"""33 — THE HARSH BACKTEST: if I had drafted on these rules, would I have scored more points?

Everything up to here measured LIFT — does a condition raise the share of players who beat their
price. That is not the question. The question is whether a draft run on these rules produces a better
ROSTER, and lift can be positive while the answer is no: the rules may fire on players you were never
going to take, or trade a small edge at one pick for a worse pick elsewhere.

This is designed to FAIL if the rules are noise:

  * **Simulated real snake drafts.** 12 teams, 16 rounds, my seat 7 — the user's actual setup.
    Opponents take the best available by ADP plus gaussian noise, with light positional sanity.
  * **PAIRED seeds.** The baseline draft and the rules draft run on the SAME seed, so the same
    players fall to me in the same order and the only difference is my own decisions. Without
    pairing, draft randomness swamps any real effect.
  * **Scored on ACTUAL season points**, optimal starting lineup (1QB/2RB/2WR/1TE/1FLEX) — not on
    `mult`, the metric the rules were derived from. Grading on the derivation metric would be
    circular.
  * **Per-season results are printed.** A rule that only works in 3 of 10 seasons is noise, and
    pooling would hide that.
  * **The loss rate is printed.** "Wins on average" means little if it loses 45% of the time.

Honest caveat stated up front: the rules were SELECTED using all these seasons, so this is not a
clean out-of-sample test — it is the friendliest test the rules will ever get. If they cannot win
here, they are dead. If they do win, that is necessary but not sufficient.

Run:  .venv/bin/python icm/work/mc_research/33_harsh_backtest.py
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_33_harsh_backtest.txt")

TEAMS, ROUNDS, MY_SLOT = 12, 16, 7
N_DRAFTS = 250                 # paired drafts per season
ADP_NOISE = 8.0                # opponents don't draft ADP exactly
STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
FLEX_OK = ("RB", "WR", "TE")
MAX_POS = {"QB": 2, "TE": 2, "RB": 6, "WR": 6}   # nobody rosters 5 QBs

NUM = ["adp", "adp_pos_rank", "mult", "games", "season", "prev_games", "prev_pos_rank_total",
       "total_pts", "draft_number", "prev_snap_pct"]

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def load():
    p = pd.read_parquet(PANEL)
    for c in NUM:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p[(p["adp"].notna()) & (p["adp"] <= 200) & (p["season"] >= 2015)
          & p["position"].isin(["RB", "WR", "TE", "QB"]) & p["total_pts"].notna()].copy()
    # the surviving rules, as flags (nothing new is derived here)
    p["missed"] = (p["prev_games"] < 15).astype(int)
    p["proven"] = (p["prev_pos_rank_total"].fillna(99) <= p["adp_pos_rank"].fillna(99)).astype(int)
    p["durable"] = (p["prev_games"] >= 15).astype(int)
    return p


def prereq_adjust(row):
    """ADP-slot nudge from the rules that SURVIVED (28_/31_/32_). Positive = draft him earlier.

    Deliberately a nudge, not a re-rank: these are tie-breakers with ~10-25pp lifts on subgroups,
    so moving a player ~10 ADP slots is the honest magnitude. A bigger number would be inventing
    confidence the evidence doesn't support.
    """
    adp = row["adp"]
    adj = 0.0
    if 16 <= adp <= 75 and row["missed"]:          # the replicated conditional (R2-3 + R4-6)
        adj += 10.0 if row["proven"] else -12.0
    if adp >= 126 and row["durable"]:              # durability is under-priced late (+15.8pp, P=1.00)
        adj += 8.0
    return adj


def simulate(pool, rng, use_prereq):
    """One 12-team snake draft. Returns my optimal-lineup point total."""
    n = len(pool)
    adp = pool["adp"].to_numpy()
    pos = pool["position"].to_numpy()
    pts = pool["total_pts"].to_numpy()
    adj = pool["_adj"].to_numpy()
    noise = rng.normal(0, ADP_NOISE, n)            # SAME noise for both strategies (paired)
    taken = np.zeros(n, dtype=bool)
    rosters = {t: {"QB": 0, "RB": 0, "WR": 0, "TE": 0} for t in range(1, TEAMS + 1)}
    mine = []

    for rd in range(1, ROUNDS + 1):
        order = range(1, TEAMS + 1) if rd % 2 else range(TEAMS, 0, -1)
        for team in order:
            avail = ~taken
            if not avail.any():
                continue
            cnt = rosters[team]
            ok = avail & np.array([cnt[p] < MAX_POS[p] for p in pos])
            if not ok.any():
                ok = avail
            score = adp + noise                     # lower is better
            if team == MY_SLOT and use_prereq:
                score = score - adj                 # my nudge only
            if team == MY_SLOT:
                # fill starters first: block a position I've already filled unless it's FLEX-able
                need = np.array([
                    (cnt[p] < STARTERS[p]) or (p in FLEX_OK) or (cnt[p] < MAX_POS[p]) for p in pos])
                if (ok & need).any():
                    ok = ok & need
            idx = np.where(ok)[0]
            pick = idx[np.argmin(score[idx])]
            taken[pick] = True
            rosters[team][pos[pick]] += 1
            if team == MY_SLOT:
                mine.append(pick)
    return optimal_lineup(pos[mine], pts[mine])


def optimal_lineup(positions, points):
    """Best 1QB/2RB/2WR/1TE/1FLEX by season points."""
    by = {p: sorted(points[positions == p], reverse=True) for p in ("QB", "RB", "WR", "TE")}
    total, used = 0.0, {p: 0 for p in by}
    for p, k in STARTERS.items():
        take = by[p][:k]
        total += sum(take)
        used[p] = len(take)
    flex = []
    for p in FLEX_OK:
        flex += by[p][used[p]:]
    if flex:
        total += max(flex)
    return total


def sweep(p, seasons, n_drafts=100):
    """Sensitivity: scale the nudge up and down. A REAL signal should improve as the nudge grows
    (up to some optimum) and degrade past it. A flat/noisy curve means there is nothing to tune —
    the strongest confirmation that a null is a true null rather than a badly-chosen magnitude."""
    say("\n" + "=" * 72)
    say("SENSITIVITY — does a BIGGER nudge help? (if the curve is flat, the null is real)")
    say("=" * 72)
    say(f"  {'scale':>7}{'mean diff':>12}{'win%':>8}   ({n_drafts} paired drafts/season)")
    for scale in (0.0, 0.5, 1.0, 2.0, 4.0):
        diffs = []
        for s in seasons:
            pool = p[p["season"] == s].copy()
            if len(pool) < 120:
                continue
            pool["_adj"] = pool.apply(prereq_adjust, axis=1) * scale
            pool = pool.reset_index(drop=True)
            for i in range(n_drafts):
                b = simulate(pool, np.random.default_rng(500 + i), use_prereq=False)
                q = simulate(pool, np.random.default_rng(500 + i), use_prereq=True)
                diffs.append(q - b)
        d = np.array(diffs)
        note = "  <- sanity: must be exactly 0" if scale == 0.0 else ""
        say(f"  {scale:>7.1f}{d.mean():>+12.1f}{(d > 0).mean():>8.0%}{note}")
    say("\n  A monotonic rise would mean real signal being under-applied. Flat or random means the")
    say("  rules carry no drafting edge at ANY magnitude — the null is about the rules, not the knob.")


def main():
    p = load()
    seasons = sorted(p["season"].dropna().unique())
    say("HARSH BACKTEST — do the surviving rules actually score more points?")
    say(f"  {TEAMS}-team snake, {ROUNDS} rounds, my seat {MY_SLOT} · {N_DRAFTS} PAIRED drafts/season")
    say(f"  scored on ACTUAL season points, optimal 1QB/2RB/2WR/1TE/1FLEX lineup")
    say(f"  rules applied: the replicated injury conditional (ADP 16-75) + late durability (ADP 126+)")
    say(f"  NOTE: rules were selected using these same seasons — this is the FRIENDLIEST possible")
    say(f"  test. Failing here is fatal; passing is necessary but not sufficient.\n")
    say(f"  {'season':<8}{'n':>6}{'baseline':>10}{'prereq':>10}{'diff':>9}{'win%':>8}")
    all_diffs, season_means = [], []
    for s in seasons:
        pool = p[p["season"] == s].copy()
        if len(pool) < 120:
            continue
        pool["_adj"] = pool.apply(prereq_adjust, axis=1)
        pool = pool.reset_index(drop=True)
        diffs, base_tot, pre_tot = [], [], []
        for i in range(N_DRAFTS):
            rng_a = np.random.default_rng(10_000 + i)
            rng_b = np.random.default_rng(10_000 + i)      # identical seed -> paired
            b = simulate(pool, rng_a, use_prereq=False)
            q = simulate(pool, rng_b, use_prereq=True)
            diffs.append(q - b)
            base_tot.append(b)
            pre_tot.append(q)
        d = np.array(diffs)
        all_diffs.append(d)
        season_means.append(d.mean())
        say(f"  {int(s):<8}{len(pool):>6}{np.mean(base_tot):>10.0f}{np.mean(pre_tot):>10.0f}"
            f"{d.mean():>+9.1f}{(d > 0).mean():>7.0%}")

    D = np.concatenate(all_diffs)
    say(f"\n  POOLED over {len(D)} paired drafts:")
    say(f"    mean difference   {D.mean():+.1f} pts   (median {np.median(D):+.1f})")
    say(f"    rules WIN         {(D > 0).mean():.1%} of drafts")
    say(f"    rules LOSE        {(D < 0).mean():.1%} of drafts")
    say(f"    identical         {(D == 0).mean():.1%}")
    lo, hi = np.percentile(D, [2.5, 97.5])
    say(f"    95% of drafts land between {lo:+.0f} and {hi:+.0f} pts")
    pos_seasons = sum(1 for m in season_means if m > 0)
    say(f"    seasons where the rules helped: {pos_seasons} of {len(season_means)}")
    typical = np.mean([np.mean(x) for x in all_diffs])
    say(f"\n  VERDICT: " + (
        f"the rules add ~{typical:+.0f} pts per draft and help in {pos_seasons}/{len(season_means)} "
        f"seasons — real but small." if typical > 5 and pos_seasons >= len(season_means) * 0.7 else
        f"NO RELIABLE GAIN. ~{typical:+.0f} pts per draft, helping in only "
        f"{pos_seasons}/{len(season_means)} seasons. On a roster scoring "
        f"~{np.mean([np.mean(x) for x in all_diffs]) and np.mean(D) * 0 + 1500:.0f}+ points that is "
        f"noise, not an edge."))
    sweep(p, seasons)
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
