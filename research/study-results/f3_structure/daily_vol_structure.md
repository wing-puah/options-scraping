# daily_vol_structure — per-era record

**Question.** Do a daily straddle and 1x2 ratios on QQQ and SMH pay net of commission, and do their results move with volume or price?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs c4c967e · sha 847d0ef — recorded 2026-11-18
<!-- key era=v4 sha=847d0ef inputs=c4c967e -->

population  1,053 results · 2,223 proxy · 3,546 analysis · 871 spy_vix_daily_full  (inputs dated 2026-10-21 14:48 … 2026-11-16 18:23)
run         2026-11-18 10:37:55 · git 847d0ef (main, working tree clean) · exit 0 · 132.5s
command     python -m scripts.backtest_study.f3_structure.daily_vol_structure
excerpt     verdict

```
VERDICT
  Pays every day: none
  Moves with a known feature: none
  LIVE read, its own forward test: none
  cells (144): CANDIDATE 0  CONTRARY 0  NULL 144  UNDERPOWERED 0
  unconditional (20 sides): CANDIDATE 0  CONTRARY 1  NULL 19  UNDERPOWERED 0
  analysis cells (108): RETRO-ONLY, not tallied
>>> daily_vol_structure UNCONDITIONAL QQQ T30 S long: NULL <<<
>>> daily_vol_structure UNCONDITIONAL QQQ T30 RC back: NULL <<<
>>> daily_vol_structure UNCONDITIONAL QQQ T30 RC front: NULL <<<
>>> daily_vol_structure UNCONDITIONAL QQQ T30 RP back: CONTRARY <<<
>>> daily_vol_structure UNCONDITIONAL QQQ T30 RP front: NULL <<<
>>> daily_vol_structure UNCONDITIONAL QQQ T7 S long: NULL <<<
>>> daily_vol_structure UNCONDITIONAL QQQ T7 RC back: NULL <<<
>>> daily_vol_structure UNCONDITIONAL QQQ T7 RC front: NULL <<<
>>> daily_vol_structure UNCONDITIONAL QQQ T7 RP back: NULL <<<
>>> daily_vol_structure UNCONDITIONAL QQQ T7 RP front: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T30 S long: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T30 RC back: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T30 RC front: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T30 RP back: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T30 RP front: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T7 S long: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T7 RC back: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T7 RC front: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T7 RP back: NULL <<<
>>> daily_vol_structure UNCONDITIONAL SMH T7 RP front: NULL <<<
  FORWARD  no CANDIDATE, so nothing to grade
  Nothing ships from this study. A CANDIDATE earns only a forward grade.
  trades -> backtests/study_output/daily_vol_structure-trades.csv
```

