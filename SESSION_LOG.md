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