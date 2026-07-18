# Stage 05 — Ship (Layer 2 contract)

**Goal:** land verified work and capture anything learned, without surprising the user.

## Inputs
- The verified change + its evidence (Stage 04).
- `../../reference/lessons.md` (to append to, if a new lesson emerged).

## Process
1. **Commit when the change is verified.** Stage specific files (not `git add -A` blindly). Write a
   message that says what changed and WHY, and end with:
   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
   This repo commits directly to `main` (its established convention); commits are local until pushed.
2. **Do NOT push / deploy unless the user asks.** Pushing `main` auto-deploys to Streamlit Cloud —
   that's the user's call, every time.
3. **Capture the lesson.** If this fix corrected a wrong assumption or a class of bug, add a short
   entry to `reference/lessons.md` so it never repeats. If it changed how a subsystem works, update
   the relevant `reference/*.md` and the user's memory index.
4. **Report faithfully.** State what's done and verified plainly; if a step was skipped or a test
   failed, say so.

## Outputs
- A commit on `main`; updated reference docs / lessons where warranted; a clear status to the user.

## Done when
Work is committed, docs reflect reality, and the user knows exactly what landed and what (if
anything) is left — including that the deploy push is still theirs to make.
