"""23 — What has to be TRUE for a first-round pick to hit? (player-prerequisite research)

User hypothesis (Jul 28): every player carries a specific set of make-or-break PREREQUISITES, and
the useful research is per-player — "what conditions separate the boom seasons from the bust seasons
for players LIKE him." The cohort layer already gives marginal RATES + named comps; it cannot say
what had to be true. This script tests the conditions directly on the 2014-25 panel.

Population: first-round-PRICED seasons (ADP inside the top 15 overall) — the actual decision the user
faces at slot 7. Outcome = `mult` (season finish vs preseason price): HIT >= 1.0 (met/beat the
price), BUST <= 0.7 (lost the pick).

Rigor (matches this project's bar — see lessons L45/L46 + late-round-strategy):
- Every condition is measurable from PRIOR-season / static data, i.e. knowable ON DRAFT DAY.
- TRAIN 2015-2021, HOLDOUT 2022-2025. A condition only counts if it holds out of sample.
- Base rates and Ns printed for everything; conditions that FAIL are reported, not hidden.
- Multiple-testing honesty: ~12 conditions tested, so single-split "significance" is not claimed —
  the holdout + the dose-response curve are the real evidence.

Run:  .venv/bin/python icm/work/mc_research/23_r1_prerequisites.py
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_23_r1_prereqs.txt")

R1_ADP = 15          # "first round" = priced inside the top 15 overall (12-team R1 + the turn)
HIT, BUST = 1.0, 0.7
TRAIN_END = 2021     # train 2015-2021, holdout 2022-2025

lines = []


def say(s=""):
    print(s)
    lines.append(s)


NUMERIC = ["adp", "adp_pos_rank", "age", "mult", "games", "season", "draft_number", "prev_games",
           "prev_ended_early", "prev_inj_weeks_out", "prev_snap_pct", "prev_touches_pg",
           "prev_tgt_share", "prev_wopr", "prev_ppg", "prev_xfp_pg", "prev_implied_total_avg",
           "prev_n_teams", "prev_cv", "prev_pos_rank_total", "prev_targets_pg", "prev_carries_pg"]


def load():
    p = pd.read_parquet(PANEL)
    for col in NUMERIC:                     # panel stores some of these as object/str
        if col in p.columns:
            p[col] = pd.to_numeric(p[col], errors="coerce")
    p = p[(p["adp"].notna()) & (p["adp"] <= R1_ADP) & (p["season"] >= 2015)].copy()
    p = p[p["position"].isin(["RB", "WR", "TE", "QB"])]
    p["hit"] = (p["mult"] >= HIT).astype(float)
    p["bust"] = (p["mult"] <= BUST).astype(float)
    return p


def conditions(p):
    """Binary, draft-day-knowable conditions. Each is a hypothesis about what must be TRUE."""
    med = lambda s: s.median()
    c = pd.DataFrame(index=p.index)
    # --- durability / health ---
    c["durable_prev"] = p["prev_games"] >= 15
    c["no_early_end"] = p["prev_ended_early"].fillna(0) == 0
    c["light_injury_hist"] = p["prev_inj_weeks_out"].fillna(0) <= 1
    # --- age / arc ---
    c["young"] = p["age"] <= 26
    c["not_old_rb"] = ~((p["position"] == "RB") & (p["age"] >= 28))
    # --- volume / role ---
    c["high_snap"] = p["prev_snap_pct"].fillna(0) >= 0.70
    vol = p["prev_touches_pg"].where(p["position"] == "RB", p["prev_tgt_share"])
    c["elite_volume"] = vol >= vol.groupby(p["position"]).transform(med)
    c["wopr_strong"] = p["prev_wopr"].fillna(0) >= p["prev_wopr"].groupby(p["position"]).transform(med)
    # --- was last year EARNED? (opportunity vs production) ---
    ratio = p["prev_ppg"] / p["prev_xfp_pg"].replace(0, np.nan)
    c["earned_prod"] = ratio <= 1.15                      # not TD-lucky going in
    c["not_fluke_cheap"] = p["prev_xfp_pg"].notna()
    # --- situation ---
    c["good_offense"] = p["prev_implied_total_avg"] >= p["prev_implied_total_avg"].median()
    c["stayed_put"] = p["prev_n_teams"].fillna(1) <= 1
    # --- pedigree / consistency ---
    c["capital"] = p["draft_number"].fillna(999) <= 32
    c["consistent"] = p["prev_cv"] <= p["prev_cv"].groupby(p["position"]).transform(med)
    # --- price honesty: is the market paying for a REPEAT or a LEAP? ---
    c["proven_at_price"] = p["prev_pos_rank_total"].fillna(99) <= p["adp_pos_rank"].fillna(99)
    return c.astype(float)


def rate(sub, col):
    return (sub[col].mean() if len(sub) else np.nan)


def evaluate(p, c, label, cols=None):
    say(f"\n=== {label} · n={len(p)} · base HIT {p['hit'].mean():.1%} · base BUST {p['bust'].mean():.1%} ===")
    tr, ho = p["season"] <= TRAIN_END, p["season"] > TRAIN_END
    say(f"{'condition':<20}{'n_true':>7}{'HIT|T':>8}{'HIT|F':>8}{'lift':>7}   "
        f"{'ho_n':>5}{'ho_HIT|T':>9}{'ho_HIT|F':>9}{'ho_lift':>8}  verdict")
    keep = []
    for col in (cols or c.columns):
        t, f = c[col] == 1, c[col] == 0
        n_t = int(t.sum())
        if n_t < 15 or int(f.sum()) < 15:
            say(f"{col:<20}{n_t:>7}   (too few either way)")
            continue
        ht, hf = rate(p[t], "hit"), rate(p[f], "hit")
        lift = 100 * (ht - hf)
        ht2, hf2 = rate(p[t & ho], "hit"), rate(p[f & ho], "hit")
        lift2 = 100 * (ht2 - hf2) if pd.notna(ht2) and pd.notna(hf2) else np.nan
        n_ho = int((t & ho).sum())
        ok = pd.notna(lift2) and lift >= 8 and lift2 >= 5 and n_ho >= 8
        weak = pd.notna(lift2) and lift >= 8 and 0 <= lift2 < 5
        verdict = "HOLDS" if ok else ("weak" if weak else ("FAILS ho" if lift >= 8 else "no signal"))
        if ok:
            keep.append(col)
        say(f"{col:<20}{n_t:>7}{ht:>8.1%}{hf:>8.1%}{lift:>+6.1f}   {n_ho:>5}"
            f"{ht2:>9.1%}{hf2:>9.1%}{lift2:>+7.1f}  {verdict}")
    return keep


def dose(p, c, keep, label):
    """The money curve: hit rate by HOW MANY validated prerequisites a season met."""
    if not keep:
        say(f"\n[{label}] no conditions survived — no dose curve")
        return None
    k = c[keep].sum(axis=1)
    say(f"\n[{label}] DOSE-RESPONSE — prerequisites met (of {len(keep)}: {', '.join(keep)})")
    say(f"{'met':>5}{'n':>6}{'HIT':>8}{'BUST':>8}{'med mult':>10}   (holdout n / HIT)")
    ho = p["season"] > TRAIN_END
    for v in range(0, len(keep) + 1):
        m = k == v
        if m.sum() == 0:
            continue
        hh = p[m & ho]
        say(f"{v:>5}{int(m.sum()):>6}{p[m]['hit'].mean():>8.1%}{p[m]['bust'].mean():>8.1%}"
            f"{p[m]['mult'].median():>10.2f}   ({len(hh)} / "
            f"{hh['hit'].mean():.0%})" if len(hh) else
            f"{v:>5}{int(m.sum()):>6}{p[m]['hit'].mean():>8.1%}{p[m]['bust'].mean():>8.1%}"
            f"{p[m]['mult'].median():>10.2f}   (—)")
    lo, hi = k <= max(1, len(keep) - 3), k >= len(keep) - 1
    if lo.sum() >= 10 and hi.sum() >= 10:
        say(f"  SPREAD: meets most ({int(hi.sum())}) HIT {p[hi]['hit'].mean():.1%} / BUST "
            f"{p[hi]['bust'].mean():.1%}  vs  meets few ({int(lo.sum())}) HIT "
            f"{p[lo]['hit'].mean():.1%} / BUST {p[lo]['bust'].mean():.1%}")
    return k


def failure_modes(p):
    """HOW first-rounders actually fail — the denominator behind 'prerequisites'."""
    say("\n=== HOW R1 PICKS FAIL (all seasons) ===")
    b = p[p["bust"] == 1]
    say(f"busts: {len(b)} of {len(p)} ({len(b) / len(p):.1%})")
    inj = b["games"] <= 12
    say(f"  missed 5+ games (injury-driven):      {inj.mean():.1%} of busts")
    say(f"  played 15+ but underperformed:        {(b['games'] >= 15).mean():.1%} of busts")
    for pos in ("RB", "WR", "TE", "QB"):
        s = p[p["position"] == pos]
        if len(s) < 20:
            continue
        say(f"  {pos}: n={len(s):<4} HIT {s['hit'].mean():.1%}  BUST {s['bust'].mean():.1%}  "
            f"med mult {s['mult'].median():.2f}  played<13g {(s['games'] <= 12).mean():.1%}")


def main():
    p = load()
    say(f"R1-priced seasons (ADP<= {R1_ADP}, 2015-2025): n={len(p)}")
    say(f"  train {int((p['season'] <= TRAIN_END).sum())} / holdout {int((p['season'] > TRAIN_END).sum())}")
    say(f"  mult: median {p['mult'].median():.2f}  mean {p['mult'].mean():.2f}  "
        f"HIT(>= {HIT}) {p['hit'].mean():.1%}  BUST(<= {BUST}) {p['bust'].mean():.1%}")
    failure_modes(p)
    c = conditions(p)
    keep_all = evaluate(p, c, "ALL first-round picks")
    k = dose(p, c, keep_all, "ALL")

    per_pos = {}
    for pos in ("RB", "WR"):
        s = p[p["position"] == pos]
        if len(s) < 45:
            continue
        cs = conditions(s)
        kp = evaluate(s, cs, f"{pos} only")
        per_pos[pos] = kp
        dose(s, cs, kp, pos)

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")
    return keep_all, per_pos


if __name__ == "__main__":
    main()
