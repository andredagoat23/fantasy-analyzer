"""Pre-draft name-match audit (read-only — touches nothing).

Pulls ESPN's live player universe from the same PUBLIC endpoint load_espn_adp.py uses, then checks
that every top-N player by ADP resolves to a value_board.csv player via normalize_name — the exact
match the live draft bridge relies on. Anything unmatched is a player who, if drafted in the ESPN
room, would NOT be recognized against your board.

Run it before the draft (especially after regenerating the board):
    .venv/bin/python tools/name_audit.py

Findings are split into:
  * unmatched below ESPN's ADP floor  -> the real signal (genuinely-drafted players missing/renamed)
  * unmatched at the ADP floor (~169+) -> noise (ESPN's catch-all for near-undrafted players)
  * unmatched DEF                      -> expected, the board has no D/ST
"""
import json
import os
import sys

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import normalize_name

SEASON = 2026
TOP_N = 200
ADP_FLOOR = 169.0   # ESPN pins near-undrafted players at ~169.9; below this = genuinely drafted
ESPN_POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}
URL = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/players"
HEADERS = {
    "X-Fantasy-Filter": json.dumps({"players": {"filterActive": {"value": True}}}),
    "X-Fantasy-Source": "kona",
    "User-Agent": "Mozilla/5.0",
}


def main():
    resp = requests.get(URL, params={"view": "kona_player_info", "scoringPeriodId": 0},
                        headers=HEADERS, timeout=30)
    resp.raise_for_status()

    espn = []
    for entry in resp.json():
        pl = entry.get("player", entry)
        adp = pl.get("ownership", {}).get("averageDraftPosition")
        pos = ESPN_POS.get(pl.get("defaultPositionId"))
        if adp and adp > 0 and pos:
            espn.append({"name": pl["fullName"], "pos": pos, "adp": round(float(adp), 1)})
    espn.sort(key=lambda r: r["adp"])
    top = espn[:TOP_N]

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    board = pd.read_csv(os.path.join(root, "value_board.csv"))
    board_norms = {normalize_name(n) for n in board["full_name"]}

    real, floor, defense = [], [], []
    for r in top:
        if normalize_name(r["name"]) in board_norms:
            continue
        if r["pos"] == "DEF":
            defense.append(r)
        elif r["adp"] >= ADP_FLOOR:
            floor.append(r)
        else:
            real.append(r)

    print(f"ESPN players with ADP: {len(espn)} | auditing top {len(top)} | board rows: {len(board)}\n")
    print(f"⚠️  UNMATCHED below the ADP floor — INVESTIGATE ({len(real)}):")
    for r in real:
        print(f"     ADP {r['adp']:>6}  {r['pos']:<3} {r['name']}")
    if not real:
        print("     (none — every genuinely-drafted top player resolves to the board ✅)")
    print(f"\n·  unmatched at ADP floor ~{ADP_FLOOR}+ (noise, near-undrafted): {len(floor)}")
    print(f"·  unmatched DEF (expected, board has no D/ST): {len(defense)}")

    matched = len(top) - len(real) - len(floor) - len(defense)
    print(f"\nmatched: {matched}/{len(top)} top-{TOP_N} ESPN names resolve to the board")
    return 1 if real else 0


if __name__ == "__main__":
    sys.exit(main())
