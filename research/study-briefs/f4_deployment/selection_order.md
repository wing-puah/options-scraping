# selection_order — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f4_deployment/selection_order.md); where the two differ, the registration wins.
> Latest outcome: on the registered v3 book, `POWER-STOPPED`: no arm powered, best 11 of 25 dates (2026-08-15). Later v4 runs, not the registered book, read `ORDERING-IS-NOISE` (2026-09-28) · [record](../../study-results/f4_deployment/selection_order.md).
> Nothing else here is a result.

## The question

Does a different, blind, entry-side order of the same candidates spend the binding delta budget better? [`account_sim`](../../arm-index.md#account_sim) found that delta exposure binds, not cash. It also found that the picks the net cap excludes outperform the picks it admits. The ladder-rank walk may spend a scarce budget on earlier picks that then underperform the ones it excludes. That reading was post-hoc in `account_sim`. This study makes a test of it admissible.

## What it compares

Only the order in which an eligible day's candidates reach the ledger changes. Tier membership, the candidate universe, sizing, caps and exits stay frozen as `account_sim` runs them. The six arms are fixed. None may be added after a result is seen.

Every arm reads entry-side fields only (`delta`, `entry_underlying`, `max_loss_per_contract`, `tier`). Ties break on `ladder_rank`. Higher sorts first.

| Object | What it does | Kind |
|---|---|---|
| [selection_order O0](../../arm-index.md#selection_order) | `ladder_rank`: tier, then `score_total` tie-break. Today's production order | baseline |
| selection_order O1 | Delta-notional ascending, within tier. Cheapest exposure first | ordering arm |
| selection_order O2 | Reserved dollars per unit of delta-notional, descending, within tier | ordering arm |
| selection_order O3 | `\|delta\|` descending, within tier. A transfer test of `hedge_sizing`'s D4 rule outside bear | ordering arm |
| selection_order O1b | Delta-notional ascending, tier-blind across A∪B. Eligibility is unchanged | ordering arm |
| selection_order O4 | Seeded random permutation within the day, 200 draws | null band |

`O4` decides what the other arms mean. An arm must beat the random band, not merely beat `O0`. If `O0` itself sits inside the band, the adverse-ordering read was an artifact and the thread closes.

## How it is judged

**Measure.** The within-date paired difference versus `O0` in [mean R](../../glossary.md#meanr) over the day's taken positions. Dollars print beside it as a sanity check only, because they depend on which positions get sized.

**Unit.** A contested date: a session with at least 2 eligible candidates and at least 1 exclusion in `{day3_cap, net_delta, per_pos_delta}`. Uncontested dates are identical across arms and are left out of the paired test.

**Population.** The registered book is `load_book(include_bs=False)` with the proxy calibration gate on. The registration names it as the frozen 795-row, 118-date basis, with v4 rows never pooled in. The configured dense episodes are PRIMARY. The full book is SECONDARY, reported, and carries nothing. `config/account-sim.yml` runs as committed with compounding off. The `--structure-universe` arm is not used. The bear hedge sleeve (`ARM H`) is off for every arm.

**Gates.** Each exits non-zero on failure.

- `G0`: runs first and blocks everything. It prints the contested-date census and, per arm, the dates whose pick set differs from `O0`. Under 25 affected dates, the arm is `POWER-STOPPED` and its cells are not read.
- `G1`: `O0` must reproduce the default `account_sim` run exactly, including the `220 / 90 / $63,553` book line.
- `G2`: every arm passes the `BlindRec` / `blind_records` probe. The resulting book must equal the sighted one.
- `G3`: candidates partition exactly into taken plus census buckets, per arm.
- `G4`: no annualised figure, Sharpe or time-to-recover anywhere.
- `G5`: in-sample tables are labelled. Only LOO folds and `protocol.walk_forward_splits` TEST rows are adoption-eligible.

**Bar.** An arm must clear all seven items. No relaxation after a number is seen.

1. Paired mean gain versus `O0` is above zero, with a date-clustered bootstrap CI excluding zero (`BOOT_N = 10000`).
2. Median gain among affected dates is positive, with at least 25 affected dates.
3. Every LOO fold is positive.
4. The gain is positive in every calendar year present in the arm's population.
5. It holds on the shipped exit config, not only a variant.
6. It survives `protocol.window_cuts` and the ex-both-windows cut added by hand.
7. It exceeds the `O4` random band: above the 95th percentile of the 200 draws.

## Possible verdicts

| Token | What it means |
|---|---|
| `ORDERING-MATTERS` | An arm clears all seven items. A candidate, not a ship. It queues an independent-window confirmation |
| `ORDERING-IS-NOISE` | No arm separates from the `O4` band. The adverse-ordering read was an artifact. Record it and close the thread |
| `CAP-BOUND-NOT-ORDER-BOUND` | Arms clear `G0` but produce near-identical books. The cap excludes the same picks whatever the order |
| `POWER-STOPPED` | `G0` fails. Census only, nothing read, no re-run on these dates |

## What could ship

Nothing ships from this study under any outcome, and the report must say why. After `ORDERING-MATTERS` and an independent-window confirmation, the ordering may be proposed for [`deployment-rules.md`](../../../docs/deployment-rules.md) as a tie-break within the deployed set. The report must carry a standing caveat: the ladder is itself in-sample, so an ordering tested on the same book is second-order in-sample.

## What this study cannot tell you

- Whether selection is right. Selection is closed, and reopens on new columns only.
- Anything about cap values, capital, risk percentage, positions per day, `take_floor`, `downsize` or the exit profile. All stay at committed values.
- Anything from dollars. Dollars depend on composition and are a sanity check only.
- Whether a hedge sleeve interacts with order. `ARM H` is off.
- Whether the ladder holds out of sample. The ladder is fitted on this book.
