# Positional-run dynamics — what REALLY happens after a run (Jul 27, 2026)

**Why:** L48 shipped the POSITION RUN read on an assumption ("a run means the position is draining —
act early"), and the user then challenged the 1-start half of it ("if there's a five-QB run doesn't
that make it LESS likely another QB goes?"). Neither claim had evidence. Sleeper's public API is a
real pick-by-pick corpus, so we measured it instead of arguing.

**Corpus:** 1,162 completed 2026 12-team snake drafts, **372,394 picks**, crawled from Sleeper's
public API (`mc_research/21_sleeper_run_corpus.py`, throttled ~6 req/s, no user ids stored).
Split by format — **111 one-QB** (the user's format) and 1,051 superflex/2QB (contrast). Format
segmentation was essential: superflex drafts take QBs at 29% of round-1 picks vs 4% in one-QB, so
pooling them would have produced a garbage answer.

**Method** (`22_run_dynamics.py`): every 8-pick window, slot-matched baselines from the corpus, the
same HOT/COLD binomial tests the shipped code uses. Outcome = did that position get taken on the very
next pick, and within the next four? Δ is measured against the baseline **at exactly the conditioned
slots**, so round-mix can't fake an effect.

---

## Finding 1 — positional runs do NOT continue. The core premise of L48 is false.

| segment | RB HOT | WR HOT | QB HOT | TE HOT |
|---|---|---|---|---|
| one-QB (n windows 519-717) | **−2.9pp** | +0.6 | +1.5 | −3.0 |
| superflex (n windows 8.4k-9.6k) | **−1.0pp** | −0.1 | +2.5 | +0.4 |

Δ = change in P(position taken in the next 4 picks) vs the slot-matched baseline.

Every value is a null. The superflex RB cell rests on **9,200 windows** and lands at −1.0pp — with
that much data a real momentum effect would be unmissable. Dose-response doesn't rescue it either:
superflex RB reads +12.2pp at k=3 (n=38) and +10.7 at k=4 (n=199), then −1.0 at k=5 (**n=6,799**) and
−2.4 at k≥6 (n=2,164) — the "positive" cells are the tiny ones, which is what noise looks like.

**"Five of the last eight were RBs, so the cliff is NOW" is folklore.** It does not predict more RBs.

## Finding 2 — the COLD side is real, sizable, and replicates

| segment | RB COLD | WR COLD | QB COLD |
|---|---|---|---|
| one-QB | −2.5pp (n=1,197) | **−11.5pp** (n=1,253) | — (n=0) |
| superflex | −3.5pp (n=15,784) | **−7.7pp** (n=15,628) | −5.6pp (n=3,883) |

A position the room has been ignoring **keeps** getting ignored. WR is the strongest and it replicates
across both formats on five-figure samples. In plain terms: when receivers have gone cold, ~12% fewer
receivers than baseline come off the board over your next four picks — so the value genuinely does
keep falling toward you, and the wheel-back there is safer than ADP-based survival says.

**Mechanism honesty:** this is probably *room/settings preference persistence* more than live
sentiment — a room that has been WR-light is a room that stays WR-light. That's a different story from
"momentum," but it is equally predictive and equally actionable, which is what matters for the read.

## Finding 3 — the 1-start depletion argument is also not a real force
The user's hypothesis was that a QB run removes QB-needy teams and should *suppress* future QB picks.
Checked directly: after a QB HOT window, the next four picking teams already hold a QB **77.3%** of the
time vs a **74.8%** round-matched baseline — a +2.5pp depletion, far too small to drive anything. And
the net QB HOT effect is +1.5pp (one-QB) / +2.5pp (superflex), i.e. nothing.

So depletion is real but tiny, and it roughly cancels whatever urgency effect exists. **Neither
momentum nor depletion meaningfully moves QB.** The proposed "restrict flags to RB/WR" fix was aimed
at the right worry but the wrong half of the feature — HOT doesn't work for RB/WR either.

---

## What this means for L48 (shipped locally, UNPUSHED — `da8a695`)
The read currently tells the model, for a HOT position the user needs: *"act before your wheel; treat
'risky' wheels as gone."* **That advice is unsupported by 372k real picks** and should not go live.

**Recommended change (needs the user's go):**
1. **Delete the HOT branch entirely.** No evidence in either format at any run size.
2. **Keep COLD, and keep the framing the user already corrected me into** — the value is falling TO
   you; a faller worth taking now already tops TOP PICKS, otherwise take the scarcer need first and
   collect him on the wheel. That framing is exactly what the data supports.
3. Rename the line from POSITION RUN to something honest (e.g. **COLD POSITION**), and state the
   measured effect in it so the model weights it correctly rather than guessing.
4. Keep it advisory. The effect is a ~7-12pp survival nudge, not a re-ranking mandate.
5. Update `tests/test_run.py` (drop HOT cases, keep/extend COLD), lessons L48, `draft-strategy.md`,
   `architecture.md`.

## Reusable lesson
The project already knew "don't ship an unvalidated magnitude into the math," and L48 honored that by
staying advisory — which is the only reason this is a cheap fix instead of a bad pick on draft day.
But *advisory prose is still a claim*: telling the model "act early" is an instruction, and it was
wrong. **Validate the direction of advice, not just the size of a coefficient.** Also: when a public
API can settle an argument, crawl it before theorizing — this took one afternoon and killed a feature
premise that fantasy convention treats as obvious.
