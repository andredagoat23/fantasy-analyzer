# First-round PREREQUISITES — what has to be true for a R1 pick to hit (Jul 27, 2026)

**The question (user hypothesis):** every player carries a specific set of make-or-break conditions,
so the useful research is per-player — "what separated the boom seasons from the bust seasons for
players *like him*." The cohort layer already gives marginal RATES + named comps; it cannot say what
had to be TRUE. This tested the conditions directly.

**Data:** `seasons_exp.parquet`, the project's own 2014-25 panel. Population = every season priced
inside the top 15 overall (n=145, 2015-2025). Outcome = `mult` (season finish ÷ preseason price):
HIT ≥ 1.0, BUST ≤ 0.7. Every condition is knowable ON DRAFT DAY (prior-season or static).
Train 2015-2021 / holdout 2022-2025 — a condition only counts if it survives out of sample.
Scripts: `mc_research/23_r1_prerequisites.py`, `24_r1_availability_and_2026.py`.

---

## Finding 1 — first-rounders don't disappoint, they get hurt
Base rates: **HIT 52.4%**, BUST 18.6% (27 of 145). Of those 27 busts:

| how the bust happened | share of busts |
|---|---|
| missed 5+ games | **81.5%** |
| played 15+ games and merely underperformed | **7.4%** |

By position: RB HIT 49.4% / BUST 21.0% · WR HIT 55.0% / BUST 15.0%.
**P(plays 15+ games): RB 51.9% vs WR 66.7%** — the single largest structural gap in the study.

So "is he good enough?" is nearly the wrong question in round 1. Essentially every top-15 pick is good
enough. The question is whether he is *available*.

## Finding 2 — availability is close to unpredictable, and the popular tells are worthless
Base P(15+ games) = 58.6%. Tested against it:

| claim people make | train lift | holdout | verdict |
|---|---|---|---|
| he played 16+ games last year | −4.3pp | −3.6 | **no signal** |
| he has no injury history (0 wks out) | −11.0pp | −3.6 | **no signal (negative)** |
| he's young (≤25) | +5.7pp | +13.4 | inconsistent |
| big backs hold up (RB ≥215 lbs) | −16.0pp | −21.1 | **no signal (negative)** |
| light prior workload (below-median touches) | +15.4pp | +8.3 | **HOLDS** |
| he's a WR, not an RB | +13.7pp | +5.9 | **HOLDS** |

**Correlation between last year's games played and this year's: +0.019.** That is zero. Players who
missed badly last year (≤10 games) played 15+ this year **57.1%** of the time — *better* than the guys
who were basically healthy (15-16 games) at **53.2%**. Age vs games: −0.058, also nothing.

Two things do survive: **cumulative workload** (heavy prior-season touch counts predict missing time —
wear is real) and **position** (RB is structurally fragile). Note this independently validates the
pipeline's current design: the Monte Carlo applies a *position-level* availability prior (~.82-.85)
rather than a player-specific injury-history adjustment, which is exactly right given the +0.019.

> **Flag, not an edit:** prior-season total touches predicting availability is NOT modeled anywhere
> today, and `compute_outcomes.py` is frozen. Raising it as a data-quality/roadmap item per the rules.

## Finding 3 — what does predict hitting, and it's position-specific
Conditions that held in train AND holdout. Critically, **they do not transfer across positions:**

**RB — both hold:**
- **NFL draft capital (pick ≤ 32):** +18.6pp train / +33.3 holdout
- **Receiving involvement (above-median WOPR):** +16.0pp / +8.9

**WR — both hold:**
- **Earned production (last year's PPG not inflated vs expected/opportunity — i.e. not TD-lucky):**
  +15.3pp / +53.9
- **Proven at price (last year's positional finish ≥ this year's positional price):** +16.1pp / +21.2

**The cross-application FAILS, which matters:** draft capital does nothing for WRs (−2.7 / −13.6), and
"proven at price" is *negative* for RBs (−6.8 / −26.7) — RB breakouts routinely come from nowhere, so
demanding proof at RB actively misleads.

**Dose-response (met 0 → all):**
- RB: 0 met → HIT 32%, BUST 28%, median 0.87x · 2 met → HIT 63.2%, median **1.35x**
- WR: 0 met → HIT 22.2%, BUST 33.3%, median 0.80x · 1-2 met → HIT ~60%, BUST ~12%

**Conventional wisdom that FAILED validation** (reported so nobody re-tries them): elite prior volume
(*negative*), week-to-week consistency (*negative*), youth, high snap share, good offense,
prior-season durability. Fading a first-rounder for any of these is unsupported.

## Finding 4 — the 2026 first round, scored
All 15 pass **earned production** — there is no TD-luck in this year's first round (verified: the flag
works; 29 board players carry it, 5 in the top 60 — Henry, Higgins, McConkey, McLaurin, J. Williams —
just none in the top 15). So this year that prereq is a green light for everyone and the
position-specific ones do the separating.

**RBs** (capital ≤32 + receiving involvement):
- **2/2 —** Gibbs (#12, 17% tgt), Bijan (#8, 20%), McCaffrey (#8, 23%), Barkley (#2, 11%), Jeanty (#6, 15%)
- **1/2 —** J. Taylor (#41 ✗), Achane (#84 ✗), Love (#3 ✓, rookie — no usage data yet)
- **0/2 — James Cook** (#63 ✗, 8% target share ✗) — the only first-rounder failing both RB prereqs, at ADP 14.1

**WRs** (earned production + proven at price):
- **2/2 —** Nacua (finished WR1, priced WR1), Smith-Njigba (WR2 → priced WR3), St. Brown (WR3 → priced WR4)
- **1/2 —** Chase (finished WR4, priced WR2), Lamb (WR21, priced WR5, 13 games), Jefferson (WR20, priced WR6)

Nacua's #177 draft capital is *not* a strike — capital doesn't apply to WRs.
Chase, Lamb, and Jefferson are all being priced for a bounce-back rather than a repeat.

---

## Honest limits
- n=145 total (81 RB / 60 WR); holdout cells run 9-17 seasons. The lifts are directional, not precise.
- ~15 conditions × 3 populations were tested, so some survivor is likely chance. What earns belief is
  the holdout + a real mechanism, not the p-value. Finding 1 (the failure-mode split) is a plain
  descriptive fact and is the most robust thing here; the Finding 3 lifts are suggestive.
- "Proven at price" for WR rests on 32/28 seasons. Treat as a tie-breaker, never a veto.

## Usage — proposed, NOT built
1. **Pre-draft study sheet (zero draft-day risk).** Generate this brief for the top ~40 so the read
   happens BEFORE Aug 7. Directly serves "maximize our draft brain."
2. **An advisory PREREQ line in `build_context`** mirroring COHORT HISTORY: for shortlist players,
   which validated prereqs they meet/fail. Advisory only — like the cohort block, it explains and
   breaks ties; it must NEVER re-rank (effect sizes are too small-n).
3. **Extend the method to R2-R5**, where more of the user's picks actually live.
4. **Do NOT** feed any of this into `rank_composite`. Small n + multiple testing = exactly the
   overfitting the L45/L46 work was careful to avoid.
