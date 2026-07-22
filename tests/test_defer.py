"""Regression tests for the NEXT-PICK DEFER (advisor._punt_read next_pick path, L33).

The rule: even when a 1-start slot (QB/TE) is NOT punt-able 5 rounds out, defer the ELITE one when he
lasts to my very NEXT pick AND a scarce RB/WR exists to take instead. Because he survives, I get him
back next pick, so grabbing the scarcer RB/WR now is a free gain (+8..33 pts at the snake turn,
validated on actual roster value). Self-limiting: a genuine cliff never lasts to the next pick.

Run:  .venv/bin/python tests/test_defer.py
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


def pool(rows):   # (name, pos, vols, adp, bust)
    return pd.DataFrame(rows, columns=["full_name", "position", "vols", "adp_rank", "p_bust"])


# A board where TE is a genuine 5-round CLIFF (steep drop, high punt_loss) but the RB/WR pool is DEEP
# (low punt_loss). The elite TE's ADP (21) lasts past my next pick (14). So only the next-pick defer
# can flag it — the 5-round read alone would keep it a cliff.
board = pool([
    ("TE Elite", "TE", 100.0, 21.0, 0.0), ("TE Late", "TE", 5.0, 130.0, 0.0),   # steep TE cliff
    ("RB Elite", "RB", 60.0, 12.0, 0.0), ("RB Late", "RB", 50.0, 130.0, 0.0),   # deep RB
    ("WR Elite", "WR", 40.0, 20.0, 0.0), ("WR Late", "WR", 30.0, 130.0, 0.0),   # deep WR
])
reads, bar = advisor._punt_read(board, ["TE"], 11, 12, next_pick=14)
check("elite TE lasts to my next pick -> DEFERRED", reads["TE"]["next_defer"])
check("defer sets punt_able (so TOP PICKS demotes it below RB/WR)", reads["TE"]["punt_able"])
check("the 5-round read ALONE would NOT punt it (it's a real cliff there)", reads["TE"]["punt_loss"] > bar)
check("elite survival to next pick is recorded and high", reads["TE"]["elite_survives_next"] >= 0.6)

# Josh Allen analog: the elite goes BEFORE my next pick (ADP 8 < next 14) -> he does NOT survive, so he
# is NOT deferred and stays a grab. A positional prior gets no veto (L28) and neither does the defer.
board2 = pool([
    ("TE Elite", "TE", 100.0, 8.0, 0.0), ("TE Late", "TE", 5.0, 130.0, 0.0),
    ("RB Elite", "RB", 60.0, 12.0, 0.0), ("RB Late", "RB", 50.0, 130.0, 0.0),
])
reads2, _ = advisor._punt_read(board2, ["TE"], 11, 12, next_pick=14)
check("an elite that WON'T survive to next pick is NOT deferred", not reads2["TE"].get("next_defer"))
check("...and stays a cliff (still grabbed, not punt-able)", not reads2["TE"]["punt_able"])

# Backward compatible: no next_pick -> the defer path never fires (the old 5-round behaviour is intact).
reads3, _ = advisor._punt_read(board, ["TE"], 11, 12)
check("no next_pick given -> defer never fires (backward compatible)", not reads3["TE"].get("next_defer"))

# No scarce RB/WR to take instead -> deferring would be pointless, so it must NOT fire.
board4 = pool([("TE Elite", "TE", 100.0, 21.0, 0.0), ("TE Late", "TE", 5.0, 130.0, 0.0)])
reads4, _ = advisor._punt_read(board4, ["TE"], 11, 12, next_pick=14)
check("no RB/WR available to defer TO -> no defer", not reads4["TE"].get("next_defer"))

print(f"\n{passed} checks passed ✅")
