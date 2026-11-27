## spy_put_write — does a weekly SPY put credit spread pay beyond its SPY beta?

<!-- outcome:start -->
> Latest outcome: `NULL` on the first run, 2026-11-27, signal weeks 2022-01-31 to 2026-10-26. `ARM Z NULL: cycle-mean R +0.019 CI95 [-0.072, +0.095] on 232 trades, 55 cycles`; `ARM H NO-ALPHA` at beta 4.49; `C4 PBO 0.829`. Nothing ships. Post-run review: about zero once the uncached November 2026 cycle (about -1 R) is counted. Alpha is per $25,000 of reference capital against unfinanced 4.5x SPY (post-run review) · [record](../../study-results/f3_structure/spy_put_write.md).
<!-- outcome:end -->

_Registered 2026-11-27._

**STATUS: ACCEPTED 2026-11-27. The operator approved the design. The drafter
filled each gap conservatively, and each fill is tagged `Resolved at draft
(2026-11-27)` beside its rule. A revisit after a result is a NEW registration,
never an edit.** A fresh second reader is owed before the first outcome and
before the commit.

## The question

Does a mechanical SPY put credit spread, sold every week, earn a net return
that SPY's own beta does not explain?

Two questions are graded separately, because they can disagree.

| Object | Question | Comparator |
|---|---|---|
| `spy_put_write ARM Z` | Is the mean net R per trade above zero? | none |
| `spy_put_write ARM H` | Is the monthly return above what beta-matched SPY shares earn? | SPY held as shares, by Jensen alpha |

A short put spread is long SPY delta and short volatility at once. In a rising
market it can look profitable for the delta alone. `ARM Z` cannot tell the two
parts apart. `ARM H` can.

**The literature.**

- Whaley (2002) measured the CBOE BXM buy-write index. It writes a one-month,
  at-the-money call each month and holds it to expiry. By put-call parity, a
  covered call and a cash-secured put hold the same payoff, so BXM is the
  put-write's reference.
- Israelov and Nielsen (2015) split a covered call's return into three parts:
  equity exposure, short volatility, and an "equity reversal" part. The
  short-vol part earned a premium. The equity part carried most of the risk.
  The reversal part added risk with little return. This study
  copies that split: `ARM H` removes the beta and grades what is left.

**Why now.** The operator asked on 2026-11-27 for a test of the textbook
put-write on this repo's real quotes, net of beta. No study here has graded
it. See [How this differs from index_vrp](#how-this-differs-from-index_vrp).

### How this differs from index_vrp

[`index_vrp`](index_vrp.md) sold a monthly SPY iron condor at 0.16 delta. It
graded one thing: whether the condor lost on the deployed book's worst days.
It said plainly that it was not a profitability test, and it fitted no beta to
the condor's return.
This study sells a put spread only, so it is directional. It enters weekly,
picks strikes by moneyness, and grades net R against zero and against SPY's
beta. It reads no book. The log recorded "Short index vol is closed for this
book: it neither pays on these quotes nor hedges the book's worst days"
([current.md](../../current.md#2026-10-12--index_vrp-a-short-spy-condor-shares-the-books-bad-months-not-its-bad-days)).
This registration re-opens only the "pays" half, under a new question: the beta
split. That half rested on agent-trading's model-priced rejections and on the
condor's flat P&L, which `index_vrp` printed as a caveat, not as a graded
profit test. The operator approved
the re-opening on 2026-11-27.

## What this study is not

- **Not a sleeve test.** It reads no book and makes no claim about the ladder's
  tail. That was `index_vrp`'s question.
- **Not a VRP gate.** No volatility state chooses entry dates. Every first
  session of an ISO week is a signal date.
- **Not an exit search.** Two exits are registered, and both come from common
  practice. No other exit is tried.
- **Not a fetch.** It prices only quotes the cache already holds. See
  [Dependencies](#dependencies).
- **Not a ship decision.** See [What could ship](#what-could-ship).

## Definitions

| Term | Meaning here |
|---|---|
| Put credit spread | Sell one SPY put at strike `K_s`; buy one SPY put at a lower strike `K_l`, same expiry. Also called a bull put spread |
| Credit | The net premium received at the entry fill, per share. Positive for a valid entry |
| Width | `K_s − K_l`, per share |
| Max loss | `(width − credit) × 100` dollars per one-lot |
| R (this study) | Net dollar P&L of one lot over its max loss. It runs from about −1 to `credit / (width − credit)`. This is not the glossary's realized-percent [R](../../glossary.md#r) |
| Signal date D | The first NYSE session of an ISO week |
| Fill day | The session after D. Every leg fills at that day's close |
| DTE | Calendar days from the fill day to expiry |
| Cell | One combination of short strike, width and exit. There are twelve |
| [MFE / MAE](../../glossary.md#mfe) | The best and worst closing mark of a trade over its hold, in R |
| [Capture](../../glossary.md#capture) | Sum of R over sum of MFE, over trades with MFE above zero |

## Dependencies

- **The option cache.** `backtests/option_history_cache/SPY_*P.csv`, real
  end-of-day Barchart quotes. No model price anywhere. On a fresh checkout, run
  `python3 scripts/backup_research_caches.py pull` before the census.
- **The skip-list.** `backtests/option_history_cache/_unlisted.jsonl`, read as
  evidence that a contract is not listed.
- **SPY closes.** `backtests/mech_regime/spy_base_rate_daily.csv`, extended past
  its end by `spy_vix_daily_full.csv`. This gives the session calendar, the
  settlement close and `ARM H`'s monthly returns.
- **Shared pricing, imported, never copied.** From `scripts/backtest/simulate.py`:
  `entry_day_fill` (with `_junk_entry_fill` and `_close_mid` inside it),
  `_is_junk_quote`, `junk_day_mark`, `_refuse_credit_priced_to_debit`,
  `_entry_outside_bounds`, `_monotonicity_violation`, `common_entry_day`,
  `entry_window_end`, and `_cost_knobs` read on `config/backtest.yml`.
- **Shared helpers.** `mechanical_benchmark.monthly_expiries`,
  `mechanical_benchmark.UniverseSpot`, `mechanical_benchmark.listed_by`,
  `lib/pbo.py::cscv` and `pad_head`, `lib/ruin_walk.py::stationary_indices`,
  and `lib/confidence_sequence.py` with `refuse_floor_forward`'s constants.

**No fetch is part of this registration.** A missing contract is counted as
uncached. It is never fetched by study code. If a fetch is ever run for this
study, it needs a `Resolved at build` note here first. It also needs the cache
to have no other writer running: no backtest, no journal, no other
`fetch_*_legs.py` collector.

## Population and basis, fixed here

### Signal dates and window

- **Signal dates.** The first session of each ISO week in the SPY close table.
- **In-sample window.** It starts at the first signal date whose planned
  expiry is on or after the first cached SPY monthly. It ends at the last
  signal date before 2026-11-27 whose planned expiry is on or before the last
  cached SPY put quote date. The build prints both dates. No date is hardcoded
  here.
- **One window for every cell.** The planned expiry, not the exit, sets the
  window, so all twelve cells share the same signal weeks. A signal week with
  a later planned expiry is excluded and counted.

_Resolved at draft (2026-11-27):_ both ends come from the calendar and the
cache's date range only. Ending the window on the last week with both legs
cached would drop uncached weeks from the coverage count. Ending it on each
trade's exit would keep a target trade that closed early and drop one still
open, so the outcome would choose the sample.
- **The market in the window.** The cache starts with 2022 monthly expiries.
  The window therefore holds the 2022 bear market at its start, then a mostly
  rising SPY. In effect it is one bull tape. A positive `ARM Z` without a
  positive `ARM H` cannot promote anything.
- **Era.** The rule reads no analysis row, so prompt eras do not apply.

_Resolved at draft (2026-11-27):_ the module declares no prompt era, because it
reads no export. The report header says "era: none (option cache only)".

_Resolved at draft (2026-11-27):_ the [holdout seal](../f4_deployment/holdout_seal.md)
was lifted on 2026-11-26. No in-sample date is cut for it.

### Expiry

- Standard monthly expiries only: third Fridays, or the Thursday before on a
  holiday (`mechanical_benchmark.monthly_expiries`).
- Among monthlies with DTE of 21 or more from the planned fill day, take the
  one with DTE nearest 37. Ties go to the earlier expiry.
- Weeklies are not used. Which weeklies were listed on a past date is not
  known from disk.

_Resolved at draft (2026-11-27):_ DTE is counted from the planned fill day,
the session after D. The expiry is therefore known on D. If the actual fill
day moves later and leaves fewer than 21 DTE, the trade is refused and counted.

### Strikes

Spot is `mechanical_benchmark.UniverseSpot` on D: the median `Price~` of up to
five cached SPY calls on D's own rows. Every strike is chosen from D's close,
never from the fill day's.

| Parameter | Values | Target strike |
|---|---|---|
| Short strike | at spot; 3% below; 5% below | `spot × 1.00`, `× 0.97`, `× 0.95` |
| Width | 5% or 10% of spot | long target = `K_s − width × spot` |

- **The grid.** Each target maps to the nearest strike that is a multiple of $5.
  Ties go to the lower strike.
- **Walk.** If that strike is skip-listed, the walk steps to the next nearest
  $5 multiple, ties to the lower. A cached strike counts only when it has a row
  on or before D (`listed_by`). A cached file with no row by D counts as not
  cached.
- **Uncached.** If the nearest $5 strike is neither cached nor skip-listed, the
  trade is `UNCACHED`. It is never built on the next cached strike.
- **Selection print.** SPY's close table covers every signal week, cached or
  not. For the primary cell the census prints, per year, built against not
  built: SPY's return from fill day to expiry, and the spread's intrinsic at
  expiry on the target strikes, in dollars. It carries no verdict. It shows
  whether the cache's holes sit on calm or violent weeks.

_Resolved at build (2026-11-27):_ the selection print takes its target strikes
from the close-table close on D, rounded to $5. A week with no option spot
still needs strikes for this print. "Not built" holds every week the census
does not count as built.

_Resolved at draft (2026-11-27):_ the cache was fetched for past plays and
other studies, not for this rule, so its holes need not be random. Some
studies fetched puts around sell-offs. The coverage floors bound how many weeks
can be missing. The selection print shows which kind are missing.
- **Collision.** If `K_l` equals `K_s`, the trade is dropped and counted.

_Resolved at draft (2026-11-27):_ "nearest listed" is read as the nearest $5
multiple. SPY monthlies list every $5 strike in this range, so the strike is
listed. Its distance from the target is at most $2.50. The finer $1 strikes are
cached only where past plays touched them. Walking them would let the cache's
history choose the strike.

### Fills and costs

- **Decision on D, fill on the next session's close.** Both legs fill at the
  fill day's closing quote, on one clock (`entry_day_fill`). The operator fills
  spreads as one combo order at mid.
- **If a leg has no usable quote that day,** the entry moves to the first day on
  which both legs have one (`common_entry_day`). It must stay inside
  production's window (`entry_window_end`, five sessions). Otherwise the trade
  is refused and counted.
- **The junk-quote rule applies, as production has it.** A junk quote has no
  bid, or a spread wider than its mid, or wider than twice the Cboe width
  (`_is_junk_quote`). A sold leg on a junk quote fills at its bid, or at 0 with
  no bid. A bought leg on a junk quote fills at its mid when a bid exists, and
  is refused when none does.
- **Refused as a bad quote.** A net debit at entry
  (`_refuse_credit_priced_to_debit`), a credit at or above the width
  (`_entry_outside_bounds`), or legs priced against strike order
  (`_monotonicity_violation`). Each is counted.
- **Costs.** Commission $0.65 per contract per leg per side, from
  `config/backtest.yml` through `_cost_knobs`. Slippage 0. That is $2.60 per
  one-lot round trip. R is net of commission. Gross prints beside it.

_Resolved at build (2026-11-27):_ a credit of zero is refused, because the
Definitions call a valid credit positive. A credit equal to the width is
refused too, because the rule says "at or above". `_entry_outside_bounds`
alone refuses only a credit strictly above it.

_Resolved at draft (2026-11-27):_ commission is charged at exit on both legs
even when the spread settles at expiry. Production's `_apply_costs` charges
both sides on every row, so this matches it. A spread that expires worthless
pays no exit commission in practice, so the charge errs against the rule.
Exercise and assignment fees are not modelled. Early assignment of the short put is not modelled either.

### Exits

| Exit | Rule |
|---|---|
| Hold | Hold to expiry. Settle at intrinsic on the expiry-day SPY close |
| Target | Close when a session's closing mark is at or below 50% of the credit. Close at the first session with DTE of 21 or less if the target has not fired |

- **Settlement.** Intrinsic is `max(0, K_s − S) − max(0, K_l − S)`, with S the
  SPY close-table close on the expiry date.
- **Daily marks.** Each leg marks at its closing mid when the quote is two-sided
  and not junk. A junk leg marks by `junk_day_mark`. The spread's mark is
  clamped to the range from 0 to the width.
- **Target fill.** The target is checked on each session's closing mark from
  the session after the fill day. When it fires on session t, the close fills
  at session t+1's daily mark, as defined above. The entry's junk rules do not
  apply at exit.
- **21-DTE fill.** That date is known in advance. The close fills at the
  closing mark of the first session with DTE of 21 or less.

_Resolved at draft (2026-11-27):_ settlement uses the SPY close table, not an
option file's `Price~`. SPY options settle on the closing price, and
`index_vrp` found one bad `Price~` print in the cache. If the expiry date has
no close in the table, the trade is dropped and counted.

_Resolved at draft (2026-11-27):_ a target fill on t+1 avoids filling at the
mark that fired the target. A mark with no real price on t+1 carries the rule
of `junk_day_mark`; if it returns nothing, the close moves to the next session
with a mark.

_Resolved at build (2026-11-27):_ four gaps, each filled with production's
rule or the stricter reading.

- A leg with no row on a day carries its last real snap, as production's daily
  mark does. That mark is tagged `carried`, and `barchart_stale` past
  `max_price_carry_days` (5).
- The 21-DTE session is the first session after the fill day with DTE of 21 or
  less, so no trade closes on its own fill day.
- An unmarked 21-DTE session moves the close to the next session with a mark,
  as the target fill does. A close that finds no mark before expiry settles at
  intrinsic.
- MFE and MAE use the gross marks over max loss. Capture divides net R by that
  gross MFE.

### Size

One lot per trade. Weekly entries at about 37 DTE overlap, so about five
trades are open at once. R is size-free, and the verdicts read R and alpha
only.

The report also prints, per cell:

- dollar P&L of one lot: mean, median, total and worst trade;
- the share of trades whose one-lot max loss is at or under $1,000, the
  operator's stop;
- the share of trades whose worst closing mark breached a $1,000 loss;
- for the primary cell, R with a $1,000 stop applied. A breach on session t's
  close fills at t+1's close. This is descriptive and carries no verdict.

## Plan-time observations, disclosed

Written before any module exists. None of these is an outcome of this rule.

**File census of the cache, 2026-11-27.** Filenames only; no file was opened.
These are SPY put contract files by expiry year.

| Expiry year | Put files, all expiries | Distinct expiries | Monthly expiries | Put files on monthlies |
|---|---|---|---|---|
| 2022 | 1,102 | 45 | 10 | 251 |
| 2023 | 1,144 | 52 | 12 | 271 |
| 2024 | 1,550 | 52 | 12 | 477 |
| 2025 | 2,207 | 54 | 12 | 532 |
| 2026 | 1,921 | 43 | 12 | 592 |
| 2027 | 25 | 4 | 3 | 23 |

- The first cached expiry is 2022-02-25 and the first monthly 2022-03-18.
- Older monthlies hold a $5 grid of about 20 to 28 put strikes. Later ones
  add scattered $1 strikes.
- The monthlies from 2026-10-16 on hold 3 to 12 put files each. Trades on them
  are mostly open or uncached. The forward read will need new quotes.
- The skip-list holds 267 lines naming SPY.

**Arithmetic, not an outcome.** A width of 5% of spot is $20 to $34 per share
over SPY's range in the window. One lot's max loss is then $2,000 to $3,400,
less the credit. One lot is expected never to fit inside $1,000 of max loss. The
$1,000 stop prints show how often the stop would have bound.

**Prior results the drafter has seen.** These set a negative prior. None is a
result of this rule.

| Source | What it printed | Why it is only a prior |
|---|---|---|
| [`index_vrp`](index_vrp.md) | SPY straddle `NO-PREMIUM` at expiry. The SPY condor was "roughly flat": +$337 over 55 cycles at mid | Condor, 0.16 delta, monthly, held to expiry; no beta split |
| [§7.2](../../../docs/deployment-rules.md#s7-2) | `bull_put_spread` PF 0.92 on the v4 book | The analysis's picks on many tickers, not a SPY rule |
| agent-trading 0001 | SPY/QQQ put credit spread rejected: SPY test Sharpe −0.30 | 35%-of-spread fill and a partly synthetic vol model |
| agent-trading 0005 | Same without the regime exit, rejected: SPY −0.13 at model skew | Same basis |
| agent-trading 0058 | SPY put credit spread passed its in-sample bar, then failed adverse fill: Sharpe −0.47 | Same basis; not activated |

## What it compares

| Object | What it is | Kind |
|---|---|---|
| `spy_put_write ARM Z` | Primary cell's mean net R per trade, against zero | PRIMARY |
| `spy_put_write ARM H` | Primary cell's monthly Jensen alpha against SPY shares | PRIMARY |
| the other eleven cells | The same two reads, printed | descriptive cells, inputs to PBO |
| `$1,000 stop` line | Primary cell with the stop applied | descriptive cut |

### The primary cell

**Short strike at spot, width 10% of spot, held to expiry.**

- Both papers measure writing near the money, one month out, held to expiry.
  The at-spot strike, the 37-DTE monthly and the hold exit copy that.
- Their position has no long wing. Of the two registered widths, 10% is
  nearer to it.
- The 50% target and 21-DTE close are trading-desk practice, not literature.
  They are registered as cells, not as the primary.

The primary was chosen before any cell was priced.

### `ARM Z` — net R against zero

- **Unit.** One monthly expiry cycle: the mean net R of the in-sample primary
  trades that share one expiry. The forward read uses the same unit.
- **Statistic.** The mean of the cycle means.
- **Interval.** A stationary block bootstrap over the ordered cycles
  (`lib/ruin_walk.py::stationary_indices`), mean block 3 cycles, 10,000 draws,
  seed 20261127. CI95 by percentile. Blocks of 2 and 4 cycles print beside it.
- **Why cycles, and why 3.** Four or five weekly trades share one expiry and
  most of one path, so they are one bet, not five. Trades on neighbouring
  expiries also overlap for weeks. A block of 3 cycles, about three months,
  keeps them together and matches `ARM H`'s month blocks.
- **Printed beside it, no verdict.** The mean net R per trade, with a
  stationary bootstrap over signal weeks, mean block 8 weeks.

_Resolved at draft (2026-11-27):_ a cycle with no priced trade is kept as an
empty slot in the ordered sequence. Each draw takes the mean of the non-empty
cycle means it holds. One unit for both reads keeps the in-sample and forward
grades on the same footing; a per-trade CI would be narrower than the data
supports.

### `ARM H` — Jensen alpha against SPY shares

- **The account.** Every in-sample primary trade at one lot, with no cap.
- **Marks.** Mark-to-market on `mtm_curve.book_curves`, net of each position's
  commission at its exit. Each trade enters it through `mtm_sessions` and
  `mtm_dollars`: its cumulative dollar P&L at each session's daily mark, as
  defined under Exits, from the fill day to the exit. A held trade's last value
  is its settlement intrinsic.
- **Monthly return.** The book's equity level at the month's last session,
  minus its level at the previous month's last session, over a fixed reference
  capital of $25,000 (`account_sim`'s capital). Nothing compounds. A month with
  no open position returns 0. The capital scales alpha but not its sign or its
  interval's sign.
- **Regression.** Monthly account return on SPY's monthly price return, from
  month-end closes in the SPY close table. The intercept is the alpha. The slope
  is the beta, and beta-matched SPY shares are the comparator it defines.
- **Interval.** `stationary_indices` over months, mean block 3 months, 10,000
  draws, seed 20261127. CI95 by percentile.
- **Months.** From the first full month after the first fill to the last full
  calendar month that ends on or before the last in-sample exit.

_Resolved at draft (2026-11-27):_ the account copies `mechanical_baseline`'s
`ARM H` basis: one contract, no cap, `book_curves` mark-to-market, commission
at exit, reference capital, three-month blocks. A partial last month is cut,
because SPY's return for it would span days the account did not.

_Resolved at draft (2026-11-27):_ returns are raw, with no risk-free rate. No
dividend series is on disk, so SPY's return leaves out its dividend. This
follows `mechanical_baseline`'s build ruling.

_Resolved at draft (2026-11-27):_ the regression fits one static beta. The
equity reversal part that Israelov and Nielsen isolate is not removed. It falls
into the residual and the alpha.

Printed with `ARM H`: the beta, its CI95, and the beta-matched SPY line's
total return beside the account's.

### MFE, MAE and capture

Results are never judged on realized P&L alone. For every cell the report
prints mean and median MFE and MAE in R, capture, and the share of trades that
reached half their max loss on a close.

It also splits marks by pricing tier: closing mid, `barchart_last`,
`barchart_stale` and the zero-bid ceiling. The junk-entry fills are counted the
same way. None of these carries a verdict.

## How it is judged

- **C1 SIGN.** The CI95 excludes zero.
- **C2 LEAVE-ONE-YEAR-OUT.** Dropping any one calendar year keeps the mean's
  sign. For `ARM Z` a cycle's year is its expiry's year. For `ARM H` the fold
  is that year's months.
- **C3 STRESS WINDOWS.** The mean keeps its sign with each window below removed.
  For `ARM Z` a cycle is removed when any of its trades' holds overlaps the
  window. For `ARM H` the window's months are removed.

| Window | Dates |
|---|---|
| W1 2022 bear | 2022-01-01 → 2022-12-31 |
| W2 Aug 2024 | 2024-08-01 → 2024-08-31 |
| W3 Mar–Apr 2025 | 2025-03-01 → 2025-04-30 |
| W4 Feb–Apr 2026 | 2026-02-01 → 2026-04-30 |

_Resolved at draft (2026-11-27):_ the stress windows are `index_vrp`'s. C2
folds by year, not by date or cycle. With about 240 weekly trades on about 55
cycles, one date or one cycle rarely moves the mean, so a finer fold tests
little.

- **C4 OVERFITTING.** [PBO by CSCV](#references) across the twelve cells
  (`lib/pbo.py::cscv`, S = 16). Rows are the in-sample signal weeks, in order,
  the same rows for every cell. Each cell holds two channels per week: its
  trade's net R and a count of 1, or 0 and 0 when that week has no priced
  trade. The metric is `ratio_metric`, the mean net R per trade over the rows
  given. The head is padded with `pad_head` so 16 blocks divide it.

_Resolved at draft (2026-11-27):_ `cscv` refuses an empty value, so an empty
week is the zero row of both channels, not a gap. A pad row is true for the
same reason: no cell had a trade before the first signal week. A cell with no
trade in a whole half ranks worst there.

_Resolved at draft (2026-11-27):_ PBO is computed only over cells with at
least 60 priced trades. It needs at least six such cells, the primary among
them. Otherwise it is "not computable".

## Gates

1. **C0a COVERAGE.** Run by `--dry-run` before anything is priced. The census
   reads filenames and row dates only. For the primary cell it prints, per
   year: signal weeks, built, `UNCACHED`, skip-list steps, no spot, no fill-day
   quote, collisions, and expiry closes missing. It passes when built weeks are
   at least 75% of all signal weeks in the window, and at least 50% in every
   calendar year.
2. **C0b POWER.** Once priced, the primary cell needs at least 120 priced
   trades on at least 24 cycles for `ARM Z`, and at least 24 months for
   `ARM H`. Entry refusals count against it. The 24 cycles and 24 months are
   the independent units; 120 trades is not.
3. **No model price.** Any leg priced by a model raises and stops the run.
4. **No lookahead.** Spot, expiry and strikes come from D's rows or earlier.
   The fill reads the fill day's close only. Each mark reads its own day. The
   settlement close is read only on the expiry date. A test checks each of
   these.

No floor may be lowered after the census.

_Resolved at draft (2026-11-27):_ the coverage floors are new here. A hole of
25% could hide a crash month, so each year is checked too.

_Resolved at build (2026-11-27):_ a week counts as built for C0a only when
both legs also have a row on the planned fill day. A week without one is
printed as "no fill-day quote" and left out of the built count. It is still
priced if both legs quote inside the five-session window. This can only make
C0a harder to pass.

## Bar for a candidate

The primary cell is a candidate only when all of these hold:

- C0a and C0b pass;
- `ARM Z` meets C1, C2 and C3 with a positive mean;
- `ARM H` meets C1, C2 and C3 with a positive alpha;
- PBO is computable and at or below 0.50.

## Verdicts, worded now

### Per object

| Object | Token | When |
|---|---|---|
| `ARM Z` | `POSITIVE` | C1, C2 and C3 hold; mean above zero |
| | `NEGATIVE` | C1 holds; mean below zero |
| | `NULL` | any other powered case |
| `ARM H` | `ALPHA` | C1, C2 and C3 hold; alpha above zero |
| | `NEGATIVE-ALPHA` | C1 holds; alpha below zero |
| | `NO-ALPHA` | any other powered case |

### Study level

Read top to bottom. The first row that applies is the verdict, so exactly one
prints.

| Order | Token | When | What it means |
|---|---|---|---|
| 1 | `UNCOVERED` | C0a fails | Too few weeks are cached. Census printed, nothing priced |
| 2 | `UNDERPOWERED` | C0a passes, C0b fails | Too few priced trades or months. Census printed, nothing concluded |
| 3 | `LOSES` | `ARM Z` is `NEGATIVE` | The put-write loses money on these quotes, net |
| 4 | `PBO-VETO` | `ARM Z` is `POSITIVE`, and PBO is above 0.50 or not computable | It looks profitable, but the cell grid is too fragile to trust |
| 5 | `PUT-WRITE-ALPHA` | `ARM Z` is `POSITIVE` and `ARM H` is `ALPHA` | It pays, and pays beyond its SPY beta. It earns the forward read as a candidate |
| 6 | `BETA-ONLY` | `ARM Z` is `POSITIVE` and `ARM H` is not `ALPHA` | It pays, but no more than beta-matched SPY shares. It is a costlier way to own SPY |
| 7 | `NULL` | any other case | No net return can be shown |

- `BETA-ONLY` prints the `ARM H` token beside it, so `NEGATIVE-ALPHA` stays
  visible.
- `NULL` names the first criterion that failed, and prints the `ARM H` token
  beside it.
- The other eleven cells print their own `ARM Z` and `ARM H` tokens, labelled
  descriptive. They carry no verdict.

_Resolved at build (2026-11-27):_ a descriptive cell's tokens use the primary's
C0b floors. Below them the cell prints `UNDERPOWERED`.

### The forward read

The forward read is the grade of record for anything that would trade.

- **Dates.** Signal weeks from 2026-11-27 on, primary cell.
- **Unit.** Mean net R per monthly expiry cycle, as in `ARM Z`. A forward cycle
  holds only forward trades.
- **Statistic.** A [confidence sequence](../../glossary.md#confidence-sequence)
  on that unit, with `refuse_floor_forward`'s constants imported.
- **Floor.** 30 forward signal weeks with a closed trade, about seven cycles.
- **Tokens.** `STILL-OPEN` below the floor or while the sequence spans zero;
  `FORWARD-HOLDS` when it clears zero above; `FORWARD-FAILS` when it clears
  zero below.
- Forward trades are priced only from quotes the cache holds when the read runs.

_Resolved at build (2026-11-27):_ the sequence's running intersection starts
at the cycle in which the 30th closed forward week falls. Earlier cycles feed
the mean but cannot end the read.

_Resolved at draft (2026-11-27):_ the unit is one cycle, not one trade. Weekly
trades on one expiry share most of their path, so a per-trade sequence would
count one bet four or five times. At seven cycles the sequence is unlikely to
clear zero. The read is expected to stay `STILL-OPEN` for well over a year.

## Anti-tuning

- The primary cell may not change after any number is seen. A losing primary is
  the result.
- No other cell may be promoted in this file. A cell that looks better earns its
  own registration and needs a PBO of 0.50 or less here.
- No strike may be moved onto a cached $1 strike to raise coverage.
- No stress window or year may be dropped from the window because it lost.
- `ARM Z` may not be quoted without `ARM H`, the drop census and the selection
  print beside it.

## What could ship

Nothing ships from the retrospective.

- `PUT-WRITE-ALPHA` earns the forward read as a candidate. A later
  `FORWARD-HOLDS` is the evidence a live-money change would rest on. The change
  still needs the operator's explicit decision and a new section of
  `docs/deployment-rules.md`.
- `BETA-ONLY` ships nothing. Owning SPY directly does the same job with less
  cost and no short-vol tail.
- `LOSES`, `NULL`, `PBO-VETO`, `UNCOVERED` and `UNDERPOWERED` ship nothing.

## References

| Paper | Use here |
|---|---|
| Whaley (2002), "Return and risk of CBOE Buy Write Monthly Index", _Journal of Derivatives_ 10(2) | The reference buy-write: one-month, near-the-money, held to expiry; the primary cell |
| Israelov & Nielsen (2015), "Covered calls uncovered", _Financial Analysts Journal_ 71(6) | Splitting the return into equity beta and short volatility; `ARM H` |
| Jensen (1968), "The performance of mutual funds in the period 1945–1964", _Journal of Finance_ 23(2) | `ARM H`: alpha as the intercept of returns on the market |
| Politis & Romano (1994), "The stationary bootstrap", _Journal of the American Statistical Association_ 89(428) | The block bootstrap for overlapping trades and months |
| Bailey, Borwein, López de Prado & Zhu (2017), "The probability of backtest overfitting", _Journal of Computational Finance_ 20(4) | C4: PBO by CSCV across the twelve cells |
