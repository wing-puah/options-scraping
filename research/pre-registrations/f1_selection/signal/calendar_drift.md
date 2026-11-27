## calendar_drift — do the pre-FOMC drift and the turn of the month still pay on SPY after publication?

<!-- outcome:start -->
> Latest outcome: no verdict yet — the first run refused at gate GE (`GE: SPY ends 2026-11-25, before the registration date 2026-11-27`), so no return was computed; the graded run is owed after the 2026-11-30 US close, the first session after the registration date (`python3 -m scripts.backtest_study run calendar_drift --refresh`), run 2026-11-27 · [record](../../../study-results/f1_selection/signal/calendar_drift.md)
<!-- outcome:end -->

_Registered 2026-11-27._

**STATUS: REGISTERED 2026-11-27 on the design the operator approved.** Every detail the operator
did not fix is the drafter's most conservative conventional choice, tagged `Resolved at draft`
beside the rule. No return inside or outside either window had been computed by the drafter
before this file was written. A fresh second reader checked it on 2026-11-27, before its first
outcome. Its changes are tagged `Resolved at second read (2026-11-27)`.

## The question

Two calendar effects were published as strong, simple ways to hold the US market. Do they still
pay on SPY in the years after publication, net of costs?

- **`PF`, pre-FOMC drift.** Lucca and Moench (2015, Journal of Finance) found that US stocks rose
  sharply in the hours before scheduled FOMC announcements.
- **`TOM`, turn of the month.** Lakonishok and Smidt (1988, Review of Financial Studies) and
  McConnell and Xu (2008, Financial Analysts Journal) found that US stock returns concentrate in
  the last session of a month and the first three of the next.

The graded test, for each arm: is SPY's mean daily return inside the window, net of costs, higher
than its mean daily return outside it? Only years after each paper became public are graded. The
years before are printed as the published prior.

Both windows are fixed by the papers, so the study has no free parameter.

## What this study is not

- **Not `macro_event_study`.** [That study](../regime/macro_event_study.md) asked whether macro
  dates change how the model's flow picks did. This study trades SPY itself on a fixed calendar and
  reads no pick, play, tier or backtest row.
- **Not an option study.** A one-session option hold pays a day of time decay and two bid-ask
  half-spreads. The drafter's prior is that these costs exceed the few tenths of a percent the
  drift is worth. So there is no options arm. Shares only.
- **Not a parameter search.** Each arm has one window, taken from its paper. No window length,
  shift, cost or start date is tuned.
- **Not pooled across eras.** The inputs are market data with no prompt version. There is one
  population and no `--era` replication.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price basis

- **Source.** SPY daily bars from yfinance, from SPY's first session (1993-01-29), fetched with
  `auto_adjust=False`. The cache holds date, close and `Adj Close` in
  `backtests/calendar_drift/SPY.csv`.
- **The calendar.** The sessions in that file, after dropping any session with no `Adj Close`.
  Every distance in sessions is counted on it.
- **Daily return.** `r_t = A_t / A_{t−1} − 1`, where `A_t` is SPY's `Adj Close` on session t. It
  includes dividends, so an ex-dividend drop is not a loss.

### The FOMC calendar

- **Decision day.** The last day of a scheduled FOMC meeting. From 1999 on, the statement is
  released that day. Before mid-1999 the Fed issued a statement only when policy changed; a
  scheduled meeting with no statement is still a decision day. `Resolved at second read
  (2026-11-27)`.
- **2023-06 on.** The `fomc` entries of `config/macro-events.yml`, read through
  `scripts/backtest_study/lib/macro_calendar.py`. Entries marked `unscheduled: true` are dropped.
- **Before 2023-06.** A new file, `config/fomc-history.yml`, hand-transcribed at build time from
  the federalreserve.gov historical FOMC calendars. It holds every scheduled decision day from
  1994-01-01 to 2023-05-31.
- **Unscheduled actions are out.** Inter-meeting moves and emergency meetings are never events.
  They were not knowable the day before.
- **Fixed before any return.** The history file is committed with the build. It is complete before
  the module computes any return. Gate GF refuses a run on an untracked or modified copy.
- **`Resolved at draft`: a cancelled meeting is no event.** When a scheduled meeting was cancelled
  or replaced by an unscheduled one, its date is not an event. The drafter knows one case: the
  March 2020 meeting, replaced by the 2020-03-15 emergency action.
- **`Resolved at build (2026-11-27)`: the September 15, 2003 meeting is no event.** The Fed's 2003
  page lists two meetings that week. The August 2003 minutes name September 16 as the next regular
  meeting, and the September 15 session discussed only communication practice. So September 16 is
  the decision day and September 15 is listed as excluded. With it out, 2003 holds eight.
- **`Resolved at draft`: a transcription fix.** A date may change after the first report only when
  the Fed's own page proves it wrong. The fix is tagged `Resolved at build (date)` beside this
  clause, and the report prints the old and new verdicts side by side.

### The windows

Each window is a set of close-to-close daily returns. You buy SPY at the close before the first
return and sell at the close of the last.

| Arm | Window returns | Buy at the close of | Sell at the close of | Sessions |
|---|---|---|---|---|
| `PF` | `r_D`, where D is a decision day | The session before D | D | 1 |
| `TOM` | `r_L`, `r_F1`, `r_F2`, `r_F3` | The session before L | F3 | 4 |

- **`TOM` sessions.** L is the last session of calendar month m. F1, F2 and F3 are the first three
  sessions of month m+1. This is McConnell and Xu's interval: the last trading day through the
  third trading day of the next month.
- **The second-to-last session.** The `TOM` buy session is the session before L, the
  second-to-last session of month m.
- **One event per window.** A `PF` event is one decision day. A `TOM` event is one month turn.
- **Event dates.** An event's first session is its first window return's session: D, or L. Its
  last session is D, or F3.
- **`PF` window limit.** Lucca and Moench measured the 24 hours from 2pm the day before to 2pm on
  the decision day. Daily closes cannot split that. The `PF` window also holds the market's
  reaction from the release to the 4pm close. That adds noise and, if the reaction is negative on
  average, bias against `PF`. Statement times also moved, from 2:15pm to 2pm, in 2013.
- **A decision day must be a session.** Gate GF refuses if any decision day is not a SPY session.
- **`Resolved at second read (2026-11-27)`: an undefined return voids the event.** An event with
  any window return undefined is not counted, and its window days are in neither set. The first
  `TOM` turn (L = 1993-01-29, SPY's first session) is one such event.
- **`Resolved at second read (2026-11-27)`: unscheduled market closures.** The calendar is the
  sessions in the file. A window that spans an unscheduled closure (2001-09, Hurricane Sandy in
  2012-10) holds a return over the closed days. This is accepted, not corrected.
- **`Resolved at build (2026-11-27)`: the data's final session.** The calendar cannot show
  whether the last session in the file is its month's last, because no later session exists yet.
  So that session is an open `TOM` event and sits in neither set. It joins a set on the next run
  that has a later session.
- **`Resolved at build (2026-11-27)`: today's bar.** The fetch keeps a bar dated on the fetch day
  only after 16:30 New York time, so every cached close is a finished session.

### Cost

- **Cost.** 2 bps per side, so `c = 0.0004` per round trip. It covers commission, half-spread and
  closing-auction slippage on SPY shares.
- **Charged to the window.** Each window day's return is reduced by `c / n`, where n is the
  window's session count: 1 for `PF`, 4 for `TOM`.
- **Out-of-window days carry no cost.** Charging only the window side is conservative.
- **Event net return.** `(1 + r_first) × … × (1 + r_last) − 1 − c`.

### In and out of the window

- **In-window days.** Every session that is a window return of a counted event in the population.
- **Out-of-window days.** Every other session in the population whose return is defined. A window
  day of an event that is not counted (a gap event, an open event, or an event from the other
  period) is in neither set.
- **Net excess.** `Δ = mean of net in-window daily returns − mean of out-of-window daily returns`.
  This is the headline for each arm.
- **Cash earns nothing.** On out-of-window days the window strategy holds cash at zero return.
  This is conservative.

### Cycles, the resampling unit

A cycle runs from the session after one event's last session through the next event's last
session. So each cycle holds one window and the out-of-window days before it.

- The first cycle in a population starts at its first session.
- Days after the last event, to the population's end, form one final cycle with no window.
- Cycles are formed separately for each arm and each population.

## Dependencies

- `backtests/calendar_drift/SPY.csv`, fetched from yfinance only when the run is passed
  `--refresh`. Without the file, the run refuses (exit 3) and says to pass `--refresh`. Forward
  runs pass `--refresh` first; otherwise the forward population never grows.
- `config/macro-events.yml` through `scripts/backtest_study/lib/macro_calendar.py`, read unchanged.
- `config/fomc-history.yml`, new at build time, as defined above.
- `scripts/backtest_study/f1_selection/regime/tail_breach.py::ratio_problems`, imported unchanged,
  for gate GB.
- `scripts/backtest_study/f1_selection/benchmark/ticker_class.py::holm` and `lib/era.py`, imported
  unchanged.
- No Barchart call, no Sheets export, no option price and no backtest row.

## Population and basis, fixed here

- **Era.** Only the default era `current` runs. Any other `STUDY_ERA` refuses (exit 2).
- **Seal.** The [holdout seal](../../f4_deployment/holdout_seal.md) binds the signal dates of emitted
  plays. This study reads no flow signal, play or backtest row, so the seal does not apply.
- **The registration date** enters the code as the constant `REGISTERED`, 2026-11-27.

| Population | `PF` | `TOM` | Role |
|---|---|---|---|
| `PRIOR` | Events with first session 1994-01-01 to 2011-12-31 | Events with first session 1993-01-29 to 2008-12-31 | Printed as the published prior; never graded |
| `GRADED` | Events with first session 2012-01-01 to `REGISTERED` | Events with first session 2009-01-01 to `REGISTERED` | The sample verdict |
| `FORWARD` | Events with first session after `REGISTERED` | The same | The forward verdict |

- **Why these starts.** The Lucca and Moench working paper circulated in 2011, so `PF` grades from
  2012. McConnell and Xu was published in 2008, so `TOM` grades from 2009.
- **Out-of-window days by date.** An out-of-window day belongs to the population that holds its own
  date. `GRADED` days run to `REGISTERED`; `FORWARD` days start the session after it.
- **Gap events.** An event whose first session is on or before `REGISTERED` and whose last session
  is after it is a gap event. It is counted in neither population. The drafter knows of none on
  either arm.
- **Open events.** A `FORWARD` event whose last session is past the last session in the data is
  open. It waits for the next run.
- **`Resolved at second read (2026-11-27)`: the `PF` forward horizon.** `PF`'s `FORWARD`
  population ends at the `fomc` `verified_through` date of `config/macro-events.yml`, now
  2027-12-31. Later sessions are in neither set for `PF` until that file is extended. Without this,
  missing decision days would be counted as ordinary days. The report prints the horizon.
- **The first forward events.** The `TOM` turn into December 2026 buys at the close of 2026-11-27
  and is the first `FORWARD` `TOM` event. The 2026-12-09 decision is the first `FORWARD` `PF`
  event.
- **Report header.** The report prints `era: current (inputs are unversioned market data)`, the SPY
  session range, the git sha, the dirty flag, every input file read and the git blob sha of
  `config/fomc-history.yml`.

## Plan-time observations, disclosed

### What the papers report

These were written from the drafter's memory. The second reader checked the Lucca-Moench and
McConnell-Xu rows against the papers' abstracts and a Fed presentation on 2026-11-27, and
corrected the McConnell-Xu row. The Lakonishok-Smidt row is unchecked. The builder may correct
wording, not the design, under a `Resolved at build (date)` tag.

| Paper | Reported headline |
|---|---|
| Lucca and Moench (2015) | The S&P 500 rose about 49 bps on average in the 24 hours before scheduled FOMC announcements, 1994 to 2011 |
| Lucca and Moench (2015) | That drift accounts for a large share, reported as about 80%, of the period's annual realized excess stock return |
| McConnell and Xu (2008) | From 1926 to 2005, the US value-weighted market averaged 0.15% a day over the four turn-of-month days and about zero (−0.001% a day) over the other days |
| Lakonishok and Smidt (1988) | Over 90 years of the Dow, returns around the turn of the month are well above other days |

### Later work the drafter knows

- **Decay of `PF`.** Kurov, Wolfe and Gilbert (2021, Finance Research Letters, vol. 40) extend
  the sample to 2019. They report that the pre-FOMC drift essentially disappeared after 2015. The
  drafter expects `PF` to print `NULL` more likely than not.
- **The FOMC cycle.** Cieslak, Morse and Vissing-Jorgensen (2019, Journal of Finance) report that
  since 1994 the equity premium was earned in even weeks of the FOMC cycle: weeks 0, 2, 4 and 6.
  Week 0 is days −1 to +3 around the decision; week 1 is days 4 to 8. Odd-week returns were
  around zero or negative. The `PF` placebo below is placed in week 1 for this reason.
- **`TOM`.** The drafter has no firm prior on post-2008 decay of the turn-of-month effect.

### What earlier work in this repo showed

- **`macro_event_study` ARM V-price.** It printed, as context only, SPY's return from three
  sessions before an FOMC decision to the decision close, on dates from 2023-06. That window and
  sample differ from `PF`'s.
- **One line seen.** While searching the repo for this file, the drafter saw one archived sentence
  (`research/archive/16-first-runs-on-v3.md`): the Lucca-Moench drift "does NOT reproduce" there.
  The drafter read no number from it. That sample overlaps only the last few years of `GRADED`.
- No study in this repo has tested a turn-of-month window.

### Counts made for this file

These count calendar events, not returns. No price was read.

| Arm | `GRADED` events, approximately | Power floor (gate GN) |
|---|---|---|
| `PF` | 118 decision days, 2012-01 to 2026-10 | 40 events |
| `TOM` | 214 month turns, 2009-01 to 2026-10 | 40 events |

### Power, from a prior

- **Assumption.** SPY's daily return has a standard deviation of about 1.2%. This is a general
  market fact, not a figure computed here.
- **`PF`.** With about 118 one-day windows, the standard error of the in-window mean is about
  11 bps. So `Δ` smaller than about 35 bps is unlikely to be detected after Holm.
- **`TOM`.** With about 856 window days, the standard error is about 4 bps per day. So `Δ` smaller
  than about 14 bps per day is unlikely to be detected.
- **The `PF` window is noisier than the paper's.** The close-to-close window adds the post-release
  reaction. So the paper's 49 bps is an upper guide to what this window could show.
- **Forward is weak for `PF`.** At the 40-event floor the standard error is about 19 bps. A forward
  `PF` grade can only detect a drift larger than the paper's.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `PF` | arm | Net excess on decision days, `GRADED` | Co-primary, Holm m = 2 with `TOM` |
| `TOM` | arm | Net excess on turn-of-month days, `GRADED` | Co-primary, Holm m = 2 with `PF` |
| Out-of-window days | control | Every other session in the same population | The reference each excess is measured from |
| `PF-PLACEBO` | control | The `PF` window shifted 6 sessions later | Gate GP |
| `TOM-PLACEBO` | control | The `TOM` window shifted 10 sessions earlier | Gate GP |
| `FORWARD` | population scope | `PF` and `TOM` on events after `REGISTERED` | Forward verdicts |
| `PRIOR` | population scope | `PF` and `TOM` before publication | Printed only |

### `PF`

Long SPY from the close of the session before each scheduled decision day to the close of the
decision day. It asks whether decision days still beat ordinary days after 2011.

### `TOM`

Long SPY from the close of the second-to-last session of each month to the close of the third
session of the next month. That is four daily returns: the month's last session and the next
month's first three. It asks whether those days still beat the rest of the month after 2008.

### Why two co-primaries with Holm

The operator asked one question about two effects. Two uncorrected intervals would give two
chances at a false yes. So `PF` and `TOM` form one Holm family, m = 2. The report prints each arm's
unadjusted p beside its Holm-adjusted p.

### Why there is no PBO

[PBO](../../../glossary.md) measures the chance that a rule picked as best from many
configurations is overfit. This study picks nothing: each arm is one window taken whole from its
paper, with zero free parameters. With one configuration per arm there is nothing to rank, so PBO
is undefined. The placebo shift and the cost are fixed here and never varied.

### Printed only, never graded

| Label | What it prints |
|---|---|
| `GROSS` | `Δ` with no cost |
| `BREAKEVEN` | The round-trip cost at which `Δ` reaches zero |
| `ANNUAL` | Annualised return of holding SPY only in the window, cash at zero, net of cost |
| `SHARPE` | Annualised Sharpe of that strategy, cash at zero, no risk-free rate subtracted |
| `CAPTURE` | The strategy's summed log return over SPY's summed log return, same sessions |
| `HIT` | Share of events with a positive net return, beside SPY's share for every same-length window |
| `YEARS` | `Δ` per calendar year, and the count of years with `Δ` above zero |
| `EX-OVERLAP` | Each arm with overlapping events removed, with its CI (used by gate GV) |
| `UNION` | Holding SPY in the union of both arms' windows, one cost per contiguous holding |

- **`Resolved at build (2026-11-27)`: `UNION` and `HIT` populations.** `UNION` uses counted
  windows of both arms that fall inside the years both arms share: 2012-01-01 to `REGISTERED`
  for `GRADED`, and 1994-01-01 to 2008-12-31 for `PRIOR`. Its out-of-window days are sessions in
  no window of either arm. `HIT`'s SPY share counts every gross same-length window that starts
  inside the population's dates.
- **`Resolved at build (2026-11-28)`: the final session inside an open window.** When the
  data's final session already sits inside an earlier open `TOM` window, it adds no event of
  its own. Which days are in or out of a set does not change.
- **`Resolved at build (2026-11-28)`: printed labels, no statistic changed.**
  - `YEARS` notes that per-year deltas are net of cost, so with no calendar effect about 0.45
    of years print above 0, not 0.50 (pre-run simulation).
  - `HIT` says the event hit rate is net of cost and SPY's base share is gross.
  - A `REVERSED` verdict prints a note: read with the `GROSS` line, because the 2 bp cost alone
    makes `REVERSED` fire in about 3-4% of simulated paths with no effect.
  - Each arm prints one more line, `EX-OTHER-ARM`: the same `Δ` with the other arm's window
    days removed from the out-of-window reference set, same bootstrap. It is printed only, not
    graded, and feeds no verdict.
| `PRIOR` | Every line above, and `Δ` with its CI, for the pre-publication years |

- **`ANNUAL`.** `(product of (1 + s_t))^(252 / N) − 1`, where `s_t` is the strategy's net return on
  session t and N counts the population's sessions.
- **`SHARPE`.** `mean(s_t) / sd(s_t) × √252`, over every session in the population.
- **`Resolved at build (2026-11-27)`: the population's sessions.** For `ANNUAL`, `SHARPE` and
  `CAPTURE` these are the population's in-window and out-of-window days. Days in neither set are
  left out.
- **`CAPTURE`.** It prints `n/a` when SPY's summed log return over the population is zero or less.
- **`YEARS` and the leave-one-year-out gate.** An event, with all its window days, belongs to the
  year of its last session. An out-of-window day belongs to its own year.
- **Every printed-only line carries no verdict.** Lines with an interval use the same bootstrap.

## How it is judged

- **Statistic.** The net excess `Δ`, for each arm, on `GRADED`.
- **Bootstrap.** Resample the arm's cycles with replacement, as many as there are, 10,000 times,
  seed 20261127. Each draw pools the in-window and out-of-window days of the drawn cycles and
  recomputes `Δ`.
- **Why cycles.** Each cycle keeps a window with the days around it. Volatility clusters over
  weeks, so resampling single days would make the interval too narrow.
- **CI.** The 2.5th and 97.5th percentiles of the draws.
- **p-value.** Two-sided, from the same draws: twice the smaller of the share at or below 0 and the
  share at or above 0, capped at 1. This is the convention of `tail_breach`.
- **Multiple comparisons.** `PF` and `TOM` form one Holm family, m = 2, through `ticker_class.holm`.
- **A gated arm stays in its family.** m stays 2 whatever the gates print. An `UNDERPOWERED` arm
  enters its family with p = 1.
- **`Resolved at draft`: forward keeps Holm.** `FORWARD` uses the same Holm family, m = 2. Dropping
  it would make a forward yes easier than a sample yes.

## Gates

### Refusals, before any statistic

- **GE, inputs.** `backtests/calendar_drift/SPY.csv` exists, is not empty, starts on or before
  1993-02-01 and runs through `REGISTERED`. Any failure refuses (exit 3).
  - **`Resolved at build (2026-11-28)`: GE needs a session after `REGISTERED`.** The last
    session with an Adj Close must fall strictly after the registration date. The final session
    is always an open `TOM` event, so the graded sample is final only once a later session
    exists; a file ending on 2026-11-27 would grade one day short and a rerun would print
    different figures. This tightens the gate before any outcome. GE also refuses duplicate
    dates, and tests the last session that has an Adj Close, not the raw last row.
- **GB, basis.** `tail_breach.ratio_problems`, imported unchanged: the close-to-`Adj Close` ratio
  never steps like a split. Any failure refuses (exit 3).
- **GF, FOMC calendar.** Any failure refuses (exit 3):
  - `config/fomc-history.yml` is tracked by git and unmodified in the working tree;
  - every year 1994–2022 holds eight scheduled decision days, except years listed in the file's
    `meta.exceptions`, each with a reason (2020 is one);
  - the two files join without overlap or gap: the last history date precedes 2023-06-14, the
    first `macro-events.yml` decision, by fewer than 70 days;
  - every decision day is a SPY session.
- **GX, no lookahead.** The tests rebuild every window on a price series whose later sessions are
  all changed. No window may change. Window membership reads only the session calendar and the
  FOMC dates, never a price.
- **Era.** Any era but `current` refuses (exit 2).

### Power, per arm

- **GN.** At least 40 events in the arm's population, spread over at least 5 calendar years for
  `GRADED` and at least 3 for `FORWARD`. Otherwise the arm prints `UNDERPOWERED` on `GRADED` and
  `STILL-OPEN` on `FORWARD`.
- **`Resolved at build (2026-11-27)`: the year span.** GN counts the distinct calendar years of
  the counted events' last sessions.

**Why 40.** It is about five years of FOMC meetings and the smallest count at which the bootstrap
interval is stable for a one-day window. It is set here from the calendar counts above, not from
any return.

### Robustness, per arm, read only for a positive result

- **GL, leave-one-year-out.** Drop each calendar year of the population in turn and recompute `Δ`.
  GL passes when every one of these estimates is above zero.
- **GP, placebo.** Shift every window of the arm on the calendar, keeping its length and cost:
  `PF` 6 sessions later, `TOM` 10 sessions earlier. A placebo day that is a window day of the other
  arm leaves the placebo set and stays an out-of-window day. Compare the placebo days with the
  arm's own out-of-window days, less the placebo days. GP passes when the placebo's 95% CI, from
  the same bootstrap on its own cycles, contains zero.
- **GV, overlap.** An overlap is a decision day that is one of a `TOM` window's four sessions.
  Remove every overlapping event from the arm. Its window days leave the in-window set and do not
  join the out-of-window set. GV passes when the arm's `Δ` stays above zero.
- **`Resolved at build (2026-11-27)`: which days the placebo and overlap rules read.** A
  placebo day must be one of the population's own out-of-window days. So a shifted day that is an
  own-arm window day, has no defined return, or falls outside the population's dates is dropped.
  "A window day of the other arm" and "a `TOM` window" mean any such window, counted or not.
- **`Resolved at build (2026-11-27)`: forward robustness.** GL, GP and GV run on `FORWARD` by the
  same rules. An arm still at `STILL-OPEN` enters the forward Holm family with p = 1.

**`Resolved at draft`: the `TOM` placebo shift.** Ten sessions earlier puts the `TOM` placebo near
the middle of month m. The shift is fixed here and never varied.

**`Resolved at second read (2026-11-27)`: the `PF` placebo shift.** The draft shifted `PF` 10
sessions earlier too. Day −10 falls in week 4 or 6 of the previous FOMC cycle for most meeting
gaps, so a real cycle effect could fail GP. Six sessions after the decision is the middle of week
1, an odd week, for every gap. It is never another decision day. The other-arm rule keeps a real
`TOM` effect, or a real `PF` effect, out of the other arm's placebo. The shift is fixed here and
never varied.

**`Resolved at draft`: how overlap is handled.** The headline keeps overlapping events in both arms.
Each arm is its own question, and a trader following one rule holds through the overlap. GV checks
that neither arm's result rests on the other's days. Expect overlaps around late January, late
April, late July and late October, when decision days often fall at a month turn.

## Bar for a candidate

No result here makes a candidate rule on its own.

- A `GRADED` `STILL-PAYS` files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md). It waits on its forward read.
- A candidate needs `STILL-PAYS` on both `GRADED` and `FORWARD` for the same arm.
- Even then, money moves only on the operator's own decision, in a new registration that sizes it.

## Verdicts, worded now

**`PF` and `TOM`, on `GRADED`.** Read top to bottom; the first row that holds is the verdict.

| Token | When |
|---|---|
| (refusal, no token) | GE, GB, GF or the era check fails; the run exits 2 or 3 and prints no banner |
| `UNDERPOWERED` | GN unmet, or the CI is not finite; census printed, nothing concluded |
| `REVERSED` | The CI upper bound below 0, and the Holm-adjusted p (m = 2) below 0.05 |
| `STILL-PAYS` | The CI lower bound above 0, the Holm-adjusted p below 0.05, and GL, GP and GV all pass |
| `FRAGILE` | The CI lower bound above 0 and the Holm-adjusted p below 0.05, but GL, GP or GV fails |
| `NULL` | GN met, and none of the above |

- **Each case has exactly one token.** The rows are read in order, and a CI cannot sit both above
  and below zero.
- **`STILL-PAYS`** means the window still beats ordinary days after publication, net of 2 bps a
  side, and the result holds without any single year, on a placebo check and without overlaps.
- **`FRAGILE`** means the interval clears zero, but the result rests on one year, on the other
  arm's days, or on a method that also flags a shifted window.
- **`NULL`** prints its CI. It reads as "no excess outside the interval", not as "no effect".
- **`REVERSED`** means the window now does worse than ordinary days.
- The report names the gate that failed for each `FRAGILE` arm.

**`FORWARD`.** The same tokens and Holm family on `FORWARD` events, against `FORWARD`'s own
out-of-window days. `STILL-OPEN` takes the place of `UNDERPOWERED` until the arm meets GN's forward
floor. `TOM` has about 12 month turns a year and reaches 40 events around early 2030. `PF` has
about 8 meetings a year and reaches 40 around late 2031. Each run before then prints the forward
census. The verdict of record is the
first forward run that prints a token other than `STILL-OPEN`.

**`PRIOR`.** No token. The report prints `PRIOR (pre-publication, not graded)` beside its lines.

**The banner.** The report's section titled VERDICT prints:

```
>>> calendar_drift PF (SPY decision-day close-to-close return, net 2 bps a side, vs other days, 2012 on, Holm m=2): STILL-PAYS | FRAGILE | NULL | REVERSED | UNDERPOWERED <<<
>>> calendar_drift TOM (SPY last session plus first three of the month, net 2 bps a side, vs other days, 2009 on, Holm m=2): STILL-PAYS | FRAGILE | NULL | REVERSED | UNDERPOWERED <<<
>>> calendar_drift FORWARD (events after the registration date): PF <w> TOM <w> <<<
```

## Anti-tuning

- Fixed here: both windows, the scheduled-only FOMC rule, the cancelled-meeting rule, the price
  basis, the 2 bps per side cost, the graded start dates, the statistic, the cycle bootstrap, the
  seed, the 10,000 draws, the floor of 40 events and its year spans, the placebo shifts (`PF` 6
  sessions later, `TOM` 10 earlier),
  the overlap rule, the Holm family and the verdict words.
- No other window, shift, cost, start date, instrument or reference is graded.
- The `PRIOR` years are never graded and never move a verdict.
- The FOMC history file is complete and committed before any return is computed. A later change is
  allowed only under the transcription-fix rule above.
- This registration is immutable in substance. Editorial consolidation only.

## What could ship

Nothing ships from this study.

- A `GRADED` `STILL-PAYS` files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md).
- A `STILL-PAYS` on both `GRADED` and `FORWARD` makes a candidate for a separate SPY share sleeve.
  It would need its own registration and the operator's decision before any money moves.
- No verdict here changes a tier, a veto, a size class, an exit, the deploy card or the hedge
  sleeve's rule in [§4](../../../../docs/deployment-rules.md#s4).
