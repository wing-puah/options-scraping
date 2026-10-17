# staged_exit — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f2_management/staged_exit.md); where the two differ, the registration wins.
> Latest outcome: no full PRIMARY v3 verdict is recorded. On v4, which is not PRIMARY: one `staged_exit ARM E` cell (X = 5, R ≥ +0.50) `REACTIVE-AGAIN`. 39 `staged_exit ARM T` cells `UNDERPOWERED`. 56 cells carry no verdict word. No `CANDIDATE` — 2026-09-28 · [record](../../study-results/f2_management/staged_exit.md).
> Nothing else here is a result.

## The question

Does a time-staged exit switch beat the shipped exit profile? The rule is the operator's own: by session X, if the position is ±Y against its original entry, do A. Otherwise continue exactly as shipped.

The signal, entry day, structure, sizing and candidate set are all frozen. An arm changes only what happens to an open position at one pre-declared session.

This is not a fourth drawdown-from-peak trail. Three such trails failed, because a trail re-arms on every new peak and fires on noise. All 21 debit trail exits sold continuations. A staged switch evaluates once, at a fixed session, against the original entry. It cannot re-fire.

## What it compares

Every arm is paired against the shipped book, never against a clean `DEBIT_PROD`. The shipped book uses the production profiles, including the bear-keyed variants.

| Object | What it does | Kind |
|---|---|---|
| [staged_exit ARM E](../../arm-index.md#staged_exit-arm-e) | Replays the shipped profile untouched. If the position is still open at X and the band holds, it overrides the result to exit at that mark. No fork of the harness | arm (the headline) |
| [staged_exit ARM T](../../arm-index.md#staged_exit-arm-t) | At X, tightens the stop to −0.40, or arms a trail at 0.50 / 0.50. Uses a local copy of `harness.replay`, with the peak carried across the swap | arm (transfer test) |

The `ARM T` action values are the shipped `BEAR_HE` values. They are a transfer test of a deployed setting, not a new knob. Nothing is searched.

The frozen grid:

| Dimension | Values |
|---|---|
| Switch session X | 5, 10, 15, 20 |
| Profit condition | R ≥ +0.50 · R ≥ +0.25 |
| Loss condition | R ≤ −0.25 · R ≤ −0.50 |
| Parallel dollar cut | ±$250 · ±$500, reported alongside R |
| Else-branch | Always "continue shipped profile" |

## How it is judged

**Population.** PRIMARY is `--era v3`, 118 dates, the proxy calibration gate on, no Black-Scholes rows. The `current` (v4) era is reported and carries nothing. Eras are never pooled. Credits are included and priced under `CREDIT_PROD`.

**In scope at X.** Only rows whose shipped replay survives past X (`days_held > X`). A row that already exited is untouched and excluded from the paired test at that X.

**Credit rows.** `ARM T`'s tighten action introduces a stop on credit rows, whose shipped profile has no stop. That is the registered action.

**Metric.** Within-row paired [ΔR](../../glossary.md#r), staged minus shipped, aggregated by date with a paired date-clustered bootstrap (`BOOT_N = 10000`, α = .05). Contract counts are identical across arms, so dollars print as a sanity read. R is what every conclusion quotes.

**Gates.** Each gate exits non-zero on failure, in this order.

- `G0`: a cell with under 25 affected dates or under 60 affected rows is power-stopped. No criterion is evaluated on it.
- `G1`: a staged arm must change zero rows outside its population. Every row with `days_held <= X` must come back byte-identical.
- `G-FORK` (`ARM T` only): with `stage1 == stage2`, the fork must reproduce `harness.replay` exactly on all 795 rows at every X, and on the `tests/test_harness_replay.py` fixture.
- `G2`: the continuation diagnostic, which is a pass criterion. A cell whose staged exits are a majority followed by a post-exit path maximum above realized + 0.30 R fails, whatever its ΔR.

**Bar for a candidate.** A cell must clear all seven clauses.

1. Paired ΔR > 0 versus the shipped book, with the CI excluding zero.
2. Every leave-one-date-out fold is positive.
3. The cell survives `window_cuts` and the hand-added cut that drops both dominant windows.
4. The cell is positive in every calendar year present.
5. The cell is right-signed on both pricing tiers, real and tweak.
6. The cell has at least 25 affected dates and at least 60 affected rows.
7. The cell passes `G2`.

Worst-decile cells print descriptively, marked NOT A CRITERION.

## Possible verdicts

| Token | What it means |
|---|---|
| `CANDIDATE` | A cell clears all seven clauses. Queued for an independent-window confirmation |
| `REACTIVE-AGAIN` | A cell clears the R conjunction but fails `G2`. The switch sells continuations, as the trails did. Thread closed for these dates |
| `NULL` | Cells clear the CI but fail LOO, the ex-both cut or sign stability. A window artifact |
| `POWER-STOPPED` | `G0` fails for a cell. Census only, nothing read |

## What could ship

Nothing ships from a research-tier study. A `CANDIDATE` queues an independent-window confirmation. Only after that may it be proposed for `deployment-rules.md`.

## What this study cannot tell you

- Whether any exit rule beats the shipped profile on drawdown. That is `exit_drawdown`'s question.
- Anything about a third outcome. The else-branch is always "continue shipped profile".
- Anything about X, conditions or actions outside the frozen grid. Nothing is swept.
- Whether the trail action works. It was expected to be near-inert on this book, so `ARM T` is carried mostly by the tighten stop.
- Anything from the v4 era, which carries nothing.
