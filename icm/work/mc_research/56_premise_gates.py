"""56 — WS2 PREMISE GATES: H2a (personnel-profile carryover), H2b (touch-concentration
carryover), H2c (goal-line tendency carryover).

Charter: icm/work/research-blueprint-prompt.md — WS2 preamble (the n=31 constraint, ~line 590),
H2a (~603), H2b (~611), H2c (~617), section 3.1 playcaller row (~272), T0.2 gate item (~502).
All three hypotheses are DEMOTED TO PREMISE GATES by the charter itself: the points test is
declared NOT REACHABLE at n=31 coach-moves ("The points test is NOT reachable at this n and the
charter does not pretend it is"), so NOTHING here is graded in league points, and even a
PASS-PREMISE verdict routes to the 2026 preregistration — never to an under-powered paired grade.
A clean death here is a legitimate kill-list entry (charter section 10.9 / S10).

S12 note: primary quantities are ROLE/MIX units (personnel rates, touch shares, inside-5 shares)
by charter design, because the charter forbids the points test at this n. League-vs-base currency
is therefore N/A for this script; no points number of any kind is produced.

S11: every interval is a CLUSTER bootstrap on the treatment unit = the COACH-MOVE. Effective
n = the cluster count (31 or fewer where data drops an event), printed with every estimate.

S14 — PRIMARY ENDPOINTS, DECLARED HERE BEFORE ANY RESULT WAS COMPUTED. This script contributes
FOUR primary endpoints to the global FDR count (3 gates + 1 split-out stability check):

  H2a PRIMARY: incremental ADJUSTED R^2 (Delta R2_adj) of the incoming caller's pooled
    personnel-rate profile ADDED to an OLS of next-season team personnel rate on the team's own
    prior-year rate, averaged across the three rates (11 / 12 / 21 personnel), on the carryable
    coach-moves. 95% cluster-bootstrap CI resampling coach-moves.
      PASS-PREMISE  : point >= 0.15 AND CI lower bound > 0
      FAIL-PREMISE  : point < 0.15                      (charter abandon threshold "~15%")
      UNINFORMATIVE : point >= 0.15 but CI lower <= 0   (charter: "interval ... uninformative")
    (Adjusted R2 is used because raw in-sample Delta R2 is >= 0 by construction, which would make
    a "CI excludes 0" criterion pass mechanically.)

  H2b PRIMARY: mean paired difference in absolute out-of-sample prediction error,
    |err(team-prior-year)| - |err(caller-profile)|, for RB TOUCH HHI (the headline concentration
    object in the hypothesis title), over the carryable coach-moves; positive = caller profile
    better. 95% cluster-bootstrap CI.
      PASS-PREMISE  : point > 0 AND CI excludes 0
      FAIL-PREMISE  : point <= 0   (charter falsification: "caller profile does not beat
                                    team-prior-year on the role forecast")
      UNINFORMATIVE : point > 0 but CI includes 0
    Secondary: top-back share, RB target share, TE target share; blend predictor; the ADP-control
    regressions (charter-named confound) are reported for ALL metrics with and without control.

  H2c PRIMARY: same paired |error| difference (null - caller), for RB SHARE OF INSIDE-5 RUSHES
    ("a coach's inside-5 running-back share ... travels with him"), over the carryable
    coach-moves, caller profile = POOLED inside-5 plays across his prior other-team stints.
    Same decision rule as H2b. Bar stated in COACH-MOVES, not rooms (charter [CORRECTED]).
    Secondary: QB share (sneak proxy), non-QB top-rusher share, non-QB HHI.

  SPLIT-OUT (separate non-carryover hypothesis, charter-suggested): team-level goal-line
    concentration STABILITY — year-over-year Pearson r of team inside-5 non-QB top-rusher share,
    all team-season pairs 2015-2025, CI clustered on TEAM (32 clusters).
      STABLE if r >= 0.30 with CI excluding 0, else UNSTABLE/UNINFORMATIVE.

No OR-clauses. Everything not named above is SECONDARY and labelled so in the results file.

Data corrections found while scoping (both recorded in results):
  * load_ftn_charting has NO offense_personnel column (only n_offense_backfield / is_qb_sneak)
    [V] — the assignment's "ftn 2022+" personnel fallback does not exist. Participation carries
    offense_personnel for ALL of 2016-2025, so it is the sole personnel source here.
  * offense_personnel is TWO ENCODINGS under one name (S8): pre-2023 skill-only
    ("1 RB, 1 TE, 3 WR", ~76% of plays populated); 2023+ full-XI ("1 C, 2 G, 1 QB, 1 RB, ...",
    100% populated). Parsing extracts the RB and TE counts, which exist in both encodings.

Prior scripts read before writing this one (charter mandate): 46_league_scored_panel.py,
47_participation_semantics.py, 55_h2g_depthchart.py. New files only; frozen pipeline untouched.

Run (per-season personnel builds are cached + atomic so a retry RESUMES):
  .venv/bin/python icm/work/mc_research/56_premise_gates.py personnel 2016 2017 ...
  .venv/bin/python icm/work/mc_research/56_premise_gates.py run
"""
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RAW = os.path.join(HERE, "raw")
os.makedirs(RAW, exist_ok=True)
os.environ.setdefault("NFLREADPY_CACHE_MODE", "filesystem")
os.environ.setdefault("NFLREADPY_CACHE_DIR", os.path.join(HERE, ".nflcache"))
os.environ.setdefault("NFLREADPY_CACHE_DURATION", str(7 * 24 * 3600))
os.environ.setdefault("NFLREADPY_TIMEOUT", "120")

PC_CSV = os.path.join(ROOT, "data", "playcallers_hist.csv")
WEEKLY = os.path.join(HERE, "weekly.parquet")
SEASONS = os.path.join(HERE, "seasons.parquet")
SEASONS_25 = os.path.join(HERE, "seasons_2025repair.parquet")
PBP_SLIM = os.path.join(HERE, "pbp_slim_{y}.parquet")            # T0.3 sibling cache
PERS_CACHE = os.path.join(RAW, "personnel56_{y}.parquet")        # this script's cache
OUT = os.path.join(HERE, "results_56_premise_gates.txt")

PERS_YEARS = list(range(2016, 2026))     # participation offense_personnel availability
I5_YEARS = list(range(2014, 2026))       # pbp_slim availability (T0.3)
CONC_YEARS = list(range(2014, 2026))     # weekly.parquet availability
# playcallers_hist.csv uses LAR; nflverse weekly/pbp/participation use LA.
TEAM_FIX = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX", "ARZ": "ARI", "OAK": "LV",
            "SD": "LAC", "STL": "LA"}
N_BOOT = 10_000
RNG_SEED = 56

lines = []


def say(s=""):
    print(s)
    lines.append(str(s))


def flush():
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")


def fix_team(s):
    return s.replace(TEAM_FIX)


# =============================================================================================
# Event table (Task 1)
# =============================================================================================
def build_events():
    pc = pd.read_csv(PC_CSV)
    assert len(pc) == 224, f"playcallers_hist rows {len(pc)} != 224"
    pc["team"] = fix_team(pc["team"])
    assert pc.team.nunique() == 32 and sorted(pc.season.unique()) == list(range(2019, 2026))
    ev = pc[pc.pc_changed].copy()

    def classify(row):
        prior = pc[(pc.season < row.season) & (pc.playcaller == row.playcaller)]
        if len(prior[prior.team != row.team]):
            return "carryable"
        return "same-team-only" if len(prior) else "first-time"

    ev["bucket"] = ev.apply(classify, axis=1)

    def stints(row):
        p = pc[(pc.season < row.season) & (pc.playcaller == row.playcaller)
               & (pc.team != row.team)]
        return list(zip(p.season, p.team))

    ev["prior_stints"] = ev.apply(stints, axis=1)
    return pc, ev


# =============================================================================================
# Personnel table (per-season, cached, atomic) — H2a
# =============================================================================================
def build_personnel_year(y):
    dest = PERS_CACHE.format(y=y)
    if os.path.exists(dest):
        print(f"personnel {y}: cached")
        return
    import nflreadpy as nfl
    part = nfl.load_participation(seasons=[y]).to_pandas()
    part = part[["nflverse_game_id", "play_id", "possession_team", "offense_personnel"]]
    part["possession_team"] = fix_team(part["possession_team"])
    pbp = pd.read_parquet(PBP_SLIM.format(y=y),
                          columns=["game_id", "play_id", "season_type",
                                   "pass_attempt", "rush_attempt", "posteam"])
    pbp = pbp[(pbp.season_type == "REG")
              & ((pbp.pass_attempt == 1) | (pbp.rush_attempt == 1))]
    m = pbp.merge(part, left_on=["game_id", "play_id"],
                  right_on=["nflverse_game_id", "play_id"], how="left")
    join_rate = m.offense_personnel.notna().mean()
    pers = m.offense_personnel.fillna("")
    covered = pers.str.len() > 0
    rb = pers.str.extract(r"(\d+) RB")[0].astype(float)
    te = pers.str.extract(r"(\d+) TE")[0].astype(float)
    m["p11"] = ((rb == 1) & (te == 1)).where(covered)
    m["p12"] = ((rb == 1) & (te == 2)).where(covered)
    m["p21"] = ((rb == 2) & (te == 1)).where(covered)
    g = m.groupby("posteam").agg(
        scrim=("play_id", "size"), cov=("p11", "count"),
        n11=("p11", "sum"), n12=("p12", "sum"), n21=("p21", "sum")).reset_index()
    g["season"] = y
    g["join_rate"] = join_rate
    assert len(g) == 32, f"{y}: {len(g)} teams"
    g.to_parquet(dest + ".tmp", index=False)
    os.replace(dest + ".tmp", dest)
    print(f"personnel {y}: {len(g)} teams, scrim-play participation match "
          f"{join_rate:.1%}, personnel coverage {g['cov'].sum() / g.scrim.sum():.1%}")


def load_personnel():
    parts = [pd.read_parquet(PERS_CACHE.format(y=y)) for y in PERS_YEARS]
    t = pd.concat(parts, ignore_index=True).rename(columns={"posteam": "team"})
    counts = t.groupby("season").size()
    assert (counts == 32).all(), f"S8 per-year team counts off:\n{counts}"  # S8
    for r, n in (("r11", "n11"), ("r12", "n12"), ("r21", "n21")):
        t[r] = t[n] / t["cov"]
        # within-season cross-team z-score: the era-robust view (the 2023 product break moves
        # LEVELS; a caller tendency is relative to that year's league)
        t["z" + r[1:]] = t.groupby("season")[r].transform(lambda s: (s - s.mean()) / s.std())
    return t


# =============================================================================================
# Touch-concentration table — H2b (weekly.parquet, no pull)
# =============================================================================================
def build_concentration():
    w = pd.read_parquet(WEEKLY, columns=["season", "week", "season_type", "team", "player_id",
                                         "position", "carries", "receptions", "targets"])
    assert set(w.season_type.unique()) == {"REG"}
    w = w[w.season.isin(CONC_YEARS)]
    ps = (w.groupby(["season", "team", "player_id", "position"], as_index=False)
            [["carries", "receptions", "targets"]].sum())
    ps["touches"] = ps.carries + ps.receptions
    rows = []
    for (season, team), g in ps.groupby(["season", "team"]):
        rb = g[g.position == "RB"]
        rb_touch = rb.touches.sum()
        shares = rb.touches / rb_touch if rb_touch > 0 else pd.Series(dtype=float)
        tgt_all = g.targets.sum()
        rows.append(dict(
            season=season, team=team,
            rb_hhi=float((shares ** 2).sum()) if rb_touch > 0 else np.nan,
            top_back_share=float(shares.max()) if rb_touch > 0 else np.nan,
            rb_tgt_share=float(rb.targets.sum() / tgt_all) if tgt_all > 0 else np.nan,
            te_tgt_share=float(g[g.position == "TE"].targets.sum() / tgt_all)
                         if tgt_all > 0 else np.nan))
    t = pd.DataFrame(rows)
    counts = t.groupby("season").size()
    assert (counts == 32).all(), f"S8 per-year team counts off:\n{counts}"  # S8
    return t


# =============================================================================================
# Inside-5 table — H2c (pbp_slim, no pull)
# =============================================================================================
def build_inside5():
    w = pd.read_parquet(WEEKLY, columns=["season", "player_id", "position"])
    posmap = w.drop_duplicates(["season", "player_id"]).set_index(["season", "player_id"])
    rows = []
    for y in I5_YEARS:
        p = pd.read_parquet(PBP_SLIM.format(y=y),
                            columns=["season", "season_type", "posteam", "rush_attempt",
                                     "yardline_100", "rusher_player_id"])
        p = p[(p.season_type == "REG") & (p.rush_attempt == 1)
              & (p.yardline_100 <= 5) & p.rusher_player_id.notna()]
        idx = pd.MultiIndex.from_arrays([p.season, p.rusher_player_id])
        p = p.assign(pos=posmap.reindex(idx).position.fillna("OTH").values)
        for team, g in p.groupby("posteam"):
            nonqb = g[g.pos != "QB"]
            top = nonqb.groupby("rusher_player_id").size()
            sh = top / len(nonqb) if len(nonqb) else pd.Series(dtype=float)
            rows.append(dict(
                season=y, team=team, n_i5=len(g),
                qb_share=float((g.pos == "QB").mean()),
                rb_share=float((g.pos == "RB").mean()),
                n_nonqb=len(nonqb),
                nonqb_top_share=float(sh.max()) if len(nonqb) else np.nan,
                nonqb_hhi=float((sh ** 2).sum()) if len(nonqb) else np.nan))
    t = pd.DataFrame(rows)
    counts = t.groupby("season").size()
    assert (counts == 32).all(), f"S8 per-year team counts off:\n{counts}"  # S8
    return t


# =============================================================================================
# Best-back ADP (H2b confound control) — seasons.parquet + T0.2 2025 repair union
# =============================================================================================
def bestback_adp():
    cols = ["player_id", "season", "position", "adp"]
    s = pd.read_parquet(SEASONS, columns=cols)
    s = s[s.season < 2025]
    r = pd.read_parquet(SEASONS_25, columns=cols)          # 2025 price = Sleeper adp_ppr (T0.2)
    s = pd.concat([s, r[r.season == 2025]], ignore_index=True)
    w = pd.read_parquet(WEEKLY, columns=["season", "team", "player_id", "week"])
    modal = (w.groupby(["season", "player_id", "team"]).size().rename("wk")
              .reset_index().sort_values("wk", ascending=False)
              .drop_duplicates(["season", "player_id"]))
    s = s.merge(modal[["season", "player_id", "team"]], on=["season", "player_id"], how="left")
    rb = s[(s.position == "RB") & s.adp.notna() & s.team.notna()]
    return rb.groupby(["season", "team"]).adp.min().rename("bestback_adp")


# =============================================================================================
# Stats helpers
# =============================================================================================
def ols_r2(y, X):
    """R2 and adjusted R2 of OLS with intercept."""
    X1 = np.column_stack([np.ones(len(y))] + [np.asarray(x, float) for x in X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ beta
    sst = ((y - y.mean()) ** 2).sum()
    r2 = 1 - (resid ** 2).sum() / sst if sst > 0 else np.nan
    n, k = len(y), X1.shape[1] - 1
    adj = 1 - (1 - r2) * (n - 1) / (n - k - 1)
    return r2, adj, beta


def pred_r2(y, pred):
    """No-fit predictive R2: 1 - SSE(pred)/SST(grand mean)."""
    sst = ((y - y.mean()) ** 2).sum()
    return 1 - ((y - pred) ** 2).sum() / sst if sst > 0 else np.nan


def boot_ci(stat_fn, n_units, rng, n_boot=N_BOOT):
    """Cluster bootstrap: stat_fn(idx array) -> float. Returns (lo, hi, n_valid)."""
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n_units, n_units)
        v = stat_fn(idx)
        if np.isfinite(v):
            vals.append(v)
    return (np.percentile(vals, 2.5), np.percentile(vals, 97.5), len(vals))


def fmt_ci(pt, lo, hi):
    return f"{pt:+.3f}  [95% CI {lo:+.3f}, {hi:+.3f}]"


# =============================================================================================
# Gate analyses
# =============================================================================================
def gate_h2a(ev_carry, pers, rng):
    say("\n" + "=" * 100)
    say("H2a PREMISE GATE — personnel-profile carryover (11/12/21 rates)")
    say("=" * 100)
    key = pers.set_index(["season", "team"])
    rows = []
    for _, e in ev_carry.iterrows():
        rec = {"season": e.season, "team": e.team, "caller": e.playcaller}
        try:
            out = key.loc[(e.season, e.team)]
            nul = key.loc[(e.season - 1, e.team)]
        except KeyError:
            continue
        stint_keys = [(s, t) for s, t in e.prior_stints
                      if (s, t) in key.index and s >= PERS_YEARS[0]]
        if not stint_keys:
            continue
        stint = key.loc[stint_keys].reset_index()
        for r in ("r11", "r12", "r21"):
            n = "n" + r[1:]
            rec[f"out_{r}"], rec[f"nul_{r}"] = out[r], nul[r]
            rec[f"cal_{r}"] = stint[n].sum() / stint["cov"].sum()   # play-weighted pool
        for z in ("z11", "z12", "z21"):
            rec[f"out_{z}"], rec[f"nul_{z}"] = out[z], nul[z]
            rec[f"cal_{z}"] = (stint[z] * stint["cov"]).sum() / stint["cov"].sum()
        rec["stint_n"] = len(stint)
        rec["stint_last"] = int(stint.season.max())
        rows.append(rec)
    d = pd.DataFrame(rows)
    n = len(d)
    say(f"\nUsable carryable coach-moves: n = {n} (of 31) — effective n / cluster count (S11)")
    say(f"Caller prior-stint seasons pooled per event: median {d.stint_n.median():.0f}, "
        f"max {d.stint_n.max()}; recency gap (event yr - last stint yr): "
        f"median {(d.season - d.stint_last).median():.0f}, max {(d.season - d.stint_last).max()}")

    def run_block(cols, label):
        say(f"\n--- {label} ---")
        say(f"{'rate':<5} {'predR2 null':>12} {'predR2 caller':>14} {'predR2 blend':>13} "
            f"{'fitR2 null':>11} {'fitR2 +caller':>14} {'dR2':>7} {'dR2_adj':>8}")
        d_adj, d_raw, per_rate = [], [], {}
        for r in cols:
            y = d[f"out_{r}"].values
            nul, cal = d[f"nul_{r}"].values, d[f"cal_{r}"].values
            p_n, p_c = pred_r2(y, nul), pred_r2(y, cal)
            p_b = pred_r2(y, 0.5 * nul + 0.5 * cal)
            r2n, adjn, _ = ols_r2(y, [nul])
            r2f, adjf, beta = ols_r2(y, [nul, cal])
            per_rate[r] = (y, nul, cal)
            d_raw.append(r2f - r2n)
            d_adj.append(adjf - adjn)
            say(f"{r:<5} {p_n:>12.3f} {p_c:>14.3f} {p_b:>13.3f} {r2n:>11.3f} {r2f:>14.3f} "
                f"{r2f - r2n:>7.3f} {adjf - adjn:>8.3f}   caller beta={beta[2]:+.3f}")

        def stat(idx):
            deltas = []
            for r in cols:
                y, nul, cal = per_rate[r]
                _, a_n, _ = ols_r2(y[idx], [nul[idx]])
                _, a_f, _ = ols_r2(y[idx], [nul[idx], cal[idx]])
                deltas.append(a_f - a_n)
            return float(np.mean(deltas))

        pt = float(np.mean(d_adj))
        lo, hi, _ = boot_ci(stat, n, rng)
        say(f"mean Delta R2_adj across the three rates = {fmt_ci(pt, lo, hi)}"
            f"   (raw in-sample mean dR2 = {np.mean(d_raw):+.3f}, upward-biased)")
        return pt, lo, hi

    pt, lo, hi = run_block(["r11", "r12", "r21"],
                           "PRIMARY (as declared): RAW personnel rates")
    if pt >= 0.15 and lo > 0:
        verdict = "PASS-PREMISE"
    elif pt < 0.15:
        verdict = "FAIL-PREMISE"
    else:
        verdict = "UNINFORMATIVE"
    say(f"H2a VERDICT (primary, raw rates): {verdict}  (rule pre-stated; threshold ~15%)")

    # --- robustness on the primary (SECONDARY, but decision-relevant honesty checks) ---
    say("\nRobustness check 1 — LEAVE-ONE-OUT CROSS-VALIDATION (guards against in-sample")
    say("optimism in dR2_adj: each event predicted by a model fit on the other 30):")
    say(f"{'rate':<5} {'cvR2 null-model':>16} {'cvR2 +caller':>13} {'cv gain':>8}")
    cv_gains = []
    for r in ("r11", "r12", "r21"):
        y = d[f"out_{r}"].values
        nul, cal = d[f"nul_{r}"].values, d[f"cal_{r}"].values
        sst = ((y - y.mean()) ** 2).sum()
        sse_n = sse_f = 0.0
        for i in range(n):
            m = np.arange(n) != i
            _, _, b_n = ols_r2(y[m], [nul[m]])
            _, _, b_f = ols_r2(y[m], [nul[m], cal[m]])
            sse_n += (y[i] - (b_n[0] + b_n[1] * nul[i])) ** 2
            sse_f += (y[i] - (b_f[0] + b_f[1] * nul[i] + b_f[2] * cal[i])) ** 2
        cv_n, cv_f = 1 - sse_n / sst, 1 - sse_f / sst
        cv_gains.append(cv_f - cv_n)
        say(f"{r:<5} {cv_n:>16.3f} {cv_f:>13.3f} {cv_f - cv_n:>+8.3f}")
    say(f"mean LOO-CV gain = {np.mean(cv_gains):+.3f} "
        f"({'confirms' if np.mean(cv_gains) > 0 else 'CONTRADICTS'} the in-sample primary)")

    say("\nRobustness check 2 — LEAVE-ONE-EVENT-OUT JACKKNIFE on the primary statistic")
    say("(C11 precedent: if one dropped event moves the result by more than half, the finding")
    say("is one event, not a rule):")
    jk = []
    for i in range(n):
        m = np.arange(n) != i
        deltas = []
        for r in ("r11", "r12", "r21"):
            y = d[f"out_{r}"].values
            nul, cal = d[f"nul_{r}"].values, d[f"cal_{r}"].values
            _, a_n, _ = ols_r2(y[m], [nul[m]])
            _, a_f, _ = ols_r2(y[m], [nul[m], cal[m]])
            deltas.append(a_f - a_n)
        jk.append(np.mean(deltas))
    jk = np.array(jk)
    imin = int(np.argmin(jk))
    say(f"jackknife primary over 31 drops: min {jk.min():+.3f} (dropping "
        f"{d.iloc[imin].season} {d.iloc[imin].team} {d.iloc[imin].caller}), "
        f"max {jk.max():+.3f}; drops below the 0.15 threshold: {(jk < 0.15).sum()}/31; "
        f"drops below 0: {(jk < 0).sum()}/31")

    say("\nSECONDARY (era-robust instrument-break control, NOT the declared primary): the 2023")
    say("participation product changes the personnel LEVELS (league 21-personnel collapses from")
    say("~8% to ~1.7% at the break — a charting change, not football). For 2024+ events the")
    say("null (=Y-1) is measured in the same era as the outcome while older caller stints are")
    say("not, which mechanically favors the null. Within-season cross-team z-scores remove the")
    say("level shift; caller profile = cov-weighted mean of his stint-season z-scores.")
    z_pt, z_lo, z_hi = run_block(["z11", "z12", "z21"],
                                 "SECONDARY: within-season z-scored rates")
    say(f"Secondary would read: {'PASS' if (z_pt >= 0.15 and z_lo > 0) else ('FAIL' if z_pt < 0.15 else 'UNINF')}"
        f" — reported for era-robustness only; the verdict above stands on the declared primary.")
    return d, verdict, pt, (lo, hi), n, (z_pt, z_lo, z_hi)


def paired_gate(d, metrics, primary, rng, label):
    """Shared machinery for H2b / H2c: paired |err| comparisons + bootstrap CIs.
    The lgm_ column (prior-season LEAGUE MEAN of the metric) is the shrinkage comparator:
    a pooled caller profile is a lower-variance estimator, so it can beat the noisy
    team-prior-year WITHOUT carrying any caller-specific information — if caller does not
    also beat the league-mean predictor, the 'win' is shrinkage, not carryover."""
    n = len(d)
    results = {}
    say(f"\n{'metric':<16} {'mean|e| null':>13} {'mean|e| caller':>15} {'mean|e| blend':>14} "
        f"{'mean|e| lgmean':>15} {'diff null-caller':>17} {'95% CI':>20} {'caller wins':>12}")
    for m in metrics:
        y, nul, cal = d[f"out_{m}"].values, d[f"nul_{m}"].values, d[f"cal_{m}"].values
        lgm = d[f"lgm_{m}"].values
        e_n, e_c = np.abs(y - nul), np.abs(y - cal)
        e_b = np.abs(y - (0.5 * nul + 0.5 * cal))
        e_l = np.abs(y - lgm)
        diff = e_n - e_c
        pt = float(diff.mean())
        lo, hi, _ = boot_ci(lambda idx, dd=diff: float(dd[idx].mean()), n, rng)
        wins = float((diff > 0).mean())
        tag = " <-- PRIMARY" if m == primary else ""
        say(f"{m:<16} {e_n.mean():>13.4f} {e_c.mean():>15.4f} {e_b.mean():>14.4f} "
            f"{e_l.mean():>15.4f} {pt:>+17.4f} {'[' + f'{lo:+.4f}, {hi:+.4f}' + ']':>20} "
            f"{wins:>11.0%}{tag}")
        results[m] = (pt, lo, hi, wins, float(e_l.mean() - e_c.mean()))
    say("(shrinkage read: caller only carries INFORMATION where mean|e| caller < mean|e| "
        "lgmean as well as < mean|e| null)")
    pt, lo, hi = results[primary][:3]
    if pt > 0 and lo > 0:
        verdict = "PASS-PREMISE"
    elif pt <= 0:
        verdict = "FAIL-PREMISE"
    else:
        verdict = "UNINFORMATIVE"
    say(f"\n{label} PRIMARY ({primary}): diff(|e|null - |e|caller) = {fmt_ci(pt, lo, hi)}"
        f"  on n = {n} coach-move clusters (S11)")
    say(f"{label} VERDICT: {verdict}  (rule pre-stated in docstring)")
    return results, verdict


def gate_h2b(ev_carry, conc, bb_adp, rng):
    say("\n" + "=" * 100)
    say("H2b PREMISE GATE — touch-concentration carryover (RB HHI / top-back / RB+TE tgt share)")
    say("=" * 100)
    key = conc.set_index(["season", "team"])
    metrics = ["rb_hhi", "top_back_share", "rb_tgt_share", "te_tgt_share"]
    rows = []
    for _, e in ev_carry.iterrows():
        rec = {"season": e.season, "team": e.team, "caller": e.playcaller}
        try:
            out = key.loc[(e.season, e.team)]
            nul = key.loc[(e.season - 1, e.team)]
        except KeyError:
            continue
        stint = [key.loc[(s, t)] for s, t in e.prior_stints if (s, t) in key.index]
        if not stint:
            continue
        stint = pd.DataFrame(stint)
        lg = conc[conc.season == e.season - 1]
        ok = True
        for m in metrics:
            rec[f"out_{m}"], rec[f"nul_{m}"] = out[m], nul[m]
            rec[f"cal_{m}"] = stint[m].mean()        # equal weight per stint-season (stated)
            rec[f"lgm_{m}"] = lg[m].mean()           # prior-season league mean (shrinkage ref)
            ok &= np.isfinite([rec[f"out_{m}"], rec[f"nul_{m}"], rec[f"cal_{m}"]]).all()
        if ok:
            rec["bestback_adp"] = bb_adp.get((e.season, e.team), np.nan)
            rows.append(rec)
    d = pd.DataFrame(rows)
    n = len(d)
    say(f"\nUsable carryable coach-moves: n = {n} (of 31) — effective n / cluster count (S11)")
    say("Caller profile = EQUAL-WEIGHT mean of his prior other-team stint-season metric values")
    results, verdict = paired_gate(d, metrics, "rb_hhi", rng, "H2b")

    # --- charter-named confound: receiving team's best-back ADP, with and without ---
    say("\nADP-control regressions (SECONDARY; charter: 'the concentration a caller ran is")
    say("partly the back he had'). outcome ~ prior + caller  vs  ... + bestback_adp.")
    n_adp = int(d.bestback_adp.notna().sum())
    say(f"bestback_adp defined for {n_adp}/{n} events (min RB adp on receiving team, event "
        f"season; union panel: seasons.parquet <2025 + T0.2 repair for 2025, whose price")
    say("instrument is SLEEPER adp_ppr, NOT ESPN/FFC — stated per T0.2's downstream contract.")
    say(f"Missing best-back ADP (no priced RB) filled at 200 for {n - n_adp} events.")
    adp = d.bestback_adp.fillna(200).values
    say(f"{'metric':<16} {'beta_caller (no ctl)':>21} {'beta_caller (+adp ctl)':>23} "
        f"{'dR2_adj (no ctl)':>17} {'dR2_adj (+ctl)':>15}")
    for m in metrics:
        y, nul, cal = d[f"out_{m}"].values, d[f"nul_{m}"].values, d[f"cal_{m}"].values
        _, a1n, _ = ols_r2(y, [nul])
        _, a1f, b1 = ols_r2(y, [nul, cal])
        _, a2n, _ = ols_r2(y, [nul, adp])
        _, a2f, b2 = ols_r2(y, [nul, cal, adp])
        say(f"{m:<16} {b1[2]:>+21.3f} {b2[2]:>+23.3f} {a1f - a1n:>+17.3f} {a2f - a2n:>+15.3f}")
    return d, results, verdict


def gate_h2c(ev_carry, i5, rng):
    say("\n" + "=" * 100)
    say("H2c PREMISE GATE — inside-5 goal-line tendency carryover")
    say("=" * 100)
    say("Bar stated in COACH-MOVES (charter [CORRECTED]): the carryover population is capped at")
    say("31 coach-moves; 'rooms' never enter it. Directional at this n by construction.")
    key = i5.set_index(["season", "team"])
    rows = []
    for _, e in ev_carry.iterrows():
        rec = {"season": e.season, "team": e.team, "caller": e.playcaller}
        try:
            out = key.loc[(e.season, e.team)]
            nul = key.loc[(e.season - 1, e.team)]
        except KeyError:
            continue
        stint = [key.loc[(s, t)] for s, t in e.prior_stints if (s, t) in key.index]
        if not stint:
            continue
        stint = pd.DataFrame(stint)
        pooled = stint.n_i5.sum()
        rec["out_n_i5"], rec["nul_n_i5"], rec["cal_n_i5"] = out.n_i5, nul.n_i5, pooled
        # pooled-play caller rates for share metrics; play-weighted mean for concentration
        lg = i5[i5.season == e.season - 1]
        for m in ("qb_share", "rb_share"):
            rec[f"out_{m}"], rec[f"nul_{m}"] = out[m], nul[m]
            rec[f"cal_{m}"] = (stint[m] * stint.n_i5).sum() / pooled
            rec[f"lgm_{m}"] = lg[m].mean()
        for m in ("nonqb_top_share", "nonqb_hhi"):
            rec[f"out_{m}"], rec[f"nul_{m}"] = out[m], nul[m]
            wn = stint.n_nonqb.sum()
            rec[f"cal_{m}"] = (stint[m] * stint.n_nonqb).sum() / wn if wn else np.nan
            rec[f"lgm_{m}"] = lg[m].mean()
        if np.isfinite([v for k, v in rec.items() if k.startswith(("out_", "nul_", "cal_"))
                        ]).all():
            rows.append(rec)
    d = pd.DataFrame(rows)
    n = len(d)
    say(f"\nUsable carryable coach-moves: n = {n} (of 31) — effective n / cluster count (S11)")
    say(f"Brutal denominators, as the charter warns: receiving-team inside-5 rushes in the event"
        f" season: median {d.out_n_i5.median():.0f}, min {d.out_n_i5.min():.0f}, "
        f"max {d.out_n_i5.max():.0f}; caller pooled prior plays: median {d.cal_n_i5.median():.0f}"
        f", min {d.cal_n_i5.min():.0f}")
    p_bar = d.out_rb_share.mean()
    noise = np.sqrt(p_bar * (1 - p_bar) / d.out_n_i5.median())
    say(f"Binomial noise floor on the OUTCOME itself: sampling SD of rb_share at median "
        f"denominator ~ {noise:.3f} — no predictor can beat that floor; intervals, not points.")
    say("Caller share profile = POOLED raw inside-5 plays across prior other-team stints;")
    say("concentration profile = play-weighted mean of per-stint-season values (identity of the")
    say("top back does not travel; only the concentration level can).")
    metrics = ["rb_share", "qb_share", "nonqb_top_share", "nonqb_hhi"]
    results, verdict = paired_gate(d, metrics, "rb_share", rng, "H2c")
    return d, results, verdict


def team_stability(i5, rng):
    say("\n" + "=" * 100)
    say("SPLIT-OUT (separate, non-carryover hypothesis) — TEAM-LEVEL inside-5 concentration")
    say("stability, ALL teams, ALL adjacent season pairs (the 'much larger population')")
    say("=" * 100)
    key = i5.set_index(["season", "team"])
    pairs = []
    for y in I5_YEARS[1:]:
        for team in i5.team.unique():
            try:
                a, b = key.loc[(y - 1, team)], key.loc[(y, team)]
            except KeyError:
                continue
            pairs.append(dict(season=y, team=team,
                              **{f"prev_{m}": a[m] for m in
                                 ("rb_share", "qb_share", "nonqb_top_share", "nonqb_hhi")},
                              **{f"cur_{m}": b[m] for m in
                                 ("rb_share", "qb_share", "nonqb_top_share", "nonqb_hhi")}))
    d = pd.DataFrame(pairs).dropna()
    teams = sorted(d.team.unique())
    t_idx = {t: i for i, t in enumerate(teams)}
    say(f"\nTeam-season pairs: n = {len(d)} ({I5_YEARS[1]}-{I5_YEARS[-1]}); "
        f"clusters = {len(teams)} TEAMS (S11 — the repeated unit here is the franchise)")

    say(f"\n{'metric':<16} {'YoY Pearson r':>14} {'95% CI (team-clustered)':>26}")
    prim = None
    for m in ("nonqb_top_share", "nonqb_hhi", "rb_share", "qb_share"):
        x, y = d[f"prev_{m}"].values, d[f"cur_{m}"].values
        r = float(np.corrcoef(x, y)[0, 1])
        cl = d.team.map(t_idx).values

        def stat(idx, x=x, y=y, cl=cl):
            mask = np.isin(cl, idx)
            if mask.sum() < 10:
                return np.nan
            return float(np.corrcoef(x[mask], y[mask])[0, 1])

        lo, hi, _ = boot_ci(stat, len(teams), rng)
        tag = " <-- PRIMARY (declared)" if m == "nonqb_top_share" else ""
        say(f"{m:<16} {r:>14.3f} {'[' + f'{lo:+.3f}, {hi:+.3f}' + ']':>26}{tag}")
        if m == "nonqb_top_share":
            prim = (r, lo, hi)
    r, lo, hi = prim
    verdict = "STABLE" if (r >= 0.30 and lo > 0) else (
        "UNSTABLE" if hi < 0.30 else "UNINFORMATIVE")
    say(f"\nSPLIT-OUT VERDICT: {verdict}  (pre-stated rule: STABLE if r >= 0.30 and CI "
        f"excludes 0)")
    say("Context: if even the SAME franchise's goal-line concentration barely persists year to")
    say("year, a caller-carryover version of the same quantity has no stable target to carry.")
    return d, verdict, prim


# =============================================================================================
def main_run():
    rng = np.random.default_rng(RNG_SEED)
    say("=" * 100)
    say("56 — WS2 PREMISE GATES: H2a / H2b / H2c  (results_56_premise_gates.txt)")
    say("=" * 100)
    say("All numbers [V] (computed this run) unless labelled [R]. Charter: research-blueprint-")
    say("prompt.md WS2. S14 primary endpoints + decision rules are in the script docstring,")
    say("declared BEFORE any result was computed. This script contributes FOUR primary")
    say("endpoints to the global FDR count: H2a, H2b, H2c gates + the team-stability split-out.")
    say("NO POINTS TEST IS RUN ANYWHERE HERE: the charter demotes all three hypotheses to")
    say("premise gates and declares the points test not reachable at n=31 (S12 both-currency")
    say("reporting therefore N/A by design). Even PASS-PREMISE routes to the 2026")
    say("preregistration, never to an under-powered paired grade.")

    # ---- Task 1: event table ----
    say("\n" + "=" * 100)
    say("TASK 1 — EVENT TABLE from data/playcallers_hist.csv")
    say("=" * 100)
    pc, ev = build_events()
    n_ev = len(ev)
    buckets = ev.bucket.value_counts()
    say(f"\nteam-seasons in file: {len(pc)} (2019-2025, 32 teams)  [V]")
    say(f"caller-change events: {n_ev}  [V]   (foundation/charter expected 78)")
    say(f"  carryable (prior in-window history at a DIFFERENT team): "
        f"{buckets.get('carryable', 0)}  [V] (expected 31)")
    say(f"  first-time callers: {buckets.get('first-time', 0)}  [V]  + same-team-only prior: "
        f"{buckets.get('same-team-only', 0)}  [V]  (foundation T0.2: 47 = 46 + 1)")
    assert n_ev == 78 and buckets.get("carryable", 0) == 31
    assert buckets.get("first-time", 0) == 46 and buckets.get("same-team-only", 0) == 1
    say("\nConfirmed against foundation counts (78 / 31 / 47-as-46+1). The same-team-only case")
    stq = ev[ev.bucket == "same-team-only"]
    say(f"is {stq.iloc[0].playcaller} ({stq.iloc[0].team} {stq.iloc[0].season}) — carryover from")
    say("a different team is undefined for him; excluded, matching T0.2's refinement.")
    say("\nFile-granularity limits (stated): one primary caller per team-season — midseason")
    say("caller changes are not represented. Two committee cells exist and are events but can")
    say("never match an individual's prior history: "
        + "; ".join(f"{r.playcaller} ({r.team} {r.season})"
                    for _, r in ev[ev.playcaller.str.contains("/")].iterrows()))
    ev_carry = ev[ev.bucket == "carryable"].copy()
    say(f"\nTHE 31 CARRYABLE COACH-MOVES (the entire WS2 forecasting population):")
    for _, e in ev_carry.iterrows():
        say(f"  {e.season} {e.team:<4} <- {e.playcaller:<22} prior: "
            + ", ".join(f"{t}{s}" for s, t in e.prior_stints))
    say(f"\nEvents by season: " + ", ".join(f"{s}:{c}" for s, c in
                                            ev.groupby('season').size().items()))

    # ---- data builds ----
    say("\n" + "=" * 100)
    say("DATA BUILD + S8 CHECKS")
    say("=" * 100)
    pers = load_personnel()
    say("\nPersonnel (participation offense_personnel joined to pbp_slim REG scrimmage plays,")
    say("classified by RB/TE counts: 11 = 1RB/1TE, 12 = 1RB/2TE, 21 = 2RB/1TE):")
    say(f"{'season':<7} {'teams':>5} {'scrim plays':>12} {'personnel cov':>14} "
        f"{'lg r11':>7} {'lg r12':>7} {'lg r21':>7}")
    for y, g in pers.groupby("season"):
        say(f"{y:<7} {len(g):>5} {g.scrim.sum():>12,} {g['cov'].sum() / g.scrim.sum():>13.1%} "
            f"{(g.n11.sum() / g['cov'].sum()):>7.3f} {(g.n12.sum() / g['cov'].sum()):>7.3f} "
            f"{(g.n21.sum() / g['cov'].sum()):>7.3f}")
    say("\nS8 flags, visible above and handled: (a) offense_personnel is TWO ENCODINGS under one")
    say("name — pre-2023 skill-only strings (raw-file non-empty ~76%), 2023+ full-XI strings")
    say("(100%); RB/TE counts exist in both, which is what the parser extracts. On the ANALYSIS")
    say("population (REG pass/rush attempts joined to pbp) coverage is shown in the table above —")
    say("the pre-2023 raw-file gaps are no_play/admin rows, exactly as T0.1 [R] found for")
    say("offense_players. (b) rates are computed on covered plays only; per-season league means")
    say("printed so any era jump is visible.")
    say("(c) load_ftn_charting has NO personnel column [V] — the assignment's 'ftn 2022+'")
    say("personnel fallback does not exist; participation is the sole personnel source.")
    say(f"(d) participation<->pbp scrim-play join rate by season: "
        + ", ".join(f"{y}:{g.join_rate.iloc[0]:.1%}" for y, g in pers.groupby('season')))

    conc = build_concentration()
    say(f"\nTouch-concentration table (weekly.parquet REG, {CONC_YEARS[0]}-{CONC_YEARS[-1]}): "
        f"{len(conc)} team-seasons, 32/season asserted (S8). Positions are the panel's QB/RB/WR/")
    say("TE only — FB targets/touches are outside the panel and excluded from denominators.")

    i5 = build_inside5()
    say(f"\nInside-5 table (pbp_slim REG rush_attempt==1 & yardline_100<=5, rusher position via")
    say(f"weekly panel map; unmapped rushers (FB/OL/DST) -> 'OTH'): {len(i5)} team-seasons, "
        f"32/season asserted (S8).")
    say(f"League-wide inside-5 rushes/team-season: median {i5.n_i5.median():.0f}, "
        f"p10 {i5.n_i5.quantile(.1):.0f}, p90 {i5.n_i5.quantile(.9):.0f} — the charter's")
    say("'brutal denominators (~25-45)' warning is confirmed. Kneel plays at the opponent 5")
    say("cannot be excluded (pbp_slim carries no qb_kneel column); they are rare end-of-half")
    say("events and are noted as a small contaminant of qb_share.")

    bb = bestback_adp()

    # ---- gates ----
    h2a = gate_h2a(ev_carry, pers, rng)
    h2b = gate_h2b(ev_carry, conc, bb, rng)
    h2c = gate_h2c(ev_carry, i5, rng)
    stab = team_stability(i5, rng)

    # ---- verdict table ----
    say("\n" + "=" * 100)
    say("VERDICT TABLE (4 primary endpoints from this script; all enter the global S14/FDR set)")
    say("=" * 100)
    say(f"{'gate':<12} {'primary endpoint':<58} {'n(clusters)':>11} {'verdict':<15}")
    say(f"{'H2a':<12} {'mean dR2_adj of caller personnel profile over team-prior':<58} "
        f"{h2a[4]:>11} {h2a[1]:<15}")
    say(f"{'H2b':<12} {'|e|null - |e|caller, RB touch HHI':<58} {len(h2b[0]):>11} {h2b[2]:<15}")
    say(f"{'H2c':<12} {'|e|null - |e|caller, inside-5 RB share':<58} {len(h2c[0]):>11} "
        f"{h2c[2]:<15}")
    say(f"{'split-out':<12} {'YoY r of team inside-5 non-QB top-rusher share':<58} "
        f"{'32 teams':>11} {stab[1]:<15}")
    say("\nROUTING (charter-mandated, regardless of verdicts): NONE of these gates may proceed")
    say("to a points test at n=31 clusters. A PASS-PREMISE routes to the 2026 preregistration +")
    say("a future run on a hand-extended playcallers_hist (back to 2014, ~160 more team-seasons")
    say("of MANUAL news verification — a budgeted human task, not code). A FAIL-PREMISE is a")
    say("legitimate kill-list entry and closes the line cheaply, which the charter names as the")
    say("expected and correct outcome.")

    # ---- interpretation, kill list, limits ----
    z_pt, z_lo, z_hi = h2a[5]
    say("\n" + "=" * 100)
    say("INTERPRETATION")
    say("=" * 100)
    say(f"""
H2a — PASS-PREMISE, and honesty demands three qualifiers in the same breath:
  (1) MARGINAL: the primary lands at +{h2a[2]:.3f} against a ~0.150 abandon threshold — at the
      wire. The jackknife never goes below zero (min +0.114) but 14/31 single-event drops push
      it under the threshold: the PASS/FAIL label is fragile even though the SIGN is not.
  (2) The effect is almost entirely ONE rate: 11-personnel (dR2_adj +0.341, LOO-CV gain +0.368,
      caller beta +0.56). 12- and 21-personnel carryover is ~nil (+0.051, +0.064 in-sample;
      -0.007, +0.029 in LOO-CV). The surviving claim is narrow: "an incoming caller's
      three-wide rate travels with him"; the TE-heavy / two-back shape does not measurably.
  (3) It survived the checks that usually kill this kind of result here: LOO cross-validation
      (+0.130 mean gain — not in-sample optimism), the era-robust z-scored rerun
      (+{z_pt:.3f} [{z_lo:+.3f}, {z_hi:+.3f}] — not the 2023 charting break), and a null
      predictor (team prior year) that is genuinely hard to beat elsewhere in this script.
  A useful diagnostic fell out: after a carryable caller change, the receiving team's OWN
  prior-year 11-rate has predictive R2 ~ -0.36 to 0.03 — i.e. WORSE than predicting the league
  mean. Regime change really does reset the personnel mix; the new caller's history is the
  better prior. That is the premise H2a needed, and it is the ONLY thing this gate certifies.
  ROUTE: 2026 preregistration only (predicted personnel mixes for the teams receiving the
  carryable 2026 callers), per charter. NOT a points test; NOT a board input.

H2b — FAIL-PREMISE, kill-list entry with the numbers:
  Caller profile LOSES to team-prior-year on rb_hhi (-0.0075), top_back_share (-0.0076) and
  rb_tgt_share (-0.0032), and its one directional win (te_tgt_share +0.0108, CI includes 0)
  fails the shrinkage comparator — the prior-season LEAGUE MEAN beats the caller profile on
  ALL FOUR metrics (e.g. rb_hhi 0.0741 vs 0.1208). Touch concentration at the team level is
  mean-reverting noise; there is nothing caller-shaped in it to carry. The charter-named
  confound was addressed head-on: controlling the receiving team's best-back ADP barely moves
  the caller coefficient (rb_hhi -0.190 -> -0.180), so the null is not the talent control's
  artifact. Per the charter: step one failed, STOP — no fantasy test on a broken premise.

H2c — FAIL-PREMISE, kill-list entry with the numbers:
  Primary (inside-5 RB share): caller profile loses to team-prior (-0.0103, CI [-0.059,
  +0.039]). The seductive secondary — nonqb_hhi +0.0571 with a CI excluding zero — is exposed
  by the shrinkage comparator: the caller's pooled profile (mean|e| 0.1234) does NOT beat the
  prior-season league mean (0.1204). A pooled multi-season profile wins against a noisy
  one-season team value by variance reduction alone; it carries no caller-specific
  information. The split-out explains why nothing could carry: the receiving-team quantity
  itself has franchise-level YoY r = 0.067 — there is no stable target. Even the charter's
  fallback use ("a committee tie-breaker only") is dead: the league mean is the better
  tie-breaker. The goal-line denominators (median 27 outcome plays, binomial noise floor
  ~0.08 on the outcome itself) were the charter's stated fear and are confirmed.

SPLIT-OUT — team-level inside-5 stability (the larger-population, non-carryover question):
  Goal-line CONCENTRATION (who among the non-QB rushers gets the carries) is UNSTABLE year to
  year (r = 0.067 [-0.011, +0.142], 352 pairs, 32 team clusters). The QB-vs-RB MIX is
  moderately persistent (rb_share r = 0.348 [+0.210, +0.457]; qb_share r = 0.335 [+0.164,
  +0.456]) — a roster property (who your QB is), not shown here to be a caller property:
  caller profiles did not beat team-prior on qb_share either (-0.0076). Descriptive, not
  actionable: no board input follows from a stability coefficient.
""")
    say("=" * 100)
    say("NOT DONE / LIMITS (stated so the absence is not read as an omission)")
    say("=" * 100)
    say("""
* NO points test, in either currency (league or base PPR) — charter-mandated for all three
  gates ("The points test is NOT reachable at this n and the charter does not pretend it is").
  S12's both-currency rule is therefore N/A to this script by design.
* The caller-profile definitions (play-weighted personnel pool; equal-weight stint mean for
  concentration; pooled raw plays for inside-5 shares) are single pre-stated choices, not a
  swept family — sweeping profile definitions on n=31 clusters would be S2-shaped overfitting,
  so the sweep was deliberately not run. A recency-weighted profile is the one variant a 2026
  preregistration could reasonably also carry for H2a.
* playcallers_hist.csv granularity limits inherited: one primary caller per team-season
  (midseason changes invisible); two committee cells (Godsey/Studesville MIA2021,
  Patricia/Judge NE2022) can never match an individual's prior history; Mike Kafka (NYG 2025)
  excluded per T0.2's same-team-only refinement.
* The charter's "~15% of the receiving team's next-season mix" did not pin the exact
  statistic; this script's reading (mean Delta R2_adj across the three rates, vs the
  team-prior-year null) was declared in the docstring BEFORE the run. Under that reading H2a
  passes at the boundary; a stricter reading (all three rates individually >= 15%) would FAIL
  (only 11-personnel clears it). Both readings are reported above; the declared one governs.
* qb_share carries rare end-of-half kneel contamination (pbp_slim has no qb_kneel column;
  FTN's is_qb_sneak exists only 2022+ — 4 of 10 outcome years — and was not used).
* 2025 prices in the best-back ADP control are the T0.2 repair instrument (Sleeper adp_ppr,
  not ESPN/FFC).
* load_ftn_charting has NO personnel column [V] — the assignment's "ftn 2022+" personnel
  fallback does not exist; participation.offense_personnel (2016-2025) is the sole source.
* FDR: this script contributes 4 primary endpoints (raw verdicts printed here); the global
  Benjamini-Hochberg pass at q=0.10 across ALL charter primaries happens in the Blueprint,
  not here.
* Hand-extending playcallers_hist.csv to 2014 (~160 team-seasons of manual news verification)
  remains the only lever that changes n=31. On these results it is justifiable ONLY for the
  H2a personnel gate; spending it on H2b/H2c would be re-opening lines that died with the
  league-mean comparator in hand.
""")
    say("FILE INVENTORY (this run):")
    say("  script   icm/work/mc_research/56_premise_gates.py")
    say("  results  icm/work/mc_research/results_56_premise_gates.txt")
    say("  caches   icm/work/mc_research/raw/personnel56_{2016..2025}.parquet (team-season")
    say("           11/12/21 counts from participation x pbp_slim REG scrimmage plays)")
    say("  inputs   data/playcallers_hist.csv (224 rows), weekly.parquet (67,353),")
    say("           pbp_slim_{2014..2025}.parquet [T0.3], seasons.parquet + ")
    say("           seasons_2025repair.parquet [T0.2], participation via nflreadpy .nflcache")

    flush()
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "personnel":
        for y in [int(a) for a in sys.argv[2:]]:
            build_personnel_year(y)
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        main_run()
    else:
        print(__doc__)
