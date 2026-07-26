"""BACKTEST the rank_composite weights (L44-era) against REAL outcomes — the best feasible version.

Data reality (see the session notes): actual finishes + REAL historical ADP (FFC API) are obtainable;
historical ECR and past PROJECTIONS are NOT. So this is a HYBRID:
  - REAL market signal: FantasyFootballCalculator PPR ADP per season (the same thing our board's ADP is).
  - REAL target: each season's actual fantasy finish, scored under the league base scoring (scoring_config).
  - PROXIED value signals: VOLS / ceiling / floor / role reconstructed from the PRIOR year's actuals
    (a backward proxy — the real board uses FORWARD projections, so this UNDER-states the value edge).
  - ECR: folded into ADP (they're ~0.9 correlated); no separate expert signal.
Veterans only (a proxy needs a prior-year line) — rookies are excluded, another caveat.

Question: what weighting of {value, market(ADP), ceiling, floor, role} best predicts finish, and does the
composite beat ADP-alone? Metric: Spearman(predicted order, actual points) over the draftable pool,
averaged across seasons. Compares ADP-only vs the CURRENT weights vs a random-search optimum.

Run:  .venv/bin/python icm/work/mc_research/17_weight_backtest.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
import requests
import nflreadpy as nfl

from utils import normalize_name
from scoring_config import SCORING

np.random.seed(0)
SEASONS = [2022, 2023, 2024]                # test seasons (each needs prior-year actuals + FFC ADP)
POS = ["QB", "RB", "WR", "TE"]
REPL = {"QB": 12, "RB": 30, "WR": 36, "TE": 12}   # positional replacement ranks (VOLS levels)
POOL = 150                                   # draftable pool = top-N by ADP

# nflverse weekly-stat column -> our canonical SCORING key (base scoring only; bonuses ~correlated)
NFL_COL = {"pass_yds": "passing_yards", "pass_td": "passing_tds", "pass_int": "passing_interceptions",
           "rush_yds": "rushing_yards", "rush_td": "rushing_tds", "rec": "receptions",
           "rec_yds": "receiving_yards", "rec_td": "receiving_tds"}


def base_points(df):
    """Season fantasy points under the league BASE scoring, on nflverse totals."""
    pts = pd.Series(0.0, index=df.index)
    for k, col in NFL_COL.items():
        if k in SCORING and col in df.columns:
            pts = pts + df[col].fillna(0) * SCORING[k]
    return pts


def season_totals(year):
    wk = nfl.load_player_stats(seasons=[year]).to_pandas()
    wk = wk[(wk["season_type"] == "REG") & (wk["position"].isin(POS))].copy()
    wk["pts"] = base_points(wk)
    tot = wk.groupby(["player_id", "position"]).agg(
        pts=("pts", "sum"), g=("pts", "count"),
        wk_p90=("pts", lambda s: s.quantile(0.9)), wk_p10=("pts", lambda s: s.quantile(0.1)),
        tgt=("targets", "sum") if "targets" in wk.columns else ("pts", "size"),
        car=("carries", "sum") if "carries" in wk.columns else ("pts", "size"),
        name=("player_display_name", "first") if "player_display_name" in wk.columns else ("player_id", "first"),
    ).reset_index()
    return tot


def ffc_adp(year):
    pl = []
    for _ in range(4):                       # FFC rate-limits rapid calls — space them out + retry
        try:
            time.sleep(1.5)
            r = requests.get("https://fantasyfootballcalculator.com/api/v1/adp/ppr",
                             params={"teams": 12, "year": year}, timeout=20)
            pl = r.json().get("players", [])
            if pl:
                break
        except Exception:
            pass
    d = pd.DataFrame([{"norm": normalize_name(p["name"]), "position": p["position"], "adp": p["adp"]}
                     for p in pl], columns=["norm", "position", "adp"])
    if d.empty:
        raise RuntimeError(f"FFC ADP empty for {year} (rate-limited?)")
    return d[d["position"].isin(POS)]


def vols(tot):
    out = tot.copy()
    lvl = {}
    for p, n in REPL.items():
        pts = out[out["position"] == p]["pts"]
        lvl[p] = pts.nlargest(n).min() if len(pts) >= n else 0.0
    out["value"] = out["pts"] - out["position"].map(lvl)
    out["role"] = np.where(out["position"] == "QB", out["pts"],   # QB role ~ its own scoring (no share)
                           out["tgt"] + out["car"])               # RB/WR/TE role ~ opportunity volume
    return out


# ---- assemble the backtest table (one row per player-season with all signals + the actual finish) ----
rows = []
for y in SEASONS:
    cur = season_totals(y)                     # ACTUAL finish (target) in year y
    cur["norm"] = cur["name"].apply(normalize_name)
    prior = vols(season_totals(y - 1))         # PROXY signals from year y-1
    prior["norm"] = prior["name"].apply(normalize_name)
    adp = ffc_adp(y)
    m = adp.merge(prior[["norm", "position", "value", "wk_p90", "wk_p10", "role"]], on=["norm", "position"], how="inner")
    m = m.merge(cur[["norm", "position", "pts"]].rename(columns={"pts": "finish"}), on=["norm", "position"], how="inner")
    m = m[m["adp"] <= POOL].copy()
    m["season"] = y
    rows.append(m)
bt = pd.concat(rows, ignore_index=True)
print(f"backtest rows (veteran, top-{POOL} ADP, all signals present): {len(bt)} across {SEASONS}")
print("  per season:", bt.groupby("season").size().to_dict())

# ---- rank each signal WITHIN season, blend, score by Spearman vs actual finish ----
SIGS = ["value", "adp", "ceiling", "floor", "role"]
bt["ceiling"] = bt["wk_p90"]; bt["floor"] = bt["wk_p10"]
for s in SIGS:
    asc = (s == "adp")   # ADP: lower = better; others higher = better
    bt[s + "_rk"] = bt.groupby("season")[s].rank(ascending=asc, method="min")


def spearman_by_season(weights):
    """Mean per-season Spearman between the weighted composite rank and actual finish (higher=better)."""
    w = dict(zip(SIGS, weights))
    comp = sum(w[s] * bt[s + "_rk"] for s in SIGS)   # lower composite = better pick
    bt["_c"] = comp
    cors = []
    for y, g in bt.groupby("season"):
        # Spearman = Pearson of ranks (no scipy needed). -1 so low composite ~ high finish -> positive.
        cors.append(g["_c"].rank().corr(g["finish"].rank()) * -1)
    return float(np.mean(cors))


# baselines
adp_only = spearman_by_season([0, 1, 0, 0, 0])
# current composite maps to these 5 signals: VOLS=value .32, market(ECR+ADP)=.24+.12=.36 -> adp, up .13, dn .09, role .10
current_w = [0.32, 0.36, 0.13, 0.09, 0.10]
current = spearman_by_season(current_w)

# random search for the optimum (Dirichlet over the simplex)
best, best_w = -9, None
for _ in range(4000):
    w = np.random.dirichlet(np.ones(5))
    sc = spearman_by_season(w)
    if sc > best:
        best, best_w = sc, w

print("\n=== predictive accuracy (mean per-season Spearman vs actual finish; higher = better) ===")
print(f"  ADP-only (market)            : {adp_only:.3f}")
print(f"  CURRENT composite weights    : {current:.3f}   weights value/market/ceil/floor/role = {current_w}")
print(f"  OPTIMIZED (random search)    : {best:.3f}   weights = {dict(zip(SIGS, best_w.round(2)))}")
print(f"\n  lift of current over ADP-only : {current - adp_only:+.3f}")
print(f"  lift of optimized over current: {best - current:+.3f}")
