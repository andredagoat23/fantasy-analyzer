"""Browser-bridge live sync.

A small browser userscript running on the draft site (ESPN/Sleeper/Yahoo — any of them)
writes each pick into a Firebase Realtime Database "mailbox". This module reads that
mailbox and resolves every pick to one of our board players by normalized name. Because
the picks come from the browser (not a site API), it works live on ANY draft site.

Mailbox shape at  <db_url>/draft.json :
    {"picks": [{"player": "Bijan Robinson", "team": "Team A", "mine": false}, ...]}

Each pick: player + team names exactly as shown on the draft site; optional `mine` flag
the userscript sets on your own picks. app.py owns the URL (st.secrets); this is pure I/O.
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


def fetch_raw(url):
    """Read the mailbox once. Returns the list of raw pick dicts (empty list if nothing yet)."""
    r = requests.get(f"{url}/draft.json", timeout=4)
    r.raise_for_status()
    data = r.json() or {}
    picks = data.get("picks") if isinstance(data, dict) else data   # tolerate a bare list too
    return [p for p in (picks or []) if isinstance(p, dict)]


def resolve(raw_picks, by_name, my_team=None):
    """Raw browser picks -> (drafted set, mine set, sorted team names seen, total pick count).

    Player is matched to our board by normalized name. A pick lands in `mine` if the userscript
    flagged it (`mine: true`) or its team equals the team you selected as yours. `total` counts
    EVERY pick received (incl. any that don't map to our board, e.g. D/ST) so the on-the-clock
    number stays exact — same rule as the ESPN sync.
    """
    drafted, mine, teams = set(), set(), set()
    for p in raw_picks:
        team = p.get("team")
        if team:
            teams.add(team)
        name = by_name.get(normalize_name(p.get("player", "")))
        if name:
            drafted.add(name)
            if p.get("mine") or (my_team and team == my_team):
                mine.add(name)
    return drafted, mine, sorted(teams), len(raw_picks)
