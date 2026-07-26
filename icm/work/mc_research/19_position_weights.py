"""POSITION-BY-POSITION composite-weight backtest — is a per-position blend better than one global set?

Reuses the cached 13-season table from 18 (real FFC ADP + real finishes + prior-year-proxied value
signals). For each of QB/RB/WR/TE separately: LEAVE-ONE-SEASON-OUT cross-validated optimization of the
5 weights, scored by WITHIN-POSITION Spearman(composite order, actual finish) per season. Compares, per
position: ADP-only vs the global L45 weights vs a position-tuned set — and reports whether the tuned
weights are STABLE across folds (small samples -> watch for noise, esp. QB/TE).

Caveats (same as 18) + one more: in this proxy the QB "role" signal == QB value (both are prior-year
points), so QB's value/role weights aren't separately identifiable — read them as one bucket.

Run:  .venv/bin/python icm/work/mc_research/19_position_weights.py   (instant; uses 18's cache)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import numpy as np
import pandas as pd

np.random.seed(0)
HERE = os.path.dirname(os.path.abspath(__file__))
bt = pd.read_csv(os.path.join(HERE, "18_bt_cache.csv"))
SIGS = ["value", "adp", "ceiling", "floor", "role"]
GLOBAL_L45 = [0.32, 0.19, 0.25, 0.15, 0.09]     # the current (L45) global weights, 5-signal
bt["ceiling"] = bt["wk_p90"]; bt["floor"] = bt["wk_p10"]
# rank WITHIN (season, position) so each position is scored on its own pool
for s in SIGS:
    bt[s + "_rk"] = bt.groupby(["season", "position"])[s].rank(ascending=(s == "adp"), method="min")
ALL = sorted(bt.season.unique())


def score(sub, weights, seasons):
    w = dict(zip(SIGS, weights))
    cors = []
    for y in seasons:
        g = sub[sub.season == y]
        if len(g) < 5:
            continue
        comp = sum(w[s] * g[s + "_rk"] for s in SIGS)
        cors.append(comp.rank().corr(g["finish"].rank()) * -1)
    return float(np.nanmean(cors)) if cors else float("nan")


def optimize(sub, seasons, n=4000):
    best, bw = -9, None
    for _ in range(n):
        w = np.random.dirichlet(np.ones(5))
        sc = score(sub, w, seasons)
        if sc > best:
            best, bw = sc, w
    return bw


print(f"{'pos':4}{'n/season':>9}{'ADP-only':>10}{'global L45':>12}{'pos-tuned(OOS)':>16}   position-tuned weights (LOSO mean±sd)  [V/mkt/ceil/floor/role]")
for pos in ["QB", "RB", "WR", "TE"]:
    sub = bt[bt.position == pos]
    npg = int(sub.groupby("season").size().mean())
    adp = score(sub, [0, 1, 0, 0, 0], ALL)
    glob = score(sub, GLOBAL_L45, ALL)
    # LOSO: tune on N-1 seasons, score held-out; collect fold weights
    oos, fw = [], []
    for y in ALL:
        w = optimize(sub, [s for s in ALL if s != y], n=2500)
        oos.append(score(sub, w, [y]))
        fw.append(w)
    fw = np.array(fw)
    wtxt = " ".join(f"{fw[:, i].mean():.2f}±{fw[:, i].std():.2f}" for i in range(5))
    print(f"{pos:4}{npg:>9}{adp:>10.3f}{glob:>12.3f}{np.nanmean(oos):>16.3f}   {wtxt}")

print("\n(read: pos-tuned(OOS) vs global L45 = the honest, generalizable gain from going per-position.")
print(" high ±sd on a weight = that position's sample can't pin it down = don't trust that knob.)")
