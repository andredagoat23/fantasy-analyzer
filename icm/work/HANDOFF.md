# SESSION HANDOFF — read this first if you're a fresh session

**How to use this file:** read `icm/CONTEXT.md` (the router) first, then this, then whatever
reference docs the task needs. Everything below is CURRENT as of **Jul 20, 2026 (late)** —
deployed through commit `2042da9`. Draft day is **July 31, 2026** (ESPN, 12-team, slot 7,
custom PPR, 16 rounds).

## The stack as it stands (all LIVE on Streamlit Cloud)
1. **Calibrated Monte Carlo** (`compute_outcomes.py`, FROZEN — user authorized all shipped edits):
   Waves 1/2/2b/2c. Depth-dependent `SIGMA_ANCHORS`, honest availability (~.82-.85 all positions),
   games↔per-game injury coupling, exact mean re-centering, draft-capital refit, team-changer split
   by PROVEN production (proven movers untouched, unproven 0.86/σ×1.2), stable-vet narrowing,
   WR30+ fade, CV blend, stayed+new-HC tilt (1.02/σ×0.85, QB/RB/WR). **Backtested 60-62% band
   coverage INCLUDING true out-of-sample 2014-18 (62.1%)** — not overfit. Acceptance tests:
   `icm/work/mc_research/05_distribution.py` + `06_finish_odds.py` after ANY re-tune.
2. **Cohort priors** (`cohort_priors.py` → `cohort_data.csv`): every board player's 15 nearest
   historical seasons (kNN over 2014-2025: price, experience, capital, production, age, mover,
   role, vegas, injury history, recency) with **empirical-Bayes-shrunken rates (m=25, LOSO-fitted
   — raw 15-sample rates were overconfident)** + the 5 absolute closest matches with outcomes.
   Advisor cites them by name.
3. **Coaching intelligence** (`sos_priors.py`, `data/`): news-verified 2026 lists — 10 new HCs
   (`new_hc_2026.csv`, drives the MC tilt; the schedules feed was STALE for ARI/ATL/BUF — the
   verified list is authoritative), 18 new PLAYCALLERS incl. 6 first-timers
   (`playcallers_2026.csv` + `playcallers_hist.csv`, 224 sourced team-seasons 2019-25).
   **Validated split: the mispricing lives with FULL regime change (new HC, med 1.09x); OC-only
   changes are price-NEUTRAL (med 1.00x)** → MC tilts on HC only; playcaller = advisor
   usage-reasoning context (never fade/boost on an OC change alone — encoded in SYSTEM).
4. **Positional SOS** (`sos_data.csv`): 2026 opponents × 2025 per-position points allowed;
   `sos` column (rank 1=easiest..32) in the advisor table, tie-break-only rules.
5. **Advisor** (`advisor.py`): strategy-is-the-plan (L25 — absolutes BINDING, deviation protocol
   plan-first, Plan: note in every pick), roster-risk accumulation gate (L23), cohort/SOS/
   playcaller context blocks, **STREAMER ALERT** (forces K/D-ST when remaining picks barely cover
   them — a live full-draft test finished kicker-less without it; `draft.py` passes
   `total_rounds: 16`), prompt-cached SYSTEM (~4.9k tokens, verified ~90% cache reads).
6. **Speculative PRE-READ** (`app_pages/draft.py`): background deep call (adaptive thinking)
   within 3 picks of the clock; exact board-fingerprint guard (race-tested under pick storms —
   stale text can never be served; worst case ≈30s live fallback); instant serve on match.
7. **Live sync**: ESPN + Sleeper (~81% platform coverage). Yahoo not started
   (`icm/work/yahoo-probe-scope.md` — probe BEFORE building).

## Regeneration playbook (data freshens between now and draft day)
- Board: `.venv/bin/python run_all.py` (or the tail: `compute_outcomes.py` →
  `load_ff_opportunity.py` → `value_board.py`). Deterministic (seeded, verified byte-identical);
  upstream nflverse data DRIFTS between days — regenerate close to draft day.
- Then re-run the non-frozen priors: `cohort_priors.py`, `sos_priors.py` (needs the local research
  panel: `icm/work/mc_research/01_build_panel.py` + `02_expectation.py` rebuild it; heavy data is
  gitignored). Commit the regenerated CSVs (deployed app reads them from the repo).
- Verify after regeneration: `icm/work/mc_research/11_stress_test.py` (component invariants +
  cohort LOSO) and `12_full_system_stress.py` (24 offline drafts) — both must say ALL PASS;
  `python -m unittest discover -s tests` (13 checks).

## Verified vs pending
- **Stress-tested end-to-end** (Jul 20): component suite, 24 offline drafts (384 advised picks),
  a full LIVE-API 16-round draft (16/16 valid picks, strategy executed, median 4.7s), prelook
  races, determinism. The one real bug found (kicker never forced) is fixed + retested live.
- **Pending live verify:** a real **Sleeper mock draft** end-to-end (needs the user's account);
  a user-driven ESPN mock through the deployed app is the best pre-draft-day rehearsal.
- **Pre-draft-day checklist:** regenerate board + priors on fresh data (see playbook), rerun the
  two stress suites, and eyeball the app once.

## ROADMAP — next features ranked (user-approved ordering)
1. **Opponent-aware survival** — replace ADP-only "will he last" with the actual roster needs of
   the specific teams picking before my wheel (live rosters are already synced). Sharpens VONA +
   wheel. App/advisor layer only.
2. **Positional-run detection** — "5 of the last 8 picks were RBs → the cliff is NOW."
3. **Live news/injury layer** — the real July-31 difference-maker; needs a source decision.
4. **Mock draft simulator** — rehearse from slot 7 vs ADP-bots (the offline engine in
   `12_full_system_stress.py` is 80% of it already).
5. **Rest-of-draft lookahead** — optimize the FINAL roster, not this pick. Biggest build.
6. **August usage refresh** · 7. **ESPN-vs-consensus divergence** · 8. **Live draft grade** ·
9. **"My guys" watchlist UI** (interim: name them in the strategy — the advisor executes it) ·
10. **OC/coordinator dataset** (none exists; manual-note only).

## Where the research lives
- Findings narrative: `icm/work/mc-research-findings.md` (Waves 1-2c, expansion, playcaller
  decomposition, cross-positional NULLs — the market prices teammate quality, don't pay premiums
  for supporting cast).
- Scripts + results: `icm/work/mc_research/` (01-12; results_*.txt committed, heavy parquets
  gitignored/rebuildable).
- Lessons L21-L26: `icm/reference/lessons.md`. Non-negotiables unchanged:
  `icm/reference/engineering-principles.md`, `icm/reference/collaboration.md`.
