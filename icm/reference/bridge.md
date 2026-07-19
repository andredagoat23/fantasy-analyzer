# Live-Draft Bridge (Layer 3 — subsystem)

Live sync of the ESPN draft into the app, chosen over the ESPN API because a browser userscript works
live on any draft site (the ESPN read-API only reflects picks after the draft finalizes, and doesn't
expose mock-draft players at all).

## Flow
```
ESPN draft room  →  Tampermonkey userscript  →  Firebase RTDB "mailbox"  →  app polls it
```
- **Userscript:** `browser-bridge/espn-draft-bridge.user.js` (v0.3.0). Scrapes ESPN's "Pick History"
  grid and reads the league shape from ESPN's own API.
- **Mailbox:** Firebase RTDB `https://fantasy-analyzer-3741d-default-rtdb.firebaseio.com`, at
  `/draft.json`. Shape: `{"meta": {teams, slot, myTeam}, "picks": [{pick, player, team, mine?}, ...]}`.
- **App:** `bridge.py` (`fetch`, `resolve`) + the `poll_bridge` fragment in `draft.py`.

## Userscript scraper (LOCKED to real ESPN DOM)
ESPN's "Pick History" grid is a virtualized React `fixed-data-table`: `.pick-history-table` per round
→ `.public_fixedDataTableRow_main` rows → 6 `.public_fixedDataTableCell_main` cells in fixed order
`[pick#, player, fantasy-owner, 2025pts, projpts, rk]`. The clean player name is the `<a>` in cell 1
(cell text also mashes in NFL team + position + injury "Q" tag). Fantasy owner = cell 2. Picks
accumulate in a Map keyed by pick# so a scrolled-out (un-rendered) round can't drop picks.

## League shape (meta)
The userscript reads `mTeam`+`mDraftDetail` from ESPN's authenticated API (in-browser,
`credentials:'include'`) and posts `meta:{teams, slot, myTeam}`. The app applies teams/slot ONCE via
the `*_pending` path. NOTE: ESPN's read-API returns `playerId:-1` / empty rosters for MOCK drafts —
it's reliable for team names + pick order + your teamId, NOT for the drafted players (those come from
the DOM).

## `bridge.resolve(raw_picks, by_name, my_team=None)` — the rules
- **drafted:** every pick whose player resolves to the board (by `normalize_name`).
- **mine (the roster):** ONLY picks flagged `mine:true` by the userscript, OR whose fantasy owner ==
  `my_team`. `my_team` = the ESPN-detected team (`bridge_detected_team`) or the "Which team is yours?"
  dropdown. **Owner match is ground truth.** No team identified → empty roster (never guessed).
  ⚠️ A seat/pick-number `mine` path was tried and REMOVED — it pulled other teams' picks onto the
  roster (lesson L4). Do not reintroduce it.
- **total (on-the-clock count):** a row counts only if it resolves to a board player OR carries a
  valid pick number (keeps D/ST etc. counted); junk blobs are ignored so they can't inflate the count
  or mislead the advisor (lesson: junk immunity). Prefers ESPN's max pick number.

## On-the-clock pick numbers
Computed live in `draft.py` from the current `slot`+`teams` (standard snake), every rerun — NOT from
sticky state (lesson L5). `made = pick_count` when live-synced, else `len(drafted)`.

## Debug helpers (in the userscript console)
`FAB.dom()` (grid + scrape), `FAB.meta()` (league shape), `FAB.picks()`, `FAB.ws()`, `FAB.test()`
(fake pick end-to-end), `FAB.clear()` (wipe mailbox + local state — use between mocks).

## Config
`bridge.db_url()`: `FA_BRIDGE_URL` env (dev) first, else `[bridge] url` in Streamlit secrets. The
deployed app needs the `[bridge]` block in Streamlit Cloud secrets for live sync.

## Sleeper sync (`sleeper_sync.py`) — the second source, no userscript/Firebase
Sleeper has a PUBLIC read-only API, so the app polls it DIRECTLY (no browser bridge). `sleeper_sync`
normalizes Sleeper's `/draft/{id}` + `/picks` into the SAME `{meta, picks}` shape, so `bridge.resolve`
+ `bridge.my_dst` are REUSED unchanged. `_normalize()` is a pure function (unit-tested against the real
schema in `tests/test_sleeper.py`); `fetch()` wraps the two GETs; `user_id`/`list_drafts`/`season` back
the setup connect flow. `mine` is stamped per-pick from the API's own `draft_slot` (ground truth — not
the seat math L4 removed). Defenses come back as position `DEF` → formatted `"<Team> D/ST"` so `my_dst`
detects them (L9). Wiring: setup.py "Connect Sleeper" (username → pick draft → `sleeper_draft_id`);
draft.py `poll_sleeper` fragment (highest-priority branch when `sleeper_draft_id` is set). Works for
Sleeper MOCKS too (their API exposes mock picks; ESPN's doesn't). Rate limit 1000/min — we poll ~1/4s.
**Final verify pending:** a live Sleeper mock draft end-to-end (needs a real Sleeper account/draft_id).
