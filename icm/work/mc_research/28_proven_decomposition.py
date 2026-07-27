"""28 — Is "proven at price" a REAL signal, or just last year's injuries wearing a disguise?

26_'s strongest result was `proven_at_price` in the R4-6 band (+10.4pp, bootstrap P=0.97, 9/9 grid):
buy the guy whose LAST-season positional finish was at least as good as this season's positional
price. But a player coming off a torn ACL finishes terribly, so he automatically "fails" — which
means the condition could be silently re-measuring availability, something we already know is the
dominant driver AND is near-unpredictable. If so it's a proxy, not an insight, and it would double
count with the injury story.

The test: split the band by whether the player was HEALTHY last season (15+ games) and re-measure.
  - If the lift survives inside the healthy subgroup, "proven" carries real information beyond health.
  - If it collapses there, the condition is an injury detector and should be described as one.

Also reported: the 2x2 hit-rate table (proven x healthy), and the same decomposition for the R7-10
band, so we can see whether the answer is band-specific.

Run:  .venv/bin/python icm/work/mc_research/28_proven_decomposition.py
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, "seasons_exp.parquet")
OUT = os.path.join(HERE, "results_28_proven_decomp.txt")

NUM = ["adp", "adp_pos_rank", "mult", "games", "season", "prev_games", "prev_pos_rank_total",
       "prev_inj_weeks_out"]
N_BOOT = 2000
RNG = np.random.default_rng(0)

lines = []


def say(s=""):
    print(s)
    lines.append(s)


def load():
    p = pd.read_parquet(PANEL)
    for c in NUM:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    p = p[(p["adp"].notna()) & (p["season"] >= 2015)
          & p["position"].isin(["RB", "WR", "TE", "QB"])].copy()
    p["hit"] = (p["mult"] >= 1.0).astype(float)
    p["proven"] = (p["prev_pos_rank_total"].fillna(99) <= p["adp_pos_rank"].fillna(99)).astype(float)
    p["healthy"] = (p["prev_games"] >= 15).astype(float)
    return p


def lift_ci(sub):
    """Lift of `proven` on `hit` within sub, plus bootstrap P(lift>0)."""
    h, c = sub["hit"].to_numpy(), sub["proven"].to_numpy()
    t, f = c == 1, c == 0
    if t.sum() < 10 or f.sum() < 10:
        return np.nan, np.nan, int(t.sum()), int(f.sum())
    l0 = 100.0 * (h[t].mean() - h[f].mean())
    out = []
    n = len(h)
    for _ in range(N_BOOT):
        idx = RNG.integers(0, n, n)
        hh, cc = h[idx], c[idx]
        tt, ff = cc == 1, cc == 0
        if tt.sum() >= 5 and ff.sum() >= 5:
            out.append(100.0 * (hh[tt].mean() - hh[ff].mean()))
    p_gt = float((np.array(out) > 0).mean()) if len(out) >= 100 else np.nan
    return l0, p_gt, int(t.sum()), int(f.sum())


def decompose(p, lo, hi, label):
    band = p[(p["adp"] >= lo) & (p["adp"] <= hi)]
    say(f"\n{'=' * 76}\n{label} · n={len(band)}\n{'=' * 76}")
    l0, pg, nt, nf = lift_ci(band)
    say(f"whole band          : lift {l0:+.1f}pp  P(>0) {pg:.2f}   (n proven {nt} / not {nf})")

    healthy = band[band["healthy"] == 1]
    hurt = band[band["healthy"] == 0]
    lh, ph, nth, nfh = lift_ci(healthy)
    lu, pu, ntu, nfu = lift_ci(hurt)
    say(f"  HEALTHY last yr   : lift {lh:+.1f}pp  P(>0) {ph:.2f}   (n proven {nth} / not {nfh})"
        if not np.isnan(lh) else "  HEALTHY last yr   : too few")
    say(f"  MISSED time       : lift {lu:+.1f}pp  P(>0) {pu:.2f}   (n proven {ntu} / not {nfu})"
        if not np.isnan(lu) else "  MISSED time       : too few")

    say("\n  2x2 HIT rate:")
    say(f"  {'':<22}{'proven':>10}{'not proven':>13}")
    for hv, hl in ((1.0, "healthy last yr"), (0.0, "missed time")):
        row = f"  {hl:<22}"
        for pv in (1.0, 0.0):
            cell = band[(band["healthy"] == hv) & (band["proven"] == pv)]
            row += f"{(f'{cell.hit.mean():.0%} (n={len(cell)})'):>13}" if len(cell) >= 8 else f"{'—':>13}"
        say(row)

    # what does health ALONE buy in this band? (if health explains it, this should be large)
    hh = band[band["healthy"] == 1]["hit"].mean()
    hu = band[band["healthy"] == 0]["hit"].mean()
    say(f"\n  health alone      : healthy {hh:.1%} vs missed {hu:.1%} = {100 * (hh - hu):+.1f}pp")
    # Three genuinely different structures, and calling them all "proxy" would be sloppy:
    #   INDEPENDENT  — the lift survives with health held fixed, so it carries its own information.
    #   INTERACTION  — inert among healthy players, strong among those who missed time. That is NOT a
    #                  proxy; it's a CONDITIONAL prerequisite (it only applies to one kind of player),
    #                  which is exactly the shape the user hypothesised.
    #   PROXY/NOISE  — nothing survives in either subgroup.
    strong_h = not np.isnan(lh) and lh >= 6 and ph >= 0.85
    strong_u = not np.isnan(lu) and lu >= 10 and pu >= 0.85
    if strong_h and strong_u:
        v = "INDEPENDENT — holds in both subgroups"
    elif strong_h:
        v = "INDEPENDENT — survives with health held fixed"
    elif strong_u:
        v = ("CONDITIONAL — inert among healthy players, strong ONLY for players coming off a "
             "missed-time season (a prerequisite that applies to one profile, not everyone)")
    else:
        v = "NOISE/PROXY — nothing survives once health is held fixed"
    say(f"  verdict           : {v}")


def main():
    p = load()
    say("Question: does `proven_at_price` still predict once we hold LAST-YEAR HEALTH fixed?")
    say(f"panel n={len(p)} priced seasons 2015-2025 · bootstrap {N_BOOT} (seed 0)")
    decompose(p, 41, 75, "R4-6 (ADP 41-75) — where proven_at_price was ROBUST")
    decompose(p, 76, 125, "R7-10 (ADP 76-125)")
    decompose(p, 16, 40, "R2-3 (ADP 16-40)")
    decompose(p, 1, 15, "R1 (ADP 1-15) — where it was DEAD")
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
