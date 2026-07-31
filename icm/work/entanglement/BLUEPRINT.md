# THE ENTANGLEMENT BLUEPRINT
Deliverable of the research charter `icm/work/research-blueprint-prompt.md` (charter section 10).
Written 2026-07-31 from the sixteen results files `results_46_*.txt` through `results_61_*.txt`
under `/Users/natearaskog/fantasy-analyzer/icm/work/mc_research/`.

Labelling discipline (charter style rule): **[R]** = read from the named results file on disk
(all of which were produced and verified this run by execution agents); **[V]** = computed by the
Blueprint author in this session (the global BH-FDR pass and the p-values derived from printed
CIs — arithmetic shown in section 2.1). Every number cites its source file. No emojis.

---

## 1. EXECUTIVE SUMMARY (what does NOT work, first)

**1. "Situation step changes are pre-season predictable" did not survive contact with the data —
except in the variance, not the mean.** Exactly as the charter's honest prior predicted. The
variance decomposition (`results_58_ws1.txt` [R]) shows the portable PLAYER component of
league-scored PPG collapses once price is controlled — RB 36.6% raw to 5.7% (±15.9%) above price,
WR 18.4% to −0.9% (±14.2%) — and the same-position teammate "situation" term is NEGATIVE
(RB −25.9% raw: carry cannibalization outweighs shared environment; C15/C7 made empirical). The
measured pre-season unpriced-environment ceiling is the cross-position estimator: +5.8% ±2.9% of
above-price variance = SD ~0.99 league ppg = **~17 points per 17 games at one full SD** — roughly
one bench streamer. The one live pre-season overlay tested (prior pass-snap participation on RB
team-changers) came back +19.4 league pts, CI [−16.0, +52.2], p=0.387 — null in the mean; its
flashier sibling (prior target share, +34.9 on the RB discovery slice) **failed its S2 replication**
(WR slice −5.7, sign flipped) — the exact C4-shaped trap. Every ceiling measured is the same order
as or smaller than C3's own CI width [−30, +40], so WS1 sharpens C3 rather than overturning it.
Step-change predictability survives only as the shipped Wave-2b sigma inflation for unproven movers
(`compute_outcomes.py:173-180` [R results_60]). **The pre-season half of this charter is alive only
as calibration, not as edge. Budget goes to WS3 (in-season) and the WS5 mechanics.**

**2. The charter's own highest-EV headline also failed.** H5f — "the bonus structure shifts
positional replacement level enough to change optimal allocation" — is a **clean, well-powered
null**: +2.7 league pts, season-clustered 95% CI [−6.2, +11.5], n=4 clusters, treatment-specific
MDE ±12, CI upper bound below every candidate bar (`results_51_h5f.txt` [R]). Mechanism: the
league table shifts every position's replacement level a lot (RB +29.5, WR +29.3, TE +16.7,
QB −11.5) but shifts them TOGETHER; the priced-tier cross-position VOLS tilt is only ~2–5 pts.
The pre-registered T0.3 falsification substantially fires: **charter §4.1.1's "largest and most
reliable edge available" claim is closed at the allocation level.**

**3. Page-1 statement on the league-scored panel (the T0.3 falsification):** the league-scored
panel did **not flip any tested WS5 verdict relative to base PPR**. H5f: +2.7 league vs +2.1 base
(same null); H5a: −20.2 league vs −17.5 base (same separation, same sign); H5e: null in both
currencies by construction (`results_51/52/59` [R]). So at the workstream level, league- and
base-scored grades agreed within noise, and per the pre-registered clause in
`results_46_league_panel.txt` Appendix C, §4.1.1's headline is wrong as stated. The honest
remainder: the league currency is still required for **measurement access**, not verdict flips —
the QB sack term (−32.8 ± 3.0 pts/season for top-12 QBs, within-top-24 spread 24.1 pts) and the
position-level first-down biases (3–7 pts/season, sign-stable 12/12 seasons) are exactly 0.0 in
base PPR and could never have been measured without T0.3 (`results_54`, `results_53` [R]). They are
real, small, player-level channels — all below the instrument's MDE for a points verdict today.

**4. The MDE of the instrument actually built — the most important fact in this document:** the
corrected three-arm grader resolves ±53 league points at 80% power (t-based, df=3, n=4 season
clusters; ±35 normal-approx) (`results_49_grader_selftest.txt` [R]). **Every stated charter bar
(+15/+20/+25) sits below that MDE**, so any points verdict at those bars is DIRECTIONAL-ONLY under
S11 unless the specific treatment's own cross-season dispersion is tighter (H5f achieved MDE ±12,
which is why its null is informative). The placebo calibration (`results_50_placebo.txt` [R]):
**p95 = +5.4 league pts** (bootstrap CI [+0.5, +8.4]) across 20 zero-information variables; 0/20
placebos reached +15; placebo mean −5.7 (a random deviation from the composite COSTS points — S4
made empirical); and the S3 sweep-shape criterion false-alarms on 2 of 6 placebos, so a PASS shape
can never rescue a below-bar estimate.

**5. The instrument finding that reframes the repo's own history:** the legacy +5.2 result (C3)
was reproduced to the decimal in legacy configuration (gate PASS), then re-graded on the corrected
instrument: **−18.2 league pts [−58.5, +22.1]** — and switching only the opponent model from flat
sd 8.0 to the measured dispersion flips it to −3.3 on its own (`results_49` [R]). The +5.2 was an
artifact of a misspecified opponent model, availability-blind season scoring, and the wrong
currency. Every future points claim runs through the corrected grader.

**What did work.** WS0 in full: league-scored panel (67,353 player-weeks, TD reconciliation
99.99–100%, anchor reproduced exactly [R results_46]); the three-arm/two-mode/five-slot grader with
a byte-identical provenance check and a passed legacy gate [R results_49]; the placebo bar
[R results_50]; the 2025 holdout REPAIRED (Sleeper adp_ppr instrument — ESPN kona is wiped and
S7-contaminated; 166 priced 2025 rows restored from 5) and the panel extended to ADP≤300 for
2020–2025 [R results_48]; `population.json` frozen; the role census (role lives in SIX sites, not
five) and already-shipped census (the F6 health-fact feed already ships in three places)
[R results_60]; the weekly snapshot job built, smoke-tested, and its first immutable snapshot
written (`data/snapshots/2026-07-31/`, 6/6 sources) [R results_61]. Positive findings that
survived: **H5a** — a high-aDOT WR TAX of ~20 league pts/season at matched price, with the deep
arm's ceiling LOWER, refuting folklore (p<0.001 but 11 season clusters, so **DIRECTIONAL-ONLY
under S11, not a points PASS**; the draft-knowable form attenuates further to −10.5, CI through
zero → prose caution only) [R results_52]; **H3d** — the operative
blacklist holds and is encoded as data (never rank tier-change candidates by a YPC or TD-rate
spike; the information is the volume the spike rides in on) [R results_57]; **H2a** — the one
surviving pre-season premise: an incoming playcaller's 11-personnel rate travels with him
(dR2_adj +0.152 [+0.040, +0.318], n=31 coach-moves — marginal, sign-robust, label-fragile;
2026 preregistration only) [R results_56]; and the empirically re-derived stabilization ladder —
job metrics are 2–5x FASTER than the inherited table among priced players (carry share G*≈0.6
games, snap ≈0.8, target ≈1.9, goal-line ≈2.3) while first-down rates are far SLOWER (10–20 games)
[R results_58] — which is the quantitative case for the in-season system.

**Where the budget goes now:** (1) the WS3 detector build on the 57_ scaffold, fed by dated
Tuesday snapshots (the only clean lead-time instrument this project will ever have); (2) the 2026
preregistration (`icm/work/entanglement/PREREGISTRATION.md`, DRAFT — pushed in draft state
2026-07-31 to timestamp P1–P8; the named-player fill and lock push follow the 08-07 draft, before
Week 1); (3) the two WS5 proposals that survive as gradeable: the H5b
position-level rate corrections and the H5c shrinkage fix, both through the corrected harness,
both propose-only against frozen files.

---

## 2. THE VERDICT TABLE

**Printed at the top, per charter:** placebo 95th percentile = **+5.4 league pts** (bootstrap 95%
CI [+0.5, +8.4]; n=20 placebos; 0/20 ≥ +15) [R results_50]. The operative bar for any points
verdict = max(placebo p95, the stated charter bar) — in practice the stated bars, all of which
sit below the instrument MDE of ±53 league pts (n=4 clusters) [R results_49], so no points PASS
was reachable this cycle and none is claimed. **Row count: 29 hypothesis ids in 30 rows** (H1; H2a–H2g,
with H2f split into two declared sub-rows a/b; H3a–H3e; H4-QB/RB/WR/TE; H5a–H5f; F1–F6), **plus
the declared H2c-s split-out = 31 physical rows.** **Primary
endpoints actually tested: 14 hypothesis-level** (+24 WS1 reliability diagnostics that the charter
counts toward FDR = 38 total). No row earned TRUE-BUT-UNREACHABLE — nothing survived to a
reachability test this cycle.

### 2.1 BH-FDR across all primary endpoints actually tested [V]

Where a results file printed a raw p it is used as-is; four p-values are **derived** [V] from the
printed CIs (normal approximation, SE=(hi−lo)/3.92: H2a p=0.032, H2b p=0.64, H2c p=0.68, split-out
p=0.086) and one t-based (H5f: t=0.96, df=3, p=0.41 from season SD 5.6, n=4). H5a's bootstrap p
printed as 0.000 and H3d's criterion-1 (precision CI [0.185, 0.280] vs 0.5) are entered as <0.001.

- **Pool A — 14 hypothesis-level primaries** (the honest pool), enumerated by name per S14
  ("print the count" — an unenumerated count is not checkable): **H1, H2a, H2b, H2c, H2c-s, H2g,
  H3d, H5a, H5c, H5f, and the four H5e positional cells (QB / RB / TE / WR)**. Two treatments
  stated explicitly: (i) **H5e is counted as 4 primaries**, one per position — results_59 declared
  a per-position endpoint, which is a declared deviation from S14's one-primary-per-hypothesis
  wording, recorded here rather than hidden in the count; (ii) **H2e is excluded from the pool**:
  results_54 called its verdict from the CI directly and assigned no p — an admitted inconsistency
  with the four CI-derived p-values above, so the sensitivity check is printed [V]: deriving
  H2e's p by the same normal approximation gives p≈0.9; with it, m=15 and the k=2 threshold is
  0.0133 — survivors identical, no verdict changes either way. BH q=0.10 adjusted threshold =
  **0.0143 (k=2)**. Survivors: **H5a (p<0.001)** and **H3d criterion-1 (p<0.001)**. Everything
  else fails BH, including H2a (raw p≈0.032 > 0.0214 at its rank).
- **Pool B — 38 tests** (adding WS1's 24 reliability diagnostics, per the charter's WS1 text):
  threshold rises mechanically to 0.0737 (k=28) because 24 diagnostics have p≈0; H2a and the H5e
  TE cell (p=0.0716) then nominally pass. **This is an artifact of pooling trivially-significant
  diagnostics with hypotheses; Pool A governs the verdict column.** Both raw and adjusted verdicts
  are shown per row.

S11 remains binding regardless of BH: every result under 40 clusters is capped DIRECTIONAL-ONLY,
which is why BH survival does not upgrade any verdict to PASS-in-points.

### 2.2 The table

Columns: primary endpoint (league points unless noted) / clustered 95% CI / effective n in
clusters / sensitivity-sweep shape / firing rate (% drafts identical) / per-slot spread / raw p ·
BH-adj (Pool A) / verdict. "—" = not applicable to that design (sweep, firing rate, and slot
spread exist only for paired-draft grades; only H5f ran one this cycle).

| # | Hypothesis | Primary endpoint | Clustered CI | eff. n (clusters) | Sweep | Fire% | Slot spread | p raw · BH-A | VERDICT |
|---|---|---|---|---|---|---|---|---|---|
| H1 | WS1 situation-vs-player (quantification) | RB movers, HIGH−LOW prior pass-snap participation, league pts above price: **+19.4** | [−16.0, +52.2] | 104 player-moves (9 seasons) | — | — | — | 0.387 · fail | **FAIL** (null in mean; diagnostic deliverables stand — ladder + decomposition). Overlays capped DIRECTIONAL-ONLY. [R results_58] |
| H2a | Playcaller personnel carryover (premise gate) | mean dR2_adj of caller profile over team-prior null: **+0.152** (R² units — points test not reachable at this n by charter design) | [+0.040, +0.318] | 31 coach-moves | — | — | — | 0.032 [V derived] · fail (passes Pool B) | **DIRECTIONAL-ONLY** (PASS-PREMISE at the wire; effect ~all 11-personnel, dR2_adj +0.341; 14/31 jackknife drops fall under the 0.15 threshold, 0/31 below zero; stricter all-three-rates reading FAILS). Routes to 2026 prereg only. [R results_56] |
| H2b | Playcaller touch-concentration carryover (premise gate) | \|e\|null − \|e\|caller on RB touch HHI: **−0.0075** | [−0.0390, +0.0236] | 31 coach-moves | — | — | — | 0.64 [V derived] · fail | **FAIL** (kill list). League-mean comparator beats the caller on all four metrics; best-back-ADP control does not rescue it. [R results_56] |
| H2c | Inside-5 goal-line tendency carryover (premise gate) | \|e\|null − \|e\|caller on inside-5 RB share: **−0.0103** | [−0.0586, +0.0393] | 31 coach-moves | — | — | — | 0.68 [V derived] · fail | **FAIL** (kill list). The seductive nonqb_hhi secondary (+0.0571, CI excl. 0) is shrinkage, not information — it loses to the league mean. [R results_56] |
| H2c-s | Split-out: team-level inside-5 concentration stability | YoY r of team non-QB top-rusher share: **+0.067** | [−0.011, +0.142] | 32 teams (352 pairs) | — | — | — | 0.086 [V derived] · fail | **FAIL/UNSTABLE** — no stable target exists to carry; explains H2c's death. [R results_56] |
| H2d | Contract/guaranteed-money committee tie-breaker | not executed | — | — | — | — | — | — | **NOT-RUN** — below the charter §10 priority line this cycle; the genuinely new axis (guaranteed money) remains untested; baseline (`_go_score` + `role_data.csv` carry share) ships. Post-draft candidate. |
| H2e | OL continuity → sack-rate staleness (pre-registered null) | OL-continuity carry-slope diff (high−low), stayers 2023–25: **+0.03** | [−0.55, +0.63] (ext. 2016–25: +0.06 [−0.22, +0.36]) | 87 pairs / 282 pairs (QB-season rows) | — | — | — | n.s. (CI) · — | **FAIL — pre-registered null CONFIRMED, line CLOSED.** Carried rate is not measurably staler for movers or turned-over lines; instrument = snap-count five-man overlap (2024 depth charts are OLD schema — see §3). [R results_54] |
| H2f-a | Adjectival camp reports (`news_updated` test) | deleted before running | — | — | — | — | — | — | **NOT-RUN by design** (kill list): 8,135/12,204 coverage = a null by construction; no free corpus, no ground truth, adversarially selected. [R charter D6] |
| H2f-b | Factual layer (PUP/NFI/missed practice) as a FORECAST | not testable historically and not tested by design | — | — | — | — | — | — | **NOT-RUN (routed to WS6/F6 as forward-only FACT, citing C16).** Prevalence measured: 4 PUP + 15 Q of top-150 ADP (Jul 27, `tools/injury_watch.py` [R results_60 M1]); Sleeper live 2026-07-31: PUP 18 / IR 9 / Q 78 league-wide [R results_61]. The flag fires. |
| H2g | Depth chart as independent role signal | 2025 disagreement rooms (wk-1), dc-favored − proj-favored league pts-above-price: **−5.8** (median −8.1) | pair-boot [−58.3, +44.5], DESCRIPTIVE | **1 season** (6 rooms) | — | — | — | 1.000 (sign) · fail | **DIRECTIONAL-ONLY** by construction. Evidence runs AGAINST replace: realized-No.1 in disagreement rooms — projection 50% vs chart 17% (wk-1), 60% vs 10% (Aug-07 lead time); chart carries a verified staleness hazard (ranks a Sleeper-PUP player SEA RB1). Route: HYBRID/flag at most; 10 rooms preregistered for 2026. [R results_55] |
| H3a | Two-gate rule (usage step + independent mechanism) | not executed | — | — | — | — | — | — | **NOT-RUN** — post-draft WS3 build; mechanism feeds named (`load_injuries` report/practice status, roster deltas, transactions, coaching CSVs) and the harness scaffold ships in 57_. Bar preregistered: +15pp precision at matched volume, event-clustered. [R results_57 §8] |
| H3b | Change-point vs rolling averages | not executed | — | — | — | — | — | — | **NOT-RUN** — post-draft; CUSUM/BOCPD slots into the same matched harness; bar ≥1.5 weeks median lead at matched FPR, DIRECTIONAL until 2026 snapshots. [R results_57 §8] |
| H3c | Earned vs vacated tier changes | not executed | — | — | — | — | — | — | **NOT-RUN** — post-draft; instrument built (`pass_snap_participation.parquet`, 93,045 rows 2016–25, blocker-conflation bound quantified). TPRR proper does not exist free. [R results_47] |
| H3d | YPC/TD-rate blacklist validation | pooled precision at matched alert volume, tau=0, league scoring: ypc **0.233**, td_rate **0.233** (criterion 1: <0.5 MET; criterion 2: below every usage family NOT MET — explained by the volume-gate ablation) | ypc [0.185, 0.280]; td [0.197, 0.272] | 383 / 635 player-season clusters (1,469 event-weeks, 411 event player-seasons) | volume-sens 0.5x/1x/2x ordering stable | — | — | <0.001 (crit-1) · **PASS** | **PASS (operative rule), encoded as data** (BLACKLIST_JSON in results_57 §6): never RANK candidates by a rate spike — within its own gated universe, ypc-ranking is WORSE than dumb window volume (−0.038 [−0.074, −0.003]; the gate ablation carries results_57's own POST-HOC label — designed AFTER seeing section 4; the criterion-1 primary stands independently, and P7 preregisters exactly this comparison on 2026 live data); 74–80% of blacklist alerts carry a concurrent usage step. Precision LEVELS and any lead-time reading are UPPER BOUNDS (revised-data bias) — DIRECTIONAL until 2026 live snapshots. NO family is high-precision (FP/TP ≥ 3.3 for everything). [R results_57] |
| H3e | Position-specific suppression | TE half: settled, not a hypothesis | — | — | — | — | — | — | **TE: SETTLED by C14 and already enforced in data** (`advisor.py:540` RB-only handcuff gate, test-pinned [R results_60 M2]). RB/WR suppression halves **NOT-RUN** (post-draft; `score_family()` on the removed set is the ready-made test). |
| H4-QB | Separate QB sub-model | collapsed into H5c | — | — | — | — | — | — | **NOT-RUN by charter design (D6)** — the falsification targeted a strawman; VOLS-vs-QB12 + PUNT READ already ship. See H5c. |
| H4-RB | RB depth-chart-forecast sub-model | not executed | — | — | — | — | — | — | **NOT-RUN** — post-draft. Falsification baseline stands ready (`role_data.csv` carry share); ingredients built (psp parquet, gl_share/carry_share ladder speeds G*≈0.6–2.3 games [R results_58]). High false-null risk vs the six shipped role sites — grade on the override population. [R results_60 §7] |
| H4-WR | WR archetype re-ordering above ceiling/floor incumbents | measurement half executed as H5a; the weekly-mode paired grade | — | — | — | — | — | — | **NOT-RUN (grading half)** — H5a supplies the measured axis; the board-reorder question requires the weekly-mode harness + placebo bar and was deliberately not run (knowable form is directional-only anyway). |
| H4-TE | TE classification (blocker vs catcher) sub-model | not executed | — | — | — | — | — | — | **NOT-RUN** — post-draft. Instrument ready: pass-snap share separates archetypes (blocking TEs 23–29% vs route-runners 80–98%), with the stated ambiguity band at ~50%. Never rank TEs on snap share (measured 0.065 at TE — below the 0.097 random benchmark). [R results_47, results_57] |
| H5a | WR archetype under league scoring (aDOT terciles) | ADP-matched paired league-VOLS gap, T3(deep)−T1(short): **−20.2** (a high-aDOT TAX; T2−T1 = −0.1) | [−31.1, −8.5] | 11 seasons (180 pairs) | robust: floor10/50, ADP≤170, ex-2025, pooled terciles all −18 to −28 | — | — | <0.001 · **BH-survivor** | **DIRECTIONAL-ONLY (measurement axis AND draft-usable form).** League-points endpoint on 11 season clusters < 40, so S11 caps the verdict regardless of BH survival — the preamble's "no points PASS was claimed" governs; the separation and the ceiling refutation stand as supporting measurement (S1/S11 permit that). Ceiling folklore REFUTED: deep arm's absolute p80-minus-replacement ceiling is LOWER (−25.8 [−40.3, −7.6], p=0.007). Knowable-at-draft form (prior-year aDOT): −10.5 [−23.6, +2.5], p=0.115 → prose caution only; NO rank nudge without paired grade + placebo bar. [R results_52] |
| H5b | Per-player rates for league-average bonus constants | points grade PENDING (0 primaries contributed; measurement screens only) | — | 11 cells, 19–232 player clusters each | — | — | — | — · — | **NOT-RUN (grading phase).** Measurement verdicts [R results_53]: PER-PLAYER CANDIDATES = rec_fd×WR (sp 0.369; dMAE +0.228 [+0.118, +0.345]), rec_fd×TE (0.366; +0.237 [+0.043, +0.435]), pass_tier×QB (0.391; +0.327 [+0.072, +0.576]; spread 8.1 pts). Valuable nulls: everything else. **DOMINANT finding = position-level bias, sign-stable 12/12 seasons**: QB rush-FD underpaid (dMAE +3.38 [+2.41, +4.24]; ~+3.2 to +5.4 pts/season), RB rec-FD overpaid (+2.73 [+2.43, +3.04]; ~−4.8 to −7.2), WR rec-FD underpaid ~+3.6. Per-player half alone expected NOT to clear +20. |
| H5c | Sack tax: staleness / invisibility / shrinkage | OOS sack-rate forecast improvement M0(shipped K=12)→M2(K*-nested + TTT), league pts/QB-season: **−0.62** | [−2.19, +0.96] | 7 seasons (179 QB-seasons) | — | — | — | 0.375 · fail | **FAIL (directional null — challenger does not beat shipped).** TTT adds NO forecast value (kill list). Live remainder: K=12 is wrong by CV (K*=512 last-1yr / 768 pooled; +14.1% excess MSE; a 3-yr starter should keep 66% of his deviation, not 99%; Maye's −25.9 would roughly halve) — but M3 points delta is tiny (+0.17 [−0.40, +0.73]) so the K fix's consequence is BOARD SPREAD and must be graded in the paired harness. Cheap checks: the market does NOT price prior sack rate (slope −3.2 [−54.3, +47.8], p=0.890; −1.5 pts/IQR); WE already price it at 100% (Spearman(total, custom+sack-only)=+0.996) — anti-double-count rule stands. Invisibility (S12 payload): top-12 QB sack term −32.8 ± 3.0 pts/season; top-24 spread 24.1 ≈ half the QB6→QB12 gap (56.2), not all of it; charter's −42 is ~25% high. [R results_54] |
| H5d | Full-bonus weekly scoring inside the MC | not executed | — | — | — | — | — | — | **NOT-RUN by charter design** (demoted, propose-only): the linearization happens upstream (H5b); the 62.1% OOS target must first be re-established on the league-scored panel before any comparison means anything. |
| H5e | League-scoring xFP as a role signal | delta predictive Spearman (league − standard xPPG) vs next-season league pts-above-price: QB −0.0103 / RB +0.0003 / **TE +0.0120** / WR −0.0009 | TE ±0.0116 (others in file) | 11 season-pairs each | assumption-variants stable (all medians ≥0.989) | — | — | 0.072–0.966 · all fail (TE passes Pool B only) | **FAIL (clean null — do not ship).** Gate falsified by only 2/48 cells (min rho 0.9753); 0/4 positions survive BH; the 171 no-xppg players CANNOT be helped by construction (identical coverage). T0.9 deliverable (`league_xfp_weekly.parquet`, 61,211 rows) stands for WS3. [R results_59] |
| H5f | Replacement level under league scoring (allocation) | paired grade arm3−arm2, SEASON mode, walk-forward positional tilt: **+2.7** | [−6.2, +11.5]; MDE ±12 | 4 seasons (2,000 paired drafts) | 0x=exactly 0; +1.2/+2.7/+5.4/+5.5 — plateau at 2x, every CI spans zero (shape cannot rescue) | 30.8% (69.2% identical) | slot1 −0.2 / s5 +1.1 / s8 +5.0 / s10 +8.2 / s12 −0.9 | 0.41 [V derived] · fail | **FAIL — clean, well-powered, informative null.** Pre-registered falsification FIRES: the bonus structure is rank-preserving at the allocation level (replacement shifts RB +29.5 / WR +29.3 / TE +16.7 / QB −11.5 move together; priced-tier VOLS tilt ≤3 pts cross-position). Jackknife does not fire (+2.7→+2.8). Closes §4.1.1 at the allocation level. C6 seam measured and EMPTY at the tier (bias +2.0 ±15.6, scoring +1.7 ±8.3, signs flip yearly). [R results_51] |
| F1 | Role signal: replace or sit-beside? | agreement rate, new signal vs shipped role sites, draftable range | — | — | — | — | — | — | **DIRECTIONAL-ONLY, answer = SIT-BESIDE / CONTRADICTION-FLAG, not replace.** Measured: 68.3% overall (<95% cosmetic gate → material), but 100% top-50 ADP, 92.9% top-100, 92.2% of room leaders; **60.9% in the override population (n=64)** — the competes-with-nothing population is where the disagreement lives, and the 2025 evidence favors the projection there. Coupled to H2g's 2026 prereg. Note: the override population is 65 RB/WR/TE (the charter's "85" is board-wide all positions). [R results_55, results_60] |
| F2 | Revive discarded signals (proj_divergence; FP sd/best/worst) | not executed | — | — | — | — | — | — | **NOT-RUN.** The genuinely-new half (FantasyPros sd/best/worst) is now captured weekly (`data/snapshots/*/fp_ecr.csv`, 511 ppr rows + sd/best/worst [R results_61]); the proj_divergence half expects a near-null (C17: sources correlate +0.964..+0.987 top-180 [R charter]). Post-draft calibration test vs MC sigma. |
| F3 | Where does the in-season detector live? | design question | — | — | — | — | — | — | **ANSWERED (design, JUDGMENT — see §5).** Measured fact: NO in-season surface exists today (`app_pages/` = draft.py + setup.py only [R results_60 F3]). |
| F4 | Reachability through survival machinery | not executed | — | — | — | — | — | — | **NOT-RUN — and correctly so:** no pre-season finding survived to shipping, so no reachability run was required. Machinery ready (`advisor._survival_prob`, advisor.py:789-812). Bar stands for any future flag. |
| F5 | FFC stdev validates `_SCALE_S`? | not executed | — | — | — | — | — | — | **NOT-RUN (data staged).** `ffc_adp_2026.csv` captured: 247 players, 3,899 drafts, stdev on 247/247; FFC max ADP 188.6 so the `_SCALE_ADP=165.5` anchor cannot be densely validated — say so rather than extrapolate. Point-by-point ±30% comparison is a half-day post-draft task. [R results_48] |
| F6 | Forward-only health FACT feed | fact routing, no backtest by design | — | — | — | — | — | — | **FACT — ALREADY SHIPS in three places** (`tools/injury_watch.py`; `app_pages/draft.py:147-170` injury_map; `advisor.py:1344-1363` HEALTH FLAGS "FACTS, not forecasts") [R results_60 M1]. Remaining work: the early-August PUP/NFI framing + explicit C16 citation in the advisor text. The charter's premise ("the BOARD has no injury input at all") is true of value_board.csv, not of the app+advisor stack. |

**Reading rule for this table** (charter S1/S11/S15): the verdict column is governed by S11 cluster
floors and the placebo/MDE facts, not by BH alone; `mult`/lift numbers appear nowhere in the result
column. **Declared vocabulary extension** beyond the charter's five labels (PASS / FAIL /
DIRECTIONAL-ONLY / NOT-TESTABLE / TRUE-BUT-UNREACHABLE): **NOT-RUN** marks rows deferred by the
charter's own priority order that remain testable — labelling those NOT-TESTABLE would be
dishonest, because the charter reserves that word for designs the data structurally cannot answer;
**SETTLED** (H3e-TE: C14, already enforced in code), **ANSWERED**/**FACT** (F3/F6: design and fact
rows with no testable endpoint), and **FAIL/UNSTABLE** (H2c-s: the target itself has no
year-over-year stability to carry) are one-row precision labels. The two BH survivors (H5a, H3d)
are measurement results, not shipping decisions — both carry explicit routing caps (prose-only;
encode-as-data) — and only H3d's PASS survives S11 (383–635 clusters on a precision endpoint);
H5a is capped DIRECTIONAL-ONLY (11 season clusters on a points endpoint).

---

## 3. THE DATA-AVAILABILITY TABLE (WS0 resolution)

Every later workstream cites this table. All entries [R] from the named results files; verified by
execution on 2026-07-31.

| Question | Resolution | Source |
|---|---|---|
| `load_participation` `route` semantics | ONE label per play describing the TARGETED receiver (2022: 99.4% of targeted, 0.0% of untargeted); 2024-era labels ALSO appear on 32.5% of untargeted pass plays (intended-route charting) — a third pre/post-2023 product difference beyond coverage and vocabulary. **No per-player routes-run column exists in any season.** Always test non-empty with `.fillna('').str.len()>0`, never `.notna()` (2023+ empty strings report 100% under notna). Vocabulary changed at 2023 (HITCH/OUT/CROSS → HITCH/CURL, QUICK OUT, IN/DIG...) — never pool across the boundary. | results_47 |
| `offense_players` coverage | 91.3–91.6% raw pre-2023, 100.0% 2023+ — but on REG dropbacks coverage is **100.0% in every season 2016–2025** (the pre-2023 gaps are entirely no_play penalties + admin rows). A coverage-adjusted denominator is an inert safeguard. | results_47 |
| Pass-snap participation (the free ceiling) | BUILT: `icm/work/mc_research/pass_snap_participation.parquet`, 93,045 player-week rows 2016–2025, REG. Blocker conflation quantified: smaller than assumed (blocking archetypes are benched on dropbacks — 23–29% share vs 80–98% for route runners); residual overstatement bound ≥5–17pp for named blocker profiles; a TE at ~50% share is ambiguous. Contains ALL offense players (OL at 1.0) — filter by position via rosters before use. | results_47 |
| `load_depth_charts` schema break | WORSE than the charter said: **2024 is ALSO old schema** (club_code/depth_team, 37,312 rows), so only 2025/2026 carry the ESPN pos_rank schema — zero usable new-schema YoY pairs inside 2023–2025. `pos_rank` (2025/26 schema) is a GLOBAL within-(team, pos_abb) ordering across slots — maps 1:1 onto team_role's number. Never pool `depth_team` with `pos_rank`. Charts lag injury FACTS (2026-07-31 chart ranks Sleeper-PUP Charbonnet SEA RB1) — any chart signal needs a freshness/injury gate. | results_54, results_55 |
| ESPN kona historical ADP | **DEAD as a repair path — do not retry.** 2025 is wiped (all 991 skill values = the 170.0 undrafted sentinel); surviving years are S7-contaminated (kona-2024 vs genuine preseason FFC-2024 Spearman only +0.780; promoted players scored ~2x demoted — the "price" drifted toward outcomes; CMC FFC 1.4 → kona 16.0). Correction: `espn_hist_cache.json`'s 'adp' field is SLEEPER ADP written by 35_, not ESPN ADP. Live 2026 kona works (ADP + ownership momentum fields). | results_48 |
| The 2025 price instrument | **REPAIRED with Sleeper adp_ppr** (validated: vs FFC overlap seasons Spearman +0.956..+0.974; S7 leak test in-range). 2025 priced rows ≤200 restored 5 → 166. Union contract: `seasons_exp.parquet[season≠2025] ∪ seasons_2025repair.parquet`; `adp_hist.csv[season≠2025] ∪ adp_hist_2025repair.csv`. **Every downstream 2025-priced result must state the instrument change** (all sixteen results files do). No dispersion (adp_stdev NaN). | results_48 |
| Priced-panel depth per season | FFC max ADP 153.8–177.5 for 2014–2024; Sleeper extension to ADP≤300 exists **2020–2025 only** (panel-matched 216/215/212/233/251/250). The charter's own pool floor (≥222) FAILS at adp≤200 in EVERY season; the ≤300 extension clears it 2023–2025 matched (graders may add priced-but-unplayed at 0 pts, which 49_ does). **Deep-band points tests: impossible before 2020; ≥2020 capped at 6 season clusters (directional-only).** | results_48 §E |
| `population.json` | EMITTED: `icm/work/mc_research/population.json` — filters, per-season rows/priced counts/max-ADP/cluster counts/position mix, instrument per season, pool flags at ≤200 and ≤300, union contract, do-not-retry kona verdict. Downstream scripts assert against it on load (49_/50_/51_ do). | results_48 §F |
| FFC | Requires a browser User-Agent (plain urllib → 403). Hard asserts wired (total_drafts non-null AND >100 players raises). 2026: 247 players / 3,899 drafts / stdev 247/247 / max ADP 188.6 → cannot densely validate the `_SCALE_ADP=165.5` anchor. **2025 is a missing year** (assert fired as designed). | results_48 §A |
| PUP/NFI history | ABSENT from nflverse (`load_injuries` has no preseason rows, no PUP/NFI in report_status; week-1 rosters show PUP exactly once league-wide). **Live** Sleeper `injury_status` carries it now: PUP 18 / IR 9 / Q 78 on 2026-07-31 — captured weekly by the snapshot job. Forward-only FACT (C16). | charter §3.4, results_61 |
| Playcaller history | 224 team-seasons → 78 caller-change events → **31 carryable** + 46 first-timers + 1 same-team-only (Mike Kafka NYG 2025). 31 < the S11 40-cluster floor: WS2's forecasting half is structurally directional-only. Only lever: hand-extending to 2014 (~160 team-seasons of MANUAL news verification) — justified on these results only for the H2a personnel gate. | results_48 §H, results_56 |
| `load_ftn_charting` | Has **NO personnel column** — the assumed 2022+ personnel fallback does not exist. `participation.offense_personnel` (2016–2025) is the sole free personnel source, and it is TWO ENCODINGS breaking at 2023 (league 21-personnel collapses 8% → 1.7% — a charting change, not football): within-season standardize or split eras. | results_56 |
| League-scored panel | BUILT: `weekly_league.parquet` / `seasons_league.parquet` / `bonus_weekly.parquet` (67,353 rows, 12 seasons; scoring constants imported solely from `scoring_config.py`; tiers exact per game; anchor reproduced: QB −8.9 / RB +64.2 / WR +34.9 / TE +24.8). QB/RB/WR/TE only — **no K/D-ST league-scored history exists** (scope cut). pbp slims cached per season (`pbp_slim_2014..2025.parquet`); the feared largest-compute-item took 0.2 minutes. | results_46 |
| Weekly league xFP | BUILT: `league_xfp_weekly.parquet` (61,211 rows, both currencies, components broken out, exact actuals joined). Sacks/fumbles/returns/PAT-FG have NO expectation in the source — absent from BOTH currencies (the sack divergence is structurally invisible to xFP; H5c owns it). | results_59 |
| WS3 ground truth | BUILT: `gt57_records_league.parquet` (20,634 eligible (player,W) records 2015–2024, 3,722 player-season clusters) + importable machinery (weekly replacement from `utils.startable_counts`, PAR with absent-week=0−repl, strict gap week, full tau curve). Weekly PAR is NOT comparable to season VOLS/17 — different replacement objects. | results_57 |
| Snapshot instrument | BUILT AND LIVE: `tools/weekly_snapshot.py` (immutable dated dirs + manifest; fail-safe hard asserts; 6 preseason sources + 4 in-season adds; ~10–20 s/run; ~80–90 MB/season, commits by default). First snapshot: `data/snapshots/2026-07-31/` (6/6 ok). Cadence: TUESDAY (the seam between MNF/nflverse refresh and Wednesday waivers), plus one extra run FRIDAY AUG 7 (draft morning) — that dir IS the §9.1 recorded-price file. | results_61 |

**Standing data-quality flags raised (frozen files untouched):** (1) `apply_bonuses.py` ~line 66
reads the dead `pt_return_tds` column (ALL ZERO every season) — shipped return-TD points are
silently zero for everyone; ~6 pts/season ceiling for a returner [R results_46 B1]. (2)
`load_ff_opportunity.py:43-58` aggregates ALL weeks with no REG filter — shipped xppg mixes
postseason into playoff players' per-game rates [R results_59]. (3) `49_grader_lib.report_primary`
has a slot-major/season-major misalignment in its printed "when ≥1 changed" conditional line only
(pooled means/CIs/win rates unaffected); recompute that block as 51_ does until patched
[R results_51]. (4) RESOLVED at the
audit fix pass (2026-07-31): `49_cache/`, `50_cache/`, `51_cache/` (seeded, regenerable) and
`espn_adp_hist/` (~31MB — the dead kona pull; its verdict is preserved in `population.json`)
added to `icm/work/mc_research/.gitignore`; every other artifact of this run committed and
pushed (SHA in `icm/work/HANDOFF.md`). (5) Number drift to re-pin before
quoting: Maye is 3rd (not 2nd) on custom_proj_points today (Lamar 371.8 > 370.7) [R results_60];
T0.3's "FD/carry 0.237" is the panel-wide mean — the shipped 2024+25 window value is 0.2509
[R results_53].

---

## 4. THE ARCHITECTURE PROPOSAL (per position, routed through the WS6 decision tree)

Design is JUDGMENT built on the measurements above; each element names its WS6 layer, its
committed-CSV artifact, and its pinning test. Nothing here ships before the user's explicit
approval, after Aug 7. The frozen chain is never edited; frozen-file items are PROPOSALS.

**QB.** Replacement stays QB12 (C12 — asserted throughout this run). The sack term already ships
and the board prices it at 100% (Spearman +0.996 [R results_54]); the one live proposal is the
**K recalibration** (K=12 → ~512–768 for the sack term): parallel research module recomputes the
column, graded in the corrected harness (weekly mode) at bar max(+15, placebo p95), full 0/0.5/1/2/4
sweep — **guard: `scoring_config.py` K is SHARED with the long-TD terms; a K change must clear
H5b's long-TD cross-validation too or be term-specific.** Second proposal: the **H5b position-level
rush-FD correction** (+3.2 to +5.4 pts/season underpaid, sign-stable 12/12) — same route.
Layer: frozen-file proposal. CSV: none new (bonus recompute). Test: extend
`tests/` with a pinned Maye/Allen bonus fixture. In-season: QB tier changes are QB-change EVENTS,
not usage steps — the detector excludes QB by design [R results_57].

**RB.** Role remains measured carry share (`role_data.csv`) + `_go_score`; the depth chart enters
as a **CONTRADICTION FLAG (fact)**, not a rank input — H2g's 2025 evidence opposes replacement and
the chart has a verified staleness hazard. Freshness gate: suppress the flag when Sleeper
`injury_status` contradicts the chart (the Charbonnet case). H5b: position-level rec-FD correction
(RBs overpaid ~5–7 pts/season) — frozen-file proposal via the same graded route as QB. In-season:
RB is the detector's home position (snap_share_step usable at RB only, 0.202; carry-share G*≈0.6
games priced [R results_57/58]); handcuff logic stays RB-only (C14). Layer: fact/prose + graded
proposal. CSV: `data/depth_flags.csv` (or read from the snapshot dir). Test: a fixture pinning the
flag's freshness gate.

**WR.** The H5a high-aDOT tax enters at the **lowest-risk layer only**: an advisor prose READ
("this profile costs ~20 league pts/season at matched price historically; the draft-knowable form
is directional") — no rank nudge without the weekly-mode paired grade + placebo bar. Per-player
rec-FD EB rates (WR: sp 0.369, dMAE CI excludes 0) are the H5b per-player candidate — pending
grading, pooled 2 prior years (L2b beat L2 in 9/11 cells). The distribution incumbent (ceiling
0.25 + floor 0.15 + cv_rel) stands — any shape proposal competes with it (H4-WR NOT-RUN).
Layer: prose READ now; graded rank work later. Test: prose reads get snapshot-text tests per the
COLD/PUNT pattern.

**TE.** Positional scarcity logic unchanged. The classification question (H4-TE) is post-draft;
its instrument (pass-snap share) is built and its trap is measured — never rank TEs on snap share
(0.065 vs 0.097 random [R results_57]). rec-FD per-player candidate (sp 0.366) pending the same
H5b grading. TE promotion alerts remain suppressed (C14, settled, already enforced).

**K / D-ST.** Stated scope cut — no league-scored history exists in the panel, no sub-model is
proposed, and per L36/L38 any advisor recommendation surface for them needs its own tracking
(section 10).

**Cross-cutting:** every sub-model must be gradeable in `49_grader_lib` by swapping only its
position's ranking; arm 2 carries no ceiling/floor/role/cohort terms, so treatments overlapping
those shipped terms will read partially "new" (false-POSITIVE direction) — grade with the T0.8
census (results_60 §7) in hand, and report each position's contribution separately.

---

## 5. THE IN-SEASON SYSTEM DESIGN (WS3)

Everything below rides on the built scaffold (`57_h3d_blacklist.py` importable machinery +
`gt57_records_league.parquet` + `pass_snap_participation.parquet` + `league_xfp_weekly.parquet`)
and on dated Tuesday snapshots. Design = JUDGMENT; every quantitative anchor is [R] as cited.

1. **Ground truth (settled):** rest-of-season league-scored points-above-weekly-replacement
   (replacement = `utils.startable_counts` on realized weekly `pts_league`; PAR; absent week =
   0 − replacement; strict gap week W+1; detection weeks 4–12). Tier-change threshold: the FULL
   tau curve (−3..+3 PAR/wk) is always reported, tau=0 primary — preregistered.
2. **The two-gate rule (H3a):** usage step + INDEPENDENT mechanism. Named mechanism feeds, proven
   independent of the usage panel: `load_injuries` report_status/practice_status (snapshotted
   weekly), week-over-week roster deltas, transactions (`load_draft_picks`/`load_contracts`), and
   the hand-curated coaching CSVs. A mechanism inferred from a TEAMMATE'S snap count is NOT
   independent — it runs as a separate, labelled arm; if the gate only works there, the gate is an
   artifact. Bar: +15pp precision at matched alert volume, event-clustered CIs. Empirical
   motivation is now measured: NO trigger family exceeds 0.233 precision alone (FP/TP ≥ 3.3), so a
   usage-only detector is 3–9x more wrong than right [R results_57].
3. **Change-point method (H3b):** CUSUM on the weekly PAR/usage series (chosen for being online,
   one-parameter, and directly pluggable into `matched_alerts()`; BOCPD as a sensitivity arm).
   Bar: ≥1.5 weeks median lead at matched FPR, blocked over weeks — DIRECTIONAL until confirmed on
   2026 live snapshots (revised-data bias is a measured, named upward bias on every historical
   lead-time claim).
4. **Suppression rules:** TE settled (C14; cite `advisor.py:540` precedent — encode, do not
   re-measure). RB/WR candidate rules are tested by scoring the precision of the REMOVED alert set
   (`score_family()` on the removed slice); a rule that removes high-precision alerts is a bad rule.
   Blacklist encoded as data: BLACKLIST_JSON (results_57 §6) — ypc_spike and td_rate_spike are
   never ranking triggers; snap_share_step carries the WR/TE below-random caveat.
5. **Reversion dates:** every event-driven promotion carries an expected reversion date (the
   mechanism feed supplies it: an injury designation implies a return window; a trade does not).
6. **Two-track metrics:** garbage-time-stripped for the ROLE read, raw for the POINTS read —
   never collapsed. Alerts are gated by lineup slot (§7.10: an alert you cannot start is worth 0).
7. **Benchmark:** primary = precision/recall/median lead time at matched alert volume with
   event-clustered CIs and a per-season table. Secondary = EX-ANTE weekly lineup comparison
   (detector-manager vs a 3-game rolling league-PPG manager; `fp_ecr_week.csv` is snapshotted
   weekly as the consensus start/sit control), with hindsight-optimal totals reported alongside as
   a ceiling. Tertiary = an explicitly-labelled upper bound on acquisition value. The FIRST WS3
   output is the baseline itself (what the rolling-PPG manager earns) — the threshold is set from
   that measurement, not defended after the fact.
8. **Product surface (F3, the concrete answer):** measured fact — no in-season surface exists
   (`app_pages/` = draft.py + setup.py [R results_60]). Named design: a **new Streamlit page
   `app_pages/inseason.py`** reading a committed `data/inseason/alerts_YYYY-MM-DD.csv` (the
   cohort_data/role_data committed-CSV pattern — required because nflreadpy is not on Streamlit
   Cloud); interim CLI in the `tools/injury_watch.py` style until the page is built post-draft.
   **Weekly runtime cost:** `tools/weekly_snapshot.py` measured at 5.5 s preseason / ~10–20 s
   in-season [R results_61]; the detector pass over one week of data on the 57_ machinery is
   estimated <2 minutes (JUDGMENT; the 2015–2024 full-history build ran in 16 s [R results_57]);
   plus commit+push. Total Tuesday ritual ≈ 5 minutes. Regeneration steps: (1) run
   `tools/weekly_snapshot.py`; (2) run the detector script against the new snapshot dir; (3)
   commit `data/snapshots/YYYY-MM-DD/` + `data/inseason/alerts_*.csv`; (4) push (an unpushed
   snapshot is one disk failure from not existing).

---

## 6. THE FUSION PLAN (file by file, number by number)

Every item states FACT (no backtest; advisor context, clearly labelled) vs FORECAST (full grading:
corrected harness, both currencies, 0/0.5/1/2/4 sweep with 0x asserting exactly zero, mandatory
reporting block, bar = max(stated, placebo p95 = +5.4), MDE caveat printed). Frozen files are
proposals only.

| # | Change | File(s) | FACT/FORECAST | Numbers + gate |
|---|---|---|---|---|
| 1 | Early-August PUP/NFI framing + C16 citation in the HEALTH FLAGS text | `advisor.py:1344-1363` (text only) | FACT | Feed already ships in 3 places [R results_60 M1]; prevalence 4 PUP + 15 Q of top-150 (Jul 27); Sleeper PUP=18 today [R results_61]. No sweep (prose); pin with a snapshot-text test. |
| 2 | Depth-chart CONTRADICTION FLAG with freshness gate | new `data/depth_flags.csv` (or snapshot read) + one advisor prose line | FACT (a chart disagreement is a fact; no forecast attached) | H2g: agreement 100% top-50 / 60.9% override population; 2025 evidence AGAINST replace; Charbonnet-PUP staleness hazard [R results_55]. Suppress flag when Sleeper injury_status contradicts the chart. No rank effect until the 2026 prereg grades. |
| 3 | High-aDOT WR prose caution | advisor READ layer | FORECAST expressed as prose (lowest-risk layer; L48b: prose is still a claim — text must state the knowable form is directional) | −20.2 [−31.1, −8.5] measured; knowable form −10.5 [−23.6, +2.5] p=0.115 [R results_52]. A rank nudge requires the weekly-mode paired grade + placebo bar — not run, not proposed. |
| 4 | H5b position-level bonus rates (fd_carry, fd_rec, yardage tiers by position) | parallel research module → PROPOSAL against `apply_bonuses.py` (FROZEN) | FORECAST | Biases sign-stable 12/12 seasons: QB rush-FD +3.38 [+2.41, +4.24] MAE gain; RB rec-FD +2.73 [+2.43, +3.04]; WR +3.6 [R results_53]. Gate: corrected harness weekly mode, bar max(+20, +5.4), sweep, jackknife printed (n=4 clusters makes results player-sensitive — 49_'s jackknife rule always printed). |
| 5 | H5b per-player EB rates, ONLY rec_fd×WR/TE + pass_tier×QB, pooled 2 prior years | same route as #4 | FORECAST | dMAE CIs exclude 0 but magnitudes ~0.2–0.3 pts/season; expected NOT to clear +20 alone [R results_53 §6.5]. Grade jointly with #4; accept the null if it lands. |
| 6 | H5c K recalibration (sack term) | PROPOSAL against `apply_bonuses.py` / `scoring_config.py` (FROZEN) | FORECAST | K*≈512–768 vs shipped 12 (+14.1% excess MSE); M3 points delta +0.17 [−0.40, +0.73] → the payload is board SPREAD, so the paired harness decides; bar max(+15, +5.4). **Shared-K guard:** the long-TD terms use the same K and were not cross-validated — a global K change must clear H5b too [R results_54]. |
| 7 | Blacklist + suppression encoded in the detector build | new WS3 module (post-draft) | data-encoded rule (neither fact nor forecast — a measured negative) | BLACKLIST_JSON verbatim from results_57 §6; quote the gate-ablation numbers, never the naive table alone — and always with results_57's own POST-HOC label (the ablation was designed AFTER seeing section 4; P7 preregisters the comparison on 2026 live data). |
| 8 | FP sd/best/worst uncertainty into the risk dial (F2) | post-draft test vs MC sigma | FORECAST | Captured weekly since 2026-07-31; bar: improves calibration vs the depth-dependent sigma with a CI, else not shipped. proj_divergence half expects a near-null (C17). |
| 9 | H2g role SWAP (only if the 2026 prereg reverses the 2025 evidence) | `value_board.py:41-43,48-51,98-112` + `app_pages/draft.py:90-94` + `cohort_priors.py:85` + advisor consumers + 3 test suites — SIX sites in ONE pass | FORECAST | role_lead's MAGNITUDE (0.5 VONA/pt cap ±10; ±15 prose; ≥15 ascend gate) cannot come from an ordinal pos_rank; the evidence-backed reconstruction is HYBRID (order from chart where fresh, magnitude = projection gap along the chart's ordering, defined semantic for negative leads) [R results_55/60]. L52/L53: a partial fix to a duplicated concept is worse than no fix. |
| 10 | Do-not-do list confirmed by this run | — | — | No league-xFP swap (H5e null); no allocation tilt (H5f null); no caller-concentration or goal-line carryover input (H2b/H2c dead); no TTT feature (dead); no `news_updated` sentiment (dead); no re-litigation of C1–C19. |

S5 requirement carried forward: any of #4–#6 that survives grading must have its firing state
measured under the REAL advisor policy before shipping (the C5 precedent: 552 decision points,
zero occurrences).

---

## 7. OBTAINABLE FREE AND PROGRAMMATIC vs NOT (the user's straight answer)

The user asked for "every statistic, every news article, every change." The honest split, with
evidence:

**Free, programmatic, and now instrumented (tool named):**
- Weekly box scores, snap counts, schedules+Vegas lines, rosters, draft capital, contracts,
  combine (nflreadpy loaders — all row-count re-verified [R results_48 §I]).
- pbp at 12-season depth, slimmed and cached (`pbp_slim_*.parquet`; the feared compute item costs
  0.2 minutes warm [R results_46]).
- Pass-snap participation 2016–2025 (`pass_snap_participation.parquet` [R results_47]).
- League-scored weekly history + league xFP (`weekly_league.parquet`, `league_xfp_weekly.parquet`).
- Three ADP sources with dispersion where offered: ESPN kona live (+ ownership momentum fields),
  FFC (browser UA; stdev; ~247 players), Sleeper adp_ppr/adp_std (the 2025 historical repair
  instrument) [R results_48].
- FantasyPros ECR with sd/best/worst via `load_ff_rankings` (511 ppr rows; snapshotted weekly)
  [R results_61].
- Depth charts, 2025/2026 schema only (daily ESPN snapshots) [R results_55].
- Live health FACTS: Sleeper injury_status incl. PUP/NFI/IR (snapshotted; PUP fires today)
  [R results_61].
- NGS derived aggregates, PFR advstats, FTN charting (no personnel column), ff_opportunity xFP.

**Not obtainable — do not plan around these (charter §3.4, carried explicitly with evidence):**
1. **Beat-reporter text:** no free licensed corpus, no ground truth, adversarially selected — do
   not build. The cheap substitute (`news_updated`) is a null by construction (8,135/12,204
   coverage).
2. **PUP/NFI history:** verified absent from nflverse injuries (no preseason rows; PUP appears
   once league-wide in week-1 2023 rosters) — forward-only fact, C16 forbids attaching a forecast.
3. **Coordinator/scheme data:** hand-curated only; the curated file supports **n=31** carryable
   events, below the S11 floor forever unless ~160 team-seasons are hand-verified back to 2014.
4. **Per-player routes run (and TPRR):** do not exist in free data in any season — the free
   ceiling is pass-snap participation with the quantified blocker conflation [R results_47].
Plus: historical FantasyPros projections (permanently unreconstructable — the forward fix ran:
`data/projection_archive/2026_preseason_2026-07-31.csv`, 1,575 rows [R results_48 §G]); FFC 2025
(not served); ESPN kona history (wiped/contaminated [R results_48 §B]); Sleeper historical
projections (backfilled — invalid); PFF grades; player tracking; OL quality ratings; season-long
props; weather; zone/gap labels.

---

## 8. THE 2026 TEST PROTOCOL

The protocol file is `/Users/natearaskog/fantasy-analyzer/icm/work/entanglement/PREREGISTRATION.md`
— **currently marked DRAFT.** It contains every 2026 hypothesis as a directional prediction with a
threshold, primary endpoint, and discovery/replication slices; the snapshot-capture plan built on
`tools/weekly_snapshot.py` (Tuesday cadence + the mandatory extra run on draft morning, Fri
2026-08-07 — that snapshot dir IS the recorded-price file); the tier-change threshold-curve
commitment; and a PLACEHOLDER for the §9.1 named-player list, which MUST be filled from the
2026-08-07 ESPN ADP snapshot after the draft and then committed AND pushed with the SHA recorded
in `icm/work/HANDOFF.md` in a separate later commit. Player names and prices are NOT fabricated
now — the 08-07 prices do not exist yet. Lock rule (charter 9.1): a local commit is not a lock;
push to `origin/main` and record the SHA + push timestamp. **Status: the DRAFT was committed and
pushed on 2026-07-31 at the audit fix pass — that push timestamps the P1–P8 hypothesis-level
predictions (which exist today) and its SHA is recorded in `icm/work/HANDOFF.md`; it is NOT the
lock, which remains the second push after the 08-07 fill.** Verdict vocabulary for 2026: pre-season
hypotheses can only be FAIL / NOT-FALSIFIED / INCONCLUSIVE (one season cannot confirm); only
in-season event-level metrics may PASS, with event-clustered CIs; end-of-season deliverable is
`icm/work/entanglement/2026-SCORECARD.md` with a mandatory non-empty "What I got wrong" section.

---

## 9. THE KILL LIST (all measured, this run)

1. **H2b — playcaller touch-concentration carryover.** FAIL-PREMISE: caller loses to team-prior on
   rb_hhi (−0.0075 [−0.039, +0.024]), top_back_share, rb_tgt_share; prior-season LEAGUE MEAN beats
   the caller on all four metrics (rb_hhi 0.0741 vs 0.1208); best-back-ADP control moves the beta
   −0.190 → −0.180 only. Do not re-open without the league-mean comparator in hand. [R results_56]
2. **H2c — inside-5 goal-line tendency carryover.** FAIL-PREMISE (−0.0103 [−0.059, +0.039]); the
   CI-excluding-zero secondary (nonqb_hhi +0.0571) is shrinkage, not information; the target
   itself is unstable (team YoY r=0.067) — nothing exists to carry; even the committee-tie-breaker
   fallback loses to the league mean. [R results_56]
3. **H2e — OL-continuity staleness of the sack rate.** Pre-registered null CONFIRMED both scopes
   (+0.03 [−0.55, +0.63]; +0.06 [−0.22, +0.36]). The rate travels with the QB, not the line.
   CLOSED. [R results_54]
4. **avg_time_to_throw as a sack-rate forecaster.** Adds NO out-of-sample value (M1→M2 increment
   −0.43 to −0.52 pts). Killed. [R results_54]
5. **The ESPN kona historical-ADP repair path.** 2025 wiped to the 170.0 sentinel; surviving years
   S7-contaminated (promoted-vs-demoted players scored 220 vs 114). DO NOT RETRY — recorded in
   `population.json`. [R results_48]
6. **The adjectival camp-report test (`news_updated`).** Deleted by design: near-universal flag =
   no variance = null by construction. [R charter D6]
7. **H5f — the allocation-level scoring edge (charter §4.1.1's headline).** +2.7 [−6.2, +11.5],
   MDE ±12, firing 30.8%, sweep plateau with every CI through zero. The replacement tier absorbs
   its own position's bonus tilt. Closed at the allocation level. [R results_51]
8. **H5e — league-currency xFP as a role signal.** 0/4 positions survive BH; identical coverage to
   standard xFP means it cannot help the 171 no-xppg players by construction. Do not ship.
   [R results_59]
9. **The target-share mover overlay.** +34.9 [+10.3, +60.9] on the RB discovery slice, then
   **sign-flipped** on the WR replication (−5.7 [−35.7, +24.0]) — the exact C4 shape. Capped
   directional; never a board input on this evidence. [R results_58]
10. **ypc_spike and td_rate_spike as tier-change triggers.** Blacklisted as data: precision 0.233,
    FP/TP 3.3, and within their own gated universes the rate ranking is no better (ypc: WORSE,
    −0.038 [−0.074, −0.003]) than dumb window volume. [R results_57]
11. **snap_share_step at WR/TE as a trigger.** Below the random benchmark (0.075 / 0.065 vs
    0.097). RB-only. [R results_57]
12. **"Deep threat = ceiling" folklore.** Refuted under C13's absolute definition: the deep arm's
    p80-minus-replacement ceiling is LOWER (−25.8 [−40.3, −7.6]). [R results_52]
13. **H5b's valuable nulls.** Per-player rush-FD (both positions), rush_tier, rec_tier×RB, and
    rec_fd×RB rates: the league/position average wins — 8 of 11 cells closed. [R results_53]
14. **The legacy +5.2 as evidence.** Reproduced, then shown to be −3.3 under the measured opponent
    model alone and −18.2 [−58.5, +22.1] on the corrected instrument — an instrument artifact, not
    an edge. C3's closure is now double-locked. [R results_49]

---

## 10. WHAT I COULD NOT DO, AND WHY

- **The WS3 detector build proper (H3a, H3b, H3c) and the RB/WR suppression tests (H3e halves).**
  Post-draft by charter sequencing; this run built the ground truth, the matched-alert harness, the
  participation instrument, and the snapshot feed they require, and preregistered their bars.
- **WS6 fusion grading beyond what ran.** No paired grade for the H5b rate corrections, the H5c
  K re-rank, or any H2g swap — all pending the post-draft Grading phase; F2's calibration test,
  F4 reachability runs, and F5's point-by-point FFC-vs-`_SCALE_S` comparison were not executed
  (F5's data is staged in `ffc_adp_2026.csv`).
- **K and D/ST.** Stated scope cut (charter §6): the league starts both, the K sigma is flagged
  in-code as unresearched, and the panel carries no league-scored K/D-ST history; per L36/L38 any
  future advisor surface for them needs its own tracking.
- **The manual playcaller-history extension to 2014** (~160 team-seasons of hand news
  verification). Not code; not attempted. On this run's evidence it is justified ONLY for the H2a
  personnel gate — spending it on H2b/H2c would re-open dead lines.
- **H2d (guaranteed money), H4-RB/WR/TE paired grades, H5d.** Not executed this cycle (priority
  order); H5d additionally requires re-establishing the 62.1% OOS target on the league panel
  first.
- **2019/2020/2023 in the composite arm.** Unusable (backfilled/thin projections); the corrected
  instrument is therefore n=4 season clusters with MDE ±53 — the single binding constraint on
  every points verdict, restated wherever it matters.
- **The 2026 in-season snapshot path.** Cannot execute before Week 1 completes; verified
  end-to-end against 2025 instead, with a pre-stated cadence self-check for the residual risk.
  NGS/pbp weekly fetchers are not yet in the snapshot job (~15 lines each; NGS recommended before
  Week 1). Nothing is automated — the Tuesday runs are a human ritual until a scheduler is chosen.
- **The Sleeper mock corpus re-run (charter §0.5 exception 2) — COMPLETED 2026-07-31**, by the
  orchestrator in parallel with this run (the audit fix pass could not see it and wrongly assigned
  it to the user for Aug 4; corrected same day). Result: **300 one-QB / 2,001 total drafts** (from
  111 / 1,162), resume-safe, prior corpus backed up. Follow-up already run: the L51 survival-curve
  recheck on the fattened corpus (`results_62_dispersion_recheck.txt` [V], 62,890 matched picks vs
  43_'s 19,300) — **7 of 8 ADP buckets hold within the ±30% band**; the one outlier (ADP 7-12,
  measured s 1.91 vs shipped 2.80, −32%) is marginal, and every deviation is small and in one
  direction (measured dispersion ~11-18% tighter than shipped), consistent with ADP staleness in
  the older drafts as a confound. Verdict: L51 independently confirmed at 3.3x the pick sample; no
  pre-freeze constants change recommended; revisit post-draft with draft-date controlled.
- **Failures worth naming:** the charter's assumed 2025 price repair path (ESPN kona) failed
  outright and was replaced with the Sleeper instrument — every 2025-priced number in this
  programme now carries that instrument change; `49_grader_lib.report_primary`'s conditional-line
  bug is flagged but unfixed (new-files-only rule); the `.gitignore` gaps (49/50/51 caches,
  espn_adp_hist) were resolved at the audit fix pass (ignored as regenerable/dead-path; everything
  else committed and pushed); ESPN's whole-increment vs continuous return-yardage
  convention is unobservable until a live week (<~1–2 pts/season ceiling).
- **One season of history for H2g** (the depth-chart schema break makes 2025 the only comparable
  year, and 2024 turned out to be old-schema too) — which is why H2g's real test is the
  preregistered 2026 season, not anything computable today.
