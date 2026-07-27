"""27 — Apply the STRESS-TESTED band prerequisites to the real 2026 board, pick by pick (slot 7).

25_ stress-tested the round-1 prereqs (bootstrap + 12-setting grid) and 26_ found the conditions
that actually hold CHANGE by round band. This turns that into the thing the user can study before
Aug 7: for each of his 16 picks at slot 7, the players realistically in range, screened on the
condition that is ROBUST for THAT band — not a one-size-fits-all checklist.

Band screens (only conditions that passed 26_'s bootstrap-P >= .90 AND >= 75% of the grid):
  R1    ADP 1-15    -> receiving involvement (wopr proxy: target share vs position median)
  R2-3  ADP 16-40   -> NFL draft capital, top-64
  R4-6  ADP 41-75   -> PROVEN AT PRICE (2025 positional finish at least as good as 2026 positional
                       price) — the single strongest result in the study (+10.4pp, P=0.97, 9/9)
  R7-10 ADP 76-125  -> draft capital top-32 + receiving involvement + played 15+ games in 2025

Deliberately NOT applied outside its band: `proven_at_price` is ROBUST at R4-6 but DEAD in round 1
(survived 1 of 12 settings there), and `durable_prev` is DEAD in round 1 but ROBUST at R7-10. Using
one checklist everywhere is precisely the mistake this script exists to avoid.

Run:  .venv/bin/python icm/work/mc_research/27_2026_band_screen.py
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
OUT = os.path.join(HERE, "results_27_2026_screen.txt")

SLOT, TEAMS, ROUNDS = 7, 12, 16
WINDOW = 6          # show players within +/- this many ADP slots of the pick

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def band_of(adp):
    if adp <= 15:
        return "R1"
    if adp <= 40:
        return "R2-3"
    if adp <= 75:
        return "R4-6"
    if adp <= 125:
        return "R7-10"
    return "late"


def main():
    b = pd.read_csv(os.path.join(ROOT, "value_board.csv"))
    b["position"] = b["pos_label"].str.replace(r"\d+$", "", regex=True)
    b = b[b["adp_rank"].notna()].copy()
    b["key"] = b["full_name"].map(normalize_name)

    role = pd.read_csv(os.path.join(ROOT, "role_data.csv"))
    role["key"] = role["name"].map(normalize_name)
    rmap = role.drop_duplicates("key").set_index("key")

    p = pd.read_parquet(PANEL)
    for c in ("games", "pos_rank_total", "season"):
        p[c] = pd.to_numeric(p[c], errors="coerce")
    p25 = p[p["season"] == 2025].copy()
    p25["key"] = p25["full_name_r"].fillna(p25["name_disp"]).astype(str).map(normalize_name)
    p25 = p25.drop_duplicates("key").set_index("key")
    fin25, g25 = p25["pos_rank_total"], p25["games"]

    # position-median target share on the board = the receiving-involvement bar
    tsmed = b.groupby("position")["target_share_2025"].transform("median")
    b["ts_ok"] = b["target_share_2025"].fillna(0) >= tsmed.fillna(0)
    b["cap_pick"] = b["key"].map(rmap["nfl_pick"]) if "nfl_pick" in rmap.columns else np.nan
    b["cap_pick"] = pd.to_numeric(b["cap_pick"], errors="coerce").fillna(
        pd.to_numeric(b.get("draft_pick"), errors="coerce"))
    b["posadp"] = pd.to_numeric(b["key"].map(rmap["pos_adp_rank"]), errors="coerce")
    b["fin25c"] = b["key"].map(fin25)
    b["g25c"] = b["key"].map(g25)

    def screen(r):
        """(passes, human-readable status) for the band-appropriate ROBUST condition(s)."""
        band = band_of(r.adp_rank)
        # K/DEF are streamers — the STREAMER/DART logic owns them, and none of these conditions were
        # derived on them. And the receiving-involvement test is meaningless for a QB, so it is
        # simply not applied there rather than silently passing him on a 0% target share.
        if r.position in ("K", "DEF", "DST"):
            return True, "streamer — not screened"
        recv_ok = r.position in ("RB", "WR", "TE")
        if band == "R1":
            if not recv_ok:
                return True, "recv test n/a for QB"
            ok = bool(r.ts_ok)
            lab = (f"recv role {r.target_share_2025:.0%}"
                   if pd.notna(r.target_share_2025) else "no tgt data")
            return ok, lab
        if band == "R2-3":
            ok = pd.notna(r.cap_pick) and r.cap_pick <= 64
            return ok, (f"NFL #{int(r.cap_pick)}" if pd.notna(r.cap_pick) else "no capital")
        if band == "R4-6":
            ok = pd.notna(r.fin25c) and pd.notna(r.posadp) and r.fin25c <= r.posadp
            return ok, (f"2025 {r.position}{int(r.fin25c)} vs priced {r.position}{int(r.posadp)}"
                        if pd.notna(r.fin25c) and pd.notna(r.posadp) else "no 2025 finish")
        if band == "R7-10":
            cap = pd.notna(r.cap_pick) and r.cap_pick <= 32
            dur = pd.notna(r.g25c) and r.g25c >= 15
            parts = [("cap", cap), ("dur", dur)]
            if recv_ok:
                parts.insert(1, ("recv", bool(r.ts_ok)))
            n, tot = sum(v for _, v in parts), len(parts)
            lab = " ".join(f"{k}{'✓' if v else '✗'}" for k, v in parts)
            return n >= (tot + 1) // 2, f"{lab} ({n}/{tot})"
        return True, "late — DART READ owns this"

    picks = [((r - 1) * TEAMS + SLOT) if r % 2 else (r * TEAMS - SLOT + 1)
             for r in range(1, ROUNDS + 1)]
    say(f"SLOT {SLOT} of {TEAMS} · picks: {', '.join(map(str, picks))}")
    say("Screened on the condition that is ROBUST for each pick's BAND (see 26_). PASS/FAIL is a")
    say("tie-breaker among comparable players — it never outranks VONA, the board, or your plan.\n")

    for pk in picks:
        band = band_of(pk)
        if band == "late":
            say(f"\n### Pick #{pk} — beyond ADP 125: the validated DART READ playbook owns this range")
            continue
        pool = b[(b["adp_rank"] >= pk - WINDOW) & (b["adp_rank"] <= pk + WINDOW)]
        pool = pool.sort_values("adp_rank")
        if not len(pool):
            continue
        # NOTE: each player is screened on HIS OWN ADP band (the research is ADP-band based), so a
        # window straddling a band edge legitimately applies two different screens. The band is
        # printed per row so it's never ambiguous which condition was tested.
        say(f"\n### Pick #{pk}  (mostly {band})")
        for r in pool.itertuples():
            ok, why = screen(r)
            say(f"   {'PASS' if ok else 'fail'}  {r.full_name:<24}{r.pos_label:<5}"
                f"ADP {r.adp_rank:>5.1f}  [{band_of(r.adp_rank):<5}] {why}")

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
