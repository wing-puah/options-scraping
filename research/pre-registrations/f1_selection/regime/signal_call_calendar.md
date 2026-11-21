## signal_call_calendar — after a mech BEAR or E-VOL signal, does a SPY call calendar pay?

<!-- outcome:start -->
> Latest outcome: not run.
<!-- outcome:end -->

_Registered 2026-11-21 (accepted by default; immutable in substance)._

**STATUS: REGISTERED · ACCEPTED BY DEFAULT, NOT YET RUN**, on the plan's defaults in
[`next-steps.md` §2.32](../../../next-steps.md) (the operator's standing rule of 2026-10-09). No
calendar was priced and no SPY option price or return for a signal date was read before this file
was written.

A fresh second reader checked the draft on 2026-11-21, before any outcome existed. Its read was
READY WITH LISTED FIXES. Every fix is folded in below, and its rulings are listed under
[Second reader (2026-11-21)](#second-reader-2026-11-21).

## The question

The operator asked on 2026-11-21 whether an out-of-the-money call calendar pays after a bear
signal. This study turns that into one mechanical SPY rule and asks two things.

| Question | Comparator |
|---|---|
| After a mech `S-BEAR` or `S-EVOL` onset, is the calendar's mean R above 0, net of commission? | none |
| Is it above the same calendar opened on a calm day? | `selloff_put_diagonal.calm_days` |

**Why one study.** Near-dated options are rich after the signal, and a calendar sells them. Its
loss is capped at the debit paid. Two results argue against it:

- `tail_rebound` found no rebound edge after SPY tail falls.
- The earnings calendar's edge in `earnings_vol` was the bid-ask spread.

What each verdict word would mean for the operator:

| Word | Meaning |
|---|---|
| `CALENDAR-PAYS` | The calendar made money after the signal, and more than on calm days |
| `PAYS-NOT-SIGNAL` | The calendar made money after the signal, but a calm day did as well. The signal adds nothing |
| `CONTRARY` | The calendar lost money after the signal |
| `NULL` | Nothing was shown either way |
| `UNDERPOWERED` | Too few signal months to judge. Nothing is concluded |

No verdict changes a production rule.

## What this study is not

- **Not a new signal search.** The signals are `state_map`'s Q3 onsets, imported unchanged. No
  other state, threshold or re-arm is graded.
- **Not a re-grade of `state_map` Q4.** Q4 priced a put spread on these onsets. This study prices
  a different structure on the same onsets and reads no Q4 figure.
- **Not intraday.** The operator's view that puts pay intraday cannot be tested here. Every price
  is a daily close.
- **Not a geometry search.** One geometry is graded. The others print and never promote.
- **Not a hedge of the book.** No analysis row, play row or backtest row is read.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price basis

- **Session.** A date with a SPY close in `state_map`'s calendar (`state_map.build_cal`).
- **Spot.** The SPY unadjusted close on the entry session.
- **Hold return.** `ln(A[exit] / A[entry])`, with `A` the SPY `Adj Close`. It is used only by a
  printed split.
- **VIX and VIX3M.** The `^VIX` and `^VIX3M` closes in `backtests/state_map/`, matched to SPY
  sessions by exact date.

### Signals

Signals are `state_map`'s Q3 onsets. They are read through `state_map.onsets` on
`state_map.state_flags(mech_labels(cal, 50), mech_labels(cal, 200))`.

| Label | State | Role |
|---|---|---|
| `S-BEAR` | mech direction BEAR (50-day SMA) | Graded |
| `S-EVOL` | mech vol E-VOL | Graded |

- **Onset, `D`.** A session on which the state holds, where none of the 10 sessions before `D`
  held it and all 10 had a state. The re-arm is 10 sessions (`state_map.REARM`).
- **Entry session.** `D + 1`. The label is known at `D`'s close.
- **Both at once.** An onset of both signals on one `D` enters `K-BEAR` once and `K-EVOL` once.
  The arms are graded separately, so an entry is never counted twice within one arm.

### The calendar, fixed here

| Item | Headline rule |
|---|---|
| Underlying | SPY only |
| Short leg | 1 short call, standard monthly nearest 30 DTE among those at least 21 DTE |
| Long leg | 1 long call, same strike, standard monthly after the short's, nearest 60 DTE |
| Strike | Listed strike nearest spot × 1.03, on the short expiry's listed grid |
| Entry | Both legs at the closing mid of `D + 1`, via `simulate.entry_day_fill` |
| Exit | Both legs at the close of `D + 1 + 21`, or at the short's expiry close if earlier |
| Cost | $0.65 per contract per leg-side, slippage 0 |
| Size | 1 calendar; the graded unit is R |

- **Short expiry.** `mechanical_benchmark.monthly_for(entry, 30, (21, 122))`: the monthly nearest
  30 DTE with at least 21 DTE, ties to the earlier. Its DTE runs from 21 to about 55 days.
- **Long expiry.** Among `mechanical_benchmark.monthly_expiries` dates strictly after the short's
  expiry, the one nearest 60 DTE (90 DTE in its parameter cell), ties to the earlier.
- **DTE.** Calendar days from the entry session.
- **Monthlies only.** Weeklies are not used, as in `selloff_put_diagonal` and `state_map` Q4.
- **Strike walk.** `selloff_put_diagonal.nearest_listed` with option type `Call`, on
  `mechanical_benchmark`'s listing grid, as of the entry session.
- **Same close.** The strike is chosen on the same `D + 1` close that fills the trade, as in
  `state_map` Q4.
- **Long strike.** The long leg uses the short leg's strike. If that strike is not listed on the
  long expiry by the entry session, the entry is dropped and counted.
- **Short-expiry exit.** When the short expires before `D + 1 + h`, both legs close on its
  expiry day. The short takes the expiry-day rule and the long takes the daily mark.
- **Exit marks.** `selloff_put_diagonal.leg_mark`: production's daily mark with
  `simulate.junk_day_mark` on a junk quote. On its expiry day a leg takes the closing mid, or
  intrinsic value when the quote is junk or missing.

### R, fixed here

R is the calendar's net P&L over the cash it put at risk, commission included.

| Term | Definition |
|---|---|
| Debit | Long leg's fill minus short leg's fill, in option points |
| Exit value | Long leg's mark minus short leg's mark, floored at 0 |
| Cost | 4 leg-sides × $0.65 = $2.60, entry and exit together |
| Basis | Debit × 100 + Cost |
| P&L | (Exit value − Debit) × 100 − Cost |
| R | P&L / Basis |

- **The loss is capped at −1.** The exit value is floored at 0, so the worst P&L is minus the
  basis. R can never fall below −1.
- **Why the floor.** A same-strike call calendar is worth at least 0 before the short expires. A
  negative exit value is a mark artifact. Every floored exit is counted and printed.
- **Exit commission.** It is charged even when the exit value is 0. It is also charged when the
  short expires worthless, which is the conservative choice.
- **Gross R.** `(Exit value − Debit) / Debit`, with no commission, prints beside R.
- **Defined-risk clamp.** `helpers._defined_risk_bounds` returns None for any two-expiry leg set,
  so it never clamps a calendar. The floor at 0 above takes its place. It is still called, and its
  bound count prints as a check (expected 0).

### Refusals and drops

Every entry that does not price is counted by reason and by arm, and leaves the cell.

| Case | What happens |
|---|---|
| Debit priced to a credit or to 0 | Refused, reason `debit_priced_to_credit` |
| Long call priced at or below the short call (expiry order) | Refused as `debit_priced_to_credit`, the row above |
| A bought leg is junk with no bid | Refused, `simulate.JUNK_ENTRY_REFUSAL` |
| A leg has no quote on the entry session | Dropped, `no_entry_quote`; no later entry day is tried |
| No listed strike on the short expiry | Dropped, `no_listed_strike` |
| The short's strike is not listed on the long expiry | Dropped, `long_strike_unlisted` |
| No monthly meets a leg's DTE rule | Dropped, `no_monthly` |
| A leg cannot be marked at the exit | Dropped, `exit_unmarked`; see the sensitivity line below |

- **Monotonicity check.** `simulate._monotonicity_violation` compares same-expiry legs only and
  cannot fire on a calendar. It is still called, and its count prints.
- **Unlisted and no-history contracts.** `nearest_listed` steps past a strike on the skip-list
  (`backtests/option_history_cache/_unlisted.jsonl`) and past a cached strike with no row by the
  entry session. A strike that is neither cached nor skip-listed makes the entry
  `AWAITING SCRAPE`.
- **No other substitution.** An entry is never built on another expiry or a strike beyond that
  walk.

### Calm days

The control is the same calendar opened on calm days.

- **Calm day.** A date from `selloff_put_diagonal.calm_days`. Per ISO week it is the first session
  that is disarmed on the `E-DD5` rule and within 2% of the 63-session high.
- **In-sample calm days** are
  `calm_days(rule_state(closes cut at 2026-09-22, "E-DD5"), 2022-02-01, 2026-09-22)`, with the
  truncation rule under the population.
- **Entry.** A calm day is read as `D`, and its calendar enters at the close of `D + 1` by the
  same rules.
- **Disjoint from the signals.** A calm day `D` on which mech BEAR or E-VOL holds is dropped and
  counted. "Holds" is read on `D` from the same `state_flags` the signals use.
- **Calm cells.** Calm days price at the headline strike only, with each long expiry and each exit.

### Clusters

Onsets 10 sessions apart can share part of a 21-session hold. Every cell groups its entries by
the calendar month of `D`. A cluster is one month's entries. The bootstrap resamples clusters,
and the floor counts clusters, not entries.

Month clusters do not capture holds that cross a month boundary, so the CI is somewhat too narrow.
`state_map` Q3 shares this limit.

### Terms used here

| Term | Meaning |
|---|---|
| Calendar | Short a near call and long a later call at the same strike |
| [R](../../../glossary.md#net-r) | Net P&L over cost, but the basis here adds the commission (see R, fixed here) |
| [MFE / MAE](../../../glossary.md#mfe) | The best and worst open R on the daily mark path |
| [Capture](../../../glossary.md#capture) | Sum of R over sum of MFE |
| Holm | A step-down correction for testing several things at once |
| PBO / CSCV | The chance that the best cell in one half of the history ranks below the median in the other half. `lib/pbo.py` holds the method |

## Dependencies

- `scripts/backtest_study/f1_selection/regime/state_map.py`: `build_cal`, `cut_cal`,
  `mech_labels`, `state_flags`, `onsets`, `REARM`, `q4_trades`, `zone_bounds`, and the cached
  series in `backtests/state_map/`.
- `scripts/backtest_study/f1_selection/regime/selloff_put_diagonal.py`: `rule_state`,
  `calm_days`, `gate_hash`, `nearest_listed`, `leg_fill`, `leg_mark`.
- `scripts/backtest_study/f1_selection/benchmark/mechanical_benchmark.py`: `monthly_for`,
  `monthly_expiries` and the listing grid.
- `scripts/backtest/simulate.py` (`entry_day_fill`, `junk_day_mark`, `_monotonicity_violation`)
  and `helpers._defined_risk_bounds`. No price rule is re-derived.
- The SPY files in `backtests/option_history_cache/` and its skip-list.
- `scripts/backtest_study/lib/pbo.py` (`cscv`, `ratio_metric`, `pad_head`).
- `scripts/backtest_study/f1_selection/benchmark/ticker_class.py::holm`.
- `scripts/backtest_study/lib/era.py`: `CURRENT`, `SEAL_START`.
- A collector copied from
  `scripts/collector/study_legs/f1_selection/fetch_state_map_legs.py`. Its fetch list follows the
  rules above, never an outcome.

## Population and basis, fixed here

| Window | Signal dates `D` | Use |
|---|---|---|
| In-sample | 2022-02-01 to 2026-09-22 | Every in-sample verdict |
| Gap | 2026-09-23 to 2026-11-20 | In no population |
| Forward | From 2026-11-21 | The one-shot forward read |

- **The cut.** No SPY close, VIX close or option quote after 2026-09-22 enters the in-sample run.
  The study cuts every series at 2026-09-22 before it computes anything.
- **Same candidate entries.** Every cell, `CALM` included, starts from the same candidate entries:
  the onsets, or calm days, whose `D + 1 + 21` close falls on or before 2026-09-22. An entry that
  fails this is dropped and counted as `n_truncated`.
- **Per-cell drops.** After that, each cell keeps or drops an entry by its own pricing rules, and
  every cell prints its own drop counts. Entries are not intersected across cells.
- **Era.** The inputs carry no prompt version. The report prints `era: current (inputs are
  unversioned market closes and option quotes)`.
- **Seal.** The [holdout seal](../../f4_deployment/holdout_seal.md) binds signal dates of emitted
  plays. This study reads no play, so it does not bind. The in-sample window still ends the day
  before `era.SEAL_START` (2026-09-23).
- **Report header.** Era, the windows, the git sha, the dirty flag, the input files and each
  series' first and last date read.

## Plan-time observations, disclosed

The in-sample window is not blind. Each item below was seen by the operator before this file was
written. The drafter read registrations, the plan and code. The drafter read no option price, no
SPY return and no study record for any signal date.

### `state_map`, on these same signals

`state_map` was run and graded on 2026-11-21.

| Part | What the operator saw |
|---|---|
| Q2 | `COINCIDENT`: state variables turn on during a fall, not before the top |
| Q3 | `NULL` (PBO veto): SPY after an `S-BEAR` or `S-EVOL` onset did no differently from other days |
| Q3 tables | Per-cell SPY log returns after onsets at 5, 10 and 21 sessions, from 2016 |
| Q4 | `DESCRIPTIVE`: a put spread on 39 onsets from 2022-02-01, all priced; no edge in the put spread |
| Post-hoc `TURN-ON` | An all-sessions table, added 2026-11-21 at the operator's go-ahead, descriptive only |

- **What it spends here.** Q4 printed each onset's date, and SPY's return over 5, 10 and 21
  sessions after it. So the SPY path after every in-sample signal is known.
- **The geometry is not blind.** The 1.03 strike, the 30/60 DTE pair and the 21-session exit were
  set in §2.32 after Q4 printed those returns. The report says so beside the verdict.
- **The printed SPY-sign split is not blind** either. It is printed only for this reason.
- **The count of 39.** It is known from Q4. The split between the two signals was printed there
  too. The drafter did not read it.

### Other studies the operator has seen

| Study | What the operator saw |
|---|---|
| [`selloff_put_diagonal`](selloff_put_diagonal.md) | The put plus call-diagonal package paid on 9 `E-DD5` triggers and did not beat calm weeks |
| [`tail_rebound`](tail_rebound.md) | No rebound edge after SPY tail falls, 1993 on, at 5, 21 and 63 sessions |
| [`tail_rebound_etf`](tail_rebound_etf.md) | No rebound edge after QQQ or SMH tail falls |
| [`earnings_vol`](../../f3_structure/earnings_vol.md) | The earnings calendar's `ARM K` printed `NULL`; its edge was the bid-ask spread |

### Reads of nearly the same events

These were disclosed in `state_map`'s registration and seen by the operator.

- **`regime_confirm`'s exploration (2026-10-21).** On 97 SPY mech BEAR flips, the median 60-day
  return was +3.9%. Those flips are close to `S-BEAR` onsets.
- **The vol-expansion count (2026-11-06).** After 23 E-VOL onsets from 2023-06 to 2026-09-22, VIX
  fell in 15. Those onsets overlap `S-EVOL`. A call calendar is long vega, so this bears on it.

### The 2026-11-21 peek at the current sell-off

The [entry](../../../current.md#2026-11-21--bear-strategies-in-2026-peek-ungraded-sealed-dates)
read sealed play rows at the operator's request.

| What it showed | Value |
|---|---|
| SPY, 2026-10-06 to 2026-11-20 | 779.09 to 689.81, −11.5% |
| Regime-watch row, 2026-11-20 | BEAR and E-VOL, VIX 35.89 |

- **What it spends here.** The current sell-off is known, and both signal states held on
  2026-11-20. It is in the gap and is excluded from the forward read.

### A second structure on one signal set

The idea came after the put-spread result in `state_map` Q4. So this is the second structure tried
on the same onsets. The family is therefore the two structures, not one. This study cannot correct
for the first structure, and the report says so beside every verdict.

### A prior, not evidence

- **Power.** About 39 onsets split over two signals is thin. Each signal may hold fewer than 10
  month clusters. No power calculation was run.
- **The likeliest outcome**, written down now, is `NULL` or `UNDERPOWERED`.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `K-BEAR` | arm | The headline calendar on `S-BEAR` onsets | Graded, Holm m = 2 |
| `K-EVOL` | arm | The headline calendar on `S-EVOL` onsets | Graded, Holm m = 2 |
| `CALM` | control | The headline calendar on calm days | The reference for every gain |
| Parameter cells | descriptive cut | One choice moved from the headline, per signal | Printed only, in the PBO grid |
| Diagnostics | descriptive cut | MFE, MAE, capture and two splits | Printed only |
| `FORWARD` | population scope | The two arms on forward onsets | Forward verdict |

### Parameter cells

Each parameter moves one choice from the headline, with the rest held.

| Parameter | Headline | Printed |
|---|---|---|
| Strike | spot × 1.03 | spot × 1.00, spot × 1.05 |
| Long expiry | nearest 60 DTE | nearest 90 DTE, after the short's |
| Exit | 21 sessions | 5, 10 sessions |

- **Per signal**, that gives 6 cells: the headline and 5 others.
- **Calm comparison.** It prints for the long-expiry and exit cells. The strike cells print mean R
  only, because calm days price at the headline strike.

## How it is judged

### Statistic

For each graded arm:

- **Mean R** is entry-weighted: the sum of R over all priced entries divided by their count.
- **Gain.** Mean R on the arm minus mean R on `CALM`, same long expiry and exit.

### Bootstrap

- **Unit.** Calendar-month clusters of `D`. Each draw resamples the arm's clusters with
  replacement, as many as the arm holds.
- **Draw statistic.** In each draw, the statistic is the entry-weighted mean R over every entry
  in the drawn clusters.
- **Gain.** In the same draw, `CALM`'s clusters are resampled on their own, independently. The
  gain in a draw is the arm's draw mean minus `CALM`'s draw mean.
- 10,000 draws, seed 20261121.
- **CI.** The 2.5th and 97.5th percentiles of the draws. Each CI prints its half-width.
- **p-value.** Two-sided: twice the smaller of the share of draws at or below 0 and the share at or
  above 0, capped at 1.

### Multiple comparisons

| Family | Members | m |
|---|---|---|
| Mean R | `K-BEAR`, `K-EVOL` at the headline cell | 2 |
| Gain | `K-BEAR`, `K-EVOL` at the headline cell | 2 |

Holm at 0.05 within each family, with `ticker_class.holm`. Parameter cells test nothing.

### PBO / CSCV

The selection guarded against is picking the best cell of the printed grid.

- **Configs.** Every printed signal cell: 2 signals × 6 cells = 12.
- **Rows.** Calendar quarters of `D`, 2022 Q1 to 2026 Q3, so 19. One zero quarter is padded at the
  head with `pbo.pad_head`, giving T = 20 and S = 20 blocks of one quarter.
- **Per-period value.** [sum of R, entry count] for the cell's entries in the quarter.
- **Metric.** `pbo.ratio_metric`, so a half's value is the mean R over its entries.
- **Empty quarters** are [0, 0] and add nothing to either sum.
- **Not computable.** If PBO cannot be computed, it prints "not computed". Then
  `CALENDAR-PAYS`, `PAYS-NOT-SIGNAL` and `CONTRARY` cannot print, and the arm prints `NULL` with
  "PBO not computed".

| PBO | Reading |
|---|---|
| ≤ 0.25 | Supports a verdict |
| 0.25 – 0.50 | The verdict prints with "selection fragile" |
| > 0.50 | Veto. Both graded arms print `NULL` with "PBO veto" |

PBO enters only as a veto, never as evidence.

## Gates

A failed gate refuses the run (non-zero exit).

- **GE, inputs.** The SPY, VIX and VIX3M series exist and reach 2026-09-22. The option cache
  exists.
- **GH, hash.** `selloff_put_diagonal.gate_hash` passes, so the calm-day `E-DD5` thresholds match
  `EPISODE_DEFS_SHA256`.
- **GS, signals.** Per signal, the set of onset dates `D` ≥ 2022-02-01 the study uses, before any
  drop or truncation, equals `{t.D for t in state_map.q4_trades(...)}` from the same run. No date
  list is hardcoded.
- **GX, no lookahead.** Strike, expiry and listing choices read nothing after the entry session.
  A test changes every later quote and close and requires identical choices.
- **GC, the cut.** The in-sample report is identical when every close and quote after 2026-09-22
  is changed. A test checks it.
- **Await gate.** Nothing is priced until every headline entry, in both arms and `CALM`, has its
  contracts cached or a recorded refusal. Until then the report prints its census and
  `NOT BUILT — AWAITING SCRAPE`. A parameter cell still awaiting prints `NOT BUILT` for that cell
  only.
- **Census first.** Entry counts per arm, the fetch list and every drop by reason print before
  any price is read.

| Population | Floor |
|---|---|
| Graded arm, in-sample | 10 month clusters of priced entries |
| `CALM` | 10 month clusters of priced entries |
| Parameter cell | 10 month clusters, else THIN |
| Forward arm | 10 month clusters of forward priced entries |

## Bar for a candidate

No result here makes a rule. A `CALENDAR-PAYS` files "to be tested" in
[`deployment-evidence.md`](../../../deployment-evidence.md), pending the forward read.

## Verdicts, worded now

### Per graded arm

The first matching row is the verdict. The word meanings are in [The question](#the-question).

**`UNDERPOWERED`.** Fewer than 10 month clusters in the arm, or in `CALM`. The census prints and
nothing is concluded.

**`CALENDAR-PAYS`.** All five hold:

1. The mean R CI lower bound is above 0.
2. The mean R Holm-adjusted p is below 0.05 (mean R family, m = 2).
3. The gain CI lower bound is above 0.
4. The gain Holm-adjusted p is below 0.05 (gain family, m = 2).
5. The PBO is 0.50 or below.

**`PAYS-NOT-SIGNAL`.** All three hold:

- Conditions 1 and 2 above hold (mean R).
- Condition 5 holds (PBO).
- Condition 3 or 4 fails (gain).

**`CONTRARY`.** All three hold:

1. The mean R CI upper bound is below 0.
2. The mean R Holm-adjusted p is below 0.05 (mean R family, m = 2).
3. The PBO is 0.50 or below.

**`NULL`.** Otherwise, printed with the half-width. It includes both arms under the PBO veto.

**Exit-drop sensitivity.** Beside each graded arm and `CALM`, the report prints mean R with every
`exit_unmarked` entry set to R = −1 in a signal arm, or left out of `CALM`. If `CALENDAR-PAYS` or
`PAYS-NOT-SIGNAL` would fail under that substitution, the arm prints `NULL` with "exit-drop
sensitive".

### Printed only, no verdict

- **MFE, MAE and capture**, on the daily mark path of both legs from entry to exit, per arm and
  for `CALM`.
- **R by the sign of SPY's hold return.** This shows whether the trade needs a rebound. It is not
  blind (see the plan-time observations).
- **R by VIX above or below VIX3M** at the entry session's close.
- **Per entry.** `D`, signal, strike, both expiries, debit, R, gross R and the exit reason.
- **Counts.** Every drop and refusal by reason, floored exits, stale marks and clamp hits, per arm
  and by year.
- **Short-expiry exits.** Their count and share of exits, per arm and for `CALM`.
- **The parameter cells.** Mean R, its CI, and the gain where `CALM` prices.

### Forward

- **Opens 2026-11-21.** One shot, on frozen definitions. No PBO veto applies forward, because
  nothing is selected.
- **Forward onsets.** Onsets with `D` on or after 2026-11-21 whose 10 re-arm sessions also fall on
  or after 2026-11-21. So the BEAR and E-VOL runs in force on 2026-11-20 never count.
- **The current sell-off is excluded.** A forward onset inside the current episode's zone leaves
  the graded forward cell and prints in a split of its own.
- **The zone.** It is the one `state_map.run_forward` computes for the current episode:
  `zone_bounds` of the last headline `E-DD8` episode whose peak is on or before 2026-11-20. While
  that episode is unclosed, the zone runs to the data end.
- **Forward calm days.** `calm_days` dates on or after 2026-11-21, under the same rules.
- **Holm.** The same two families, m = 2 each.
- **Forward conditions.** `CALENDAR-PAYS` condition 5 is dropped, and so are the PBO clauses of
  `PAYS-NOT-SIGNAL` and `CONTRARY`.
- **Words.** The in-sample tokens, with `STILL-OPEN` in place of `UNDERPOWERED`. An arm stays
  `STILL-OPEN` until it reaches 10 forward month clusters.
- **Verdict of record.** The first forward run in which an arm prints a token other than
  `STILL-OPEN`. Later forward runs are descriptive.
- **Sunset.** 2028-11-21. An arm still `STILL-OPEN` then keeps `STILL-OPEN` as its final word.

### The banner

The report's section titled VERDICT prints:

```
>>> signal_call_calendar K-BEAR (call calendar after S-BEAR, 1.03 strike, 30/60 DTE, 21 sessions or short expiry, 2022-02-01 to 2026-09-22): CALENDAR-PAYS | PAYS-NOT-SIGNAL | CONTRARY | NULL | UNDERPOWERED <<<
>>> signal_call_calendar K-EVOL (call calendar after S-EVOL, 1.03 strike, 30/60 DTE, 21 sessions or short expiry, 2022-02-01 to 2026-09-22): CALENDAR-PAYS | PAYS-NOT-SIGNAL | CONTRARY | NULL | UNDERPOWERED <<<
>>> signal_call_calendar PBO: <value> <<<
>>> signal_call_calendar FORWARD (onsets from 2026-11-21, current sell-off out): K-BEAR <w> K-EVOL <w> <<<
```

Each line carries two notes: "second structure on one signal set" and "geometry set after Q4".

## Anti-tuning

- **Fixed here, the inputs.** The signals, the re-arm, the calm-day rule and the windows.
- **Fixed here, the design.** The strike, both DTE rules, the exit, the cost, the R definition and
  the drop rules.
- **Fixed here, the judging.** The floors, the seed, the clusters, the Holm families, the PBO grid
  and thresholds, and the verdict words.
- The parameter cells and every printed-only cut appear as they fall. None is used to re-grade.
- No other signal, strike, expiry, exit or structure is graded.
- The in-sample run reads nothing after 2026-09-22, and the forward read opens on 2026-11-21. No
  later run moves either date.
- A put calendar, a diagonal or another ticker on these signals is a new registration.
- This registration is immutable in substance. Editorial consolidation only.

## What could ship

Nothing ships from this study.

- A `CALENDAR-PAYS` files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md), pending the forward read.
- Any rule built on a result here needs its own registration and an operator decision.
- No verdict here changes a tier, a veto, a size class, an exit, the deploy card or the hedge
  sleeve in [§4](../../../../docs/deployment-rules.md#s4).

## Second reader (2026-11-21)

Verdict: READY WITH LISTED FIXES. Every fix is folded into the text above. Its rulings on the
drafter's open points:

1. **Exit against short expiry.** Accepted: both legs close at the short's expiry if it comes
   before 21 sessions. The short's DTE runs from 21 to about 55 days.
2. **Monthlies only.** Accepted.
3. **Long expiry strictly after the short's.** Accepted.
4. **Long strike must equal the short's, else drop.** Accepted.
5. **No entry window, `D + 1` only.** Accepted.
6. **R basis includes all commission; exit value floored at 0.** Accepted.
7. **Two Holm families, m = 2 each.** Accepted.
8. **PBO veto covers every word.** Accepted.
9. **One-at-a-time PBO grid of 12 configs.** Accepted.
10. **Fetch size.** The reader's estimate is at most 7 contracts per onset, about 270 for the
    signals. Calm days need 3 each, about 460 to 720. The build counts it from the code.
11. **Same candidate entries for every cell.** Accepted, with per-cell drops and no intersection.
12. **Calm days disjoint from the signals.** Accepted.
13. **Unmarked exits.** Changed: the exit-drop sensitivity line above is added.
14. **Seed 20261121.** Accepted.
