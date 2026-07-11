"""Blend Vegas-based player projections into total_points (before VOLS is computed).

Vegas lines (firstdown.studio) are among the sharpest projections available. We run each
Vegas stat line through the league's custom Bucket-1 scoring, scale it up by the player's
own bonus ratio (to be comparable to our FP total_points which includes Bucket-2 bonuses),
then blend. Players with only Vegas (missing from the FP download) get filled outright.
"""
import pandas as pd
from utils import normalize_name

BLEND = 0.5   # fraction of the projection taken from Vegas (rest from FantasyPros)

# Bucket-1 custom scoring (matches custom_scoring.SCORING; INT not in the Vegas source)
SCORING_B1 = {"pass_yds": 0.04, "pass_td": 6, "rush_yds": 0.1, "rush_td": 6,
              "rec": 1, "rec_yds": 0.1, "rec_td": 6}

df = pd.read_csv("players_final.csv", dtype={"player_id": str})
veg = pd.read_csv("data/vegas_player_proj.csv", comment="#")

# idempotency: always blend from the original FP projection, never a prior blend
if "fp_total_points" not in df.columns:
    df["fp_total_points"] = df["total_points"]

# Vegas -> custom Bucket-1 points
veg["vegas_b1"] = sum(veg[c] * w for c, w in SCORING_B1.items())
veg["norm"] = veg["name"].apply(normalize_name)
df["norm"] = df["full_name"].apply(normalize_name)

# bonus ratio (total / bucket-1) per position, from players who have both — used to lift the
# Vegas bucket-1 to a full-scoring estimate comparable to our total_points
both = df[(df["custom_proj_points"] > 0) & df["fp_total_points"].notna()]
ratio_series = both["fp_total_points"] / both["custom_proj_points"]
pos_ratio = ratio_series.groupby(both["position"]).median().to_dict()
overall_ratio = ratio_series.median()

m = df.merge(veg[["norm", "position", "vegas_b1"]], on=["norm", "position"], how="left")

def vegas_total(r):
    if pd.isna(r["vegas_b1"]):
        return None
    if r["custom_proj_points"] > 0 and pd.notna(r["fp_total_points"]):
        ratio = r["fp_total_points"] / r["custom_proj_points"]
    else:
        ratio = pos_ratio.get(r["position"], overall_ratio)
    return r["vegas_b1"] * ratio

m["vegas_total"] = m.apply(vegas_total, axis=1)

def blend(r):
    fp, vg = r["fp_total_points"], r["vegas_total"]
    if pd.notna(vg) and pd.notna(fp):
        return (1 - BLEND) * fp + BLEND * vg   # blend
    if pd.notna(vg):
        return vg                              # Vegas-only: fill a missing FP projection
    return fp                                  # FP-only / neither: unchanged

m["total_points"] = m.apply(blend, axis=1)
m = m.drop(columns=["norm", "vegas_b1", "vegas_total"])
m.to_csv("players_final.csv", index=False)

matched = m["fp_total_points"].notna() if False else None
n_match = m.merge(veg[["norm"]].assign(_v=1), left_on=m["full_name"].apply(normalize_name),
                  right_on="norm", how="inner").shape[0]
filled = int(((df["custom_proj_points"].isna() | (df["custom_proj_points"] <= 0))
              & df["full_name"].apply(normalize_name).isin(veg["norm"])).sum())
print(f"blended Vegas into total_points ({BLEND:.0%} Vegas / {1-BLEND:.0%} FP)")
print(f"  Vegas rows: {len(veg)} | matched to a player: {veg['norm'].isin(df['norm']).sum()}")
print(f"  players that had NO FP projection and got filled from Vegas: {filled}")
