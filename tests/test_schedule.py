"""Regression test for ROUND<->PICK TRUTH: advisor.my_pick_schedule, _lasts_round, the MY PICKS
context line, and the slot-aware PUNT READ.

TWO BUGS THIS LOCKS OUT, both the same class — round<->pick arithmetic done ad hoc:

1. THE MODEL INVENTED A SCHEDULE. Asked a whole-draft strategy question from slot 10, the advisor said
   "rounds 3-7 give you picks in the 25-35 range". Slot 10's real R3-R7 are #34/#39/#58/#63/#82 — one
   of five is in range and #82 is nowhere near it. Cause: the entire 12,746-char context contained
   exactly THREE pick numbers (1, 10, 15) and zero rounds, while the prompt forbids computing pick
   numbers. Forbidden to compute, given nothing to read. Fix: the MY PICKS line.

2. PYTHON INVENTED A SURVIVAL CLAIM — worse, because principle #3 exists to stop exactly this.
   `_pos_punt_loss` derived `lasts_round = floor((adp - 1) / teams) + 1`, which is the round the MARKET
   drafts him in, and rendered it as "lasts ~R7". That is the OPPOSITE reading, and it ignored my slot:
   ADP 77.8 printed "lasts ~R7" whether the truth was 61% (slot 1, #73), 40% (slot 10, #82) or 36%
   (slot 12, #84). The model quoted our own wrong line back to the user. Fix: `_lasts_round` measures
   survival at MY actual pick and the render carries the probability.

   This one could bite DURING the draft — `_punt_read` runs at every pick including my_turn=True, and
   it is the read that tells me a 1-start slot is safe to punt.

Also pinned: `late_pick` is now taken off the snake schedule instead of `current_overall + rounds*teams`
(which counted from whoever was on the clock and gave #61 for every seat).

Fixtures are SYNTHETIC / hard-coded ADPs on purpose: `run_all.py` refreshes ESPN ADP on draft morning,
so a suite pinned to a live player's ADP would go red on Aug 7.

Run:  .venv/bin/python tests/test_schedule.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

import advisor

passed = 0


def check(label, cond):
    global passed
    assert cond, f"FAIL: {label}"
    passed += 1
    print(f"  ok  {label}")


# =============================================================== A. the schedule itself
print("\nA. my_pick_schedule — the single source of truth for round<->pick")

s1, s10, s12 = (advisor.my_pick_schedule(s, 12, 16) for s in (1, 10, 12))
d1, d10, d12 = dict(s1), dict(s10), dict(s12)

check("slot 1 turns back-to-back at the 2/3 boundary (R2 #24, R3 #25)", d1[2] == 24 and d1[3] == 25)
check("slot 12 turns back-to-back at 1/2 (R1 #12, R2 #13)", d12[1] == 12 and d12[2] == 13)
check("slot 1 R1 #1 and R16 #192", d1[1] == 1 and d1[16] == 192)
check("16 rounds returned", len(s10) == 16)

# the exact numbers the model got wrong
check("slot 10 R3-R7 are #34/#39/#58/#63/#82 (the invented claim was 'picks 25-35')",
      [d10[r] for r in (3, 4, 5, 6, 7)] == [34, 39, 58, 63, 82])
check("only ONE of slot 10's R3-R7 picks is in 25-35",
      sum(1 for r in (3, 4, 5, 6, 7) if 25 <= d10[r] <= 35) == 1)

# strong invariant: 12 slots x 16 rounds must tile every pick exactly once
allp = sorted(pk for s in range(1, 13) for _, pk in advisor.my_pick_schedule(s, 12, 16))
check("all 12 slots tile picks 1..192 exactly once", allp == list(range(1, 193)))
check("no pick appears twice in one slot's schedule", len({pk for _, pk in s10}) == 16)
check("bad input -> empty (no slot)", advisor.my_pick_schedule(None, 12, 16) == [])
check("bad input -> empty (slot > teams)", advisor.my_pick_schedule(13, 12, 16) == [])
check("non-12-team leagues work (slot 3 of 10, R2 = #18)",
      dict(advisor.my_pick_schedule(3, 10, 16))[2] == 18)

# =============================================================== B. _lasts_round semantics
print("\nB. _lasts_round measures survival at MY pick — it is NOT floor(ADP/teams)")

ADP = 77.8                                    # hard-coded: the value that exposed the bug
old_formula = int((ADP - 1) // 12) + 1        # == 7, the round the MARKET takes him in
r1, p1 = advisor._lasts_round(ADP, s1)
r10, p10 = advisor._lasts_round(ADP, s10)
r12, p12 = advisor._lasts_round(ADP, s12)

check("the old formula would have said R7 for every slot", old_formula == 7)
check("the answer is now SLOT-DEPENDENT (slot 1 vs slot 12 differ)", (r1, p1) != (r12, p12))
check("slot 1 keeps R7 because #73 genuinely clears the floor", r1 == 7 and p1 >= advisor._PUNT_STREAM_P)
check("slot 10 drops off R7 — its R7 is #82, below the floor", r10 < 7)
check("slot 12 drops off R7 too — its R7 is #84", r12 < 7)
check("every returned probability clears the floor",
      all(p >= advisor._PUNT_STREAM_P for p in (p1, p10, p12)))

# the returned round must be the LAST one clearing the floor
nxt = dict(s10).get(r10 + 1)
check("it is the LAST qualifying round (the next round's pick is below the floor)",
      nxt is None or float(advisor._survival_prob(pd.Series([ADP]), nxt).iloc[0]) < advisor._PUNT_STREAM_P)

check("NaN ADP -> (None, None)", advisor._lasts_round(float("nan"), s10) == (None, None))
check("empty schedule -> (None, None)", advisor._lasts_round(ADP, []) == (None, None))
check("a player certain to be gone -> (None, None), never a fabricated round",
      advisor._lasts_round(1.2, [(r, pk) for r, pk in s10 if r >= 3]) == (None, None))

# =============================================================== C. the MY PICKS context line
print("\nC. the MY PICKS line puts the schedule in front of the model")


def board(rows):
    """rows = [(name, pos, adp, vols)] on the real schema so build_context accepts it."""
    real = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "app_data.csv"))
    b = real.head(len(rows)).copy().reset_index(drop=True)
    b["full_name"] = [r[0] for r in rows]
    b["position"] = [r[1] for r in rows]
    b["pos_label"] = [f"{r[1]}{i + 1}" for i, r in enumerate(rows)]
    b["adp_rank"] = [r[2] for r in rows]
    b["vols"] = [r[3] for r in rows]
    b["rank_composite"] = range(1, len(rows) + 1)
    b["overall_rank"] = range(1, len(rows) + 1)
    b["team"], b["proj_outlier"], b["market"] = "BUF", False, "fair"
    b["p_startable"], b["p_bust"] = 0.7, 0.25
    if "no_team" in b.columns:
        b["no_team"] = False
    return b


BOARD = board([("Elite RB", "RB", 2.0, 190.0), ("Elite WR", "WR", 5.0, 150.0),
               ("Mid RB", "RB", 30.0, 95.0), ("Stream QB", "QB", 77.8, 60.0),
               ("Stream TE", "TE", 80.0, 45.0), ("Deep WR", "WR", 120.0, 30.0)])
SC = {"QB": 5, "RB": 20, "WR": 30, "TE": 8, "K": 5}


def ctx(slot, overall_now=1, my_turn=False, teams=12):
    d = {"slot": slot, "teams": teams, "overall_now": overall_now, "my_turn": my_turn,
         "next_pick": dict(advisor.my_pick_schedule(slot, teams, 16))[1], "picks_away": slot - 1,
         "following": dict(advisor.my_pick_schedule(slot, teams, 16))[2], "total_rounds": 16}
    h = advisor._horizon(d)
    return advisor.build_context(advisor.add_vona(BOARD.copy(), h), BOARD.head(0), SC, d)


c10 = ctx(10)
myline = next((l for l in c10.splitlines() if l.startswith("MY PICKS")), None)
check("the MY PICKS line is present", myline is not None)
check("it names the slot and league size", "slot 10 of 12" in myline)
check("it tells the model to READ, not compute", "NEVER compute" in myline)
check("it lists slot 10's real R3-R7 picks", all(f"R{r} #{d10[r]}" in myline for r in (3, 4, 5, 6, 7)))
check("it lists all 16 rounds pre-draft", all(f"R{r} #{d10[r]}" in myline for r in range(1, 17)))
check("slot 1 and slot 10 render different schedules",
      next(l for l in ctx(1).splitlines() if l.startswith("MY PICKS")) != myline)

mid = ctx(10, overall_now=40)                    # mid-draft: past picks must be dropped
midline = next(l for l in mid.splitlines() if l.startswith("MY PICKS"))
check("mid-draft drops picks already gone (R1 #10 absent at overall 40)", "R1 #10" not in midline)
check("mid-draft keeps the picks still ahead (R5 #58)", "R5 #58" in midline)

# =============================================================== D. the PUNT READ carries its number
print("\nD. the PUNT READ states the round WITH its measured probability, slot-aware")

PUNT_RE = re.compile(r"lasts ~R(\d+) \((\d+)%\)")
p10_line = next((l for l in c10.splitlines() if l.startswith("PUNT READ")), None)
check("a PUNT READ line renders", p10_line is not None)
m = PUNT_RE.search(p10_line)
check("it reads 'lasts ~R<n> (<p>%)' — the bare '~R7' promise is gone", m is not None)
check("the stated probability clears the floor", int(m.group(2)) >= advisor._PUNT_STREAM_P * 100)
p1_line = next(l for l in ctx(1).splitlines() if l.startswith("PUNT READ"))
check("the same board gives a DIFFERENT punt read at slot 1 vs slot 10 (was identical)",
      PUNT_RE.search(p1_line).groups() != m.groups())
check("it still reports the punt/cliff verdict", "DEEP" in p10_line or "CLIFF" in p10_line)

# =============================================================== E. the prompt rules
print("\nE. the prompt tells the model where round<->pick comes from")

check("prompt points round↔pick conversion at MY PICKS", "MY PICKS line lists EVERY pick" in advisor.SYSTEM)
check("prompt forbids deriving the schedule itself", "never computed, never estimated" in advisor.SYSTEM)
check("prompt requires a number behind any 'lasts to round N' claim",
      'Any claim of the form "X lasts to round N"' in advisor.SYSTEM)
check("prompt tells it to decline rather than estimate", "do NOT estimate one" in advisor.SYSTEM)

# =============================================================== F. rest-of-draft lookahead
print("\nF. WHO'S REALISTICALLY LEFT AT MY PICKS — odds at every pick, not just the next one")

# The regression: MY PICKS gave the model the pick NUMBERS, but every survival figure still sat at
# ONE pick (my next). Asked about R3 it reused the R2 number — at slot 6 it read Josh Allen 68% @ #19
# and called him "still alive" at #30, where he is 20.9%.
LOOK_RE = re.compile(r"R(\d+) #(\d+) BEST:")
PCT_RE = re.compile(r"([A-Z][\w'.\- ]+?) (\d+)%")


def look(slot, my_turn=True, now=None, teams=12):
    sch = dict(advisor.my_pick_schedule(slot, teams, 16))
    now = now if now is not None else sch[1]
    ahead = [pk for _, pk in advisor.my_pick_schedule(slot, teams, 16) if pk >= now]
    d = {"slot": slot, "teams": teams, "overall_now": now, "my_turn": my_turn,
         "next_pick": ahead[0], "picks_away": ahead[0] - now,
         "following": ahead[1] if len(ahead) > 1 else None, "total_rounds": 16}
    return advisor.available_at_my_picks(BOARD_FULL, d), d


BOARD_FULL = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      "app_data.csv"))
BOARD_FULL["position"] = BOARD_FULL["pos_label"].str.extract(r"([A-Z]+)")

blk, d6 = look(6)
picks = [int(pk) for _, pk in LOOK_RE.findall(blk)]
check("the block renders", bool(blk) and "WHO'S REALISTICALLY LEFT" in blk)
check("it starts at _horizon, NOT my current pick (everyone in the pool is already available there)",
      picks[0] == advisor._horizon(d6) and d6["overall_now"] not in picks)
check("slot 6 on the clock at #6 -> the block starts at #19", picks[0] == 19)
check("every pick listed is one of MY picks", set(picks) <= {pk for _, pk in advisor.my_pick_schedule(6, 12, 16)})
check("picks are in ascending order, no repeats", picks == sorted(set(picks)))
check(f"capped at _LOOKAHEAD_PICKS ({advisor._LOOKAHEAD_PICKS})", len(picks) <= advisor._LOOKAHEAD_PICKS)

# every printed probability must be real, and must clear the bar at ITS OWN pick
bad = []
for seg in blk.split("\n")[1:]:
    m = LOOK_RE.search(seg)
    pk = int(m.group(2)) if m else pk
    for name, pct in PCT_RE.findall(seg):
        row = BOARD_FULL[BOARD_FULL.full_name == name.strip()]
        if row.empty:
            continue
        true_p = float(advisor._survival_prob(pd.Series([row.adp_rank.iloc[0]]), pk).iloc[0])
        if abs(true_p * 100 - int(pct)) > 0.51 or true_p < advisor._PUNT_STREAM_P:
            bad.append((name, pk, pct, round(true_p, 3)))
check("every printed % equals _survival_prob at THAT pick and clears the bar", not bad, )

# THE ordering contract — value first, so odds ascend. Re-sorting by odds is the failure mode.
rb_line = next(l for l in blk.split("\n") if "by pos: RB" in l)
rb_seg = rb_line.split("RB ", 1)[1].split(" | ")[0]
rb_names = [n.strip() for n, _ in PCT_RE.findall(rb_seg)]
comp = [int(BOARD_FULL[BOARD_FULL.full_name == n].rank_composite.iloc[0]) for n in rb_names
        if not BOARD_FULL[BOARD_FULL.full_name == n].empty]
check("within a position the order is OUR VALUE (composite ascending), not probability",
      comp == sorted(comp) and len(comp) >= 2)
check("the header warns that the % rises and must not be re-sorted",
      "RISES as you read right" in blk and "never re-order by probability" in blk)
check("the header states both assumptions (my own picks, marginal odds)",
      "draft nobody in between" in blk and "directional not exact" in blk)

# slot-sensitivity + degradation
b12, _ = look(12)
check("a different seat gives a different block", [int(p) for _, p in LOOK_RE.findall(b12)] != picks)
late, _ = look(6, now=dict(advisor.my_pick_schedule(6, 12, 16))[15])
check("near the end it degrades quietly (no blank rows, no crash)",
      "BEST:" not in late or all("BEST:" in l or "by pos" in l or l.startswith("WHO")
                                 for l in late.split("\n") if l.strip()))
check("no draft_pos -> empty string, no crash", advisor.available_at_my_picks(BOARD_FULL, None) == "")
check("no horizon (final pick) -> empty string",
      advisor.available_at_my_picks(BOARD_FULL, {"slot": 6, "teams": 12, "overall_now": 192,
                                                 "my_turn": True, "next_pick": 192,
                                                 "following": None, "total_rounds": 16}) == "")

# wired into the context, and the prompt points at it
sc = {"QB": 5, "RB": 20, "WR": 30, "TE": 8, "K": 5}
ctx6 = advisor.build_context(advisor.add_vona(BOARD_FULL.copy(), advisor._horizon(d6)),
                             BOARD_FULL.head(0), sc, d6)
check("the block is present in the real context", "WHO'S REALISTICALLY LEFT AT MY PICKS" in ctx6)
check("the context now carries survival at MORE than one pick",
      len({int(x) for x in re.findall(r"#(\d+) BEST:", ctx6)}) >= 4)
check("prompt sends later-pick questions to the block",
      "WHO'S REALISTICALLY LEFT AT MY PICKS block" in advisor.SYSTEM)
check("prompt forbids restating the wheel cell for a later pick",
      "never restate it for a later pick" in advisor.SYSTEM)
check("prompt forbids re-ordering the block by probability",
      "NEVER re-order them by probability" in advisor.SYSTEM)

print(f"\nALL {passed} CHECKS PASS")
