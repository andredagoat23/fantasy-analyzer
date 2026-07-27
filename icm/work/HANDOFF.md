# SESSION HANDOFF — read this first if you're a fresh session

**How to use this file:** read `icm/CONTEXT.md` (the router) first, then this, then whatever reference
docs the task needs. Everything below is CURRENT as of **Jul 26, 2026**.

## Where things stand right now
- **DEPLOYED & CLEAN.** Local `main` = `origin/main` = **`6eff5f9`**, tree clean. Streamlit Cloud
  auto-deploys on push to `main`, so `main` == what's live.
- **Health:** preflight **OK** (0 blocking, 0 warnings). **All 14 unit suites green — 195 checks.** Board
  + all priors regenerated. **No open CODE items, no open DATA flags.**
- **Draft day: August 7, 2026** — ESPN, 12-team, **slot 7**, custom PPR, 16 rounds. (Practice mocks ran at
  slots 1/5/10; the real draft is **slot 7** — never hardcode a slot.)
- **⚠️ One open THREAD (not a repro'd bug):** in the last mock the advisor recommended a 4th RB at R7 with
  WR2 open. It does NOT reproduce offline — rebuilding that roster yields an all-WR shortlist (the gate is
  sound), so the live roster STATE differed. Added **per-pick context logging** (L47) to catch it next
  time: after a weird pick, **Draft settings → "Download pick log"** → hand it over. Don't patch the gate
  blind.

## The build's current capabilities (the arc through L47)
Scoring, projections, and the board are all substantially stronger than a few sessions ago:
- **Custom scoring COMPLETE + verified vs the real ESPN settings (L41).** User pasted the actual league
  scoring; diff found all values right but 5 rules missing — added QB **sacks** (~−30 to −55/QB, the big
  one), 2pt, PAT-missed, return yds/TDs, and fixed a tiered-vs-stacked big-game bug. All in
  `apply_bonuses.py`. See `memory/league-scoring.md`.
- **Scoring is a SINGLE SOURCE OF TRUTH — `scoring_config.py` (L42).** Edit values THERE only;
  `custom_scoring` / `apply_bonuses` / `compute_outcomes` all import it (the MC weekly proxy used to
  hardcode + silently desync). Robustness-audited across 6 settings (`mc_research/16`).
- **Team D/ST now SCORED (L43) — last scoring gap closed.** `load_dst.py` scores every defense under the
  real ESPN tiers from nflverse (2024-25, shrunk + 2026-SOS-tilt) → `data/dst_rankings.csv`. STREAMER
  layer only — stays OFF the cross-position board (L9); grounds the advisor's D/ST rec. Validated 12/15 vs
  FP consensus.
- **Projections are a FP+ESPN CONSENSUS (L44).** ESPN's own projections ride the same endpoint as ADP
  (free), blended with FP at the component level (`projections.py`, weights in scoring_config = **0.35 FP
  / 0.65 ESPN**). `proj_divergence` on the board. FP-only mode is byte-identical (proven). New pipeline
  step `load_espn_projections.py`.
- **Composite weights RE-TUNED from a 13-season LOSO backtest (L45).** The board under-weighted the
  outcome distribution → shifted market .36→.19 into ceiling .13→.25 + floor .09→.15 (+0.033
  generalizable). VOLS kept full at .32 (the backtest's "value" proxy is backward — can't judge the real
  forward VOLS). **Per-position weights were tested and DON'T help** (within-position ADP dominates,
  `mc_research/19`) — the position edge is SHAPE, not weights.
- **Position-shape advisory is HYBRID (L46).** Durable historical prose (corrected: QB is opportunity-cost
  not "no edge"; WR usually safe but check the board; TE dead-zone→pocket) + a COMPUTED `POSITION SHAPE`
  line (`advisor.position_shape`) that reads THIS class's cliffs/next-tier-bust/value-pockets from the
  live board — self-updating each regen. `tests/test_shape.py`.
- **Opponent-aware survival SHIPPED + REHEARSED (L40).** Survival/VONA/wheel fold in the live rosters of
  the teams before my wheel. `opp=None` byte-identical. Kill-switch = "Opponent-aware survival" toggle in
  Draft settings. **Its live-sync rehearsal is DONE** — the last mock synced all 192 picks cleanly.
- **✅ SEA/Charbonnet flag RESOLVED — board is RIGHT** (Price = SEA RB1; Walker→KC + Charbonnet ACL). Do
  NOT re-open. `memory/sea-backfield-projection-flag.md`.

*(The earlier L32–L39 arc — the "stale-role" fixes (L16/L34/L37/L39), off-the-board K/D-ST leaks
(L36/L38b), the DEFER read (L33), ambiguous-room pairs (L35), cohort sanity-pull (L32) — is all shipped
and detailed in `lessons.md`.)*

---

## The stack as it stands (all LIVE on Streamlit Cloud)

### The modeling core (FROZEN pipeline — do not edit without an explicit ask; scoring VALUES live in `scoring_config.py`)
1. **Calibrated Monte Carlo** (`compute_outcomes.py`): Waves 1/2/2b/2c — depth-dependent `SIGMA_ANCHORS`,
   honest availability (~.82-.85), games↔per-game injury coupling, exact mean re-centering, draft-capital
   refit, team-changer split by PROVEN production, WR30+ fade, CV blend, stayed+new-HC tilt. **Backtested
   60-62% band coverage incl. true OOS 2014-18 (62.1%)** — not overfit. Acceptance tests: `mc_research/05`
   + `06`.
2. **Cohort priors** (`cohort_priors.py` → `cohort_data.csv`): each player's 15 nearest historical seasons
   (kNN 2014-25, EB-shrunk m=25). Emits `cohort_trimmed` + `cohort_mean` (L29 — right-skewed; advisor
   shows median + trimmed mean, tags TAIL-DRIVEN; raw mean NEVER read).
3. **Coaching intel** (`sos_priors.py`): 10 new HCs (drive the MC tilt) + 18 playcallers (advisor context).
4. **Positional SOS** (`sos_data.csv`): 2026 opponents × 2025 per-position points allowed.
5. **Projection layer** (`projections.py`, L44): FP+ESPN component-level consensus feeding custom_scoring +
   apply_bonuses. **D/ST** (`load_dst.py`, L43) is scored separately (streamer, off the board).

### The advisor (`advisor.py` — app layer, freely editable; `draft-strategy.md` is source of truth)
6. **Value engine:** VONA, roster/lineup gates (`_lineup_gaps` → dedicated_open/flex_only/bench_sat with a
   `_sink_rank` hard-demote), ROSTER RISK (L23), strategy-is-the-plan (L25). Stale-role fixes L16/L34/L37/
   L39. **Cohort sanity-pull** (L32, `cohort_pull.py` in `draft.py load_board`) nudges rank_composite.
7. **The read stack** (Python-computed, enforced in TOP PICKS per L8 — the model can't ignore them):
   PUNT (L11/L28 — "Josh Allen at 29 is CORRECT, not a bug"), DEFER (L33), HEDGE (L27), HANDCUFF (L30/31),
   DART (L31/L37, R11+), STREAMER (L26). **K/D-ST rankings come from the board AND are now hidden once the
   slot is filled** (L47 — was suggesting a 2nd kicker). **POSITION SHAPE** line (L46). Prompt-cached SYSTEM.
8. **Speculative PRE-READ** (`draft.py`): background deep call within 3 picks; never BLOCKS the pick.
9. **Live sync + logging:** ESPN + Sleeper + FA bridge (userscript→Firebase→app; synced 192 picks cleanly).
   **Per-pick context log** (L47, `session_state.pick_log` + Draft-settings download). Tools: `preflight.py`,
   `name_audit.py`, `fa_watch.py` (Sleeper FA-signing watch, roadmap #4's first piece).

---

## Git / branch state (Jul 26)
- **`main` = `origin/main` = `6eff5f9` — DEPLOYED.** Holds the entire arc through L47.
- **One branch UNMERGED:** `yahoo-probe` (`b8cb697`) — Yahoo probe tooling; awaits the user's Yahoo dev-app
  + a mock. Doesn't touch `advisor.py`. (All other old branches were deleted; their work is in main.)

---

## Regeneration ritual (data drifts; regenerate close to draft day)
1. **Board** (FROZEN chain, incl. `load_espn_projections.py`): `.venv/bin/python run_all.py` (refreshes
   live ESPN ADP + ESPN projections).
2. **Priors** — rerun all three after a board rebuild: `cohort_priors.py`, `sos_priors.py`, `role_priors.py`
   (needs the local `mc_research/seasons_exp.parquet`). Commit the regenerated CSVs.
3. **D/ST** (L43): `.venv/bin/python load_dst.py` → `data/dst_rankings.csv` (nflverse-slow, standalone).
4. **Verify**: `tools/preflight.py` (must say OK) → `mc_research/11` + `12` stress (ALL PASS) → the 14 unit
   suites → `tools/name_audit.py` + `tools/fa_watch.py` (network) → eyeball the app.

> **After any `value_board.py` edit** (weights, role logic): re-run `value_board.py` → priors → preflight
> + suites. Board CSV + priors are read by the deployed app from the repo — regenerate + commit together.
> (A `value_board.py`-only weight change doesn't affect the priors' inputs, but rerun them for a clean
> mtime so preflight's staleness guard stays happy.)

## Tests (plain-assert, run individually: `.venv/bin/python tests/<file>.py`)
`tests/` — **14 suites, 195 checks, all green**: `test_bridge` (26), `test_sleeper` (13), `test_hedge`
(8), `test_punt` (8), `test_cohort_skew` (10), `test_dart` (23), `test_handcuff` (16), `test_cohort_pull`
(19), `test_defer` (8), `test_role_alpha` (7), `test_dst` (14), `test_kicker` (7, incl. the L47 filled-K
gate), `test_opponent` (25, L40), `test_shape` (11, L46). Plus the two stress suites in `mc_research/`.

## Verified vs pending
- **Verified + deployed:** 195 unit checks, preflight clean, both stress suites ALL PASS, a full 192-pick
  live-mock (the opp-survival rehearsal — opp-active ran live and held).
- **Pending:** the R7 roster-state mystery (diagnose from the next mock's **pick log**); a real **Sleeper**
  mock; the **Yahoo** probe go/no-go.
- **Pre-draft checklist:** run the regen ritual on fresh data; run `tools/fa_watch.py` for late FA signings
  (watch **Stefon Diggs** — unsigned, ADP ~164, a real value IF he signs to a role); one live ESPN mock at
  **slot 7** (download the pick log if anything looks off).

---

## ROADMAP — next features
1. ✅ **Opponent-aware survival** — SHIPPED + rehearsed (L40).
2. ✅ **Projection consensus** — SHIPPED (L44, FP+ESPN).
3. **Positional-run detection** — "5 of the last 8 picks were RBs → the cliff is NOW." The clearest next
   build (self-contained advisor logic).
4. **Live news/injury layer** — first piece SHIPPED (`fa_watch.py`, Sleeper). Next: an in-app signing/
   injury banner + in-season `nflverse load_injuries` + a FAAB plan (~half the edge is in-season).
5. **"Upgrade a weak starter" read** (from the mock) — when the lineup is full but a dedicated starter is
   weak (low p_startable / high bust), surface upgrading it over redundant bench depth. NOT yet built.
6. **Mock draft simulator** (`13`+`12` are ~80% of it) · 7. Rest-of-draft lookahead · 8. Live draft grade
   · 9. Home hub / Research landing page (deferred until after Aug 7; `memory/home-hub-idea.md`).

## Where the knowledge lives
- **Lessons L1–L47:** `icm/reference/lessons.md` (**check before diagnosing** — esp. L28: the Josh Allen
  pick is CORRECT, not a bug). Non-negotiables: `engineering-principles.md`, `collaboration.md`.
- **Sources of truth:** `draft-strategy.md` (advisor), `pipeline.md` (frozen chain + scoring), `bridge.md`
  (live sync), `architecture.md` (system map).
- **Late-round playbook:** `late-round-strategy.md`. **MC + backtest research:** `mc-research-findings.md`
  + `mc_research/` (scoring robustness `16`, weight backtests `17`/`18`/`19`, shape validation `20`).
- **Resolved data flag (do NOT re-open):** `memory/sea-backfield-projection-flag.md`.
