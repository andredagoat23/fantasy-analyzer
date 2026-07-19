# Yahoo verification probe — scope (de-risk before building Yahoo sync)

**The one question that decides everything:** does Yahoo's `.../league/{league_key}/draftresults`
endpoint return picks **LIVE, during** the draft (updating within seconds as picks are made) — or only
**after** the draft finalizes? Research confirmed nobody documents this. It's the go/no-go:
- **Live** → build Yahoo the clean way: OAuth + poll the API (like Sleeper, but with auth). ~18% coverage.
- **Post-draft only** → Yahoo needs the browser-userscript path (like ESPN), a totally different build.

So the probe answers an **architecture** question, not just a detail — that's why it comes first.

## Why a probe, not just start the build
Two risks sit in front of Yahoo: (1) the live-vs-post question above, and (2) OAuth 2.0 in Streamlit is
fiddly. The probe answers #1 with the *minimum* auth scaffolding (a one-off token from a library, no UI
flow), so we don't sink a day into the full Streamlit OAuth build before knowing the API even works live.

## What the probe needs (all one-time, ~1–2 hrs total)
1. **A Yahoo developer app** — register at the [Yahoo developer portal](https://sports.yahoo.com/developer/),
   get `client_id` + `client_secret`. Redirect URI can be `oob`/localhost for a probe. (~15 min)
2. **A one-off OAuth 2.0 token** — do NOT build the Streamlit flow yet. Use an existing library
   (`yahoo_fantasy_api` + `yahoo-oauth`, or `YahooFantasyWrapper`) to get a `token.json` via the 3-legged
   flow once, from a script. (~20 min)
3. **A Yahoo draft to watch** — ideally a **Yahoo mock draft**; if the API can't see mocks (a key
   secondary finding), a free practice/real league draft. (Yahoo runs frequent public mock drafts.)

## The endpoints to hit (Fantasy v2, XML/JSON)
- `GET /fantasy/v2/game/nfl` → the season's `game_key`.
- `GET /fantasy/v2/users;use_login=1/games;game_keys=nfl/leagues` → my `league_key`(s) + my `team_key`.
- **`GET /fantasy/v2/league/{league_key}/draftresults`** → each pick: `pick`, `round`, `team_key`,
  `player_id/player_key`. ← the endpoint under test.
- `GET /fantasy/v2/league/{league_key}/settings` → `num_teams`, roster slots (for meta).
- `player_key` → name: `/fantasy/v2/players;player_keys=…` (for board matching via `normalize_name`).

## Procedure
1. Get token → resolve `game_key` → `league_key` → my `team_key`.
2. Open a Yahoo mock/live draft in the browser.
3. Run a ~40-line script that polls `draftresults` every 3–5s and prints each NEW pick with a wall-clock
   timestamp. Watch it against the actual draft room.

## PASS / FAIL
- **PASS:** a pick shows up in `draftresults` within a few seconds of being made in the room, pick after
  pick, all draft long.
- **FAIL:** `draftresults` stays empty / frozen until the draft completes (→ Yahoo needs the userscript path).

## Secondary answers to capture while there (they shape the build)
- **Mock-draft support:** can we even get a `league_key` for a Yahoo mock via the API? (If not, live sync
  only works for real leagues — a real UX limitation to know.)
- **"Mine" detection:** `team_key` per pick vs my auth'd `team_key` → clean owner match (our ground-truth rule).
- **Player mapping:** Yahoo player names vs our board (`normalize_name` + aliases) — spot-check ~20, esp. D/ST.
- **Rate limits + latency:** how many calls/hr Yahoo tolerates; how fresh the data is at a 3–5s poll.

## Output
A one-paragraph **go/no-go** + the notes above → either greenlight the OAuth-poll build (reusing
`bridge.resolve` like Sleeper, once picks are normalized to `{meta,picks}`) or pivot Yahoo to a userscript.

## Effort
~1–2 hours: app registration + token + the polling script + running it against one mock draft. Cheap
insurance against a multi-hour OAuth build aimed at an API that might not even be live.
