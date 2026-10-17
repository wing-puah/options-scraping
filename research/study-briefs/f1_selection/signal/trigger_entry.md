# trigger_entry — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/signal/trigger_entry.md); where the two differ, the registration wins.
> Latest outcome: `ARM T` `LATE-ENTRY` at N=1, N=3 and N=5 — 2026-09-28 · [record](../../../study-results/f1_selection/signal/trigger_entry.md).
> Nothing else here is a result.

## The question

Does entering a play only when its stated trigger level is first crossed, at that session's close, beat the unconditional next-open entry once the entry price pays for the confirmation? Production ignores the model's trigger and fills every non-vetoed play at the next open. An earlier study, `exit_from_text` ARM E2, kept the next-open price, so the favourable move that met the trigger sat inside the entered number. Nobody had tested entering at the trigger and paying for it.

## What it compares

The exit profiles, sizing formula, structure universe and candidate set are frozen. Only whether and when a play opens moves. Every arm replays the shipped per-row profile through the frozen `lib/harness.replay`. The rule is close-only. No intraday-touch rule is registered.

| Object | What it does | Kind |
|---|---|---|
| [trigger_entry ARM T](../../../arm-index.md#trigger_entry) | Enters at the close of the first session k ∈ [1..N] whose underlying close crosses the stated level, inclusive. Re-priced and re-sized. No crossing within N is NOT ENTERED. N ∈ {1, 3, 5} | arm, headline |
| `trigger_entry ARM L` | Fills every in-scope row at a fixed session k ∈ {1, 3}, with no trigger gate | control |
| `trigger_entry ARM C` | ARM T's ΔR stratified by day-0 conformity band, using `next_day_move.DAY0_PNL_BANDS` and `MIN_CELL_N = 20` | control |
| `trigger_entry ARM D` | Shipped top-3/day ladder run twice: shipped picks at shipped pricing, and with NOT-ENTERED rows ineligible so the slot frees to the next-ranked play | deployment read |

ARM L separates timing from selection. A ΔR that ARM L reproduces is a lag finding, not a trigger finding. A band thinner than `MIN_CELL_N` prints its n and is not read. Rows the trigger cannot be read on stay eligible at shipped pricing in both ARM D books.

## How it is judged

**Population.** Primary era v4, secondary `--era v3` with identical thresholds, never pooled. Real and `strike_expiry_tweak` rows only. The `exit_from_text` calibration gate runs first, by import: only rows whose shipped replay reproduces are admitted. A row is in scope when its trigger parses to a numeric level and a direction, underlying bars exist, and the entry day resolves. Exclusion buckets print with n and share.

**Measure.** Paired-by-date ΔR on the entered rows: trigger-priced against the same rows' shipped replay. The CI is date-clustered, `BOOT_N = 10000`, α = .05. R only. No dollar figure is quoted across arms, because contracts are re-sized. An E2-shape census prints beside it, marked not a criterion.

**Gates.** Each blocks everything below it.

- `G0`: at least 25 affected dates and 60 affected rows per cell, else `UNDERPOWERED`.
- `G1`: parse census, with every exclusion bucket, the conditional-trigger count and the bar-source split.
- `G2`: `synth_trade(rec, 0)` must reproduce the stored trade, and a construction failure fails the run. A row with no usable day-0 mark is a counted exclusion.
- `G3`: every out-of-scope row must replay byte-identical to its shipped replay. One changed row fails the run.
- `G4`: sizing census, with the no-dollar statement beside it.
- `G5`: deadline diagnostic, printed and not a second grid.

**Bar.** All eight, for each ARM T cell.

1. The paired date-clustered CI excludes zero.
2. Every leave-one-date-out fold is on the point estimate's side.
3. It survives `protocol.window_cuts` and an ex-BOTH cut added by hand.
4. The sign is stable per calendar year.
5. It is right-signed on the pricing tiers present in the cell.
6. The floor holds on the evaluated set (25 dates, 60 rows).
7. No sign flip across N ∈ {1, 3, 5}.
8. The ΔR is right-signed in every conformity band holding at least `MIN_CELL_N` entered rows. If no band clears `MIN_CELL_N`, clause 8 fails.

**L-SEP.** ARM T separates from ARM L when its ΔR exceeds ARM L's at the matched k and ARM L's own ΔR does not clear clause 1 in that direction. The matched k is min(N, 3).

## Possible verdicts

Evaluated in this order. The first match wins. The criteria vector prints under every verdict.

| Token | What it means |
|---|---|
| `UNDERPOWERED` | A floor was not met. Nothing is read |
| `LATE-ENTRY` | ΔR ≤ 0 and the E2-shape census reproduces at shipped pricing: the signal works, but the confirmed entry comes after the move it selects on |
| `CONTRARY` | Clause 1 holds with ΔR < 0 and the census does not reproduce: the trigger misleads |
| `CONFOUND-EXPLAINED` | ΔR > 0, clauses 1–7 hold, clause 8 fails: the gain is the day-0 move |
| `LAG-EXPLAINED` | ΔR > 0, all eight hold, L-SEP fails: ARM L reproduces the effect without a gate |
| `CANDIDATE` | All eight hold and L-SEP holds. An intake proposal, never an exit rule |
| `NULL` | Powered, and nothing above matched |

ARM L, ARM C and ARM D carry no verdict word. The E2-shape census carries none either.

## What could ship

Nothing ships from this study. A `CANDIDATE` becomes a written intake proposal with its own rollback trigger and an independent-window confirmation before it may reach `docs/deployment-rules.md`. `LATE-ENTRY` closes `exit_from_text` ARM E2 as a shippable intake rule.

## What this study cannot tell you

- Anything about exits. No arm changes an exit rule.
- Whether an intraday touch would work. This book cannot replay one.
- Anything by structure or `mech_cell`. Those crosses are not registered and underpower on this book.
- Whether the day-0 move works as a rule. `next_day_move` ARM C owns it, and here it is only a control.
- Anything from v3 on its own.
