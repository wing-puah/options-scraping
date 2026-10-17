# ruin_bound — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f4_deployment/ruin_bound.md); where the two differ, the registration wins.
> Latest outcome: headline ($500 budget and stop) `SAFEST ELIGIBLE CELL: N250-F2 G-none`; declared secondary ($1,000 budget and stop) `NO CELL MEETS THE BOUNDS` — 2026-10-10 · [record](../../study-results/f4_deployment/ruin_bound.md).
> Nothing else here is a result.

## The question

The operator will accept a deeper drawdown for more return, if a clear guardrail prevents ruin. Among the cap cells and guardrails, which one earns the most while the probability of ruin and the p95 and p99 max drawdown stay under bounds fixed first?

This is a risk-budget question, not an edge test. [`account_sim`](../../arm-index.md#account_sim)'s [A1](../../glossary.md#criteria-a1a6) still decides whether the ladder has an edge, and this study requires it. The registration was accepted by default on 2026-10-09. The result is a reading for the operator: it changes no tracked cap, config file or production rule.

## What it compares

Every configuration is a cap cell times a guardrail, run under each overlay. All 24 are reported. The per-position cap is 0.25 × equity. The budget is 2% of capital on a max-loss basis ($500 budget and stop, the headline). A declared secondary runs the same design at $1,000 budget and stop, with the same bounds.

| Object | What it does | Kind |
|---|---|---|
| [ruin_bound N100-F1, N150-F1, N250-F1](../../arm-index.md#ruin_bound) | Net cap 1.00, 1.50, 2.50. [F1](../../glossary.md#f1-vs-f2) takes the one-contract floor | cap cell |
| ruin_bound N100-F2, N150-F2, N250-F2 | The same net caps. F2 refuses a pick whose one contract exceeds the budget | cap cell |
| ruin_bound G-none | No guardrail beyond the caps | guardrail |
| ruin_bound G-M | Refuses a new position if reserved capital would exceed 0.50 × current MTM equity | guardrail |
| ruin_bound G-K | Stops all new entries for the rest of H once MTM equity is 0.25 below its running peak | guardrail |
| ruin_bound G-C | After a session whose MTM loss is at least 5% of equity, takes no new entries for the next 5 sessions | guardrail |

Guardrails stop or cap entries; they never resize them. ARM R (reject) runs throughout.

Four overlays represent markets the sample never held.

- `O0`: none, the resample alone.
- `O1`: once per path, at the session with the most reserved capital, every open long-delta position loses the smaller of its max loss and 0.10 × its absolute delta-notional.
- `O2`: at the same session, every open position loses its full max loss.
- `O3`: resample only from sessions that carry a candidate list.

## How it is judged

**Ruin and basis.** Every deciding figure is net of cost, and drawdown is MTM as a fraction of starting capital. A path is ruined if MTM equity closes at or below half the starting capital on any session inside the horizon H. H is the length of the pooled PRIMARY session series, computed at run time.

**Resample.** A stationary block bootstrap over sessions, re-running the account walk on 5,000 paths per configuration per overlay, seed 20261009. Primary block length L is max(20, p75 of held sessions, rounded up to a multiple of 5). Sensitivity values are half and 1.5 × L.

**Population.** PRIMARY decides. SECONDARY is a check, and a cell must meet every bound on both. The study reads signal dates up to 2026-09-22 only. A v3 control prints realized walks and is never scored.

**Gates.** A failing gate exits non-zero and prints no verdict. `R0` is the era check: `lib/era.py` refuses a wrong or thin era.

- `R1`: every taken position carries `cost_total` and `cost_basis`. Anything under 100% refuses.
- `R2`: with L at the series length, no guardrail and no overlay, the resampled walk reproduces `account_sim`'s realized walk.
- `R3`: `cash + Σreserved == capital + Σrealized` on every path and session, and reserved never exceeds equity.
- `R4`: guardrails and selection read no outcome field.
- `R5`: on every shocked path, equity at the shock is ordered O2 ≤ O1 ≤ O0. The full-horizon order prints and gates nothing.

**Bar.** A configuration is eligible only if every clause holds at every readable L, on PRIMARY and SECONDARY. An L with H / L under 8 is printed and not read.

1. **B1.** P(ruin within H) under `O0` is at most 0.01.
2. **B2.** P(ruin within H) under `O1` and `O3` is at most 0.05.
3. **B3.** The p95 MTM max drawdown under `O0` is at most 0.30.
4. **B4.** The p99 MTM max drawdown under `O0` is at most 0.45.
5. **B5.** The p99 `O2` loss is at most 0.60 of equity.
6. **B6.** `account_sim`'s A1 holds on the realized walk, unchanged.

**Decision rule.**

1. Take the eligible configuration with the lowest p95 MTM max drawdown under `O0`, at the primary L, on PRIMARY. Call it **S**.
2. A riskier eligible configuration (higher p95 drawdown) displaces S only if its per-date dollar advantage over S on the realized PRIMARY walk is positive, with a date-clustered paired 95% CI excluding zero.
3. If several pass step 2, choose the highest median dollars over H under `O0`.
4. If none is eligible, none is chosen. Ties in step 1 go to the earlier configuration in the arms order.

## Possible verdicts

The report prints one line for the headline and one for the declared secondary. The secondary never breaks a tie for the headline.

| Token | What it means |
|---|---|
| `RISKIER CELL EARNS ITS DRAWDOWN: <config>` | A configuration other than S passed step 2 and was chosen |
| `SAFEST ELIGIBLE CELL: <config>` | S was eligible and nothing riskier earned its drawdown |
| `NO CELL MEETS THE BOUNDS` | No configuration is eligible. The answer points at capital, never at looser bounds |
| `UNDERPOWERED` | H / L is under 8 at the primary L on PRIMARY. Nothing is chosen |

## What could ship

Nothing ships from the first run. It is a reading, and the tracked cap in `config/account-sim.yml` keeps its value whatever the verdict says. The operator may later change two things by hand: the chosen cell's caps in that file, and the chosen guardrail as an attention flag first. Nothing ships on `NO CELL MEETS THE BOUNDS` or `UNDERPOWERED`.

## What this study cannot tell you

- How bad a different market could be. A resample recombines one history, and the overlays are assumptions.
- Whether the ladder has an edge. That stays with A1.
- Whether a sizing rule helps. Kelly, volatility-scaled budgets and size throttles are ruled out.
- Whether early assignment, gap-through fills or broker margin changes would hurt. None is modelled.
- Anything about a market unlike the sample's. The sample has no 2020-style crash and no 2022-length bear market, and the book is 100% long delta.
