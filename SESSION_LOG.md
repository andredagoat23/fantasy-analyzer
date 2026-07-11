2026-05-30 update (Block 2, ~60 min):
- Did: pushed to GitHub (via gh cli), scoped all 4 data sources into DATA_SOURCES.md.
- Caught: nfl-data-py is deprecated, pivoted to nflreadpy.
- Next: [whatever feels like the right next move — probably nothing until Monday's block]

2026-06-01 → 2026-06-03 (catch-up block, ~75 min):
- Did: Python 3.9→3.12 + venv setup, installed nflreadpy + requests + pandas + pyarrow, expanded players.py to all positions, saved players.csv (3218 active players), confirmed nflreadpy works (real 2024 stats), wrote .gitignore, locked requirements.txt, committed + pushed everything.
- Learned: [one real sentence — could be about venv mental model, polars vs pandas, or something else that clicked]
- Gotchas captured in docs: polars vs pandas (DATA_SOURCES.md section 2)
- Next: Friday June 5 — start SPEC.md draft. Frozen-spec milestone is end of week 1.

2026-06-15 (back from ACT lockdown, AI block ~90 min):
- Did: re-oriented, confirmed players.py runs, drafted + froze SPEC.md.
- Corrections during freeze: 10→12 teams, captured custom scoring rules, D/ST display mapping, 7 bench + 1 IR roster, Le'Veon Bell ghost diagnosed (Sleeper data goes stale on exiting players — fix requires nflreadpy cross-ref, not just team check).
- Next: Wed Jun 17 — build week 1 starts. First task: tighten players.py filter to drop ghost players via nflreadpy 2024+2025 cross-reference using gsis_id.

2026-06-16 (Pride Double Day, AI block ~90 min):
- Did: split filter logic into filter_active.py (separate from fetch). Discovered load_ff_playerids crosswalk for sleeper_id ↔ gsis_id. Built ghost-player filter. Caught & fixed a None-matching bug via sanity check.
- Results: 3221 raw → 817 active. gsis_id coverage 38% → 96% (non-DEF). Bell gone, vets present.
- Next: Wed Jun 17 — add 2026 rookie + 2025 ghost-rookie inclusion (load_rosters + years_exp == 0 fallbacks). Then start joining 2024 seasonal stats onto players_active.csv.

2026-06-20 (Saturday, AI block ~45 min):
- Did: extended filter_active.py with Track A (2025 rookie roster check) + Track B (2026 draft-pick rookie inclusion via name matching). Created load_player_stats.py — joins 2024 season totals onto players_active.csv. Sanity check: 929 active (+112 from Tuesday), 4/4 top 2026 rookies present, real stats on real vets, expected NaN on rookies.
- Eng notes: load_draft_picks > Sleeper years_exp for rookie source-of-truth. Name normalization handled with proper suffix-stripping order. gsis_id backfill for rookies keeps downstream joins clean. Unmatched rookies surfaced for manual review.
- Next: add 2025 stats join (separate columns or aggregated "most recent season"). Maybe start computing first metrics (target_share, snap_share) using nflreadpy snap_count + ftn data.

2026-06-23 (Tuesday, Pride Double Day, AI block ~90 min):
- Did: 2024 + 2025 stats now joined as separate _YYYY columns. SPEC.md compressed for July 31 draft date — added v1.0/v1.1 split, cut polish features, scheduled LLM advisor for W7-W8. v1.5 listed as conditional backup.
- Architectural decision: LLM draft advisor moved INTO v1 (v1.1 specifically, deploying Jul 30).
- Next: Wed Jun 24 — compute first derived metrics (target_share, snap_share). Will need nflreadpy snap_count function.

2026-06-23 BONUS BLOCK (7-on-7 canceled — reclassified as Pride Single):
- Did: pulled Wed's task forward. Extended load_player_stats.py (instead of new file) with two new functions: snap_share() and target_share(). Computed for 2024 + 2025 and joined onto players_with_stats.csv (now 34 columns).
- snap_share: nflverse's offense_pct per game, averaged across REG-season games.
- target_share: derived (player targets / team total REG targets), restricted to WR/TE/RB.
- Schedule effect: +1 day buffer by Saturday.
- Spot-checks: Jefferson 30% TS, Mahomes 99% SS w/ NaN TS (correct — QBs excluded), CMC TS 4% → 23% (injury → bounce-back).
- Architectural note: consolidated into load_player_stats.py instead of a separate compute_metrics.py — kept pipeline shorter. Reconsider if file bloats past ~150 lines.
- Misread earlier: thought weekly data was added; it isn't. Output is season-aggregated only.
- Next: Wed Jun 24 — FFC ADP integration (pulled forward).

2026-06-24 (Wednesday, Pride Single Day, AI block ~90 min):
- Did: built load_adp.py — fetches FFC ADP for 12-team PPR 2026, joins onto players_with_stats.csv by normalized name + position.
- Refactor: extracted normalize_name into utils.py for reuse across files.
- Result: [X of 929 players have ADP, Y unmatched from FFC side]
- Next: Thu Jun 25 — FantasyPros ECR ingestion (manual CSV download + same name-normalization join).

2026-06-24 → 2026-07-05 (12 days, mostly no AI):
- Jun 24 Wed: built load_adp.py for FFC. Later diagnosed FFC sparseness (90 players, noisy).
- Jun 25 Thu: recovery + pack for Carlton. No AI.
- Jun 26 Fri: travel to Carlton Landing. No AI.
- Jun 27 Sat: downloaded 2 of 8 planned FP CSVs (ECR + ESPN ADP).
- Jun 28 Sun: Sabbath.
- Jun 29 - Jul 5: Carlton tail + Driver's Ed + lake + 4th of July + Sabbath. No AI.

2026-07-06 (Mon, Deload resume, block ~60 min):
- Did: built load_fp_adp.py — parsed FP's compound "Player (Team / Bye)" column + position-rank suffix. 407 players with ADP (vs FFC's 72). Downloaded 4 more FP CSVs (Projections QB/RB/WR/TE/K). Deprecation of FFC loader deferred.

2026-07-07 (Tue, Deload day 2, block ~60 min):
- Did: deprecated old FFC loader (renamed to load_ffc_adp.py.deprecated). Built load_ecr.py — 10-column CSV with team/bye pre-separated. Joined ECR onto players_with_adp.csv → players_with_ecr.csv.
- TD regression CSV confirmed not exportable from FP. Kept in v1.5 backlog (was never actually moved to v1.0 in spec — no revert needed).

2026-07-08 (Wed, Deload day 3, block ~60 min):
- Doing today: SPEC.md FP pivot edits + load_fp_projecti

2026-07-09 (Thu, Deload day 4, MULTI-BLOCK - CAP BREACH ~4 hours 19:14 → 23:11):
- Cap breach: ran 4x normal Deload budget in one push. Real drift risk. Do not repeat next week.
- What shipped:
  1. load_fp_projections.py rebuilt preserving raw stat columns.
  2. custom_scoring.py — Bucket 1 scoring. CeeDee Lamb 175 → 273. PPR credit landing.
  3. apply_bonuses.py — Bucket 2 bonuses (300+/400+ passing, 100+/200+ rush/rec, 40+/50+ TDs) using nflreadpy pbp + shrinkage to league average.
  4. compute_metrics.py — VOLS with 12-team replacement (QB12/RB30/WR36/TE12/K12).
  5. compute_outcomes.py — Monte Carlo 20k sims for floor/ceiling/boom-bust/P_pos1.
  6. value_board.py — final draft board with market labels (VALUE/REACH/fair) + risk tiers.
- v1.0 math side DONE. UI is the only remaining v1.0 gap.

2026-07-10 (Fri, Deload day 5, v1.0 UI shipped):
- Did: built app.py end-to-end for Streamlit. 195 lines.
  - Two-zone layout: sidebar (position scarcity + my roster + reset) + main (filters + draft board).
  - Filters: position multiselect, top-N slider, search, steals/reaches checkboxes.
  - Draft board: st.data_editor with Mine + Drafted checkboxes, sortable, Styler CSS coloring, market icons, risk badges, P(#1) progress bar.
  - Session state versioning (bump()) to force fresh renders when state changes.
  - Undo drawer for drafted players.
- Also built: run_all.py orchestrator, .streamlit/config.toml theme, CLAUDE.md project context, app_data.csv/json combined artifact for v1.1.
- v1.0 status: LOCAL COMPLETE. Streamlit Cloud deployment still pending.

2026-07-10 (Fri evening, cap breach continued — extended past v1.0 UI to injury upgrades + v1.1 shipment):
- Did: three more shipments after the v1.0 UI committed.
  1. Cleanup commit — gitignore drift closed.
  2. Injury upgrades: injury-aware P(start), catastrophic tail modeling in compute_outcomes.py, two-rankings output. compute_outcomes.py grew to 7.3KB, value_board.py to 5.1KB.
  3. v1.1 Claude advisor: built advisor.py (~9KB). Anthropic API integration via st.secrets, Claude Opus 4.8 model. app.py updated with mobile / split-screen layout for phone use during actual draft. Flex-aware replacement level math added to value_board.py.
- v1.1 status: shipped 17 days ahead of the Jul 27-31 (W8) target from the compressed schedule.
- Real cap breach on the day — cleanup + injuries + v1.1 in one day. Do not repeat as a pattern.
- Next: Sat — test the advisor with mock draft state, iterate on prompt quality.

2026-07-11 (Sat, Deload day 6 — v1.2 strategy brain shipment):
- Did:
  1. Fixed advisor crash on players without ADP (undrafted/deep-league). Now handles missing ADP gracefully with a "UD" flag.
  2. v1.2 advisor: rewrote system prompt into a real strategy brain. Includes:
     - League details (12-team custom-scoring PPR + roster).
     - Full data dictionary (VOLS, ADP, tier, market, risk, floor/ceiling, P_start%, bust%, tgt%/snap%, age, rook_pk).
     - Draft strategy toolkit — Best-Available, Hero-RB, Zero-RB, Robust-RB, Upside archetypes.
     - Tier-cliff logic (grab last-in-tier before the drop).
     - Positional-run pivoting.
     - Snake-draft survival math: current_pick + 2 * picks_until_turn = next pick; compare to ADP to decide "grab now" vs "wait for next".
     - Vegas team scoring context (25+ = high upside, <20 = capped).
     - Scarcity-pivot rule (pivot to deep position unless scarce one is a VALUE).
     - Conversation-mode vs pick-mode response guidelines.
  3. ADP added as a default advisor input so it's always available.
- v1.2 status: shipped. Advisor is now a real fantasy strategist, not a raw projection reader.
- Ship probability update: v1.1/v1.2 shipped ~3 weeks ahead of the W8 target. Draft-day tool is essentially ready pending Streamlit Cloud deployment + mock draft testing.
- Next: (a) Deploy to Streamlit Cloud, (b) mock draft dry-run to shake out UX