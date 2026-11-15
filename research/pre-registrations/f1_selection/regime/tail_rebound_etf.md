## tail_rebound_etf — does QQQ or SMH beat its usual return after a tail fall?

<!-- outcome:start -->
> Latest outcome: `>>> tail_rebound_etf QQQ-A21 (QQQ 21-session total return after an intraday 2x-VXN breach, first of each episode, vs unconditional, 2001 on): NO-EDGE <<<` (excess −0.66% [−1.97%, +0.61%], 89 clusters); QQQ-B21 `NO-EDGE` (+0.56% [−0.86%, +1.94%], 96 clusters); SMH-A21 `NO-EDGE` (+0.02% [−0.99%, +1.06%], 106 clusters); SMH-B21 `NO-EDGE` (+0.27% [−0.97%, +1.47%], 107 clusters); secondaries `NO-EDGE` except SMH-A63 `UNDERPOWERED`; forward `STILL-OPEN` — yfinance OHLC to 2026-11-13, run 2026-11-15 · [record](../../../study-results/f1_selection/regime/tail_rebound_etf.md)
<!-- outcome:end -->

_Registered 2026-11-15._

**STATUS: REGISTERED (ACCEPTED BY DEFAULT 2026-11-15) on the drafter's recommended defaults; the
operator may revisit (a revisit after a result is a NEW registration, never an edit).** Drafted
2026-11-15 on the operator's question, with the drafter's defaults for every detail the operator
deferred. No forward return after any event, on either ETF, had been computed or looked at by
anyone before this file was written. A fresh second reader checked it the same day. Its two
blockers and ten fixes are folded in.

## The question

[`tail_rebound`](tail_rebound.md) asked whether SPY beats its usual return after a tail fall. It
printed `NO-EDGE` on every arm on 2026-11-15. The operator then asked the same question for two
technology ETFs: QQQ (the Nasdaq-100) and SMH (semiconductors).

- **Event A, intraday 2σ breach.** The ETF's intraday low on session s falls more than twice the
  prior close's implied one-day move below the prior close. The implied move comes from `^VXN`,
  the Nasdaq-100 volatility index, for both ETFs.
- **Event B, a 5% fall completed.** The ETF's intraday low on session s is at least 5% below the
  highest adjusted close of the five sessions before it.

The graded question, for each ETF and each event: is the ETF's total return over the next h
sessions, entered at the trigger session's close, higher or lower than its return over any h
sessions in the same history? The primary horizon is h = 21 sessions, about one month.

This file is a new registration. `tail_rebound`'s registration is immutable, so its rules are
imported here, not edited. This study's own rules are the data source, the volatility source, the
GB limit, the SMH relaunch handling, and the printed-only `MOVE-PARAM`, `VOL-ALT`, `RELAUNCH` and
`VS-SPY` lines. Every other rule is `tail_rebound`'s, applied to a different ticker.

## What this study is not

- **Not an option study.** It prices no option and reads no position, tier, R or backtest row.
- **Not a timing edge on its own.** Expected returns are higher when volatility is high. A
  `REBOUND` verdict says the conditional mean is higher, not that it is free of the higher risk.
  The VXN-scaled excess, below, separates the two.
- **Not a re-grade of `tail_rebound`.** SPY's verdicts stand. The SPY comparison below is printed
  only.
- **Not a sweep.** Two events at one horizon on two ETFs are the co-primaries; two more horizons
  are secondaries. Every other cut is printed only.
- **Not pooled across eras.** The inputs are market data with no prompt version.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price basis

- **Source.** yfinance daily OHLC with `auto_adjust=False`, cached in `backtests/tail_rebound_etf/`
  as `QQQ.csv`, `SMH.csv` and `VXN.csv` (date, open, high, low, close, adj_close). The module's
  `--refresh` flag fetches them. A plain run never fetches.
- **Reader.** Each file is read through `tail_breach_intraday.read_ohlc`, and each ETF's calendar
  is built by `tail_breach_intraday.build_icals`, both imported unchanged.
- **The VIX slot.** The calendar's VIX slot holds the volatility source in index points, so
  `implied_sigma` and `intraday_down` read it unchanged. It divides by 100 × √252 and shifts one
  session, so the value at index s−1 sets σ_s. The primary calendar holds VXN. `VOL-ALT` builds a
  second calendar per ETF with `VIX.csv` in the slot, and a third with `RV20` (below).
- **The calendar.** Each ETF has its own session calendar. Every distance in sessions is counted
  on it.
- **Total-return basis.** `A_t` is the ETF's `Adj Close`. The total-return low is
  `L_t = Low_t × A_t / Close_t`, and the open and high are scaled the same way. This is
  `tail_rebound`'s basis.
- **SPY.** The `VS-SPY` comparison reads `tail_breach_intraday`'s cached `SPY.csv` and `VIX.csv`
  through `tail_rebound.load_inputs`, unchanged.

### Volatility for event A

| Label | σ_s, the implied one-day move used on session s | Role |
|---|---|---|
| `VXN` | `VXN_{s−1} / 100 / √252` | Primary, both ETFs |
| `VIX` | `VIX_{s−1} / 100 / √252` | Printed only |
| `RV20` | The sample standard deviation (ddof 1) of the 20 daily log total returns `ln(A_i / A_{i−1})`, i = s−20 … s−1 | Printed only |

- **Why VXN for SMH.** SMH has no implied-volatility index of its own. VXN is the nearest listed
  one, since semiconductors are a large part of the Nasdaq-100. SMH is more volatile than the
  Nasdaq-100, so a 2σ VXN breach is a smaller move for SMH in its own units. `RV20` prints what an
  own-volatility trigger gives.
- **How `RV20` fills the slot.** The slot at index s−1 holds the sample standard deviation of the
  20 log returns ending at `A_{s−1}`, scaled to index points. So σ_s is that standard deviation.
- **No lookahead in `RV20`.** It reads closes up to `A_{s−1}`, all known before session s opens.
- **Event A is first defined on the session after VXN's first close.** VXN's first close is
  2001-01-23, so event A starts on 2001-01-24.
- **VXN's own history was not checked.** Cboe has revised how VXN is calculated since 2001, and
  yfinance's early values may follow an older method. The drafter did not check which. Either way,
  the A threshold may shift over time for reasons unrelated to the ETFs.

### Triggers

| Label | Rule on session s | Role |
|---|---|---|
| `A` | `ln(L_s / A_{s−1}) < −k × σ_s`, k = 2, σ from VXN (`tail_breach_intraday.intraday_down`) | Event A, graded |
| `A-1.5`, `A-2.5` | The same with k = 1.5 and k = 2.5 | Printed only |
| `B` | `L_s ≤ 0.95 × max(A_{s−5}, …, A_{s−1})` (`tail_rebound.completed_fall`) | Event B, graded |
| `B-7.5`, `B-10` | The same with 7.5% and 10% falls | Printed only |

- **Why print 7.5% and 10%.** SMH's daily moves are about twice SPY's. A 5% fall in five sessions
  is ordinary for it, so the 5% event may be too common to mark a tail. The larger falls show
  whether the answer changes for rarer moves.
- **No lookahead.** Every input to either trigger is known by the close of session s. A low set in
  the closing auction itself is disclosed, not corrected, as in `tail_rebound`.
- **Undefined sessions.** A trigger is undefined, and the session is out, when an input it reads is
  missing.

### Episodes, entries, outcome and clusters

These are `tail_rebound`'s, imported unchanged, and applied to each ETF on its own calendar.

- **Episode.** A trigger starts a new episode when the previous trigger is more than 5 sessions
  before it. Episodes are chained over the whole series, before any split into sample and forward.
- **Entry.** The first trigger session of each episode, entered at its close.
- **Return.** `R_h(s) = ln(A_{s+h} / A_s)`.
- **Eligible sessions.** Every session of the same ETF and population on which the event's trigger
  is defined and `R_h(s)` is defined. The unconditional reference is their mean `R_h`.
- **Excess.** `E_h` = the mean `R_h` over the entries minus the mean over the eligible sessions.
- **Cluster.** An entry fewer than h sessions after the previous entry joins its cluster. Clusters
  are formed per ETF, event and h, separately in the sample and forward populations.

## Dependencies

- `backtests/tail_rebound_etf/QQQ.csv`, `SMH.csv` and `VXN.csv`, fetched from yfinance by this
  module's `--refresh`. A missing file refuses (exit 3) and names the flag.
- `backtests/tail_breach_intraday/SPY.csv` and `VIX.csv`, read for the `VIX` column and the SPY
  comparison. A missing file refuses (exit 3) and names `tail_breach_intraday -- --refresh`.
- `scripts/backtest_study/f1_selection/regime/tail_rebound.py`, imported unchanged: the triggers,
  episodes, clusters, outcomes, windows, `excess_ci`, `word`, `forward_word` and `family_p`.
- Through it, `tail_breach_intraday.py` (`read_ohlc`, `build_icals`, `intraday_down`,
  `ohlc_problems`, `cross_feed_problems`) and `tail_breach.py` (`implied_sigma`, report helpers),
  imported unchanged.
- `tail_breach.ratio_problems` hardcodes its 2% limit, so gate GB re-implements its logic with the
  limit as a parameter. A test pins the new check at 2% to the original's output.
- `backtests/underlying_ohlc_cache/QQQ.csv` and `SMH.csv`, the Barchart cache, read only by gate GC.
- No Barchart call, no Sheets export and no backtest row.

## Population and basis, fixed here

- **Era.** Only the default era `current` runs. Any other `STUDY_ERA` refuses (exit 2).
- **Seal.** The [holdout seal](../../f4_deployment/holdout_seal.md) binds the signal dates of emitted
  plays. This study reads no flow signal, play or backtest row, so the seal does not apply.
- **The registration date** enters the code as the constant `REGISTERED`.
- **Sample.** Entries and eligible sessions whose whole outcome window, s through s+h, is on or
  before `REGISTERED`.
  - QQQ starts at its first yfinance session, 1999-03-10. SMH starts at its first, 2000-06-05.
  - Event A starts on 2001-01-24, the session after VXN's first close, for both.
- **Forward.** Entries and eligible sessions after `REGISTERED` whose window is complete in the
  data.
- **Counted, in neither.** Gap entries and open entries, as in `tail_rebound`. The report prints
  both counts per arm.
- **Report header.** The report prints `era: current (inputs are unversioned market data)`, each
  ETF's session range, the git sha, the dirty flag and every input file read.

### SMH before its 2011 relaunch

- **What changed.** Before 2011-12-20 the ticker SMH was Merrill Lynch's Semiconductor HOLDRS, a
  fixed basket. On that date VanEck's Market Vectors Semiconductor ETF took the ticker. yfinance
  splices both into one series.
- **What the data show.** The splice has no price break: the close-to-`Adj Close` ratio does not
  step, and no raw close moves more than 25% in a day. But yfinance records no dividend for SMH
  before 2012. Its first dividend step is 2012-12-24, and there is one each December after.
- **What that means.** Before 2012, SMH's "total return" here is price return only. The HOLDRS
  basket did pass dividends through, so pre-2012 returns are understated by its yield.
- **How large the bias is.** Entries and eligible sessions both lose the yield, so the excess loses
  only the difference in their pre-2012 shares. It biases the SMH excess downward by at most the
  yield × h/252. At h = 21 and a yield up to 2%, that is under 0.2%, well below the standard
  error.
- **Default.** The full SMH history is primary. The post-relaunch subset, entries and eligible
  sessions from 2011-12-20, is printed only as `RELAUNCH`.

## Plan-time observations, disclosed

### What the drafter already knows

- **SPY's answer.** `tail_rebound` printed `NO-EDGE` on all six SPY arms on 2026-11-15. Its A21
  excess was −0.40% and its B21 excess +0.44%, both with intervals spanning 0. The drafter read
  those figures before writing this file.
- **The tickers were picked after SPY's null.** QQQ moves closely with SPY, so most of QQQ's tail
  falls share dates with SPY's. SPY's result is therefore partly informative about QQQ. A verdict
  here is one of three tickers tried, and the Holm family covers only the four arms in this file.
- **The dot-com collapse.** QQQ fell about 80% from March 2000 to October 2002, and SMH fell
  further. The full sample holds it. Its many tail falls were mostly followed by further falls, so
  it weighs against a rebound, most on B and on h = 63.
- **Event A misses the start of the collapse.** VXN starts in January 2001, ten months after the
  peak, so the A arms see the second half of the collapse only.
- **V-rebounds.** March 2020 and April 2025 were followed within weeks by sharp rebounds in both
  ETFs. So was the August 2024 spike.
- **Other known cases.** 2008, 2018 and 2022 are in the sample. 2022 was a long tech bear market
  with many tail falls.

### Data checks made for this file

These checks ran on 2026-11-15, after the fetch. No low was compared with a threshold and no
return was computed.

| Check | QQQ | SMH | VXN |
|---|---|---|---|
| Sessions, first to last | 6,965, 1999-03-10 to 2026-11-13 | 6,652, 2000-06-05 to 2026-11-13 | 6,492, 2001-01-23 to 2026-11-13 |
| Missing open, high, low, close or adj close | 0 | 0 | 0 |
| OHLC out of order, from the first session (GO) | 0 | 0 | not checked (close only) |
| Close-to-adj ratio steps outside `tail_breach`'s 2% limit | 0 | 2 (see below) | — |
| Raw close moves over 25% in a day | 0 | 0 | — |
| Barchart cross-feed, low within 0.5% (GC) | 1,066 common from 2022-08-17, 0 off | 999 common from 2022-08-17, 0 off | — |
| ETF sessions from 2001-01-23 with no VXN close | 0 | 0 | — |
| ETF sessions with no VIX close in the SPY cache | 0 | 0 | — |

- **SMH's two ratio steps** are 2012-12-24 (−2.12%) and 2015-12-21 (−2.12%). Both are its annual
  December dividends, which exceed the 2% limit `tail_breach` set for SPY's quarterly ones. Gate GB
  below allows a single step down of up to 3%.
- **yfinance's close is split-adjusted.** SMH split 2-for-1 in May 2023 and the raw close shows no
  step. The Barchart cache matches it, so it is split-adjusted too.
- **GC covers 2022-08-17 on only.** The Barchart caches start there, so the cross-feed checks
  nothing in the dot-com, 2008 or HOLDRS years.
- **VXN** has four sessions in February 2017 with the high equal to the low. Only VXN's close is
  read.

### Power, from a prior

- **Event A.** SPY gave 110 A21 clusters over 1993–2026. VXN starts in 2001, and QQQ's breaches in
  VXN units should run at a rate near SPY's in VIX units. So QQQ A21 should have roughly 70 to 100
  clusters. SMH breaches VXN more often, since its own volatility is higher.
- **Event B.** A 5% fall is more common for QQQ than for SPY and much more common for SMH. So B
  should have more episodes than SPY's 68 B21 clusters, but they merge more at h = 63.
- **h = 63 is at risk.** In the long bear markets named above, entries arrive every few weeks, and one
  cluster can chain a year or more. `B63`, mainly on SMH, may fail the concentration rule.
- **What that detects.** A 21-session return after a tail fall has a standard deviation of perhaps
  9% to 12% for these ETFs. With 60 clusters the standard error of the excess is about 1.2% to
  1.5%. So an excess below about 3 percentage points a month is unlikely to be detected.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `QQQ-A21`, `QQQ-B21`, `SMH-A21`, `SMH-B21` | arm | The excess after event A or B entries, h = 21 | Co-primary, one Holm family, m = 4 |
| `QQQ-A5`, `QQQ-A63`, `QQQ-B5`, `QQQ-B63`, `SMH-A5`, `SMH-A63`, `SMH-B5`, `SMH-B63` | arm | The same at h = 5 and 63 | Secondary, one Holm family, m = 8 |
| Unconditional | control | Mean `R_h` over every eligible session of the same ETF and population | The reference |
| `FORWARD` | population scope | The four co-primaries on entries after the registration date | Forward verdicts |

### Why four co-primaries in one Holm family

The operator asked one question about two events on two ETFs. Grading four arms on uncorrected
intervals would give four chances at a false yes. So the four h = 21 arms form one Holm family,
m = 4. QQQ and SMH are highly correlated, so Holm is conservative here; it is used anyway because
it needs no estimate of that correlation. The report prints each arm's unadjusted word beside its
graded word.

### Printed only, never graded

| Label | What it prints |
|---|---|
| `EVERY` | Each arm with every trigger session as an entry |
| `K-PARAM` | `A` arms with k = 1.5 and 2.5 |
| `MOVE-PARAM` | `B` arms with 7.5% and 10% falls |
| `VOL-ALT` | `A` arms with σ from `VIX` and from `RV20`, for both ETFs |
| `OPEN` | Each arm entered at the next session's total-return open |
| `HIT` | Share of entries with `R_h > 0`, against the share of eligible sessions |
| `MAE`, `MFE` | Mean and median worst and best excursion over sessions s+1 … s+h, entries against eligible sessions |
| `VOL-SCALED` | Each `R_h` divided by `VXN_s / 100 × √(h/252)`; the entry mean minus the eligible mean |
| `DECADE` | Each arm per span of entry: 1999–2009, 2010–2019, 2020–2026 |
| `2024+` | Each arm on entries from 2024-01-02 |
| `RELAUNCH` | SMH arms on entries and eligible sessions from 2011-12-20 |
| `VS-SPY` | Each arm's excess of `R_h^ETF − R_h^SPY` on the same dates (see below) |
| `CENSUS` | Per arm: clusters, the largest cluster's entries and its share |

- **`VS-SPY`.** For each ETF session s, `D_h(s) = R_h^ETF(s) − R_h^SPY(s)`, where
  `R_h^SPY(s) = ln(A^SPY[date(s+h)] / A^SPY[date(s)])` on the ETF's own dates. A session whose two
  dates are not both in SPY's file leaves the pool. Its excess over the ETF arm's own entries and eligible sessions equals the ETF's excess
  minus SPY's excess on the same dates. A positive value says the ETF rebounded more than SPY did
  after the ETF's own falls. Sessions with no SPY match leave the pool.
- **`VOL-SCALED`** uses VXN for both ETFs. It sizes each return against the implied move, so a
  higher mean that only matches higher implied risk scales to near zero.
- Every printed-only line uses the same cluster bootstrap and prints its CI and cluster count. None
  carries a verdict. A line whose value needs more inputs than `R_h` uses its own eligible set.

## How it is judged

These are `tail_rebound`'s rules, with the families widened.

- **Statistic.** The excess `E_h`, for each arm.
- **Bootstrap.** Resample the arm's clusters with replacement, 10,000 times, seed 20261115. Each
  draw pools the entries in the drawn clusters and takes their mean `R_h`, minus the unconditional
  mean.
- **The unconditional mean is held fixed.** It averages thousands of sessions, so its own sampling
  error is small next to the entry mean's. Holding it fixed makes the interval slightly too
  narrow. The report prints its half-width from a moving-block bootstrap with 63-session blocks,
  printed only.
- **CI.** The 2.5th and 97.5th percentiles of the draws.
- **p-value.** Two-sided, from the same draws: twice the smaller of the share at or below 0 and the
  share at or above 0, capped at 1.
- **Multiple comparisons.** The four co-primaries form one Holm family, m = 4. The eight
  secondaries form another, m = 8.
- **A gated arm stays in its family.** m stays 4 or 8 whatever the gates print. An arm that is
  `UNDERPOWERED` enters its family with p = 1.

## Gates

- **GE, inputs.** The three ETF-side files and the two SPY-side files exist and are not empty. Any
  failure refuses (exit 3).
- **GB, basis.** GB checks every day-to-day change in close/`Adj Close`, per ETF.
  - A fall may be at most 3%, so an annual dividend passes; `tail_breach` allowed 2%. Every step
    may reach the limit, not just one.
  - A rise may be at most `RATIO_UP_TOL` (1e-4), as in `tail_breach`.
  - A raw close moving more than 25% in one session fails, as an unadjusted split would.
  - Any failure refuses (exit 3). The 2026-11-15 data check says both pass.
  - The parent's base-rate check against `spy_base_rate_daily.csv` has no QQQ or SMH file, so it is
    dropped. GC is the only cross-feed check.
- **GO, OHLC order.** `tail_breach_intraday`'s check, from each ETF's first session. Any failure
  refuses (exit 3).
- **GC, cross-feed.** `tail_breach_intraday`'s check of the raw low against the Barchart cache, per
  ETF. Any disagreement over 0.5% refuses (exit 3). A missing cache file skips it, and the report
  says so.
- **GX, no lookahead.** The tests recompute event A under each volatility source, and event B, on a
  series cut at session s and on one whose later sessions are all changed. The trigger at s must not change.
- **GN, clusters.** At least 10 clusters for the arm in the sample, and the largest cluster holds
  at most a third of the arm's entries. Otherwise the arm prints `UNDERPOWERED`.
- **Era.** Any era but `current` refuses (exit 2).

| Population | Floor |
|---|---|
| Sample | 10 clusters per arm, largest cluster at most a third of entries (GN) |
| Forward | The same, per arm |

## Bar for a candidate

No result here makes a candidate rule.

- A `REBOUND` or `CONTINUATION` co-primary files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md). It waits on its forward read and on
  an option study that prices the trade.
- A `REBOUND` whose VXN-scaled CI spans 0 files as "risk premium, not timing".
- A `REBOUND` files "to be tested" only with its `VS-SPY` line beside it, and the entry names the
  SPY null.

## Verdicts, worded now

**The four co-primaries:**

| Token | When |
|---|---|
| `REBOUND` | GN met, the excess CI lower bound above 0, and the Holm-adjusted p (m = 4) below 0.05 |
| `CONTINUATION` | GN met, the excess CI upper bound below 0, and the Holm-adjusted p (m = 4) below 0.05 |
| `NO-EDGE` | GN met, and neither of the above |
| `UNDERPOWERED` | GN unmet, or the CI is not finite; census printed, nothing concluded |

- `NO-EDGE` prints its CI. It reads as "no excess outside the interval", not as "no rebound".

**The eight secondaries.** The same tokens, with the Holm p of their own family (m = 8).

**FORWARD.** The four co-primaries on forward entries, each against its own forward eligible
sessions, with the same tokens and no Holm step. `STILL-OPEN` takes the place of `UNDERPOWERED`
until the arm meets the forward floor.

**The banner.** The report's section titled VERDICT prints:

```
>>> tail_rebound_etf QQQ-A21 (QQQ 21-session total return after an intraday 2x-VXN breach, first of each episode, vs unconditional, 2001 on): REBOUND | CONTINUATION | NO-EDGE | UNDERPOWERED <<<
>>> tail_rebound_etf QQQ-B21 (QQQ 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 1999 on): <word> <<<
>>> tail_rebound_etf SMH-A21 (SMH 21-session total return after an intraday 2x-VXN breach, first of each episode, vs unconditional, 2001 on): <word> <<<
>>> tail_rebound_etf SMH-B21 (SMH 21-session total return after a completed 5% fall, first of each episode, vs unconditional, 2000 on): <word> <<<
>>> tail_rebound_etf SECONDARY (h = 5 and 63, Holm m=8): QQQ-A5 <w> ... SMH-B63 <w> <<<
>>> tail_rebound_etf FORWARD (entries after the registration date): QQQ-A21 <w> QQQ-B21 <w> SMH-A21 <w> SMH-B21 <w> <<<
```

## Anti-tuning

- Fixed here:
  - both trigger rules, VXN as the primary volatility for both ETFs, k = 2 and the 5% move;
  - the 5-session episode chain and the first-of-episode entry at the close;
  - the price basis and the full SMH history as primary;
  - the horizons 5, 21 and 63, the statistic, the cluster rule and the seed;
  - the floor, the concentration rule, the Holm families and the verdict words.
- Every printed-only line falls as it falls. Only the VXN-scaled CI is used, and only to file a
  `REBOUND` as risk premium; none re-grades a verdict.
- No other ticker, trigger, horizon, entry rule or reference is graded.
- This registration is immutable in substance once accepted. Editorial consolidation only.

## What could ship

Nothing ships from this study.

- A `REBOUND` or `CONTINUATION` co-primary files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md).
- No verdict here changes a tier, a veto, a size class, an exit, the deploy card or the hedge
  sleeve's timing rule in [§4](../../../../docs/deployment-rules.md#s4).
