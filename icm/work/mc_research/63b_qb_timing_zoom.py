"""63 — QB TIMING FROM SLOT 2: risk-adjusted points gained/lost by taking a QB earlier vs later.

*** RETRACTED — see the header of results_63_qb_timing.txt and L57. Superseded by 64_. ***

The user's question, from a real draft: planning said "QB later", the advisor said Josh Allen early.
What does waiting actually COST, in points, from this seat?

DESIGN — paired drafts, only the QB rule differs:
  arm "natural"  = the REAL advisor decides QB timing on its own (current shipped behaviour)
  arm "R>=N"     = an ABSOLUTE strategy instruction, "no QB before round N" (rule 0 binding), which
                   is implemented the way the advisor would see it: QBs are removed from the
                   available pool before it picks, so the gate is structural, not persuasion.
Every arm runs the SAME seeds against the SAME sticky-ADP opponent field, so the paired difference
isolates the QB rule. Reuses 13_strategy_bakeoff.py's machinery by import — same opponent model,
same deadline guard — so this is comparable to the bake-off.

THREE LENSES on the final optimal starting lineup (1QB/2RB/2WR/1TE/1FLEX/1K, D/ST excluded):
  value    = sum of season projection (total_points, already LEAGUE-scored incl. bonuses)
  floor    = sum of MC p10 season floor
  risk-adj = sum of projection x availability  <- the "risk adjusted" the question asks for

SCOPE, STATED PLAINLY: this measures what THE BOARD believes, on the 2026 projections, with
opponent-draw variance as the only noise. It is NOT an outcome backtest — it cannot tell you whether
the projections are right, only what waiting costs GIVEN them. The historical-outcome instrument
(mc_research/49_) has an MDE of +/-53 pts and could not resolve an effect this size; this one is
tighter precisely because it holds the projections fixed.

Run:  .venv/bin/python icm/work/mc_research/63_qb_timing.py [N_SEEDS]
"""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("bk", os.path.join(HERE, "13_strategy_bakeoff.py"))
bk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bk)

OUT = os.path.join(HERE, "results_63b_qb_timing_zoom.txt")
SLOT, TEAMS, ROUNDS = 2, bk.TEAMS, bk.ROUNDS
# ("natural",0) = advisor decides. ("force",N) = MUST take a QB at round N if none yet (tests taking
# one EARLIER than natural). ("ban",N) = no QB before round N (tests waiting LONGER).
ARMS = [("natural", 0), ("force", 5), ("force", 6), ("force", 7), ("force", 8), ("force", 9)]

# availability is NaN for 228 of 540 players; 13_'s injury lens fillna(0)s the PRODUCT, which zeroes
# an unknown-availability player entirely. Fill with the position mean instead and say so.
BOARD = bk.board_full.copy()
_av = BOARD.groupby("position")["availability"].transform("mean")
BOARD["_avail"] = BOARD["availability"].fillna(_av).fillna(BOARD["availability"].mean())

lines = []


def say(s):
    print(s, flush=True)
    lines.append(s)


def draft_one(seed, arm):
    kind, n = arm
    """One full draft from SLOT with the QB gate applied. Returns (roster_df, qb_round, qb_name)."""
    rng = np.random.default_rng(seed)
    drafted, mine = set(), []
    qb_round, qb_name = None, None
    for overall in range(1, TEAMS * ROUNDS + 1):
        avail = BOARD[~BOARD.full_name.isin(drafted)]
        rd = (overall - 1) // TEAMS + 1
        if bk.snake_picker(overall) != SLOT:
            drafted.add(bk.opponent_pick(avail, rng, rd))
            continue
        roster = BOARD[BOARD.full_name.isin(mine)]
        # THE GATE: an absolute "no QB before round N" removes QBs from what the advisor can see.
        pool = avail
        have_qb = (roster.position == "QB").any() if len(roster) else False
        if kind == "ban" and rd < n:
            pool = avail[avail.position != "QB"]
        elif kind == "force" and rd == n and not have_qb:
            pool = avail[avail.position == "QB"]
        if pool.empty:
            pool = avail
        have = roster.position.value_counts().to_dict()
        need = {p: max(0, bk.MAND[p] - have.get(p, 0)) for p in bk.MAND}
        if (ROUNDS - len(mine)) <= sum(need.values()):          # deadline guard (same as 13_)
            forced = pool[pool.position.isin([p for p, n in need.items() if n > 0])]
            name = (forced.sort_values("vols", ascending=False).iloc[0].full_name
                    if not forced.empty else pool.iloc[0].full_name)
        else:
            name = bk.ours_pick(pool, roster.sort_values("total_points", ascending=False), overall, SLOT)
        if BOARD.loc[BOARD.full_name == name, "position"].iloc[0] == "QB" and qb_round is None:
            qb_round, qb_name = rd, name
        mine.append(name)
        drafted.add(name)
    return BOARD[BOARD.full_name.isin(mine)], qb_round, qb_name


def score(roster):
    v, _ = bk._lineup(roster, lambda r: r.total_points.fillna(0))
    f, _ = bk._lineup(roster, lambda r: r.floor.fillna(0))
    a, _ = bk._lineup(roster, lambda r: (r.total_points * r._avail).fillna(0))
    return v, f, a


def _star(arg):
    arm, seed = arg[0], arg[1]
    ros, qr, qn = draft_one(seed, arm)
    v, f, a = score(ros)
    return {"arm": f"{arm[0]}{arm[1] or ''}", "seed": seed, "value": v, "floor": f, "riskadj": a,
            "qb_round": qr, "qb": qn}


if __name__ == "__main__":
    import multiprocessing as mp
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    jobs = [(a, s) for a in ARMS for s in range(1, N + 1)]
    LAB = {f"{k}{v or ''}": ("natural (advisor decides)" if k=="natural" else (f"MUST take QB by R{v}" if k=="force" else f"no QB before R{v}")) for k,v in ARMS}
    say(f"QB TIMING FROM SLOT {SLOT} — {len(ARMS)} arms x {N} paired seeds = {len(jobs)} drafts")
    import advisor
    sched = advisor.my_pick_schedule(SLOT, TEAMS, ROUNDS)
    say("  " + " · ".join(f"R{r} #{p}" for r, p in sched[:9]))
    say("\nSCOPE: this is what the BOARD believes on the 2026 projections. Opponent-draw variance is")
    say("the only noise. It is NOT an outcome backtest — it cannot say the projections are right.\n")
    with mp.Pool(min(len(ARMS), mp.cpu_count())) as pool:
        rows = pool.map(_star, jobs)
    d = pd.DataFrame(rows)

    base = d[d.arm == "natural"].set_index("seed")
    say(f"{'arm':<16}{'value':>9}{'floor':>9}{'risk-adj':>10}   {'vs natural (risk-adj)':>24}")
    say("-" * 74)
    for k,v in ARMS:
        a = f"{k}{v or ''}"
        g = d[d.arm == a].set_index("seed")
        lab = LAB[a]
        if k == "natural":
            say(f"{lab:<16}{g.value.mean():>9.0f}{g.floor.mean():>9.0f}{g.riskadj.mean():>10.0f}"
                f"{'— (baseline)':>26}")
            continue
        diff = (g.riskadj - base.riskadj).dropna()
        se = diff.std() / np.sqrt(len(diff))
        say(f"{lab:<16}{g.value.mean():>9.0f}{g.floor.mean():>9.0f}{g.riskadj.mean():>10.0f}"
            f"{diff.mean():>+15.1f} ± {1.96*se:.1f}  ({(diff<0).mean():.0%} worse)")

    say("\nWHEN the QB actually gets taken, and who:")
    say(f"{'arm':<16}{'median QB rd':>13}{'most common QB':>22}{'% of drafts':>13}")
    for k,v in ARMS:
        a = f"{k}{v or ''}"
        g = d[d.arm == a]
        lab = LAB[a]
        top = g.qb.value_counts()
        say(f"{lab:<16}{g.qb_round.median():>13.0f}{(top.index[0] if len(top) else '—'):>22}"
            f"{(top.iloc[0]/len(g) if len(top) else 0):>12.0%}")

    say("\nPAIRED cost of waiting, risk-adjusted (negative = waiting COSTS you):")
    for k,v in ARMS[1:]:
        a = f"{k}{v or ''}"
        g = d[d.arm == a].set_index("seed")
        diff = (g.riskadj - base.riskadj).dropna()
        say(f"  {LAB[a]:<26} {diff.mean():+7.1f} pts   median {diff.median():+7.1f}   "
            f"worst {diff.min():+7.1f}   best {diff.max():+7.1f}")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    say(f"\nwrote {OUT}")
