# Fantasy Analyzer — polish & roadmap

Running to-do list. Checked = done. "Needs you" = things only you can do (I can't touch secrets, Google Cloud, or pick the jingle).

## Genuine app feel (UI polish — my work)
- [ ] Setup page as clickable **cards/sections** with a status each (✓ set / needs attention), instead of one long scroll — the "different blocks to go do things" ask
- [ ] Draft page: group the controls into cleaner sections/tabs (draft position · pick tracking · advisor · board) so it's not all out in the open at once
- [ ] Hide the remaining Streamlit chrome app-wide (footer, top-right menu) for a true product feel — keep only what's useful on draft day
- [ ] App header / brand lockup polish (`st.logo`, a consistent brand bar across pages)
- [ ] Nicer empty states (empty My roster, "no players drafted yet", advisor first-run)
- [ ] Mobile / responsive pass (compact board, controls wrapping, login on a phone)
- [ ] Account menu: show name / avatar once Google sign-in is on

## Before charging a dollar — legal/business gate (do FIRST, with Dad)
This is the real blocker to a paid product. Free personal use = fine. Paid = these must be solved.
- [ ] **Get Dad in the loop** — payments (Stripe) need someone 18+ and likely an LLC; a 14-year-old can't take money or sign a data license.
- [ ] **Licensed data can't ship in a paid product as-is:**
  - FantasyPros **ECR + ADP** (`load_ecr.py`, `load_fp_adp.py`) — licensed.
  - Vegas totals from **firstdown.studio** (`data/vegas_*.csv`) — scraped/gray-area.
  - **espn-api** live sync — unofficial endpoints, against ESPN ToS for commercial use.
  - Paths: (a) **own your projections/rankings** (hardest, but the real moat — you already have the modeling), (b) pay to license, or (c) bring-your-own-CSV (fastest legal path, but weakens the product).
- [ ] Per-user API cost: today the advisor spends YOUR Anthropic key for everyone — a paid product needs metering/limits or bring-your-own-key.

## Product / v2.0 (bigger lifts)
- [ ] **Per-league re-scoring** — run the pipeline against a user's custom scoring so the BOARD itself matches their league (not just the advisor). Needs a backend; this is the core problem for going public/paid.
- [ ] Accounts + payments for the planned $10/season public release
- [ ] Multi-site draft sync beyond ESPN (Sleeper is easiest — free public API)

## Needs you (I can't do these)
- [ ] Set `app_password` in Streamlit Cloud → Settings → Secrets to gate the deployed app (until then the public URL is open and anyone can spend the API key)
- [ ] Wire Google sign-in: create a Google Cloud OAuth client → add the `[auth]` block to secrets (checklist in `.streamlit/secrets.toml.example`)
- [ ] Pick the draft jingle: drop `assets/draft_theme.mp3` (tell me the source and I'll flag if it's copyrighted — the real Fox/ESPN/NFL themes are)
- [ ] Create the family ESPN test league → give me the league ID (cookies go in secrets) → validate live draft sync
- [ ] Day-before-draft: re-run `run_all.py` + refresh Vegas numbers, then push the regenerated board

## Recently done
- [x] Login landing page (branded front door with hero + sign-in card)
- [x] Custom scoring block with AI "decipher"
- [x] League size max 20; draft slot capped at league size
- [x] "Enter the draft" same-tab nav + hidden auto-play fanfare
- [x] Multi-page app (login gate → Setup → Draft board) + per-user saved setup
