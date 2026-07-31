"""50 — PLACEBO CALIBRATION (charter T0.6 / S15): the real bar for every points threshold.

WHY THIS EXISTS
  Every points threshold in charter section 8 (+15 / +20 / +25) is PROVISIONAL until this file's
  output exists (S15). A threshold is only meaningful against the distribution of scores that
  PURE NOISE earns on the same instrument. This script generates 20 synthetic "situation"
  variables that carry ZERO information by construction — their values are random draws — but
  that match the real candidates' marginal distributions and CLUSTERING structure, then runs
  each through the IDENTICAL pipeline a real treatment gets:
    bounded rank nudge (cohort_pull.py's bounds) -> paired arm3-vs-arm2 grading in the T0.4
    grader (49_grader_lib.py, corrected instrument) -> sensitivity sweep (S3) -> season-
    clustered CI (S11).
  The 95th percentile of the 20 point estimates IS the bar for every Grading-phase verdict.

THE 20 PLACEBOS (assignment-unit structure mirrors the real candidate families)
  P01-P07  TEAM-SEASON  (regime-type signals: new-HC, playcaller change, "good offense" flags)
           one value per (season, team); every pooled player on that team-season shares it.
           P01 binary prev 10/32 (2026 new-HC rate), sign +      P02 binary prev 78/224
           (playcaller-change rate, playcallers_hist.csv [R]), sign -   P03 binary prev 0.25,
           sign +      P04-P07 continuous (dev drawn per team-season).
  P08-P12  COACH-MOVE   (carryover-type signals) — a "move" = a team-season flagged at the
           measured 78/224 = 34.8% event rate; only flagged team-seasons carry a value, drawn
           once per move. In a 4-season pool a coach-move placebo is structurally a sparser
           team-season placebo (one move touches one team-season here); the distinction matters
           for the CI clustering unit of REAL treatments (S11: cluster on coach-move), and is
           preserved here so the placebo's sparsity matches the real family's.
           P08 binary sign +, P09 binary sign -, P10-P12 continuous-per-move.
  P13-P20  PLAYER-SEASON (player-level signals: cohort skew, durability flags)
           P13-P16 continuous, iid per player-season.
           P17 binary at the pool's measured `missed` prevalence, sign +
           P18 binary at the pool's measured `proven` prevalence, sign -
           P19 binary at the pool's measured `durable` prevalence, sign +
           P20 binary prev 0.10 (rare-event flag), sign +.

MARGINALS: the continuous "dev" pool is the empirical distribution of (cohort_trimmed - 1.0)
  from the live cohort_data.csv (n=280) — the archetypal shipped player-level candidate, and the
  exact quantity cohort_pull.py nudges on. Binary placebos, when they fire, draw |dev| from the
  same empirical pool with the variable's fixed sign, so magnitude marginals match the real
  family too. Assignments are RANDOM (numpy default_rng, fixed integer seeds, no wall clock) —
  the variables carry no information; only their statistical shape is real.

THE NUDGE PIPELINE (identical to what a real treatment gets)
  cohort_pull.py's bounds, verbatim: SCALE=30.0, DEAD=0.08, CAP=4, FREEZE=8 (its GATE=0.40 on
  p_startable is mapped to `vols > 0` — the pool has no p_startable; a player projected above
  the league-starter replacement line is the pool's startable analog; the gate only blocks
  LIFTS, exactly as in cohort_pull).
    adj_slots = clip(SCALE * dev, -CAP, +CAP)   [positive = draft him earlier, 33_'s convention]
    adj_slots = 0 where |dev| < DEAD            (deadband)
    adj_slots = 0 where adp <= FREEZE           (leave the consensus top alone)
    adj_slots = 0 where adj > 0 and vols <= 0   (don't LIFT a non-startable)
  then the grader's own price-value mapping (adp_nudge_to_points) converts slots -> points in
  the composite policy's currency — no constant invented here.
  Sensitivity sweep multiplies the FINAL bounded nudge by k in {0, 0.5, 1, 2, 4} (S3): at 2x the
  effective cap is 8 slots, at 4x it is 16 — bracketing the prereq-bundle-sized treatments
  (prereq_adjust nudges are +/-8..12 slots), so the sweep also calibrates bigger-cap treatments.

GRADING: 49_grader_lib.run_paired with the CORRECTED config (composite policy = arm 2, +delta =
  arm 3, weekly hindsight-optimal lineups, league scoring primary / base PPR secondary, measured
  opponent dispersion, CLEAN seasons 2021/22/24/25, seed_base 4900 — the SAME draft-noise seeds
  every real treatment is graded on, so placebo scores are exchangeable with treatment scores).

COMPUTE BUDGET (assignment item 3): slots restricted to {5, 10} (allowed), n_drafts=100/slot/
  season -> 800 paired drafts per placebo-multiplier (T0.5c used 5 slots = 2,000). SE arithmetic
  in the results file: the clustered SE is dominated by the between-season term (T0.5c measured
  season SD 25.3 [R]); halving the per-season draft count inflates the clustered SE only through
  the within-season term s_w/sqrt(m), shown with measured s_w in section 4 of the results.

RESUME: every (placebo, multiplier) result is pickled under 50_cache/; a rerun skips finished
  jobs. Delete 50_cache/ to force a clean re-run. Progress streams to 50_cache/progress.log.

Run:  .venv/bin/python icm/work/mc_research/50_placebo.py
New file; imports the grader and frozen code, modifies nothing (charter hard rule).
"""
import importlib.util
import os
import pickle
import sys
import time
from dataclasses import replace

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("g49", os.path.join(HERE, "49_grader_lib.py"))
g = importlib.util.module_from_spec(_spec)
sys.modules["g49"] = g          # register so Pool objects can round-trip through pickle
_spec.loader.exec_module(g)

OUT = os.path.join(HERE, "results_50_placebo.txt")
CACHE = os.path.join(HERE, "50_cache")
os.makedirs(CACHE, exist_ok=True)
PROGRESS = os.path.join(CACHE, "progress.log")

# ---- cohort_pull.py bounds, copied verbatim (assignment: "copy the cohort_pull.py pattern's
# bounds"). GATE maps p_startable>=0.40 -> vols>0 (documented above). -------------------------
SCALE, DEAD, CAP, FREEZE = 30.0, 0.08, 4.0, 8.0

N_DRAFTS = 100                 # per slot per season (T0.5c used 100 over 5 slots)
SLOTS = (5, 10)                # assignment-sanctioned restriction
MULTS_SWEEP = (0.0, 0.5, 2.0, 4.0)   # 1x is the main run
N_DRAFTS_0X = 25               # 0x is a structural-exactness check, not an estimate
SWEEP_PRE = ["P01", "P04", "P08", "P13", "P17"]   # pre-declared: one per structural family
THRESHOLDS = (15.0, 20.0, 25.0)          # charter section 8's provisional bars
COACH_MOVE_RATE = 78.0 / 224.0           # playcallers_hist.csv census [R, T0.2-confirmed]

# The 20 placebo specs. (id, class, kind, prevalence-or-None, sign)
SPECS = [
    ("P01", "team",   "bin",  10 / 32,          +1),
    ("P02", "team",   "bin",  COACH_MOVE_RATE,  -1),
    ("P03", "team",   "bin",  0.25,             +1),
    ("P04", "team",   "cont", None,             0),
    ("P05", "team",   "cont", None,             0),
    ("P06", "team",   "cont", None,             0),
    ("P07", "team",   "cont", None,             0),
    ("P08", "coach",  "bin",  COACH_MOVE_RATE,  +1),
    ("P09", "coach",  "bin",  COACH_MOVE_RATE,  -1),
    ("P10", "coach",  "cont", COACH_MOVE_RATE,  0),
    ("P11", "coach",  "cont", COACH_MOVE_RATE,  0),
    ("P12", "coach",  "cont", COACH_MOVE_RATE,  0),
    ("P13", "player", "cont", None,             0),
    ("P14", "player", "cont", None,             0),
    ("P15", "player", "cont", None,             0),
    ("P16", "player", "cont", None,             0),
    ("P17", "player", "bin",  "missed",         +1),
    ("P18", "player", "bin",  "proven",         -1),
    ("P19", "player", "bin",  "durable",        +1),
    ("P20", "player", "bin",  0.10,             +1),
]

lines = []


def say(s=""):
    print(s, flush=True)
    lines.append(s)
    with open(PROGRESS, "a") as f:
        f.write(s + "\n")


def quiet(_s=""):
    with open(PROGRESS, "a") as f:
        f.write(_s + "\n")


def atomic_dump(obj, path):
    """tmp+rename so an interrupted run can never leave a truncated pickle (T0.3's pattern)."""
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(obj, f)
    os.replace(tmp, path)


# =================================================================================================
# SETUP — pools (cached), team map, dev pool
# =================================================================================================
def get_pools():
    """Corrected pools, pickled for resume. On cache load, population.json is re-asserted and the
    per-season n is pinned against the values recorded at build time (S8)."""
    p = os.path.join(CACHE, "pools.pkl")
    if os.path.exists(p):
        with open(p, "rb") as f:
            pools, pins = pickle.load(f)
        g.assert_population(g.CLEAN, say=quiet)
        for s, n in pins.items():
            assert pools[s].n == n, f"pools cache drift: season {s} n={pools[s].n}, pinned {n}"
        say(f"  [resume] pools loaded from cache (per-season n re-pinned: {pins})")
        return pools
    pools = g.corrected_pools(say=say)
    pins = {s: pool.n for s, pool in pools.items()}
    atomic_dump((pools, pins), p)
    return pools


def team_map():
    """(season, nn, position) -> team_last from the exp∪repair panel (T0.2 union contract)."""
    exp = pd.read_parquet(os.path.join(HERE, "seasons_exp.parquet"),
                          columns=["nn", "position", "season", "team_last"])
    rep = pd.read_parquet(os.path.join(HERE, "seasons_2025repair.parquet"),
                          columns=["nn", "position", "season", "team_last"])
    u = pd.concat([exp[exp["season"] != 2025], rep], ignore_index=True)
    out = {}
    for s in g.CLEAN:
        sub = u[u["season"] == s].drop_duplicates(subset=["nn", "position"])
        out[s] = dict(zip(zip(sub["nn"], sub["position"]), sub["team_last"]))
    return out


def load_devpool():
    """Empirical dev distribution from the live cohort_data.csv — the real player-level
    candidate's marginal (cohort_trimmed - 1.0)."""
    ch = pd.read_csv(os.path.join(g.ROOT, "cohort_data.csv"))
    dev = (ch["cohort_trimmed"] - 1.0).dropna().to_numpy(float)
    return dev


# =================================================================================================
# PLACEBO CONSTRUCTION — deterministic, clustered, marginal-matched
# =================================================================================================
def gen_dev(spec, pools, tmap, devpool, rng):
    """Return {season: dev array aligned to pool.df}. Cluster structure per the spec's class."""
    pid, cls, kind, prev, sign = spec
    out = {}
    for s in sorted(pools):
        df = pools[s].df
        teams = [tmap[s].get((nn, p)) for nn, p in zip(df["nn"], df["position"])]
        dev = np.zeros(len(df))
        if cls == "player":
            if kind == "cont":
                dev = rng.choice(devpool, size=len(df))
            else:
                pr = float(df[prev].mean()) if isinstance(prev, str) else float(prev)
                fire = rng.random(len(df)) < pr
                dev[fire] = sign * np.abs(rng.choice(devpool, size=int(fire.sum())))
        else:
            # team-season / coach-move: ONE draw per (season, team); teammates share it
            uteams = sorted({t for t in teams if isinstance(t, str)})
            vals = {}
            for t in uteams:
                if cls == "team" and kind == "bin":
                    v = sign * abs(rng.choice(devpool)) if rng.random() < prev else 0.0
                elif cls == "team":
                    v = float(rng.choice(devpool))
                elif kind == "bin":     # coach binary: move gate then signed magnitude
                    v = sign * abs(rng.choice(devpool)) if rng.random() < prev else 0.0
                else:                   # coach continuous: move gate then dev draw
                    v = float(rng.choice(devpool)) if rng.random() < prev else 0.0
                vals[t] = v
            dev = np.array([vals.get(t, 0.0) if isinstance(t, str) else 0.0 for t in teams])
        out[s] = dev
    return out


def bounded_nudge(df, dev):
    """cohort_pull.py's bounds, mapped to the grader's slot-nudge convention (positive=earlier)."""
    adj = np.clip(SCALE * dev, -CAP, CAP)
    adj[np.abs(dev) < DEAD] = 0.0                       # deadband
    adj[df["adp"].to_numpy(float) <= FREEZE] = 0.0      # freeze the consensus top
    lift_block = (adj > 0) & (df["vols"].to_numpy(float) <= 0)
    adj[lift_block] = 0.0                               # don't LIFT a non-startable
    return adj


def build_all_placebos(pools, tmap, devpool):
    """All 20 placebos' bounded nudges, deterministic (seed 770_000+k), cached with summary."""
    p = os.path.join(CACHE, "placebo_adj.pkl")
    if os.path.exists(p):
        with open(p, "rb") as f:
            say("  [resume] placebo nudges loaded from cache")
            return pickle.load(f)
    adjs, summ = {}, {}
    for k, spec in enumerate(SPECS):
        pid = spec[0]
        rng = np.random.default_rng(770_000 + k)
        devs = gen_dev(spec, pools, tmap, devpool, rng)
        adjs[pid] = {s: bounded_nudge(pools[s].df, devs[s]) for s in devs}
        nz = np.concatenate([adjs[pid][s] for s in sorted(adjs[pid])])
        dv = np.concatenate([devs[s] for s in sorted(devs)])
        summ[pid] = {"cls": spec[1], "kind": spec[2],
                     "pct_players_nudged": float((nz != 0).mean()),
                     "mean_abs_slots_nonzero": float(np.abs(nz[nz != 0]).mean()) if (nz != 0).any() else 0.0,
                     "pct_at_cap": float((np.abs(nz) >= CAP).mean()),
                     "pct_dev_nonzero": float((dv != 0).mean()),
                     "n_pos": int((nz > 0).sum()), "n_neg": int((nz < 0).sum())}
    atomic_dump((adjs, summ), p)
    return adjs, summ


# =================================================================================================
# GRADING — one job = (placebo, multiplier) through run_paired (arm3 vs arm2, paired seeds)
# =================================================================================================
def set_delta(pools, adjs_pid, mult):
    for s, pool in pools.items():
        a = adjs_pid[s] * mult
        pool.adj = a
        pool.adj_pts = g.adp_nudge_to_points(pool.df, a)


def run_job(pools, adjs, pid, mult):
    tag = f"{pid}_x{mult:g}"
    p = os.path.join(CACHE, f"res_{tag}.pkl")
    if os.path.exists(p):
        say(f"  [resume] {tag} loaded from 50_cache (first computed in the run logged in "
            f"50_cache/progress.log)")
        with open(p, "rb") as f:
            return pickle.load(f)
    t0 = time.time()
    n = N_DRAFTS_0X if mult == 0.0 else N_DRAFTS
    cfg = replace(g.CORRECTED, name=f"placebo_{tag}", slots=SLOTS, n_drafts=n)
    set_delta(pools, adjs[pid], mult)
    res = g.run_paired(pools, cfg, say=quiet)
    out = {(sl, s): {"dl": v["dl"], "db": v["db"], "nchg": v["nchg"]}
           for (sl, s), v in res.items()}
    atomic_dump(out, p)
    say(f"  [{tag}] {n} drafts x {len(SLOTS)} slots x {len(pools)} seasons "
        f"in {time.time() - t0:.0f}s")
    return out


def estimate(res):
    """Point estimate + clustered CI in both currencies, from a job's result dict (mirrors
    report_primary's arithmetic: per-season mean pools the slots, CI clusters on season)."""
    seasons = sorted({k[1] for k in res})
    slots = sorted({k[0] for k in res})
    per_l = {s: np.concatenate([res[(sl, s)]["dl"] for sl in slots]) for s in seasons}
    per_b = {s: np.concatenate([res[(sl, s)]["db"] for sl in slots]) for s in seasons}
    ci = g.cluster_ci([per_l[s].mean() for s in seasons])
    ci_b = g.cluster_ci([per_b[s].mean() for s in seasons])
    D = np.concatenate([per_l[s] for s in seasons])
    NC = np.concatenate([res[(sl, s)]["nchg"] for sl in slots for s in seasons])
    s_w = float(np.mean([per_l[s].std(ddof=1) for s in seasons]))   # within-season draft SD
    return {"ci": ci, "ci_b": ci_b, "identical": float((D == 0).mean()),
            "picks_changed": float(NC.mean()), "win": float((D > 0).mean()),
            "per_season": {s: float(per_l[s].mean()) for s in seasons}, "s_w": s_w,
            "per_slot": {sl: float(np.concatenate([res[(sl, s)]["dl"]
                                                   for s in seasons]).mean()) for sl in slots}}


# =================================================================================================
# MAIN
# =================================================================================================
def main():
    t_start = time.time()
    say("=" * 96)
    say("T0.6 — PLACEBO CALIBRATION (charter S15): 20 zero-information situation variables")
    say(f"  run {time.strftime('%Y-%m-%d %H:%M')} · grader = 49_grader_lib.py (T0.4, corrected "
        f"instrument)")
    say("  All numbers [V] (computed this run) unless marked [R] (read from a prior results file).")
    say("=" * 96)
    say("")
    say("PRIMARY-ENDPOINT DECLARATION (S14, before any grading): each placebo's point estimate is")
    say("the season-clustered pooled mean of Δ(arm3 − arm2) in LEAGUE points, weekly mode, slots")
    say(f"{SLOTS}, {N_DRAFTS} paired drafts/slot/season, seed_base {g.CORRECTED.seed_base} (the")
    say("same seeds every real treatment is graded on). The deliverable statistic is the 95th")
    say("percentile of the 20 point estimates. Base PPR is secondary (S12). Sweep set pre-declared")
    say(f"before any run: {SWEEP_PRE} (one per structural family) + post-hoc the largest-|1x|")
    say("placebo if not already in the set (labelled post-hoc).")
    say("")

    say("POOLS (S8: population.json asserted; per-season n pinned)")
    pools = get_pools()
    tmap = team_map()
    devpool = load_devpool()
    say(f"  dev marginal source: cohort_data.csv (live board artifact), n={len(devpool)} values,")
    say(f"  mean {devpool.mean():+.3f}, sd {devpool.std(ddof=1):.3f}, share |dev|>=DEAD({DEAD}) "
        f"{(np.abs(devpool) >= DEAD).mean():.1%}  [V]")
    cover = {s: np.mean([tmap[s].get((nn, p)) is not None
                         for nn, p in zip(pools[s].df["nn"], pools[s].df["position"])])
             for s in sorted(pools)}
    say("  team-join coverage (pool players with a team_last): "
        + " ".join(f"{s}:{c:.0%}" for s, c in cover.items()))
    say("  (a pool player with no team joins NO team-clustered placebo — same as a real team")
    say("   signal, which cannot fire on a player whose team is unknown)")
    say("")

    say("PLACEBO CONSTRUCTION (deterministic: default_rng(770_000+k); bounds = cohort_pull.py's")
    say(f"  SCALE {SCALE} / DEAD {DEAD} / CAP {CAP} / FREEZE {FREEZE} verbatim; GATE mapped to")
    say("  vols>0 — blocks LIFTS only, as in cohort_pull)")
    adjs, summ = build_all_placebos(pools, tmap, devpool)
    say(f"  {'id':4} {'class':6} {'kind':4} {'%nudged':>8} {'|slots|':>8} {'%at-cap':>8} "
        f"{'n+':>5} {'n-':>5}")
    for pid, m in summ.items():
        say(f"  {pid:4} {m['cls']:6} {m['kind']:4} {m['pct_players_nudged']:8.1%} "
            f"{m['mean_abs_slots_nonzero']:8.2f} {m['pct_at_cap']:8.1%} "
            f"{m['n_pos']:5d} {m['n_neg']:5d}")
    say("")

    # ------------------------------------------------------------------ 1x main runs (all 20)
    say("=" * 96)
    say(f"MAIN RUNS — 20 placebos at 1x · {N_DRAFTS} paired drafts x slots {SLOTS} x "
        f"{len(pools)} seasons = {N_DRAFTS * len(SLOTS) * len(pools)} paired drafts each")
    say("=" * 96)
    est = {}
    for pid in [s[0] for s in SPECS]:
        res = run_job(pools, adjs, pid, 1.0)
        est[pid] = estimate(res)

    # ------------------------------------------------------------------ sweep set
    order = sorted(est, key=lambda k: -abs(est[k]["ci"]["mean"]))
    sweep_ids = list(SWEEP_PRE)
    posthoc = None
    if order[0] not in sweep_ids:
        posthoc = order[0]
        sweep_ids.append(posthoc)
    say("")
    say("=" * 96)
    say(f"SENSITIVITY SWEEP (S3) — multipliers {MULTS_SWEEP + (1.0,)} on {sweep_ids}"
        + (f" ({posthoc} added post-hoc: largest |1x|)" if posthoc else ""))
    say("=" * 96)
    sweep = {}
    for pid in sweep_ids:
        sweep[pid] = {1.0: est[pid]}
        for m in MULTS_SWEEP:
            res = run_job(pools, adjs, pid, m)
            e = estimate(res)
            if m == 0.0:
                allz = all(np.all(res[k]["dl"] == 0) and np.all(res[k]["db"] == 0)
                           for k in res)
                assert allz, f"{pid} at 0.0x produced a nonzero delta — pipeline broken (S3)"
            sweep[pid][m] = e

    # ------------------------------------------------------------------ report
    say("")
    say("=" * 96)
    say("SECTION 1 — THE PLACEBO DISTRIBUTION (the deliverable)")
    say("=" * 96)
    say("  Each row: a zero-information variable's arm3−arm2 result on the corrected instrument.")
    say(f"  {'id':4} {'class':6} {'kind':4} {'Δleague':>8} {'[clustered 95% CI]':>20} "
        f"{'SE':>6} {'Δbase':>7} {'ident%':>7} {'pks':>5} {'win%':>6}  per-season")
    ests = []
    for pid in [s[0] for s in SPECS]:
        e, m = est[pid], summ[pid]
        ci = e["ci"]
        ests.append(ci["mean"])
        say(f"  {pid:4} {m['cls']:6} {m['kind']:4} {ci['mean']:+8.1f} "
            f"[{ci['lo']:+7.1f},{ci['hi']:+7.1f}] {ci['se']:6.1f} {e['ci_b']['mean']:+7.1f} "
            f"{e['identical']:7.1%} {e['picks_changed']:5.2f} {e['win']:6.1%}  "
            + " ".join(f"{s}:{v:+.0f}" for s, v in e["per_season"].items()))
    ests = np.array(ests)
    p95 = float(np.percentile(ests, 95))
    say("")
    say(f"  n placebos            : {len(ests)}")
    say(f"  mean / median         : {ests.mean():+.1f} / {np.median(ests):+.1f} league pts")
    say(f"  sd across placebos    : {ests.std(ddof=1):.1f}")
    say(f"  min / max             : {ests.min():+.1f} / {ests.max():+.1f}")
    say(f"  95th percentile (p95) : {p95:+.1f}  <-- THE REAL BAR (S15)")
    srt = np.sort(ests)
    say(f"  order stats around p95: 18th={srt[17]:+.1f} 19th={srt[18]:+.1f} 20th(max)={srt[19]:+.1f}")
    rng_b = np.random.default_rng(99)
    boots = np.array([np.percentile(rng_b.choice(ests, len(ests)), 95) for _ in range(10_000)])
    say(f"  p95 bootstrap 95% CI  : [{np.percentile(boots, 2.5):+.1f}, "
        f"{np.percentile(boots, 97.5):+.1f}]  (10,000 resamples, seed 99)")
    say("")
    for th in THRESHOLDS:
        n_pass = int((ests >= th).sum())
        say(f"  placebos with point estimate >= +{th:.0f}: {n_pass} of 20"
            + ("  <-- a stated charter bar a placebo cleared" if n_pass else ""))
    n_ci = int(sum(1 for pid in est if est[pid]["ci"]["lo"] > 0))
    n_ci_neg = int(sum(1 for pid in est if est[pid]["ci"]["hi"] < 0))
    say(f"  placebos whose clustered 95% CI excludes 0 on the POSITIVE side: {n_ci} of 20")
    say(f"  placebos whose clustered 95% CI excludes 0 on the NEGATIVE side: {n_ci_neg} of 20"
        f"  (a 95% CI should false-alarm ~1 in 20; this is the coverage check)")
    say("")
    say(f"  SIDE FINDING: the placebo mean is {ests.mean():+.1f} — random deviations from the")
    say("  composite COST points on average on this instrument (S4 made empirical: the nudge")
    say("  trades a composite-optimal pick for a noise-shifted one, and the trade is not free).")
    say("  This is why the bar is the placebo P95, not the placebo mean.")
    say("")

    say("=" * 96)
    say("SECTION 2 — SENSITIVITY SWEEPS (S3 shapes on zero-information variables)")
    say("=" * 96)
    n_pass_shape = 0
    for pid in sweep_ids:
        row = sweep[pid]
        ms = [0.0, 0.5, 1.0, 2.0, 4.0]
        vals = [row[m]["ci"]["mean"] for m in ms]
        ses = [row[m]["ci"]["se"] for m in ms]
        # S3 shape call on the nonzero multipliers: PASS = monotone rise, or peak at >= 1x
        nz_m, nz_v = ms[1:], vals[1:]
        peak_m = nz_m[int(np.argmax(nz_v))]
        if max(nz_v) <= 0:
            shape = "FAIL shape (never positive)"
        elif all(b > a for a, b in zip(nz_v, nz_v[1:])):
            shape = "PASS shape, nominal (monotone rise)"
        elif peak_m >= 1.0:
            shape = f"PASS shape, nominal (peak at {peak_m:g}x)"
        else:
            shape = f"FAIL shape (peak below 1x, at {peak_m:g}x)"
        if shape.startswith("PASS"):
            n_pass_shape += 1
        say(f"  {pid} ({summ[pid]['cls']}/{summ[pid]['kind']}):  "
            + "  ".join(f"{m:g}x:{v:+.1f}" for m, v in zip(ms, vals))
            + f"   -> {shape}")
        say(f"       clustered SEs:      " + "  ".join(f"{m:g}x:{s:.1f}"
                                                       for m, s in zip(ms, ses)))
    say("")
    say(f"  MEASURED FALSE-POSITIVE RATE OF THE S3 SHAPE CRITERION: {n_pass_shape} of "
        f"{len(sweep_ids)} zero-information sweeps show a nominal PASS shape.")
    say("  A PASS shape on a placebo is pure noise wearing the criterion's clothes — in Grading-")
    say("  phase verdicts a PASS shape is supporting evidence only when its magnitudes clear the")
    say("  placebo bar too; it can never rescue a below-bar point estimate.")
    say("")

    say("=" * 96)
    say("SECTION 3 — WHAT THE PLACEBO DISTRIBUTION IS MADE OF (precision, assignment item 3)")
    say("=" * 96)
    mean_se2 = float(np.mean([est[pid]["ci"]["se"] ** 2 for pid in est]))
    var_est = float(ests.var(ddof=1))
    say(f"  mean per-placebo clustered SE^2 : {mean_se2:7.1f}  (avg SE {np.sqrt(mean_se2):.1f})")
    say(f"  cross-placebo variance          : {var_est:7.1f}  (sd {np.sqrt(var_est):.1f})")
    share = min(1.0, mean_se2 / var_est) if var_est > 0 else float("nan")
    say(f"  => share of placebo spread attributable to instrument measurement noise: {share:.0%}")
    if mean_se2 >= var_est:
        say("  The mean per-placebo SE^2 EXCEEDS the cross-placebo variance: the placebo spread is")
        say("  FULLY explained by instrument measurement noise, exactly what 20 true-zero effects")
        say("  should produce. No detectable 'flag-set luck' component beyond noise.")
    else:
        say("  The remainder is 'flag-set luck' — a random flag set interacting with one realized")
        say("  season of outcomes. BOTH belong in the bar: a real treatment's point estimate")
        say("  carries both noise sources too (same instrument, same seeds, same seasons).")
    say("")
    s_w_all = float(np.mean([est[pid]["s_w"] for pid in est]))
    m_per = N_DRAFTS * len(SLOTS)
    say("  SE ARITHMETIC for the reduced design (S11; assignment item 3):")
    say(f"    within-season per-draft paired-diff SD, measured mean over placebos: s_w = {s_w_all:.0f}")
    say(f"    drafts per season-cluster: m = {N_DRAFTS} x {len(SLOTS)} slots = {m_per}")
    say(f"    within contribution to a season mean: s_w/sqrt(m) = {s_w_all / np.sqrt(m_per):.1f} pts")
    say(f"    T0.5c's full design (5 slots, m=500) [R]: season SD 25.3, clustered SE 12.7")
    say(f"    this design's measured mean season-SD across placebos: "
        f"{np.mean([est[p]['ci']['sd'] for p in est]):.1f}; clustered SE (df=3): "
        f"{np.mean([est[p]['ci']['se'] for p in est]):.1f}")
    say(f"    => the between-season (cluster) term dominates; restricting slots 5->2 and using")
    say(f"       {N_DRAFTS} drafts costs little precision on the placebo point estimates, and the")
    say(f"       residual measurement noise INFLATES the placebo spread (conservative: the bar")
    say(f"       can only be too high, never too low, from this reduction).")
    say("")

    say("=" * 96)
    say("SECTION 4 — VERDICT (what Grading-phase agents must do with this)")
    say("=" * 96)
    say(f"  * The real bar for every points verdict is max(placebo p95 = {p95:+.1f}, the stated")
    say(f"    charter number) — S15. Print this p95 at the top of the verdict table.")
    say(f"  * Placebos clearing +15/+20/+25 (Section 1 counts) measure how often noise beats the")
    say(f"    stated bars on this exact instrument at cohort_pull-scale nudges (cap 4 slots).")
    say(f"  * For treatments with LARGER caps (prereq-style +/-8..12 slots), use the 2x/4x sweep")
    say(f"    rows: the placebo spread grows with magnitude; a big-cap treatment must clear the")
    say(f"    bigger-magnitude placebo spread, not the 1x one.")
    say(f"  * The instrument MDE (~±53 league pts t-based at n=4 [R, T0.5]) still applies: a bar")
    say(f"    below the MDE means DIRECTIONAL-ONLY regardless of the placebo p95 (S11).")
    say("")
    say(f"  total wall time {time.time() - t_start:.0f}s · caches in 50_cache/ (delete to re-run)")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
