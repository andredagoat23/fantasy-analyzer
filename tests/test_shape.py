"""Regression test for the position-shape advisory (advisor.position_shape / POSITION_SHAPE, L46).

The hybrid shape advisory = a DURABLE historical note in the system prompt + a COMPUTED per-class line
from the live board (reliable cliff where p_startable<70%, next-tier bust, value pocket by ADP round).
This tests the computed logic: the cliff detection, the pocket detection, graceful no-op, and that the
real board produces a shape line that flows into build_context.

Run:  .venv/bin/python tests/test_shape.py
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


# --- synthetic WR set: cliff should land at WR4 (0.75 ok, then two sub-0.70), pocket in the R3 cluster ---
syn = pd.DataFrame({
    "pos_label": [f"WR{i}" for i in range(1, 9)],
    "adp_rank": [1, 2, 3, 4, 30, 31, 32, 33],          # ranks 5-8 sit in round 3
    "p_startable": [0.90, 0.85, 0.80, 0.75, 0.60, 0.55, 0.50, 0.40],
    "p_bust":      [0.10, 0.10, 0.15, 0.20, 0.35, 0.40, 0.45, 0.55],
    "value_gap":   [-2, -1, 0, 1, 5, 6, 4, -1],         # the R3 cluster goes cheap (value_gap>0)
})
out = advisor.position_shape(syn)
check("synthetic: reliable cliff detected at WR4", "WR4" in out and "reliable" in out)
check("synthetic: value pocket found in the R3 cluster", "pocket ~R3" in out)
check("synthetic: reports a next-tier bust %", "next-tier bust" in out and "%" in out)

# --- graceful no-op when the board lacks the needed columns ---
check("no p_startable column -> empty string", advisor.position_shape(pd.DataFrame({"adp_rank": [1, 2]})) == "")
check("None board -> empty string", advisor.position_shape(None) == "")

# --- real board: POSITION_SHAPE computed at import, all four positions, sane cliffs ---
check("POSITION_SHAPE is non-empty on the real board", bool(advisor.POSITION_SHAPE))
for pos in ("RB", "WR", "TE", "QB"):
    check(f"POSITION_SHAPE covers {pos}", f"{pos} reliable" in advisor.POSITION_SHAPE)

# --- it flows into build_context ---
b = pd.read_csv("value_board.csv")
b["position"] = b["pos_label"].str.replace(r"\d+$", "", regex=True)
av = advisor.add_vona(b.copy(), 18)
dp = {"slot": 7, "teams": 12, "overall_now": 7, "my_turn": True, "next_pick": 7, "picks_away": 0,
      "following": 18, "total_rounds": 16}
ctx = advisor.build_context(av, b.iloc[0:0], {"QB": 5, "RB": 20, "WR": 20, "TE": 8, "K": 10},
                            dp, my_dst=None, drafted_dsts=set())
check("build_context includes the POSITION SHAPE line", "POSITION SHAPE" in ctx)

print(f"\n{passed} checks passed ✅")
