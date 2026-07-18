# Stage 04 — Verify (Layer 2 contract)

**Goal:** PROVE the change does what it should, with real evidence — not "it should work."

## Inputs
- The change from Stage 03.
- Real data sources: `value_board.csv`, the Firebase mailbox, ESPN's public API, the
  `ANTHROPIC_API_KEY` in `.streamlit/secrets.toml` (for advisor calls), the running app.
- `tests/test_bridge.py` and any relevant test.

## Process — pick what actually exercises the change
1. **Pure logic** (`bridge.py`, math, parsing): run `tests/test_bridge.py`; add a case for the new
   behavior and for the failure it fixes. Reproduce the ORIGINAL bug scenario and confirm it's gone.
2. **Advisor / prompt changes:** make a real API call (read the key from secrets) on the actual
   failure case and read the recommendation + reasoning. Verify against the board's real numbers.
3. **App / UI changes:** boot the dev server (`.claude/launch.json` → preview), check `preview_logs`
   for errors, and drive the page to confirm the change renders.
4. **Never assert a number by eye** — compute it in Python and compare.
5. **Check for regressions** in the same area (e.g., run the full test file, not just the new case).

## Outputs
- Verification evidence shown to the user: test output, the real recommendation, a screenshot, or
  the resolved data. If something fails, say so with the output — never paper over it.

## Done when
There is concrete proof the change works AND the original failure no longer reproduces. Anything
less is "I think it works," which is not done.
