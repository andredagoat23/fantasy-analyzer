import pandas as pd
from utils import startable_counts

DRAFTABLE = 180
W_MODEL, W_EXPERT = 0.65, 0.35                         # rank_ecr blend
# rank_composite ("Everything") blend: value / expert(ECR) / market(ADP) / upside(x Vegas) / floor / role
W_V, W_E, W_A, W_UP, W_DN, W_R = 0.32, 0.24, 0.12, 0.13, 0.09, 0.10
ROOKIE_MKT = 0.5      # rookies: blend composite this much toward market consensus (unreliable proj)
# consensus sanity: when our projection ranks a NON-rookie this many spots better than expert consensus
# (ECR), the projection is a likely outlier — blend his composite this much toward ECR so he can't look
# draftable after the experts wrote him off (e.g. John Metchie: our 148 vs ECR 361 vs ESPN 589).
CONSENSUS_GAP, CONSENSUS_ECR = 100, 0.6

# 1. load, keep scored players
df = pd.read_csv("players_with_outcomes.csv", dtype={"player_id": str})
board = df[df["vols"].notna()].copy()
# Drop unsigned free agents (no NFL team) — no offense, no role, unreliable projection, not draftable
# (Diggs / Deebo / Keenan Allen / Vannett). Advisor lesson L15, now fixed at the source.
board = board[board["team"].notna() & ~board["team"].astype(str).str.upper().isin(["FA", "NAN", ""])].copy()

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

# depth-chart role: each player's rank at his position WITHIN his own team by projection (BUF WR1,
# DET WR2, DET RB1 …). The situational role signal the advisor reads (L14) — WR1 = locked targets,
# WR2/WR3 competes with the alpha + a pass-catching RB1. Canonical here so app + advisor agree.
board["team_role"] = board["position"] + (
    board.groupby(["team", "position"])["total_points"]
    .rank(ascending=False, method="first").astype(int).astype(str))
# role_lead: how CLEARLY he leads his position room = his projection minus the best OTHER player at his
# position on his team (positive = the clear alpha, ~0 = a coin-flip WR1/committee, negative = behind
# the alpha by that much). The advisor scales its role preference by this so a 2-point WR1/WR2 tie
# (Burden vs Odunze) doesn't get the same weight as a real alpha (DJ Moore leads his WR2 by 25).
_g = board.groupby(["team", "position"])["total_points"]
_top1 = _g.transform("max")
_top2 = _g.transform(lambda s: s.sort_values(ascending=False).iloc[1] if len(s) > 1 else s.iloc[0])
board["role_lead"] = (board["total_points"] - _top2.where(board["total_points"] >= _top1, _top1)).round(1)

# team passing ENVIRONMENT: a WR1's locked role only matters if the offense throws valuable targets.
# role_env_ok = the team is above-median in scoring (vegas implied total) OR in pass volume (its skill
# players' 2025 targets). Fails only for a bad AND run-heavy offense (below median in BOTH), where the
# WR1-vs-WR2 distinction barely matters — the advisor applies its role preference only when this is true.
_tv = board.groupby("team")["team_implied_total"].first()
_tp = (board[board["position"].isin(["WR", "TE", "RB"])].groupby("team")["targets_2025"].sum()
       .reindex(_tv.index).fillna(0.0))
_env_ok = (_tv >= _tv.median()) | (_tp >= _tp.median())
board["role_env_ok"] = board["team"].map(_env_ok).fillna(False)

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

# role/opportunity = xPPG percentile within position (WR/TE/RB). xPPG (expected fantasy points per
# game from 2024-25 opportunity, from ff_opportunity) is a MORE COMPLETE role signal than target
# share alone: it captures RB rushing + goal-line work target share misses, and it's points-
# denominated. Falls back to best-demonstrated target share where there's no xPPG (rookies / <8
# games), so proven alphas (Nabers' 2024) and no-history players still get a fair read. QB/K neutral.
# Vegas team environment still scales UPSIDE (ceiling), not the role signal, so a mediocre offense
# can't tank an elite workhorse (e.g. Bijan on ATL) — his VOLS/ADP/ECR/floor still anchor him.
_rec = board["position"].isin(["WR", "TE", "RB"])
xppg_pct = board["xppg"].where(_rec).groupby(board["position"]).rank(pct=True)
ts_best = board[["target_share_2024", "target_share_2025"]].max(axis=1).where(_rec)
ts_pct = ts_best.groupby(board["position"]).rank(pct=True)
role_pct = xppg_pct.fillna(ts_pct).fillna(0.5)   # xPPG first, target-share fallback, then neutral
# team-changers have a STALE opportunity profile (xPPG/target share describe the OLD team). For them,
# use their 2026 projection (VOLS) percentile as the role signal instead — it already prices the new
# situation (better or worse), so we neither over-dock a guy who left an elite offense (A.J. Brown ->
# NE) nor over-hold one who upgraded. Forward-looking and spreads players out (no artificial ties).
if "switched_team" in board.columns:
    vols_pct = board["vols"].where(_rec).groupby(board["position"]).rank(pct=True)
    switched = board["switched_team"].fillna(False).astype(bool) & vols_pct.notna()
    role_pct = role_pct.mask(switched, vols_pct)
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

# consensus sanity check: a NON-rookie whose projection ranks him FAR better than expert consensus is a
# likely projection outlier — pull his composite toward ECR so he can't look draftable (John Metchie).
proj_gap = board["ecr_rank"] - board["overall_rank"]
outlier = proj_gap.notna() & (proj_gap > CONSENSUS_GAP) & ~is_rook
board["proj_outlier"] = outlier
comp = comp.mask(outlier, CONSENSUS_ECR * ecr_r + (1 - CONSENSUS_ECR) * comp)
board["rank_composite"] = comp.rank(method="min").astype(int)

# 5. value vs market (round: adp_rank is now ESPN's decimal ADP, so keep the gap a clean integer)
board["value_gap"] = (board["adp_rank"] - board["overall_rank"]).round().astype("Int64")
in_pool = (board["adp_rank"] <= DRAFTABLE) & (board["overall_rank"] <= DRAFTABLE)
board["market"] = ""
board.loc[in_pool, "market"] = "fair"
# VALUE only for players actually projected to START (p_startable >= 0.40): a "steal" who won't be
# startable (e.g. John Metchie, p_start 0.28) is cheap because he's BAD, not underpriced — a false
# signal the advisor latched onto (L1). Uses p_startable, not VOLS, so it keeps near-replacement but
# viable starters (compressed-VOLS QBs like Lawrence 0.46) and only strips true non-starters.
board.loc[in_pool & (board["value_gap"] >= 12) & (board["p_startable"] >= 0.40), "market"] = "VALUE"
board.loc[in_pool & (board["value_gap"] <= -12), "market"] = "REACH"

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
        "xppg", "xppg_diff", "regression", "switched_team",   # xPPG lens (load_ff_opportunity)
        # situational fields the AI advisor reasons over (not shown in the board table)
        "team", "team_role", "role_lead", "role_env_ok", "proj_outlier", "team_implied_total", "age", "bye_week", "target_share_2025", "snap_share_2025",
        "ecr_tier", "is_rookie", "draft_pick",
        "espn_id"]   # for live ESPN draft sync (maps ESPN pick playerId -> our player)
board[cols].to_csv("value_board.csv", index=False)
board.round(3).to_csv("app_data.csv", index=False)
board.round(3).to_json("app_data.json", orient="records", indent=2)

print(f"{len(board)} players. Top 15 by 'Everything' (composite):")
show = ["rank_composite", "overall_rank", "full_name", "pos_label", "p_startable", "p_elite"]
print(board.sort_values("rank_composite").head(15)[show].to_string(index=False))
print("\nposition mix in composite top 40:", board.sort_values("rank_composite").head(40)["position"].value_counts().to_dict())
