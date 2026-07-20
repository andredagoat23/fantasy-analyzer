# SESSION HANDOFF — read this first if you're a fresh session

**How to use this file:** read `icm/CONTEXT.md` (the router) first, then this, then the specific docs
below. This captures where the project stands after a long build session and what to do next.
The NEXT TASK is a **Monte Carlo deep-dive** — details + the questions to ask the user are at the bottom.

## What this session shipped (lessons L11–L20 + Sleeper sync)
- **Advisor decision quality (L11–L13):** the **PUNT READ** (punt a deep QB/TE, grab the scarce RB —
  stats-based, `keep_frac`≥0.75 + a scarcer-RB/WR gate); **bench-saturation** (no 4th RB while a WR
  starter is open); **dedicated-before-FLEX**. All enforced in the TOP PICKS ranking (`advisor.py`).
- **Role + data cleanup (L14–L18, frozen pipeline opened by the user):** depth-chart `team_role` +
  `role_lead` + `role_env_ok` (WR1 bump only on an offense that throws — vegas OR pass volume); dropped
  no-team FAs; `p_startable`-gated VALUE tag (killed false "steals" like Metchie); **consensus-outlier**
  demotion (`proj_outlier`, blend toward ECR when our proj ≫ consensus); **bench balance**
  (`_bench_overstacked`); **anti-hallucination** rule (never state a team/role from memory — data only,
  fixed "Metchie is on HOU"). All in `value_board.py` + `advisor.py`; board regenerated.
- **Metrics audit:** every board metric verified correct against a recompute (VOLS, ranks, market,
  risk, Monte-Carlo outputs, team_role/role_lead/role_env_ok/proj_outlier). Fixed a stale composite
  formula in `pipeline.md`.
- **Strategy handling (L20):** value-first, but on a positional-rule conflict the advisor now surfaces
  BOTH — "Best value: X" + "Sticking to your [strategy]: Y" — and a risk-flavored strategy re-weights
  toward ceiling. (Verified live.)
- **Sleeper live sync (new):** `sleeper_sync.py` polls Sleeper's PUBLIC API directly (no userscript/
  Firebase), normalizes to the mailbox `{meta,picks}` shape, reuses `bridge.resolve`. Setup connect UI +
  a `poll_sleeper` fragment. 13 unit tests pass; app boots + UI renders. Coverage now ESPN+Sleeper ≈81%.

## Git / deploy state (IMPORTANT)
- **Pushed/deployed** (Streamlit Cloud auto-deploys `main`): through commit **`6cfe100`** — includes
  L11–L19 + the numpy pin.
- **Committed locally but NOT pushed** (so the DEPLOYED app does NOT have these yet):
  `ea8bc04` (pipeline doc fix), `e798429` (**L20 strategy tuning**), `8eb5d7b` (**Sleeper sync**).
  → When the user is ready, `git push origin main` deploys them.
- **Uncommitted scratch** in `icm/work/`: `sleeper-sync-scope.md`, `yahoo-probe-scope.md`, `diagnosis.md`.

## Verified vs still-pending
- **Pending live verify:** a real **Sleeper mock draft end-to-end** (needs the user's Sleeper
  account/draft_id) — the module + UI are proven, but a live pick-flow run hasn't been done.
- **Pending user UX check:** the L16–L18 + Sleeper batch changed the pipeline/board; a quick smoke of the
  live app is worthwhile before/after pushing.
- **Yahoo:** NOT started. Next platform toward the user's 95%-automated goal (ESPN 48% + Sleeper 33% +
  Yahoo 18%). A **verification probe is scoped** (`yahoo-probe-scope.md`) — do that BEFORE building.

## Reading order to get oriented
`icm/CONTEXT.md` → this file → `icm/reference/pipeline.md` (§`compute_outcomes.py` — Monte Carlo) →
`compute_outcomes.py` itself → `icm/reference/draft-strategy.md` (how the advisor uses floor/ceiling/
p_bust) → `icm/reference/lessons.md` (L11–L20).

---

# NEXT TASK — Monte Carlo deep-dive (the user's priority)

> **STATUS UPDATE (Jul 19, 2026): RESEARCH DONE + WAVE 1 SHIPPED (user-authorized frozen edit).**
> 7 seasons mined (findings: `icm/work/mc-research-findings.md`, scripts: `icm/work/mc_research/`);
> constants backtested (60.3% band coverage vs 60% target; old 41.5%), `compute_outcomes.py`
> recalibrated (depth-dependent SIGMA_ANCHORS, honest availability/p_major/age, games↔per-game
> coupling, draft_tilt refit), pipeline re-run, acceptance tests pass, 13 unit tests pass, app boots.
> Lessons L21–L22 logged. **WAVE 2 ALSO SHIPPED (same session):** team-change tilts (QB/RB/TE),
> stable-RB/TE narrowing, WR30+ fade, CV-blend sigma — each fitted to close subgroup calibration
> gaps and verified to keep global coverage at 59.7% (`09_wave2_validation.py`); late-usage surge
> tested and dropped (noise). Both waves committed locally; push deploys.

The user believes the **Monte Carlo model (`compute_outcomes.py`) could be the best predictor** and
wants to "utilize it to its very highest possibility." **`compute_outcomes.py` is a FROZEN pipeline
file — the user must explicitly authorize edits** (they are inclined to; confirm scope first). Editing
it means re-running the pipeline (`run_all.py`, or just `compute_outcomes.py` → then `value_board.py`).

## What Monte Carlo does today (so you don't re-derive it)
20k simulated seasons/player from 2024–25 weekly scoring: a right-skewed **log-normal** season
multiplier × games-played (bell curve + a 6–30% season-ending-injury tail), centered on the projection.
Outputs: `floor`/`ceiling` (20th/80th pct), `p_elite`/`P_pos1`/`p_startable`/`p_bust` (rank-within-
position finish odds), `availability` (shrunk games-rate − age penalty). Knobs at the top of the file
(`N_SIMS`, `ROLE_RISK`, injury params, BOOM/BUST). Today the advisor uses these as **tiebreakers** +
the risk dial; VALUE is driven by VOLS/VONA (the mean projection), not the distribution.

## Candidate directions to raise (pick with the user — DON'T assume)
1. **Calibration / backtest FIRST (highest value):** is it actually accurate? Backtest vs 2024/2025
   real outcomes — do the 20/80 floor/ceiling bands contain the actual result ~60% of the time? When
   `p_bust`=30%, do ~30% actually bust? If it's not calibrated, tune the model before leaning on it.
2. **Make MC drive VALUE, not just tiebreak:** e.g., a risk-adjusted / floor-weighted / certainty-
   equivalent value that the advisor drafts on — especially tied to the risk dial (safe → weight floor;
   upside → weight ceiling). This is likely what "utilize it to its highest" means — CONFIRM.
3. **Better inputs:** the season multiplier rides on `ROLE_RISK` + weekly CV; could fold in target-share
   trend, Vegas, O-line, coaching/scheme change, landing spot (rookies).
4. **Correlation:** players are simmed independently; QB↔his WR / backfield splits correlate — matters
   for lineup construction more than per-player draft value.
5. **Injury model realism:** the availability + major-injury tail is heuristic; could use real
   position/age injury base rates.
6. **Distribution shape:** the log-normal skew is assumed; could fit it to actual position-level
   outcome distributions.

## Questions to ASK THE USER before building (this is the "what to ask" the handoff owes you)
- **Goal:** do you want to (a) first VALIDATE accuracy (backtest vs real results), (b) make the advisor
  DRAFT on MC (risk-adjusted value, not just tiebreak), (c) improve the model inputs, or some mix?
- **Authorize the frozen edit?** Editing `compute_outcomes.py` + re-running the pipeline — OK to proceed?
- **Risk-dial integration:** should the draft VALUE itself shift with the risk dial (floor-weighted when
  "safe", ceiling-weighted when "upside"), or keep MC as tiebreaker + board-filter only?
- **Ground truth:** is it OK to pull 2024/25 actual season finishes (nflreadpy) to backtest calibration?

**Recommended first step:** propose a **calibration backtest** (read-only, no frozen edit) — it tells us
whether MC is trustworthy enough to lean on, and whatever we learn shapes every other direction. Walk
the user through it and get their "go" (Stage 02) before touching the frozen file.
