"""Pull ESPN's own Average Draft Position (ADP) live and join it onto our players.

Replaces the stale FantasyPros ADP export (load_fp_adp.py). ESPN's ADP is what you actually
see in the ESPN draft room, so this keeps VALUE/REACH and the cliff-watch survival math honest.

The endpoint is PUBLIC (no login / cookies needed). We match by (normalized name, position) so
same-name players — e.g. two different Justin Jeffersons — don't collide. Output interface is
identical to the old loader: players_with_adp.csv with `adp` + `adp_rank`.
"""
import json

import pandas as pd
import requests

from utils import normalize_name

SEASON = 2026
ESPN_POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}
URL = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/players"
HEADERS = {
    "X-Fantasy-Filter": json.dumps({"players": {"filterActive": {"value": True}}}),
    "X-Fantasy-Source": "kona",
    "User-Agent": "Mozilla/5.0",
}

# 1. pull the ESPN player universe (with ADP under ownership.averageDraftPosition)
resp = requests.get(URL, params={"view": "kona_player_info", "scoringPeriodId": 0},
                    headers=HEADERS, timeout=30)
resp.raise_for_status()

# 2. build {(normalized_name, position): ADP} from players that carry a real ADP
espn_adp = {}
for entry in resp.json():
    pl = entry.get("player", entry)
    adp = pl.get("ownership", {}).get("averageDraftPosition")
    pos = ESPN_POS.get(pl.get("defaultPositionId"))
    if adp and adp > 0 and pos:
        espn_adp[(normalize_name(pl["fullName"]), pos)] = round(float(adp), 1)
print(f"ESPN players with ADP: {len(espn_adp)}")

# 3. join onto our players by (name, position). ESPN's ADP number IS our adp_rank — it's the
#    ranking/compare key the rest of the pipeline uses (value_gap = adp_rank - overall_rank).
players = pd.read_csv("players_with_stats.csv", dtype={"player_id": str})
keys = list(zip(players["full_name"].apply(normalize_name), players["position"]))
players["adp"] = [espn_adp.get(k) for k in keys]
players["adp_rank"] = players["adp"]

# 4. save (overwrites the old FantasyPros-based players_with_adp.csv)
players.to_csv("players_with_adp.csv", index=False)

# 5. summary
have = int(players["adp"].notna().sum())
print(f"{len(players)} active players")
print(f"  with ADP:    {have}")
print(f"  without ADP: {len(players) - have}")
