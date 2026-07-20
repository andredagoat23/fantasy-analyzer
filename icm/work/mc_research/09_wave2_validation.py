# Wave-2 candidate validation: under the WAVE-1 machinery, do these subgroups still show
# calibration gaps (realized boom/bust vs simulated), and does a minimal tilt close them
# without breaking global calibration?
# Candidates: (a) team-changers QB/RB/TE, (b) WR age 30+, (c) high prev-season CV,
#             (d) late-season target-share surge (WR/TE).
import pandas as pd
import numpy as np

rng = np.random.default_rng(0)
OUT = "icm/work/mc_research"
N_SIMS = 4000
GAMES_BY_SEASON = {y: (16 if y <= 2020 else 17) for y in range(2014, 2026)}

SIGMA_ANCHORS = {
    "QB": [(3, 0.235), (9, 0.238), (18, 0.238), (32, 0.294), (50, 0.45)],
    "RB": [(3, 0.334), (9, 0.334), (18, 0.334), (32, 0.398), (50, 0.491)],
    "WR": [(3, 0.240), (9, 0.240), (18, 0.246), (32, 0.287), (50, 0.351)],
    "TE": [(3, 0.305), (9, 0.346), (18, 0.364), (32, 0.497), (50, 0.504)],
}
AVAIL_PRIOR = {"QB": 0.845, "RB": 0.817, "WR": 0.841, "TE": 0.828}
P_MAJOR_POS = {"QB": 0.103, "RB": 0.108, "WR": 0.089, "TE": 0.071}
AGE_CLIFF = {"QB": 99, "RB": 29, "WR": 29, "TE": 29}
AGE_SLOPE = {"QB": 0.0, "RB": 0.035, "WR": 0.025, "TE": 0.030}
COUPLE, COUPLE_FLOOR = 0.41, 0.55
ROOKIE_SIGMA_MULT = {"QB": 1.5, "RB": 1.4, "WR": 1.0, "TE": 1.1}

def sigma_for(pos, rank):
    xs, ys = zip(*SIGMA_ANCHORS[pos])
    return float(np.interp(rank, xs, ys))

def simulate(sp, G, mean_tilt=None, sigma_mult=None):
    """Wave-1 machinery over one season's pool; optional per-player tilt/sigma multipliers."""
    n = len(sp)
    proj = sp["exp_pts"].values
    pos = sp["position"].values
    rank = sp["exp_pos_rank"].values
    age = sp["age"].values
    rookie = sp["rookie"].values
    av = np.array([AVAIL_PRIOR[p] for p in pos])
    pen = np.array([max(0.0, (a - AGE_CLIFF[p])) * AGE_SLOPE[p] if not np.isnan(a) else 0.0
                    for a, p in zip(age, pos)])
    av = np.clip(av - pen, 0.5, 1.0)
    p_major = np.clip(np.array([P_MAJOR_POS[p] for p in pos]) + 0.5 * (0.84 - av), 0.05, 0.18)
    sig = np.array([sigma_for(p, r) * (ROOKIE_SIGMA_MULT[p] if rk else 1.0)
                    for p, r, rk in zip(pos, rank, rookie)])
    if sigma_mult is not None:
        sig = sig * sigma_mult
    normal_games = np.clip(rng.normal((G * av)[:, None], (1.0 * (1 - av) * G)[:, None], (n, N_SIMS)), 0, G)
    major = rng.random((n, N_SIMS)) < p_major[:, None]
    games = np.where(major, rng.uniform(1, 8, (n, N_SIMS)), normal_games)
    couple = np.clip(1 - COUPLE * (1 - games / G), COUPLE_FLOOR, 1.0)
    M = rng.lognormal((-(sig ** 2) / 2)[:, None], sig[:, None], (n, N_SIMS))
    raw = games * couple * M
    sims = raw * (proj / raw.mean(1))[:, None]
    if mean_tilt is not None:
        sims = sims * mean_tilt[:, None]
    return sims

# ---------- panel + subgroup features ----------
sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")
wk = pd.read_parquet(f"{OUT}/weekly.parquet")
pool = sea[sea["exp_pts"].notna() & (sea["exp_pos_rank"] <= 60) & sea["total_pts"].notna()].copy()
pool["rookie"] = pool["years_exp"].fillna(1) == 0
pool["team_changed"] = (pool["team_last"] != pool["prev_team_last"]) & pool["prev_team_last"].notna()
pool["wr30"] = (pool["position"] == "WR") & (pool["age"] >= 30)
med_cv = pool.groupby("position")["prev_cv"].transform("median")
pool["cv_rel"] = pool["prev_cv"] / med_cv
# late-usage surge: last-4-played-weeks target share minus season avg, PRIOR season
wk_r = wk[wk["position"].isin(["WR", "TE", "RB"])].sort_values(["player_id", "season", "week"])
l4 = (wk_r.groupby(["player_id", "season"])
      .apply(lambda g: g.tail(4)["target_share"].mean() - g["target_share"].mean(), include_groups=False)
      .rename("ts_surge").reset_index())
l4["join_season"] = l4["season"] + 1
pool = pool.merge(l4[["player_id", "join_season", "ts_surge"]],
                  left_on=["player_id", "season"], right_on=["player_id", "join_season"], how="left")

# ---------- baseline Wave-1 predictions per player ----------
recs = []
for season, sp in pool.groupby("season"):
    sims = simulate(sp, GAMES_BY_SEASON[season])
    proj = sp["exp_pts"].values
    recs.append(pd.DataFrame({
        "idx": sp.index,
        "pred_boom": (sims >= 1.5 * proj[:, None]).mean(1),
        "pred_bust": (sims <= 0.7 * proj[:, None]).mean(1)}))
pred = pd.concat(recs).set_index("idx")
pool["pred_boom"], pool["pred_bust"] = pred["pred_boom"], pred["pred_bust"]
pool["real_boom"] = pool["mult"] >= 1.5
pool["real_bust"] = pool["mult"] <= 0.7

def gap_report(mask, label):
    d = pool[mask & pool["pred_boom"].notna()]
    if len(d) < 25:
        print(f"  {label:34} n={len(d)} (too thin)")
        return None
    print(f"  {label:34} n={len(d):4}  boom pred {d['pred_boom'].mean():.3f} vs real {d['real_boom'].mean():.3f}"
          f"   bust pred {d['pred_bust'].mean():.3f} vs real {d['real_bust'].mean():.3f}")
    return d

print("=== subgroup calibration gaps under WAVE-1 machinery ===")
print("-- (a) team-changers vs stayers, by position --")
for p in ["QB", "RB", "TE", "WR"]:
    gap_report((pool.position == p) & pool.team_changed, f"{p} changed")
    gap_report((pool.position == p) & ~pool.team_changed & pool.prev_team_last.notna(), f"{p} stayed")
print("-- (b) WR age 30+ --")
gap_report(pool.wr30, "WR 30+")
gap_report((pool.position == "WR") & (pool.age < 30), "WR <30")
print("-- (c) prev-season CV terciles (vets with history) --")
cvd = pool[pool["cv_rel"].notna()]
q1, q3 = cvd["cv_rel"].quantile(1/3), cvd["cv_rel"].quantile(2/3)
gap_report(pool["cv_rel"] <= q1, "low prev CV (steady)")
gap_report(pool["cv_rel"] >= q3, "high prev CV (volatile)")
print("-- (d) late-usage surge terciles (WR/TE) --")
sd = pool[pool["ts_surge"].notna() & pool["position"].isin(["WR", "TE"])]
s1, s3 = sd["ts_surge"].quantile(1/3), sd["ts_surge"].quantile(2/3)
gap_report(pool.index.isin(sd[sd["ts_surge"] >= s3].index), "surge top tercile")
gap_report(pool.index.isin(sd[sd["ts_surge"] <= s1].index), "surge bottom tercile")

# ================= fit-and-verify: apply candidate adjustments, recheck =================
# Adjustments under test (survivors only, minimal form):
#   team-change (non-rookie): QB tilt .97 sigma x1.25 | RB tilt .94 | TE tilt .95 sigma x1.10
#   stable RB/TE vets (no team change): sigma x0.90 / x0.92 (safer than position-wide machinery)
#   WR age 30+: sigma x0.70 (known quantities: fewer booms AND fewer busts)
#   CV blend: sigma x clip(1 + 0.20*(cv_rel - 1), 0.85, 1.25)
def wave2_adjust(sp):
    tilt = np.ones(len(sp))
    smult = np.ones(len(sp))
    pos = sp["position"].values
    chg = sp["team_changed"].values & ~sp["rookie"].values
    stay = ~sp["team_changed"].values & sp["prev_team_last"].notna().values & ~sp["rookie"].values
    tilt[(pos == "QB") & chg] = 0.97
    smult[(pos == "QB") & chg] = 1.40
    tilt[(pos == "RB") & chg] = 0.94
    tilt[(pos == "TE") & chg] = 0.95
    smult[(pos == "TE") & chg] = 1.15
    smult[(pos == "RB") & stay] *= 0.85
    smult[(pos == "TE") & stay] *= 0.85
    wr30 = (pos == "WR") & (sp["age"].values >= 30)
    smult[wr30] *= 0.70
    tilt[wr30] = 0.98
    cvr = sp["cv_rel"].fillna(1.0).values
    smult *= np.clip(1 + 0.30 * (cvr - 1), 0.80, 1.30)
    return tilt, smult

recs2, cov2 = [], []
for season, sp in pool.groupby("season"):
    tilt, smult = wave2_adjust(sp)
    sims = simulate(sp, GAMES_BY_SEASON[season], mean_tilt=tilt, sigma_mult=smult)
    proj = sp["exp_pts"].values
    p20 = np.percentile(sims, 20, 1); p80 = np.percentile(sims, 80, 1)
    actual = sp["total_pts"].values
    cov2.extend(((actual >= p20) & (actual <= p80)).tolist())
    recs2.append(pd.DataFrame({
        "idx": sp.index,
        "pred_boom": (sims >= 1.5 * proj[:, None]).mean(1),
        "pred_bust": (sims <= 0.7 * proj[:, None]).mean(1)}))
pred2 = pd.concat(recs2).set_index("idx")
pool["pred_boom"], pool["pred_bust"] = pred2["pred_boom"], pred2["pred_bust"]

print(f"\n=== AFTER Wave-2 adjustments ===")
print(f"global 20/80 coverage: {np.mean(cov2):.1%} (target ~60%)   "
      f"global boom pred {pool['pred_boom'].mean():.3f} vs real {pool['real_boom'].mean():.3f}")
print("-- team change --")
for p in ["QB", "RB", "TE", "WR"]:
    gap_report((pool.position == p) & pool.team_changed, f"{p} changed")
    gap_report((pool.position == p) & ~pool.team_changed & pool.prev_team_last.notna(), f"{p} stayed")
print("-- WR 30+ --")
gap_report(pool.wr30, "WR 30+")
print("-- CV terciles --")
gap_report(pool["cv_rel"] <= q1, "low prev CV (steady)")
gap_report(pool["cv_rel"] >= q3, "high prev CV (volatile)")

# ================= Wave-2b: split the RB mover tilt by PROVEN production =================
# User challenge: role-upgrade movers (e.g. Montgomery) shouldn't eat the blanket penalty.
# Data: proven movers (2yr ppg>=10, games>=12) bust 30% / med 1.01 -> NO tilt;
#       unproven movers bust 52% / med 0.64 -> HARSHER tilt than the uniform 0.94.
sea2 = sea.sort_values(["player_id","season"])
g2 = sea2.groupby("player_id")
sea2["pts_2p"] = g2["total_pts"].apply(lambda s: s.shift(1).rolling(2, min_periods=1).sum()).reset_index(level=0, drop=True)
sea2["gms_2p"] = g2["games"].apply(lambda s: s.shift(1).rolling(2, min_periods=1).sum()).reset_index(level=0, drop=True)
pool = pool.merge(sea2[["player_id","season","pts_2p","gms_2p"]], on=["player_id","season"], how="left")
pool["proven2"] = (pool["pts_2p"] / pool["gms_2p"] >= 10) & (pool["gms_2p"] >= 12)

def wave2b_adjust(sp):
    tilt, smult = wave2_adjust(sp)
    pos = sp["position"].values
    chg = sp["team_changed"].values & ~sp["rookie"].values
    proven = sp["proven2"].fillna(False).values
    rb_chg = (pos == "RB") & chg
    tilt[rb_chg & proven] = 1.0                      # proven mover: no penalty (was 0.94)
    tilt[rb_chg & ~proven] = 0.86                    # unproven mover: harsher (real med 0.64)
    smult[rb_chg & ~proven] *= 1.20
    return tilt, smult

recs3, cov3 = [], []
for season, sp in pool.groupby("season"):
    tilt, smult = wave2b_adjust(sp)
    sims = simulate(sp, GAMES_BY_SEASON[season], mean_tilt=tilt, sigma_mult=smult)
    proj = sp["exp_pts"].values
    p20 = np.percentile(sims, 20, 1); p80 = np.percentile(sims, 80, 1)
    cov3.extend(((sp["total_pts"].values >= p20) & (sp["total_pts"].values <= p80)).tolist())
    recs3.append(pd.DataFrame({"idx": sp.index,
        "pred_boom": (sims >= 1.5 * proj[:, None]).mean(1),
        "pred_bust": (sims <= 0.7 * proj[:, None]).mean(1)}))
pred3 = pd.concat(recs3).set_index("idx")
pool["pred_boom"], pool["pred_bust"] = pred3["pred_boom"], pred3["pred_bust"]
print(f"\n=== AFTER Wave-2b (split RB mover tilt) ===")
print(f"global coverage: {np.mean(cov3):.1%}   boom pred {pool['pred_boom'].mean():.3f} vs real {pool['real_boom'].mean():.3f}")
gap_report((pool.position=="RB") & pool.team_changed & pool.proven2, "RB movers PROVEN (2yr ppg>=10)")
gap_report((pool.position=="RB") & pool.team_changed & ~pool.proven2, "RB movers unproven")
gap_report((pool.position=="RB") & ~pool.team_changed & pool.prev_team_last.notna(), "RB stayed (unchanged)")

# ================= Wave-2c: stayed + NEW HEAD COACH tilt (backlog, user go) =================
# Raw research: stayers on new-HC teams beat price (med 1.04, bust 21% vs 24%; QB strongest).
# Historical new-HC flags derived from schedules coach fields (same source as the 2026 list).
import os
os.environ.setdefault("NFLREADPY_CACHE_MODE", "filesystem")
os.environ.setdefault("NFLREADPY_CACHE_DIR", "icm/work/mc_research/.nflcache")
import nflreadpy as nfl
_sch = nfl.load_schedules(seasons=list(range(2013, 2026))).to_pandas()
_sch = _sch[_sch.game_type == "REG"]
_hc = pd.concat([_sch[["season","home_team","home_coach"]].rename(columns={"home_team":"team","home_coach":"coach"}),
                 _sch[["season","away_team","away_coach"]].rename(columns={"away_team":"team","away_coach":"coach"})])
_tc = _hc.groupby(["season","team"])["coach"].agg(lambda s: s.mode().iloc[0]).reset_index().sort_values(["team","season"])
_tc["prev_coach"] = _tc.groupby("team")["coach"].shift(1)
_tc["new_hc"] = _tc["prev_coach"].notna() & (_tc["coach"] != _tc["prev_coach"])
pool = pool.merge(_tc[["season","team","new_hc"]], left_on=["season","team_last"], right_on=["season","team"], how="left")
pool["stayed_flag"] = ~pool["team_changed"] & pool["prev_team_last"].notna() & ~pool["rookie"]
pool["nhc_seg"] = pool["stayed_flag"] & pool["new_hc"].fillna(False) & pool["position"].isin(["QB","RB","WR"])

def wave2c_adjust(sp):
    tilt, smult = wave2b_adjust(sp)
    seg = sp["nhc_seg"].values
    tilt[seg] *= 1.02          # small mean lift (raw med 1.04)
    smult[seg] *= 0.85         # narrower: fewer busts AND fewer booms than machinery predicts
    return tilt, smult

recs4, cov4 = [], []
for season, sp in pool.groupby("season"):
    tilt, smult = wave2c_adjust(sp)
    sims = simulate(sp, GAMES_BY_SEASON[season], mean_tilt=tilt, sigma_mult=smult)
    proj = sp["exp_pts"].values
    p20 = np.percentile(sims, 20, 1); p80 = np.percentile(sims, 80, 1)
    cov4.extend(((sp["total_pts"].values >= p20) & (sp["total_pts"].values <= p80)).tolist())
    recs4.append(pd.DataFrame({"idx": sp.index,
        "pred_boom": (sims >= 1.5 * proj[:, None]).mean(1),
        "pred_bust": (sims <= 0.7 * proj[:, None]).mean(1)}))
pred4 = pd.concat(recs4).set_index("idx")
pool["pred_boom"], pool["pred_bust"] = pred4["pred_boom"], pred4["pred_bust"]
print(f"\n=== AFTER Wave-2c (stayed + new-HC tilt 1.035) — FULL 2014-25 POOL (out-of-sample incl.) ===")
print(f"global coverage: {np.mean(cov4):.1%}   boom pred {pool['pred_boom'].mean():.3f} vs real {pool['real_boom'].mean():.3f}")
gap_report(pool["nhc_seg"], "stayed + new HC (QB/RB/WR)")
gap_report(pool["stayed_flag"] & ~pool["new_hc"].fillna(False), "stayed + same HC")
# era split: the constants were FIT on 2019-25; 2014-18 is true out-of-sample
early = pool[pool.season <= 2018]
late = pool[pool.season >= 2019]
print(f"OOS check — 2014-18 coverage: {np.mean([c for c, s in zip(cov4, pool['season']) if s <= 2018]):.1%} | "
      f"2019-25: {np.mean([c for c, s in zip(cov4, pool['season']) if s >= 2019]):.1%}")
