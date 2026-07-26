"""DEEP board-weight backtest — 13 seasons (2012-2024) with LEAVE-ONE-SEASON-OUT cross-validation.

Extends 17 (which was 3 seasons, in-sample only). Same hybrid data (REAL FFC ADP + REAL finishes +
prior-year-proxied value signals; no historical ECR/projections exist). The point of LOSO-CV: an
in-sample "optimum" overfits the sample. Here we find the best weights on N-1 seasons and score them on
the HELD-OUT season, averaged over all 13 folds — an honest estimate of how much tuning actually
generalizes. Also reports whether the optimal weights are STABLE across folds (unstable = noise).

CAVEAT unchanged: "value" is proxied by prior-year actuals (backward) — a weak stand-in for the real
FORWARD projection VOLS — so the value weight is judged unfairly LOW. Veterans only, base scoring.

Run:  .venv/bin/python icm/work/mc_research/18_weight_backtest_full.py   (cached after first run)
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

np.random.seed(0)
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "18_bt_cache.csv")
SEASONS = list(range(2012, 2025))          # test seasons; each needs prior-year actuals + FFC ADP
POS = ["QB", "RB", "WR", "TE"]
REPL = {"QB": 12, "RB": 30, "WR": 36, "TE": 12}
POOL = 150
SIGS = ["value", "adp", "ceiling", "floor", "role"]
NFL_COL = {"pass_yds": "passing_yards", "pass_td": "passing_tds", "pass_int": "passing_interceptions",
           "rush_yds": "rushing_yards", "rush_td": "rushing_tds", "rec": "receptions",
           "rec_yds": "receiving_yards", "rec_td": "receiving_tds"}


def base_points(df):
    pts = pd.Series(0.0, index=df.index)
    for k, col in NFL_COL.items():
        if k in SCORING and col in df.columns:
            pts = pts + df[col].fillna(0) * SCORING[k]
    return pts


def season_totals(year):
    wk = nfl.load_player_stats(seasons=[year]).to_pandas()
    wk = wk[(wk["season_type"] == "REG") & (wk["position"].isin(POS))].copy()
    wk["pts"] = base_points(wk)
    tgt = "targets" if "targets" in wk.columns else "pts"
    car = "carries" if "carries" in wk.columns else "pts"
    nm = "player_display_name" if "player_display_name" in wk.columns else "player_id"
    return wk.groupby(["player_id", "position"]).agg(
        pts=("pts", "sum"), wk_p90=("pts", lambda s: s.quantile(0.9)), wk_p10=("pts", lambda s: s.quantile(0.1)),
        tgt=(tgt, "sum"), car=(car, "sum"), name=(nm, "first")).reset_index()


def ffc_adp(year):
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
    d = pd.DataFrame([{"norm": normalize_name(p["name"]), "position": p["position"], "adp": p["adp"]}
                     for p in pl], columns=["norm", "position", "adp"])
    return d[d["position"].isin(POS)]


def vols(tot):
    out = tot.copy()
    lvl = {p: (out[out.position == p]["pts"].nlargest(n).min() if (out.position == p).sum() >= n else 0.0)
           for p, n in REPL.items()}
    out["value"] = out["pts"] - out["position"].map(lvl)
    out["role"] = np.where(out["position"] == "QB", out["pts"], out["tgt"] + out["car"])
    return out


# ---- assemble (cached) ----
if os.path.exists(CACHE):
    bt = pd.read_csv(CACHE)
    print(f"loaded cache: {len(bt)} rows, seasons {sorted(bt.season.unique())}")
else:
    rows = []
    for y in SEASONS:
        try:
            adp = ffc_adp(y)
            if adp.empty:
                print(f"  {y}: no FFC ADP, skipped"); continue
            cur = season_totals(y); cur["norm"] = cur["name"].apply(normalize_name)
            prior = vols(season_totals(y - 1)); prior["norm"] = prior["name"].apply(normalize_name)
            m = adp.merge(prior[["norm", "position", "value", "wk_p90", "wk_p10", "role"]], on=["norm", "position"])
            m = m.merge(cur[["norm", "position", "pts"]].rename(columns={"pts": "finish"}), on=["norm", "position"])
            m = m[m.adp <= POOL].copy(); m["season"] = y
            rows.append(m); print(f"  {y}: {len(m)} rows")
        except Exception as e:
            print(f"  {y}: ERROR {e}")
    bt = pd.concat(rows, ignore_index=True)
    bt.to_csv(CACHE, index=False)
    print(f"assembled + cached: {len(bt)} rows across {sorted(bt.season.unique())}")

bt["ceiling"] = bt["wk_p90"]; bt["floor"] = bt["wk_p10"]
for s in SIGS:
    bt[s + "_rk"] = bt.groupby("season")[s].rank(ascending=(s == "adp"), method="min")


def season_scores(weights, seasons):
    w = dict(zip(SIGS, weights))
    out = {}
    for y in seasons:
        g = bt[bt.season == y]
        comp = sum(w[s] * g[s + "_rk"] for s in SIGS)
        out[y] = comp.rank().corr(g["finish"].rank()) * -1
    return out


def mean_score(weights, seasons):
    return float(np.mean(list(season_scores(weights, seasons).values())))


def optimize(seasons, n=6000):
    best, bw = -9, None
    for _ in range(n):
        w = np.random.dirichlet(np.ones(5))
        sc = mean_score(w, seasons)
        if sc > best:
            best, bw = sc, w
    return best, bw


ALL = sorted(bt.season.unique())
adp_only = mean_score([0, 1, 0, 0, 0], ALL)
current_w = [0.32, 0.36, 0.13, 0.09, 0.10]
current = mean_score(current_w, ALL)
insample_best, insample_w = optimize(ALL)

print(f"\n=== in-sample (all {len(ALL)} seasons) ===")
print(f"  ADP-only            : {adp_only:.3f}")
print(f"  CURRENT weights     : {current:.3f}")
print(f"  in-sample OPTIMUM   : {insample_best:.3f}   weights = {dict(zip(SIGS, insample_w.round(2)))}")

# ---- LOSO-CV: optimize on N-1, score on held-out; the HONEST generalization estimate ----
print("\n=== leave-one-season-out CV (optimize on the rest, score on the held-out season) ===")
oos_opt, oos_cur, fold_w = [], [], []
for y in ALL:
    train = [s for s in ALL if s != y]
    _, w = optimize(train, n=3000)
    oos_opt.append(mean_score(w, [y]))
    oos_cur.append(mean_score(current_w, [y]))
    fold_w.append(w)
print(f"  CURRENT weights, mean held-out Spearman : {np.mean(oos_cur):.3f}")
print(f"  TUNED (LOSO) , mean held-out Spearman   : {np.mean(oos_opt):.3f}")
print(f"  honest generalizable gain from tuning   : {np.mean(oos_opt) - np.mean(oos_cur):+.3f}")

fw = np.array(fold_w)
print("\n=== optimal-weight STABILITY across the 13 folds (mean ± sd; high sd = the 'optimum' is noise) ===")
for i, s in enumerate(SIGS):
    print(f"  {s:8}: {fw[:, i].mean():.2f} ± {fw[:, i].std():.2f}")
