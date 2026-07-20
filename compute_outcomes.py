import nflreadpy as nfl
import pandas as pd
import numpy as np
from utils import normalize_name, startable_counts

np.random.seed(0)

# ---- tunable knobs ----
# Wave-1 recalibration (Jul 2026): every constant below was fit to 2019-2025 real outcomes
# vs preseason market expectation and BACKTESTED to 60.3% 20/80-band coverage (target 60%)
# and 15.0% predicted vs 15.3% realized boom rate. Evidence + scripts: icm/work/mc_research/.
N_SIMS = 20000
INJURY_K = 1.0
GAMES = 17
BOOM = {"QB": 25, "RB": 20, "WR": 20, "TE": 15, "K": 13}
BUST = {"QB": 12, "RB": 6,  "WR": 6,  "TE": 4,  "K": 4}
# per-game lognormal sigma by preseason positional rank: variance GROWS with rank depth
# (real 20/80 bands: ~1.6x wide for elites, 2.5-3.5x for rank 25+). Interpolated per player.
SIGMA_ANCHORS = {
    "QB": [(3, 0.235), (9, 0.238), (18, 0.238), (32, 0.294), (50, 0.45)],  # deep-QB clipped (backups)
    "RB": [(3, 0.334), (9, 0.334), (18, 0.334), (32, 0.398), (50, 0.491)],
    "WR": [(3, 0.240), (9, 0.240), (18, 0.246), (32, 0.287), (50, 0.351)],
    "TE": [(3, 0.305), (9, 0.346), (18, 0.364), (32, 0.497), (50, 0.504)],
    "K":  [(3, 0.350), (50, 0.350)],   # not researched - flat mid value
}
ROOKIE_SIGMA_MULT = {"QB": 1.5, "RB": 1.4, "WR": 1.0, "TE": 1.1, "K": 1.0}  # WR rookies: NOT wider
# durability: real starters play ~.82-.85 at EVERY position (old QB .94 was fiction)
AVAIL_PRIOR = {"RB": 0.817, "WR": 0.841, "TE": 0.828, "QB": 0.845, "K": 0.97}
AVAIL_K = 4.0             # shrink history harder: "injury-prone" barely recurs among starters
# season-tanking injury odds by position (empirical P(miss 9+)); mild bump for low availability
P_MAJOR_POS = {"QB": 0.103, "RB": 0.108, "WR": 0.089, "TE": 0.071, "K": 0.05}
# age cliffs: RB holds until ~29 then falls fast; QB shows NO age availability penalty
AGE_CLIFF = {"RB": 29, "WR": 29, "TE": 29, "QB": 99, "K": 34}
AGE_SLOPE = {"RB": 0.035, "WR": 0.025, "TE": 0.030, "QB": 0.0, "K": 0.010}
# injuries hurt twice: players who miss time are also worse per game when active
# (miss 4-8 -> ~10% worse, 9+ -> ~20%; corr(games, per-game) = +0.29)
COUPLE = 0.41
COUPLE_FLOOR = 0.55


def sigma_for(pos, rank):
    """Per-game sim sigma from the position's anchor table, by projection positional rank."""
    xs, ys = zip(*SIGMA_ANCHORS[pos])
    return float(np.interp(rank, xs, ys))
# REPLACEMENT (startable-tier size for p_startable/p_bust) is computed flex-aware from
# the loaded board below via startable_counts() — RB/WR split floats with projections.


def draft_tilt(pick):
    """Rookie mean adjustment by draft capital — refit to 2019-2025 (median mult vs market:
    top-32 picks 1.10-1.20, 2nd rd ~1.0, 3rd rd is the dead zone at 0.78, 4th+ ~0.97)."""
    if pd.isna(pick):  return 1.00
    if pick <= 15:     return 1.10
    if pick <= 32:     return 1.08
    if pick <= 64:     return 1.00
    if pick <= 105:    return 0.92
    return 0.95


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
    prior = AVAIL_PRIOR.get(row["position"], 0.84)
    shrunk = (row["_obs"]*row["_ns"] + prior*AVAIL_K) / (row["_ns"] + AVAIL_K)
    pen = 0.0
    if pd.notna(row["age"]):
        pen = max(0.0, row["age"] - AGE_CLIFF.get(row["position"], 30)) * AGE_SLOPE.get(row["position"], 0.015)
    return float(np.clip(shrunk - pen, 0.5, 1.0))


df["availability"] = df.apply(durability, axis=1)
df = df.drop(columns=["_obs", "_ns"])

# ---- Wave-2 situation flags (backtested: icm/work/mc_research/09_wave2_validation.py) ----
# team change: last 2025 team (nflverse codes; LA -> LAR) vs current Sleeper team
last25 = (wk[wk["season"] == 2025].sort_values("week")
          .groupby("player_id")["team"].last().replace({"LA": "LAR"}))
_t25 = df["gsis_id"].map(last25)
df["team_changed"] = _t25.notna() & (_t25 != df["team"])
df["team_stayed"] = _t25.notna() & (_t25 == df["team"])   # (no team_2025 col: load_ff_opportunity merges its own)
# volatility relative to position peers (prior 2 seasons' weekly CV)
pos_med_cv = df.groupby("position")["consistency"].transform("median")
df["cv_rel"] = (df["consistency"] / pos_med_cv).fillna(1.0)

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
    av = sub["availability"].fillna(AVAIL_PRIOR.get(pos, 0.84)).clip(0.5, 1.0).values
    rookie = sub["is_rookie"].values
    # sigma by projection positional rank (variance grows with depth), rookies wider (not WRs)
    pos_rank = (-proj).argsort().argsort() + 1
    season_sigma = np.array([sigma_for(pos, r) for r in pos_rank])
    season_sigma = np.where(rookie, season_sigma * ROOKIE_SIGMA_MULT[pos], season_sigma)
    tilt = np.where(rookie, np.array([draft_tilt(p) for p in sub["draft_pick"].values]), 1.0)
    # Wave-2 situational adjustments (each backtested; see 09_wave2_validation.py):
    # team-changers bust hard at QB/RB/TE (real bust .38-.40 vs .23-.27 stayers); stable
    # RB/TE vets run tighter; WR 30+ are known quantities (booms fade); volatile players wider.
    chg = sub["team_changed"].values & ~rookie
    stay = sub["team_stayed"].values & ~rookie
    if pos == "QB":
        tilt = np.where(chg, tilt * 0.97, tilt)
        season_sigma = np.where(chg, season_sigma * 1.40, season_sigma)
    elif pos == "RB":
        tilt = np.where(chg, tilt * 0.94, tilt)
        season_sigma = np.where(stay, season_sigma * 0.85, season_sigma)
    elif pos == "TE":
        tilt = np.where(chg, tilt * 0.95, tilt)
        season_sigma = np.where(chg, season_sigma * 1.15,
                       np.where(stay, season_sigma * 0.85, season_sigma))
    elif pos == "WR":
        wr30 = sub["age"].fillna(0).values >= 30
        tilt = np.where(wr30, tilt * 0.98, tilt)
        season_sigma = np.where(wr30, season_sigma * 0.70, season_sigma)
    if pos != "K":
        cv_blend = np.clip(1 + 0.30 * (sub["cv_rel"].values - 1), 0.80, 1.30)
        season_sigma = season_sigma * np.where(rookie, 1.0, cv_blend)
    # season-tanking injury: position base rate + mild bump for low-availability players
    p_major = np.clip(P_MAJOR_POS[pos] + 0.5 * (0.84 - av), 0.05, 0.18)

    normal_games = np.clip(np.random.normal((GAMES*av)[:, None], (INJURY_K*(1-av)*GAMES)[:, None], (n, N_SIMS)), 0, GAMES)
    major = np.random.random((n, N_SIMS)) < p_major[:, None]  # a season-tanking injury this sim?
    games = np.where(major, np.random.uniform(1, 8, (n, N_SIMS)), normal_games)
    # coupling: missing time also degrades per-game output (empirical slope -0.41, floored)
    couple = np.clip(1 - COUPLE * (1 - games / GAMES), COUPLE_FLOOR, 1.0)
    M = np.random.lognormal((-(season_sigma**2)/2)[:, None], season_sigma[:, None], (n, N_SIMS))
    raw = games * couple * M
    # exact re-centering: E[sims] = projection x tilt (replaces the old e_games approximation)
    sims = raw * (proj / raw.mean(1))[:, None] * tilt[:, None]
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
