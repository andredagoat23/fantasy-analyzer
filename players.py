import requests

response = requests.get("https://api.sleeper.app/v1/players/nfl")
players = response.json()

for player_id in list(players)[:5]:
    player = players[player_id]
    print(f"{player['first_name']} {player['last_name']} - {player['position']} - {player['team']}")