# Robustness pass before the frozen-file edit:
# 1) sigma targets recomputed the RIGHT way for MC's structure: M carries PER-GAME variance
#    (sd of ln mult_pg), the games machinery + coupling carry the rest.
# 2) outlier-robust sigma (from the 20/80 band, not std - Puka-proof).
# 3) era-split stability (2019-21 vs 2022-25) and 2020-COVID exclusion sensitivity.
# 4) final smoothed sigma tables to paste into compute_outcomes.py.
import pandas as pd
import numpy as np

OUT = "icm/work/mc_research"
sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")
Z80 = 0.841621  # z-score of the 80th percentile: sigma = ln(p80/p20) / (2*z80)

pool = sea[sea["mult"].notna() & (sea["exp_pos_rank"] <= 60) & (sea["mult"] > 0)].copy()
pool = pool[pool["mult_pg"].notna() & (pool["mult_pg"] > 0)]
pool["ln_pg"] = np.log(pool["mult_pg"])
pool["tier"] = pd.cut(pool["exp_pos_rank"], [0, 6, 12, 24, 40, 60],
                      labels=["1-6", "7-12", "13-24", "25-40", "41-60"])

def robust_sigma(s):
    """sigma implied by the empirical 20/80 band of a multiplier (outlier-insensitive)."""
    p20, p80 = s.quantile(.2), s.quantile(.8)
    if p20 <= 0:
        return np.nan
    return np.log(p80 / p20) / (2 * Z80)

# ---------- 1+2. per-game sigma by pos x tier: std vs robust ----------
print("=== PER-GAME sigma targets for M (this is what replaces ROLE_RISK) ===")
print("pos tier      n   sd(ln)  robust(20/80)")
rows = {}
for (posn, tier), g in pool.groupby(["position", "tier"], observed=True):
    rs = robust_sigma(g["mult_pg"])
    rows[(posn, str(tier))] = (len(g), g["ln_pg"].std(), rs)
    print(f"{posn:3} {tier:6} {len(g):4}   {g['ln_pg'].std():.3f}   {rs:.3f}")

# ---------- 3a. era split (2019-2021 vs 2022-2025): is the tier pattern stable? ----------
print("\n=== era-split stability: robust per-game sigma ===")
pool["era"] = np.where(pool["season"] <= 2021, "2019-21", "2022-25")
print("pos tier      early   late")
for (posn, tier), g in pool.groupby(["position", "tier"], observed=True):
    e = robust_sigma(g[g.era == "2019-21"]["mult_pg"]) if (g.era == "2019-21").sum() >= 15 else np.nan
    l = robust_sigma(g[g.era == "2022-25"]["mult_pg"]) if (g.era == "2022-25").sum() >= 15 else np.nan
    print(f"{posn:3} {tier:6}  {e:5.3f}   {l:5.3f}" if not (np.isnan(e) or np.isnan(l))
          else f"{posn:3} {tier:6}  (thin)")

# ---------- 3b. 2020-COVID exclusion sensitivity on the headline numbers ----------
nc = pool[pool["season"] != 2020]
print("\n=== 2020-exclusion sensitivity ===")
for posn, g in pool.groupby("position"):
    g2 = nc[nc["position"] == posn]
    print(f"  {posn}: P(mult>=1.5) all={ (g['mult']>=1.5).mean():.3f}  no2020={(g2['mult']>=1.5).mean():.3f}"
          f"   robust sigma(mult_pg) all={robust_sigma(g['mult_pg']):.3f} no2020={robust_sigma(g2['mult_pg']):.3f}")

# ---------- 3c. availability numbers without 2020 (starter pool) ----------
CUT = {"QB": 18, "RB": 36, "WR": 42, "TE": 14}
st = sea[sea["exp_pos_rank"].notna()].copy()
st = st[st.apply(lambda r: r["exp_pos_rank"] <= CUT[r["position"]], axis=1)]
st_nc = st[st["season"] != 2020]
print("\n=== starter played_frac / P(9+ missed): all vs no-2020 ===")
for posn in ["QB", "RB", "WR", "TE"]:
    a = st[st.position == posn]; b = st_nc[st_nc.position == posn]
    print(f"  {posn}: played {a['games_frac'].mean():.3f}/{b['games_frac'].mean():.3f}   "
          f"cat9 {(a['games_missed']>=9).mean():.3f}/{(b['games_missed']>=9).mean():.3f}")

# ---------- 4. final smoothed sigma tables (monotone in rank, tier-midpoint anchors) ----------
# robust sigma per tier, shrunk toward the position's pooled value by cell size (k=60),
# then enforced non-decreasing with rank depth. QB deep tiers clipped (backup artifact).
print("\n=== FINAL per-game sigma anchors (paste into compute_outcomes.py) ===")
MIDS = {"1-6": 3, "7-12": 9, "13-24": 18, "25-40": 32, "41-60": 50}
K = 60
final = {}
for posn in ["QB", "RB", "WR", "TE"]:
    g_all = pool[pool["position"] == posn]
    pooled = robust_sigma(g_all["mult_pg"])
    anchors = []
    for tier, mid in MIDS.items():
        n, sd, rs = rows.get((posn, tier), (0, np.nan, np.nan))
        if n == 0 or np.isnan(rs):
            continue
        shrunk = (rs * n + pooled * K) / (n + K)
        anchors.append((mid, shrunk))
    # monotone non-decreasing with depth
    vals = [v for _, v in anchors]
    vals = np.maximum.accumulate(vals)
    final[posn] = list(zip([m for m, _ in anchors], np.round(vals, 3)))
    print(f"  {posn}: {final[posn]}  (pooled={pooled:.3f})")

# ---------- 5. coupling strength: fit per-game decline vs games missed ----------
d = pool.copy()
d["miss_frac"] = 1 - d["games_frac"]
# median mult_pg in miss-frac bins -> slope of decline
bins = pd.cut(d["miss_frac"], [-0.01, 0.05, 0.2, 0.5, 1.0])
fit = d.groupby(bins, observed=True).agg(n=("mult_pg", "size"), mid=("miss_frac", "median"),
                                         pg=("mult_pg", "median"))
print("\n=== coupling fit: per-game multiplier vs fraction of season missed ===")
print(fit.round(3).to_string())
x, y = fit["mid"].values, fit["pg"].values
slope = np.polyfit(x, y, 1)[0]
print(f"linear slope ~ {slope:.2f}  -> per_game_eff = per_game * (1 + {slope:.2f} * (1 - games/GAMES))")
