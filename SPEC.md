# Fantasy Analyzer — v1 Spec (FROZEN)

**Frozen on:** 2026-06-15
**Ship target:** 2026-08-14, new ship is 2026-07-31 due to draft being scheduled for then
**Rule:** Anything not in this doc is NOT in v1. New ideas go to v1.5 backlog.

## League assumption (v1)
- Custom PPR-based (full scoring in "Scoring rules" section below)
- 12 teams
- Standard roster: 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 D/ST, 1 K, 7 bench, 1 IR
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
- FG made (by distance): 0-39: 3, 40-49: 4, 50-59: 6, 60+: 7
- PAT: 1
- Missed PAT: -1

### D/ST
- Sack: 1
- Interception: 2
- Fumble recovery: 2
- TD: 6
- Safety: 2
- Points allowed and Yards allowed brackets: Standard

### Misc
- Fumble lost: -2
- Any other quirky rule: 1 pt per 25 Kick Return Yards, 1 pt per 10 punt return yards, Rest is standard

### Source
- Pulled from: LCS 9th Grade Fantasy Football League on ESPN
- Date confirmed: 2026-06-15
## Data sources
1. Sleeper API — player metadata (working as of 6/3)
2. nflreadpy — 2024 + 2025 stats, snap counts, route data
3. FantasyPros — manual CSV downloads (ECR, ESPN ADP with 407 players, Season Projections QB/RB/WR/TE/K). PRIMARY data hub as of 2026-06-25. Refresh weekly pre-season.
4. Fantasy Football Calculator (FFC) — DEPRECATED as of 2026-06-25. Kept as fallback only. FFC data was sparse (90 players, median 18 drafts sample) and generic-scoring only.

## Required columns in main player table
Each row = one player. Columns:
- player_name
- position (QB / RB / WR / TE / K / D/ST)
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
- proj_points (from FantasyPros Season Projections CSV; custom scoring applied at compute time)

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
- TD regression flagger (compare expected_tds vs actual)

## v1.5 backlog (post-Aug-14, pre-season-start)
- VONA (Value Over Next Available — live-draft simulation)
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

## Known data quality issues (TODO for build week 1)

### Position naming
- Sleeper API returns "DEF" for team defenses.
- Data layer keeps "DEF" (raw API value).
- UI display layer translates "DEF" → "D/ST" via a POSITION_DISPLAY_MAP dict.
- Translation happens in ONE place only — at render time.

### Ghost players in Sleeper "active" set
- ...existing description...
- Status: RESOLVED 2026-06-20 with two-track approach:
  - Track A (2025 rookies who didn't play): use load_rosters(seasons=[2026]) filtered to entry_year==2025, join on sleeper_id.
  - Track B (2026 rookies): use load_draft_picks(seasons=[2026]) with name normalization to match against Sleeper rookies (years_exp==0).
  - Backfill gsis_id for added rookies so downstream joins work.
  - Unmatched 2026 picks logged for manual review (no silent failures).

### isin() + NaN matching gotcha (caught + fixed 2026-06-16)
- pandas isin() with sets containing None will match other None values silently.
- nflreadpy stats sometimes contain rows with player_id=None (special teams/team-level entries).
- Without explicit NaN guard, every Sleeper player not in the crosswalk gets None → matches None in stats set → passes filter.
- Fix in filter_active.py: build played_gsis as a set comprehension excluding None/empty, AND add .notna() guard to the keep mask.
- Lesson: when joining on IDs across libraries, always strip None from both sides before isin().

## Frozen
The columns + UI sections above are the WHOLE spec. If I want to add something, it goes to v1.5 backlog. Period.