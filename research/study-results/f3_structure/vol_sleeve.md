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
