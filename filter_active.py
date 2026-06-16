import pandas as pd
import nflreadpy as nfl

# 1. read raw players; force player_id to text so it matches the crosswalk
players = pd.read_csv("players.csv", dtype={"player_id": str})

# 2. build the sleeper_id -> gsis_id bridge from the crosswalk (polars -> dict)
xwalk = nfl.load_ff_playerids().select(["sleeper_id", "gsis_id"]).drop_nulls()
sleeper_to_gsis = {str(row["sleeper_id"]): row["gsis_id"] for row in xwalk.to_dicts()}

# 3. set of gsis ids that actually played in 2024 or 2025
stats = nfl.load_player_stats(seasons=[2024, 2025])
played_gsis = {pid for pid in stats["player_id"].to_list() if pid is not None and pid != ""}

# 4. translate each player's sleeper id to a real gsis id, then filter
players["gsis_id"] = players["player_id"].map(sleeper_to_gsis)
keep = (
    (players["position"] == "DEF")
    | (players["gsis_id"].notna() & players["gsis_id"].isin(played_gsis))
)
active_players = players[keep]

# 5. save and report
active_players.to_csv("players_active.csv", index=False)
print(f"Kept {len(active_players)} of {len(players)} players -> players_active.csv")