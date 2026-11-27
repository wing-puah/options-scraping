# sector_momentum — per-era record

**Question.** Does holding the three of the nine original SPDR sector ETFs with the strongest 12-1 return, rebalanced monthly at 5 bp a side, beat holding all nine in rebalanced equal weight over 2000-01 to 2026-08?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era current · inputs e0c2e79 · sha 8e94d19 — recorded 2026-11-28
<!-- key era=current sha=8e94d19 inputs=e0c2e79 -->

population  16,711 IRX · 7,270 SPY · 7,025 XLB · 111 XLB_dividends · 7,025 XLE · 112 XLE_dividends · 7,025 XLF · 111 XLF_dividends · 7,025 XLI · 110 XLI_dividends · 7,025 XLK · 85 XLK_dividends · 7,025 XLP · 111 XLP_dividends · 7,025 XLU · 112 XLU_dividends · 7,025 XLV · 106 XLV_dividends · 7,025 XLY · 111 XLY_dividends  (inputs dated 2026-11-28 02:35)
run         2026-11-28 02:36:26 · git 8e94d19 (main, working tree dirty) · exit 0 · 8.8s
command     python -m scripts.backtest_study.f1_selection.signal.sector_momentum
excerpt     verdict

```
VERDICT
>>> sector_momentum HEADLINE (12-1-T3 vs EW-9, pooled 2000-01 to 2026-08, 5 bp): UNDERPOWERED-BY-DESIGN (could not see one: delta80 above REF) <<<
>>> sector_momentum POOLED (2000-01 to 2026-08): XS +0.19% [-2.20%, +2.62%] p 0.8676 IR +0.026 [-0.307, +0.368] <<<
>>> sector_momentum HALVES (sign checks): 2000-01 to 2012-12 XS -0.75% [-4.66%, +3.13%]; 2013-01 to 2026-08 XS +1.08% [-1.83%, +4.08%] <<<
>>> sector_momentum CALIBRATION (0 bp size, block 6, bound 0.075): G-IID 0.070 G-GARCH 0.074 G-MONTH 0.056 <<<
>>> sector_momentum POWER (delta80 0.0450 vs REF 0.030; BEATS-EW false-positive 0.026) <<<
>>> sector_momentum PBO (12 cells, S=16, metric mean d_m, in-sample): 0.656 <<<
>>> sector_momentum FORWARD (12-1-T3 vs EW-9, 2026-12 to 2029-11, sunset 2030-11-30): STILL-OPEN (0 complete forward months) <<<
  beside the word: max drawdown 12-1-T3 40.9%, EW-9 48.9%; alpha/beta vs EW-9 +0.91%/0.91, vs SPY +1.81%/0.86; G-MEANS mean XS -0.02%
  best sector-month removed: XLE 2021-02: XS -0.38%, -206% of the original
  UNDERPOWERED-BY-DESIGN means the test could not see one: delta80 0.0450 is the smallest gain it would usually have seen. It never means no effect.
  The rule counts when graded p < 0.05, graded XS > 0 and both halves' XS > 0.
  Nothing ships from this study (sector_momentum.md).
```

