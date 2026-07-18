"""Regression tests for bridge.py — the browser-bridge pick resolver.

Plain asserts, no pytest dependency (keeps requirements.txt = streamlit + pandas + requests).
Run:  .venv/bin/python tests/test_bridge.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge

# A tiny stand-in board: normalized name -> canonical name (mirrors what draft.py builds).
BY_NAME = {
    "bijan robinson": "Bijan Robinson",
    "jahmyr gibbs": "Jahmyr Gibbs",
    "puka nacua": "Puka Nacua",
    "chase brown": "Chase Brown",
    "christian mccaffrey": "Christian McCaffrey",
}

passed = 0


def check(label, cond):
    global passed
    assert cond, f"FAIL: {label}"
    passed += 1
    print(f"  ok  {label}")


# ---- _pick_no ----
check("_pick_no accepts a positive int", bridge._pick_no({"pick": 7}) == 7)
check("_pick_no rejects zero", bridge._pick_no({"pick": 0}) is None)
check("_pick_no rejects missing", bridge._pick_no({}) is None)
check("_pick_no rejects bool True (int subclass)", bridge._pick_no({"pick": True}) is None)
check("_pick_no rejects non-int", bridge._pick_no({"pick": "3"}) is None)

# ---- resolve: junk filtering ----
junk = [
    {"player": "RankPLAYERNo players in queue", "team": ""},          # blob, no pick# -> ignored
    {"player": "PickPlayerTeam...Bijan Robinson...", "team": "ATL"},  # blob, no pick# -> ignored
    {"pick": 1, "player": "Bijan Robinson", "team": "Team 7"},        # real
]
drafted, mine, teams, total = bridge.resolve(junk, BY_NAME)
check("junk blobs excluded from drafted", drafted == {"Bijan Robinson"})
check("junk blobs don't inflate total", total == 1)
check("junk teams (NFL abbrevs) not in dropdown", teams == ["Team 7"])

# ---- resolve: mine by pick number (any draft order) ----
picks = [
    {"pick": 1, "player": "Bijan Robinson", "team": "Landon's Optimum Team"},
    {"pick": 5, "player": "Puka Nacua", "team": "Whoever"},
    {"pick": 20, "player": "Chase Brown", "team": "Someone Else"},
    {"pick": 7, "player": "Christian McCaffrey", "team": "Not Me"},
]
drafted, mine, teams, total = bridge.resolve(picks, BY_NAME)
check("total tracks the max pick number", total == 20)

# ---- resolve: mine by owner name ONLY (never by seat/pick-number) ----
drafted, mine, teams, total = bridge.resolve(picks, BY_NAME, my_team="Landon's Optimum Team")
check("mine-by-owner flags exactly my team's picks", mine == {"Bijan Robinson"})
check("no team selected -> empty roster, never guessed",
      bridge.resolve(picks, BY_NAME, my_team=None)[1] == set())
# a pick that lands on a 'seat' number but belongs to another owner must NEVER be mine
seat_bait = [{"pick": 5, "player": "Puka Nacua", "team": "Some Other Team"}]
check("pick at a seat number but another owner is NOT mine",
      bridge.resolve(seat_bait, BY_NAME, my_team="Me")[1] == set())

# ---- resolve: mine by explicit flag ----
flagged = [{"pick": 3, "player": "Jahmyr Gibbs", "team": "X", "mine": True}]
drafted, mine, teams, total = bridge.resolve(flagged, BY_NAME)
check("mine-by-flag honored", mine == {"Jahmyr Gibbs"})

# ---- resolve: D/ST (real pick, valid #, not on board) still counts ----
dst = [
    {"pick": 5, "player": "Puka Nacua", "team": "Me"},
    {"pick": 6, "player": "49ers D/ST", "team": "Them"},   # not on board
]
drafted, mine, teams, total = bridge.resolve(dst, BY_NAME)
check("D/ST not added to board-drafted set", drafted == {"Puka Nacua"})
check("D/ST still counts toward total via its pick #", total == 6)

# ---- my_dst: defenses aren't on the board, so they're detected by owner + name ----
dst_picks = [{"pick": 5, "player": "Puka Nacua", "team": "Me"},
             {"pick": 130, "player": "Broncos D/ST", "team": "Me"},
             {"pick": 131, "player": "Bills D/ST", "team": "Other"}]
check("my_dst finds my defense", bridge.my_dst(dst_picks, "Me") == "Broncos D/ST")
check("my_dst ignores another team's defense", bridge.my_dst(dst_picks, "Nobody") is None)
check("my_dst None when I have no defense", bridge.my_dst([{"pick": 5, "player": "Puka Nacua", "team": "Me"}], "Me") is None)
check("my_dst honors the mine flag", bridge.my_dst([{"pick": 9, "player": "49ers D/ST", "mine": True}], None) == "49ers D/ST")

# ---- resolve: empty ----
drafted, mine, teams, total = bridge.resolve([], BY_NAME)
check("empty picks -> empty everything", (drafted, mine, teams, total) == (set(), set(), [], 0))

# ---- resolve: gap in pick numbers -> total is the max, not the count ----
drafted, mine, teams, total = bridge.resolve(
    [{"pick": 1, "player": "Bijan Robinson", "team": "A"},
     {"pick": 24, "player": "Jahmyr Gibbs", "team": "B"}], BY_NAME)
check("total = max pick# even with gaps (round survives a missing row)", total == 24)

# ---- fetch: shape tolerance (mock the network) ----
_orig_get = bridge.requests.get


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _fetch_with(payload):
    bridge.requests.get = lambda *a, **k: _Resp(payload)
    try:
        return bridge.fetch("http://x")
    finally:
        bridge.requests.get = _orig_get


out = _fetch_with({"meta": {"teams": 12}, "picks": [{"pick": 1, "player": "x"}]})
check("fetch reads new {meta,picks} shape", out["meta"] == {"teams": 12} and len(out["picks"]) == 1)
out = _fetch_with({"picks": [{"pick": 1, "player": "x"}]})
check("fetch tolerates old {picks} shape (empty meta)", out["meta"] == {} and len(out["picks"]) == 1)
out = _fetch_with([{"pick": 1, "player": "x"}])
check("fetch tolerates a bare list", out["meta"] == {} and len(out["picks"]) == 1)
out = _fetch_with(None)
check("fetch tolerates null/empty mailbox", out == {"picks": [], "meta": {}})
out = _fetch_with({"picks": "not-a-list", "meta": "not-a-dict"})
check("fetch guards against wrong-typed fields", out == {"picks": [], "meta": {}})

print(f"\n{passed} checks passed ✅")
