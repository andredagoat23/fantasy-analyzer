"""Regression test for the WHEEL CELL REFERENT (advisor._wheel_cell + the DRAFT POSITION binding).

THE BUG THIS LOCKS OUT. `_wheel_label` renders gone/risky/safe against `_horizon(draft_pos)`, which
returns `following` when it IS my turn but `next_pick` when it is NOT. Pre-draft at slot 2 the context
therefore said `wheel: safe` for a player computed against my ON-DECK pick #2 — while the same
DRAFT POSITION line also named #23 — and nothing anywhere stated which pick the column meant. The
advisor read the two together and told the user an ADP-14.3 RB was "safe to #23" (true survival to
#23: 9.0%). The prompt made it worse by handing the model an output template containing "#X" that it
was never given a value for.

Fix, in two stages:
  TIER 1 (display-only) — the cell carries its own referent (`gone→#23`) and the not-my-turn DRAFT
    POSITION line states which pick the column was computed to, the way the my-turn branch always had.
  TIER 2 (behaviour) — `_horizon()` now returns `following` in BOTH turn states. It used to return
    `next_pick` when it was not my turn, i.e. the pick I am ABOUT to make — and I cannot lose anyone
    before a pick I already hold, so every "will he still be there?" number was answered against the
    wrong pick. With both stages in, the ADP-14.3 RB reads `gone→#23`: the true answer (9.0%).
    `app_pages/draft.py` now calls `advisor._horizon` too, so the board's VONA column and the advisor's
    context can never desync — that duplication is what made this a two-place bug in the first place.

WHY THIS SUITE EXISTS AT ALL: every other unit suite and every offline mock (12_/13_/14_/45_) sets
`my_turn: True`, so the not-my-turn branch of `_horizon` — the exact branch used for pre-draft
strategy talk — had no coverage. 238 checks and 19,200 simulated picks never touched it.

Group D deliberately pins `_wheel_label`'s CURRENT rule (raw ADP arithmetic, flat 12-pick cushion).
Tier 2's HORIZON half has shipped; re-basing this RULE on the measured `_survival_prob` curve has NOT
— when that happens these checks MUST go red so the change is made on purpose, not by accident.

Fixtures are SYNTHETIC on purpose: `run_all.py` refreshes ESPN ADP the morning of the draft, so a test
pinned to a live player's ADP would go red on Aug 7 — the worst possible moment.

Run:  .venv/bin/python tests/test_wheel.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

import advisor

passed = 0

CELL_RE = re.compile(r"(gone|risky|safe)→#(\d+)")


def check(label, cond):
    global passed
    assert cond, f"FAIL: {label}"
    passed += 1
    print(f"  ok  {label}")


# ---------------------------------------------------------------- fixtures
# build_context needs the full board schema (age, target_share_2025, team_implied_total, ...), so the
# frame is built from the REAL board's columns and then every field this test asserts on is OVERWRITTEN
# with a controlled value. That keeps the suite regen-proof — `run_all.py` can move any live ADP on
# draft morning without touching these numbers — while still failing loudly if the schema changes.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REAL = pd.read_csv(os.path.join(_ROOT, "app_data.csv"))

ROWS = [                                   # (name, pos, adp, vols)
    ("Test Back", "RB", 14.3, 112.0),      # the regression player: was safe→#2, now gone→#23
    ("Early WR", "WR", 3.0, 140.0),        # gone at any realistic horizon
    ("Mid RB", "RB", 30.0, 90.0),
    ("Late WR", "WR", 60.0, 70.0),         # safe at any realistic horizon
    ("Deep TE", "TE", 90.0, 40.0),
]

BOARD = _REAL.head(len(ROWS)).copy().reset_index(drop=True)
BOARD["full_name"] = [r[0] for r in ROWS]
BOARD["position"] = [r[1] for r in ROWS]
BOARD["pos_label"] = [f"{r[1]}{i + 1}" for i, r in enumerate(ROWS)]
BOARD["adp_rank"] = [r[2] for r in ROWS]
BOARD["vols"] = [r[3] for r in ROWS]
BOARD["rank_composite"] = range(1, len(ROWS) + 1)
BOARD["overall_rank"] = range(1, len(ROWS) + 1)
BOARD["team"] = "BUF"                      # non-FA so the L15 unsigned-FA drop can't remove them
BOARD["proj_outlier"] = False              # so the L17 outlier drop can't remove them
BOARD["p_startable"] = 0.7
BOARD["p_bust"] = 0.25
BOARD["market"] = "fair"
if "no_team" in BOARD.columns:
    BOARD["no_team"] = False
EMPTY_ROSTER = BOARD.head(0)
SC = {"QB": 5, "RB": 20, "WR": 30, "TE": 8, "K": 5}


def dp(my_turn, next_pick=2, following=23, overall_now=1):
    return {"slot": 2, "teams": 12, "overall_now": overall_now, "my_turn": my_turn,
            "next_pick": next_pick, "picks_away": next_pick - overall_now, "following": following}


def ctx_for(d):
    h = advisor._horizon(d)
    av = advisor.add_vona(BOARD.copy(), h) if h else BOARD.copy()
    return advisor.build_context(av, EMPTY_ROSTER, SC, d)


def cells(text):
    return CELL_RE.findall(text)


def cell_for(text, name):
    """Just the wheel cell(s) attached to `name`. Scoped deliberately: the TOP PICKS shortlist puts
    EVERY entry on one line, so a whole-line search leaks other players' labels in."""
    out = set()
    for seg in re.split(r" \| |\n", text):
        if name in seg:
            out |= {f"{a}→#{p}" for a, p in CELL_RE.findall(seg)}
    return out


# =============================================================== A. referent present + correct
print("\nA. every wheel cell carries its referent, and the referent is the horizon actually used")

ctx_off = ctx_for(dp(my_turn=False))
ctx_on = ctx_for(dp(my_turn=True))

check("not-my-turn: context renders at least one wheel cell", len(cells(ctx_off)) >= 1)
check("my-turn: context renders at least one wheel cell", len(cells(ctx_on)) >= 1)
check("not-my-turn: no bare label survives (every gone/risky/safe in a table row has a →#pick)",
      all(CELL_RE.search(ln) for ln in ctx_off.splitlines()
          if re.search(r"\b(gone|risky|safe)\b", ln) and "Test Back" in ln))
check("not-my-turn: every cell's pick == following (23) — was next_pick before L52 Tier 2",
      {int(p) for _, p in cells(ctx_off)} == {23})
check("my-turn: every cell's pick == following (23)",
      {int(p) for _, p in cells(ctx_on)} == {23})
check("both turn states now render the SAME referent (one wait-decision, one horizon)",
      {int(p) for _, p in cells(ctx_off)} == {int(p) for _, p in cells(ctx_on)})

# =============================================================== B. the exact regression
print("\nB. the exact failure: an ADP-14.3 RB pre-draft at slot 2")

row_off = [ln for ln in ctx_off.splitlines() if "Test Back" in ln]
row_on = [ln for ln in ctx_on.splitlines() if "Test Back" in ln]
back_off, back_on = cell_for(ctx_off, "Test Back"), cell_for(ctx_on, "Test Back")
check("not-my-turn: the ADP-14.3 RB now reads gone→#23 — the TRUE answer to the question asked",
      back_off == {"gone→#23"})
check("my-turn: the same player also reads gone→#23", back_on == {"gone→#23"})
# A bare `"safe→#23" not in ctx` would be WRONG now: with the horizon at #23 a genuinely deep player
# (Late WR, ADP 60) is correctly safe→#23. The bug was never "the string exists" — it was THIS player
# being called safe to a pick he cannot reach. Hence cell_for().
check("THE BUG: the ADP-14.3 RB is never labeled safe, at any referent",
      not any(c.startswith("safe") for c in back_off))
check("THE BUG: and never safe to my on-deck pick", "safe→#2" not in back_off)
check("a genuinely deep player IS still allowed to read safe→#23 (no blanket suppression)",
      cell_for(ctx_off, "Late WR") == {"safe→#23"})
check("both turn states now AGREE for the same player (Tier 2: one wait-horizon)",
      advisor._wheel_label(14.3, advisor._horizon(dp(False)))
      == advisor._wheel_label(14.3, advisor._horizon(dp(True))))
check("_horizon returns following when it is NOT my turn (it returned next_pick — the bug)",
      advisor._horizon(dp(False)) == 23)
check("_horizon returns following when it IS my turn", advisor._horizon(dp(True)) == 23)
check("_horizon is None at the last pick — there is no wait-decision left",
      advisor._horizon(dp(True, following=None)) is None)

# =============================================================== C. the DRAFT POSITION binding
print("\nC. the DRAFT POSITION line states which pick the column was computed to")

dpl_off = next(ln for ln in ctx_off.splitlines() if ln.startswith("DRAFT POSITION"))
dpl_on = next(ln for ln in ctx_on.splitlines() if ln.startswith("DRAFT POSITION"))
check("not-my-turn line binds the column to #23, the wait-pick", "computed to #23" in dpl_off)
check("not-my-turn line spells out what a 'safe' would mean", "safe to #23" in dpl_off)
check("not-my-turn line explains #2 is a pick I already hold", "already hold" in dpl_off)
check("not-my-turn line still names both picks", "up next at #2" in dpl_off and "Then #23" in dpl_off)
check("my-turn line keeps its existing binding", "wheel` column already says who lasts until then" in dpl_on)

ctx_last = ctx_for(dp(my_turn=False, next_pick=192, following=None, overall_now=191))
check("no `following` (final pick): horizon is None so NO wheel cell renders at all",
      not cells(ctx_last))
check("no `following`: no binding note, no crash", "computed to #" not in ctx_last)

# =============================================================== D. rule lock (Tier 2 tripwire)
print("\nD. _wheel_label's CURRENT rule is pinned — Tier 2 must break these on purpose")

check("adp before the horizon -> gone", advisor._wheel_label(10.0, 23) == "gone")
check("adp exactly AT the horizon -> gone (boundary)", advisor._wheel_label(23.0, 23) == "gone")
check("adp a full round past -> safe", advisor._wheel_label(40.0, 23) == "safe")
check("adp exactly horizon+12 -> safe (boundary)", advisor._wheel_label(35.0, 23) == "safe")
check("adp inside the round -> risky", advisor._wheel_label(30.0, 23) == "risky")
check("no ADP (undrafted) -> safe", advisor._wheel_label(float("nan"), 23) == "safe")

# =============================================================== E. opponent-aware / fractional eff
print("\nE. a fractional opponent-adjusted horizon never leaks a fake pick number")

check("fractional eff labels off eff but displays the REAL pick",
      advisor._wheel_cell(14.3, 21.37, 23) == "gone→#23")
check("no '.' ever reaches a rendered pick number",
      "." not in advisor._wheel_cell(14.3, 21.37, 23).split("#")[1])
check("label still tracks the effective horizon, not the shown pick",
      advisor._wheel_cell(30.0, 2.0, 2) == "safe→#2"
      and advisor._wheel_cell(30.0, 25.0, 2) == "risky→#2")
check("numpy float horizon renders cleanly (eff values are numpy floats)",
      advisor._wheel_cell(14.3, np.float64(21.37), np.float64(23.0)) == "gone→#23")

print(f"\nALL {passed} CHECKS PASS")
