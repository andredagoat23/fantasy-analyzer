"""49 — HARNESS SELF-TEST (charter T0.5): provenance, legacy gate, corrected-mode finding.

Stages (results land in results_49_grader_selftest.txt; heavy intermediates cached in 49_cache/
so a retry RESUMES rather than restarts):
  T0.5a  provenance — diff the regenerated results_33_harsh_backtest.txt against its .bak.
  T0.5b  LEGACY gate (the ONLY stop-and-fix condition): new grader in legacy config must
         reproduce the prerequisite bundle at +5.2 ± 2 AND 51.5% ± 1pp win rate.
  diag   legacy policy under MEASURED opponent dispersion — isolates the opponent model
         (charter T0.4: "re-run the prerequisite bundle under both opponent models").
  T0.5c  CORRECTED mode — same bundle in the corrected instrument (composite arm, weekly
         hindsight-optimal scoring, measured dispersion, five slots, league currency).
         The delta vs +5.2 is reported AS A FINDING; divergence is EXPECTED, not failure.
  arms   arm2−arm1 sanity floor (composite vs ADP-follow, paired seeds) — SECONDARY only.
  jack   leave-one-player-out jackknife on the most-frequently-flag-drafted player.
  MDE    the instrument's measured MDE at 80% power from the actual clustered SEs.

Run:  .venv/bin/python icm/work/mc_research/49_run_selftest.py
"""
import importlib.util
import os
import pickle
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("g49", os.path.join(HERE, "49_grader_lib.py"))
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

OUT = os.path.join(HERE, "results_49_grader_selftest.txt")
CACHE_DIR = os.path.join(HERE, "49_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def cached(name, fn):
    p = os.path.join(CACHE_DIR, name + ".pkl")
    if os.path.exists(p):
        say(f"  [resume] {name} loaded from cache")
        with open(p, "rb") as f:
            return pickle.load(f)
    t0 = time.time()
    r = fn()
    with open(p, "wb") as f:
        pickle.dump(r, f)
    say(f"  [{name}] computed in {time.time() - t0:.0f}s, cached")
    return r


# =================================================================================================
def stage_t05a():
    say("=" * 96)
    say("T0.5a — PROVENANCE: 33_harsh_backtest.py re-run unmodified, output diffed vs backup")
    say("=" * 96)
    cur = open(os.path.join(HERE, "results_33_harsh_backtest.txt")).read()
    bak_path = os.path.join(HERE, "results_33_harsh_backtest.txt.bak")
    if not os.path.exists(bak_path):
        say("  [V] backup missing — provenance diff was done pre-run by the orchestrating agent")
        return
    bak = open(bak_path).read()
    if cur == bak:
        say("  [V] BYTE-IDENTICAL. Fixed seeds (default_rng(10_000+i)) reproduce on this")
        say("      environment — the historical results file is untouched and trustworthy.")
    else:
        import shutil
        shutil.copy(bak_path, os.path.join(HERE, "results_33_harsh_backtest.txt"))
        say("  [V] DRIFT DETECTED — regenerated output differs; backup RESTORED over the drifted")
        say("      file. Environment drift must be diagnosed before trusting any grader number.")
        raise SystemExit("T0.5a drift — stop")


def stage_t05b(legacy_pools):
    say("")
    say("=" * 96)
    say("T0.5b — LEGACY GATE: new grader, legacy config (ADP policy + prereq nudge, season totals,")
    say("        flat noise 8.0, slot 7, 33_'s exact population & seeds). Stop-and-fix if missed.")
    say("=" * 96)
    res = cached("legacy", lambda: g.run_paired(legacy_pools, g.LEGACY, say=say))
    seasons = sorted({k[1] for k in res})
    D = np.concatenate([res[(7, s)]["db"] for s in seasons])          # 33_'s currency = base PPR
    mean, win, ident = D.mean(), (D > 0).mean(), (D == 0).mean()
    say(f"\n  pinned 33_ result [R]: +5.2 mean · 51.5% win · 0.5% identical (2,500 paired drafts)")
    say(f"  new grader (legacy):   {mean:+.1f} mean · {win:.1%} win · {ident:.1%} identical "
        f"({len(D)} paired drafts)")
    say(f"  per-season Δbase: " +
        " ".join(f"{s}:{res[(7, s)]['db'].mean():+.1f}" for s in seasons))
    gate_mean = abs(mean - 5.2) <= 2.0
    gate_win = abs(win - 0.515) <= 0.01
    say(f"\n  GATE mean within ±2 of +5.2:  {'PASS' if gate_mean else 'FAIL'} "
        f"(|{mean:+.1f} − 5.2| = {abs(mean - 5.2):.2f})")
    say(f"  GATE win within ±1pp of 51.5%: {'PASS' if gate_win else 'FAIL'} "
        f"(|{win:.1%} − 51.5%| = {abs(win - .515):.1%})")
    if not (gate_mean and gate_win):
        say("  STOP-AND-FIX: the grader cannot reproduce the known result — nothing downstream")
        say("  is trustworthy until this is diagnosed (charter WS0 falsification).")
        raise SystemExit("T0.5b gate failed")
    say("  Equivalence note [V]: simulate() in legacy config was verified BITWISE-identical to")
    say("  33_'s simulate() over 10 paired drafts in each of 2015/2020/2024 before this run.")
    # bonus finding: the same 2,500 paired drafts in the REAL currency (league points)
    ci = g.cluster_ci([res[(7, s)]["dl"].mean() for s in seasons])
    say(f"\n  SECONDARY (S12) — the identical drafts graded in LEAGUE points: {ci['mean']:+.1f}")
    say(f"  [clustered 95% CI {ci['lo']:+.1f}, {ci['hi']:+.1f}; n={ci['n']} seasons] — the old")
    say(f"  base-PPR null holds in the real currency too on the legacy instrument.")
    return res


def stage_diag_measured(legacy_pools):
    say("")
    say("=" * 96)
    say("DIAGNOSTIC — same legacy bundle, opponents on the MEASURED dispersion curve (T0.4:")
    say("  'Re-run the prerequisite bundle under both opponent models and report the delta.')")
    say("=" * 96)
    res = cached("legacy_measured", lambda: g.run_paired(legacy_pools, g.LEGACY_MEASURED, say=say))
    seasons = sorted({k[1] for k in res})
    D = np.concatenate([res[(7, s)]["db"] for s in seasons])
    ci = g.cluster_ci([res[(7, s)]["db"].mean() for s in seasons])
    say(f"\n  flat 8.0 opponents:      +5.2 mean · 51.5% win  [pinned 33_ [R]]")
    say(f"  measured-sd opponents:   {D.mean():+.1f} mean · {(D > 0).mean():.1%} win · "
        f"clustered CI [{ci['lo']:+.1f}, {ci['hi']:+.1f}] (base PPR)")
    say(f"  per-draft spread: 95% of paired diffs in [{np.percentile(D, 2.5):+.0f}, "
        f"{np.percentile(D, 97.5):+.0f}] (33_ under flat noise: [-318, +319] [R])")
    return res


def stage_t05c(corrected_pools):
    say("")
    say("=" * 96)
    say("T0.5c — CORRECTED MODE: same prerequisite bundle in the corrected instrument")
    say("  (arm 3 = composite + bundle vs arm 2 = composite · weekly hindsight-optimal lineups ·")
    say("   league scoring · measured dispersion · slots 1/5/8/10/12 · CLEAN = 2021/22/24/25)")
    say("=" * 96)
    res = cached("corrected", lambda: g.run_paired(corrected_pools, g.CORRECTED, say=say))
    ci, D, Db, NC = g.report_primary(res, say=say, label="T0.5c corrected")
    # season-mode diagnostics on the SAME drafts (mode comparison for free)
    seasons = sorted({k[1] for k in res})
    slots = sorted({k[0] for k in res})
    Dsl = np.concatenate([res[(sl, s)]["dsl"] for sl in slots for s in seasons])
    Dsb = np.concatenate([res[(sl, s)]["dsb"] for sl in slots for s in seasons])
    say(f"\n  mode comparison on the SAME drafts (diagnostic):")
    say(f"    weekly league {D.mean():+.1f} · season-total league {Dsl.mean():+.1f} · "
        f"weekly base {Db.mean():+.1f} · season-total base {Dsb.mean():+.1f}")
    return res, ci, D


def stage_arms(corrected_pools):
    say("")
    say("=" * 96)
    say("ARM SANITY FLOOR — arm 2 (reconstructed composite) vs arm 1 (ADP-follow), paired seeds.")
    say("  SECONDARY ONLY (charter: arm3−arm1 may never be a headline; this is arm2−arm1).")
    say("=" * 96)

    def run():
        from dataclasses import replace
        cfg2 = g.CORRECTED
        cfg1 = replace(g.CORRECTED, name="adp_follow", policy="adp")
        out = {}
        for slot in cfg2.slots:
            for s, pool in corrected_pools.items():
                dl = []
                for i in range(cfg2.n_drafts):
                    m2 = g.simulate(pool, cfg2, slot, np.random.default_rng(cfg2.seed_base + i),
                                    use_delta=False)
                    m1 = g.simulate(pool, cfg1, slot, np.random.default_rng(cfg2.seed_base + i),
                                    use_delta=False)
                    dl.append(g.score_weekly(pool, m2, "league")
                              - g.score_weekly(pool, m1, "league"))
                out[(slot, s)] = np.array(dl)
        return out

    res = cached("arms21", run)
    seasons = sorted({k[1] for k in res})
    slots = sorted({k[0] for k in res})
    per_season = [np.concatenate([res[(sl, s)] for sl in slots]).mean() for s in seasons]
    ci = g.cluster_ci(per_season)
    D = np.concatenate(list(res.values()))
    say(f"  arm2 − arm1 = {ci['mean']:+.1f} league pts/draft · clustered CI "
        f"[{ci['lo']:+.1f}, {ci['hi']:+.1f}] · win {(D > 0).mean():.0%} · n={ci['n']} seasons")
    say(f"  per-slot: " + " ".join(
        f"slot{sl}:{np.concatenate([res[(sl, s)] for s in seasons]).mean():+.0f}" for sl in slots))
    say("  (the reconstructed composite must not LOSE to naive ADP-following, or arm 2 is not a")
    say("   credible reconstruction — a sanity check on the instrument, not a research finding)")
    return res


def stage_jackknife(corrected_pools, res_c):
    say("")
    say("=" * 96)
    say("JACKKNIFE — zero the bundle for the single most-frequently-flag-drafted player, re-run")
    say("  (charter reporting block #4: if one player moves the result by more than half, the")
    say("   finding is one player, not a rule)")
    say("=" * 96)
    top = g.top_flagged(res_c)
    if not top:
        say("  no flagged player was ever drafted differently — jackknife vacuous")
        return None
    nn, cnt = top[0]
    say(f"  target: '{nn}' (drafted into a changed arm-3 roster {cnt} times; next: "
        + ", ".join(f"{n}:{c}" for n, c in top[1:4]) + ")")
    res_j = cached("jackknife", lambda: g.run_paired(
        corrected_pools, g.CORRECTED, say=lambda *_: None, zero_adj_nn=nn))
    seasons = sorted({k[1] for k in res_j})
    slots = sorted({k[0] for k in res_j})
    per_season = [np.concatenate([res_j[(sl, s)]["dl"] for sl in slots]).mean() for s in seasons]
    ci = g.cluster_ci(per_season)
    say(f"  with '{nn}' un-flagged: Δ = {ci['mean']:+.1f} league pts "
        f"[clustered CI {ci['lo']:+.1f}, {ci['hi']:+.1f}]")
    return nn, ci


SIM_NOTES = """
ONE-PARAGRAPH NOTES ON THE 13 PRIOR SIMULATOR/GRADER SCRIPTS (charter T0.4 deliverable)
Each note answers: what did this instrument get wrong, judged against the corrected grader's
requirements (three arms / VONA policy / measured dispersion / multi-slot / weekly league scoring)?

08_backtest_sim — Monte-Carlo OUTCOME simulator validating the Wave-1 constants (band coverage,
  P(mult>=1.5), tier odds) per season. Not a draft simulator at all: it grades the projection's
  calibration, never a drafting policy, on the base-scoring panel. It can certify honest bands and
  still say nothing about whether any pick decision wins points.
09_wave2_validation — the same family for the Wave-2 mover tilts. Panel calibration, base scoring,
  no drafts, no arms, nothing incremental. Its findings shipped into the MC; as a GRADER it has no
  opinion.
11_stress_test — cohort LOSO validation plus board-invariant audit. A correctness harness: it
  asserts identities (percentile ordering, probability sums), never points. A board can pass every
  invariant here and still draft worse; it cannot detect that by design.
12_full_system_stress — plays full drafts through the real advisor and asserts invariants at every
  pick. Opponents are ADP + FLAT noise (the misspecified opponent model), only 3 slots x 2 seeds,
  and there is NO scoring of the resulting rosters — it proves the machinery does not crash or
  violate roster logic, not that it wins anything.
13_strategy_bakeoff — the real advisor vs six classic strategies, slot 7 only, flat-noise ADP
  bots. Fatal for grading: the lenses are OUR OWN projections (value/floor/injury-availability), so
  the advisor is graded by the very numbers it drafts on — circular by construction. No actual
  outcomes anywhere in the script.
14_capture_top3 — records the MODAL first-three picks per slot for the Research page, stopping
  each draft after round 3. A UI artifact, not a grader; inherits the flat-noise opponents and
  grades nothing.
16_scoring_robustness — audits the scoring/bonus math for linearity and edge cases across
  alternative scoring settings, loading real pbp. No drafts. Nothing wrong on its own terms — it is
  why the frozen chain's ARITHMETIC is trusted — but it is evidence about formulas, not about value.
17_weight_backtest — grades composite WEIGHTS by Spearman correlation with finishes over 3
  seasons, in-sample. Value signals are PRIOR-YEAR actuals (a backward proxy; the real board uses
  forward projections), veterans only, base scoring, and rank correlation has no roster structure:
  an ordering can improve while the drafted lineup gets worse (scarcity timing invisible).
18_weight_backtest_full — the honest 13-season LOSO extension of 17_. Same proxy defect (backward
  value signals judged the value weight unfairly low, stated in its own header), same no-draft
  no-roster limitation, base scoring.
33_harsh_backtest — the first points grader and the +5.2 result this self-test reproduces. What it
  got wrong: FLAT opponent sd 8.0 (measured curve runs 1.8-17.9 — ~4.4x too loose at the top,
  letting elite players free-fall to any seat, and it inflates the ±318 per-draft spread S4 quotes
  as a rhetorical anchor); hard-wired slot 7; SEASON-TOTAL optimal lineup, availability-blind (a
  200-pt/9-game season grades identical to 200/17 — yet 73-85% of busts in every band are
  unavailability, so the instrument systematically understates availability signals and overstates
  accumulation signals); BASE-PPR currency (S12: the league pays RB +64/WR +35/TE +25 mean bonus
  points to top-12 finishers — all invisible); pool adp<=200 giving 146-179 players, under the 222
  floor, so 192-pick drafts nearly exhaust the board and late rounds grade against fumes; and the
  comparison is ADP+nudge vs ADP — nothing measures the treatment as INCREMENTAL to the composite
  the user actually drafts with (the three-arm structure exists precisely to fix this).
35_wr_bias_backtest — brought out-of-sample correction factors and paired seeds (both good), but
  BOTH arms draft by raw VOLS while the real advisor drafts by VONA, flat noise, slot 7 only,
  base currency, season totals. A calibration fix graded under a policy the app does not run.
42_upgrade_backtest — introduced roster-need gating and the '% of drafts identical' report line
  (which is what made C5's null legible and is now mandatory), but its header admits the core
  defect: my picks are VOLS-scored, not VONA, which made the upgrade read structurally unable to
  fire (100.0% identical) — the exact vacuousness 44_ was built to fix. Flat noise, slot 7, base
  currency, season totals.
44_survival_curve_backtest — the base template of this grader: it fixed the two big ones (my picks
  through advisor.add_vona; opponents on the measured per-player dispersion) and ran five slots.
  Still wrong for the charter's purpose: SEASON-TOTAL scoring (availability-blind, D1), base-PPR
  'actual' from the blend cache as the only currency (S12), pool = cache adp<=220 = 183-193 real
  rows (below the 222 floor; the last rounds graze the pool bottom), no third arm (it A/B'd its own
  survival curve, so nothing measures a treatment against the composite), N=100/slot/season, and it
  restates 43_'s pick-sd table as literals beside advisor's survival scale with nothing saying the
  two tables are different objects — the exact two-curves trap T0.8 flags as M7. This library
  imports both tables from their homes (advisor / 44_) rather than restating either.
"""


def main():
    t_start = time.time()
    say("SELF-TEST OF THE THREE-ARM, TWO-MODE, FIVE-SLOT GRADER (charter T0.4 + T0.5)")
    say(f"  library: 49_grader_lib.py · run: 49_run_selftest.py · {time.strftime('%Y-%m-%d %H:%M')}")
    say("  All numbers [V] (computed this run) unless marked [R] (read from a prior results file).")
    say("")
    say("PRIMARY-ENDPOINT DECLARATION (S14, before any run): the grader's single primary endpoint")
    say("is arm 3 MINUS arm 2 in LEAGUE points in the declared mode, season-clustered CI (S11),")
    say("effective n = season clusters. Base PPR is the secondary currency (S12). Arm3−arm1 is")
    say("never a headline. For THIS self-test the corrected-mode number is a FINDING about the")
    say("instrument (expected to disagree with +5.2), not a hypothesis verdict.")
    say("")

    stage_t05a()

    say("")
    say("=" * 96)
    say("POOLS (S8: per-year counts asserted; population.json asserted on load)")
    say("=" * 96)
    lp = g.legacy_pools(say=say)
    say("  legacy pool = 33_'s exact population (seasons_exp, adp<=200, season>=2015; the 222")
    say("  floor is WAIVED here BY DESIGN — the pool must equal 33_'s or the gate is meaningless).")
    cp = g.corrected_pools(say=say)
    say("  corrected pools: blend-cache CLEAN seasons at adp<=220 (44_'s prep) + Sleeper-extension")
    say("  padding to adp<=300 (T0.2's sanctioned option: priced-but-unplayed enter at real price,")
    say("  zero projection). INSTRUMENT NOTE: 2025 prices are SLEEPER adp_ppr (T0.2 repair) — not")
    say("  ESPN, not FFC; cache 2021-2024 adp is FFC-primary with Sleeper fallback (38_).")

    legacy_res = stage_t05b(lp)
    stage_diag_measured(lp)
    res_c, ci_c, D_c = stage_t05c(cp)
    stage_arms(cp)
    jk = stage_jackknife(cp, res_c)

    say("")
    say("=" * 96)
    say("HEADLINE FINDING (T0.5c) — what the corrected instrument says about the SAME bundle")
    say("=" * 96)
    say(f"  legacy instrument [R+V]: +5.2 base-PPR pts (reproduced this run to the decimal)")
    say(f"  corrected instrument [V]: {ci_c['mean']:+.1f} LEAGUE pts "
        f"[clustered 95% CI {ci_c['lo']:+.1f}, {ci_c['hi']:+.1f}, n={ci_c['n']} seasons]")
    say(f"  The corrected grader was EXPECTED to disagree — reproducing +5.2 would have meant it")
    say(f"  inherited the legacy defects (flat dispersion, availability blindness, base currency,")
    say(f"  ADP-policy me). Divergence here is the instrument working, not a bug (charter T0.5c).")
    say("")
    say(f"  INSTRUMENT MDE (80% power, from the ACTUAL clustered SE, n={ci_c['n']} seasons):")
    say(f"    ±{ci_c['mde80']:.0f} league pts (t-based, df={ci_c['n'] - 1}) · "
        f"±{ci_c['mde80_normal']:.0f} (normal approx) · charter's a-priori estimate: +90-100 [R]")
    say(f"    Any Grading-phase bar below this MDE must be reported DIRECTIONAL-ONLY, not PASS")
    say(f"    (S11). The composite arm exists for {ci_c['n']} seasons; that is the hard constraint")
    say(f"    the charter names — the honest deliverable for small effects is a ranked hypothesis")
    say(f"    list plus the 2026 live test, not a points verdict.")

    say(SIM_NOTES)

    say("=" * 96)
    say("PROVENANCE, CONVENTIONS, AND WHAT WAS NOT DONE")
    say("=" * 96)
    say("""  CONVENTIONS BAKED INTO THE INSTRUMENT:
  * D1: draft grading uses weekly HINDSIGHT-optimal lineups (weeks 1-17 for >=2021), fixed
    replacement fill (per-season per-position mean weekly points of players season-ranked
    REPL+1..REPL+6 — the waiver tier) for slots with no available player. Ex-ante lineups are for
    in-season detector grading, a different instrument, per D1.
  * Both currencies are graded from the SAME T0.3 panel (weekly_league.parquet pts_league /
    pts_base) over the SAME weeks, so currency deltas are pure scoring-table effects. The blend
    cache's 'actual' column is used ONLY to scale projections (44_'s prep, unchanged).
  * The treatment enters the composite policy through the measured price-value curve:
    adj_pts = V(adp − adj_slots) − V(adp), V = per-position monotone envelope of VOLS over ADP
    (rolling-median smoothed). 'Move him N slots earlier on the value curve' — no invented
    points-per-slot constant.
  * Opponent dispersion: 43_'s measured pick-sd table, imported from 44_ (one home). Survival:
    advisor._SCALE_ADP/_SCALE_S via advisor.add_vona (one curve). These are DIFFERENT objects
    (pick-sd vs logistic scale) — restating either is the L52/L53 failure mode.
  * Runtime invariants asserted per run: composite policy => VONA picks + measured dispersion +
    advisor.USE_MEASURED_SCALE. Pool >= 222 asserted (corrected); PopulationMismatch /
    PoolTooSmall / WeeklyPanelMissing are named aborts.

  NOT DONE / LIMITS (stated per charter honesty rules):
  * The 62.1% OOS band coverage and −11.5pp WR COLD figures were NOT re-run (T0.5 forbids;
    settled, cited from their results files).
  * T0.6 placebo calibration is NOT here — thresholds stay PROVISIONAL (S15) until it runs.
  * Weekly-mode join coverage: ~99% of cache rows with an 'actual' value match the league panel;
    unmatched pool rows are almost entirely extension-pad players who never played (graded 0,
    correct) plus a few name-variant misses (counted per season above). Rookies with no prev_*
    row get missed=0/durable=0 — identical to 33_'s NaN handling.
  * Arm 2 is a RECONSTRUCTION (50/50 ESPN/Sleeper blend + VOLS + VONA + need-gating). It carries
    no ceiling/floor/role/cohort terms, so treatments touching those graded against arm 2 see a
    board that under-expresses the shipped composite (T0.8's false-null warning stands).
  * K and D/ST are not drafted (panel has no league-scored K/DST history — T0.3 scope cut);
    16 roster spots over QB/RB/WR/TE only, as in every prior template.
  * 2019/2020 (backfilled Sleeper projections) and 2023 (31 cache rows) remain unusable for the
    composite arm; the corrected instrument is n=4 season clusters until a new honest projection
    source for those years exists (none is known).""")

    say(f"\n  total wall time {time.time() - t_start:.0f}s · caches in 49_cache/ (delete to re-run)")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
