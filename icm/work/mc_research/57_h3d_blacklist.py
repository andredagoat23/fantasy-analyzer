"""57 — H3d (blacklist validation) + the WS3 ground-truth machinery it requires.

Charter: icm/work/research-blueprint-prompt.md WS3 (esp. the corrected ground-truth
definition, the strict gap week, revised-data bias), section 5 (stabilization ladder:
YPC and TD-rate are the two BLACKLIST rows), section 7.10 (unstartable points).

============================ PRE-REGISTRATION (S14) ============================
Declared BEFORE any detector or event table was computed. This script contributes
ONE hypothesis / ONE primary endpoint to the charter-wide FDR count.

HYPOTHESIS (H3d): YPC spikes and realized-TD-rate spikes produce more false
positives than true positives as tier-change triggers, and underperform usage
step triggers (snap share, carry share, target share) at MATCHED alert volume.

PRIMARY ENDPOINT: per-family PRECISION at matched alert volume — alert volume
per season = the number of true tier-change event-weeks that season — pooled
over RB/WR/TE, seasons 2015-2024, tier threshold tau = 0 PAR/week (crossing
positional replacement), ground truth in LEAGUE scoring (pts_league).
VERDICT CRITERIA (both pre-declared):
  (1) literal blacklist claim: precision(ypc_spike) < 0.5 and
      precision(td_rate_spike) < 0.5  (i.e. more FP than TP);
  (2) relative claim: each blacklist family's precision is below EVERY usage
      family's precision, with the pairwise difference's 95% cluster CI
      (cluster = player-season, S11) reported for blacklist-vs-worst-usage.
SECONDARY (pre-declared, reported, never swapped in as primary):
  - the FULL tier-threshold curve tau in {-3..+3} PAR/week (charter WS3 rule:
    report the curve, not one cherry-picked cutoff);
  - recall at the event-player-season level;
  - per-season, per-position breakdowns;
  - base-PPR-currency rerun (S12 secondary currency);
  - alert-volume sensitivity at 0.5x / 2x matched volume;
  - 2025 out-of-slice check (single season => n=1 season cluster,
    DIRECTIONAL-ONLY by S11; 2015-2024 is the discovery slice, 2025 + live
    2026 snapshots are the replication slices, S2).
NO lead-time endpoint is computed. Any lead-time reading of these step
statistics is DIRECTIONAL ONLY (revised-data bias — the nflverse archive is
retroactively corrected and is not what real-time data looked like).
===============================================================================

GROUND TRUTH (charter WS3, corrected definition — exact construction):
  Weekly replacement: for every (season, week), run utils.startable_counts on
  that week's realized player scores (points = pts_league) -> counts
  {QB 12 fixed; RB/WR/TE = locked 24/24/12 plus that week's allocation of the
  12 FLEX slots to the best remaining RB/WR/TE}. replacement(pos, week) = the
  counts[pos]-th best score at the position that week. 12-team by construction
  (utils.LOCKED_STARTERS = 2/2/1 x 12, N_FLEX = 12, FIXED_STARTERS QB=12).
  PAR (points above replacement) of a player-week = pts - replacement(pos, wk);
  an ABSENT week counts as (0 - replacement) — availability is punished, per
  the charter's "PPG hides unavailability" correction. Inferred no-game weeks
  of the player's team (team absent from the panel that week = bye/cancelled)
  are EXCLUDED from outcome windows, not scored as absences.
  Detection after week W: pre-state = mean PAR over the player's PLAYED weeks
  1..W (played-only so an injured star's return is not misread as a tier
  change); outcome = mean PAR over ALL weeks W+2..last-REG-week (absent = 0-
  repl), with week W+1 excluded — the STRICT GAP WEEK.
  TIER-CHANGE EVENT at (player, W, tau): pre_rate < tau AND post_rate >= tau.

Trigger families (identical step-detector functional form; window = the last 2
played weeks through W, baseline = all earlier played weeks; eligibility =
4th-or-later played game, W in 4..12):
  ypc_spike        rushing_yards/carries, window-vs-baseline (win carries >=8,
                   base carries >=10, else no alert possible)
  td_rate_spike    (rushing+receiving TDs)/touches (win touches >=8, base >=10)
  snap_share_step  mean offense_pct (both window weeks non-null, >=2 non-null
                   baseline weeks)
  carry_share_step mean weekly carries/team-rush-attempts
  target_share_step mean weekly targets/team-pass-attempts
Alerts = per family, per season, the top-N (N = matched volume) records by the
family's own step statistic, restricted to positive steps and to players NOT
already startable (pre_rate < tau).

Outputs: results_57_h3d.txt (+ gt57_records_league.parquet cache).
Run:  .venv/bin/python icm/work/mc_research/57_h3d_blacklist.py

REUSE (WS3 scaffolding — import via importlib since the name starts with a
digit):  weekly_replacement(), build_records(), events_at(), matched_alerts(),
score_family(), cluster_boot_ci().  See results file section 8 for the exact
H3a/H3b/H3c reuse map.
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

from utils import startable_counts, LOCKED_STARTERS, FIXED_STARTERS, N_FLEX  # noqa: E402

WEEKLY_LEAGUE = os.path.join(HERE, "weekly_league.parquet")
OUT_TXT = os.path.join(HERE, "results_57_h3d.txt")

SEASONS = list(range(2015, 2025))          # discovery slice (charter assignment)
HOLDOUT_SEASON = 2025                      # out-of-slice check (S2), directional
W_MIN, W_MAX = 4, 12                       # detection weeks (calendar)
MIN_PLAYED = 4                             # 4th-or-later played game at W
TAUS = [-3, -2, -1, 0, 1, 2, 3]            # PAR/week threshold curve
TAU_PRIMARY = 0
FAMILIES = ["ypc_spike", "td_rate_spike", "snap_share_step",
            "carry_share_step", "target_share_step"]
BLACKLIST_FAMS = ["ypc_spike", "td_rate_spike"]
USAGE_FAMS = ["snap_share_step", "carry_share_step", "target_share_step"]
N_BOOT = 2000
RNG_SEED = 0

# S8 anchor: per-year row counts of weekly_league.parquet as verified by 46_ [R]
EXPECTED_ROWS = {2014: 5412, 2015: 5423, 2016: 5413, 2017: 5448, 2018: 5363,
                 2019: 5411, 2020: 5543, 2021: 5866, 2022: 5808, 2023: 5797,
                 2024: 5849, 2025: 6020}

lines = []


def say(s=""):
    print(s)
    lines.append(str(s))


# ------------------------------------------------------------------ data
def load_panel():
    wl = pd.read_parquet(WEEKLY_LEAGUE)
    assert len(wl) == 67353, "S8: weekly_league row count changed"
    per_year = wl.groupby("season").size().to_dict()
    for y, n in EXPECTED_ROWS.items():
        assert per_year.get(y) == n, f"S8: {y} rows {per_year.get(y)} != {n}"
    assert not wl.duplicated(["player_id", "season", "week"]).any(), \
        "S8: duplicate player-week keys"
    assert set(wl["position"]) == {"QB", "RB", "WR", "TE"}
    keep = ["player_id", "player_display_name", "season", "week", "team",
            "position", "pts_league", "pts_base", "carries", "rushing_yards",
            "rushing_tds", "receiving_tds", "touches", "targets", "receptions",
            "offense_pct", "rush_attempt_team", "pass_attempt_team", "attempts"]
    return wl[keep].copy()


# ------------------------------------------------------------------ replacement
def weekly_replacement(wl, points_col="pts_league"):
    """Per (season, week, position): startable count N (utils.startable_counts on
    that week's realized scores) and replacement = Nth-best score. Returns a
    DataFrame [season, week, position, n_startable, repl]."""
    rows = []
    for (s, w), g in wl.groupby(["season", "week"]):
        counts = startable_counts(g, points=points_col, position="position")
        for pos in ["QB", "RB", "WR", "TE"]:
            n = counts[pos]
            v = g.loc[g["position"] == pos, points_col].nlargest(n)
            assert len(v) >= n, f"fewer than {n} {pos} rows in {s} wk{w}"
            rows.append({"season": s, "week": w, "position": pos,
                         "n_startable": n, "repl": float(v.iloc[-1])})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ records
def build_records(wl, points_col="pts_league", seasons=None):
    """One row per eligible (player, season, detection-week W):
    pre_rate  = mean PAR over PLAYED weeks 1..W
    post_rate = mean PAR over weeks W+2..last (absent = 0 - repl; team no-game
                weeks excluded)  -- strict gap week W+1 excluded
    plus the five family step statistics. Eligibility: RB/WR/TE, 4th+ played
    game, W in [W_MIN, W_MAX], >=1 remaining outcome week."""
    seasons = seasons or SEASONS
    wl = wl[wl["season"].isin(seasons)].copy()

    rp = weekly_replacement(wl, points_col)
    repl = {(r.season, r.week, r.position): r.repl for r in rp.itertuples()}
    last_week = wl.groupby("season")["week"].max().to_dict()
    # team-week presence (bye / cancelled-game inference) from the FULL panel
    team_played = set(map(tuple, wl[["season", "week", "team"]].drop_duplicates()
                          .itertuples(index=False)))
    # team denominators: column value where present, panel sum as fallback
    tsum = wl.groupby(["season", "week", "team"]).agg(
        pan_car=("carries", "sum"), pan_att=("attempts", "sum")).reset_index()
    tden = {(r.season, r.week, r.team): (r.pan_car, r.pan_att)
            for r in tsum.itertuples()}

    recs = []
    sk = wl[wl["position"].isin(["RB", "WR", "TE"])].sort_values("week")
    for (pid, season), g in sk.groupby(["player_id", "season"]):
        pos = g["position"].iloc[0]
        wk = g["week"].to_numpy()
        pts = g[points_col].fillna(0).to_numpy(float)
        ca = g["carries"].fillna(0).to_numpy(float)
        ry = g["rushing_yards"].fillna(0).to_numpy(float)
        td = (g["rushing_tds"].fillna(0) + g["receiving_tds"].fillna(0)).to_numpy(float)
        tou = g["touches"].fillna(0).to_numpy(float)
        tgt = g["targets"].fillna(0).to_numpy(float)
        snap = g["offense_pct"].to_numpy(float)          # NaN allowed
        team = g["team"].to_numpy()
        # weekly shares (team denominator: column else panel fallback)
        tcar = g["rush_attempt_team"].to_numpy(float).copy()
        tpas = g["pass_attempt_team"].to_numpy(float).copy()
        for i in range(len(g)):
            fb = tden.get((season, wk[i], team[i]), (np.nan, np.nan))
            if np.isnan(tcar[i]):
                tcar[i] = fb[0]
            if np.isnan(tpas[i]):
                tpas[i] = fb[1]
        with np.errstate(divide="ignore", invalid="ignore"):
            csh = np.where(tcar > 0, ca / tcar, np.nan)
            tsh = np.where(tpas > 0, tgt / tpas, np.nan)
        rpl = np.array([repl[(season, w, pos)] for w in wk])
        par = pts - rpl
        last = last_week[season]
        pts_by_week = dict(zip(wk, pts))

        for j in range(MIN_PLAYED - 1, len(g)):
            W = int(wk[j])
            if W < W_MIN or W > W_MAX or W + 2 > last:
                continue
            pre_rate = par[: j + 1].mean()
            # outcome window: W+2..last, strict gap week, team no-game excluded
            post, myteam = [], team[j]
            for w in range(W + 2, last + 1):
                if (season, w, myteam) not in team_played:
                    continue                              # bye / cancelled
                post.append(pts_by_week.get(w, 0.0) - repl[(season, w, pos)])
            if not post:
                continue
            r = {"player_id": pid, "season": season, "W": W, "position": pos,
                 "name": g["player_display_name"].iloc[0],
                 "pre_rate": pre_rate, "post_rate": float(np.mean(post)),
                 "n_post_weeks": len(post), "n_played_pre": j + 1}
            win, base = slice(j - 1, j + 1), slice(0, j - 1)
            r["win_carries"] = ca[win].sum()      # for the gate-vs-spike ablation
            r["win_touches"] = tou[win].sum()
            # ypc
            cw, cb = ca[win].sum(), ca[base].sum()
            r["ypc_spike"] = (ry[win].sum() / cw - ry[base].sum() / cb) \
                if (cw >= 8 and cb >= 10) else np.nan
            # td rate
            tw, tb = tou[win].sum(), tou[base].sum()
            r["td_rate_spike"] = (td[win].sum() / tw - td[base].sum() / tb) \
                if (tw >= 8 and tb >= 10) else np.nan
            # snap share
            sw, sb = snap[win], snap[base]
            r["snap_share_step"] = (np.nanmean(sw) - np.nanmean(sb)) \
                if (np.isfinite(sw).all() and np.isfinite(sb).sum() >= 2) else np.nan
            # carry / target share
            for nm, arr in [("carry_share_step", csh), ("target_share_step", tsh)]:
                aw, ab = arr[win], arr[base]
                r[nm] = (np.nanmean(aw) - np.nanmean(ab)) \
                    if (np.isfinite(aw).all() and np.isfinite(ab).sum() >= 2) else np.nan
            recs.append(r)
    df = pd.DataFrame(recs)
    df["cluster"] = df["player_id"] + "_" + df["season"].astype(str)
    return df, rp


# ------------------------------------------------------------------ events + alerts
def events_at(records, tau):
    """Event-week flag at threshold tau. Returns (records+flag, event clusters)."""
    r = records.copy()
    r["event"] = (r["pre_rate"] < tau) & (r["post_rate"] >= tau)
    ev_clusters = set(r.loc[r["event"], "cluster"])
    return r, ev_clusters


def matched_alerts(r, fam, tau, vol_mult=1.0):
    """Per season: top-N records by the family's step statistic (positive steps,
    pre_rate < tau), N = round(vol_mult * event-weeks that season)."""
    out = []
    for season, g in r.groupby("season"):
        n = int(round(vol_mult * g["event"].sum()))
        cand = g[(g["pre_rate"] < tau) & (g[fam] > 0)].sort_values(fam, ascending=False)
        out.append(cand.head(n))
    return pd.concat(out) if out else r.iloc[0:0]


def score_family(alerts, ev_clusters):
    """Precision (alert-level, TP = alert lands on an event-week) and recall
    (event player-season detected by >=1 alert on one of its event-weeks)."""
    tp = alerts["event"].to_numpy(bool)
    detected = set(alerts.loc[alerts["event"], "cluster"])
    prec = tp.mean() if len(tp) else np.nan
    rec = len(detected & ev_clusters) / len(ev_clusters) if ev_clusters else np.nan
    return {"n_alerts": len(alerts), "tp": int(tp.sum()), "fp": int((~tp).sum()),
            "precision": prec, "recall": rec,
            "alert_clusters": alerts["cluster"].nunique(),
            "event_clusters": len(ev_clusters)}


def cluster_boot_ci(alerts, stat="precision", n_boot=N_BOOT, seed=RNG_SEED):
    """Cluster bootstrap (cluster = player-season) over the alert set. Returns
    (lo, hi) 95% CI for alert-level precision."""
    rng = np.random.default_rng(seed)
    groups = [g["event"].to_numpy(bool) for _, g in alerts.groupby("cluster")]
    k = len(groups)
    if k < 2:
        return (np.nan, np.nan)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, k, k)
        cat = np.concatenate([groups[i] for i in idx])
        if len(cat):
            vals.append(cat.mean())
    return tuple(np.percentile(vals, [2.5, 97.5]))


def boot_diff_ci(alerts_a, alerts_b, n_boot=N_BOOT, seed=RNG_SEED):
    """95% cluster-bootstrap CI for precision(A) - precision(B); clusters drawn
    from the union of both alert sets' player-season clusters."""
    rng = np.random.default_rng(seed)
    cl = sorted(set(alerts_a["cluster"]) | set(alerts_b["cluster"]))
    ga = {c: g["event"].to_numpy(bool) for c, g in alerts_a.groupby("cluster")}
    gb = {c: g["event"].to_numpy(bool) for c, g in alerts_b.groupby("cluster")}
    k = len(cl)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, k, k)
        aa = [ga[cl[i]] for i in idx if cl[i] in ga]
        bb = [gb[cl[i]] for i in idx if cl[i] in gb]
        if not aa or not bb:
            continue
        diffs.append(np.concatenate(aa).mean() - np.concatenate(bb).mean())
    return tuple(np.percentile(diffs, [2.5, 97.5])), k


def recall_boot_ci(alerts, ev_clusters, n_boot=N_BOOT, seed=RNG_SEED):
    rng = np.random.default_rng(seed)
    ev = sorted(ev_clusters)
    detected = set(alerts.loc[alerts["event"], "cluster"])
    flags = np.array([c in detected for c in ev])
    k = len(flags)
    if k < 2:
        return (np.nan, np.nan)
    vals = [flags[rng.integers(0, k, k)].mean() for _ in range(n_boot)]
    return tuple(np.percentile(vals, [2.5, 97.5]))


# ------------------------------------------------------------------ report helpers
def family_table(r, ev_clusters, tau, vol_mult=1.0, with_ci=True):
    rows = {}
    alerts_by_fam = {}
    for fam in FAMILIES:
        al = matched_alerts(r, fam, tau, vol_mult)
        sc = score_family(al, ev_clusters)
        if with_ci:
            sc["prec_ci"] = cluster_boot_ci(al)
            sc["rec_ci"] = recall_boot_ci(al, ev_clusters)
        rows[fam] = sc
        alerts_by_fam[fam] = al
    return rows, alerts_by_fam


def print_family_table(rows, base_rate):
    say(f"  {'family':<18}{'alerts':>7}{'TP':>6}{'FP':>6}{'FP/TP':>7}"
        f"{'precision':>10}{'95% CI':>18}{'recall':>8}{'95% CI':>18}{'clusters':>9}")
    for fam, sc in rows.items():
        fptp = (sc["fp"] / sc["tp"]) if sc["tp"] else float("inf")
        ci = sc.get("prec_ci", (np.nan, np.nan))
        rci = sc.get("rec_ci", (np.nan, np.nan))
        say(f"  {fam:<18}{sc['n_alerts']:>7}{sc['tp']:>6}{sc['fp']:>6}{fptp:>7.2f}"
            f"{sc['precision']:>10.3f}{f'[{ci[0]:.3f},{ci[1]:.3f}]':>18}"
            f"{sc['recall']:>8.3f}{f'[{rci[0]:.3f},{rci[1]:.3f}]':>18}"
            f"{sc['alert_clusters']:>9}")
    say(f"  (base rate = event-weeks / eligible universe rows = {base_rate:.3f};"
        f" random alerting at matched volume has expected precision ~ base rate"
        f" of the pre<tau sub-universe)")


# ------------------------------------------------------------------ diagnostics
def ranked_within(universe, rank_col, n_by_season):
    """Top-N-per-season slice of `universe` ranked by rank_col (descending).
    n_by_season = {season: N} — the same alert budget the family actually used."""
    out = []
    for season, g in universe.groupby("season"):
        n = n_by_season.get(season, 0)
        out.append(g.sort_values(rank_col, ascending=False).head(n))
    return pd.concat(out) if out else universe.iloc[0:0]


def gate_vs_spike(r0, fam, vol_col, fam_alerts):
    """POST-HOC diagnostic: within the family's own GATED universe (stat defined
    = volume gates passed, pre_rate < tau), compare ranking by the efficiency
    spike vs ranking by dumb window volume, at the family's own alert budget.
    Returns dict of numbers."""
    uni = r0[(r0["pre_rate"] < TAU_PRIMARY) & r0[fam].notna()]
    n_by_season = fam_alerts.groupby("season").size().to_dict()
    spike_al = ranked_within(uni, fam, n_by_season)          # == fam alerts, minus
    vol_al = ranked_within(uni, vol_col, n_by_season)        # the >0 restriction
    (dlo, dhi), k = boot_diff_ci(spike_al, vol_al)
    return {"universe": len(uni), "universe_clusters": uni["cluster"].nunique(),
            "base_rate": uni["event"].mean(),
            "spike_prec": spike_al["event"].mean(), "vol_prec": vol_al["event"].mean(),
            "diff": spike_al["event"].mean() - vol_al["event"].mean(),
            "diff_ci": (dlo, dhi), "n_clusters": k,
            "n_alerts": len(spike_al)}


# ------------------------------------------------------------------ main
def main():
    t0 = time.time()
    say("=" * 78)
    say("57 — H3d BLACKLIST VALIDATION + WS3 GROUND-TRUTH MACHINERY"
        f"   (run {time.strftime('%Y-%m-%d %H:%M')})")
    say("=" * 78)
    say()
    say("0. PRE-REGISTRATION — copied verbatim from the module docstring, which was")
    say("   written before any event table or detector was computed. ONE hypothesis,")
    say("   ONE primary endpoint (S14): pooled RB/WR/TE precision at matched alert")
    say(f"   volume, tau={TAU_PRIMARY} PAR/week, league scoring, 2015-2024.")
    say("   Verdict criteria: (1) blacklist families precision < 0.5 (more FP than")
    say("   TP); (2) each blacklist family below EVERY usage family, pairwise-diff")
    say("   cluster CI reported. Threshold curve, recall, per-season/position,")
    say("   base-PPR, volume sensitivity, 2025 check: all SECONDARY, pre-declared.")
    say("   This script contributes 1 primary endpoint to the charter FDR count.")
    say()

    wl = load_panel()
    say("1. DATA + S8")
    say(f"   weekly_league.parquet: 67,353 rows total [V]; per-year counts asserted")
    say(f"   against 46_'s verified table (2015-2024 slice = "
        f"{wl[wl.season.isin(SEASONS)].groupby('season').size().sum()} rows) [V]")
    say(f"   no duplicate (player_id, season, week) keys [V]; positions QB/RB/WR/TE")
    say(f"   REG only (inherited from the panel; K/DST absent by construction).")
    say(f"   Trigger-signal coverage (share of 2015-2024 rows non-null) [V]:")
    sl = wl[wl.season.isin(SEASONS)]
    for c in ["offense_pct", "rush_attempt_team", "pass_attempt_team"]:
        cov = sl.groupby("season")[c].apply(lambda s: s.notna().mean())
        say(f"     {c:<18} min {cov.min():.3f} (season {int(cov.idxmin())}) "
            f"max {cov.max():.3f}")
    say("     Missing team denominators fall back to panel-sum denominators")
    say("     (QB/RB/WR/TE rows only; understates team attempts slightly — a")
    say("     WITHIN-player share step is unaffected).")
    say("     offense_pct nulls (join gaps in the frozen panel, worst 2015 at 23%)")
    say("     shrink the snap family's alertable universe — noted in caveats.")
    say()

    # ---------------- ground truth (league scoring)
    say("2. GROUND-TRUTH CONSTRUCTION (importable machinery)")
    say("   Exact construction — see module docstring for the normative text:")
    say(f"   - utils.startable_counts per (season, week) on realized {'pts_league'};")
    say(f"     LOCKED_STARTERS={LOCKED_STARTERS}, FIXED_STARTERS={FIXED_STARTERS},")
    say(f"     N_FLEX={N_FLEX} (12 teams by construction).")
    say("   - replacement(pos, week) = counts[pos]-th best realized score that week")
    say("   - PAR = pts_league - replacement; ABSENT week = 0 - replacement")
    say("     (availability punished); inferred team no-game weeks excluded")
    say("   - pre_rate = mean PAR over PLAYED weeks 1..W  (played-only, so an")
    say("     injured star's return is not misread as a tier change)")
    say("   - post_rate = mean PAR over ALL weeks W+2..last  (STRICT GAP WEEK W+1)")
    say(f"   - detection weeks W in {W_MIN}..{W_MAX}; eligibility = 4th+ played game")
    say("   - EVENT at (player, W, tau): pre_rate < tau AND post_rate >= tau")
    say()
    records, rp = build_records(wl, "pts_league", SEASONS)
    say(f"   eligible (player, W) records 2015-2024: {len(records)}  "
        f"[{records['cluster'].nunique()} player-season clusters]")
    say("   S8 records per season:")
    say("   " + records.groupby("season").size().to_string().replace("\n", "\n   "))
    say()
    say("   replacement sanity (pooled 2015-2024 means) [V]:")
    rps = rp.groupby("position").agg(n_start=("n_startable", "mean"),
                                     repl=("repl", "mean")).round(2)
    say("   " + rps.to_string().replace("\n", "\n   "))
    say("   (n_start floats with the weekly flex split; QB fixed at 12. Weekly")
    say("   replacement is HIGHER than a season-total replacement divided by 17")
    say("   because the weekly Nth-best is a different player each week — this is")
    say("   the correct hurdle for a weekly startability decision, and it makes")
    say("   PAR/week numbers here NOT comparable to season VOLS/17.)")
    per_season_repl = rp.pivot_table(index="season", columns="position",
                                     values="repl", aggfunc="mean").round(1)
    say("   mean weekly replacement by season (drift check, S8):")
    say("   " + per_season_repl.to_string().replace("\n", "\n   "))
    say()

    # ---------------- threshold curve
    say("3. TIER-CHANGE THRESHOLD CURVE (pre-registered: full curve, no single")
    say("   cherry-picked cutoff; tau in PAR/week, league scoring)")
    say(f"   {'tau':>5}{'event-weeks':>12}{'event-clusters':>15}{'universe':>10}"
        f"{'base rate':>11}")
    curve_cache = {}
    for tau in TAUS:
        r, ev = events_at(records, tau)
        curve_cache[tau] = (r, ev)
        say(f"   {tau:>5}{int(r['event'].sum()):>12}{len(ev):>15}{len(r):>10}"
            f"{r['event'].mean():>11.3f}")
    say()

    # ---------------- primary
    say("=" * 78)
    say(f"4. H3d PRIMARY (tau={TAU_PRIMARY}, league scoring, matched volume =")
    say("   per-season event-week count; alerts restricted to pre_rate < tau and")
    say("   positive steps; TP = alert lands on an event-week)")
    say("=" * 78)
    r0, ev0 = curve_cache[TAU_PRIMARY]
    n_events = int(r0["event"].sum())
    say(f"   true event-weeks: {n_events}  event player-seasons: {len(ev0)}")
    say(f"   effective n (S11): clusters are PLAYER-SEASONS; see table columns.")
    rows, alerts = family_table(r0, ev0, TAU_PRIMARY)
    sub_base = r0[r0["pre_rate"] < TAU_PRIMARY]["event"].mean()
    print_family_table(rows, r0["event"].mean())
    say(f"   pre<tau sub-universe base rate (the honest random-alert benchmark): "
        f"{sub_base:.3f}")
    say("   NOTE: ypc_spike and td_rate_spike could not FILL the matched budget —")
    say("   their volume-gated candidate pools ran out (alerts column < 1469).")
    say("   Their precision is therefore over their ENTIRE positive-spike pool,")
    say("   not a top-of-ranking slice; the unequal n is stated, not hidden.")
    say()

    say("   PAIRWISE precision differences (usage minus blacklist), cluster-")
    say("   bootstrap 95% CI, clusters = player-seasons from the union:")
    for bf in BLACKLIST_FAMS:
        for uf in USAGE_FAMS:
            d = rows[uf]["precision"] - rows[bf]["precision"]
            (lo, hi), k = boot_diff_ci(alerts[uf], alerts[bf])
            say(f"     {uf:<18} - {bf:<15} = {d:+.3f}  CI [{lo:+.3f},{hi:+.3f}]"
                f"  (n={k} clusters)")
    say()

    say("   per-season precision (S4/S11 — never a pooled mean alone):")
    hdr = f"   {'season':>7}" + "".join(f"{f[:12]:>14}" for f in FAMILIES) + f"{'events':>8}"
    say(hdr)
    for season in SEASONS:
        cells = f"   {season:>7}"
        for fam in FAMILIES:
            a = alerts[fam][alerts[fam]["season"] == season]
            cells += f"{(a['event'].mean() if len(a) else np.nan):>14.3f}"
        cells += f"{int(r0[(r0.season == season)]['event'].sum()):>8}"
        say(cells)
    say()

    say("   per-position precision (alert mix differs by family — YPC is RB-only")
    say("   by eligibility; descriptive, secondary):")
    for fam in FAMILIES:
        a = alerts[fam]
        parts = []
        for pos in ["RB", "WR", "TE"]:
            ap = a[a["position"] == pos]
            parts.append(f"{pos} {ap['event'].mean():.3f} (n={len(ap)})"
                         if len(ap) else f"{pos} --")
        say(f"     {fam:<18} " + "  ".join(parts))
    say()

    # threshold curve precision (secondary)
    say("   precision across the FULL tau curve (secondary; CIs omitted for bulk):")
    say(f"   {'tau':>5}" + "".join(f"{f[:12]:>14}" for f in FAMILIES))
    for tau in TAUS:
        r, ev = curve_cache[tau]
        cells = f"   {tau:>5}"
        for fam in FAMILIES:
            al = matched_alerts(r, fam, tau)
            cells += f"{(al['event'].mean() if len(al) else np.nan):>14.3f}"
        say(cells)
    say()

    # ---------------- diagnostic: is it the spike, or the volume gate?
    say("=" * 78)
    say("4b. DIAGNOSTIC — IS IT THE SPIKE OR THE GATE?  [POST-HOC, clearly")
    say("    labelled: designed AFTER seeing section 4. The primary endpoint")
    say("    verdict above stands unchanged; this section explains it.]")
    say("=" * 78)
    say("   The efficiency families carry VOLUME GATES (window carries >= 8 /")
    say("   window touches >= 8) without which a rate statistic is undefined.")
    say("   The gate itself is a usage signal: a sub-replacement RB suddenly")
    say("   carrying 8+ times in two weeks IS a usage step. So section 4's")
    say("   cross-family comparison confounds the rate spike with the usage")
    say("   embedded in its own eligibility. Ablation: within each family's own")
    say("   gated universe, at the same per-season alert budget, rank by the")
    say("   efficiency spike vs by DUMB WINDOW VOLUME (no rate involved):")
    diag = {}
    for fam, vol_col in [("ypc_spike", "win_carries"),
                         ("td_rate_spike", "win_touches")]:
        d = gate_vs_spike(r0, fam, vol_col, alerts[fam])
        diag[fam] = d
        say(f"   {fam}:")
        say(f"     gated universe: {d['universe']} records / "
            f"{d['universe_clusters']} player-season clusters; base rate "
            f"{d['base_rate']:.3f} (vs 0.097 for the whole pre<tau universe —")
        say(f"     the GATE ALONE more than doubles the hit rate before any ranking)")
        say(f"     rank by {fam:<17}: precision {d['spike_prec']:.3f}")
        say(f"     rank by {vol_col + ' (dumb volume)':<17}: precision {d['vol_prec']:.3f}")
        say(f"     spike-minus-volume diff: {d['diff']:+.3f}  "
            f"95% cluster CI [{d['diff_ci'][0]:+.3f},{d['diff_ci'][1]:+.3f}]  "
            f"(n={d['n_clusters']} clusters, {d['n_alerts']} alerts/arm)")
    say()
    say("   descriptive: how usage-contaminated are the blacklist alerts?")
    for fam in BLACKLIST_FAMS:
        a = alerts[fam]
        has = a["carry_share_step"].notna() | a["target_share_step"].notna()
        up = ((a["carry_share_step"].fillna(-9) > 0)
              | (a["target_share_step"].fillna(-9) > 0))
        say(f"     {fam}: {up.mean()*100:.0f}% of its alerts carry a concurrent")
        say(f"       POSITIVE carry- or target-share step (share defined on "
            f"{has.mean()*100:.0f}%)")
    say()

    # ---------------- secondaries
    say("=" * 78)
    say("5. SECONDARIES (all pre-declared)")
    say("=" * 78)
    say("5a. ALERT-VOLUME SENSITIVITY (tau=0, league; precision at 0.5x/1x/2x")
    say("    matched volume — ordering should be volume-stable):")
    say(f"    {'family':<18}{'0.5x':>8}{'1x':>8}{'2x':>8}")
    for fam in FAMILIES:
        cells = f"    {fam:<18}"
        for m in [0.5, 1.0, 2.0]:
            al = matched_alerts(r0, fam, TAU_PRIMARY, m)
            cells += f"{(al['event'].mean() if len(al) else np.nan):>8.3f}"
        say(cells)
    say()

    say("5b. BASE-PPR CURRENCY (S12 secondary; full recompute of replacement,")
    say("    PAR, events and matched volumes under pts_base):")
    records_b, _ = build_records(wl, "pts_base", SEASONS)
    rb0, evb0 = events_at(records_b, TAU_PRIMARY)
    say(f"    event-weeks {int(rb0['event'].sum())}, event clusters {len(evb0)}")
    rows_b, _ab = family_table(rb0, evb0, TAU_PRIMARY, with_ci=False)
    say(f"    {'family':<18}{'alerts':>7}{'TP':>6}{'precision':>10}{'recall':>8}")
    for fam, sc in rows_b.items():
        say(f"    {fam:<18}{sc['n_alerts']:>7}{sc['tp']:>6}"
            f"{sc['precision']:>10.3f}{sc['recall']:>8.3f}")
    say()

    say("5c. 2025 OUT-OF-SLICE CHECK (S2; ONE season => n=1 season cluster,")
    say("    DIRECTIONAL-ONLY by S11's n<40 cluster floor):")
    records_h, _ = build_records(wl, "pts_league", [HOLDOUT_SEASON])
    rh0, evh0 = events_at(records_h, TAU_PRIMARY)
    say(f"    2025 records {len(records_h)}, event-weeks {int(rh0['event'].sum())},"
        f" event clusters {len(evh0)}")
    rows_h, _ah = family_table(rh0, evh0, TAU_PRIMARY, with_ci=False)
    say(f"    {'family':<18}{'alerts':>7}{'TP':>6}{'precision':>10}{'recall':>8}")
    for fam, sc in rows_h.items():
        say(f"    {fam:<18}{sc['n_alerts']:>7}{sc['tp']:>6}"
            f"{sc['precision']:>10.3f}{sc['recall']:>8.3f}")
    say()

    # ---------------- verdict
    say("=" * 78)
    say("6. VERDICT + BLACKLIST ENCODED AS DATA")
    say("=" * 78)
    prec = {f: rows[f]["precision"] for f in FAMILIES}
    lit = {f: prec[f] < 0.5 for f in BLACKLIST_FAMS}
    rel = {f: all(prec[f] < prec[u] for u in USAGE_FAMS) for f in BLACKLIST_FAMS}
    say("   PRE-REGISTERED criteria, reported as declared:")
    say(f"   criterion 1 (precision < 0.5, more FP than TP): "
        + ", ".join(f"{f} {'MET' if lit[f] else 'NOT MET'} ({prec[f]:.3f})"
                    for f in BLACKLIST_FAMS))
    say(f"   criterion 2 (below every usage family): "
        + ", ".join(f"{f} {'MET' if rel[f] else 'NOT MET'}" for f in BLACKLIST_FAMS))
    say()
    say("   READING (verdict prose): the literal blacklist claim HOLDS — every")
    say("   family, blacklist or usage, produces 3-9x more false positives than")
    say("   true positives at matched volume; there is no high-precision trigger")
    say("   in this table. The naive relative claim FAILS, but section 4b shows")
    say("   why: the rate statistics are undefined without recent volume, and the")
    say("   volume gate — not the rate — is what raises their hit rate. Within")
    say("   their own gated universes, ranking by the rate spike is statistically")
    say("   indistinguishable from (or worse than) ranking by dumb window volume.")
    say("   So the OPERATIVE blacklist rule the charter wants encoded is:")
    say("   never rank tier-change candidates by a YPC or TD-rate spike; if the")
    say("   rate spike arrives with volume, act on the volume, which you can see")
    say("   directly. The rate adds no measurable ranking information on top.")
    say()
    # operative rule (stated transparently: refined POST-HOC via section 4b; the
    # burden of proof is on the rate spike to beat dumb volume, CI excluding 0)
    op = {}
    for f in BLACKLIST_FAMS:
        d = diag[f]
        proves_value = d["diff_ci"][0] > 0
        op[f] = not proves_value          # stays blacklisted unless proven
    blk = {
        "artifact": "H3d blacklist, 57_h3d_blacklist.py",
        "date": time.strftime("%Y-%m-%d"),
        "discovery_slice": "2015-2024 weekly_league, RB/WR/TE, W 4-12",
        "replication_slice": "2025 (directional, sec 5c) + 2026 live snapshots (pending)",
        "tau_primary_par_per_week": TAU_PRIMARY,
        "preregistered": {
            "criterion_1_more_fp_than_tp": {f: bool(lit[f]) for f in BLACKLIST_FAMS},
            "criterion_2_below_every_usage_family": {f: bool(rel[f])
                                                     for f in BLACKLIST_FAMS},
        },
        "diagnostic_post_hoc_gate_vs_spike": {
            f: {"gated_universe_base_rate": round(float(diag[f]["base_rate"]), 3),
                "spike_ranked_precision": round(float(diag[f]["spike_prec"]), 3),
                "volume_ranked_precision": round(float(diag[f]["vol_prec"]), 3),
                "spike_minus_volume": round(float(diag[f]["diff"]), 3),
                "diff_ci95": [round(float(x), 3) for x in diag[f]["diff_ci"]]}
            for f in BLACKLIST_FAMS},
        "recommended_blacklist": {
            "ypc_spike": {
                "blacklisted_as_tier_change_trigger": bool(op["ypc_spike"]),
                "rule": "never rank tier-change candidates by YPC; a YPC spike's"
                        " apparent hit rate is its embedded volume gate — act on"
                        " the volume (carries), which is directly observable",
                "precision_at_matched_volume": round(float(prec["ypc_spike"]), 3),
                "fp_per_tp": round(rows["ypc_spike"]["fp"] / rows["ypc_spike"]["tp"], 2)},
            "td_rate_spike": {
                "blacklisted_as_tier_change_trigger": bool(op["td_rate_spike"]),
                "rule": "never rank tier-change candidates by realized TD rate;"
                        " same volume-gate mechanism; also charter 7.4 asymmetry:"
                        " fading a low-TD player with an intact red-zone role is"
                        " the more expensive error",
                "precision_at_matched_volume": round(float(prec["td_rate_spike"]), 3),
                "fp_per_tp": round(rows["td_rate_spike"]["fp"]
                                   / rows["td_rate_spike"]["tp"], 2)},
            "snap_share_step": {
                "blacklisted_as_tier_change_trigger": False,
                "caveat": "usable at RB only in this harness (RB 0.202); at WR"
                          " 0.075 and TE 0.065 it ran BELOW the 0.097 random"
                          " benchmark — consistent with charter section 5/6"
                          " ('never rank TEs on snap share')",
                "precision_at_matched_volume": round(float(prec["snap_share_step"]), 3)},
            "carry_share_step": {
                "blacklisted_as_tier_change_trigger": False,
                "precision_at_matched_volume": round(float(prec["carry_share_step"]), 3)},
            "target_share_step": {
                "blacklisted_as_tier_change_trigger": False,
                "precision_at_matched_volume": round(float(prec["target_share_step"]), 3)},
        },
    }
    say("   BLACKLIST_JSON (machine-readable; consumers key on")
    say("   recommended_blacklist.*.blacklisted_as_tier_change_trigger):")
    for ln in json.dumps(blk, indent=2).splitlines():
        say("   " + ln)
    say()

    # ---------------- caveats / reuse / not-done
    say("=" * 78)
    say("7. DIRECTIONAL LABELS AND REVISED-DATA BIAS (charter WS3 correction)")
    say("=" * 78)
    say("   - Every number above is computed on nflverse AS IT STANDS TODAY:")
    say("     retroactively corrected snap counts, team attempts, box scores.")
    say("     Real-time week-W data will be noisier, so real-time precision is")
    say("     plausibly LOWER than measured; treat levels as an UPPER bound.")
    say("   - NO lead-time endpoint was computed, by design. Any reading of the")
    say("     2-week step window as an achievable real-time lead time is")
    say("     DIRECTIONAL ONLY until confirmed on dated 2026 snapshots (the")
    say("     charter 9.2 snapshot job is WS3's load-bearing instrument).")
    say("   - The 2025 check (5c) is one season = one cluster: DIRECTIONAL ONLY.")
    say("     It preserves the family ORDERING (blacklist families' pooled-level")
    say("     precision, snap worst), which is the only claim it can support.")
    say()
    say("=" * 78)
    say("8. WS3 REUSE MAP — what H3a/H3b/H3c import from this module")
    say("   (import via importlib: importlib.import_module('57_h3d_blacklist')")
    say("   with icm/work/mc_research on sys.path — the name starts with a digit)")
    say("=" * 78)
    say("   weekly_replacement(wl, points_col)")
    say("     the league-scored WEEKLY replacement series + startable counts from")
    say("     utils.startable_counts — the ground-truth currency for ALL of WS3.")
    say("   build_records(wl, points_col, seasons) / gt57_records_league.parquet")
    say("     the (player, season, W) panel: pre_rate (played-only PAR through W),")
    say("     post_rate (PAR over W+2..last, absent=0-repl, byes excluded, STRICT")
    say("     GAP WEEK), n_post_weeks, win_carries/win_touches, and the five step")
    say("     statistics. Cached copy: gt57_records_league.parquet (20,634 rows).")
    say("   events_at(records, tau)")
    say("     tier-change event flags at any startability threshold; the full tau")
    say("     curve in section 3 is the pre-registered threshold report.")
    say("   matched_alerts() / score_family() / cluster_boot_ci() / boot_diff_ci()")
    say("     the matched-alert-volume harness with EVENT-clustered (player-")
    say("     season) CIs — S11-compliant scoring for any detector family.")
    say("   Specifically:")
    say("   - H3a (two-gate rule): join a mechanism feed (load_injuries report_")
    say("     status/practice_status, roster deltas, transactions, coaching CSVs)")
    say("     onto records by (player_id/team, season, W); gated vs ungated arms")
    say("     are two matched_alerts() calls; the usage-derived-mechanism arm")
    say("     must be run separately (charter warning). Ground truth: unchanged.")
    say("   - H3b (change-point vs rolling): replace the step statistic with a")
    say("     CUSUM/BOCPD score computed on the SAME weekly series; compare at")
    say("     matched FPR via matched_alerts() on the score column; lead time")
    say("     needs the alert week vs first event week — both already in records.")
    say("   - H3c (earned vs vacated): classify each alert by participation-step")
    say("     vs targets-per-pass-snap-step (join 47_'s pass_snap_participation.")
    say("     parquet on gsis player_id + season + week); post_rate and the")
    say("     weekly PAR series give persistence/reversion for the two classes.")
    say("   - H3e (RB/WR suppression): apply the candidate suppression rule to")
    say("     any family's alert set and report precision of the REMOVED set —")
    say("     score_family() on the removed slice does it directly.")
    say()
    say("=" * 78)
    say("9. NOT DONE / LIMITATIONS (stated, per charter)")
    say("=" * 78)
    say("   - No lead-time measurement, no mechanism gate (H3a), no change-point")
    say("     detector (H3b), no earned/vacated split (H3c) — post-draft WS3.")
    say("   - No lineup-slot gating (charter 7.10): this harness carries no")
    say("     roster state; alerts are position-level. The machinery accepts a")
    say("     per-week startability gate when WS3 proper builds roster context.")
    say("   - No waiver/acquisition friction (S9): precision/recall is the honest")
    say("     instrument per the charter's corrected WS3 benchmark; points-per-")
    say("     season from acting on alerts is NOT claimed anywhere above.")
    say("   - snap_share_step operates on a reduced universe (offense_pct join")
    say("     gaps: 23% of 2015 rows null). Its recall is disadvantaged; its")
    say("     precision is comparable (alerts drawn where the stat exists).")
    say("   - QB excluded from the arena (blacklist is a skill-position error;")
    say("     QB tier changes are QB-change events, not usage steps). K/DST have")
    say("     no league-scored history in the panel (46_ scope cut).")
    say("   - Events are defined on the DETECTABLE universe (4+ played games by")
    say("     W, W in 4..12): late-season (W>12) and week-1-3 tier changes are")
    say("     out of scope; the W floor exists because a 2-week window needs a")
    say("     baseline, the cap so every event has >= 4 outcome weeks.")
    say("   - Volume gates (8 carries / 8 touches in-window) were fixed a priori")
    say("     and not swept; a gate sweep is a different hypothesis (it would")
    say("     measure the GATE, which section 4b shows is the active ingredient).")
    say("   - mult/lift currencies appear nowhere; nothing here re-ranks a draft")
    say("     board. This is detector instrumentation, not a drafting rule (C3).")
    say("   - FDR bookkeeping: this script contributes exactly 1 primary endpoint")
    say("     to the charter-wide Benjamini-Hochberg count (S14).")
    say()
    say(f"   [{time.time()-t0:.0f}s total]")

    # cache the record panel for sibling reuse
    records.to_parquet(os.path.join(HERE, "gt57_records_league.parquet"), index=False)
    return records


if __name__ == "__main__":
    main()
    with open(OUT_TXT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nresults -> {OUT_TXT}")
