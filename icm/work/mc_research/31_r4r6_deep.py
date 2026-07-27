"""31 — Rounds 4-6 (ADP 41-75) deep dive, and a REPLICATION TEST of the study's strongest finding.

At slot 7 this band holds picks 42, 55 and 66 — three of sixteen. 26_ already flagged it as the worst
value band on the board (HIT 50.4% vs 60.1% in R2-3, and the highest bust rate at 23.0%), and 28_
showed its one "robust" condition (`proven_at_price`) is really a conditional that only fires for
players coming off a missed-time season.

The centerpiece here is not another band summary. 30_ found the strongest, most mechanistic result in
the whole arc — **NFL draft capital predicts hugely (+42pp) for a player with NO established role, and
does nothing (+0.6pp) for a player you can already judge on usage** — on 38 seasons in one band. A
result that size on that sample is exactly the kind of thing that is either a real mechanism or a
fluke, and the way to tell is REPLICATION in data it wasn't found in.

So Part D runs that same split across EVERY band side by side. If the rule is real it should appear
in R4-6 and R7-10 too, without being tuned to them. If it only exists in R2-3, it was noise and the
2026 read built on it (trust Jeremiyah Love's pedigree) has to be withdrawn.

Also cross-checks the existing validated TE finding: draft-strategy.md says R4-5 is the TE DEAD ZONE
and ~R6 is the value pocket. That claim came from a per-slot backtest, so this band is where it should
be visible — a good independent test of both analyses.

Run:  .venv/bin/python icm/work/mc_research/31_r4r6_deep.py
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
OUT = os.path.join(HERE, "results_31_r4r6.txt")

LO, HI = 41, 75
BANDS = [(1, 15, "R1"), (16, 40, "R2-3"), (41, 75, "R4-6"), (76, 125, "R7-10")]
N_BOOT = 1500
RNG = np.random.default_rng(0)

NUM = ["adp", "adp_pos_rank", "age", "mult", "games", "season", "draft_number", "prev_games",
       "prev_snap_pct", "prev_touches_pg", "prev_tgt_share", "prev_wopr", "prev_ppg", "prev_xfp_pg",
       "prev_implied_total_avg", "prev_cv", "prev_pos_rank_total", "prev_total_touches",
       "years_exp", "pos_rank_total"]

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def raw_panel():
    """The panel with NO price filter — needed for 2025 lookups.

    IMPORTANT: 2025 rows carry OUTCOMES but no preseason `adp` (only 5 of 608 have one), so any
    price-based analysis silently excludes them. That means every band analysis in 23_-31_ is really
    over **2015-2024 priced seasons** — ten years, not eleven. The 2025 season is still usable as a
    LOOKUP for "what did he do last year", which is what part F needs.
    """
    p = pd.read_parquet(PANEL)
    for c in NUM:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")
    return p


def load():
    p = raw_panel()
    p = p[(p["adp"].notna()) & (p["season"] >= 2015)
          & p["position"].isin(["RB", "WR", "TE", "QB"])].copy()
    p["hit"] = (p["mult"] >= 1.0).astype(float)
    p["bust"] = (p["mult"] <= 0.7).astype(float)
    p["no_role"] = (p["prev_snap_pct"].fillna(0) < 0.50).astype(float)
    p["capital32"] = (p["draft_number"].fillna(999) <= 32).astype(float)
    p["capital64"] = (p["draft_number"].fillna(999) <= 64).astype(float)
    return p


def conditions(p):
    med = lambda s: s.median()
    c = pd.DataFrame(index=p.index)
    ratio = p["prev_ppg"] / p["prev_xfp_pg"].replace(0, np.nan)
    c["earned_prod"] = ratio <= 1.15
    c["capital_top32"] = p["capital32"]
    c["capital_top64"] = p["capital64"]
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
    s["had a real role"] = (1 - p["no_role"]).astype(float)
    return s


def lift(hit, cond):
    t, f = cond == 1, cond == 0
    if t.sum() < 10 or f.sum() < 10:
        return np.nan
    return 100.0 * (hit[t].mean() - hit[f].mean())


def boot_p(hit, cond):
    h, c = np.asarray(hit, float), np.asarray(cond, float)
    n, out = len(h), []
    for _ in range(N_BOOT):
        i = RNG.integers(0, n, n)
        hh, cc = h[i], c[i]
        t, f = cc == 1, cc == 0
        if t.sum() >= 5 and f.sum() >= 5:
            out.append(100.0 * (hh[t].mean() - hh[f].mean()))
    return float((np.array(out) > 0).mean()) if len(out) >= 100 else np.nan


def part_a(p):
    say("=" * 84)
    say("A. R4-6 IN CONTEXT — the worst value band on the board")
    say("=" * 84)
    for lo, hi, lab in BANDS:
        s = p[(p["adp"] >= lo) & (p["adp"] <= hi)]
        say(f"  {lab:<6} n={len(s):<4} HIT {s['hit'].mean():.1%}  BUST {s['bust'].mean():.1%}  "
            f"med mult {s['mult'].median():.2f}")
    band = p[(p["adp"] >= LO) & (p["adp"] <= HI)]
    say(f"\n  R4-6 by position:")
    for pos in ("RB", "WR", "TE", "QB"):
        s = band[band["position"] == pos]
        if len(s) >= 20:
            say(f"    {pos:<3} n={len(s):<4} HIT {s['hit'].mean():.1%}  BUST {s['bust'].mean():.1%}  "
                f"med mult {s['mult'].median():.2f}")


def part_b(p):
    say("\n" + "=" * 84)
    say("B. CONDITIONS INSIDE R4-6, BY POSITION")
    say("=" * 84)
    band = p[(p["adp"] >= LO) & (p["adp"] <= HI)]
    for lab, sub in [("ALL", band), ("RB", band[band["position"] == "RB"]),
                     ("WR", band[band["position"] == "WR"]), ("TE", band[band["position"] == "TE"])]:
        if len(sub) < 45:
            say(f"\n  {lab}: n={len(sub)} — too small to split")
            continue
        cs = conditions(sub)
        say(f"\n  {lab} · n={len(sub)} · HIT {sub['hit'].mean():.1%}")
        say(f"  {'condition':<18}{'lift':>7}{'P(>0)':>8}  note")
        for col in cs.columns:
            l0 = lift(sub["hit"], cs[col])
            if np.isnan(l0) or abs(l0) < 5:
                continue
            pg = boot_p(sub["hit"], cs[col])
            flag = "STRONG" if abs(l0) >= 10 and (pg >= 0.90 or pg <= 0.10) else ""
            say(f"  {col:<18}{l0:>+6.1f}{pg:>8.2f}  {flag}")


def part_c(p):
    say("\n" + "=" * 84)
    say("C. INTERACTION SCAN inside R4-6")
    say("=" * 84)
    band = p[(p["adp"] >= LO) & (p["adp"] <= HI)]
    cs, sp = conditions(band), splits(band)
    tests, hits = 0, []
    for col in cs.columns:
        for sname in sp.columns:
            a, b = band[sp[sname] == 1], band[sp[sname] == 0]
            if len(a) < 25 or len(b) < 25:
                continue
            la, lb = lift(a["hit"], cs.loc[a.index, col]), lift(b["hit"], cs.loc[b.index, col])
            if np.isnan(la) or np.isnan(lb):
                continue
            tests += 1
            if abs(la - lb) < 12:
                continue
            strong = a if abs(la) > abs(lb) else b
            sl, ol = (la, lb) if abs(la) > abs(lb) else (lb, la)
            pg = boot_p(strong["hit"], cs.loc[strong.index, col])
            if np.isnan(pg) or not (pg >= 0.85 or pg <= 0.15):
                continue
            side = sname if abs(la) > abs(lb) else f"NOT {sname}"
            hits.append((col, side, sl, ol, pg, len(strong)))
    say(f"  ran {tests} condition x split tests; >=12pp gap AND bootstrap P>=0.85\n")
    if not hits:
        say("  none survived — no conditional structure detected in this band")
    else:
        say(f"  {'condition':<18}{'applies to':<24}{'there':>9}{'elsewhere':>11}{'P':>7}{'n':>6}")
        for col, side, sl, ol, pg, n in sorted(hits, key=lambda x: -abs(x[2])):
            say(f"  {col:<18}{side:<24}{sl:>+8.1f}{ol:>+11.1f}{pg:>7.2f}{n:>6}")


def part_d(p):
    say("\n" + "=" * 84)
    say("D. REPLICATION TEST — does 'capital matters only when there's no role' hold everywhere?")
    say("=" * 84)
    say("  Found in R2-3 (+42.3pp among no-role players vs +0.6pp among those with a role, n=38).")
    say("  A result that big on that sample is either a real mechanism or a fluke. Replication in")
    say("  bands it was NOT found in is how we tell. Nothing below is tuned.\n")
    for capcol, caplab in (("capital32", "top-32"), ("capital64", "top-64")):
        say(f"  --- NFL draft capital {caplab} ---")
        say(f"  {'band':<8}{'NO role: lift':>15}{'P':>7}{'n':>6}   {'HAS role: lift':>16}{'P':>7}{'n':>6}")
        for lo, hi, lab in BANDS:
            band = p[(p["adp"] >= lo) & (p["adp"] <= hi)]
            row = f"  {lab:<8}"
            for want in (1.0, 0.0):
                sub = band[band["no_role"] == want]
                if len(sub) < 20:
                    row += f"{'(too few)':>15}{'':>7}{len(sub):>6}" if want == 1.0 else \
                           f"   {'(too few)':>16}{'':>7}{len(sub):>6}"
                    continue
                l0 = lift(sub["hit"], sub[capcol])
                if np.isnan(l0):
                    row += f"{'(n/a)':>15}{'':>7}{len(sub):>6}" if want == 1.0 else \
                           f"   {'(n/a)':>16}{'':>7}{len(sub):>6}"
                    continue
                pg = boot_p(sub["hit"], sub[capcol])
                row += (f"{l0:>+14.1f}{pg:>7.2f}{len(sub):>6}" if want == 1.0
                        else f"   {l0:>+15.1f}{pg:>7.2f}{len(sub):>6}")
            say(row)
        say("")
    say("  READ: the rule replicates if the NO-role column is consistently large and positive while")
    say("  the HAS-role column sits near zero, across bands. Judge it on the pattern, not one cell.")
    say("")
    say("  VERDICT — IT DOES NOT REPLICATE.")
    say("  top-32 NO-role goes +42.3 (R2-3, n=38) -> -14.0 (R4-6, n=88) -> +12.5 (R7-10, n=194):")
    say("  it REVERSES in the band with more than twice the sample it was discovered in. And the")
    say("  top-64 version — the same rule one notch wider — collapses to +0.8 and +0.5 outside")
    say("  R2-3. A real mechanism does not evaporate when the cutoff moves from 32 to 64.")
    say("  CONCLUSION: the +42.3pp was almost certainly a fluke of a 38-season cell. WITHDRAWN.")
    say("")
    say("  WHAT SURVIVES: the OTHER half. Capital is near-inert for a player who already HAS a")
    say("  role — +8.9 / +0.6 / -6.8 / +3.1 across the four bands, never meaningful. So 'do not")
    say("  fade an established-role player for a late draft slot' still stands; 'trust a no-role")
    say("  player because of pedigree' does not.")


def part_e(p):
    say("\n" + "=" * 84)
    say("E. TE CROSS-CHECK — does the validated R4-5 'dead zone' show up here?")
    say("=" * 84)
    say("  draft-strategy.md (from a per-slot backtest) says mid-TEs at ~R4-5 are the worst value")
    say("  per pick and ~R6 is the best non-elite pocket. Independent test on this panel:")
    te = p[p["position"] == "TE"]
    for lo, hi, lab in [(1, 25, "elite TE (ADP 1-25)"), (26, 50, "R3-4 TE (26-50)"),
                        (51, 75, "R5-6 TE (51-75)"), (76, 110, "R7-9 TE (76-110)"),
                        (111, 200, "late TE (111+)")]:
        s = te[(te["adp"] >= lo) & (te["adp"] <= hi)]
        if len(s) < 12:
            say(f"    {lab:<22} n={len(s):<4} (too few)")
            continue
        say(f"    {lab:<22} n={len(s):<4} HIT {s['hit'].mean():.1%}  BUST {s['bust'].mean():.1%}  "
            f"med mult {s['mult'].median():.2f}")


def part_f(p_unused):
    say("\n" + "=" * 84)
    say("F. THE 2026 BOARD AT PICKS 42, 55, 66")
    say("=" * 84)
    p = raw_panel()      # 2025 rows have no ADP, so the price-filtered panel can't serve this lookup
    b = pd.read_csv(os.path.join(ROOT, "value_board.csv"))
    b["position"] = b["pos_label"].str.replace(r"\d+$", "", regex=True)
    b = b[b["adp_rank"].between(LO - 4, HI + 4)].copy()
    b["key"] = b["full_name"].map(normalize_name)
    role = pd.read_csv(os.path.join(ROOT, "role_data.csv"))
    role["key"] = role["name"].map(normalize_name)
    rmap = role.drop_duplicates("key").set_index("key")
    b["cap"] = pd.to_numeric(b["key"].map(rmap["nfl_pick"]), errors="coerce").fillna(
        pd.to_numeric(b.get("draft_pick"), errors="coerce"))
    b["share25"] = pd.to_numeric(b["key"].map(rmap["share_2025"]), errors="coerce")
    b["wk25"] = pd.to_numeric(b["key"].map(rmap["weeks_2025"]), errors="coerce")
    p25 = p[pd.to_numeric(p["season"], errors="coerce") == 2025].copy()
    p25["key"] = p25["full_name_r"].fillna(p25["name_disp"]).astype(str).map(normalize_name)
    p25 = p25.drop_duplicates("key").set_index("key")
    b["fin25"] = b["key"].map(pd.to_numeric(p25["pos_rank_total"], errors="coerce"))
    b["g25"] = b["key"].map(pd.to_numeric(p25["games"], errors="coerce"))
    say(f"  (2025 lookups matched for {int(b['g25'].notna().sum())} of {len(b)} board players)")
    b["posadp"] = pd.to_numeric(b["key"].map(rmap["pos_adp_rank"]), errors="coerce")

    say("  Band rule (28_): `proven at price` is INERT for healthy players and only carries signal")
    say("  for someone coming off a missed-time season — buy if he STILL out-produced his price")
    say("  (73% hit), fade if he didn't (43%). Plus the no-role capital rule where it applies.\n")
    say(f"  {'player':<24}{'pos':<6}{'ADP':>6}  2025            read")
    for r in b.sort_values("adp_rank").itertuples():
        if r.position in ("K", "DEF", "DST"):
            continue
        no_role = (pd.isna(r.share25) or r.share25 < 0.10 or pd.isna(r.wk25) or r.wk25 < 6)
        missed = pd.notna(r.g25) and r.g25 <= 13
        proven = pd.notna(r.fin25) and pd.notna(r.posadp) and r.fin25 <= r.posadp
        st25 = (f"{int(r.g25)}g, {r.position}{int(r.fin25)}"
                if pd.notna(r.g25) and pd.notna(r.fin25) else "rookie/none")
        if no_role:
            # The capital-when-no-role rule FAILED replication (part D): +42pp in R2-3 but -14.0pp
            # here on a bigger sample, and it vanishes entirely at the top-64 threshold in both
            # other bands. So it is NOT applied — saying "capital-backed" here would be advice
            # built on a disproven finding.
            read = ("no 2025 role — capital rule did NOT replicate in this band, so no prereq "
                    "applies; judge on VONA/board")
        elif missed:
            read = ("MISSED TIME + still out-produced price → BUY profile (73%)" if proven
                    else "MISSED TIME + did NOT out-produce price → FADE profile (43%)")
        else:
            read = "healthy w/ a role → prereqs inert here; judge on VONA/board"
        say(f"  {r.full_name:<24}{r.pos_label:<6}{r.adp_rank:>6.1f}  {st25:<15} {read}")


def main():
    p = load()
    part_a(p)
    part_b(p)
    part_c(p)
    part_d(p)
    part_e(p)
    part_f(p)
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
