# STRATEGY BAKE-OFF — pit OUR strategy (the real advisor engine) against classic drafting
# philosophies, from slot 7, against the same ADP-bot field, and score the resulting rosters on
# three honest lenses. Research artifact — reads value_board.csv + advisor.py; changes NOTHING.
#
# Contestants (our seat runs each; the other 11 seats always draft ADP-with-noise):
#   Ours          - the REAL advisor: add_vona -> build_context -> TOP PICKS #1 (no API; the
#                   deterministic backbone of our strategy, minus the LLM's near-tie best-player pick)
#   ADP-follow    - best available by ESPN ADP (drafting straight off the market)
#   VOLS-max/BPA  - best available by our own value, IGNORING VONA timing (isolates VONA's worth)
#   ECR-follow    - best available by expert consensus
#   Zero-RB       - no RB rounds 1-4, then best value
#   Robust-RB     - RB with the first two picks, then best value
#   Double-late-QB- no QB before R9, then grab TWO QBs late (the streaming/platoon build)
#
# Lenses (optimal starting lineup 1QB/2RB/2WR/1TE/1FLEX/1K; D/ST off-board, excluded for everyone):
#   value   = sum of season projection (total_points)
#   floor   = sum of MC p10 season floor
#   injury  = sum of projection x availability (expected value after injuries)
# Plus a Double-QB-only "QB insurance bonus": the extra expected starting-QB points a 2nd QB buys
# (combined availability), which the uniform base scorer intentionally does NOT credit — reported
# separately so the head-to-head is honest about what streaming actually gains.
import json
import os
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import advisor

TEAMS, ROUNDS = 12, 16
MAND = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1}        # mandatory starters (FLEX filled from extras)
SLOTS = [("QB", ["QB"], 1), ("RB", ["RB"], 2), ("WR", ["WR"], 2),   # optimal-lineup fill order
         ("TE", ["TE"], 1), ("FLEX", ["RB", "WR", "TE"], 1), ("K", ["K"], 1)]
SLOT_ORDER = ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "FLEX", "K"]

board_full = pd.read_csv("value_board.csv")
board_full["position"] = board_full["pos_label"].str.extract(r"([A-Z]+)")
_cohort = (pd.read_csv("cohort_data.csv").drop_duplicates("full_name").set_index("full_name")["cohort_trimmed"]
           if os.path.exists("cohort_data.csv") else pd.Series(dtype=float))

# Realistic opponent model (fixes the elite-free-fall bug): each bot takes the available player with
# the smallest ADP + gaussian noise, the noise SCALING with ADP so elite picks are sticky (Gibbs goes
# 1-2) while later picks stay variable. Calibrated: ADP-1 ~93% gone by pick 3, all elites gone by R1.
OPP_SIGMA_BASE, OPP_SIGMA_FRAC = 1.5, 0.10


def metrics_for(name):
    row = board_full[board_full.full_name == name]
    if row.empty:
        return {}
    r = row.iloc[0]
    g = lambda k: (None if pd.isna(r.get(k)) else round(float(r[k]), 3))
    return {"pos_label": r.pos_label, "team": (None if pd.isna(r.team) else r.team),
            "overall_rank": g("overall_rank"), "rank_composite": g("rank_composite"),
            "adp_rank": g("adp_rank"), "ecr_rank": g("ecr_rank"), "vols": g("vols"),
            "value_gap": g("value_gap"), "market": (None if pd.isna(r.market) else r.market),
            "floor": g("floor"), "ceiling": g("ceiling"), "p_startable": g("p_startable"),
            "p_bust": g("p_bust"), "availability": g("availability"),
            "risk_tier": (None if pd.isna(r.risk_tier) else r.risk_tier), "age": g("age"),
            "cohort_trimmed": (None if name not in _cohort.index else round(float(_cohort[name]), 3))}


def snake_picker(overall, teams=TEAMS):
    r, i = (overall - 1) // teams + 1, (overall - 1) % teams + 1
    return i if r % 2 else teams - i + 1


def counts_of(roster):
    return roster["position"].value_counts().to_dict()


def opponent_pick(avail, rng, rd):
    pool = avail.dropna(subset=["adp_rank"])
    if rd <= 10:
        pool = pool[pool.position != "K"]
    if pool.empty:
        pool = avail.head(5)
    a = pool["adp_rank"].to_numpy(dtype=float)
    score = a + rng.normal(0, 1, len(a)) * (OPP_SIGMA_BASE + OPP_SIGMA_FRAC * a)   # ADP-sticky elites
    return pool.iloc[int(np.argmin(score))].full_name


def legal_pool(avail, roster, rd, qb_max=1, te_max=2):
    """Draftable players given roster legality: caps QB/TE/K, and a deadline guard that force-fills
    mandatory starters when picks run short (so no strategy ends with a structural hole)."""
    have = counts_of(roster)
    picks_left = ROUNDS - len(roster)
    need = {p: max(0, MAND[p] - have.get(p, 0)) for p in MAND}
    if picks_left <= sum(need.values()):                   # deadline: must fill remaining starters
        forced = avail[avail.position.isin([p for p, n in need.items() if n > 0])]
        if not forced.empty:
            return forced
    pool = avail.copy()
    if have.get("QB", 0) >= qb_max:
        pool = pool[pool.position != "QB"]
    if have.get("TE", 0) >= te_max:
        pool = pool[pool.position != "TE"]
    if have.get("K", 0) >= 1 or rd < 14:                   # K only in the last rounds, exactly one
        pool = pool[pool.position != "K"]
    return pool if not pool.empty else avail


def _best(pool, by, asc):
    p = pool.dropna(subset=[by])
    p = p if not p.empty else pool
    return p.sort_values(by, ascending=asc).iloc[0].full_name


def pick_adp(avail, roster, rd, rng):     return _best(legal_pool(avail, roster, rd), "adp_rank", True)
def pick_vols(avail, roster, rd, rng):    return _best(legal_pool(avail, roster, rd), "vols", False)
def pick_ecr(avail, roster, rd, rng):     return _best(legal_pool(avail, roster, rd), "ecr_rank", True)


def pick_zero_rb(avail, roster, rd, rng):
    pool = legal_pool(avail, roster, rd)
    if rd <= 4:
        pool = pool[pool.position != "RB"] if not pool[pool.position != "RB"].empty else pool
    return _best(pool, "vols", False)


def pick_robust_rb(avail, roster, rd, rng):
    pool = legal_pool(avail, roster, rd)
    if rd <= 2:
        pool = pool[pool.position == "RB"] if not pool[pool.position == "RB"].empty else pool
    return _best(pool, "vols", False)


def pick_double_qb(avail, roster, rd, rng):
    have = counts_of(roster)
    pool = legal_pool(avail, roster, rd, qb_max=2)
    if rd < 9:                                             # never a QB before round 9
        pool = pool[pool.position != "QB"] if not pool[pool.position != "QB"].empty else pool
    elif rd <= 14 and have.get("QB", 0) < 2:               # late window: grab QBs until we hold two
        pool = pool[pool.position == "QB"] if not pool[pool.position == "QB"].empty else pool
    return _best(pool, "vols", False)


def ours_pick(avail, mine_df, overall, slot):
    sc = {p: int(((avail.position == p) & (avail.vols >= 0)).sum()) for p in ["QB", "RB", "WR", "TE", "K"]}
    upcoming = [p for p in range(overall + 1, TEAMS * ROUNDS + 1) if snake_picker(p) == slot]
    dp = {"slot": slot, "teams": TEAMS, "overall_now": overall, "my_turn": True,
          "next_pick": overall, "picks_away": 0, "following": upcoming[0] if upcoming else None}
    av = advisor.add_vona(avail.copy(), dp["following"] or overall + 10)
    ctx = advisor.build_context(av, mine_df, sc, dp)
    m = re.search(r"TOP PICKS NOW.*?(?:\n)", ctx, re.S)
    shortlist = re.findall(r"\d\. \*?([A-Z][^(]+?) \(", m.group(0)) if m else []
    return shortlist[0].strip() if shortlist else avail.iloc[0].full_name


def run_draft(picker, seed, is_ours, slot):
    rng = np.random.default_rng(seed)
    drafted, mine = set(), []
    for overall in range(1, TEAMS * ROUNDS + 1):
        avail = board_full[~board_full.full_name.isin(drafted)]
        if snake_picker(overall) != slot:
            drafted.add(opponent_pick(avail, rng, (overall - 1) // TEAMS + 1))
            continue
        roster = board_full[board_full.full_name.isin(mine)]
        rd = (overall - 1) // TEAMS + 1
        if is_ours:
            # STREAMER ALERT analog (L26): TOP PICKS excludes K/D-ST, so when picks barely cover the
            # remaining mandatory starters, force the fill (in practice only ever the K) — same
            # deadline guard the rule bots get, so nobody is penalized for the TOP-PICKS K exclusion.
            have = counts_of(roster)
            need = {p: max(0, MAND[p] - have.get(p, 0)) for p in MAND}
            if (ROUNDS - len(mine)) <= sum(need.values()):
                forced = avail[avail.position.isin([p for p, n in need.items() if n > 0])]
                name = (forced.sort_values("vols", ascending=False).iloc[0].full_name if not forced.empty
                        else ours_pick(avail, roster.sort_values("total_points", ascending=False), overall, slot))
            else:
                name = ours_pick(avail, roster.sort_values("total_points", ascending=False), overall, slot)
        else:
            name = picker(avail, roster, rd, rng)
        mine.append(name)
        drafted.add(name)
    return board_full[board_full.full_name.isin(mine)], mine   # roster + draft-order names


def _lineup(roster, val, want_picks=False):
    """Greedy optimal starting lineup by the per-player value `val`. Fills QB, RB, RB, WR, WR, TE,
    then FLEX (best remaining RB/WR/TE), then K — each the highest-value unused player at that slot.
    Returns (summed starter value, #unfilled slots) [+ the per-slot picks when want_picks]."""
    r = roster.assign(_v=val(roster))
    used, total, unfilled, picks = set(), 0.0, 0, []
    for label, positions, n in SLOTS:
        c = r[r.position.isin(positions) & ~r.full_name.isin(used)].sort_values("_v", ascending=False)
        for i in range(n):
            slot = f"{label}{i + 1}" if n > 1 else label
            if i < len(c):
                row = c.iloc[i]; used.add(row.full_name); total += row._v
                picks.append((slot, row.full_name, row._v))
            else:
                unfilled += 1; picks.append((slot, None, 0.0))
    return (total, unfilled, picks) if want_picks else (total, unfilled)


def score(roster):
    v, unf = _lineup(roster, lambda r: r.total_points.fillna(0))
    f, _ = _lineup(roster, lambda r: r.floor.fillna(0))
    inj, _ = _lineup(roster, lambda r: (r.total_points * r.availability).fillna(0))
    qbs = roster[roster.position == "QB"].sort_values("total_points", ascending=False)
    qb_ins = 0.0
    if len(qbs) >= 2:
        a1, a2 = qbs.iloc[0].availability, qbs.iloc[1].availability
        qb_ins = qbs.iloc[0].total_points * ((1 - (1 - a1) * (1 - a2)) - a1)   # extra starting-QB pts from insurance
    return dict(value=v, floor=f, injury=inj, unfilled=unf, nQB=int((roster.position == "QB").sum()), qb_ins=qb_ins)


STRATS = {"Ours": None, "ADP-follow": pick_adp, "VOLS-max": pick_vols, "ECR-follow": pick_ecr,
          "Zero-RB": pick_zero_rb, "Robust-RB": pick_robust_rb, "Double-late-QB": pick_double_qb}
posser = board_full.set_index("full_name")["position"]


def run_slot(slot, N):
    """Every strategy x N seeds from ONE draft slot. Returns per-strategy raw score rows, the
    value-lens per-lineup-slot breakdown, and structural profile. Self-contained so it parallelizes."""
    out = {}
    picks_by_round = {r: Counter() for r in range(1, ROUNDS + 1)}   # Ours only: what we drafted each round
    for name, fn in STRATS.items():
        srows, slot_acc, struct_acc = [], [], []
        for sd in range(1, N + 1):
            roster, order = run_draft(fn, sd, fn is None, slot)
            if fn is None:                                          # Ours: log the per-round pick
                for r, nm in enumerate(order, 1):
                    picks_by_round[r][nm] += 1
            srows.append(score(roster))
            _, _, picks = _lineup(roster, lambda r: r.total_points.fillna(0), want_picks=True)
            slot_acc.append({s: v for s, nm, v in picks})
            starters = board_full[board_full.full_name.isin([nm for s, nm, v in picks if nm])]
            first_qb = next((i + 1 for i, nm in enumerate(order) if posser.get(nm) == "QB"), 99)
            c = roster.position.value_counts().to_dict()
            struct_acc.append(dict(firstQB=first_qb, nRB=c.get("RB", 0), nWR=c.get("WR", 0), nTE=c.get("TE", 0),
                                   startAvail=starters.availability.mean(), startBust=starters.p_bust.mean()))
        out[name] = dict(raw=pd.DataFrame(srows), slots=pd.DataFrame(slot_acc).mean(),
                         struct=pd.DataFrame(struct_acc).mean())
    out["_picks_by_round"] = {r: c.most_common(4) for r, c in picks_by_round.items()}
    return slot, out


def _run_slot_star(arg):
    return run_slot(*arg)


if __name__ == "__main__":
    import multiprocessing as mp
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    slots = list(range(1, TEAMS + 1))
    nproc = min(len(slots), mp.cpu_count())
    print(f"Bake-off across ALL {len(slots)} draft slots x {N} seeds/strategy = "
          f"{len(slots) * N} drafts/strategy ({len(slots) * N * len(STRATS)} total), {nproc} procs.\n", flush=True)
    by_slot = {}
    with mp.Pool(nproc) as pool:
        for slot, out in pool.imap_unordered(_run_slot_star, [(s, N) for s in slots]):
            by_slot[slot] = out
            print(f"  slot {slot} done ({len(by_slot)}/{len(slots)})", flush=True)

    names = list(STRATS)
    def mean_at(slot, nm, L): return by_slot[slot][nm]["raw"][L].mean()

    # ---- POOLED over all slots (headline: len(slots)*N drafts/strategy) ----
    pooled = {nm: pd.concat([by_slot[s][nm]["raw"] for s in slots], ignore_index=True) for nm in names}
    ptab = pd.DataFrame({nm: pooled[nm].mean(numeric_only=True) for nm in names}).T
    pstd = pd.DataFrame({nm: pooled[nm].std(numeric_only=True) for nm in names}).T
    order = sorted(names, key=lambda k: -ptab.loc[k, "value"])
    n_pool = len(slots) * N

    print(f"\n=== POOLED over all slots ({n_pool} drafts/strategy) ===")
    print(f"{'strategy':16} {'value':>7} {'SE':>5} {'floor':>7} {'injury':>7} {'#QB':>5} {'unfilled':>9}")
    print("-" * 62)
    for nm in order:
        r, se = ptab.loc[nm], pstd.loc[nm, "value"] / n_pool ** 0.5
        print(f"{nm:16} {r.value:7.0f} {se:5.1f} {r.floor:7.0f} {r.injury:7.0f} {r.nQB:5.1f} {r.unfilled:9.2f}")
    print("(SE = standard error of the value mean; gaps > ~2-3x SE are real)")
    print("\nRanking by lens:")
    for L in ["value", "floor", "injury"]:
        print(f"  {L:7}: " + " > ".join(ptab.sort_values(L, ascending=False).index))

    # ---- PER-SLOT: does Ours win at every draft position? ----
    print("\n=== PER-SLOT: Ours vs the field at each draft position (rank out of 7) ===")
    print(f"{'slot':>4} {'OursVal':>8} {'bestOther':>10} {'name':>15} {'margin':>7} {'rkVal':>6} {'rkFlr':>6} {'rkInj':>6}")
    for s in slots:
        vals = {nm: mean_at(s, nm, "value") for nm in names}
        best = max((v, nm) for nm, v in vals.items() if nm != "Ours")
        def rank(L):
            d = {nm: mean_at(s, nm, L) for nm in names}
            return 1 + sum(1 for v in d.values() if v > d["Ours"])
        print(f"{s:>4} {vals['Ours']:8.0f} {best[0]:10.0f} {best[1]:>15} {vals['Ours'] - best[0]:+7.0f} "
              f"{rank('value'):>6} {rank('floor'):>6} {rank('injury'):>6}")
    wins = sum(1 for s in slots if all(
        mean_at(s, "Ours", L) >= max(mean_at(s, nm, L) for nm in names) for L in ["value", "floor", "injury"]))
    print(f"\nOurs is #1 on ALL THREE lenses at {wins}/{len(slots)} draft slots.")

    # ---- Double-QB focus (pooled) ----
    print("\n=== FOCUS: Double-late-QB vs Ours (pooled) ===")
    o, dq = ptab.loc["Ours"], ptab.loc["Double-late-QB"]
    for L in ["value", "floor", "injury"]:
        d = dq[L] - o[L]
        print(f"  {L:7}: Ours {o[L]:.0f} vs Double-QB {dq[L]:.0f} ({d:+.0f}, {d / o[L] * 100:+.1f}%)")
    print(f"  QB-insurance bonus (not in base injury): +{dq.qb_ins:.0f}; injury WITH it: "
          f"Double-QB {dq.injury + dq.qb_ins:.0f} vs Ours {o.injury:.0f} ({dq.injury + dq.qb_ins - o.injury:+.0f}).")

    # ---- WHY (pooled): per-lineup-slot value breakdown ----
    print("\n=== WHY (pooled): starting-lineup points per slot, value lens ===")
    slot_df = pd.DataFrame({nm: pd.concat([by_slot[s][nm]["slots"] for s in slots], axis=1).mean(axis=1)
                            for nm in names}).T[SLOT_ORDER]
    print(f"{'strategy':16}" + "".join(f"{x:>7}" for x in SLOT_ORDER) + f"{'TOTAL':>8}")
    for nm in order:
        row = slot_df.loc[nm]
        print(f"{nm:16}" + "".join(f"{row[x]:7.0f}" for x in SLOT_ORDER) + f"{row.sum():8.0f}")
    print("vs-Ours (negative = weaker slot):")
    for nm in order:
        if nm == "Ours":
            continue
        d = slot_df.loc[nm] - slot_df.loc["Ours"]
        print(f"  {nm:16}" + "".join(f"{d[x]:+7.0f}" for x in SLOT_ORDER) + f"   worst: {d.idxmin()} ({d.min():+.0f})")

    # ---- PICK LOG -> app-ready JSON (top-3 candidates R1-8, top-1 R9-16) ----
    pj = {"generated": f"Ours strategy, {N} sims/slot, realistic-ADP opponents "
                       f"(sigma {OPP_SIGMA_BASE}+{OPP_SIGMA_FRAC}*adp), slots 1-12",
          "schema": "per slot: rounds[]; round r lists top-3 candidates for r<=8 else top-1; each "
                    "candidate has player, freq (share of N sims), metrics, pros[], con (authored later)",
          "N": N, "slots": []}
    for s in slots:
        pbr = by_slot[s]["_picks_by_round"]
        rounds_out = [{"round": r, "candidates": [
            {"player": nm, "freq": round(ct / N, 2), "metrics": metrics_for(nm), "pros": [], "con": ""}
            for nm, ct in pbr[r][:(3 if r <= 8 else 1)]]} for r in range(1, ROUNDS + 1)]
        pj["slots"].append({"slot": s, "rounds": rounds_out})
    with open("icm/work/mc_research/pick_capture.json", "w") as f:
        json.dump(pj, f, indent=2)
    print(f"\nwrote pick_capture.json ({len(pj['slots'])} slots; top-3 R1-8, top-1 R9-16)")
    print("R1 pick per slot (sanity: Gibbs should NOT appear past slot 2):")
    for s in pj["slots"]:
        r1 = s["rounds"][0]["candidates"][0]
        print(f"  slot {s['slot']:>2} R1: {r1['player']} ({r1['freq']:.0%})")
