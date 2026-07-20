# Finish-odds calibration: MC emits p_elite (top-3), P_pos1 (top-12), p_startable, p_bust.
# Empirical: given preseason positional rank, how often did players ACTUALLY finish there?
# Compare to what the live board's MC currently claims for the same tiers.
import pandas as pd
import numpy as np

OUT = "icm/work/mc_research"
sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")

pool = sea[sea["exp_pos_rank"].notna()].copy()
pool = pool[pool["exp_pos_rank"] <= 60]
# actual finish by TOTAL points (the board's definition), within season x position
pool["top3"] = pool["pos_rank_total"] <= 3
pool["top12"] = pool["pos_rank_total"] <= 12
STARTABLE = {"QB": 12, "TE": 12, "RB": 30, "WR": 30}   # flex-aware-ish tier size
pool["startable"] = pool.apply(lambda r: r["pos_rank_total"] <= STARTABLE[r["position"]], axis=1)

pool["tier"] = pd.cut(pool["exp_pos_rank"], [0, 3, 6, 12, 24, 40, 60],
                      labels=["1-3", "4-6", "7-12", "13-24", "25-40", "41-60"])
t = pool.groupby(["position", "tier"], observed=True).agg(
    n=("top3", "size"), top3=("top3", "mean"), top12=("top12", "mean"),
    startable=("startable", "mean"))
t["bust"] = 1 - t["startable"]
print("=== EMPIRICAL finish odds by preseason positional rank (2019-2025) ===")
print(t.round(3).to_string(), "\n")

# the live board's MC claims, same tiers by projection rank
board = pd.read_csv("players_with_outcomes.csv")
b = board[board["position"].isin(["QB", "RB", "WR", "TE"]) & board["P_pos1"].notna()].copy()
b["pos_rank_proj"] = b.groupby("position")["total_points"].rank(ascending=False)
b["tier"] = pd.cut(b["pos_rank_proj"], [0, 3, 6, 12, 24, 40, 60],
                   labels=["1-3", "4-6", "7-12", "13-24", "25-40", "41-60"])
t2 = b[b["tier"].notna()].groupby(["position", "tier"], observed=True).agg(
    n=("p_elite", "size"), mc_top3=("p_elite", "median"), mc_top12=("P_pos1", "median"),
    mc_startable=("p_startable", "median"), mc_bust=("p_bust", "median"))
print("=== MC's CURRENT claimed odds (live board medians, by projection rank tier) ===")
print(t2.round(3).to_string())
