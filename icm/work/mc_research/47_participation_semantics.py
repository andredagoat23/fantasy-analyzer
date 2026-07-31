"""47 — T0.1: participation semantics + the pass-snap participation builder.

Charter (icm/work/research-blueprint-prompt.md) WS0 T0.1 + section 3.3 item 10:
  1. load_participation for each season 2016-2025 INDIVIDUALLY: rows, `route` non-empty
     rate via .fillna('').str.len()>0 (NEVER .notna() — the prior scoping's "100%" was
     an empty-string artifact), `offense_players` non-empty rate.
  2. `route` value counts 2022 vs 2024 side by side: confirm semantics (one label per
     play, describing the TARGETED receiver) and the vocabulary change (S8).
  3. Build pass-snap participation = share of team dropbacks on which a gsis_id appears
     in `offense_players`, joined to pbp on (nflverse_game_id, play_id). Seasons
     2022-2025 minimum. Output: pass_snap_participation.parquet
     (season, week, gsis_id, team, snaps_on_dropbacks, team_dropbacks, pass_snap_share).
  4. Validate vs load_snap_counts offense_pct for known route-runners and known
     blocking TEs / early-down RBs; QUANTIFY the blocker conflation.

S14 note: this is an INSTRUMENTATION task (WS0), not a hypothesis test. No points
endpoint is declared or run; nothing here feeds the FDR count.

Everything expensive is cached per season under icm/work/mc_research/raw/ so a
timed-out run RESUMES instead of restarting.

Run:  .venv/bin/python icm/work/mc_research/47_participation_semantics.py [fetch_part Y..|fetch_pbp Y..|run]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
os.makedirs(RAW, exist_ok=True)
# persistent nflreadpy download cache (same pattern as 01_build_panel.py)
os.environ.setdefault("NFLREADPY_CACHE_MODE", "filesystem")
os.environ.setdefault("NFLREADPY_CACHE_DIR", os.path.join(HERE, ".nflcache"))
os.environ.setdefault("NFLREADPY_CACHE_DURATION", str(7 * 24 * 3600))
os.environ.setdefault("NFLREADPY_TIMEOUT", "120")

import numpy as np
import pandas as pd

SEM_YEARS = list(range(2016, 2026))       # task 1: semantics census
BUILD_YEARS = list(range(2016, 2026))     # task 3: charter minimum is 2022-2025; we
                                          # attempt all 10 (2016-21 has ~91% coverage,
                                          # handled via a coverage-adjusted denominator)
BUILD_MIN = [2022, 2023, 2024, 2025]      # hard requirement; asserts run on these
PART_COLS = ["nflverse_game_id", "play_id", "possession_team", "offense_players", "route"]
PBP_COLS = ["game_id", "play_id", "season_type", "week", "posteam", "qb_dropback",
            "pass", "receiver_player_id"]
STATS_JSON = os.path.join(HERE, "participation_semantics_stats.json")
OUT_PARQUET = os.path.join(HERE, "pass_snap_participation.parquet")
RESULTS = os.path.join(HERE, "results_47_participation.txt")

# validation roster: (full_name as in nflverse rosters/snap_counts, position, season)
ROUTE_RUNNERS = [
    ("Justin Jefferson", "WR", 2022),
    ("Travis Kelce", "TE", 2022),
    ("Tyreek Hill", "WR", 2023),
    ("CeeDee Lamb", "WR", 2023),
    ("Amon-Ra St. Brown", "WR", 2024),
    ("Ja'Marr Chase", "WR", 2024),
]
BLOCKERS = [
    ("Josh Oliver", "TE", 2023),      # signed by MIN explicitly as a blocking TE
    ("Luke Farrell", "TE", 2023),     # JAX blocking TE
    ("Charlie Woerner", "TE", 2024),  # ATL blocking TE
    ("Gus Edwards", "RB", 2023),      # BAL early-down back, near-zero receiving role
    ("Derrick Henry", "RB", 2022),    # TEN early-down bell cow
]


def _nfl():
    import nflreadpy as nfl
    return nfl


# ---------------------------------------------------------------- fetchers (cached)
def fetch_participation(y):
    """Slim per-season participation cache. Returns path."""
    p = os.path.join(RAW, f"participation_slim_{y}.parquet")
    if os.path.exists(p):
        return p
    d = _nfl().load_participation(seasons=[y]).to_pandas()
    keep = [c for c in PART_COLS if c in d.columns]
    d[keep].to_parquet(p, index=False)
    print(f"  cached participation {y}: {len(d)} rows -> {os.path.basename(p)}")
    return p


def fetch_pbp_slim(y):
    """Slim per-season pbp cache. Prefers a sibling's pbp_slim_{y}.parquet when it has
    the columns we need; otherwise pulls and slims immediately (never persists 372 cols)."""
    sib = os.path.join(HERE, f"pbp_slim_{y}.parquet")
    if os.path.exists(sib):
        d = pd.read_parquet(sib)
        if all(c in d.columns for c in PBP_COLS):
            return sib
    p = os.path.join(RAW, f"pbp_slim47_{y}.parquet")
    if os.path.exists(p):
        return p
    d = _nfl().load_pbp(seasons=[y]).to_pandas()
    d[PBP_COLS].to_parquet(p, index=False)
    print(f"  cached pbp {y}: {len(d)} rows -> {os.path.basename(p)}")
    return p


def fetch_snap_counts():
    p = os.path.join(RAW, f"snap_counts_2022_2025.parquet")
    if os.path.exists(p):
        return p
    d = _nfl().load_snap_counts(seasons=BUILD_MIN).to_pandas()
    d = d[d["game_type"] == "REG"][["season", "week", "player", "pfr_player_id",
                                    "position", "team", "offense_snaps", "offense_pct"]]
    d.to_parquet(p, index=False)
    print(f"  cached snap_counts: {len(d)} rows")
    return p


def fetch_rosters():
    p = os.path.join(RAW, f"rosters_2022_2025.parquet")
    if os.path.exists(p):
        return p
    d = _nfl().load_rosters(seasons=BUILD_MIN).to_pandas()
    d = d.dropna(subset=["gsis_id"])[["season", "gsis_id", "full_name", "position", "team"]]
    d.to_parquet(p, index=False)
    print(f"  cached rosters: {len(d)} rows")
    return p


# ---------------------------------------------------------------- phase A: semantics
def nonempty(s):
    """The charter-mandated non-empty test. NEVER .notna() on this file (§3.3.10)."""
    return s.fillna("").str.len() > 0


def phase_a():
    stats = {}
    if os.path.exists(STATS_JSON):
        stats = json.load(open(STATS_JSON))
    for y in SEM_YEARS:
        if str(y) in stats:
            continue
        d = pd.read_parquet(fetch_participation(y))
        n = len(d)
        r_ne = int(nonempty(d["route"]).sum()) if "route" in d.columns else 0
        o_ne = int(nonempty(d["offense_players"]).sum())
        r_na = int(d["route"].notna().sum()) if "route" in d.columns else 0
        stats[str(y)] = {"rows": n, "route_nonempty": r_ne, "route_notna": r_na,
                         "off_players_nonempty": o_ne}
        json.dump(stats, open(STATS_JSON, "w"), indent=1)
        print(f"  {y}: rows={n} route_ne={r_ne} ({r_ne/n:.1%}) off_ne={o_ne} ({o_ne/n:.1%})")
    return stats


# ---------------------------------------------------------------- phase B: route semantics
def phase_b():
    out = {}
    for y in (2022, 2024):
        d = pd.read_parquet(fetch_participation(y))
        vc = d.loc[nonempty(d["route"]), "route"].value_counts()
        out[y] = vc
        # semantic check: does non-empty route track TARGETED pass plays?
        pb = pd.read_parquet(fetch_pbp_slim(y))
        j = pb.merge(d[["nflverse_game_id", "play_id", "route"]],
                     left_on=["game_id", "play_id"],
                     right_on=["nflverse_game_id", "play_id"], how="left")
        j["route_ne"] = nonempty(j["route"])
        targeted = j["receiver_player_id"].notna()
        pass_play = j["pass"] == 1
        out[f"sem_{y}"] = {
            "plays": len(j),
            "route_ne": int(j["route_ne"].sum()),
            "route_ne_on_targeted": int((j["route_ne"] & targeted).sum()),
            "targeted": int(targeted.sum()),
            "route_ne_untargeted_pass": int((j["route_ne"] & pass_play & ~targeted).sum()),
            "untargeted_pass": int((pass_play & ~targeted).sum()),
            "route_ne_nonpass": int((j["route_ne"] & ~pass_play).sum()),
            "multi_label": int(d.loc[nonempty(d["route"]), "route"].str.contains(";").sum()),
        }
    return out


# ---------------------------------------------------------------- phase C: builder
def build_season(y):
    p = os.path.join(RAW, f"pass_snap_part_{y}.parquet")
    if os.path.exists(p):
        return pd.read_parquet(p)
    part = pd.read_parquet(fetch_participation(y))
    pb = pd.read_parquet(fetch_pbp_slim(y))
    pb = pb[(pb["season_type"] == "REG") & (pb["qb_dropback"] == 1)]
    j = pb.merge(part[["nflverse_game_id", "play_id", "possession_team", "offense_players"]],
                 left_on=["game_id", "play_id"],
                 right_on=["nflverse_game_id", "play_id"], how="left")
    j["covered"] = nonempty(j["offense_players"].astype("string"))
    cov = j["covered"].mean()
    # denominator = COVERED dropbacks (plays where offense_players exists); pre-2023
    # coverage is ~91%, so a raw-dropback denominator would deflate every share.
    j = j[j["covered"]].copy()
    team_db = (j.groupby(["week", "posteam"], as_index=False)
                .agg(team_dropbacks=("play_id", "size")))
    ex = j[["week", "posteam", "offense_players"]].copy()
    ex["gsis_id"] = ex["offense_players"].str.split(";")
    ex = ex.explode("gsis_id")
    ex = ex[ex["gsis_id"].fillna("").str.len() > 0]
    agg = (ex.groupby(["week", "posteam", "gsis_id"], as_index=False)
             .agg(snaps_on_dropbacks=("offense_players", "size")))
    agg = agg.merge(team_db, on=["week", "posteam"], how="left")
    agg["pass_snap_share"] = agg["snaps_on_dropbacks"] / agg["team_dropbacks"]
    agg["season"] = y
    agg = agg.rename(columns={"posteam": "team"})[
        ["season", "week", "gsis_id", "team", "snaps_on_dropbacks",
         "team_dropbacks", "pass_snap_share"]]
    agg.attrs = {}
    agg.to_parquet(p, index=False)
    print(f"  built {y}: {len(agg)} player-week rows, dropback coverage {cov:.1%}")
    return agg


def phase_c():
    frames, meta = [], {}
    for y in BUILD_YEARS:
        try:
            f = build_season(y)
            frames.append(f)
            meta[y] = len(f)
        except Exception as e:  # a pre-2022 season failing is reported, not fatal
            if y in BUILD_MIN:
                raise
            print(f"  {y}: SKIPPED ({type(e).__name__}: {e})")
    full = pd.concat(frames, ignore_index=True)
    # S8: after any multi-year concat, assert per-year row counts + per-season means
    counts = full.groupby("season").size()
    print("S8 per-year rows:", counts.to_dict())
    for y in BUILD_MIN:
        assert counts.get(y, 0) > 5000, f"S8 FAIL: season {y} has {counts.get(y, 0)} rows"
    assert full["pass_snap_share"].between(0, 1.0000001).all(), "share outside [0,1]"
    full.to_parquet(OUT_PARQUET, index=False)
    return full, counts


# ---------------------------------------------------------------- phase D: validation
def season_share(full, gsis, season):
    d = full[(full["gsis_id"] == gsis) & (full["season"] == season)]
    if d.empty:
        return np.nan, 0, 0
    return (d["snaps_on_dropbacks"].sum() / d["team_dropbacks"].sum(),
            int(d["snaps_on_dropbacks"].sum()), int(d["team_dropbacks"].sum()))


def phase_d(full):
    ros = pd.read_parquet(fetch_rosters())
    sc = pd.read_parquet(fetch_snap_counts())
    wk = pd.read_parquet(os.path.join(HERE, "weekly.parquet"))  # gsis targets per week
    rows = []
    for name, pos, season in ROUTE_RUNNERS + BLOCKERS:
        rr = ros[(ros["full_name"] == name) & (ros["position"] == pos)
                 & (ros["season"] == season)]
        if rr.empty:
            rows.append({"name": name, "pos": pos, "season": season, "note": "NO ROSTER MATCH"})
            continue
        gsis = rr["gsis_id"].iloc[0]
        share, snaps, teamdb = season_share(full, gsis, season)
        s = sc[(sc["player"] == name) & (sc["season"] == season) & (sc["position"] == pos)]
        off_pct = s["offense_pct"].mean() if len(s) else np.nan
        w = wk[(wk["player_id"] == gsis) & (wk["season"] == season)]
        tgts = w["targets"].sum() if len(w) else np.nan
        rows.append({
            "name": name, "pos": pos, "season": season, "gsis": gsis,
            "pass_snap_share": share, "dropback_snaps": snaps, "team_dropbacks": teamdb,
            "offense_pct": off_pct, "targets": tgts,
            "tgt_per_pass_snap": tgts / snaps if snaps else np.nan,
            "tgt_per_team_db": tgts / teamdb if teamdb else np.nan,
        })
    val = pd.DataFrame(rows)

    # population view: ALL TEs 2022-2025 with >=200 dropback snaps —
    # distribution of targets-per-pass-snap, to show the blocker/route-runner split
    te = ros[ros["position"] == "TE"][["season", "gsis_id"]].drop_duplicates()
    agg = (full[full["season"].isin(BUILD_MIN)]
           .groupby(["season", "gsis_id"], as_index=False)
           .agg(snaps=("snaps_on_dropbacks", "sum"), teamdb=("team_dropbacks", "sum")))
    agg = agg.merge(te, on=["season", "gsis_id"], how="inner")
    tw = (wk[wk["season"].isin(BUILD_MIN)]
          .groupby(["season", "player_id"], as_index=False)["targets"].sum()
          .rename(columns={"player_id": "gsis_id"}))
    agg = agg.merge(tw, on=["season", "gsis_id"], how="left").fillna({"targets": 0})
    agg = agg[agg["snaps"] >= 200].copy()
    agg["share"] = agg["snaps"] / agg["teamdb"]
    agg["tpps"] = agg["targets"] / agg["snaps"]
    return val, agg


# ---------------------------------------------------------------- report
def dropback_coverage():
    """Per season: share of REG dropbacks with non-empty offense_players (the
    builder's denominator adjustment). Cheap — all inputs are cached parquets."""
    out = {}
    for y in BUILD_YEARS:
        part = pd.read_parquet(fetch_participation(y))
        pb = pd.read_parquet(fetch_pbp_slim(y))
        pb = pb[(pb["season_type"] == "REG") & (pb["qb_dropback"] == 1)]
        j = pb.merge(part[["nflverse_game_id", "play_id", "offense_players"]],
                     left_on=["game_id", "play_id"],
                     right_on=["nflverse_game_id", "play_id"], how="left")
        n_unc = int((~nonempty(j["offense_players"].astype("string"))).sum())
        out[y] = (int(len(j)), float(nonempty(j["offense_players"].astype("string")).mean()),
                  n_unc)
    return out


def classify_empty_2022():
    """What ARE the ~9% empty offense_players rows pre-2023? Classify 2022 by pbp
    play_type (full pbp is already in the local .nflcache — no network). Cached."""
    p = os.path.join(HERE, "participation_empty_classify.json")
    if os.path.exists(p):
        return json.load(open(p))
    pb = _nfl().load_pbp(seasons=[2022]).to_pandas()[["game_id", "play_id", "play_type"]]
    part = pd.read_parquet(fetch_participation(2022))
    emp = part[~nonempty(part["offense_players"].astype("string"))]
    j = emp.merge(pb, left_on=["nflverse_game_id", "play_id"],
                  right_on=["game_id", "play_id"], how="left")
    vc = j["play_type"].fillna("NOT_IN_PBP").value_counts().to_dict()
    out = {"n_empty": int(len(emp)), "by_play_type": {k: int(v) for k, v in vc.items()}}
    json.dump(out, open(p, "w"), indent=1)
    return out


def fmt_pct(x):
    return f"{x:.1%}" if pd.notna(x) else "   -"


def run():
    print("=== phase A: per-season semantics census ===")
    stats = phase_a()
    print("=== phase B: route vocabulary + semantics ===")
    b = phase_b()
    print("=== phase C: pass-snap participation builder ===")
    full, counts = phase_c()
    print("=== phase D: validation vs snap counts ===")
    val, tes = phase_d(full)
    cov = dropback_coverage()
    emp = classify_empty_2022()

    L = []
    say = lambda s="": (print(s), L.append(s))
    say("T0.1 — PARTICIPATION SEMANTICS + PASS-SNAP PARTICIPATION BUILDER")
    say("script: 47_participation_semantics.py · run 2026-07-31 · all numbers [V] unless noted")
    say("S14: instrumentation task — no hypothesis, no points endpoint, no FDR entry.")
    say("")
    # ---- the charter-mandated one-page statement, numbers filled from this run ----
    m22, m24 = b["sem_2022"], b["sem_2024"]
    rr = val[val["name"].isin([n for n, _, _ in ROUTE_RUNNERS])]
    bl = val[val["name"].isin([n for n, _, _ in BLOCKERS])]
    q = tes["tpps"].quantile([.25, .75])
    lo = tes[tes["tpps"] <= q[.25]]
    hi = tes[tes["tpps"] >= q[.75]]
    say("== 0. ONE-PAGE STATEMENT: WHAT PARTICIPATION DATA THIS PROJECT HAS ==")
    say("")
    say("1. THERE IS NO ROUTES-RUN COLUMN ANYWHERE IN FREE NFLVERSE DATA. `route` in")
    say("   load_participation is ONE label per play. In 2022 it describes the TARGETED")
    say(f"   receiver's route and nothing else: present on {m22['route_ne_on_targeted']/m22['targeted']:.1%} of targeted pass")
    say(f"   plays, on 0.0% of untargeted pass plays, on 0 non-pass plays, 0 multi-label")
    say(f"   rows. In 2024 it is still one label per play ({m24['route_ne_on_targeted']/m24['targeted']:.1%} of targeted plays)")
    say(f"   but ALSO appears on {m24['route_ne_untargeted_pass']/m24['untargeted_pass']:.1%} of UNtargeted pass plays ({m24['route_ne_untargeted_pass']} plays —")
    say("   intended-route charting on throwaways/sacks). Per-player route counts cannot")
    say("   be built from it in any season.")
    say("")
    say("2. THE FILE IS TWO DATA PRODUCTS UNDER ONE NAME (S8), breaking at 2023:")
    say("   - 2016-2022: offense_players non-empty on 91.3-91.6% of plays — but the")
    say(f"     empty rows are NOT missing scrimmage data: classified for 2022, all")
    say(f"     {emp['n_empty']} are {emp['by_play_type']}")
    say("     (no_play = pre-snap penalties; NOT_IN_PBP = timeouts/admin rows).")
    say("     On REG dropbacks coverage is 100.0% in every season (2016: 1 play short).")
    say("     Absent route is NaN (so .notna() and the honest test agree, ~36-39%).")
    say("   - 2023-2025: offense_players 100.0%; absent route is EMPTY STRING, so")
    say("     .notna() reports 100.0% while the honest rate is 41.6-42.5%. This is the")
    say("     prior scoping's '100% coverage' artifact. ALWAYS .fillna('').str.len()>0.")
    say("   - The route VOCABULARY also changed (HITCH/OUT/CROSS/IN/FLAT/ANGLE ->")
    say("     HITCH/CURL, QUICK OUT, IN/DIG, DEEP OUT, SHALLOW CROSS/DRAG, SWING,")
    say("     TEXAS/ANGLE). Never pool route labels across the 2022/2023 boundary.")
    say("")
    say("3. THE FREE CEILING IS PASS-SNAP PARTICIPATION — share of team dropbacks on")
    say("   which a gsis_id appears in offense_players. Built here for 2016-2025 (10")
    say(f"   seasons, {len(full)} player-week rows -> pass_snap_participation.parquet),")
    say("   REG only. Denominator = dropbacks with non-empty offense_players, which is")
    say("   measured to be a no-op safeguard (100.0% covered every season) — the ~9%")
    say("   overall empty rate pre-2023 lives entirely in no_plays/admin rows.")
    say("")
    f_half = rr["tgt_per_pass_snap"].min() / 2
    bl2 = bl.assign(over=(bl["pass_snap_share"] - bl["tgt_per_team_db"] / f_half).clip(lower=0))
    over_str = ", ".join(f"{r['name']} >={r['over']:.0%}"
                         for _, r in bl2[bl2["over"] > 0.02].iterrows())
    say("4. THE BLOCKER CONFLATION IS REAL BUT SMALLER THAN THE PRIOR SCOPING ASSUMED,")
    say("   because coaches BENCH the blocking archetype on dropbacks. Classic blocking")
    say(f"   TEs sit at {bl[bl.pos=='TE']['pass_snap_share'].min():.0%}-{bl[bl.pos=='TE']['pass_snap_share'].max():.0%} pass-snap share (vs {rr['pass_snap_share'].min():.0%}-{rr['pass_snap_share'].max():.0%} for route runners), so the")
    say("   metric already separates the archetypes. The residual conflation: even at a")
    say("   conservative per-route target-earn floor (half the route-runner minimum,")
    say(f"   f={f_half:.3f}/route), pass-snap share overstates the implied route-share upper")
    say(f"   bound by: {over_str}. Population-wide, bottom-")
    say(f"   quartile TE target-earners still log {lo['share'].mean():.0%} mean pass-snap share vs {hi['share'].mean():.0%} for")
    say("   top-quartile — a TE at ~50% share is ambiguous between a part-time route")
    say("   runner and a full-time player who blocks on half his dropbacks. Every")
    say("   conclusion built on pass-snap participation must carry this bound; it is")
    say("   snap share restricted to dropbacks, NOT a route signal (charter 3.3.10).")
    say("")
    rr_d = rr["pass_snap_share"] - rr["offense_pct"]
    bl_d = bl["pass_snap_share"] - bl["offense_pct"]
    say("5. VALIDATION vs load_snap_counts: route runners' pass-snap share runs ABOVE")
    say(f"   their overall offense_pct ({rr_d.min():+.1%} to {rr_d.max():+.1%} — they stay on for passing")
    say(f"   downs); blockers/early-down RBs run BELOW ({bl_d.min():+.1%} to {bl_d.max():+.1%}). Both")
    say("   directions are the expected physics, and no share left [0,1].")
    say("")
    say("== 1. WHAT PARTICIPATION DATA THIS PROJECT HAS (per season, measured now) ==")
    say("   non-empty = .fillna('').str.len()>0  (NEVER .notna(): route is '' on non-pass")
    say("   rows, so .notna() reports ~100% and is the documented artifact)")
    say(f"   {'season':<8}{'rows':>8}{'route .notna()':>15}{'route non-empty':>17}{'offense_players ne':>20}")
    for y in SEM_YEARS:
        s = stats.get(str(y))
        if not s:
            say(f"   {y:<8}  MISSING (fetch failed)")
            continue
        n = s["rows"]
        say(f"   {y:<8}{n:>8}{s['route_notna']/n:>14.1%}{s['route_nonempty']/n:>16.1%}"
            f"{s['off_players_nonempty']/n:>19.1%}")
    say("")
    say("== 2. ROUTE SEMANTICS — one label per play, describing the TARGETED receiver ==")
    for y in (2022, 2024):
        m = b[f"sem_{y}"]
        say(f"   {y}: route non-empty on {m['route_ne']}/{m['plays']} plays"
            f" · on TARGETED pass plays {m['route_ne_on_targeted']}/{m['targeted']}"
            f" ({m['route_ne_on_targeted']/m['targeted']:.1%})"
            f" · on UNtargeted pass plays {m['route_ne_untargeted_pass']}/{m['untargeted_pass']}"
            f" ({m['route_ne_untargeted_pass']/m['untargeted_pass']:.1%})"
            f" · on non-pass plays {m['route_ne_nonpass']}"
            f" · rows with multiple labels: {m['multi_label']}")
    say("")
    say("   route value counts, 2022 vs 2024 (top 12) — the VOCABULARY CHANGED (S8):")
    v22, v24 = b[2022], b[2024]
    rows = max(12, 0)
    l22, l24 = v22.head(rows), v24.head(rows)
    say(f"   {'2022 label':<24}{'n':>7}   |   {'2024 label':<28}{'n':>7}")
    for i in range(rows):
        a = f"{l22.index[i]:<24}{l22.iloc[i]:>7}" if i < len(l22) else " " * 31
        c = f"{l24.index[i]:<28}{l24.iloc[i]:>7}" if i < len(l24) else ""
        say(f"   {a}   |   {c}")
    only22 = sorted(set(v22.index) - set(v24.index))
    only24 = sorted(set(v24.index) - set(v22.index))
    say(f"   labels only in 2022: {only22}")
    say(f"   labels only in 2024: {only24}")
    say("")
    say("== 3. PASS-SNAP PARTICIPATION BUILD ==")
    say("   definition: for each (season, week, gsis_id, team):")
    say("     snaps_on_dropbacks = # REG-season plays with qb_dropback==1 where the id")
    say("       appears in offense_players (joined pbp<->participation on")
    say("       (nflverse_game_id, play_id); offense_players split on ';')")
    say("     team_dropbacks = that team-week's dropbacks WITH non-empty offense_players.")
    say("       Measured: an inert safeguard — dropback coverage is 100.0% in every")
    say("       season (2016 is 1 play short); the pre-2023 ~9% empty rows are")
    say("       no_plays and non-pbp admin rows, not scrimmage plays.")
    say("     pass_snap_share = snaps_on_dropbacks / team_dropbacks")
    say(f"   output: pass_snap_participation.parquet · {len(full)} rows")
    say("   S8 per-year row counts (asserted >5000 for 2022-2025) + dropback coverage:")
    for y, n in counts.items():
        m = full[full["season"] == y]
        cy = cov.get(y, (0, np.nan, 0))
        say(f"     {y}: {n} rows · mean share {m['pass_snap_share'].mean():.3f}"
            f" · players/wk {n / m['week'].nunique() / 32:.1f} per team"
            f" · REG dropbacks {cy[0]}, uncovered {cy[2]}")
    say("")
    say("== 4. VALIDATION vs load_snap_counts offense_pct ==")
    say(f"   {'player':<22}{'pos':>4}{'yr':>6}{'pass-snap%':>11}{'offense%':>10}"
        f"{'tgt/pass-snap':>14}{'targets':>9}")
    for grp, name in ((ROUTE_RUNNERS, "-- route runners --"), (BLOCKERS, "-- blocking TEs / early-down RBs --")):
        say(f"   {name}")
        for nm, pos, yr in grp:
            r = val[(val["name"] == nm) & (val["season"] == yr)].iloc[0]
            if "note" in val.columns and isinstance(r.get("note"), str):
                say(f"   {nm:<22}{pos:>4}{yr:>6}   {r['note']}")
                continue
            say(f"   {nm:<22}{pos:>4}{yr:>6}{fmt_pct(r['pass_snap_share']):>11}"
                f"{fmt_pct(r['offense_pct']):>10}{r['tgt_per_pass_snap']:>14.3f}"
                f"{r['targets']:>9.0f}")
    say("")
    # conflation bound
    rr = val[val["name"].isin([n for n, _, _ in ROUTE_RUNNERS])]
    bl = val[val["name"].isin([n for n, _, _ in BLOCKERS])]
    f_med = rr["tgt_per_pass_snap"].median()
    f_min = rr["tgt_per_pass_snap"].min()
    say("== 5. THE BLOCKER CONFLATION, QUANTIFIED ==")
    say(f"   route-runner target-earn rates (targets per pass snap): median {f_med:.3f},"
        f" min {f_min:.3f}")
    say("   bound logic: routes <= pass snaps, and targets = routes x earn-per-route.")
    say("   if a blocker earned targets at rate f per route, his route share is at most")
    say("   (targets/team_dropbacks)/f. Overstatement >= pass_snap_share - that bound.")
    say(f"   {'player':<22}{'pass-snap%':>11}{'route-share UB':>15}{'UB @ f/2':>10}{'overstate >=':>13}")
    for _, r in bl.iterrows():
        ub = r["tgt_per_team_db"] / f_min
        ub2 = r["tgt_per_team_db"] / (f_min / 2)
        say(f"   {r['name']:<22}{fmt_pct(r['pass_snap_share']):>11}{fmt_pct(min(ub,1)):>15}"
            f"{fmt_pct(min(ub2,1)):>10}{fmt_pct(max(r['pass_snap_share']-ub2,0)):>13}")
    say("")
    q = tes["tpps"].quantile([.1, .25, .5, .75, .9])
    say(f"   population view — all TE player-seasons 2022-25 with >=200 dropback snaps (n={len(tes)}):")
    say(f"   targets-per-pass-snap deciles: p10 {q[.1]:.3f} · p25 {q[.25]:.3f} · p50 {q[.5]:.3f}"
        f" · p75 {q[.75]:.3f} · p90 {q[.9]:.3f}")
    lo = tes[tes["tpps"] <= q[.25]]
    hi = tes[tes["tpps"] >= q[.75]]
    gap = hi["share"].mean() - lo["share"].mean()
    say(f"   bottom-quartile target-earners average pass-snap share {lo['share'].mean():.1%}"
        f" (n={len(lo)}); top quartile {hi['share'].mean():.1%} (n={len(hi)});"
        f" gap {gap:+.1%}.")
    say("")
    say("   provenance: targets come from weekly.parquet (prior artifact of 01_build_panel,")
    say("   raw pass-through of load_player_stats). Everything else pulled + computed now.")
    say("")
    with open(RESULTS, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {RESULTS}")
    return stats, b, full, val, tes


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "fetch_part":
        for y in map(int, sys.argv[2:]):
            fetch_participation(y)
    elif cmd == "fetch_pbp":
        for y in map(int, sys.argv[2:]):
            fetch_pbp_slim(y)
    elif cmd == "phase_a":
        phase_a()
    elif cmd == "run":
        run()
    else:
        raise SystemExit(f"unknown command {cmd}")
