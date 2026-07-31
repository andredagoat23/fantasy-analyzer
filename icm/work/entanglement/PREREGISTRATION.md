# 2026 PRE-REGISTRATION — ENTANGLEMENT PROGRAMME

```
================================================================================
                    *** DRAFT — NOT YET LOCKED ***

This file is a DRAFT until BOTH of the following happen:
  1. Section 6's PLACEHOLDER is filled with the named-player list built from
     the 2026-08-07 ESPN ADP snapshot (data/snapshots/2026-08-07/), AFTER the
     league draft on 2026-08-07.
  2. The file is committed, PUSHED to origin/main, and the resulting commit
     SHA + push timestamp are recorded in icm/work/HANDOFF.md in a separate,
     later commit (charter 9.1: a local commit is amendable and its timestamp
     is author-controlled — a prediction made after the fact is not a
     prediction).
Until both are done, nothing in this file counts as a pre-registration.
Deadline: locked BEFORE Week 1 (first 2026 game is Wed 2026-09-09).
================================================================================
```

**Draft-state push (2026-07-31):** this file was committed and pushed to `origin/main` in DRAFT
state at the audit fix pass, to timestamp the P1–P8 hypothesis-level predictions (which exist
today); the SHA is recorded in `icm/work/HANDOFF.md`. That push is NOT the lock — the lock is the
second push after the 2026-08-07 named-player fill, per the box above.

Charter: `icm/work/research-blueprint-prompt.md` sections 9.1–9.4. Companion document:
`icm/work/entanglement/BLUEPRINT.md` (all evidence citations live there). Every number below is
[R] from the named results file under `icm/work/mc_research/` unless marked otherwise.

---

## 1. GLOBAL RULES (bind every hypothesis below)

- **Verdict vocabulary (charter 9.4):** pre-season hypotheses on 2026 have exactly three verdicts
  — FAIL, NOT-FALSIFIED, INCONCLUSIVE. There is NO PASS for a pre-season hypothesis on n=1 season.
  Only in-season detection metrics (event-level) may be reported PASS, and only with
  event-clustered CIs.
- **Effective n:** in-season effective n = independent tier-change EVENTS (expect 30–100 → expect
  precision CIs on the order of ±10–15pp and say so); pre-season effective n = 1 season cluster.
  n<40 clusters = DIRECTIONAL-ONLY in every sentence that cites it (S11).
- **Multiplicity:** the scorecard applies Benjamini-Hochberg FDR at q = 0.10 across ALL primary
  endpoints listed in section 3, printing the adjusted threshold and both raw and adjusted
  verdicts (S14). Each hypothesis has ONE primary endpoint, declared here; no OR-thresholds.
- **Thresholds:** every points threshold is bounded below by the measured placebo bar,
  p95 = +5.4 league pts (bootstrap CI [+0.5, +8.4]) [R results_50], and every points verdict
  carries the instrument MDE (±53 league pts at n=4 season clusters, t-based [R results_49]; the
  MDE for any new treatment is recomputed from its own clustered SE, never reused).
- **Currencies:** league scoring primary, base PPR secondary (S12), graded from the T0.3 panel.
- **Prices:** 2026 prices = the draft-day ESPN ADP in `data/snapshots/2026-08-07/espn_kona.csv`.
  Historical 2025 prices anywhere in supporting analysis are the Sleeper adp_ppr instrument
  (T0.2 repair) and must be labelled as such.
- **Leakage rules (charter 9.2):** every input snapshotted at the time it was knowable; Vegas
  totals from the week-1/2 snapshot lines, never season averages; no season-averaged variable
  predicts an outcome inside its own season; Sleeper historical projections are backfilled and
  are never used as forecasts.
- **Revised-data rule (WS3):** all in-season lead-time and precision claims for 2026 are computed
  from the DATED Tuesday snapshots, not from the retroactively-revised nflverse archive. The
  snapshot-vs-later-archive diff is itself recorded as the measured revised-data bias.

## 2. SNAPSHOT-CAPTURE PLAN (the instrument; charter 9.2)

Tool: `/Users/natearaskog/fantasy-analyzer/tools/weekly_snapshot.py` (built and smoke-tested
2026-07-31; immutable dated dirs + MANIFEST.json; fail-safe per-source hard asserts; ~10–20 s per
run) [R results_61]. First snapshot exists: `data/snapshots/2026-07-31/` (6/6 sources ok, 1.77 MB).

- **Cadence: every TUESDAY, year-round** — the measured seam that captures completed week W after
  MNF + the nflverse refresh but BEFORE Wednesday waivers and any W+1 practice reports
  [R results_61 §5, measured vs judgment labelled there].
- **Mandatory extra run: FRIDAY 2026-08-07 (draft morning).** `data/snapshots/2026-08-07/` is the
  recorded-price file this pre-registration's named-player list is stated against. The Tuesday
  Aug 4 run does not substitute.
- Scheduled runs: Aug 4, Aug 7 (draft morning), Aug 11, 18, 25, Sep 1, Sep 8; first in-season
  snapshot Tue Sep 15 (week 1 completes Mon Sep 14). Preseason sources (6): schedules+Vegas lines,
  espn_kona (ADP + ownership momentum + projection components), ffc_adp (+stdev), sleeper (ADP +
  live health facts incl. PUP/NFI), fp_ecr (+sd/best/worst), depth_charts (latest dt). In-season
  adds (4): injuries, snap_counts, participation, fp_ecr_week — each season-to-date so consecutive
  snapshots measure the revision bias directly.
- **Ritual:** run, then commit AND push the new dir the same day. An unpushed snapshot is one disk
  failure from not existing.
- **Cadence self-check (pre-stated, falsifiable):** if the just-completed week W is absent from a
  Tuesday snapshot's injuries/snap_counts/participation manifests twice in the first three
  in-season weeks, move to Wednesday 06:00 ET and record the change [R results_61 §5].
- Recommended before Week 1 (not yet done): add the ~15-line NGS fetcher [R results_61 §7].
- **Sleeper mock-corpus refresh (charter §0.5 exception 2) — DONE 2026-07-31**: 300 one-QB /
  2,001 total drafts (from 111 / 1,162). The L51 curve recheck on the fattened corpus
  (`results_62_dispersion_recheck.txt`) holds in 7 of 8 buckets; no pre-freeze change. An optional
  incremental re-crawl closer to the draft remains cheap (the crawler is resume-safe) but is no
  longer load-bearing.

## 3. THE 2026 HYPOTHESES (directional prediction · threshold · primary endpoint · slices · abandon condition)

**P1 — H2g: depth chart vs projection in disagreement rooms.**
- Treatment set: the 10 disagreement rooms frozen in `results_55_h2g.txt` section E against the
  2026-07-31 chart snapshot (dt=2026-07-31T09:40:30Z): LV QB, NE RB, SEA RB, WAS RB, CAR TE,
  LA TE, CHI WR, CLE WR, DEN WR, JAX WR — named players and ADPs recorded there.
- Directional prediction (from the 2025 evidence, which favored the projection): **the
  projection's No.1 wins at least 6 of the 10 rooms.**
- Primary endpoint: realized 2026 within-room volume No.1 (carries+targets; attempts+carries for
  QB). Secondary: league-scored points-above-price at the 2026-08-07 ESPN ADP.
- Slices: discovery = 2025 (results_55); replication = 2026 (this test).
- Thresholds: chart wins ≥7/10 → the REPLACE/HYBRID line revives and gets a paired grade;
  chart wins ≤4/10 → the replace line dies permanently (flag-only forever); 5–6 → INCONCLUSIVE.

**P2 — H2a: playcaller 11-personnel carryover.**
- Population: the 2026 carryable caller-change events, derived from `data/playcallers_2026.csv`
  by the exact rule of `56_premise_gates.py` (prior in-window history at a different team).
  TO FILL AT LOCK TIME: enumerate the 2026 carryable moves by name here (the rule is frozen; the
  list is mechanical). Expected order: single digits of events.
- Directional prediction: **the incoming caller's prior-stint 11-personnel profile (within-season
  z-scored) predicts the receiving team's 2026 11-personnel rate better than the team's own 2025
  rate** (discovery: dR2_adj +0.152 [+0.040, +0.318], n=31 [R results_56]).
- Primary endpoint: pooled squared-error comparison (caller-augmented vs team-prior null) on the
  2026 events, r11 only (the discovery effect was ~entirely 11-personnel).
- Slices: discovery = 2019–2025 moves; replication = 2026 moves.
- Thresholds: caller-augmented beats the null on r11 (pooled dR2 > 0) → NOT-FALSIFIED and the
  manual 2014-extension of `playcallers_hist.csv` becomes justified; pooled dR2 ≤ 0 → FAIL and
  the H2a line closes (it is already boundary-fragile). No board input either way; no points test
  at this n.

**P3 — H5a: the high-aDOT WR tax, knowable form.**
- Population: 2026 priced WRs (draft-day ESPN ADP) with a 2025 aDOT on ≥25 targets; terciles on
  PRIOR-season aDOT; greedy log-ADP matched T3-vs-T1 pairs (caliper 0.25), exactly
  `52_h5a_wr_archetype.py`'s S-E variant.
- Directional prediction: **T3 − T1 < 0 in realized 2026 league VOLS** (discovery: knowable form
  −10.5 [−23.6, +2.5]; same-season form −20.2 [−31.1, −8.5] [R results_52]).
- Primary endpoint: mean matched-pair league-VOLS gap, 2026 only (sign test — one season
  falsifies, never confirms).
- Slices: discovery = 2015–2025; replication = 2026.
- Thresholds: gap ≥ 0 → FAIL (the prose caution is removed); gap < 0 → NOT-FALSIFIED (still
  prose-only; a rank nudge additionally requires the weekly-mode paired grade clearing
  max(+20, placebo p95)).

**P4 — H5b: position-level bonus-rate biases hold.**
- Directional prediction: in 2026 realized league rates, **all four signs repeat**: QB FD/carry >
  all-position rate; RB FD/rec < all-position rate; WR FD/rec > all-position rate; RB rec-tier
  rate < league rate (each sign was stable 12/12 seasons 2014–2025 [R results_53 §3]).
- Primary endpoint: count of the 4 signs that repeat in 2026.
- Slices: discovery = 2014–2025; replication = 2026.
- Thresholds: 4/4 or 3/4 → NOT-FALSIFIED (the position-level correction proposal proceeds to the
  paired grade); ≤2/4 → INCONCLUSIVE→FAIL review (the bias-class fix is re-examined before any
  proposal).

**P5 — H5c: sack-rate shrinkage.**
- Directional prediction: **the nested-K pooled-3yr forecast (K*≈768) beats the shipped K=12
  construction on 2026 QB sack rates in points-MAE** (M3 vs M0; discovery +0.17 [−0.40, +0.73]
  [R results_54]).
- Primary endpoint: M0−M3 points-MAE on 2026 QB-seasons with throws ≥200 in both 2025 and 2026.
- Slices: discovery = 2017–2025; replication = 2026.
- Thresholds: positive → NOT-FALSIFIED (the K re-rank goes to the paired harness at
  max(+15, p95), with the shared-K/long-TD guard); negative → FAIL (K stays 12; line closes).
  avg_time_to_throw stays dead regardless (killed at discovery).

**P6 — WS1 mover overlay (pass-snap participation).**
- Directional prediction: **2026 RB+WR priced team-changers with HIGH prior pass-snap
  participation outscore LOW, in league points above price** (discovery: RB +19.4 [−16.0, +52.2],
  WR +15.9 [−11.1, +42.7], both CIs through zero — sign-consistent only [R results_58]).
- Primary endpoint: pooled HIGH−LOW league points above draft-day price, 2026 movers.
- Slices: discovery = 2017–2025 RB (and the WR replication); replication = 2026, both positions
  pooled.
- Thresholds: pooled ≤ 0 → FAIL (overlay dies); > 0 → NOT-FALSIFIED, still DIRECTIONAL-ONLY, no
  board action (a board action would need clusters this design cannot produce). The target-share
  overlay is NOT preregistered — it already failed replication (sign flip) and is on the kill
  list.

**P7 — H3d blacklist, live-data replication.**
- Directional prediction: on 2026 DATED snapshots (not the revised archive), **ranking
  tier-change candidates by a YPC or TD-rate spike does not beat ranking by dumb window volume
  within the same gated universe** (discovery: ypc −0.038 [−0.074, −0.003]; td −0.016
  [−0.053, +0.024] [R results_57 §4b]), and the family precision ordering is preserved.
- Primary endpoint: spike-ranked minus volume-ranked precision at matched per-season alert
  volume, tau=0, league scoring, 2026 events, event-clustered.
- Slices: discovery = 2015–2024 (+2025 directional check); replication = 2026 live snapshots.
- Thresholds: spike−volume > 0 with CI excluding 0 → the blacklist encoding is revisited;
  otherwise NOT-FALSIFIED and the blacklist stays encoded.

**P8 — WS3 detector (conditional on the post-draft build; pre-registered NOW so the build cannot
tune its own bars).**
- Ground truth: rest-of-season league-scored points-above-weekly-replacement (replacement =
  `utils.startable_counts` on realized weekly `pts_league`); absent week = 0 − replacement;
  detection after week W affects week W+1 lineups only; STRICT gap week (outcome = W+2 onward);
  no waiver resolves before the W+1 processing date.
- **Tier-change threshold commitment: the FULL threshold curve tau ∈ {−3..+3} PAR/week is always
  reported, with tau = 0 as the primary row** — no single cherry-picked cutoff, ever (this
  sentence is the charter-required pre-specification; the curve convention is already exercised in
  results_57 §3).
- H3a primary: mechanism-gated minus ungated precision at matched alert volume, event-clustered.
  Directional prediction: gated > ungated. Bar: **+15pp**. Mechanism feed: `load_injuries`
  report/practice status, roster deltas, transactions, coaching CSVs — the teammate-usage-derived
  arm runs separately and can NOT rescue the gate.
- H3b primary: median lead-time advantage of CUSUM over 3-game rolling average at matched FPR,
  blocked over weeks. Directional prediction: positive. Bar: **≥1.5 weeks**.
- H3c: earned (targets-per-pass-snap step) vs vacated (participation step) alerts have different
  post-return reversion; falsification = identical profiles → drop the distinction.
- All 2026 in-season results are computed from dated snapshots; precision/recall are reported
  with event counts as the effective n; the first output is the BASELINE (what a plain 3-game
  rolling league-PPG manager earns), before any detector claim.
- Suppression: the TE rule is settled (C14) and encoded, not re-measured; RB/WR suppression
  rules are graded by the precision of the REMOVED alert set.

**Explicitly NOT preregistered (facts need no backtest; closed lines stay closed):** the health
FACT feed (C16 — no forecast attached, ever); the depth-chart contradiction FLAG as a fact
surface; H2b/H2c/H2e/H5e/H5f and everything on the Blueprint kill list; C1–C19.

## 4. WHAT WOULD MAKE US ABANDON EACH LINE (single sentences)

- H2g: chart wins ≤4/10 rooms → chart is a flag forever, never a rank input.
- H2a: pooled 2026 dR2 ≤ 0 → close; do not fund the 2014 hand-extension.
- H5a: 2026 knowable-form gap ≥ 0 → remove the prose caution; close the axis.
- H5b: ≤2/4 signs repeat → no rate proposal goes to grading.
- H5c: M3 worse than M0 on 2026 → K stays 12; close.
- P6 overlay: pooled ≤ 0 → close (its sibling already died by sign flip).
- H3a: gated fails +15pp on 2026 events, or works only under the usage-derived mechanism arm →
  the two-gate rule is an artifact; detector falls back to plain volume steps.
- H3b: lead-time advantage <1.5 weeks at matched FPR → rolling averages win; drop the
  change-point machinery.
- Detector as a whole: does not beat the 3-game rolling baseline, or beats it only in seasons/
  weeks dominated by a few extreme events (per-week table makes this visible) → report and stop.

## 5. DATA SNAPSHOT DATES AND CAPTURE (charter 9.1 bullet 3)

Exact dates: weekly Tuesdays from 2026-08-04; the draft-morning capture 2026-08-07; in-season
from 2026-09-15. Capture mechanism, file layout, immutability, manifest content, and runtime are
specified in `tools/weekly_snapshot.py` and documented in
`icm/work/mc_research/results_61_snapshot_job.txt` and `data/snapshots/README.md`. The
2026-08-07 directory is the price record for section 6; the weekly `fp_ecr.csv` sd/best/worst
series is the consensus-uncertainty record; `sleeper.csv` is the health-FACT record.

## 6. NAMED-PLAYER LIST — PLACEHOLDER (charter 9.1, MANDATORY FORMAT)

```
*** PLACEHOLDER — MUST BE FILLED AFTER THE 2026-08-07 DRAFT, FROM THE
*** 2026-08-07 SNAPSHOT, THEN COMMITTED AND PUSHED WITH THE SHA RECORDED IN
*** icm/work/HANDOFF.md (SEPARATE LATER COMMIT). DO NOT FILL FROM MEMORY OR
*** FROM ANY OTHER DATE'S PRICES. THE 08-07 PRICES DO NOT EXIST TODAY
*** (2026-07-31) AND NOTHING HERE MAY BE FABRICATED IN ADVANCE.
```

Required entry format, one row per flagged player (charter-corrected form — "Barkley will be
good" is not admissible):

| Player | Pos | Flagging finding | Direction | 2026-08-07 ESPN ADP | ADP-implied positional finish N | Prediction | Board `rank_composite` (covariate) |
|---|---|---|---|---|---|---|---|
| (to fill) | | e.g. P3 high-aDOT tax / P1 H2g room | above/below | from `data/snapshots/2026-08-07/espn_kona.csv` | derived from ADP within position | "finishes above/below his ADP-implied positional finish of N" | from `value_board.csv` on draft day |

Rules for filling: every player named by P1 (the 10 rooms are already frozen in results_55 —
restate them here with their 08-07 prices), P3 (the matched 2026 T3/T1 WR pairs), and P6 (the
2026 movers HIGH/LOW sets) is listed; the `rank_composite` covariate is recorded so a call that
merely tracks the board (which already contains ADP at W_A 0.06, ECR at W_E 0.13, and 50% Vegas)
can be identified as such after the fact; the source snapshot filename and its git SHA are
written next to the table.

## 7. THE 2026 SCORECARD (commitment)

At season end, write `icm/work/entanglement/2026-SCORECARD.md` containing: every prediction above
with its outcome under the section-1 verdict vocabulary; the named-player table with recorded
prices, covariates, and outcomes; the detector's precision/recall/median lead time by position
with event-clustered CIs and the event count as effective n; a per-week log of every alert with
its mechanism and expected reversion date; the BH pass across all section-3 primaries (raw +
adjusted); and a mandatory, non-empty section titled **"What I got wrong."**
