# Lessons (Layer 3 — check BEFORE diagnosing)

Every entry is a real mistake this project made and the fix. The pattern is almost always the same:
an ad-hoc decision made without reproducing or verifying. Read this before diagnosing a new issue —
the bug you're chasing may be a repeat, or the "clever" fix you're about to try may already be known
to mis-fire.

Format: **Symptom → Root cause → Fix → Principle it teaches.**

---

### L1 — Advisor over-weighted the VALUE tag and tier scarcity
- **Symptom:** picked the worse player because of a "VALUE" market tag; reached into thin positions.
- **Root cause:** the prompt literally told it to "TRUST" faded players and to "grab the last one
  before the drop." Heuristic tags were driving picks over player quality and roster need.
- **Fix:** strict priority order — roster need → player quality → market/scarcity as tiebreakers
  ONLY; rewrote the scarcity rule; demoted `market` to a pricing signal.
- **Teaches:** don't let a salient tag override the real objective. (Principle 5)

### L2 — Advisor recommended a 2nd QB with a full roster (Dak)
- **Symptom:** "QB need" recommended when the QB slot was already filled.
- **Root cause:** the model inferred roster needs from a comma-separated name list and got it wrong.
- **Fix:** compute roster needs in Python (`_roster_needs`) and state them explicitly
  ("lineup COMPLETE — bench upside only"). That, not prompt wording, killed the pick.
- **Teaches:** hand the model computed facts, don't make it infer them. (Principle 3)

### L3 — Chasing ceiling drafted QB/TE far too early (Josh Allen at #19)
- **Symptom:** elite QB/TE recommended in round 1–2.
- **Root cause TWO layers deep:** (a) a prompt line licensed "lower-VOLS higher-ceiling can be
  better," which unanchored value; (b) deeper — the board's VOLS itself OVER-rates QB/TE for draft
  timing (an elite rushing QB shows VOLS ~80, RB-level, because his replacement is far worse, but
  you start only one and can wait).
- **Fix:** re-anchor on VOLS as the value backbone, and add a positional discount that OVERRIDES raw
  VOLS for QB/TE (wait positions). Flagged the VOLS-vs-timing gap as a board-calibration issue.
- **Teaches:** reproduce with the real numbers (VOLS=80 was the whole story); a metric can be
  arithmetically right yet wrong for the decision. (Principles 1, 8)

### L4 — "Hallucinating picks" — roster showed players the user never drafted
- **Symptom:** the roster panel + advisor thought the user had drafted other teams' players. Looked
  like LLM hallucination; it was NOT.
- **Root cause:** the "mine-by-position" feature flagged any pick landing on the user's *computed
  seat numbers* as theirs. When the seat was off, it grabbed other teams' picks. The comment even
  claimed this path was "the most robust" — it was the least.
- **Fix:** `mine` = fantasy-OWNER match only (ground truth from ESPN / the dropdown), or the
  userscript's explicit flag. Seat inference removed. No team identified → empty roster (never
  guessed).
- **Teaches:** ask what the user actually observed before assuming (it wasn't the LLM); prefer the
  ground-truth signal over the clever inference. (Principles 1, 4)

### L5 — "You're up at #X" didn't update / was wrong
- **Symptom:** on-the-clock pick tracking stuck or wrong after the roster fix.
- **Root cause:** it read `bridge_my_picks` (set ONCE from ESPN meta) in preference to the live
  slot — sticky hidden state that overrode the seat and never updated. Also dead weight after L4.
- **Fix:** compute pick numbers live from the current slot + teams every rerun; delete the sticky
  state.
- **Teaches:** sticky session state that shadows a live input is a trap; prefer transparent,
  recomputed-every-run values. (Principle 4)

### L6 — Tyreek Hill missing from the board
- **Symptom:** a real, drafted player (ADP 168) absent from `value_board.csv`.
- **Root cause:** no FantasyPros 2026 projection → `proj_points = NaN` → `value_board.py` drops
  NaN-points players. Not a name-match or bridge bug.
- **Fix:** flagged to the user; did NOT touch the frozen pipeline. Added `tools/name_audit.py` to
  catch this class before draft day.
- **Teaches:** trace the pipeline to the real drop point; flag data gaps, don't work around them.
  (Principles 1, 7, 8)

### L7 — Overall-rank/VOLS-first drafting + stale tiers were the wrong engine
- **Symptom:** advisor drafted by absolute value (rank/VOLS) and leaned on stale, inaccurate ECR
  "tiers"; it also flipped wheel-back ("take the guy who'll be left, not the one who won't").
- **Root cause:** absolute value ignores WHEN you pick next and who'll be left; tiers were a crude,
  static, stale proxy for positional drop-offs.
- **Fix:** **VONA — Value Over Next Available** (his VOLS minus the best same-position player ADP says
  could still be there at your next pick). Computed in Python, shared by the advisor + a board column,
  it's the live ADP-driven drop-off and makes wheel-back STRUCTURAL (gone = high VONA = grab; safe =
  low VONA = wait). Tiers deleted from advisor + board. See `draft-strategy.md`.
- **Teaches:** draft by marginal value over the next-available, not absolute rank; kill stale proxies.

### L8 — A roster rule the model keeps ignoring must be enforced IN DATA
- **Symptom:** after VONA went in, the advisor chased the single highest VONA — a 2nd TE (Kelce, VONA
  15) — even though the roster-needs line explicitly said "a 2nd TE is NOT draftable." Prose rule
  ignored.
- **Root cause:** VONA is position-blind; a strong prose gate lost to a big salient number.
- **Fix:** enforce the gate in the data — `build_context` nulls the VONA of filled 1-start positions
  (QB/TE) to `n/a` so a worthless backup can't be the "highest VONA." (RB/WR always keep depth value.)
- **Teaches:** when the model reliably ignores a rule, don't reword it — remove the temptation from
  the data (same principle as computing wheel-back/roster-needs in Python). (Principle 3)

---

## How to add a lesson
When a fix corrects a wrong assumption or a class of bug, append here in the same format during
Stage 05. Keep it short and concrete — the goal is that the next agent doesn't repeat it.
