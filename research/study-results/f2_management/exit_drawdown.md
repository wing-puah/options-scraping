# exit_drawdown — per-era record

**Question.** Does any exit rule — chosen WITHOUT look-ahead, on TRAIN dates only — reduce the ACCOUNT-LEVEL mark-to-market drawdown of the deployed account_sim book without giving back its edge? Five arms: W (walk-forward selection over the shipped pt x sl x tef grid, the honesty baseline), U (an underlying ATR stop with ATR14 FROZEN at entry), O (a flow-unwind exit off the entry long leg's own Open Int path, read LAGGED one session, plus one volume-climax variant), P (partial scale-out, exact), and D (a SECONDARY drawdown THROTTLE on sizing, which can never ship from an f2 study).

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs 76cc867 · sha e19d3b4 — recorded 2026-09-05
<!-- key era=v4 sha=e19d3b4 inputs=76cc867 -->

population  535 results · 1,303 proxy · 2,212 analysis · 820 spy_vix_daily_full  (inputs dated 2026-09-04 23:34 … 2026-09-05 09:48)
run         2026-09-05 12:53:26 · git e19d3b4 (main, working tree dirty) · exit 0 · 7.0s
command     python -m scripts.backtest_study.f2_management.exit_drawdown
excerpt     verdict

```
VERDICT SUMMARY
  ARM W/wf         UNDERPOWERED
  ARM W/prod       UNDERPOWERED
  ARM U/a          UNDERPOWERED
  ARM U/b          UNDERPOWERED
  ARM O/oi         UNDERPOWERED
  ARM O/vol        UNDERPOWERED
  ARM P/half       UNDERPOWERED
  ARM D/throttle   SECONDARY-UNDERPOWERED
  ARM W arm-level token: UNDERPOWERED
  PROD-ROBUST is NOT claimed — too few dates to say whether PROD survived.
  tally: {'UNDERPOWERED': 7, 'SECONDARY-UNDERPOWERED': 1}
```


## era v3 · inputs e400b13 · sha e19d3b4 — recorded 2026-09-05
<!-- key era=v3 sha=e19d3b4 inputs=e400b13 -->

population  406 results · 796 proxy · 1,607 analysis · 820 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-09-05 09:48)
run         2026-09-05 12:53:48 · git e19d3b4 (main, working tree dirty) · exit 0 · 3.5s
command     python -m scripts.backtest_study.f2_management.exit_drawdown
excerpt     verdict

```
VERDICT SUMMARY
  ARM W/wf         UNDERPOWERED   (no OOS dates)
  ARM W/prod       UNDERPOWERED   (no OOS dates)
  ARM U/a          UNDERPOWERED   (no OOS dates)
  ARM U/b          UNDERPOWERED   (no OOS dates)
  ARM O/oi         UNDERPOWERED   (no OOS dates)
  ARM O/vol        UNDERPOWERED   (no OOS dates)
  ARM P/half       UNDERPOWERED   (no OOS dates)
  ARM D/throttle   SECONDARY-UNDERPOWERED   (no OOS dates)
```

## era v4 · inputs 76cc867 · sha efd9b76 — recorded 2026-09-05
<!-- key era=v4 sha=efd9b76 inputs=76cc867 -->

population  535 results · 1,303 proxy · 2,212 analysis · 820 spy_vix_daily_full  (inputs dated 2026-09-04 23:34 … 2026-09-05 09:48)
run         2026-09-05 16:18:31 · git efd9b76 (main, working tree dirty) · exit 0 · 17.4s
command     python -m scripts.backtest_study.f2_management.exit_drawdown
excerpt     verdict

```
VERDICT SUMMARY
  population: PRIMARY  (PRIMARY — the cut the verdicts are read from)
  ARM W/wf         UNDERPOWERED
  ARM W/prod       UNDERPOWERED
  ARM U/a          UNDERPOWERED
  ARM U/b          UNDERPOWERED
  ARM O/oi         UNDERPOWERED
  ARM O/vol        UNDERPOWERED
  ARM P/half       UNDERPOWERED
  ARM D/throttle   SECONDARY-UNDERPOWERED
  ARM W arm-level token: UNDERPOWERED
  PROD-ROBUST is NOT claimed — too few dates to say whether PROD survived.
```


## era v3 · inputs e400b13 · sha efd9b76 — recorded 2026-09-05
<!-- key era=v3 sha=efd9b76 inputs=e400b13 -->

population  406 results · 796 proxy · 1,607 analysis · 820 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-09-05 09:48)
run         2026-09-05 16:18:23 · git efd9b76 (main, working tree dirty) · exit 0 · 7.0s
command     python -m scripts.backtest_study.f2_management.exit_drawdown
excerpt     verdict

```
VERDICT SUMMARY
  population: PRIMARY  (PRIMARY — the cut the verdicts are read from)
  ARM W/wf         UNDERPOWERED   (no OOS dates)
  ARM W/prod       UNDERPOWERED   (no OOS dates)
  ARM U/a          UNDERPOWERED   (no OOS dates)
  ARM U/b          UNDERPOWERED   (no OOS dates)
  ARM O/oi         UNDERPOWERED   (no OOS dates)
  ARM O/vol        UNDERPOWERED   (no OOS dates)
  ARM P/half       UNDERPOWERED   (no OOS dates)
  ARM D/throttle   SECONDARY-UNDERPOWERED   (no OOS dates)
  ARM W arm-level token: UNDERPOWERED
  PROD-ROBUST is NOT claimed — too few dates to say whether PROD survived.
```

