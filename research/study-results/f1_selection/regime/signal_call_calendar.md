# signal_call_calendar — per-era record

**Question.** After a mech BEAR or E-VOL onset (state_map's Q3 signals, 2022-02-01 to 2026-09-22), does a SPY call calendar (short the monthly nearest 30 DTE, long the same strike nearest 60 DTE, strike nearest spot x 1.03, out after 21 sessions) pay net of commission, and does it beat the same calendar opened on a calm day?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs e028cbc · sha e5e0e3c — recorded 2026-11-21
<!-- key era=v4 sha=e5e0e3c inputs=e028cbc -->

population  1,178 results · 2,273 proxy · 3,782 analysis · 873 spy_vix_daily_full  (inputs dated 2026-11-21 12:09 … 2026-11-21 13:06)
run         2026-11-21 20:24:34 · git e5e0e3c (main, working tree clean) · exit 0 · 12.9s
command     python -m scripts.backtest_study.f1_selection.regime.signal_call_calendar
excerpt     verdict

```
VERDICT
  >>> signal_call_calendar K-BEAR (call calendar after S-BEAR, 1.03 strike, 30/60 DTE, 21 sessions or short expiry, 2022-02-01 to 2026-09-22): NULL <…
  >>> signal_call_calendar K-EVOL (call calendar after S-EVOL, 1.03 strike, 30/60 DTE, 21 sessions or short expiry, 2022-02-01 to 2026-09-22): NULL <…
  >>> signal_call_calendar PBO: 0.334 <<<  [second structure on one signal set; geometry set after Q4]
  >>> signal_call_calendar FORWARD (onsets from 2026-11-21, current sell-off out): K-BEAR STILL-OPEN K-EVOL STILL-OPEN <<<  [second structure on one …
  CALENDAR-PAYS files 'to be tested' in deployment-evidence.md, pending the forward read.
  Nothing ships from this study (signal_call_calendar.md).
```


## era v4 · inputs 2f45ae6 · sha 436c8f7 — recorded 2026-11-26
<!-- key era=v4 sha=436c8f7 inputs=2f45ae6 -->

population  1,214 results · 2,286 proxy · 3,826 analysis · 878 spy_vix_daily_full · 703 BaselineDaily  (inputs dated 2026-11-26 11:38 … 2026-11-26 14:01)
run         2026-11-26 15:10:00 · git 436c8f7 (main, working tree clean) · exit 0 · 7.6s
command     python -m scripts.backtest_study.f1_selection.regime.signal_call_calendar
excerpt     verdict

```
VERDICT
  >>> signal_call_calendar K-BEAR (call calendar after S-BEAR, 1.03 strike, 30/60 DTE, 21 sessions or short expiry, 2022-02-01 to 2026-09-22): NULL <…
  >>> signal_call_calendar K-EVOL (call calendar after S-EVOL, 1.03 strike, 30/60 DTE, 21 sessions or short expiry, 2022-02-01 to 2026-09-22): NULL <…
  >>> signal_call_calendar PBO: 0.334 <<<  [second structure on one signal set; geometry set after Q4]
  >>> signal_call_calendar FORWARD (onsets from 2026-11-21, current sell-off out): K-BEAR STILL-OPEN K-EVOL STILL-OPEN <<<  [second structure on one …
  CALENDAR-PAYS files 'to be tested' in deployment-evidence.md, pending the forward read.
  Nothing ships from this study (signal_call_calendar.md).
```

