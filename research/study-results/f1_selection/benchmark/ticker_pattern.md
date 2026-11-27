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


## era v4 · inputs 61bda3a · sha 3dae88d — recorded 2026-10-26
<!-- key era=v4 sha=3dae88d inputs=61bda3a -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-26 01:06)
run         2026-10-26 19:33:02 · git 3dae88d (main, working tree dirty) · exit 0 · 49.1s
command     python -m scripts.backtest_study.f1_selection.benchmark.ticker_pattern
excerpt     verdict

```
VERDICT
>>> ticker_pattern P1 (omnibus, ten names, v4): NULL <<<
>>> ticker_pattern P2 (per-name, Holm m=10, split-half): none graded <<<
>>> ticker_pattern PBO (CSCV, pick-the-best-name): 0.314 <<<
  P1 p = 0.1243 (T 0.647); p = 0.1243 > 0.05
  gates: GP0 10/10 names at the floor (bar 8) pass; GP1 share 0.821 pass; GP2 power 0.825 pass
  PBO reading: 0.25-0.50: selection fragile
  step 3: closes on these dates
  Nothing ships from this study.
```


## era v4 · inputs 2f45ae6 · sha 436c8f7 — recorded 2026-11-26
<!-- key era=v4 sha=436c8f7 inputs=2f45ae6 -->

population  1,214 results · 2,286 proxy · 3,826 analysis · 878 spy_vix_daily_full · 703 BaselineDaily  (inputs dated 2026-11-26 11:38 … 2026-11-26 14:01)
run         2026-11-26 15:08:42 · git 436c8f7 (main, working tree clean) · exit 0 · 15.8s
command     python -m scripts.backtest_study.f1_selection.benchmark.ticker_pattern
excerpt     verdict

```
VERDICT
>>> ticker_pattern P1 (omnibus, ten names, v4): NULL <<<
>>> ticker_pattern P2 (per-name, Holm m=10, split-half): none graded <<<
>>> ticker_pattern PBO (CSCV, pick-the-best-name): 0.469 <<<
  P1 p = 0.1035 (T 0.702); p = 0.1035 > 0.05
  gates: GP0 10/10 names at the floor (bar 8) pass; GP1 share 0.834 pass; GP2 power 0.890 pass
  PBO reading: 0.25-0.50: selection fragile
  step 3: closes on these dates
  Nothing ships from this study.
```


## era v4 · inputs e7318a6 · sha f04686e — recorded 2026-11-27
<!-- key era=v4 sha=f04686e inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 12:12)
run         2026-11-27 14:19:25 · git f04686e (main, working tree clean) · exit 0 · 16.7s
command     python -m scripts.backtest_study.f1_selection.benchmark.ticker_pattern
excerpt     verdict

```
VERDICT
>>> ticker_pattern P1 (omnibus, ten names, v4): NULL <<<
>>> ticker_pattern P2 (per-name, Holm m=10, split-half): none graded <<<
>>> ticker_pattern PBO (CSCV, pick-the-best-name): 0.416 <<<
  P1 p = 0.0938 (T 0.733); p = 0.0938 > 0.05
  gates: GP0 10/10 names at the floor (bar 8) pass; GP1 share 0.842 pass; GP2 power 0.845 pass
  PBO reading: 0.25-0.50: selection fragile
  step 3: closes on these dates
  Nothing ships from this study.
```

