# Stage 03 — Implement (Layer 2 contract)

**Goal:** make the approved change cleanly, matching the code around it.

## Inputs
- The approved plan (`../../work/plan.md` or the inline walkthrough).
- `../../reference/architecture.md` for conventions and file roles.
- The target files themselves — read before editing.

## Process
1. **Match the surrounding code** — comment density, naming, idiom. New code should read like it was
   always there.
2. **Keep diffs minimal and focused.** One concern per change. Don't refactor unrelated code, add
   speculative abstractions, or "improve" things the user didn't ask about.
3. **Respect the frozen boundary.** Do not edit `custom_scoring.py`, `compute_metrics.py`,
   `compute_outcomes.py`, or the other pipeline scoring files unless the user explicitly asked. If a
   fix seems to need them, that's a data-quality flag for the user, not a silent edit.
4. **Prefer determinism over LLM judgment for anything numeric.** If the model is doing arithmetic
   or membership checks that must be right, compute it in Python and hand it over (see the wheel-back
   and roster-need patterns in `draft-strategy.md`).

## Outputs
- The edits, syntactically valid.

## Done when
The change is in and imports/parses clean. Do not claim it works yet — that's Stage 04.
