## ml_combination — does any learned combination beat the score-free ladder? (2026-08-11, quoted from research/ml-plan.md)

_Registered 2026-08-11._

Module: `scripts/backtest_study/f1_selection/ml_combination.py`.

The plan was written on 2026-08-11 in `research/ml-plan.md` — before this
folder existed, before the module was written, and before any code ran. It
therefore had no file here and could not go through `study_review`. This file
carries the commitments over so a run can be graded; every criterion below is
**quoted**, not restated. `research/ml-plan.md` itself was removed on
2026-08-24 once its three studies had files of their own — its original text is
in git (`git show 42b5e46:research/ml-plan.md`).

The same document registered two other arms, each now its own file:
[`bear_arm.md`](bear_arm.md) (the BEAR arm, B1/B2) and
[`../f4_deployment/bear_deploy.md`](../f4_deployment/bear_deploy.md) (the
DEPLOY arm, D1–D5).

## Question

> Determine, with models instead of hand-cut screens, **which combination of
> structure × regime × entry geometry × enrichment columns best predicts play
> outcome** — and whether any learned rule beats the shipped score-free ladder.

## What this is NOT

Three scope limits, all fixed before the search began.

- **Not a licence to ship a score.** Ship form, quoted: "only human-readable
  rules ship (deployment-rules.md is an operator checklist). A black-box score
  never gates deployment; at most it tie-breaks within a tier, clearly
  labelled with its validation window."
- **Not a deep-learning study.** Ground rule 5: "At ~800 usable rows / ~118
  dates, the model class is regularized linear, shallow trees, and gradient
  boosting with heavy regularization. Anything bigger fits the windows, not the
  market."
- **Not an exit study.** Only `M3` — the single depth-3 tree — has an output
  that may ship, "because only it reduces to a human checklist".

## Population and basis, fixed here

One row per priced play from the deduped pooled book (dedup key
`date|ticker|structure|play`, within-tab then proxy-minus-real). Three ground
rules bind how that book may be read.

- **Ground rule 2 — everything date-clustered.** "Rows within a signal_date
  share the tape; the effective sample is ~118 dates, not ~1,100 rows. All CV
  splits group by date; all CIs are date-clustered bootstrap."
- **Ground rule 3 — pricing-tier discipline.** "Train on real +
  strike_expiry_tweak only (n≈817). bs_options_hist rows are excluded from
  training AND from any headline metric … Report bs-tier performance
  separately as a curiosity only."
- **Ground rule 7 — known inherited bias.** "The book is in practice ≤60-DTE
  (h≥180 unpriceable with real data — 07-27 §3). Whatever the model learns, it
  learns about short-dated spreads; say so in any output."

**Features (frozen at decision time — D+1 morning, post-enrichment)**, quoted
in full:

> - Structure (one-hot), horizon bucket, direction (long/short delta), credit
>   vs debit.
> - Market regime tokens from `market_regime` (direction / vol / RISK-OFF /
>   HP flags), mech regime from `lib/mech_regime.py` (SPY/VIX — refresh the
>   table first), stock-regime leading token from `regime`.
> - Entry geometry: |delta|, dte_entry, iv_entry_pct, entry_premium_total /
>   max_loss_per_contract (defined-risk width).
> - Enrichment: iv_spread, iv_skew, iv_pct, oi_confirm_pct, cpir.
> - Score components: score_flow, score_dealer, score_price, score_vol,
>   score_catalyst, score_total — **post-13c rows only** for any score
>   feature (pre-13c scores anti-select; encode a `post13c` indicator and
>   interact, or drop pre-13c rows in score ablations).
> - Calendar: day-of-week, month (regularized hard; these are confound
>   detectors, not features to ship).

Three further choices were **settled at kickoff, before any code ran:**

1. "**2026 rows train.** They enter the expanding walk-forward (so they are
   only ever *tested* out-of-fold), rather than being held out wholesale …
   A single extra 'train ≤ 2025 → test 2026' epoch is reported alongside as
   the strictest cut, not as the headline."
2. "**E-only models in v1.** R entangles the exit config; E is the selection
   measure. R is used for evaluation (replay $, tier means)…"
3. "**No ticker/sector features in v1**, per the plan default. Revisited only
   in the Phase-4 ablation."

## Plan-time observations, disclosed

The plan discloses, up front, the failure modes this study could repeat:

> The tuning history (current.md + archive/) already burned every failure mode
> this study is exposed to: post-hoc slicing generating three verdicts in one
> session (addenda 11–14), composition proxies masquerading as signal
> (BEAR_HE ≈ bear_put; oi_confirm/iv_pct killed by composition), one market
> window carrying 94% of an effect (Mar–Apr 2025), and score_total looking
> monotone on noise (07-19 vs 07-21). ML amplifies all four if the protocol is
> loose.

The Phase-4 ablation's expected answer is disclosed too: "The 07-21
column sweep predicts: little — only delta+dte on bull_put and iv_spread on
bear_put were decision-relevant."

## Arms

Six arms: three baselines and three models, of which only `M3` can ship.
Labels are study-local — `B1`/`B2` here are **baselines**, not `bear_arm`'s
selection/exit criteria of the same letters; see
[`../../arm-index.md`](../../arm-index.md).

- `B0` (baseline, the benchmark) — "ladder replay out-of-fold".
- `B1` (baseline) — "logistic regression on E>0 with structure ×
  market-direction × vol only — does the model rediscover the ladder? If B1 ≈
  ladder, the ladder is near the information ceiling of those columns."
- `B2` (baseline) — "elastic-net linear regression on E with the full feature
  set — the 'is there anything linear left' check."
- `M1` (model) — "LightGBM (or XGBoost) on E, depth ≤ 3, min_child_samples ≥
  30, strong L1/L2, early stopping on the walk-forward validation block.
  Monotone constraints where theory is unambiguous (none forced initially)."
- `M2` (model) — "same on binary E>0 (classification often stabler at this n)."
- `M3` (model, the only shippable one) — "a single depth-3 decision tree on
  the survivors' features — the 'ladder v2' candidate."

**Benchmark, fixed in advance** (ground rule 1): "the shipped ladder … the
score-free deployment-rules.md ladder's **top-3/day A-then-B replay,
out-of-fold** (completed book: +$22.7k / +$44.8k / +$8.8k by year; monotone
tiers every year). A model that cannot beat a 4-rule checklist out-of-sample
does not ship, whatever its AUC."

## Unit and metric

The selection measure is E; R is for evaluation only, and every metric is cut
three ways.

- **Labels:** "primary **E** (`pnl_at_cap_pct`, exit-free — the selection
  measure per addendum 13); secondary **R** (PROD exits) and binary E>0.
  Optional auxiliary: MFE-asymmetry class, for interpretation only."
- **Metrics, in order of authority:** "(1) out-of-fold top-3/day replay $ and
  mean R vs B0; (2) mean E of selected rows, date-clustered CI; (3) per-year
  sign stability (the 08-08 screen standard: same sign every year present);
  (4) rank metrics (Spearman of prediction vs E) last."
- "Every metric also cut: ex-window (rule 4), real-tier-only, post-13c-only."

**Validation protocol:** "**Primary: purged walk-forward.** Expanding window
by date; test blocks of ~15 trading dates; **embargo = 120 calendar days**
between train end and test start (path_cap_days — outcome windows overlap, so
unpurged CV leaks the label; López de Prado purged-CV rationale). Secondary:
GroupKFold(signal_date) for variance estimates only."

## Gates

Four checks, each of which can stop a result from being called signal.

- **Leakage audit — gate to Phase 1.** "for each feature, verify it is
  available at deployment time. oi_confirm_pct is D+1-enriched and live
  analysis runs after enrich_oi lands, so it is legitimate; anything computed
  from the price path after entry (MFE/MAE, exit_reason, days_held) is a
  label, never a feature. iv_spread is blind on unenriched dates — impute with
  a missing-indicator column, never silently drop rows (missingness is
  correlated with the 2026 window = with the label)."
- **Window-dominance checks are mandatory** (ground rule 4). "Every headline
  reported ALL / ex-Mar–Apr-2025 / ex-Feb–Apr-2026. A learned rule whose gain
  concentrates >70% in one window is recorded, not shipped."
- **"Composition-proxy test (rule 7)."** — the original's own label. "Any
  feature the model ranks highly must be re-tested *within* structure before
  being named as signal — the oi_confirm/iv_pct trap." It is the SIXTH item in
  the ground-rules list, but "rule 7" is how the document names it, including
  in the Phase-4 cross-reference.
- **Stability** (Phase 4). "refit per year, compare feature rankings; a
  combination that reorders every refit is window fit."

**Phase 4 — attribution + robustness**, the method as registered:

> - SHAP / permutation importance on M1/M2 to *name* the combinations.
> - Within-structure re-test of every top-5 feature (rule 6).
> - Ablations: full model vs ladder-features-only vs enrichment-only vs
>   scores-only — how much does anything beyond structure × regime add?
>   (The 07-21 column sweep predicts: little — only delta+dte on bull_put
>   and iv_spread on bear_put were decision-relevant.)
> - Stability: refit per year, compare feature rankings; a combination that
>   reorders every refit is window fit.

(The original cites the composition test as "rule 6" here and "rule 7" in the
ground rules — both point at the same single check.)

## Bar for a candidate

Phase 5, "written now, evaluated once, no re-cuts":

> - **SHIP (as ladder v2)** iff the M3 tree's top-3/day out-of-fold replay
>   beats B0's by a margin whose date-clustered 95% CI excludes zero, AND the
>   gain is positive in ≥2 of 3 years, AND survives both ex-window cuts, AND
>   the tree's rules pass the within-structure composition test.
> - **ADOPT AS TIE-BREAK** iff M1/M2 rank-order adds value within tiers
>   (out-of-fold, same CI standard) but no tree beats the ladder outright —
>   the model score replaces score_total as the within-tier ordering only.

## Verdicts, worded now

> - **NULL RESULT** otherwise — recorded as "the ladder is near the ceiling of
>   this data", which is a finding, not a failure. Given the 07-21 sweep and
>   the one-factor structure of this book, this is the modal outcome.

## Anti-tuning

- "benchmark fixed in advance, validation fixed in advance, ship criteria
  fixed in advance."
- "No production config, prompt, or ladder change from any phase before the
  Phase-5 evaluation."
- "Any deviation at run time must be recorded as a deviation."

## Ship criteria

Only `M3` may ship, and only as a human-readable checklist, per **Ship form**
above. A model score may at most tie-break within a tier, labelled with its
validation window; it may never gate deployment.

## Build notes

*Not part of the registration — implementation and operational record.*

- **Deviations declared before the run and recorded** (`ml-plan.md` status
  block, and the module docstring): "sklearn HistGradientBoosting in place of
  LightGBM/XGBoost, and an added 'abstain' replay variant so the ladder's
  right to trade nothing is not an unfair advantage."
- **Artifacts + hygiene, as registered:** code lives under
  `scripts/backtest_study/` — TRACKED, not `backtests/`; outputs go to
  `backtests/study_output/`. The loader
  (`scripts/backtest_study/lib/book.py`) is a port of the same
  dedup/calibration as `exit_switch_mech_study.py` "so setup differences can't
  explain answer differences".
- **Era.** Registered and first run on the **v3** book (2026-08-11, Phase 5
  NULL RESULT). The same code has since been re-read on era **v4**
  (2026-08-22, 2026-08-24 — the gap widened against the models, `M3` paired R
  gain −0.103). The criteria above name CIs, cuts and sign stability rather
  than figures, so they are era-agnostic; a grading run must nevertheless say
  which era it graded, and reproducing the original verdict needs `--era v3`.
- **Re-open condition, recorded in `study_map/catalog.py`:** "Re-open on new
  COLUMNS only, never on new models; the ladder is at the ceiling of this
  feature set."
