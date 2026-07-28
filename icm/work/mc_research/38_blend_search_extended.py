"""38 — The blend question, answered on SIX seasons instead of two.

37_ swept every ESPN/Sleeper weight on 2024-25 and found the two seasons picked opposite ends of the
range, so no weight was trustworthy. The correct response to n=2 is not a cleverer fit — it is more
data. ESPN's endpoint serves projections back to 2019, and Sleeper's does too.

Sample notes (measured, not assumed):
  * 2019-2022, 2024, 2025 each yield ~475-490 players with a substantive ESPN projection AND actuals.
  * **2023 is an ESPN data quirk** — only ~100 usable, versus ~480 every other year. The same
    extraction works fine for six other seasons, so it is included but flagged, never load-bearing.
  * Sleeper has no ADP for 2019, so the DRAFT BACKTEST uses 2020-2025; the accuracy comparison uses
    every season where ADP resolves (panel ADP first, Sleeper ADP as fallback).

The question n=6 can finally answer: is one source CONSISTENTLY better, or does the winner flip? If
it flips, no fixed weight is justifiable and the honest answer is to leave scoring_config alone.

Validation is leave-one-season-out: fit the weight on all other seasons, evaluate on the held-out
one. That is the only honest way to ask "would this weight have helped in a season we didn't tune on".

Run:  .venv/bin/python icm/work/mc_research/38_blend_search_extended.py
"""
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from scoring_config import SCORING  # noqa: E402
from utils import normalize_name  # noqa: E402

_spec = importlib.util.spec_from_file_location("wb", os.path.join(HERE, "35_wr_bias_backtest.py"))
wb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wb)

OUT = os.path.join(HERE, "results_38_blend_extended.txt")
CACHE = os.path.join(HERE, "blend_cache_2019_2025.json")
PANEL = os.path.join(HERE, "seasons_exp.parquet")
SEASONS = (2019, 2020, 2021, 2022, 2023, 2024, 2025)
SMALL = {2023}                       # ESPN data quirk — kept but never load-bearing
# SLEEPER'S 2019-2020 PROJECTIONS ARE CONTAMINATED — verified, not assumed. The injured-player test
# is decisive: in clean seasons a player who missed time is projected 2-3x what he scored (2021:
# 91 vs 35, 2022: 76 vs 35, 2024: 74 vs 38). In 2019-20 the "projection" essentially EQUALS the
# actual (53 vs 50, 61 vs 57), and proj-vs-actual correlation is 0.95-0.96 versus 0.74-0.83
# elsewhere. Those are backfilled, not forecasts. They inflated Sleeper's apparent accuracy to
# 0.959/0.965 and contributed two of the largest gains before exclusion.
CONTAMINATED = {2019, 2020}
BACKTEST_W = (0.0, 0.25, 0.5, 0.75, 1.0)
GRID_W = [round(x, 2) for x in np.arange(0, 1.01, 0.1)]
N_DRAFTS = 150
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE"}
ESPN_STAT = {"pass_yds": "3", "pass_td": "4", "pass_int": "20", "rush_yds": "24", "rush_td": "25",
             "rec": "53", "rec_yds": "42", "rec_td": "43"}
SL_STAT = {"pass_yds": "pass_yd", "pass_td": "pass_td", "pass_int": "pass_int",
           "rush_yds": "rush_yd", "rush_td": "rush_td",
           "rec": "rec", "rec_yds": "rec_yd", "rec_td": "rec_td"}

lines = []


def say(s):
    print(s)
    lines.append(s)


def sc(d, keymap):
    t = 0.0
    for canon, key in keymap.items():
        v = d.get(key)
        if v is not None:
            try:
                t += float(v) * SCORING.get(canon, 0.0)
            except (TypeError, ValueError):
                pass
    return t


def fetch():
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return {int(k): v for k, v in json.load(f).items()}
    panel = pd.read_parquet(PANEL)
    panel["adp"] = pd.to_numeric(panel["adp"], errors="coerce")
    panel["season"] = pd.to_numeric(panel["season"], errors="coerce")
    panel["key"] = panel["full_name_r"].fillna(panel["name_disp"]).astype(str).map(normalize_name)
    sl_players = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60).json()
    sl_name = {pid: p.get("full_name") for pid, p in sl_players.items() if p.get("full_name")}
    out = {}
    for season in SEASONS:
        url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/players"
        hdr = {"X-Fantasy-Source": "kona", "Accept": "application/json",
               "X-Fantasy-Filter": json.dumps({"players": {"filterActive": {"value": True},
                                                           "limit": 900,
                                                           "sortPercOwned": {"sortPriority": 1,
                                                                             "sortAsc": False}}})}
        d = requests.get(url, params={"view": "kona_player_info", "scoringPeriodId": 0},
                         headers=hdr, timeout=60).json()
        players = d["players"] if isinstance(d, dict) else d
        sp = requests.get(f"https://api.sleeper.app/v1/projections/nfl/regular/{season}",
                          timeout=45).json()
        sl, sl_adp = {}, {}
        for pid, row in sp.items():
            nm = sl_name.get(pid)
            if not nm:
                continue
            k = normalize_name(nm)
            v = sc(row, SL_STAT)
            if v > 20:
                sl[k] = v
            a = row.get("adp_ppr")
            try:
                a = float(a)
                if 0 < a < 400:
                    sl_adp[k] = a
            except (TypeError, ValueError):
                pass
        pan = panel[panel["season"] == season].drop_duplicates("key").set_index("key")["adp"]
        rows = []
        for p in players:
            pl = p.get("player", p)
            pos, nm = POS.get(pl.get("defaultPositionId")), pl.get("fullName")
            if not pos or not nm:
                continue
            proj = act = None
            for s in pl.get("stats", []) or []:
                if s.get("seasonId") != season or s.get("statSplitTypeId") != 0:
                    continue
                if s.get("statSourceId") == 1:
                    proj = s.get("stats", {})
                elif s.get("statSourceId") == 0:
                    act = s.get("stats", {})
            if not (proj and act and any(k in proj for k in ("3", "24", "42", "53"))):
                continue
            k = normalize_name(nm)
            pp = sc(proj, ESPN_STAT)
            if pp <= 20 or k not in sl:
                continue
            adp = pan.get(k)
            if adp is None or not np.isfinite(adp):
                adp = sl_adp.get(k)
            if adp is None:
                continue
            rows.append({"name": nm, "pos": pos, "espn": pp, "sleeper": sl[k],
                         "actual": sc(act, ESPN_STAT), "adp": float(adp)})
        out[season] = rows
        print(f"  {season}: {len(rows)} players with ESPN + Sleeper + ADP + actual")
    with open(CACHE, "w") as f:
        json.dump({str(k): v for k, v in out.items()}, f)
    return out


def prep(rows):
    df = pd.DataFrame(rows)
    df = df[df["adp"] <= 220].reset_index(drop=True)
    for c in ("espn", "sleeper"):
        df[c + "_s"] = df[c] * (df["actual"].mean() / df[c].mean())
    return df


def rho_at(df, w):
    b = w * df["espn_s"] + (1 - w) * df["sleeper_s"]
    return b.rank().corr(df["actual"].rank())


def pts_at(df, w, n=N_DRAFTS):
    d = df.copy()
    d["blend"] = w * d["espn_s"] + (1 - w) * d["sleeper_s"]
    d["v"] = wb.vols(d, "blend")
    return float(np.mean([wb.simulate(d, np.random.default_rng(5500 + i), "v") for i in range(n)]))


def main():
    say("BLEND SEARCH ON SIX SEASONS — is one source CONSISTENTLY better, or does the winner flip?")
    say("  w = weight on ESPN; remainder to Sleeper. Live board is 65% ESPN (against FantasyPros).\n")
    data = fetch()
    dfs = {s: prep(v) for s, v in data.items() if len(v) >= 60 and s not in CONTAMINATED}
    say(f"  EXCLUDED {sorted(CONTAMINATED)} — Sleeper's projections there are backfilled, not")
    say("  forecasts (injured players projected ~= what they actually scored; see header).")
    for s in sorted(dfs):
        flag = "   ⚠️ ESPN data quirk — small, not load-bearing" if s in SMALL else ""
        say(f"  {s}: n={len(dfs[s])}{flag}")

    say("\n" + "=" * 76)
    say("A. WHICH SOURCE IS BETTER, SEASON BY SEASON? (Spearman vs actual finish)")
    say("=" * 76)
    say(f"  {'season':<9}{'ESPN':>9}{'Sleeper':>10}{'winner':>10}{'gap':>9}")
    wins = {"ESPN": 0, "Sleeper": 0}
    for s in sorted(dfs):
        e, k = rho_at(dfs[s], 1.0), rho_at(dfs[s], 0.0)
        w = "ESPN" if e > k else "Sleeper"
        if s not in SMALL:
            wins[w] += 1
        say(f"  {s:<9}{e:>9.3f}{k:>10.3f}{w:>10}{abs(e - k):>9.3f}"
            + ("   (small sample)" if s in SMALL else ""))
    say(f"\n  Excluding the small 2023 sample: ESPN wins {wins['ESPN']}, Sleeper wins {wins['Sleeper']}.")
    say("  If this splits roughly evenly, NO fixed weight is defensible — that is the whole question.")

    say("\n" + "=" * 76)
    say("B. ACCURACY BY WEIGHT, PER SEASON (Spearman)")
    say("=" * 76)
    say(f"  {'season':<9}" + "".join(f"{w:>7.1f}" for w in GRID_W) + f"{'best w':>9}")
    best_by_season = {}
    for s in sorted(dfs):
        rr = [rho_at(dfs[s], w) for w in GRID_W]
        bw = GRID_W[int(np.argmax(rr))]
        best_by_season[s] = bw
        say(f"  {s:<9}" + "".join(f"{r:>7.3f}" for r in rr) + f"{bw:>9.1f}")
    big = [s for s in sorted(dfs) if s not in SMALL]
    say(f"\n  best weight per season: " + ", ".join(f"{s}:{best_by_season[s]:.1f}" for s in big))
    spread = max(best_by_season[s] for s in big) - min(best_by_season[s] for s in big)
    say(f"  spread across seasons: {spread:.1f}"
        + ("  -> unstable; a fixed weight is fitting noise" if spread >= 0.5 else "  -> reasonably stable"))

    say("\n" + "=" * 76)
    say("C. DRAFT BACKTEST BY WEIGHT (roster points, actual season scoring)")
    say("=" * 76)
    say(f"  {'season':<9}" + "".join(f"{w:>9.2f}" for w in BACKTEST_W) + f"{'best':>8}")
    pts = {}
    for s in sorted(dfs):
        row = [pts_at(dfs[s], w) for w in BACKTEST_W]
        pts[s] = row
        say(f"  {s:<9}" + "".join(f"{p:>9.0f}" for p in row)
            + f"{BACKTEST_W[int(np.argmax(row))]:>8.2f}")

    say("\n" + "=" * 76)
    say("D. LEAVE-ONE-SEASON-OUT — fit the weight elsewhere, apply it to the held-out season")
    say("=" * 76)
    say(f"  {'held out':<10}{'fitted w':>10}{'pts at w':>10}{'pts at 0.75':>13}{'gain':>8}")
    gains = []
    for s in big:
        others = [t for t in big if t != s]
        avg = [np.mean([pts[t][i] for t in others]) for i in range(len(BACKTEST_W))]
        fw = BACKTEST_W[int(np.argmax(avg))]
        i_f = BACKTEST_W.index(fw)
        i_ref = BACKTEST_W.index(0.75)          # nearest grid point to our live 0.65 ESPN weight
        g = pts[s][i_f] - pts[s][i_ref]
        gains.append(g)
        say(f"  {s:<10}{fw:>10.2f}{pts[s][i_f]:>10.0f}{pts[s][i_ref]:>13.0f}{g:>+8.0f}")
    say(f"\n  mean out-of-sample gain vs our current weighting: {np.mean(gains):+.0f} pts "
        f"(helped in {sum(1 for g in gains if g > 0)}/{len(gains)} seasons)")
    say("\n  VERDICT: " + (
        f"a reweighting generalises — {np.mean(gains):+.0f} pts held out, "
        f"{sum(1 for g in gains if g > 0)}/{len(gains)} seasons."
        if np.mean(gains) > 20 and sum(1 for g in gains if g > 0) >= len(gains) * 0.7 else
        f"NO generalisable reweighting — {np.mean(gains):+.0f} pts held out, helping in only "
        f"{sum(1 for g in gains if g > 0)}/{len(gains)} seasons. Leave scoring_config alone."))
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
