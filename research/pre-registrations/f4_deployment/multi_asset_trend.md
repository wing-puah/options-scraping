## multi_asset_trend — does monthly trend across nine ETFs beat holding all nine?

<!-- outcome:start -->
> Latest outcome: `>>> multi_asset_trend HEADLINE (TB-12-EW vs EW-9, holdout 2017-01 to 2026-08, 5 bp): PBO-VETO <<<` — `dMDD` counts (holdout `+0.131 [+0.021, +0.235]`, discovery `+0.231`), `dSharpe` does not (holdout `+0.187 [-0.165, +0.491]`), and the in-sample PBO is `0.746`; options arm `36/191 trades priced`; forward `STILL-OPEN (0 forward months of 36)` — era current (yfinance closes to 2026-09-22), run 2026-11-27 · [record](../../study-results/f4_deployment/multi_asset_trend.md)
<!-- outcome:end -->

_Registered 2026-11-27._

**STATUS: REGISTERED, NOT YET RUN.** The operator approved the design on 2026-11-27. The drafter
filled the gaps the design left with the most conservative conventional choice, each tagged
`Resolved at draft (2026-11-27)` beside its rule. No return, Sharpe ratio, drawdown, turnover or
coverage figure for any rule, cell or benchmark below was computed before this file was written.
A fresh second reader is owed before the first run and before the commit
([README](../README.md#the-second-reader-before-every-new-registration-freezes)).

## The question

Does a monthly time-series momentum rule, run on nine ETFs at once, beat equal-weight
buy-and-hold of the same nine ETFs after costs? "Beat" is graded on two statistics: the Sharpe
ratio and the maximum drawdown. The holdout decides the verdict.

The published claim:

- Moskowitz, T., Ooi, Y. H. and Pedersen, L. H. (2012), "Time Series Momentum", *Journal of
  Financial Economics* 104(2). An asset's own 12-month excess return predicts its next month's
  return, across equity indices, bonds, commodities and currencies. A diversified portfolio of
  these trend bets earned a positive return with low beta, and did best in extreme markets.
  Their portfolio goes long or short each futures contract and scales each bet by its own
  volatility.
- Faber, M. (2007), "A Quantitative Approach to Tactical Asset Allocation", *Journal of Wealth
  Management* 9(4). Five asset classes, each held only while above its 10-month moving average,
  checked once a month. The equal-weight timed portfolio kept about the return of holding all
  five, at a lower volatility and a much smaller drawdown.

[`trend_overlay`](trend_overlay.md) tested one asset, the S&P 500. This study tests the claim
across many asset classes, each switched to T-bills on its own trend. Diversity of assets is where
both papers found most of the benefit. The long-or-T-bills form is Faber's. It is not the
Moskowitz, Ooi and Pedersen portfolio, which also shorts and scales by volatility. This study does
neither, so it borrows their signal, not their portfolio.

What each headline word would mean:

| Word | Meaning |
|---|---|
| `BEATS-EW` | The trend portfolio had a higher Sharpe ratio and a shallower maximum drawdown than holding all nine |
| `DRAWDOWN-ONLY` | It had a shallower maximum drawdown; the Sharpe gain was not shown |
| `SHARPE-ONLY` | It had a higher Sharpe ratio; the drawdown gain was not shown |
| `PBO-VETO` | A gain was shown, but the 12-cell grid looks overfit, so it is not claimed |
| `CONTRARY` | No gain was shown, and the trend portfolio was clearly worse on at least one statistic |
| `NULL` | No gain and no loss was shown |
| `UNDERPOWERED` | Too few months or too few drawdowns to judge. Nothing is concluded |
| `REFUSED` | A gate failed. Nothing is computed past it |

No word changes a rule in production.

## What this study is not

- **Not a forecast test of one asset.** It grades a portfolio's Sharpe ratio and drawdown, not
  whether a trend flag predicts the next month's mean return of one ETF.
- **Not a parameter search.** Twelve cells are fixed below, and one is the headline. The other
  eleven exist only so PBO can measure how fragile the choice is.
- **Not an option study.** The options arm is descriptive and never enters a verdict.
- **Not a book study.** It reads no play, flow signal or backtest row.
- **Not leveraged and not short.** Each sleeve holds its ETF or T-bills, never a short position.
- **Not intraday.** Every signal and every return uses daily closes.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Universe and price series

| Series | Asset class | Source |
|---|---|---|
| SPY | US large-cap stocks | yfinance `Adj Close` |
| QQQ | US large-cap growth (Nasdaq-100) | yfinance `Adj Close` |
| IWM | US small-cap stocks | yfinance `Adj Close` |
| EFA | Developed ex-US stocks | yfinance `Adj Close` |
| EEM | Emerging-market stocks | yfinance `Adj Close` |
| TLT | US Treasuries, 20+ years | yfinance `Adj Close` |
| IEF | US Treasuries, 7–10 years | yfinance `Adj Close` |
| GLD | Gold | yfinance `Adj Close` |
| DBC | Broad commodities | yfinance `Adj Close` |
| `^IRX` | 13-week T-bill yield | `backtests/trend_overlay/IRX.csv`, read only |

- **Adjusted closes.** Every ETF signal and return uses the split- and dividend-adjusted close.
  So returns are total returns, and the moving-average rule also reads a dividend-adjusted series.
- **Unadjusted SPY close.** yfinance `Close`, used only to pick option strikes in the options arm.
- **Cache.** The module writes `backtests/multi_asset_trend/<TICKER>.csv` (date, close,
  adj_close). It fetches only with `--refresh`. Without the flag it reads the cache, and a
  missing file refuses (exit 3). yfinance's `end` is exclusive, so today's bar is never fetched.
- **The T-bill file.** `backtests/trend_overlay/IRX.csv` belongs to `trend_overlay`, and this
  module never writes it. `Resolved at draft (2026-11-27)`: forward months need `^IRX` closes
  past that file's last date. So `--refresh` also writes `backtests/multi_asset_trend/IRX.csv`.
  The module reads that copy when it exists, and gate GI checks the two copies agree.

### Calendar

- **Sessions.** The SPY session dates. Gate GI refuses if any other ETF lacks a close on a SPY
  session inside the window.
- **Month-end.** A session is a month-end when the next session falls in a later month. The last
  row of a series is never a decision close, so a cut series never invents a decision (as in
  `trend_overlay`).
- **Monthly return.** The compounded daily return of a curve over the sessions of one calendar
  month. Every graded statistic uses monthly returns.

### Cash

- **Daily T-bill return** on session `k` = `^IRX` close of session `k − 1` / 100 / 252. The yield
  is known before the session it pays for.
- **A session with no `^IRX` close** carries the last close forward. A carry of more than 5
  sessions refuses (gate GI).
- `Resolved at draft (2026-11-27)`: `^IRX` is quoted on a discount basis, not as a bond-equivalent
  yield. The error is a few basis points a year and falls on every curve that holds cash.
- `Resolved at build (2026-11-27)`: `^IRX` quoted at or below zero on 7 sessions from
  2020-03-19 to 2020-03-27. Those quotes are real closes and are used as printed, which gives a
  small negative daily T-bill return. They are not dropped and carried, since dropping them would
  manufacture a 7-session carry that gate GI refuses.

### The rule

Each of the nine sleeves is **IN** (holds its ETF) or **OUT** (holds T-bills) after each decision
close.

- **Decision.** At each month-end close `t`, every sleeve's state and weight are set from closes at
  or before `t`.
- **Execution.** The portfolio trades to the new weights at the close of the next session,
  `t + 1`. The return from close `t + 1` to close `t + 2` is the first one earned at the new
  weights.
- **Between executions** the weights drift with prices. No trade is made.
- **Cost.** 5 basis points per side on traded notional, charged at the execution close. Traded
  notional is the sum over sleeves of `|target weight − drifted weight|` × equity, the T-bill
  sleeve included.
- `Resolved at draft (2026-11-27)`: the T-bill sleeve is charged too, as if cash were held in a
  T-bill fund. This is the more conservative of the two usual conventions.
- **Ties.** A trend measure exactly equal to its reference is OUT.
- **Start.** Every curve starts at 1.0 at the first execution close, at its target weights, with
  no entry cost.

### The 12 cells, fixed here

Each cell is one lookback, one trend rule and one weighting.

| Factor | Values |
|---|---|
| Lookback `L` | 6, 10 or 12 months |
| Trend rule | `TB`: total return over `L` above T-bill return over the same span. `SMA`: price above its `L`-month moving average |
| Weights | `EW`: equal. `IV`: inverse 60-day volatility |

- **`TB-L`.** At month-end `t`, the sleeve is IN when the ETF's adjusted-close return from
  month-end `t − L` to `t` is above the compounded daily T-bill return over the same sessions.
  This is the Moskowitz, Ooi and Pedersen sign rule.
- **`SMA-L`.** At month-end `t`, the sleeve is IN when the adjusted month-end close is above the
  mean of the `L` month-end adjusted closes ending at `t`. This is Faber's rule.
- **`EW` weights.** Each sleeve gets 1/9 of equity.
- **`IV` weights.** Sleeve `i` gets `(1/σ_i) / Σ_j (1/σ_j)`, summed over all nine. `σ` is the
  sample standard deviation of the last 60 daily log returns of the adjusted close, ending at `t`.
  An OUT sleeve's weight goes to T-bills. There is no volatility target and no leverage.
- **Cell labels** read rule, lookback, weights: `TB-12-EW`, `SMA-6-IV`, and so on.
- **The headline cell is `TB-12-EW`.** It is the published sign rule at its published lookback,
  with the simplest weights. Only this cell is graded.

### Benchmarks

| Label | What it holds | Role |
|---|---|---|
| `EW-9` | 1/9 in each of the nine ETFs, rebalanced at every execution close, same 5 bp cost | The graded comparison |
| `SPY` | SPY alone, bought once and held | Printed, not graded |
| `60-40` | 60% SPY and 40% IEF, rebalanced at every execution close, same 5 bp cost | Printed, not graded |

### Windows

| Window | Months | Role |
|---|---|---|
| Discovery | First month after the first common decision, to 2016-12 | Sign check |
| Holdout | 2017-01 to 2026-08 | Decides the verdict |
| Gap | 2026-09 to 2026-11 | In no window |
| Forward | From 2026-12 | One-shot forward read |

- **The first common decision** is the first month-end at which all 12 cells are defined for all
  nine ETFs. `TB-12` needs a month-end close 12 months earlier, so DBC sets it. DBC listed in
  2006-02, so the expected first decision is 2007-02-28 and the expected first month 2007-03. The
  module finds the date from the data and prints it.
- **The first month is short by one session.** The curves start at the first execution close,
  so that month runs from it to the month's last close. Every cell and benchmark is treated alike.
  It is graded as discovery's first month and counts toward the GN month floor.
- **Each window stands alone.** A window's statistics, episodes and bootstrap read only that
  window's monthly returns. Its equity is rebased to 1.0 at the window's start, and the running
  peak for MDD starts at that 1.0. The simulation itself runs once, without a restart.
- **The in-sample cut.** Every series is cut at 2026-09-22 (`IN_SAMPLE_END`) before anything is
  computed. Only complete calendar months are graded, so the holdout ends with 2026-08.
- `Resolved at draft (2026-11-27)`: closes after 2026-09-22 were seen in the 2026-11-21 bear
  peek, and `trend_overlay` and the [holdout seal](holdout_seal.md) cut there too. The design
  said "2017-01 on" and named no end. This is the conservative end.
- **The forward run is continuous.** It runs the same simulation through the gap without a
  restart. Only months from 2026-12 are graded forward. 2026-11 is the registration month and is
  incomplete on 2026-11-27.

### Metrics, fixed here

| Metric | Definition |
|---|---|
| Sharpe | `√12 ×` mean / sample standard deviation of monthly excess returns over the monthly T-bill return |
| Max drawdown (`MDD`) | The largest fall of the compounded monthly equity from its running peak, as a fraction of that peak |
| CAGR | Compounded monthly equity, `E_end^(12 / months) − 1` |
| Turnover | One-way traded notional over equity, summed per year, averaged over years. `Resolved at build (2026-11-27)`: per execution, the cost's traded notional (all ten sleeves) over pre-cost equity, each trade counted once; summed over the window and scaled by 12 / months |
| Time in market | The mean, over executions, of the summed target weight in ETFs; also per sleeve |
| Worst calendar year | The lowest compounded calendar-year return; a partial year is labelled partial |
| Jensen alpha and beta | OLS of the cell's monthly excess return on `EW-9`'s; alpha × 12; Newey–West errors, 12 lags |
| Daily MDD | MDD on the daily equity curve, printed beside the monthly one |

- `ΔSharpe = Sharpe(cell) − Sharpe(EW-9)`. Positive favours the trend cell.
- `ΔMDD = MDD(EW-9) − MDD(cell)`. Positive means the trend cell's worst drawdown was shallower.
- `ΔCAGR = CAGR(cell) − CAGR(EW-9)`, in points a year. This is the CAGR cost.
- **Alpha and beta** split the edge. A positive `ΔSharpe` with a beta well below 1 and an alpha
  near zero is mostly lower exposure, not a residual edge. Both are printed, not graded.

### Drawdown episodes

- **An episode** is a fall of `EW-9`'s monthly equity of **10%** or more from its running peak.
- **Peak** is the month of the running high. **Trough** is the lowest month before recovery.
  **Recovery** is the first later month at or above the peak, or the window end. A new episode
  starts only after a recovery.
- **Per episode**, printed: dates, `EW-9`'s depth, the headline cell's deepest drawdown inside the
  episode, and the gap between them.
- `Resolved at draft (2026-11-27)`: 10% rather than `trend_overlay`'s 20%. A nine-asset
  portfolio half in bonds and real assets falls less than one stock index. A 20% line would leave
  the holdout with very few episodes by construction.

## Dependencies

- yfinance, for the nine ETFs and, with `--refresh`, `^IRX`.
- `backtests/trend_overlay/IRX.csv`, read only.
- `scripts/backtest_study/lib/path_bootstrap.py::_resample_indices`, the moving circular block
  resampler, imported unchanged.
- `scripts/backtest_study/lib/pbo.py::cscv`, with a Sharpe metric defined in the module.
- `scripts/backtest_study/lib/era.py::SEAL_START`, printed in the header.
- The options arm only: `scripts/backtest/simulate.py::entry_day_fill`, `_close_mid` and
  `_is_junk_quote`, the cached files in
  `backtests/option_history_cache/`, and `commission_per_contract` in `config/backtest.yml`, all
  read unchanged.

## Population and basis, fixed here

- **Era.** The inputs carry no prompt version. The report prints `era: current (inputs are
  unversioned market closes)`, as `trend_overlay` does. `Resolved at build (2026-11-27)`: a run
  asked for any other era refuses (exit 2), as `tail_breach` does, so a `--era v3` suite run
  never files these closes under a past era.
- **The seal.** The seal binds signal dates of emitted plays. This study reads no play, flow
  signal or backtest row, so the seal does not bind it. The options arm reads cached SPY quotes
  only, and only through 2026-09-22.
- **Report header.** Era, the windows with their actual first and last months, the git sha, the
  dirty flag, each input file with its first and last date, and the first common decision.

## Plan-time observations, disclosed

Every check below was made on 2026-11-27, before this file was written.

### Inputs

- **ETF data.** `backtests/multi_asset_trend/` does not exist yet. No ETF series was fetched or
  read.
- **T-bill file.** `backtests/trend_overlay/IRX.csv` starts 1960-01-04. Its first two rows were
  read to see the column layout.
- **SPY option cache.** A file-name listing found 16,397 SPY contract files. Their expiries run
  from 2022-02-25 to 2027-09-17. One file's header row and first data row were read for the column
  layout. No option return was computed.
- So the options arm can price trades only from about 2022 on, and its coverage over the full
  window will be low by construction.

### What the drafter already knows

- **Public market history.** The drafter knows the dates of the 2008 crisis, the 2020 crash and
  the 2022 fall in stocks and bonds together. Published trend-following indices are widely
  reported to have done well in 2008 and 2022 and to have lagged in the choppy years after 2009.
- **So neither window is blind** to the drafter in direction. No figure was computed on this
  data.
- **`trend_overlay`.** The drafter has seen that study's printed outcome on the S&P 500. SPY is
  one of the nine sleeves here. That outcome is not cited, and it set no number in this file.

### Known limits, stated now

- **One 2008.** ETF history starts in the 2000s, and DBC in 2006. The discovery window holds one
  global crisis, and it is the episode the published claim leans on most.
- **Published-rule decay.** Both rules were published before the holdout began. A rule that many
  funds trade may have lost some of its edge since. The holdout and the forward read measure the
  rule after publication, which is the honest test, but a null may be decay, not a false claim.
- **Adjusted closes embed dividends.** The SMA rule then reads a total-return series, not the
  price Faber used. Bond and stock ETFs with high yields trend up a little faster in this series.
- **Few independent observations.** About 116 holdout months, and the bootstrap block is 12
  months. That is roughly ten independent blocks. Only a large difference can clear zero.
- **One universe.** The nine ETFs were chosen before any run, but they are one choice among many.
  PBO covers the rule grid, not the universe.

### A prior, not evidence

The drafter expects `DRAWDOWN-ONLY` or `NULL`. A diversified benchmark already has a modest
drawdown, which leaves the trend rule less to cut than on one stock index. The drafter expects the
Sharpe interval to straddle zero with about ten blocks. The drafter also expects PBO near 0.5,
because the 12 cells are close variants of one idea.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `TB-12-EW` | arm | 12-month return above T-bills, equal weight | Headline, graded on the holdout |
| The other 11 cells | cell | The rest of the 3 × 2 × 2 grid | PBO only; their deltas print, not graded |
| `EW-9` | control | Equal-weight nine-ETF buy-and-hold | The graded comparison |
| `SPY` | control | SPY alone | Printed, not graded |
| `60-40` | control | 60% SPY, 40% IEF | Printed, not graded |
| Episodes | descriptive cut | Per `EW-9` drawdown, the headline cell's depth | Printed only |
| Sensitivities | descriptive cut | Cost 0 and 15 bp; bootstrap block 6 and 24 | Printed only |
| Options arm | descriptive cut | The SPY sleeve as a call vertical | Printed only, never in a verdict |
| `FORWARD` | population scope | `TB-12-EW` against `EW-9` from 2026-12 | One-shot forward read |

### The options arm

The question it describes: when the SPY sleeve is IN, what would a call vertical have done in its
place? It is printed so a later study can be designed on real quotes. It grades nothing.

- **When.** At every execution session where `TB-12-EW` holds the SPY sleeve IN, one vertical
  opens.
- **Expiry.** The standard monthly expiry (third Friday) with the calendar days to expiry nearest
  65 from the entry session. A tie takes the later expiry. Only expiries with cached files count.
  `Resolved at build (2026-11-27)`: "third Friday" is read strictly. A holiday-shifted Thursday
  expiry is not a candidate, and an expiry on or before the entry day cannot be opened.
- **Strikes.** The long call is the cached strike nearest the unadjusted SPY close on the entry
  day. The short call is the cached strike nearest 1.05 × that close. A tie takes the lower strike
  for the long call and the higher strike for the short call.
- **Entry price.** Each leg off its own entry-day closing quote, through production's
  `simulate.entry_day_fill`: the long call as a bought leg, the short call as a sold leg. A
  normal two-sided quote fills at its closing mid (`_close_mid`). A junk quote
  (`_is_junk_quote`) follows production: a sold leg fills at its bid, or 0 with no bid; a bought
  leg with a bid fills at its mid; a bought leg with no bid is refused. Debit = long fill − short
  fill.
- **Exit.** At the next execution session, whatever the trend, each leg at its closing mid on that
  day (`_close_mid`). If the sleeve is still IN, a new vertical opens at the same close.
- **Cost.** `commission_per_contract` from `config/backtest.yml` (0.65 today), per leg per
  contract, at entry and at exit, so 2.60 per vertical. No slippage, as `_cost_knobs` reads
  `slippage_frac_of_spread: 0`. Return on debit and P&L are net of commission.
- **Priced.** A trade is priced when `entry_day_fill` prices both legs on the entry day, the
  debit is above 0, and both legs have a two-sided, non-junk closing quote on the exit day.
  Otherwise it is unpriced. No strike, expiry, price, carried mark or `Latest` print is
  substituted, so every price sits on one closing clock.
  `Resolved at build (2026-11-27)`: when the two strike rules pick the same cached strike, the
  trade is not a vertical and is unpriced ("strikes coincide").
- **No fetch.** A contract with no cached file is unpriced. The arm never calls the network.
- **Cut.** No entry or exit after 2026-09-22. A vertical whose exit would fall after the cut is
  not wanted. It is left out of both coverage counts and printed as a count of open trades.
- **Printed.** Coverage as trades priced / trades wanted, over the full in-sample window and over
  months from the first cached SPY expiry. Per priced trade: return on debit and the SPY
  adjusted return over the same span. In total: mean return on debit, hit rate, and P&L per one
  vertical.
- **Cache bias.** The cache was filled for the book's plays, so the strikes and expiries on file
  are not a random sample. This is one more reason the arm grades nothing.
- `Resolved at draft (2026-11-27)`, by the second reader: the draft filled a junk sold leg at its mid. That
  departed from the standing entry rulings (2026-09-24 junk quote, 2026-10-23 one clock), which
  fill a junk sold leg at its bid. The entry now calls `entry_day_fill` unchanged. Production
  marks a junk exit-day quote at a `Latest` print or a carried mark, which share no clock with the
  other leg. So a junk exit quote leaves the trade unpriced instead.

## How it is judged

### Bootstrap

- **Paired moving block bootstrap on monthly returns.** Each draw resamples one window's months
  with `path_bootstrap._resample_indices`. The headline cell's return, `EW-9`'s return and the
  T-bill return of a month travel together. The rule is not re-run on the resampled path.
- **Block 12 months**, 5,000 draws, seed 20261127. Each window uses the same seed.
- **Per draw:** `ΔSharpe` and `ΔMDD` on the resampled months.
- **CI.** The 2.5th and 97.5th percentiles of the draws. The observed value prints beside it.
- **Sensitivities.** Blocks of 6 and 24 months, printed only.
- `Resolved at draft (2026-11-27)`: a 12-month block keeps a year of serial dependence, which the
  12-month lookback creates. It is also the shortest block that keeps most drawdowns whole.
- **What the `ΔMDD` interval means.** A resampled path re-orders the months that happened. A
  drawdown longer than one block is cut at block joins, and the circular wrap joins the window's
  last month to its first. So the interval measures the noise in one drawdown figure. It is not
  centred on the observed `ΔMDD`, and the verdict reads its 2.5th percentile, as in
  `trend_overlay`.

### When a statistic counts

A statistic (`ΔSharpe` or `ΔMDD`) **counts** as a benefit when both hold:

- its holdout CI lower bound is above 0;
- its discovery point estimate is above 0.

This is the bar `trend_overlay` registered: an interval that reaches zero shows no benefit. The
discovery clause makes the sign agree in both windows. The discovery CI prints but does not gate.

A statistic is **clearly worse** when its holdout CI upper bound is below 0.

### PBO / CSCV

- **Rows.** The monthly excess returns over T-bills of the 12 cells, over the whole in-sample
  window, discovery and holdout together.
- **Columns.** The 12 cells.
- **S = 16.**
- **Trim, not pad.** The oldest months are dropped until 16 divides the row count. The dropped
  months are printed. `Resolved at draft (2026-11-27)`: `pad_head` adds zero rows, and a zero
  excess month is not a true row for any cell here.
- **Metric.** The Sharpe ratio of the rows given: `√12 ×` mean / sample standard deviation. A zero
  standard deviation gives NaN, which `cscv` ranks worst.
- **The bar.** Above **0.50** is a veto: no gain is claimed. Above 0.25 and at most 0.50 prints
  "selection fragile". At most 0.25 prints nothing extra.
- **The noise baseline.** With 12 cells, an in-sample best cell that lands at random out of
  sample gives a PBO near 0.50. So close variants of one idea sit near the veto line by
  construction, and the veto is a coin-flip under pure noise.
- **Printed only.** A discovery-window PBO, on the same rule, and `n_at_zero` beside each value.
- **What PBO means here.** The headline cell was fixed before any run. PBO asks whether the cell
  that looks best in one half of the months tends to rank below the median in the other half. A
  high value means the grid's ranking is noise, so a gain from any one cell is not trusted.

### Everything printed beside the headline

For each window, for the headline cell, every grid cell and every benchmark: Sharpe, monthly and
daily MDD, CAGR, `ΔCAGR` against `EW-9`, turnover, time in market, worst calendar year, and
Jensen alpha and beta against `EW-9`. Per-sleeve time IN prints for the headline cell.

## Gates

- **GI, inputs.** Each ETF cache covers the first common decision's lookback to 2026-09-22. Every
  SPY session in that range has a close for all nine. No `^IRX` carry exceeds 5 sessions. When
  both `^IRX` copies exist, they agree within 0.01 points on every common date through
  2026-09-22. Any failure refuses (exit 3).
- **GB, basis.** For each ETF, the `Adj Close / Close` ratio never falls by more than 0.01% and
  never jumps by more than 5% between sessions. No daily adjusted return exceeds ±25%. Any
  failure refuses (exit 3) and prints the rows.
- `Resolved at draft (2026-11-27)`: 5% rather than `trend_overlay`'s 2%, because some of these
  ETFs pay large annual or year-end distributions. A refusal here is settled by a
  `Resolved at build` ruling, never by loosening the bound silently.
- `Resolved at build (2026-11-27)`: the first run refused on one row, DBC 2024-12-20 to
  2024-12-23, an `Adj Close / Close` jump of +5.34%. DBC's close fell 5.0% that session while its
  adjusted close rose 0.08%. yfinance's dividend feed lists a 1.116 distribution on 2024-12-23,
  which implies the same +5.34% jump. The ruling: a jump above 5% passes only when the dividend
  feed lists a cash distribution on that ex-date whose implied jump,
  `close_prev / (close_prev − D) − 1`, matches the observed step within 0.1 points. The report
  prints every row passed this way. The 5% bound holds for every other row. The fall bound and the
  ±25% return bound have no exemption. `--refresh` writes the feed to
  `backtests/multi_asset_trend/<TICKER>_dividends.csv`.
- `Resolved after review (2026-11-28)`: the feed-match check alone is circular on yfinance data,
  because yfinance builds `Adj Close` from the same feed. The gate now also requires the adjusted
  close's ex-date return to be within 3 points of zero. The DBC row passes: the raw close returned
  -5.00% and the adjusted close returned +0.08%. This tightens the gate and changes no outcome.
  The operator's ruling on the row is still owed.
- **GX, no lookahead.** The target weights and states behind session `k`'s return read no close
  after the latest decision close at or before `k − 2`. Drift between executions moves weights
  with realised prices only, so it is not a signal. `tests/test_multi_asset_trend.py` changes every later close
  and requires identical weights. Each run also recomputes 24 evenly spaced decisions on series
  cut at that decision close, and stops on any difference.
- **GX and the calendar.** The test also checks that the last row of a cut series is never a
  decision close.
- **GC, the cut.** The in-sample report is identical when every close after 2026-09-22 is changed.
  The test file checks it.
- **GR, replay.** A cell forced IN on every sleeve, with `EW` weights, must reproduce `EW-9`'s
  monthly returns exactly. A mismatch refuses (exit 3). Without it, a gap could come from the
  simulator, not the rule.
- `Resolved at build (2026-11-27)`: `EW-9` is computed by a separate function that has no
  states and no cash sleeve, so GR is a real replay check. "Exactly" is read as a largest monthly
  difference of at most 1e-12, which allows float rounding only.
- **GN, floors.** A window is `UNDERPOWERED` when either holds:
  - it has fewer than **96** complete months;
  - `EW-9` has fewer than **2** episodes with a trough inside it.
- **Why these floors.** 96 months at a 12-month block is 8 blocks. With fewer, the interval
  mostly reflects which few years were drawn. A drawdown statistic from one episode is that one
  event, and no bootstrap can separate the rule from it.
- **The month floor is a backstop.** With the expected first month 2007-03, discovery holds 118
  months and the holdout 116, both from the calendar alone. The month floor binds only if the
  first common decision falls after 2008-12. The episode floor is the live one.

## Verdicts, worded now

### Headline, `TB-12-EW` against `EW-9` at 5 bp

The first matching row wins.

1. **`REFUSED (reason)`.** A gate failed. Nothing else prints in the verdict section.
2. **`UNDERPOWERED`.** Discovery or holdout is below a floor.
3. **`PBO-VETO`.** At least one statistic counts, and the in-sample PBO is above 0.50.
4. **`BEATS-EW`.** Both `ΔSharpe` and `ΔMDD` count.
5. **`DRAWDOWN-ONLY`.** `ΔMDD` counts and `ΔSharpe` does not.
6. **`SHARPE-ONLY`.** `ΔSharpe` counts and `ΔMDD` does not.
7. **`CONTRARY`.** Neither counts, and at least one is clearly worse.
8. **`NULL`.** Every other case.

The rows are complete and mutually exclusive: each case meets exactly one first match, and
`NULL` takes the rest.

- `ΔCAGR`, alpha and beta print beside the word. They never change it.
- **`DRAWDOWN-ONLY` with a clearly worse Sharpe** keeps its word. The Sharpe CI beside it shows
  the cost. The report adds "Sharpe clearly worse" beside the word.
- **`SHARPE-ONLY` with a clearly worse `ΔMDD`** keeps its word the same way, with "drawdown
  clearly worse" beside it.
- **Windows that disagree.** A holdout CI lower bound above 0 with a discovery point estimate at
  or below 0 does not count. If nothing else applies, the word is `NULL`, and the report adds
  "holdout gain, discovery sign disagrees".
- **"Clearly worse" reads the holdout only.** It has no discovery clause.
- **Grid cells** print the word they would get by the same rows, marked "grid, not graded".
- **Sensitivities** print the headline word they would give, marked "printed only".
  `Resolved at build (2026-11-27)`: a cost sensitivity runs every cell and `EW-9` at that cost
  and recomputes PBO at it. A block sensitivity keeps the 5 bp PBO, which no block changes.
- **The other benchmarks** print the headline cell's deltas against `SPY` and `60-40`, with no
  word.

### Forward

- **Opens with 2026-12**, the first complete month after registration. `TB-12-EW` against `EW-9`
  at 5 bp.
- **Minimum 36 forward months.** The read fires once, on the first run after 2029-11 is
  complete. Until then the forward line prints `STILL-OPEN` with a count of forward months.
- **Words at the read**, on point estimates over the forward months:
  - `FORWARD-AGREES`: `ΔSharpe` above 0 and `ΔMDD` above 0;
  - `FORWARD-SPLIT`: exactly one of the two above 0;
  - `FORWARD-AGAINST`: neither above 0.
- **Why point estimates.** 36 months is three 12-month blocks. No interval at that size means
  much, so the forward read checks for decay; it is not a second test. The block-6 CIs print
  beside it.
- **Verdict of record.** The first forward run that prints a word other than `STILL-OPEN`. Later
  runs are descriptive.

### The banner

The report's section titled VERDICT prints:

```
>>> multi_asset_trend HEADLINE (TB-12-EW vs EW-9, holdout 2017-01 to 2026-08, 5 bp): <word> <<<
>>> multi_asset_trend DISCOVERY (<first> to 2016-12): dSharpe <x> [<lo>, <hi>] dMDD <x> [<lo>, <hi>] <<<
>>> multi_asset_trend HOLDOUT (2017-01 to 2026-08): dSharpe <x> [<lo>, <hi>] dMDD <x> [<lo>, <hi>] <<<
>>> multi_asset_trend PBO (12 cells, S=16, in-sample): <value> <<<
>>> multi_asset_trend OPTIONS ARM (descriptive, not graded): <priced>/<wanted> trades priced <<<
>>> multi_asset_trend FORWARD (TB-12-EW vs EW-9 from 2026-12, 36-month minimum): <word> <<<
```

In the DISCOVERY line, `<first>` is the first graded month, expected 2007-03. Each window line
also prints `ΔCAGR`, alpha and beta.

## Anti-tuning

- **Fixed here, the universe.** The nine ETFs, the T-bill cash leg and the adjusted-close basis.
- **Fixed here, the rules.** The 12 cells, the headline cell, the month-end decision, the
  next-session execution and the tie rule.
- **Fixed here, the money.** The 5 bp cost on every sleeve, its two sensitivities, and the
  benchmarks.
- **Fixed here, the judging.** The windows and their dates, the 10% episode line, the floors, the
  12-month block, the 5,000 draws and the seed, the PBO bar, the 36-month forward minimum, and the
  verdict words.
- No other ETF, lookback, rule, weighting, cost or window is graded.
- A grid cell, a sensitivity, a benchmark or the options arm never re-grades the headline.
- PBO never selects a cell.
- The in-sample run reads no close after 2026-09-22. The forward read opens with 2026-12. No
  later run moves either date.

## What could ship

Nothing ships from this study.

- `BEATS-EW`, `DRAWDOWN-ONLY` or `SHARPE-ONLY` files "multi-asset trend: in-sample gain, to be
  tested forward" in [`deployment-evidence.md`](../../deployment-evidence.md). Any live
  allocation needs its own registration and an operator decision.
- A `FORWARD-AGAINST` read after an in-sample gain files the gain as decayed.
- The options arm's figures may inform a later registration. They never support a verdict here.
- No word here changes a tier, a veto, a size class, an exit, the deploy card or the hedge sleeve
  in [§4](../../../docs/deployment-rules.md#s4).
