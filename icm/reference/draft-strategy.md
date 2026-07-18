# Draft Strategy (Layer 3 — source of truth for the advisor)

The advisor's system prompt in `advisor.py` is a DERIVATIVE of this document. Change strategy here
first, then update the prompt to match. This is what "the advisor should know" — the what, why, and
how of a pick.

## League
12-team snake, custom-scoring PPR. Starters: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 D/ST, 1 K,
plus bench. One QB and one TE start — this drives the positional logic below.

## The core idea: draft by VONA, not overall rank or VOLS
Drafting by overall rank / VOLS answers "who's the best player left?" (absolute value). What wins is
"where does waiting cost me the most?" — the drop-off from the best guy at a position to the next guy
I could realistically still get at my next pick. That is **VONA — Value Over Next Available**.

**VONA(player) = his VOLS − `best_wait[his position]`, where `best_wait` is the EXPECTED VOLS of the
best player still on the board at your NEXT pick** — each candidate weighted by the probability he's
the top survivor (he survives AND everyone better at his position is gone). Survival is a softened
**logistic of ADP vs your next pick** (`_survival_prob`, scale `_ADP_SCALE`≈7), not a hard cutoff —
a player drafted right at your next pick is ~50/50, a round later ~88%. Floored at replacement (0).

This works out to **VONA ≈ P(he's gone) × (his VOLS − the next-best you'd expect)** — the drop-off
behind him, weighted by how likely you actually lose him.

- Computed in Python: `advisor.add_vona(available, horizon)`. `horizon` = your next pick after the one
  being decided. Shared by the advisor context AND the board's VONA column so they always agree.
- ADP-driven by construction. High VONA = a real cliff behind him you'll likely lose (grab now);
  VONA ≈ 0 = comparable value will still be there (wait).
- **The model gets a Python-ranked "TOP PICKS NOW" list** (draftable players by VONA; K/D-ST + filled
  1-start QB/TE excluded) and is told to take #1 unless a clear risk/upside reason bumps it to #2-3.
  This is because softening compressed the numbers and the model reverted to force-filling a safe
  open starter and even misread the VONA column — the ranked list makes the answer unambiguous
  (lesson L8: enforce in data what the model gets wrong).
- It REPLACES the old ECR tiers (stale, inaccurate — lesson L7) with the live, personalized drop-off,
  and it makes the wheel-back direction STRUCTURAL: the "gone" cliff has high VONA, the "safe" guy has
  low VONA, so you take the right one without the model having to reason out the direction (it kept
  flipping it — lessons L2/L5-adjacent).

## The decision
1. **ROSTER NEED filters what's DRAFTABLE** (it does NOT force-fill):
   - Draftable: any open starter/FLEX, plus **RB/WR bench depth** (RB and WR always keep bench/FLEX
     value via injuries/upside).
   - NOT draftable: a **filled 1-start position** — QB and TE are 1-start, so a 2nd QB or 2nd TE is
     nearly worthless (you start one, they're streamable), *no matter how high its VONA*. Also no
     K/D-ST before the lineup is full. This is enforced IN DATA: `build_context` nulls a blocked
     position's VONA to `n/a` so the model can't chase it (a prose rule alone got ignored — lesson L8).
   - A still-open starter whose good options will KEEP (wheel "safe", low VONA) can WAIT — grab a
     bigger VONA cliff at a draftable RB/WR now, fill the safe slot next pick for the same value. But
     don't let an open starter rot if its options are going (rising VONA / wheel "gone").
2. **VONA is the SHORTLIST, not the final answer.** `build_context` computes a ranked "TOP PICKS NOW"
   list and **stars options within a few VONA of the top** (a genuine tie). Among the starred, pick the
   BEST PLAYER by age, risk/reward, offense (vegas) and role (tgt%/snap%) — NOT the tiny VONA gap (the
   softened VONA compresses the numbers — lesson L10). Only when one VONA clearly stands alone does it
   decide by itself. Within a position, best available (highest VOLS).
3. **RISK APPETITE steers the tiebreak:** upside build → ceiling/boom/ascending roles/high vegas+role;
   safe build → floor/durable/low bust. `market` is a pricing tiebreaker only (can I wait?), never a
   talent signal.

**Roster tracking (all 9 starters).** The advisor tracks QB/RB/RB/WR/WR/TE/FLEX + D/ST + K. K is on
the board (resolves normally); **D/ST is NOT on the board**, so it's detected from the raw picks
(`bridge.my_dst`) and threaded in via `build_context(my_dst=)`. `_roster_needs` reports what you HAVE
and only says "complete" when the full lineup is set — it used to ignore K/D-ST and miscount (L9).

**Timing is already inside VONA.** Because `best_wait` weights the next-tier players by their survival
probability, a position where a comparable player lasts several rounds yields a LOW VONA (take other
guys now, grab that position later); a real cliff yields a HIGH VONA. No separate "when does the next
guy go" rule is needed — VONA is the point-maximizing signal for it.

## Why QB/TE fall on their own now (no hardcoded discount)
QB and TE are deep, so comparable production usually still lasts to your next pick → their VONA is
low → you naturally wait, with no "don't draft QB before round 5" rule. If a QB/TE ever shows a
genuinely top VONA at a position you NEED (a real cliff), that's a real signal — take it. This
replaced the old hardcoded QB/TE-discount hack (lesson L3), which the user asked to remove in favor of
trusting VONA. Watch: if the board's VOLS over-rates elite rushing QBs, their VONA can run hot — if
that resurfaces, it's a board/VOLS calibration issue (frozen pipeline), flag it, don't hack the prompt.

## Wheel-back — still Python-computed, still read never re-derived
The `wheel` column (gone / risky / safe) is the per-player timing read; VONA is the position-level
decision. Both use the same `horizon`. The model reads them; it never does the ADP arithmetic.

## Data the advisor is given
VONA, VOLS, ADP, `wheel`, market, risk tier, floor/ceiling, P(start)%/bust%, xPPG/regression, team
vegas total, tgt%/snap%, age, rookie pick. VONA drives; the rest breaks close calls. Tiers are GONE.

## Modes / models
Pick button = terse decisive one-pick answer; chat = discuss. Both on Sonnet (`claude-sonnet-4-6`);
setup helpers on Haiku.
