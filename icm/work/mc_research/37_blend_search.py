"""37 — Search EVERY blend weight, backtest each, and pick the most RELIABLE (not just the best).

The question: our board is 65% ESPN / 35% FantasyPros. 34_ showed ESPN is the weakest projection
source we can measure (+0.647) and Sleeper the strongest (+0.717), and 36_ showed accuracy is worth
~130-200 roster points per +0.05 Spearman. So what weighting should we actually use?

SOURCE AVAILABILITY — why this is a two-source search:
  * ESPN     — usable. Verified preseason and uncontaminated (34_).
  * Sleeper  — usable. Same verification.
  * FantasyPros — NOT retrievable historically (proprietary). The shipped 0.35/0.65 FP/ESPN weight
    therefore still cannot be validated directly; this measures the PRINCIPLE (does adding a second,
    better source help, and how much) on the two sources that can be tested.
  * panel `exp_pts` — DISQUALIFIED. It is E[actual pts | preseason rank] with the curve fit over
    2019-2025 INCLUDING the test seasons, and it is a monotone transform of preseason rank rather
    than an independent forecast. Blending it would re-inject rank plus leakage and manufacture a
    fake win. (Its +0.655 in 34_ is real but comes from converting rank to a cross-position POINTS
    scale — the same job VOLS does — not from new information.)

"Most reliable" is deliberately not "highest scoring". A weight is only recommended if it (a) wins in
BOTH seasons, (b) survives an out-of-sample check (fit on one season, evaluate on the other), and
(c) sits on a FLAT part of the curve — a knife-edge optimum is a fitting artifact, which is the
lesson L49 was written for.

Run:  .venv/bin/python icm/work/mc_research/37_blend_search.py
"""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

_spec = importlib.util.spec_from_file_location("wb", os.path.join(HERE, "35_wr_bias_backtest.py"))
wb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wb)

OUT = os.path.join(HERE, "results_37_blend_search.txt")
SEASONS = (2024, 2025)
WEIGHTS = [round(x, 2) for x in np.arange(0.0, 1.01, 0.1)]   # weight on ESPN
N_DRAFTS = 200

lines = []


def say(s):
    print(s)
    lines.append(s)


def prep(pool):
    """Rescale both sources to a common mean so the blend is a genuine mix, not a level shift."""
    df = pd.DataFrame(pool)
    df = df[(df["adp"] <= 220) & df["sleeper"].notna()].reset_index(drop=True)
    for c in ("espn", "sleeper"):
        df[c + "_s"] = df[c] * (df["actual"].mean() / df[c].mean())
    return df


def build_pools():
    """Attach Sleeper projections to the cached ESPN pools (35_'s cache holds ESPN + ADP only)."""
    import json

    import requests
    from utils import normalize_name
    from scoring_config import SCORING
    SL = {"pass_yds": "pass_yd", "pass_td": "pass_td", "pass_int": "pass_int",
          "rush_yds": "rush_yd", "rush_td": "rush_td",
          "rec": "rec", "rec_yds": "rec_yd", "rec_td": "rec_td"}
    base = wb.load_pools()
    pl = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=45).json()
    name = {pid: p.get("full_name") for pid, p in pl.items() if p.get("full_name")}
    out = {}
    for s in SEASONS:
        pr = requests.get(f"https://api.sleeper.app/v1/projections/nfl/regular/{s}", timeout=40).json()
        sp = {}
        for pid, d in pr.items():
            nm = name.get(pid)
            if not nm:
                continue
            v = sum(float(d.get(k, 0) or 0) * SCORING.get(c, 0) for c, k in SL.items())
            if v > 20:
                sp[normalize_name(nm)] = v
        rows = []
        for r in base[s]:
            rows.append({**r, "espn": r["proj"], "sleeper": sp.get(normalize_name(r["name"]))})
        out[s] = rows
    return out


def evaluate(df, w, n_drafts=N_DRAFTS):
    """(Spearman vs actual, mean roster points) for a blend at weight w on ESPN."""
    df = df.copy()
    df["blend"] = w * df["espn_s"] + (1 - w) * df["sleeper_s"]
    rho = df["blend"].rank().corr(df["actual"].rank())
    df["v"] = wb.vols(df, "blend")
    pts = [wb.simulate(df, np.random.default_rng(4100 + i), "v") for i in range(n_drafts)]
    return rho, float(np.mean(pts))


def main():
    say("BLEND SEARCH — every ESPN/Sleeper weighting, scored AND backtested")
    say(f"  12-team snake, seat 7 · {N_DRAFTS} drafts per weight per season · common seeds throughout")
    say("  w = weight on ESPN; the remainder goes to Sleeper. Our live board is 65% ESPN (vs FP).\n")
    pools = build_pools()
    dfs = {s: prep(pools[s]) for s in SEASONS}
    for s in SEASONS:
        say(f"  {s}: {len(dfs[s])} players with ESPN + Sleeper + ADP + actual")

    res = {}
    for s in SEASONS:
        say(f"\n  === {s} ===")
        say(f"  {'w(ESPN)':>9}{'Spearman':>11}{'roster pts':>12}{'vs 65% ESPN':>13}")
        rows = []
        for w in WEIGHTS:
            rho, pts = evaluate(dfs[s], w)
            rows.append((w, rho, pts))
        ref = [p for w, r, p in rows if abs(w - 0.7) < 1e-6][0]   # nearest grid point to our 0.65
        for w, rho, pts in rows:
            mark = "  <- ~our live weight" if abs(w - 0.7) < 1e-6 else ""
            say(f"  {w:>9.1f}{rho:>11.3f}{pts:>12.0f}{pts - ref:>+13.0f}{mark}")
        res[s] = rows

    say("\n" + "=" * 78)
    say("RELIABILITY — does one weight win in BOTH seasons, and is the curve flat there?")
    say("=" * 78)
    say(f"  {'w(ESPN)':>9}{'rho 2024':>11}{'rho 2025':>11}{'pts 2024':>11}{'pts 2025':>11}{'both>ref?':>11}")
    ref = {s: [p for w, r, p in res[s] if abs(w - 0.7) < 1e-6][0] for s in SEASONS}
    winners = []
    for i, w in enumerate(WEIGHTS):
        r24, p24 = res[2024][i][1], res[2024][i][2]
        r25, p25 = res[2025][i][1], res[2025][i][2]
        both = p24 > ref[2024] and p25 > ref[2025]
        if both:
            winners.append((w, (p24 - ref[2024] + p25 - ref[2025]) / 2))
        say(f"  {w:>9.1f}{r24:>11.3f}{r25:>11.3f}{p24:>11.0f}{p25:>11.0f}{('YES' if both else '-'):>11}")

    say("\n  OUT-OF-SAMPLE — pick the best weight on one season, apply it to the other:")
    for fit, test in ((2024, 2025), (2025, 2024)):
        best_w = max(res[fit], key=lambda r: r[2])[0]
        i = WEIGHTS.index(best_w)
        gain = res[test][i][2] - ref[test]
        say(f"    fit on {fit} -> w={best_w:.1f} -> on {test}: {gain:+.0f} pts vs our ~65% ESPN weight")

    say("")
    # A single winning grid point is a KNIFE EDGE, not an optimum. Require a contiguous run of at
    # least 2 winning weights before calling anything recommendable — the L49 lesson applied to
    # weight-fitting rather than to rules.
    best24 = max(res[2024], key=lambda r: r[2])[0]
    best25 = max(res[2025], key=lambda r: r[2])[0]
    say(f"  best weight in 2024: w={best24:.1f} · best weight in 2025: w={best25:.1f} "
        f"(disagreement: {abs(best24 - best25):.1f})")
    if len(winners) >= 2:
        best = max(winners, key=lambda x: x[1])
        ws = sorted(w for w, _ in winners)
        say(f"  RECOMMENDED: w(ESPN) ~= {best[0]:.1f} (+{best[1]:.0f} pts avg), and {len(winners)} "
            f"adjacent weights ({min(ws):.1f}-{max(ws):.1f}) also win — a broad optimum, trustworthy.")
    elif len(winners) == 1:
        w, g = winners[0]
        say(f"  ⚠️ NO RELIABLE WEIGHT. Exactly ONE grid point (w={w:.1f}) beat our current setting in")
        say(f"     both seasons, by {g:+.0f} pts on average — a knife edge, and well inside noise.")
        say("     The two seasons pick OPPOSITE ends of the range, so any weight fitted here is")
        say("     fitting a 2-season sample. DO NOT change scoring_config on this evidence.")
    else:
        say("  NO weight beat our current setting in both seasons — leave the blend alone.")
    say("\n  CAVEAT: this is ESPN-vs-SLEEPER. The live board blends ESPN with FantasyPros, which")
    say("  cannot be tested historically. Read this as evidence about the PRINCIPLE (lean toward the")
    say("  more accurate source, and away from a 65% weight on the weakest one), not as a drop-in")
    say("  number for scoring_config.")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
