"""Weekly snapshot job — capture every volatile input, dated and immutable, before it revises away.

Why this exists (charter icm/work/research-blueprint-prompt.md §9.2): the single most valuable asset
the research programme can build is a season of DATED snapshots, because a snapshot is the one thing
that cannot be reconstructed later — exactly the lesson of the permanently-unreconstructable
historical FantasyPros projections. And per WS3's revised-data bias ("in real time, a Week 3 snap
count is not what a Week 3 snap count looks like in the archive"), these snapshots are the ONLY
clean lead-time instrument this project will ever have: every historical lead-time claim stays
DIRECTIONAL until the 2026 live snapshots confirm it.

What one run captures, into data/snapshots/YYYY-MM-DD/ (all year round):
  schedules.csv     - 2026 schedule + Vegas total_line/spread_line AS KNOWABLE TODAY. S7's killer
                      leak was season-averaged Vegas totals; this is the cure — week-1..2 totals
                      frozen before the season reveals anything.
  espn_kona.csv     - ESPN ADP + ownership momentum (averageDraftPositionPercentChange,
                      percentOwned/Started) + ESPN's own projected component stats, one endpoint.
                      Same public kona_player_info request as load_espn_adp.py (reused read-only).
  ffc_adp.csv       - FantasyFootballCalculator 12-team PPR ADP with per-player stdev/high/low.
                      Browser User-Agent (plain urllib gets 403) + hard assert on player count so
                      a hollow response FAILS LOUDLY instead of silently writing a 5-row file.
  sleeper.csv       - Sleeper adp_ppr/adp_std/adp_half_ppr + projection components + the live
                      injury_status/injury_notes/news_updated/depth_chart fields, one row per player.
  fp_ecr.csv        - FantasyPros current draft ECR via nflreadpy load_ff_rankings("draft"): ecr,
                      sd, best, worst for every draft page (ppr-cheatsheets is the league's page;
                      dynasty pages ride along free as a situation-discounted talent contrast).
  depth_charts.csv  - load_depth_charts(2026), LATEST snapshot only (max dt) — the ESPN-sourced
                      daily depth chart, ~3.2k current rows.

Added IN SEASON (after week 1 completes; each is season-to-date so revisions to earlier weeks are
captured — the revision history IS the instrument):
  injuries.csv          - weekly report_status / practice_status designations
  snap_counts.csv       - PFR snap counts, offense_pct
  participation.parquet - offense_players / personnel / route per play (the pass-snap
                          participation source; parquet because of the id-string columns)
  fp_ecr_week.csv       - FantasyPros current WEEKLY rankings (the ex-ante start/sit consensus,
                          i.e. the manager-policy instrument for D1's ex-ante lineup grading)

Immutability contract: a dated dir with a MANIFEST.json is FINISHED and this script refuses to
touch it. A dated dir without a manifest is a crashed run: rerunning the same day RESUMES it —
existing files are never overwritten, only missing ones are fetched, and the manifest is written
last as the commit marker.

Fail-safety contract: every source is fetched independently; one source down cannot kill the
others. MANIFEST.json records, per source: ok, file, rows, bytes, seconds, fetched_at_utc, error,
and source-specific notes (drafts counted, scrape dates, status mixes...). Exit 0 = all captured;
exit 2 = snapshot written but at least one source failed (check the manifest); exit 1 = refused
or fatal.

Cadence (measured reasoning in icm/work/mc_research/results_61_snapshot_job.txt): run every
TUESDAY, season-round. In season, Tuesday sits after Monday Night Football (the completed week's
stats have landed in nflverse) and before Wednesday-morning waiver processing and the Wednesday
practice reports — so each snapshot is exactly the information set available at the week's
waiver/lineup decision, which is what the leakage rules in §9.2 require.

Run:  .venv/bin/python tools/weekly_snapshot.py
Test the in-season code path off-season (writes to /tmp-style dir, never data/snapshots):
      .venv/bin/python tools/weekly_snapshot.py --test-inseason 2025 --test-dir <dir>
"""
import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests

from utils import normalize_name

# nflreadpy: memory cache only — a SNAPSHOT job must never serve last week's disk cache as today's
# data. Env must be set before nflreadpy is imported (imports happen lazily inside fetchers).
os.environ["NFLREADPY_CACHE_MODE"] = "memory"
os.environ.setdefault("NFLREADPY_TIMEOUT", "120")

SEASON = 2026
SNAP_ROOT = os.path.join("data", "snapshots")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

ESPN_URL = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/players"
ESPN_POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}
# ESPN numeric stat ids -> canonical component names, as mapped in load_espn_projections.py
# (that file is a top-level pipeline script that runs on import, so the map is reproduced here
# read-only rather than imported; it is an id map, not a scoring constant).
ESPN_STAT = {"pass_att": "0", "pass_yds": "3", "pass_td": "4", "pass_int": "20",
             "rush_att": "23", "rush_yds": "24", "rush_td": "25",
             "rec": "53", "rec_yds": "42", "rec_td": "43",
             "fg_made": "83", "fg_att": "84", "pat_made": "86"}

# Sleeper projection stat keys -> canonical names (same map as tools/archive_projections.py)
SL_STAT = {"pass_yds": "pass_yd", "pass_td": "pass_td", "pass_int": "pass_int",
           "pass_att": "pass_att", "rush_yds": "rush_yd", "rush_td": "rush_td",
           "rush_att": "rush_att", "rec": "rec", "rec_yds": "rec_yd", "rec_td": "rec_td",
           "fumbles_lost": "fum_lost"}
SL_POS = {"QB", "RB", "WR", "TE", "K", "DEF"}

# slim column lists — intersected with whatever the source actually serves, so a schema change
# degrades to "missing column recorded in manifest" instead of a crash (S8: drift is expected)
SCHED_COLS = ["game_id", "season", "game_type", "week", "gameday", "weekday", "gametime",
              "away_team", "home_team", "away_score", "home_score", "result", "total",
              "overtime", "spread_line", "total_line", "away_moneyline", "home_moneyline",
              "roof", "surface", "away_qb_name", "home_qb_name", "away_coach", "home_coach",
              "stadium"]
DC_COLS = ["dt", "team", "player_name", "gsis_id", "espn_id", "pos_grp", "pos_abb",
           "pos_slot", "pos_rank"]
INJ_COLS = ["season", "season_type", "game_type", "team", "week", "gsis_id", "full_name",
            "first_name", "last_name", "position", "report_primary_injury",
            "report_secondary_injury", "report_status", "practice_primary_injury",
            "practice_secondary_injury", "practice_status", "date_modified"]
SNAP_COLS = ["game_id", "pfr_game_id", "season", "game_type", "week", "player",
             "pfr_player_id", "position", "team", "opponent", "offense_snaps", "offense_pct"]
PART_COLS = ["nflverse_game_id", "play_id", "possession_team", "offense_formation",
             "offense_personnel", "defense_personnel", "defenders_in_box", "n_offense",
             "n_defense", "route", "defense_coverage_type", "was_pressure", "time_to_throw",
             "offense_players"]

README = """# data/snapshots — the dated-snapshot archive

One directory per capture date (YYYY-MM-DD), written by `tools/weekly_snapshot.py`, run every
TUESDAY. Each directory is IMMUTABLE once its MANIFEST.json exists — the script refuses to touch
a finished snapshot, and nothing else should either.

Why: prices (ADP/ECR), depth charts, injury designations and usage data all revise or vanish.
A season of dated captures is the only clean lead-time instrument this project will ever have
(charter §9.2 / WS3 revised-data bias), and the one asset that cannot be rebuilt after the fact.
Read MANIFEST.json first: it records per source what succeeded, row counts, and timestamps.
Full file-by-file documentation is in the header of `tools/weekly_snapshot.py`; capture history
and cadence reasoning in `icm/work/mc_research/results_61_snapshot_job.txt`.

Commit these directories. Losing the laptop must not lose the season.
"""


def _nfl():
    import nflreadpy as nfl
    return nfl


def _slim(df, cols):
    keep = [c for c in cols if c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    return df[keep].copy(), missing


# ---------------------------------------------------------------- year-round fetchers
def fetch_schedules(season=SEASON):
    df = _nfl().load_schedules(seasons=[season]).to_pandas()
    out, missing = _slim(df, SCHED_COLS)
    assert len(out) > 200, f"schedules: only {len(out)} games — hollow response"
    notes = {"games": len(out),
             "total_line_populated": int(out["total_line"].notna().sum()) if "total_line" in out else None,
             "results_populated": int(out["result"].notna().sum()) if "result" in out else None,
             "missing_cols": missing}
    return out, notes


def fetch_espn_kona():
    filt = {"players": {"filterActive": {"value": True}, "limit": 5000,
                        "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
    hdr = {"X-Fantasy-Filter": json.dumps(filt), "X-Fantasy-Source": "kona",
           "Accept": "application/json", "User-Agent": UA}
    r = requests.get(ESPN_URL, params={"view": "kona_player_info", "scoringPeriodId": 0},
                     headers=hdr, timeout=60)
    r.raise_for_status()
    data = r.json()
    players = data["players"] if isinstance(data, dict) else data
    rows = []
    for p in players:
        pl = p.get("player", p)
        pos = ESPN_POS.get(pl.get("defaultPositionId"))
        name = pl.get("fullName")
        if not pos or not name:
            continue
        own = pl.get("ownership") or {}
        row = {"espn_id": pl.get("id"), "full_name": name, "position": pos,
               "pro_team_id": pl.get("proTeamId"),
               "adp": own.get("averageDraftPosition"),
               "adp_pct_change": own.get("averageDraftPositionPercentChange"),
               "pct_owned": own.get("percentOwned"), "pct_started": own.get("percentStarted")}
        proj = next((s for s in pl.get("stats", []) or []
                     if s.get("statSourceId") == 1 and s.get("seasonId") == SEASON
                     and s.get("statSplitTypeId") == 0), None)
        if proj:
            row["proj_total_espn_default"] = proj.get("appliedTotal")
            st = proj.get("stats", {}) or {}
            for canon, sid in ESPN_STAT.items():
                if sid in st:
                    row["proj_" + canon] = round(float(st[sid]), 3)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["nn"] = df["full_name"].map(normalize_name)
    n_adp = int(((pd.to_numeric(df["adp"], errors="coerce") > 0)).sum())
    assert n_adp > 300, f"kona: only {n_adp} players carry a positive ADP — hollow response"
    comp = [c for c in df.columns if c.startswith("proj_") and c != "proj_total_espn_default"]
    n_proj = int(df[comp].notna().any(axis=1).sum()) if comp else 0
    notes = {"players": len(df), "with_adp": n_adp,
             "with_projected_components": n_proj,
             # appliedTotal is ESPN-default-scoring points; ESPN serves it for few players —
             # the COMPONENT stats are the projection record (re-scorable under any rules)
             "with_applied_total": int(df["proj_total_espn_default"].notna().sum())
             if "proj_total_espn_default" in df else 0}
    return df, notes


def fetch_ffc():
    r = requests.get(
        f"https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year={SEASON}",
        headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    d = r.json()
    meta, players = d.get("meta", {}), d.get("players", [])
    # the charter's hard asserts (T0.2 pattern): a hollow response must RAISE, never write
    assert meta.get("total_drafts") is not None, "FFC: meta.total_drafts is null"
    assert len(players) > 100, f"FFC: only {len(players)} players — hollow response"
    df = pd.DataFrame(players)
    keep = [c for c in ("name", "position", "team", "adp", "high", "low", "stdev",
                        "times_drafted", "bye") if c in df.columns]
    df = df[keep]
    df["nn"] = df["name"].map(normalize_name)
    notes = {"players": len(df), "total_drafts": meta.get("total_drafts"),
             "window": f"{meta.get('start_date')}..{meta.get('end_date')}",
             "stdev_populated": int(df["stdev"].notna().sum()) if "stdev" in df else 0}
    return df, notes


def fetch_sleeper():
    proj = requests.get(f"https://api.sleeper.app/v1/projections/nfl/regular/{SEASON}",
                        timeout=90).json() or {}
    pls = requests.get("https://api.sleeper.app/v1/players/nfl", timeout=90).json()
    assert len(pls) > 5000, f"sleeper: universe only {len(pls)} players — hollow response"
    projmap = {pid: d for pid, d in proj.items() if isinstance(d, dict)}
    rows = []
    for pid, p in pls.items():
        pos, name = p.get("position"), p.get("full_name") or p.get("last_name")
        if pos not in SL_POS or not name:
            continue
        d = projmap.get(pid) or {}
        has_adp = d.get("adp_ppr") not in (None, "")
        if not p.get("team") and not has_adp:
            continue                       # neither rostered nor drafted anywhere — skip
        row = {"sleeper_id": pid, "full_name": name, "position": pos,
               "team": p.get("team"), "status": p.get("status"),
               "injury_status": p.get("injury_status"),
               "injury_body_part": p.get("injury_body_part"),
               "injury_start_date": p.get("injury_start_date"),
               "injury_notes": p.get("injury_notes"),
               "news_updated": p.get("news_updated"),
               "depth_chart_position": p.get("depth_chart_position"),
               "depth_chart_order": p.get("depth_chart_order"),
               "adp_ppr": d.get("adp_ppr"), "adp_std": d.get("adp_std"),
               "adp_half_ppr": d.get("adp_half_ppr"), "adp_2qb": d.get("adp_2qb"),
               "proj_pts_ppr": d.get("pts_ppr"), "proj_pts_std": d.get("pts_std")}
        for canon, key in SL_STAT.items():
            v = d.get(key)
            if v not in (None, ""):
                row["proj_" + canon] = float(v)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["nn"] = df["full_name"].map(normalize_name)
    adp_num = pd.to_numeric(df["adp_ppr"], errors="coerce")
    n_adp = int(adp_num.notna().sum())
    assert n_adp > 200, f"sleeper: only {n_adp} adp_ppr values — hollow projections payload"
    inj = df["injury_status"].fillna("").replace("", "none").value_counts().to_dict()
    notes = {"universe": len(pls), "kept": len(df), "with_adp_ppr": n_adp,
             # values are stored RAW; >=999 is Sleeper's undrafted sentinel (48_'s finding)
             "adp_ppr_below_999_sentinel": int((adp_num < 999).sum()),
             "injury_status_counts": inj}
    return df, notes


def fetch_fp_ecr():
    df = _nfl().load_ff_rankings("draft").to_pandas()
    for c in ("ecr", "sd", "best", "worst", "scrape_date", "fp_page"):
        assert c in df.columns, f"ff_rankings draft: column {c} missing — schema drift"
    scrape = str(df["scrape_date"].max())
    ppr = int((df["fp_page"] == "/nfl/rankings/ppr-cheatsheets.php").sum())
    assert ppr > 300, f"ff_rankings: ppr-cheatsheets page has only {ppr} players"
    stale = (datetime.date.today() - datetime.date.fromisoformat(scrape[:10])).days
    notes = {"rows": len(df), "pages": int(df["fp_page"].nunique()),
             "ppr_cheatsheet_rows": ppr, "scrape_date": scrape, "scrape_age_days": stale}
    if stale > 7:
        notes["warning"] = f"scrape_date is {stale} days old — FP mirror may have stopped updating"
    return df, notes


def fetch_depth_charts(season=SEASON):
    df = _nfl().load_depth_charts(seasons=[season]).to_pandas()
    assert "dt" in df.columns, "depth_charts: no dt column — wrong-era schema (charter §3.3.2)"
    latest = df["dt"].max()
    cur = df[df["dt"] == latest]
    out, missing = _slim(cur, DC_COLS)
    assert len(out) > 1000, f"depth_charts: latest snapshot has only {len(out)} rows"
    teams = int(out["team"].nunique()) if "team" in out else 0
    notes = {"latest_snapshot": str(latest), "rows": len(out), "teams": teams,
             "full_pull_rows": len(df), "missing_cols": missing}
    if teams != 32:
        notes["warning"] = f"expected 32 teams, got {teams}"
    return out, notes


# ---------------------------------------------------------------- in-season fetchers
# Each stores SEASON-TO-DATE, not just the completed week: next week's snapshot then captures any
# revision nflverse makes to earlier weeks, and diffing snapshot N vs N+1 measures the revised-data
# bias directly — that diff is unobtainable any other way.
def fetch_injuries(season=SEASON):
    df = _nfl().load_injuries(seasons=[season]).to_pandas()
    out, missing = _slim(df, INJ_COLS)
    assert len(out) > 0, "injuries: zero rows"
    wk = "week" if "week" in out else None
    notes = {"rows": len(out), "weeks": sorted(out[wk].unique().tolist()) if wk else None,
             "report_status_counts": out["report_status"].fillna("none").value_counts().to_dict()
             if "report_status" in out else None,
             "missing_cols": missing}
    return out, notes


def fetch_snap_counts(season=SEASON):
    df = _nfl().load_snap_counts(seasons=[season]).to_pandas()
    out, missing = _slim(df, SNAP_COLS)
    assert len(out) > 0, "snap_counts: zero rows"
    notes = {"rows": len(out),
             "weeks": sorted(out["week"].unique().tolist()) if "week" in out else None,
             "game_type_counts": out["game_type"].value_counts().to_dict()
             if "game_type" in out else None,
             "missing_cols": missing}
    return out, notes


def fetch_participation(season=SEASON):
    df = _nfl().load_participation(seasons=[season]).to_pandas()
    out, missing = _slim(df, PART_COLS)
    assert len(out) > 0, "participation: zero rows"
    # the charter-mandated non-empty test — NEVER .notna() on this file (§3.3.10)
    op = (out["offense_players"].fillna("").str.len() > 0).mean() if "offense_players" in out else None
    notes = {"rows": len(out),
             "offense_players_nonempty_rate": round(float(op), 4) if op is not None else None,
             "missing_cols": missing}
    return out, notes


def fetch_fp_week():
    df = _nfl().load_ff_rankings("week").to_pandas()
    assert len(df) > 0, "ff_rankings week: zero rows"
    scrape = str(df["scrape_date"].max()) if "scrape_date" in df else None
    notes = {"rows": len(df),
             "pages": int(df["fp_page"].nunique()) if "fp_page" in df else None,
             "scrape_date": scrape}
    if scrape:
        stale = (datetime.date.today() - datetime.date.fromisoformat(scrape[:10])).days
        notes["scrape_age_days"] = stale
        if stale > 7:
            notes["warning"] = (f"weekly scrape is {stale} days old — likely last season's "
                                "final week; the 2026 weekly mirror has not started yet")
    return df, notes


# ---------------------------------------------------------------- machinery
# 2026 week 1 ends Monday 2026-09-14 (read from the live schedule, snapshot 2026-07-31).
# Only used when the schedules source is down, so one dead source cannot kill the whole
# in-season block. Assumes each later week also ends on its Monday (conservative by <=1 day
# for Saturday-ending late-season weeks).
WK1_FINAL_GAMEDAY = datetime.date(2026, 9, 14)


def completed_week(sched):
    """Highest REG week whose games have ALL been played (every gameday before today)."""
    if sched is None or "week" not in sched or "gameday" not in sched:
        return None
    reg = sched[sched["game_type"] == "REG"] if "game_type" in sched else sched
    today = datetime.date.today().isoformat()
    done = [int(w) for w, d in reg.groupby("week")["gameday"].max().items()
            if str(d)[:10] < today]
    return max(done) if done else 0


def completed_week_fallback():
    days = (datetime.date.today() - WK1_FINAL_GAMEDAY).days
    if days < 1:
        return 0
    return min(18, (days - 1) // 7 + 1)


def _write(df, dest):
    tmp = dest + ".tmp"
    if dest.endswith(".parquet"):
        df.to_parquet(tmp, index=False)
    else:
        df.to_csv(tmp, index=False)
    os.replace(tmp, dest)                                    # atomic on POSIX


def _rows_on_disk(dest):
    if dest.endswith(".parquet"):
        return int(len(pd.read_parquet(dest)))
    with open(dest) as f:
        return sum(1 for _ in f) - 1


def run_source(manifest, snap_dir, name, filename, fn):
    """Fetch one source, fail-safe. Returns the DataFrame (or None on failure/resume-skip)."""
    dest = os.path.join(snap_dir, filename)
    rec = {"ok": False, "file": filename, "rows": None, "bytes": None, "seconds": None,
           "fetched_at_utc": None, "error": None, "notes": {}}
    df = None
    t0 = time.time()
    if os.path.exists(dest):                                 # resume of a crashed run
        rec.update(ok=True, rows=_rows_on_disk(dest), bytes=os.path.getsize(dest),
                   notes={"resumed": "file already existed; not re-fetched"})
        print(f"  {name:<16} RESUMED  {rec['rows']:>7} rows (already on disk)")
    else:
        try:
            df, notes = fn()
            _write(df, dest)
            rec.update(ok=True, rows=int(len(df)), bytes=os.path.getsize(dest), notes=notes,
                       fetched_at_utc=datetime.datetime.now(datetime.timezone.utc)
                       .isoformat(timespec="seconds"))
            print(f"  {name:<16} ok       {len(df):>7} rows  {time.time()-t0:5.1f}s")
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
            print(f"  {name:<16} FAILED   {rec['error']}")
        rec["seconds"] = round(time.time() - t0, 1)
    manifest["sources"][name] = rec
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--test-inseason", type=int, metavar="SEASON",
                    help="exercise the in-season fetchers against a past season, into --test-dir "
                         "(never touches data/snapshots)")
    ap.add_argument("--test-dir", default=None, help="output dir for --test-inseason")
    args = ap.parse_args()

    if args.test_inseason:
        yr = args.test_inseason
        out = args.test_dir or f"/tmp/weekly_snapshot_test_{yr}"
        os.makedirs(out, exist_ok=True)
        manifest = {"test_mode": True, "season": yr, "sources": {}}
        print(f"TEST MODE — in-season fetchers vs {yr}, writing to {out}")
        run_source(manifest, out, "injuries", "injuries.csv", lambda: fetch_injuries(yr))
        run_source(manifest, out, "snap_counts", "snap_counts.csv", lambda: fetch_snap_counts(yr))
        run_source(manifest, out, "participation", "participation.parquet",
                   lambda: fetch_participation(yr))
        run_source(manifest, out, "fp_ecr_week", "fp_ecr_week.csv", fetch_fp_week)
        with open(os.path.join(out, "MANIFEST.json"), "w") as f:
            json.dump(manifest, f, indent=2, default=str)
        bad = [k for k, v in manifest["sources"].items() if not v["ok"]]
        print(f"test manifest -> {out}/MANIFEST.json  ({'ALL OK' if not bad else 'FAILED: ' + ', '.join(bad)})")
        return 2 if bad else 0

    today = datetime.date.today().isoformat()
    snap_dir = os.path.join(SNAP_ROOT, today)
    if os.path.exists(os.path.join(snap_dir, "MANIFEST.json")):
        print(f"{snap_dir} already has a MANIFEST.json — that snapshot is FINISHED and immutable.")
        print("A snapshot you can silently redo is not a snapshot. Nothing was touched.")
        return 1
    resuming = os.path.isdir(snap_dir)
    os.makedirs(snap_dir, exist_ok=True)
    readme = os.path.join(SNAP_ROOT, "README.md")
    if not os.path.exists(readme):
        with open(readme, "w") as f:
            f.write(README)

    t0 = time.time()
    manifest = {"snapshot_date": today,
                "created_at_utc": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds"),
                "season": SEASON, "tool": "tools/weekly_snapshot.py", "sources": {}}
    print(f"weekly snapshot -> {snap_dir}" + ("  (RESUMING a crashed run)" if resuming else ""))

    # schedules first: cheap, and it decides the in-season block
    sched = run_source(manifest, snap_dir, "schedules", "schedules.csv", fetch_schedules)
    if sched is None and manifest["sources"]["schedules"]["ok"]:     # resumed from disk
        sched = pd.read_csv(os.path.join(snap_dir, "schedules.csv"))
    wk = completed_week(sched)
    manifest["week_source"] = "schedules"
    if wk is None:                       # schedules down — date arithmetic keeps the block alive
        wk = completed_week_fallback()
        manifest["week_source"] = "date_arithmetic_fallback (schedules source failed)"
    manifest["completed_week"] = wk
    manifest["phase"] = "preseason" if wk == 0 else "in_season"
    print(f"  phase: {manifest['phase']}" + (f" (completed week {wk})" if wk else ""))

    run_source(manifest, snap_dir, "espn_kona", "espn_kona.csv", fetch_espn_kona)
    run_source(manifest, snap_dir, "ffc_adp", "ffc_adp.csv", fetch_ffc)
    run_source(manifest, snap_dir, "sleeper", "sleeper.csv", fetch_sleeper)
    run_source(manifest, snap_dir, "fp_ecr", "fp_ecr.csv", fetch_fp_ecr)
    run_source(manifest, snap_dir, "depth_charts", "depth_charts.csv", fetch_depth_charts)

    if wk >= 1:
        run_source(manifest, snap_dir, "injuries", "injuries.csv", fetch_injuries)
        run_source(manifest, snap_dir, "snap_counts", "snap_counts.csv", fetch_snap_counts)
        run_source(manifest, snap_dir, "participation", "participation.parquet",
                   fetch_participation)
        run_source(manifest, snap_dir, "fp_ecr_week", "fp_ecr_week.csv", fetch_fp_week)
    else:
        manifest["in_season_block"] = "skipped — no completed regular-season week yet"

    manifest["total_seconds"] = round(time.time() - t0, 1)
    manifest["total_bytes"] = sum(v["bytes"] or 0 for v in manifest["sources"].values())
    with open(os.path.join(snap_dir, "MANIFEST.json"), "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    bad = [k for k, v in manifest["sources"].items() if not v["ok"]]
    n_ok = len(manifest["sources"]) - len(bad)
    print(f"\nMANIFEST.json written — {n_ok}/{len(manifest['sources'])} sources ok, "
          f"{manifest['total_bytes']/1e6:.1f} MB, {manifest['total_seconds']:.0f}s total.")
    if bad:
        print(f"FAILED sources (snapshot still valid for the rest): {', '.join(bad)}")
        print("A failed source stays failed for this date — the dir is now immutable. If it was")
        print("transient, the record of the outage is itself data; next Tuesday will capture it.")
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
