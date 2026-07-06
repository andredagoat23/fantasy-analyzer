import pandas as pd
from utils import normalize_name

# 1. read the FantasyPros ECR export (pandas strips the quoted headers fine)
ecr = pd.read_csv("data/fantasypros_ecr.csv")

# 2. rename the columns we care about
ecr = ecr.rename(columns={
    "RK": "ecr_rank",
    "TIERS": "ecr_tier",
    "PLAYER NAME": "name",
    "POS": "position_raw",
    "SOS SEASON": "sos_season",
})

# 3. drop the tier-separator rows (blank PLAYER NAME) — prevents the "nan" collision
ecr = ecr.dropna(subset=["name"]).copy()

# 4. base position: strip the positional-rank digits, map DST -> DEF
ecr["position"] = ecr["position_raw"].str.replace(r"\d+$", "", regex=True).replace({"DST": "DEF"})

# 5. normalized-name join key on both sides
ecr["norm_name"] = ecr["name"].apply(normalize_name)
players = pd.read_csv("players_with_adp.csv", dtype={"player_id": str})
players["norm_name"] = players["full_name"].apply(normalize_name)

# 6. left join ECR onto players; keep only ECR-specific columns
ecr_cols = ecr[["norm_name", "position", "ecr_rank", "ecr_tier", "sos_season"]]
merged = players.merge(ecr_cols, on=["norm_name", "position"], how="left")
merged = merged.drop(columns="norm_name")

# 7. save
merged.to_csv("players_with_ecr.csv", index=False)

# 8. summary
have = merged["ecr_rank"].notna().sum()
print(f"{len(merged)} active players")
print(f"  with ECR:    {have}")
print(f"  without ECR: {len(merged) - have}")

chk = ecr.merge(players[["norm_name", "position"]].drop_duplicates(),
                on=["norm_name", "position"], how="left", indicator=True)
unmatched = chk[chk["_merge"] == "left_only"]
print(f"  ECR entries unmatched: {len(unmatched)}")
for _, r in unmatched.iterrows():
    print("     ", r["name"], "|", r["position"])