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

