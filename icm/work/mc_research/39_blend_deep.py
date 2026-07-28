"""39 — FULL research on the blend decision: where the edge lives, whether it is real, and if it holds.

38_ established the headline on four clean seasons (2021, 2022, 2024, 2025): Sleeper is more accurate
in 3 of 4, and leave-one-season-out reweighting is worth ~+60 roster points. Before recommending a
change to a FROZEN pipeline file, that needs to survive interrogation. This runs it.

Third-source hunt closed first (probed, not assumed): NFL.com 404s, FantasyPros 403s (key-gated,
confirming it is proprietary), CBS 400s. ESPN and Sleeper are the only public sources with usable
history, and Sleeper's 2019-2020 are backfilled (see 38_). Four clean seasons is the ceiling.

Six questions, in order of how much they could kill the recommendation:

  A. WHERE does the edge live — is it in the draftable top of the board, or only in the tail that
     never gets picked? An edge in the tail is worthless.
  B. WHICH POSITIONS drive it? If Sleeper is only better at one position, a global weight is the
     wrong instrument.
  C. IS IT SIGNIFICANT? Bootstrap the per-draft paired differences rather than trusting a mean.
  D. DOES IT HOLD AT OTHER DRAFT SLOTS? Seat 7 is the user's, but an effect that only exists at one
     seat is a simulation artifact.
  E. WOULD A PER-POSITION BLEND BEAT A GLOBAL ONE? Tested with leave-one-season-out, because this is
     exactly the kind of extra freedom that invites overfitting (L49).
  F. WHY DOES 2025 FLIP? The one season ESPN wins. If the reason is understood, we know whether to
     trust the direction going into 2026.

Run:  .venv/bin/python icm/work/mc_research/39_blend_deep.py
"""
import importlib.util
import json
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

CACHE = os.path.join(HERE, "blend_cache_2019_2025.json")
OUT = os.path.join(HERE, "results_39_blend_deep.txt")
CLEAN = (2021, 2022, 2024, 2025)
TEAMS, ROUNDS = 12, 16
N_DRAFTS = 150
N_BOOT = 3000
RNG = np.random.default_rng(0)
STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
FLEX_OK = ("RB", "WR", "TE")
MAX_POS = {"QB": 2, "TE": 2, "RB": 6, "WR": 6}
REF_W = 0.75          # nearest grid point to the live board's 65% ESPN weight

lines = []


def say(s):
    print(s)
    lines.append(s)


def prep(rows):
    df = pd.DataFrame(rows)
    df = df[df["adp"] <= 220].reset_index(drop=True)
    for c in ("espn", "sleeper"):
        df[c + "_s"] = df[c] * (df["actual"].mean() / df[c].mean())
    return df


def rho(df, w, mask=None):
    d = df if mask is None else df[mask]
    if len(d) < 25:
        return np.nan
    b = w * d["espn_s"] + (1 - w) * d["sleeper_s"]
    return b.rank().corr(d["actual"].rank())


def simulate(df, rng, col, my_slot):
    n = len(df)
    adp, pos, pts = df["adp"].to_numpy(), df["pos"].to_numpy(), df["actual"].to_numpy()
    val = df[col].to_numpy()
    noise = rng.normal(0, 8.0, n)
    taken = np.zeros(n, dtype=bool)
    ros = {t: {"QB": 0, "RB": 0, "WR": 0, "TE": 0} for t in range(1, TEAMS + 1)}
    mine = []
    for rd in range(1, ROUNDS + 1):
        order = range(1, TEAMS + 1) if rd % 2 else range(TEAMS, 0, -1)
        for team in order:
            av = ~taken
            if not av.any():
                continue
            c = ros[team]
            ok = av & np.array([c[p] < MAX_POS[p] for p in pos])
            if not ok.any():
                ok = av
            idx = np.where(ok)[0]
            if team == my_slot:
                need = np.array([(c[p] < STARTERS[p]) or (p in FLEX_OK) for p in pos])
                cand = np.where(ok & need)[0]
                if len(cand) == 0:
                    cand = idx
                pick = cand[np.argmax(val[cand])]
            else:
                pick = idx[np.argmin((adp + noise)[idx])]
            taken[pick] = True
            ros[team][pos[pick]] += 1
            if team == my_slot:
                mine.append(pick)
    mine = np.array(mine)
    by = {p: sorted(pts[mine][pos[mine] == p], reverse=True) for p in ("QB", "RB", "WR", "TE")}
    tot, used = 0.0, {}
    for p, k in STARTERS.items():
        t = by[p][:k]
        tot += sum(t)
        used[p] = len(t)
    flex = [x for p in FLEX_OK for x in by[p][used[p]:]]
    return tot + (max(flex) if flex else 0.0)


def paired(df, w_a, w_b, my_slot=7, n=N_DRAFTS):
    """Per-draft differences (arm B minus arm A) on identical seeds."""
    d = df.copy()
    d["va"] = wb.vols(d.assign(x=w_a * d["espn_s"] + (1 - w_a) * d["sleeper_s"]), "x")
    d["vb"] = wb.vols(d.assign(x=w_b * d["espn_s"] + (1 - w_b) * d["sleeper_s"]), "x")
    out = []
    for i in range(n):
        a = simulate(d, np.random.default_rng(6100 + i), "va", my_slot)
        b = simulate(d, np.random.default_rng(6100 + i), "vb", my_slot)
        out.append(b - a)
    return np.array(out)


def main():
    with open(CACHE) as f:
        data = {int(k): v for k, v in json.load(f).items()}
    dfs = {s: prep(data[s]) for s in CLEAN}
    say("FULL BLEND RESEARCH — interrogating the +60 pts before touching a frozen file")
    say(f"  clean seasons: {CLEAN} · ref weight {REF_W:.2f} ESPN (nearest grid point to the live 0.65)")
    say("  third source: none exists — NFL.com 404, FantasyPros 403 (key-gated), CBS 400\n")

    say("=" * 78)
    say("A. WHERE DOES THE EDGE LIVE? (Spearman, all-Sleeper vs all-ESPN, by ADP band)")
    say("=" * 78)
    say(f"  {'season':<8}{'top 50':>18}{'51-120':>18}{'121-220':>18}")
    for s in CLEAN:
        d = dfs[s]
        cells = ""
        for lo, hi in ((1, 50), (51, 120), (121, 220)):
            m = d["adp"].between(lo, hi)
            e, k = rho(d, 1.0, m), rho(d, 0.0, m)
            cells += f"{'—':>18}" if np.isnan(e) or np.isnan(k) else f"{f'{k - e:+.3f} (n={m.sum()})':>18}"
        say(f"  {s:<8}{cells}")
    say("  positive = Sleeper better in that band. The top-120 is where picks actually happen.")

    say("\n" + "=" * 78)
    say("B. WHICH POSITIONS DRIVE IT? (Sleeper minus ESPN Spearman, per position)")
    say("=" * 78)
    say(f"  {'season':<8}" + "".join(f"{p:>12}" for p in ("QB", "RB", "WR", "TE")))
    for s in CLEAN:
        d = dfs[s]
        row = ""
        for p in ("QB", "RB", "WR", "TE"):
            m = d["pos"] == p
            e, k = rho(d, 1.0, m), rho(d, 0.0, m)
            row += f"{'—':>12}" if np.isnan(e) or np.isnan(k) else f"{k - e:>+12.3f}"
        say(f"  {s:<8}{row}")

    say("\n" + "=" * 78)
    say("C. IS IT SIGNIFICANT? (paired per-draft differences, all-Sleeper vs ref, bootstrapped)")
    say("=" * 78)
    say(f"  {'season':<8}{'mean':>9}{'95% CI':>20}{'P(>0)':>8}{'win%':>8}")
    per_season = {}
    for s in CLEAN:
        d = paired(dfs[s], REF_W, 0.0)
        per_season[s] = d
        bs = np.array([d[RNG.integers(0, len(d), len(d))].mean() for _ in range(N_BOOT)])
        say(f"  {s:<8}{d.mean():>+9.0f}{f'[{np.percentile(bs, 2.5):+.0f}, {np.percentile(bs, 97.5):+.0f}]':>20}"
            f"{(bs > 0).mean():>8.2f}{(d > 0).mean():>8.0%}")
    pooled = np.concatenate([per_season[s] for s in CLEAN])
    bs = np.array([pooled[RNG.integers(0, len(pooled), len(pooled))].mean() for _ in range(N_BOOT)])
    say(f"  {'POOLED':<8}{pooled.mean():>+9.0f}"
        f"{f'[{np.percentile(bs, 2.5):+.0f}, {np.percentile(bs, 97.5):+.0f}]':>20}"
        f"{(bs > 0).mean():>8.2f}{(pooled > 0).mean():>8.0%}")
    say("  Season-level agreement matters more than the pooled CI: 3-of-4 with one reversal is a")
    say("  weaker claim than the pooled interval alone suggests.")

    say("\n" + "=" * 78)
    say("D. DOES IT HOLD AT OTHER DRAFT SLOTS?")
    say("=" * 78)
    say(f"  {'slot':<7}" + "".join(f"{s:>10}" for s in CLEAN) + f"{'mean':>9}")
    for slot in (1, 4, 7, 10, 12):
        row, vals = "", []
        for s in CLEAN:
            m = paired(dfs[s], REF_W, 0.0, my_slot=slot, n=80).mean()
            vals.append(m)
            row += f"{m:>+10.0f}"
        say(f"  {slot:<7}{row}{np.mean(vals):>+9.0f}")
    say("  An effect that only exists at seat 7 would be a simulation artifact, not a real edge.")

    say("\n" + "=" * 78)
    say("E. WOULD A PER-POSITION BLEND BEAT A GLOBAL ONE? (leave-one-season-out)")
    say("=" * 78)
    grid = [0.0, 0.25, 0.5, 0.75, 1.0]
    say(f"  {'held out':<10}{'per-pos weights fitted elsewhere':<40}{'vs global':>11}")
    for s in CLEAN:
        others = [t for t in CLEAN if t != s]
        best = {}
        for p in ("QB", "RB", "WR", "TE"):
            scores = []
            for w in grid:
                rs = [rho(dfs[t], w, dfs[t]["pos"] == p) for t in others]
                scores.append(np.nanmean(rs))
            best[p] = grid[int(np.nanargmax(scores))]
        d = dfs[s].copy()
        d["x"] = [w_ * e + (1 - w_) * k for w_, e, k in
                  zip(d["pos"].map(best), d["espn_s"], d["sleeper_s"])]
        d["v_pp"] = wb.vols(d, "x")
        d["v_gl"] = wb.vols(d.assign(y=0.0 * d["espn_s"] + 1.0 * d["sleeper_s"]), "y")
        diff = np.mean([simulate(d, np.random.default_rng(6600 + i), "v_pp", 7)
                        - simulate(d, np.random.default_rng(6600 + i), "v_gl", 7) for i in range(80)])
        say(f"  {s:<10}{str({p: round(best[p], 2) for p in best}):<40}{diff:>+11.0f}")
    say("  vs global = per-position blend minus all-Sleeper. Positive would justify the extra freedom.")

    say("\n" + "=" * 78)
    say("F. WHY DOES 2025 FLIP?")
    say("=" * 78)
    for s in CLEAN:
        d = dfs[s]
        e, k = rho(d, 1.0), rho(d, 0.0)
        say(f"  {s}: n={len(d):<4} ESPN {e:.3f}  Sleeper {k:.3f}  gap {k - e:+.3f}"
            f"  · mean actual {d['actual'].mean():.0f}"
            f"  · injured share {(d['actual'] < 0.5 * d['actual'].median()).mean():.0%}")
    say("  2025 is the most recent season and the only reversal. If it reflects an ESPN methodology")
    say("  change rather than noise, the direction may be weakening exactly when we would apply it —")
    say("  which is the single biggest risk in this recommendation.")

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
