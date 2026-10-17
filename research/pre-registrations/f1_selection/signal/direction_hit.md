## direction_hit — does anything known at entry predict that the underlying moves the play's way?

<!-- brief:start -->
## In brief

> Plain-language brief for readers. The registration below is the binding text; where the two differ, the registration wins. `study_review` cuts this brief out before grading, so the blind graders never see it.
> Latest outcome: `NULL`; forward `STILL-OPEN` — 2026-10-12 · [record](../../../study-results/f1_selection/signal/direction_hit.md).
> Nothing else in this brief is a result.

**The question**

Does a fixed logistic model on 17 features known at entry rank the plays whose underlying moves their way above the plays whose underlying does not, out of sample, better than chance (AUC 0.5)? A Tier A/B pick's R is mostly its underlying's own move over the hold (R² 0.47 on v4, 2026-10-12 exploratory read). The number that decides R is therefore the [direction hit](../../../glossary.md#direction-hit).

**What it compares**

The registration was accepted by default on 2026-10-12. Only the defaults carry a verdict.

| Object | What it does | Kind |
|---|---|---|
| `direction_hit F1…F17` | Each of 17 features screened alone: permutation test, BH correction. A v4 q < 0.05 flags `screen+`, which feeds no decision | descriptive cut |
| The graded model | L2 logistic regression on all 17 features, C = 1.0, one walk-forward fold per month | arm |
| The Tier A/B model | The same model on Tier A/B rows only, printed with its own token | population scope, secondary |
| Feature-group subsets | 16 configurations over four groups, read by PBO. The graded model is the full set, so PBO never moves the verdict | control |

The features, in groups:

- **Market (F1–F6):** model market direction against the play, model vol, `mech_cell`, SPY trend aligned, SPY 20-session return aligned, VIX close.
- **Flow (F7–F12):** `score_total`, `oi_confirm_pct`, cpir − 0.5, `iv_spread`, `iv_skew`, `iv_pct`.
- **Underlying (F15–F16):** its own 20-session return aligned, its close over its 50-session SMA minus 1, aligned.
- **Structure (F13, F14, F17):** DTE at entry, index ETF flag, sector.

"Aligned" means multiplied by the play's direction. Every test is two-sided. The expected signs from the literature are context only.

**How it is judged**

**Target.** `hit` is 1 when the aligned return is above zero, else 0. The aligned return is direction × (`C_exit` / `C_signal` − 1). A zero move is a miss.

- `C_signal` is the close on the last bar on or before the signal date, at most 5 calendar days earlier.
- `C_exit` is the close at the exit day (`days_held` on the grid), strictly after the signal bar. A hold moving more than 35% on `Price~` bars is dropped as a split artifact. A row with no usable bar at either end is dropped. All drops are counted.

**Population.** Loader defaults, rows with no stored R or `fill_trusted` False dropped. Only directional plays count: `bull_*`, `long_call` and `short_put` are +1, `bear_*` and `long_put` are −1. VETO rows stay in. The primary population is every directional play. The secondary population is Tier A/B only. v4 is graded and v3 is the replication.

**Method 1, the screen.** Binary features use the difference in hit rate. Numbers use top tercile minus bottom tercile. Categories use between-level variance of the hit rate. The null is 2,000 permutations, seed 20261012. A within-date feature shuffles among each date's rows. An across-dates feature shuffles per-date values across dates. BH runs over the 17 features, per population and era. The screen carries no verdict.

**Method 2, the graded model.** One fold per calendar month. A month's model trains on rows whose signal date and exit day both fall before the month starts. The first graded month starts at least six calendar months after the era's first signal date. A month with fewer than 100 training rows, or one class only, is skipped and counted.

**Gates.**

- The graded statistic is the pooled out-of-sample [AUC](../../../glossary.md#auc), with a 95% CI from a date-clustered bootstrap of 2,000 draws, seed 20260811.
- The Brier skill against the base rate prints beside it and is not graded.
- Forward floor: 30 signal dates and 100 positions.

**Bar.** `PREDICTS` needs both of these.

1. The v4 AUC CI95 lower bound exceeds 0.5.
2. The v3 walk-forward AUC point estimate exceeds 0.5.

Two parameters print both ways and are not graded: C = 0.1 against 1.0, and a 10-session hit horizon against the exit day. A PBO above 0.50 prints "selection fragile".

**Possible verdicts**

| Token | What it means |
|---|---|
| `PREDICTS` | v4 AUC CI95 lower bound > 0.5, and the v3 walk-forward AUC point > 0.5 |
| `WEAK` | v4 AUC CI95 lower bound > 0.5, and the v3 point ≤ 0.5 |
| `NULL` | v4 AUC CI95 includes 0.5, or lies below it |

The forward read refits on every in-sample row whose exit came before `era.SEAL_START`. It scores v4 signal dates on or after it, once the seal lifts.

| Forward token | What it means |
|---|---|
| `CONFIRMED` | Past the floor, forward AUC CI95 lower bound > 0.5 |
| `NOT-CONFIRMED` | Past the floor, otherwise |
| `STILL-OPEN` | Below the floor, or the dates still sealed |

**What could ship**

Nothing ships from this study. `PREDICTS` lets the operator consider a registered filter or tie-break. That would need its own PBO read and forward dates.

**What this study cannot tell you**

- Anything about option P&L. The target is the underlying's direction, not R.
- Anything about a feature added later. The 17 features, the target and C are fixed, and a new feature needs a new registration.
- Anything blind. The feature list was drawn up after the exploratory R results.
- Whether published cross-sectional effects hold. This book holds only the analysis's own picks.

---
<!-- brief:end -->

_Registered 2026-10-12, before the study's first run._

**STATUS: ACCEPTED BY DEFAULT 2026-10-12 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Contested choices are parameters printed both
ways; only the defaults below carry a verdict.

**What this file says, in one paragraph.** A Tier A/B pick's R is mostly its
underlying's own move over the hold (R² 0.47 on v4, 2026-10-12 exploratory
read). So the number that decides R is the hit rate: how often the underlying
moves the way the play bets. This study asks whether any of 17 features known
at entry predicts that hit. It screens each feature alone under a
date-clustered permutation test with BH correction. Then it grades one
pre-specified model, a regularised logistic regression fitted walk-forward, by
its out-of-sample AUC.

## Question

Does a fixed logistic model on 17 entry-time features rank the plays whose
underlying moves their way above those whose underlying does not, out of
sample, better than chance (AUC 0.5)?

## What this is NOT

- **Not a selection rule.** A `PREDICTS` verdict lets the operator consider a
  registered filter or tie-break. It changes nothing by itself.
- **Not an R study.** The target is the underlying's direction, not the
  option P&L. R depends on the hit and on the wrapper; this study isolates
  the first.
- **Not `ml_combination` again.** That study learned R and E from the
  analysis columns and printed `NULL`; its rule is "re-open on new columns
  only, never on new models". This study changes the target to the hit and
  adds five columns no study has fed a model: SPY's 20-day return, the VIX
  level, the underlying's own 20-day return, its position against its own
  50-day SMA, and a sector bucket.

## Overlap with earlier studies

| Study | What it already covers | What this adds |
|---|---|---|
| `ml_combination` | Learned models on R and E, analysis columns | Hit target; five new columns |
| `ticker_class` | Index ETF vs single stock, on R, direction held fixed | Index ETF as one feature among 17, on the hit |
| `text_features` | The model's own prose | Nothing; no prose feature here |
| Exploratory read, 2026-10-12 | 26 features against R, permutation and BH | The same test design pointed at the hit |

## Population and basis, fixed here

- **Loader.** `load_book()` at its defaults. Rows with no stored R, or with
  `fill_trusted` False, are dropped and counted, as in `dip_buy`.
- **Directional plays.** `ticker_class.direction`: `bull_*`, `long_call` and
  `short_put` are bullish (+1); `bear_*` and `long_put` are bearish (−1).
  Every other structure is out. VETO rows stay in.
- **Primary population.** Every directional play. **Secondary.** Tier A/B
  only, tiered with `mapping.ladder_tier` via `dip_buy.tier_of`.
- **Era.** v4 is graded. v3 is the replication. In-sample dates are those
  before `era.SEAL_START`.

### The target

`hit` = 1 when `direction × (C_exit / C_signal − 1) > 0`, else 0. A zero move
is a miss.

- `C_signal` is the underlying's close on the last bar on or before the signal
  date, at most 5 calendar days earlier. Entry is the next open, so the
  overnight gap counts toward the hit.
- `C_exit` is the close on the last bar on or before the exit day, at most 5
  calendar days earlier and strictly after the signal bar. The exit day is
  the grid day at `days_held` (`ticker_class.exit_date_of`), the same
  convention as the exploratory `beta.py`.
- Bars come from `lib/underlying.py::load_bars`: stock OHLC first, the
  option files' `Price~` as the fallback.
- **Rescaled tickers** (`rescaled_tickers()`) stay in. Every quantity here is a
  ratio on one series, which a split adjustment does not change. Their count
  is printed.
- **Split artifacts.** A hold whose move exceeds 35% on `Price~` bars
  (`underlying._SPLIT_ARTIFACT_PCT`) is dropped and counted.
- A row with no usable bar at either end is dropped and counted.

**Secondary target, printed.** The aligned hold return,
`direction × (C_exit / C_signal − 1)`. Its mean and median print per
population; it carries no verdict.

**Descriptive cut, printed.** The hit at a fixed 10 sessions after the signal
bar, which no exit rule touches. Its AUC prints beside the graded one.

## Features, fixed now

"Aligned" means multiplied by the play's direction, so a positive value
always favours the play. The permutation column says what is shuffled under
the null.

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

- **SPY and VIX** come from `backtests/mech_regime/spy_vix_daily_full.csv`, as
  of the signal date: the table `mech_cell` reads.
- **F15 and F16** use only bars on or before the signal date
  (`underlying_features.trailing_bars`). F15 needs 21 bars spanning at most 35
  calendar days. F16 needs 50 bars spanning at most 80 days. A sparse
  `Price~` series fails these and the feature is missing for that row.
- **The rollup columns** (F7–F12) are the analysis row's values, written the
  morning after the signal date and before entry.

### Why these signs, and how far to trust them

The expected signs are context. Every test is two-sided.

- **Short-term reversal.** Stocks with high returns over the past week or
  month tend to do worse over the next month: Jegadeesh (1990), *J. Finance*
  45(3); Lehmann (1990), *QJE* 105(1). F15's 20-session window sits at this
  horizon, so reversal predicts a negative aligned effect.
- **Momentum.** Winners over 3 to 12 months keep winning for months:
  Jegadeesh & Titman (1993), *J. Finance* 48(1). F16 is a trend measure; the
  50-session window is shorter than their formation period.
- **Option flow.** Opening option volume predicts stock returns: Pan &
  Poteshman (2006), *RFS* 19(3), cited in `references/` papers 01 and 04.
  CPIR is the open-interest form from Hilliard, Hilliard & Wu (2025),
  `references/` paper 03.
- **IV spread and skew.** Cremers & Weinbaum (2010), *JFQA* 45(2), and Xing,
  Zhang & Zhao (2010), *JFQA* 45(3), via Lin, Lu & Driessen (2013), paper 04.
  The repo's own reconstruction of both is flagged unverified in
  `docs/conviction-score.md`.
- **The caveat.** Every paper above measured cross-sectional returns over a
  large universe. This book holds the analysis's own picks, so a null here
  does not contradict them.

The three momentum and reversal papers are new to the repo. They are cited
from their published versions; no `references/` copy exists.

## Method 1 — the univariate screen

| Feature type | Statistic |
|---|---|
| Binary | hit rate where 1 minus hit rate where 0 |
| Number | hit rate in the top tercile minus the bottom tercile, terciles within era and population |
| Category | Σ n_k (p_k − p)² / n, the between-level variance of the hit rate |

- **Null.** 2,000 permutations, seed 20261012. A within-date feature is
  shuffled among the rows of each signal date. An across-dates feature has
  its per-date value shuffled across dates. Aligned features are re-aligned
  with each row's own direction after the shuffle.
- **p.** `(1 + count of |null| ≥ |observed|) / 2,001`.
- **Correction.** BH over the 17 features, separately per population and era.
- **Printed beside it.** The v3 statistic, its p, and whether its sign agrees.
  A category has no sign; its per-level hit rates print instead.
- **No verdict.** A feature with v4 q < 0.05 is flagged `screen+`. The flag
  feeds no decision.

## Method 2 — the graded model

- **Model.** L2-regularised logistic regression, C = 1.0, `lbfgs`, intercept
  fitted, no class weights.
- **Inputs.** All 17 features. A number is standardised with the training
  fold's mean and standard deviation; a missing number takes the training
  median plus a missing-indicator column. A category is one-hot over the
  levels seen in training; an unseen level is all zeros.
- **Walk-forward.** One fold per calendar month. A month's model is fitted on
  rows whose signal date **and exit day** are both before the month's first
  day. A row whose outcome was not yet known never trains a prediction.
- **Warm-up.** The first graded month starts at least six calendar months
  after the era's first signal date. A month with fewer than 100 training
  rows, or one class only, is skipped and counted.
- **Graded statistic.** The pooled out-of-sample AUC over every predicted
  row, with a 95% CI from a date-clustered bootstrap: 2,000 draws of signal
  dates, seed 20260811.
- **Beside it.** The Brier skill against the base rate, `1 − Brier(model) /
  Brier(base)`, where the base predicts the training fold's own hit rate. Same
  bootstrap. Printed, not graded.

## Verdicts, worded now

Graded on the primary population.

| Token | When |
|---|---|
| `PREDICTS` | v4 AUC CI95 lower bound > 0.5, and the v3 walk-forward AUC point > 0.5 |
| `WEAK` | v4 AUC CI95 lower bound > 0.5, and the v3 point ≤ 0.5 |
| `NULL` | v4 AUC CI95 includes 0.5, or lies below it |

The Tier A/B model is run the same way and printed with its own token,
labelled secondary.

## PBO over the feature subsets

Four feature groups: market (F1–F6), flow (F7–F12), underlying (F15–F16) and
structure (F13, F14, F17). The 15 non-empty unions of groups, plus an
intercept-only model, are 16 configurations. Each is run through the same
walk-forward. CSCV (`lib/pbo.py`, S = 16) ranks them by the summed negative
Brier score per out-of-sample date; the earliest dates are trimmed so 16
divides the count.

The graded model is the full set, fixed now, not the in-sample best subset.
So PBO does not change the verdict. A PBO above 0.50 prints "selection
fragile": picking a subset by its in-sample score would not hold.

## Parameters printed both ways, not graded

| Parameter | Default (graded) | Alternative (printed) | Why contested |
|---|---|---|---|
| Regularisation | C = 1.0 | C = 0.1 | Small book; stronger shrinkage is defensible |
| Hit horizon | Exit day | 10 sessions | Exits cut a hold short when the move goes wrong |

## Forward read

The model is refitted on every in-sample row whose exit came before
`era.SEAL_START`. It is then scored on v4 signal dates on or after it, once
the seal lifts. The floor is 30 signal dates and 100 positions.

| Token | When |
|---|---|
| `CONFIRMED` | Past the floor, forward AUC CI95 lower bound > 0.5 |
| `NOT-CONFIRMED` | Past the floor, otherwise |
| `STILL-OPEN` | Below the floor, or the dates still sealed |

## Plan-time observations, disclosed

The 2026-10-12 exploratory read tested 26 features against R, not the hit.
`cpir` ranked R at ρ +0.083 (raw p 0.008, BH 0.104), and the index-ETF flag
lowered meanR by 0.128. It also printed the hit's base rate for Tier A/B: 52%
on v4, 67% on v3. No feature was tested against the hit before this file was
written. The feature list was drawn up knowing those R results.

## Anti-tuning

- The 17 features, their alignment, the target, the floors, the warm-up, C,
  both seeds and the four groups are fixed here.
- No feature is added, removed or re-binned after the first run. A new
  feature is a new registration.

## Ship criteria

Nothing ships from this study. `PREDICTS` lets the operator consider a
registered filter or tie-break, which would need its own PBO read and
forward dates.

## Build notes

Not part of the registration.

- Module: `scripts/backtest_study/f1_selection/signal/direction_hit.py`. Run
  with `python -m scripts.backtest_study run direction_hit`. The report is
  `backtests/study_output/direction_hit-latest.txt`.
- v3 is loaded in the same process with `load_book(era="v3")`.
- Tests: `tests/test_direction_hit.py` pins the hit's signal-date close, the
  walk-forward's training cut, the permutation design, the verdict grammar
  and the floors on synthetic data.
