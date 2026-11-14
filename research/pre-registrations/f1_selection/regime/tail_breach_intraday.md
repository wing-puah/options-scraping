## tail_breach_intraday — SPY's intraday 2σ breaches and 5% weekly falls: how often, and forecastable?

<!-- outcome:start -->
> Latest outcome: `>>> tail_breach_intraday PA (four-predictor logistic, any intraday 2x-VIX breach in the next 5 sessions, test from 2024-01-02): NO-FORECAST <<<` (13 test episodes, gate met); `>>> tail_breach_intraday PB (four-predictor logistic, intraday low 5% below the origin close within 5 sessions, test from 2024-01-02): UNDERPOWERED <<<` (`GN B`: 3 test episodes, floor 10); SA1–SA4 and NA1 `NO-FORECAST`, SB1–SB4 `UNDERPOWERED`; forward `STILL-OPEN` — yfinance OHLC to 2026-11-13, run 2026-11-14 · [record](../../../study-results/f1_selection/regime/tail_breach_intraday.md)
<!-- outcome:end -->

_Registered 2026-11-14._

**STATUS: REGISTERED (ACCEPTED BY DEFAULT 2026-11-14) on the drafter's recommended defaults; the
operator may revisit (a revisit after a result is a NEW registration, never an edit).** Drafted
2026-11-14 on the operator's chosen definitions, with the drafter's defaults for every detail the
operator deferred. No predictor was compared with either event before this file was written. The
breach counts the operator was shown are disclosed under the plan-time observations. A fresh second
reader checked it the same day and found no leakage in the text. Its four blockers and its fixes are
folded in.

## The question

After [`tail_breach`](tail_breach.md) printed `UNDERPOWERED` on 2026-11-14, the operator asked for
two changes. The first measures the breach on the session's intraday low rather than its close. The
second adds a 5% move, because a 5% move makes short-dated options very lucrative.

- **Event A, intraday 2σ breach.** SPY's intraday low falls more than twice the prior close's
  VIX-implied one-day move below the prior close, whatever the close does.
- **Event B, a 5% fall.** SPY's intraday low reaches 5% below the origin close at some point within
  the next five sessions.

The study has two parts.

- **Part 1, measurement.** How often did each event happen in 2024, 2025 and 2026 to date, against
  a normal-law reference? Descriptive; no verdict.
- **Part 2, forecast.** Do the four `tail_breach` volatility readings, taken at the origin close,
  forecast each event better than its long-run base rate? Graded.

The operator was asked on 2026-11-14 whether B should be down only or either direction, and over
one session or five. The answer was down only, over five sessions, the drafter's default.

## What this study is not

- **Not a hedge or option study.** It prices no option and reads no position, tier, R or backtest
  row. The operator's reason for B is the payoff of short-dated options. This study measures only
  whether SPY moves 5%, not what an option on that move would have paid.
- **Not a re-grade of `tail_breach`.** That study's close-basis verdict stands. This one asks new
  questions on new events, with the same predictors and the same scoring.
- **Not a sweep.** Two events, one horizon each, one model and one metric are graded. Every other
  cut is printed only.
- **Not pooled across eras.** The inputs are market data with no prompt version. There is one
  population and no `--era` replication.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price basis

- **Source.** yfinance `SPY`, fetched with `auto_adjust=False`, giving the raw open, high, low and
  close plus `Adj Close`. `^VIX` and `^VIX3M` closes come from the same fetch and are matched to SPY
  sessions by exact date.
- **Total-return low and high.** `L_t = Low_t × F_t` and `H_t = High_t × F_t`, where
  `F_t = Adj Close_t / Close_t`. `A_t` is `Adj Close_t`. This is the same factor yfinance applies to
  every price field when `auto_adjust=True`.
- **Why that basis.** Every event compares a low with an earlier close. On an ex-dividend date the
  raw low falls by the dividend with no loss to a holder. Scaling the low by the same session's
  factor puts it on the adjusted close's basis, so the dividend is not counted as a fall. The raw
  twin, the raw low against the raw prior close, is printed and never graded.
- **Splits.** SPY has never split. Gate `GB` refuses a feed whose close-to-`Adj Close` ratio steps
  like a split.
- **Close timing.** `^VIX` settles at 4:15pm Eastern and SPY closes at 4:00pm, as in `tail_breach`.
  The small bias against breaches is disclosed, not corrected.

### Why the intraday breach rate exceeds the normal-law 2.3%

The VIX-implied move `σ_t` is built from closes and measured from the prior close, over one day's
variance `σ_t²`. It describes the spread of close-to-close returns,
not of the lowest point within a session. A low is always at or below the close, so the share of
sessions whose low crosses `−2σ_t` is higher than the share whose close does. This study does not
correct for that. Instead, Part 1 prints two references beside each rate.

- **The closing law, `Φ(−k)`.** 2.28% at k = 2. The rate a close-basis breach would show under a
  normal law.
- **The reflection law, `2 × Φ(−k)`.** 4.55% at k = 2. The chance that a continuous driftless
  Brownian path dips below `−kσ` at some point during the day. It treats the overnight gap as part
  of the path, which is an approximation.

### Event definitions

`σ_t = VIX_{t−1} / 100 / √252`, as in `tail_breach`. An event is undefined, and the session is out,
when an input it reads is missing.

| Label | Rule | Role |
|---|---|---|
| `A` | `ln(L_t / A_{t−1}) < −k × σ_t`, k = 2 | Event A; graded through `YA5` |
| `A-1.5`, `A-2.5` | The same rule with k = 1.5 and k = 2.5 | Parameters, printed beside it |
| `A-BASIS` | `A` on the raw low and the raw prior close | Printed only |
| `CLOSE` | `tail_breach`'s close-basis `DOWN` event | Printed only, for comparison |
| `B` | `min(L_t … L_{t+4}) ≤ 0.95 × A_{t−1}`, indexed by its first session t | Event B; graded |
| `B-CLOSE` | `B` on adjusted closes instead of lows | Printed only |
| `B-1` | `L_t ≤ 0.95 × A_{t−1}`: a 5% intraday fall on one session | Printed only |
| `B-UP` | `max(H_t … H_{t+4}) ≥ 1.05 × A_{t−1}` | Printed only |
| `B-EITHER` | `B` or `B-UP`: the straddle view | Printed only |

- `A` is strict (`<`) on a log return, as in `tail_breach`. `B` is inclusive (`≤`, `≥`) on a
  simple 5%.
- `B`'s windows overlap. One sell-off flags several consecutive first sessions, so its counts are
  counts of windows, not of independent events. Episodes, below, deal with that.

### Episodes

An **episode** is a run of flagged sessions in which each falls within 5 sessions of the one before.
For `A` the flagged sessions are breach sessions, exactly as in `tail_breach`. For `B` they are the
flagged first sessions. The power floors count episodes, not sessions, because both events cluster.

### Predictors

The four `tail_breach` predictors, computed by that module's own `predictors_at` and imported
unchanged. Each forecast has an **origin**, the close of session t−1. Every predictor reads closes
on the origin or before it, never later.

| Label | Name | Definition |
|---|---|---|
| `X1` | VIX level | `VIX_{t−1}` |
| `X2` | VIX percentile | Midrank share of `VIX_{t−1}` within the 252 VIX closes strictly before the origin |
| `X3` | Term structure | `VIX_{t−1} / VIX3M_{t−1}` |
| `X4` | Realized over implied | 20-session realized vol, from adjusted closes ending at the origin, over `VIX_{t−1}` |

No predictor reads a high or a low. A row with any predictor missing is out, and counted. The first
origin with all four is 2006-07-17, the first VIX3M close.

### Outcomes

| Label | Rule | Role |
|---|---|---|
| `YA5` | 1 if any of sessions t … t+4 is an `A` breach | Event A, primary |
| `YA1` | 1 if session t is an `A` breach | Event A, secondary (`NA1`) |
| `YB` | 1 if `B` flags first session t: the low reaches 5% below the origin close within t … t+4 | Event B, primary |

- A row whose outcome sessions are not all defined is out, and counted.
- `YB`'s outcome sessions are t … t+4, though it is read from `B`'s flag at t. The row split uses
  h = 5 for `YB`, as for `YA5`. So no training row reads a low from 2024, and no test row reads a
  session after the registration date.

### Training and test windows

These are `tail_breach`'s windows and its `split_of` code, imported unchanged.

| Window | Rows |
|---|---|
| Training | Every outcome session before 2024-01-02, all four predictors present, origins from 2006-07-17 |
| Test | First outcome session on or after 2024-01-02, last on or before the registration date |
| Forward | Origin after the registration date |

- **Straddle rows** have outcome sessions on both sides of 2024-01-02. They are in neither window,
  and counted.
- **Gap rows** have an origin on or before the registration date and a last outcome session after
  it. They are in neither window, and counted.
- **Fitting.** Coefficients and the standardisation are fitted on training rows only, once, and
  never refitted. The registration date enters the code as the constant `REGISTERED`.

## Dependencies

- `backtests/tail_breach_intraday/SPY.csv`, `VIX.csv`, `VIX3M.csv` (date, open, high, low, close,
  adj_close), fetched by the module from yfinance. `--refresh` refetches all three. Today's bar is
  never fetched.
- `scripts/backtest_study/f1_selection/regime/tail_breach.py`, imported unchanged. It supplies the
  predictors, the row split, the logistic fit, the Brier skill score, the bootstrap, the verdict
  words and gates `GB` and `GX`.
- `backtests/underlying_ohlc_cache/SPY.csv`, the Barchart cache from 2022-08-17, read only by gate
  `GC` as a cross-check on the low. Not an input.
- `backtests/mech_regime/spy_base_rate_daily.csv`, read only by gate `GB`, as in `tail_breach`.
- `scripts/backtest_study/lib/era.py`, `ticker_class.py::holm` and `ruin_walk.py::wilson` (through
  `tail_breach`), imported unchanged.
- No Barchart call, no Sheets export and no backtest row.

## Population and basis, fixed here

- **Era.** Only the default era `current` runs. Any other `STUDY_ERA` refuses (exit 2).
- **Seal.** The [holdout seal](../../f4_deployment/holdout_seal.md) binds the signal dates of emitted
  plays. This study reads no flow signal, play or backtest row, so the seal does not apply.
- **Report header.** The report prints `era: current (inputs are unversioned market data)`, the SPY
  session range, the git sha, the dirty flag and every input file read.
- **Part 1 population.** Every SPY session in each test year to the latest close, a pooled line over
  the test years, and a training-years context line from 2006-07-18 to 2023-12-29.
- **Part 2 population.** The training, test and forward rows defined above.

## Plan-time observations, disclosed

### What the operator was shown before this file

On 2026-11-14, before this file was written, the operator was shown descriptive counts of event A
from the Barchart cache. The operator chose the intraday basis after seeing those counts, and after
`tail_breach` failed its floor with 9 episodes. So event A was chosen knowing it would likely clear
the floor.

| Fact, 2024 to 2026-11-13 | Value |
|---|---|
| Sessions | 721 |
| Intraday 2σ breach sessions | 18 |
| By year: 2024, 2025, 2026 | 7, 6, 5 |
| Close-basis breaches, from `tail_breach` | 11 |
| Intraday rate against the closing law | About 2.5% against 2.28% |

- Those counts used the Barchart cache's raw low. This study's primary basis adjusts the low for
  dividends, so its count may differ by a session or two.
- The counts were not split into episodes. With 18 breaches, A's test window likely clears the floor
  of 10 episodes. That floor is inherited from `tail_breach` unchanged; it was not chosen in light of
  the count.
- The brief handed to the drafter records the counts by year only. It does not record whether the
  18 dates were listed, or whether any VIX value was shown beside them. A list of dates would give
  the episode count and, with public VIX history, a rough read of predictor against event. That
  possibility is disclosed, not ruled out.
- No predictor has been compared with an intraday breach or with a 5% move, in any window. No count
  of event B, `B-1` or any 5% variant was made on any date.

### Data checks made for this file

Every check below was made on 2026-11-14 on the module's own yfinance fetch. They covered date
ranges, missing values, the price basis and agreement between feeds. No low was compared with a
threshold.

| Fact | Value |
|---|---|
| SPY sessions | 8,507, from 1993-01-29 to 2026-11-13 |
| `^VIX` closes | 9,288, from 1990-01-02 to 2026-11-13 |
| `^VIX3M` closes | 5,116, from 2006-07-17 to 2026-11-13 |
| SPY sessions with no VIX close | 0 |
| SPY sessions since 2006-07-17 with no VIX3M close | 0 |
| Sessions since 2006-07-17 with a missing or out-of-order high or low | 0 |
| Sessions since 2006-07-17 with the high equal to the low | 0 |
| Close-to-`Adj Close` ratio steps outside the dividend pattern | 0 |
| Raw low against the Barchart cache, 1,066 common sessions | Largest gap 0.0013% |
| Close and VIX against `spy_base_rate_daily.csv`, 8,471 common dates | 0 gaps over 0.5% |
| Test-window sessions: 2024, 2025, 2026 to 11-13 | 252, 250, 219 |
| Training sessions, 2006-07-18 to 2023-12-29 | 4,394 |

**General knowledge, not counted.** The drafter knows from public market history that the test
window holds the August 2024 volatility spike and the April 2025 sell-off. Both very likely include
a 5% fall within a week; that is the drafter's expectation, not a count.

### Power, from a prior

The prior below reads VIX closes only, never a SPY low. It asks how many events a normal law would
give at the test window's VIX levels.

- **At face value.** If VIX were an unbiased forecast, the reflection law gives about 33 test
  origins flagged by `B`, and about 33 `A` sessions.
- **With the variance risk premium.** VIX usually sits above the volatility that follows it. The
  literature puts realized vol near 0.8 × VIX on average. At that scale the figures fall to about 13
  `B` origins and 9 `A` sessions.
- **From origins to episodes.** One sell-off flags a run of consecutive `B` origins, often two to
  five. Dividing the flagged origins by that run length gives roughly 3 to 10 episodes.
- **A's power rests on the peek.** The expectation that A clears its floor comes from the
  plan-time count of 18, not from this prior.
- **The expected answer for B is `UNDERPOWERED`.** The floor of 10 test episodes is kept, for the
  reason given under the gates. The study says so now rather than lowering the floor.
- **`B-1` is far rarer.** The same prior gives 0.15 to 0.6 single-session 5% falls in the whole test
  window. It is printed and never graded.
- **Training.** The same prior gives about 190 to 360 `B` origins in training. Training should clear
  its floor of 30 episodes, though the 2008 and 2020 crises chain many origins into few episodes.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `PA` | arm | Logistic regression on `X1`–`X4`, outcome `YA5` | Co-primary, Holm m = 2 with `PB` |
| `PB` | arm | Logistic regression on `X1`–`X4`, outcome `YB` | Co-primary, Holm m = 2 with `PA` |
| `SA1`–`SA4` | arm | One predictor each, outcome `YA5` | Secondary, Holm m = 4 |
| `SB1`–`SB4` | arm | One predictor each, outcome `YB` | Secondary, Holm m = 4 |
| `NA1` | arm | The four-predictor model on `YA1` | Secondary, own family |
| Climatology | control | The training base rate of the same outcome | The reference every BSS is scored against |
| `FORWARD` | population scope | `PA` and `PB` on forward rows, coefficients frozen | Forward verdicts |
| Part 1 table | descriptive cut | Counts, rates and references per year | Printed only |

### The co-primaries

Each predictor is standardised with the training rows' mean and standard deviation. An unpenalised
logistic regression is fitted to the outcome on the training rows. Its predicted probability on
each test row is scored against climatology.

### Why two co-primaries with Holm

The operator asked two questions, one per event. Grading both on an uncorrected 95% interval would
give two chances at a false yes. So `PA` and `PB` form one Holm family, m = 2. The report prints each
arm's unadjusted word beside its graded word.

### Printed only, never graded

| Label | What it prints |
|---|---|
| `PART1` | Per year: sessions, events, rate, Wilson 95% CI, closing-law and reflection-law references, episodes |
| `AUC` | Test-window [AUC](../../../glossary.md#auc) for every arm. Context only |
| `COEF` | Fitted coefficients and convergence for every arm |
| `SHIFT` | Training and test base rate, a block CI on the test rate, and the BSS of a constant at the test rate |
| `YEAR` | `PA` and `PB` BSS in each test year. A row's year is the year of its first outcome session |
| `B10`, `B42` | `PA` and `PB` CIs with 10- and 42-session blocks |
| `K-PARAM` | `PA` refitted with k = 1.5 and k = 2.5 |
| `B-DEF` | `PB` refitted on `B-CLOSE`, `B-1`, `B-UP` and `B-EITHER` |
| `BASIS` | `PA` refitted on `A-BASIS` |

- The B references in Part 1 use the reflection law at `σ_t × √5` for the low basis.
- For `B-CLOSE` they use the end-point law, which ignores the four closes before the last. It is a
  floor.
- Wilson intervals treat sessions as independent. Both events cluster, so those intervals are too
  narrow.

## How it is judged

These are `tail_breach`'s rules, applied to each arm.

- **Metric.** The [Brier skill](../../../glossary.md#brier-skill) score on test rows:
  `BSS = 1 − mean((p − y)²) / mean((c − y)²)`. Here `p` is the model's probability and `c` is the
  training base rate of the same outcome.
- **Bootstrap.** A moving-block bootstrap over test rows in date order: ⌈n/21⌉ blocks of 21
  consecutive rows, starts uniform, cut to n rows. 10,000 draws, seed 20261114. The arms on one
  outcome share one draw set.
- **Why 21 sessions.** Each outcome overlaps across five consecutive rows, both events cluster, and
  VIX is persistent for weeks. `B10` and `B42` show how much the choice matters.
- **CI.** The 2.5th and 97.5th percentiles of the draws, with the half-width printed.
- **p-value.** Two-sided, from the same draws: twice the smaller of the share at or below 0 and the
  share at or above 0, capped at 1.
- **Multiple comparisons.** `PA` and `PB` form one Holm family, m = 2. `SA1`–`SA4` form one, m = 4,
  and `SB1`–`SB4` another. `NA1` stands alone.
- **A gated arm stays in its family.** m stays 2 or 4 whatever the gates print. An arm that is
  `UNDERPOWERED` or does not converge enters its family with p = 1.

## Gates

- **GE, inputs.** The three series exist or can be fetched, none is empty, and SPY reaches the test
  window. Any failure refuses (exit 3).
- **GB, basis.** `tail_breach`'s two checks, imported unchanged: the close-to-`Adj Close` ratio
  never steps like a split, and the close and VIX agree with `spy_base_rate_daily.csv` within 0.5%.
  Any failure refuses (exit 3).
- **GO, OHLC order.** From 2006-07-17, every session has a high and a low. The low sits at or below
  the open (when present) and the close, which sit at or below the high, within a relative 1e-6.
  Any failure refuses (exit 3).
- **GC, cross-feed.** Where the Barchart cache holds the session, the raw yfinance low agrees with
  its low within 0.5%. Any failure refuses (exit 3). Without the file this check is skipped, and the
  report says so.
- **GX, no lookahead.** `tail_breach`'s check, imported unchanged: the predictors are recomputed at
  60 origins on a series cut at the origin and must match. The tests also change every later close,
  high and low. They require identical predictors, and identical outcomes for every row whose last
  outcome session is on or before the cut. They also require every training row's last outcome
  session, o+5, to fall before 2024-01-02 for both outcomes.
- **GT, training.** At least 2,500 training rows, and at least 30 training episodes of the event the
  arm forecasts. Below either, that event's arms print `UNDERPOWERED`.
- **GN, test episodes.** At least 10 independent episodes of the event in the test window. For `A`
  they are counted among the test rows' outcome sessions. For `B` they are counted among the first
  sessions t = o+1 of test rows with `YB` = 1. Below 10, that event's arms print `UNDERPOWERED`.
- **One count per event.** GT and GN are counted once per event: on the `YA5` rows for `PA`,
  `SA1`–`SA4` and `NA1`, and on the `YB` rows for `PB` and `SB1`–`SB4`.
- **Convergence.** A model whose fit does not converge prints `UNDERPOWERED`.
- **Era.** Any era but `current` refuses (exit 2).

**Why 10 episodes.** The reason is `tail_breach`'s. About 34 blocks of 21 sessions span the test
window. With 10 episodes, a bootstrap draw almost never misses all of them. With 5, about one draw
in 220 holds none, and each draw's BSS turns on which two or three episodes it holds. Below 10 the
interval measures which episodes were drawn, not the forecast.

| Population | Floor |
|---|---|
| Training | 2,500 rows and 30 episodes, per event (GT) |
| Test | 10 episodes, per event (GN) |
| Forward | 250 rows and 10 episodes, per event |

## Bar for a candidate

No result here makes a candidate rule. A `PREDICTABLE` `PA` or `PB` files "to be tested" in
[`deployment-evidence.md`](../../../deployment-evidence.md), pending its forward read.

## Verdicts, worded now

**`PA` and `PB`:**

| Token | When |
|---|---|
| `PREDICTABLE` | Gates met, BSS 95% CI lower bound above 0, and the Holm-adjusted p (m = 2) below 0.05 |
| `NO-FORECAST` | Gates met, and the CI lower bound at or below 0 or the Holm p at or above 0.05 |
| `UNDERPOWERED` | GT, GN or convergence unmet, or the CI is not finite; census printed, nothing concluded |

**`SA1`–`SA4` and `SB1`–`SB4`.** The same tokens, with the Holm p of their own family (m = 4).

**`NA1`.** The same tokens with no Holm step. A `PREDICTABLE` `NA1` does not turn a `NO-FORECAST`
`PA` into a yes.

**FORWARD.** `PA` and `PB`, each with its frozen coefficients on forward rows, with the same tokens
and no Holm step. `STILL-OPEN` takes the place of `UNDERPOWERED` until that event's forward rows
reach 250 rows and 10 episodes. The verdict of record is the first forward run that prints a token
other than `STILL-OPEN`. For `B`, under the prior above, that is likely several years away.

**The banner.** The report's section titled VERDICT prints:

```
>>> tail_breach_intraday PA (four-predictor logistic, any intraday 2x-VIX breach in the next 5 sessions, test from 2024-01-02): PREDICTABLE | NO-FORECAST | UNDERPOWERED <<<
>>> tail_breach_intraday PB (four-predictor logistic, intraday low 5% below the origin close within 5 sessions, test from 2024-01-02): PREDICTABLE | NO-FORECAST | UNDERPOWERED <<<
>>> tail_breach_intraday SECONDARY A (each predictor alone, Holm m=4): SA1 <w> SA2 <w> SA3 <w> SA4 <w> <<<
>>> tail_breach_intraday SECONDARY B (each predictor alone, Holm m=4): SB1 <w> SB2 <w> SB3 <w> SB4 <w> <<<
>>> tail_breach_intraday NA1 (four-predictor logistic, next-session intraday breach): <w> <<<
>>> tail_breach_intraday FORWARD (forecast origins after the registration date): PA <w> PB <w> <<<
```

## Anti-tuning

- Fixed here: both event rules, k = 2 and the 5% move, the price basis, the predictors (inherited),
  the 5-session horizon, the training boundary, the unpenalised logistic model, the metric, the
  21-session block, the seed, the floors, the Holm families and the verdict words.
- k = 1.5 and 2.5, the B variants, the raw basis, the block-length cuts, `AUC` and the per-year BSS
  are printed as they fall. None is used to re-grade.
- No other predictor, horizon, threshold or model is graded.
- This registration is immutable in substance once accepted. Editorial consolidation only.

## What could ship

Nothing ships from this study.

- A `PREDICTABLE` `PA` or `PB` files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md), pending its forward read.
- No verdict here changes a tier, a veto, a size class, an exit, the deploy card or the hedge
  sleeve's timing rule in [§4](../../../../docs/deployment-rules.md#s4).
