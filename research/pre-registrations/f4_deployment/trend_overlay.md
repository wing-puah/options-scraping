## trend_overlay — does a slow trend rule cut drawdown, and at what cost?

<!-- outcome:start -->
> Latest outcome: `>>> trend_overlay A DISCOVERY (T-10M vs long SPY, 1993-02-01 to 2026-09-22, 10 bp, cash 0%): NO-DRAWDOWN-BENEFIT <<<` on `dMDD +0.273 [-0.009, +0.457]`; `>>> trend_overlay A HOLDOUT (T-10M vs long ^GSPC price-only, 1950-01-03 to 1992-12-31, 10 bp, cash 0%): NO-DRAWDOWN-BENEFIT <<<` on `dMDD +0.150 [-0.042, +0.335]`; `AGREES`; B `UNDERPOWERED` (15 switched dates, floor 20); forward `STILL-OPEN` — era current for A (closes to 2026-09-22), v4 book for B, run 2026-11-21 · [record](../../study-results/f4_deployment/trend_overlay.md)
<!-- outcome:end -->

_Registered 2026-11-21 (accepted by default; immutable in substance)._

**STATUS: REGISTERED · ACCEPTED BY DEFAULT, NOT YET RUN**, on the drafter's recommended defaults
(the operator's standing rule of 2026-10-09). The operator asked for the study on 2026-11-21. No
return, drawdown, switch count or episode figure for any rule below was computed before this file
was written.

A fresh second reader checked the draft on 2026-11-21, before any outcome existed. Its read was DO
NOT FREEZE YET, on two blockers: the Population B wrapper was not named, and a cut series could
invent a month-end. Both are fixed below, with gate GW and the month-end rule. Its eleven minor
findings are folded in.

## The question

Every earlier trend test in this repo asked whether a trend break **forecasts** the next weeks'
mean return. All were null:

| Earlier test | What it asked | Verdict |
|---|---|---|
| [`regime_confirm`](../f1_selection/regime/regime_confirm.md) `RC-200` | Does a BEAR flip below the 200-day SMA pick out flips followed by a 10% fall? | `NULL` |
| [`state_map`](../f1_selection/regime/state_map.md) `C6`, Q3 | Is "below the 200-day SMA" on before a top; does SPY keep falling after a BEAR onset? | `NO-FORECAST`, `NULL` |
| Label review 2026-10-29 ([evidence](../../deployment-evidence.md#new-market-regime-labels-tested-dropped-2026-10-29)) | Do `sma200`, `sma50`, `tsmom1m`, `tsmom3m` separate the book's PF? | rotation p 0.59 or higher |

The published trend-following claim is a different one. It is a **payoff shape**, not a forecast.
A slow trend rule takes many small losses when it exits and re-enters in a choppy market. In return
it is out of the market for most of a long bear market. The mean return stays about the same, and
the maximum drawdown is lower.

- Faber, M. (2007), "A Quantitative Approach to Tactical Asset Allocation", *Journal of Wealth
  Management* 9(4). The 10-month SMA rule, checked once a month.
- Moskowitz, T., Ooi, Y. H. and Pedersen, L. H. (2012), "Time Series Momentum", *Journal of
  Financial Economics* 104(2). The 12-month sign of an asset's own past return.
- Hurst, B., Ooi, Y. H. and Pedersen, L. H. (2017), "A Century of Evidence on Trend-Following
  Investing", *Journal of Portfolio Management* 44(1). Trend rules did best in long bear markets.

So this study does not ask whether the rule predicts returns. It asks two things:

| Label | Question | Role |
|---|---|---|
| Population A | On a 1× long S&P 500 position, does switching to cash while the index is below its trend cut the maximum drawdown, and what does it cost in return? | Primary. Discovery and holdout graded separately |
| Population B | On the `account_sim` book, does cutting the net cap from 2.50 to 1.00 while the index is below trend cut the book's drawdown? | Secondary. In-sample, one era |

What each verdict word would mean:

| Word | Meaning |
|---|---|
| `CUTS-DRAWDOWN-NO-COST` | The rule cut the maximum drawdown, and the return did not fall |
| `CUTS-DRAWDOWN-AT-A-COST` | The rule cut the maximum drawdown, and gave up some return, within the limits below |
| `TOO-COSTLY` | The rule cut the maximum drawdown, but gave up more than 2 points of return a year, or its return-to-drawdown ratio (Calmar) was no better than holding |
| `NO-DRAWDOWN-BENEFIT` | No drawdown cut was shown |
| `UNDERPOWERED` | Too few bear markets in the window to judge. Nothing is concluded |

No verdict changes a rule.

## What this study is not

- **Not a forecast test.** It grades no mean-return difference after a signal. The earlier tests
  did that.
- **Not a re-run of the ruled-out entry gate.** See [Population B](#population-b-the-book) for how
  the switch differs from the "entry-side regime gate" in
  [`account-sim-feasibility-plan.md`](../../account-sim-feasibility-plan.md#what-is-ruled-out-and-why).
- **Not an option study.** Population A trades a 1× index position. Population B changes only
  the net cap on new entries. It never closes an open position.
- **Not a parameter search.** Three rules are fixed below, and one is the headline.
- **Not intraday.** Every signal and every return uses daily closes.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price series

| Series | Source | Use |
|---|---|---|
| `^GSPC` close | yfinance `Close`, `auto_adjust=False`, from 1948-01-02 | Every trend signal, in both windows. Holdout returns |
| SPY adjusted close | yfinance `Adj Close`, from 1993-01-29 | Discovery returns. It folds in dividends, so discovery returns are total returns |
| SPY close | yfinance `Close` | Gate GB only |
| `^IRX` close | yfinance, from 1960-01-04 | The cash-yield sensitivity only |

- **Holdout returns are price-only.** `^GSPC` carries no dividends. Both the long position and the
  overlay lose the dividend alike, so the drawdown comparison is fair. The overlay's return cost is
  overstated a little, since it would also miss dividends while out.
- **One signal series.** The rule reads `^GSPC` closes in both windows, so it is the same rule
  everywhere. On SPY sessions the `^GSPC` close of the same date is used. In discovery, a SPY
  session with no `^GSPC` close is refused by gate GE. Holdout returns come from `^GSPC` itself.
- **Cache.** The module writes `backtests/trend_overlay/<NAME>.csv` (date, close, adj_close).
  yfinance's `end` is exclusive, so today's bar is never fetched. `--refresh` refetches.

### The three rules, fixed here

Each rule is **IN** (hold the index) or **OUT** (hold cash) at each decision close.

| Label | Decision closes | IN when | Source |
|---|---|---|---|
| `T-10M` | The last session of each calendar month | The month-end close is above the mean of the 10 month-end closes ending at it | Faber (2007) |
| `T-200D` | Every session | The close is above the mean of the 200 closes ending at it | The 200-day rule `state_map` `C6` and `regime_confirm` `RC-200` used |
| `T-12M` | The last session of each calendar month | The month-end close is above the month-end close 12 months earlier | Moskowitz, Ooi and Pedersen (2012), on price |

- **`T-10M` is the headline.** It is the rule the drawdown claim was published on. Checking once a
  month also means fewer switches, so whipsaw should cost least.
- **`T-200D` and `T-12M`** are printed with the same metrics. Their words print as "secondary,
  not graded".
- **Ties.** A close exactly equal to its reference is OUT. It is a measure-zero case.
- **Which session ends a month.** A session is a month-end when the next session in the series
  falls in a later month. The last row of a series is never a decision close, so a cut series
  (at 2026-09-22, or inside gate GX) never invents a decision. A true month-end on the last row is
  read one session late, when its successor arrives; at 2026-09-22 this cannot arise.
- **`T-12M` on price.** The paper uses excess total return. This study uses the `^GSPC` price, so
  the rule is the same in both windows. It is a stated simplification.

### Execution

- **A decision at close `t` is executed at the close of the next session, `t + 1`.** The return
  from close `t + 1` to close `t + 2` is the first one earned at the new exposure.
- So the exposure for session `k`'s return (close `k − 1` to close `k`) is the state from the
  latest decision close at or before `k − 2`.
- **Why a one-session lag.** The rule needs the close to be known before it trades. Trading at the
  same close as the signal would assume a fill at a price not yet known.
- **Starting state.** Each curve starts at 1.0 at the close before the window's first session. The
  overlay starts IN or OUT as the rule says at that point, with no entry cost.

### Returns, cost and cash

- **Long position.** Session return `r_k = P_k / P_{k−1} − 1`, with `P` the SPY adjusted close in
  discovery and the `^GSPC` close in holdout.
- **Overlay.** `r_k` while IN. The cash return while OUT.
- **Cost per switch.** Every change of state costs **10 basis points** of overlay equity, charged at
  the execution close. It covers commission, spread and slippage on one full-position trade.
  Printed both ways at 0 and 25 basis points.
- **Cash return.** **0% while OUT** (headline). Printed both ways with cash earning the 13-week
  T-bill: `^IRX / 100 / 252` per session from 1960-01-04, and 0 before that date.
- **Why 0% cash is the headline.** It is the conservative case for the overlay. The T-bill twin is
  what a cash account would have earned, and it is printed beside every figure.

### Windows

| Window | Sessions | Return series | Role |
|---|---|---|---|
| Discovery | 1993-02-01 to 2026-09-22 | SPY adjusted close | Graded |
| Holdout | 1950-01-03 to 1992-12-31 | `^GSPC` close, price-only | Graded separately |
| Gap | 2026-09-23 to 2026-11-20 | — | In no population |
| Forward | From 2026-11-21 | SPY adjusted close | The one-shot forward read |

- **No close after 2026-09-22 enters the in-sample run.** Every series is cut at 2026-09-22
  (`IN_SAMPLE_END`) before anything is computed.
- **Why 2026-09-22.** Closes after it were seen in the 2026-11-21 bear peek. The
  [holdout seal](holdout_seal.md) also starts on 2026-09-23.
- **Runway.** Signals read `^GSPC` closes from 1948, so every rule is defined on the first session
  of both windows.
- **The holdout is earlier history.** It is not a later out-of-sample period. It tests whether the
  shape held in a different market, on prices this repo has read only through `regime_confirm`'s
  flip rates.

### Metrics, fixed here

All are computed on each curve's daily equity, per window.

| Metric | Definition |
|---|---|
| Max drawdown (`MDD`) | The largest fall of equity from its running peak, as a fraction of that peak |
| Average drawdown | The mean over sessions of `1 − equity / running peak` |
| CDaR95 | The mean of the worst 5% of those daily drawdown depths |
| Time under water | The share of sessions with equity below its running peak, and the longest such run in sessions |
| CAGR | `E_end^(252 / N) − 1`, with `N` the window's sessions |
| Calmar | CAGR / MDD |
| Switches | The number of state changes, and switches per year |
| Time OUT | The share of sessions the overlay held cash |

`ΔMDD = MDD(long) − MDD(overlay)`. A positive value means the overlay's worst drawdown was
shallower. `ΔCAGR = CAGR(overlay) − CAGR(long)`, in percentage points a year.

### Whipsaw cost

- **An OUT spell** runs from the execution close of an exit to the execution close of the next
  re-entry.
- **A whipsaw** is an OUT spell that re-enters within **63 sessions**, one quarter. A spell that
  short cannot have avoided a long bear market.
- **Its cost** is `ln(overlay growth over the spell) − ln(long growth over the spell)`. It includes
  both switch costs. A negative value means the spell lost ground.
- **Printed:** whipsaw count, their summed cost in log points, the sum of the losing ones alone,
  and the summed cost per year.
- **A spell open at the window end** is counted apart and enters no whipsaw sum.

### Bear-market episodes

- **An episode** is a drawdown of the **long** curve of 20% or more from its running peak.
- **Peak** is the session of the running high. **Trough** is the lowest session before recovery.
  **Recovery** is the first later session at or above the peak, or the window end.
- **Per episode**, printed: dates, the long curve's depth, the overlay's deepest drawdown inside
  the episode, and the savings.
- **Savings** = overlay log return − long log return, peak to trough. Printed again peak to
  recovery, which charges the late re-entry.
- **Cost outside episodes** = the summed overlay-minus-long log return on every session in no
  episode.
- **An episode with its peak before the window's first session** is printed and counted apart.

So the table shows both sides of the shape: what each bear market saved, and what the calm years
cost.

## Dependencies

- yfinance, for the four series above.
- `scripts/backtest_study/lib/path_bootstrap.py::_resample_indices`, the moving circular block
  resampler. Population A imports it unchanged.
- `scripts/backtest_study/lib/pbo.py::cscv` and `pad_head`.
- `scripts/backtest_study/lib/era.py`: `requested_era`, `SEAL_START`.
- Population B only: `scripts/backtest_study/f4_deployment/account_sim.py` (`load_settings`,
  `simulate`, `equity_curve`, `dense_episodes`, and `max_drawdown`, which `account_sim`
  re-exports from `f5_hedging/hedge_sizing.py`), `lib/protocol.py`
  (`ordered_by_day`, `ladder_rank`, `ladder_eligible`), `lib/book.py::load_book`,
  `lib/mtm_curve.py` (`book_curves`, `path_stats`, `TARGET_POSITION`), and
  `config/account-sim.yml`, read unchanged.

## Population and basis, fixed here

- **Population A era.** The inputs carry no prompt version. The report prints `era: current
  (inputs are unversioned market closes)`, as `state_map` does.
- **The seal and Population A.** The seal binds signal dates of emitted plays. Population A reads
  no play, flow signal or backtest row, so the seal does not bind it.
- **Population B era.** `era.requested_era()` and `load_book(era=…)`, which refuses a wrong or
  mixed era (exit 3) and a thin one (exit 2). v4 is the population. It is not re-run on v3.
- **The seal and Population B.** `load_book` is called with no `sealed_read`, so every signal date
  from 2026-09-23 is withheld. This study is not a named reader.
- **Exits past the cut.** A book position opened on or before 2026-09-22 keeps its stored exit,
  which may fall later. That is the seal's convention, a date boundary on signal dates. The trend
  state that gates an entry reads no close after the entry session's prior close.
- **Report header.** Era, the windows, the seal state, the git sha, the dirty flag, the input
  files, and each series' first and last date read.

## Plan-time observations, disclosed

Every check below was made on 2026-11-21, before this file was written. No return, drawdown,
switch or episode figure was computed for any rule.

### Inputs

| Series | First date | Last date | Rows |
|---|---|---|---|
| `^GSPC` | 1948-01-02 | 2026-11-20 | 19,846 |
| `^IRX` | 1960-01-04 | 2026-11-20 | 16,708 |
| SPY | 1993-01-29 | 2026-11-20 | 8,512 |

These came from a yfinance probe that printed row counts and end dates only.

The v4 results export holds 256 signal dates from 2024-01-10 to 2026-09-22 before the seal. That
was a date count of the export, with no outcome column read.

### What the drafter already knows

- **The current market.** The `state_map` registration printed the regime-watch row for
  2026-11-20: SPY 689.81 against a 200-day SMA of 732.76. So `T-200D` is OUT at the forward start.
  That date is in the gap.
- **The book's 2025 drawdown.** The feasibility plan says the losing positions of the book's worst
  window were opened while the regime read bull, and only one opened after the mech BEAR flip of
  2025-02-24. A 200-day or 10-month rule turns later than the 50-day mech label.
- **Public market history.** The drafter knows the dates of the large S&P 500 bear markets since
  1950 and the published results for these rules.
  - Faber reports a drawdown roughly halved, at about the same return, on US stocks from 1973.
  - Trend rules are known to have lagged in the fast 2020 crash and in the choppy years after 2009.
  - So the discovery window is not blind to the drafter, in direction or in rough size.
  - The holdout is not blind either. None of these figures was computed on this data.

### A prior, not evidence

The drafter expects `T-10M` to print `CUTS-DRAWDOWN-AT-A-COST` in both windows, with a return cost
under one point a year. The drafter expects Population B to print `UNDERPOWERED`. The book's 256
dates hold at most one or two below-trend spells under a 10-month rule.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `LONG` | control | The 1× long index position, never switched | The reference for every Population A delta |
| `T-10M` | arm | The 10-month SMA overlay, monthly | Headline, graded in discovery and in holdout |
| `T-200D` | arm | The 200-day SMA overlay, daily | Secondary, not graded |
| `T-12M` | arm | The 12-month momentum overlay, monthly | Secondary, not graded |
| Episodes | descriptive cut | Per bear market, savings against cost | Printed only |
| Sensitivities | descriptive cut | Cost 0 and 25 bp; T-bill cash; block 63 and 504 | Printed only |
| `B-CONTROL` | control | The `account_sim` book at its configured net cap 2.50 | The reference for Population B |
| `B-SWITCH` | arm | The same book, net cap 1.00 on entries while `T-10M` is OUT | Secondary, graded in-sample |
| `FORWARD` | population scope | `T-10M` against `LONG` from 2026-11-21 | One-shot forward read |

### Population B, the book

**The book.** The `account_sim` book exactly as `account_sim.report_population` builds it: v4,
`load_book()`, `ordered_by_day(..., ladder_rank, ladder_eligible)`, and `config/account-sim.yml`
unchanged. The headline is the SECONDARY full book, every pre-seal date. The PRIMARY dense episodes
print beside it.

**The switch.** On a signal date whose entry session is `k`, `B-SWITCH` uses a net cap of 1.00 ×
equity when `T-10M` is OUT, and 2.50 otherwise.

- The state is the one from the latest month-end decision close strictly before `k`.
- It reads no close on or after `k`.
- Every other knob is `B-CONTROL`'s: capital, risk, caps, floor rule, three positions a day.
- The cap gates new entries only. A position already open stays open.
- **1.00** is the lowest value in `account-sim.yml`'s own `grids.net`. It was not tuned.

**Terms.** "SECONDARY full book" and "PRIMARY dense episodes" are `account_sim`'s own population
names: every pre-seal signal date, and the runs of dates with no gap over five sessions. They are
not this file's "secondary, not graded" rules. "A3 basis" is realised P&L booked on each
position's exit day, the curve `account_sim`'s drawdown criterion A3 reads. "Mech BEAR" is
`lib/mech_regime.py`'s label: SPY below its 50-day SMA with a negative 20-session return.

**How it runs.** The study calls `account_sim.simulate` itself, in its own process, on the frozen
basis: `load_settings(DEFAULT_CONFIG)` with compounding and the ticker cap off. `account_sim.py`
is not edited. `simulate` has no per-session cap, so the switch rides on its one per-session hook:

- A pass-through `ranker` records the session's signal date and returns the day's list unchanged.
  `simulate` calls it once per session, before any admission.
- The cfg is a duck-typed wrapper. Its `net_cap` reads that date and returns 1.00 on a switched
  date, else the base value. Every other attribute is the base `Cfg`'s.
- It never runs `account_sim.main`, so it writes no `account_sim` report, CSV or page.

- **Gate GW** proves the wrapper is neutral. With the switch set to never fire, `B-SWITCH`'s
  `account_sim.book_signature` must equal `B-CONTROL`'s. A mismatch refuses (exit 3). Without it, a
  null could come from a wrapper that does nothing.

- **Gate GA** proves this. It hashes `backtests/study_output/account_sim*` and
  `site/account_sim*.html` before and after the run. Any change refuses (exit 3) and prints the
  diff. The report prints the empty diff.

**How it differs from the ruled-out entry gate.** The
[feasibility plan](../../account-sim-feasibility-plan.md#what-is-ruled-out-and-why) ruled out "an
entry-side regime gate". That gate refused entries on mech BEAR days, the 50-day label. It was
ruled out because the losing positions were opened while the label read bull.

| | Ruled-out gate | `B-SWITCH` |
|---|---|---|
| Signal | Mech direction, 50-day SMA and 20-session return | `^GSPC` against its 10-month SMA, month-end |
| Action | Refuse the entry | Lower the net cap to 1.00; entries that fit still open |
| Question | Does refusing bear-day entries fix the window? | Does a slower exposure cut lower the book's drawdown? |

The two overlap in spirit. A slower signal turns even later than the 50-day label, so `B-SWITCH`
may change few entries.

**What bounds it, disclosed.** `account_sim`'s cap grid already prints this book at a net cap of
1.00 on every date, and the feasibility plan quotes those cap cells. `B-SWITCH` applies 1.00 on a
subset of dates, so its effect lies between the control and that always-1.00 cell. The plan also
says the book is 100% long delta and mostly one contract per position, so the net cap binds only
when many positions are open at once. Population B is kept as a check of what Population A would mean for the
live net cap, not as a fix. If it is inert, that is the answer.

## How it is judged

### Bootstrap, Population A

- **Paired moving block bootstrap.** Each draw resamples the window's sessions in blocks with
  `path_bootstrap._resample_indices`. The long return and the overlay return of a session travel
  together. The overlay's exposure is the one it had, and the rule is not re-run on the resampled
  path.
- **Block 252 sessions**, one year. A bear market lasts one to two years, and a shorter block would
  cut it into pieces the rule never saw. Printed both ways at 63 and 504.
- 5,000 draws, seed 20261121.
- **Per draw:** `ΔMDD` and `ΔCAGR` on the resampled paths.
- **CI.** The 2.5th and 97.5th percentiles of the draws. The observed `ΔMDD` prints beside it.
- **What the verdict reads.** The 2.5th percentile of the resampled `ΔMDD`. The interval is over
  re-ordered paths, so it is not centred on the observed figure.
- **What it measures.** The noise in one drawdown figure, which is a noisy order statistic.
  A resampled path keeps each session's realised exposure, so it is a reordering of what happened,
  not a new test of the rule.

### PBO / CSCV

- `pbo.cscv` once per window, over the three rules.
- **Rows.** Sessions, padded at the head with zero rows by `pad_head` so 16 divides them. A zero
  row is cash earning nothing, the same for every rule.
- **S = 16.**
- **Metric.** Calmar on log returns: 252 × the mean session log return over the rows, divided by
  the maximum fall of their cumulative log return. Higher is better.
- **A half with no drawdown.** The metric is +∞ for a positive mean and −∞ for a negative one.
- **Reading.** At most 0.25 supports a claim that one rule beats the others. 0.25 to 0.50 prints
  "selection fragile". Above 0.50 prints "PBO veto".
- **The baseline with three rules.** An in-sample best rule that lands in the middle out of sample
  has a logit of exactly 0, which `cscv` counts as overfit. So pure noise gives a PBO near 0.67,
  and a veto is close to the default. The report prints `n_at_zero` beside the value.
- **What it never does.** It never changes the headline word. The headline was fixed before any
  run, so no rule was selected. PBO only limits what the report may say about which rule is best.

### Population B

- **Basis.** The headline is the realised-on-close curve, `account_sim`'s A3 basis: `equity_curve`
  over the signal positions, and `max_drawdown`. The mark-to-market curve from
  `mtm_curve.book_curves` at `TARGET_POSITION` prints beside it.
- **Per arm:** positions, net dollars, maxDD in dollars and as a share of capital, Ulcer, time under
  water, net-cap refusals, and the signal dates the switch was on.
- **Bootstrap, if powered.** A paired moving block bootstrap of the two arms' per-session realised
  P&L on every weekday session from the first entry to the last exit, with 0 on a session with no
  exit. Block 10 sessions, 5,000 draws, seed 20261121.
  `ΔMDD$ = |maxDD(control)| − |maxDD(switch)|` and `Δ$ = dollars(switch) − dollars(control)`.

## Gates

- **GE, inputs.** `^GSPC` covers 1948-01-02 to 2026-09-22, SPY covers 1993-02-01 to 2026-09-22,
  and every SPY session in that range has a `^GSPC` close. Any failure refuses (exit 3).
- **GB, basis.** SPY's `Adj Close / Close` ratio never falls by more than 0.01% and never moves by
  more than 2% between sessions. SPY close is within 3% of `^GSPC` / 10 on every common date. Any
  failure refuses (exit 3).
- **GX, no lookahead.** The exposure for session `k` reads no close after `k − 2`.
  `tests/test_trend_overlay.py` changes every later close and requires identical exposures. Each
  run also recomputes 60 evenly spaced sessions on series cut at that session, and stops on any
  difference.
- **GC, the cut.** The in-sample report is identical when every close after 2026-09-22 is changed.
  The test file checks it.
- **GA, artifacts.** `account_sim`'s reports, CSVs and pages are byte-identical after the run, as
  above.
- **GW, wrapper.** With the switch set to never fire, `B-SWITCH` takes exactly `B-CONTROL`'s
  positions. A mismatch refuses (exit 3).
- **GX and the calendar.** The test also checks that the last row of a cut series is never a
  decision close.
- **GN, floors.** A window with fewer than **2** episodes whose trough falls inside it prints
  `UNDERPOWERED` for Population A. Population B needs at least **20** signal dates under the switch,
  in at least **2** separate OUT spells, or it prints `UNDERPOWERED`.
- **Population B era.** `load_book` refuses a wrong or mixed era (exit 3), and a thin one (exit 2).
  A Population B refusal prints `B REFUSED (reason)` where B would be. Population A and the banner
  print in full.

**Why 2 episodes.** The claim is about bear markets. With one, the window holds a single event, and
no block bootstrap can say whether the cut was the rule or that event.

## Verdicts, worded now

### Population A, per window, headline `T-10M` at 10 bp and 0% cash

The first matching row wins.

1. **`UNDERPOWERED`.** Fewer than 2 episodes in the window.
2. **`NO-DRAWDOWN-BENEFIT`.** The lower bound of the `ΔMDD` CI is 0 or below.
3. **`TOO-COSTLY`.** The lower bound of the `ΔMDD` CI is above 0, and either holds:
   - `ΔCAGR` is below −2.0 points a year;
   - the overlay's Calmar is at or below the long position's.
4. **`CUTS-DRAWDOWN-AT-A-COST`.** The lower bound of the `ΔMDD` CI is above 0, not `TOO-COSTLY`, and
   `ΔCAGR` is below 0.
5. **`CUTS-DRAWDOWN-NO-COST`.** The lower bound of the `ΔMDD` CI is above 0, and `ΔCAGR` is 0 or
   above.

The cost lines read point estimates. The `ΔCAGR` CI prints beside them.

- **Why −2.0 points.** The published claim is "about the same return". A cost of two points a year
  is a fifth to a quarter of the long position's return over these windows. Past that line the
  shape is not the published one, whatever the drawdown did.
- **Why Calmar too.** A rule that cuts the drawdown by less than it cuts the return has made the
  ride smoother only by holding less.

**Agreement.** `AGREES` when both windows print a `CUTS-DRAWDOWN-*` word, or neither does. Otherwise
`DISAGREES`. `UNDERPOWERED` in either window gives `NOT COMPARABLE`.

**Secondary rules.** `T-200D` and `T-12M` print the same words in both windows, marked "secondary,
not graded". Each sensitivity prints the headline word it would give, marked "printed only".

### Population B

The first matching row wins.

1. **`UNDERPOWERED`.** Below the floor. The census and every figure print, and nothing is concluded.
2. **`INERT`.** Both arms took the same positions (`book_signature` equal). The switch changed no
   entry, so there is nothing to grade.
3. **`NO-BOOK-DRAWDOWN-BENEFIT`.** The lower bound of the `ΔMDD$` CI is 0 or below.
4. **`TOO-COSTLY`.** The lower bound of the `ΔMDD$` CI is above 0, and the dollars given up exceed
   the drawdown dollars saved: `−Δ$ > ΔMDD$`.
5. **`CUTS-BOOK-DRAWDOWN-AT-A-COST`.** Not `TOO-COSTLY`, the CI lower bound is above 0, and `Δ$` is
   below 0.
6. **`CUTS-BOOK-DRAWDOWN-NO-COST`.** The CI lower bound is above 0, and `Δ$` is 0 or above.

**Why B's cost line differs from A's.** The book is a sparse, fixed-capital account with no
compounding, so a CAGR and a Calmar have no clean meaning there. Dollars given up against
drawdown dollars saved is the same trade-off in the book's own unit.

Population B is in-sample on the window that set the net cap. No word here moves the cap.

### Forward

- **Opens 2026-11-21.** `T-10M` against `LONG` on SPY sessions from 2026-11-21, at 10 bp and 0%
  cash. 2026-11-21 is a Saturday, so the first forward session is 2026-11-23. The rule's state
  then is whatever the closes before it say; that state is OUT on `T-200D` (see the plan-time
  observations).
- **The read fires once**, on the first run on or after the earlier of two dates:
  - the recovery date of the first forward episode, a fall of the long curve of 20% or more from a
    forward peak (peak on or after 2026-11-21);
  - the sunset, **2029-11-21**.
- **Until then** the forward line prints `STILL-OPEN`, with a census of forward sessions only.
- **Words at the read.**
  - With a forward episode, or at the sunset when the long curve has fallen 20% from a forward
    peak without recovering (read over all forward sessions): `CUTS-DRAWDOWN` when the overlay's forward MDD is at least 5 points
    shallower than the long curve's and `ΔCAGR` is −2.0 points or above. `NO-DRAWDOWN-BENEFIT`
    otherwise. One episode allows no bootstrap, so the words read point estimates.
  - At the sunset with no forward episode: `NO-EPISODE`. The whipsaw cost and `ΔCAGR` print, and
    nothing about drawdown is concluded.
- **Verdict of record.** The first forward run that prints a word other than `STILL-OPEN`. Later
  runs are descriptive.
- **Expected wait.** A 20% bear market comes about once every five to seven years, so `NO-EPISODE`
  at the sunset is likely.

### The banner

The report's section titled VERDICT prints:

```
>>> trend_overlay A DISCOVERY (T-10M vs long SPY, 1993-02-01 to 2026-09-22, 10 bp, cash 0%): <word> <<<
>>> trend_overlay A HOLDOUT (T-10M vs long ^GSPC price-only, 1950-01-03 to 1992-12-31, 10 bp, cash 0%): <word> <<<
>>> trend_overlay A AGREEMENT: AGREES | DISAGREES | NOT COMPARABLE <<<
>>> trend_overlay A SECONDARY (not graded): T-200D <d>/<h> T-12M <d>/<h> <<<
>>> trend_overlay PBO: discovery <value> holdout <value> <<<
>>> trend_overlay B (net cap 2.50 -> 1.00 while T-10M is OUT, v4 book to 2026-09-22): <word> <<<
>>> trend_overlay FORWARD (T-10M vs long SPY from 2026-11-21, sunset 2029-11-21): <word> <<<
```

Each Population A line also prints `ΔMDD [CI]`, `ΔCAGR [CI]` and the whipsaw cost per year.

## Anti-tuning

- **Fixed here, the rules.** The three rules, their lengths and decision closes, the headline, the
  one-session lag and the tie rule.
- **Fixed here, the money.** The 10 bp cost, 0% cash, the two sensitivities, and the 1.00 net cap.
- **Fixed here, the judging.** The windows and their dates, the 20% episode line, the 63-session
  whipsaw line, the block length and seed, the floors, the −2.0 point line, and the verdict words.
- No other rule, length, band, cost, cap value or window is graded.
- A sensitivity, a secondary rule or an episode row never re-grades the headline.
- PBO never selects a rule.
- The in-sample run reads no close after 2026-09-22. The forward read opens on 2026-11-21 and
  closes at the sunset. No later run moves either date.

## What could ship

Nothing ships from this study.

- A `CUTS-DRAWDOWN-*` word in both windows files "trend overlay: drawdown cut at a cost, to be
  sized" in [`deployment-evidence.md`](../../deployment-evidence.md). Any live rule needs its own
  registration and an operator decision.
- Population B is in-sample on one era. Its word never moves `caps.net` in `account-sim.yml` or the
  live 2.50 cap in production.
- No word here changes a tier, a veto, a size class, an exit, the deploy card or the hedge sleeve in
  [§4](../../../docs/deployment-rules.md#s4).
