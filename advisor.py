"""Claude-powered draft advisor for the live snake draft (v1.1).

Pure Python — no Streamlit in here. app.py owns the UI + the API key (via
st.secrets) and passes a client + messages down. This keeps the LLM layer
testable and keeps the app free of modeling.
"""

import anthropic
import numpy as np
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
- VOLS = value over last starter: projected season points above the last startable player at his position. The season-long value BACKBONE (how good he is all year).
- VONA = Value Over Next Available — his VOLS minus the best same-position player ADP says could still be on the board at your NEXT pick, floored at replacement. THIS is the "who do I take NOW" number: the value you'd LOSE by waiting on his position. It already bakes in scarcity + who-could-still-be-left, so it's the live, personalized version of a tier drop. High VONA = a real cliff behind him (grab now); VONA near 0 = comparable value will still be there (you can wait). Precomputed — use it, never recompute. **VONA "n/a" = a position I CANNOT use (a filled 1-start QB/TE — a backup is worthless); never recommend an "n/a" player no matter his VOLS.**
- ADP = average overall draft position (where the field takes him). Lower = earlier. "UD" = undrafted / no ADP (very likely still available late).
- wheel = MY precomputed read of whether he lasts to your next pick: gone / risky / safe. Use it directly for wheel-back — never recompute it from ADP (see SURVIVAL below).
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
1) ROSTER NEED filters what's DRAFTABLE — a position that helps my roster: an open starter/FLEX, or RB/WR bench depth (RB and WR ALWAYS keep bench/FLEX value). QB and TE are 1-START positions — once mine is filled, a 2nd one is NOT draftable no matter how high its VONA (a backup QB/TE is nearly worthless — I start one and they're streamable). Never draft a filled 1-start position, or a K/D-ST before my lineup is full. Roster need does NOT force me to fill an open starter this instant: a still-open slot whose good options will KEEP (wheel "safe", low VONA) can wait while I grab a bigger VONA cliff at a draftable RB/WR — I'll fill the safe slot next pick for the same value (but don't let it rot if its options are going).
2) VALUE — DRAFT BY VONA, and the work is already done for you: the **TOP PICKS NOW** line ranks your draftable options by VONA. Recommend **#1** unless a clear risk/upside reason (per my risk appetite) bumps you to #2 or #3 — and if so, say why. NEVER bump a lower-VONA player to the top just because it fills an open starter: a safe open slot WAITS (you fill it next pick for the same value); the value cliff that won't last is the pick now. VONA already bakes in scarcity + who-could-be-left, so QB/TE fall on their own and a filled 1-start QB/TE is already excluded (VONA "n/a"). WITHIN a position, take the best available (highest VOLS).
3) UPSIDE & RISK break the close calls — when two candidates' VONA is genuinely close, pick the one that fits my RISK APPETITE: upside build → lean ceiling/boom, ascending young roles, high vegas + role; safe build → lean floor, durable, low bust. Use role / situation (vegas) / xPPG-regression as tiebreakers; `market` is a pricing tiebreaker only (can I wait on him?), never a talent signal. Say which factors drove the call.
Only recommend players on the "available" list — never invent players.

DRAFT STRATEGY TOOLKIT (apply whichever fits my stated strategy + the board)
- Draft the value CLIFF, not the rank: VONA already tells you where waiting costs the most — take the high-VONA player before the drop; don't reach across a position for a tiny ADP edge when VONA is flat.
- Positional value is handled BY VONA, not a rule: QB and TE are deep, so comparable production usually still lasts → their VONA is low → you'll naturally wait on them, no hard cutoff needed. On a genuine VONA tie, still lean RB/WR (FLEX-eligible, thin out with injury). If a QB/TE shows a real top VONA at a needed position, trust it and take him. K is always the final pick.
- Roster construction (HARD GATE): lock startable-quality starters early; chase upside (ceiling, boom, rookies) on the bench late. Once my starters + FLEX are full, only recommend a player who genuinely raises my bench's upside at a position that wins leagues (RB/WR ceiling, an elite TE). NEVER recommend a 2nd QB, or any D/ST or K before my lineup is full, or a redundant backup, just because his VONA or a VALUE tag looks good — a steal I can't start adds nothing to my roster.
- Archetype playbooks: Best-Available = top VONA; Hero-RB = one anchor RB early then hammer WR; Zero-RB = load elite WR/TE early, attack RB value/upside mid-late; Robust-RB = RB-heavy early for the positional edge; Upside = weight ceiling, boom, ascending young roles and rookie capital over safe floors.

READING THE SITUATION (this is your edge over a raw projection)
- ROLE beats last year's box score. A high target/snap share means locked volume even if last season's TDs were flukily low — projections overweight TD variance, role predicts the bounce-back. If a player's VOLS/projection looks low but his tgt%/snap%, tier, and ADP are all strong, the model is probably underrating him — say so and weight the role + market.
- SITUATION drives upside. A featured pass-catcher on a high-powered offense with a good QB has more ceiling than the same player on a weak one — use the team to reason about it.
- Rookies have no role history, so lean on draft capital (rook_pk) and landing spot (team): premium picks into open roles are the high-upside swings.

D/ST & KICKER (streamers — draft LAST)
Never draft a D/ST or K before your starting lineup is full — they're last-2-3-rounds picks with tiny week-to-week edges. Defenses aren't in the main board data; when I ask about D/ST, recommend from the D/ST ranking I give you (Tier 1 are the best; a Tier 1-2 defense late is ideal, and don't reach — they're nearly interchangeable). For kickers, just grab a top-scoring one in the final round.

SCARCITY IS ALREADY IN VONA — don't reason about it separately
Do not talk about "tiers" or scarcity as a separate factor: VONA already IS the scarcity-aware number (value lost by waiting, given who could still be left). A thin position shows up as a high VONA for its best remaining player; a deep one shows up as a low VONA. Just draft the highest VONA at a position I need — that IS getting ahead of a positional run, correctly and automatically.

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
Be concise and skimmable, bold player names, and ground everything in the data I gave you. When you DO steer me to a player the crowd is fading — because he's genuinely the best fit for my roster, not merely because of a tag — say so and give the ONE concrete reason he's underrated (role, situation, a real VONA cliff). I get nervous taking players the internet fades, so justify it with substance. But never manufacture a value case for a worse player: if the better pick is the boring chalk player, tell me to take the chalk. A specific mode instruction follows below."""


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
    open_pos = [pos for pos in ["QB", "RB", "WR", "TE"] if filled[pos] < _STARTER_CAP[pos]]
    open_starters = [f"{pos}×{_STARTER_CAP[pos] - filled[pos]}" if _STARTER_CAP[pos] - filled[pos] > 1
                     else pos for pos in open_pos]
    core_full = not open_starters and flex_filled
    # 1-start positions (QB/TE) already filled: a backup is nearly worthless — NOT draftable.
    filled_single = [pos for pos in ("QB", "TE") if filled[pos] >= _STARTER_CAP[pos]]
    if core_full:
        return ("ROSTER NEEDS — starting lineup COMPLETE. DRAFTABLE now: RB/WR bench upside "
                "(young/ascending, real ceiling) — take the highest-VONA one. NOT draftable (ignore "
                "their VONA): a 2nd QB or 2nd TE (you start one — a backup is nearly worthless), and "
                "D/ST + K until the final 2-3 rounds.")
    depth = [p for p in ("RB", "WR") if p not in open_pos]     # RB/WR always keep bench/FLEX value
    draftable_bits = list(open_starters) + (["RB/WR depth"] if depth else [])
    not_bits = []
    if filled_single:
        not_bits.append("a 2nd " + "/".join(filled_single) + " (you start one — a backup is nearly worthless)")
    not_bits.append("D/ST + K until your lineup is full")
    return (f"ROSTER NEEDS — open starters: {', '.join(open_starters)}. "
            f"DRAFTABLE: {', '.join(draftable_bits)}. NOT draftable (ignore their VONA): "
            f"{'; '.join(not_bits)}. Among draftable, take the HIGHEST VONA. Don't force-fill a "
            "safe/low-VONA open starter (a QB/TE who'll keep) over a higher-VONA RB/WR who WON'T last "
            "— grab the value cliff and fill the safe slot at your next pick; but don't let an open "
            "starter rot if its good options are going (rising VONA / wheel 'gone').")


def _blocked_positions(mine_df):
    """1-start positions (QB/TE) whose starter is already on my roster — a 2nd one is not draftable
    (a backup QB/TE is nearly worthless). Used to null out their VONA so the model can't chase it."""
    if not len(mine_df):
        return set()
    have = set()
    for _, p in mine_df.iterrows():
        have.add(str(p.get("pos_label", "")).rstrip("0123456789") or p.get("position", ""))
    return {pos for pos in ("QB", "TE") if pos in have}


def _horizon(draft_pos):
    """Overall pick number of my NEXT chance after the pick being decided — the point I'd wait until
    if I pass now. Drives both wheel-back and VONA."""
    if not draft_pos:
        return None
    return draft_pos.get("following") if draft_pos.get("my_turn") else draft_pos.get("next_pick")


# Logistic scale for "is he still on the board at my next pick?" — ADP is ~a round noisy, so a player
# `_ADP_SCALE` picks past my next pick is ~73% likely to still be there, ~a round past ~88%. Tunable.
_ADP_SCALE = 7.0


def _survival_prob(adp_rank, horizon):
    """P(player still available at your next pick), softened from ADP with a logistic curve. A player
    drafted right at your next pick is ~50/50; later = more likely there; earlier = less. UD -> 1.0."""
    p = 1.0 / (1.0 + np.exp(-(adp_rank - horizon) / _ADP_SCALE))
    return p.where(adp_rank.notna(), 1.0)


def add_vona(available, horizon):
    """VONA — Value Over Next Available: the value you LOSE by waiting on a player's position.

    VONA = his VOLS minus `best_wait` for his position, where best_wait is the EXPECTED VOLS of the
    best player still on the board at your NEXT pick — each candidate weighted by the probability he's
    the top survivor (he survives AND everyone better at his position is gone). Survival is a softened
    logistic of ADP vs your next pick (see _survival_prob), so there's no hard cutoff. This works out
    to roughly VONA ≈ P(he's gone) × (his VOLS − the next-best you'd expect): the drop-off behind him,
    weighted by how likely you actually lose him. Floored at replacement (0), cross-position
    comparable — the live, personalized version of a "tier drop" that replaced the stale ECR tiers.
    Shared by the advisor context and the board column so they always agree.
    """
    av = available.copy()
    if not horizon or "vols" not in av.columns or "position" not in av.columns:
        av["vona"] = av.get("vols", 0.0)
        return av
    av["_p"] = _survival_prob(av["adp_rank"], horizon)
    best_wait = {}
    for pos, g in av.groupby("position"):
        g = g.sort_values("vols", ascending=False)     # NaN VOLS sort last -> treated as replacement
        gone_above, exp_best = 1.0, 0.0                 # gone_above = P(everyone better is gone)
        for v, pi in zip(g["vols"], g["_p"]):
            vv = 0.0 if pd.isna(v) else max(float(v), 0.0)   # below-replacement / no-VOLS -> 0
            pi = float(pi)
            exp_best += vv * pi * gone_above            # v_i · P(i survives) · P(all better gone)
            gone_above *= (1.0 - pi)
        best_wait[pos] = exp_best
    av["vona"] = av["vols"] - av["position"].map(best_wait).fillna(0.0)
    return av.drop(columns="_p")


def _wheel_label(adp, horizon):
    """gone / risky / safe — will he last to your next pick? (per-player read; VONA is the decision)."""
    if pd.isna(adp):
        return "safe"                     # UD / no ADP -> very likely still there later
    if adp <= horizon:
        return "gone"                     # typically drafted before your next pick
    if adp >= horizon + 12:
        return "safe"                     # ~a full round of cushion
    return "risky"                        # within a round — could go either way


def build_context(available, mine_df, scarcity, draft_pos=None, top_n=35):
    """Compact text snapshot of the live board for the current turn."""
    horizon = _horizon(draft_pos)
    if "vona" not in available.columns:      # normally precomputed in draft.py; compute if standalone
        available = add_vona(available, horizon)
    cols = ["full_name", "pos_label", "team", "team_implied_total", "vols", "vona", "adp_rank",
            "market", "risk_tier", "target_share_2025", "snap_share_2025", "age", "is_rookie",
            "draft_pick", "floor", "ceiling", "p_startable", "p_bust", "xppg", "regression",
            "switched_team"]
    cols = [c for c in cols if c in available.columns]   # tolerate an older board
    top = available.sort_values("rank_composite").head(top_n)[cols].copy()
    # Wheel-back computed in PYTHON so the model never does the ADP-vs-next-pick arithmetic (LLMs
    # flip the direction). horizon = my next real chance to pick; "gone" = his average draft spot is
    # at/before it, "safe" = a full round of cushion past it, "risky" = within a round (toss-up).
    if horizon:
        top["wheel"] = top["adp_rank"].map(lambda a: _wheel_label(a, horizon))
    top["market"] = top.get("market", "").fillna("")
    top["team"] = top.get("team", "FA").fillna("FA")
    # NaN-safe formatting: some available players have no ADP / role / outcome data
    to_int = lambda s: s.map(lambda x: "" if pd.isna(x) else str(int(round(x))))
    to_1dp = lambda s: s.map(lambda x: "" if pd.isna(x) else f"{x:.1f}")
    top["adp_rank"] = top["adp_rank"].map(lambda x: "UD" if pd.isna(x) else f"{x:.1f}")
    for c in ["vols", "vona", "floor", "ceiling", "age"]:
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
                              "vona": "VONA", "risk_tier": "risk", "regression": "regr",
                              "p_startable": "P_start%", "p_bust": "bust%"})
    if "switched_team" in top:   # xPPG/regr describe the OLD team for a player who moved
        _sw = top["switched_team"].astype(str).str.lower().isin(["true", "1"])
        top.loc[_sw, "regr"] = "new-tm"
        top = top.drop(columns=["switched_team"])
    # Enforce the roster gate in the DATA: null the VONA of filled 1-start positions (QB/TE) so a
    # worthless backup can't show up as the "highest VONA" and get chased (a prose rule alone got ignored).
    blocked = _blocked_positions(mine_df)
    if blocked and "VONA" in top.columns and "pos" in top.columns:
        base = top["pos"].str.replace(r"\d+$", "", regex=True)
        top.loc[base.isin(blocked), "VONA"] = "n/a"
    # THE ANSWER, computed in Python: the draftable players (blocked 1-start positions removed) ranked
    # by VONA, so the model can't misread the table or bump a "need" over the real value. Take #1
    # unless a clear risk/upside reason moves you to #2-3.
    picks_line = ""
    if "vona" in available.columns:
        skip = set(blocked) | {"K", "DEF", "DST", "D/ST"}   # streamers (K/D-ST) are a final-round call
        ok = available[~available["position"].isin(skip)].sort_values("vona", ascending=False).head(6)
        if len(ok):
            def _pk(r):
                w = f", {_wheel_label(r.adp_rank, horizon)}" if horizon else ""
                return f"{r.full_name} ({r.pos_label}, VONA {r.vona:.0f}{w})"
            picks_line = ("TOP PICKS NOW — your best DRAFTABLE options ranked by VONA (a filled 1-start "
                          "QB/TE is already excluded). THIS IS THE ANSWER: recommend #1 unless a clear "
                          "risk/upside reason bumps you to #2 or #3; do NOT bump a lower one up just "
                          "because it fills an open starter. "
                          + " | ".join(f"{i+1}. {_pk(r)}" for i, r in enumerate(ok.itertuples())) + "\n")
    order = ["player", "pos", "team", "vegas", "VONA", "vols", "ADP", "wheel", "tgt%", "snap%", "age",
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
    scar = ", ".join(f"{p} {scarcity[p]} startable" for p in scarcity)

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
        f"{picks_line}"
        f"Startable pool left by position (context only — VONA already prices scarcity): {scar}\n\n"
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
