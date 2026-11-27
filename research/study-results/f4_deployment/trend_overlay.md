# trend_overlay — per-era record

**Question.** Does a slow trend rule (^GSPC below its 10-month SMA at month-end, Faber 2007) used as an exposure overlay cut the maximum drawdown of a 1x long S&P 500 position, at what cost in return (discovery SPY 1993-2026, holdout ^GSPC 1950-1992), and does cutting the account_sim net cap from 2.50 to 1.00 while below trend cut the book's drawdown?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs e028cbc · sha aee4477 — recorded 2026-11-21
<!-- key era=v4 sha=aee4477 inputs=e028cbc -->

population  1,178 results · 2,273 proxy · 3,782 analysis · 873 spy_vix_daily_full  (inputs dated 2026-11-21 12:09 … 2026-11-21 13:06)
run         2026-11-21 23:17:14 · git aee4477 (main, working tree clean) · exit 0 · 113.6s
command     python -m scripts.backtest_study.f4_deployment.trend_overlay
excerpt     verdict

```
VERDICT
  >>> trend_overlay A DISCOVERY (T-10M vs long SPY, 1993-02-01 to 2026-09-22, 10 bp, cash 0%): NO-DRAWDOWN-BENEFIT <<<
      dMDD +0.273 [-0.009, +0.457]  dCAGR -0.0153 [-0.0517, +0.0296]  whipsaw/yr -0.0309  episodes 4
  >>> trend_overlay A HOLDOUT (T-10M vs long ^GSPC price-only, 1950-01-03 to 1992-12-31, 10 bp, cash 0%): NO-DRAWDOWN-BENEFIT <<<
      dMDD +0.150 [-0.042, +0.335]  dCAGR -0.0138 [-0.0405, +0.0148]  whipsaw/yr -0.0228  episodes 7
  >>> trend_overlay A AGREEMENT: AGREES <<<
  >>> trend_overlay A SECONDARY (not graded): T-200D NO-DRAWDOWN-BENEFIT/CUTS-DRAWDOWN-AT-A-COST  T-12M NO-DRAWDOWN-BENEFIT/NO-DRAWDOWN-BENEFIT <<<
  >>> trend_overlay PBO: discovery 0.828 holdout 0.261 <<<
  >>> trend_overlay B (net cap 2.50 -> 1.00 while T-10M is OUT, v4 book to 2026-09-22): UNDERPOWERED <<<
  >>> trend_overlay FORWARD (T-10M vs long SPY from 2026-11-21, sunset 2029-11-21): STILL-OPEN <<<
  CUTS-DRAWDOWN-* needs the dMDD CI above 0, dCAGR at or above -2.0 points a year and a Calmar above LONG's.
  Nothing ships from this study (trend_overlay.md).
```


## Note 2026-11-21 · era named, graded

The machine header says era v4 because the runner names the book's era. Population A reads
unversioned market closes, so its era is `current (inputs are unversioned market closes)`, cut at
2026-09-22. Only Population B reads the v4 book, with the seal withholding 170 rows on 37 dates.

`study_review` graded this report: both analysts and the validator agree on every verdict and
gate. The one split is whether PBO is a graded criterion; the registration says it never changes
the headline word. Reading: [current.md](../../current.md#2026-11-21--trend_overlay-a-slow-trend-rule-roughly-halves-drawdown-but-not-clear-of-noise).

## Note 2026-11-21 · smoke run disclosed

One smoke run at 50 bootstrap draws ran after the registration commit (4e3ca8d) and before the
graded run. It was there to check Population B and the gates. Nothing in the registration, code
or config changed after it. The graded run is the one recorded above.

## era v4 · inputs e7318a6 · sha f04686e — recorded 2026-11-27
<!-- key era=v4 sha=f04686e inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 12:12)
run         2026-11-27 14:43:06 · git f04686e (main, working tree clean) · exit 0 · 65.0s
command     python -m scripts.backtest_study.f4_deployment.trend_overlay
excerpt     verdict

```
VERDICT
  >>> trend_overlay A DISCOVERY (T-10M vs long SPY, 1993-02-01 to 2026-09-22, 10 bp, cash 0%): NO-DRAWDOWN-BENEFIT <<<
      dMDD +0.273 [-0.009, +0.457]  dCAGR -0.0153 [-0.0517, +0.0296]  whipsaw/yr -0.0309  episodes 4
  >>> trend_overlay A HOLDOUT (T-10M vs long ^GSPC price-only, 1950-01-03 to 1992-12-31, 10 bp, cash 0%): NO-DRAWDOWN-BENEFIT <<<
      dMDD +0.150 [-0.042, +0.335]  dCAGR -0.0138 [-0.0405, +0.0148]  whipsaw/yr -0.0228  episodes 7
  >>> trend_overlay A AGREEMENT: AGREES <<<
  >>> trend_overlay A SECONDARY (not graded): T-200D NO-DRAWDOWN-BENEFIT/CUTS-DRAWDOWN-AT-A-COST  T-12M NO-DRAWDOWN-BENEFIT/NO-DRAWDOWN-BENEFIT <<<
  >>> trend_overlay PBO: discovery 0.828 holdout 0.261 <<<
  >>> trend_overlay B (net cap 2.50 -> 1.00 while T-10M is OUT, v4 book to 2026-09-22): UNDERPOWERED <<<
  >>> trend_overlay FORWARD (T-10M vs long SPY from 2026-11-21, sunset 2029-11-21): STILL-OPEN <<<
  CUTS-DRAWDOWN-* needs the dMDD CI above 0, dCAGR at or above -2.0 points a year and a Calmar above LONG's.
  Nothing ships from this study (trend_overlay.md).
```

