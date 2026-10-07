## ticker_class_regime — does the index-vs-single-stock gap depend on market regime?

_Registered ____-__-__ (DRAFT — not registered; becomes immutable in substance when the operator accepts it)._

**STATUS: DRAFT.** This file was written and hashed on 2026-10-07, BEFORE the exploratory
in-sample regime read was run. That read cannot change this design. Any edit made after it
is listed under [Changes after the exploratory read](#changes-after-the-exploratory-read).

## Question

[`ticker_class`](ticker_class.md) found no reliability gap between index ETFs and single
stocks on the pooled in-sample book. A pooled NULL can hide a gap that flips sign by regime.
Does the index-minus-single-stock difference on bear plays differ between the
[BEAR_HE](../../glossary.md#bear_he) and [LVOL](../../glossary.md#lvol) regime cells? It is
graded on forward dates only.

## What this is NOT

- Not a re-grade of `ticker_class`. Its verdicts stand. This study reads none of its
  in-sample dates.
- Not a regime filter or exit rule. A positive verdict files "to be tested" and changes no
  production code.
- Not a test of the model's own regime text. The regime label is the deterministic
  [mech_cell](../../glossary.md#mech_cell) only.

## The trial ledger

This study adds three trials to the selection ledger that `ticker_class` opened: one primary
(F1) and two secondary (F2, F3). It selects nothing in-sample, so no PBO read applies. The
forward window is the guard.

## Definitions

- **Groups.** The frozen `ticker_class` table, imported from its module and checked by the
  same sha256 (`6ce7373e…`). G1 is the index group. S is G5 ∪ G6 ∪ G7.
- **Direction.** As in `ticker_class`. Only bear plays are graded. G1 is 80% bear, so a
  bull cell would rarely reach power.
- **Regime.** The row's `mech_cell` as `load_book()` returns it. LVOL and BEAR_HE are graded.
  RB_EVOL and `PROD` are printed only. `PROD` is the loader's label for rows that map to no
  override cell, including rows with no label.
- **Metrics.** meanR with a date-clustered CI95 and hit rate, on the `load_book()` basis and
  net of cost, exactly as `ticker_class` computes them.

## Population and basis, fixed here

- **Forward dates.** Signal dates after 2026-10-07 that have backtest rows.
- **One prompt era.** All graded rows come from one era. If the prompt version bumps before
  the grade, the count restarts at the new era's first date and earlier forward rows are
  printed, never pooled.
- **No in-sample reads.** Dates on or before 2026-10-07 are never graded here.

## Plan-time observations, disclosed

These are accrual estimates from the in-sample descriptor census. No outcome was used.

| Cell, bear plays | In-sample rate per signal date | About 60 positions after |
|---|---|---|
| G1, LVOL | 0.6 | 5 months |
| S, LVOL | 1.0 | 3 months |
| G1, BEAR_HE | 0.1 | 2 years or more |
| S, BEAR_HE | 0.3 | 10 months |

The "after" column assumes about 21 live signal dates a month. BEAR_HE accrues only while
the market is in a downtrend with high VIX, so its pace depends on the market, not the
calendar. It is the binding cell. The study may well end UNDERPOWERED.

## Arms

| Object | Object type | Role |
|---|---|---|
| F1 | (G1 − S) in BEAR_HE minus (G1 − S) in LVOL, bear plays | PRIMARY, graded |
| F2 | G1 − S in LVOL, bear plays | secondary, graded |
| F3 | G1 − S in BEAR_HE, bear plays | secondary, graded |
| D1 | G1 − S in RB_EVOL and `PROD`, bear plays | printed |
| D2 | G1 − S per cell, bull plays | printed |

F1's CI comes from one date-clustered bootstrap that resamples dates jointly across all four
sides.

## Gates

| Gate | Rule | On failure |
|---|---|---|
| GR0 power | Each of F1's four sides has 30 or more dates and 60 or more positions | census printed; `STILL-OPEN` |
| GR1 settled | 25% or fewer of a graded side's positions are open at the data end | `STILL-OPEN` |
| GR2 map | The group-table hash matches `ticker_class`'s | exit 1 |
| GR3 era | Every graded row is from one era, named in the header | exit 3 |
| GR4 sunset | GR0 or GR1 still fails on 2027-10-07 | `UNDERPOWERED`, final |

Runs before GR0 and GR1 pass print the census only. No outcome statistic is printed until
then. The grade is taken once, at the first run where both pass. No later run re-grades it.

## Bar

F1, or a secondary contrast, clears only when all three hold:

1. **Expectancy.** Its CI95 excludes 0. F2 and F3 are Holm-adjusted as a pair.
2. **Hit rate.** The hit-rate difference has the same sign as the meanR difference.
3. **Concentration.** The sign holds with the largest ticker of each side removed.

## Verdicts, worded now

| Verdict | When |
|---|---|
| REGIME-DEPENDENT | F1 clears the bar |
| NULL | F1 does not clear the bar. This means no evidence of dependence; it never means the gap is regime-free. |
| INDEX-BETTER-IN-`<cell>` / INDEX-WORSE-IN-`<cell>` | F2 or F3 clears the bar, by sign |
| STILL-OPEN | GR0 or GR1 fails before the sunset |
| UNDERPOWERED | GR4 |

## Anti-tuning

- Cells, sides, gates, the sunset and the bar are fixed here.
- The exploratory in-sample read is never pooled with forward rows and never cited as
  support for a forward verdict.
- No new regime definition, threshold or cell after acceptance. Each is a new registration.

## Ship criteria

Nothing ships from this study. REGIME-DEPENDENT or a per-cell verdict files "to be tested"
in `research/deployment-evidence.md`.

## Changes after the exploratory read

The draft was hashed at 2026-10-07 20:11 +08 (sha256 `682be3c0…`) before the read ran.

| Date | Change | Why |
|---|---|---|
| 2026-10-07 | `NONE` and `NO_DATA` replaced by the loader's `PROD` label | The loader has no `NONE` or `NO_DATA` value. A label fact, not an outcome. |

## Build notes

- Add it as a forward mode on `scripts/backtest_study/f1_selection/ticker_class.py`, or as a
  sibling module that imports its group table, `prepare` and `joint_boot`. Never copy them.
- It needs a catalog entry, an arm-index section and a README row at acceptance.
