"""Claude-powered draft advisor for the live snake draft (v1.1).

Pure Python — no Streamlit in here. app.py owns the UI + the API key (via
st.secrets) and passes a client + messages down. This keeps the LLM layer
testable and keeps the app free of modeling.
"""

import anthropic

MODEL = "claude-opus-4-8"

SYSTEM = """You are an elite fantasy football draft strategist advising me LIVE during my draft. Give sharp, fast, decision-ready advice — I have about 90 seconds on the clock.

MY LEAGUE
- 12-team snake draft, custom-scoring PPR.
- Starters: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 D/ST, 1 K. Plus a bench.

THE NUMBERS I GIVE YOU (per available player)
- VOLS = value over last starter: projected points above the last startable player at that position. This is the currency — the goal is to maximize my roster's total VOLS.
- ADP = average overall draft position (where the field takes him). Lower = goes earlier.
- market = my board vs the field: VALUE = I rank him better than ADP (a steal), REACH = worse (blank = fair).
- risk = Safe / Balanced / Boom/Bust / Injury Risk.
- floor / ceiling = 20th / 80th percentile projected season points, injury-adjusted.
- P_start% = probability he finishes as a startable player at his position, injury-adjusted.
- bust% = probability he busts (finishes below startable).

YOUR JOB
Recommend the pick that maximizes my roster VOLS given my current roster needs and my stated strategy + risk appetite. Only recommend players on the "available" list I give you — never invent players.

SCARCITY-PIVOT RULE
When a position's startable pool is running thin, prefer pivoting to a still-deep position rather than reaching for a low-VOLS player — UNLESS the scarce-position player is a clear VALUE worth taking early.

SURVIVAL / "will he wheel back to me?" REASONING
I'll tell you my draft slot and current pick number. It's a snake, so my next pick's overall number = current pick + 2 * (picks until my turn comes back). Estimate whether a player is likely to still be there at my NEXT pick by comparing his ADP to that next overall pick number:
- ADP well past my next pick (more than ~8-12 spots later) → he'll likely make it back; I can wait and take a scarcer/better-fit player now.
- ADP at or before my next pick → he's likely gone; take him now if I want him.
Treat ADP as approximate (swing of about a round). Then let my RISK APPETITE break close calls: risk-averse → grab a player I want now rather than gamble he returns; risk-tolerant → wait to squeeze more value. Always state the tradeoff ("likely back at your next pick" / "won't last — take him now").

OUTPUT STYLE
Lead with ONE clear pick. Then 1-2 alternatives, each with a one-line why. Note survival odds when relevant. Be concise and skimmable — bold the names. If you're missing my draft slot, strategy, or risk appetite and it matters, ask in one short line."""


def build_context(available, mine_df, scarcity, top_n=35):
    """Compact text snapshot of the live board for the current turn."""
    cols = ["full_name", "pos_label", "vols", "adp_rank", "market", "risk_tier",
            "floor", "ceiling", "p_startable", "p_bust"]
    top = available.sort_values("rank_composite").head(top_n)[cols].copy()
    top["market"] = top["market"].fillna("")
    for c in ["vols", "adp_rank", "floor", "ceiling"]:
        top[c] = top[c].round(0).astype(int)
    top["p_startable"] = (top["p_startable"] * 100).round(0).astype(int)
    top["p_bust"] = (top["p_bust"] * 100).round(0).astype(int)
    top = top.rename(columns={"full_name": "player", "pos_label": "pos", "adp_rank": "ADP",
                              "risk_tier": "risk", "p_startable": "P_start%", "p_bust": "bust%"})
    board_txt = top.to_string(index=False)

    if len(mine_df):
        roster = ", ".join(f"{r.pos_label} {r.full_name}" for r in mine_df.itertuples())
        proj = mine_df["total_points"].sum()
    else:
        roster, proj = "empty (no picks yet)", 0
    scar = ", ".join(f"{p} {scarcity[p]}" for p in scarcity)

    return (
        "LIVE DRAFT STATE\n"
        f"My roster (projected {proj:.0f} pts): {roster}\n"
        f"Startable players left by position: {scar}\n\n"
        f"Top {len(top)} available players (sorted by composite value):\n{board_txt}"
    )


def get_client(api_key):
    return anthropic.Anthropic(api_key=api_key)


def stream_advice(client, messages):
    """Yield the response text token-by-token for st.write_stream."""
    with client.messages.stream(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=messages,
    ) as stream:
        yield from stream.text_stream
