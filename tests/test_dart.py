"""Regression tests for the L31 late-round DART READ (advisor._dart_profiles / _dart_read) and the
GO-screen handcuff (_go_score). Every rule encoded here survived the adversarial research campaign
(2014-25 backtest, 2022-25 holdout); these tests lock the ENCODING, not the research.

Run:  .venv/bin/python tests/test_dart.py
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


def board(rows):
    """(name, pos, adp_pos_rank-ish is in ROLES; here: age, team_implied_total, switched, rookie, draft_pick)"""
    df = pd.DataFrame(rows, columns=["full_name", "position", "age", "team_implied_total",
                                     "switched_team", "is_rookie", "draft_pick"])
    df["pos_label"] = df["position"] + "1"
    df["team"] = "XX"
    df["adp_rank"] = 150.0
    df["total_points"] = 150.0
    return df


FAKE_ROLES = {
    "share wr": {"nn": "share wr", "position": "WR", "share_2025": 0.24, "ppg_2025": 11.0,
                 "weeks_2025": 16, "pos_adp_rank": 50, "nfl_pick": 40},
    "thin wr": {"nn": "thin wr", "position": "WR", "share_2025": 0.10, "ppg_2025": 6.0,
                "weeks_2025": 16, "pos_adp_rank": 52, "nfl_pick": 90},
    "inj vet": {"nn": "inj vet", "position": "WR", "share_2025": 0.25, "ppg_2025": 13.0,
                "weeks_2025": 8, "pos_adp_rank": 55, "nfl_pick": 20},
    "go rb": {"nn": "go rb", "position": "RB", "share_2025": 0.35, "ppg_2025": 9.0,
              "weeks_2025": 17, "pos_adp_rank": 40, "nfl_pick": 60},
    "old qb": {"nn": "old qb", "position": "QB", "share_2025": 0.6, "ppg_2025": 18.0,
               "weeks_2025": 17, "pos_adp_rank": 16, "nfl_pick": 5},
    "clip rb": {"nn": "clip rb", "position": "RB", "share_2025": 0.05, "ppg_2025": 3.0,
                "weeks_2025": 17, "pos_adp_rank": 66, "nfl_pick": 220},
    "young te": {"nn": "young te", "position": "TE", "share_2025": 0.15, "ppg_2025": 5.0,
                 "weeks_2025": 14, "pos_adp_rank": 20, "nfl_pick": 46},
    "vet qb": {"nn": "vet qb", "position": "QB", "share_2025": 0.6, "ppg_2025": 17.0,
               "weeks_2025": 17, "pos_adp_rank": 17, "nfl_pick": 10},
    "moved qb": {"nn": "moved qb", "position": "QB", "share_2025": 0.6, "ppg_2025": 16.0,
                 "weeks_2025": 17, "pos_adp_rank": 18, "nfl_pick": 12},
}

AVAIL = board([
    ("Share WR", "WR", 25.0, 22.0, False, False, float("nan")),
    ("Thin WR", "WR", 24.0, 22.0, False, False, float("nan")),
    ("Inj Vet", "WR", 27.0, 24.0, False, False, float("nan")),
    ("Go RB", "RB", 24.0, 24.0, False, False, float("nan")),
    ("Clip RB", "RB", 26.0, 25.0, False, False, float("nan")),
    ("Young TE", "TE", 23.0, 26.0, False, False, float("nan")),
    ("Vet QB", "QB", 29.0, 25.0, False, False, float("nan")),
    ("Old QB", "QB", 35.0, 25.0, False, False, float("nan")),
    ("Moved QB", "QB", 30.0, 25.0, True, False, float("nan")),
    ("Old WR", "WR", 30.0, 25.0, False, False, float("nan")),
    ("Capless Rook", "RB", 22.0, 24.0, False, True, 150.0),
])
MINE_RISKY_TE = pd.DataFrame([("My TE", "TE1", "ZZ", 0.37, "Boom/Bust", 200.0, 0.6)],
                             columns=["full_name", "pos_label", "team", "p_bust", "risk_tier",
                                      "total_points", "availability"])

_orig = advisor._ROLES
advisor._ROLES = FAKE_ROLES
advisor._ROLES_MTIME = os.path.getmtime(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'role_data.csv'))
try:
    # ---- _go_score ----
    check("GO: committee share + implied + rank = 3", advisor._go_score("go rb", None, 24.0) == 3)
    check("GO: clipboard share, deep rank, good implied = 1 (NO-GO)",
          advisor._go_score("clip rb", None, 25.0) == 1)
    check("GO: NaN implied scores 0 on that component", advisor._go_score("go rb", None, float("nan")) == 2)

    # ---- profiles: buys ----
    buys, fades = advisor._dart_profiles(AVAIL, MINE_RISKY_TE, ["QB"], current_round=15, total_rounds=16)
    check("A1 buy: WR41-65 with share >= 20%", "Share WR" in buys)
    check("thin-share WR is NOT a buy", "Thin WR" not in buys)
    check("B1 buy: GO-screen RB in band", "Go RB" in buys)
    check("B2 buy: proven vet QB (kept team, good offense) while QB open", "Vet QB" in buys)
    check("B6 buy: young high-capital TE when my TE starter is RISKY (hedge scenario)",
          "Young TE" in buys)
    check("buys are priority-ordered: QB profile first", list(buys)[0] == "Vet QB")

    # ---- profiles: fades ----
    check("A3 fade: injury-discount vet (13 ppg, 8 games)", "Inj Vet" in fades)
    check("A12 fade: WR age 29+ (no role row needed)", "Old WR" in fades)
    check("A4 fade: moved late QB", "Moved QB" in fades)
    check("A13 fade: rookie without top-100 capital", "Capless Rook" in fades)
    check("A5 fade: deep-band clipboard RB (rank 66)", "Clip RB" in fades)
    check("QB 33+ fade (worst late-QB age bin)", "Old QB" in fades)

    # ---- gates ----
    b2, _ = advisor._dart_profiles(AVAIL, MINE_RISKY_TE, [], current_round=15, total_rounds=16)
    check("QB profile only while QB is OPEN", "Vet QB" not in b2)
    b3, _ = advisor._dart_profiles(AVAIL, MINE_RISKY_TE, ["QB"], current_round=13, total_rounds=16)
    check("TE dart gated to the FINAL round window (R15+ of 16)", "Young TE" not in b3)
    safe_te = MINE_RISKY_TE.assign(p_bust=0.15, risk_tier="Safe")
    b4, _ = advisor._dart_profiles(AVAIL, safe_te, [], current_round=16, total_rounds=16)
    check("TE dart needs TE open OR a risky TE starter", "Young TE" not in b4)

    # ---- the read line ----
    line = advisor._dart_read(buys, fades, 15)
    check("DART READ fires in bench rounds with the honesty cap",
          line.startswith("DART READ") and "Honesty cap" in line and "1/3" in line)
    check("DART READ silent before the bench rounds", advisor._dart_read(buys, fades, 9) == "")
    check("DART READ silent with nothing to say", advisor._dart_read({}, {}, 14) == "")
finally:
    advisor._ROLES = _orig

print(f"\n{passed} checks passed ✅")
