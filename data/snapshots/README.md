# data/snapshots — the dated-snapshot archive

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
