"""Regression tests for the cohort MEDIAN + TRIMMED-MEAN skew read (L29).

Why it exists: fantasy outcomes are right-skewed, so the median alone hides the boom tail — across the
board mean > median for 61% of players and 30% flip their "beats his price?" verdict. But the RAW mean
is unusable (mult = finish/price, so a cheap backup QB who starts a few games explodes it: Tyrod Taylor
median 0.69x -> mean 2.01x). The TRIMMED mean (drop 2 best + 2 worst of 15) keeps the tail and kills the
blow-ups. The advisor now shows med + trimmed-mean, and flags TAIL-DRIVEN only when the two straddle
1.0x — a real verdict flip, not a tuned cutoff.

Run:  .venv/bin/python tests/test_cohort_skew.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

import advisor

passed = 0


def check(label, cond):
    global passed
    assert cond, f"FAIL: {label}"
    passed += 1
    print(f"  ok  {label}")


# ---- the trimming rule itself: drop the 2 best and 2 worst of 15 ----
mults = pd.Series([0.28, 0.59, 0.74, 0.74, 0.76, 0.81, 0.86, 0.91, 0.97, 1.19, 1.31, 1.33, 1.52, 1.53, 1.60])
raw_mean = mults.mean()
trimmed = mults.sort_values().iloc[2:-2].mean()
check("median is the 8th of 15 (JSN's real 0.91x)", abs(mults.median() - 0.91) < 1e-9)
check("trimmed mean drops 2 high + 2 low (11 remain)", len(mults.sort_values().iloc[2:-2]) == 11)
check("trimmed lifts well above the median (it captures the tail the median hides)",
      trimmed > mults.median() + 0.05)
# NOTE: trimmed can exceed the raw mean here — dropping the two LOW outliers (0.28, 0.59) removes more
# downward pull than dropping the two highs. Both land ~1.01 for JSN; the point is both clear 1.0x.
check("trimmed and raw mean agree closely when there is no blow-up comp",
      abs(trimmed - raw_mean) < 0.05)

# a blow-up outlier (the Tyrod Taylor shape) is neutralised by trimming
blow = pd.Series([0.2, 0.4, 0.5, 0.6, 0.7, 0.7, 0.8, 0.9, 0.9, 1.0, 1.1, 1.2, 1.4, 6.0, 8.0])
check("raw mean is wrecked by extreme comps", blow.mean() > 1.6)
check("trimmed mean resists them", blow.sort_values().iloc[2:-2].mean() < 1.0)

# ---- the advisor surfaces it, and flags TAIL-DRIVEN only on the 1.0x crossing ----
FAKE = {
    "tail guy": {"cohort_desc": "WR yr-4", "cohort_boom": 0.27, "cohort_bust": 0.19,
                 "cohort_med": 0.91, "cohort_trimmed": 1.01, "cohort_top5": 0.17,
                 "cohort_comps": "Someone '23->WR1 (1.60x)", "cohort_best5": "3/5 boomed"},
    "steady guy": {"cohort_desc": "RB yr-4", "cohort_boom": 0.41, "cohort_bust": 0.21,
                   "cohort_med": 1.45, "cohort_trimmed": 1.36, "cohort_top5": 0.30,
                   "cohort_comps": "Someone '25->RB3 (1.45x)", "cohort_best5": "3/5 boomed"},
    "fading guy": {"cohort_desc": "WR yr-9", "cohort_boom": 0.15, "cohort_bust": 0.30,
                   "cohort_med": 0.88, "cohort_trimmed": 0.90, "cohort_top5": 0.05,
                   "cohort_comps": "Someone '18->WR55 (0.80x)", "cohort_best5": "0/5 boomed"},
}
_orig = advisor._COHORTS
advisor._COHORTS = FAKE
try:
    board = pd.DataFrame([
        ("Tail Guy", "WR1", "SEA", 300.0, 80.0, 5.0, 0.15, 250.0, 400.0, 0.85, 0.10, 24.0),
        ("Steady Guy", "RB1", "DET", 300.0, 78.0, 6.0, 0.15, 250.0, 400.0, 0.85, 0.10, 24.0),
        ("Fading Guy", "WR2", "NYG", 290.0, 70.0, 7.0, 0.20, 240.0, 380.0, 0.80, 0.10, 24.0),
    ], columns=["full_name", "pos_label", "team", "total_points", "vols", "adp_rank", "p_bust",
                "floor", "ceiling", "p_startable", "role_lead", "team_implied_total"])
    board["position"] = board["pos_label"].str.replace(r"\d+$", "", regex=True)
    board["rank_composite"] = range(1, len(board) + 1)
    for c in ["market", "risk_tier", "regression", "team_role"]:
        board[c] = ""
    for c in ["target_share_2025", "snap_share_2025", "age", "draft_pick", "xppg"]:
        board[c] = 0.0
    for c in ["is_rookie", "switched_team", "no_team", "proj_outlier"]:
        board[c] = False
    board["role_env_ok"] = True
    av = advisor.add_vona(board.copy(), 20)
    dp = {"slot": 5, "teams": 12, "overall_now": 5, "my_turn": True, "next_pick": 5,
          "following": 20, "picks_away": 0, "total_rounds": 16}
    ctx = advisor.build_context(av, board.iloc[0:0], {p: 5 for p in ["QB", "RB", "WR", "TE", "K"]}, dp)
    cohort_lines = [l for l in ctx.splitlines() if "trimmed-mean" in l]
    check("advisor reports trimmed-mean alongside the median", len(cohort_lines) >= 1)
    # pick the COHORT line specifically — the name also appears in TOP PICKS / the board table
    cline = lambda nm: [l for l in ctx.splitlines() if nm in l and "trimmed-mean" in l]
    tail_line, steady_line, fading_line = cline("Tail Guy"), cline("Steady Guy"), cline("Fading Guy")
    check("TAIL-DRIVEN flags the med<1.0<=trimmed crossing",
          tail_line and "TAIL-DRIVEN" in tail_line[0])
    check("no flag when BOTH clear 1.0x (already good, not tail-dependent)",
          steady_line and "TAIL-DRIVEN" not in steady_line[0])
    check("no flag when BOTH miss 1.0x (the tail doesn't rescue him)",
          fading_line and "TAIL-DRIVEN" not in fading_line[0])
finally:
    advisor._COHORTS = _orig

print(f"\n{passed} checks passed ✅")
