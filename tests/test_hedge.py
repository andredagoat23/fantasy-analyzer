"""Regression tests for the HEDGE READ (advisor._hedge_read) — the risk-aware 1-start hedge surfacer.

Plain asserts, no pytest dep (mirrors test_bridge.py). Run:
    .venv/bin/python tests/test_hedge.py
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


def roster(rows):   # (name, pos_label, p_bust, risk_tier, total_points)
    df = pd.DataFrame(rows, columns=["full_name", "pos_label", "p_bust", "risk_tier", "total_points"])
    df["position"] = df["pos_label"].str.replace(r"\d+$", "", regex=True)
    return df


def board(rows):    # available: (name, position, p_bust, floor, total_points)
    return pd.DataFrame(rows, columns=["full_name", "position", "p_bust", "floor", "total_points"])


AVAIL = board([("Safe TE", "TE", 0.20, 180, 200), ("Risky TE", "TE", 0.55, 90, 150),
               ("Safe QB", "QB", 0.22, 300, 360), ("Boom QB", "QB", 0.50, 200, 340)])

# 1) risky (Boom/Bust) TE starter, dedicated starters set -> fires, names the TE + the safest hedge
mine = roster([("Colston Loveland", "TE1", 0.37, "Boom/Bust", 204)])
note = advisor._hedge_read(mine, AVAIL, set())
check("fires for a Boom/Bust TE starter", "HEDGE READ" in note and "Colston Loveland" in note)
check("suggests the safest available hedge (lowest bust)", "Safe TE" in note)
check("labels it insurance, not a value pick", "INSURANCE" in note and "stays blocked" in note)

# 2) a SAFE QB starter needs no hedge
check("silent for a safe QB starter (Balanced, 25% bust)",
      advisor._hedge_read(roster([("Josh Allen", "QB1", 0.25, "Balanced", 380)]), AVAIL, set()) == "")

# 3) a high-bust QB starter DOES fire (risk-aware, not position-blind)
note = advisor._hedge_read(roster([("Risky QB", "QB1", 0.45, "Balanced", 340)]), AVAIL, set())
check("fires for a high-bust QB starter", "HEDGE READ" in note and "QB" in note and "Safe QB" in note)

# 4) still filling dedicated starters -> stay SILENT (a hedge is a bench decision, don't nag)
check("silent while a dedicated starter slot is still open",
      advisor._hedge_read(roster([("Colston Loveland", "TE1", 0.37, "Boom/Bust", 204)]), AVAIL, {"WR"}) == "")

# 5) no safe-floor hedge left at the position -> say stream
note = advisor._hedge_read(roster([("Colston Loveland", "TE1", 0.55, "Boom/Bust", 150)]),
                           board([("Safe QB", "QB", 0.22, 300, 360)]), set())
check("says stream when no hedge is left", "stream" in note.lower())

# 6) empty roster -> silent
check("silent on an empty roster",
      advisor._hedge_read(roster([]).iloc[0:0], AVAIL, set()) == "")

print(f"\n{passed} checks passed ✅")
