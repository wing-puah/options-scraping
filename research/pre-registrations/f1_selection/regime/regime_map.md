## regime_map — in which market conditions does each ladder tier make or lose money?

_Registered 2026-10-12, before the study's first run._

**STATUS: ACCEPTED BY DEFAULT 2026-10-12 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Contested choices are parameters printed both
ways; only the defaults below carry a verdict.

**What this file says, in one paragraph.** The operator asked where the ladder
works. This study prints a fixed map: each ladder tier (A, B, C, VETO) against
each of six market labels, one label at a time. Every cell gets the same
statistics and one of four verdict words, with a multiple-comparison
correction across the whole map. A cell counts as replicated only when v4 and
v3 give it the same non-null verdict. It is a descriptive map, not a selection
rule.

## Question

For each tier × label cell, is the realized [meanR](../../../glossary.md#meanr)
clearly above zero, clearly below zero, or neither, and does the answer hold
in both eras?

## What this is NOT

- **Not a selection rule.** No cell here changes which plays are deployed. A
  rule a cell suggests ("skip Tier B in label X") needs its own registration,
  a PBO read over the rules it was chosen from, and forward dates.
- **Not a contrast between cells.** Each cell is graded against zero, not
  against its neighbours. [`dip_buy DB1`](../../../arm-index.md#dip_buy) stays
  the one graded dip-minus-above contrast; this map prints the same
  population's two halves but grades neither against the other.
- **Not a new tier or label.** Tiers come from
  `scripts/journal/lib/mapping.py::ladder_tier` (via `dip_buy.tier_of`).
  Mechanical labels come from `lib/mech_regime.py::MechLabeler`. Model labels
  come from the analysis row's `market_regime` text, as the loader parses it.
- **Not an exit study.** Exits are the shipped ones as stored on each row.

## Overlap with earlier studies

| Study | What it already covers | What this adds |
|---|---|---|
| `mech_regime_recut` | Mechanical vs model label as a veto and exit key, pooled book | Every tier × every label, one grammar, BH, v3 replication |
| `regime_gap_reread` | The pooled-book baseline report, no verdicts | Verdicts per cell |
| `dip_buy` | Tier A/B dip minus above, forward only | The dip label for every tier, graded against zero |
| `ticker_class_regime` (draft) | Index vs single stock by regime | Nothing; tickers are not a cell axis here |

## Population and basis, fixed here

- **Loader.** `load_book()` at its defaults: real and `strike_expiry_tweak`
  rows, bs excluded, proxy calibration on. Rows with no stored R, or with
  `fill_trusted` False, are dropped and counted. VETO rows are kept as a tier.
- **Outcome.** The stored `realized_pnl_pct` ([R](../../../glossary.md#r)).
  On v4 it is net of the row's `cost_total`; the gross figure adds the cost
  back on the same scale (`ticker_class.cost_pct_of`). v3 carries no cost
  columns, so v3 R is gross.
- **In-sample.** Every signal date before `era.SEAL_START`, on v4 and on v3,
  each run separately.
- **Forward.** v4 signal dates on or after `era.SEAL_START`, readable once
  `era.SEAL_LIFTED` is set. This study is not a named sealed reader.

## Cells

Tiers: `A`, `B`, `C`, `VETO`, each graded. `A+B` is printed beside them and
never graded.

| Label family | Levels | Source |
|---|---|---|
| `RM-CELL` mech_cell | LVOL, BEAR_HE, RB_EVOL, NONE | `MechLabeler.cell`; NONE = labelled, no cell |
| `RM-MDIR` mech direction | BULL, BEAR, RANGE | `MechLabeler.label` |
| `RM-MVOL` mech vol | L-VOL, H-VOL, E-VOL | `MechLabeler.label` |
| `RM-SMA` SPY vs 50-day SMA | below, above | `MechLabeler.below_sma` ([dip date](../../../glossary.md#dip-date)) |
| `RM-RDIR` model regime direction | BULL, BEAR, RANGE | `book.model_direction(market_regime)` |
| `RM-RVOL` model vol | L-VOL, H-VOL, E-VOL, C-VOL | `book.model_vol(market_regime)` |

A row a family cannot label (the SPY/VIX table does not reach the date, no
50-day runway, or no token in the model's text) leaves that family only. The
count is printed per family. Tier A is defined partly by the model regime, so
some tier × model-label cells are empty by construction; they print as THIN.

## Per-cell statistics

Every cell prints all of these. None is dropped for looking bad.

| Statistic | Definition |
|---|---|
| n, dates | Positions and distinct signal dates |
| win% | Share of positions with R > 0 |
| [PF](../../../glossary.md#pf) | Sum of gains over sum of losses |
| meanR net, CI95 | Pooled mean, date-clustered bootstrap, 10,000 draws, seed 20260811 |
| meanR gross | v4 only; equals net on v3 |
| [MFE / MAE](../../../glossary.md#mfe) | Mean `mfe_pct` and `mae_pct` |
| [give-back](../../../glossary.md#give-back) | Mean of MFE − R over rows with an MFE |
| [capture](../../../glossary.md#capture) | Sum of R over sum of MFE, rows with MFE > 0 |
| $ | Sum of `R_dol` |
| p, q | Two-sided bootstrap p for meanR = 0, and its BH q |

The bootstrap p is `min(1, 2 × min(share of draws ≤ 0, share ≥ 0))`.

## Floors

A cell needs **30 positions and 10 signal dates** to carry a verdict. Below
either floor it prints every statistic and the token `THIN`.

**Why these.** 30 positions is the smallest cell the
[`ticker_class`](../../../arm-index.md#ticker_class) power gate used per side.
10 dates keeps one clustered sell-off from being a whole cell. A cell at the
floor has a meanR CI roughly ±0.3 wide, so only large effects will clear.

## Verdicts, worded now

Graded per cell, per era, on that era's default basis (v4 net, v3 gross).

| Token | When |
|---|---|
| `POSITIVE` | Past both floors, meanR > 0, BH q < 0.05 |
| `NEGATIVE` | Past both floors, meanR < 0, BH q < 0.05 |
| `NULL` | Past both floors, q ≥ 0.05 |
| `THIN` | Below either floor |

**The BH family** is every non-THIN graded cell in that era's map: four tiers
× all 19 levels, at most 76 cells. `A+B` and the ex-stress re-cut are outside
it. A percentile-bootstrap p below 0.05 is the same event as a CI clear of
zero, so the raw token (`POSITIVE`/`NEGATIVE` on the CI alone) is printed in
its own column.

**Replicated.** A cell is `REPLICATED` when its v4 verdict and its v3 verdict
are the same token and that token is `POSITIVE` or `NEGATIVE`. A cell with
opposite non-null tokens is `CONTRADICTED`. Anything else is not replicated.

## Parameters printed both ways, not graded

| Parameter | Default (graded) | Alternative (printed) | Why contested |
|---|---|---|---|
| Correction | BH q < 0.05 | Raw CI clear of 0 | BH on 76 overlapping cells is strict |
| Replication basis | v4 net vs v3 gross | v4 gross vs v3 gross | Net is what the operator earns; gross is like for like |

## Ex-stress re-cut

The whole map again without signal dates from 2025-03-01 to 2025-04-30 and
2026-02-01 to 2026-04-30 (the windows `adaptive_ladder` used). Its tokens are
printed and labelled not graded. The windows were chosen from outcomes, so
they cannot grade anything.

## Forward read

Only cells `REPLICATED` in-sample are read forward, on v4 signal dates on or
after `era.SEAL_START`, with the same floors.

| Token | When |
|---|---|
| `CONFIRMED` | Past both floors, CI95 clear of 0 on the in-sample side |
| `NOT-CONFIRMED` | Past both floors, otherwise |
| `STILL-OPEN` | Below either floor, or the forward dates still sealed |

No BH on the forward read: it tests a short list fixed before the dates exist.

## Plan-time observations, disclosed

The 2026-10-12 exploratory read (scratchpad `q1.py`) printed Tier A, B and C
meanR by `mech_cell`, model direction, model vol and SPY above or below its
SMA, on both eras, without a correction. Two cells stood out on v4: Tier A
in BEAR_HE (+0.426, 28 positions) and Tier A below the SMA (+0.332, 65
positions). This file was written after that read, so the map is not blind to
it. That is one reason the map grades every cell under one correction and
ships nothing.

## Anti-tuning

- The six label families, their levels, the floors, the BH level, the
  bootstrap seed and the stress windows are fixed here.
- No new label, threshold, combined label (`mech_cell` × model vol) or tier
  subset is added to this study. A new cut is a new registration.

## Ship criteria

Nothing ships from this study. A `REPLICATED` cell that is later `CONFIRMED`
forward lets the operator consider a deployment-rules change, through its own
registration.

## Build notes

Not part of the registration.

- Module: `scripts/backtest_study/f1_selection/regime/regime_map.py`. Run
  with `python -m scripts.backtest_study run regime_map`. The report is
  `backtests/study_output/regime_map-latest.txt`.
- v3 is loaded in the same process with `load_book(era="v3")`.
- Tests: `tests/test_regime_map.py` pins the cell labels, the floors, the BH
  adjustment, the verdict grammar and the replication rule on synthetic data.
