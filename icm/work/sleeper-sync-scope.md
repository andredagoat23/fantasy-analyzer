# Sleeper live-draft sync — scope / design (Stage 02 draft)

**Goal:** add live-draft sync for Sleeper leagues + mocks, the way the ESPN bridge does — but far
simpler, because Sleeper has a **public read-only API** (no auth). No userscript, no Firebase.

## Why Sleeper is the easy, high-ROI win
- **Public API, no OAuth.** Verified live: `api.sleeper.app` is reachable, players + draft endpoints are
  open. Rate limit 1000 calls/min (we poll ~1/2s = 30/min — trivial).
- **The app polls Sleeper directly** — unlike ESPN, no browser userscript scraping the DOM and no
  Firebase relay. Removes the two most fragile pieces of the ESPN path.
- **Mock drafts work too** (Sleeper exposes mock picks via the API — ESPN mocks do NOT via ESPN's API,
  which is why ESPN needs the DOM scraper).
- **`draft_slot` is authoritative per pick** → clean "mine" detection from the API (not our fragile
  seat math that L4 warned against — this is API ground truth, like the owner-match rule).

## The endpoints (verified against docs + live)
- `GET /v1/user/<username>` → `{user_id, ...}` (username → user_id)
- `GET /v1/user/<user_id>/drafts/nfl/<season>` → the user's drafts (to pick which one)
- `GET /v1/league/<league_id>/drafts` → a league's drafts (alt path)
- `GET /v1/draft/<draft_id>` → `settings.{teams, rounds, slots_*}`, `draft_order{user_id→slot}`,
  `slot_to_roster_id`, `status` ("drafting"/"complete"), `type` ("snake")
- `GET /v1/draft/<draft_id>/picks` → per pick: `pick_no, round, draft_slot, roster_id, picked_by,
  player_id, metadata{first_name,last_name,position,team,injury_status}`
- `GET /v1/players/nfl` → 12,200 players `{player_id→{full_name,position,team,...}}` (cache daily;
  actually optional — pick `metadata` already carries first/last/position/team).

## Architecture — reuse the existing resolve, add one adapter
The elegant fit: make Sleeper emit the SAME `{meta, picks}` shape the Firebase mailbox does, then
**reuse `bridge.resolve()` unchanged**. This is the "pluggable adapter" generalization in miniature.

New module `sleeper_sync.py` (pure Python, mirrors `bridge.py`, no Streamlit):
- `user_id(username)` — resolve username → user_id.
- `list_drafts(user_id, season)` — for the setup draft-picker.
- `fetch(draft_id)` → `{meta:{teams, slot, myTeam}, picks:[{pick, player, team, mine}]}`:
  - `meta.teams = draft.settings.teams`
  - `meta.slot  = draft.draft_order[my_user_id]` (my seat — authoritative)
  - each pick → `{pick: pick_no, player: f"{first} {last}", team: metadata.team,
    mine: (draft_slot == my_slot) or (picked_by == my_user_id)}`
  - **D/ST:** Sleeper's defense `player_id` is the team abbrev (e.g. "PIT"); map to `my_dst` the same
    way ESPN does (owner/slot + name), threaded via `build_context(my_dst=)` (lesson L9).
- Then `bridge.resolve(picks, by_name, my_team=my_slot_or_userid)` — UNCHANGED. Same drafted/mine/total
  rules, same junk-immunity, same "owner match is ground truth" (here: slot/user match).

`draft.py`: a Sleeper poll `st.fragment(run_every=...)` mirroring `poll_bridge` — calls
`sleeper_sync.fetch(draft_id)` → `bridge.resolve(...)` → same state writes (`drafted`, `mine`,
`pick_count`, `slot`/`teams` via `*_pending`), then `st.rerun(scope="app")`. Source is chosen by the
setup "Draft site" field (ESPN → Firebase poller; Sleeper → API poller).

`setup.py`: a "Connect Sleeper" control — enter **username** (fetch drafts → pick the live one) OR
paste a **draft_id** (from the draft URL). Store `sleeper_draft_id` + `sleeper_user_id` in session.

## What we can REUSE vs build
- **Reuse unchanged:** `bridge.resolve`, `normalize_name`/aliases, the on-the-clock pick math in
  draft.py, the roster/`my_dst` handling, the advisor — all downstream of the resolved `{meta,picks}`.
- **Build:** `sleeper_sync.py` (~120 lines), a setup connect UI (~40 lines), a Sleeper poll fragment in
  draft.py (~30 lines, mirrors poll_bridge), tests.

## Verify plan (Stage 04)
- Record real fixtures: run a Sleeper **mock draft**, save `/draft/<id>` + `/picks` JSON, and add
  cases to `tests/test_bridge.py` (Sleeper pick → normalized `{meta,picks}` → resolve → drafted/mine/DST).
- Drive it live end-to-end in a Sleeper mock (picks appear in the app, roster fills, advisor reacts) —
  the same bar the ESPN bridge was held to.

## Risks / notes
- **Name matching** = same class as ESPN (normalize_name + NAME_ALIASES); run `tools/name_audit.py`
  after. Sleeper uses full team-name defenses via team-abbrev id → handle in the DST map.
- **No auth needed**, but a private league's drafts still resolve by draft_id (drafts are public read).
- Rate limit is a non-issue at our poll cadence; still, poll every ~2–3s and only re-resolve on change.
- This is strictly ADDITIVE — ESPN path untouched; Sleeper is a second source behind the same resolve.

## Effort estimate
~½–1 focused session for a working Sleeper mock sync (adapter + setup UI + poller + fixtures), since
`resolve` and everything downstream is reused. Lowest-risk, highest-coverage next platform.
