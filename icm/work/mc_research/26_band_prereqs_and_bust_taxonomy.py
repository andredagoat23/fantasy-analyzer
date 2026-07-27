"""26 — How does the make-or-break condition CHANGE by round? (bust taxonomy + per-band prereqs)

23_/24_ answered round 1: picks fail because they get hurt, and availability is near-unforecastable.
But at slot 7 only ONE of the user's picks is a first-rounder. This script asks whether the failure
mode — and therefore the prerequisite — shifts as you move down the board.

Two deep cuts:

**A. BUST TAXONOMY.** Every bust is classified by HOW it failed, using in-season data:
   - INJURY      — played <= 12 games.
   - ROLE LOSS   — played 13+ but his usage share COLLAPSED vs the prior year (< 75% of it).
                   RB/QB measured on touches/attempts per game, WR/TE on target share.
   - INEFFICIENT — played 13+, kept the role, and still missed his price. He had the job and the job
                   wasn't enough (or he was bad).
   The mix of these three across round bands is the real answer to "what makes or breaks a season,"
   because each one implies a DIFFERENT prerequisite to screen for.

**B. PER-BAND PREREQUISITES**, carrying 25_'s stress discipline forward so nothing gets over-claimed:
   each condition is reported with a bootstrap P(lift>0) and a 9-setting sensitivity grid
   (HIT threshold x band-edge jitter). Verdicts use the same strict rules as 25_.

Bands are ADP-based: R1 1-15, R2-3 16-40, R4-6 41-75, R7-10 76-125.

Run:  .venv/bin/python icm/work/mc_research/26_band_prereqs_and_bust_taxonomy.py
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_26_bands.txt")

NUM = ["adp", "adp_pos_rank", "age", "mult", "games", "season", "draft_number", "prev_games",
       "prev_snap_pct", "prev_touches_pg", "prev_tgt_share", "prev_wopr", "prev_ppg", "prev_xfp_pg",
       "prev_implied_total_avg", "prev_cv", "prev_pos_rank_total", "prev_total_touches",
       "touches_pg", "tgt_share", "attempts_pg", "prev_attempts_pg", "prev_inj_weeks_out"]

BANDS = [(1, 15, "R1 (ADP 1-15)"), (16, 40, "R2-3 (ADP 16-40)"),
         (41, 75, "R4-6 (ADP 41-75)"), (76, 125, "R7-10 (ADP 76-125)")]
GRID_HIT = [0.9, 1.0, 1.1]
JITTER = [0.75, 1.0, 1.25]        # band-edge stretch
N_BOOT = 1500
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
    p = p[(p["adp"].notna()) & (p["season"] >= 2015)
          & p["position"].isin(["RB", "WR", "TE", "QB"])].copy()
    # usage now vs usage last year — the ROLE LOSS test
    now = p["tgt_share"].copy()
    prev = p["prev_tgt_share"].copy()
    is_rb = p["position"] == "RB"
    is_qb = p["position"] == "QB"
    now[is_rb], prev[is_rb] = p.loc[is_rb, "touches_pg"], p.loc[is_rb, "prev_touches_pg"]
    now[is_qb], prev[is_qb] = p.loc[is_qb, "attempts_pg"], p.loc[is_qb, "prev_attempts_pg"]
    p["_use_now"], p["_use_prev"] = now, prev
    p["_use_ratio"] = np.where(prev.fillna(0) > 0, now / prev.replace(0, np.nan), np.nan)
    return p


def conditions(p):
    med = lambda s: s.median()
    c = pd.DataFrame(index=p.index)
    ratio = p["prev_ppg"] / p["prev_xfp_pg"].replace(0, np.nan)
    c["earned_prod"] = ratio <= 1.15
    c["capital"] = p["draft_number"].fillna(999) <= 32
    c["capital_top64"] = p["draft_number"].fillna(999) <= 64
    c["wopr_strong"] = p["prev_wopr"].fillna(0) >= p["prev_wopr"].groupby(p["position"]).transform(med)
    c["proven_at_price"] = p["prev_pos_rank_total"].fillna(99) <= p["adp_pos_rank"].fillna(99)
    c["had_a_role"] = p["prev_snap_pct"].fillna(0) >= 0.50
    c["durable_prev"] = p["prev_games"] >= 15
    c["young_capital"] = (p["age"] <= 25) & (p["draft_number"].fillna(999) <= 64)
    c["good_offense"] = p["prev_implied_total_avg"] >= p["prev_implied_total_avg"].median()
    c["light_workload"] = p["prev_total_touches"] < p["prev_total_touches"].median()
    return c.astype(float)


def lift(hit, cond):
    t, f = cond == 1, cond == 0
    if t.sum() < 10 or f.sum() < 10:
        return np.nan
    return 100.0 * (hit[t].mean() - hit[f].mean())


def boot_p(hit, cond):
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
    return float((out > 0).mean()) if len(out) >= 100 else np.nan


def taxonomy(sub, label):
    b = sub[sub["mult"] <= 0.7]
    if len(b) < 8:
        say(f"  {label}: only {len(b)} busts — too few to classify")
        return
    inj = b["games"] <= 12
    rest = b[~inj]
    roleloss = rest["_use_ratio"] < 0.75
    known = rest["_use_ratio"].notna()
    ineff = known & ~roleloss
    say(f"  {label}: {len(b)} busts of {len(sub)} ({len(b) / len(sub):.0%})  ->  "
        f"INJURY {inj.mean():.0%} · ROLE LOSS {roleloss.sum() / len(b):.0%} · "
        f"INEFFICIENT {ineff.sum() / len(b):.0%}"
        + (f" · unknown usage {(~known).sum() / len(b):.0%}" if (~known).sum() else ""))


def hit_usage(sub, label):
    h = sub[sub["mult"] >= 1.3]                      # the real winners
    k = h["_use_ratio"].notna()
    if k.sum() < 8:
        say(f"  {label}: too few boom seasons with usage data")
        return
    grew = h.loc[k, "_use_ratio"] > 1.25
    say(f"  {label}: {int(k.sum())} boom seasons -> usage GREW 25%+ in {grew.mean():.0%} "
        f"(median usage ratio {h.loc[k, '_use_ratio'].median():.2f}x)")


def band_conditions(p, lo, hi, label):
    sub = p[(p["adp"] >= lo) & (p["adp"] <= hi)].copy()
    say(f"\n--- {label} · n={len(sub)} · HIT {(sub['mult'] >= 1.0).mean():.1%} ---")
    if len(sub) < 60:
        say("  too small")
        return
    cs = conditions(sub)
    hit = (sub["mult"] >= 1.0).astype(float)
    say(f"{'condition':<18}{'lift':>7}{'P(>0)':>8}{'grid':>7}  verdict")
    for col in cs.columns:
        l0 = lift(hit, cs[col])
        if np.isnan(l0):
            continue
        pgt = boot_p(hit, cs[col])
        surv = tot = 0
        for h_ in GRID_HIT:
            for j in JITTER:
                mid = (lo + hi) / 2
                w = (hi - lo) / 2 * j
                s2 = p[(p["adp"] >= mid - w) & (p["adp"] <= mid + w)]
                if len(s2) < 50:
                    continue
                lv = lift((s2["mult"] >= h_).astype(float), conditions(s2)[col])
                if np.isnan(lv):
                    continue
                tot += 1
                surv += int(lv >= 5.0)
        v = ("ROBUST" if surv >= tot * 0.75 and pgt >= 0.90 else
             "shaky" if surv >= tot * 0.5 or pgt >= 0.80 else "DEAD")
        if v != "DEAD":
            say(f"{col:<18}{l0:>+6.1f}{pgt:>8.2f}{f'{surv}/{tot}':>7}  {v}")
    say("  (only non-DEAD conditions listed)")


def main():
    p = load()
    say(f"panel: {len(p)} priced seasons 2015-2025 · bands by ADP\n")
    say("=" * 84)
    say("A. BUST TAXONOMY — HOW picks fail, by round band")
    say("=" * 84)
    for lo, hi, lab in BANDS:
        taxonomy(p[(p["adp"] >= lo) & (p["adp"] <= hi)], lab)
    say("\nby position (all bands):")
    for pos in ("RB", "WR", "TE", "QB"):
        taxonomy(p[p["position"] == pos], f"{pos:<3}")

    say("\n" + "=" * 84)
    say("B. WHAT THE WINNERS DID — usage growth in boom seasons (mult >= 1.3)")
    say("=" * 84)
    for lo, hi, lab in BANDS:
        hit_usage(p[(p["adp"] >= lo) & (p["adp"] <= hi)], lab)

    say("\n" + "=" * 84)
    say("C. PREREQUISITES BY BAND (stress-tested: bootstrap P + 9-setting grid)")
    say("=" * 84)
    for lo, hi, lab in BANDS:
        band_conditions(p, lo, hi, lab)

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
