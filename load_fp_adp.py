import pandas as pd
from utils import normalize_name

# 1. read the FantasyPros / ESPN ADP export
fp = pd.read_csv("data/fantasypros_adp_espn.csv")

# 2. split "Player (Team / Bye)" on the 2+ spaces
#    part 0 = name (ALWAYS present); part 1 = "TEAM (BYE)" remainder (missing for free agents)
parts = fp["Player (Team / Bye)"].str.split(r"\s{2,}", n=1, expand=True)
fp["name"] = parts[0].str.strip()

# 3. pull team + bye from the remainder (NaN for team-less players — that's fine)
tb = parts[1].str.extract(r"([A-Z]{2,3})\s*\((\d+)\)")
fp["team"] = tb[0]
fp["bye"] = pd.to_numeric(tb[1], errors="coerce")

# 4. base position: strip the positional-rank digits, map DST -> DEF
fp["position"] = fp["POS"].str.replace(r"\d+$", "", regex=True).replace({"DST": "DEF"})

# 5. rename to our column names
fp = fp.rename(columns={"AVG": "adp", "Rank": "adp_rank"})

# 6. normalized-name join key on both sides
fp["norm_name"] = fp["name"].apply(normalize_name)
players = pd.read_csv("players_with_stats.csv", dtype={"player_id": str})
players["norm_name"] = players["full_name"].apply(normalize_name)

# 7. left join ADP onto players by (norm_name, position); keep just adp + adp_rank
adp_cols = fp[["norm_name", "position", "adp", "adp_rank"]]
merged = players.merge(adp_cols, on=["norm_name", "position"], how="left")
merged = merged.drop(columns="norm_name")

# 8. save (overwrites the old FFC-based players_with_adp.csv)
merged.to_csv("players_with_adp.csv", index=False)

# 9. summary
have = merged["adp"].notna().sum()
print(f"{len(merged)} active players")
print(f"  with ADP:    {have}")
print(f"  without ADP: {len(merged) - have}")

chk = fp.merge(players[["norm_name", "position"]].drop_duplicates(),
               on=["norm_name", "position"], how="left", indicator=True)
unmatched = chk[chk["_merge"] == "left_only"]
print(f"  FP entries unmatched: {len(unmatched)}")
for _, r in unmatched.iterrows():
    print("     ", r["name"], "|", r["position"])