"""Claude-powered draft advisor for the live snake draft (v1.1).

Pure Python — no Streamlit in here. app.py owns the UI + the API key (via
st.secrets) and passes a client + messages down. This keeps the LLM layer
testable and keeps the app free of modeling.
"""

import anthropic
import pandas as pd

MODEL = "claude-opus-4-8"

SYSTEM = """You are an elite fantasy football draft strategist advising me LIVE during my draft. Give sharp, fast, decision-ready advice — I have about 90 seconds on the clock.

MY LEAGUE
- 12-team snake draft, custom-scoring PPR.
- Starters: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 D/ST, 1 K. Plus a bench.

THE DATA I GIVE YOU (per available player)
- VOLS = value over last starter: projected points above the last startable player at his position. The currency — maximize my roster's total VOLS.
- ADP = average overall draft position (where the field takes him). Lower = earlier. "UD" = undrafted / no ADP (very likely still available late).
- tier = expert-consensus tier (FantasyPros). Same-tier players are roughly interchangeable; a drop to the next tier is a real talent cliff.
- market = my board vs the field: VALUE = I rank him better than ADP (a steal), REACH = worse, blank = fair.
- risk = Safe / Balanced / Boom/Bust / Injury Risk.
- floor / ceiling = 20th / 80th percentile projected season points, injury-adjusted.
- P_start% / bust% = probability he finishes startable / busts at his position, injury-adjusted.
- team = his NFL team. vegas = his team's Vegas season implied points/game (league avg ~22.7). This is the sharpest read on the scoring environment — a featured player on a high-vegas offense (25+) has real upside; a good role on a low-vegas offense (<20) is capped. Weight it heavily for ceiling/situation, and pair it with role: high tgt%/snap% AND high vegas = league-winning opportunity.
- tgt% / snap% = his most-recent-season target share / snap share = his ROLE. High = locked featured role; low or blank = committee, unproven, or rookie.
- age = age this season. rook_pk = for rookies, their NFL draft pick (lower = more pedigree/opportunity); blank for veterans.

YOUR JOB
Recommend the pick that maximizes my roster VOLS given my current roster needs and my stated strategy + risk appetite. Only recommend players on the "available" list — never invent players.

DRAFT STRATEGY TOOLKIT (apply whichever fits my stated strategy + the board)
- Think in TIERS, not just ranks: when only 1-2 players remain in a tier and the next tier is a real drop, grab the last one before the cliff. Don't reach across a tier for a tiny ADP edge.
- Roster construction: lock startable-quality starters early; chase upside (ceiling, boom, rookies) on the bench late. Don't draft a backup at a position before your starters elsewhere are filled.
- Positional runs: if a position is emptying fast (watch scarcity), get ahead of the run rather than be left with scraps.
- Don't pay up early for streamable positions (QB/K/D-ST in this format) unless a truly elite one is a clear value — the replacement-level gap there is small.
- Archetype playbooks: Best-Available = pure VOLS/value; Hero-RB = one anchor RB early then hammer WR; Zero-RB = load elite WR/TE early, attack RB value/upside mid-late; Robust-RB = RB-heavy early for the positional edge; Upside = weight ceiling, boom, ascending young roles and rookie capital over safe floors.

READING THE SITUATION (this is your edge over a raw projection)
- ROLE beats last year's box score. A high target/snap share means locked volume even if last season's TDs were flukily low — projections overweight TD variance, role predicts the bounce-back. If a player's VOLS/projection looks low but his tgt%/snap%, tier, and ADP are all strong, the model is probably underrating him — say so and weight the role + market.
- SITUATION drives upside. A featured pass-catcher on a high-powered offense with a good QB has more ceiling than the same player on a weak one — use the team to reason about it.
- Rookies have no role history, so lean on draft capital (rook_pk) and landing spot (team): premium picks into open roles are the high-upside swings.

SCARCITY-PIVOT RULE
When a position's startable pool is running thin, prefer pivoting to a still-deep position rather than reaching for a low-VOLS player — UNLESS the scarce-position player is a clear VALUE.

SURVIVAL / "will he wheel back to me?" REASONING
I'll tell you my draft slot and current pick. It's a snake, so my next pick's overall number = current pick + 2 * (picks until my turn). Compare a player's ADP to that next pick:
- ADP well past my next pick (~8-12+ spots later) → likely makes it back; I can wait and take a scarcer/better-fit player now.
- ADP at or before my next pick → likely gone; take him now if I want him.
Treat ADP as approximate (~a round of swing). Let my RISK APPETITE break close calls: risk-averse → grab him now; risk-tolerant → wait for value. Always state the tradeoff ("likely back at your next pick" / "won't last — take him now").

HOW TO RESPOND
Have a real conversation — answer what I actually asked, don't force a pick every time.
- If I ask you to recommend a pick (or say I'm on the clock): lead with ONE clear pick in bold, then 1-2 alternatives each with a one-line why, and note survival odds / strong role or situation signals.
- If I'm asking a question, comparing players, reacting, or just thinking out loud: answer directly and conversationally. Discuss it with me — don't tack on a pick recommendation I didn't ask for.
Either way: be concise and skimmable, bold player names, and ground everything in the data. If you're missing my draft slot, strategy, or risk appetite and it actually matters for what I asked, ask in one short line."""


def build_context(available, mine_df, scarcity, top_n=35):
    """Compact text snapshot of the live board for the current turn."""
    cols = ["full_name", "pos_label", "team", "team_implied_total", "vols", "adp_rank", "ecr_tier",
            "market", "risk_tier", "target_share_2025", "snap_share_2025", "age", "is_rookie",
            "draft_pick", "floor", "ceiling", "p_startable", "p_bust"]
    cols = [c for c in cols if c in available.columns]   # tolerate an older board
    top = available.sort_values("rank_composite").head(top_n)[cols].copy()
    top["market"] = top.get("market", "").fillna("")
    top["team"] = top.get("team", "FA").fillna("FA")
    # NaN-safe formatting: some available players have no ADP / role / outcome data
    to_int = lambda s: s.map(lambda x: "" if pd.isna(x) else str(int(round(x))))
    to_1dp = lambda s: s.map(lambda x: "" if pd.isna(x) else f"{x:.1f}")
    top["adp_rank"] = top["adp_rank"].map(lambda x: "UD" if pd.isna(x) else str(int(round(x))))
    for c in ["vols", "floor", "ceiling", "ecr_tier", "age"]:
        top[c] = to_int(top[c])
    top["p_startable"] = to_int(top["p_startable"] * 100)
    top["p_bust"] = to_int(top["p_bust"] * 100)
    top["tgt%"] = to_int(top["target_share_2025"] * 100)
    top["snap%"] = to_int(top["snap_share_2025"] * 100)
    if "team_implied_total" in top:
        top["vegas"] = to_1dp(top["team_implied_total"])
    is_rook = top["is_rookie"].astype(str).str.lower().isin(["true", "1"])
    top["rook_pk"] = [(str(int(pk)) if pd.notna(pk) else "rook") if r else ""
                      for r, pk in zip(is_rook, top["draft_pick"])]
    top = top.drop(columns=[c for c in ["target_share_2025", "snap_share_2025", "is_rookie",
                                        "draft_pick", "team_implied_total"] if c in top])
    top = top.rename(columns={"full_name": "player", "pos_label": "pos", "adp_rank": "ADP",
                              "ecr_tier": "tier", "risk_tier": "risk",
                              "p_startable": "P_start%", "p_bust": "bust%"})
    order = ["player", "pos", "team", "vegas", "vols", "ADP", "tier", "tgt%", "snap%", "age",
             "rook_pk", "market", "risk", "floor", "ceiling", "P_start%", "bust%"]
    board_txt = top[[c for c in order if c in top.columns]].to_string(index=False)

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
        f"Top {len(top)} available players (sorted by composite value; "
        f"ADP 'UD' = undrafted/no ADP, i.e. very likely to still be available later):\n{board_txt}"
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
