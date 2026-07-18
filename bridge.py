"""Browser-bridge live sync.

A small browser userscript running on the draft site (ESPN/Sleeper/Yahoo — any of them)
writes each pick into a Firebase Realtime Database "mailbox". This module reads that
mailbox and resolves every pick to one of our board players by normalized name. Because
the picks come from the browser (not a site API), it works live on ANY draft site.

Mailbox shape at  <db_url>/draft.json :
    {"meta":  {"teams": 12, "slot": 5, "myTeam": "Team A", "myPicks": [5, 20, 29, ...]},
     "picks": [{"pick": 1, "player": "Bijan Robinson", "team": "Team A", "mine": false}, ...]}

Each pick: player + team names exactly as shown on the draft site, plus its overall pick number;
optional `mine` flag the userscript sets on your own picks. `meta` (optional) carries the league
shape the userscript read from ESPN's API — team count, your seat, and your exact pick numbers for
whatever draft order the league uses. app.py owns the URL (st.secrets); this is pure I/O.
"""
import os

import requests

from utils import normalize_name


def db_url():
    """Firebase mailbox URL: FA_BRIDGE_URL env (dev) first, else [bridge] url in secrets. None = off."""
    url = os.environ.get("FA_BRIDGE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("bridge", {}).get("url")
        except Exception:
            url = None
    return url.rstrip("/") if url else None


def fetch(url):
    """Read the mailbox once. Returns {"picks": [pick dicts], "meta": {league shape}}.

    Tolerates the old picks-only shapes (a bare list, or {"picks": [...]}) — those just come back
    with an empty meta, so an older userscript keeps working.
    """
    r = requests.get(f"{url}/draft.json", timeout=4)
    r.raise_for_status()
    data = r.json() or {}
    if isinstance(data, list):                  # bare list of picks
        picks, meta = data, {}
    else:
        picks = data.get("picks") or []
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    return {"picks": [p for p in picks if isinstance(p, dict)], "meta": meta}


def fetch_raw(url):
    """Back-compat: just the list of raw pick dicts."""
    return fetch(url)["picks"]


def _pick_no(p):
    """The overall pick number if this row carries a valid one (v0.2.0 stamps it on every row),
    else None. bool is excluded because it's an int subclass in Python."""
    n = p.get("pick")
    return n if isinstance(n, int) and not isinstance(n, bool) and n >= 1 else None


def my_dst(raw_picks, my_team=None):
    """The D/ST you drafted (its name), if any — detected by owner + a D/ST-looking name. Defenses
    aren't in value_board.csv, so they never enter `mine` via resolve(); this is the only way the
    app/advisor learns you have one. Returns None if you haven't drafted a D/ST."""
    for p in raw_picks:
        name = str(p.get("player", ""))
        mine = p.get("mine") or (my_team and p.get("team") == my_team)
        if mine and ("D/ST" in name.upper() or name.upper().endswith(" DST") or "DEFENSE" in name.upper()):
            return name
    return None


def resolve(raw_picks, by_name, my_team=None):
    """Raw browser picks -> (drafted set, mine set, sorted team names seen, total pick count).

    Player is matched to our board by normalized name. A pick lands in `mine` ONLY if it is
    definitively yours: the userscript flagged it (`mine: true`), or its fantasy owner equals your
    team (`my_team` — auto-detected from ESPN, or the team you picked in the dropdown). This is
    ground truth from the draft site's own data, so it never claims another team's pick.

    (An earlier version also flagged `mine` by seat/pick-number math; that mis-fired whenever the
    seat was even slightly off and grabbed OTHER teams' picks onto your roster — removed.)

    Only REAL picks count: a row must either resolve to a board player OR carry a valid pick
    number (the latter keeps D/ST picks — which aren't on our board — in the on-the-clock count,
    same rule as the ESPN sync). Junk rows (a stale/mis-scrape blob that matches no player and has
    no pick number) are ignored, so they can't inflate the count or mislead the advisor.
    """
    drafted, mine, teams = set(), set(), set()
    counted = 0
    for p in raw_picks:
        name = by_name.get(normalize_name(p.get("player", "")))
        if not name and _pick_no(p) is None:
            continue                      # junk row — not a real pick
        team = p.get("team")
        if team:
            teams.add(team)
        if name:
            drafted.add(name)
            if p.get("mine") or (my_team and team == my_team):
                mine.add(name)
        counted += 1
    # "How far along" prefers ESPN's own pick numbering — exact even if a row is briefly missing
    # from the grid — and falls back to the count of real picks for sites without pick numbers.
    max_pick = max((_pick_no(p) or 0 for p in raw_picks), default=0)
    return drafted, mine, sorted(teams), max(counted, max_pick)
