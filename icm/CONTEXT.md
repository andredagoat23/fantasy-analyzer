# ICM Workspace — Fantasy Draft Assistant (Layer 1: Routing)

> ⭐ **NEW SESSION? READ `work/HANDOFF.md` NEXT.** Current as of **Aug 1, 2026**: the stack through
> **L57**. `main` = `origin/main` = `7c96583`, tree clean. The LIVE BOARD is `fc185e5` (L56) —
> everything after it is research/docs. Board + priors regenerated **Jul 31** (540 players).
> Suites **18 / 339 green**, both stress suites pass, preflight OK, **NO open code or data items** —
> what remains before Aug 7 is operational only.
>
> **⛔ CODE FREEZE Aug 3 (2 days). Draft Aug 7 (6 days).** The live mock at the real slot is the
> single highest-value item left and has NOT been run. The remaining work is OPERATIONAL, not
> features: a live mock at the real slot on Aug 3, injury/FA watches Aug 5-6, a final regen Aug 7.
>
> **⚠️ THE DRAFT SLOT IS NOT SETTLED** — older docs said 7, the user says it could be anywhere, the app
> is currently set to 12. Every pick number and every VONA depends on it. Confirm before Aug 7; never
> hardcode.
>
> Live: MC + cohort/coaching/SOS · FP+ESPN projection consensus (L44) · custom scoring verified vs the
> real ESPN settings with `scoring_config.py` as the single source of truth (L41/L42) · D/ST scored
> (L43) · backtest-retuned composite weights (L45) · hybrid position-shape (L46) · opponent-aware
> survival rehearsed on a 192-pick mock (L40) · **COLD POSITION** (L48b — the "a run is on" half was
> measured against 372k real Sleeper picks and CUT) · **draft-day RESILIENCE** (the computed pick
> survives an API outage) · **HEALTH FLAGS** (live injury status; facts, never a gate) ·
> **L51 per-player ADP survival curve** (one constant scale was ~4x too wide at the top; fixed from
> 19,300 measured picks, behind `USE_MEASURED_SCALE`).
>
> **L52 + L53 (Jul 29-30):** the advisor was stating pick numbers and survival odds it had no grounded
> input for. Three fixes shipped: the wheel cell now carries its referent (`gone→#23`); `_horizon()`
> returns the pick AFTER the one being decided in BOTH turn states (it used to answer against a pick I
> already hold); a computed `MY PICKS` line puts the whole snake schedule in the context (it had 3 pick
> numbers in 12,746 chars and invented the rest); and the PUNT READ's "lasts ~R7" — which was
> `floor(ADP/teams)`, the round the MARKET takes him in, and fired at `my_turn: True` — now measures
> survival at MY pick and shows the number. `my_pick_schedule()` and `_horizon()` are single sources of
> truth. **L54** then re-based the wheel bands on measured survival (`gone <20%` / `safe >=70%`,
> replacing `adp<=horizon` = a flat 50% and `adp>=horizon+12` = anywhere from 66% to 99.9%) and put the
> probability in the cell: `risky→#13 (59%)`. **L55** added the rest-of-draft lookahead —
> `WHO'S REALISTICALLY LEFT AT MY PICKS` gives odds at my next EIGHT picks, not just the next one
> (the advisor had 25 survival figures all anchored to one pick and reused them for later rounds).
> See HANDOFF "Open questions" for what is still judgment. **L56** then gave the QB sack rate its
> own shrinkage constant (`K_SACK=768`; `K` was shared with the long-TD rates and shrank sacks only
> ~0.8%). **L57** is a RETRACTION lesson — three QB-timing claims were withdrawn after the user
> checked them against his own mocks; a bimodal median is not a policy. Read it before trusting any
> aggregate in `mc_research/63*` (all retracted in place).
>
> **One open THREAD:** a non-repro'd R7 roster-state issue — diagnosable only from the next mock's
> pick log (L47); don't patch the gate blind. **Two research lines are CLOSED** (per-player
> prerequisites L49, upgrade-a-weak-starter L50) — do NOT re-open or rebuild. One unmerged branch
> (`yahoo-probe`). See `work/HANDOFF.md` "Open questions" before changing anything, and `memory/` for
> the resolved SEA/Charbonnet flag.

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

**Research findings (Layer 3 in practice — durable, in `work/`):** `work/mc-research-findings.md`
(MC + cohorts), `work/run-dynamics-findings.md` (positional runs don't continue — 372k picks),
`work/r1-prerequisites-findings.md` (the prerequisite line that failed its backtest, L49). Their
scripts + saved output live in `work/mc_research/`.

## Working artifacts (Layer 4) — NOT all ephemeral, read this before deleting anything
`work/` mixes three kinds of file. Only the third is safe to clear:
- **`work/HANDOFF.md` — the live state doc.** Read every session, updated at the end of every
  session. Never "clear" it.
- **`work/mc_research/` + the findings docs** (`mc-research-findings.md`, `run-dynamics-findings.md`,
  `r1-prerequisites-findings.md`) — **DURABLE evidence.** Numbered scripts `00_`-`65_` each with a
  `results_*.txt`. They are why several plausible features were killed, and re-deriving them costs
  hours. Large data (`*.parquet`, the Sleeper corpus, caches) is gitignored and regenerable.
- **`work/diagnosis.md` + `work/plan.md`** — genuine scratch for the CURRENT task; overwrite freely.

## Ground rules that outrank convenience (from CLAUDE.md + hard experience)
1. Walk through code before writing it; pause for the user's "go" (rule #1).
2. Never touch the frozen pipeline scoring files unless explicitly asked.
3. Flag data-quality issues; never silently work around them.
4. No fabrication — if you don't know, look it up or say so. Hallucinated facts are the #1 enemy.
5. Verify with the real thing (real board, real mailbox, real API), not assumptions.
