# Product SPEC (Layer 3 — v1.0 domain identity + scope of record)

This is the product **SPEC** — the what/who/why of the app and the locked v1.0 scope. It used to live
in `CLAUDE.md`; it moved here so the entry file stays a small router (ICM: routing files don't carry
payload). `CLAUDE.md` now points here. The **data pipeline** and the **board's columns** are NOT
re-listed here on purpose — their one home is `architecture.md` (system map) and `pipeline.md` (deep
internals). The **collaboration rules** live in `collaboration.md`.

## What we're building
A single-page Streamlit web app that runs my personal draft board during a live snake draft on ESPN. My draft is July 31, 2026. This is v1.0 (math-based recommender). v1.1 will add a Claude API advisor on top.

## Who uses it
Just me. Single-user tool. No auth, no accounts, no multi-league support.

## When it gets used
During a live ESPN snake draft on July 31. Snake draft in a 12-team custom-scoring PPR league. I have ~90 seconds between my picks. The app has to be fast to filter, fast to check off drafted players, and readable in a glance.

## The data
The board the app reads is `value_board.csv` (already built — don't rebuild it for the app). Its
current columns are documented in `architecture.md`; the FROZEN script chain that produces it is in
`architecture.md` (map) and `pipeline.md` (deep internals). `utils.normalize_name` matches names
across sources.

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

## Note on scope drift since v1.0
v1.1 (the Claude advisor) and the live-draft bridge now exist — see `architecture.md`, `draft-strategy.md`,
and `bridge.md`. The "HARD NOT in v1.0" list above is the record of what v1.0 deliberately excluded;
several items have since shipped in later versions. Treat this SPEC as the v1.0 baseline, not the
current feature set.
