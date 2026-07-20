# Cross-positional dependencies: does the quality of your TEAMMATES move your outcome vs price?
#   (a) QB quality  -> WR/TE outcomes      (b) OL quality -> RB/QB outcomes
#   (c) receiver-corps quality -> QB outcomes
# mult is measured VS PRICE, so tercile spreads = market MISPRICING, not the obvious effect.
# Features are preseason-knowable analogs: the team's primary QB's own PRIOR-season efficiency
# (wherever he played - handles QB moves), the team's prior-season OL proxies, and the current
# receivers' prior-season production.
import pandas as pd
import numpy as np

OUT = "icm/work/mc_research"
wk = pd.read_parquet(f"{OUT}/weekly.parquet")
sea = pd.read_parquet(f"{OUT}/seasons_exp.parquet")

# ---------- team-season building blocks ----------
qb = wk[wk.position == "QB"].copy()
qb["dropbacks"] = qb["attempts"].fillna(0) + qb.get("sacks_suffered", 0).fillna(0)
qb_seas = qb.groupby(["player_id", "season"]).agg(
    att=("attempts", "sum"), epa=("passing_epa", "sum"), db=("dropbacks", "sum"),
    qb_ppg=("pts", "mean"), team_last=("team", "last")).reset_index()
qb_seas["epa_db"] = qb_seas["epa"] / qb_seas["db"].replace(0, np.nan)

# primary QB per team-season (most attempts) + THAT QB's prior-season efficiency anywhere
prim = (qb.groupby(["season", "team", "player_id"])["attempts"].sum().reset_index()
          .sort_values("attempts", ascending=False).drop_duplicates(["season", "team"]))
qb_prev = qb_seas[["player_id", "season", "epa_db", "qb_ppg"]].copy()
qb_prev["join_season"] = qb_prev["season"] + 1
prim = prim.merge(qb_prev[["player_id", "join_season", "epa_db", "qb_ppg"]],
                  left_on=["player_id", "season"], right_on=["player_id", "join_season"], how="left")
prim = prim.rename(columns={"epa_db": "qb_prev_epa", "qb_ppg": "qb_prev_ppg"})[
    ["season", "team", "qb_prev_epa", "qb_prev_ppg"]]

# OL proxies per team-season (then lag 1yr): sack rate allowed + team rush ypc
tm = wk.groupby(["season", "team"]).agg(
    att=("attempts", "sum"), sk=("sacks_suffered", "sum"),
    ry=("rushing_yards", "sum"), ca=("carries", "sum")).reset_index()
tm["sack_rate"] = tm["sk"] / (tm["att"] + tm["sk"]).replace(0, np.nan)
tm["ypc"] = tm["ry"] / tm["ca"].replace(0, np.nan)
ol = tm[["season", "team", "sack_rate", "ypc"]].copy()
ol["join_season"] = ol["season"] + 1
ol = ol.rename(columns={"sack_rate": "ol_prev_sackrate", "ypc": "ol_prev_ypc"})[
    ["team", "join_season", "ol_prev_sackrate", "ol_prev_ypc"]]

# receiver-corps quality: current team's receivers' PRIOR-season receiving ppg, top-2 sum
rec = wk[wk.position.isin(["WR", "TE"])].copy()
rec["rec_pts"] = rec["receptions"] + rec["receiving_yards"] * .1 + rec["receiving_tds"] * 6
rec_seas = rec.groupby(["player_id", "season"]).agg(rp=("rec_pts", "mean")).reset_index()
rec_seas["join_season"] = rec_seas["season"] + 1
roster_now = rec.groupby(["season", "team", "player_id"]).size().reset_index()[["season", "team", "player_id"]]
roster_now = roster_now.merge(rec_seas[["player_id", "join_season", "rp"]],
                              left_on=["player_id", "season"], right_on=["player_id", "join_season"], how="left")
corps = (roster_now.sort_values("rp", ascending=False).groupby(["season", "team"])
         .head(2).groupby(["season", "team"])["rp"].sum().reset_index()
         .rename(columns={"rp": "corps_prev_top2"}))

# ---------- join to the priced pool ----------
pool = sea[sea.mult.notna() & (sea.exp_pos_rank <= 60)].copy()
pool = pool.merge(prim, left_on=["season", "team_last"], right_on=["season", "team"], how="left")
pool = pool.merge(ol, left_on=["team_last", "season"], right_on=["team", "join_season"], how="left")
pool = pool.merge(corps, left_on=["season", "team_last"], right_on=["season", "team"], how="left")

def terciles(d, col, label, outcomes=("mult",)):
    d = d[d[col].notna()]
    if len(d) < 60:
        print(f"  {label}: n={len(d)} thin"); return
    q1, q2 = d[col].quantile(1/3), d[col].quantile(2/3)
    for name, seg in [("bottom", d[d[col] <= q1]), ("middle", d[(d[col] > q1) & (d[col] < q2)]),
                      ("top", d[d[col] >= q2])]:
        print(f"  {label} {name:6} n={len(seg):4}  boom {(seg['mult']>=1.3).mean():.0%}  "
              f"bust {(seg['mult']<=0.7).mean():.0%}  med {seg['mult'].median():.2f}  "
              f"med/gm {seg['mult_pg'].median():.2f}")
    print()

print("=== (a) QB quality (primary QB's prior-season EPA/dropback) -> WR/TE vs price ===")
terciles(pool[pool.position.isin(["WR", "TE"])], "qb_prev_epa", "WR/TE by QB quality")
terciles(pool[pool.position == "WR"], "qb_prev_epa", "WR only")
terciles(pool[pool.position == "TE"], "qb_prev_epa", "TE only")

print("=== (b) OL quality -> RB and QB vs price ===")
terciles(pool[pool.position == "RB"], "ol_prev_ypc", "RB by prior team YPC")
terciles(pool[pool.position == "RB"], "ol_prev_sackrate", "RB by prior sack rate (inverse OL)")
terciles(pool[pool.position == "QB"], "ol_prev_sackrate", "QB by prior sack rate")

print("=== (c) receiver-corps quality -> QB vs price ===")
terciles(pool[pool.position == "QB"], "corps_prev_top2", "QB by corps top-2 prior ppg")

# save the enriched pool for the cohort matcher
pool.to_parquet(f"{OUT}/pool_crosspos.parquet", index=False)
print(f"saved enriched pool: {len(pool)} rows")
