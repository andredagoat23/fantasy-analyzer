"""36 — What is a point of PROJECTION ACCURACY actually worth, in roster points?

The honest reason this exists: after 33_ (prereq rules) and 35_ (WR calibration) both returned nulls,
I claimed chasing projection accuracy was low-value too. That was an unjustified extrapolation. Those
interventions were TINY — a tie-breaker on a few players, and a one-rank reordering. Improving the
projections reorders the ENTIRE board, which is a different scale of change. The user pushed back and
was right to.

Method: synthesize projections of known accuracy by mixing the real projection with the realized
outcome, `synth = (1-w)*proj_rescaled + w*actual`. w=0 is today's projection; w=1 is perfect
foresight. Each w yields a measurable Spearman-vs-actual AND a draft outcome, so the pair traces the
exchange rate between accuracy and points.

Then read off the question directly: **what do 5 percentage points of Spearman buy?**

Honest limits, stated up front:
  * Mixing in the outcome is an IDEALISED improvement — it sharpens a projection uniformly and
    without bias. A real gain (a better model, another source) would be lumpier and partly
    correlated with what the projection already gets right, so treat this as an OPTIMISTIC bound.
  * Same harness as 33_/35_: 12-team snake, seat 7, paired seeds, opponents on ADP+noise, scored on
    actual season points with an optimal lineup.

Run:  .venv/bin/python icm/work/mc_research/36_projection_roi.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("wb", os.path.join(HERE, "35_wr_bias_backtest.py"))
wb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wb)

OUT = os.path.join(HERE, "results_36_projection_roi.txt")
SEASONS = (2024, 2025)
N_DRAFTS = 250
WEIGHTS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 0.75, 1.0)

lines = []


def say(s):
    print(s)
    lines.append(s)


def main():
    say("WHAT IS PROJECTION ACCURACY WORTH? (roster points per point of Spearman)")
    say(f"  12-team snake, seat 7 · {N_DRAFTS} PAIRED drafts per season per accuracy level")
    say("  synth = (1-w)*projection + w*actual — an IDEALISED, unbiased sharpening, so the numbers")
    say("  below are an OPTIMISTIC bound on what a real projection improvement would buy.\n")
    pools = wb.load_pools()
    per_season = {}
    for s in SEASONS:
        df = pd.DataFrame(pools[s])
        df = df[df["adp"] <= 220].reset_index(drop=True)
        # rescale the projection to the actual's mean so the mix isn't just a level correction
        df["p0"] = df["proj"] * (df["actual"].mean() / df["proj"].mean())
        rows = []
        base_pts = None
        for w in WEIGHTS:
            df["synth"] = (1 - w) * df["p0"] + w * df["actual"]
            rho = df["synth"].rank().corr(df["actual"].rank())
            df["v"] = wb.vols(df, "synth")
            df["v_base"] = wb.vols(df, "p0")
            tot = []
            for i in range(N_DRAFTS):
                tot.append(wb.simulate(df, np.random.default_rng(9000 + i), "v"))
            mean_pts = float(np.mean(tot))
            if base_pts is None:
                base_pts = mean_pts
            rows.append((w, rho, mean_pts, mean_pts - base_pts))
        per_season[s] = rows
        say(f"  === {s} (n={len(df)} players) ===")
        say(f"  {'w':>6}{'Spearman':>11}{'roster pts':>12}{'vs today':>10}")
        for w, rho, pts, d in rows:
            tag = "   <- today's projection" if w == 0 else ("   <- perfect foresight" if w == 1 else "")
            say(f"  {w:>6.2f}{rho:>11.3f}{pts:>12.0f}{d:>+10.1f}{tag}")
        say("")

    say("=" * 72)
    say("THE EXCHANGE RATE — points gained per +0.05 Spearman (pooled across seasons)")
    say("=" * 72)
    say(f"  {'accuracy band':<28}{'Δ Spearman':>12}{'Δ points':>11}{'pts per +0.05':>15}")
    allrows = [per_season[s] for s in SEASONS]
    for i in range(1, len(WEIGHTS)):
        drho = np.mean([r[i][1] - r[i - 1][1] for r in allrows])
        dpts = np.mean([r[i][3] - r[i - 1][3] for r in allrows])
        rate = (dpts / drho * 0.05) if drho > 1e-9 else float("nan")
        lo = np.mean([r[i - 1][1] for r in allrows])
        hi = np.mean([r[i][1] for r in allrows])
        say(f"  {f'{lo:.3f} -> {hi:.3f}':<28}{drho:>+12.3f}{dpts:>+11.1f}{rate:>+15.1f}")

    first = [r[1] for r in allrows]
    base_rho = np.mean([r[0][1] for r in allrows])
    say("")
    say(f"  Today's projection sits at Spearman {base_rho:.3f}.")
    tgt = np.mean([r[1][3] for r in allrows])
    dr = np.mean([r[1][1] - r[0][1] for r in allrows])
    say(f"  The FIRST real step (w=0.05) buys {dr:+.3f} Spearman for {tgt:+.1f} pts, i.e. "
        f"~{tgt / dr * 0.05:+.0f} pts per +0.05.")
    perfect = np.mean([r[-1][3] for r in allrows])
    say(f"  PERFECT foresight is worth {perfect:+.0f} pts — the absolute ceiling on all projection work.")
    say("")
    say("  Compare: 33_'s prereq rules were +5.2 pts and 35_'s calibration fix -8.2 pts. If a")
    say("  realistic +0.05 in accuracy is worth many times that, projections are a genuinely")
    say("  different lever and worth pushing on; if not, the same ceiling applies.")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
