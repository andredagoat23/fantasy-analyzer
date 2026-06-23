import pandas as pd
import nflreadpy as nfl

STATS = [
    "passing_yards", "passing_tds",
    "rushing_yards", "rushing_tds", "carries",
    "receptions", "receiving_yards", "receiving_tds", "targets",
]
OFFENSE = ["QB", "RB", "WR", "TE"]   # snap_share covers these
RECEIVERS = ["WR", "TE", "RB"]             # target_share covers these

# snap counts use pfr_player_id, so build a pfr_id -> gsis_id bridge once
_xw = nfl.load_ff_playerids().to_pandas()
PFR_TO_GSIS = {p: g for p, g in zip(_xw["pfr_id"], _xw["gsis_id"]) if pd.notna(p) and pd.notna(g)}


def season_totals(year, suffix):
    """REG-season stat totals per player, keyed by gsis_id, columns suffixed by year."""
    weekly = nfl.load_player_stats(seasons=[year]).to_pandas()
    weekly = weekly[(weekly["season_type"] == "REG") & (weekly["player_id"].notna())]
    totals = weekly.groupby("player_id")[STATS].sum().reset_index()
    rename_map = {"player_id": "gsis_id"}
    rename_map.update({s: s + suffix for s in STATS})
    return totals.rename(columns=rename_map)


def snap_share(year):
    """Average REG offensive snap share (offense_pct) per player, bridged to gsis_id."""
    sc = nfl.load_snap_counts(seasons=[year]).to_pandas()
    sc = sc[(sc["game_type"] == "REG") & (sc["position"].isin(OFFENSE))]
    s = sc.groupby("pfr_player_id")["offense_pct"].mean().reset_index()
    s["gsis_id"] = s["pfr_player_id"].map(PFR_TO_GSIS)          # pfr -> gsis bridge
    s = s.dropna(subset=["gsis_id"])
    return s[["gsis_id", "offense_pct"]].rename(columns={"offense_pct": f"snap_share_{year}"})


def target_share(year):
    """WR/TE target share = targets on primary team / that team's total REG targets."""
    ps = nfl.load_player_stats(seasons=[year]).to_pandas()
    ps = ps[(ps["season_type"] == "REG") & (ps["player_id"].notna()) & (ps["position"].isin(RECEIVERS))]
    # targets per player per team, then keep each player's primary (most-targets) team
    by_team = ps.groupby(["player_id", "team"], as_index=False)["targets"].sum()
    primary = by_team.loc[by_team.groupby("player_id")["targets"].idxmax()].copy()
    # team total targets that season
    team = nfl.load_team_stats(seasons=[year]).to_pandas()
    team = team[team["season_type"] == "REG"]
    team_total = team.groupby("team")["targets"].sum()
    primary["team_total"] = primary["team"].map(team_total)
    primary[f"target_share_{year}"] = primary["targets"] / primary["team_total"]
    return primary.rename(columns={"player_id": "gsis_id"})[["gsis_id", f"target_share_{year}"]]


# 1. read active players (gsis_id is the join key for everything)
active = pd.read_csv("players_active.csv", dtype={"player_id": str})

# 2. season stat totals, both years, suffixed
merged = active.merge(season_totals(2024, "_2024"), on="gsis_id", how="left")
merged = merged.merge(season_totals(2025, "_2025"), on="gsis_id", how="left")

# 3. snap share (QB/RB/WR/TE) and target share (WR/TE), both years
for yr in (2024, 2025):
    merged = merged.merge(snap_share(yr), on="gsis_id", how="left")
    merged = merged.merge(target_share(yr), on="gsis_id", how="left")

# 4. save (overwrites previous version)
merged.to_csv("players_with_stats.csv", index=False)

# 5. summary
has_2024 = merged[[s + "_2024" for s in STATS]].notna().any(axis=1)
has_2025 = merged[[s + "_2025" for s in STATS]].notna().any(axis=1)
print(f"{len(merged)} active players")
print(f"  with 2024 stats: {int(has_2024.sum())}")
print(f"  with 2025 stats: {int(has_2025.sum())}")
print(f"  neither season:  {int(((~has_2024) & (~has_2025)).sum())}")
print(f"  snap_share 24/25:   {merged['snap_share_2024'].notna().sum()} / {merged['snap_share_2025'].notna().sum()}")
print(f"  target_share 24/25: {merged['target_share_2024'].notna().sum()} / {merged['target_share_2025'].notna().sum()}")