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
