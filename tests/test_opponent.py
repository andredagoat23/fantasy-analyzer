"""Regression tests for opponent-aware survival — bridge seat/roster helpers + advisor.opponent_read
and the effective-horizon path through add_vona.

Plain asserts, no pytest dependency (mirrors test_bridge.py). Run:
    .venv/bin/python tests/test_opponent.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

import advisor
import bridge

passed = 0


def check(label, cond):
    global passed
    assert cond, f"FAIL: {label}"
    passed += 1
    print(f"  ok  {label}")


# ---- bridge.seat_of: standard 12-team snake ----
check("seat_of pick 1 -> seat 1", bridge.seat_of(1, 12) == 1)
check("seat_of pick 12 -> seat 12", bridge.seat_of(12, 12) == 12)
check("seat_of pick 13 -> seat 12 (round 2 reverses)", bridge.seat_of(13, 12) == 12)
check("seat_of pick 24 -> seat 1", bridge.seat_of(24, 12) == 1)
check("seat_of pick 7 -> seat 7", bridge.seat_of(7, 12) == 7)
check("seat_of pick 17 -> seat 8 (round 2)", bridge.seat_of(17, 12) == 8)
check("seat_of guards bad teams", bridge.seat_of(5, 0) is None and bridge.seat_of(None, 12) is None)
# consistency with draft.py's my_picks formula for slot 7
_my = [((r - 1) * 12 + 7) if r % 2 else (r * 12 - 7 + 1) for r in range(1, 5)]
check("seat_of matches the my_picks snake formula (slot 7)",
      all(bridge.seat_of(n, 12) == 7 for n in _my))

# ---- bridge.seat_owners: majority vote, ties omitted ----
picks = [
    {"pick": 7, "player": "A", "team": "Team G"},    # seat 7
    {"pick": 18, "player": "B", "team": "Team G"},    # seat_of(18,12)=7 -> same seat, same team
    {"pick": 8, "player": "C", "team": "Team H"},     # seat 8
    {"pick": 17, "player": "D", "team": "Other"},     # seat 8 but a DIFFERENT team -> 1-1 tie
]
owners = bridge.seat_owners(picks, 12)
check("seat_owners resolves a consistent seat", owners.get(7) == "Team G")
check("seat_owners omits a tied/conflicted seat", 8 not in owners)

# ---- bridge.rosters: position counts, D/ST, unresolved skip ----
name_to_pos = {"josh allen": "QB", "bijan robinson": "RB", "trey mcbride": "TE", "puka nacua": "WR"}
rpicks = [
    {"pick": 1, "player": "Josh Allen", "team": "Team A"},
    {"pick": 2, "player": "Bijan Robinson", "team": "Team A"},
    {"pick": 3, "player": "San Francisco D/ST", "team": "Team A"},
    {"pick": 4, "player": "Nobody OnBoard", "team": "Team A"},   # unresolved -> skipped
    {"pick": 5, "player": "Trey McBride", "team": "Team B"},
    {"pick": 6, "player": "Puka Nacua", "team": None},           # no owner -> skipped
]
ros = bridge.rosters(rpicks, name_to_pos)
check("rosters counts QB for Team A", ros["Team A"].get("QB") == 1)
check("rosters counts RB for Team A", ros["Team A"].get("RB") == 1)
check("rosters detects D/ST", ros["Team A"].get("DST") == 1)
check("rosters skips an unresolved name (no phantom position)", sum(ros["Team A"].values()) == 3)
check("rosters skips a teamless pick", "Puka Nacua" not in str(ros) and ros["Team B"].get("TE") == 1)


# ---- a tiny synthetic board for opponent_read / add_vona ----
def board():
    rows = [
        ("Elite QB", "QB", 20, 80.0), ("Mid QB", "QB", 45, 30.0), ("Late QB", "QB", 90, 12.0),
        ("Elite RB", "RB", 22, 100.0), ("Good RB", "RB", 30, 70.0), ("Deep RB", "RB", 55, 40.0),
        ("Elite WR", "WR", 24, 95.0), ("Good WR", "WR", 33, 65.0), ("Deep WR", "WR", 60, 35.0),
        ("Elite TE", "TE", 21, 90.0), ("Mid TE", "TE", 48, 25.0),
    ]
    return pd.DataFrame(rows, columns=["full_name", "position", "adp_rank", "vols"])


DP = {"slot": 7, "teams": 12, "overall_now": 31, "my_turn": False,
      "next_pick": 42, "following": 55, "picks_away": 11, "total_rounds": 16}
WINDOW = list(range(31, 42))   # 11 opponent picks before my #42


def read_with(window_owners, rosters):
    return advisor.opponent_read(board(), DP, window_owners, rosters)


# all-unknown seats -> nothing to add over ADP
check("opponent_read returns None when no team is known",
      read_with([None] * len(WINDOW), {}) is None)
check("opponent_read returns None for an empty window",
      advisor.opponent_read(board(), DP, [], {}) is None)

# every window team already has its QB filled -> QB survives longer, RB/WR go sooner
qb_filled = {f"T{i}": {"QB": 1} for i in range(11)}
owners_qbfull = [f"T{i}" for i in range(11)]
r = read_with(owners_qbfull, qb_filled)
check("opponent_read produces eff horizons + a summary", r and "eff" in r and r["summary"])
check("QB effective horizon shrinks when everyone's QB is filled",
      r["eff"]["QB"] < DP["next_pick"])
check("RB effective horizon extends (blocked QB demand shifts to RB/WR)",
      r["eff"]["RB"] > DP["next_pick"])
check("summary names the window teams and their need, with survival arrows",
      "needs TE" in r["summary"] and "QB" in r["summary"] and "↑surv" in r["summary"])

# direction check through add_vona: a QB's survival RISES (VONA falls) when QBs are filled around me
base = advisor.add_vona(board(), DP["next_pick"])
oppd = advisor.add_vona(board(), DP["next_pick"], opp=r["eff"])
mid_base = float(base.loc[base.full_name == "Mid QB", "vona"].iloc[0])
mid_opp = float(oppd.loc[oppd.full_name == "Mid QB", "vona"].iloc[0])
check("a mid QB's VONA drops once nearby teams have their QB (he'll survive)", mid_opp <= mid_base)

# ---- IDENTITY: opp=None / opp={} reproduce the plain single-horizon math exactly ----
plain = advisor.add_vona(board(), DP["next_pick"])
none_opp = advisor.add_vona(board(), DP["next_pick"], opp=None)
empty_opp = advisor.add_vona(board(), DP["next_pick"], opp={})
check("add_vona(opp=None) == add_vona() (byte-identical VONA)",
      plain["vona"].round(9).equals(none_opp["vona"].round(9)))
check("add_vona(opp={}) == add_vona() (empty dict is a no-op)",
      plain["vona"].round(9).equals(empty_opp["vona"].round(9)))
# a per-position eff dict equal to the horizon everywhere is also a no-op
same = advisor.add_vona(board(), DP["next_pick"],
                        opp={p: DP["next_pick"] for p in ("QB", "RB", "WR", "TE")})
check("add_vona with eff==horizon for every position == plain",
      plain["vona"].round(9).equals(same["vona"].round(9)))

print(f"\n{passed} checks passed ✅")
