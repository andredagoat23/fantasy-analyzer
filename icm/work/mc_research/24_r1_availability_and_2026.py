"""24 — (A) Is first-round AVAILABILITY predictable? (B) Apply the validated prereqs to the 2026 board.

23_ found the dominant fact: 81.5% of first-round busts missed 5+ games; only 7.4% played a full
season and merely underperformed. So the make-or-break prerequisite for an R1 pick is AVAILABILITY.
That makes the decisive question: can availability be forecast on draft day, or is it a tax?

Part A tests draft-day-knowable predictors of "played >= 15 games" on the same R1-priced population
(train 2015-2021 / holdout 2022-2025) — including the ones fantasy people assert constantly (he's
never been hurt / he's young / he's not overworked / big backs hold up).

Part B scores the ACTUAL 2026 first-round board on the prereqs that survived 23_+24_, and pairs each
player with his computed cohort comps, so the output is per-player and readable.

Run:  .venv/bin/python icm/work/mc_research/24_r1_availability_and_2026.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))          # icm/work/mc_research
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))   # repo root
sys.path.insert(0, ROOT)
from utils import normalize_name  # noqa: E402

PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_24_availability_2026.txt")
R1_ADP, TRAIN_END = 15, 2021

lines = []


def say(s=""):
    print(s)
    lines.append(s)


NUM = ["adp", "adp_pos_rank", "age", "mult", "games", "season", "draft_number", "prev_games",
       "prev_ended_early", "prev_inj_weeks_out", "prev_inj_weeks_listed", "prev_snap_pct",
       "prev_touches_pg", "prev_tgt_share", "prev_wopr", "prev_ppg", "prev_xfp_pg", "prev_weight",
       "prev_implied_total_avg", "prev_n_teams", "prev_cv", "prev_pos_rank_total", "years_exp",
       "prev_total_touches", "prev_games_missed", "pos_rank_total"]


def panel():
    p = pd.read_parquet(PANEL)
    for c in NUM:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")
    return p


def part_a(p):
    r1 = p[(p["adp"].notna()) & (p["adp"] <= R1_ADP) & (p["season"] >= 2015)
           & p["position"].isin(["RB", "WR", "TE", "QB"])].copy()
    r1["full"] = (r1["games"] >= 15).astype(float)
    say(f"\n{'=' * 78}\nPART A — is R1 AVAILABILITY predictable?  n={len(r1)}  "
        f"base P(15+ games) = {r1['full'].mean():.1%}\n{'=' * 78}")

    c = pd.DataFrame(index=r1.index)
    c["healthy_last_yr"] = r1["prev_games"] >= 16
    c["no_injury_hist"] = r1["prev_inj_weeks_out"].fillna(0) == 0
    c["didnt_end_early"] = r1["prev_ended_early"].fillna(0) == 0
    c["young"] = r1["age"] <= 25
    c["under_27"] = r1["age"] <= 26
    c["light_workload"] = r1["prev_total_touches"] < r1["prev_total_touches"].median()
    c["is_wr"] = r1["position"] == "WR"
    c["big_back"] = (r1["position"] == "RB") & (r1["prev_weight"].fillna(0) >= 215)
    c["low_exp"] = r1["years_exp"] <= 3
    c = c.astype(float)

    tr, ho = r1["season"] <= TRAIN_END, r1["season"] > TRAIN_END
    say(f"{'claim':<20}{'n_true':>7}{'P15|T':>8}{'P15|F':>8}{'lift':>7}   {'ho_n':>5}"
        f"{'ho|T':>7}{'ho|F':>7}{'ho_lift':>8}  verdict")
    for col in c.columns:
        t, f = c[col] == 1, c[col] == 0
        if t.sum() < 15 or f.sum() < 15:
            say(f"{col:<20}{int(t.sum()):>7}   (too few either way)")
            continue
        a, b = r1[t]["full"].mean(), r1[f]["full"].mean()
        a2, b2 = r1[t & ho]["full"].mean(), r1[f & ho]["full"].mean()
        lift, lift2 = 100 * (a - b), 100 * (a2 - b2)
        v = ("HOLDS" if lift >= 8 and lift2 >= 5 else
             "FAILS ho" if lift >= 8 else "no signal")
        say(f"{col:<20}{int(t.sum()):>7}{a:>8.1%}{b:>8.1%}{lift:>+6.1f}   "
            f"{int((t & ho).sum()):>5}{a2:>7.1%}{b2:>7.1%}{lift2:>+7.1f}  {v}")

    say("\nprior-year games -> P(15+ games this year), by bucket:")
    for lo, hi, lab in [(0, 10, "<=10 (hurt badly)"), (11, 14, "11-14 (some missed)"),
                        (15, 16, "15-16 (basically full)"), (17, 25, "17+ (iron man)")]:
        m = r1["prev_games"].between(lo, hi)
        if m.sum() >= 10:
            say(f"  prev {lab:<22} n={int(m.sum()):<4} P(15+) {r1[m]['full'].mean():.1%}  "
                f"HIT(mult>=1) {(r1[m]['mult'] >= 1).mean():.1%}")
    say(f"\n  correlation prev_games vs games: "
        f"{r1[['prev_games', 'games']].corr().iloc[0, 1]:+.3f}  (0 = last year tells you nothing)")
    say(f"  correlation age vs games:        {r1[['age', 'games']].corr().iloc[0, 1]:+.3f}")
    for pos in ("RB", "WR"):
        s = r1[r1["position"] == pos]
        say(f"  {pos}: P(15+ games) {s['full'].mean():.1%}   (n={len(s)})")
    return r1


def part_b(p):
    say(f"\n{'=' * 78}\nPART B — the 2026 first round scored on the surviving prerequisites\n{'=' * 78}")
    b = pd.read_csv(os.path.join(ROOT, "value_board.csv"))
    b["position"] = b["pos_label"].str.replace(r"\d+$", "", regex=True)
    b = b[b["adp_rank"].notna()].nsmallest(15, "adp_rank").copy()
    role = pd.read_csv(os.path.join(ROOT, "role_data.csv"))
    role["key"] = role["name"].map(normalize_name)
    rmap = role.set_index("key")
    # 2025 positional finish, from the panel itself (ground truth, not memory)
    p25 = p[p["season"] == 2025].copy()
    p25["key"] = p25["full_name_r"].fillna(p25["name_disp"]).astype(str).map(normalize_name)
    fin = p25.dropna(subset=["pos_rank_total"]).set_index("key")["pos_rank_total"]
    g25 = p25.dropna(subset=["games"]).set_index("key")["games"]
    try:
        co = pd.read_csv(os.path.join(ROOT, "cohort_data.csv"))
        co["key"] = co["full_name"].map(normalize_name) if "full_name" in co.columns else co.iloc[:, 0].map(normalize_name)
        co = co.set_index("key")
    except Exception:
        co = None

    say(f"{'player':<22}{'pos':<5}{'ADP':>5}{'age':>4}  {'earned?':<9}{'capital':<9}"
        f"{'role/proof':<13}{'2025 g':<7}met")
    rows = []
    for r in b.itertuples():
        key = normalize_name(r.full_name)
        rr = rmap.loc[key] if key in rmap.index else None
        pick = None
        if rr is not None and pd.notna(rr.get("nfl_pick")):
            pick = float(rr["nfl_pick"])
        elif pd.notna(getattr(r, "draft_pick", np.nan)):
            pick = float(r.draft_pick)
        earned = str(getattr(r, "regression", "")) != "TD-lucky"
        capital = pick is not None and pick <= 32
        pos_fin = fin.get(key)
        games25 = g25.get(key)
        if r.position == "WR":
            pos_adp = float(rr["pos_adp_rank"]) if rr is not None and pd.notna(rr.get("pos_adp_rank")) else np.nan
            proof = (pd.notna(pos_fin) and pd.notna(pos_adp) and pos_fin <= pos_adp)
            plab = (f"fin WR{int(pos_fin)}" if pd.notna(pos_fin) else "no 2025") + (" ✓" if proof else " ✗")
        else:
            ts = float(getattr(r, "target_share_2025", np.nan) or np.nan)
            proof = pd.notna(ts) and ts >= 0.10            # receiving-involved back (RB WOPR proxy)
            plab = (f"tgt {ts:.0%}" if pd.notna(ts) else "no tgt") + (" ✓" if proof else " ✗")
        met = int(earned) + int(capital) + int(proof)
        rows.append((r.full_name, r.position, met, earned, capital, proof))
        say(f"{r.full_name:<22}{r.pos_label:<5}{r.adp_rank:>5.1f}{int(r.age):>4}  "
            f"{('earned ✓' if earned else 'TD-LUCKY ✗'):<9}"
            f"{(f'#{int(pick)} ✓' if capital else (f'#{int(pick)} ✗' if pick else 'n/a ✗')):<9}"
            f"{plab:<13}{(f'{int(games25)}g' if pd.notna(games25) else '—'):<7}{met}/3")

    if co is not None:
        say("\ncohort comps (already computed by cohort_priors.py) for the top 8:")
        for r in b.head(8).itertuples():
            k = normalize_name(r.full_name)
            if k in co.index:
                c = co.loc[k]
                say(f"  {r.full_name:<20} boom {float(c.get('cohort_boom', np.nan)):.0%} / "
                    f"bust {float(c.get('cohort_bust', np.nan)):.0%} · med "
                    f"{c.get('cohort_med', '?')}x · comps: {str(c.get('cohort_comps', ''))[:78]}")
    return rows


def main():
    p = panel()
    part_a(p)
    part_b(p)
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
