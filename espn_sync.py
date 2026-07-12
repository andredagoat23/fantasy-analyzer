"""Live ESPN draft sync (Phase 2).

Connects to an ESPN fantasy league via the unofficial v3 API (through the espn-api
library) and reads draft picks as they happen. Maps each ESPN pick to one of our
board players by espn_id (exact) or, failing that, normalized name. Pure Python —
app.py owns the credentials (via st.secrets) and the polling loop.
"""
import pandas as pd
from espn_api.football import League
from utils import normalize_name


def connect(league_id, year, espn_s2=None, swid=None):
    """Open a league connection. Raises on bad id / auth / network — caller handles it."""
    return League(league_id=int(league_id), year=int(year),
                  espn_s2=espn_s2 or None, swid=swid or None)


def build_maps(board):
    """Two lookups from our board: {espn_id -> full_name} and {normalized_name -> full_name}."""
    by_espn, by_name = {}, {}
    for name, eid in zip(board["full_name"], board.get("espn_id", pd.Series(index=board.index))):
        by_name[normalize_name(name)] = name
        if pd.notna(eid):
            by_espn[int(eid)] = name
    return by_espn, by_name


def _resolve(pick, by_espn, by_name):
    """ESPN pick -> our full_name (espn_id first, then name), or None if unmatched."""
    if pick.playerId in by_espn:
        return by_espn[pick.playerId]
    return by_name.get(normalize_name(pick.playerName))


def fetch_picks(league, by_espn, by_name):
    """Refresh the draft and return the picks made so far as a list of dicts.

    Each: {name (our full_name or None), espn_name, team_id, team_name, overall}.
    Empty list = draft hasn't started (or nothing picked yet).
    """
    league.refresh_draft()
    picks = []
    for i, p in enumerate(league.draft, 1):
        picks.append({
            "name": _resolve(p, by_espn, by_name),
            "espn_name": p.playerName,
            "team_id": p.team.team_id if p.team else None,
            "team_name": p.team.team_name if p.team else "",
            "overall": i,
        })
    return picks


def teams(league):
    """[(team_id, team_name)] so the user can pick which team is theirs."""
    return [(t.team_id, t.team_name) for t in league.teams]
