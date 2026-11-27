## vol_expansion_long_vol — after a SPY E-VOL onset, do a long straddle or a 1x2 backspread pay, and more than on calm weeks?

<!-- outcome:start -->
<!-- outcome:end -->

_Registered 2026-11-27._

**STATUS: REGISTERED · ACCEPTED BY THE OPERATOR ON THE DEFAULTS 2026-11-27, NOT YET RUN.** The
design is the proposal in [`next-steps.md`](../../next-steps.md#waiting-on-the-operator) item 18.
Every default in its open-decisions table is the frozen choice here. A revisit after a result is a
NEW registration, never an edit.

No straddle or 1x2 was priced, and no SPY option price, mid change or return for any onset was
read by the drafter before this file was written. A fresh second reader must check this file
before its first outcome and before its commit ([README](../README.md#the-second-reader-before-every-new-registration-freezes)).

## The question

After SPY's mechanical vol label turns `E-VOL`, we buy one of three long-vol structures at the
next close and sell it five sessions later. We ask two things per structure:

| Question | Comparator |
|---|---|
| Is the mean R above 0, net of commission? | none |
| Is it above the same structure opened on a calm week? | `ARM C` |

The three structures are graded separately:

- `ARM S`: a long ATM straddle.
- `ARM BC`: a call backspread, short 1 ATM call and long 2 calls near spot × 1.05.
- `ARM BP`: a put backspread, short 1 ATM put and long 2 puts near spot × 0.95.

**Why ask.** The operator trades straddles and backspreads on expanding-vol days. The analysis
prompt recommends them for its gamma-expansion playbook (`config/prompts/analysis-framework.md:186,227`).
No repo result tests either after a vol state
([evidence](../../current.md#2026-11-06--long-straddles-and-backspreads-after-a-vol-expansion-untested-one-spy-study-proposed)).

**The prior is against it.** Published index evidence says long volatility loses on average:

| Source | What it reports | Status in the 2026-11-06 search |
|---|---|---|
| Coval and Shumway (2001) | Zero-beta ATM S&P straddles lose about 3% per week | Abstract; sample period not confirmed |
| Bakshi and Kapadia (2003) | Delta-hedged index option gains are negative on average | Search summary; magnitude unverified |
| Goyal and Saretto (2009) | Straddles on stocks with realized above implied vol outperform | Abstract; the cross-section, not an event trade |
| Moreira and Muir (2017) | Lagged volatility relates to current volatility | Search summary |
| Corsi (2009), HAR | Forecasts the level of realized vol, in-sample | Full text; asset mapping unconfirmed |
| Muravyev and Pearson (2020) | Timed executions pay under 40% of conventional spreads | Abstract; supports a mid-fill cost model |

- **No study found conditions straddle returns on a just-occurred expansion day.** No
  peer-reviewed test of backspreads was found either.
- **The backspread case is inference only.** A net long-vega position pays the variance premium
  unless realized vol beats what was priced.

What each verdict word would mean for the operator:

| Word | Meaning |
|---|---|
| `LONG-VOL-PAYS` | The structure made money after the onset, and more than on calm weeks |
| `PAYS-NOT-SIGNAL` | It made money after the onset, but calm weeks did as well. The label adds nothing |
| `CONTRARY` | It lost money after the onset |
| `NULL` | Nothing was shown either way. Only a large effect could have been seen |
| `UNDERPOWERED` | Too few trades to judge. Nothing is concluded |

No verdict changes a production rule.

## What this study is not

- **Not a new signal search.** The trigger is the frozen `E-VOL` label with a 5-session re-arm.
  No other state, threshold or re-arm is graded.
- **Not intraday.** Every price is a daily close. Entry is the next close only, as the operator's
  end-of-day data allows. Same-session practice stays ungraded.
- **Not a structure search.** Three structures are fixed here. The 12-cell grid is printed for the
  overfitting check and never promotes a cell.
- **Not a re-grade of a closed line on its own terms.** See the next section.
- **Not sizing guidance.** One unit risks far more than the operator's $1,000 stop (see
  [R, fixed here](#r-fixed-here)). A stop cell prints and is not graded.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

### How it differs from the closed straddle line

The straddle line was closed on 2026-08-12. The `vol_sleeve` record calls its straddle and
strangle results "two-window artifacts" built on the engine's signal dates
(`research/archive/12-wrappers-and-vol-sleeve.md:322-327`). `hedge_structure.md:30-33` then put
"straddle/strangle structures" out of scope, "CLOSED 2026-08-12". That closure concerned flow-picked
dates. This study reads no flow, play or signal date. Its dates come from a market-wide vol state,
which no earlier straddle verdict conditions on. Earlier straddle results are on other triggers:
`structure_sweep` ARM D on the play's own date, `earnings_vol` ARM S across earnings, and `index_vrp`
selling monthly. So the line is reopened as a new question, per item 18's default. Declining it would
have cancelled `ARM S` only.

## Definitions

### Sessions and prices

- **Session.** A row with a SPY close in the label table (see [The label](#the-label)).
- **Spot.** The SPY unadjusted close on a session, from `backtests/state_map/SPY.csv` as
  `state_map.build_cal` reads it. A session with no spot drops the trade (`no_spot`).
- **`D`.** The onset session, or the calm week's chosen session.
- **`F`.** The fill session, the session after `D`.
- **Exit session.** `F + 5` sessions, which is `D + 6`. The printed 10-session hold exits at
  `F + 10`, which is `D + 11`.
- **DTE.** Calendar days from `F` to the expiry.

### The label

`E-VOL` is the vol field of the frozen mechanical regime label.

- **Function.** `lib/mech_regime.py::compute_mech_table`, field `mech_vol == "E-VOL"`. The rule is
  "VIX >= 30 OR 5-day VIX change >= +25%" (`lib/mech_regime.py:11-13`).
- **Causal at D's close.** The label for `D` reads the VIX close on `D` and the VIX close five table
  rows earlier, nothing later (`lib/mech_regime.py:5-6`). The fill is the next close.
- **Thresholds.** They are module constants `VIX_EVOL_LEVEL = 30.0` and `VIX_EVOL_PCT = 0.25`. They
  were frozen in the 2026-07-22 spec, before this study, and never iterated against P&L
  (`research/archive/06-mech-regime-and-shipped-exits.md`, addendum 3 and its leak-door list).
- **In-sample table.** `backtests/mech_regime/spy_base_rate_daily.csv`, which runs from 1993. Rows are
  cut at 2026-09-22 before the label is computed.
- **Forward table.** `backtests/mech_regime/spy_vix_daily_full.csv`, the production table refreshed
  nightly by `scripts/collector/daily/fetch_mech_regime.py` and read by `scripts/regime_watch.py`.

**LIVE or RETRO.** Every in-sample label is a RETRO computation. No log of the label as printed on
each day covers the window, so the run recomputes it from stored closes. This differs from the
model's labels, whose RETRO rows were written with hindsight
([`market_read`](../f1_selection/regime/market_read.md)). The mechanical rule has no judgment in it.
A recomputation equals the live value whenever the stored VIX closes equal the closes published that
day. The residual risk is a revised VIX close in the source. Gate GL below checks the two tables
against each other. It cannot check either against a contemporaneous print. A second reader must see
this limit.

_Resolved at draft (2026-11-27):_ two tables, because the production table starts 2023-06-01 and the
in-sample window starts 2022-03-01.

### Onsets

- **Onset `D`.** A session whose label is `E-VOL`, where none of the 5 sessions before `D` is
  `E-VOL` and all 5 carry a vol label.
- **Re-arm.** 5 sessions. With a 5-session hold, two onset trades never overlap. With the printed
  10-session hold they can.

_Resolved at draft (2026-11-27):_ a prior session with no vol label blocks the onset. It is counted
as `no_rearm_history`.

### Calm weeks, `ARM C`

`ARM C` is the control: the same structures opened on weeks with no vol expansion.

- **Calm week.** An ISO week inside the window. Its `D` is the week's first session.
- **Calm condition.** No `E-VOL` on `D` or on any of the 5 sessions before `D`, and all 6 carry a
  vol label. A week failing it has no calm entry and is counted.
- **Entry.** The calm `D` enters at `F` by every rule below.
- **Columns.** `ARM C` prices all three structures at the headline expiry, at both holds. Its columns
  are `C-S`, `C-BC` and `C-BP`.

_Resolved at draft (2026-11-27):_ item 18 names a "calm-week ARM C" and does not define it. The
definition above mirrors the non-`E-VOL` grid of the 2026-11-06 descriptive count. It is not
`selloff_put_diagonal.calm_days`, which picks weeks near a 63-session high. That rule would make the
control a low-vol, near-high state rather than "no expansion".

### Structures, fixed here

| Arm | Legs, one unit |
|---|---|
| `ARM S` | +1 ATM call, +1 ATM put |
| `ARM BC` | −1 ATM call, +2 wing calls |
| `ARM BP` | −1 ATM put, +2 wing puts |

- **Headline expiry.** `mechanical_benchmark.monthly_for(F, 30, (21, 122))`: the standard monthly
  nearest 30 DTE with at least 21 DTE at `F`. Ties go to the earlier. All legs share it.
- **Strike grid.** A fixed $1 step for SPY. The cache never moves the grid.
- **ATM.** The $1 strike nearest `F`'s spot with both a call and a put listed by `F`. All three
  arms use the same ATM strike on one onset.
- **Wing call.** The $1 strike nearest spot × 1.05, strictly above ATM, listed by `F`.
- **Wing put.** The $1 strike nearest spot × 0.95, strictly below ATM, listed by `F`.
- **The walk.** `daily_vol_structure.walk_strike` with `step = 1.0` and `asof = F`. Nearest first,
  ties to the lower strike. A trade awaiting a fetch keeps the run at `NOT BUILT`.
- **Same close.** Strikes are chosen on the `F` close that fills the trade.

_Resolved at draft (2026-11-27):_ the fixed $1 step replaces `mechanical_benchmark`'s grid, which uses
$5 above a $250 spot unless cached strikes are finer. SPY sits above $250 throughout the window, so
that grid could put ATM up to $2.50 from spot.

_Resolved at draft (2026-11-27):_ a failed ATM drops all three arms on that onset. A failed wing drops
only its own arm.

### Fills, marks and cost

- **Entry fill.** Every leg at `F`'s own closing quote, through `simulate.entry_day_fill(row, q)`
  with the leg's signed quantity. A two-sided quote fills at its mid. No leg is priced off another day.
- **Junk quote.** The production rule applies: bid ≤ 0, or spread > mid, or spread > twice the
  legacy Cboe width (`simulate._is_junk_quote`). A bought junk leg with a bid fills at its mid. A
  bought leg with no bid is refused (`junk_entry_quote`). A sold junk leg fills at its bid or 0.
- **Exit mark.** `selloff_put_diagonal.leg_mark` on the exit session: the closing mid, or on a junk
  quote its `Latest` if it traded. A leg with no row that day drops the trade (`no_exit_quote`). So
  does a mark carried from an earlier day (`stale_exit_mark`).
- **Commission.** $0.65 per contract per side, slippage 0. That is $2.60 per straddle and $3.90 per
  1x2, entry and exit together.
- **Model prices.** None.

_Resolved at draft (2026-11-27):_ the side-aware production fill is used, not the all-mid mirror
`daily_vol_structure` needed for its front ratios. This study has no front ratio. The count of trades
where a sold leg took its bid prints per arm.

### R, fixed here

R is net P&L over the most the unit can lose at expiry, commission included.

| Term | Definition, in option points unless marked |
|---|---|
| `N`, entry net | Σ q × fill over the legs, q signed (+ bought). Positive is a debit, negative a credit |
| `L`, max loss at expiry | `ARM S`: `N`. `ARM BC`: (wing − ATM) + `N`. `ARM BP`: (ATM − wing) + `N` |
| Basis, dollars | `L` × 100 + all commission |
| Exit value | Σ q × mark over the legs at the exit session |
| P&L, dollars | (Exit value − `N`) × 100 − all commission |
| R | P&L / Basis |

**Why this unit.** A 1x2 can open for a credit or a debit, so a debit-based R breaks on credit rows.
Its loss is largest when spot ends at the wing strike. That loss is the width plus the debit, or the
width minus the credit. It is positive whenever the quotes are sane, so one formula serves every row.
For the straddle the same formula gives the debit. Every arm's R is therefore P&L per dollar the unit
can lose.

- **The floor near −1.** Before expiry, a call 1x2 is worth at least minus the width, by the vertical
  spread bound. The put side is the same. So R falls below −1 only on inconsistent marks. Such rows
  are kept and counted, never floored.
- **Refusals.** `L` ≤ 0 refuses the trade (`nonpositive_max_loss`). A straddle with `N` ≤ 0 is
  refused the same way.
- **Not from the helper.** No capital-at-risk figure comes from `helpers._defined_risk_bounds`
  (build trap 2, below).
- **Printed beside R.** P&L in dollars per unit, and P&L as a share of `F`'s spot.

**Size against the stop.** On SPY one 1x2 unit risks roughly the 5% width, near $3,500 at a $700
spot. That is unverified arithmetic. The operator closes on a $1,000 loss
(`operator_sizes_on_1000_stop`). A stop cell prints: each trade closed at the first daily close
from `F + 1` on where its open P&L reaches −$1,000. Daily closes can overshoot the stop. The stop
cell is not graded and is not in the PBO grid.

### Build traps, fixed here

- **Trap 1, the credit exit profile.** `simulate._exit_basis` returns `"CREDIT"` when `entry_net < 0`
  (`scripts/backtest/simulate.py:784-785`). Such a row takes `CREDIT_PROD`: a 65% target, no stop and
  no time exit (`scripts/backtest_study/lib/book.py:187-188`). One 1x2 arm could split across two
  profiles. This study uses only its own fixed exit. It never calls the harness exit scan,
  `_exit_basis` or `book.py`'s profiles.
- **Trap 2, the bounds asymmetry.** `helpers._defined_risk_bounds` returns `None` when net call
  quantity is not zero (`scripts/backtest/helpers.py:53-54`). So `simulate._entry_outside_bounds`
  can refuse `ARM BP` rows and never `ARM BC` rows. This study never uses it to refuse a trade. It
  still calls it, and the count it would have refused prints per arm.

### Refusals and drops

Every entry that does not price is counted by reason and by arm, and leaves the cell.

| Case | Reason |
|---|---|
| No monthly meets the expiry rule | `no_monthly` |
| No listed ATM or wing strike | `no_listed_strike` |
| A leg has no quote on `F` | `no_entry_quote`; no later day is tried |
| A bought leg is junk with no bid | `junk_entry_quote` |
| Strike-order violation on `F` | `non_monotonic_entry_quote`, via `simulate._monotonicity_violation` |
| `L` ≤ 0, or a straddle with `N` ≤ 0 | `nonpositive_max_loss` |
| A leg has no row at the exit, or a carried mark | `no_exit_quote`, `stale_exit_mark` |
| No spot on `F` or the exit | `no_spot` |

### Terms used here

| Term | Meaning |
|---|---|
| Backspread, 1x2 | Short one ATM option and long two further out, same type and expiry |
| [MFE / MAE](../../glossary.md#mfe) | The best and worst open R on the daily mark path |
| [Capture](../../glossary.md#capture) | Sum of R over sum of MFE |
| Implied-move ratio | \|ln(spot at exit ÷ spot at `F`)\| ÷ (0.8 × ATM IV at `F` × √(h/252)) |
| ATM IV change | Mean IV of the ATM call and put at the exit minus at `F`, in vol points as cached |
| Holm | A step-down correction for testing several things at once |
| PBO / CSCV | The chance that the best cell in one half of the history ranks below the median in the other half. `lib/pbo.py` holds the method |

## Dependencies

- `lib/mech_regime.py::compute_mech_table` and its frozen constants, on the two tables above.
- `scripts/backtest_study/f1_selection/regime/state_map.py`: `build_cal` for spot, and its
  `backtests/state_map/SPY.csv`.
- `scripts/backtest_study/f3_structure/daily_vol_structure.py`: `walk_strike`, `SELLOFF_WINDOWS`.
- `scripts/backtest_study/f1_selection/benchmark/mechanical_benchmark.py`: `monthly_for`,
  `monthly_expiries`, `listed_by`.
- `scripts/backtest_study/f1_selection/regime/selloff_put_diagonal.py`: `leg_mark`, `holm`.
- `scripts/backtest/simulate.py`: `entry_day_fill`, `_is_junk_quote`, `_monotonicity_violation`,
  `_entry_outside_bounds`. `scripts/backtest/helpers.py::_defined_risk_bounds`, as a count only.
- `scripts/backtest_study/lib/pbo.py`: `cscv`, `ratio_metric`, `pad_head`.
- `scripts/backtest_study/lib/era.py`: `CURRENT`, `SEAL_START`, `SEAL_LIFTED`.
- The SPY files in `backtests/option_history_cache/` and `_unlisted.jsonl`.
- `scripts/backtest_study/lib/harness.py` is not read. Nothing in `book.py`'s exit profiles is read.
- A collector under `scripts/collector/study_legs/f3_structure/`. Its fetch list follows the rules
  above, never an outcome. It prints its contract count in a dry run first. It refuses while another
  cache writer runs, and `scripts/backup_research_caches.py push` follows it.

## Population and basis, fixed here

| Window | Dates `D` | Use |
|---|---|---|
| In-sample | 2022-03-01 to 2026-09-22 | Every in-sample verdict |
| Gap | 2026-09-23 to 2026-11-26 | In no population |
| Forward | From 2026-11-27 | The one-shot forward read |

- **The cut.** No SPY close, VIX close or option quote after 2026-09-22 enters the in-sample run.
  Every series is cut before anything is computed.
- **Same candidate entries.** Every cell, `ARM C` included, starts from entries whose `D + 11` close
  falls on or before 2026-09-22. So the 5- and 10-session holds share entries. An entry failing this
  is counted as `n_truncated`.
- **Per-cell drops.** After that, each cell keeps or drops entries by its own pricing rules and
  prints its own counts. Entries are not intersected across cells.
- **Era.** The inputs carry no prompt version. The report prints `era: current (inputs are
  unversioned market closes and option quotes)`.
- **The seal and the gap.** The in-sample end is the day before `era.SEAL_START` (2026-09-23). The
  [holdout seal](../f4_deployment/holdout_seal.md) binds play signal dates, and this study reads no
  play. The seal was lifted on 2026-11-26 (`era.SEAL_LIFTED`). The lift does not move this window.
  Dates from 2026-09-23 to 2026-11-26 are neither in-sample nor forward.

_Resolved at draft (2026-11-27):_ the gap is the conservative reading. The README gives no rule for
dates between an in-sample end and a registration date. The current sell-off sits in the gap, and it
was seen before registration (see below). Excluding the gap keeps a known episode out of both reads.

- **Report header.** Era, the windows, the git sha, the dirty flag, the input files, and each
  series' first and last date read.

## Plan-time observations, disclosed

The in-sample window is not blind. Each item below was seen before this file was written.

### The read-only census, 2026-11-06

A read-only census of the option cache counted onsets and quote coverage
([`next-steps.md`](../../next-steps.md#waiting-on-the-operator) item 18).

| What it found | Count |
|---|---|
| Onsets with a 5-session re-arm | 29 |
| Straddle legs quoted at entry and at exit | 29 |
| Each 1x2 quoted at entry and at exit | 28 |

- **What it saw.** Which cached strikes had a row with a positive bid on each entry and exit date.
  It took the nearest cached strike and applied no strike tolerance, junk-quote rule or 21-DTE floor.
- **What it did not record.** No P&L, mid change or return is recorded from it. The record does not
  say whether quote values were printed. Treat quote values as possibly seen.
- **An upper bound.** The priced count here can be lower. The calm grid was not censused.

### The 23-onset print, 2026-11-06

While counting onsets for the proposal, SPY and VIX moves after 23 onsets from 2023-06 to
2026-09-22 were printed
([entry](../../current.md#2026-11-06--long-straddles-and-backspreads-after-a-vol-expansion-untested-one-spy-study-proposed)).

- **What it saw.** VIX fell after 15 of the 23. SPY's moves were printed too.
- **What it did not see.** No option price was read.
- **What it touched.** It shaped no design choice. It is inside this window, so the direction of
  VIX after most in-sample onsets is known. A long-vega position loses when VIX falls.
- **Why 23, not 29.** The 23 came from the production table, which starts 2023-06-01. The census
  covered the window from 2022-03.

### The 1993–2022 descriptive count, 2026-11-06

Over 140 onsets from 1993 to 2022-02, SPY moved no more relative to implied than on other days, and
VIX fell after 72% of onsets ([entry](../../current.md#2026-11-06--long-straddles-and-backspreads-after-a-vol-expansion-untested-one-spy-study-proposed)).
It ends before this window and read no option price. It motivated printing the 10-session hold.

### Other studies seen on the same state

| Study | What was seen |
|---|---|
| [`signal_call_calendar`](../f1_selection/regime/signal_call_calendar.md) | `K-EVOL` printed `NULL` on 22 SPY call calendars after `E-VOL` onsets with a 10-session re-arm, 2026-11-21. A calendar is long vega |
| [`state_map`](../f1_selection/regime/state_map.md) | Q3 printed SPY returns after each `S-EVOL` onset, 10-session re-arm, from 2016. Q4 priced a put spread on 39 onsets from 2022-02 |
| [`index_vrp`](index_vrp.md) | SPY's high-VIX tercile paid sellers +3.41 points over 14 cycles, a descriptive cut |
| [`structure_sweep`](structure_sweep.md), [`earnings_vol`](earnings_vol.md) | Long-straddle verdicts on other triggers, both `NULL` |

- **What it spends here.** SPY's path after most in-sample onsets is known from `state_map` Q3.
  The `S-EVOL` onsets there use a 10-session re-arm, so they are close to a subset of these onsets. Their source table differs.

### The current sell-off

The [2026-11-21 entry](../../current.md#2026-11-21--bear-strategies-in-2026-peek-ungraded-sealed-dates)
showed SPY falling 11.5% from 2026-10-06 to 2026-11-20, with `E-VOL` holding on 2026-11-20. It is in
the gap and in no population.

### What the drafter read

The drafter read registrations, the plan, code and the research log. The drafter read no option price
and no SPY return for any onset. Two exposures are disclosed:

- **Table edges.** The first and last rows of both label tables: 1993-01-29, 2023-06-01, 2026-09-24
  and 2026-11-25. The last two are outside the in-sample window.
- **The study index.** The latest-outcome lines in the [README](../README.md), including those above.

### Choices with no source

- **Hold length.** 5 sessions graded and 10 printed. No source supports either.
- **Wing.** Spot × 1.05 and × 0.95. No source supports it. It follows the 2026-11-06 model
  illustration, which is not evidence of returns.

### A prior, not evidence

- **Power is thin.** Assuming a five-session R standard deviation of 0.25 (unmeasured), 29 trades
  give a CI half-width near 0.09 R. A `NULL` means no large effect.
- **The likeliest outcome**, written now: `ARM S` `NULL` or `CONTRARY`. The backspreads `NULL` or
  `UNDERPOWERED`.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `ARM S` | arm | Straddle on onsets, headline cell | Graded |
| `ARM BC` | arm | Call 1x2 on onsets, headline cell | Graded |
| `ARM BP` | arm | Put 1x2 on onsets, headline cell | Graded |
| `ARM C` | control | The three structures on calm weeks | The reference for every gain |
| 12 cells | descriptive cut | Structure × hold × expiry, below | PBO grid; printed only |
| Diagnostics | descriptive cut | MFE, MAE, implied-move ratio, ATM IV change, stop cell | Printed only |
| `FORWARD` | population scope | The three arms on forward onsets | Forward verdict |

`ARM S`, `ARM BC` and `ARM BP` each earn one verdict. Their headline cell is the 5-session hold at
the headline expiry.

### The 12 cells, fixed here

| Cell | Structure | Hold | Expiry |
|---|---|---|---|
| 1 | S | 5 sessions | Headline: nearest 30 DTE, at least 21 |
| 2 | S | 10 sessions | Headline |
| 3 | S | 5 sessions | Nearest 60 DTE, at least 45 |
| 4 | S | 10 sessions | Nearest 60 DTE, at least 45 |
| 5 | BC | 5 sessions | Headline |
| 6 | BC | 10 sessions | Headline |
| 7 | BC | 5 sessions | Nearest 60 DTE, at least 45 |
| 8 | BC | 10 sessions | Nearest 60 DTE, at least 45 |
| 9 | BP | 5 sessions | Headline |
| 10 | BP | 10 sessions | Headline |
| 11 | BP | 5 sessions | Nearest 60 DTE, at least 45 |
| 12 | BP | 10 sessions | Nearest 60 DTE, at least 45 |

- **The 60-DTE expiry.** `mechanical_benchmark.monthly_for(F, 60, (45, 122))`, with the same strike
  rules.
- **Graded cells.** 1, 5 and 9 only.

_Resolved at draft (2026-11-27):_ the axes are structure, hold and expiry. The grid holds every
variant the report prints, so a reader picking the best printed variant is inside the PBO. Hold uses
the two registered lengths, which adds no fetch. Strike offset is not an axis, because the straddle
has none and the grid would not be balanced. The expiry axis has one alternative, the smallest
addition that applies to all three structures.

## How it is judged

### Statistic

For each graded arm:

- **Mean R** is trade-weighted: the sum of R over priced trades divided by their count.
- **Gain.** Mean R on the arm minus mean R on the same `ARM C` column, same hold and expiry.

### Bootstrap

- **Unit.** Calendar-month clusters of `D`, for onsets and for calm weeks. Each draw resamples the
  arm's clusters with replacement, as many as it holds.
- **Draw statistic.** The trade-weighted mean R over every trade in the drawn clusters.
- **Gain.** In the same draw, `ARM C`'s clusters are resampled on their own. The gain in a draw is
  the arm's draw mean minus `ARM C`'s draw mean.
- 10,000 draws, seed 20261127.
- **CI.** The 2.5th and 97.5th percentiles. Each CI prints its half-width.
- **p-value.** Two-sided: twice the smaller of the share of draws at or below 0 and the share at or
  above 0, capped at 1.

Month clusters miss correlation across a month boundary, so the CI is somewhat too narrow. Calm-week
holds overlap the next week's entry by one session, which month clusters absorb.

### Multiple comparisons

| Family | Members | m |
|---|---|---|
| Mean R | `ARM S`, `ARM BC`, `ARM BP`, headline cell | 3 |
| Gain | `ARM S`, `ARM BC`, `ARM BP`, headline cell | 3 |

Holm at 0.05 within each family, with `selloff_put_diagonal.holm`. An arm with no p-value enters as
1.0, so m stays 3. The 12 cells test nothing.

_Resolved at draft (2026-11-27):_ item 18 says "Holm over arms, and the difference from ARM C". It is
read as two families of three, as in `signal_call_calendar`.

### PBO / CSCV

The selection guarded against is picking the best of the 12 cells.

- **Configs.** The 12 cells, onset trades only.
- **Rows.** Calendar quarters of `D`, 2022 Q1 to 2026 Q3, so 19. One zero quarter is padded at the
  head with `pbo.pad_head`, giving T = 20 and S = 20 blocks of one quarter.
- **Per-period value.** [sum of R, trade count] for the cell's trades in the quarter.
- **Metric.** `pbo.ratio_metric`, so a half's value is its mean R.
- **Not computable.** If PBO cannot be computed, it prints "not computed". Then the positive words
  cannot print, and an arm that would earn one prints `NULL` with "PBO not computed".

## Gates

The design names five gates, C0 to C4. They decide which verdict words can print. C0 to C4 are
gate ids; `ARM C` is the calm control, and the letters are unrelated.

- **C0, power.** At least 20 priced trades in the arm's headline cell, and at least 60 priced calm
  weeks in its `ARM C` column. Otherwise the arm is `UNDERPOWERED`.
- **C1, sign.** The Holm-adjusted mean-R and gain tests above, with their CIs.
- **C2, leave-one-out.** With each single month cluster removed in turn, the mean R keeps the sign of
  the full-sample mean. For `LONG-VOL-PAYS` the gain must keep its sign too.
- **C3, sell-off windows cut.** With every `D` in 2025-03-01 to 2025-04-30 or 2026-02-01 to
  2026-04-30 removed, from the arm and from `ARM C`, the mean R keeps its sign. For
  `LONG-VOL-PAYS` the gain must keep its sign too. These are `vol_sleeve`'s windows, as
  `daily_vol_structure.SELLOFF_WINDOWS` holds them.
- **C4, PBO.** A positive word needs PBO below 0.50. A PBO of 0.50 or more bars promotion.

_Resolved at draft (2026-11-27):_ C2 removes a month cluster, not a single trade. A cluster is the
bootstrap unit, and removing it is the stricter test.

_Resolved at draft (2026-11-27):_ item 18 reads "0.5 or more bars promotion". So exactly 0.50 bars.
C4 guards the positive words only. `CONTRARY` picks no cell, so it does not need C4.

### Run gates

A failed run gate refuses the run (non-zero exit).

- **GE, inputs.** Both label tables, `backtests/state_map/SPY.csv` and the option cache exist. The
  in-sample table reaches 2026-09-22.
- **GL, label agreement.** On `D` from the production table's eleventh row to 2026-09-22, the onset
  dates from the two tables are identical. A mismatch refuses and prints the dates.
- **GX, no lookahead.** Strike, expiry and listing choices read nothing after `F`. A test changes
  every later quote and close and requires identical choices.
- **GC, the cut.** The in-sample report is identical when every close and quote after 2026-09-22 is
  changed. A test checks it.
- **Await gate.** Nothing is priced until every headline entry, in all three arms and `ARM C`, has
  its contracts cached or a recorded refusal. Until then the report prints its census and
  `NOT BUILT — AWAITING SCRAPE`. A non-headline cell still awaiting prints `NOT BUILT` for that cell,
  and PBO prints "not computed".
- **Census first.** Onset and calm counts, the fetch list and every drop by reason print before any
  price is read.

_Resolved at draft (2026-11-27):_ GL starts on the production table's eleventh row. From there `D` and
its 5 re-arm sessions each have a full five-day VIX change in both tables.

## Bar for a candidate

No result here makes a rule. A `LONG-VOL-PAYS` files "to be tested" in
[`deployment-evidence.md`](../../deployment-evidence.md), pending the forward read.

## Verdicts, worded now

### Per graded arm, in-sample

The first matching row is the verdict. Word meanings are in [The question](#the-question).

**`UNDERPOWERED`.** C0 fails: fewer than 20 priced trades in the arm, or fewer than 60 priced calm
weeks in its `ARM C` column. The census prints and nothing is concluded.

**`LONG-VOL-PAYS`.** All of these hold:

1. The mean R CI lower bound is above 0.
2. The mean R Holm-adjusted p is below 0.05.
3. The gain CI lower bound is above 0.
4. The gain Holm-adjusted p is below 0.05.
5. C2 holds for the mean R and the gain.
6. C3 holds for the mean R and the gain.
7. PBO is below 0.50 (C4).
8. The exit-drop check below holds.

**`PAYS-NOT-SIGNAL`.** Conditions 1, 2 and 7 hold, C2 and C3 hold for the mean R, and the exit-drop
check holds. Condition 3 or 4 fails.

**`CONTRARY`.** All of these hold:

1. The mean R CI upper bound is below 0.
2. The mean R Holm-adjusted p is below 0.05.
3. C2 and C3 hold for the mean R.
4. The exit-drop check holds.

**`NULL`.** Otherwise, printed with the half-width. The reason prints beside it: "PBO veto", "PBO
not computed", "C2 fails", "C3 fails", "exit-drop sensitive", or none.

The words cannot overlap. `LONG-VOL-PAYS` and `PAYS-NOT-SIGNAL` need the mean R CI above 0, and
`CONTRARY` needs it below 0. `LONG-VOL-PAYS` needs conditions 3 and 4, and `PAYS-NOT-SIGNAL` needs
one of them to fail.

**Exit-drop check.** Exit drops (`no_exit_quote`, `stale_exit_mark`) depend on where spot went, so they
can bias R.

- For a positive word, every exit-dropped onset trade is set to R = −1. The bootstrap, Holm, C2 and
  C3 re-run, and the word's own conditions are checked again.
- For `CONTRARY`, every exit-dropped onset trade is set to the arm's largest priced R, and the same
  re-run follows.
- `ARM C` keeps its exit drops out in both re-runs.
- A word that fails its re-run prints `NULL` with "exit-drop sensitive".

### Printed only, no verdict

- **The 12 cells.** Mean R, its CI and count. The gain where `ARM C` prices, which is the headline
  expiry at both holds.
- **`ARM C`.** Mean R and CI for each column and hold.
- **MFE and MAE**, on the daily mark path from `F + 1` through the exit, with the R formula. A session
  with no mark is skipped. Capture prints beside them.
- **Implied-move ratio and ATM IV change**, per trade and as means per arm and `ARM C` column.
- **The stop cell**, per arm and per `ARM C` column: mean R and the count of stops.
- **Per trade.** `D`, `F`, strikes, expiry, DTE, `N`, `L`, R, dollars and the exit reason.
- **Counts.** Every drop and refusal by reason and arm, R below −1, sold legs filled at the bid,
  credit and debit entries per 1x2 arm, and the `_entry_outside_bounds` count per arm.
- **Two caveats**, word for word: "A long-straddle `CONTRARY` is not evidence for selling straddles,
  because no short side is graded." "A backspread result says nothing about tail loss beyond five
  sessions or about margin."

### Forward

- **Opens 2026-11-27.** One shot, on frozen definitions, on the headline cells only.
- **Forward onsets.** Onsets with `D` on or after 2026-11-27 whose 5 re-arm sessions also fall on or
  after 2026-11-27. An `E-VOL` run in force on 2026-11-26 never counts.
- **Forward calm weeks.** Calm weeks with `D` on or after 2026-11-27, under the same rules.
- **Floor.** 20 priced forward trades per arm and 60 priced forward calm weeks per column. At about
  six onsets a year, 20 onsets take about three and a half years, so near mid-2030.
- **Conditions.** The in-sample conditions, less C3 and C4. C3's windows hold no forward date, and no
  cell is selected forward. C2 and the exit-drop check apply.
- **Holm.** The same two families, m = 3 each.
- **Words.** The in-sample tokens, with `STILL-OPEN` in place of `UNDERPOWERED`.
- **Verdict of record.** The first forward run in which an arm prints a token other than
  `STILL-OPEN`. Later forward runs are descriptive.
- **Sunset.** 2031-11-27. An arm still `STILL-OPEN` then keeps `STILL-OPEN` as its final word.

_Resolved at draft (2026-11-27):_ the forward floor equals C0, so the forward read can only conclude
what the in-sample read could.

### The banner

The report's section titled VERDICT prints:

```
>>> vol_expansion_long_vol ARM S (ATM straddle after E-VOL onset, D+1 close to D+6 close, monthly ~30 DTE, 2022-03-01 to 2026-09-22): LONG-VOL-PAYS | PAYS-NOT-SIGNAL | CONTRARY | NULL | UNDERPOWERED <<<
>>> vol_expansion_long_vol ARM BC (call 1x2 -1 ATM +2 at 1.05, same): LONG-VOL-PAYS | PAYS-NOT-SIGNAL | CONTRARY | NULL | UNDERPOWERED <<<
>>> vol_expansion_long_vol ARM BP (put 1x2 -1 ATM +2 at 0.95, same): LONG-VOL-PAYS | PAYS-NOT-SIGNAL | CONTRARY | NULL | UNDERPOWERED <<<
>>> vol_expansion_long_vol PBO (12 cells): <value> <<<
>>> vol_expansion_long_vol FORWARD (onsets from 2026-11-27): ARM S <w> ARM BC <w> ARM BP <w> <<<
```

Each arm line carries the note "VIX direction after 23 in-window onsets was printed before
registration".

## Anti-tuning

- **Fixed here, the inputs.** The label, its tables, the re-arm, the calm-week rule and the windows.
- **Fixed here, the design.** The structures, the wing, both expiry rules, the strike grid and walk,
  the fill, the exit, both holds, the cost, R and the drop rules.
- **Fixed here, the judging.** The floors, the seed, the clusters, the Holm families, the 12 cells,
  the PBO rows and bar, C2, C3's windows, the exit-drop check and the verdict words.
- The 12 cells and every printed-only cut appear as they fall. None re-grades an arm.
- No other structure, wing, hold, expiry, stop or ticker is graded. Any of them is a new
  registration.
- The in-sample run reads nothing after 2026-09-22. The forward read opens on 2026-11-27. No later run
  moves either date.
- This registration is immutable in substance. Editorial consolidation only.

## What could ship

Nothing ships from this study.

- A `LONG-VOL-PAYS` files "to be tested" in [`deployment-evidence.md`](../../deployment-evidence.md),
  pending the forward read.
- Any rule built on a result here needs its own registration and an operator decision.
- No verdict changes a tier, a veto, a size class, an exit, the deploy card, the analysis prompt or
  the hedge sleeve in [§4](../../../docs/deployment-rules.md#s4).
- Before any live 1x2, check that the journal labels unequal leg quantities as a ratio
  (`research/robustness-review.md:80`). Otherwise a 1x2 can read as a 1-lot vertical.
