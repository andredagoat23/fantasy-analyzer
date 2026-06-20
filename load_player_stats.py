import pandas as pd
import nflreadpy as nfl

STATS = [
    "passing_yards", "passing_tds",
    "rushing_yards", "rushing_tds", "carries",
    "receptions", "receiving_yards", "receiving_tds", "targets",
]

# 1. read the active players (gsis_id is already the join key)
active = pd.read_csv("players_active.csv", dtype={"player_id": str})

# 2. load 2024 weekly stats (polars) and convert to pandas
weekly = nfl.load_player_stats(seasons=[2024]).to_pandas()

# 3. regular season only, and drop the null-id junk rows
weekly = weekly[weekly["season_type"] == "REG"]
weekly = weekly[weekly["player_id"].notna()]

# 4. aggregate weekly rows into 2024 season totals, one row per player
totals = weekly.groupby("player_id")[STATS].sum().reset_index()

# 5. the stats' player_id is a GSIS id -> rename so it joins to our gsis_id
totals = totals.rename(columns={"player_id": "gsis_id"})

# 6. left join: keep all active players, attach stats where they exist
merged = active.merge(totals, on="gsis_id", how="left")

# 7. save
merged.to_csv("players_with_stats.csv", index=False)

# 8. summary
has_stats = merged[STATS].notna().any(axis=1).sum()
print(f"{len(merged)} active players")
print(f"  with 2024 stats: {has_stats}")
print(f"  no 2024 stats (NaN): {len(merged) - has_stats}")