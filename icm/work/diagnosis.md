# Diagnosis — "the app overvalued QB (Josh Allen in round 2)"

## The ask (restated)
The mock-draft review flagged that the app took Josh Allen at pick 24 (round 2) and I claimed the
cause was "the board's VOLS over-rates elite rushing QBs." Task: confirm the root cause with real
data before proposing any fix. FROZEN boundary respected — this is diagnosis only, no pipeline edits.

## How VOLS is actually computed (compute_metrics.py, FROZEN)
`VOLS = total_points − replacement_level[position]`, where `replacement_level` = the points of the
**Nth-best** player at the position and N = the startable count. For QB in a 1-QB/12-team league,
N = 12, so QB replacement = **QB12's season points (≈362.6)**. Allen (442.6) − 362.6 = **80.0**.

## Reproduction (value_board.csv)
- Implied replacement pts/pos: QB 362.6, RB 208.4, WR 211.2, TE 176.7, K 151.6.
- Allen VOLS = 80.0 → overall VOLS rank **#21** (RB-tier, matches lesson L3's "VOLS ~80").
- Top-20 by VOLS holds only 2 QB/TE (Allen, McBride/Bowers), so the board is NOT broadly QB-inflated;
  it's specifically that elite QB lands in the low-first-round VOLS band.

## The correction — my earlier claim was half-wrong
"VOLS over-rates QB, so fix it in compute_metrics" is **not** a clean bug, and the obvious fix
BACKFIRES. VOLS = points over QB12 is a textbook VORP number — it's arithmetically correct. And the
direction is counter-intuitive:

| QB replacement baseline | Allen VOLS |
|---|---|
| QB6  | 59 |
| QB8  | 71 |
| **QB12 (current)** | **80** |
| QB18 | 101 |
| QB24 | 141 |

Deepening the baseline (QB12→QB24) makes Allen's VOLS **rise to 141 (rank #7)** — the OPPOSITE of
"wait on QB." To make elite-QB VOLS *smaller* (encourage waiting), the baseline must go *higher*
(QB6–8), which is not a "replacement level" in any standard sense.

## The real root cause (one layer deeper)
The reason to wait on QB in a 1-QB league is **opportunity cost + replacement availability**, not a
VOLS miscalculation:
- RB/WR fall off a cliff — the RB at pick 24 is far better than the RB at pick 96 (scarce).
- QB is flat and deep — a *startable* QB lasts extremely late. In this very mock, **8 startable QBs
  were still on the board at pick 145** (Herbert, Mahomes, Stafford, Murray, Jones, Goff, Mayfield,
  Stroud).
So spending pick 24 on Allen forgoes a scarce RB/WR (Chase Brown, VOLS 100.9, was there at 24) to
lock a position you can refill for ~0 VOLS in the last few rounds. That's the overvaluation — and it
is a *decision/timing* issue, which is precisely what **VONA** exists to encode, not a VOLS bug.

Whether VONA fired correctly at pick 24 is hard to reconstruct exactly from screenshots: pick 24 is a
TURN (I pick 24 AND 25), and `_horizon` uses the "following" pick on my turn, so best_wait/VONA at a
turn behave differently than my simplified reconstruction (which used horizon = my very next pick).
So I can confirm the VOLS number cold, but I should NOT claim the exact live VONA value.

## Fix options (for the user to choose — one crosses the frozen boundary)
- **(A) Frozen pipeline — streaming-aware QB/TE baseline.** Raise the QB (and TE) replacement to
  reflect that your real in-season replacement is a *streamed* QB (~QB8 weekly), which lowers elite-QB
  VOLS and lets them fall naturally. Real modeling decision, needs calibration, touches
  `compute_metrics.py` (frozen) — the user's explicit call. NOT the naive "deepen the baseline," which
  backfires.
- **(B) Advisor layer — opportunity-cost awareness (lower risk).** Leave VOLS/VONA untouched; add a
  small rule so that when a 1-start position (QB/TE) is unfilled but the position is deep on the board
  (many startable left past the next few rounds), the advisor treats an early QB/TE as high
  opportunity cost and prefers the scarce RB/WR. This is the "trust the wait" nudge, in data where the
  model won't fight it (per L8).
- **(C) Accept it.** Early elite QB is a defensible real strategy (Allen's season-points edge over a
  streamer is genuinely ~80–100). This may not be a bug at all — just not the point-maximizing
  wheel-back line.

## Recommendation
Lead with **(B)** — it's inside the app boundary, reversible, and matches the strategy doc's stated
intent ("QB/TE fall on their own"). Only pursue **(A)** if the user wants to re-open the frozen VOLS
model, and if so, calibrate the streaming baseline empirically, don't guess. Do NOT ship the naive
"deepen QB baseline" — proven here to backfire.
