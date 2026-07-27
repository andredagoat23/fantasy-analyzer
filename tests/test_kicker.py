"""Regression test for the kicker ranking (advisor build_context k_line / STREAMER ALERT, L38b).

The bug: every GOOD kicker trips `proj_outlier` (our VOLS ranks Ks ~#50 overall while ECR ranks them
~#200 — a >100 gap), and build_context drops proj_outliers from `available`. That gutted the kicker
list to the 8 worst Ks, so the advisor recommended Jake Moody (whom the board actually ranks K19) as
the "top K." Fix: never drop a kicker for proj_outlier — the K ranking must reflect the whole board.

Run:  .venv/bin/python tests/test_kicker.py
"""
import os
import re
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


b = pd.read_csv("value_board.csv")
b["position"] = b["pos_label"].str.extract(r"([A-Z]+)")
true_best_k = b[b.position == "K"].nsmallest(1, "rank_composite").iloc[0].full_name

# most kickers are flagged proj_outlier — the exact condition that caused the bug
n_outlier_k = int(b[(b.position == "K")]["proj_outlier"].fillna(False).sum())
check("setup: most kickers ARE proj_outlier (the trap)", n_outlier_k >= 10)

# reproduce a late-draft streamer turn (K + D/ST open, 2 picks left)
mine = b[b.position.isin(["RB", "WR", "TE", "QB"])].sort_values("rank_composite").head(14).copy()
avail = advisor.add_vona(b[~b.full_name.isin(mine.full_name)].copy(), 176)
dp = {"slot": 1, "teams": 12, "overall_now": 175, "my_turn": True, "next_pick": 175,
      "picks_away": 0, "following": None, "total_rounds": 16}
ctx = advisor.build_context(avail, mine, {"QB": 5, "RB": 20, "WR": 20, "TE": 8, "K": 10},
                            dp, my_dst=None, drafted_dsts=set())

kline = next((l for l in ctx.split("\n") if "KICKER ranking" in l), "")
first_k = re.search(r"1\.([A-Z][^ ]+(?: [A-Z][^ ]+)*?)  ", kline)
check("a KICKER ranking line is present", bool(kline))
check("the #1 K in the ranking is the board's actual best K", first_k and first_k.group(1).strip() == true_best_k)
check("the board's best K is Brandon Aubrey (sanity)", true_best_k == "Brandon Aubrey")
check("Jake Moody is NOT recommended as a top K", "1.Jake Moody" not in ctx and "Best K available: Jake Moody" not in ctx)
check("the good kicker survived the proj_outlier drop (it's in the ranking)", "Brandon Aubrey" in kline)

# L47: once a K is on the roster, the kicker ranking must DISAPPEAR (else the advisor recommends a 2nd K
# on the final pick — the live-mock catch). Same gate as the streamer alert.
mine_with_k = pd.concat([mine, b[b.position == "K"].nsmallest(1, "rank_composite")])
ctx_k = advisor.build_context(avail, mine_with_k, {"QB": 5, "RB": 20, "WR": 20, "TE": 8, "K": 10},
                              dp, my_dst=None, drafted_dsts=set())
check("KICKER ranking is HIDDEN once a K is rostered (no 2nd-K suggestion)", "KICKER ranking" not in ctx_k)

print(f"\n{passed} checks passed ✅")
