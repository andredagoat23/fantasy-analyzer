# Engineering Principles (Layer 3 — read once per session)

The non-negotiables. Every one of these exists because violating it caused a real bug this project
has already paid for (see `lessons.md`).

## 1. Diagnose before you fix — with real data
Never theorize a root cause you haven't reproduced. Build the actual failing scenario against the
real board / mailbox / API and watch it fail. Every genuine fix here came from reproducing first;
every wasted edit came from guessing. "It's probably X" is a hypothesis, not a diagnosis.

## 2. Never fabricate
If you don't know something — a player's stat, an API's shape, who "Jake Van Clief" is — look it up
or say you don't know. A confident wrong answer is worse than "let me check." Hallucinated facts are
the #1 enemy of a tool the user trusts on draft day.

## 3. Offload anything that must be correct to Python
LLMs flip comparison directions and miscount. If a number, a membership check, or a pick-timing
decision has to be right, compute it in code and hand the model the answer to read. The advisor does
NO arithmetic anymore — pick numbers, picks-away, roster needs, and wheel-back are all Python
(see `draft-strategy.md`). "We can't afford mistakes" = don't leave math to the model.

## 4. Prefer the reliable signal over the clever one
When two signals can identify something, pick the one that's ground truth, not the one that's
"elegant." Roster membership by *fantasy owner* (ground truth from ESPN) beat membership by *seat
math* (a clever inference that mis-fired). Clever-but-fragile is how you get silent corruption.

## 5. Fix the root cause, not the symptom
"The advisor recommends wrong players" was really "the roster set is polluted." "Reasoning is bad"
was really "VOLS over-rates QBs." Trace one layer past the complaint.

## 6. Walk through before writing; pause for "go"
CLAUDE.md rule #1. Show the change and the why first. It catches bad designs before they cost edits,
and it keeps the 14-yo owner (who is learning) in the loop. Explain Streamlit-specific concepts
(session_state, cache_data, data_editor, reruns); skip Python basics.

## 7. Respect the frozen boundary
Do not touch the pipeline scoring files (`custom_scoring.py`, `compute_metrics.py`,
`compute_outcomes.py`, etc.) unless explicitly asked. If a fix seems to need them, that's a
data-quality flag to raise, not a silent edit.

## 8. Flag data-quality issues; never paper over them
When the data is wrong (Tyreek Hill missing a projection; VOLS over-rating QBs), say so and let the
user decide. Correct it in the layer you're allowed to touch (e.g., the advisor prompt), and flag
the deeper cause. Report test failures with their output.

## 9. Verify with the real thing, then report faithfully
Prove it works against real data/tests/the app before saying "done." Then state plainly what's done,
what's verified, and what's left. No hedging on verified work; no overclaiming on unverified work.

## 10. Keep it minimal
Smallest correct change. No speculative abstractions, no unrequested refactors, no "while I'm here."
Scope creep is the enemy of "efficient and to a T."
