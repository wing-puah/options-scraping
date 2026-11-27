## vol_managed_spy — does cutting SPY exposure when volatility is high beat simply holding less SPY?

<!-- outcome:start -->
> Latest outcome: not yet run — registered 2026-11-27
<!-- outcome:end -->

_Registered 2026-11-27._

**STATUS: REGISTERED · ACCEPTED BY DEFAULT, NOT YET RUN**, on the drafter's recommended defaults
(the operator's standing rule of 2026-10-09). The operator set the design on 2026-11-27. The
drafter filled the gaps it left with the most conservative conventional choice, each tagged
`Resolved at draft (2026-11-27)` beside its rule. No return, Sharpe ratio, drawdown, weight or
turnover figure for any rule, cell or benchmark below was computed before this file was written.
A fresh second reader checked it on 2026-11-27, before its first outcome
([README](../README.md#the-second-reader-before-every-new-registration-freezes)). It found no
lookahead in the rule. Its changes are tagged `Resolved at second read (2026-11-27)` beside the
rules they amend.

## The question

Does scaling a SPY position down when recent realised volatility is high improve the Sharpe ratio
or cut the maximum drawdown? The comparison that decides it is a constant SPY and T-bill mix that
holds the same average weight in SPY. The holdout decides the verdict.

The lever is a sizing rule for a small fully mechanical account, about $13,000. It holds SPY
shares and T-bills only. It never borrows, so the weight in SPY is capped at 1.0.

The published claim, and the dispute:

- Moreira, A. and Muir, T. (2017), "Volatility-Managed Portfolios", *Journal of Finance* 72(4).
  Scaling a factor by the inverse of last month's realised variance raised its Sharpe ratio. For
  the US market the managed portfolio had a positive alpha on the unmanaged one. Their version
  levers up in calm months; this study cannot.
- Cederburg, S., O'Doherty, M. S., Wang, F. and Yan, X. (2020), "On the Performance of
  Volatility-Managed Portfolios", *Journal of Financial Economics* 138(1). Across 103 equity strategies
  the regression alphas were real in sample. A real-time investor using them out of sample mostly
  did no better than the unmanaged strategy.
- Harvey, C. R., Hoyle, E., Korgaonkar, R., Rattray, S., Sargaison, M. and Van Hemert, O.
  (2018), "The Impact of Volatility Targeting", *Journal of Portfolio Management* 45(1).
  Volatility targeting cut the left tail across assets. It raised the Sharpe ratio mainly for
  equities and credit, where volatility rises as prices fall.
- Liu, F., Tang, X. and Zhou, G. (2019), "Volatility-Managed Portfolio: Does It Really Work?",
  *Journal of Portfolio Management* 46(1). The published strategy's scaling constant is fixed
  with the whole sample, which no real-time investor could do. Without that lookahead, they found
  the managed market portfolio did not reliably beat the market. That point is why benchmark
  `MIX` below is a benchmark and never a rule.

So the prior is published and contested. The best-supported part is the tail cut on equities.

What each headline word would mean:

| Word | Meaning |
|---|---|
| `BEATS-MIX` | The managed rule had a higher Sharpe ratio and a shallower maximum drawdown than `MIX` |
| `DRAWDOWN-ONLY` | It had a shallower maximum drawdown than `MIX`; the Sharpe gain was not shown |
| `SHARPE-ONLY` | It had a higher Sharpe ratio than `MIX`; the drawdown gain was not shown |
| `PBO-VETO` | A gain was shown, but the 12-cell grid looks overfit, so it is not claimed |
| `CONTRARY` | No gain was shown, and the managed rule was clearly worse on at least one statistic |
| `NULL` | No gain and no clear loss was shown |
| `UNDERPOWERED` | Too few months or too few drawdowns to judge. Nothing is concluded |
| `REFUSED (reason)` | A gate failed. Nothing is computed past it |

No word changes a rule in production.

## What this study is not

- **Not leveraged.** The weight never exceeds 1.0. The levered half of Moreira and Muir's result
  is not tested.
- **Not an option study.** It holds shares and T-bills. It says nothing about hedging with puts
  or selling volatility.
- **Not a forecast test.** It grades a portfolio's Sharpe ratio and drawdown, not whether high
  volatility predicts a low next-month return.
- **Not after tax.** Monthly rebalancing realises gains. A taxable account would pay for that,
  and this study charges nothing for it.
- **Not whole shares.** Weights are fractional. At $13,000 one SPY share is about 5% of equity,
  so live weights would be rounded.
- **Not a parameter search.** Twelve cells are fixed below, and one is the headline. The other
  eleven exist so PBO can measure how fragile the choice is.
- **Not a book study.** It reads no play, flow signal or backtest row.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price series

| Series | Source | Use |
|---|---|---|
| SPY adjusted close | yfinance `Adj Close`, from 1993-01-29 | Every volatility estimate and every SPY return. Returns are total returns |
| SPY close | yfinance `Close` | Gate GB only |
| `^GSPC` close | `backtests/trend_overlay/GSPC.csv`, read only | The session calendar in gate GI only |
| `^IRX` close | `backtests/trend_overlay/IRX.csv`, read only | T-bill cash |

- **Cache.** The module writes `backtests/vol_managed_spy/SPY.csv` (date, close, adj_close). It
  fetches only with `--refresh`. Without the flag it reads the cache, and a missing file refuses
  (exit 3). yfinance's `end` is exclusive, so today's bar is never fetched.
- **Files owned by `trend_overlay`.** This module never writes `backtests/trend_overlay/`.
  `Resolved at draft (2026-11-27)`: forward months need closes past those files' last date. So
  `--refresh` also writes `backtests/vol_managed_spy/IRX.csv` and `GSPC.csv`. The module reads
  those copies when they exist, and gate GI checks each copy against the `trend_overlay` file.

### Calendar

- **Sessions.** The SPY session dates.
- **Month-end.** A session is a month-end when the next session falls in a later month. The last
  row of a series is never a decision close, so a cut series never invents a decision (as in
  `trend_overlay`).
- **Monthly return.** The compounded daily return of a curve over the sessions of one calendar
  month. Every graded statistic uses monthly returns.

### Cash

- **Daily T-bill return** on session `k` = `^IRX` close of session `k − 1` / 100 / 252. The yield
  is known before the session it pays for.
- **Zero and negative quotes are data.** `^IRX` printed at or below zero on some 2020 sessions. A
  finite close at or below zero is used as printed, which gives a zero or small negative T-bill
  return. It is never dropped, carried or floored. Gate GI checks this.
- **A session with no `^IRX` close** (an empty or non-numeric field, or no row) carries the last
  close forward. A carry of more than 5 sessions refuses (gate GI).
- `Resolved at draft (2026-11-27)`: `^IRX` is a discount-basis yield, not a bond-equivalent one.
  A broker cash sweep on a small account also pays less than T-bills. Both errors fall alike on
  every curve that holds cash.

### The rule

At each month-end close `t`, the rule sets one target weight `w` in SPY. The rest of equity is
in T-bills.

- **The volatility estimate.** `σ̂` is the sample standard deviation (one degree of freedom
  removed) of the last `N` daily log returns of the SPY adjusted close, ending with the return
  into close `t`. It is multiplied by `√252` to annualise it.
- **Volatility form (`VOL`).** `w = min(1.0, target / σ̂)`.
- **Variance form (`VAR`).** `w = min(1.0, (target / σ̂)²)`. This is Moreira and Muir's scaling,
  with the cap.
- **Decision.** The weight reads closes at or before `t` only.
- **Execution.** The portfolio trades to `w` at the close of the next session, `t + 1`. The return
  from close `t + 1` to close `t + 2` is the first one earned at the new weight.
- **Between executions** the weights drift with prices. No trade is made.
- **Cost.** 5 basis points per side on the SPY notional traded, charged at the execution close.
  The SPY notional traded is `|w − drifted SPY weight|` × equity.
- `Resolved at draft (2026-11-27)`: the T-bill side is not charged. On a shares account, cash is
  the broker balance, not a fund that is bought and sold.
- **No floor and no band.** Every execution trades to `w`, however small the change.
- **Start.** Every curve starts at 1.0 at the first execution close, at its target weight, with no
  entry cost.

### The 12 cells, fixed here

| Factor | Values |
|---|---|
| Window `N` | 21 or 63 sessions |
| Scaling | `VOL` or `VAR` |
| Target | 0.10, 0.12 or 0.15 a year |

- **Cell labels** read scaling, window, target in hundredths: `VOL-21-12`, `VAR-63-15`, and so
  on.
- **The headline cell is `VOL-21-12`.** It is the only graded cell.
- `Resolved at draft (2026-11-27)`, why this cell. `VOL` is the form the operator wrote as the
  rule, and the form Harvey et al. test. 21 sessions is Moreira and Muir's one-month window. 0.12
  is the middle target. It sits below SPY's usual volatility. So the rule sits at the cap in calm
  months and cuts in the others.

### Benchmarks

| Label | What it holds | Role |
|---|---|---|
| `MIX` | A fixed weight `w̄` in SPY, the rest in T-bills, traded back to `w̄` at every execution close at the same 5 bp | The graded comparison |
| `SPY` | SPY alone, bought once and held | Printed, not graded |
| `MIX-VOL` | A fixed weight whose daily volatility over the window equals the managed rule's. Like `w̄`, it is known only at the window's end | Printed, not graded |

- **`w̄`** is the mean of the managed rule's target weights over the executions whose month falls
  in the window graded. Each window, and each cell, gets its own `w̄`.
- **`w̄` is known only at the window's end.** No investor could have held `MIX` at the time.
- **Why that is fair for a benchmark.** `MIX` asks one question: did the timing of the cuts add
  anything over the same average exposure held flat? Giving the benchmark the rule's own average
  removes "it just held less stock" as the reason for any gain.
- **Why it is not allowed for a rule.** A rule must trade on what it knows that day. A weight
  fixed with the whole sample is the lookahead Liu, Tang and Zhou found in the published market
  result. So no grid cell, sensitivity or later rule may use `w̄`.
- **Sharpe against `MIX` and `SPY`.** A constant mix with T-bills has about SPY's own Sharpe ratio,
  less small rebalancing costs. So `ΔSharpe` against either is nearly the same number. `MIX`
  matters for the drawdown and the CAGR.
- `Resolved at second read (2026-11-27)`, **what each statistic can and cannot show.**
  - `ΔSharpe` asks whether the timing raised the return per unit of risk. Holding less stock
    cannot raise it on its own, so this test is meaningful even though `MIX` and `SPY` give it
    the same number.
  - `ΔMDD` asks whether the timing cut the worst fall by more than the same average stock held
    flat. Without `MIX`, holding less stock would pass this test on its own.
  - Neither shows that the rule earns more than SPY. `ΔCAGR` against `SPY` prints for that, and
    grades nothing.

### Windows

| Window | Months | Role |
|---|---|---|
| Discovery | First month after the first decision, to 2009-12 | Sign check |
| Holdout | 2010-01 to 2026-08 | Decides the verdict |
| Post-publication | 2017-01 to 2026-08, inside the holdout | Printed only |
| Gap | 2026-09 to 2026-11 | In no window |
| Forward | From 2026-12 | One-shot forward read |

- **The first decision** is the first month-end with 63 daily returns before it, so all 12 cells
  are defined. SPY starts 1993-01-29, so the expected first decision is 1993-04-30 or 1993-05-28.
  The module finds the date from the data and prints it.
- **The first month is short by one session.** The curves start at the first execution close, so
  that month runs from it to the month's last close. Every cell and benchmark is treated alike.
- **Each window stands alone.** A window's statistics, episodes, `w̄` and bootstrap read only that
  window's months. Its equity is rebased to 1.0 at the window's start, and the running peak starts
  at that 1.0. The simulation itself runs once, without a restart.
- **The in-sample cut.** Every series is cut at 2026-09-22 (`IN_SAMPLE_END`) before anything is
  computed. Only complete calendar months are graded, so the holdout ends with 2026-08.
- `Resolved at draft (2026-11-27)`: the design said "to the last complete month". Closes after
  2026-09-22 were seen in the 2026-11-21 bear peek. `trend_overlay`, `multi_asset_trend` and the
  [holdout seal](holdout_seal.md) cut there too, so this study does the same.
- **Post-publication.** Moreira and Muir circulated in 2016 and were published in 2017. The
  2017-01 split shows the rule after publication. It prints the same statistics and CIs, and no
  word.
- **The forward run is continuous.** It runs the same simulation through the gap without a
  restart. Only months from 2026-12 are graded forward. 2026-11 is the registration month and is
  incomplete on 2026-11-27.

### Metrics, fixed here

| Metric | Definition |
|---|---|
| Sharpe | `√12 ×` mean / sample standard deviation of monthly excess returns over the monthly T-bill return |
| Max drawdown (`MDD`) | The largest fall of the compounded monthly equity from its running peak, as a fraction of that peak |
| CAGR | Compounded monthly equity, `E_end^(12 / months) − 1` |
| Mean weight | `w̄`, as above; also the share of executions at the cap of 1.0 |
| Turnover | SPY notional traded over pre-cost equity, summed over the window, times 12 / months |
| Worst calendar year | The lowest compounded calendar-year return; a partial year is labelled partial |
| Daily MDD | MDD on the daily equity curve, printed beside the monthly one |
| CVaR, monthly | The mean of the worst 5% of monthly returns, printed only |

- `ΔSharpe = Sharpe(managed) − Sharpe(MIX)`. Positive favours the managed rule.
- `ΔMDD = MDD(MIX) − MDD(managed)`. Positive means the managed rule's worst drawdown was
  shallower.
- `ΔCAGR = CAGR(managed) − CAGR(MIX)`, in points a year. Printed, never graded.

### The Moreira and Muir regression (`ARM R`)

- **The regression.** OLS of the managed cell's monthly excess return on SPY's monthly excess
  return, over one window. The intercept times 12 is `alpha`. The slope is `beta`.
- **What it adds.** It asks the published question directly. A constant mix at weight `beta` has
  zero alpha before costs, so `ARM R` compares the rule to a mix matched on beta, not on mean
  weight.
- **Graded on `VOL-21-12` only**, by the bootstrap below, with its own word. It never changes the
  headline word.
- Newey–West standard errors with 12 lags print beside the bootstrap CI.

### Drawdown episodes

- **An episode** is a fall of `SPY`'s monthly equity of **15%** or more from its running peak.
- **Peak** is the month of the running high. **Trough** is the lowest month before recovery.
  **Recovery** is the first later month at or above the peak, or the window end. A new episode
  starts only after a recovery.
- **Per episode**, printed: dates, `SPY`'s depth, and the headline cell's and `MIX`'s deepest
  drawdown inside it. Also printed: the managed weight at each execution inside the episode.
- `Resolved at draft (2026-11-27)`: 15% rather than `trend_overlay`'s 20%. On month-end closes a
  fast crash such as 2020's can show a fall just under 20%. A 20% line could leave the holdout
  below the episode floor for that reason alone. The drafter set the line from public market
  history, not from this data.
- `Resolved at second read (2026-11-27)`, **what the line was chosen knowing.** From public index
  history, a 20% line on month-end closes is expected to give the holdout about one episode, in
  2022. A 15% line is expected to add 2011 and 2020. So the line was set knowing roughly
  which side of the 2-episode floor each choice would put the holdout. No count was made on this
  data. The line feeds only gate GN, the printed episode table and the forward "no forward
  episode" note. No graded statistic reads it, so it can decide whether the study runs, never
  which way it comes out.

## Dependencies

- yfinance, for SPY and, with `--refresh`, `^IRX` and `^GSPC`.
- `backtests/trend_overlay/IRX.csv` and `backtests/trend_overlay/GSPC.csv`, read only.
- `scripts/backtest_study/lib/path_bootstrap.py::_resample_indices`, the moving circular block
  resampler, imported unchanged.
- `scripts/backtest_study/lib/pbo.py::cscv`, with a Sharpe metric defined in the module.
- `scripts/backtest_study/lib/era.py::SEAL_START`, printed in the header.

## Population and basis, fixed here

- **Era.** The inputs carry no prompt version. The report prints `era: current (inputs are
  unversioned market closes)`, as `trend_overlay` does. A run asked for any other era refuses
  (exit 2), as `multi_asset_trend` does.
- **The seal.** The seal binds signal dates of emitted plays. This study reads no play, flow
  signal or backtest row, so the seal does not bind it.
- **Report header.** Era, the windows with their actual first and last months, the git sha, the
  dirty flag, each input file with its first and last date, and the first decision.

## Plan-time observations, disclosed

Every check below was made on 2026-11-27, before this file was written.

### Inputs

- **This study's cache.** `backtests/vol_managed_spy/` does not exist yet. No series was fetched
  for it.
- **`backtests/trend_overlay/SPY.csv`.** Its header and first row were read for the layout. It
  starts 1993-01-29 and holds 8,512 data rows. No return was computed. This study does not read
  it.
- **`backtests/trend_overlay/IRX.csv`.** Its header and first row were read. It starts 1960-01-04
  and its last row is 2026-11-20. It holds 16,708 data rows.
- **`backtests/trend_overlay/GSPC.csv`.** Its header and last date, 2026-11-20, were read.

### What the drafter already knows

- **`trend_overlay`'s printed outcome.** The drafter read it in `research/current.md`. It prints
  SPY's total-return MDD over 1993-02 to 2026-09-22 and its four 20% bear markets. That set no
  number here, but the discovery and holdout windows are not blind in rough size.
- **`multi_asset_trend`'s printed outcome**, in the same file. SPY is one of its nine sleeves.
  It set no number here.
- **A book-level vol-targeting overlay** was tried on the options book in `account_sim` work and
  dropped. `research/deployment-evidence.md` prints its Sharpe against the book's. That is a
  different population, an option book, and it set no number here.
- **Public market history.** The drafter knows when SPY's large volatility spikes fell, in both
  windows. The 2020 crash was fast, and a monthly rule reacts only after its first month.

### Known limits, stated now

- **The cap removes the levered half.** Moreira and Muir's gain comes partly from levering up in
  calm months. Capped at 1.0, the rule can only cut. So any gain must come from the high-volatility
  months alone.
- **Published-rule decay.** The post-publication split and the forward read measure the rule
  after it was known. A null there may be decay, not a false claim.
- `Resolved at second read (2026-11-27)`: **the holdout is not out of the paper's sample.**
  Moreira and Muir's data run to about 2015, so 2010–2015 lies inside their sample, and the
  headline cell copies their window. The holdout is held out from this study's choices, not from
  theirs.
- **Few independent observations.** About 200 holdout months, and the bootstrap block is 12
  months. That is roughly 17 independent blocks. Only a large difference can clear zero.
- **One asset, one estimator family.** PBO covers the 12 cells, not other estimators such as
  exponential weighting or implied volatility.

### A prior, not evidence

The drafter expects `DRAWDOWN-ONLY` or `NULL`. Harvey et al. found the tail cut the most robust
part. Cederburg et al. found the Sharpe gain did not survive out of sample. The drafter expects
the `ΔSharpe` interval to straddle zero, and PBO near 0.5, because the 12 cells are close
variants of one idea.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `VOL-21-12` | arm | Volatility form, 21 sessions, target 0.12 | Headline, graded on the holdout |
| `ARM R` | arm | `VOL-21-12`'s alpha on SPY | Secondary, graded on the holdout |
| The other 11 cells | cell | The rest of the 2 × 2 × 3 grid | PBO only; their deltas print, not graded |
| `MIX` | control | Constant SPY and T-bill mix at the rule's mean weight | The graded comparison |
| `SPY` | control | SPY bought and held | Printed, not graded |
| `MIX-VOL` | control | Constant mix matched on volatility | Printed, not graded |
| Post-publication | descriptive cut | 2017-01 to 2026-08 | Printed only |
| Episodes | descriptive cut | Per `SPY` drawdown, the managed and `MIX` depths | Printed only |
| Sensitivities | descriptive cut | Cost 0 and 15 bp; bootstrap block 6 and 24 | Printed only |
| `FORWARD` | population scope | `VOL-21-12` against `MIX` from 2026-12 | One-shot forward read |

## How it is judged

### Bootstrap

- **Paired moving block bootstrap on monthly returns.** Each draw resamples one window's months
  with `path_bootstrap._resample_indices`. The managed return, `MIX`'s return, SPY's return and
  the T-bill return of a month travel together. The rule is not re-run on the resampled path.
- `Resolved at second read (2026-11-27)`: **`MIX` is re-matched in every draw.** Each month
  carries the target weight of the execution in that month. A draw's mean weight `w̄_b` is the
  mean of the weights its months carry. In that draw, each month's `MIX` excess return over the
  T-bill is scaled by `w̄_b / w̄`, and the T-bill return is added back.
  - **Why.** The draft held `w̄` at the window's observed value in every draw. A draw heavy in
    high-volatility months then gives `MIX` more stock than the managed rule held in that draw.
    A calm draw gives it less. The net bias in the `ΔMDD` interval could not be signed in
    advance, so the draft's interval did not test "same average exposure".
  - **Exactness.** Over a holding period with no trade, a constant mix's excess return is its
    weight times SPY's excess return. Over a calendar month it is so to within drift over one
    session. On the observed path `w̄_b = w̄`, so the scaling changes nothing there.
  - **What it leaves alone.** A positive scale does not change a Sharpe ratio, so `ΔSharpe` draws
    are unchanged. Only the `ΔMDD` draws move.
- **Block 12 months**, 5,000 draws, seed 20261127. Each window uses the same seed.
- **Per draw:** `ΔSharpe`, `ΔMDD` and `ARM R`'s `alpha`, refitted on the resampled months.
- **The CI.** The 2.5th and 97.5th percentiles of the draws. The observed value prints beside it.
- `Resolved at draft (2026-11-27)`: a 12-month block keeps a year of volatility clustering, and
  most drawdowns whole. The 63-session window makes weights overlap across three months, which a
  12-month block also covers.
- **What the `ΔMDD` interval means.** A resampled path re-orders the months that happened. A
  drawdown longer than one block is cut at block joins. So the interval measures the noise in one
  drawdown figure. It is not centred on the observed `ΔMDD`, as in `trend_overlay`.

### When a headline statistic counts, with Holm

The two headline statistics, `ΔSharpe` and `ΔMDD`, are one family of two tests. Holm's step-down
method holds the one-sided family error at 0.025, the same as 0.05 two-sided.

- **Each statistic's p-value** is the share of the 5,000 holdout draws at or below 0. It is
  one-sided, in the direction of a benefit.
- **Order.** The statistic with the smaller p-value is tested first. A tie tests `ΔSharpe` first.
- **First test.** Its p-value is below 0.0125. This is about the same as its 97.5% interval
  (lower end at the 1.25th percentile) lying above 0.
- **Second test.** Run only if the first statistic's p-value passed its threshold, whatever that
  statistic's discovery sign. Its p-value is below 0.025. This is about the same as its usual
  95% interval lying above 0.
- `Resolved at second read (2026-11-27)`: **the p-value rules.** An interpolated percentile and
  a count of draws can disagree by one draw at the boundary. The thresholds above apply to the
  p-value. The intervals print beside it.
- **A statistic counts** when it passes its Holm test and its discovery point estimate is above 0.
  The discovery CI prints but does not gate.

So an interval that touches zero never counts. That is the bar `trend_overlay` and
`multi_asset_trend` registered, made stricter by Holm. If the first-tested statistic fails Holm,
the second cannot count either.

**Clearly worse.** A statistic is clearly worse when its holdout 97.5th percentile is below 0.
This reads the holdout only, with no Holm step and no discovery clause.

### `ARM R`

`ARM R`'s `alpha` is outside the Holm family. It is a separate question with its own word.

- **Counts** when its holdout 2.5th percentile is above 0 and its discovery point estimate is
  above 0.
- **Clearly negative** when its holdout 97.5th percentile is below 0.
- `Resolved at second read (2026-11-27)`: **`ALPHA` beside a `NULL` headline is no
  contradiction.** The rule's correlation with SPY is below 1. So `alpha` can be above 0 when the
  rule's Sharpe ratio is no higher than SPY's.

### PBO / CSCV

- **Rows.** The monthly excess returns over T-bills of the 12 cells, over the whole in-sample
  window, discovery and holdout together.
- **Columns.** The 12 cells. **S = 16.**
- **Trim, not pad.** The oldest months are dropped until 16 divides the row count. The dropped
  months are printed. A zero excess month is not a true row for any cell here.
- **Metric.** The Sharpe ratio of the rows given. A zero standard deviation gives NaN, which `cscv`
  ranks worst.
- **The bar.** Above **0.50** is a veto. Above 0.25 and at most 0.50 prints "selection fragile".
- **The noise baseline.** With 12 cells, an in-sample best cell that lands at random out of sample
  gives a PBO near 0.50. So the veto is close to a coin-flip under pure noise.
- **What it never does.** It never selects a cell. The headline was fixed before any run.
- `Resolved at second read (2026-11-27)`: **a veto on a drawdown gain.** PBO ranks the cells by
  Sharpe ratio, not by drawdown, as in `multi_asset_trend`. So a veto on a `ΔMDD` gain says the
  grid's ranking is fragile, not that the drawdown gain is.
- `Resolved at second read (2026-11-27)`: a PBO that is not finite refuses, as
  `REFUSED (PBO undefined)`.

### Everything printed beside the headline

For each window, for every cell and benchmark: Sharpe, monthly and daily MDD, CAGR, `ΔCAGR`
against `MIX` and `SPY`, mean weight, share at the cap, turnover, worst calendar year and monthly
CVaR. The headline cell also prints `ARM R`'s alpha and beta, and its deltas against `SPY` and
`MIX-VOL`.

## Gates

- **GI, inputs.**
  - The SPY cache runs from 1993-01-29 to at least 2026-09-22 in sample. For a forward run, it
    reaches the last session of the last forward month graded.
  - Every `^GSPC` session in that range has a SPY close, and every SPY session has a `^GSPC` close.
  - No SPY close or adjusted close is empty, zero or negative.
  - No `^IRX` carry exceeds 5 sessions.
  - Every finite `^IRX` close at or below zero is used. The count used equals the count in the
    file, and `tests/test_vol_managed_spy.py` checks it on a file with such rows.
  - When both copies of a file exist, they agree within 0.01 points on every common date through
    2026-09-22.
  - Any failure refuses (exit 3) and prints the rows.
- **GB, basis.** SPY's `Adj Close / Close` ratio never falls by more than 0.01% and never jumps by
  more than 2% between sessions. No daily adjusted return exceeds ±25%. Any failure refuses
  (exit 3) and prints the rows. A refusal here is settled by a `Resolved at build` ruling, never
  by loosening a bound silently.
- **GX, no lookahead.**
  - The weight behind session `k`'s return reads no close after the latest decision close at or
    before `k − 2`.
  - `σ̂` at decision `t` reads daily returns into closes at or before `t` only.
  - The test file changes every later close and requires identical weights.
  - Each run also recomputes 24 evenly spaced decisions on series cut at that decision close, and
    stops on any difference.
  - The test also checks that the last row of a cut series is never a decision close.
- **GC, the cut.** The in-sample report is identical when every close after 2026-09-22 is changed.
  The test file checks it.
- **GR, replay.** Two checks, each by a separate function with no volatility logic:
  - a cell forced to weight 1.0 must reproduce `SPY`'s monthly returns;
  - a cell forced to a fixed weight `w̄` must reproduce `MIX`'s.
  - "Reproduce" means a largest monthly difference of at most 1e-12. A mismatch refuses (exit 3).
  - Without GR, a gap could come from the simulator, not the rule.
- **GW, weights.** Every target weight lies in [0, 1.0]. Every `σ̂` is finite and above 0. Any
  failure refuses (exit 3).
- **GN, floors.** A window is `UNDERPOWERED` when either holds:
  - it has fewer than **96** complete months;
  - `SPY` has fewer than **2** episodes with a trough inside it.
- **Why these floors.** 96 months at a 12-month block is 8 blocks. A drawdown statistic from one
  episode is that one event, and no bootstrap can separate the rule from it.

## Verdicts, worded now

### Headline, `VOL-21-12` against `MIX` at 5 bp

The first matching row wins.

1. **`REFUSED (reason)`.** A gate failed. Nothing else prints in the verdict section.
2. **`UNDERPOWERED`.** Discovery or holdout is below a floor.
3. **`PBO-VETO`.** At least one statistic counts, and the in-sample PBO is above 0.50.
4. **`BEATS-MIX`.** Both `ΔSharpe` and `ΔMDD` count.
5. **`DRAWDOWN-ONLY`.** `ΔMDD` counts and `ΔSharpe` does not.
6. **`SHARPE-ONLY`.** `ΔSharpe` counts and `ΔMDD` does not.
7. **`CONTRARY`.** Neither counts, and at least one is clearly worse.
8. **`NULL`.** Every other case.

Each case meets exactly one first match, and `NULL` takes the rest.

- **"Counts"** is the Holm rule above, with the discovery clause.
- **`DRAWDOWN-ONLY` with a clearly worse Sharpe** keeps its word. The report adds "Sharpe clearly
  worse" beside it. `SHARPE-ONLY` with a clearly worse `ΔMDD` adds "drawdown clearly worse".
- **Windows that disagree.** A statistic that passes Holm on the holdout but has a discovery point
  estimate at or below 0 does not count. If nothing else applies, the word is `NULL`, and the
  report adds "holdout gain, discovery sign disagrees".
- `ΔCAGR` prints beside the word. It never changes it.
- **Grid cells** print the word they would get by the same rows against their own `MIX`, marked
  "grid, not graded".
- **Sensitivities** print the headline word they would give, marked "printed only". A cost
  sensitivity re-runs every cell and `MIX` at that cost and recomputes PBO at it. A block
  sensitivity keeps the 5 bp PBO.
- **Post-publication** prints `ΔSharpe`, `ΔMDD` and `alpha` with CIs, and no word.

### `ARM R`, `VOL-21-12`'s alpha on SPY

The first matching row wins.

1. **`REFUSED (reason)`** or **`UNDERPOWERED`**, as for the headline, and for the same reason.
2. **`PBO-VETO`.** `alpha` counts, and the in-sample PBO is above 0.50.
3. **`ALPHA`.** `alpha` counts.
4. **`NEGATIVE-ALPHA`.** `alpha` is clearly negative.
5. **`NO-ALPHA`.** Every other case.

### Forward

- **Opens with 2026-12**, the first complete month after registration. `VOL-21-12` against `MIX`
  at 5 bp.
- **Floor, 36 forward months.** The read fires once, on the first run after 2029-11 is complete.
  Until then the forward line prints `STILL-OPEN` with a count of forward months.
- `Resolved at second read (2026-11-27)`: **the read uses exactly 2026-12 to 2029-11.** A run
  made later still grades those 36 months and no more, and `w̄` is their mean target weight. So
  the read's months never depend on the run date.
- **Sunset, 2030-11-30.** If no run has fired the read by then, the forward line closes as
  `LAPSED`, and nothing is concluded.
- **Words at the read**, on point estimates over the forward months:
  - `FORWARD-AGREES`: `ΔSharpe` above 0 and `ΔMDD` above 0;
  - `FORWARD-SPLIT`: exactly one of the two above 0;
  - `FORWARD-AGAINST`: neither above 0.
- **Why point estimates.** 36 months is three 12-month blocks. No interval at that size means
  much, so the forward read checks for decay; it is not a second test. Block-6 CIs print beside
  it.
- **A calm forward window.** When `SPY` has no 15% episode in the forward months, the report adds
  "no forward episode" beside the word. The cap then rarely bites, and `ΔMDD` says little.
- **Verdict of record.** The first forward run that prints a word other than `STILL-OPEN`. Later
  runs are descriptive.

### The banner

The report's section titled VERDICT prints:

```
>>> vol_managed_spy HEADLINE (VOL-21-12 vs MIX, holdout 2010-01 to 2026-08, 5 bp): <word> <<<
>>> vol_managed_spy DISCOVERY (<first> to 2009-12): dSharpe <x> [<lo>, <hi>] dMDD <x> [<lo>, <hi>] <<<
>>> vol_managed_spy HOLDOUT (2010-01 to 2026-08): dSharpe <x> [<lo>, <hi>] p <p> dMDD <x> [<lo>, <hi>] p <p> <<<
>>> vol_managed_spy ARM R (alpha on SPY, holdout): <word> alpha <x> [<lo>, <hi>] beta <b> <<<
>>> vol_managed_spy PBO (12 cells, S=16, in-sample): <value> <<<
>>> vol_managed_spy POST-PUBLICATION (2017-01 to 2026-08, printed only): dSharpe <x> dMDD <x> alpha <x> <<<
>>> vol_managed_spy FORWARD (VOL-21-12 vs MIX from 2026-12, 36-month floor, sunset 2030-11-30): <word> <<<
```

In the DISCOVERY line, `<first>` is the first graded month. Each window line also prints `w̄`,
the share at the cap and `ΔCAGR`.

## Anti-tuning

- **Fixed here, the rule.** The estimator, both scalings, the cap of 1.0, the month-end decision,
  the next-session execution, and the 12 cells.
- **Fixed here, the headline.** `VOL-21-12`, and `MIX` as its comparison.
- **Fixed here, the money.** The 5 bp cost on the SPY leg, its two sensitivities, and T-bill cash.
- **Fixed here, the judging.** The windows and their dates, the 15% episode line, the floors, the
  12-month block, the 5,000 draws and the seed, the Holm family of two, the PBO bar, the 36-month
  forward floor, the sunset, and the verdict words.
- No other window length, target, estimator, cap, cost or window is graded.
- No parameter is set or changed on the holdout.
- A grid cell, a sensitivity, a benchmark or the post-publication split never re-grades the
  headline.
- PBO never selects a cell. `w̄` is never used by a rule.
- The in-sample run reads no close after 2026-09-22. The forward read opens with 2026-12. No later
  run moves either date.

## What could ship

Nothing ships from this study.

- `BEATS-MIX`, `DRAWDOWN-ONLY` or `SHARPE-ONLY` files "volatility-managed SPY: in-sample gain,
  to be tested forward" in [`deployment-evidence.md`](../../deployment-evidence.md). That earns
  the forward read only.
- Any live sizing rule needs its own registration and an operator decision.
- A `FORWARD-AGAINST` read after an in-sample gain files the gain as decayed.
- No word here supports leverage, an option overlay or a tax claim.
- No word here changes a tier, a veto, a size class, an exit, the deploy card or the hedge sleeve
  in [§4](../../../docs/deployment-rules.md#s4).
