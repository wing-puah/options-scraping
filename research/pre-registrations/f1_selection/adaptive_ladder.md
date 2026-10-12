## adaptive_ladder — does re-choosing the selection rule from trailing results beat the shipped ladder?

_Registered 2026-10-12._

**STATUS: ACCEPTED BY DEFAULT 2026-10-12 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Contested choices are parameters printed both
ways; only the default adapter is graded.

**What this file says, in one paragraph.** The operator wants the deploy rule
to adapt to current conditions. With a short book the honest way is to make
the adaptation procedure itself the strategy: a small fixed menu of selection
rules, and a fixed procedure that re-picks one of them from trailing realized
results. Every decision on a date uses only positions whose outcome was known
before it. The procedure is graded walk-forward on the v4 dates before the
holdout seal, and again on forward dates once the seal lifts.

## Question

Does the default adapter's book earn more R per signal date than the shipped
ladder (`M0`), net of cost, on dates it did not use to choose?

## What this is NOT

- **Not a clean out-of-sample test on the in-sample dates.** Four menu rules
  (`M1`, `M3`, `M4`, `M5`) were built from the 2026-10-12 exploratory read of
  these same v4 dates ([`current.md`](../../current.md)). The walk-forward
  stops the adapter from seeing the future, but the menu was chosen with
  hindsight. The forward read is the clean one.
- **Not a new tier rule.** Every rule tiers with
  `scripts/journal/lib/mapping.py::ladder_tier`, via `dip_buy.tier_of`, and
  never re-implements [§1–§3](../../../docs/deployment-rules.md#s1).
- **Not an exit study.** Exits are the stored ones.
- **Not a ship.** An `ADAPTS` lets the operator consider a deployment-rules
  change, which would need its own registration and rollback trigger.
- **Not a named sealed reader.** The [holdout seal](../f4_deployment/holdout_seal.md)
  closed its list on 2026-10-09; the forward read waits for the unseal.

## Population and basis

- **Loader.** `load_book()` at its defaults, through
  [`dip_buy`](dip_buy.md)'s preparation: non-veto rows with a stored R, a
  trusted fill and a [dip label](../../glossary.md#dip-date).
- **Outcome.** The stored [R](../../glossary.md#r), net of `cost_total` on
  v4. v3 carries no cost columns, so v3 R is gross.
- **Known date.** A position's outcome is known at the close of its exit
  session, `t.grid[days_held - 1]` (a deferred fill is already inside
  `days_held`). A row marked `open_at_data_end` is never known; it still
  counts in the graded book at its stored mark.
- **No lookahead.** On a rebalance date `Rb` a position enters a trailing
  score only when its known date is strictly before `Rb`. Overlapping holds
  therefore never leak.

## The menu

Six rules, fixed now. Each picks up to 3 positions per signal date.

| Rule | What it deploys |
|---|---|
| `M0` | Tier A/B, A first, `score_total` descending: the shipped card |
| `M1` | Tier A/B, A first, `score_total` ascending |
| `M2` | Tier A/B, A first, random order within tier, as an exact expected value |
| `M3` | `M1` on dip dates only; nothing on other dates |
| `M4` | `M1`, but on above dates Tier A only |
| `M5` | Non-veto bull_call_spreads, tier-blind, `score_total` ascending |

- A row with no score sorts after the scored rows of its tier, either order
  (`dip_buy.rank_key`).
- `M2` gives each row its pick probability: a tier with more rows than the
  remaining slots splits those slots evenly. The book is then a weighted list,
  so no seed is needed.
- The dip flag is `MechLabeler.below_sma`, as in `dip_buy`.

## The adapter

| Choice | Default | Printed as a parameter |
|---|---|---|
| Rebalance | The first signal date of each calendar month | First signal date of each ISO week |
| Trailing window | Positions known in the last 120 calendar days | 60 days; expanding |
| Score | Weighted [meanR](../../glossary.md#meanr) and a 95% lower bound, standard error clustered on signal date | — |
| Switch margin | A challenger's lower bound beats the incumbent's trailing mean | Its plain mean beats it |
| Minimum trailing n | 20 positions (summed weight) | — |
| Start | `M0` | — |
| Warm-up | Signal dates before the first day of the seventh calendar month are not graded | — |

- **Switching.** Among challengers past the minimum n and the margin, the one
  with the highest trailing mean wins. Ties go to menu order.
- **An empty incumbent.** An incumbent with no known trailing position scores
  0, the value of cash.
- The 12 grid configurations are printed beside the default. Only the default
  is graded.

## Unit and metric

- **Per date.** R per budget slot: the summed R of the date's picks divided by
  3. An empty slot or a sat-out date earns 0. This is the only per-date figure
  defined on a date a gated rule sits out.
- **Graded statistic.** The mean over graded dates of adapter minus `M0`.
- **[CI](../../glossary.md#ci).** 95%, calendar-month blocks resampled with
  replacement, 10,000 draws, seed 20260811. Months are the blocks because
  adjacent dates share holds and the default rebalances monthly.
- **Beside it.** Per book: positions, pooled meanR, total R, and max drawdown
  of the cumulative per-date total R. Switches, and time in each rule.
- **Oracle.** The static rule with the best per-date R on the graded dates,
  labelled hindsight. It is an upper bound, never a candidate.

## Populations graded

| Read | Dates | Status |
|---|---|---|
| Walk-forward | v4 signal dates after warm-up and before `era.SEAL_START` | Graded |
| Replication | The same procedure on v3 | Descriptive |
| Stress re-cut | Graded dates outside Mar–Apr 2025 and Feb–Apr 2026 | Descriptive |
| Per year | Graded dates by calendar year | Descriptive |
| Forward | v4 signal dates on or after `era.SEAL_START` | Graded once the floors are met |

The adapter runs over every date in each era; a cut only drops dates from the
statistics.

## Verdicts, worded now

| Token | When |
|---|---|
| `ADAPTS` | CI on adapter − `M0` excludes 0, positive |
| `HURTS` | CI excludes 0, negative |
| `NULL` | CI spans 0 |
| `STILL-OPEN` | Forward only: fewer than 30 forward signal dates or 60 `M0` positions |

**Forward floors.** 30 signal dates and 60 positions, the floor
[`dip_buy`](dip_buy.md) registered for one arm, applied here to the paired
stream. At 30 dates expect a CI near ±0.05 R per date, wider than the
in-sample walk-forward's. The forward verdict of record is the first run that
prints a token other than `STILL-OPEN`.

## PBO

[`lib/pbo.py`](../../arm-index.md#pbo_ledger) CSCV over 18 configurations:
the six static rules and the 12 adapter configurations. Rows are the graded
dates, the metric is summed per-date R, S = 16. The earliest dates are trimmed
until 16 divides the count. Printed, never graded.

## Anti-tuning

- The menu, the grid, the margin, the minimum n, the warm-up, the block
  bootstrap and the seed are fixed here.
- No rule joins the menu after a result. A new rule is a new registration.
- The tables print as they fall.

## Ship criteria

Nothing ships from this study. A walk-forward or forward `ADAPTS` lets the
operator consider a deployment-rules change. `NULL` or `HURTS` closes the
lead for this menu.

## Build notes

Not part of the registration.

- Module: `scripts/backtest_study/f1_selection/adaptive_ladder.py`. Run with
  `python -m scripts.backtest_study run adaptive_ladder`. The report is
  `backtests/study_output/adaptive_ladder-latest.txt`.
- `Resolved at build (2026-10-12)`: the request named the defaults; the code
  fixed five readings of them before the first run. Per-date R is per budget
  slot. The CI blocks are calendar months. The lower bound uses a
  date-clustered standard error, not a bootstrap, so a weekly rebalance stays
  cheap. An empty incumbent scores 0. The known date is the exit session. No
  parameter moved after that run.
- Tests: `tests/test_adaptive_ladder.py` pins the no-lookahead rule, the
  margin, the warm-up, the verdict grammar and the menu gating on synthetic
  data.
