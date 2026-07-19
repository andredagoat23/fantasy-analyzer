"""Regression tests for sleeper_sync.py — Sleeper draft JSON -> mailbox shape -> bridge.resolve.

Plain asserts, no pytest. Uses a fixture built from Sleeper's real API schema (verified against
docs.sleeper.com + a live api.sleeper.app call). The final live check is a real Sleeper mock draft.
Run:  .venv/bin/python tests/test_sleeper.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge
import sleeper_sync as sl

BY_NAME = {
    "bijan robinson": "Bijan Robinson",
    "jahmyr gibbs": "Jahmyr Gibbs",
    "puka nacua": "Puka Nacua",
}

ME, OTHER = "user_me", "user_other"
DRAFT = {"status": "drafting", "type": "snake",
         "settings": {"teams": 12, "rounds": 16},
         "draft_order": {ME: 5, OTHER: 3}}
# picks in Sleeper's real /picks shape (pick_no, draft_slot, picked_by, metadata{...})
PICKS = [
    {"pick_no": 3,  "draft_slot": 3, "picked_by": OTHER, "roster_id": 3,
     "metadata": {"first_name": "Bijan", "last_name": "Robinson", "position": "RB", "team": "ATL"}},
    {"pick_no": 5,  "draft_slot": 5, "picked_by": ME, "roster_id": 5,
     "metadata": {"first_name": "Jahmyr", "last_name": "Gibbs", "position": "RB", "team": "DET"}},
    {"pick_no": 8,  "draft_slot": 8, "picked_by": "u8", "roster_id": 8,
     "metadata": {"first_name": "Puka", "last_name": "Nacua", "position": "WR", "team": "LAR"}},
    {"pick_no": 20, "draft_slot": 5, "picked_by": ME, "roster_id": 5,   # my D/ST (not on the board)
     "metadata": {"first_name": "", "last_name": "Steelers", "position": "DEF", "team": "PIT"}},
    {"pick_no": 24, "draft_slot": 5, "picked_by": ME, "roster_id": 5,   # unknown player, still counts
     "metadata": {"first_name": "Deep", "last_name": "Sleeper", "position": "WR", "team": "FA"}},
]

passed = 0
def check(label, cond):
    global passed
    assert cond, f"FAIL: {label}"
    passed += 1
    print(f"  ok  {label}")


out = sl._normalize(DRAFT, PICKS, ME)
check("meta carries teams from settings", out["meta"]["teams"] == 12)
check("meta.slot = draft_order[my_user_id]", out["meta"]["slot"] == 5)
check("picks normalized to {pick,player,team,mine}", set(out["picks"][0]) == {"pick", "player", "team", "mine"})
check("player name joined from metadata", out["picks"][1]["player"] == "Jahmyr Gibbs")
check("mine set by draft_slot == my slot", out["picks"][1]["mine"] is True)
check("other team's pick is NOT mine", out["picks"][0]["mine"] is False)
check("defense formatted as '<Team> D/ST'", out["picks"][3]["player"] == "Steelers D/ST")

# end-to-end through the SHARED resolver (my_team=None since Sleeper sets mine directly)
drafted, mine, teams_seen, total = bridge.resolve(out["picks"], BY_NAME, my_team=None)
check("resolve: board players drafted", drafted == {"Bijan Robinson", "Jahmyr Gibbs", "Puka Nacua"})
check("resolve: only MY board pick in mine", mine == {"Jahmyr Gibbs"})
check("resolve: total counts all real picks (incl D/ST + unknown w/ pick#)", total == 24)
check("my_dst detects my Sleeper defense", bridge.my_dst(out["picks"]) == "Steelers D/ST")

# robustness: empty / missing user
empty = sl._normalize({}, [], None)
check("empty draft -> empty picks + null meta", empty["picks"] == [] and empty["meta"]["slot"] is None)
no_user = sl._normalize(DRAFT, PICKS, None)
check("no my_user_id -> nothing flagged mine", all(p["mine"] is False for p in no_user["picks"]))

print(f"\n{passed} checks passed ✅")
