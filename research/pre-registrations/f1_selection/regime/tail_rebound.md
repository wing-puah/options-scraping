## tail_rebound — after a SPY tail fall, does SPY beat its usual return over the next weeks?

<!-- outcome:start -->
> Latest outcome: `>>> tail_rebound A21 (SPY 21-session total return after an intraday 2x-VIX breach, first of each episode, vs unconditional, 1993 on): NO-EDGE <<<` (excess −0.40% [−1.47%, +0.64%], 110 clusters); `>>> tail_rebound B21 (SPY 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 1993 on): NO-EDGE <<<` (excess +0.44% [−0.98%, +1.75%], 68 clusters); A5, A63, B5, B63 `NO-EDGE`; forward `STILL-OPEN` — yfinance OHLC 1993-01-29 to 2026-11-13, run 2026-11-15 · [record](../../../study-results/f1_selection/regime/tail_rebound.md)
<!-- outcome:end -->

_Registered 2026-11-15._

**STATUS: REGISTERED (ACCEPTED BY DEFAULT 2026-11-15) on the drafter's recommended defaults; the
operator may revisit (a revisit after a result is a NEW registration, never an edit).** Drafted
2026-11-15 on the operator's question, with the drafter's defaults for every detail the operator
deferred. No forward return after any event had been computed or looked at by anyone before this
file was written. A fresh second reader checked it the same day. Its four blockers and its fixes
are folded in.

## The question

[`tail_breach_intraday`](tail_breach_intraday.md) asked whether two SPY tail events can be
forecast. It printed `NO-FORECAST` for the intraday 2σ breach and `UNDERPOWERED` for the 5% weekly
fall. The operator then asked the next question: once such a fall has happened, does SPY rebound?

- **Event A, intraday 2σ breach.** SPY's intraday low on session s falls more than twice the prior
  close's VIX-implied one-day move below the prior close. This is `tail_breach_intraday`'s event A.
- **Event B, a 5% fall completed.** SPY's intraday low on session s is at least 5% below the
  highest adjusted close of the five sessions before it. B fires on every such session, including
  each session of a weeks-long fall. The first session of an episode is the first time the fall is
  completed.

The graded question, for each event: is SPY's total return over the next h sessions, entered at the
trigger session's close, higher or lower than its return over any h sessions in the same history?
The primary horizon is h = 21 sessions, about one month.

This is a conditional-mean question with no fitted model. So it can use the full SPY history from
1993, which gives the power the 2024+ window lacked.

## What this study is not

- **Not an option study.** It prices no option and reads no position, tier, R or backtest row. A
  rebound in SPY says nothing on its own about what a call, a put spread or a short put would have
  paid after the fall.
- **Not a timing edge on its own.** Expected returns are higher when volatility is high. That is
  the textbook risk premium. A `REBOUND` verdict says the conditional mean is higher, not that the
  higher mean is free of the higher risk. The bar for a candidate, below, uses the VIX-scaled
  excess to separate the two.
- **Not a re-grade of `dip_buy`.** That study grades Tier A/B plays after SPY closes below its
  50-day SMA. This one reads SPY alone, after a tail fall.
- **Not a sweep.** Two events at one horizon are the co-primaries; two more horizons are
  secondaries. Every other cut is printed only.
- **Not pooled across eras.** The inputs are market data with no prompt version. There is one
  population and no `--era` replication.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price basis

- **Source.** The yfinance cache `tail_breach_intraday` keeps in `backtests/tail_breach_intraday/`:
  `SPY.csv` (date, open, high, low, close, adj_close) and `VIX.csv`. They are read through that
  module's `read_ohlc` and `build_icals`, imported unchanged. `build_icals` is passed an empty
  VIX3M map, which gives a NaN column this study never reads. Nothing is copied or refetched.
- **The calendar.** `read_ohlc` drops a session with no close, and `build_icals` drops one with no
  `Adj Close`. Every distance in sessions, below, is counted on that calendar.
- **Total-return basis.** `A_t` is SPY's `Adj Close` on session t. The total-return low is
  `L_t = Low_t × A_t / Close_t`, and the high and open are scaled the same way. This is
  `tail_breach_intraday`'s basis: an ex-dividend drop is not counted as a fall, and a return over
  h sessions includes the dividends paid in it.
- **VIX.** `^VIX` closes, matched to SPY sessions by exact date. `σ_t = VIX_{t−1} / 100 / √252`,
  as in `tail_breach`.

### Triggers

| Label | Rule on session s | Role |
|---|---|---|
| `A` | `ln(L_s / A_{s−1}) < −k × σ_s`, k = 2 (`tail_breach_intraday.intraday_down`) | Event A, graded |
| `A-1.5`, `A-2.5` | The same with k = 1.5 and k = 2.5 | Parameters, printed beside it |
| `B` | `L_s ≤ 0.95 × max(A_{s−5}, …, A_{s−1})` | Event B, graded |

- **Why B reads the maximum.** `tail_breach_intraday`'s B flags a window first session t when some
  low in t … t+4 reaches 0.95 × `A_{t−1}`. A session s completes such a window for some t exactly
  when its low reaches 0.95 times one of the five closes before it. That is the same as reaching
  0.95 times their maximum.
- **No lookahead.** Every input to either trigger is known by the close of session s. A low can
  only fall during the day, so once the low has crossed its threshold the trigger is certain, even
  before the close. The one exception is a low set in the closing auction itself. It is disclosed,
  not corrected.
- **Undefined sessions.** A trigger is undefined, and the session is out, when an input it reads is
  missing: `A` needs `VIX_{s−1}`, `L_s` and `A_{s−1}`; `B` needs `L_s` and all five prior closes.

### Episodes and entries

- **Episode.** A trigger starts a new episode when the previous trigger is more than 5 sessions
  before it; otherwise it joins the current one. This is `tail_breach.episodes`'s rule. That
  function returns a count, so a new helper returns each episode's first session, and a test checks
  that the helper's length equals `episodes()`.
- **Chained on the whole series.** Episodes are formed over every session before any split into
  sample and forward. A trigger after the registration date that chains to an earlier trigger is
  not a forward entry.
- **The gap counts sessions on the calendar,** undefined sessions included.
- **Entry.** The first trigger session of each episode, entered at its close.
- **Every trigger, printed only.** Entering on every trigger session is printed beside the graded
  line.

### Outcome

- **Return.** `R_h(s) = ln(A_{s+h} / A_s)`, the log total return from the close of session s to the
  close h sessions later.
- **Eligible sessions.** Every session s in the same population on which the event's trigger is
  defined and `R_h(s)` is defined. The unconditional reference is the mean of `R_h` over every
  eligible session, trigger sessions included.
- **Excess.** `E_h = mean of R_h over the entries − mean of R_h over the eligible sessions`. Each
  entry counts once.

### Clusters

Two entries fewer than h sessions apart have overlapping outcome windows, so their returns are not
independent. An entry joins the current **cluster** when it is fewer than h sessions after the
previous entry; otherwise it starts a new one.

- Clusters are formed separately for each event and each h.
- They are formed separately in the sample and in the forward population, never across the
  boundary.
- They are the resampling unit and the power floor's unit.

## Dependencies

- `backtests/tail_breach_intraday/SPY.csv` and `VIX.csv`, the cache `tail_breach_intraday`
  fetched from yfinance. This study never fetches. A missing file refuses (exit 3) and says to run
  `tail_breach_intraday -- --refresh`. Forward runs refresh the cache that way first; otherwise the
  forward population never grows.
- `scripts/backtest_study/f1_selection/regime/tail_breach_intraday.py` (`read_ohlc`,
  `build_icals`, `ICal`, `intraday_down`, `ohlc_problems`, `cross_feed_problems`), imported
  unchanged.
- `scripts/backtest_study/f1_selection/regime/tail_breach.py` (`episodes`, `ratio_problems`,
  `base_rate_problems`, `block_indices`, the report helpers), imported unchanged.
- `scripts/backtest_study/f1_selection/benchmark/ticker_class.py::holm` and `lib/era.py`, imported
  unchanged.
- `backtests/mech_regime/spy_base_rate_daily.csv` and `backtests/underlying_ohlc_cache/SPY.csv`,
  read only by the basis gates, as in `tail_breach_intraday`.
- No Barchart call, no Sheets export and no backtest row.

## Population and basis, fixed here

- **Era.** Only the default era `current` runs. Any other `STUDY_ERA` refuses (exit 2).
- **Seal.** The [holdout seal](../../f4_deployment/holdout_seal.md) binds the signal dates of emitted
  plays. This study reads no flow signal, play or backtest row, so the seal does not apply.
- **The registration date** enters the code as the constant `REGISTERED`, 2026-11-15.
- **Sample.** Entries and eligible sessions from the first session, 1993-01-29, whose whole outcome
  window, s through s+h, is on or before `REGISTERED`.
- **Forward.** Entries and eligible sessions after `REGISTERED` whose window is complete in the
  data.
- **Counted, in neither.** An entry on or before `REGISTERED` whose window ends after it is a gap
  entry. An entry whose window runs past the last session in the data is an open entry. The report
  prints both counts per arm.
- **Report header.** The report prints `era: current (inputs are unversioned market data)`, the SPY
  session range, the git sha, the dirty flag and every input file read.

## Plan-time observations, disclosed

### Public market history the drafter knows

- **Continuation cases.** SPY kept falling for months after the first sharp falls of late 2008.
  The 2000–2002 and 2022 bear markets held many tail falls followed by further falls.
- **Rebound cases.** March 2020 and April 2025 were followed within weeks by sharp V-shaped
  rebounds. So was the volatility spike of early August 2024.
- **Mixed or short cases.** The drafter also knows the outlines of 1998 (LTCM), August 2011, and
  February and December 2018. They sit in the sample and bear on both events.
- **The general pattern.** It is widely reported that the largest up days cluster near the largest
  down days. The drafter expects the excess to be positive on average and very noisy. That is an
  expectation, not a count.

### What earlier studies showed

`tail_breach_intraday` printed these counts on 2026-11-14. No forward return was computed in that
study or since.

| Fact, from `tail_breach_intraday` | Value |
|---|---|
| `A` sessions, 2024 to 2026-11-13 | 18, in 13 episodes |
| `A` sessions, 2006-07-18 to 2023-12-29 | 131, in 85 episodes |
| `B` windows by first session, 2024 to 2026-11-13 | 14, in 3 episodes |
| `B` windows by first session, 2006-07-18 to 2023-12-29 | 292, in 61 episodes |

- `B` here is indexed by the session that completes the fall, not by the window's first session.
  So its counts will differ, but its episodes should be close to those above.
- That study's report shows the 2024+ episodes only as counts per year. Public price history would
  let anyone match them to the sell-offs named above.

### Data checks made for this file

A data check on 2026-11-15 on the cached SPY file found no out-of-order OHLC and no session with
the high equal to the low in 1993–2007. So gate GO, run from 1993, is already known to pass. No low
was compared with a threshold and no return was computed for this file.

### Power, from a prior

- **Episodes.** The counts above, extended to 1993–2005 at a similar rate, suggest roughly 130 to
  170 `A` episodes and 70 to 90 `B` episodes in the sample.
- **Clusters.** At h = 21, overlapping windows should merge these into roughly 60 to 100 `A`
  clusters and 35 to 60 `B` clusters.
- **h = 63 is at risk.** In 2000–2002 and 2008–2009, entries arrive every few weeks, so one
  cluster can chain years of entries. The concentration rule under the gates guards against a
  bootstrap that turns on whether one cluster is drawn. `A63` or `B63` may fail it.
- **What that detects.** A 21-session return after a tail fall has a standard deviation of perhaps
  6% to 8%. With 40 clusters the standard error of the excess is about 1% to 1.3%. So an excess
  smaller than about 2.5 percentage points over a month is unlikely to be detected. Published
  post-crash reversal effects are often near or below that size.
- **2024+ alone.** With 13 `A` episodes and about 3 `B` episodes, the 2024+ subperiod is printed
  only, and would fail the floor if it were graded.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `A21` | arm | Excess after event A entries, h = 21 | Co-primary, Holm m = 2 with `B21` |
| `B21` | arm | Excess after event B entries, h = 21 | Co-primary, Holm m = 2 with `A21` |
| `A5`, `A63`, `B5`, `B63` | arm | The same at h = 5 and h = 63 | Secondary, one Holm family, m = 4 |
| Unconditional | control | Mean `R_h` over every eligible session in the same population | The reference each excess is measured from |
| `FORWARD` | population scope | `A21` and `B21` on entries after the registration date | Forward verdicts |

### `A21`, `A5`, `A63`

Event A entries, the first intraday 2σ breach of each episode, at h = 21, 5 and 63. `A21` asks
whether a month after the first breach beats a usual month.

### `B21`, `B5`, `B63`

Event B entries, the first session of each episode on which a 5% fall from a recent close is
completed, at h = 21, 5 and 63.

### Why two co-primaries with Holm

The operator asked one question about two events. Grading both on an uncorrected interval would
give two chances at a false yes. So `A21` and `B21` form one Holm family, m = 2. The report prints
each arm's unadjusted word beside its graded word.

### Printed only, never graded

| Label | What it prints |
|---|---|
| `EVERY` | Each arm with every trigger session as an entry, clusters re-formed |
| `K-PARAM` | `A` arms with k = 1.5 and k = 2.5 |
| `OPEN` | Each arm entered at the next session's open: `ln(A_{s+h} / O_{s+1})`, total-return open, against the same formula on every eligible session |
| `HIT` | Share of entries with `R_h > 0`, against the share of eligible sessions |
| `MAE`, `MFE` | Mean and median of `ln(min L / A_s)` and `ln(max H / A_s)` over sessions s+1 … s+h, entries against eligible sessions |
| `VIX-SCALED` | Each entry's and each eligible session's `R_h`, divided by its own `VIX_s / 100 × √(h/252)`; the entry mean minus the eligible mean |
| `DECADE` | Each arm's excess per decade of entry (1993–1999, 2000–2009, 2010–2019, 2020–2026), against its own decade's eligible sessions |
| `2024+` | Each arm's excess on entries from 2024-01-02, against that subperiod's eligible sessions |
| `CENSUS` | Per arm: clusters, the largest cluster's entries and its share of all entries |

- Every printed-only line uses the same cluster bootstrap and prints its CI and cluster count.
  None carries a verdict.
- A line whose value needs more inputs than `R_h` uses its own eligible set: `MAE` and `MFE` need
  every low and high in s+1 … s+h, `OPEN` the next open, `VIX-SCALED` `VIX_s`.
- A window that crosses a decade boundary belongs to the decade of its entry s.
- The operator asked for MAE and MFE split out. They show how far SPY fell further, and rose,
  inside the window, which a final return hides.

## How it is judged

- **Statistic.** The excess `E_h` above, for each arm.
- **Bootstrap.** Resample the arm's clusters with replacement, as many as there are, 10,000 times,
  seed 20261115. Each draw pools the entries in the drawn clusters and takes their mean `R_h`,
  minus the unconditional mean.
- **The unconditional mean is held fixed.** It averages thousands of sessions, so its own sampling
  error is small next to the entry mean's. Holding it fixed makes the interval slightly too
  narrow. The report prints the unconditional mean's own half-width beside it, from a moving-block
  bootstrap with 63-session blocks. That half-width is printed only, never a gate.
- **CI.** The 2.5th and 97.5th percentiles of the draws.
- **p-value.** Two-sided, from the same draws: twice the smaller of the share at or below 0 and the
  share at or above 0, capped at 1. This is the convention of `tail_breach`.
- **Multiple comparisons.** `A21` and `B21` form one Holm family, m = 2. `A5`, `A63`, `B5` and `B63`
  form another, m = 4.
- **The CI and Holm clauses agree.** A Holm p below 0.05 implies an unadjusted p below 0.05, and so
  a 95% CI clear of 0. The verdict table states both so a builder need not derive it.
- **A gated arm stays in its family.** m stays 2 or 4 whatever the gates print. An arm that is
  `UNDERPOWERED` enters its family with p = 1.

## Gates

- **GE, inputs.** `SPY.csv` and `VIX.csv` exist in the `tail_breach_intraday` cache and are not
  empty. Any failure refuses (exit 3).
- **GB, basis.** `tail_breach`'s two checks, imported unchanged: the close-to-`Adj Close` ratio
  never steps like a split, and the close and VIX agree with `spy_base_rate_daily.csv` within 0.5%.
  Any failure refuses (exit 3).
- **GO, OHLC order.** `tail_breach_intraday`'s check, run from the first session, 1993-01-29, not
  from 2006: every session has a high and a low, in order. Any failure refuses (exit 3). The
  2026-11-15 data check says it passes.
- **GC, cross-feed.** `tail_breach_intraday`'s check against the Barchart cache. Skipped without
  the file, and the report says so.
- **GX, no lookahead.** The tests recompute both triggers on a series cut at session s, and on a
  series whose later sessions are all changed. The trigger at s must not change.
- **GN, clusters.** At least 10 clusters for the arm in the sample, and the largest cluster holds
  at most a third of the arm's entries. Otherwise the arm prints `UNDERPOWERED`.
- **Era.** Any era but `current` refuses (exit 2).

**Why 10 clusters.** It is the floor `tail_breach` and `tail_breach_intraday` used for episodes.
Below 10, each draw's mean turns on which few clusters it holds, and the interval measures that
rather than the rebound.

**Why a third.** When one cluster holds most entries, a draw's mean depends mainly on whether that
cluster is drawn. Ten clusters do not guard against that on their own.

| Population | Floor |
|---|---|
| Sample | 10 clusters per arm, largest cluster at most a third of entries (GN) |
| Forward | The same, per arm |

## Bar for a candidate

No result here makes a candidate rule.

- A `REBOUND` or `CONTINUATION` co-primary files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md). It waits on its forward read and on
  an option study that prices the trade.
- A `REBOUND` whose VIX-scaled CI spans 0 files as "risk premium, not timing". The higher mean is
  then no more than the higher implied risk pays.

## Verdicts, worded now

**`A21` and `B21`:**

| Token | When |
|---|---|
| `REBOUND` | GN met, the excess CI lower bound above 0, and the Holm-adjusted p (m = 2) below 0.05 |
| `CONTINUATION` | GN met, the excess CI upper bound below 0, and the Holm-adjusted p (m = 2) below 0.05 |
| `NO-EDGE` | GN met, and neither of the above |
| `UNDERPOWERED` | GN unmet, or the CI is not finite; census printed, nothing concluded |

- `NO-EDGE` prints its CI. It reads as "no excess outside the interval", not as "no rebound".

**`A5`, `A63`, `B5`, `B63`.** The same tokens, with the Holm p of their own family (m = 4).

**FORWARD.** `A21` and `B21` on forward entries, each against the forward population's own
eligible sessions, with the same tokens and no Holm step. `STILL-OPEN` takes the place of
`UNDERPOWERED` until the arm meets the forward floor. The verdict of record is the first forward
run that prints a token other than `STILL-OPEN`. For `B` that is likely a decade away.

**The banner.** The report's section titled VERDICT prints:

```
>>> tail_rebound A21 (SPY 21-session total return after an intraday 2x-VIX breach, first of each episode, vs unconditional, 1993 on): REBOUND | CONTINUATION | NO-EDGE | UNDERPOWERED <<<
>>> tail_rebound B21 (SPY 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 1993 on): REBOUND | CONTINUATION | NO-EDGE | UNDERPOWERED <<<
>>> tail_rebound SECONDARY (h = 5 and 63, Holm m=4): A5 <w> A63 <w> B5 <w> B63 <w> <<<
>>> tail_rebound FORWARD (entries after the registration date): A21 <w> B21 <w> <<<
```

## Anti-tuning

- Fixed here: both trigger rules, k = 2 and the 5% move, the 5-session episode chain, the
  first-of-episode entry at the close, the price basis, the horizons 5, 21 and 63, the statistic,
  the cluster rule, the seed, the floor and the concentration rule, the Holm families and the
  verdict words.
- k = 1.5 and 2.5, every-trigger entry, next-open entry, the hit rate, MAE and MFE, the VIX-scaled
  excess, the decades and the 2024+ subperiod are printed as they fall. Only the VIX-scaled CI is
  used, and only to file a `REBOUND` as risk premium; none re-grades a verdict.
- No other trigger, horizon, entry rule or reference is graded.
- This registration is immutable in substance once accepted. Editorial consolidation only.

## What could ship

Nothing ships from this study.

- A `REBOUND` or `CONTINUATION` co-primary files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md).
- No verdict here changes a tier, a veto, a size class, an exit, the deploy card or the hedge
  sleeve's timing rule in [§4](../../../../docs/deployment-rules.md#s4).
