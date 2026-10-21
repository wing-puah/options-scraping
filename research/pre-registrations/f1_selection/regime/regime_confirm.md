## regime_confirm — does a confirmed mech BEAR flip predict a real sell-off better than the flip alone?

<!-- outcome:start -->
> Latest outcome: not run.
<!-- outcome:end -->

_Registered 2026-10-21._

**STATUS: ACCEPTED BY DEFAULT 2026-10-21 on the drafter's recommended defaults; the operator may
revisit (a revisit after a result is a NEW registration, never an edit).** Drafted 2026-10-21,
after an exploratory pass on SPY 1993–2026 in the main session. That pass chose the candidate
rule, so it is spent as evidence: SPY 1993–2026 is no longer clean in-sample evidence for these
thresholds.

## The question

When SPY first turns mech BEAR after a quiet stretch, most of those turns fade within days. Does
waiting for the turn to persist, and for other stress signs to agree, pick out the turns that
become a real sell-off, often enough to be worth the price already lost by waiting?

In plain terms: is "confirmed" a better hedge trigger than "flipped"?

If the answer is `SUPPORTED`, the operator could consider two changes, each through its own
registration with a rollback trigger:

- **The hedge trigger.** [§4](../../../../docs/deployment-rules.md#s4) leaves the bear hedge
  sleeve's timing to operator discretion. A confirmed shift could become a named reason to open
  it. [`hedge_timing`](../../f5_hedging/hedge_timing.md) found its gap-up trigger
  (`hedge_timing ARM H3-GAP`) `CONTRARY`, and
  [`index_bear_hedge`](../../f5_hedging/index_bear_hedge.md) is still forward `STILL-OPEN`, so no
  mechanical hedge trigger is supported today.
- **Dip-date sizing.** [Sizing](../../../../docs/deployment-rules.md#s2-sizing) gives Tier A full
  size on a [dip date](../../../glossary.md#dip-date). A confirmed shift is a dip that kept
  falling, so a verdict could argue for sizing down on those dates.

Neither change follows from the verdict by itself.

## What this study is not

- **Not a test of `dip_buy` or `regime_map`.** [`dip_buy`](dip_buy.md) asks whether Tier A/B
  positions earn more on dip dates; [`regime_map`](regime_map.md) maps tier outcome by label. This
  study reads no position, no tier and no R. Its unit is a market event, and its outcome is the
  index's own path.
- **Not a new label for the mech table.** BEAR is read from
  `lib/mech_regime.py::compute_mech_table`, never re-implemented. No threshold in that module
  moves. The shipped `mech_cell` and its exit conditioning are untouched.
- **Not a validation of `scripts/regime_watch.py`.** That script was built in commit `6744f34`
  as a REPORT that prints whether today is a flip or a confirmed shift. This registration does
  not validate it until a verdict lands. It must never feed `mapping.ladder_tier()`, a veto, a
  size class or an exit, whatever this study prints.
- **`regime_watch`'s `CONFIRMED` is not `RC1`.** It is a trailing BEAR streak with no
  20-quiet-session requirement, and it adds a `WATCH` state that this study does not grade.
- **Not a timing study for the book.** It does not ask whether hedges opened on confirmed dates
  make money. That needs option prices and is a separate registration.
- **Not a sweep.** One streak length, one condition set and one outcome are graded.

## Definitions

**Flip.** The first mech BEAR session after 20 sessions with no BEAR label. BEAR is
`compute_mech_table`'s rule on the flip ticker's own closes: close below its 50-day SMA and
20-day return below zero. A session with no label (no runway) breaks the 20-session look-back,
so it cannot precede a flip. The coined term is in the
[glossary](../../../glossary.md#regime-flip).

**Streak.** The count of consecutive BEAR sessions starting at the flip. The flip session counts
as day 1. A streak of 3 means the flip session and the next two sessions are all BEAR.

**Decision date.** The session on which a rule acts, using closes on or before it:

| Rule family | Decision date |
|---|---|
| Acts at the flip | The flip session |
| Waits for a streak of k | The k-th BEAR session of the streak |

**Real shift.** From the decision date's close, the lowest close over the next 60 sessions is
10% or more below it. The outcome is measured from each rule's own decision close, because that
is the price a trader acting on the rule would get. See the
[glossary](../../../glossary.md#real-shift).

**Conditions.** Each is read at the decision date's close.

| Code | Condition | Source series | First date usable |
|---|---|---|---|
| `C-200` | SPY close below its 200-day SMA | SPY | 1993-11 (200-day runway) |
| `C-CR` | HYG/IEF ratio's 20-session change below −1%, on Adj Close | HYG, IEF | 2007-05 |
| `C-IWM` | IWM close below its 200-day SMA | IWM | 2001-03 |
| `C-VIX` | VIX close at or above 20 | ^VIX | 1990-01 |

**Price basis.** `C-CR` uses the HYG/IEF ratio of Adj Close (dividend-adjusted), matching
`lib/regime_watch.py::_credit_change`. Unadjusted HYG drifts down by its distributions, so an
unadjusted ratio would read as credit weakness that is not there. Every other series uses
unadjusted Close.

**Missing data.** A condition whose series does not reach the decision date counts as **not
met**. The event stays in the arm's base; it is not dropped. The count of such events is printed
per condition.

_Resolved at build (2026-10-21):_ a condition reads its series' last close on or before the
decision date. It is missing only when no such close exists, or when the series is too short for
its 200-day SMA or its 20-session change.

**Market-wide on every ticker.** The four conditions read the series in the table above,
whatever the flip ticker. On a QQQ or IWM flip, `C-200` still reads SPY's close and SPY's
200-day SMA.

**Own 200-day condition.** For `RC-200` below, the flip ticker's own close is below its own
200-day SMA. On SPY flips it equals `C-200`.

## Dependencies

- `lib/mech_regime.py::compute_mech_table`, fed a temporary `date,spy_close,vix_close` CSV whose
  `spy_close` column carries the flip ticker's closes. Its frozen constants (50, 20) are the
  flip rule. Direction does not read VIX, so the VIX column may be blank.
- yfinance daily closes, `auto_adjust=False`, matching the convention in
  `scripts/collector/daily/fetch_mech_regime.py`: ^GSPC, SPY, QQQ, IWM, ^VIX, ^VIX3M, HYG, IEF.
  Close and Adj Close are both kept; only `C-CR` reads Adj Close.
- The repo's mech table (`backtests/mech_regime/spy_vix_daily_full.csv`) only reaches back to
  2023. It is used as a cross-check: on every date both cover, the study's SPY BEAR label must
  match the table's. A mismatch refuses the run (`RC-G0`).

## Population and basis, fixed here

| Scope | Flip ticker | Flip dates | Role |
|---|---|---|---|
| `RC-IS` | SPY | 1993-01-29 to 2026-10-21 | Spent. Printed as context, labelled post hoc, never graded |
| `RC-H1` | ^GSPC | 1950-01-03 to 1992-12-31 | Holdout, never read. Graded for `RC-P` and `RC-200` |
| `RC-H2` | QQQ and IWM, pooled | 1999-03-10 and 2000-05-26 to 2026-10-21 | Replication, correlated with `RC-IS`. Graded for `RC1` |
| `RC-FWD` | SPY, QQQ, IWM | After 2026-10-21 | Standing forward census and grade |

- **`RC-IS` is spent.** The exploration chose the conditions and the streak length on it. No
  figure from it carries a verdict.
- **`RC-H1` is the clean holdout.** Nobody has computed an outcome on ^GSPC before 1993 in this
  repo. It is the S&P 500 price index, not SPY, and it carries none of the four conditions except
  `C-VIX` from 1990. So `RC1` cannot be graded there; its two parts can. An `RC-H1` event's
  60-session outcome window must close on or before 1993-01-28, the day before SPY's first close.
- **`RC-H2` is a weak replication.** QQQ and IWM flips often fall within days of a SPY flip that
  the exploration saw, and their sell-offs are the same market's. A pass there shows the rule is
  not SPY-specific; it does not show the rule is out of sample. That is why `RC-H2` alone cannot
  earn `SUPPORTED`.
- **`RC-FWD`** holds flips whose flip date is after 2026-10-21. The SPY flip of
  2026-10-19 falls before it and after the exploration, so it is excluded from every graded
  scope and printed as a case.
- **Censoring.** An event with fewer than 60 sessions of closes after its decision date is
  excluded from that rule's rate and counted. Forward events are graded once their window closes.
  _Resolved at build (2026-10-21):_ a flip still BEAR at the data end, with fewer than k
  sessions so far, is not yet an event of a rule that waits for k. It is counted as pending.

## Plan-time observations, disclosed

**The exploration (2026-10-21, main session, `RC-IS`).** It motivated the study and is spent.

| Observation on SPY flips, n = 97 | Value |
|---|---|
| Real-shift rate at the flip (the base rate) | 11% |
| Median 60-day return from the flip | +3.9% |
| BEAR runs of 3 sessions or fewer | 56% |

| Condition at the flip | Real-shift rate if true | If false | n if true |
|---|---|---|---|
| SPY below 200-day SMA | 29% | 8% | 14 |
| Credit weak (from 2007) | 19% | 7% | 26 |
| IWM below 200-day SMA | 17% | 11% | 18 |
| VIX at or above 20 | 15% | 8% | 48 |
| VIX/VIX3M above 1 | 6% | 16% | 17 |

| Still BEAR after | Flips surviving | Real-shift rate | Median cost of waiting |
|---|---|---|---|
| 3 days | 44% | 14% | −0.6% |
| 10 days | 20% | 21% | −1.4% |

The candidate rule shown to the operator was a streak of 3 or more and 2 or more of `C-200`,
`C-CR`, `C-IWM`, `C-VIX`. The VIX term-structure condition read the opposite way to intuition,
so it is not in the rule.

**The drafter's census (2026-10-21, event counts only).** No outcome, return or drawdown was
computed on any scope. Its purpose is the power floor.

| Scope | Flips | Streak of 3 | `RC-200` events | `RC1` events |
|---|---|---|---|---|
| `RC-IS` SPY | 98 | 51 | 9 | 16 |
| `RC-H1` ^GSPC | 118 | 80 | 22 | 0 |
| `RC-H2` QQQ | 71 | 37 | 9 | 19 |
| `RC-H2` IWM | 77 | 41 | 11 | 17 |

The census found 98 SPY flips, where the exploration found 97, and a streak-of-3 share of 52%,
where the exploration found 44% "still BEAR after 3 days". The exploration's exact counting was
not recorded. The study's own counting, as defined above, is the one of record. The
exploration's figures are context only.

## What it compares

| Object | Object type | Rule | Graded on |
|---|---|---|---|
| `RC0` | control | Every flip, acting at the flip | Baseline in every scope |
| `RC1` | arm | Streak of 3 and 2 or more of the four conditions | **`RC-H2`, `RC-FWD`** |
| `RC-200` | arm | Streak of 3 and the own 200-day condition | **`RC-H1`**, and `RC-H2` as secondary |
| `RC-P` | arm | Streak of 3, no conditions | `RC-H1`, `RC-H2`, secondary |
| `RC-C` | arm | 2 or more of the four conditions at the flip, no wait | `RC-H2`, secondary |
| `RC-10` | descriptive cut | Streak of 10, no conditions | Printed only |
| `RC-TS` | descriptive cut | `RC0` split by VIX/VIX3M above 1, from 2007 | Printed only |

### RC1, the candidate rule

The rule as shown to the operator. It is the only object that could change a hedge decision.
Its four conditions only coexist from 2007, so its graded scopes are `RC-H2` and `RC-FWD`.

### RC-200, the part the holdout can test

Persistence plus a long-trend break, the strongest single condition in the exploration. It is
the only form of the rule that `RC-H1` can grade, and it is graded there as a co-primary.

### RC-P and RC-C, the two halves

They ask whether the wait alone, or the conditions alone, carry the effect. If `RC1` passes and
`RC-P` passes by the same margin, the conditions add nothing.

## How it is judged

- **Statistic.** For each arm, the real-shift rate of the arm's events minus `RC0`'s rate, in
  the same scope. Each rate is the share of a rule's decision events followed by a real shift.
- **Unit.** One event per flip per ticker. An arm's events are a subset of `RC0`'s flips, each
  judged from its own decision date.
- **Clusters.** Events are chained into clusters: two events join one cluster when their
  decision dates, from any ticker, fall within 60 SPY sessions of each other. On `RC-H2` this
  ties a QQQ flip to the IWM flip of the same sell-off.
- **CI.** 95% percentile bootstrap, resampling clusters with replacement, both rates from the same
  draw, 10,000 draws, seed 20260811.

_Resolved at build (2026-10-21):_ "60 SPY sessions" is counted on the ^GSPC session calendar.
It is the same NYSE calendar as SPY's from 1993, and the only one before. For each arm-versus-`RC0`
comparison, the arm's and `RC0`'s events are chained together, so one draw resamples both. The
`RC-G2` cluster count is the number of those joint clusters that hold an arm event.
- **Printed beside it**, for every arm and scope, from each event's decision close:

| Secondary outcome | Definition |
|---|---|
| 20-session return | Close 20 sessions later over the decision close, minus 1 |
| 60-session return | The same at 60 sessions |
| Max drawdown | Lowest close over the next 60 sessions over the decision close, minus 1 |
| False-alarm rate | Share of the arm's events with no real shift |
| Recall | Share of `RC0`'s real-shift flips that the arm also catches |
| Lag cost | Decision close over the flip close, minus 1; median and quartiles |

Medians carry a cluster-bootstrap CI on the same draws. Secondaries carry no verdict.

_Resolved at build (2026-10-21):_ recall counts a real-shift flip as caught when the arm acts on
that flip, whatever the arm's own outcome from its later decision close.

## Gates

- **`RC-G0`, data.** Every series loads with `auto_adjust=False` and no gap over 5 sessions in
  its graded span. The SPY BEAR labels match the repo's mech table on every shared date. Either
  failure refuses the run (exit 2). _Resolved at build (2026-10-21):_ a gap is the count of
  ^GSPC sessions missing between two consecutive closes; for ^GSPC itself, the weekdays between
  them. It is checked over each series' whole fetched span.
- **`RC-G1`, causality.** Every condition and label for a decision date uses closes on or before
  it. Every outcome uses closes strictly after it. The module asserts both per event.
- **`RC-G2`, floors.** An arm in a scope needs **20 uncensored events in 12 or more clusters**,
  and `RC0` needs 60 events. Below either floor the arm prints its census and `UNDERPOWERED`.
- **Expected width, stated now.** At 22 events and a rate near 20%, the arm's rate alone has a
  CI about ±0.17 wide. Only a difference near the exploration's 200-day gap (about +0.2) is
  likely to clear. A `NULL` here is weak evidence of no effect.
- **Expected wait, stated now.** On `RC-IS` the rate of `RC1` events was about one every two
  years per ticker. `RC-FWD` pools three correlated tickers, so its floor is likely more than a
  decade away. The forward grade is a standing census, not a verdict the operator should wait on.

## Verdicts, worded now

**Per arm, per scope:**

| Token | When |
|---|---|
| `SUPPORTED` | Floors met, CI on the difference wholly above 0 |
| `CONTRARY` | Floors met, CI wholly below 0 |
| `NULL` | Floors met, CI spans 0 |
| `UNDERPOWERED` | Below either floor; census printed, nothing concluded |

**The study's retrospective verdict** combines the two co-primaries, `RC1` on `RC-H2` and
`RC-200` on `RC-H1`:

| Token | When |
|---|---|
| `RETRO-SUPPORTED` | Both co-primaries `SUPPORTED` |
| `RETRO-CONTRARY` | Either co-primary `CONTRARY` |
| `RETRO-NULL` | Both past their floors, and neither of the above |
| `UNDERPOWERED` | Either co-primary below its floor, and neither `CONTRARY` |

**The forward verdict** is `RC1` on `RC-FWD`, with the per-arm tokens above, printing
`STILL-OPEN` in place of `UNDERPOWERED` until its floor is met.

**Multiple comparisons.** The retrospective verdict needs both co-primaries, an
intersection-union test, so each is tested at 5% with no correction. The secondary arms (`RC-P`
on both scopes, `RC-C`, `RC-200` on `RC-H2`) form one family under
[BH](../../../glossary.md#bh) at q < 0.05. They are printed, and none carries
a verdict. _Resolved at build (2026-10-21):_ each p-value is two-sided, from the same bootstrap
draws: twice the smaller share of draws at or below 0 and at or above 0. A member below its floor
enters the family at p = 1, so the family size stays 4.

**The verdict of record** is the first run that prints a retrospective token, and separately the
first forward run that prints a token other than `STILL-OPEN`. Later runs are descriptive.

## Anti-tuning

- Fixed here: the 20-session quiet look-back, the streak of 3, the four conditions and their
  thresholds (200-day SMA, −1% over 20 sessions, VIX 20), "2 or more of 4", the 10% drop, the
  60-session window, the 60-session cluster chain, the floors and the seed.
- No other streak length, condition, threshold, drop size or window is graded. `RC-10` and
  `RC-TS` print as they fall and cannot be promoted.
- `RC-IS` figures are printed beside every graded scope, labelled post hoc. None is dropped for
  looking bad.
- A rule suggested by a result here is a new registration on new dates.

## What could ship

Nothing ships from this study.

- `RETRO-SUPPORTED` lets the operator consider a §4 hedge-trigger policy or a dip-date sizing
  exception, each through its own registration and rollback trigger.
- `RETRO-NULL` or `RETRO-CONTRARY` closes the lead. `regime_watch.py` may still print flips, but
  it must not call a flip "confirmed".
- `UNDERPOWERED` changes nothing.
- No verdict here lets `regime_watch.py` feed `ladder_tier()`.
