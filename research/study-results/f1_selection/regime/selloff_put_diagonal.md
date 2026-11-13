# selloff_put_diagonal — per-era record

**Question.** On a SPY sell-off trigger (E-DD5: 5% below the 63-session high, disarmed on a close back above -2%), does a near ATM put plus a long-dated call diagonal, rolled three times, pay net of commission? Graded against zero, against the same package on calm weeks (ARM C), and for the put's own contribution.

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 61bda3a · sha 102d6fb — recorded 2026-11-13
<!-- key era=v4 sha=102d6fb inputs=61bda3a -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 854 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-10-26 01:06)
run         2026-11-13 14:40:56 · git 102d6fb (main, working tree clean) · exit 0 · 35.3s
command     python -m scripts.backtest_study.f1_selection.regime.selloff_put_diagonal
excerpt     verdict

```
VERDICT
  ARM K vs zero          PAYS (PROVISIONAL)
  ARM K vs ARM C         NULL (PROVISIONAL)
  put contribution       NULL (PROVISIONAL)
  STUDY                  NO-EDGE (PROVISIONAL)
  FORWARD                STILL-OPEN  (0 forward triggers, 0 closed and priced; confirmation needs 3)
  Nothing ships from this study.
  trades -> backtests/study_output/selloff_put_diagonal-trades.csv
```

