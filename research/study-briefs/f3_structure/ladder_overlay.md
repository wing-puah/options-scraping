# ladder_overlay — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f3_structure/ladder_overlay.md); where the two differ, the registration wins.
> Latest outcome: all cells `NULL` — 2026-09-28. Selling the call at entry loses with the CI clear of zero (`L-F4`, `L-T0`, `L-T0-TEF`); the trigger and naked-put cells are indistinguishable from zero · [record](../../study-results/f3_structure/ladder_overlay.md).
> Nothing else here is a result.

## The question

Holding the signal, entry day and core position fixed, does a shorter-dated short call sold against a long-dated bull call spread beat running the spread to the shipped [§5](../../../docs/deployment-rules.md#s5) exits? The short call rolls as each one expires. The operator's real trades are mostly this shape.

Four questions, in order of importance:

1. Is the ladder profitable versus closing the core at the shipped §5 exits?
2. When should the call be sold: at entry, on a gap-up, on a sustained rise, or never? Does holding the core longer beat the profit target?
3. How does the answer behave under a fixed-volatility scenario and across regime cuts?
4. Would a naked short put in place of the core have yielded more?

This is the roll registration that `financed_spread` deferred. It does not reopen `F0`–`F3`.

## What it compares

The core is a two-leg, single-expiry `bull_call_spread` row. Every cell runs at the baseline core's production contract count, with a 1:1 overlay ratio and at most one live tranche. All PRIMARY call cells use |Δ| 0.20 and `BHOLD` (do nothing on breach).

| Object | What it does | Kind |
|---|---|---|
| [ladder_overlay L-BASE](../../arm-index.md#ladder_overlay) | Core alone, run to §5 exits (`TNEVER`, `X-SHIP`) | baseline, never a candidate |
| ladder_overlay L-F4 | One tranche sold at entry, never rolled (`T0`, `R0`). Reproduces `financed_spread` ARM F4-d20-hold | `G1b` anchor, never a candidate |
| ladder_overlay L-T0 | Sells at entry, rolls each slot (`T0`, `R1`) | PRIMARY |
| ladder_overlay L-GAP | Sells after a gap-up, rolls (`TGAP`, `R1`) | PRIMARY |
| ladder_overlay L-RUN | Sells after a sustained rise, rolls (`TRUN`, `R1`) | PRIMARY |
| `L-T0-TEF`, `L-GAP-TEF`, `L-RUN-TEF` | The three trigger cells with the profit target dropped (`X-TEF`) | PRIMARY |
| ladder_overlay N-CORE | Replaces the core with a short put at the core's long strike and expiry | PRIMARY (naked put) |
| ladder_overlay N-ROLL | Replaces the core with a rolled short put, |Δ| 0.30 | PRIMARY (naked put) |

Trigger definitions, frozen:

- `T0`: sell on the core's entry day.
- `TGAP`: the session whose open is at least 1.015 × the prior close.
- `TRUN`: the session whose close is at least 1.04 × the entry-day close and is the third of 3 consecutive higher closes.
- `TNEVER`: no tranche.

`TGAP` and `TRUN` fire at most once per empty slot. The tranche sells on the next grid day, never on the trigger session.

Nine SENSITIVITY cells print (seven rows; the `[MODEL]` row runs at three IV scales) with n and are never a criterion. They vary delta, breach policy, hold period, trigger level, DTE floor and a `[MODEL]` tier. The [registration](../../pre-registrations/f3_structure/ladder_overlay.md#sensitivity) lists each cell.

## How it is judged

**Population.** PRIMARY is era v4, real and tweak pricing tiers carried separately, no Black-Scholes rows. A `--era v3` companion run carries nothing. Eras are never pooled. A core over 120 days is truncated at the path cap.

**Metric.** Within-row paired [ΔR](../../glossary.md#r), cell minus `L-BASE`, aggregated by date with a paired date-clustered bootstrap (`BOOT_N = 10000`). The R denominator is the core debit. For the naked-put cells it is the core's max-loss dollars. Dollars are never quoted on a substitution.

**Costs and settlement.** Commission and slippage are charged on every tranche open and close, and a criterion is read net. Settlement rules are in the [registration](../../pre-registrations/f3_structure/ladder_overlay.md#pricing-sizing-exits--pinned).

**Gates.** Each gate exits non-zero on failure, in this order.

- `G0`: under 25 dates or under 60 rows is `UNDERPOWERED`. It is re-applied inside every regime cut.
- `G1`: `reconstructs()` on every candidate core.
- `G1b`: `L-F4`'s per-day mark series must equal `financed_spread` F4-d20-hold's to $0.01 per day on the shared rows.
- `G2`: every ladder cell is 100% unclamped on days with a live tranche.
- `G3`: sizing census, plus a margin proxy for the naked-put cells. No criterion reads it.
- `G4`: breach census. Clause 8 is read against it.
- `E1`, `E2`, `E3`: exposure reads.

`E1` needs net delta to go more negative. A trigger cell is gated at its first sale day. The naked-put cells print `E1` and `E2` and are not gated. `E3` needs at least 8 shared dates, or it is NOT EVALUABLE and the cell cannot be a `CANDIDATE`.

**Bar for a candidate.** A cell must clear all eight clauses.

1. Paired ΔR > 0, with the CI excluding zero.
2. Every leave-one-date-out fold is positive.
3. The cell survives `window_cuts` and the hand-added cut that drops both dominant windows.
4. The cell is positive in every calendar year present.
5. The cell is right-signed on both pricing tiers, real and tweak.
6. The cell has at least 25 affected dates.
7. `E3` ≤ 0.
8. The cell stays positive when intrinsic is paid on every breached tranche.

## Possible verdicts

| Token | What it means |
|---|---|
| `CANDIDATE` | A cell clears all eight clauses. Queued for an independent-window confirmation |
| `RE-WRAP` | Clears 1–6 and 8, fails 7. The ladder holds more of the same exposure. Thread closed for these dates |
| `NULL` | The total default: any cell that is not one of the other tokens. Includes a CI at or below zero, failed LOO, ex-both or sign stability, failed clause 5 or 6, `E3` NOT EVALUABLE, or both 7 and 8 failing |
| `UNDERPOWERED` | `G0` fails for the cell or a regime cut. Nothing concluded |
| `BREACH-DOMINATED` | Clauses 1–7 pass and clause 8 flips the sign. Recorded as its own outcome |
| `AWAITING SCRAPE` | The contracts a cell needs are not cached. The run prints the census and evaluates nothing |

There is no `CONTRARY` token. A losing cell with a CI clear of zero prints `NULL`, and the write-up states the sign in words.

## What could ship

Nothing ships. The most a cell can earn is `CANDIDATE`, which queues an independent-window confirmation. No §5 exit, deployment rule or card behaviour changes on this file's evidence.

## What this study cannot tell you

- Whether `L-GAP` or `L-RUN` work. Both triggers subset the book hard, and an `UNDERPOWERED` trigger cell says nothing about the trigger.
- The full life of a core beyond 120 days. The path cap truncates it.
- Whether `RE-WRAP` is avoidable. The registration calls it the modal expected outcome.
- The cost of early assignment, which is unmodelled. Every ladder cell's ΔR is optimistic by an unmeasured amount.
- Whether the account could carry the naked puts. The margin figure is a proxy on a proxy denominator.
