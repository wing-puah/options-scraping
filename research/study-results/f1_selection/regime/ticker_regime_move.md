# ticker_regime_move — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs e7318a6 · sha 3d2cae8 — recorded 2026-11-27
<!-- key era=v4 sha=3d2cae8 inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 12:12)
run         2026-11-27 16:45:20 · git 3d2cae8 (main, working tree clean) · exit 0 · 14.4s
command     python -m scripts.backtest_study.f1_selection.regime.ticker_regime_move
excerpt     verdict

```
VERDICT
  era v4, 21-session window closed by 2026-11-25: 2923 rows, 303 dates, 34 blocks; 10000 block draws, seed 20261127
  bres21 in percentage points; absz10 as a ratio; [95% CI]
  D       +3.77 [+0.66, +6.38]  p=0.0110  discarded draws 0
          above BULL 1310r/34b BEAR 27r/18b diff +4.19 (under floor); below BULL 50r/19b BEAR 483r/34b diff +2.72
          Holm adj p 1.0000
  S      +0.102 [+0.010, +0.203]  p=0.0286  E-VOL 731r/34b  other-vol 1647r/34b  Holm adj p 0.0572
  >>> ticker_regime_move D (BULL - BEAR, 21d beta-adjusted return, own-trend strata, v4 in-sample): UNDERPOWERED <<<
  >>> ticker_regime_move S (E-VOL - other vol, scaled 10d move, v4 in-sample): NULL <<<
  >>> ticker_regime_move READ (D): UNDERPOWERED <<<
  >>> ticker_regime_move FORWARD (LIVE signal dates after 2026-11-27): D STILL-OPEN, S STILL-OPEN <<<
  D and S are one Holm family (m = 2) at 0.05.
  The first run is the in-sample verdict of record. A contrast's forward verdict of record is its first word other than STILL-OPEN.
  Nothing ships from this study (ticker_regime_move.md).
```


## era v3 · inputs 29371be · sha 3d2cae8 — recorded 2026-11-27
<!-- key era=v3 sha=3d2cae8 inputs=29371be -->

population  406 results · 796 proxy · 1,607 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-08-15 19:03 … 2026-11-27 07:17)
run         2026-11-27 16:45:53 · git 3d2cae8 (main, working tree dirty) · exit 0 · 7.7s
command     python -m scripts.backtest_study.f1_selection.regime.ticker_regime_move
excerpt     verdict

```
VERDICT
  era v3, 21-session window closed by 2026-11-25: 1314 rows, 141 dates, 21 blocks; 10000 block draws, seed 20261127
  bres21 in percentage points; absz10 as a ratio; [95% CI]
  D       -1.00 [-5.45, +2.20]  p=0.5818  discarded draws 0
          above BULL 451r/21b BEAR 22r/11b diff -0.96 (under floor); below BULL 101r/17b BEAR 387r/20b diff -1.04
          Holm adj p 1.0000
  S      +0.118 [-0.056, +0.310]  p=0.1808  E-VOL 345r/19b  other-vol 568r/19b  Holm adj p 0.3616
  >>> ticker_regime_move D (BULL - BEAR, 21d beta-adjusted return, own-trend strata, v3 in-sample): UNDERPOWERED <<<
  >>> ticker_regime_move S (E-VOL - other vol, scaled 10d move, v3 in-sample): NULL <<<
  >>> ticker_regime_move READ (D): UNDERPOWERED <<<
  >>> ticker_regime_move FORWARD (LIVE signal dates after 2026-11-27): D STILL-OPEN, S STILL-OPEN <<<
  D and S are one Holm family (m = 2) at 0.05.
  The first run is the in-sample verdict of record. A contrast's forward verdict of record is its first word other than STILL-OPEN.
  Nothing ships from this study (ticker_regime_move.md).
```

