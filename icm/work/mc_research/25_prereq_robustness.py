"""25 — Do the R1 prerequisites SURVIVE stress-testing? (sensitivity grid + bootstrap)

23_ found four surviving conditions on one train/holdout split. That is exactly the setup where a
lucky threshold choice can manufacture a result, and ~15 conditions x 3 populations were tested, so
some survivor is likely chance. This script attacks the findings on purpose:

1. **Sensitivity grid** — recompute every condition's lift across 12 settings: what counts as "first
   round" (top 12 / 15 / 20 / 24) x what counts as a HIT (mult >= 0.9 / 1.0 / 1.1). A real effect
   should not care much where we draw those lines. Reported as "survives N/12".
2. **Bootstrap** — resample the population 2,000x (fixed seed) and report the 95% interval on the
   lift plus P(lift > 0). With n this small, a point estimate alone is not evidence.
3. Conditions that FAILED in 23_ are re-tested too, to confirm they are actually dead rather than
   just unlucky at one setting.

Verdict rules (deliberately strict): ROBUST = survives >= 9/12 settings AND P(lift>0) >= 0.90.
SHAKY = survives >= 6/12 or P >= 0.80. DEAD = neither.

Run:  .venv/bin/python icm/work/mc_research/25_prereq_robustness.py
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_25_robustness.txt")

NUM = ["adp", "adp_pos_rank", "age", "mult", "games", "season", "draft_number", "prev_games",
       "prev_ended_early", "prev_inj_weeks_out", "prev_snap_pct", "prev_touches_pg", "prev_weight",
       "prev_tgt_share", "prev_wopr", "prev_ppg", "prev_xfp_pg", "prev_implied_total_avg",
       "prev_n_teams", "prev_cv", "prev_pos_rank_total", "prev_total_touches"]

GRID_ADP = [12, 15, 20, 24]
GRID_HIT = [0.9, 1.0, 1.1]
N_BOOT = 2000
RNG = np.random.default_rng(0)

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def load():
    p = pd.read_parquet(PANEL)
    for c in NUM:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")
    return p[(p["adp"].notna()) & (p["season"] >= 2015)
             & p["position"].isin(["RB", "WR", "TE", "QB"])].copy()


def conditions(p):
    """Same definitions as 23_, kept in sync deliberately (standalone script, no cross-import)."""
    med = lambda s: s.median()
    c = pd.DataFrame(index=p.index)
    ratio = p["prev_ppg"] / p["prev_xfp_pg"].replace(0, np.nan)
    c["earned_prod"] = ratio <= 1.15
    c["capital"] = p["draft_number"].fillna(999) <= 32
    c["wopr_strong"] = p["prev_wopr"].fillna(0) >= p["prev_wopr"].groupby(p["position"]).transform(med)
    c["proven_at_price"] = p["prev_pos_rank_total"].fillna(99) <= p["adp_pos_rank"].fillna(99)
    # re-test the notable FAILURES from 23_ to confirm they're dead, not just unlucky once
    c["durable_prev"] = p["prev_games"] >= 15
    c["young"] = p["age"] <= 26
    vol = p["prev_touches_pg"].where(p["position"] == "RB", p["prev_tgt_share"])
    c["elite_volume"] = vol >= vol.groupby(p["position"]).transform(med)
    c["consistent"] = p["prev_cv"] <= p["prev_cv"].groupby(p["position"]).transform(med)
    c["good_offense"] = p["prev_implied_total_avg"] >= p["prev_implied_total_avg"].median()
    c["light_workload"] = p["prev_total_touches"] < p["prev_total_touches"].median()
    return c.astype(float)


def lift(hit, cond):
    t, f = cond == 1, cond == 0
    if t.sum() < 10 or f.sum() < 10:
        return np.nan
    return 100.0 * (hit[t].mean() - hit[f].mean())


def boot(hit, cond):
    """Bootstrap the lift. Returns (lo, hi, P(lift>0))."""
    h, c = hit.to_numpy(), cond.to_numpy()
    n = len(h)
    out = np.empty(N_BOOT)
    for i in range(N_BOOT):
        idx = RNG.integers(0, n, n)
        hh, cc = h[idx], c[idx]
        t, f = cc == 1, cc == 0
        out[i] = (100.0 * (hh[t].mean() - hh[f].mean())
                  if t.sum() >= 5 and f.sum() >= 5 else np.nan)
    out = out[~np.isnan(out)]
    if len(out) < 100:
        return np.nan, np.nan, np.nan
    return np.percentile(out, 2.5), np.percentile(out, 97.5), float((out > 0).mean())


def run(p, pos_label, pos_filter):
    say(f"\n{'=' * 88}\n{pos_label}\n{'=' * 88}")
    base = p[pos_filter(p) & (p["adp"] <= 15)].copy()
    if len(base) < 40:
        say(f"  n={len(base)} — too small, skipped")
        return
    cb = conditions(base)
    hit_base = (base["mult"] >= 1.0).astype(float)
    say(f"base population n={len(base)} · HIT rate {hit_base.mean():.1%}")
    say(f"\n{'condition':<18}{'lift@base':>10}{'boot 95% CI':>20}{'P(>0)':>8}{'grid':>7}  verdict")
    for col in cb.columns:
        l0 = lift(hit_base, cb[col])
        if np.isnan(l0):
            say(f"{col:<18}   (too few either way at base)")
            continue
        lo, hi, pgt = boot(hit_base, cb[col])
        survives = 0
        total = 0
        for cap in GRID_ADP:
            for h in GRID_HIT:
                sub = p[pos_filter(p) & (p["adp"] <= cap)].copy()
                if len(sub) < 40:
                    continue
                cs = conditions(sub)
                lv = lift((sub["mult"] >= h).astype(float), cs[col])
                if np.isnan(lv):
                    continue
                total += 1
                survives += int(lv >= 5.0)
        v = ("ROBUST" if survives >= 9 and pgt >= 0.90 else
             "shaky" if survives >= 6 or pgt >= 0.80 else "DEAD")
        say(f"{col:<18}{l0:>+9.1f}{f'[{lo:+.1f}, {hi:+.1f}]':>20}{pgt:>8.2f}"
            f"{f'{survives}/{total}':>7}  {v}")


def main():
    p = load()
    say(f"panel: {len(p)} priced seasons 2015-2025 (all ADP), "
        f"{int((p['adp'] <= 15).sum())} inside the top 15")
    say(f"grid = ADP cap {GRID_ADP} x HIT threshold {GRID_HIT} · bootstrap {N_BOOT} resamples (seed 0)")
    run(p, "ALL first-round picks", lambda d: d["position"].isin(["RB", "WR", "TE", "QB"]))
    run(p, "RB only", lambda d: d["position"] == "RB")
    run(p, "WR only", lambda d: d["position"] == "WR")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
