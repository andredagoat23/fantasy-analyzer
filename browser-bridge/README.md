# Draft Bridge — browser userscript

Gets your **live** ESPN draft picks into the Fantasy Analyzer app. A small script runs on
the ESPN draft page, watches picks happen, and posts them to a Firebase "mailbox" the app
reads every few seconds. Works while the draft is in progress (the ESPN API only shows picks
after the draft finishes).

```
ESPN draft page ──(userscript)──> Firebase mailbox ──(app polls)──> your board
```

## Install (one time, ~3 minutes)

1. Install the **Tampermonkey** extension (Chrome/Edge/Firefox/Safari) from your browser's
   extension store.
2. Open Tampermonkey → **Create a new script**.
3. Delete the template, paste in the contents of
   [`espn-draft-bridge.user.js`](espn-draft-bridge.user.js), and **File → Save** (Ctrl/Cmd-S).
4. (Optional) At the top of the script, set `MY_TEAM` to your exact ESPN team name so your
   own picks auto-fill your roster. Otherwise just pick your team in the app.

The `BRIDGE_URL` is already set to your Firebase mailbox.

## Test the pipe (no draft needed)

1. Open any ESPN fantasy page (e.g. `fantasy.espn.com`). A small **"FA Bridge"** badge
   appears bottom-right.
2. Press **F12** → **Console**, type `FAB.test()`, Enter. It fires one fake pick.
3. In the app's draft board, you should see "browser bridge · 1 pick received" and
   **Bijan Robinson** leave the board within a few seconds.
4. Run `FAB.clear()` to empty the mailbox again.

## Tune it on a mock draft

The script sends picks two ways — a WebSocket sniffer (most reliable) and a DOM scraper.
On a mock ESPN draft, open the console and run:

- `FAB.dom()` — shows what the DOM scraper is finding (so we fix the `SEL` selectors).
- `FAB.ws()` — dumps recent WebSocket messages (so we lock a parser to ESPN's real feed).
- `FAB.picks()` — shows the picks it's currently sending.

Paste that output back and we finalize the parser so it's rock-solid for draft day.

## Notes

- `DEBUG = true` prints activity to the console; flip to `false` once it's tuned.
- The mailbox URL with test-mode rules is readable/writable by anyone who has it — fine for a
  throwaway draft store. The rules auto-expire ~30 days after you created the database.
