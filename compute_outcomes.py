import nflreadpy as nfl
import pandas as pd
import numpy as np
from utils import normalize_name, startable_counts

np.random.seed(0)

# ---- tunable knobs ----
N_SIMS = 20000
ROLE_RISK = 0.20          # season role/usage uncertainty (veterans)
ROOKIE_ROLE_RISK = 0.35   # wider for players with no NFL history (honest uncertainty)
INJURY_K = 1.0
GAMES = 17
BOOM = {"QB": 25, "RB": 20, "WR": 20, "TE": 15, "K": 13}
BUST = {"QB": 12, "RB": 6,  "WR": 6,  "TE": 4,  "K": 4}
# position-specific durability baseline (RBs get hurt more as a class)
AVAIL_PRIOR = {"RB": 0.86, "WR": 0.92, "TE": 0.91, "QB": 0.94, "K": 0.97}
AVAIL_K = 2.0
AGE_CLIFF = {"RB": 26, "WR": 29, "TE": 29, "QB": 35, "K": 34}
AGE_SLOPE = {"RB": 0.025, "WR": 0.015, "TE": 0.015, "QB": 0.020, "K": 0.010}
# REPLACEMENT (startable-tier size for p_startable/p_bust) is computed flex-aware from
# the loaded board below via startable_counts() — RB/WR split floats with projections.


def draft_tilt(pick):
    """Rookie mean adjustment by draft capital — premium picks beat conservative rookie projections."""
    if pd.isna(pick):  return 1.00
    if pick <= 15:     return 1.08
    if pick <= 32:     return 1.04
    if pick <= 64:     return 1.00
    if pick <= 105:    return 0.97
    return 0.93


# ---- 1. weekly points (2024-25) -> volatility + boom/bust ----
wk = nfl.load_player_stats(seasons=[2024, 2025]).to_pandas()
wk = wk[wk["season_type"] == "REG"].copy().fillna(0)
col = lambda c: wk[c] if c in wk.columns else 0
wk["pts"] = (
    wk["passing_yards"]*0.04 + wk["passing_tds"]*6 + wk["passing_interceptions"]*-2
    + wk["rushing_yards"]*0.1 + wk["rushing_tds"]*6
    + wk["receptions"]*1 + wk["receiving_yards"]*0.1 + wk["receiving_tds"]*6
    + (col("fg_made_0_19")+col("fg_made_20_29")+col("fg_made_30_39"))*3
    + col("fg_made_40_49")*4 + col("fg_made_50_59")*6 + col("fg_made_60_")*7
    + col("pat_made")*1 - col("fg_missed")*1
)
wk["is_boom"] = (wk["pts"] >= wk["position"].map(BOOM)).astype(float)
wk["is_bust"] = (wk["pts"] <= wk["position"].map(BUST)).astype(float)
prof = wk.groupby("player_id").agg(
    games=("pts", "count"), wk_mean=("pts", "mean"), wk_std=("pts", "std"),
    boom_rate=("is_boom", "mean"), bust_rate=("is_bust", "mean"))
prof = prof[prof["games"] >= 8]
HISTORY = set(prof.index)

# ---- 2. durability (regressed to a per-position prior, age-penalized) ----
w3 = nfl.load_player_stats(seasons=[2023, 2024, 2025]).to_pandas()
w3 = w3[w3["season_type"] == "REG"]
season_games = w3.groupby(["player_id", "season"])["week"].count()
max_season = season_games.groupby("player_id").max()
total = w3.groupby("player_id")["week"].count()
n_seasons = w3.groupby("player_id")["season"].nunique()
obs = (total / (GAMES * n_seasons)).clip(upper=1.0)
obs = obs[max_season >= 14]

# ---- 3. rookie draft capital (2026) ----
dp = nfl.load_draft_picks(seasons=[2026]).to_pandas()
dp = dp[dp["pick"].notna()]
gsis_pick = dict(zip(dp["gsis_id"].dropna(), dp.loc[dp["gsis_id"].notna(), "pick"]))
dp["nn"] = dp["pfr_player_name"].apply(normalize_name)
name_pick = dict(zip(dp["nn"], dp["pick"]))

# ---- 4. base board ----
df = pd.read_csv("players_with_metrics.csv", dtype={"player_id": str})
REPLACEMENT = startable_counts(df)   # flex-aware startable-tier size per position
df = df.merge(prof, left_on="gsis_id", right_index=True, how="left")
df["consistency"] = df["wk_std"] / df["wk_mean"]
df["_obs"] = df["gsis_id"].map(obs)
df["_ns"] = df["gsis_id"].map(n_seasons)
df["is_rookie"] = ~df["gsis_id"].isin(HISTORY)
df["draft_pick"] = df["gsis_id"].map(gsis_pick)
nn = df["full_name"].apply(normalize_name)
df["draft_pick"] = df["draft_pick"].fillna(nn.map(name_pick))


def durability(row):
    if pd.isna(row["_obs"]):
        return np.nan
    prior = AVAIL_PRIOR.get(row["position"], 0.90)
    shrunk = (row["_obs"]*row["_ns"] + prior*AVAIL_K) / (row["_ns"] + AVAIL_K)
    pen = 0.0
    if pd.notna(row["age"]):
        pen = max(0.0, row["age"] - AGE_CLIFF.get(row["position"], 30)) * AGE_SLOPE.get(row["position"], 0.015)
    return float(np.clip(shrunk - pen, 0.4, 1.0))


df["availability"] = df.apply(durability, axis=1)
df = df.drop(columns=["_obs", "_ns"])
median_cv = df["consistency"].median()

# ---- 5. Monte Carlo: right-skewed, injury- & capital-aware ----
NEW = ["floor", "ceiling", "p10", "p90", "P_pos1", "P_pos2", "P_pos3", "p_elite", "p_startable", "p_bust",
       "floor_healthy", "ceiling_healthy"]   # injury-free floor/ceiling (for the injury-neutral composite base)
for c in NEW:
    df[c] = np.nan

for pos in ["QB", "RB", "WR", "TE", "K"]:
    sub = df[(df["position"] == pos) & df["total_points"].notna()]
    if sub.empty:
        continue
    n = len(sub)
    proj = sub["total_points"].values
    av = sub["availability"].fillna(AVAIL_PRIOR.get(pos, 0.90)).clip(0.4, 1.0).values
    cv = sub["consistency"].fillna(median_cv).values
    rookie = sub["is_rookie"].values
    role_eff = np.where(rookie, ROOKIE_ROLE_RISK, ROLE_RISK)
    season_sigma = np.clip(np.sqrt(role_eff**2 + (cv / np.sqrt(GAMES))**2), 0.05, 0.60)
    tilt = np.where(rookie, np.array([draft_tilt(p) for p in sub["draft_pick"].values]), 1.0)
    # baseline season-ending injury risk -- even iron-men aren't bulletproof (~6%, more if injury-prone)
    p_major = np.clip(0.06 + (1 - av) * 0.15, 0.06, 0.30)
    e_games = (1 - p_major) * (GAMES * av) + p_major * 4.0     # expected games incl. the major-injury tail
    per_game = proj / e_games                                 # rescale so E[season] stays = projection

    normal_games = np.clip(np.random.normal((GAMES*av)[:, None], (INJURY_K*(1-av)*GAMES)[:, None], (n, N_SIMS)), 0, GAMES)
    major = np.random.random((n, N_SIMS)) < p_major[:, None]  # a season-tanking injury this sim?
    games = np.where(major, np.random.uniform(0, 8, (n, N_SIMS)), normal_games)
    M = np.random.lognormal((-(season_sigma**2)/2)[:, None], season_sigma[:, None], (n, N_SIMS))
    sims = games * (per_game*tilt)[:, None] * M
    sims_healthy = (proj*tilt)[:, None] * M      # injury-free: full season, same season variance

    finish = (-sims).argsort(0).argsort(0) + 1
    repl = REPLACEMENT.get(pos, 24)
    df.loc[sub.index, "floor"] = np.percentile(sims, 20, axis=1)
    df.loc[sub.index, "ceiling"] = np.percentile(sims, 80, axis=1)
    df.loc[sub.index, "floor_healthy"] = np.percentile(sims_healthy, 20, axis=1)
    df.loc[sub.index, "ceiling_healthy"] = np.percentile(sims_healthy, 80, axis=1)
    df.loc[sub.index, "p10"] = np.percentile(sims, 10, axis=1)
    df.loc[sub.index, "p90"] = np.percentile(sims, 90, axis=1)
    df.loc[sub.index, "p_elite"] = (finish <= 3).mean(1)
    df.loc[sub.index, "P_pos1"] = (finish <= 12).mean(1)
    df.loc[sub.index, "P_pos2"] = ((finish > 12) & (finish <= 24)).mean(1)
    df.loc[sub.index, "P_pos3"] = ((finish > 24) & (finish <= 36)).mean(1)
    df.loc[sub.index, "p_startable"] = (finish <= repl).mean(1)
    df.loc[sub.index, "p_bust"] = (finish > repl).mean(1)

df.to_csv("players_with_outcomes.csv", index=False)
print(f"outcomes for {df['P_pos1'].notna().sum()} players ({df['is_rookie'].sum()} rookies, "
      f"{df['draft_pick'].notna().sum()} with draft capital)")
cols = ["full_name", "position", "total_points", "floor", "ceiling", "P_pos1", "p_elite", "p_bust", "availability"]
for nm in ["Ladd McConkey", "DJ Moore", "Christian McCaffrey", "Jeremiyah Love", "Carnell Tate"]:
    r = df[df.full_name == nm]
    if len(r):
        x = r.iloc[0]
        print(f"  {nm:20} proj={x.total_points:.0f} fl={x.floor:.0f} ceil={x.ceiling:.0f} "
              f"P1={x.P_pos1*100:.0f}% elite={x.p_elite*100:.0f}% bust={x.p_bust*100:.0f}% "
              f"rookie={x.is_rookie} pick={x.draft_pick if pd.notna(x.draft_pick) else '-'}")
