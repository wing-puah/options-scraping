# direction_hit — per-era record

**Question.** Does anything known at entry (17 fixed features: market labels, SPY and VIX, the rollup columns, DTE, index ETF, the underlying's own 20-day return and 50-SMA position, sector) predict that the underlying moves the play's way over the hold? One walk-forward logistic model, graded by out-of-sample AUC.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha 92d5bc8 — recorded 2026-10-12
<!-- key era=v4 sha=92d5bc8 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-12 21:14:57 · git 92d5bc8 (main, working tree dirty) · exit 0 · 27.8s
command     python -m scripts.backtest_study.f1_selection.signal.direction_hit
excerpt     verdict

```
VERDICT
  v4 OOS AUC 0.525 CI95 [0.484, 0.563]; v3 OOS AUC 0.564; PBO 0.085
  >>> direction_hit MODEL (all directional, v4): NULL <<<
  secondary, Tier A/B: NULL (AUC 0.519 [0.468, 0.576])
  forward: STILL-OPEN
  Nothing ships from this study. PREDICTS would let the operator consider a registered filter or tie-break.
```

