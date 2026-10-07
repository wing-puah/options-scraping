# ticker_class — per-era record

**Question.** Is a play on a broad US index ETF (SPY, QQQ, IWM, DIA) more reliable than a single-stock play once direction is held fixed? Graded on meanR, hit rate, drawdown share and sign stability, with a PBO veto over the five graded groups.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 4b1c61f · sha fc716c3 — recorded 2026-10-07
<!-- key era=v4 sha=fc716c3 inputs=4b1c61f -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-28 12:45 … 2026-10-06 23:39)
run         2026-10-07 19:24:01 · git fc716c3 (main, working tree dirty) · exit 0 · 111.9s
command     python -m scripts.backtest_study.f1_selection.ticker_class
excerpt     verdict

```
VERDICTS
  P1  NULL
  S1  NULL vs G5
  S2  NULL vs G6
  S3  NULL vs G7
  S4  UNDERPOWERED vs G2
  PBO 0.367 (graded N=5)  |  bear-stratum diagnostic PBO 0.178
  Nothing ships from this study. INDEX-MORE-RELIABLE or CONTRARY files a 'to be tested' entry in research/deployment-evidence.md.
```


## era v4 · sha fc716c3 — graded excerpts beside the 2026-10-07 verdict above

The verdict block for this run is recorded in the v4 section above. These are further verbatim excerpts from the same report.

excerpt     P1 (v4)

```
  P1  G1 vs S, direction-standardised (bear + bull)
    power: G1 237 pos / 207 dates; S 964 pos / 246 dates   GT0 pass
    weights: G1 raw mix bear 0.797, bull 0.203; used bear 0.797, bull 0.203
    meanR NET   G1 -0.089  S -0.058  diff -0.031  CI95 [-0.149, +0.086]  p=0.6230
    meanR GROSS G1 -0.083  S -0.053  diff -0.029
    per-side raw meanR (protocol.boot_ci_by_date): G1 -0.089 [-0.197, +0.021]  S +0.021 [-0.040, +0.078]
    hit rate    G1 0.392  S 0.416  diff -0.023  CI95 [-0.093, +0.045]
    windows: ex_2025_mar_apr -0.061  ex_2026_feb_apr -0.020
    years (G1 n / comp n / diff, graded when both >= 10): 2024 109/371/+0.055  2025 74/295/+0.105  2026 54/298/-0.382
    half-years: 2024H1 61/225/+0.107  2024H2 48/146/+0.007  2025H1 41/144/+0.393  2025H2 33/151/-0.193  2026H1 34/194/-0.454  2026H2 20/104/-0.330   sign kept 3 of 6
    concentration: drop IWM (55% of G1) and NVDA (13% of S) -> diff +0.003
    DEBIT_PROD replay (gross; credit rows CREDIT_PROD): diff -0.032   shipped tiers A/B only: G1 n=36 +0.197  S n=445 +0.087  diff +0.110
    pooled unadjusted G1 vs S (all directions, n 239/1000): diff -0.111 CI95 [-0.233, +0.013]
    criteria: 1 not met | 2 not met | 3 not met | 4 not met | 5 not met | 6 not met
    VERDICT P1: NULL
```

excerpt     S3 (v4)

```
  S3  G1 vs G7, bear only
    power: G1 189 pos / 188 dates; G7 122 pos / 96 dates   GT0 pass
    meanR NET   G1 -0.187  G7 +0.018  diff -0.205  CI95 [-0.382, -0.026]  p=0.0254
    Holm: rank 1, level 0.0125, adjusted p=0.1016, CI at Holm level [-0.423, +0.025]
    meanR GROSS G1 -0.180  G7 +0.025  diff -0.205
    per-side raw meanR (protocol.boot_ci_by_date): G1 -0.187 [-0.306, -0.067]  G7 +0.018 [-0.127, +0.165]
    hit rate    G1 0.302  G7 0.459  diff -0.157  CI95 [-0.263, -0.050]
    windows: ex_2025_mar_apr -0.241  ex_2026_feb_apr -0.212
    years (G1 n / comp n / diff, graded when both >= 10): 2024 81/39/-0.181  2025 60/39/-0.044  2026 48/44/-0.410
    half-years: 2024H1 48/19/-0.038  2024H2 33/20/-0.295  2025H1 30/16/+0.507  2025H2 30/23/-0.553  2026H1 31/26/-0.571  2026H2 17/18/-0.219   sign kept 5 of 6
    concentration: drop IWM (58% of G1) and SPCX (8% of G7) -> diff -0.190
    DEBIT_PROD replay (gross; credit rows CREDIT_PROD): diff -0.205   shipped tiers A/B only: G1 n=0    n/a  G7 n=0    n/a  diff    n/a
    pooled unadjusted G1 vs G7 (all directions, n 239/384): diff -0.115 CI95 [-0.245, +0.016]
    criteria: 1 not met | 2 not met | 3 not met | 4 MET | 5 MET | 6 MET
    VERDICT S3: NULL vs G7
```

excerpt     PBO (v4)

```
  T = 32 months (2024-01 .. 2026-08); trimmed earliest none; S = 16; combinations 12870; weights {'bear': 0.7974683544303798, 'bull': 0.20253164556962025}
  blank (no position) months per group: {'G1': 1, 'G2': 9, 'G5': 2, 'G6': 1, 'G7': 1}
  PBO 0.367 (lambda <= 0; 2333 combinations exactly at the median)
  P(IS argmax lands below the OOS median, lambda < 0 strictly) 0.186
  IS argmax: most often G2; share of combinations each group is IS-best: G1 0.024  G2 0.643  G5 0.021  G6 0.037  G7 0.276
  full-window statistic (mean of non-blank monthly cells): G1 -0.148  G2 +0.145  G5 -0.061  G6 -0.039  G7 +0.070   -> argmax G2
  degradation slope -0.360; P(OOS meanR of the IS pick < 0) 0.325
  READING: PBO 0.367 0.25-0.50: verdicts print with 'selection fragile'
```

excerpt     drawdown share (v4)

```
  episode: after peak 2025-12-01 through trough 2026-08-31; depth 54.383 R; 503 positions exit inside it
    G1_index     share of episode R   46%   share of episode positions   12%
    G2_country   share of episode R   -6%   share of episode positions    2%
    G3_sector    share of episode R  -15%   share of episode positions   12%
    G4_noneq     share of episode R   28%   share of episode positions   14%
    G5_bigtech   share of episode R    1%   share of episode positions   14%
    G6_semis     share of episode R   30%   share of episode positions   26%
    G7_rest      share of episode R   16%   share of episode positions   19%
  criterion 3 (G1 share 46% <= its position share 12%): not met
```

## era v3 · inputs fc289e2 · sha fc716c3 — recorded 2026-10-07

This section is the v3 replication (same path). Its report is filed as `backtests/study_output/ticker_class-v3-2026-10-07.txt`. It cannot confirm or refute a v4 verdict.
<!-- key era=v3 sha=fc716c3 inputs=fc289e2 -->

population  406 results · 796 proxy · 1,607 analysis · 835 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-09-28 12:45)
run         2026-10-07 19:26:29 · git fc716c3 (main, working tree dirty) · exit 0 · 31.7s
command     python -m scripts.backtest_study.f1_selection.ticker_class
excerpt     verdict

```
VERDICTS — v3 replication (same path); notes agreement only, confirms nothing
  P1  v3 replication (same path): NULL (PBO 0.845 > 0.50: no group-level verdict ships)
  S1  v3 replication (same path): NULL vs G5 (PBO 0.845 > 0.50: no group-level verdict ships)
  S2  v3 replication (same path): UNDERPOWERED vs G6
  S3  v3 replication (same path): NULL vs G7 (PBO 0.845 > 0.50: no group-level verdict ships)
  PBO 0.845 (graded N=5)  |  bear-stratum diagnostic PBO 0.292
  Nothing ships from this study. INDEX-MORE-RELIABLE or CONTRARY files a 'to be tested' entry in research/deployment-evidence.md.
```


excerpt     P1 (v3, in effect the bear stratum)

```
  P1  G1 vs S, direction-standardised (bear + bull) — on v3 in effect the bear stratum
    power: G1 106 pos / 96 dates; S 419 pos / 112 dates   GT0 pass
    weights: G1 raw mix bear 0.849, bull 0.151; used bear 1.000; dropped bull (G1 15 dates, comparison 98 dates)
    meanR NET   G1 -0.045  S -0.259  diff +0.215  CI95 [+0.005, +0.427]  p=0.0454
    meanR GROSS G1 -0.045  S -0.259  diff +0.215
    per-side raw meanR (protocol.boot_ci_by_date): G1 -0.045 [-0.238, +0.157]  S -0.259 [-0.394, -0.122]
    hit rate    G1 0.378  S 0.333  diff +0.044  CI95 [-0.065, +0.156]
    windows: ex_2025_mar_apr +0.010  ex_2026_feb_apr +0.218
    years (G1 n / comp n / diff, graded when both >= 10): 2024 33/114/+0.126  2025 45/197/+0.271  2026 28/108/+0.223
    half-years: 2024H1 6/22/-  2024H2 27/92/+0.182  2025H1 38/174/+0.412  2025H2 7/23/-  2026H1 28/108/+0.223   sign kept 3 of 3
    concentration: drop IWM (45% of G1) and NVDA (15% of S) -> diff +0.339
    DEBIT_PROD replay (gross; credit rows CREDIT_PROD): diff +0.360   shipped tiers A/B only: G1 n=11    n/a  S n=174    n/a  diff    n/a
    pooled unadjusted G1 vs S (all directions, n 106/426): diff -0.078 CI95 [-0.270, +0.114]
    criteria: 1 MET | 2 MET | 3 not met | 4 MET | 5 MET | 6 MET
    VERDICT P1: NULL (PBO 0.845 > 0.50: no group-level verdict ships)
```

excerpt     PBO (v3)

```
  T = 16 months (2025-05 .. 2026-08); trimmed earliest ['2024-06', '2024-07', '2024-08', '2024-09', '2024-10', '2024-11', '2024-12', '2025-01', '2025-02', '2025-03', '2025-04']; S = 16; combinations 12870; weights {'bear': 1.0}
  blank (no position) months per group: {'G1': 8, 'G2': 15, 'G5': 12, 'G6': 9, 'G7': 10}
  PBO 0.845 (lambda <= 0; 3729 combinations exactly at the median)
  P(IS argmax lands below the OOS median, lambda < 0 strictly) 0.556
  IS argmax: most often G2; share of combinations each group is IS-best: G1 0.049  G2 0.442  G5 0.099  G6 0.000  G7 0.409
  full-window statistic (mean of non-blank monthly cells): G1 -0.509  G2 +0.169  G5 -0.301  G6 -0.618  G7 -0.147   -> argmax G2
  degradation slope -0.363; P(OOS meanR of the IS pick < 0) 0.887
  READING: PBO 0.845 > 0.50: no group-level verdict ships; every graded contrast reads NULL
```
