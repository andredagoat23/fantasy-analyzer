# Plan — Positional-run detection (roadmap #3) · Jul 27, 2026 · SHIPPED as L48 (user go'd; verified 15 suites/215 + preflight)

**One-line why:** ADP survival is a season average and the opponent read prices roster NEEDS — neither
sees the live room's observed RATE; a run ("5 of the last 8 were RBs") means every survival read at
that position is optimistic RIGHT NOW, and the mirror position is falling. Surface it as a computed,
advisory read.

## The signal (Python, stats-only, no fitted knobs)
Over the last `_RUN_WINDOW = 8` synced picks (need ≥ `_RUN_MIN_N = 6`):
- **Baseline share s_pos** = the position's share of the top-`_OPP_TOP_N`(=12, reuse)-by-ADP pool
  **as of the window start** — current `available` + the window's own picked players concatenated
  back, so the run doesn't drain its own baseline (else surprise is overstated).
- **k** = picks at that position in the window; n = window length (unresolved picks — D/ST,
  unmatched names — stay in n as "other": they consumed real picks).
- **HOT**: k ≥ `_RUN_MIN_K = 3` AND binomial upper tail P(X ≥ k | n, s) ≤ `_RUN_P = 0.05`.
- **COLD**: only for a position I can still start (dedicated_open ∪ flex_only), lower tail
  P(X ≤ k) ≤ `_COLD_P = 0.10` and expected ≥ 1. (Low-share positions mathematically can't fire.)
- Binomial via `math.comb` closed form (needs `import math`) — no scipy dep.

Thresholds are significance levels (standard, explainable), documented as tunable constants — not
values fitted to data we don't have.

## Edits
1. **`advisor.py` — `_run_read(available, recent, needed=None)`** (+constants above, near the
   `_OPP_*` block; `recent` = ordered oldest→newest list of `(position, adp_rank)` or `None` per
   pick). Returns `""` or one line:
   `POSITION RUN (last 8 live picks; NOT baked into VONA/wheel — apply as judgment): RB HOT — 5
   taken vs ~2.0 expected (chance ≤2%): you still need RB — act before your wheel; treat 'risky' RB
   wheels as gone. | WR COLD — 0 taken vs ~3.1 expected (chance ≤6%): WR value is falling TO you —
   a faller worth taking NOW already tops TOP PICKS (COLD never demotes anyone); otherwise take the
   scarcer need first and collect the faller on the wheel — safer than the wheel column says.`
   (HOT at an un-needed position → "let it burn — every {pos} taken pushes value at your positions
   back to you.")
   **COLD ≠ fade (user design review, Jul 27):** the take-the-value-now case is the value engine's
   existing job — a genuine faller spikes VONA / tags VALUE → TOP PICKS #1 → you take him now; COLD
   only upgrades the TIMING leg (the wheel-back at that position is more trustworthy than ADP
   implies — the live market-evidence twin of the validated L33 DEFER sequencing). Caveat kept in
   the SYSTEM rule: a cold ROOM is odds, not a guarantee for one player — per-player timing stays
   with wheel/VONA.
2. **`advisor.py` — `build_context(..., recent_picks=None)`**: compute
   `run_line = _run_read(available, recent_picks, dedicated_open | flex_only)` after the gates are
   known; emit it right after `opp_line` (the other live-market read). Default `None` → no line →
   every existing caller (tests, stress suites, pick log replays) is byte-identical.
3. **`advisor.py` — SYSTEM**: one durable bullet after the POSITION SHAPE block: what HOT/COLD mean,
   that VONA/wheel do NOT include it, the action rule (HOT+needed = act a pick early; HOT+not-needed
   = good news; COLD+needed = the value is falling to me: if the faller tops TOP PICKS take him now
   — that IS the value pick — else sequence scarce-first and collect him on the wheel; a cold room
   is odds, not a promise for one player), and that it never overrides hard gates (blocked / punt
   / dart tiers). One-time prompt-cache invalidation, same as any SYSTEM edit.
4. **`app_pages/draft.py`**: cached `board_run_map(mtime)` → `{normalized_name: (position,
   adp_rank)}`; after the opp block build `recent_picks` from `sync_picks` sorted by `pick`
   (`None` for unresolved names); pass `recent_picks=` at BOTH `build_context` call sites (prelook
   + on-prompt). No `cur_key` change needed — any new pick already changes `drafted`, which is in
   the fingerprint. Manual mode → stays `None`.
5. **`tests/test_run.py`** (new, house plain-assert style, ~12 checks): clear run fires; balanced
   window silent; CHALK run silent (high expected share — R1 RB streak isn't a "run"); < MIN_N
   silent; None/empty silent; COLD fires only when needed; unresolved picks dilute n; baseline
   reconstruction adds the window back (engineered case where the drained pool alone would misfire);
   zero-share position with 3 picks fires (s=0 edge, no div-by-zero — phrasing uses "vs ~0.0
   expected", no ratio); build_context integration (line present with kwarg, absent without).

## Explicitly NOT in v1
- No VONA / wheel / effective-horizon modification (no validated magnitude — we hold no pick-by-pick
  corpus to fit run-continuation). v2 slot if mocks demand it: compose into the opp `eff` horizons.
- No manual-mode ordered tracking (undo makes order bookkeeping fiddly; the real draft is synced).
- No K/D-ST runs (streamer logic owns them; pool restricted to `_OPP_POS`).

## Blast radius
`advisor.py` (additive: constants + one function + one kwarg + one output line + one SYSTEM bullet),
`app_pages/draft.py` (one cached map + ~8 lines + 2 kwargs), new test file. Frozen pipeline
UNTOUCHED. Regressions guarded by: default-None kwarg (old callers identical), 14 suites + preflight
re-run. Bonus: the L47 pick log automatically captures the new line (helps the open R7 thread).

## Stage 04 verification
`test_run.py` → all 14 suites → preflight → offline smoke: build_context on the REAL board with a
synthetic 5-RB-in-8 window, eyeball the line + a full context render. Honest limit: live firing is
verified at the next ESPN mock (already on the pre-draft checklist).
