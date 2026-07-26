"""Projection source layer — the ONE place the scorers get per-player component stats.

Blends FantasyPros (the 5 data/FantasyPros_*.csv files) with ESPN's own projections
(data/espn_projections.csv, from load_espn_projections.py) at the COMPONENT-STAT level, weighted by
scoring_config.PROJ_W_FP / PROJ_W_ESPN. Because the scoring is LINEAR in these volumes, blending the
components then scoring == scoring each source then averaging. custom_scoring.py + apply_bonuses.py both
call blended_components(), so there is ONE projection definition (mirrors scoring_config for scoring).

Guarantees:
  - FP-ONLY mode (PROJ_W_ESPN=0, or no ESPN file) returns the FP components verbatim → byte-identical to
    the pre-consensus pipeline.
  - a component ESPN doesn't provide (e.g. fumbles_lost) always uses FP.
  - a player in only ONE source uses that source at full weight.
"""
import glob
import re

import pandas as pd

from utils import normalize_name
from scoring_config import PROJ_W_FP, PROJ_W_ESPN

# canonical component stats every downstream scorer reads
COMPONENTS = ["pass_yds", "pass_td", "pass_int", "pass_att", "rush_yds", "rush_td", "rush_att",
              "rec", "rec_yds", "rec_td", "fumbles_lost", "fg_made", "fg_att", "pat_made"]

# FP per-position column maps (UNION of custom_scoring + apply_bonuses POS_MAPs, so one parse serves both)
_FP_MAP = {
    "QB": {"pass_yds": "YDS", "pass_td": "TDS", "pass_int": "INTS", "pass_att": "ATT",
           "rush_yds": "YDS.1", "rush_td": "TDS.1", "rush_att": "ATT.1", "fumbles_lost": "FL"},
    "RB": {"rush_yds": "YDS", "rush_td": "TDS", "rush_att": "ATT", "rec": "REC",
           "rec_yds": "YDS.1", "rec_td": "TDS.1", "fumbles_lost": "FL"},
    "WR": {"rec": "REC", "rec_yds": "YDS", "rec_td": "TDS", "rush_yds": "YDS.1", "rush_td": "TDS.1",
           "rush_att": "ATT", "fumbles_lost": "FL"},
    "TE": {"rec": "REC", "rec_yds": "YDS", "rec_td": "TDS", "fumbles_lost": "FL"},
    "K":  {"fg_made": "FG", "fg_att": "FGA", "pat_made": "XPT"},
}
_to_num = lambda s: pd.to_numeric(s.astype(str).str.replace(",", ""), errors="coerce").fillna(0)


def _fp_components():
    frames = []
    for f in sorted(glob.glob("data/FantasyPros_Fantasy_Football_Projections_*.csv")):
        pos = re.search(r"_([A-Z]+)\.csv$", f).group(1)
        df = pd.read_csv(f)
        df = df[df["Player"].notna() & (df["Player"].str.strip() != "")].copy()
        d = {c: (_to_num(df[_FP_MAP[pos][c]]) if c in _FP_MAP[pos] else 0.0) for c in COMPONENTS}
        d["full_name"] = df["Player"].values
        d["position"] = pos
        frames.append(pd.DataFrame(d))
    fp = pd.concat(frames, ignore_index=True)
    fp["norm_name"] = fp["full_name"].apply(normalize_name)
    return fp


def _espn_components():
    try:
        e = pd.read_csv("data/espn_projections.csv")
    except Exception:
        return None, []
    provides = [c for c in COMPONENTS if c in e.columns]   # which stats ESPN actually carries
    e["norm_name"] = e["full_name"].apply(normalize_name)
    return e, provides


def _proxy(df, sfx=""):
    """A rough standard-fantasy-point proxy from components, for the divergence flag only."""
    g = lambda c: df[c + sfx].fillna(0)
    return (g("pass_yds") * .04 + g("pass_td") * 4 + g("rush_yds") * .1 + g("rush_td") * 6
            + g("rec") + g("rec_yds") * .1 + g("rec_td") * 6)


def blended_components(w_fp=PROJ_W_FP, w_espn=PROJ_W_ESPN):
    """Per-(norm_name, position) canonical components, FP+ESPN blended, + a proj_divergence column."""
    fp = _fp_components()
    espn, provides = (None, []) if w_espn == 0 else _espn_components()
    cols = ["full_name", "norm_name", "position"] + COMPONENTS + ["proj_divergence"]
    if espn is None:                                    # FP-only -> byte-identical to the old pipeline
        fp["proj_divergence"] = 0.0
        return fp[cols]

    key = ["norm_name", "position"]
    e2 = espn.rename(columns={"full_name": "full_name_e", **{c: c + "_e" for c in provides}})
    m = fp.merge(e2[key + ["full_name_e"] + [c + "_e" for c in provides]], on=key, how="outer", indicator=True)
    m["full_name"] = m["full_name"].fillna(m["full_name_e"])
    both = m["_merge"] == "both"
    espn_only = m["_merge"] == "right_only"

    # divergence (both-source players only): how far apart the two sources' point proxies are
    fp_px, e_px = _proxy(m, ""), _proxy(m, "_e")
    m["proj_divergence"] = ((fp_px - e_px).abs() / ((fp_px + e_px) / 2).clip(lower=1)).where(both, 0.0)

    for c in COMPONENTS:
        fpv = m[c].astype(float)                        # FP value (NaN on ESPN-only rows)
        if c in provides:
            ev = m[c + "_e"].astype(float)              # ESPN value (NaN if not projected for this player)
            res = fpv.where(~espn_only, ev)             # ESPN-only rows take ESPN
            res = res.where(~(both & ev.notna()), w_fp * fpv.fillna(0) + w_espn * ev)  # both -> weighted
            m[c] = res
        else:
            m[c] = fpv                                  # ESPN doesn't provide this stat -> FP always
    for c in COMPONENTS:
        m[c] = m[c].fillna(0.0)                          # a missing component = 0 projection
    return m[cols]


if __name__ == "__main__":   # quick self-check
    b = blended_components()
    print(f"blended: {len(b)} players (FP∪ESPN). weights FP={PROJ_W_FP} ESPN={PROJ_W_ESPN}")
    show = b[b.full_name.isin(["Josh Allen", "Bijan Robinson", "Ja'Marr Chase"])]
    print(show[["full_name", "position", "pass_yds", "rush_yds", "rec", "rec_yds", "rec_td", "proj_divergence"]].round(1).to_string(index=False))
