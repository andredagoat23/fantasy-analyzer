import pandas as pd
import nflreadpy as nfl

STATS = [
    "passing_yards", "passing_tds",
    "rushing_yards", "rushing_tds", "carries",
    "receptions", "receiving_yards", "receiving_tds", "targets",
]


def season_totals(year, suffix):
    """Load one season's weekly stats and return REG-season totals per player,
    keyed by gsis_id, with `suffix` (e.g. '_2024') added to each stat column."""
    weekly = nfl.load_player_stats(seasons=[year]).to_pandas()
    weekly = weekly[weekly["season_type"] == "REG"]
    weekly = weekly[weekly["player_id"].notna()]
    totals = weekly.groupby("player_id")[STATS].sum().reset_index()
    rename_map = {"player_id": "gsis_id"}
    rename_map.update({s: s + suffix for s in STATS})
    return totals.rename(columns=rename_map)


# 1. read the active players (gsis_id is the join key)
active = pd.read_csv("players_active.csv", dtype={"player_id": str})

# 2. compute each season's totals, columns suffixed by year
t2024 = season_totals(2024, "_2024")
t2025 = season_totals(2025, "_2025")

# 3. left join both onto the active players (all 929 survive)
merged = active.merge(t2024, on="gsis_id", how="left").merge(t2025, on="gsis_id", how="left")

# 4. save (overwrites the single-season version)
merged.to_csv("players_with_stats.csv", index=False)

# 5. summary: who has 2024 stats, 2025 stats, and neither
has_2024 = merged[[s + "_2024" for s in STATS]].notna().any(axis=1)
has_2025 = merged[[s + "_2025" for s in STATS]].notna().any(axis=1)
neither = (~has_2024) & (~has_2025)
print(f"{len(merged)} active players")
print(f"  with 2024 stats: {int(has_2024.sum())}")
print(f"  with 2025 stats: {int(has_2025.sum())}")
print(f"  neither season:  {int(neither.sum())}")