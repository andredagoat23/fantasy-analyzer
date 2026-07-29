"""42 — Does the UPGRADE READ actually win points? (roadmap #5, validated before shipping)

The gap is real and was measured before building: across 300 simulated slot-7 drafts (8,672
post-lineup states), an available player beat one of my STARTERS 8.1% of the time, and by >=20 VOLS
in 4.0% — roughly one or two genuine chances per draft. `_lineup_gaps` cannot see any of it, because
it treats a slot as binary filled-or-open, and once the whole lineup incl. FLEX is set `bench_sat`
empties too, so a 4th RB competes with a real starter upgrade purely on VONA.

The asymmetry is ARITHMETIC: a bench pick adds 0 to this week's starting lineup; replacing a weak
starter adds (new − old) straight into it. That is why it is worth encoding at all — unlike the
prerequisite rules (33_), which were a statistical claim and died here.

But L49 is the standing rule: measure in POINTS, on the outcome you care about, before shipping.
Paired drafts, identical seeds, only my valuation differs; scored on ACTUAL season points with an
optimal 1QB/2RB/2WR/1TE/1FLEX lineup — which is exactly the metric an upgrade should move, since
only your best 7 count.

Run:  .venv/bin/python icm/work/mc_research/42_upgrade_backtest.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

from advisor import _UPGRADE_CAP, _UPGRADE_K, _UPGRADE_MIN  # noqa: E402

CACHE = os.path.join(HERE, "blend_cache_2019_2025.json")
OUT = os.path.join(HERE, "results_42_upgrade.txt")
CLEAN = (2021, 2022, 2024, 2025)          # Sleeper's 2019-20 are backfilled (38_)
TEAMS, ROUNDS, SLOT = 12, 16, 7
N_DRAFTS = 300
START = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
FLEX_OK = ("RB", "WR", "TE")
MAXP = {"QB": 2, "TE": 2, "RB": 6, "WR": 6}
REPL = {"QB": 12, "RB": 24, "WR": 24, "TE": 12}
N_BOOT = 3000
RNG = np.random.default_rng(0)

lines = []


def say(s):
    print(s)
    lines.append(s)


def prep(rows):
    df = pd.DataFrame(rows)
    df = df[df["adp"] <= 220].reset_index(drop=True)
    # neutral 50/50 blend as "my projection" so the test isn't entangled with the blend question
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
    return df


def simulate(df, rng, use_upgrade):
    n = len(df)
    adp, pos, actual = df["adp"].to_numpy(), df["pos"].to_numpy(), df["actual"].to_numpy()
    vols = df["vols"].to_numpy()
    noise = rng.normal(0, 8.0, n)
    taken = np.zeros(n, dtype=bool)
    ros = {t: {"QB": 0, "RB": 0, "WR": 0, "TE": 0} for t in range(1, TEAMS + 1)}
    mine = []
    for rd in range(1, ROUNDS + 1):
        order = range(1, TEAMS + 1) if rd % 2 else range(TEAMS, 0, -1)
        for t in order:
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
            if t == SLOT:
                score = vols[idx].copy()
                # ROSTER-NEED GATING — without this the test is vacuous. Drafting pure
                # best-available-by-value makes a weak starter STRUCTURALLY IMPOSSIBLE (your starter
                # is by construction the best you could have taken), so the upgrade case never
                # arises: measured 0 firings in 1,361 opportunities. The real advisor deviates from
                # best-available via `_lineup_gaps` (dedicated slots first, FLEX-only and bench
                # demoted), and it is precisely that deviation that can leave a slot weakly filled.
                cnt0 = {p: 0 for p in START}
                for i in mine:
                    if pos[i] in cnt0:
                        cnt0[pos[i]] += 1
                ded_open = {p for p in START if cnt0[p] < START[p]}
                flex_filled = sum(max(0, cnt0[p] - START[p]) for p in FLEX_OK) >= 1
                for j, gi in enumerate(idx):
                    p = pos[gi]
                    if p in ded_open:
                        continue                      # fills a dedicated slot — full credit
                    if p in FLEX_OK and not flex_filled:
                        score[j] -= 15.0              # FLEX-only, mirrors _FLEX_MARGIN
                    elif ded_open:
                        score[j] -= 30.0              # bench while a starter is open (bench_sat)
                if use_upgrade and mine:
                    # weakest STARTER at each position whose dedicated slots are full (greedy fill)
                    cnt, starters = {p: 0 for p in START}, {p: [] for p in START}
                    for i in sorted(mine, key=lambda j: -vols[j]):
                        p = pos[i]
                        if cnt[p] < START[p]:
                            starters[p].append(i)
                            cnt[p] += 1
                    floor = {p: min(vols[s] for s in starters[p])
                             for p in START if cnt[p] >= START[p] and starters[p]}
                    for j, gi in enumerate(idx):
                        f = floor.get(pos[gi])
                        if f is None:
                            continue
                        gain = vols[gi] - f
                        if gain >= _UPGRADE_MIN:
                            score[j] += min(gain * _UPGRADE_K, _UPGRADE_CAP)
                pick = idx[int(np.argmax(score))]
            else:
                pick = idx[int(np.argmin((adp + noise)[idx]))]
            taken[pick] = True
            ros[t][pos[pick]] += 1
            if t == SLOT:
                mine.append(pick)
    mine = np.array(mine)
    by = {p: sorted(actual[mine][pos[mine] == p], reverse=True) for p in ("QB", "RB", "WR", "TE")}
    tot, used = 0.0, {}
    for p, k in START.items():
        t_ = by[p][:k]
        tot += sum(t_)
        used[p] = len(t_)
    flex = [x for p in FLEX_OK for x in by[p][used[p]:]]
    return tot + (max(flex) if flex else 0.0)


def main():
    with open(CACHE) as f:
        data = {int(k): v for k, v in json.load(f).items()}
    say("UPGRADE READ — does it win points? (paired drafts, actual season scoring)")
    say(f"  seat {SLOT} of {TEAMS}, {ROUNDS} rounds · {N_DRAFTS} PAIRED drafts/season")
    say(f"  knobs: min gain {_UPGRADE_MIN} VOLS · nudge {_UPGRADE_K}x gain · cap {_UPGRADE_CAP}\n")
    say(f"  {'season':<9}{'baseline':>10}{'upgrade':>10}{'diff':>9}{'win%':>8}{'n':>7}")
    allд = []
    for s in CLEAN:
        df = prep(data[s])
        d = np.array([simulate(df, np.random.default_rng(8800 + i), True)
                      - simulate(df, np.random.default_rng(8800 + i), False)
                      for i in range(N_DRAFTS)])
        base = np.mean([simulate(df, np.random.default_rng(8800 + i), False) for i in range(60)])
        allд.append(d)
        say(f"  {s:<9}{base:>10.0f}{base + d.mean():>10.0f}{d.mean():>+9.1f}"
            f"{(d > 0).mean():>8.0%}{len(df):>7}")
    D = np.concatenate(allд)
    bs = np.array([D[RNG.integers(0, len(D), len(D))].mean() for _ in range(N_BOOT)])
    say(f"\n  POOLED n={len(D)}: mean {D.mean():+.1f} pts · 95% CI "
        f"[{np.percentile(bs, 2.5):+.1f}, {np.percentile(bs, 97.5):+.1f}] · P(>0) {(bs > 0).mean():.2f}")
    say(f"  wins {(D > 0).mean():.1%} · loses {(D < 0).mean():.1%} · identical {(D == 0).mean():.1%}")
    pos_seasons = sum(1 for d in allд if d.mean() > 0)
    say(f"  helped in {pos_seasons}/{len(allд)} seasons")
    say("\n  VERDICT: " + (
        f"SHIP — {D.mean():+.0f} pts, {pos_seasons}/{len(allд)} seasons, P(>0)={(bs > 0).mean():.2f}."
        if D.mean() > 5 and pos_seasons >= 3 and (bs > 0).mean() >= 0.9 else
        f"DO NOT SHIP — {D.mean():+.0f} pts, helping in only {pos_seasons}/{len(allд)} seasons "
        f"(P(>0)={(bs > 0).mean():.2f}). Same bar that killed 33_ and 35_."))
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
