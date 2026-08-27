# vol_sleeve — per-era record

**Question.** Synthesize straddle / strangle / calendar on the dates the engine already signalled. Is there a vol sleeve in here?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:46:49 · git 53b7167 (main, working tree dirty) · exit 0 · 33.8s
command     python -m scripts.backtest_study.f3_structure.vol_sleeve
excerpt     tail

```
  vrp < 0 (implied cheap)         237  +0.160   -0.022            [+0.008, +0.350]  <- excludes 0
  earnings inside DTE             178  +0.082   +0.056            [-0.149, +0.194]
  iv_pct bottom tercile (<0.55)   144  +0.033   +0.079            [-0.223, +0.132]
--- calendar  (n=171) -------------------------------------------------------
  condition                         n   meanE  vs rest  diff CI95 (date-clustered)
  vrp < 0 (implied cheap)          74  -0.094   +0.950            [-2.597, +0.072]
  earnings inside DTE              37  +0.186   +0.585            [-1.520, +0.410]
  iv_pct bottom tercile (<0.57)    49  -0.131   +0.751            [-2.114, +0.029]
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 18:13:37 · git d47e227 (main, working tree dirty) · exit 0 · 15.5s
command     python -m scripts.backtest_study.f3_structure.vol_sleeve
excerpt     tail

```
  vrp < 0 (implied cheap)          48  -0.072   -0.126            [-0.200, +0.266]
  earnings inside DTE              41  +0.100   -0.212            [+0.033, +0.607]  <- excludes 0
  iv_pct bottom tercile (<0.44)    36  -0.117   -0.099            [-0.279, +0.256]
--- calendar  (n=38) --------------------------------------------------------
  condition                         n   meanE  vs rest  diff CI95 (date-clustered)
  vrp < 0 (implied cheap)          10  +0.205   +0.603            [-1.373, +0.412]
  earnings inside DTE              16  +1.088   +0.070            [-0.227, +2.890]
  iv_pct bottom tercile (<0.42)    10  +1.338   +0.198            [-0.466, +4.133]
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:22:50 · git c841a01 (main, working tree dirty) · exit 0 · 10.5s
command     python -m scripts.backtest_study.f3_structure.vol_sleeve
excerpt     tail

```
  vrp < 0 (implied cheap)          51  -0.087   -0.116            [-0.210, +0.245]
  earnings inside DTE              42  +0.093   -0.203            [+0.028, +0.591]  <- excludes 0
  iv_pct bottom tercile (<0.43)    38  -0.180   -0.071            [-0.379, +0.150]
--- calendar  (n=50) --------------------------------------------------------
  condition                         n   meanE  vs rest  diff CI95 (date-clustered)
  vrp < 0 (implied cheap)          16  +0.374   +0.532            [-0.987, +0.551]
  earnings inside DTE              23  +0.878   +0.143            [-0.215, +2.064]
  iv_pct bottom tercile (<0.42)    14  +1.068   +0.253            [-0.457, +2.910]
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:42:21 · git 25f3e27 (main, working tree dirty) · exit 0 · 18.9s
command     python -m scripts.backtest_study.f3_structure.vol_sleeve
excerpt     tail

```
  vrp < 0 (implied cheap)          97  -0.092   +0.002            [-0.352, +0.143]
  earnings inside DTE              75  -0.022   -0.045            [-0.237, +0.274]
  iv_pct bottom tercile (<0.36)    71  -0.090   -0.014            [-0.370, +0.242]
--- calendar  (n=117) -------------------------------------------------------
  condition                         n   meanE  vs rest  diff CI95 (date-clustered)
  vrp < 0 (implied cheap)          36  +0.450   +0.272            [-0.212, +0.547]
  earnings inside DTE              44  +0.556   +0.189            [-0.150, +1.093]
  iv_pct bottom tercile (<0.32)    36  +0.580   +0.214            [-0.173, +1.182]
```

