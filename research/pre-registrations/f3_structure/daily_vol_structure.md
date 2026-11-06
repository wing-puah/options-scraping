## daily_vol_structure — do daily straddles and 1x2 ratios on QQQ and SMH pay, and do results move with volume, price or the analysis page?

<!-- outcome:start -->
> Latest outcome: not yet run.
<!-- outcome:end -->

_Registered 2026-11-06._

**STATUS: ACCEPTED BY DEFAULT 2026-11-06 on the drafter's recommended defaults, under the standing
[2026-10-09 ruling](../../current.md#2026-10-09--parked-drafts-accepted-by-default-and-run). A
revisit after a result is a NEW registration, never an edit.**

## The question

The operator wants to enter a straddle, a front ratio and a back ratio on SMH and QQQ every day,
because those names move often. Two questions follow:

- **Does it pay every day?** The mean net P&L of each structure, with no condition.
- **Does the result move with a feature known beforehand?** Volume, price, realized and implied
  vol, and the analysis page's regime and signal text.

The study graded here scans about 250 feature × series cells on overlapping trades. So discovery
and confirmation sit on separate dates, and a `CANDIDATE` earns only a forward grade.

## What this study is not

- **Not the SPY `E-VOL` proposal.** [`next-steps.md`](../../next-steps.md#waiting-on-the-operator)
  item 18 stays open as a separate question.
- **Not a re-opening of the text thread.** The
  [2026-09-04 closure](../../archive/18-hedge-programme-exit-basis-and-text-loop.md) ended text as
  an edge search on the plays' own R. This study has another target, a daily mechanical structure,
  and the operator asked for it.
- **Not sizing guidance.** A front call ratio has no cap, and a fixed-exit grade understates what a
  real margin call does.
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

| Tenor | Expiry | Minimum at fill | Exit |
|---|---|---|---|
| T30 | Standard monthly nearest 30 DTE | 21 calendar days | 5 sessions after the fill |
| T7 | Friday weekly nearest 7 DTE | 5 calendar days | 2 sessions after the fill |

DTE counts from the fill. A tie goes to the earlier expiry. A Friday that is not a session moves to
the Thursday before it.

| Wing x | T30 | T7 |
|---|---|---|
| QQQ | 5% | 2.5% |
| SMH | 9% | 4.5% |

SMH is scaled by the median 20-day realized vol ratio printed at planning (0.313 / 0.178). T7 is
scaled by √(7/30). The values are rounded and fixed here.

### Dates

- **D.** The signal date, a session in the window. The session calendar is the SPY session table
  (`mechanical_baseline.load_closes`).
- **Fill.** The session after D.
- **Exit.** The fixed number of sessions after the fill.

### One signed series

On the same strikes, a front ratio is exactly minus a back ratio at mid, before commission. So each
ratio has one stored series, `y`, the back ratio's gross P&L as a share of spot. The front ratio's
gross P&L is `−y`. Every correlation runs once, on `y`, and reads with the opposite sign for the
front ratio. There are 12 series: 2 tickers × 2 tenors × 3 structures.

### Unit

- **Primary.** Net P&L as a share of spot, because a front call ratio has no defined max loss. Spot
  is D's close.
- **R.** P&L over max loss at expiry, printed wherever risk is defined: S, both back ratios and the
  front put ratio. Never graded.

### Features, fixed here

Every feature is known at D's close, except the lag noted under the analysis page. A missing input
leaves the row out of that feature's cells only.

| Feature | Definition | Kind |
|---|---|---|
| `ret1`, `ret5`, `ret20` | Close-to-close return over 1, 5, 20 sessions | rank |
| `dist50` | Close ÷ its 50-session average − 1 | rank |
| `range_atr` | Day's high − low ÷ the 20-session mean true range | rank |
| `evol` | `E-VOL` from `lib/mech_regime.py`, thresholds unchanged, on D exactly | cut 0 / 1 |
| `rv5_rv20` | 5-session realized vol ÷ 20-session realized vol | rank |
| `iv_rv20` | ATM IV on D − RV20, both in vol points | rank |
| `iv_chg5` | ATM IV on D − ATM IV 5 sessions earlier | rank |
| `und_vol` | Share volume ÷ the mean of the prior 20 sessions | rank |
| `opt_vol` | ATM option volume ÷ the mean of the prior 20 sessions, 15 of them present | rank |
| `qqq_prem` | BaselineDaily `qqq_call_prem` + `qqq_put_prem`, QQQ only | rank |
| `qqq_cp` | BaselineDaily `qqq_call_prem` ÷ `qqq_put_prem`, QQQ only | rank |
| `mkt_dir` | MARKET `dir`: BULL 1, RANGE 0, BEAR −1 | cut 0 / 1 |
| `mkt_vol` | MARKET `vol`: C-VOL 0, L-VOL 1, H-VOL 2, E-VOL 3 | cut 2 / 3 |
| `mkt_risk` | MARKET `risk`: RISK-ON 1, RISK-OFF 0 | cut 0 / 1 |
| `mkt_hp` | MARKET `HP` token present | cut 0 / 1 |
| `mkt_hp_score` | The hedge-pressure score in the MARKET signal, 0 to 100 | rank |
| `mkt_flow` | `[FLOW]` items in the MARKET signal | cut 2 / 4 |
| `tk_dir` | The ticker row's `dir` | cut 0 / 1 |
| `tk_vol` | The ticker row's `vol` | cut 2 / 3 |
| `tk_flow` | `[FLOW]` items in the ticker row's signal | cut 3 / 4 |

- **ATM IV and option volume.** The mean IV, and the summed `Volume`, of the D row of that session's
  own ATM call and put. An IV of 0 is missing.
- **Rank.** Top minus bottom is the top rank tercile's mean minus the bottom's.
- **Cut lo / hi.** Top is x ≥ hi and bottom is x ≤ lo.

_Resolved at build (2026-11-06):_ a discrete feature takes fixed cuts, not rank terciles.
`forward_drawdown.tercile_contrast` breaks ties by position, so on a binary feature its groups would
be arbitrary. A `cut` reads the levels themselves.

_Resolved at build (2026-11-06):_ the plan's "about 15" features is 22 on QQQ and 20 on SMH, once
each regime field and each `[FLOW]` count is its own feature. That is 252 cells against the plan's
"about 180". The census found no `risk` or `HP` token in any ticker row's head, so those two are
MARKET only. The FDR step is run on the true count.

### The analysis page, parsed deterministically

No model call. Rows come through `lib/era.py` as era v4, with the seal respected.

- **Tokens.** `market_read.parse_label`, read unchanged: the head is the text before the first of
  `—`, `" - "`, `". "`, `": "` or `" ("`; `dir` is the first of BULL, BEAR, RANGE; `vol` the first of
  E-VOL, H-VOL, L-VOL, C-VOL; `risk` is RISK-ON or RISK-OFF; `HP` is a whole token.
- **Unparsed fields.** A field with no token is missing, and is never imputed. First words such as
  `spot`, `Below`, `PxVec`, `Rich`, `nan` or a blank parse to no direction. A head reading `E-VOL`
  alone has a `vol` and no `dir`.
- **A date with two rows for one ticker.** It leaves the ticker's analysis features.

**The hedge-pressure score.** The first of these forms, tried in this order, with a value from 0 to
100. Anything else is missing.

| Order | Form (case-insensitive) |
|---|---|
| 1 | `hedge[- ]pressure[^\n.]{0,40}?(\d{1,3})\s*/\s*100` |
| 2 | `hedge[- ]pressure(?:\s+score)?\s+(\d{1,3})\b` |
| 3 | `(\d{1,3})\s*/\s*100[^\n.]{0,20}?hedge[- ]pressure` |

### Lag bin

Lag is `created_datetime[:10]` minus `date`, in days, by `market_read.lag_bin`.

| Lag bin | Lag |
|---|---|
| LIVE | 0 or 1 day |
| NEAR | 2 to 7 days |
| RETRO | more than 7 days |
| UNKNOWN | blank, or negative |

A LIVE row at lag 1 was written after D's close. It is treated as known by the fill, which is the
next session's close. Its time of day is not checked. That is unresolved and the default stands.
Changing it would only shrink LIVE, which is already below its floor.

## Dependencies

- `scripts/backtest/simulate.py`: `entry_day_fill`, `_monotonicity_violation`. Imported, never copied.
- `selloff_put_diagonal.leg_mark`: the exit mark, on the shared `_snap_asof`, `_is_junk_quote` and
  `junk_day_mark`.
- `index_vrp.natural_fill`, `realized_vol`.
- `mechanical_benchmark`: `grid_step`, `grid_around`, `listed_by`, `monthly_expiries`.
- `market_read`: `parse_label`, `lag_bin`. `regime_map.bh_q`.
- `lib/forward_drawdown.py`, `lib/pbo.py::cscv`, `lib/era.py`, `lib/underlying.py`.
- `lib/mech_regime.py::MechLabeler` on `backtests/mech_regime/spy_vix_daily_full.csv`, unchanged.
- `scripts/backtest_study/lib/harness.py` is not read. No Black-Scholes or other model price exists
  anywhere in this study.

## Population and basis, fixed here

- **Underlyings.** QQQ and SMH, graded separately.
- **Window.** Signal dates 2024-03-15 to 2026-09-22: the option cache starts 2024-03, and the seal
  starts 2026-09-23. That is 632 sessions on the SPY table. The plan's "about 635" was an estimate.
- **Forward.** Signal dates from 2026-09-23.
- **Discovery.** The first 60% of the window's dates, chronologically: 379 sessions, through
  2025-09-18. A row whose exit falls on or after 2025-09-19 also leaves discovery.
- **Confirmation.** The last 40%: signal dates from 2025-09-19, 253 sessions. There is no k-fold.
- **Era.** Analysis rows are era v4, by `era.resolve_paths` and `era.enforce` on the exports. A
  different era refuses (exit 3). Price, volume and option series belong to no era. The report's
  header says so: `analysis features are era v4; price, volume and option series are era-free`.
- **Era floor.** `era.require_dates` refuses fewer than 60 MARKET dates in the window (exit 2).
- **Seal.** `era.drop_sealed(rows, date_key="date")`, with no reader, on analysis and BaselineDaily
  rows. This study is not in `era.SEALED_READERS`. A trade's exit may fall after the seal's start: the
  seal binds signal dates.

### Strikes

- **Spot.** D's close from `lib/underlying.py`. QQQ and SMH have no split inside the window.
- **ATM.** The strike nearest spot with both a call and a put listed by D.
- **Wing.** The strike nearest spot × (1 ± x), of its own type, listed by D, strictly outside the ATM
  strike. Otherwise the trade drops as `wing_degenerate`.
- **The walk.** Nearest first, on `mechanical_benchmark.grid_step`'s grid. A contract skip-listed on
  evidence is stepped past. A cached contract with a row on or before D is chosen; one with no such
  row is stepped past. An uncached contract makes the trade await a fetch.

_Resolved at build (2026-11-06):_ an expiry is `not listed` only when three of its strikes are
skip-listed on evidence, and a cached file never proves it. A first version also read cached files
whose first row came after D as proof, and it dropped 25 QQQ T30 trades that way. Those files are
shallow fetches, and a monthly 30 days out is listed. T7 weeklies' listing is unknown from disk, so
they are probed the same way and no strike is inferred from a sparse cache.

### Pricing and costs

- **Fill.** Every leg at the fill day's own closing mid, through `entry_day_fill`, on one clock. A leg
  with no row that day drops the trade. No leg moves to another day.
- **Junk quotes.** A wide two-sided quote fills at its mid, and a quote with no bid is refused
  (`junk_entry_quote`). A priced-against-strike-order pair is refused (`non_monotonic_entry_quote`).
- **Exit.** `leg_mark` on the exit session. A leg with no row that day drops the row
  (`no_exit_quote`), and so does a carried mark (`stale_exit_mark`).
- **Credit entries.** A ratio may open as a credit. `run_trade` is this study's own fixed exit. It
  never calls the harness or `_simulate`, so a credit never takes the `CREDIT_PROD` route
  (`scripts/backtest/simulate.py:784-785`).
- **Commission.** $0.65 per contract per side: 4 sides on S, 6 on a ratio.
- **Natural fill.** Each side's own round trip at the touch, on `index_vrp.natural_fill`. Front and
  back print separately. Never graded.
- **Model prices.** None.

_Resolved at build (2026-11-06):_ every leg takes `entry_day_fill(row, +1)`, whichever side holds it.
That returns the closing mid for a normal or wide quote and refuses a quote with no bid. The
side-aware call would fill a sold junk leg at its bid and a bought one at its mid, which breaks
Front = −Back. A sold leg's bid therefore reaches only the natural-fill print.

## Plan-time observations, disclosed

No QQQ or SMH option outcome has been read. No option P&L, mid change, IV path or straddle cost was
computed on those tickers, as a smoke test or otherwise. The figures below come from analysis text,
session calendars, underlying closes and volumes, `Price~` and file names.

### What planning printed

| Item | Figure |
|---|---|
| MARKET dates in the window | 258 |
| QQQ dated rows in the export | 92 (78 in the window) |
| SMH dated rows in the export | 130 (110 in the window) |
| RV20 median, QQQ, at planning | 0.178 |
| RV20 median, SMH, at planning | 0.313 |
| RV20 median, window to 2026-08-11, this census | QQQ 0.179, SMH 0.333 |
| Median share volume, window to 2026-08-11 | QQQ 42,393,600; SMH 7,379,000 |

The wing scale keeps the plan's 0.313 / 0.178. The census's higher SMH figure is disclosed, and no
wing moved.

**Contract counts.** Planning estimated them from OHLC closes: T30 about 1,550 on a $5 grid, about
2,900 on a finer one; T7 about 3,000, rough and unmeasured. The fetcher's dry run on 2026-11-06 named
3,928 uncached contracts with 116 trades held back, because the OHLC then ended 2026-08-11.

### Regime first words, whole export

| Ticker | First words and counts |
|---|---|
| MARKET | BULL 168, RANGE 120, BEAR 13 |
| QQQ | BULL 48, RANGE 33, BEAR 2, blank 2; once each: `spot`, `Below`, `BEAR-leaning`, `RANGE/soft`, `about`, `BULL-tilt`, `RANGE→BEAR` |
| SMH | BULL 63, BEAR 28, RANGE 22, blank 3; twice each: `PxVec`, `E-VOL`, `Rich`, `Spot`; once each: `BEAR-lean`, `E-VOL:`, `Semis`, `BEAR-tilt`, `Crowded`, `Extended` |

### Token census, window

| Field | MARKET | QQQ | SMH |
|---|---|---|---|
| `dir` | BULL 135, RANGE 110, BEAR 13 | BULL 39, RANGE 34, BEAR 3, none 2 | BULL 45, BEAR 30, RANGE 21, none 14 |
| `vol` | L 156, E 67, C 27, H 8 | L 48, E 14, C 6, H 1, none 9 | E 53, L 33, H 2, none 22 |
| `risk` | ON 155, OFF 98, none 5 | none 78 | none 110 |
| `HP` | 119 of 258 | 0 | 0 |
| `[FLOW]` items | 1 to 6, most 3 | 2 to 5 | 2 to 7 |
| Lag: LIVE, NEAR, RETRO | 28, 2, 228 | 10, 1, 67 | 17, 1, 92 |

The hedge-pressure forms return a score on 203 of the 258 window MARKET rows. 222 rows mention the phrase.

**Every LIVE date falls in confirmation, and no BEAR label on MARKET is LIVE**, by the record at
[`current.md`](../../current.md#the-regime-labels-were-mostly-written-after-the-fact). LIVE holds at
most 28 MARKET dates in the window, below the 60-date floor. So every analysis cell is expected to
read `UNDERPOWERED` on confirmation, and none can be a `CANDIDATE` on these dates.

### Data checks

- **`E-VOL` input.** `spy_vix_daily_full.csv` runs 2023-06-01 to 2026-10-22 and labels all 632
  sessions: L-VOL 494, H-VOL 81, E-VOL 57. It is market-wide and applies to both tickers.
- **BaselineDaily.** 610 window dates, all on sessions. 601 carry QQQ premium.
- **Off-calendar.** One date in each of MARKET, QQQ and SMH (a non-session) leaves the study.
- **`Price~` against the closes.** Over 974 SMH days and 995 QQQ days, the ratio is 1.0 inside the
  window. SMH reads 2.0 before 2023-05-05, a split before the window. QQQ's one bad print is
  2025-11-28.
- **OHLC.** Both files end 2026-08-11 at registration, so the run reads `NOT BUILT` until they are
  refreshed.

### Prior prints

- **The 23-onset print, 2026-11-06.** While counting `E-VOL` onsets, SPY and VIX moves after 23 onsets
  from 2023-06 to 2026-09-22 were printed. VIX fell in 15 of the 23
  ([entry](../../current.md#2026-11-06--long-straddles-and-backspreads-after-a-vol-expansion-untested-one-spy-study-proposed)).
  No option price was read, and it shaped no choice here.
- **The 2026-09-04 text-thread closure.** Text features were `NULL` on the plays' own R. This study
  has another target, and the operator asked for it.
- **`earnings_vol`, `index_vrp`, `hedge_structure`.** Earlier straddle and short-vol verdicts on other
  names and dates are known. None reads QQQ or SMH daily.

## What it compares

| Object | Object type | What it reads | Role |
|---|---|---|---|
| 12 series, 20 sides | cell | Mean net P&L per side, no condition | Unconditional read |
| 252 feature × series cells | cell | Spearman and top minus bottom | Discovery, then confirmation |
| Natural fill per side | descriptive cut | Net P&L at the touch | Printed only |
| R per side | descriptive cut | Net P&L over max loss, where defined | Printed only |
| ALL, LIVE, RETRO | descriptive cut | Each analysis cell, on both date sets | LIVE alone can confirm |
| Worst trade, worst 21 rows | descriptive cut | Per side | Printed only |

## How it is judged

### Bootstrap

- **Block.** 21 consecutive rows, at least the hold of both tenors. `forward_drawdown.block_bootstrap`
  with 10,000 draws, seed 20261106. The hold-length block prints beside each confirmed cell, never
  graded.

_Resolved at build (2026-11-06):_ `block_bootstrap` takes a `stat_fn(x, y)`, so it fits both a mean
and a tercile difference, and no other helper is needed. It returns no draws, and the FDR step needs a
p-value, so discovery draws through the same `resample_blocks` with the same seed. A test pins the two
together. A row-based block is never shorter than the hold, and missing rows only lengthen it in
sessions.

### 1. Unconditional

For each series and side: mean net P&L with a block-bootstrap CI over the whole window, and the same
mean on discovery rows, on confirmation rows, and with the two `vol_sleeve` windows cut.

### 2. Discovery, first 60% of dates

- **Statistics.** Spearman, and top minus bottom, for each cell. Analysis cells use all their rows.
- **p-value.** Two-sided normal, from the block-bootstrap standard error of Spearman, on 2,000 draws.
- **FDR.** Benjamini-Hochberg across every cell above its floor, one family.
- **Ranked list.** The cells at q ≤ 0.10. Only these move on. The whole list is printed.
- **Nothing later is read.** A discovery row closes before 2025-09-19, and no feature reads past D.

### 3. Confirmation, last 40% of dates

A ranked cell's clauses are under [Bar for a candidate](#bar-for-a-candidate). An analysis cell reads
LIVE rows only. RETRO reads as descriptive, because those labels were written after the fact.

### PBO

`lib/pbo.py::cscv`, S = 16, on total P&L, one value for the whole study.

- **Configurations.** Every gradable cell, once each way: a session's value is +y in the top arm, −y in
  the bottom arm, 0 otherwise, and the column's mirror image. Rank cuts come from discovery rows.
- **Rows.** Each window session. A session with no row is 0.

## Gates

**The coverage gate.** It is all-or-nothing, and it comes before any price is read.

- Every trade in all four ticker and tenor pairs must be built or dropped on evidence. One awaiting
  trade anywhere keeps it shut.
- Both OHLC files must reach 2026-09-22.
- `Price~` on built trades' D rows must agree with the close. A run of 3 or more observations more than
  10% off refuses, because the closes would be on another split basis. A shorter run is a bad print,
  counted only.

While it is shut the run prints `NOT BUILT — AWAITING SCRAPE` and contract counts per ticker and tenor,
and writes nothing. `Book.price` and `Book.option_row` raise until it opens. A partly cached leg set
therefore cannot produce a partial figure.

**Power floors (C0), per cell.** A cell below its floor reads `UNDERPOWERED`, on the dates it is read on.

| Floor | Value |
|---|---|
| Dates | 60 usable rows |
| Calendar blocks | 6 distinct `session index // 21` |
| Each arm | 12 rows in 3 calendar blocks |
| Unconditional | 60 rows in 6 calendar blocks |

A coverage gap on T7, or anywhere else, reads `UNDERPOWERED`. It is never filled with another price.

## Bar for a candidate

**A cell.** All of these must hold:

1. **Confirmation.** Top minus bottom has discovery's Spearman sign, with its CI excluding zero, on the
   confirmation dates. An analysis cell reads LIVE dates only.
2. **Other ticker.** The same tenor, structure and feature has the same sign on the other ticker on the
   same dates, above its own floors. QQQ and SMH are correlated, and the report prints that caveat.
3. **Windows cut.** The same sign with the two `vol_sleeve` windows removed: signal dates 2025-03-01 to
   2025-04-30 and 2026-02-01 to 2026-04-30.
4. **PBO.** Below 0.5.
5. **Natural fill.** Printed for each side.

_Resolved at build (2026-11-06):_ `qqq_prem` and `qqq_cp` have no SMH column, so clause 2 reads QQQ's
value against SMH's series. Without this they could never meet the clause.

**The unconditional read.** CI above zero, positive on discovery rows, positive on confirmation rows
and positive with the windows cut.

## Verdicts, worded now

**A cell.** The first matching row wins.

| Token | When |
|---|---|
| `UNDERPOWERED` | A C0 floor is unmet on the dates read, or the statistic is NaN; or clauses before 2 hold and the other ticker is below its floor |
| `CONTRARY` | CI excludes zero, on the opposite sign from discovery |
| `NULL` | Not on the ranked list and above its discovery floor; or a clause fails. A `NULL` means no large effect, since the effective sample is far below 632 |
| `CANDIDATE` | Every clause holds. It earns only a forward grade |

A cell below its discovery floor reads `UNDERPOWERED`.

**The unconditional read**, per side.

| Token | When |
|---|---|
| `UNDERPOWERED` | Below its floor |
| `CONTRARY` | CI below zero |
| `CANDIDATE` | Its bar holds |
| `NULL` | Otherwise |

**FORWARD.** Each `CANDIDATE`'s confirmation statistic on signal dates from 2026-09-23, on the same
floors. `STILL-OPEN` until the floors are met; then `CANDIDATE`, `CONTRARY` or `NULL`, by the first
clause. Forward legs need their own fetch. Analysis and BaselineDaily cells wait for `era.SEAL_LIFTED`.

**The banner.**

```
>>> daily_vol_structure <ticker> <tenor> <structure> <feature>: CANDIDATE | CONTRARY | NULL | UNDERPOWERED <<<
>>> daily_vol_structure UNCONDITIONAL <ticker> <tenor> <structure> <side>: CANDIDATE | CONTRARY | NULL | UNDERPOWERED <<<
```

Only the ranked cells print a banner line. The rest print as a tally. If a `CANDIDATE` prints, the
replication protocol's analyst pair reads it before anyone calls it a finding.

## Anti-tuning

- Fixed here: both tickers, both tenors, the wings, the exits, the feature list and its cuts, the
  hedge-pressure forms, the 60/40 split and its first confirmation date, the block, the seed, q ≤ 0.10,
  the floors and the verdict words.
- No feature, tenor, wing or hold is added on a look at the results.
- Natural fill, R, the hold-length block, RETRO and the worst figures are printed as they fall, and none
  re-grades anything.
- A window, feature or cell is never dropped after an outcome prints. Any change is a new registration.

## What could ship

Nothing ships from this study.

- A `CANDIDATE` earns a forward grade and files "to be tested" in
  [`deployment-evidence.md`](../../deployment-evidence.md). It changes no production code.
- `CONTRARY`, `NULL` or `UNDERPOWERED` changes nothing.
- Any production change goes back to the operator.
