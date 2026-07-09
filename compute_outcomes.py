import nflreadpy as nfl
import pandas as pd
import numpy as np

np.random.seed(0)

# ---- tunable knobs ----
N_SIMS = 20000
ROLE_RISK = 0.20
INJURY_K = 1.0
GAMES = 17
BOOM = {"QB": 25, "RB": 20, "WR": 20, "TE": 15, "K": 13}
BUST = {"QB": 12, "RB": 6,  "WR": 6,  "TE": 4,  "K": 4}
# durability model
AVAIL_PRIOR = 0.90         # healthy-baseline availability a small sample regresses toward
AVAIL_K = 2.0              # shrinkage strength (acts like this many "prior seasons")
AGE_CLIFF = {"RB": 26, "WR": 29, "TE": 29, "QB": 35, "K": 34}   # age where durability starts to fall
AGE_SLOPE = {"RB": 0.025, "WR": 0.015, "TE": 0.015, "QB": 0.020, "K": 0.010}

# ---- 1. weekly points (2024-25) for volatility + boom/bust ----
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

# ---- 2. durability: observed games-rate, regressed for sample size + age-penalized ----
w3 = nfl.load_player_stats(seasons=[2023, 2024, 2025]).to_pandas()
w3 = w3[w3["season_type"] == "REG"]
season_games = w3.groupby(["player_id", "season"])["week"].count()
max_season = season_games.groupby("player_id").max()
total = w3.groupby("player_id")["week"].count()
n_seasons = w3.groupby("player_id")["season"].nunique()
observed = (total / (GAMES * n_seasons)).clip(upper=1.0)
observed = observed[max_season >= 14]            # proven starters only ("backup" != "hurt")

# ---- 3. base board + weekly profile ----
df = pd.read_csv("players_with_metrics.csv", dtype={"player_id": str})
df = df.merge(prof, left_on="gsis_id", right_index=True, how="left")
df["consistency"] = df["wk_std"] / df["wk_mean"]
df["_obs"] = df["gsis_id"].map(observed)
df["_ns"] = df["gsis_id"].map(n_seasons)

def durability(row):
    if pd.isna(row["_obs"]):
        return np.nan
    shrunk = (row["_obs"]*row["_ns"] + AVAIL_PRIOR*AVAIL_K) / (row["_ns"] + AVAIL_K)   # regress small samples
    pen = 0.0
    if pd.notna(row["age"]):
        pen = max(0.0, row["age"] - AGE_CLIFF.get(row["position"], 30)) * AGE_SLOPE.get(row["position"], 0.015)
    return float(np.clip(shrunk - pen, 0.5, 1.0))

df["availability"] = df.apply(durability, axis=1)
df = df.drop(columns=["_obs", "_ns"])

# ---- 4. Monte Carlo per position: injury-aware floor/ceiling + finish odds ----
for c in ["floor", "ceiling", "P_pos1", "P_pos2", "P_pos3"]:
    df[c] = np.nan

for pos in ["QB", "RB", "WR", "TE", "K"]:
    sub = df[(df["position"] == pos) & df["total_points"].notna()]
    if sub.empty:
        continue
    proj = sub["total_points"].values
    wstd = sub["wk_std"].fillna(sub["wk_std"].median()).values
    av = sub["availability"].fillna(sub["availability"].median()).clip(0.5, 1.0).values
    n = len(sub)
    per_game = proj / (GAMES * av)
    games = np.clip(np.random.normal((GAMES*av)[:, None], (INJURY_K*(1-av)*GAMES)[:, None], (n, N_SIMS)), 0, GAMES)
    role = np.random.normal(1, ROLE_RISK, (n, N_SIMS))
    sims = np.clip(np.random.normal(games*per_game[:, None]*role, np.sqrt(games)*wstd[:, None]), 0, None)
    finish = (-sims).argsort(0).argsort(0) + 1
    df.loc[sub.index, "floor"] = np.percentile(sims, 20, axis=1)
    df.loc[sub.index, "ceiling"] = np.percentile(sims, 80, axis=1)
    df.loc[sub.index, "P_pos1"] = (finish <= 12).mean(1)
    df.loc[sub.index, "P_pos2"] = ((finish > 12) & (finish <= 24)).mean(1)
    df.loc[sub.index, "P_pos3"] = ((finish > 24) & (finish <= 36)).mean(1)

df.to_csv("players_with_outcomes.csv", index=False)
print(f"outcomes for {df['P_pos1'].notna().sum()} players; {df['availability'].notna().sum()} have a durability read")
