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


def _resolve_id(pid, player_map, by_espn, by_name):
    """ESPN playerId -> our full_name: espn_id first, else ESPN's name (from player_map) normalized."""
    if pid in by_espn:
        return by_espn[pid]
    espn_name = player_map.get(pid)
    if isinstance(espn_name, str):
        return by_name.get(normalize_name(espn_name))
    return None


def fetch_picks(league, by_espn, by_name):
    """Return the picks made so far — WORKS DURING A LIVE DRAFT, not only after it finishes.

    espn-api's `league.draft` hides everything until draftDetail.drafted is True (i.e. the draft is
    fully complete), so a live in-progress draft looks empty. We instead read draftDetail.picks
    straight from the API each call and resolve each playerId to our board via the league's
    player_map (name-matched) — our espn_id coverage alone is too thin (~30% of the top).

    Each: {name (our full_name or None), espn_name, team_id, team_name, overall}.
    Empty list = nothing picked yet.
    """
    data = league.espn_request.get_league_draft()
    player_map = getattr(league, "player_map", {}) or {}
    picks = []
    for p in data.get("draftDetail", {}).get("picks", []):
        pid = p.get("playerId")
        if not isinstance(pid, int) or pid in (0, -1):   # empty / unmade slot (D/ST are -16xxx, kept)
            continue
        espn_name = player_map.get(pid, "")
        picks.append({
            "name": _resolve_id(pid, player_map, by_espn, by_name),
            "espn_name": espn_name if isinstance(espn_name, str) else "",
            "team_id": p.get("teamId"),
            "team_name": "",
            "overall": p.get("overallPickNumber"),
        })
    return picks


def teams(league):
    """[(team_id, team_name)] so the user can pick which team is theirs."""
    return [(t.team_id, t.team_name) for t in league.teams]
