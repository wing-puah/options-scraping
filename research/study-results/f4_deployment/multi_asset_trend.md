# multi_asset_trend — per-era record

**Question.** Does a monthly time-series momentum rule (12-month return above T-bills, Moskowitz, Ooi and Pedersen 2012; Faber 2007's long-or-T-bills form) run on nine ETFs at once beat equal-weight buy-and-hold of the same nine after 5 bp costs, on the Sharpe ratio and the maximum drawdown (discovery 2007-2016 sign check, holdout 2017-01 to 2026-08 decides)?

Append-only. One section per (export era, git sha); newest last. The excerpts are quoted verbatim from the study's own report — see [README.md](../README.md) for why this folder exists.


## era v4 · inputs e7318a6 · sha 558da68 — recorded 2026-11-27
<!-- key era=v4 sha=558da68 inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-27 19:39:06 · git 558da68 (main, working tree dirty) · exit 0 · 46.2s
command     python -m scripts.backtest_study.f4_deployment.multi_asset_trend
excerpt     verdict

```
VERDICT
>>> multi_asset_trend HEADLINE (TB-12-EW vs EW-9, holdout 2017-01 to 2026-08, 5 bp): PBO-VETO <<<
>>> multi_asset_trend DISCOVERY (2007-03 to 2016-12): dSharpe +0.154 [-0.396, +0.619] dMDD +0.231 [-0.009, +0.408] dCAGR -0.76 points alpha +0.019 be…
>>> multi_asset_trend HOLDOUT (2017-01 to 2026-08): dSharpe +0.187 [-0.165, +0.491] dMDD +0.131 [+0.021, +0.235] dCAGR -2.04 points alpha +0.022 beta…
>>> multi_asset_trend PBO (12 cells, S=16, in-sample): 0.746 <<<
>>> multi_asset_trend OPTIONS ARM (descriptive, not graded): 36/191 trades priced <<<
>>> multi_asset_trend FORWARD (TB-12-EW vs EW-9 from 2026-12, 36-month minimum): STILL-OPEN (0 forward months of 36) <<<
  A statistic counts when its holdout CI lower bound is above 0 and its discovery point estimate is above 0.
  Nothing ships from this study (multi_asset_trend.md).
```


## Note 2026-11-27 · first run, era named

**`PBO-VETO`: the trend portfolio's shallower drawdown counts, but the 12-cell grid looks overfit, so no gain is claimed.** Nothing ships.

The machine header says era v4 because the runner names the book's era. This study reads no book. Its era is `current (inputs are unversioned market closes)`: nine yfinance ETF series and `^IRX`, cut at 2026-09-22. The first common decision is 2007-02-28, set by DBC.

The two window lines in full, verbatim from `backtests/study_output/multi_asset_trend-latest.txt`:

```
>>> multi_asset_trend DISCOVERY (2007-03 to 2016-12): dSharpe +0.154 [-0.396, +0.619] dMDD +0.231 [-0.009, +0.408] dCAGR -0.76 points alpha +0.019 beta 0.45 <<<
>>> multi_asset_trend HOLDOUT (2017-01 to 2026-08): dSharpe +0.187 [-0.165, +0.491] dMDD +0.131 [+0.021, +0.235] dCAGR -2.04 points alpha +0.022 beta 0.45 <<<
```

| Object | Window | dSharpe | CI | dMDD | CI |
|---|---|---|---|---|---|
| `TB-12-EW` vs `EW-9` | Discovery, 118 months | +0.154 | [−0.396, +0.619] | +0.231 | [−0.009, +0.408] |
| `TB-12-EW` vs `EW-9` | Holdout, 116 months | +0.187 | [−0.165, +0.491] | +0.131 | [+0.021, +0.235] |

- **Drawdown counts.** The holdout `dMDD` interval clears zero and the discovery point estimate is positive.
- **Sharpe does not count.** Its holdout interval straddles zero.
- **Without the veto the word would be `DRAWDOWN-ONLY`.** The in-sample PBO is 0.746, above the 0.50 veto line.
- **The cost of the shallower drawdown.** The trend cell earned about 2 points a year less than `EW-9` in the holdout, at a beta of 0.45.
- **Every printed-only sensitivity also gives `PBO-VETO`.** That holds for both other block lengths and both other costs.
- **The options arm prices 36 of 191 wanted trades.** From the first cached SPY expiry, it prices 22 of 41. It grades nothing.

## Note 2026-11-27 · build rulings and smoke runs disclosed

Two gate refusals came before the graded run. Each had a cause that was not an outcome.

- **GI refused** on a 7-session `^IRX` carry in March 2020. The reader had dropped `^IRX` quotes at or below zero, which are real closes. This was a code bug, fixed by keeping those quotes.
- **GB refused** on DBC's 2024-12-23 year-end distribution, a +5.34% `Adj Close / Close` jump. The registration settles a GB refusal by a build ruling. The ruling passes a jump above 5% only when yfinance's dividend feed implies the same jump within 0.1 points.

Both rulings sit beside their rules in the [registration](../../pre-registrations/f4_deployment/multi_asset_trend.md).

One smoke run at 50 bootstrap draws followed the GB ruling and came before the graded run. It found two code defects. The buy-and-hold SPY benchmark printed no time in market in the holdout. One options trade with the same strike on both legs was priced as a vertical. Both were fixed. No gate, cell, bar, seed or verdict rule changed after the smoke run, and the graded run is the one recorded above.

## era v4 · inputs e7318a6 · sha 0c46dfd — recorded 2026-11-28
<!-- key era=v4 sha=0c46dfd inputs=e7318a6 -->

population  1,211 results · 2,289 proxy · 3,826 analysis · 878 spy_vix_daily_full · 704 BaselineDaily  (inputs dated 2026-11-26 12:31 … 2026-11-27 16:53)
run         2026-11-28 01:01:32 · git 0c46dfd (main, working tree clean) · exit 0 · 5.8s
command     python -m scripts.backtest_study.f4_deployment.multi_asset_trend
excerpt     verdict

```
VERDICT
>>> multi_asset_trend HEADLINE (TB-12-EW vs EW-9, holdout 2017-01 to 2026-08, 5 bp): PBO-VETO <<<
>>> multi_asset_trend DISCOVERY (2007-03 to 2016-12): dSharpe +0.154 [-0.396, +0.619] dMDD +0.231 [-0.009, +0.408] dCAGR -0.76 points alpha +0.019 be…
>>> multi_asset_trend HOLDOUT (2017-01 to 2026-08): dSharpe +0.187 [-0.165, +0.491] dMDD +0.131 [+0.021, +0.235] dCAGR -2.04 points alpha +0.022 beta…
>>> multi_asset_trend PBO (12 cells, S=16, in-sample): 0.746 <<<
>>> multi_asset_trend OPTIONS ARM (descriptive, not graded): 36/191 trades priced <<<
>>> multi_asset_trend FORWARD (TB-12-EW vs EW-9 from 2026-12, 36-month minimum): STILL-OPEN (0 forward months of 36) <<<
  A statistic counts when its holdout CI lower bound is above 0 and its discovery point estimate is above 0.
  Nothing ships from this study (multi_asset_trend.md).
```

