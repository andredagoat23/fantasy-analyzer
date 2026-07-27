"""30 — Rounds 2-3 (ADP 16-40), the same deep treatment R1 got — plus a systematic INTERACTION scan.

At slot 7 the user picks 18 and 31, so this band holds two of his first three picks. 26_ established
the headline for it (hit rate 60.1%, higher than R1; `capital_top64` the one robust condition), but
that was a pooled, marginal view. This goes deeper in three ways:

**A. Why is R2-3 a BETTER band than R1?** Compare the hit/bust/mult distributions directly. If it is
   just that the price bar is lower, the mult distribution should shift while the raw production
   ordering doesn't — worth knowing before concluding "round 2 is safer."

**B. Position-specific conditions inside the band.** R1 taught us conditions do not transfer across
   positions (draft capital is everything for an RB and worthless for a WR), so pooling RB+WR inside
   R2-3 could easily hide or invent an effect.

**C. A systematic INTERACTION SCAN.** 28_ found by hand that `proven_at_price` is inert among healthy
   players and powerful only for players coming off a missed-time season — a CONDITIONAL prerequisite,
   which is exactly the structure the user hypothesised. This scans every condition against every
   split automatically, so we stop finding those one at a time.
   Multiple-testing honesty: the scan runs conditions x splits tests and PRINTS the count, requires
   both subgroups n>=25, a >=12pp gap between subgroup lifts, and bootstrap P>=0.85 on the strong
   side. Survivors are HYPOTHESES to check, not conclusions.

Run:  .venv/bin/python icm/work/mc_research/30_r2r3_deep.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from utils import normalize_name  # noqa: E402

PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_30_r2r3.txt")

LO, HI = 16, 40
N_BOOT = 1500
RNG = np.random.default_rng(0)

NUM = ["adp", "adp_pos_rank", "age", "mult", "games", "season", "draft_number", "prev_games",
       "prev_snap_pct", "prev_touches_pg", "prev_tgt_share", "prev_wopr", "prev_ppg", "prev_xfp_pg",
       "prev_implied_total_avg", "prev_cv", "prev_pos_rank_total", "prev_total_touches",
       "touches_pg", "tgt_share", "years_exp", "prev_inj_weeks_out"]

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def load():
    p = pd.read_parquet(PANEL)
    for c in NUM:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p[(p["adp"].notna()) & (p["season"] >= 2015)
          & p["position"].isin(["RB", "WR", "TE", "QB"])].copy()
    p["hit"] = (p["mult"] >= 1.0).astype(float)
    p["bust"] = (p["mult"] <= 0.7).astype(float)
    return p


def conditions(p):
    med = lambda s: s.median()
    c = pd.DataFrame(index=p.index)
    ratio = p["prev_ppg"] / p["prev_xfp_pg"].replace(0, np.nan)
    c["earned_prod"] = ratio <= 1.15
    c["capital_top32"] = p["draft_number"].fillna(999) <= 32
    c["capital_top64"] = p["draft_number"].fillna(999) <= 64
    c["wopr_strong"] = p["prev_wopr"].fillna(0) >= p["prev_wopr"].groupby(p["position"]).transform(med)
    c["proven_at_price"] = p["prev_pos_rank_total"].fillna(99) <= p["adp_pos_rank"].fillna(99)
    c["had_a_role"] = p["prev_snap_pct"].fillna(0) >= 0.50
    c["durable_prev"] = p["prev_games"] >= 15
    c["good_offense"] = p["prev_implied_total_avg"] >= p["prev_implied_total_avg"].median()
    c["light_workload"] = p["prev_total_touches"] < p["prev_total_touches"].median()
    return c.astype(float)


def splits(p):
    s = pd.DataFrame(index=p.index)
    s["healthy last yr"] = (p["prev_games"] >= 15).astype(float)
    s["age <=25"] = (p["age"] <= 25).astype(float)
    s["experienced (3+ yr)"] = (p["years_exp"] >= 3).astype(float)
    s["is RB"] = (p["position"] == "RB").astype(float)
    s["had a real role"] = (p["prev_snap_pct"].fillna(0) >= 0.50).astype(float)
    return s


def lift(hit, cond):
    t, f = cond == 1, cond == 0
    if t.sum() < 10 or f.sum() < 10:
        return np.nan
    return 100.0 * (hit[t].mean() - hit[f].mean())


def boot_p(hit, cond):
    h, c = np.asarray(hit, float), np.asarray(cond, float)
    n = len(h)
    out = []
    for _ in range(N_BOOT):
        i = RNG.integers(0, n, n)
        hh, cc = h[i], c[i]
        t, f = cc == 1, cc == 0
        if t.sum() >= 5 and f.sum() >= 5:
            out.append(100.0 * (hh[t].mean() - hh[f].mean()))
    return float((np.array(out) > 0).mean()) if len(out) >= 100 else np.nan


def part_a(p):
    say("=" * 82)
    say("A. WHY IS R2-3 A BETTER BAND THAN R1?")
    say("=" * 82)
    for lo, hi, lab in [(1, 15, "R1   (ADP 1-15)"), (LO, HI, "R2-3 (ADP 16-40)"),
                        (41, 75, "R4-6 (ADP 41-75)")]:
        s = p[(p["adp"] >= lo) & (p["adp"] <= hi)]
        say(f"  {lab}: n={len(s):<4} HIT {s['hit'].mean():.1%}  BUST {s['bust'].mean():.1%}  "
            f"median mult {s['mult'].median():.2f}  ·  median FINISH rank "
            f"{s['pos_rank_total'].median():.0f} vs median PRICE rank {s['adp_pos_rank'].median():.0f}")
    say("\n  Read: if R2-3's edge is just a lower bar, its median FINISH will be worse than R1's while")
    say("  its median mult is better — i.e. you are not buying better players, you are buying a")
    say("  cheaper promise. Compare the last two columns above.")


def part_b(p):
    say("\n" + "=" * 82)
    say("B. CONDITIONS INSIDE R2-3, BY POSITION (pooling hides position-specific effects)")
    say("=" * 82)
    band = p[(p["adp"] >= LO) & (p["adp"] <= HI)]
    for lab, sub in [("ALL", band), ("RB", band[band["position"] == "RB"]),
                     ("WR", band[band["position"] == "WR"])]:
        if len(sub) < 45:
            say(f"\n  {lab}: n={len(sub)} — too small")
            continue
        cs = conditions(sub)
        say(f"\n  {lab} · n={len(sub)} · HIT {sub['hit'].mean():.1%}")
        say(f"  {'condition':<18}{'lift':>7}{'P(>0)':>8}  note")
        for col in cs.columns:
            l0 = lift(sub["hit"], cs[col])
            if np.isnan(l0):
                continue
            pg = boot_p(sub["hit"], cs[col])
            flag = "STRONG" if abs(l0) >= 10 and (pg >= 0.90 or pg <= 0.10) else ""
            if abs(l0) >= 5 or flag:
                say(f"  {col:<18}{l0:>+6.1f}{pg:>8.2f}  {flag}")


def part_c(p):
    say("\n" + "=" * 82)
    say("C. INTERACTION SCAN — where is a condition CONDITIONAL on the player's profile?")
    say("=" * 82)
    band = p[(p["adp"] >= LO) & (p["adp"] <= HI)]
    cs, sp = conditions(band), splits(band)
    tests = 0
    hits = []
    for col in cs.columns:
        for sname in sp.columns:
            a = band[sp[sname] == 1]
            b = band[sp[sname] == 0]
            if len(a) < 25 or len(b) < 25:
                continue
            la = lift(a["hit"], cs.loc[a.index, col])
            lb = lift(b["hit"], cs.loc[b.index, col])
            if np.isnan(la) or np.isnan(lb):
                continue
            tests += 1
            gap = la - lb
            if abs(gap) < 12:
                continue
            strong, weak = (a, b) if abs(la) > abs(lb) else (b, a)
            sl = la if abs(la) > abs(lb) else lb
            pg = boot_p(strong["hit"], cs.loc[strong.index, col])
            if np.isnan(pg) or not (pg >= 0.85 or pg <= 0.15):
                continue
            side = sname if (abs(la) > abs(lb)) else f"NOT {sname}"
            hits.append((col, side, sl, la if abs(la) <= abs(lb) else lb, pg, len(strong)))
    say(f"  ran {tests} condition x split tests; reporting those with a >=12pp subgroup gap "
        f"AND bootstrap P>=0.85\n")
    if not hits:
        say("  none survived — no conditional structure detected in this band")
    else:
        say(f"  {'condition':<18}{'applies to':<24}{'lift there':>11}{'elsewhere':>11}{'P':>7}{'n':>6}")
        for col, side, sl, ol, pg, n in sorted(hits, key=lambda x: -abs(x[2])):
            say(f"  {col:<18}{side:<24}{sl:>+10.1f}{ol:>+11.1f}{pg:>7.2f}{n:>6}")
    say("\n  These are HYPOTHESES, not conclusions: with this many tests some will be chance.")
    say("  Treat any survivor as something to re-check, the way 28_ re-checked proven_at_price.")


def part_d(p):
    say("\n" + "=" * 82)
    say("D. THE 2026 BOARD AT PICKS 18 AND 31 (band's robust condition: NFL draft capital top-64)")
    say("=" * 82)
    b = pd.read_csv(os.path.join(ROOT, "value_board.csv"))
    b["position"] = b["pos_label"].str.replace(r"\d+$", "", regex=True)
    b = b[b["adp_rank"].between(LO - 4, HI)].copy()
    b["key"] = b["full_name"].map(normalize_name)
    role = pd.read_csv(os.path.join(ROOT, "role_data.csv"))
    role["key"] = role["name"].map(normalize_name)
    rmap = role.drop_duplicates("key").set_index("key")
    b["cap"] = pd.to_numeric(b["key"].map(rmap["nfl_pick"]), errors="coerce")
    b["cap"] = b["cap"].fillna(pd.to_numeric(b.get("draft_pick"), errors="coerce"))
    b["share25"] = pd.to_numeric(b["key"].map(rmap["share_2025"]), errors="coerce")
    b["wk25"] = pd.to_numeric(b["key"].map(rmap["weeks_2025"]), errors="coerce")
    # Apply the CONDITIONAL rule from part C, not the marginal one: draft capital predicts hugely
    # (+42pp) for players with NO real role last year, and does nothing (+0.6pp) for players you can
    # already judge on usage. Using it marginally would wrongly fade proven-role backs with late
    # draft capital.
    say("  Applying the CONDITIONAL rule from C: capital is the signal ONLY where last-year usage")
    say("  can't be judged (no real role). Players with an established 2025 role are judged on that.\n")
    say(f"  {'player':<24}{'pos':<6}{'ADP':>6}  2025 role        capital  read")
    for r in b.sort_values("adp_rank").itertuples():
        if r.position in ("K", "DEF", "DST"):
            continue
        no_role = (pd.isna(r.share25) or r.share25 < 0.10 or pd.isna(r.wk25) or r.wk25 < 6)
        capok = pd.notna(r.cap) and r.cap <= 64
        capt = f"NFL #{int(r.cap)}" if pd.notna(r.cap) else "unknown"
        rolet = (f"{r.share25:.0%} / {int(r.wk25)}wk"
                 if pd.notna(r.share25) and pd.notna(r.wk25) else "none/rookie")
        read = (("CAPITAL-BACKED ✓" if capok else "no role + weak capital ✗") if no_role
                else "judge on role (capital n/a)")
        say(f"  {r.full_name:<24}{r.pos_label:<6}{r.adp_rank:>6.1f}  {rolet:<16} {capt:<8} {read}")


def main():
    p = load()
    p["pos_rank_total"] = pd.to_numeric(p["pos_rank_total"], errors="coerce")
    part_a(p)
    part_b(p)
    part_c(p)
    part_d(p)
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
