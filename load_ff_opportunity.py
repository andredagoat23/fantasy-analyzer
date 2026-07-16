"""Opportunity-based regression lens: xPPG (expected fantasy points per game).

xPPG comes from nflverse's ff_opportunity (open-licensed): it values each target/carry by the
league-average fantasy points that situation historically yields, so it measures a player's ROLE
quality independent of finishing luck. The signal is actual PPG vs xPPG:
  - scored MORE than expected -> TD-lucky, regression risk (fade / don't reach)
  - scored LESS than expected -> efficient role, unlucky TDs (buy-low)

Two refinements (both validated on 2024-25 data):
  * POSITION-BASED — over/under-performance is z-scored WITHIN position (RB scales != WR).
  * ELITE DAMPENING — top-of-position players are shrunk on the "lucky" side, because elite
    players MAKE their touchdowns (repeatable finishing), so their overperformance is mostly
    talent, not luck. Without this, Bijan/Chase/Nacua/Gibbs would all be (wrongly) flagged.

Runs after compute_outcomes, before value_board; joins on gsis_id (the pipeline's key) and writes
xppg / xppg_diff / regression back into players_with_outcomes.csv.
"""
import numpy as np
import pandas as pd

import nflreadpy as nfl

SEASONS = [2024, 2025]
MIN_GAMES = 8       # need enough games for a stable read
LUCKY_Z = 1.0       # position-relative z cutoff for the TD-lucky / buy-low labels

# a few abbreviation mismatches between nflverse rosters and our Sleeper team codes
_TEAM_NORM = {"LA": "LAR", "JAC": "JAX", "WSH": "WAS", "ARZ": "ARI"}


def _norm_team(t):
    return _TEAM_NORM.get(t, t) if isinstance(t, str) else t


def team_2025():
    """gsis_id -> the team a player was on in 2025 (to detect off-season situation changes)."""
    r = nfl.load_rosters(seasons=[2025]).to_pandas()
    idc = "gsis_id" if "gsis_id" in r.columns else "player_id"
    r = r[[idc, "team"]].dropna().drop_duplicates(idc)
    return r.rename(columns={idc: "gsis_id", "team": "team_2025"})


def xppg_table():
    """Per-player (gsis_id) expected vs actual fantasy points per game, pooled over SEASONS."""
    frames = []
    for yr in SEASONS:
        d = nfl.load_ff_opportunity(seasons=[yr]).to_pandas()
        frames.append(d[["player_id", "week", "total_fantasy_points", "total_fantasy_points_exp"]])
    opp = pd.concat(frames, ignore_index=True)
    g = opp.groupby("player_id", as_index=False).agg(
        games=("week", "count"),
        fp=("total_fantasy_points", "sum"),
        xfp=("total_fantasy_points_exp", "sum"),
    )
    g = g[g["games"] >= MIN_GAMES].copy()
    g["xppg"] = g["xfp"] / g["games"]
    g["xppg_diff"] = g["fp"] / g["games"] - g["xppg"]      # + = overperformed (TD-lucky)
    return g.rename(columns={"player_id": "gsis_id"})[["gsis_id", "xppg", "xppg_diff"]]


def main():
    board = pd.read_csv("players_with_outcomes.csv", dtype={"player_id": str})
    board = board.drop(columns=[c for c in ("xppg", "xppg_diff", "regression", "switched_team")
                                if c in board.columns])
    board = board.merge(xppg_table(), on="gsis_id", how="left")

    # situation change: a player whose 2026 team differs from his 2025 team has a STALE opportunity
    # profile — his xPPG describes his old role, not the new one. Flag them so value_board can
    # neutralize the (backward-looking) role signal and let the 2026 projection / market rank them.
    board = board.merge(team_2025(), on="gsis_id", how="left")
    board["switched_team"] = (board["team_2025"].notna()
                              & (board["team_2025"].map(_norm_team) != board["team"].map(_norm_team)))
    board = board.drop(columns=["team_2025"])

    # talent proxy: rank by our projected points within position (1 = best)
    pos_rank = board.groupby("position")["total_points"].rank(ascending=False, method="min")

    # position-relative z of the raw over/under-performance
    grp = board.groupby("position")["xppg_diff"]
    z = (board["xppg_diff"] - grp.transform("mean")) / grp.transform("std")

    # elite dampening: shrink the POSITIVE (lucky) z for top-of-position players — they MAKE their
    # TDs (repeatable finishing), so their overperformance is talent, not luck. rank 1 keeps ~5% of
    # the "luck", tapering to full by ~rank 30. The buy-low (unlucky) side is never dampened.
    keep = (0.05 + 0.95 * (pos_rank - 1) / 30).clip(0.05, 1.0)
    z_adj = np.where(z > 0, z * keep, z)

    board["regression"] = np.select(
        [z_adj >= LUCKY_Z, z_adj <= -LUCKY_Z],
        ["TD-lucky", "Buy-low"],
        default="Sustainable",
    )
    board.loc[board["xppg"].isna(), "regression"] = ""     # rookies / <8 games -> no read

    board.to_csv("players_with_outcomes.csv", index=False)
    print(f"xPPG merged for {int(board['xppg'].notna().sum())} players · "
          f"{int((board.regression == 'TD-lucky').sum())} TD-lucky, "
          f"{int((board.regression == 'Buy-low').sum())} buy-low, "
          f"{int((board.regression == 'Sustainable').sum())} sustainable · "
          f"{int(board['switched_team'].sum())} changed teams (role signal neutralized)")


if __name__ == "__main__":
    main()
