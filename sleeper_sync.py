"""Sleeper live-draft sync.

Sleeper has a PUBLIC, read-only API (no auth) — so unlike the ESPN path there is NO browser userscript
and NO Firebase relay: the app polls Sleeper directly. This module normalizes each Sleeper pick into
the SAME `{meta, picks}` shape the Firebase mailbox emits, so `bridge.resolve()` consumes it unchanged
(same drafted/mine/total rules, junk-immunity, and D/ST handling). Sleeper mock drafts expose picks via
the API too, so this works for mocks (ESPN mocks don't — hence ESPN's DOM scraper).

Docs: https://docs.sleeper.com  ·  rate limit 1000 calls/min (we poll ~1 every few sec).
Pick fields we use: pick_no, draft_slot, picked_by, metadata{first_name,last_name,position,team}.
Draft fields: settings.teams, draft_order{user_id -> slot}, status.
"""
import requests

API = "https://api.sleeper.app/v1"
_TIMEOUT = 6


def season():
    """Current NFL season per Sleeper's own state (authoritative — the draft year isn't just the
    calendar year once the season rolls over). Falls back to the calendar year if unreachable."""
    try:
        r = requests.get(f"{API}/state/nfl", timeout=_TIMEOUT)
        r.raise_for_status()
        s = (r.json() or {}).get("season")
        if s:
            return str(s)
    except requests.RequestException:
        pass
    import datetime
    return str(datetime.date.today().year)


def user_id(username):
    """Sleeper username -> user_id, or None if not found / unreachable. First step of setup."""
    try:
        r = requests.get(f"{API}/user/{username}", timeout=_TIMEOUT)
        if r.status_code != 200:
            return None
        return (r.json() or {}).get("user_id")
    except requests.RequestException:
        return None


def list_drafts(uid, season):
    """The user's NFL drafts for a season (Sleeper returns most-recent first) — for the setup picker.
    Returns [] on any failure so the UI can show 'none found' rather than crash."""
    try:
        r = requests.get(f"{API}/user/{uid}/drafts/nfl/{season}", timeout=_TIMEOUT)
        r.raise_for_status()
        out = []
        for d in (r.json() or []):
            st = d.get("settings") or {}
            out.append({"draft_id": d.get("draft_id"), "status": d.get("status"),
                        "type": d.get("type"), "teams": st.get("teams"),
                        "name": (d.get("metadata") or {}).get("name") or d.get("draft_id")})
        return out
    except requests.RequestException:
        return []


def _player(md):
    """Display name from a pick's metadata. Defenses come back as position 'DEF' with the team name in
    last_name — format them as '<Team> D/ST' so bridge.my_dst() detects them (defenses aren't on the
    board, so they only ever surface via that name check)."""
    first = (md.get("first_name") or "").strip()
    last = (md.get("last_name") or "").strip()
    if (md.get("position") or "").upper() in ("DEF", "DST"):
        return f"{last or (md.get('team') or '')} D/ST".strip()
    return f"{first} {last}".strip()


def _normalize(draft, raw_picks, my_user_id=None):
    """Pure transform (no I/O): Sleeper draft JSON + picks JSON -> {"meta": {teams, slot, myTeam},
    "picks": [{pick, player, team, mine}]} in the Firebase-mailbox shape bridge.resolve() consumes.

    `mine` is Sleeper's authoritative `draft_slot` (my seat, from draft_order[my_user_id]) or
    `picked_by == my_user_id` — API ground truth, NOT the seat-math inference that L4 removed.
    """
    settings = (draft or {}).get("settings") or {}
    order = (draft or {}).get("draft_order") or {}
    my_slot = order.get(my_user_id) if my_user_id else None
    meta = {"teams": settings.get("teams"), "slot": my_slot, "myTeam": my_user_id}
    picks = []
    for p in (raw_picks or []):
        md = p.get("metadata") or {}
        slot = p.get("draft_slot")
        mine = bool((my_slot is not None and slot == my_slot)
                    or (my_user_id and p.get("picked_by") == my_user_id))
        picks.append({"pick": p.get("pick_no"), "player": _player(md),
                      "team": f"Team {slot}" if slot else None, "mine": mine})
    return {"meta": meta, "picks": picks}


def fetch(draft_id, my_user_id=None):
    """Poll a Sleeper draft once -> the normalized {meta, picks}. Two public GETs (draft + picks),
    well under the 1000/min limit. Raises requests.RequestException on a network error (the poller
    catches it and keeps the last state)."""
    dr = requests.get(f"{API}/draft/{draft_id}", timeout=_TIMEOUT)
    dr.raise_for_status()
    pr = requests.get(f"{API}/draft/{draft_id}/picks", timeout=_TIMEOUT)
    pr.raise_for_status()
    return _normalize(dr.json() or {}, pr.json() or [], my_user_id)
