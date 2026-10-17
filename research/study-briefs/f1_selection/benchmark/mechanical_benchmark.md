# mechanical_benchmark — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/benchmark/mechanical_benchmark.md); where the two differ, the registration wins.
> Latest outcome: `SAME-TICKER READ — ARM U NOT BUILT`. `mechanical_benchmark ARM M1` meets `CONTRARY`; `ARM M2` does not. C1 and C2 fail on both. `ARM U` is not built, so no study-level verdict prints. v3 is not graded: its pairs await a fetch — 2026-10-15 · [record](../../../study-results/f1_selection/benchmark/mechanical_benchmark.md).
> Nothing else here is a result.

## The question

Is the book selection, or is it a long call spread in a rising market? Every recorded edge is measured against the book's own variants. No study has compared a pick with what a rule, with no model, would have done on the same day. The study registered 2026-10-09 and was accepted by default the same day.

## What it compares

Every arm replays through the frozen harness under the shipped debit exit profile ([§5](../../../../docs/deployment-rules.md#s5)) and the same [path cap](../../../glossary.md#path-cap). Costs are not modelled, so both books are gross. The counterpart is always a bull call vertical, even against a bear pick.

| Object | What it does | Kind |
|---|---|---|
| [mechanical_benchmark ARM T](../../../arm-index.md#mechanical_benchmark) | The deployed picks, replayed unchanged | reference, no verdict |
| mechanical_benchmark ARM M1 | Same ticker and date. Long the strike nearest spot × 1.00, short the strike nearest spot × 1.05, at the pick's own expiry | PRIMARY |
| mechanical_benchmark ARM M2 | Same ticker and date. Long the strike whose signal-date delta is nearest the pick's net delta, short leg 5% above it | SECONDARY |
| mechanical_benchmark ARM M2L | Like `ARM M2`, but the target is the pick's bought-leg delta | declared secondary, no verdict |
| mechanical_benchmark ARM U | The `ARM M1` wrap on random flow-universe tickers, ≥ 1,000 seeded draws, reported as a [p5, p95] band | PRIMARY for selection |
| mechanical_benchmark ARM CEN | Pair-build, redraw and band-coverage counts | descriptive, never a criterion |

The geometry is frozen: ATM/+5%, DTE bands `[7,21) [21,45) [45,90) [90,180)`, one contract, one expiry on both legs. A counterpart outside the pick's band drops the pair on both sides.

A pair whose strike is not cached awaits a fetch. While any pair awaits, no outcome prints. Other build rules, including the redraw cap and how `ARM U` runs, are in [Definitions](../../../pre-registrations/f1_selection/benchmark/mechanical_benchmark.md#definitions).

## How it is judged

**Measure.** Paired within-date mean gain in [R](../../../glossary.md#r), picks minus counterpart, with a 95% date-clustered CI. [PF](../../../glossary.md#pf) prints on both sides, never without mean R.

**Population.** The deployed set: top 3 per day, `ladder_eligible` (Tier A and B only), real and `strike_expiry_tweak` rows. v4 is primary. v3 runs as the era-stability read. Every signal date from 2026-09-23 is withheld while the [`holdout_seal`](../../../pre-registrations/f4_deployment/holdout_seal.md) stands. A "bear pick" means a deployed row whose model regime reads BEAR.

**Census floors.** The census runs first and decides whether anything prints.

- Floor 1 (every arm): at least 25 dates, each with at least 1 priced `ARM M1` pair.
- Floor 2 (every arm): no tier more than 10 points from another in the share of in-scope picks whose counterpart is unbuildable. A failure here kills the whole study.
- Floor 3 (`ARM U`): the median priceable share of the day's universe is ≥ 75%.
- Floor 4a (same-ticker arms): no `ARM M1` or `ARM M2` pair awaits a fetch.
- Floor 4b (`ARM U` and the study verdict): no contract is left to fetch for any arm.
- Floor 5: printed only.

**Gates.** G1 to G7 cover era identity, no look-ahead, exit parity, pairing integrity, pricing-tier honesty, no new statistic and no hardcoded census. Each exits non-zero on failure.

**Bar.** Criteria C0 to C5, all required for a selection claim.

1. C0: at least 25 dates and 40 matched pairs, or the arm prints `UNDERPOWERED`. The floor may not be lowered.
2. C1: the paired gain's CI excludes zero.
3. C2: every [leave-one-date-out](../../../glossary.md#loo) fold is positive.
4. C3: the picks' mean R over the slots `ARM U` covers is above `ARM U`'s p95 across the draws.
5. C4: Tier A's gain is not smaller than Tier B's. Graded on `ARM U`.
6. C5: C1 holds on both eras with the same sign. Graded on `ARM U`.

## Possible verdicts

`CONTRARY` takes precedence, since it must reach the operator first.

| Token | What it means |
|---|---|
| `SELECTION-CONFIRMED` | `ARM U` clears C0–C3, and C4 and C5 hold |
| `STRUCTURE-ONLY` | `ARM M1` or `ARM M2` clears C0–C2, but `ARM U` does not |
| `BASE-RATE` | `ARM U` clears, but `ARM M1` and `ARM M2` do not |
| `NULL` | Powered, and no arm clears C1 |
| `CONTRARY` | An arm's paired gain is negative with a CI excluding zero |
| `UNDERPOWERED` | No arm clears C0 |
| `NOT BUILT` | The census fails its floors |
| `NOT BUILT — AWAITING SCRAPE` | A floor could still pass after the operator-run fetch |
| `UNWORDED` | Matches no worded verdict, such as `ARM M1` clearing C1 but not C2 |
| `SAME-TICKER READ — ARM U NOT BUILT` | The same-ticker arms pass their floors and `ARM U` does not. Per-arm C0, C1, C2 and `CONTRARY` print; no study-level verdict does |

`SAME-TICKER READ — ARM U NOT BUILT` is not a verdict of record. An arm meeting `CONTRARY` is still named for the operator.

## What could ship

Nothing ships under any outcome. A mechanical wrap that wins is a finding about the picks, not a strategy. `STRUCTURE-ONLY`, `BASE-RATE`, `NULL` and `CONTRARY` each record a written narrowing of what the shipped rules may claim. The same-ticker read feeds [`programme_gate`](../../../pre-registrations/f4_deployment/programme_gate.md).

## What this study cannot tell you

- Whether a different geometry would fare better. The geometry is frozen and may not be searched.
- Whether exits or sizing are tuned well. Both sides use the same exit profile.
- Anything about cost. Both books are gross.
- What the operator actually traded. That is a separate journal-based read.
- Anything about `ARM U` until it is built. `ARM M1` and `ARM M2` alone cannot answer the base-rate question.
