# regime_map — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/regime/regime_map.md); where the two differ, the registration wins.
> Latest outcome: on v4 net, `POSITIVE` 2, `NEGATIVE` 1, `NULL` 45. On v3 gross, `POSITIVE` 17, `NEGATIVE` 8, `NULL` 19. Cells printing `THIN`: 28 on v4, 32 on v3. The `REPLICATED` cells are `A x RM-MDIR=BEAR` and `A x RM-SMA=below`, both `POSITIVE`. Forward `STILL-OPEN` — 2026-10-12 · [record](../../../study-results/f1_selection/regime/regime_map.md).
> Nothing else here is a result.

## The question

For each ladder tier against each market label, is the realized [meanR](../../../glossary.md#meanr) clearly above zero, clearly below zero, or neither? Does the answer hold in both eras? The study prints a fixed map. It is descriptive, not a selection rule.

## What it compares

The registration was accepted by default on 2026-10-12. Only the defaults carry a verdict.

Each cell is one tier on one label level. The graded tiers are A, B, C and VETO. `A+B` prints beside them and is never graded. Each cell is graded against zero, never against its neighbours.

| Object | Label family and levels | Kind |
|---|---|---|
| `regime_map RM-CELL` | `mech_cell`: LVOL, BEAR_HE, RB_EVOL, NONE (labelled, no cell) | arm |
| `regime_map RM-MDIR` | mech direction: BULL, BEAR, RANGE | arm |
| `regime_map RM-MVOL` | mech vol: L-VOL, H-VOL, E-VOL | arm |
| `regime_map RM-SMA` | SPY below or above its 50-day SMA, the [dip date](../../../glossary.md#dip-date) label | arm |
| `regime_map RM-RDIR` | model regime direction: BULL, BEAR, RANGE | arm |
| `regime_map RM-RVOL` | model vol: L-VOL, H-VOL, E-VOL, C-VOL | arm |

A row a family cannot label leaves that family only, and the count prints per family. Tier A is defined partly by the model regime, so some tier × model-label cells are empty by construction. They print as `THIN`.

## How it is judged

**Measure.** The stored [R](../../../glossary.md#r), per cell. v4 R is net of `cost_total`. v3 carries no cost columns, so v3 R is gross. Every cell prints n, dates, win%, [PF](../../../glossary.md#pf), meanR net with its [CI](../../../glossary.md#ci), meanR gross (v4 only), [MFE and MAE](../../../glossary.md#mfe), [give-back](../../../glossary.md#give-back), [capture](../../../glossary.md#capture), dollars, p and q.

**Population.** Loader defaults: real and `strike_expiry_tweak` rows, no bs rows, proxy calibration on. VETO rows are kept as a tier. Rows with no stored R, or with `fill_trusted` False, are dropped and counted.

- **In-sample:** every signal date before `era.SEAL_START`, v4 and v3 run separately.
- **Forward:** v4 signal dates on or after `era.SEAL_START`, readable once `era.SEAL_LIFTED` is set.

**Interval.** Date-clustered bootstrap, 10,000 draws, seed 20260811. The bootstrap p is `min(1, 2 × min(share of draws ≤ 0, share ≥ 0))`.

**Gates.** A cell needs 30 positions and 10 signal dates to carry a verdict. Below either floor it prints every statistic and the token `THIN`.

**Bar.** Each cell is graded per era, on that era's default basis.

1. The cell is past both floors.
2. The [BH](../../../glossary.md#bh) q-value decides the token: below 0.05 is `POSITIVE` or `NEGATIVE` by the sign of meanR.
3. The BH family is every non-`THIN` graded cell in that era's map: four tiers × all 19 levels, at most 76 cells.

`A+B` and the ex-stress re-cut sit outside the BH family. The raw CI-only token prints in its own column.

Two parameters print both ways and are not graded:

- Correction: BH q < 0.05 is graded; the raw CI clear of 0 is printed.
- Replication basis: v4 net against v3 gross is graded; v4 gross against v3 gross is printed.

The ex-stress re-cut repeats the map without 2025-03-01 to 2025-04-30 and 2026-02-01 to 2026-04-30. It is printed and not graded.

## Possible verdicts

| Token | What it means |
|---|---|
| `POSITIVE` | Past both floors, meanR > 0, BH q < 0.05 |
| `NEGATIVE` | Past both floors, meanR < 0, BH q < 0.05 |
| `NULL` | Past both floors, q ≥ 0.05 |
| `THIN` | Below either floor |
| `REPLICATED` | The v4 and v3 verdicts are the same token, and it is `POSITIVE` or `NEGATIVE` |
| `CONTRADICTED` | The v4 and v3 verdicts are opposite non-null tokens |

Only `REPLICATED` cells are read forward, on v4 signal dates on or after `era.SEAL_START`, with the same floors and no BH.

| Forward token | What it means |
|---|---|
| `CONFIRMED` | Past both floors, CI95 clear of 0 on the in-sample side |
| `NOT-CONFIRMED` | Past both floors, otherwise |
| `STILL-OPEN` | Below either floor, or the forward dates still sealed |

## What could ship

Nothing ships from this study. A `REPLICATED` cell that is later `CONFIRMED` forward lets the operator consider a deployment-rules change, through its own registration.

## What this study cannot tell you

- Whether one cell beats another. Cells are graded against zero only. [`dip_buy DB1`](../../../arm-index.md#dip_buy) stays the one graded dip-minus-above contrast.
- A selection rule. A rule a cell suggests needs its own registration, a PBO read and forward dates.
- Anything blind. The map was written after an exploratory read that had already shown two v4 cells.
- Anything about exits or combined labels such as `mech_cell` × model vol. Exits are the stored ones, and no combined label is added.
