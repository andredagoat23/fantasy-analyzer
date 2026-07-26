import nflreadpy as nfl
import pandas as pd
import glob
import re
from utils import normalize_name
# Bucket-2 values live in scoring_config.py (single source of truth; see it for the tiered-vs-cumulative
# note + the tier/threshold meaning of each constant). Edit values THERE, not here.
from scoring_config import (PTD40, PTD50, RETD40, RETD50, RTD40, RTD50, P300, P400, RY100, RY200,
                            REY100, REY200, RFD, REFD, FG0, FG40, FG50, FG60, SACK, TWOPT, PATM,
                            KR25, PR10, RETTD, K)

K = max(int(K), 1)           # shrinkage MUST be > 0 (K=0 -> 0/0 for players with no historical TDs)

# ============ 1. league rates + per-player long-TD rates (2023-25) ============
pbp = nfl.load_pbp(seasons=[2023, 2024, 2025]).to_pandas()
pass_len = pbp[pbp["pass_touchdown"] == 1]["yards_gained"]
rush_len = pbp[pbp["rush_touchdown"] == 1]["yards_gained"]
L_pass40, L_pass50 = (pass_len >= 40).mean(), (pass_len >= 50).mean()
L_rush40, L_rush50 = (rush_len >= 40).mean(), (rush_len >= 50).mean()

def blended(id_col, mask, l40, l50):
    """Per-player fraction of TDs going 40+/50+, shrunk toward the league by K."""
    g = pbp[mask].dropna(subset=[id_col]).groupby(id_col)["yards_gained"].agg(
        total="count", n40=lambda s: (s >= 40).sum(), n50=lambda s: (s >= 50).sum())
    return (g["n40"] + K*l40)/(g["total"]+K), (g["n50"] + K*l50)/(g["total"]+K)

pass40, pass50 = blended("passer_player_id", pbp["pass_touchdown"] == 1, L_pass40, L_pass50)
rec40, rec50 = blended("receiver_player_id", pbp["pass_touchdown"] == 1, L_pass40, L_pass50)
rush40, rush50 = blended("rusher_player_id", pbp["rush_touchdown"] == 1, L_rush40, L_rush50)

md = pbp[pbp["field_goal_result"] == "made"]["kick_distance"].dropna()
fg_ppm = ((md < 40).mean()*FG0 + ((md >= 40) & (md < 50)).mean()*FG40
          + ((md >= 50) & (md < 60)).mean()*FG50 + (md >= 60).mean()*FG60)

# QB sack rate — sacks aren't in the FP projections, so estimate per-QB sacks/throw shrunk to league.
# (throws = pass attempts that weren't sacks; projected sacks = proj pass ATT x this rate.)
sk_by = pbp[pbp["sack"] == 1].dropna(subset=["passer_player_id"]).groupby("passer_player_id").size().rename("sacks")
thr_by = (pbp[(pbp["pass_attempt"] == 1) & (pbp["sack"] == 0)].dropna(subset=["passer_player_id"])
          .groupby("passer_player_id").size().rename("throws"))
sdf = pd.concat([sk_by, thr_by], axis=1).fillna(0)
L_sack = sdf["sacks"].sum() / sdf["throws"].sum()
sack_rate = (sdf["sacks"] + K*L_sack) / (sdf["throws"] + K)

# 2pt conversion league rates, tied to TD volume (too rare/situational for per-player shrinkage).
# A successful 2pt PASS scores BOTH the passer and the receiver, so per-rec-TD rate ~= per-pass-TD rate.
tp = pbp[(pbp["two_point_attempt"] == 1) & (pbp["two_point_conv_result"] == "success")]
r_2pass = (tp["play_type"] == "pass").sum() / (pbp["pass_touchdown"] == 1).sum()   # per pass/rec TD
r_2run = (tp["play_type"] == "run").sum() / (pbp["rush_touchdown"] == 1).sum()      # per rush TD

# PAT miss rate (league) — projected PATs made come from the K file (XPT); missed ~= made x miss/(1-miss)
xp = pbp[pbp["extra_point_attempt"] == 1]
L_patmiss = (xp["extra_point_result"] != "good").mean()

wk = nfl.load_player_stats(seasons=[2024, 2025]).to_pandas()
wk = wk[wk["season_type"] == "REG"]
rate = lambda col, thr: (wk[col] >= thr).sum() / wk[col].sum()
rate_bt = lambda col, lo, hi: ((wk[col] >= lo) & (wk[col] < hi)).sum() / wk[col].sum()   # tiered range
r_rush100, r_rush200 = rate_bt("rushing_yards", 100, 200), rate("rushing_yards", 200)
r_rec100, r_rec200 = rate_bt("receiving_yards", 100, 200), rate("receiving_yards", 200)
r_pass300, r_pass400 = rate_bt("passing_yards", 300, 400), rate("passing_yards", 400)
fd_carry = wk["rushing_first_downs"].sum() / wk["carries"].sum()
fd_rec = wk["receiving_first_downs"].sum() / wk["receptions"].sum()

# return production — no return projections exist, so estimate from 2024-25 actuals (/2 = per-season).
# BACKWARD-LOOKING by nature: credits a past returner, misses a new/rookie one. Labeled as such.
retg = wk.groupby("player_id").agg(kry=("kickoff_return_yards", "sum"),
                                   pry=("punt_return_yards", "sum"), rtd=("pt_return_tds", "sum"))
ret_pts = (retg["kry"]/2/25*KR25 + retg["pry"]/2/10*PR10 + retg["rtd"]/2*RETTD)   # Series keyed by gsis

# ============ 2. projected volumes from the projection files ============
POS_MAP = {
    "QB": {"pass_yds":"YDS","pass_td":"TDS","pass_att":"ATT","rush_yds":"YDS.1","rush_td":"TDS.1","rush_att":"ATT.1"},
    "RB": {"rush_yds":"YDS","rush_td":"TDS","rush_att":"ATT","rec":"REC","rec_yds":"YDS.1","rec_td":"TDS.1"},
    "WR": {"rec":"REC","rec_yds":"YDS","rec_td":"TDS","rush_yds":"YDS.1","rush_td":"TDS.1","rush_att":"ATT"},
    "TE": {"rec":"REC","rec_yds":"YDS","rec_td":"TDS"},
    "K":  {"fg_made":"FG","pat_made":"XPT"},
}
VOL = ["pass_yds","pass_td","pass_att","rush_yds","rush_td","rush_att","rec","rec_yds","rec_td","fg_made","pat_made"]
to_num = lambda s: pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce").fillna(0)

frames = []
for f in sorted(glob.glob("data/FantasyPros_Fantasy_Football_Projections_*.csv")):
    pos = re.search(r"_([A-Z]+)\.csv$", f).group(1)
    df = pd.read_csv(f)
    df = df[df["Player"].notna() & (df["Player"].str.strip() != "")].copy()
    d = {v: (to_num(df[POS_MAP[pos][v]]) if v in POS_MAP[pos] else 0) for v in VOL}
    d["name"] = df["Player"].values
    d["position"] = pos
    frames.append(pd.DataFrame(d))
proj = pd.concat(frames, ignore_index=True)
proj["norm_name"] = proj["name"].apply(normalize_name)

# ============ 3. attach volumes + each player's blended TD rates ============
players = pd.read_csv("players_scored.csv", dtype={"player_id": str})
players["norm_name"] = players["full_name"].apply(normalize_name)
m = players.merge(proj[["norm_name", "position"] + VOL], on=["norm_name", "position"], how="left")

g = m["gsis_id"]
p40 = g.map(pass40).fillna(L_pass40); p50 = g.map(pass50).fillna(L_pass50)
e40 = g.map(rec40).fillna(L_pass40);  e50 = g.map(rec50).fillna(L_pass50)
u40 = g.map(rush40).fillna(L_rush40); u50 = g.map(rush50).fillna(L_rush50)
sr = g.map(sack_rate).fillna(L_sack)          # per-QB sacks/throw
retp = g.map(ret_pts).fillna(0.0)             # backward-looking return points (0 for non-returners)

# ============ 4. expected bonus = rate x projected volume ============
# Long-TD bonuses are CUMULATIVE (40+ and 50+ both apply). Big-game bonuses are TIERED (r_*300/100/rec
# are the 300-399/100-199 range rates, r_*400/200 the top tier) so a 400+/200+ game scores one tier only.
m["bonus_points"] = (
    m["pass_td"] * (p40*PTD40 + p50*PTD50)
    + m["rec_td"] * (e40*RETD40 + e50*RETD50)
    + m["rush_td"] * (u40*RTD40 + u50*RTD50)
    + m["pass_yds"] * (r_pass300*P300 + r_pass400*P400)
    + m["rush_yds"] * (r_rush100*RY100 + r_rush200*RY200)
    + m["rec_yds"] * (r_rec100*REY100 + r_rec200*REY200)
    + m["rush_att"] * fd_carry * RFD
    + m["rec"] * fd_rec * REFD
    + m["fg_made"] * fg_ppm
    + m["pass_att"] * sr * SACK                                   # QB sacks (estimated)
    + (m["pass_td"]*r_2pass + m["rush_td"]*r_2run + m["rec_td"]*r_2pass) * TWOPT   # 2pt conversions
    + m["pat_made"] * (L_patmiss/(1-L_patmiss)) * PATM            # PAT missed
    + retp                                                        # return yds + return TDs
)
m["total_points"] = m["custom_proj_points"] + m["bonus_points"]
m = m.drop(columns=["norm_name"] + VOL)
m.to_csv("players_final.csv", index=False)

print(f"{m['bonus_points'].notna().sum()} players scored -> players_final.csv")
print(m.nlargest(8, "total_points")[["full_name", "position", "custom_proj_points", "bonus_points", "total_points"]].to_string(index=False))
