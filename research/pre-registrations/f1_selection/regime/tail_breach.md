## tail_breach — how often does SPY fall more than twice its VIX-implied move, and can it be forecast?

<!-- outcome:start -->
> Latest outcome: `>>> tail_breach P (four-predictor logistic, any 2x-VIX down breach in the next 5 sessions, test from 2024-01-02): UNDERPOWERED <<<` (`GN`: 9 test episodes, floor 10); S1–S4 and N1 `UNDERPOWERED`; forward `STILL-OPEN` — yfinance closes to 2026-11-13, run 2026-11-14 · [record](../../../study-results/f1_selection/regime/tail_breach.md)
<!-- outcome:end -->

_Registered 2026-11-14._

**STATUS: REGISTERED (ACCEPTED BY DEFAULT 2026-11-14) on the drafter's recommended defaults; the
operator may revisit (a revisit after a result is a NEW registration, never an edit).** Drafted
2026-11-14 on the operator's chosen definitions, with the drafter's defaults for every detail the
operator deferred. No breach count, rate or predictor-versus-breach figure was computed before this
file was written. A fresh second reader checked it the same day, found no blocker and no leakage,
and its fixes are folded in.

## The question

The operator asked: "measure the tail risk breach in 2024, 2025 and 2026 and see if there is any
predictability to it."

A **down breach** is a session on which SPY fell more than twice the one-day move that the prior
close's VIX implied. The study has two parts.

- **Part 1, measurement.** How many breaches were there in 2024, 2025 and 2026 to date, how does
  that compare with a normal law, and do breaches cluster? Descriptive; no verdict.
- **Part 2, forecast.** Do four volatility readings taken at the prior close forecast a breach in
  the next five sessions better than the long-run base rate? Graded.

A `PREDICTABLE` answer would tell the operator that hedge timing could lean on these readings. It
would not by itself change any rule.

## What this study is not

- **Not a hedge study.** It prices no option and reads no position, tier, R or backtest row. Its
  unit is a SPY session, and its outcome is SPY's own path.
- **Not a test of the mech label or `regime_watch`.** [`regime_confirm`](regime_confirm.md) asks
  whether a confirmed mech BEAR flip precedes a 10% fall. This study asks about one-day tail moves
  scaled by VIX.
- **Not a sweep.** One breach multiple, one horizon, one model and one metric are graded. Every
  other cut is printed only.
- **Not pooled across eras.** The inputs are market closes with no prompt version. There is one
  population and no `--era` replication.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price basis

- **SPY return.** `r_t = ln(A_t / A_{t−1})`, where `A` is yfinance's `Adj Close` for SPY, fetched
  with `auto_adjust=False`. `Adj Close` folds in dividends, so `r_t` is a total return.
- **Why adjusted.** An unadjusted close drops by the dividend on each ex-dividend date. That drop
  reached 0.81% of the price on one date (see the plan-time observations), while a 2× breach at
  VIX 12 is about a 1.5% fall. An unadjusted basis would therefore fake or inflate small down
  moves. The unadjusted twin is printed, never graded.
- **Splits.** SPY has never split. Gate GB still refuses a feed whose close-to-`Adj Close` ratio
  steps like a split.
- **VIX and VIX3M.** The yfinance `Close` of `^VIX` and `^VIX3M`, matched to SPY sessions by exact
  date.
- **Close timing.** `^VIX` settles at 4:15pm Eastern and SPY closes at 4:00pm. A late-day VIX
  jump on t−1 therefore widens the threshold for session t a little, a small bias against
  breaches. It is disclosed, not corrected.

### Breach definitions

`σ_t = VIX_{t−1} / 100 / √252`, the one-day move implied by the prior close's VIX. A breach is
undefined, and the session is out, when `VIX_{t−1}` is missing.

| Label | Rule | Role |
|---|---|---|
| `DOWN` | `r_t < −k × σ_t`, k = 2 | Primary; graded outcome |
| `DOWN-1.5`, `DOWN-2.5` | The same rule with k = 1.5 and k = 2.5 | Parameters, printed beside the primary |
| `FIXED` | Simple total return `A_t / A_{t−1} − 1` below −2% | Secondary, printed only |
| `WINDOW` | `ln(A_{t+4} / A_{t−1}) < −2 × VIX_{t−1}/100 × √5/√252`, indexed by its first session t | Secondary, printed only |
| `UP` | `r_t > 2 × σ_t` | Secondary mirror, printed only |
| `BASIS` | `DOWN` on the unadjusted close | Printed only |

`WINDOW` windows overlap, so its counts are counts of windows, not of independent events.

`PART1` prints for `DOWN`, `DOWN-1.5`, `DOWN-2.5`, `FIXED`, `WINDOW`, `UP` and `BASIS`.

### Episodes

An **episode** is a run of `DOWN` breaches in which each breach falls within 5 sessions of the
one before. A breach more than 5 sessions after the previous one starts a new episode. The power
floors count episodes, not breaches, because breaches cluster.

### Predictors

Each forecast has an **origin**: the close of session t−1. Every predictor reads closes on the
origin or before it, and never later.

| Label | Name | Definition |
|---|---|---|
| `X1` | VIX level | `VIX_{t−1}` |
| `X2` | VIX percentile | Midrank share of `VIX_{t−1}` within the 252 VIX closes on the SPY sessions strictly before the origin: (count below + half the count equal) / 252 |
| `X3` | Term structure | `VIX_{t−1} / VIX3M_{t−1}` |
| `X4` | Realized over implied | 20-session realized vol over `VIX_{t−1}`. Realized vol is `√(mean of r²) × √252 × 100` over the 20 returns ending at the origin |

A row with any predictor missing is out, and counted. The four models are fitted and scored on the
same rows. The first origin is 2006-07-17, the first VIX3M close.

### Outcomes

| Label | Rule | Role |
|---|---|---|
| `Y5` | 1 if any of sessions t … t+4 is a `DOWN` breach, else 0 | Primary |
| `Y1` | 1 if session t is a `DOWN` breach | Secondary (`N1`) |

A row whose outcome sessions are not all defined is out, and counted.

### Training and test windows

| Window | Rows |
|---|---|
| Training | Every outcome session before 2024-01-02, all four predictors present. `X3` starts the window at 2006-07-17 |
| Test | First outcome session on or after 2024-01-02, last outcome session on or before the registration date, 2026-11-14 |
| Forward | Origin after the registration date |

Two kinds of row are in neither window, and both are counted:

- **Straddle.** Outcome sessions on both sides of 2024-01-02. For `Y5` that is four rows.
- **Gap.** Origin on or before the registration date, last outcome session after it. For `Y5`
  that is the last few origins before the forward window.

So the test window is fixed once the registration date passes, and no outcome session is shared
between test and forward. Coefficients and the standardisation are fitted on training rows only,
once, and never refitted. Standardisation only puts the coefficients on one scale; it does not
change the fitted probabilities. The date enters the code as the constant `REGISTERED`.

## Dependencies

- `backtests/tail_breach/SPY.csv`, `VIX.csv`, `VIX3M.csv` (date, close, adj_close), fetched by the
  module from yfinance. `--refresh` refetches all three. Today's bar is never fetched.
- `backtests/mech_regime/spy_base_rate_daily.csv`, read only by gate GB as a cross-check.
- `scripts/backtest_study/lib/era.py`: `requested_era`, `CURRENT` and the exit codes.
- `scripts/backtest_study/lib/ruin_walk.py::wilson` and
  `scripts/backtest_study/f1_selection/benchmark/ticker_class.py::holm`, imported unchanged.
- No Barchart call, no Sheets export and no backtest row.

## Population and basis, fixed here

- **Era.** The inputs carry no prompt version. Only the default era `current` runs. Any other
  `STUDY_ERA`, such as `--era v3`, refuses (exit 2).
- **Seal.** The [holdout seal](../../f4_deployment/holdout_seal.md) binds signal dates of emitted
  plays. This study reads no flow signal, play or backtest row, so the seal does not apply. The
  report says so.
- **Report header.** The report prints `era: current (inputs are unversioned market closes)`, the
  SPY session range, the git sha, the dirty flag and every input file read.
- **Part 1 population.** Every SPY session in 2024, 2025 and 2026 to the latest close, plus a
  pooled 2024–2026 line and a 2006-07-18 to 2023-12-29 context line.
- **Part 2 population.** The training, test and forward rows defined above.

## Plan-time observations, disclosed

Every check below was made on 2026-11-14, before this file was written. The checks covered date
ranges, missing values and the price basis. No return was compared with a threshold, and no breach
was counted on any date.

_Inputs: the module's own yfinance fetch of 2026-11-14 into `backtests/tail_breach/`, and the
`regime_confirm` cache in `backtests/regime_confirm/` (to 2026-10-20)._

| Fact | Value |
|---|---|
| SPY sessions | 8,507, from 1993-01-29 to 2026-11-13 |
| `^VIX` closes | 9,288, from 1990-01-02 to 2026-11-13 |
| `^VIX3M` closes | 5,116, from 2006-07-17 to 2026-11-13 |
| SPY sessions with no VIX close | 0 |
| SPY sessions since 2006-07-17 with no VIX3M close | 0 |
| First origin with all four predictors | 2006-07-17 |
| Test-window sessions: 2024, 2025, 2026 to 11-13 | 252, 250, 219 |
| Training sessions, 2006-07-18 to 2023-12-29 | 4,394 (from the `regime_confirm` cache) |

**The price basis.**

- `spy_base_rate_daily.csv` holds the unadjusted SPY close. It matches the yfinance `Close` on all
  8,471 common dates exactly, and its VIX matches too. It ends 2026-09-24, so it is a cross-check,
  not the input.
- On the `regime_confirm` cache, the ratio of `Close` to `Adj Close` changed on 136 dates. Every
  change was downward, the largest 0.81% (2008-12-19). That is about four dividends a year over 34
  years, and no step looks like a split.
- The split-adjusted-close trap recorded from earlier fetches does not reach SPY, which has never
  split, or VIX, which is an index.

**General knowledge, not counted.** The drafter knows from public market history that the test
window holds the August 2024 volatility spike and the April 2025 sell-off. No count was made on
them.

**A prior, from the literature, not from this data.** VIX usually sits above the volatility that
follows it (the variance risk premium), which would make 2× breaches rarer than the normal law's
2.3%. Fat tails push the other way. Under the normal law the test window would hold about 16
breaches. `UNDERPOWERED` is therefore a real possibility, and the floor below was set without
knowing the count.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `P` | arm | Logistic regression on `X1`–`X4`, outcome `Y5` | Primary |
| `S1`–`S4` | arm | Logistic regression on one predictor each (`X1`, `X2`, `X3`, `X4`), outcome `Y5` | Secondary, Holm m = 4 |
| `N1` | arm | The four-predictor model on `Y1` | Secondary, own family |
| Climatology | control | The training base rate of the outcome, the same for every row | The reference every BSS is scored against |
| `FORWARD` | population scope | `P` on forward rows, coefficients still frozen | Forward verdict |
| Part 1 table | descriptive cut | Counts, rates and clustering per year | Printed only |

### P, the four-predictor model

Each predictor is standardised with the training rows' mean and standard deviation. An
unpenalised logistic regression is fitted to `Y5` on the training rows. Its predicted probability
on each test row is scored against climatology.

### S1 to S4, one predictor at a time

The same fit with one predictor. They show which reading, if any, carries the signal.

### N1, the next session

The four-predictor model refitted on `Y1`. It asks whether the forecast works for the very next
session, where outcomes do not overlap.

### Printed only, never graded

| Label | What it prints |
|---|---|
| `PART1` | Per year: sessions, breaches, rate, Wilson 95% CI, normal-law rate, breaches with another breach in the 5 sessions before against `1 − (1 − rate)^5`, episodes |
| `FIXED` normal rate | The mean over sessions of the normal-law chance of a −2% day at that session's `σ_t` |
| `AUC` | Test-window [AUC](../../../glossary.md#auc) for `P`, `S1`–`S4` and `N1`. Context only |
| `COEF` | Fitted coefficients and convergence for `P`, `S1`–`S4` and `N1` |
| `SHIFT` | Training and test base rate of `Y5`, a block CI on the test rate, and the BSS a constant at the test rate would score |
| `YEAR` | `P`'s BSS in each test year, with its own block CI. A row's year is the year of its first outcome session |
| `B10`, `B42` | `P`'s CI with 10- and 42-session blocks |
| `K-PARAM` | `P` refitted with k = 1.5 and k = 2.5 |
| `SEC-DEF` | `P` refitted on `FIXED`, `WINDOW` (the window t … t+4) and `UP` |

Wilson intervals treat sessions as independent. Breaches cluster, so those intervals are too
narrow, and the report says so.

## How it is judged

- **Metric.** The [Brier skill](../../../glossary.md#brier-skill) score (BSS) on test rows:
  `BSS = 1 − mean((p − y)²) / mean((c − y)²)`, where `p` is the model's probability and `c` is the
  training base rate of the same outcome.
- **Why against the training rate.** The test window's own rate is unknown at forecast time. A
  shift in the base rate can sink BSS even when the ranking works, which is why `SHIFT` and `AUC`
  print beside it.
- **Bootstrap.** A moving-block bootstrap over test rows in date order. Each draw strings together
  ⌈n/21⌉ blocks of 21 consecutive rows, with starts drawn uniformly, and cuts the result to n rows.
  10,000 draws, seed 20261114. `P` and `S1`–`S4` share one draw set.
- **Why 21 sessions.** `Y5` overlaps across five consecutive rows, breaches cluster, and VIX is
  persistent for weeks. A 21-session block covers the overlap four times over. It is the same
  21-session length as [`market_read`](market_read.md) and [`baseline_read`](baseline_read.md),
  which use fixed rather than moving blocks.
  `B10` and `B42` show how much the choice matters.
- **CI.** The 2.5th and 97.5th percentiles of the draws. Each CI prints its half-width.
- **p-value.** Two-sided, from the same draws: twice the smaller of the share of draws at or below
  0 and the share at or above 0, capped at 1.
- **Multiple comparisons.** `P` stands alone. `S1`–`S4` form one Holm family, m = 4. `N1` stands
  alone.

## Gates

- **GE, inputs.** The three series exist or can be fetched, none is empty, and SPY reaches the
  test window. Any failure refuses (exit 3).
- **GB, basis.** Two checks. Any failure refuses (exit 3).
  - The ratio of SPY `Close` to `Adj Close` never rises by more than 0.01% and never moves by more
    than 2% from one session to the next.
  - Where `spy_base_rate_daily.csv` exists, the cached SPY close and VIX agree with it within 0.5%
    on every common date. Without the file this check is skipped, and the report says so.
- **GX, no lookahead.** `predictors_at` slices every series to the origin before it reads a value,
  and the origin is strictly before the first outcome session. Each run recomputes the predictors
  at 60 evenly spaced origins on a series cut at the origin and stops with an error unless they
  match. `tests/test_tail_breach.py` changes or removes every later close and requires identical
  predictors.
- **GT, training.** At least 2,500 training rows and 30 training episodes. Below either, `P`,
  `S1`–`S4` and `N1` print `UNDERPOWERED`.
- **GN, test episodes.** At least 10 independent `DOWN` episodes among the test rows' outcome
  sessions. Below it, `P`, `S1`–`S4` and `N1` print `UNDERPOWERED`.
- **One count for every arm.** GT and GN are counted once, on the `Y5` rows, and apply to every
  arm.
- **Convergence.** A model whose fit does not converge prints `UNDERPOWERED`.
- **Era.** Any era but `current` refuses (exit 2).

**Why 10 episodes.** About 34 blocks of 21 sessions span the test window. With 10 episodes spread
over them, a bootstrap draw holds no episode with a chance near (24/34)^34, about 1 in 140,000. With
5 it is about 1 in 220, and each draw's BSS then turns on which two or three episodes it happens to
hold. A draw with no episode scores only the cost of false alarms. Below 10 the CI measures which
episodes were drawn, not the forecast.

| Population | Floor |
|---|---|
| Training | 2,500 rows and 30 episodes (GT) |
| Test | 10 episodes (GN) |
| Forward | 250 rows and 10 episodes |

## Bar for a candidate

No result here makes a candidate rule. A `PREDICTABLE` `P` files "to be tested" in
[`deployment-evidence.md`](../../../deployment-evidence.md), pending the forward read.

## Verdicts, worded now

**`P` and `N1`:**

| Token | When |
|---|---|
| `PREDICTABLE` | Gates met, BSS 95% CI lower bound above 0: the forecast beat the training base rate |
| `NO-FORECAST` | Gates met, CI lower bound at or below 0. This includes a CI wholly below 0, a forecast worse than the base rate |
| `UNDERPOWERED` | GT, GN or convergence unmet, or the CI is not finite; census printed, nothing concluded |

**`S1`–`S4`.** The same tokens. `PREDICTABLE` also needs the Holm-adjusted p below 0.05.

**FORWARD.** `P`'s frozen coefficients on forward rows, with the same tokens. `STILL-OPEN` takes
the place of `UNDERPOWERED`, and holds until the forward window reaches 250 rows and 10 episodes.
The verdict of record is the first forward run that prints a token other than `STILL-OPEN`. Later
forward runs are descriptive. Under the normal-law prior, about 6 breaches a year, 10 forward
episodes take roughly two years or more. `STILL-OPEN` is the expected forward word for a long time.

**`N1` answers a different question.** A `PREDICTABLE` `N1` does not turn a `NO-FORECAST` `P`
into a yes.

**The banner.** The report's section titled VERDICT prints:

```
>>> tail_breach P (four-predictor logistic, any 2x-VIX down breach in the next 5 sessions, test from 2024-01-02): PREDICTABLE | NO-FORECAST | UNDERPOWERED <<<
>>> tail_breach SECONDARY (each predictor alone, Holm m=4): S1 <w> S2 <w> S3 <w> S4 <w> <<<
>>> tail_breach N1 (four-predictor logistic, next-session breach): <w> <<<
>>> tail_breach FORWARD (forecast origins after the registration date): <w> <<<
```

## Anti-tuning

- Fixed here: the breach rule and k = 2, the price basis, the four predictor definitions and their
  windows (252, 20), the 5-session horizon, the training boundary 2024-01-02, the unpenalised
  logistic model, the metric, the 21-session block, the seed, the floors and the verdict words.
- k = 1.5 and 2.5, the secondary breach definitions, the block-length cuts, `AUC` and the per-year
  BSS are printed as they fall. None is used to re-grade.
- No other predictor, horizon, threshold or model is graded.
- This registration is immutable in substance from 2026-11-14. Editorial consolidation only.

## What could ship

Nothing ships from this study.

- A `PREDICTABLE` `P` files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md), pending the forward read.
- No verdict here changes a tier, a veto, a size class, an exit, the deploy card or the hedge
  sleeve's timing rule in [§4](../../../../docs/deployment-rules.md#s4).
