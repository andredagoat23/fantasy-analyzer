import pandas as pd
from utils import normalize_name
from projections import blended_components   # FP+ESPN consensus components (single projection source-of-truth)
from scoring_config import SCORING           # Bucket-1 values — single source of truth (also read by compute_outcomes.py)

# 1. blended component projections (FP + ESPN), then score Bucket 1 = sum(stat x value).
#    Every SCORING key is a canonical component column (fg_missed derived), and non-relevant stats are
#    0-filled per position, so summing over SCORING gives each player exactly their base points.
comp = blended_components()
comp["fg_missed"] = comp["fg_att"] - comp["fg_made"]                 # missed = attempted - made (K)
comp["custom_proj_points"] = sum(comp[s] * v for s, v in SCORING.items())

# 2. join custom points onto the pipeline
players = pd.read_csv("players_with_projections.csv", dtype={"player_id": str})
players["norm_name"] = players["full_name"].apply(normalize_name)
merged = players.merge(comp[["norm_name", "position", "custom_proj_points"]],
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
