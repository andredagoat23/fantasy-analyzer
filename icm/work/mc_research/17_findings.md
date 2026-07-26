# Board-weight backtest — findings (Jul 2026)

**Script:** `17_weight_backtest.py`. **Method (best feasible):** a HYBRID backtest over 2022-2024 —
REAL historical ADP (FantasyFootballCalculator PPR, 12-team), REAL finishes (nflverse actuals scored
under the league base scoring), and value signals (VOLS/ceiling/floor/role) PROXIED from each prior
year's actuals. Metric = mean per-season Spearman between the weighted composite order and actual
finish, over the top-150-ADP veteran pool (393 player-seasons).

## Results (higher = better predictor of finish)
| Predictor | Spearman | vs ADP |
|---|---|---|
| ADP-only (the market) | 0.420 | — |
| **Current composite weights** (V .32 / market .36 / ceil .13 / floor .09 / role .10) | **0.505** | **+0.085** |
| Optimized (random search) | 0.560 | +0.140 |

Optimized weights: **value 0.00 · market(ADP) 0.34 · ceiling 0.33 · floor 0.12 · role 0.21.**

## What it means
1. **The composite genuinely beats the market (+0.085 over ADP-only).** Blending signals adds real
   predictive value — the core design is validated, not just plausible.
2. **Upside (ceiling) + opportunity (role) look UNDER-weighted.** Current gives them 0.13+0.10 = 0.23;
   the optimum wants 0.33+0.21 = 0.54. Prior-year ceiling and usage predict next-year finish well.
3. **Market weight is about right** (opt 0.34 vs current 0.36 — ADP + ECR are ~0.9 correlated, so ADP
   stands in for both here).

## The big caveat — why "value → 0" is NOT a real result
The backtest PROXIES value with **prior-year actual points** (backward-looking). The real board's VOLS
comes from **forward projections** (which now blend FP + ESPN, L44) — a much stronger predictor than
last year's stats (last year's points regress hard and the market already prices them in). So the
optimizer zeroing "value" means *"prior-year points don't add over ADP+ceiling+role,"* NOT *"forward
VOLS is worthless."* **Do not cut the VOLS weight based on this.** Other limits: 3 seasons only,
veterans only (no rookies — where forward projection matters most), no separate ECR, base scoring.

## Recommendation (for brainstorming)
- **Keep the composite** — it beats the market, which is the bar.
- **The one defensible, data-backed tweak:** nudge **ceiling + role UP** a little (upside + opportunity
  are under-credited), funded from **floor** and a touch of **market** — NOT from value (proxy-biased).
  e.g. a conservative move: ceiling .13→.16, role .10→.13, floor .09→.07, market(ECR+ADP) .36→.33,
  value .32 (unchanged). Small, in the direction the data points, without trusting the proxy on value.
- **But 5 days from the draft**, I'd lean *leave the weights as-is* (the gain is modest, 0.505→~0.53
  best-case, and the current board is reviewed/stable) and revisit properly POST-draft with real
  historical ECR + projections (which would let us judge the value weight honestly). Your call.
