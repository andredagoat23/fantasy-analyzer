import pandas as pd
import glob
import re
from utils import normalize_name

# --- your league's stat-based (Bucket 1) scoring — edit values here ---
SCORING = {
    "pass_yds": 0.04, "pass_td": 6, "pass_int": -2,
    "rush_yds": 0.1,  "rush_td": 6,
    "rec": 1, "rec_yds": 0.1, "rec_td": 6,
    "fumbles_lost": -2,
    "pat_made": 1, "fg_missed": -1,
}

# per-position: canonical stat -> that file's raw column
# (files reuse names — QB "YDS" is passing, RB "YDS" is rushing, etc.)
POS_MAP = {
    "QB": {"pass_yds":"YDS","pass_td":"TDS","pass_int":"INTS","rush_yds":"YDS.1","rush_td":"TDS.1","fumbles_lost":"FL"},
    "RB": {"rush_yds":"YDS","rush_td":"TDS","rec":"REC","rec_yds":"YDS.1","rec_td":"TDS.1","fumbles_lost":"FL"},
    "WR": {"rec":"REC","rec_yds":"YDS","rec_td":"TDS","rush_yds":"YDS.1","rush_td":"TDS.1","fumbles_lost":"FL"},
    "TE": {"rec":"REC","rec_yds":"YDS","rec_td":"TDS","fumbles_lost":"FL"},
    "K":  {"pat_made":"XPT","fg_made":"FG","fg_att":"FGA"},
}


def to_num(series):
    """Parse a stat column to numbers, stripping comma-thousands like '3,812.5'."""
    return pd.to_numeric(series.astype(str).str.replace(",", ""), errors="coerce").fillna(0)


# 1. read each projection file, pull its stats, compute custom points
frames = []
for f in sorted(glob.glob("data/FantasyPros_Fantasy_Football_Projections_*.csv")):
    pos = re.search(r"_([A-Z]+)\.csv$", f).group(1)
    df = pd.read_csv(f)
    df = df[df["Player"].notna() & (df["Player"].str.strip() != "")].copy()
    stats = {canon: to_num(df[raw]) for canon, raw in POS_MAP[pos].items()}
    if pos == "K":
        stats["fg_missed"] = stats["fg_att"] - stats["fg_made"]     # missed = attempted - made
    points = sum(stats[s] * v for s, v in SCORING.items() if s in stats)
    frames.append(pd.DataFrame({"name": df["Player"], "position": pos, "custom_proj_points": points}))

scored = pd.concat(frames, ignore_index=True)
scored["norm_name"] = scored["name"].apply(normalize_name)

# 2. join custom points onto the pipeline
players = pd.read_csv("players_with_projections.csv", dtype={"player_id": str})
players["norm_name"] = players["full_name"].apply(normalize_name)
merged = players.merge(scored[["norm_name", "position", "custom_proj_points"]],
                       on=["norm_name", "position"], how="left")
merged = merged.drop(columns="norm_name")

# 3. save
merged.to_csv("players_scored.csv", index=False)

# 4. summary
have = merged["custom_proj_points"].notna()
print(f"{have.sum()} players scored (of {len(merged)})")
print("  by position:", merged[have].groupby("position").size().to_dict())
print("\ntop 5 by custom score:")
print(merged.nlargest(5, "custom_proj_points")[["full_name", "position", "custom_proj_points"]].to_string(index=False))