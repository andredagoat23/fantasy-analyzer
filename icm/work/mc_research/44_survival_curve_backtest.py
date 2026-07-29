"""44 — Does the MEASURED survival curve actually draft better than the constant one?

43_ showed `advisor._survival_prob`'s single logistic scale (7.0) is wrong nearly everywhere: the
measured scale runs 1.8 at the top of the board to 17.9 late, and 7.0 is only right around ADP 25-40.
The model gave an ADP-2 player a 4.1% chance of lasting to pick 24 when reality is 0.5%, which
inflated `best_wait` and pushed VONA negative at ~ADP 12 with the next pick at #24 (the user's catch).

A more CORRECT input does not automatically draft better, so this measures it in points — the same
bar that killed 33_, 35_ and 42_.

Two things make this sim more honest than the earlier ones:

  * **My picks are made by VONA**, not raw VOLS. VONA is what the change actually affects; drafting
    by VOLS would make the whole test vacuous (that mistake is what 42_ ran into).
  * **Opponent noise uses the MEASURED dispersion too.** Earlier sims used a flat sd of 8 picks
    everywhere, which we now know is wrong at both ends. Testing a survival-curve fix against an
    unrealistic draft flow would prove nothing.

Run across FIVE draft slots, because the user's real slot is not yet known and the bug's severity
depends on it: at slot 1 the gap to your next pick is 22 picks, at the turn it is 1-2.

Run:  .venv/bin/python icm/work/mc_research/44_survival_curve_backtest.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

import advisor  # noqa: E402

CACHE = os.path.join(HERE, "blend_cache_2019_2025.json")
OUT = os.path.join(HERE, "results_44_survival_backtest.txt")
CLEAN = (2021, 2022, 2024, 2025)
TEAMS, ROUNDS = 12, 16
SLOTS = (1, 4, 7, 10, 12)
N_DRAFTS = 100
START = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
FLEX_OK = ("RB", "WR", "TE")
MAXP = {"QB": 2, "TE": 2, "RB": 6, "WR": 6}
REPL = {"QB": 12, "RB": 24, "WR": 24, "TE": 12}
# measured sd of (actual pick - ADP), from 43_ — used for OPPONENT behaviour
_SD_ADP = [3.5, 9.5, 18.5, 32.5, 50.5, 75.5, 110.5, 165.5]
_SD = [3.3, 5.1, 8.3, 12.5, 15.9, 18.8, 27.3, 32.5]

lines = []


def say(s):
    print(s)
    lines.append(s)


def prep(rows):
    df = pd.DataFrame(rows)
    df = df[df["adp"] <= 220].reset_index(drop=True)
    for c in ("espn", "sleeper"):
        df[c + "_s"] = df[c] * (df["actual"].mean() / df[c].mean())
    df["proj"] = 0.5 * df["espn_s"] + 0.5 * df["sleeper_s"]
    v = np.zeros(len(df))
    pos, val = df["pos"].to_numpy(), df["proj"].to_numpy()
    for p, n in REPL.items():
        k = pos == p
        if k.sum() >= n:
            v[k] = val[k] - np.sort(val[k])[::-1][n - 1]
        elif k.sum():
            v[k] = val[k] - val[k].min()
    df["vols"] = v
    df["position"] = df["pos"]
    df["adp_rank"] = df["adp"]
    df["sd"] = np.interp(df["adp"], _SD_ADP, _SD)
    return df


def my_picks(slot):
    return [((r - 1) * TEAMS + slot) if r % 2 else (r * TEAMS - slot + 1)
            for r in range(1, ROUNDS + 1)]


def simulate(df, rng, slot, measured):
    advisor.USE_MEASURED_SCALE = measured
    n = len(df)
    pos, actual, adp = df["position"].to_numpy(), df["actual"].to_numpy(), df["adp"].to_numpy()
    noise = rng.normal(0, 1, n) * df["sd"].to_numpy()      # per-player MEASURED dispersion
    order_key = adp + noise
    taken = np.zeros(n, dtype=bool)
    ros = {t: {"QB": 0, "RB": 0, "WR": 0, "TE": 0} for t in range(1, TEAMS + 1)}
    mine, mypk = [], my_picks(slot)
    overall = 0
    for rd in range(1, ROUNDS + 1):
        seats = range(1, TEAMS + 1) if rd % 2 else range(TEAMS, 0, -1)
        for t in seats:
            overall += 1
            av = ~taken
            if not av.any():
                continue
            c = ros[t]
            ok = av & np.array([c[p] < MAXP[p] for p in pos])
            if not ok.any():
                ok = av
            idx = np.where(ok)[0]
            if len(idx) == 0:
                continue
            if t == slot:
                nxt = next((p for p in mypk if p > overall), None)
                sub = df.iloc[idx]
                if nxt:
                    scored = advisor.add_vona(sub.copy(), nxt)["vona"].to_numpy().astype(float).copy()
                else:
                    scored = sub["vols"].to_numpy().astype(float).copy()
                # roster-need gating, mirroring _lineup_gaps
                cnt0 = {p: 0 for p in START}
                for i in mine:
                    if pos[i] in cnt0:
                        cnt0[pos[i]] += 1
                ded_open = {p for p in START if cnt0[p] < START[p]}
                flex_filled = sum(max(0, cnt0[p] - START[p]) for p in FLEX_OK) >= 1
                for j, gi in enumerate(idx):
                    p = pos[gi]
                    if p in ded_open:
                        continue
                    if p in FLEX_OK and not flex_filled:
                        scored[j] -= 15.0
                    elif ded_open:
                        scored[j] -= 30.0
                pick = idx[int(np.argmax(scored))]
            else:
                pick = idx[int(np.argmin(order_key[idx]))]
            taken[pick] = True
            ros[t][pos[pick]] += 1
            if t == slot:
                mine.append(pick)
    mine = np.array(mine)
    by = {p: sorted(actual[mine][pos[mine] == p], reverse=True) for p in ("QB", "RB", "WR", "TE")}
    tot, used = 0.0, {}
    for p, k in START.items():
        tk = by[p][:k]
        tot += sum(tk)
        used[p] = len(tk)
    flex = [x for p in FLEX_OK for x in by[p][used[p]:]]
    return tot + (max(flex) if flex else 0.0)


def main():
    with open(CACHE) as f:
        data = {int(k): v for k, v in json.load(f).items()}
    dfs = {s: prep(data[s]) for s in CLEAN}
    say("MEASURED SURVIVAL CURVE vs the constant 7.0 — paired drafts, actual season scoring")
    say(f"  my picks made by VONA · opponents use MEASURED ADP dispersion · {N_DRAFTS} paired "
        f"drafts per slot per season\n")
    say(f"  {'slot':<6}" + "".join(f"{s:>10}" for s in CLEAN) + f"{'mean':>9}{'win%':>8}")
    allrows = []
    for slot in SLOTS:
        row, wins, cells = [], [], ""
        for s in CLEAN:
            d = np.array([simulate(dfs[s], np.random.default_rng(3300 + i), slot, True)
                          - simulate(dfs[s], np.random.default_rng(3300 + i), slot, False)
                          for i in range(N_DRAFTS)])
            row.append(d.mean())
            wins.append((d > 0).mean())
            cells += f"{d.mean():>+10.0f}"
            allrows.append(d)
        say(f"  {slot:<6}{cells}{np.mean(row):>+9.0f}{np.mean(wins):>8.0%}")
    D = np.concatenate(allrows)
    rng = np.random.default_rng(0)
    bs = np.array([D[rng.integers(0, len(D), len(D))].mean() for _ in range(3000)])
    say(f"\n  POOLED n={len(D)}: mean {D.mean():+.1f} pts · 95% CI "
        f"[{np.percentile(bs, 2.5):+.1f}, {np.percentile(bs, 97.5):+.1f}] · P(>0) {(bs > 0).mean():.2f}")
    say(f"  wins {(D > 0).mean():.1%} · loses {(D < 0).mean():.1%} · identical {(D == 0).mean():.1%}")
    say("\n  VERDICT: " + (
        f"SHIP — {D.mean():+.0f} pts, P(>0)={(bs > 0).mean():.2f}. A correctness fix that also wins."
        if D.mean() > 5 and (bs > 0).mean() >= 0.9 else
        f"the curve is measurably more CORRECT but worth {D.mean():+.0f} pts "
        f"(P(>0)={(bs > 0).mean():.2f}) — decide on correctness, not points."))
    advisor.USE_MEASURED_SCALE = True
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
