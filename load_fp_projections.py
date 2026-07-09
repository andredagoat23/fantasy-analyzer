import pandas as pd
import glob
import re
from utils import normalize_name

# 1. find the 5 projection files (QB, RB, WR, TE, K)
files = sorted(glob.glob("data/FantasyPros_Fantasy_Football_Projections_*.csv"))

# 2. read each file, tag position from filename, compute PPR points
frames = []
for f in files:
    pos = re.search(r"_([A-Z]+)\.csv$", f).group(1)
    df = pd.read_csv(f)
    df = df[df["Player"].notna() & (df["Player"].str.strip() != "")].copy()
    fpts = pd.to_numeric(df["FPTS"], errors="coerce")                      # standard (0-PPR) points
    rec = pd.to_numeric(df["REC"], errors="coerce") if "REC" in df.columns else 0
    frames.append(pd.DataFrame({
        "name": df["Player"],
        "team": df["Team"],
        "position": pos,
        "proj_points": fpts + rec,        # PPR = standard FPTS + 1 point per reception
    }))

# 3. concat + build join key
proj = pd.concat(frames, ignore_index=True)
proj["norm_name"] = proj["name"].apply(normalize_name)

# 4. read players + left join
players = pd.read_csv("players_with_ecr.csv", dtype={"player_id": str})
players["norm_name"] = players["full_name"].apply(normalize_name)
merged = players.merge(proj[["norm_name", "position", "proj_points"]],
                       on=["norm_name", "position"], how="left")
merged = merged.drop(columns="norm_name")

# 5. save
merged.to_csv("players_with_projections.csv", index=False)

# 6. summary
have = merged["proj_points"].notna()
print(f"{len(merged)} active players, {have.sum()} with PPR projections")
print("  by position:", merged[have].groupby("position").size().to_dict())
chk = proj.merge(players[["norm_name", "position"]].drop_duplicates(),
                 on=["norm_name", "position"], how="left", indicator=True)
print("  projection entries unmatched:", (chk["_merge"] == "left_only").sum())