# baseline_read — per-era record

**Question.** Do the flow baseline's mechanical hedging metrics (index put premium share, ETF put share, put-dominance breadth), each read as its trailing 60-session percentile from the day's own scrape, forecast SPY over the next 21 sessions in return or in drawdown depth? The mechanical twin of market_read.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 1124d27 · sha 046bdab — recorded 2026-10-23
<!-- key era=v4 sha=046bdab inputs=1124d27 -->

population  1,103 results · 2,142 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-23 07:23)
run         2026-10-23 23:08:58 · git 046bdab (main, working tree dirty) · exit 0 · 12.4s
command     python -m scripts.backtest_study.f1_selection.regime.baseline_read
excerpt     verdict

```
VERDICT
  BaselineDaily (unversioned), signal dates before 2026-09-23: 599 dates in 31 blocks (590 with an M1 percentile); 10000 block draws, seed 20261023
  HEAVY minus REST, percentage points; [95% CI] ±half-width
  P1 M1 ret21 +0.52 [-1.00, +1.90] ±1.45  HEAVY 149d/28b  REST 441d/31b  before Holm NULL, adj p 0.6376
  P2 M1 dd21  +0.71 [-0.38, +2.08] ±1.23  HEAVY 149d/28b  REST 441d/31b  before Holm NULL, adj p 0.6376
  S1 M2 ret21 +1.07 [-0.56, +2.54] ±1.55  HEAVY 134d/26b  REST 456d/31b  before Holm NULL, adj p 0.6648
  S2 M2 dd21  +0.64 [-0.41, +2.03] ±1.22  HEAVY 134d/26b  REST 456d/31b  before Holm NULL, adj p 0.7360
  S3 M3 ret21 +0.74 [-0.29, +1.79] ±1.04  HEAVY 137d/28b  REST 462d/31b  before Holm NULL, adj p 0.6648
  S4 M3 dd21  +0.08 [-0.52, +0.74] ±0.63  HEAVY 137d/28b  REST 462d/31b  before Holm NULL, adj p 0.8074
  gates: GE pass; GC M1 pass M2 pass M3 pass; GF P1 met, P2 met; GP P1 1.00 P2 1.00 (pass)
  >>> baseline_read P1 (index put share, top quintile of 60-session window vs rest, 21d SPY return): NULL <<<
  >>> baseline_read P2 (same cut, 21d drawdown depth): NULL <<<
  >>> baseline_read READ (P1+P2, Holm m=2): NO-FORECAST <<<
  >>> baseline_read SECONDARY (ETF put share S1/S2, breadth S3/S4, Holm m=4): S1 NULL S2 NULL S3 NULL S4 NULL <<<
  >>> baseline_read FORWARD (signal dates from 2026-09-23, read after the seal lifts): STILL-OPEN <<<
  P1 and P2 are one Holm family (m = 2); S1-S4 another (m = 4). A HEDGE-* word stands
  only below 0.05 after Holm. On ret21 HEDGE-WARNS means a CI below 0; on dd21, above 0.
  The forward verdict of record is the first forward run printing a token other than STILL-OPEN.
  Nothing ships from this study (baseline_read.md).
```

