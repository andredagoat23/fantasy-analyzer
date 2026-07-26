# Diagnosis — Opponent-aware survival (roadmap #1)

**The ask (restated):** replace the ADP-only "will he last to my next pick" estimate with one that
accounts for the actual roster needs of the specific teams picking between me and my wheel — using
the live-synced rosters we already have. App/advisor layer only. (HANDOFF roadmap #1, user-approved.)

## The gap, reproduced with real data (Jul 20 board)
At slot 7 of 12, on the clock at overall #31 (R3), horizon = #42. Picks 32-41 are seats 8-12
picking twice each — 5 known teams. Current `advisor._survival_prob` (pure logistic of ADP vs
horizon, `_ADP_SCALE = 7`) gives, on the real `value_board.csv`:

    QB  Lamar Jackson   ADP 37.0  P(survives to #42) = 33%
    TE  Trey McBride    ADP 21.0  P(survives to #42) =  5%
    TE  Brock Bowers    ADP 23.5  P(survives to #42) =  7%

Those numbers are IDENTICAL whether the 5 wheel teams all have their QB/TE filled (true survival
high — only a rare double-up takes one) or all still need one (true survival ≈ 0). Roster-blind.

## Root cause (one sentence)
Survival is computed from ADP alone (`_survival_prob`, advisor.py:346), while the identity and
rosters of the exact teams picking in the now→horizon window — owner ground truth present in every
sync path — are discarded (`bridge.resolve` keeps only name *sets*; per-pick `team` is dropped).

## What the data already provides (verified in code)
- **Bridge/userscript** (`bridge.py`): every pick row is `{pick, player, team, mine}` — owner name
  per pick. `resolve()` currently reduces to sets; raw rows are available in the poller (draft.py:355).
- **Sleeper** (`sleeper_sync._normalize`): emits the same shape; `team` = "Team {slot}" from
  `draft_slot` — owner ground truth.
- **ESPN API** (`espn_sync.fetch_picks`): each pick has `team_id`, `team_name`, `overall`.
- **Snake math** exists for MY picks (draft.py:446); the same formula gives the seat for ANY overall
  pick. Seat→owner is derivable from observed (pick_no, team) pairs — evidence, not guesswork.

## Where survival is consumed (the blast radius)
1. `add_vona` (advisor.py:359) — `best_wait` expectation per position → VONA. Computed ONCE in
   draft.py:465 and shared by the board column and the advisor context.
2. `_wheel_label` (advisor.py:390) — gone/risky/safe, hard ADP cutoffs (same roster-blind idea).
3. `_pos_punt_loss` (advisor.py:420) — survival at the ~5-rounds-out fill window (mostly beyond the
   known-team window; ADP blur dominates there).

## Prior art / lessons checked
- Bridge seat-math misfire (bridge.py docstring, L4-adjacent): seat inference must NEVER assign
  players to rosters. Rosters stay keyed by owner name (ground truth); seat math only predicts WHO
  picks in the window, validated against observed picks.
- L8: anything the model must respect goes IN DATA — the adjusted survival lands in the same
  vona/wheel columns the model already reads; plus a Python-computed window summary line.
- Stress-engine bots (12_full_system_stress.py) are pure ADP-samplers (top-12-by-ADP pool) — no
  existing opponent model to stay consistent with; the top-12 pool notion is reusable as the
  demand-share baseline.

## Files involved (expected)
`advisor.py` (survival + context), `bridge.py` (additive pure helper), `app_pages/draft.py`
(compute/store opponent context, pass through), `tests/`. NO frozen pipeline files.
