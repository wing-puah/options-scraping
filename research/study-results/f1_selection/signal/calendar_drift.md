# calendar_drift — per-era record

**Question.** Do the pre-FOMC drift (SPY's close-to-close return on scheduled FOMC decision days, 2012 on) and the turn of the month (the last session plus the first three of the next, 2009 on) still beat SPY's other days after publication, net of 2 bps a side?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs e7318a6 · sha 558da68 — recorded 2026-11-27
<!-- key era=v4 sha=558da68 inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-27 19:39:08 · git 558da68 (main, working tree dirty) · exit 3 (designed refusal) · 5.4s
command     python -m scripts.backtest_study.f1_selection.signal.calendar_drift --refresh
excerpt     refusal

```
     236 lines  2026-11-27 17:05  config/macro-events.yml
config/fomc-history.yml git blob: 0e8f84cfa1fff3c30795bc564ff685529f801807
SEAL: not applied — no flow signal, play or backtest row is read
cost 4 bps round trip (2 a side), charged COST/n per window day; cycle bootstrap 10000 draws, seed 20261127
transcription fixes to config/fomc-history.yml after the first report: none
GATES — refusals (GE, GB, GF)
  GE: SPY ends 2026-11-25, before the registration date 2026-11-27
REFUSED — GE: the SPY input check failed. Exit 3.
```


**No verdict yet: the first run refused at gate GE, as designed.** Nothing ships. The SPY file
fetched before the 2026-11-27 session ends on 2026-11-25. The registration requires data through
the registration date, so no return was computed. The graded run is owed after the 2026-11-27
close: rerun with `--refresh` after 16:30 New York time that day.
