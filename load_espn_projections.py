"""Pull ESPN's OWN season projections (component stats) → data/espn_projections.csv.

Second projection source for the consensus blend (see projections.py). Uses the SAME ESPN endpoint as
load_espn_adp.py — the kona_player_info payload already carries each player's projected stat line
(statSourceId=1), so this is free and needs no new auth. Maps ESPN's numeric stat ids to the pipeline's
canonical component names; fumbles_lost isn't cleanly identifiable in ESPN's ids, so it's left to
FantasyPros in the blend.

Run:  .venv/bin/python load_espn_projections.py   (part of run_all, before custom_scoring)
"""
import json

import pandas as pd
import requests

from utils import normalize_name

SEASON = 2026
URL = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/players"
HDR = {
    "X-Fantasy-Filter": json.dumps({"players": {"filterActive": {"value": True}, "limit": 2000,
                                                "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}),
    "X-Fantasy-Source": "kona",
    "Accept": "application/json",
}
ESPN_POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K"}          # skip 16=DEF (D/ST is a separate layer)
ESPN_STAT = {"pass_att": "0", "pass_yds": "3", "pass_td": "4", "pass_int": "20",
             "rush_att": "23", "rush_yds": "24", "rush_td": "25",
             "rec": "53", "rec_yds": "42", "rec_td": "43",
             "fg_made": "83", "fg_att": "84", "pat_made": "86"}

resp = requests.get(URL, params={"view": "kona_player_info", "scoringPeriodId": 0}, headers=HDR, timeout=30)
resp.raise_for_status()
data = resp.json()
players = data["players"] if isinstance(data, dict) else data

rows = []
for p in players:
    pl = p.get("player", p)
    pos = ESPN_POS.get(pl.get("defaultPositionId"))
    name = pl.get("fullName")
    if not pos or not name:
        continue
    proj = next((s.get("stats", {}) for s in pl.get("stats", [])
                 if s.get("statSourceId") == 1 and s.get("seasonId") == SEASON and s.get("statSplitTypeId") == 0), None)
    if not proj:
        continue
    row = {"full_name": name, "position": pos}
    for canon, sid in ESPN_STAT.items():
        if sid in proj:
            row[canon] = round(float(proj[sid]), 3)
    # keep only players ESPN actually projects for their position (has at least one real stat)
    if len(row) > 2:
        rows.append(row)

out = pd.DataFrame(rows).drop_duplicates(subset=["full_name", "position"])
out.to_csv("data/espn_projections.csv", index=False)
print(f"ESPN projections: {len(out)} players -> data/espn_projections.csv")
print("  by position:", out.groupby("position").size().to_dict())
print(out[out.full_name.isin(["Josh Allen", "Bijan Robinson", "Ja'Marr Chase", "Brandon Aubrey"])]
      .set_index("full_name").round(0).to_string())
