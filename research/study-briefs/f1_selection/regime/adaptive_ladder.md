# adaptive_ladder — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../../pre-registrations/f1_selection/regime/adaptive_ladder.md); where the two differ, the registration wins.
> Latest outcome: forward `STILL-OPEN` (in-sample walk-forward `ADAPTS`) — 2026-10-12 · [record](../../../study-results/f1_selection/regime/adaptive_ladder.md).
> Nothing else here is a result.

## The question

Does a fixed procedure that re-picks a selection rule from trailing results beat the shipped ladder? The operator wants the deploy rule to adapt to current conditions. With a short book, the procedure itself becomes the strategy. A small fixed menu of rules is re-picked from past results only.

## What it compares

The registration was accepted by default on 2026-10-12. Contested choices are parameters printed both ways, and only the default adapter is graded.

Six rules form the menu. Each picks up to 3 positions per signal date, and tiers come from `mapping.ladder_tier`.

| Object | What it deploys | Kind |
|---|---|---|
| `adaptive_ladder M0` | Tier A/B, A first, `score_total` descending: the shipped card | arm, baseline |
| `adaptive_ladder M1` | Tier A/B, A first, `score_total` ascending | arm |
| `adaptive_ladder M2` | Tier A/B, A first, random order within tier, as an exact expected value | arm |
| `adaptive_ladder M3` | `M1` on dip dates only; nothing on other dates | arm |
| `adaptive_ladder M4` | `M1`, but Tier A only on above dates | arm |
| `adaptive_ladder M5` | Non-veto bull_call_spreads, tier-blind, `score_total` ascending | arm |

`M1`, `M3`, `M4` and `M5` were built from the 2026-10-12 exploratory read of these same v4 dates. The menu was chosen with hindsight. Only the forward read is clean.

The adapter's default settings:

- Rebalance on the first signal date of each calendar month.
- Trailing window: positions whose outcome was known in the last 120 calendar days.
- A challenger needs at least 20 positions (summed weight) and a 95% lower bound above the incumbent's trailing mean.
- Among qualifying challengers, the highest trailing mean wins. Ties go to menu order.
- Start on `M0`. An incumbent with no known trailing position scores 0.
- Signal dates before the first day of the seventh calendar month are not graded.

The 12 grid configurations print beside the default. The weekly rebalance, the 60-day and expanding windows, and the plain-mean margin are among them. Only the default is graded.

A position's outcome is known at the close of its exit session. On a rebalance date it enters the trailing score only if its known date is strictly before that date. An `open_at_data_end` row is never known, but it counts in the graded book at its stored mark.

## How it is judged

**Measure.** Per date, [slot R](../../../glossary.md#slot-r): summed R of the date's picks divided by 3. An empty slot or a sat-out date earns 0. The graded statistic is the mean over graded dates of adapter minus `M0`.

**Interval.** The 95% [CI](../../../glossary.md#ci) resamples calendar-month blocks, 10,000 draws, seed 20260811.

**Population.** v4 loader defaults through `dip_buy`'s preparation: non-veto rows with a stored R, a trusted fill and a dip label. v4 R is net of `cost_total`. v3 carries no cost columns, so v3 R is gross.

| Read | Dates | Status |
|---|---|---|
| Walk-forward | v4 signal dates after warm-up and before `era.SEAL_START` | graded |
| Replication | the same procedure on v3 | descriptive |
| Stress re-cut | graded dates outside Mar–Apr 2025 and Feb–Apr 2026 | descriptive |
| Per year | graded dates by calendar year | descriptive |
| Forward | v4 signal dates on or after `era.SEAL_START` | graded once the floors are met |

**Gates.** The forward floors are 30 signal dates and 60 `M0` positions.

**Printed beside it, never graded.** Positions, pooled meanR, total R and max drawdown per book. Switches and time in each rule. The `ORACLE`, the static rule with the best per-date R in hindsight, is an upper bound and never a candidate. A [PBO](../../../arm-index.md#pbo_ledger) CSCV read runs over 18 configurations (six static rules, 12 adapter configurations), S = 16.

**Bar.** The CI on adapter − `M0` excludes 0 and decides the sign.

## Possible verdicts

| Token | What it means |
|---|---|
| `ADAPTS` | CI on adapter − `M0` excludes 0, positive |
| `HURTS` | CI excludes 0, negative |
| `NULL` | CI spans 0 |
| `STILL-OPEN` | Forward only: fewer than 30 forward signal dates or 60 `M0` positions |

The forward verdict of record is the first run that prints a token other than `STILL-OPEN`.

## What could ship

Nothing ships from this study. A walk-forward or forward `ADAPTS` lets the operator consider a deployment-rules change, which needs its own registration and rollback trigger. `NULL` or `HURTS` closes the lead for this menu.

## What this study cannot tell you

- Whether the menu is right. A rule added after a result needs a new registration.
- Anything clean from the in-sample dates. The menu was chosen with hindsight.
- Anything about exits. Exits are the stored ones.
- Whether any grid configuration beats the default. Only the default is graded.
