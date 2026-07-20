# Backtest the PROPOSED Wave-1 machinery on history BEFORE editing the frozen file.
# For each season 2019-2025: treat market-expected points as the projection, simulate every
# ranked player with the new constants, then score calibration against what actually happened:
#   - 20/80 band coverage (target ~60%)
#   - P(mult >= 1.5) predicted vs realized
#   - top-12 / startable odds by preseason tier vs reality
# This file IS the spec for the compute_outcomes.py edit - same formulas, same constants.
import pandas as pd
import numpy as np

rng = np.random.default_rng(0)
OUT = "icm/work/mc_research"
N_SIMS = 5000
GAMES_BY_SEASON = {2019: 16, 2020: 16, 2021: 17, 2022: 17, 2023: 17, 2024: 17, 2025: 17}

# ---- PROPOSED CONSTANTS (Wave 1) ----
SIGMA_ANCHORS = {   # per-game lognormal sigma by preseason positional rank (robust, shrunk, monotone)
    "QB": [(3, 0.235), (9, 0.238), (18, 0.238), (32, 0.294), (50, 0.45)],   # deep-QB clipped (backup artifact)
    "RB": [(3, 0.334), (9, 0.334), (18, 0.334), (32, 0.398), (50, 0.491)],
    "WR": [(3, 0.240), (9, 0.240), (18, 0.246), (32, 0.287), (50, 0.351)],
    "TE": [(3, 0.305), (9, 0.346), (18, 0.364), (32, 0.497), (50, 0.504)],
}
AVAIL_PRIOR = {"QB": 0.845, "RB": 0.817, "WR": 0.841, "TE": 0.828}
P_MAJOR_POS = {"QB": 0.103, "RB": 0.108, "WR": 0.089, "TE": 0.071}
AGE_CLIFF = {"QB": 99, "RB": 29, "WR": 29, "TE": 29}      # QB: no age availability penalty observed
AGE_SLOPE = {"QB": 0.0, "RB": 0.035, "WR": 0.025, "TE": 0.030}
COUPLE = 0.41          # per-game decline per fraction of season missed
COUPLE_FLOOR = 0.55    # floor on the coupling factor
ROOKIE_SIGMA_MULT = {"QB": 1.5, "RB": 1.4, "WR": 1.0, "TE": 1.1}   # rookies wider (WR: no)

def sigma_for(pos, rank):
    xs, ys = zip(*SIGMA_ANCHORS[pos])
    return float(np.interp(rank, xs, ys))

sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")
pool = sea[sea["exp_pts"].notna() & (sea["exp_pos_rank"] <= 60) & sea["total_pts"].notna()].copy()
pool["rookie"] = pool["years_exp"].fillna(1) == 0

cov_hits, boom_pred, boom_real = [], [], []
tier_rows = []
for season, sp in pool.groupby("season"):
    G = GAMES_BY_SEASON[season]
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

    normal_games = np.clip(rng.normal((G * av)[:, None], (1.0 * (1 - av) * G)[:, None], (n, N_SIMS)), 0, G)
    major = rng.random((n, N_SIMS)) < p_major[:, None]
    games = np.where(major, rng.uniform(1, 8, (n, N_SIMS)), normal_games)
    couple = np.clip(1 - COUPLE * (1 - games / G), COUPLE_FLOOR, 1.0)
    M = rng.lognormal((-(sig ** 2) / 2)[:, None], sig[:, None], (n, N_SIMS))
    raw = games * couple * M
    sims = raw * (proj / raw.mean(1))[:, None]        # exact re-centering: E[sims] = projection

    p20 = np.percentile(sims, 20, 1); p80 = np.percentile(sims, 80, 1)
    actual = sp["total_pts"].values
    cov_hits.extend(((actual >= p20) & (actual <= p80)).tolist())
    boom_pred.extend((sims >= 1.5 * proj[:, None]).mean(1).tolist())
    boom_real.extend((actual >= 1.5 * proj).tolist())

    # rank-based odds: joint sim within season x position
    finish = (-sims).argsort(0).argsort(0) + 1
    sdf = pd.DataFrame({"pos": pos, "rank": rank, "actual_rank": sp["pos_rank_total"].values})
    for p in ["QB", "RB", "WR", "TE"]:
        m = pos == p
        if m.sum() < 12:
            continue
        fin_p = (-sims[m]).argsort(0).argsort(0) + 1
        top12 = (fin_p <= 12).mean(1)
        startable = (fin_p <= (30 if p in ("RB", "WR") else 12)).mean(1)
        tier_rows.append(pd.DataFrame({
            "season": season, "pos": p, "rank": rank[m],
            "sim_top12": top12, "sim_start": startable,
            "real_top12": (sdf.loc[m, "actual_rank"] <= 12).values,
            "real_start": (sdf.loc[m, "actual_rank"] <= (30 if p in ("RB", "WR") else 12)).values}))

print(f"=== BACKTEST (proposed Wave-1 constants) on {len(cov_hits)} player-seasons ===")
print(f"20/80 band coverage: {np.mean(cov_hits):.1%}   (target ~60%)")
print(f"P(>=1.5x): predicted {np.mean(boom_pred):.1%}  vs realized {np.mean(boom_real):.1%}")

tiers = pd.concat(tier_rows)
tiers["tier"] = pd.cut(tiers["rank"], [0, 3, 6, 12, 24, 40, 60],
                       labels=["1-3", "4-6", "7-12", "13-24", "25-40", "41-60"])
cal = tiers.groupby(["pos", "tier"], observed=True).agg(
    n=("sim_top12", "size"), sim_top12=("sim_top12", "mean"), real_top12=("real_top12", "mean"),
    sim_start=("sim_start", "mean"), real_start=("real_start", "mean"))
print("\n=== finish-odds calibration: simulated vs real, by preseason tier ===")
print(cal.round(3).to_string())

# also: what the OLD constants would have said (flat ROLE_RISK=.20, old avail machinery)
print("\n=== comparison: OLD MC constants, same backtest ===")
cov_o, boom_po = [], []
for season, sp in pool.groupby("season"):
    G = GAMES_BY_SEASON[season]
    n = len(sp); proj = sp["exp_pts"].values; pos = sp["position"].values
    OLD_AV = {"QB": 0.94, "RB": 0.86, "WR": 0.92, "TE": 0.91}
    av = np.array([OLD_AV[p] for p in pos])
    p_major = np.clip(0.06 + (1 - av) * 0.15, 0.06, 0.30)
    sig = np.full(n, 0.25)
    normal_games = np.clip(rng.normal((G * av)[:, None], (1.0 * (1 - av) * G)[:, None], (n, N_SIMS)), 0, G)
    major = rng.random((n, N_SIMS)) < p_major[:, None]
    games = np.where(major, rng.uniform(0, 8, (n, N_SIMS)), normal_games)
    M = rng.lognormal((-(sig ** 2) / 2)[:, None], sig[:, None], (n, N_SIMS))
    raw = games * M
    sims = raw * (proj / raw.mean(1))[:, None]
    p20 = np.percentile(sims, 20, 1); p80 = np.percentile(sims, 80, 1)
    actual = sp["total_pts"].values
    cov_o.extend(((actual >= p20) & (actual <= p80)).tolist())
    boom_po.extend((sims >= 1.5 * proj[:, None]).mean(1).tolist())
print(f"OLD 20/80 coverage: {np.mean(cov_o):.1%}   OLD P(>=1.5x) predicted: {np.mean(boom_po):.1%} "
      f"(realized {np.mean(boom_real):.1%})")
