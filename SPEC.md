# Fantasy Analyzer — v1 Spec (FROZEN)

**Frozen on:** 2026-06-15
**Ship target:** 2026-08-14
**Rule:** Anything not in this doc is NOT in v1. New ideas go to v1.5 backlog.

## League assumption (v1)
- Standard PPR
- 12 teams
- Standard roster: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 D/ST, 1 K, 6 bench
- (League config sidebar comes in v1.5 — v1 is hardcoded to MY league)
## Scoring rules (v1 — MY league, hardcoded)

### Passing
- Passing yards: 0.04
- Passing TD: 6
- Interception: -2
- 2-pt conversion: 2
- 40+ yd TD bonus: 0.5
- 50+ yd TD bonus: 1
- 300-399 yard bonus: 3
- 400+ yard bonus: 5
- Sacked: -1

### Rushing
- Rushing yards: 0.1
- Rushing TD: 6
- 2-pt conversion: 2
- 100-199 yard bonus: 3
- 200+ yd bonus: 5
- Rushing First Down: 0.5
- 40+ yd TD bonus: 2
- 50+ yd TD bonus: 3


### Receiving
- Receiving yards: 0.1
- Receiving TD: 6
- 2-pt conversion: 2
- 100-199 yard bonus: 2
- 200+ yd bonus: 4
- Rushing First Down: 0.5
- 40+ yd TD bonus: 1
- 50+ yd TD bonus: 2

### Kicking
- FG made (by distance): 0-39: 3, 40-49: 4, 50-59: 6, 6
- PAT: 1
- Missed PAT: -1

### D/ST
- Sack: 
- Interception: 
- Fumble recovery: 
- TD: 
- Safety: 
- Points allowed brackets: 

### Misc
- Fumble lost: 
- Any other quirky rule: 

### Source
- Pulled from: [your league site URL]
- Date confirmed: 2026-06-15
## Data sources
1. Sleeper API — player metadata (working as of 6/3)
2. nflreadpy — 2024 + 2025 stats, snap counts, route data
3. Fantasy Football Calculator ADP API — current ADP for 10-team PPR
4. FantasyPros ECR — manual CSV download, refreshed weekly

## Required columns in main player table
Each row = one player. Columns:
- player_name
- position (QB / RB / WR / TE / K / DEF)
- team
- bye_week
- proj_points (consensus blend of FFC ADP + manual ECR — formula in v1.5)
- vols (Value Over Last Starter — labeled correctly, NOT VORP)
- target_share (WR/TE only)
- snap_share_pct (all positions)
- route_participation_rate (WR/TE — from FTN data in nflreadpy)
- wopr (1.5 × target_share + 0.7 × air_yards_share — Hermsmeyer formula)
- tprr (targets per route run — computed from FTN)
- rz_targets (red zone targets)
- rz_touches (red zone touches, all skill positions)
- expected_tds (from RZ usage — regression candidate flag)
- metric_rank (percentile blend of above)
- adp_rank
- value_gap (metric_rank − adp_rank — negative = steal, positive = reach)
- drafted (boolean — toggled in UI)

## Required UI elements
- Searchable + sortable player table
- Position filter (QB / RB / WR / TE / FLEX)
- Top-N slider
- Steals toggle (positive value gap)
- Reaches toggle (negative value gap)
- Color-coded value gap column
- Drafted checkbox per player (removes from best-available view)
- Position scarcity panel ("only 2 RB1-tier players left")
- Static sidebar (10-team PPR locked) — toggles come v1.5

## v1.5 backlog (post-Aug-14, pre-season-start)
- VONA (Value Over Next Available — live-draft simulation)
- TD regression flagger (compare expected_tds vs actual)
- "Go Great or Go Late" QB recommender
- Auto-refresh on schedule (GitHub Actions cron or manual)
- Custom league settings toggles (PPR / half / standard, team count, roster slots)
- Injury override CSV

## Hard NOT in v1 (do not build)
- ML projection model
- Waiver wire recommender (separate project)
- Trade analyzer (separate project)
- Native mobile app (Streamlit responsive is enough)
- Auth / user accounts (single-user tool)

## Stack
- Python 3.12 + venv
- Data: requests, pandas, polars (via nflreadpy), pyarrow
- App: Streamlit
- Hosting: Streamlit Community Cloud (free tier)
- Source control: GitHub (andredagoat23/fantasy-analyzer)

## Frozen
The columns + UI sections above are the WHOLE spec. If I want to add something, it goes to v1.5 backlog. Period.