## baseline_read — do the flow baseline's hedging metrics forecast SPY?

<!-- outcome:start -->
> Latest outcome: BaselineDaily (unversioned), run 2026-10-23 ·
> [record](../../../study-results/f1_selection/regime/baseline_read.md)
>
> ```
> >>> baseline_read P1 (index put share, top quintile of 60-session window vs rest, 21d SPY return): NULL <<<
> >>> baseline_read P2 (same cut, 21d drawdown depth): NULL <<<
> >>> baseline_read READ (P1+P2, Holm m=2): NO-FORECAST <<<
> >>> baseline_read SECONDARY (ETF put share S1/S2, breadth S3/S4, Holm m=4): S1 NULL S2 NULL S3 NULL S4 NULL <<<
> >>> baseline_read FORWARD (signal dates from 2026-09-23, read after the seal lifts): STILL-OPEN <<<
> ```
<!-- outcome:end -->

_Registered 2026-10-23._

## The question

Does heavy hedging in the day's own flow, measured mechanically, come before weaker SPY returns
or deeper SPY drawdowns over the next 21 sessions?

The operator remembers that heavy hedging in the flow precedes market falls. No study has tested
that. [`market_read`](market_read.md) tested the model's MARKET label and printed `NO-FORECAST`.
This study tests the metric the model was reading: the daily flow baseline that
`lib/baseline.py` computes from each day's own scrape, with no model involved.

Two primary contrasts answer the question. Both compare `HEAVY` dates with `REST` dates on the
index put share `M1` (labels in [`arm-index.md`](../../../arm-index.md#baseline_read)):

- **P1.** Mean 21-session forward SPY log return, `HEAVY` minus `REST`.
- **P2.** Mean 21-session SPY drawdown depth, `HEAVY` minus `REST`.

Four secondaries repeat both outcomes on two other baseline metrics:

- **S1, S2.** Return and drawdown on the ETF-section put share `M2`.
- **S3, S4.** Return and drawdown on put-dominance breadth `M3`.

## What this study is not

- **Not a test of the model's label.** That is `market_read`. This study reads no analysis row.
- **Not a selection, sizing or exit rule.** It reads no position, no tier and no R. Its outcome
  is SPY's own path.
- **Not a test of the raw level.** Index puts outweighing calls is the everyday norm, so the
  graded signal is the trailing percentile. A level twin is printed only.
- **Not pooled across eras.** The `BaselineDaily` tab is unversioned. There is one population and
  no `--era` replication.
- **Not a re-test of the 2026-10-22 pass.** That pass read VIX and SPY at entry against trade
  return. It is a different question.
- **Not a ship.** A confirmed read files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md) and changes no production code.

## Definitions

### The metrics

Every metric is computed per baseline row from that row's own cells. A cell counts when it parses
as a finite number.

| Label | Name | Definition | Role |
|---|---|---|---|
| `M1` | `idx_put_share` | (`spy_put_prem` + `qqq_put_prem` + `iwm_put_prem`) / (those three + `spy_call_prem` + `qqq_call_prem` + `iwm_call_prem`) | Graded: P1, P2 |
| `M2` | `etf_put_share` | 1 / (1 + `etfs_cp_prem`) | Graded: S1, S2 |
| `M3` | `breadth` | `stocks_pct_put_dom`, the share of the top 50 stocks by premium whose put premium exceeds call premium | Graded: S3, S4 |
| `M4` | `stock_put_share` | 1 / (1 + `stocks_cp_prem`) | Printed only |
| `M5` | `idx_put_dollars` | `spy_put_prem` + `qqq_put_prem` + `iwm_put_prem` | Printed only |

- **Blank `M1`.** Any of its six cells blank, or a denominator of 0.
- **Blank `M2`, `M4`.** The ratio cell blank or negative. `etfs_cp_prem` is call premium over put
  premium for the ETF section, so `M2` is that section's put share by premium.
- **Blank `M3`, `M5`.** Any of their cells blank.

### The trailing percentile

- **Order.** Baseline rows sorted by `date`. Row order, not the calendar, defines the window.
- **Window.** For row `d`, the `W = 60` rows strictly before `d`. `W` is
  `lib.baseline.WINDOW_ROWS`, the production window.
- **Percentile.** `pct_d` = (count of window values below today's + half the count equal to it) /
  count of numeric window values. A midrank share, from 0 to 1.
- **Window floor.** At least 50 numeric values in the window. Below it the date is out for that
  metric, and counted.
- **Edges.** The first 60 rows have no full window and are out. A blank value today is out.
- **Production differs.** `lib/baseline.py::percentile_of` counts values at or below today, and
  `select_window` also drops rows older than 120 calendar days. This study uses neither rule.

### HEAVY and REST

| Cell | Rule |
|---|---|
| `HEAVY` | `pct_d` at or above 0.80 |
| `REST` | `pct_d` below 0.80 |

A date with no percentile is in neither cell.

Why 0.80. The analysis method file reserves strong labels for "roughly the outer quintile of the
window (≤20th / ≥80th percentile)" (`config/prompts/analysis-methods/claude.md`, lines 52–54).
The framework defines its hedge-pressure qualifier HP as "index/sector at/near highs while large
downside hedging accumulates" (`config/prompts/analysis-framework.md`, lines 56–60).

`HEAVY` on `M1` is the hedging half of HP. The printed cut `HP-MECH` adds the "near highs" half
through the mechanical BULL label.

### Calendar and outcomes

- **Calendar.** The SPY sessions with a non-blank close in
  `backtests/mech_regime/spy_vix_daily_full.csv`, read by `market_read.load_calendar`. A
  baseline date must be an exact session. An off-calendar date is dropped and counted.
- **Outcomes.** `market_read.outcomes`, imported unchanged, plus two printed checks that look
  backward. `c` is SPY's unadjusted close and `i` the date's session index.

| Outcome | Definition | Role |
|---|---|---|
| `ret21` | `ln(c[i+21] / c[i])` | Graded: P1, S1, S3 |
| `dd21` | `−mae21`, where `mae21 = min(0, min(c[i+1..i+21]) / c[i] − 1)`; zero or positive | Graded: P2, S2, S4 |
| `ret5`, `ret10` | `ln(c[i+h] / c[i])` | Printed only |
| `ret21_next` | `ln(c[i+22] / c[i+1])`, the window starting at the next close | Printed only |
| `rv21` | SD of the 21 daily log returns ending at `i+21`, % per day | Printed only |
| `ret0` | `ln(c[i] / c[i−1])`, the same day's move | Printed only |
| `ret_prev5` | `ln(c[i] / c[i−5])`, the five sessions before | Printed only |

Every outcome prints in percentage points. `ret0` and `ret_prev5` read no close after `i`. They
show whether heavy hedging comes with a fall already under way.

### Bootstrap block

A block is `i // 21` (`market_read.block_of`): a fixed 21-session run of the SPY calendar. All
dates in one block travel together in every draw.

### Collection mode

`market_read.lag_bin` on `created_datetime` minus `date`, in days. The mode partitions dates for
printed cuts. It never predicts.

| Mode | Lag |
|---|---|
| `LIVE` | 0 or 1 day |
| `NEAR` | 2 to 7 days |
| `RETRO` | more than 7 days |
| `UNKNOWN` | blank, or negative |

### Mechanical direction

`MechLabeler.label(d)` from `lib/mech_regime.py`, kept when `ok` is true and the mapped date
equals `d`. It is used for printed strata only.

## Dependencies

- `backtests/to_evaluate/analysis - BaselineDaily.csv`, from
  `python3 scripts/export_tabs.py --tabs BaselineDaily`.
- `lib/baseline.py`: `BASELINE_COLUMNS` and `WINDOW_ROWS`, read unchanged.
- `backtests/mech_regime/spy_vix_daily_full.csv` and `lib/mech_regime.py::MechLabeler`. Refresh
  the table with `make mech-regime` before a forward run.
- `market_read`'s helpers, imported and never copied: `load_calendar`, `outcomes`, `block_of`,
  `lag_bin`, `Draws`, `mean_diff`, `summarize`, `arm_floor`, `holm`, `ci`, `section`.
- `scripts/backtest_study/lib/era.py`: `requested_era`, `CURRENT`, `drop_sealed`, `seal_line`,
  `SEAL_START` and `SEAL_LIFTED`.
- `scripts/backtest_study/lib/protocol.py::window_cuts`.

## Population and basis, fixed here

- **Era.** The tab is unversioned. Only the default era `current` runs. Any other `STUDY_ERA`,
  such as `--era v3`, refuses (exit 2) with a one-line message.
- **Report header.** The report prints `era: current (inputs are unversioned)` and
  `population: BaselineDaily (unversioned tab), <n> rows, <first> → <last>`, beside the git sha,
  the dirty flag and the inputs read.
- **Header check.** A missing file, or a header that is not exactly `BASELINE_COLUMNS`, refuses
  (exit 3).
- **Seal.** `era.drop_sealed(rows, date_key="date")`, with no reader, and `seal_line` prints the
  count. This study is not in `era.SEALED_READERS` (see the
  [holdout seal](../../f4_deployment/holdout_seal.md) and the
  [sealed window](../../../glossary.md#sealed-window)).
- **Windows may cross the seal.** The seal binds signal dates. A pre-seal date's 21-session SPY
  window may run past 2026-09-23.
- **In-sample: P1, P2, S1–S4.** Rows from the 61st on, on exact sessions, dated before
  `era.SEAL_START`, with a closed 21-session window. This stays true after the seal lifts.
- **Forward.** Signal dates on or after `era.SEAL_START` with closed windows. None is read until
  `era.SEAL_LIFTED` is set.
- **Closed windows.** Every window date must fall after `d`. A window past the table's end is
  dropped and counted.
- **Drops, each counted and printed.** Off-calendar dates, the first 60 rows, sealed rows,
  windows past the end, and per metric the blank and thin-window dates.

## Plan-time observations, disclosed

Every figure below was counted on 2026-10-23, before this file was written. No outcome was read:
no forward SPY return, drawdown or volatility was computed on any date. The metric percentiles
and the mechanical label, which reads trailing closes only, were computed.

_Export: `backtests/to_evaluate/analysis - BaselineDaily.csv`, pulled 2026-10-23._

### The export

| Fact | Count |
|---|---|
| Rows, one per date | 681, from 2024-01-04 to 2026-10-22 |
| Duplicate dates; off-calendar dates | 0; 0 |
| SPY sessions spanned | 703, so 22 sessions have no baseline row |
| Session span of a 60-row window | 60 to 69 sessions |
| Rows with the six index cells and `etfs_cp_prem` blank | 9 |
| Rows with a blank `stocks_pct_put_dom` | 0 |
| Rows on sealed dates (from 2026-09-23) | 22 |

The 22 missing sessions fall in short runs, the longest four sessions (2024-10-22 to 10-25,
2025-09-29 to 10-02). The nine blank-cell rows are scattered from 2024-10-21 to 2026-03-18.

### Two collection modes

The rows were built in two ways. The `RETRO` rows were rebuilt after the fact from historically
scraped flow files. The `LIVE` rows come from each session's compiled intraday snapshots. Both
run the same mechanical code, with no model and no hindsight, but coverage may step at the seam.

| Lag bin | Rows | Dates |
|---|---|---|
| `RETRO` | 584 | 2024-01-04 to 2026-06-08 |
| `NEAR` | 4 | 2026-06-04 to 2026-06-11 |
| `LIVE` | 93 | 2026-06-10, then 2026-06-12 to 2026-10-22 |

`created_datetime` runs from 2026-06-11 to 2026-10-23. The mode cut is printed, never graded.

### The in-sample population

599 dates, from 2024-04-02 to 2026-09-22, in 31 blocks.

| In-sample mode | Dates | Blocks touched |
|---|---|---|
| `RETRO` | 524 | — |
| `NEAR` | 4 | — |
| `LIVE` | 71 | 4 |

| Metric | Dates with a percentile | `HEAVY` dates / blocks | `REST` dates / blocks |
|---|---|---|---|
| `M1` | 590 | 149 / 28 | 441 / 31 |
| `M2` | 590 | 134 / 26 | 456 / 31 |
| `M3` | 599 | 137 / 28 | 462 / 31 |

- **More than a fifth.** `HEAVY` holds 25% of `M1` dates. A trailing percentile is not uniform
  when the level drifts.
- **Overlap.** 105 of the 149 `M1` `HEAVY` dates are also `M2` `HEAVY`. 58 are also `M3`
  `HEAVY`.

### Heavy index hedging sits with a falling tape

| `M1`, by mechanical direction | `HEAVY` | `REST` |
|---|---|---|
| BULL | 56 | 339 |
| RANGE | 20 | 41 |
| BEAR | 73 | 61 |

93 of the 149 `HEAVY` dates are not mech BULL. The mechanical label reads trailing closes, so
heavy index hedging often arrives while SPY is already falling. `ret0` and `ret_prev5` are printed
for that reason. It also means P1 partly repeats the mechanical direction.

### The levels

| Metric level, all rows | Median | Share above 0.5 |
|---|---|---|
| `M1` | 0.66 | 79% |
| `M2` | 0.55 | 61% |
| `M3` | 0.42 | — |

Index puts outweigh calls on most days, as the `lib/baseline.py` docstring says. That is why the
graded signal is the percentile, not the level.

### The prior

`market_read` (2026-10-23, v4) printed `NO-FORECAST` for the model's label. Two of its printed
twins bear on this study. Neither was graded.

| `market_read` printed twin | Difference in `dd21` | CI |
|---|---|---|
| HP-labelled dates minus the rest, stratified | −0.55 pp | [−1.19, −0.02] |
| E-VOL minus the rest, stratified (its P3, `NULL`) | +1.08 pp | [−0.13, +3.08] |

HP-labelled dates were followed by shallower drawdowns, not deeper ones. That is the prior. This
study tests the mechanical metric behind the label.

### Other disclosures

- **One graded cell.** One threshold and one window are graded, taken from the production window
  and the method file's outer-quintile phrase. The grid is printed only. No arm was tuned on
  outcomes.
- **The seal.** It withholds the 22 rows dated from 2026-09-23.
- **A different question.** The unregistered 2026-10-22 pass found no rank correlation between
  VIX or SPY at entry and trade return. It read positions, not SPY's path.

## What it compares

| Object | Object type | Contrast | Role |
|---|---|---|---|
| `HEAVY`, `REST` | cell | `pct_d` at or above 0.80, and below it | The two arms of every contrast |
| P1 | arm | Mean `ret21`, `M1` `HEAVY` minus `REST` | Primary, Holm m = 2 |
| P2 | arm | Mean `dd21`, `M1` `HEAVY` minus `REST` | Primary, Holm m = 2 |
| S1, S2 | arm | `ret21`, `dd21` on `M2` | Secondary, Holm m = 4 |
| S3, S4 | arm | `ret21`, `dd21` on `M3` | Secondary, Holm m = 4 |
| `M4`, `M5` | descriptive cut | `ret21`, `dd21` on each | Printed only |
| FORWARD | population scope | P1 and P2 on signal dates from 2026-09-23 | Forward verdict |

### P1 and P2, the index put share

P1 asks whether SPY earned less after heavy index hedging. P2 asks whether it fell further. A
`HEAVY` date has its `M1` in the top fifth of its own trailing 60-row window.

### S1 to S4, the other two metrics

The same two outcomes on `M2`, the whole ETF section's put share, and on `M3`, the stock breadth.
They carry no combined word.

### Printed only, never graded

Each line prints its n, and a CI wherever it shows a mean.

| Label | What it prints |
|---|---|
| `DOSE` | Mean `ret21` and `dd21` by `pct_d` fifth (Q1 below 0.20 … Q5 at or above 0.80), for `M1`, `M2`, `M3` |
| `RHO` | Spearman rho between `pct_d` and `ret21`, and `dd21`, per metric, with a block-bootstrap CI |
| `LEVEL` | The level twin: an expanding percentile over every prior row, 60 or more numeric, at or above 0.80; the same six contrasts |
| `GRID` | P1 and P2 at thresholds 0.70, 0.80, 0.90 by windows 40, 60, 90; (0.80, 60) is the graded cell |
| `MECH` | P1 and P2 inside mech BULL, and inside mech non-BULL (RANGE and BEAR) |
| `HP-MECH` | `HEAVY` on `M1` and mech BULL, against every other date, on `ret21` and `dd21` |
| `CUTS` | The six graded contrasts excluding March–April 2025, and excluding February–April 2026 (`protocol.window_cuts`) |
| `HALVES` | P1 and P2 on the first and second half of the dates by session order, with sign agreement |
| `MODE` | P1 and P2 on `RETRO` dates only and on `LIVE` dates only; mean `M1`, `M2`, `M3` by mode |
| `BOUNDARY` | Mean `M1` over the 60 rows before the first `LIVE` row, against the 60 rows from it |
| `H5`, `H10` | P1 on `ret5` and `ret10` |
| `NEXT` | P1 and P2 with the window starting at the next session's close |
| `B42` | The six graded contrasts on 42-session blocks |
| `TAIL` | Per arm, the share of dates with `mae21` below −3% and below −5% |
| `CONC` | `ret0` and `ret_prev5`, `HEAVY` minus `REST`, per metric |
| `YEAR` | `M1`'s level and `HEAVY` share by calendar year |
| `POWER` | The design-power table, below |
| `COUNTS` | Blank and out-of-window dates per metric |

The `GRID` window floor scales with the window, at five sixths of it, rounded up. The first `W`
rows are out in each cell, so its populations differ slightly.

| `GRID` window | Numeric values needed |
|---|---|
| 40 | 34 |
| 60 | 50 |
| 90 | 75 |

## How it is judged

- **Bootstrap.** Resample blocks with replacement, as many as the population holds, for 10,000
  draws. The seed is 20261023.
- **Shared draws.** P1, P2, S1–S4 and every printed contrast on the in-sample population share
  one draw set. A printed cut on a sub-population (`CUTS`, `HALVES`, `MODE`, `MECH`) resamples its
  own blocks from the same seed.
- **CI.** The 95% percentile interval ([CI](../../../glossary.md#ci95-date-clustered-bootstrap),
  here clustered by block, not by date). Every CI prints its half-width, so a `NULL` reads "spans
  0 at ±x".
- **p-values.** Two-sided, from the same draws: twice the smaller of the share of draws at or
  below 0 and the share at or above 0, capped at 1. A draw with an empty arm is discarded and
  counted.
- **Sensitivity.** The `B42` cut, printed and never graded.

**Multiple comparisons.**

- P1 and P2 form one Holm family with m = 2.
- S1 to S4 form one Holm family with m = 4.
- A contrast that is `UNDERPOWERED` enters its family at p = 1.
- A CI word stands only when its Holm-adjusted p is below 0.05. Otherwise the contrast prints
  `NULL`. The report prints the word before Holm beside it.

## Gates

- **GE, inputs.** The baseline export and the SPY/VIX table exist, the baseline header is exactly
  `BASELINE_COLUMNS`, and every in-sample window closes inside the table. Any failure refuses
  (exit 3).
- **GC, population.** Each metric's in-sample population holds at least 300 dates. A metric below
  it prints `UNDERPOWERED` on its contrasts.
- **GF, floors.** Each arm holds at least 20 dates in 12 blocks, for P1 and P2. The same floor
  applies to S1–S4. Below it, or with a NaN statistic, the contrast prints `UNDERPOWERED`.
- **GP, planted power.** Below.
- **Era.** Any era but `current` refuses (exit 2).

### GP, planted power

GP asks whether a real 3-point effect would be seen on this population at all.

- **Simulations.** 200, seed 20261024.
- **Each simulation.** Shuffle the `M1` `HEAVY` and `REST` labels within each block, keeping each
  block's `HEAVY` count. Add −3 pp to `ret21` and +3 pp to `dd21` on the shuffled `HEAVY` dates.
  Re-run P1 and P2 with 2,000 draws.
- **Detection.** P1's CI wholly below 0. P2's CI wholly above 0.
- **Pass.** Both detection rates at or above 0.80. Otherwise P1, P2 and READ print `UNDERPOWERED`.

The shuffle keeps each block's `HEAVY` count, so any difference between blocks stays in every
simulation.

**Design power.** The same simulation, printed only, at each planted shift below.

| Design power | Value |
|---|---|
| Shifts on `ret21` | ±1, ±2, ±3 pp; `dd21` takes the opposite sign |
| Simulations per shift | 100 |
| Seed | 20261025 |

A negative shift on `ret21` is on the warning side and a positive one on the contrarian side. Detection is a CI wholly on the planted side. A `NULL` is read at the size
this table says the study could detect.

### Floors

| Contrast | Floor |
|---|---|
| P1, P2, S1–S4 | 300 in-sample dates on the metric (GC); 20 dates and 12 blocks per arm (GF) |
| FORWARD | 20 dates and 6 blocks per arm, all with closed 21-session windows |

## Bar for a candidate

No contrast here can make a candidate rule. A `WARNS` or `CONTRARIAN` READ is the bar for filing
"to be tested", pending the forward read.

## Verdicts, worded now

**Each contrast on `ret21` (P1, S1, S3):**

| Token | When |
|---|---|
| `HEDGE-WARNS` | Floors met, CI wholly below 0: heavy hedging came before weaker SPY |
| `HEDGE-CONTRARIAN` | Floors met, CI wholly above 0 |
| `NULL` | Floors met, CI spans 0; printed with its half-width |
| `UNDERPOWERED` | A floor or gate unmet, or the statistic is NaN; census printed, nothing concluded |

**Each contrast on `dd21` (P2, S2, S4).** The signs flip.

| Token | When |
|---|---|
| `HEDGE-WARNS` | Floors met, CI wholly above 0: deeper drawdowns after heavy hedging |
| `HEDGE-CONTRARIAN` | Floors met, CI wholly below 0 |
| `NULL` | Floors met, CI spans 0; printed with its half-width |
| `UNDERPOWERED` | A floor or gate unmet, or the statistic is NaN |

The graded word is the CI word only when the Holm-adjusted p is below 0.05. Otherwise it is
`NULL`.

**READ, combining P1 and P2.** The first matching row wins.

| P1 and P2 | READ | In plain words |
|---|---|---|
| Either `UNDERPOWERED` | `UNDERPOWERED` | Too few dates, or too little power, to judge |
| Both `NULL` | `NO-FORECAST` | Heavy index hedging forecast neither |
| `HEDGE-WARNS` present, no `HEDGE-CONTRARIAN` | `WARNS` | Heavy hedging came before a weaker or deeper-falling SPY |
| `HEDGE-CONTRARIAN` present, no `HEDGE-WARNS` | `CONTRARIAN` | Heavy hedging came before a stronger or shallower SPY |
| Both present | `MIXED` | The two outcomes point opposite ways |

S1 to S4 take the contrast words and carry no READ word.

**FORWARD.** P1 and P2 on forward dates use the same words and the same Holm family (m = 2), on
the forward population's own blocks. `STILL-OPEN` takes the place of `UNDERPOWERED`. The FORWARD
line prints their READ combination. The verdict of record for the standing claim is the first
forward run that prints a token other than `STILL-OPEN`. Later forward runs are descriptive.

**The banner.** The report's section titled VERDICT prints:

```
>>> baseline_read P1 (index put share, top quintile of 60-session window vs rest, 21d SPY return): <word> <<<
>>> baseline_read P2 (same cut, 21d drawdown depth): <word> <<<
>>> baseline_read READ (P1+P2, Holm m=2): WARNS | CONTRARIAN | MIXED | NO-FORECAST | UNDERPOWERED <<<
>>> baseline_read SECONDARY (ETF put share S1/S2, breadth S3/S4, Holm m=4): S1 <w> S2 <w> S3 <w> S4 <w> <<<
>>> baseline_read FORWARD (signal dates from 2026-09-23, read after the seal lifts): STILL-OPEN <<<
```

## Anti-tuning

- Fixed here: the five metric definitions, the 60-row window and its floor of 50, the 0.80
  threshold, the midrank rule, the outcomes, the 21-session horizon and block, the floors, the
  seeds and the verdict words.
- Every printed-only cut is printed as it falls. None is used to re-grade.
- No other metric, threshold, window or horizon is graded.
- This registration is immutable in substance from 2026-10-23. Editorial consolidation only.

## What could ship

Nothing ships from this study.

- A `WARNS` or `CONTRARIAN` READ files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md), pending the forward read.
- The shipped [sizing rule](../../../../docs/deployment-rules.md#s2-sizing) stays on the
  mechanical [dip flag](../../../glossary.md#dip-date).
- No verdict here changes a tier, a veto, a size class or an exit.
