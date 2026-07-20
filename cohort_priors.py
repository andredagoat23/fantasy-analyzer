"""Cohort priors — the "Hampton treatment" for every board player.

For each fantasy-relevant player, find his historical ARCHETYPE COHORT in the 2019-2025
research panel (same position, experience, price tier, draft capital, production profile,
mover status — relaxed hierarchically until the cohort has enough members) and record how
that archetype ACTUALLY performed vs its preseason price: boom/bust rates, median multiplier,
top-5 rate, and real named comps (best / typical / worst outcomes).

NOT part of the frozen run_all chain — run manually after a board rebuild:
    .venv/bin/python cohort_priors.py
Needs the local research panel (icm/work/mc_research/seasons_exp.parquet — rebuild via
icm/work/mc_research/01_build_panel.py + 02_expectation.py if missing). Writes cohort_data.csv
(committed, so the deployed advisor can read it without the panel).

The advisor uses these as ARCHETYPE PRIORS + explainable comps ("profile like Gibbs '24").
They never override the calibrated MC odds — small-n history is color, not calibration.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import normalize_name

PANEL = "icm/work/mc_research/seasons_exp.parquet"
MIN_N = 8          # widen the cohort definition until at least this many historical seasons match
MAX_POS_RANK = 70  # only players fantasy-relevant enough to have a meaningful archetype

EXP_BUCKETS = [(0, 0, "rookie"), (1, 1, "2nd-yr"), (2, 3, "yr 3-4"), (4, 6, "yr 5-7"), (7, 30, "vet 8+")]
TIERS = [(1, 3, "top-3"), (4, 6, "top-6"), (7, 12, "starter"), (13, 24, "mid"), (25, 40, "late"), (41, 70, "deep")]
CAPITAL = [(1, 15, "top-15 pick"), (16, 32, "1st-rd"), (33, 64, "2nd-rd"), (65, 105, "3rd-rd"), (106, 400, "day-3")]
PROD = [(0, 8, "low prod"), (8, 12, "solid prod"), (12, 16, "strong prod"), (16, 99, "elite prod")]
AGES = [(0, 23, "<=23"), (24, 26, "24-26"), (27, 29, "27-29"), (30, 60, "30+")]


def bucket(val, table, default=None):
    if pd.isna(val):
        return default
    for lo, hi, name in table:
        if lo <= val <= hi:
            return name
    return default


def label_of(table, name):
    return next((t for t in table if t[2] == name), None)


def in_bucket(series, table, name):
    t = label_of(table, name)
    if t is None:
        return pd.Series(True, index=series.index)
    return series.between(t[0], t[1])


def build():
    if not os.path.exists(PANEL):
        raise SystemExit(f"research panel missing: {PANEL} — rebuild via icm/work/mc_research/01+02")
    sea = pd.read_parquet(PANEL)
    hist = sea[sea["mult"].notna() & (sea["exp_pos_rank"] <= MAX_POS_RANK)].copy()
    hist["moved"] = (hist["team_last"] != hist["prev_team_last"]) & hist["prev_team_last"].notna()
    # team-role analog: rank among same-position teammates by preseason expectation
    hist["role_rank"] = hist.groupby(["season", "team_last", "position"])["exp_pos_rank"].rank(method="first")
    # older roster years carry mixed types - force every matching feature numeric
    for c in ["draft_number", "years_exp", "age", "prev_ppg", "prev_games_missed", "implied_total_avg"]:
        hist[c] = pd.to_numeric(hist[c], errors="coerce")

    board = pd.read_csv("players_with_outcomes.csv", dtype={"player_id": str})
    board = board[board["position"].isin(["QB", "RB", "WR", "TE"]) & board["total_points"].notna()].copy()
    board["pos_rank"] = board.groupby("position")["total_points"].rank(ascending=False, method="first")
    board = board[board["pos_rank"] <= MAX_POS_RANK]

    # years_exp + career draft slot from 2026 rosters (players_with_outcomes only has the 2026 class)
    import nflreadpy as nfl
    ros = nfl.load_rosters(seasons=[2026]).to_pandas()
    ros = (ros.dropna(subset=["gsis_id"]).drop_duplicates("gsis_id")
              .set_index("gsis_id")[["years_exp", "draft_number"]])
    board["years_exp"] = board["gsis_id"].map(ros["years_exp"])
    board["career_pick"] = board["gsis_id"].map(ros["draft_number"])
    # enrichment from the value board (role, vegas env) + last-season games from the panel weekly
    vb = pd.read_csv("value_board.csv")
    vb["nn"] = vb["full_name"].apply(normalize_name)
    vb["role_rank"] = vb["team_role"].astype(str).str.extract(r"(\d+)").astype(float)
    board["nn"] = board["full_name"].apply(normalize_name)
    board = board.merge(vb[["nn", "role_rank", "team_implied_total"]], on="nn", how="left")
    wk25 = pd.read_parquet("icm/work/mc_research/weekly.parquet")
    g25 = wk25[wk25["season"] == 2025].groupby("player_id").size()
    board["missed_last"] = (17 - board["gsis_id"].map(g25).fillna(0)).clip(lower=0)

    K = 15   # cohort = the K most-similar historical player-seasons (no bucket cliffs)
    rows = []
    for _, p in board.iterrows():
        is_rk = bool(p.get("is_rookie", False))
        base = hist[hist["position"] == p["position"]]
        # rookies comp only to rookie seasons; veterans never to rookie seasons
        base = base[base["years_exp"] == 0] if is_rk else base[base["years_exp"] > 0]
        if len(base) < K:
            continue
        # weighted L1 distance over preseason-knowable features (scales ~ "1 unit of difference")
        d = pd.Series(0.0, index=base.index)
        d += (base["exp_pos_rank"] - p["pos_rank"]).abs() / 6.0            # price tier
        if pd.notna(p["years_exp"]) and not is_rk:
            d += (base["years_exp"] - p["years_exp"]).abs() / 2.0          # experience
        if pd.notna(p["career_pick"]):
            d += (base["draft_number"].fillna(180) - p["career_pick"]).abs() / 40.0   # draft capital
        else:
            d += (base["draft_number"].notna()).astype(float) * 0.8        # UDFA vs drafted
        if pd.notna(p["wk_mean"]) and not is_rk:
            d += (base["prev_ppg"].fillna(4) - p["wk_mean"]).abs() / 3.0   # recent production
        if pd.notna(p["age"]):
            d += (base["age"].fillna(26) - p["age"]).abs() / 2.5           # age
        d += (base["moved"] != bool(p.get("team_changed", False))).astype(float) * 0.7  # mover status
        if pd.notna(p.get("role_rank")):
            d += (base["role_rank"].fillna(2) - p["role_rank"]).abs() / 1.0          # depth-chart role
        if pd.notna(p.get("team_implied_total")):
            d += (base["implied_total_avg"].fillna(22.5) - p["team_implied_total"]).abs() / 2.5  # vegas env
        if not is_rk:
            d += (base["prev_games_missed"].fillna(3) - p["missed_last"]).abs() / 5.0  # injury history
        d += (2025 - base["season"]) * 0.05                                          # mild recency preference
        cohort = base.loc[d.nsmallest(K).index]
        dist = d.loc[cohort.index]

        prof = [p["position"], "rookie" if is_rk else f"yr-{int(p['years_exp']) + 1}" if pd.notna(p["years_exp"]) else "vet"]
        if pd.notna(p["career_pick"]):
            prof.append(f"pick {int(p['career_pick'])}")
        if pd.notna(p["wk_mean"]) and not is_rk:
            prof.append(f"{p['wk_mean']:.0f} ppg")
        prof.append(f"priced {p['position']}{int(p['pos_rank'])}")
        if pd.notna(p["age"]):
            prof.append(f"age {int(p['age'])}")
        if p.get("team_changed", False):
            prof.append("new team")
        desc = " ".join(prof)

        boom = (cohort["mult"] >= 1.3).mean()
        bust = (cohort["mult"] <= 0.7).mean()
        med = cohort["mult"].median()
        top5 = (cohort["pos_rank_total"] <= 5).mean()

        # the 5 ABSOLUTE best matches (closest profiles), shown with their real outcomes
        def fmt(i):
            r = cohort.loc[i]
            fin = f"{r['position']}{int(r['pos_rank_total'])}" if pd.notna(r["pos_rank_total"]) else "-"
            return f"{r['name_disp']} '{int(r['season']) % 100:02d}->{fin} ({r['mult']:.2f}x)"
        best5_idx = list(dist.nsmallest(5).index)
        comps = [fmt(i) for i in best5_idx]
        b5 = cohort.loc[best5_idx]
        best5_note = f"{(b5['mult']>=1.3).sum()}/5 boomed, {(b5['mult']<=0.7).sum()}/5 busted"

        rows.append({"full_name": p["full_name"], "position": p["position"],
                     "cohort_desc": desc, "cohort_n": len(cohort),
                     "cohort_boom": round(boom, 3), "cohort_bust": round(bust, 3),
                     "cohort_med": round(med, 2), "cohort_top5": round(top5, 3),
                     "cohort_comps": " | ".join(comps), "cohort_best5": best5_note})

    out = pd.DataFrame(rows)
    out["nn"] = out["full_name"].apply(normalize_name)
    out.to_csv("cohort_data.csv", index=False)
    print(f"cohorts for {len(out)} players "
          f"(median cohort n={out['cohort_n'].median():.0f}, min={out['cohort_n'].min()})")
    for nm in ["Omarion Hampton", "Jeremiyah Love", "Mike Evans", "Rashee Rice", "David Montgomery"]:
        r = out[out.full_name == nm]
        if len(r):
            x = r.iloc[0]
            print(f"  {nm}: [{x.cohort_desc}] n={x.cohort_n} boom {x.cohort_boom:.0%} bust {x.cohort_bust:.0%} "
                  f"med {x.cohort_med}x top5 {x.cohort_top5:.0%}\n    comps: {x.cohort_comps}")
    return out


if __name__ == "__main__":
    build()
