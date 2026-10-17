# direction_hit — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/signal/direction_hit.md); where the two differ, the registration wins.
> Latest outcome: `NULL`; forward `STILL-OPEN` — 2026-10-12 · [record](../../../study-results/f1_selection/signal/direction_hit.md).
> Nothing else here is a result.

## The question

Does a fixed logistic model on 17 features known at entry rank the plays whose underlying moves their way above the plays whose underlying does not, out of sample, better than chance (AUC 0.5)? A Tier A/B pick's R is mostly its underlying's own move over the hold (R² 0.47 on v4, 2026-10-12 exploratory read). The number that decides R is therefore the [direction hit](../../../glossary.md#direction-hit).

## What it compares

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

## How it is judged

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

## Possible verdicts

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

## What could ship

Nothing ships from this study. `PREDICTS` lets the operator consider a registered filter or tie-break. That would need its own PBO read and forward dates.

## What this study cannot tell you

- Anything about option P&L. The target is the underlying's direction, not R.
- Anything about a feature added later. The 17 features, the target and C are fixed, and a new feature needs a new registration.
- Anything blind. The feature list was drawn up after the exploratory R results.
- Whether published cross-sectional effects hold. This book holds only the analysis's own picks.
