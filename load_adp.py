import requests
import pandas as pd
from utils import normalize_name

KEEP = ["name", "position", "team", "adp", "adp_formatted", "times_drafted", "stdev", "bye"]

# 1. fetch FFC ADP — 12-team PPR, 2026
url = "https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year=2026"
data = requests.get(url, timeout=30).json()
ffc = pd.DataFrame(data["players"])[KEEP]

# 2. FFC calls kickers "PK"; we use "K" — align so they can match
ffc["position"] = ffc["position"].replace({"PK": "K"})

# 3. build the normalized-name join key on both sides
ffc["norm_name"] = ffc["name"].apply(normalize_name)
players = pd.read_csv("players_with_stats.csv", dtype={"player_id": str})
players["norm_name"] = players["full_name"].apply(normalize_name)

# 4. left join FFC onto players by (normalized name, position)
merged = players.merge(ffc, on=["norm_name", "position"], how="left", suffixes=("", "_ffc"))
merged = merged.drop(columns="norm_name")

# 5. save
merged.to_csv("players_with_adp.csv", index=False)

# 6. summary
have_adp = merged["adp"].notna().sum()
print(f"{len(merged)} active players")
print(f"  with ADP:    {have_adp}")
print(f"  without ADP: {len(merged) - have_adp}")

# FFC entries that matched no active player
chk = ffc.merge(players[["norm_name", "position"]].drop_duplicates(),
                on=["norm_name", "position"], how="left", indicator=True)
unmatched = chk[chk["_merge"] == "left_only"]
print(f"  FFC entries unmatched: {len(unmatched)}")
for _, r in unmatched.iterrows():
    print("     ", r["name"], "|", r["position"])