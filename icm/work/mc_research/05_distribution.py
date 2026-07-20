# Distribution-shape research: is MC's lognormal season multiplier the right shape,
# and is its width right? Compares the CURRENT board's MC bands vs 7 seasons of reality.
import pandas as pd
import numpy as np

# no scipy in this venv - tiny local stand-ins
class stats:
    @staticmethod
    def skew(x):
        x = np.asarray(x); m = x.mean(); s = x.std()
        return ((x - m) ** 3).mean() / s ** 3
    @staticmethod
    def kurtosis(x):
        x = np.asarray(x); m = x.mean(); s = x.std()
        return ((x - m) ** 4).mean() / s ** 4 - 3
    class norm:
        @staticmethod
        def cdf(z):
            from math import erf, sqrt
            return 0.5 * (1 + erf(z / sqrt(2)))

OUT = "icm/work/mc_research"
sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")

pool = sea[sea["mult"].notna() & (sea["exp_pos_rank"] <= 60) & (sea["mult"] > 0)].copy()
pool["ln_mult"] = np.log(pool["mult"])

# ---------- 1. shape: is ln(mult) normal? (lognormal => yes) ----------
print("=== ln(season multiplier): moments by position ===")
for pos, g in pool.groupby("position"):
    ln = g["ln_mult"]
    print(f"  {pos}: n={len(g)} mean={ln.mean():+.3f} sigma={ln.std():.3f} "
          f"skew={stats.skew(ln):+.2f} exkurt={stats.kurtosis(ln):+.2f}")
print("  (lognormal fit => skew ~0, exkurt ~0 in ln space)\n")

# ---------- 2. width: empirical sigma by expectation tier (does it shrink for elites?) ----------
pool["tier"] = pd.cut(pool["exp_pos_rank"], [0, 6, 12, 24, 40, 60],
                      labels=["1-6", "7-12", "13-24", "25-40", "41-60"])
t2 = pool.groupby(["position", "tier"], observed=True).agg(
    n=("ln_mult", "size"), sigma=("ln_mult", "std"),
    p20=("mult", lambda s: s.quantile(.2)), p80=("mult", lambda s: s.quantile(.8)))
t2["band_ratio"] = t2["p80"] / t2["p20"]
print("=== empirical multiplier width by preseason tier ===")
print(t2.round(3).to_string(), "\n")

# ---------- 3. MC's CURRENT bands on the live board (apples-to-apples) ----------
board = pd.read_csv("players_with_outcomes.csv")
b = board[board["total_points"].notna() & board["floor"].notna() &
          board["position"].isin(["QB", "RB", "WR", "TE"])].copy()
b["mc_p20"] = b["floor"] / b["total_points"]      # MC's 20th pct as a multiplier of projection
b["mc_p80"] = b["ceiling"] / b["total_points"]
b["pos_rank_proj"] = b.groupby("position")["total_points"].rank(ascending=False)
b["tier"] = pd.cut(b["pos_rank_proj"], [0, 6, 12, 24, 40, 60], labels=["1-6", "7-12", "13-24", "25-40", "41-60"])
t3 = b[b["tier"].notna()].groupby(["position", "tier"], observed=True).agg(
    n=("mc_p20", "size"), mc_p20=("mc_p20", "median"), mc_p80=("mc_p80", "median"))
t3["mc_band_ratio"] = t3["mc_p80"] / t3["mc_p20"]
print("=== MC's CURRENT 20/80 band (multiplier of projection), live board ===")
print(t3.round(3).to_string())
print("compare: empirical p20/p80 above. If MC band is inside the real band -> overconfident.\n")

# ---------- 4. tail probabilities: empirical vs MC-implied ----------
print("=== right-tail: P(mult >= 1.5) and P(mult >= 2.0) ===")
for pos, g in pool.groupby("position"):
    p15, p20x = (g["mult"] >= 1.5).mean(), (g["mult"] >= 2.0).mean()
    # MC-implied with its typical vet sigma ~0.25 (lognormal, mean-preserving)
    sig = 0.25
    z15 = (np.log(1.5) + sig**2/2) / sig
    z20 = (np.log(2.0) + sig**2/2) / sig
    print(f"  {pos}: empirical {p15:.1%} / {p20x:.1%}   "
          f"MC(sigma=.25) implies {1-stats.norm.cdf(z15):.1%} / {1-stats.norm.cdf(z20):.1%}")
print()

# ---------- 5. variance decomposition: games vs per-game ----------
d = pool[pool["mult_pg"].notna() & (pool["mult_pg"] > 0) & (pool["games_frac"] > 0)].copy()
d["ln_pg"] = np.log(d["mult_pg"])
d["ln_gf"] = np.log(d["games_frac"])
v_pg, v_gf = d["ln_pg"].var(), d["ln_gf"].var()
cov = d[["ln_pg", "ln_gf"]].cov().iloc[0, 1]
tot = v_pg + v_gf + 2 * cov
print("=== variance decomposition of ln(season mult) ===")
print(f"  var(per-game)={v_pg:.3f} ({v_pg/tot:.0%})  var(games)={v_gf:.3f} ({v_gf/tot:.0%})  "
      f"2cov={2*cov:.3f} ({2*cov/tot:.0%})  total={tot:.3f}")
print(f"  -> per-game (role/efficiency) variance is the DOMINANT term, not injuries\n")

# ---------- 6. what sigma should be: empirical sigma of ln mult by pos x tier, clean table ----------
print("=== RECOMMENDED sigma targets (empirical sd of ln mult) ===")
t6 = pool.groupby(["position", "tier"], observed=True)["ln_mult"].agg(["count", "std"])
print(t6.round(3).to_string())
print("\nMC today: season_sigma = sqrt(ROLE_RISK^2 + (cv/sqrt(17))^2), ROLE_RISK=.20 vets/.35 rookies,")
print("clip .05-.60 -> typically ~.21-.30 for vets. Empirical says ~.45-.75 depending on tier.")

# ---------- 7. rookie vs vet width ----------
pool["rk"] = pool["years_exp"] == 0
t7 = pool.groupby(["position", "rk"], observed=True)["ln_mult"].agg(["count", "std"])
print("\n=== rookie vs veteran sigma ===")
print(t7.round(3).to_string())
