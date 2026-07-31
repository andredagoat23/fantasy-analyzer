"""55 — H2g: 2026/2025 ESPN depth charts as an INDEPENDENT role signal.

Charter: icm/work/research-blueprint-prompt.md — H2g (WS2, "RUN THIS FIRST"), §2.6 (team_role is a
projection artifact), §3.3 item 2 (the load_depth_charts schema break), T0.7 (role census, executed
as results_60_censuses.txt R1-R19: role lives in SIX sites, not five).

SCOPE (charter-corrected): 2026 (current board) + 2025 (history) ONLY. The 2019/2023 depth-chart
schema (`depth_team`, NFL gameday charts) shares ZERO column names with the 2025/2026 schema
(`pos_rank`, ESPN daily snapshots) and is NEVER pooled here. n = ONE season of history.

SEMANTICS ESTABLISHED BEFORE DESIGN [V, this run]: in the 2025/2026 schema `pos_rank` is a GLOBAL
within-(team, pos_abb) ordering across slots (DET WR latest 2026 snapshot: St. Brown 1, J. Williams
2, TeSlaa 3, Dortch 4 — pos_slot 1/2/8 are the X/Z/slot alignments, pos_rank runs 1..13 across
them). So pos_rank maps 1:1 onto team_role's number with no tie-break invention.

DESIGN (stage-gated, per the charter's own sequencing):
  A. CHEAP CHECK (2026): agreement rate between the latest 2026 snapshot's pos_rank ordering and
     value_board's projection-derived team_role ordering, in the draftable range (board DRAFTABLE =
     adp_rank <= 180), on the common set of players present in both, re-ranked within (team,
     position) on each side.  GATE: if >= 95% agreement, the swap is cosmetic — report and STOP.
  B. 2025 instruments: week-1-adjacent snapshot (last dt <= 2025-09-05T00:00Z) as the depth-chart
     signal; projection-derived team_role reconstructed from the 44_ blend cache (prep() logic of
     44_survival_curve_backtest.py: per-source scale to actual mean, then 0.5*espn + 0.5*sleeper),
     ordered within (team, position) on the same common set.  Lead-time sensitivity: the
     2025-08-07 snapshot (the draft-day-equivalent lead time; league drafts 2026-08-07).
  C. Outcomes: LEAGUE-scored (S12 primary) points-above-price, price = the T0.2 repair instrument
     (** Sleeper adp_ppr, NOT ESPN ADP and NOT FFC ** — instrument change stated per T0.2's
     downstream contract), expectation = 02_expectation's exact curve code re-fit on the
     league-scored panel 2014-2024 (2025 excluded from the fit — no leakage), applied to the
     repair file's exp_pos_rank. Base-PPR secondary uses the repair file's own exp_pts.
  D. Head-to-head + the priority sub-population (switched-team players; the ascending half of the
     override population is NOT reconstructed for 2025 — stated in results).
  E. Verdict (DIRECTIONAL-ONLY by construction: 1 season cluster, S11) + the 2026 preregistration:
     the full list of 2026 disagreement pairs frozen into the results file.

S14 PRIMARY ENDPOINT — DECLARED HERE, BEFORE ANY RESULT WAS COMPUTED. Exactly ONE:
  On 2025, RB/WR/TE rooms only (the positions where role moves a rank — census R12/R13: the
  advisor's _role_bonus_series is RB/WR/TE-only), among rooms where the week-1 depth chart's No.1
  differs from the blend-projection's No.1 and BOTH players are priced (repair adp <= 300, defined
  expectation): the mean paired difference in LEAGUE-scored points-above-price, depth-chart-favored
  minus projection-favored. Positive = the depth chart's contradiction of the projection carried
  information. No OR-clause. Verdict capped at DIRECTIONAL-ONLY regardless of the number
  (effective n = 1 season cluster; the 2026 season is the pre-registered real test).
  Everything else below (base currency, realized-role top-1, rank agreement, sub-populations,
  Aug-07 lead time, QB rooms) is SECONDARY and labelled so.

Hypothesis count for S14/FDR: this script tests ONE hypothesis (H2g) with one primary endpoint.

Prior scripts read before writing this one (charter mandate): 44_survival_curve_backtest.py,
02_expectation.py, 48_source_verification.py.  New files only; frozen pipeline untouched.

Run:  .venv/bin/python icm/work/mc_research/55_h2g_depthchart.py
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from utils import normalize_name  # noqa: E402

os.environ.setdefault("NFLREADPY_CACHE_DIR", os.path.join(HERE, ".nflcache"))
os.environ.setdefault("NFLREADPY_CACHE_MODE", "filesystem")

OUT = os.path.join(HERE, "results_55_h2g.txt")
DC26_CACHE = os.path.join(HERE, "dc2026_latest_55.parquet")
DC25_CACHE = os.path.join(HERE, "dc2025_slim_55.parquet")

SKILL = ["QB", "RB", "WR", "TE"]
REC = ["RB", "WR", "TE"]          # the positions the role machinery moves (census R12/R13)
DRAFTABLE_ADP = 180               # value_board.py DRAFTABLE
PRICED_MAX = 300                  # T0.2 extension band (166 rows <=200, 250 <=300 in 2025)
WK1_CUT = "2025-09-05T00:00:00Z"  # 2025 REG week 1 kicked off 2025-09-04 20:20 ET = 09-05 00:20Z
AUG7_CUT = "2025-08-08T00:00:00Z"

lines = []


def say(s=""):
    print(s)
    lines.append(str(s))


def flush():
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------------------------
# depth-chart loading (cached slim parquets so a rerun never re-pulls)
# ---------------------------------------------------------------------------------------------
def load_dc2026():
    if os.path.exists(DC26_CACHE):
        return pd.read_parquet(DC26_CACHE)
    import nflreadpy as nfl
    dc = nfl.load_depth_charts([2026]).to_pandas()
    snap = dc[(dc.dt == dc.dt.max()) & dc.pos_abb.isin(SKILL)].copy()
    snap.to_parquet(DC26_CACHE + ".tmp", index=False)
    os.replace(DC26_CACHE + ".tmp", DC26_CACHE)
    return snap


def load_dc2025():
    if os.path.exists(DC25_CACHE):
        return pd.read_parquet(DC25_CACHE)
    import nflreadpy as nfl
    dc = nfl.load_depth_charts([2025]).to_pandas()
    dts = sorted(dc.dt.unique())
    wk1 = [d for d in dts if d <= WK1_CUT][-1]
    aug7 = [d for d in dts if d <= AUG7_CUT][-1]
    slim = dc[dc.dt.isin([wk1, aug7]) & dc.pos_abb.isin(SKILL)].copy()
    slim.to_parquet(DC25_CACHE + ".tmp", index=False)
    os.replace(DC25_CACHE + ".tmp", DC25_CACHE)
    return slim


def common_set_orders(df, proj_col, dc_col="pos_rank"):
    """Within (team, position): rank both signals on the common set. Returns df with
    ord_proj / ord_dc (1 = room leader on that signal)."""
    df = df.copy()
    df["ord_proj"] = df.groupby(["team", "position"])[proj_col].rank(
        ascending=True, method="first").astype(int)     # proj_col pre-negated => ascending
    df["ord_dc"] = df.groupby(["team", "position"])[dc_col].rank(
        ascending=True, method="first").astype(int)
    return df


def binom_p(k, n):
    """Two-sided exact binomial sign-test p (descriptive only — S11: 1 season cluster)."""
    if n == 0:
        return float("nan")
    p_hi = sum(math.comb(n, i) for i in range(k, n + 1)) / 2**n
    p_lo = sum(math.comb(n, i) for i in range(0, k + 1)) / 2**n
    return min(1.0, 2 * min(p_hi, p_lo))


say("=" * 100)
say("55 — H2g: DEPTH CHARTS AS AN INDEPENDENT ROLE SIGNAL   (run date 2026-07-31)")
say("=" * 100)
say("All numbers [V] = computed this run unless marked [R] = read from a prior results file.")
say("Schema rule enforced: 2019/2023 depth-chart era (depth_team) NEVER loaded, NEVER pooled.")
say("PRIMARY ENDPOINT (S14, declared in the module docstring BEFORE running): 2025 RB/WR/TE")
say("disagreement rooms, both priced, league-scored points-above-price, depth-favored minus")
say("projection-favored, week-1 snapshot. ONE endpoint; everything else is SECONDARY.")
say("")

# =============================================================================================
# SECTION A — THE 2026 CHEAP CHECK
# =============================================================================================
say("=" * 100)
say("SECTION A — CHEAP CHECK: 2026 board team_role vs latest 2026 depth-chart pos_rank [V]")
say("=" * 100)

dc26 = load_dc2026()
say(f"2026 snapshot: dt={dc26.dt.iloc[0]}  skill rows={len(dc26)}  teams={dc26.team.nunique()}")

board = pd.read_csv(os.path.join(ROOT, "app_data.csv"),
                    dtype={"player_id": str, "gsis_id": str})
board = board[board["position"].isin(SKILL)].copy()
board["role_num"] = board["team_role"].astype(str).str.extract(r"(\d+)").astype(float)
board["nn"] = board["full_name"].map(normalize_name)
say(f"board (app_data.csv): {len(board)} skill players; gsis_id present on "
    f"{board.gsis_id.notna().sum()}")

# --- match board -> snapshot: gsis, then espn, then name+team+pos, then unique name+pos
dc = dc26.copy()
dc["nn"] = dc.player_name.map(normalize_name)
dc["espn_id_s"] = dc.espn_id.astype(str)
board["espn_id_s"] = board["espn_id"].apply(
    lambda v: str(int(v)) if pd.notna(v) and str(v) not in ("", "nan") else np.nan)

# explicit, readable matching (three passes, first hit wins).
# NOTE: app_data.csv carries its own `pos_rank` column (the board's VOLS position rank) — the
# depth chart's pos_rank is renamed dc_pos_rank BEFORE the merge so the two can never collide.
dcx = dc.rename(columns={"pos_abb": "position", "team": "dc_team",
                         "pos_rank": "dc_pos_rank"})[
    ["gsis_id", "espn_id_s", "nn", "dc_team", "position", "dc_pos_rank"]]

matched = []
used_dc = set()
for method, keys in [("gsis", ["gsis_id", "position"]),
                     ("espn", ["espn_id_s", "position"]),
                     ("name+pos", ["nn", "position"])]:
    left = board[~board.index.isin([i for i, _ in matched])].reset_index()
    right = dcx[~dcx.index.isin(used_dc)].reset_index()
    l = left.dropna(subset=[keys[0]])
    r = right.dropna(subset=[keys[0]])
    r = r[~r.duplicated(subset=keys, keep=False) | (keys[0] != "nn")]  # name join: unique only
    j = l.merge(r, on=keys, suffixes=("", "_dc"))
    j = j[~j.duplicated(subset=["index"], keep="first")]
    for _, row in j.iterrows():
        matched.append((row["index"], (row["index_dc"], row["dc_team"],
                                       row["dc_pos_rank"], method)))
        used_dc.add(row["index_dc"])
mm = pd.DataFrame([(i, t, pr, meth) for i, (di, t, pr, meth) in matched],
                  columns=["bidx", "dc_team", "dc_pos_rank", "match_method"]).set_index("bidx")
A = board.join(mm, how="inner")
say(f"matched board->snapshot: {len(A)} of {len(board)} "
    f"({dict(A.match_method.value_counts())})")
unmatched = board[~board.index.isin(A.index)]
if len(unmatched):
    say("  unmatched board players (not on any current chart): "
        + ", ".join(f"{r.full_name} ({r.position} {r.team}, adp {r.adp_rank:.0f})"
                    for _, r in unmatched.iterrows()))
team_mismatch = (A["team"].astype(str) != A["dc_team"].astype(str)).sum()
say(f"board-team vs snapshot-team mismatches among matched: {team_mismatch} "
    "(snapshot team used for room grouping — it is the fresher fact)")

# --- common-set orderings within (snapshot team, position)
A = A.rename(columns={"dc_team": "room_team"})
A["team"] = A["room_team"]
A["neg_role"] = A["role_num"]                     # smaller team_role number = better
A = common_set_orders(A.rename(columns={"neg_role": "proj_key"}).assign(
    proj_key=lambda d: d["role_num"]), "proj_key", "dc_pos_rank")
A["agree"] = A.ord_proj == A.ord_dc
A["exact"] = A.role_num == A.dc_pos_rank          # secondary: raw number match (no re-rank)

say("")
say("AGREEMENT (common-set re-rank within snapshot-team+position; player counted once):")
say("NOTE: the board's adp_rank carries ESPN's 170.0 UNDRAFTED SENTINEL, so the <=180 cut barely")
say("filters (498 of 499 matched pass it) — read the top-50/top-100 rows as the draftable range.")
for label, mask in [
        (f"adp_rank <= {DRAFTABLE_ADP} (sentinel-diluted)", A.adp_rank <= DRAFTABLE_ADP),
        ("top-100 ADP", A.adp_rank <= 100),
        ("top-50 ADP", A.adp_rank <= 50),
        ("all matched", pd.Series(True, index=A.index))]:
    sub = A[mask]
    say(f"  {label:34s} n={len(sub):4d}  ordering-agreement={sub.agree.mean()*100:5.1f}%   "
        f"raw pos_rank==team_role_num={sub.exact.mean()*100:5.1f}%")
say("  by position (adp_rank <= 180, sentinel-diluted):")
for pos, g in A[A.adp_rank <= DRAFTABLE_ADP].groupby("position"):
    say(f"    {pos}: n={len(g):3d}  ordering-agreement={g.agree.mean()*100:5.1f}%")

# room-leader agreement among rooms with >=2 matched players
rooms = A.groupby(["team", "position"]).filter(lambda g: len(g) >= 2)
r1 = rooms[rooms.ord_proj == 1][["team", "position", "full_name", "adp_rank"]].rename(
    columns={"full_name": "proj_no1", "adp_rank": "proj_no1_adp"})
d1 = rooms[rooms.ord_dc == 1][["team", "position", "full_name", "adp_rank"]].rename(
    columns={"full_name": "dc_no1", "adp_rank": "dc_no1_adp"})
lead = r1.merge(d1, on=["team", "position"])
lead["same"] = lead.proj_no1 == lead.dc_no1
say(f"  room-leader agreement (rooms with >=2 matched): {lead.same.mean()*100:.1f}% "
    f"({lead.same.sum()}/{len(lead)} rooms)")

# --- the override population (census R5): reproduce value_board.py:89-112 EXACTLY from the
#     unrounded upstream file value_board.py itself reads.
pw = pd.read_csv(os.path.join(ROOT, "players_with_outcomes.csv"), dtype={"player_id": str})
vb = pw[pw["vols"].notna()].copy()
vb = vb[vb["team"].notna() & ~vb["team"].astype(str).str.upper().isin(["FA", "NAN", ""])].copy()
_g = vb.groupby(["team", "position"])["total_points"]
_top1 = _g.transform("max")
_top2 = _g.transform(lambda s: s.sort_values(ascending=False).iloc[1] if len(s) > 1 else s.iloc[0])
vb["role_lead_x"] = (vb["total_points"] - _top2.where(vb["total_points"] >= _top1, _top1)).round(1)
_rec = vb["position"].isin(REC)
xppg_pct = vb["xppg"].where(_rec).groupby(vb["position"]).rank(pct=True)
ts_best = vb[["target_share_2024", "target_share_2025"]].max(axis=1).where(_rec)
ts_pct = ts_best.groupby(vb["position"]).rank(pct=True)
role_pct = xppg_pct.fillna(ts_pct).fillna(0.5)
vols_pct = vb["vols"].where(_rec).groupby(vb["position"]).rank(pct=True)
switched = vb["switched_team"].fillna(False).astype(bool) & vols_pct.notna()
_rook = vb["is_rookie"].fillna(False).astype(str).str.lower().isin(["true", "1"])
ascend = (_rec & ~switched & ~_rook & (vb["vols"] > 0)
          & (vb["role_lead_x"] >= 15) & (vols_pct >= role_pct + 0.25))
vb["override"] = switched | ascend
say("")
say(f"OVERRIDE POPULATION reproduced from players_with_outcomes.csv per value_board.py:89-112:")
say(f"  switched-team: {switched.sum()}   ascending leads: {ascend.sum()}   "
    f"union: {vb.override.sum()} of {len(vb)} board players")
sw_all = vb["switched_team"].fillna(False).astype(bool).sum()
say(f"  reconciliation with the charter's '85 of 536': switched_team=True board-wide = {sw_all}")
say(f"  (all positions); the override code only touches RB/WR/TE (vols_pct is _rec-only), which")
say(f"  is the {switched.sum()} counted here. Both are correct; different denominators.")
A = A.merge(vb[["player_id", "override"]], on="player_id", how="left")
A["override"] = A["override"].fillna(False)
ovr = A[A.override & (A.adp_rank <= DRAFTABLE_ADP)]
say(f"  override & draftable & matched: n={len(ovr)}  ordering-agreement="
    f"{ovr.agree.mean()*100:.1f}%  (this is the population where role_pct IS the VOLS")
say("   percentile — census R5; a real depth-chart signal here competes with NOTHING)")

overall_agree = A[A.adp_rank <= DRAFTABLE_ADP].agree.mean() * 100
say("")
say(f"GATE (charter H2g): draftable ordering-agreement = {overall_agree:.1f}% "
    f"vs the 95% cosmetic bar -> {'COSMETIC, STOP' if overall_agree >= 95 else 'MATERIAL, CONTINUE'}")
flush()
if overall_agree >= 95:
    say("Agreement >= 95%: the swap is cosmetic. Stopping per charter H2g.")
    flush()
    sys.exit(0)

# =============================================================================================
# SECTION B — 2025 INSTRUMENTS
# =============================================================================================
say("")
say("=" * 100)
say("SECTION B — 2025: week-1-adjacent depth chart vs 44_-blend projection-derived team_role [V]")
say("=" * 100)

dc25 = load_dc2025()
wk1_dt = sorted(d for d in dc25.dt.unique() if d <= WK1_CUT)[-1]
aug7_dt = sorted(d for d in dc25.dt.unique() if d <= AUG7_CUT)[-1]
say(f"snapshots: week-1-adjacent dt={wk1_dt}   draft-day-equivalent dt={aug7_dt}")
say("(the operational 2026 instrument is an Aug-07 chart — the Aug-07 2025 run below is the")
say(" lead-time sensitivity for exactly that)")

blend = pd.DataFrame(json.load(open(os.path.join(HERE, "blend_cache_2019_2025.json")))["2025"])
# 44_ prep(), minus its adp<=220 pool filter (role ordering wants the full cached universe):
for c in ("espn", "sleeper"):
    blend[c + "_s"] = blend[c] * (blend["actual"].mean() / blend[c].mean())
blend["proj"] = 0.5 * blend["espn_s"] + 0.5 * blend["sleeper_s"]
blend["nn"] = blend["name"].map(normalize_name)
blend = blend.rename(columns={"pos": "position"})
dup = blend.duplicated(subset=["nn", "position"], keep=False).sum()
say(f"44_ blend cache 2025: {len(blend)} players (ADP {blend.adp.min():.0f}-{blend.adp.max():.0f}"
    f"); dup name+pos rows dropped: {dup}")
blend = blend[~blend.duplicated(subset=["nn", "position"], keep=False)]


def build_rooms(snapshot_dt):
    snap = dc25[dc25.dt == snapshot_dt].copy()
    snap["nn"] = snap.player_name.map(normalize_name)
    snap = snap.rename(columns={"pos_abb": "position"})
    snap = snap[~snap.duplicated(subset=["nn", "position"], keep=False)]
    j = blend.merge(snap[["nn", "position", "team", "pos_rank", "gsis_id"]],
                    on=["nn", "position"], how="inner")
    j = common_set_orders(j.assign(proj_key=-j["proj"]), "proj_key", "pos_rank")
    return j


B = build_rooms(wk1_dt)
say(f"common set (blend  ∩ week-1 snapshot, name+pos join): {len(B)} of {len(blend)} blend players")
say(f"  by position: {dict(B.position.value_counts())}")
unm = blend[~blend.nn.isin(B.nn)]
say(f"  unmatched blend players (not on any week-1 chart — injured/cut/suspended): {len(unm)}; "
    f"top-priced examples: {', '.join(unm.nsmallest(5, 'adp')['name'])}")

# realized roles from weekly.parquet 2025 (REG, QB/RB/WR/TE by construction — T0.3)
wk = pd.read_parquet(os.path.join(HERE, "weekly.parquet"))
w25 = wk[wk.season == 2025]
assert len(w25) > 0, "S8: weekly.parquet has no 2025 rows"
opp = w25.groupby("player_id").agg(carries=("carries", "sum"), targets=("targets", "sum"),
                                   attempts=("attempts", "sum")).reset_index()
opp["opps"] = opp.carries + opp.targets  # RB/WR/TE volume
B = B.merge(opp.rename(columns={"player_id": "gsis_id"}), on="gsis_id", how="left")
B[["carries", "targets", "attempts", "opps"]] = B[["carries", "targets", "attempts", "opps"]].fillna(0)
B["real_vol"] = np.where(B.position == "QB", B.attempts + B.carries, B.opps)
B["ord_real"] = B.groupby(["team", "position"])["real_vol"].rank(
    ascending=False, method="first").astype(int)
say(f"realized-role volume joined from weekly.parquet 2025 (gsis): "
    f"{(B.real_vol > 0).sum()} of {len(B)} common-set players logged 2025 volume")

# 2025 movers (priority sub-population): week-1 snapshot team != last 2024 weekly team
w24 = wk[wk.season == 2024].sort_values("week").groupby("player_id")["team"].last()
B["team_2024"] = B.gsis_id.map(w24)
B["switched_2025"] = B.team_2024.notna() & (B.team_2024 != B.team)
say(f"2025 switched-team (wk-1 team != last 2024 team): {B.switched_2025.sum()} of {len(B)}")
say("NOTE: the ASCENDING half of the override population is NOT reconstructed for 2025 (needs")
say("the 2025-preseason xppg file, which does not exist on disk) — stated, not hidden. The 2026")
say("agreement split in Section A covers the full override population.")
flush()

# =============================================================================================
# SECTION C — OUTCOMES: league-scored points-above-price (price = T0.2 repair = SLEEPER adp_ppr)
# =============================================================================================
say("")
say("=" * 100)
say("SECTION C — outcome-above-price instruments [V]")
say("=" * 100)
say("PRICE INSTRUMENT (T0.2 contract, stated loudly): 2025 prices are ** Sleeper adp_ppr ** from")
say("seasons_2025repair.parquet — NOT ESPN ADP, NOT FFC. Fallback ecr_hist was not needed.")

rep = pd.read_parquet(os.path.join(HERE, "seasons_2025repair.parquet"))
lg = pd.read_parquet(os.path.join(HERE, "seasons_league.parquet"))
assert (lg[lg.season == 2025].shape[0] == 608), "S8: league panel 2025 row count changed"

# league expectation curve: 02_expectation's exact curve code, re-fit on LEAGUE points 2014-2024
sea = pd.read_parquet(os.path.join(HERE, "seasons_exp.parquet"))
fit = sea[sea.season < 2025].merge(
    lg[["player_id", "season", "total_league"]], on=["player_id", "season"], how="inner")
per_year = fit.groupby("season").size()
say(f"curve fit pool: seasons_exp x seasons_league 2014-2024, rows/yr min={per_year.min()} "
    f"max={per_year.max()} (S8 per-year counts: {per_year.to_dict()})")
fit["pts_psg"] = fit["total_league"] / fit["season_games"]


def expectation_curve(df, max_rank=80):          # verbatim from 02_expectation.py
    d = df[df["exp_pos_rank"].notna() & (df["exp_pos_rank"] <= max_rank)]
    m = d.groupby(d["exp_pos_rank"].astype(int))["pts_psg"].agg(["mean", "count"])
    m = m.reindex(range(1, max_rank + 1))
    m["mean"] = m["mean"].interpolate(limit_direction="both")
    sm = m["mean"].rolling(5, center=True, min_periods=1).mean()
    sm = np.minimum.accumulate(sm)
    return sm


curves = {pos: expectation_curve(fit[fit.position == pos]) for pos in SKILL}
say("league-scored expectation (pts/scheduled-game) at pos rank 1/5/12/24/36:")
for pos, c in curves.items():
    say(f"  {pos}: " + " / ".join(f"{c.iloc[r-1]:.2f}" for r in [1, 5, 12, 24, 36]))

out = rep[["player_id", "position", "name_disp", "adp", "exp_pos_rank", "season_games",
           "total_pts", "exp_pts"]].merge(
    lg.loc[lg.season == 2025, ["player_id", "total_league"]], on="player_id", how="left")
out["total_league"] = out["total_league"].fillna(0.0)   # priced-but-unplayed graded at 0 (T0.2 note)


def exp_league(row):
    if pd.isna(row.exp_pos_rank):
        return np.nan
    c = curves[row.position]
    return c.iloc[min(int(row.exp_pos_rank), len(c)) - 1] * row.season_games


out["exp_league_pts"] = out.apply(exp_league, axis=1)
out["paa_league"] = out.total_league - out.exp_league_pts     # PRIMARY currency
out["paa_base"] = out.total_pts - out.exp_pts                  # SECONDARY currency
priced = out[(out.adp <= PRICED_MAX) & out.paa_league.notna()]
say(f"2025 outcome rows: {len(out)}; priced (adp<= {PRICED_MAX}) with defined league expectation: "
    f"{len(priced)}; unplayed-graded-at-0 among priced: {(priced.total_league == 0).sum()}")
B = B.merge(out[["player_id", "adp", "paa_league", "paa_base", "total_league", "total_pts"]]
            .rename(columns={"player_id": "gsis_id", "adp": "adp_rep"}), on="gsis_id", how="left")
flush()

# =============================================================================================
# SECTION D — HEAD-TO-HEAD
# =============================================================================================
say("")
say("=" * 100)
say("SECTION D — head-to-head: does the chart's contradiction of the projection carry info? [V]")
say("=" * 100)


def pairs_table(J, positions):
    rooms = J[J.position.isin(positions)].groupby(["team", "position"]).filter(lambda g: len(g) >= 2)
    P1 = rooms[rooms.ord_proj == 1].set_index(["team", "position"])
    D1 = rooms[rooms.ord_dc == 1].set_index(["team", "position"])
    idx = P1.index.intersection(D1.index)
    rowsL = []
    for k in idx:
        p, d = P1.loc[k], D1.loc[k]
        if p["name"] == d["name"]:
            continue
        rowsL.append({"team": k[0], "position": k[1], "dc_no1": d["name"], "proj_no1": p["name"],
                      "dc_adp": d.get("adp_rep", np.nan), "proj_adp": p.get("adp_rep", np.nan),
                      "dc_paaL": d.get("paa_league", np.nan), "proj_paaL": p.get("paa_league", np.nan),
                      "dc_paaB": d.get("paa_base", np.nan), "proj_paaB": p.get("paa_base", np.nan),
                      "dc_ptsL": d.get("total_league", np.nan), "proj_ptsL": p.get("total_league", np.nan),
                      "dc_real1": d["ord_real"] == 1 if "ord_real" in d else np.nan,
                      "proj_real1": p["ord_real"] == 1 if "ord_real" in p else np.nan,
                      "any_switch": bool(d.get("switched_2025", False) or p.get("switched_2025", False))})
    return pd.DataFrame(rowsL)


pairs = pairs_table(B, REC)
say(f"RB/WR/TE rooms with >=2 common-set players: "
    f"{B[B.position.isin(REC)].groupby(['team','position']).filter(lambda g: len(g)>=2).groupby(['team','position']).ngroups}")
say(f"disagreement rooms (dc No.1 != proj No.1): {len(pairs)}")

pp = pairs[(pairs.dc_adp <= PRICED_MAX) & (pairs.proj_adp <= PRICED_MAX)
           & pairs.dc_paaL.notna() & pairs.proj_paaL.notna()]
diff = pp.dc_paaL - pp.proj_paaL
k = int((diff > 0).sum())
say("")
say("--- PRIMARY ENDPOINT [V] ---")
say(f"n disagreement pairs, both priced (adp<={PRICED_MAX}): {len(pp)}")
if len(pp):
    say(f"mean paired diff, LEAGUE points-above-price (dc-favored - proj-favored): {diff.mean():+.1f}")
    say(f"median {diff.median():+.1f}   dc-favored wins {k}/{len(pp)} ({k/len(pp)*100:.0f}%)   "
        f"sign-test p={binom_p(k, len(pp)):.3f} (descriptive only)")
    boot = [np.random.default_rng(i).choice(diff, len(diff)).mean() for i in range(2000)]
    say(f"pair-bootstrap 95% CI [{np.percentile(boot, 2.5):+.1f}, {np.percentile(boot, 97.5):+.1f}]"
        " — DESCRIPTIVE ONLY: the S11 treatment unit is the SEASON and effective n = 1 cluster.")
say("VERDICT CAP: DIRECTIONAL-ONLY regardless of the number (n = 1 season; 2026 is the test).")

say("")
say("--- SECONDARIES [V] ---")
db = pp.dc_paaB - pp.proj_paaB
say(f"base-PPR currency (S12 secondary), same pairs: mean {db.mean():+.1f}, "
    f"dc wins {(db>0).sum()}/{len(pp)}")
dr = pairs.dc_ptsL - pairs.proj_ptsL
say(f"raw league points, ALL {len(pairs)} pairs (no price filter): mean {dr.mean():+.1f}, "
    f"dc wins {(dr>0).sum()}/{dr.notna().sum()}")
t_dc = pairs.dc_real1.astype(float).mean()
t_pj = pairs.proj_real1.astype(float).mean()
say(f"realized-role No.1 accuracy IN DISAGREEMENT ROOMS: depth chart {t_dc*100:.0f}% vs "
    f"projection {t_pj*100:.0f}%  (n={len(pairs)} rooms)")

allrooms = B[B.position.isin(REC)].groupby(["team", "position"]).filter(lambda g: len(g) >= 2)
d_all = (allrooms[allrooms.ord_dc == 1].ord_real == 1).mean()
p_all = (allrooms[allrooms.ord_proj == 1].ord_real == 1).mean()
say(f"realized-role No.1 accuracy, ALL rooms: depth chart {d_all*100:.0f}% vs projection "
    f"{p_all*100:.0f}% (n={allrooms.groupby(['team','position']).ngroups})")
Bd = B[B.adp_rep <= DRAFTABLE_ADP]
say(f"player-level rank agreement with realized role, priced<= {DRAFTABLE_ADP} (n={len(Bd)}): "
    f"depth {(Bd.ord_dc==Bd.ord_real).mean()*100:.0f}% vs projection "
    f"{(Bd.ord_proj==Bd.ord_real).mean()*100:.0f}%")

sw = pairs[pairs.any_switch]
swp = sw[(sw.dc_adp <= PRICED_MAX) & (sw.proj_adp <= PRICED_MAX)
         & sw.dc_paaL.notna() & sw.proj_paaL.notna()]
say("")
say(f"PRIORITY SUB-POPULATION (pair involves a 2025 switched-team player): "
    f"{len(sw)} pairs, {len(swp)} both-priced")
if len(swp):
    ds = swp.dc_paaL - swp.proj_paaL
    say(f"  league paa diff: mean {ds.mean():+.1f}, dc wins {(ds>0).sum()}/{len(swp)}")
say(f"  realized No.1 in switched pairs: depth {sw.dc_real1.astype(float).mean()*100:.0f}% vs "
    f"proj {sw.proj_real1.astype(float).mean()*100:.0f}%")

# QB rooms (secondary — role machinery does not re-rank QBs, census R12)
qb_pairs = pairs_table(B, ["QB"])
say(f"QB rooms (secondary, not in the primary): {len(qb_pairs)} disagreement rooms; "
    f"depth realized-No.1 {qb_pairs.dc_real1.astype(float).mean()*100:.0f}% vs "
    f"proj {qb_pairs.proj_real1.astype(float).mean()*100:.0f}%"
    if len(qb_pairs) else "QB rooms (secondary): 0 disagreement rooms")

# lead-time sensitivity: Aug-07 snapshot (the operational 2026 lead time)
B7 = build_rooms(aug7_dt)
B7 = B7.merge(opp.rename(columns={"player_id": "gsis_id"}), on="gsis_id", how="left")
B7[["carries", "targets", "attempts"]] = B7[["carries", "targets", "attempts"]].fillna(0)
B7["real_vol"] = np.where(B7.position == "QB", B7.attempts + B7.carries,
                          B7.carries + B7.targets)
B7["ord_real"] = B7.groupby(["team", "position"])["real_vol"].rank(
    ascending=False, method="first").astype(int)
B7 = B7.merge(out[["player_id", "adp", "paa_league", "paa_base", "total_league"]]
              .rename(columns={"player_id": "gsis_id", "adp": "adp_rep"}), on="gsis_id", how="left")
B7["switched_2025"] = False
p7 = pairs_table(B7, REC)
pp7 = p7[(p7.dc_adp <= PRICED_MAX) & (p7.proj_adp <= PRICED_MAX)
         & p7.dc_paaL.notna() & p7.proj_paaL.notna()]
d7 = pp7.dc_paaL - pp7.proj_paaL
say("")
say(f"LEAD-TIME SENSITIVITY — Aug-07-2025 snapshot (the draft-day lead time): "
    f"{len(p7)} disagreement rooms, {len(pp7)} both-priced; league paa diff mean {d7.mean():+.1f}, "
    f"dc wins {(d7>0).sum()}/{len(pp7)}; realized-No.1 depth "
    f"{p7.dc_real1.astype(float).mean()*100:.0f}% vs proj {p7.proj_real1.astype(float).mean()*100:.0f}%")

say("")
say("disagreement pairs, week-1 2025 (both-priced set the primary was computed on):")
for _, r in pp.sort_values("dc_adp").iterrows():
    say(f"  {r.team} {r.position}: chart={r.dc_no1} (adp {r.dc_adp:.0f}, paaL {r.dc_paaL:+.0f}) "
        f"vs proj={r.proj_no1} (adp {r.proj_adp:.0f}, paaL {r.proj_paaL:+.0f})"
        + ("  [switch]" if r.any_switch else ""))
flush()

# =============================================================================================
# SECTION E — VERDICT, CENSUS, 2026 PREREGISTRATION
# =============================================================================================
say("")
say("=" * 100)
say("SECTION E — verdict + role census + the 2026 preregistration")
say("=" * 100)
say("""
HEADLINE (the conclusion a future reader should reconstruct from the numbers above):
1. The cheap check is MATERIAL overall (68.3%) but the disagreement is PRICE-STRATIFIED: 100%
   agreement in the top-50, 92.9% top-100, 92.2% of room leaders — the chart and the projection
   only part company in the mid/late rounds and in the override population (60.9%, n=64), which
   is exactly the population the charter said a role signal would compete with nothing in.
2. On the one season of testable history, the depth chart did NOT beat the projection: primary
   endpoint -5.8 league pts-above-price per disagreement pair (3/6 wins, n=6 — noise); realized-
   role No.1 accuracy FAVORS THE PROJECTION in disagreement rooms (50% vs 17% wk-1; 60% vs 10%
   at the Aug-07 lead time) and is a tie overall (74% vs 71% across 70 rooms).
3. The chart carries a verified STALENESS hazard the projection does not: the 2026-07-31 chart
   ranks a Sleeper-PUP player (Charbonnet) SEA RB1 (see the check below; project memory's
   SEA-backfield note [R] said the same).
=> DIRECTIONAL READ: H2g's REPLACE premise is unsupported — the evidence points to the census's
   HYBRID option at most (order-from-chart only where it survives a freshness check, magnitude
   from the projection), or to keeping the chart as a CONTRADICTION FLAG (a fact surfaced to the
   advisor, like the health facts) rather than a rank input. The 2026 preregistration below is
   the test that could reverse this.

VERDICT: DIRECTIONAL-ONLY by construction. n = ONE season (2025) of new-schema history; the S11
treatment unit is the season, so effective n = 1 cluster and no paired grade is attempted — at
n=1 the MDE (S11: ~+45 pts needs 10 clusters at 80% power) makes any points claim meaningless.
The real test is the 2026 season, pre-registered below.

WHICH ROLE SITES A SWAP WOULD TOUCH (census results_60_censuses.txt, [R] — role lives in SIX
sites, not five): R1 value_board.py:41-43 (team_role), R2 :48-51 (role_lead), R5 :98-112 (the
override population where role_pct IS the VOLS pct), R8 app_pages/draft.py:90-94 (the silent
byte-for-byte fallback duplicate of R1 — miss it and an old CSV resurrects the projection role),
R18 cohort_priors.py:85 (role_rank kNN matching feature), plus consumers R11-R13/R16
(advisor.py:364-385, :1465, :1573-1581) which inherit through role_lead. role_lead's MAGNITUDE
(0.5 VONA/pt capped +/-10; +/-15-pt alpha prose; >=15 ascend gate) cannot come from an ordinal
pos_rank — the census's option (a) HYBRID (order from the chart, magnitude = the projection gap
along the chart's ordering, with a defined semantic for negative leads in disagreement rooms) is
the reconstruction this script's evidence speaks to. Any swap touches 5 production files + 3 test
suites AT ONCE (L52/L53: a partial fix to a duplicated concept is worse than no fix).

2026 PREREGISTRATION (the real test — grade after the 2026 season):
The Section-A disagreement pairs on TODAY'S board (frozen below, snapshot dt printed in Section
A) are the treatment set. Endpoint, declared now: in each 2026 disagreement room, the realized
2026 within-room No.1 by volume (carries+targets; attempts+carries for QB) decides the winner;
secondary: league-scored points-above-price with the price = 2026 draft-day ESPN ADP already on
the board. If the chart beats the projection on those rooms at a rate resembling the 2025
direction, the H2g swap graduates from DIRECTIONAL to actionable; if not, it dies here.""")
say("2026 disagreement rooms (at least one No.1 in the draftable range, from Section A):")
lead_dis = lead[~lead.same].copy()
lead_dis = lead_dis[(lead_dis.dc_no1_adp.fillna(999) <= DRAFTABLE_ADP)
                    | (lead_dis.proj_no1_adp.fillna(999) <= DRAFTABLE_ADP)]
lead_dis = lead_dis.sort_values(["position", "team"])
for _, r in lead_dis.iterrows():
    say(f"  {r.team} {r.position}: chart No.1 = {r.dc_no1} (adp {r.dc_no1_adp:.0f})  vs  "
        f"board team_role No.1 = {r.proj_no1} (adp {r.proj_no1_adp:.0f})")
say(f"  ({len(lead_dis)} rooms of {len(lead)} with >=2 matched players)")

# chart-STALENESS caution: cross the 2026 disagreement names against Sleeper's live injury FACTS
# (the same feed tools/injury_watch.py ships — facts, not forecasts). A chart that still lists an
# injured player at No.1 is exactly the failure a naive swap would inject into the board.
try:
    import requests
    sl = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=60).json()
    inj = {}
    for p in sl.values():
        if isinstance(p, dict) and p.get("injury_status"):
            nm = normalize_name(f"{p.get('first_name','')} {p.get('last_name','')}")
            inj[(nm, p.get("position"))] = p["injury_status"]
    say("")
    say("chart-staleness check — Sleeper live injury_status (FACTS feed) for the names above [V]:")
    flagged = 0
    for _, r in lead_dis.iterrows():
        for who, tag in [(r.dc_no1, "chart No.1"), (r.proj_no1, "board No.1")]:
            st = inj.get((normalize_name(who), r.position))
            if st:
                flagged += 1
                say(f"  {r.team} {r.position} {tag} {who}: injury_status={st}"
                    + ("  <-- the chart still ranks an injured player No.1"
                       if tag == "chart No.1" else ""))
    if not flagged:
        say("  (no current injury designations among the 20 names)")
except Exception as e:                                    # offline-safe: the check is a bonus
    say(f"  (Sleeper injury check skipped: {type(e).__name__})")
say("")
say("NOT DONE / LIMITS (honest-partial contract): (1) no paired-draft grade — forbidden at n=1 by")
say("the assignment itself; (2) the 2025 ASCENDING-lead half of the override population was not")
say("reconstructed (no 2025-preseason xppg on disk) — switched-team only; (3) realized role uses")
say("season-total volume ranked within the week-1 room grouping — mid-season movers blur it;")
say("(4) blend-cache roles exist only for its 245 cached players — camp bodies invisible to the")
say("projection side; (5) 2019/2023 depth-chart era untouched per the schema break; (6) the")
say("Aug-07 sensitivity shares the 2025 season with the primary — it is a lead-time probe, not")
say("replication (S2). Replication slice = the 2026 season, by preregistration above.")
flush()
print(f"\nwrote {OUT}")
