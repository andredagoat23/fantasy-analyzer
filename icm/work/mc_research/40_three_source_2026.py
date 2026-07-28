"""40 — All three sources on the ACTUAL 2026 board: how much does the mix even change?

The hard constraint, verified not assumed: there are NO historical FantasyPros projections. The
data/FantasyPros_*.csv files are 2026-only (dated Jul 6), no archive exists in the repo or its git
history, and the FP API returns 403 (key-gated). So a historical 3-way backtest is impossible —
39_'s ESPN-vs-Sleeper evidence is the most that can ever be validated against outcomes.

What CAN be answered, and it is the part that actually decides this: **on the 2026 board the user
will really draft from, how much does the weighting change anything?**

  * If the three sources broadly agree on 2026, the weight is nearly irrelevant and the correct
    action is to leave a frozen file alone.
  * If they disagree sharply, the weight matters, and 39_ tells us which direction to lean (away
    from a heavy single-source weight; ESPN is steadier, Sleeper higher-mean but 3x more volatile).

Everything is scored under the league's own scoring_config, so these are the numbers the board would
actually carry — not generic PPR.

Run:  .venv/bin/python icm/work/mc_research/40_three_source_2026.py
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
from scoring_config import PROJ_W_ESPN, PROJ_W_FP, SCORING  # noqa: E402
from utils import normalize_name  # noqa: E402

OUT = os.path.join(HERE, "results_40_three_source_2026.txt")
SL_STAT = {"pass_yds": "pass_yd", "pass_td": "pass_td", "pass_int": "pass_int",
           "rush_yds": "rush_yd", "rush_td": "rush_td",
           "rec": "rec", "rec_yds": "rec_yd", "rec_td": "rec_td"}
# (w_fp, w_espn, w_sleeper) — today's board is (0.35, 0.65, 0.00)
MIXES = [
    ("TODAY  FP.35/ESPN.65/SL.00", 0.35, 0.65, 0.00),
    ("equal thirds", 1 / 3, 1 / 3, 1 / 3),
    ("FP.33/ESPN.33/SL.34", 0.33, 0.33, 0.34),
    ("FP.25/ESPN.25/SL.50", 0.25, 0.25, 0.50),
    ("FP.40/ESPN.20/SL.40", 0.40, 0.20, 0.40),
    ("FP.50/ESPN.00/SL.50", 0.50, 0.00, 0.50),
    ("FP.35/ESPN.40/SL.25", 0.35, 0.40, 0.25),
    ("FP.00/ESPN.00/SL1.0", 0.00, 0.00, 1.00),
]

lines = []


def say(s):
    print(s)
    lines.append(s)


def score_components(df):
    t = np.zeros(len(df))
    for canon, val in SCORING.items():
        if canon in df.columns:
            t += pd.to_numeric(df[canon], errors="coerce").fillna(0).to_numpy() * val
    return t


def main():
    say("THREE SOURCES ON THE REAL 2026 BOARD — does the mix actually change anything?")
    say(f"  live weights: FP {PROJ_W_FP}, ESPN {PROJ_W_ESPN}, Sleeper 0.00 (not a source yet)")
    say("  all scored under scoring_config (base bucket), so these are the board's own units.\n")

    fp = projections._fp_components().copy()
    espn, provides = projections._espn_components()
    espn = espn.copy()
    fp["key"] = fp["full_name"].map(normalize_name)
    espn["key"] = espn["full_name"].map(normalize_name)
    fp["fp_pts"] = score_components(fp)
    espn["espn_pts"] = score_components(espn)

    sl_raw = requests.get("https://api.sleeper.app/v1/projections/nfl/regular/2026", timeout=45).json()
    players = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60).json()
    nm = {pid: p.get("full_name") for pid, p in players.items() if p.get("full_name")}
    rows = []
    for pid, d in sl_raw.items():
        n = nm.get(pid)
        if not n:
            continue
        v = sum(float(d.get(k, 0) or 0) * SCORING.get(c, 0.0) for c, k in SL_STAT.items())
        if v > 0:
            rows.append({"key": normalize_name(n), "sl_pts": v})
    sl = pd.DataFrame(rows).drop_duplicates("key")

    board = pd.read_csv(os.path.join(ROOT, "value_board.csv"))
    board["key"] = board["full_name"].map(normalize_name)
    board["position"] = board["pos_label"].str.replace(r"\d+$", "", regex=True)
    b = board[board["adp_rank"].notna() & board["position"].isin(["QB", "RB", "WR", "TE"])]
    b = b.nsmallest(180, "adp_rank")[["key", "full_name", "pos_label", "position", "adp_rank"]]

    m = (b.merge(fp[["key", "fp_pts"]], on="key", how="left")
          .merge(espn[["key", "espn_pts"]], on="key", how="left")
          .merge(sl, on="key", how="left"))
    full = m.dropna(subset=["fp_pts", "espn_pts", "sl_pts"]).reset_index(drop=True)
    say(f"  top-180 by ADP: {len(m)} players · with ALL THREE sources: {len(full)}")
    for c, lab in (("fp_pts", "FP"), ("espn_pts", "ESPN"), ("sl_pts", "Sleeper")):
        say(f"    missing {lab}: {int(m[c].isna().sum())}")

    # put the three on a common scale so a mix is a genuine mix, not a level shift
    for c in ("fp_pts", "espn_pts", "sl_pts"):
        full[c + "_s"] = full[c] * (full["fp_pts"].mean() / full[c].mean())

    say("\n" + "=" * 76)
    say("A. HOW MUCH DO THE THREE AGREE ON 2026? (Spearman among top-180 by ADP)")
    say("=" * 76)
    pairs = [("FP", "fp_pts_s", "ESPN", "espn_pts_s"), ("FP", "fp_pts_s", "Sleeper", "sl_pts_s"),
             ("ESPN", "espn_pts_s", "Sleeper", "sl_pts_s")]
    for a, ca, bb, cb in pairs:
        say(f"  {a:<8} vs {bb:<8} {full[ca].rank().corr(full[cb].rank()):>+8.3f}")
    say("  High agreement => the weight barely matters. Low => it matters a lot.")

    say("\n" + "=" * 76)
    say("B. WHAT EACH MIX DOES TO THE BOARD (vs today's FP.35/ESPN.65)")
    say("=" * 76)
    base = None
    say(f"  {'mix':<28}{'mean |rank shift|':>19}{'moved 10+':>11}{'top-40 out':>12}")
    ranks = {}
    for label, wf, we, ws in MIXES:
        v = wf * full["fp_pts_s"] + we * full["espn_pts_s"] + ws * full["sl_pts_s"]
        r = v.rank(ascending=False)
        ranks[label] = r
        if base is None:
            base = r
            say(f"  {label:<28}{'— (reference)':>19}{'':>11}{'':>12}")
            continue
        d = (r - base)
        t40_base = set(full.loc[base <= 40, "full_name"])
        t40_new = set(full.loc[r <= 40, "full_name"])
        say(f"  {label:<28}{d.abs().mean():>19.1f}{int((d.abs() >= 10).sum()):>11}"
            f"{len(t40_base - t40_new):>12}")

    say("\n" + "=" * 76)
    say("C. WHO MOVES MOST under an equal-thirds mix (the 39_-informed direction)")
    say("=" * 76)
    r_new = ranks["equal thirds"]
    full["b_rank"], full["n_rank"] = base, r_new
    full["mv"] = full["b_rank"] - full["n_rank"]           # + = rises under the new mix
    say(f"  {'player':<24}{'pos':<6}{'ADP':>6}{'today':>7}{'new':>6}{'move':>7}   FP / ESPN / SL pts")
    for r in pd.concat([full.nlargest(6, "mv"), full.nsmallest(6, "mv")]).itertuples():
        say(f"  {r.full_name:<24}{r.pos_label:<6}{r.adp_rank:>6.1f}{r.b_rank:>7.0f}{r.n_rank:>6.0f}"
            f"{r.mv:>+7.0f}   {r.fp_pts:>5.0f} /{r.espn_pts:>5.0f} /{r.sl_pts:>5.0f}")

    say("\n" + "=" * 76)
    say("D. WHERE THE SOURCES DISAGREE MOST ON 2026 (max minus min, rescaled pts)")
    say("=" * 76)
    full["spread"] = (full[["fp_pts_s", "espn_pts_s", "sl_pts_s"]].max(axis=1)
                       - full[["fp_pts_s", "espn_pts_s", "sl_pts_s"]].min(axis=1))
    say(f"  {'player':<24}{'pos':<6}{'ADP':>6}{'spread':>8}   FP / ESPN / SL pts")
    for r in full.nlargest(12, "spread").itertuples():
        say(f"  {r.full_name:<24}{r.pos_label:<6}{r.adp_rank:>6.1f}{r.spread:>8.0f}"
            f"   {r.fp_pts:>5.0f} /{r.espn_pts:>5.0f} /{r.sl_pts:>5.0f}")
    say(f"\n  median spread across the top-180: {full['spread'].median():.0f} pts "
        f"· 90th pct: {full['spread'].quantile(0.9):.0f} pts")
    say("  These are the players whose board position actually depends on the weighting.")

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
