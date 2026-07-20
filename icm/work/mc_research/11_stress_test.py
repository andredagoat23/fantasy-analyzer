# STRESS TEST - cohorts + board outputs.
# A. Cohort leave-one-season-out (LOSO) validation: for every historical player-season, build his
#    cohort from OTHER seasons only (same kNN as cohort_priors), then check whether cohort rates
#    actually PREDICT realized outcomes (calibration by decile + discrimination top-vs-bottom).
# B. Board invariant audit: percentile ordering, probability identities, flags, coverage, SOS shape.
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
OUT = "icm/work/mc_research"
FAIL = []

def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)

# ================= A. cohort LOSO predictive validation =================
sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")
hist = sea[sea["mult"].notna() & (sea["exp_pos_rank"] <= 70)].copy()
hist["moved"] = (hist["team_last"] != hist["prev_team_last"]) & hist["prev_team_last"].notna()
hist["role_rank"] = hist.groupby(["season", "team_last", "position"])["exp_pos_rank"].rank(method="first")
for c in ["draft_number", "years_exp", "age", "prev_ppg", "prev_games_missed", "implied_total_avg"]:
    hist[c] = pd.to_numeric(hist[c], errors="coerce")
hist = hist.reset_index(drop=True)

K = 15
preds = []
for pos in ["QB", "RB", "WR", "TE"]:
    hp = hist[hist.position == pos].reset_index(drop=True)
    n = len(hp)
    # feature matrix mirrors cohort_priors distances
    rank = hp["exp_pos_rank"].values
    yexp = hp["years_exp"].fillna(3).values
    cap = hp["draft_number"].fillna(180).values
    ppg = hp["prev_ppg"].fillna(4).values
    age = hp["age"].fillna(26).values
    mov = hp["moved"].values.astype(float)
    role = hp["role_rank"].fillna(2).values
    veg = hp["implied_total_avg"].fillna(22.5).values
    inj = hp["prev_games_missed"].fillna(3).values
    season = hp["season"].values
    rookie = (hp["years_exp"].fillna(1) == 0).values
    mult = hp["mult"].values
    for i in range(n):
        same_class = rookie == rookie[i]
        elig = same_class & (season != season[i])          # LOSO: never same season
        d = (np.abs(rank - rank[i]) / 6.0 + np.abs(cap - cap[i]) / 40.0
             + np.abs(age - age[i]) / 2.5 + np.abs(mov - mov[i]) * 0.7
             + np.abs(role - role[i]) / 1.0 + np.abs(veg - veg[i]) / 2.5
             + np.abs(season - season[i]) * 0.02)
        if not rookie[i]:
            d = d + np.abs(yexp - yexp[i]) / 2.0 + np.abs(ppg - ppg[i]) / 3.0 + np.abs(inj - inj[i]) / 5.0
        d = np.where(elig, d, np.inf)
        idx = np.argpartition(d, K)[:K]
        cm = mult[idx]
        preds.append({"pos": pos, "i_mult": mult[i],
                      "c_boom": (cm >= 1.3).mean(), "c_bust": (cm <= 0.7).mean(),
                      "c_med": np.median(cm)})
pr = pd.DataFrame(preds)
pr["r_boom"] = pr["i_mult"] >= 1.3
pr["r_bust"] = pr["i_mult"] <= 0.7
# apply the SHIPPED empirical-Bayes shrinkage (m=25, fitted here) before judging calibration
M = 25
bb = pr.groupby("pos")["r_boom"].transform("mean")
bu = pr.groupby("pos")["r_bust"].transform("mean")
pr["c_boom"] = (pr["c_boom"] * K + bb * M) / (K + M)
pr["c_bust"] = (pr["c_bust"] * K + bu * M) / (K + M)

print("=== A. cohort LOSO validation ===")
# calibration: quintiles of predicted boom -> realized boom (monotone? close?)
pr["q"] = pd.qcut(pr["c_boom"], 5, labels=False, duplicates="drop")
cal = pr.groupby("q").agg(pred=("c_boom", "mean"), real=("r_boom", "mean"), n=("r_boom", "size"))
print("boom calibration by predicted quintile:")
print(cal.round(3).to_string())
mono = cal["real"].is_monotonic_increasing
gap = (cal["pred"] - cal["real"]).abs().max()
check("boom quintiles monotone-increasing in realized rate", mono, f"realized: {list(cal['real'].round(2))}")
check("boom calibration gap (max |pred-real| per quintile) < 0.08", gap < 0.08, f"max gap {gap:.3f}")
top, bot = pr[pr.q == pr.q.max()], pr[pr.q == 0]
check("discrimination: top-quintile realized boom >= 1.5x bottom",
      top["r_boom"].mean() >= 1.5 * max(bot["r_boom"].mean(), 1e-9),
      f"{top['r_boom'].mean():.2f} vs {bot['r_boom'].mean():.2f}")
prb = pr.copy()
prb["qb"] = pd.qcut(prb["c_bust"], 5, labels=False, duplicates="drop")
calb = prb.groupby("qb").agg(pred=("c_bust", "mean"), real=("r_bust", "mean"))
gapb = (calb["pred"] - calb["real"]).abs().max()
print("bust calibration by predicted quintile:")
print(calb.round(3).to_string())
check("bust quintiles monotone", calb["real"].is_monotonic_increasing, f"{list(calb['real'].round(2))}")
check("bust calibration gap < 0.08", gapb < 0.08, f"max gap {gapb:.3f}")

# ================= B. board invariant audit =================
print("\n=== B. board + data invariants ===")
b = pd.read_csv("players_with_outcomes.csv")
bb = b[b["total_points"].notna() & b["P_pos1"].notna()]
check("percentile ordering p10<=floor<=ceiling<=p90 for all",
      ((bb.p10 <= bb.floor + 1e-6) & (bb.floor <= bb.ceiling + 1e-6) & (bb.ceiling <= bb.p90 + 1e-6)).all())
check("probabilities in [0,1]",
      bb[["P_pos1", "p_elite", "p_startable", "p_bust"]].apply(lambda s: s.between(0, 1)).all().all())
check("p_startable + p_bust == 1", np.allclose(bb.p_startable + bb.p_bust, 1, atol=1e-6))
check("P_pos1 >= p_elite", (bb.P_pos1 >= bb.p_elite - 1e-9).all())
check("availability in [0.5, 1] where set", bb.availability.dropna().between(0.5, 1).all())
NEWHC = {"ARI", "ATL", "BAL", "BUF", "CLE", "LV", "MIA", "NYG", "PIT", "TEN"}
check("new_hc_team flag == verified 10-team list",
      set(bb.loc[bb.new_hc_team.fillna(False), "team"].unique()) == NEWHC,
      str(sorted(set(bb.loc[bb.new_hc_team.fillna(False), 'team'].unique()))))
# elite tiers narrower than deep tiers, per position
ok_bands = True
for pos in ["QB", "RB", "WR", "TE"]:
    s = bb[bb.position == pos].copy()
    s["r"] = s["total_points"].rank(ascending=False)
    el = s[s.r <= 6]; dp = s[(s.r >= 25) & (s.r <= 45)]
    if len(el) and len(dp):
        ok_bands &= (el.ceiling / el.floor).median() < (dp.ceiling / dp.floor).median()
check("elite band ratio < deep band ratio (all positions)", ok_bands)
vb = pd.read_csv("value_board.csv")
check("value_board floors present, no NaN", vb["floor"].notna().all())
co = pd.read_csv("cohort_data.csv")
check("cohort coverage ~280 with n=15 all", len(co) >= 270 and (co.cohort_n == 15).all(), f"{len(co)} rows")
check("cohort rates in [0,1]", co[["cohort_boom", "cohort_bust", "cohort_top5"]].apply(
    lambda s: s.between(0, 1)).all().all())
check("cohort comps well-formed (5 entries)", co["cohort_comps"].str.count(r"\|").eq(4).all())
sos = pd.read_csv("sos_data.csv")
check("sos 32x4 rows", len(sos) == 128)
check("sos ranks span 1..32 per position",
      all(set(sos[sos.position == p].sos_rank).issuperset({1}) and sos[sos.position == p].sos_rank.max() == 32
          for p in ["QB", "RB", "WR", "TE"]))
hc = pd.read_csv("data/new_hc_2026.csv")
check("new_hc csv has 10 TRUE rows", int(hc.new_hc.sum()) == 10)

print(f"\n{'ALL PASS' if not FAIL else 'FAILURES: ' + ', '.join(FAIL)}")
