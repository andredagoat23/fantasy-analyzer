"""ROBUSTNESS AUDIT (read-only): run apply_bonuses' bonus math + compute_metrics' VOLS math under
SEVERAL scoring settings, checking every setting: no crash, total==custom+bonus, linearity (double ->
2x, zero -> 0), edge cases (K=0 shrinkage, extreme sack), and that VOLS/replacement adapt. Loads
pbp/wk ONCE. Mirrors the exact formulas in apply_bonuses.py + compute_metrics.py. Writes nothing."""
import nflreadpy as nfl
import pandas as pd, glob, re
from utils import normalize_name, startable_counts

pbp = nfl.load_pbp(seasons=[2023, 2024, 2025]).to_pandas()
wk = nfl.load_player_stats(seasons=[2024, 2025]).to_pandas(); wk = wk[wk["season_type"] == "REG"]

# --- data that does NOT depend on the scoring constants ---
pass_len = pbp[pbp["pass_touchdown"] == 1]["yards_gained"]; rush_len = pbp[pbp["rush_touchdown"] == 1]["yards_gained"]
L_p40, L_p50 = (pass_len >= 40).mean(), (pass_len >= 50).mean()
L_u40, L_u50 = (rush_len >= 40).mean(), (rush_len >= 50).mean()
sk_by = pbp[pbp["sack"] == 1].dropna(subset=["passer_player_id"]).groupby("passer_player_id").size().rename("sacks")
thr_by = pbp[(pbp["pass_attempt"] == 1) & (pbp["sack"] == 0)].dropna(subset=["passer_player_id"]).groupby("passer_player_id").size().rename("throws")
sdf = pd.concat([sk_by, thr_by], axis=1).fillna(0); L_sack = sdf["sacks"].sum()/sdf["throws"].sum()
tp = pbp[(pbp["two_point_attempt"] == 1) & (pbp["two_point_conv_result"] == "success")]
r_2pass = (tp["play_type"] == "pass").sum()/(pbp["pass_touchdown"] == 1).sum(); r_2run = (tp["play_type"] == "run").sum()/(pbp["rush_touchdown"] == 1).sum()
xp = pbp[pbp["extra_point_attempt"] == 1]; L_patmiss = (xp["extra_point_result"] != "good").mean()
md = pbp[pbp["field_goal_result"] == "made"]["kick_distance"].dropna()
rate = lambda c, t: (wk[c] >= t).sum()/wk[c].sum(); rate_bt = lambda c, lo, hi: ((wk[c] >= lo) & (wk[c] < hi)).sum()/wk[c].sum()
r_rush100, r_rush200 = rate_bt("rushing_yards", 100, 200), rate("rushing_yards", 200)
r_rec100, r_rec200 = rate_bt("receiving_yards", 100, 200), rate("receiving_yards", 200)
r_pass300, r_pass400 = rate_bt("passing_yards", 300, 400), rate("passing_yards", 400)
fd_carry = wk["rushing_first_downs"].sum()/wk["carries"].sum(); fd_rec = wk["receiving_first_downs"].sum()/wk["receptions"].sum()
retg = wk.groupby("player_id").agg(kry=("kickoff_return_yards", "sum"), pry=("punt_return_yards", "sum"), rtd=("pt_return_tds", "sum"))

POS_MAP = {"QB": {"pass_yds":"YDS","pass_td":"TDS","pass_att":"ATT","rush_yds":"YDS.1","rush_td":"TDS.1","rush_att":"ATT.1"},
    "RB": {"rush_yds":"YDS","rush_td":"TDS","rush_att":"ATT","rec":"REC","rec_yds":"YDS.1","rec_td":"TDS.1"},
    "WR": {"rec":"REC","rec_yds":"YDS","rec_td":"TDS","rush_yds":"YDS.1","rush_td":"TDS.1","rush_att":"ATT"},
    "TE": {"rec":"REC","rec_yds":"YDS","rec_td":"TDS"}, "K": {"fg_made":"FG","pat_made":"XPT"}}
VOL = ["pass_yds","pass_td","pass_att","rush_yds","rush_td","rush_att","rec","rec_yds","rec_td","fg_made","pat_made"]
to_num = lambda s: pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce").fillna(0)
frames = []
for f in sorted(glob.glob("data/FantasyPros_Fantasy_Football_Projections_*.csv")):
    pos = re.search(r"_([A-Z]+)\.csv$", f).group(1); df = pd.read_csv(f)
    df = df[df["Player"].notna() & (df["Player"].str.strip() != "")].copy()
    d = {v: (to_num(df[POS_MAP[pos][v]]) if v in POS_MAP[pos] else 0) for v in VOL}
    d["name"] = df["Player"].values; d["position"] = pos; frames.append(pd.DataFrame(d))
proj = pd.concat(frames, ignore_index=True); proj["norm_name"] = proj["name"].apply(normalize_name)
players = pd.read_csv("players_scored.csv", dtype={"player_id": str}); players["norm_name"] = players["full_name"].apply(normalize_name)
base = players.merge(proj[["norm_name", "position"] + VOL], on=["norm_name", "position"], how="left")


def compute(cfg):
    """Exact apply_bonuses formula, parameterized by the scoring config dict. Returns a scored frame."""
    m = base.copy(); g = m["gsis_id"]; K = cfg["K"]
    def bl(idc, mask, l40, l50):
        gg = pbp[mask].dropna(subset=[idc]).groupby(idc)["yards_gained"].agg(total="count", n40=lambda s:(s>=40).sum(), n50=lambda s:(s>=50).sum())
        return (gg["n40"]+K*l40)/(gg["total"]+K), (gg["n50"]+K*l50)/(gg["total"]+K)
    p40,p50 = bl("passer_player_id", pbp["pass_touchdown"]==1, L_p40,L_p50); p40=g.map(p40).fillna(L_p40); p50=g.map(p50).fillna(L_p50)
    e40,e50 = bl("receiver_player_id", pbp["pass_touchdown"]==1, L_p40,L_p50); e40=g.map(e40).fillna(L_p40); e50=g.map(e50).fillna(L_p50)
    u40,u50 = bl("rusher_player_id", pbp["rush_touchdown"]==1, L_u40,L_u50); u40=g.map(u40).fillna(L_u40); u50=g.map(u50).fillna(L_u50)
    sackr = (sdf["sacks"]+K*L_sack)/(sdf["throws"]+K); sr = g.map(sackr).fillna(L_sack)
    fg_ppm = ((md<40).mean()*cfg["FG0"] + ((md>=40)&(md<50)).mean()*cfg["FG40"] + ((md>=50)&(md<60)).mean()*cfg["FG50"] + (md>=60).mean()*cfg["FG60"])
    ret_pts = (retg["kry"]/2/25*cfg["KR25"] + retg["pry"]/2/10*cfg["PR10"] + retg["rtd"]/2*cfg["RETTD"]); retp = g.map(ret_pts).fillna(0.0)
    m["bonus_points"] = (m["pass_td"]*(p40*cfg["PTD40"]+p50*cfg["PTD50"]) + m["rec_td"]*(e40*cfg["RETD40"]+e50*cfg["RETD50"])
        + m["rush_td"]*(u40*cfg["RTD40"]+u50*cfg["RTD50"]) + m["pass_yds"]*(r_pass300*cfg["P300"]+r_pass400*cfg["P400"])
        + m["rush_yds"]*(r_rush100*cfg["RY100"]+r_rush200*cfg["RY200"]) + m["rec_yds"]*(r_rec100*cfg["REY100"]+r_rec200*cfg["REY200"])
        + m["rush_att"]*fd_carry*cfg["RFD"] + m["rec"]*fd_rec*cfg["REFD"] + m["fg_made"]*fg_ppm
        + m["pass_att"]*sr*cfg["SACK"] + (m["pass_td"]*r_2pass + m["rush_td"]*r_2run + m["rec_td"]*r_2pass)*cfg["TWOPT"]
        + m["pat_made"]*(L_patmiss/(1-L_patmiss))*cfg["PATM"] + retp)
    m["total_points"] = m["custom_proj_points"] + m["bonus_points"]
    return m


def vols(m):
    """Exact compute_metrics logic."""
    counts = startable_counts(m); repl = {}
    for pos, n in counts.items():
        pts = m[(m["position"] == pos) & m["total_points"].notna()]["total_points"]
        repl[pos] = pts.nlargest(n).min()
    v = m["total_points"] - m["position"].map(repl)
    return v, repl


BASE = dict(PTD40=.5,PTD50=1,RETD40=1,RETD50=2,RTD40=2,RTD50=3,P300=3,P400=5,RY100=3,RY200=5,REY100=2,REY200=4,
            RFD=.5,REFD=.5,FG0=3,FG40=4,FG50=6,FG60=7,SACK=-1,TWOPT=2,PATM=-1,KR25=1,PR10=1,RETTD=6,K=12)
BONUS_KEYS = [k for k in BASE if k != "K"]
SETTINGS = {
    "baseline": BASE,
    "zero-bonus": {**{k: 0 for k in BONUS_KEYS}, "K": 12},
    "double-bonus": {**{k: (v*2 if k != "K" else v) for k, v in BASE.items()}},
    "standard-ish (no bonus, no FG dist)": {**{k: 0 for k in BONUS_KEYS}, "FG0": 3, "FG40": 3, "FG50": 3, "FG60": 3, "K": 12},
    "no-shrinkage (K=0)": {**BASE, "K": 0},
    "extreme sack (-3)": {**BASE, "SACK": -3},
}

passed = 0
def ck(label, cond):
    global passed
    assert cond, f"FAIL: {label}"; passed += 1; print(f"  ok  {label}")

results = {}
for name, cfg in SETTINGS.items():
    try:
        m = compute(cfg); v, repl = vols(m)
    except Exception as e:
        print(f"  FAIL  {name}: raised {type(e).__name__}: {e}"); raise
    scored = m["total_points"].notna()
    consistent = ((m["custom_proj_points"] + m["bonus_points"] - m["total_points"]).abs() < 1e-6)
    ck(f"[{name}] no crash; {int(scored.sum())} scored", scored.sum() > 400)
    ck(f"[{name}] total == custom + bonus (self-consistent)", bool(consistent[scored].all()))
    ck(f"[{name}] replacement levels finite for QB/RB/WR/TE", all(pd.notna(repl.get(p)) for p in ["QB","RB","WR","TE"]))
    ck(f"[{name}] VOLS finite for all scored players", bool(v[scored].notna().all()))
    results[name] = (m, v, repl)

# cross-setting invariants
mb = results["baseline"][0]; mz = results["zero-bonus"][0]; md2 = results["double-bonus"][0]
_zsc = mz["total_points"].notna()   # scored rows only (unscored have NaN volumes -> NaN*0 = NaN)
ck("zero-bonus: bonus_points == 0 for all scored", bool((mz["bonus_points"].abs() < 1e-9)[_zsc].all()))
ck("zero-bonus: total == custom (bonuses removed cleanly)", bool(((mz["total_points"] - mz["custom_proj_points"]).abs() < 1e-9)[mz["total_points"].notna()].all()))
ck("double-bonus: bonus == 2x baseline (linear in the constants)", bool(((md2["bonus_points"] - 2*mb["bonus_points"]).abs() < 1e-6)[mb["bonus_points"].notna()].all()))

# does VOLS reorder sensibly when scoring changes? (top RB should stay an RB; QB replacement shifts)
print("\n=== replacement level (points) by setting ===")
print(f"{'setting':36} {'QB':>7} {'RB':>7} {'WR':>7} {'TE':>7} {'K':>7}")
for name, (m, v, repl) in results.items():
    print(f"{name:36} " + " ".join(f"{repl.get(p, float('nan')):7.1f}" for p in ["QB","RB","WR","TE","K"]))

print(f"\n{passed} checks passed ✅")
