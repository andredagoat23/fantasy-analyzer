import pandas as pd
from utils import startable_counts

DRAFTABLE = 180
W_MODEL, W_EXPERT = 0.65, 0.35                         # rank_ecr blend
# rank_composite ("Everything") blend: value / expert(ECR) / market(ADP) / upside(x Vegas) / floor / role
W_V, W_E, W_A, W_UP, W_DN, W_R = 0.32, 0.24, 0.12, 0.13, 0.09, 0.10
ROOKIE_MKT = 0.5      # rookies: blend composite this much toward market consensus (unreliable proj)

# 1. load, keep scored players
df = pd.read_csv("players_with_outcomes.csv", dtype={"player_id": str})
board = df[df["vols"].notna()].copy()

# 1b. Vegas team environment: season implied team totals (points/game). team_env is the
#     team's implied total vs league average (>1 = high-scoring offense). This is the sharpest
#     signal for situational upside — a featured player on a high-total offense sees more scoring.
vegas = pd.read_csv("data/vegas_team_totals.csv", comment="#")
board = board.merge(vegas, on="team", how="left").rename(columns={"implied_total": "team_implied_total"})
board["team_env"] = (board["team_implied_total"] / vegas["implied_total"].mean()).fillna(1.0)

# 2. base value rank (pure VOLS) + positional label
vols_rank = board["vols"].rank(ascending=False, method="min")
board["overall_rank"] = vols_rank.astype(int)
board["pos_rank"] = board.groupby("position")["vols"].rank(ascending=False, method="min").astype(int)
board["pos_label"] = board["position"] + board["pos_rank"].astype(str)

# 3. rank_ecr — value blended with expert/situation consensus
ecr = board["ecr_rank"].fillna(vols_rank)
ecr_blend = W_MODEL * vols_rank + W_EXPERT * ecr
board["rank_ecr"] = ecr_blend.rank(method="min").astype(int)

# 4. rank_composite ("Everything") — value + expert(ECR) + market(ADP) + upside + floor + role,
#    all as cross-position ranks (robust; no shallow-position inflation). Weighting the expert /
#    market / role signals in lifts players the raw projection underrates (e.g. an alpha WR off a
#    fluky-low-TD year) so the board agrees with the AI advisor's situational read.
repl_pts = {}
for pos, n in startable_counts(board).items():
    pts = board.loc[board["position"] == pos, "total_points"].dropna()
    repl_pts[pos] = pts.nlargest(n).min() if len(pts) >= n else (pts.min() if len(pts) else 0.0)
# injury-FREE floor/ceiling here so the base composite carries no injury discount — injury is applied
# entirely by the app's "Fade injury risk" slider (0 = no injury effect anywhere). Displayed floor/
# ceiling columns stay injury-adjusted.
ceil_val = board["ceiling_healthy"] - board["position"].map(repl_pts)   # injury-free upside over replacement
floor_val = board["floor_healthy"] - board["position"].map(repl_pts)    # injury-free floor over replacement

# role = receiving usage (target share) percentile within position, for WR/TE/RB. Target share is
# the stable PPR-predictive role signal; using it (not snap share) for RBs rewards dual-threat backs
# and avoids dinging elite backs for carry-sharing or a stale committee snap share (e.g. Gibbs).
# Vegas team environment scales UPSIDE (ceiling) instead of the role signal, so a mediocre offense
# can't tank an elite workhorse (e.g. Bijan on ATL) — his VOLS/ADP/ECR/floor still anchor him.
# best demonstrated role across 2024/2025 (injury-proof: an injury-shortened season won't erase a
# proven alpha's target share, e.g. Nabers' 30% in 2024 vs 7% in an injured 2025)
role_best = board[["target_share_2024", "target_share_2025"]].max(axis=1)
role_raw = role_best.where(board["position"].isin(["WR", "TE", "RB"]))
role_pct = role_raw.groupby(board["position"]).rank(pct=True).fillna(0.5)   # QB / K / rookies neutral
ceil_val_veg = ceil_val * board["team_env"]        # upside, boosted by the Vegas scoring environment

BIG = len(board) + 1
ecr_r = board["ecr_rank"].fillna(BIG).rank(method="min")
adp_r = board["adp_rank"].fillna(BIG).rank(method="min")
comp = (W_V  * vols_rank
        + W_E  * ecr_r
        + W_A  * adp_r
        + W_UP * ceil_val_veg.rank(ascending=False, method="min")
        + W_DN * floor_val.rank(ascending=False, method="min")
        + W_R  * role_pct.rank(ascending=False, method="min"))

# rookies have no pro history, so their VOLS/role projection is a guess — anchor them halfway to
# the market consensus (ADP/ECR), which prices draft capital + landing spot. Keeps some model
# skepticism (they land a touch below ADP, since rookies are boom/bust). Veterans unaffected.
is_rook = board["is_rookie"].astype(str).str.lower().isin(["true", "1"])
comp = comp.mask(is_rook, ROOKIE_MKT * ((adp_r + ecr_r) / 2) + (1 - ROOKIE_MKT) * comp)
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
        "floor", "ceiling", "p_elite", "p_startable", "p_bust", "P_pos1",
        "xppg", "xppg_diff", "regression",   # opportunity-based regression lens (load_ff_opportunity)
        # situational fields the AI advisor reasons over (not shown in the board table)
        "team", "team_implied_total", "age", "bye_week", "target_share_2025", "snap_share_2025",
        "ecr_tier", "is_rookie", "draft_pick",
        "espn_id"]   # for live ESPN draft sync (maps ESPN pick playerId -> our player)
board[cols].to_csv("value_board.csv", index=False)
board.round(3).to_csv("app_data.csv", index=False)
board.round(3).to_json("app_data.json", orient="records", indent=2)

print(f"{len(board)} players. Top 15 by 'Everything' (composite):")
show = ["rank_composite", "overall_rank", "full_name", "pos_label", "p_startable", "p_elite"]
print(board.sort_values("rank_composite").head(15)[show].to_string(index=False))
print("\nposition mix in composite top 40:", board.sort_values("rank_composite").head(40)["position"].value_counts().to_dict())
