## ticker_class_regime — does the index-vs-single-stock gap depend on market regime?

_Registered ____-__-__ (DRAFT — not registered; becomes immutable in substance when the operator accepts it)._

**STATUS: DRAFT.** The first version was hashed on 2026-10-07, BEFORE the exploratory
in-sample regime read ran. The operator then asked for more regime splits and stronger
robustness. Every change made after the read is listed under
[Changes after the exploratory read](#changes-after-the-exploratory-read), with which ones the
read suggested.

## Question

[`ticker_class`](ticker_class.md) found no reliability gap between index ETFs and single
stocks on the pooled in-sample book. A pooled NULL can hide a gap that flips sign by regime.
Does the index-minus-single-stock gap depend on the market's trend or volatility regime, on
forward dates only?

## What this is NOT

- Not a re-grade of `ticker_class`. Its verdicts stand. This study reads none of its
  in-sample dates.
- Not a regime filter or exit rule. A confirmed verdict files "to be tested" and changes no
  production code.
- Not a test of the model's own regime text. The graded regime is the deterministic
  [mech_cell](../../glossary.md#mech_cell) axes. The model's text appears only as a robustness check.
- Not a search. The graded family is closed below at seven contrasts. Everything else is
  printed and never graded.

## How overfitting is held down

Testing many splits finds something by chance unless the design pays for each one. Six
guards do that. Each is defined in full further down.

| Guard | What it stops |
|---|---|
| A closed family of seven graded contrasts, fixed now | Adding splits after seeing results |
| A fixed share of the error budget for each contrast (Bonferroni, total 0.05) | Chance hits across many splits, whenever each one is graded |
| Permutation p-values that keep the data's time structure | Overconfident p-values from correlated dates |
| A veto-only robustness battery | A result that lives in one ticker, month, cost basis or metric |
| A minimum effect of 0.10 R | Significant but trivial gaps |
| A separate confirmation window | A discovery-window fluke being reported as a finding |

The robustness checks can only veto. Adding more of them makes a positive verdict harder,
never easier.

## The trial ledger

This study adds seven graded trials to the selection ledger that `ticker_class` opened. The
printed grid adds none, because nothing in it can produce a verdict.

## Definitions

- **Groups.** The frozen `ticker_class` table, imported from its module and checked by the
  same sha256 (`6ce7373e…`). G1 is the index group. S is G5 ∪ G6 ∪ G7.
- **Play direction.** As in `ticker_class`: bear, bull or neutral, from the canonical
  structure. Neutral plays are printed only.
- **Trend axis.** The loader's `mech_direction`: BULL, RANGE or BEAR. "Non-BULL" pools RANGE
  and BEAR.
- **Vol axis.** The loader's `mech_vol`: L-VOL, or "H/E-VOL", which pools H-VOL and E-VOL.
- **Gap.** G1 meanR minus S meanR within a cell, on the `load_book()` basis, net of cost,
  computed exactly as `ticker_class` computes it. Both sides of a gap have the same play
  direction, so no direction standardisation is needed.
- **Unlabelled rows.** Rows with no `mech_direction` or `mech_vol` are dropped and counted.

## Population and basis, fixed here

- **Forward dates.** Signal dates after 2026-10-07 that have backtest rows.
- **One prompt era.** All graded rows come from one era. If the prompt version bumps before
  a contrast is graded, its count restarts at the new era's first date. Earlier forward rows
  are printed, never pooled.
- **No in-sample reads.** Dates on or before 2026-10-07 are never graded here.

## Plan-time observations, disclosed

These are accrual estimates from the in-sample descriptor census (251 signal dates). They
use counts only. They assume about 21 live signal dates a month and an in-sample regime mix.
The real pace depends on the market.

| Cell | G1 positions per signal date | G1 reaches 60 positions after about |
|---|---|---|
| Bear plays, BULL trend | 0.49 | 6 months |
| Bear plays, non-BULL trend | 0.27 | 11 months |
| Bear plays, L-VOL | 0.59 | 5 months |
| Bear plays, H/E-VOL | 0.16 | 18 months |
| Bull plays, BULL trend and L-VOL | 0.14 | 20 months |

S accrues faster than G1 in every cell, so G1 is the binding side. Index bear plays sit
mostly in BULL + L-VOL: 112 of 189 in-sample positions. Every other cell of the 3 × 3 grid
has under 20 G1 bear positions in-sample, so the grid is printed, not graded.

## Arms

### Graded family

| Object | Object type | Error budget (α) |
|---|---|---|
| C1 | Gap, bear plays, BULL trend | 0.005 |
| C2 | Gap, bear plays, non-BULL trend | 0.005 |
| C3 | Gap, bear plays, L-VOL | 0.005 |
| C4 | Gap, bear plays, H/E-VOL | 0.005 |
| C5 | Gap, bull plays, BULL trend and L-VOL | 0.005 |
| I1 | C1 minus C2: does the gap depend on trend? | 0.0125 |
| I2 | C3 minus C4: does the gap depend on volatility? | 0.0125 |

The budgets sum to 0.05. A fixed budget per contrast keeps the family-wise error at or below
0.05 even though contrasts reach power at different times and are graded separately.

### Printed, never graded

| Object | What it shows |
|---|---|
| P1 | The gap in every cell of the 3 × 3 trend × vol grid, bear and bull plays |
| P2 | The gap against G5, G6 and G7 separately, per graded cell |
| P3 | The original draft's contrast: BEAR_HE minus LVOL, bear plays |
| P4 | Neutral plays per cell |

A lead seen in P1–P4 needs a new registration.

## Tests

- **Cell gaps (C1–C5).** The test is a permutation test.
  - The G1/S labels are shuffled among positions of the same play direction, within the
    same calendar week and the same cell.
  - Shuffling within a week keeps each week's market move on both sides.
  - The p-value is two-sided, (1 + shuffles at least as extreme) / (1 + 10,000), with
    seed 20261007.
  - A date-clustered bootstrap CI at level 1 − α (for example 99.5% for C1) is printed
    beside it.
- **Interactions (I1, I2).** The test is a circular-shift permutation test.
  - The date series of regime labels is shifted by k signal dates, for every k at least 10
    dates away from zero, and the interaction is recomputed each time.
  - The p-value is (1 + shifts at least as extreme) / (1 + shifts). With 160 shifts its
    floor is about 0.006.
  - Shifting keeps the regime's own run lengths and autocorrelation. Shuffling it would
    destroy them.
  - A joint date-clustered bootstrap CI is printed beside it.

## Gates

| Gate | Rule | On failure |
|---|---|---|
| GR0 power | Each side of the contrast has 30 or more dates and 60 or more positions. An interaction needs this on all four sides. | census only; `STILL-OPEN` |
| GR1 settled | 25% or fewer of each side's positions are open at the data end | `STILL-OPEN` |
| GR2 map | The group-table hash matches `ticker_class`'s | exit 1 |
| GR3 era | Every graded row is from one era, named in the header | exit 3 |
| GR4 shifts | An interaction has at least 160 admissible circular shifts, so its p can fall below its α of 0.0125 | that interaction `STILL-OPEN` |
| GR5 sunset | A contrast has not passed GR0 and GR1 by 2028-04-07 | `UNDERPOWERED`, final |

Before a contrast passes GR0 and GR1, runs print its census only. No outcome statistic of
that contrast is printed. Each contrast is graded once, at the first run where it passes.
Its discovery window is every forward date up to that run. No later run re-grades it.

## Bar at discovery

A contrast clears discovery only when all four hold:

1. **Significance.** The permutation p is at or below its α, AND the bootstrap CI at level
   1 − α excludes 0.
2. **Size.** The absolute gap, or interaction, is at least 0.10 R.
3. **Robustness.** Every evaluable check in the battery keeps the sign.
4. **No PBO veto.** See [PBO diagnostic](#pbo-diagnostic).

### Robustness battery

A check is evaluable when each side of its subset has 15 or more positions. A check that is
not evaluable is printed as `n/a` and does not veto. At least six checks must be evaluable,
or the contrast reads `NOT ROBUST-TESTABLE` instead of clearing.

| Check | The sign must hold when… |
|---|---|
| RB1 | the largest ticker of each side is removed (for example IWM) |
| RB2 | only real rows are used (proxy rows dropped) |
| RB3 | R is taken gross of cost |
| RB4 | the median R difference is used instead of the mean |
| RB5 | the hit-rate difference is used instead of meanR |
| RB6 | any single calendar month is left out, in every such fold |
| RB7 | the discovery window is cut into an earlier and a later half, in both halves |
| RB8 | only debit verticals are used |
| RB9 | the cell is defined by the model's own `market_regime` text, where it parses to the same trend or vol |
| RB10 | the exit-free number [E](../../glossary.md#e) is used instead of R |
| RB11 | the five dates contributing most to the gap are removed |

For an interaction, each check is applied to the interaction itself.

### PBO diagnostic

When a contrast is graded, a CSCV over discovery-window months picks the best of the five
cell gaps C1–C5. It needs at least 8 months: the earliest months are trimmed to a multiple of
8 and S is 8. Below 8 months it prints `n/a`. A PBO above 0.50 vetoes every discovery verdict
graded at that run.

## Confirmation

A contrast that clears discovery is `PROVISIONAL`. It must then repeat on new dates.

- **Window.** Signal dates after its discovery run, until GR0 and GR1 pass again on those
  dates alone.
- **Test.** The gap has the same sign and a one-sided permutation p at or below 0.05.
  RB1, RB4 and RB5 must hold.
- **Sunset.** Two years after the discovery run. Failing to reach power by then reads
  `UNCONFIRMED`, final.

Confirmation tests one named contrast in one direction, so it carries no family-wise
correction.

## Verdicts, worded now

| Verdict | When |
|---|---|
| REGIME-DEPENDENT (trend) or (vol) | I1 or I2 is confirmed |
| INDEX-BETTER-IN-`<cell>` or INDEX-WORSE-IN-`<cell>` | C1–C5 confirmed, by sign |
| PROVISIONAL | Discovery cleared; confirmation pending |
| FAILED-CONFIRMATION | Confirmation powered and failed |
| UNCONFIRMED | Confirmation sunset reached without power |
| NULL | Discovery graded and did not clear. This means no evidence; it never means the gap is regime-free. |
| NOT ROBUST-TESTABLE | Discovery significant and large, but fewer than six checks were evaluable |
| STILL-OPEN | Not yet powered, before the sunset |
| UNDERPOWERED | GR5 |

## Anti-tuning

- The family, the α budgets, the blocks, the shift rule, the battery, the effect floor, the
  sunsets and the bar are fixed here.
- No contrast is added, merged or re-cut after acceptance. A new one is a new registration
  with its own ledger line.
- The exploratory in-sample read is never pooled with forward rows and never cited as
  support for a forward verdict.
- An outcome not named above goes to the nearest verdict with a printed qualification.

## Ship criteria

Nothing ships from this study. Only a confirmed verdict files "to be tested" in
`research/deployment-evidence.md`. A `PROVISIONAL` result files nothing.

## Changes after the exploratory read

The first draft was hashed at 2026-10-07 20:11 +08 (sha256 `682be3c0…`) before the read ran.

| Date | Change | Source |
|---|---|---|
| 2026-10-07 | `NONE` and `NO_DATA` replaced by the loader's label | A label fact, not an outcome |
| 2026-10-07 | Graded family rebuilt on the trend and vol axes: C1–C5, I1, I2 | Operator, asking for more splits |
| 2026-10-07 | I1 (BULL vs non-BULL) added | The read: the late-2025 loss sat inside L-VOL, which mixes trends |
| 2026-10-07 | C5 (bull plays, BULL + L-VOL) added | The read: in-sample bull lead +0.256 on 41 positions |
| 2026-10-07 | The draft's BEAR_HE vs LVOL contrast moved to printed (P3). I2 replaces it on the plain vol axis, which accrues faster. | Accrual census, counts only |
| 2026-10-07 | α budgets, permutation tests, robustness battery, effect floor, confirmation window added | Operator, asking for robustness against overfitting |

## Build notes

- Add it as a forward mode on `scripts/backtest_study/f1_selection/ticker_class.py`, or as a
  sibling module that imports its group table, `prepare` and bootstrap helpers. Never copy them.
- Tests must check that each permutation test holds its α on synthetic null data, and that a
  planted effect clears. That is a test of the code, not of the data.
- It needs a catalog entry, an arm-index section, and its README row updated at acceptance.
