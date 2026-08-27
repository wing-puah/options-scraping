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

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:10:34 · git d47e227 (main, working tree dirty) · exit 0 · 4.1s
command     python -m scripts.backtest_study.f2_management.bear_giveback
excerpt     tail

```
  RANGE + H-VOL                  n=  17  win   41%  PF  0.40  meanR -0.110  $    -6,242  MFE  +0.67  MAE  -0.74  gb  1.11  cap  -0.16
  RANGE + L-VOL                  n=  77  win   56%  PF  1.09  meanR +0.070  $     2,408  MFE  +0.99  MAE  -0.75  gb  0.76  cap  +0.07
  RANGE + C-VOL                  n=  23  win   48%  PF  0.95  meanR +0.050  $      -507  MFE  +0.89  MAE  -0.68  gb  0.77  cap  +0.06
--- the deploy-time cell: bull_call_spread by model regime x vol ------------
  RANGE + E-VOL                  n=  10  win   60%  PF  2.14  meanR +0.338  $     4,375  MFE  +1.02  MAE  -0.45  gb  0.44  cap  +0.33
  RANGE + L-VOL                  n=  30  win   57%  PF  1.18  meanR +0.123  $     2,073  MFE  +0.99  MAE  -0.53  gb  0.53  cap  +0.12
  BULL + L-VOL                   n= 114  win   54%  PF  1.40  meanR +0.126  $    18,524  MFE  +0.92  MAE  -0.60  gb  0.66  cap  +0.14
  BULL + C-VOL                   n=  10  win   80%  PF  4.93  meanR +0.651  $     7,699  MFE  +1.36  MAE  -0.34  gb  0.25  cap  +0.48
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:20:51 · git c841a01 (main, working tree dirty) · exit 0 · 2.5s
command     python -m scripts.backtest_study.f2_management.bear_giveback
excerpt     tail

```
  RANGE + H-VOL                  n=  17  win   41%  PF  0.40  meanR -0.110  $    -6,242  MFE  +0.67  MAE  -0.74  gb  1.11  cap  -0.16
  RANGE + L-VOL                  n=  77  win   56%  PF  1.09  meanR +0.070  $     2,408  MFE  +0.99  MAE  -0.75  gb  0.76  cap  +0.07
  RANGE + C-VOL                  n=  23  win   48%  PF  0.95  meanR +0.050  $      -507  MFE  +0.89  MAE  -0.68  gb  0.77  cap  +0.06
--- the deploy-time cell: bull_call_spread by model regime x vol ------------
  RANGE + E-VOL                  n=  10  win   60%  PF  2.14  meanR +0.338  $     4,375  MFE  +1.02  MAE  -0.45  gb  0.44  cap  +0.33
  RANGE + L-VOL                  n=  30  win   57%  PF  1.18  meanR +0.123  $     2,073  MFE  +0.99  MAE  -0.53  gb  0.53  cap  +0.12
  BULL + L-VOL                   n= 127  win   54%  PF  1.45  meanR +0.142  $    22,511  MFE  +0.92  MAE  -0.61  gb  0.65  cap  +0.15
  BULL + C-VOL                   n=  10  win   80%  PF  4.93  meanR +0.651  $     7,699  MFE  +1.36  MAE  -0.34  gb  0.25  cap  +0.48
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:37:40 · git 25f3e27 (main, working tree dirty) · exit 0 · 4.6s
command     python -m scripts.backtest_study.f2_management.bear_giveback
excerpt     tail

```
  RANGE + C-VOL                  n=  34  win   38%  PF  0.68  meanR -0.165  $    -5,176  MFE  +0.81  MAE  -0.80  gb  0.98  cap  -0.20
--- the deploy-time cell: bull_call_spread by model regime x vol ------------
  RANGE + E-VOL                  n=  22  win   55%  PF  1.94  meanR +0.269  $     7,554  MFE  +1.00  MAE  -0.55  gb  0.55  cap  +0.27
  RANGE + L-VOL                  n=  43  win   58%  PF  1.33  meanR +0.178  $     5,509  MFE  +1.03  MAE  -0.53  gb  0.52  cap  +0.17
  RANGE + C-VOL                  n=  12  win   50%  PF  1.50  meanR +0.104  $     2,355  MFE  +1.18  MAE  -0.56  gb  0.48  cap  +0.09
  BULL + E-VOL                   n=   8  win   25%  PF  0.22  meanR -0.272  $    -4,464  MFE  +0.23  MAE  -0.64  gb  2.72  cap  -1.16
  BULL + L-VOL                   n= 244  win   56%  PF  1.55  meanR +0.182  $    51,973  MFE  +0.94  MAE  -0.59  gb  0.62  cap  +0.19
  BULL + C-VOL                   n=  37  win   70%  PF  4.12  meanR +0.566  $    28,081  MFE  +1.39  MAE  -0.52  gb  0.37  cap  +0.41
```

