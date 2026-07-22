# Architecture (Layer 3 — system map)

## What this is
A single-page Streamlit app that runs a personal draft board during a live ESPN snake draft
(July 31, 2026). v1.0 = math-based recommender; the AI advisor (v1.1) sits on top. Single user.

## App files (edit these)
- `app.py` — entry point: page config, shared CSS, login gate (`auth`), session-state defaults,
  `st.navigation` between Setup and Draft board, and the `*_pending` mechanism that lets the advisor
  / setup set `slot`/`teams`/`risk` before the widgets render.
- `app_pages/setup.py` — pre-draft league setup (name, site, scoring, strategy, slot, teams).
- `app_pages/draft.py` — the draft board: sidebar (scarcity, roster, reset), main strip (exit,
  draft settings, roster popover, compact toggle), scarcity readout, **live sync**, on-the-clock +
  cliff watch, **AI advisor**, filters, the `st.data_editor` board, undo drawer.
- `advisor.py` — the Claude advisor. `build_context()` turns the live board into the prompt context:
  the Python-computed `wheel` column, roster-needs, and a stack of **precomputed READ lines all
  enforced in the TOP PICKS ranking (L8 — the model can't ignore them):** VONA (`add_vona`); PUNT READ
  (`_punt_read`, L28 — risk-symmetric, depth-aware, no positional margin); HEDGE READ (`_hedge_read`,
  L27 — risky filled 1-start); HANDCUFF READ (`_handcuff_read` + `_go_score`, L30/31 — GO-screened RB
  backups behind my starters); DART READ (`_dart_profiles`/`_dart_read`, L31 — R11+ BUY/FADE tiers);
  ROSTER RISK (L23); STREAMER ALERT (L26). Cohort block prints median + trimmed-mean (L29).
  `stream_advice()` streams the pick/chat; `prelook()` is the deep BACKGROUND pre-read; `parse_scoring()`
  / `suggest_strategy()` are one-shot setup helpers. SYSTEM is prompt-cached (`_system_blocks`, ~90%
  cache reads). Data readers (`_cohorts`/`_playcallers`/`_sos`/`_roles`) are try/excepted (a missing
  CSV = feature off, never a crash); `_roles` is mtime-keyed so a regen doesn't serve stale roles.
  **Speculative precompute (draft.py):** within 3 picks of my turn `prelook()` fires on a background
  thread (`prelook_pool`); the Recommend button serves a ready pre-read on an exact board-fingerprint
  match, else the fast live call. **It NEVER blocks the pick** (the 20s-wait bug is fixed).
- `cohort_priors.py` — the "Hampton treatment" for every board player: kNN over the 2019-25
  research panel (position, experience, draft capital, production, price, age, mover status) →
  each player's 15 most-similar historical seasons, their boom/bust/median-vs-price rates, and
  REAL named comps → `cohort_data.csv` (committed; the advisor's COHORT HISTORY block reads it for
  the TOP PICKS shortlist). NOT in run_all — rerun manually after board rebuilds; needs the local
  research panel (`icm/work/mc_research/seasons_exp.parquet`, rebuildable via `01+02` there).
  Cohorts are PRIORS + explainable stories; the calibrated MC numbers always win on disagreement.
  **Median AND trimmed mean (L29):** outcomes are right-skewed, so `cohort_med` alone hides the boom
  tail (mean > median for 61% of players; 30% flip their "beats his price?" verdict). `cohort_trimmed`
  (drop the 2 best + 2 worst of 15) captures that tail without the raw mean's blow-ups — `mult` is
  finish/price, so a cheap backup QB who starts a few games explodes it (Tyrod Taylor med 0.69x →
  mean 2.01x → trimmed 1.12x). The advisor prints both and tags TAIL-DRIVEN when they straddle 1.0x
  (41 board players; e.g. JSN 0.91x median but 1.01x trimmed). `cohort_mean` is stored for reference
  but is NOT what the advisor reads.
- `sos_priors.py` — positional strength of schedule (`sos_data.csv`: 2026 opponents x 2025
  points allowed per position, rank 1=easiest) + the news-verified 2026 coaching files in `data/`:
  `new_hc_2026.csv` (10 teams — drives the MC stayed+new-HC tilt; schedules feed was stale for
  ARI/ATL/BUF, the VERIFIED_NEW_HC_2026 constant is authoritative), `playcallers_2026.csv`
  (18 changes, 6 first-timers) and `playcallers_hist.csv` (224 sourced team-seasons 2019-25 —
  validated that OC-only changes are price-neutral). NOT in run_all; rerun with cohort_priors.
- `role_priors.py` — the LATE-ROUND role layer (L31): each board skill player's PREVIOUS-season
  workload share (carries for RB/QB, targets for WR/TE — the one validated handcuff/dart predictor),
  full-season ppg/games, NFL draft capital, and the market's positional ADP rank → `role_data.csv`
  (committed; the advisor's DART READ / GO-screened HANDCUFF READ read it). BOARD-FIRST (every skill
  player gets a row, rookies included); share is primary-stint, ppg/games are full-season (the
  midseason-trade false-fade fix), suffix-stripped name matching (the Godwin fix). NOT in run_all;
  rerun with cohort_priors/sos_priors after a board rebuild. Full playbook: `late-round-strategy.md`.
- `bridge.py` — reads the live-draft Firebase mailbox and resolves picks to board players. See
  `bridge.md`.
- `auth.py`, `config_store.py`, `utils.py` (`normalize_name`), `espn_sync.py` (ESPN-API fallback).
- `sleeper_sync.py` — Sleeper live sync via Sleeper's PUBLIC API (no userscript/Firebase); normalizes to
  the bridge's `{meta,picks}` shape so `bridge.resolve` is reused. See `bridge.md`.

## The board — `value_board.csv`
THE file the app reads. Columns include: overall_rank, full_name, pos_label ("RB1"), total_points,
vols, adp_rank (live ESPN ADP, a float), ecr_rank/ecr_tier, value_gap, market (VALUE/REACH/fair),
risk_tier, floor, ceiling, p_startable, p_bust, xppg, regression, team_implied_total, etc.
Loaded once via `@st.cache_data` keyed on the value-board + cohort-data mtimes (a cohort regen busts
the cache). `value_board.py` now produces `team_role`
(depth-chart slot, BUF WR1) + `role_lead` (projection gap to the next player in his position room, for
the advisor's role bump — L14/L16), DROPS no-team FAs, suppresses a below-replacement VALUE tag
(L16), and blends a projection OUTLIER's composite toward ECR when our proj ranks him ≫ expert
consensus (`CONSENSUS_GAP`/`CONSENSUS_ECR`, L17 — e.g. Metchie). `load_board` (draft.py) derives
`team_role`/`no_team` only as a fallback for an older board CSV, and applies the **L32 cohort
sanity-pull** (`cohort_pull.apply_pull`): the LOSO-validated `cohort_trimmed` nudges `rank_composite`
— bounded (deadband / cap ±4 / startable-gate so it never lifts a bench handcuff / freeze the top-8),
`trimmed` not median (L29), missing CSV = no-op. Flows to the Everything board, the risk dial, and the
advisor's TOP PICKS shortlist. App-layer only; the frozen pipeline is untouched.

## The data pipeline (FROZEN — do not edit without an explicit ask)
This is the map-level summary; the **authoritative per-file internals live in `pipeline.md`**.
`run_all.py` runs the chain. Sleeper roster → active filter → nflreadpy stats → **live ESPN ADP**
(`load_espn_adp.py`, public endpoint) → ECR → FP projections → custom scoring → bonuses → metrics
(VOLS) → Monte-Carlo outcomes → `value_board.py` → `value_board.csv`. `value_board.py` DROPS players
with NaN projected points (why Tyreek Hill is absent — lesson L6). Re-running `run_all.py` the morning
of the draft refreshes ESPN ADP. `tools/name_audit.py` (read-only) checks ESPN's top-200 resolve to
the board — run it after any regen.

## Key Streamlit patterns in play
- `st.session_state`: `drafted` (set), `mine` (set — the roster; owner-match only, see bridge.md),
  `version` (monotonic counter for fresh `data_editor`/selectbox keys), `pick_count`, `slot`, `teams`.
- Reruns: the whole script reruns on every widget change; the bridge poller is an `st.fragment`
  (`run_every`) that updates state and `st.rerun(scope="app")`.
- `*_pending`: app.py applies `slot_pending`/`teams_pending`/`risk_pending` before the widgets render,
  so the advisor and ESPN meta can set them safely.

## Advisor model + key
`MODEL_ADVISOR = claude-sonnet-4-6` (pick + chat), `MODEL_FAST = claude-haiku-4-5` (setup helpers).
API key in `.streamlit/secrets.toml` (`ANTHROPIC_API_KEY`); also needs it in Streamlit Cloud secrets.

## Tests
Plain-assert suites (no pytest dep), run each with `.venv/bin/python tests/<file>.py`:
`test_bridge` (26), `test_sleeper` (13), `test_hedge` (8, L27), `test_punt` (8, L28),
`test_cohort_skew` (10, L29), `test_dart` (21, L31), `test_handcuff` (16, L30/31).
Plus the two stress suites: `icm/work/mc_research/11_stress_test.py` (component invariants + cohort
LOSO) and `12_full_system_stress.py` (24 offline drafts). And `tools/preflight.py` (runtime CSV
health) — run all after any board/priors regeneration.

## Deploy (USER TRIGGERS)
Streamlit Community Cloud, auto-deploys on push to `main` (repo: andredagoat23/fantasy-analyzer).
Commits land locally on `main`; **pushing = deploying**, which is always the user's call. Live sync on
the deployed app needs the `[bridge] url` (and `[espn]`) blocks in Streamlit Cloud secrets.
