# Draft PREREQUISITES — what has to be true for a pick to hit (Jul 27, 2026)

**The question (user hypothesis):** every player carries a specific set of make-or-break conditions,
so the useful research is per-player — "what separated the boom seasons from the bust seasons for
players *like him*." The cohort layer already gives marginal RATES + named comps; it cannot say what
had to be TRUE.

**Data:** `seasons_exp.parquet`, the project's own 2014-25 panel — 1,661 priced player-seasons from
2015-2025. Outcome = `mult` (season finish ÷ preseason price): HIT ≥ 1.0, BUST ≤ 0.7. Every condition
is knowable ON DRAFT DAY (prior-season or static).

**Rigor.** Findings are stress-tested, not asserted: a **bootstrap** (2,000 resamples, fixed seed) for
P(lift > 0), plus a **sensitivity grid** re-deriving every condition under 9-12 different definitions
of "first round" and "hit". Verdicts are strict — ROBUST needs P ≥ 0.90 **and** ≥ 75% of the grid.
Scripts: `mc_research/23_` (base) · `24_` (availability) · `25_` (stress) · `26_` (bands + taxonomy)
· `27_` (2026 screen) · `28_` (decomposition).

> **⚠️ The stress test in `25_` demoted several claims from the first pass. Everything below is the
> post-stress version.** The first-pass write-up over-claimed; this supersedes it.

---

## Finding 1 — picks don't disappoint, they get hurt. At EVERY round.
The bust taxonomy (`26_`) classifies each bust by *how* it failed: **unavailable** (played ≤12 games),
**role loss** (played 13+, usage collapsed below 75% of prior year), **inefficient** (played 13+, kept
the role, still missed).

| band | bust rate | unavailable | role loss | inefficient |
|---|---|---|---|---|
| R1 (ADP 1-15) | 19% | **81%** | 0% | 19% |
| R2-3 (16-40) | 19% | **82%** | 11% | 4% |
| R4-6 (41-75) | 23% | **85%** | 8% | 5% |
| R7-10 (76-125) | 26% | **73%** | 16% | 6% |

By position: RB 80% unavailable · WR 73% · TE 77% · **QB 97%**. A quarterback essentially only busts
by not playing.

*Honest wording:* "unavailable" = played ≤12 games, which conflates injury with benching. For QBs in
particular some of that is being benched, not hurt.

## Finding 2 — availability is close to unpredictable, and the popular tells are worthless
Base P(15+ games) among first-rounders = 58.6%. Tested against it (`24_`):

| claim | train lift | holdout | verdict |
|---|---|---|---|
| played 16+ games last year | −4.3pp | −3.6 | no signal |
| no injury history (0 wks out) | −11.0pp | −3.6 | no signal (negative) |
| big backs hold up (RB ≥215 lbs) | −16.0pp | −21.1 | **negative** |
| light prior workload | +15.4pp | +8.3 | holds |
| he's a WR, not an RB | +13.7pp | +5.9 | holds |

**Correlation between last year's games played and this year's: +0.019** — zero. Players who missed
badly last year (≤10 games) played 15+ this year **57.1%** of the time, *better* than those who were
basically healthy (53.2%). Age vs games: −0.058.

Only **cumulative workload** and **position** survive (RB 51.9% vs WR 66.7% play 15+). This
independently validates the pipeline: the MC applies a *position-level* availability prior rather than
a player-specific injury-history adjustment, which is exactly right given r=+0.019.

> **Flag, not an edit:** prior-season total touches predicting availability is not modeled anywhere,
> and `compute_outcomes.py` is frozen. Raised as a roadmap item per the rules.

## Finding 3 — what predicts HITTING is position- and band-specific, and survives stress badly
After bootstrap + grid (`25_`, `26_`), only these clear the bar:

| band | condition | lift | P(>0) | grid |
|---|---|---|---|---|
| R1 | receiving involvement (WOPR) | +11.9 | 0.93 | 9/9 |
| **RB only, R1** | **NFL draft capital ≤32** | **+18.6** | **0.95** | **12/12** |
| **RB only, R1** | **receiving involvement** | **+16.0** | **0.92** | **12/12** |
| R2-3 | NFL draft capital top-64 | +9.1 | 0.93 | 7/9 |
| R7-10 | draft capital ≤32 | +6.9 | 0.91 | 8/9 |
| R7-10 | receiving involvement | +12.2 | 0.99 | 7/9 |
| R7-10 | played 15+ last year | +8.7 | 0.97 | 8/9 |

**Demoted by the stress test** (these were "HOLDS" on the first pass): WR *earned production* → shaky
(10/12, P=0.85). WR *proven at price* → shaky and **fragile at only 4/12 settings**. This matters —
see Finding 5, which explains why.

**Confirmed DEAD** (0-2 of 12 settings): prior-season durability at R1, week-to-week consistency,
elite prior volume, youth, snap share, offense quality. Fading a first-rounder for any of these is
unsupported. Note `durable_prev` is DEAD at R1 but **ROBUST at R7-10** — the same condition flips
meaning by band, which is the whole reason band-specific analysis was necessary.

## Finding 4 — early picks boom by *keeping* a role; late picks boom by *gaining* one
Among boom seasons (mult ≥ 1.3), the share whose usage grew 25%+ over the prior year:

| band | booms that grew usage 25%+ | median usage ratio |
|---|---|---|
| R1 | 15% | 1.08x |
| R2-3 | 20% | 1.10x |
| R4-6 | 27% | 1.10x |
| R7-10 | **42%** | **1.20x** |

A clean monotonic gradient. Early, you are buying *continuation* — screen for role security and
availability. Late, you are buying *change* — screen for a path to more work. This independently
validates the existing DART READ philosophy (post-hype target share, committee handcuffs): those are
all "path to a bigger role" bets, which is exactly what the late bands reward.

## Finding 5 — the strongest mid-round result is CONDITIONAL, not general (`28_`)
`proven_at_price` (last year's positional finish ≥ this year's positional price) looked like the best
result in the study at R4-6: +10.4pp, P=0.97, 9/9. Suspecting it merely re-detected last year's
injuries, we split the band by whether the player was healthy:

| R4-6 | proven | not proven |
|---|---|---|
| healthy last year | 53% (n=135) | 51% (n=69) |
| **missed time last year** | **73% (n=22)** | **43% (n=117)** |

Among **healthy** players it is inert (+2.6pp, P=0.65). The entire effect is an **interaction**: it
only says something about a player coming off a season where he missed time. Health alone explains
just +5.0pp, so this is not a simple proxy — it is a genuinely conditional prerequisite.

**The actionable form:** for a player coming off a lost/injured season, ask whether he *still*
out-produced his current price. If yes, he's a strong buy (73%, though n=22). If no, he's a real fade
(43%, n=117 — a big, trustworthy sample). This agrees with the existing validated late-round rule
that the "injury-discount vet" is a fade, and sharpens it: the discount is only worth buying when the
production survived the injury.

**This is the clearest support for the user's original hypothesis** — prerequisites are conditional on
a player's profile, not a universal checklist. It also means the earlier
Chase/Lamb/Jefferson "priced for a bounce-back" flag was over-stated: at R1 the condition is DEAD.

## Finding 6 — "wear" is mostly a myth; the RB age decline is real but gradual (`29_`)
Since being unavailable causes most busts, we attacked it with career mileage accumulated across the
panel. (The literal "curse of 370" is untestable — only **2** seasons in 12 years reach 370 carries —
so it was tested on total touches, the better wear proxy anyway.)

- **Career mileage does NOT predict breakdown.** Holding *price* fixed — essential, since only good
  backs survive long enough to accumulate touches and still get drafted — high-mileage RBs did
  slightly **better**: ADP 1-40 → 58.3% hit (high mileage) vs 54.4% (low); ADP 41-90 → 55.6% vs 47.8%.
  P(low better) = 0.31 / 0.23. The wear story collapses once you control for survivorship.
- **One real signal at the extreme:** a back coming off a **350+ touch** season hit only **22.2%**
  (n=18) vs 53.9% for everyone else, with availability −8.9pp. Small sample, big gap — the damage
  shows up more in missing his (elevated) price than in missing games.
- **The RB age curve is a slope, not a cliff.** Availability by age: 24 → 56.8%, 25 → 42.2%,
  26 → 50.0%, 27 → 46.3%, 28 → 37.2%, 29+ → 38.5% (median mult 0.92). Availability sags from ~28 and
  value from ~29. **It's RB-specific:** WRs hold 52-62% availability at *every* age, including 29+.

## Finding 7 — rounds 2-3 are the best value band on the board (`30_`)
| band | HIT | BUST | median mult | median finish vs price |
|---|---|---|---|---|
| R1 (1-15) | 52.4% | 18.6% | 1.02 | finishes 9th, priced 4th |
| **R2-3 (16-40)** | **60.1%** | 18.5% | **1.07** | finishes 15th, priced 12th |
| R4-6 (41-75) | 50.4% | 23.0% | 1.01 | finishes 25th, priced 23rd |

R2-3 has the highest hit rate and the *same* bust rate as round 1. Round 1 also carries the worst
price-to-finish slippage — you pay for the 4th-best player at the position and get the 9th. This is a
value story, not a talent story: you aren't buying better players in round 2, you're buying a cheaper
promise, and the cheaper promise is met more often.

## Finding 8 — in rounds 2-3 the market OVER-prices visible health and production
Inside R2-3, several "good" traits are strongly **negative** predictors of beating price:

| condition | lift | P(lift>0) |
|---|---|---|
| played 15+ games last year | **−16.5pp** | 0.01 |
| had a real role last year (50%+ snaps) | −13.0pp | 0.06 |
| light prior workload | −12.1pp | 0.03 |
| earned production (not TD-lucky) | −10.4pp | 0.07 |

For RBs specifically, prior durability is **−23.6pp** (P=0.01). The mechanism is pricing, not
football: a player who was healthy and productive last year is priced *at* that, so there is no room
left in his cost. The discounted player in the same band has room. This is the same structure as
Finding 5 and it explains why `durable_prev` was DEAD in round 1 yet ROBUST at R7-10 — by the late
rounds the market stops paying for health.

**Tension to respect:** `late-round-strategy.md` validated that the "injury-discount vet" is a FADE at
R11+ (0 league-winners in 47 cases). That is a different band and a different outcome metric
(league-winner, not mult ≥ 1.0). Finding 5 reconciles them: the discount is only worth buying when
the player *still out-produced his price* despite missing time.

## Finding 9 — the unifying rule: draft capital matters exactly when you can't judge the usage
The interaction scan (35 tests, survivors listed with their sample sizes) produced one result far
beyond what noise makes, plus a family of results telling the same story:

| condition | applies to | lift there | lift elsewhere | P | n |
|---|---|---|---|---|---|
| **capital top-32** | **no real role last year** | **+42.3pp** | +0.6 | 1.00 | 38 |
| capital top-64 | no real role last year | +33.9pp | +5.6 | 0.99 | 38 |
| capital top-32 | missed time last year | +22.1pp | +0.7 | 0.99 | 94 |
| capital top-32 | age ≤25 | +16.7pp | +0.3 | 0.94 | 80 |
| proven at price | inexperienced (<3 yr) | +22.3pp | −8.3 | 0.98 | 79 |

Every one points the same way: **NFL draft capital is a powerful signal precisely when recent usage
data is missing or unreliable — no role, injured, or too young to have a book — and is worth nothing
when you can already judge him on an established role.** That is a mechanism, not a curve fit, which
is why it's believable at n=38.

**Applied to your 2026 board at picks 18 and 31**, exactly one player in the band has no 2025 role:
**Jeremiyah Love** (rookie, NFL #3) — capital-backed, so the rule says trust the pedigree. Everyone
else has a real 2025 role, which means their draft capital is **irrelevant** and should not be used
against them. Concretely: do **not** fade Chase Brown (#163), Kyren Williams (#164), De'Von Achane
(#84) or Nico Collins (#89) for weak draft capital — all four carried genuine 2025 roles (69%, 63%,
63%, 35% shares). A naive marginal capital screen would have wrongly faded all of them.

---

## Honest limits
- R1 is n=145 (81 RB / 60 WR); bootstrap intervals on the ROBUST findings still cross zero (RB capital
  is +18.6 with a 95% interval of [−3.8, +40.7]). What earns belief is grid stability + P(>0) + a real
  mechanism, not the point estimate. Treat every lift as directional.
- ~15 conditions × multiple populations were tested, so some survivor is chance. The stress test in
  `25_` exists precisely because the first pass over-claimed.
- The "missed time + proven" buy cell is n=22. Directionally strong, not precise.
- Finding 1 (the failure-mode split) is a plain descriptive count and is the most robust thing here.
- The interaction scan (Finding 9) ran 35 tests and ~15 cleared the bar, which is more than chance
  would give but still means individual rows need re-checking. The capital × no-role row (+42.3pp,
  P=1.00) is the one far enough outside noise to act on, and it has a clean mechanism.
- Finding 8's negative conditions are about BEATING A PRICE, not about football quality. "Durable
  players are bad" would be a catastrophic misreading — the claim is that durability is already paid
  for at that price. Never carry these into a context where the outcome isn't value-over-price.
- The 350+ touch finding is n=18.

## Usage — proposed, NOT built. Awaiting the user's call.
1. **Pre-draft study sheet** — `27_` already generates a per-pick screen for slot 7
   (`results_27_2026_screen.txt`), applying each band's ROBUST condition. Zero draft-day risk.
2. **An advisory PREREQ line** in `build_context` mirroring COHORT HISTORY. Advisory only.
3. **Do NOT** feed any of this into `rank_composite` — small n + multiple testing is exactly the
   overfitting L45/L46 avoided.
