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

### L9 — The advisor miscounted the roster (D/ST invisible, K/D-ST slots ignored)
- **Symptom:** late in a mock the advisor thought the roster was full when it wasn't and thought the
  user had no D/ST when they did.
- **Root cause:** `value_board.csv` has NO defenses, so a drafted D/ST never resolves to a board
  player → never enters `mine` → the advisor can't see it. And `_roster_needs` only tracked
  QB/RB/WR/TE/FLEX, ignoring the K and D/ST starter slots, so it called a half-empty lineup "complete."
- **Fix:** `bridge.my_dst()` detects the D/ST from the raw picks (owner + name); draft.py threads it
  through (`mine_dst` state, roster-panel slot, `build_context(my_dst=)`); `_roster_needs` now covers
  all 9 starters, reports what you HAVE, and only says "complete" when the full lineup is set.
- **Teaches:** know the data's blind spots (defenses aren't on the board) and model the WHOLE roster,
  not just the positions that happen to be in the CSV. (Principles 1, 8)

### L10 — Softened VONA compresses the numbers; weight the profile on ties
- **Symptom:** with the softened VONA, top options are often within a point or two — and the model
  over-indexed on the tiny VONA gap.
- **Fix:** `build_context` stars the options within a few VONA of the top (a genuine tie) in the TOP
  PICKS list; the prompt says pick the BEST PLAYER among the starred by age/risk/offense(vegas)/role,
  not the VONA gap. VONA = the shortlist; the profile = the tiebreaker. (Also confirmed VONA already
  reflects position timing — a comparable player who lasts several rounds yields a low VONA.)
- **Teaches:** a metric that's mathematically right can still be too precise to decide on — surface
  the tie explicitly and let the richer profile break it.

### L11 — VONA's one-pick horizon reaches for a punt-able QB at a turn; add the PUNT READ
- **Symptom:** in a July-2026 mock the advisor took an elite QB (Josh Allen) in round 2 over a scarce
  elite RB (Chase Brown) — the L3 pattern resurfacing on a real draft.
- **Root cause (NOT a VOLS bug):** Allen's VOLS 80 is a correct VORP over QB12; "fixing"
  `compute_metrics.py` by deepening the QB baseline BACKFIRES (it raises elite-QB VOLS). The real miss
  is a horizon artifact: VONA measures value lost by waiting ONE pick, so at a snake TURN (back-to-back
  picks) waiting looks free for everyone, under-crediting a scarce RB/WR (who "survives one pick") and
  over-crediting the QB's within-position cliff.
- **Fix (advisor layer, computed in Python — Principle 3 / L8):** the PUNT READ. Final form is fully
  stats-based (the user asked for no "feeling"): for EVERY position compute the same
  `punt_loss = elite VOLS − (best survivor at the fill window) × (1 − bust%)` — the risk-adjusted value
  lost by deferring it, with the `× (1−bust%)` VARIANCE factor so a boom/bust streamer counts less.
  A 1-start slot is punt-able iff its punt_loss < the best RB/WR's punt_loss (pure comparison — no
  keep_frac, no 0.75). Punt-able slots are HARD-DEMOTED below RB/WR in TOP PICKS; it self-corrects
  (grabs the QB once it's the scarcest value / depth is gone). NOTE: this is raw-value-optimal, so it
  can grab an elite QB over an elite TE at a turn (unlike the interim keep_frac version) — the variance
  factor keeps TE stickier but won't override a real QB VONA edge. Verified live: pick 24 takes Chase
  Brown (scarce RB) and passes the round-2 QB. Knob: `_PUNT_LATE_ROUNDS`. (Design history: flat-margin →
  depth-count → keep_frac → symmetric risk-adjusted punt_loss; earlier forms overfit or were "feel".)
- **Teaches:** a metric can be right yet myopic (one-pick horizon); fix the DECISION layer, not the
  frozen metric — and beware the "obvious" pipeline fix that backfires. Reproduce first; verify live.
  (Principles 1, 3, 5, 8)

### L12 — Advisor recommended a 4th RB with 3 RB and 0 WR (bench depth over an open starter)
- **Symptom:** with 3 RB and 0 WR rostered, the advisor put RB depth at the top of TOP PICKS (a 4th RB
  out-VONA'd the remaining WRs after a WR run) and recommended it — over the two EMPTY WR starter slots.
  Reported live, and "not the first time."
- **Root cause:** VONA is position-blind and `_roster_needs` marked RB as "RB/WR depth = draftable"
  even though 3 RB already fill RB1+RB2+FLEX — so a 4th RB is bench-only (can't crack the lineup), yet
  it ranked above a WR who fills an open starter.
- **Fix (enforce in data — L8):** `_bench_saturated_positions` flags a FLEX position as bench-saturated
  when its dedicated slots + the FLEX are already filled (3 RB / 3 WR / 2 TE) AND a FLEX-eligible
  starter is still open; those are hard-demoted below the lineup-fillers in TOP PICKS and tagged
  BENCH-ONLY, and dropped from `_roster_needs` "depth". Gated: once the FLEX-eligible slots are all set
  it stops (normal late bench depth). Verified live: 3-RB-0-WR now recommends the top WR, not a 4th RB.
- **Teaches:** "RB/WR always keep depth value" is true UNTIL you can't start another one — model the
  actual lineup slots, and enforce roster construction in the data, not the prose. (Principles 3, 8)

### L13 — Fill DEDICATED starters before the FLEX (FLEX is week-to-week)
- **Symptom:** with dedicated slots still open (e.g. 2 RB, 1 WR — WR2 + TE + FLEX open), the advisor
  would spend the pick on a 3rd RB (higher VONA) that only upgrades the FLEX, leaving the WR/TE
  starter holes unfilled. User's read: the FLEX is a week-to-week / matchup slot you can stream, so a
  piece that ONLY improves it is worth less than filling a fixed positional need — unless it's way
  better.
- **Fix (extends L12's `_lineup_gaps`, enforced in data):** a position whose dedicated slots are full
  but that only fills the open FLEX is tagged FLEX-only and HARD-DEMOTED below the dedicated-need
  fillers in TOP PICKS — UNLESS its VONA beats the best dedicated filler by `_FLEX_MARGIN` (default 15),
  so a genuine RB/WR value cliff still gets taken. Verified live: 2RB/1WR with a modest 3rd-RB (VONA 81)
  vs an elite TE need (McBride 82) now recommends McBride; a stud RB (Taylor 110) is still kept #1.
- **Teaches:** model the lineup slots, not just position VONA — dedicated starters outrank a
  week-to-week FLEX upgrade, with a margin so studs aren't blocked. (Principles 3, 8)

### L14 — Advisor under-read player ROLE; needed depth-chart slot + stale-role flag
- **Symptom:** the model preferred Jameson Williams over DJ Moore, missing that Moore is his team's WR1
  with an elite QB (Allen) while Williams is a WR2 behind an alpha (Amon-Ra) with a target-eating RB1
  (Gibbs). The board gave the model tgt%/snap% but no depth-chart context.
- **Root cause:** (a) no explicit depth-chart role on the board — the model couldn't see WR1-vs-WR2; and
  (b) `tgt%/snap%` are LAST-season stats, so for a player who CHANGED TEAMS they describe the OLD team
  (DJ Moore's 16% is his Chicago role, not his new Buffalo WR1 role) — but the model was told they were
  current, so it under-rated the mover.
- **Fix (app layer, `load_board`):** derive `team_role` = each player's rank at his position WITHIN his
  team by 2026 projection (BUF WR1, DET WR2, DET RB1 …) from the FULL board, and surface it. Prompt now
  reads `role` WITH vegas (WR1 on a high-vegas offense = secure volume; WR2/WR3 competes with the alpha
  + a pass-catching RB1) and DISCOUNTS tgt%/snap% for movers (regr "new-tm" already flags them), trusting
  role + projection. Verified live: the advisor now leads DJ Moore's case with "WR1 for Josh Allen, stale
  stats — trust role." (Honest limit: true QB quality beyond the vegas total isn't in the data.)
- **Teaches:** give the model the situational fact (depth-chart role) computed from data, and know which
  columns are stale (last-season role for a mover). (Principles 3, 8)

### L15 — Advisor recommended unsigned free agents (Stefon Diggs, no NFL team)
- **Symptom:** the advisor repeatedly recommended Stefon Diggs, who has no 2026 team on the board.
- **Root cause:** the frozen pipeline projects 4 players with `team` = blank/NaN (Diggs, Deebo Samuel,
  Keenan Allen, Nick Vannett) — no team = no offense, no vegas total, no real role — yet they were in the
  draftable pool.
- **Fix (app layer):** `load_board` flags `no_team`; `build_context` drops no-team players from
  everything the advisor sees (and the prompt says: if asked about one, call him an unsigned FA, don't
  recommend him). Flagged the data gap to the user; did NOT touch the frozen pipeline (their call whether
  `value_board.py` should also drop no-team players).
- **Teaches:** a player with no team has an unreliable projection — filter it in the layer you own and
  flag the data-quality gap. (Principles 7, 8)

### L16 — Role (WR1>WR2), false VALUE tags, and FAs — fixed at the source (frozen pipeline opened)
- **Symptoms:** (a) the advisor preferred a WR2 (Jameson) over a WR1 (DJ Moore) — role too weak; (b) it
  recommended below-replacement players like John Metchie (WR47, VOLS −28) tagged `market=VALUE`;
  (c) it still surfaced unsigned FAs. The user authorized touching the frozen pipeline.
- **Root causes:** (a) role was informational only, not in the ranking; (b) `value_board.py` tagged any
  big ADP-vs-rank gap as VALUE even below replacement — a "steal" that's cheap because he's BAD (L1);
  (c) FAs (no team) were kept in the board.
- **Fixes:**
  - **Pipeline (`value_board.py`):** drop no-team players; only tag VALUE when `vols ≥ 0`; add canonical
    `team_role` (depth-chart slot) + `role_lead` (projection gap to the next player in his position room).
    Regenerated `value_board.csv` from the existing intermediates (no live re-fetch).
  - **Advisor:** TOP PICKS rank = VONA + a role nudge SCALED BY `role_lead` (× _ROLE_LEAD_K, ±_ROLE_CAP)
    — a CLEAR alpha (DJ Moore leads his WR2 by 25) beats a comparable WR2, but a coin-flip WR1 (Burden
    +2 over Odunze) gets ~nothing, so it never amplifies a projection tie or resurfaces a low-value WR1.
    GATED by `role_env_ok` (team above-median vegas OR pass volume): a clear WR1 on a bad, run-heavy
    offense (NYJ/MIA/CLE…) gets NO bump — his targets aren't valuable — while a low-vegas but pass-heavy
    team (ARI, 515 targets) still qualifies via the OR. The user's rule: WR1 only if the team throws.
  - **L8 follow-through:** reordering alone wasn't enough — the model re-sorted by the raw VONA column.
    Annotating entries "CLEAR ALPHA (locked targets)" / "behind the alpha" + "TAKE #1, don't re-sort by
    VONA" made it follow the order. Verified live: it now takes the clear-WR1 over the higher-VONA WR2.
- **Teaches:** scale a role signal by how REAL it is (gap-based, not ordinal) so you don't amplify
  projection noise; and enforcing a ranking needs the REASON visible to the model, not just the order.
  (Principles 3, 8; L1)

### L17 — Projection outliers (John Metchie): trust expert consensus over a lone inflated projection
- **Symptom:** John Metchie looked draftable on our board (WR46, our proj rank 148) but ESPN ranks him
  589th and has "no potential" per the user.
- **Root cause:** our FantasyPros projection (182 pts) rated him far above expert consensus (ECR 361)
  and his 2025 actuals (274 yds, 9% target share). A LONE projection outlier. Investigation showed the
  board is NOT systemically over-rating — mean `proj_vs_ecr` is −13 (we're generally more conservative
  than ECR); Metchie was a near-unique extreme, plus a cluster of deep backup TEs (TE replacement is
  low, so mediocre TEs project positive and out-rank their ECR).
- **Fix (`value_board.py`, consensus sanity):** a NON-rookie whose projection ranks him > CONSENSUS_GAP
  (100) spots better than ECR gets his composite blended CONSENSUS_ECR (60%) toward ECR. Demoted 29
  players (Metchie + deep TEs), ALL of them undrafted (ADP maxed) AND expert-faded — zero false
  positives (none had a real ADP). Metchie 191 → 236; the elite tier is untouched.
- **Teaches:** a single model's projection can be an outlier — sanity-check it against expert consensus
  (ECR) and demote lone over-projections, but verify you're not catching players the market actually
  drafts (check ADP). (Principles 1, 8)
- **Follow-up (L18 batch):** demoting the composite wasn't enough — the advisor ranks by VONA and still
  surfaced Metchie, so `build_context` now also DROPS `proj_outlier` players from everything it sees
  (like FAs). Column written to the board.

### L18 — Bench balance + team hallucination
- **Symptoms:** (a) with 4 RB / 2 WR the advisor recommended a 5th RB (no balance once starters are
  full); (b) it recommended John Metchie and said he's on "HOU" — he's on CAR in our data; the model
  invented the team from stale training memory.
- **Fixes (advisor):**
  - **Bench balance:** `_bench_overstacked` — once RB/WR depth is 2+ lopsided, the heavier position is
    hard-demoted below the thinner one in TOP PICKS (lowest sink tier), so bench depth stays ~even
    (4 RB / 2 WR → take a WR). Also gated `bench_sat` to fire only while a FLEX-eligible starter is
    actually open (so a full lineup isn't mislabeled "starter open elsewhere").
  - **Anti-hallucination:** the prompt now forbids stating ANY team/role/stat from memory — use only the
    data given; if a player isn't in the data, say so and don't guess his team or recommend him. Plus
    the `proj_outlier`/FA exclusion means faded players aren't in the context at all. Verified live: it
    now says "I don't have Metchie… I won't guess," no "HOU."
- **Teaches:** roster construction includes balance even on the bench; and NEVER let the model emit a
  fact (team/role) from its training when live data is authoritative — rosters change yearly. (Principles 2, 3, 8)

### L19 — Deploy env ≠ local: an unpinned dep + a cloud Python bump crashed the live board
- **Symptom:** the app worked perfectly locally but crashed on Streamlit Cloud on boot —
  `AttributeError` at `advisor.add_vona` → `_survival_prob`, taking down the whole board.
- **Root cause:** Streamlit Cloud had moved to **Python 3.14** with an **unpinned numpy**, where
  `np.exp(a_pandas_Series)` returns a bare ndarray (older numpy returned a Series); ndarray has no
  `.where`, so the logistic blew up. Pure environment drift — the code was unchanged there.
- **Fix:** (1) make `_survival_prob` version-proof — compute on numpy explicitly, re-wrap in a Series
  with the original index (byte-identical VONA). (2) PIN `numpy==2.4.6` in requirements.txt (verified it
  ships a cp314 manylinux wheel so the cloud build stays binary, no source build).
- **Process miss:** I verified only at the code/data level and pushed without booting the full app —
  exactly the crash a UI smoke-test catches. For any deploy, boot the real runtime (or at least run the
  entry path end-to-end), and PIN runtime deps so a silent cloud upgrade can't change behavior.
- **Teaches:** "works on my machine" is not verification for a deploy — the runtime environment is part
  of the system; pin it, and exercise the actual boot path. (Principles 1, 9)

### L20 — Stated strategy: value-first, but surface the strategy-compliant pick on a conflict
- **Symptom (from a test battery):** the advisor was purely value-first — it silently overrode a stated
  strategy (took the RB despite "strict Zero-RB", buried the compliant option as a generic "fallback"),
  so a committed Zero-RB/punt-TE drafter couldn't actually execute their plan.
- **Fix (prompt, per the user's spec):** VONA stays the backbone, but (1) a RISK-flavored strategy
  (high-risk/high-reward, upside) RE-WEIGHTS value — down-weight VONA toward ceiling/boom; (2) on a
  POSITIONAL-rule conflict, give BOTH labeled: "**Best value: X** (costs ~N VONA to follow your plan)"
  + "**Sticking to your [strategy]: Y**", and let the user choose. PICK mode swaps its fallback for the
  two options on conflict.
- **Verified live:** Zero-RB conflict now returns "Best value: Chase Brown | Sticking to Zero-RB: Chris
  Olave." Note: the risk re-weight rarely FLIPS a clear-value pick because on this board value (VONA)
  and ceiling are tightly correlated — a lower-value/higher-ceiling player basically doesn't exist — so
  the value pick is usually also the upside pick (correct). It bites mainly on genuine ties.
- **Teaches:** don't make the model silently override the user's explicit intent OR blindly obey it —
  surface both and let them decide; and test a behavior against data that can actually discriminate it.
  (Principles 6, 9)

---

## L21 — Cross-year schema drift silently zeroes a data layer (MC research, Jul 2026)
- **Symptom:** injury-report aggregates looked plausible but were ~0 for 2019–2024 and populated only
  for 2025; downstream "injury type recurrence" tables came out near-empty.
- **Root cause:** nflverse `injuries_*.parquet` files pre-2025 have NO `season_type` column (only
  `game_type`); after `pd.concat`, filtering on `season_type=="REG"` NaN-dropped six seasons without
  any error. A second trap in the same layer: FFC's ADP API 403s the default Python user-agent, and
  FantasyPros' historical ADP pages only server-render 5 rows (the rest is JS/paywall).
- **Fix:** filter on the column that exists in EVERY year (`game_type`); after any multi-year concat,
  ASSERT per-year row counts / group-by-season means before trusting aggregates. Fallback sources:
  DynastyProcess ECR archive via `load_ff_rankings("all")` (deep, consistent, 2021+).
- **Teaches:** when pooling files across years, schema drift fails SILENTLY through filters — verify
  the pooled data has all years represented before analyzing. (Principles 1, 8, 9)

## L22 — Calibrate the simulator to reality, then keep the acceptance test (Jul 2026)
- **Symptom:** MC looked reasonable but had never been checked against real season outcomes. Research
  vs 2019–2025 (actual ÷ market-expected points = "season multiplier") showed: spreads ~2× too narrow
  (booms ≥1.5× real 12–18% vs 4% simmed), elite RBs 4× riskier than claimed, availability ≈.82–.85 at
  ALL positions (QB .94 was fiction), and games missed COUPLES with per-game decline (corr .29) which
  independent sims can't produce.
- **Fix (Wave 1, user-authorized frozen edit):** depth-dependent `SIGMA_ANCHORS`, recalibrated
  availability/p_major/age cliffs, games↔per-game coupling, refit draft tilt — all constants
  BACKTESTED before the edit (60.3% band coverage vs 60% target; old: 41.5%).
- **Teaches:** a simulator's constants are CLAIMS about the world — back-test them against history
  before trusting them, and encode the check as a rerunnable acceptance test
  (`icm/work/mc_research/05_distribution.py` + `06_finish_odds.py`). (Principles 1, 5, 9)

---

## L23 — Risk accumulates across a roster; the advisor must see the ROOM, not just the player (Jul 2026)
- **Symptom:** a mock draft graded fine pick-by-pick (fair value everywhere) but assembled five RBs
  at 25–76% bust with mediocre ceilings — better-than-coin-flip odds that two bust, with no jackpot
  compensation. Every per-player signal was correct; nothing watched the pile.
- **Root cause:** the advisor priced each candidate's bust risk but had no roster-level state: no
  notion of a "bust-heavy room," and no preference for compensated risk (big ceiling / elite odds)
  over uncompensated risk at equal VONA.
- **Fix (`advisor.py`):** `_roster_risk` computes per-room high-bust counts from MY roster; when a
  room has ≥2 players ≥40% bust, a further uncompensated high-bust candidate there is VONA-penalized
  and tagged RISK-STACKED — but ONLY if a genuinely stabler same-position swap exists at comparable
  value (late in drafts everyone is high-bust; penalizing all of them equally is noise). A ROSTER
  RISK line states each room's load. Verified against the real mock: at pick 127 the 76%-bust
  handcuff fell out of TOP PICKS and stable swaps surfaced; at pick 90 the risky-but-correct value
  pick stayed #1 with the room warning attached; a clean roster shows nothing.
- **Teaches:** independent risks multiply — evaluate additions against the portfolio, not in
  isolation; and risk is only worth carrying when the upside pays for it. (Principles 3, 5)

---

## L24 — A user challenge to a model rule is a subgroup hypothesis — test it, don't defend it (Jul 2026)
- **Symptom:** the user pushed back on the Wave-2 blanket RB team-changer penalty: "players who
  moved into a better role (e.g. Montgomery) should be boosted, not taken down."
- **What the data said:** the intuitive mechanism was WRONG but the conclusion was RIGHT. Splitting
  7 seasons of RB movers: "market-perceived role upgrade" movers bust MORE (44% — the market prices
  the new role in and reality underdelivers), and unproven backs handed a new chance are the real
  trap (52% bust, med mult 0.64). But PROVEN producers who moved (2yr ppg≥10, 12+ games) deliver
  their price (bust 30%, med 1.01) — the blanket 0.94 tilt was punishing exactly the wrong guys.
- **Fix:** split the RB mover tilt on proven production (no penalty for proven; .86 tilt + σ×1.2
  for unproven), validated in the backtest harness (subgroup pred/real: proven .33/.30, unproven
  .51/.52; global coverage 60.2%). Montgomery: bust 42→38%, ceiling 297→316, composite 58→53.
- **Teaches:** when the user says a rule feels wrong, the rule is often too COARSE rather than
  wrong-directioned — find the subgroup split that separates their counterexample from the cases
  the rule was built on, and let the backtest arbitrate. Also: definitions must survive contact
  with the pipeline's data window (snap-based "established" misfiled Montgomery; production-based
  didn't). (Principles 1, 5; collaboration rule: take "this looks off" seriously)

---

## L25 — The strategy is the PLAN, not a tiebreaker (user contract change, Jul 2026)
- **Symptom:** the user: "the model isn't following the strategy or really going out of its way to
  follow the strategy — which is what makes it the specific person's draft." The advisor treated
  value as the backbone with strategy as a conflict-surfacing tiebreak (the L20 contract).
- **Root cause of the worst failure:** the TOP PICKS prose said "this is the FINAL ranking: TAKE #1"
  — but that ranking is STRATEGY-BLIND (Python doesn't read the plan), so the prompt's own
  instructions contradicted each other and value won. Live test: strategy said "no WRs early no
  matter what" and the advisor still led with the WR, rationalizing the plan as "executes later."
- **Fix (`advisor.py`):** new decision order rule 0 — the strategy is the plan; ABSOLUTE
  instructions ("no X before round N", "no matter what") are BINDING with no deviation option;
  soft preferences deviate only via a protocol (12+ VONA cliff or hard gate) presented PLAN-FIRST.
  TOP PICKS prose now says the ranking is strategy-blind and the plan outranks it. Every PICK /
  PRE-READ answer includes a "Plan:" note. Strategy renders as its own MY DRAFT PLAN context block
  (passed to `build_context(strategy=...)`), no longer buried in the setup note. Python hard gates
  (n/a, BENCH-ONLY, OVER-STACKED) still outrank everything; soft demotions (PUNT-ABLE) yield to an
  explicit instruction. Verified with three live scenarios (absolute obeyed; soft preference read
  by its own terms; safe-early drives risk reasoning).
- **Teaches:** when two prompt sections give the model contradictory authority ("take #1" vs
  "follow the plan"), the model picks one and rationalizes — find and break the contradiction, and
  make precedence explicit. Personalization = the user's plan outranking the generic optimum.
  (Supersedes L20's value-first default; keeps its both-options transparency.)

---

## How to add a lesson
When a fix corrects a wrong assumption or a class of bug, append here in the same format during
Stage 05. Keep it short and concrete — the goal is that the next agent doesn't repeat it.
