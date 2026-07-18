# ICM Workspace — Fantasy Draft Assistant (Layer 1: Routing)

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
