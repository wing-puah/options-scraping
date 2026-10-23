# ticker_pattern — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v3 · inputs ee938bc · sha 8e27590 — recorded 2026-10-23
<!-- key era=v3 sha=8e27590 inputs=ee938bc -->

population  406 results · 796 proxy · 1,607 analysis · 854 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-10-23 07:23)
run         2026-10-23 15:54:22 · git 8e27590 (main, working tree dirty) · exit 0 · 24.1s
command     python -m scripts.backtest_study.f1_selection.benchmark.ticker_pattern
excerpt     verdict

```
VERDICT — v3 replication (same ten names); notes agreement only
>>> ticker_pattern P1 (omnibus, ten names, v3): NULL <<<
>>> ticker_pattern P2 (per-name, Holm m=10, split-half): none graded <<<
>>> ticker_pattern PBO (CSCV, pick-the-best-name): 0.533 <<<
  P1 p = 0.0722 (T 0.794); PBO veto (0.533 > 0.50); no name flagged
  gates: GP0 4/10 names at the floor (bar 4) pass; GP1 share 0.863 pass; GP2 power 0.950 pass
  PBO reading: > 0.50: veto
  v3 replication (same ten names): same market path as v4, so it can note agreement with the v4 verdict only; never pooled with v4.
  step 3: closes on these dates (decided on v4 only; this v3 line is for agreement)
  Nothing ships from this study.
```


## era v4 · inputs 1124d27 · sha 8e27590 — recorded 2026-10-23
<!-- key era=v4 sha=8e27590 inputs=1124d27 -->

population  1,103 results · 2,142 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-23 07:23)
run         2026-10-23 15:55:26 · git 8e27590 (main, working tree dirty) · exit 0 · 45.6s
command     python -m scripts.backtest_study.f1_selection.benchmark.ticker_pattern
excerpt     verdict

```
VERDICT
>>> ticker_pattern P1 (omnibus, ten names, v4): TICKER-EFFECT <<<
>>> ticker_pattern P2 (per-name, Holm m=10, split-half): FLAGGED GLD <<<
>>> ticker_pattern PBO (CSCV, pick-the-best-name): 0.274 <<<
  P1 p = 0.0383 (T 0.817); selection fragile
  gates: GP0 10/10 names at the floor (bar 8) pass; GP1 share 0.823 pass; GP2 power 0.975 pass
  PBO reading: 0.25-0.50: selection fragile
  step 3: a second registration is written (next ten names, own omnibus and Holm family)
  Nothing ships from this study.
```

