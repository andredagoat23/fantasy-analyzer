"""Regression tests for D/ST already-drafted filtering (advisor.dst_ranking_text + bridge.drafted_dsts, L36).

The bug: defenses aren't on the board, so the advisor was shown the full static D/ST ranking and kept
recommending a defense (Houston) already drafted by another team. Fix: track every drafted D/ST (any
team) and strip them from the ranking the advisor sees.

Run:  .venv/bin/python tests/test_dst.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import advisor
import bridge

passed = 0


def check(label, cond):
    global passed
    assert cond, f"FAIL: {label}"
    passed += 1
    print(f"  ok  {label}")


# --- name -> team code resolution (picks say "Texans D/ST"; ranking says HOU) ---
check("nickname resolves", advisor._dst_code("Texans D/ST") == "HOU")
check("city resolves", advisor._dst_code("San Francisco D/ST") == "SF")
check("nickname (Broncos) resolves", advisor._dst_code("Broncos D/ST") == "DEN")
check("raw code passes through", advisor._dst_code("HOU") == "HOU")
check("LAC vs LAR disambiguated by nickname", advisor._dst_code("Chargers D/ST") == "LAC" and advisor._dst_code("Rams D/ST") == "LAR")
check("unknown -> None", advisor._dst_code("Not A Team Player") is None)

# --- bridge collects EVERY drafted D/ST (any owner), not just mine ---
picks = [{"player": "Josh Allen"}, {"player": "Texans D/ST", "mine": False},
         {"player": "Eagles D/ST", "team": "Other"}, {"player": "Bijan Robinson"}]
dd = bridge.drafted_dsts(picks)
check("bridge picks up all drafted D/STs", dd == {"Texans D/ST", "Eagles D/ST"})
check("bridge ignores non-D/ST picks", "Josh Allen" not in dd and "Bijan Robinson" not in dd)

# --- the ranking the advisor sees drops drafted defenses ---
full = advisor.dst_ranking_text(set())
check("full ranking lists Houston when nothing drafted", "HOU" in full)
filtered = advisor.dst_ranking_text({"Texans D/ST", "Eagles D/ST"})
check("drafted Houston is REMOVED from the ranking", "HOU" not in filtered)
check("drafted Philadelphia is REMOVED from the ranking", "PHI" not in filtered)
check("an undrafted defense still appears", "DEN" in filtered)
check("filtering only removed the drafted ones", filtered.count(".") == full.count(".") - 2)

# --- end to end: my_dst still works alongside the new all-D/ST tracking ---
check("my_dst unchanged (mine only)", bridge.my_dst([{"player": "Texans D/ST", "mine": True}]) == "Texans D/ST")

print(f"\n{passed} checks passed ✅")
