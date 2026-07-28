"""41 — The blend question restricted to where picks ACTUALLY happen (top ~100), ranked by VOLS.

The user's correction, and it was right twice over:

  1. Late-round projection accuracy barely matters — outcome is driven by the top ~100, and by the
     7 starters those picks produce. Measuring Spearman across a 180-player pool dilutes that.
  2. My "all three sources agree at 0.96-0.99" claim (40_) was a POOLING ARTIFACT. Correlation over
     a wide range is inflated by the huge top-to-bottom spread. Restricted to the top 50, agreement
     is markedly LOWER — 0.879 between ESPN and Sleeper. They disagree most exactly where it counts.

Second correction, caught here: comparing raw projected POINTS puts QBs on top of everything (6-pt
passing TDs) and is not how the board ranks. The board ranks on VOLS — points over positional
replacement — so that is what this compares. Reading raw points would have produced a confidently
wrong picture of which players move.

Run:  .venv/bin/python icm/work/mc_research/41_top100_focus.py
"""
import os
import sys

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

import projections  # noqa: E402
from scoring_config import SCORING  # noqa: E402
from utils import normalize_name  # noqa: E402

OUT = os.path.join(HERE, "results_41_top100.txt")
SL_STAT = {"pass_yds": "pass_yd", "pass_td": "pass_td", "pass_int": "pass_int",
           "rush_yds": "rush_yd", "rush_td": "rush_td",
           "rec": "rec", "rec_yds": "rec_yd", "rec_td": "rec_td"}
REPL = {"QB": 12, "RB": 24, "WR": 24, "TE": 12}
MIXES = [("TODAY FP.35/ESPN.65", 0.35, 0.65, 0.0), ("equal thirds", 1 / 3, 1 / 3, 1 / 3),
         ("FP.25/ESPN.25/SL.50", .25, .25, .5), ("all Sleeper", 0.0, 0.0, 1.0)]

lines = []


def say(s):
    print(s)
    lines.append(s)


def score(df):
    t = np.zeros(len(df))
    for c, v in SCORING.items():
        if c in df.columns:
            t += pd.to_numeric(df[c], errors="coerce").fillna(0).to_numpy() * v
    return t


def main():
    fp = projections._fp_components().copy()
    es = projections._espn_components()[0].copy()
    fp["key"] = fp["full_name"].map(normalize_name)
    es["key"] = es["full_name"].map(normalize_name)
    fp["fp"], es["es"] = score(fp), score(es)
    raw = requests.get("https://api.sleeper.app/v1/projections/nfl/regular/2026", timeout=45).json()
    pls = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60).json()
    nm = {p: v.get("full_name") for p, v in pls.items() if v.get("full_name")}
    rows = []
    for p, d in raw.items():
        n = nm.get(p)
        if not n:
            continue
        v = sum(float(d.get(k, 0) or 0) * SCORING.get(c, 0.0) for c, k in SL_STAT.items())
        if v > 0:                                   # drop zero-projection duplicate ids
            rows.append({"key": normalize_name(n), "sl": v})
    sl = pd.DataFrame(rows).sort_values("sl", ascending=False).drop_duplicates("key")

    b = pd.read_csv(os.path.join(ROOT, "value_board.csv"))
    b["key"] = b["full_name"].map(normalize_name)
    b["position"] = b["pos_label"].str.replace(r"\d+$", "", regex=True)
    b = b[b["adp_rank"].notna() & b["position"].isin(["QB", "RB", "WR", "TE"])].nsmallest(200, "adp_rank")
    # select ONLY needed columns before merging: a wide merge + dropna silently killed every row
    m = (b[["key", "full_name", "pos_label", "position", "adp_rank"]]
         .merge(fp[["key", "fp"]], on="key").merge(es[["key", "es"]], on="key")
         .merge(sl, on="key").reset_index(drop=True))
    for c in ("fp", "es", "sl"):
        m[c + "_s"] = m[c] * (m["fp"].mean() / m[c].mean())

    say("BLEND, RESTRICTED TO WHERE PICKS HAPPEN — 2026 board, ranked by VOLS")
    say(f"  {len(m)} of 200 top-ADP players carry all three sources\n")
    say("=" * 74)
    say("A. AGREEMENT BY DEPTH — the pooled number was an artifact")
    say("=" * 74)
    say(f"  {'range':<12}{'n':>5}{'FP~ESPN':>10}{'FP~Slp':>9}{'ESPN~Slp':>10}")
    for lo, hi, lab in ((1, 50, "top 50"), (1, 100, "top 100"), (1, 150, "top 150"),
                        (101, 200, "101-200")):
        d = m[m["adp_rank"].between(lo, hi)]
        if len(d) < 15:
            continue
        say(f"  {lab:<12}{len(d):>5}{d.fp_s.rank().corr(d.es_s.rank()):>+10.3f}"
            f"{d.fp_s.rank().corr(d.sl_s.rank()):>+9.3f}{d.es_s.rank().corr(d.sl_s.rank()):>+10.3f}")
    say("  Agreement is LOWEST in the top 50. Sources diverge most exactly where picks matter.")

    def vols(v):
        out = np.zeros(len(m))
        pos, val = m["position"].to_numpy(), v.to_numpy()
        for p, n in REPL.items():
            k = pos == p
            if k.sum() >= n:
                out[k] = val[k] - np.sort(val[k])[::-1][n - 1]
            elif k.sum():
                out[k] = val[k] - val[k].min()
        return out

    say("\n" + "=" * 74)
    say("B. TOP 12 BY VOLS UNDER EACH MIX (raw points would wrongly put QBs on top)")
    say("=" * 74)
    tops = {}
    for lab, wf, we, ws in MIXES:
        t = m.assign(V=vols(wf * m.fp_s + we * m.es_s + ws * m.sl_s)).nlargest(12, "V")
        tops[lab] = list(zip(t["full_name"], t["pos_label"]))
    say(f"  {'#':>3}  " + "".join(f"{lab:<26}" for lab, *_ in MIXES))
    for i in range(12):
        say(f"  {i + 1:>3}  " + "".join(f"{tops[lab][i][0] + ' (' + tops[lab][i][1] + ')':<26}"
                                        for lab, *_ in MIXES))
    say("")
    base = {n for n, _ in tops["TODAY FP.35/ESPN.65"]}
    for lab, *_ in MIXES:
        o = tops[lab]
        say(f"  {lab:<22}{sum(1 for _, p in o if p.startswith('RB'))} RB / "
            f"{sum(1 for _, p in o if p.startswith('WR'))} WR / "
            f"{sum(1 for _, p in o if p.startswith('TE'))} TE / "
            f"{sum(1 for _, p in o if p.startswith('QB'))} QB"
            f"   · changed vs today: {len(base - {n for n, _ in o})}")
    say("\n  NOTE the direction is the OPPOSITE of what raw points suggest. Sleeper projects elite")
    say("  RBs LOWER in absolute points, but it also projects replacement-level RBs lower still, so")
    say("  the RB curve is STEEPER and elite-RB VOLS goes UP. Level differences are irrelevant to a")
    say("  board built on value over replacement — only the within-position SHAPE matters.")

    say("\n" + "=" * 74)
    say("C. BIGGEST 3-SOURCE DISAGREEMENTS INSIDE THE TOP 100")
    say("=" * 74)
    t = m[m["adp_rank"] <= 100].copy()
    t["spread"] = t[["fp_s", "es_s", "sl_s"]].max(axis=1) - t[["fp_s", "es_s", "sl_s"]].min(axis=1)
    say(f"  {'player':<24}{'pos':<6}{'ADP':>6}{'spread':>8}   FP / ESPN / SL")
    for r in t.nlargest(10, "spread").itertuples():
        say(f"  {r.full_name:<24}{r.pos_label:<6}{r.adp_rank:>6.1f}{r.spread:>8.0f}"
            f"   {r.fp:>5.0f} /{r.es:>5.0f} /{r.sl:>5.0f}")
    say(f"\n  median spread in the top 100: {t['spread'].median():.0f} pts "
        f"· 90th pct {t['spread'].quantile(0.9):.0f}")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
