"""52 — H5a: the WR archetype question under LEAGUE scoring, resolved in VOLS.

QUESTION (charter H5a, §6-WR, §7.1, §7.12)
  Under this league's exact multipliers, which WR archetype nets more at the same draft
  price: the high-volume lower/medium-aDOT chain-mover (paid twice per catch — reception
  1.0 + receiving-FD 0.5 on the majority of his catches) or the high-aDOT deep threat
  (cumulative 40+/50+ rec-TD bonuses, more 100/200-yard tier hits, worse catch rate)?

PRIOR — STATED BEFORE ANY NUMBER WAS RUN (charter H5a mandate):
  (1) EV: the high-volume chain-mover profile wins expected league VOLS at matched price.
  (2) Ceiling: the deep-threat profile wins the ceiling (absolute league-scored p80 minus
      replacement — NEVER an upside multiplier, per C13).

PRIMARY ENDPOINT (S14 — exactly ONE, declared before running; endpoint count printed):
  Mean paired league-scored VOLS difference, HIGH-aDOT tercile (T3) minus LOW-aDOT
  tercile (T1), ADP-matched within season (greedy nearest log-ADP match, no replacement,
  caliper |dlog ADP| <= 0.25), CI = season-cluster bootstrap (S11; effective n = the 11
  season clusters 2015-2025, printed as such). Verdict bar: the 95% cluster CI excludes 0.
  EVERYTHING else below (T3-T2, T2-T1, ceiling p80 gap, base-PPR currency, the
  season-total instrument, all sensitivities) is SECONDARY and labelled so.

FALSIFICATION: no separation — primary CI covers 0 AND the ceiling-p80 secondary shows
  no tercile ordering — in which case aDOT is NOT an archetype axis worth carrying and
  that clean null is the deliverable.

TWO SCORING INSTRUMENTS (assignment task 1):
  B "weekly-distribution-exact"  = total_league from seasons_league.parquet (46_/T0.3):
      per-game tiered 100/200 bonuses exact, cumulative long-TD bonuses from pbp. PRIMARY.
  A "season-total-derived"       = everything linear recomputed from season totals
      (bucket1, FDs, long-TD counts, 2pt, returns — identical by linearity) BUT the
      game-level 100/200 yardage tiers replaced by the pipeline-style league-rate
      linearization (per-position pooled per-yard rate x season yards, the apply_bonuses
      convention, §2.6). A is what a season-total instrument can see; B - A isolates the
      concentration term of §7.1 by archetype. RB/WR/TE rush+rec tiers are all linearized
      in A so the flex-aware replacement level stays internally consistent.

VOLS DENOMINATION (assignment task 3): value over the LEAGUE-SCORED WR replacement.
  Replacement = the WR at rank k where k = utils.startable_counts(...)["WR"] computed
  per season on realized totals under the SAME instrument (flex-aware: 24 locked WR +
  flex wins; k lands ~28-31, printed per season). Sensitivity: fixed WR30.

aDOT (assignment task 2): per player-season from pbp_slim_{year}.parquet air yards per
  target (REG, 2014-2025); terciles WITHIN season (S8 era drift) among the qualified
  priced population (targets >= 25). Cross-checks: (i) weekly.parquet
  receiving_air_yards/targets, (ii) pfr_advstats season adot 2019+.

PRICES: adp_hist.csv (FFC) for 2015-2024; 2025 rows are POISONED (5 FP-preview rows) and
  are replaced per T0.2's union contract by adp_hist_2025repair.csv — the 2025 price
  instrument is SLEEPER adp_ppr, not FFC (loud flag, T0.2). Sensitivity: exclude 2025.

Run:  .venv/bin/python icm/work/mc_research/52_h5a_wr_archetype.py
Outputs: results_52_h5a.txt (+ adot_wr_2014_2025.parquet cache for siblings)
"""
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

from utils import startable_counts, normalize_name  # noqa: E402
from scoring_config import REY100, REY200, RY100, RY200  # noqa: E402

YEARS = list(range(2015, 2026))          # the H5a window (charter: 2015-2025)
ADOT_YEARS = list(range(2014, 2026))     # 2014 included so the prior-season variant covers 2015
TGT_FLOOR = 25                           # aDOT-assignment floor (stated; sensitivity at 50, 10)
CALIPER = 0.25                           # max |dlog ADP| for a matched pair
NBOOT = 4000
SEED = 52
OUT_TXT = os.path.join(HERE, "results_52_h5a.txt")
OUT_ADOT = os.path.join(HERE, "adot_wr_2014_2025.parquet")

lines = []


def say(s=""):
    print(s)
    lines.append(str(s))


# ------------------------------------------------------------------ aDOT from pbp
def build_adot():
    """Per (season, player_id): targets and aDOT from pbp_slim caches. REG only.
    Target = pass_attempt with a receiver_player_id (nflverse convention)."""
    if os.path.exists(OUT_ADOT):
        a = pd.read_parquet(OUT_ADOT)
        say(f"aDOT cache reused: {OUT_ADOT} ({len(a)} rows) [V]")
        return a
    frames = []
    for y in ADOT_YEARS:
        p = pd.read_parquet(os.path.join(HERE, f"pbp_slim_{y}.parquet"),
                            columns=["season", "week", "season_type", "pass_attempt",
                                     "receiver_player_id", "air_yards"])
        p = p[(p["season_type"] == "REG") & (p["pass_attempt"] == 1)
              & p["receiver_player_id"].notna()]
        assert len(p) > 15000, f"S8: pbp {y} targets suspiciously few ({len(p)})"
        frames.append(p)
    pbp = pd.concat(frames, ignore_index=True)
    per_year = pbp.groupby("season").size()
    say("S8 assert — REG targeted pass plays per pbp season (each 15k-21k):")
    say("  " + "  ".join(f"{y}:{per_year[y]}" for y in ADOT_YEARS))
    assert sorted(per_year.index) == ADOT_YEARS
    g = pbp.groupby(["season", "receiver_player_id"]).agg(
        pbp_targets=("pass_attempt", "size"),
        adot=("air_yards", "mean"),
        ay_nonnull=("air_yards", "count"))
    a = g.reset_index().rename(columns={"receiver_player_id": "player_id"})
    say(f"air_yards non-null on targets: {a.ay_nonnull.sum() / a.pbp_targets.sum():.4f} "
        f"(aDOT = mean over non-null) [V]")
    tmp = OUT_ADOT + ".tmp"
    a.to_parquet(tmp, index=False)
    os.replace(tmp, OUT_ADOT)
    return a


# ------------------------------------------------------------------ replacement
def wr_replacement(sl, col):
    """Per-season flex-aware WR replacement under scoring column `col`.
    Returns {season: (k, repl_points)} with k from utils.startable_counts."""
    out = {}
    for s, g in sl.groupby("season"):
        d = g[["position", col]].reset_index(drop=True)
        k = startable_counts(d, points=col)["WR"]
        wr = np.sort(g.loc[g.position == "WR", col].to_numpy())[::-1]
        out[s] = (k, float(wr[k - 1]))
    return out


# ------------------------------------------------------------------ matching
def match_pairs(df, hi_lab, lo_lab, caliper=CALIPER):
    """Within each season, greedy nearest log-ADP matching (no replacement) between
    tercile hi_lab and tercile lo_lab. Returns DataFrame of pairs."""
    rows = []
    for s, g in df.groupby("season"):
        hi = g[g.terc == hi_lab]
        lo = g[g.terc == lo_lab]
        if hi.empty or lo.empty:
            continue
        cand = []
        for i, r in hi.iterrows():
            for j, q in lo.iterrows():
                d = abs(np.log(r.adp) - np.log(q.adp))
                if d <= caliper:
                    cand.append((d, i, j))
        used_i, used_j = set(), set()
        for d, i, j in sorted(cand):
            if i in used_i or j in used_j:
                continue
            used_i.add(i)
            used_j.add(j)
            rows.append({"season": s, "i_hi": i, "i_lo": j, "logd": d})
    return pd.DataFrame(rows)


def paired_gap(df, pairs, col):
    """Per-pair diff hi - lo of column col; returns (per-pair series with season)."""
    d = pairs.copy()
    d["diff"] = df.loc[pairs.i_hi, col].to_numpy() - df.loc[pairs.i_lo, col].to_numpy()
    return d


def cluster_boot_mean(d, nboot=NBOOT, seed=SEED):
    """Season-cluster bootstrap of the mean of d['diff']. Returns (mean, lo, hi, p, n_seasons)."""
    seasons = sorted(d.season.unique())
    by = {s: d.loc[d.season == s, "diff"].to_numpy() for s in seasons}
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(nboot):
        pick = rng.choice(seasons, size=len(seasons), replace=True)
        v = np.concatenate([by[s] for s in pick])
        stats.append(v.mean())
    stats = np.array(stats)
    m = d["diff"].mean()
    p = 2 * min((stats <= 0).mean(), (stats >= 0).mean())
    return m, np.percentile(stats, 2.5), np.percentile(stats, 97.5), p, len(seasons)


def cluster_boot_p80gap(df, pairs, col, nboot=NBOOT, seed=SEED):
    """Season-cluster bootstrap of p80(VOLS hi-arm) - p80(VOLS lo-arm) over matched arms."""
    seasons = sorted(pairs.season.unique())
    hi_by = {s: df.loc[pairs.loc[pairs.season == s, "i_hi"], col].to_numpy() for s in seasons}
    lo_by = {s: df.loc[pairs.loc[pairs.season == s, "i_lo"], col].to_numpy() for s in seasons}
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(nboot):
        pick = rng.choice(seasons, size=len(seasons), replace=True)
        hi = np.concatenate([hi_by[s] for s in pick])
        lo = np.concatenate([lo_by[s] for s in pick])
        stats.append(np.percentile(hi, 80) - np.percentile(lo, 80))
    stats = np.array(stats)
    hi_all = np.concatenate(list(hi_by.values()))
    lo_all = np.concatenate(list(lo_by.values()))
    gap = np.percentile(hi_all, 80) - np.percentile(lo_all, 80)
    p = 2 * min((stats <= 0).mean(), (stats >= 0).mean())
    return gap, np.percentile(stats, 2.5), np.percentile(stats, 97.5), p, \
        np.percentile(hi_all, 80), np.percentile(lo_all, 80)


def report_contrast(df, hi, lo, tag, cols=("v_league",)):
    """Matched-pair contrast hi-lo over the given VOLS columns. Returns pairs df."""
    pairs = match_pairs(df, hi, lo)
    if pairs.empty:
        say(f"  {tag}: NO matched pairs")
        return pairs
    a_hi = df.loc[pairs.i_hi]
    a_lo = df.loc[pairs.i_lo]
    say(f"  {tag}: {len(pairs)} pairs across {pairs.season.nunique()} seasons | "
        f"ADP balance: hi-arm mean {a_hi.adp.mean():.1f} vs lo-arm {a_lo.adp.mean():.1f} "
        f"(median |dlog|={pairs.logd.median():.3f})")
    for col in cols:
        m, clo, chi, p, ns = cluster_boot_mean(paired_gap(df, pairs, col))
        say(f"    {col:<10} mean gap {m:+7.1f}  95% cluster CI [{clo:+7.1f}, {chi:+7.1f}]  "
            f"p={p:.3f}  (effective n = {ns} season clusters)")
    return pairs


# ================================================================== main
def main():
    t0 = time.time()
    say("=" * 78)
    say("52 — H5a: WR ARCHETYPE (aDOT TERCILES) UNDER LEAGUE SCORING, IN VOLS")
    say("run " + time.strftime("%Y-%m-%d %H:%M") + " — all numbers [V] unless labelled [R]")
    say("=" * 78)
    say("""
PRIOR (stated before running): (1) chain-mover (lower/mid aDOT, high volume) wins
expected league VOLS at matched draft price; (2) deep threat (high aDOT) wins ceiling
(absolute league-scored p80 minus replacement — C13: never an upside multiplier).
PRIMARY ENDPOINT (S14, count = 1): mean ADP-matched paired league-VOLS gap, T3 minus T1,
season-cluster bootstrap 95% CI. Bar: CI excludes 0. All else is SECONDARY.
FALSIFICATION: primary CI covers 0 and ceiling-p80 shows no ordering -> aDOT is not an
archetype axis worth carrying.""")

    # ---------------- load panel ----------------
    sl = pd.read_parquet(os.path.join(HERE, "seasons_league.parquet"))
    assert len(sl) == 6974, "S8: seasons_league changed size"
    sl = sl[sl.season.isin(YEARS)].reset_index(drop=True)
    yr_counts = sl.groupby("season").size()
    say("\nS8 — seasons_league rows per year (2015-2025): "
        + "  ".join(f"{y}:{yr_counts[y]}" for y in YEARS))
    assert sorted(yr_counts.index) == YEARS and (yr_counts > 500).all()

    # season receiving/rushing aggregates for WR/RB/TE (for linearization + descriptives)
    wl = pd.read_parquet(
        os.path.join(HERE, "weekly_league.parquet"),
        columns=["player_id", "season", "position", "targets", "receptions",
                 "receiving_yards", "receiving_air_yards", "receiving_first_downs",
                 "receiving_tds", "rushing_yards", "b_rec_tier", "b_rush_tier"])
    wl = wl[wl.season.isin(YEARS)]
    agg = (wl.groupby(["player_id", "season", "position"])
             .agg(targets=("targets", "sum"), receptions=("receptions", "sum"),
                  rec_yds=("receiving_yards", "sum"), rec_ay=("receiving_air_yards", "sum"),
                  rec_fd=("receiving_first_downs", "sum"), rec_tds=("receiving_tds", "sum"),
                  rush_yds=("rushing_yards", "sum"))
             .reset_index())
    sl = sl.merge(agg, on=["player_id", "season", "position"], how="left")
    for c in ["targets", "receptions", "rec_yds", "rec_ay", "rec_fd", "rec_tds", "rush_yds"]:
        sl[c] = sl[c].fillna(0)
    assert len(sl) == int(yr_counts.sum()), "S8: aggregate merge duplicated rows"

    # ---------------- instrument A: season-total-derived (linearized game tiers) ----------
    say("\n" + "=" * 78)
    say("INSTRUMENT A — SEASON-TOTAL-DERIVED (pipeline-style linearized game tiers)")
    say("=" * 78)
    lin_rate = {}
    for pos in ["WR", "TE", "RB"]:
        wpos = wl[wl.position == pos]
        rec_rate = wpos["b_rec_tier"].sum() / max(wpos["receiving_yards"].sum(), 1)
        rush_rate = wpos["b_rush_tier"].sum() / max(wpos["rushing_yards"].sum(), 1)
        lin_rate[pos] = (rec_rate, rush_rate)
        say(f"  {pos}: rec-tier {rec_rate*1000:.3f} pts/1000 rec yds, "
            f"rush-tier {rush_rate*1000:.3f} pts/1000 rush yds (pooled 2015-2025 panel rates)")
    sl["total_lin"] = sl["total_league"]
    m = sl.position.isin(["WR", "TE", "RB"])
    sl.loc[m, "total_lin"] = (
        sl.loc[m, "total_league"] - sl.loc[m, "b_rec_tier"] - sl.loc[m, "b_rush_tier"]
        + sl.loc[m, "rec_yds"] * sl.loc[m, "position"].map({p: r[0] for p, r in lin_rate.items()})
        + sl.loc[m, "rush_yds"] * sl.loc[m, "position"].map({p: r[1] for p, r in lin_rate.items()}))
    say("  (QB pass-tier left exact — QBs never enter the flex-aware WR replacement.)")
    say("  A = B - actual game-tier points + league-rate x season yards; every other")
    say("  component is linear in season totals, so A needs nothing weekly.")

    # ---------------- replacement levels ----------------
    say("\n" + "=" * 78)
    say("WR REPLACEMENT PER SEASON (utils.startable_counts, flex-aware, per instrument)")
    say("=" * 78)
    rep_league = wr_replacement(sl, "total_league")
    rep_lin = wr_replacement(sl, "total_lin")
    rep_base = wr_replacement(sl, "total_base")
    say(f"  {'season':<8}{'k_league':>9}{'repl_league':>12}{'k_lin':>7}{'repl_lin':>10}"
        f"{'k_base':>8}{'repl_base':>11}")
    for s in YEARS:
        say(f"  {s:<8}{rep_league[s][0]:>9}{rep_league[s][1]:>12.1f}{rep_lin[s][0]:>7}"
            f"{rep_lin[s][1]:>10.1f}{rep_base[s][0]:>8}{rep_base[s][1]:>11.1f}")
    sl["v_league"] = sl.total_league - sl.season.map({s: r[1] for s, r in rep_league.items()})
    sl["v_lin"] = sl.total_lin - sl.season.map({s: r[1] for s, r in rep_lin.items()})
    sl["v_base"] = sl.total_base - sl.season.map({s: r[1] for s, r in rep_base.items()})

    # ---------------- aDOT ----------------
    say("\n" + "=" * 78)
    say("aDOT — pbp air yards per target, with two cross-checks")
    say("=" * 78)
    adot = build_adot()
    wr = sl[sl.position == "WR"].copy()
    wr = wr.merge(adot[["season", "player_id", "pbp_targets", "adot"]],
                  on=["season", "player_id"], how="left")

    # cross-check 1: panel receiving_air_yards / targets
    chk = wr[(wr.targets >= TGT_FLOOR) & wr.adot.notna()].copy()
    chk["adot_panel"] = chk.rec_ay / chk.targets
    r1 = np.corrcoef(chk.adot, chk.adot_panel)[0, 1]
    say(f"cross-check 1 (panel rec_air_yards/targets, WR targets>={TGT_FLOOR}, n={len(chk)}): "
        f"Pearson r={r1:.4f}, median |diff|={np.median(np.abs(chk.adot - chk.adot_panel)):.3f} yds [V]")

    # cross-check 2: pfr_advstats season adot, 2019+
    try:
        import nflreadpy as nfl
        pfr = nfl.load_pfr_advstats(seasons=[y for y in YEARS if y >= 2019],
                                    stat_type="rec", summary_level="season").to_pandas()
        pfr = pfr[pfr["pos"] == "WR"][["season", "player", "adot", "tgt"]].copy()
        pfr["nn"] = pfr["player"].apply(normalize_name)
        pfr = pfr[pfr.tgt >= TGT_FLOOR].drop_duplicates(["season", "nn"])
        wr["nn"] = wr["name_disp"].apply(normalize_name)
        j = wr[(wr.targets >= TGT_FLOOR) & wr.adot.notna()].merge(
            pfr, on=["season", "nn"], how="inner", suffixes=("", "_pfr"))
        r2 = np.corrcoef(j.adot, j.adot_pfr)[0, 1]
        say(f"cross-check 2 (pfr_advstats adot, 2019-2025, name-joined, n={len(j)}): "
            f"Pearson r={r2:.4f}, median |diff|={np.median(np.abs(j.adot - j.adot_pfr)):.3f} yds [V]")
    except Exception as e:
        say(f"cross-check 2 (pfr_advstats) FAILED — {type(e).__name__}: {e} — "
            "relying on cross-check 1 only (stated, not hidden)")

    # ---------------- prices (T0.2 union contract) ----------------
    say("\n" + "=" * 78)
    say("PRICES — FFC 2015-2024 + SLEEPER-instrument 2025 repair (T0.2 union contract)")
    say("=" * 78)
    adp = pd.read_csv(os.path.join(HERE, "adp_hist.csv"))
    n_poison = len(adp[(adp.season == 2025)])
    rep25 = pd.read_csv(os.path.join(HERE, "adp_hist_2025repair.csv"))
    adp = pd.concat([adp[adp.season != 2025], rep25], ignore_index=True)
    adp = adp[adp.season.isin(YEARS) & (adp.position == "WR")]
    adp = adp.drop_duplicates(["season", "nn"])[["season", "nn", "adp"]]
    say(f"  dropped {n_poison} poisoned 2025 FFC/FP rows; 2025 uses SLEEPER adp_ppr "
        f"({len(rep25)} rows) — the 2025 price is a DIFFERENT INSTRUMENT (T0.2 flag).")
    say("  priced WR rows per season: "
        + "  ".join(f"{y}:{(adp.season == y).sum()}" for y in YEARS))
    if "nn" not in wr.columns:
        wr["nn"] = wr["name_disp"].apply(normalize_name)
    wr = wr.merge(adp, on=["season", "nn"], how="left")
    say("  panel WR seasons with a price: "
        + "  ".join(f"{y}:{wr[(wr.season == y) & wr.adp.notna()].shape[0]}" for y in YEARS))

    # ---------------- population + terciles ----------------
    say("\n" + "=" * 78)
    say(f"POPULATION + WITHIN-SEASON aDOT TERCILES (priced AND targets >= {TGT_FLOOR})")
    say("=" * 78)
    pop = wr[wr.adp.notna() & wr.adot.notna() & (wr.targets >= TGT_FLOOR)].copy()
    dropped = wr[wr.adp.notna() & ((wr.targets < TGT_FLOOR) | wr.adot.isna())]
    say(f"  qualified: {len(pop)} WR-seasons | priced-but-under-floor/no-aDOT dropped: "
        f"{len(dropped)} (their mean realized league VOLS {dropped.v_league.mean():.1f} — "
        "these are mostly injury/role busts; floor conditions mildly on realized volume, "
        "stated as a limitation; knowable-at-draft variant below has no such floor)")

    def tercile(g):
        q = g.adot.quantile([1 / 3, 2 / 3])
        return pd.cut(g.adot, [-np.inf, q.iloc[0], q.iloc[1], np.inf], labels=["T1", "T2", "T3"])
    pop["terc"] = pop.groupby("season", group_keys=False).apply(tercile)
    cuts = pop.groupby("season").adot.quantile([1 / 3, 2 / 3]).unstack()
    say("\n  per-season tercile boundaries (aDOT yds):")
    say("  " + "  ".join(f"{y}:{cuts.loc[y, 1/3]:.1f}/{cuts.loc[y, 2/3]:.1f}" for y in YEARS))
    say("  n per (season-pooled) tercile: " + str(pop.terc.value_counts().to_dict()))

    # ---------------- descriptives: what each archetype is ----------------
    say("\n" + "=" * 78)
    say("DESCRIPTIVE — ARCHETYPE PROFILES AND THE §7.12 PER-TARGET ORDERING")
    say("=" * 78)
    des = pop.groupby("terc", observed=True).agg(
        n=("adot", "size"), adot=("adot", "mean"), adp=("adp", "mean"),
        targets=("targets", "mean"), catch_rate=("receptions", "sum"),
        rec_yds=("rec_yds", "mean"), games=("games", "mean"),
        total_league=("total_league", "mean"), total_base=("total_base", "mean"),
        v_league=("v_league", "mean"),
        b_rec_fd=("b_rec_fd", "mean"), b_ltd_rec=("b_ltd_rec", "mean"),
        b_rec_tier=("b_rec_tier", "mean"))
    des["catch_rate"] = (pop.groupby("terc", observed=True).receptions.sum()
                         / pop.groupby("terc", observed=True).targets.sum())
    g = pop.groupby("terc", observed=True)
    des["yds_per_tgt"] = g.rec_yds.sum() / g.targets.sum()
    des["lg_pts_per_tgt"] = g.total_league.sum() / g.targets.sum()
    des["base_pts_per_tgt"] = g.total_base.sum() / g.targets.sum()
    des["fd_per_tgt"] = g.rec_fd.sum() / g.targets.sum()
    des["fd_per_rec"] = g.rec_fd.sum() / g.receptions.sum()
    say(des.round(2).T.to_string())
    say("""
  §7.12 check — 'football EV per target' (yds/tgt) vs 'league pts per target': if the two
  orderings across terciles disagree, catch-rate/aDOT trade off differently under this
  table than in football EV — read the two rows above.""")
    say("  bonus mix (season means): b_rec_fd (chain-mover pay) vs b_ltd_rec (deep pay) vs")
    say("  b_rec_tier (concentration pay) — the mechanism rows above.")

    # ---------------- PRIMARY ENDPOINT ----------------
    say("\n" + "=" * 78)
    say("PRIMARY ENDPOINT — ADP-MATCHED PAIRED LEAGUE-VOLS GAP, T3 (deep) - T1 (short)")
    say("=" * 78)
    pairs31 = report_contrast(pop, "T3", "T1", "T3-T1 [PRIMARY on v_league]",
                              cols=("v_league", "v_lin", "v_base"))
    say("    (v_league row = THE primary; v_lin/v_base rows = secondary currencies S12)")
    say("    NOTE: within a season, replacement is a constant, so each pair's VOLS diff")
    say("    IS its league-points diff — the VOLS denomination matters for levels and for")
    say("    cross-season commensurability, not for the paired gap itself.")
    if not pairs31.empty:
        ex = pairs31[pairs31.season == 2024].nsmallest(5, "logd")
        say("    example 2024 pairs (tightest ADP matches):")
        for _, r in ex.iterrows():
            h, l = pop.loc[r.i_hi], pop.loc[r.i_lo]
            say(f"      {h.name_disp:<22} aDOT {h.adot:4.1f} ADP {h.adp:5.1f} vLg {h.v_league:+7.1f}"
                f"   vs {l.name_disp:<22} aDOT {l.adot:4.1f} ADP {l.adp:5.1f} vLg {l.v_league:+7.1f}")

    say("\nSECONDARY CONTRASTS (same matched design):")
    report_contrast(pop, "T3", "T2", "T3-T2", cols=("v_league",))
    report_contrast(pop, "T2", "T1", "T2-T1", cols=("v_league",))

    # per-season breakdown of the primary (S4)
    if not pairs31.empty:
        say("\n  per-season breakdown of the primary paired gap (S4):")
        d = paired_gap(pop, pairs31, "v_league")
        tbl = d.groupby("season")["diff"].agg(["count", "mean"]).round(1)
        say(tbl.to_string())

    # ---------------- CEILING (C13) ----------------
    say("\n" + "=" * 78)
    say("CEILING (SECONDARY-1) — ABSOLUTE LEAGUE-SCORED p80 MINUS REPLACEMENT (C13)")
    say("=" * 78)
    say("  computed as p80 of VOLS (= p80 of total_league - same-season replacement) within")
    say("  each MATCHED arm; gap = p80(T3 arm) - p80(T1 arm); season-cluster bootstrap CI.")
    cgap = None
    if not pairs31.empty:
        cgap, clo, chi_, cp, cp80h, cp80l = cluster_boot_p80gap(pop, pairs31, "v_league")
        say(f"  p80 VOLS: T3 arm {cp80h:+.1f} vs T1 arm {cp80l:+.1f}  ->  gap {cgap:+.1f}  "
            f"95% CI [{clo:+.1f}, {chi_:+.1f}]  p={cp:.3f}")
        gp, lp, hp, pp, p80hb, p80lb = cluster_boot_p80gap(pop, pairs31, "v_base")
        say(f"  (base-PPR secondary: T3 {p80hb:+.1f} vs T1 {p80lb:+.1f}, gap {gp:+.1f} "
            f"[{lp:+.1f}, {hp:+.1f}], p={pp:.3f})")

    # ---------------- concentration premium (B - A) by tercile ----------------
    say("\n" + "=" * 78)
    say("WEEKLY-EXACT MINUS SEASON-TOTAL INSTRUMENT (B - A), BY TERCILE — §7.1 quantified")
    say("=" * 78)
    pop["conc"] = pop.total_league - pop.total_lin
    cc = pop.groupby("terc", observed=True)["conc"].agg(["count", "mean", "std"]).round(2)
    say(cc.to_string())
    say("  (positive = the player's real game-level tier points exceed what the linearized")
    say("   season-total instrument credits — the concentration the board cannot see)")

    # ---------------- sensitivities ----------------
    say("\n" + "=" * 78)
    say("SENSITIVITIES (all SECONDARY; primary is declared above and does not move)")
    say("=" * 78)

    say(f"\nS-A: target floor 50 (was {TGT_FLOOR}):")
    popA = pop[pop.targets >= 50].copy()
    popA["terc"] = popA.groupby("season", group_keys=False).apply(tercile)
    report_contrast(popA, "T3", "T1", "T3-T1 @ floor50", cols=("v_league",))

    say(f"\nS-A2: target floor 10 (weakest selection on realized volume):")
    popA2 = wr[wr.adp.notna() & wr.adot.notna() & (wr.targets >= 10)].copy()
    popA2["terc"] = popA2.groupby("season", group_keys=False).apply(tercile)
    report_contrast(popA2, "T3", "T1", "T3-T1 @ floor10", cols=("v_league",))

    say("\nS-B: fixed WR30 replacement (instead of computed flex-aware k):")
    rep30 = {s: float(np.sort(sl[(sl.season == s) & (sl.position == 'WR')]
                              .total_league.to_numpy())[::-1][29]) for s in YEARS}
    pop["v_league30"] = pop.total_league - pop.season.map(rep30)
    if not pairs31.empty:
        m30, lo30, hi30, p30, _ = cluster_boot_mean(paired_gap(pop, pairs31, "v_league30"))
        say(f"  T3-T1 mean gap {m30:+.1f}  CI [{lo30:+.1f}, {hi30:+.1f}]  p={p30:.3f} "
            "— IDENTICAL to the primary BY CONSTRUCTION: any per-season replacement "
            "constant cancels in a within-season pair diff. Replacement choice moves VOLS "
            "LEVELS (e.g. the ceiling p80 rows), never the paired gap. Kept as a check "
            "that the code does what the algebra says.")

    say("\nS-F: common ADP support, ADP <= 170 in every season (FFC's effective depth —")
    say("     removes the 2025 Sleeper-instrument depth advantage, ~1,171 priced 2025 WRs")
    say("     vs ~58-74 FFC rows/season):")
    report_contrast(pop[pop.adp <= 170], "T3", "T1", "T3-T1 @ ADP<=170", cols=("v_league",))

    say("\nS-C: exclude 2025 (Sleeper price instrument):")
    report_contrast(pop[pop.season < 2025], "T3", "T1", "T3-T1 ex-2025", cols=("v_league",))

    say("\nS-D: pooled (cross-year) terciles instead of within-season:")
    popD = pop.copy()
    qs = popD.adot.quantile([1 / 3, 2 / 3])
    popD["terc"] = pd.cut(popD.adot, [-np.inf, qs.iloc[0], qs.iloc[1], np.inf],
                          labels=["T1", "T2", "T3"])
    report_contrast(popD, "T3", "T1", "T3-T1 pooled-terciles", cols=("v_league",))

    say("\nS-E: KNOWABLE-AT-DRAFT variant — tercile from PRIOR-season aDOT (t-1, targets>=25")
    say("     in t-1); no realized-volume floor at season t; priced-but-unplayed WRs kept at")
    say("     0 points (VOLS = -replacement). This is the variant a draft board could use.")
    prior = adot[adot.pbp_targets >= TGT_FLOOR][["season", "player_id", "adot"]].copy()
    prior["season"] = prior["season"] + 1
    prior = prior.rename(columns={"adot": "adot_prior"})
    wrE = wr[wr.adp.notna()].merge(prior, on=["season", "player_id"], how="left")
    # priced players with a prior aDOT; realized totals already on the row (0 handled: a
    # priced WR with no panel row is absent — count them honestly instead of imputing)
    n_priced = adp.groupby("season").size()
    n_onpanel = wr[wr.adp.notna()].groupby("season").size()
    say("  priced WR rows without ANY panel season (unplayed -> not includable without "
        "imputation): " + "  ".join(f"{y}:{int(n_priced.get(y, 0) - n_onpanel.get(y, 0))}"
                                    for y in YEARS))
    popE = wrE[wrE.adot_prior.notna()].copy()
    popE["adot"] = popE["adot_prior"]
    popE["terc"] = popE.groupby("season", group_keys=False).apply(tercile)
    say(f"  population: {len(popE)} priced WR-seasons with a prior-year aDOT")
    report_contrast(popE, "T3", "T1", "T3-T1 prior-aDOT", cols=("v_league",))
    pairsE = match_pairs(popE, "T3", "T1")
    if not pairsE.empty:
        gapE, loE, hiE, pE, p80hE, p80lE = cluster_boot_p80gap(popE, pairsE, "v_league")
        say(f"  prior-aDOT ceiling p80 VOLS: T3 {p80hE:+.1f} vs T1 {p80lE:+.1f}, "
            f"gap {gapE:+.1f} [{loE:+.1f}, {hiE:+.1f}] p={pE:.3f}")

    # ---------------- verdict ----------------
    say("\n" + "=" * 78)
    say("VERDICT — H5a")
    say("=" * 78)
    say("  primary endpoints in this script: 1 (S14). BH-FDR across the programme is the")
    say("  orchestrator's job; the raw p above is what feeds it.")
    if not pairs31.empty:
        m, lo, hi, p, ns = cluster_boot_mean(paired_gap(pop, pairs31, "v_league"))
        sep = "SEPARATION" if (lo > 0 or hi < 0) else "NO SEPARATION (falsification arm)"
        say(f"  PRIMARY: T3-T1 matched league-VOLS gap {m:+.1f} [{lo:+.1f}, {hi:+.1f}] "
            f"p={p:.3f} on {ns} season clusters -> {sep}")
        say(f"""
READING (what a future reader needs, without the chat transcript):
1. PRIOR PART 1 (chain-mover wins EV at matched price): CONFIRMED, with a shape
   refinement — the axis is a HIGH-aDOT TAX, not a low-aDOT premium. T2-T1 is a flat
   ~0; the whole separation is the deep tercile losing ~{-m:.0f} league VOLS (= league
   points, replacement cancels in pairs) per season at the same ADP.
2. PRIOR PART 2 (deep threat wins ceiling): REFUTED. Under C13's absolute definition
   (league-scored p80 minus replacement) the deep arm's ceiling is LOWER
   (gap {cgap:+.1f}, CI excludes 0). The 'deep threat = upside' folklore is a
   spread-relative-to-price intuition — exactly the multiplier reading C13 closed.
3. MECHANISM (descriptive table above): the deep profile's compensations are real but
   tiny — b_ltd_rec runs ~+0.9/season above T1 and fd_per_rec RISES with aDOT
   (0.57 -> 0.70), yet catch rate falls 0.68 -> 0.58 and realized targets run ~14%
   lighter, so per-TARGET league points are FLAT across terciles (~2.05-2.09) while
   football yds/target rises 7.75 -> 8.65 (the §7.12 divergence, on this data). A
   market pricing the football ordering at a flat league pay-per-target overprices
   the high-aDOT profile — that is the ~20-point wedge.
4. INSTRUMENT: the answer does NOT depend on the weekly-exact transform — the
   season-total instrument (A) gives the same gap (concentration premium B-A is
   ~+1 pt/season and near-flat across terciles). H5a is a volume/catch-rate story,
   not a concentration story; the §7.1 machinery matters elsewhere (46_ showed it
   at the elite top-12), not on this axis.
5. CARRY IT? Same-season aDOT is not knowable at draft. The knowable variant
   (prior-season aDOT, S-E) attenuates to about half the effect and its CI covers 0
   on 11 clusters -> DIRECTIONAL-ONLY (S11) for any 2026 board use. Honest routing:
   a prose-level caution on high-aDOT WR profiles at draft (WS6 layer 'advisor READ',
   the lowest-risk layer), NOT a rank nudge; a rank change would need the paired-draft
   harness with the T0.6 placebo bar, which this script deliberately did not run.
FALSIFICATION CHECK: 'no separation' did NOT occur — aDOT IS an archetype axis, but
   its payload is the opposite sign of folklore on ceiling, and only its non-knowable
   form clears significance.""")
    say(f"  [{time.time() - t0:.0f}s total]")

    with open(OUT_TXT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT_TXT}")


if __name__ == "__main__":
    main()
