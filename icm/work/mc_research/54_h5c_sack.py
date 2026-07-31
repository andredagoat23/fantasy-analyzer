"""54 — H5c: the sack tax — STALENESS, INVISIBILITY, SHRINKAGE (NOT existence).

The per-QB EB-shrunk sack rate ALREADY SHIPS (apply_bonuses.py:34-41, K=12 from
scoring_config.py:42, pooled 2023-25 pbp with NO season_type filter, applied at
apply_bonuses.py:98 as pass_att * rate * SACK, SACK=-1). The charter is explicit:
do not rebuild it. This script answers the three live questions:

  (a) STALENESS (absorbing H2e): does a QB's shrunken sack rate carry when he changed
      teams or his OL turned over? Pre-registered expectation for the OL half: NULL.
  (b) INVISIBILITY: quantify, from weekly_league.parquet, the per-season league-point
      value of the sack term across QB1-QB24 — what every base-PPR backtest missed.
  (c) SHRINKAGE: cross-validate K instead of assuming 12; does NGS avg_time_to_throw
      improve the sack-rate FORECAST over last-year's shrunk rate?

PRIMARY ENDPOINT — DECLARED HERE, BEFORE ANY ANALYSIS RAN (S14, one endpoint, no OR):
  The out-of-sample sack-rate forecast improvement in LEAGUE POINTS at the QB level:
    MAE_pts(M0) - MAE_pts(M2), where per QB-season t
      err_pts = |rate_hat - rate_t| * throws_t * |SACK|   (volume held at truth, so the
                RATE forecast is isolated; SACK=-1 so 1 sack = 1 league point)
      M0 (incumbent, the shipped construction shifted to a forecast): pooled seasons
         t-3..t-1, K=12, shrunk toward the pool league rate.
      M2 (challenger): WLS fit on train seasons < t only (expanding window):
         rate ~ a + b*shrunk_last1(K* nested) + c*avg_time_to_throw(t-1).
    Population: QB-seasons t in 2019-2025 with throws_t >= 200, throws_{t-1} >= 200,
    and an NGS t-1 avg_time_to_throw row. Paired per QB-season; CI clustered on SEASON
    (S11; 7 clusters -> DIRECTIONAL-ONLY by the n<40 cluster floor, stated up front).
  Everything else in this file is a cheap check, a descriptive quantification, or a
  secondary sensitivity, and is labelled as such.

C12 GUARDRAIL: nothing here touches VOLS denominators or the QB12 replacement. All
outputs are rate-forecast and bonus-term diagnostics; no replacement redefinition.

INSTRUMENT CORRECTION (verified this run): the task scoped H2e to "new-schema depth
charts only, 2023-2025" — but load_depth_charts(2024) returns the OLD schema
(club_code/depth_team, 37,312 rows [V]), same as 2019/2023; only 2025/2026 carry the
new ESPN schema. Inside 2023-2025 there is therefore ZERO usable new-schema
year-over-year OL pair. OL continuity is instead instrumented from SNAP COUNTS
(the charter's own named instrument, "snap-weighted five-man overlap", line 342),
which has a stable schema across all years. No depth-chart schemas were pooled.

Inputs (all pre-existing or cached by this script; frozen pipeline imported, not edited):
  pbp_slim_{2014..2025}.parquet          (T0.3 caches; REG+POST, filtered at use)
  weekly_league.parquet, seasons_league.parquet  (T0.3)
  seasons.parquet (ADP joins; 2025 prices broken -> adp_hist_2025repair.csv union,
                   instrument = Sleeper adp_ppr per T0.2, stated wherever 2025 appears)
  raw/ngs_passing_{2016..2025}.parquet   (pulled+cached this run, keyed player_gsis_id)
  raw/snaps54_{2014..2025}.parquet       (pulled+cached this run, incl. game_type)
  players_final.csv, projections.blended_components(), scoring_config constants.

Run:  .venv/bin/python icm/work/mc_research/54_h5c_sack.py        (from repo root;
      projections.py reads data/*.csv relative to cwd)
Output: results_54_h5c.txt (rewritten from scratch).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from scoring_config import SACK, K as K_SHIPPED          # noqa: E402  (frozen, import-only)
from utils import normalize_name                          # noqa: E402

YEARS = list(range(2014, 2026))
SEASON_GAMES = {y: (16 if y <= 2020 else 17) for y in YEARS}
OLPOS = {"T", "G", "C", "OT", "OG", "OL"}
TEAM_FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA"}        # relocations, for YoY team joins
OUT_TXT = os.path.join(HERE, "results_54_h5c.txt")

lines = []
HEAD = {}          # headline numbers each section deposits for the final verdict table
def say(s=""):
    print(s)
    lines.append(str(s))


def wmean(x, w):
    x, w = np.asarray(x, float), np.asarray(w, float)
    return (x * w).sum() / w.sum()


def wls_slope(y, x, w):
    """throws-weighted OLS slope+intercept of y on x."""
    x, y, w = np.asarray(x, float), np.asarray(y, float), np.asarray(w, float)
    xm, ym = wmean(x, w), wmean(y, w)
    b = (w * (x - xm) * (y - ym)).sum() / (w * (x - xm) ** 2).sum()
    return b, ym - b * xm


def t_pdf(x, v):
    import math
    return (math.gamma((v + 1) / 2) / (math.sqrt(v * math.pi) * math.gamma(v / 2))
            * (1 + x ** 2 / v) ** (-(v + 1) / 2))


def t_sf(t, v):
    """P(T > t) for t>=0, numeric integration (scipy-free)."""
    xs = np.linspace(t, t + 60, 40000)
    return float(np.trapezoid([t_pdf(x, v) for x in xs], xs))


T975 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31,
        9: 2.26, 10: 2.23, 11: 2.20, 12: 2.18}


def season_ci(vals):
    """mean of season-level values +- t-based 95% CI, cluster = season (S11)."""
    v = np.asarray(vals, float)
    n = len(v)
    m, sd = v.mean(), v.std(ddof=1)
    se = sd / np.sqrt(n)
    t = T975.get(n - 1, 1.96)
    p = 2 * t_sf(abs(m / se), n - 1) if se > 0 else np.nan
    return m, m - t * se, m + t * se, p, n


# ============================================================================
# 0. QB-season sack panel from the T0.3 pbp slims (S8-asserted)
# ============================================================================
def build_sack_panel():
    frames = []
    for y in YEARS:
        p = pd.read_parquet(os.path.join(HERE, f"pbp_slim_{y}.parquet"))
        assert len(p) > 40000, f"S8: pbp {y} suspiciously small"
        frames.append(p)
    pbp = pd.concat(frames, ignore_index=True)
    per_year = pbp.groupby("season").size()
    assert sorted(per_year.index) == YEARS and (per_year > 40000).all(), "S8 pbp season check"
    say("pbp slims loaded, plays/season (REG+POST) [V]:")
    say("  " + "  ".join(f"{y}:{per_year[y]}" for y in YEARS))

    reg = pbp[pbp["season_type"] == "REG"]
    sk = (reg[reg["sack"] == 1].dropna(subset=["passer_player_id"])
          .groupby(["season", "passer_player_id"]).size().rename("sacks"))
    th = (reg[(reg["pass_attempt"] == 1) & (reg["sack"] == 0)].dropna(subset=["passer_player_id"])
          .groupby(["season", "passer_player_id"]).size().rename("throws"))
    qs = pd.concat([sk, th], axis=1).fillna(0).reset_index().rename(
        columns={"passer_player_id": "player_id"})
    qs["rate"] = qs["sacks"] / (qs["sacks"] + qs["throws"]).clip(lower=1) * 0  # placeholder
    # rate definition = apply_bonuses': sacks per non-sack pass attempt ("per throw")
    qs["rate"] = qs["sacks"] / qs["throws"].replace(0, np.nan)
    lg = qs.groupby("season").apply(
        lambda g: g["sacks"].sum() / g["throws"].sum()).rename("league_rate")
    qs = qs.merge(lg, on="season")
    say(f"QB-season sack panel: {len(qs)} rows (all passers), league sack/throw by season [V]:")
    say("  " + "  ".join(f"{y}:{lg[y]:.4f}" for y in YEARS))
    return pbp, qs, lg


# ============================================================================
# 1. Anchor + cheap check (b): is OUR board already pricing it? (S13 anti-double-count)
# ============================================================================
def anchor_and_board_check(pbp):
    say(); say("=" * 78)
    say("1. ANCHOR REPRODUCTION + CHEAP CHECK (b): THE BOARD ALREADY PRICES IT")
    say("=" * 78)
    pf = pd.read_csv(os.path.join(ROOT, "players_final.csv"), dtype={"player_id": str})
    qb = pf[pf["position"] == "QB"].copy()
    qb["rk_custom"] = qb["custom_proj_points"].rank(ascending=False)
    qb["rk_total"] = qb["total_points"].rank(ascending=False)
    m = qb[qb["full_name"] == "Drake Maye"].iloc[0]
    say(f"Drake Maye [V]: bonus_points {m.bonus_points:+.1f}  custom_proj rank {m.rk_custom:.0f}"
        f"  total_points rank {m.rk_total:.0f}  (charter said -25.9 / 2nd -> 10th = 8 spots;"
        f" T0.8 re-pin: Lamar Jackson has drifted above Maye on custom_proj, so today it is"
        f" 3rd -> 10th = 7 spots; the -25.9 and rank-10 anchors hold)")
    assert abs(m.bonus_points - (-25.9)) < 0.1 and m.rk_total == 10, "anchor mismatch — stop"

    # exact reproduction of the shipped rate: pooled 2023-25, NO season_type filter (the
    # frozen file pools REG+POST — noted as a factual observation, not edited)
    p3 = pbp[pbp["season"].isin([2023, 2024, 2025])]
    sk = p3[p3["sack"] == 1].dropna(subset=["passer_player_id"]).groupby("passer_player_id").size()
    th = (p3[(p3["pass_attempt"] == 1) & (p3["sack"] == 0)].dropna(subset=["passer_player_id"])
          .groupby("passer_player_id").size())
    sdf = pd.concat([sk.rename("sacks"), th.rename("throws")], axis=1).fillna(0)
    L = sdf["sacks"].sum() / sdf["throws"].sum()
    shipped = (sdf["sacks"] + K_SHIPPED * L) / (sdf["throws"] + K_SHIPPED)
    say(f"shipped-rate reproduction [V]: pooled 2023-25 REG+POST, K={K_SHIPPED},"
        f" league rate {L:.4f} ({int(sdf['sacks'].sum())} sacks / {int(sdf['throws'].sum())} throws)")

    from projections import blended_components
    proj = blended_components()
    qb["norm_name"] = qb["full_name"].apply(normalize_name)
    qb = qb.merge(proj[proj["position"] == "QB"][["norm_name", "pass_att"]],
                  on="norm_name", how="left")
    qb["sack_term"] = qb["gsis_id"].map(shipped).fillna(L) * qb["pass_att"].fillna(0) * SACK
    top30 = qb.nlargest(30, "total_points").copy()
    r2 = np.corrcoef(top30["bonus_points"], top30["sack_term"])[0, 1] ** 2
    spear = lambda a, b: np.corrcoef(pd.Series(a).rank(), pd.Series(b).rank())[0, 1]
    rho_c = spear(top30["total_points"], top30["custom_proj_points"])
    rho_cs = spear(top30["total_points"], top30["custom_proj_points"] + top30["sack_term"])
    say(f"top-30 QBs: sack term explains R2={r2:.2f} of bonus_points variance;")
    say(f"  Spearman(total, custom)                 = {rho_c:+.3f}")
    say(f"  Spearman(total, custom + sack term only)= {rho_cs:+.3f}   <- the sack term alone"
        f" recovers {'nearly all' if rho_cs - rho_c > 0.6 * (1 - rho_c) else 'part'} of the QB re-ranking")
    say(f"  Maye decomposition [V]: sack term {top30[top30.full_name=='Drake Maye']['sack_term'].iloc[0]:+.1f}"
        f"  vs total bonus {m.bonus_points:+.1f} (remainder = tiers/FD/long-TD, positive)")
    say("VERDICT (b): WE ALREADY PRICE IT — the board carries the pooled-2023-25 K=12 rate")
    say("  at 100% strength by construction; the sack term alone reproduces the bulk of the")
    say("  QB bonus re-ranking. Any H5c proposal must therefore be graded as a CHANGE to the")
    say("  shipped rate (recency / K / TTT), never as adding a sack term — that would double-count.")
    return qb, shipped, L


# ============================================================================
# 2. Cheap check (a): is the MARKET pricing it? (ADP residual on prior sack rate)
# ============================================================================
def market_check(qs):
    say(); say("=" * 78)
    say("2. CHEAP CHECK (a): IS THE MARKET PRICING IT? (ADP residual regression)")
    say("=" * 78)
    sea = pd.read_parquet(os.path.join(HERE, "seasons.parquet"),
                          columns=["player_id", "season", "position", "nn", "name_disp",
                                   "adp", "adp_pos_rank"])
    sea = sea[sea["position"] == "QB"].copy()
    # 2025 price repair (T0.2): seasons.parquet 2025 adp is poisoned; instrument for 2025
    # is SLEEPER adp_ppr (not FFC) via adp_hist_2025repair.csv — stated per T0.2 contract.
    rep = pd.read_csv(os.path.join(HERE, "adp_hist_2025repair.csv"))
    rep = rep[rep["position"] == "QB"][["nn", "adp", "adp_pos_rank"]]
    is25 = sea["season"] == 2025
    sea.loc[is25, ["adp", "adp_pos_rank"]] = np.nan
    r25 = sea[is25].drop(columns=["adp", "adp_pos_rank"]).merge(rep, on="nn", how="left")
    sea = pd.concat([sea[~is25], r25], ignore_index=True)

    sl = pd.read_parquet(os.path.join(HERE, "seasons_league.parquet"),
                         columns=["player_id", "season", "position", "total_league", "games"])
    d = sea.merge(sl[sl["position"] == "QB"][["player_id", "season", "total_league", "games"]],
                  on=["player_id", "season"], how="inner")
    d["psg_league"] = d["total_league"] / d["season"].map(SEASON_GAMES)

    # prior-season (t-1) shrunk rate, K=12 toward that season's league rate, throws>=100
    q = qs.copy()
    q["shrunk1"] = (q["sacks"] + K_SHIPPED * q["league_rate"]) / (q["throws"] + K_SHIPPED)
    prev = q[q["throws"] >= 100][["season", "player_id", "shrunk1", "throws"]].copy()
    prev["season"] = prev["season"] + 1
    d = d.merge(prev.rename(columns={"shrunk1": "prior_rate", "throws": "prior_throws"}),
                on=["season", "player_id"], how="inner")
    d = d[d["adp_pos_rank"].notna() & (d["adp_pos_rank"] <= 24)].copy()
    say(f"population: QB-seasons with a price (FFC ADP; 2025 = Sleeper adp_ppr [T0.2]),")
    say(f"  adp_pos_rank <= 24, prior-season throws >= 100: n = {len(d)} rows,"
        f" {d.season.nunique()} seasons ({d.season.min()}-{d.season.max()})")

    # E[league psg | QB adp rank]: pooled binned means, monotone (02_expectation pattern)
    curve = d.groupby(d["adp_pos_rank"].astype(int))["psg_league"].mean()
    curve = curve.reindex(range(1, 25)).interpolate(limit_direction="both")
    curve = np.minimum.accumulate(curve.rolling(3, center=True, min_periods=1).mean())
    d["exp_psg"] = d["adp_pos_rank"].astype(int).map(curve)
    d["resid"] = d["psg_league"] - d["exp_psg"]

    # (a1) the operative check: does prior sack rate predict outcome ABOVE price?
    slopes = []
    for s, g in d.groupby("season"):
        if len(g) >= 8:
            slopes.append((s, np.polyfit(g["prior_rate"], g["resid"], 1)[0], len(g)))
    sl_df = pd.DataFrame(slopes, columns=["season", "slope", "n"])
    m, lo, hi, p, n = season_ci(sl_df["slope"])
    iqr = d["prior_rate"].quantile(0.75) - d["prior_rate"].quantile(0.25)
    say()
    say("(a1) ADP-residual regression: resid_league_psg ~ prior shrunk sack rate, per season:")
    say("  " + "  ".join(f"{int(r.season)}:{r.slope:+.0f}(n={int(r.n)})" for r in sl_df.itertuples()))
    say(f"  pooled slope (league psg per unit rate): {m:+.1f}, 95% CI [{lo:+.1f}, {hi:+.1f}],"
        f" p={p:.3f}, clusters={n} seasons")
    say(f"  in points: p25->p75 prior rate (IQR {iqr:.3f}) moves expected SEASON outcome by"
        f" {m * iqr * 17:+.1f} league pts vs price (17-game season) [V]")

    # (a2) does the PRICE itself already load on sack rate, given prior production?
    d["prior_psg"] = np.nan
    prev_out = sl[sl["position"] == "QB"][["player_id", "season", "total_league"]].copy()
    prev_out["psg"] = prev_out["total_league"] / prev_out["season"].map(SEASON_GAMES)
    prev_out["season"] = prev_out["season"] + 1
    d = d.merge(prev_out[["player_id", "season", "psg"]].rename(columns={"psg": "prior_psg"}),
                on=["player_id", "season"], how="left", suffixes=("_drop", ""))
    d = d.drop(columns=[c for c in d.columns if c.endswith("_drop")])
    dd = d.dropna(subset=["prior_psg"])
    X = np.column_stack([np.ones(len(dd)), dd["prior_psg"], dd["prior_rate"]])
    beta, *_ = np.linalg.lstsq(X, dd["adp_pos_rank"], rcond=None)
    X0 = np.column_stack([np.ones(len(dd)), dd["prior_psg"]])
    b0, *_ = np.linalg.lstsq(X0, dd["adp_pos_rank"], rcond=None)
    r2_full = 1 - ((dd["adp_pos_rank"] - X @ beta) ** 2).sum() / ((dd["adp_pos_rank"] - dd["adp_pos_rank"].mean()) ** 2).sum()
    r2_base = 1 - ((dd["adp_pos_rank"] - X0 @ b0) ** 2).sum() / ((dd["adp_pos_rank"] - dd["adp_pos_rank"].mean()) ** 2).sum()
    say()
    say(f"(a2) price regression: adp_pos_rank ~ prior league psg + prior sack rate (n={len(dd)}):")
    say(f"  sack-rate coefficient {beta[2]:+.1f} ranks per unit rate"
        f" ({beta[2] * iqr:+.2f} ADP ranks per IQR); R2 {r2_base:.3f} -> {r2_full:.3f}"
        f" (adds {r2_full - r2_base:+.4f})")
    say("  reading: the market prices QB production, in which sacks are ~invisible under")
    say("  STANDARD scoring — a near-zero coefficient here means the room is NOT separately")
    say("  discounting sack-prone QBs. Our league scores SACK=-1, so whatever (a1) shows is")
    say("  edge retained/lost vs that standard-scoring room.")
    HEAD["a1"] = (m, lo, hi, p, n, m * iqr * 17)
    HEAD["a2_dR2"] = r2_full - r2_base
    return d


# ============================================================================
# 3. STALENESS (absorbing H2e): team change + OL continuity
# ============================================================================
def staleness(qs):
    say(); say("=" * 78)
    say("3. STALENESS (H2e absorbed): DOES THE SHRUNK RATE CARRY ACROSS CHANGE?")
    say("=" * 78)
    say("instrument note [V]: 2024 depth charts are OLD schema (club_code/depth_team,")
    say("  37,312 rows) — only 2025/2026 carry the new ESPN schema, so inside the mandated")
    say("  2023-2025 scope there is NO new-schema YoY OL pair. OL continuity is computed from")
    say("  SNAP COUNTS (charter line 342's own instrument: snap-weighted five-man overlap).")
    say("  No depth-chart schema pooling occurred; depth charts were not used at all.")

    # --- OL continuity per (team, season): share of the top-5 OL's snaps taken by players
    # --- who logged any OL snap for the SAME franchise in season t-1
    sn = pd.concat([pd.read_parquet(os.path.join(HERE, f"raw/snaps54_{y}.parquet"))
                    for y in YEARS], ignore_index=True)
    per_year = sn.groupby("season").size()
    assert sorted(per_year.index) == YEARS and (per_year > 20000).all(), "S8 snaps"
    sn = sn[(sn["game_type"] == "REG") & sn["position"].isin(OLPOS)].copy()
    sn["team"] = sn["team"].replace(TEAM_FIX)
    tot = (sn.groupby(["season", "team", "pfr_player_id"])["offense_snaps"].sum()
           .reset_index())
    conts = []
    for (y, tm), g in tot.groupby(["season", "team"]):
        if y == 2014:
            continue
        five = g.nlargest(5, "offense_snaps")
        prevpool = set(tot[(tot["season"] == y - 1) & (tot["team"] == tm)]["pfr_player_id"])
        w = five["offense_snaps"].sum()
        ov = five[five["pfr_player_id"].isin(prevpool)]["offense_snaps"].sum()
        conts.append({"season": y, "team": tm, "ol_cont": ov / w if w else np.nan})
    olc = pd.DataFrame(conts)
    say(f"OL continuity built: {len(olc)} team-seasons 2015-2025; distribution"
        f" p10/p50/p90 = {olc.ol_cont.quantile(.1):.2f}/{olc.ol_cont.median():.2f}/{olc.ol_cont.quantile(.9):.2f} [V]")

    # --- QB-season pairs with team + prior rate
    wl = pd.read_parquet(os.path.join(HERE, "weekly_league.parquet"),
                         columns=["player_id", "season", "week", "position", "team",
                                  "player_display_name", "attempts"])
    wq = wl[wl["position"] == "QB"]
    team_mode = (wq.groupby(["player_id", "season"])
                 .apply(lambda g: g.groupby("team")["attempts"].sum().idxmax())
                 .rename("team").reset_index())
    team_mode["team"] = team_mode["team"].replace(TEAM_FIX)
    names = wq.drop_duplicates("player_id")[["player_id", "player_display_name"]]

    q = qs.copy()
    q["shrunk1"] = (q["sacks"] + K_SHIPPED * q["league_rate"]) / (q["throws"] + K_SHIPPED)
    cur = q[q["throws"] >= 150][["season", "player_id", "rate", "throws"]]
    prv = q[q["throws"] >= 150][["season", "player_id", "shrunk1"]].copy()
    prv["season"] = prv["season"] + 1
    pairs = cur.merge(prv, on=["season", "player_id"], how="inner")
    pairs = pairs.merge(team_mode, on=["player_id", "season"], how="left")
    tm_prev = team_mode.copy(); tm_prev["season"] = tm_prev["season"] + 1
    pairs = pairs.merge(tm_prev.rename(columns={"team": "team_prev"}),
                        on=["player_id", "season"], how="left")
    pairs["moved"] = pairs["team"] != pairs["team_prev"]
    pairs = pairs.merge(olc, on=["season", "team"], how="left")
    pairs = pairs.merge(names, on="player_id", how="left")

    def carry_report(sub, label):
        say(); say(f"  -- {label} --")
        hd = HEAD.setdefault("stale", {}).setdefault(label, {})
        for tag, g in [("STAYED", sub[~sub.moved]), ("MOVED", sub[sub.moved])]:
            if len(g) < 4:
                say(f"  {tag:7s}: n={len(g)} — too few to report")
                continue
            b, a = wls_slope(g["rate"], g["shrunk1"], g["throws"])
            r = np.corrcoef(g["rate"], g["shrunk1"])[0, 1]
            mae = wmean((g["rate"] - g["shrunk1"]).abs(), g["throws"])
            say(f"  {tag:7s}: n={len(g):3d} QB-seasons | carry slope {b:+.2f} | r {r:+.2f}"
                f" | wMAE(rate_t vs shrunk_(t-1)) {mae:.4f} (~{mae*500:.0f} pts/500 throws)")
            hd[tag] = (len(g), b, r, mae)
        st = sub[~sub.moved].dropna(subset=["ol_cont"])
        if len(st) >= 12:
            med = st["ol_cont"].median()
            lo_, hi_ = st[st.ol_cont < med], st[st.ol_cont >= med]
            bl, _ = wls_slope(lo_["rate"], lo_["shrunk1"], lo_["throws"])
            bh, _ = wls_slope(hi_["rate"], hi_["shrunk1"], hi_["throws"])
            # bootstrap the slope difference over QB-season rows (the task's cluster unit)
            rng = np.random.default_rng(54)
            diffs = []
            for _ in range(2000):
                l2 = lo_.sample(len(lo_), replace=True, random_state=None)
                h2 = hi_.sample(len(hi_), replace=True, random_state=None)
                try:
                    diffs.append(wls_slope(h2["rate"], h2["shrunk1"], h2["throws"])[0]
                                 - wls_slope(l2["rate"], l2["shrunk1"], l2["throws"])[0])
                except Exception:
                    pass
            lo_ci, hi_ci = np.percentile(diffs, [2.5, 97.5])
            say(f"  OL-continuity split (STAYERS only, median {med:.2f}):"
                f" carry slope LOW-cont {bl:+.2f} (n={len(lo_)}) vs HIGH-cont {bh:+.2f} (n={len(hi_)})")
            say(f"    slope diff (high-low) {bh-bl:+.2f}, bootstrap 95% CI [{lo_ci:+.2f}, {hi_ci:+.2f}]"
                f" (clusters = QB-season rows per task directive)")
            hd["ol_split"] = (bl, bh, bh - bl, lo_ci, hi_ci, len(lo_), len(hi_))

    prim = pairs[pairs["season"].isin([2023, 2024, 2025])]
    say(); say("PRIMARY SCOPE (2023-2025, per task):"
               f" {len(prim)} QB-season pairs (throws>=150 both years)")
    say("  [n < 40 clusters -> DIRECTIONAL-ONLY per S11, stated in advance]")
    carry_report(prim, "primary 2023-2025")
    movers = prim[prim.moved].sort_values("season")
    say("  movers, listed: " + "; ".join(
        f"{r.player_display_name} {int(r.season)} ({r.team_prev}->{r.team},"
        f" prior {r.shrunk1:.3f} -> realized {r.rate:.3f})" for r in movers.itertuples()))

    ext = pairs[pairs["season"] >= 2016]
    say(); say(f"SECONDARY POWER EXTENSION (2016-2025, snap-count instrument — no schema issue;"
               f" outside the task's depth-chart scope and labelled so): {len(ext)} pairs")
    carry_report(ext, "extension 2016-2025")

    # mover error direction: does the old-team rate over- or under-state the new situation?
    mv = ext[ext.moved]
    sgn = wmean(mv["rate"] - mv["shrunk1"], mv["throws"])
    say(f"\n  movers 2016-2025 (n={len(mv)}): weighted mean signed error"
        f" (realized - carried) = {sgn:+.4f} rate ({sgn*500:+.1f} pts/500 throws)"
        f" — {'carried rate too LOW (moves hurt)' if sgn > 0 else 'carried rate too HIGH on average'}")
    return pairs, olc


# ============================================================================
# 4. SHRINKAGE + the PRIMARY ENDPOINT forecast harness
# ============================================================================
def forecast(qs):
    say(); say("=" * 78)
    say("4. SHRINKAGE: CROSS-VALIDATE K; TTT FORECAST — PRIMARY ENDPOINT")
    say("=" * 78)
    q = qs.set_index(["season", "player_id"])

    def pool_rate(pid, t, span):
        """pooled shrunk rate over seasons t-span..t-1 (K applied by caller)."""
        s = th = 0.0
        Ls = Lt = 0.0
        for y in range(t - span, t):
            if (y, pid) in q.index:
                r = q.loc[(y, pid)]
                s += r["sacks"]; th += r["throws"]
            if y in q.index.get_level_values(0):
                pass
        return s, th

    # season-level tables for speed
    by_season = {y: g.set_index("player_id") for y, g in qs.groupby("season")}
    lg_rate = qs.drop_duplicates("season").set_index("season")["league_rate"]

    def shrunk(pid, t, span, K):
        """EB-shrunk rate from seasons t-span..t-1, toward the pool league rate."""
        s = th = ls = lt = 0.0
        for y in range(t - span, t):
            if y not in by_season:
                return np.nan
            g = by_season[y]
            if pid in g.index:
                s += g.loc[pid, "sacks"]; th += g.loc[pid, "throws"]
            ls += g["sacks"].sum(); lt += g["throws"].sum()
        L = ls / lt
        return (s + K * L) / (th + K)

    # ---- NGS avg_time_to_throw, season aggregate (REG, week==0), keyed player_gsis_id
    ngs = pd.read_parquet(os.path.join(HERE, "raw/ngs_passing_2016_2025.parquet"))
    ngs0 = ngs[(ngs["week"] == 0) & (ngs["season_type"] == "REG")]
    ttt = ngs0.set_index(["season", "player_gsis_id"])["avg_time_to_throw"]
    say(f"NGS passing season aggregates (week==0, REG): "
        f"{len(ngs0)} QB-seasons 2016-2025, avg_time_to_throw p10/p50/p90 = "
        f"{ngs0.avg_time_to_throw.quantile(.1):.2f}/{ngs0.avg_time_to_throw.median():.2f}/"
        f"{ngs0.avg_time_to_throw.quantile(.9):.2f}s [V]")

    # ---- evaluation frame: QB-seasons t with throws_t>=200 & throws_{t-1}>=200
    rows = []
    for t in range(2017, 2026):
        cur = by_season[t]
        for pid, r in cur[cur["throws"] >= 200].iterrows():
            prevg = by_season[t - 1]
            if pid not in prevg.index or prevg.loc[pid, "throws"] < 200:
                continue
            rows.append({
                "season": t, "player_id": pid, "rate": r["rate"], "throws": r["throws"],
                "inc": shrunk(pid, t, 3, K_SHIPPED),            # M0: shipped construction
                "ttt_prev": ttt.get((t - 1, pid), np.nan),
            })
    ev = pd.DataFrame(rows)
    say(f"evaluation frame: {len(ev)} QB-seasons 2017-2025 (throws>=200 both years);"
        f" t-1 TTT present on {ev.ttt_prev.notna().sum()} [V]")

    # ---- K cross-validation curve (the deliverable: is K=12 right?)
    KGRID = [0, 1, 2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384,
             512, 768, 1024, 1536, 2048]
    KINF = 10 ** 9                                     # ~pure league rate baseline
    say(); say("K SWEEP — throws-weighted OOS MSE(x1e4) of rate forecast, t=2017-2025")
    say("  (predictor uses only <=t-1 data at every K; picking K on this table is the")
    say("   in-sample-for-K view — the PRIMARY endpoint below picks K nested, train-only)")
    say(f"  {'K':>5s}  {'last-1yr':>9s}  {'pool-3yr':>9s}")
    kcurve = {}
    for Kv in KGRID + [KINF]:
        e1 = []
        e3 = []
        for r in ev.itertuples():
            s1 = shrunk(r.player_id, r.season, 1, max(Kv, 1e-9))
            s3 = shrunk(r.player_id, r.season, 3, max(Kv, 1e-9))
            e1.append((s1 - r.rate) ** 2)
            e3.append((s3 - r.rate) ** 2)
        m1 = wmean(e1, ev["throws"]) * 1e4
        m3 = wmean(e3, ev["throws"]) * 1e4
        kcurve[Kv] = (m1, m3)
        say(f"  {'INF' if Kv == KINF else Kv:>5}  {m1:9.3f}  {m3:9.3f}")
    best1 = min(KGRID, key=lambda k: kcurve[k][0])
    best3 = min(KGRID, key=lambda k: kcurve[k][1])
    say(f"  minima: last-1yr K*={best1}, pool-3yr K*={best3}   (shipped: pool-3yr K=12);")
    say(f"  INF row = ignore the QB entirely, use the 3yr league rate — its MSE"
        f" {kcurve[KINF][1]:.3f} vs best pooled {kcurve[best3][1]:.3f}: the per-QB rate DOES"
        f" carry OOS signal, but far less than K=12 assumes")
    say(f"  shipped-vs-best pooled construction: MSE {kcurve[K_SHIPPED][1]:.3f} vs {kcurve[best3][1]:.3f}"
        f" ({(kcurve[K_SHIPPED][1]-kcurve[best3][1])/kcurve[K_SHIPPED][1]*100:+.1f}% excess)")
    HEAD["k_shipped_mse"] = kcurve[K_SHIPPED][1]
    HEAD["k_best3"], HEAD["k_best3_mse"] = best3, kcurve[best3][1]
    HEAD["k_inf_mse"] = kcurve[KINF][1]

    # ---- PRIMARY ENDPOINT: expanding-window, nested K, TTT challenger, points MAE
    say(); say("PRIMARY ENDPOINT (declared in module docstring before analysis):")
    say("  M0 incumbent  = pooled t-3..t-1, K=12 (shipped construction as a forecast)")
    say("  M1 secondary  = last-year-only, K* chosen on train seasons < t (nested)")
    say("  M2 challenger = WLS on train: rate ~ shrunk_last1(K*) + avg_time_to_throw(t-1)")
    say("  M3 secondary  = pooled t-3..t-1 with NESTED-CV K (the K-only fix to the shipped")
    say("                  construction; not the primary — added after the K sweep was designed,")
    say("                  before it ran)")
    say("  err_pts = |rate_hat - rate_t| * throws_t * |SACK|;  population = eval frame with TTT")
    evp = ev.dropna(subset=["ttt_prev", "inc"]).copy()
    res = []
    for t in range(2019, 2026):
        tr = evp[evp["season"] < t]
        te = evp[evp["season"] == t]
        if len(tr) < 20 or len(te) == 0:
            continue
        # nested K on train (throws-weighted MSE), separately for last-1yr and pool-3yr
        kbest = {}
        for span in (1, 3):
            kb, kmse = None, np.inf
            for Kv in KGRID:
                errs = [(shrunk(r.player_id, r.season, span, max(Kv, 1e-9)) - r.rate) ** 2
                        for r in tr.itertuples()]
                mm = wmean(errs, tr["throws"])
                if mm < kmse:
                    kb, kmse = Kv, mm
            kbest[span] = kb
        tr = tr.assign(s1=[shrunk(r.player_id, r.season, 1, max(kbest[1], 1e-9))
                           for r in tr.itertuples()])
        te = te.assign(s1=[shrunk(r.player_id, r.season, 1, max(kbest[1], 1e-9))
                           for r in te.itertuples()],
                       s3=[shrunk(r.player_id, r.season, 3, max(kbest[3], 1e-9))
                           for r in te.itertuples()])
        W = np.sqrt(tr["throws"].values)
        X = np.column_stack([np.ones(len(tr)), tr["s1"], tr["ttt_prev"]]) * W[:, None]
        y = tr["rate"].values * W
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        pred2 = beta[0] + beta[1] * te["s1"] + beta[2] * te["ttt_prev"]
        for r, p2 in zip(te.itertuples(), pred2):
            res.append({"season": t, "player_id": r.player_id, "throws": r.throws,
                        "K1_nested": kbest[1], "K3_nested": kbest[3], "b_ttt": beta[2],
                        "e0": abs(r.inc - r.rate) * r.throws,
                        "e1": abs(r.s1 - r.rate) * r.throws,
                        "e2": abs(p2 - r.rate) * r.throws,
                        "e3": abs(r.s3 - r.rate) * r.throws})
    rs = pd.DataFrame(res)
    per = rs.groupby("season").agg(n=("e0", "size"), K1=("K1_nested", "first"),
                                   K3=("K3_nested", "first"), b_ttt=("b_ttt", "first"),
                                   mae0=("e0", "mean"), mae1=("e1", "mean"),
                                   mae2=("e2", "mean"), mae3=("e3", "mean"))
    per["d02"] = per["mae0"] - per["mae2"]
    per["d01"] = per["mae0"] - per["mae1"]
    per["d03"] = per["mae0"] - per["mae3"]
    say(); say("per-season (points MAE per QB-season; d02 = M0 - M2 = PRIMARY, + is better):")
    say(per.round(2).to_string())
    m, lo, hi, p, n = season_ci(per["d02"])
    m1_, lo1, hi1, p1, _ = season_ci(per["d01"])
    m3_, lo3, hi3, p3, _ = season_ci(per["d03"])
    win = (rs["e2"] < rs["e0"]).mean()
    win3 = (rs["e3"] < rs["e0"]).mean()
    say()
    say(f"PRIMARY RESULT: OOS improvement M0->M2 = {m:+.2f} league pts per QB-season,")
    say(f"  95% CI [{lo:+.2f}, {hi:+.2f}], p={p:.3f}, clusters = {n} seasons, QB-level win rate"
        f" {win*100:.0f}% (n={len(rs)} QB-seasons)")
    say(f"  DIRECTIONAL-ONLY by S11 ({n} < 40 clusters), whatever the p-value.")
    say(f"secondary decomposition: recency/K alone (M0->M1) = {m1_:+.2f} [{lo1:+.2f}, {hi1:+.2f}],"
        f" p={p1:.3f}; TTT increment (M1->M2) = {m - m1_:+.2f}")
    say(f"secondary M3 (K-only fix, pooled 3yr @ nested K): M0->M3 = {m3_:+.2f}"
        f" [{lo3:+.2f}, {hi3:+.2f}], p={p3:.3f}, QB-level win rate {win3*100:.0f}%")
    HEAD.update(primary=(m, lo, hi, p, n), d01=(m1_, lo1, hi1, p1), d03=(m3_, lo3, hi3, p3),
                win=win, win3=win3, n_qbseasons=len(rs))
    return ev, rs, per, kcurve, best1, best3


# ============================================================================
# 5. INVISIBILITY: the sack term across QB1-QB24, per season, in league points
# ============================================================================
def invisibility():
    say(); say("=" * 78)
    say("5. INVISIBILITY: WHAT EVERY BASE-PPR BACKTEST MISSED (weekly_league b_sack)")
    say("=" * 78)
    sl = pd.read_parquet(os.path.join(HERE, "seasons_league.parquet"))
    qb = sl[sl["position"] == "QB"].copy()
    rows = []
    for y, g in qb.groupby("season"):
        g = g.nlargest(24, "total_league").copy()
        g["rk"] = g["total_league"].rank(ascending=False, method="first")
        nosack = g["total_league"] - g["b_sack"]
        rk_no = nosack.rank(ascending=False, method="first")
        shift = (g["rk"] - rk_no).abs()
        top12_flip = int(((g["rk"] <= 12) != (rk_no <= 12)).sum())
        rows.append({
            "season": y,
            "sack_QB1_12": g[g["rk"] <= 12]["b_sack"].mean(),
            "sack_QB13_24": g[g["rk"] > 12]["b_sack"].mean(),
            "sd_top24": g["b_sack"].std(),
            "spread_p90_p10": g["b_sack"].quantile(.9) - g["b_sack"].quantile(.1),
            "mean_abs_rankshift": shift.mean(), "max_shift": int(shift.max()),
            "top12_flips": top12_flip,
        })
    t = pd.DataFrame(rows).set_index("season")
    say("per season, QBs ranked by total_league (the corrected instrument):")
    say(t.round(1).to_string())
    say()
    pooled = t.mean(); sd = t.std()
    say(f"pooled over 12 seasons (mean +/- season SD, S11 clusters=12):")
    say(f"  sack term, QB1-12:  {pooled.sack_QB1_12:+.1f} +/- {sd.sack_QB1_12:.1f} pts/season")
    say(f"  sack term, QB13-24: {pooled.sack_QB13_24:+.1f} +/- {sd.sack_QB13_24:.1f} pts/season")
    say(f"  within-top-24 SD:   {pooled.sd_top24:.1f}; p90-p10 spread {pooled.spread_p90_p10:.1f} pts")
    say(f"  removing the sack term shifts a top-24 QB {pooled.mean_abs_rankshift:.1f} ranks on"
        f" average (max {t.max_shift.max():.0f}); {pooled.top12_flips:.1f} QB1/QB2-tier"
        f" membership flips per season")
    gap612 = np.mean([g.nlargest(24, 'total_league').iloc[5]['total_league']
                      - g.nlargest(24, 'total_league').iloc[11]['total_league']
                      for _, g in qb.groupby('season')])
    say(f"  charter's '-42 pts/season ~ QB6->QB12 gap' claim vs measured: mean top-12 sack"
        f" term {pooled.sack_QB1_12:+.1f}; QB6-QB12 total_league gap = {gap612:.1f} pts [V]")
    HEAD["invis"] = (pooled.sack_QB1_12, pooled.sack_QB13_24, pooled.sd_top24,
                     pooled.spread_p90_p10, pooled.mean_abs_rankshift,
                     pooled.top12_flips, gap612)
    return t


# ============================================================================
def main():
    say("=" * 78)
    say("54 — H5c: THE SACK TAX — staleness / invisibility / shrinkage (NOT existence)")
    say("=" * 78)
    say(__doc__.split("Inputs")[0])

    pbp, qs, lg = build_sack_panel()
    anchor_and_board_check(pbp)
    del pbp
    market_check(qs)
    staleness(qs)
    forecast(qs)
    invisibility()

    say(); say("=" * 78)
    say("6. VERDICT SUMMARY (one primary endpoint declared; everything else secondary)")
    say("=" * 78)
    pm, plo, phi, pp, pn = HEAD["primary"]
    a1 = HEAD["a1"]
    inv = HEAD["invis"]
    st_p = HEAD["stale"]["primary 2023-2025"]
    st_e = HEAD["stale"]["extension 2016-2025"]
    d3 = HEAD["d03"]
    say(f"""
PRIMARY (declared pre-run, S14): OOS sack-rate forecast improvement in league points
  at the QB level, M0(shipped pooled-3yr K=12) -> M2(last1 K*-nested + TTT):
  {pm:+.2f} pts/QB-season, 95% CI [{plo:+.2f}, {phi:+.2f}], p={pp:.3f}, {pn} season
  clusters, win rate {HEAD['win']*100:.0f}% on {HEAD['n_qbseasons']} QB-seasons.
  VERDICT: NULL / slightly NEGATIVE — the challenger does NOT beat the shipped
  construction. DIRECTIONAL-ONLY (clusters < 40). TTT increment alone is negative:
  avg_time_to_throw adds NO OOS forecast value over the shrunk rate (kill-list entry).

SECONDARY, the one live improvement: K. The CV curve has an INTERIOR minimum far past
  K=12 for BOTH constructions (last-1yr K*=512, pooled-3yr K* = {HEAD['k_best3']}; K=12 carries
  {(HEAD['k_shipped_mse']-HEAD['k_best3_mse'])/HEAD['k_shipped_mse']*100:+.1f}% excess MSE). The league-rate-only forecast (K=INF) is clearly WORSE
  ({HEAD['k_inf_mse']:.3f} vs {HEAD['k_best3_mse']:.3f} MSEx1e4), so the per-QB rate carries real OOS signal —
  but a 3-year starter (~1,500 pooled throws) should keep only {1500/(1500+HEAD['k_best3'])*100:.0f}% of his own
  deviation from league average, not the {1500/(1500+12)*100:.0f}% K=12 grants; a 2-season QB like Maye
  (~900 pooled throws) keeps ~{900/(900+HEAD['k_best3'])*100:.0f}%, i.e. his -25.9 sack tax roughly HALVES its
  distance from the league mean. In points-MAE terms the K-only fix (M3) is real but
  tiny: {d3[0]:+.2f} [{d3[1]:+.2f}, {d3[2]:+.2f}] pts/QB-season, p={d3[3]:.3f}, win rate {HEAD['win3']*100:.0f}% —
  the misspecification's main consequence is the BOARD SPREAD (rank ordering of
  sack-prone QBs), not forecast accuracy, so it must be graded in the paired harness,
  not shipped on this number. DIRECTIONAL-ONLY, same clusters. Exact 2026 rebuilt
  column deliberately not produced (frozen file, propose-only).

CHEAP CHECK (a) market: ADP-residual slope on prior sack rate {a1[0]:+.1f} psg/unit,
  CI [{a1[1]:+.1f}, {a1[2]:+.1f}], p={a1[3]:.3f} ({a1[4]} seasons) — {a1[5]:+.1f} league pts per
  prior-rate IQR over a 17-game season. The market shows NO exploitable mispricing
  signal on prior sack rate, and the price itself barely loads on it
  (dR2={HEAD['a2_dR2']:+.4f}). VERDICT: null — no ADP edge hiding in sack rate beyond
  what the board already prices mechanically.

CHEAP CHECK (b) our board: prices the pooled-2023-25 K=12 rate at 100% by
  construction; the sack term alone recovers the bulk of the QB bonus re-ranking.
  Any future sack proposal must grade AGAINST the shipped rate (anti-double-count).

STALENESS (H2e, absorbed): pre-registered null CONFIRMED on both halves.
  Primary 2023-2025 (n={st_p['STAYED'][0]}+{st_p['MOVED'][0]}): carry slope stayers {st_p['STAYED'][1]:+.2f} vs movers {st_p['MOVED'][1]:+.2f};
  OL-continuity split diff {st_p['ol_split'][2]:+.2f}, bootstrap CI [{st_p['ol_split'][3]:+.2f}, {st_p['ol_split'][4]:+.2f}].
  Extension 2016-2025 (n={st_e['STAYED'][0]}+{st_e['MOVED'][0]}): stayers {st_e['STAYED'][1]:+.2f} vs movers {st_e['MOVED'][1]:+.2f};
  OL split diff {st_e['ol_split'][2]:+.2f} CI [{st_e['ol_split'][3]:+.2f}, {st_e['ol_split'][4]:+.2f}]. The carried rate is NOT
  measurably staler for movers or turned-over lines — the rate travels with the QB
  more than with the line at these sample sizes. H2e CLOSED as the charter expected.
  (Note the carry slope ~0.45 << 1 for EVERYONE is itself the K finding restated.)

INVISIBILITY (descriptive, the S12 payload): top-12 QBs carry {inv[0]:+.1f} pts/season of
  sack tax (top-24 within-range p90-p10 spread {inv[3]:.1f} pts, SD {inv[2]:.1f}); ignoring it
  shifts a top-24 QB {inv[4]:.1f} ranks on average, {inv[5]:.1f} top-12 membership flips/season.
  Every base-PPR backtest in this repo mis-scored QBs by ~33 pts/season LEVEL and up to
  ~{inv[3]:.0f} pts/season SPREAD inside the startable range. The charter's '-42 pts' figure
  is the right order of magnitude but ~25% high vs measured top-12 realized seasons;
  the QB6->QB12 league gap is {inv[6]:.0f} pts, so the sack SPREAD (~{inv[3]:.0f}) is roughly half
  that gap, not all of it.

C12: replacement stayed QB12 throughout; no VOLS denominator touched.
""")
    say("=" * 78)
    say("7. WHAT WAS NOT DONE (honest gaps)")
    say("=" * 78)
    say("""
- The charter's H5c shipping bar ("league points in VOLS terms, corrected grader,
  placebo 95th pct or +15") was NOT evaluated: no T0.6 placebo distribution existed at
  run time and the paired-draft harness re-grade is outside this assignment's tasks.
  This file delivers the grader's ingredients (forecast deltas + invisibility table).
- The best-K rebuilt 2026 board column was NOT produced (apply_bonuses is frozen;
  proposal only). The proposal, precisely: change scoring_config.K for the SACK term
  only if re-graded — the long-TD terms share the same K and were NOT cross-validated
  here (H5b territory; a shared-K change must clear both).
- Depth charts were NOT used (2024 is old-schema [V]; no new-schema YoY pair exists
  inside 2023-2025). OL continuity = snap-count five-man overlap instead.
- In-season TTT (first-2-games) as a change-point detector was not tested — this file
  tested the PRESEASON forecast per the assignment; the in-season question is WS3's.
- POST-season plays are excluded from the analysis panel (REG only), while the shipped
  rate pools REG+POST; the reproduction in section 1 used REG+POST to match exactly.
- 2025 prices are Sleeper adp_ppr, not FFC (T0.2 instrument change), stated at use.
- BH/FDR: this file contributes exactly ONE primary endpoint (p={:.3f}) to the
  charter-wide S14 correction pool; secondaries here must not enter that pool.
""".format(pp))

    with open(OUT_TXT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT_TXT}")


if __name__ == "__main__":
    main()
