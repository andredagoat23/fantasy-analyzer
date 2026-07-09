import nflreadpy as nfl
import pandas as pd
import glob
import re
from utils import normalize_name

# ============ your league's Bucket-2 bonus values (edit here) ============
PTD40, PTD50 = 0.5, 1        # 40+/50+ passing TD
RETD40, RETD50 = 1, 2        # 40+/50+ receiving TD
RTD40, RTD50 = 2, 3          # 40+/50+ rushing TD
P300, P400 = 3, 5            # 300/400 passing game
RY100, RY200 = 3, 5          # 100/200 rushing game
REY100, REY200 = 2, 4        # 100/200 receiving game
RFD = REFD = 0.5             # rushing / receiving first down
FG0, FG40, FG50, FG60 = 3, 4, 6, 7   # FG made by distance bucket
K = 12                       # shrinkage: higher = trust the league average more

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

wk = nfl.load_player_stats(seasons=[2024, 2025]).to_pandas()
wk = wk[wk["season_type"] == "REG"]
rate = lambda col, thr: (wk[col] >= thr).sum() / wk[col].sum()
r_rush100, r_rush200 = rate("rushing_yards", 100), rate("rushing_yards", 200)
r_rec100, r_rec200 = rate("receiving_yards", 100), rate("receiving_yards", 200)
r_pass300, r_pass400 = rate("passing_yards", 300), rate("passing_yards", 400)
fd_carry = wk["rushing_first_downs"].sum() / wk["carries"].sum()
fd_rec = wk["receiving_first_downs"].sum() / wk["receptions"].sum()

# ============ 2. projected volumes from the projection files ============
POS_MAP = {
    "QB": {"pass_yds":"YDS","pass_td":"TDS","rush_yds":"YDS.1","rush_td":"TDS.1","rush_att":"ATT.1"},
    "RB": {"rush_yds":"YDS","rush_td":"TDS","rush_att":"ATT","rec":"REC","rec_yds":"YDS.1","rec_td":"TDS.1"},
    "WR": {"rec":"REC","rec_yds":"YDS","rec_td":"TDS","rush_yds":"YDS.1","rush_td":"TDS.1","rush_att":"ATT"},
    "TE": {"rec":"REC","rec_yds":"YDS","rec_td":"TDS"},
    "K":  {"fg_made":"FG"},
}
VOL = ["pass_yds","pass_td","rush_yds","rush_td","rush_att","rec","rec_yds","rec_td","fg_made"]
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

# ============ 4. expected bonus = rate x projected volume ============
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
)
m["total_points"] = m["custom_proj_points"] + m["bonus_points"]
m = m.drop(columns=["norm_name"] + VOL)
m.to_csv("players_final.csv", index=False)

print(f"{m['bonus_points'].notna().sum()} players scored -> players_final.csv")
print(m.nlargest(8, "total_points")[["full_name", "position", "custom_proj_points", "bonus_points", "total_points"]].to_string(index=False))
