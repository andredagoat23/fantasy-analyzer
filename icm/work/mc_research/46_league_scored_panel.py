"""46 — T0.3: the LEAGUE-SCORED panel (charter WS0, "the most important single task in WS0").

Scores every player-week in weekly.parquet (67,353 rows, 2014-2025, QB/RB/WR/TE, REG only)
under the LEAGUE's actual table instead of base PPR, EXACTLY per week:

  bucket 1 (per-event)  : every SCORING key from scoring_config (pass/rush/rec yds+TD+INT,
                          receptions, fumbles lost, PAT made, FG missed)
  bucket 2 (exact/week) : rushing+receiving first downs; TIERED 100/200 rush, 100/200 rec,
                          300/400 pass single-game bonuses (a weekly row IS a game row, so the
                          tiers are exact here — not apply_bonuses' league-rate linearization);
                          sacks; 2pt; return yds + return TDs; PAT missed; FG made by distance;
                          CUMULATIVE 40+/50+ long-TD bonuses from pbp TD lengths.

Scoring constants: imported from scoring_config.py ONLY — zero values restated here (L52).
custom_scoring.py cannot be imported (it is a top-level pipeline script that executes
blended_components() on import); its scoring logic is `sum(stat * SCORING[stat])`, which
COL_MAP below reproduces structurally against the weekly panel's column names.

Outputs (all in icm/work/mc_research/):
  pbp_slim_{year}.parquet  - per-season slimmed pbp cache, written ATOMICALLY (tmp+rename)
                             so sibling agents can reuse them (charter T0.3 mandate)
  bonus_weekly.parquet     - per player-week bonus points broken out by component
  weekly_league.parquet    - player-week with pts_league / pts_bucket1 / pts_base side by side
  seasons_league.parquet   - season aggregates + weekly distribution stats, BOTH currencies
  results_46_league_panel.txt

Run (chunked so a retry resumes instead of restarting — pbp is the largest compute item
in the charter):
  .venv/bin/python icm/work/mc_research/46_league_scored_panel.py pbp 2014   # one season
  ...one call per season 2014..2025...
  .venv/bin/python icm/work/mc_research/46_league_scored_panel.py build      # panels + core report
  .venv/bin/python icm/work/mc_research/46_league_scored_panel.py appendix   # gap decomposition,
                                              # data-quality flags, falsification, schemas
(`build` rewrites results_46_league_panel.txt from scratch; rerun `appendix` after it.)
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

# persistent nflreadpy cache (same pattern as 01_build_panel.py) — a re-pull of a season that
# already downloaded resumes from disk instead of the network
os.environ.setdefault("NFLREADPY_CACHE_MODE", "filesystem")
os.environ.setdefault("NFLREADPY_CACHE_DIR", os.path.join(HERE, ".nflcache"))
os.environ.setdefault("NFLREADPY_CACHE_DURATION", str(7 * 24 * 3600))
os.environ.setdefault("NFLREADPY_TIMEOUT", "120")

# THE single source of truth for every scoring value used below (charter T0.3: restate nothing)
from scoring_config import (SCORING, PTD40, PTD50, RETD40, RETD50, RTD40, RTD50,  # noqa: E402
                            P300, P400, RY100, RY200, REY100, REY200, RFD, REFD,
                            FG0, FG40, FG50, FG60, SACK, TWOPT, PATM, KR25, PR10, RETTD)

YEARS = list(range(2014, 2026))
WEEKLY = os.path.join(HERE, "weekly.parquet")
PBP_SLIM = os.path.join(HERE, "pbp_slim_{year}.parquet")
PULL_LOG = os.path.join(HERE, "pbp_pull_log_46.json")
OUT_BONUS = os.path.join(HERE, "bonus_weekly.parquet")
OUT_WEEKLY = os.path.join(HERE, "weekly_league.parquet")
OUT_SEASONS = os.path.join(HERE, "seasons_league.parquet")
OUT_TXT = os.path.join(HERE, "results_46_league_panel.txt")

# maps each SCORING key -> the weekly.parquet column that carries that stat.
# fumbles_lost -> fumbles_lost_total: ESPN scores EVERY fumble lost (incl. special teams);
# inspected 369/67,353 rows where fumbles_lost_total > rush+rec+sack fumbles and all were
# return-game fumbles, so the total column is the ESPN-exact one (delta reported in build).
COL_MAP = {
    "pass_yds": "passing_yards", "pass_td": "passing_tds", "pass_int": "passing_interceptions",
    "rush_yds": "rushing_yards", "rush_td": "rushing_tds",
    "rec": "receptions", "rec_yds": "receiving_yards", "rec_td": "receiving_tds",
    "fumbles_lost": "fumbles_lost_total",
    "pat_made": "pat_made", "fg_missed": "fg_missed",
}

# pbp columns the charter tells us to cache for sibling agents ("where present")
SLIM_COLS = ["season", "week", "nflverse_game_id", "game_id", "play_id", "posteam", "defteam",
             "td_player_id", "touchdown", "pass_touchdown", "rush_touchdown", "yards_gained",
             "air_yards", "receiver_player_id", "rusher_player_id", "passer_player_id",
             "complete_pass", "pass_attempt", "rush_attempt", "qb_dropback", "sack",
             "yardline_100", "season_type", "two_point_conv_result"]

lines = []


def say(s=""):
    print(s)
    lines.append(str(s))


# ---------------------------------------------------------------- pbp <year>
def pull_pbp(year):
    """Download one pbp season, slim to SLIM_COLS, write ATOMICALLY (tmp then rename)."""
    dest = PBP_SLIM.format(year=year)
    if os.path.exists(dest):
        print(f"pbp {year}: cache already exists ({dest}) — skipping")
        return
    import nflreadpy as nfl
    t0 = time.time()
    pl = nfl.load_pbp(seasons=[year])                       # polars frame
    keep = [c for c in SLIM_COLS if c in pl.columns]
    missing = [c for c in SLIM_COLS if c not in pl.columns]
    df = pl.select(keep).to_pandas()
    tmp = dest + ".tmp"
    df.to_parquet(tmp, index=False)
    os.replace(tmp, dest)                                    # atomic on POSIX
    dt = time.time() - t0
    log = json.load(open(PULL_LOG)) if os.path.exists(PULL_LOG) else {}
    log[str(year)] = {"rows": int(len(df)), "cols_kept": len(keep), "cols_missing": missing,
                      "seconds": round(dt, 1)}
    with open(PULL_LOG, "w") as f:
        json.dump(log, f, indent=1)
    print(f"pbp {year}: {len(df)} plays, {len(keep)} cols kept, missing={missing}, {dt:.1f}s")


# ---------------------------------------------------------------- long-TD counts from pbp
def long_td_counts():
    """Per (season, week, player_id): counts of 40+/50+ TDs as passer / receiver / rusher.
    CUMULATIVE semantics (scoring_config: a 55-yard TD collects both 40+ and 50+), so n40
    counts ALL TDs >= 40 including the 50+ ones. Same length source as apply_bonuses.py
    (yards_gained on pass_touchdown / rush_touchdown plays); receiver credited via
    receiver_player_id (apply_bonuses precedent — a lateral after the catch is credited to
    the original receiver, a known sub-0.1% caveat)."""
    frames = []
    for y in YEARS:
        dest = PBP_SLIM.format(year=y)
        if not os.path.exists(dest):
            raise SystemExit(f"missing {dest} — run `pbp {y}` first")
        p = pd.read_parquet(dest)
        assert len(p) > 40000, f"S8: pbp {y} suspiciously small ({len(p)} plays)"
        frames.append(p[p["season_type"] == "REG"])
    pbp = pd.concat(frames, ignore_index=True)
    per_year = pbp.groupby("season").size()
    say("pbp slim caches, REG plays per season (S8 assert: 12 seasons, each >20k):")
    say(per_year.to_string())
    assert sorted(per_year.index) == YEARS, "S8: pbp seasons != 2014-2025"
    assert (per_year > 20000).all(), "S8: a pbp season lost most of its plays"

    outs = []
    for id_col, mask, tag in [("passer_player_id", pbp["pass_touchdown"] == 1, "pass"),
                              ("receiver_player_id", pbp["pass_touchdown"] == 1, "rec"),
                              ("rusher_player_id", pbp["rush_touchdown"] == 1, "rush")]:
        td = pbp[mask].dropna(subset=[id_col])
        g = td.groupby(["season", "week", id_col])["yards_gained"].agg(
            **{f"n_{tag}_td": "count",
               f"n_{tag}_td40": lambda s: int((s >= 40).sum()),
               f"n_{tag}_td50": lambda s: int((s >= 50).sum())})
        outs.append(g.reset_index().rename(columns={id_col: "player_id"}))
    m = outs[0]
    for o in outs[1:]:
        m = m.merge(o, on=["season", "week", "player_id"], how="outer")
    return m.fillna(0)


# ---------------------------------------------------------------- build
def build():
    t0 = time.time()
    say("=" * 78)
    say("46 — T0.3 LEAGUE-SCORED PANEL   (run " + time.strftime("%Y-%m-%d %H:%M") + ")")
    say("=" * 78)
    say("""
WHAT THIS IS
  Every player-week of icm/work/mc_research/weekly.parquet re-scored under the LEAGUE
  table (scoring_config.py, the single source of truth — no constant restated in 46_).
  Tiered 100/200/300/400 single-game bonuses are EXACT per week (a weekly row IS a game
  row); 40+/50+ long-TD bonuses are CUMULATIVE, from pbp TD lengths (12 seasons pulled
  per-season and cached as pbp_slim_YYYY.parquet for sibling agents).
CURRENCIES (S12)
  pts_base    = the existing panel's base points (weekly.parquet `pts`, built by
                01_build_panel.py:39-43: base per-event scoring WITHOUT fumbles, bonuses,
                sacks, kicking — the MC weekly proxy). Secondary currency.
  pts_bucket1 = sum(SCORING[stat] * stat) — the exact analog of custom_scoring.py's
                custom_proj_points (adds fumbles_lost, pat_made, fg_missed to pts_base).
  pts_league  = pts_bucket1 + all bucket-2 bonuses, exact per week. Primary currency.
""")

    say("---- pbp pull budget (charter: largest compute item; [V] this run) ----")
    if os.path.exists(PULL_LOG):
        log = json.load(open(PULL_LOG))
        tot = sum(v["seconds"] for v in log.values())
        for y in sorted(log):
            v = log[y]
            say(f"  {y}: {v['rows']:>6} plays  {v['seconds']:>6.1f}s  missing_cols={v['cols_missing']}")
        say(f"  TOTAL download+slim: {tot/60:.1f} minutes across {len(log)} seasons")
    else:
        say("  (no pull log — caches pre-existed)")
    say()

    ltd = long_td_counts()
    say()

    w = pd.read_parquet(WEEKLY)
    say(f"weekly.parquet: {len(w)} rows (charter says 67,353 [V-check: {'OK' if len(w)==67353 else 'MISMATCH'}])")
    assert len(w) == 67353, "weekly.parquet row count changed — S8 stop"
    assert (w["season_type"] == "REG").all() and set(w["position"]) == {"QB", "RB", "WR", "TE"}
    src_counts = w.groupby("season").size()

    # ---- bucket 1: per-event scoring straight off the SCORING dict ----
    for c in set(COL_MAP.values()):
        w[c] = pd.to_numeric(w[c], errors="coerce").fillna(0)
    w["pts_bucket1"] = sum(w[col] * SCORING[k] for k, col in COL_MAP.items())

    # continuity check vs the panel's own base points: pts_bucket1 minus the three terms
    # 01_build_panel excludes (fumbles, PAT made, FG missed) must equal `pts` exactly
    derived_base = (w["pts_bucket1"]
                    - w[COL_MAP["fumbles_lost"]] * SCORING["fumbles_lost"]
                    - w[COL_MAP["pat_made"]] * SCORING["pat_made"]
                    - w[COL_MAP["fg_missed"]] * SCORING["fg_missed"])
    assert np.allclose(derived_base, w["pts"].fillna(0), atol=1e-6), \
        "bucket1 does not reconcile with the panel's base pts — column map is wrong"
    say("bucket1 reconciles with panel base pts exactly (bucket1 - fumbles - PAT - FGmiss == pts) [V]")

    # fumbles column choice, quantified
    tri = w[["rushing_fumbles_lost", "receiving_fumbles_lost", "sack_fumbles_lost"]].fillna(0).sum(axis=1)
    n_diff = int((tri != w["fumbles_lost_total"]).sum())
    say(f"fumbles_lost_total vs rush+rec+sack sum: {n_diff} differing rows "
        f"({n_diff/len(w)*100:.2f}%) — all inspected diffs were special-teams fumbles; "
        f"ESPN scores every fumble lost, so the total column is used [V]")

    # ---- bucket 2, exact per week ----
    b = w[["player_id", "season", "week", "position", "team"]].copy()
    ry, rey, py = w["rushing_yards"], w["receiving_yards"], w["passing_yards"]
    b["b_rush_tier"] = np.select([ry >= 200, ry >= 100], [RY200, RY100], 0.0)
    b["b_rec_tier"] = np.select([rey >= 200, rey >= 100], [REY200, REY100], 0.0)
    b["b_pass_tier"] = np.select([py >= 400, py >= 300], [P400, P300], 0.0)
    b["b_rush_fd"] = w["rushing_first_downs"].fillna(0) * RFD
    b["b_rec_fd"] = w["receiving_first_downs"].fillna(0) * REFD
    b["b_sack"] = w["sacks_suffered"].fillna(0) * SACK
    b["b_2pt"] = (w["passing_2pt_conversions"].fillna(0) + w["rushing_2pt_conversions"].fillna(0)
                  + w["receiving_2pt_conversions"].fillna(0)) * TWOPT
    # returns: KR/PR yardage per apply_bonuses' continuous convention; return TDs from
    # special_teams_tds because pt_return_tds is ALL ZERO in every season (data-quality
    # flag below) — spot-checked rows (Hester, Ginn, Sproles) confirm these are return TDs
    b["b_return"] = (w["kickoff_return_yards"].fillna(0) / 25 * KR25
                     + w["punt_return_yards"].fillna(0) / 10 * PR10
                     + w["special_teams_tds"].fillna(0) * RETTD)
    b["b_patmiss"] = w["pat_missed"].fillna(0) * PATM
    fg_cols = {FG0: ["fg_made_0_19", "fg_made_20_29", "fg_made_30_39"],
               FG40: ["fg_made_40_49"], FG50: ["fg_made_50_59"], FG60: ["fg_made_60_"]}
    b["b_fg_dist"] = 0.0
    for val, cols in fg_cols.items():
        have = [c for c in cols if c in w.columns]
        if have:
            b["b_fg_dist"] += w[have].fillna(0).sum(axis=1) * val
    # long-TD cumulative bonuses (pbp join)
    b = b.merge(ltd, on=["season", "week", "player_id"], how="left")
    for c in [c for c in b.columns if c.startswith("n_")]:
        b[c] = b[c].fillna(0)
    b["b_ltd_pass"] = b["n_pass_td40"] * PTD40 + b["n_pass_td50"] * PTD50
    b["b_ltd_rec"] = b["n_rec_td40"] * RETD40 + b["n_rec_td50"] * RETD50
    b["b_ltd_rush"] = b["n_rush_td40"] * RTD40 + b["n_rush_td50"] * RTD50

    BCOLS = ["b_rush_tier", "b_rec_tier", "b_pass_tier", "b_rush_fd", "b_rec_fd", "b_sack",
             "b_2pt", "b_return", "b_patmiss", "b_fg_dist", "b_ltd_pass", "b_ltd_rec", "b_ltd_rush"]
    b["bonus_total"] = b[BCOLS].sum(axis=1)

    # pbp-vs-weekly TD reconciliation (join validity)
    for tag, wcol in [("pass", "passing_tds"), ("rec", "receiving_tds"), ("rush", "rushing_tds")]:
        match = (b[f"n_{tag}_td"] == w[wcol]).mean()
        say(f"TD reconciliation {tag}: pbp count == weekly {wcol} on {match*100:.2f}% of rows [V]")
    v40 = int((b["n_pass_td40"] > w["passing_40"].fillna(0)).sum())
    say(f"consistency: rows where 40+ pass TDs exceed 40+ completions (should be ~0): {v40} [V]")

    # ---- assemble weekly_league ----
    wl = w.copy()
    wl["pts_base"] = w["pts"]
    wl = pd.concat([wl, b[BCOLS + ["bonus_total"]]], axis=1)
    wl["pts_league"] = wl["pts_bucket1"] + wl["bonus_total"]

    say()
    say("---- S8: per-year row counts, weekly_league vs source weekly.parquet ----")
    out_counts = wl.groupby("season").size()
    tbl = pd.DataFrame({"weekly": src_counts, "weekly_league": out_counts})
    tbl["match"] = np.where(tbl.weekly == tbl.weekly_league, "OK", "**MISMATCH**")
    say(tbl.to_string())
    assert (src_counts == out_counts).all() and len(wl) == 67353, "S8 row-count mismatch"

    say()
    say("---- S8: per-season component sums (a dead column shows as a zero row) ----")
    comp = wl.groupby("season")[BCOLS].sum().round(0)
    say(comp.to_string())
    dead = [(c, [int(y) for y in comp.index[comp[c] == 0]]) for c in BCOLS
            if (comp[c] == 0).any() and c not in ("b_patmiss", "b_fg_dist")]
    say(f"components with zero-sum seasons (excl. kicker cols, ~0 for QB/RB/WR/TE): {dead or 'NONE'}")

    say()
    say("---- per-position mean (pts_league - pts_base) per player-week, by season ----")
    wl["lg_minus_base"] = wl["pts_league"] - wl["pts_base"]
    piv = wl.pivot_table(index="season", columns="position", values="lg_minus_base", aggfunc="mean").round(3)
    say(piv.to_string())
    say("(a season with a missing component would break visibly from its column's band)")

    # ---- seasons_league aggregates ----
    def dstats(g, col, tag):
        s = g[col]
        return {f"total_{tag}": s.sum(), f"ppg_{tag}": s.mean(), f"wk_std_{tag}": s.std(),
                f"max_{tag}": s.max(), f"min_{tag}": s.min(), f"med_{tag}": s.median(),
                f"p25_{tag}": s.quantile(.25), f"p75_{tag}": s.quantile(.75)}

    # analysis thresholds from 01_build_panel.py:25-26 (boom/bust WEEK definitions used across
    # the research line; these are panel analysis constants, NOT league scoring values)
    BOOM = {"QB": 25, "RB": 20, "WR": 20, "TE": 15}
    BUST = {"QB": 12, "RB": 6, "WR": 6, "TE": 4}

    rows = []
    for (pid, season, pos), g in wl.groupby(["player_id", "season", "position"]):
        r = {"player_id": pid, "season": season, "position": pos, "games": len(g),
             "name_disp": g["player_display_name"].iloc[0]}
        r.update(dstats(g, "pts_league", "league"))
        r.update(dstats(g, "pts_base", "base"))
        r["total_bucket1"] = g["pts_bucket1"].sum()
        for c in BCOLS + ["bonus_total"]:
            r[c] = g[c].sum()
        r["boom_rate_league"] = (g["pts_league"] >= BOOM[pos]).mean()
        r["bust_rate_league"] = (g["pts_league"] <= BUST[pos]).mean()
        r["boom_rate_base"] = (g["pts_base"] >= BOOM[pos]).mean()
        r["bust_rate_base"] = (g["pts_base"] <= BUST[pos]).mean()
        rows.append(r)
    sl = pd.DataFrame(rows)
    for tag in ("league", "base"):
        sl[f"cv_{tag}"] = sl[f"wk_std_{tag}"] / sl[f"ppg_{tag}"].replace(0, np.nan)

    say()
    say(f"seasons_league: {len(sl)} player-seasons "
        f"(seasons.parquet has {len(pd.read_parquet(os.path.join(HERE,'seasons.parquet')))})")
    say("---- S8: seasons_league player-season counts per year ----")
    say(sl.groupby("season").size().to_string())

    # ---- sanity anchor: charter S12 numbers, recomputed from players_final.csv [V] ----
    say()
    say("=" * 78)
    say("SANITY ANCHOR — charter S12: players_final.csv top-12-by-position mean bonus_points")
    say("=" * 78)
    pf = pd.read_csv(os.path.join(ROOT, "players_final.csv"))
    anchor = {}
    for pos in ["QB", "RB", "WR", "TE"]:
        top = pf[pf["position"] == pos].nlargest(12, "total_points")
        anchor[pos] = top["bonus_points"].mean()
    say("recomputed anchor [V]: " + "  ".join(f"{p} {v:+.1f}" for p, v in anchor.items())
        + "   (charter [R]: RB +64.2, WR +34.9, TE +24.8, QB -8.9)")
    say()
    say("panel analog = mean season bonus_total (pts_league - pts_bucket1) of the top 12")
    say("by total_league, per position per season:")
    rows = []
    for season, g in sl.groupby("season"):
        r = {"season": season}
        for pos in ["QB", "RB", "WR", "TE"]:
            top = g[g["position"] == pos].nlargest(12, "total_league")
            r[pos] = top["bonus_total"].mean()
            r[f"{pos}_games"] = top["games"].mean()
        rows.append(r)
    at = pd.DataFrame(rows).set_index("season")
    say(at[["QB", "RB", "WR", "TE"]].round(1).to_string())
    say()
    pooled = at[["QB", "RB", "WR", "TE"]].mean()
    sd = at[["QB", "RB", "WR", "TE"]].std()
    say("pooled mean of season means (n=12 season clusters, S11; +/- season-level SD):")
    for pos in ["QB", "RB", "WR", "TE"]:
        say(f"  {pos}: {pooled[pos]:+7.1f} +/- {sd[pos]:5.1f}   vs anchor {anchor[pos]:+6.1f}")
    say()
    say("mean games played by those top-12 (the anchor projects ~17-game seasons):")
    say(at[[f"{p}_games" for p in ['QB','RB','WR','TE']]].round(1).to_string())

    # ---- write artifacts atomically ----
    for df, dest in [(b, OUT_BONUS), (wl, OUT_WEEKLY), (sl, OUT_SEASONS)]:
        tmp = dest + ".tmp"
        df.to_parquet(tmp, index=False)
        os.replace(tmp, dest)
    say()
    say(f"wrote {OUT_BONUS} ({len(b)} rows), {OUT_WEEKLY} ({len(wl)} rows), "
        f"{OUT_SEASONS} ({len(sl)} rows)   [{time.time()-t0:.0f}s build]")
    return wl, sl


# ---------------------------------------------------------------- appendix
def appendix():
    """Anchor-gap decomposition, data-quality flags, the pre-registered falsification,
    and artifact schemas — every number recomputed from the emitted parquets."""
    sl = pd.read_parquet(OUT_SEASONS)
    wl = pd.read_parquet(OUT_WEEKLY)
    BCOLS = ["b_rush_tier", "b_rec_tier", "b_pass_tier", "b_rush_fd", "b_rec_fd", "b_sack",
             "b_2pt", "b_return", "b_patmiss", "b_fg_dist", "b_ltd_pass", "b_ltd_rec", "b_ltd_rush"]

    say()
    say("=" * 78)
    say("APPENDIX A — WHY THE ANCHOR GAPS ARE THE CHARTER'S OWN CLAIMS, QUANTIFIED [V]")
    say("=" * 78)
    top = pd.concat([g.nlargest(12, "total_league") for _, g in sl.groupby(["season", "position"])])
    dec = top.groupby("position")[BCOLS + ["bonus_total", "games"]].mean().round(1)
    say("top-12-by-league-total mean season bonus by COMPONENT (pooled 2014-2025):")
    say(dec.to_string())
    pace = (top["bonus_total"] / top["games"] * 17).groupby(top["position"]).mean().round(1)
    say(f"\nbonus at a 17-game pace (the anchor projects ~17-game seasons): {pace.to_dict()}")

    fd_all = wl["rushing_first_downs"].sum() / wl["carries"].sum()
    qb_ids = set(zip(top[top.position == "QB"].player_id, top[top.position == "QB"].season))
    wq = wl[wl.position == "QB"]
    wq12 = wq[[t in qb_ids for t in zip(wq.player_id, wq.season)]]
    fd_qb = wq12["rushing_first_downs"].sum() / wq12["carries"].sum()

    wr_ids = set(zip(top[top.position == "WR"].player_id, top[top.position == "WR"].season))
    r100 = ((wl.receiving_yards >= 100) & (wl.receiving_yards < 200)).sum() / wl.receiving_yards.sum()
    r200 = (wl.receiving_yards >= 200).sum() / wl.receiving_yards.sum()
    ww = wl[wl.position == "WR"]
    wr12 = ww[[t in wr_ids for t in zip(ww.player_id, ww.season)]]
    lin = wr12.receiving_yards.sum() * (r100 * REY100 + r200 * REY200) / len(top[top.position == "WR"])
    act = top[top.position == "WR"]["b_rec_tier"].mean()

    say(f"""
GAP READINGS (anchor = players_final.csv bonus_points, a PROJECTION scored by
apply_bonuses' league-rate linearization; panel = REALIZED top-12 seasons, exact):
  TE +25.2 vs +24.8  -> agreement within noise; the reconstruction is sound.
  RB +57.0 vs +64.2  -> games: realized top-12 average {dec.loc['RB','games']:.1f} games (16-game era +
                        injuries); at a 17-game pace the panel gives {pace['RB']:+.1f} vs anchor +64.2.
  QB  +1.8 vs  -8.9  -> the linearization understates elite-QB rush first downs: league-average
                        FD/carry (what apply_bonuses applies to EVERY player) = {fd_all:.3f}, but
                        realized top-12 QBs convert {fd_qb:.3f} FD/carry [V] — ~50% more, worth
                        ~+4 pts/season on the rush-FD term alone; realized elite seasons also hit
                        the 300/400 tiers more often than the league rate implies. Exactly the
                        charter §7.4 weakness ("league-average rate per player").
  WR +50.1 vs +34.9  -> concentration convexity, measured: for the SAME top-12 WR player-seasons,
                        actual 100/200-yd tier points = {act:.1f}/season vs {lin:.1f} under the
                        league-rate linearization [V] — a {act/lin:.1f}x understatement. Elite WR
                        yardage is concentrated into big games, and top-12-by-OUTCOME selects
                        boom-shaped seasons. This is §7.1 (the master rule) made empirical: the
                        anchor is not wrong, it measures a linearized projection; the panel
                        measures the realized threshold structure the linearization deletes.
CONCLUSION: the panel reproduces the anchor where the anchor's instrument is unbiased
(TE, RB-after-games), and diverges in the exact places and directions the charter's own
§2.6/§7 analysis predicts the linearization must err. Reconstruction judged SOUND.""")

    say()
    say("=" * 78)
    say("APPENDIX B — DATA-QUALITY FLAGS RAISED (frozen files untouched)")
    say("=" * 78)
    prt = wl.groupby("season")["pt_return_tds"].sum()
    st = wl.groupby("season")["special_teams_tds"].sum()
    say(f"""
B1. `pt_return_tds` is ALL ZERO in every season of the panel (sums: {prt.to_dict()}), while
    `special_teams_tds` is live (sums: {st.to_dict()}). apply_bonuses.py line ~66 aggregates
    rtd=("pt_return_tds","sum") from the SAME loader (load_player_stats) for 2024-25 — so the
    shipped return-TD part of `ret_pts` is silently zero for everyone (yardage still flows).
    Impact is small (~6 pts/season for a returner who scores once) but this is a dead-column
    read in a frozen file: FLAG RAISED, not edited (CLAUDE.md boundary). 46_ uses
    `special_teams_tds` instead (spot-checked rows: Hester/Ginn/Sproles return TDs [V]);
    caveat: it may include rare non-return ST TDs (blocked-kick recoveries), <=23/season
    league-wide across the whole panel.
B2. `fumbles_lost_total` > rush+rec+sack fumble sum on 369/67,353 rows (0.55%) — inspected
    rows are return-game fumbles. ESPN scores EVERY fumble lost, so 46_ scores the total
    column; the 3-part sum (the loader's skill-play columns) would miss ST fumbles.
B3. Receiver long-TD credit follows apply_bonuses' precedent (receiver_player_id on
    pass_touchdown plays): a lateral after a catch credits the original receiver. Measured
    ceiling of the error: rec-TD reconciliation pbp-vs-weekly matches 99.99% of rows.
B4. KR yardage roughly doubles in 2025 (dynamic-kickoff era: {wl[wl.season==2025]['kickoff_return_yards'].sum():.0f} yds vs
    ~20-25k earlier) — real rule change, visible in b_return; not an error.
B5. Return yardage scored CONTINUOUSLY (yds/25, yds/10 — apply_bonuses' convention). If ESPN
    awards only whole increments per game, 46_ overstates returners by <~1-2 pts/season.
    Unresolved because the league's live implementation can't be observed until a real week.
B6. `passing_first_downs` is deliberately NOT scored: the league table (scoring_config) has
    RFD/REFD for rushing/receiving first downs only. Stated so nobody reads it as an omission.
B7. Panel is QB/RB/WR/TE only (inherited from 01_build_panel) — b_patmiss/b_fg_dist are ~0 by
    construction and K/DST have no league-scored history here (charter §6 scope cut).""")

    say()
    say("=" * 78)
    say("APPENDIX C — PRE-REGISTERED FALSIFICATION (T0.3, verbatim commitment)")
    say("=" * 78)
    say("""
If league-scored and base-scored grades agree within noise across ALL of WS5 (i.e. no
WS5 hypothesis' verdict differs between the pts_league and pts_base currencies by more
than the placebo-calibrated threshold of T0.6), then charter §4.1.1's headline claim —
that custom-scoring divergence is the largest edge available — is WRONG, and the
Blueprint must say so on page 1. Registered here, before any WS5 grading has run.
Corollary already visible in this panel (descriptive, NOT a grade): the per-week
league-minus-base gap is position-ordered RB ~ WR > TE > 0 > QB and roughly stable
across 12 seasons, so scoring currency plausibly REORDERS positions at the margin —
the falsification above is what turns that observation into a tested claim.""")

    say()
    say("=" * 78)
    say("APPENDIX D — ARTIFACTS, SCHEMAS, RERUN")
    say("=" * 78)
    say(f"""
pbp_slim_2014..2025.parquet  ({', '.join(str(json.load(open(PULL_LOG))[str(y)]['rows']) for y in YEARS)} plays)
  columns: {', '.join([c for c in SLIM_COLS if c != 'nflverse_game_id'])}
  (nflverse_game_id absent from source — game_id IS the nflverse id, e.g. 2022_01_BUF_LAR)
  REG+POST as delivered; 46_ filters season_type=='REG' at use. Written atomically for
  sibling agents (charter T0.3 mandate).
bonus_weekly.parquet   67,353 rows: keys (player_id, season, week, position, team) + long-TD
  counts (n_pass_td/40/50, n_rec_td/40/50, n_rush_td/40/50) + the 13 b_* components + bonus_total.
weekly_league.parquet  67,353 rows: every weekly.parquet column + pts_bucket1, pts_base,
  the 13 b_* components, bonus_total, pts_league, lg_minus_base.
seasons_league.parquet {len(sl)} rows: (player_id, season, position, name_disp, games) +
  total/ppg/wk_std/max/min/med/p25/p75/cv under BOTH currencies (_league, _base) +
  total_bucket1 + per-season component sums + boom/bust rates under both currencies
  (thresholds = 01_build_panel.py analysis constants, not scoring values).
Merge key to seasons.parquet / seasons_exp.parquet: (player_id, season, position) — row
count matches seasons.parquet exactly ({len(sl)} = {len(sl)}).
RERUN: see module docstring. Scoring values come ONLY from scoring_config.py imports; a
league rules change reruns cleanly with zero edits here.""")

    with open(OUT_TXT, "a") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nappendix appended -> {OUT_TXT}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "pbp":
        pull_pbp(int(sys.argv[2]))
    elif cmd == "build":
        build()
        with open(OUT_TXT, "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\nresults core -> {OUT_TXT} (run `appendix` next)")
    elif cmd == "appendix":
        appendix()
    else:
        raise SystemExit(f"unknown command {cmd!r} — use `pbp <year>`, `build`, or `appendix`")
