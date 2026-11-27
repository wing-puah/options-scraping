# tail_breach_intraday — per-era record

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs 0984c38 · sha 1b22bc2 — recorded 2026-11-14
<!-- key era=v4 sha=1b22bc2 inputs=0984c38 -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 870 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-11-14 01:02)
run         2026-11-14 23:52:45 · git 1b22bc2 (main, working tree dirty) · exit 0 · 4.3s
command     python -m scripts.backtest_study.f1_selection.regime.tail_breach_intraday
excerpt     verdict

```
VERDICT
  PA test window 2024-01-02 -> 2026-11-06 (origins); 717 rows, 13 episodes
  PB test window 2024-01-02 -> 2026-11-06 (origins); 717 rows, 3 episodes
  10000 moving-block draws (block 21), seed 20261114
  >>> tail_breach_intraday PA (four-predictor logistic, any intraday 2x-VIX breach in the next 5 sessions, test from 2024-01-02): NO-FORECAST <<<
  >>> tail_breach_intraday PB (four-predictor logistic, intraday low 5% below the origin close within 5 sessions, test from 2024-01-02): UNDERPOWERED…
  >>> tail_breach_intraday SECONDARY A (each predictor alone, Holm m=4): SA1 NO-FORECAST SA2 NO-FORECAST SA3 NO-FORECAST SA4 NO-FORECAST <<<
  >>> tail_breach_intraday SECONDARY B (each predictor alone, Holm m=4): SB1 UNDERPOWERED SB2 UNDERPOWERED SB3 UNDERPOWERED SB4 UNDERPOWERED <<<
  >>> tail_breach_intraday NA1 (four-predictor logistic, next-session intraday breach): NO-FORECAST <<<
  >>> tail_breach_intraday FORWARD (forecast origins after the registration date): PA STILL-OPEN PB STILL-OPEN <<<
  PREDICTABLE needs the 95% CI on the Brier skill score wholly above 0 and a Holm-adjusted
  p below 0.05 (PA/PB m=2; SA/SB m=4). AUC is context only.
  Nothing ships from this study (tail_breach_intraday.md).
```


## era v4 · inputs 2f45ae6 · sha 436c8f7 — recorded 2026-11-26
<!-- key era=v4 sha=436c8f7 inputs=2f45ae6 -->

population  1,214 results · 2,286 proxy · 3,826 analysis · 878 spy_vix_daily_full · 703 BaselineDaily  (inputs dated 2026-11-26 11:38 … 2026-11-26 14:01)
run         2026-11-26 15:10:22 · git 436c8f7 (main, working tree clean) · exit 0 · 2.0s
command     python -m scripts.backtest_study.f1_selection.regime.tail_breach_intraday
excerpt     verdict

```
VERDICT
  PA test window 2024-01-02 -> 2026-11-06 (origins); 717 rows, 13 episodes
  PB test window 2024-01-02 -> 2026-11-06 (origins); 717 rows, 3 episodes
  10000 moving-block draws (block 21), seed 20261114
  >>> tail_breach_intraday PA (four-predictor logistic, any intraday 2x-VIX breach in the next 5 sessions, test from 2024-01-02): NO-FORECAST <<<
  >>> tail_breach_intraday PB (four-predictor logistic, intraday low 5% below the origin close within 5 sessions, test from 2024-01-02): UNDERPOWERED…
  >>> tail_breach_intraday SECONDARY A (each predictor alone, Holm m=4): SA1 NO-FORECAST SA2 NO-FORECAST SA3 NO-FORECAST SA4 NO-FORECAST <<<
  >>> tail_breach_intraday SECONDARY B (each predictor alone, Holm m=4): SB1 UNDERPOWERED SB2 UNDERPOWERED SB3 UNDERPOWERED SB4 UNDERPOWERED <<<
  >>> tail_breach_intraday NA1 (four-predictor logistic, next-session intraday breach): NO-FORECAST <<<
  >>> tail_breach_intraday FORWARD (forecast origins after the registration date): PA STILL-OPEN PB STILL-OPEN <<<
  PREDICTABLE needs the 95% CI on the Brier skill score wholly above 0 and a Holm-adjusted
  p below 0.05 (PA/PB m=2; SA/SB m=4). AUC is context only.
  Nothing ships from this study (tail_breach_intraday.md).
```


## era v4 · inputs e7318a6 · sha f04686e — recorded 2026-11-27
<!-- key era=v4 sha=f04686e inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 12:12)
run         2026-11-27 14:20:44 · git f04686e (main, working tree clean) · exit 0 · 2.2s
command     python -m scripts.backtest_study.f1_selection.regime.tail_breach_intraday
excerpt     verdict

```
VERDICT
  PA test window 2024-01-02 -> 2026-11-06 (origins); 717 rows, 13 episodes
  PB test window 2024-01-02 -> 2026-11-06 (origins); 717 rows, 3 episodes
  10000 moving-block draws (block 21), seed 20261114
  >>> tail_breach_intraday PA (four-predictor logistic, any intraday 2x-VIX breach in the next 5 sessions, test from 2024-01-02): NO-FORECAST <<<
  >>> tail_breach_intraday PB (four-predictor logistic, intraday low 5% below the origin close within 5 sessions, test from 2024-01-02): UNDERPOWERED…
  >>> tail_breach_intraday SECONDARY A (each predictor alone, Holm m=4): SA1 NO-FORECAST SA2 NO-FORECAST SA3 NO-FORECAST SA4 NO-FORECAST <<<
  >>> tail_breach_intraday SECONDARY B (each predictor alone, Holm m=4): SB1 UNDERPOWERED SB2 UNDERPOWERED SB3 UNDERPOWERED SB4 UNDERPOWERED <<<
  >>> tail_breach_intraday NA1 (four-predictor logistic, next-session intraday breach): NO-FORECAST <<<
  >>> tail_breach_intraday FORWARD (forecast origins after the registration date): PA STILL-OPEN PB STILL-OPEN <<<
  PREDICTABLE needs the 95% CI on the Brier skill score wholly above 0 and a Holm-adjusted
  p below 0.05 (PA/PB m=2; SA/SB m=4). AUC is context only.
  Nothing ships from this study (tail_breach_intraday.md).
```

