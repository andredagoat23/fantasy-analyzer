# PROJECT CONTEXT — Fantasy Football Draft Assistant

## ⭐ START HERE — ICM workspace (Layer 0)
This project uses **ICM (Interpretable Context Methodology)**: `icm/` is a filesystem-as-methodology
workspace that governs *how work gets done here* so every change is reproduced, designed, verified,
and shipped — not ad-hoc (ad-hoc caused this project's worst bugs). **Before acting on any request,
read `icm/CONTEXT.md`** (the router) and route through the stages. Prime directive: do whatever the
user asks **efficiently and to a T** — reproduce before fixing, verify with REAL data before claiming
done, never fabricate. Durable knowledge lives in `icm/reference/` (engineering principles, lessons
from every past mistake, the draft-strategy source of truth, architecture, and the bridge). The rest
of this file is the product SPEC (Layer 0 domain identity).

## What we're building
A single-page Streamlit web app that runs my personal draft board during a live snake draft on ESPN. My draft is July 31, 2026. This is v1.0 (math-based recommender). v1.1 will add a Claude API advisor on top.

## Who uses it
Just me. Single-user tool. No auth, no accounts, no multi-league support.

## When it gets used
During a live ESPN snake draft on July 31. Snake draft in a 12-team custom-scoring PPR league. I have ~90 seconds between my picks. The app has to be fast to filter, fast to check off drafted players, and readable in a glance.

## The data — what already exists
The pipeline is already built. I have these files/CSVs on disk in ~/fantasy-analyzer/:

Pipeline (already runs):
- players.py → players.csv (raw Sleeper roster)
- filter_active.py → players_active.csv (active NFL players only)
- load_player_stats.py → players_with_stats.csv (adds nflreadpy 2024+2025 stats)
- load_fp_adp.py → players_with_adp.csv (adds FP ESPN ADP)
- load_ecr.py → players_with_ecr.csv (adds FP ECR)
- load_fp_projections.py → players_with_projections.csv (adds FP raw stat columns)
- custom_scoring.py → players_scored.csv (applies my league's scoring)
- apply_bonuses.py → players_final.csv (Bucket 2 bonuses)
- compute_metrics.py → players_with_metrics.csv (VOLS)
- compute_outcomes.py → players_with_outcomes.csv (Monte Carlo floor/ceiling/boom-bust)
- value_board.py → value_board.csv (final draft board — THIS is what the app reads)

value_board.csv columns:
overall_rank, full_name, pos_label (e.g. "RB1", "WR5"), total_points, vols, adp_rank, ecr_rank, value_gap, market ("VALUE"/"REACH"/"fair"), risk_tier ("Safe"/"Balanced"/"Boom/Bust"), floor, ceiling, bust_rate, P_pos1 (probability of finishing #1 at position)

## Existing utilities I already wrote
- utils.normalize_name(name) — lowercases, strips punctuation + Jr/Sr/II/III suffixes. Use this if you ever need to match names across data sources.

## App layout — the target end state

Two-zone layout:

LEFT SIDEBAR (~25% width, always visible):
1. "Position Scarcity" panel — count of top-N players remaining at each position (QB/RB/WR/TE/K/D-ST), with visual indicator when a tier is running thin.
2. "My Roster" panel — grouped by roster slot (1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 D/ST, 1 K, 7 bench, 1 IR). Shows total projected points so far.
3. "Reset draft" button at bottom, requires confirmation.

MAIN AREA (~75% width):
Top of main:
- Big title with football emoji
- Filter controls in a row: position multi-select, top-N slider (default 100, max 200), search box for name, checkboxes for "Steals only" and "Reaches only"

Below filters:
- The main draft board — sortable table showing filtered/searched players.
- Columns in order: Drafted checkbox, Rank, Player name, Pos, VOLS, ADP, ECR, Gap, Market, Risk, Floor, Ceiling, P(#1)
- Value gap column color-coded: green for positive (VALUE), red for negative (REACH)
- Market column shown with icon: 🔥 VALUE, ⚠️ REACH, blank for "fair"
- Risk tier as colored badge
- P(#1) as horizontal progress bar 0-100%
- Height 700px so table scrolls, not the page

## How I use it during a draft
1. Draft starts. I look at the top of the board for my first pick.
2. Every pick that happens (mine or not), I check the "Drafted" box next to that player. They disappear from the main board, appear in "My Roster" if it was my pick, and Position Scarcity updates.
3. Between my picks, I check the sidebar to see position scarcity, glance at my roster shape, then look at the top of the board again for my next pick.
4. I use the market column (VALUE / REACH) to spot when someone's ranked much better by my board than by ADP.
5. I use risk tier to decide if I want a Safe pick vs. a Boom/Bust upside pick given roster context.

## Constraints — what's IN v1.0

Locked from SPEC.md. Only these features. Anything else is scope creep.
- Data source: value_board.csv (already built, don't rebuild)
- Layout: two-zone as above
- Filters: position multi-select, top-N slider, search, steals/reaches toggles
- Interactive: drafted checkbox, undo (via unchecking), reset button
- Sidebars: position scarcity + my roster + reset
- Styling: dark mode by default via .streamlit/config.toml, custom CSS for value_gap color scale + market icons

## Constraints — HARD NOT in v1.0
Do not build:
- LLM/Claude API integration (v1.1, after v1.0 deploys)
- Live ESPN draft state sync (v1.5)
- Multi-league config (v1.5)
- Charts / visualizations beyond the P(#1) progress bar
- Multi-page navigation
- User accounts, login, auth
- Waiver wire, trade analyzer, in-season features
- ML projection model
- VONA simulation

## Deployment
- Streamlit Community Cloud (free tier)
- Connected to my GitHub repo: andredagoat23/fantasy-analyzer
- Auto-deploys on git push
- Entry point: app.py

## Tech decisions locked
- Streamlit (single file: app.py)
- pandas for data handling
- @st.cache_data for the CSV read (critical — Streamlit reruns the entire script on every widget change)
- st.session_state for the drafted set (survives reruns)
- st.data_editor for the checkbox column
- Custom theme via .streamlit/config.toml
- Custom CSS injected via st.markdown(..., unsafe_allow_html=True) for the value_gap color scale

## Aesthetics
"Beautiful" for v1.0 means:
- Dark mode default
- Terracotta accent color for VALUE labels
- Blue accent for REACH labels
- Generous whitespace, rounded containers
- Emoji as visual anchors (🏈 header, 🔥 value, ⚠️ reach)
- Column widths tuned for scan-ability
- Not: custom React components, complex animations, multi-page navigation

## Build phases — 5 sessions, ~60-90 min each

Phase 1: Skeleton — read CSV, display all 12 configured columns with formatting. (DONE — app.py exists)
Phase 2: Filters — position multi-select, top-N slider, search input, steals/reaches toggles. All in main area, above the table. (DONE)
Phase 3: Drafted state — st.session_state.drafted (a set of player IDs). Drafted column with checkbox. Checking removes from main view. Unchecking restores. (DONE — keyed on full_name since value_board.csv has no player_id; undo via a "↩︎ Drafted" drawer; monotonic version counter for fresh data_editor keys)
Phase 4: Sidebars — position scarcity + my roster. Both auto-update from session_state. (DONE — scarcity = positive-VOLS remaining per position with ⚠️ when ≤5; "Mine" checkbox column added alongside "Drafted"; greedy roster slot-fill + projected-points metric; reset button with two-step confirm via callbacks)
Phase 5: Polish + deploy — theme, custom CSS, deploy to Streamlit Community Cloud. (POLISH DONE — dark theme + Inter font via .streamlit/config.toml (terracotta primary, blue REACH); pandas Styler for value_gap green/red + risk badges + market tints (NOT injected CSS — canvas table can't take it; Styler applies to non-editable cols); Material Symbols for chrome, 🏈/🔥/⚠️ kept as brand accents; requirements.txt = streamlit+pandas only. DEPLOY DONE — pushed to main (commit c45aa1c) 2026-07-10, Streamlit Cloud auto-deploys. v1.0 COMPLETE.)

## Rules for our collaboration
1. Always walk me through the code line-by-line BEFORE writing it. Then PAUSE and let me say "go" before you write code.
2. Explain WHY you chose a particular Streamlit widget or pattern, not just what it does.
3. Assume I have AP CSP background — I know Python fundamentals. Explain Streamlit-specific concepts (session_state, cache_data, data_editor, reruns) but skip basic Python.
4. If I ask for a feature that's in the "Hard NOT in v1.0" list, remind me of the spec and defer to v1.5.
5. If you catch a data quality issue (like the FP FPTS = standard scoring bug I caught before), FLAG IT before continuing — never silently work around bad data.
6. Never touch the data pipeline files (custom_scoring.py, compute_metrics.py, etc.) unless I explicitly ask. Those are frozen for v1.0.
