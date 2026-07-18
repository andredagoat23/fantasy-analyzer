# Stage 02 — Design (Layer 2 contract)

**Goal:** a change plan the user has approved, so implementation is mechanical and low-risk.

## Inputs
- `../../work/diagnosis.md` (from Stage 01).
- `../../reference/draft-strategy.md` if the change touches advisor logic.
- `../../reference/architecture.md` for where the change belongs and what it affects.

## Process
1. **Design the smallest correct change.** Prefer fixing the root cause over patching the symptom;
   prefer moving logic to Python over trusting the LLM with math (see `engineering-principles.md`).
2. **Walk it through line-by-line** for the user — what changes, where, and WHY — before writing
   code. This is CLAUDE.md rule #1 and it is not optional.
3. **Name the blast radius:** which files, which callers, what could regress. Note anything frozen
   (pipeline scoring files) that must NOT be touched.
4. **Pause for "go."** Only clarify with a question if a decision is genuinely the user's to make.

## Outputs
- A short plan (inline to the user, or `../../work/plan.md` for larger work): the exact edits, the
  files, the verification you'll run in Stage 04, and the one-line "why."
- The user's explicit **go**.

## Done when
The user said go (or the change is a trivial, already-authorized mechanical edit). Never start
implementing a substantive change the user hasn't seen.
