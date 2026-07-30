# SLOT PICK DISTRIBUTION — what does OUR advisor actually draft from each of the 12 seats?
#
# Runs N mock drafts per draft slot (default 100 -> 1200 drafts) with the REAL advisor in our seat
# (add_vona -> build_context -> TOP PICKS #1, no API) against the calibrated sticky-ADP bot field,
# then reports, for every (slot, round):
#   * the PLAYER distribution  — share of the N sims in which we took each player
#   * the POSITION distribution — share of the N sims by QB/RB/WR/TE/K
#
# Reuses 13_strategy_bakeoff.py's machinery by IMPORT (not copy), so the opponent model
# (sigma = 1.5 + 0.10*adp, so elite picks stay sticky) and the mandatory-starter deadline guard are
# provably identical to the validated bake-off. Only the "Ours" contestant runs here.
#
# Seeds 1..N are the SAME at every slot, so slot-to-slot differences are the slot, not luck: our
# picks are deterministic given the field, so all variation across the N sims comes from opponents.
#
# Research artifact — reads value_board.csv + advisor.py, changes NOTHING shipped.
# Run from the repo root:  .venv/bin/python icm/work/mc_research/45_slot_pick_distribution.py [N]
import csv
import importlib.util
import sys
from collections import Counter

sys.path.insert(0, ".")

# 13_'s filename starts with a digit, so it can't be a normal `import` — load it by path.
# This runs in spawned children too (they re-import this file), which is what we want.
_spec = importlib.util.spec_from_file_location("bakeoff13", "icm/work/mc_research/13_strategy_bakeoff.py")
bakeoff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bakeoff)

TEAMS, ROUNDS = bakeoff.TEAMS, bakeoff.ROUNDS
POSITIONS = ["QB", "RB", "WR", "TE", "K"]
CUTOFF = 0.02                      # players below this share get rolled into "+N others"
OUT_DIR = "icm/work/mc_research"


def run_slot(slot, n):
    """N mock drafts from one slot. Returns per-round player + position Counters (picklable)."""
    players = {r: Counter() for r in range(1, ROUNDS + 1)}
    posits = {r: Counter() for r in range(1, ROUNDS + 1)}
    for seed in range(1, n + 1):
        _, order = bakeoff.run_draft(None, seed, True, slot)   # None/True = the "Ours" advisor path
        for rd, name in enumerate(order, 1):
            players[rd][name] += 1
            posits[rd][bakeoff.posser.get(name, "?")] += 1
    return slot, players, posits


def _run_slot_star(arg):
    return run_slot(*arg)


def pct(count, n):
    return 100.0 * count / n


def fmt_round_players(counter, n):
    """'Name 54% | Name 31% | +3 others 6%' — everything under CUTOFF rolled up."""
    ranked = counter.most_common()
    shown = [(nm, c) for nm, c in ranked if c / n >= CUTOFF]
    tail = [(nm, c) for nm, c in ranked if c / n < CUTOFF]
    parts = [f"{nm} {pct(c, n):.0f}%" for nm, c in shown]
    if tail:
        parts.append(f"+{len(tail)} others {pct(sum(c for _, c in tail), n):.0f}%")
    return " | ".join(parts) if parts else "(none)"


if __name__ == "__main__":
    import multiprocessing as mp

    N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    slots = list(range(1, TEAMS + 1))
    nproc = min(len(slots), mp.cpu_count())
    print(f"Slot pick distribution: {N} mocks x {len(slots)} slots = {len(slots) * N} drafts "
          f"({len(slots) * N * ROUNDS} advised picks), {nproc} procs.", flush=True)

    by_slot = {}
    with mp.Pool(nproc) as pool:
        for slot, players, posits in pool.imap_unordered(_run_slot_star, [(s, N) for s in slots]):
            by_slot[slot] = (players, posits)
            print(f"  slot {slot} done ({len(by_slot)}/{len(slots)})", flush=True)

    L = []                                                     # report lines (printed AND saved)
    def say(s=""):
        L.append(s)
        print(s, flush=True)

    say(f"\n{'=' * 78}")
    say(f"SLOT PICK DISTRIBUTION — real advisor, {N} mocks/slot, {len(slots) * N} drafts total")
    say(f"opponents: sticky-ADP (sigma {bakeoff.OPP_SIGMA_BASE}+{bakeoff.OPP_SIGMA_FRAC}*adp) · "
        f"seeds 1-{N} identical at every slot · L51 measured survival curve LIVE")
    say(f"{'=' * 78}")

    # ---- POSITION % by round, per slot ----
    say(f"\n=== POSITION % BY ROUND, PER SLOT ===")
    for s in slots:
        _, posits = by_slot[s]
        say(f"\n--- SLOT {s} ---")
        say(f"{'rd':>3}" + "".join(f"{p:>7}" for p in POSITIONS))
        for r in range(1, ROUNDS + 1):
            cells = []
            for p in POSITIONS:
                c = posits[r].get(p, 0)
                cells.append(f"{pct(c, N):6.0f}%" if c else f"{'-':>7}")
            say(f"{r:>3}" + "".join(cells))

    # ---- POSITION % by round, pooled over all slots ----
    say(f"\n\n=== POSITION % BY ROUND, POOLED over all {len(slots)} slots "
        f"({len(slots) * N} drafts) ===")
    say(f"{'rd':>3}" + "".join(f"{p:>7}" for p in POSITIONS))
    pooled_n = len(slots) * N
    for r in range(1, ROUNDS + 1):
        tot = Counter()
        for s in slots:
            tot.update(by_slot[s][1][r])
        cells = [f"{pct(tot.get(p, 0), pooled_n):6.0f}%" if tot.get(p, 0) else f"{'-':>7}"
                 for p in POSITIONS]
        say(f"{r:>3}" + "".join(cells))

    # ---- roster SHAPE per slot (how many of each position a full 16-round draft ends with) ----
    say(f"\n\n=== AVG ROSTER SHAPE PER SLOT (positions per 16-round draft) ===")
    say(f"{'slot':>4}" + "".join(f"{p:>7}" for p in POSITIONS))
    for s in slots:
        _, posits = by_slot[s]
        tot = Counter()
        for r in range(1, ROUNDS + 1):
            tot.update(posits[r])
        say(f"{s:>4}" + "".join(f"{tot.get(p, 0) / N:7.2f}" for p in POSITIONS))

    # ---- PLAYER % by round, per slot ----
    say(f"\n\n=== PLAYERS TAKEN PER ROUND, PER SLOT (>={CUTOFF:.0%} shown, rest rolled up) ===")
    for s in slots:
        players, _ = by_slot[s]
        say(f"\n--- SLOT {s} ---")
        for r in range(1, ROUNDS + 1):
            say(f" R{r:<2} {fmt_round_players(players[r], N)}")

    # ---- files ----
    with open(f"{OUT_DIR}/results_45_slot_distribution.txt", "w") as f:
        f.write("\n".join(L) + "\n")

    with open(f"{OUT_DIR}/45_player_by_round.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["slot", "round", "player", "position", "count", "pct", "n_sims"])
        for s in slots:
            players, _ = by_slot[s]
            for r in range(1, ROUNDS + 1):
                for nm, c in players[r].most_common():
                    w.writerow([s, r, nm, bakeoff.posser.get(nm, "?"), c,
                                round(pct(c, N), 1), N])

    with open(f"{OUT_DIR}/45_position_by_round.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["slot", "round"] + [f"{p}_pct" for p in POSITIONS] + ["n_sims"])
        for s in slots:
            _, posits = by_slot[s]
            for r in range(1, ROUNDS + 1):
                w.writerow([s, r] + [round(pct(posits[r].get(p, 0), N), 1) for p in POSITIONS] + [N])

    say(f"\nwrote results_45_slot_distribution.txt, 45_player_by_round.csv, "
        f"45_position_by_round.csv  ({OUT_DIR}/)")
