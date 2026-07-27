"""21 — Build a REAL pick-by-pick draft corpus from Sleeper's public API (L48 run-dynamics research).

Why: the positional-run read (L48) shipped ADVISORY-only because "we hold no pick-by-pick corpus."
Sleeper's public, no-auth API IS one: completed drafts expose every pick in order with position +
draft_slot. This crawler snowballs from seed usernames -> their drafts -> those drafts' participants
(draft_order keys + picked_by) -> their drafts, collecting COMPLETED 2026 12-team NFL SNAKE drafts.

Respectful crawling: documented rate limit is 1000 calls/min; we throttle to ~6/s (~360/min) with a
hard request cap. Only public read-only GETs (the same API the app's live sync uses).

Privacy: the stored corpus keeps NO user ids — each pick keeps only (pick_no, draft_slot, position,
human) where human = picked_by was non-empty (empty = CPU/autopick slot in mocks). User ids live only
in the in-memory crawl frontier.

Output: sleeper_drafts_2026.jsonl (one draft per line; resume-safe — reruns skip known draft_ids).
Run:  .venv/bin/python icm/work/mc_research/21_sleeper_run_corpus.py
"""
import json
import os
import time
from collections import deque

import requests

API = "https://api.sleeper.app/v1"
T = 6
SLEEP = 0.15                # ~6 req/s, ~1/3 of the documented limit
MAX_REQUESTS = 3000         # hard cap for the whole crawl
MAX_DRAFTS = 300            # stop once we have this many kept ONE-QB drafts (SF kept as robustness)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sleeper_drafts_2026.jsonl")

SEED_USERNAMES = ["ben", "sleeper", "john", "mike", "matt", "josh", "jake", "ryan", "sam",
                  "jordan", "will", "jack", "luke", "kyle", "cody", "tony", "paul", "sean",
                  "joe", "tom", "james", "david", "aaron", "jason", "justin", "austin",
                  "brandon", "logan", "hunter", "connor"]

req_count = 0


def get(path):
    """Throttled GET -> parsed JSON (None on any failure). Counts toward the hard cap."""
    global req_count
    if req_count >= MAX_REQUESTS:
        raise RuntimeError("request cap reached")
    req_count += 1
    time.sleep(SLEEP)
    try:
        r = requests.get(f"{API}{path}", timeout=T)
        if r.status_code == 429:          # back off once if we ever get throttled
            time.sleep(5)
            r = requests.get(f"{API}{path}", timeout=T)
        if r.status_code != 200:
            return None
        return r.json()
    except requests.RequestException:
        return None


def keepable(d):
    """A draft summary we want: completed 2026 NFL 12-team snake, >=14 rounds."""
    st = d.get("settings") or {}
    return (d.get("type") == "snake" and d.get("status") == "complete"
            and str(d.get("season")) == "2026" and d.get("sport", "nfl") == "nfl"
            and st.get("teams") == 12 and (st.get("rounds") or 0) >= 14)


# Roster-slot fields we store per draft. The first crawl showed ~half of Sleeper drafts are
# SUPERFLEX/2QB — a different game for run dynamics (QB is effectively 2-start there), so the
# analysis MUST segment by format. The user's league is 1QB.
SLOT_KEYS = ("slots_qb", "slots_super_flex", "slots_rb", "slots_wr", "slots_te", "slots_flex")


def slotinfo(meta):
    st = (meta or {}).get("settings") or {}
    return {k: st.get(k) for k in SLOT_KEYS}


def is_1qb(row):
    return row.get("slots_qb") == 1 and not row.get("slots_super_flex")


def main():
    rows_by_id = {}
    if os.path.exists(OUT):
        with open(OUT) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    rows_by_id[r["draft_id"]] = r
                except Exception:
                    pass
    # self-heal: backfill roster-slot fields for rows collected before we stored them
    missing = [i for i, r in rows_by_id.items() if "slots_qb" not in r]
    if missing:
        print(f"backfilling slots for {len(missing)} drafts")
        for did in missing:
            meta = get(f"/draft/{did}")
            if meta:
                rows_by_id[did].update(slotinfo(meta))
        with open(OUT, "w") as f:
            for r in rows_by_id.values():
                f.write(json.dumps(r) + "\n")
    known = set(rows_by_id)
    kept1 = sum(1 for r in rows_by_id.values() if is_1qb(r))
    print(f"resuming with {len(known)} drafts on disk ({kept1} are 1QB)" if known else "fresh crawl")

    frontier = deque()
    seen_users = set()

    # Seed: usernames -> user_ids -> (their drafts' participants join the frontier too)
    for name in SEED_USERNAMES:
        u = get(f"/user/{name}")
        if u and u.get("user_id"):
            frontier.append(u["user_id"])

    out = open(OUT, "a")
    try:
        while frontier and kept1 < MAX_DRAFTS:
            uid = frontier.popleft()
            if uid in seen_users:
                continue
            seen_users.add(uid)
            drafts = get(f"/user/{uid}/drafts/nfl/2026") or []
            for d in drafts:
                did = d.get("draft_id")
                if not did:
                    continue
                # participants of ANY of the user's drafts feed the frontier (active drafters)
                meta = None
                if keepable(d) and did not in known:
                    meta = get(f"/draft/{did}")
                    if not meta or not keepable(meta):
                        continue
                    picks = get(f"/draft/{did}/picks") or []
                    st = meta.get("settings") or {}
                    exp = st.get("teams", 0) * st.get("rounds", 0)
                    if len(picks) < exp:      # "complete" but short payload -> skip
                        continue
                    rows = [{"no": p.get("pick_no"), "slot": p.get("draft_slot"),
                             "pos": ((p.get("metadata") or {}).get("position") or "").upper(),
                             "human": bool(p.get("picked_by"))} for p in picks]
                    row = {"draft_id": did, "league_id": meta.get("league_id"),
                           "teams": st.get("teams"), "rounds": st.get("rounds"),
                           "created": meta.get("created"), **slotinfo(meta), "picks": rows}
                    out.write(json.dumps(row) + "\n")
                    out.flush()
                    known.add(did)
                    if is_1qb(row):
                        kept1 += 1
                        if kept1 % 25 == 0:
                            print(f"  kept {kept1} 1QB drafts ({len(known)} total) · "
                                  f"{req_count} requests · frontier {len(frontier)}")
                    for u2 in (meta.get("draft_order") or {}):
                        if u2 not in seen_users:
                            frontier.append(u2)
                    if kept1 >= MAX_DRAFTS:
                        break
                elif did not in known and len(frontier) < 4000:
                    # cheap frontier growth: participants of non-kept drafts too (one meta call),
                    # but only while the frontier needs feeding
                    if len(frontier) < 300:
                        meta = get(f"/draft/{did}")
                        for u2 in ((meta or {}).get("draft_order") or {}):
                            if u2 not in seen_users:
                                frontier.append(u2)
    except RuntimeError as e:
        print(f"stopped: {e}")
    finally:
        out.close()
    print(f"DONE: {kept1} 1QB drafts ({len(known)} total) · {req_count} requests · "
          f"{len(seen_users)} users visited")


if __name__ == "__main__":
    main()
