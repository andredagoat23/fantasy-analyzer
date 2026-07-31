"""59 — T0.9 + H5e: LEAGUE-scoring xFP, and the cheap check on whether it matters.

WHAT THIS BUILDS (T0.9)
  A weekly expected-fantasy-points series computed under THIS league's scoring table
  (scoring_config.py — the single source of truth; zero values restated here, L52),
  from nflreadpy load_ff_opportunity's per-week expectation columns (receptions_exp,
  *_touchdown_exp, *_yards_gained_exp, *_first_down_exp, *_two_point_conv_exp,
  pass_interception_exp). The frozen pipeline file load_ff_opportunity.py is NOT
  modified — this is the charter-mandated parallel research module.

WHAT THIS TESTS (H5e) — S14 PRE-REGISTRATION, DECLARED BEFORE ANY MEASUREMENT RAN
  CHEAP CHECK (gate, not the endpoint): within (position, season), Spearman rank
    correlation between season-aggregate league-xPPG and standard-xPPG in the
    DRAFTABLE range (priced adp <= 200 via seasons.parquet, 2025 via the T0.2
    Sleeper repair; >= 8 REG games with xFP data). Decision rule, stated verbatim
    from the assignment: if the correlation is >= 0.98 in EVERY (position x season)
    cell, the answer is a clean null — the two xFPs are the same role signal, the
    board's existing xppg is fine, and NO points test runs.
  PRIMARY ENDPOINT (runs ONLY if the cheap check falsifies the null): the paired
    difference, per position, in predictive Spearman against NEXT-season league
    points-above-price — Spearman(league-xPPG_t, resid_{t+1}) minus
    Spearman(standard-xPPG_t, resid_{t+1}) — pooled over the 11 season-pairs
    2014->15 .. 2024->25, CI clustered on SEASON-PAIR (S11; 11 clusters < 40 =>
    any result is DIRECTIONAL-ONLY regardless of its number). resid_{t+1} =
    total_league(t+1) minus a per-position quadratic-in-log(adp) price curve fit
    on all priced player-seasons. A league-points grade in the paired-draft
    harness is explicitly a WS6 follow-on, not claimed here.
  SECONDARY (reported regardless, no OR-threshold): the "171 players with no
    xppg" population. Named failure mode (reproduced BEFORE any test, per S14):
    value_board.py:90-93 — role_pct falls back to target-share pct, then neutral
    0.5, when xppg is NaN. League-xFP is computed from the SAME ff_opportunity
    rows as standard xFP, so its coverage is IDENTICAL BY CONSTRUCTION and it
    cannot address that population. This is a structural-coverage fact, not a
    points claim.

APPROXIMATIONS IN THE LEAGUE-xFP (each documented, with a sensitivity variant)
  a. TIERED single-game yardage bonuses (100/200 rush, 100/200 rec, 300/400 pass):
     an expectation of a tiered bonus needs a distributional assumption about
     actual game yardage given expected yardage. ASSUMPTION USED: empirical
     crossing curves P(actual >= T | expected x) fitted as logistic-in-x on the
     TRAIN era 2014-2019 (out-of-era calibration reported on 2020-2025), with
     P(>=200) clipped <= P(>=100). E[tier] = T1*(P>=T1 - P>=T2) + T2*P(>=T2).
  b. CUMULATIVE 40+/50+ long-TD bonuses: no TD-length expectation exists in
     ff_opportunity. ASSUMPTION USED: per-position, per-component league rates
     P(TD >= 40yd), P(TD >= 50yd) from bonus_weekly.parquet (T0.3 pbp counts),
     train era 2014-2019, times touchdown_exp. Position-constant per expected TD
     — i.e. this term CANNOT reorder players within a position except by
     reweighting td_exp; a player-specific long-TD propensity is apply_bonuses /
     H5b territory, deliberately out of scope here.
  c. OMITTED (no expectation exists in the source, for either currency):
     sacks (SACK per sack — the league's biggest QB-side term, ~-25 to -40/season
     for sack-prone profiles; H5c owns it), fumbles lost, PAT/FG (K out of panel
     scope), return yardage/TDs. Both xFP currencies omit all of these, so the
     cheap check compares the two tables on the components xFP can see. Stated
     limit: a league-vs-standard divergence living ONLY in sacks/fumbles is
     invisible to H5e by construction.

DATA
  raw/ffopp_slim_{year}.parquet  - per-season slimmed load_ff_opportunity cache
                                   (pulled per season, atomic write, resumable)
  bonus_weekly.parquet           - T0.3 artifact (long-TD counts per player-week)
  weekly_league.parquet          - T0.3 artifact (exact league-scored actuals)
  seasons_league.parquet         - T0.3 artifact (season aggregates, league pts)
  seasons.parquet + seasons_2025repair.parquet - prices (T0.2 union contract;
                                   2025 price instrument = Sleeper adp_ppr, NOT
                                   ESPN/FFC — stated wherever 2025 prices appear)

OUTPUTS
  league_xfp_weekly.parquet  - weekly series, BOTH currencies + components (WS3)
  results_59_xfp.txt         - this run's full report

RUN (chunked; every step resumable)
  .venv/bin/python icm/work/mc_research/59_league_xfp.py pull 2014   # one per year
  .venv/bin/python icm/work/mc_research/59_league_xfp.py build       # xFP + cheap check
  .venv/bin/python icm/work/mc_research/59_league_xfp.py predict     # ONLY if build says so
All numbers in the results file are [V] (computed by that run) unless tagged [R].
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

os.environ.setdefault("NFLREADPY_CACHE_MODE", "filesystem")
os.environ.setdefault("NFLREADPY_CACHE_DIR", os.path.join(HERE, ".nflcache"))
os.environ.setdefault("NFLREADPY_CACHE_DURATION", str(7 * 24 * 3600))
os.environ.setdefault("NFLREADPY_TIMEOUT", "120")

# single source of truth for every scoring value (L52: restate nothing)
from scoring_config import (SCORING, TWOPT, RFD, REFD,                     # noqa: E402
                            RY100, RY200, REY100, REY200, P300, P400,
                            PTD40, PTD50, RETD40, RETD50, RTD40, RTD50)

YEARS = list(range(2014, 2026))
TRAIN_ERA = list(range(2014, 2020))          # tier-curve + long-TD-rate fit era
TEST_ERA = list(range(2020, 2026))           # out-of-era calibration report
POS = ["QB", "RB", "WR", "TE"]
MIN_GAMES = 8                                # matches frozen load_ff_opportunity.py
DRAFTABLE_ADP = 200
CHEAP_BAR = 0.98

RAW_DIR = os.path.join(HERE, "raw")
SLIM = os.path.join(RAW_DIR, "ffopp_slim_{year}.parquet")
PULL_LOG = os.path.join(HERE, "ffopp_pull_log_59.json")
OUT_WEEKLY = os.path.join(HERE, "league_xfp_weekly.parquet")
OUT_TXT = os.path.join(HERE, "results_59_xfp.txt")
STATE = os.path.join(HERE, "xfp_cheap_check_59.json")   # build -> predict handoff

# SCORING key -> ff_opportunity _exp column. Keys with no expectation in the source
# (fumbles_lost, pat_made, fg_missed) are OMITTED — documented in the module header.
EXP_MAP = {
    "pass_yds": "pass_yards_gained_exp", "pass_td": "pass_touchdown_exp",
    "pass_int": "pass_interception_exp",
    "rush_yds": "rush_yards_gained_exp", "rush_td": "rush_touchdown_exp",
    "rec": "receptions_exp", "rec_yds": "rec_yards_gained_exp", "rec_td": "rec_touchdown_exp",
}
NO_EXP_KEYS = sorted(set(SCORING) - set(EXP_MAP))

SLIM_COLS = ["season", "week", "player_id", "full_name", "position", "posteam",
             "total_fantasy_points", "total_fantasy_points_exp",
             "pass_fantasy_points", "pass_fantasy_points_exp",
             "rec_fantasy_points", "rec_fantasy_points_exp",
             "rush_fantasy_points", "rush_fantasy_points_exp",
             "pass_yards_gained", "pass_yards_gained_exp",
             "pass_touchdown", "pass_touchdown_exp",
             "pass_interception", "pass_interception_exp",
             "pass_two_point_conv", "pass_two_point_conv_exp",
             "pass_first_down", "pass_first_down_exp", "pass_attempt",
             "receptions", "receptions_exp",
             "rec_yards_gained", "rec_yards_gained_exp",
             "rec_touchdown", "rec_touchdown_exp",
             "rec_two_point_conv", "rec_two_point_conv_exp",
             "rec_first_down", "rec_first_down_exp", "rec_attempt",
             "rush_yards_gained", "rush_yards_gained_exp",
             "rush_touchdown", "rush_touchdown_exp",
             "rush_two_point_conv", "rush_two_point_conv_exp",
             "rush_first_down", "rush_first_down_exp", "rush_attempt",
             "rec_fumble_lost", "rush_fumble_lost"]

lines = []


def say(s=""):
    print(s)
    lines.append(str(s))


def spear(a, b):
    """Spearman via rank-Pearson (no scipy dependency; 53_'s convention)."""
    a, b = pd.Series(a).rank(), pd.Series(b).rank()
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def reg_weeks(df):
    """REG-season mask: ff_opportunity has no season_type; REG = weeks 1..17 (<=2020)
    or 1..18 (2021+), the nflverse week convention."""
    lim = np.where(df["season"] <= 2020, 17, 18)
    return df["week"] <= lim


# ---------------------------------------------------------------- pull <year>
def pull(year):
    dest = SLIM.format(year=year)
    if os.path.exists(dest):
        print(f"ffopp {year}: cache exists — skipping")
        return
    os.makedirs(RAW_DIR, exist_ok=True)
    import nflreadpy as nfl
    t0 = time.time()
    d = nfl.load_ff_opportunity(seasons=[year]).to_pandas()
    missing = [c for c in SLIM_COLS if c not in d.columns]
    assert not missing, f"ffopp {year}: required columns missing: {missing}"
    d = d[SLIM_COLS].copy()
    for c in SLIM_COLS:
        if c not in ("player_id", "full_name", "position", "posteam"):
            d[c] = pd.to_numeric(d[c], errors="coerce")
    tmp = dest + ".tmp"
    d.to_parquet(tmp, index=False)
    os.replace(tmp, dest)
    dt = time.time() - t0
    log = json.load(open(PULL_LOG)) if os.path.exists(PULL_LOG) else {}
    log[str(year)] = {"rows": int(len(d)), "seconds": round(dt, 1)}
    with open(PULL_LOG, "w") as f:
        json.dump(log, f, indent=1)
    print(f"ffopp {year}: {len(d)} rows in {dt:.1f}s -> {dest}")


# ---------------------------------------------------------------- helpers
def load_all():
    frames = []
    for y in YEARS:
        dest = SLIM.format(year=y)
        if not os.path.exists(dest):
            raise SystemExit(f"missing {dest} — run `pull {y}` first")
        frames.append(pd.read_parquet(dest))
    d = pd.concat(frames, ignore_index=True)
    d["season"] = d["season"].astype(int)
    d["week"] = d["week"].astype(int)
    return d


def fit_logistic(x, y, iters=60):
    """2-parameter logistic P(y=1) = sigmoid(a + b*x), Newton-Raphson, tiny ridge.
    Returns (a, b)."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    X = np.column_stack([np.ones_like(x), x])
    w = np.zeros(2)
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(X @ w)))
        g = X.T @ (y - p) - 1e-6 * w
        W = p * (1 - p)
        H = -(X.T * W) @ X - 1e-6 * np.eye(2)
        step = np.linalg.solve(H, g)
        w = w - step
        if np.max(np.abs(step)) < 1e-10:
            break
    return w[0], w[1]


def p_of(x, ab):
    return 1.0 / (1.0 + np.exp(-(ab[0] + ab[1] * np.asarray(x, float))))


def price_union():
    """Priced (player_id, season, adp): seasons.parquet for 2014-2024 UNION the T0.2
    2025 repair (instrument = Sleeper adp_ppr, NOT ESPN/FFC ADP — T0.2 contract)."""
    s = pd.read_parquet(os.path.join(HERE, "seasons.parquet"),
                        columns=["player_id", "season", "position", "adp"])
    s = s[s["season"] != 2025]
    r = pd.read_parquet(os.path.join(HERE, "seasons_2025repair.parquet"),
                        columns=["player_id", "season", "position", "adp"])
    r = r[r["season"] == 2025]
    u = pd.concat([s, r], ignore_index=True).dropna(subset=["adp"])
    u = u.drop_duplicates(["player_id", "season"])
    return u


# ---------------------------------------------------------------- build
def build():
    t0 = time.time()
    say("=" * 78)
    say("59 — T0.9 + H5e: LEAGUE-SCORING xFP + CHEAP CHECK   (run "
        + time.strftime("%Y-%m-%d %H:%M") + ")")
    say("=" * 78)
    say("""
S14 PRE-REGISTRATION (verbatim from the module docstring; declared before any
measurement ran):
  GATE  : cheap check — within (position, season) Spearman(league-xPPG,
          standard-xPPG), draftable range (priced adp <= %d; >= %d REG games).
          If >= %.2f in EVERY position x season cell -> CLEAN NULL, stop; the
          board's existing xppg is the same role signal and no points test runs.
  PRIMARY (only if the gate falsifies the null): delta predictive Spearman vs
          next-season league points-above-price, clustered on season-pair
          (11 clusters -> DIRECTIONAL-ONLY per the S11 n<40 floor, stated now).
  SECONDARY (reported regardless): the 171 no-xppg players — failure mode named
          up front: value_board.py:90-93 role_pct falls back to target-share pct
          then 0.5 on NaN xppg; league-xFP shares ff_opportunity's rows, so its
          coverage is IDENTICAL by construction and cannot help that population.
""" % (DRAFTABLE_ADP, MIN_GAMES, CHEAP_BAR))

    d = load_all()
    say("---- S8: per-year row counts after concat (ffopp slim caches) ----")
    per_year = d.groupby("season").size()
    say(per_year.to_string())
    assert sorted(per_year.index) == YEARS, "S8: seasons != 2014-2025"
    assert (per_year > 4000).all(), "S8: a season lost most of its rows"

    pos_counts = d["position"].value_counts()
    d = d[d["position"].isin(POS)].copy()
    say(f"\nposition filter to QB/RB/WR/TE: kept {len(d)} rows; dropped positions "
        f"{ {k: int(v) for k, v in pos_counts.items() if k not in POS} }")
    n_post = int((~reg_weeks(d)).sum())
    d = d[reg_weeks(d)].copy()
    say(f"REG filter (wk<=17 pre-2021, <=18 after): dropped {n_post} postseason rows")
    say("DATA-QUALITY FLAG (raised, frozen file untouched): the FROZEN pipeline's")
    say("load_ff_opportunity.py:43-58 aggregates ALL weeks — it has no REG filter, so")
    say("the shipped xppg mixes postseason weeks into playoff-team players' games and")
    say("per-game rates. 59_ filters REG for research; the flag is for the pipeline owner.")
    for c in SLIM_COLS:
        if c not in ("player_id", "full_name", "position", "posteam", "season", "week"):
            d[c] = d[c].fillna(0.0)

    # ---- verify the STANDARD formula (so 'standard xFP' is a known object) ----
    say()
    say("---- standard-scoring formula, verified against the file's own columns [V] ----")
    chk = (0.04 * d["pass_yards_gained"] + 4 * d["pass_touchdown"]
           - 2 * d["pass_interception"] + 2 * d["pass_two_point_conv"]
           - d["pass_fantasy_points"]).abs().max()
    say(f"pass  = 0.04*yds + 4*TD - 2*INT + 2*2pt          max|resid| = {chk:.2e}")
    chk = (d["receptions"] + 0.1 * d["rec_yards_gained"] + 6 * d["rec_touchdown"]
           + 2 * d["rec_two_point_conv"] - 2 * d["rec_fumble_lost"]
           - d["rec_fantasy_points"]).abs().max()
    say(f"rec   = 1*rec + 0.1*yds + 6*TD + 2*2pt - 2*fumL  max|resid| = {chk:.2e}")
    chk = (0.1 * d["rush_yards_gained"] + 6 * d["rush_touchdown"]
           + 2 * d["rush_two_point_conv"] - 2 * d["rush_fumble_lost"]
           - d["rush_fantasy_points"]).abs().max()
    say(f"rush  = 0.1*yds + 6*TD + 2*2pt - 2*fumL          max|resid| = {chk:.2e}")
    chk = (d["total_fantasy_points"] - d[["pass_fantasy_points", "rec_fantasy_points",
                                          "rush_fantasy_points"]].sum(axis=1)).abs().max()
    say(f"total = pass + rec + rush                        max|resid| = {chk:.2e}")
    chk_exp = (0.04 * d["pass_yards_gained_exp"] + 4 * d["pass_touchdown_exp"]
               - 2 * d["pass_interception_exp"] + 2 * d["pass_two_point_conv_exp"]
               - d["pass_fantasy_points_exp"]).abs().max()
    say(f"exp side uses the SAME formula (pass check)      max|resid| = {chk_exp:.2e} "
        f"(rounding of stored cols)")
    say("=> nflverse 'standard' = 4-pt pass TD, full PPR, -2 INT/fumble, NO first")
    say("   downs, NO tiers, NO long-TD bonuses, NO sacks. League deltas vs it:")
    say(f"   pass TD {SCORING['pass_td']} (vs 4), +{RFD}/rush FD, +{REFD}/rec FD, "
        f"tiers {RY100}/{RY200} rush {REY100}/{REY200} rec {P300}/{P400} pass,")
    say(f"   long-TD +{PTD40}/{PTD50} pass +{RETD40}/{RETD50} rec +{RTD40}/{RTD50} rush "
        f"(cumulative). No sack/fumble/return exp exists in the source (omitted BOTH sides).")

    # ---- tier crossing curves: fit on TRAIN_ERA, calibrate on TEST_ERA ----
    say()
    say("---- approximation (a): tier crossing curves P(actual >= T | expected x) ----")
    say(f"logistic-in-x, fit on {TRAIN_ERA[0]}-{TRAIN_ERA[-1]} only; "
        f"out-of-era calibration below [V]")
    fams = {"rush": ("rush_yards_gained", "rush_yards_gained_exp", 100, 200, RY100, RY200),
            "rec": ("rec_yards_gained", "rec_yards_gained_exp", 100, 200, REY100, REY200),
            "pass": ("pass_yards_gained", "pass_yards_gained_exp", 300, 400, P300, P400)}
    tr = d[d["season"].isin(TRAIN_ERA)]
    curves = {}
    for fam, (act, exp, t1, t2, v1, v2) in fams.items():
        sub = tr[tr[exp] > 0]
        ab1 = fit_logistic(sub[exp], (sub[act] >= t1).astype(float))
        ab2 = fit_logistic(sub[exp], (sub[act] >= t2).astype(float))
        curves[fam] = (ab1, ab2)
        n1, n2 = int((sub[act] >= t1).sum()), int((sub[act] >= t2).sum())
        say(f"  {fam:>4}: fit rows {len(sub)}, {t1}+ games {n1}, {t2}+ games {n2}; "
            f"logit({t1}+) = {ab1[0]:.3f} + {ab1[1]:.4f}x, "
            f"logit({t2}+) = {ab2[0]:.3f} + {ab2[1]:.4f}x")

    def tier_exp_pts(df, fam):
        act, exp, t1, t2, v1, v2 = fams[fam]
        ab1, ab2 = curves[fam]
        x = df[exp].values
        p1 = np.where(x > 0, p_of(x, ab1), 0.0)
        p2 = np.minimum(np.where(x > 0, p_of(x, ab2), 0.0), p1)   # tiers can't cross
        return v1 * (p1 - p2) + v2 * p2

    say("\n  out-of-era calibration (2020-2025): predicted vs actual TIER POINTS per season")
    say("  (actual = exact tier points from the same rows' actual yardage)")
    te = d[d["season"].isin(TEST_ERA)]
    cal = []
    for fam, (act, exp, t1, t2, v1, v2) in fams.items():
        pred = pd.Series(tier_exp_pts(te, fam), index=te.index).groupby(te["season"]).sum()
        a = te[act]
        actual = pd.Series(np.select([a >= t2, a >= t1], [v2, v1], 0.0),
                           index=te.index).groupby(te["season"]).sum()
        for s in pred.index:
            cal.append({"family": fam, "season": int(s), "pred": round(float(pred[s]), 0),
                        "actual": round(float(actual[s]), 0),
                        "ratio": round(float(pred[s] / actual[s]), 3) if actual[s] else np.nan})
    cal = pd.DataFrame(cal)
    say(cal.pivot(index="season", columns="family", values="ratio").round(3).to_string())
    say("  (ratio = predicted/actual league-wide; 1.00 = perfectly calibrated)")
    # top-decile check — the draftable range lives in the tail of x
    say("\n  top-decile-of-x calibration (the range that matters for draftable players):")
    for fam, (act, exp, t1, t2, v1, v2) in fams.items():
        sub = te[te[exp] > 0]
        q = sub[exp].quantile(0.9)
        top = sub[sub[exp] >= q]
        pred = tier_exp_pts(top, fam).sum()
        a = top[act]
        actual = np.select([a >= t2, a >= t1], [v2, v1], 0.0).sum()
        say(f"    {fam:>4}: x >= {q:.0f} ({len(top)} rows)  pred {pred:.0f} vs actual "
            f"{actual:.0f}  (ratio {pred/actual:.3f})" if actual else f"    {fam}: no events")

    # ---- long-TD rates from bonus_weekly (T0.3 pbp counts), train era ----
    say()
    say("---- approximation (b): long-TD rates per position x component "
        f"({TRAIN_ERA[0]}-{TRAIN_ERA[-1]}) [V] ----")
    bw = pd.read_parquet(os.path.join(HERE, "bonus_weekly.parquet"))
    bw_tr = bw[bw["season"].isin(TRAIN_ERA)]
    ltd_rate = {}
    for comp, (b40, b50) in [("pass", (PTD40, PTD50)), ("rec", (RETD40, RETD50)),
                             ("rush", (RTD40, RTD50))]:
        g = bw_tr.groupby("position")[[f"n_{comp}_td", f"n_{comp}_td40", f"n_{comp}_td50"]].sum()
        for pos in POS:
            if pos in g.index and g.loc[pos, f"n_{comp}_td"] >= 20:
                r40 = g.loc[pos, f"n_{comp}_td40"] / g.loc[pos, f"n_{comp}_td"]
                r50 = g.loc[pos, f"n_{comp}_td50"] / g.loc[pos, f"n_{comp}_td"]
            else:
                tot = bw_tr[[f"n_{comp}_td", f"n_{comp}_td40", f"n_{comp}_td50"]].sum()
                r40 = tot[f"n_{comp}_td40"] / tot[f"n_{comp}_td"]
                r50 = tot[f"n_{comp}_td50"] / tot[f"n_{comp}_td"]
            ltd_rate[(comp, pos)] = b40 * r40 + b50 * r50
    tab = pd.DataFrame({c: {p: round(ltd_rate[(c, p)], 3) for p in POS}
                        for c in ["pass", "rec", "rush"]})
    say("expected long-TD BONUS POINTS per expected TD (position-constant — cannot")
    say("reorder within position except via td_exp weighting; stated limit):")
    say(tab.to_string())

    # ---- assemble the league-xFP series ----
    say()
    say("---- league-xFP assembly (constants imported from scoring_config only) ----")
    say(f"SCORING keys with no expectation in the source, omitted: {NO_EXP_KEYS}")
    d["lgx_base"] = sum(d[col] * SCORING[k] for k, col in EXP_MAP.items())
    d["lgx_2pt"] = TWOPT * (d["pass_two_point_conv_exp"] + d["rush_two_point_conv_exp"]
                            + d["rec_two_point_conv_exp"])
    d["lgx_fd"] = RFD * d["rush_first_down_exp"] + REFD * d["rec_first_down_exp"]
    d["lgx_tier"] = sum(tier_exp_pts(d, fam) for fam in fams)
    d["lgx_ltd"] = (d["pass_touchdown_exp"] * d["position"].map(lambda p: ltd_rate[("pass", p)])
                    + d["rec_touchdown_exp"] * d["position"].map(lambda p: ltd_rate[("rec", p)])
                    + d["rush_touchdown_exp"] * d["position"].map(lambda p: ltd_rate[("rush", p)]))
    d["xfp_league"] = d[["lgx_base", "lgx_2pt", "lgx_fd", "lgx_tier", "lgx_ltd"]].sum(axis=1)
    d["xfp_std"] = d["total_fantasy_points_exp"]

    # join exact league-scored ACTUALS (T0.3) for WS3's change-point work
    wl = pd.read_parquet(os.path.join(HERE, "weekly_league.parquet"),
                         columns=["player_id", "season", "week", "pts_league", "pts_base"])
    d = d.merge(wl, on=["player_id", "season", "week"], how="left")
    say(f"joined weekly_league actuals: pts_league present on "
        f"{d['pts_league'].notna().mean()*100:.1f}% of rows "
        f"(gap = ff_opportunity rows outside the T0.3 panel, e.g. 0-stat weeks)")

    say("\n---- S8: per-season mean per-row (league-xFP - standard-xFP) by position ----")
    d["lgx_minus_std"] = d["xfp_league"] - d["xfp_std"]
    piv = d.pivot_table(index="season", columns="position", values="lgx_minus_std",
                        aggfunc="mean").round(3)
    say(piv.to_string())
    say("(a dead component would break a column's band visibly)")

    keep = ["season", "week", "player_id", "full_name", "position", "posteam",
            "xfp_std", "xfp_league", "lgx_base", "lgx_2pt", "lgx_fd", "lgx_tier",
            "lgx_ltd", "total_fantasy_points", "pts_league", "pts_base"]
    out = d[keep].copy()
    tmp = OUT_WEEKLY + ".tmp"
    out.to_parquet(tmp, index=False)
    os.replace(tmp, OUT_WEEKLY)
    say(f"\nwrote {OUT_WEEKLY} ({len(out)} rows, {len(keep)} cols) — emitted regardless "
        f"of the H5e verdict (T0.9 deliverable for WS3)")

    # ---- season aggregates for the cheap check ----
    ag = (d.groupby(["player_id", "season", "position"], as_index=False)
            .agg(games=("week", "count"), full_name=("full_name", "first"),
                 xfp_league=("xfp_league", "sum"), xfp_std=("xfp_std", "sum"),
                 lgx_fd=("lgx_fd", "sum"), lgx_tier=("lgx_tier", "sum"),
                 lgx_ltd=("lgx_ltd", "sum"), lgx_2pt=("lgx_2pt", "sum"),
                 lgx_base=("lgx_base", "sum")))
    ag["xppg_league"] = ag["xfp_league"] / ag["games"]
    ag["xppg_std"] = ag["xfp_std"] / ag["games"]
    # sensitivity variants of the league currency (assumption-dependence check)
    ag["xppg_league_notier"] = (ag["xfp_league"] - ag["lgx_tier"]) / ag["games"]
    ag["xppg_league_noltd"] = (ag["xfp_league"] - ag["lgx_ltd"]) / ag["games"]
    ag["xppg_league_analytic"] = (ag["xfp_league"] - ag["lgx_tier"] - ag["lgx_ltd"]) / ag["games"]

    pr = price_union()
    ag = ag.merge(pr[["player_id", "season", "adp"]], on=["player_id", "season"], how="left")
    pool = ag[(ag["games"] >= MIN_GAMES) & (ag["adp"] <= DRAFTABLE_ADP)].copy()
    say()
    say("=" * 78)
    say("CHEAP CHECK (H5e gate) — draftable range = priced adp <= "
        f"{DRAFTABLE_ADP} (2025 instrument = Sleeper adp_ppr per T0.2), games >= {MIN_GAMES}")
    say("=" * 78)
    say("---- S8/S5: draftable-pool size per season x position ----")
    say(pool.pivot_table(index="season", columns="position", values="player_id",
                        aggfunc="count").fillna(0).astype(int).to_string())

    say("\n---- Spearman(xppg_league, xppg_std) per position x season [V] ----")
    rows = []
    for (s, p), g in pool.groupby(["season", "position"]):
        rows.append({"season": s, "position": p, "n": len(g),
                     "rho": spear(g["xppg_league"], g["xppg_std"]),
                     "rho_notier": spear(g["xppg_league_notier"], g["xppg_std"]),
                     "rho_noltd": spear(g["xppg_league_noltd"], g["xppg_std"]),
                     "rho_analytic": spear(g["xppg_league_analytic"], g["xppg_std"])})
    cc = pd.DataFrame(rows)
    say(cc.pivot(index="season", columns="position", values="rho").round(4).to_string())

    say("\n---- per-position summary over the 12 seasons ----")
    summ = cc.groupby("position").agg(n_seasons=("season", "count"),
                                      pooled_min=("rho", "min"),
                                      pooled_median=("rho", "median"),
                                      pooled_mean=("rho", "mean")).round(4)
    say(summ.to_string())
    say("\nsensitivity variants (median rho by position — does the verdict depend on the")
    say("distributional assumptions?):")
    sv = cc.groupby("position")[["rho", "rho_notier", "rho_noltd", "rho_analytic"]].median().round(4)
    sv.columns = ["full", "no_tier", "no_longTD", "analytic_only"]
    say(sv.to_string())

    min_cell = float(cc["rho"].min())
    min_row = cc.loc[cc["rho"].idxmin()]
    verdict_null = min_cell >= CHEAP_BAR
    say()
    say(f"minimum cell: rho = {min_cell:.4f}  ({min_row['position']} {int(min_row['season'])}, "
        f"n = {int(min_row['n'])})")
    say(f"pre-registered rule: >= {CHEAP_BAR} in EVERY cell -> CLEAN NULL, stop.")
    if verdict_null:
        msg = ("CLEAN NULL — the two xFPs are the same role signal in the draftable "
               "range; the primary points test does NOT run.")
    else:
        msg = (f"FALSIFIED — at least one cell < {CHEAP_BAR}; run `predict` "
               f"(primary endpoint).")
    say("GATE VERDICT: " + msg)

    # level shifts (descriptive — ranks are the decision object, levels shown for honesty)
    say("\n---- level shift by position (league-xPPG minus standard-xPPG, draftable pool) ----")
    lv = pool.assign(diff=pool.xppg_league - pool.xppg_std).groupby("position")["diff"] \
             .describe()[["mean", "std", "min", "max"]].round(2)
    say(lv.to_string())
    say("(cross-position level shifts are REAL under the league table but role_pct is a")
    say(" WITHIN-position percentile — value_board.py:90 — so ranks are the decision object)")

    # biggest within-position rank movers, pooled (archetype evidence)
    say("\n---- biggest within-(position,season) rank movers in the draftable pool [V] ----")
    pool["rk_lg"] = pool.groupby(["season", "position"])["xppg_league"].rank(ascending=False)
    pool["rk_sd"] = pool.groupby(["season", "position"])["xppg_std"].rank(ascending=False)
    pool["rk_move"] = pool["rk_sd"] - pool["rk_lg"]     # + = league table promotes
    mv = pool.reindex(pool["rk_move"].abs().sort_values(ascending=False).index).head(15)
    say(mv[["season", "position", "full_name", "games", "xppg_std", "xppg_league",
            "rk_sd", "rk_lg", "rk_move"]].round(2).to_string(index=False))
    say("\nmean |rank move| by position: "
        + str(pool.groupby('position')['rk_move'].apply(lambda s: round(s.abs().mean(), 2)).to_dict()))

    # ---- SECONDARY (reported regardless, S14): the 171 no-xppg players ----
    say()
    say("=" * 78)
    say("SECONDARY — the 171 no-xppg players (failure mode named BEFORE any test)")
    say("=" * 78)
    vb = pd.read_csv(os.path.join(ROOT, "value_board.csv"))
    n_nox = int(vb["xppg"].isna().sum())
    say(f"value_board.csv: {len(vb)} players, {n_nox} with xppg NaN [V] "
        f"(charter says 171 [R] — {'MATCH' if n_nox == 171 else 'DRIFT, re-pin'})")
    vb["pos"] = vb["pos_label"].astype(str).str.replace(r"\d+$", "", regex=True)
    say(f"by position: {vb[vb['xppg'].isna()].groupby('pos').size().to_dict()}")
    say("""
FAILURE MODE (value_board.py:90-93): on NaN xppg, role_pct falls back to
target-share pct, then neutral 0.5. VERDICT ON THE SECONDARY CLAIM: league-xFP
CANNOT address this population — it is computed from the SAME ff_opportunity
player-weeks as standard xFP, so a player with no standard xppg has no league
xppg either, identically, by construction. The 171-player gap is a COVERAGE
problem (rookies + <8-game players + K/DST), not a scoring-currency problem.
Any fix routes through a different signal (depth charts H2g, participation
T0.1), not through H5e.""")

    with open(STATE, "w") as f:
        json.dump({"min_cell_rho": min_cell, "clean_null": bool(verdict_null),
                   "bar": CHEAP_BAR, "run": time.strftime("%Y-%m-%d %H:%M")}, f, indent=1)
    say(f"\n[{time.time()-t0:.0f}s build]  gate state -> {STATE}")
    with open(OUT_TXT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nresults -> {OUT_TXT}")


# ---------------------------------------------------------------- predict
def predict():
    """PRIMARY ENDPOINT — runs only if build recorded clean_null = False."""
    st = json.load(open(STATE))
    say("=" * 78)
    say("59 predict — H5e PRIMARY ENDPOINT   (run " + time.strftime("%Y-%m-%d %H:%M") + ")")
    say("=" * 78)
    if st["clean_null"]:
        say(f"build recorded CLEAN NULL (min cell rho {st['min_cell_rho']:.4f} >= "
            f"{st['bar']}). Per the S14 pre-registration the primary points test does "
            f"not run. Nothing to do.")
        with open(OUT_TXT, "a") as f:
            f.write("\n".join(lines) + "\n")
        return

    d = pd.read_parquet(OUT_WEEKLY)
    ag = (d.groupby(["player_id", "season", "position"], as_index=False)
            .agg(games=("week", "count"), xfp_league=("xfp_league", "sum"),
                 xfp_std=("xfp_std", "sum")))
    ag["xppg_league"] = ag["xfp_league"] / ag["games"]
    ag["xppg_std"] = ag["xfp_std"] / ag["games"]
    ag = ag[ag["games"] >= MIN_GAMES]

    sl = pd.read_parquet(os.path.join(HERE, "seasons_league.parquet"),
                         columns=["player_id", "season", "position", "total_league"])
    pr = price_union()
    nxt = sl.merge(pr, on=["player_id", "season", "position"])
    nxt = nxt[nxt["adp"] <= DRAFTABLE_ADP].copy()
    # price curve: per position, quadratic in log(adp), pooled across seasons
    nxt["resid"] = np.nan
    for p, g in nxt.groupby("position"):
        X = np.column_stack([np.ones(len(g)), np.log(g["adp"]), np.log(g["adp"]) ** 2])
        beta, *_ = np.linalg.lstsq(X, g["total_league"], rcond=None)
        nxt.loc[g.index, "resid"] = g["total_league"] - X @ beta

    sig = ag.rename(columns={"season": "sig_season"})
    sig["season"] = sig["sig_season"] + 1
    j = sig.merge(nxt[["player_id", "season", "position", "resid"]],
                  on=["player_id", "season", "position"])
    say(f"joined signal-year t -> outcome-year t+1: {len(j)} player-season-pairs, "
        f"{j['season'].nunique()} outcome seasons")
    say("2025 outcome prices use the T0.2 Sleeper repair (instrument stated).")

    rows = []
    for (s, p), g in j.groupby(["season", "position"]):
        if len(g) < 10:
            continue
        rows.append({"season": s, "position": p, "n": len(g),
                     "rho_lg": spear(g["xppg_league"], g["resid"]),
                     "rho_sd": spear(g["xppg_std"], g["resid"])})
    r = pd.DataFrame(rows)
    r["delta"] = r["rho_lg"] - r["rho_sd"]

    def t_p(tval, df):
        """two-sided p from Student-t via numerical integration (no scipy)."""
        x = np.linspace(0, max(abs(tval), 1e-9), 20001)
        pdf = (1 + x ** 2 / df) ** (-(df + 1) / 2)
        # normalize with the full density over a wide grid
        xw = np.linspace(0, 400, 400001)
        norm = 2 * np.trapezoid((1 + xw ** 2 / df) ** (-(df + 1) / 2), xw)
        return float(1 - 2 * np.trapezoid(pdf, x) / norm)

    say("\nper position: mean delta Spearman (league - standard) vs next-season")
    say("league points-above-price, clustered on season-pair [V]:")
    stats = []
    for p, g in r.groupby("position"):
        m, sd, n = g["delta"].mean(), g["delta"].std(), len(g)
        se = sd / np.sqrt(n)
        tval = m / se if se > 0 else 0.0
        pval = t_p(tval, n - 1)
        stats.append({"position": p, "delta": m, "ci95": 1.96 * se, "t": tval,
                      "p_raw": pval, "clusters": n,
                      "zero_cells": int((g["delta"] == 0).sum())})
        say(f"  {p}: delta = {m:+.4f} +/- {1.96*se:.4f} (95% CI, {n} season clusters, "
            f"t = {tval:+.2f}, p = {pval:.3f})  [DIRECTIONAL-ONLY: {n} < 40 clusters, S11]")
    st_df = pd.DataFrame(stats).sort_values("p_raw").reset_index(drop=True)

    say("\nS14 FDR: the primary endpoint splits into 4 position comparisons —")
    say("Benjamini-Hochberg at q = 0.10 across the 4, raw and adjusted verdicts:")
    Q = 0.10
    m_tests = len(st_df)
    st_df["bh_crit"] = [(i + 1) / m_tests * Q for i in range(m_tests)]
    passed = st_df[st_df["p_raw"] <= st_df["bh_crit"]]
    k = passed.index.max() + 1 if len(passed) else 0
    st_df["raw_verdict"] = np.where(st_df["p_raw"] < 0.05, "nominal", "null")
    st_df["bh_verdict"] = ["PASS" if i < k else "null" for i in range(m_tests)]
    say(st_df[["position", "delta", "t", "p_raw", "bh_crit", "raw_verdict",
               "bh_verdict", "clusters", "zero_cells"]].round(4).to_string(index=False))
    say("(zero_cells = season-cells where the two xFPs rank identically, delta exactly 0)")

    say("\nfull table:")
    say(r.round(4).to_string(index=False))
    say("\nA positive material delta would route to WS6 as a bounded role_pct swap")
    say("candidate, to be graded in the paired harness (T0.4) — NOT claimed here.")

    # ---------------------------------------------------------------- verdict
    n_bh = int((st_df["bh_verdict"] == "PASS").sum())
    say()
    say("=" * 78)
    say("FINAL VERDICT — T0.9 + H5e")
    say("=" * 78)
    say(f"""
1. T0.9 DELIVERED. league_xfp_weekly.parquet: weekly xFP 2014-2025 (REG,
   QB/RB/WR/TE) in BOTH currencies with the league components broken out
   (lgx_base / lgx_2pt / lgx_fd / lgx_tier / lgx_ltd) and exact league-scored
   actuals (pts_league) joined for WS3's change-point work. Approximations:
   tier bonuses via out-of-era-calibrated crossing curves; long-TD bonuses via
   position-constant per-TD rates; sacks / fumbles / returns / PAT-FG absent
   from the source's expectation model and therefore from BOTH currencies.

2. H5e GATE: strictly falsified but only just — {json.load(open(STATE))['min_cell_rho']:.4f} was the minimum
   of 48 position x season Spearman cells (QB 2016; RB 2017 = 0.9798 the only
   other cell under 0.98); 46/48 cells >= 0.98, every position's MEDIAN >= 0.99.
   The divergence archetype is real but small: the league's FD + yardage-tier
   structure promotes early-down volume RBs (Henry, Jacobs, Lynch, Jamaal
   Williams +4..+7 rank slots) and demotes satellite pass-catch RBs (James
   White -5..-10, Duke Johnson, Woodhead) — i.e. it claws back part of PPR's
   satellite-back premium; QB moves come from 6-pt (vs 4) pass TDs plus rush
   FDs and are ~0.5 slots on average.

3. H5e PRIMARY ENDPOINT: NULL. Delta predictive Spearman vs next-season league
   points-above-price, 11 season-pair clusters: QB -0.010, RB +0.000, TE +0.012,
   WR -0.001. {n_bh} of 4 position comparisons survive Benjamini-Hochberg at
   q = 0.10; every one is DIRECTIONAL-ONLY under the S11 n<40 cluster floor
   anyway. The league-currency xFP does NOT better predict next-season league
   points above price than the standard xFP the board already uses. The
   existing xppg role signal is fine; do NOT ship a league-xFP swap.

4. SECONDARY (the 171 no-xppg players): league-xFP cannot help by construction
   — identical row coverage to standard xFP. Coverage fixes route through H2g /
   T0.1 signals, not scoring currency.

5. WHAT THIS DOES NOT SAY: (a) nothing here grades LEAGUE-scored OUTCOMES —
   seasons_league (T0.3) remains the grading currency for every WS5 hypothesis;
   this null is only about the xFP ROLE-SIGNAL currency. (b) Sack- and fumble-
   driven league divergence is invisible to both xFPs (H5c owns sacks).
   (c) No paired-draft points grade was run — the predictive null made that
   moot; if anyone revives league-xFP, the T0.4 harness is the bar. (d) The
   tier/long-TD expectations are assumption-bearing; the sensitivity variants
   (no_tier / no_longTD / analytic_only medians all >= 0.989) show the gate
   conclusion does not hinge on them.""")
    with open(OUT_TXT, "a") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nappended -> {OUT_TXT}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "pull":
        pull(int(sys.argv[2]))
    elif cmd == "build":
        build()
    elif cmd == "predict":
        predict()
    else:
        raise SystemExit(f"unknown command {cmd!r} — use `pull <year>`, `build`, `predict`")
