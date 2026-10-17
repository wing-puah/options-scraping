# dip_buy — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/regime/dip_buy.md); where the two differ, the registration wins.
> Latest outcome: forward `STILL-OPEN` — 2026-10-12 · [record](../../../study-results/f1_selection/regime/dip_buy.md).
> Nothing else here is a result.

## The question

Do non-vetoed Tier A/B positions earn a higher [meanR](../../../glossary.md#meanr) when SPY closed below its 50-day SMA on the signal date? An exploratory read on 2026-10-12 found one rule that ranked high in both eras: Tier A/B positions taken on a [dip date](../../../glossary.md#dip-date).

The rule was picked after the fact from 28 candidates. The in-sample book therefore cannot confirm it. Only forward dates carry a verdict.

## What it compares

The registration was accepted by default on 2026-10-12. Contested choices are parameters printed both ways. None of them is graded.

| Object | What it does | Kind |
|---|---|---|
| `dip_buy DB1` | Tier A+B meanR on dip dates minus meanR on above dates, forward dates only | arm, graded |
| `dip_buy DB-TB` | The `score_total` tie-break within tier, printed descending and ascending | descriptive cut |
| `dip_buy DB-CPIR` | `DB1` inside cpir above 0.92 and inside cpir at or below 0.92 | descriptive cut |
| `dip_buy DB-DEP` | Ladder top-3 per day against dip-gated top-3 per day, under both tie-break orders | descriptive cut |
| `dip_buy DB-NULL` | Random non-veto bull_call_spreads on the same dates, as many per date as the book picked | control |

Definitions behind the labels:

- A dip date has SPY's close strictly below its 50-day SMA, as of the last trading day on or before the signal date. The label is `MechLabeler.below_sma`.
- A date the table does not reach, or with no 50-day runway, is dropped and counted.
- The tier comes from `mapping.ladder_tier`. VETO rows are dropped. Nothing here changes which plays are tiered A or B.
- The 0.92 cpir split is the median finite cpir over v4 Tier A/B in-sample positions on the 2026-10-06 exports. It is a constant and never re-estimated.
- The `DB-DEP` dip-gated book takes no position on an above date. `DB-NULL` uses 10,000 draws and seed 42, and prints the book's percentile in that null.

## How it is judged

**Measure.** meanR(dip arm) − meanR(above arm), pooled over positions. The outcome is the stored [R](../../../glossary.md#r), net of the row's `cost_total`.

**Population.** The loader uses its defaults: real and `strike_expiry_tweak` rows, no bs rows, proxy calibration on. Rows with no stored R, or with `fill_trusted` False, are dropped and counted.

- **Forward (graded):** every v4 signal date on or after `era.SEAL_START`, read from `lib/era.py` at run time.
- **In-sample (context only):** every date before `era.SEAL_START`, v4 and v3 printed separately. No in-sample figure carries a verdict.
- **Still sealed:** forward dates are readable only after `era.SEAL_LIFTED` is set. Until then the forward arms are empty.
- **Era:** a prompt-version bump freezes the grade at the last v4 date. Dates from two prompt versions are never pooled.

**Interval.** The 95% [CI](../../../glossary.md#ci) is date-clustered. The two arms resample their own signal dates independently, 10,000 draws, seed 20260811. Each arm's meanR and [PF](../../../glossary.md#pf) print with their own CI. PF is never graded.

**Gates.** The floors apply to each arm of `dip_buy DB1`, on forward dates.

- 30 signal dates per arm.
- 60 positions per arm.

The report also prints how many forward dates exist and how many priced sealed dates remain before the seal lifts.

**Bar.** The verdict needs all of these.

1. Both arms are past their floors.
2. The CI of the difference excludes 0.
3. The sign of the difference decides `SUPPORTED` or `CONTRARY`.

The verdict of record is the first run that prints a token other than `STILL-OPEN`. Later runs are descriptive.

## Possible verdicts

| Token | What it means |
|---|---|
| `SUPPORTED` | Both arms past their floor, CI excludes 0, difference positive |
| `CONTRARY` | Both arms past their floor, CI excludes 0, difference negative |
| `NULL` | Both arms past their floor, CI spans 0 |
| `STILL-OPEN` | Either arm short of its floor, or the forward dates still sealed |

## What could ship

Nothing ships from this study. A forward `SUPPORTED` lets the operator consider a deployment-rules change, such as fewer positions on above dates. That change needs its own registration and rollback trigger. A forward `NULL` or `CONTRARY` closes the lead. `STILL-OPEN` changes nothing.

## What this study cannot tell you

- Anything from the in-sample dates. They are post hoc context and carry no verdict.
- Whether any other moving average, distance below the SMA, VIX cut or tier subset helps. None is graded.
- Anything about exits. Exits are the stored ones.
- When the answer arrives. The registration expects a wait of about 142 forward signal dates for the dip arm at the in-sample dip rate of 21%.
