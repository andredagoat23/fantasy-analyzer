# Pipeline internals (Layer 3 — the FROZEN data chain, deep reference)

`architecture.md` has the high-level flow. THIS doc is the durable "how each layer actually works and
where it bites" knowledge — the stuff you need before touching (or debugging output from) the
pipeline. **The pipeline is FROZEN: do not edit these scripts unless the user explicitly asks.** When
you do, reproduce with the REAL numbers first (a result that's too *large* is as suspicious as too
small) and flag data gaps rather than working around them (lesson L6).

All scripts + `utils.py` live in the **project ROOT** and must run from there (a script in `data/`
gets "No module named utils"). `run_all.py` regenerates the whole chain in ~19s and stops on any
failure — ALWAYS use it; piecemeal runs drift (a stale all-null `bye_week` bug came from downstream
files predating the bye-fill).

## The chain
`players.py` → `filter_active.py` → `load_player_stats.py` → `load_fp_adp.py` (now live ESPN ADP) →
`load_ecr.py` → `load_fp_projections.py` → `custom_scoring.py` → `apply_bonuses.py` →
`compute_metrics.py` (VOLS) → `compute_outcomes.py` (Monte Carlo) → `load_ff_opportunity.py` (xPPG) →
`value_board.py` → `value_board.csv` (+ `app_data.csv`/`app_data.json`).

## The gsis_id gap (the #1 pipeline trap)
Sleeper's `/players/nfl` `gsis_id` is **incompletely populated** — missing for many players who
entered ~2019–2020+ including stars (Lamb, Jefferson, Chase, Lamar all had `gsis_id = None`; only
~32% of active skill players had one; ~27% of populated ones have a leading space → `.strip()`).
- **Do NOT join Sleeper→nflreadpy stats on Sleeper's `gsis_id`** — it silently drops active stars.
- **Correct bridge:** anchor on Sleeper's own `player_id` (always present — it's the dict key), then
  use `nflreadpy.load_ff_playerids()` (a DynastyProcess crosswalk, returns **polars**) which has both
  `sleeper_id` and `gsis_id`, to translate `player_id → gsis_id`, then check membership in
  `load_player_stats([2024, 2025])`'s `player_id` column (which holds gsis ids).
- **Null-match bug (caught 2026-06-16):** `load_player_stats` has ~44 rows with NULL `player_id`.
  Building `set(stats["player_id"])` puts `None` in the set; unmatched players get `NaN` from `.map()`,
  and pandas `.isin()` matches `NaN`↔`None`, wrongly keeping ~1241 never-played players (2058 vs the
  correct 817). FIX: `.drop_nulls()` before building the set; guard the player side too (keep a row
  only if `position=="DEF"` OR gsis is non-null AND in the set). **Correct filtered count = 817**
  (785 w/ gsis + 32 DEF) — a realistic roster size.
- nflreadpy returns **polars**, not pandas. gsis presence ≠ active (retired players keep it forever) —
  the join to 2024–25 stats is what drops retired/never-played.

## `filter_active.py` — active + rookies + byes → `players_active.csv` (929)
Base 817 = players with a 2024/25 stat line. That misses rookies with no stat line, so two tracks add
them into a `keep_ids` set:
- **Track A — 2025 rookies who didn't play (~32):** `load_rosters([2026])`, skill positions,
  `entry_year == 2025`, non-null `sleeper_id` → clean ID join on `sleeper_id`.
- **Track B — 2026 drafted rookies (~80):** `load_draft_picks([2026])`, skill positions, matched by
  `normalize_name()` + position to the Sleeper `years_exp == 0` pool. **Name-match is the ONLY option**
  — nflverse has 0% sleeper/espn/yahoo id for the 2026 class (only gsis, which Sleeper lacks for
  rookies). Scope: **drafted only**, not undrafted FAs. **This is a TEMPORARY stopgap** — once
  nflverse links sleeper_id/espn_id for the 2026 class (expected over summer 2026), replace the fragile
  name-match with a clean ID join and re-run.
- `normalize_name()` gotcha: squeeze whitespace BEFORE stripping the Jr/Sr/III suffix (punctuation→
  space leaves a trailing space that breaks the `$`-anchored suffix regex). Rookie gsis backfilled via
  `.fillna(...map(rookie_gsis))`.
- **bye_week** (built here): from `load_schedules([2026])` (REG) — each team plays 17 of 18 weeks; the
  missing week is the bye. ⚠️ Sleeper uses `LAR` for the Rams, nflverse schedule uses `LA` →
  `bye.rename({"LA":"LAR"})`. Free agents (team=None) stay blank. Filled 746/929.

## `load_player_stats.py` → `players_with_stats.csv` (929)
Per-season columns for 2024 & 2025 (suffixed `_2024`/`_2025`). Everything keys on `gsis_id`. Always
filter `season_type == "REG"` (or `game_type` for snaps) and drop null player_ids.
- **Season totals:** `load_player_stats([year])` — weekly; groupby `player_id`(=gsis) + sum. 9 stats
  incl `carries`.
- **snap_share (QB/RB/WR/TE):** `load_snap_counts([year])` — use `offense_pct`, average per player.
  ⚠️ keyed by **`pfr_player_id`**, NOT gsis — bridge via `load_ff_playerids()` `pfr_id → gsis_id`
  (~99%). K uses `st_pct`, DEF = team unit → excluded.
- **target_share (RB/WR/TE — RB included for PPR):** player targets ÷ team total targets from
  `load_team_stats([year])`. **Traded players:** assign to their primary team (most targets:
  `groupby([player_id,team]).targets.sum().idxmax`), divide by that team's total — exact for
  non-traded, approximate for traded.

## Draft signals
- **ADP** — SWITCHED sources over time: FFC API → FantasyPros/ESPN CSV → **live public ESPN ADP**
  (`load_espn_adp.py`, current; re-run `run_all.py` the morning of the draft to refresh). FFC was
  dropped as too noisy in June (`total_drafts` didn't reconcile with per-player `times_drafted`; it
  ranked Bijan ~pick 17). Sleeper has NO public ADP endpoint.
  - Parsing gotcha (FP CSV era, still instructive): the "Player (Team / Bye)" col has THREE formats —
    `"Name  TEAM (BYE)"`, team-less FAs `"Name"`, and defenses `"Houston Texans DST  (BYE)"`. Use
    `.str.split(r"\s{2,}", n=1, expand=True)` (part 0 = name) NOT a strict regex (a strict regex drops
    the team-less players and makes `normalize_name(NaN)="nan"` collide with blank-`full_name` DEF rows
    → merge explodes 929→1921). POS like `"RB1"`/`"DST3"` → strip trailing `\d+$`, then `DST→DEF`.
    `PK`→`K` for kickers.
- **ECR** (`load_ecr.py`): FantasyPros ECR CSV → `ecr_rank`(RK), `ecr_tier`(TIERS), `sos_season`
  (TEXT like "4 out of 5 stars", not a number). ⚠️ tier-separator rows have blank PLAYER NAME →
  `dropna(subset=["name"])` or the `"nan"` collision explodes the merge again. Compare ADP vs ECR:
  ADP later than ECR = value; earlier = reach.
- `normalize_name` lives in shared **`utils.py`** with `NAME_ALIASES` for nicknames
  (`kenny gainwell`→`kenneth gainwell`, `hollywood brown`→`marquise brown`), applied at the end so all
  joins benefit. An empty `utils.py` still imports → "cannot import name normalize_name" (not "no
  module"); make sure it has content.

## `load_fp_projections.py` → `players_with_projections.csv`
Reads 5 files `data/FantasyPros_..._{QB,RB,WR,TE,K}.csv`; position comes from the FILENAME. ⚠️
**QB/RB/WR/TE have a blank subheader row at line 2, K does NOT** — filter blank-Player rows, don't
`skiprows=[1]` (that deletes the top kicker). ⚠️ **The FP `FPTS` column is STANDARD scoring (0 PPR)** —
verified by reconstructing the standard formula (Gibbs 301.6 = computed 301.3). League is PPR so
`proj_points = FPTS + receptions` (RB/WR/TE have `REC`; QB/K don't — correct, PPR only adds
1/reception). This bug was a USER catch — the kind of data-quality flag we never skip.

## Scoring layers (the "custom" in custom-scoring)
League = **ESPN**, full PPR + heavy big-play/boom bonuses.
- **`custom_scoring.py` → `players_scored.csv` (Bucket 1, stat×value):** pass 0.04/yd, **6/pass TD**
  (not 4 — big QB boost), −2/INT; rush 0.1/yd, 6/TD; rec 0.1/yd, **1/rec**, 6/TD; −2/fumble lost;
  K +1 PAT, −1 missed FG. `POS_MAP` handles that files reuse col names (QB `YDS`=pass, RB=rush,
  WR/TE=rec; TE has no rush cols). `to_num` strips comma-thousands.
- **`apply_bonuses.py` → `players_final.csv` (Bucket 2, rate × projected volume):** long-TD bonuses
  use **per-player shrinkage-blended rates** (empirical Bayes `(player_long_TDs + K·league)/(player_
  total_TDs + K)`, K=12, from 2023-25 pbp) so burners (Tyreek ~0.3 rec-TD-40+) separate from red-zone
  guys (Andrews 0.04). Big-games/first-downs/FG-distance use flat league rates. `total_points` =
  `custom_proj_points + bonus_points`. SEPARATE script because the pbp load is slow. ⚠️ COMMENT-BUG
  lesson: don't put a 2nd assignment after `#` on one line — it's silently a comment (RETD40/RY100 were
  undefined). ESTIMATE, not exact; the big-game bonus is CONSERVATIVE (linear per-yard undercounts the
  boomiest players).
- **Skip/not-projectable:** 2pt conv, QB sacks-taken, PAT missed, return yds. **Team DST:** elaborate
  points/yards-allowed tiers — NO defense projections in the pipeline, entirely out of scope until a
  DST projection source is added. (This is why D/ST isn't on the board and must be tracked separately —
  lesson L9, `bridge.my_dst`.)

## `compute_metrics.py` — VOLS
**VOLS (Value Over Last Starter)** = `total_points − positional replacement level`, using
`total_points` (REAL league scoring), NOT generic `proj_points` — that's the whole point of the custom
scoring. 12-team replacement levels: QB12, RB30, WR36, TE12, K12; **DEF dropped**.
`replacement_level[pos] = pts.nlargest(n).min()`. Insight: top VOLS is all RB/WR, ZERO QBs — QB
replacement is ~367 (deep, high-scoring in a 6pt-pass-TD league) so their value-over-replacement is
low despite high raw points. This is WHY the advisor drafts by VONA off VOLS and QB/TE fall naturally
(see `draft-strategy.md`); if VOLS ever over-rates elite rushing QBs, that's a board-calibration issue
to FLAG, not hack around (lesson L3).

## `compute_outcomes.py` — Monte Carlo risk (tunable knobs at top)
**Wave-1 recalibrated (Jul 2026):** every constant fit to 2019–2025 real outcomes vs preseason market
expectation and BACKTESTED (60.3% 20/80-band coverage vs 60% target; predicted boom 15.0% vs realized
15.3%; old constants scored 41.5%/7.0%). Evidence + rerunnable scripts: `icm/work/mc_research/`,
findings: `icm/work/mc-research-findings.md`.
Scores each player-week under league rules from 2024-25 weekly → `consistency`(CV), `boom_rate`/
`bust_rate`. Then Monte Carlo (20k sims/pos): **right-skewed log-normal** season multiplier,
season ~ games × coupling × M, re-centered so E[season] = `total_points` × tilt exactly; rank within
position each sim → `p_elite`/`p_startable`/`p_bust` + `floor`/`ceiling`/`p10`/`p90`. Layers:
- **Depth-dependent sigma (`SIGMA_ANCHORS`):** per-game lognormal sigma interpolated by projection
  positional rank — variance GROWS with rank depth (elite bands ~1.6–1.9×, rank-25+ bands 2.2–3.5×).
  Replaced the flat ROLE_RISK=0.20 that made booms 4× rarer than reality. Rookies get a sigma
  multiplier {QB 1.5, RB 1.4, TE 1.1, WR 1.0 — rookie WRs are NOT wider}.
- **Injury/availability:** shrinkage + age penalty, recalibrated: PRIOR {QB .845, RB .817, WR .841,
  TE .828, K .97} (real starters play ~.82–.85 at EVERY position), K=4 (injury-proneness barely
  recurs among starters: +3.5pp), age cliffs at 29 for RB/WR/TE (slopes .035/.025/.030), QB none.
  Clip floor .5. Only for proven starters (`max_season>=14`); rest fall back to position prior.
- **Catastrophic tail:** `p_major = clip(P_MAJOR_POS + 0.5·(0.84−avail), .05, .18)` with position
  bases {QB .103, RB .108, WR .089, TE .071} (= empirical P(miss 9+)); lost seasons play U(1,8) games.
- **Games↔per-game coupling (`COUPLE=0.41`):** missing time also degrades per-game output
  (miss 4-8 → ~10% worse, 9+ → ~20%; corr .29) — this is what fattens the left tail correctly.
- **Draft-capital tilt (refit):** top-15 1.10, 16-32 1.08, 2nd rd 1.00, 3rd rd 0.92 (the dead zone),
  4th+ 0.95. rng seeded.
- **Wave-2 situational tilts (backtested in `09_wave2_validation.py`; global coverage held 59.7%):**
  team-changers (vs last 2025 team, LA→LAR normalized) — QB tilt .97 σ×1.40, RB tilt .94,
  TE tilt .95 σ×1.15 (real changer bust .38-.40 vs .23-.27 stayers); stable RB/TE vets σ×0.85;
  WR age-30+ tilt .98 σ×0.70 (booms fade — kept conservative, n=53); CV blend
  σ×clip(1+0.30·(cv_rel−1), .8, 1.3) for non-rookie vets (volatile players run wider). Late-usage
  surge tested and DROPPED (noise under Wave-1). Known residuals (documented, not chased): RB/TE
  stayers' bust still ~7pp overpredicted (games-machinery-driven; stayers actually get MORE
  catastrophic injuries — selection effect), WR30+ boom residual within noise at n=53.
- ⚠️ CAVEATS: sigma anchors estimated vs MARKET expectation (≈ our projections in accuracy, not
  identical); deep-QB sigma clipped (backup contamination); per-player CV no longer feeds sigma
  (unvalidated — candidate for Wave 2 re-validation); handcuff contingent upside still understated.
  Acceptance test after ANY re-tune: rerun `icm/work/mc_research/05_distribution.py` +
  `06_finish_odds.py` — new board bands/odds must land on the empirical tables.

## `load_ff_opportunity.py` — xPPG regression lens
Source: `nfl.load_ff_opportunity()` (OPEN-licensed) — per-week `total_fantasy_points_exp` (expected FP
from opportunity), keyed by gsis. Pools 2024+25 (games≥8): `xppg`, `xppg_diff = actual − expected`,
position-relative z, then **elite dampening on the POSITIVE side only** (`keep=clip(0.05+0.95·(pos_
rank-1)/30,.05,1)`) — because raw overperformers are almost all elite (they MAKE their TDs, not lucky);
without dampening we'd wrongly fade Bijan/Chase/Henry. Labels: ≥1 "TD-lucky", ≤−1 "Buy-low", else
"Sustainable". **Team-change fix:** xPPG is backward-looking (old team) → `switched_team` flagged
(roster team vs `load_rosters(2025)`, abbrev-normalized); for switchers `value_board.py` uses their
**2026 VOLS percentile** instead of stale xPPG (forward-looking, no artificial ties). Advisor is told
to trust the 2026 projection over stale xPPG for switchers, and never to fade a stud on xPPG alone —
it's a tiebreaker/sustainability check, not a projection.

## `value_board.py` — the board
Ranks scored players; emits `overall_rank` + `pos_label` (RB1/TE9), `value_gap = adp_rank −
overall_rank` (+VALUE/−REACH — only tagged within the DRAFTABLE pool, both ranks ≤180, else the deep
tail manufactures fake +154 "values"), `risk_tier` (availability<0.85 → "Injury Risk", else CV bands
Safe<0.45<Balanced<0.60<Boom/Bust). Carries THREE rankings (points stay pure): `overall_rank` (VOLS),
`rank_ecr` (0.65·VOLS_rank+0.35·ECR_rank — experts fade Aubrey, lift McConkey), `rank_composite`
(RANK-based cross-position value, current weights: **0.32·rank(VOLS) + 0.24·rank(ECR) + 0.12·rank(ADP)
+ 0.13·rank(ceiling−repl, ×vegas team_env) + 0.09·rank(floor−repl) + 0.10·rank(role)**; the ROLE term
uses xPPG percentile w/ VOLS-pct fallback for switchers). Two blends adjust it: **rookies** anchor
halfway to market (ADP/ECR); a **consensus outlier** (non-rookie whose proj ranks >100 spots better
than ECR) blends 60% toward ECR + is flagged `proj_outlier` (L17). ⚠️ the composite was REBUILT once —
the original used position-RELATIVE p_elite/p_bust which inflated shallow QB/TE/K; rank-based
cross-position fixed it. value_board.py ALSO now emits `team_role`/`role_lead`/`role_env_ok` (depth-
chart role for the advisor, L16), DROPS no-team FAs, and gates the VALUE tag on `p_startable≥0.40`
(no below-startable "steals", L16). Writes `app_data.csv`/`app_data.json` (`orient=records`, NaN→null).
DROPS NaN-projection players (why Tyreek is absent — L6). Sorted by `rank_composite`.

## Still-pending pipeline items
- **DST scoring** — no defense projection source yet (out of scope until one exists).
- **2026 rookie clean re-run** — swap Track B's name-match for an ID join once nflverse links the 2026
  class (see filter_active above).
- A few stars can be missing from a FantasyPros projection download (→ NaN → dropped); re-download that
  position's file to fix, and run `tools/name_audit.py` after any regen to catch it before draft day.
