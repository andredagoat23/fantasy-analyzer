"""49 — THE GRADER LIBRARY (charter T0.4): three arms, two modes, five slots, measured dispersion.

This module is the measurement instrument for every Grading-phase workstream. It does NOT decide
anything by itself — it turns a "policy delta" (a per-player attractiveness adjustment) into a
paired-draft points result with the charter's mandatory reporting block.

DESIGN (charter D2 — the layering):
  * `44_survival_curve_backtest.py` supplies the OPPONENT MODEL (per-player measured ADP dispersion)
    and MY policy (VONA via `advisor.add_vona` — imported, never copied, so the sim and the shipped
    survival math use ONE curve: `advisor._SCALE_ADP` / `advisor._SCALE_S`).
  * `33_harsh_backtest.py` supplies `optimal_lineup` and the actual-points season scoring — imported
    from the file via importlib (module name starts with a digit), never copied, so the legacy
    self-test can NOT drift from the historical instrument.
  * The three-arm structure supplies the endpoint: ARM 3 (composite+treatment) MINUS ARM 2
    (reconstructed composite) is the ONLY primary endpoint (S14). Arm 1 (ADP-follow) is a sanity
    floor and arm3−arm1 may never be a headline.
  * The T0.3 league-scored panel (`weekly_league.parquet`) supplies the CURRENCY: league points
    primary, base PPR secondary (S12). Both are graded from the SAME panel and week range so the
    two currencies differ only by the scoring table, never by data coverage.

TWO SCORING MODES (charter D1):
  * SEASON — `33_`'s optimal lineup over season totals. Correct for roster-construction questions.
    Blind to availability by construction (a 200-pt/9-game season == 200-pt/17-game season).
  * WEEKLY — hindsight-optimal lineup EACH WEEK from rostered players who actually played that
    week, fixed replacement-level fill for unfilled slots (D1: draft grading uses hindsight-optimal;
    ex-ante lineups are for in-season detector grading, a different instrument).
    Weeks graded: 1-17 for seasons >= 2021, 1-16 before (fantasy leagues do not play the final NFL
    week; ESPN default ends week 17 in the 17-game era).

THREE ARMS:
  arm1 = ADP-follow me (policy='adp', no delta)         — sanity floor
  arm2 = reconstructed composite me (policy='composite')— the current system rebuilt historically
  arm3 = arm2 + policy delta                            — the treatment
Legacy self-test (T0.5b) pairs arm1 vs arm1+delta because that is what `33_` measured.

POPULATIONS:
  * LEGACY pool = `h33.load()` — the exact 33_ population (seasons_exp, adp<=200, season>=2015).
    It deliberately reproduces the historical instrument INCLUDING its known defects (pool ~160-180
    < the charter's 222 floor, base-PPR currency, flat noise). The 222 assert is WAIVED here by
    design: the pool must equal 33_'s or the +5.2 gate is meaningless. Never use it for new results.
  * CORRECTED pool = blend_cache_2019_2025.json CLEAN seasons (2021, 2022, 2024, 2025 — Sleeper's
    2019-20 projections are backfilled per 38_; 2023 has only 31 cache rows), adp<=220 exactly as
    44_'s prep, PADDED past the cache with `adp_ext_sleeper_2020_2025.csv` (<=300) so the
    `pool >= 12*16+30 = 222` assert passes (T0.2's sanctioned option: priced-but-unplayed players
    enter at their real price with zero projection — opponents draft them by ADP, I value them at
    replacement). 2025 prices are SLEEPER adp_ppr (T0.2 instrument repair), NOT ESPN, NOT FFC.
    Asserted against population.json on load; aborts on mismatch (PopulationMismatch).

RUNTIME INVARIANTS (charter T0.4, carried from 44_):
  * composite-policy picks go through `advisor.add_vona` (VONA), never raw VOLS;
  * composite mode requires opponent_noise='measured' AND advisor.USE_MEASURED_SCALE == True;
  * the dispersion curve is imported from advisor — grep confirms `_SCALE_ADP` exists nowhere else
    in this module (L52/L53: one concept, one home).

Author: charter task T0.4/T0.5 agent. New file; imports frozen code, modifies nothing.
"""
import importlib.util
import json
import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

import advisor  # noqa: E402  (frozen; supplies add_vona + the ONE dispersion curve)
from utils import normalize_name  # noqa: E402

# ---- import 33_ as a module (digit-leading filename) so its functions cannot drift from history --
_spec = importlib.util.spec_from_file_location("harsh33", os.path.join(HERE, "33_harsh_backtest.py"))
h33 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h33)          # safe: 33_ is __main__-guarded

# ---- import 44_ the same way: its _SD_ADP/_SD opponent pick-sd table is 43_'s measurement and
# must not exist in two places with two values (L52/L53). advisor._SCALE_S is a DIFFERENT object
# (the survival logistic scale) — both derive from 43_ but they are not interchangeable (T0.8 M7).
_spec44 = importlib.util.spec_from_file_location(
    "surv44", os.path.join(HERE, "44_survival_curve_backtest.py"))
s44 = importlib.util.module_from_spec(_spec44)
_spec44.loader.exec_module(s44)        # safe: 44_ is __main__-guarded

# ---- constants shared with the templates (roster shape is the league's, from 33_/44_) -----------
TEAMS, ROUNDS = 12, 16
START = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
FLEX_OK = ("RB", "WR", "TE")
MAXP = {"QB": 2, "TE": 2, "RB": 6, "WR": 6}
REPL = {"QB": 12, "RB": 24, "WR": 24, "TE": 12}
MIN_POOL = TEAMS * ROUNDS + 30          # = 222, charter T0.2/T0.4
CLEAN = (2021, 2022, 2024, 2025)        # 2025 included: T0.2 price repair landed (Sleeper adp_ppr)
# measured sd of (actual pick − ADP) — 43_'s opponent-behaviour table, IMPORTED from 44_ (one home)
_SD_ADP, _SD = s44._SD_ADP, s44._SD

# S8 pins — abort loudly if an upstream artifact silently changes under us.
_CACHE_ROWS = {2019: 150, 2020: 243, 2021: 211, 2022: 207, 2023: 31, 2024: 256, 2025: 245}
_WEEKLY_LEAGUE_ROWS = 67_353


class PopulationMismatch(AssertionError):
    pass


class PoolTooSmall(AssertionError):
    pass


class WeeklyPanelMissing(RuntimeError):
    """Named error per assignment: raised if weekly mode is requested without T0.3's panel."""


# =================================================================================================
# CONFIG
# =================================================================================================
@dataclass(frozen=True)
class GraderConfig:
    name: str
    policy: str            # 'adp' (33_-style pick rule at my seat) | 'composite' (44_-style VONA)
    opponent_noise: str    # 'flat' | 'measured'
    scoring: str           # 'season' | 'weekly'
    slots: tuple
    n_drafts: int
    seed_base: int
    flat_sd: float = 8.0

    def validate(self):
        assert self.policy in ("adp", "composite") and self.scoring in ("season", "weekly")
        if self.policy == "composite":
            # charter runtime invariants: VONA policy ⇒ measured dispersion + measured survival
            assert self.opponent_noise == "measured", "composite policy requires measured dispersion"
            assert advisor.USE_MEASURED_SCALE is True, "advisor measured survival curve must be on"


LEGACY = GraderConfig(name="legacy", policy="adp", opponent_noise="flat", scoring="season",
                      slots=(7,), n_drafts=250, seed_base=10_000, flat_sd=8.0)
LEGACY_MEASURED = GraderConfig(name="legacy_measured", policy="adp", opponent_noise="measured",
                               scoring="season", slots=(7,), n_drafts=250, seed_base=10_000)
CORRECTED = GraderConfig(name="corrected", policy="composite", opponent_noise="measured",
                         scoring="weekly", slots=(1, 5, 8, 10, 12), n_drafts=100, seed_base=4900)


# =================================================================================================
# POOLS
# =================================================================================================
class Pool:
    """One season's draftable pool with everything the simulator needs precomputed."""

    def __init__(self, season, df, weeks, W_league, W_base, played, repl_league, repl_base):
        self.season = int(season)
        self.df = df                    # reset_index'd; iloc == positional index
        self.n = len(df)
        self.adp = df["adp"].to_numpy(float)
        self.pos = df["position"].to_numpy()
        self.vols = df["vols"].to_numpy(float) if "vols" in df else None
        self.sd = df["sd"].to_numpy(float) if "sd" in df else None
        self.adj = df["_adj"].to_numpy(float) if "_adj" in df else np.zeros(self.n)
        self.adj_pts = df["_adj_pts"].to_numpy(float) if "_adj_pts" in df else np.zeros(self.n)
        self.t_league = df["total_league"].to_numpy(float)
        self.t_base = df["total_base"].to_numpy(float)
        self.weeks = weeks
        self.W_league, self.W_base, self.played = W_league, W_base, played
        self.repl_league, self.repl_base = repl_league, repl_base


def _load_weekly():
    wl = pd.read_parquet(os.path.join(HERE, "weekly_league.parquet"),
                         columns=["player_id", "position", "season", "week",
                                  "pts_league", "pts_base"])
    if len(wl) != _WEEKLY_LEAGUE_ROWS:
        raise WeeklyPanelMissing(
            f"weekly_league.parquet has {len(wl)} rows, expected {_WEEKLY_LEAGUE_ROWS} (S8 pin)")
    return wl


def _week_range(season):
    return list(range(1, 18)) if season >= 2021 else list(range(1, 17))


def _weekly_matrices(df, season, wl, id_of):
    """(n x n_weeks) league/base points + played mask, via (nn,pos)->player_id map."""
    weeks = _week_range(season)
    n = len(df)
    Wl = np.zeros((n, len(weeks))); Wb = np.zeros((n, len(weeks)))
    played = np.zeros((n, len(weeks)), dtype=bool)
    sl = wl[(wl["season"] == season) & (wl["week"].isin(weeks))]
    g = sl.groupby(["player_id", "week"])[["pts_league", "pts_base"]].sum()
    wk_ix = {w: j for j, w in enumerate(weeks)}
    matched = 0
    for i, (nn, p) in enumerate(zip(df["nn"], df["position"])):
        pid = id_of.get((nn, p))
        if pid is None:
            continue
        matched += 1
        try:
            rows = g.loc[pid]
        except KeyError:
            continue
        for w, r in rows.iterrows():
            j = wk_ix.get(w)
            if j is not None:
                Wl[i, j] = r["pts_league"]; Wb[i, j] = r["pts_base"]; played[i, j] = True
    return weeks, Wl, Wb, played, matched


def _replacement(sl_season, wl, season):
    """Fixed replacement-level weekly fill per position/currency: mean weekly points, over played
    weeks in the graded range, of players season-ranked REPL[p]+1 .. REPL[p]+6 (waiver tier)."""
    weeks = _week_range(season)
    out_l, out_b = {}, {}
    slw = wl[(wl["season"] == season) & (wl["week"].isin(weeks))]
    for p, k in REPL.items():
        posdf = sl_season[sl_season["position"] == p]
        for cur, col, out in (("l", "total_league", out_l), ("b", "total_base", out_b)):
            tier = posdf.sort_values(col, ascending=False).iloc[k:k + 6]
            rows = slw[slw["player_id"].isin(tier["player_id"])]
            pts = rows["pts_league" if cur == "l" else "pts_base"]
            out[p] = float(pts.mean()) if len(pts) else 0.0
    out_l["FLEX"] = max(out_l[p] for p in FLEX_OK)
    out_b["FLEX"] = max(out_b[p] for p in FLEX_OK)
    return out_l, out_b


def legacy_pools(say=print):
    """The exact 33_ population, via 33_'s own load() + prereq_adjust. League totals joined as the
    SECONDARY currency (33_ never had it). Row order untouched (join by map, not merge)."""
    p = h33.load()
    slg = pd.read_parquet(os.path.join(HERE, "seasons_league.parquet"),
                          columns=["player_id", "season", "total_league", "total_base"])
    key = slg.set_index([slg["player_id"], slg["season"].astype(int)])
    lmap = key["total_league"].to_dict()
    pools = {}
    for s in sorted(p["season"].dropna().unique()):
        pool = p[p["season"] == s].copy()
        if len(pool) < 120:                     # 33_'s own gate (drops broken 2025: 5 priced rows)
            continue
        pool["_adj"] = pool.apply(h33.prereq_adjust, axis=1)
        pool = pool.reset_index(drop=True)
        pool["sd"] = np.interp(pool["adp"], _SD_ADP, _SD)   # only used by legacy_measured diagnostic
        pool["total_base"] = pool["total_pts"]  # 33_'s currency IS base PPR season points
        pool["total_league"] = [lmap.get((pid, int(s)), np.nan)
                                for pid in pool["player_id"]]
        miss = pool["total_league"].isna().sum()
        pool["total_league"] = pool["total_league"].fillna(0.0)
        say(f"  legacy pool {int(s)}: n={len(pool)} · league-total join misses={miss}")
        pools[int(s)] = Pool(s, pool, None, None, None, None, None, None)
    assert len(pools) == 10, f"legacy population must be the 10 seasons 2015-2024, got {len(pools)}"
    return pools


def assert_population(seasons, say=print):
    pop = json.load(open(os.path.join(HERE, "population.json")))
    pa = pop["pool_assert"]
    if not (pa["teams"] == TEAMS and pa["rounds"] == ROUNDS and pa["min_pool"] == MIN_POOL):
        raise PopulationMismatch(f"pool_assert drifted: {pa}")
    for s in seasons:
        ent = pop["per_season"].get(str(s))
        if ent is None:
            raise PopulationMismatch(f"season {s} missing from population.json")
        if s == 2025 and "Sleeper" not in ent["instrument"]:
            raise PopulationMismatch(f"2025 instrument must be the Sleeper repair, got {ent['instrument']}")
        if s >= 2020 and not ent.get("rows_priced_le300_sleeper_ext"):
            raise PopulationMismatch(f"season {s}: no <=300 extension rows in population.json")
    say(f"  population.json asserts OK for seasons {list(seasons)} "
        f"(teams {TEAMS}, rounds {ROUNDS}, min_pool {MIN_POOL}; 2025 instrument = Sleeper repair)")


def corrected_pools(say=print, clean=CLEAN):
    """CLEAN-season pools: 44_'s prep + extension padding + flags + league-panel weekly matrices."""
    assert_population(clean, say)
    with open(os.path.join(HERE, "blend_cache_2019_2025.json")) as f:
        cache = {int(k): v for k, v in json.load(f).items()}
    for s, nrows in _CACHE_ROWS.items():          # S8 pin
        assert len(cache[s]) == nrows, f"blend cache {s}: {len(cache[s])} rows, pinned {nrows}"
    ext = pd.read_csv(os.path.join(HERE, "adp_ext_sleeper_2020_2025.csv"))
    exp = pd.read_parquet(os.path.join(HERE, "seasons_exp.parquet"))
    rep = pd.read_parquet(os.path.join(HERE, "seasons_2025repair.parquet"))
    exp = pd.concat([exp[exp["season"] != 2025], rep], ignore_index=True)   # T0.2 union contract
    yr = exp.groupby("season").size()
    say("  seasons_exp∪repair per-year rows: " +
        ", ".join(f"{int(y)}:{c}" for y, c in yr.items() if y >= 2019))     # S8
    slg = pd.read_parquet(os.path.join(HERE, "seasons_league.parquet"))
    slg["nn"] = slg["name_disp"].map(normalize_name)
    wl = _load_weekly()
    pools = {}
    for s in clean:
        df = pd.DataFrame(cache[s])
        df = df[df["adp"] <= 220].reset_index(drop=True)                    # 44_'s prep filter
        df["nn"] = df["name"].map(normalize_name)
        # projection scaling on CACHE rows only (identical to 44_ prep), then pad
        for c in ("espn", "sleeper"):
            df[c + "_s"] = df[c] * (df["actual"].mean() / df[c].mean())
        df["proj"] = 0.5 * df["espn_s"] + 0.5 * df["sleeper_s"]
        have = set(zip(df["nn"], df["pos"]))
        es = ext[(ext["season"] == s) & (ext["adp"] <= 300)].copy()
        es = es[~es.apply(lambda r: (r["nn"], r["position"]) in have, axis=1)]
        es = es.drop_duplicates(subset=["nn", "position"])
        pad = pd.DataFrame({"name": es["name"], "pos": es["position"], "espn": np.nan,
                            "sleeper": np.nan, "actual": np.nan, "adp": es["adp"],
                            "nn": es["nn"], "espn_s": np.nan, "sleeper_s": np.nan, "proj": 0.0})
        n_pad = len(pad)
        df = pd.concat([df, pad], ignore_index=True)
        df["proj"] = df["proj"].fillna(0.0)
        # VOLS exactly as 44_ prep
        v = np.zeros(len(df)); pos, val = df["pos"].to_numpy(), df["proj"].to_numpy()
        for p, n_ in REPL.items():
            k = pos == p
            if k.sum() >= n_:
                v[k] = val[k] - np.sort(val[k])[::-1][n_ - 1]
            elif k.sum():
                v[k] = val[k] - val[k].min()
        df["vols"] = v
        df["position"] = df["pos"]
        df["adp_rank"] = df["adp"]
        df["sd"] = np.interp(df["adp"], _SD_ADP, _SD)
        # prerequisite flags from the exp∪repair panel (33_'s definitions, on the corrected pool)
        ex = exp[exp["season"] == s].drop_duplicates(subset=["nn", "position"])
        for col in ("prev_games", "prev_pos_rank_total"):
            m = ex.set_index([ex["nn"], ex["position"]])[col].to_dict()
            df[col] = [m.get((a, b), np.nan) for a, b in zip(df["nn"], df["position"])]
        df["adp_pos_rank"] = df.groupby("position")["adp"].rank(method="first")
        df["missed"] = (df["prev_games"] < 15).astype(int)
        df["proven"] = (df["prev_pos_rank_total"].fillna(99)
                        <= df["adp_pos_rank"].fillna(99)).astype(int)
        df["durable"] = (df["prev_games"] >= 15).astype(int)
        df["_adj"] = df.apply(h33.prereq_adjust, axis=1)
        df["_adj_pts"] = adp_nudge_to_points(df, df["_adj"].to_numpy())
        # actual outcomes from the LEAGUE panel (both currencies from the SAME panel + week range)
        id_of = {}
        dup = 0
        for (nn, p), grp in slg[slg["season"] == s].groupby(["nn", "position"]):
            if len(grp) > 1:
                dup += 1
                grp = grp.sort_values("total_league", ascending=False)
            id_of[(nn, p)] = grp["player_id"].iloc[0]
        weeks, Wl, Wb, played, matched = _weekly_matrices(df, s, wl, id_of)
        df["total_league"] = Wl.sum(axis=1)
        df["total_base"] = Wb.sum(axis=1)
        rl, rb = _replacement(slg[slg["season"] == s], wl, s)
        if len(df) < MIN_POOL:
            raise PoolTooSmall(f"season {s}: pool {len(df)} < {MIN_POOL} even after extension")
        active = df["actual"].notna().sum()
        say(f"  corrected pool {s}: n={len(df)} (cache {len(df) - n_pad} + ext pad {n_pad}) "
            f"· weekly-join matched {matched}/{len(df)} "
            f"({matched / len(df):.0%}; cache-row match "
            f"{df.loc[df['actual'].notna(), 'total_league'].gt(0).mean():.0%} of {active}) "
            f"· ambiguous nn+pos {dup} · repl wk (lg) " +
            " ".join(f"{p}:{rl[p]:.1f}" for p in ("QB", "RB", "WR", "TE")))
        pools[s] = Pool(s, df.reset_index(drop=True), weeks, Wl, Wb, played, rl, rb)
    return pools


def adp_nudge_to_points(df, adj_picks):
    """Map an ADP-slot nudge into the composite policy's currency (projected points) through the
    measured price-value curve: adj_pts = V(adp − adj) − V(adp), where V is a per-position
    monotone-decreasing envelope of VOLS over ADP (rolling-median smoothed). 'Move him N slots
    earlier ON THE VALUE CURVE' — no invented conversion constant."""
    out = np.zeros(len(df))
    for p, g in df.groupby("position"):
        g = g.sort_values("adp")
        x = g["adp"].to_numpy(float)
        y = g["vols"].rolling(7, center=True, min_periods=1).median().to_numpy(float)
        y = np.maximum.accumulate(y[::-1])[::-1]          # monotone non-increasing envelope
        xu, iu = np.unique(x, return_index=True)
        yu = y[iu]
        idx = g.index.to_numpy()
        a = df.loc[idx, "adp"].to_numpy(float)
        adj = np.asarray(adj_picks, float)[df.index.get_indexer(idx)]
        out[df.index.get_indexer(idx)] = np.interp(a - adj, xu, yu) - np.interp(a, xu, yu)
    return out


# =================================================================================================
# SIMULATOR — one snake draft; branch per policy, mechanics verbatim from the template it mirrors
# =================================================================================================
def _my_picks(slot):
    return [((r - 1) * TEAMS + slot) if r % 2 else (r * TEAMS - slot + 1)
            for r in range(1, ROUNDS + 1)]


def simulate(pool, cfg, my_slot, rng, use_delta):
    """Returns (roster indices tuple). Scoring is applied separately so one draft can be graded in
    every currency/mode without re-drafting."""
    n = pool.n
    adp, pos = pool.adp, pool.pos
    if cfg.opponent_noise == "flat":
        noise = rng.normal(0, cfg.flat_sd, n)             # 33_'s exact draw
    else:
        noise = rng.normal(0, 1, n) * pool.sd             # 44_'s exact draw
    order_key = adp + noise
    taken = np.zeros(n, dtype=bool)
    ros = {t: {"QB": 0, "RB": 0, "WR": 0, "TE": 0} for t in range(1, TEAMS + 1)}
    mine, mypk = [], _my_picks(my_slot)
    overall = 0
    for rd in range(1, ROUNDS + 1):
        seats = range(1, TEAMS + 1) if rd % 2 else range(TEAMS, 0, -1)
        for t in seats:
            overall += 1
            av = ~taken
            if not av.any():
                continue
            c = ros[t]
            ok = av & np.array([c[p] < MAXP[p] for p in pos])
            if not ok.any():
                ok = av
            if t == my_slot and cfg.policy == "adp":
                # 33_'s my-seat rule, verbatim: ADP order, minus the nudge, need-filtered
                score = order_key.copy()
                if use_delta:
                    score = score - pool.adj
                need = np.array([(c[p] < START[p]) or (p in FLEX_OK) or (c[p] < MAXP[p])
                                 for p in pos])
                if (ok & need).any():
                    ok = ok & need
                idx = np.where(ok)[0]
                pick = idx[np.argmin(score[idx])]
            elif t == my_slot:
                # 44_'s my-seat rule, verbatim: VONA + roster-need gating (+ the policy delta)
                idx = np.where(ok)[0]
                if len(idx) == 0:
                    continue
                nxt = next((p_ for p_ in mypk if p_ > overall), None)
                sub = pool.df.iloc[idx]
                if nxt:
                    scored = advisor.add_vona(sub.copy(), nxt)["vona"].to_numpy(float).copy()
                else:
                    scored = sub["vols"].to_numpy(float).copy()
                cnt0 = {p: 0 for p in START}
                for i in mine:
                    if pos[i] in cnt0:
                        cnt0[pos[i]] += 1
                ded_open = {p for p in START if cnt0[p] < START[p]}
                flex_filled = sum(max(0, cnt0[p] - START[p]) for p in FLEX_OK) >= 1
                for j, gi in enumerate(idx):
                    p = pos[gi]
                    if p in ded_open:
                        pass
                    elif p in FLEX_OK and not flex_filled:
                        scored[j] -= 15.0
                    elif ded_open:
                        scored[j] -= 30.0
                    if use_delta:
                        scored[j] += pool.adj_pts[gi]
                pick = idx[int(np.argmax(scored))]
            else:
                idx = np.where(ok)[0]
                if len(idx) == 0:
                    continue
                pick = idx[int(np.argmin(order_key[idx]))]
            taken[pick] = True
            ros[t][pos[pick]] += 1
            if t == my_slot:
                mine.append(pick)
    return tuple(mine)


# =================================================================================================
# SCORING — season mode (33_'s optimal_lineup, imported) and weekly mode (D1 hindsight-optimal)
# =================================================================================================
def score_season(pool, mine, currency):
    pts = pool.t_league if currency == "league" else pool.t_base
    return h33.optimal_lineup(pool.pos[np.array(mine)], pts[np.array(mine)])


def score_weekly(pool, mine, currency):
    if pool.W_league is None:
        raise WeeklyPanelMissing("weekly matrices not built for this pool")
    W = pool.W_league if currency == "league" else pool.W_base
    repl = pool.repl_league if currency == "league" else pool.repl_base
    mine = np.array(mine)
    pmine = pool.pos[mine]
    total = 0.0
    for j in range(W.shape[1]):
        wk = {p: sorted(W[mine[pmine == p], j][pool.played[mine[pmine == p], j]], reverse=True)
              for p in ("QB", "RB", "WR", "TE")}
        used = {}
        for p, k in START.items():
            take = wk[p][:k]
            total += sum(take) + repl[p] * (k - len(take))   # replacement fill for empty slots
            used[p] = len(take)
        flex = [x for p in FLEX_OK for x in wk[p][used[p]:]]
        total += max(flex) if flex else repl["FLEX"]
    return total


def grade(pool, mine, cfg):
    """(league, base) in the config's mode, plus season-mode league/base as diagnostics."""
    out = {"season_league": score_season(pool, mine, "league"),
           "season_base": score_season(pool, mine, "base")}
    if cfg.scoring == "weekly":
        out["weekly_league"] = score_weekly(pool, mine, "league")
        out["weekly_base"] = score_weekly(pool, mine, "base")
        out["league"], out["base"] = out["weekly_league"], out["weekly_base"]
    else:
        out["league"], out["base"] = out["season_league"], out["season_base"]
    return out


# =================================================================================================
# PAIRED RUN + REPORT
# =================================================================================================
def run_paired(pools, cfg, say=print, zero_adj_nn=None):
    """Paired drafts: base arm vs base+delta, identical seeds. Returns the raw results dict.
    `zero_adj_nn`: jackknife — zero the delta for this normalized name in every season."""
    cfg.validate()
    res = {}
    for slot in cfg.slots:
        for s, pool in pools.items():
            if zero_adj_nn is not None:
                mask = (pool.df["nn"] == zero_adj_nn).to_numpy()
                sv_adj, sv_pts = pool.adj.copy(), pool.adj_pts.copy()
                pool.adj = np.where(mask, 0.0, pool.adj)
                pool.adj_pts = np.where(mask, 0.0, pool.adj_pts)
            dl, db, dsl, dsb, nchg, flag_picks = [], [], [], [], [], {}
            for i in range(cfg.n_drafts):
                rng_a = np.random.default_rng(cfg.seed_base + i)
                rng_b = np.random.default_rng(cfg.seed_base + i)
                m0 = simulate(pool, cfg, slot, rng_a, use_delta=False)
                m1 = simulate(pool, cfg, slot, rng_b, use_delta=True)
                g0, g1 = grade(pool, m0, cfg), grade(pool, m1, cfg)
                dl.append(g1["league"] - g0["league"])
                db.append(g1["base"] - g0["base"])
                dsl.append(g1["season_league"] - g0["season_league"])
                dsb.append(g1["season_base"] - g0["season_base"])
                nchg.append(len(set(m1) - set(m0)))
                for i_ in set(m1) - set(m0):
                    if pool.adj[i_] != 0:
                        nn = pool.df["nn"].iloc[i_]
                        flag_picks[nn] = flag_picks.get(nn, 0) + 1
            if zero_adj_nn is not None:
                pool.adj, pool.adj_pts = sv_adj, sv_pts
            res[(slot, s)] = {"dl": np.array(dl), "db": np.array(db),
                              "dsl": np.array(dsl), "dsb": np.array(dsb),
                              "nchg": np.array(nchg), "flag_picks": flag_picks}
            say(f"    slot {slot} season {s}: Δleague {np.mean(dl):+7.1f} · Δbase "
                f"{np.mean(db):+7.1f} · identical {np.mean(np.array(dl) == 0):.0%}")
    return res


# Student-t quantiles (no scipy in the venv): {df: (t_.975, t_.80)}. Standard table values.
_T_TABLE = {1: (12.706, 1.376), 2: (4.303, 1.061), 3: (3.182, 0.978), 4: (2.776, 0.941),
            5: (2.571, 0.920), 6: (2.447, 0.906), 7: (2.365, 0.896), 8: (2.306, 0.889),
            9: (2.262, 0.883), 10: (2.228, 0.879), 11: (2.201, 0.876), 12: (2.179, 0.873),
            15: (2.131, 0.866), 20: (2.086, 0.860), 30: (2.042, 0.854)}


def _t_quantiles(df):
    if df in _T_TABLE:
        return _T_TABLE[df]
    k = min(_T_TABLE, key=lambda d: abs(d - df))
    return _T_TABLE[k]


def cluster_ci(season_means):
    """Season-clustered mean, SE, 95% t-CI, and 80%-power MDE (S11). Effective n = #seasons."""
    m = np.array(season_means, float)
    n = len(m)
    mu, sd = m.mean(), m.std(ddof=1)
    se = sd / np.sqrt(n)
    t975, t80 = _t_quantiles(n - 1)
    return {"mean": mu, "se": se, "lo": mu - t975 * se, "hi": mu + t975 * se, "n": n,
            "sd": sd, "mde80": (t975 + t80) * se, "mde80_normal": 2.80 * se}


def report_primary(res, say=print, label=""):
    """The charter's mandatory reporting block. PRIMARY ENDPOINT (S14, declared here, baked in):
    treatment-arm MINUS base-arm total in LEAGUE points, the config's declared mode, pooled over
    slots and drafts, with the season-clustered 95% CI and season count as effective n. Everything
    else printed here is SECONDARY."""
    slots = sorted({k[0] for k in res})
    seasons = sorted({k[1] for k in res})
    say(f"\n  PRIMARY ENDPOINT [{label}]: Δ(treatment − base) LEAGUE points, "
        f"season-clustered (S11, n={len(seasons)} season clusters)")
    per_season = {s: np.concatenate([res[(sl, s)]["dl"] for sl in slots]) for s in seasons}
    ci = cluster_ci([per_season[s].mean() for s in seasons])
    D = np.concatenate([per_season[s] for s in seasons])
    Db = np.concatenate([res[(sl, s)]["db"] for sl in slots for s in seasons])
    NC = np.concatenate([res[(sl, s)]["nchg"] for sl in slots for s in seasons])
    say(f"    pooled mean {ci['mean']:+.1f} league pts · clustered 95% CI "
        f"[{ci['lo']:+.1f}, {ci['hi']:+.1f}] · season SD {ci['sd']:.1f} · eff n = {ci['n']} seasons")
    say(f"    MDE at 80% power (this instrument): ±{ci['mde80']:.0f} league pts "
        f"(t-based, df={ci['n'] - 1}; normal-approx ±{ci['mde80_normal']:.0f})")
    say(f"    secondary currency (base PPR): {Db.mean():+.1f} pts")
    say(f"    drafts identical: {np.mean(D == 0):.1%} · mean picks changed {NC.mean():.2f} "
        f"(when ≥1 changed: {NC[NC > 0].mean():.2f} picks, Δleague "
        f"{D[NC > 0].mean():+.1f} pts)" if (NC > 0).any() else
        f"    drafts identical: {np.mean(D == 0):.1%} · no picks ever changed")
    say(f"    per-season Δleague: " +
        " ".join(f"{s}:{per_season[s].mean():+.0f}" for s in seasons))
    say(f"    per-slot Δleague:   " +
        " ".join(f"slot{sl}:{np.concatenate([res[(sl, s)]['dl'] for s in seasons]).mean():+.0f}"
                 for sl in slots))
    say(f"    win {np.mean(D > 0):.1%} · lose {np.mean(D < 0):.1%} · tie {np.mean(D == 0):.1%}")
    return ci, D, Db, NC


def top_flagged(res):
    """Most-frequently drafted-in flagged player (jackknife target)."""
    agg = {}
    for v in res.values():
        for nn, k in v["flag_picks"].items():
            agg[nn] = agg.get(nn, 0) + k
    return sorted(agg.items(), key=lambda kv: -kv[1])
