import pandas as pd

# replacement level = the last startable player at each position (12-team PPR)
REPLACEMENT = {"QB": 12, "RB": 30, "WR": 36, "TE": 12, "K": 12}   # DEF dropped (no projections)

# 1. read the league-scored board
df = pd.read_csv("players_final.csv", dtype={"player_id": str})

# 2. find each position's replacement-level points (the Nth-best scorer)
replacement_level = {}
for pos, n in REPLACEMENT.items():
    pts = df[(df["position"] == pos) & df["total_points"].notna()]["total_points"]
    replacement_level[pos] = pts.nlargest(n).min()      # smallest of the top N = the Nth best

# 3. VOLS = a player's points minus their position's replacement level
df["vols"] = df["total_points"] - df["position"].map(replacement_level)

# 4. save
df.to_csv("players_with_metrics.csv", index=False)

# 5. report
print("replacement level (points) by position:")
for pos, lvl in replacement_level.items():
    print(f"  {pos}: {lvl:.1f}")
print("\ntop 15 by VOLS:")
print(df.nlargest(15, "vols")[["full_name", "position", "total_points", "vols"]].to_string(index=False))