# Injury research v2 - STARTER pools only, so "missed game" ~ injury, not benching.
# (QB33-60 are backups; their absences are depth-chart artifacts. Starter cut fixes it.)
# Starter pools: QB<=18, RB<=36, WR<=42, TE<=14 preseason positional rank.
import pandas as pd
import numpy as np

OUT = "icm/work/mc_research"
sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")
wk = pd.read_parquet(f"{OUT}/weekly.parquet")

CUT = {"QB": 18, "RB": 36, "WR": 42, "TE": 14}
pool = sea[sea["exp_pos_rank"].notna()].copy()
pool = pool[pool.apply(lambda r: r["exp_pos_rank"] <= CUT[r["position"]], axis=1)]
pool["big_miss"] = pool["games_missed"] >= 4
pool["catastrophic"] = pool["games_missed"] >= 9

print(f"starter pool: {len(pool)} player-seasons "
      f"({dict(pool.groupby('position').size())})\n")

# ---------- 1. base rates (the MC constants check) ----------
t1 = pool.groupby("position").agg(
    n=("games", "size"), games_mean=("games", "mean"), played_frac=("games_frac", "mean"),
    miss4=("big_miss", "mean"), miss9=("catastrophic", "mean"), missed_med=("games_missed", "median"))
print("=== STARTER availability base rates ===")
print(t1.round(3).to_string())
print("MC AVAIL_PRIOR: RB .86  WR .92  TE .91  QB .94 | MC p_major floor .06 cap .30\n")

# ---------- 2. age curve (starters) ----------
ab = pool.copy()
ab["age_b"] = pd.cut(ab["age"], [20, 23, 25, 27, 29, 31, 40],
                     labels=["<=23", "24-25", "26-27", "28-29", "30-31", "32+"])
t3 = ab.groupby(["position", "age_b"], observed=True).agg(
    n=("big_miss", "size"), played=("games_frac", "mean"), miss4=("big_miss", "mean"),
    miss9=("catastrophic", "mean"), mult_pg_med=("mult_pg", "median"))
print("=== age x availability + per-game outcome (starters) ===")
print(t3[t3.n >= 10].round(3).to_string(), "\n")

# ---------- 3. recurrence (starters) ----------
r = pool[pool["prev_games_missed"].notna()].copy()
r["prev_b"] = pd.cut(r["prev_games_missed"], [-1, 0, 2, 5, 20], labels=["0", "1-2", "3-5", "6+"])
t4 = r.groupby(["position", "prev_b"], observed=True).agg(
    n=("big_miss", "size"), played=("games_frac", "mean"), miss4=("big_miss", "mean"),
    miss9=("catastrophic", "mean"))
print("=== recurrence: availability by LAST season's games missed (starters) ===")
print(t4[t4.n >= 10].round(3).to_string(), "\n")
r["prev_inj3"] = r["prev_games_missed"] >= 3
t4b = r.groupby("prev_inj3").agg(n=("big_miss", "size"), miss4=("big_miss", "mean"),
                                 miss9=("catastrophic", "mean"), played=("games_frac", "mean"))
print(t4b.round(3).to_string(), "\n")

# ---------- 4. injury types from the injuries dataset (played-weeks panel lacks Out weeks) ----------
import glob
# local parquets; pre-2025 files lack season_type - filter on game_type instead
inj = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{OUT}/raw/injuries_*.parquet"))])
inj = inj[inj["game_type"] == "REG"].copy()
inj["season"] = inj["season"].astype(int)
inj_w = inj[inj["report_status"].isin(["Out", "Doubtful"]) & inj["report_primary_injury"].notna()]
inj_w = inj_w.rename(columns={"gsis_id": "player_id"})
# player-seasons in starter pool only
keys = set(zip(pool["player_id"], pool["season"]))
inj_w = inj_w[[k in keys for k in zip(inj_w["player_id"], inj_w["season"])]]
by_type = inj_w.groupby("report_primary_injury").size().sort_values(ascending=False)
print("=== Out/Doubtful player-weeks by body part (starters; note: IR often unlisted) ===")
print(by_type.head(14).to_string(), "\n")

# type -> NEXT season: recurrence & availability. Use each player-season's modal Out injury.
modal = (inj_w.groupby(["player_id", "season"])["report_primary_injury"]
         .agg(lambda s: s.value_counts().index[0]).reset_index()
         .rename(columns={"report_primary_injury": "inj_type"}))
modal["join_season"] = modal["season"] + 1
nxt = pool.merge(modal[["player_id", "join_season", "inj_type"]],
                 left_on=["player_id", "season"], right_on=["player_id", "join_season"], how="inner")
grp = nxt.groupby("inj_type").agg(n=("big_miss", "size"), miss4=("big_miss", "mean"),
                                  played=("games_frac", "mean"))
grp = grp[grp["n"] >= 15].sort_values("miss4", ascending=False)
base_miss4 = pool["big_miss"].mean()
print(f"=== NEXT-season miss4 by prior-year primary injury type (baseline={base_miss4:.3f}) ===")
print(grp.round(3).to_string(), "\n")

# soft tissue vs structural recurrence
SOFT = ["Hamstring", "Groin", "Calf", "Quadricep", "Quad", "Hip"]
STRUCT = ["Knee", "Ankle", "Foot", "Shoulder", "Back"]
nxt["cls"] = np.where(nxt["inj_type"].isin(SOFT), "soft",
              np.where(nxt["inj_type"].isin(STRUCT), "structural", "other"))
print(nxt.groupby("cls").agg(n=("big_miss", "size"), miss4=("big_miss", "mean"),
                             played=("games_frac", "mean")).round(3).to_string(), "\n")

# ---------- 5. devastation (starters): games x per-game correlation ----------
bm = pool[pool["mult"].notna() & pool["mult_pg"].notna()]
print("=== per-game outcome vs games missed (starters) - the correlation MC ignores ===")
mb = bm.copy()
mb["miss_b"] = pd.cut(mb["games_missed"], [-1, 0, 3, 8, 20], labels=["0", "1-3", "4-8", "9+"])
t5 = mb.groupby(["position", "miss_b"], observed=True).agg(
    n=("mult_pg", "size"), mult_pg_med=("mult_pg", "median"))
print(t5[t5.n >= 10].round(3).to_string(), "\n")
corr = bm[["games_frac", "mult_pg"]].corr().iloc[0, 1]
print(f"corr(games_frac, per-game mult) = {corr:.3f}  (MC sims these independently)\n")

# ---------- 6. catastrophic sims: games played when 9+ missed ----------
cat = pool[pool["catastrophic"]]
print("=== catastrophic (9+ missed) starters: games played ===")
print(cat["games"].describe().round(1).to_string())
print(f"\nempirical P(catastrophic) by pos: "
      f"{ {p: round(g['catastrophic'].mean(), 3) for p, g in pool.groupby('position')} }")
print("MC p_major: 6% (healthy) to 30% (fragile), U(0,8) games -> mean 4")
