"""Regenerate the whole pipeline end to end. Run with the venv python:
    .venv/bin/python run_all.py
Each step is a separate script; if any fails, we stop so you don't build on bad data."""
import subprocess
import sys
import time

STEPS = [
    "players.py",               # Sleeper API      -> players.csv
    "filter_active.py",         # active + rookies -> players_active.csv
    "load_player_stats.py",     # 24/25 stats      -> players_with_stats.csv
    "load_fp_adp.py",           # FantasyPros ADP  -> players_with_adp.csv
    "load_ecr.py",              # FantasyPros ECR  -> players_with_ecr.csv
    "load_fp_projections.py",   # projections      -> players_with_projections.csv
    "custom_scoring.py",        # Bucket 1 scoring -> players_scored.csv
    "apply_bonuses.py",         # Bucket 2 bonuses -> players_final.csv
    "blend_vegas.py",           # blend Vegas proj -> players_final.csv (overwrites total_points)
    "compute_metrics.py",       # VOLS             -> players_with_metrics.csv
    "compute_outcomes.py",      # risk + sims      -> players_with_outcomes.csv
    "value_board.py",           # final board      -> value_board.csv + app_data.*
]

def main():
    start = time.time()
    for i, script in enumerate(STEPS, 1):
        print(f"\n{'='*60}\n[{i}/{len(STEPS)}] running {script}\n{'='*60}", flush=True)
        t0 = time.time()
        if subprocess.run([sys.executable, script]).returncode != 0:
            print(f"\n[FAILED] {script} (step {i}) after {time.time()-t0:.0f}s -- stopping.")
            sys.exit(1)
        print(f"[ok] {script} in {time.time()-t0:.0f}s")
    print(f"\n[DONE] all {len(STEPS)} steps in {time.time()-start:.0f}s "
          f"-> value_board.csv, app_data.csv, app_data.json ready")

if __name__ == "__main__":
    main()
