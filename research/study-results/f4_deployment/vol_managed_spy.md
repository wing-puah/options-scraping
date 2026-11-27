# vol_managed_spy — per-era record

**Question.** Does scaling a SPY position by the inverse of recent realised volatility (Moreira and Muir 2017; capped at 1.0, the rest in T-bills, monthly, 5 bp on the SPY leg) beat a constant SPY and T-bill mix at the rule's own mean weight on the Sharpe ratio and the maximum drawdown (discovery 1993-2009 sign check, holdout 2010-01 to 2026-08 decides, Holm family of two)?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs e7318a6 · sha e0b58d2 — recorded 2026-11-27
<!-- key era=v4 sha=e0b58d2 inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-27 23:57:22 · git e0b58d2 (main, working tree dirty) · exit 0 · 5.2s
command     python -m scripts.backtest_study.f4_deployment.vol_managed_spy
excerpt     verdict

```
VERDICT
>>> vol_managed_spy HEADLINE (VOL-21-12 vs MIX, holdout 2010-01 to 2026-08, 5 bp): NULL <<<
>>> vol_managed_spy DISCOVERY (1993-05 to 2009-12): dSharpe +0.112 [-0.076, +0.320] dMDD +0.100 [-0.002, +0.216] wbar 0.767 at-cap 35% dCAGR +0.73 po…
>>> vol_managed_spy HOLDOUT (2010-01 to 2026-08): dSharpe +0.012 [-0.135, +0.149] p 0.4732 dMDD +0.053 [-0.021, +0.081] p 0.0816 wbar 0.837 at-cap 48…
>>> vol_managed_spy ARM R (alpha on SPY, holdout): NO-ALPHA alpha +0.008 [-0.008, +0.022] beta 0.68 <<<
>>> vol_managed_spy PBO (12 cells, S=16, in-sample): 0.630 <<<
>>> vol_managed_spy POST-PUBLICATION (2017-01 to 2026-08, printed only): dSharpe +0.025 [-0.161, +0.198] dMDD +0.050 [-0.011, +0.085] alpha +0.011 [-…
>>> vol_managed_spy FORWARD (VOL-21-12 vs MIX from 2026-12, 36-month floor, sunset 2030-11-30): STILL-OPEN (0 forward months of 36) <<<
  A headline statistic counts when it passes its Holm test on the holdout and its discovery point estimate is above 0.
  Nothing ships from this study (vol_managed_spy.md).
```

