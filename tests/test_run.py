"""Regression test for positional-run detection (advisor._run_read + build_context wiring, roadmap #3).

The POSITION RUN read turns the ordered live pick stream into an advisory HOT/COLD line: baseline =
each position's share of the top-12-by-ADP pool AS OF the window start (the window's own picks are
added back so a run can't drain its own baseline), surprise = the plain binomial tail. HOT needs
k >= _RUN_MIN_K and upper tail <= _RUN_P; COLD fires only for a still-needed position with lower
tail <= _COLD_P. Advisory only — nothing feeds VONA/wheel/TOP PICKS.

Run:  .venv/bin/python tests/test_run.py
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


# A WR/QB/TE-heavy top of board: ADP expects ~zero RBs to go next (the RBs sit at ADP 40+).
BOARD = av([("WR", float(i)) for i in range(1, 9)] + [("QB", 9.0), ("QB", 10.0), ("TE", 11.0),
            ("TE", 12.0)] + [("RB", 40.0 + i) for i in range(8)])

# --- a real run fires: 5 RB reaches (ADP ~45) in the last 8 when ADP expected ~0 ---
run5 = [("RB", 45.0), ("RB", 46.0), None, ("RB", 47.0), ("WR", 3.5), ("RB", 48.0), None, ("RB", 49.0)]
out = advisor._run_read(BOARD, run5, {"RB", "WR"})
check("clear RB run fires HOT", "RB HOT" in out)
check("needed HOT position gets the act-now phrasing", "act before your wheel" in out)
check("line declares itself advisory", "NOT baked into VONA/wheel" in out)
out2 = advisor._run_read(BOARD, run5, {"WR"})
check("un-needed HOT position says let it burn", "RB HOT" in out2 and "let it burn" in out2)

# --- chalk is not a run: 5 RBs off an RB-heavy top of board ---
rb_board = av([("RB", float(i)) for i in range(9, 16)] + [("WR", 16.0), ("WR", 17.0), ("QB", 18.0),
               ("TE", 19.0)])
chalk = [("RB", 1.0), ("RB", 2.0), ("RB", 3.0), ("RB", 4.0), ("RB", 5.0),
         ("WR", 6.0), ("WR", 7.0), ("TE", 8.0)]
check("5 RBs off an RB-heavy board = chalk, no HOT",
      "RB HOT" not in advisor._run_read(rb_board, chalk, {"RB"}))

# --- baseline reconstruction: a chalk run that DRAINED the board must not read as a run. The
# drained available has no RBs near the top, so without adding the window's own picks back the
# RB share would be ~0 and 5 chalk RB picks would look like a giant surprise. ---
drained = av([("WR", 10.0 + i) for i in range(12)] + [("RB", 60.0 + i) for i in range(6)])
chalk_gone = [("RB", 1.0), ("RB", 2.0), ("RB", 3.0), ("RB", 4.0), ("RB", 5.0),
              ("WR", 6.0), ("WR", 7.0), ("WR", 8.0)]
check("window picks are added back to the baseline (chalk stays chalk after draining the board)",
      "RB HOT" not in advisor._run_read(drained, chalk_gone, {"RB"}))

# --- COLD: WR frozen out (0 of 8 vs ~5 expected) while RBs run ---
cold_win = [("RB", 45.0), ("RB", 46.0), ("QB", 9.5), None, ("RB", 47.0), ("TE", 11.5), None,
            ("RB", 48.0)]
out3 = advisor._run_read(BOARD, cold_win, {"WR", "RB"})
check("COLD fires for a needed frozen-out position", "WR COLD" in out3)
check("COLD phrasing sells the value + sequencing, never a fade",
      "falling TO you" in out3 and "COLD never demotes" in out3)
check("HOT and COLD co-report (the run and its mirror)", "RB HOT" in out3)
check("COLD suppressed when the position isn't needed",
      "WR COLD" not in advisor._run_read(BOARD, cold_win, {"RB"}))

# --- zero-expected position drawing 3+ picks IS a run (reaches ADP saw no reason for) ---
noqb = av([("WR", float(i)) for i in range(1, 13)] + [("QB", 45.0), ("QB", 46.0), ("QB", 47.0)])
qb3 = [("QB", 45.0), ("QB", 46.0), ("QB", 47.0), ("WR", 20.0), ("WR", 21.0), ("WR", 22.0), None,
       ("WR", 23.0)]
out4 = advisor._run_read(noqb, qb3, set())
check("3 picks at a zero-share position fires HOT", "QB HOT" in out4)
check("zero-share phrasing shows ~0.0 expected (no ratio blow-up)", "~0.0 expected" in out4)

# --- guards ---
check("fewer than _RUN_MIN_N picks -> silent", advisor._run_read(BOARD, run5[:5], {"RB"}) == "")
check("None recent -> silent", advisor._run_read(BOARD, None, {"RB"}) == "")
check("empty recent -> silent", advisor._run_read(BOARD, [], {"RB"}) == "")
balanced = [("WR", 20.0), ("WR", 21.0), ("QB", 22.0), ("TE", 23.0), ("WR", 24.0), ("QB", 25.0),
            None, ("WR", 26.0)]
check("balanced window -> silent", advisor._run_read(BOARD, balanced, {"RB", "WR"}) == "")
check("missing columns -> silent", advisor._run_read(pd.DataFrame({"x": [1]}), run5, {"RB"}) == "")

# --- integration: a QB run on the REAL board flows into build_context via recent_picks ---
b = pd.read_csv("value_board.csv")
b["position"] = b["pos_label"].str.replace(r"\d+$", "", regex=True)
qbs = b[(b["position"] == "QB") & b["adp_rank"].notna()].nsmallest(5, "adp_rank")
wrs = b[(b["position"] == "WR") & b["adp_rank"].notna()].nsmallest(3, "adp_rank")
gone = pd.concat([qbs, wrs])
avail = advisor.add_vona(b[~b["full_name"].isin(gone["full_name"])].copy(), 18)
recent = ([("WR", float(a)) for a in wrs["adp_rank"]]
          + [("QB", float(a)) for a in qbs["adp_rank"]])
dp = {"slot": 7, "teams": 12, "overall_now": 9, "my_turn": True, "next_pick": 9, "picks_away": 0,
      "following": 18, "total_rounds": 16}
scar = {"QB": 5, "RB": 20, "WR": 20, "TE": 8, "K": 10}
ctx = advisor.build_context(avail, b.iloc[0:0], scar, dp, my_dst=None, drafted_dsts=set(),
                            recent_picks=recent)
check("build_context renders the run line (5-QB run on the real board)",
      "POSITION RUN" in ctx and "QB HOT" in ctx)
ctx0 = advisor.build_context(avail, b.iloc[0:0], scar, dp, my_dst=None, drafted_dsts=set())
check("no recent_picks kwarg -> no run line (old callers unchanged)", "POSITION RUN" not in ctx0)
tp = [l for l in ctx.splitlines() if l.startswith("TOP PICKS NOW")]
tp0 = [l for l in ctx0.splitlines() if l.startswith("TOP PICKS NOW")]
check("advisory only: TOP PICKS identical with and without the run line", tp == tp0 and tp)

print(f"\n{passed} checks passed ✅")
