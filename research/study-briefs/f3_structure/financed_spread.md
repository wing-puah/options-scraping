# financed_spread — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f3_structure/financed_spread.md); where the two differ, the registration wins.
> Latest outcome: PRIMARY v3 — `F4-d20 hold` `CANDIDATE`, the other 12 cells `NULL`, awaiting an independent window (2026-08-19). On v4: all 13 cells `NULL` (2026-09-28) · [record](../../study-results/f3_structure/financed_spread.md).
> Nothing else here is a result.

## The question

Holding the signal, entry day and exit rules fixed, does wrapping a debit vertical in a financing credit position improve the outcome? The operator's idea is to sell premium against the debit and cheapen the entry. This is a structure question: same signal, same dates, same exits, different wrapper.

## What it compares

The studied rows are two-leg, single-expiry debit verticals. For a bull call debit, the table mirrors for a bear put. Strikes come from the ticker's observed cached ladder only.

| Cell | What it adds | Risk |
|---|---|---|
| [financed_spread F0](../../arm-index.md#financed_spread) own | A same-direction credit at the debit's own two strikes. The machinery pilot, run first | defined |
| `financed_spread F1` | An opposite-delta credit spread at the next two cached strikes beyond the outer strike | defined |
| `financed_spread F2` | A naked short leg at the first cached strike beyond the outer strike | unbounded |
| `financed_spread F3` | A same-direction credit spread on the other side of spot | defined |
| `financed_spread F4` | A short-dated, delta-targeted naked short leg, sold once at entry, never rolled | unbounded |

`F1`, `F2` and `F3` each run at strike offset 1 (the nearest cached strike beyond) and offset 2 (one further). No third offset exists. `F0` has one cell, because its offset axis is degenerate.

`F4` was registered after the `F0`–`F3` run. Its short leg expires at the nearest cached expiry that is at least 7 calendar days out and at most half the debit's DTE. Its target is |Δ| ∈ {0.10, 0.20} (`F4-d10`, `F4-d20`). A row with no such expiry, or whose closest candidate is off target by more than 0.10 in |Δ|, is excluded and counted.

`F4` runs three management bases, giving 6 cells.

- `mgmt-pt50`: buy back at the first session whose mark is at most 0.5 × entry credit.
- `mgmt-$100`: buy back when (credit − mark) × 100 × contracts reaches $100.
- `hold`: no early buyback. It attributes any effect to the rule versus the structure.

Both management bases also stop at a mark of at least 2 × entry credit. A leg still open at its near expiry is bought back at its last real mark, never at zero.

## How it is judged

**Population.** PRIMARY is `--era v3`, 118 dates, the proxy calibration gate on, no Black-Scholes rows. The `current` (v4) era is reported and carries nothing. Eras are never pooled.

**Sizing and exits.** Sizing follows the production formula per variant. A `--fixed-contracts` control prints alongside. Exits follow the sign of the synthetic net entry: debit-signed uses the shipped debit profile, credit-signed uses `CREDIT_PROD`. A synthetic with an absolute net entry under 0.10 is excluded and counted.

**Metric.** Within-row paired [ΔR](../../glossary.md#r), financed minus baseline, aggregated by date with a paired date-clustered bootstrap (`BOOT_N = 10000`). Dollars are never quoted on a substitution.

**Exposure reads.** Three reads print beside ΔR for every shape.

- `E1`: Δ(net delta) at entry. `F1` must reduce the absolute net delta, and `F0`, `F3` must increase it. `F4` must reduce it. A shape that fails its geometry is a build bug and fails the run.
- `E2`: Δ(net vega).
- `E3`: date-level correlation of the shape's mean R with the deployed top-3 sleeve, per year, with at least 8 shared dates. A positive correlation is a `RE-WRAP`, whatever the ΔR.

**Gates.** Each gate exits non-zero on failure, in this order.

- `G0`: a cell under 25 dates or under 60 rows is power-stopped.
- `G1`: `reconstructs()` on every candidate row. Failures are excluded and counted by reason.
- `G2`: clamp attribution. `F2` must be unclamped on the naked-short-call subset. `F0`, `F1` and `F3` must be about 100% clamped. `F4` is unclamped while the short leg lives.
- `G3`: contract-count census per shape.

**Bar for a candidate.** A shape must clear all seven clauses.

1. Paired ΔR > 0, with the CI excluding zero.
2. Every leave-one-date-out fold is positive.
3. The shape survives `window_cuts` and the hand-added cut that drops both dominant windows.
4. The shape is positive in every calendar year present.
5. The shape is right-signed on both pricing tiers, real and tweak.
6. The shape has at least 25 affected dates.
7. `E3` ≤ 0.

Worst-decile cells print descriptively, marked NOT A CRITERION.

## Possible verdicts

| Token | What it means |
|---|---|
| `CANDIDATE` | A shape clears all seven clauses. Queued for an independent-window confirmation |
| `RE-WRAP` | Clears clauses 1–6 and fails clause 7. The financing does not diversify. Thread closed for these dates |
| `NULL` | Clears the CI but fails LOO, the ex-both cut or sign stability. A window artifact |
| `POWER-STOPPED` | `G0` fails after the scrape. Census only |

## What could ship

Nothing ships from a research-tier study. A `CANDIDATE` queues an independent-window confirmation first.

## What this study cannot tell you

- Whether a rolling financing campaign works. `F4` sells once and does not roll.
- Anything about selection or sizing. Both are pinned.
- Anything from the v4 era, which carries nothing.
- Anything about dollars across shapes, because contract counts differ by construction.
- Anything about multi-expiry or three-leg rows. The study uses two-leg single-expiry debit verticals only.
