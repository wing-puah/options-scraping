# bear_rewrap — per-era record

**Question.** A bear SPREAD sells the lower put, giving away the vol expansion that makes a bear position pay. What if the short leg goes?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:46:18 · git 53b7167 (main, working tree dirty) · exit 0 · 22.2s
command     python -m scripts.backtest_study.f3_structure.bear_rewrap
excerpt     matched

```
  P1 worst-decile: n= 21  meanR +0.262  CI [-0.273, +0.730]  $+9,450   -> not met
  P2 correlation with deployed sleeve: -0.089 over 84 shared dates   -> MET
  P1 worst-decile: n= 13  meanR +0.160  CI [-0.306, +0.527]  $+2,505   -> not met
  P2 correlation with deployed sleeve: -0.130 over 74 shared dates   -> MET
  P1 worst-decile: n= 10  meanR -0.188  CI [-0.746, +0.318]  $-2,458   -> not met
  P2 correlation with deployed sleeve: -0.070 over 65 shared dates   -> MET
```
