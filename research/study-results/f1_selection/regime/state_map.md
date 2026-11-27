# state_map — per-era record

**Question.** Which market states (VIX level and shape, price trend, realised vol, credit) come before SPY falls of 8% or more since 1993, and once the mechanical BEAR or E-VOL state prints, does SPY keep falling or is the move already over?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../../README.md) for why this folder exists.


## era v4 · inputs e028cbc · sha 744433f — recorded 2026-11-21
<!-- key era=v4 sha=744433f inputs=e028cbc -->

population  1,178 results · 2,273 proxy · 3,782 analysis · 873 spy_vix_daily_full  (inputs dated 2026-11-21 12:09 … 2026-11-21 13:06)
run         2026-11-21 16:11:19 · git 744433f (main, working tree dirty) · exit 0 · 7.3s
command     python -m scripts.backtest_study.f1_selection.regime.state_map
excerpt     verdict

```
VERDICT
  >>> state_map Q2 READ (state variables before E-DD8 onsets, 10-session lead, test 2016-01-01 to 2026-09-22): COINCIDENT <<<
  >>> state_map Q2 CANDIDATES (Holm m=9): C1 COINCIDENT C2 COINCIDENT C3 COINCIDENT C4 COINCIDENT C5 NO-FORECAST C6 NO-FORECAST C7 NO-FORECAST C8 NO-…
  >>> state_map Q3 READ (B10: SPY 10 sessions after a mech BEAR onset vs other days, test 2016-01-01 to 2026-09-22): NULL <<<
  >>> state_map Q3 CELLS (Holm m=6): B5 NULL B10 NULL B21 NULL V5 NULL V10 NULL V21 NULL <<<
  >>> state_map PBO: Q2 0.395 Q3 0.603 <<<
  >>> state_map Q4 (SPY put spread on Q3 signals, 2022 on): AWAITING SCRAPE <<<
  >>> state_map FORWARD (episodes and onsets after 2026-11-20): Q2 STILL-OPEN Q3 STILL-OPEN <<<
  LEADS needs the lead lift's CI above 0, a Holm p below 0.05, a positive discovery lift and PBO <= 0.50.
  Nothing ships from this study (state_map.md).
```

## Note 2026-11-21 (later) · re-run `state_map-v4-20261121b.txt`

The verdict banner above is unchanged after a printing-only re-run. The report now prints the coincident Holm p (m = 6) and the raw p for C5 to C7, a discovery census that reconciles 19 episodes to the lift n, and a labelled post-hoc all-sessions TURN-ON table (not registered, descriptive only). Reading: [current.md](../../../current.md#2026-11-21--state_map-no-market-state-warned-before-a-top).

## Note 2026-11-21 (later) · re-run `state_map-v4-20261121c.txt`

Q4 priced after the fetch. Every other verdict line is unchanged from `-b`; only the Q4 line moved, from `AWAITING SCRAPE` to `DESCRIPTIVE`. `fetch_state_map_legs.py` fetched 12 SPY puts (none unlisted, none refused). All 39 onsets priced.

```
  >>> state_map Q4 (SPY put spread on Q3 signals, 2022 on): DESCRIPTIVE <<<
```

Reading: [current.md](../../../current.md#2026-11-21--state_map-no-market-state-warned-before-a-top).

## Note 2026-11-21 (later) · re-graded on `state_map-v4-20261121c.txt`

`study_review` re-graded the report that carries Q4 and the post-hoc table. Both analysts and the validator agree with every printed verdict. The `COINCIDENT` words and the Q4 `DESCRIPTIVE` line grade MET. The post-hoc table was not graded.

Still open after the re-grade:

- The graders split on three gate rows (GB, GX, GC) and on the label of the Q3 READ row.
- The registered per-trade Q4 table is not printed.
- "selection fragile" prints on the PBO line only, not in the banner.

The run's own record block was appended and then lost to a concurrent revert the same day. This note stands in for it. The first-run review files are kept in `backtests/study_output/` with a `-first-run-20261121` suffix.

## era v4 · inputs 2f45ae6 · sha 436c8f7 — recorded 2026-11-26
<!-- key era=v4 sha=436c8f7 inputs=2f45ae6 -->

population  1,214 results · 2,286 proxy · 3,826 analysis · 878 spy_vix_daily_full · 703 BaselineDaily  (inputs dated 2026-11-26 11:38 … 2026-11-26 14:01)
run         2026-11-26 15:10:10 · git 436c8f7 (main, working tree clean) · exit 0 · 7.1s
command     python -m scripts.backtest_study.f1_selection.regime.state_map
excerpt     verdict

```
VERDICT
  >>> state_map Q2 READ (state variables before E-DD8 onsets, 10-session lead, test 2016-01-01 to 2026-09-22): COINCIDENT <<<
  >>> state_map Q2 CANDIDATES (Holm m=9): C1 COINCIDENT C2 COINCIDENT C3 COINCIDENT C4 COINCIDENT C5 NO-FORECAST C6 NO-FORECAST C7 NO-FORECAST C8 NO-…
  >>> state_map Q3 READ (B10: SPY 10 sessions after a mech BEAR onset vs other days, test 2016-01-01 to 2026-09-22): NULL <<<
  >>> state_map Q3 CELLS (Holm m=6): B5 NULL B10 NULL B21 NULL V5 NULL V10 NULL V21 NULL <<<
  >>> state_map PBO: Q2 0.395 Q3 0.603 <<<
  >>> state_map Q4 (SPY put spread on Q3 signals, 2022 on): DESCRIPTIVE <<<
  >>> state_map FORWARD (episodes and onsets after 2026-11-20): Q2 STILL-OPEN Q3 STILL-OPEN <<<
  LEADS needs the lead lift's CI above 0, a Holm p below 0.05, a positive discovery lift and PBO <= 0.50.
  Nothing ships from this study (state_map.md).
```


## era v4 · inputs e7318a6 · sha f04686e — recorded 2026-11-27
<!-- key era=v4 sha=f04686e inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 12:12)
run         2026-11-27 14:20:30 · git f04686e (main, working tree clean) · exit 0 · 8.3s
command     python -m scripts.backtest_study.f1_selection.regime.state_map
excerpt     verdict

```
VERDICT
  >>> state_map Q2 READ (state variables before E-DD8 onsets, 10-session lead, test 2016-01-01 to 2026-09-22): COINCIDENT <<<
  >>> state_map Q2 CANDIDATES (Holm m=9): C1 COINCIDENT C2 COINCIDENT C3 COINCIDENT C4 COINCIDENT C5 NO-FORECAST C6 NO-FORECAST C7 NO-FORECAST C8 NO-…
  >>> state_map Q3 READ (B10: SPY 10 sessions after a mech BEAR onset vs other days, test 2016-01-01 to 2026-09-22): NULL <<<
  >>> state_map Q3 CELLS (Holm m=6): B5 NULL B10 NULL B21 NULL V5 NULL V10 NULL V21 NULL <<<
  >>> state_map PBO: Q2 0.395 Q3 0.603 <<<
  >>> state_map Q4 (SPY put spread on Q3 signals, 2022 on): DESCRIPTIVE <<<
  >>> state_map FORWARD (episodes and onsets after 2026-11-20): Q2 STILL-OPEN Q3 STILL-OPEN <<<
  LEADS needs the lead lift's CI above 0, a Holm p below 0.05, a positive discovery lift and PBO <= 0.50.
  Nothing ships from this study (state_map.md).
```

