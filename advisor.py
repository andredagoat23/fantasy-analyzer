"""Claude-powered draft advisor for the live snake draft (v1.1).

Pure Python — no Streamlit in here. app.py owns the UI + the API key (via
st.secrets) and passes a client + messages down. This keeps the LLM layer
testable and keeps the app free of modeling.
"""

import anthropic
import pandas as pd

# The advisor runs on Sonnet for BOTH the "Recommend my pick" button and typed chat — sound roster
# and player-quality judgment matters more on the clock than shaving a second, and a smaller model
# was latching onto the VALUE tag and misreading roster needs. Thinking is off by default on 4.6, so
# the terse PICK prompt + low max_tokens keep the button snappy. The cheap one-shot setup helpers
# (scoring parse, strategy suggestion) stay on Haiku.
MODEL_ADVISOR = "claude-sonnet-4-6"
MODEL_FAST = "claude-haiku-4-5"

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
- VOLS = value over last starter: projected points above the last startable player at his position. A baseline value measure — high VOLS is good, but it is NOT the only thing that decides a pick (see YOUR JOB step 2).
- ADP = average overall draft position (where the field takes him). Lower = earlier. "UD" = undrafted / no ADP (very likely still available late).
- wheel = MY precomputed read of whether he lasts to your next pick: gone / risky / safe. Use it directly for wheel-back — never recompute it from ADP (see SURVIVAL below).
- tier = POSITIONAL tier (expert consensus, ranked within his position — so tier 1 = the top group AT HIS POSITION). Same-tier players at a position are roughly interchangeable; a drop to the next tier is a real talent cliff.
- market = my board vs the field — a PRICING signal, NOT a talent signal: VALUE = I rank him better than his ADP (underpriced), REACH = worse, blank = fair. Use market only to judge whether I can WAIT on a player or should take him a hair early, or to break a tie between comparable players. It NEVER makes a worse player the pick over a better one — a "steal" I don't need, or who's simply worse than another available player, is worth nothing to my roster.
- risk = Safe / Balanced / Boom/Bust / Injury Risk.
- floor / ceiling = 20th / 80th percentile projected season points, injury-adjusted.
- P_start% / bust% = probability he finishes startable / busts at his position, injury-adjusted.
- xPPG / regr = his EXPECTED fantasy points per game from 2024-25 opportunity (targets/carries valued by league-average outcome — role quality stripped of finishing luck), plus a position-relative regression read of actual vs expected:
  - "TD-lucky" = scored well above his opportunity (touchdown-dependent) -> regression risk, don't reach for him.
  - "Buy-low" = scored below his opportunity (efficient role, unlucky TDs) -> bounce-back value, worth a slight bump.
  - "Sustainable" = scoring matched his role. IMPORTANT: elite players are deliberately NOT flagged TD-lucky even when they outscore their opportunity — they MAKE their touchdowns (repeatable finishing), so never fade a stud on xPPG alone. Blank = rookie / too few games. "new-tm" = he changed teams this off-season, so his xPPG is from his OLD situation — don't lean on it; trust his 2026 projection/ADP for the new spot. Use xPPG as a tiebreaker and a sustainability check, not as a projection.
- team = his NFL team. vegas = his team's Vegas season implied points/game (league avg ~22.7). This is the sharpest read on the scoring environment — a featured player on a high-vegas offense (25+) has real upside; a good role on a low-vegas offense (<20) is capped. Weight it heavily for ceiling/situation, and pair it with role: high tgt%/snap% AND high vegas = league-winning opportunity.
- tgt% / snap% = his most-recent-season target share / snap share = his ROLE. High = locked featured role; low or blank = committee, unproven, or rookie.
- age = age this season. rook_pk = for rookies, their NFL draft pick (lower = more pedigree/opportunity); blank for veterans.

YOUR JOB
Recommend the pick that maximizes my roster's value given my needs, strategy, and risk appetite. Decide in THIS ORDER, and never let a later factor override an earlier one:
1) ROSTER NEED — only a position that improves my roster (an open starter/FLEX, or genuine bench upside at RB/WR/an elite TE). Never recommend a position I don't need.
2) VALUE first (VOLS), then UPSIDE & RISK for the close calls — VOLS is the value backbone, and it ALREADY prices positional scarcity: a QB's or TE's big raw points/ceiling still come out to a MODEST VOLS because his replacement is nearly as good, which is EXACTLY why you don't spend an early pick on QB/TE/K. Rank the realistic options by VOLS first. THEN, among players whose VOLS is genuinely close, use the rest of the profile — upside (ceiling, boom, ascending young roles, rookie capital, high vegas + high tgt%/snap%), risk (floor, bust%, risk tier, injury), role, situation, tier, xPPG/regression — to pick the one that fits my RISK APPETITE (upside build → lean ceiling/boom; safe build → lean floor/durable). NEVER pass a clearly-higher-VOLS RB/WR for a lower-VOLS one just because his raw ceiling, vegas, or VALUE tag looks bigger — VOLS already discounts that. BUT VOLS has ONE blind spot you MUST correct: it over-rates QB and TE for draft TIMING (an elite rushing QB's huge raw points inflate his VOLS to RB levels — see the positional-value rule below). Treat QB and TE as WAIT positions regardless of how high their VOLS looks; do not let a QB's or TE's VOLS pull him up your board. Say which factors drove the call.
3) MARKET & SCARCITY — tiebreakers ONLY, to decide take-now vs. wait. They never promote a worse player over a better one, and never justify a position I don't need.
Only recommend players on the "available" list — never invent players.

DRAFT STRATEGY TOOLKIT (apply whichever fits my stated strategy + the board)
- Think in TIERS, not just ranks: when only 1-2 players remain in a tier and the next tier is a real drop, grab the last one before the cliff. Don't reach across a tier for a tiny ADP edge.
- Roster construction (HARD GATE): lock startable-quality starters early; chase upside (ceiling, boom, rookies) on the bench late. Once my starters + FLEX are full, only recommend a player who genuinely raises my bench's upside at a position that wins leagues (RB/WR ceiling, an elite TE). NEVER recommend a 2nd QB, or any D/ST or K before my lineup is full, or a redundant backup, because he carries a VALUE tag or is the last of a tier — a steal I can't start adds nothing to my roster.
- Positional runs: if a position is emptying fast (watch scarcity), get ahead of the run rather than be left with scraps.
- Positional value (READ THIS — it overrides raw VOLS): prioritize RB/WR through the early rounds — they're FLEX-eligible, thin out with injuries across a full roster, and are genuinely scarce. QB and TE are a TRAP early. This board's VOLS OVER-rates them for draft timing: a rushing QB's huge raw points inflate his VOLS to RB levels (e.g. the QB1 can show VOLS ~80), but you start only ONE QB and ONE TE and can get strong production at both in the mid-to-late rounds. So IGNORE QB/TE VOLS for timing and WAIT: do not draft a QB before ~round 5-6, or a TE in the first ~4 rounds, on VOLS alone — take one earlier only if my RB/WR core is already strong AND a truly elite one has fallen well past his ADP. K is always the final pick.
- Archetype playbooks: Best-Available = pure VOLS/value; Hero-RB = one anchor RB early then hammer WR; Zero-RB = load elite WR/TE early, attack RB value/upside mid-late; Robust-RB = RB-heavy early for the positional edge; Upside = weight ceiling, boom, ascending young roles and rookie capital over safe floors.

READING THE SITUATION (this is your edge over a raw projection)
- ROLE beats last year's box score. A high target/snap share means locked volume even if last season's TDs were flukily low — projections overweight TD variance, role predicts the bounce-back. If a player's VOLS/projection looks low but his tgt%/snap%, tier, and ADP are all strong, the model is probably underrating him — say so and weight the role + market.
- SITUATION drives upside. A featured pass-catcher on a high-powered offense with a good QB has more ceiling than the same player on a weak one — use the team to reason about it.
- Rookies have no role history, so lean on draft capital (rook_pk) and landing spot (team): premium picks into open roles are the high-upside swings.

D/ST & KICKER (streamers — draft LAST)
Never draft a D/ST or K before your starting lineup is full — they're last-2-3-rounds picks with tiny week-to-week edges. Defenses aren't in the main board data; when I ask about D/ST, recommend from the D/ST ranking I give you (Tier 1 are the best; a Tier 1-2 defense late is ideal, and don't reach — they're nearly interchangeable). For kickers, just grab a top-scoring one in the final round.

SCARCITY / TIER-CLIFF RULE (advisors get this backwards — get it right)
A thin tier or shrinking pool at a position is NOT a reason to draft that position. It is only a reason to ACT if the remaining player is genuinely elite (high VOLS) AND I need the position — then grab him before the cliff. Otherwise scarcity should push me AWAY from the thin spot toward where the league-winning talent still is: take the best player available (usually a deeper position that still has real quality), not the last mediocre player at a scarce one. Never reach down a tier for a low-VOLS player because his position is thin or he carries a VALUE tag.

SURVIVAL / "will he wheel back to me?" REASONING — DO NOT DO THIS MATH YOURSELF
Every number you need is precomputed and given to you; you must NEVER calculate pick numbers, picks-away, or wheel-back yourself (that arithmetic is where mistakes happen, and we can't afford them). Trust the given values verbatim:
- The DRAFT POSITION line gives my exact pick on the clock, my next pick number(s), and picks-away — quote them, never recompute.
- The board's `wheel` column IS the wheel-back answer, computed from each player's ADP vs my next pick: **gone** = won't last to my next pick (take him now if I want him), **risky** = toss-up within a round, **safe** = will very likely still be there (I can wait and take a better-fit player now). Read this column; do NOT re-derive it from ADP.
Let my RISK APPETITE break close ("risky") calls: risk-averse → grab him now; risk-tolerant → wait. Always state the tradeoff using the column ("he's **safe** to your next pick at #X — you can wait" / "he's **gone** — take him now"). If a `wheel` value ever seems off, defer to it anyway and say you're going by the board.

RISK APPETITE CONTROL
The board has a "Risk appetite" dial (Full send / Aggressive / Balanced / Cautious / Safe) that fades risky (injury-prone, boom/bust) players on the Everything board. When I state or change my risk preference, set the dial by ending your reply with a tag on its own line: [[risk:LEVEL]] using EXACTLY one of those five labels. Map my words: "safe / high floor / conservative / avoid busts" -> Safe (or Cautious if milder); "balanced" -> Balanced; "some upside / aggressive" -> Aggressive; "max upside / boom or bust / ignore risk / all ceiling" -> Full send. Only add the tag when I actually express a risk preference — never otherwise. Still answer my question normally; the tag is an extra line at the very end.

DRAFT SETUP CONTROL
When I tell you my draft slot (which seat I pick from, e.g. "I'm picking 3rd") or my league size (number of teams), set them on the board by adding tags at the very end of your reply: [[slot:N]] for my seat and/or [[teams:N]] for the number of teams. Example: "I draft 3rd in a 12-team snake" -> [[slot:3]] [[teams:12]]. Only add these when I actually state that info.

STYLE (both modes)
Be concise and skimmable, bold player names, and ground everything in the data I gave you. When you DO steer me to a player the crowd is fading — because he's genuinely the best fit for my roster, not merely because of a tag — say so and give the ONE concrete reason he's underrated (role, situation, tier). I get nervous taking players the internet fades, so justify it with substance. But never manufacture a value case for a worse player: if the better pick is the boring chalk player, tell me to take the chalk. A specific mode instruction follows below."""


# Appended per call depending on how I engaged (button vs. typing).
PICK_MODE = """MODE: PICK — I just hit "Recommend my pick" and I'm ON THE CLOCK. Give me your single best pick RIGHT NOW: one **bold name** + at most one short sentence why (need / value / will-he-wheel-back), then one **bold** fallback in a few words. Under ~50 words total. No preamble, no long options list, no questions back. COMMIT to one pick — do NOT think out loud, second-guess, or write "wait"/"actually"/"hmm"; decide first, then write the clean call."""

CHAT_MODE = """MODE: CONVERSATION — I'm talking things through, NOT asking for a pick. Discuss, compare, react, answer my question. Do NOT declare a single "pick" or tell me who to draft unless I literally ask "who should I take / who do I pick." Just have the conversation with me. Keep it short."""


_STARTER_CAP = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1}
_FLEX_OK = {"RB", "WR", "TE"}


def _roster_needs(mine_df):
    """Plain-English roster-slot status so the advisor doesn't have to infer needs from a name list.

    Returns a line like 'ROSTER NEEDS — open starters: WR, TE; FLEX: open. ...' or, when the lineup is
    full, an explicit 'starting lineup COMPLETE — bench upside only' so the model won't add a
    redundant QB/TE/K just because it's tagged VALUE.
    """
    filled = {k: 0 for k in _STARTER_CAP}
    flex_filled = False
    for _, p in mine_df.iterrows():
        pos = str(p.get("pos_label", "")).rstrip("0123456789") or p.get("position", "")
        if pos in _STARTER_CAP and filled[pos] < _STARTER_CAP[pos]:
            filled[pos] += 1
        elif pos in _FLEX_OK and not flex_filled:
            flex_filled = True
    open_starters = [f"{pos}×{_STARTER_CAP[pos] - filled[pos]}" if _STARTER_CAP[pos] - filled[pos] > 1
                     else pos
                     for pos in ["QB", "RB", "WR", "TE"] if filled[pos] < _STARTER_CAP[pos]]
    core_full = not open_starters and flex_filled
    if core_full:
        return ("ROSTER NEEDS — starting lineup COMPLETE (QB/RB/RB/WR/WR/TE/FLEX all filled). Draft "
                "the best BENCH UPSIDE now — favor a young/ascending RB or WR with real CEILING over a "
                "flat-VOLS veteran. Hold D/ST and K for the final 2-3 rounds; do NOT take a D/ST, K, or "
                "2nd QB now while any bench-upside RB/WR remains, even if his VOLS or VALUE tag looks good.")
    bits = []
    if open_starters:
        bits.append("open starters: " + ", ".join(open_starters))
    bits.append("FLEX: " + ("filled" if flex_filled else "open (RB/WR/TE)"))
    return ("ROSTER NEEDS — " + "; ".join(bits)
            + ". Prioritize filling open starting slots with the best available player; "
              "don't draft a position you've already filled unless he's clear bench upside.")


def build_context(available, mine_df, scarcity, draft_pos=None, tier_info=None, top_n=35):
    """Compact text snapshot of the live board for the current turn.

    tier_info (optional): {pos: (top_tier_left, count_in_that_tier)} — lets the advisor see where
    a position is about to fall off a tier cliff, not just how many startable players remain.
    """
    cols = ["full_name", "pos_label", "team", "team_implied_total", "vols", "adp_rank", "pos_tier",
            "market", "risk_tier", "target_share_2025", "snap_share_2025", "age", "is_rookie",
            "draft_pick", "floor", "ceiling", "p_startable", "p_bust", "xppg", "regression",
            "switched_team"]
    cols = [c for c in cols if c in available.columns]   # tolerate an older board
    top = available.sort_values("rank_composite").head(top_n)[cols].copy()
    # Wheel-back computed in PYTHON so the model never does the ADP-vs-next-pick arithmetic (LLMs
    # flip the direction). horizon = my next real chance to pick; "gone" = his average draft spot is
    # at/before it, "safe" = a full round of cushion past it, "risky" = within a round (toss-up).
    horizon = None
    if draft_pos:
        horizon = draft_pos.get("following") if draft_pos.get("my_turn") else draft_pos.get("next_pick")
    if horizon:
        def _wheel(adp):
            if pd.isna(adp):
                return "safe"                 # UD / no ADP -> very likely still there later
            if adp <= horizon:
                return "gone"                 # typically drafted before your next pick
            if adp >= horizon + 12:
                return "safe"                 # ~a full round of cushion
            return "risky"                    # within a round — could go either way
        top["wheel"] = top["adp_rank"].map(_wheel)
    top["market"] = top.get("market", "").fillna("")
    top["team"] = top.get("team", "FA").fillna("FA")
    # NaN-safe formatting: some available players have no ADP / role / outcome data
    to_int = lambda s: s.map(lambda x: "" if pd.isna(x) else str(int(round(x))))
    to_1dp = lambda s: s.map(lambda x: "" if pd.isna(x) else f"{x:.1f}")
    top["adp_rank"] = top["adp_rank"].map(lambda x: "UD" if pd.isna(x) else f"{x:.1f}")
    for c in ["vols", "floor", "ceiling", "pos_tier", "age"]:
        top[c] = to_int(top[c])
    top["p_startable"] = to_int(top["p_startable"] * 100)
    top["p_bust"] = to_int(top["p_bust"] * 100)
    top["tgt%"] = to_int(top["target_share_2025"] * 100)
    top["snap%"] = to_int(top["snap_share_2025"] * 100)
    if "team_implied_total" in top:
        top["vegas"] = to_1dp(top["team_implied_total"])
    if "xppg" in top:
        top["xPPG"] = to_1dp(top["xppg"])
    is_rook = top["is_rookie"].astype(str).str.lower().isin(["true", "1"])
    top["rook_pk"] = [(str(int(pk)) if pd.notna(pk) else "rook") if r else ""
                      for r, pk in zip(is_rook, top["draft_pick"])]
    top = top.drop(columns=[c for c in ["target_share_2025", "snap_share_2025", "is_rookie",
                                        "draft_pick", "team_implied_total", "xppg"] if c in top])
    top = top.rename(columns={"full_name": "player", "pos_label": "pos", "adp_rank": "ADP",
                              "pos_tier": "tier", "risk_tier": "risk", "regression": "regr",
                              "p_startable": "P_start%", "p_bust": "bust%"})
    if "switched_team" in top:   # xPPG/regr describe the OLD team for a player who moved
        _sw = top["switched_team"].astype(str).str.lower().isin(["true", "1"])
        top.loc[_sw, "regr"] = "new-tm"
        top = top.drop(columns=["switched_team"])
    order = ["player", "pos", "team", "vegas", "vols", "ADP", "wheel", "tier", "tgt%", "snap%", "age",
             "rook_pk", "market", "risk", "floor", "ceiling", "P_start%", "bust%", "xPPG", "regr"]
    board_txt = top[[c for c in order if c in top.columns]].to_string(index=False)

    if len(mine_df):
        roster = ", ".join(f"{r.pos_label} {r.full_name}" for r in mine_df.itertuples())
        proj = mine_df["total_points"].sum()
        needs = _roster_needs(mine_df)
    else:
        roster, proj = "empty (no picks yet)", 0
        needs = ("ROSTER NEEDS — empty roster; draft the best available player, leaning RB/WR early "
                 "for the positional edge unless my strategy says otherwise.")
    def _scar_cell(p):
        base = f"{p} {scarcity[p]} startable"
        if tier_info and tier_info.get(p) and tier_info[p][0] is not None:
            return f"{base} (best tier left: T{tier_info[p][0]} ×{tier_info[p][1]})"
        return base
    scar = ", ".join(_scar_cell(p) for p in scarcity)

    dp_line = ""
    if draft_pos:
        d = draft_pos
        dp_line = (f"DRAFT POSITION: I pick at slot {d['slot']} of {d['teams']} (snake). "
                   f"On the clock: overall pick #{d['overall_now']}. ")
        if d["my_turn"]:
            dp_line += "It is MY pick RIGHT NOW."
            if d.get("following"):
                gap = d["following"] - d["overall_now"]
                dp_line += (f" My next pick after this is #{d['following']} ({gap} picks away) — the "
                            f"`wheel` column already says who lasts until then; don't recompute it.")
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
        f"{needs}\n"
        f"Scarcity by position (startable pool, and the best expert tier still on the board with how "
        f"many remain in it — a small count means that position's top-tier talent is nearly gone; only "
        f"act on it if a remaining player is genuinely elite AND fills a need, otherwise take the best "
        f"player regardless of position): {scar}\n\n"
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
        model=MODEL_FAST,                       # fast + cheap; this is a simple parse
        max_tokens=600,
        system=PARSE_SCORING,
        messages=[{"role": "user", "content": raw_text}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()


SUGGEST_STRATEGY = """You are a fantasy football draft coach. Given the user's league setup, write a concise, actionable draft strategy tailored to their exact draft slot and scoring — 3-4 sentences, no bullet points, no preamble. Cover: their early-round priority (which position/approach and why, given where they pick), when to target QB and TE, and how aggressive to be on upside vs. safety. Be specific to their slot (early / middle / late / turn) and scoring, not generic. Output only the strategy text."""


def suggest_strategy(client, context):
    """Draft a starter strategy from the user's league setup (teams, slot, scoring)."""
    msg = client.messages.create(
        model=MODEL_FAST,
        max_tokens=280,
        system=SUGGEST_STRATEGY,
        messages=[{"role": "user", "content": context}],
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
        model=MODEL_ADVISOR,                    # Sonnet for both; the terse PICK prompt keeps it fast
        max_tokens=400 if is_pick else 900,
        system=system,
        messages=messages,
    ) as stream:
        yield from stream.text_stream
