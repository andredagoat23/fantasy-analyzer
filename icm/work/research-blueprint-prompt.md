# RESEARCH CHARTER — "ENTANGLEMENT": A Situation-Aware, Position-Specific Fantasy Prediction System

**For:** Fable 5 Ultracode (multi-agent deep research)
**Repo:** `/Users/natearaskog/fantasy-analyzer` (Python, Streamlit, git, branch `main`)
**Deliverable:** a Blueprint — a written, evidence-graded design for a system that predicts FANTASY outcomes from situation + usage, per position, pre-season and in-season, fused with the existing stack. Plus a 2026-season live test protocol.
**Date context:** charter written 2026-07-31. League draft 2026-08-07. Code freeze 2026-08-03.

This charter has been through four adversarial reviews (redundancy, feasibility, rigor, fantasy-specificity), each of which ran code against this repo. Numbers below marked **[V]** were verified by executing against the repo or a live endpoint on 2026-07-31. Numbers marked **[R]** are recalled from prior results files and have NOT been re-run. Hold yourself to the same labelling.

---

## 0. READ THIS BEFORE YOU DO ANYTHING ELSE

### 0.1 The origin of this request, in the user's own words

The user watched a video about "entanglement" in the NFL — the idea that a player's output is inseparable from his situation. The motivating case is Saquon Barkley: same player, New York vs Philadelphia, wildly different fantasy output. His questions, verbatim in intent:

1. Is a step change actually unpredictable, or are there signs? (He specifically floated niche ideas like offseason workout reports.)
2. How do you detect a step change **in season**, as fast as possible?
3. Can we build a system, **per position**, that uses "every statistic, every news article, every change" to make the best possible fantasy predictions?
4. He is explicit: **"we're not just predicting football, we're predicting fantasy."**
5. He accepts that beating the market pre-draft is hard. The system does **not** have to beat ADP pre-draft to be valuable.
6. It must **fuse with what already exists** in the repo, not replace it.
7. He may not use it this season, but he wants to **test it on 2026** to see how accurate it truly is.

Answer these with evidence, not with enthusiasm.

### 0.2 The non-negotiable methodological standard

This project has a documented history of beautiful findings that turned out to be worth nothing. The standard below is scar tissue from three killed research lines plus four adversarial reviews of this charter. Violate it and your entire output is discarded.

**S1. Lift is not points.** A condition that raised "share of players who beat their draft price" by 10–25 percentage points bought **+5.2 points on a ~1,600-point roster** [R] when graded on actual season points. Never grade a finding on the metric you derived it from. Grade on **actual season fantasy points scored by a set lineup, in paired drafts** where only your decisions differ (same seed, same opponents, same board).

**S2. A bootstrap cannot tell you your sample was not a lucky slice.** Only replication in data the finding was **not discovered in** can. Canonical failure: a rule measured +42.3pp with bootstrap P=1.00 on n=38, then reversed to −14.0pp on n=88 in a different band, and evaporated when one cutoff moved from top-32 to top-64. **Every scan survivor is a HYPOTHESIS until re-tested in a band, era, or position it was not found in.** Every hypothesis must name its **discovery slice** and its **replication slice** in the pre-registration BEFORE the discovery run. The replication slice must differ on at least one of: era, ADP band, position, format. **A hypothesis with no out-of-slice replication is capped at DIRECTIONAL-ONLY in the verdict table regardless of its points number.**

**S3. Run the sensitivity sweep, and report it.** Scale any proposed nudge at 0.0× / 0.5× / 1× / 2× / 4×. 0.0× must return exactly zero.
- **PASS shapes:** monotone rise (real signal, under-applied — raise the magnitude and re-grade), or **rise-then-fall with the peak at or above 1×** (real signal, correctly scaled).
- **FAIL shapes:** flat, monotone decline, or a peak below 0.5× (the fitted magnitude is below the noise floor).
- The observed FAIL pattern last time was +8.8 / −0.7 / −21.0 / −59.5 [R]. That is a null about the RULES, not the knob.

**S4. ADP is a strong baseline and draft variance dwarfs any effect you will find.** In the harsh backtest 95% of drafts landed between −318 and +319 points [R] — though note S11: part of that spread is simulator artifact from a misspecified opponent model. Deviating from ADP on a weak signal costs more than the signal gains. State every claimed edge with a paired-difference confidence interval, a win-rate, and a per-season breakdown — never a single mean.

**S5. Measure prevalence under the ACTUAL decision policy.** A feature was once built because an opportunity appeared 8.1% of the time — measured with the simulator drafting by ADP, while the real advisor drafts by value. Under the real policy the state occurred **zero times in 552 decision points** [R]. Prevalence measured under the wrong policy is *worse* than no measurement, because it looks like evidence. **Apply this to your own instruments, not only to the features you test** — three of the four reviews of this charter found S5 violated by the charter's own grader.

**S6. Validate the DIRECTION of advice, not just the size of a coefficient.** Advisory prose is still a claim. A shipped, "advisory-only" read once told the model "act before your wheel" — and the direction was backwards.

**S7. Hunt for leakage in anything averaged over the season you are predicting.** A family of "good offense" gates died when season-averaged Vegas implied totals turned out to drift toward the player's own outcome; clean week-1–2 totals killed the effect. Two seasons were excluded from another study because that source's "projections" were backfilled, not forecasts.

**S8. Check for schema drift and format mixing before trusting any split.** nflverse injury files pre-2025 have no `season_type` column, so a filter on it silently NaN-dropped six seasons. Pooling superflex with one-QB drafts produced a confidently WRONG first-pass answer. **After any multi-year concat, assert per-year row counts and group-by-season means before analyzing anything.** Two live instances in this charter: `load_depth_charts` has zero overlapping column names between its 2019/2023 schema and its 2025/2026 schema [V]; the pbp `route` vocabulary changed between 2022 and 2024 [V].

**S9. A mispricing you cannot reach is not an edge.** Even a genuinely underpriced player must survive to one of this roster's actual picks in a 12-team snake. Report reachability before investing in any pre-draft signal.

**S10. Honest negative results are first-class deliverables.** See §10.9. "This does not work, here is the measurement" is a shipped result here and is rewarded.

**S11. Cluster your confidence intervals on the unit at which the treatment is assigned, and report the cluster count as the effective n.**
- Paired drafts → cluster on **SEASON**. Recomputed from `icm/work/mc_research/results_33_harsh_backtest.txt`: per-season means −55.4, −30.8, +66.7, +67.8, +10.7, −77.8, −9.9, +15.4, +36.9, +28.7; season-mean SD **48.9**; clustered SE with 10 seasons **15.5**; so "+5.2" has t = 0.34 and a 95% CI of roughly **[−30, +40]** [V, recomputed by review]. A naive bootstrap over 2,500 individual drafts gives SE ≈ 3.2 and would render +25 an apparent 8σ result. That bootstrap is wrong — paired differences inside a season share one realized season of player outcomes.
- Regime change → cluster on **team-season**. Playcaller carryover → cluster on **coach-move**. Coaching tendency → cluster on **coach**. In-season detection → cluster on **EVENT** (and block over weeks for lead time), never on player-weeks.
- **The n<40 directional-only floor applies to CLUSTERS, not rows.** Report both.
- **Minimum detectable effect at 80% power:** ≈ +45 points with 10 seasons, ≈ +90–100 with 4. Any threshold below the MDE of the instrument you actually built is a threshold you cannot honestly test. Say so and report DIRECTIONAL-ONLY rather than PASS.

**S12. Grade in LEAGUE scoring, not base PPR.** The research panel `icm/work/mc_research/seasons.parquet` is built at `icm/work/mc_research/01_build_panel.py:38-43` from base PPR only — no first downs, no sacks, no fumbles, no 40+/50+ cumulative TD bonuses, no 100/200/300/400 yardage tiers, no 2pt, no returns [V]. Measured on `players_final.csv`, mean `bonus_points` for the top 12 by `total_points`: **RB +64.2 (18.9% of total), WR +34.9 (11.5%), TE +24.8 (11.9%), QB −8.9 (−2.5%)** [V]. An instrument blind to that cannot grade the workstream the charter itself nominates as highest-EV. Build the league-scored panel (T0.3) before you grade anything, and report every headline number in **both** currencies.

**S13. Grep before you propose.** For every hypothesis, search the repo for the quantity it proposes to add and state in one line what already computes it. Three of this charter's original hypotheses proposed building features that already ship. The failure mode is symmetric with S5: a rebuilt feature graded against a board that already prices it returns a **false null on a real edge**, which then gets recorded as a closed line.

**S14. One primary endpoint per hypothesis, declared before running. No OR-thresholds.** Every other measure is secondary and is reported as secondary. "Or fixes a named failure mode" clauses are only admissible if the failure mode is **named, reproduced, and its prevalence measured under the real advisor policy BEFORE the points test runs**, and the points number is reported regardless. A failure mode named after a failed points test is inadmissible. Count your hypotheses, print the count in the verdict table, apply **Benjamini-Hochberg FDR at q = 0.10 across all primary endpoints**, and print both raw and adjusted verdicts.

**S15. Calibrate your thresholds against a placebo before you trust them.** See T0.6. **Every points threshold stated in §8 is PROVISIONAL until the placebo distribution exists.** The 95th percentile of the placebo distribution is the real bar.

### 0.3 CLOSED LINES — do not re-open, do not re-derive, do not "improve"

These were measured, in this repo, on real data, and killed. Re-litigating any is wasted budget and will be rejected. Where a **surviving fragment** is noted, that fragment is live knowledge you may build on.

| # | Line | Why it died | Evidence |
|---|---|---|---|
| C1 | **Positional-run momentum ("HOT")** | DISPROVEN. Slot-matched baselines at the conditioned slots: 1QB RB −2.9pp / WR +0.6 / QB +1.5 / TE −3.0; superflex RB −1.0pp on 9,200 windows. Dose-response does not rescue it (superflex RB +12.2pp at k=3, n=38, then −1.0 at k=5, n=6,799). Branch deleted; `tests/test_cold.py` guards its return. | 1,162 completed 2026 12-team drafts, 372,394 picks; `icm/work/run-dynamics-findings.md` |
| C2 | **1-start depletion as an actionable counter-hypothesis** | Directionally real, too small to act on (+2.5pp). Kills the "restrict run flags to RB/WR" fix. | Same corpus |
| C3 | **Per-player draft PREREQUISITES as a drafting rule** (~15 conditions × 5 ADP bands) | Lifts were real (10–25pp). Points were not: **+5.2 mean**, wins 51.5% / loses 48.0%, helped 6 of 10 seasons; sensitivity sweep worse than null. Friendliest possible test (in-sample) and it still failed. | 2,500 paired drafts 2015–2024; `33_harsh_backtest.py`; L49 |
| C4 | **"Draft capital matters exactly when the player has no usage data"** (+42.3pp) | FAILED REPLICATION, retracted. Reversed to −14.0pp in another band on 2× the sample; collapsed to +0.8 when the cutoff moved 32→64. **Surviving fragment:** capital is near-inert for a player who ALREADY has a role — "don't fade an established-role player for a late draft slot" stands. | `31_r4r6_deep.py` |
| C5 | **"Upgrade a weak starter"** | Built, measured, reverted unshipped. The state cannot arise: across 552 post-lineup decision points the best available at a filled position never beat the incumbent by the threshold (max −0.4 VOLS, median −25.4). 1,200 paired drafts: **100.0% identical.** | `42_upgrade_backtest.py`; L50 |
| C6 | **Per-position projection BIAS correction** | Bias real (ESPN ratios QB 1.15 / RB 1.17 / WR 1.24 / TE 1.13) but factors unstable season-to-season. OOS **−8.2 pts**, corrected wins 14%. In-sample ceiling −19.5. **Surviving seam:** the bias was only ever tested on the PLAYER side, never at the REPLACEMENT tier — see H5f. | 600 paired drafts; `34_`/`35_` |
| C7 | **Cross-positional dependencies as a matching feature** | NULL vs price, and worse — the market OVERPRICES teammate quality. Receivers of top-tercile QBs boom LESS (22% vs 26%; WR-only 18% vs 26%). QB-behind-bad-OL positive was confounded by scramblers. Only whisper: TE with elite QB (med 1.05 vs 0.93). | ~300+ player-seasons/tercile on a 2,227-row 12-season pool; `10_crosspos.py` |
| C8 | **Per-position COMPOSITE WEIGHTS** | Tested and rejected — within a position, ADP dominates and per-position weights add nothing. | `19_position_weights.py` |
| C9 | **Career mileage / "the curse of 370"** | Collapses under survivorship control. Holding price fixed, high-mileage RBs did slightly BETTER (ADP 1–40: 58.3% vs 54.4%; 41–90: 55.6% vs 47.8%). **Surviving fragment:** a back coming off a 350+ touch season hit 22.2% (n=18) vs 53.9%. n=18 — directional only. | `29_mileage_and_availability.py` |
| C10 | **Popular AVAILABILITY tells** ("played 16+ last year", "no injury history", "big backs hold up", "he's young") | All null or NEGATIVE on train AND holdout vs a 58.6% base rate. Big backs (≥215 lbs) **−16.0 / −21.1pp**. **Surviving fragments:** light prior workload (+15.4 / +8.3) and position (WR 66.7% vs RB 51.9%). | n=145 first-rounders + holdout; `24_`, `25_` |
| C11 | **Late-round folk wisdom** (dart score; "good offense" gates; bell-cow handcuff logic; rushing-QB late edge; year-2 WR breakout; share signals finding league-winners) | Each died differently. The dart score validated in-sample then FAILED the 2022–25 holdout — plain ADP order caught 6 of 9 holdout league-winners, the score caught 2. "Good offense" gates were a **data leak**. Share signals buy STARTABLE WEEKS, never league-winners (holdout slope p=.88). | 3,329 late player-seasons + 289 handcuff cases 2014–2025; `icm/reference/late-round-strategy.md` |
| C12 | **"Deepen the QB replacement baseline"** | The obvious pipeline fix BACKFIRES — it raises elite-QB VOLS, the opposite of intent. The number was never wrong; the defect was a horizon artifact in the decision layer, resolved with zero frozen-file edits. **Replacement stays QB12 (`utils.py:58 FIXED_STARTERS`) [V].** | L11 |
| C13 | **"The advisor taking Josh Allen at R3 is a bug"** | Reproduced and REFUTED. Allen VONA 50.7 vs best RB 13.3; higher risk-adjusted VOLS, higher ceiling, LOWEST cohort bust. **Trap:** do not read "low variance" as "low ceiling" — upside multipliers measure spread *relative to price*. | L28 |
| C14 | **WR and TE handcuffs; handcuffing behind BENCH players** | Scope-corrected by measurement. 281 team-seasons where a starter missed 3+ games: backup RB 4.0→9.5 ppg (2.25×, 56% gain 5+ ppg); WR only 7.2→8.6 (1.17×); TE 2.3→4.8 (still below streaming). Handcuffing is **RB-only, behind an actual starter.** Promoted TE backups boom **4.5% (p=5.5e-6)** — the one absolute fade. | L30, L31 |
| C15 | **"Buy BOTH receivers from an ambiguous room"** | BROKEN for WR (same-team WRs correlate +0.12 — redundant), UPHELD for RB (anti-correlate −0.28 — carries are a one-winner pie). | L35 |
| C16 | **Player-specific injury-proneness and injury-TYPE recurrence** | Barely exists among starters. Prior 3+ missed games moves next-year miss4+ only 29%→33%. Games-played YoY correlation **r = +0.019**. Players who missed badly (≤10 games) played 15+ the next year **57.1%** — better than the healthy group's 53.2%. **This is the project's single most-replicated negative.** | 764 starter seasons + n=145; L21, L49 |
| C17 | **Blend reweighting away from FP 0.35 / ESPN 0.65** | Half-closed. Direction generalises (+83 pooled, P(>0)=1.00) but the best weight per season is 0.0/0.1/0.0/0.6 — fitting a 4-season sample. On the 2026 board the three sources correlate **+0.964 to +0.987 over the top 180**. Standing instruction: **do not touch `scoring_config` before the draft.** | `37_`–`41_` |
| C18 | **Late-season target-share surge tilt; per-player CV personalization at full strength** | Surge already calibrated under existing machinery; residual was noise. CV survives only as a bounded blend clipped to [0.80, 1.30]. | `09_wave2_validation.py` |
| C19 | **ESPN editorial PPR rank as a board input** | Interrogated, not implemented — it lowballs TE scarcity worse than the ADP already in use. | memory note |

**Four closed lines are directly load-bearing and you must internalize them:**

- **C7 is the cleanest "situation is already priced" result in the project.** QB quality → pass-catcher outcomes is NULL vs price and the market *overpays* for supporting cast. Your entanglement research starts from a repo where the most obvious entanglement hypothesis has already been tested and rejected.
- **C3 is the governing precedent for this entire charter.** Find a condition, measure lift vs price — that exact shape has already run to completion here and died in the paired-draft backtest. **If your workstreams produce lift tables, you have reproduced a known failure.**
- **C12 governs every QB proposal.** Any proposal that changes what "replacement" means at QB is out of scope. Say so and stop.
- **C16 governs every availability-forecast proposal.** Player-level durability forecasting is the most-replicated null in this repo. Availability FACTS (a current designation) are a different object from availability FORECASTS and route differently (§8 WS6).

**C8 note for WS4:** C8 killed per-position composite *weights*. WS4 proposes per-position *model shape*. Your first paragraph in WS4 must state why the C8 null does not transfer, or abandon the workstream.

### 0.4 The hard boundary

**Never edit the frozen pipeline scoring files:** `custom_scoring.py`, `compute_metrics.py`, `compute_outcomes.py`, `apply_bonuses.py`, and the rest of the `run_all.py` chain. If a fix appears to require them, that is a data-quality flag to raise, not a silent edit. Your deliverable is a **Blueprint** — proposals, evidence, and standalone research scripts under `icm/work/`. Nothing ships into the live board without the user's explicit approval, after Aug 7.

### 0.5 Timing, and the two pre-Aug-3 exceptions

Code freeze **Aug 3**. Draft **Aug 7**. **This is post-draft work.** Do not propose shipping anything into the live app before the draft.

**Two read-only exceptions are not just permitted but URGENT, because their windows close permanently:**

1. **Run `tools/archive_projections.py` before Week 1** and verify it wrote a dated CSV with >400 rows into `data/projection_archive/` (which currently contains only a subdirectory listing). Historical FantasyPros projections are **permanently unreconstructable** (§3.3); this script is the only forward fix, and it is read-only — running it is not shipping.
2. **Re-run the Sleeper mock corpus in early August** via `icm/work/mc_research/21_sleeper_run_corpus.py`. The crawler exists, is rate-limit aware, and the 1QB sample under the entire survival stack is **111 drafts** — the thinnest input in the system. Read-only.

Assume the Blueprint itself is read and acted on *after* the draft, with the 2026 season as a live holdout.

---

## 1. REPO ORIENTATION

### 1.1 What this is

A single-page **Streamlit** app (`app.py`) running the user's personal draft board during a live ESPN snake draft. **12-team, custom-scoring PPR, single user, no auth.** v1.0 was a math-based recommender reading `value_board.csv`; v1.1 added a Claude advisor; a live-draft bridge syncs ESPN and Sleeper picks. Deploys to Streamlit Community Cloud on push to `main`.

The user is 14, has taken AP CSP, has solid CS fundamentals, and is newer to Python and APIs. Explain new concepts and Python-specific quirks; do not over-explain fundamentals.

### 1.2 The methodology workspace (ICM)

`icm/` governs how work is done. **Read `icm/CONTEXT.md` first** — it is the router. Then:

- `icm/reference/engineering-principles.md` — non-negotiables
- `icm/reference/collaboration.md` — how to communicate with this user
- `icm/reference/lessons.md` — the numbered lesson log (L1…L55). The most valuable file in the repo.
- `icm/reference/pipeline.md` — script chain, frozen-file boundary, data traps
- `icm/reference/architecture.md`, `draft-strategy.md`, `late-round-strategy.md`, `bridge.md`, `spec.md`
- `icm/work/` — scratch, plus finished write-ups: `mc-research-findings.md`, `r1-prerequisites-findings.md`, `run-dynamics-findings.md`, `HANDOFF.md`
- `icm/work/mc_research/` — **45 numbered scripts (`00_`–`45_`) with matching `results_*.txt`** [V]. Your library of prior art and method templates. Read the results files before proposing anything adjacent.

**Documentation drift warning:** `icm/reference/pipeline.md` still prints the PRE-L45 composite weights. The live code is authoritative.

### 1.3 Pipeline chain (frozen — read, do not edit)

`run_all.py` orchestrates: `players.py` → `filter_active.py` → `load_player_stats.py` → `load_espn_adp.py` → `load_espn_projections.py` → `load_fp_projections.py` → `projections.py` → `apply_bonuses.py` → `blend_vegas.py` → `load_ecr.py` → `load_ff_opportunity.py` → `compute_metrics.py` → `compute_outcomes.py` → `value_board.py` → `value_board.csv`.

Side artifacts NOT in `run_all`, requiring manual rerun after every board rebuild: `role_priors.py` (→`role_data.csv`), `cohort_priors.py` (→`cohort_data.csv`), `sos_priors.py` (→`sos_data.csv`), `load_dst.py` (→`data/dst_rankings.csv`). If these drift, DART/HANDCUFF/COHORT reads silently degrade.

Decision layer (NOT frozen, change only with evidence): `advisor.py`, `app_pages/draft.py`, `cohort_pull.py`.

Tests: `tests/` — 18 suites, 339 checks (`test_cold`, `test_dart`, `test_punt`, `test_wheel`, `test_handcuff`, `test_hedge`, `test_shape`, `test_defer`, `test_opponent`, `test_schedule`, …).

**Deployment constraint that gates every idea in this charter:** the deployed app's `requirements.txt` contains only `streamlit, pandas, numpy, anthropic, espn-api, Authlib`. **`nflreadpy` is NOT installed on Streamlit Cloud** (it lives in local-only `requirements-pipeline.txt`). **No nflverse-derived feature can be computed at runtime.** Every new source must be reduced to a **committed CSV** (the pattern already used by `cohort_data.csv`, `role_data.csv`, `sos_data.csv`, `data/dst_rankings.csv`) and regenerated locally before a push. The only live sources the deployed app can reach are Sleeper's public API, ESPN's public endpoints, and the Firebase mailbox.

---

## 2. WHAT THE CURRENT SYSTEM ALREADY MODELS

You must fuse with this, not duplicate it (S13). Read the actual code; this is orientation, not a substitute.

### 2.1 The projection backbone

`total_points` = **0.5 × Vegas-derived total + 0.5 × (FantasyPros+ESPN component consensus scored through league scoring + bonuses)**. Underneath, `PROJ_W_FP, PROJ_W_ESPN = 0.35, 0.65` in `scoring_config.py`. This is the mean of every Monte Carlo sim and the basis of VOLS, `team_role`, `role_lead`, `repl_pts`.

**Admitted weakness:** 0.35/0.65 is a *preference* ("lean ESPN — it's the room the draft runs in"), not a fit. `BLEND = 0.5` for Vegas is likewise judgment. Historical FantasyPros projections are **permanently unreconstructable**, so this weight cannot be validated retrospectively at any price.

### 2.2 The composite (`value_board.py`, live weights)

`rank_composite` = W_V 0.32 (VOLS rank) + W_UP 0.25 (ceiling_healthy − replacement, × team_env) + W_DN 0.15 (floor_healthy − replacement) + W_E 0.13 (ECR) + W_R 0.09 (role_pct) + W_A 0.06 (ADP).

Plus: `ROOKIE_MKT = 0.5` (rookie composite blended halfway to market — 117 of 536 board players); `CONSENSUS_GAP = 100 / CONSENSUS_ECR = 0.6` (a non-rookie whose projection ranks >100 spots better than ECR gets pulled 60% to ECR and flagged `proj_outlier` — 56 players, **all dropped from what the advisor can see**).

**L45 note:** these weights came from a 13-season LOSO-CV backtest (composite Spearman 0.430 vs ADP-only 0.323), taken **halfway** to the LOSO optimum. The backtest **could not judge VOLS** (its value proxy is backward-looking, our VOLS is a forward projection), so the largest weight in the composite is the one weight cross-validation explicitly did not validate. **The board already IS distributional:** ceiling (0.25) + floor (0.15) = 40% of the composite, and L45 measured raising them (.13→.25, .09→.15) as worth +0.033 generalizable Spearman.

### 2.3 The Monte Carlo (`compute_outcomes.py` — FROZEN)

`N_SIMS = 20000`, `GAMES = 17`, seed 0. `sims = games × couple × lognormal(M)`, re-centred so `E[sims] = projection × tilt`.

- **Depth-dependent sigma** (`SIGMA_ANCHORS`, interpolated): QB (3,.235)→(50,.45); RB (3,.334)→(50,.491); WR (3,.240)→(50,.351); TE (3,.305)→(50,.504); K flat .350 (**explicitly "not researched — flat mid value"**).
- **Availability prior + shrinkage:** `AVAIL_PRIOR = {RB .817, WR .841, TE .828, QB .845, K .97}`, `AVAIL_K = 4.0`. **228 of 536 board players have no availability estimate** and take the flat prior.
- **Age penalty:** `AGE_CLIFF = {RB 29, WR 29, TE 29, QB 99, K 34}`, `AGE_SLOPE = {RB .035, WR .025, TE .030, QB 0, K .010}`.
- **Season-tanking tail:** `P_MAJOR_POS = {QB .103, RB .108, WR .089, TE .071}`; a "major" sim plays U(1,8) games.
- **Games↔per-game coupling:** `COUPLE = 0.41`, floor 0.55 (empirical corr +0.29; 22% of outcome variance is this covariance term).
- **Rookie capital tilt:** pick ≤15 → 1.10, ≤32 → 1.08, ≤64 → 1.00, ≤105 → 0.92 (third-round dead zone), else 0.95.
- **Wave-2 team-change tilts (non-rookies):** QB changer ×0.97 σ×1.40; RB changer AND unproven ×0.86 σ×1.20 (**a proven RB mover gets no penalty**); RB stayer σ×0.85; TE changer ×0.95 σ×1.15; WR age ≥30 ×0.98 σ×0.70.
- **Wave-2b measured splits [R]** (`compute_outcomes.py` ~lines 164–189): proven producers who moved bust 30% / median 1.01; unproven backs handed a new chance bust 52% / median 0.64; market-perceived-upgrade movers bust MORE (44%). **This is a shipped control, not an open question — see WS1.**
- **New-HC tilt (stayers only, QB/RB/WR):** ×1.02, σ×0.85, from `VERIFIED_NEW_HC_2026` (10 teams).
- **Relative weekly volatility:** σ × clip(1 + 0.30×(cv_rel − 1), 0.80, 1.30).

**Calibration status:** proven out-of-sample. On 2014–2018 (five seasons the constants never saw) band coverage was **62.1%** vs a 60% target, against fit-era 60.7–61.2%. Boom prediction .145 vs realized .153. **Known residual: RB/TE stayers' bust is ~7pp over-predicted.** Two standing stress-suite failures on cohort calibration (boom max |pred−real| 0.179, bust 0.087, against a <0.08 bar).

**Admitted weakness:** sigma anchors were fit against MARKET expectation, not this board's own projections. The weekly points used for volatility shape use **base scoring only** — no bonuses, no sacks, no fumbles — so volatility SHAPE and the projection MEAN are computed under two different scoring systems. That exclusion "protects the 62.1% OOS calibration," so changing it is a measured experiment, never a casual edit. **Critically: the 62.1% benchmark was itself established against a base-scored target, so it must be re-established on the league-scored panel before any full-bonus comparison means anything.**

### 2.4 The decision layer (`advisor.py`)

- **`_survival_prob`** — measured ADP-dispersion logistic. `_SCALE_ADP = [3.5, 9.5, 18.5, 32.5, 50.5, 75.5, 110.5, 165.5]` → `_SCALE_S = [1.8, 2.8, 4.6, 6.9, 8.7, 10.4, 15.0, 17.9]`, interpolated (`advisor.py:774-815`). Fitted on 19,300 real picks from 111 one-QB Sleeper drafts. **Drives VONA, the wheel column, the punt read, `_lasts_round`, the lookahead block, and the not-my-turn shortlist.** Already backtested in `44_survival_curve_backtest.py`: −3.0 pts, CI [−5.1, −0.9], 80.5% of drafts identical — it shipped anyway on correctness grounds.
- **VONA** = VOLS − best_wait, where best_wait = Σ over the position of max(VOLS,0) × P(survives) × P(everyone better is gone).
- **`opponent_read`** — live opponent rosters → per-position effective horizon.
- **`_cold_read`** — the surviving half of the run-dynamics work. WR COLD: **−11.5pp** change in P(a WR goes in the next 4 picks) vs slot-matched baseline in one-QB (n=1,253), replicating at −7.7pp in superflex (n=15,628). RB COLD −2.5/−3.5pp. Advisory only; never re-ranks. Code is honest that this probably measures room/settings *preference persistence*, not momentum.
- **Wheel bands** — `_WHEEL_GONE_P, _WHEEL_SAFE_P = 0.20, 0.70` on measured survival probability. **Judgment, not backtested.**
- **Punt read, rest-of-draft lookahead (`_LOOKAHEAD_PICKS = 8`), roster-shape gates, risk-stack penalty, late-round DART profiles, `_go_score` handcuff screen** (carry share ≥0.30, implied ≥23, pos_adp ≤50; validated holdout 42% vs 18%).
- **Cohort priors** (`cohort_priors.py`): K=15 nearest historical 2019–25 seasons, `M_SHRINK = 25`. Outputs boom/bust/median/trimmed-mean/top-5 rate + 5 named comps. **Explicitly demoted to colour: "small-n history is color, not calibration."**
- **SOS and playcaller changes** — advisor PROSE ONLY. The system prompt forbids using an OC-only playcaller change as a price adjustment (validated price-neutral, n=135).
- **Replacement level** — `utils.py:58 FIXED_STARTERS = {"QB": 12, "K": 12}` [V], consumed by `compute_metrics.py` (`replacement_level[pos] = pts.nlargest(n).min()`). QB replacement is the QB12.

### 2.5 Signals computed and then THROWN AWAY (your cheapest starting inventory)

- `proj_divergence` (|FP − ESPN|) — written to the board, never read. **But see C17: the three 2026 sources correlate +0.964 to +0.987 over the top 180, so this has almost no variance in the draftable range. Expect a near-null.**
- `boom_rate` / `bust_rate` per player — computed in the MC, merged, never used.
- `p10 / p90 / P_pos2 / P_pos3` — computed, written, never surfaced.
- `bye_week` — carried, nothing reads it. No bye-week conflict check anywhere.
- `ecr_tier` — carried, unused.
- `snap_share_2025` — display-only, in no formula.
- Carry share outside the late rounds; per-player first-down rate (league-specific gap — §7).

### 2.6 Admitted weaknesses to treat as research targets

- **`team_role` is not a depth chart.** It ranks projected `total_points` within team+position (`value_board.py` ~line 41). "BUF WR1" means "the Bills WR our blended projection likes most." The advisor is told to weight it heavily for volume safety — **reading a projection artifact as football information.**
- **The role term collapses into the value term** for switched-team players (85 of 536) and "ascending" same-team leads, where `role_pct` is *replaced* by the VOLS percentile. For that population the 0.09 role weight is a second helping of VOLS, not a second signal — **so a real role signal there competes with nothing. That is the cheapest genuine win available in this charter.**
- **xPPG is stale for team-changers** by construction and absent for 171 of 536 players.
- **The whole survival layer is single-source:** ESPN ADP softened by a logistic fitted on Sleeper drafts. Nothing models that this specific 12-team league drafts differently from either corpus. **The draft slot itself is not settled** (app set to 12; mocks run at 1/5/10; a prior handoff asserted 7 and was corrected).
- **The composite is strategy-blind** and the prompt says so.
- **"Boom" and "bust" are price-relative, not performance-relative** — `mult = finish ÷ preseason price`, and the cohort kNN uses price tier as a *matching feature*.
- **`apply_bonuses.py` linearizes the threshold structure.** Every tiered/cumulative bonus except long TDs is computed as **league rate × projected season volume** [V, lines ~58–61 and ~95–96]:
  ```python
  r_rush100, r_rush200 = rate_bt("rushing_yards",100,200), rate("rushing_yards",200)
  ...
  + m["rush_yds"] * (r_rush100*RY100 + r_rush200*RY200)
  + m["rush_att"] * fd_carry * RFD
  ```
  So a boom/bust back and a metronome with identical projected yards receive **identical** bonus points. The shape is averaged away before the MC ever runs, and the MC re-centres on `total_points` so it cannot recover it. Measured symptom: top-12 RB `bonus_points` spans only **13.5 points** (57.2 → 70.7) on a level of ~64 [V] — near-pure volume, almost no independent information. **Long-TD 40+/50+ rates ARE per-player, empirical-Bayes shrunk with K=12 — the in-repo precedent that the per-player pattern is viable.**

### 2.7 Where fantasy and football are already separated — and where they are still conflated

**Already separated (enforced in data):** VOLS (football production → league points − replacement) vs VONA (draft-market economics); `market` quarantined as a pricing signal that "NEVER makes a worse player the pick over a better one"; the VALUE tag gated on `p_startable ≥ 0.40`; xPPG as a role-quality-vs-finishing-luck instrument with elite dampening; injury FACTS separated from injury forecasts (the composite runs on `ceiling_healthy`/`floor_healthy` and carries **no injury discount at all**); cohort history ranked below calibrated odds; room behaviour walled off from value.

**Still conflated (your research surface):**
1. W_E 0.13 + W_A 0.06 = **0.19 of the composite is where experts and the crowd rank a player.** Chasing ADP is partly chasing our own board.
2. Rookie football quality **is** market consensus (`ROOKIE_MKT = 0.5`, 117 players).
3. The consensus-outlier rule lets expert RANK veto a projection and then **hides the player from the advisor entirely.**
4. Role collapses into value for a large minority (§2.6).
5. "Role" is a projection artifact (§2.6).
6. Boom/bust are price-relative.
7. `team_env` does double duty — a football-quality input used as a ceiling multiplier *and* as a draft-strategy threshold (≥23 implied).
8. `total_points` is 50% Vegas, and Vegas is a market — the "pure value" backbone is half market-derived before ECR and ADP are added.

---

## 3. DATA INVENTORY

Verified in this environment on 2026-07-31, including by adversarial re-verification. **Re-verify before building on any of it (S8).** Corrections from the reviews are marked **[CORRECTED]**.

### 3.1 In use now

| Source | What it gives | Access | Key gaps |
|---|---|---|---|
| **Sleeper player universe** `api.sleeper.app/v1/players/nfl` | Base universe (12,204 → 3,223 active skill), cross-IDs, live `injury_status`/`injury_notes`/`news_updated` | FREE, no auth | **`gsis_id` unreliable — ~32% populated, ~27% of those with a leading space. NEVER join Sleeper→nflverse on it.** `espn_id` 1,472/3,223 and **0 of 307 rookies**. `injury_notes` populated for only 89 of 12,204. |
| **`load_ff_playerids()`** (DynastyProcess crosswalk) | sleeper_id ↔ gsis_id ↔ pfr_id ↔ espn_id | FREE via nflreadpy | **Broken for the 2026 class:** of 81 skill draft picks, supplies sleeper_id for 5, espn_id for 5, pff_id for 0. |
| **`load_player_stats()`** | Weekly REG box score + target_share, air_yards_share, wopr | FREE, 12 call sites | ~44 rows have NULL player_id; `set()` + `.isin()` once wrongly kept 1,241 never-played players. Always `.drop_nulls()`. |
| **`load_snap_counts()`** | `offense_pct` per game | FREE | Joins on **`pfr_player_id`, NOT gsis** — bridge via crosswalk. Coverage 412/536 on the board. |
| **`load_team_stats()`**, **`load_rosters()`**, **`load_draft_picks()`**, **`load_schedules()`** | Team totals/defense; season rosters; NFL draft capital; schedule + coaches + `spread_line`/`total_line` | FREE | Team abbreviation drift (LA/LAR, WSH/WAS, JAC/JAX, ARZ/ARI) normalized ad hoc in ≥4 files. **2026 coach fields were STALE for ARI/ATL/BUF.** |
| **`load_pbp()`** | TD lengths, FG distance, sack rate, 2pt, PAT miss — **~12 of 372 columns used** | FREE, loaded 2023–25 by `apply_bonuses.py` | Most under-exploited source in the repo. **An 11–12 season pull is the largest single compute item in this charter and must be budgeted (see T0.3).** |
| **`load_ff_opportunity()`** | xFP → xppg, xppg_diff, regression label. **1 of 159 columns read.** | FREE, OPEN-licensed | 365/536 coverage; backward-looking for movers |
| **ESPN `kona_player_info`** | Live ESPN ADP **and** ESPN's own projections, one endpoint | FREE, PUBLIC, no login. Headers `X-Fantasy-Filter`, `X-Fantasy-Source: kona` | 533/536 ADP on board; tail polluted with retired sentinels. **`34_projection_calibration.py` already proved prior-season kona endpoints are reachable and cached them in `espn_hist_cache.json` — this is the repair path for the 2025 price gap (T0.2).** |
| **FantasyPros projections + ECR** | 5 component-stat CSVs + ECR/tiers/SOS | **MANUAL DOWNLOADS. API 403s.** | Projections dated **Jul 6**; ECR **Jun 25**. Landmines: K has no blank subheader row; `FPTS` is STANDARD scoring so PPR = FPTS + REC; a missing star silently becomes NaN and gets dropped. |
| **Vegas season projections** (firstdown.studio) | Per-player Vegas stat lines + team implied totals | **HAND-TYPED, no refresh script.** Pulled 2026-07-12. | **The most load-bearing manual data in the project** — 50% weight on `total_points`, `team_implied_total` non-null for all 536. |
| **Sleeper draft API** | Live draft sync + the 1,162-draft / 372,394-pick corpus | FREE, 1,000 calls/min | **Corpus is 1QB-scarce: only 111 of 1,162 are one-QB.** |
| **ESPN live draft** (`espn-api`) + **ESPN DOM bridge** (Tampermonkey + Firebase) | Live picks; the DOM path is the only one that works for ESPN MOCKS | FREE | DOM path locked to ESPN's Pick History grid |
| **Sleeper projections** `/v1/projections/nfl/regular/2026` | Third projection source + `adp_ppr` / `adp_std` for 9,397 players | FREE | Read only by `tools/archive_projections.py` — **does not feed the board**. Historical Sleeper projections are **backfilled, not forecasts** (`38_`) — invalid as a backtest source. |
| **`load_injuries()`** (research only) | Weekly `report_status`, primary/secondary injury, `practice_status` | FREE | Pre-2025 files have no `season_type` (the L21 silent-drop bug). **[CORRECTED] `game_type` ∈ {REG, WC, DIV, CON, SB} — there are NO preseason rows, and `report_status` ∈ {Questionable, Out, Doubtful, Note, NaN} contains NO PUP and NO NFI** [V]. **The BOARD has no injury input at all.** |
| **`load_ff_rankings('all')`** | 1.8M rows of historical FantasyPros ECR with `sd`, `best`, `worst`, **and `scrape_date`** | FREE | Used in exactly one place. **This is the only free historical price TIME SERIES available anywhere in this project.** |
| **Hand-curated coaching intel** | `new_hc_2026.csv` (10 HC changes), `playcallers_2026.csv` (18 changes, 6 first-timers), `playcallers_hist.csv` (224 sourced team-seasons 2019–25) | **NEWS-VERIFIED BY HAND** | **[CORRECTED] The testable unit is far smaller than 224.** 224 team-seasons → **78 caller-change events** → only **31** have an incoming caller with prior playcalling history at a different team inside the window; **47 are first-time callers for whom the carryover hypothesis is undefined** [V]. |

### 3.2 Derived research artifacts on disk — and their limits

| File | What it is | **[CORRECTED] limits** |
|---|---|---|
| `icm/work/mc_research/seasons.parquet`, `seasons_exp.parquet` | 2014–2025 priced player-season panel | **Priced rows (adp ≤ 200) per season: 2014 159, 2015 165, 2016 158, 2017 156, 2018 164, 2019 165, 2020 170, 2021 179, 2022 146, 2023 177, 2024 176, 2025 **5** [V]. 2025 by position: QB 0 / RB 3 / TE 0 / WR 2. **2025 is not a usable holdout as shipped.** |
| `icm/work/mc_research/adp_hist.csv` | Historical ADP | **Max ADP per season 153.8–177.5** [V]. `33_harsh_backtest.py` runs 12×16 = **192 picks from a pool of 146–183**. The pool is exhausted in every season; rounds ~13–16 draft from a near-empty board. **The mandated grader is structurally blind to the deep bands — the one place this project has holdout-validated edges.** 2025 has 5 rows. |
| `icm/work/mc_research/ecr_hist.csv` | Historical ECR | **[CORRECTED] Covers 2021–2025 only** (488/472/464/654/470 rows) [V], not 2014–2025. One collapsed `ecr_pre` per player-season, **no `scrape_date`** — the time dimension was thrown away. For longer history or any before/after price movement, pull raw `load_ff_rankings('all')`. |
| `icm/work/mc_research/weekly.parquet` | 2014–2025 weekly panel, 67,353 rows [V] | **Carries `rushing_first_downs`, `receiving_first_downs`, `passing_first_downs`, `sacks_suffered`, `sack_fumbles_lost`, `rushing_fumbles_lost`, `receiving_fumbles_lost`, `kickoff_return_yards`, `punt_return_yards`, `pt_return_tds`, and `passing_40`/`rushing_40`/`receiving_40`** [V]. Note `receiving_40` counts **receptions** of 40+ yards, **not touchdowns** — the cumulative 40+/50+ TD bonus needs TD length from pbp. |
| `icm/work/mc_research/espn_hist_cache.json` | Cached prior-season ESPN kona pulls from `34_` | The repair path for the 2025 price gap. |
| `icm/work/mc_research/blend_cache_2019_2025.json` | Projection cache used by `44_` | `44_` restricts to `CLEAN = (2021, 2022, 2024, 2025)` because `38_` established Sleeper's 2019–20 projections are backfilled [V]. |

### 3.3 Obtainable free and unused — ranked by leverage, with corrections

1. **`load_ff_rankings('all')` filtered to `fp_page == '/nfl/rankings/ppr-cheatsheets.php'`, latest `scrape_date`.** 511 players in the 2026-07-31 snapshot with `ecr`, **`sd`, `best`, `worst`**. The manual CSV is 36 days stale and covers 406/536. ECR carries 24% of `rank_composite`. **This unlocks per-player expert dispersion — a free, direct measure of consensus uncertainty the project has never had** — and, via `scrape_date`, the only free historical price time series. Caveat: no `TIERS` or `SOS SEASON` column on the mirror.
2. **`load_depth_charts()`.** 2026: 388,004 rows, 32 teams, latest snapshot 2026-07-31T09:40:30Z, 3,184 rows current; columns `team, player_name, gsis_id, espn_id, pos_grp, pos_abb, pos_slot, pos_rank`. Spot-checked correct. **[CORRECTED — CRITICAL] This is two different data products under one name** [V]: 2019 (36,308 rows) and 2023 (37,327 rows) carry `season, club_code, week, game_type, depth_team, depth_position` — the NFL's official, widely-known-to-be-perfunctory gameday depth chart. 2025 (**554,215 rows**) and 2026 carry the ESPN-sourced daily-snapshot schema above. **ZERO column names overlap between the eras.** Do not pool `depth_team` with `pos_rank`. A null in the historical half is a data-quality result, not a signal result.
3. **`load_schedules(seasons=[2026])` → `total_line`, `spread_line`.** 51 of 272 games populated. Implied total = total_line/2 ± spread_line/2 (the formula `01_build_panel.py` uses). A free automatable cross-check on the hand-typed Vegas file.
4. **FFC ADP API 2026** — `fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year=2026`. Live 12-team PPR ADP with `stdev`, `high`, `low`, `times_drafted`. 2026-07-31: 3,899 drafts over a 7-day window, Gibbs 1.6 (stdev 0.8), Bijan 2.0. The June rejection ("too noisy") does not reproduce. **[CORRECTED] FFC returns HTTP 403 to a plain urllib GET; it requires a browser `User-Agent`** [V]. With the header: 2026 → 247 players; 2024 → 205 players / 1,371 drafts; **2025 → 0 players. FFC does not serve 2025 on this endpoint — it is a missing year, not a broken request** [V]. Historical years return a single **late-August** snapshot (2024 window = 2024-08-31..09-01), not comparable to a Jul-31 ESPN ADP without saying so. FFC serves only ~205–247 players (≈20 rounds), so it **cannot densely validate the `_SCALE_ADP = 165.5` anchor.**
5. **Sleeper `adp_ppr` + `adp_std`** — a third independent ADP with dispersion; parser already written in `tools/archive_projections.py`.
6. **`load_pbp()` — the ~350 unused columns.** Verified present in 2025 (48,771 × 372): `air_yards`, `yards_after_catch`, `epa`, `cpoe`, `xyac_mean_yardage`, `xpass`, `pass_oe`, `yardline_100`, `wp`, `td_prob`, `qb_dropback`, `shotgun`, `no_huddle`, weather/roof/surface, player ids. **Red-zone share must be derived from `yardline_100` — there is no `red_zone` column.**
7. **`load_ff_opportunity()` — the 158 unused columns.** `rec_touchdown_exp`, `rush_touchdown_exp`, `pass_touchdown_exp`, `receptions_exp`, `*_first_down_exp`, and a full set of `*_team` denominators.
8. **`load_nextgen_stats()`** — 2016–2025. `avg_separation`, `avg_cushion`, `avg_intended_air_yards`, `percent_share_of_intended_air_yards`, `catch_percentage`, `avg_yac_above_expectation`, **`avg_time_to_throw`**. Keyed by `player_gsis_id`.
9. **`load_pfr_advstats(summary_level='season')`** — 2019–2025. `adot`, `ybc`, `yac`, `brk_tkl`, `drop_percent`, `x1d`, `rat`. Keyed by `pfr_id`.
10. **`load_participation()` — [CORRECTED, THE SINGLE MOST IMPORTANT CORRECTION IN THIS CHARTER].** The prior scoping claimed this delivers per-player routes run. **It does not.**
    - **`route` is ONE LABEL PER PLAY** describing the *targeted receiver's* route. 2022 value counts: `HITCH 2937 / FLAT 2601 / OUT 2528 / CROSS 2076 / GO 1775 / SCREEN 1711` [V]. It is non-empty on 19,110 of 45,919 plays in 2024 and 18,176 of 50,150 in 2022 — i.e. on pass plays only, one row each. **There is no routes-run column anywhere in nflverse.**
    - **The "100% non-null" figure in the prior scoping was an empty-string artifact.** `.notna()` → 45,905/45,919 = 100.0%; `.fillna('').str.len()>0` → 19,110/45,919 = **41.6%** [V]. Use `.str.len()>0`, never `.notna()`, on this file.
    - **The route vocabulary changed between seasons.** 2022 uses `HITCH / OUT / CROSS / IN / SLANT`; 2024 uses `HITCH/CURL / QUICK OUT / IN/DIG / DEEP OUT / SHALLOW CROSS/DRAG` [V]. Pooling silently mixes taxonomies — S8 with no error raised.
    - **What IS obtainable:** `offense_players` (the gsis ids on the field) is non-empty on **91.5% / 91.4% / 91.4% of plays in 2016 / 2020 / 2022 and 100.0% in 2023 / 2024 / 2025** [V]. From it you can build **pass-snap participation** = share of team dropbacks on which the player's `gsis_id` appears in `offense_players`, joined to pbp on `(nflverse_game_id, play_id)`.
    - **State the conflation bound in every conclusion that uses it:** a TE or RB who stays in to block counts as a pass snap. This is exactly the validity weakness §5 assigns to snap share. **Pass-snap participation is snap share restricted to dropbacks — it is NOT a fast, high-validity route signal, and it is the ceiling of what is free.**
    - Also carries `offense_personnel`, `defense_personnel`, `offense_formation`, `defenders_in_box`, `was_pressure`, `time_to_throw`, `defense_coverage_type`.
11. **`load_ftn_charting(seasons=[2022..2025])`** — verified 2022 (41,643) through 2025 (47,316). `is_play_action`, `is_motion`, `is_screen_pass`, `is_rpo`, `is_no_huddle`, `is_qb_out_of_pocket`, `n_blitzers`, `read_thrown`. **Direct scheme measurement** — the empirical version of the hand-typed playcaller CSVs.
12. **`load_contracts()`** — 51,796 rows of OTC data: `apy`, `guaranteed`, `apy_cap_pct`, `years`, `year_signed`. Contract capital is the veteran equivalent of draft capital and the one signal that updates when a team pays a free agent to be the new lead back.
13. **`load_combine()`** — 969 rows for 2024–2026; the 2026 class is present.
14. **`load_rosters_weekly()`** — **[NEW, substitutes for the absent PUP/NFI history].** 2023 week-1 status counts: `ACT 1536 / CUT 498 / DEV 486 / RES 249 / INA 193 / … / PUP 1` [V]. **PUP appears exactly once league-wide.** The usable historical proxy is week-1 `RES`/`INA`, which collapses IR/PUP/NFI into one bucket — say so wherever you use it.
15. **ESPN `kona` ownership fields beyond ADP** — `percentOwned`, `percentStarted`, `averageDraftPositionPercentChange` (an ADP MOMENTUM signal on the exact platform being drafted on). Zero marginal cost; the bytes are already on the wire.
16. **Re-run the Sleeper mock corpus in early August** (§0.5 exception 2).

### 3.4 Not obtainable — do not plan around these

- **FantasyPros API: PAYWALLED**, re-confirmed HTTP 403 on 2026-07-31.
- **Historical preseason FantasyPros projections: UNRECONSTRUCTABLE, permanently.** Never archived, API 403s, nothing in git history. **The blend weight cannot be validated retrospectively at any price.** Only forward fix: §0.5 exception 1.
- **Sleeper historical projections as a backtest source:** downloadable, scientifically invalid — `38_` established they are **backfilled, not forecasts.**
- **Per-player routes run: NOT IN FREE DATA** (§3.3.10). Closest free substitute is pass-snap participation with the blocker conflation.
- **Targets per route run (TPRR): NOT COMPUTABLE FREE**, because routes are not. "Targets per pass-snap" is a different and noisier object; label it as such.
- **PFF grades / premium charting: PAYWALLED.** Closest free substitutes are FTN charting and PFR advstats.
- **Raw NFL player-tracking (x/y/speed): NOT PUBLIC.** Only NGS derived aggregates are released.
- **PUP / NFI historical designations: ABSENT from nflverse injuries** (§3.1) — no preseason rows, no PUP/NFI in `report_status` [V].
- **Real-time fantasy news wire text: no free programmatic source.** Rotoworld/RotoWire/FantasyPros are paywalled or ToS-restricted. The honest free substitute is already implemented: Sleeper's `news_updated` timestamp as a "something happened" flag (8,135 of 12,204 carry one — **near-universal, therefore near-zero variance**), plus the very sparse `injury_notes`.
- **ESPN mock drafts via API: DOES NOT EXIST.** That is why the DOM scraper exists.
- **Structured coordinator/scheme data: NO FREE SOURCE.** nflverse carries head coach only, and it was stale for three teams. The hand-curated file supports **n=31** carryover events.
- **Offensive-line quality as a rated metric: NO FREE SOURCE.** Free proxies only (pressure rate, `was_pressure`, sack rate, OL contract spend).
- **Season-long Vegas player props and team win totals: not in nflverse, not free.** The largest remaining un-automatable dependency.
- **A clean ID join for the 2026 rookie class: STILL UNAVAILABLE.** Depth-chart espn_id bridge tested: **0 of 81 matched into Sleeper.** `filter_active.py`'s Track-B `normalize_name + position` match remains the only option.
- **Weather forecasts for 2026 games: unknowable in principle** at draft time. Only `roof` (229/272) and `surface` (272/272) are structurally known.
- **Zone vs gap blocking scheme labels: NOT IN PUBLIC DATA.** `run_gap` in pbp is a *direction*, not a scheme.
- **FFC ADP for 2025: NOT SERVED** (§3.3.4).

---

## 4. WHAT PRIOR SCOPING BELIEVES ABOUT SITUATION SIGNALS

A prior, not a conclusion. Test what is marked worth testing; do not spend budget on what is marked dead.

| Signal | Prior | Priced in? |
|---|---|---|
| **Full regime change (new HC + new playcaller), player STAYED** | **HIGHEST of anything here, already measured in-repo.** Stayers under a full regime change: median mult **1.09×**, bust **17%**. **OC-only change with the same HC (n=135) is price-NEUTRAL at med 1.00.** The market prices coordinator swaps correctly and under-reacts only to whole-regime resets. **But see §3.1: only 31 caller moves have a carryable profile.** | **NO** |
| **Player changes teams (the Saquon case) as a MEAN effect** | **NEGATIVE as a mean, measured here.** Tilts: QB 0.97 σ×1.40, RB 0.94, TE 0.95 σ×1.15. **Changing teams is a VARIANCE event, not an EV gain.** Barkley 2024 is a draw from the right tail; the left tail is equally populated and forgotten. **The actionable inversion: bet on the situation changing UNDER a player, not on a player changing situations.** | NO (direction is opposite the folk belief) |
| **QB quality change for pass-catchers** | **NULL vs price, worse than null** (C7). | **YES** |
| **OL quality** | LOW. Tested here vs price, NULL. The widely-quoted "adjusted line yards explains ~29% of half-PPR RB production" is **RECALLED, NOT VERIFIED**, is a raw correlation, and is heavily confounded. | YES |
| **OL continuity (snap-weighted five-man overlap)** | WEAK, expect null. Only QUALITY was ever tested, never CONTINUITY. **Its one league-specific consequence is through the QB sack tax, not through RB weeks 1–4 — see H5c.** | Probably |
| **Playcaller PROE carryover (career PROE minus team's current PROE)** | MODERATE mechanism, THIN edge. PROE *level* is heavily published and priced; the *delta* less so. Caller PROE is partly a function of the roster he inherited. | Mostly |
| **Personnel/formation profile change under a new caller** | **MODERATE — one of the better under-worked ideas**, but only for STRUCTURAL, near-binary calls (does the WR3 exist? is this a 12-personnel TE room?). As a continuous ranking input it will be noise. **n=31 caps it.** | **NO** |
| **Playcaller touch-CONCENTRATION profile (RB touch HHI, top-back share, RB/TE target share)** | **MODERATE** — forecasts ROLE (stable, payable) rather than efficiency. Risk: the concentration a caller ran is partly the back he had. **n=31 caps it.** | **NO** |
| **Goal-line / inside-5 coaching tendency carried with the coach** | MODERATE, under-explored publicly. Predicts ROLE ALLOCATION. Denominators brutal — ~25–45 inside-5 plays per team-season. Tie-breaker only. | **NO** |
| **Vacated targets/carries** | **LOW — the most over-consumed offseason stat in the hobby.** Redistribution is not proportional, and every outlet publishes the same table in June. **Contrast: this project validated a player's OWN existing target share (17% vs 4%), not vacated share. Held volume predicts; freed volume does not.** | YES |
| **Route participation rate / alignment change** | MODERATE in principle, **but the data does not exist free** (§3.3.10). What you can actually test is pass-snap participation with a blocker conflation. Honest limit: players with suppressed participation are suppressed for a reason. | **NO** |
| **Competition ADDED (new draft capital / FA money at the position)** | MODERATE, strongly asymmetric. Loud at the top of the board, **never re-priced in the deep bands.** | Partly |
| **Contract structure as organizational intent** | MODERATE for ROLE SECURITY, weak for points-above-price. Cleanest usable form: a **committee tie-breaker** in ambiguous RB/TE rooms. | Partly |
| **Age / mileage** | **MOSTLY A MYTH** (C9). Surviving: the RB age curve is a *slope not a cliff* (availability sags from ~28, median mult 0.92 at 29+; WRs hold at every age). | YES |
| **Team implied total / win total** | **NULL as an edge.** Baked into every projection that feeds ADP. This project's late-round work refuted offense gates as a **Vegas-total leak.** | YES |
| **Game script projection** | LOW. Real in-season, nearly useless pre-season; defensive YoY stability is poor; double-counts implied total. | YES |
| **Pace** | LOW, bordering irrelevant. | YES |
| **Scheme fit (zone vs gap)** | **LOW, and the data does not exist.** Acts on EFFICIENCY; fantasy is dominated by VOLUME. **Do not spend the week here.** | — |
| **Offseason program attendance / OTAs** | **OTAs: NULL** — voluntary and routinely skipped by exactly the veterans you care about. **PUP/NFI placement was the one candidate under-priced item — but it is ABSENT from free historical data (§3.4), so it cannot be tested as a forecast and must be routed as a forward-only FACT.** Loud holdouts are priced within a day. | Mixed |
| **Beat-reporter camp reports (the user's explicit question)** | **MOSTLY NOISE with a non-noise core.** The adjectival layer ("best shape of his life") is close to pure noise and *adversarially selected* — teams talk up players they want to start, trade, or justify. The FACTUAL layer (first-team reps, PUP, missed practice) is real but captured better by structured sources. And it is the **fastest-priced information class in fantasy.** **Honest verdict: read camp news to avoid drafting a player who is hurt or demoted, never to find an edge.** | YES |
| **xFP vs actual (TD-luck lens)** | **The correct BASELINE, not a new edge** — and the bar every situation signal must clear. "The situation changed" and "his TD rate was unsustainable" explain many of the same step changes. **A situational feature that merely re-discovers TD regression has added nothing.** | — |

### 4.1 Where the market is structurally weakest

1. **FORMAT AND SCORING MISMATCH — the largest and most reliable edge available, and it is not a prediction problem at all.** ADP is aggregated across leagues that do not use this league's scoring. **ADP cannot price bonuses and settings it never sees.** An hour spent sharpening custom-scoring valuation beats an hour spent forecasting situations, because the mispricing is *mechanical* rather than statistical. **The measured positional tilt is huge: mean bonus for the top-12 is RB +64.2 vs QB −8.9, a 73-point cross-position swing, and RB vs WR is +29.3** [V].
2. **THE TAILS, NOT THE MEANS.** The measured team-change effect is a *sigma multiplier* with a mean tilt near 1.0. The exploitable decision is not "which mover pops" but **"when do I want mover-shaped variance"** — narrow distributions at anchor picks, fat ones in the upside bands. ADP is a single number and cannot express this.
3. **SECOND-ORDER ROLE CONSEQUENCES OF A REGIME CHANGE.** The market re-prices a new coach's stars within hours and stops. Nobody re-prices the TE2 who becomes relevant because the new caller runs 32% 12-personnel.
4. **THE DEEP BANDS (~ADP 120+).** Thin trading, few real opinions. This project found real holdout-validated edges there and none of comparable size at the top. **Warning: the priced panel tops out at ADP 153.8–177.5 [V], so most deep-band claims are NOT-TESTABLE-IN-POINTS unless T0.2 succeeds in extending it.**
5. **SIGNALS REQUIRING A SNAP-LEVEL JOIN.** Anything computable from a box score is priced. Anything requiring a participation/pbp join has at least a chance.
6. **ORGANIZATIONAL-INTENT SIGNALS IN THE MID-TIER.** Headline free agency is priced instantly; a $5M/yr guarantee to a back in a three-way committee moves role probability materially and ADP almost not at all.
7. **TIMING WINDOWS, WITH A CAVEAT.** ADP lags hard news 24–72 hours in late July / early August. **This is a trading edge, not a drafting edge** (S9).

---

## 5. IN-SEASON DETECTION: THE STABILIZATION LADDER

The organizing physical fact: **stabilization speed is approximately a function of events per game.** Snaps ~65, routes ~35, carries ~15, targets ~7, red-zone plays ~4, goal-line carries ~1, two-minute drives ~1.5. A 17-game season means almost nothing in football "stabilizes" by baseball standards — **which is exactly why the mechanism gate, not a p-value, is what makes early tier-change calls trustworthy.**

**Two definitions before you read the table.** (a) **Leverage is defined in league points**: points-above-replacement per unit of the metric, computed on the league-scored panel (T0.3). A ladder ordered by reliability alone is a football ladder, not a fantasy one. (b) This table is **inherited prior art, not measurement.** WS1 re-derives it empirically from this project's own data; **where your measured numbers disagree, yours win — say so explicitly.**

| Indicator | Type | Games to stabilize | Notes |
|---|---|---|---|
| **Roster/depth-chart EVENTS** (teammate injury, trade, OC change, QB change, benching, OL injury, suspension) | event / mechanism | **0 (instantaneous)** | **The highest-value entry in the whole system and the one most frameworks omit because it is not a statistic.** Every reliable early call is two-gate: (1) a usage step-change AND (2) a MECHANISM explaining it. Usage moves *without* a mechanism are variance until proven otherwise; usage moves *with* one can be trusted at n=1–2 games. **Fantasy values a SLOT in a depth chart, not a player.** Tag every event-driven promotion with an **expected reversion date.** |
| Alignment / slot rate | OPPORTUNITY | 1–2 | Near-deterministic coaching fact. **NOT in free nflverse data.** |
| Snap share | OPPORTUNITY | 2–3 | Highest raw reliability, **moderate validity** — includes blocking snaps. Free weekly. Strip garbage time for the ROLE read; do NOT strip it for the POINTS read. |
| **Pass-snap participation (proxy for route participation)** | OPPORTUNITY | **2–3** | **[CORRECTED] Routes run are NOT free.** Build from `offense_players` ∩ dropbacks (§3.3.10). Conflates blockers with route runners, so it is snap share restricted to dropbacks — **moderate validity, not high.** Still the best free (speed × leverage) product for WR/TE/pass-catching RB, and the biggest tier separator at TE and at RB in PPR. |
| Carry share (raw + neutral-script) | OPPORTUNITY | 2–3 | Most game-script-confounded opportunity metric. **Compute both versions — they answer different questions.** |
| Team plays/game, neutral pass rate, PROE | CONTEXT | 3–4 | `pass_oe` is native in pbp. Very sticky within a regime; resets instantly on an OC or QB change. |
| Personnel grouping rates (11/12/21) | CONTEXT | 3–4 | Extremely sticky team identity. Highest leverage at TE — 12-personnel rate is the precondition for a second fantasy-relevant TE. |
| aDOT | OPPORTUNITY | 3–4 | Coach-assigned, not earned. **A change in aDOT WITHOUT a change in target share is a genuine, commonly-missed tier change.** |
| Third-down/passing-down participation | OPPORTUNITY (binary) | 3–5 as a rate, **2 as a flag** | Model as categorical — the underlying reality is a coaching binary. Best free proxy for RB pass-game role. |
| Air-yards share / WOPR | OPPORTUNITY | 4–5 | Best-validated single composite for receiver volume. Free via NGS. |
| Target share | OPPORTUNITY | 4–6 | **Always decompose: target share = participation × targets-per-participation.** First half stabilizes in 2–3 ("does he have a job"), second in 6–8 ("is he earning it"). |
| Red-zone opportunity share | OPPORTUNITY | 5–7 by count, **3–4 by presence** | Clearest case where leverage and speed point opposite ways. **Change the MEASUREMENT: count presence in red-zone personnel, not touches.** |
| Goal-line / inside-5 share | OPPORTUNITY | 6–10 (effectively never) | Statistically never stabilizes; practically you can KNOW it in 3–4 games by watching who is on the field. |
| **Per-player first-down conversion rate** | league-specific | 4–5 (rush), 5–6 (rec) | **CURRENTLY UNMODELLED PER-PLAYER.** `apply_bonuses.py` applies a LEAGUE-AVERAGE rate to everyone. Worth 35–50 pts/season to a 15-carry back. |
| QB designed rush attempts | OPPORTUNITY | 3–4 | **Primary QB tier separator under this scoring**, extremely sticky — a scheme decision, not a QB decision. |
| QB sack rate (avg time-to-throw as the ~2-game-earlier proxy) | HYBRID + **direct scoring term here** | 5–7 (3–4 for TTT) | SACK = −1. 2.5 sacks/game = **−42 pts/season** ≈ the QB6→QB12 gap. **Already per-QB EB-shrunk in the board — see H5c.** |
| Targets per pass-snap (the free stand-in for TPRR) | HYBRID | 6–8 | TPRR proper is unavailable. This noisier cousin still separates an EARNED tier change from a VACATED one — **two things with completely different reversion profiles** — but label the conflation. |
| CPOE | EFFICIENCY | 6–8 | Slow talent prior; useless as an early trigger; low leverage. |
| xFP differential | DIAGNOSTIC | 5–6 | **Tells you a player has been lucky, NOT that he has changed tier.** Extend to a WEEKLY series so it can feed a change-point test. |
| Two-minute participation | OPPORTUNITY (flag) | 6+ | Mostly redundant with passing-down participation. |
| QB interception rate | EFFICIENCY | 10+ | Project from a shrunken multi-year prior. **For a sack-prone QB the sack tax (−42/season) dwarfs the INT tax (−16/season).** |
| YPRR | EFFICIENCY | 8–10 | Not computable free; and **do not use whole** even in proxy form — decompose. |
| Catch rate, YAC-over-expected, missed tackles, separation | EFFICIENCY | 8+, weak leverage | Correct role: a slow prior on whether a role is likely to be TAKEN AWAY. |
| **Yards per carry** | EFFICIENCY | **Never (~250+ carries to halve the noise)** | **BLACKLIST as a tier-change trigger.** The single most common false positive in amateur in-season analysis. |
| **TD rate per touch/target** | EFFICIENCY | **Never** | Model TDs from expected TDs built on red-zone/goal-line opportunity. **Asymmetry: fading a low-TD player whose red-zone ROLE is intact is the more expensive error.** |

---

## 6. PER-POSITION BRIEFS

League scoring is in `scoring_config.py` — **read it, it is the single source of truth, and it is NOT standard.**

### QB
**Drivers:** pass_yd 0.04, **pass_TD 6 (not ESPN's 4)**, pass_int −2, **SACK −1**, fumbles_lost −2, rush_yd 0.1, rush_TD 6, rushing first down 0.5, 300/400-yard tiers +3/+5, 40+/50+ passing TD +0.5/+1 cumulative, 2pt +2.
**What casual analysis misses:** (a) a rushing yard is worth 2.5 passing yards on the base rate; with the first-down bonus a QB with 50 rush yards and 3 rushing first downs banks ~6.5 points ≈ 162 passing yards — **rushing is worth 3–3.5× per yard AND it is the lowest-variance QB input**; (b) SACK −1 is a first-class scoring term worth ~the QB6→QB12 gap; (c) tiered/cumulative bonuses pay for the SHAPE of the weekly distribution.
**Key signals by (speed × leverage):** designed rush attempts (3–4) > Vegas implied total (0, forward-looking) > team plays / neutral pass rate / PROE (3–4) > avg time to throw (3–4, leads sack rate) > sack rate (5–7, plus OL injury as an instant change point) > aDOT (3–4) > red-zone dropback share vs handoff rate (5–7) > QB rushes inside the 10 (6+, huge leverage) > CPOE (6–8).
**Failure modes:** chasing passing-TD rate; conflating football-good with fantasy-good (efficient QB on a run-heavy team throws 480 times and finishes QB16); under-weighting the sack; missing that rushing is the only low-variance input, so floor and ceiling MOVE TOGETHER at QB; reading a hot 3-game stretch as a tier change when dropbacks and rush attempts never moved. **Counter-caution: the "Konami rushing-QB filter" showed NO late-round edge (1/15 vs 14/101).** Do not pay a late-round premium for rushing NARRATIVE.
**The predictive problem is different at QB:** highest R² on raw points, **lowest value of information** — 1 starts, replacement is high and streamable.
**[CORRECTED — C12 GOVERNS] Every QB output is denominated in the EXISTING VOLS/VONA. Replacement stays the QB12 from `utils.startable_counts`, unchanged.** The streaming alternative is expressed the way L11 resolved it: as a **decision-layer opportunity cost** (the PUNT READ's `punt_loss` against the fill window in `advisor.py`), never as a redefinition of replacement. Any proposal that redefines QB replacement — including "denominate against a QB13–QB24 pool" — is C12 re-opened under a new name. Say so and stop.

### RB
**Drivers:** reception 1.0, rush_yd 0.1, rush_TD 6, rushing FD 0.5, receiving FD 0.5, 100/200-yd rushing +3/+5 tiered, **40+/50+ rushing TD +2/+3 cumulative (the largest long-TD bonuses in the table)**, fumbles_lost −2.
**Two structural tilts:** (1) the 0.5 first-down bonus is enormous — a 15-carry back converts ~4–6 rushing first downs a game = 2–3 free points/game, 35–50/season; a 2-yard gain on 3rd-and-1 scores 0.7 while a 20-yard gain on 1st-and-10 scores 2.5 — **a ~6× per-yard multiplier on conversions**, which makes the short-yardage/goal-line specialist genuinely rosterable. **`apply_bonuses.py` applies a LEAGUE-AVERAGE first-down rate to every player.** (2) tiered yardage + cumulative long-TD bonuses **pay for CONCENTRATION**: identical season totals score differently — **except that the pipeline currently linearizes this away (§2.6), so the board cannot see it.**
**Key signals:** pass-snap participation (2–3, biggest PPR tier separator — a 60%-participation back and a 20% back are different asset classes at identical carries) > carry share, computed twice (2–3) > snap share (2–3) > goal-line PRESENCE (3–4) > passing-down binary (2–3) > target share (4–6) > team run rate / plays / implied total > per-player rushing FD rate (4–5) > OL run-block + OL injury as an event.
**Failure modes:** YPC chasing; committee misdiagnosis (a genuine 50/50 split reads as a takeover for 2–3 weeks by chance); TD-mirage **with a critical asymmetry — the goal-line ROLE is sticky even when the conversion rate is not, so fade the finish, not the role**; game-script blindness; treating injury-driven change as a trend (**it is a discrete change point — rolling averages are structurally 2–3 weeks late on the most valuable calls of the season**); forgetting the reversion date.
**Different at RB:** opportunity explains more of fantasy PPG variance here than anywhere — **but what you are forecasting is a depth chart and a coaching preference, not a player.** RB carries the highest injury hazard, producing both the most tier changes and an asset class (contingent value) with no football-analytics analogue.

### WR
**Drivers:** reception 1.0, rec_yd 0.1, rec_TD 6, receiving FD 0.5, 100/200-yd +2/+4 tiered, 40+/50+ rec TD +1/+2 cumulative.
The receiving first-down bonus tilts toward the chain-mover: a 100-target slot receiver with 70 catches and ~45 receiving first downs banks **~22 bonus points on top of 70 PPR points** — a possession receiver is paid twice for the same catch. The deep threat collects cumulative long-TD bonuses and hits the 100-yard tier more often, with a worse catch rate and a lower floor. **WHICH ARCHETYPE NETS MORE UNDER THESE EXACT MULTIPLIERS IS AN OPEN EMPIRICAL QUESTION AND IS A NAMED RESEARCH LINE (H5a), not an assumption.**
**Key signals:** pass-snap participation (2–3) > alignment/slot rate (not free) > aDOT (3–4) > air-yards share / WOPR (4–5) > target share decomposed (4–6) > targets per pass-snap (6–8) > red-zone target share (5–7 count, faster by presence) > team PROE/pace/implied total > **the event layer**, dominant at WR because value is a SHARE.
**Failure modes:** efficiency mirage; confusing target QUALITY with target VALUE (high-aDOT targets have low catch rate — a PPR floor killer, so football EV per target and PPR points per target rank the same targets differently); the football-good/fantasy-bad WR2 in a 480-attempt offense; two-sided TD regression where **fading a low-TD WR with elite volume is the more expensive error**; the teammate problem; **rookie WR bimodality — rookies step-change mid-season more than any cohort, so the detector needs a rookie-specific faster-triggering prior.** Note the inversion: at DRAFT time this project found WRs 29+ and "year-2 breakout" WRs both went 0-for in late-round league winners, while the post-hype 20%+ target-share WR was the most robust signal. **In-season and preseason WR priors are genuinely different objects.**
**Different at WR:** the widest outcome distribution of any position, so SHAPE matters more than the mean. **But note the incumbent: the board is ALREADY distributional (ceiling 0.25 + floor 0.15 = 40% of the composite, L45-measured at +0.033 Spearman). Any WR distribution proposal competes with that, not with a point projection.**

### TE
**Drivers:** per-event scoring identical to WR, but **almost all TE value comes from POSITIONAL SCARCITY**: 1 starts, replacement far below WR/RB, so the 40th-best pass catcher in football can be a top-30 fantasy asset. A larger share of TE points comes from TDs than at any other pass-catching position — simultaneously the noisiest position per unit of usage and the one where TD regression does the most damage in both directions.
**Key signals:** pass-snap participation (2–3) — **THE TE signal, because most TEs block and the first question is binary** > alignment in-line vs flexed (not free) > team 11-vs-12 personnel rate (3–4) > red-zone target share (5–7, presence faster) > target share (nominally 4–6, slower in practice at ~4–6 targets/game) > snap share, which is fast but the **LEAST VALID metric at this position — never rank TEs on snap share.**
**Failure modes:** TD-dependency variance (TE5 on 60 catches and 8 TDs → TE20 on identical usage); the blocking-TE trap; rookie TE year-1 dead zone (and **test, do not assume, the "year-3 breakout" folklore** — the young high-capital TE dart hits top-6 at roughly 1-in-10); **the handcuff trap, which at TE is settled by C14 — promoted TE backups boom at 4.5% (p=5.5e-6, 281 team-seasons). An in-season TE alert triggered purely by a starter's injury is a FALSE POSITIVE at this position by measurement, and the suppression rule is SETTLED, not a hypothesis.**
**Different at TE:** largely a CLASSIFICATION problem (pass-catcher vs blocker) plus a TD-luck term. **Express every TE output in VOLS/VONA.**

### K and D/ST — a stated scope cut, not an oversight
This league starts a **K and a D/ST**, both scored under real ESPN tiers (`DST_PA_TIERS`, `DST_YA_TIERS`, FG-by-distance in `scoring_config.py`). The K sigma is flagged in-code as **"not researched — flat mid value."** D/ST has no research line at all. **They are out of scope for sub-modelling in this charter — say so deliberately in §10.10 ("What I could not do"), and note L36/L38: any position the advisor recommends needs its own tracking, or the model fills the gap from training memory.**

---

## 7. THE FANTASY-VS-FOOTBALL LAYER (the user's explicit framing)

These divergences are the reason a good football model can be a bad fantasy model. This section survived all four reviews intact and is the strongest content in the charter.

1. **THE MASTER RULE — fantasy scoring is a NON-LINEAR, THRESHOLDED transform of a game-level box score, not a linear function of season totals.** This league proves it: 100/200-yard bonuses are TIERED (a 210-yard rushing game scores +5, not +3+5); long-TD bonuses are CUMULATIVE (a 55-yard TD collects both 40+ and 50+); 300/400-yard passing is tiered. **Two players with identical season totals score differently based purely on the SHAPE of their weekly distribution — concentrated/boom beats steady at equal totals here.** Football analytics measures per-play efficiency and correctly aggregates linearly; fantasy requires modelling the weekly DISTRIBUTION and then applying the transform. **Two places this is currently destroyed: `apply_bonuses.py` linearizes the tiers into per-yard constants (§2.6), and the MC's weekly volatility uses base scoring only (§2.3). The FIRST of those is where the damage happens; the second cannot recover it.**
2. **VOLUME BEATS EFFICIENCY, AND IT IS NOT CLOSE.** A 4.0-YPC back with 18 touches beats a 5.2-YPC back with 9 touches essentially every week. **The correct research target is the COACH'S DECISION, not the player's ability.** This also explains the stabilization asymmetry that makes in-season detection viable: opportunity metrics stabilize in 2–4 games, efficiency in 8+ or never, and **the fast family carries most of the fantasy signal. In football analytics the reverse is true — importing a football-analytics metric set wholesale gives you a system that is both slow and wrong.**
3. **GOAL LINE AND SHORT YARDAGE — the purest divergence.** A 1-yard TD plunge is near-zero EPA and 6+ fantasy points (here: 6 + 0.5 FD). A touchdown vulture with genuinely negative per-play football value is a legitimately rosterable fantasy asset. **Any system that filters by "efficiency" deletes this archetype entirely.**
4. **THE FIRST-DOWN BONUS REWARDS CONVERSION, NOT EXPLOSIVENESS** — a ~6× per-yard multiplier on conversions. Football analytics values the explosive play far more. **Currently modelled with a league-average rate per player: a concrete, measurable, unexploited edge.**
5. **GARBAGE TIME — the most important two-track requirement in the system.** Football analytics discounts garbage time; fantasy counts every yard. A bad offense can be an EXCELLENT fantasy environment for its WR1 and pass-catching back and terrible for its early-down runner. **Maintain TWO versions of every usage metric: garbage-time-stripped as the TALENT/ROLE proxy, raw as the POINTS projection. Collapsing these is the most common way a sophisticated football-analytics approach produces worse fantasy answers than a naive one.**
6. **SACKS AND TURNOVERS ARE WHERE THE TWO CONVERGE — call it out, because it is unusual.** This league adds SACK −1 and fumbles_lost −2 on top of INT −2, pulling the QB answer much closer to the football answer than standard scoring does. **Pressure-to-sack rate, time to throw, and turnover-worthy-play rate become direct fantasy scoring inputs here — worth 40–60 points/season on a sack-and-turnover-prone profile. A genuine edge over an ADP room priced on standard scoring, and the board already exploits part of it (§H5c).**
7. **TEAM QUALITY ≠ FANTASY ENVIRONMENT.** The best fantasy environment is usually a good-but-not-dominant offense that plays close games. Pace and neutral pass rate matter more than team quality; a Vegas GAME total often beats the team total for a receiver.
8. **A TEAMMATE'S INJURY IS THE LARGEST SINGLE SOURCE OF FANTASY ALPHA AND HAS NO FOOTBALL-ANALYTICS ANALOGUE.** Fantasy evaluates the SLOT a player occupies. **No football framework has a concept for "this player's value expires in week 11."**
9. **REPLACEMENT LEVEL AND POSITIONAL SCARCITY EXIST ONLY IN FANTASY.** Importing football rankings directly mis-tiers QB and TE in opposite directions. **And replacement level is where this league's custom scoring does most of its work — see H5f.**
10. **UNSTARTABLE POINTS ARE WORTH ZERO** (L8). The in-season layer inherits this: **an alert on a position you cannot start is not actionable.**
11. **SNAP SHARE VS ROUTE PARTICIPATION is the cleanest measurement-level divergence** — **but [CORRECTED] routes are not obtainable free (§3.3.10). The honest statement is: the gap between what public analysis measures and what actually scores is real, and the free ceiling for closing it is pass-snap participation with a blocker conflation. This is a smaller investment than the prior scoping claimed, and it is not "the single highest-leverage data investment in this programme" — WS5 is.**
12. **CATCH RATE AND aDOT TRADE OFF DIFFERENTLY IN PPR THAN IN FOOTBALL EV.** The correct currency is **points per TARGET under this exact scoring table**, not yards or EPA per target — and the two orderings genuinely disagree on real players.
13. **xFP IS THE RIGHT BRIDGE OBJECT** — it denominates football-neutral opportunity directly in fantasy currency. Two extensions: make it **WEEKLY** so it can feed a change-point test, and **recompute the expectation under THIS league's scoring table** — nflverse xFP is built on standard scoring and therefore systematically mis-prices short-yardage conversions, goal-line carries, and yardage-tier bonuses in a league that pays for exactly those.
14. **OPPONENT ADJUSTMENT MUST BE BY POSITION AND USAGE TYPE**, not by defensive quality. A generic SOS number approximates a fundamentally multi-dimensional object.
15. **CONTINGENT VALUE IS AN ASSET CLASS WITH NO FOOTBALL ANALOGUE — but conditional.** The option is worth something only if the backup ALREADY has a real role; at TE it is worth essentially nothing (C14). **Suppress injury-triggered alerts for players with no pre-existing participation or carry share.**
16. **"STABILIZES" IS NOT "PREDICTS FANTASY POINTS."** Reliability and validity are separate axes. Rank by (speed × leverage) with leverage in league points, and **where they conflict, change the MEASUREMENT rather than discarding the signal** (count goal-line presence, not touches).

---

## 8. THE WORKSTREAMS

Each workstream must produce, in writing: **hypothesis → data + provenance → test design → ONE primary endpoint in league points (S14) → falsification condition → verdict with the actual numbers and a season-clustered CI (S11).** A workstream with no falsification condition is not a workstream.

**Mandatory reporting block for every paired-draft result** (this is what made C5's null legible — `results_42_upgrade.txt`'s "100.0% of drafts IDENTICAL" turned an ambiguous +0.0 into a structural proof):
1. **% of paired drafts identical** — the policy's firing rate.
2. Mean and distribution of the number of picks changed.
3. The paired-difference distribution **conditional on ≥1 pick changed**.
4. A **leave-one-player-out jackknife** — drop the single most-frequently-flagged player and re-report. **If dropping one player moves the result by more than half, the finding is one player, not a rule.** (C11 is the precedent: plain ADP caught 6 of 9 holdout league-winners; the composite score caught 2.)
5. **Per-slot spread across slots 1, 5, 8, 10, 12** — never a pooled mean. `45_` showed roster shape is near slot-invariant but QB/TE timing bifurcates hard (Josh Allen in R2: 64% at slot 5, <2% at slots 11–12). **A finding that only pays at one seat is not a finding.**
6. **Per-season breakdown** (S4) and the season-clustered CI (S11).
7. Both currencies — league points primary, base PPR secondary (S12).

**`mult` results are SCREENING ONLY and may never appear in the verdict table's result column.** The verdict column is league points, or NOT-TESTABLE. `mult` lifts may appear in supporting text only, and every sentence citing one carries the C3 caveat.

**Power.** Choose `N_DRAFTS` so the SE of the *conditional* mean (conditional on the policy firing) is ≤ ⅓ of the stated bar, and **show the arithmetic**. A policy firing in 10% of drafts has ~3.2× the SE of one firing every draft at the same n.

Prefix new scripts under `icm/work/mc_research/` continuing the numbering (`46_`, `47_`, …) with matching `results_NN_*.txt`. **Read three existing scripts before writing your first.**

---

### WS0 — Foundations, replication, and instrumentation (do this first; everything depends on it)

**Purpose:** establish that your data is what you think it is, and rebuild a measurement rig that can actually resolve the effects the rest of the charter chases. Three of the four adversarial reviews concluded the existing rig would produce a false positive or a false null. **Do not skip any of this.**

**T0.1 — Participation semantics, not just coverage.** Load `load_participation()` for every season 2016–2025 individually. For each: row count, and **non-EMPTY rate using `.fillna('').str.len()>0`, never `.notna()`** (the prior scoping's 100% figure was an empty-string artifact). Report the `route` column's **semantics** — confirm it is one label per play describing the targeted receiver's route, and print the value counts for 2022 and 2024 side by side to expose the vocabulary change. Report `offense_players` non-empty rate per season. Then build and validate **pass-snap participation** = share of team dropbacks on which a gsis_id appears in `offense_players`, joined to pbp on `(nflverse_game_id, play_id)`. Sanity-check it against `load_snap_counts` `offense_pct` for a handful of known route-runners and known blockers. **Deliverable: a one-page statement of exactly what participation data this project has, with the blocker conflation quantified.** Budget: half a day, not a workstream.

**T0.2 — Source verification, price-instrument repair, and the frozen population.**
- Re-verify every source in §3.3 with row counts, coverage against the 536-player board, and join success rates. Report anything changed since 2026-07-31.
- **Every FFC call sends a browser `User-Agent`.** Add a hard assert: `meta.total_drafts` non-null and `len(players) > 100`, so a 0-player response **raises** instead of silently writing a 5-row CSV.
- **Repair the 2025 price row.** `34_projection_calibration.py` already proved prior-season ESPN `kona` endpoints are reachable and cached them in `espn_hist_cache.json`. Pull 2025 ESPN ADP the same way and rebuild the 2025 rows of `adp_hist.csv` / `seasons_exp.parquet`. **This is roughly an hour of work and it is the single highest-value cheap fix available, because it restores a genuinely untouched out-of-sample season (S2).** If it fails, use `ecr_hist.csv`'s 2025 (470 rows) as the price instrument and **state the instrument change explicitly in every result that uses it.**
- **Try to extend the priced panel past ADP 180.** Pull ESPN historical ADP at depth and report the achieved max ADP per season. **If the panel cannot be extended past ~180, then no deep-band hypothesis is testable in points, and every deep-band claim is labelled NOT-TESTABLE in the verdict table rather than graded on a truncated pool.** Do not silently grade rounds 13–16 against an empty board.
- **Emit `icm/work/mc_research/population.json`:** exact filters, exact row count per season, exact cluster count per season, exact max ADP per season, exact position mix. Every downstream script asserts against it on load and aborts on mismatch. `33_` uses `adp ≤ 200, season ≥ 2015`; `42_` uses `adp ≤ 220` and four seasons — **the templates already disagree, and unfrozen populations quietly destroy the comparability of the verdict table.**
- **Assert `pool_size >= TEAMS * ROUNDS + 30` for every season before any paired-draft run**, and abort with a named error if it fails.
- **Gate WS2 on the playcaller counts.** Print `78 caller-change events / 31 with a carryable prior profile / 47 first-time callers` from `data/playcallers_hist.csv` and confirm against the file. This number decides whether WS2's forecasting half is a workstream or a premise gate.

**T0.3 — Build the LEAGUE-SCORED panel. This is the most important single task in WS0.**
Write `icm/work/mc_research/46_league_scored_panel.py` producing `weekly_league.parquet` and `seasons_league.parquet`, scoring each player-week through this league's actual table rather than base PPR.
- **Import the scoring functions from `custom_scoring.py` and the constants from `scoring_config.py`. Do not restate a single rate or multiplier in your module.** League scoring is already expressed in five places (`scoring_config.py`, `custom_scoring.py`, `apply_bonuses.py`, `blend_vegas.py`, the MC's base-scoring weekly proxy) — per L52, a duplicated scoring constant is a bug waiting for the next rules change.
- Feasibility is established: `weekly.parquet` (67,353 rows, 2014–2025) already carries `rushing_first_downs`, `receiving_first_downs`, `passing_first_downs`, `sacks_suffered`, `sack_fumbles_lost`, `rushing_fumbles_lost`, `receiving_fumbles_lost`, `kickoff_return_yards`, `punt_return_yards`, `pt_return_tds` [V].
- **Because a weekly row IS a game row, the tiered 100/200/300/400 bonuses are computable EXACTLY per week rather than as a league rate.** This is the only place in the project where the threshold structure can be evaluated without approximation.
- Only the **40+/50+ long-TD** bonuses need a pbp join on TD length. `apply_bonuses.py` loads pbp for 2023–2025 only; you need **11–12 seasons**. Budget this download/compute explicitly — it is the largest compute item in the charter. Cache the result as `bonus_weekly.parquet` (per player-week bonus points broken out by component) so every later script reads a committed artifact rather than re-pulling pbp.
- Assert per-year row counts before pooling (S8). Report per-position mean (league points − base points) by season, so any year with missing columns is immediately visible.
- **Pre-register this falsification:** *if league-scored and base-scored grades agree within noise across all of WS5, then §4.1.1's "largest edge available" claim is wrong and the Blueprint must say so on page 1.*

**T0.4 — Build the grader. Three arms, two modes, five slots, measured opponent dispersion.**

*Base template:* start from **`icm/work/mc_research/44_survival_curve_backtest.py`**, not from `33_`/`42_`. `44_` is the newest simulator and its header documents two corrections the older templates lack [V]: "**My picks are made by VONA**, not raw VOLS… drafting by VOLS would make the whole test vacuous (that mistake is what 42_ ran into)" and "**Opponent noise uses the MEASURED dispersion too.** Earlier sims used a flat sd of 8 picks everywhere, which we now know is wrong at both ends." Borrow `optimal_lineup()` and the actual-season-points scoring from `33_`. **Grep all 13 simulator scripts first and write a one-paragraph note on what each got wrong — that note is a deliverable.**

*Three arms, because nothing in the repo currently measures anything as INCREMENTAL:*
- **Arm 1 — ADP-follow.** Sanity floor only.
- **Arm 2 — reconstructed composite** (the current system as closely as it can be rebuilt historically).
- **Arm 3 — composite + treatment.**
- **The primary endpoint is arm 3 minus arm 2.** Arm 3 minus arm 1 is a secondary number and must never be reported as the headline.
- **State the hard constraint up front:** arm 2 can only be reconstructed for seasons where honest preseason projections exist — per `38_`, Sleeper's 2019–20 projections are backfilled, so `44_`'s `CLEAN = (2021, 2022, 2024, 2025)` is the usable set [V] — **and 2025 has no price row unless T0.2's repair lands.** So the composite arm is **n = 3 or 4 seasons**, with an MDE near **+90 points** (S11). **If you cannot live with that, the honest deliverable is a ranked hypothesis list plus the 2026 live test, not a points verdict — say so rather than reporting an under-powered PASS.**

*Two scoring modes, declared per hypothesis:*
- **(a) SEASON mode** — the existing `optimal_lineup` over season totals, correct for roster-construction questions.
- **(b) WEEKLY mode** — iterate weeks, set a lineup each week from the rostered players who actually played that week, with a fixed replacement-level fill for any unfilled slot, scored from `weekly_league.parquet`. **This is the only mode that can represent distribution shape, bye weeks, and mid-season availability.** `33_`'s `optimal_lineup` at line ~125 chooses ONE lineup for the whole season from season totals [V], which treats a player who scored 200 points in 9 games identically to one who scored 200 across 17. **The repo's single most robust finding is that unavailability is the dominant failure mode — 73–85% of busts in every round band — and the season-mode grader is blind to it, in a direction that systematically UNDERSTATES availability signals and OVERSTATES accumulation signals.**
- Hypotheses whose payoff is shape or availability are graded in weekly mode or **marked NOT-TESTABLE**. Do not record a structurally guaranteed null as evidence.

*Opponent model:* **replace the flat `ADP_NOISE = 8.0` [V] with the measured per-player dispersion — import `advisor._SCALE_ADP` / `advisor._SCALE_S` (`advisor.py:774-815`) so the sim and the shipped survival math use ONE curve.** Flat sigma 8 is ~4.4× too loose at the top of the board (measured scale 1.8 at ADP 1–6) and ~2.2× too tight at the bottom (17.9 at 131–200). It lets elite players free-fall to your seat at random — L33's diagnosed failure in a different costume — and it inflates the ±318 per-draft spread that §S4 quotes as a rhetorical anchor. Re-run the prerequisite bundle under both opponent models and report the delta. **Grep first: the ADP-dispersion curve must not exist in two places with two values (L52/L53).**

*Slot:* **parameterize `MY_SLOT`** (`33_` hard-wires 7 [V]; the app is set to 12; mocks ran at 1/5/10; a prior handoff asserted 7 and was corrected). Run at **1, 5, 8, 10, 12** and report the per-slot spread on every row.

*Policy delta interface:* the module accepts a "policy delta" callable so every workstream is graded identically. Carry `44_`'s two invariants forward as runtime assertions: my picks go through VONA; opponent sd comes from the measured curve.

**T0.5 — Harness self-test (two modes, and the corrected mode is allowed to disagree).**
- **T0.5a — provenance check.** Run `33_harsh_backtest.py` unmodified and confirm byte-identical output. It uses fixed seeds (`np.random.default_rng(10_000 + i)`), so this checks the environment, not the method.
- **T0.5b — legacy mode.** Run the NEW grader in legacy configuration (ADP policy, season-total scoring, flat noise 8.0, slot 7) and confirm it reproduces the prerequisite bundle at **+5.2 within ±2 points AND the 51.5% win rate within ±1pp.** "± noise" is not a criterion — at 2,500 drafts the naive SE is ~3.2, so "+5.2 ± noise" is a gate that cannot fail.
- **T0.5c — corrected mode.** Run the same treatment in corrected configuration (composite arm, weekly scoring, measured dispersion, five slots) and **report the delta as a finding at the top of the report.** **The corrected grader SHOULD NOT reproduce +5.2 — reproducing it would prove the new grader inherited the old one's defects.** Do not treat divergence here as a failure.
- **Only T0.5b carries a stop-and-fix condition.** Do not re-run the 62.1% OOS band coverage or the −11.5pp WR COLD figure: they are settled, they cost a day (1,454 player-seasons and a 372,394-pick corpus respectively), and the grader does not compute either. Cite them from their results files.

**T0.6 — Placebo calibration. Cheap, decisive, and the thresholds in §8 are provisional until it exists (S15).**
Generate **20 synthetic "situation" variables** with the same marginal distributions and the same clustering structure as the real candidates — assigned at team-season for regime-type signals, at coach-move for carryover signals, at player-season for player-level signals. Run each through the **identical** pipeline: nudge construction, paired grading, sensitivity sweep, season-clustered CI. Report the distribution of placebo results — the max, the 95th percentile, and **how many placebos would have "passed" each stated threshold.** **The 95th percentile of the placebo distribution is the real bar.** If a placebo routinely scores +20, everyone learns on day two instead of day thirty.

**T0.7 — The role census (do this before any role hypothesis).**
`team_role` / `role_lead` / `role_pct` / `role_env_ok` / `role_alpha_ok` appear across `advisor.py` (16 sites), `value_board.py` (12), `app_pages/draft.py` (6), `tools/preflight.py` (3), `cohort_priors.py` (1), plus three test suites. **Enumerate every site that computes or consumes a role concept, what each means, and which are derived from `total_points` and therefore not independent evidence.** Then require every role hypothesis (H2g, H4-RB, and anything in WS3 that uses role) to state which of the five it replaces, which it sits beside, and — critically — **how `role_lead`'s MAGNITUDE (`_ROLE_LEAD_K = 0.5 VONA per point`) is reconstructed from an ordinal depth-chart `pos_rank`, which supplies rank but not magnitude.** This is L52/L53's exact failure mode at larger scale: the snake-pick schedule lived in four places and was wrong in three, and the recorded lesson was *"a partial fix to a duplicated concept is worse than no fix."* Role lives in five.

**T0.8 — The already-shipped census (S13).**
For **every** hypothesis in §8, grep the repo for the quantity it proposes to add and write one line on what already computes it. This charter's own draft proposed three features that already ship. Produce this as a table in the Blueprint. Known instances you must not re-derive:
- **Per-QB sack rate:** `apply_bonuses.py` lines ~34–41 [V] — `sack_rate = (sdf["sacks"] + K*L_sack) / (sdf["throws"] + K)`, applied at line ~98 as `m["pass_att"] * sr * SACK`. Per-QB, empirical-Bayes shrunk, in the frozen chain. Material, not decorative: top-12 QB `bonus_points` spans **35.0 points**, Josh Allen +9.0 to Drake Maye **−25.9**; Maye is 2nd on raw `custom_proj_points` (370.7) and **10th after the sack tax (332.2) — an eight-spot re-rank** [V].
- **Per-player long-TD 40+/50+ rates:** already EB-shrunk with K=12 in the same file [V].
- **Committee-leader screening:** `_go_score` (carry share ≥0.30, implied ≥23, pos_adp ≤50), holdout 42% vs 18%; plus `role_priors.py`'s 2025 carry share.
- **Draft-capital tilt:** `draft_tilt()` in the MC (≤15 → 1.10, ≤32 → 1.08, ≤105 → 0.92).
- **Mover proven/unproven split:** shipped as MC Wave-2b tilts.
- **Survival curve backtest:** `44_` already graded it (−3.0 pts, CI [−5.1, −0.9], 80.5% identical).
- **Distributional board:** ceiling 0.25 + floor 0.15 in the composite.

**T0.9 — Weekly league-scoring xFP.**
Build a weekly xFP series under this league's table (§7.13). **Do not modify `load_ff_opportunity.py`; write a parallel research module — and import scoring from `custom_scoring.py` / `scoring_config.py` per T0.3.** Report where league-scoring xFP diverges most from nflverse standard-scoring xFP, by position and by archetype.

**WS0 success criterion:** a working three-arm, two-mode, five-slot grader that reproduces the known result in legacy mode and reports a measured delta in corrected mode; a league-scored panel; a placebo distribution that sets the real thresholds; a frozen `population.json`; a role census; an already-shipped census; and a data-availability table every later workstream cites.
**WS0 falsification:** if legacy mode cannot reproduce +5.2 within ±2 and 51.5% ±1pp, the grader is wrong and nothing downstream is trustworthy. Stop and fix it.

---

### WS1 — Situation vs player: decomposition (quantification only)

**Scope cut, stated up front.** The draft of this charter asked WS1 to test whether the situation term dominates and whether stable player contribution lives in earned-opportunity rather than efficiency. **§7.2 already asserts that as a binding design rule, and the mover regression is substantially the shipped Wave-2b analysis.** A charter cannot both assert something as a design constraint and spend budget testing it. **WS1 is therefore a magnitude exercise for calibration, not a direction test.**

**H1 (quantification):** *How much* does the situation term dominate — **in this league's scoring, on this panel** — and how much of that is already in price?

**Data:** `seasons_league.parquet` (T0.3), `seasons_exp.parquet`, `weekly_league.parquet`, `adp_hist.csv` (with the T0.2 repair), `ecr_hist.csv` (2021–2025 only, §3.2), raw `load_ff_rankings('all')` for longer ECR history.

**Test design:**
1. Variance decomposition of league-scored fantasy PPG into player, team-season, and residual components, done **twice** — once on raw PPG, once on **PPG-above-price**. The gap between the two decompositions *is* the market's pricing accuracy on situation.
2. Split-half reliability, within-season and across-season, for every metric in §5, computed on this project's own data. **Report the empirical stabilization ladder from THIS data. Where your measured numbers disagree with §5, yours win — say so explicitly.** Define leverage in league points-above-replacement (§5 preamble). Note this is ~25 tests and they all count toward the S14 FDR correction.
3. **Movers:** start from the **shipped Wave-2b split (`compute_outcomes.py` ~lines 164–189) as a FIXED CONTROL**, not as a finding to rediscover. The only new question is whether *earned-opportunity* features (pass-snap participation, targets-per-pass-snap, target share) add anything **on top of** proven/unproven, which was not in the Wave-2b feature set.

**Primary endpoint:** WS1 is diagnostic. It succeeds if it produces a **ranked list of candidate signal families with measured stabilization times and measured residual-vs-price variance shares**, which WS2–WS5 draw from. **It must reduce the search space, not expand it.**

**Falsification, stated in points not variance:** the draft's "under ~2% residual variance share" threshold is stated in variance units, which S1 forbids. **C3 already answered this question in points: the friendliest possible bundle of situation-shaped conditions bought +5.2 on ~1,600, CI [−30, +40].** So: state the points-equivalent of your variance threshold, or simply take C3 as the prior and say WS1 is sharpening it. **If the pre-season-knowable residual is small in points, the pre-season half of this charter is dead — say so on the first page of the Blueprint and redirect budget to WS3 and WS5.**

**Required honesty:** the Barkley case is one draw from a distribution this repo has already measured (movers ran 0.94–0.97× price with sigma inflated 15–40%). **Your executive summary must state whether "situation step changes are predictable" survived contact with the data — and the honest prior is that it will not, in the mean, and will survive only in the variance.**

---

### WS2 — Pre-season step-change prediction (heavily re-scoped by feasibility)

**The framing constraint:** the user has accepted that beating ADP pre-draft is hard. WS2's job is **not** "beat ADP." It is: **identify the narrow, defensible set of pre-season-knowable conditions under which a step change is more likely than the market implies, and quantify how narrow that set is.** A precise, small, honest answer beats a broad, exciting one.

**The binding constraint on the whole workstream, computed before you start:** `playcallers_hist.csv` yields **78 caller-change events, of which only 31 have an incoming caller with a carryable prior profile; 47 are first-time callers for whom the carryover hypothesis is undefined** [V]. Cross with ~5.4 priced skill players per team-season, H2b's fantasy test tops out at ~167 priced player-seasons and H2a's explicitly non-alpha target at **~62 player-seasons — before any position split.** One split lands it at ~n=38, **the exact sample that produced the retracted C4 finding at bootstrap P=1.00.** And clustered on the treatment unit (S11), the effective n is **31 coach-moves**, not 62 player-seasons. **The only lever that changes this is hand-extending `playcallers_hist.csv` back to 2014 (~160 more team-seasons) — that is manual news verification, not code. Name it as a budgeted manual task or accept directional-only.**

**Sequencing:** run **H2g first** — it is a cheap validity fix, not a forecast, and it becomes the baseline the forecasting hypotheses must beat.

**H2g — 2026 depth charts as an independent role signal. RUN THIS FIRST.**
Replacing the projection-derived `team_role` (§2.6) with real `load_depth_charts` `pos_rank` produces a role signal that can *contradict* the projection. This is the highest-leverage plumbing fix in the charter and it is a validity fix, not a prediction problem.
- **[CORRECTED] Scope to 2025 only.** The historical half is not comparable: `load_depth_charts` is two data products under one name with **zero overlapping column names** between the 2019/2023 schema (`depth_team`, the perfunctory NFL gameday chart) and the 2025/2026 schema (`pos_rank`, ESPN daily snapshots) [V]. **Explicitly forbid pooling `depth_team` with `pos_rank`.** State n = one season.
- **Cheap check first:** what is the agreement rate between real `pos_rank` and projection-derived `team_role` in the draftable range? **If ≥95%, the fix is cosmetic — report it as such and stop.**
- Then: does real `pos_rank` beat projection-derived `team_role` at predicting actual role and actual league-scored outcome above price on 2025? Requires the T0.2 price repair; if that fails, use ECR as the price instrument and say so.
- Then grade the swap in the paired harness — **but first complete T0.7's role census and state which of the five role sites you are changing and how you reconstruct `role_lead`'s magnitude from an ordinal rank.**
- **Primary endpoint:** league points in the corrected grader, arm 3 − arm 2. **Bar: the T0.6 placebo 95th percentile, or +20, whichever is higher.** No OR-clause (S14).
- **Highest-value population:** the 85 switched-team players and ascending same-team leads where `role_pct` currently *is* the VOLS percentile. **For that population you are not competing with a role signal, you are competing with nothing.** Report that sub-population separately.

**H2a — Regime-change second-order roles. [DEMOTED TO PREMISE GATE.]**
A full regime change (new HC + new playcaller) predicts a shift in personnel-mix-determined role availability (does the WR3 exist? is this a 12-personnel TE room?) that the market prices only for the team's stars. Target: the WR3/TE2/committee-RB tier, not the alpha.
- **Premise test, and STOP there:** carry the incoming caller's personnel-rate profile from his prior team; predict the receiving team's next-season personnel mix; **report the carryover R² with its interval, clustered on coach-move (n=31).** Compare against the receiving team's own prior year as the null predictor.
- **Abandon if carryover explains less than ~15% of the receiving team's next-season mix**, or if the interval on 31 clusters is uninformative — which is the honest expectation.
- **The points test is NOT reachable at this n and the charter does not pretend it is.** If the premise passes surprisingly well, note it as a candidate for the 2026 pre-registration and for a future run with a hand-extended history — do not force an under-powered paired grade.
- **If it survives the premise gate, its success bar is "beats the H2g depth-chart signal," not "beats nothing."**
- Data: `playcallers_hist.csv`, `new_hc_2026.csv`, `playcallers_2026.csv`, `load_participation` personnel rates, `load_ftn_charting` (2022–25).

**H2b — Playcaller touch-CONCENTRATION carryover. [DEMOTED TO PREMISE GATE.]**
A caller's RB touch HHI, top-back share, RB target share and TE target share travel with him and predict the receiving team's next-year distribution better than the team's own prior year does.
- **Premise test only:** for each of the 31 carryable caller-moves, compare three predictors of the new team's concentration — (i) the team's own prior year, (ii) the caller's career profile, (iii) a blend — by out-of-sample error, clustered on coach-move.
- **The confound you must address head-on:** the concentration a caller ran is partly the *back he had*. Control for the receiving team's RB talent (ADP of its best back) and report the effect with and without.
- **Falsification:** caller profile does not beat team-prior-year on the *role* forecast. **If step one fails, stop — do not proceed to a fantasy test on a broken premise.** This is where H2b should die, in one afternoon instead of a week, and that is a legitimate kill-list entry.

**H2c — Goal-line / inside-5 coaching tendency carryover.**
A coach's inside-5 running-back share (vs sneak, vs big-body, vs feature back) travels with him.
- Data: pbp `yardline_100 ≤ 5`, rusher ids, `offense_personnel` for the goal-line package, joined to the caller table.
- **[CORRECTED] Restate the success criterion in the test's actual unit.** The draft said "≥60 rooms"; the carryover population is capped at **31 coach-moves**. Those are different populations and the criterion cannot be met by the test it was attached to. Either state the bar in coach-moves (and accept it is directional at n=31), or split into a separate non-carryover hypothesis about *team-level* goal-line concentration, which has a much larger population.
- Expect brutal denominators (~25–45 inside-5 plays per team-season). Pool multiple seasons per coach and **report intervals, not point estimates.**
- **Usable outcome, if any: a committee tie-breaker only.**

**H2d — Contract/capital organizational intent as a committee tie-breaker.**
In ambiguous RB and TE rooms only, current-year guaranteed money identifies the room's leader.
- **[CORRECTED] The baseline is NOT ADP.** The system already beats ADP here: `_go_score` screens committee leaders with a validated holdout of 42% vs 18%, and `role_priors.py` supplies prior-year carry share. **Baseline = prior-year carry share + `_go_score`.**
- **[CORRECTED] Drop draft capital from the predictor**, or justify it explicitly against C4's surviving fragment — capital is near-inert for a player who already has a role, which is exactly the committee-leader population this targets — and against `draft_tilt()`, which already applies it upstream. **The genuinely new signal is guaranteed money.**
- Data: `load_contracts()` (51,796 rows, covers back to 2015) + `role_data.csv`.
- **[CORRECTED] Count the buildable rooms BEFORE setting the bar.** Ambiguous RB rooms at ADP 25–45 across 2019–2024 is realistically ~36–48, not 80. Going back to 2015 reaches 80 but then the out-of-band replication (S2) eats the same seasons. **Report the achievable n first, then state a bar that n can support.**
- **Falsification:** no replication out of band; or the effect vanishes when headline signings (top-decile APY) are excluded — which would mean you measured "the market already knows" (C7's shape).

**H2e — OL continuity, redirected through the sack term. [PRE-REGISTERED NULL, RE-AIMED.]**
The draft aimed this at weeks 1–4 RB output. **The reviews converge on a better target:** OL continuity's one *league-specific, direct scoring* consequence is the **QB sack tax**, because SACK = −1 here and the shipped per-QB sack rate is backward-looking and pooled across three seasons — it describes the QB's *old* line.
- **Run H2e through H5c, not through RB weeks 1–4.** Hypothesis: does a QB's shrunken sack rate carry when his OL turned over or he changed teams?
- **Scope to 2023–2025** — new-schema depth charts carry OL for 2025/2026, and any historical version crosses the §3.3.2 schema break.
- **Pre-register the expectation of a null before running it.** Only OL QUALITY was ever tested here; continuity never was. Confounded with team quality and cap health.
- **Falsification:** null (expected). **Report the null; it closes a line.** If budget is tight, dropping H2e costs almost nothing and buys budget for WS5.

**H2f — The user's own question: offseason workout reports and camp signals. [RESTRUCTURED — most of it is not a WS2 question.]**

*The adjectival layer* ("best shape of his life", "looks explosive"): state plainly that there is **no free licensed corpus, no ground truth, and the layer is adversarially selected** — teams talk up players they want to start, trade, or justify. **Do not build a sentiment model.** The draft's cheap substitute (does a Sleeper `news_updated` timestamp near the draft predict anything above ADP?) is **a null by construction**: 8,135 of 12,204 players carry a timestamp, and ~50 of the top-150 ADP were updated within 3 days. A near-universal flag has no variance. **Either specify a recency threshold tight enough to create variance and test that, or delete the test and record the reasoning in the kill list.** Deleting it is the recommended choice.

*The factual layer* (PUP/NFI, missed practice, first-team reps): **[CORRECTED] this is NOT testable as a historical forecast, and it should not be tested as one anyway.**
- **The data is absent.** `load_injuries()` has **no preseason rows** (`game_type` ∈ {REG, WC, DIV, CON, SB}) and **no PUP or NFI in `report_status`** (∈ {Questionable, Out, Doubtful, Note, NaN}) [V]. `load_rosters_weekly(2023)` week-1 shows **PUP exactly once league-wide** [V]. The usable historical proxy is week-1 `RES`/`INA`, which collapses IR/PUP/NFI into one bucket.
- **The price instrument is absent.** Historical FFC returns a single late-August snapshot, so "does the lift disappear when ADP is measured after the designation" **cannot be evaluated historically at all.** The only free historical price time series is raw `load_ff_rankings('all')` via `scrape_date` — and that is a RANK, not an ADP. Label it.
- **The destination is wrong.** Per WS6's own decision tree, **facts need no backtest**, and the precedent is exact: injury FLAGS were the one thing to survive the L49 line *because they are facts*. PUP/NFI placement is a fact about current state, not a forecast of durability. Testing it as a durability forecast walks straight into **C10** (every popular availability tell null or negative on train and holdout) and **C16** (games-played YoY r = +0.019, the project's most-replicated negative).
- **So: route the factual layer to WS6 as a forward-only FACT feed.** Sleeper's `injury_status` carries PUP/IR live. Surface early-August PUP/NFI/IR as a health flag in advisor context alongside the existing injury line, **with no forecast attached, and cite C16 as the reason.**
- **Keep exactly one cheap measurement:** what fraction of top-180 ADP players carry a PUP/NFI/IR designation in the first week of August — i.e. **does the flag ever fire** (S5)? If it fires on two players a year, say so and move on.

---

### WS3 — In-season tier-change detection (stabilization-aware)

This is the user's second question and probably the highest hit rate — because in-season you are watching a depth chart change, not forecasting one. **It is also where the 2026 season is genuinely informative, because the unit is a player-week.**

**Ground truth, timing, and leakage — get these right before writing any detector.**

- **[CORRECTED] Ground truth is crossing a STARTABILITY threshold in league scoring**, not PPG rank. Define it as **rest-of-season points-above-positional-replacement**, with replacement from `utils.startable_counts` at that week's roster state — the same VOLS currency the draft layer uses, so in-season and pre-season findings are commensurable. Report PPG-rank change as a secondary descriptive column only. Two reasons: §7.10 says an alert at a position you cannot start is worth zero, and PPG deliberately divides out games played — **the one construct engineered to hide the project's dominant failure mode (unavailability, 73–85% of busts).**
- **[CORRECTED] Close the detection/outcome window.** Ground truth for a detection made after Week W is measured over **weeks W+2 through 17**, with a **strict gap week**. If the target starts at Week 1, the detection weeks are inside the outcome window and a detector that fires on a week-1–3 usage spike is partly predicting a window it already observed. That is the classic change-point leak and S7 exists to prevent it.
- **[CORRECTED] Lineup timing.** A detection made after Week W's games may only affect **Week W+1's** lineup, and no waiver claim may resolve before the W+1 processing date. If a Week-W alert can change the Week-W lineup, the entire lead-time result is manufactured.
- **[CORRECTED] Pre-specify the tier-change threshold in `PREREGISTRATION.md`, or report the full threshold curve** rather than a single point (and pre-register that you will report the curve). A threshold chosen after seeing the data is p-hacking with extra steps.
- **[CORRECTED] Revised-data bias.** All 2015–2024 validation runs on nflverse as it stands today — retroactively corrected snap counts, revised injury designations, cleaned practice reports. **In real time, a Week 3 snap count is not what a Week 3 snap count looks like in the archive, and lead time is the quantity most contaminated by revision.** State this as a known **upward** bias, bound it where you can, and **label all historical lead-time claims DIRECTIONAL until confirmed on 2026 live snapshots.** This raises the §9.2 snapshot job from "valuable" to **the single load-bearing deliverable of WS3.**

**H3a — The two-gate rule.** A tier-change call requires (1) a usage step-change AND (2) a MECHANISM explaining it. Usage moves *with* a mechanism can be trusted at n=1–2 games; moves *without* one are variance until proven otherwise.
- **[CORRECTED] Name the mechanism feed and prove it is independent of the usage series under test.** The draft named no feed at all. Acceptable historical sources: `load_injuries()` weekly `report_status` / `practice_status` (designations, not usage), `load_rosters(seasons=[...])` week-over-week roster deltas, `load_draft_picks` / `load_contracts` for transactions, and the hand-curated coaching CSVs. **A mechanism inferred from a TEAMMATE'S snap count is NOT independent — it is derived from the same weekly usage panel the detector is tested on, so part of any precision gain is mechanical.** Run it as a separate, clearly-labelled arm. **If the gate only works under the usage-derived version, the gate is an artifact.**
- Test: build both detectors on 2015–2024 weekly league-scored data — mechanism-gated and ungated — and compare precision / recall / lead time at **matched alert volume**.
- **Primary endpoint:** precision at matched alert volume, with **event-clustered CIs** (S11). Bar: +15pp. **No OR-clause** — if you also want to claim the lead-time version, declare which one is primary before running.

**H3b — Change-point detection beats rolling averages on event-driven changes.** Injury-driven role changes are discrete change points; rolling averages are structurally 2–3 weeks late on the most valuable calls of the season.
- Test: a change-point method (CUSUM, Bayesian online change-point, or a two-sided likelihood-ratio scan — pick one and justify it) against 3-game and 4-game rolling averages on the same weekly usage series. Metric: **weeks of lead time to a correct call, at matched false-positive rate.**
- **Primary endpoint:** median lead-time advantage at matched FPR, blocked-bootstrap over weeks. Bar: ≥1.5 weeks. **Labelled DIRECTIONAL until 2026 confirms it (revised-data bias).**

**H3c — EARNED vs VACATED tier changes have different reversion profiles. [RE-SCOPED — TPRR is not available.]**
- **[CORRECTED] TPRR proper requires routes run, which do not exist free (§3.3.10).** The runnable version is: participation share rose (vacated) vs targets-per-pass-snap rose (earned). **That is a different and noisier object than TPRR — say so in every conclusion, and expect weaker separation.** If T0.1 shows the participation proxy is too noisy to separate the two, **delete this hypothesis and record it in the kill list rather than running a version that cannot answer the question.**
- Test: classify every detected tier change, then measure rest-of-season persistence and post-return reversion separately for the two classes.
- **Falsification:** identical profiles — drop the distinction and save the complexity.

**H3d — Blacklist validation.** YPC and realized TD rate produce more false positives than true positives as tier-change triggers. Cheap; hardens the system against the most common amateur error. Run it, report the numbers, encode the blacklist.

**H3e — Position-specific suppression rules. [SCOPE-CORRECTED BY C14.]**
- **The TE rule is SETTLED, not a hypothesis.** C14 measured promoted TE backups booming at **4.5%, p=5.5e-6, on 281 team-seasons where a starter missed 3+ games** — that IS the in-season promotion case. **Encode TE suppression as settled and cite C14. Do not re-measure it.**
- Likewise **start H3's ground-truth calibration from L30's measured promotion effect** (backup RB 4.0→9.5 ppg, 2.25×, 56% gain 5+ ppg) rather than re-measuring it.
- **Test only the RB and WR suppression rules.** For each: measure how many alerts the rule removes and **what the precision of the removed set was. A rule that removes high-precision alerts is a bad rule.**

**Design requirements for the whole workstream:**
- **Two-track metrics (§7.5):** garbage-time-stripped for the ROLE read, raw for the POINTS read. Report both; never collapse.
- **Every event-driven promotion carries an expected reversion date.**
- **Alerts are gated by lineup slot** (§7.10).
- **Ground truth is in league scoring** (`weekly_league.parquet`), never base PPR or generic PPG rank.

**WS3's benchmark — [HEAVILY CORRECTED].**
The draft proposed a 2015–2024 waiver simulation with "the same FAAB budget and the same waiver priority," and "both setting optimal lineups." Both halves are wrong:
- **The FAAB/waiver-priority simulation cannot be built from data.** There is no historical record of what was available, who bid, or what rosters looked like. **L33 is directly on point: a bad opponent model changed the strategy standings themselves in the draft bakeoff, and a waiver opponent model is strictly harder with no ADP-like anchor to calibrate against.** Delete it — it promises rigour the data cannot support.
- **"Both setting optimal lineups" deletes the value being measured.** If both managers set hindsight-optimal lineups, both already know who will score, and a tier-change detector's entire weekly value — *start him this week* — is assumed away. Second-order: hindsight-optimal lineups actively **reward rostering high-variance players**, so the benchmark is biased toward a roster policy no real manager can execute.

**The replacement benchmark:**
1. **Primary: precision, recall, and median lead time in weeks at matched alert volume**, with event-clustered CIs and a per-season table. This is the honest instrument.
2. **Secondary: an ex-ante lineup comparison.** Both managers set lineups **weekly, from information available before kickoff** — the detector-manager from the detector's projection, the control from a 3-game rolling league-scored PPG. Score realized league points. **Report hindsight-optimal totals alongside as a ceiling, and report the gap between ex-ante and hindsight: that gap is the lineup-decision value, and it is the number the user actually asked for.**
3. **Tertiary: an explicitly-labelled UPPER BOUND on acquisition value** assuming free acquisition, with the statement that real acquisition friction makes realised value strictly lower.
- **[CORRECTED] The threshold is uncalibrated judgment.** The draft's "+40 points per season" has no anchor — this project has never measured what in-season waiver activity is worth. **Label it "judgment, uncalibrated — no prior exists for waiver value in this project," and make the FIRST WS3 output the baseline itself** (what a plain 3-game rolling-PPG manager earns per season), so the threshold is set from a measurement rather than defended after the fact.
- **Falsification:** the detector does not beat a plain rolling average, or it beats it only in seasons where a few extreme events dominate — **report the per-season table so this is visible.**

---

### WS4 — Per-position sub-models

**C8 gate (mandatory first paragraph):** C8 killed per-position composite *weights* — "within a position, ADP dominates and per-position weights add nothing." WS4 proposes per-position *model shape*. **State why the C8 null does not transfer, or abandon the workstream.**

**The hypothesis under all of them:** the right model *shape* differs by position, and a single global model necessarily mis-serves at least two of them.

- **H4-QB — [COLLAPSED INTO H5c].** The draft's falsification ("a raw-points QB model and a VOLS-denominated one produce the same draft behaviour") falsifies a strawman: nobody proposed a raw-points QB model, `compute_metrics.py` already computes VOLS against `startable_counts()` (QB12), and the PUNT READ exists specifically to fix the QB horizon problem. **The only live QB question is whether the sack and designed-rush inputs change the VOLS ORDERING — that is H5c. Do not run a separate H4-QB.**
- **H4-RB — RB is a depth-chart forecast.** Build around pass-snap participation, carry share (both versions), goal-line presence, passing-down binary, and per-player first-down rate. **Falsification: the sub-model's role forecast does not beat `role_data.csv`'s existing carry share at predicting next-season role.** (Complete T0.7 first and state which role site you are changing.)
- **H4-WR — [FALSIFICATION REPLACED].** The draft's "a point-projection WR model performs equivalently to a distribution model" fires 100% of the time and is not a test: **the board already IS distributional** (ceiling 0.25 + floor 0.15 = 40% of the composite; L45 measured +0.033 Spearman from raising them). **Replace with H5a applied to WR ranking: does aDOT-tercile archetype scoring under league rules re-order the WR board above what `ceiling_healthy`/`floor_healthy` already capture?** That competes with the real incumbent. Graded in **weekly mode** (T0.4b) or marked NOT-TESTABLE.
- **H4-TE — TE is a classification problem** (pass-catcher vs blocker) plus a TD-luck term. **Falsification: a continuous TE model beats the classify-then-project model on both rank accuracy and paired league points.**

**Cross-cutting requirement:** every sub-model must be gradeable in the WS0 harness by swapping only its position's ranking. **Note the hard constraint from T0.4: the composite arm exists for 3–4 seasons only, so "the rest of the board unchanged" means the reconstructed board, not the 2026 board.** **Report each position's contribution separately — a global +X that is really "+3X at RB, −2X at TE" is a bad result wearing a good number.**

**Primary endpoint per sub-model:** league points, arm 3 − arm 2, in the declared mode. **Bar: the T0.6 placebo 95th percentile, or +20, whichever is higher — and if the MDE of the instrument exceeds the bar, report DIRECTIONAL-ONLY, not PASS (S11).** Sub-models that do neither are reported as nulls and not proposed for shipping.

---

### WS5 — The fantasy-scoring-specific layer (the highest expected value in the charter)

**This is the pocket where the market is structurally weakest (§4.1.1), it is a mechanical mispricing rather than a statistical forecast, and it is the one place sample size is not the binding constraint.** All four reviews independently ranked it first. **It is also the workstream the old instrument could not see at all — H5b and H5c were worth exactly 0.0 points in a base-PPR grader (S12), which would have produced two false nulls with confident numbers attached.**

**H5f — Positional replacement level under league scoring. NEW, AND THE HIGHEST-EV ITEM HERE.**
**Hypothesis:** the bonus structure shifts positional REPLACEMENT LEVEL enough to change optimal positional allocation versus an ADP room priced on standard scoring.
- **Why this and not the player-level questions:** within the top-12 RBs the bonus term spans only **13.5 points** (57.2 → 70.7) on a level of ~64 — a near-uniform level shift that barely re-ranks *within* RB. **Across positions it is enormous: RB +64.2 vs QB −8.9 is a 73-point positional tilt; RB vs WR is +29.3** [V]. A uniform per-position level shift does exactly one thing mechanically: it moves `replacement_level[pos]` in `compute_metrics.py`, and therefore every VOLS, every cross-position VONA comparison, and every RB-vs-WR timing decision. **The board already does this correctly; the research panel does not, and no hypothesis in the draft charter asked about replacement level at all.**
- It fires on **every pick**, not a handful of players per draft, so S9 reachability is total — the opposite of WS2's problem.
- Test: measure `replacement_level` per position under (a) base PPR and (b) league scoring, on `seasons_league.parquet`, for 2015–2025 and for the 2026 board. Report the VOLS delta at each position and the induced change in cross-position VONA ordering in the draftable range.
- **Second test, closing the C6 seam:** recompute replacement level using *realized* finishes rather than projections, and report how much of the RB-vs-WR VOLS baseline gap is projection bias rather than scoring. **C6 forbids correcting player-level bias; it says nothing about MEASURING the replacement tier, and a 0.12 cross-position bias spread shifts the baseline by the same order as the effects WS2 is chasing.** This is a measurement, not a correction.
- **Primary endpoint:** league points from positional-allocation change alone, in the corrected grader. Bar: placebo 95th percentile or +25, whichever is higher.
- **Falsification:** replacement-level deltas are within noise after the level shift, i.e. the bonus structure is a rank-preserving monotone transform in the draftable range. **Report it — that is a clean, valuable null that closes §4.1.1's headline claim.**

**H5b — Per-player rates for EVERY league-average constant in `apply_bonuses.py`. [WIDENED — absorbs the draft's H5b and the MC half of H5d.]**
**Hypothesis:** per-player, EB-shrunk threshold rates create real spread that currently does not exist.
- **The defect is bigger than first downs.** `apply_bonuses.py` converts every tiered/cumulative bonus except long TDs into league-rate × season volume [V, lines ~58–61, ~95–96]. **So the board cannot distinguish concentrated from steady at equal totals — the exact quantity §7.1 calls the master rule.** The measured symptom is the 13.5-point top-12 RB spread.
- **The in-repo precedent exists:** long-TD 40+/50+ rates are already per-player and EB-shrunk with **K=12** in the same file. Cite it as the pattern.
- Named targets: rushing first-down rate, receiving first-down rate, 100/200 rushing-yard game rate, 100/200 receiving-yard game rate, 300/400 passing-yard game rate.
- **Measure year-over-year stability of each rate FIRST, with EB shrinkage and K chosen by cross-validation.** **This is the real question — if a rate is not stable, the league average IS the right answer and that is a valuable null.** Bar for stability: state it before running; the draft suggested YoY under ~0.3 after shrinkage as a fail.
- Then grade the re-ordered board in the paired harness, **weekly mode** (this is a shape claim).
- **`apply_bonuses.py` is in the `run_all.py` chain and therefore FROZEN. Build a parallel research module and PROPOSE. Do not edit.**
- **Primary endpoint:** league points, corrected grader, weekly mode. Bar: placebo 95th percentile or +20, whichever is higher.

**H5a — The WR archetype question, resolved in VOLS.**
Under this league's exact multipliers, which WR archetype nets more: the high-volume medium-aDOT chain-mover (paid twice per catch via the 0.5 receiving FD bonus) or the deep threat (cumulative 40+/50+ TD bonuses, more 100-yard tier hits, worse catch rate)?
- Test: score every 2015–2025 WR season under this league's exact table, both as a season total and as a **weekly-distribution-transformed** total (which `weekly_league.parquet` makes exact, not approximate). Split by aDOT tercile.
- **[CORRECTED] Report the answer in VOLS against the league-scored WR replacement level, not in raw points.** And **report the ceiling as absolute league-scored p80 minus replacement, NEVER as an upside multiplier — per C13, multipliers measure spread relative to price, and reading one as a ceiling is a closed error in this repo.**
- **State your prior and test it:** the high-volume profile wins on expected points and the deep profile wins on ceiling.
- **Falsification:** no separation, in which case aDOT is not an archetype axis worth carrying.

**H5c — The sack tax: staleness, invisibility, and shrinkage — NOT existence. [REWRITTEN.]**
**The per-QB EB-shrunk sack rate already ships** (`apply_bonuses.py`, K=12, pooled 2023–25) and is worth up to **−25.9 points**, re-ranking Drake Maye **eight spots** on the 2026 board (2nd on `custom_proj_points`, 10th on `total_points`) [V]. It is the best existing example of §7.6's thesis. **Do not rebuild it.** Three real questions:
- **(a) Staleness.** The rate is backward-looking and pooled across three seasons, so it describes the QB's *old* line and *old* team. **Does sack rate carry for a QB who changed teams or whose OL turned over?** This is where H2e lives.
- **(b) Invisibility.** Sacks are absent from both the MC's weekly proxy and `weekly.parquet`'s scoring, so **no backtest in this repo could previously see a −42 pts/season term.** Fixed by T0.3 — then re-examine.
- **(c) Shrinkage.** Is K=12 right? **Cross-validate it; do not assume.** Does NGS `avg_time_to_throw` (free, weekly, stabilizes ~2 games before sack rate) improve the per-QB sack-rate *forecast* over last year's shrunk rate?
- **Cheap checks first, both of them:** regress ADP residual on prior-season sack rate (is the market already pricing it?), **and regress our own board's QB ordering on it (are WE already pricing it?)**. The second check is what stops you double-counting.
- **Primary endpoint:** league points in VOLS terms, corrected grader. Bar: placebo 95th percentile or +15, whichever is higher. **C12 guardrail applies — replacement stays QB12.**

**H5d — Full-bonus weekly scoring inside the MC. [DEMOTED TO SECONDARY, propose-only.]**
The MC's weekly volatility uses base scoring only, so volatility SHAPE and projection MEAN come from two different scoring systems (§2.3).
- **Demoted because the linearization happens upstream in `apply_bonuses.py` (H5b), and the MC re-centres on `total_points` so it cannot recover what was already averaged away.** Fix the upstream defect first; only then is this question meaningful.
- **[CORRECTED TRAP] The 62.1% OOS benchmark was established against a BASE-SCORED panel. It must be re-established on `seasons_league.parquet` before any full-bonus comparison means anything. Do not report degradation against a base-scored target — that is an apples-to-oranges comparison that would kill a good change.**
- Test: re-run `05_distribution.py`, `06_finish_odds.py`, `08_backtest_sim.py` and the OOS 2014–2018 check with full-bonus weekly scoring, against the re-established target.
- **This is a proposal about a FROZEN file. Measure it; do not ship it.**
- **Falsification:** OOS calibration degrades against the correctly re-established target. **The existing calibration is hard-won; protecting it beats any theoretical improvement.**

**H5e — League-scoring xFP.** (Built in T0.9.) Does an xFP computed under this league's table beat nflverse standard-scoring xFP as a role signal in the composite?
- **Cheap check first:** do the two xFPs rank players nearly identically in the draftable range? If yes, stop.
- **Primary endpoint:** league points, or a materially better `role_pct` for the **171 players who currently have no xPPG** — but if you claim the second, name and reproduce the failure mode BEFORE the points test and report the points number regardless (S14).

---

### WS6 — Fusion with the existing stack

**Nothing in WS1–WS5 is worth anything until it is expressed as a change to a specific number in a specific file, graded in the corrected harness, and sensitivity-swept.**

**The fusion decision tree — every proposed finding routes through this:**

1. **Is it a FACT or a FORECAST?** Facts (injury designations, depth-chart position, a coaching change that actually happened, a PUP/NFI placement) need no backtest and belong in the advisor context as facts, clearly labelled. Forecasts need the full grading treatment. **Precedent: injury FLAGS were the one thing to survive an entire research line, precisely because they are facts.** **C16 is the reason no forecast is attached to a health fact.**
2. **Does it move a RANK or does it inform PROSE?** L8: **enforce rules in the data, not in prose** — a strong prose gate reliably loses to a big salient number. But L48b's counter-lesson: **advisory prose is still a claim, and it was once backwards.** Prose-only is a lower bar, not no bar.
3. **Which layer does it belong in?** In increasing order of risk:
   - a **new advisor READ** (prose + a precomputed number) — lowest risk, the COLD/PUNT/DART/HANDCUFF pattern
   - a **bounded rank nudge** — the `cohort_pull.py` pattern (SCALE, DEAD zone, CAP, GATE, FREEZE the top N). **Copy this pattern; it exists precisely to keep a signal from doing damage.**
   - a **new committed CSV** consumed by the app (`cohort_data.csv` / `role_data.csv` / `sos_data.csv` pattern) — required for anything nflverse-derived, because nflreadpy is not installed in production
   - a **composite weight change** — high risk, requires LOSO-CV like L45
   - a **frozen-file change** — **propose only, never edit**
4. **Does the state it fires on actually arise under the current policy (S5)?** Measure prevalence with the *real* advisor policy, not an ADP-drafting proxy.
5. **Is the concept duplicated anywhere?** (L52/L53: the snake-pick schedule lived in FOUR places and was wrong in three.) **Grep for every place the idea is computed BEFORE editing — see T0.7 for role and T0.8 for everything else. A partial fix to a duplicated concept is worse than no fix.**
6. **What test pins it?** Every shipped behaviour has a test. New reads need new suites. L26: **closed-loop whole-draft testing finds omission bugs that per-step assertion testing structurally cannot** — 384/384 per-pick invariants passed while a full draft finished with no kicker.

**Fusion questions, each with a numeric bar (S14 — "a workstream with no falsification condition is not a workstream" applies to WS6 too):**

- **F1 — Does a participation-based or depth-chart-based role signal REPLACE `role_pct` or sit beside it?** **Gate: report the agreement rate between the new signal and each of the five existing role sites (T0.7). If agreement ≥95% in the draftable range, the change is cosmetic — report it as such and do not ship.** Priority population: the 85 switched-team players and ascending same-team leads where `role_pct` currently *is* the VOLS percentile, so a real role signal competes with nothing.
- **F2 — Should the discarded signals in §2.5 be revived?** `proj_divergence` and the new FantasyPros `sd`/`best`/`worst` are both free uncertainty measures the risk dial could use. **Expect a near-null on the `proj_divergence` half — per C17 the three 2026 sources correlate +0.964 to +0.987 over the top 180, so it has almost no variance in the draftable range. The `sd`/`best`/`worst` half is genuinely new dispersion the board has never had.** **Bar: does either predict realized outcome variance above the MC's existing depth-dependent sigma? State the improvement in calibration terms with a CI.**
- **F3 — Where does an in-season detector live at all?** The app is a *draft* board with no in-season surface. **Answer explicitly, and the answer must include a named product surface (a second Streamlit page? a separate CLI? a weekly notebook?) plus a weekly runtime cost in minutes and the committed-CSV regeneration steps required.** No hand-waving.
- **F4 — Reachability through the survival machinery (S9).** Run every pre-season finding through `advisor._survival_prob` and report how many flagged players are realistically available at this roster's picks. **Bar: a pre-season finding is REACHABLE only if ≥2 flagged players are available at this seat's picks in ≥50% of simulated drafts at ≥3 of the 5 tested slots (the slot is unsettled). Below that, the finding is reported as TRUE-BUT-UNREACHABLE and is not proposed for shipping.**
- **F5 — Does FFC validate `_adp_scale`?** **[REFRAMED] The curve has already been backtested** (`44_`: −3.0 pts, CI [−5.1, −0.9], 80.5% identical; it shipped on correctness grounds). **What is new is a SECOND INDEPENDENT SOURCE for the dispersion** — FFC's per-player `stdev` on a 12-team PPR corpus matching the user's exact format. **Bar: compare the FFC stdev curve point-by-point against `_SCALE_S` with a stated tolerance (e.g. within ±30% at each anchor). Note the limit: FFC serves only ~205–247 players, so it cannot validate the `_SCALE_ADP = 165.5` anchor at all — say so rather than extrapolating.** This is a validation of the fit, not a re-run of the decision.
- **F6 — Where does the forward-only health FACT feed live?** (H2f's factual layer.) Sleeper `injury_status` is already reachable from production. **Name the surface, the refresh cadence, and the text the advisor sees. No backtest; cite C16.**

---

## 9. THE 2026 TEST PROTOCOL

The user wants to test this on 2026. This is a hard requirement, and it must be designed **before** any 2026 data exists so it cannot be tuned after the fact.

### 9.1 Pre-register everything, in writing, before Week 1

Write `icm/work/entanglement/PREREGISTRATION.md` **before the season starts**, containing:
- Every hypothesis you intend to test on 2026, stated as a directional prediction with a numeric threshold.
- The exact metric, the exact population, the exact success threshold, **the declared PRIMARY endpoint (S14), and the declared discovery slice and replication slice (S2).**
- The exact data snapshot dates and how they will be captured.
- **The pre-specified in-season tier-change threshold** (or an explicit commitment to report the full threshold curve).
- **A named list of specific 2026 players your pre-season findings flag** — **[CORRECTED] each stated as a direction RELATIVE TO A RECORDED PRICE**: *"Player X finishes above his 2026-08-07 ESPN ADP-implied positional finish of N,"* with N and the ADP snapshot file both written down. "Barkley will be good" cannot fail and is not admissible. **Also record the board's own `rank_composite` for each named player as a covariate**, so a call that merely tracks the board (which already contains ADP at W_A 0.06, ECR at W_E 0.13 and 50% Vegas) can be identified as such after the fact.
- A statement of what result would make you abandon each line.

**[CORRECTED] Lock it properly.** A local commit is amendable and rebaseable and its timestamp is author-controlled. **Commit `PREREGISTRATION.md`, PUSH to `origin/main`, then record the resulting commit SHA and the push timestamp inside `icm/work/HANDOFF.md` in a separate later commit.** A prediction made after the fact is not a prediction.

### 9.2 Look-ahead leakage: the specific traps in this project

- **Snapshot every input at the time it was knowable.** ADP as of the draft date, not end-of-season ADP. Depth charts as of the week in question, not the latest snapshot. **Vegas totals from week 1–2, not season averages — this exact leak killed the "good offense" gates (S7).**
- **`tools/archive_projections.py` must be run before Week 1** and verified to have written a dated CSV with **>400 rows** into `data/projection_archive/` (which currently contains only a subdirectory listing). **This window closes permanently when the season starts** (§0.5 exception 1).
- **Build a weekly snapshot job.** Capture, dated and immutable: ESPN ADP, FFC ADP + stdev (with the browser User-Agent), Sleeper `adp_ppr` + `adp_std`, FantasyPros ECR + `sd`/`best`/`worst`, depth charts, injury designations and `injury_status`, and the pbp / participation / NGS / snap-count weekly pull. **A season of dated snapshots is the single most valuable asset this research programme can build**, because it is the thing that cannot be reconstructed later — exactly the lesson of the unreconstructable FantasyPros projections. **And per WS3's revised-data bias, it is the ONLY clean lead-time instrument this project will ever have.**
- **Never use a season-averaged variable to predict an outcome inside that season.**
- **Beware backfilled sources.** Sleeper's historical projections are backfilled and will look accurate while meaning nothing.

### 9.3 What sample size makes a 2026 finding credible

**Be blunt with the user: one season is a small sample, and 2026 alone cannot confirm anything.**

- **Pre-season findings:** one season gives roughly 100–200 priced player-seasons in the relevant bands and maybe 8–10 regime-change events. **A 2026 result can FALSIFY a finding but cannot CONFIRM one.** Design 2026 as a **falsification test**.
- **In-season detection:** genuinely informative, but **[CORRECTED] the effective n is the number of independent tier-change EVENTS — dozens — not thousands of player-weeks.** Player-weeks are massively autocorrelated within player and within week (a league-wide environment shift moves everyone at once; one heavy injury week creates a burst of correlated events), and events cluster by cause. **Bootstrap precision and recall over EVENTS; block over WEEKS for lead time. Report the event count as the effective n. A single season plausibly supports 30–100 independent events, so expect precision CIs on the order of ±10–15pp — say so rather than reporting a point estimate.**
- **Minimum credible cell sizes: treat n<40 CLUSTERS as directional-only** (S11) and say so in every sentence that cites it. The project's most famous false finding had n=38 and a bootstrap P of 1.00. The "missed time + proven" BUY cell is n=22 and the 350+ touch flag is n=18 — both explicitly labelled directional by their own authors.
- **Multiple comparisons:** this charter names 25+ hypotheses before per-position and per-band splits, and WS1's reliability sweep adds ~25 more tests. **Pre-register the list, report ALL of them including failures, and apply Benjamini-Hochberg FDR at q = 0.10 across all PRIMARY endpoints, printing the adjusted threshold and both raw and adjusted verdicts (S14).**

### 9.4 The 2026 scorecard

Produce, at end of season, `icm/work/entanglement/2026-SCORECARD.md` with:
- Every pre-registered prediction and its outcome. **[CORRECTED] Pre-season hypotheses have exactly three verdicts on 2026: FAIL, NOT-FALSIFIED, INCONCLUSIVE. There is no PASS for a pre-season hypothesis on n=1 season** — §9.3 says one season cannot confirm, so §9.4 must not offer a verdict that reads as confirmation. **Only in-season detection metrics (event-level) may be reported as PASS, and only with event-clustered CIs.**
- The named-player list from §9.1, each with its recorded price, its `rank_composite` covariate, and what actually happened.
- The in-season detector's precision, recall and median lead time, by position, with event-clustered CIs.
- A per-week log of every alert the detector would have fired, with the mechanism and the expected reversion date, so the user can read them in hindsight.
- **A section titled "What I got wrong" — mandatory, non-empty.**

---

## 10. DELIVERABLE

Produce a **Blueprint** at `icm/work/entanglement/BLUEPRINT.md`, plus supporting research scripts and results files under `icm/work/mc_research/` (continuing the `46_`, `47_`… numbering, each with a matching `results_NN_*.txt`).

**Do NOT write scattered summary/findings .md files.** One Blueprint, one pre-registration, one scorecard, and the numbered results files. That is the whole documentary output.

**The Blueprint must contain, in this order:**

1. **Executive summary, ≤2 pages, leading with what does NOT work.** State plainly whether "situation step changes are pre-season predictable" survived contact with the data. If the answer is "only in the variance, not the mean," say exactly that in the first paragraph. **Also state on page 1 whether the league-scored panel changed any conclusion relative to base PPR** (the T0.3 falsification), and **the MDE of the instrument you actually built** — because if the MDE exceeds your thresholds, that is the most important fact in the document.
2. **The verdict table** — every hypothesis, its **PRIMARY endpoint in league points**, its **season/event-clustered CI**, its **effective n in clusters**, its sensitivity sweep shape, its **firing rate (% of drafts identical)**, its **per-slot spread**, its **BH-adjusted verdict**, and a **PASS / FAIL / DIRECTIONAL-ONLY / NOT-TESTABLE / TRUE-BUT-UNREACHABLE** verdict. One row per hypothesis, plus a row count and the placebo 95th percentile printed at the top of the table. **This table is the deliverable; everything else is support.**
3. **The data-availability table** from WS0 — including the resolved participation question with `route`'s true semantics, the `load_depth_charts` schema break, the FFC User-Agent and missing-2025 findings, the absent PUP/NFI history, the priced-panel depth per season, and `population.json`.
4. **The architecture proposal** — per position, what the sub-model is, which layer it lives in, what CSV it commits, what test pins it. Explicitly routed through the WS6 decision tree.
5. **The in-season system design** — the two-gate rule with its named independent mechanism feed, the change-point method, the suppression rules (TE settled by C14), the reversion-date mechanic, where it lives in the product (F3), and what it costs to run weekly.
6. **The fusion plan** — file by file, number by number, with the sensitivity sweep for each proposed change and an explicit statement of which are FACTS (no backtest) and which are FORECASTS (backtest required).
7. **What is obtainable free and programmatically vs what is not** — a clean table, because the user asked for "every statistic, every news article, every change" and deserves a straight answer. **Be specific and do not soften §3.4.** Carry these three "no"s explicitly, with the evidence beside each: **beat-reporter text** — no free licensed corpus, no ground truth, do not build; **PUP/NFI history** — verified absent from nflverse injuries (no preseason rows; PUP appears once league-wide in a week-1 roster file); **coordinator/scheme data** — hand-curated only, and the hand-curated file supports **n=31** carryover events. Add: **per-player routes run do not exist in free data**, and the free ceiling is pass-snap participation with a blocker conflation.
8. **The 2026 test protocol**, with the pre-registration file written, committed, and **pushed**, and its SHA recorded.
9. **The kill list** — everything you tested that does not work, with the numbers. **This section must not be empty.** Three lines have already been killed in this project and each closure made the system better by removing a maintenance burden and a false sense of coverage. **A charter this ambitious that returns zero nulls has not been honest.** Expected residents based on the re-scoping above: H2b's premise gate, H2e, the adjectival-camp-report test, and quite possibly H2a and H3c.
10. **What you could not do, and why** — budget, data, or time. Name it. **K and D/ST sub-models are a stated scope cut and belong here (§6).**

**Style requirements:**
- Say which parts are MEASURED and which are JUDGMENT. Do not dress one as the other (L54).
- Put the measurement in front of the reader before the judgment call.
- Report the SHAPE of skewed distributions, not just the middle — and when the robust statistic and the EV statistic disagree, **that gap is the signal** (L29).
- Cite absolute file paths and result files for every number.
- **Distinguish "I read this in a prior results file" from "I re-ran this."** The scoping that produced the first draft of this charter ran **no new analysis**, and that is exactly how the `route`-column error and three already-shipped-feature proposals survived into it. The four adversarial reviews caught them by running code. **Verify or label. Every claim about what the repo currently does must be grepped, not asserted.**
- No emojis.

**Scope realism, stated as an instruction:** the user wants a system that uses "every statistic, every news article, every change." Be ambitious in the Blueprint's architecture — design the full system. But be ruthless in the verdict table about which parts are reachable with free, programmatic data and which are aspiration. **A Blueprint that describes a beautiful system built on data that does not exist is worse than a smaller one that ships.**

**Run one or two lines end to end including the paired grade, rather than half-running six.** The feasibility-driven priority order, confirmed independently by all four reviews:

1. **WS0 in full.** Non-negotiable. Without T0.3 (league-scored panel), T0.4 (three-arm corrected grader) and T0.6 (placebo), every number downstream is uninterpretable — and two of the highest-EV hypotheses would return confident false nulls.
2. **WS5** — the only workstream whose data is confirmed present and complete. H5f, H5b and H5c need no new pull beyond the 11-season pbp job in T0.3. Start with **H5f**.
3. **WS3** — with the pass-snap proxy substituted for routes and the benchmark replaced. A season of player-weeks is a real sample, and the 2026 snapshot job is its load-bearing deliverable.
4. **H2g** — scoped to 2025 only. A validity fix, not a prediction.
5. **H2a / H2b / H2c — premise gates only.** They will likely die at the gate, cheaply, which is the correct outcome and a legitimate kill-list entry.
6. **H2e** — pre-registered null, re-aimed through the sack term, or dropped to buy budget.
7. **H2f** — restructured to a forward-only fact feed. No forecast.

---

## 11. DESIGN DECISIONS — where the reviews disagreed, and what was chosen

These are recorded so you do not re-litigate them, and so you can see the reasoning if you find evidence against a choice.

**D1. Hindsight-optimal weekly lineups (rigor) vs ex-ante weekly lineups (fantasy-specificity).**
Rigor argued the grader must set an optimal lineup each week from players who actually played, to stop the season-total scorer from being blind to unavailability. Fantasy-specificity argued that hindsight-optimal lineups delete the start/sit value a detector exists to create, and bias toward high-variance rosters no manager can execute. **Both are right about different instruments.** Chosen: **draft grading uses weekly HINDSIGHT-optimal lineups** — it fixes the availability blindness, and it keeps draft evaluation from being contaminated by whatever start/sit policy you happen to bolt on, which is the standard perfect-manager convention. **In-season detector grading uses EX-ANTE lineups**, because there start/sit IS the product, and the hindsight total is reported alongside purely as a ceiling with the gap called out. Two different questions, two different conventions, both stated.

**D2. Base the grader on `44_` (redundancy) vs rebuild three arms (rigor) vs add a league-scored panel (fantasy).**
Not actually in conflict, but the layering matters. Chosen: **`44_` supplies the opponent model and the VONA policy** (it is the only script whose header documents both corrections); **`33_` supplies `optimal_lineup` and actual-points scoring**; **rigor's three-arm structure supplies the endpoint definition**; **fantasy's league-scored panel supplies the currency.** The legacy mode exists solely to reproduce +5.2 as a self-test — and per rigor R6, the corrected mode is expected to disagree, so only legacy mode carries a stop-and-fix condition.

**D3. The charter's own §3.2 said routes are free; §5 and §7 said they are not.**
The feasibility review ran the code and found a third answer: `route` exists but is a per-play label for the targeted receiver, and the "100% coverage" figure was an empty-string artifact. **Empirical verification supersedes both recalled beliefs.** Chosen: routes are **not** obtainable free; the free ceiling is pass-snap participation from `offense_players`; §5, §7.11 and every dependent hypothesis were rewritten downward accordingly, and §7.11's claim that route data is "the single highest-leverage data investment in this programme" was demoted in favour of WS5. T0.1 remains as a half-day confirmation, not as the question that determines feasibility.

**D4. Thresholds: +25/+20/+15 (draft) vs "+25 is inside the null's own CI, MDE ≈ +45 at n=10 and ≈ +90 at n=4" (rigor) vs "run a power analysis" (feasibility).**
Chosen: **all thresholds are PROVISIONAL (S15)**, expressed as "the placebo 95th percentile, or the stated number, whichever is higher," with the power arithmetic shown and **DIRECTIONAL-ONLY reported rather than PASS whenever the bar sits below the instrument's MDE.** This is the honest reconciliation: it neither pretends the design can resolve +25 nor abandons the ambition, and it puts the decisive number (the placebo distribution) on day two.

**D5. H2f's factual layer: test it as a forecast (draft) vs route it as a fact (redundancy) vs it is not in the data at all (feasibility).**
All three converge on the same action for different reasons. Chosen: **route as a forward-only FACT**, keep one prevalence measurement, cite C16 as the reason no forecast is attached. Feasibility's finding (no preseason rows, PUP appears once league-wide, no historical before/after price) makes the forecast test impossible even if it were desirable, which it is not.

**D6. Which hypotheses to kill outright vs demote.**
Chosen: **demote rather than delete** where the premise test is cheap and informative (H2a, H2b, H2c → premise gates), and **delete** where the test cannot answer its own question (the `news_updated` adjectival test, which is a null by construction at 8,135/12,204 coverage). H2e is kept as a pre-registered null but re-aimed at the sack term, where it has a real league-specific consequence, with explicit permission to drop it for budget. H4-QB is collapsed into H5c because its falsification targeted a strawman the repo does not contain.

**D7. Where the "already shipped" problem gets fixed.**
Four separate instances were found across two reviews (per-QB sack rate, the 13-simulator sprawl, the five role sites, the yardage-tier league averages). Rather than patching each hypothesis in isolation, this is elevated to **S13 (grep before you propose)** plus two mandatory WS0 tasks — **T0.7 the role census** and **T0.8 the already-shipped census.** The failure mode is symmetric with S5: a rebuilt feature graded against a board that already prices it returns a **false null on a real edge**, which then gets recorded as a closed line and does permanent damage.
