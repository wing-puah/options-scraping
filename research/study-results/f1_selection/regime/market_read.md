# market_read — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v3 · inputs ee938bc · sha 8e27590 — recorded 2026-10-23
<!-- key era=v3 sha=8e27590 inputs=ee938bc -->

population  406 results · 796 proxy · 1,607 analysis · 854 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-10-23 07:23)
run         2026-10-23 16:57:36 · git 8e27590 (main, working tree dirty) · exit 0 · 1.2s
command     python -m scripts.backtest_study.f1_selection.regime.market_read
excerpt     verdict

```
VERDICT
  era v3, signal dates before 2026-09-23: 137 dates in 21 blocks; 10000 block draws, seed 20260811
  ret21 / dd21 in percentage points; [95% CI] ±half-width
  P1     -0.21 [-3.30, +3.22] ±3.26  BULL 36d/11b  nonBULL 101d/18b  p=0.8738
  P1m    -0.32 [-4.02, +3.70] ±3.86  mBULL 49d/13b  mnonBULL 88d/13b  (control)
  P1-P1m +0.11 [-0.96, +1.12] ±1.04  (paired, printed)
  P2     -0.48 [-1.60, +1.03] ±1.32  strata entering: BULL 1.00; discarded draws 0
  P3     +1.88 [-0.38, +3.92] ±2.15  E-VOL 55d/12b  other 81d/17b  p=0.0886  before Holm NULL, Holm adj p 0.1772
  P4     -0.04 [-4.28, +1.98] ±3.13  RETRO 113d/18b  LIVE 23d/3b  floors NOT met; tape gauge +2.28
  >>> market_read P1 (model BULL - non-BULL, 21d fwd SPY, v3 pre-seal): UNDERPOWERED <<<
  >>> market_read P2 (P1 within mech direction): NULL <<<
  >>> market_read READ (P1+P2): UNDERPOWERED <<<
  >>> market_read P3 (sizing, E-VOL, 21d drawdown, Holm m=2): NULL <<<
  >>> market_read P4 (recall, RETRO - LIVE): STILL-OPEN <<<
  >>> market_read FORWARD (P1, P2, dates after registration): STILL-OPEN <<<
  P1 and P2 are read together at 5% each; P3 and P4 are one Holm family (m = 2).
  The forward verdict of record is the first forward run printing a token other than STILL-OPEN.
  Nothing ships from this study (market_read.md).
```


## era v4 · inputs 1124d27 · sha 8e27590 — recorded 2026-10-23
<!-- key era=v4 sha=8e27590 inputs=1124d27 -->

population  1,103 results · 2,142 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-23 07:23)
run         2026-10-23 16:58:48 · git 8e27590 (main, working tree dirty) · exit 0 · 1.6s
command     python -m scripts.backtest_study.f1_selection.regime.market_read
excerpt     verdict

```
VERDICT
  era v4, signal dates before 2026-09-23: 280 dates in 33 blocks; 10000 block draws, seed 20260811
  ret21 / dd21 in percentage points; [95% CI] ±half-width
  P1     -1.00 [-2.26, +0.39] ±1.32  BULL 157d/32b  nonBULL 123d/30b  p=0.1570
  P1m    -0.75 [-2.66, +1.27] ±1.97  mBULL 184d/29b  mnonBULL 96d/21b  (control)
  P1-P1m -0.25 [-1.25, +0.78] ±1.01  (paired, printed)
  P2     -0.72 [-1.69, +0.33] ±1.01  strata entering: BULL 0.81, RANGE 0.19; discarded draws 0
  P3     +1.08 [-0.13, +3.08] ±1.60  E-VOL 68d/22b  other 212d/33b  p=0.1008  before Holm NULL, Holm adj p 0.2016
  P4     +0.11 [-0.99, +1.35] ±1.17  RETRO 250d/31b  LIVE 28d/2b  floors NOT met; tape gauge +1.23
  >>> market_read P1 (model BULL - non-BULL, 21d fwd SPY, v4 pre-seal): NULL <<<
  >>> market_read P2 (P1 within mech direction): NULL <<<
  >>> market_read READ (P1+P2): NO-FORECAST <<<
  >>> market_read P3 (sizing, E-VOL, 21d drawdown, Holm m=2): NULL <<<
  >>> market_read P4 (recall, RETRO - LIVE): STILL-OPEN <<<
  >>> market_read FORWARD (P1, P2, dates after registration): STILL-OPEN <<<
  P1 and P2 are read together at 5% each; P3 and P4 are one Holm family (m = 2).
  The forward verdict of record is the first forward run printing a token other than STILL-OPEN.
  Nothing ships from this study (market_read.md).
```

