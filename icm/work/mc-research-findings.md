# Monte Carlo Deep-Dive — Research Findings (2019–2025, 7 seasons of real data)

**What this is:** the evidence base for upgrading `compute_outcomes.py` (frozen — no edits made).
Every claim below was computed from real nflreadpy data + historical preseason ADP/ECR, scored
under OUR league rules. Scripts + raw outputs live in `icm/work/mc_research/` (rerunnable).

**Method in one paragraph:** for every fantasy-relevant player-season 2019–2025 we know what the
market expected preseason (FFC ADP 2019–24 + FantasyPros ECR archive 2021–25 → positional rank →
expected points via the historical rank→points curve) and what actually happened (weekly stats under
league scoring). The ratio `actual / expected` = the **season multiplier** — the exact quantity MC's
lognormal × games machinery simulates. 1,454 player-seasons with expectations; sanity-checked against
known seasons (Kupp '21 = 2.13×, Puka '23 = 4.82×, Javonte '22 ACL = 0.20×).

---

## Verdict on today's MC: right skeleton, wrong widths

**What it gets RIGHT (keep):**
- Lognormal-family upside + a separate catastrophic-injury branch — correct structure.
- Mid-tier finish odds (ranks 7–24) are close to reality (e.g. WR13–24 top-12 odds: MC .206 vs
  real .214; RB7–12: .476 vs .561).
- Rookie draft-capital tilt — direction confirmed (top-32 rookies beat market expectation,
  median mult 1.10–1.20).
- Catastrophic branch games-played: U(0,8)→mean 4 vs empirical mean 5.3, median 6 — close, minor tweak.

**What it gets WRONG (the gains):**

### 1. Distributions are far too narrow — and uniformly so (BIGGEST FIX)
MC's 20/80 band is ~[0.70, 1.28]× projection for nearly everyone (band ratio 1.6–1.9, flat across
tiers). Reality: only elite tiers are that tight; variance GROWS with rank depth:

| tier (pos rank) | empirical p80/p20 band ratio | MC today |
|---|---|---|
| 1–12 | 1.6–1.9 ✔ | 1.6–1.8 |
| 13–24 | 1.7–1.9 | 1.6–1.7 |
| 25–40 | **2.2–3.3** | 1.7–1.9 |
| 41–60 | **2.5–3.7** (QB inflated by backups) | 1.8–2.1 |

Right-tail proof: P(actual ≥ 1.5× expectation) = **12–18%** by position; MC's σ≈.25 implies **4%**.
P(≥2.0×) = 1–7% real vs 0.2% modeled. Booms are ~4× more common than MC simulates.
- Empirical σ of ln(mult) by pos×tier (the calibration targets, `results_05_distribution.txt`):
  QB1–6 .32, WR1–6 .45, TE1–6 .37, RB1–6 .70; mid tiers ~.4–.8; deep tiers ~.6–1.0.
- **Knob:** replace flat `ROLE_RISK=0.20` with a **rank-depth-dependent sigma** per position
  (interpolate the empirical table; raise the .60 clip).

### 2. Elite RBs are ~4× riskier than MC claims; late QB/TE upside is real (PUNT READ vindicated)
- RB ranked 1–3 preseason: MC says 6% bust; **empirically 24% bust**, only 52% finish top-12.
  (Elite-RB σ .70 vs WR .45 — RBs deserve their own wider elite risk.)
- QB/TE ranked 25–40: MC says 0.6–4% startable; **empirically 11–14%**. The deep-QB/TE punt the
  advisor already plays (L11) has 7 years of data behind it — MC just can't see it today.

### 3. Availability constants are miscalibrated (all positions ≈ equal, ~83%)
True starters (QB≤18/RB≤36/WR≤42/TE≤14 preseason) play:
**QB .845, WR .841, TE .828, RB .817** of games — vs MC's AVAIL_PRIOR RB .86 / WR .92 / TE .91 / QB .94.
QBs get hurt like everyone else; MC's spread is fiction.
- P(catastrophic, 9+ missed): QB .103, RB .108, WR .089, TE .071 — MC's 6% floor is low,
  its 30% cap is unreachable in reality.
- **"Injury-prone" barely exists among starters:** prior 3+ missed games → miss4+ rises only
  29%→33%, played-frac .838→.804. One bad year should barely move availability
  (current shrinkage AVAIL_K=2 is directionally right — make the prior even stronger).
- Injury TYPE doesn't predict next season (ankle .367 vs hamstring .294 miss4 — spread of 7pp, n small).
- **Knobs:** `AVAIL_PRIOR` → {QB .845, RB .817, WR .841, TE .828}; `p_major` → position base
  {QB .103, RB .108, WR .089, TE .071} with mild (±.02) prior-injury adjustment, cap ~.15;
  catastrophic games U(0,8) → U(1,8) (empirical mean 5.3).

### 4. Injuries hurt TWICE — games AND per-game (MC sims them independently)
Players who miss 4–8 games are also **7–11% worse per game** when active; 9+ missed → **~20% worse**
(per-game mult median .79–.81). corr(games played, per-game outcome) = +0.29, and 22% of total
outcome variance is this covariance term. This is why real outcomes have a much fatter left tail
than lognormal (ln-space skew −1.6 to −2.6).
- **Knob (new mechanism):** couple the sims — e.g. `per_game_eff = per_game × (1 − 0.35·(1 − games/17))`
  reproduces the observed medians. One line inside the sim loop.

### 5. Situational tilts the data supports (smaller, optional wave 2)
- **Team-changers (QB/RB/TE) bust hard:** bust rate 38–40% vs 24–27% for stayers; median mult
  .84–.94. WRs unaffected. → widen sigma and/or small negative mean tilt for position-switchers.
- **WR age arc:** ≤27 boom rate 25–30%, 30–31 only 15%, and 32+ availability craters (.735
  played, 23% catastrophic). RB cliff at 30–31 (.716 played, 47% miss4). MC's age penalty exists
  but only touches availability — the boom-rate fade is separate.
- **Vegas implied total is the strongest weekly boom lever:** QB boom rate 9%→48% from <17 to 26+
  implied points (WR 5→16%, RB 9→23%, TE 5→17%). Already used in the composite's ceiling term —
  validated; could also tilt season sigma slightly toward high-total offenses.
- **Rookie tilts:** top-32 picks median mult 1.10–1.20 (current tilt 1.04–1.08 — could go up);
  3rd-rounders median 0.78 (current 0.97 — too generous); 4th+ high-variance (median .97, p80 1.68).
  Rookie σ wider for QB/RB (×1.5) — current ROOKIE_ROLE_RISK idea confirmed; WR rookies actually
  BEAT expectations (median 1.17) — the market, not variance, is the story there.
- **Late-season target-share surge** (WR/TE): +7pp boom rate top vs bottom tercile — real but modest.
- **"Year-2 breakout" is a myth vs market:** year-2 WRs boom LESS (21.5%) than rookies (37.8%).

## Honest caveats
- Multipliers are measured vs MARKET expectation (ADP/ECR-implied), not vs FantasyPros point
  projections; the two are near-equivalent in accuracy, but MC sims around OUR projection —
  treat σ targets as strong anchors, not gospel to the 3rd decimal.
- QB 41–60 rows are backup-contaminated (benching ≠ injury) — starter-pool numbers used for all
  availability claims; deep-QB sigma (1.69) should be clipped, not copied.
- K excluded from research (low draft value, noisy). 2020 COVID season included; excluding it
  doesn't change conclusions materially (spot-checked).
- Sample sizes: pos×tier cells are n≈40–140 — plenty for rates, thin for 3-decimal precision.

## ✅ WAVE 1 APPLIED (Jul 19, 2026 — user-authorized)
Robustness pass first (`07_robustness.py`): era-split stable, 2020-exclusion negligible,
outlier-robust sigma anchors derived (per-GAME sigma for M — totals would double-count games
variance). Then the full proposed machinery was **backtested on 1,454 historical player-seasons
BEFORE the edit** (`08_backtest_sim.py`): **20/80 coverage 60.3% (target 60%), boom 15.0% predicted
vs 15.3% realized** — old constants scored 41.5% / 7.0%. `compute_outcomes.py` edited (sigma anchors
+ rookie multipliers, availability/p_major/age recalibration, U(1,8) lost seasons, games↔per-game
coupling 0.41, exact mean re-centering, draft_tilt refit); pipeline re-run; acceptance tests
(`05`/`06` vs the new board) land on the empirical tables; 13 unit tests pass; app boots and renders.
Per-player CV personalization of sigma was REMOVED (unvalidated) — Wave-2 candidate alongside the
team-change/WR-age tilts. Note: live-board deep-QB odds stay below history because 2026 projections
rate deep QBs low — projection input, not sim miscalibration.

## ✅ WAVE 2 APPLIED (Jul 19, 2026)
Each candidate measured for RESIDUAL calibration gaps under Wave-1 machinery, minimal tilts fitted,
subgroup + global calibration re-verified (`09_wave2_validation.py`). **Shipped:** team-change
tilts (QB .97/σ1.40, RB .94, TE .95/σ1.15 — changer bust gaps closed from ~+11pp to ~±1pp),
stable-RB/TE narrowing (σ×.85), WR30+ fade (tilt .98, σ×.70 — conservative; n=53 residual within
noise), CV blend (σ×[.8–1.3] by relative volatility — closed both tercile gaps). **Dropped:**
late-usage surge (calibrated already under Wave-1 = noise). Global coverage after Wave 2: 59.7%
(target 60), boom .145 pred vs .153 real. Known residual: RB/TE stayers' bust ~7pp overpredicted —
structural (games-machinery); stayers empirically get MORE 9+-game injuries than changers
(selection effect), so the lever isn't availability. Implementation detail: flags computed in
`compute_outcomes.py` from 2025 last-team (LA→LAR) vs current team; `team_2025` intermediate NOT
persisted (collides with `load_ff_opportunity.py`'s own merge).

## Original proposal (kept for the record — now implemented)
Wave 1 (the calibration fixes, ~30 lines in `compute_outcomes.py`):
1. Depth-dependent sigma table (finding 1) — replaces flat ROLE_RISK for vets.
2. AVAIL_PRIOR + p_major recalibration (finding 3).
3. Games↔per-game coupling (finding 4).
Then re-run pipeline → **acceptance test: rerun `05_distribution.py` + `06_finish_odds.py`** —
the new board's bands/odds should land on the empirical tables. That's the "calibrated" proof.

Wave 2 (situational tilts, finding 5) — after Wave 1 validates, so effects don't confound.

Downstream effects to expect: elite-RB p_bust rises to honest ~20%; late QB/TE p_startable
becomes nonzero (strengthens PUNT READ); ceilings for rounds 6–12 players rise (more real VALUE
flags on upside picks); the risk dial gets meaningfully wider bands to work with.
