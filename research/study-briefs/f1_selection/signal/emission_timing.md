# emission_timing — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/signal/emission_timing.md); where the two differ, the registration wins.
> Latest outcome: no PRIMARY v3 verdict is recorded. On v4, which is not PRIMARY: `ARM P` `NULL`; `ARM L` `LAG-TOLERANT` — 2026-09-28. The same report also prints `CANDIDATE` cells under those verdicts: `ARM P` repeats against the play, and `ARM L` low-tercile lags · [record](../../../study-results/f1_selection/signal/emission_timing.md).
> Nothing else here is a result.

## The question

Does the timing of an entry, relative to the signal, degrade a play? Two questions share this theme. Does a play that the model emits a second time do worse than the first emission? Does an entry filled 1, 2 or 3 sessions after the signal lose the edge?

Selection is closed in this repo, so the study needs new columns to be admissible. It adds two, and an operator can read both at entry: the emission ordinal, and where the underlying travelled before the signal.

## What it compares

Neither arm changes which structures are eligible or how they exit. Shipped profiles replay through the frozen harness.

| Object | What it does | Kind |
|---|---|---|
| [emission_timing ARM P](../../../arm-index.md#emission_timing-arm-p) | Compares repeat emissions with the first emission of the same (ticker, structure). The ordinal is capped at {1st, 2nd, 3rd, 4th+} | arm |
| [emission_timing ARM L](../../../arm-index.md#emission_timing) | Builds a synthetic trade for each lag L ∈ {0, 1, 2, 3} sessions after the signal. Each is compared with L = 0 | arm |

`ARM P` has two frozen sub-cuts, and no third may be added.

1. Consecutive-date repeats versus gapped repeats.
2. Repeats split by whether the underlying had already moved the play's way since the first emission.

`ARM L` is also reported within terciles of the pre-signal `price_vector`. The terciles are cut on the full book and frozen before any lag result is read. Rows with no `price_vector` form a MISSING cell, reported and never imputed.

## How it is judged

**Population.** PRIMARY is `--era v3`, 118 dates, the proxy calibration gate on, no Black-Scholes rows. The `current` (v4) era is reported and carries nothing. The two eras are never pooled.

**Unit and metric.** The unit is the signal date. `ARM P` is the within-date paired Δ(mean R), repeat minus first. `ARM L` is the within-row paired [ΔR](../../../glossary.md#r) against L = 0, aggregated by date. Both use a paired date-clustered bootstrap, `BOOT_N = 10000`, α = .05. R is quoted, never dollars.

**Lag construction.** L = 0 is a day-0 close fill, built the same way as L = 1..3, so only the lag differs. Contracts are re-sized by the production formula at every lag, including L = 0. Marks are right-padded with blanks to the recomputed grid length. The padded-row count prints in every report. A zero entry mark is excluded and counted as `degenerate_zero_entry`.

**Ordinal join.** The ordinal uses `book.py`'s `created_datetime`-sorted keep-first rule. Same-day duplicate emissions collapse to one and cannot fake a repeat.

**Gates.** Each gate exits non-zero on failure, in this order.

- `G0`: at least 25 affected dates per cell. Each tercile lag cell must clear the floor on its own.
- `G1`: every synthetic trade must have `len(marks) == len(grid)`. Any construction failure fails the run.
- `G2`: prints the contract-count census per lag. No dollar figure is quoted across lags.
- `G3`: asserts that no arm reads the signal day's own underlying move.

**Bar for a candidate.** A cell must clear all six clauses.

1. The paired ΔR CI excludes zero.
2. Every leave-one-date-out fold is positive.
3. The cell survives `window_cuts` and the hand-added cut that drops both dominant windows.
4. The cell is positive in every calendar year present.
5. The cell is right-signed on both pricing tiers, real and tweak.
6. The cell has at least 25 affected dates.

Worst-decile cells print descriptively, marked NOT A CRITERION.

## Possible verdicts

| Token | What it means |
|---|---|
| `STALE-ENTRY-PENALTY` | Repeats or lagged fills are reliably worse under the full bar. This proposes an intake rule, queued for an independent window |
| `LAG-TOLERANT` | No lag in {1, 2, 3} separates from L = 0 under the bar. The signal does not decay within three sessions |
| `LAG-SENSITIVE` | The ladder degrades monotonically with L but fails the bar. Directional evidence only, no rule |
| `NULL` | Cells clear a CI but fail the rest. A window artifact |
| `POWER-STOPPED` | `G0` fails for a cell. Census only, nothing read |

## What could ship

Nothing ships from this study. `STALE-ENTRY-PENALTY` would queue an intake rule, to prefer first emissions and fill the same session. That rule needs an independent-window confirmation before it may reach `deployment-rules.md`. `LAG-TOLERANT` is an operator finding in its own right: a missed same-day fill is not a lost trade.

## What this study cannot tell you

- Anything about intraday entry timing. Daily marks cannot represent a fill inside the session.
- Anything about the day-0 underlying move. `next_day_move` `ARM C` tested it, and `G3` enforces that this study does not.
- Anything about dollars across lags, because contract counts differ by construction.
- Anything from the v4 era, which carries nothing.
- Anything from a tercile lag cell under the floor. The registration names this the likeliest stop.
