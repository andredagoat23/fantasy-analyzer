# Stage 01 — Understand (Layer 2 contract)

**Goal:** know exactly what's being asked and, for a bug, the ROOT CAUSE — before any code changes.
Skipping this stage is how we shipped fixes for the wrong thing.

## Inputs
- The user's request (verbatim — don't reinterpret it into something easier).
- `../../reference/lessons.md` — has this exact class of bug happened before?
- The relevant subsystem doc (`../../reference/architecture.md`, `bridge.md`, `draft-strategy.md`).
- REAL data: `value_board.csv`, the live Firebase mailbox, the ESPN API, the running app — whatever
  the issue actually touches.

## Process
1. **Restate the ask** in one line. If it's ambiguous and the answer changes what you do, ASK
   (a wrong assumption here wastes the whole pipeline — see the "hallucinating picks" lesson).
2. **Reproduce with real data.** Build the actual failing scenario in Python / the app and observe
   it. Do not theorize a cause you haven't seen. (Every real fix this session came from reproducing
   first: the Dak pick, the Allen VOLS=80, the roster pollution.)
3. **Find the root cause, not the symptom.** "The advisor picked wrong" was really "the roster set
   was polluted." Trace one layer deeper than the surface complaint.
4. **Check `lessons.md`** for prior art and for what NOT to try.

## Outputs
- A crisp diagnosis written to `../../work/diagnosis.md`: the ask restated, the reproduction, the
  confirmed root cause, and the files involved. This is the input to Stage 02.

## Done when
You can state the root cause in one sentence and point to the reproduction that proves it. If you
can't, you are not done — do not proceed to design.
