# Diagnosis — Positional-run detection (roadmap #3) · Jul 28, 2026

## The ask (restated)
Build roadmap #3: detect a positional RUN in the live pick stream — "5 of the last 8 picks were
RBs → the cliff is NOW" — and surface it to the advisor. A feature, not a bug; "root cause" here =
the gap the feature fills and where the data lives.

## The gap (why the current math can't see a run)
Survival/VONA/wheel price "will he last to my next pick" from two signals only:
1. **ADP** — a season-long market AVERAGE (`_survival_prob`, logistic of adp_rank vs horizon).
2. **Opponent rosters** (L40, `opponent_read`) — the NEEDS of the specific teams before my wheel,
   shifting per-position effective horizons.

Neither sees the observed **rate** of the live room. When 5 of the last 8 picks are RBs, the room is
draining RB ~2× faster than the ADP average assumed — every RB survival estimate is optimistic — and
the reverse position (say 0 WR of 8 vs ~3 expected) is lasting LONGER than priced. Runs/herding are
real draft-room behavior; ADP by construction cannot encode sequence momentum.

## The data (verified in code — the feature costs no new source)
- **`st.session_state.sync_picks`** = the ordered raw pick list `[{"pick": N, "team": ..., "player":
  ...}, ...]`, set by ALL THREE sync paths: Sleeper (draft.py:355), browser bridge (draft.py:423),
  ESPN API (draft.py:477-480). Already consumed by the opponent-aware read (draft.py:524-530).
- Positions/ADP for picked names resolve via the full `board` df (a cached name→(pos, adp) map, same
  pattern as `board_pos_map`, draft.py:177).
- **Manual (non-synced) mode has NO ordered history** — `drafted` is a set. Run detection is
  live-sync-only; absent sync → the read is silently off (matches the "missing CSV = feature off"
  convention).

## Where it belongs (pattern match)
An advisor READ, computed in Python (principle #3), following the existing read-stack shape:
- Computation: a new `_run_read()` in `advisor.py` (like `_punt_read`/`opponent_read`).
- Delivery: a new `POSITION RUN` context line in `build_context` (placed with `opp_line`, the other
  live-market read) + a durable interpretation paragraph in SYSTEM (like the POSITION SHAPE pairing).
- Wiring: `draft.py` passes an ordered `(position, adp)` list via a new `build_context` kwarg,
  default `None` → byte-identical old behavior for every existing caller (stress suites included).

## Key modeling decisions (for stage 02)
- **Baseline = what ADP expected**, not a flat 1/4: each position's share of the top-12-by-ADP pool
  **as of the window start** (current `available` + the window's own picks added back, so a run
  doesn't drain its own baseline and overstate its surprise).
- **Surprise = plain binomial tail** (coin-flip math, `math.comb` closed form, no scipy): HOT when
  P(X ≥ k) is small, COLD when P(X ≤ k) is small. Significance levels, not fitted knobs.
- **Advisory line ONLY in v1 — no VONA/wheel/horizon modification.** We have no data to validate a
  run-continuation magnitude (ADP is an average; we hold no pick-by-pick draft corpus), and the
  project rule is: unvalidated knobs don't ship into the math (cf. L28, L45/L46 validation rhythm).
  The opp-read's `eff` horizon plumbing is the natural v2 slot IF mocks show it's needed.

## Files involved
`advisor.py` (new read + context line + SYSTEM note), `app_pages/draft.py` (ordered-picks wiring),
`tests/test_run.py` (new). Frozen pipeline: untouched. Plan: `icm/work/plan.md`.
