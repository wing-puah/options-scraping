## spy_dip_forward — do SPY entries on dip dates do better over the next month, 1993 on?

<!-- outcome:start -->
> Latest outcome: not yet run — registered 2026-11-27
<!-- outcome:end -->

_Registered 2026-11-27._

**STATUS: REGISTERED 2026-11-27, accepted by default; NOT YET RUN.** The operator fixed the design
commitments. Every detail they did not fix is the drafter's conservative conventional choice,
tagged `Resolved at draft (2026-11-27)` beside its rule. No SPY forward return, conditional on a dip
or not, was computed or looked at before this file was written. A fresh second reader checked it
on 2026-11-27, before its first outcome. Its changes are tagged `Resolved at second read
(2026-11-27)`.

## The question

The deploy card sizes Tier A heavier on a [dip date](../../../glossary.md#dip-date), staged in over
several dip sessions ([§ Sizing](../../../../docs/deployment-rules.md#s2-sizing), operator ruling
2026-11-26). Its only evidence is the v4 option book, one bull tape. After the 2026-11-27 re-price
that cell read adjusted p 0.054, `NULL`
([`current.md`](../../../current.md#the-dip-date-cell)).

This study asks the share-level question behind the rule, on SPY since 1993:

- **Graded question.** Is SPY's mean forward excess return after an entry on a dip date higher than
  after an entry on a non-dip date, over the same horizon?
- **Primary horizon.** 21 sessions. The 2026 book's median hold was 21 days
  ([`current.md`](../../../current.md#2026-10-22--the-2026-book-described-break-even-before-one-strangle-no-cut-proven-better)).
- **Risk.** Do dip entries suffer deeper worst-decile drawdowns inside the hold? A dip rule can buy
  falling knives.
- **Regime.** Among dip entries, do dips with SPY above its 200-day SMA do better than dips below
  it?

A yes can support the idea that dip-date entries do better. It cannot validate the option rule:
an option position's payoff, decay and stop are not SPY's.

## What this study is not

- **Not the `dip_buy` forward grade.** [`dip_buy`](../regime/dip_buy.md) grades Tier A/B option
  positions on forward dates. This study reads SPY shares only. No verdict here stands in for that
  grade or for the §2-sizing rollback it keys.
- **Not an option study.** It prices no option and reads no play, tier, R or backtest row.
- **Not `tail_rebound`.** [That study](../regime/tail_rebound.md) entered after rare tail falls.
  A dip date is a common state: SPY below its 50-day SMA.
- **Not a parameter search.** Twelve cells are fixed below and one is graded. The other eleven
  exist so PBO can measure how fragile the choice is.
- **Not a sizing study.** It compares mean returns per entry. It does not test staging, position
  size or a stop.
- **Not pooled across eras.** The inputs are market data with no prompt version.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price basis

- **Source.** SPY daily bars from yfinance, from SPY's first session (1993-01-29), fetched with
  `auto_adjust=False`. The cache holds date, close and `Adj Close` in
  `backtests/spy_dip_forward/SPY.csv`. It is fetched only with `--refresh`.
- **Signal basis: the unadjusted close.** Every dip signal reads `Close`, not `Adj Close`. This is
  the adopted rule's basis. `scripts/collector/daily/fetch_mech_regime.py:23-25` fixes unadjusted
  closes and says the dividend distortion of the SMA "is part of the frozen spec".
- **Return basis: the adjusted close.** `A_t` is SPY's `Adj Close` on session t. Returns include
  dividends, so an ex-dividend drop is not a loss.
- **The calendar.** The sessions in the cache, after dropping any session with no `Close` or no
  `Adj Close`. Every distance in sessions is counted on it.
- **Today's bar.** `Resolved at draft (2026-11-27)`: as in `calendar_drift`, a bar dated on the
  fetch day is kept only after 16:30 New York time.

### T-bill and excess return

- **Daily T-bill return** on session k is `y_{k−1} / 100 / 252`. `y` is the `^IRX` close, so the
  yield is known before the session it pays for.
- **Source.** `backtests/trend_overlay/IRX.csv`, read only. `--refresh` also writes
  `backtests/spy_dip_forward/IRX.csv`. The module reads that copy when it exists, and gate GI checks
  the two agree.
- **Carry.** A session with no `^IRX` close carries the last close forward.
- **Negative quotes are data.** `^IRX` quoted at or below zero (March 2020) is used as printed.
- **Discount basis.** `^IRX` is a discount yield, not a bond-equivalent one. The error is a few
  basis points a year and falls on both arms alike.
- **Forward excess return.** For an entry at the close of session e and horizon h:
  `X_h(e) = A_{e+h} / A_e − Π_{k=e+1..e+h} (1 + y_{k−1} / 100 / 252) − 0.0004`. The last term is
  the round-trip cost below, so `X_h` is net.

### Signal date and entry, one clock

- **Signal date D.** A session. Its flag reads closes at or before D only.
- **Entry session e = D+1.** The entry is at the close of the session after D. This is the book's
  one-clock fill: the card reads the flag after D's close, and the fill is the next closing mid.
- **The last session in the data** has no D+1, so it is no signal date yet.
- **Cost.** 2 bps per side on shares, `0.0004` per round trip. Dip and non-dip entries pay the same
  cost, so every difference below is the same gross or net. Printed levels are net.

### The adopted dip definition, primary

`SMA50`: SPY's unadjusted close on D is strictly below the mean of the 50 unadjusted closes ending
at D. A session with fewer than 50 closes up to D has no flag.

This is the definition the live rule uses, found at:

- `docs/deployment-rules.md:140-143`: "**Dip date:** SPY closed strictly below its 50-day SMA on the
  signal date (`spy_below_sma` ...)".
- `scripts/journal/s06_recommend.py:767-788` (`dip_status`): the card's flag is
  `MechLabeler.below_sma(session)`.
- `lib/mech_regime.py:39` (`SMA_WINDOW = 50`), `:72-76` (the SMA over the 50 rows ending at D) and
  `:113` (`"spy_below_sma": (r["spy"] < sma) if sma is not None else None`).

The `dip_buy` registration, the glossary's "dip date", the `regime_map` cut `RM-SMA` and
`mechanical_baseline`'s dip-gated weekly cell all read this same flag. The drafter found no second
definition in use. The 2026-10-12 card calls the cell "Tier A, falling market". That is a name for
the same below-SMA cell, not another rule.

- **Computed by the shipped code.** The module writes the cached `Close` column as `spy_close`, with
  `vix_close` blank, and calls `lib/mech_regime.py::compute_mech_table` unchanged. The flag is that
  function's `spy_below_sma`. Gate GS checks it against the shipped tables.
- **Entry clock.** The book's `next_open` entry fills at the close of the trading day after the
  signal ([architecture](../../../../docs/architecture.md), one-clock ruling 2026-10-23). The D+1
  close entry here matches it.
- **Not `mech_cell`.** The BEAR direction also needs a negative 20-day return. It is not used.

### The other dip definitions, grid only

| Label | Dip on D when | Role |
|---|---|---|
| `SMA50` | Close below its 50-session SMA, as above | Primary |
| `SMA20` | Close below its 20-session SMA | Grid only |
| `PB5` | Close at or below 0.95 × the highest close of the 20 sessions ending at D | Grid only |
| `DN3` | Three lower closes in a row: `C_D < C_{D−1} < C_{D−2} < C_{D−3}` | Grid only |

- Every variant reads unadjusted closes, strict inequalities as written, and closes at or before D.
- `Resolved at draft (2026-11-27)`: `PB5` and `DN3` are the usual shape of practitioner pullback
  rules. They are lore, not evidence, and are here only to give PBO real alternatives.
- **The module's own SMA helper** computes `SMA20` and `SMA200`. A test checks that the helper at
  N = 50 reproduces `compute_mech_table`'s flag on every session.

### The 200-day regime

- **Above-200.** SPY's unadjusted close on D is at or above the mean of the 200 unadjusted closes
  ending at D. **Below-200** is the rest. A session with fewer than 200 closes has no regime.
- `Resolved at draft (2026-11-27)`: 200 sessions, about Faber's 10 months. The tie goes to above,
  so below-200 is strict, as `SMA50` is.

### Horizons and outcomes

- **Horizons.** h = 5, 21 and 63 sessions. 21 is primary.
- **Forward drawdown.** `MAE_h(e) = min over k = e+1..e+h of (A_k / A_e − 1)`. It can be positive
  when SPY never closes below the entry.
- **Vol-scaled return.** `X_h(e) / (σ_D × √h)`, where `σ_D` is the sample standard deviation of the
  21 daily log adjusted returns ending at D. Printed only.

### Entries, the difference and dip episodes

- **Every session is an entry.** Each session D with a defined flag gives one entry at D+1, in the
  dip set or the non-dip set.
- **The statistic.** `Δ_h = mean X_h over dip entries − mean X_h over non-dip entries`, same window,
  same h.
- **Dip episode.** Formed on the whole series. An episode starts on a dip session when none of the
  5 sessions before it was a dip session. It ends when more than 5 sessions in a row are non-dip.
- **Why episodes.** Dip sessions arrive in runs. The episode count, not the session count, is
  closest to the number of independent dips. It sets the power floor.
- **Episodes read later sessions.** An episode's end is known only after it. So episodes feed the
  power floor and the `ORDINAL` print only. No flag, entry or return reads them.

## Dependencies

- yfinance, with `--refresh` only, for SPY and `^IRX`. Without the cache the run refuses (exit 3)
  and says to pass `--refresh`. Forward runs pass `--refresh` first.
- `backtests/trend_overlay/IRX.csv`, read only.
- `lib/mech_regime.py::compute_mech_table`, imported unchanged, for `SMA50`.
- `backtests/mech_regime/spy_vix_daily_full.csv` and `spy_base_rate_daily.csv`, read only by gates
  GS and GM.
- `scripts/backtest_study/f1_selection/regime/tail_breach.py` (`ratio_problems`,
  `base_rate_problems`, `block_indices`), imported unchanged.
- `scripts/backtest_study/f1_selection/benchmark/ticker_class.py::holm`, imported unchanged.
- `scripts/backtest_study/lib/pbo.py::cscv`, with a metric defined in the module.
- `scripts/backtest_study/lib/era.py`, for the era check.
- No Barchart call, no Sheets export, no option price and no backtest row.

## Population and basis, fixed here

- **Era.** Only the default era `current` runs. Any other `STUDY_ERA` refuses (exit 2).
- **Seal.** The [holdout seal](../../f4_deployment/holdout_seal.md) binds emitted plays' signal
  dates. This study reads no play, so the seal does not apply.
- **The registration date** enters the code as the constant `REGISTERED`, 2026-11-27.

| Window | Signal dates D | Role |
|---|---|---|
| `DISCOVERY` | First flagged session (about 1993-04) to 2009-12-31 | Sign check |
| `HOLDOUT` | 2010-01-01 to 2025-12-31 | Decides the verdict |
| `PRE-BOOK` | 2010-01-01 to 2023-12-31, a part of `HOLDOUT` | Sign check for `P` only |
| `2026` | 2026-01-01 to `REGISTERED` | Contaminated; printed, never graded |
| `FORWARD` | After `REGISTERED` | One forward verdict |

- **A whole window per entry.** An entry counts in a window only when D, the entry session and the
  last session of its h-window all fall inside that window. Others are gap entries, counted and
  printed per window and h.
- **Open entries.** An entry whose h-window runs past the data is open. It waits for a later run.
- `Resolved at draft (2026-11-27)`: **why 2010.** Each window then holds at least two deep
  sell-offs. Discovery holds the dot-com bear and the 2008 crisis. The holdout holds the 2020 crash,
  the 2022 bear and several smaller falls. The split was set from public market history, not from
  any figure computed here.
- **Why 2026 is not graded.** The dip idea was chosen after seeing the v4 book. 2026 holds the
  cell's latest dates and the live journal. Those dates print apart, labelled
  `2026 (contaminated, not graded)`.
- `Resolved at second read (2026-11-27)`: **the holdout overlaps the book.** The v4 export's
  signal dates start on 2024-01-10, and v3's on 2024-06-17. The second reader read only that date
  column. The dip idea came from Tier A option results on those dates, which include the April 2025
  fall. So 2024 and 2025 are not unseen. They stay in `HOLDOUT`, as the operator fixed. `P` also
  needs a positive point estimate on `PRE-BOOK`, the holdout without them.
- **The other holdout years** were never read as dip-conditional SPY returns. The drafter knows
  their public market history, disclosed below.
- **Report header.** `era: current (inputs are unversioned market data)`, the SPY session range,
  the git sha, the dirty flag, every input file with its first and last date, and each window's
  first and last signal date.

## Plan-time observations, disclosed

### Why this question exists

The dip idea came from the option book, after its results were seen. Every figure in this section
was seen before the file was written, and none of it can grade the question.

| Source | What the drafter saw |
|---|---|
| `dip_buy` registration | v4 Tier A+B below minus above +0.096 [−0.164, +0.322]; v3 +0.199 [−0.050, +0.428] |
| Deploy card §2-sizing | Tier A, falling market: v4 +0.332 [+0.133, +0.522]; v3 gross +0.383 [+0.194, +0.582] |
| `current.md`, 2026-11-27 | A × below-SMA in-sample +0.270 [+0.054, +0.498], adjusted p 0.054, `NULL` |
| `current.md`, `dip_buy` forward | Below arm 14 of 30 dates, above arm 19 of 30; `STILL-OPEN` |

These are option R figures on signal dates from 2024-01-10 on. They set no number in this file.

### Related SPY results already seen

The drafter read the latest-outcome lines in the pre-registration index while drafting. Three bear
on this question.

- **`tail_rebound`.** On SPY since 1993, entries after tail falls printed `NO-EDGE` at every
  horizon it graded. Tail falls are rare and most fall on dip dates, so this is a weak prior for `NULL`.
- **`trend_overlay`.** A slow trend switch on the index printed `NO-DRAWDOWN-BENEFIT`. It bears on
  the 200-day split only.
- **`regime_confirm`.** Mechanical BEAR flips printed `RETRO-NULL` as sell-off warnings. The BEAR
  label shares the below-SMA half with `SMA50`.

None of these computed a mean forward return split by `SMA50`. No number from them is used here.

### Data read for this file

- The first row of `backtests/mech_regime/spy_base_rate_daily.csv` (1993-01-29, close 43.9375) and
  its last date (2026-09-24), to confirm the unadjusted basis and its span.
- The first row of `spy_vix_daily_full.csv` (2023-06-01) and its row count.
- The first two rows and the last date (2026-11-20) of `backtests/trend_overlay/IRX.csv`.
- `backtests/spy_dip_forward/` does not exist yet. No SMA, flag or return was computed.

### Public market history the drafter knows

- **Continuation cases.** SPY kept falling for months below its 50-day SMA in 2000–2002, 2008 and
  2022. Those are the falling knives the risk test is for.
- **Rebound cases.** 2020, late 2018 and April 2025 recovered within weeks.
- **2024 and 2025.** The option book's dates cover the April 2025 fall. That is direct exposure to
  holdout episodes, though no dip-conditional SPY figure was computed on them. `PRE-BOOK` exists
  for this reason.

### Literature and prior

The published evidence points both ways, and most of it is on individual stocks.

- **Short-horizon reversal, individual stocks.** Lehmann (1990, Quarterly Journal of Economics) found
  weekly reversals, and Jegadeesh (1990, Journal of Finance) monthly ones. Both are cross-sections of
  stocks. Neither shows that an index reverses after a fall.
- **Index autocorrelation.** Lo and MacKinlay (1988, Review of Financial Studies) found weekly
  index returns positively autocorrelated in their sample. That points away from a dip edge.
- **Time-series momentum.** Moskowitz, Ooi and Pedersen (2012, Journal of Financial Economics) found
  that an asset's own 1-to-12-month return predicts the next month with the same sign. A dip is a
  recent loss, so this predicts dips do worse.
- **Moving-average rules.** Brock, Lakonishok and LeBaron (1992, Journal of Finance) found Dow returns
  lower and more volatile when price was below its moving average. Sullivan, Timmermann and White
  (1999, Journal of Finance) found those rules weakened after their sample. This also predicts dips
  do worse, and more volatile.
- **The 200-day regime.** Faber (2007, Journal of Wealth Management) held assets only above their
  10-month SMA and cut drawdown. That suggests a dip above the long average is safer than one below.
- **Practitioner pullback rules.** Connors-style "buy the pullback" rules are practitioner lore,
  not peer-reviewed evidence.

**The drafter's prior.** `NULL` on the mean, more likely than not. The drawdown test should show
deeper drawdowns after dips, because volatility is higher below the SMA. The 200-day split leans
toward above-200 dips doing better.

### Power, from a prior

- **Assumption.** SPY's 21-session return has a standard deviation near 4.5%. That is about 16%
  annual volatility, a general market fact, not a figure computed here.
- **Episodes.** The drafter expects roughly 3 to 6 `SMA50` dip episodes a year. That gives about 50
  to 100 in the holdout. It is an expectation from public charts, not a count.
- **What that detects.** With about 60 effective dip observations, the standard error of `Δ_21` is
  near 0.7 points. After Holm across three tests, a `Δ_21` below about 1.7 points is unlikely to
  be detected. SPY's mean 21-session return is itself under 1 point.
- **So a `NULL` is the likely outcome even if a small edge exists.** It will print its CI, which
  bounds the edge's size.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| `P` | arm | `Δ_21` for `SMA50`, every-session entries | Primary; Holm m = 3 with `T` and `Z` |
| `T` | arm | Worst-decile `MAE_21`, dip minus non-dip, `SMA50` | Graded risk test; Holm m = 3 |
| `Z` | arm | Mean `X_21` of above-200 dips minus below-200 dips, `SMA50` | Graded regime test; Holm m = 3 |
| Non-dip entries | control | Every flagged non-dip session in the same window | The reference for `P` and `T` |
| Grid | cell | 4 definitions × 3 horizons, `SMA50-21` among them | PBO only; deltas printed, not graded |
| `2026` | population scope | All three arms on 2026 entries | Printed, contaminated, never graded |
| `FORWARD` | population scope | All three arms on entries after `REGISTERED` | Forward verdicts |

### `P`, the mean difference

`Δ_21` on `SMA50` entries against non-dip entries. It asks whether buying SPY the session after a
dip date beat buying it the session after any other date, over the next 21 sessions.

### `T`, the drawdown tail

`T = q10(MAE_21 | dip entries) − q10(MAE_21 | non-dip entries)`. `q10` is the 10th percentile, by
numpy's default linear rule. A negative `T` means the worst tenth of dip entries fell further inside
the hold.

- `Resolved at draft (2026-11-27)`: the path drawdown, not the final return's tail, is graded. The
  operator manages to a $1,000 stop, so a fall inside the hold matters even when SPY recovers.

### `Z`, the 200-day split

`Z = mean X_21 over dip entries above-200 − mean X_21 over dip entries below-200`. Only `SMA50` dip
entries with a 200-day regime enter it. The operator's design left this descriptive unless
pre-committed. It is pre-committed here because the 200-day literature makes a directional
prediction, and a split rule is the obvious next change to the card.

### Why three tests with Holm

The operator asked three questions of one rule: does it pay, does it hurt, and does the regime
matter. Three uncorrected tests give three chances at a false yes, so they form one Holm family.

### The grid, for PBO

| Factor | Values |
|---|---|
| Definition | `SMA50`, `SMA20`, `PB5`, `DN3` |
| Horizon h | 5, 21, 63 |

Cell labels read definition-horizon: `SMA50-21` is `P`'s cell. Only `SMA50-21` is graded.

### Printed only, never graded

| Label | What it prints |
|---|---|
| `LEVELS` | Mean net `X_h` for dip, non-dip and all entries, per window and h |
| `HIT` | Share of entries with `X_21 > 0`, dip against non-dip |
| `TAIL-RET` | `q10` of `X_21`, dip minus non-dip |
| `MAE-MEAN` | Mean `MAE_21`, dip minus non-dip |
| `VOL-SCALED` | `P` on vol-scaled returns |
| `WEEKLY` | `P` with D the first session of each ISO week only, as `mechanical_baseline`'s dip-gated weekly cell |
| `SPACED` | `P` with D every 21st flagged session from the window's first, so no two windows overlap |
| `ORDINAL` | Mean `X_21` by dip session within its episode: 1st, 2nd to 5th, 6th on |
| `REGIME-2X2` | Mean `X_21` and count in each cell of dip or non-dip by above-200 or below-200 |
| `NW` | OLS of `X_21` on a dip dummy, Newey–West t with 42 lags |
| `BLOCKS` | `P`, `T` and `Z` with bootstrap blocks of half and twice the registered length |
| `YEARS` | `Δ_21` per calendar year of D, and the count of years above 0 |
| `GRID` | Every cell's `Δ_h` and `Δ_h / h`, with CI and unadjusted p, per window; no token |

- Every printed line with an interval uses the same bootstrap rule. None carries a verdict.
- **`ORDINAL` speaks to staging.** The live rule spreads size over several dip sessions because the
  dip can keep dipping. This cut shows whether later dip sessions did better than the first. It
  grades nothing.
- **`SPACED` and `WEEKLY` speak to overlap.** They thin the entries so fewer outcome windows share
  sessions. `SPACED` uses blocks of 3 entries; `WEEKLY` uses blocks of 13 weeks.

## How it is judged

### Bootstrap

- **Moving-block bootstrap on the entry sequence.** A window's entries, in date order, are one
  series. Each row carries the entry's dip flag, 200-day regime, `X_h` and `MAE_h`. Draws use
  `tail_breach.block_indices` (blocks of L consecutive rows, starts uniform).
- `Resolved at second read (2026-11-27)`: **what is resampled.** Blocks of whole rows of that one
  series, dip and non-dip together. Dip and non-dip entries are never resampled apart. A drawn
  block keeps each session's flag beside its own returns, so a dip run and its overlapping windows
  travel together. The dip and non-dip counts vary from draw to draw.
- **Why that is valid.** Each arm is a smooth function of row means, such as the mean of `X·F`
  over the mean of `F`, with `F` the dip flag. The moving-block bootstrap covers such statistics on
  a dependent series.
- **Its limit.** A dip run longer than L rows is split across blocks, which can narrow the CI.
  Holdout runs in 2020 and 2022 may be that long. `BLOCKS` prints the CI at 2L to show how much.
- **Block length.** `L = max(63, 2h)` rows. That is 63 rows for the two shorter horizons and 126
  for the longest.
- **Why this length.** Entries fewer than h sessions apart share returns. Dip states last weeks, and
  volatility clusters for months. A block of at least 2h, and never under a quarter, keeps most
  overlapping pairs and most dip runs inside one block.
- `Resolved at draft (2026-11-27)`: every-session entries with a block bootstrap are primary, not
  thinned entries. They use every dip date, as the card does. `SPACED` and `WEEKLY` print beside
  them.
- **Draws.** 10,000, seed 20261127, for every window and arm.
- **Per draw.** Recompute `P`, `T` and `Z` on the drawn rows. A draw with no row in a needed group
  gives NaN.
- **CI.** The 2.5th and 97.5th percentiles of the finite draws. If more than 1% of draws are NaN,
  the CI is not finite.
- **p-value.** Two-sided, from the same draws: twice the smaller of the share at or below 0 and the
  share at or above 0, capped at 1. This is `tail_breach`'s convention.
- **Holm.** `P`, `T` and `Z` on `HOLDOUT` form one family, m = 3, through `ticker_class.holm`. An
  `UNDERPOWERED` arm stays in the family with p = 1. The report prints each unadjusted p beside
  its Holm-adjusted p.
- **The CI and Holm clauses agree.** A Holm-adjusted p below 0.05 implies the unadjusted p is too.
  The 95% CI is then clear of zero. The verdict rows state both.

### When `P` counts as support

All four hold:

- the `HOLDOUT` CI lower bound is above 0, and its Holm-adjusted p is below 0.05;
- the `DISCOVERY` point estimate of `Δ_21` is above 0;
- the `PRE-BOOK` point estimate of `Δ_21` is above 0, and finite;
- the PBO is at most 0.50.

An interval that touches zero does not count. The `DISCOVERY` and `PRE-BOOK` CIs print but do not
gate. These two windows are sign checks only, for `P` only.

### PBO / CSCV

- **Rows.** Signal sessions D from the first session on which all four definitions have a flag, to
  the last D whose 63-session window ends on or before 2025-12-31. 2026 is never in it.
- `Resolved at second read (2026-11-27)`: **matrix.** A T × 12 × 2 array, passed to `pbo.cscv`
  as its T × N × K form. Row t is signal session D. Channel 0 is the cell's net `X_h` for the
  entry at D+1. Channel 1 is the cell's dip flag on D, 1 or 0. Every value is finite, because every
  row's 63-session window closes inside the data. `cscv` refuses a non-finite value.
- **Metric.** A function in the module. Per cell, on the rows `cscv` gives it: the mean return
  over the cell's dip rows, minus the mean over its non-dip rows, divided by h. That is `Δ_h / h`,
  the difference per session held. A subset with no dip row or no non-dip row gives NaN.
  `cscv` ranks a NaN worst.
- `Resolved at draft (2026-11-27)`: dividing by h puts the three horizons on one scale. Without it
  the 63-session cells would rank first by construction.
- **S = 16.** The oldest rows are dropped until 16 divides the row count, and the count is printed.
  Each of the 16 blocks holds about two years, far longer than any h.
- **The bar.** Above 0.50 is a veto. Above 0.25 and at most 0.50 prints "selection fragile". A PBO
  that cannot be computed counts as above 0.50.
- **What it measures.** `SMA50-21` was fixed before any run, not picked as the best cell. PBO asks
  whether the grid's best cell keeps its rank in unseen blocks. A high value says the ranks are
  noise, so a gain in the fixed cell is fragile.
- **Its limits.** The rows span the holdout, so PBO is not an out-of-sample test. The last rows of
  a block carry returns from the next block, up to 63 of about 520. That leak makes the two halves
  alike, so PBO may read slightly low. Twelve close variants of one idea sit near 0.50 under pure
  noise, so the veto is near a coin flip when there is no edge.

## Gates

### Refusals, before any statistic

Each prints `REFUSED (<gate>: <reason>)` and exits 3, except the era check.

- **GE, inputs.** `backtests/spy_dip_forward/SPY.csv` exists, is not empty and starts on or before
  1993-02-01. It holds at least 64 sessions after 2025-12-31. Every 2025 entry then has its full
  63-session window in the data, so the holdout and PBO rows are fixed and none is left open.
- **GB, basis.** `tail_breach.ratio_problems`, imported unchanged: the `Close / Adj Close` ratio
  never steps like a split. The module's own check: no daily adjusted return exceeds ±25%.
- **GM, missing sessions.** No run of more than one missing weekday, except 2001-09-11 to 2001-09-14,
  2007-01-01 to 2007-01-02 and 2012-10-29 to 2012-10-30. Every session in
  `spy_base_rate_daily.csv` is in the cache over their common span.
  `tail_breach.base_rate_problems`, imported unchanged and passed an empty VIX map, finds no
  unadjusted close more than 0.5% from that table's.
- `Resolved at draft (2026-11-27)`: single missing weekdays are holidays and national days of
  mourning. The listed runs are the closures after 9/11 and for Hurricane Sandy.
  `Resolved at second read (2026-11-27)`: 2007-01-02, the day of mourning for President Ford, fell
  the day after New Year's Day. That run is listed too, or GM would refuse a true calendar.
- **GS, signal parity.** The `SMA50` flag from the cache equals the flag `compute_mech_table`
  gives on `spy_vix_daily_full.csv` and on `spy_base_rate_daily.csv`, on every common date where both
  are defined. A mismatch where `|close / SMA − 1|` is at least 0.0005 refuses. Mismatches inside
  that band are counted and printed, and the cache's flag is used.
- **GI, T-bill.** `^IRX` covers every session from the first entry to the last window end. No carry
  exceeds 5 sessions. When both `^IRX` copies exist, they agree within 0.01 points on every common
  date.
- **GX, no lookahead.** `Resolved at second read (2026-11-27)`: a run-time check, as
  `tail_breach.gx_check`. At 60 evenly spaced sessions D, the module recomputes every flag and the
  200-day regime on the series cut at D. Any value that differs from the full-series value refuses.
  `tests/test_spy_dip_forward.py` also changes every close after D on a synthetic series. It checks
  the same values, that each entry's first price is D+1's close, and that no signal reads a return.
- **Era.** Any era but `current` refuses (exit 2).

### Power, per window

- **GN.** At least 20 dip episodes, at least 250 dip entries and at least 250 non-dip entries. The
  largest episode holds at most a third of the window's dip entries. `P` needs GN in both
  `DISCOVERY` and `HOLDOUT`, because its sign check reads discovery. `T` needs it in `HOLDOUT`.
- **GN for `Z`.** In `HOLDOUT`, at least 10 episodes holding an above-200 dip entry and 10 holding a
  below-200 one. `Resolved at second read (2026-11-27)`: each side also needs at least 100 dip
  entries, so neither mean rests on a few weeks.
- **An episode counts in a window** when the window holds at least one of its dip entries.

**Why 20 episodes.** It is twice the cluster floor of `tail_rebound` and `tail_breach`. Dip episodes
are less extreme than tail falls, so their outcomes are more alike, and more are needed to separate
an edge from noise. It is set from the calendar, not from any return.

**Why a third.** When one long dip holds most entries, a draw's mean turns on whether that dip is
drawn.

| Population | Floor |
|---|---|
| `DISCOVERY`, `HOLDOUT` | GN, per arm |
| `FORWARD` | GN, per arm, on forward entries |
| `2026` | None; printed only |

## Bar for a candidate

No result here makes a candidate rule.

- A `SUPPORTED` files "dip-date entries: SPY shares support it, option rule untested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md). It waits on its forward read and on
  `dip_buy`.
- A `SUPPORTED` whose `VOL-SCALED` CI spans 0 files as "risk premium, not timing". The higher mean
  is then no more than the higher volatility pays.
- A `Z` of `ABOVE-200-BETTER` files a possible card split for a later registration on option data.

## Verdicts, worded now

### `P`, on `HOLDOUT`

The first matching row wins.

| Token | When |
|---|---|
| `REFUSED (<gate>)` | GE, GB, GM, GS, GI or GX fails; nothing past it is computed |
| `UNDERPOWERED` | GN unmet in `DISCOVERY` or `HOLDOUT`, or the `HOLDOUT` CI is not finite |
| `CONTRARY` | `HOLDOUT` CI upper bound below 0, and Holm-adjusted p (m = 3) below 0.05 |
| `PBO-VETO` | The support clauses hold except PBO, which is above 0.50 |
| `SUPPORTED` | All four support clauses hold |
| `NULL` | Every other case |

- **Each case has exactly one token.** A CI cannot sit both above and below zero, so `CONTRARY` and
  the support rows never both apply. Their order does not change any token.
- **A holdout gain whose discovery or pre-book sign disagrees** is `NULL`. The report adds
  "holdout gain, discovery sign disagrees" or "holdout gain, pre-book sign disagrees".
- **`CONTRARY` reads the holdout only.** A significant loss is reported whatever discovery shows.
  PBO does not veto it: PBO guards a gain from a picked cell, and `SMA50-21` was not picked. The
  PBO still prints beside it.
- **`NULL` prints its CI.** It reads as "no difference outside the interval", not "no effect".

### `T`, on `HOLDOUT`

The first matching row wins.

| Token | When |
|---|---|
| `REFUSED (<gate>)` | As for `P` |
| `UNDERPOWERED` | GN unmet in `HOLDOUT`, or the CI is not finite |
| `DEEPER-DRAWDOWN` | CI upper bound below 0, and Holm-adjusted p below 0.05 |
| `SHALLOWER-DRAWDOWN` | CI lower bound above 0, and Holm-adjusted p below 0.05 |
| `NULL` | Every other case |

### `Z`, on `HOLDOUT`

The first matching row wins.

| Token | When |
|---|---|
| `REFUSED (<gate>)` | As for `P` |
| `UNDERPOWERED` | GN for `Z` unmet, or the CI is not finite |
| `ABOVE-200-BETTER` | CI lower bound above 0, and Holm-adjusted p below 0.05 |
| `BELOW-200-BETTER` | CI upper bound below 0, and Holm-adjusted p below 0.05 |
| `NULL` | Every other case |

### Grid, `DISCOVERY`, `PRE-BOOK` and `2026`

- **Grid cells** print as `GRID` above, with no token. `Resolved at second read (2026-11-27)`: the
  draft gave them `P`'s tokens, but `P`'s rows need clauses a cell does not have.
- **`DISCOVERY`** and **`PRE-BOOK`** print each arm's estimate and CI, with no token.
- **`2026`** prints each arm's estimate, CI and counts under `2026 (contaminated, not graded)`.

### `FORWARD`

- **The same tables** on forward entries, against forward non-dip entries, with Holm m = 3 over `P`,
  `T` and `Z`.
- **No PBO, no discovery clause and no pre-book clause.** `P`'s tokens are `SUPPORTED`,
  `CONTRARY`, `NULL`, `STILL-OPEN` and `REFUSED`. Its support needs the CI and Holm clauses only.
- **`STILL-OPEN`** takes the place of `UNDERPOWERED` until the arm meets its GN on forward
  entries. A `STILL-OPEN` arm enters the Holm family with p = 1.
- **The wait.** At the expected episode rate the floor is about four to seven years away. Each run
  before then prints the census.
- **Verdict of record, per arm.** The first forward run in which that arm prints a token other than
  `STILL-OPEN`. Later runs are descriptive for that arm.

### What each `P` verdict would mean for the live rule

| `P` verdict | It would mean | It would not mean |
|---|---|---|
| `SUPPORTED` | SPY shares bought after a dip date beat other entries over a month on the holdout, with the same sign before the book's years | That a Tier A call spread does better on dip dates, or that heavier size is safe |
| `CONTRARY` | Entries after dip dates did worse over a month, which fits momentum better than reversal | That the option rule failed; it changes no size class by itself |
| `NULL` | No share-level difference outside the interval | That the rule is wrong; the share test is too weak to rule out a small edge |
| `PBO-VETO` | A gain showed, but the grid ranks look like noise | Support of any kind |
| `UNDERPOWERED` | Too few dip episodes to judge | Anything about the rule |
| `REFUSED` | The data failed a gate | Anything about the rule |

- **`T` as `DEEPER-DRAWDOWN`** with `P` as `SUPPORTED` means dips paid more and hurt more. That is
  what staging is for. It is a reason to keep staging, not a reason to size up.
- **`Z` as `ABOVE-200-BETTER`** means dips in an uptrend beat dips in a downtrend on shares. A card
  rule that sizes up only above the 200-day SMA would still need its own option-book registration.

**The banner.** The report's section titled VERDICT prints:

```
>>> spy_dip_forward P (SPY 21-session excess return, entry the close after a close below the 50-day SMA, vs other entries, holdout 2010-2025, Holm m=3): SUPPORTED | PBO-VETO | CONTRARY | NULL | UNDERPOWERED | REFUSED (<gate>) <<<
>>> spy_dip_forward T (worst-decile 21-session drawdown, dip minus non-dip, holdout, Holm m=3): DEEPER-DRAWDOWN | SHALLOWER-DRAWDOWN | NULL | UNDERPOWERED <<<
>>> spy_dip_forward Z (dips above minus below the 200-day SMA, 21 sessions, holdout, Holm m=3): ABOVE-200-BETTER | BELOW-200-BETTER | NULL | UNDERPOWERED <<<
>>> spy_dip_forward DISCOVERY (to 2009-12-31): P <x> [<lo>, <hi>] T <x> [<lo>, <hi>] Z <x> [<lo>, <hi>] <<<
>>> spy_dip_forward PRE-BOOK (2010-2023): P <x> [<lo>, <hi>] <<<
>>> spy_dip_forward PBO (12 cells, S=16, 1993-2025): <value> <<<
>>> spy_dip_forward 2026 (contaminated, not graded): P <x> [<lo>, <hi>], <n> dip entries <<<
>>> spy_dip_forward FORWARD (entries after the registration date): P <w> T <w> Z <w> <<<
```

Each `<w>` is that arm's forward token, `STILL-OPEN` until its floor is met.

## Anti-tuning

- **Fixed here, the signal.** `SMA50` as the shipped code computes it, the unadjusted-close basis,
  the strict inequality, the D+1 close entry and the 200-day regime with its tie rule.
- **Fixed here, the outcome.** The three horizons and the primary one, the excess-return formula,
  `MAE_h`, the 10th percentile and the cost.
- **Fixed here, the judging.** The windows and their dates, `PRE-BOOK` among them, the whole-row
  resampling, the gap-entry rule, the episode rule,
  the floors, `L = max(63, 2h)`, the 10,000 draws and the seed, the Holm family, the PBO grid, metric,
  S and bar, and the verdict words.
- No other dip definition, horizon, moving average, threshold, window or reference is graded.
- A grid cell, a printed-only line or the `2026` window never re-grades an arm.
- PBO never selects a cell.
- This registration is immutable in substance. Editorial consolidation only.

## What could ship

Nothing ships from this study, and no live rule changes because of it.

- Any change to the deploy card, including §2-sizing's staging or its size classes, is the
  operator's call alone, in a new registration on option data.
- The §2-sizing rollback stays keyed to the `dip_buy` forward verdict. No verdict here triggers or
  blocks it.
- `SUPPORTED`, `CONTRARY` and any graded `T` or `Z` token file their line in
  [`deployment-evidence.md`](../../../deployment-evidence.md).
- No verdict here changes a tier, a veto, an exit, `ladder_tier()` or the hedge sleeve in
  [§4](../../../../docs/deployment-rules.md#s4).
