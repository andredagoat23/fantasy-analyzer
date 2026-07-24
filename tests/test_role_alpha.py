"""Regression tests for the WR alpha target-competition gate (advisor._role_bonus_series + role_alpha_ok, L34).

A nominal "team WR1" by projection is only a LOCKED-TARGET alpha if no same-team RB/TE out-targets him.
`role_alpha_ok` (computed in draft.load_board from best-demonstrated target share vs the top same-team
RB/TE share) gates the WR's POSITIVE role nudge. Fixes Mike Evans (SF "WR1" by projection but 3rd in
targets behind CMC + Kittle) without touching genuine alphas or the negative "behind the alpha" nudge.

Run:  .venv/bin/python tests/test_role_alpha.py
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


df = pd.DataFrame({
    "position":      ["WR",  "WR",  "WR",  "RB",  "WR",   "WR"],
    "role_lead":     [40.0,  40.0,  -40.0, 40.0,  40.0,   40.0],
    "role_env_ok":   [True,  True,  True,  True,  False,  True],
    "role_alpha_ok": [True,  False, False, False, True,   True],
})
n = advisor._role_bonus_series(df)

check("real alpha WR (alpha_ok) keeps his +nudge (capped)", n.iloc[0] == advisor._ROLE_CAP)
check("nominal WR1 out-targeted by an RB/TE (not alpha_ok) LOSES the +nudge", n.iloc[1] == 0.0)
check("a WR BEHIND the alpha keeps his negative nudge (gate is +only)", n.iloc[2] == -advisor._ROLE_CAP)
check("an RB is NOT gated by the WR alpha check (keeps +nudge)", n.iloc[3] == advisor._ROLE_CAP)
check("role_env_ok still zeroes a bad-offense role nudge", n.iloc[4] == 0.0)
check("a normal alpha WR is unaffected", n.iloc[5] == advisor._ROLE_CAP)

# backward compatible: no role_alpha_ok column -> nobody is stripped (old behaviour)
n2 = advisor._role_bonus_series(df.drop(columns=["role_alpha_ok"]))
check("no role_alpha_ok column -> WR keeps his +nudge (backward compatible)", n2.iloc[1] == advisor._ROLE_CAP)

print(f"\n{passed} checks passed ✅")
