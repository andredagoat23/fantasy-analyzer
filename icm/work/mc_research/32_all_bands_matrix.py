"""32 — Finish the board: R7-10 and the late rounds, presented as ONE condition x band matrix.

The capital rule (31_) died because it was discovered in one band and never checked in the others.
Reporting band-by-band invites exactly that mistake — you find something in the band you happen to be
studying and write it up. So this completes the remaining bands (R7-10, R11+) and then puts EVERY
condition against EVERY band in a single table, with a consistency count.

A finding that appears in one column and vanishes elsewhere is now visible as such, at a glance,
instead of needing a dedicated replication script to catch it.

Bands (by ADP): R1 1-15 · R2-3 16-40 · R4-6 41-75 · R7-10 76-125 · R11+ 126-200.

Late-round caveat: past ~R11 nearly everyone is below replacement, so `mult` (finish ÷ price) gets
noisy and generous — a cheap player who does anything clears his price. Base rates are printed so the
inflation is visible, and `late-round-strategy.md` (the validated DART READ playbook, built from a
purpose-made analysis) remains the source of truth there. This does not overrule it.

Run:  .venv/bin/python icm/work/mc_research/32_all_bands_matrix.py
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_32_matrix.txt")

BANDS = [(1, 15, "R1"), (16, 40, "R2-3"), (41, 75, "R4-6"), (76, 125, "R7-10"), (126, 200, "R11+")]
N_BOOT = 1200
RNG = np.random.default_rng(0)

NUM = ["adp", "adp_pos_rank", "age", "mult", "games", "season", "draft_number", "prev_games",
       "prev_snap_pct", "prev_touches_pg", "prev_tgt_share", "prev_wopr", "prev_ppg", "prev_xfp_pg",
       "prev_implied_total_avg", "prev_cv", "prev_pos_rank_total", "prev_total_touches", "years_exp"]

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def load():
    p = pd.read_parquet(PANEL)
    for c in NUM:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p[(p["adp"].notna()) & (p["season"] >= 2015)
          & p["position"].isin(["RB", "WR", "TE", "QB"])].copy()
    p["hit"] = (p["mult"] >= 1.0).astype(float)
    p["bust"] = (p["mult"] <= 0.7).astype(float)
    return p


def conditions(p):
    med = lambda s: s.median()
    c = pd.DataFrame(index=p.index)
    ratio = p["prev_ppg"] / p["prev_xfp_pg"].replace(0, np.nan)
    c["earned_prod"] = ratio <= 1.15
    c["capital_top32"] = p["draft_number"].fillna(999) <= 32
    c["capital_top64"] = p["draft_number"].fillna(999) <= 64
    c["wopr_strong"] = p["prev_wopr"].fillna(0) >= p["prev_wopr"].groupby(p["position"]).transform(med)
    c["proven_at_price"] = p["prev_pos_rank_total"].fillna(99) <= p["adp_pos_rank"].fillna(99)
    c["had_a_role"] = p["prev_snap_pct"].fillna(0) >= 0.50
    c["durable_prev"] = p["prev_games"] >= 15
    c["young"] = p["age"] <= 26
    c["good_offense"] = p["prev_implied_total_avg"] >= p["prev_implied_total_avg"].median()
    c["light_workload"] = p["prev_total_touches"] < p["prev_total_touches"].median()
    c["consistent"] = p["prev_cv"] <= p["prev_cv"].groupby(p["position"]).transform(med)
    # the CONDITIONAL that survived replication (28_ + 31_): only meaningful for players who
    # missed time last year — carried here so the matrix shows it is genuinely band-wide
    c["proven_AND_missed"] = ((p["prev_pos_rank_total"].fillna(99) <= p["adp_pos_rank"].fillna(99))
                              & (p["prev_games"] < 15))
    return c.astype(float)


def lift(hit, cond, min_n=12):
    t, f = cond == 1, cond == 0
    if t.sum() < min_n or f.sum() < min_n:
        return np.nan
    return 100.0 * (hit[t].mean() - hit[f].mean())


def boot_p(hit, cond):
    h, c = np.asarray(hit, float), np.asarray(cond, float)
    n, out = len(h), []
    for _ in range(N_BOOT):
        i = RNG.integers(0, n, n)
        hh, cc = h[i], c[i]
        t, f = cc == 1, cc == 0
        if t.sum() >= 5 and f.sum() >= 5:
            out.append(100.0 * (hh[t].mean() - hh[f].mean()))
    return float((np.array(out) > 0).mean()) if len(out) >= 100 else np.nan


def base_rates(p):
    say("=" * 92)
    say("A. THE WHOLE BOARD — base rates by band")
    say("=" * 92)
    say(f"  {'band':<8}{'n':>6}{'HIT':>8}{'BUST':>8}{'med mult':>10}   note")
    for lo, hi, lab in BANDS:
        s = p[(p["adp"] >= lo) & (p["adp"] <= hi)]
        note = ("best value band" if lab == "R2-3" else
                "worst; RB bust 31%" if lab == "R4-6" else
                "mult inflates here — everyone is cheap" if lab == "R11+" else "")
        say(f"  {lab:<8}{len(s):>6}{s['hit'].mean():>8.1%}{s['bust'].mean():>8.1%}"
            f"{s['mult'].median():>10.2f}   {note}")
    say("\n  R7-10 and R11+ by position:")
    for lo, hi, lab in BANDS[-2:]:
        band = p[(p["adp"] >= lo) & (p["adp"] <= hi)]
        row = f"    {lab:<7}"
        for pos in ("RB", "WR", "TE", "QB"):
            s = band[band["position"] == pos]
            row += f"{pos} n={len(s):<4} HIT {s['hit'].mean():.0%}   " if len(s) >= 20 else f"{pos} —   "
        say(row)


def matrix(p):
    say("\n" + "=" * 92)
    say("B. THE MATRIX — every condition, every band. Lift in pp; (P) = bootstrap P(lift>0).")
    say("=" * 92)
    say("  A finding that is REAL should hold its sign across bands. One big number surrounded by")
    say("  noise is what the withdrawn capital rule looked like — that shape is now visible here.\n")
    cols = [lab for _, _, lab in BANDS]
    header = f"  {'condition':<20}" + "".join(f"{c:>15}" for c in cols) + f"{'consistent':>12}"
    say(header)
    say("  " + "-" * (len(header) - 2))
    rows = {}
    for lo, hi, lab in BANDS:
        band = p[(p["adp"] >= lo) & (p["adp"] <= hi)]
        cs = conditions(band)
        for col in cs.columns:
            l0 = lift(band["hit"], cs[col])
            pg = boot_p(band["hit"], cs[col]) if not np.isnan(l0) else np.nan
            rows.setdefault(col, {})[lab] = (l0, pg)
    for col, by_band in rows.items():
        cells, signs = "", []
        for lab in cols:
            l0, pg = by_band.get(lab, (np.nan, np.nan))
            if np.isnan(l0):
                cells += f"{'—':>15}"
                continue
            cells += f"{l0:>+9.1f}({pg:>3.2f})"
            if abs(l0) >= 5:
                signs.append(np.sign(l0))
        if signs:
            same = max(signs.count(1), signs.count(-1))
            tag = f"{same}/{len(signs)}" + ("  ✅" if same >= 3 and same == len(signs) else
                                            "  ⚠️" if same == len(signs) and same == 2 else "  ✗")
        else:
            tag = "flat"
        say(f"  {col:<20}{cells}{tag:>12}")
    say("\n  ✅ = same direction in 3+ bands (believable) · ⚠️ = only 2 · ✗ = flips sign somewhere")
    say("  'flat' = never reaches 5pp anywhere, i.e. no effect worth discussing.")
    return rows


def late_check(p):
    say("\n" + "=" * 92)
    say("C. LATE ROUNDS (R11+) — cross-check against the VALIDATED DART playbook")
    say("=" * 92)
    say("  late-round-strategy.md is the source of truth here (a purpose-built per-profile analysis).")
    say("  This is only a consistency check; where they disagree, trust the playbook.\n")
    late = p[(p["adp"] >= 126) & (p["adp"] <= 200)]
    say(f"  R11+ n={len(late)} · HIT {late['hit'].mean():.1%} · BUST {late['bust'].mean():.1%} "
        f"· med mult {late['mult'].median():.2f}")
    say(f"  NOTE the inflation: {late['hit'].mean():.0%} 'hit' rate at a price this low means the")
    say("  metric is nearly meaningless late — a 14th-rounder who plays at all beats his price.")
    say("  This is exactly why the DART READ uses PROFILES rather than value math after R11.\n")
    cs = conditions(late)
    say(f"  {'condition':<20}{'lift':>8}{'P(>0)':>8}")
    for col in cs.columns:
        l0 = lift(late["hit"], cs[col])
        if np.isnan(l0) or abs(l0) < 5:
            continue
        say(f"  {col:<20}{l0:>+7.1f}{boot_p(late['hit'], cs[col]):>8.2f}")
    say("\n  Read these as descriptive only. The validated late-round rules (post-hype target share,")
    say("  RB-only handcuffs, the injury-discount vet fade) came from analyses built for the")
    say("  question; a generic hit-rate lift on an inflated metric cannot overturn them.")


def main():
    p = load()
    say(f"panel: {len(p)} priced player-seasons, 2015-2024 "
        f"(2025 rows carry outcomes but no preseason ADP, so they cannot enter a price analysis)\n")
    base_rates(p)
    matrix(p)
    late_check(p)
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
