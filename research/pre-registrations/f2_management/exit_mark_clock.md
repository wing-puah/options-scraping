## exit_mark_clock — does a closing-mid daily mark make better exits?

<!-- outcome:start -->
> Latest outcome: not run.
<!-- outcome:end -->

_Registered 2026-10-29._

Registered after an in-sample replay that showed the effect. That replay is disclosed below and is not evidence. Only rows signal-dated after the registration date are graded.

## The question

Production marks each leg every day on its closing mid. A leg whose closing quote is junk (`simulate._is_junk_quote`) is marked differently, by `simulate.junk_day_mark`:

- if the contract traded that day, at its last trade (`barchart_last`), a print at an unknown time;
- else at an older good mark, carried (`barchart_stale`).

A spread's legs can then be marked at different times. Exit rules fire on that mark.

The question: if every leg with a two-sided quote is marked on its closing mid every day, do the exits that change earn more than the exits they replace, on new data?

## What this study is not

- It does not change entry pricing. Entries already use the closing mid (ruling 2026-10-23).
- It does not test exit rules. The exit config stays as `config/backtest.yml` holds it.
- It does not test the live account. It tests how the backtest books an exit.
- It ships nothing by itself. Adoption is a pricing ruling for the operator.

## Definitions

- **Junk day**: a day a leg's closing quote is junk under `_is_junk_quote`.
- **Two-sided**: `0 < bid <= ask`, the condition under which `simulate._close_mid` returns a value.
- **Affected row**: a row whose outcome triple `(exit_reason, days_held, round(realized_pnl_abs, 2))` differs between the two arms.
- **Affected date**: a signal date with at least one affected row.
- **Per-date delta**: the sum over that date's rows of `realized_pnl_abs` (ARM M − ARM P), net of costs.

## Dependencies

- Production's engine, `scripts/backtest/simulate.py::_simulate`, run cache-only on each row's stored legs, the way `--reprice-stale` re-simulates.
- The option history cache. The study makes no network call and writes no tab.

## Population and basis, fixed here

- **Era**: v4, read through `lib/era.py`.
- **Rows**: multi-leg rows (two or more legs) on the BacktestResults export (PRIMARY) and the BacktestProxy export (SECONDARY), signal-dated AFTER the registration date.

  _Resolved at build (2026-10-29):_ every such date sits inside the holdout seal (`holdout_seal`, from 2026-09-23). This study is not a named reader, and that list is closed. The graded set therefore stays empty, and the verdict `UNDERPOWERED`, until `SEAL_LIFTED` is set. The descriptive in-sample block also omits sealed dates, so its figures differ from the table below.
- **Exits counted**: every exit reason. A row still `open_at_data_end` in either arm is excluded from the grade until both arms close it.
- **Single-leg rows**: printed as a descriptive line, never graded.
- **Config**: `config/backtest.yml` as committed on the registration date.

## Plan-time observations, disclosed

The replay on 2026-10-29 used all v4 rows then on the exports. It is in-sample and chose this arm after seeing it, so it is not evidence.

| Tab, multi-leg | Dates | Affected dates | Total delta | Median per-date delta | Positive dates |
|---|---|---|---|---|---|
| Results | 272 | 169 | +$27,481 | −$1 | 84 |
| Proxy | 271 | 183 | +$39,061 | +$2 | 95 |

The total is positive but the median date is flat. A few large rows carry the gain, mostly cancelled dollar stops. About 62% of dates were affected, so 25 affected dates should take about 40 new signal dates. That is an expectation, not a commitment.

The unpatched engine reproduced 99.9% of stored results rows and 98.4% of stored proxy rows.

## What it compares

| Arm | Daily mark on a junk day |
|---|---|
| `ARM P` | Production as it is: last trade, else a carried good mark, with the no-bid ceiling |
| `ARM M` | Closing mid when the quote is two-sided; otherwise exactly `ARM P` |

### `ARM P`

`simulate.junk_day_mark` unchanged.

### `ARM M`

On a junk day with a two-sided quote, the leg's mark is `_close_mid` of that day's row, tagged `barchart`. A junk day with no bid falls through to `ARM P`, so the no-bid ceiling stays. The spread clamp (`helpers._defined_risk_bounds`), exit deferral, costs and every exit rule are the same in both arms.

## How it is judged

- **Unit**: the affected date.
- **Estimators**: the total and the median of per-date deltas over affected dates; the total in each chronological half of affected dates.
- **Descriptive lines**, printed and not graded:
  - the share of fired exits that land on a junk day, in each arm;
  - the count of `profit_target` exits with a negative net, in each arm;
  - deltas split by original exit reason.

## Gates

- **G-REPRO**: `ARM P` must reproduce at least 98% of the stored graded rows on their outcome triple. Below that, the study refuses; it does not grade.
- **G-THIN**: at least 25 affected dates on the PRIMARY tab. Below that, the verdict is `UNDERPOWERED` and only the census prints.
- **G-LOOK**: a day's mark in either arm reads only that day's row, or for `ARM P` an earlier one. A mark that reads a later row refuses the run.

## Bar for a candidate

All of these, on the PRIMARY tab:

1. Total per-date delta > 0.
2. Median per-date delta > 0.
3. Total per-date delta > 0 in each chronological half of affected dates.

## Verdicts, worded now

| Verdict | Condition |
|---|---|
| `CANDIDATE` | G-THIN met and all three bar clauses met |
| `CONTRARY` | G-THIN met, total < 0 and median < 0 |
| `NULL` | G-THIN met, neither of the above |
| `UNDERPOWERED` | G-THIN not met |

The SECONDARY tab gets the same verdict wording, printed beside the PRIMARY one. It never upgrades or downgrades the PRIMARY verdict.

## Anti-tuning

- One alternative mark only. No other junk-day rule (bid, ask, last trade clipped to the quote, a width cap) is tried on the graded rows. A new rule needs its own registration.
- The junk-quote rule (`_is_junk_quote`) and its threshold stay as committed on the registration date.
- No re-grade on a narrower population after a read.

## What could ship

`CANDIDATE` lets the operator rule that the backtest marks a two-sided junk-day leg at its closing mid. The v4 tabs would then be re-priced with `--redo`. Any other verdict leaves `junk_day_mark` as it is. Live trading is not affected either way.
