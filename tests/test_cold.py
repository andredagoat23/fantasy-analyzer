"""Regression test for the COLD POSITION read (advisor._cold_read + build_context wiring, L48).

The read fires when the room is SKIPPING a position I can still start: baseline = the position's
share of the top-12-by-ADP pool AS OF the window start (the window's own picks are added back so a
stretch of picks can't drain its own baseline), surprise = the binomial lower tail (<= _COLD_P), and
it only fires for a needed position where ADP expected at least one pick.

Validated on 1,162 real Sleeper drafts / 372k picks (icm/work/run-dynamics-findings.md): a cold
position keeps getting skipped (WR -11.5pp over the next 4 picks). The mirror "HOT run" read was CUT
as unsupported (RB runs measured -2.9pp / -1.0pp on 9,200 windows), so several checks below exist to
make sure no run/HOT behavior ever comes back. Advisory only — TOP PICKS must be untouched.

Run:  .venv/bin/python tests/test_cold.py
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


def av(rows):
    """Tiny available-board builder: rows = [(pos, adp), ...]."""
    return pd.DataFrame({"position": [p for p, _ in rows], "adp_rank": [a for _, a in rows],
                         "full_name": [f"P{i}" for i in range(len(rows))]})


# Fixtures model the board as it REALLY is: a player taken in the window is no longer `available`.
# BOARD = what's left after the window — 8 WRs untouched at the top, the near RBs gone.
BOARD = av([("WR", float(i)) for i in range(1, 9)]
           + [("RB", 20.0), ("RB", 21.0), ("RB", 22.0), ("QB", 25.0), ("TE", 26.0)])

# --- WR frozen out: the room spent 6 of its last 8 on RBs and took ZERO WRs (~5 expected) ---
cold_win = [("RB", 9.0), ("RB", 10.0), None, ("RB", 11.0), ("RB", 12.0), ("RB", 13.0), None,
            ("RB", 14.0)]
out = advisor._cold_read(BOARD, cold_win, {"WR", "RB"})
check("WR freeze-out fires COLD", "COLD POSITION" in out and out.count("WR —") == 1)
check("COLD sells the value + sequencing, never a fade",
      "falling TO you" in out and "never demotes" in out and "collect the faller" in out)
check("line cites the measured evidence", "372k picks" in out or "372,394" in out)
check("line declares itself advisory", "NOT baked into VONA/wheel" in out)

# --- the cut HOT branch must never come back (cold_win IS a 6-of-8 RB run) ---
hot = advisor._cold_read(BOARD, cold_win, {"RB", "WR"})
check("a 6-of-8 RB run does NOT fire a HOT/urgency read", "HOT" not in hot and "act before" not in hot)
check("no 'let it burn' phrasing survives anywhere", "let it burn" not in hot)
check("_run_read is gone (renamed to _cold_read)", not hasattr(advisor, "_run_read"))
check("HOT constants removed", not hasattr(advisor, "_RUN_P") and not hasattr(advisor, "_RUN_MIN_K"))

# --- needed-gating: a cold position I can't start isn't actionable ---
check("COLD suppressed when the position isn't needed",
      "WR —" not in advisor._cold_read(BOARD, cold_win, {"RB"}))
check("no needed set at all -> silent", advisor._cold_read(BOARD, cold_win, set()) == "")

# --- the exp>=1 gate keeps the read off positions too thin to judge (why QB/TE never fire in 1QB:
#     across 111 real one-QB drafts, QB COLD fired 0 times) ---
thin = av([("RB", float(i)) for i in range(1, 12)] + [("WR", 12.0), ("QB", 80.0), ("TE", 90.0)])
allrb = [("RB", 30.0 + i) for i in range(8)]
check("a position ADP barely expects (QB/TE in 1QB) never fires COLD",
      advisor._cold_read(thin, allrb, {"QB", "TE", "WR"}) == "")

# --- baseline reconstruction: the window's own picks are added back. Without it, the drained board
#     looks WR-dominated (share .75) and 3-of-8 WRs would FALSELY read cold (tail .027); adding the
#     window back gives the true as-of-window-start share (.583) and it correctly stays silent. ---
recon = av([("WR", float(i)) for i in range(1, 7)] + [("RB", 40.0), ("RB", 41.0)])
mixed = [("RB", 7.0), ("RB", 8.0), ("RB", 9.0), ("RB", 10.0), ("RB", 11.0),
         ("WR", 13.0), ("WR", 14.0), ("WR", 15.0)]
check("window picks are added back to the baseline (no false WR-cold on a drained board)",
      "WR —" not in advisor._cold_read(recon, mixed, {"WR", "RB"}))

# --- guards ---
check("fewer than _RUN_MIN_N picks -> silent", advisor._cold_read(BOARD, cold_win[:5], {"WR"}) == "")
check("None recent -> silent", advisor._cold_read(BOARD, None, {"WR"}) == "")
check("empty recent -> silent", advisor._cold_read(BOARD, [], {"WR"}) == "")
bal_board = av([("WR", 20.0), ("WR", 22.0), ("WR", 24.0), ("WR", 26.0), ("WR", 28.0), ("WR", 30.0),
                ("RB", 21.0), ("RB", 23.0), ("RB", 25.0), ("RB", 27.0), ("RB", 29.0), ("RB", 31.0)])
balanced = [("WR", 1.0), ("WR", 2.0), ("WR", 3.0), ("WR", 4.0),
            ("RB", 5.0), ("RB", 6.0), ("RB", 7.0), ("RB", 8.0)]
check("balanced window (4 WR / 4 RB at a 50-50 baseline) -> silent",
      advisor._cold_read(bal_board, balanced, {"RB", "WR"}) == "")
check("missing columns -> silent", advisor._cold_read(pd.DataFrame({"x": [1]}), cold_win, {"WR"}) == "")

# --- integration on the REAL board: freeze WRs out while RBs go ---
b = pd.read_csv("value_board.csv")
b["position"] = b["pos_label"].str.replace(r"\d+$", "", regex=True)
rbs = b[(b["position"] == "RB") & b["adp_rank"].notna()].nsmallest(8, "adp_rank")
avail = advisor.add_vona(b[~b["full_name"].isin(rbs["full_name"])].copy(), 18)
recent = [("RB", float(a)) for a in rbs["adp_rank"]]
dp = {"slot": 7, "teams": 12, "overall_now": 9, "my_turn": True, "next_pick": 9, "picks_away": 0,
      "following": 18, "total_rounds": 16}
scar = {"QB": 5, "RB": 20, "WR": 20, "TE": 8, "K": 10}
ctx = advisor.build_context(avail, b.iloc[0:0], scar, dp, my_dst=None, drafted_dsts=set(),
                            recent_picks=recent)
check("build_context renders the cold line (8 straight RBs on the real board)",
      "COLD POSITION" in ctx and "WR —" in ctx)
ctx0 = advisor.build_context(avail, b.iloc[0:0], scar, dp, my_dst=None, drafted_dsts=set())
check("no recent_picks kwarg -> no cold line (old callers unchanged)", "COLD POSITION" not in ctx0)
tp = [l for l in ctx.splitlines() if l.startswith("TOP PICKS NOW")]
tp0 = [l for l in ctx0.splitlines() if l.startswith("TOP PICKS NOW")]
check("advisory only: TOP PICKS identical with and without the cold line", tp == tp0 and tp)
check("SYSTEM inoculates against the disproven run read",
      "positional runs do NOT continue" in advisor.SYSTEM.lower()
      or "runs do not continue" in advisor.SYSTEM.lower())

print(f"\n{passed} checks passed ✅")
