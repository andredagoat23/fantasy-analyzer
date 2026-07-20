# Build the MC-research panel: player-weeks + player-seasons, 2019-2025, QB/RB/WR/TE,
# scored under the SAME league formula compute_outcomes.py uses (apples-to-apples with MC).
# Outputs (cached in icm/work/mc_research/):
#   weekly.parquet   - player-week rows with usage + team context
#   seasons.parquet  - player-season aggregates + prior-season features + preseason ADP
#   adp_hist.csv     - FFC preseason ADP per year (market expectation baseline)
import sys, os, time, json, subprocess
# persistent disk cache -> reruns don't re-download 7 seasons; longer timeout for big files
os.environ["NFLREADPY_CACHE_MODE"] = "filesystem"
os.environ["NFLREADPY_CACHE_DIR"] = "icm/work/mc_research/.nflcache"
os.environ["NFLREADPY_CACHE_DURATION"] = str(7 * 24 * 3600)
os.environ["NFLREADPY_TIMEOUT"] = "120"
import nflreadpy as nfl
import pandas as pd
import numpy as np

sys.path.insert(0, ".")
from utils import normalize_name

OUT = "icm/work/mc_research"
YEARS = list(range(2014, 2026))   # modern-era window: 2x the cohort sample
SEASON_GAMES = {y: (16 if y <= 2020 else 17) for y in range(2014, 2026)}
POS = ["QB", "RB", "WR", "TE"]
# boom/bust week thresholds — identical to compute_outcomes.py
BOOM = {"QB": 25, "RB": 20, "WR": 20, "TE": 15}
BUST = {"QB": 12, "RB": 6, "WR": 6, "TE": 4}

# ---------- 1. weekly stats, league-scored ----------
wk = nfl.load_player_stats(seasons=YEARS).to_pandas()
wk = wk[(wk["season_type"] == "REG") & wk["position"].isin(POS)].copy()
num_cols = ["passing_yards", "passing_tds", "passing_interceptions", "rushing_yards", "rushing_tds",
            "receptions", "receiving_yards", "receiving_tds", "targets", "carries",
            "target_share", "air_yards_share", "wopr", "receiving_air_yards", "attempts",
            "rushing_fumbles_lost", "receiving_fumbles_lost", "sack_fumbles_lost"]
for c in num_cols:
    if c not in wk.columns:
        wk[c] = 0.0
wk[num_cols] = wk[num_cols].fillna(0)
wk["pts"] = (
    wk["passing_yards"]*0.04 + wk["passing_tds"]*6 + wk["passing_interceptions"]*-2
    + wk["rushing_yards"]*0.1 + wk["rushing_tds"]*6
    + wk["receptions"]*1 + wk["receiving_yards"]*0.1 + wk["receiving_tds"]*6
)
wk["is_boom"] = (wk["pts"] >= wk["position"].map(BOOM)).astype(float)
wk["is_bust"] = (wk["pts"] <= wk["position"].map(BUST)).astype(float)
wk["touches"] = wk["carries"] + wk["receptions"]

# ---------- 2. snap counts (join via pfr_id from rosters) ----------
sc = nfl.load_snap_counts(seasons=YEARS).to_pandas()
sc = sc[sc["game_type"] == "REG"][["season", "week", "pfr_player_id", "offense_pct"]]
ros = nfl.load_rosters(seasons=YEARS).to_pandas()
ros = ros[ros["position"].isin(POS)].copy()
pfr2gsis = (ros.dropna(subset=["pfr_id", "gsis_id"])
              .drop_duplicates(["season", "pfr_id"])[["season", "pfr_id", "gsis_id"]])
sc = sc.merge(pfr2gsis, left_on=["season", "pfr_player_id"], right_on=["season", "pfr_id"], how="inner")
sc = sc.drop_duplicates(["season", "week", "gsis_id"])[["season", "week", "gsis_id", "offense_pct"]]
wk = wk.merge(sc, left_on=["season", "week", "player_id"], right_on=["season", "week", "gsis_id"], how="left")
wk = wk.drop(columns=["gsis_id"])

# ---------- 3. expected fantasy points (ff_opportunity) + team volume ----------
xfp = nfl.load_ff_opportunity(seasons=YEARS).to_pandas()
xfp["season"] = xfp["season"].astype(int)
xfp["week"] = xfp["week"].astype(int)
xfp_p = xfp[["season", "week", "player_id", "total_fantasy_points_exp",
             "pass_attempt_team", "rush_attempt_team"]].dropna(subset=["player_id"])
xfp_p = xfp_p.drop_duplicates(["season", "week", "player_id"])
wk = wk.merge(xfp_p, on=["season", "week", "player_id"], how="left")

# ---------- 4. vegas implied team totals per game ----------
sch = nfl.load_schedules(seasons=YEARS).to_pandas()
sch = sch[sch["game_type"] == "REG"]
home = sch[["season", "week", "home_team", "total_line", "spread_line"]].rename(columns={"home_team": "team"})
home["implied_total"] = home["total_line"]/2 + home["spread_line"]/2
away = sch[["season", "week", "away_team", "total_line", "spread_line"]].rename(columns={"away_team": "team"})
away["implied_total"] = away["total_line"]/2 - away["spread_line"]/2
veg = pd.concat([home, away])[["season", "week", "team", "implied_total", "total_line"]]
wk = wk.merge(veg, on=["season", "week", "team"], how="left")

# ---------- 5. roster info: age, weight, draft capital ----------
ros["birth_date"] = pd.to_datetime(ros["birth_date"], errors="coerce")
ros["age_sep1"] = ros.apply(
    lambda r: (pd.Timestamp(f"{int(r['season'])}-09-01") - r["birth_date"]).days / 365.25
    if pd.notna(r["birth_date"]) else np.nan, axis=1)
ros_info = (ros.sort_values("draft_number")
              .drop_duplicates(["season", "gsis_id"])
              [["season", "gsis_id", "age_sep1", "weight", "height", "draft_number",
                "years_exp", "entry_year", "full_name"]])
wk = wk.merge(ros_info, left_on=["season", "player_id"], right_on=["season", "gsis_id"], how="left")
wk = wk.drop(columns=["gsis_id"])

# ---------- 6. injuries: weekly report status ----------
# NOTE: read the locally-downloaded parquets. Pre-2025 files have NO season_type column
# (only game_type) - filtering on season_type silently drops every year but 2025.
import glob
inj = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{OUT}/raw/injuries_*.parquet"))])
inj = inj[inj["game_type"] == "REG"].copy()
inj["season"] = inj["season"].astype(int)
inj["week"] = inj["week"].astype(int)
inj_w = (inj.drop_duplicates(["season", "week", "gsis_id"])
            [["season", "week", "gsis_id", "report_status", "report_primary_injury", "practice_status"]])
wk = wk.merge(inj_w, left_on=["season", "week", "player_id"], right_on=["season", "week", "gsis_id"], how="left")
wk = wk.drop(columns=["gsis_id"])

wk.to_parquet(f"{OUT}/weekly.parquet", index=False)
print(f"weekly: {len(wk)} rows, seasons {sorted(wk.season.unique())}")

# ---------- 7. historical preseason ADP: FFC (2019-24) + FantasyPros (2025 gap) ----------
import re
def fp_adp(year):
    """FantasyPros historical PPR ADP - data embedded as JSON in the page."""
    url = f"https://www.fantasypros.com/nfl/adp/ppr-overall.php?year={year}"
    html = subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", url],
                          capture_output=True, text=True, timeout=60).stdout
    pat = (r'"name":"([^"]+)","team":"([^"]*)","url":"[^"]*"\},"pos":"([A-Z]+)\d+"'
           r'.*?"avg":([\d.]+)')
    rows = []
    for m in re.finditer(pat, html):
        name, team, pos, avg = m.groups()
        rows.append({"season": year, "name": name, "position": pos,
                     "team": team.split(" ")[0], "adp": float(avg), "adp_stdev": np.nan})
    return rows

adp_rows = []
for y in YEARS:
    url = f"https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year={y}"
    raw = subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", url],
                         capture_output=True, text=True, timeout=60).stdout
    data = json.loads(raw)
    if "players" in data:
        for p in data["players"]:
            adp_rows.append({"season": y, "name": p["name"], "position": p["position"],
                             "team": p["team"], "adp": p["adp"], "adp_stdev": p["stdev"]})
    else:
        fp = fp_adp(y)
        print(f"  FFC missing {y} -> FantasyPros fallback: {len(fp)} players")
        adp_rows.extend(fp)
    time.sleep(0.6)
adp = pd.DataFrame(adp_rows)
adp = adp[adp["position"].isin(POS)].copy()
adp["nn"] = adp["name"].apply(normalize_name)
adp["adp_pos_rank"] = adp.groupby(["season", "position"])["adp"].rank(method="first")
adp.to_csv(f"{OUT}/adp_hist.csv", index=False)
print(f"adp: {len(adp)} rows across {adp.season.nunique()} seasons")

# ---------- 8. player-season aggregates ----------
def agg_season(g):
    return pd.Series({
        "games": len(g), "total_pts": g["pts"].sum(), "ppg": g["pts"].mean(),
        "wk_std": g["pts"].std(), "boom_rate": g["is_boom"].mean(), "bust_rate": g["is_bust"].mean(),
        "snap_pct": g["offense_pct"].mean(), "tgt_share": g["target_share"].mean(),
        "ay_share": g["air_yards_share"].mean(), "wopr": g["wopr"].mean(),
        "touches_pg": g["touches"].mean(), "carries_pg": g["carries"].mean(),
        "targets_pg": g["targets"].mean(), "attempts_pg": g["attempts"].mean(),
        "total_touches": g["touches"].sum(),
        "xfp_total": g["total_fantasy_points_exp"].sum(), "xfp_pg": g["total_fantasy_points_exp"].mean(),
        "team_pass_pg": g["pass_attempt_team"].mean(), "implied_total_avg": g["implied_total"].mean(),
        "last_week": g["week"].max(), "first_week": g["week"].min(),
        "n_teams": g["team"].nunique(), "team_last": g.sort_values("week")["team"].iloc[-1],
        "age": g["age_sep1"].iloc[0], "weight": g["weight"].iloc[0],
        "draft_number": g["draft_number"].iloc[0], "years_exp": g["years_exp"].iloc[0],
        "entry_year": g["entry_year"].iloc[0], "full_name_r": g["full_name"].iloc[0],
        "name_disp": g["player_display_name"].iloc[0],
    })

sea = wk.groupby(["player_id", "season", "position"]).apply(agg_season).reset_index()
sea["cv"] = sea["wk_std"] / sea["ppg"].replace(0, np.nan)
sea["season_games"] = sea["season"].map(SEASON_GAMES)
sea["games_missed"] = sea["season_games"] - sea["games"]

# injury-report aggregates per player-season (listed weeks, Out weeks, distinct injury types)
inj_agg = (inj_w.assign(is_out=lambda d: d["report_status"].isin(["Out", "Doubtful"]).astype(float))
           .groupby(["season", "gsis_id"])
           .agg(inj_weeks_listed=("report_status", lambda s: s.notna().sum()),
                inj_weeks_out=("is_out", "sum"),
                inj_types=("report_primary_injury", lambda s: s.dropna().nunique()))
           .reset_index())
sea = sea.merge(inj_agg, left_on=["season", "player_id"], right_on=["season", "gsis_id"], how="left")
sea = sea.drop(columns=["gsis_id"])
sea[["inj_weeks_listed", "inj_weeks_out", "inj_types"]] = sea[["inj_weeks_listed", "inj_weeks_out", "inj_types"]].fillna(0)

# primary injury body-part per player-season (most-listed)
inj_main = (inj.dropna(subset=["report_primary_injury"])
              .groupby(["season", "gsis_id"])["report_primary_injury"]
              .agg(lambda s: s.value_counts().index[0]).reset_index()
              .rename(columns={"report_primary_injury": "inj_primary"}))
sea = sea.merge(inj_main, left_on=["season", "player_id"], right_on=["season", "gsis_id"], how="left")
sea = sea.drop(columns=["gsis_id"])

# season-ended-early flag: missed the final 3+ team weeks after last appearance
final_wk = wk.groupby("season")["week"].max().to_dict()
sea["end_missed"] = sea["season"].map(final_wk) - sea["last_week"]
sea["ended_early"] = (sea["end_missed"] >= 3) & (sea["games"] >= 1)

# position finish ranks (by total and per-game among 6+ game players)
sea["pos_rank_total"] = sea.groupby(["season", "position"])["total_pts"].rank(ascending=False, method="first")
ppg_pool = sea[sea["games"] >= 6]
sea["pos_rank_ppg"] = ppg_pool.groupby(["season", "position"])["ppg"].rank(ascending=False, method="first")

# ---------- 8b. preseason ECR (FantasyPros archive via dynastyprocess) ----------
ecr_all = nfl.load_ff_rankings("all").to_pandas()
ecr_all["scrape_date"] = pd.to_datetime(ecr_all["scrape_date"])
ppr = ecr_all[ecr_all["fp_page"] == "/nfl/rankings/ppr-cheatsheets.php"]
ecr_rows = []
for y in YEARS:
    w = ppr[(ppr.scrape_date >= f"{y}-08-15") & (ppr.scrape_date <= f"{y}-09-06")]
    if w.empty:
        continue
    snap = w[w.scrape_date == w.scrape_date.max()].copy()
    snap["season"] = y
    ecr_rows.append(snap[["season", "player", "pos", "ecr", "sd"]])
ecr = pd.concat(ecr_rows)
ecr = ecr[ecr["pos"].isin(POS)].copy()
ecr["nn"] = ecr["player"].apply(normalize_name)
ecr = ecr.rename(columns={"pos": "position", "ecr": "ecr_pre", "sd": "ecr_sd"})
ecr = ecr.drop_duplicates(["season", "position", "nn"])
ecr["ecr_pos_rank"] = ecr.groupby(["season", "position"])["ecr_pre"].rank(method="first")
ecr.to_csv(f"{OUT}/ecr_hist.csv", index=False)
print(f"ecr: {len(ecr)} rows across seasons {sorted(ecr.season.unique())}")

# preseason ADP + ECR joins (name-normalized within season+position)
sea["nn"] = sea["name_disp"].apply(normalize_name)
sea = sea.merge(adp[["season", "position", "nn", "adp", "adp_pos_rank"]],
                on=["season", "position", "nn"], how="left")
sea = sea.merge(ecr[["season", "position", "nn", "ecr_pre", "ecr_sd", "ecr_pos_rank"]],
                on=["season", "position", "nn"], how="left")
# unified preseason expectation: ECR pos-rank where available, else ADP pos-rank
sea["exp_pos_rank"] = sea["ecr_pos_rank"].fillna(sea["adp_pos_rank"])

# prior-season (t-1) features for prediction analyses
prev = sea.add_prefix("prev_")
prev["join_season"] = prev["prev_season"] + 1          # align t-1 row to season t
sea = sea.merge(prev, left_on=["player_id", "season"],
                right_on=["prev_player_id", "join_season"], how="left",
                suffixes=("", "_x"))
sea = sea.drop(columns=["join_season"], errors="ignore")

sea.to_parquet(f"{OUT}/seasons.parquet", index=False)
print(f"seasons: {len(sea)} player-seasons, ADP matched: {sea['adp'].notna().sum()}")

# sanity spot-checks against known reality
for nm, yr in [("Christian McCaffrey", 2023), ("Puka Nacua", 2023), ("Cooper Kupp", 2021),
               ("Justin Jefferson", 2023), ("Saquon Barkley", 2024)]:
    r = sea[(sea["name_disp"] == nm) & (sea["season"] == yr)]
    if len(r):
        x = r.iloc[0]
        print(f"  {nm} {yr}: g={x.games:.0f} pts={x.total_pts:.0f} ppg={x.ppg:.1f} "
              f"rank={x.pos_rank_total:.0f} adp_pos={x.adp_pos_rank if pd.notna(x.adp_pos_rank) else '-'} "
              f"missed={x.games_missed:.0f} ended_early={x.ended_early}")
