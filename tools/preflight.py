"""Pre-draft preflight health check (read-only — touches nothing).

One command, run after the morning-of regen, that turns ~20 silent moving parts into a single
loud go/no-go. It validates ONLY the runtime surface — the files the deployed app actually reads
while you draft (5 committed CSVs) — plus the cross-file consistency and staleness that a partial
regen would break. The heavy build-time deps (FantasyPros CSVs, the cohort research panel, FF
Opportunity) aren't checked here because the app never touches them live; they're already baked
into these CSVs.

    .venv/bin/python tools/preflight.py

FAIL  = would corrupt the draft (missing/unloadable file, NaN in a load-bearing column, a data
        layer that silently zeroed out). Exit code 1.
WARN  = worth a look but the app still runs (stale priors, a count that drifted). Exit code 0.

This is the offline, deterministic half. The network name-match audit lives in its own tool —
run it too:  .venv/bin/python tools/name_audit.py
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import normalize_name

# Repo root the checks read from. Overridable (FA_PREFLIGHT_ROOT) so the fault-injection tests can
# point it at a corrupted copy; defaults to the real project root in normal use.
ROOT = os.environ.get("FA_PREFLIGHT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- what "healthy" looks like for each runtime file (rows are ranges; upstream data drifts) ----
RUNTIME_FILES = {
    "value_board.csv":            {"rows": (300, 900)},
    "cohort_data.csv":            {"rows": (150, 500)},
    "sos_data.csv":               {"rows": (128, 128)},
    "role_data.csv":              {"rows": (200, 700)},
    "data/playcallers_2026.csv":  {"rows": (32, 32)},
    "data/new_hc_2026.csv":       {"rows": (32, 32)},
    "data/dst_rankings.csv":      {"rows": (10, 40), "comment": "#"},
}
# columns the app cannot function without (a missing one breaks VONA / the board / the advisor)
VB_REQUIRED = ["full_name", "pos_label", "total_points", "vols", "adp_rank", "rank_composite",
               "market", "risk_tier", "floor", "ceiling", "p_startable", "p_bust", "team",
               "team_implied_total", "team_role", "role_lead", "role_env_ok", "is_rookie"]
# load-bearing columns that must NEVER be NaN — a NaN here silently corrupts VONA / the advisor
# (adp_rank is deliberately EXCLUDED: UD players legitimately have no ADP — checked separately)
VB_NO_NAN = ["full_name", "pos_label", "total_points", "vols", "rank_composite", "floor",
             "ceiling", "p_startable", "p_bust", "team_implied_total", "risk_tier", "team_role",
             "role_env_ok"]

_fails, _warns = [], []


def _p(path):
    return os.path.join(ROOT, path)


def ok(label):
    print(f"  \033[32mok\033[0m   {label}")


def fail(label, detail=""):
    _fails.append(label)
    print(f"  \033[31mFAIL\033[0m {label}" + (f"  — {detail}" if detail else ""))


def warn(label, detail=""):
    _warns.append(label)
    print(f"  \033[33mWARN\033[0m {label}" + (f"  — {detail}" if detail else ""))


def section(title):
    print(f"\n{title}")


# ---------------------------------------------------------------------------------------------
section("1. Runtime files load + have the columns the app reads")
loaded = {}
for path, spec in RUNTIME_FILES.items():
    full = _p(path)
    if not os.path.exists(full):
        fail(f"{path} present", "file missing — the app will 500 on load")
        continue
    try:
        df = pd.read_csv(full, comment=spec.get("comment"))
    except Exception as e:
        fail(f"{path} loads", f"unreadable: {e}")
        continue
    loaded[path] = df
    lo, hi = spec["rows"]
    if lo <= len(df) <= hi:
        ok(f"{path} loads ({len(df)} rows)")
    else:
        warn(f"{path} row count {len(df)} outside [{lo},{hi}]", "regen may have changed scope")

vb = loaded.get("value_board.csv")
if vb is not None:
    miss = [c for c in VB_REQUIRED if c not in vb.columns]
    fail("value_board.csv has every required column", f"missing: {miss}") if miss \
        else ok("value_board.csv has every required column")

# ---------------------------------------------------------------------------------------------
section("2. No NaN in value_board's load-bearing columns (the corruption guard)")
if vb is not None:
    for c in VB_NO_NAN:
        if c not in vb.columns:
            continue
        n = int(vb[c].isna().sum())
        ok(f"{c}: no NaN") if n == 0 else fail(f"{c} has {n} NaN", "would corrupt VONA/advisor output")

# ---------------------------------------------------------------------------------------------
section("3. Live ESPN ADP actually loaded (the morning-refresh dependency)")
if vb is not None and "adp_rank" in vb.columns:
    have = int(vb["adp_rank"].notna().sum())
    if have < len(vb) * 0.5:
        fail(f"only {have}/{len(vb)} players have an ADP", "ESPN ADP load likely failed → VONA blind")
    else:
        ok(f"ADP populated for {have}/{len(vb)} players")
        top50 = vb.sort_values("rank_composite").head(50)
        blind = list(top50.loc[top50["adp_rank"].isna(), "full_name"])
        warn(f"{len(blind)} top-50 players missing ADP (treated as UD)", ", ".join(blind[:5])) \
            if blind else ok("every top-50 player has an ADP")

# ---------------------------------------------------------------------------------------------
section("4. Priors are as fresh as the board (partial-regen staleness guard)")
if vb is not None:
    board_m = os.path.getmtime(_p("value_board.csv"))
    for path in ("cohort_data.csv", "sos_data.csv"):
        if os.path.exists(_p(path)):
            if os.path.getmtime(_p(path)) + 1 >= board_m:      # +1s slack for same-run writes
                ok(f"{path} is at least as new as value_board.csv")
            else:
                warn(f"{path} is OLDER than value_board.csv",
                     "board was regenerated without the priors — rerun cohort_priors.py + sos_priors.py")

# ---------------------------------------------------------------------------------------------
section("5. Cross-file consistency (cohorts, SoS, coaching)")
coh = loaded.get("cohort_data.csv")
if coh is not None and vb is not None:
    cset = set(coh["nn"]) if "nn" in coh.columns else set()
    skill = vb[~vb["pos_label"].str.startswith(("K", "D"))].sort_values("rank_composite").head(120)
    missing = [n for n in skill["full_name"] if normalize_name(n) not in cset]
    ok("every top-120 skill player has a cohort") if not missing \
        else fail(f"{len(missing)} top skill players missing a cohort", ", ".join(missing[:6])
                  + " — board regenerated without cohort_priors.py?")
    rates_ok = coh[["cohort_boom", "cohort_bust"]].apply(lambda s: s.between(0, 1).all()).all() \
        if {"cohort_boom", "cohort_bust"} <= set(coh.columns) else False
    ok("cohort boom/bust rates in [0,1]") if rates_ok else fail("cohort rates out of [0,1]")
    # the skew read (L29) — a regen that drops these silently costs the advisor the boom-tail signal
    if {"cohort_med", "cohort_trimmed"} <= set(coh.columns):
        ok(f"cohort median + trimmed-mean present "
           f"({int(((coh.cohort_med < 1.0) & (coh.cohort_trimmed >= 1.0)).sum())} tail-driven players)")
        # Scope to players who can actually reach the advisor's shortlist. Bottom-of-board backup QBs
        # (Rudolph/Mullens, composite ~#506) legitimately show trimmed >2x — their WHOLE comp set is
        # inflated because a backup who starts games beats a near-zero price. Warning on them would be
        # permanent noise, which is how a preflight gets ignored.
        core_nn = set(skill["full_name"].apply(normalize_name)) if len(skill) else set()
        core = coh[coh["nn"].isin(core_nn)] if "nn" in coh.columns else coh.iloc[0:0]
        blow = int((core["cohort_trimmed"] > 2.0).sum()) if len(core) else 0
        ok(f"trimmed means outlier-resistant across the draftable core "
           f"(max {core['cohort_trimmed'].max():.2f}x)") if blow == 0 and len(core) \
            else warn(f"{blow} DRAFTABLE players have trimmed mean > 2.0x",
                      "trimming may not be suppressing blow-up comps")
    else:
        fail("cohort_trimmed column missing", "rerun cohort_priors.py — advisor loses the skew read")

role = loaded.get("role_data.csv")
if role is not None:
    # the L31 dart/handcuff reads go dark without these — a regen that drops them is a FAIL
    need = {"nn", "share_2025", "ppg_2025", "weeks_2025", "pos_adp_rank"}
    if need <= set(role.columns):
        shares_ok = role["share_2025"].dropna().between(0, 1).all()
        ok(f"role_data has the L31 columns; shares in [0,1] "
           f"({int((role['share_2025'] >= 0.30).sum())} committee-share players)") if shares_ok \
            else fail("role_data share_2025 out of [0,1]")
        # staleness: must be regenerated alongside the board (same trap as cohorts)
        if os.path.getmtime(_p("role_data.csv")) + 1 >= os.path.getmtime(_p("value_board.csv")):
            ok("role_data.csv is at least as new as value_board.csv")
        else:
            warn("role_data.csv is OLDER than value_board.csv", "rerun role_priors.py after a board regen")
    else:
        fail(f"role_data missing columns {need - set(role.columns)}", "rerun role_priors.py — dart/handcuff reads dark")

sos = loaded.get("sos_data.csv")
if sos is not None and {"position", "sos_rank"}.issubset(sos.columns):
    # ranks tie legitimately (two teams can allow identical points), so check span 1..32 + full
    # 32-team coverage per position, not a strict permutation (mirrors 11_stress_test.py).
    spans = all(len(g) == 32 and g["sos_rank"].min() == 1 and g["sos_rank"].max() == 32
                for _, g in sos.groupby("position"))
    ok("SoS covers 32 teams, ranks span 1..32 for every position") if spans \
        else fail("SoS ranks don't span 1..32 for all 4 positions")

hc = loaded.get("data/new_hc_2026.csv")
if hc is not None and "new_hc" in hc.columns:
    n_true = int(hc["new_hc"].sum())
    ok(f"new-HC list has the verified {n_true} teams") if n_true == 10 \
        else warn(f"new_hc TRUE count is {n_true}, expected 10", "verify the 2026 coaching list")

# ---------------------------------------------------------------------------------------------
section("6. Live-sync + advisor configuration (informational)")
secrets_path = _p(".streamlit/secrets.toml")
if os.path.exists(secrets_path):
    try:
        import tomllib
        with open(secrets_path, "rb") as f:
            sec = tomllib.load(f)
        ok("ANTHROPIC_API_KEY set") if sec.get("ANTHROPIC_API_KEY") \
            else warn("ANTHROPIC_API_KEY not set", "the advisor will be disabled")
        sources = [n for n, present in (("espn", "espn" in sec),
                                        ("bridge", "bridge" in sec)) if present]
        if os.environ.get("FA_BRIDGE_URL"):
            sources.append("bridge(env)")
        ok(f"sync source configured: {', '.join(sources)}") if sources \
            else warn("no live-sync source configured", "Sleeper is entered in-app; else manual mode")
    except Exception as e:
        warn("could not parse .streamlit/secrets.toml", str(e))
else:
    warn("no .streamlit/secrets.toml", "dev may use FA_BRIDGE_URL; Cloud reads its own secrets")

# ---------------------------------------------------------------------------------------------
print("\n" + "=" * 70)
if _fails:
    print(f"\033[31mPREFLIGHT FAILED ❌  {len(_fails)} blocking issue(s), {len(_warns)} warning(s)\033[0m")
    for f in _fails:
        print(f"  ✗ {f}")
    sys.exit(1)
print(f"\033[32mPREFLIGHT OK ✅  0 blocking issues, {len(_warns)} warning(s)\033[0m"
      + ("  (review the WARNs above)" if _warns else ""))
print("Reminder: also run the network name audit -> .venv/bin/python tools/name_audit.py")
