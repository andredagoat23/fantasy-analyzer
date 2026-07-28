# ICM Workspace — Fantasy Draft Assistant (Layer 1: Routing)

> ⭐ **NEW SESSION? READ `work/HANDOFF.md` NEXT.** It has the full current state: the stack through
> **L49**, DEPLOYED at `7bc24fd` — MC + cohort/coaching/SOS + the FP+ESPN
> projection consensus (L44) + scoring COMPLETE & verified vs real ESPN settings with a single source of
> truth `scoring_config.py` (L41/L42) + D/ST scored (L43) + backtest-retuned composite weights (L45) +
> the hybrid position-shape advisory (L46) + the COLD POSITION read (L48b, advisory — its "run is on"
> half was measured against 372k real Sleeper picks and CUT) + the full advisor read-stack;
> opponent-aware survival SHIPPED & rehearsed (L40, 192-pick live mock). NO open code/data items — one
> open THREAD: a non-repro'd R7 roster-state issue, diagnosable via the per-pick pick-log (L47). Also
> live: draft-day RESILIENCE (the computed pick survives an API outage) + HEALTH FLAGS (live injury
> status; facts, never a gate). The per-player prerequisite research is **CLOSED — it failed a harsh
> backtest (L49); do not wire it in.** One unmerged branch (`yahoo-probe`). Suites: 16 / 238 green.
> **⛔ CODE FREEZE Aug 3.** Draft day: **August 7, 2026** (ESPN, slot 7). See `memory/` for the
> resolved SEA/Charbonnet flag.

This workspace applies **ICM (Interpretable Context Methodology)** to *how work gets done on this
project*, so every change is explicit, staged, and verified instead of ad-hoc. Ad-hoc is what caused
this project's worst bugs (see `reference/lessons.md`). The filesystem is the methodology.

> **Prime directive:** whatever the user asks, do it **efficiently and to a T** — reproduce before
> fixing, verify with REAL data before claiming done, never fabricate, and leave the project +
> these docs better than you found them.

## How to use this workspace
Before acting on a request, route it through the stages. Each stage is a contract in
`stages/NN_*/CONTEXT.md` (Layer 2). Load ONLY what a stage lists — keep context lean.

```
01_understand  → reproduce the issue / scope the ask with REAL data; find root cause
02_design      → plan the change, walk it through, get the user's "go"
03_implement   → make the change to convention
04_verify      → PROVE it with real data / tests / the running app
05_ship        → commit (deploy is the user's call); capture any new lesson
```

## Routing table — which stages + references a request needs
| Request type | Stages | Load these references |
|---|---|---|
| Bug ("X is broken / wrong") | 01 → 02 → 03 → 04 → 05 | `lessons.md`, plus the subsystem doc (`bridge.md` / `architecture.md`) |
| Advisor / recommendation quality | 01 → 02 → 03 → 04 → 05 | `draft-strategy.md` (source of truth), `architecture.md` |
| New feature | 01 → 02 → 03 → 04 → 05 | `spec.md` (scope check), `architecture.md`, relevant subsystem doc |
| Data / board / pipeline question | 01 → 04 | `pipeline.md` (deep internals); never touch frozen pipeline files |
| Deploy | 05 | `architecture.md` (deploy section) — user triggers the push |
| Quick factual answer | — | answer directly; still never fabricate |

**Every request also carries `collaboration.md`** — who the user is (a 14yo who knows CS fundamentals,
newer to Python/APIs) and how to explain + the walk-through-then-"go" contract. Read it once per
session.

## Reference material (Layer 3 — durable, read as needed)
- `reference/spec.md` — the product SPEC: v1.0 scope, layout, constraints, tech decisions, build log.
- `reference/engineering-principles.md` — the non-negotiable guardrails (read once per session).
- `reference/collaboration.md` — who the user is + how to explain + the collaboration contract.
- `reference/lessons.md` — every mistake we've hit + its fix. **Check before diagnosing.**
- `reference/draft-strategy.md` — the codified draft methodology the advisor is built from.
- `reference/late-round-strategy.md` — the validated R11-16 playbook (buys/fades/handcuffs + what
  FAILED validation); source of truth for the DART READ.
- `reference/architecture.md` — system map: files, data flow, pipeline overview, deploy.
- `reference/pipeline.md` — deep FROZEN-pipeline internals (gsis bridge, rookies, layer sources,
  scoring buckets, VOLS/Monte-Carlo/xPPG knobs, value board). Read before touching or debugging data.
- `reference/bridge.md` — live-draft sync (userscript ↔ Firebase ↔ app).

## Working artifacts (Layer 4)
`work/` holds scratch for the CURRENT task — a diagnosis note, a plan, verification output. It's
ephemeral; clear or overwrite freely. Durable knowledge belongs in `reference/`, not here.

## Ground rules that outrank convenience (from CLAUDE.md + hard experience)
1. Walk through code before writing it; pause for the user's "go" (rule #1).
2. Never touch the frozen pipeline scoring files unless explicitly asked.
3. Flag data-quality issues; never silently work around them.
4. No fabrication — if you don't know, look it up or say so. Hallucinated facts are the #1 enemy.
5. Verify with the real thing (real board, real mailbox, real API), not assumptions.
