"""62 — Does the L51 survival curve hold at 2.7x the data?

The shipped `advisor._SCALE_ADP`/`_SCALE_S` (drives VONA, the wheel, the punt read, the lookahead)
was fitted by 43_ on 19,300 picks from 111 one-QB drafts — flagged by the research charter as the
thinnest input in the system. The Jul-31 corpus re-crawl (charter §0.5 exception 2) grew the corpus
to ~300 one-QB / 2,001 total drafts. This re-measures the dispersion on the FULL fattened corpus
with 43_'s exact method and compares the implied logistic scale per bucket against the shipped
anchors. Read-only with respect to 43_ (own cache, own results file).

Decision rule, stated before running: the shipped curve HOLDS if every bucket's newly measured s is
within ±30% of the shipped anchor (the same tolerance the charter's F5 uses for the FFC cross-check).
Any bucket outside that band is a pre-freeze flag, not an auto-edit — advisor.py is 3 days from
freeze and any change is the user's call with the 44_ A/B rerun as the gate.

Run:  .venv/bin/python icm/work/mc_research/62_adp_dispersion_recheck.py
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
SRC = os.path.join(HERE, "sleeper_drafts_2026.jsonl")
CACHE = os.path.join(HERE, "adp_dispersion_cache_v2.json")     # NOT 43_'s cache
OUT = os.path.join(HERE, "results_62_dispersion_recheck.txt")
SLEEP = 0.15

lines = []


def say(s):
    print(s, flush=True)
    lines.append(s)


def collect():
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return json.load(f)
    ids = []
    with open(SRC) as f:
        for line in f:
            r = json.loads(line)
            if r.get("slots_qb") == 1 and not r.get("slots_super_flex"):
                ids.append(r["draft_id"])
    print(f"one-QB drafts in corpus: {len(ids)} (43_ used 111)")
    adp = {}
    pr = requests.get("https://api.sleeper.app/v1/projections/nfl/regular/2026", timeout=45).json()
    for pid, d in pr.items():
        try:
            a = float(d.get("adp_ppr"))
            if 0 < a < 400:
                adp[pid] = a
        except (TypeError, ValueError):
            pass
    rows = []
    for i, did in enumerate(ids):
        try:
            time.sleep(SLEEP)
            picks = requests.get(f"https://api.sleeper.app/v1/draft/{did}/picks", timeout=30).json()
        except requests.RequestException:
            continue
        for p in picks or []:
            pid, no = p.get("player_id"), p.get("pick_no")
            if pid in adp and no:
                rows.append({"adp": adp[pid], "pick": int(no)})
        if (i + 1) % 50 == 0:
            print(f"  fetched {i + 1}/{len(ids)} drafts · {len(rows)} matched picks", flush=True)
    with open(CACHE, "w") as f:
        json.dump(rows, f)
    return rows


def main():
    import advisor  # the shipped anchors — read-only

    rows = collect()
    d = pd.DataFrame(rows)
    d["err"] = d["pick"] - d["adp"]
    say(f"L51 CURVE RECHECK on {len(d)} picks from the fattened corpus "
        f"(43_ fitted on 19,300 picks / 111 drafts)\n")
    say(f"  {'bucket':<12}{'n':>8}{'sd':>8}{'new s':>8}{'shipped s':>11}{'delta':>9}   verdict (±30% band)")
    buckets = [(1, 6), (7, 12), (13, 24), (25, 40), (41, 60), (61, 90), (91, 130), (131, 200)]
    anchors = dict(zip(zip([1, 7, 13, 25, 41, 61, 91, 131], [6, 12, 24, 40, 60, 90, 130, 200]),
                       advisor._SCALE_S))
    holds = True
    for lo, hi in buckets:
        g = d[d["adp"].between(lo, hi)]
        if len(g) < 40:
            say(f"  {f'{lo}-{hi}':<12}{len(g):>8}   (too thin)")
            continue
        s = g["err"].std() * np.sqrt(3) / np.pi
        ship = anchors[(lo, hi)]
        delta = (s - ship) / ship
        ok = abs(delta) <= 0.30
        holds &= ok
        say(f"  {f'{lo}-{hi}':<12}{len(g):>8}{g['err'].std():>8.1f}{s:>8.2f}{ship:>11.2f}{delta:>+9.0%}"
            f"   {'HOLDS' if ok else '<-- OUTSIDE BAND'}")
    say("")
    top = d[d["adp"] <= 6]
    say(f"  ADP<=6 lasting to pick 24+: {(top['pick'] >= 24).mean():.2%} "
        f"(L51's motivating number was ~0.5% real vs 4.1% under the old constant scale)")
    say(f"\nVERDICT: the shipped curve {'HOLDS at 2.7x the data — L51 independently confirmed, '
        'no pre-freeze action needed' if holds else 'has at least one bucket OUTSIDE the ±30% band '
        '— flag to the user BEFORE the Aug 3 freeze; the fix is a constants change gated by a 44_ rerun'}")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
