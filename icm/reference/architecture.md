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
- `advisor.py` — the Claude advisor. `build_context()` turns the live board into the prompt context
  (incl. the Python-computed `wheel` column and roster-needs line); `stream_advice()` streams the
  pick/chat; `parse_scoring()` / `suggest_strategy()` are one-shot setup helpers.
- `bridge.py` — reads the live-draft Firebase mailbox and resolves picks to board players. See
  `bridge.md`.
- `auth.py`, `config_store.py`, `utils.py` (`normalize_name`), `espn_sync.py` (ESPN-API fallback).
- `sleeper_sync.py` — Sleeper live sync via Sleeper's PUBLIC API (no userscript/Firebase); normalizes to
  the bridge's `{meta,picks}` shape so `bridge.resolve` is reused. See `bridge.md`.

## The board — `value_board.csv`
THE file the app reads. Columns include: overall_rank, full_name, pos_label ("RB1"), total_points,
vols, adp_rank (live ESPN ADP, a float), ecr_rank/ecr_tier, value_gap, market (VALUE/REACH/fair),
risk_tier, floor, ceiling, p_startable, p_bust, xppg, regression, team_implied_total, etc.
Loaded once via `@st.cache_data` keyed on file mtime. `value_board.py` now produces `team_role`
(depth-chart slot, BUF WR1) + `role_lead` (projection gap to the next player in his position room, for
the advisor's role bump — L14/L16), DROPS no-team FAs, suppresses a below-replacement VALUE tag
(L16), and blends a projection OUTLIER's composite toward ECR when our proj ranks him ≫ expert
consensus (`CONSENSUS_GAP`/`CONSENSUS_ECR`, L17 — e.g. Metchie). `load_board` (draft.py) derives
`team_role`/`no_team` only as a fallback for an older board CSV.

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
`tests/test_bridge.py` — plain-assert regression suite (no pytest dep):
`.venv/bin/python tests/test_bridge.py`.

## Deploy (USER TRIGGERS)
Streamlit Community Cloud, auto-deploys on push to `main` (repo: andredagoat23/fantasy-analyzer).
Commits land locally on `main`; **pushing = deploying**, which is always the user's call. Live sync on
the deployed app needs the `[bridge] url` (and `[espn]`) blocks in Streamlit Cloud secrets.
