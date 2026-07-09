import pandas as pd

DRAFTABLE = 180   # ~15 rounds x 12 teams: the pool actually drafted

# 1. load the complete model, keep players we scored
df = pd.read_csv("players_with_outcomes.csv", dtype={"player_id": str})
board = df[df["vols"].notna()].copy()

# 2. overall + positional draft rank, by VOLS (value over replacement)
board["overall_rank"] = board["vols"].rank(ascending=False, method="min").astype(int)
board["pos_rank"] = board.groupby("position")["vols"].rank(ascending=False, method="min").astype(int)
board["pos_label"] = board["position"] + board["pos_rank"].astype(str)

# 3. value vs market = how many spots later the market drafts them than our rank
board["value_gap"] = board["adp_rank"] - board["overall_rank"]        # + = value, - = reach
in_pool = (board["adp_rank"] <= DRAFTABLE) & (board["overall_rank"] <= DRAFTABLE)
board["market"] = ""
board.loc[in_pool & (board["value_gap"] >= 12), "market"] = "VALUE"
board.loc[in_pool & (board["value_gap"] <= -12), "market"] = "REACH"
board.loc[in_pool & board["value_gap"].between(-11, 11), "market"] = "fair"

# 4. risk tier: injury/availability takes precedence, else weekly volatility
def risk(row):
    if pd.notna(row["availability"]) and row["availability"] < 0.85:
        return "Injury Risk"                       # proven starter who misses real time
    cv = row["consistency"]
    if pd.isna(cv): return "unknown"
    if cv < 0.45: return "Safe"
    if cv < 0.60: return "Balanced"
    return "Boom/Bust"
board["risk_tier"] = board.apply(risk, axis=1)

# 5. sort to master board order and save
board = board.sort_values("overall_rank")
cols = ["overall_rank", "full_name", "pos_label", "total_points", "vols", "adp_rank", "ecr_rank",
        "value_gap", "market", "risk_tier", "availability", "floor", "ceiling", "bust_rate", "P_pos1"]
board[cols].to_csv("value_board.csv", index=False)

# 6. the views you'll use on draft day
pd.set_option("display.width", 230)
show = ["overall_rank", "full_name", "pos_label", "vols", "adp_rank", "value_gap", "market", "risk_tier", "floor", "P_pos1"]
print("=== TOP 20 OVERALL ===")
print(board.head(20)[show].to_string(index=False))
print("\n=== INJURY-RISK players in the top 60 (steady points, shaky availability) ===")
print(board[(board.risk_tier == "Injury Risk") & (board.overall_rank <= 60)][show].to_string(index=False))
