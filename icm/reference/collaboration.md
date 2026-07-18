# Collaboration (Layer 3 — who you're working with and how)

This is the human side of the prime directive. Get the technical work right AND explain it at the
right level. Both matter here.

## Who the user is
- **A 14-year-old** for whom this fantasy-analyzer is among their first real scripts.
- Took **AP CSP** in the 2025–2026 school year and **got an A** — so programming *fundamentals* are
  solid: variables, loops, conditionals, functions.
- **Newer to Python specifically**, and to real-world topics like calling APIs, JSON, and libraries.
- Sharp about data quality — has personally caught real bugs (the FantasyPros `FPTS` = standard-
  scoring bug; Bijan's unrealistic 99.95% P(start); the age/sample-size risk inversion). Take their
  "this looks off" seriously; it's usually right.

## How to explain (feedback the user gave directly)
- **Don't over-explain the basics.** They explicitly asked to stop the super-in-depth explaining of
  everything after getting an A in AP CSP. Skip definitions of loops, variables, conditionals,
  functions — they know these.
- **Still explain, at their level:** Python-specific syntax/quirks and genuinely new real-world
  concepts (APIs, JSON, libraries, Streamlit's `session_state`/`cache_data`/`data_editor`/reruns).
  Concisely — explain the *why* behind a choice, not a tutorial.
- Net: assume fundamentals, teach the new stuff briefly. See CLAUDE.md "Rules for our collaboration."

## The collaboration contract (from CLAUDE.md — still binding)
1. **Walk through the code line-by-line BEFORE writing it, then PAUSE for "go."** (This is the
   Stage 02 → 03 gate — don't jump to Implement.) *Exception:* the user has, in some sessions, given
   blanket "just do it" autonomy for long unattended stretches — honor that when it's explicitly
   granted, but default to the walk-through-then-go rhythm.
2. Explain WHY a particular Streamlit widget/pattern was chosen, not just what it does.
3. If they ask for a "Hard NOT in v1.0" feature, remind them of the spec and defer to the right
   version — don't silently scope-creep.
4. **Flag data-quality issues before continuing** — never silently work around bad data (this is how
   the biggest catches happened).
5. **Never touch the frozen pipeline files** (`custom_scoring.py`, `compute_metrics.py`, etc.) unless
   explicitly asked. See `pipeline.md` for what they do.

## Where this is heading (context, not a mandate)
Right now it's a single-user tool for the user's own July 31, 2026 ESPN draft. The user has floated a
longer arc — family/friends test → eventually a public, ~$10/season product in a later season, with a
parent + Stripe + LLC + a legal-first "own your data" path (licensed FantasyPros/Vegas data is the
blocker). Treat that as background for why "make it feel like a real app" requests come up; it does
NOT change v1.0 scope. The near-term north star is: **fast, trustworthy, correct during a live draft —
we can't afford mistakes.**
