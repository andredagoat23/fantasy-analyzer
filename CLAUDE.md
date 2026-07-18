# PROJECT CONTEXT — Fantasy Football Draft Assistant

## ⭐ START HERE — how work gets done (ICM)
This project runs on **ICM (Interpretable Context Methodology)**: `icm/` is a filesystem-as-methodology
workspace that governs *how work gets done here* so every change is reproduced, designed, verified,
and shipped — not ad-hoc (ad-hoc caused this project's worst bugs). **Before acting on any request,
read `icm/CONTEXT.md`** (the router) and route the work through its stages.

Prime directive: do whatever the user asks **efficiently and to a T** — reproduce before fixing,
verify with REAL data before claiming done, never fabricate.

Cardinal collaboration rule: **walk a change through before writing it, then pause for the user's
"go."** The full contract (who the user is — a 14-yo who knows CS fundamentals, newer to Python/APIs —
and how to explain) is `icm/reference/collaboration.md`; the non-negotiables are
`icm/reference/engineering-principles.md`. Read both once per session.

## What this is (identity)
A single-page **Streamlit** app (`app.py`) that runs the user's personal draft board during a live
ESPN snake draft — 12-team, custom-scoring PPR, draft day **July 31, 2026**. Single user, no auth.
v1.0 = a math-based recommender reading `value_board.csv`; v1.1 added a Claude advisor on top, and a
live-draft bridge now syncs ESPN picks. Deploys to Streamlit Community Cloud on push to `main`.

## Where everything lives (routing — this file stores almost nothing, it points)
- **How to work** → `icm/CONTEXT.md` (router) → `icm/stages/NN_*/CONTEXT.md` (the 5 stage contracts)
- **The full product SPEC** (v1.0 scope, layout, constraints, tech decisions, build-phase log,
  aesthetics) → `icm/reference/spec.md`
- **Durable knowledge** → `icm/reference/`: `engineering-principles.md`, `collaboration.md`,
  `lessons.md`, `draft-strategy.md`, `architecture.md`, `pipeline.md`, `bridge.md`
- **Scratch for the current task** → `icm/work/`

## The one hard boundary
Never edit the **frozen pipeline scoring files** (`custom_scoring.py`, `compute_metrics.py`,
`compute_outcomes.py`, and the rest of the `run_all.py` chain) unless the user explicitly asks. If a
fix seems to need them, that's a data-quality flag to raise — not a silent edit. Details in
`icm/reference/pipeline.md`.
