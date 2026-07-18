# HANDOFF — Fantasy Draft Assistant

_Updated 2026-07-17 (autonomous session). Draft day: **July 31, 2026**._

## TL;DR
Live-sync bridge is now feature-complete and unit-verified. The DOM parser is locked to ESPN's
real draft room, junk can no longer mislead the app, and the league shape (teams / your seat /
your exact pick numbers) auto-configures from ESPN. **Nothing is committed yet** — the working
tree has the changes below. The last human-in-the-loop step is a live v0.3.0 mock run, then the
deploy push (your call — pushing auto-deploys to Streamlit Cloud).

## Uncommitted changes (working tree)
- `app_pages/draft.py` — roster popover on the main page (mobile fix); bridge poller reads `meta`
  + does mine-by-position; on-the-clock uses ESPN's exact picks when present.
- `bridge.py` — `fetch()` returns `{picks, meta}`; `resolve()` is junk-immune + supports
  `my_pick_nums` (mine-by-seat).
- `browser-bridge/espn-draft-bridge.user.js` — **v0.3.0** (DOM parser locked + ESPN league-shape meta).
- `tests/test_bridge.py` — new; 22 plain-assert regression tests (`.venv/bin/python tests/test_bridge.py`).
- `HANDOFF.md` — this file.

## What got done this session
1. **Roster-on-main / mobile fix (was open item #1) — DONE, verified.** A "My roster" popover now
   lives in the main top strip (`render_roster` / `render_reset` helpers, shared with the sidebar).
   Verified rendering on desktop **and** a 375px phone viewport (roster + Reset both reachable).
2. **Mock-draft parser tuning (was open item #2) — DONE, verified live.** Captured ESPN's real
   draft room and locked the scraper to the **"Pick History" grid** (`.pick-history-table` →
   `.public_fixedDataTableRow_main` → 6 `.public_fixedDataTableCell_main` cells). Clean player name
   = the `<a>` in cell 1; fantasy owner = cell 2. Accumulate-only Map keyed by pick# survives the
   grid's virtualization. Confirmed live: 67 real picks flowed clean, 0 unmatched vs the board.
3. **Junk-immunity fix.** The old scraper had spammed the mailbox with blob rows; `resolve()` was
   counting them as picks and telling the advisor the draft was ~800 picks deep. Now a row counts
   only if it resolves to a board player OR carries a valid pick number — blobs are ignored.
4. **League auto-config + mine-by-position (v0.3.0).** Userscript reads `mTeam`+`mDraftDetail` from
   ESPN's API (works in mocks — proven) and posts `meta:{teams, slot, myTeam, myPicks}` with the
   picks. `myPicks` is ESPN's authoritative per-team pick list, so it's correct for **any** draft
   order (snake / 3RR / linear). The app applies teams/slot once, and any pick landing on your seat
   auto-joins your roster — no dropdown, no name-matching. Simulated against the live 192-pick
   mailbox: mine-by-position picked exactly the players at seats #5, #20, #29, #44…

## Key facts learned (so we don't re-investigate)
- **ESPN REST is useless for the players in a MOCK** — `mDraftDetail` picks have `playerId:-1` and
  `mRoster` is empty; ESPN doesn't persist mock selections to the read API. So players come from the
  DOM. REST **is** reliable for team names + pick ORDER (that's the league-shape meta).
- ESPN's draft WebSocket speaks a terse token protocol (`AUTODRAFT 1 false`, etc.); the old keyword
  filter dropped real pick events. v0.3.0 captures all text frames for future use (DOM is the live
  source today).

## Open items — pick order (your call)
1. **Live-confirm v0.3.0** _(needs your browser — I can't drive your ESPN login)._ Load v0.3.0 in
   Tampermonkey → reload the ESPN draft page → `FAB.clear()` → run a mock. Check `FAB.meta()` shows
   `{teams, slot, myTeam, myPicks}`, and a pick at your seat auto-lands in "My roster". The app's
   bridge caption should read `seat N of 12 (auto)`. (I verified all the logic offline + the app
   boots clean; this is the last real-world confirmation.)
2. **Push to deploy (was open item #3).** Pushing `main` auto-deploys to Streamlit Community Cloud.
   Add `[bridge] url` (the Firebase RTDB URL) to Streamlit Cloud secrets so live sync works on the
   deployed app; confirm the `[espn]` block too if you still want the API fallback.

## Notes / possible follow-ups
- Mine-by-position is only as right as `slot`. With v0.3.0 meta feeding the real slot it's exact;
  in manual mode a wrong slot mis-flags picks (same as before). Reset (`do_reset`) intentionally
  keeps the league shape — only clears drafted/mine.
- To run the app locally against the live mailbox, set `FA_BRIDGE_URL` before launching Streamlit
  (dev env var path in `bridge.db_url()`); otherwise the app uses the `[espn]` secrets path.

## Ground rules (from CLAUDE.md — still apply)
- Walk through code before writing it, then pause for "go".
- Don't touch frozen pipeline scoring files unless asked.
- Flag data-quality issues instead of silently working around them.
