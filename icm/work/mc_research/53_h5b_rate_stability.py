"""53 — H5b: year-over-year STABILITY of per-player rates for every league-average
constant in apply_bonuses.py (charter WS5/H5b; §2.6 linearization defect; §7.4).

WHAT THIS MEASURES (and what it does not)
  apply_bonuses.py (FROZEN — read-only here) multiplies projected season volume by a
  LEAGUE-AVERAGE rate for: rushing/receiving first downs, 100/200 rushing-yard games,
  100/200 receiving-yard games, 300/400 passing-yard games. The charter's real question
  (H5b): which of those rates are STABLE per player year-over-year, so that an
  EB-shrunk per-player rate beats the league average out of sample — and which are
  not, where the league average IS the right answer (a valuable null).
  This script is MEASUREMENT toward a proposal. Nothing is edited, nothing ships.
  H5b's primary endpoint (league points, corrected grader, weekly mode, bar =
  placebo 95th pct or +20) is PENDING for the Grading phase — not computed here.

STABILITY OBJECT
  Per family the analyzed rate is POINTS-PER-EXPOSURE — exactly the multiplier the
  shipped formula applies (rate x projected volume):
    rush_fd   : b_rush_fd  / carries          (= RFD  x FD-per-carry)
    rec_fd    : b_rec_fd   / receptions       (= REFD x FD-per-reception)
    rush_tier : b_rush_tier/ rushing_yards    (tiered 100/200 pts per rush yard)
    rec_tier  : b_rec_tier / receiving_yards  (tiered 100/200 pts per rec yard)
    pass_tier : b_pass_tier/ passing_yards    (tiered 300/400 pts per pass yard)
  The individual 100- vs 200-game sub-rates are reported descriptively (league drift
  table); they are too rare to carry per-player treatment on their own.

DATA  weekly_league.parquet (T0.3 artifact, 67,353 player-weeks 2014-2025, REG,
  QB/RB/WR/TE, league-scored exact per week). All numbers here are [V] (computed by
  this run) unless explicitly tagged [R].

RUN   .venv/bin/python icm/work/mc_research/53_h5b_rate_stability.py
  (local parquet only, no network; writes results_53_h5b.txt)
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

# scoring constants: single source of truth, imported not restated (L52 discipline)
from scoring_config import RFD, REFD, RY100, RY200, REY100, REY200, P300, P400  # noqa: E402

WEEKLY_LEAGUE = os.path.join(HERE, "weekly_league.parquet")
OUT_TXT = os.path.join(HERE, "results_53_h5b.txt")
YEARS = list(range(2014, 2026))
B_BOOT = 1000
RNG = np.random.default_rng(53)

lines = []


def say(s=""):
    print(s)
    lines.append(str(s))


def spear(a, b):
    """Spearman via rank-Pearson (no scipy dependency)."""
    a, b = pd.Series(a).rank(), pd.Series(b).rank()
    if a.std() == 0 or b.std() == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


# ============================================================================
# 0. PRE-REGISTRATION — printed before any measurement runs
# ============================================================================
say("=" * 78)
say("53 — H5b RATE STABILITY   (run " + time.strftime("%Y-%m-%d %H:%M") + ")")
say("=" * 78)
say("""
PRE-REGISTRATION (declared BEFORE the measurement ran; nothing below was tuned
after seeing results):

  DECISION STATISTIC per rate-family x position cell:
    Spearman correlation between the K*-shrunk year-t rate and the realized raw
    year-t+1 rate, pooled across the 11 consecutive-season pairs (2014->15 ...
    2024->25), 95% CI cluster-bootstrapped on PLAYER (S11; clusters = unique
    players; cluster count reported as effective n; <40 clusters => DIRECTIONAL-
    ONLY flag).
  BAR (from the charter, stated verbatim): shrunk YoY under ~0.3 = the league
    average wins (NULL verdict for that rate).
  COMBINED VERDICT RULE: 'PER-PLAYER CANDIDATE' requires BOTH
    (a) shrunk-YoY Spearman >= 0.3, AND
    (b) out-of-sample error improvement vs the POSITION-average predictor
        (dMAE L1-L2 > 0) with the 95% player-clustered CI excluding 0.
    'LEAGUE AVG BEATABLE VIA POSITION' if L1 beats L0 (dMAE L0-L1 CI > 0) even
    where (a)/(b) fail — the position-level rate is a free, stability-riskless fix.
    Anything else: NULL (league average wins).

  EB SHRINKAGE: shrunk_i,t = (bonus_pts_i,t + K * L1_pos,t) / (exposure_i,t + K),
    shrinkage target = POSITION-year rate (hierarchical; noted deviation from the
    in-repo long-TD precedent which shrinks to league — position gaps are exactly
    what the league constant erases, so position is the honest center).
    K is in EXPOSURE UNITS and chosen by NESTED leave-one-pair-year-out CV:
    for each held-out pair-year, K* minimizes the mean per-year MSE of predicted
    t+1 bonus points over the other 10 pair-years; the held-out year is predicted
    with that K*. A global K* (all pairs) is used only for descriptive shrunk
    correlations and spread percentiles, and is labelled as such.
  K GRIDS: FD families (carries/receptions): 0,5,10,25,50,100,200,400,800.
           Tier families (yards): 0,125,250,500,1000,2000,4000,8000,16000.

  OOS PREDICTORS of realized t+1 bonus points, all evaluated at ACTUAL t+1
  exposure (isolates the RATE from volume forecasting — stated ceiling-friendly
  design; the Grading phase must also carry volume projection error):
    L0  = league rate, year t, all positions pooled (apply_bonuses' convention)
    L1  = position rate, year t
    L2  = per-player EB-shrunk year-t rate (nested-CV K)   <- the H5b candidate
    L2b = per-player shrunk on pooled years {t-1,t} (secondary; mirrors the
          shipped file's 2-3yr pooling precedent; reuses L2's per-fold K*)
  ERROR METRIC: mean absolute error in POINTS (robust to rare 200/400-yd games);
  MSE used only inside K selection.

  EXPOSURE FLOORS (in both years of a pair):
    rush_fd carries>=50 (QB,RB) | rec_fd receptions>=25 (RB,WR,TE)
    rush_tier rush_yds>=300 (QB,RB) | rec_tier rec_yds>=300 (RB,WR,TE)
    pass_tier pass_yds>=1500 (QB)

  SPREAD (task 4): p10-p90 of shrunk rates (global K*) among qualifiers, x a
  reference volume = mean over seasons of the median exposure of the top-24
  players by that exposure at that position (top-12 for QB) — the ceiling on
  what a paired grade could find between extreme players at equal volume.

  PRIORS (stated before running): rec_fd most stable (aDOT is a stable trait);
  rush_fd moderately stable, more at QB (scramble selection) than RB; pass_tier
  weak-moderate; rush_tier/rec_tier expected NULL (rare-game noise) — i.e. we
  EXPECT the league average to win the yardage tiers and lose the first downs.

  S12 NOTE: these bonuses are worth exactly 0.0 in base PPR by construction, so
  the dual-currency report collapses — league currency only, said once here.
  S14 NOTE: this task contributes ZERO primary-endpoint tests to the charter's
  FDR count; the decision statistics above are measurement screens, and H5b's
  single primary endpoint remains the pending Grading-phase points test.
""")

# ============================================================================
# 1. CENSUS — every league-average rate apply_bonuses.py applies (task 1)
# ============================================================================
say("=" * 78)
say("1. CENSUS OF LEAGUE-AVERAGE CONSTANTS IN apply_bonuses.py (read-only [V])")
say("=" * 78)
say("""
Applied UNIFORMLY to every player (league rate x projected volume) — IN SCOPE:
  fd_carry    line 60, applied line 95  rushing FDs / carries  (x rush_att x RFD)
  fd_rec      line 61, applied line 96  receiving FDs / receptions (x rec x REFD)
  r_rush100/200  line 57, applied 93    100-199 / 200+ rush-yd games per rush yard
  r_rec100/200   line 58, applied 94    100-199 / 200+ rec-yd games per rec yard
  r_pass300/400  line 59, applied 92    300-399 / 400+ pass-yd games per pass yard
  (all computed on load_player_stats 2024+2025 REG, ALL positions pooled)

League-average but OUT of named H5b scope (census only, reasons):
  L_pass40/50, L_rush40/50  lines 17-18  long-TD length rates — FALLBACK ONLY for
      players w/o history (lines 79-81); the applied rates are PER-PLAYER EB-shrunk
      K=12 (lines 20-28) = the in-repo precedent that per-player is viable.
  L_sack      line 40   fallback only; per-QB shrunk rate ships (H5c's domain).
  r_2pass/r_2run  46-47  2pt per TD — league by design ('too rare/situational for
      per-player shrinkage', file's own comment line 43). Not re-litigated.
  L_patmiss   line 51   PAT miss — K position; panel has no K rows (§6 scope cut).
  fg_ppm      lines 30-32  FG distance mix — K position; same scope cut.
  ret_pts     lines 63-67  per-player backward actuals, not a league average;
      reads the dead pt_return_tds column — flag already raised by T0.3 [R].
""")

# ============================================================================
# 2. LOAD + S8
# ============================================================================
wl = pd.read_parquet(WEEKLY_LEAGUE)
assert len(wl) == 67353, "S8: weekly_league row count changed"
per_year = wl.groupby("season").size()
assert sorted(per_year.index) == YEARS and (per_year > 5000).all(), "S8: season counts"
say("=" * 78)
say("2. INPUT — weekly_league.parquet (T0.3), S8 per-year rows [V]")
say("=" * 78)
say(per_year.to_string())

# player-season aggregates
wl["_g100_ry"] = ((wl.rushing_yards >= 100) & (wl.rushing_yards < 200)).astype(int)
wl["_g200_ry"] = (wl.rushing_yards >= 200).astype(int)
wl["_g100_rey"] = ((wl.receiving_yards >= 100) & (wl.receiving_yards < 200)).astype(int)
wl["_g200_rey"] = (wl.receiving_yards >= 200).astype(int)
wl["_g300_py"] = ((wl.passing_yards >= 300) & (wl.passing_yards < 400)).astype(int)
wl["_g400_py"] = (wl.passing_yards >= 400).astype(int)

sea = wl.groupby(["player_id", "season", "position"], as_index=False).agg(
    name=("player_display_name", "first"), games=("week", "size"),
    car=("carries", "sum"), rec=("receptions", "sum"),
    ry=("rushing_yards", "sum"), rey=("receiving_yards", "sum"), py=("passing_yards", "sum"),
    fd_rush=("rushing_first_downs", "sum"), fd_rec=("receiving_first_downs", "sum"),
    b_rush_fd=("b_rush_fd", "sum"), b_rec_fd=("b_rec_fd", "sum"),
    b_rush_tier=("b_rush_tier", "sum"), b_rec_tier=("b_rec_tier", "sum"),
    b_pass_tier=("b_pass_tier", "sum"),
    g100_ry=("_g100_ry", "sum"), g200_ry=("_g200_ry", "sum"),
    g100_rey=("_g100_rey", "sum"), g200_rey=("_g200_rey", "sum"),
    g300_py=("_g300_py", "sum"), g400_py=("_g400_py", "sum"))
assert sea["games"].sum() == 67353, "S8: season aggregate loses player-weeks"
say(f"\nplayer-seasons: {len(sea)}  (games sum back to 67,353 [V]); per-year:")
say(sea.groupby("season").size().to_string())

# ============================================================================
# 3. LEAGUE-RATE DRIFT — the 8 named raw rates per season (descriptive)
# ============================================================================
say()
say("=" * 78)
say("3. LEAGUE-RATE DRIFT PER SEASON (computed exactly as apply_bonuses does,")
say("   restricted to the QB/RB/WR/TE panel — K/DST/FB rows excluded, negligible")
say("   for these denominators). apply_bonuses ships the 2024+2025 pooled value.")
say("=" * 78)
drift = []
for y in YEARS:
    g = wl[wl.season == y]
    drift.append({
        "season": y,
        "fd_carry": g.rushing_first_downs.sum() / g.carries.sum(),
        "fd_rec": g.receiving_first_downs.sum() / g.receptions.sum(),
        "r_rush100": g._g100_ry.sum() / g.rushing_yards.sum(),
        "r_rush200": g._g200_ry.sum() / g.rushing_yards.sum(),
        "r_rec100": g._g100_rey.sum() / g.receiving_yards.sum(),
        "r_rec200": g._g200_rey.sum() / g.receiving_yards.sum(),
        "r_pass300": g._g300_py.sum() / g.passing_yards.sum(),
        "r_pass400": g._g400_py.sum() / g.passing_yards.sum(),
    })
dr = pd.DataFrame(drift).set_index("season")
say(dr.to_string(float_format=lambda v: f"{v:.5f}"))
g2425 = wl[wl.season.isin([2024, 2025])]
say("\n2024+2025 pooled (what apply_bonuses ships today, recomputed on the panel):")
say(f"  fd_carry {g2425.rushing_first_downs.sum()/g2425.carries.sum():.4f}"
    f"  (T0.3 quoted 0.237 [R])   fd_rec {g2425.receiving_first_downs.sum()/g2425.receptions.sum():.4f}")

# position-level points-per-exposure rates per year (L1) + pooled L0, all rows
FAM = {
    "rush_fd": dict(num="b_rush_fd", expo="car", floor=50, pos=["QB", "RB"],
                    kgrid=[0, 5, 10, 25, 50, 100, 200, 400, 800], unit="carries"),
    "rec_fd": dict(num="b_rec_fd", expo="rec", floor=25, pos=["RB", "WR", "TE"],
                   kgrid=[0, 5, 10, 25, 50, 100, 200, 400, 800], unit="receptions"),
    "rush_tier": dict(num="b_rush_tier", expo="ry", floor=300, pos=["QB", "RB"],
                      kgrid=[0, 125, 250, 500, 1000, 2000, 4000, 8000, 16000], unit="rush yds"),
    "rec_tier": dict(num="b_rec_tier", expo="rey", floor=300, pos=["RB", "WR", "TE"],
                     kgrid=[0, 125, 250, 500, 1000, 2000, 4000, 8000, 16000], unit="rec yds"),
    "pass_tier": dict(num="b_pass_tier", expo="py", floor=1500, pos=["QB"],
                      kgrid=[0, 125, 250, 500, 1000, 2000, 4000, 8000, 16000], unit="pass yds"),
}

L0 = {}   # (fam, year) -> league pts-per-exposure
L1 = {}   # (fam, pos, year) -> position pts-per-exposure
L1W = {}  # (fam, pos, year) -> pooled {t-1,t} position rate (for L2b)
for fam, cfg in FAM.items():
    for y in YEARS:
        gy = sea[sea.season == y]
        L0[(fam, y)] = gy[cfg["num"]].sum() / max(gy[cfg["expo"]].sum(), 1e-9)
        for pos in cfg["pos"]:
            gp = gy[gy.position == pos]
            L1[(fam, pos, y)] = gp[cfg["num"]].sum() / max(gp[cfg["expo"]].sum(), 1e-9)
            gw = sea[(sea.season.isin([y - 1, y])) & (sea.position == pos)]
            L1W[(fam, pos, y)] = gw[cfg["num"]].sum() / max(gw[cfg["expo"]].sum(), 1e-9)

say("\nposition-level points-per-exposure by year (L1; the free fix apply_bonuses'")
say("single league rate erases). Units: bonus points per carry/reception/yard.")
for fam, cfg in FAM.items():
    tbl = pd.DataFrame({pos: [L1[(fam, pos, y)] for y in YEARS] for pos in cfg["pos"]},
                       index=YEARS)
    tbl["league_L0"] = [L0[(fam, y)] for y in YEARS]
    say(f"\n{fam} (per {cfg['unit']}):")
    say(tbl.to_string(float_format=lambda v: f"{v:.5f}"))

# ============================================================================
# 4. YoY PAIRS + STABILITY + NESTED-CV SHRINKAGE + OOS
# ============================================================================
nxt = sea.copy()
nxt["season"] = nxt["season"] - 1
nxt = nxt.rename(columns={c: c + "_n" for c in nxt.columns
                          if c not in ("player_id", "season", "position")})
pairs_all = sea.merge(nxt, on=["player_id", "season", "position"], how="inner")

prv = sea.copy()
prv["season"] = prv["season"] + 1
prv = prv.rename(columns={c: c + "_p" for c in prv.columns
                          if c not in ("player_id", "season", "position")})
pairs_all = pairs_all.merge(prv, on=["player_id", "season", "position"], how="left")

PAIR_YEARS = YEARS[:-1]   # t = 2014..2024


def cell_analysis(fam, pos):
    cfg = FAM[fam]
    num, expo, floor, kgrid = cfg["num"], cfg["expo"], cfg["floor"], cfg["kgrid"]
    c = pairs_all[(pairs_all.position == pos)
                  & (pairs_all[expo] >= floor)
                  & (pairs_all[expo + "_n"] >= floor)].copy().reset_index(drop=True)
    if len(c) < 20:
        return None
    c["rate_t"] = c[num] / c[expo]
    c["rate_n"] = c[num + "_n"] / c[expo + "_n"]
    c["l0"] = c.season.map(lambda y: L0[(fam, y)])
    c["l1"] = c.season.map(lambda y: L1[(fam, pos, y)])
    c["l1w"] = c.season.map(lambda y: L1W[(fam, pos, y)])
    c["actual"] = c[num + "_n"]
    c["pred0"] = c.l0 * c[expo + "_n"]
    c["pred1"] = c.l1 * c[expo + "_n"]

    def shrunk(k, pooled=False):
        if pooled:
            n_ = c[num] + c[num + "_p"].fillna(0)
            e_ = c[expo] + c[expo + "_p"].fillna(0)
            return (n_ + k * c.l1w) / (e_ + k)
        return (c[num] + k * c.l1) / (c[expo] + k)

    # MSE by (K, pair-year) for nested CV
    mse = {k: c.assign(err=(shrunk(k) * c[expo + "_n"] - c.actual) ** 2)
             .groupby("season")["err"].mean() for k in kgrid}
    years_here = sorted(c.season.unique())
    kstar_fold, pred2, pred2b = {}, pd.Series(index=c.index, dtype=float), pd.Series(index=c.index, dtype=float)
    for y in years_here:
        others = [yy for yy in years_here if yy != y]
        cvm = {k: np.mean([mse[k].get(yy, np.nan) for yy in others]) for k in kgrid}
        kstar_fold[y] = min(cvm, key=lambda k: cvm[k])
        m = c.season == y
        pred2[m] = (shrunk(kstar_fold[y]) * c[expo + "_n"])[m]
        pred2b[m] = (shrunk(kstar_fold[y], pooled=True) * c[expo + "_n"])[m]
    c["pred2"], c["pred2b"] = pred2, pred2b

    # global K* (descriptive only) + CV curve
    cv_curve = {k: float(np.mean([mse[k].get(y, np.nan) for y in years_here])) for k in kgrid}
    kg = min(cv_curve, key=lambda k: cv_curve[k])
    c["shrunk_g"] = shrunk(kg)

    # point stats
    stats = {
        "n_pairs": len(c), "n_clusters": c.player_id.nunique(),
        "kstar_fold": kstar_fold, "k_global": kg, "cv_curve": cv_curve,
        "sp_raw": spear(c.rate_t, c.rate_n),
        "sp_shrunk": spear(c.shrunk_g, c.rate_n),
        "pear_shrunk": float(np.corrcoef(c.shrunk_g, c.rate_n)[0, 1]),
        "mae0": float((c.pred0 - c.actual).abs().mean()),
        "mae1": float((c.pred1 - c.actual).abs().mean()),
        "mae2": float((c.pred2 - c.actual).abs().mean()),
        "mae2b": float((c.pred2b - c.actual).abs().mean()),
        "per_year_sp": {int(y): spear(g.rate_t, g.rate_n)
                        for y, g in c.groupby("season") if len(g) >= 8},
        "per_year_n": c.groupby("season").size().to_dict(),
    }
    stats["d01"] = stats["mae0"] - stats["mae1"]
    stats["d02"] = stats["mae0"] - stats["mae2"]
    stats["d12"] = stats["mae1"] - stats["mae2"]
    stats["d12b"] = stats["mae1"] - stats["mae2b"]

    # cluster bootstrap (players) for sp_shrunk, d01, d02, d12
    groups = {k: np.asarray(v) for k, v in c.groupby("player_id").indices.items()}
    keys = list(groups)
    sh, rn = c.shrunk_g.to_numpy(), c.rate_n.to_numpy()
    e0 = (c.pred0 - c.actual).abs().to_numpy()
    e1 = (c.pred1 - c.actual).abs().to_numpy()
    e2 = (c.pred2 - c.actual).abs().to_numpy()
    boots = {"sp_shrunk": [], "d01": [], "d02": [], "d12": []}
    for _ in range(B_BOOT):
        pick = RNG.integers(0, len(keys), len(keys))
        idx = np.concatenate([groups[keys[i]] for i in pick])
        boots["sp_shrunk"].append(spear(sh[idx], rn[idx]))
        boots["d01"].append(e0[idx].mean() - e1[idx].mean())
        boots["d02"].append(e0[idx].mean() - e2[idx].mean())
        boots["d12"].append(e1[idx].mean() - e2[idx].mean())
    for k, v in boots.items():
        v = np.asarray(v, dtype=float)
        stats[k + "_ci"] = (float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5)))

    # spread at equal volume (task 4)
    top_n = 12 if pos == "QB" else 24
    refvol = float(np.mean([sea[(sea.season == y) & (sea.position == pos)]
                            .nlargest(top_n, expo)[expo].median() for y in YEARS]))
    qual = sea[(sea.position == pos) & (sea[expo] >= floor)].copy()
    qual["l1"] = qual.season.map(lambda y: L1[(fam, pos, y)])
    qual["shr"] = (qual[num] + kg * qual.l1) / (qual[expo] + kg)
    p10a, p90a = qual.shr.quantile(.10), qual.shr.quantile(.90)
    q25 = qual[qual.season == 2025]
    p10b, p90b = (q25.shr.quantile(.10), q25.shr.quantile(.90)) if len(q25) >= 8 else (np.nan, np.nan)
    dl = (c.shrunk_g - c.l1) * c[expo + "_n"]
    stats.update(refvol=refvol, top_n=top_n,
                 spread_pool=float((p90a - p10a) * refvol),
                 p10_pool=float(p10a), p90_pool=float(p90a),
                 spread_2025=float((p90b - p10b) * refvol) if len(q25) >= 8 else np.nan,
                 n_2025=len(q25),
                 dl_p10=float(dl.quantile(.10)), dl_p90=float(dl.quantile(.90)))
    return stats


say()
say("=" * 78)
say("4. PER-CELL RESULTS (family x position). All [V]. CIs = 95% player-cluster")
say("   bootstrap, B=1000. dMAE > 0 means the second predictor is BETTER.")
say("=" * 78)
results = {}
for fam, cfg in FAM.items():
    for pos in cfg["pos"]:
        st = cell_analysis(fam, pos)
        if st is None:
            say(f"\n--- {fam} x {pos}: <20 pairs, skipped ---")
            continue
        results[(fam, pos)] = st
        flag = "  [<40 clusters -> DIRECTIONAL-ONLY (S11)]" if st["n_clusters"] < 40 else ""
        say(f"\n--- {fam} x {pos} ---  pairs={st['n_pairs']}  players(clusters)={st['n_clusters']}{flag}")
        say(f"  per-year pairs: { {int(k): int(v) for k, v in st['per_year_n'].items()} }")
        say(f"  raw YoY Spearman (pooled): {st['sp_raw']:+.3f}")
        say("  per-year raw Spearman: "
            + "  ".join(f"{y}:{v:+.2f}" for y, v in st["per_year_sp"].items()))
        say(f"  CV curve (mean per-year MSE by K): "
            + "  ".join(f"K={k}:{v:.2f}" for k, v in st["cv_curve"].items()))
        say(f"  nested-CV K* by fold: { {int(k): int(v) for k, v in st['kstar_fold'].items()} }"
            f"   global K* = {st['k_global']} {cfg['unit']}")
        say(f"  DECISION STAT shrunk-YoY Spearman: {st['sp_shrunk']:+.3f}"
            f"  CI [{st['sp_shrunk_ci'][0]:+.3f}, {st['sp_shrunk_ci'][1]:+.3f}]"
            f"   (Pearson {st['pear_shrunk']:+.3f})")
        say(f"  OOS MAE (pts/season): L0 {st['mae0']:.2f} | L1 {st['mae1']:.2f} | "
            f"L2 {st['mae2']:.2f} | L2b {st['mae2b']:.2f}")
        say(f"    dMAE L0-L1 (position beats league): {st['d01']:+.3f}"
            f"  CI [{st['d01_ci'][0]:+.3f}, {st['d01_ci'][1]:+.3f}]")
        say(f"    dMAE L0-L2 (player beats league):   {st['d02']:+.3f}"
            f"  CI [{st['d02_ci'][0]:+.3f}, {st['d02_ci'][1]:+.3f}]")
        say(f"    dMAE L1-L2 (player beats position): {st['d12']:+.3f}"
            f"  CI [{st['d12_ci'][0]:+.3f}, {st['d12_ci'][1]:+.3f}]")
        say(f"    dMAE L1-L2b (2yr-pooled variant):   {st['d12b']:+.3f}")
        say(f"  SPREAD at equal volume (ref = median {cfg['expo']} of top-{st['top_n']} "
            f"{pos}, {st['refvol']:.0f} {cfg['unit']}):")
        say(f"    p10-p90 shrunk rate pooled 2014-25: {st['p10_pool']:.5f} -> {st['p90_pool']:.5f}"
            f"  = {st['spread_pool']:.1f} pts/season")
        say(f"    2025 qualifiers (n={st['n_2025']}): {st['spread_2025']:.1f} pts/season")
        say(f"    realized per-pair (shrunk - position) x actual t+1 volume, p10/p90: "
            f"{st['dl_p10']:+.1f} / {st['dl_p90']:+.1f} pts")

# ============================================================================
# 5. DECISION TABLE
# ============================================================================
say()
say("=" * 78)
say("5. DECISION TABLE (rule pre-registered in section 0)")
say("=" * 78)
rows = []
for (fam, pos), st in results.items():
    stable = st["sp_shrunk"] >= 0.3
    beats_pos = st["d12"] > 0 and st["d12_ci"][0] > 0
    pos_beats_lg = st["d01"] > 0 and st["d01_ci"][0] > 0
    if stable and beats_pos:
        verdict = "PER-PLAYER CANDIDATE"
    elif pos_beats_lg:
        verdict = "POSITION-AVG FIX (player-level NULL)" if not stable else \
                  "POSITION-AVG FIX (stable but no OOS player edge)"
    else:
        verdict = "NULL — league average wins"
    if st["n_clusters"] < 40:
        verdict += " [DIRECTIONAL-ONLY]"
    rows.append({"family": fam, "pos": pos, "clusters": st["n_clusters"],
                 "sp_shrunk": round(st["sp_shrunk"], 3),
                 "dMAE_L0-L2": round(st["d02"], 3), "dMAE_L1-L2": round(st["d12"], 3),
                 "spread_pts": round(st["spread_pool"], 1), "verdict": verdict})
say(pd.DataFrame(rows).to_string(index=False))

say("""
FROZEN-FILE STATEMENT: apply_bonuses.py is in the run_all.py chain and FROZEN.
This entire script is measurement toward a proposal; no pipeline file was edited,
imported-with-side-effects, or re-run. The H5b primary endpoint (league points,
corrected grader, weekly mode, bar = placebo 95th pct or +20) is PENDING for the
Grading phase and is NOT claimed here.
""")

# ============================================================================
# 6. POST-RUN INTERPRETATION (written 2026-07-31 AFTER inspecting the numbers
#    above; the pre-registered verdicts in section 5 were NOT altered. Prose
#    refers to the seeded, deterministic run — a rerun reproduces it exactly.)
# ============================================================================
say("=" * 78)
say("6. POST-RUN INTERPRETATION")
say("=" * 78)
say("""
6.1 ANSWER TO THE REAL QUESTION (which rates are stable enough, which are not)

  PER-PLAYER CANDIDATES — stable AND beat even the position average OOS:
    rec_fd  x WR  (sp 0.369; dMAE L1-L2 +0.228, CI [+0.118,+0.345]; spread 4.1)
    rec_fd  x TE  (sp 0.366; +0.237, CI [+0.043,+0.435]; spread 4.0)
    pass_tier x QB (sp 0.391; +0.327, CI [+0.072,+0.576]; spread 8.1 — largest)
  All three also beat the shipped league constant (d02 CI > 0). Magnitudes are
  SMALL: mean error reduction ~0.2-0.3 pts/season per player; the p10-p90
  equal-volume spread (4-8 pts/season) is the ceiling between EXTREME players.

  THE DOMINANT FINDING IS NOT PER-PLAYER — it is the POSITION-level correction.
  The single all-position league constant systematically misprices whole
  positions, and that bias dwarfs the per-player residual:
    QB rush FD: QBs convert 0.29-0.36 FD/carry, the file applies 0.22-0.25.
      dMAE L0-L1 = +3.38 pts/season (CI [+2.41,+4.24]). At 2025 rates a
      median-volume (70-carry) top-12 QB is UNDERPAID ~3.2 pts/season; a
      120-carry rushing QB ~5.4 [V]. Consistent with (and partly explaining)
      T0.3's QB anchor gap and its 0.357 top-12-QB rate [R].
    RB receiving FD: RBs convert 0.16-0.19 FD/rec, the file applies ~0.26.
      dMAE L0-L1 = +2.73 (CI [+2.43,+3.04]). A median top-24 RB (47 rec) is
      OVERPAID ~4.8 pts/season; a 70-catch RB ~7.2 [V].
    WR receiving FD: +0.042 pts/rec x 86 rec = UNDERPAID ~3.6 pts/season [V].
    TE receiving FD: ~neutral (-0.3) — TE sits at the league mean.
    RB rec_tier: +0.59 MAE (RBs almost never hit 100-yd receiving games).
  The sign of every one of these gaps is stable in ALL 12 seasons of the L1
  tables (section 3) — bias, not noise. This is the stability-riskless 80% of
  H5b, it needs NO per-player history, and it feeds H5f directly: a systematic
  RB-negative / QB-positive / WR-positive tilt inside bonus_points moves
  cross-position replacement levels, which is where the charter expects the
  points to be.

  NULLS (league or position average wins — the valuable nulls, pre-registered
  bar respected):
    rush_fd per-player: RB sp 0.260 with d12 CI spanning 0; QB directional-only
      (26 clusters). First-down conversion per carry is ROLE+context, not a
      stable per-player skill, once the position rate is applied.
    rec_fd x RB: sp 0.261, d12 +0.022 — nothing left after the position fix.
    rush_tier (QB directional, RB sp 0.179): 100/200-yd rushing games per yard
      do not persist per player.
    rec_tier x RB: sp 0.163, d12 -0.013 — pure noise.
  Near-misses recorded for honesty (verdicts unchanged): rec_tier x WR fails
  the 0.3 bar (0.278) yet shows d12 +0.172 CI [+0.041,+0.314]; rec_tier x TE
  passes the bar (0.308) and beats the LEAGUE constant (d02 CI [+0.094,+0.391])
  but misses the position-beating CI ([-0.009,+0.437]) — its 'NULL' strictly
  means 'no demonstrated edge over the free position-average fix'.

6.2 PRIOR SCORECARD (priors were pre-stated in section 0)
  RIGHT: rec_fd most stable (WR/TE candidates); rush/rec yardage tiers mostly
  null. WRONG: rush_fd was expected moderately stable per-player — it is not,
  at either position (the QB effect is positional, not individual); pass_tier
  was expected weak — it is the STRONGEST candidate (sp 0.391, spread 8.1),
  i.e. which QBs concentrate yardage into 300+ games persists.

6.3 LEAGUE-RATE DRIFT (section 3) — the constants are moving targets:
  fd_carry 0.215 -> 0.250 (+16% over 12 seasons), r_pass300 0.00087 -> 0.00051
  (-41%), fd_rec 0.564 -> 0.524. The shipped 2-season window (2024-25) is the
  right recency choice versus a long average; any proposal should keep it.

6.4 DISCREPANCY NOTE vs T0.3 [R -> V]: T0.3's summary quotes "apply_bonuses'
  league-average FD/carry 0.237". Recomputed [V]: the 2024+2025 loader value
  (apply_bonuses' actual window, all positions) is 0.2509; 0.237 matches the
  2014-25 PANEL-WIDE average (mean of section 3's fd_carry column = 0.2364).
  T0.3's QB-gap conclusion is unaffected (0.357 vs 0.250 is still +43%), but
  re-pin the number before quoting it downstream.

6.5 CEILING FOR THE GRADING PHASE (task 4, stated plainly)
  Realized per-pair re-ranking from the per-player term, (shrunk - position) x
  actual next-year volume, spans roughly -1.8 to +3.0 pts/season (p10/p90) even
  in the strongest cell. Against S11's minimum detectable effect (~+45 pts with
  10 season clusters), a paired-draft grade of the PER-PLAYER rates alone is
  expected to be under-powered and is unlikely to clear H5b's +20 bar unless
  the effect concentrates on pick-boundary rank flips. The POSITION-level
  corrections (systematic 3-7 pts/season per starter, sign-stable 12/12
  seasons) plus their H5f replacement-level channel are where H5b's league
  points live. RECOMMENDED PROPOSAL SHAPE (for post-Aug-7 consideration, via
  the Grading phase): (1) position-level rates for fd_carry, fd_rec and the
  yardage tiers — bias-class fix, no stability risk; (2) per-player EB rates
  ONLY for rec_fd WR/TE and pass_tier QB, pooled over 2 prior seasons (L2b
  beat L2 in 9 of 11 cells), K per section 4's CV; (3) leave everything else
  at the (position) average — measured null.

6.6 LIMITATIONS / NOT DONE
  - No paired-draft points grade (H5b primary endpoint) — PENDING, by design.
  - OOS evaluation uses ACTUAL t+1 exposure: the rate is isolated from volume
    forecasting, so live-projection gains will be smaller than the dMAEs here.
  - Exposure floors were not sensitivity-swept (single stated values).
  - Pairs require the same panel position in consecutive seasons; position
    switches drop out. QB rush_fd (26) and QB rush_tier (19) cells are under
    the 40-cluster S11 floor -> DIRECTIONAL-ONLY, as flagged.
  - rush_tier x QB per-year Spearman prints 'nan' where a year's QB rates are
    tie-heavy (many zeros) — cosmetic, pooled stat unaffected.
  - 2pt / PAT / FG / returns / long-TD / sack rates: census only (section 1).
  - The projection-side volumes (blended_components) were not touched or
    re-weighted; this run says nothing about volume projection quality.
""")

with open(OUT_TXT, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nwrote {OUT_TXT}")
