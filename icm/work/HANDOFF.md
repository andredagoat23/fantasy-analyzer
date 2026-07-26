# SESSION HANDOFF — read this first if you're a fresh session

**How to use this file:** read `icm/CONTEXT.md` (the router) first, then this, then whatever reference
docs the task needs. Everything below is CURRENT as of **Jul 25, 2026**.

## Where things stand right now
- **DEPLOYED & CLEAN.** Local `main` = `origin/main` = **`fe94011`**, working tree clean. Streamlit
  Cloud auto-deploys on push to `main`, so `main` == what's live.
- **Health:** preflight **OK** (0 blocking, 0 warnings). **All 13 unit suites green — 183 checks.**
  Board + all three priors regenerated this session (L39). No open CODE items, no open DATA flags.
- **Opponent-aware survival is SHIPPED (L40, roadmap #1)** — survival/VONA/wheel now fold in the live
  rosters of the teams picking before my wheel (per-position effective horizon). Additive: `opp=None` is
  byte-identical. Kill-switch = the "Opponent-aware survival" toggle in Draft settings (default on). Its
  one true rehearsal is a live-sync mock (opp-active only fires with live rosters) — see L40.
- **Draft day: July 31, 2026** — ESPN, 12-team, **slot 7**, custom PPR, 16 rounds. (Recent practice
  mocks ran at slots 5 and 1; the real draft is **slot 7** — don't hardcode a slot.)
- ✅ **SEA/Charbonnet flag RESOLVED (Jul 25) — the board was RIGHT.** The board has Jadarian Price as
  SEA RB1 over Charbonnet; verified against real news that's correct — Walker signed with **KC** and
  Charbonnet **tore his ACL** (out most/all of 2026), so a first-round rookie is the legit lead. No
  board change needed. Do NOT re-open. See `memory/sea-backfield-projection-flag.md`.

## What shipped this session (L32–L39) — the live-mock rehearsal arc
A full live-mock rehearsal ran end-to-end; the **FA bridge synced all 192 picks cleanly**, and the
user's post-mock catches drove every fix below. Three themes:

**A. The "stale-role" bug class — now patched in FOUR places.** A player who changed teams (or just got
promoted) was being valued on his OLD/rookie role. Fixed everywhere it lived:
- **L16** — composite `role_pct` for team-changers (pre-existing).
- **L34** — the WR *alpha* bump now gated by cross-position target competition (the **Mike Evans** catch:
  he shares targets with CMC/Kittle/Pearsall, so no alpha bump). `tests/test_role_alpha.py`.
- **L37** — the DART post-hype-WR buy now **excludes movers** (the **Jauan Jennings** catch: it was
  buying him on a stale 36% SF share though he's now MIN's buried WR3). `tests/test_dart.py`.
- **L39** — an **ascending same-team clear lead** now uses forward VOLS for role instead of stale rookie
  xppg (the **Bhayshaul Tuten** catch: 88→59, alongside Montgomery). Gate is tight (`role_lead ≥ 15`,
  `vols > 0`, margin ≥ 0.25, non-mover). **BOARD REGENERATED** — only Tuten moved >1; rest ripple ±1.

**B. The advisor was recommending things off the board.** Two "from memory" leaks, both fixed by handing
the advisor the *board's own* ranking in `build_context`:
- **L36 — D/ST:** it kept recommending an already-drafted defense (Houston). Now threads
  `bridge.drafted_dsts` and hands a filtered D/ST ranking. `tests/test_dst.py`.
- **L38 / L38b — kicker:** it recommended Jake Moody (whom we rank K19) from memory. Now handed the
  board's top-8 K ranking. **L38b was the real fix:** every *good* K trips `proj_outlier` (VOLS ranks
  Ks ~#50 vs ECR ~#200), and `build_context` was dropping proj_outliers — so the K list had been gutted
  to the 8 worst Ks. Now K is exempt from that drop → recommends **Aubrey**, not Moody. `tests/test_kicker.py`.

**C. Position-shape advisories (guidance notes, NOT board re-ranks).** The composite is already near-even
on these; the advisor just needs to know the *shape*:
- **L33** next-pick **DEFER** read (survival-primary: `surv ≥ 0.6 AND best_rbwr > 0`) + **TE-shape**
  (top-heavy, R6 pocket, avoid the R4-5 dead zone). `tests/test_defer.py`.
- **QB-shape** (deep — punt to the R7-9 pocket; mirror of TE-shape).
- **L35** ambiguous-room **pairs** (two breakout guys in one room → buy BOTH RBs, but diversify WRs).
- **WR-shape** (validated thin + risky — reliable tier gone by ~WR10, bust 38% vs RB 25% → secure
  reliable WRs early).

**Plus L32** (start-of-session): the **cohort sanity-pull** (`cohort_pull.py`) — the LOSO-validated
`cohort_trimmed` multiplier nudges `rank_composite` at board-load. And the **strategy bake-off harness**
(`icm/work/mc_research/13_strategy_bakeoff.py` + `14`/`15`) proved our strategy wins on value/floor/injury
at all 12 slots (Zero-RB #2 after the opponent-model fix).

**Projection-source research (this session):** no clearly-better FREE *forward* projection than FP (the
strong ones — Fantasy Points/ETR/PFF/FTN/RotoWire — are paid). `ff_opportunity` (ffverse) is the best
free *opportunity* model and is **already ingested** (it's `xppg`). The realistic future upgrade is a
**FP+ESPN projection consensus + grounding `role_lead` in ff_opportunity** — a scoped feature, not a
quick fix (see ROADMAP #3). (NB: the Price>Charbonnet case turned out NOT to be a single-source miss —
FP was right — so it's no longer the motivating example; the feature still has general merit.)

---

## The stack as it stands (all LIVE on Streamlit Cloud)

### The modeling core (FROZEN pipeline — do not edit without an explicit ask)
1. **Calibrated Monte Carlo** (`compute_outcomes.py`): Waves 1/2/2b/2c. Depth-dependent
   `SIGMA_ANCHORS`, honest availability (~.82-.85), games↔per-game injury coupling, exact mean
   re-centering, draft-capital refit, team-changer split by PROVEN production, stable-vet narrowing,
   WR30+ fade, CV blend, stayed+new-HC tilt. **Backtested 60-62% band coverage incl. true OOS 2014-18
   (62.1%)** — not overfit. Re-tune acceptance tests: `icm/work/mc_research/05_distribution.py` +
   `06_finish_odds.py`.
2. **Cohort priors** (`cohort_priors.py` → `cohort_data.csv`): each board player's 15 nearest
   historical seasons (kNN 2014-25) with empirical-Bayes-shrunken rates (m=25, LOSO-fitted). Emits
   **`cohort_trimmed` + `cohort_mean`** (L29 — outcomes are right-skewed; advisor shows median + trimmed
   mean, tags TAIL-DRIVEN when they straddle 1.0x; raw mean stored but NEVER read).
3. **Coaching intelligence** (`sos_priors.py`, `data/`): news-verified 2026 — 10 new HCs
   (`new_hc_2026.csv`, drives the MC tilt), 18 playcallers (`playcallers_2026.csv` +
   `playcallers_hist.csv`). Mispricing lives with FULL regime change (new HC); OC-only is price-neutral
   → MC tilts on HC only, playcaller = advisor usage context.
4. **Positional SOS** (`sos_data.csv`): 2026 opponents × 2025 per-position points allowed; tie-break
   context in the advisor table.

### The advisor (`advisor.py` — app layer, freely editable; `draft-strategy.md` is source of truth)
5. **Value engine:** VONA (Value Over Next Available), roster/lineup gates, role-lead bump, ROSTER RISK
   accumulation (L23), strategy-is-the-plan (L25). **Stale-role fixes L16/L34/L37/L39 live here** (see
   theme A above).
   - **Cohort sanity-pull (L32, `cohort_pull.py`, called in `draft.py` `load_board`):** `cohort_trimmed`
     nudges `rank_composite` at board-load — bounded (deadband / cap ±4 / startable-gate / freeze top-8),
     `trimmed` not median, missing CSV = no-op. Flows to the Everything board, the risk dial, AND the
     advisor's TOP PICKS shortlist. App-layer only; frozen pipeline untouched.
6. **The read stack** (all Python-computed, enforced in TOP PICKS data per L8 — the model can't ignore them):
   - **PUNT READ** (L11/L28): unfilled QB/TE — risk-symmetric, depth-aware, NO positional margin.
     Correctly recommends elite QB when metrics say so ("Josh Allen at 29 is CORRECT" — do NOT re-open
     it as a bug; see L28).
   - **DEFER READ** (L33): a punt-able QB/TE you can wait on — survival-primary (`surv ≥ 0.6` and a
     real RB/WR alternative exists). Pairs with the TE/QB-shape notes.
   - **HEDGE READ** (L27): a FILLED risky 1-start starter → surface the hedge-vs-stream call once
     dedicated starters are set. Insurance, not a value pick.
   - **HANDCUFF READ** (L30/L31): GO-screened backups behind MY starting RBs only (never bench, never
     WR/TE). GO screen = prior role + offense + real price.
   - **DART READ** (L31): from R11+, TOP PICKS switches to deterministic BUY/neutral/FADE tiers from
     `_dart_profiles` (movers now excluded, L37). Playbook: `reference/late-round-strategy.md`. Backed by
     `role_priors.py` → `role_data.csv`.
   - **STREAMER ALERT** (L26): forces K/D-ST when remaining picks barely cover them. **K and D/ST
     rankings come from the board** (L36 D/ST filtered by `drafted_dsts`; L38b K exempt from the
     proj_outlier drop) — the advisor never names one from memory.
   - **Shape advisories** (guidance, not re-ranks): TE-shape, QB-shape, WR-shape, ambiguous-room pairs
     (L35). See theme C above.
   - Prompt-cached SYSTEM (~90% cache reads).
7. **Speculative PRE-READ** (`app_pages/draft.py`): background deep call within 3 picks of the clock,
   exact board-fingerprint guard. It never BLOCKS the pick (Jul-20 fix) — the Recommend button serves a
   ready pre-read or falls straight to the fast ~4-5s live call.
8. **Live sync**: ESPN + Sleeper (~81% coverage), FA bridge (userscript→Firebase→app; synced 192 picks
   cleanly this session). **Preflight** `tools/preflight.py` (validates every runtime CSV, NaN guards,
   ADP freshness, priors/role staleness, cross-file consistency) + `tools/name_audit.py` (network).

---

## Git / branch state (Jul 25)
- **`main` = `origin/main` — DEPLOYED.** Holds the entire advisor arc through L40 (incl. opponent-aware
  survival, hand-reapplied — the old `opponent-aware-survival` branch had forked 20 commits back, so it
  was reapplied onto current `advisor.py`, not rebased; design: `icm/work/plan.md` + `diagnosis.md`).
- **One branch still genuinely UNMERGED:**
  - `yahoo-probe` (`b8cb697`): Yahoo probe tooling `tools/yahoo_probe/` — awaits the user's Yahoo
    dev-app + a mock. Doesn't touch `advisor.py`, rebases trivially. See `icm/work/yahoo-probe-scope.md`.
- **Stale local branches — work already in main, safe to delete:** `advisor-hedge-read`,
  `cohort-mean-trimmed`, `fix-prelook-blocking`, `preflight-health-check`, `punt-read-metric-correct`,
  and now `opponent-aware-survival` (its logic shipped via the L40 reapply).

---

## Regeneration ritual (data drifts; regenerate close to draft day)
1. **Board** (FROZEN, deterministic): `.venv/bin/python run_all.py` (refreshes live ESPN ADP).
2. **Non-frozen priors** — rerun all three after a board rebuild:
   `cohort_priors.py`, `sos_priors.py`, `role_priors.py` (role_priors needs the local research panel
   `icm/work/mc_research/seasons_exp.parquet`, rebuildable via `01`+`02`). Commit the regenerated CSVs.
3. **Verify**: `tools/preflight.py` (must say PREFLIGHT OK), then
   `icm/work/mc_research/11_stress_test.py` + `12_full_system_stress.py` (both ALL PASS), then the unit
   suites (below). Then `tools/name_audit.py` (network) + eyeball the app.

> **After any `value_board.py` edit** (like L39): re-run `value_board.py` → then the three priors → then
> preflight + suites. The board CSV and priors are read by the deployed app from the repo, so they MUST
> be regenerated and committed together.

## Tests (all plain-assert, run individually: `.venv/bin/python tests/<file>.py`)
`tests/` — 13 suites, **183 checks, all green**:
`test_bridge` (26), `test_sleeper` (13), `test_hedge` (8), `test_punt` (8, L28),
`test_cohort_skew` (10, L29), `test_dart` (23, L31/L37), `test_handcuff` (16, L30/31),
`test_cohort_pull` (19, L32), `test_defer` (8, L33), `test_role_alpha` (7, L34),
`test_dst` (14, L36), `test_kicker` (6, L38b), `test_opponent` (25, L40). Plus the two stress
suites in `icm/work/mc_research/`.

## Verified vs pending
- **Deployed + fully verified** (this session): 183 unit checks green, preflight clean, board+priors
  regenerated, a full 192-pick live-mock bridge sync. L40 opp-survival: both stress suites ALL PASS
  (opp=None identity), opp-active proven on the real board, AppTest renders clean.
- **Pending live verify:** the **opp-active path** of L40 in a live-sync mock (safe to run live — it
  only fires with live rosters, opp=None can't regress); a real **Sleeper** mock end-to-end; the
  **Yahoo** probe go/no-go.
- **Pre-draft-day checklist:** run the regeneration ritual on fresh data; do one live ESPN mock at
  **slot 7** (doubles as the opp-survival rehearsal — watch the WHEEL WINDOW line).

---

## ROADMAP — next features (user-approved ordering)
1. ✅ **Opponent-aware survival** — SHIPPED (L40). Only a live-sync mock remains to exercise the
   opp-active path end-to-end (the code is proven; the mock is the rehearsal, not a gate to shipping).
2. **Positional-run detection** — "5 of last 8 picks were RBs → the cliff is NOW."
3. **Projection-consensus layer** (NEW, from this session's research) — blend FP + ESPN forward
   projections + ground `role_lead` in ff_opportunity, to damp single-source misses. Scoped feature; the
   public-product path needs a licensed forward-projection API. (General merit; not urgent — the one case
   that prompted it, Price>Charbonnet, turned out to be FP being correct.)
4. **Live news/injury layer** — the real July-31 difference-maker; needs a source decision. (~half the
   handcuff edge and sharpest signals are in-season → a live layer + FAAB plan is the next real edge.)
5. **Mock draft simulator** — rehearse slot 7 vs ADP-bots (`13_strategy_bakeoff.py` + `12_full_system_
   stress.py` are ~80% of it).
6. Rest-of-draft lookahead · 7. August usage refresh · 8. ESPN-vs-consensus divergence ·
   9. Live draft grade · 10. "My guys" watchlist UI · 11. Home hub / Research landing page (deferred
   until after the Jul 31 draft; see `memory/home-hub-idea.md`).

## Where the knowledge lives
- **Lessons L1–L39:** `icm/reference/lessons.md` (**check before diagnosing** — esp. L28: the Josh Allen
  pick is CORRECT, not a bug). Non-negotiables: `engineering-principles.md`, `collaboration.md`.
- **Draft strategy source of truth:** `icm/reference/draft-strategy.md`. Architecture map:
  `icm/reference/architecture.md`. Bridge: `icm/reference/bridge.md`. Pipeline boundary:
  `icm/reference/pipeline.md`.
- **Late-round playbook** (validated buys/fades/handcuffs + what FAILED validation):
  `icm/reference/late-round-strategy.md`.
- **MC research narrative:** `icm/work/mc-research-findings.md`; scripts + committed results (incl. the
  strategy bake-off `13`/`14`/`15`) in `icm/work/mc_research/`.
- **Resolved data flag (do NOT re-open):** `memory/sea-backfield-projection-flag.md` — the board is
  correct that Price is SEA RB1 (Walker→KC + Charbonnet ACL).
