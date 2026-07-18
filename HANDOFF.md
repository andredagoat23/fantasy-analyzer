# HANDOFF — Fantasy Draft Assistant

_Updated 2026-07-18. Draft day: **July 31, 2026**. Working tree clean; everything committed on `main`._

## First thing tomorrow
**Read `icm/CONTEXT.md`** — this project now runs on an ICM workspace (methodology-as-filesystem)
that routes every request through reproduce → design → implement → verify → ship. `CLAUDE.md` points
to it up top. The durable knowledge lives in `icm/reference/` (engineering principles, lessons from
every past mistake, the draft-strategy source of truth, architecture, bridge).

## Git state
- Branch `main`, tree clean. All session work is committed **locally**; **nothing pushed**.
- Pushing `main` auto-deploys to Streamlit Cloud — that's your call (item below). ~12 commits are
  unpushed, ending at the VONA work (`d54c0d3`, `4ba2558`).

## What got done this session (all committed + verified)
- **Live sync fully working & verified on live mocks:** v0.3.0 userscript (locked ESPN parser +
  league-shape meta), junk immunity, league auto-config.
- **Roster fix:** `mine` = fantasy-owner match ONLY (was polluted by seat-inference — other teams'
  picks landed on your roster). Verified 0 leaks live.
- **On-the-clock fix:** pick tracking computes live from your slot; dropped sticky `bridge_my_picks`.
- **Advisor overhaul → VONA.** The recommender now drafts by **VONA (Value Over Next Available)** —
  each player's VOLS minus the best same-position player ADP says could still be there at your next
  pick. Tiers deleted (advisor + board). Wheel-back is now structural (grab "gone", wait "safe").
  Roster gate hardened: RB/WR always draftable for depth; a 2nd QB/TE is blocked (VONA shown as
  `n/a` so the model can't chase it). Verified on real data + live API calls.
- **ICM workspace** added (`icm/`) + kept in sync with the code.
- **`tools/name_audit.py`** (read-only) — run before draft day after any board regen.

## Open items (your call)
1. **Fresh mock to pressure-test VONA** — sort the board by the new **VONA** column, click
   **Recommend my pick** across rounds, and sanity-check the calls against your gut. That's the real
   judge of the advisor now.
2. **Push to deploy** — when ready, push `main`. Add the `[bridge] url` (and confirm `[espn]`) blocks
   to Streamlit Cloud secrets so live sync + the advisor work on the deployed app.

## Known data flag (not a bug — see icm/reference/lessons.md L6)
Tyreek Hill is absent from the board (no FantasyPros 2026 projection → dropped by `value_board.py`).
Low impact; pipeline is frozen, so it's flagged, not fixed. `tools/name_audit.py` catches this class.

## Ground rules (still apply)
Walk through code before writing; pause for "go". Don't touch frozen pipeline scoring files. Flag
data issues, don't work around them. Verify with real data; never fabricate. (All in
`icm/reference/engineering-principles.md`.)
