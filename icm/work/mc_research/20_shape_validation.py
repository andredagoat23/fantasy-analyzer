"""Validate the advisor's POSITION-SHAPE advisories against 13 seasons of REAL ADP + finishes.

Shape only needs ADP (draft cost) + actual finish — both REAL (no value proxy). Full pool (all rounds,
incl rookies), 2012-2024. For each position, by ADP ROUND: startable hit-rate, bust-rate, and mean
positional finish — the "value curve." Then it checks the three specific claims the advisor makes:
  TE  — top-heavy: elite tier, then an R4-5 DEAD ZONE, then an ~R6 value POCKET.
  QB  — deep: an elite (R1-3) QB gives ~no edge over a mid (R7-9) QB.
  WR  — thin/risky: reliable tier runs out FAST (by ~WR10) vs RB staying reliable to ~RB20+; WR busts more.

Run:  .venv/bin/python icm/work/mc_research/20_shape_validation.py   (slow first run: FFC + nflverse; caches)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import numpy as np
import pandas as pd
import requests
import nflreadpy as nfl

from utils import normalize_name
from scoring_config import SCORING

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "20_shape_cache.csv")
SEASONS = list(range(2012, 2025))
POS = ["QB", "RB", "WR", "TE"]
STARTERS = {"QB": 12, "RB": 30, "WR": 42, "TE": 12}   # ~league-wide starters incl flex (12-team)
NFL_COL = {"pass_yds": "passing_yards", "pass_td": "passing_tds", "pass_int": "passing_interceptions",
           "rush_yds": "rushing_yards", "rush_td": "rushing_tds", "rec": "receptions",
           "rec_yds": "receiving_yards", "rec_td": "receiving_tds"}


def base_points(df):
    pts = pd.Series(0.0, index=df.index)
    for k, col in NFL_COL.items():
        if k in SCORING and col in df.columns:
            pts = pts + df[col].fillna(0) * SCORING[k]
    return pts


def finish(year):
    wk = nfl.load_player_stats(seasons=[year]).to_pandas()
    wk = wk[(wk["season_type"] == "REG") & (wk["position"].isin(POS))].copy()
    wk["pts"] = base_points(wk)
    nm = "player_display_name" if "player_display_name" in wk.columns else "player_id"
    tot = wk.groupby([nm, "position"])["pts"].sum().reset_index().rename(columns={nm: "name"})
    tot["fin_rank"] = tot.groupby("position")["pts"].rank(ascending=False, method="min")   # 1 = best at pos
    tot["norm"] = tot["name"].apply(normalize_name)
    return tot


def ffc(year):
    pl = []
    for _ in range(4):
        try:
            time.sleep(1.3)
            pl = requests.get("https://fantasyfootballcalculator.com/api/v1/adp/ppr",
                              params={"teams": 12, "year": year}, timeout=20).json().get("players", [])
            if pl:
                break
        except Exception:
            pass
    return pd.DataFrame([{"norm": normalize_name(p["name"]), "position": p["position"], "adp": p["adp"]}
                        for p in pl], columns=["norm", "position", "adp"])


if os.path.exists(CACHE):
    d = pd.read_csv(CACHE)
else:
    rows = []
    for y in SEASONS:
        a = ffc(y)
        if a.empty:
            print(f"  {y}: no ADP"); continue
        f = finish(y)
        m = a[a.position.isin(POS)].merge(f[["norm", "position", "fin_rank"]], on=["norm", "position"], how="left")
        m["season"] = y; rows.append(m); print(f"  {y}: {len(m)} drafted, {m.fin_rank.notna().sum()} with a finish")
    d = pd.concat(rows, ignore_index=True)
    d.to_csv(CACHE, index=False)
    print(f"cached {len(d)} rows")

d["rd"] = np.ceil(d["adp"] / 12).astype(int)             # draft round (12-team)
d["startable"] = (d["fin_rank"] <= d["position"].map(STARTERS)).astype(float)
d["bust"] = ((d["fin_rank"].isna()) | (d["fin_rank"] > 2 * d["position"].map(STARTERS))).astype(float)

print("\n=== value curve by position x round (startable% / bust% / median finish rank; n) ===")
for p in POS:
    sub = d[d.position == p]
    print(f"\n{p} (startable = finish top-{STARTERS[p]}):")
    for rd in range(1, 13):
        g = sub[sub.rd == rd]
        if len(g) < 5:
            continue
        med = g["fin_rank"].median()
        print(f"  R{rd:<2} n={len(g):3d}  startable {g.startable.mean():4.0%}  bust {g.bust.mean():4.0%}  median finish {p}{med:.0f}" if pd.notna(med)
              else f"  R{rd:<2} n={len(g):3d}  startable {g.startable.mean():4.0%}  bust {g.bust.mean():4.0%}")

# ---- claim checks ----
def rd_startable(p, rds):
    g = d[(d.position == p) & (d.rd.isin(rds))]
    return g.startable.mean(), g.bust.mean(), len(g)

print("\n=== CLAIM CHECKS ===")
# TE: elite (R1-3) vs dead zone (R4-5) vs pocket (R6-7)
for lab, rds in [("TE elite R1-3", [1, 2, 3]), ("TE dead R4-5", [4, 5]), ("TE pocket R6-7", [6, 7])]:
    s, b, n = rd_startable("TE", rds); print(f"  {lab:16}: startable {s:.0%}  bust {b:.0%}  (n={n})")
# QB: elite R1-4 vs mid R7-9
for lab, rds in [("QB elite R1-4", [1, 2, 3, 4]), ("QB mid R7-9", [7, 8, 9])]:
    s, b, n = rd_startable("QB", rds); print(f"  {lab:16}: startable {s:.0%}  bust {b:.0%}  (n={n})")
# WR reliability cliff vs RB: startable% by ADP-rank tier within position
print("  -- reliability by within-position ADP tier (does WR fall off faster than RB?) --")
for p in ["WR", "RB"]:
    sub = d[d.position == p].copy()
    sub["pos_adp_rk"] = sub.groupby("season")["adp"].rank(method="min")
    for lo, hi in [(1, 10), (11, 20), (21, 36)]:
        g = sub[(sub.pos_adp_rk >= lo) & (sub.pos_adp_rk <= hi)]
        if len(g):
            print(f"    {p} #{lo}-{hi:<2}: startable {g.startable.mean():.0%}  bust {g.bust.mean():.0%}  (n={len(g)})")
