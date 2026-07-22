"""Regression tests for the HANDCUFF READ (advisor._handcuff_read / _starters, L30).

contingency value = P(my starter misses time) x the backup's ceiling. `availability` IS the
probability, so there's no tuned threshold.

TWO scope rules, both MEASURED (2014-25 weekly, 281 team-seasons where a starter missed 3+ games) —
an earlier version of this feature violated both and would have made late picks WORSE:

  * RB ONLY. Backup RB goes 4.0 -> 9.5 ppg when the starter sits (2.25x, 56% gain 5+ ppg) because
    carries transfer ~1-for-1. WR is 7.2 -> 8.6 (1.17x — vacated targets scatter across WR2/WR3/TE/RB)
    and TE 2.3 -> 4.8 (below streaming level). WR/TE handcuffs are noise.
  * STARTERS ONLY. A contingency behind a BENCH player is worthless — I wasn't starting him anyway.
    FLEX counts; pure bench does not.

Run:  .venv/bin/python tests/test_handcuff.py
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


def roster(rows):   # (name, pos_label, team, availability, risk_tier, total_points)
    df = pd.DataFrame(rows, columns=["full_name", "pos_label", "team", "availability",
                                     "risk_tier", "total_points"])
    df["position"] = df["pos_label"].str.replace(r"\d+$", "", regex=True)
    return df


def board(rows):    # (name, position, team, team_role, total_points, ceiling)
    return pd.DataFrame(rows, columns=["full_name", "position", "team", "team_role",
                                       "total_points", "ceiling"])


AVAIL = board([
    ("MIA Backup RB", "RB", "MIA", "RB2", 90.0, 140.0),
    ("CHI Backup RB", "RB", "CHI", "RB2", 70.0, 110.0),
    ("SF Backup WR", "WR", "SF", "WR3", 143.0, 204.0),    # big projection — must still be IGNORED
    ("KC Backup TE", "TE", "KC", "TE2", 100.0, 150.0),    # must be IGNORED
])

# ---- _starters: greedy 1QB/2RB/2WR/1TE + 1 FLEX ------------------------------------------------
full = roster([
    ("QB Guy", "QB1", "BUF", 0.90, "Balanced", 380.0),
    ("RB One", "RB1", "MIA", 0.84, "Injury Risk", 300.0),
    ("RB Two", "RB1", "CHI", 0.88, "Balanced", 280.0),
    ("RB Bench", "RB1", "PIT", 0.60, "Injury Risk", 150.0),   # 3rd RB -> loses FLEX to the better WR
    ("WR One", "WR1", "CIN", 0.89, "Balanced", 320.0),
    ("WR Two", "WR1", "IND", 0.88, "Balanced", 260.0),
    ("WR Flex", "WR1", "SF", 0.73, "Injury Risk", 200.0),     # 3rd WR -> takes the FLEX (200 > 150)
    ("TE Guy", "TE1", "CHI", 0.85, "Boom/Bust", 220.0),
])
st = advisor._starters(full)
check("_starters fills 1QB/2RB/2WR/1TE + FLEX", len(st) == 8 - 1)   # 8 rostered, 1 is bench
check("_starters puts the better 3rd skill player in the FLEX", "WR Flex" in st)
check("_starters leaves the weaker 3rd RB on the BENCH", "RB Bench" not in st)

# ---- RB ONLY -----------------------------------------------------------------------------------
note = advisor._handcuff_read(full, AVAIL, set())
check("fires for a fragile STARTING RB", "MIA Backup RB" in note and "RB One" in note)
check("IGNORES a WR starter even with a big-projection backup (targets scatter)",
      "SF Backup WR" not in note)
check("IGNORES a TE starter", "KC Backup TE" not in note)
check("cites the validated screen basis", "DOUBLE the hit rate" in note or "STARTABLE WEEKS" in note)

# ---- STARTERS ONLY -----------------------------------------------------------------------------
# RB Bench is the most fragile player on the roster (0.60) with a backup available — must be ignored
bench_avail = board([("PIT Backup RB", "RB", "PIT", "RB2", 95.0, 150.0)])
check("IGNORES a contingency behind a BENCH RB (I wasn't starting him anyway)",
      advisor._handcuff_read(full, bench_avail, set()) == "")

# a FLEX RB DOES count as a starter
flexrb = roster([
    ("RB One", "RB1", "MIA", 0.84, "Injury Risk", 300.0),
    ("RB Two", "RB1", "CHI", 0.88, "Balanced", 280.0),
    ("RB Flex", "RB1", "PIT", 0.70, "Injury Risk", 200.0),   # 3rd RB, nothing else -> takes FLEX
])
check("a FLEX RB counts as a starter", "PIT Backup RB" in
      advisor._handcuff_read(flexrb, bench_avail, set()))

# ---- ranking + guards --------------------------------------------------------------------------
two = roster([("RB One", "RB1", "MIA", 0.84, "Injury Risk", 300.0),    # .16 x 140 = 22
              ("RB Two", "RB1", "CHI", 0.98, "Balanced", 280.0)])       # .02 x 110 = 2
n2 = advisor._handcuff_read(two, AVAIL, set(), top_n=1)
check("ranks the FRAGILE starter's contingency first (equal GO -> higher miss risk)",
      "MIA Backup RB" in n2 and "CHI Backup RB" not in n2)
check("silent while a dedicated starter slot is open", advisor._handcuff_read(full, AVAIL, {"WR"}) == "")
check("skips a starter with no availability data (no guessing)",
      advisor._handcuff_read(roster([("RB One", "RB1", "MIA", float("nan"), "Balanced", 300.0)]),
                             AVAIL, set()) == "")
check("silent on an empty roster", advisor._handcuff_read(roster([]).iloc[0:0], AVAIL, set()) == "")

print(f"\n{passed} checks passed ✅")

# ---- L31 addendum: the GO screen inside the handcuff read ----
FAKE = {"mia backup rb": {"share_2025": 0.35, "pos_adp_rank": 40},
        "pit backup rb": {"share_2025": 0.04, "pos_adp_rank": 55}}
_o = advisor._ROLES
advisor._ROLES = FAKE
advisor._ROLES_MTIME = os.path.getmtime(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'role_data.csv'))
try:
    m = roster([("RB One", "RB1", "MIA", 0.84, "Injury Risk", 300.0),
                ("RB Two", "RB1", "CHI", 0.88, "Balanced", 280.0)])
    m["team_implied_total"] = 24.0
    note = advisor._handcuff_read(m, AVAIL, set())
    check("L31: committee-share backup is tagged GO", "GO (passes the validated screen" in note)
    m2 = roster([("RB Flex", "RB1", "PIT", 0.70, "Injury Risk", 200.0),
                 ("RB One", "RB1", "MIA", 0.95, "Balanced", 300.0),
                 ("RB Two", "RB1", "CHI", 0.95, "Balanced", 280.0)])
    m2["team_implied_total"] = 20.0
    note2 = advisor._handcuff_read(m2, board([("PIT Backup RB", "RB", "PIT", "RB2", 95.0, 150.0)]), set())
    check("L31: screen-failing backup is tagged NO-GO (even behind a fragile starter)",
          "NO-GO (fails the screen" in note2)
    check("L31: startable-not-league-winner language enforced", "STARTABLE WEEKS" in note and "never a TE handcuff" in note)
finally:
    advisor._ROLES = _o

print(f"\n{passed} checks passed (incl. L31 addendum) ✅")
