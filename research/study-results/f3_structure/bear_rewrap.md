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

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:11:20 · git d47e227 (main, working tree dirty) · exit 0 · 16.7s
command     python -m scripts.backtest_study.f3_structure.bear_rewrap
excerpt     matched

```
  P1 worst-decile: n= 18  meanR -0.068  CI [-0.587, +0.449]  $+316   -> not met
  P2 correlation with deployed sleeve: -0.183 over 68 shared dates   -> MET
  P1 worst-decile: n= 13  meanR -0.178  CI [-0.548, +0.223]  $-2,692   -> not met
  P2 correlation with deployed sleeve: -0.192 over 52 shared dates   -> MET
  P1 worst-decile: n= 11  meanR +0.815  CI [+0.212, +1.371]  $+11,946   -> MET
  P2 correlation with deployed sleeve: -0.257 over 51 shared dates   -> MET
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:21:21 · git c841a01 (main, working tree dirty) · exit 0 · 10.8s
command     python -m scripts.backtest_study.f3_structure.bear_rewrap
excerpt     matched

```
  P1 worst-decile: n= 18  meanR -0.068  CI [-0.587, +0.449]  $+316   -> not met
  P2 correlation with deployed sleeve: -0.156 over 73 shared dates   -> MET
  P1 worst-decile: n= 14  meanR -0.096  CI [-0.426, +0.284]  $-1,387   -> not met
  P2 correlation with deployed sleeve: -0.221 over 57 shared dates   -> MET
  P1 worst-decile: n= 10  meanR +0.902  CI [+0.275, +1.498]  $+12,004   -> MET
  P2 correlation with deployed sleeve: -0.275 over 54 shared dates   -> MET
```

