import pandas as pd
from utils import startable_counts

# 1. read the league-scored board
df = pd.read_csv("players_final.csv", dtype={"player_id": str})

# 2. replacement level = the last STARTABLE player at each position. The startable count
#    is flex-aware (24 RB + 24 WR + 12 TE locked, 12 FLEX to the best remaining RB/WR/TE,
#    QB/K fixed at 12), so RB vs WR floats with the projections.
counts = startable_counts(df)
replacement_level = {}
for pos, n in counts.items():
    pts = df[(df["position"] == pos) & df["total_points"].notna()]["total_points"]
    replacement_level[pos] = pts.nlargest(n).min()      # smallest of the top N = the Nth best

# 3. VOLS = a player's points minus their position's replacement level
df["vols"] = df["total_points"] - df["position"].map(replacement_level)

# 4. save
df.to_csv("players_with_metrics.csv", index=False)

# 5. report
print("startable counts (flex-allocated):", counts)
print("replacement level (points) by position:")
for pos, lvl in replacement_level.items():
    print(f"  {pos}: {lvl:.1f}")
print("\ntop 15 by VOLS:")
print(df.nlargest(15, "vols")[["full_name", "position", "total_points", "vols"]].to_string(index=False))