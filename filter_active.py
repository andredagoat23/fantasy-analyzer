import re
import pandas as pd
import nflreadpy as nfl

SKILL = {"QB", "RB", "WR", "TE", "K"}


def normalize_name(name):
    """Lowercase, strip punctuation and Jr/Sr/III suffixes so names match across sources."""
    s = str(name).lower().strip()
    s = re.sub(r"[^a-z0-9 ]", " ", s)            # punctuation -> space
    s = re.sub(r"\s+", " ", s).strip()           # squeeze spaces FIRST
    s = re.sub(r" (jr|sr|ii|iii|iv|v)$", "", s)  # then strip a trailing suffix
    return s


# 1. read raw players; force player_id to text so it matches the crosswalk
players = pd.read_csv("players.csv", dtype={"player_id": str})

# 2. build the sleeper_id -> gsis_id bridge from the crosswalk (polars -> dict)
xwalk = nfl.load_ff_playerids().select(["sleeper_id", "gsis_id"]).drop_nulls()
sleeper_to_gsis = {str(row["sleeper_id"]): row["gsis_id"] for row in xwalk.to_dicts()}

# 3. set of gsis ids that actually played in 2024 or 2025
stats = nfl.load_player_stats(seasons=[2024, 2025])
played_gsis = {pid for pid in stats["player_id"].to_list() if pid is not None and pid != ""}

# 4. translate each player's sleeper id to a real gsis id, then find the "played" set
players["gsis_id"] = players["player_id"].map(sleeper_to_gsis)
keep = (
    (players["position"] == "DEF")
    | (players["gsis_id"].notna() & players["gsis_id"].isin(played_gsis))
)
keep_ids = set(players.loc[keep, "player_id"])
n_played = len(keep_ids)

# rookie_gsis: clean gsis ids for the rookies we add below (from nflverse, not Sleeper)
rookie_gsis = {}

# 5. TRACK A — 2025 rookies who didn't play (clean sleeper_id join from 2026 rosters)
rosters = nfl.load_rosters(seasons=[2026]).to_pandas()
rosters["sleeper_id"] = rosters["sleeper_id"].astype("string")
rookies_2025 = rosters[
    (rosters["position"].isin(SKILL))
    & (rosters["entry_year"] == 2025)
    & (rosters["sleeper_id"].notna())
]
ids_in_csv = set(players["player_id"])
track_a = 0
for _, row in rookies_2025.iterrows():
    sid = row["sleeper_id"]
    if sid in ids_in_csv and sid not in keep_ids:
        keep_ids.add(sid)
        track_a += 1
    if pd.notna(row["gsis_id"]):
        rookie_gsis[sid] = row["gsis_id"]

# 6. TRACK B — 2026 drafted rookies (name match; no shared ID exists yet)
draft = nfl.load_draft_picks(seasons=[2026]).to_pandas()
draft = draft[draft["position"].isin(SKILL)]

# lookup of Sleeper ROOKIES only (years_exp == 0), keyed by (normalized name, position)
rookie_pool = players[players["years_exp"] == 0]
name_lookup = {
    (normalize_name(row["full_name"]), row["position"]): row["player_id"]
    for _, row in rookie_pool.iterrows()
}

track_b = 0
unmatched = []
for _, row in draft.iterrows():
    key = (normalize_name(row["pfr_player_name"]), row["position"])
    pid = name_lookup.get(key)
    if pid is None:
        unmatched.append(f'{row["pfr_player_name"]} ({row["position"]})')
        continue
    if pid not in keep_ids:
        keep_ids.add(pid)
        track_b += 1
    if pd.notna(row["gsis_id"]):
        rookie_gsis[pid] = row["gsis_id"]

# 7. combine, fill rookie gsis ids, save, report
final = players[players["player_id"].isin(keep_ids)].copy()
final["gsis_id"] = final["gsis_id"].fillna(final["player_id"].map(rookie_gsis))
final.to_csv("players_active.csv", index=False)

print(f"played:         {n_played}")
print(f"+ 2025 rookies: {track_a}")
print(f"+ 2026 rookies: {track_b}")
print(f"= total:        {len(final)} -> players_active.csv")
print(f"\nunmatched 2026 draft picks ({len(unmatched)}) - add by hand or re-run later:")
for u in unmatched:
    print("   ", u)