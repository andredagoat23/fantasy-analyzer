"""43 — How much does a player's ACTUAL draft slot vary around his ADP, by ADP level?

The bug this exists to settle (user's catch, Jul 28): drafting from slot 1, VONA goes NEGATIVE at
around ADP 12 even though the next pick is #24 — i.e. the model says "waiting beats taking him" for
players who will almost certainly be gone. Traced to `advisor._survival_prob`, which uses a single
logistic with a CONSTANT scale (`_ADP_SCALE = 7.0`) across the entire board.

That constant gives Jahmyr Gibbs (ADP 1.6) a **3.9%** chance of lasting to pick 24, and a 23% chance
that one of the top-4 RBs falls that far. Those branches carry VOLS of 138-198, which drags the
expected-best-survivor (`best_wait`) up to 119 — above Achane's own 112 — so Achane prices at VONA
−7. The math is self-consistent; the input is wrong.

Real ADP noise is obviously not constant: the consensus #1 goes 1-3 essentially every time, while an
ADP-100 player routinely swings 20+ picks. This measures the true dispersion on real drafts so any
fix is fitted to data rather than intuition.

Method: re-fetch picks for the 111 one-QB 12-team drafts already discovered by 21_ (their draft_ids
are on disk; only the player_id was not stored), join each pick to Sleeper's own `adp_ppr`, and
measure the spread of (actual pick − ADP) in ADP buckets.

Run:  .venv/bin/python icm/work/mc_research/43_adp_dispersion.py
"""
import json
import os
import time

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sleeper_drafts_2026.jsonl")
CACHE = os.path.join(HERE, "adp_dispersion_cache.json")
OUT = os.path.join(HERE, "results_43_adp_dispersion.txt")
SLEEP = 0.15
MAX_DRAFTS = 111

lines = []


def say(s):
    print(s)
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
    ids = ids[:MAX_DRAFTS]
    adp = {}
    pr = requests.get("https://api.sleeper.app/v1/projections/nfl/regular/2026", timeout=45).json()
    for pid, d in pr.items():
        a = d.get("adp_ppr")
        try:
            a = float(a)
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
        if (i + 1) % 25 == 0:
            print(f"  fetched {i + 1}/{len(ids)} drafts · {len(rows)} matched picks")
    with open(CACHE, "w") as f:
        json.dump(rows, f)
    return rows


def main():
    rows = collect()
    d = pd.DataFrame(rows)
    d["err"] = d["pick"] - d["adp"]
    say(f"ADP DISPERSION on {len(d)} real picks from up to {MAX_DRAFTS} one-QB 12-team drafts\n")
    say("The model assumes ONE logistic scale of 7.0 picks everywhere. A logistic's scale s relates")
    say("to its standard deviation by sd = s*pi/sqrt(3) ~= 1.81*s, so s=7 implies sd ~= 12.7 picks")
    say("at EVERY point on the board. Measured instead:\n")
    say(f"  {'ADP bucket':<14}{'n':>7}{'mean err':>10}{'sd':>8}{'implied s':>11}   vs model s=7.0")
    buckets = [(1, 6), (7, 12), (13, 24), (25, 40), (41, 60), (61, 90), (91, 130), (131, 200)]
    fit = []
    for lo, hi in buckets:
        g = d[d["adp"].between(lo, hi)]
        if len(g) < 40:
            continue
        sd = g["err"].std()
        s = sd * np.sqrt(3) / np.pi
        fit.append((lo, hi, len(g), g["err"].mean(), sd, s))
        flag = "  <-- model FAR too wide" if s < 4 else ("  <-- model too narrow" if s > 10 else "")
        say(f"  {f'{lo}-{hi}':<14}{len(g):>7}{g['err'].mean():>+10.1f}{sd:>8.1f}{s:>11.1f}{flag}")

    say("\nWHAT THIS MEANS FOR THE TOP OF THE BOARD:")
    top = d[d["adp"] <= 6]
    if len(top) >= 40:
        say(f"  players with ADP <= 6 went at pick <= 12 in {(top['pick'] <= 12).mean():.1%} of drafts")
        say(f"  they lasted to pick 24 or later in {(top['pick'] >= 24).mean():.1%}")
        s_top = top['err'].std() * np.sqrt(3) / np.pi
        # what the CURRENT model claims for an ADP-2 player surviving to 24
        import math
        model_p = 1 / (1 + math.exp(-(2 - 24) / 7.0))
        say(f"  the model claims an ADP-2 player lasts to 24 with p={model_p:.1%}; measured "
            f"{(top['pick'] >= 24).mean():.1%}")
        say(f"  measured scale up there is ~{s_top:.1f}, not 7.0")

    say("\nPROPOSED SHAPE (fitted, not intuited):")
    if fit:
        xs = np.array([(lo + hi) / 2 for lo, hi, *_ in fit])
        ys = np.array([f[5] for f in fit])
        a, bb = np.polyfit(np.log(xs), ys, 1)
        say(f"  scale grows roughly with log(ADP):  s(adp) ~= {a:.2f}*ln(adp) + {bb:.2f}")
        for adp in (2, 6, 12, 24, 50, 100, 180):
            say(f"     ADP {adp:>4} -> s ~= {max(a * np.log(adp) + bb, 0.5):.1f}"
                f"   (model currently uses 7.0 everywhere)")
    say("\nNOTE: changing _ADP_SCALE moves EVERY VONA on the board — it is the most load-bearing knob")
    say("in the advisor. Any change needs the paired-draft backtest before it ships, and the code")
    say("freeze is Aug 3.")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
