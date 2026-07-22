"""L32 — cohort sanity-pull on the board's composite rank.

cohort_trimmed (from cohort_priors.py; a LOSO-validated finish/price multiplier — >1.0 means the
player's 15 nearest historical comps BEAT his draft price) has only ever fed the advisor's PROSE.
Here we let it nudge the board rank itself (rank_composite, which also seeds the advisor's TOP PICKS
shortlist). It is a BOUNDED sanity-pull, never a re-rank:
  - trimmed (not median) dodges the cheap-backup finish/price blow-up (L29).
  - deadband: ignore near-fair cohorts so the ~1.0 crowd doesn't jitter.
  - cap: no player can move more than CAP spots.
  - startable gate: only LIFT players already startable; a bench/handcuff's contingent value is the
    DART/HANDCUFF read's job, not the standalone board rank (avoids double-counting).
  - freeze: leave the consensus top (efficient; we already agree with the field there).
Missing/unreadable cohort_data.csv, or a player with no name-match, is a no-op (feature off, no crash).

Kept as a pure, Streamlit-free module so it's unit-testable; draft.py imports apply_pull() inside its
cached load_board().
"""
import pandas as pd

# knobs — see the L32 note; tuned via a sensitivity sweep (icm/work/, Jul 21 2026)
SCALE, DEAD, CAP, GATE, FREEZE = 30.0, 0.08, 4, 0.40, 8


def nudge(board, trimmed, scale=SCALE, dead=DEAD, cap=CAP, gate=GATE, freeze=FREEZE):
    """Pure core. board needs columns full_name, rank_composite, p_startable; `trimmed` is a
    full_name -> cohort_trimmed Series (unique index). Returns a rank-nudge Series (index-aligned to
    board): NEGATIVE moves a player UP (comps beat his price), POSITIVE moves him DOWN."""
    dev = (board["full_name"].map(trimmed) - 1.0)               # + = beats price -> move UP
    dev = dev.where(dev.abs() >= dead, 0.0).fillna(0.0)         # deadband + no name-match -> no-op
    n = (-scale * dev).clip(-cap, cap)
    n = n.mask((n < 0) & (board["p_startable"] < gate), 0.0)    # don't LIFT a bench/handcuff (DART owns it)
    n = n.mask(board["rank_composite"] <= freeze, 0.0)          # leave the efficient top alone
    return n


def apply_pull(board, path="cohort_data.csv", **knobs):
    """Read cohort_data.csv and return a COPY of board with rank_composite cohort-adjusted (the raw
    rank is preserved as rank_composite_base). Missing/unreadable CSV => board returned unchanged."""
    try:
        trimmed = (pd.read_csv(path).drop_duplicates("full_name")
                   .set_index("full_name")["cohort_trimmed"])
    except Exception:
        return board
    n = nudge(board, trimmed, **knobs)
    board = board.copy()
    board["rank_composite_base"] = board["rank_composite"]
    board["rank_composite"] = (board["rank_composite"] + n).rank(method="min").astype(int)
    return board
