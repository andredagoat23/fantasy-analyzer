# Boom research: what situations precede boom seasons, how often, and how big.
# Boom (season) = mult >= 1.30 (beat market expectation by 30%+).
# Elite-boom = mult >= 1.60. All predictors are preseason-knowable (prev-season stats, age, capital).
import pandas as pd
import numpy as np

OUT = "icm/work/mc_research"
sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")
wk = pd.read_parquet(f"{OUT}/weekly.parquet")

pool = sea[(sea["mult"].notna()) & (sea["exp_pos_rank"] <= 60)].copy()
pool["boom"] = pool["mult"] >= 1.30
pool["boom_big"] = pool["mult"] >= 1.60
pool["bust"] = pool["mult"] <= 0.70

print(f"pool: {len(pool)} player-seasons (exp_pos_rank<=60, 2019-2025)")
print(f"base rates: boom(>=1.3x)={pool['boom'].mean():.1%}  big(>=1.6x)={pool['boom_big'].mean():.1%}  "
      f"bust(<=0.7x)={pool['bust'].mean():.1%}\n")

# ---------- 1. base rates by position x expectation tier ----------
pool["tier"] = pd.cut(pool["exp_pos_rank"], [0, 6, 12, 24, 40, 60],
                      labels=["1-6", "7-12", "13-24", "25-40", "41-60"])
t = pool.groupby(["position", "tier"], observed=True).agg(
    n=("boom", "size"), boom=("boom", "mean"), big=("boom_big", "mean"),
    bust=("bust", "mean"), mult_med=("mult", "median"),
    boom_size=("mult", lambda s: s[s >= 1.3].mean()))
print("=== base rates by position x preseason tier ===")
print(t.round(3).to_string(), "\n")

# ---------- 2. signal screen: boom rate in top vs bottom tercile of each preseason signal ----------
signals = {
    "age": "age", "years_exp": "years_exp", "draft_number": "draft_number",
    "prev_tgt_share": "prev_tgt_share", "prev_snap_pct": "prev_snap_pct",
    "prev_touches_pg": "prev_touches_pg", "prev_xfp_pg": "prev_xfp_pg",
    "prev_games_missed": "prev_games_missed", "prev_cv": "prev_cv",
    "prev_boom_rate": "prev_boom_rate",
    "prev_xfp_diff_pg": None,   # computed: prev (actual - expected) fantasy pts per game (TD luck)
    "implied_total_avg": "implied_total_avg",   # season vegas env (mild leakage - flag)
    "team_pass_pg": "team_pass_pg",
}
pool["prev_xfp_diff_pg"] = pool["prev_ppg"] - pool["prev_xfp_pg"]

print("=== signal screen: boom% top tercile vs bottom tercile (within position, n>=40) ===")
rows = []
for pos in ["QB", "RB", "WR", "TE"]:
    d = pool[pool["position"] == pos]
    for sig in signals:
        s = d[sig] if sig in d.columns else None
        if s is None or s.notna().sum() < 40:
            continue
        v = d[s.notna()]
        q1, q3 = s.quantile(1/3), s.quantile(2/3)
        lo, hi = v[v[sig] <= q1], v[v[sig] >= q3]
        if len(lo) < 15 or len(hi) < 15:
            continue
        rows.append({"pos": pos, "signal": sig, "n": len(v),
                     "boom_lo": lo["boom"].mean(), "boom_hi": hi["boom"].mean(),
                     "lift": hi["boom"].mean() - lo["boom"].mean(),
                     "mult_lo": lo["mult"].median(), "mult_hi": hi["mult"].median()})
scr = pd.DataFrame(rows).sort_values(["pos", "lift"])
print(scr.round(3).to_string(index=False), "\n")

# ---------- 3. age curve of the PER-GAME multiplier (does skill outcome shift with age?) ----------
print("=== mult_pg (per-game outcome vs expectation) by age bucket ===")
ab = pool.copy()
ab["age_b"] = pd.cut(ab["age"], [20, 23, 25, 27, 29, 31, 40],
                     labels=["<=23", "24-25", "26-27", "28-29", "30-31", "32+"])
t3 = ab.groupby(["position", "age_b"], observed=True).agg(
    n=("mult_pg", "size"), mult_pg_med=("mult_pg", "median"),
    boom=("boom", "mean"), bust=("bust", "mean"))
print(t3[t3.n >= 12].round(3).to_string(), "\n")

# ---------- 4. years-exp breakout curve (the "year-2 leap" myth check), WR/RB/TE ----------
print("=== boom rate by years_exp (year in league) ===")
ye = pool[pool["years_exp"].notna() & (pool["years_exp"] <= 9)]
t4 = ye.groupby(["position", "years_exp"], observed=True).agg(
    n=("boom", "size"), boom=("boom", "mean"), big=("boom_big", "mean"), mult_med=("mult", "median"))
print(t4[t4.n >= 12].round(3).to_string(), "\n")

# ---------- 5. team change: does a new team raise boom odds? ----------
pool["team_changed"] = (pool["team_last"] != pool["prev_team_last"]) & pool["prev_team_last"].notna()
t5 = pool[pool["prev_team_last"].notna()].groupby(["position", "team_changed"]).agg(
    n=("boom", "size"), boom=("boom", "mean"), bust=("bust", "mean"), mult_med=("mult", "median"))
print("=== team change effect ===")
print(t5.round(3).to_string(), "\n")

# ---------- 6. late-prev-season usage surge (last 4 played wks tgt_share vs season avg) ----------
wk_r = wk[wk["position"].isin(["WR", "TE", "RB"])].copy()
wk_r = wk_r.sort_values(["player_id", "season", "week"])
last4 = (wk_r.groupby(["player_id", "season"])
         .apply(lambda g: pd.Series({
             "ts_last4": g.tail(4)["target_share"].mean(),
             "ts_avg": g["target_share"].mean()}), include_groups=False)
         .reset_index())
last4["ts_surge"] = last4["ts_last4"] - last4["ts_avg"]
last4["join_season"] = last4["season"] + 1
pool = pool.merge(last4[["player_id", "join_season", "ts_surge", "ts_last4"]],
                  left_on=["player_id", "season"], right_on=["player_id", "join_season"], how="left")
d = pool[pool["position"].isin(["WR", "TE"]) & pool["ts_surge"].notna()]
q1, q3 = d["ts_surge"].quantile(1/3), d["ts_surge"].quantile(2/3)
print("=== WR/TE: prev-season late-usage surge (targets share, last-4 wks vs avg) ===")
print(f"  surge top-tercile boom%: {d[d.ts_surge >= q3]['boom'].mean():.1%} (n={len(d[d.ts_surge >= q3])})")
print(f"  surge bot-tercile boom%: {d[d.ts_surge <= q1]['boom'].mean():.1%} (n={len(d[d.ts_surge <= q1])})\n")

# ---------- 7. rookies: boom by draft capital (informs draft_tilt) ----------
rook = sea[(sea["years_exp"] == 0) & sea["mult"].notna() & (sea["exp_pos_rank"] <= 80)].copy()
rook["boom"] = rook["mult"] >= 1.30
rook["cap"] = pd.cut(rook["draft_number"], [0, 15, 32, 64, 105, 300],
                     labels=["top-15", "16-32", "2nd rd", "3rd rd", "4th+"])
t7 = rook.groupby("cap", observed=True).agg(n=("boom", "size"), boom=("boom", "mean"),
                                            mult_med=("mult", "median"), mult_p80=("mult", lambda s: s.quantile(.8)))
print("=== rookie mult by draft capital (vs market expectation) ===")
print(t7.round(3).to_string(), "\n")

# ---------- 8. weekly boom conditions: vegas + usage elasticity ----------
wkp = wk[wk["position"].isin(["QB", "RB", "WR", "TE"])].copy()
wkp = wkp[wkp["offense_pct"].fillna(0) >= 0.3]   # actually playing a real snap load
wkp["it_b"] = pd.cut(wkp["implied_total"], [0, 17, 20, 23, 26, 40],
                     labels=["<17", "17-20", "20-23", "23-26", "26+"])
t8 = wkp.groupby(["position", "it_b"], observed=True).agg(n=("is_boom", "size"), boom_wk=("is_boom", "mean"))
print("=== weekly boom rate by vegas implied team total ===")
print(t8[t8.n > 200].round(3).to_string())
