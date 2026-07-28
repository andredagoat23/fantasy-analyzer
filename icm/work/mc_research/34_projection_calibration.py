"""34 — PROJECTION CALIBRATION: how good are our projection sources, and are they biased BY POSITION?

Why this matters more than ranking accuracy (the user's point, Jul 27): the board is built on POINTS,
not ranks. projections -> custom_scoring -> total_points -> VOLS (points over replacement) -> VONA
(a difference of VOLS). Two players one rank apart can project 70 points apart, and VONA is a
difference of differences, so projection error compounds. ECR/rank enters only as a display column
and the L17 outlier guard.

The killer failure mode is CROSS-POSITION BIAS. If a source over-projects RBs by 15% and WRs by 5%,
every RB-vs-WR VONA comparison on the board is skewed — and you would never see it by checking
ranking accuracy, because within-position ordering can be perfect while the levels are wrong.

Sources tested (all verified PRESEASON, not contaminated — see the injured-player check in each
probe: a genuine preseason projection has CMC at 337 pts in a season he played 4 games):
  * **ESPN** season projections, component stats, scored under the USER'S OWN scoring_config.
  * **Sleeper** season projections (`pts_ppr` + components where present).
  * **ESPN ADP** and **FantasyPros ECR** from the research panel — rank-only, so rank-accuracy only.
  * **The panel's own `exp_pts`** expectation model — our historical analog.

Ground truth = ESPN's ACTUAL component stats for the same season, scored the same way, so projection
and outcome sit on identical footing.

Caveat stated up front: this uses BUCKET-1 base scoring only (scoring_config.SCORING). The Bucket-2
bonuses (long TDs, big games, first downs, sacks) need game-level data we don't have historically.
That applies equally to every source and to the actuals, so comparisons are fair; absolute point
totals will read a little low versus the live board.

Run:  .venv/bin/python icm/work/mc_research/34_projection_calibration.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from scoring_config import SCORING  # noqa: E402
from utils import normalize_name  # noqa: E402

PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_34_calibration.txt")
SEASONS = (2023, 2024, 2025)
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE"}
ESPN_STAT = {"pass_yds": "3", "pass_td": "4", "pass_int": "20", "rush_yds": "24", "rush_td": "25",
             "rec": "53", "rec_yds": "42", "rec_td": "43"}
SLEEPER_STAT = {"pass_yds": "pass_yd", "pass_td": "pass_td", "pass_int": "pass_int",
                "rush_yds": "rush_yd", "rush_td": "rush_td",
                "rec": "rec", "rec_yds": "rec_yd", "rec_td": "rec_td"}

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def score(d, keymap):
    """Base custom scoring (scoring_config.SCORING) over a component dict."""
    tot = 0.0
    for canon, key in keymap.items():
        v = d.get(key)
        if v is not None:
            try:
                tot += float(v) * SCORING.get(canon, 0.0)
            except (TypeError, ValueError):
                pass
    return tot


def espn_season(season):
    """{normalized_name: (position, projected_pts, actual_pts)} — both custom-scored."""
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/players"
    hdr = {"X-Fantasy-Source": "kona", "Accept": "application/json",
           "X-Fantasy-Filter": json.dumps({"players": {"filterActive": {"value": True}, "limit": 900,
                                                       "sortPercOwned": {"sortPriority": 1,
                                                                         "sortAsc": False}}})}
    try:
        d = requests.get(url, params={"view": "kona_player_info", "scoringPeriodId": 0},
                         headers=hdr, timeout=45).json()
    except Exception as e:
        say(f"  ESPN {season}: unreachable ({e})")
        return {}
    players = d["players"] if isinstance(d, dict) else d
    out = {}
    for p in players:
        pl = p.get("player", p)
        pos = POS.get(pl.get("defaultPositionId"))
        nm = pl.get("fullName")
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
        # ESPN returns a projection ROW for many fringe players with an EMPTY stats dict (half of all
        # 2024 QB projection rows had no pass_yds; Logan Woodside's was literally {}). Including
        # those pairs a ~0 projection with a real actual, which craters the mean and can even flip
        # the correlation negative. Require a SUBSTANTIVE projection — and never filter on the
        # actual, which would bias the calibration by conditioning on the outcome.
        if proj and act and any(k in proj for k in ("3", "24", "42", "53")):
            pp, aa = score(proj, ESPN_STAT), score(act, ESPN_STAT)
            if pp > 20:
                out[normalize_name(nm)] = (pos, pp, aa)
    return out


def sleeper_season(season):
    """{normalized_name: (projected_pts, adp_ppr)} — Sleeper also ships ADP, which matters because
    the research panel has NO 2025 ADP (5 of 608 rows), so without it the newest season drops out."""
    try:
        pr = requests.get(f"https://api.sleeper.app/v1/projections/nfl/regular/{season}",
                          timeout=40).json()
        pl = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=45).json()
    except Exception as e:
        say(f"  Sleeper {season}: unreachable ({e})")
        return {}
    name = {pid: p.get("full_name") for pid, p in pl.items() if p.get("full_name")}
    out = {}
    for pid, d in pr.items():
        nm = name.get(pid)
        if not nm:
            continue
        s = score(d, SLEEPER_STAT)
        adp = d.get("adp_ppr")
        adp = float(adp) if adp not in (None, "") and float(adp) < 400 else np.nan
        if s > 20:
            out[normalize_name(nm)] = (s, adp)
    return out


def spearman(a, b):
    return pd.Series(a).rank().corr(pd.Series(b).rank())


def main():
    panel = pd.read_parquet(PANEL)
    for c in ("adp", "ecr_pre", "exp_pts", "total_pts", "season", "games"):
        panel[c] = pd.to_numeric(panel[c], errors="coerce")
    panel["key"] = panel["full_name_r"].fillna(panel["name_disp"]).astype(str).map(normalize_name)

    say("PROJECTION CALIBRATION — sources scored under the league's own scoring_config (base bucket)")
    say(f"seasons: {', '.join(map(str, SEASONS))}\n")

    frames = []
    for season in SEASONS:
        e = espn_season(season)
        s = sleeper_season(season)
        if not e:
            continue
        pan = panel[panel["season"] == season].drop_duplicates("key").set_index("key")
        rows = []
        for k, (pos, proj, act) in e.items():
            sp, sadp = s.get(k, (np.nan, np.nan))
            padp = pan["adp"].get(k, np.nan)
            rows.append({"key": k, "season": season, "pos": pos, "espn_proj": proj, "actual": act,
                         "sleeper_proj": sp, "sleeper_adp": sadp,
                         "adp": padp if pd.notna(padp) else sadp,   # panel ADP, else Sleeper's
                         "ecr": pan["ecr_pre"].get(k, np.nan),
                         "exp_pts": pan["exp_pts"].get(k, np.nan),
                         "games": pan["games"].get(k, np.nan)})
        df = pd.DataFrame(rows)
        frames.append(df)
        say(f"  {season}: {len(df)} ESPN players · Sleeper proj {int(df.sleeper_proj.notna().sum())}"
            f" · ADP {int(df.adp.notna().sum())} · ECR {int(df.ecr.notna().sum())}")
    if not frames:
        say("no data retrieved")
        return
    d = pd.concat(frames, ignore_index=True)

    say("\n" + "=" * 84)
    say("A. RANK ACCURACY — Spearman vs actual finish (drafted players only, ADP<=200)")
    say("=" * 84)
    say("  Rank sources (ADP/ECR) can only be judged here; point sources are judged in B too.")
    drafted = d[d["adp"].notna() & (d["adp"] <= 200)]
    say(f"  {'source':<16}" + "".join(f"{s:>9}" for s in SEASONS) + f"{'all':>9}   n(all)")
    for label, col, invert in [("ESPN proj", "espn_proj", False), ("Sleeper proj", "sleeper_proj", False),
                               ("panel exp_pts", "exp_pts", False), ("ESPN ADP", "adp", True),
                               ("FP ECR", "ecr", True)]:
        cells, tot = "", None
        for season in SEASONS:
            sub = drafted[(drafted["season"] == season) & drafted[col].notna()]
            if len(sub) < 30:
                cells += f"{'—':>9}"
                continue
            r = spearman(sub[col] * (-1 if invert else 1), sub["actual"])
            cells += f"{r:>+9.3f}"
        sub = drafted[drafted[col].notna()]
        tot = spearman(sub[col] * (-1 if invert else 1), sub["actual"]) if len(sub) > 30 else np.nan
        say(f"  {label:<16}{cells}{tot:>+9.3f}{len(sub):>9}")

    say("\n" + "=" * 84)
    say("B. POSITIONAL CALIBRATION — the one that corrupts VONA")
    say("=" * 84)
    say("  ratio = mean(projected) / mean(actual) among drafted players at that position.")
    say("  1.00 = calibrated. The DANGER is the SPREAD between positions: if RB reads 1.20 and WR")
    say("  1.05, every RB-vs-WR VONA comparison on the board is skewed by ~15% even when the")
    say("  within-position ordering is perfect.\n")
    for label, col in [("ESPN projection", "espn_proj"), ("Sleeper projection", "sleeper_proj"),
                       ("panel exp_pts", "exp_pts")]:
        sub = drafted[drafted[col].notna()]
        if len(sub) < 60:
            say(f"  {label}: too few matched ({len(sub)})")
            continue
        say(f"  {label}:")
        say(f"    {'pos':<6}{'n':>5}{'mean proj':>11}{'mean actual':>13}{'ratio':>8}{'MAE':>8}")
        ratios = {}
        for pos in ("QB", "RB", "WR", "TE"):
            g = sub[sub["pos"] == pos]
            if len(g) < 15:
                continue
            ratio = g[col].mean() / g["actual"].mean() if g["actual"].mean() else np.nan
            ratios[pos] = ratio
            say(f"    {pos:<6}{len(g):>5}{g[col].mean():>11.0f}{g['actual'].mean():>13.0f}"
                f"{ratio:>8.2f}{(g[col] - g['actual']).abs().mean():>8.0f}")
        if len(ratios) >= 2:
            spread = max(ratios.values()) - min(ratios.values())
            worst = max(ratios, key=ratios.get)
            best = min(ratios, key=ratios.get)
            say(f"    -> cross-position SPREAD {spread:.2f} "
                f"({worst} most over-projected at {ratios[worst]:.2f}, "
                f"{best} least at {ratios[best]:.2f})"
                + ("  ⚠️ material distortion" if spread >= 0.10 else "  ✅ tight"))
        say("")

    say("=" * 84)
    say("C. DOES A BLEND BEAT EITHER SOURCE ALONE?")
    say("=" * 84)
    both = drafted[drafted["espn_proj"].notna() & drafted["sleeper_proj"].notna()]
    if len(both) >= 60:
        say(f"  n={len(both)} players with both sources")
        say(f"  {'weighting':<22}{'Spearman':>10}{'MAE':>9}")
        for w in (0.0, 0.25, 0.5, 0.65, 0.75, 1.0):
            blend = w * both["espn_proj"] + (1 - w) * both["sleeper_proj"]
            say(f"  {f'{w:.0%} ESPN / {1-w:.0%} Slp':<22}{spearman(blend, both['actual']):>+10.3f}"
                f"{(blend - both['actual']).abs().mean():>9.0f}")
        say("\n  NOTE: this is ESPN-vs-SLEEPER, NOT the live board's ESPN-vs-FantasyPros blend.")
        say("  Historical FantasyPros projections are proprietary and not retrievable, so the")
        say("  shipped 0.35/0.65 FP/ESPN weight still cannot be validated directly. What this DOES")
        say("  show is whether blending two independent sources beats either alone in principle.")
    else:
        say(f"  only {len(both)} players matched both sources — too few")

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
