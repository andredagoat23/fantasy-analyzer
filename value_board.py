import pandas as pd
from utils import startable_counts

DRAFTABLE = 180
W_MODEL, W_EXPERT = 0.65, 0.35                         # rank_ecr blend
W_V, W_E, W_UP, W_DN = 0.40, 0.25, 0.20, 0.15          # rank_composite blend (rank-based)

# 1. load, keep scored players
df = pd.read_csv("players_with_outcomes.csv", dtype={"player_id": str})
board = df[df["vols"].notna()].copy()

# 2. base value rank (pure VOLS) + positional label
vols_rank = board["vols"].rank(ascending=False, method="min")
board["overall_rank"] = vols_rank.astype(int)
board["pos_rank"] = board.groupby("position")["vols"].rank(ascending=False, method="min").astype(int)
board["pos_label"] = board["position"] + board["pos_rank"].astype(str)

# 3. rank_ecr — value blended with expert/situation consensus
ecr = board["ecr_rank"].fillna(vols_rank)
ecr_blend = W_MODEL * vols_rank + W_EXPERT * ecr
board["rank_ecr"] = ecr_blend.rank(method="min").astype(int)

# 4. rank_composite — value + expert + upside + floor-safety, all in cross-position VALUE terms,
#    combined as ranks (robust to outliers; no shallow-position inflation)
repl_pts = {}
for pos, n in startable_counts(board).items():
    pts = board.loc[board["position"] == pos, "total_points"].dropna()
    repl_pts[pos] = pts.nlargest(n).min() if len(pts) >= n else (pts.min() if len(pts) else 0.0)
ceil_val = board["ceiling"] - board["position"].map(repl_pts)     # upside over replacement
floor_val = board["floor"] - board["position"].map(repl_pts)      # downside over replacement
comp = (W_V * vols_rank
        + W_E * ecr_blend.rank(method="min")
        + W_UP * ceil_val.rank(ascending=False, method="min")
        + W_DN * floor_val.rank(ascending=False, method="min"))
board["rank_composite"] = comp.rank(method="min").astype(int)

# 5. value vs market
board["value_gap"] = board["adp_rank"] - board["overall_rank"]
in_pool = (board["adp_rank"] <= DRAFTABLE) & (board["overall_rank"] <= DRAFTABLE)
board["market"] = ""
board.loc[in_pool & (board["value_gap"] >= 12), "market"] = "VALUE"
board.loc[in_pool & (board["value_gap"] <= -12), "market"] = "REACH"
board.loc[in_pool & board["value_gap"].between(-11, 11), "market"] = "fair"

# 6. risk tier
def risk(row):
    if pd.notna(row["availability"]) and row["availability"] < 0.85:
        return "Injury Risk"
    cv = row["consistency"]
    if pd.isna(cv): return "unknown"
    if cv < 0.45: return "Safe"
    if cv < 0.60: return "Balanced"
    return "Boom/Bust"
board["risk_tier"] = board.apply(risk, axis=1)

board = board.sort_values("rank_composite")

cols = ["overall_rank", "rank_ecr", "rank_composite", "full_name", "pos_label", "total_points", "vols",
        "adp_rank", "ecr_rank", "value_gap", "market", "risk_tier", "availability",
        "floor", "ceiling", "p_elite", "p_startable", "p_bust", "P_pos1"]
board[cols].to_csv("value_board.csv", index=False)
board.round(3).to_csv("app_data.csv", index=False)
board.round(3).to_json("app_data.json", orient="records", indent=2)

print(f"{len(board)} players. Top 15 by 'Everything' (composite):")
show = ["rank_composite", "overall_rank", "full_name", "pos_label", "p_startable", "p_elite"]
print(board.sort_values("rank_composite").head(15)[show].to_string(index=False))
print("\nposition mix in composite top 40:", board.sort_values("rank_composite").head(40)["position"].value_counts().to_dict())
