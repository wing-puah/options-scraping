## dip_buy — do Tier A/B positions do better when SPY closes below its 50-day SMA?

_Registered 2026-10-12._

**STATUS: ACCEPTED BY DEFAULT 2026-10-12 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Contested choices are parameters printed both
ways; none of them is graded.

**What this file says, in one paragraph.** The 2026-10-12 exploratory read
found one rule that ranked high in both eras: Tier A/B positions taken on a
[dip date](../../../glossary.md#dip-date). It was picked after the fact from 28
candidates, so the in-sample book cannot confirm it. This file grades it on
one population only: signal dates on or after the holdout seal's start, read
from `lib/era.py`, once the seal lifts. Everything in-sample is printed as
context and labelled post hoc.

## Question

Among non-vetoed Tier A/B positions, is the realized
[meanR](../../../glossary.md#meanr) higher on dip dates than on above dates?

The exploratory read behind it is the 2026-10-12 entry in
[`current.md`](../../../current.md). Its three findings, in short:

- The v4 book was mostly a bull tape. SPY closed above its 50-day SMA on about
  four in five v4 signal dates and about one in three v3 dates.
- Tier A/B outcome tracks the underlying's own move over the hold (R² 0.47 on
  v4). At zero move the v4 intercept is about zero.
- Of 28 single-feature rules in a PBO read
  ([`pbo_ledger`](../../../arm-index.md#pbo_ledger)), the dip rule was the one
  that ranked high in both eras. PBO was 0.48 on v4 and 0.33 on v3.

## What this is NOT

- **Not an in-sample test.** The rule was chosen by looking at these dates.
  No in-sample figure carries a verdict, whatever it prints.
- **Not a new tier rule.** The ladder ([§1–§3](../../../../docs/deployment-rules.md#s1))
  is read from `scripts/journal/lib/mapping.py::ladder_tier` and never
  re-implemented. Nothing here changes which plays are tiered A or B.
- **Not an exit study.** Exits are the shipped ones, as stored on each row.
- **Not a ship.** A forward `SUPPORTED` lets the operator consider a
  deployment-rules change. It changes nothing by itself.
- **Not a named sealed reader.** The [holdout seal](../../f4_deployment/holdout_seal.md)
  closed its reader list on 2026-10-09. This study waits for the unseal like
  any other forward read accepted after that date.

## Definitions

### Dip date

A signal date on which SPY's close, as of the last trading day on or before
it, is strictly below its 50-day simple moving average.

- **Source.** `lib/mech_regime.py::MechLabeler.below_sma`, reading
  `backtests/mech_regime/spy_vix_daily_full.csv`. That is the table and the
  SMA behind the shipped `mech_cell`.
- **Why not `mech_cell` itself.** `mech_cell` does not encode this flag. Its
  BEAR direction needs SPY below the SMA and a negative 20-day return, and
  its cells mix in VIX. The flag was added to `compute_mech_table` on
  2026-10-12 as one more output of the same SMA. No threshold moved.
- **Unlabelled.** A date the table does not reach, or with no 50-day runway,
  is dropped and counted. A run whose table ends before the last forward date
  prints that count; refresh with `make mech-regime` before reading it.

### Tier

`mapping.ladder_tier(structure, market_regime, dte, short_leg_delta=delta)`.
VETO rows are dropped. Tier A/B rows form the graded population; the
bull_call_spread null below draws from every non-veto row.

## Population and basis, fixed here

- **Loader.** `load_book()` at its defaults: real and `strike_expiry_tweak`
  rows, bs excluded, proxy calibration on. Rows with no stored R, or with
  `fill_trusted` False, are dropped and counted.
- **Outcome.** The stored `realized_pnl_pct`
  ([R](../../../glossary.md#r)), net of the row's `cost_total`.
- **In-sample (context only).** Every signal date before `era.SEAL_START`,
  on v4 and on v3, each printed separately.
- **Forward (graded).** Every v4 signal date on or after `era.SEAL_START`.
  The date is read from `lib/era.py` at run time, never copied. Today it is
  2026-09-23.
- **When forward dates become readable.** Only after `era.SEAL_LIFTED` is
  set by the seal's own unseal read. Until then `load_book` withholds them,
  the forward arms are empty and the verdict is `STILL-OPEN`.
- **Era.** A prompt-version bump freezes the grade at the last v4 date. Dates
  from two prompt versions are never pooled.

## Plan-time observations, disclosed

Every figure below was seen before this file was written. They are why the
hypothesis exists, and they are why none of them can grade it. Source: the
first `dip_buy` run on the 2026-10-06 exports, which reproduces the
exploratory read.

| Era, Tier A+B | Dip arm | Above arm | Difference, CI95 |
|---|---|---|---|
| v4 | +0.192, 112 positions, 46 dates | +0.096, 630 positions, 197 dates | +0.096 [−0.164, +0.322] |
| v3 | +0.450, 161 positions, 53 dates | +0.252, 131 positions, 35 dates | +0.199 [−0.050, +0.428] |

| Tier alone | v4 difference | v3 difference |
|---|---|---|
| Tier A | +0.306 [+0.062, +0.537] | −0.186 [−0.721, +0.382] |
| Tier B | −0.119 [−0.678, +0.272] | +0.422 [+0.109, +0.672] |

The pooled direction agrees across eras. The tier splits do not, which is
one more reason the graded object is the pooled A+B contrast.

## Arms

| Object | Object type | What it is | Graded |
|---|---|---|---|
| `DB1` | arm | Tier A+B, dip arm minus above arm, meanR | **Yes, forward only** |
| `DB-TB` | descriptive cut | The `score_total` tie-break within tier, descending and ascending | No |
| `DB-CPIR` | descriptive cut | `DB1` inside cpir above 0.92 and at or below 0.92 | No |
| `DB-DEP` | descriptive cut | Ladder top-3/day against dip-gated top-3/day | No |
| `DB-NULL` | control | A random bull_call_spread null for each `DB-DEP` book | No |

### DB-TB, the tie-break

Production ranks within a tier by `score_total`. The exploratory read found
that the descending order picks worse spreads on v4, so the order is
contested. `DB-DEP` and the top-3 contrast print under both orders. A row
with no score sorts after the scored rows of its tier either way.

### DB-CPIR, the cpir split

The median is fixed now at **0.92**: the median finite cpir over v4 Tier A/B
in-sample positions on the 2026-10-06 exports (694 positions, 353 at or below
it). It is a constant in the module and never re-estimated. The v3 median on
the same rule was 0.94.

### DB-DEP and DB-NULL, the deployment arm

- **Ladder.** The top 3 Tier A/B rows per signal date, every labelled date.
- **Dip-gated.** The same, on dip dates only. No position on an above date.
- **Printed.** Positions, dates, total R, meanR with its CI, and the per-date
  meanR (the mean of each date's mean).
- **Null.** On the same dates, as many random non-veto bull_call_spreads per
  date as the book picked, 10,000 draws, seed 42. The book's percentile in
  that null is printed.

## Unit and metric

- **Statistic.** meanR(dip arm) − meanR(above arm), pooled over positions.
- **CI.** 95%, date-clustered: each arm's signal dates are resampled
  independently with replacement in the same draw, 10,000 draws, seed
  20260811. The arms hold disjoint dates, because the label is per date.
- **Beside it.** Each arm's meanR and [PF](../../../glossary.md#pf), each with
  its own date-clustered [CI](../../../glossary.md#ci). PF is printed, never
  graded.

## Gates

The floors apply to each arm of `DB1`, on forward dates.

| Floor | Value |
|---|---|
| Signal dates per arm | 30 |
| Positions per arm | 60 |

**Why these.** 30 dates and 60 positions per side is the floor
`ticker_class` registered for the same kind of contrast. In-sample, the v4 dip
arm held 46 dates and its difference CI was still about ±0.24 wide. At 30
dates expect about ±0.3. A forward `SUPPORTED` therefore needs a difference
near the in-sample Tier A figure, not the pooled +0.096. The floor is the
minimum for a verdict, not a promise of power.

**Expected wait.** SPY was below its SMA on 21% of v4 in-sample signal dates.
At that rate the dip arm needs about 142 forward signal dates, roughly seven
months of trading days, before its options expire. In a v3-like tape (65%)
it needs about 47. In a steady rally it may never fill. The seal must also
lift first, at 40 priced sealed dates. The report prints both counts on
every run.

The era refusals of `lib/era.py` (exit 2 and 3) are designed refusals.

## Verdicts, worded now

| Token | When |
|---|---|
| `SUPPORTED` | Both arms past their floor, CI excludes 0, difference positive |
| `CONTRARY` | Both arms past their floor, CI excludes 0, difference negative |
| `NULL` | Both arms past their floor, CI spans 0 |
| `STILL-OPEN` | Either arm short of its floor, or the forward dates still sealed |

**The verdict of record is the first run that prints a token other than
`STILL-OPEN`,** as recorded in
[`study-results`](../../../study-results/f1_selection/regime/dip_buy.md). The CI is a
fixed-sample interval, so later runs are descriptive and never replace it.

## Anti-tuning

- The SMA window (50), the strict "below", the floors, the cpir median, the
  tie-break pair, `TOP_K` 3 and both seeds are fixed here.
- No other moving average, distance below the SMA, VIX cut or tier subset is
  graded. A new cut is a new registration on new dates.
- The in-sample tables are printed as they fall. None is removed for looking
  bad, and none is promoted for looking good.

## Ship criteria

Nothing ships from this study.

- A forward `SUPPORTED` lets the operator consider a deployment-rules change,
  for example deploying fewer positions on above dates. That change would need
  its own registration and rollback trigger.
- A forward `NULL` or `CONTRARY` closes the lead.
- `STILL-OPEN` changes nothing.

## Build notes

Not part of the registration.

- Module: `scripts/backtest_study/f1_selection/regime/dip_buy.py`. Run with
  `python -m scripts.backtest_study run dip_buy`. The report is
  `backtests/study_output/dip_buy-latest.txt`.
- The v3 context is loaded in the same process with `load_book(era="v3")`.
  A `--era v3` run prints v3 alone and grades nothing.
- Tests: `tests/test_dip_buy.py` pins the dip label, the gating, the
  tie-break and the verdict grammar on synthetic data.
