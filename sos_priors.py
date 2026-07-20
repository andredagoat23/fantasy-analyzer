"""Positional strength of schedule + 2026 head-coach changes — context layers for the advisor.

sos_data.csv     — for each 2026 team x position: how many fantasy points/game the team's 2026
                   opponents allowed to that position in 2025, as a rank (1 = EASIEST schedule
                   for that position) and a delta vs league average. Advisor-layer context only;
                   season-long SOS is a mild signal (schedules shuffle, defenses change) — it
                   breaks ties and flags extremes, it does not move projections.
data/new_hc_2026.csv — teams whose 2026 head coach differs from their 2025 coach, derived from
                   the schedules data itself (coach fields are populated for 2026). Used by the
                   validated stayed+new-HC tilt in compute_outcomes.py.

NOT part of the frozen run_all chain — run manually alongside cohort_priors.py:
    .venv/bin/python sos_priors.py
"""
import os

import pandas as pd

os.environ.setdefault("NFLREADPY_CACHE_MODE", "filesystem")
os.environ.setdefault("NFLREADPY_CACHE_DIR", "icm/work/mc_research/.nflcache")
os.environ.setdefault("NFLREADPY_TIMEOUT", "120")
import nflreadpy as nfl

POS = ["QB", "RB", "WR", "TE"]
# nflverse codes -> board (Sleeper) codes
TEAM_FIX = {"LA": "LAR"}

# 2026 head-coaching changes, NEWS-VERIFIED Jul 20 2026 (Panthers.com full table + SI/Yahoo/NBC/
# Fox trackers all agree; 10 changes). The schedules feed was STALE for ARI/ATL/BUF (still showed
# the 2025 coach) - this verified list is authoritative; the schedules derivation below is kept
# as a cross-check and warns on disagreement.
VERIFIED_NEW_HC_2026 = {
    "ARI": ("Jonathan Gannon", "Mike LaFleur"),  "ATL": ("Raheem Morris", "Kevin Stefanski"),
    "BAL": ("John Harbaugh", "Jesse Minter"),    "BUF": ("Sean McDermott", "Joe Brady"),
    "CLE": ("Kevin Stefanski", "Todd Monken"),   "LV":  ("Pete Carroll", "Klint Kubiak"),
    "MIA": ("Mike McDaniel", "Jeff Hafley"),     "NYG": ("Brian Daboll", "John Harbaugh"),
    "PIT": ("Mike Tomlin", "Mike McCarthy"),     "TEN": ("Brian Callahan", "Robert Saleh"),
}


def build():
    # ---- 2025 fantasy points allowed per position, per defense ----
    wk = pd.read_parquet("icm/work/mc_research/weekly.parquet")
    w25 = wk[(wk["season"] == 2025) & wk["position"].isin(POS)].copy()
    allowed = (w25.groupby(["opponent_team", "position"])["pts"].sum().reset_index()
                  .rename(columns={"opponent_team": "defense", "pts": "pts_allowed"}))
    games = w25.groupby("opponent_team")["week"].nunique().rename("def_games")
    allowed = allowed.merge(games, left_on="defense", right_index=True)
    allowed["pa_pg"] = allowed["pts_allowed"] / allowed["def_games"]

    # ---- 2026 opponents per team ----
    sch = nfl.load_schedules(seasons=[2026]).to_pandas()
    reg = sch[sch["game_type"] == "REG"]
    opp = pd.concat([
        reg[["home_team", "away_team"]].rename(columns={"home_team": "team", "away_team": "opponent"}),
        reg[["away_team", "home_team"]].rename(columns={"away_team": "team", "home_team": "opponent"}),
    ])

    rows = []
    for pos in POS:
        pa = allowed[allowed["position"] == pos].set_index("defense")["pa_pg"]
        lg = pa.mean()
        team_sos = (opp.assign(pa=opp["opponent"].map(pa))
                       .groupby("team")["pa"].mean().rename("sos_pa"))
        for team, v in team_sos.items():
            rows.append({"team": TEAM_FIX.get(team, team), "position": pos,
                         "sos_pa_pg": round(v, 2), "sos_delta": round(v - lg, 2)})
    sos = pd.DataFrame(rows)
    # rank 1 = easiest (opponents allow the MOST points to this position)
    sos["sos_rank"] = sos.groupby("position")["sos_pa_pg"].rank(ascending=False, method="min").astype(int)
    sos.to_csv("sos_data.csv", index=False)

    # ---- 2026 new head coaches (schedules carry coach fields for 2026) ----
    c26 = pd.concat([
        reg[["home_team", "home_coach"]].rename(columns={"home_team": "team", "home_coach": "coach"}),
        reg[["away_team", "away_coach"]].rename(columns={"away_team": "team", "away_coach": "coach"}),
    ]).groupby("team")["coach"].agg(lambda s: s.mode().iloc[0])
    s25 = nfl.load_schedules(seasons=[2025]).to_pandas()
    r25 = s25[s25["game_type"] == "REG"]
    c25 = pd.concat([
        r25[["home_team", "home_coach"]].rename(columns={"home_team": "team", "home_coach": "coach"}),
        r25[["away_team", "away_coach"]].rename(columns={"away_team": "team", "away_coach": "coach"}),
    ]).groupby("team")["coach"].agg(lambda s: s.mode().iloc[0])
    hc = pd.DataFrame({"coach_2026": c26, "coach_2025": c25})
    hc["sched_new_hc"] = hc["coach_2026"] != hc["coach_2025"]
    hc = hc.reset_index().rename(columns={"index": "team"})
    hc["team"] = hc["team"].map(lambda t: TEAM_FIX.get(t, t))
    hc["new_hc"] = hc["team"].isin(VERIFIED_NEW_HC_2026)
    for t, (old_c, new_c) in VERIFIED_NEW_HC_2026.items():
        hc.loc[hc["team"] == t, ["coach_2025", "coach_2026"]] = [old_c, new_c]
    stale = hc[hc["new_hc"] != hc["sched_new_hc"]]["team"].tolist()
    if stale:
        print(f"NOTE: schedules feed stale for {stale} - verified news list used")
    os.makedirs("data", exist_ok=True)
    hc.to_csv("data/new_hc_2026.csv", index=False)

    print(f"sos: {len(sos)} team-position rows")
    for pos in POS:
        s = sos[sos.position == pos].sort_values("sos_rank")
        print(f"  {pos} easiest: {', '.join(s.head(3).team)}  |  hardest: {', '.join(s.tail(3).team)}")
    newc = hc[hc.new_hc]
    print(f"new 2026 head coaches ({len(newc)}): "
          + ", ".join(f"{r.team} ({r.coach_2025} -> {r.coach_2026})" for r in newc.itertuples()))
    return sos, hc


if __name__ == "__main__":
    build()
