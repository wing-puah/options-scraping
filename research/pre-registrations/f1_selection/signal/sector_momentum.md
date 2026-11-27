## sector_momentum — does holding the three strongest SPDR sectors beat holding all nine?

<!-- outcome:start -->
> Latest outcome: `>>> sector_momentum HEADLINE (12-1-T3 vs EW-9, pooled 2000-01 to 2026-08, 5 bp): UNDERPOWERED-BY-DESIGN (could not see one: delta80 above REF) <<<` (`XS +0.19% [-2.20%, +2.62%] p 0.8676`). The test could not see one: `delta80 0.0450 vs REF 0.030`; it never means no effect. Halves `-0.75%` and `+1.08%`; GK passed at block 6; PBO `0.656`; forward `STILL-OPEN` — window POOLED 2000-01 to 2026-08, yfinance closes to 2026-11-25, run 2026-11-28 on a dirty tree (descriptive until a clean rerun) · [record](../../../study-results/f1_selection/signal/sector_momentum.md)
<!-- outcome:end -->

_Registered 2026-11-28._

**STATUS: REGISTERED · ACCEPTED BY DEFAULT, NOT YET RUN**, on the drafter's recommended defaults
(the operator's standing rule of 2026-10-09). The operator set the design commitments on
2026-11-28. The drafter filled each gap with a conservative conventional choice, tagged
`Resolved at draft (2026-11-28)` beside its rule. No sector return, rank, holding, turnover or
difference for any cell or benchmark was computed or looked at before this file was written. A
fresh second reader checked it on 2026-11-28, before its first outcome
([README](../../README.md#the-second-reader-before-every-new-registration-freezes)). Its changes
are tagged `Resolved at second read (2026-11-28)`.

## The question

Among the nine original SPDR sector ETFs, does holding the three with the strongest past return,
rebalanced monthly, earn more than holding all nine in equal weight? The whole graded window,
2000-01 to 2026-08, decides the verdict. Each half must agree in sign.

**Why it matters here.** The operator is moving to a fully mechanical options book. That book needs
a rule for which underlying to hold. Every earlier mechanical rule tested direction or exposure:
`trend_overlay`, `multi_asset_trend`, `vol_managed_spy` and `spy_dip_forward`. This one tests
selection.

**Why holding less cannot win it.** Both arms hold 100% in sector ETFs at all times, with no cash.
So a gain cannot come from lower exposure, which is how both trend studies cut their drawdowns
([current.md](../../../current.md#drawdown-tests-on-the-two-trend-studies-holding-less-passes-them)).

The published claim, and why the prior is weak:

- Jegadeesh, N. and Titman, S. (1993), "Returns to Buying Winners and Selling Losers: Implications
  for Stock Market Efficiency", *Journal of Finance* 48(1). Stocks with high returns over the past
  3 to 12 months kept outperforming over the next months. The usual form skips the most recent
  month, which tends to reverse for single stocks.
- Moskowitz, T. J. and Grinblatt, M. (1999), "Do Industries Explain Momentum?", *Journal of
  Finance* 54(4). Industry portfolios show strong momentum, and it accounts for much of the stock
  effect. Unlike single stocks, industries also show it at the one-month horizon.
- McLean, R. D. and Pontiff, J. (2016), "Does Academic Research Destroy Stock Return
  Predictability?", *Journal of Finance* 71(1). Across 97 published predictors, portfolio returns
  were 26% lower out of sample and 58% lower after publication.
- Daniel, K. and Moskowitz, T. J. (2016), "Momentum Crashes", *Journal of Financial Economics*
  122(2). Momentum suffers rare, severe losses in rebounds after market falls, when past losers
  rally hardest.

So the prior is a published, widely known effect, tested here only after publication, on nine
broad ETFs, net of costs. The drafter expects it to be weak.

What each headline word would mean:

| Word | Meaning |
|---|---|
| `BEATS-EW` | The top-three rule earned more than `EW-9` over the graded window, with the sign agreeing in both halves |
| `PBO-VETO` | A gain was shown, but the 12-cell grid looks overfit, so it is not claimed |
| `CONTRARY` | The rule earned clearly less than `EW-9` over the graded window |
| `UNDERPOWERED-BY-DESIGN` | No gain or loss was shown, and the test could not have seen an effect of the reference size |
| `NULL` | No gain or loss was shown, on a test that could have seen the reference effect |
| `UNDERPOWERED` | Too few months to judge. Nothing is concluded |
| `REFUSED (gate)` | A gate failed. Nothing is computed past it |

No word changes a rule in production.

## What this study is not

- **Not an option study.** It holds ETF shares. It says nothing about options on these ETFs.
- **Not after tax.** Monthly rotation realises gains, and this study charges nothing for it.
- **Not single names.** It ranks sector funds, not the stocks inside them.
- **Not the eleven-sector set.** XLRE (2015) and XLC (2018) are left out for short history. Their
  sectors sit inside XLF and XLK/XLY for part of the window, so the nine are not today's map.
- **Not market timing.** Both arms are always fully invested. It cannot say when to hold stocks.
- **Not long-short.** The published spreads buy winners and sell losers. This rule only buys.
- **Not a drawdown test.** Drawdowns print. None is graded (see How it is judged).
- **Not whole shares.** Weights are fractional. At about $13,000, one third is about $4,300 per
  ETF, so rounding is small but real.
- **Not a parameter search.** Twelve cells are fixed below, and one is graded. The other eleven
  exist so PBO can measure how fragile the choice is.
- **Not a book study.** It reads no play, flow signal, backtest row or option quote.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Design lessons applied

Each choice below answers a defect found on 2026-11-27 or 2026-11-28.

| Defect found | Where | Choice here |
|---|---|---|
| Holding less passes a drawdown-difference test | [current.md](../../../current.md#drawdown-tests-on-the-two-trend-studies-holding-less-passes-them), next-steps item 21 | Both arms fully invested; no drawdown graded |
| A drawdown test with few episodes cannot pass even a perfect effect | `vol_managed_spy` post-run review | Drawdowns print only; the graded statistic is a monthly mean |
| PBO ranked Sharpe while drawdown was the counted statistic | `multi_asset_trend` post-run review | PBO ranks cells by the graded statistic, mean monthly excess |
| The bootstrap rejected 7.5% of no-effect draws at a nominal 5% | `spy_dip_forward` post-run review | Gate GK measures the test's size on null panels and refuses above 7.5% |
| "16 of 16 years positive" was read as support; the null rate was 69% | `spy_dip_forward` post-run review | The per-year table prints its null base rate beside it and grades nothing |
| `NULL` meant "could not see one", not "no effect" | `vol_managed_spy` post-run review | Power printed before grading; token `UNDERPOWERED-BY-DESIGN` |
| A run's figures could change on rerun because the last session was open | `calendar_drift` gate GE ruling | Graded months fixed by calendar; GE needs sessions past every graded month |
| The dividend-feed check was circular on yfinance data | `multi_asset_trend` `Resolved after review` | Gate GB adds a peer-relative return check that the feed cannot satisfy |
| The benchmark was called buy-and-hold but rebalanced | `multi_asset_trend` post-run review | `EW-9` is named "rebalanced equal weight"; a test pins the rebalance |
| A stored report ran on a dirty tree with a header placeholder | `multi_asset_trend` post-run review | Only a clean-tree run with a complete header is the run of record |
| A gain rested on one row or one year | `selection_order` O3, `spy_put_write` | The share of the gain left after removing the best sector-month prints |
| A gain may be beta, not selection | `spy_dip_forward` VOL-SCALED, `spy_put_write` ARM H | Beta and alpha against `EW-9` and SPY print beside the verdict |
| Closes after 2026-09-22 were seen in the bear peek | sibling studies, [holdout seal](../../f4_deployment/holdout_seal.md) | The same in-sample cut |
| Off-clock option marks and cache growth moved verdicts | next-steps items 22 and 24 | No option quote is read; each input file's dates and hash print |
| A discovery and holdout split halved the months, though nothing was fitted on discovery | this file's second read | One pooled graded window; each half is a sign check |

## Definitions

### Universe and price series

| Series | Source | Use |
|---|---|---|
| XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY | yfinance `Adj Close` and `Close`, from each ETF's first session | Ranks and returns use `Adj Close`, so returns are total returns. `Close` feeds gate GB only |
| SPY | yfinance `Adj Close` | The session calendar, and the printed beta and alpha against SPY |
| `^IRX` | yfinance close | T-bill cash, for excess returns and Sharpe ratios |

- **All nine listed in 1998-12.** The module finds the first session common to all nine from the
  data and prints it.
- **Cache.** The module writes `backtests/sector_momentum/<TICKER>.csv` (date, close, adj_close)
  for the nine, SPY and `IRX`. `--refresh` also writes `<TICKER>_dividends.csv` for the nine.
- **Fetch only with `--refresh`.** Without the flag the module reads the cache, and a missing file
  refuses (exit 3). The runner takes the flag directly:
  `python3 -m scripts.backtest_study run sector_momentum --refresh`, with no `--` before it.
- **Today's bar.** As in `calendar_drift`, a bar dated on the fetch day is kept only after 16:30
  New York time. yfinance's `end` is exclusive.
- `Resolved at draft (2026-11-28)`: `backtests/trend_overlay/IRX.csv` exists. When it does, gate GI
  checks this study's `^IRX` copy against it. This module never writes it.

### Calendar

- **Sessions.** The SPY session dates.
- **Month-end.** A session is a month-end when the next session falls in a later month. The last
  row of a series is never a month-end, so a cut series never invents a decision.
- **`M_0`, `M_−k`.** At a decision, `M_0` is that month-end close. `M_−k` is the month-end close
  `k` calendar months earlier.
- **Monthly return.** The compounded daily return of a curve over the sessions of one calendar
  month. Every graded statistic uses monthly returns.
- **Complete month.** A calendar month whose sessions are all in the data and whose last session is
  followed by a session in a later month.

### Cash

- **Daily T-bill return** on session `k` = `^IRX` close of session `k − 1` / 100 / 252.
- **Zero and negative quotes are data.** A finite close at or below zero is used as printed. It is
  never dropped, carried or floored.
- **A session with no `^IRX` close** carries the last close forward. A carry of more than 5
  sessions refuses (gate GI).
- Cash is never held by either arm. The T-bill return only defines excess returns.

### The rule

- **Decision.** At each month-end close `M_0`, rank the nine by formation return. The formation
  return of the headline is `Adj Close(M_−1) / Adj Close(M_−12) − 1`. That is 11 monthly returns,
  skipping the month from `M_−1` to `M_0`.
- **Holdings.** The top `K` ETFs, each at weight `1/K`.
- **Ties.** Formation returns equal within 1e-12 rank by ticker in alphabetical order, earlier
  first. `Resolved at draft (2026-11-28)`.
- **Execution.** Both arms trade to their target weights at the close of the next session,
  `M_0 + 1`. The return from close `M_0 + 1` to the next close is the first one earned on the new
  holdings. The return into close `M_0 + 1` is earned on the old holdings.
- **Between executions** weights drift with prices. No trade is made.
- **Every execution trades to target**, even when the names do not change. No band, no floor.
- **Cost.** 5 basis points per side on traded notional, charged at the execution close. Traded
  notional is the sum over the nine of `|target weight − drifted weight|` × equity.
  `Resolved at second read (2026-11-28)`: traded notional uses equity before cost. The cost is
  then deducted, and the target weights apply to the equity after cost. Both arms use this order,
  and gate GR checks that they match.
- **Start.** Every curve starts at 1.0 at the first execution close, at its target weights, with
  no entry cost.

### The benchmark, `EW-9`

- **Rebalanced equal weight.** 1/9 in each of the nine, traded back to 1/9 at every execution
  close, at the same 5 bp on its own turnover.
- It is not buy-and-hold. A test pins the rebalance.
- It is computed by a separate function with no ranking logic, so gate GR is a real replay check.

### The 12 cells, fixed here

| Factor | Values |
|---|---|
| Formation | `12-1`: `M_−12` to `M_−1`, 11 monthly returns. `6-1`: `M_−6` to `M_−1`, 5. `3-1`: `M_−3` to `M_−1`, 2. `12-0`: `M_−12` to `M_0`, 12, no skip |
| Number held `K` | 2, 3 or 4 |

- **Cell labels** read formation, then `T` and `K`: `12-1-T3`, `6-1-T2`, `12-0-T4`, and so on.
- **The headline cell is `12-1-T3`.** It is the only graded cell.
- `Resolved at draft (2026-11-28)`, why `3-1` is the fourth formation. It makes a clean 4 × 3 grid.
  It also covers the short horizon at which Moskowitz and Grinblatt found industry momentum, while
  keeping the skip month. `12-0` tests the skip itself.

### Windows

| Window | Months | Role |
|---|---|---|
| Graded | First graded month to 2026-08 | Decides the verdict |
| Early half | First graded month to 2012-12 | Sign check |
| Late half | 2013-01 to 2026-08 | Sign check |
| Gap | 2026-09 to 2026-11 | In no window |
| Forward | 2026-12 to 2029-11 | One-shot forward read |

- **The first decision** is the first month-end at which all 12 cells are defined. The 12-month
  formations set it, so it is expected at 1999-12-31. The expected first graded month is 2000-01.
  The module finds both from the data and prints them.
- **The first month is short by one session.** It runs from the first execution close to the
  month's last close. Both arms are treated alike.
- **Each window stands alone.** Its statistics and bootstrap read only its own months. The
  simulation itself runs once, without a restart.
- **The in-sample cut.** Every series is cut at 2026-09-22 (`IN_SAMPLE_END`) before anything is
  computed. So 2026-08 is the last complete month, as in `trend_overlay`, `multi_asset_trend` and
  `vol_managed_spy`.
- `Resolved at second read (2026-11-28)`: **later fetches cannot move an in-sample figure.** A
  dividend paid after the cut rescales every earlier `Adj Close` by one constant factor. Returns,
  ranks and every graded figure are unchanged by that, up to floating-point rounding.
- **Post-publication.** Moskowitz and Grinblatt were published in 1999. Every graded month is
  after it, so the whole study measures the effect after publication. No separate split prints.

`Resolved at second read (2026-11-28)`: **one pooled graded window, not a discovery and a
holdout.** The draft graded 2013-01 to 2026-08 alone and used 2000 to 2012 as a sign check.

- Nothing is fitted on the early half. The headline cell, the grid and every parameter come from
  the papers and are fixed in this file. So the split bought no guard against overfitting.
- It did halve the months. Pooling about 320 months instead of 164 cuts the standard error of
  `XS` by about 28%.
- Neither half is blind: the drafter knows the rough sector history of both. So the late half was
  no cleaner a test than the early one.
- The halves stay as sign checks. A gain that lives in one era alone does not count.
- This was decided before any return was computed.

### Metrics, fixed here

| Metric | Definition |
|---|---|
| Monthly excess `d_m` | Rule's monthly return minus `EW-9`'s, both net of their own costs |
| `XS` | `12 ×` the mean of `d_m` over a window's months. The headline statistic |
| `IR` | `√12 ×` mean / sample standard deviation of `d_m`. Printed, not graded |
| Sharpe | `√12 ×` mean / sample standard deviation of monthly excess returns over T-bills |
| Max drawdown | The largest fall of compounded monthly equity from its running peak. Printed, not graded |
| CAGR | Compounded monthly equity, `E_end^(12 / months) − 1` |
| Turnover | Traded notional over pre-cost equity, summed over the window, times 12 / months |
| Beta and alpha | OLS of the rule's monthly excess over T-bills on the benchmark's; alpha × 12; Newey–West errors, 12 lags. Against `EW-9` and against SPY. Printed |
| Hit rate | Share of months with `d_m` above 0. Printed, with its null base rate |
| Best sector-month removed | See below. Printed |

**Best sector-month removed.** For each sector `i` and graded month `m`, both arms are recomputed
with sector `i`'s daily returns in month `m` replaced by `EW-9`'s daily returns in that month. The
best sector-month is the one whose replacement lowers graded-window `XS` most. Ranks are
recomputed after the replacement. The report prints `XS` after that replacement and, when
graded-window `XS` is above 0, its share of the original.

`Resolved at build (2026-11-28)`: in the first graded month, the execution session comes before
the curves start, so `EW-9` has no return there. The sector keeps its own return for that one
session. `EW-9`'s daily returns are its curve's, net of its own cost.

## Dependencies

- yfinance, with `--refresh`, for the nine ETFs, SPY, `^IRX` and the nine dividend feeds.
- `backtests/trend_overlay/IRX.csv`, read only, for gate GI's cross-check.
- `scripts/backtest_study/lib/path_bootstrap.py::_resample_indices`, the moving circular block
  resampler, imported unchanged.
- `scripts/backtest_study/lib/pbo.py::cscv`, with the metric defined in the module.
- `scripts/backtest_study/lib/era.py::SEAL_START`, printed in the header.

## Population and basis, fixed here

- **Module.** `scripts/backtest_study/f1_selection/signal/sector_momentum.py`. Tests in
  `tests/test_sector_momentum.py`.
- **Era.** The inputs carry no prompt version. A run asked for any era but `current` refuses
  (exit 2).
- **Header declarations** ([architecture](../../../../docs/architecture.md), study runner):
  - `HEADER_ERA = "current (inputs are unversioned market closes)"`;
  - `HEADER_INPUTS = ["backtests/sector_momentum/*.csv"]`;
  - no `HEADER_CACHE`, because no option cache is read.
- **Report header, from the module.** The windows with their actual first and last months, the
  first decision, the git sha and dirty flag. For each input file: its first and last date, row
  count and the first 12 characters of its sha256.
- **Run of record.** A run on a clean tree whose header has no placeholder. A dirty-tree run is
  descriptive only.
- **The seal.** It binds signal dates of emitted plays. This study reads none, so it does not bind.

## Plan-time observations, disclosed

Every check below was made on 2026-11-28, before this file was written.

### Inputs

- **This study's cache.** `backtests/sector_momentum/` does not exist. No series was fetched.
- **`backtests/trend_overlay/`.** A file listing shows `GSPC.csv`, `IRX.csv` and `SPY.csv`. None
  was opened for this file.
- **Sector tickers elsewhere.** A count-only search found 10 lines naming a sector ticker across
  four files in `research/`. They concern option plays. The drafter did not read them.

### What the drafter already knows

- **The sibling studies' printed outcomes**, read in `research/current.md`. `multi_asset_trend`
  prints `PBO-VETO`. `vol_managed_spy` prints `NULL`. `spy_dip_forward` prints P `SUPPORTED`. The
  post-run reviews of all three were read. None holds a sector return, and none set a number here.
- **Public market history.** The drafter knows in rough terms which sectors led. Technology led
  much of the late half. Energy had deep falls and one strong late run. Financials
  fell hardest in 2008. So neither window is blind in rough direction. No figure was computed.
- **No search for published backtests.** Sector rotation on these ETFs is a popular retail rule.
  The drafter did not search for its published results, to avoid reading outcomes on this data.

### Known limits, stated now

- **Nine assets.** The papers sort many more portfolios. With nine, the top three differ from the
  average by less, so the spread is smaller and noisier.
- **Sector concentration.** XLK's weight in the S&P 500 grew through the late half. A rule that held
  XLK often would gain from that one trend. The best-sector-month line and the betas show it; they
  cannot remove it.
- **The momentum crash** of 2009 falls in the early half. A long-only rule against an
  equal-weight benchmark has less crash exposure than a long-short spread.
- **Few independent observations.** About 320 graded months with a 6-month block is about 53
  blocks. Each half holds about 27.

### A prior, not evidence

The arithmetic is generic and unmeasured. It assumes the top-three portfolio tracks `EW-9` with
an error of 6% to 9% a year. The 80%-power effect is about 2.8 standard errors.

| Window | Years | Standard error of `XS`, at 9% | 80%-power effect, at 9% | 80%-power effect, at 6% |
|---|---|---|---|---|
| Late half alone (the draft's holdout) | 13.7 | 2.4% | 6.8% | 4.5% |
| Pooled (graded here) | 26.7 | 1.7% | 4.9% | 3.3% |

- The draft expected `UNDERPOWERED-BY-DESIGN` from the first row.
- On the pooled window it stays the likely word, but it is not certain. `Resolved at second read
  (2026-11-28)`.

Gate GK replaces this guess with a simulation before grading.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `12-1-T3` | arm | Top three by 12-1 return, equal weight | Headline, graded on the pooled window |
| The other 11 cells | cell | The rest of the 4 × 3 grid | PBO only; their `XS` prints, not graded |
| `EW-9` | control | All nine, rebalanced to equal weight monthly | The graded comparison |
| `SPY` | control | SPY held | Printed, not graded |
| `NULL-PANELS` | control | Simulated panels with no predictability | Gate GK: size, base rates, power |
| `G-MEANS` | descriptive cut | `G-MONTH` with each ETF's real mean kept | Printed only: the `XS` that persistent mean differences alone would give |
| Sensitivities | descriptive cut | Cost 0 and 15 bp; block 3 and 12 months | Printed only |
| `FORWARD` | population scope | `12-1-T3` against `EW-9`, 2026-12 to 2029-11 | One-shot forward read |

## How it is judged

### One test, no multiplicity

One statistic decides: graded-window `XS` of `12-1-T3` against `EW-9`. `IR` prints with its interval but
is not graded, because its test is nearly the same test. So there is one test, and no Holm step
applies. `Resolved at draft (2026-11-28)`.

### Bootstrap

- **Paired moving block bootstrap on monthly returns.** Each draw resamples one window's months
  with `path_bootstrap._resample_indices`. The rule's and `EW-9`'s returns of a month travel
  together, so each draw resamples the `d_m` series. The rule is not re-run on the draw.
- **Block 6 months**, 5,000 draws, seed 20261128. Each window uses the same seed.
- `Resolved at draft (2026-11-28)`: a 6-month block, not the siblings' 12. Those graded drawdowns,
  which need long blocks. A mean of a difference series needs less, and more blocks keep the
  interval nearer its nominal size. Gate GK checks the size at this block.
- **CI.** The 2.5th and 97.5th percentiles of the draws.
- **p-value.** Two-sided: twice the smaller of the share of draws at or below 0 and the share at
  or above 0, capped at 1.
- `Resolved at second read (2026-11-28)`: p below 0.05 is the same event as a 95% interval clear
  of zero, up to percentile interpolation. Where the two disagree, the p decides. An interval
  touching zero never counts.

### When the rule counts as better or worse

- **Counts** when all four hold:
  - graded-window p below 0.05;
  - graded-window `XS` above 0;
  - early-half `XS` above 0;
  - late-half `XS` above 0.
- The halves are sign checks only. Their CIs print and do not gate.
- **Clearly worse** when graded-window p is below 0.05 and graded-window `XS` is below 0. No half
  clause.

### Pre-run calibration, gate GK

Before any real-data statistic is computed or printed, the module runs its own test on simulated
panels with no cross-sectional predictability. The same functions run the rule, `EW-9` and the
bootstrap as on the real data.

- **Generators**, each 500 paths, seed 20261128. Each path has the real panel's number of months.
  Every window keeps its real month count.
  - **G-IID.** Daily return vectors drawn iid multivariate normal. Covariance: the real panel's
    sample covariance of daily returns. Mean: one common daily mean `μ̄`, the average of the
    nine ETFs' means in the real panel.
  - **G-GARCH.** `r_t = μ̄ + s_t L z_t`. `L` is the Cholesky factor of the same covariance. `z_t` is
    iid Student-t with 5 degrees of freedom, scaled to unit variance. `s_t` is a GJR-GARCH(1,1)
    scale with unit mean variance. Its parameters are fixed here: α 0.02, γ 0.12, β 0.90. The
    shock `u_t` that drives it is the mean of `z_t`, scaled to unit variance.
  - **G-MONTH.** The real daily panel, each ETF demeaned to `μ̄`. Whole calendar months, all nine
    together, are drawn iid with replacement and joined. This keeps fat tails, correlation and
    within-month clustering, and removes persistence across months.
- `Resolved at second read (2026-11-28)`: **what "the real panel" is.** The daily returns of the
  nine from the first common session through 2026-08-31. Covariances and means come from these
  sessions. `G-MONTH` draws from the complete calendar months among them. A simulated path keeps
  the warm-up months before the first decision, so its first graded month matches the real one.
  `G-IID` and `G-GARCH` use the real session count of each month.
- **Why these remove the effect.** Every ETF has the same mean, and no ETF's expected return
  depends on the past. `G-GARCH` carries volatility forward, but not the mean. So past ranks
  predict nothing. At 0 bp the true `XS` is exactly 0 under
  `G-IID` and `G-GARCH`.
- `Resolved at second read (2026-11-28)`: **`G-MONTH` is zero only to second order.** Demeaning
  equalises daily means, but drawing whole months weights months, not days. Compounding inside a
  month also differs slightly by ETF. The report prints the mean `XS` over `G-MONTH` paths at 0 bp
  beside its rate.
- `Resolved at draft (2026-11-28)`: the covariance and means come from the real panel at run time.
  They are properties of single ETFs, not of the rule.
- `Resolved at second read (2026-11-28)`: **persistent mean differences versus momentum.** Real
  sectors have different means, and a 12-1 rank partly picks the high-mean ones.
  - The size gate keeps one common mean. Only then is the true `XS` known to be 0, so the
    rejection rate measures the test's size.
  - A null that kept each ETF's real mean would hand the rule a true gain. Its rejection rate
    would then be power, not size.
  - The verdict counts any gain over `EW-9`, from momentum or from persistent mean differences.
    The study does not separate them.
  - `G-MEANS`, printed only, shows the split. It is `G-MONTH` without the demeaning, 500 paths,
    the same seed. Its mean `XS` at 5 bp prints beside the real `XS`. It grades nothing.
- **Gate quantity.** The two-sided rejection rate on the graded window at 0 bp: the share of paths
  with graded-window p below 0.05. Nominal 0.05.
- **The bound.** GK refuses when that rate exceeds **0.075** (1.5 × nominal) for any generator. The
  report prints the rate for all three either way.
- **Monte Carlo error.** With 500 paths, a true 5% rate has a standard error near 1 point. The
  bound is about 2.6 standard errors above nominal. A correctly sized test then refuses at one
  generator under 1% of the time, and at any of three under 2.5%. A true 9% rate refuses about
  88% of the time.
- **A refusal** prints no real-data statistic. `Resolved at second read (2026-11-28)`: the one
  fallback is fixed here. GK re-runs with a 12-month block for every window and for `δ80`. If it
  still refuses, the verdict is `REFUSED (gate)`. No other fix is allowed.

**Also printed from the same paths, at 5 bp, per generator:**

- the share of paths where the rule counts (the false-positive rate of `BEATS-EW`);
- the share where it is clearly worse (the false-positive rate of `CONTRARY`, which includes the
  extra cost of the rule's turnover);
- the null share of graded-window calendar years with `d_m` summed above 0, and the null hit rate;
- the share of forward-length windows (36 months) with `XS` above 0;
  `Resolved at build (2026-11-28)`: every rolling 36-month window inside the graded window,
  pooled over paths;
- the rejection rate of each half alone, at 0 bp.

The real per-year table and hit rate print beside these null rates. They grade nothing.

### Power, and the reference effect

- **The reference effect `REF` = 3.0% a year.** It is a planning value fixed here, not a figure
  quoted from a paper. The drafter has no verified published number for top three of nine against
  equal weight, and did not search for one. `Resolved at draft (2026-11-28)`.
- **Why 3%.** The published long-short industry spreads were several percent a year. Top three
  against the average is about half of a top-minus-bottom spread. McLean and Pontiff's decay
  roughly halves it again after publication. 3% is generous after both cuts.
- `Resolved at second read (2026-11-28)`: **3% is generous, and fixed.** The papers' extremes
  are the top and bottom few of 20 or more industries. Top three of nine is a milder tilt, so the
  same decay leaves nearer 1% to 1.5% a year. 3% stays the planning value. A larger `REF` makes
  `NULL` easier to earn, so a `NULL` here rules out 3% a year, not 1%.
- **`δ80`.** For each generator, every null path's `d_m` at 5 bp is shifted by `δ / 12` in every
  window. The bootstrap draws shift by the same amount, so no rerun is needed. The pass rate is
  the share of paths where the rule counts.
- `Resolved at second read (2026-11-28)`: δ is added to the 5 bp null, which already carries the
  rule's extra trading cost. So δ and `REF` are gains before that extra cost. The extra cost is a
  few tenths of a point a year.
- **The δ grid.** 0.25% to 15.00% a year in 0.25-point steps. A generator's `δ80` is the smallest
  grid value with a pass rate of at least 0.80. If none reaches it, `δ80` prints as "above 15%".
- **The study's `δ80`** is the largest of the three generators' values.
- **The power rule.** When no gain and no loss is shown and `δ80` is above `REF`, the word is
  `UNDERPOWERED-BY-DESIGN`, not `NULL`. It means "could not see an effect of the reference size",
  never "no effect". `δ80` equal to `REF` is not above it.
- **A `BEATS-EW` with `δ80` above `REF`** keeps its word. The report adds "low power: the estimate
  is likely inflated" beside it.
- `Resolved at second read (2026-11-28)`: **why the power rule cannot be gamed.** `δ80` comes from
  simulated paths only, under parameters fixed here, before any real statistic is computed. `REF`
  is fixed here. The real `XS` never enters either.

**What the study can and cannot detect, stated before the run.** `Resolved at second read
(2026-11-28)`. By the rough arithmetic above, it can detect a gain of about 3.3% to 5% a year with
80% power. It cannot detect the 1% to 1.5% a year that a decayed published effect suggests.
`NULL` or `UNDERPOWERED-BY-DESIGN` never means "no effect". The printed `δ80` is the smallest gain
this test would usually have seen.

### Drawdown: printed, not graded

Each arm's maximum drawdown prints per window, with the difference. No drawdown test is graded,
for two reasons:

- **Few episodes.** Each window holds a handful of market falls. In `vol_managed_spy` a planted
  perfect effect on 3 episodes could not reach the bar.
- **What passes it.** The 2026-11-28 check found that holding less passes such tests. Both arms
  here are fully invested, so that bias is gone, but the floor is not.

### PBO / CSCV

- **Rows.** The monthly `d_m` of the 12 cells, each against `EW-9`, over the graded window. The
  partial month 2026-09 is not a row. `Resolved at second read (2026-11-28)`.
- **Columns.** The 12 cells. **S = 16.**
- **Trim, not pad.** The oldest months are dropped until 16 divides the row count. The dropped
  months print.
- **Metric.** The column mean of the rows given: the graded statistic, `XS`, up to the factor 12.
  `report_metric` is the same. It is passed to `pbo.cscv` as `metric=lambda rows: rows.mean(axis=0)`
  on a T × 12 array.
- **The bar.** Above **0.50** is a veto. Above 0.25 and at most 0.50 prints "selection fragile".
- **The noise baseline.** With 12 cells, an in-sample best cell that lands at random out of sample
  gives a PBO near 0.50.
- **What it never does.** It never selects a cell. The headline was fixed before any run.
- A PBO that is not finite refuses, as `REFUSED (PBO undefined)`.

### Everything printed beside the headline

For each window, for every cell, `EW-9` and SPY: `XS`, `IR` with CI, Sharpe, CAGR, max drawdown
(monthly and daily), turnover, hit rate, worst calendar year. For the headline cell: betas and
alphas against `EW-9` and SPY, the best sector-month line, the per-year table, and the share of
months each ETF was held.

## Gates

The gates run in this order. GK runs after every data gate and before any real-data statistic.

- **GE, dates.** Any failure refuses (exit 3).
  - Each of the 11 cache files starts on or before the first session common to the nine.
  - Each has a session with a finite adjusted close after 2026-09-22. So the 2026-09-22 row is
    never a file's last row, and every graded month is complete.
  - Rows after 2026-09-22 are never read into any graded or printed in-sample statistic. GC
    tests this.
  - A partial final bar is harmless. The today's-bar rule drops a bar dated on the fetch day
    before 16:30 New York time. Any other last row lies after the cut, which drops it.
  - `Resolved at second read (2026-11-28)`: the draft also required each file's last session to
    fall after 2026-11-28, following `calendar_drift`. That clause is removed. In `calendar_drift`
    the final session is an open event inside a graded set. Here every graded month ends by
    2026-08-31, and no rule reads a file's last session. A run today and a run next week print the
    same in-sample figures. Only the header's file dates, row counts and hashes differ. The
    forward line reads `STILL-OPEN` with 0 complete months in both.
  - A forward read needs a session after 2029-11-30 (see Forward).
- `Resolved at second read (2026-11-28)`: **GI and GB check only the rows a statistic reads.** In
  an in-sample run that is every row through 2026-09-22. When the forward read fires, they also
  check every row through the first session after 2029-11-30. A bad row outside these ranges never
  refuses.
- **GI, integrity.** Any failure refuses (exit 3) and prints the rows.
  - No duplicate dates in any file.
  - Every SPY session from the first common session to the cut has a close and adjusted close for
    all nine. No ETF has a session SPY lacks. No ETF close is carried.
  - No close or adjusted close is empty, zero or negative.
  - No `^IRX` carry exceeds 5 sessions. Every finite `^IRX` close at or below zero is used; the count
    used equals the count in the file.
  - When `backtests/trend_overlay/IRX.csv` exists, the two `^IRX` files agree within 0.01 points on
    every common date through 2026-09-22.
- **GB, basis.** Any failure refuses (exit 3) and prints the rows.
  - The `Adj Close / Close` ratio never falls by more than 0.01% between sessions.
  - A rise of up to 3% passes as an ordinary dividend.
  - A rise above 3% refuses unless the dividend feed lists a cash distribution on that ex-date
    whose implied rise, `close_prev / (close_prev − D) − 1`, matches within 0.1 points.
  - A row that passes the feed match then takes a peer check. The ETF's adjusted return that
    session should lie within 3 points of the median adjusted return of the other eight.
  - The peer check is not circular. A fake distribution would lift the adjusted return by the
    same rise, away from the ETF's peers. The report prints every row passed by the feed match.
  - `Resolved at second read (2026-11-28)`: **a failed peer check flags; it does not refuse.** A
    sector can truly move 4% against its peers in one session, as energy did in 2020. On an
    ex-date, a hard refusal could then block true data. Instead, for each flagged row, the headline is recomputed with
    that row's ratio rise removed, as if the distribution were fake. Both words print. When any
    flagged row changes the headline word, the verdict is `REFUSED (gate)`, with the row named.
  - No daily adjusted return exceeds ±35%. `Resolved at draft (2026-11-28)`: sector ETFs moved more
    than SPY in 2008 and 2020. A missing split shows as a far larger move.
  - A refusal is settled by a `Resolved at build` ruling, never by loosening a bound silently.
- **GX, no lookahead.**
  - The holdings behind session `k`'s return read no close after the latest month-end at or before
    `k − 2`.
  - The `12-1` rank reads `Adj Close` at `M_−12` and `M_−1` only.
  - The test file changes every later close and requires identical holdings.
  - Each run recomputes the ranks of 24 evenly spaced decisions from series cut at that decision
    close, with the decision date given. It stops on any difference.
  - The test also checks that the last row of a cut series is never a month-end.
- **GC, the cut.** The in-sample report is identical when every close after 2026-09-22 is changed.
- **GR, replay.** The rule's code run with `K = 9` must reproduce `EW-9`'s monthly returns, to a
  largest difference of 1e-12. A mismatch refuses (exit 3). Without GR, a gap could come from the
  simulator, not the rank.
- **GK, calibration.** As above. It refuses when the 0 bp rejection rate exceeds 0.075 for any
  generator.
- **GN, floors.** The study is `UNDERPOWERED` when the graded window has fewer than **240**
  complete months, or either half fewer than **120**. The calendar gives about 320, 156 and 164, so
  these are backstops. `Resolved at second read (2026-11-28)`, for the pooled design.

### Mechanics tests the build must include

Each test must fail under the one-step mutation named. The test's docstring names the mutation,
and the builder records that it was seen to fail with that mutation applied.

| Test | Pins | Fails under |
|---|---|---|
| Decision keys | Every key of the decision table is the first session after a month-end | Keying on the month-end itself |
| Formation window | A return only in the month before `M_−12` does not move the rank; one in the month after does | Window start one month early or late |
| Skip month | A return only in the month ending `M_0` does not move the `12-1` rank, and does move `12-0` | Dropping the skip |
| Headline sign | On a panel where the next month's top three earn a planted +1% a month over the rest, `XS` is positive and near the planted value | Computing `EW-9` minus rule |
| Pairing | Holdings decided at `M_0` earn returns from close `M_0 + 1`; the return into `M_0 + 1` accrues to the old holdings | Shifting holdings one session or one month |
| Rebalance | After one ETF doubles, `EW-9` is back at 1/9 each after the next execution, and pays cost on that trade | Letting `EW-9` drift |
| Cost | Cost equals 5 bp × traded notional; zero when weights are already at target | Charging one side only |
| Ties | Equal formation returns take the alphabetical order | Reversing the tie-break |
| PBO metric | The metric passed to `cscv` is the column mean of `d_m` | Passing a Sharpe metric |
| GK refusal | A bootstrap with a deliberately narrow interval refuses; the real one passes on a small null set | Removing the bound check |
| GB peer check | A planted fake distribution, listed in the feed with no fall in `Close`, is flagged; when it changes the headline word, the run refuses | Dropping the peer check |
| GE dates | A synthetic file whose last session is 2026-09-22 refuses; one ending 2026-09-23 passes | Comparing with "on or after" |
| Cut | Changing every row after 2026-09-22, including a partial last bar, leaves the in-sample report unchanged | Reading the uncut series |
| Negative `^IRX` | A file with zero and negative closes uses them as printed | Dropping non-positive rows |

## Verdicts, worded now

### Headline, `12-1-T3` against `EW-9` at 5 bp

The first matching row wins.

1. **`REFUSED (gate)`.** GE, GI, GB, GX, GC, GR or GK failed, a GB-flagged row changes the word,
   PBO is undefined, or the era is not `current`. Nothing else prints in the verdict section.
2. **`UNDERPOWERED`.** A window is below its GN floor.
3. **`PBO-VETO`.** The rule counts, and the in-sample PBO is above 0.50.
4. **`BEATS-EW`.** The rule counts.
5. **`CONTRARY`.** The rule is clearly worse.
6. **`UNDERPOWERED-BY-DESIGN`.** `δ80` is above `REF`.
7. **`NULL`.** Every other case.

Each case meets exactly one first match, and `NULL` takes the rest. Cases checked while drafting:

- Graded-window p below 0.05 and `XS` above 0, one half's `XS` at or below 0: not counted, not
  worse. The word is row 6 or 7, with "pooled gain, <half> sign disagrees" beside it.
- Graded-window `XS` of zero: p is near 1, so it is not counted and not worse.
- Clearly worse with `δ80` above `REF`: row 5 comes first. A loss that was seen is reported.
- Counts with PBO above 0.50 and `δ80` above `REF`: row 3.
- GK refuses and a window is below its floor: row 1.
- p exactly 0.05: not below 0.05, so neither counts nor clearly worse.

Beside the word, always: graded-window `XS` with CI and p, `IR` with CI, each half's `XS` with CI,
both drawdowns, the betas and alphas, the best-sector-month line, the `G-MEANS` mean `XS`, and
`δ80` against `REF`. None changes the word.

- **Grid cells** print the word they would get by the same rows, marked "grid, not graded". They
  use the headline's PBO and `δ80`. `Resolved at second read (2026-11-28)`.
- **Sensitivities** print the headline word they would give, marked "printed only". A cost
  sensitivity re-runs every cell and `EW-9` at that cost and recomputes PBO and GK's power at it. A
  block sensitivity re-runs GK at that block and keeps the 5 bp PBO.

### Forward

- **The months are fixed:** 2026-12 to 2029-11, exactly 36. A later run grades these months and no
  others, so the read never depends on the run date.
- **The run continues** through the gap without a restart. Gap months grade nothing.
- **Fires once**, on the first run whose cache holds a session after 2029-11-30. Until then the
  forward line prints `STILL-OPEN` with a count of complete forward months.
- **Sunset, 2030-11-30.** If no run has fired the read by then, it closes as `LAPSED`, and nothing
  is concluded.
- **Words at the read**, on the point estimate:
  - `FORWARD-AGREES`: forward `XS` above 0;
  - `FORWARD-AGAINST`: forward `XS` at or below 0.
- **Why a point estimate.** 36 months is six 6-month blocks. No interval at that size means much,
  so the read checks for decay; it is not a second test. The block-6 CI prints beside it, with the
  null share of 36-month windows above 0 from GK.
- **Verdict of record.** The first forward run that prints a word other than `STILL-OPEN`.

### The banner

The report's section titled VERDICT prints:

```
>>> sector_momentum HEADLINE (12-1-T3 vs EW-9, pooled <first> to 2026-08, 5 bp): <word> <<<
>>> sector_momentum POOLED (<first> to 2026-08): XS <x> [<lo>, <hi>] p <p> IR <x> [<lo>, <hi>] <<<
>>> sector_momentum HALVES (sign checks): <first> to 2012-12 XS <x> [<lo>, <hi>]; 2013-01 to 2026-08 XS <x> [<lo>, <hi>] <<<
>>> sector_momentum CALIBRATION (0 bp size, block <blk>, bound 0.075): G-IID <a> G-GARCH <b> G-MONTH <c> <<<
>>> sector_momentum POWER (delta80 <d> vs REF 0.030; BEATS-EW false-positive <f>) <<<
>>> sector_momentum PBO (12 cells, S=16, metric mean d_m, in-sample): <value> <<<
>>> sector_momentum FORWARD (12-1-T3 vs EW-9, 2026-12 to 2029-11, sunset 2030-11-30): <word> <<<
```

`<first>` is the first graded month. `<blk>` is 6, or 12 after GK's one fallback. `<f>` is the
largest of the three generators' rates.

## Anti-tuning

- **Fixed here, the universe.** The nine ETFs, the adjusted-close basis and the SPY calendar.
- **Fixed here, the rule.** The 12 cells, the headline `12-1-T3`, the month-end decision, the
  next-session execution, the tie-break, and `EW-9` as the comparison.
- **Fixed here, the money.** 5 bp per side on both arms' turnover, and the two cost sensitivities.
- **Fixed here, the judging.** The pooled window and the 2012-12 split of its halves, the one
  graded statistic, the bootstrap's block, draws and seed, and the floors.
- **Fixed here, the calibration.** The three generators and their parameters, `G-MEANS`, the path
  count, the bound, the one fallback block, `REF` and the δ grid.
- **Fixed here, the words.** The PBO bar, the forward months, the sunset, and the verdict words.
- No other ETF, formation, `K`, weighting, cost, block or window is graded.
- No parameter is set or changed on real returns. GK is settled on simulated output only.
- A grid cell, a sensitivity, a benchmark, a drawdown or the per-year table never re-grades the
  headline.
- PBO never selects a cell.
- The in-sample run reads no close after 2026-09-22. No later run moves that date or the forward
  months.

## What could ship

Nothing ships from this study.

- `BEATS-EW` files "sector momentum: in-sample gain, to be tested forward" in
  [`deployment-evidence.md`](../../../deployment-evidence.md). It earns the forward read and a note
  for the design of a mechanical baseline's underlying choice. No live rule changes.
- Any live selection rule needs its own registration and an operator decision.
- A `FORWARD-AGAINST` read after `BEATS-EW` files the gain as decayed.
- `UNDERPOWERED-BY-DESIGN` files nothing. It records that nine ETFs over this window cannot answer
  the question at the reference size.
- No word here supports an option structure on these ETFs, a tax claim, or a single-name rule.
- No word here changes a tier, a veto, a size class, an exit, the deploy card or the hedge sleeve
  in [§4](../../../../docs/deployment-rules.md#s4).
