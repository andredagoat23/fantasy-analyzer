# Injury research: base rates of missed games / season-ending injuries, what predicts them,
# how devastating they are - and how MC's current constants compare.
# MC today: AVAIL_PRIOR {RB .86 WR .92 TE .91 QB .94}; p_major = clip(.06+(1-av)*.15, .06, .30);
#           age cliff RB26/.025 WR29/.015 TE29/.015 QB35/.02; major-injury games ~ U(0,8).
import pandas as pd
import numpy as np

OUT = "icm/work/mc_research"
sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")
wk = pd.read_parquet(f"{OUT}/weekly.parquet")

# relevant universe: fantasy-relevant players (preseason expectation <= 60 at their position)
pool = sea[(sea["exp_pos_rank"].notna()) & (sea["exp_pos_rank"] <= 60)].copy()
pool["missed_frac"] = pool["games_missed"] / pool["season_games"]
pool["big_miss"] = pool["games_missed"] >= 4          # missed a quarter of the season
pool["catastrophic"] = pool["games_missed"] >= 9      # lost most of the season

print(f"pool: {len(pool)} fantasy-relevant player-seasons\n")

# ---------- 1. base rates by position (compare to MC constants) ----------
t1 = pool.groupby("position").agg(
    n=("games", "size"), games_mean=("games", "mean"),
    played_frac=("games_frac", "mean"),
    miss4=("big_miss", "mean"), miss9=("catastrophic", "mean"),
    ended_early=("ended_early", "mean"), missed_med=("games_missed", "median"))
print("=== availability base rates by position (fantasy-relevant) ===")
print(t1.round(3).to_string())
print("MC AVAIL_PRIOR says: RB .86  WR .92  TE .91  QB .94 (frac of 17)")
print("MC p_major floor 6%, cap 30%; empirical analog = miss9 / ended_early above\n")

# ---------- 2. severity: distribution of games missed GIVEN any miss ----------
m = pool[pool["games_missed"] >= 1]
print("=== severity: games missed distribution | missed >=1 ===")
for pos, g in m.groupby("position"):
    q = g["games_missed"].quantile([.25, .5, .75, .9]).tolist()
    print(f"  {pos}: n={len(g)} q25={q[0]:.0f} med={q[1]:.0f} q75={q[2]:.0f} q90={q[3]:.0f} "
          f"share>=9wks={(g['games_missed']>=9).mean():.1%}")
print()

# ---------- 3. age curves: missed games by age bucket x position ----------
ab = pool.copy()
ab["age_b"] = pd.cut(ab["age"], [20, 23, 25, 27, 29, 31, 40],
                     labels=["<=23", "24-25", "26-27", "28-29", "30-31", "32+"])
t3 = ab.groupby(["position", "age_b"], observed=True).agg(
    n=("big_miss", "size"), games_mean=("games", "mean"), miss4=("big_miss", "mean"),
    miss9=("catastrophic", "mean"))
print("=== age curve of availability ===")
print(t3[t3.n >= 12].round(3).to_string(), "\n")

# ---------- 4. recurrence: does last-year injury predict this year? ----------
r = pool[pool["prev_games_missed"].notna()].copy()
r["prev_b"] = pd.cut(r["prev_games_missed"], [-1, 0, 2, 5, 20],
                     labels=["0", "1-2", "3-5", "6+"])
t4 = r.groupby(["position", "prev_b"], observed=True).agg(
    n=("big_miss", "size"), games_mean=("games", "mean"),
    miss4=("big_miss", "mean"), miss9=("catastrophic", "mean"))
print("=== recurrence: this-year availability by LAST year's games missed ===")
print(t4[t4.n >= 10].round(3).to_string(), "\n")

# multi-year: two straight healthy seasons vs two straight injured
r2 = pool.dropna(subset=["prev_games_missed"]).copy()
r2["prev_inj"] = r2["prev_games_missed"] >= 3
t4b = r2.groupby(["position", "prev_inj"]).agg(n=("big_miss", "size"), miss4=("big_miss", "mean"))
print(t4b.round(3).to_string(), "\n")

# ---------- 5. workload: RB touches -> next-season availability + performance ----------
rb = pool[(pool["position"] == "RB") & pool["prev_total_touches"].notna()].copy()
rb["load_b"] = pd.cut(rb["prev_total_touches"], [0, 150, 250, 320, 500],
                      labels=["<150", "150-250", "250-320", "320+"])
t5 = rb.groupby("load_b", observed=True).agg(
    n=("big_miss", "size"), games_mean=("games", "mean"), miss4=("big_miss", "mean"),
    mult_pg_med=("mult_pg", "median"), mult_med=("mult", "median"))
print("=== RB prior-season total touches -> next season ===")
print(t5.round(3).to_string(), "\n")

# ---------- 6. injury TYPE: recurrence + cost by body part (from weekly reports) ----------
inj_cost = pool[pool["inj_primary"].notna()].groupby("inj_primary").agg(
    n=("games_missed", "size"), missed_mean=("games_missed", "mean"),
    miss4=("big_miss", "mean"))
inj_cost = inj_cost[inj_cost["n"] >= 20].sort_values("missed_mean", ascending=False)
print("=== games missed by primary injury type (season level, n>=20) ===")
print(inj_cost.round(2).to_string(), "\n")

# soft-tissue recurrence: hamstring this year -> hamstring/miss next year?
soft = ["Hamstring", "Groin", "Calf", "Quadricep"]
pool["soft_prev"] = pool["prev_inj_primary"].isin(soft) if "prev_inj_primary" in pool.columns else False
if "prev_inj_primary" in pool.columns:
    t6 = pool[pool["prev_inj_primary"].notna()].copy()
    t6["prev_soft"] = t6["prev_inj_primary"].isin(soft)
    g = t6.groupby("prev_soft").agg(n=("big_miss", "size"), miss4=("big_miss", "mean"),
                                    games_mean=("games", "mean"))
    print("=== prior-year soft-tissue injury -> this year ===")
    print(g.round(3).to_string(), "\n")

# ---------- 7. in-season signal: listed Questionable/Out weeks -> rest-of-season? ----------
# (useful for live-draft risk flags; MC is preseason so keep brief)
q = pool.copy()
q["listed_b"] = pd.cut(q["inj_weeks_listed"], [-1, 0, 2, 5, 20], labels=["0", "1-2", "3-5", "6+"])
t7 = q.groupby("listed_b", observed=True).agg(n=("ppg", "size"), mult_pg_med=("mult_pg", "median"))
print("=== weeks on injury report vs per-game outcome (context) ===")
print(t7.round(3).to_string(), "\n")

# ---------- 8. how devastating: points lost vs expectation decomposition ----------
# For big-miss players: how much of the shortfall is games vs per-game decline when active?
bm = pool[pool["big_miss"] & pool["mult"].notna() & pool["mult_pg"].notna()]
print("=== devastation: outcomes for players who missed 4+ games ===")
for pos, g in bm.groupby("position"):
    print(f"  {pos}: n={len(g)} season mult med={g['mult'].median():.2f} "
          f"per-game mult med={g['mult_pg'].median():.2f} "
          f"(games gone AND {1-g['mult_pg'].median():.0%} worse per game when active)")
print()

# ---------- 9. does MC's uniform(0,8) major-injury games match reality? ----------
cat = pool[pool["catastrophic"]]
print("=== catastrophic (9+ missed): games actually played distribution ===")
print(cat["games"].describe().round(1).to_string())
print("\nMC assumes major-injury sims play U(0,8) games -> mean 4. Empirical mean above.")
