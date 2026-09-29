# ladder_overlay — per-era record

**Question.** Does selling a shorter-dated short call against a long-dated bull call spread — and rolling that short call as each one expires — beat simply running the spread to the shipped §5 exits, and would a naked put beat both?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs b462dfe · sha 8aed569 — recorded 2026-09-10
<!-- key era=v4 sha=8aed569 inputs=b462dfe -->

population  598 results · 1,665 proxy · 2,677 analysis · 823 spy_vix_daily_full  (inputs dated 2026-09-08 22:38 … 2026-09-10 11:32)
run         2026-09-10 22:17:35 · git 8aed569 (main, working tree dirty) · exit 0 · 210.1s
command     python -m scripts.backtest_study.f3_structure.ladder_overlay
excerpt     matched

```
  >= 8 shared dates required; fewer means E3 is NOT EVALUABLE and the cell
```


## era v3 · inputs e5140f3 · sha 2d72047 — recorded 2026-09-16
<!-- key era=v3 sha=2d72047 inputs=e5140f3 -->

population  406 results · 796 proxy · 1,607 analysis · 827 spy_vix_daily_full  (inputs dated 2026-08-15 19:03 … 2026-09-16 11:32)
run         2026-09-16 23:11:29 · git 2d72047 (main, working tree dirty) · exit 0 · 254.5s
command     python -m scripts.backtest_study.f3_structure.ladder_overlay
excerpt     matched

```
  >= 8 shared dates required; fewer means E3 is NOT EVALUABLE and the cell
```


## era v4 · inputs 271c4b5 · sha 6d8dfc6 — recorded 2026-09-19
<!-- key era=v4 sha=6d8dfc6 inputs=271c4b5 -->

population  598 results · 1,665 proxy · 2,781 analysis · 827 spy_vix_daily_full  (inputs dated 2026-09-16 11:32 … 2026-09-19 16:45)
run         2026-09-19 17:08:08 · git 6d8dfc6 (main, working tree dirty) · exit 0 · 354.5s
command     python -m scripts.backtest_study.f3_structure.ladder_overlay
excerpt     matched

```
  >= 8 shared dates required; fewer means E3 is NOT EVALUABLE and the cell
```


## era v4 · inputs 271c4b5 · sha 8e9b6a7 — recorded 2026-09-20
<!-- key era=v4 sha=8e9b6a7 inputs=271c4b5 -->

population  598 results · 1,665 proxy · 2,781 analysis · 827 spy_vix_daily_full  (inputs dated 2026-09-16 11:32 … 2026-09-19 16:45)
run         2026-09-19 23:44:37 · git 8e9b6a7 (main, working tree clean) · exit 0 · 347.1s
command     python -m scripts.backtest_study.f3_structure.ladder_overlay
excerpt     matched

```
  >= 8 shared dates required; fewer means E3 is NOT EVALUABLE and the cell
```


## era v4 · inputs 7373cdb · sha de5a6f3 — recorded 2026-09-28
<!-- key era=v4 sha=de5a6f3 inputs=7373cdb -->

population  1,012 results · 2,029 proxy · 3,346 analysis · 835 spy_vix_daily_full  (inputs dated 2026-09-27 15:57 … 2026-09-28 12:45)
run         2026-09-28 13:27:56 · git de5a6f3 (main, working tree dirty) · exit 0 · 2627.5s
command     python -m scripts.backtest_study.f3_structure.ladder_overlay
excerpt     verdict

```
VERDICTS
  L-BASE          NULL
  L-F4            NULL
  L-T0            NULL
  L-GAP           NULL
  L-RUN           NULL
  L-T0-TEF        NULL
  L-GAP-TEF       NULL
  L-RUN-TEF       NULL
  N-CORE          NULL
  N-ROLL          NULL
  CANDIDATE is not a ship. Nothing ships from a research-tier study, and a
  RE-WRAP or BREACH-DOMINATED cell closes its own thread for these dates.
per-row per-cell results: 2837 rows -> backtests/study_output/ladder_overlay-rows.csv
```

