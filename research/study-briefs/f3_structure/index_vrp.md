# index_vrp — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f3_structure/index_vrp.md); where the two differ, the registration wins.
> Latest outcome: `NO-TAIL-LINK` (SPY condor d0.16, mid fill, v4 deployed book); all eight secondary lines also `NO-TAIL-LINK`; M1 premium `NO-PREMIUM` on SPY and GLD, as context only; nothing ships — 2026-10-12 · [record](../../study-results/f3_structure/index_vrp.md).
> Nothing else here is a result.

## The question

On the deployed ladder book's worst days and in its stress windows, does a monthly short SPY iron condor lose money alongside the book?

The ladder is a bet on direction, and nothing at entry predicts direction. A non-directional sleeve is the next question. Selling index volatility is the textbook one.

The study does not re-ask whether short index volatility pays. It prints the [variance risk premium](../../glossary.md#vrp) as context. It grades only whether a defined-risk short condor loses in the same windows and on the same days as the book.

## What it compares

One condor, or one straddle, per underlying per cycle. The cycles are every standard monthly expiry from the 2022-03 cycle on. Cycles never overlap. Entry is the trading day whose calendar DTE is nearest 30, with ties to the earlier day. Both arms hold to expiry and settle at intrinsic. Labels are `index_vrp ARM S` and `ARM C` ([index](../../arm-index.md#index_vrp)).

| Object | What it does | Kind |
|---|---|---|
| `index_vrp ARM S` | Sells the call and put at the listed strike nearest spot. Undefined risk, so no verdict | descriptive cut |
| `index_vrp ARM C` | Short [iron condor](../../glossary.md#iron-condor): shorts at the cached `Delta` nearest ±0.16, wings nearest 0.03 × spot beyond. Graded on SPY at mid | PRIMARY |

SPY is graded. GLD prints beside it as a secondary read.

**Condor rules.**

- A wing that would land on the short strike moves one listed strike out.
- Max loss is the wider wing's width less the net credit, per share × 100.
- Data is real end-of-day quotes from `backtests/option_history_cache/`. There is no fetch and no model price.
- A leg with no entry-day row, or a cycle with a leg missing on more than 2 held sessions, is dropped and counted.

**Fills.** The default is mid for every leg, plus $0.65 per contract per side. The natural fill prints beside it: sold legs at the bid, bought legs at the ask. A sold leg with no bid fills at 0. A junk quote falls back to `Latest` and is counted.

**Size.** Drawdown and O2 figures print at 1 contract and at the contract count whose max loss is nearest $1,000, minimum 1.

## How it is judged

**Book.** `load_book()` at its defaults on the v4 era, with the holdout seal applied. The deployed book is `account_sim`'s registered cell, marked daily and gross of costs. The cell is:

- $25,000 capital and 2% risk
- 0.25 per position and net 1.50
- `ARM R`, F1, no compounding

The 2.50 net cap book prints as an unregistered secondary line. The stored book prints beside it, net. The v3 era prints as replication when it loads.

**Stress windows.**

| Window | Dates | Book coverage on v4 |
|---|---|---|
| W1 2022 bear | 2022-01-01 → 2022-12-31 | none |
| W2 Aug 2024 | 2024-08-01 → 2024-08-31 | yes |
| W3 Mar–Apr 2025 | 2025-03-01 → 2025-04-30 | yes |
| W4 Feb–Apr 2026 | 2026-02-01 → 2026-04-30 | yes |

W1 has no book. It prints a beta proxy only, which is descriptive and never enters a verdict.

**Context measures.**

- `M1`: the premium per cycle and underlying, in price form and in variance form (`IV_entry − RV`). It prints `PREMIUM` when the price-form CI95 lower bound is above 0, else `NO-PREMIUM`. A VIX tercile cut uses only past values.
- `M2`: P&L, worst daily mark (MAE) and best daily mark (MFE) per cycle. The worst five cycles are listed.

**Graded measure `M3`.** The sleeve is the SPY condor at mid. Its daily mark-to-market change is aligned to the book's sessions.

- `T1`: mean daily sleeve P&L on the book's worst 5% of sessions, CI95.
- `T2`: book and sleeve P&L summed per window W2–W4.
- `T3`: daily correlation, sleeve against book, on all common sessions and on the book's worst-decile sessions, CI95.
- `T4`: max drawdown of the book alone against book plus sleeve, with a block-bootstrap band.
- `T5`: the O2 total-loss overlay, book alone against book plus sleeve.

T1 and T3 use a stationary block bootstrap over sessions: mean block 10, 10,000 paths, seed 20261012. Blocks 5 and 20 print beside it.

## Possible verdicts

Graded on the SPY condor, mid fill, v4 deployed book.

| Token | What it means |
|---|---|
| `LOSES-TOGETHER` | The sleeve loses in at least 2 of the 3 covered windows in which the book loses, and T1's CI95 upper bound is below 0 |
| `DIVERSIFIES` | T1's CI95 lower bound is above 0, and the realized max drawdown of book plus sleeve is below the book's alone |
| `NO-TAIL-LINK` | Neither |

If the book loses in fewer than 2 covered windows, the window clause cannot be met. Then `DIVERSIFIES` or `NO-TAIL-LINK` decides alone, and the report says so.

Each contested choice prints both ways, and each secondary line prints its own token with no verdict standing.

| Choice | Default | Printed beside it |
|---|---|---|
| Fill | mid | natural |
| Condor short delta | 0.16 | 0.30 |
| Book | deployed, gross | stored, net |
| T1 and T3 block length | 10 | 5, 20 |

The GLD condor and v3 also print their own tokens. No configuration is picked from this grid, so no PBO read applies.

## What could ship

Nothing ships whatever it prints. A `DIVERSIFIES` token would earn a new registration with a sizing and an exit rule, not a deployment.

## What this study cannot tell you

- Whether short index volatility pays on its own. The premium is context, not graded.
- Whether any management rule helps. Both arms hold to expiry.
- Anything about W1. No book covers it, and the beta proxy carries no verdict.
- Anything from the straddle. It has no max loss and no part in the verdict.
