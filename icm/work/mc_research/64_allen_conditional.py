"""64 — GIVEN an elite QB is actually available at my pick, is taking him worth it?

CORRECTS 63_. That experiment compared "force a QB at round N" arms against a "natural" baseline and
I read its median QB round of 8 as the advisor PREFERRING to wait. It does not. Measured (100 seeds,
slot 2): Josh Allen survives to the R2 pick #23 in only 34% of drafts, and when he does the advisor
takes him 100/100 of the time. The QB-round distribution is BIMODAL — {R2: 34, R8: 23, R9: 6,
R10: 15, R11: 22} — so its median is a mixture artifact, not a policy. 63_'s "force QB by R2" arm
also drafted Lamar Jackson 68% of the time rather than Allen, so it never tested the real question.

THE REAL QUESTION, asked conditionally: among ONLY the drafts where the elite QB is genuinely on the
board at my pick, does taking him beat passing on him?

  arm TAKE  = take the elite QB at that pick (what the advisor actually does)
  arm PASS  = he is removed from view for that ONE pick, so the advisor takes its best non-QB;
              QB timing is unconstrained afterwards (it fills QB whenever it next wants to)

Same seed, same opponent field, paired. Only the one decision differs. Lenses: value, MC p10 floor,
and projection x availability (risk-adjusted).

SCOPE: projections held fixed, so this is what THE BOARD believes about its own picks — the correct
frame for "how should this tool spend a pick", not evidence the projections are right.

Run:  .venv/bin/python icm/work/mc_research/64_allen_conditional.py [N_SEEDS] [SLOT]
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

OUT = os.path.join(HERE, "results_64_allen_conditional.txt")
TEAMS, ROUNDS = bk.TEAMS, bk.ROUNDS
ELITE = "Josh Allen"

BOARD = bk.board_full.copy()
_av = BOARD.groupby("position")["availability"].transform("mean")
BOARD["_avail"] = BOARD["availability"].fillna(_av).fillna(BOARD["availability"].mean())

lines = []


def say(s):
    print(s, flush=True)
    lines.append(s)


def run(seed, slot, pass_at):
    """pass_at = the overall pick at which the elite QB is hidden (PASS arm), or None (TAKE arm).
    Returns (roster, elite_available_at_my_R2, qb_round, took_elite)."""
    rng = np.random.default_rng(seed)
    drafted, mine = set(), []
    my_r2 = [p for p in range(1, TEAMS * ROUNDS + 1) if bk.snake_picker(p) == slot][1]
    elite_avail, qb_round, took = False, None, False
    for overall in range(1, TEAMS * ROUNDS + 1):
        avail = BOARD[~BOARD.full_name.isin(drafted)]
        rd = (overall - 1) // TEAMS + 1
        if bk.snake_picker(overall) != slot:
            drafted.add(bk.opponent_pick(avail, rng, rd))
            continue
        if overall == my_r2:
            elite_avail = ELITE in set(avail.full_name)
        roster = BOARD[BOARD.full_name.isin(mine)]
        pool = avail
        if pass_at is not None and overall == pass_at:
            pool = avail[avail.full_name != ELITE]        # hide him for this ONE pick only
        have = roster.position.value_counts().to_dict()
        need = {p: max(0, bk.MAND[p] - have.get(p, 0)) for p in bk.MAND}
        if (ROUNDS - len(mine)) <= sum(need.values()):
            f = pool[pool.position.isin([p for p, n in need.items() if n > 0])]
            name = (f.sort_values("vols", ascending=False).iloc[0].full_name
                    if not f.empty else pool.iloc[0].full_name)
        else:
            name = bk.ours_pick(pool, roster.sort_values("total_points", ascending=False), overall, slot)
        if name == ELITE:
            took = True
        if BOARD.loc[BOARD.full_name == name, "position"].iloc[0] == "QB" and qb_round is None:
            qb_round = rd
        mine.append(name)
        drafted.add(name)
    return BOARD[BOARD.full_name.isin(mine)], elite_avail, qb_round, took


def score(r):
    v, _ = bk._lineup(r, lambda x: x.total_points.fillna(0))
    f, _ = bk._lineup(r, lambda x: x.floor.fillna(0))
    a, _ = bk._lineup(r, lambda x: (x.total_points * x._avail).fillna(0))
    return v, f, a


def _star(arg):
    seed, slot = arg
    my_r2 = [p for p in range(1, TEAMS * ROUNDS + 1) if bk.snake_picker(p) == slot][1]
    rt, av_t, qr_t, took = run(seed, slot, None)
    if not av_t:
        return None                       # elite not available this seed — not part of the question
    rp, _, qr_p, _ = run(seed, slot, my_r2)
    vt, ft, at = score(rt)
    vp, fp, ap = score(rp)
    return {"seed": seed, "took_elite": took,
            "take_v": vt, "take_f": ft, "take_a": at, "take_qbrd": qr_t,
            "pass_v": vp, "pass_f": fp, "pass_a": ap, "pass_qbrd": qr_p}


if __name__ == "__main__":
    import multiprocessing as mp
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    SLOT = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    my_r2 = [p for p in range(1, TEAMS * ROUNDS + 1) if bk.snake_picker(p) == SLOT][1]
    say(f"CONDITIONAL TEST — slot {SLOT}, decision pick #{my_r2} (R2). {ELITE} ADP "
        f"{BOARD.loc[BOARD.full_name==ELITE,'adp_rank'].iloc[0]:.1f}")
    say(f"{N} seeds; only the seeds where he is genuinely available count.\n")
    with mp.Pool(mp.cpu_count()) as pool:
        rows = [r for r in pool.map(_star, [(s, SLOT) for s in range(1, N + 1)]) if r]
    d = pd.DataFrame(rows)
    say(f"He was available at #{my_r2} in {len(d)}/{N} seeds ({len(d)/N:.0%}); "
        f"the advisor took him in {d.took_elite.mean():.0%} of those.\n")
    say(f"{'lens':<12}{'TAKE him':>11}{'PASS':>11}{'paired diff':>14}{'95% CI':>16}{'take wins':>11}")
    say("-" * 76)
    for lab, t, p in (("value", "take_v", "pass_v"), ("floor", "take_f", "pass_f"),
                      ("risk-adj", "take_a", "pass_a")):
        diff = d[t] - d[p]
        se = diff.std() / np.sqrt(len(diff))
        say(f"{lab:<12}{d[t].mean():>11.0f}{d[p].mean():>11.0f}{diff.mean():>+14.1f}"
            f"{f'[{diff.mean()-1.96*se:+.1f}, {diff.mean()+1.96*se:+.1f}]':>16}{(diff>0).mean():>10.0%}")
    say(f"\nWhen you PASS, the QB you end up with comes at round "
        f"{d.pass_qbrd.median():.0f} (median); taking him is round {d.take_qbrd.median():.0f}.")
    say(f"paired risk-adj: median {(d.take_a-d.pass_a).median():+.1f} · "
        f"worst {(d.take_a-d.pass_a).min():+.1f} · best {(d.take_a-d.pass_a).max():+.1f}")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    say(f"\nwrote {OUT}")
