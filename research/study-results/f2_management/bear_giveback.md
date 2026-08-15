# bear_giveback — per-era record

**Question.** 82% of bear rows go green and then give it back. Can a breakeven ratchet capture that, and does the underlying path explain it?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:45:48 · git 53b7167 (main, working tree dirty) · exit 0 · 5.7s
command     python -m scripts.backtest_study.f2_management.bear_giveback
excerpt     tail

```
  RANGE + E-VOL                  n=  50  win   66%  PF  2.99  meanR +0.543  $    25,423  MFE  +1.47  MAE  -0.47  gb  0.32  cap  +0.37
  RANGE + H-VOL                  n=  13  win   77%  PF  9.80  meanR +0.644  $    10,425  MFE  +1.08  MAE  -0.25  gb  0.23  cap  +0.60
  RANGE + L-VOL                  n=  15  win   53%  PF  1.81  meanR +0.197  $     3,700  MFE  +1.26  MAE  -0.68  gb  0.54  cap  +0.16
  RANGE + C-VOL                  n=  32  win   56%  PF  1.35  meanR +0.179  $     4,926  MFE  +1.02  MAE  -0.60  gb  0.59  cap  +0.18
  BULL + L-VOL                   n=  60  win   43%  PF  1.07  meanR +0.033  $     1,919  MFE  +0.99  MAE  -0.71  gb  0.71  cap  +0.03
  BULL + C-VOL                   n=  40  win   75%  PF  5.01  meanR +0.544  $    24,507  MFE  +1.37  MAE  -0.31  gb  0.22  cap  +0.40
  BEAR + E-VOL                   n=  20  win   65%  PF  2.37  meanR +0.446  $     6,760  MFE  +1.56  MAE  -0.38  gb  0.25  cap  +0.29
  BEAR + H-VOL                   n=   9  win   67%  PF  2.27  meanR +0.389  $     2,948  MFE  +1.50  MAE  -0.43  gb  0.29  cap  +0.26
```
