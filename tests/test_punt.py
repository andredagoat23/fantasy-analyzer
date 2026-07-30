"""Regression tests for the PUNT READ math (advisor._pos_punt_loss / _expected_best_survivor, L28).

What this locks in — and what it deliberately does NOT do:

  punt_loss = elite RISK-ADJ VOLS now − E[best RISK-ADJ VOLS still there at the fill window]

1. BOTH sides are risk-adjusted. The old form discounted only the fallback and left the elite raw,
   which inflated every punt_loss (apples-to-oranges).
2. The fallback is the EXPECTED BEST SURVIVOR over the whole pool, not one player — so a DEEP,
   streamable position correctly costs less to defer. That depth is the real "punt" value.
3. There is NO safety margin. A "QB/TE should fall" margin was tried and REMOVED: on the real pick-29
   board it demoted Josh Allen (VONA 50.7 vs the best RB's 13.3, higher risk-adj VOLS/ceiling/P(elite),
   LOWER cohort bust) for a worse player. The metrics decide; a positional prior gets no veto.

Run:  .venv/bin/python tests/test_punt.py
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


def pool(rows):   # (name, pos, vols, adp, bust)
    return pd.DataFrame(rows, columns=["full_name", "position", "vols", "adp_rank", "p_bust"])


LATE = 89   # fill window used throughout
# `_pos_punt_loss` now takes MY snake schedule (not `teams`) so it can measure which round a streamer
# actually lasts to at MY pick — the old `floor(ADP/teams)+1` reported the round the MARKET drafts him
# in and ignored the slot entirely. Slot 1 of 12 puts a pick at #73 and #96, straddling LATE=89.
SCHED = advisor.my_pick_schedule(1, 12, 16)

# --- _expected_best_survivor: depth is rewarded -------------------------------------------------
thin = pool([("Only One", "QB", 20.0, 89.0, 0.0)])                      # 1 option, ~50% survival
deep = pool([("Only One", "QB", 20.0, 89.0, 0.0)]                       # same top option ...
            + [(f"Backup{i}", "QB", 18.0, 130.0, 0.0) for i in range(4)])  # ... plus safe backups
e_thin = advisor._expected_best_survivor(thin, LATE, risk_adj=False)
e_deep = advisor._expected_best_survivor(deep, LATE, risk_adj=False)
check("expected-best-survivor rewards DEPTH (streaming value)", e_deep > e_thin + 5)
check("thin pool ~= top option x its survival", 8.0 < e_thin < 12.0)

# risk adjustment scales the expectation down
e_risky = advisor._expected_best_survivor(
    pool([("Bust Prone", "QB", 20.0, 130.0, 0.5)]), LATE, risk_adj=True)
check("risk_adj scales the fallback by (1 - p_bust)", 9.0 < e_risky < 11.0)

# --- _pos_punt_loss: both sides risk-adjusted ---------------------------------------------------
p = pool([("Elite", "QB", 100.0, 10.0, 0.20), ("Late", "QB", 20.0, 130.0, 0.0)])
r = advisor._pos_punt_loss(p, "QB", LATE, SCHED)
# elite risk-adj = 100*0.8 = 80 ; fallback ~= 20  ->  punt_loss ~= 60 (NOT 100-20=80)
check("elite is risk-adjusted too (not left raw)", 55.0 < r["punt_loss"] < 65.0)

# --- depth changes the verdict, as it should ----------------------------------------------------
thin_pos = pool([("Elite", "QB", 100.0, 10.0, 0.0), ("Late", "QB", 10.0, 89.0, 0.0)])
deep_pos = pool([("Elite", "QB", 100.0, 10.0, 0.0)]
                + [(f"Streamer{i}", "QB", 60.0, 130.0, 0.0) for i in range(4)])
lt = advisor._pos_punt_loss(thin_pos, "QB", LATE, SCHED)["punt_loss"]
ld = advisor._pos_punt_loss(deep_pos, "QB", LATE, SCHED)["punt_loss"]
check("a DEEP streamable position costs less to defer than a thin one", ld < lt - 20)

# --- _punt_read: bare comparison, NO margin -----------------------------------------------------
board = pd.concat([
    pool([("QB Elite", "QB", 100.0, 10.0, 0.0), ("QB Late", "QB", 60.0, 130.0, 0.0)]),   # deep QB
    pool([("RB Elite", "RB", 90.0, 15.0, 0.0), ("RB Late", "RB", 5.0, 130.0, 0.0)]),     # thin RB
    pool([("WR Elite", "WR", 40.0, 20.0, 0.0), ("WR Late", "WR", 5.0, 130.0, 0.0)]),
])
reads, bar = advisor._punt_read(board, ["QB"], 29, 12)
check("deep QB + scarce RB -> QB is PUNT-ABLE on the merits", reads["QB"]["punt_able"])
check("no margin applied: cliff_bar IS the RB/WR bar", abs(reads["QB"]["cliff_bar"] - bar) < 1e-9)

# flip it: a THIN QB pool behind the elite -> genuine cliff, grab him
board2 = pd.concat([
    pool([("QB Elite", "QB", 100.0, 10.0, 0.0), ("QB Late", "QB", 2.0, 130.0, 0.0)]),    # thin QB
    pool([("RB Elite", "RB", 60.0, 15.0, 0.0), ("RB Late", "RB", 40.0, 130.0, 0.0)]),    # deep RB
    pool([("WR Elite", "WR", 40.0, 20.0, 0.0), ("WR Late", "WR", 30.0, 130.0, 0.0)]),
])
reads2, _ = advisor._punt_read(board2, ["QB"], 29, 12)
check("thin QB pool + deep RB -> QB is a real CLIFF (grab)", not reads2["QB"]["punt_able"])

# --- the "lasts ~Rn" claim is now MEASURED, not floor(ADP/teams) --------------------------------
# Regression: `lasts_round` used to be the round the MARKET drafts him in, rendered as the round he
# LASTS TO, with no probability and no awareness of my slot. See tests/test_schedule.py for the full
# treatment; these two checks keep _pos_punt_loss's own contract honest.
lr = advisor._pos_punt_loss(
    pool([("Elite", "QB", 100.0, 10.0, 0.0), ("Streamer", "QB", 60.0, 130.0, 0.0)]),
    "QB", LATE, SCHED)
check("a named streamer carries a measured survival probability", lr["lasts_p"] is not None)
check("that probability clears the streamer floor", lr["lasts_p"] >= advisor._PUNT_STREAM_P)
check("the round comes from MY schedule, not floor(ADP/teams)",
      lr["lasts_round"] in [r for r, _ in SCHED])

# no slot -> we cannot place the snake, so the fill window falls back to the old flat estimate and the
# round is simply not claimed (never guessed)
reads3, _ = advisor._punt_read(board, ["QB"], 29, 12)          # slot omitted
check("no slot: still produces a verdict without inventing a round",
      "punt_able" in reads3["QB"] and reads3["QB"]["lasts_round"] is None)

print(f"\n{passed} checks passed ✅")
