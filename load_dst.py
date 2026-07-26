"""load_dst.py — score every team defense under the REAL ESPN D/ST tiers → data/dst_rankings.csv.

D/ST is a STREAMER (drafted in the last 2-3 rounds) and stays OFF the cross-position board (L9). This
just grounds the advisor's D/ST ranking (L36) in the actual ESPN scoring instead of a hand-typed list.

Method: score each defense's 2024-25 games under scoring_config's DST tiers (per-event points + the
per-game points-allowed and yards-allowed tiers, exactly as ESPN scores them weekly), average per game
(shrunk toward the league mean for small samples), x17 for a season, then a MODEST SOS tilt for the 2026
schedule (facing weaker offenses -> more D/ST points). BACKWARD-LOOKING by nature (2024-25 defense).

Run:  .venv/bin/python load_dst.py   (part of the pre-draft regen ritual; needs nflreadpy/network)
"""
import nflreadpy as nfl
import pandas as pd

from scoring_config import (DST_SACK, DST_INT, DST_FR, DST_SAFETY, DST_DEF_TD, DST_RET_TD,
                            DST_PA_TIERS, DST_YA_TIERS)

HIST = [2024, 2025]
GAMES = 17
PRIOR_W = 8          # shrinkage: games of league-average prior mixed into each team's per-game mean
SOS_MAX = 0.08       # cap the 2026 schedule tilt at +/-8%
NORM = {"LA": "LAR", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LAR"}   # -> advisor's team codes
norm = lambda t: NORM.get(t, t)


def tier(val, tiers):
    for ub, pts in tiers:
        if val <= ub:
            return pts
    return tiers[-1][1]


# --- historical team-game data ---
ts = nfl.load_team_stats(seasons=HIST).to_pandas()
ts = ts[ts["season_type"] == "REG"].copy()
ts["team"] = ts["team"].map(norm)
ts["opponent_team"] = ts["opponent_team"].map(norm)
ts["off_yards"] = ts["passing_yards"].fillna(0) + ts["rushing_yards"].fillna(0)

sched = nfl.load_schedules(seasons=HIST).to_pandas()
sched = sched[sched["game_type"] == "REG"]
pf = {}   # (season, week, team) -> points that team SCORED (= points the opponent's D/ST allowed)
for _, gm in sched.iterrows():
    pf[(gm["season"], gm["week"], norm(gm["home_team"]))] = gm["home_score"]
    pf[(gm["season"], gm["week"], norm(gm["away_team"]))] = gm["away_score"]
yf = {(r.season, r.week, r.team): r.off_yards for r in ts.itertuples()}   # team -> yards it gained

# --- score each defense's individual games ---
rows = []
for r in ts.itertuples():
    pa = pf.get((r.season, r.week, r.opponent_team))       # points the opponent scored
    ya = yf.get((r.season, r.week, r.opponent_team))       # yards the opponent gained
    if pa is None or ya is None:
        continue
    events = (r.def_sacks * DST_SACK + r.def_interceptions * DST_INT + r.fumble_recovery_opp * DST_FR
              + r.def_safeties * DST_SAFETY + r.def_tds * DST_DEF_TD + r.special_teams_tds * DST_RET_TD)
    rows.append({"team": r.team, "pts": events + tier(pa, DST_PA_TIERS) + tier(ya, DST_YA_TIERS)})
gg = pd.DataFrame(rows).groupby("team")["pts"].agg(mean="mean", n="count")
league = gg["mean"].mean()
gg["ppg"] = (gg["mean"] * gg["n"] + league * PRIOR_W) / (gg["n"] + PRIOR_W)   # shrink small samples

# --- offensive PPG (2024-25) for the SOS tilt ---
off = pd.Series(pf).groupby(level=2).mean()   # team -> points scored per game

# --- 2026 schedule -> each team's avg opponent offensive PPG (weaker opp offense = more D/ST points) ---
s26 = nfl.load_schedules(seasons=[2026]).to_pandas()
s26 = s26[s26["game_type"] == "REG"]
opp_ppg = {}
for _, gm in s26.iterrows():
    h, a = norm(gm["home_team"]), norm(gm["away_team"])
    opp_ppg.setdefault(h, []).append(off.get(a))
    opp_ppg.setdefault(a, []).append(off.get(h))
sos = {t: pd.Series([x for x in v if pd.notna(x)]).mean() for t, v in opp_ppg.items()}
lg = pd.Series(sos).mean()
sos_factor = {t: 1 + max(-SOS_MAX, min(SOS_MAX, (lg - s) / lg)) for t, s in sos.items()}

# --- season projection + SOS tilt ---
out = gg.reset_index()
out["sos_opp_ppg"] = out["team"].map(sos).round(1)
out["proj"] = (out["ppg"] * GAMES * out["team"].map(sos_factor).fillna(1.0)).round(1)
out = out.sort_values("proj", ascending=False).reset_index(drop=True)
out["rank"] = out.index + 1
out["tier"] = [min(i // 4 + 1, 5) for i in range(len(out))]     # T1 = top 4, T2 next 4, ...
out = out[["rank", "team", "tier", "proj", "sos_opp_ppg"]].head(20)

hdr = ("# 2026 D/ST draft rankings — SCORED under the real ESPN tiers (load_dst.py, 2024-25 defense,\n"
       "# shrunk + 2026-SOS-tilted). D/ST is a streamer: draft one in your last 2-3 rounds. Regenerate\n"
       "# with `.venv/bin/python load_dst.py`. proj = projected season D/ST points; sos_opp_ppg = avg\n"
       "# 2026 opponent offensive PPG (lower = easier schedule).\n")
with open("data/dst_rankings.csv", "w") as f:
    f.write(hdr)
    out.to_csv(f, index=False)

print(f"wrote data/dst_rankings.csv ({len(out)} teams). league avg D/ST ppg={league:.1f}")
print(out.to_string(index=False))
