"""SINGLE SOURCE OF TRUTH for the league's scoring — edit values HERE only.

Three pipeline scripts import from this module so their scoring can never drift apart:
  - custom_scoring.py   (Bucket 1: base stat x value)                 -> SCORING
  - apply_bonuses.py    (Bucket 2: bonuses/estimates not in FP files) -> the bonus constants + K
  - compute_outcomes.py (the Monte-Carlo WEEKLY volatility proxy)     -> SCORING + FG distance

Verified line-by-line against the real ESPN league settings (L41). The MC weekly proxy DELIBERATELY
uses only the base scoring here (no Bucket-2 bonuses/sacks/fumbles) — it models volatility SHAPE, and
the MC mean re-centers on the full total_points; keeping bonuses out protects the 62.1% OOS calibration.
"""

# ---- Bucket 1: base stat scoring (custom_scoring.py) ----
SCORING = {
    "pass_yds": 0.04, "pass_td": 6, "pass_int": -2,
    "rush_yds": 0.1,  "rush_td": 6,
    "rec": 1, "rec_yds": 0.1, "rec_td": 6,
    "fumbles_lost": -2,
    "pat_made": 1, "fg_missed": -1,
}

# ---- FG made by distance (shared: apply_bonuses fg_ppm AND the compute_outcomes weekly proxy) ----
FG0, FG40, FG50, FG60 = 3, 4, 6, 7   # <40 / 40-49 / 50-59 / 60+  (ESPN ranges = mutually exclusive)

# ---- Bucket 2: bonuses / estimates (apply_bonuses.py) ----
# Long-TD bonuses are CUMULATIVE (ESPN "40+"/"50+": a 55-yд TD gets both). Big-game bonuses are TIERED
# (ESPN "300-399" vs "400+": a 420-yд game scores P400 only). See apply_bonuses.py section 4.
PTD40, PTD50 = 0.5, 1        # 40+/50+ passing TD (cumulative)
RETD40, RETD50 = 1, 2        # 40+/50+ receiving TD (cumulative)
RTD40, RTD50 = 2, 3          # 40+/50+ rushing TD (cumulative)
P300, P400 = 3, 5            # 300-399 / 400+ passing game (tiered)
RY100, RY200 = 3, 5          # 100-199 / 200+ rushing game (tiered)
REY100, REY200 = 2, 4        # 100-199 / 200+ receiving game (tiered)
RFD = REFD = 0.5             # rushing / receiving first down
SACK = -1                    # QB sacked (estimated)
TWOPT = 2                    # 2pt conversion (pass / rush / rec)
PATM = -1                    # PAT missed (estimated from league miss rate)
KR25, PR10, RETTD = 1, 1, 6  # return: 1 per 25 KR yд, 1 per 10 PR yд, 6 per return TD (backward-looking)

# empirical-Bayes shrinkage for per-player rates. MUST be > 0 — at K=0 a player with no historical TDs
# hits 0/0 and drops off the board. apply_bonuses.py clamps to >=1 defensively.
K = 12
