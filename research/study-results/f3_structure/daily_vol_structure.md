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


## Graded by `study_review` — 2026-11-18

Two analysts and a validator graded the 2026-11-18 report (v4, sha 847d0ef). They agree on every verdict row.

- **Verdict:** nothing passes. All 144 cells are `NULL`, discovery ranks no cell (smallest q 0.953), and 19 of 20 unconditional sides are `NULL`.
- **The one `CONTRARY`:** the back leg of the QQQ 30-day put ratio, −0.065% a day [−0.105%, −0.024%]. It says the long leg loses, not that selling it pays.
- **Not evaluable from the report:** the OHLC-end and `Price~` coverage sub-gates, arm-level exit drops, PBO (no ranked cell) and the forward grade (no `CANDIDATE`).
- **One open framing point:** analyst A graded the LIVE power floor as a gate (not met); analyst B graded only the LIVE read (not evaluable). The 36 LIVE cells are `UNDERPOWERED` either way.
- **A label, not a rule breach:** 25 QQQ 30-day trades drop as `no_listed_strike`. The monthly is walked as the registration says; the label means the walk found no listed strike in its window, not that the expiry was skipped.
- **Hand reconciliation (2026-11-18):** 9 sampled trades, 3 per structure across both tickers and tenors, match the trades file to 1e-9. Six were credit entries and four exited on the junk-quote `Latest` rule.

## era v4 · inputs 2f45ae6 · sha 436c8f7 — recorded 2026-11-26
<!-- key era=v4 sha=436c8f7 inputs=2f45ae6 -->

population  1,214 results · 2,286 proxy · 3,826 analysis · 878 spy_vix_daily_full · 703 BaselineDaily  (inputs dated 2026-11-26 11:38 … 2026-11-26 14:01)
run         2026-11-26 15:25:10 · git 436c8f7 (main, working tree clean) · exit 0 · 76.4s
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

