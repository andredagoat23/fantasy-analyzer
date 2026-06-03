import requests
import pandas as pd

response = requests.get("https://api.sleeper.app/v1/players/nfl")
players = response.json()

allowed_positions = ["QB", "RB", "WR", "TE", "K", "DEF"]
rows = []

for player_id in players:
    player = players[player_id]
    if player.get("active") and player.get("position") in allowed_positions:
        rows.append({
            
                "full_name": player.get("full_name"),
                "position": player.get("position"),
                "team": player.get("team"),
                "age": player.get("age"),
                "status": player.get("status"),
            })

df = pd.DataFrame(rows)
df.to_csv("players.csv", index=False)

print(f"Saved {len(df)} players to players.csv")
        

