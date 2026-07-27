"""29 — Availability, deeper: does MILEAGE predict breakdown? (the curse of 370, age cliffs, career wear)

Why this and not something else: 26_ showed being unavailable causes 73-85% of busts in EVERY round
band (QB 97%). It is the dominant failure mode in fantasy football, and 24_ showed the obvious tells
are worthless — last year's games played correlates with this year's at r=+0.019. But two things DID
survive there: light prior workload, and position. That points at WEAR, so this script attacks wear
properly with the one thing 24_ never used: a player's CAREER mileage, accumulated across the panel.

Hypotheses tested (all famous, all testable with this data, all draft-day knowable):
  H1 "Curse of 370"  — a 370+ carry season breaks a back the following year.
  H2 Career mileage  — cumulative touches predict the breakdown better than any single season.
  H3 RB age cliff    — backs fall off a cliff at some age (26? 28? 30?).
  H4 Age x mileage   — young legs survive a heavy load; old legs don't (the interaction).

Outcomes: P(plays 15+ games) and HIT (mult >= 1.0). Career totals are truncated for players who
entered before the panel starts, so every career analysis is ALSO reported on the clean subset
(entry_year >= 2015) where the accumulation is genuinely complete.

Run:  .venv/bin/python icm/work/mc_research/29_mileage_and_availability.py
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_29_mileage.txt")

NUM = ["adp", "age", "mult", "games", "season", "total_touches", "prev_total_touches", "carries_pg",
       "prev_carries_pg", "prev_games", "entry_year", "years_exp", "draft_number", "prev_ppg"]
N_BOOT = 2000
RNG = np.random.default_rng(0)

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def load():
    p = pd.read_parquet(PANEL)
    for c in NUM:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p[p["position"].isin(["RB", "WR", "TE", "QB"])].copy()
    p = p.sort_values(["player_id", "season"])
    # CAREER touches accumulated BEFORE this season (shift so it's draft-day knowable)
    g = p.groupby("player_id")["total_touches"]
    p["career_touches_before"] = (g.cumsum() - p["total_touches"].fillna(0)).fillna(0)
    p["prev_carries_total"] = p["prev_carries_pg"] * p["prev_games"]
    p["full"] = (p["games"] >= 15).astype(float)
    p["hit"] = (p["mult"] >= 1.0).astype(float)
    p["clean_career"] = p["entry_year"] >= 2015          # career total is genuinely complete
    return p


def boot_diff(a, b):
    """P(mean(a) > mean(b)) by bootstrap."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 8 or len(b) < 8:
        return np.nan
    out = np.empty(N_BOOT)
    for i in range(N_BOOT):
        out[i] = (a[RNG.integers(0, len(a), len(a))].mean()
                  - b[RNG.integers(0, len(b), len(b))].mean())
    return float((out > 0).mean())


def bucket_table(sub, col, edges, labels, title, drafted_only=True):
    d = sub[sub["adp"].notna()] if drafted_only else sub
    say(f"\n{title}")
    say(f"  {'bucket':<22}{'n':>6}{'P(15+ g)':>10}{'HIT':>8}{'med mult':>10}")
    rows = []
    for (lo, hi), lab in zip(edges, labels):
        m = d[col].between(lo, hi)
        s = d[m]
        if len(s) < 12:
            say(f"  {lab:<22}{len(s):>6}   (too few)")
            rows.append(None)
            continue
        say(f"  {lab:<22}{len(s):>6}{s['full'].mean():>10.1%}{s['hit'].mean():>8.1%}"
            f"{s['mult'].median():>10.2f}")
        rows.append(s)
    return rows


def main():
    p = load()
    rb = p[p["position"] == "RB"]
    say(f"panel {len(p)} player-seasons · RB {len(rb)} · drafted (has ADP) {int(p['adp'].notna().sum())}")
    say(f"clean-career subset (entered 2015+): {int(p['clean_career'].sum())} seasons\n")

    say("=" * 84)
    say("H1 — THE CURSE OF 370: does a monster carry season break a back the NEXT year?")
    say("=" * 84)
    # NOTE: carries alone can't test this — the panel holds only 2 seasons at 370+ carries and 25 at
    # 300+, so the literal "370" threshold is untestable. TOUCHES (carries + receptions) is both the
    # better wear proxy for a modern back and has usable sample, so the hypothesis is tested on that.
    d = rb[rb["adp"].notna() & rb["prev_total_touches"].notna()]
    say("  (tested on prev-season TOUCHES — only 2 seasons in the panel reach 370 carries)")
    for thr in (250, 300, 350):
        hi = d[d["prev_total_touches"] >= thr]
        lo = d[d["prev_total_touches"] < thr]
        if len(hi) < 10:
            say(f"  prev touches >= {thr}: only n={len(hi)} — too few")
            continue
        pg = boot_diff(lo["full"], hi["full"])
        say(f"  prev touches >= {thr}: n={len(hi):<4} P(15+ g) {hi['full'].mean():.1%} vs "
            f"{lo['full'].mean():.1%} for the rest ({100 * (hi['full'].mean() - lo['full'].mean()):+.1f}pp)"
            f" · HIT {hi['hit'].mean():.1%} vs {lo['hit'].mean():.1%}"
            f" · P(rest more available) {pg:.2f}")

    say("\n" + "=" * 84)
    say("H2 — CAREER MILEAGE: do cumulative touches predict breakdown? (RB, drafted seasons)")
    say("=" * 84)
    edges = [(0, 249), (250, 749), (750, 1249), (1250, 1749), (1750, 99999)]
    labs = ["<250 career", "250-749", "750-1249", "1250-1749", "1750+"]
    bucket_table(rb, "career_touches_before", edges, labs, "ALL RBs with an ADP:")
    bucket_table(rb[rb["clean_career"]], "career_touches_before", edges, labs,
                 "CLEAN subset (entered 2015+, career total complete):")

    say("\n" + "=" * 84)
    say("H3 — THE RB AGE CLIFF: where does it actually happen?")
    say("=" * 84)
    # age is a CONTINUOUS float in this panel (median 25.70), so single-integer bins catch nothing
    edges = [(0, 23.999), (24, 24.999), (25, 25.999), (26, 26.999), (27, 27.999),
             (28, 28.999), (29, 50)]
    labs = ["<=23", "24", "25", "26", "27", "28", "29+"]
    bucket_table(rb, "age", edges, labs, "RB by age (drafted seasons):")
    say("\n  same for WR (contrast — is the cliff RB-specific?):")
    bucket_table(p[p["position"] == "WR"], "age", edges, labs, "WR by age:")

    say("\n" + "=" * 84)
    say("H4 — AGE x MILEAGE: do young legs absorb a heavy load that old legs can't?")
    say("=" * 84)
    d = rb[rb["adp"].notna() & rb["career_touches_before"].notna()]
    say(f"  {'':<16}{'low mileage (<750)':>22}{'high mileage (750+)':>22}")
    for lo_a, hi_a, lab in [(0, 25, "age <=25"), (26, 27, "age 26-27"), (28, 40, "age 28+")]:
        row = f"  {lab:<16}"
        cells = []
        for ml, mh in [(0, 749), (750, 99999)]:
            c = d[d["age"].between(lo_a, hi_a) & d["career_touches_before"].between(ml, mh)]
            cells.append(c)
            row += (f"{f'{c.full.mean():.0%} avail, n={len(c)}':>22}" if len(c) >= 12
                    else f"{'—':>22}")
        say(row)
        if all(len(c) >= 12 for c in cells):
            say(f"  {'':<16}{'':>22}   P(low-mileage more available) = "
                f"{boot_diff(cells[0]['full'], cells[1]['full']):.2f}")

    say("\n" + "=" * 84)
    say("SURVIVORSHIP CONTROL — hold PRICE fixed, then vary mileage")
    say("=" * 84)
    say("  Raw mileage buckets are badly confounded: only good backs survive long enough to")
    say("  accumulate touches AND still get drafted, so high mileage self-selects for quality.")
    say("  ADP already encodes that quality — so compare high vs low mileage WITHIN a price band.")
    for lo_a, hi_a, lab in [(1, 40, "ADP 1-40"), (41, 90, "ADP 41-90"), (91, 200, "ADP 91-200")]:
        s = d[d["adp"].between(lo_a, hi_a)]
        a = s[s["career_touches_before"] < 750]
        b = s[s["career_touches_before"] >= 750]
        if len(a) < 12 or len(b) < 12:
            say(f"  {lab}: too few to split (low {len(a)} / high {len(b)})")
            continue
        say(f"  {lab}: HIT {a['hit'].mean():.1%} (low mi, n={len(a)}) vs {b['hit'].mean():.1%} "
            f"(high mi, n={len(b)}) = {100 * (a['hit'].mean() - b['hit'].mean()):+.1f}pp · "
            f"avail {a['full'].mean():.0%} vs {b['full'].mean():.0%} · "
            f"P(low better) {boot_diff(a['hit'], b['hit']):.2f}")

    say("\n" + "=" * 84)
    say("CONTROL — is mileage just a stand-in for AGE? (RB, holding age band fixed)")
    say("=" * 84)
    for lo_a, hi_a, lab in [(0, 25, "age <=25"), (26, 27, "age 26-27"), (28, 40, "age 28+")]:
        s = d[d["age"].between(lo_a, hi_a)]
        a = s[s["career_touches_before"] < 750]
        b = s[s["career_touches_before"] >= 750]
        if len(a) < 12 or len(b) < 12:
            say(f"  {lab}: too few to split")
            continue
        say(f"  {lab}: HIT {a['hit'].mean():.1%} (low mi, n={len(a)}) vs {b['hit'].mean():.1%} "
            f"(high mi, n={len(b)}) = {100 * (a['hit'].mean() - b['hit'].mean()):+.1f}pp"
            f" · P(low better) {boot_diff(a['hit'], b['hit']):.2f}")

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
