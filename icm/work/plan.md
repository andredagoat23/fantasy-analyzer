# Plan — Opponent-aware survival (roadmap #1)

**One-line why:** survival (the input to VONA, wheel, and take-now-vs-wait) currently pretends the
picks between me and my wheel are an anonymous ADP market; in reality they're 5 known teams whose
rosters we already sync — use them.

## Design: per-position EFFECTIVE HORIZON (smallest correct change)
Keep the calibrated logistic `σ((adp − horizon)/7)` exactly as-is; make the horizon position-aware.

1. **Window teams.** For each overall pick n in (now → my next pick T): seat(n) by the same snake
   formula as draft.py:446 (generalized to any seat). seat → owner name by MAJORITY VOTE over
   observed `(pick_no, team)` pairs from the synced picks — evidence only; an unseen/conflicted seat
   stays unknown. (Never used for roster assignment — the seat-math lesson. Rosters stay keyed by
   owner name, ground truth.)
2. **Rosters → demand.** Per owner: position counts from resolved picks (board lookup; D/ST via the
   existing name heuristic). Per window pick j, team demand over positions:
   - baseline shares `s_P` = position mix of the top-12-by-ADP available players (the stress-bot
     pool notion — data-driven, stage-appropriate);
   - gates: filled 1-start (QB/TE) → 0.1 (double-ups are rare); K/D-ST → 0 until the last ~3
     rounds, else 1; RB/WR → always 1;
   - renormalize so each pick takes exactly one player: `rel_j(P) = g_P / Σ_Q s_Q·g_Q`.
     Blocked teams' demand redistributes onto their open positions — the "hole boost" falls out
     for free, bounded, with NO new tuned constants (only the 0.1 double-up floor + late-K gate).
   - unknown team → rel = 1 (exact ADP baseline). Manual mode / no sync → everything rel = 1.
3. **Effective horizon.** `n_eff(P) = Σ_j rel_j(P)`; `T_eff(P) = T − (N_window − n_eff(P))`.
   Survival, VONA's best_wait, and the wheel label for a player use HIS position's T_eff.
   All rel = 1 ⇒ T_eff = T ⇒ byte-identical to today (regression-provable).
4. **Advisor visibility (L8 / principle 3).** The numbers move in the same vona/wheel columns the
   model already reads, PLUS one Python-computed context line, e.g.:
   `WHEEL WINDOW to #42: Alpha×2 (QB✓TE✓→RB/WR), Beta×2 (needs QB!) … → QB eff. competitors 1.2/10 (survival ↑), RB 11.6/10 (↓)`
5. **Punt read stays ADP-only in v1** — its window is ~5 rounds out where ADP blur dominates;
   revisit only with live evidence.

## Sanity math (the diagnosis scenario)
10 window picks, all 5 teams have QB filled, shares at R3 ≈ {QB .15, RB .40, WR .35, TE .10}:
rel(QB) = 0.1 → n_eff(QB) = 1 → T_eff = 33 → Lamar (ADP 37): 33% → ~64% survives. RB rel ≈ 1.16 →
T_eff(RB) ≈ 43.6 → RBs slightly MORE likely gone. Both directions correct.

## Edits (blast radius)
- `bridge.py` — ADDITIVE pure helpers: `rosters(raw_picks, name_to_pos)` and
  `seat_owners(raw_picks, teams)`. `resolve()` untouched; existing tests untouched.
- `advisor.py` — new `opponent_read(...)` (pure: picks-derived structures + board + draft_pos →
  {pos: T_eff} + the window summary string); `add_vona(available, horizon, opp=None)`;
  wheel-label call sites take the per-pos horizon; `build_context(..., opp=None)` emits the
  WHEEL WINDOW line. `_survival_prob` itself UNTOUCHED. All defaults None ⇒ current behavior.
- `app_pages/draft.py` — store the synced raw picks' minimal structures in session_state on poll
  (bridge + sleeper share the mailbox shape; ESPN-API path gets a 3-line adapter to it), build
  `opp` once above the add_vona call (single choke point → board column and advisor always agree),
  pass to add_vona + build_context (+ prelook path, same ctx — fingerprint already covers pick
  changes, verify).
- `tests/` — new unit tests (seat majority vote, roster counts + D/ST, renormalization math,
  T_eff identity when opp=None, direction checks).
- FROZEN pipeline, cohort/sos files: untouched.

## Stage 04 verification plan
1. Unit tests above + `python -m unittest discover -s tests` green.
2. Identity regression: add_vona(opp=None) on the real board ≡ current output;
   `11_stress_test.py` + `12_full_system_stress.py` still ALL PASS (they run the None path).
3. Real-scenario proof: scripted mailbox reconstructing the diagnosis scenario both ways
   (QBs filled vs QBs needed) — survival/VONA/wheel move the right direction with real board data.
4. AppTest live-sync run: WHEEL WINDOW line present, manual mode unaffected, prelook consistent.
