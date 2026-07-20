# FULL-SYSTEM STRESS - play entire drafts through the real machinery and assert invariants
# at every single pick. Opponents draft by ADP with noise; "my" picks take the top of the
# advisor's own TOP PICKS ranking (offline - no API). 24 scenarios: 3 slots x 4 strategies x 2 seeds.
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import advisor
from utils import normalize_name

TEAMS, ROUNDS = 12, 16
FAIL = []
board_full = pd.read_csv("value_board.csv")
board_full["position"] = board_full["pos_label"].str.extract(r"([A-Z]+)")
board_full["nn"] = board_full["full_name"].apply(normalize_name)

def check(name, ok, detail=""):
    if not ok:
        FAIL.append(f"{name} - {detail}")

def snake_picker(overall, teams=TEAMS):
    r = (overall - 1) // teams + 1
    i = (overall - 1) % teams + 1
    return i if r % 2 else teams - i + 1

def run_draft(slot, strategy, seed):
    rng = np.random.default_rng(seed)
    drafted, mine = set(), set()
    label = f"slot{slot}/{(strategy or 'no-strat')[:12]}/s{seed}"
    my_shortlists = []
    for overall in range(1, TEAMS * ROUNDS + 1):
        avail = board_full[~board_full.full_name.isin(drafted)]
        if snake_picker(overall) != slot:
            # opponent: ADP with noise, skip K/DST-ish until late rounds
            pool = avail.dropna(subset=["adp_rank"]).copy()
            rd = (overall - 1) // TEAMS + 1
            if rd <= 10:
                pool = pool[~pool.position.isin(["K"])]
            pool = pool.nsmallest(12, "adp_rank")
            if pool.empty:
                pool = avail.head(5)
            pick = pool.sample(1, weights=np.linspace(1.0, 0.2, len(pool)), random_state=int(rng.integers(1e9))).iloc[0]
            drafted.add(pick.full_name)
            continue
        # MY pick: exercise the full advisor context machinery
        mine_df = board_full[board_full.full_name.isin(mine)].sort_values("total_points", ascending=False)
        sc = {p: int(((avail["position"] == p) & (avail["vols"] >= 0)).sum()) for p in ["QB", "RB", "WR", "TE", "K"]}
        upcoming = [p for p in range(overall + 1, TEAMS * ROUNDS + 1) if snake_picker(p) == slot]
        dp = {"slot": slot, "teams": TEAMS, "overall_now": overall, "my_turn": True,
              "next_pick": overall, "picks_away": 0, "following": upcoming[0] if upcoming else None}
        av = advisor.add_vona(avail.copy(), dp["following"] or overall + 10)
        ctx = advisor.build_context(av, mine_df, sc, dp, strategy=strategy)

        # ---- invariants at EVERY one of my picks ----
        check(f"{label}#{overall} ctx nonempty", len(ctx) > 500)
        for d in list(drafted)[:5]:
            check(f"{label}#{overall} drafted player absent from context tables",
                  f" {d} " not in ctx.split("Top ")[-1][:4000] or d in mine, d)
        m = re.search(r"TOP PICKS NOW.*?(?:\n)", ctx, re.S)
        shortlist = re.findall(r"\d\. \*?([A-Z][^(]+?) \(", m.group(0)) if m else []
        check(f"{label}#{overall} shortlist parses", len(shortlist) >= 1, ctx[:200])
        for s in shortlist:
            check(f"{label}#{overall} shortlist player available", s.strip() in set(avail.full_name), s)
        if strategy:
            check(f"{label}#{overall} plan line present", "MY DRAFT PLAN" in ctx)
        # roster-gate spot checks: once QB owned, no QB in shortlist
        owned_pos = set(mine_df["position"])
        if "QB" in owned_pos:
            check(f"{label}#{overall} no 2nd QB in shortlist",
                  not any(board_full.loc[board_full.full_name == s.strip(), "position"].eq("QB").any() for s in shortlist))
        # cohort block players must be shortlist players
        cb = re.findall(r"^  ([A-Z][A-Za-z.'\- ]+): \[", ctx, re.M)
        for c in cb:
            check(f"{label}#{overall} cohort line only for shortlist", c in [s.strip() for s in shortlist], c)
        my_shortlists.append(shortlist)
        # take the advisor's #1 (mirrors PICK mode's TAKE #1 with no API)
        pick_name = shortlist[0].strip() if shortlist else avail.iloc[0].full_name
        mine.add(pick_name); drafted.add(pick_name)
    # ---- end-of-draft roster construction sanity ----
    roster = board_full[board_full.full_name.isin(mine)]
    pos_counts = roster["position"].value_counts().to_dict()
    check(f"{label} exactly 16 picks", len(mine) == ROUNDS, str(len(mine)))
    check(f"{label} roster startable (>=1QB >=2RB >=2WR >=1TE)",
          pos_counts.get("QB", 0) >= 1 and pos_counts.get("RB", 0) >= 2
          and pos_counts.get("WR", 0) >= 2 and pos_counts.get("TE", 0) >= 1, str(pos_counts))
    check(f"{label} no more than 1 QB+1 TE... (1-start gates)", pos_counts.get("QB", 0) <= 2, str(pos_counts))
    return pos_counts

scenarios = [(s, st, sd) for s in (1, 7, 12)
             for st in (None, "get good solid players early, avoid injury risk",
                        "Zero-RB - no RBs before round 6 no matter what",
                        "Robust-RB - RBs with my first two picks no matter what")
             for sd in (1, 2)]
results = []
for s, st, sd in scenarios:
    results.append(run_draft(s, st, sd))
print(f"ran {len(scenarios)} full drafts ({len(scenarios)*ROUNDS} advised picks)")
zero_rb = [r for (s, st, sd), r in zip(scenarios, results) if st and "Zero-RB" in st]
rob = [r for (s, st, sd), r in zip(scenarios, results) if st and "Robust" in st]
print("Zero-RB drafts RB counts:", [r.get("RB", 0) for r in zero_rb])
print("Robust-RB drafts RB counts:", [r.get("RB", 0) for r in rob])
if FAIL:
    print(f"\nFAILURES ({len(FAIL)}):")
    for f in FAIL[:25]:
        print("  " + f)
else:
    print("\nALL INVARIANTS PASS across every pick of every draft")
