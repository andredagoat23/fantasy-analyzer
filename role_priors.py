"""Role-share priors: every board player's PREVIOUS-season workload share -> role_data.csv.

Why (L31): the handcuff/late-round research showed the single strongest predictor of a backup paying
off is the share of his team's workload he ALREADY commands — carries for RBs, targets for WR/TE.
The board has snap_share_2025 but not carry share, and snap share conflates pass-blocking/special
usage; carry share is the signal the research validated. This computes, from the local research
weekly data (gitignored, same source as cohort_priors), each player's 2025 share of his primary
team's carries (RB) or targets (WR/TE), plus his team's 2025 workload concentration.

Run manually after a board rebuild (same cadence as cohort_priors.py / sos_priors.py):
    .venv/bin/python role_priors.py
Reads:  icm/work/mc_research/weekly.parquet, value_board.csv
Writes: role_data.csv (committed — the deployed advisor reads it; missing file -> feature off)
"""
import os

import numpy as np
import pandas as pd

from utils import normalize_name

WEEKLY = "icm/work/mc_research/weekly.parquet"
SEASON = 2025          # the completed season the shares describe


def build():
    if not os.path.exists(WEEKLY):
        raise SystemExit(f"research weekly data missing: {WEEKLY} — rebuild via icm/work/mc_research/01")
    w = pd.read_parquet(WEEKLY)
    w = w[(w.season == SEASON) & (w.season_type == "REG")].copy()
    w["carries"] = w["carries"].fillna(0)
    w["targets"] = w["targets"].fillna(0)
    w["pts"] = w["fantasy_points_ppr"].fillna(0)

    rows = []
    for pos, col in [("RB", "carries"), ("WR", "targets"), ("TE", "targets"), ("QB", "carries")]:
        g = w[w.position == pos]
        # SHARE is per-stint (his role in that room) — keep the primary (most-weeks) stint.
        per = (g.groupby(["player_id", "player_display_name", "team"])
                .agg(wl=(col, "sum"), wks=("week", "nunique")).reset_index())
        team_tot = g.groupby("team")[col].sum().rename("team_tot")
        per = per.merge(team_tot, on="team")
        per["share"] = np.where(per.team_tot > 0, per.wl / per.team_tot, np.nan)
        per = per.sort_values("wks").groupby("player_id").tail(1)      # primary stint
        # PPG/WEEKS are FULL-SEASON (across every stint): the injury-discount fade proxies
        # games-missed with weeks played, and the research computed that on full seasons — a
        # per-stint count falsely marks a healthy midseason-traded player as injured (the
        # Shaheed bug, caught in adversarial code review).
        season = (g.groupby("player_id")
                   .agg(wks_all=("week", "nunique"), pts_all=("pts", "sum")).reset_index())
        per = per.merge(season, on="player_id", how="left")
        for r in per.itertuples():
            rows.append({"name": r.player_display_name, "position": pos,
                         "team_2025": r.team, "share_2025": round(float(r.share), 4),
                         "workload_2025": int(r.wl), "weeks_2025": int(r.wks_all),
                         "ppg_2025": round(float(r.pts_all) / max(int(r.wks_all), 1), 2)})
    out = pd.DataFrame(rows)
    out["nn"] = out["name"].apply(normalize_name)
    out = out.drop_duplicates("nn", keep="first")

    # NFL draft capital (for the young high-capital TE dart, L31/B6) — same source cohort_priors uses
    try:
        import nflreadpy as nfl
        ros = (nfl.load_rosters(seasons=[SEASON + 1]).to_pandas()
                  .dropna(subset=["full_name"]).drop_duplicates("full_name"))
        ros["nn"] = ros["full_name"].apply(normalize_name)
        out = out.merge(ros[["nn", "draft_number"]].rename(columns={"draft_number": "nfl_pick"}),
                        on="nn", how="left")
    except Exception as e:                        # offline regen still produces the core columns
        print(f"  (nfl_pick skipped: {e})")
        out["nfl_pick"] = np.nan

    # BOARD-FIRST assembly (adversarial-review fix): EVERY board skill player gets a row — rookies
    # and 2025 absentees included — so the advisor's price-band logic (pos_adp_rank) and capital
    # lookups never silently miss. 2025 workload fields stay NaN where no season exists; the reads
    # treat NaN as "no role data", which is the truthful state.
    # pos_adp_rank = the market's positional price (rank of ADP within position on the FULL board) —
    # the research's price bands (RB31-70 etc.) are defined on this, so it ships precomputed.
    board = pd.read_csv("value_board.csv")
    board["nn"] = board["full_name"].apply(normalize_name)
    board["position"] = board["pos_label"].str.replace(r"\d+$", "", regex=True)
    board["pos_adp_rank"] = board.groupby("position")["adp_rank"].rank(method="first")
    board = board[board["position"].isin(["QB", "RB", "WR", "TE"])]
    # nflverse drops suffixes the board keeps ("Chris Godwin" vs "Chris Godwin Jr") — remap unmatched
    # weekly rows onto the BOARD's nn via a suffix-stripped key so the advisor's lookups (board-keyed)
    # actually hit. Without this a suffixed player silently has no role row (the Godwin bug, L31).
    strip = lambda n: " ".join(t for t in n.split() if t not in {"jr", "sr", "ii", "iii", "iv", "v"})
    b_by_stripped = {}
    for nn in board["nn"]:
        b_by_stripped.setdefault(strip(nn), nn)
    out["nn"] = out["nn"].map(lambda nn: nn if nn in set(board["nn"]) else b_by_stripped.get(strip(nn), nn))
    out = out.drop_duplicates("nn", keep="first")
    kept = board[["nn", "full_name", "position", "pos_adp_rank", "draft_pick"]].merge(
        out.drop(columns=["name", "position"]), on="nn", how="left")
    # NFL capital: roster join first, the board's own draft_pick (rookies) as fallback
    kept["nfl_pick"] = kept["nfl_pick"].fillna(kept["draft_pick"])
    kept = kept.drop(columns="draft_pick").rename(columns={"full_name": "name"})
    kept.to_csv("role_data.csv", index=False)
    print(f"role_data.csv: {len(kept)} board players with {SEASON} shares "
          f"(RB {sum(kept.position=='RB')}, WR {sum(kept.position=='WR')}, TE {sum(kept.position=='TE')})")
    for nm in ["Jaylen Warren", "Kenny Gainwell", "Justice Hill", "Alvin Kamara"]:
        r = kept[kept.name.str.contains(nm.split()[-1], case=False) & kept.name.str.contains(nm.split()[0], case=False)]
        if len(r):
            x = r.iloc[0]
            print(f"  {x['name']:20} {x.position} {x.team_2025} share {x.share_2025:.0%} ({x.workload_2025} {'carries' if x.position=='RB' else 'targets'})")
    return kept


if __name__ == "__main__":
    build()
