"""Archive this season's PRESEASON projections + prices, so next year they can be scored honestly.

Why this exists: the single most load-bearing constant in the board is the FP/ESPN blend weight
(`scoring_config.PROJ_W_FP` / `PROJ_W_ESPN`), and it was chosen by judgment, not measurement. It
cannot be validated retrospectively because **we never kept a copy of past projections** —
FantasyPros is proprietary and paywalled, so no archive can be reconstructed after the fact
(verified: data/FantasyPros_*.csv are current-season only, the FP API returns 403, and nothing exists
in git history). ESPN and Sleeper serve some history but Sleeper's older seasons turn out to be
backfilled rather than genuine forecasts (see icm/work/mc_research/38_).

So the fix is to stop losing the data. Run this ONCE per preseason, before the draft, and by the
following January you can score every source against real outcomes and set the weight from evidence.
Research showing why this matters: projection accuracy is worth roughly 130-200 roster points per
+0.05 Spearman (mc_research/36_) — far and away the biggest lever measured in this project.

What it captures, per player per source: the raw component stats (so it can be RE-SCORED later under
any scoring rules, including if the league's settings change), the points under today's
scoring_config, and BOTH available preseason prices (ESPN ADP from the board, Sleeper ADP). Price is
essential — without it you can measure accuracy but not value-over-price.

Writes a DATED file and never overwrites: an archive you can silently clobber is not an archive.

Run:  .venv/bin/python tools/archive_projections.py
"""
import datetime
import os
import sys

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import projections
from scoring_config import SCORING
from utils import normalize_name

ARCHIVE_DIR = os.path.join("data", "projection_archive")
SEASON = 2026
COMPONENTS = ["pass_yds", "pass_td", "pass_int", "pass_att", "rush_yds", "rush_td", "rush_att",
              "rec", "rec_yds", "rec_td", "fumbles_lost"]
SL_STAT = {"pass_yds": "pass_yd", "pass_td": "pass_td", "pass_int": "pass_int",
           "pass_att": "pass_att", "rush_yds": "rush_yd", "rush_td": "rush_td",
           "rush_att": "rush_att", "rec": "rec", "rec_yds": "rec_yd", "rec_td": "rec_td",
           "fumbles_lost": "fum_lost"}


def score(df):
    t = np.zeros(len(df))
    for canon, val in SCORING.items():
        if canon in df.columns:
            t += pd.to_numeric(df[canon], errors="coerce").fillna(0).to_numpy() * val
    return t


def tidy(df, source):
    out = pd.DataFrame({"source": source, "full_name": df["full_name"],
                        "position": df.get("position", "")})
    for c in COMPONENTS:
        out[c] = pd.to_numeric(df[c], errors="coerce") if c in df.columns else np.nan
    out["pts_scoring_config"] = score(df)
    out["key"] = out["full_name"].map(normalize_name)
    return out


def main():
    frames = []

    fp = projections._fp_components().copy()
    frames.append(tidy(fp, "fantasypros"))
    print(f"  FantasyPros: {len(fp)} players")

    try:
        espn, _ = projections._espn_components()
        frames.append(tidy(espn.copy(), "espn"))
        print(f"  ESPN:        {len(espn)} players")
    except Exception as e:
        print(f"  ESPN: SKIPPED ({e})")

    try:
        raw = requests.get(f"https://api.sleeper.app/v1/projections/nfl/regular/{SEASON}",
                           timeout=45).json()
        pls = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60).json()
        rows = []
        for pid, d in raw.items():
            p = pls.get(pid) or {}
            nm, pos = p.get("full_name"), (p.get("position") or "")
            if not nm or pos not in ("QB", "RB", "WR", "TE", "K"):
                continue
            r = {"full_name": nm, "position": pos}
            got = False
            for canon, key in SL_STAT.items():
                v = d.get(key)
                if v not in (None, ""):
                    r[canon] = float(v)
                    got = True
            if got:
                rows.append(r)
        sl = pd.DataFrame(rows)
        # a name can map to several Sleeper ids (inactive dupes) — keep the real projection
        sl = sl.assign(_p=score(sl)).sort_values("_p", ascending=False)
        sl = sl.drop_duplicates("full_name").drop(columns="_p")
        frames.append(tidy(sl, "sleeper"))
        print(f"  Sleeper:     {len(sl)} players")
    except Exception as e:
        print(f"  Sleeper: SKIPPED ({e})")

    arch = pd.concat(frames, ignore_index=True)

    # --- prices: without these you can measure accuracy but never value-over-price ---
    try:
        board = pd.read_csv("value_board.csv")
        board["key"] = board["full_name"].map(normalize_name)
        adp = board.drop_duplicates("key").set_index("key")["adp_rank"]
        arch["adp_espn"] = arch["key"].map(adp)
        print(f"  ESPN ADP attached for {int(arch['adp_espn'].notna().sum())} rows")
    except Exception as e:
        arch["adp_espn"] = np.nan
        print(f"  ESPN ADP: SKIPPED ({e})")
    try:
        sadp = {}
        for pid, d in raw.items():
            p = pls.get(pid) or {}
            nm, a = p.get("full_name"), d.get("adp_ppr")
            if nm and a not in (None, "") and 0 < float(a) < 400:
                sadp[normalize_name(nm)] = float(a)
        arch["adp_sleeper"] = arch["key"].map(sadp)
        print(f"  Sleeper ADP attached for {int(arch['adp_sleeper'].notna().sum())} rows")
    except Exception:
        arch["adp_sleeper"] = np.nan

    arch["season"] = SEASON
    arch["archived_at"] = datetime.date.today().isoformat()

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    path = os.path.join(ARCHIVE_DIR, f"{SEASON}_preseason_{arch['archived_at'].iloc[0]}.csv")
    if os.path.exists(path):
        print(f"\n⚠️  {path} already exists — NOT overwriting. Delete it first if you really mean to.")
        return 1
    arch.to_csv(path, index=False)
    print(f"\nwrote {path}  ({len(arch)} rows, {arch['source'].nunique()} sources)")
    print(arch.groupby("source").agg(players=("full_name", "size"),
                                     mean_pts=("pts_scoring_config", "mean")).round(1).to_string())
    print("\nNEXT JANUARY: pull the real 2026 outcomes (nflreadpy), join on `key`, and score each")
    print("source on accuracy AND value-over-price. That finally sets PROJ_W_FP / PROJ_W_ESPN from")
    print("evidence rather than judgment — see icm/work/mc_research/34_ and 36_ for the method.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
