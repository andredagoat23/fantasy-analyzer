"""FA / signing watch (read-only) — which draftable-ADP players are MISSING from the board, and why.

The board (value_board.py) DROPS no-team free agents and NaN-projection players, so a notable unsigned
FA (e.g. Stefon Diggs) or a player with no FantasyPros projection is correctly absent. FantasyPros can't
project a player who has no team, so such a player only reappears the first time the pipeline is
regenerated AFTER he signs. This tool cross-checks the draftable ESPN-ADP pool against the board and
against Sleeper's live player feed, so you see:

  - who is UNSIGNED right now (watch these — the moment Sleeper flips their `team`, re-run run_all.py),
  - who HAS a team but is still off the board (investigate: injured / missing projection / name mismatch).

Sleeper's structured `injury_status` is only reliably populated IN-SEASON, so in the offseason health is
a NEWS-judgment call, not something this tool asserts — the reliable signal here is `team` (signed or not).

Run:  .venv/bin/python tools/fa_watch.py
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests

from utils import normalize_name

TOP_N = 200                                            # the draftable range of ESPN ADP to watch
TEAMS = 12                                             # for the round estimate
SLEEPER = "https://api.sleeper.app/v1/players/nfl"


def rnd(adp):
    return f"R{int(adp // TEAMS) + 1}"


def news_days(ms):
    if not ms:
        return None
    return (datetime.now(timezone.utc) - datetime.fromtimestamp(ms / 1000, timezone.utc)).days


def news_age(days):
    if days is None:
        return "?"
    return "today" if days == 0 else f"{days}d ago"


# --- the draftable pool (top-N ESPN ADP) vs what's on the board ---
board = pd.read_csv("value_board.csv")
on_board = {normalize_name(n) for n in board["full_name"].dropna()}
adp = pd.read_csv("players_with_adp.csv")
adp = adp[adp["position"] != "DEF"].dropna(subset=["adp_rank"]).nsmallest(TOP_N, "adp_rank")
missing = adp[~adp["full_name"].apply(normalize_name).isin(on_board)].copy()
# ESPN's ADP tail is full of retired/fringe sentinels (Philip Rivers at "ADP 170"). Sleeper's `active`
# flag doesn't catch them, but NEWS RECENCY does: a real FA in the market (Diggs) has news days old; a
# dormant name has news months stale. So we sort unsigned by news recency and tag the dormant ones.
DORMANT_DAYS = 120

# --- Sleeper live feed (team is the reliable signed/unsigned signal) ---
try:
    sl = requests.get(SLEEPER, timeout=30).json()
except Exception as e:
    print(f"Could not reach Sleeper ({e}). Skipping the live status cross-check.")
    sys.exit(1)
by_name = {normalize_name(p["full_name"]): p for p in sl.values() if p.get("full_name")}

signed_off, unsigned, unknown = [], [], []
for _, r in missing.iterrows():
    nm, pos, a = r["full_name"], r["position"], float(r["adp_rank"])
    pl = by_name.get(normalize_name(nm))
    if pl is None:
        unknown.append((nm, pos, a))
    elif pl.get("team"):
        signed_off.append((nm, pos, a, pl.get("team"), pl.get("injury_status") or pl.get("status") or "",
                           news_days(pl.get("news_updated"))))
    else:
        unsigned.append((nm, pos, a, news_days(pl.get("news_updated"))))

print(f"Watching top-{TOP_N} ESPN ADP — {len(missing)} draftable-ADP players are MISSING from the board.\n")

if unsigned:
    # freshest Sleeper news first = most active in the market; stale = likely dormant/retired sentinel
    live = sorted(unsigned, key=lambda x: (x[3] is None, x[3] if x[3] is not None else 1e9))
    hot = [u for u in live if u[3] is not None and u[3] <= DORMANT_DAYS]
    print(f"⚪ UNSIGNED free agents — off the board until they sign, then re-run ({len(unsigned)}):")
    for nm, pos, a, days in live:
        tag = f"  ← dormant ({news_age(days)}), likely retired/inactive" if days is None or days > DORMANT_DAYS else ""
        print(f"   {nm:22} {pos:3} ADP {a:5.0f} ~{rnd(a):4} | news {news_age(days):8}{tag}")
    print(f"   → {len(hot)} with FRESH news (active market — watch these).\n")

if signed_off:
    print(f"🟡 HAS a team but OFF the board — investigate (injured / no FP projection / name) ({len(signed_off)}):")
    for nm, pos, a, team, flag, days in sorted(signed_off, key=lambda x: x[2]):
        print(f"   {nm:22} {pos:3} ADP {a:5.0f} ~{rnd(a):4} | {team:3} {('['+flag+']') if flag and flag!='Active' else ''} news {news_age(days)}")
    print()

if unknown:
    print(f"❓ not found in Sleeper by name (alias/mismatch — check manually) ({len(unknown)}):")
    for nm, pos, a in sorted(unknown, key=lambda x: x[2]):
        print(f"   {nm:22} {pos:3} ADP {a:5.0f} ~{rnd(a)}")
    print()

print("➡️  When an UNSIGNED player above signs, Sleeper fills in their `team` → re-run "
      "`.venv/bin/python run_all.py` to project them onto the board.")
print("   (A player with a team but off the board is usually injured or missing a FantasyPros "
      "projection — verify via news before expecting a re-run to add them.)")
