"""Regression tests for the cohort sanity-pull (cohort_pull.py, L32).

What this locks in — the pull nudges rank_composite by cohort_trimmed (>1.0 = the player's 15 nearest
historical comps BEAT his price), as a BOUNDED sanity-pull, never a re-rank:

1. A startable "beats price" player moves UP (negative nudge); an "overpay" moves DOWN (positive).
2. Deadband: a near-fair cohort (|trimmed-1.0| < DEAD) is a no-op.
3. Cap: no nudge exceeds ±CAP no matter how extreme the multiplier (dodges the L29 cheap-backup blow-up).
4. Startable gate: a bench/handcuff (p_startable < GATE) is NOT lifted — its contingent value is the
   DART/HANDCUFF read's job (no double-count) — but an overpay bench player can still be pushed DOWN.
5. Freeze: the consensus top (rank <= FREEZE) is untouched — the efficient top isn't scrambled.
6. No name-match / missing CSV => a clean no-op (feature off, never a crash).

Run:  .venv/bin/python tests/test_cohort_pull.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

import cohort_pull as cp

passed = 0


def check(label, cond):
    global passed
    assert cond, f"FAIL: {label}"
    passed += 1
    print(f"  ok  {label}")


# --- the pure core: nudge() at default knobs (SCALE=30, DEAD=0.08, CAP=4, GATE=0.40, FREEZE=8) ---
board = pd.DataFrame({
    "full_name":      ["Up", "Down", "Fair", "Huge", "BenchUp", "BenchDown", "TopFrozen", "NoMatch"],
    "rank_composite": [50,    51,     52,     53,     54,        55,          5,           56],
    "p_startable":    [0.80,  0.80,   0.80,   0.80,   0.20,      0.20,        0.80,        0.80],
}).set_index("full_name", drop=False)

trimmed = pd.Series({
    "Up": 1.20, "Down": 0.80, "Fair": 1.03, "Huge": 5.00,
    "BenchUp": 1.30, "BenchDown": 0.70, "TopFrozen": 0.50,   # "NoMatch" deliberately absent
})
n = cp.nudge(board, trimmed)

check("beats-price startable moves UP (negative nudge)", n["Up"] < 0)
check("overpay moves DOWN (positive nudge)", n["Down"] > 0)
check("near-fair cohort is deadbanded to 0", n["Fair"] == 0.0)
check("extreme multiplier is capped at -CAP", n["Huge"] == -cp.CAP)
check("symmetric down-cap: overpay clipped to +CAP", n["Down"] == cp.CAP)          # dev -0.20 * 30 = 6 -> +4
check("startable gate: a bench player is NOT lifted", n["BenchUp"] == 0.0)
check("gate is one-directional: an overpay bench player still sinks", n["BenchDown"] > 0)
check("freeze: a top-8 player is untouched despite a huge deviation", n["TopFrozen"] == 0.0)
check("no name-match is a no-op", n["NoMatch"] == 0.0)

# --- knobs actually parameterize (a stronger cap lets the beats-price player move further) --------
n_cap6 = cp.nudge(board, trimmed, cap=6)
check("cap knob widens the clip (Up moves past the default -4 toward ~-6)",
      n_cap6["Up"] < n["Up"] and n_cap6["Up"] >= -6 - 1e-9)
n_freeze0 = cp.nudge(board, trimmed, freeze=0)
check("freeze=0 lets the former top-8 player move", n_freeze0["TopFrozen"] != 0.0)
n_gate0 = cp.nudge(board, trimmed, gate=0.0)
check("gate=0 lets the bench player get lifted", n_gate0["BenchUp"] < 0)

# --- apply_pull(): end-to-end read + re-rank -----------------------------------------------------
full = pd.DataFrame({
    "full_name":      ["A", "B", "C", "D", "E"],
    "rank_composite": [20,  21,  22,  23,  24],
    "p_startable":    [0.9, 0.9, 0.9, 0.9, 0.9],
})
with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
    pd.DataFrame({"full_name": ["A", "B", "C", "D", "E"],
                  "cohort_trimmed": [1.30, 1.00, 1.00, 1.00, 0.70]}).to_csv(f.name, index=False)
    csv_path = f.name
out = cp.apply_pull(full, path=csv_path)
os.unlink(csv_path)

check("apply_pull preserves the raw rank as rank_composite_base", list(out["rank_composite_base"]) == [20, 21, 22, 23, 24])
check("apply_pull returns integer ranks", out["rank_composite"].dtype.kind == "i")
check("beats-price A ends up ranked above the fair middle", out.loc[out.full_name == "A", "rank_composite"].iloc[0] == out["rank_composite"].min())
check("overpay E ends up ranked last", out.loc[out.full_name == "E", "rank_composite"].iloc[0] == out["rank_composite"].max())
check("apply_pull does not mutate the caller's frame", "rank_composite_base" not in full.columns)

# --- missing / unreadable CSV => board returned unchanged, no crash ------------------------------
safe = cp.apply_pull(full, path="/no/such/cohort_file.csv")
check("missing CSV: rank_composite unchanged", list(safe["rank_composite"]) == [20, 21, 22, 23, 24])
check("missing CSV: no partial columns added", "rank_composite_base" not in safe.columns)

print(f"\n{passed} checks passed ✅")
