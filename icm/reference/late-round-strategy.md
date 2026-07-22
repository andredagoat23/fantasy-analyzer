# The Late-Round Playbook (R11–16) — what the data actually says

**Where this comes from:** a full research campaign on 12 seasons of real NFL weekly data (2014–2025):
3,329 late-round player-seasons + 289 real "backup takes over" cases, analyzed by 13 independent
analyses, then attacked by 5 adversarial reviews (data leakage, small samples, era drift, definition
gaming, and an independent audit that reproduced ~40 key numbers bit-for-bit). Only rules that
SURVIVED that gauntlet are in here. Every rule was also checked on held-out 2022–2025 seasons it was
never fit on. The advisor's DART READ and HANDCUFF READ are this document, enforced in code.

---

## The one-paragraph version

Late picks are not about projections — by R11 everyone left projects below replacement, so ranking
by projected points just picks the least-bad veteran (that's how Theo Wease happens). What actually
predicts late-round hits is a small set of PROFILES. Buy: **WRs who already commanded 20%+ of their
team's WR targets last year**, **committee RBs who already had a real role** (the GO screen),
**a proven pocket QB who kept his team, priced QB15-20 on a good offense** (only if you still need
a QB), and — final rounds only — **a young TE the NFL itself invested a top-105 pick in**. Fade:
last year's injured formerly-good veteran, WRs 29+, late QBs on new teams, rookies the NFL didn't
believe in, and the deep end of every position. And hold humility: about a third of every season's
late-round league-winners fit NO signal anyone can see in July.

---

## The BUY list (in priority order)

| # | Profile | The numbers | What you're buying |
|---|---------|-------------|--------------------|
| 1 | **Late QB (only while yours is open):** proven vet (6+ yrs, 15+ ppg last yr), KEPT his team, QB15-20 price, good offense | front-band top-8 rate ~21% modern; the moved-QB version collapses to 2% | The highest-equity late cell in the entire study — a real shot at a weekly winner |
| 2 | **Post-hype target-share WR:** WR41-65 price, ≥20% of his team's WR targets last season (better yet with 10+ real ppg) | startable 17% vs 4% below the share line — the single most robust signal in the campaign (it got STRONGER out-of-sample) | A startable floor. NOT a league-winner claim (that leg didn't survive review) |
| 3 | **GO-screen committee RB:** RB31-50 price, at least 2 of {30%+ carry share last yr, team total ≥23, priced ≤RB50} | direction-only lean (holdout ~2x non-GO; the CI spans zero — never treat the 42% as a promise) | Startable weeks when (not if) an RB room breaks. ~9.5 ppg standalone if he's a true committee back |
| 4 | **Young high-capital TE dart (final rounds, only if TE open or your TE is risky):** age ≤25, NFL pick ≤105 | ~1-in-6 top-6 optimistic, ~1-in-10 modern | A cheap lottery ticket at the one position where a hit changes your week every week |

**Tiebreaker everywhere:** earlier ADP wins. The fancy combined dart score we built FAILED
out-of-sample validation (A10) — ADP order caught 6 of 9 holdout league-winners; the score caught 2.
That's why the advisor doesn't overlay a score on everything.

## The FADE list (talk yourself out of these)

| Fade | The numbers |
|------|-------------|
| **The injury-discount vet** (10+ ppg last year AND missed 6+ games) | startable 2% vs 14% baseline; **0 league-winners in 47 cases**. The discount is correct — the interaction is the poison: formerly-good & healthy hits 17.6%, cheap & injured 13.8%, the COMBO collapses |
| **WR age 29+ / 6+ years experience** | 0 late league-winners in 71 and 91 cases. The "year-2 WR breakout" is also a myth late (0/74) |
| **Late QB on a NEW team** | top-8 rate 2.2% vs 16.8% for QBs who stayed |
| **Rookies without top-100 NFL capital** | startable 6.5%. (And the reverse "high-capital rookie = prize" is ALSO null — capital only screens the bad, it doesn't find the good) |
| **The deep end of every band** (RB57+, WR75+, TE31+, QB29+) | back-third league-winner rate 1.9% vs 9.9% front-third. Spend late picks at the FRONT of each position's late band |
| **Any TE handcuff** | the one absolute rule: promoted TE backups boom 4.5% (p=5.5e-6). Every TE that ever paid off after a starter injury was already a 1B, not a handcuff |
| **The clipboard handcuff** — even behind your own stud | the GO screen is the draft-day rule: non-GO handcuffs hit at roughly half the GO rate (holdout). The famous clipboard-vs-committee split (~5% vs ~51/65%) is an IN-SEASON number — concurrent usage, only visible after weeks 3-4. Bell-cow-handcuffing showed a *directional* penalty only (the pooled version was a position-mix artifact — withdrawn as a rule, keep as a tilt) |
| **The Konami rushing-QB filter** | no evidence of benefit late (1/15 vs 14/101 — though the sample is too small to prove harm). Don't PAY for rushing narrative late; it just isn't a validated edge |

## The handcuff truth (what 289 real takeovers say)

- **Carries transfer ~1-for-1; targets scatter.** A promoted backup RB goes 4.0 → 9.5 ppg. A "promoted"
  WR gains +1.4 ppg because vacated targets spread across the whole offense. TE gains stay below
  streaming level. → RB handcuffs only.
- **The only thing that predicts a handcuff paying off is the role he ALREADY has** (in-season numbers; the draft-day GO screen recovers about half of this) — not his draft
  pedigree, not his age, not how hurt the starter is (a confirmed null!). Prior role → boom.
- **Half the edge is invisible in July.** Committee status is *revealed* by weeks 3-4 usage; the
  draft-day screen recovers about half the in-season signal. So: draft GO-screen candidates, keep
  bench flexibility, and budget FAAB to pounce when usage reveals the real committees. The waiver
  version of this edge is STRONGER than the draft version.

## The honesty section (read before draft day)

- A 12-team league produces only **~6-7 late-round league-winners per season LEAGUE-WIDE** — about
  one per two teams. Nobody drafts their way to all of them.
- **~35% of late-round league-winners fit no preseason archetype at all** (39% in 2022-25). The best
  defensible profile set captures about **half** of the rest.
- What this playbook actually does: roughly **doubles your per-pick odds in the right cells**, buys
  real startable floors, and — just as important — keeps you from lighting picks on fire (the fade
  list is better-validated than most of the buy list).
- Positional league-winner ordering, modern era: **QB 13% > TE 5.5% > RB 3.8% > WR 1.6%** — but on
  weekly-startable outcomes it inverts (QB 54% > WR 14% > RB 7% > TE 6%). Late QBs/TEs are
  lottery tickets; late WRs are floor plays; late RBs are contingency plays. Draft accordingly.

## What was tried and REJECTED (so nobody re-litigates it)

- A combined RB/WR "dart score" — validated beautifully in-sample, failed the 2022-25 holdout (its
  draft-capital component literally inverted). ADP order beat it.
- "Good offense" gates for late RB/WR — an artifact of a data leak (season-average Vegas totals
  drift toward the player's own outcome). Clean preseason totals kill the effect for RB/WR;
  it survives only for QB (attenuated) and mildly TE.
- Handcuffing by starter fragility, ceiling ranking, bell-cow logic, chronic-injury starters,
  young-ascending-back narratives, year-2 WR breakouts, rushing-QB upside: all null or refuted.
- Any claim that role/share signals find LEAGUE-WINNERS: they find STARTABLE WEEKS. At the ≥15 ppg
  threshold every share signal dies (holdout slope p=.88). The advisor is required to say
  "startable," never "league-winning," about these.

*Full evidence trail: `icm/work/mc_research/` scratchpad `lateround/` (13 analysis reports, 5
adversarial reports, SYNTHESIS.md). Encoded: `advisor._dart_profiles` / `_dart_read` /
`_go_score` / `_handcuff_read`, data layer `role_priors.py` → `role_data.csv`, tests
`tests/test_dart.py` + `tests/test_handcuff.py`, lesson L31.*
