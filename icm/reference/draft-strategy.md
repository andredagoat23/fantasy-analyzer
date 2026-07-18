# Draft Strategy (Layer 3 — source of truth for the advisor)

The advisor's system prompt in `advisor.py` is a DERIVATIVE of this document. When strategy changes,
change it here first, then update the prompt to match. This is what "the advisor should know" — the
what, why, and how of a pick.

## League
12-team snake, custom-scoring PPR. Starters: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 D/ST, 1 K,
plus bench. One QB and one TE start — this drives everything below.

## The decision, in strict priority order
A later factor NEVER overrides an earlier one.

1. **ROSTER NEED.** Only recommend a position that improves the roster (an open starter/FLEX, or
   genuine bench upside at RB/WR/elite TE). Never a position already filled, for any reason. Once
   starters + FLEX are full: bench upside only (young/ascending RB/WR with ceiling); hold D/ST and K
   for the final 2–3 rounds. Roster needs are COMPUTED in Python (`_roster_needs`) and handed to the
   model as an explicit line — the model must not infer them.

2. **PLAYER VALUE, then UPSIDE & RISK for close calls.** VOLS (value over last starter) is the value
   backbone. Among players of comparable VOLS, use the rest of the profile — ceiling/boom, floor/
   bust, role (tgt%/snap%), situation (vegas/team), tier, xPPG/regression — to choose the one that
   fits the RISK APPETITE (upside build → ceiling/boom; safe build → floor/durable). VOLS anchors;
   the rest modulates. Do NOT abandon VOLS to chase raw ceiling.

3. **MARKET & SCARCITY are tiebreakers only.** `market` (VALUE/REACH) is a PRICING signal (can I
   wait, or take him a hair early?), never a talent signal. A "steal" you don't need, or who's simply
   worse than another available player, is worth nothing. A thin tier is only a reason to act if the
   remaining player is genuinely elite AND you need the position — otherwise scarcity pushes you
   TOWARD where the league-winning talent still is, not into the scarce spot.

## The QB/TE trap (the hard-won correction — see lessons L3)
The board's VOLS OVER-rates QB and TE for draft timing. An elite rushing QB posts huge raw points, so
his VOLS can look RB-level (e.g. the QB1 shows VOLS ~80). But you start only ONE QB and ONE TE and
can get strong production far later. So:
- Treat QB and TE as WAIT positions **regardless of how high their VOLS looks.**
- Don't draft a QB before ~round 5–6, or a TE in the first ~4 rounds, on VOLS alone.
- Take one early ONLY if the RB/WR core is already strong AND a truly elite one has fallen well past
  his ADP. K is always the final pick.
- Prioritize RB/WR early: FLEX-eligible, injury-attrition, genuinely scarce over a full roster.

## Wheel-back ("will he last to my next pick?") — COMPUTED, not reasoned
The math is done in Python (`build_context`) and handed to the model as a `wheel` column per player:
- **gone** = his ADP is at/before your next pick (take him now if you want him)
- **risky** = within a round (toss-up)
- **safe** = a full round of cushion (you can wait and take a better-fit player)
The model READS the column and never re-derives it from ADP. Draft position (which pick is yours,
picks-away, next pick) is likewise Python-computed and quoted verbatim.

## Data the advisor is given (per available player)
VOLS, ADP, `wheel`, positional tier, market, risk tier, floor, ceiling, P(start)%, bust%, xPPG,
regression (TD-lucky / Buy-low / Sustainable / new-tm), team vegas total, tgt%/snap%, age, rookie
draft pick. All of it is fair game for step 2; none of it overrides step 1.

## Known data caveat (flagged, not silently fixed)
`value_board.csv` VOLS runs hot for elite QB/TE in this 1-QB/1-TE format. The advisor corrects for it
at the prompt layer (the QB/TE trap above). Correcting the board itself is a pipeline/VOLS-calibration
change — do not do it without the user asking (frozen boundary).

## Modes
- **Pick button** (`PICK_MODE`): one bold name + one reason + a bold fallback, <~50 words, decisive —
  no thinking out loud or self-correction.
- **Chat** (`CHAT_MODE`): discuss/compare; don't declare a single pick unless asked.
- Both run on Sonnet (`claude-sonnet-4-6`); cheap one-shot setup helpers run on Haiku.
