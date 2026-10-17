## direction_hit — does anything known at entry predict that the underlying moves the play's way?

<!-- outcome:start -->
> Latest outcome: `NULL`; forward `STILL-OPEN` — 2026-10-12 · [record](../../../study-results/f1_selection/signal/direction_hit.md).
<!-- outcome:end -->

_Registered 2026-10-12, before the study's first run._

**STATUS: ACCEPTED BY DEFAULT 2026-10-12 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Contested choices are parameters printed both
ways; only the defaults below carry a verdict.

## The question

Does a fixed logistic model on 17 entry-time features rank the plays whose
underlying moves their way above those whose underlying does not, out of
sample, better than chance (AUC 0.5)?

A Tier A/B pick's R is mostly its underlying's own move over the hold (R² 0.47
on v4, 2026-10-12 exploratory read). So the number that decides R is the
[direction hit](../../../glossary.md#direction-hit): how often the underlying
moves the way the play bets. The study screens each of the 17 features alone
under a date-clustered permutation test with BH correction. Then it grades one
pre-specified model, a regularised logistic regression fitted walk-forward, by
its out-of-sample [AUC](../../../glossary.md#auc).

## What this study is not

- **Not a selection rule.** A `PREDICTS` verdict lets the operator consider a
  registered filter or tie-break. It changes nothing by itself.
- **Not an R study.** The target is the underlying's direction, not the option
  P&L. R depends on the hit and on the wrapper; this study isolates the hit.
  It says nothing about option P&L.
- **Not `ml_combination` again.** That study learned R and E from the analysis
  columns and printed `NULL`; its rule is "re-open on new columns only, never
  on new models". This study changes the target to the hit and adds five
  columns no study has fed a model: SPY's 20-day return, the VIX level, the
  underlying's own 20-day return, its position against its own 50-day SMA, and
  a sector bucket.
- **Not open to a later feature.** The 17 features, the target and C are fixed.
  A new feature needs a new registration.
- **Not blind.** The feature list was drawn up after the exploratory R results.
- **Not a test of published cross-sectional effects.** This book holds only the
  analysis's own picks.

### Overlap with earlier studies

| Study | Already covers | This study adds |
|---|---|---|
| `ml_combination` | Learned models on R and E, analysis columns | Hit target; five new columns |
| `ticker_class` | Index ETF vs single stock, on R, direction held fixed | Index ETF as one feature among 17, on the hit |
| `text_features` | The model's own prose | Nothing; no prose feature here |
| Exploratory read, 2026-10-12 | 26 features against R, permutation and BH | The same test design pointed at the hit |

## Population and basis, fixed here

- **Loader.** `load_book()` at its defaults. Rows with no stored R, or with
  `fill_trusted` False, are dropped and counted, as in `dip_buy`.
- **Directional plays.** `ticker_class.direction` decides. `bull_*`,
  `long_call` and `short_put` are bullish (+1). `bear_*` and `long_put` are
  bearish (−1). Every other structure is out. VETO rows stay in.
- **Primary population.** Every directional play.
- **Secondary population.** Tier A/B only, tiered with `mapping.ladder_tier`
  via `dip_buy.tier_of`.
- **Era.** v4 is graded. v3 is the replication. In-sample dates are those
  before `era.SEAL_START`.

### The target

`hit` is 1 when `direction × (C_exit / C_signal − 1) > 0`, else 0. A zero move
is a miss.

- `C_signal` is the underlying's close on the last bar on or before the signal
  date, at most 5 calendar days earlier. Entry is the next open, so the
  overnight gap counts toward the hit.
- `C_exit` is the close on the last bar on or before the exit day, at most 5
  calendar days earlier and strictly after the signal bar. The exit day is the
  grid day at `days_held` (`ticker_class.exit_date_of`), the same convention as
  the exploratory `beta.py`.
- Bars come from `lib/underlying.py::load_bars`: stock OHLC first, the option
  files' `Price~` as the fallback.
- **Rescaled tickers** (`rescaled_tickers()`) stay in. Every quantity is a ratio
  on one series, which a split adjustment does not change. Their count is
  printed.
- **Split artifacts.** A hold whose move exceeds 35% on `Price~` bars
  (`underlying._SPLIT_ARTIFACT_PCT`) is dropped and counted.
- A row with no usable bar at either end is dropped and counted.

**Secondary target, printed.** The aligned hold return,
`direction × (C_exit / C_signal − 1)`. Its mean and median print per
population. It carries no verdict.

**Descriptive cut, printed.** The hit at a fixed 10 sessions after the signal
bar, which no exit rule touches. Its AUC prints beside the graded one.

## Plan-time observations, disclosed

The 2026-10-12 exploratory read tested 26 features against R, not the hit.

- `cpir` ranked R at ρ +0.083 (raw p 0.008, BH 0.104).
- The index-ETF flag lowered meanR by 0.128.
- It also printed the hit's base rate for Tier A/B: 52% on v4, 67% on v3.

No feature was tested against the hit before this file was written. The
feature list was drawn up knowing those R results.

## What it compares

The study has one graded model and three printed objects.

| Object | What it does | Kind |
|---|---|---|
| `direction_hit F1…F17` | Each of 17 features screened alone: permutation test, BH correction. A v4 q < 0.05 flags `screen+`, which feeds no decision | descriptive cut |
| The graded model | L2 logistic regression on all 17 features, C = 1.0, one walk-forward fold per month | arm |
| The Tier A/B model | The same model on Tier A/B rows only, printed with its own token, labelled secondary | population scope, secondary |
| Feature-group subsets | 16 configurations over four groups, read by PBO. The graded model is the full set, so PBO never moves the verdict | control |

### The 17 features

"Aligned" means multiplied by the play's direction, so a positive value always
favours the play. The "Permuted" column says what is shuffled under the null.
The expected signs are context only. Every test is two-sided.

| Id | Feature | Type | Permuted | Expected sign, source |
|---|---|---|---|---|
| F1 | Model market direction vs the play: agrees, RANGE, opposes | category | across dates | none |
| F2 | Model vol (`model_vol`) | category | across dates | none |
| F3 | `mech_cell` | category | across dates | none |
| F4 | SPY trend aligned: bull play on an above date, or bear play on a [dip date](../../../glossary.md#dip-date) | binary | across dates | none |
| F5 | SPY 20-session return, aligned | number | across dates | none |
| F6 | VIX close | number | across dates | none |
| F7 | `score_total` | number | within date | none |
| F8 | `oi_confirm_pct` | number | within date | none |
| F9 | `cpir − 0.5`, aligned | number | within date | + (Hilliard, Hilliard & Wu 2025) |
| F10 | `iv_spread`, aligned | number | within date | + (Cremers & Weinbaum 2010) |
| F11 | `iv_skew`, aligned against the play (−direction × skew) | number | within date | + (Xing, Zhang & Zhao 2010) |
| F12 | `iv_pct` | number | within date | none |
| F13 | DTE at entry | number | within date | none |
| F14 | Index ETF (SPY, QQQ, IWM, DIA; `ticker_class` G1) | binary | within date | none |
| F15 | Underlying's own 20-session return, aligned | number | within date | − (Jegadeesh 1990; Lehmann 1990) |
| F16 | Underlying close over its own 50-session SMA, minus 1, aligned | number | within date | + (Jegadeesh & Titman 1993) |
| F17 | Sector, `lib/sectors.py::cluster_for` | category | within date | none |

The four feature groups are:

- **Market:** F1–F6.
- **Flow:** F7–F12.
- **Underlying:** F15–F16.
- **Structure:** F13, F14, F17.

Rules for the inputs:

- **SPY and VIX** come from `backtests/mech_regime/spy_vix_daily_full.csv`, as
  of the signal date. This is the table `mech_cell` reads.
- **F15 and F16** use only bars on or before the signal date
  (`underlying_features.trailing_bars`). F15 needs 21 bars spanning at most 35
  calendar days. F16 needs 50 bars spanning at most 80 days. A sparse `Price~`
  series fails these, and the feature is missing for that row.
- **The rollup columns** (F7–F12) are the analysis row's values, written the
  morning after the signal date and before entry.

### How far to trust the expected signs

The signs come from papers that measured cross-sectional returns over a large
universe. This book holds the analysis's own picks, so a null here does not
contradict them. The signs steer no test and no verdict.

- **Short-term reversal.** Jegadeesh (1990), *J. Finance* 45(3); Lehmann
  (1990), *QJE* 105(1). F15's 20-session window sits at this horizon, so
  reversal predicts a negative aligned effect.
- **Momentum.** Jegadeesh & Titman (1993), *J. Finance* 48(1). F16 is a trend
  measure, and its 50-session window is shorter than their formation period.
- **Option flow.** Pan & Poteshman (2006), *RFS* 19(3), cited in `references/`
  papers 01 and 04. CPIR is the open-interest form from Hilliard, Hilliard & Wu
  (2025), `references/` paper 03.
- **IV spread and skew.** Cremers & Weinbaum (2010), *JFQA* 45(2); Xing, Zhang &
  Zhao (2010), *JFQA* 45(3); via Lin, Lu & Driessen (2013), paper 04. The
  repo's own reconstruction of both is flagged unverified in
  `docs/conviction-score.md`.

The three momentum and reversal papers are new to the repo. They are cited from
their published versions; no `references/` copy exists.

## How it is judged

The graded statistic is the pooled out-of-sample
AUC of Method 2. Method 1 carries no verdict.

### Method 1 — the univariate screen

| Feature type | Statistic |
|---|---|
| Binary | hit rate where 1 minus hit rate where 0 |
| Number | hit rate in the top tercile minus the bottom tercile, terciles within era and population |
| Category | Σ n_k (p_k − p)² / n, the between-level variance of the hit rate |

- **Null.** 2,000 permutations, seed 20261012. A within-date feature is shuffled
  among the rows of each signal date. An across-dates feature has its per-date
  value shuffled across dates. Aligned features are re-aligned with each row's
  own direction after the shuffle.
- **p.** `(1 + count of |null| ≥ |observed|) / 2,001`.
- **Correction.** BH over the 17 features, separately per population and era.
- **Printed beside it.** The v3 statistic, its p, and whether its sign agrees.
  A category has no sign, so its per-level hit rates print instead.
- **No verdict.** A feature with v4 q < 0.05 is flagged `screen+`. The flag
  feeds no decision.

### Method 2 — the graded model

- **Model.** L2-regularised logistic regression, C = 1.0, `lbfgs`, intercept
  fitted, no class weights.
- **Inputs.** All 17 features. A number is standardised with the training
  fold's mean and standard deviation. A missing number takes the training
  median plus a missing-indicator column. A category is one-hot over the levels
  seen in training. An unseen level is all zeros.
- **Walk-forward.** One fold per calendar month. A month's model is fitted on
  rows whose signal date **and exit day** are both before the month's first
  day. A row whose outcome was not yet known never trains a prediction.
- **Warm-up.** The first graded month starts at least six calendar months after
  the era's first signal date. A month with fewer than 100 training rows, or
  one class only, is skipped and counted.
- **Graded statistic.** The pooled out-of-sample AUC over every predicted row,
  with a 95% CI from a date-clustered bootstrap: 2,000 draws of signal dates,
  seed 20260811.
- **Beside it.** The Brier skill against the base rate,
  `1 − Brier(model) / Brier(base)`, where the base predicts the training
  fold's own hit rate. Same bootstrap. Printed, not graded.

The Tier A/B model is run the same way and printed with its own token,
labelled secondary.

### PBO over the feature subsets

The 15 non-empty unions of the four groups, plus an intercept-only model, are 16
configurations. Each is run through the same walk-forward. CSCV (`lib/pbo.py`,
S = 16) ranks them by the summed negative Brier score per out-of-sample date.
The earliest dates are trimmed so 16 divides the count.

The graded model is the full set, fixed now, not the in-sample best subset. So
PBO does not change the verdict. A PBO above 0.50 prints "selection fragile":
picking a subset by its in-sample score would not hold.

### Parameters printed both ways, not graded

| Parameter | Default (graded) | Alternative (printed) |
|---|---|---|
| Regularisation | C = 1.0 | C = 0.1 |
| Hit horizon | Exit day | 10 sessions |

## Gates

- **Graded statistic.** The pooled out-of-sample AUC, with its 95% CI from the
  date-clustered bootstrap above (2,000 draws, seed 20260811).
- **Not graded.** The Brier skill prints beside the AUC and gates nothing.
- **Forward floor.** 30 signal dates and 100 positions.

## Bar for a candidate

`PREDICTS` needs both clauses. The primary population is graded.

1. The v4 AUC CI95 lower bound exceeds 0.5.
2. The v3 walk-forward AUC point estimate exceeds 0.5.

## Verdicts, worded now

The verdict is read on the primary population.

| Token | When |
|---|---|
| `PREDICTS` | v4 AUC CI95 lower bound > 0.5, and the v3 walk-forward AUC point > 0.5 |
| `WEAK` | v4 AUC CI95 lower bound > 0.5, and the v3 point ≤ 0.5 |
| `NULL` | v4 AUC CI95 includes 0.5, or lies below it |

### Forward read

The model is refitted on every in-sample row whose exit came before
`era.SEAL_START`. It is then scored on v4 signal dates on or after it, once the
seal lifts. The floor is 30 signal dates and 100 positions.

| Forward token | When |
|---|---|
| `CONFIRMED` | Past the floor, forward AUC CI95 lower bound > 0.5 |
| `NOT-CONFIRMED` | Past the floor, otherwise |
| `STILL-OPEN` | Below the floor, or the dates still sealed |

## Anti-tuning

- The 17 features, their alignment, the target, the floors, the warm-up, C,
  both seeds and the four groups are fixed here.
- No feature is added, removed or re-binned after the first run. A new feature
  is a new registration.

## What could ship

Nothing ships from this study. `PREDICTS` lets the operator consider a
registered filter or tie-break, which would need its own PBO read and forward
dates.
