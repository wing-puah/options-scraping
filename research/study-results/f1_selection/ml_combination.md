# ml_combination — per-era record

**Question.** Does any learned combination of structure × regime × geometry × enrichment beat the score-free ladder out of sample?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v3 — recorded 2026-08-15
<!-- key era=v3 sha=53b7167 -->

population  1,926 results · 4,533 proxy · 11,836 analysis · 805 spy_vix_daily_full  (inputs dated 2026-08-15 12:38 … 2026-08-15 19:03)
run         2026-08-15 23:45:14 · git 53b7167 (main, working tree dirty) · exit 0 · 29.7s
command     python -m scripts.backtest_study.f1_selection.ml_combination
excerpt     verdict

```
PHASE 5 — pre-registered ship decision (ml-plan.md, written before the run)
  M3 out-of-fold paired R gain vs B0: -0.155 CI95 [-0.314, -0.001]  -> CI excludes zero: False
  positive in >=2 of 3 years: False  ({'2025': 0.3612206349206349, '2026': -0.12093899999999999})
  survives both ex-window cuts: True
  B1  gain -0.173 CI [-0.374, +0.010]
  B2  gain -0.180 CI [-0.363, -0.024]
  M1  gain -0.096 CI [-0.228, +0.023]
  M2  gain -0.113 CI [-0.268, +0.035]
  VERDICT: NULL RESULT — the ladder is at/near the ceiling of this data
  (ADOPT-AS-TIE-BREAK requires a within-tier ordering gain at the same CI standard —
   evaluate only if a model's gain CI excludes zero while M3's does not.)
Dataset written to /Users/wing/claude_playground/options-trading/backtests/study_output/dataset.csv
```

## era v4 · inputs dd4c8aa · sha d47e227 — recorded 2026-08-22
<!-- key era=v4 sha=d47e227 inputs=dd4c8aa -->

population  1,212 results · 2,967 proxy · 8,470 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-22 10:37 … 2026-08-22 18:08)
run         2026-08-22 20:12:26 · git d47e227 (main, working tree dirty) · exit 0 · 13.9s
command     python -m scripts.backtest_study.f1_selection.ml_combination
excerpt     verdict

```
PHASE 5 — pre-registered ship decision (ml-plan.md, written before the run)
  M3 out-of-fold paired R gain vs B0: -0.012 CI95 [-0.151, +0.119]  -> CI excludes zero: False
  positive in >=2 of 3 years: False  ({'2024': -0.15548333333333333, '2025': 0.15194141414141413})
  survives both ex-window cuts: True
  B1  gain -0.030 CI [-0.173, +0.106]
  B2  gain -0.071 CI [-0.178, +0.035]
  M1  gain +0.006 CI [-0.105, +0.116]
  M2  gain +0.003 CI [-0.151, +0.145]
  VERDICT: NULL RESULT — the ladder is at/near the ceiling of this data
  (ADOPT-AS-TIE-BREAK requires a within-tier ordering gain at the same CI standard —
   evaluate only if a model's gain CI excludes zero while M3's does not.)
Dataset written to /Users/wing/claude_playground/options-trading/backtests/study_output/dataset.csv
```


## era v4 · inputs 46cc19b · sha c841a01 — recorded 2026-08-24
<!-- key era=v4 sha=c841a01 inputs=46cc19b -->

population  280 results · 627 proxy · 1,146 analysis · 810 spy_vix_daily_full  (inputs dated 2026-08-24 17:09 … 2026-08-24 18:08)
run         2026-08-24 18:20:39 · git c841a01 (main, working tree dirty) · exit 0 · 9.4s
command     python -m scripts.backtest_study.f1_selection.ml_combination
excerpt     verdict

```
PHASE 5 — pre-registered ship decision (ml-plan.md, written before the run)
  M3 out-of-fold paired R gain vs B0: -0.103 CI95 [-0.239, +0.023]  -> CI excludes zero: False
  positive in >=2 of 3 years: False  ({'2024': -0.2699555555555555, '2025': 0.06473838383838383})
  survives both ex-window cuts: True
  B1  gain -0.045 CI [-0.191, +0.102]
  B2  gain -0.097 CI [-0.213, +0.019]
  M1  gain -0.078 CI [-0.207, +0.049]
  M2  gain -0.004 CI [-0.145, +0.132]
  VERDICT: NULL RESULT — the ladder is at/near the ceiling of this data
  (ADOPT-AS-TIE-BREAK requires a within-tier ordering gain at the same CI standard —
   evaluate only if a model's gain CI excludes zero while M3's does not.)
Dataset written to /Users/wing/claude_playground/options-trading/backtests/study_output/dataset.csv
```


## era v4 · inputs 44c76b5 · sha 25f3e27 — recorded 2026-08-27
<!-- key era=v4 sha=25f3e27 inputs=44c76b5 -->

population  485 results · 1,111 proxy · 1,893 analysis · 813 spy_vix_daily_full  (inputs dated 2026-08-27 11:31 … 2026-08-27 20:34)
run         2026-08-27 20:37:13 · git 25f3e27 (main, working tree dirty) · exit 0 · 24.1s
command     python -m scripts.backtest_study.f1_selection.ml_combination
excerpt     verdict

```
PHASE 5 — ship decision, pre-registered BEFORE the run (pre-registrations/f1_selection/ml_combination.md)
  M3 out-of-fold paired R gain vs B0: -0.028 CI95 [-0.139, +0.081]  -> CI excludes zero: False
  positive in >=2 of 3 years: True  ({'2024': 0.29991927710843375, '2025': 0.10605722891566265})
  survives both ex-window cuts: True
  B1  gain -0.037 CI [-0.159, +0.086]
  B2  gain -0.058 CI [-0.180, +0.064]
  M1  gain -0.013 CI [-0.140, +0.110]
  M2  gain -0.010 CI [-0.125, +0.101]
  VERDICT: NULL RESULT — the ladder is at/near the ceiling of this data
  (ADOPT-AS-TIE-BREAK requires a within-tier ordering gain at the same CI standard —
   evaluate only if a model's gain CI excludes zero while M3's does not.)
Dataset written to /Users/wing/claude_playground/options-trading/backtests/study_output/dataset.csv
```

