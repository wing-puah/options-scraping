# earnings_vol — per-era record

**Question.** Across 11 earnings seasons on a fixed list of 25 names, does a long ATM straddle or a long ATM double calendar, entered 5 sessions before the report and closed the session after, earn a positive mean return whose daily P&L does not move with the deployed book?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs a5f1fab · sha 65e4d0d — recorded 2026-10-13
<!-- key era=v4 sha=65e4d0d inputs=a5f1fab -->

population  1,020 results · 2,021 proxy · 3,417 analysis · 845 spy_vix_daily_full  (inputs dated 2026-10-06 23:39 … 2026-10-12 22:05)
run         2026-10-13 00:56:55 · git 65e4d0d (main, working tree dirty) · exit 0 · 12.0s
command     python -m scripts.backtest_study.f3_structure.earnings_vol
excerpt     verdict

```
VERDICT
  ARM S (mid, exit E, in-sample): n 271  mean +0.019  CI95 [-0.085, +0.123] over 11 seasons;  H1 +0.064  H2 -0.036;  G1 corr -0.066 -> PASS
  ARM K (mid, exit E, in-sample): n 161  mean +0.073  CI95 [-0.024, +0.170] over 11 seasons;  H1 +0.079  H2 +0.067;  G1 corr -0.018 -> PASS
  >>> earnings_vol ARM S NULL / ARM K NULL <<<
  secondary, ARM S natural fill: NULL
  secondary, ARM S run-up exit (close of E-1): NULL
  secondary, ARM S with unknown-as-amc events: NULL
  secondary, ARM S at the 0.10 gate: NULL
  secondary, ARM K natural fill: CONTRARY
  secondary, ARM K run-up exit (close of E-1): NULL
  secondary, ARM K with unknown-as-amc events: NULL
  secondary, ARM K at the 0.10 gate: NULL
  forward (2 sealed events): STILL-OPEN
  Nothing ships.
```

