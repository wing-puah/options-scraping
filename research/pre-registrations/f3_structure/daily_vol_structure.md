## daily_vol_structure — do daily straddles and 1x2 ratios on QQQ and SMH pay, and do results move with volume or price?

<!-- outcome:start -->
> Latest outcome: not yet run.
<!-- outcome:end -->

_Registered 2026-11-06._

**STATUS: ACCEPTED BY DEFAULT 2026-11-06 on the drafter's recommended defaults, under the standing
[2026-10-09 ruling](../../current.md#2026-10-09--parked-drafts-accepted-by-default-and-run). A
revisit after a result is a NEW registration, never an edit.**

A second reader reviewed the draft three times on 2026-11-06, before any outcome was read. Its findings are
folded into the rules below.

## The question

We open a long straddle and 1x2 ratios on QQQ and SMH at every session's next close, and close them
2 or 5 sessions later. We ask two things:

1. Does any position make money on average, with no filter?
2. Does its P&L change with price, volume or volatility known the day before?

A filter must show up on the first 60% of dates, then hold on the last 40%. A pass earns only a
forward test, and nothing ships.

**The analysis page cannot be tested on these dates**, because almost all its labels were written
after the fact. Its cells print as description. Three of its market-wide features get a separate
read on labels written at the time. That read prints `UNDERPOWERED`, meaning too few dates to judge,
until it has 60 such dates in 6 blocks, with 12 rows per arm. Those 60 dates allow a test and no more: a
`CANDIDATE` there needs the position's arm to hold 63 rows, which takes far more dates.

**The most likely result is that no filter passes.** The sample detects only large effects.

- **Back ratio:** sell 1 ATM, buy 2 further out.
- **Front ratio:** buy 1 ATM, sell 2 further out.
- **Cell:** a cell is one feature on one series. Its top and bottom arms are the rows with high and low
  values of that feature.
- **LIVE:** a label written within a day of its date. **RETRO:** written more than a week later.
- **BH (Benjamini-Hochberg):** holds the expected share of false finds among those it passes.
- **Holm:** tightens each p for the number of series tested.

## What this study is not

- **Not the SPY proposal.** [`next-steps.md`](../../next-steps.md#waiting-on-the-operator) item 18
  asks whether SPY straddles pay after volatility has started expanding. That stays a separate
  question.
- **Not a return to an old finding.** On
  [2026-09-04](../../archive/18-hedge-programme-exit-basis-and-text-loop.md) the repo found that play
  text did not predict the plays' own results. This study has another target, a daily mechanical
  structure, and the operator asked for it.
- **Not sizing guidance.** A front call ratio has no cap. A fixed 2- or 5-session exit limits the
  losses the study can observe.
- **Not a ship.** Any production change goes back to the operator.

## Definitions

### Structures and tenors

| Label | Structure |
|---|---|
| S | Long ATM straddle: +1 ATM call, +1 ATM put |
| RC, back | Call ratio: −1 ATM call, +2 wing calls at spot × (1 + x) |
| RC, front | +1 ATM call, −2 wing calls |
| RP, back | Put ratio: −1 ATM put, +2 wing puts at spot × (1 − x) |
| RP, front | +1 ATM put, −2 wing puts |

T30 and T7 are labels. The true DTE at the fill differs, and the expiry-cycle clause below reads it.

| Tenor | Expiry | Minimum at fill | True DTE at the fill | Exit |
|---|---|---|---|---|
| T30 | Standard monthly nearest 30 DTE | 21 calendar days | 21 to 53, median 35 | 5 sessions after the fill |
| T7 | Friday weekly nearest 7 DTE | 5 calendar days | 6 to 11, median 9, set by the weekday | 2 sessions after the fill |

DTE counts from the fill. A tie goes to the earlier expiry. A Friday that is not a session moves to
the Thursday before it.

| Wing x | T30 | T7 |
|---|---|---|
| QQQ | 5% | 2.5% |
| SMH | 9% | 4.5% |

SMH is scaled by the median 20-day realized vol ratio printed at planning (0.313 / 0.178). T7 is
scaled by √(7/30). The values are rounded and fixed here.

### Dates

- **D.** The signal date, a session in the window. The calendar is the SPY session table
  (`mechanical_baseline.load_closes`).
- **Fill.** The session after D.
- **Exit.** The fixed number of sessions after the fill.

### One signed series

On the same strikes, a front ratio is exactly minus a back ratio at mid, before commission. So each
ratio has one stored series, `y`, the back ratio's gross P&L as a share of spot. The front ratio's
gross P&L is `−y`. Every correlation runs once, on `y`, and reads with the opposite sign for the
front ratio. There are 12 series: 2 tickers × 2 tenors × 3 structures. They have 20 sides.

### Unit

- **The unconditional read and the arm means.** Net P&L as a share of spot. A front call ratio has no
  defined max loss, so R cannot be the unit. Spot is D's close.
- **Cell statistics.** Gross of commission, because they compare two arms and the commission cancels.
  The tradability clause reads the net arm means.
- **R.** P&L over max loss at expiry, printed where risk is defined: S, both back ratios and the
  front put ratio. Never graded.

### Features, fixed here

Every feature in this first table is known at D's close. A missing input leaves the row out of that
feature's cells only.

| Feature | Definition | Kind |
|---|---|---|
| `ret1`, `ret5`, `ret20` | Close-to-close return over 1, 5, 20 sessions | rank |
| `dist50` | Close ÷ its 50-session average − 1 | rank |
| `range_atr` | Day's high − low ÷ the 20-session mean true range | rank |
| `evol` | VIX at or above 30, or up 25% or more in 5 sessions (`E-VOL`, `lib/mech_regime.py`, unchanged) | cut 0 / 1 |
| `rv5_rv20` | 5-session realized vol ÷ 20-session realized vol | rank |
| `iv_rv20` | ATM IV on D − RV20, both in vol points | rank |
| `iv_chg5` | ATM IV on D − ATM IV 5 sessions earlier | rank |
| `und_vol` | Share volume ÷ the mean of the prior 20 sessions | rank |
| `opt_vol` | ATM option volume ÷ the mean of the prior 20 sessions, 15 of them present | rank |
| `qqq_prem` | QQQ call + put premium in the daily flow totals tab ÷ the mean of the prior 20 sessions, 15 present; QQQ cells only | rank |
| `qqq_cp` | QQQ call premium ÷ put premium in the same tab; QQQ cells only | rank |

The analysis features come from the analysis page's market-wide row (`mkt_`) and the ticker's own row
(`tk_`). They print as description, and only the three marked below are graded, in the LIVE read.

| Feature | Definition | Kind | LIVE read |
|---|---|---|---|
| `mkt_dir` | Market direction: BULL 1, RANGE 0, BEAR −1 | cut 0 / 1 | yes |
| `mkt_vol` | Market vol state: C-VOL 0, L-VOL 1, H-VOL 2, E-VOL 3 | cut 2 / 3 | yes |
| `mkt_risk` | RISK-ON 1, RISK-OFF 0 | cut 0 / 1 | |
| `mkt_hp` | The hedge-pressure token `HP` is present | cut 0 / 1 | |
| `mkt_hp_score` | The hedge-pressure score in the market-wide signal, 0 to 100 | rank | yes |
| `mkt_flow` | `[FLOW]` items in the market-wide signal | cut 2 / 4 | |
| `tk_dir` | The ticker row's direction | cut 0 / 1 | |
| `tk_vol` | The ticker row's vol state | cut 2 / 3 | |
| `tk_flow` | `[FLOW]` items in the ticker row's signal | cut 3 / 4 | |

- **ATM IV and option volume.** The mean IV, and the summed `Volume`, of the D row of that session's
  own ATM call and put. An IV of 0 is missing.
- **Top and bottom.** Top is x ≥ hi and bottom is x ≤ lo. Top minus bottom is the difference of the
  two arms' mean `y`.
- **Cuts are frozen on discovery rows.** A rank feature's lo and hi bound its bottom and top rank
  tercile on discovery rows. A discrete feature's cuts are the fixed levels above. Confirmation, the
  forward reads and every rotation use the same cuts, so the rule is one a trader could have held.

_Resolved at build (2026-11-06):_ a discrete feature takes fixed cuts, not rank terciles.
`forward_drawdown.tercile_contrast` breaks ties by position, so on a binary feature its groups would
be arbitrary.

_Resolved at build (2026-11-06):_ the plan's "about 15" features is 22 on QQQ and 20 on SMH, once
each regime field and each `[FLOW]` count is its own feature. That makes 252 cells: 144 graded and 108
analysis. The census found no `risk` or `HP` token in any ticker row's head, so those two are
market-wide only.

### The analysis page, parsed deterministically

No model call. Rows are from the current prompt version (era v4, through `lib/era.py`). Signal dates
from 2026-09-23 are withheld for a later test.

The text is parsed by `market_read.parse_label`, unchanged.

| Field | Rule |
|---|---|
| Head | The text before the first of `—`, `" - "`, `". "`, `": "` or `" ("` |
| Direction | The first of BULL, BEAR, RANGE in the head |
| Vol state | The first of E-VOL, H-VOL, L-VOL, C-VOL in the head |
| Risk, hedge pressure | RISK-ON or RISK-OFF; `HP` as a whole token |

- **Unparsed fields.** A field with no token is missing, and is never imputed. First words such as
  `spot`, `Below`, `PxVec`, `Rich`, `nan` or a blank parse to no direction. A head reading `E-VOL`
  alone has a vol state and no direction.
- **A date with two rows for one ticker.** It leaves the ticker's analysis features.

**The hedge-pressure score.** The first of these forms, tried in this order, with a value from 0 to
100. Anything else is missing.

| Order | Form (case-insensitive) |
|---|---|
| 1 | `hedge[- ]pressure[^\n.]{0,40}?(\d{1,3})\s*/\s*100` |
| 2 | `hedge[- ]pressure(?:\s+score)?\s+(\d{1,3})\b` |
| 3 | `(\d{1,3})\s*/\s*100[^\n.]{0,20}?hedge[- ]pressure` |

### When a label was written

Lag is `created_datetime[:10]` minus `date`, in days, by `market_read.lag_bin`.

| Lag bin | Lag |
|---|---|
| LIVE | 0 or 1 day |
| NEAR | 2 to 7 days |
| RETRO | more than 7 days |
| UNKNOWN | blank, or negative |

`created_datetime` is the local clock of the machine that ran the pipeline
(`scripts/analysis_pipeline/core.py:447`), which is UTC+8. All 28 market-wide LIVE rows in the window
carry lag 1, at hours 08 to 15 plus one at 23. In UTC+8 the US close of D+1 falls at 04:00 or 05:00 on
the next calendar day, so each of those rows precedes its fill. It follows D's close. So a LIVE label
is known by the fill, and not by D's close.

## Dependencies

- `scripts/backtest/simulate.py`: `entry_day_fill`, `_monotonicity_violation`. Imported, never copied.
- `selloff_put_diagonal.leg_mark`: the exit mark, on the shared `_snap_asof`, `_is_junk_quote` and
  `junk_day_mark`.
- `index_vrp.realized_vol`.
- `mechanical_benchmark`: `grid_around`, `listed_by`, `monthly_expiries`.
- `market_read`: `parse_label`, `lag_bin`. `regime_map.bh_q`. `selloff_put_diagonal.holm`.
- `lib/forward_drawdown.py`, `lib/pbo.py::cscv`, `lib/era.py`, `lib/underlying.py`.
- `lib/mech_regime.py::MechLabeler` on `backtests/mech_regime/spy_vix_daily_full.csv`, unchanged.
- `scripts/backtest_study/lib/harness.py` is not read. No Black-Scholes or other model price exists
  anywhere in this study.

## Population and basis, fixed here

- **Underlyings.** QQQ and SMH, graded separately.
- **Window.** Signal dates 2024-03-15 to 2026-09-22: the option cache starts 2024-03, and the holdout
  starts 2026-09-23. That is 632 sessions on the SPY table. The plan's "about 635" was an estimate.
- **Forward.** Signal dates from 2026-09-23.
- **Discovery.** The first 60% of the window's dates, in order: 379 sessions, through 2025-09-18. A
  row whose exit falls on or after 2025-09-19 also leaves discovery. Discovery reads only the 144
  graded cells.
- **Confirmation.** The last 40%: signal dates from 2025-09-19, 253 sessions. There is no k-fold.
- **Era.** `era.resolve_paths` and `era.enforce` on the exports. An era other than v4 refuses (exit
  3). Price, volume and option series belong to no era. The report's header says so: `analysis features
  are era v4; price, volume and option series are era-free`.
- **Era floor.** `era.require_dates` refuses fewer than 60 market-wide dates in the window (exit 2).
- **Holdout.** `era.drop_sealed(rows, date_key="date")`, with no reader, on analysis rows and the
  daily flow totals tab. This study is not in `era.SEALED_READERS`. A trade's exit may fall after
  2026-09-23, because the holdout binds signal dates.

### Strikes

- **Spot.** D's close from `lib/underlying.py`. QQQ and SMH have no split inside the window.
- **Step, fixed per ticker and tenor.** QQQ $1 on both tenors, SMH $2.50 on both tenors.
- **ATM.** The multiple of the step nearest spot with both a call and a put listed by D. The fill is a
  session later, so ATM drifts. The report prints |ATM ÷ spot − 1| at D and at the fill, per series.
- **Wing.** The multiple of the step nearest spot × (1 ± x), of its own type, listed by D, strictly
  outside the ATM strike. Otherwise the trade drops as `wing_degenerate`.
- **The walk, nearest first, ties to the lower strike.**
  1. A cached contract with a row on or before D: chosen. This comes first, so a later skip-list entry
     cannot move a strike on a date where a file has real rows.
  2. A contract Barchart confirmed does not exist (the skip-list, on evidence): step on.
  3. A cached contract with no such row, in a file written on or after 2026-09-09, when the fetch-range
     fix landed: not listed yet, so step on.
  4. The same in an older file: it may be a shallow fetch, so the trade awaits a re-fetch. A repeated
     empty re-fetch would keep its trade awaiting, visibly, and is handled by hand if it happens.
  5. An uncached contract: the trade awaits a fetch.
- **A dropped leg drops the day for that ticker and tenor.** A failed wing also removes that day's
  straddle.

_Resolved at build (2026-11-06):_ the step is fixed and the cache never changes the grid, so a later
fetch by any study cannot move a strike. `mechanical_benchmark.grid_step` used $5 above a $250 spot
unless cached strikes were finer, which put ATM up to 1% from spot. The steps are the finest spacing in
the cached file names: QQQ $1, SMH $2.50.

_Resolved at build (2026-11-06):_ an expiry is `not listed` only on a weekly, and only when three
distinct strikes within 2% of spot are on the skip-list. A monthly is always walked, because a missing
strike is not a missing expiry: QQQ's 2024-07-19 monthly has skip-listed $1 strikes. A cached file never
proves it, because older fetches hold shallow histories. The report prints the count.

### Pricing and costs

- **Fill.** Every leg at the fill day's own closing mid, through `entry_day_fill`, on one clock. A leg
  with no row that day drops the trade. No leg moves to another day.
- **Junk quotes at entry.** A wide two-sided quote fills at its mid, and a quote with no bid is refused
  (`junk_entry_quote`). A pair priced against strike order is refused (`non_monotonic_entry_quote`).
- **Exit.** `leg_mark` on the exit session: the closing mid, or on a junk quote its `Latest` if it
  traded, or ask ÷ 2 with no bid. A leg with no row that day drops the row (`no_exit_quote`), and so
  does a carried mark (`stale_exit_mark`).
- **Credit entries.** A credit entry closes on the same fixed exit as a debit entry. Production's
  credit-exit rule does not apply.
- **Commission.** $0.65 per contract per side: 4 sides on S, 6 on a ratio.
- **Strict touch.** Each side's own round trip: a sale at the bid, or 0 with no bid; a purchase at the
  ask. There is no fallback, so a wide quote stays wide. Printed for each side and never graded,
  consistent with the operator's mid-fill ruling.
- **Model prices.** None.

_Resolved at build (2026-11-06):_ every leg takes `entry_day_fill(row, +1)`, whichever side holds it.
That returns the closing mid for a normal or wide quote and refuses a quote with no bid. The side-aware
call would fill a sold junk leg at its bid and a bought one at its mid, which breaks Front = −Back.
Each series prints its share of rows with a wide leg. A front-only print shows the side-aware fill,
`entry_day_fill(row, -1)` on each sold leg. `y` stays on the mirror.

## Plan-time observations, disclosed

Disclosures follow. To skip them, go to [What it compares](#what-it-compares).

No QQQ or SMH option outcome has been read. No option P&L, mid change, IV path or straddle cost was
computed on those tickers, as a smoke test or otherwise. The figures below come from analysis text,
session calendars, underlying closes and volumes, `Price~` and file names.

### What the second reader read

- `Book.coverage()` listing counts for cached QQQ and SMH files: 65 trades countable, and no price.
- QQQ and SMH file dates and listing counts only, on the re-check.
- Junk-quote proxy shares from other tickers' cached quotes, on the re-check.
- Session calendars and `E-VOL` labels.
- Analysis-row dates and lags.
- Skip-list names.
- `qqq_prem` medians.
- One SPY option file, for its column format.
- A textbook power estimate that uses no quotes, and synthetic simulations.

### What planning printed

| Item | Figure |
|---|---|
| Market-wide dates in the window | 258 |
| QQQ dated rows in the export | 92 (78 in the window) |
| SMH dated rows in the export | 130 (110 in the window) |
| RV20 median, QQQ, at planning | 0.178 |
| RV20 median, SMH, at planning | 0.313 |
| RV20 median, window to 2026-08-11, this census | QQQ 0.179, SMH 0.333 |
| Median share volume, window to 2026-08-11 | QQQ 42,393,600; SMH 7,379,000 |

The wing scale keeps the plan's 0.313 / 0.178. The census's higher SMH figure is disclosed, and no
wing moved.

**Contract counts.** Planning estimated them from OHLC closes: T30 about 1,550 on a $5 grid, about
2,900 on a finer one; T7 about 3,000, rough and unmeasured. The fetcher's dry run on 2026-11-06, on the
fixed steps, named 5,359 contracts, 48 of them re-fetches. It held back 116 trades, because the OHLC
then ended 2026-08-11.

### Regime first words, whole export

| Row | First words and counts |
|---|---|
| Market-wide | BULL 168, RANGE 120, BEAR 13 |
| QQQ | BULL 48, RANGE 33, BEAR 2, blank 2; once each: `spot`, `Below`, `BEAR-leaning`, `RANGE/soft`, `about`, `BULL-tilt`, `RANGE→BEAR` |
| SMH | BULL 63, BEAR 28, RANGE 22, blank 3; twice each: `PxVec`, `E-VOL`, `Rich`, `Spot`; once each: `BEAR-lean`, `E-VOL:`, `Semis`, `BEAR-tilt`, `Crowded`, `Extended` |

### Token census, window

| Field | Market-wide | QQQ | SMH |
|---|---|---|---|
| Direction | BULL 135, RANGE 110, BEAR 13 | BULL 39, RANGE 34, BEAR 3, none 2 | BULL 45, BEAR 30, RANGE 21, none 14 |
| Vol state | L 156, E 67, C 27, H 8 | L 48, E 14, C 6, H 1, none 9 | E 53, L 33, H 2, none 22 |
| Risk | ON 155, OFF 98, none 5 | none 78 | none 110 |
| `HP` | 119 of 258 | 0 | 0 |
| `[FLOW]` items | 1 to 6, most 3 | 2 to 5 | 2 to 7 |
| Lag: LIVE, NEAR, RETRO | 28, 2, 228 | 10, 1, 67 | 17, 1, 92 |

The hedge-pressure forms return a score on 203 of the 258 market-wide rows. 222 rows mention the phrase.

### Why the analysis page cannot be answered on these dates

- **Discovery rows are all RETRO:** market-wide 133 of 133, QQQ 42 of 42, SMH 36 of 36. Those labels
  came from a model whose training data may cover those months
  ([record](../../current.md#the-regime-labels-were-mostly-written-after-the-fact)).
- **LIVE rows are few, and all late.** Every LIVE date is from 2026-08-11 on. LIVE holds 28 market-wide
  dates in the window against a floor of 60, and no market-wide BEAR label is LIVE.
- **Hindsight would contaminate the test.** BH loosens as rejections rise, so a hindsight hit would
  lower the bar for every other cell.

### Data checks

- **`E-VOL` input.** `spy_vix_daily_full.csv` runs 2023-06-01 to 2026-10-22 and labels all 632
  sessions: L-VOL 494, H-VOL 81, E-VOL 57. It is market-wide and applies to both tickers.
- **Daily flow totals tab.** 610 window dates, all on sessions. 601 carry QQQ premium. Its raw QQQ
  premium median doubles across the window, from about $113M to about $222M, which is why `qqq_prem` is
  a ratio.
- **Off-calendar.** One date in each of the market-wide, QQQ and SMH rows (a non-session) leaves the
  study.
- **`Price~` against the closes.** Over 974 SMH days and 995 QQQ days, the ratio is 1.0 inside the
  window. SMH reads 2.0 before 2023-05-05, a split before the window. QQQ's one bad print is 2025-11-28.
- **OHLC.** Both files end 2026-08-11 at registration, so the run reads `NOT BUILT` until they are
  refreshed.

### Prior prints

- **The 23-onset print, 2026-11-06.** While counting `E-VOL` onsets, SPY and VIX moves after 23 onsets
  from 2023-06 to 2026-09-22 were printed. VIX fell in 15 of the 23
  ([entry](../../current.md#2026-11-06--long-straddles-and-backspreads-after-a-vol-expansion-untested-one-spy-study-proposed)).
  No option price was read, and it shaped no choice here.
- **Earlier straddle and short-vol verdicts.** `earnings_vol`, `index_vrp` and `hedge_structure` are
  known. They used other names and dates, and none reads QQQ or SMH daily.

### Expected result, before any run

**The ranked list is most likely empty.** These are synthetic and textbook estimates, using no quotes.
They flatter power, because the simulations behind them used p-values that ran too small.

| Test | About 80% power needs |
|---|---|
| Discovery, lone cell, T30 | Spearman about 0.35 |
| Discovery, lone cell, T7 | Spearman about 0.25 |
| Confirmation test alone, T30 | Top minus bottom about 0.8 SD of 5-day P&L |
| Confirmation test alone, T7 | Top minus bottom about 0.6 to 0.65 SD of 2-day P&L |
| Whole bar on a zero-mean series, T30 | Top minus bottom about 0.8 to 0.9 SD |
| Whole bar on a zero-mean series, T7 | Top minus bottom about 0.7 SD |

The two "whole bar" rows are a synthetic run with no commission: the circular-shift test at p<.05, the
position's arm mean clearing zero, and the cycle clause. The cycle clause cost almost nothing in that
run, and the arm-mean clause cost up to 0.1 SD. A textbook estimate puts the T30 confirmation figure near
0.5% of spot per trade, or about 12% of a QQQ straddle's premium. Every analysis cell is expected to stay
`RETRO-ONLY`, and the LIVE read `UNDERPOWERED`, including after 60 LIVE dates on any test that passes on an
arm under 63 rows.

**The exit-drop limit is expected to bite.** A junk-quote proxy on other tickers' cached quotes runs 2%
to 30%, so many SMH ratio cells may go over 5%. Over the limit a `CANDIDATE` or `CONTRARY` can stand if it
is unchanged with dropped rows closed at the adverse touch. Every `NULL` over the limit reads
`UNDERPOWERED`, so those cells are expected to say too little data, not no effect.

## What it compares

| Object | Object type | What it reads | Role |
|---|---|---|---|
| 12 series, 20 sides | cell | Mean net P&L per side, no condition | Unconditional read, Holm across series |
| 144 price, vol and volume cells | cell | Spearman and top minus bottom | Discovery, then confirmation |
| 108 analysis cells | descriptive cut | Top minus bottom on ALL, LIVE and RETRO rows | Printed as `RETRO-ONLY`, outside every test and tally |
| 36 shortlist cells | cell | `mkt_dir`, `mkt_vol`, `mkt_hp_score` × 12 series, on LIVE rows | The LIVE read, with its own BH |
| Strict touch, R | descriptive cut | Per side, and per arm for ranked cells | Printed only |
| Worst trade, worst 21 rows | descriptive cut | Per side | Printed only |
| Other ticker, sell-off windows cut | descriptive cut | The same contrast's sign | Printed robustness lines |
| PBO | descriptive cut | The ranked cells | Printed only |

## How it is judged

### 1. Unconditional

- **Figures.** For each side: mean net P&L with a block-bootstrap CI over the whole window, and the
  same mean on discovery rows, on confirmation rows, and with the sell-off windows cut.
- **Block.** 21 consecutive rows, at least the hold of both tenors. Seed 20261106.
- **Multiplicity.** Holm across the 12 series. A side's p is two-sided, from 10,000 block draws. A
  series enters on its smaller side's p, and its other side is never adjusted below that.

_Resolved at build (2026-11-06):_ the CIs come from `forward_drawdown.block_bootstrap`, and the p from the
same resampling.

### 2. Discovery, first 60% of dates

- **Statistics.** Spearman, and top minus bottom, for each of the 144 cells.
- **p-value.** z is Spearman over the SD of Spearman under circular shifts of the feature against the
  outcome, `forward_drawdown.circular_shift_null`, minimum shift 21, 1,000 draws. The p is two-sided
  normal. A rotation keeps both series' own autocorrelation.
- **BH.** Across every cell above its floor, holding the expected share of false finds at 10%.
- **Ranked list.** The cells at q ≤ 0.10. Only these move on. The whole list is printed.
- **Nothing later is read.** A discovery row closes before 2025-09-19, and no feature reads past D.

_Resolved at build (2026-11-06):_ the test divides by the rotated statistics' SD and does not centre on
their mean. On a persistent synthetic null at 1,000 draws it read p<.05 on 6.4% of runs, against 9.7%
centred and about 26% for the block bootstrap it replaced.

### 3. Confirmation, last 40% of dates

Only the ranked cells. The same null, with the contrast on discovery's frozen cuts, and BH at q ≤ 0.05
across the ranked list, so a lone ranked cell needs p ≤ .05. See
[Bar for a candidate](#bar-for-a-candidate).

For each ranked cell the report prints:

- **Arm means.** Net at mid and at the strict touch, for the top arm, the bottom arm and all rows, per side.
- **The position.** Its side, arm, net mean at mid, p and strict touch.
- **Tradable at mid.** Yes or no, in the banner.
- **The cycle.** Top minus bottom and row count in each DTE bucket or weekday, and the feature's rank
  correlation with DTE.
- **Exit drops.** The share of the series and of each arm, and whether the verdict held at the adverse touch.
- **Robustness lines.** The sign on the other ticker on the same dates, and the sign with two sell-off
  windows removed: signal dates 2025-03-01 to 2025-04-30 and 2026-02-01 to 2026-04-30, removed because a
  single sell-off could carry a result. These lines are not replication and are not in the bar. On
  synthetic nulls they passed 77% to 94% of the false hits, and nine features use one identical x on
  both tickers: `evol`, the six `mkt_*` and, for this line, `qqq_prem` and `qqq_cp`, whose QQQ value is
  read against SMH's series.

### PBO, printed only

PBO is the chance that the best in-sample choice ranks below the median out of sample. It prints through
`lib/pbo.py::cscv`, S = 16, on total P&L, over the ranked cells only.

- **Columns.** One per ranked cell, in discovery's sign: +y in the top arm, −y in the bottom arm, 0
  otherwise. Each column is scaled to unit variance.
- **Rows.** Each window session, with zero rows padded at the head to divide evenly into 16 blocks.
- **A lone ranked cell gets no PBO**, because it has nothing to be ranked against. None of this affects a
  verdict.

_Resolved at build (2026-11-06):_ PBO left the bar. One study-wide figure over mirrored columns sat near a
coin flip on synthetic nulls, and a real effect in a low-variance series did not raise it. The standing
rule that every candidate gets a PBO read and a forward grade is met by this print and the forward grade.

### The LIVE read, forward

The route for the analysis-page question. Frozen now, before any outcome.

- **Cells.** `mkt_dir`, `mkt_vol` and `mkt_hp_score` × the 12 series: 36 cells.
- **Rows.** LIVE rows only, in the window and, once the holdout opens and their legs are fetched, after it.
- **Test.** The circular-shift null on top minus bottom, with discovery's frozen cuts. BH at q ≤ 0.05
  across the cells at their floor, the same bar as confirmation.
- **It is its own forward test.** A LIVE `CANDIDATE` gets a banner line, a headline and a forward line
  saying so, and no further grade.
- **Limit.** LIVE rows stop accumulating if the analysis pipeline is retired, which is the direction the
  operator set on 2026-10-23 (see [`current.md`](../../current.md#2026-10-26--mechanical_baseline-registered-a-weekly-spy-call-spread-as-the-replacement-candidate)). The
  read then stays `UNDERPOWERED`.

## Gates

**The coverage gate.** It is all-or-nothing, and it comes before any price is read.

- Every trade in all four ticker and tenor pairs must be built, or dropped on evidence. One awaiting
  trade anywhere keeps it shut.
- Both OHLC files must reach 2026-09-22.
- `Price~` on built trades' D rows must agree with the close. A run of 3 or more observations more than
  10% off refuses, because the closes would be on another split basis. A shorter run is a bad print,
  counted only.

While it is shut the run prints `NOT BUILT — AWAITING SCRAPE` and contract counts per ticker and tenor,
and writes nothing. `Book.price` and `Book.option_row` raise until it opens. A partly cached leg set
therefore cannot produce a partial figure.

**Power floors, per cell.** A cell below its floor reads `UNDERPOWERED`, on the dates it is read on.

| Floor | Value |
|---|---|
| Dates | 60 usable rows |
| Calendar blocks | 6 distinct `session index // 21` |
| Each arm | 12 rows in 3 calendar blocks |
| Unconditional | 60 rows in 6 calendar blocks |

A coverage gap on T7, or anywhere else, reads `UNDERPOWERED`. It is never filled with another price.

**Exit drops.** A junk or missing exit quote depends on where spot went after the fill, so these drops
act after the outcome and can bias `y`. Every series prints its share, the drops split by the underlying's
direction from fill to exit, and each side's mean with dropped rows closed at the adverse touch.

- **The adverse touch.** A long leg closes at its bid or 0, a short leg at its ask. A cell closes each
  dropped row against its own sign: the low figure in the arm its sign favours, the high figure in the
  other.
- **The limit.** 5% of a series, or of an arm on the dates and lag bin read.
- **Over the limit.** Only `CANDIDATE` or `CONTRARY` can stand. Each is re-graded with the dropped rows
  included, and stands only if it is unchanged and every dropped row in an arm has an ask to bound its
  short legs. Anything else reads `UNDERPOWERED`. A `NULL` cannot stand, because closing dropped rows
  against the cell's sign can only weaken a result, so a `NULL` would nearly always hold.
- **Everywhere.** The rule applies to the unconditional read, confirmation, unranked cells in the tally,
  the LIVE read and both forward reads.

## Bar for a candidate

**A cell.** All of these must hold, on the confirmation dates:

1. **Confirmation.** On discovery's frozen cuts, top minus bottom has discovery's Spearman sign, at BH
   q ≤ 0.05 across the ranked list on the circular-shift null.
2. **Tradable at mid.** Take the position with the larger net mean in its arm: for S, long in the higher
   arm; for a ratio, the back ratio in the higher arm or the front ratio in the lower arm. Its mean must
   clear zero at p<.05 on 10,000 block draws. A positive mean alone is not enough, because at mid front =
   −back, so one of a ratio's two positions looks positive whenever the arms differ. Its arm must hold 63
   rows, three full blocks. Below that the cell reads `UNDERPOWERED`.
3. **Expiry cycle.** The row-weighted average of the bucket contrasts has discovery's sign and is at least
   half the overall contrast, with at least two readable buckets. T30's buckets are DTE 21 to 30, 31 to
   38, and 39 to 53. T7's are the fill's weekday. A bucket is readable when each arm has 5 rows.

Clause 2 is not a strict 5% test, and its false-pass rate depends on arm size. It is a further check on a
confirmed contrast. Synthetic null pass rates:

| Rows in the arm | One position | Best of two (a ratio) | Standing |
|---|---|---|---|
| 12 to 21 | about 50% | about 75% | Below 63: not read |
| 22 to 42 | 27% | 47% | Below 63: not read |
| 43 to 63 | 12% to 14% | 22% to 25% | Read only at exactly 63 |
| 84 | 11% | 21% | Read |
| 126 | 7% | 14% | Read |

**What the 63-row limit implies.**

- **`evol`.** Its top arm holds 17 confirmation dates. A position held in that arm cannot reach `CANDIDATE`
  on these dates. Only a position in the other arm, the sessions without `E-VOL`, can.
- **The LIVE read.** No arm reaches 63 rows on the 28 LIVE dates in the window, so no LIVE cell can reach
  `CANDIDATE` there. The floor of 60 dates only lets the read print a test: a cell then reads `NULL` if the
  test fails and `UNDERPOWERED` if it passes on a thin arm. By arithmetic, a tercile arm reaches 63 rows
  near 190 LIVE dates. Direction and vol-state arms depend on how often each label prints.

Clause 3 exists because a feature tied to DTE and a P&L tied to DTE correlate with no signal. The fixed
T30 wing moves from about 1.2 sigma at 21 DTE to about 0.75 sigma at 53 DTE, and the same calendar
repeats on both date sets and both tickers. It reads an average because requiring the sign in every bucket
failed a real effect about half the time on T7. It can miss a gradient inside one wide bucket, so the
report prints every bucket and the feature's correlation with DTE.

**The unconditional read**, per side. Holm-adjusted p below 0.05, with a positive mean overall, on
discovery rows, on confirmation rows and with the sell-off windows cut.

## Verdicts, worded now

Three headline lines come first: `Pays every day: <sides that are CANDIDATE, or none>`, `Moves with a
known feature: <cells, or none>` and `LIVE read, its own forward test: <cells, or none>`.

**A cell.** The first matching row wins.

| Token | When |
|---|---|
| `UNDERPOWERED` | Below its floor on the dates read, or the statistic is NaN, or over the exit limit unless an unchanged `CANDIDATE` or `CONTRARY` stands |
| `NULL` | Above its discovery floor and not on the ranked list |
| `NULL` | Ranked, and q > 0.05 on confirmation |
| `CONTRARY` | Ranked, q ≤ 0.05 on confirmation, on the opposite sign from discovery |
| `UNDERPOWERED` | Ranked and confirmed, and the position's arm has fewer than 63 rows |
| `NULL` | Ranked and confirmed, and the position's net mean does not clear zero at p<.05 |
| `UNDERPOWERED` | Ranked, confirmed and tradable, with fewer than two readable cycle buckets |
| `NULL` | Ranked, confirmed and tradable, and the cycle clause fails |
| `CANDIDATE` | Every clause holds. It earns only a forward grade |

A `NULL` means no large effect, at the sizes under [Expected result](#expected-result-before-any-run). It
does not mean no effect.

**The unconditional read**, per side.

| Token | When |
|---|---|
| `UNDERPOWERED` | Below its floor, or over the exit limit unless an unchanged `CANDIDATE` or `CONTRARY` stands |
| `CONTRARY` | Holm-adjusted p below 0.05 on a negative mean |
| `CANDIDATE` | Its bar holds. It earns only a forward grade |
| `NULL` | Otherwise |

Two caveats print with this table, word for word:

- On a front ratio, `CANDIDATE` means a positive sample mean only. It says nothing about tail loss,
  margin or return on capital.
- A long-straddle `CONTRARY` is not evidence for selling straddles, because no such side is graded.

**An analysis cell** prints `RETRO-ONLY`, and is in no tally.

**The LIVE read.**

| Token | When |
|---|---|
| `UNDERPOWERED` | Below 60 LIVE dates in 6 blocks, or below 12 rows in an arm, or over the exit limit unless an unchanged `CANDIDATE` stands |
| `NULL` | q > 0.05 across the shortlist |
| `UNDERPOWERED` | q ≤ 0.05, and the position's arm has fewer than 63 rows |
| `CANDIDATE` | q ≤ 0.05, and the position's net mean clears zero at p<.05 on an arm of 63 rows |
| `NULL` | Otherwise |

**FORWARD.** Each `CANDIDATE`, cell or unconditional side, on signal dates from 2026-09-23. A side reads
its mean. A cell reads its frozen-cut contrast on the null. The floors are the same. `STILL-OPEN` until
they are met; then `CANDIDATE`, `CONTRARY` or `NULL` at p below 0.05, with the cell's tradability clause,
its 63-row arm (`UNDERPOWERED` below that) and the exit-drop rule. Forward legs need their own fetch. A `qqq_*` cell waits until the holdout opens.

**The banner.**

```
>>> daily_vol_structure <ticker> <tenor> <structure> <feature>: CANDIDATE | CONTRARY | NULL | UNDERPOWERED | tradable at mid: yes | no <<<
>>> daily_vol_structure UNCONDITIONAL <ticker> <tenor> <structure> <side>: CANDIDATE | CONTRARY | NULL | UNDERPOWERED <<<
>>> daily_vol_structure LIVE <ticker> <tenor> <structure> <feature>: CANDIDATE <<<
```

Only the ranked cells print a banner line. The rest print as a tally. If a `CANDIDATE` prints, two
independent analysts re-grade it before anyone calls it a finding.

## Anti-tuning

- **Fixed here:**
  - both tickers, both tenors, the wings, the strike steps and the exits;
  - the feature list, its cuts and the three LIVE-read features;
  - the hedge-pressure forms, the 60/40 split and its first confirmation date;
  - the block, the minimum shift, the seed, q ≤ 0.10, the DTE buckets;
  - q ≤ 0.05 at confirmation, the cycle clause's one-half;
  - the floors, the 5% exit limit and the verdict words.
- No feature, tenor, wing or hold is added on a look at the results.
- Strict touch, R, PBO, RETRO, the robustness lines and the worst figures are printed as they fall, and
  none re-grades anything.
- A window, feature or cell is never dropped after an outcome prints. Any change is a new registration.

## What could ship

Nothing ships from this study.

- A `CANDIDATE` earns a forward grade and files "to be tested" in
  [`deployment-evidence.md`](../../deployment-evidence.md). It changes no production code.
- `CONTRARY`, `NULL`, `UNDERPOWERED` or `RETRO-ONLY` changes nothing.
- Any production change goes back to the operator.
