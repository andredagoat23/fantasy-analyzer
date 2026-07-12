"""Claude-powered draft advisor for the live snake draft (v1.1).

Pure Python — no Streamlit in here. app.py owns the UI + the API key (via
st.secrets) and passes a client + messages down. This keeps the LLM layer
testable and keeps the app free of modeling.
"""

import anthropic
import pandas as pd

# Adaptive by task: the quick "Recommend my pick" button uses the fastest model (live clock),
# typed conversation uses a deeper one. No extended thinking on either — speed matters live.
MODEL_PICK = "claude-haiku-4-5"
MODEL_CHAT = "claude-sonnet-4-6"

# D/ST draft ranking (defenses aren't projected in the pipeline — this is the reference the advisor
# uses for the 1 D/ST pick). Loaded once; edit data/dst_rankings.csv to update.
try:
    _dst = pd.read_csv("data/dst_rankings.csv", comment="#")
    DST_TEXT = "  ".join(f"{r.rank}.{r.team}(T{r.tier})" for r in _dst.itertuples())
except Exception:
    DST_TEXT = ""

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

D/ST & KICKER (streamers — draft LAST)
Never draft a D/ST or K before your starting lineup is full — they're last-2-3-rounds picks with tiny week-to-week edges. Defenses aren't in the main board data; when I ask about D/ST, recommend from the D/ST ranking I give you (Tier 1 are the best; a Tier 1-2 defense late is ideal, and don't reach — they're nearly interchangeable). For kickers, just grab a top-scoring one in the final round.

SCARCITY-PIVOT RULE
When a position's startable pool is running thin, prefer pivoting to a still-deep position rather than reaching for a low-VOLS player — UNLESS the scarce-position player is a clear VALUE.

SURVIVAL / "will he wheel back to me?" REASONING
I give you my EXACT draft position each turn in the DRAFT POSITION line — the overall pick on the clock, my next pick number(s), and how many picks until I'm up. USE THOSE NUMBERS DIRECTLY. Never recompute my picks or ask me for them; trust the numbers given. To judge if a player wheels back, compare his ADP to MY NEXT PICK number:
- ADP well past my next pick (~8-12+ later) → likely makes it back; I can wait and take a scarcer/better-fit player now.
- ADP at or before my next pick → likely gone; take him now if I want him.
Treat ADP as approximate (~a round of swing). Let my RISK APPETITE break close calls: risk-averse → grab him now; risk-tolerant → wait for value. Always state the tradeoff ("likely back at your next pick at #X" / "won't last to #X — take him now").

RISK APPETITE CONTROL
The board has a "Risk appetite" dial (Full send / Aggressive / Balanced / Cautious / Safe) that fades risky (injury-prone, boom/bust) players on the Everything board. When I state or change my risk preference, set the dial by ending your reply with a tag on its own line: [[risk:LEVEL]] using EXACTLY one of those five labels. Map my words: "safe / high floor / conservative / avoid busts" -> Safe (or Cautious if milder); "balanced" -> Balanced; "some upside / aggressive" -> Aggressive; "max upside / boom or bust / ignore risk / all ceiling" -> Full send. Only add the tag when I actually express a risk preference — never otherwise. Still answer my question normally; the tag is an extra line at the very end.

DRAFT SETUP CONTROL
When I tell you my draft slot (which seat I pick from, e.g. "I'm picking 3rd") or my league size (number of teams), set them on the board by adding tags at the very end of your reply: [[slot:N]] for my seat and/or [[teams:N]] for the number of teams. Example: "I draft 3rd in a 12-team snake" -> [[slot:3]] [[teams:12]]. Only add these when I actually state that info.

STYLE (both modes)
Be concise and skimmable, bold player names, and ground everything in the data I gave you. TRUST: when you point me toward a player the crowd is fading (his ADP or expert rank is worse than where your board has him), say so out loud and give the ONE reason he's a value on my board — I get nervous picking guys the internet says to avoid, so tell me why we're right. A specific mode instruction follows below."""


# Appended per call depending on how I engaged (button vs. typing).
PICK_MODE = """MODE: PICK — I just hit "Recommend my pick" and I'm ON THE CLOCK. Give me your single best pick RIGHT NOW: one **bold name** + at most one short sentence why (need / value / will-he-wheel-back), then one **bold** fallback in a few words. Under ~50 words total. No preamble, no long options list, no questions back — just make the call, fast."""

CHAT_MODE = """MODE: CONVERSATION — I'm talking things through, NOT asking for a pick. Discuss, compare, react, answer my question. Do NOT declare a single "pick" or tell me who to draft unless I literally ask "who should I take / who do I pick." Just have the conversation with me. Keep it short."""


def build_context(available, mine_df, scarcity, draft_pos=None, top_n=35):
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

    dp_line = ""
    if draft_pos:
        d = draft_pos
        dp_line = (f"DRAFT POSITION: I pick at slot {d['slot']} of {d['teams']} (snake). "
                   f"On the clock: overall pick #{d['overall_now']}. ")
        if d["my_turn"]:
            dp_line += "It is MY pick RIGHT NOW."
            if d.get("following"):
                gap = d["following"] - d["overall_now"]
                dp_line += (f" My next pick after this is #{d['following']} ({gap} picks away) — "
                            f"compare ADPs to #{d['following']} to judge who wheels back to me.")
        else:
            dp_line += f"Not my pick — I'm up next at #{d['next_pick']} ({d['picks_away']} picks away)."
            if d.get("following"):
                dp_line += f" Then #{d['following']} after that."
        dp_line += "\n"

    dst_line = f"\n\nD/ST draft ranking (streamer, draft late): {DST_TEXT}" if DST_TEXT else ""
    return (
        "LIVE DRAFT STATE\n"
        + dp_line +
        f"My roster (projected {proj:.0f} pts): {roster}\n"
        f"Startable players left by position: {scar}\n\n"
        f"Top {len(top)} available players (sorted by composite value; "
        f"ADP 'UD' = undrafted/no ADP, i.e. very likely to still be available later):\n{board_txt}"
        f"{dst_line}"
    )


def get_client(api_key):
    return anthropic.Anthropic(api_key=api_key)


PARSE_SCORING = """You translate a fantasy football league's scoring settings into a clean, structured breakdown.
The user pastes their league's scoring rules — often messy, copied from ESPN / Sleeper / Yahoo settings.
Return a compact markdown bullet list grouped by category (Passing, Rushing, Receiving, Kicking, D/ST, Bonuses, Misc).
Use points-per-unit (e.g. "Passing yards: 1 pt / 25 yds", "Passing TD: 4", "INT: -2").
State the PPR type explicitly on its own line first (Standard / Half-PPR / Full-PPR), inferred from points per reception.
Omit any category that isn't specified. No preamble and no closing remarks — just the breakdown."""


def parse_scoring(client, raw_text):
    """One-shot: turn pasted league scoring settings into a clean structured breakdown."""
    msg = client.messages.create(
        model=MODEL_PICK,                       # fast + cheap; this is a simple parse
        max_tokens=600,
        system=PARSE_SCORING,
        messages=[{"role": "user", "content": raw_text}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


def stream_advice(client, messages, mode="chat"):
    """Yield the response text token-by-token for st.write_stream.

    mode="pick"  -> fast model, terse pick-first answer (the button).
    mode="chat"  -> deeper model, pure conversation (typed messages).
    """
    is_pick = mode == "pick"
    system = SYSTEM + "\n\n" + (PICK_MODE if is_pick else CHAT_MODE)
    with client.messages.stream(
        model=MODEL_PICK if is_pick else MODEL_CHAT,
        max_tokens=400 if is_pick else 900,
        system=system,
        messages=messages,
    ) as stream:
        yield from stream.text_stream
