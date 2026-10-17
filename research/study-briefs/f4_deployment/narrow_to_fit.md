# narrow_to_fit — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f4_deployment/narrow_to_fit.md); where the two differ, the registration wins.
> Latest outcome: headline `(R, F3, $1,000)` `NULL` (N4 and N5 `NOT MET`); secondary `(R, F3, $500)` `NARROW-FEASIBLE`; both 20% net-floor lines print the same tokens; stop-basis lines for `(R, F1, $1,000)` and `F4` `NOT FEASIBLE` — 2026-10-10 · [record](../../study-results/f4_deployment/narrow_to_fit.md).
> Nothing else here is a result.

## The question

When a pick's one-contract max loss is over budget, is it better to narrow the spread until it fits, or to refuse it? [`account_sim`](../../arm-index.md#account_sim) offers two answers: [F1](../../glossary.md#f1-vs-f2) takes the pick at one contract, and F2 refuses it. The operator does neither. The operator substitutes strikes so the pick fits, and closes on a $1,000 loss.

F2's gain mixes affordability with selection. Narrowing separates them. If the narrowed picks still earn, refusing them throws away edge. If they lose, F2's gain came from refusing bad trades.

A second question rides along: does the $1,000 stop, rather than the $500 budget, change the account's feasibility?

## What it compares

All cells run under `account_sim` ARM R (reject on a cap breach). Selection, exits and the replay harness are frozen. Narrowing never adds or removes a pick. The seven cells are fixed, and exactly two budgets run.

| Object | What it does | Kind |
|---|---|---|
| [narrow_to_fit (R, F3, $1,000)](../../arm-index.md#narrow_to_fit) | Narrows an over-budget pick. Budget and stop $1,000 | **HEADLINE** cell |
| narrow_to_fit (R, F1, $1,000) | Takes the pick at one contract. Budget and stop $1,000 | cell |
| narrow_to_fit (R, F2, $1,000) | Refuses the pick at $1,000 | control |
| narrow_to_fit (R, F3, $500) | Narrows at budget and stop $500 | secondary cell |
| narrow_to_fit (R, F1, $500) | The registered `account_sim` headline | control |
| narrow_to_fit (R, F2, $500) | The post-hoc result in question | control |
| narrow_to_fit F4 | Sizes like F1 at the $500 budget, with a $1,000 stop. Nothing narrowed | cell |

Two declared secondary lines join the table: `(R, F3, $1,000)` and `(R, F3, $500)`, each with a 20% net floor. A narrowed debit spread whose net debit is under 20% of its width is refused as `narrow_no_fit`, reason `below_net_floor`. Credit spreads are never floored. These lines are not new arms. Each is graded on N1 to N5 and prints its own verdict line.

**The F3 rule.** It keeps the ticker, expiry, right and anchor leg, and moves the other leg inward to the widest listed strike at which one contract's max loss fits the budget. It refuses the pick when nothing fits (`narrow_no_fit`), the tier rule breaks (`narrow_tier_break`) or the substitute leg has no usable price (`narrow_unpriced`). The strike rule and the listed-strike evidence rule are in [the registration](../../pre-registrations/f4_deployment/narrow_to_fit.md#narrow-to-fit-cell-family-f3).

## How it is judged

**Population.** Era v4 only. There is no v3 run. [PRIMARY dense episodes](../../glossary.md#primary-dense-episodes-vs-secondary-full-book) carry the verdict. SECONDARY may block a verdict but never carries one alone. The account is `account_sim`'s: $25,000, 3 positions a day, commission-only cost. The headline runs on the (0.25, 1.50) cap cell. The (0.25, 2.50) cell runs as a robustness cell, and a verdict must hold on both.

**Gates.** All exit non-zero on failure, except `GN0` and `GN5`, which print.

- `G2`–`G5`: `account_sim`'s own, run on every cell that uses cached rows only.
- `GN0`: the narrowed subset needs at least 25 dates and 60 positions in PRIMARY. Below either, the cell prints `UNDERPOWERED`.
- `GN1`: `F3` with every narrowing forced to refuse must reproduce `(R, F2)` at the same budget.
- `GN2`: `F4` with its stop set back to $500 must reproduce `(R, F1, $500)`.
- `GN3`: the narrowed-spread builder, run at a stored row's own strikes, must reproduce that row's entry net and daily marks.
- `GN4`: truncating each substitute history after its entry day must leave the chosen strikes identical.
- `GN5`: if more than 10% of PRIMARY over-budget picks end `narrow_unpriced`, the `F3` cells print `AWAITING SCRAPE`.
- `GN6`: no annualised figure, Sharpe or time-to-recover, and no hardcoded count.

**Bar.** Two questions, graded in this order on PRIMARY. The window re-cuts are fixed to `ex-2025_mar_apr` and `ex-2026_feb_apr`.

*Q1: is `(R, F3, $1,000)` feasible?* It must meet all three.

1. **N1.** `account_sim`'s FEASIBLE (A1∧A2∧A3∧A5∧A6) on both cap cells.
2. **N2.** The median max drawdown over the cell's block-bootstrap paths (block length 10) is at or under 25% of capital.
3. **N3.** Inside every `(R, F1, $500)` drawdown window of 10% of capital or deeper, the cell's deepest drawdown is shallower, on PRIMARY and SECONDARY.

*Q2: do the narrowed picks earn?* The subset is picks over $1,000 that were narrowed and taken.

1. **N4.** The subset's meanR is above zero, with the CI excluding zero.
2. **N5.** It keeps its sign on both window re-cuts and in every calendar year with at least 10 narrowed positions.

`(R, F3, $500)` is graded on N1 to N5. `(R, F1, $1,000)` and `F4` are graded on N1 to N3. None changes the headline verdict.

## Possible verdicts

| Token | What it means |
|---|---|
| `NARROW-FEASIBLE` | Q1 and Q2 pass. Narrowing keeps the edge and the account survives |
| `AFFORDABILITY` | Q2 passes, Q1 fails |
| `SELECTION` | N4's CI sits wholly at or below zero. F2's gain was selection |
| `NULL` | N4's CI straddles zero and `GN0` passes. Q1 prints as a line |
| `UNDERPOWERED` | `GN0` stops Q2. Census only |
| `AWAITING SCRAPE` | `GN5` fires. Census only. The fix is the scrape, never a lower gate |

The stop-basis line for `(R, F1, $1,000)` and `F4` reads one of three ways.

- `STOP-FEASIBLE`: N1 to N3 pass.
- `STOP-HURTS`: maxDD is deeper than `(R, F1, $500)`'s on PRIMARY.
- `NOT FEASIBLE`: anything else.

## What could ship

Nothing ships directly. A `NARROW-FEASIBLE` verdict, confirmed by a forward read that keeps its sign, lets the operator consider a deploy-card rule: narrow an unaffordable spread to fit, and refuse it if nothing fits. The forward read needs at least 15 signal dates after acceptance, once the `holdout_seal` decision allows. The rule needs its own [§2](../../../docs/deployment-rules.md#s2) change, a rollback trigger and a `deployment-evidence.md` entry. A `STOP-FEASIBLE` line licenses nothing.

## What this study cannot tell you

- Whether the ladder has an edge. Selection is frozen.
- Whether any other budget or stop works. Only two budgets run.
- Anything about ARM D downsizing or about v3. Every cell runs ARM R, on v4.
- Whether the 20% net floor works. It was picked after an in-sample read, so on this book it is seen, not tested.
