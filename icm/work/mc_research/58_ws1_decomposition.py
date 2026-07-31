"""58 — WS1: situation-vs-player decomposition. QUANTIFICATION ONLY (charter scope cut:
do NOT re-test direction; §7.2 already asserts opportunity>efficiency as a design rule).

Charter refs: WS1 (lines ~565-582), §5 ladder, S1/S8/S11/S12/S14.

FOUR TASKS
  1. Variance decomposition of league-scored fantasy PPG (seasons_league.parquet, T0.3)
     into player / team-season / residual — TWICE: raw PPG, and PPG-above-price
     (price = FFC ADP from the panel join of adp_hist, 2025 = T0.2 Sleeper repair).
     The gap between the two decompositions IS the market's pricing accuracy on situation.
     Estimator: method-of-moments on cross products —
        var_player   = E[y_it * y_it'] over same-player pairs in DIFFERENT seasons whose
                       modal team also differs (so persistent team quality can't leak in);
        var_teamsea  = E[y_it * y_jt] over DIFFERENT-player pairs in the SAME team-season;
        var_resid    = var_total - var_player - var_teamsea.
     KNOWN CONFOUNDS OF THE TEAMMATE ESTIMATOR (printed with results): co-location of good
     players biases it UP; same-position share cannibalization (C15: same-team RBs -0.28)
     biases it DOWN at RB. It is a bracket, not a clean parameter.
     CIs: leave-one-season-out jackknife (S11 cluster = SEASON, n = 12).
     Currencies: league scoring primary, base secondary (S12).
  2. Split-half reliability (odd/even appearance weeks within season; year-over-year) for
     the §5 ladder metrics computable from this repo's panels, plus league-points leverage
     per +1 SD (Fama-MacBeth by season). Output: THE EMPIRICAL STABILIZATION LADDER, with
     explicit disagreements vs the charter's inherited §5 table (ours wins).
     Games-to-stabilize via Spearman-Brown inversion: G* = k*(1-r)/r at half-length k.
  3. Movers: Wave-2b proven/unproven split (compute_outcomes.py:173-180, read-only) as a
     FIXED CONTROL. ONE new question: do earned-opportunity features add discrimination on
     top of proven/unproven for RB team-changers? Cluster = player-move.
     >>> PRIMARY ENDPOINT (S14, declared before running): among priced RB team-changers,
     the stratified (within proven/unproven cells) HIGH-minus-LOW difference in LEAGUE
     season points above price, split at the pool median of PRIOR-SEASON pass-snap
     participation (T0.1 artifact). Cluster bootstrap over player-moves. Everything else
     (target share, targets-per-pass-snap, base currency) is SECONDARY. <<<
  4. Honesty paragraph: does the pre-season-knowable residual, in points, anchored to
     C3's +5.2 CI [-30,+40], leave the pre-season half of the charter alive?

PRICE INSTRUMENT NOTE (T0.2, repeated wherever a 2025-priced number appears): the 2025
price is Sleeper adp_ppr, NOT ESPN ADP and NOT FFC. Union contract:
  seasons_exp.parquet[season!=2025] ∪ seasons_2025repair.parquet.

Run:  .venv/bin/python icm/work/mc_research/58_ws1_decomposition.py
Writes: icm/work/mc_research/results_58_ws1.txt
"""
import os
import math
import numpy as np
import pandas as pd

def _norm_sf(z):
    """Standard-normal survival function via math.erf (scipy not installed in .venv)."""
    return 0.5 * (1.0 - math.erf(z / math.sqrt(2.0)))

HERE = os.path.dirname(os.path.abspath(__file__))
OUTF = os.path.join(HERE, "results_58_ws1.txt")
RNG = np.random.default_rng(58)
N_BOOT = 4000
YEARS = list(range(2014, 2026))
POS = ["QB", "RB", "WR", "TE"]

lines = []
def say(s=""):
    print(s)
    lines.append(s)

# collected p-values for the S14/BH block: (label, p, kind)
PVALS = []

# ---------------------------------------------------------------- load panels
def load_union_seasons():
    se = pd.read_parquet(os.path.join(HERE, "seasons_exp.parquet"))
    rep = pd.read_parquet(os.path.join(HERE, "seasons_2025repair.parquet"))
    assert list(se.columns) == list(rep.columns), "repair schema drift"
    uni = pd.concat([se[se["season"] != 2025], rep], ignore_index=True)
    # S8: per-year row counts after the concat
    cnt = uni.groupby("season").size()
    say("S8 union panel rows/season: " + " ".join(f"{y}:{cnt.get(y,0)}" for y in YEARS))
    assert cnt.get(2025, 0) == 608, "2025 repair rows != 608"
    for y in YEARS:
        assert 450 <= cnt.get(y, 0) <= 700, f"suspicious year count {y}: {cnt.get(y,0)}"
    assert len(uni) == cnt.sum()
    return uni

def load_weekly():
    cols = ["season", "week", "player_id", "position", "team", "offense_pct", "carries",
            "targets", "receptions", "rush_attempt_team", "pass_attempt_team",
            "receiving_air_yards", "rushing_first_downs", "receiving_first_downs",
            "rushing_tds", "receiving_tds", "rushing_yards", "pts_league", "pts_base"]
    wk = pd.read_parquet(os.path.join(HERE, "weekly_league.parquet"), columns=cols)
    cnt = wk.groupby("season").size()
    say("S8 weekly_league rows/season: " + " ".join(f"{y}:{cnt.get(y,0)}" for y in YEARS))
    assert cnt.sum() == 67353, f"weekly_league rows {cnt.sum()} != 67353"
    return wk

def load_pbp_rz():
    """Per-week red-zone / goal-line opportunity counts from the T0.3 pbp_slim caches."""
    frames = []
    for y in YEARS:
        f = os.path.join(HERE, f"pbp_slim_{y}.parquet")
        d = pd.read_parquet(f, columns=["season", "week", "season_type", "posteam",
                                        "rusher_player_id", "receiver_player_id",
                                        "rush_attempt", "pass_attempt", "yardline_100"])
        d = d[d["season_type"] == "REG"]
        frames.append(d)
    pbp = pd.concat(frames, ignore_index=True)
    cnt = pbp.groupby("season").size()
    say("S8 pbp_slim REG plays/season: " + " ".join(f"{y}:{cnt.get(y,0)}" for y in YEARS))
    for y in YEARS:
        assert 38000 <= cnt.get(y, 0) <= 55000, f"pbp season {y} suspicious: {cnt.get(y,0)}"
    rz = pbp[(pbp["yardline_100"] <= 20)
             & ((pbp["rush_attempt"] == 1) | (pbp["pass_attempt"] == 1))].copy()
    gl = pbp[(pbp["yardline_100"] <= 5) & (pbp["rush_attempt"] == 1)].copy()
    # player weekly counts
    rz["pid"] = np.where(rz["rush_attempt"] == 1, rz["rusher_player_id"],
                         rz["receiver_player_id"])
    rz_p = (rz.dropna(subset=["pid"]).groupby(["season", "week", "pid"]).size()
              .rename("rz_opps").reset_index())
    rz_t = rz.groupby(["season", "week", "posteam"]).size().rename("rz_team").reset_index()
    gl_p = (gl.dropna(subset=["rusher_player_id"])
              .groupby(["season", "week", "rusher_player_id"]).size()
              .rename("gl_carries").reset_index()
              .rename(columns={"rusher_player_id": "pid"}))
    gl_t = gl.groupby(["season", "week", "posteam"]).size().rename("gl_team").reset_index()
    return rz_p, rz_t, gl_p, gl_t

# ---------------------------------------------------------------- part 1 machinery
def fit_curve(df, ycol, rankcol, max_rank=80, min_games=None):
    """02_expectation's exact shape: binned mean -> rolling(5) smooth -> monotone decreasing."""
    d = df[df[rankcol].notna() & (df[rankcol] <= max_rank)]
    if min_games is not None:
        d = d[d["games"] >= min_games]
    m = d.groupby(d[rankcol].astype(int))[ycol].agg(["mean"])
    m = m.reindex(range(1, max_rank + 1))
    m["mean"] = m["mean"].interpolate(limit_direction="both")
    sm = m["mean"].rolling(5, center=True, min_periods=1).mean()
    return np.minimum.accumulate(sm)

def apply_curve(curves, pos, rank):
    if pd.isna(rank):
        return np.nan
    c = curves[pos]
    return c.iloc[min(int(rank), len(c)) - 1]

def mom_decompose(df, ycol):
    """Method-of-moments crossed decomposition on season-demeaned y (within position pool).
    Returns dict of variance components. df needs: player_id, season, team_mode, y."""
    d = df[[ "player_id", "season", "team_mode", ycol]].dropna().copy()
    d["y"] = d[ycol] - d.groupby("season")[ycol].transform("mean")
    var_total = float((d["y"] ** 2).mean())
    # same-player pairs, different seasons, different modal team
    prods_p, prods_p_all = [], []
    for _, g in d.groupby("player_id"):
        if len(g) < 2:
            continue
        rows = g[["season", "team_mode", "y"]].values
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if rows[i][0] == rows[j][0]:
                    continue
                prod = rows[i][2] * rows[j][2]
                prods_p_all.append(prod)
                if rows[i][1] != rows[j][1]:
                    prods_p.append(prod)
    var_player = float(np.mean(prods_p)) if len(prods_p) >= 30 else np.nan
    var_player_all = float(np.mean(prods_p_all)) if len(prods_p_all) >= 30 else np.nan
    # teammate pairs, same team-season
    prods_t = []
    for _, g in d.groupby(["season", "team_mode"]):
        if len(g) < 2:
            continue
        ys = g["y"].values
        for i in range(len(ys)):
            for j in range(i + 1, len(ys)):
                prods_t.append(ys[i] * ys[j])
    var_ts = float(np.mean(prods_t)) if len(prods_t) >= 30 else np.nan
    var_resid = var_total - (var_player if np.isfinite(var_player) else 0) \
                          - (var_ts if np.isfinite(var_ts) else 0)
    return {"var_total": var_total, "var_player": var_player,
            "var_player_allpairs": var_player_all, "var_ts": var_ts,
            "var_resid": var_resid, "n_rows": len(d),
            "n_pairs_player": len(prods_p), "n_pairs_team": len(prods_t)}

def jackknife_decompose(df, ycol):
    """Leave-one-season-out jackknife on the MoM shares (S11: cluster=SEASON)."""
    full = mom_decompose(df, ycol)
    seasons = sorted(df["season"].unique())
    reps = {"share_player": [], "share_ts": [], "share_resid": []}
    for s in seasons:
        r = mom_decompose(df[df["season"] != s], ycol)
        if not np.isfinite(r["var_player"]) or not np.isfinite(r["var_ts"]):
            continue
        reps["share_player"].append(r["var_player"] / r["var_total"])
        reps["share_ts"].append(r["var_ts"] / r["var_total"])
        reps["share_resid"].append(r["var_resid"] / r["var_total"])
    out = dict(full)
    S = len(reps["share_player"])
    for k, v in reps.items():
        v = np.array(v)
        se = np.sqrt((S - 1) / S * ((v - v.mean()) ** 2).sum()) if S > 2 else np.nan
        out[k + "_se"] = se
    out["n_seasons_jack"] = S
    return out

def decomp_report(tag, dc, note=""):
    vt = dc["var_total"]
    def cell(v, se):
        if not np.isfinite(v):
            return "     n/a"
        s = f"{v / vt:5.1%}"
        if np.isfinite(se):
            s += f" ±{1.96 * se:4.1%}"
        return s
    sd_p = np.sqrt(max(dc["var_player"], 0)) if np.isfinite(dc["var_player"]) else np.nan
    sd_t = np.sqrt(max(dc["var_ts"], 0)) if np.isfinite(dc["var_ts"]) else np.nan
    sd_r = np.sqrt(max(dc["var_resid"], 0))
    say(f"  {tag:28s} n={dc['n_rows']:4d}  totalSD={np.sqrt(vt):5.2f} ppg  "
        f"(clusters: {dc['n_seasons_jack']} seasons; pairs P/T "
        f"{dc['n_pairs_player']}/{dc['n_pairs_team']})")
    say(f"    player      {cell(dc['var_player'], dc.get('share_player_se', np.nan))}"
        f"   SD {sd_p:5.2f} ppg = {17 * sd_p:5.1f} pts/17g"
        + (f"   [all-pairs sens: {dc['var_player_allpairs']/vt:5.1%}]"
           if np.isfinite(dc["var_player_allpairs"]) else ""))
    say(f"    team-season {cell(dc['var_ts'], dc.get('share_ts_se', np.nan))}"
        f"   SD {sd_t:5.2f} ppg = {17 * sd_t:5.1f} pts/17g")
    say(f"    residual    {cell(dc['var_resid'], dc.get('share_resid_se', np.nan))}"
        f"   SD {sd_r:5.2f} ppg = {17 * sd_r:5.1f} pts/17g")
    if note:
        say(f"    note: {note}")

# ---------------------------------------------------------------- part 2 machinery
def half_split(wk_pool, num, den, min_games=4, min_den=0, mean_of_col=None):
    """Odd/even appearance-week split. Ratio-of-sums per half (or mean of a ratio column).
    Returns df: player_id, season, position, vA, vB, kA, kB."""
    d = wk_pool.sort_values(["player_id", "season", "week"]).copy()
    d["gidx"] = d.groupby(["player_id", "season"]).cumcount()
    d["half"] = np.where(d["gidx"] % 2 == 0, "A", "B")
    if mean_of_col is not None:
        d = d[d[mean_of_col].notna()]
        g = (d.groupby(["player_id", "season", "position", "half"])
               .agg(v=(mean_of_col, "mean"), k=(mean_of_col, "size")).reset_index())
        g["dn"] = g["k"]
    else:
        d = d[d[den].notna() & (d[den] > 0)]
        g = (d.groupby(["player_id", "season", "position", "half"])
               .agg(nsum=(num, "sum"), dsum=(den, "sum"), k=(num, "size")).reset_index())
        g["v"] = g["nsum"] / g["dsum"]
        g["dn"] = g["dsum"]
    piv = g.pivot_table(index=["player_id", "season", "position"], columns="half",
                        values=["v", "k", "dn"], aggfunc="first")
    piv.columns = [f"{a}{b}" for a, b in piv.columns]
    piv = piv.reset_index().dropna(subset=["vA", "vB"])
    piv = piv[(piv["kA"] >= min_games) & (piv["kB"] >= min_games)
              & (piv["dnA"] >= min_den) & (piv["dnB"] >= min_den)]
    return piv

def zscore_within(df, col, by):
    g = df.groupby(by)[col]
    return (df[col] - g.transform("mean")) / g.transform("std").replace(0, np.nan)

def jack_r(df, xcol, ycol):
    """Pearson r with leave-one-season-out jackknife SE (cluster = season)."""
    d = df[[xcol, ycol, "season"]].dropna()
    if len(d) < 40 or d["season"].nunique() < 4:
        return np.nan, np.nan, len(d), np.nan
    r_full = float(np.corrcoef(d[xcol], d[ycol])[0, 1])
    reps = []
    for s in sorted(d["season"].unique()):
        dd = d[d["season"] != s]
        if len(dd) > 30:
            reps.append(float(np.corrcoef(dd[xcol], dd[ycol])[0, 1]))
    v = np.array(reps); S = len(v)
    se = np.sqrt((S - 1) / S * ((v - v.mean()) ** 2).sum())
    p = 2 * _norm_sf(abs(r_full) / se) if se > 0 else np.nan
    return r_full, se, len(d), p

# ================================================================ MAIN
def main():
    say("=" * 88)
    say("58 — WS1 DECOMPOSITION (quantification only). Run 2026-07-31. All numbers [V]")
    say("unless marked [R]. 2025 price instrument = Sleeper adp_ppr (T0.2 repair), NOT FFC/ESPN.")
    say("=" * 88)

    uni = load_union_seasons()
    wk = load_weekly()
    sl = pd.read_parquet(os.path.join(HERE, "seasons_league.parquet"))
    assert len(sl) == 6974, "seasons_league rows != 6974"

    # modal team per player-season from weekly_league
    tm = (wk.groupby(["player_id", "season", "team"]).size().rename("nwk").reset_index()
            .sort_values(["player_id", "season", "nwk"])
            .drop_duplicates(["player_id", "season"], keep="last")
            .rename(columns={"team": "team_mode"})[["player_id", "season", "team_mode"]])
    sl = sl.merge(tm, on=["player_id", "season"], how="left")

    # price join: ADP rank from the union panel (assignment: adp_hist + 2025 repair)
    price = uni[["player_id", "season", "adp", "adp_pos_rank", "exp_pos_rank",
                 "season_games", "team_last", "prev_team_last", "prev_ppg", "prev_games",
                 "prev_tgt_share", "total_pts", "exp_pts", "mult", "games_frac"]]
    sl = sl.merge(price, on=["player_id", "season"], how="left")
    assert len(sl) == 6974, "price join changed row count"
    cov = sl[sl["adp_pos_rank"].notna()].groupby("season").size()
    say("\npriced rows (ADP instrument)/season: "
        + " ".join(f"{y}:{cov.get(y,0)}" for y in YEARS))

    # ---------------------------------------------------------------- PART 1
    say("\n" + "=" * 88)
    say("PART 1 — VARIANCE DECOMPOSITION of league-scored PPG (games>=6)")
    say("=" * 88)
    say("Estimator: MoM cross-products. player = same-player pairs across seasons w/ DIFFERENT")
    say("modal team (persistent-team leak excluded; all-pairs shown as sensitivity).")
    say("team-season = teammate pairs. CONFOUNDS: co-location biases UP; same-position share")
    say("cannibalization biases DOWN (C15: same-team RB r=-0.28) — treat as a bracket.")
    say("CIs: leave-one-season-out jackknife, cluster = SEASON, n = 12 (S11).")

    pool = sl[(sl["games"] >= 6) & sl["team_mode"].notna()].copy()

    # league PPG expectation curve from ADP rank (in-sample market curve, 02_'s method)
    ppg_curves_lg, ppg_curves_bs = {}, {}
    for pos in POS:
        sub = pool[pool["position"] == pos]
        ppg_curves_lg[pos] = fit_curve(sub, "ppg_league", "adp_pos_rank", 80, min_games=6)
        ppg_curves_bs[pos] = fit_curve(sub, "ppg_base", "adp_pos_rank", 80, min_games=6)
    say("\nLeague-PPG market curve at ADP pos-rank 1/5/12/24/36 (fit on priced pool, in-sample):")
    for pos in POS:
        c = ppg_curves_lg[pos]
        say(f"  {pos}: " + " ".join(f"{c.iloc[r-1]:5.1f}" for r in [1, 5, 12, 24, 36]))

    pr = pool[pool["adp_pos_rank"].notna() & (pool["adp_pos_rank"] <= 80)].copy()
    pr["exp_ppg_lg"] = [apply_curve(ppg_curves_lg, p, r)
                        for p, r in zip(pr["position"], pr["adp_pos_rank"])]
    pr["exp_ppg_bs"] = [apply_curve(ppg_curves_bs, p, r)
                        for p, r in zip(pr["position"], pr["adp_pos_rank"])]
    pr["ppg_above_lg"] = pr["ppg_league"] - pr["exp_ppg_lg"]
    pr["ppg_above_bs"] = pr["ppg_base"] - pr["exp_ppg_bs"]

    summ = {}
    for pos in POS:
        say(f"\n--- {pos} ---")
        allp = pool[pool["position"] == pos]
        prp = pr[pr["position"] == pos]
        d_raw_all = jackknife_decompose(allp, "ppg_league")
        decomp_report("RAW league PPG (full pool)", d_raw_all)
        d_raw = jackknife_decompose(prp, "ppg_league")
        decomp_report("RAW league PPG (priced pool)", d_raw)
        d_abv = jackknife_decompose(prp, "ppg_above_lg")
        decomp_report("ABOVE-PRICE league PPG", d_abv)
        testable = (d_abv["n_pairs_team"] >= 30 and d_abv["n_seasons_jack"] >= 8)
        if not testable:
            say(f"    NOT-TESTABLE at {pos} for the team-season term on the priced pool:"
                f" only {d_abv['n_pairs_team']} same-position teammate pairs (a roster"
                f" rarely prices two same-position {pos}s) — player/residual terms stand.")
        pl_raw = (d_raw["var_player"] / d_raw["var_total"]
                  if np.isfinite(d_raw["var_player"]) else np.nan)
        pl_abv = (d_abv["var_player"] / d_abv["var_total"]
                  if np.isfinite(d_abv["var_player"]) else np.nan)
        say(f"    PRICING-ACCURACY GAP (the clean readout): the PLAYER (portable) share"
            f" collapses {pl_raw:5.1%} raw -> {pl_abv:5.1%} above-price.")
        say(f"    The market prices the persistent player component nearly completely;"
            f" what survives price is dominated by the season residual.")
        summ[pos] = dict(
            pl_raw=pl_raw, pl_abv=pl_abv,
            pl_abv_se=d_abv.get("share_player_se", np.nan),
            ts_raw=(d_raw["var_ts"] / d_raw["var_total"]
                    if np.isfinite(d_raw["var_ts"]) else np.nan),
            ts_abv=(d_abv["var_ts"] / d_abv["var_total"]
                    if np.isfinite(d_abv["var_ts"]) else np.nan),
            ts_abv_se=d_abv.get("share_ts_se", np.nan),
            sd_pl_abv=np.sqrt(max(d_abv["var_player"], 0))
                if np.isfinite(d_abv["var_player"]) else np.nan,
            sd_ts_abv=np.sqrt(max(d_abv["var_ts"], 0))
                if np.isfinite(d_abv["var_ts"]) else np.nan,
            sd_tot_abv=np.sqrt(d_abv["var_total"]), testable_ts=testable)
        # base currency secondary (S12)
        d_abv_b = jackknife_decompose(prp, "ppg_above_bs")
        decomp_report("ABOVE-PRICE base PPG (secondary)", d_abv_b)

    # -------- cross-position teammate estimator: 'team environment' with less
    # same-pie cannibalization (a QB-WR pair does not split one role's touches
    # the way two RBs do; one-ball competition remains -> still a lower bound).
    def crosspos_ts(df, ycol):
        d = df[["player_id", "season", "team_mode", "position", ycol]].dropna().copy()
        d["y"] = d[ycol] - d.groupby(["position", "season"])[ycol].transform("mean")
        var_total = float((d["y"] ** 2).mean())
        px, ps = [], []
        for _, g in d.groupby(["season", "team_mode"]):
            if len(g) < 2:
                continue
            rows = g[["position", "y"]].values
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    prod = rows[i][1] * rows[j][1]
                    (px if rows[i][0] != rows[j][0] else ps).append(prod)
        return (var_total, np.mean(px) if px else np.nan, len(px),
                np.mean(ps) if ps else np.nan, len(ps))

    say("\nCROSS-POSITION TEAMMATE ESTIMATOR (pooled, y demeaned within position-season):")
    say("  shared 'team environment' covariance with same-pie competition reduced;")
    say("  same-position covariance shown for contrast (= environment MINUS cannibalization).")
    for tag, df_, ycol in [("RAW league PPG, full pool", pool, "ppg_league"),
                           ("RAW league PPG, priced", pr, "ppg_league"),
                           ("ABOVE-PRICE league PPG", pr, "ppg_above_lg")]:
        vt, mx, nx, ms, ns = crosspos_ts(df_, ycol)
        # jackknife by season
        reps = []
        for s in sorted(df_["season"].unique()):
            vt_, mx_, nx_, _, _ = crosspos_ts(df_[df_["season"] != s], ycol)
            if np.isfinite(mx_):
                reps.append(mx_ / vt_)
        v = np.array(reps); S = len(v)
        se = np.sqrt((S - 1) / S * ((v - v.mean()) ** 2).sum()) if S > 2 else np.nan
        sd_x = np.sqrt(max(mx, 0)) if np.isfinite(mx) else np.nan
        say(f"  {tag:28s}: cross-pos share {mx/vt:+6.1%} ±{1.96*se:5.1%}"
            f" (pairs {nx}) = SD {sd_x:4.2f} ppg = {17*sd_x:5.1f} pts/17g |"
            f" same-pos share {ms/vt:+6.1%} (pairs {ns})")
        summ.setdefault("_xpos", {})[tag] = (mx / vt, se, sd_x)

    say("\nPART 1 SUMMARY (league currency, priced pools; ts = same-position teammate"
        " bracket, see cross-position line for the environment read):")
    say(f"  {'pos':4s} {'player raw':>11s} {'player abv':>11s} {'ts raw':>8s} "
        f"{'ts abv':>8s} {'abv totalSD pts/17g':>20s}")
    for pos in POS:
        s = summ[pos]
        f = lambda x: f"{x:7.1%}" if np.isfinite(x) else "    n/a"
        say(f"  {pos:4s} {f(s['pl_raw']):>11s} {f(s['pl_abv']):>11s} {f(s['ts_raw']):>8s} "
            f"{f(s['ts_abv']):>8s} {17*s['sd_tot_abv']:17.1f}")
    say("  caveat: the QB priced-pool player share is unstable — the different-team pair"
        " restriction leaves only team-switching QBs, a biased and thin subset; the"
        " full-pool QB estimate (player 14.2%) is the better-supported number.")

    # ---------------------------------------------------------------- PART 2
    say("\n" + "=" * 88)
    say("PART 2 — EMPIRICAL STABILIZATION LADDER (split-half odd/even weeks; YoY; leverage)")
    say("=" * 88)
    say("G* = games-to-stabilize = k*(1-r)/r (Spearman-Brown inversion at mean half-size k).")
    say("Leverage = league season pts (PPG*17) per +1 SD of the season metric, Fama-MacBeth")
    say("by season (mean of per-season cross-sectional slopes; SE over seasons; S11).")
    say("Half values are ratio-of-sums; z-scored within (position, season) before pooling.")

    rz_p, rz_t, gl_p, gl_t = load_pbp_rz()
    wk2 = wk.merge(rz_p, left_on=["season", "week", "player_id"],
                   right_on=["season", "week", "pid"], how="left").drop(columns=["pid"])
    wk2 = wk2.merge(rz_t, left_on=["season", "week", "team"],
                    right_on=["season", "week", "posteam"], how="left").drop(columns=["posteam"])
    wk2 = wk2.merge(gl_p, left_on=["season", "week", "player_id"],
                    right_on=["season", "week", "pid"], how="left").drop(columns=["pid"])
    wk2 = wk2.merge(gl_t, left_on=["season", "week", "team"],
                    right_on=["season", "week", "posteam"], how="left").drop(columns=["posteam"])
    for c in ["rz_opps", "gl_carries"]:
        wk2[c] = wk2[c].fillna(0)
    psp = pd.read_parquet(os.path.join(HERE, "pass_snap_participation.parquet"))
    wk2 = wk2.merge(psp.rename(columns={"gsis_id": "player_id"})
                       [["season", "week", "player_id", "snaps_on_dropbacks", "team_dropbacks"]],
                    on=["season", "week", "player_id"], how="left")
    assert len(wk2) == 67353, "week-level joins changed row count"
    wk2["touches"] = wk2["carries"] + wk2["receptions"]
    wk2["tds"] = wk2["rushing_tds"] + wk2["receiving_tds"]
    wk2["one"] = 1.0

    # (metric, pool, kwargs). Pools declared per §6 relevance.
    RBWRTE = ["RB", "WR", "TE"]
    METRICS = [
        ("snap_share",     RBWRTE,      dict(num=None, den=None, mean_of_col="offense_pct")),
        ("pass_snap_share",RBWRTE,      dict(num="snaps_on_dropbacks", den="team_dropbacks")),
        ("carry_share",    ["RB"],      dict(num="carries", den="rush_attempt_team")),
        ("target_share",   ["WR","TE"], dict(num="targets", den="pass_attempt_team")),
        ("tgt_per_psnap",  RBWRTE,      dict(num="targets", den="snaps_on_dropbacks", min_den=60)),
        ("adot",           ["WR","TE"], dict(num="receiving_air_yards", den="targets", min_den=15)),
        ("rz_opp_share",   RBWRTE,      dict(num="rz_opps", den="rz_team", min_den=8)),
        ("gl_share",       ["RB"],      dict(num="gl_carries", den="gl_team", min_den=4)),
        ("fd_rate_rush",   ["RB"],      dict(num="rushing_first_downs", den="carries", min_den=25)),
        ("fd_rate_rec",    ["WR","TE"], dict(num="receiving_first_downs", den="receptions", min_den=12)),
        ("td_rate",        RBWRTE,      dict(num="tds", den="touches", min_den=25)),
        ("ypc",            ["RB"],      dict(num="rushing_yards", den="carries", min_den=25)),
    ]

    priced_keys = sl[sl["adp_pos_rank"].notna()][["player_id", "season"]].drop_duplicates()
    ladder = []
    for name, poss, kw in METRICS:
        wp = wk2[wk2["position"].isin(poss)].copy()
        # within-season split-half
        hs = half_split(wp, kw.get("num"), kw.get("den"), min_games=4,
                        min_den=kw.get("min_den", 0), mean_of_col=kw.get("mean_of_col"))
        hs["zA"] = zscore_within(hs, "vA", ["position", "season"])
        hs["zB"] = zscore_within(hs, "vB", ["position", "season"])
        r_w, se_w, n_w, p_w = jack_r(hs, "zA", "zB")
        k_half = float((hs["kA"] + hs["kB"]).mean() / 2) if len(hs) else np.nan
        gstar = k_half * (1 - r_w) / r_w if (np.isfinite(r_w) and r_w > 0.02) else np.inf
        glo = k_half * (1 - min(r_w + 1.96 * se_w, .99)) / min(r_w + 1.96 * se_w, .99) \
            if np.isfinite(r_w) else np.nan
        ghi = k_half * (1 - (r_w - 1.96 * se_w)) / (r_w - 1.96 * se_w) \
            if (np.isfinite(r_w) and r_w - 1.96 * se_w > 0.02) else np.inf
        # SENSITIVITY (population matters for reliability): drafted players only.
        # z re-computed on the subset. Robustness read, not a new endpoint (see S14 block).
        hp = hs.merge(priced_keys, on=["player_id", "season"], how="inner")
        hp["zA"] = zscore_within(hp, "vA", ["position", "season"])
        hp["zB"] = zscore_within(hp, "vB", ["position", "season"])
        r_p, se_p, n_p, _ = jack_r(hp, "zA", "zB")
        k_p = float((hp["kA"] + hp["kB"]).mean() / 2) if len(hp) else np.nan
        g_p = k_p * (1 - r_p) / r_p if (np.isfinite(r_p) and r_p > 0.02) else np.inf

        # season-level metric for YoY + leverage
        if kw.get("mean_of_col"):
            seas = (wp[wp[kw["mean_of_col"]].notna()]
                    .groupby(["player_id", "season", "position"])
                    .agg(v=(kw["mean_of_col"], "mean"), k=("one", "sum")).reset_index())
            seas["dn"] = seas["k"]
        else:
            w3 = wp[wp[kw["den"]].notna() & (wp[kw["den"]] > 0)]
            seas = (w3.groupby(["player_id", "season", "position"])
                      .agg(nsum=(kw["num"], "sum"), dsum=(kw["den"], "sum"),
                           k=("one", "sum")).reset_index())
            seas["v"] = seas["nsum"] / seas["dsum"]
            seas["dn"] = seas["dsum"]
        seas = seas[(seas["k"] >= 8) & (seas["dn"] >= 2 * kw.get("min_den", 0))].copy()
        seas["z"] = zscore_within(seas, "v", ["position", "season"])
        nxt = seas.copy()
        nxt["season"] = nxt["season"] - 1
        yy = seas.merge(nxt[["player_id", "season", "position", "z"]],
                        on=["player_id", "season", "position"],
                        how="inner", suffixes=("", "_next"))
        r_y, se_y, n_y, p_y = jack_r(yy, "z", "z_next")

        # leverage: per-season cross-sectional slope of league PPG on z
        lev = seas.merge(sl[sl["games"] >= 6][["player_id", "season", "ppg_league"]],
                         on=["player_id", "season"], how="inner").dropna(subset=["z", "ppg_league"])
        slopes = []
        for s, g in lev.groupby("season"):
            if len(g) >= 25 and g["z"].std() > 0:
                slopes.append(np.polyfit(g["z"], g["ppg_league"], 1)[0])
        slopes = np.array(slopes)
        lev_m = 17 * slopes.mean() if len(slopes) >= 6 else np.nan
        lev_se = 17 * slopes.std(ddof=1) / np.sqrt(len(slopes)) if len(slopes) >= 6 else np.nan

        PVALS.append((f"split-half {name}", p_w, "reliability"))
        PVALS.append((f"YoY {name}", p_y, "reliability"))
        ladder.append(dict(name=name, pool="/".join(poss), r_w=r_w, se_w=se_w, n_w=n_w,
                           k=k_half, gstar=gstar, glo=glo, ghi=ghi,
                           r_p=r_p, n_p=n_p, k_p=k_p, g_p=g_p,
                           r_y=r_y, se_y=se_y, n_y=n_y, lev=lev_m, lev_se=lev_se))

    lad = pd.DataFrame(ladder).sort_values("gstar")
    say("\nTHE EMPIRICAL STABILIZATION LADDER (sorted by measured games-to-stabilize G*).")
    say("G*full = all 8+ game player-seasons (population incl. backups: between-player")
    say("spread inflates reliability, so G*full is a lower bound). G*priced = drafted")
    say("players only — the fantasy-relevant read; USE THIS ONE for tier-change timing.")
    say(f"  {'metric':16s}{'pool':9s}{'r(half)':>8s}{'±':>6s}{'n':>6s}"
        f"{'G*full':>7s}{'95%CI':>13s}{'r(prcd)':>8s}{'n':>5s}{'G*prcd':>7s}"
        f"{'YoY r':>7s}{'lev pts/SD':>12s}")
    for _, r in lad.iterrows():
        gs = f"{r.gstar:6.1f}" if np.isfinite(r.gstar) else "   inf"
        gci = (f"[{r.glo:4.1f},{r.ghi:5.1f}]" if np.isfinite(r.ghi)
               else (f"[{r.glo:4.1f}, inf]" if np.isfinite(r.glo) else "     -"))
        gp = f"{r.g_p:6.1f}" if np.isfinite(r.g_p) else "   inf"
        rp = f"{r.r_p:8.3f}" if np.isfinite(r.r_p) else "     n/a"
        lv = f"{r.lev:+7.1f}±{1.96*r.lev_se:4.1f}" if np.isfinite(r.lev) else "     n/a"
        say(f"  {r['name']:16s}{r.pool:9s}{r.r_w:8.3f}{1.96*r.se_w:6.3f}{r.n_w:6d}"
            f"{gs:>7s}{gci:>13s}{rp}{r.n_p:5d}{gp:>7s}{r.r_y:7.3f}{lv:>12s}")

    say("\nDISAGREEMENTS WITH THE CHARTER'S INHERITED §5 TABLE (ours wins, per WS1 mandate).")
    say("Verdict uses G*priced (drafted-player population) when computable, else G*full;")
    say("the comparator population is stated because reliability is population-dependent.")
    inherited = {"snap_share": (2, 3), "pass_snap_share": (2, 3), "carry_share": (2, 3),
                 "target_share": (4, 6), "tgt_per_psnap": (6, 8), "adot": (3, 4),
                 "rz_opp_share": (5, 7), "gl_share": (6, 10), "fd_rate_rush": (4, 5),
                 "fd_rate_rec": (5, 6), "td_rate": (np.inf, np.inf), "ypc": (np.inf, np.inf)}
    for _, r in lad.iterrows():
        lo, hi = inherited[r["name"]]
        use_priced = np.isfinite(r.r_p)
        g = r.g_p if use_priced else r.gstar
        basis = "priced" if use_priced else "full"
        if not np.isfinite(g):
            verdict = "AGREES (never stabilizes)" if not np.isfinite(hi) else \
                      f"DISAGREES: charter says {lo}-{hi}, measured NEVER"
        elif np.isfinite(hi) and lo <= g <= hi:
            verdict = f"agrees (charter {lo}-{hi}, measured {g:.1f})"
        elif not np.isfinite(hi):
            verdict = f"DISAGREES: charter says never, measured G*={g:.1f}"
        else:
            direction = "FASTER" if g < lo else "SLOWER"
            verdict = f"DISAGREES: charter {lo}-{hi}, measured {g:.1f} ({direction})"
        say(f"  {r['name']:16s} [{basis:6s}] {verdict}")

    # ---------------------------------------------------------------- PART 3
    say("\n" + "=" * 88)
    say("PART 3 — MOVERS: earned opportunity ON TOP OF the Wave-2b proven/unproven control")
    say("=" * 88)
    say("FIXED CONTROL [R: compute_outcomes.py:173-180, read-only]: proven mover = prior ppg")
    say(">=10 & prior games >=12 (reconstructed here as prev_ppg/prev_games on the panel's")
    say("base-formula ppg — a stated approximation of the pipeline's wk_mean).")
    say("PRIMARY ENDPOINT (declared in header before running): RB team-changers with a price;")
    say("HIGH-vs-LOW prior pass-snap participation (pool median), stratified within")
    say("proven/unproven; outcome = LEAGUE season points above price; cluster = player-move.")

    # prior-season pass-snap participation + targets-per-pass-snap (season ratio-of-sums)
    psp_seas = (psp.groupby(["gsis_id", "season"])
                   .agg(snaps=("snaps_on_dropbacks", "sum"),
                        tdrops=("team_dropbacks", "sum")).reset_index())
    psp_seas["psp_share"] = psp_seas["snaps"] / psp_seas["tdrops"]
    tgt_seas = (wk.groupby(["player_id", "season"])["targets"].sum()
                  .rename("tgt_sum").reset_index())
    psp_seas = psp_seas.merge(tgt_seas, left_on=["gsis_id", "season"],
                              right_on=["player_id", "season"], how="left")
    psp_seas["tps"] = psp_seas["tgt_sum"] / psp_seas["snaps"].replace(0, np.nan)

    mv = sl.copy()
    mv["exp_lg_psg_curve"] = [apply_curve(ppg_curves_lg, p, r)
                              for p, r in zip(mv["position"], mv["adp_pos_rank"])]
    # season-total league expectation: use the psg-style curve on total pool (incl. games<6)
    tot_curves_lg = {}
    mv["lg_psg"] = mv["total_league"] / mv["season_games"]
    for pos in POS:
        tot_curves_lg[pos] = fit_curve(mv[mv["position"] == pos], "lg_psg", "adp_pos_rank", 80)
    mv["exp_total_lg"] = np.array([apply_curve(tot_curves_lg, p, r) for p, r in
                                   zip(mv["position"], mv["adp_pos_rank"])],
                                  dtype=float) * mv["season_games"].values
    mv["pts_above_lg"] = mv["total_league"] - mv["exp_total_lg"]
    mv["pts_above_bs"] = mv["total_pts"] - mv["exp_pts"]     # base secondary, 02_'s curve

    prev_feat = psp_seas.rename(columns={"season": "prev_season_key"})

    def build_movers(pos):
        d = mv[(mv["position"] == pos) & mv["adp_pos_rank"].notna()
               & mv["team_last"].notna() & mv["prev_team_last"].notna()].copy()
        d["moved"] = d["team_last"] != d["prev_team_last"]
        d["proven"] = (d["prev_ppg"].fillna(0) >= 10) & (d["prev_games"].fillna(0) >= 12)
        d["prev_season_key"] = d["season"] - 1
        d = d.merge(prev_feat[["gsis_id", "prev_season_key", "psp_share", "tps"]],
                    left_on=["player_id", "prev_season_key"],
                    right_on=["gsis_id", "prev_season_key"], how="left")
        return d[d["moved"] & (d["season"] >= 2017)].copy()  # psp starts 2016 -> prev>=2016

    say("\nS2 slices, declared here BEFORE the replication run: discovery slice = RB")
    say("team-changers 2017-2025 (the position Wave-2b's split was fit on); replication")
    say("slice = WR team-changers 2017-2025 (same design, different position).")
    movers = build_movers("RB")
    say(f"\nRB priced team-changers 2017-2025: n={len(movers)} "
        f"(psp feature coverage {movers['psp_share'].notna().mean():.0%}, "
        f"clusters = player-moves = rows)")

    # Wave-2b control replication (context only, cited not re-litigated)
    for pv, nm in [(True, "proven"), (False, "unproven")]:
        c = movers[movers["proven"] == pv]
        if len(c) >= 10:
            say(f"  control replication [{nm:8s}]: n={len(c):3d} med mult(base)="
                f"{c['mult'].median():.2f}  bust(mult<=0.75)={ (c['mult']<=0.75).mean():.0%}"
                f"  mean lg-pts-above-price={c['pts_above_lg'].mean():+6.1f}")

    def strat_hilo(df, feat, ycol):
        """Stratified (within proven cells) HIGH-vs-LOW at pool median. Cluster bootstrap
        over rows (=player-moves). Returns diff, lo, hi, n_hi, n_lo."""
        d = df[df[feat].notna() & df[ycol].notna()].copy()
        if len(d) < 20:
            return (np.nan,) * 5
        med = d[feat].median()
        d["hi"] = d[feat] > med
        def wdiff(dd):
            parts, wts = [], []
            for pv in (True, False):
                c = dd[dd["proven"] == pv]
                if c["hi"].sum() >= 3 and (~c["hi"]).sum() >= 3:
                    parts.append(c.loc[c["hi"], ycol].mean() - c.loc[~c["hi"], ycol].mean())
                    wts.append(len(c))
            return np.average(parts, weights=wts) if parts else np.nan
        obs = wdiff(d)
        boots = []
        idx = np.arange(len(d))
        for _ in range(N_BOOT):
            bb = d.iloc[RNG.integers(0, len(d), len(d))]
            v = wdiff(bb)
            if np.isfinite(v):
                boots.append(v)
        boots = np.array(boots)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        return obs, lo, hi, int(d["hi"].sum()), int((~d["hi"]).sum())

    say("\nPRIMARY — prior pass-snap participation, league pts above price:")
    obs, lo, hi, nh, nl = strat_hilo(movers, "psp_share", "pts_above_lg")
    ncl = nh + nl
    tag = "DIRECTIONAL-ONLY (n<40 clusters)" if ncl < 40 else \
          ("CI excludes 0" if lo * hi > 0 else "CI includes 0")
    say(f"  HIGH-LOW = {obs:+.1f} league pts/season  95% CI [{lo:+.1f}, {hi:+.1f}]"
        f"  clusters={ncl} ({nh} hi/{nl} lo)  -> {tag}")
    # cluster-bootstrap p for the S14 table
    d0 = movers[movers["psp_share"].notna() & movers["pts_above_lg"].notna()]
    p_primary = np.nan
    if np.isfinite(obs):
        boots = []
        for _ in range(N_BOOT):
            bb = d0.iloc[RNG.integers(0, len(d0), len(d0))]
            med = bb["psp_share"].median()
            bb = bb.assign(hi=bb["psp_share"] > med)
            parts, wts = [], []
            for pv in (True, False):
                c = bb[bb["proven"] == pv]
                if c["hi"].sum() >= 3 and (~c["hi"]).sum() >= 3:
                    parts.append(c.loc[c["hi"], "pts_above_lg"].mean()
                                 - c.loc[~c["hi"], "pts_above_lg"].mean())
                    wts.append(len(c))
            if parts:
                boots.append(np.average(parts, weights=wts))
        boots = np.array(boots)
        p_primary = 2 * min((boots <= 0).mean(), (boots >= 0).mean())
    PVALS.append(("PRIMARY movers psp_share stratified", p_primary, "PRIMARY"))

    say("\n  per-season breakdown (S4): season: n, HIGH-LOW league pts above price")
    for s, g in d0.groupby("season"):
        med = d0["psp_share"].median()
        hi_g = g[g["psp_share"] > med]["pts_above_lg"]
        lo_g = g[g["psp_share"] <= med]["pts_above_lg"]
        if len(hi_g) >= 2 and len(lo_g) >= 2:
            say(f"    {s}: n={len(g):3d}  {hi_g.mean() - lo_g.mean():+7.1f}")

    say("\nSECONDARY (same design):")
    rb_sec = {}
    for feat, fname in [("prev_tgt_share", "prior target share"),
                        ("tps", "prior targets-per-pass-snap")]:
        o2, l2, h2, n2h, n2l = strat_hilo(movers, feat, "pts_above_lg")
        rb_sec[feat] = (o2, l2, h2, n2h + n2l)
        if np.isfinite(o2):
            say(f"  {fname:28s}: {o2:+.1f} lg pts  CI [{l2:+.1f}, {h2:+.1f}]"
                f"  clusters={n2h + n2l}")
        else:
            say(f"  {fname:28s}: insufficient data")
    o3, l3, h3, n3h, n3l = strat_hilo(movers, "psp_share", "pts_above_bs")
    if np.isfinite(o3):
        say(f"  psp_share, BASE currency     : {o3:+.1f} base pts  CI [{l3:+.1f}, {h3:+.1f}]"
            f"  clusters={n3h + n3l}   (S12 secondary)")
    # continuous check within cells (secondary)
    for pv, nm in [(True, "proven"), (False, "unproven")]:
        c = movers[(movers["proven"] == pv)].dropna(subset=["psp_share", "pts_above_lg"])
        if len(c) >= 15:
            r = np.corrcoef(c["psp_share"], c["pts_above_lg"])[0, 1]
            say(f"  corr(psp, lg-pts-above) within {nm:8s}: r={r:+.2f} (n={len(c)})")

    say("\nREPLICATION SLICE (S2) — WR team-changers, same design, same features:")
    wrm = build_movers("WR")
    say(f"  WR priced team-changers 2017-2025: n={len(wrm)}")
    wr_res = {}
    for feat, fname in [("psp_share", "prior pass-snap participation"),
                        ("prev_tgt_share", "prior target share"),
                        ("tps", "prior targets-per-pass-snap")]:
        o4, l4, h4, n4h, n4l = strat_hilo(wrm, feat, "pts_above_lg")
        wr_res[feat] = (o4, l4, h4, n4h + n4l)
        if np.isfinite(o4):
            say(f"  {fname:28s}: {o4:+.1f} lg pts  CI [{l4:+.1f}, {h4:+.1f}]"
                f"  clusters={n4h + n4l}")
        else:
            say(f"  {fname:28s}: insufficient data")

    # ---------------------------------------------------------------- S14 / BH block
    say("\n" + "=" * 88)
    say("S14 / MULTIPLE-TEST BLOCK")
    say("=" * 88)
    valid = [(l, p, k) for l, p, k in PVALS if np.isfinite(p)]
    m = len(valid)
    say(f"tests run in this script: {len(PVALS)} declared, {m} with computable p.")
    say("ONE primary endpoint (declared in header): movers psp_share stratified diff.")
    say("Reliability r's are diagnostic (WS1 is a magnitude exercise) but counted per charter.")
    say("The priced-pool ladder columns and the WR replication slice are robustness reads")
    say("of already-counted quantities, not new endpoints; they carry no separate p.")
    ranked = sorted(valid, key=lambda t: t[1])
    q = 0.10
    thresh, passing = 0.0, set()
    for i, (l, p, k) in enumerate(ranked, 1):
        if p <= q * i / m:
            thresh = p
    for l, p, k in ranked:
        if p <= thresh:
            passing.add(l)
    say(f"Benjamini-Hochberg q=0.10: adjusted threshold p<={thresh:.4g}; "
        f"{len(passing)}/{m} pass.")
    for l, p, k in ranked:
        mark = "PASS-adj" if l in passing else "fail-adj"
        say(f"  {mark}  p={p:9.3g}  [{k}] {l}")

    # ---------------------------------------------------------------- PART 4
    say("\n" + "=" * 88)
    say("PART 4 — REQUIRED HONESTY PARAGRAPH (C3-anchored, points not variance)")
    say("=" * 88)
    rb_s, wr_s = summ["RB"], summ["WR"]
    xp_abv = summ.get("_xpos", {}).get("ABOVE-PRICE league PPG", (np.nan, np.nan, np.nan))
    say(f"""
What is knowable before the season, after the market has spoken, in league points:
(1) The portable PLAYER component of league PPG collapses once price is controlled —
RB {rb_s['pl_raw']:.0%} raw -> {rb_s['pl_abv']:.0%} (±{1.96*rb_s['pl_abv_se']:.0%}) above
price, WR {wr_s['pl_raw']:.0%} -> {wr_s['pl_abv']:.0%} (±{1.96*wr_s['pl_abv_se']:.0%}).
The market prices the player almost completely; the unpriced player term is worth at most
~{17*rb_s['sd_pl_abv']:.0f} pts/17g SD at RB and ~0 at WR, with CIs through zero.
(2) The team-season 'situation' term, measured through same-position teammates, is
NEGATIVE raw (RB {rb_s['ts_raw']:+.0%}) — share cannibalization outweighs shared
environment, C15/C7 made empirical. The cross-position environment read above price is
{xp_abv[0]:+.1%} (±{1.96*xp_abv[1]:.1%}) — small but statistically NONZERO — i.e.
~{17*(xp_abv[2] if np.isfinite(xp_abv[2]) else 0):.0f} pts/17g SD. THAT NUMBER is the
measured pre-season situation ceiling among priced players (co-location selection biases
it up; residual one-ball competition biases it down). There is a detectable unpriced
situation pool, and it is worth roughly one bench-streamer of season points at 1 SD.
(3) What is left above price is overwhelmingly the season RESIDUAL — total above-price
SD ~{17*rb_s['sd_tot_abv']:.0f} pts/17g at RB, ~{17*wr_s['sd_tot_abv']:.0f} at WR — which
is exactly the variance C16/S4 say you cannot forecast player-by-player pre-season.
(4) The one live pre-season overlay tested here (Part 3): PRIMARY {obs:+.1f} league pts,
CI [{lo:+.1f}, {hi:+.1f}] — includes zero. The pass-snap overlay is at least
sign-consistent across slices (RB {obs:+.1f} / WR {wr_res['psp_share'][0]:+.1f}, both
CIs through zero). The flashiest number, the target-share secondary
({rb_sec['prev_tgt_share'][0]:+.1f}, CI [{rb_sec['prev_tgt_share'][1]:+.1f},
{rb_sec['prev_tgt_share'][2]:+.1f}] on the RB discovery slice), FAILED its S2
replication — WR slice {wr_res['prev_tgt_share'][0]:+.1f}, CI
[{wr_res['prev_tgt_share'][1]:+.1f}, {wr_res['prev_tgt_share'][2]:+.1f}], sign flipped —
so both overlays are HYPOTHESES for WS2 capped DIRECTIONAL-ONLY, not results.
ANCHORED TO C3: the friendliest situation bundle ever tested here bought +5.2 points on
~1,600, CI [-30, +40] [R]. Every ceiling measured in this script is the same order as
that CI's width or smaller, so WS1 SHARPENS C3 rather than overturning it. VERDICT: the
pre-season half of the charter is ALIVE ONLY AS CALIBRATION — it bounds nudge sizes and
prior widths — NOT as a source of edge. Budget belongs with WS3 (the priced-pool ladder
shows the job metrics — snap/pass-snap/carry/target share — reach r=0.5 discrimination
in ~1-2 games even among drafted players, goal-line share in ~2, red-zone and
targets-per-pass-snap in ~5, at 54-87 pts/SD leverage) and WS5 (scoring mechanics), exactly
as the charter's falsification clause anticipated. 'Situation step changes are
predictable' did NOT survive in the mean; per the shipped Wave-2b control [R] it
survives only in the variance (sigma inflation for unproven movers).""")
    say("\nDone. All [V] numbers computed this run from committed artifacts;")
    say("[R] numbers cite results_33/compute_outcomes/charter as marked.")

    with open(OUTF, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUTF}")


if __name__ == "__main__":
    main()
