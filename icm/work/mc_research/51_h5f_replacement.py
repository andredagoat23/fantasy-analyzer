"""51 — H5f: positional REPLACEMENT LEVEL under league scoring, end to end (charter WS5 item 1).

THE HYPOTHESIS (charter H5f, "the highest-EV item"): the league's bonus structure shifts
positional replacement level enough to change optimal positional ALLOCATION versus a room
priced on standard scoring. The 2026 board already prices this (apply_bonuses feeds
total_points before compute_metrics.py sets replacement); the RESEARCH panel and every
historical backtest before T0.3 did not. This script measures the shift and grades it.

PRIMARY ENDPOINT (S14 — declared here, before any grading run):
    Pooled arm3-minus-arm2 season-total LEAGUE points, SEASON mode (roster-construction
    question), corrected grader (49_grader_lib), multiplier 1.0x, slots (1,5,8,10,12),
    CLEAN seasons (2021,2022,2024,2025), 100 paired drafts per slot-season,
    season-clustered 95% t-CI, effective n = 4 season clusters.
    Bar: the T0.6 placebo 95th percentile if it exists at report time, else the charter's
    PROVISIONAL +25 (S15 — stated as provisional). Base PPR is the secondary currency (S12).
FALSIFICATION (charter H5f): deltas within noise => the bonus structure is a rank-preserving
    monotone transform in the draftable range — a clean null that closes section 4.1.1's
    headline claim.
C12 GUARDRAIL: QB replacement stays QB12 (utils.FIXED_STARTERS / grader REPL) — asserted at
    runtime. The treatment shifts CROSS-POSITION comparisons; it never redefines replacement.

THE TREATMENT (arm3 = arm2 + delta): a per-POSITION constant added to my VONA scores,
    tilt_s[pos] = walk-forward mean (seasons 2015..s-1) of the measured league-vs-base VOLS
    gap for the priced startable tier at pos:
        dv_i = (L_i - repl_league[pos]) - (B_i - repl_base[pos])
    averaged over the top-K players by ADP at pos (K = that season's flex-aware startable
    count under league scoring). Position-constant by design: the REPLACEMENT-LEVEL shift is
    position-constant, so the induced policy change is pure positional allocation — within-
    position order is untouched (a constant per position cancels inside a position).
    Walk-forward (prior seasons only) kills S7 leakage; T0.3 measured the tilt stable across
    all 12 seasons, so an expanding mean is the honest pre-draft-knowable estimate.

STAGES (chunked so a retry resumes; caches in 51_cache/):
    .venv/bin/python icm/work/mc_research/51_h5f_replacement.py measure
    .venv/bin/python icm/work/mc_research/51_h5f_replacement.py grade --mult 1.0
    ... (0.0 / 0.5 / 2.0 / 4.0)
    .venv/bin/python icm/work/mc_research/51_h5f_replacement.py jackknife
    .venv/bin/python icm/work/mc_research/51_h5f_replacement.py report

New file. Imports frozen code (utils.startable_counts, advisor via 49_) — modifies nothing.
"""
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from utils import startable_counts, FIXED_STARTERS  # noqa: E402  (read-only import)

CACHE_DIR = os.path.join(HERE, "51_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
OUT_TXT = os.path.join(HERE, "results_51_h5f.txt")
MEASURE_JSON = os.path.join(CACHE_DIR, "h5f_measure.json")

POSITIONS = ("QB", "RB", "WR", "TE")
CLEAN = (2021, 2022, 2024, 2025)
PANEL_YEARS = list(range(2015, 2026))
SLOTS = (1, 5, 8, 10, 12)
N_DRAFTS = 100
SEED_BASE = 5100
MULTS = (0.0, 0.5, 1.0, 2.0, 4.0)
PROVISIONAL_BAR = 25.0        # charter H5f; PROVISIONAL until T0.6 placebo exists (S15)
# S8 pins on inputs (recorded at read time 2026-07-31)
_SL_ROWS = {2014: 544, 2015: 556, 2016: 557, 2017: 553, 2018: 577, 2019: 572, 2020: 602,
            2021: 633, 2022: 608, 2023: 576, 2024: 588, 2025: 608}
# charter anchor [V in charter, recomputed here]: mean bonus_points, top-12 by total_points
ANCHOR = {"RB": 64.2, "WR": 34.9, "TE": 24.8, "QB": -8.9}

assert FIXED_STARTERS["QB"] == 12, "C12 guardrail: QB replacement must stay QB12"


def section_path(name):
    return os.path.join(CACHE_DIR, f"section_{name}.txt")


class Tee:
    def __init__(self, name):
        self.lines = []
        self.name = name

    def __call__(self, s=""):
        print(s)
        self.lines.append(str(s))

    def close(self):
        with open(section_path(self.name), "w") as f:
            f.write("\n".join(self.lines) + "\n")


def load_panel():
    sl = pd.read_parquet(os.path.join(HERE, "seasons_league.parquet"))
    per_year = sl.groupby("season").size().to_dict()
    for y, n in _SL_ROWS.items():          # S8: assert per-year rows after any load
        assert per_year.get(y) == n, f"seasons_league {y}: {per_year.get(y)} rows, pinned {n}"
    return sl


def repl_levels(df, points_col):
    """compute_metrics.py's exact rule under an arbitrary points column: flex-aware startable
    counts (utils.startable_counts, QB fixed 12 per C12), replacement = Nth-best points."""
    d = df[df[points_col].notna()].reset_index(drop=True)
    counts = startable_counts(d, points=points_col)
    repl = {}
    for pos in POSITIONS:
        pts = d[d["position"] == pos][points_col]
        repl[pos] = float(pts.nlargest(counts[pos]).min())
    return counts, repl


def season_dv(df, adp_map=None):
    """Per-player league-vs-base VOLS gap for one season + tier summaries.
    dv_i = (L_i - repl_L[pos]) - (B_i - repl_B[pos]).  Returns (counts_b, counts_l, repl_b,
    repl_l, per-pos dict of tier means)."""
    counts_b, repl_b = repl_levels(df, "total_base")
    counts_l, repl_l = repl_levels(df, "total_league")
    d = df[df["total_base"].notna() & df["total_league"].notna()].copy()
    d["dv"] = ((d["total_league"] - d["position"].map(repl_l))
               - (d["total_base"] - d["position"].map(repl_b)))
    out = {}
    for pos in POSITIONS:
        g = d[d["position"] == pos]
        top12 = g.nlargest(12, "total_league")["dv"].mean()
        tier = g.nlargest(counts_l[pos], "total_league")["dv"].mean()
        adp12 = np.nan
        adp_tier = np.nan
        if adp_map is not None:
            g2 = g.assign(adp=g["player_id"].map(adp_map)).dropna(subset=["adp"])
            if len(g2) >= 8:
                adp12 = g2.nsmallest(12, "adp")["dv"].mean()
                adp_tier = g2.nsmallest(min(counts_l[pos], len(g2)), "adp")["dv"].mean()
        out[pos] = {"top12_league": top12, "tier_league": tier,
                    "top12_adp": adp12, "tier_adp": adp_tier}
    return counts_b, counts_l, repl_b, repl_l, out, d


def cross_pos_ordering(d, repl_b, repl_l, n_draftable=192):
    """Static VONA proxy: cross-position VOLS ordering change in the draftable range.
    (At a fixed pick with identical survival inputs, VONA ordering shifts are driven by the
    VOLS shifts; the full dynamic-VONA answer is the paired grade in the grade stage.)"""
    d = d.copy()
    d["vols_b"] = d["total_base"] - d["position"].map(repl_b)
    d["vols_l"] = d["total_league"] - d["position"].map(repl_l)
    top = d.nlargest(n_draftable, "vols_b").copy()
    top["rk_b"] = top["vols_b"].rank(ascending=False)
    top["rk_l"] = top["vols_l"].rank(ascending=False)
    dr = (top["rk_l"] - top["rk_b"]).abs()
    rho = top["rk_b"].corr(top["rk_l"])   # Pearson on ranks == Spearman (no scipy in venv)
    mix = {}
    for k in (24, 48, 96):
        mix[k] = {cur: top.nlargest(k, f"vols_{cur}")["position"].value_counts().to_dict()
                  for cur in ("b", "l")}
    return {"spearman": float(rho), "mean_abs_dr": float(dr.mean()),
            "n_moved_ge12": int((dr >= 12).sum()), "max_dr": float(dr.max()), "mix": mix}


# ================================================================ stage: measure
def stage_measure():
    say = Tee("measure")
    say("=" * 100)
    say("SECTION 1 — MEASUREMENT (all numbers [V], computed this run)")
    say("=" * 100)

    # ---- 1a. anchor recompute on the 2026 board -------------------------------------------
    pf = pd.read_csv(os.path.join(ROOT, "players_final.csv"), dtype={"player_id": str})
    say("\n1a. ANCHOR — mean bonus_points of the top 12 by total_points, players_final.csv [V]:")
    anchor_now = {}
    for pos in POSITIONS:
        g = pf[(pf["position"] == pos) & pf["total_points"].notna()]
        anchor_now[pos] = g.nlargest(12, "total_points")["bonus_points"].mean()
        say(f"    {pos}: {anchor_now[pos]:+6.1f}   (charter anchor {ANCHOR[pos]:+6.1f}, "
            f"delta {anchor_now[pos] - ANCHOR[pos]:+.1f})")
    say(f"    RB-vs-WR tilt {anchor_now['RB'] - anchor_now['WR']:+.1f} "
        f"(charter +29.3); RB-vs-QB {anchor_now['RB'] - anchor_now['QB']:+.1f} (charter +73.1)")

    # ---- 1b. panel replacement levels per season, both currencies -------------------------
    sl = load_panel()
    s_adp = pd.read_parquet(os.path.join(HERE, "seasons.parquet"),
                            columns=["player_id", "season", "adp"])
    say("\n1b. REPLACEMENT LEVEL per position per season, seasons_league.parquet 2015-2025.")
    say("    Rule = compute_metrics.py's: flex-aware startable_counts (utils.py, read-only; QB")
    say("    fixed 12 per C12), replacement = Nth best. Computed under EACH currency's own")
    say("    counts, exactly as the pipeline would under that currency.")
    say("    repl_B = base-PPR replacement, repl_L = league replacement, cnt = startable count")
    hdr = f"    {'yr':>4} " + " ".join(f"| {p:>2}: cntB cntL  replB  replL   L-B" for p in POSITIONS)
    say(hdr)
    per_season = {}
    dv_rows = []
    order_rows = {}
    for yr in PANEL_YEARS:
        df = sl[sl["season"] == yr]
        adp_map = (s_adp[s_adp["season"] == yr].dropna(subset=["adp"])
                   .set_index("player_id")["adp"].to_dict())
        counts_b, counts_l, repl_b, repl_l, dv, d = season_dv(df, adp_map)
        per_season[yr] = {"counts_b": counts_b, "counts_l": counts_l,
                          "repl_b": repl_b, "repl_l": repl_l, "dv": dv,
                          "n_priced": len(adp_map)}
        row = f"    {yr:>4} "
        for p in POSITIONS:
            row += (f"| {p}: {counts_b[p]:>3} {counts_l[p]:>3} {repl_b[p]:>6.1f} "
                    f"{repl_l[p]:>6.1f} {repl_l[p] - repl_b[p]:>+6.1f}")
        say(row)
        dv_rows.append({p: dv[p] for p in POSITIONS})
        order_rows[yr] = cross_pos_ordering(d, repl_b, repl_l)

    say("\n    Pooled 2015-2025 (mean +/- season SD, n=11 season clusters — descriptive, S11):")
    for p in POSITIONS:
        rb = [per_season[y]["repl_l"][p] - per_season[y]["repl_b"][p] for y in PANEL_YEARS]
        say(f"    {p}: replacement shift (league - base) {np.mean(rb):+6.1f} +/- {np.std(rb, ddof=1):4.1f}")

    say("\n1c. VOLS DELTA per position (dv = league VOLS - base VOLS), per season:")
    say("    tier(ADP) = mean dv over the top-K priced players by ADP at the position")
    say("    (K = that season's league startable count) — the decision-relevant tilt.")
    say(f"    {'yr':>4} " + " ".join(f"| {p}: top12L tierL top12ADP tierADP" for p in POSITIONS))
    for yr, dv in zip(PANEL_YEARS, dv_rows):
        row = f"    {yr:>4} "
        for p in POSITIONS:
            v = dv[p]
            row += (f"| {p}: {v['top12_league']:+6.1f} {v['tier_league']:+5.1f} "
                    f"{_fmt(v['top12_adp'])} {_fmt(v['tier_adp'])}")
        say(row)
    say("    (2025 ADP columns are nan where <8 priced rows: seasons.parquet 2025 has 5 priced")
    say("     rows [V] — the T0.2-repaired prices live elsewhere; not needed: 2025 is never a")
    say("     PRIOR season in the walk-forward tilt below.)")
    say("\n    Pooled tier(ADP) dv, seasons with prices 2015-2024 (mean +/- season SD, n=10):")
    pooled_tier = {}
    for p in POSITIONS:
        vals = [dv[p]["tier_adp"] for dv in dv_rows if not np.isnan(dv[p]["tier_adp"])]
        pooled_tier[p] = (float(np.mean(vals)), float(np.std(vals, ddof=1)), len(vals))
        say(f"    {p}: {pooled_tier[p][0]:+6.1f} +/- {pooled_tier[p][1]:4.1f}  (n={pooled_tier[p][2]})")

    say("\n1d. CROSS-POSITION ORDERING change in the draftable range (top 192 by base VOLS),")
    say("    static VONA proxy — the dynamic answer is the paired grade (Section 3):")
    say(f"    {'yr':>4}  spearman  mean|drank|  n(|drank|>=12)  max|drank|   top-24 mix B -> L")
    for yr in PANEL_YEARS:
        o = order_rows[yr]
        m24 = o["mix"][24]
        mixs = " ".join(f"{p}:{m24['b'].get(p, 0)}->{m24['l'].get(p, 0)}" for p in POSITIONS)
        say(f"    {yr:>4}  {o['spearman']:8.4f}  {o['mean_abs_dr']:11.1f}  "
            f"{o['n_moved_ge12']:14d}  {o['max_dr']:10.0f}   {mixs}")

    # ---- 1e. 2026 board: shipped (league) vs bonus-stripped -------------------------------
    say("\n1e. 2026 BOARD (players_final.csv): shipped total_points (league, bonuses in) vs")
    say("    bonus-stripped (total_points - bonus_points). NOTE this isolates the BONUS layer")
    say("    only — per-stat custom scoring (pass TD 6, sacks in custom_proj_points) stays in")
    say("    both arms; it is the same decomposition as the charter's +64.2/-8.9 anchor.")
    pfv = pf[pf["total_points"].notna()].copy()
    pfv["strip"] = pfv["total_points"] - pfv["bonus_points"].fillna(0.0)
    counts_s, repl_s = repl_levels(pfv, "total_points")
    counts_x, repl_x = repl_levels(pfv, "strip")
    say(f"    {'pos':>4}  cnt(strip) cnt(ship)  repl(strip)  repl(ship)   shift")
    board = {}
    for p in POSITIONS:
        say(f"    {p:>4}  {counts_x[p]:>9} {counts_s[p]:>9}  {repl_x[p]:>11.1f}  "
            f"{repl_s[p]:>10.1f}  {repl_s[p] - repl_x[p]:>+6.1f}")
        board[p] = {"repl_strip": repl_x[p], "repl_ship": repl_s[p],
                    "cnt_strip": counts_x[p], "cnt_ship": counts_s[p]}
    # VONA on the board both ways, at a representative next-pick horizon
    import advisor
    pfv["vols_ship"] = pfv["total_points"] - pfv["position"].map(repl_s)
    pfv["vols_strip"] = pfv["strip"] - pfv["position"].map(repl_x)
    dvb = pfv["vols_ship"] - pfv["vols_strip"]
    say("\n    Board VOLS delta (ship - strip), mean over top-12 by total_points per pos:")
    for p in POSITIONS:
        g = pfv[pfv["position"] == p].nlargest(12, "total_points")
        say(f"    {p}: {dvb[g.index].mean():+6.1f}")
    hz = 24
    a = pfv.dropna(subset=["adp_rank"]).copy()
    v_ship = advisor.add_vona(a.assign(vols=a["vols_ship"]), hz)["vona"]
    v_strip = advisor.add_vona(a.assign(vols=a["vols_strip"]), hz)["vona"]
    a = a.assign(vona_ship=v_ship, vona_strip=v_strip)
    top = a.nsmallest(120, "adp_rank").copy()
    top["rk_ship"] = top["vona_ship"].rank(ascending=False)
    top["rk_strip"] = top["vona_strip"].rank(ascending=False)
    dr = (top["rk_ship"] - top["rk_strip"]).abs()
    say(f"\n    add_vona (advisor.py, horizon=next pick {hz}) over the top 120 by ADP, shipped")
    say(f"    vs bonus-stripped VOLS: spearman {top['rk_ship'].corr(top['rk_strip']):.4f}, "
        f"mean|drank| {dr.mean():.1f}, n(|drank|>=10) {(dr >= 10).sum()}, max {dr.max():.0f}")
    movers = top.loc[dr.sort_values(ascending=False).index[:8]]
    say("    largest VONA-rank movers (strip -> ship):")
    for _, r in movers.iterrows():
        say(f"      {r['full_name']:<24} {r['position']}  {int(r['rk_strip'])} -> {int(r['rk_ship'])}")

    # ---- 1f. C6 seam ----------------------------------------------------------------------
    say("\n" + "=" * 100)
    say("SECTION 2 — C6 SEAM: projection bias vs scoring at the REPLACEMENT TIER (measurement")
    say("only — C6 stays CLOSED; no player-level correction is applied anywhere in this script)")
    say("=" * 100)
    say("  Instruments, all at the grader's fixed tier counts REPL={QB12,RB24,WR24,TE12} on the")
    say("  SAME blend-cache pool 44_/49_ reconstruct arm 2 from (adp<=220, espn+sleeper scaled")
    say("  to realized mean, 50/50 blend — 44_'s exact prep):")
    say("    A[pos] = replacement from PROJECTIONS (what arm 2 drafts on)")
    say("    B[pos] = replacement from REALIZED base PPR (cache 'actual')")
    say("    C[pos] = replacement from REALIZED league points (seasons_league join on nn+pos)")
    say("  A-B = projection bias at the tier; B-C = scoring shift at the tier; cross-position")
    say("  differences of each = the two shares of the cross-position baseline gap.")
    from utils import normalize_name
    with open(os.path.join(HERE, "blend_cache_2019_2025.json")) as f:
        cache = {int(k): v for k, v in json.load(f).items()}
    sl["nn"] = sl["name_disp"].map(normalize_name)
    REPL_FIXED = {"QB": 12, "RB": 24, "WR": 24, "TE": 12}
    seam = {}
    say(f"\n    {'yr':>4} " + " ".join(f"| {p}:      A      B      C    A-B    B-C" for p in ("RB", "WR")))
    for yr in CLEAN:
        df = pd.DataFrame(cache[yr])
        df = df[df["adp"] <= 220].reset_index(drop=True)
        for c in ("espn", "sleeper"):
            df[c + "_s"] = df[c] * (df["actual"].mean() / df[c].mean())
        df["proj"] = 0.5 * df["espn_s"] + 0.5 * df["sleeper_s"]
        df["nn"] = df["name"].map(normalize_name)
        sly = sl[sl["season"] == yr]
        lmap = {}
        bmap = {}
        for (nn, p), grp in sly.groupby(["nn", "position"]):
            grp = grp.sort_values("total_league", ascending=False)
            lmap[(nn, p)] = float(grp["total_league"].iloc[0])
            bmap[(nn, p)] = float(grp["total_base"].iloc[0])
        df["lg"] = [lmap.get((n, p), np.nan) for n, p in zip(df["nn"], df["pos"])]
        df["bs"] = [bmap.get((n, p), np.nan) for n, p in zip(df["nn"], df["pos"])]
        ok = df.dropna(subset=["lg", "bs"])
        agree = (ok["actual"] - ok["bs"]).abs()
        seam[yr] = {}
        for p in POSITIONS:
            g = df[df["pos"] == p]
            n = REPL_FIXED[p]
            A = g["proj"].nlargest(n).min()
            B = g["actual"].nlargest(n).min()
            C = g["lg"].nlargest(n).min()
            seam[yr][p] = {"A": A, "B": B, "C": C}
        row = f"    {yr:>4} "
        for p in ("RB", "WR"):
            s = seam[yr][p]
            row += (f"| {p}: {s['A']:6.1f} {s['B']:6.1f} {s['C']:6.1f} "
                    f"{s['A'] - s['B']:+6.1f} {s['B'] - s['C']:+6.1f}")
        say(row)
        say(f"          cache-'actual' vs panel total_base agreement: median |diff| "
            f"{agree.median():.1f} pts on {len(ok)} joined rows "
            f"(join misses: {df['lg'].isna().sum()}/{len(df)})")
    say("\n    All four positions, pooled over the 4 CLEAN seasons (mean +/- season SD, n=4):")
    say(f"    {'pos':>4}   A-B (projection bias)   B-C (scoring shift)")
    for p in POSITIONS:
        ab = [seam[y][p]["A"] - seam[y][p]["B"] for y in CLEAN]
        bc = [seam[y][p]["B"] - seam[y][p]["C"] for y in CLEAN]
        say(f"    {p:>4}   {np.mean(ab):+8.1f} +/- {np.std(ab, ddof=1):4.1f}      "
            f"{np.mean(bc):+8.1f} +/- {np.std(bc, ddof=1):4.1f}")
    say("\n    RB-vs-WR VOLS BASELINE GAP decomposition (positive = RB baseline overstated")
    say("    relative to WR under arm 2's instruments):")
    tots, projs, scors = [], [], []
    for y in CLEAN:
        pb = (seam[y]["RB"]["A"] - seam[y]["RB"]["B"]) - (seam[y]["WR"]["A"] - seam[y]["WR"]["B"])
        sc = (seam[y]["RB"]["B"] - seam[y]["RB"]["C"]) - (seam[y]["WR"]["B"] - seam[y]["WR"]["C"])
        say(f"    {y}: total {pb + sc:+6.1f} = projection-bias {pb:+6.1f} + scoring {sc:+6.1f}")
        tots.append(pb + sc); projs.append(pb); scors.append(sc)
    say(f"    pooled: total {np.mean(tots):+6.1f} = projection-bias {np.mean(projs):+6.1f} "
        f"(+/- {np.std(projs, ddof=1):.1f}) + scoring {np.mean(scors):+6.1f} "
        f"(+/- {np.std(scors, ddof=1):.1f})   [n=4 seasons]")

    # ---- 1g. the walk-forward tilt table ---------------------------------------------------
    say("\n" + "=" * 100)
    say("SECTION 2b — THE TREATMENT TILT (walk-forward, leakage-free per S7)")
    say("=" * 100)
    say("  tilt_s[pos] = mean over prior seasons 2015..s-1 of tier(ADP) dv (Section 1c).")
    say("  Applied in the grader as a position-constant addition to MY VONA scores (x mult).")
    tilts = {}
    for s in CLEAN:
        tilts[s] = {}
        for p in POSITIONS:
            vals = [dv_rows[i][p]["tier_adp"] for i, y in enumerate(PANEL_YEARS)
                    if y < s and not np.isnan(dv_rows[i][p]["tier_adp"])]
            tilts[s][p] = float(np.mean(vals))
        say(f"    {s} (priors 2015-{s - 1}): " +
            "  ".join(f"{p} {tilts[s][p]:+6.1f}" for p in POSITIONS))
    say("  (A constant added to every candidate cancels in an argmax, so only the CROSS-")
    say("   position spread of these numbers acts on picks.)")

    json.dump({"tilts": {str(k): v for k, v in tilts.items()},
               "anchor_now": anchor_now, "board": board,
               "pooled_tier_dv": pooled_tier},
              open(MEASURE_JSON, "w"), indent=1)
    say(f"\n  cached -> {MEASURE_JSON}")
    say.close()


def _fmt(x):
    return f"{x:+6.1f}" if not np.isnan(x) else "   nan"


# ================================================================ stage: grade
def _load_grader():
    spec = importlib.util.spec_from_file_location("g49", os.path.join(HERE, "49_grader_lib.py"))
    g49 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g49)
    assert g49.REPL["QB"] == 12, "C12 guardrail: grader QB replacement must stay QB12"
    return g49


def _apply_tilt(pools, tilts, mult):
    for s, pool in pools.items():
        t = tilts[str(s)]
        arr = np.array([t.get(p, 0.0) for p in pool.pos]) * mult
        pool.adj_pts = arr.copy()
        pool.adj = arr.copy()          # nonzero marker so run_paired's flag/jackknife tracking works
        pool.df["_adj_pts"] = arr
        pool.df["_adj"] = arr


def stage_grade(mult, n_drafts=N_DRAFTS, zero_nn=None, tag=None):
    tag = tag or f"x{mult:g}"
    out_json = os.path.join(CACHE_DIR, f"grade_{tag}.json")
    if os.path.exists(out_json):
        print(f"grade {tag}: cache exists ({out_json}) — skipping")
        return
    tilts = json.load(open(MEASURE_JSON))["tilts"]
    say = Tee(f"grade_{tag}")
    g49 = _load_grader()
    cfg = g49.GraderConfig(name=f"h5f_{tag}", policy="composite", opponent_noise="measured",
                           scoring="season", slots=SLOTS, n_drafts=n_drafts,
                           seed_base=SEED_BASE)
    say(f"\ngrade {tag}: mult={mult} scoring=season slots={SLOTS} n_drafts={n_drafts}/slot-season"
        + (f" JACKKNIFE zero_adj_nn='{zero_nn}'" if zero_nn else ""))
    pools = g49.corrected_pools(say=say)
    _apply_tilt(pools, tilts, mult)
    res = g49.run_paired(pools, cfg, say=say, zero_adj_nn=zero_nn)
    ci, D, Db, NC = g49.report_primary(res, say=say, label=f"H5f {tag}")
    ser = {}
    for (slot, s), v in res.items():
        ser[f"{slot}|{s}"] = {"dl": v["dl"].tolist(), "db": v["db"].tolist(),
                              "nchg": v["nchg"].tolist(), "flag_picks": v["flag_picks"]}
    json.dump({"mult": mult, "tag": tag, "zero_nn": zero_nn, "n_drafts": n_drafts,
               "res": ser, "ci": {k: float(v) for k, v in ci.items()}},
              open(out_json, "w"), indent=1)
    say(f"  cached -> {out_json}")
    say.close()


def stage_jackknife():
    m1 = json.load(open(os.path.join(CACHE_DIR, "grade_x1.json")))
    agg = {}
    for v in m1["res"].values():
        for nn, k in v["flag_picks"].items():
            agg[nn] = agg.get(nn, 0) + k
    top = sorted(agg.items(), key=lambda kv: -kv[1])
    print(f"top flagged (changed-roster entries): {top[:5]}")
    nn = top[0][0]
    stage_grade(1.0, zero_nn=nn, tag="jk")


# ================================================================ stage: report
def _res_arrays(tag):
    d = json.load(open(os.path.join(CACHE_DIR, f"grade_{tag}.json")))
    res = {}
    for k, v in d["res"].items():
        slot, s = k.split("|")
        res[(int(slot), int(s))] = {"dl": np.array(v["dl"]), "db": np.array(v["db"]),
                                    "nchg": np.array(v["nchg"]), "flag_picks": v["flag_picks"]}
    return d, res


def _cluster(res):
    slots = sorted({k[0] for k in res})
    seasons = sorted({k[1] for k in res})
    per_season = {s: np.concatenate([res[(sl, s)]["dl"] for sl in slots]) for s in seasons}
    m = np.array([per_season[s].mean() for s in seasons])
    n = len(m)
    mu, sd = m.mean(), m.std(ddof=1)
    se = sd / np.sqrt(n)
    t975, t80 = (3.182, 0.978) if n == 4 else (2.776, 0.941)   # df=3 / df=4
    return {"mean": mu, "lo": mu - t975 * se, "hi": mu + t975 * se, "sd": sd, "n": n,
            "mde80": (t975 + t80) * se, "per_season": {s: per_season[s].mean() for s in seasons}}


HEADER = """H5f — POSITIONAL REPLACEMENT LEVEL UNDER LEAGUE SCORING (charter WS5, "highest-EV item")
Script: icm/work/mc_research/51_h5f_replacement.py · run 2026-07-31 · all numbers [V] unless
marked [R]. Reconstruction: `measure`, then `grade --mult {0,0.5,1,2,4}`, `jackknife`, `report`
(stages cache to 51_cache/ and resume). Inputs + pins: seasons_league.parquet (T0.3, per-year
rows asserted), seasons.parquet (ADP), players_final.csv, blend_cache_2019_2025.json +
adp_ext_sleeper_2020_2025.csv + seasons_2025repair.parquet via 49_grader_lib (population.json
asserted). 2025 prices are SLEEPER adp_ppr (T0.2 instrument repair) — stated per T0.2.
C12 GUARDRAIL: QB replacement stayed QB12 throughout — asserted at import on
utils.FIXED_STARTERS and on 49_'s REPL; the treatment never redefines replacement.

VERDICT (one line): FAIL — clean, well-powered null. The league's bonus structure shifts every
position's replacement level a lot (RB +29.5, WR +29.3, TE +16.7, QB -11.5) but shifts them
TOGETHER, so the cross-position VOLS tilt at the priced tier is ~2-5 pts and the paired grade of
the induced allocation change is +2.7 league pts [95% CI -6.2,+11.5, n=4 season clusters,
MDE ±12] — the pre-registered falsification fires and closes charter 4.1.1's headline claim at
the ALLOCATION level. Player-level scoring channels (H5a/H5b/H5c) are separate lines, untouched.
"""


def stage_report():
    out = [HEADER]
    for sec in ("measure",):
        out.append(open(section_path(sec)).read())
    m1, res1 = _res_arrays("x1")
    jk, resjk = _res_arrays("jk")
    say = Tee("grade_report")
    say("=" * 100)
    say("SECTION 3 — PAIRED GRADE (arm3 - arm2, corrected grader 49_, SEASON mode, 5 slots)")
    say("=" * 100)
    say("""
  PRIMARY ENDPOINT (declared in the module docstring BEFORE the runs; S14): pooled
  arm3-minus-arm2 LEAGUE points, season mode, mult 1.0, slots (1,5,8,10,12), CLEAN seasons
  (2021,2022,2024,2025), 100 paired drafts per slot-season = 2,000 paired drafts,
  season-clustered 95% t-CI (df=3), effective n = 4 SEASON CLUSTERS (S11).
  Arm 2 = 49_'s reconstructed composite (blend proj -> VOLS -> VONA + need gating, measured
  opponent dispersion). Arm 3 = arm 2 + walk-forward positional tilt (Section 2b).
  Both currencies from the SAME T0.3 panel; league primary, base secondary (S12).
  2025 prices are SLEEPER adp_ppr (T0.2 repair) — instrument change propagated per T0.2.""")
    slots = sorted({k[0] for k in res1})
    seasons = sorted({k[1] for k in res1})
    D = np.concatenate([res1[(sl, s)]["dl"] for sl in slots for s in seasons])
    Db = np.concatenate([res1[(sl, s)]["db"] for sl in slots for s in seasons])
    NC = np.concatenate([res1[(sl, s)]["nchg"] for sl in slots for s in seasons])
    ci = _cluster(res1)
    say("\n  MANDATORY REPORTING BLOCK (mult 1.0):")
    say(f"  1. drafts identical: {np.mean(NC == 0):.1%}  (firing rate {np.mean(NC > 0):.1%})")
    qs = np.percentile(NC, [50, 75, 90, 99])
    say(f"  2. picks changed: mean {NC.mean():.2f} · p50/p75/p90/p99 = "
        f"{qs[0]:.0f}/{qs[1]:.0f}/{qs[2]:.0f}/{qs[3]:.0f} · max {NC.max():.0f}")
    if (NC > 0).any():
        Dc = D[NC > 0]
        q = np.percentile(Dc, [5, 25, 50, 75, 95])
        say(f"  3. conditional on >=1 pick changed (n={len(Dc)}): mean {Dc.mean():+.1f} league pts,"
            f" p5/p25/p50/p75/p95 = {q[0]:+.0f}/{q[1]:+.0f}/{q[2]:+.0f}/{q[3]:+.0f}/{q[4]:+.0f}")
    agg = {}
    for v in res1.values():
        for nn, k in v["flag_picks"].items():
            agg[nn] = agg.get(nn, 0) + k
    top = sorted(agg.items(), key=lambda kv: -kv[1])
    cij = _cluster(resjk)
    moved = abs(cij["mean"] - ci["mean"])
    say(f"  4. jackknife — most-drafted-in flagged player = '{jk['zero_nn']}' "
        f"({top[0][1]} changed-roster entries); zeroing his tilt: mean {ci['mean']:+.1f} -> "
        f"{cij['mean']:+.1f} (moved {moved:.1f} pts; "
        f"{'FIRES — one-player-sensitive' if moved > abs(ci['mean']) / 2 else 'does not fire'} "
        f"per reporting rule 4). NOTE: a positional tilt flags EVERY player at the position,")
    say(f"     so 'most-flagged' here means 'most often entered a changed roster'. top5: "
        + ", ".join(f"{n} {k}" for n, k in top[:5]))
    say("  5. per-slot Δleague:  " + "  ".join(
        f"slot{sl} {np.concatenate([res1[(sl, s)]['dl'] for s in seasons]).mean():+.1f}"
        for sl in slots))
    say("  6. per-season Δleague: " + "  ".join(
        f"{s} {v:+.1f}" for s, v in ci["per_season"].items()))
    say(f"     season-clustered 95% CI [{ci['lo']:+.1f}, {ci['hi']:+.1f}] · season SD "
        f"{ci['sd']:.1f} · eff n = {ci['n']} clusters · MDE(80%) ±{ci['mde80']:.0f} league pts")
    say(f"  7. currencies — league {D.mean():+.1f} (PRIMARY) · base PPR {Db.mean():+.1f} "
        f"(secondary) · win {np.mean(D > 0):.1%} / lose {np.mean(D < 0):.1%} / tie {np.mean(D == 0):.1%}")
    say(f"     (points-tie {np.mean(D == 0):.1%} > identical-picks {np.mean(NC == 0):.1%}: some"
        f" changed picks swap players who never enter the optimal lineup, netting 0.)")
    say("\n  INSTRUMENT NOTE [V]: 49_grader_lib.report_primary builds its pooled D season-major"
        "\n  but NC/Db slot-major, so ITS printed 'when >=1 changed' conditional line (visible in"
        "\n  the per-run logs, e.g. '+0.1 pts' at 1x) is MISALIGNED garbage — self-consistency:"
        "\n  0.308 firing x its +0.1 conditional would give +0.03 pooled, not the actual +2.7."
        "\n  Every number in THIS block is recomputed with consistent slot-major ordering"
        "\n  (0.308 x +8.6 = +2.7 checks out). Pooled means/CI/win-rates are unaffected by"
        "\n  ordering. Flagged upstream; 49_ is another agent's artifact and was not edited.")
    se_cond = (D[NC > 0].std(ddof=1) / np.sqrt((NC > 0).sum())) if (NC > 0).any() else float("nan")
    say(f"\n  POWER (charter S-block): conditional-mean naive SE = {se_cond:.1f} vs bar/3 = "
        f"{PROVISIONAL_BAR / 3:.1f} — draft-count power is not binding; the binding limit is the")
    say(f"  4-season cluster CI above (naive SEs understate truth per S11 and are shown only for")
    say(f"  the power book-keeping the charter requires).")

    say("\n  SENSITIVITY SWEEP (S3) — pooled Δleague by multiplier, clustered CI:")
    say(f"    {'mult':>5}  {'mean':>7}  {'95% CI':>18}  {'seasonSD':>8}  {'identical':>9}")
    sweep, cis = {}, {}
    for mult, tag in ((0.0, "x0"), (0.5, "x0.5"), (1.0, "x1"), (2.0, "x2"), (4.0, "x4")):
        try:
            _, r = _res_arrays(tag)
        except FileNotFoundError:
            say(f"    {mult:>5}  MISSING (grade stage not run)")
            continue
        c = _cluster(r)
        nc = np.concatenate([v["nchg"] for v in r.values()])
        sweep[mult] = c["mean"]
        cis[mult] = (c["lo"], c["hi"])
        say(f"    {mult:>5}  {c['mean']:>+7.1f}  [{c['lo']:>+7.1f},{c['hi']:>+7.1f}]  "
            f"{c['sd']:>8.1f}  {np.mean(nc == 0):>8.1%}")
    shape = _shape_verdict(sweep, cis)
    say(f"    S3 shape verdict: {shape}")

    say("\n" + "=" * 100)
    say("SECTION 4 — VERDICT")
    say("=" * 100)
    bar_note = ("T0.6 placebo distribution NOT AVAILABLE at report time — 50_placebo.py was IN "
                "FLIGHT (its x1 arms done, sweep arms running, no results_50 file yet); its "
                "in-progress caches were deliberately not read (another agent's instrument, "
                "semantics unpinned). Bar = charter PROVISIONAL +25 (S15) — re-judge this row "
                "when the placebo lands; the verdict below is robust to ANY bar placement.")
    say(f"  Bar: {bar_note}")
    verdict = _verdict(ci)
    say(f"  {verdict}")
    say("""
====================================================================================================
SECTION 5 — READING, SIDE FINDINGS, AND WHAT WAS NOT DONE
====================================================================================================
  WHY THE 73-POINT TILT NETS TO ~NOTHING (the mechanism, from Section 1): the top-12 bonus
  tilt (RB +64.2 vs QB -8.9 [V, anchor reproduced exactly]) is a LEVEL story. VOLS subtracts
  each position's own replacement, and the replacement tier collects nearly the same bonus
  as the startable tier ABOVE it once players are selected by PRICE rather than by realized
  outcome: the priced-tier VOLS delta is QB +5.3 / RB +4.7 / WR +2.5 / TE +3.6 (+/- 4-7 by
  season), a <=3-pt cross-position spread. Ranking the tier by REALIZED league points instead
  inflates dv (RB top-12 +12..+35) — that is selection on outcome (boom seasons carry big
  bonuses), not an ex-ante edge. The board's own projected top-12 RB VOLS delta (+31.5, 1e)
  has the same flavor: apply_bonuses hands projected bell-cows their full projected volume
  bonus, while measured priced-tier history nets to ~+5. That gap is a MEASUREMENT
  (projection-conditional vs price-conditional), flagged for the Blueprint's C6-adjacent
  notes — NOT a proposed correction (C6 stays closed).

  C6 SEAM (Section 2): at the replacement tier the RB-vs-WR baseline gap decomposes to
  projection-bias +2.0 (+/- 15.6) + scoring +1.7 (+/- 8.3) over n=4 seasons — signs flip
  season to season; NO stable cross-position baseline distortion from either source at this
  sample. The C6 surviving seam is measured and found EMPTY at the tier. C6 stays closed.

  SIDE FINDING (not the primary endpoint): the per-season pattern at higher multipliers
  (2022 -17 vs 2025 +29 at 4x) tracks how RB-friendly the realized season was — the tilt
  helps in seasons where top-heavy RB/QB bonuses realized and hurts otherwise. At n=4
  clusters this is colour, not evidence.

  NOT DONE (stated plainly):
  * T0.6 placebo bar — not built by any agent at report time; verdict uses the provisional
    +25 and is robust to any bar (CI upper bound +11.5 < +25; MDE ±12).
  * WEEKLY-mode grade — deliberately not run: the assignment declares SEASON mode (this is a
    roster-construction/allocation question); distribution-shape channels belong to H5a/H5b.
  * A within-position rank-dependent tilt — deliberately not tested; it would mix allocation
    with within-position re-ranking and overlap H5b's per-player-rate territory.
  * 2019/2020/2023 remain outside the composite arm (backfilled/thin projections — 38_/49_),
    so the grade rests on n=4 season clusters; 2025 ADP-tier dv is not computable from
    seasons.parquet (5 priced rows) and is not needed (2025 is never a walk-forward prior).
  * BH/FDR across the charter's hypothesis family is the Blueprint's job; this file
    contributes exactly ONE primary endpoint (S14).
  * K and D/ST have no league-scored history in the panel (T0.3 scope cut) and are outside
    every number here.
""")
    say.close()
    out.append(open(section_path("grade_report")).read())
    with open(OUT_TXT, "w") as f:
        f.write("\n".join(out))
    print(f"\nwrote {OUT_TXT}")


def _shape_verdict(sweep, cis):
    if not all(m in sweep for m in MULTS):
        return "INCOMPLETE — not all multipliers run"
    v = [sweep[m] for m in MULTS]
    if abs(v[0]) > 1e-9:
        return f"BROKEN — 0.0x returned {v[0]:+.2f}, must be exactly zero"
    all_span_zero = all(cis[m][0] <= 0 <= cis[m][1] for m in MULTS[1:])
    if v[1] <= v[2] <= v[3] <= v[4] and v[4] > 0:
        shape = ("point-estimate shape: monotone rise to a PLATEAU at 2x "
                 f"({v[3]:+.1f} -> {v[4]:+.1f} from 2x to 4x)")
    else:
        peak = MULTS[int(np.argmax(v))]
        shape = f"point-estimate shape: peak at {peak}x"
    if all_span_zero:
        return (shape + ". S3's 'raise the magnitude and re-grade' was already run here (2x/4x"
                " ARE the re-grades): the mean saturates while the season SD roughly doubles per"
                " doubling, and EVERY multiplier's clustered CI spans zero — the shape never"
                " emerges from noise, so shape cannot rescue the null primary endpoint.")
    return shape


def _verdict(ci):
    mean, lo, hi, mde = ci["mean"], ci["lo"], ci["hi"], ci["mde80"]
    if lo <= 0 <= hi:
        power_note = (f"This is an INFORMATIVE null, not an under-powered one: the treatment's "
                      f"own dispersion gives MDE ±{mde:.0f} — well below the +{PROVISIONAL_BAR:.0f} "
                      f"bar — and the CI's upper bound {hi:+.1f} sits BELOW the bar, so the "
                      f"conclusion survives wherever a future placebo bar lands (any bar is > the "
                      f"upper bound or > the point estimate)."
                      if hi < PROVISIONAL_BAR else
                      f"MDE ±{mde:.0f}; CI upper bound {hi:+.1f} does not exclude the bar — "
                      f"re-judge when the placebo lands.")
        return (f"FAIL (clean null). CI [{lo:+.1f},{hi:+.1f}] spans zero at n=4 clusters -> the "
                f"positional-allocation change is WITHIN NOISE. The pre-registered falsification "
                f"FIRES: the bonus structure is rank-preserving in the draftable range at the "
                f"allocation level — each position's replacement level absorbs its own tilt "
                f"(RB +29.5 vs WR +29.3 replacement shift), leaving a cross-position VOLS tilt "
                f"of only ~2-3 points. This closes charter 4.1.1's headline claim AT THE "
                f"ALLOCATION LEVEL (player-level channels are H5a/H5b/H5c, not graded here). "
                + power_note)
    if mean >= PROVISIONAL_BAR and mde > PROVISIONAL_BAR:
        return (f"Mean {mean:+.1f} >= provisional bar +25 BUT bar < MDE ±{mde:.0f} -> "
                f"DIRECTIONAL-ONLY, not PASS (S11).")
    if mean >= PROVISIONAL_BAR:
        return f"Mean {mean:+.1f} >= provisional bar +25 and CI excludes 0 -> PASS (provisional bar)."
    return (f"CI excludes zero but mean {mean:+.1f} < provisional bar +25 -> below bar; "
            f"report as measured, do not propose for shipping.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "measure"
    if cmd == "measure":
        stage_measure()
    elif cmd == "grade":
        mult = float(sys.argv[sys.argv.index("--mult") + 1])
        tag = {0.0: "x0", 0.5: "x0.5", 1.0: "x1", 2.0: "x2", 4.0: "x4"}[mult]
        nd = int(sys.argv[sys.argv.index("--ndrafts") + 1]) if "--ndrafts" in sys.argv else N_DRAFTS
        stage_grade(mult, n_drafts=nd, tag=tag)
    elif cmd == "jackknife":
        stage_jackknife()
    elif cmd == "report":
        stage_report()
    else:
        raise SystemExit(f"unknown stage {cmd}")
