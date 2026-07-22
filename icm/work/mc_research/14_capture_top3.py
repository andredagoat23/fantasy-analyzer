# CAPTURE OUR TOP-3 PICKS PER SLOT — for the future Research page. Simulates ONLY our strategy
# (the real advisor engine) from each of the 12 draft slots against ADP-bot opponents, and records
# the MODAL player we take in rounds 1-3 at each slot, with his board metrics. Emits app-ready JSON.
# Each draft is stopped after our 3rd pick (cheap). Reasons (3 pro / 1 con) are authored separately
# from the metrics this dumps. Research artifact — reads value_board.csv + advisor.py; changes nothing.
import json
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import advisor

TEAMS, ROUNDS = 12, 16
board_full = pd.read_csv("value_board.csv")
board_full["position"] = board_full["pos_label"].str.extract(r"([A-Z]+)")
_cohort = pd.read_csv("cohort_data.csv").set_index("full_name")["cohort_trimmed"] \
    if __import__("os").path.exists("cohort_data.csv") else pd.Series(dtype=float)


def snake_picker(overall, teams=TEAMS):
    r, i = (overall - 1) // teams + 1, (overall - 1) % teams + 1
    return i if r % 2 else teams - i + 1


def opponent_pick(avail, rng, rd):
    pool = avail.dropna(subset=["adp_rank"]).copy()
    if rd <= 10:
        pool = pool[pool.position != "K"]
    pool = pool.nsmallest(12, "adp_rank")
    if pool.empty:
        pool = avail.head(5)
    return pool.sample(1, weights=np.linspace(1.0, 0.2, len(pool)),
                       random_state=int(rng.integers(1e9))).iloc[0].full_name


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


def capture_draft(slot, seed):
    """One draft; return our first 3 picks as [(round, name), ...] — stops after pick 3."""
    rng = np.random.default_rng(seed)
    drafted, mine, picks = set(), [], []
    for overall in range(1, TEAMS * ROUNDS + 1):
        avail = board_full[~board_full.full_name.isin(drafted)]
        if snake_picker(overall) != slot:
            drafted.add(opponent_pick(avail, rng, (overall - 1) // TEAMS + 1))
            continue
        roster = board_full[board_full.full_name.isin(mine)].sort_values("total_points", ascending=False)
        name = ours_pick(avail, roster, overall, slot)
        picks.append(((overall - 1) // TEAMS + 1, name))
        mine.append(name)
        drafted.add(name)
        if len(mine) >= 3:
            break
    return picks


def run_slot_capture(slot, N):
    by_round = {1: Counter(), 2: Counter(), 3: Counter()}
    for sd in range(1, N + 1):
        for rnd, name in capture_draft(slot, sd):
            by_round[rnd][name] += 1
    return slot, {r: c.most_common(3) for r, c in by_round.items()}   # top-3 modal names per round


def _star(arg):
    return run_slot_capture(*arg)


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


if __name__ == "__main__":
    import multiprocessing as mp
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    slots = list(range(1, TEAMS + 1))
    nproc = min(len(slots), mp.cpu_count())
    print(f"Capturing our top-3 picks: {len(slots)} slots x {N} seeds, {nproc} procs.\n", flush=True)
    by_slot = {}
    with mp.Pool(nproc) as pool:
        for slot, res in pool.imap_unordered(_star, [(s, N) for s in slots]):
            by_slot[slot] = res
            print(f"  slot {slot} done ({len(by_slot)}/{len(slots)})", flush=True)

    out = {"generated": f"Ours strategy, {N} sims/slot, ADP-bot opponents, slots 1-12, rounds 1-3",
           "note": "modal = most-frequent player we drafted at that slot+round; freq is out of N sims. "
                   "pros/con to be authored from metrics.", "N": N, "slots": []}
    for s in slots:
        picks = []
        for rnd in (1, 2, 3):
            modal = by_slot[s][rnd]
            top_name, top_ct = modal[0]
            picks.append({"round": rnd, "player": top_name, "freq": round(top_ct / N, 2),
                          "runners_up": [{"player": nm, "freq": round(ct / N, 2)} for nm, ct in modal[1:]],
                          "metrics": metrics_for(top_name), "pros": [], "con": ""})
        out["slots"].append({"slot": s, "picks": picks})

    with open("icm/work/mc_research/pick_capture.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote icm/work/mc_research/pick_capture.json ({len(out['slots'])} slots x 3 rounds)")
    for s in out["slots"]:
        line = "  ".join(f"R{p['round']}:{p['player']} ({p['freq']:.0%})" for p in s["picks"])
        print(f"slot {s['slot']:>2}: {line}")
