# ml_combination — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/signal/ml_combination.md); where the two differ, the registration wins.
> Latest outcome: PRIMARY v3 `NULL RESULT` (2026-08-15). Re-read on v4: `NULL RESULT` (2026-09-28) · [record](../../../study-results/f1_selection/signal/ml_combination.md).
> Nothing else here is a result.

## The question

Which combination of structure, regime, entry geometry and enrichment columns best predicts a play's outcome? Does any learned rule beat the shipped score-free ladder? The plan was written on 2026-08-11 in `research/ml-plan.md`, before any code ran. The registration quotes its criteria rather than restating them.

## What it compares

Six arms: three baselines and three models. The labels are study-local. `ml_combination B1` and `ml_combination B2` are baselines, not [`bear_arm`](../../../arm-index.md#bear_arm)'s criteria of the same letters.

| Object | What it does | Kind |
|---|---|---|
| `ml_combination B0` | The shipped ladder's top-3/day A-then-B replay, out-of-fold. The benchmark | baseline |
| `ml_combination B1` | Logistic regression on E>0 with structure × market direction × vol only. Does the model rediscover the ladder? | baseline |
| `ml_combination B2` | Elastic-net linear regression on E with the full feature set. Is anything linear left? | baseline |
| `ml_combination M1` | Gradient boosting on E, depth ≤ 3, `min_child_samples` ≥ 30, strong L1/L2, early stopping on the walk-forward validation block | model |
| `ml_combination M2` | The same on binary E>0 | model |
| `ml_combination M3` | A single depth-3 decision tree on the survivors' features: the "ladder v2" candidate | model, only shippable one |

The model class is regularised linear, shallow trees and heavily regularised boosting. Anything bigger fits the windows, not the market.

**Features.** All are frozen at decision time (D+1 morning, post-enrichment):

- Structure, horizon bucket, direction, credit or debit.
- Market regime tokens, mech regime and stock-regime leading token.
- Entry geometry: |delta|, `dte_entry`, `iv_entry_pct`, premium over max loss.
- Enrichment: `iv_spread`, `iv_skew`, `iv_pct`, `oi_confirm_pct`, cpir.
- Score components, on post-13c rows only.
- Calendar: day of week and month, as confound detectors.

Anything computed from the price path after entry is a label, never a feature. No ticker or sector features run in v1.

## How it is judged

**Measure.** The label is E (`pnl_at_cap_pct`, exit-free), with R and binary E>0 secondary. Metrics, in order of authority:

1. Out-of-fold top-3/day replay dollars and mean R against `ml_combination B0`.
2. Mean E of selected rows, with a date-clustered CI.
3. Per-year sign stability.
4. Rank metrics (Spearman of prediction against E), last.

Every metric is also cut ALL, ex-Mar–Apr-2025 and ex-Feb–Apr-2026, plus real-tier-only and post-13c-only.

**Population.** The deduped pooled book, one row per priced play. Training uses real and `strike_expiry_tweak` rows only. bs rows are excluded from training and from every headline metric. The book is in practice ≤ 60 DTE, and every output must say so. The 2026 rows train inside the expanding walk-forward, so they are only tested out-of-fold. A separate "train ≤ 2025, test 2026" epoch prints as the strictest cut, not the headline.

**Validation.** Purged walk-forward: expanding window by date, test blocks of about 15 trading dates, 120-calendar-day embargo. GroupKFold on signal date is secondary and gives variance estimates only. All CIs are date-clustered bootstrap.

**Gates.**

- **Leakage audit** (before Phase 1): every feature must be available at deployment time. A missing `iv_spread` takes a missing-indicator column, never a silent drop.
- **Window dominance:** a learned rule whose gain concentrates above 70% in one window is recorded, not shipped.
- **Composition-proxy test:** any highly ranked feature is re-tested within structure before it is named as signal.
- **Stability:** refit per year and compare feature rankings. A combination that reorders every refit is window fit.

Phase 4 attributes the result with SHAP or permutation importance and runs ablations: full model against ladder-features-only, enrichment-only and scores-only.

**Bar.** `SHIP (as ladder v2)` needs all four.

1. The `ml_combination M3` top-3/day out-of-fold replay beats `ml_combination B0` by a margin whose date-clustered 95% CI excludes zero.
2. The gain is positive in at least 2 of 3 years.
3. It survives both ex-window cuts.
4. The tree's rules pass the within-structure composition test.

## Possible verdicts

| Token | What it means |
|---|---|
| `SHIP (as ladder v2)` | The four-clause bar above holds for `ml_combination M3` |
| `ADOPT AS TIE-BREAK` | `ml_combination M1` or `M2` rank-order adds value within tiers at the same CI standard, and no tree beats the ladder outright |
| `NULL RESULT` | Otherwise: the ladder is near the ceiling of this data |

## What could ship

Only `ml_combination M3` may ship, and only as a human-readable checklist. A model score may at most tie-break within a tier, labelled with its validation window. It may never gate deployment. No production config, prompt or ladder change comes before the Phase 5 evaluation, which is written once and evaluated once.

## What this study cannot tell you

- Anything about exits. Only E-only models run in v1.
- Anything about ticker or sector features. They are revisited only in the Phase 4 ablation.
- Anything era-free. The first run used v3 (2026-08-11). A grading run must name its era, and reproducing the original verdict needs `--era v3`.
- Whether a deeper model would find more. The registration rules out anything bigger.
