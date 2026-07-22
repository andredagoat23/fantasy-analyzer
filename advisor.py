"""Claude-powered draft advisor for the live snake draft (v1.1).

Pure Python — no Streamlit in here. app.py owns the UI + the API key (via
st.secrets) and passes a client + messages down. This keeps the LLM layer
testable and keeps the app free of modeling.
"""

import os

import anthropic
import numpy as np
import pandas as pd

from utils import normalize_name

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

# Cohort priors (cohort_data.csv, built by cohort_priors.py): each player's 15 most-similar
# historical player-seasons and how that archetype performed vs its price. Loaded once; the
# advisor cites them as explainable comps. Missing file -> feature silently off.
_COHORTS = None


def _cohorts():
    global _COHORTS
    if _COHORTS is None:
        try:
            _df = pd.read_csv("cohort_data.csv")
            _COHORTS = {r["nn"]: dict(r) for _, r in _df.iterrows()}
        except Exception:
            _COHORTS = {}
    return _COHORTS


# Role priors (role_data.csv, built by role_priors.py): each board player's PREVIOUS-season workload
# share (carries for RB/QB, targets for WR/TE), ppg, games, NFL draft capital, and the market's
# positional ADP rank. Powers the L31 late-round reads. Missing file -> features silently off.
_ROLES = None
_ROLES_MTIME = None


def _roles():
    """role_data.csv keyed by nn, reloaded when the file changes (the app mtime-busts the board the
    same way — a stale cache after a regen would silently serve last month's roles). Missing file ->
    BUY profiles + price bands go dark; the board-column fades (age/moved/rookie) still fire."""
    global _ROLES, _ROLES_MTIME
    try:
        mt = os.path.getmtime("role_data.csv")
    except OSError:
        _ROLES, _ROLES_MTIME = {}, None
        return _ROLES
    if _ROLES is None or mt != _ROLES_MTIME:
        try:
            _r = pd.read_csv("role_data.csv")
            _ROLES = {r["nn"]: dict(r) for _, r in _r.iterrows()}
            _ROLES_MTIME = mt
        except Exception:
            _ROLES = {}
    return _ROLES


_PC = None


def _playcallers():
    global _PC
    if _PC is None:
        try:
            _p = pd.read_csv("data/playcallers_2026.csv")
            _PC = {r["team"]: dict(r) for _, r in _p.iterrows()}
        except Exception:
            _PC = {}
    return _PC


_SOS = None


def _sos():
    global _SOS
    if _SOS is None:
        try:
            _s = pd.read_csv("sos_data.csv")
            _SOS = {(r["team"], r["position"]): (int(r["sos_rank"]), r["sos_delta"]) for _, r in _s.iterrows()}
        except Exception:
            _SOS = {}
    return _SOS


SYSTEM = """You are an elite fantasy football draft strategist advising me LIVE during my draft. Give sharp, fast, decision-ready advice — I have about 90 seconds on the clock.

MY LEAGUE
- 12-team snake draft, custom-scoring PPR.
- Starters: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 D/ST, 1 K. Plus a bench.

THE DATA I GIVE YOU (per available player)
- VOLS = value over last starter: projected season points above the last startable player at his position. The season-long value BACKBONE (how good he is all year).
- VONA = Value Over Next Available — his VOLS minus the best same-position player ADP says could still be on the board at your NEXT pick, floored at replacement. THIS is the "who do I take NOW" number: the value you'd LOSE by waiting on his position. It already bakes in scarcity + who-could-still-be-left, so it's the live, personalized version of a tier drop. High VONA = a real cliff behind him (grab now); VONA near 0 = comparable value will still be there (you can wait). It already accounts for WHEN the next guys at his position go: if a comparable player will still be around in a few rounds his VONA is low (so you can take other guys now and grab this position later); if it's now-or-never his VONA is high. Precomputed — use it, never recompute. **VONA "n/a" = a position I CANNOT use (a filled 1-start QB/TE — a backup is worthless); never recommend an "n/a" player no matter his VOLS.**
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
- COHORT HISTORY (given for the TOP PICKS shortlist): the player's 15 most-similar historical player-seasons (same position, experience, draft capital, recent production, preseason price, age, mover status — from 2019-2025) and how that archetype ACTUALLY performed vs its draft price: boom (>=1.3x price) / bust (<=0.7x) rates, median multiplier, top-5 finish rate, plus REAL comp names with their outcomes. Use it to (a) explain picks with names ("profile like Jonathan Taylor '21"), (b) break close calls when archetype history clearly favors one profile, (c) flag when an archetype's tail differs from what the player's own numbers suggest. NEVER let cohort rates override the calibrated floor/ceiling/bust%/P_start% — 15 seasons of lookalikes is a PRIOR and a story; the MC numbers are calibration. When they disagree, trust the MC numbers and use the cohort to explain the shape.
- team = his NFL team. vegas = his team's Vegas season implied points/game (league avg ~22.7). This is the sharpest read on the scoring environment — a featured player on a high-vegas offense (25+) has real upside; a good role on a low-vegas offense (<20) is capped. Weight it heavily for ceiling/situation, and pair it with role: high tgt%/snap% AND high vegas = league-winning opportunity.
- PLAYCALLER CHANGES (team-level line in the live state): which teams have a NEW offensive playcaller for 2026 (the person actually calling plays — sometimes HC, sometimes OC; this matters more for fantasy than the HC title) and which callers are FIRST-TIMERS. Use it as scheme-uncertainty context: a new playcaller can change a player's usage in ways last year's stats can't see (tgt%/snap% describe the OLD scheme even for non-movers) — say so when it's relevant to a pick, especially for first-time callers (widest uncertainty) or when a strategy leans on a player whose role depends on the old scheme. VALIDATED HISTORY (2020-25, don't override it): an OC-only playcaller change (same HC) is price-NEUTRAL — stayers under it hit their projections at baseline rates (med 1.00x) — so never fade OR boost a player just because of a new OC; the priced-in coaching edge exists only for FULL regime changes (new HC), and the calibrated numbers already include it. This line is for USAGE reasoning, not price adjustments.
- sos = his team's 2026 POSITIONAL schedule rank (1 = EASIEST: his opponents allowed the most fantasy points to his position last season; 32 = hardest). A mild, tie-break-level signal — schedules shuffle and defenses change. Flag extremes (top-5 easiest is a small plus, bottom-5 a small minus); never let it outrank role, value, or vegas.
- role = his depth-chart slot at his position ON HIS CURRENT TEAM, ranked by 2026 projection (e.g. "WR1" = his team's top WR, "WR2" = behind an alpha, "RB1" = lead back). This is the CURRENT-team role — pair it with vegas (offense strength) to read situation: a team's WR1 on a high-vegas offense has real target security; a WR2/WR3 sits behind a bigger target earner and a pass-catching RB1 also eats targets. Weight this heavily for how safe/repeatable his volume is.
- tgt% / snap% = target share / snap share, but from LAST SEASON. For a player who CHANGED TEAMS (regr shows "new-tm"), these are his OLD team's numbers — DISCOUNT them and trust `role` + the 2026 projection for his new spot instead (a WR1 move looks low if his old role was a WR2). High on his current team = locked featured role; low or blank = committee, unproven, or rookie.
- age = age this season. rook_pk = for rookies, their NFL draft pick (lower = more pedigree/opportunity); blank for veterans.

YOUR JOB
Recommend the pick that best executes MY plan given my roster and the board. My stated strategy is not a tiebreaker — it is the PLAN I chose for my draft, and following it is what makes this MY draft instead of a generic value sheet. Decide in THIS ORDER, and never let a later factor override an earlier one:
0) MY STRATEGY IS THE PLAN (when the setup gives one) — your default recommendation is the pick that ADVANCES it, and every pick answer states how it does (or explicitly flags a deviation — see the deviation protocol below). An ABSOLUTE instruction ("no X before round N", "only Y early", "no matter what") is BINDING: recommend the best pick that obeys it, full stop — no deviation option, no reinterpreting it as "executable later"; the deviation protocol exists for soft preferences only. Python HARD GATES still outrank everything (VONA "n/a" filled 1-start positions, BENCH-ONLY, OVER-STACKED — a strategy can't make a worthless backup useful), but SOFT demotions (PUNT-ABLE, FLEX-only ordering) yield to an explicit strategy instruction — if I said "elite QB early," recommend the QB even though the punt read would wait.
1) ROSTER NEED filters what's DRAFTABLE — a position that helps my roster: an open starter/FLEX, or RB/WR bench depth (RB and WR ALWAYS keep bench/FLEX value). QB and TE are 1-START positions — once mine is filled, a 2nd one is NOT draftable no matter how high its VONA (a backup QB/TE is nearly worthless — I start one and they're streamable). Never draft a filled 1-start position, or a K/D-ST before my lineup is full. Roster need does NOT force me to fill an open starter this instant: a still-open slot whose good options will KEEP (wheel "safe", low VONA) can wait while I grab a bigger VONA cliff at a draftable RB/WR — I'll fill the safe slot next pick for the same value (but don't let it rot if its options are going).
2) VALUE — the **TOP PICKS NOW** line ranks your draftable options by VONA. VONA gives you the SHORTLIST, not the final answer: the ***starred** picks are within a few VONA of each other = a genuine TIE, so among them pick the BEST PLAYER by age, risk/reward, offense (vegas), and role (tgt%/snap%) — NOT the tiny VONA gap. Only when one option's VONA clearly stands alone above the rest (nothing else starred) does VONA alone decide. NEVER bump a lower one up just to fill an open starter: a safe open slot WAITS (you fill it next pick for the same value); a filled 1-start QB/TE is already excluded (VONA "n/a"). WITHIN a position, take the best available (highest VOLS).
3) UPSIDE & RISK break the close calls — when two candidates' VONA is genuinely close, pick the one that fits my RISK APPETITE: upside build → lean ceiling/boom, ascending young roles, high vegas + role; safe build → lean floor, durable, low bust. Use role / situation (vegas) / xPPG-regression as tiebreakers; `market` is a pricing tiebreaker only (can I wait on him?), never a talent signal. Say which factors drove the call. RISK ACCUMULATES ACROSS MY ROSTER: bust risks multiply — if the ROSTER RISK line says one of my rooms is already bust-heavy, break ties toward the STABLE option at that position (TOP PICKS already demotes the risky ones there — trust it). High bust% is only ever acceptable when the upside PAYS for it (big ceiling or real top-3 odds — a compensated boom/bust swing); a high-bust player with a mediocre ceiling is a coin-flip with no jackpot, and stacking several at one position is how a season quietly dies.
Only recommend players on the "available" list — never invent players. **NEVER state a player's NFL team, role, or stats from your own memory — rosters change every year and your training is stale, so you WILL get teams wrong (e.g. saying a player is on his old team). Use ONLY the `team`/`role`/numbers in the data I give you, verbatim.** If a player is NOT in my data, say you don't have him, do NOT guess his team, and do NOT recommend him — he's either an unsigned free agent or a player my board has faded (over-projected vs expert consensus); tell me that and move on.

DRAFT STRATEGY TOOLKIT (apply whichever fits my stated strategy + the board)
- Draft the value CLIFF, not the rank: VONA already tells you where waiting costs the most — take the high-VONA player before the drop; don't reach across a position for a tiny ADP edge when VONA is flat.
- Positional value is handled BY VONA, not a rule: QB and TE are deep, so comparable production usually still lasts → their VONA is low → you'll naturally wait on them, no hard cutoff needed. On a genuine VONA tie, still lean RB/WR (FLEX-eligible, thin out with injury). If a QB/TE shows a real top VONA at a needed position, trust it and take him. K is always the final pick.
- PUNT READ for unfilled QB/TE (precomputed — trust it): VONA only looks one pick ahead, so at a snake TURN it can over-rate an elite QB/TE. For each unfilled 1-start slot I tell you if it's DEEP (a startable one lasts to a late round → the slot is PUNT-ABLE, and I've already demoted it below the scarce RB/WR in TOP PICKS — take the RB/WR and fill the slot late) or a CLIFF (no startable one lasts → grab the elite now if you need it). A "PUNT-ABLE" tag in TOP PICKS means do NOT reach for that QB/TE now even if its VONA looks high — its edge is recoverable late; the scarce RB/WR is the pick. A DEFER tag means the elite one at that slot lasts to MY VERY NEXT pick — take the scarce RB/WR now and grab him next pick (L33).
- TE SHAPE (backtested tie-breaker, advisory — the punt read + VONA still decide the trigger): the position is TOP-HEAVY, so time the TE. If I take one, either pay up for the ELITE tier (top ~2, ~R2) or WAIT for the ~R6 value pocket (a mid-tier startable TE lands there cheap). The R4-5 mid-TEs are the DEAD ZONE — worst value per pick (they cost a good RB/WR yet barely beat the R6 TE). So don't reach for a mid-TE in R4-5: pay up for the elite tier or wait for the R6 pocket.
- Roster construction (HARD GATE): lock startable-quality starters early; chase upside (ceiling, boom, rookies) on the bench late. Once my starters + FLEX are full, only recommend a player who genuinely raises my bench's upside at a position that wins leagues (RB/WR ceiling, an elite TE). NEVER recommend a 2nd QB, or any D/ST or K before my lineup is full, or a redundant backup, just because his VONA or a VALUE tag looks good — a steal I can't start adds nothing to my roster.
- BENCH-ONLY positions (fill starters first): if I already have enough at a FLEX position to start all I'd play there (3 RB = RB1+RB2+FLEX, 3 WR, 2 TE), a FURTHER one is BENCH-ONLY — it can't crack my lineup. While a starter slot elsewhere is open (e.g. I have 3 RB and 0 WR), NEVER take that bench-only player over a player who fills the open starter, no matter how high his VONA. I mark these "BENCH-ONLY" in ROSTER NEEDS + TOP PICKS and demote them below the fillers — trust it: draft the open-starter filler.
- DEDICATED starters before the FLEX: fill my fixed positional slots (QB/RB/RB/WR/WR/TE) before spending a pick that only upgrades the FLEX — the FLEX is a week-to-week / matchup slot I can stream, so a piece that ONLY improves it (a 3rd RB/WR when my dedicated RB/WR slots are full) is worth less than filling a real positional need. I tag these "FLEX-only" and demote them below the dedicated-need fillers UNLESS one is WAY better in VONA. Take the dedicated filler unless the FLEX-only piece is a clear value cliff.
- Archetype playbooks: Best-Available = top VONA; Hero-RB = one anchor RB early then hammer WR; Zero-RB = load elite WR/TE early, attack RB value/upside mid-late; Robust-RB = RB-heavy early for the positional edge; Upside = weight ceiling, boom, ascending young roles and rookie capital over safe floors.
- LATE ROUNDS (R11+) — the DART READ is the validated playbook (backtested 2014-25, held out-of-sample on 2022-25; its BUY/FADE profiles are already boosted/demoted in TOP PICKS — trust the order): late VONA sorts sub-replacement noise, so profiles beat projections there. BUYS: post-hype target-share WR (20%+ of his team's WR-room targets last yr — the single strongest late signal), GO-screen committee RB handcuffs (prior role, good offense, real price), a proven pocket vet QB who KEPT his team on a good offense (only while my QB is open), a young high-NFL-capital TE dart in the final rounds (only while TE is open/hedging). FADES (do not talk me into these): the injury-discount vet (formerly-good + missed time — 0 league-winners in 47 cases), WRs 29+, late QBs on NEW teams, rookies without top-100 NFL capital, and the deep end of every position's price band. HANDCUFF READ: only GO-screened backups behind MY starting RBs (the screen = prior role + offense + real price; non-GO handcuffs hit at roughly half the GO rate); NEVER a TE handcuff. Frame ALL of these as startable-floor plays, never "league-winning" — and be honest when asked: about a third of each season's late-round league-winners fit no draftable profile, and the sharpest handcuff signal is IN-SEASON (weeks 3-4 usage; budget FAAB), not at the draft.

HOW TO EXECUTE MY STATED STRATEGY (when the setup gives you one)
The strategy is MY plan — your job is to run it proactively, not merely avoid violating it:
1. **Steer toward it, actively.** If it names positions, rounds, archetypes, risk levels, or specific players, hunt for the picks that advance it: "solid players early" → prefer high-floor/low-bust among the starred ties; "Zero-RB" → build my WR/TE core and time the RB value attack; "swing for upside" → weight ceiling/boom over modest VONA edges; a named player I like → track when he's reachable and TELL me the round to strike. Every PICK answer includes a short **Plan:** note — how this pick advances my strategy, in a few words.
2. **A RISK-FLAVORED strategy re-weights value, it doesn't just break ties.** High-risk/high-reward → VONA matters LESS: a high-ceiling boom player can beat a modestly-higher-VONA safe one (ascending young roles, high vegas + role, rookie capital). Safe/floor → the opposite (down-weight boom, prefer durable floor + low bust). Say which factor drove it.
3. **Deviation protocol — leaving the plan is the EXCEPTION and must be earned.** Deviate only when following the plan has a LARGE, named cost: a genuine value cliff (roughly 12+ VONA left on the table), a PUNT-READ CLIFF at an unfilled slot, or a Python hard gate. When that happens, show BOTH with the PLAN option FIRST and let me choose:
   - "**Sticking to your plan: [player]** — the best pick that follows your [strategy]."
   - "**Worth breaking it: [player]** — [the one concrete reason], gains ~N VONA."
   Small edges NEVER justify deviating: if the value gap is under ~12 VONA, the plan pick IS the pick — don't even frame it as a sacrifice.

READING THE SITUATION (this is your edge over a raw projection)
- ROLE beats last year's box score. Read `role` (depth-chart slot) WITH vegas: a team's WR1/RB1 on a high-vegas offense has secure, repeatable volume; a WR2/WR3 competes with the alpha AND a pass-catching RB1 for the same targets, so his ceiling is capped even if the offense is good. On two close players, prefer the better ROLE + situation — the TOP PICKS ranking ALREADY bumps a team's WR1/RB1 above a comparable WR2/WR3, but ONLY when the offense actually throws (decent vegas OR pass volume); a clear WR1 on a bad, run-heavy team gets NO bump (few valuable targets to lock up), so his ranking rests on his value alone. Trust that order (a lower-role player sits on top only when his value edge is big enough to overcome it). But `tgt%/snap%` are last year's — for a mover (regr "new-tm") they describe the OLD team, so a player who upgraded roles (e.g. a former WR2 who's now his new team's WR1) is UNDERRATED by those stale stats: lean on `role` + the projection, and say so.
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
PICK_MODE = """MODE: PICK — I just hit "Recommend my pick" and I'm ON THE CLOCK. If a STREAMER ALERT line is present, IT WINS over everything below: the pick is the K (or D/ST) it names — one bold name + "last-rounds K/D-ST" as the reason, done. Give me the single pick that EXECUTES MY STRATEGY right now: one **bold name** + at most one short sentence why, then "Plan: [how it advances my strategy, a few words]" (if no strategy is set, use need/value instead), then one **bold** fallback in a few words. Under ~55 words total. No preamble, no long options list, no questions back. COMMIT — do NOT think out loud, second-guess, or write "wait"/"actually"/"hmm". EXCEPTION — only when deviating clears the deviation protocol (a 12+ VONA cliff or a hard gate), replace the fallback with the two labeled options PLAN-FIRST ("**Sticking to your plan: Y**" then "**Worth breaking it: X (+N VONA)**"), still under ~60 words, so I can choose on the clock."""

CHAT_MODE = """MODE: CONVERSATION — I'm talking things through, NOT asking for a pick. Discuss, compare, react, answer my question. Do NOT declare a single "pick" or tell me who to draft unless I literally ask "who should I take / who do I pick." Just have the conversation with me. Keep it short."""


_STARTER_CAP = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1}
_FLEX_OK = {"RB", "WR", "TE"}


def _roster_needs(mine_df, my_dst=None, saturated=None, flex_only=None):
    """Plain-English roster status covering ALL 9 starters — incl. K (on the board, so it's in
    mine_df) and D/ST (passed in as `my_dst`, because defenses aren't on the board and never enter
    mine_df). So the advisor never miscounts the roster (it used to ignore K + D/ST entirely and call
    a half-empty lineup 'complete')."""
    filled = {k: 0 for k in _STARTER_CAP}
    flex_filled = False
    for _, p in mine_df.iterrows():
        pos = str(p.get("pos_label", "")).rstrip("0123456789") or p.get("position", "")
        if pos in _STARTER_CAP and filled[pos] < _STARTER_CAP[pos]:
            filled[pos] += 1
        elif pos in _FLEX_OK and not flex_filled:
            flex_filled = True
    open_pos = [pos for pos in ["QB", "RB", "WR", "TE"] if filled[pos] < _STARTER_CAP[pos]]
    open_skill = [f"{pos}×{_STARTER_CAP[pos] - filled[pos]}" if _STARTER_CAP[pos] - filled[pos] > 1
                  else pos for pos in open_pos] + ([] if flex_filled else ["FLEX"])
    streamers = [s for s, need in (("D/ST", not my_dst), ("K", filled["K"] == 0)) if need]
    have = [x for x in (("D/ST" if my_dst else None), ("K" if filled["K"] else None)) if x]
    have_note = (" You already have your " + " + ".join(have) + ".") if have else ""
    # 1-start positions (QB/TE) already filled: a backup is worthless — NOT draftable.
    no2 = [pos for pos in ("QB", "TE") if filled[pos] >= _STARTER_CAP[pos]]
    no2_note = (" NOT draftable: a 2nd " + "/".join(no2) + " (you start one — a backup is worthless).") if no2 else ""

    if not open_skill:   # every skill starter + FLEX is filled
        head = "ROSTER NEEDS — skill starters (QB/RB/RB/WR/WR/TE/FLEX) all filled." + have_note
        if streamers:
            return (head + " Still need your " + " and ".join(streamers) + " — grab them in the FINAL "
                    "2-3 rounds, NOT now while bench-upside RB/WR remain. Meanwhile draft the "
                    "highest-VONA RB/WR BENCH UPSIDE." + no2_note)
        return head + " Full lineup DONE — draft the highest-VONA RB/WR BENCH UPSIDE only." + no2_note

    saturated = saturated or set()
    flex_only = flex_only or set()
    depth = [p for p in ("RB", "WR") if p not in open_pos and p not in saturated and p not in flex_only]
    depth_label = ("/".join(depth) + " depth") if depth else ""
    draftable = ", ".join(open_skill + ([depth_label] if depth_label else []))
    stream_note = (" (still to grab in the final rounds: " + " + ".join(streamers) + " — WAIT on them)") if streamers else ""
    sat_note = (" SATURATED (bench-only NOW — you can already start all you'll play there; do NOT draft "
                "over an open starter): " + "/".join(sorted(saturated)) + ".") if saturated else ""
    flex_note = (" FLEX-only (a further one only upgrades the week-to-week FLEX; fill your dedicated "
                 "QB/RB/WR/TE starters first unless it's WAY better): " + "/".join(sorted(flex_only)) + ".") if flex_only else ""
    return (f"ROSTER NEEDS — open starters: {', '.join(open_skill)}.{have_note} DRAFTABLE now: "
            f"{draftable}{stream_note}.{no2_note}{sat_note}{flex_note} Among draftable, fill DEDICATED "
            "starters before the FLEX; take the HIGHEST VONA among the dedicated fillers, and don't "
            "force-fill a safe/low-VONA open starter over a higher-VONA dedicated RB/WR who WON'T last "
            "(grab the cliff, fill the safe slot next pick) — but don't let an open starter rot if its "
            "options are going (wheel 'gone').")


def _blocked_positions(mine_df):
    """1-start positions (QB/TE) whose starter is already on my roster — a 2nd one is not draftable
    (a backup QB/TE is nearly worthless). Used to null out their VONA so the model can't chase it."""
    if not len(mine_df):
        return set()
    have = set()
    for _, p in mine_df.iterrows():
        have.add(str(p.get("pos_label", "")).rstrip("0123456789") or p.get("position", ""))
    return {pos for pos in ("QB", "TE") if pos in have}


# How much higher a FLEX-only option's VONA must be than the best DEDICATED-need filler to be worth
# taking over the dedicated slot. FLEX is week-to-week / streamable, so fill your fixed positional
# starters first — only jump to a FLEX piece when it's WAY better (a real value cliff). Tunable.
_FLEX_MARGIN = 15.0

# ROLE PREFERENCE: a team's clear WR1/RB1 has locked targets; a WR2/WR3 competes with the alpha + a
# pass-catching RB1, so his volume is capped. In TOP PICKS a player's rank is nudged by his `role_lead`
# (how much his projection leads/trails the next player in his position room) × _ROLE_LEAD_K, capped at
# ±_ROLE_CAP. So a CLEAR alpha (DJ Moore leads his WR2 by 25) beats a comparable WR2, a coin-flip WR1
# (Burden +2 over Odunze) gets ~nothing, and a much-higher-VONA WR2 still wins (the Metchie guard).
_ROLE_LEAD_K = 0.5    # VONA per point of role_lead
_ROLE_CAP = 10.0      # max ± nudge, so a clear alpha flips a moderate VONA gap but never a big one


def _role_bonus_series(df):
    """Per-player VONA nudge for the TOP PICKS ranking from role CLARITY (role_lead), RB/WR/TE only;
    QB/K neutral. Bounded + gap-scaled, so it reorders comparable players by real role security without
    amplifying a projection-tie WR1 label or resurfacing a low-value one. GATED by `role_env_ok`: a
    WR1's locked role only matters on an offense that actually throws valuable targets (above-median
    vegas OR pass volume) — on a bad, run-heavy team the role nudge is neutral."""
    if "role_lead" not in df.columns:
        return pd.Series(0.0, index=df.index)
    skill = df["position"].isin(("RB", "WR", "TE"))
    env = df["role_env_ok"].fillna(True).astype(bool) if "role_env_ok" in df.columns else True
    nudge = (df["role_lead"].astype("float") * _ROLE_LEAD_K).clip(-_ROLE_CAP, _ROLE_CAP)
    return nudge.where(skill & env, 0.0).fillna(0.0)


_BENCH_BALANCE_GAP = 2   # keep RB and WR depth within this many of each other when stacking the bench


def _bench_overstacked(mine_df):
    """Keep RB/WR depth roughly even: a position you already have this many MORE of than the other is
    over-stacked, so it's demoted below the thinner one when adding depth (had 4 RB / 2 WR → don't add
    a 5th RB, take a WR). Returns the over-stacked position(s). Bounded — a much-higher-value player at
    the stacked position can still be taken (it only sorts within the demoted tier)."""
    if not len(mine_df):
        return set()
    cnt = {"RB": 0, "WR": 0}
    for _, p in mine_df.iterrows():
        pos = str(p.get("pos_label", "")).rstrip("0123456789") or p.get("position", "")
        if pos in cnt:
            cnt[pos] += 1
    over = set()
    if cnt["RB"] - cnt["WR"] >= _BENCH_BALANCE_GAP:
        over.add("RB")
    if cnt["WR"] - cnt["RB"] >= _BENCH_BALANCE_GAP:
        over.add("WR")
    return over


# --- roster risk accumulation (lesson L23) ---
# The MC layer prices each player's bust risk, but nothing stopped a roster from STACKING
# uncompensated risk (five 40%+-bust RBs with mediocre ceilings = coin-flip odds that two bust).
# Risk with a real jackpot (big ceiling / elite odds) is a legitimate swing; risk without one isn't.
_HIGH_BUST = 0.40      # a roster piece this bust-prone counts toward the position's risk load
_RISK_STACK_N = 2      # this many high-bust players at a position = the room is risk-stacked
_RISK_PENALTY = 6.0    # VONA-scale demotion for adding MORE uncompensated risk to a stacked room


def _is_compensated(p_bust, ceiling, total_points, p_elite):
    """High risk is OK if the upside pays for it: big ceiling ratio or real elite odds."""
    ratio = (ceiling / total_points) if (pd.notna(ceiling) and pd.notna(total_points)
                                         and total_points) else np.nan
    return (pd.notna(ratio) and ratio >= 1.45) or (pd.notna(p_elite) and p_elite >= 0.10)


def _roster_risk(mine_df):
    """Per FLEX position: how many of MY current players are high-bust, and the room's avg bust.
    Returns {pos: (n_high, avg_bust)} for positions where I have 2+ players with bust data."""
    out = {}
    if not len(mine_df) or "p_bust" not in mine_df.columns:
        return out
    base = (mine_df["pos_label"].astype(str).str.replace(r"\d+$", "", regex=True)
            if "pos_label" in mine_df.columns else mine_df.get("position", pd.Series(dtype=str)))
    for pos in ("RB", "WR", "TE"):
        room = mine_df[(base == pos) & mine_df["p_bust"].notna()]
        if len(room) >= 2:
            out[pos] = (int((room["p_bust"] >= _HIGH_BUST).sum()), float(room["p_bust"].mean()))
    return out


_HEDGE_BUST = 0.35    # a FILLED 1-start starter (QB/TE) this bust-prone — or Boom/Bust / Injury Risk —
#                       is risky enough that hedging it is a legitimate call (see _hedge_read).


def _hedge_read(mine_df, available, dedicated_open):
    """A FILLED 1-start slot (QB/TE) is normally BLOCKED (a backup is nearly worthless), but that block
    is risk-BLIND: it stays silent even when my only QB/TE is a boom/bust starter and my plan says
    "hedge risky positions" (L25/L27). This surfaces the hedge-vs-stream CALL — never a value pick (the
    backup's VONA stays blocked). Fires only once my dedicated starters are set (a hedge is a bench
    decision, not a reason to skip a starter). Returns a note string, or "" when there's nothing to raise.
    """
    if len(dedicated_open) or not len(mine_df) or "p_bust" not in mine_df.columns:
        return ""                                  # still filling fixed starters — not hedge time yet
    base = (mine_df["pos_label"].astype(str).str.replace(r"\d+$", "", regex=True)
            if "pos_label" in mine_df.columns else mine_df.get("position", pd.Series(dtype=str)))
    bits = []
    for pos in ("QB", "TE"):
        room = mine_df[base == pos]
        if not len(room):
            continue                               # position not filled -> the PUNT READ owns it, not this
        starter = room.sort_values("total_points", ascending=False).iloc[0]
        bust = float(starter["p_bust"]) if pd.notna(starter.get("p_bust")) else 0.0
        tier = str(starter.get("risk_tier", ""))
        if tier not in ("Boom/Bust", "Injury Risk") and bust < _HEDGE_BUST:
            continue                               # a safe starter (e.g. a stud QB) needs no hedge
        pool = (available[available["position"] == pos] if "position" in available.columns
                else available[available["pos_label"].astype(str).str.startswith(pos)])
        pool = pool[pool["p_bust"].notna() & (pool["total_points"] > 0)]
        if len(pool):
            h = pool.sort_values(["p_bust", "floor"], ascending=[True, False]).iloc[0]
            opt = f"safest hedge available: {h['full_name']} (bust {h['p_bust']:.0%}, floor {h['floor']:.0f})"
        else:
            opt = "no safe-floor hedge left — plan to stream"
        bits.append(f"your only {pos} ({starter['full_name']}) is {tier or 'high-bust'} at "
                    f"{bust:.0%} bust — {opt}")
    if not bits:
        return ""
    return ("HEDGE READ (my plan hedges risky positions; a backup 1-start is INSURANCE, not a value "
            "pick — its VONA stays blocked): " + " | ".join(bits)
            + ". The alternative to each is to STREAM the position off waivers and spend the pick on "
            "upside instead — present the tradeoff and let me choose.\n")


def _starters(mine_df):
    """The full_names actually in my STARTING lineup (1QB/2RB/2WR/1TE + 1 FLEX of RB/WR/TE), filled
    greedily by projection — the same fill the roster panel uses. Everyone else is BENCH."""
    if not len(mine_df):
        return set()
    cap, filled, flex = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}, {"QB": [], "RB": [], "WR": [], "TE": []}, []
    for _, p in mine_df.sort_values("total_points", ascending=False).iterrows():
        pos = str(p.get("pos_label", "")).rstrip("0123456789") or p.get("position", "")
        if pos in cap and len(filled[pos]) < cap[pos]:
            filled[pos].append(p["full_name"])
        elif pos in ("RB", "WR", "TE") and not flex:
            flex.append(p["full_name"])
    return {n for v in filled.values() for n in v} | set(flex)


def _go_score(nn, pos_adp_rank, implied):
    """The RB handcuff GO screen (L31/B1, validated out-of-sample: GO booms 42% vs 18% rest, and it
    survives the implied-leak re-basing). +1 each for: prev-season carry share >= .30 (the committee
    signal — HALF the in-season edge survives to draft day through it), preseason team implied >= 23,
    and a real market price (<= RB50). NaN scores 0. GO = score >= 2."""
    r = _roles().get(nn, {})
    s = 0
    if pd.notna(r.get("share_2025")) and r.get("share_2025", 0) >= 0.30:
        s += 1
    if pd.notna(implied) and implied >= 23:
        s += 1
    pr = r.get("pos_adp_rank", pos_adp_rank)
    if pd.notna(pr) and pr <= 50:
        s += 1
    return s


def _handcuff_read(mine_df, available, dedicated_open, top_n=2, current_round=None):
    """Late-round CONTINGENCY read (L30/L31). The board prices every player standalone, so it cannot
    see that a backup behind one of MY OWN fragile STARTERS pays out exactly when I need him.

    Scope (all MEASURED, 2014-25, adversarially re-verified):
    * RB ONLY — carries transfer ~1-for-1 (backup 4.0 -> 9.5 ppg when the starter sits); vacated WR/TE
      targets scatter. TE handcuffs are the one absolute fade (boom 4.5%, p=5.5e-6).
    * STARTERS ONLY — a contingency behind a bench player is worthless (FLEX counts, bench doesn't).
    * GO SCREEN over ceiling (L31): the one variable that predicts a handcuff paying off is the role
      he ALREADY has. A committee backup (30%+ of carries) booms ~51% once promoted; a pure clipboard
      backup ~5% — and the clipboard trap is invisible in projections. The draft-day GO screen
      (_go_score >= 2) kept a 42%-vs-18% split on 2022-25 holdout. STARTABLE language only — the
      share signal predicts startable weeks, never league-winners (holdout slope at >=15 ppg: p=.88)."""
    if len(dedicated_open) or not len(mine_df) or "team" not in available.columns:
        return ""
    if current_round is not None and current_round < _DART_ROUND:
        return ""                       # a handcuff is a BENCH-rounds decision (Part 3: R12-14)
    starters = _starters(mine_df)
    base = (mine_df["pos_label"].astype(str).str.replace(r"\d+$", "", regex=True)
            if "pos_label" in mine_df.columns else mine_df.get("position", pd.Series(dtype=str)))
    mine_names = set(mine_df["full_name"])
    cands = []
    for (_, p), pos in zip(mine_df.iterrows(), base):
        if pos != "RB" or p["full_name"] not in starters or pd.isna(p.get("availability")):
            continue
        miss = 1.0 - float(p["availability"])
        pool = available[(available["team"] == p["team"]) & (available["position"] == pos)
                         & (~available["full_name"].isin(mine_names))]
        pool = pool[pool["total_points"] > 0]
        if not len(pool):
            continue
        h = pool.loc[pool["total_points"].idxmax()]
        nn = normalize_name(h["full_name"])
        go = _go_score(nn, None, p.get("team_implied_total"))
        share = _roles().get(nn, {}).get("share_2025")
        sh_txt = f"{share:.0%} of team carries last yr" if pd.notna(share) else "no prior-year role data"
        cands.append((go, miss, p["full_name"], p.get("risk_tier", ""), h["full_name"],
                      h.get("team_role", ""), sh_txt))
    if not cands:
        return ""
    cands.sort(key=lambda c: (-c[0], -c[1]))
    bits = []
    for go, miss, starter, tier, hn, tr, sh_txt in cands[:top_n]:
        tag = ("GO (passes the validated screen: prior role / offense / real price — roughly "
               "DOUBLE the hit rate of a non-GO handcuff, held out-of-sample)"
               if go >= 2 else "NO-GO (fails the screen — non-GO handcuffs hit at roughly half the "
               "GO rate; prefer a validated dart)")
        bits.append(f"{hn} ({tr}, {sh_txt}) behind MY {starter} ({tier or 'starter'}, "
                    f"{miss:.0%} miss risk) — screen: {tag}")
    return ("HANDCUFF READ (my starting RBs' contingencies, GO-screened by PRIOR ROLE — the one "
            "validated predictor; projections can't see it): " + " | ".join(bits)
            + ". Handcuffs buy STARTABLE WEEKS, never league-winners — say it that way. RB only; "
              "never a TE handcuff.\n")


# --- L31: the late-round DART READ (the validated R11-16 strategy, enforced in data per L8) ---
_DART_ROUND = 11          # bench rounds begin here — where VONA sorts sub-replacement noise (L30)
_DART_BONUS = 15.0        # bounded TOP-PICKS rank adjustment for profile matches / fades


def _risky_1start(mine_df):
    """1-start positions (QB/TE) whose FILLED starter is risky (same criteria as the hedge read) —
    the TE dart is sanctioned there as the upside alternative to the safe hedge."""
    out = set()
    if not len(mine_df) or "p_bust" not in mine_df.columns:
        return out
    base = (mine_df["pos_label"].astype(str).str.replace(r"\d+$", "", regex=True)
            if "pos_label" in mine_df.columns else mine_df.get("position", pd.Series(dtype=str)))
    for pos in ("QB", "TE"):
        room = mine_df[base == pos]
        if not len(room):
            continue
        st = room.sort_values("total_points", ascending=False).iloc[0]
        bust = float(st["p_bust"]) if pd.notna(st.get("p_bust")) else 0.0
        if str(st.get("risk_tier", "")) in ("Boom/Bust", "Injury Risk") or bust >= _HEDGE_BUST:
            out.add(pos)
    return out


# the price band each position's late-round rules were VALIDATED on (by ADP positional rank);
# fades apply only inside the band — a mid-priced player falling late is a different situation.
_LATE_BAND = {"RB": 31, "WR": 41, "TE": 13, "QB": 15}


def _dart_profiles(available, mine_df, open_1start, current_round=None, total_rounds=16):
    """Classify available players into validated late-round BUY profiles and FADES (L31).
    Returns (buys, fades). Branch order encodes the synthesis EXACTLY (adversarial-review fix):
    specific fades first (they poison a profile), then BUY profiles, then the deep-band fade LAST —
    P1's carve-out ("deep end is dead money UNLESS it fits a Tier A/B profile") falls out of the
    ordering. Rates in the copy follow the synthesis rulings: Tier-A numbers quotable, Tier-B
    direction-only ("roughly double"), in-season Tier-C numbers never used in draft copy."""
    buys_ranked, fades = [], {}
    R = _roles()
    # the young-TE dart is a FINAL-ROUNDS play only (B6) — and only when TE is open or my TE
    # starter is risky enough that the hedge read is live
    te_count = 0
    if len(mine_df):
        _b = (mine_df["pos_label"].astype(str).str.replace(r"\d+$", "", regex=True)
              if "pos_label" in mine_df.columns else mine_df.get("position", pd.Series(dtype=str)))
        te_count = int((_b == "TE").sum())
    te_dart_ok = (("TE" in open_1start) or ("TE" in _risky_1start(mine_df))) and te_count < 2 and (
        current_round is not None and current_round >= (total_rounds or 16) - 1)
    for r in available.itertuples():
        nn = normalize_name(r.full_name)
        rd = R.get(nn, {})
        pos = r.position
        pr = rd.get("pos_adp_rank", np.nan)
        share = rd.get("share_2025", np.nan)
        ppg25, wks25 = rd.get("ppg_2025", np.nan), rd.get("weeks_2025", np.nan)
        nfl_pick = rd.get("nfl_pick", np.nan)
        if pd.isna(nfl_pick):
            nfl_pick = getattr(r, "draft_pick", np.nan)      # board capital as fallback (rookies)
        age = float(r.age) if pd.notna(r.age) else np.nan
        in_band = pd.notna(pr) and pos in _LATE_BAND and pr >= _LATE_BAND[pos]
        if pd.isna(pr) and pos in _LATE_BAND:
            # no price rank (older role_data): conservative overall-ADP proxy; undrafted = late
            adp = getattr(r, "adp_rank", np.nan)
            in_band = pd.isna(adp) or adp >= {"RB": 80, "WR": 100, "TE": 95, "QB": 105}[pos]
        # ---- specific fades (validated poison combos — they beat any profile) ----
        if in_band and pos in ("RB", "WR") and pd.notna(ppg25) and pd.notna(wks25) \
                and ppg25 >= 10 and wks25 <= 11:
            fades[r.full_name] = ("injury-discount vet (formerly good + missed real time last yr — "
                                  "the validated trap: zero league-winners in 47 cases; the discount is correct)")
            continue
        if in_band and pos == "WR" and pd.notna(age) and age >= 29:
            fades[r.full_name] = "WR 29+ (0 late league-winners in 71 cases)"
            continue
        if in_band and pos == "QB" and bool(getattr(r, "switched_team", False)):
            fades[r.full_name] = "late QB on a NEW team (top-8 rate 2% vs 17% for stayers)"
            continue
        if in_band and pos == "QB" and pd.notna(age) and age >= 33:
            fades[r.full_name] = "QB 33+ (the worst late-QB age bin)"
            continue
        if in_band and bool(getattr(r, "is_rookie", False)) \
                and not (pd.notna(nfl_pick) and nfl_pick <= 100):
            fades[r.full_name] = "rookie without top-100 NFL capital (startable 6.5%)"
            continue
        # ---- BUY profiles, priority-ordered (Part 3) ----
        if pos == "QB" and "QB" in open_1start and pd.notna(pr) and 15 <= pr <= 20 \
                and not bool(getattr(r, "switched_team", False)) \
                and pd.notna(getattr(r, "team_implied_total", np.nan)) and r.team_implied_total >= 23 \
                and pd.notna(ppg25) and ppg25 >= 15 \
                and (pd.isna(age) or 26 <= age <= 32):
            buys_ranked.append((0, pr, r.full_name,
                                "late-QB profile: proven vet in his prime, kept his team, good offense "
                                "(the highest-equity late cell: front-band top-8 ~21% modern)"))
        elif pos == "WR" and pd.notna(pr) and 41 <= pr <= 65 and pd.notna(share) and share >= 0.20:
            solid = pd.notna(ppg25) and ppg25 >= 10
            buys_ranked.append((1 if solid else 2, -share, r.full_name,
                                f"post-hype target-share WR ({share:.0%} of his team's WR-room targets "
                                "last yr" + (" + real prior ppg" if solid else "")
                                + " — the strongest validated late buy: startable 17% vs 4%)"))
        elif pos == "RB" and pd.notna(pr) and 31 <= pr <= 50:
            go = _go_score(nn, pr, getattr(r, "team_implied_total", np.nan))
            if go >= 2:
                buys_ranked.append((2, -(go + (share if pd.notna(share) else 0)), r.full_name,
                                    f"GO-screen RB (score {go}/3"
                                    + (f", {share:.0%} carry share" if pd.notna(share) else ", rookie/no-role — qualifies on price+offense")
                                    + " — roughly DOUBLE the hit rate of non-GO handcuffs, held out-of-sample)"))
        elif pos == "TE" and te_dart_ok and pd.notna(age) and age <= 25 \
                and pd.notna(nfl_pick) and nfl_pick <= 105 \
                and pd.notna(pr) and 13 <= pr <= 40:
            buys_ranked.append((3, pr, r.full_name,
                                "young high-capital TE dart (~1-in-6 top-6 optimistic, ~1-in-10 modern — "
                                "final-round only; the UPSIDE alternative to a safe TE hedge)"))
        # ---- deep-band fade LAST (P1: dead money UNLESS a profile above claimed him) ----
        elif pd.notna(pr) and ((pos == "RB" and pr > 56) or (pos == "WR" and pr > 74)
                               or (pos == "TE" and pr > 30) or (pos == "QB" and pr > 28)):
            fades[r.full_name] = ("deep-band flyer (pooled across positions the back third of the "
                                  "late band is near-dead: ~2% league-winner rate)")
    buys_ranked.sort(key=lambda t: (t[0], t[1]))
    buys = {name: {"prio": pr_, "why": reason} for pr_, _, name, reason in buys_ranked}
    return buys, fades


def _dart_read(buys, fades, current_round):
    """The DART READ context line (bench rounds only). The numbers are already enforced in the TOP
    PICKS ranking (_dart_bonus); this line makes the WHY legible + carries the honesty cap."""
    if current_round is None or current_round < _DART_ROUND or not (buys or fades):
        return ""
    shown, per_prio = [], {}
    for n, v in buys.items():                     # max 2 per profile so one archetype can't flood
        if per_prio.get(v["prio"], 0) < 2 and len(shown) < 5:
            shown.append((n, v)); per_prio[v["prio"]] = per_prio.get(v["prio"], 0) + 1
    b = " | ".join(f"{n}: {v['why']}" for n, v in shown) or "none on the board"
    f = " | ".join(f"{n}: {why}" for n, why in list(fades.items())[:5])
    out = (f"DART READ (R{current_round} — validated late-round strategy; profiles already boosted/"
           f"demoted in TOP PICKS): BUY {b}.")
    if f:
        out += f" FADE {f}."
    out += (" Honesty cap: these profiles roughly DOUBLE per-pick odds and buy startable floors, but "
            "~1/3 of the league-winners that will exist this season fit no draftable signal — the "
            "committee-handcuff edge is strongest IN-SEASON (weeks 3-4 usage + FAAB), so leave bench "
            "flexibility.\n")
    return out


def _lineup_gaps(mine_df):
    """Categorize positions by how my NEXT pick there would fit the STARTING lineup (1QB/2RB/2WR/1TE +
    1 FLEX of RB/WR/TE):
      dedicated_open — fills an empty dedicated slot (QB, RB<2, WR<2, TE<1). Top priority.
      flex_only      — its dedicated slots are full but the single FLEX is open, so it only upgrades the
                       FLEX (a 3rd RB / 3rd WR). FLEX is week-to-week, so fill dedicated needs first —
                       these get demoted below dedicated fillers unless one is WAY better (_FLEX_MARGIN).
      bench_sat      — dedicated full AND the FLEX already claimed -> a further one is BENCH-ONLY (L12).
    Returns (dedicated_open, flex_only, bench_sat) as sets; QB only ever appears in dedicated_open."""
    cnt = {"QB": 0, "RB": 0, "WR": 0, "TE": 0}
    for _, p in mine_df.iterrows():
        pos = str(p.get("pos_label", "")).rstrip("0123456789") or p.get("position", "")
        if pos in cnt:
            cnt[pos] += 1
    ded = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
    ded_open = {p: max(0, ded[p] - cnt[p]) for p in ded}
    flex_filled = sum(max(0, cnt[p] - ded[p]) for p in ("RB", "WR", "TE")) >= 1
    dedicated_open = {p for p in ded if ded_open[p] > 0}
    flex_only = {p for p in ("RB", "WR", "TE") if ded_open[p] == 0 and not flex_filled}
    # bench_sat only means something while a FLEX-eligible starter is still open ELSEWHERE; once the
    # whole RB/WR/TE + FLEX lineup is set it's just bench depth (balance handled by _bench_overstacked).
    flex_elig_open = (not flex_filled) or any(ded_open[p] > 0 for p in ("RB", "WR", "TE"))
    bench_sat = {p for p in ("RB", "WR", "TE") if ded_open[p] == 0 and flex_filled} if flex_elig_open else set()
    return dedicated_open, flex_only, bench_sat


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
    drafted right at your next pick is ~50/50; later = more likely there; earlier = less. UD -> 1.0.

    Built via an explicit ndarray -> Series round-trip: on some numpy/pandas combos (e.g. Streamlit
    Cloud's Python 3.14) `np.exp(a_Series)` returns a bare ndarray, and ndarray has no `.where` — which
    crashed the whole board. Computing on numpy then re-wrapping in a Series keeps it version-proof."""
    adp = adp_rank if isinstance(adp_rank, pd.Series) else pd.Series(adp_rank)
    z = (adp.astype("float64") - horizon) / _ADP_SCALE
    p = pd.Series(1.0 / (1.0 + np.exp(-z.to_numpy())), index=adp.index)
    return p.where(adp.notna(), 1.0)


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


# How many rounds out counts as "my realistic fill window" for a 1-start slot I could punt. VONA looks
# one pick ahead, which under-credits a scarce RB/WR at a snake turn (lesson L11); the punt read looks
# this far ahead instead. Tunable.
_PUNT_LATE_ROUNDS = 5


def _expected_best_survivor(pool, horizon, risk_adj=True):
    """Expected VOLS of the BEST player at `pool`'s position still on the board at `horizon` — each
    candidate weighted by P(he survives) × P(everyone better is gone). Same expectation form add_vona
    uses for `best_wait`, so VONA and the punt read price "what's left later" identically.

    `risk_adj` scales each candidate by (1 − p_bust) so the expectation is in risk-adjusted VOLS.
    Because it's an expectation over the WHOLE remaining pool (not one player), a DEEP position — many
    streamable options — correctly prices out higher than a thin one. That depth IS the streaming
    value of punting a 1-start slot (L28)."""
    g = pool.sort_values("vols", ascending=False)
    busts = g["p_bust"].fillna(0.0) if "p_bust" in g.columns else pd.Series(0.0, index=g.index)
    gone_above, exp_best = 1.0, 0.0
    for v, bust, pi in zip(g["vols"], busts, _survival_prob(g["adp_rank"], horizon)):
        vv = 0.0 if pd.isna(v) else max(float(v), 0.0)
        if risk_adj:
            vv *= (1.0 - float(bust))
        pi = float(pi)
        exp_best += vv * pi * gone_above          # v_i · P(i survives) · P(all better gone)
        gone_above *= (1.0 - pi)
    return exp_best


def _pos_punt_loss(available, pos, late_pick, teams):
    """Risk-adjusted value you LOSE by deferring a position to your fill window, computed identically
    for every position (no magic thresholds — a pure stats comparison):

        punt_loss = elite risk-adj VOLS now − E[best risk-adj VOLS still there at the fill window]

    Both sides are RISK-ADJUSTED (the old form discounted only the fallback while leaving the elite
    raw, which systematically inflated every punt_loss — an apples-to-oranges comparison), and the
    fallback is the EXPECTED BEST SURVIVOR over the whole remaining pool rather than a single player,
    so a position with many streamable options left costs less to defer. Returns None if empty."""
    pool = available[(available["position"] == pos) & available["vols"].notna()]
    if not len(pool):
        return None
    ei = pool["vols"].idxmax()
    e_bust = float(pool.loc[ei, "p_bust"]) if "p_bust" in pool and pd.notna(pool.loc[ei, "p_bust"]) else 0.0
    elite = max(float(pool.loc[ei, "vols"]), 0.0) * (1.0 - e_bust)
    late_adj = _expected_best_survivor(pool, late_pick, risk_adj=True)
    # descriptors for the human-readable streamer text: the best SINGLE option likely to still be there
    surv = pool[_survival_prob(pool["adp_rank"], late_pick) >= 0.5]
    if len(surv):
        i = surv["vols"].idxmax()
        late_vols = max(float(surv.loc[i, "vols"]), 0.0)
        bust = float(surv.loc[i, "p_bust"]) if "p_bust" in surv and pd.notna(surv.loc[i, "p_bust"]) else 0.0
        adp = surv.loc[i, "adp_rank"]
        lasts_round = int((adp - 1) // teams) + 1 if pd.notna(adp) else None
        late_name = str(surv.loc[i, "full_name"])
    else:
        late_vols, bust, lasts_round, late_name = 0.0, 0.0, None, None
    return {"punt_loss": max(elite - late_adj, 0.0), "late_vols": late_vols, "late_bust": bust,
            "lasts_round": lasts_round, "late_name": late_name, "late_pool": late_adj,
            "elite_adp": pool.loc[ei, "adp_rank"]}                                   # for next-pick defer (L33)


# If the ELITE 1-start player himself lasts to my NEXT pick at >= this prob, defer him — grab the
# scarcer RB/WR now and take him next pick. Survival-primary (NOT a single-pick VONA compare, which is
# too noisy at the turn): validated on actual roster value — deferring a surviving TE/QB gains +8..+33
# projected pts at the snake turn (icm/work/mc_research te_defer analysis). L33.
_NEXT_DEFER_P = 0.6


def _punt_read(available, open_1start, current_overall, teams, next_pick=None):
    """For each UNFILLED 1-start slot (QB/TE), decide whether it's PUNT-ABLE — i.e. a startable player
    at that position still lasts to my realistic fill window, so an early pick there is high
    opportunity cost vs a scarce RB/WR (lesson L11). Data-driven, NOT a hardcoded QB/TE discount:

      punt_loss[pos] = (best VOLS now) − (best VOLS still ~50%+ available _PUNT_LATE_ROUNDS out)

    A scarce position (RB/WR-like, late fallback ≈ replacement) keeps a HIGH punt_loss; a deep one
    (a startable player lasts late) gets a LOW punt_loss. `pos` is punt-able when its punt_loss is
    below the best draftable RB/WR's VOLS now (there's a scarcer skill player worth more than what
    you'd lose by deferring the 1-start slot). Returns {pos: {punt_loss, punt_able, lasts_round,
    late_name, late_vols}} plus the RB/WR bar used to gate it. Empty if we can't place the horizon.
    """
    reads = {}
    if not open_1start or not current_overall or not teams or "vols" not in available.columns:
        return reads, 0.0
    late_pick = current_overall + _PUNT_LATE_ROUNDS * teams
    # The bar: the biggest risk-adjusted punt_loss among RB/WR — the scarce skill value you'd lose by
    # deferring. A 1-start slot is punt-able iff deferring IT loses less than deferring the best RB/WR.
    rbwr_losses = [pl["punt_loss"] for p in ("RB", "WR")
                   if (pl := _pos_punt_loss(available, p, late_pick, teams))]
    best_rbwr = max(rbwr_losses) if rbwr_losses else 0.0
    for pos in open_1start:
        r = _pos_punt_loss(available, pos, late_pick, teams)
        if r is None:
            continue
        # Straight comparison, NO safety margin: cheaper to defer than the scarce RB/WR -> punt.
        # A tuned/derived "QB should fall" margin was tried here and REMOVED (L28) — on the real
        # pick-29 board it demoted Josh Allen (VONA 50.7, 3.8x the best RB's 13.3; higher risk-adj
        # VOLS, ceiling, P(elite) AND lower cohort bust) in favour of a worse player. The metrics
        # exist to decide this; a prior about which positions "should" fall does not get a veto.
        r["cliff_bar"] = best_rbwr
        r["punt_able"] = r["punt_loss"] < best_rbwr
        # NEXT-PICK DEFER (L33): even if the position isn't punt-able 5 rounds out, defer the ELITE one
        # HERE when he lasts to my very NEXT pick (and a scarce RB/WR exists to take instead). Because he
        # survives, I get him back next pick regardless, so taking the scarcer RB/WR now is a free gain
        # (+8..33 pts at the snake turn — validated on actual roster value, te_defer). Self-limiting: a
        # genuine cliff never lasts to the next pick, so Josh Allen (survival ~0) is never deferred.
        surv = float(_survival_prob(pd.Series([r["elite_adp"]]), next_pick).iloc[0]) \
            if next_pick and pd.notna(r.get("elite_adp")) else 0.0
        r["elite_survives_next"] = surv
        if surv >= _NEXT_DEFER_P and best_rbwr > 0:
            r["punt_able"] = True
            r["next_defer"] = True
        reads[pos] = r
    return reads, best_rbwr


def build_context(available, mine_df, scarcity, draft_pos=None, top_n=35, my_dst=None,
                  strategy=None):
    """Compact text snapshot of the live board for the current turn. `my_dst` = the D/ST you drafted
    (name) if any — defenses aren't on the board, so it's threaded in separately."""
    horizon = _horizon(draft_pos)
    if "vona" not in available.columns:      # normally precomputed in draft.py; compute if standalone
        available = add_vona(available, horizon)
    # Drop from EVERYTHING the advisor sees: (1) NO-TEAM players (unsigned FAs — no offense/role) and
    # (2) PROJECTION OUTLIERS our board over-rates but the market + experts have written off (John
    # Metchie: our proj 148 vs ECR 361 vs ESPN 589) — recommending them is the whole problem (L15/L17).
    if "no_team" in available.columns:
        drop = available["no_team"].fillna(False).astype(bool)
    else:
        drop = available["team"].isna() | available["team"].astype(str).str.upper().isin({"FA", "NAN", ""})
    if "proj_outlier" in available.columns:
        drop = drop | available["proj_outlier"].fillna(False).astype(bool)
    available = available[~drop]
    cols = ["full_name", "pos_label", "team", "team_role", "team_implied_total", "vols", "vona",
            "adp_rank", "market", "risk_tier", "target_share_2025", "snap_share_2025", "age",
            "is_rookie", "draft_pick", "floor", "ceiling", "p_startable", "p_bust", "xppg",
            "regression", "switched_team"]
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
    smap = _sos()
    if smap and "team" in top.columns and "pos_label" in top.columns:
        bpos = top["pos_label"].str.replace(r"\d+$", "", regex=True)
        top["sos"] = [str(smap[(t, p)][0]) if (t, p) in smap else ""
                      for t, p in zip(top["team"], bpos)]
    is_rook = top["is_rookie"].astype(str).str.lower().isin(["true", "1"])
    top["rook_pk"] = [(str(int(pk)) if pd.notna(pk) else "rook") if r else ""
                      for r, pk in zip(is_rook, top["draft_pick"])]
    top = top.drop(columns=[c for c in ["target_share_2025", "snap_share_2025", "is_rookie",
                                        "draft_pick", "team_implied_total", "xppg"] if c in top])
    top = top.rename(columns={"full_name": "player", "pos_label": "pos", "adp_rank": "ADP",
                              "vona": "VONA", "risk_tier": "risk", "regression": "regr",
                              "p_startable": "P_start%", "p_bust": "bust%", "team_role": "role"})
    if "switched_team" in top:   # xPPG/regr describe the OLD team for a player who moved
        _sw = top["switched_team"].astype(str).str.lower().isin(["true", "1"])
        top.loc[_sw, "regr"] = "new-tm"
        top = top.drop(columns=["switched_team"])
    # Enforce the roster gate in the DATA: null the VONA of filled 1-start positions (QB/TE) so a
    # worthless backup can't show up as the "highest VONA" and get chased (a prose rule alone got ignored).
    blocked = _blocked_positions(mine_df)
    dedicated_open, flex_only, bench_sat = _lineup_gaps(mine_df)   # how a next pick fits my lineup slots
    bench_over = _bench_overstacked(mine_df)                       # RB/WR I already have too many of
    if blocked and "VONA" in top.columns and "pos" in top.columns:
        base = top["pos"].str.replace(r"\d+$", "", regex=True)
        top.loc[base.isin(blocked), "VONA"] = "n/a"
    # PUNT READ (lesson L11): for each UNFILLED 1-start slot, is a startable one recoverable late? VONA
    # looks only one pick ahead, so at a snake TURN it under-credits a scarce RB/WR and over-credits an
    # elite QB's cliff. Computed in Python; a punt-able slot is HARD-DEMOTED below RB/WR in TOP PICKS
    # (enforced in data, gated) so the model can't reach for a recoverable QB/TE.
    open_1start = [p for p in ("QB", "TE") if p not in blocked]
    # L31 — late-round dart profiles (bench rounds only). Computed HERE so the TOP PICKS ranking
    # below can enforce them in data (L8); the DART READ line then explains the why.
    current_round = None
    if draft_pos and draft_pos.get("overall_now") and draft_pos.get("teams"):
        current_round = (int(draft_pos["overall_now"]) - 1) // int(draft_pos["teams"]) + 1
    dart_buys, dart_fades = ({}, {})
    if current_round is not None and current_round >= _DART_ROUND:
        dart_buys, dart_fades = _dart_profiles(available, mine_df, open_1start,
                                               current_round, (draft_pos or {}).get("total_rounds", 16))
    reads, best_rbwr = ({}, 0.0)
    if draft_pos and open_1start:
        reads, best_rbwr = _punt_read(available, open_1start, draft_pos.get("overall_now"),
                                      draft_pos.get("teams"), next_pick=horizon)
    punt_pos = {p for p, r in reads.items() if r["punt_able"]}
    defer_pos = {p for p, r in reads.items() if r.get("next_defer")}   # demoted because he lasts to my next pick (L33)
    punt_line = ""
    if reads:
        bits = []
        for p, r in reads.items():
            lr = f"~R{r['lasts_round']}" if r["lasts_round"] else "late"
            stream = (f"streamer {r['late_name']} lasts {lr}, bust {r['late_bust']:.0%}"
                      if r["late_name"] else "no startable one lasts")
            # Both numbers are risk-adjusted and the fallback prices the whole streamable pool (L28),
            # so state the straight comparison — no margin, no hedging language.
            if r["punt_able"]:
                bits.append(f"{p} is DEEP — deferring costs only ~{r['punt_loss']:.0f} risk-adj VOLS "
                            f"({stream}), LESS than the scarce RB/WR (~{best_rbwr:.0f}) → PUNT: take the "
                            f"RB/WR, fill {p} late")
            else:
                bits.append(f"{p} is a CLIFF — deferring costs ~{r['punt_loss']:.0f} risk-adj VOLS "
                            f"({stream}), MORE than any RB/WR (~{best_rbwr:.0f}) → GRAB the elite if you need {p}")
        punt_line = "PUNT READ (unfilled 1-start slots): " + " | ".join(bits) + "\n"
    # THE ANSWER, computed in Python: draftable players ranked by VONA, then punt-able 1-start slots
    # hard-demoted below RB/WR (L8/L11), so the model can't misread the table or reach for a recoverable
    # QB/TE over the scarce value. Take #1 unless a clear risk/upside reason moves you to #2-3.
    picks_line = ""
    cohort_line = ""
    if "vona" in available.columns:
        skip = set(blocked) | {"K", "DEF", "DST", "D/ST"}   # streamers (K/D-ST) are a final-round call
        pool = available[~available["position"].isin(skip)].copy()
        # L31: a dart-BUY at a blocked 1-start position (the sanctioned young-TE dart when my TE
        # starter is risky) re-enters the pool in bench rounds — it's a deliberate hedge/upside pick,
        # not the worthless-backup trap the block exists for.
        if dart_buys:
            back = available[available["full_name"].isin(dart_buys) & ~available.index.isin(pool.index)]
            if len(back):
                pool = pd.concat([pool, back.copy()])
        # rank by VONA + a bounded depth-chart ROLE nudge (WR1 beats a comparable WR2); real VONA still shown
        pool["_rk"] = pool["vona"] + _role_bonus_series(pool)
        # L31: in bench rounds the validated dart profiles OUTRANK raw VONA entirely — late VONA is
        # sorting sub-replacement noise (L30), so a linear bonus isn't enough. Deterministic tiers:
        # BUY profiles first, neutrals second, FADES last; VONA orders within a tier. Enforced in
        # data so the model can't ignore it (L8).
        if dart_buys or dart_fades:
            pool["_rk"] += pool["full_name"].map(
                lambda n: _DART_BONUS if n in dart_buys else (-_DART_BONUS if n in dart_fades else 0.0))
            pool["_darttier"] = pool["full_name"].map(
                lambda n: 0 if n in dart_buys else (2 if n in dart_fades else 1))
            pool["_dartprio"] = pool["full_name"].map(
                lambda n: dart_buys[n]["prio"] if n in dart_buys else 9)
        else:
            pool["_darttier"] = 1
            pool["_dartprio"] = 9
        # ROSTER RISK gate (L23): if my room at a position is already risk-stacked (>=2 high-bust
        # players), demote a FURTHER high-bust candidate there — but ONLY when a genuinely more
        # stable same-position swap exists at comparable value (late in drafts EVERYONE is
        # high-bust; penalizing all of them equally is noise, not advice). Compensated risk
        # (big ceiling / elite odds) is a legitimate swing and is never demoted.
        risk_state = _roster_risk(mine_df)
        risk_stacked = {p for p, (n, _) in risk_state.items() if n >= _RISK_STACK_N}
        pool["riskstack"] = False
        if risk_stacked and {"p_bust", "ceiling", "total_points"} <= set(pool.columns):
            for pos_ in risk_stacked:
                sub_ = pool[(pool["position"] == pos_) & pool["p_bust"].notna()]
                for i, r in sub_.iterrows():
                    if r["p_bust"] < _HIGH_BUST or _is_compensated(
                            r["p_bust"], r["ceiling"], r["total_points"], r.get("p_elite")):
                        continue
                    stable_swap = ((sub_["p_bust"] <= r["p_bust"] - 0.10)
                                   & (sub_["vona"] >= r["vona"] - 8)).any()
                    if stable_swap:
                        pool.loc[i, "_rk"] -= _RISK_PENALTY
                        pool.loc[i, "riskstack"] = True
        ok = (pool.sort_values(["_darttier", "_dartprio", "_rk"], ascending=[True, True, False])
              .head(25).drop(columns=["_darttier", "_dartprio"]))
        # Best VONA available at a position that fills an OPEN DEDICATED slot (not a punt-able QB) — the
        # bar a FLEX-only option must clear by _FLEX_MARGIN to be worth taking over a dedicated need.
        ded_pool = ok[ok["position"].isin(dedicated_open - punt_pos)]
        best_ded_vona = float(ded_pool["vona"].max()) if len(ded_pool) else None
        def _flex_demoted(pos, vona):   # a FLEX-only piece not clearly better than the dedicated filler
            return (pos in flex_only and best_ded_vona is not None
                    and float(vona) < best_ded_vona + _FLEX_MARGIN)
        # Hard-demote below the dedicated-need fillers (stable = keep VONA order within a tier):
        # BENCH-ONLY lowest, then punt-able 1-start QB/TE, then FLEX-only pieces (fill dedicated first).
        def _sink_rank(pos, vona):
            if pos in bench_over: return 4   # over-stacked (4 RB / 2 WR) — fill the thinner position
            if pos in bench_sat: return 3
            if pos in punt_pos:  return 2
            if _flex_demoted(pos, vona): return 1
            return 0
        if bench_over or bench_sat or punt_pos or (flex_only and best_ded_vona is not None):
            ok = ok.assign(_sink=[_sink_rank(p, v) for p, v in zip(ok["position"], ok["vona"])]
                           ).sort_values("_sink", kind="stable").drop(columns="_sink")
        ok = ok.head(6)
        if len(ok):
            ch = _cohorts()
            cl = []
            for r in ok.itertuples():
                c = ch.get(normalize_name(r.full_name))
                if c:
                    # median = the TYPICAL comp season; trimmed mean = the EXPECTED return once the
                    # boom tail is counted (outcomes are right-skewed, so the median alone hides it).
                    # When the two straddle 1.0x the profile is TAIL-DRIVEN: the middle of the range
                    # mildly misses his price, but you're buying the ceiling. Flagged only on that
                    # crossing — a real verdict flip, not a tuned cutoff.
                    trim = c.get("cohort_trimmed")
                    tail = ""
                    if trim is not None and pd.notna(trim):
                        skew = (" — TAIL-DRIVEN: the typical comp misses his price but the trimmed "
                                "mean clears it, so the value is in the ceiling, not the median"
                                if float(c["cohort_med"]) < 1.0 <= float(trim) else "")
                        tail = f", trimmed-mean {trim}x{skew}"
                    cl.append(f"{r.full_name}: [{c['cohort_desc']}] — boom {c['cohort_boom']:.0%}, "
                              f"bust {c['cohort_bust']:.0%}, med {c['cohort_med']}x{tail}, "
                              f"top-5 {c['cohort_top5']:.0%} ({c.get('cohort_best5', '')}) "
                              f"| closest matches: {c['cohort_comps']}")
            if cl:
                cohort_line = ("COHORT HISTORY (shortlist players' 15 most-similar 2019-25 seasons vs "
                               "their price — comps are real, cite them). med = the TYPICAL comp season; "
                               "trimmed-mean = the expected return WITH the boom tail (fantasy outcomes "
                               "are right-skewed, so a low median can still hide real upside):\n  "
                               + "\n  ".join(cl) + "\n")
        if len(ok):
            top_v = float(ok.iloc[0]["vona"])
            close = 4.0   # players within this many VONA of the top are a genuine tie -> profile decides
            def _pk(r):
                w = f", {_wheel_label(r.adp_rank, horizon)}" if horizon else ""
                star = "*" if (top_v - float(r.vona)) <= close else ""
                rl = getattr(r, "role_lead", 0.0)
                rl = float(rl) if rl is not None and pd.notna(rl) else 0.0
                env_ok = getattr(r, "role_env_ok", True)
                env_ok = bool(env_ok) if pd.notna(env_ok) else True
                role = (", CLEAR ALPHA (locked targets)" if rl >= 15 and r.position in _FLEX_OK and env_ok
                        else ", behind the alpha (capped targets)" if rl <= -15 and r.position in _FLEX_OK and env_ok else "")
                tag = (", TE DART — sanctioned exception to the 1-start block (deliberate final-round "
                       "hedge/upside pick; the block otherwise stands)"
                       if r.position in blocked and r.full_name in dart_buys
                       else ", OVER-STACKED (you have plenty — fill a thinner position)" if r.position in bench_over
                       else ", BENCH-ONLY (starter open elsewhere)" if r.position in bench_sat
                       else ", DEFER (he lasts to your NEXT pick — take the scarcer RB/WR now, grab him next)" if r.position in defer_pos
                       else ", PUNT-ABLE fill late" if r.position in punt_pos
                       else ", FLEX-only (fill a dedicated starter first)" if _flex_demoted(r.position, r.vona)
                       else f", RISK-STACKED (your {r.position} room already carries "
                            f"{risk_state[r.position][0]} high-bust players and this adds more "
                            "uncompensated risk — prefer the stable option)"
                       if getattr(r, "riskstack", False)
                       else "")
                return f"{star}{r.full_name} ({r.pos_label}, VONA {r.vona:.0f}{w}{role}{tag})"
            picks_line = ("TOP PICKS NOW — the value ranking, but it is STRATEGY-BLIND (Python doesn't "
                          "read my plan): take #1 when it fits MY STRATEGY; when my plan directs elsewhere, "
                          "take the highest-ranked pick that FOLLOWS the plan (rule 0 — an absolute "
                          "instruction is binding). Within that, the order already blends "
                          "VONA with roster gates AND role security, so DON'T re-sort it by the raw VONA "
                          "column — a lower-VONA player placed higher is INTENTIONAL (a team's clear WR1/"
                          "RB1 with locked targets beats a higher-VONA WR2/WR3 whose targets are capped "
                          "behind the alpha + a pass-catching RB). Demotions, lowest first: OVER-STACKED "
                          "(you already have plenty of that position — keep RB/WR depth even, don't add a "
                          "5th RB with 2 WR), BENCH-ONLY (a 4th RB while a starter is open), punt-able "
                          "1-start QB/TE, FLEX-only pieces (fill fixed QB/RB/WR/TE starters before the "
                          "week-to-week FLEX). A RISK-STACKED warning = my room there is already "
                          "bust-heavy and this player adds more risk WITHOUT a paying ceiling — he's "
                          "already down-weighted, so if a stable option sits near him, take the stable "
                          "one; if he STILL ranks #1, he's simply the value — take him, but say the risk "
                          "out loud. The *starred ones are "
                          "within a few VONA = a TIE — among them pick the BEST PLAYER by CLEAR-ALPHA role, "
                          "age, risk/reward, offense (vegas). Only override #1 for a real risk/upside reason. "
                          + " | ".join(f"{i+1}. {_pk(r)}" for i, r in enumerate(ok.itertuples())) + "\n")
    order = ["player", "pos", "team", "role", "vegas", "sos", "VONA", "vols", "ADP", "wheel", "tgt%", "snap%",
             "age", "rook_pk", "market", "risk", "floor", "ceiling", "P_start%", "bust%", "xPPG", "regr"]
    board_txt = top[[c for c in order if c in top.columns]].to_string(index=False)

    if len(mine_df) or my_dst:
        roster = ", ".join(f"{r.pos_label} {r.full_name}" for r in mine_df.itertuples()) or "—"
        if my_dst:
            roster += f", D/ST {my_dst}"
        proj = mine_df["total_points"].sum()
        needs = _roster_needs(mine_df, my_dst, saturated=bench_sat, flex_only=flex_only)
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

    # ROSTER RISK line (L23): tell the model how much bust risk each of my rooms already carries,
    # so tie-breaks lean stable when a room is loaded and a swing stays fine when it isn't.
    risk_bits = []
    for p, (n, avg) in _roster_risk(mine_df).items():
        if n >= _RISK_STACK_N:
            risk_bits.append(f"{p} room is BUST-HEAVY ({n} players ≥{_HIGH_BUST:.0%} bust, avg "
                             f"{avg:.0%}) — on close calls take the STABLE {p}; more uncompensated "
                             f"risk there is already demoted in TOP PICKS")
        elif n == 0 and avg < 0.25:
            risk_bits.append(f"{p} room is safe (avg bust {avg:.0%}) — a compensated boom/bust "
                             f"swing there is affordable")
    risk_line = ("ROSTER RISK: " + " | ".join(risk_bits) + "\n") if risk_bits else ""

    # STREAMER ALERT (full-system stress catch): TOP PICKS excludes K/D-ST by design, so in the
    # FINAL rounds nothing ever forced them - a live-API test draft finished with no kicker.
    # When remaining picks barely cover the open streamer slots, force the call.
    streamer_line = ""
    total_rounds = (draft_pos or {}).get("total_rounds")
    if draft_pos and total_rounds:
        picks_made = len(mine_df) + (1 if my_dst else 0)
        have_k = any(str(p.get("pos_label", "")).startswith("K") for _, p in mine_df.iterrows())
        open_streamers = (0 if have_k else 1) + (0 if my_dst else 1)
        picks_left = max(total_rounds - picks_made, 0)
        if open_streamers and picks_left <= open_streamers + 1:
            ks = available[available["position"] == "K"].nsmallest(3, "rank_composite")                 if "position" in available.columns else available.iloc[0:0]
            kn = ", ".join(ks["full_name"]) if len(ks) else "any listed K"
            needs_txt = " and ".join((["your K"] if not have_k else []) + (["your D/ST"] if not my_dst else []))
            streamer_line = (f"STREAMER ALERT: only {picks_left} pick(s) left and {needs_txt} still open - "
                             f"your remaining pick(s) MUST be spent there. Best K available: {kn}. "
                             f"D/ST: take the top available from the ranking below.\n")

    # HEDGE READ (L27): the 1-start block is risk-blind, so when my only QB/TE is a boom/bust starter
    # and my plan hedges risky positions, surface the hedge-vs-stream call (dedicated starters must be set).
    hedge_line = _hedge_read(mine_df, available, dedicated_open)
    # HANDCUFF READ (L30): in the bench rounds VONA is sorting sub-replacement noise, so surface the
    # contingencies behind MY OWN fragile starters — value the standalone board can't see.
    handcuff_line = _handcuff_read(mine_df, available, dedicated_open, current_round=current_round)
    dart_line = _dart_read(dart_buys, dart_fades, current_round)

    pc = _playcallers()
    pc_line = ""
    if pc:
        chg = [f"{t}{'*' if v.get('pc_first_time') else ''} ({v['playcaller_2025']} -> {v['playcaller_2026']})"
               for t, v in sorted(pc.items()) if v.get("pc_changed")]
        if chg:
            pc_line = ("PLAYCALLER CHANGES 2026 (* = first-time caller; scheme uncertainty — see rules): "
                       + ", ".join(chg) + "\n")
    dst_line = f"\n\nD/ST draft ranking (streamer, draft late): {DST_TEXT}" if DST_TEXT else ""
    return (
        "LIVE DRAFT STATE\n"
        + dp_line +
        f"My roster (projected {proj:.0f} pts): {roster}\n"
        f"{needs}\n"
        + (f"MY DRAFT PLAN — this is the strategy I chose; EXECUTE it (deviation protocol applies, "
           f"and every pick answer includes the Plan: note): {strategy}\n" if strategy else "")
        + f"{risk_line}"
        f"{hedge_line}"
        f"{handcuff_line}"
        f"{dart_line}"
        f"{punt_line}"
        f"{picks_line}"
        f"{cohort_line}"
        f"{pc_line}"
        f"{streamer_line}"
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
    with client.messages.stream(
        model=MODEL_ADVISOR,                    # Sonnet for both; the terse PICK prompt keeps it fast
        max_tokens=400 if is_pick else 900,
        system=_system_blocks(PICK_MODE if is_pick else CHAT_MODE),
        messages=messages,
    ) as stream:
        yield from stream.text_stream


def _system_blocks(mode_text):
    """System prompt as blocks: the big shared SYSTEM is cached (prompt caching — identical on
    every call, so the API bills ~10% of it after the first call in each 5-min window), while the
    small per-mode suffix stays uncached after the breakpoint."""
    return [
        {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": mode_text},
    ]


# The PRE-READ runs in the BACKGROUND while other teams pick (speculative precompute) — no clock
# pressure, so it thinks deeper than the on-clock PICK mode and plans contingencies. The app shows
# it instantly when you go on the clock IF the board hasn't changed since (exact state-key match).
PRELOOK_MODE = """MODE: PRE-READ — you are thinking AHEAD of my turn while other teams pick. There is no clock pressure: reason deeply about the board, my roster, and MY STRATEGY before answering — the pick must EXECUTE my plan (deviation protocol applies). Your answer will be shown to me INSTANTLY when I go on the clock with this exact board, so make it decision-ready:
**PICK: Name (POS)** — one short sentence why; cite ONE cohort comp when it strengthens the case ("profile like X '21").
Plan: how this advances my strategy, a few words (if none set, need/value instead).
If sniped: **Name2** — a few words when/why. (Up to two pivots, only for players realistically taken before my turn — use the `wheel` column.)
Watch: one short line — who wheels back safely; or, if deviating cleared the protocol, both options PLAN-FIRST like PICK mode.
Under ~120 words visible. COMMIT — no hedging, no questions back."""


def prelook(client, context):
    """Deep background pre-read of the current board (non-streaming; runs in a worker thread).
    Adaptive thinking is ON — this call happens off the clock, so spend the extra seconds on
    quality; the user only ever sees the finished text."""
    msg = client.messages.create(
        model=MODEL_ADVISOR,
        max_tokens=3000,                        # room for thinking + the short visible answer
        thinking={"type": "adaptive"},
        system=_system_blocks(PRELOOK_MODE),
        messages=[{"role": "user", "content": context}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
