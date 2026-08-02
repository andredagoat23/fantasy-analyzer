# SESSION HANDOFF — read this first if you're a fresh session

**How to use this file:** read `icm/CONTEXT.md` (the router) first, then this, then whatever reference
docs the task needs. Everything below is CURRENT as of **Aug 1, 2026**.

## Where things stand right now
- **DEPLOYED & CLEAN.** Local `main` = `origin/main` = **`7c96583`**, tree clean. The LIVE BOARD is
  the **`fc185e5` (L56)** state — every commit after it is research/docs and changed no app code.
  Streamlit Cloud auto-deploys on push — **pushing = deploying, always the user's call.**
- **Health:** preflight **OK** (0 blocking, 0 warnings). **18 unit suites green — 339 checks.** Both
  stress suites ALL PASS. Board + all priors regenerated **Jul 31** (L56 regen; 540 players). **No open DATA flags. NO open
  CODE items.** L52-L55 closed the advisor's survival/horizon defects; L56 fixed the QB sack
  shrinkage. What remains before Aug 7 is OPERATIONAL only.
- **⛔ CODE FREEZE Aug 3 — 2 days away. Draft Aug 7 — 6 days.** Last advisor-logic change Aug 3;
  Aug 4-6 = a full live mock, fixing only what the mock catches; Aug 7 = regen + preflight, no code.
  Rationale: this project's real bugs are caught by live mocks, not tests (L47 passed 195 checks and
  died in a mock). **Ship risky-but-verified changes INTO this window, not past it** (L51).
- **⚠️ THE DRAFT SLOT IS NOT SETTLED.** The handoff previously asserted slot 7; the user has since
  said it "could be anywhere," and the app is currently set to **slot 12**. Every pick number — and
  therefore every VONA, wheel and horizon — depends on it. **Confirm the real slot before Aug 7** and
  never hardcode one. Practice mocks have run at slots 1/5/10.

## ⚡ IF YOU READ NOTHING ELSE (Aug 1)
1. **The live mock at the real slot is the single highest-value item left.** Not started. Three things
   to probe: (a) does the two-option PLAN-FIRST format appear when the advisor deviates from a stated
   strategy? (b) does the R6-R7 QB window survive contact? (c) the L47 R7 roster-state thread.
2. **The slot is STILL not settled.** Everything keys off it.
3. **A methodology warning that cost half of Aug 1:** three of this session's QB-timing claims were
   WRONG and were caught by the user checking them against his own mocks — see **L57**. The paired
   MEASUREMENTS held up every time; the NARRATIVES about why did not. Before repeating any aggregate
   as a finding, look at the underlying names and the distribution shape.
4. **`icm/work/entanglement/PREREGISTRATION.md` is a DRAFT.** Its named-player list MUST be filled
   from the 2026-08-07 ADP snapshot, then committed AND pushed, with the SHA recorded here. That
   second push is the LOCK.
5. **Tuesday snapshot ritual** — `.venv/bin/python tools/weekly_snapshot.py`, plus a mandatory extra
   run on **Fri Aug 7 (draft morning)**. A season of dated snapshots cannot be reconstructed later.

## Shipped this session (Jul 28 - Aug 1) — all live
- **L57 (Aug 1) — a bimodal median is not a policy (RETRACTION lesson, no code).** Three QB-timing
  claims withdrawn; `63_`/`63b_`/`63c_`/`63d_` retracted in place. See L57 and the QB-timing block
  under Open Questions for what actually replaced them.
- **Research `62_` (Jul 31) — the L51 survival curve CONFIRMED at 3.3x the picks.** The Sleeper
  corpus re-crawl grew it to **300 one-QB / 2,001 drafts** (was 111/1,162); re-measuring dispersion on
  **62,890 matched picks** (was 19,300) holds in **7 of 8 ADP buckets** within ±30%. The one outlier
  (ADP 7-12, s 1.91 vs shipped 2.80) is marginal and every deviation is small and one-directional.
  No pre-freeze change. `advisor._SCALE_S` stands.
- **L56 (Jul 31) — QB SACK SHRINKAGE FIXED (frozen-file change, on the user's explicit instruction).**
  `apply_bonuses.py` shrank each QB's sack rate with `K=12`; CV on 7 seasons/179 QB-seasons says
  **K=768** (+14.1% excess OOS MSE at 12). **The trap: `K` was SHARED with the long-TD 40+/50+ rates** —
  ~60 TD chances vs ~1,500 throws over 2023-25, so the same constant shrank TDs a sensible ~12% and
  sacks only ~0.8%. Fixed with a separate **`K_SACK = 768`** in `scoring_config.py`; `K` untouched.
  Isolation verified: RB/WR/TE top-12 `bonus_points` moved <1 pt, QB moved 9.42. Board effect: Maye
  QB10→QB8, Dart QB13→QB11, 11 of top-14 QBs shift 1-2 spots, **Allen stays QB1 by 56 pts**. Full regen
  + priors + D/ST rerun; 339 checks, both stress suites, preflight all green. I recommended NOT
  shipping (points delta +0.17 [-0.40,+0.73]); the user overruled on correctness grounds — see L56.
- **L55 (Jul 30) — REST-OF-DRAFT LOOKAHEAD.** Pre-draft at slot 6 the advisor quoted Josh Allen
  `risky→#19 (68%)` and called him "still alive" at **R3 #30**, where he is **20.9%**. The pick numbers
  were right (L53 working) but **every survival figure in the context sat at ONE pick** — measured: 25
  figures, all `#19`, with #30/#43/#54/#67 carrying none. New `available_at_my_picks()` renders
  `WHO'S REALISTICALLY LEFT AT MY PICKS` for my next 8 picks: best 3 overall + top 3 per position, bar
  50% (`_PUNT_STREAM_P`). Picks with odds: **1 → 8**. +23% context. **Two traps captured in tests:**
  the list is ordered BEST-VALUE first so the % ASCENDS (re-sorting by probability picks the worst
  player), and the block must start at `_horizon`, never my current pick.
- **L54 (Jul 30) — wheel bands re-based on measured survival + the probability now rides in the cell.**
  The old rule failed at each boundary for a DIFFERENT reason: `adp <= horizon` is exactly p=50% at
  every board position (scale-invariant but misplaced — it called Josh Allen at **49.5%** "gone"),
  while `adp >= horizon+12` meant **99.9% at the top and 66.2% late** (L51's orphan). Now thresholded
  on `_survival_prob`: `gone <20%`, `safe >=70%`, risky between, from `_wheel_odds()` so the word and
  the number come from one call. Cells read `risky→#13 (59%)`. **2.7% of cells change**; the `risky`
  band (what the RISK APPETITE dial breaks) grows 105 → 182 cells. Thresholds are a judgment call, NOT
  backtested — the direction and magnitude are measured. `test_wheel` 32 → 40.
- **L53 (Jul 30) — the HORIZON was the wrong pick, and nothing computed the schedule.** Three user
  catches, one root. (a) `MY PICKS` line: the context had **3 pick numbers in 12,746 chars** and the
  model invented "rounds 3-7 = picks 25-35" (slot 10's real R3-R7 are #34/#39/#58/#63/#82) — now 17
  pick numbers, read never computed. (b) **PUNT READ was fabricating in PYTHON** — `lasts_round` was
  `floor(ADP/teams)`, the round the MARKET takes him in, rendered as the round he lasts to, slot-blind
  ("~R7" was 61%/40%/36% at slots 1/10/12). **This one fires at `my_turn: True` and could have cost a
  real pick.** Now measured at MY pick with the number shown: `lasts ~R6 (84%)`. (c) **L52 Tier 2**:
  `_horizon()` now returns `following` in BOTH turn states; (d) TOP PICKS is filtered to reachable
  players when it is not my turn (it was six `gone` players). `my_pick_schedule()` + `_horizon()` are
  now single sources of truth and `app_pages/draft.py` calls both — the arithmetic was in FOUR places
  and wrong in three.
- **L52 WHEEL REFERENT (Jul 29).** The advisor told the user an ADP-14.3 RB was "safe to #23" at
  ~75% when true survival to #23 is **9.0%**. `_horizon()` returns `next_pick` (not `following`) when
  it is **NOT my turn**, so pre-draft the label was computed to the ON-DECK pick while the DRAFT
  POSITION line named two picks and the cell was a bare word. Fixed DISPLAY-ONLY: `_wheel_cell`
  renders `safe→#2`, the not-my-turn line binds the column, the prompt quotes the cell instead of
  inferring `#X`. **No math touched.** `tests/test_wheel.py` (32) — and it is the FIRST suite to
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

## Git / branch state (Aug 1)
- **`main` = `origin/main` = `7c96583` — pushed, tree clean.** The DEPLOYED BOARD is `fc185e5` (L56);
  `242858d` / `d50b83c` / `19ef3c8` / `7c96583` are research + docs only and changed no app code.
- Recent: `7c96583` Research 65_ · `19ef3c8` retract 63d_ · `d50b83c` L57 + Research 64_ ·
  `242858d` Research 63_ (RETRACTED) · `fc185e5` **L56 (the live board)**.
- **One branch UNMERGED:** `yahoo-probe` (`b8cb697`) — awaits the user's Yahoo dev-app + a mock.
  Doesn't touch `advisor.py`.
- **2026-07-31 — ENTANGLEMENT run committed and PUSHED: commit `b93a78b`, pushed
  2026-07-31T19:55:03Z.** Contains `icm/work/entanglement/BLUEPRINT.md` and
  **`icm/work/entanglement/PREREGISTRATION.md` in DRAFT state — that push timestamps the P1–P8
  hypothesis-level predictions** (charter §9.1 lock protocol: the named-player fill from the
  2026-08-07 snapshot is the second, LOCK push, whose SHA gets its own entry here), plus scripts
  `46_`–`60_`, `results_46..61`, `population.json`, the research parquets,
  `tools/weekly_snapshot.py`, `data/snapshots/2026-07-31/`, and
  `data/projection_archive/2026_preseason_2026-07-31.csv`. The 49/50/51 caches, `espn_adp_hist/`
  (~31MB dead kona pull), and `*.bak` files are now ignored via `icm/work/mc_research/.gitignore`.
  No app code touched — the deploy was a no-op.

## Regeneration ritual (last run Jul 31 for L56 — RERUN THE MORNING OF THE DRAFT)
1. **Board:** `.venv/bin/python run_all.py` (14 steps; refreshes live ESPN ADP + projections).
2. **Priors** — NOT in the chain, rerun all three after any board rebuild: `cohort_priors.py`,
   `sos_priors.py`, `role_priors.py`.
3. **D/ST:** `.venv/bin/python load_dst.py`.
4. **Verify:** `tools/preflight.py` → `mc_research/11` + `12` stress → the 16 unit suites →
   `tools/name_audit.py`, `tools/fa_watch.py`, `tools/injury_watch.py` (all network) → eyeball the app.
5. **Commit the regenerated CSVs together** — the deployed app reads board + priors from the repo.

## Tests (plain-assert, run individually: `.venv/bin/python tests/<file>.py`)
**18 suites, 339 checks, all green:** `test_schedule` (57), **`test_wheel` (40)**, `test_bridge` (26), `test_opponent` (25),
`test_dart` (23), `test_injury` (22), `test_cold` (21), `test_cohort_pull` (19), `test_handcuff` (16),
`test_dst` (14), `test_sleeper` (13), `test_shape` (11), `test_cohort_skew` (10), `test_hedge` (8),
`test_punt` (12), `test_defer` (8), `test_kicker` (7), `test_role_alpha` (7). Plus the two stress
suites in `mc_research/` (`11_` invariants + cohort LOSO, `12_` 24 offline drafts).

⚠️ **COVERAGE HOLE, now half-closed (L52).** Every suite and every offline mock (`12_`/`13_`/`14_`/
`45_`) sets `my_turn: True`. `test_wheel` is the only one that exercises `my_turn: False` — the branch
used for PRE-DRAFT STRATEGY CHAT, where a whole conversational mode of the product ran untested. When
adding a suite, ask which turn state it covers.

---

## ⚠️ OPEN QUESTIONS / KNOWN IMPERFECTIONS (read before "fixing" anything)
- **The wheel BAND THRESHOLDS (`_WHEEL_GONE_P` 0.20 / `_WHEEL_SAFE_P` 0.70) are a JUDGMENT CALL, not
  backtested.** What IS measured: the direction (a 49.5% player must not read "gone") and the
  magnitude (2.7% of cells move; a 0.15/0.60 → 0.30/0.80 sweep all landed at 3-4%, so the rule is
  insensitive to the exact numbers). The probability now prints beside the label, so a borderline band
  is self-correcting for the reader. Don't retune these on a hunch — if they ever get revisited, it
  should be a paired backtest like `mc_research/18_`, after Aug 7.
- **QB TIMING — what survived Aug 1, and what did NOT.** `63_`/`63b_`/`63c_`/`63d_` are **RETRACTED**
  (L57): their "natural" baseline read a BIMODAL median as a policy. **Withdrawn:** "the advisor waits
  two rounds too long", "taking a QB at pick 2 costs 18.6", "the PUNT READ errs early at middle seats",
  and a proposed `data/qb_timing.csv` advisory read (never built; the emitted file was deleted).
  **What replaced them, measured conditionally on the elite QB actually being available (`64_`/`65_`,
  127/400 qualifying seeds at slot 2):** Josh Allen reaches slot 2's #23 in **32%** of drafts and the
  advisor takes him **99-100%** of the time when he does — it does NOT wait. Taking him beats
  executing a clean R6-R7 plan by **+9.1 risk-adj [+5.6,+12.7] / +24.1 floor**, not the +17.9 that
  `64_`'s drifting-to-R8 baseline suggested. The real trade is **Allen + a ~48%-bust R6 flier vs Chase
  Brown (VOLS 96.0, VALUE +12) + Bo Nix (46% bust)**. NOTE the corrected mechanism: both arms take a
  ~47%-bust R6 player — what differs is that Nix is a forced STARTER while the flier is depth.
  **Judgment, not a shipping proposal:** projections held fixed, so this is what the board believes.
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
- **Aug 3 — FREEZE, then a full live mock at the REAL slot.** Highest-value item left, NOT started.
  It validates L51-L56 live AND is the only way to close the R7 thread. Download the pick log.
  **Probe three things:** (a) set a strategy with a hard constraint and tempt a deviation — does the
  two-option PLAN-FIRST format actually render? (b) does the R6-R7 QB window hold up in a real draft?
  (c) the R7 roster-state thread.
- **Aug 4 (Tue) — `tools/weekly_snapshot.py`.** Start the weekly ritual; commit AND push each dated dir.
- **Aug 5-6 — rerun `injury_watch.py` and `fa_watch.py`.** Preseason week 1 turns both lists over.
- **Aug 7 morning — `run_all.py` + priors + `load_dst.py` + preflight + injury watch. NO CODE.**
  Then **`tools/weekly_snapshot.py`** (the draft-morning capture the preregistration is stated
  against), then FILL the prereg's named-player list, commit, **push**, and record the SHA above.
- **Watch list as of Jul 31 (re-run after the L56 regen):** 3 HARD flags, all PUP/surgery —
  **George Kittle (TE9, ADP 90.2, ~R8)**, **Alec Pierce (WR27, ADP 94.7, ~R8)**,
  **Zach Charbonnet (RB43, ADP 154.2, ~R13)**. Kittle and Pierce both land in range around R8.
  **Stefon Diggs (ADP 165.6) is still UNSIGNED** and correctly absent from the board — if he signs
  before Aug 7, re-run `run_all.py` to project him on. (Tucker Kraft cleared since Jul 29.)

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
