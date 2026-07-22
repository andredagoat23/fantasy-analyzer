# Enrich pick_capture.json with 3 pros / 1 con per candidate — generated deterministically from the
# player's REAL value_board metrics (no fabrication). Same logic could live in the Research page.
# Run AFTER 13_strategy_bakeoff.py has written pick_capture.json.
import json
import pandas as pd

PATH = "icm/work/mc_research/pick_capture.json"
b = pd.read_csv("value_board.csv")
pool = b[b["rank_composite"] <= 180]          # draftable reference for "high/low" thresholds
CEIL_HI, CEIL_LO = pool.ceiling.quantile(0.75), pool.ceiling.quantile(0.30)
FLOOR_HI = pool.floor.quantile(0.70)


def pros_for(m):
    """Return prioritized pros (metric-grounded); caller takes the top 3."""
    p, pos = [], (m.get("pos_label") or "")
    ov, adp, ecr = m.get("overall_rank"), m.get("adp_rank"), m.get("ecr_rank")
    gap, coh = m.get("value_gap"), m.get("cohort_trimmed")
    pb, ps, av = m.get("p_bust"), m.get("p_startable"), m.get("availability")
    ce, fl, age = m.get("ceiling"), m.get("floor"), m.get("age")
    def add(prio, txt):
        p.append((prio, txt))
    if ov is not None and ov <= 12:
        add(10, f"Top-{ov:.0f} overall by our value (VOLS {m.get('vols'):.0f}) — an elite anchor.")
    if m.get("market") == "VALUE" or (gap is not None and gap >= 12):
        add(9, f"Market VALUE — the field lets him fall to ADP {adp:.0f} while we rank him {ov:.0f} (+{gap:.0f}).")
    if coh is not None and coh >= 1.10:
        add(8, f"Cohort {coh:.2f}x — his 15 nearest historical comps beat their draft price.")
    if pos.startswith("TE") and ov is not None and ov <= 40:
        add(8, f"Positional scarcity — a top TE ({pos}) locks a weekly edge at a thin position.")
    if pb is not None and pb <= 0.15:
        add(7, f"Low bust ({pb:.0%}) and {ps:.0%} startable — a reliable weekly starter.")
    if ce is not None and ce >= CEIL_HI:
        add(6, f"Big ceiling ({ce:.0f}) — real league-winning upside.")
    if fl is not None and fl >= FLOOR_HI:
        add(6, f"High floor ({fl:.0f}) — a safe points base every week.")
    if av is not None and av >= 0.90:
        add(5, f"Durable — {av:.0%} availability.")
    if age is not None and age <= 24 and pos[:2] in ("WR", "RB", "TE"):
        add(5, f"Young ({age:.0f}) with an ascending role.")
    if ecr is not None and adp is not None and ecr <= adp - 8:
        add(4, f"Experts rank him well above ADP ({ecr:.0f} vs {adp:.0f}) — the market is sleeping on him.")
    # fallbacks so we always have >=3
    add(1, f"Fills a starting {pos[:2]} in this range at a fair cost.")
    add(0, f"Projected {ps:.0%} startable." if ps is not None else "Draftable roster piece here.")
    return [t for _, t in sorted(p, key=lambda x: -x[0])]


def con_for(m):
    pos = (m.get("pos_label") or "")
    pb, ps, av = m.get("p_bust"), m.get("p_startable"), m.get("availability")
    coh, gap, adp, ov = m.get("cohort_trimmed"), m.get("value_gap"), m.get("adp_rank"), m.get("overall_rank")
    ce, age = m.get("ceiling"), m.get("age")
    if m.get("risk_tier") == "Injury Risk" or (av is not None and av < 0.82):
        return f"Injury Risk — {av:.0%} availability; the projection assumes missed time."
    if pb is not None and pb >= 0.35:
        return f"Boom/bust — {pb:.0%} bust risk, only {ps:.0%} startable; a real gamble."
    if coh is not None and coh < 1.0:
        return f"Cohort {coh:.2f}x — his comps historically return below price, so little margin."
    if (gap is not None and gap <= -12) or m.get("market") == "REACH":
        return f"REACH — costs more (ADP {adp:.0f}) than our value ({ov:.0f})."
    if pos.startswith("TE") and ov is not None and ov <= 40:
        return "Spends early capital on a 1-start position; if the TE cliff is shallow it could buy more RB/WR."
    if ce is not None and ce <= CEIL_LO:
        return f"Modest ceiling ({ce:.0f}) — a solid starter but limited league-winning upside."
    if age is not None and age >= 29:
        return f"Age {age:.0f} — decline and durability risk."
    return "Solid but not a difference-maker at this cost — safe, unspectacular."


d = json.load(open(PATH))
n = 0
for s in d["slots"]:
    for rnd in s["rounds"]:
        for c in rnd["candidates"]:
            m = c.get("metrics", {})
            if not m:
                continue
            c["pros"] = pros_for(m)[:3]
            c["con"] = con_for(m)
            n += 1
d["reasons_note"] = "3 pros / 1 con per candidate, generated deterministically from value_board metrics."
json.dump(d, open(PATH, "w"), indent=2)
print(f"enriched {n} candidates in {PATH}")
