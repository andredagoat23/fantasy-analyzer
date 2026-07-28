"""22 — What ACTUALLY happens after a positional run? (L48 design check on real Sleeper drafts)

Question (user's design review, Jul 28): does a run make the position MORE likely to keep going
(momentum / room preference) or LESS (a 1-start run consumes its own demand — each QB taker is done
at QB)? The shipped L48 read assumed momentum for every position; the proposed refinement restricts
flags to RB/WR. This script measures the real dynamics on the corpus from 21_.

Method (all baselines SLOT-MATCHED, so early/late mix differences can't fake an effect):
- s_bar[pos][slot] = corpus share of drafts whose pick at that absolute slot is pos.
- For every draft & pick index t (full 8-pick window before it): k = count of pos in the window,
  E[k] = sum of s_bar over those 8 slots. HOT mirrors the shipped rule (binomial tail <=.05, k>=3
  vs s=E/8); COLD mirrors it too (lower tail <=.10, E>=1).
- Outcomes: P(pos taken at t) and P(pos taken in t..t+3), each vs the baseline expectation AT THE
  SAME conditioned slots (mean of s_bar / product-form over exactly the t's where the condition
  fired). Delta = conditional - matched baseline, in percentage points.
- Dose-response: Delta(next-4) by run size k = 3,4,5,6+ per position — monotonic growth is the
  signature of a real behavioral effect.
- Mechanism check (1-start): after a QB/TE HOT window, what fraction of the next-4 picking teams
  ALREADY hold >=1 of that position (reconstructed rosters), vs the slot-round baseline?
- Segments: all drafts / mostly-human (>=90% human picks) / league drafts (league_id set).

Confound honesty: conditioning on a run selects rooms that like the position, which biases Delta
POSITIVE for every position. So a NEGATIVE QB/TE Delta is strong evidence of depletion; a positive
RB/WR Delta supports the momentum read but can't be split from room preference (both justify HOT).

Run:  .venv/bin/python icm/work/mc_research/22_run_dynamics.py
"""
import json
import math
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sleeper_drafts_2026.jsonl")
OUT = os.path.join(HERE, "results_22_run_dynamics.txt")

FLAG_POS = ("RB", "WR", "QB", "TE")
W = 8
HOT_P, COLD_P, MIN_K = 0.05, 0.10, 3
NEXT = 4                      # look-ahead picks for the continuation outcome

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def tail(n, lo, hi, s):
    s = min(max(s, 0.0), 1.0)
    return sum(math.comb(n, i) * s**i * (1.0 - s)**(n - i) for i in range(lo, hi + 1))


def load():
    drafts = []
    with open(SRC) as f:
        for line in f:
            d = json.loads(line)
            if d.get("teams") != 12:
                continue
            picks = sorted(d["picks"], key=lambda p: p["no"] or 0)
            pos = [("RB" if p["pos"] == "FB" else p["pos"]) for p in picks]
            slot = [p["slot"] for p in picks]
            human = [p["human"] for p in picks]
            if not picks or any(p["no"] != i + 1 for i, p in enumerate(picks)):
                continue                       # non-contiguous payload -> drop
            drafts.append({"pos": pos, "slot": slot,
                           "human_frac": sum(human) / len(human),
                           "league": bool(d.get("league_id")),
                           "qb1": d.get("slots_qb") == 1 and not d.get("slots_super_flex")})
    return drafts


def baselines(drafts):
    """s_bar[pos][slot_index0] + per-slot denominators."""
    max_n = max(len(d["pos"]) for d in drafts)
    cnt = {p: [0] * max_n for p in FLAG_POS}
    den = [0] * max_n
    for d in drafts:
        for i, p in enumerate(d["pos"]):
            den[i] += 1
            if p in cnt:
                cnt[p][i] += 1
    sbar = {p: [(cnt[p][i] / den[i]) if den[i] else 0.0 for i in range(max_n)] for p in FLAG_POS}
    return sbar, den


def analyze(drafts, sbar, label):
    say(f"\n=== segment: {label} · {len(drafts)} drafts ===")
    # acc[(pos, cond)] = [n, hit1, exp1, hit4, exp4]
    acc = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])
    dose = defaultdict(lambda: [0, 0.0, 0.0])           # (pos, k_bucket) -> [n, hit4, exp4]
    mech = defaultdict(lambda: [0, 0.0, 0.0])           # pos -> [n_next_picks, already_have, base_have]
    have_base = defaultdict(lambda: [0, 0.0])           # (pos, round_bucket) -> [n, already_have]

    # pass 1: unconditional "next picker already holds pos" baseline by round bucket (1-start mech)
    for d in drafts:
        held = defaultdict(set)                          # pos -> slots holding >=1
        for i, (p, sl) in enumerate(zip(d["pos"], d["slot"])):
            if i >= W:
                rb = i // 24                             # 2-round buckets
                for fp in ("QB", "TE"):
                    b = have_base[(fp, rb)]
                    b[0] += 1
                    b[1] += 1.0 if sl in held[fp] else 0.0
            if p in FLAG_POS:
                held[p].add(sl)

    for d in drafts:
        n = len(d["pos"])
        held = defaultdict(set)
        for t in range(n):
            if t >= W:
                win = d["pos"][t - W:t]
                for fp in FLAG_POS:
                    k = sum(1 for x in win if x == fp)
                    E = sum(sbar[fp][j] for j in range(t - W, t))
                    s = E / W
                    hot = k >= MIN_K and tail(W, k, W, s) <= HOT_P
                    cold = E >= 1.0 and tail(W, 0, k, s) <= COLD_P
                    if not (hot or cold):
                        continue
                    hit1 = 1.0 if d["pos"][t] == fp else 0.0
                    exp1 = sbar[fp][t]
                    fut = d["pos"][t:t + NEXT]
                    hit4 = 1.0 if fp in fut else 0.0
                    exp4 = 1.0
                    for j in range(t, min(t + NEXT, n)):
                        exp4 *= (1.0 - sbar[fp][j])
                    exp4 = 1.0 - exp4
                    cond = "HOT" if hot else "COLD"
                    a = acc[(fp, cond)]
                    a[0] += 1; a[1] += hit1; a[2] += exp1; a[3] += hit4; a[4] += exp4
                    if hot:
                        kb = min(k, 6)
                        db = dose[(fp, kb)]
                        db[0] += 1; db[1] += hit4; db[2] += exp4
                        if fp in ("QB", "TE"):
                            rb = t // 24
                            bb = have_base[(fp, rb)]
                            basef = (bb[1] / bb[0]) if bb[0] else 0.0
                            for j in range(t, min(t + NEXT, n)):
                                m = mech[fp]
                                m[0] += 1
                                m[1] += 1.0 if d["slot"][j] in held[fp] else 0.0
                                m[2] += basef
            p = d["pos"][t]
            if p in FLAG_POS:
                held[p].add(d["slot"][t])

    say(f"{'pos':<4}{'cond':<6}{'n':>6}  {'P(next1)':>9}{'base1':>7}{'Δpp':>7}   "
        f"{'P(next4)':>9}{'base4':>7}{'Δpp':>7}")
    for fp in FLAG_POS:
        for cond in ("HOT", "COLD"):
            a = acc[(fp, cond)]
            if a[0] < 25:
                say(f"{fp:<4}{cond:<6}{a[0]:>6}  (too few windows)")
                continue
            p1, e1 = a[1] / a[0], a[2] / a[0]
            p4, e4 = a[3] / a[0], a[4] / a[0]
            say(f"{fp:<4}{cond:<6}{a[0]:>6}  {p1:>8.1%}{e1:>7.1%}{100 * (p1 - e1):>+6.1f}   "
                f"{p4:>8.1%}{e4:>7.1%}{100 * (p4 - e4):>+6.1f}")

    say("\ndose-response (HOT windows): Δpp on P(pos in next 4) by run size k")
    hdr = "pos  " + "".join(f"{('k=' + str(k)) if k < 6 else 'k>=6':>12}" for k in (3, 4, 5, 6))
    say(hdr)
    for fp in FLAG_POS:
        row = f"{fp:<4}"
        for k in (3, 4, 5, 6):
            db = dose[(fp, k)]
            row += f"{'—':>12}" if db[0] < 15 else f"{100 * (db[1] - db[2]) / db[0]:>+9.1f} ({db[0]})"
        say(row)

    say("\n1-start mechanism after a HOT run: next-4 picking teams that ALREADY hold the position")
    for fp in ("QB", "TE"):
        m = mech[fp]
        if m[0] < 25:
            say(f"{fp}: too few windows ({m[0]})")
            continue
        say(f"{fp}: {m[1] / m[0]:.1%} already-have vs {m[2] / m[0]:.1%} round-matched baseline "
            f"({m[0]} next-picks)")
    return acc


def mix_table(drafts, label):
    sbar, _ = baselines(drafts)
    say(f"\nposition mix by round ({label}):")
    for r in (0, 1, 2, 4, 7, 10, 13):
        lo, hi = r * 12, r * 12 + 12
        mix = {p: sum(sbar[p][lo:hi]) / 12 for p in FLAG_POS}
        say(f"  R{r + 1:<3}" + "  ".join(f"{p} {mix[p]:.0%}" for p in FLAG_POS))
    return sbar


def main():
    alld = load()
    one = [d for d in alld if d["qb1"]]
    sf = [d for d in alld if not d["qb1"]]
    say(f"corpus: {len(alld)} complete 12-team snake drafts (2026), "
        f"{sum(len(d['pos']) for d in alld)} picks")
    say(f"  formats: {len(one)} ONE-QB (the user's format) · {len(sf)} superflex/2QB")
    say(f"  league-attached: {sum(1 for d in alld if d['league'])} · "
        f"mostly-human (>=90% human picks): {sum(1 for d in alld if d['human_frac'] >= 0.9)}")
    if not one:
        say("no 1QB drafts yet — rerun after the crawler collects more")
        return
    sbar1 = mix_table(one, "1QB — sanity: R1 QB share should be small")
    analyze(one, sbar1, "1QB drafts (PRIMARY — the user's format)")
    seg = [d for d in one if d["human_frac"] >= 0.9]
    if 30 <= len(seg) < len(one):
        analyze(seg, baselines(seg)[0], "1QB & mostly-human")
    seg = [d for d in one if d["league"]]
    if 30 <= len(seg) < len(one):
        analyze(seg, baselines(seg)[0], "1QB & league-attached")
    if len(sf) >= 30:
        mix_table(sf, "superflex/2QB — contrast")
        analyze(sf, baselines(sf)[0], "superflex/2QB (CONTRAST — not the user's format)")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
