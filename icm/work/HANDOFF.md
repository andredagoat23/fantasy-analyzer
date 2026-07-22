# SESSION HANDOFF — read this first if you're a fresh session

**How to use this file:** read `icm/CONTEXT.md` (the router) first, then this, then whatever reference
docs the task needs. Everything below is CURRENT as of **Jul 21, 2026**. **DEPLOYED = `origin/main` =
commit `835189e`** (Streamlit Cloud auto-deploys on push to main). **Local `main` is 2 commits AHEAD of
deployed, both UNPUSHED (so NOT deployed): `33d3aa3` (ICM-refresh docs) and `d56c90d` (L32 cohort
sanity-pull — `cohort_pull.py` + `test_cohort_pull.py`). A push deploys BOTH.**
Draft day: **July 31, 2026** — ESPN, 12-team, **slot 7**, custom PPR, 16 rounds. (The recent practice
mocks were slot 5 — the real draft is slot 7.)

---

## The stack as it stands (all LIVE on Streamlit Cloud)

### The modeling core (FROZEN pipeline — do not edit without an explicit ask)
1. **Calibrated Monte Carlo** (`compute_outcomes.py`): Waves 1/2/2b/2c. Depth-dependent
   `SIGMA_ANCHORS`, honest availability (~.82-.85), games↔per-game injury coupling, exact mean
   re-centering, draft-capital refit, team-changer split by PROVEN production, stable-vet narrowing,
   WR30+ fade, CV blend, stayed+new-HC tilt. **Backtested 60-62% band coverage incl. true OOS 2014-18
   (62.1%)** — not overfit. Re-tune acceptance tests: `icm/work/mc_research/05_distribution.py` +
   `06_finish_odds.py`. The late-round research campaign (Jul 21) independently re-validated the MC's
   availability/outcome numbers — no recalibration needed.
2. **Cohort priors** (`cohort_priors.py` → `cohort_data.csv`): each board player's 15 nearest
   historical seasons (kNN 2014-25) with empirical-Bayes-shrunken rates (m=25, LOSO-fitted). Now also
   emits **`cohort_trimmed` + `cohort_mean`** (L29 — outcomes are right-skewed; the advisor shows
   median + trimmed mean and tags TAIL-DRIVEN when they straddle 1.0x; raw mean stored but NEVER read
   — it explodes for cheap backup QBs).
3. **Coaching intelligence** (`sos_priors.py`, `data/`): news-verified 2026 — 10 new HCs
   (`new_hc_2026.csv`, drives the MC tilt), 18 playcallers (`playcallers_2026.csv` +
   `playcallers_hist.csv`). Validated: mispricing lives with FULL regime change (new HC); OC-only is
   price-neutral → MC tilts on HC only, playcaller = advisor usage context.
4. **Positional SOS** (`sos_data.csv`): 2026 opponents × 2025 per-position points allowed; tie-break
   context in the advisor table.

### The advisor (`advisor.py` — the app layer, freely editable; `draft-strategy.md` is source of truth)
5. **Value engine:** VONA (Value Over Next Available, shared board column + advisor), roster/lineup
   gates, role-lead bump, ROSTER RISK accumulation (L23), strategy-is-the-plan (L25).
   - **Cohort sanity-pull (L32, `cohort_pull.py`, called in `draft.py` `load_board`):** the LOSO-
     validated `cohort_trimmed` (finish/price multiplier) now nudges `rank_composite` at board-load —
     bounded (deadband / cap ±4 / startable-gate / freeze top-8), `trimmed` not median (L29), missing
     CSV = no-op. Flows to the Everything board, the risk dial, AND the advisor's TOP PICKS shortlist
     (`build_context` sorts on `rank_composite`). App-layer only; frozen pipeline untouched. Confirmed
     our TE lean is history-backed (McBride/Kittle/Kelce/Pitts) but flags Andrews as a real overpay.
6. **The read stack** (all Python-computed, enforced in TOP PICKS data per L8 — the model can't ignore them):
   - **PUNT READ** (L11/L28): unfilled QB/TE — risk-symmetric, depth-aware (`_expected_best_survivor`),
     NO positional margin. Correctly recommends elite QB when the metrics say so (the "Josh Allen at 29
     is CORRECT" resolution — do NOT re-open it as a bug; see L28).
   - **HEDGE READ** (L27): a FILLED risky 1-start starter (boom/bust/injury) → surface the
     hedge-vs-stream call once dedicated starters are set. Insurance, not a value pick.
   - **HANDCUFF READ** (L30/L31): GO-screened backups behind MY starting RBs only (never a bench
     player, never WR/TE). GO screen = prior role + offense + real price.
   - **DART READ** (L31): from R11+, TOP PICKS switches to deterministic BUY/neutral/FADE tiers from
     `_dart_profiles`. Full validated playbook (buys, fades, honesty cap, what FAILED validation) lives
     in `reference/late-round-strategy.md`. Backed by `role_priors.py` → `role_data.csv`.
   - **STREAMER ALERT** (L26): forces K/D-ST when remaining picks barely cover them.
   - Prompt-cached SYSTEM (~90% cache reads).
7. **Speculative PRE-READ** (`app_pages/draft.py`): background deep call within 3 picks of the clock,
   exact board-fingerprint guard. **FIXED (Jul 20): it never BLOCKS the pick** — the Recommend button
   serves a ready pre-read or falls straight to the fast ~4-5s live call; no 20s clock wait.
8. **Live sync**: ESPN + Sleeper (~81% coverage). **Preflight health check**: `tools/preflight.py`
   (run after the morning-of regen — validates every runtime CSV, NaN guards, ADP freshness,
   priors/role staleness, cross-file consistency; fault-tested). Plus `tools/name_audit.py` (network).

---

## Git / branch state (Jul 21)
- **`main` = `origin/main` = `835189e` — DEPLOYED.** Contains the entire advisor arc: L27 hedge,
  L28 punt read, L29 cohort trimmed-mean, L30/L31 late-round campaign, + preflight tool + prelook fix.
- **Two branches UNMERGED (both now BEHIND main → need a rebase before shipping):**
  - `opponent-aware-survival` (`832cf38`): per-position effective-horizon survival that folds in the
    live rosters of teams picking before my wheel. `opp=None` is byte-identical (can't regress); only
    the opp-active path is unproven. **Gated on a live-sync rehearsal.** Touches `advisor.py` — rebase
    will conflict. Design/diagnosis: `icm/work/plan.md` + `diagnosis.md`.
  - `yahoo-probe` (`b8cb697`): Yahoo probe tooling `tools/yahoo_probe/` — awaits the user's Yahoo
    dev-app + a mock to run the live-vs-post go/no-go (the library docstring already leans PASS).
    Doesn't touch `advisor.py`, rebases trivially. See `icm/work/yahoo-probe-scope.md`.

---

## Regeneration ritual (data drifts; regenerate close to draft day)
1. **Board** (FROZEN, deterministic): `.venv/bin/python run_all.py` (refreshes live ESPN ADP).
2. **Non-frozen priors** — rerun all three after a board rebuild:
   `cohort_priors.py`, `sos_priors.py`, **`role_priors.py`** (new — the late-round role layer; needs
   the local research panel `icm/work/mc_research/seasons_exp.parquet`, rebuildable via `01`+`02`).
   Commit the regenerated CSVs (deployed app reads them from the repo).
3. **Verify**: `tools/preflight.py` (must say PREFLIGHT OK — it now guards `role_data.csv` +
   priors-staleness), then `icm/work/mc_research/11_stress_test.py` + `12_full_system_stress.py`
   (both ALL PASS), then the unit suites (below). Then `tools/name_audit.py` (network) + eyeball the app.

## Tests (all plain-assert, run individually)
`tests/`: `test_bridge` (26), `test_sleeper` (13), `test_hedge` (8), `test_punt` (8, L28),
`test_cohort_skew` (10, L29), `test_dart` (21, L31), `test_handcuff` (16, L30/31),
`test_cohort_pull` (19, L32). Plus the two stress suites in `icm/work/mc_research/`.

## Verified vs pending
- **Deployed + fully regression-verified** (Jul 21): 102 unit checks, both stress suites ALL PASS,
  preflight clean, AppTest clean — verified on the exact `835189e` state before the push.
- **Pending live verify:** a user-driven **ESPN mock through the deployed app** is the best pre-draft
  rehearsal (also the gate for merging opponent-aware survival); a real **Sleeper mock** end-to-end.
- **Pre-draft-day checklist:** run the regeneration ritual above on fresh data; do one live ESPN mock.

---

## ROADMAP — next features (user-approved ordering)
1. **Opponent-aware survival** — BUILT on `opponent-aware-survival`, pending the live rehearsal + a
   rebase onto current main. (This was #1; it's done, just not shipped.)
2. **Positional-run detection** — "5 of last 8 picks were RBs → the cliff is NOW."
3. **Live news/injury layer** — the real July-31 difference-maker; needs a source decision. (The
   late-round research underscores this: ~half the handcuff edge and the sharpest signals are
   in-season, so a live layer + a FAAB plan is where the next real edge is.)
4. **Mock draft simulator** — rehearse slot 7 vs ADP-bots (`12_full_system_stress.py` is 80% of it).
5. **Rest-of-draft lookahead** · 6. August usage refresh · 7. ESPN-vs-consensus divergence ·
   8. Live draft grade · 9. "My guys" watchlist UI · 10. OC/coordinator dataset.

## Where the knowledge lives
- **Late-round playbook** (validated buys/fades/handcuffs + what FAILED validation):
  `icm/reference/late-round-strategy.md`. Campaign evidence: scratchpad `lateround/` (13 analysis +
  5 adversarial reports + SYNTHESIS.md — ephemeral, regenerable via the workflow).
- **MC research narrative:** `icm/work/mc-research-findings.md`; scripts + committed results in
  `icm/work/mc_research/`.
- **Lessons L1-L32:** `icm/reference/lessons.md` (**check before diagnosing** — L28 in particular:
  the Josh Allen pick is CORRECT, not a bug). Non-negotiables: `engineering-principles.md`,
  `collaboration.md`.
