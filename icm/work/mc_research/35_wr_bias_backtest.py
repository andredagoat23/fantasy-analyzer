"""35 — Does correcting the WR over-projection actually change draft OUTCOMES?

34_ found every commercial projection source over-projects, and that the SPREAD across positions is
what corrupts VONA: ESPN reads WR 1.24 vs TE 1.13 (Sleeper 1.23 vs 1.12). Since VOLS is a difference
(projection minus a same-position replacement level), a position inflated by k has its VOLS inflated
by k too — so WR VOLS is ~10% hot relative to TE/RB, and every cross-position comparison tilts to WRs.

That is a bigger deal in principle than the prerequisite rules were, because it distorts the whole
ORDERING rather than nudging a few players. But 33_ taught the lesson: measure it in POINTS, not in
plausibility. This is the same paired-draft harness pointed at the calibration question.

Rigor:
  * **Out-of-sample ratios.** The correction factor applied to a season is derived from the OTHER
    season(s), never from the one being tested. The in-sample version is also reported, as the
    ceiling this could ever reach.
  * **Paired seeds** — both arms see the identical draft flow; only my valuation differs.
  * **Scored on actual season points**, optimal 1QB/2RB/2WR/1TE/1FLEX lineup.
  * Both arms draft by VOLS (projection minus positional replacement), which is what the real board
    does — so this isolates the calibration change and nothing else.

Run:  .venv/bin/python icm/work/mc_research/35_wr_bias_backtest.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from scoring_config import SCORING  # noqa: E402
from utils import normalize_name  # noqa: E402

OUT = os.path.join(HERE, "results_35_wr_bias.txt")
CACHE = os.path.join(HERE, "espn_hist_cache.json")
SEASONS = (2024, 2025)
TEAMS, ROUNDS, MY_SLOT = 12, 16, 7
N_DRAFTS = 300
ADP_NOISE = 8.0
STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
FLEX_OK = ("RB", "WR", "TE")
MAX_POS = {"QB": 2, "TE": 2, "RB": 6, "WR": 6}
REPLACEMENT = {"QB": 12, "RB": 24, "WR": 24, "TE": 12}   # 12-team starter demand
POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE"}
ESPN_STAT = {"pass_yds": "3", "pass_td": "4", "pass_int": "20", "rush_yds": "24", "rush_td": "25",
             "rec": "53", "rec_yds": "42", "rec_td": "43"}

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def score(d, keymap):
    tot = 0.0
    for canon, key in keymap.items():
        v = d.get(key)
        if v is not None:
            try:
                tot += float(v) * SCORING.get(canon, 0.0)
            except (TypeError, ValueError):
                pass
    return tot


def build_pool(season):
    """[{name,pos,proj,actual,adp}] for one season, from ESPN projections/actuals + Sleeper ADP."""
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/players"
    hdr = {"X-Fantasy-Source": "kona", "Accept": "application/json",
           "X-Fantasy-Filter": json.dumps({"players": {"filterActive": {"value": True}, "limit": 900,
                                                       "sortPercOwned": {"sortPriority": 1,
                                                                         "sortAsc": False}}})}
    d = requests.get(url, params={"view": "kona_player_info", "scoringPeriodId": 0},
                     headers=hdr, timeout=45).json()
    players = d["players"] if isinstance(d, dict) else d
    pr = requests.get(f"https://api.sleeper.app/v1/projections/nfl/regular/{season}", timeout=40).json()
    pl = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=45).json()
    adp = {}
    for pid, row in pr.items():
        nm = (pl.get(pid) or {}).get("full_name")
        a = row.get("adp_ppr")
        if nm and a not in (None, "") and float(a) < 400:
            adp[normalize_name(nm)] = float(a)
    out = []
    for p in players:
        pl_ = p.get("player", p)
        pos, nm = POS.get(pl_.get("defaultPositionId")), pl_.get("fullName")
        if not pos or not nm:
            continue
        proj = act = None
        for s in pl_.get("stats", []) or []:
            if s.get("seasonId") != season or s.get("statSplitTypeId") != 0:
                continue
            if s.get("statSourceId") == 1:
                proj = s.get("stats", {})
            elif s.get("statSourceId") == 0:
                act = s.get("stats", {})
        if not (proj and act and any(k in proj for k in ("3", "24", "42", "53"))):
            continue
        pp, aa = score(proj, ESPN_STAT), score(act, ESPN_STAT)
        a = adp.get(normalize_name(nm))
        if pp > 20 and a is not None:
            out.append({"name": nm, "pos": pos, "proj": pp, "actual": aa, "adp": a})
    return out


def load_pools():
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            return {int(k): v for k, v in json.load(f).items()}
    pools = {s: build_pool(s) for s in SEASONS}
    with open(CACHE, "w") as f:
        json.dump({str(k): v for k, v in pools.items()}, f)
    return pools


def ratios(pool):
    """{pos: mean(projection)/mean(actual)} — the calibration factor per position."""
    df = pd.DataFrame(pool)
    df = df[df["adp"] <= 200]
    out = {}
    for pos in ("QB", "RB", "WR", "TE"):
        g = df[df["pos"] == pos]
        if len(g) >= 15 and g["actual"].mean() > 0:
            out[pos] = g["proj"].mean() / g["actual"].mean()
    return out


def vols(df, col):
    """Projection minus same-position replacement level — what the real board ranks on."""
    v = np.zeros(len(df))
    pos = df["pos"].to_numpy()
    val = df[col].to_numpy()
    for p, n in REPLACEMENT.items():
        m = pos == p
        if m.sum() == 0:
            continue
        repl = np.sort(val[m])[::-1][min(n, m.sum()) - 1]
        v[m] = val[m] - repl
    return v


def optimal(positions, points):
    by = {p: sorted(points[positions == p], reverse=True) for p in ("QB", "RB", "WR", "TE")}
    total, used = 0.0, {}
    for p, k in STARTERS.items():
        take = by[p][:k]
        total += sum(take)
        used[p] = len(take)
    flex = []
    for p in FLEX_OK:
        flex += by[p][used[p]:]
    return total + (max(flex) if flex else 0.0)


def simulate(df, rng, my_value_col):
    n = len(df)
    adp = df["adp"].to_numpy()
    pos = df["pos"].to_numpy()
    pts = df["actual"].to_numpy()
    myval = df[my_value_col].to_numpy()
    noise = rng.normal(0, ADP_NOISE, n)
    taken = np.zeros(n, dtype=bool)
    rosters = {t: {"QB": 0, "RB": 0, "WR": 0, "TE": 0} for t in range(1, TEAMS + 1)}
    mine = []
    for rd in range(1, ROUNDS + 1):
        order = range(1, TEAMS + 1) if rd % 2 else range(TEAMS, 0, -1)
        for team in order:
            avail = ~taken
            if not avail.any():
                continue
            cnt = rosters[team]
            ok = avail & np.array([cnt[p] < MAX_POS[p] for p in pos])
            if not ok.any():
                ok = avail
            idx = np.where(ok)[0]
            if team == MY_SLOT:
                need = np.array([(cnt[p] < STARTERS[p]) or (p in FLEX_OK) for p in pos])
                cand = np.where(ok & need)[0]
                if len(cand) == 0:
                    cand = idx
                pick = cand[np.argmax(myval[cand])]          # I draft by VALUE
            else:
                pick = idx[np.argmin((adp + noise)[idx])]     # opponents by ADP
            taken[pick] = True
            rosters[team][pos[pick]] += 1
            if team == MY_SLOT:
                mine.append(pick)
    mine = np.array(mine)
    return optimal(pos[mine], pts[mine])


def run(pools, mode):
    say(f"\n  {'season':<9}{'raw':>9}{'corrected':>11}{'diff':>9}{'win%':>8}   ratios used")
    all_d = []
    for s in SEASONS:
        pool = pools[s]
        src = [x for x in SEASONS if x != s] if mode == "oos" else [s]
        r = {}
        for other in src:
            for p, v in ratios(pools[other]).items():
                r.setdefault(p, []).append(v)
        r = {p: float(np.mean(v)) for p, v in r.items()}
        df = pd.DataFrame(pool)
        df = df[df["adp"] <= 220].reset_index(drop=True)
        df["proj_corr"] = df["proj"] / df["pos"].map(r).fillna(1.0)
        df["v_raw"] = vols(df, "proj")
        df["v_corr"] = vols(df, "proj_corr")
        diffs, a_tot, b_tot = [], [], []
        for i in range(N_DRAFTS):
            a = simulate(df, np.random.default_rng(7000 + i), "v_raw")
            b = simulate(df, np.random.default_rng(7000 + i), "v_corr")
            diffs.append(b - a)
            a_tot.append(a)
            b_tot.append(b)
        d = np.array(diffs)
        all_d.append(d)
        say(f"  {s:<9}{np.mean(a_tot):>9.0f}{np.mean(b_tot):>11.0f}{d.mean():>+9.1f}"
            f"{(d > 0).mean():>7.0%}   " + " ".join(f"{p}{r.get(p, 1):.2f}" for p in ("QB", "RB", "WR", "TE")))
    D = np.concatenate(all_d)
    say(f"  POOLED n={len(D)}: mean {D.mean():+.1f} pts · corrected wins {(D > 0).mean():.1%} · "
        f"loses {(D < 0).mean():.1%}")
    return D


def main():
    say("DOES CORRECTING THE PER-POSITION PROJECTION BIAS WIN POINTS?")
    say(f"  {TEAMS}-team snake, seat {MY_SLOT}, {ROUNDS} rounds · {N_DRAFTS} PAIRED drafts/season")
    say("  both arms draft by VOLS (projection - positional replacement); only the calibration differs")
    say("  opponents draft by ADP+noise · scored on ACTUAL season points, optimal lineup\n")
    pools = load_pools()
    for s in SEASONS:
        say(f"  {s}: {len(pools[s])} players with projection + actual + ADP")

    # A correction can only work if the factor is PREDICTABLE from prior seasons. Check that first —
    # if the ratios swing year to year, last season's correction is simply the wrong number.
    say("\n" + "=" * 78)
    say("ARE THE CALIBRATION FACTORS STABLE SEASON TO SEASON?")
    say("=" * 78)
    say(f"  {'season':<9}" + "".join(f"{p:>8}" for p in ("QB", "RB", "WR", "TE")) + f"{'WR-TE gap':>11}")
    for s in SEASONS:
        r = ratios(pools[s])
        gap = r.get("WR", np.nan) - r.get("TE", np.nan)
        say(f"  {s:<9}" + "".join(f"{r.get(p, float('nan')):>8.2f}" for p in ("QB", "RB", "WR", "TE"))
            + f"{gap:>11.2f}")
    say("  A correction is only applicable if you can PREDICT the factor. Watch both the levels and")
    say("  the WR-TE gap: if they move a lot, last season's factor is the wrong number to apply.")
    say("\n" + "=" * 78)
    say("OUT-OF-SAMPLE — correction factors derived from the OTHER season (the honest test)")
    say("=" * 78)
    oos = run(pools, "oos")
    say("\n" + "=" * 78)
    say("IN-SAMPLE — factors from the season being tested (the ceiling; not achievable live)")
    say("=" * 78)
    ins = run(pools, "in")
    say("\nVERDICT: " + (
        f"correcting the bias is worth ~{oos.mean():+.0f} pts out-of-sample "
        f"({(oos > 0).mean():.0%} win rate). " +
        ("A real, usable edge." if oos.mean() > 15 and (oos > 0).mean() > 0.6 else
         "Too small to justify touching a frozen pipeline file." if abs(oos.mean()) < 15 else
         "Directionally negative — do NOT apply it.")))
    say(f"  (in-sample ceiling was {ins.mean():+.1f} pts — if OOS is far below this, the per-position")
    say("   ratios are not stable enough season to season to be worth applying.)")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
