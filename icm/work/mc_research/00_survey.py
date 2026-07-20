# Survey what nflreadpy actually has for 2019-2025 — years, rows, key columns.
# Read-only recon so the research plan is built on data that exists.
import nflreadpy as nfl
import traceback

YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]

def probe(name, fn, seasons=True):
    print(f"\n=== {name} ===")
    try:
        df = (fn(seasons=YEARS) if seasons else fn()).to_pandas()
        print(f"rows={len(df)}  cols={len(df.columns)}")
        if "season" in df.columns:
            print("seasons:", sorted(df["season"].unique().tolist()))
        print("columns:", list(df.columns))
    except Exception as e:
        print("FAILED:", repr(e))
        # retry year-by-year to find which years exist
        ok = []
        for y in YEARS:
            try:
                d = fn(seasons=[y]).to_pandas()
                ok.append((y, len(d)))
            except Exception:
                pass
        print("per-year availability:", ok)

probe("player_stats (weekly)", nfl.load_player_stats)
probe("injuries", nfl.load_injuries)
probe("snap_counts", nfl.load_snap_counts)
probe("ff_opportunity", nfl.load_ff_opportunity)
probe("rosters (age/height/weight)", nfl.load_rosters)
probe("draft_picks", lambda seasons: nfl.load_draft_picks(seasons=list(range(2015, 2027))))
probe("schedules (vegas totals/lines)", nfl.load_schedules)
probe("depth_charts", nfl.load_depth_charts)
