# tail_breach — per-era record

**Question.** How often does SPY fall more than twice the one-day move its prior close's VIX implied, in 2024, 2025 and 2026, and do four VIX readings at that close forecast such a breach in the next five sessions better than the base rate?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 0984c38 · sha 1f89e6f — recorded 2026-11-14
<!-- key era=v4 sha=1f89e6f inputs=0984c38 -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 870 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-11-14 01:02)
run         2026-11-14 13:27:43 · git 1f89e6f (main, working tree dirty) · exit 0 · 2.4s
command     python -m scripts.backtest_study.f1_selection.regime.tail_breach --refresh
excerpt     verdict

```
VERDICT
  test window 2024-01-02 -> 2026-11-06 (origins); 717 rows, 9 episodes; 10000 moving-block draws (block 21), seed 20261114
  >>> tail_breach P (four-predictor logistic, any 2x-VIX down breach in the next 5 sessions, test from 2024-01-02): UNDERPOWERED <<<
  >>> tail_breach SECONDARY (each predictor alone, Holm m=4): S1 UNDERPOWERED S2 UNDERPOWERED S3 UNDERPOWERED S4 UNDERPOWERED <<<
  >>> tail_breach N1 (four-predictor logistic, next-session breach): UNDERPOWERED <<<
  >>> tail_breach FORWARD (forecast origins after the registration date): STILL-OPEN <<<
  PREDICTABLE needs the 95% CI on the Brier skill score wholly above 0; S1-S4 also
  need a Holm-adjusted p below 0.05. AUC is context only.
  Nothing ships from this study (tail_breach.md).
```

