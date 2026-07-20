# Expectation layer: convert preseason positional rank -> expected fantasy points,
# using E[actual season pts | preseason rank] (binned + monotone-smoothed, pooled 2019-2025).
# This is the market-implied "projection" every boom/bust/distribution analysis measures against.
# Works in per-scheduled-game units so 16-game (2019-20) and 17-game seasons pool cleanly.
import pandas as pd
import numpy as np

OUT = "icm/work/mc_research"
sea = pd.read_parquet(f"{OUT}/seasons.parquet")

# per-scheduled-game actuals (era-neutral)
sea["pts_psg"] = sea["total_pts"] / sea["season_games"]
sea["exp_pool"] = sea["exp_pos_rank"].notna()

# E[pts_psg | preseason pos rank], per position: binned means then monotone-decreasing smoothing
def expectation_curve(df, max_rank=80):
    d = df[df["exp_pos_rank"].notna() & (df["exp_pos_rank"] <= max_rank)]
    m = d.groupby(d["exp_pos_rank"].astype(int))["pts_psg"].agg(["mean", "count"])
    m = m.reindex(range(1, max_rank + 1))
    m["mean"] = m["mean"].interpolate(limit_direction="both")
    # rolling smooth (window widens with rank - sparse tail), then enforce monotone decreasing
    sm = m["mean"].rolling(5, center=True, min_periods=1).mean()
    sm = np.minimum.accumulate(sm)          # expectation can't rise as rank worsens
    return sm

curves = {}
for pos in ["QB", "RB", "WR", "TE"]:
    curves[pos] = expectation_curve(sea[sea["position"] == pos])

def expected_psg(row):
    if pd.isna(row["exp_pos_rank"]):
        return np.nan
    c = curves[row["position"]]
    r = min(int(row["exp_pos_rank"]), len(c))
    return c.iloc[r - 1]

sea["exp_psg"] = sea.apply(expected_psg, axis=1)
sea["exp_pts"] = sea["exp_psg"] * sea["season_games"]

# season multiplier (the quantity MC's lognormal M x games models) + per-game multiplier
sea["mult"] = sea["total_pts"] / sea["exp_pts"]
# per-game skill multiplier: needs an expected-PPG curve (conditional on playing)
def ppg_curve(df, max_rank=80):
    d = df[df["exp_pos_rank"].notna() & (df["exp_pos_rank"] <= max_rank) & (df["games"] >= 6)]
    m = d.groupby(d["exp_pos_rank"].astype(int))["ppg"].agg(["mean"])
    m = m.reindex(range(1, max_rank + 1))
    m["mean"] = m["mean"].interpolate(limit_direction="both")
    sm = m["mean"].rolling(5, center=True, min_periods=1).mean()
    return np.minimum.accumulate(sm)

ppg_curves = {pos: ppg_curve(sea[sea["position"] == pos]) for pos in ["QB", "RB", "WR", "TE"]}
def expected_ppg(row):
    if pd.isna(row["exp_pos_rank"]):
        return np.nan
    c = ppg_curves[row["position"]]
    r = min(int(row["exp_pos_rank"]), len(c))
    return c.iloc[r - 1]

sea["exp_ppg"] = sea.apply(expected_ppg, axis=1)
sea["mult_pg"] = sea["ppg"] / sea["exp_ppg"]
sea["games_frac"] = sea["games"] / sea["season_games"]

sea.to_parquet(f"{OUT}/seasons_exp.parquet", index=False)

# --- report the curves + multiplier health ---
print("Expectation curves (pts/scheduled-game) at ranks 1/5/12/24/36/48:")
for pos, c in curves.items():
    pts = [f"{c.iloc[r-1]:.1f}" for r in [1, 5, 12, 24, 36, 48]]
    print(f"  {pos}: {pts}")
pool = sea[sea["mult"].notna() & (sea["exp_pos_rank"] <= 60)]
print(f"\nmultiplier pool: {len(pool)} player-seasons")
print("mult by position:  mean / median / p20 / p80:")
for pos, g in pool.groupby("position"):
    print(f"  {pos}: {g['mult'].mean():.2f} / {g['mult'].median():.2f} / "
          f"{g['mult'].quantile(.2):.2f} / {g['mult'].quantile(.8):.2f}  (n={len(g)})")
# spot-check the famous seasons
for nm, yr in [("Cooper Kupp", 2021), ("Puka Nacua", 2023), ("Christian McCaffrey", 2022),
               ("Jonathan Taylor", 2022), ("Javonte Williams", 2022)]:
    r = sea[(sea.name_disp == nm) & (sea.season == yr)]
    if len(r) and pd.notna(r.iloc[0]["mult"]):
        x = r.iloc[0]
        print(f"  {nm} {yr}: exp_rank={x.exp_pos_rank:.0f} exp_pts={x.exp_pts:.0f} "
              f"actual={x.total_pts:.0f} mult={x.mult:.2f} mult_pg={x.mult_pg:.2f} games={x.games:.0f}")
