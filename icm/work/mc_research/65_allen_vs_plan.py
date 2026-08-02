"""65 — Josh Allen at R2 vs EXECUTING the R6-R7 plan. (The user's question, sharpened.)

64_ answered "take him vs pass and let QB fill naturally" and the pass arm's QB arrived at a MEDIAN
of round 8. That is not the plan the user actually had — his plan was a QB in round 6-7. If a QB at
R6-R7 is better than one that slides to R8, then 64_'s +17.9 overstates the case for taking Allen.
This tests the plan as stated.

Conditioned, as 64_ established it must be, on the decision being REAL: only seeds where Josh Allen
is genuinely on the board at my R2 pick count (~32% at slot 2).

  arm TAKE     = advisor natural — it takes him at R2 (measured 99-100% of the time when available)
  arm PLAN-R6  = no QB before R6, then MUST take the best QB at R6 (the plan, executed faithfully)
  arm PLAN-R7  = same at R7

The ban runs the whole draft up to round N, so "pass on Allen" means passing for good — not passing
at R2 and scooping him at R3, which was an unstated confound in 64_'s pass arm.

Same seed, same opponent field, paired. Lenses: value / MC p10 floor / projection x availability.
SCOPE: projections held fixed — what THE BOARD believes about its own picks.

Run:  .venv/bin/python icm/work/mc_research/65_allen_vs_plan.py [N_SEEDS] [SLOT]
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

OUT = os.path.join(HERE, "results_65_allen_vs_plan.txt")
TEAMS, ROUNDS = bk.TEAMS, bk.ROUNDS
ELITE = "Josh Allen"
BOARD = bk.board_full.copy()
_a = BOARD.groupby("position")["availability"].transform("mean")
BOARD["_avail"] = BOARD["availability"].fillna(_a).fillna(BOARD["availability"].mean())

lines = []


def say(s):
    print(s, flush=True)
    lines.append(s)


def run(seed, slot, ban_until):
    """ban_until=None -> natural. Else: no QB before that round, then FORCE a QB at it."""
    rng = np.random.default_rng(seed)
    drafted, mine = set(), []
    my_r2 = [p for p in range(1, TEAMS * ROUNDS + 1) if bk.snake_picker(p) == slot][1]
    elite_avail, qb_rd, qb_name, r2_pick = False, None, None, None
    rnd_pick = {}
    for overall in range(1, TEAMS * ROUNDS + 1):
        avail = BOARD[~BOARD.full_name.isin(drafted)]
        rd = (overall - 1) // TEAMS + 1
        if bk.snake_picker(overall) != slot:
            drafted.add(bk.opponent_pick(avail, rng, rd))
            continue
        if overall == my_r2:
            elite_avail = ELITE in set(avail.full_name)
        roster = BOARD[BOARD.full_name.isin(mine)]
        have_qb = (roster.position == "QB").any() if len(roster) else False
        pool = avail
        if ban_until is not None:
            if rd < ban_until:
                pool = avail[avail.position != "QB"]          # pass for good, not just this pick
            elif rd == ban_until and not have_qb:
                pool = avail[avail.position == "QB"]          # execute the plan
        if pool.empty:
            pool = avail
        have = roster.position.value_counts().to_dict()
        need = {p: max(0, bk.MAND[p] - have.get(p, 0)) for p in bk.MAND}
        if (ROUNDS - len(mine)) <= sum(need.values()):
            f = pool[pool.position.isin([p for p, n in need.items() if n > 0])]
            name = (f.sort_values("vols", ascending=False).iloc[0].full_name
                    if not f.empty else pool.iloc[0].full_name)
        else:
            name = bk.ours_pick(pool, roster.sort_values("total_points", ascending=False), overall, slot)
        if BOARD.loc[BOARD.full_name == name, "position"].iloc[0] == "QB" and qb_rd is None:
            qb_rd, qb_name = rd, name
        if overall == my_r2:
            r2_pick = name
        if rd in (6, 7):
            rnd_pick.setdefault(rd, name)
        mine.append(name)
        drafted.add(name)
    return BOARD[BOARD.full_name.isin(mine)], elite_avail, qb_rd, qb_name, r2_pick, rnd_pick


def score(r):
    v, _ = bk._lineup(r, lambda x: x.total_points.fillna(0))
    f, _ = bk._lineup(r, lambda x: x.floor.fillna(0))
    a, _ = bk._lineup(r, lambda x: (x.total_points * x._avail).fillna(0))
    return v, f, a


def _star(arg):
    seed, slot = arg
    rt, av, qrt, qnt, r2t, rpk_t = run(seed, slot, None)
    if not av:
        return None
    out = {"seed": seed, "take_qb": qnt, "take_qbrd": qrt, "take_r2": r2t,
           "take_r6": rpk_t.get(6), "take_r7": rpk_t.get(7)}
    vt, ft, at = score(rt)
    out.update(take_v=vt, take_f=ft, take_a=at)
    for n in (6, 7):
        rp, _, qr, qn, r2p, rpk_p = run(seed, slot, n)
        v, f, a = score(rp)
        out.update({f"p{n}_v": v, f"p{n}_f": f, f"p{n}_a": a, f"p{n}_qb": qn, f"p{n}_qbrd": qr, f"p{n}_r2": r2p})
    return out


if __name__ == "__main__":
    import multiprocessing as mp
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    SLOT = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    my_r2 = [p for p in range(1, TEAMS * ROUNDS + 1) if bk.snake_picker(p) == SLOT][1]
    say(f"ALLEN AT R2 vs EXECUTING THE R6-R7 PLAN — slot {SLOT}, decision at pick #{my_r2}")
    say(f"{ELITE} ADP {BOARD.loc[BOARD.full_name==ELITE,'adp_rank'].iloc[0]:.1f}. "
        f"{N} seeds; only those where he is genuinely available count.\n")
    with mp.Pool(mp.cpu_count()) as pool:
        rows = [r for r in pool.map(_star, [(s, SLOT) for s in range(1, N + 1)]) if r]
    d = pd.DataFrame(rows)
    say(f"He was available at #{my_r2} in {len(d)}/{N} seeds ({len(d)/N:.0%}).")
    say(f"TAKE arm gets: {d.take_qb.value_counts().index[0]} at R{d.take_qbrd.median():.0f} "
        f"({d.take_qb.value_counts().iloc[0]/len(d):.0%} of seeds)")
    for n in (6, 7):
        vc = d[f"p{n}_qb"].value_counts()
        say(f"PLAN-R{n} gets: {vc.index[0]} ({vc.iloc[0]/len(d):.0%}), "
            f"then {vc.index[1] if len(vc)>1 else '—'} ({vc.iloc[1]/len(d):.0%})" if len(vc) > 1 else "")
    say("\nTHE ACTUAL SWAP — who you take at pick #%d instead of Allen:" % my_r2)
    for n in (6, 7):
        vc = d[f"p{n}_r2"].value_counts()
        say(f"  PLAN-R{n}: " + " · ".join(f"{k} {v/len(d):.0%}" for k, v in vc.head(5).items()))
    BUST = BOARD.set_index("full_name")["p_bust"]
    FLR  = BOARD.set_index("full_name")["floor"]
    say("\nWHAT EACH ARM SPENDS ITS R6 PICK ON (the piece I had not checked):")
    for lab, col in (("TAKE (already has Allen)", "take_r6"), ):
        vc = d[col].value_counts()
        say(f"  {lab}: " + " · ".join(f"{k} {v/len(d):.0%}" for k, v in vc.head(4).items()))
        mb = d[col].map(BUST).mean(); mf = d[col].map(FLR).mean()
        say(f"     mean bust of that pick: {mb:.0%} · mean floor {mf:.0f}")
    for n in (6,):
        vc = d[f"p{n}_qb"].value_counts()
        mb = d[f"p{n}_qb"].map(BUST).mean(); mf = d[f"p{n}_qb"].map(FLR).mean()
        say(f"  PLAN-R6 (takes the QB): " + " · ".join(f"{k} {v/len(d):.0%}" for k, v in vc.head(4).items()))
        say(f"     mean bust of that pick: {mb:.0%} · mean floor {mf:.0f}")
    say("\n  So the trade is:  Josh Allen  +  [R%d QB]" % 6)
    for n in (6, 7):
        top_r2 = d[f"p{n}_r2"].value_counts().index[0]
        top_qb = d[f"p{n}_qb"].value_counts().index[0]
        say(f"     vs (PLAN-R{n}):  {top_r2}  +  {top_qb}")
    say("")
    say(f"{'comparison':<26}{'lens':<11}{'TAKE':>8}{'PLAN':>8}{'diff':>9}{'95% CI':>18}{'take wins':>11}")
    say("-" * 82)
    for n in (6, 7):
        for lab, t, p in (("value", "take_v", f"p{n}_v"), ("floor", "take_f", f"p{n}_f"),
                          ("risk-adj", "take_a", f"p{n}_a")):
            diff = d[t] - d[p]
            se = diff.std() / np.sqrt(len(diff))
            head = f"Allen@R2 vs QB@R{n}" if lab == "value" else ""
            say(f"{head:<26}{lab:<11}{d[t].mean():>8.0f}{d[p].mean():>8.0f}{diff.mean():>+9.1f}"
                f"{f'[{diff.mean()-1.96*se:+.1f}, {diff.mean()+1.96*se:+.1f}]':>18}"
                f"{(diff>0).mean():>10.0%}")
        say("")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    say(f"wrote {OUT}")
