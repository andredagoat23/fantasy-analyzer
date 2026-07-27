"""Regression test for the HEALTH FLAGS read (utils.injury_severity + the build_context line).

The board has NO health input — value_board.py doesn't model it and projections lag an injury by
days — so a hurt player still carries his full projection, VOLS, VONA and ceiling. These flags are
FACTS the board can't see, surfaced as a NAMED line rather than only a table column (L8: a column in
a 35-row table gets skimmed past).

Design decision under test: it is NOT a gate. A player on PUP in preseason often returns by week 1-4
and can be real value at his discounted price, so nothing is ever removed or demoted — TOP PICKS must
be byte-identical with and without flags (user's call, Jul 27).

Run:  .venv/bin/python tests/test_injury.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

import advisor
from utils import injury_serious, injury_severity

passed = 0


def check(label, cond):
    global passed
    assert cond, f"FAIL: {label}"
    passed += 1
    print(f"  ok  {label}")


# --- severity tiers ---
check("PUP -> hard", injury_severity("PUP") == "hard")
check("IR -> hard", injury_severity("IR", "Surgery") == "hard")
check("Questionable + surgery -> procedure", injury_severity("Questionable", "Surgery") == "procedure")
check("Questionable + ACL tear -> procedure", injury_severity("Questionable", "Torn ACL") == "procedure")
check("Questionable + soreness -> soft", injury_severity("Questionable", "Soreness") == "soft")
check("Questionable, no note -> soft", injury_severity("Questionable") == "soft")
check("empty status -> no flag", injury_severity("") == "" and injury_severity(None) == "")
check("whitespace status -> no flag", injury_severity("   ") == "")
check("note matching is case-insensitive", injury_serious("Offseason SURGERY") is True)
check("unrelated note is not serious", injury_serious("Rest") is False)

# --- the context line on the REAL board ---
b = pd.read_csv("value_board.csv")
b["position"] = b["pos_label"].str.replace(r"\d+$", "", regex=True)
dp = {"slot": 7, "teams": 12, "overall_now": 7, "my_turn": True, "next_pick": 7, "picks_away": 0,
      "following": 18, "total_rounds": 16}
scar = {"QB": 5, "RB": 20, "WR": 20, "TE": 8, "K": 10}

clean = advisor.add_vona(b.copy(), 18)
ctx_none = advisor.build_context(clean, b.iloc[0:0], scar, dp, my_dst=None, drafted_dsts=set())
check("no injury columns -> no HEALTH FLAGS line (old boards unaffected)",
      "HEALTH FLAGS" not in ctx_none)

# flag the two highest-ADP players so they're guaranteed to be in the shortlist window
hurt = b.copy()
hurt["injury_status"] = ""
hurt["injury_note"] = ""
hurt["injury_sev"] = ""
top2 = hurt.nsmallest(2, "adp_rank").index
hurt.loc[top2[0], ["injury_status", "injury_note", "injury_sev"]] = ["PUP", "Surgery", "hard"]
hurt.loc[top2[1], ["injury_status", "injury_note", "injury_sev"]] = ["Questionable", "Soreness", "soft"]
n0, n1 = hurt.loc[top2[0], "full_name"], hurt.loc[top2[1], "full_name"]
ctx = advisor.build_context(advisor.add_vona(hurt, 18), b.iloc[0:0], scar, dp,
                            my_dst=None, drafted_dsts=set())

check("HEALTH FLAGS line renders", "HEALTH FLAGS" in ctx)
line = next(l for l in ctx.splitlines() if l.startswith("HEALTH FLAGS"))
check("names the flagged players", n0 in line and n1 in line)
check("carries the status text", "PUP" in line and "Questionable" in line)
check("hard flag sorts before the soft one", line.index(n0) < line.index(n1))
check("states it is NOT a gate", "NOT a gate" in line)
check("tells the model to say the flag out loud", "out loud" in line.lower())
check("distinguishes a procedure from a plain flag",
      "procedure" in advisor.build_context(
          advisor.add_vona(
              hurt.assign(injury_sev=hurt["injury_sev"].mask(hurt.index == top2[1], "procedure"),
                          injury_note=hurt["injury_note"].mask(hurt.index == top2[1], "Surgery")), 18),
          b.iloc[0:0], scar, dp, my_dst=None, drafted_dsts=set()))

# --- the whole point: it must NOT change any recommendation ---
tp_none = [l for l in ctx_none.splitlines() if l.startswith("TOP PICKS NOW")]
tp_hurt = [l for l in ctx.splitlines() if l.startswith("TOP PICKS NOW")]
check("TOP PICKS is byte-identical with flags present (never a gate)", tp_none == tp_hurt and tp_none)
check("the flagged #1 is still recommended (a PUP player can still be value)", n0 in tp_hurt[0])
check("SYSTEM explains the flags", "HEALTH FLAGS" in advisor.SYSTEM)
check("SYSTEM forbids silent removal", "never silently remove" in advisor.SYSTEM.lower())

print(f"\n{passed} checks passed ✅")
