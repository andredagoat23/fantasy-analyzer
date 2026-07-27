"""Injury / news watch (read-only) — which DRAFTABLE board players carry a health flag right now.

Why this exists: the board is built from projections generated weeks before draft day. If a player
gets hurt in preseason (Aug 7 is preseason week 1), the board still ranks him at full value and the
advisor will happily recommend him. Regenerating does NOT fix that — FantasyPros/ESPN projections lag
an injury by days, and `value_board.py` has no health input at all. So this is a JUDGMENT flag for the
human, deliberately not something that mutates the board.

Signal check (run Jul 27, 2026 against the live feed, top-150 ADP):
  - `injury_status` IS usable in preseason — 15 Questionable + 4 PUP of 150. An older note in
    fa_watch.py said this field is in-season-only; that is out of date, verified against live data.
  - `status` is useless here — all 150 read "Active".
  - `news_updated` is very live (50 of 150 updated within 3 days), so it works as a soft
    "something happened, go read about it" signal for high-ADP players.

Companion to `fa_watch.py` (which watches UNSIGNED players — the reliable signal there is `team`).
That one tells you who might JOIN the board; this one tells you who is already on it and hurt.

Run:  .venv/bin/python tools/injury_watch.py
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests

from utils import INJURY_HARD as HARD, injury_serious as serious, normalize_name

TOP_N = 200              # draftable range to watch
TEAMS = 12
FRESH_DAYS = 3           # news this recent on a high-ADP player is worth a look
SLEEPER = "https://api.sleeper.app/v1/players/nfl"

# Flags ordered by how much they should scare you. PUP/IR/Out/Doubtful are roster-status facts;
# Questionable in the OFFSEASON is softer than in-season (it often just means a minor camp issue),
# so it is reported but ranked below the hard ones.
# HARD / serious() now live in utils.py so this tool and the live draft page (which shows the same
# flags on the board and in the advisor's HEALTH FLAGS line) can never drift apart.


def rnd(adp):
    return f"R{int(adp // TEAMS) + 1}"


def news_days(ms):
    if not ms:
        return None
    return (datetime.now(timezone.utc) - datetime.fromtimestamp(ms / 1000, timezone.utc)).days


def age(days):
    return "?" if days is None else ("today" if days == 0 else f"{days}d ago")


def main():
    board = pd.read_csv("value_board.csv")
    board["position"] = board["pos_label"].str.replace(r"\d+$", "", regex=True)
    pool = board[board["adp_rank"].notna()].nsmallest(TOP_N, "adp_rank")

    try:
        sl = requests.get(SLEEPER, timeout=45).json()
    except Exception as e:
        print(f"Could not reach Sleeper ({e}).")
        return 1
    by_name = {normalize_name(p["full_name"]): p for p in sl.values() if p.get("full_name")}

    hard, soft_op, soft, watch, unmatched = [], [], [], [], []
    for r in pool.itertuples():
        p = by_name.get(normalize_name(r.full_name))
        if p is None:
            unmatched.append((r.full_name, r.pos_label, float(r.adp_rank)))
            continue
        flag = (p.get("injury_status") or "").strip()
        d = news_days(p.get("news_updated"))
        row = (float(r.adp_rank), r.full_name, r.pos_label, p.get("team") or "?", flag, d,
               p.get("injury_notes") or "")
        if flag and flag in HARD:
            hard.append(row)
        elif flag and serious(p.get("injury_notes")):
            soft_op.append(row)
        elif flag:
            soft.append(row)
        elif d is not None and d <= FRESH_DAYS:
            watch.append(row)

    n = len(pool) - len(unmatched)
    print(f"Injury / news watch — top-{TOP_N} board players by ADP ({n} matched in Sleeper)\n")

    def show(rows, title, note):
        if not rows:
            return
        print(f"{title} ({len(rows)}):")
        for adp, nm, pos, team, flag, d, notes in sorted(rows):
            tag = f"[{flag}] " if flag else ""
            print(f"   {nm:<24}{pos:<5} ADP {adp:>5.1f} ~{rnd(adp):<4} {team:<4} {tag}news {age(d)}")
            if notes:
                print(f"      └ {notes[:110]}")
        print(f"   → {note}\n")

    show(hard, "🔴 HARD health flag — do NOT draft at board value without checking",
         "PUP/IR/Out means a real absence. The board does not know; you do.")
    show(soft_op, "🟠 Questionable AFTER A PROCEDURE — the ones actually worth your attention",
         "A surgery/tear note is a real recovery timeline, not a camp tweak. Check the news.")
    show(soft, "🟡 SOFT flag, no procedure noted — offseason Questionable is often minor",
         "Read the news before it changes your pick; usually not disqualifying.")
    show(watch, f"👀 no flag, but news in the last {FRESH_DAYS} days — worth a glance",
         "Fresh news on a draftable player is how an injury shows up BEFORE the status field does.")

    if unmatched:
        print(f"❓ not found in Sleeper by name ({len(unmatched)}) — alias mismatch, check manually:")
        for nm, pos, adp in sorted(unmatched, key=lambda x: x[2]):
            print(f"   {nm:<24}{pos:<5} ADP {adp:>5.1f}")
        print()

    print("➡️  This tool NEVER edits the board — health is a judgment call, and value_board.py has no")
    print("   health input. Re-running run_all.py will NOT clear a flag: projections lag injuries by")
    print("   days. If a HARD-flagged player is in your draft range, decide manually whether to fade.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
