# SESSION HANDOFF — read this first if you're a fresh session

**How to use this file:** read `icm/CONTEXT.md` (the router) first, then this, then whatever reference
docs the task needs. Everything below is CURRENT as of **Jul 29, 2026**.

## Where things stand right now
- **DEPLOYED & CLEAN.** Local `main` = `origin/main` = **HEAD**, tree clean (HEAD = the **L52**
  wheel-referent fix; `git log -3` for hashes). Streamlit Cloud auto-deploys on push — **pushing =
  deploying, always the user's call.**
- **Health:** preflight **OK** (0 blocking, 0 warnings). **17 unit suites green — 264 checks.** Both
  stress suites ALL PASS. Board + all priors regenerated **Jul 28**. **No open DATA flags. Two open
  CODE items, both deliberate — L52 Tier 2 + Tier 3 (see Open questions).**
- **⛔ CODE FREEZE Aug 3 — 5 days away. Draft Aug 7 — 9 days.** Last advisor-logic change Aug 3;
  Aug 4-6 = a full live mock, fixing only what the mock catches; Aug 7 = regen + preflight, no code.
  Rationale: this project's real bugs are caught by live mocks, not tests (L47 passed 195 checks and
  died in a mock). **Ship risky-but-verified changes INTO this window, not past it** (L51).
- **⚠️ THE DRAFT SLOT IS NOT SETTLED.** The handoff previously asserted slot 7; the user has since
  said it "could be anywhere," and the app is currently set to **slot 12**. Every pick number — and
  therefore every VONA, wheel and horizon — depends on it. **Confirm the real slot before Aug 7** and
  never hardcode one. Practice mocks have run at slots 1/5/10.

## Shipped this session (Jul 28-29) — all live
- **L52 WHEEL REFERENT (Jul 29).** The advisor told the user an ADP-14.3 RB was "safe to #23" at
  ~75% when true survival to #23 is **9.0%**. `_horizon()` returns `next_pick` (not `following`) when
  it is **NOT my turn**, so pre-draft the label was computed to the ON-DECK pick while the DRAFT
  POSITION line named two picks and the cell was a bare word. Fixed DISPLAY-ONLY: `_wheel_cell`
  renders `safe→#2`, the not-my-turn line binds the column, the prompt quotes the cell instead of
  inferring `#X`. **No math touched.** `tests/test_wheel.py` (26) — and it is the FIRST suite to
  exercise `my_turn: False`; every prior suite and mock set it True.
- **Research `45_` (Jul 29).** 100 mocks × 12 slots = 1,200 drafts / 19,200 advised picks. Roster
  shape is near slot-invariant (1.0 QB / 6.4-6.7 RB / 6.2-6.5 WR / 1.0-1.1 TE / 1.0 K at EVERY seat)
  — the slot changes who and when, not what. QB timing bifurcates at the midpoint (Allen R2: 64% at
  slot 5, <2% at slots 11-12 which punt to R8); TE mirrors it; R1 flips RB→WR moving back.
- **L48b COLD POSITION read.** Fires when the room is SKIPPING a position I can still start. The
  HOT/"a run is on, act early" half was **measured on 372k real Sleeper picks and CUT** — runs do not
  continue. `tests/test_cold.py` (21).
- **Draft-day RESILIENCE.** A "What the math says" panel renders TOP PICKS + the whole read stack, and
  an API failure now serves the **computed pick by name** instead of an error. Sits OUTSIDE the
  api_key gate, so it works with no key at all.
- **HEALTH FLAGS.** Live Sleeper injury status → board `Inj` column + a named HEALTH FLAGS line.
  **NOT a gate** (user's explicit call: a PUP player can still be value at a discount);
  `tests/test_injury.py` (22) locks that in. Severity in `utils.injury_severity`.
- **L51 per-player ADP SURVIVAL CURVE.** `_survival_prob` used one logistic scale (7.0) for the whole
  board; measured on 19,300 real picks the true scale runs **1.8 at the top to 17.9 late**. Fixed by
  interpolating the measured dispersion, behind `advisor.USE_MEASURED_SCALE` (one-line revert).
- **Full REGEN** (Jul 28) — fresh ESPN ADP + projections, all three priors, D/ST.
- **`tools/archive_projections.py`** — snapshots FP + ESPN + Sleeper preseason projections and BOTH
  ADPs each year, so the blend weight can eventually be set from evidence. First snapshot committed.

## The build's current capabilities
- **Custom scoring COMPLETE + verified vs the real ESPN settings (L41)**, single source of truth
  `scoring_config.py` (L42). QB **sacks** were the big miss (~−30 to −55/QB).
- **Team D/ST SCORED (L43)** — `load_dst.py`, streamer layer, stays OFF the cross-position board.
- **Projections are a FP+ESPN CONSENSUS (L44)** — component-level blend, weights `0.35 FP / 0.65
  ESPN`. See the ⚠️ under "Open questions" — that weight is unvalidated and probably mis-set.
- **Composite weights RE-TUNED from a 13-season LOSO backtest (L45)** — market .36→.19 into ceiling
  .13→.25 + floor .09→.15. Per-position weights tested and REJECTED (`mc_research/19`).
- **Position-shape advisory is HYBRID (L46)** — durable prose + a computed `POSITION SHAPE` line.
- **Opponent-aware survival SHIPPED + REHEARSED (L40)** — 192-pick live mock held. Kill-switch in
  Draft settings.
- **✅ SEA/Charbonnet flag RESOLVED — board is RIGHT.** Do NOT re-open.

---

## The stack (all LIVE on Streamlit Cloud)

### Modeling core (FROZEN — do not edit without an explicit ask; scoring VALUES live in `scoring_config.py`)
1. **Calibrated Monte Carlo** (`compute_outcomes.py`) — backtested 60-62% band coverage incl. true
   OOS 2014-18 (62.1%). Its **position-level** availability prior is CORRECT and now independently
   validated: prior-year games predicts this year's at r=+0.019 (L49).
2. **Cohort priors** (`cohort_priors.py` → `cohort_data.csv`) — 15 nearest historical seasons, kNN.
3. **Coaching intel** (`sos_priors.py`) — 10 new HCs + 18 playcallers.
4. **Positional SOS** (`sos_data.csv`).
5. **Projection layer** (`projections.py`, L44) — FP+ESPN component consensus. D/ST scored separately.

### The advisor (`advisor.py` — app layer, freely editable; `draft-strategy.md` is source of truth)
6. **Value engine:** VONA (survival curve now per-player, L51), roster/lineup gates (`_lineup_gaps`),
   ROSTER RISK (L23), strategy-is-the-plan (L25), cohort sanity-pull (L32).
7. **The read stack** (Python-computed, enforced in TOP PICKS per L8): PUNT (L11/L28), DEFER (L33),
   HEDGE (L27), HANDCUFF (L30/31), DART (L31/L37, R11+), STREAMER (L26), **POSITION SHAPE** (L46),
   **COLD POSITION** (L48b), **HEALTH FLAGS** (L49). K/D-ST hidden once the slot is filled (L47).
8. **Speculative PRE-READ** — background deep call within 3 picks; never BLOCKS the pick.
9. **Resilience** — the computed pick survives an API outage or a missing key.
10. **Live sync + logging:** ESPN + Sleeper + FA bridge; per-pick context log (L47).
11. **Tools:** `preflight.py`, `name_audit.py`, `fa_watch.py`, **`injury_watch.py`**,
    **`archive_projections.py`**.

---

## Git / branch state (Jul 29)
- **`main` = `origin/main` = `6cb7300` — DEPLOYED**, tree clean.
- **One branch UNMERGED:** `yahoo-probe` (`b8cb697`) — awaits the user's Yahoo dev-app + a mock.
  Doesn't touch `advisor.py`.

## Regeneration ritual (last run Jul 28 — rerun the morning of the draft)
1. **Board:** `.venv/bin/python run_all.py` (14 steps; refreshes live ESPN ADP + projections).
2. **Priors** — NOT in the chain, rerun all three after any board rebuild: `cohort_priors.py`,
   `sos_priors.py`, `role_priors.py`.
3. **D/ST:** `.venv/bin/python load_dst.py`.
4. **Verify:** `tools/preflight.py` → `mc_research/11` + `12` stress → the 16 unit suites →
   `tools/name_audit.py`, `tools/fa_watch.py`, `tools/injury_watch.py` (all network) → eyeball the app.
5. **Commit the regenerated CSVs together** — the deployed app reads board + priors from the repo.

## Tests (plain-assert, run individually: `.venv/bin/python tests/<file>.py`)
**17 suites, 264 checks, all green:** `test_bridge` (26), **`test_wheel` (26)**, `test_opponent` (25),
`test_dart` (23), `test_injury` (22), `test_cold` (21), `test_cohort_pull` (19), `test_handcuff` (16),
`test_dst` (14), `test_sleeper` (13), `test_shape` (11), `test_cohort_skew` (10), `test_hedge` (8),
`test_punt` (8), `test_defer` (8), `test_kicker` (7), `test_role_alpha` (7). Plus the two stress
suites in `mc_research/` (`11_` invariants + cohort LOSO, `12_` 24 offline drafts).

⚠️ **COVERAGE HOLE, now half-closed (L52).** Every suite and every offline mock (`12_`/`13_`/`14_`/
`45_`) sets `my_turn: True`. `test_wheel` is the only one that exercises `my_turn: False` — the branch
used for PRE-DRAFT STRATEGY CHAT, where a whole conversational mode of the product ran untested. When
adding a suite, ask which turn state it covers.

---

## ⚠️ OPEN QUESTIONS / KNOWN IMPERFECTIONS (read before "fixing" anything)
- **L52 TIER 2 — `_horizon()` + `_wheel_label`, the one real open code item.** Two halves, one root
  cause. (a) `_horizon()` returns `next_pick` when it is NOT my turn, so pre-draft VONA and the wheel
  label answer "what's left when I'm first on the clock" instead of "what's left at the pick AFTER the
  one I'm deciding" — that is ALSO the source of the pre-draft VONA complaint (`best_wait[WR]` = 130.5
  exceeding Amon-Ra St. Brown's 128.5, i.e. implying an elite WR falls to you; true at a next-pick of
  ~6, false at any round-2 pick). (b) `_wheel_label` still buckets on raw ADP arithmetic with a flat
  12-pick cushion while `_survival_prob` got L51's measured curve — measured across the board, `gone`
  spans **0.0%-50.0%** true survival and `safe` spans **67.5%-100%** (Josh Allen at #23 is 49.5% and
  labeled `gone`). Re-base the label on `_survival_prob`. **Group D of `test_wheel.py` pins the
  current rule on purpose — those 6 checks MUST go red when you do this.** Behavior change to what
  the model reads on every pick: needs both stress suites AND the Aug 3 mock.
- **L52 TIER 3 — put the probability in the cell** (`gone→#23 (9%)`). Tier 1 anchored the label; only
  a number kills the fabrication (the advisor invented "~75%" because the context contains no
  probability anywhere and the prompt forbids computing one).
- **The R7 roster-state thread** (L47) — a 4th RB recommended at R7 with WR2 open, never reproduced
  offline. Per-pick logging is in place: after a weird pick, **Draft settings → "Download pick log"**.
  **Don't patch the gate blind.** This is the main thing the Aug 3 mock is for.
- **The FP/ESPN blend weight (0.35/0.65) is unvalidated and probably mis-set.** It was a judgment
  call ("lean ESPN, it's the room the draft runs in") and ESPN is the WEAKER of the two sources we
  can test. Leaning away from it is worth ~+60 pts out-of-sample over 4 clean seasons
  (`mc_research/38_`/`39_`) — BUT on the 2026 board specifically the three sources agree closely
  enough that any mix moves only ~2 players in the top 40 (`40_`/`41_`). **Do not touch
  `scoring_config` before the draft.** After Aug 7, and ideally after another season of archived
  projections, revisit it.
- **L51's curve slightly over-corrects at the very top** — it says "essentially never" where reality
  says 0.5%. Worth ~1 VOLS point in `best_wait`; immaterial, but not exact.
- **L51 backtested at −3.0 pts** (CI [−5.1,−0.9], 80.5% of drafts identical). Shipped for
  correctness/trust, not for points. If the mock shows anything odd, flip `USE_MEASURED_SCALE`.

## PRE-DRAFT CHECKLIST (the remaining work is operational, not features)
- **Aug 3 — FREEZE, then a full live mock at the REAL slot.** Highest-value item left. It validates
  L51 + the COLD read live AND is the only way to close the R7 thread. Download the pick log.
- **Aug 5-6 — rerun `injury_watch.py` and `fa_watch.py`.** Preseason week 1 turns both lists over.
- **Aug 7 morning — `run_all.py` + priors + preflight + injury watch. NO CODE.**
- **Watch list as of Jul 29:** 4 HARD injury flags — **George Kittle (TE9, ADP 87, PUP/surgery)**,
  Alec Pierce (94), Tucker Kraft (110), Charbonnet (156). Three live unsigned FAs with fresh news —
  **Diggs (165), Tyreek Hill (169), Deebo Samuel (170)**; if any signs, re-run `run_all.py` to
  project them onto the board.

---

## ROADMAP
1. ✅ **Opponent-aware survival** — SHIPPED + rehearsed (L40).
2. ✅ **Projection consensus** — SHIPPED (L44). Weight still unvalidated, see Open Questions.
3. ✅ **Positional-run detection** — SHIPPED as `COLD POSITION` (L48b); the run/HOT half was measured
   and cut. Live-fire check at the Aug 3 mock.
4. **Live news/injury layer** — `fa_watch.py` + **`injury_watch.py` + in-app HEALTH FLAGS SHIPPED.**
   Next: in-season `nflverse load_injuries` + a FAAB plan (~half the edge is in-season).
5. ⛔ **"Upgrade a weak starter" — CLOSED, built and reverted unshipped (L50). Do NOT rebuild.** The
   gap in `_lineup_gaps` is real but the STATE CANNOT ARISE: over 552 post-lineup decision points the
   best available at a filled position beat my weakest starter by at most **−0.4 VOLS**. Drafting by
   VALUE means your starter is by construction the best you could have taken there.
6. **Mock draft simulator** (`12_`/`13_` are ~80% of it) · 7. **Rest-of-draft lookahead** (a real
   design change: VONA currently looks exactly ONE pick ahead — L11) · 8. Live draft grade ·
   9. Home hub (deferred past Aug 7).
10. **THE BIG ONE, post-draft: in-season tools** — waiver, trade, start/sit. `36_` measured that
    projection accuracy is worth **~130-200 roster points per +0.05 Spearman**, far and away the
    biggest lever in this project, and the in-season market is much less efficient than draft ADP.

## ⛔ CLOSED RESEARCH — do not re-open without new data
- **Per-player PREREQUISITES (L49, `mc_research/23_`-`33_`).** Ran the whole board, stress-tested with
  bootstraps + sensitivity grids, then **failed a harsh paired backtest**: +5.2 pts, 51.5% win rate,
  and the harder the rules were applied the MORE points they lost (−59.5 at 4x). The headline finding
  (capital × no-role, +42.3pp, P=1.00) failed REPLICATION and was withdrawn.
  **What survives is knowledge, not rules:** unavailability drives 73-85% of busts in EVERY round band
  and is near-unforecastable (r=+0.019) — which VALIDATES the MC's position-level prior; RB is
  structurally fragile (52% vs WR 67% play 15+); R2-3 is the best value band, R4-6 the worst (RB bust
  31%); durability is over-priced early and under-priced late (+15.8pp at R11+, never backtested in
  isolation — the one cheap loose end).
- **Blend reweighting** (`37_`-`41_`) — see Open Questions. Direction generalises, magnitude doesn't,
  and it barely moves the 2026 board.

## Where the knowledge lives
- **Lessons L1–L51:** `icm/reference/lessons.md` (**check before diagnosing** — esp. L28: the Josh
  Allen pick is CORRECT, not a bug). Non-negotiables: `engineering-principles.md`,
  `collaboration.md`.
- **Sources of truth:** `draft-strategy.md` (advisor), `pipeline.md` (frozen chain + scoring),
  `bridge.md` (live sync), `architecture.md` (system map), `late-round-strategy.md` (R11+).
- **Research findings:** `mc-research-findings.md`, `run-dynamics-findings.md`,
  `r1-prerequisites-findings.md`, and `mc_research/` scripts `00_`-`44_` with their `results_*.txt`.
- **Resolved — do NOT re-open:** `memory/sea-backfield-projection-flag.md`,
  `memory/qb-vols-overvaluation.md`, `memory/espn-ppr-rank-decision.md`.
