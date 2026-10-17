# ticker_class_regime — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/benchmark/ticker_class_regime.md); where the two differ, the registration wins.
> This study is a DRAFT. It is not registered and has not run. The operator has not accepted it, and it may still change.
> Latest outcome: not run.
> Nothing else here is a result.

## The question

[`ticker_class`](../../../pre-registrations/f1_selection/benchmark/ticker_class.md) found no reliability gap between index ETFs and single stocks on the pooled in-sample book. A pooled `NULL` can hide a gap that flips sign by regime. Does the index-minus-single-stock gap depend on the market's trend or volatility regime, on forward dates only?

The first draft was hashed on 2026-10-07, before an exploratory in-sample regime read. The operator then asked for more splits and stronger robustness. Every later change is listed in the draft under [Changes after the exploratory read](../../../pre-registrations/f1_selection/benchmark/ticker_class_regime.md#changes-after-the-exploratory-read).

## What it compares

The groups are the frozen `ticker_class` table, checked by the same sha256 (`6ce7373e…`). G1 is the index group. S is G5 ∪ G6 ∪ G7. The gap is G1 meanR minus S meanR within a cell, net of cost. Both sides share the same play direction.

The regime comes from the loader's mechanical axes, not the model's text. Trend is `mech_direction`: BULL, RANGE or BEAR. "Non-BULL" pools RANGE and BEAR. Vol is `mech_vol`: L-VOL, or "H/E-VOL", which pools H-VOL and E-VOL.

The graded family is closed at seven contrasts. Each has a fixed error budget (α); the budgets sum to 0.05.

| Object | What it measures | α |
|---|---|---|
| ticker_class_regime C1 | Gap, bear plays, BULL trend | 0.005 |
| ticker_class_regime C2 | Gap, bear plays, non-BULL trend | 0.005 |
| ticker_class_regime C3 | Gap, bear plays, L-VOL | 0.005 |
| ticker_class_regime C4 | Gap, bear plays, H/E-VOL | 0.005 |
| ticker_class_regime C5 | Gap, bull plays, BULL trend and L-VOL | 0.005 |
| ticker_class_regime I1 | C1 minus C2: does the gap depend on trend? | 0.0125 |
| ticker_class_regime I2 | C3 minus C4: does the gap depend on volatility? | 0.0125 |

Four objects print and are never graded:

- `P1`: the gap in every cell of the 3 × 3 trend × vol grid.
- `P2`: the gap against G5, G6 and G7 separately.
- `P3`: the original draft's contrast, BEAR_HE minus LVOL, on bear plays.
- `P4`: neutral plays per cell.

A lead seen there needs a new registration.

## How it is judged

**Population.** Forward signal dates after 2026-10-07 that have backtest rows. Dates on or before 2026-10-07 are never graded. All graded rows come from one prompt era. Rows with no `mech_direction` or `mech_vol` are dropped and counted.

**Tests.**

- `C1`–`C5`: a permutation test. G1/S labels shuffle among positions of the same play direction, within the same calendar week and cell. The p-value is two-sided, with 10,000 shuffles and seed 20261007. A date-clustered bootstrap CI at level 1 − α prints beside it.
- `I1`, `I2`: a circular-shift permutation test of the regime-label series, for every shift at least 10 signal dates from zero.

**Gates.**

- `GR0`: each side has ≥ 30 dates and ≥ 60 positions. An interaction needs this on all four sides. Failure reads `STILL-OPEN`.
- `GR1`: ≤ 25% of each side's positions are open at the data end. Failure reads `STILL-OPEN`.
- `GR2`: the group-table hash matches `ticker_class`'s. Failure exits 1.
- `GR3`: every graded row is from one era. Failure exits 3.
- `GR4`: an interaction needs ≥ 160 admissible circular shifts. Failure leaves that interaction `STILL-OPEN`.
- `GR5`: a contrast that has not passed `GR0` and `GR1` by 2028-04-07 reads `UNDERPOWERED`, final.

Before a contrast passes `GR0` and `GR1`, runs print its census only. Each contrast is graded once, at the first run where it passes. No later run re-grades it.

**Bar at discovery.** A contrast clears discovery only when all four hold.

1. The permutation p is ≤ its α, and the bootstrap CI at level 1 − α excludes 0.
2. The absolute gap, or interaction, is ≥ 0.10 R.
3. Every evaluable check in the robustness battery keeps the sign.
4. No PBO veto.

The battery has eleven checks, `RB1` to `RB11`. A check is evaluable when each side has ≥ 15 positions. At least six must be evaluable, or the contrast reads `NOT ROBUST-TESTABLE`. See [Robustness battery](../../../pre-registrations/f1_selection/benchmark/ticker_class_regime.md#robustness-battery) for the list.

The PBO diagnostic is a CSCV over discovery-window months, choosing the best of `C1`–`C5`. It needs ≥ 8 months. A PBO above 0.50 vetoes every discovery verdict graded at that run.

**Confirmation.** A contrast that clears discovery is `PROVISIONAL`. It must repeat on new dates, until `GR0` and `GR1` pass again on those dates alone. The gap needs the same sign and a one-sided permutation p ≤ 0.05, and `RB1`, `RB4` and `RB5` must hold. Two years after discovery, a contrast still without power reads `UNCONFIRMED`, final.

## Possible verdicts

| Token | What it means |
|---|---|
| `REGIME-DEPENDENT (trend)` or `(vol)` | `I1` or `I2` is confirmed |
| `INDEX-BETTER-IN-<cell>` or `INDEX-WORSE-IN-<cell>` | `C1`–`C5` confirmed, by sign |
| `PROVISIONAL` | Discovery cleared; confirmation pending |
| `FAILED-CONFIRMATION` | Confirmation powered and failed |
| `UNCONFIRMED` | Confirmation sunset reached without power |
| `NULL` | Discovery graded and did not clear. No evidence, never proof the gap is regime-free |
| `NOT ROBUST-TESTABLE` | Discovery significant and large, but fewer than six checks evaluable |
| `STILL-OPEN` | Not yet powered, before the sunset |
| `UNDERPOWERED` | `GR5` |

## What could ship

Nothing ships. Only a confirmed verdict files "to be tested" in `research/deployment-evidence.md`. A `PROVISIONAL` result files nothing.

## What this study cannot tell you

- Anything about in-sample dates. The exploratory in-sample read is never pooled with forward rows or cited as support.
- Whether `ticker_class`'s verdicts were right. They stand and are not re-graded.
- Anything from the model's own regime text, except as one robustness check (`RB9`).
- Anything soon. The draft estimates 5 to 20 months for a cell's G1 side to reach 60 positions, and its sunset is 2028-04-07.
- Whether a regime filter or exit rule would work. It changes no production code.
