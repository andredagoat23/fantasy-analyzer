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
   - **LINEUP-SLOT gates (`_lineup_gaps`, lessons L12/L13).** VONA is position-blind, so a next pick is
     categorized by how it fits the starting lineup, and TOP PICKS is hard-demoted accordingly (enforced
     in data — prose alone got ignored):
     - *dedicated-open* — fills an empty dedicated slot (QB / RB<2 / WR<2 / TE<1): top priority.
     - *FLEX-only* (L13) — dedicated slots full, only the single FLEX open (a 3rd RB / 3rd WR). FLEX is
       week-to-week / streamable, so **fill dedicated starters first** — demoted below the dedicated
       fillers UNLESS its VONA beats the best dedicated filler by `_FLEX_MARGIN` (a real value cliff, so
       a stud still gets taken).
     - *bench-saturated* (L12) — dedicated full AND the FLEX already claimed (3 RB, 3 WR, 2 TE): a
       further one is BENCH-ONLY, demoted lowest while any FLEX-eligible starter is open (the 3-RB-0-WR
       trap). Once the lineup's FLEX-eligible slots are set, both gates stop (normal bench depth).
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

## Why QB/TE fall on their own — VONA, augmented by the PUNT READ at turns
QB and TE are deep, so comparable production usually still lasts to your next pick → their VONA is
low → you naturally wait, with no "don't draft QB before round 5" rule. If a QB/TE ever shows a
genuinely top VONA at a position you NEED (a real cliff), that's a real signal — take it. This
replaced the old hardcoded QB/TE-discount hack (lesson L3), which the user asked to remove in favor of
trusting VONA.

**The gap VONA alone leaves (lesson L11).** VONA measures value lost by waiting ONE pick (your next
pick). At a snake TURN (back-to-back picks) that lookahead is ~free for everyone, so a scarce RB/WR
who "survives one pick" gets under-credited while an elite QB's within-position cliff wins — which is
how a July-2026 mock took an elite QB (VOLS 80, a legit VORP over QB12) in round 2 over a scarce RB
(VOLS 101), even though a startable QB lasts to ~R11. The board's VOLS is NOT wrong (deepening the QB
baseline BACKFIRES — it raises elite-QB VOLS); the miss is a horizon artifact in the cross-position
decision.

**The punt read (the fix, computed in Python — L8). Fully stats-based, no tuned thresholds.** For every
position compute the same number — the risk-adjusted value you'd LOSE by deferring it to your fill
window:

    punt_loss[pos] = elite VOLS now − (best VOLS still ~50%+ available ~5 rounds out) × (1 − bust%)

The `× (1 − bust%)` is the VARIANCE factor: a boom/bust late streamer (an old TE dart) is worth less
than its projection, so deferring that position costs MORE. An unfilled 1-start slot (QB/TE) is
**punt-able iff its punt_loss < the best RB/WR's punt_loss** — a straight comparison, no margin. Two
refinements make that comparison honest (L28):
- **Both sides risk-adjusted.** The elite is `VOLS × (1 − p_bust)`, same as the fallback. The old form
  discounted only the fallback and left the elite raw, which inflated every punt_loss.
- **The fallback is the EXPECTED BEST SURVIVOR** (`_expected_best_survivor`, the same expectation
  `add_vona` uses for `best_wait`) over the whole remaining pool — not one player. A position with many
  streamable options left therefore costs less to defer. *That depth is what "punting" actually buys*,
  and it's now priced instead of assumed.

**No positional prior gets a veto.** A "QB/TE should fall" margin was added here and then REMOVED: on the
real pick-29 board it demoted Josh Allen — VONA **50.7 vs the best RB's 13.3**, higher risk-adjusted VOLS
(60.3 vs 55.3), higher ceiling (564 vs 389), higher P(elite) (28% vs 8%) and the LOWEST cohort bust (18%)
— in favour of a worse player. The RB pool was simply deep there and the QB pool cliffed. The metrics
exist to make this call; conventional wisdom about which positions "should" wait does not override them.
If a stated STRATEGY wants a different pick, that belongs in the strategy-conflict protocol (L20/L25),
not baked into the value math.
Punt-able slots are HARD-DEMOTED below the RB/WR in TOP PICKS (enforced in data) and tagged; the PUNT
READ line shows each position's punt_loss + streamer + bust%. It self-corrects: once the elite QB is
the scarcest value or depth dries up, its punt_loss exceeds the RB/WR bar → it's a CLIFF → grabbed
(an open QB/TE never rots). Knob: `_PUNT_LATE_ROUNDS` (5).

**Consequence to know:** because this is raw-value-optimal, at a turn it grabs the highest-punt_loss
player first (often the scarce RB, then the elite QB by VONA) — so it will sometimes take an elite QB
over an elite TE, unlike the earlier `keep_frac` version that always grabbed TE. The variance factor
keeps TE stickier than QB (its streamers bust more) but does not override a genuine QB VONA edge.
Verified: mock pick 24 takes Chase Brown (scarce RB) and passes the round-2 QB; the L11 reach is gone.

**The HEDGE READ — the flip side of the punt read (L27).** The punt read governs an UNFILLED 1-start
slot (wait vs. grab). Once a 1-start slot is FILLED, `_blocked_positions` blocks a 2nd (a backup QB/TE
is nearly worthless) — but that block is risk-BLIND. So when my only QB/TE is a boom/bust starter and
my plan says to hedge risky positions, `_hedge_read` surfaces the hedge-vs-stream CALL: it names the
safest available backup + the stream alternative, fires only for a risky starter (Boom/Bust / Injury
Risk / `p_bust ≥ _HEDGE_BUST`=0.35) and only once dedicated starters are set, and is explicit that a
backup is INSURANCE not a value pick (the backup's VONA stays blocked — it never enters TOP PICKS).
It stays silent for a safe stud QB and fires for a boom/bust TE — exactly the split we want.

**The HANDCUFF READ — late rounds price the CONTINGENCY (L30).** By the bench rounds every remaining
player is below replacement, so VONA sorts negative numbers ("least bad") and prefers safe low-ceiling
veterans over darts. Worse, the board prices players STANDALONE and cannot see that a backup behind my
own fragile starter pays out exactly when I need him. `_handcuff_read` computes **contingency value =
P(my starter misses time) x the backup's ceiling** (`availability` IS the probability — no tuned
threshold), and surfaces the top one or two once dedicated starters are set. Explicitly NOT a value
ranking, so it informs without distorting TOP PICKS. **Two scope rules, both measured on 2014-25 weekly
data (281 team-seasons where a starter missed 3+ games):**
- **RB ONLY.** Backup RB goes **4.0 -> 9.5 ppg (2.25x, 56% gain 5+)** when the starter sits — carries
  transfer ~1-for-1. **WR is 7.2 -> 8.6 (1.17x)** because vacated targets scatter across WR2/WR3/TE/RB,
  and **TE 2.3 -> 4.8**, still below streaming level. WR/TE handcuffs are noise.
- **STARTERS ONLY** (`_starters`, greedy 1QB/2RB/2WR/1TE + FLEX). A contingency behind a BENCH player is
  worthless — I wasn't starting him anyway. FLEX counts; pure bench does not.
(Tested and rejected: re-ranking late by `P_pos1` barely changes the list; raw `ceiling` returns only QBs.)

**The DART READ — the validated late-round playbook (L31).** From R11 on, TOP PICKS switches to
deterministic BUY / neutral / FADE tiers driven by `_dart_profiles` (profiles beat projections once
everyone is below replacement). The full evidence-backed playbook — buys, fades, the handcuff GO
screen, what failed validation, and the honesty cap — lives in **`late-round-strategy.md`** (source
of truth for the advisor's late-round behavior). Data layer: `role_priors.py` -> `role_data.csv`
(prev-season workload shares; regenerate with the other priors after a board rebuild).

## Wheel-back — still Python-computed, still read never re-derived
The `wheel` column (gone / risky / safe) is the per-player timing read; VONA is the position-level
decision. Both use the same `horizon`. The model reads them; it never does the ADP arithmetic.

## Data the advisor is given
VONA, VOLS, ADP, `wheel`, market, risk tier, floor/ceiling, P(start)%/bust%, xPPG/regression, team
vegas total, `role` (depth-chart slot on his CURRENT team, e.g. BUF WR1 / DET WR2 — derived in
`load_board`, L14), tgt%/snap%, age, rookie pick. VONA drives; the rest breaks close calls. Tiers are
GONE. **Role reads:** WR1/RB1 on a high-vegas offense = secure volume; WR2/WR3 competes with the alpha
+ a pass-catching RB1. TOP PICKS ranks by VONA + a role nudge scaled by `role_lead` (his projection
gap to the next player in his position room, L16) — a CLEAR alpha beats a comparable WR2, a coin-flip
WR1 gets ~nothing. GATED by `role_env_ok` (team above-median in vegas OR pass volume): the WR1 bump
only fires on an offense that throws valuable targets — a WR1 on a bad, run-heavy team gets none.
Entries tag "CLEAR ALPHA" and the model is told to TAKE #1 (not re-sort by VONA).
**Stale-role caveat:** tgt%/snap% are last season's, so for a mover (regr "new-tm") they're his OLD
team — discount them, trust role + projection. **No-team FAs** are now DROPPED in `value_board.py`
(frozen pipeline, L16), and a below-replacement "VALUE" tag is suppressed there too (a steal below
replacement is cheap-because-bad, not underpriced — L1).

## How the advisor treats MY stated strategy (L20)
Strategy text from setup flows to the advisor via `_setup_note()`. VONA/value stays the backbone, but
strategy shapes how it's used, per the user's spec:
1. **Risk-flavored strategy re-weights value** (not just ties): high-risk/high-reward/upside → VONA
   matters LESS, lean ceiling/boom/ascending roles; safe/floor → the opposite.
2. **A positional-rule conflict** (strategy says "no RB" but the top VONA is an RB; "punt TE" but an
   elite TE is the cliff) → the advisor gives BOTH, labeled: leads with **Best value: X** (with the
   VONA cost of following the strategy) then **Sticking to your [strategy]: Y** (best strategy-compliant
   pick), and lets the user choose. It neither silently overrides nor blindly obeys. Testing showed the
   old behavior was value-first with a soft override (it took the RB and buried the strategy option);
   this makes the strategy choice explicit. PICK mode swaps its fallback for the two labeled options
   when there's a conflict.

## Modes / models
Pick button = terse decisive one-pick answer; chat = discuss. Both on Sonnet (`claude-sonnet-4-6`);
setup helpers on Haiku.
