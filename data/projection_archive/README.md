# Projection archive — preseason snapshots, kept so they can be scored later

## Why this exists
`scoring_config.PROJ_W_FP` / `PROJ_W_ESPN` (currently 0.35 / 0.65) decide every point value on the
board, and they were chosen by **judgment, not measurement** — "lean ESPN, it's the room the draft
runs in." That weight has never been validated, and it **cannot** be validated retrospectively,
because nobody kept a copy of past projections:

- **FantasyPros** is proprietary and paywalled. The API returns 403, `data/FantasyPros_*.csv` are
  current-season only, and nothing exists in git history. **No archive can be reconstructed after
  the fact.**
- **ESPN** does serve historical preseason projections (verified — a genuine preseason projection has
  Christian McCaffrey at 337 pts in a season he played 4 games).
- **Sleeper** serves history too, but **2019-2020 are backfilled, not forecasts** — in those seasons
  an injured player's "projection" essentially equals what he actually scored. Only 2021+ is usable.

So the only way to ever answer "which source should we weight, and how much?" is to stop losing the
data. That starts here.

## Why it's worth the effort
Projection accuracy is the single biggest lever measured in this project: roughly **+130 to +200
roster points per +0.05 Spearman** (`icm/work/mc_research/36_projection_roi.py`). For comparison, the
entire per-player prerequisite research line was worth +5.2 points and the positional-calibration fix
was *negative*. Nothing else comes close.

## How to use it
**Every preseason, before the draft:**

```bash
.venv/bin/python tools/archive_projections.py
```

Writes a dated file and refuses to overwrite an existing one.

**The following January**, once the season's outcomes exist:

1. Pull real outcomes with `nflreadpy` and normalize names with `utils.normalize_name` (join on `key`).
2. Score each source on **accuracy** (Spearman vs actual finish) and on **value over price** — both
   ADPs are stored, and without price you can measure accuracy but not what it was worth.
3. Follow the method in `icm/work/mc_research/34_projection_calibration.py` (accuracy + per-position
   calibration) and `36_projection_roi.py` (what accuracy is worth in points).
4. Only then change `scoring_config`. Note the standing caution from `37_`-`39_`: with few seasons the
   best weight swings wildly year to year, and **which source is most accurate rotates**. Prefer a
   balanced blend over betting on one source, and require a leave-one-season-out check before moving
   a weight.

## What each row holds
`source` · `full_name` · `position` · raw component stats (`pass_yds`, `rush_td`, `rec`, …) ·
`pts_scoring_config` · `adp_espn` · `adp_sleeper` · `season` · `archived_at` · `key` (normalized name)

Components are stored raw **on purpose**: if the league's scoring ever changes, every past season can
be re-scored under the new rules instead of being stranded at the old ones.
