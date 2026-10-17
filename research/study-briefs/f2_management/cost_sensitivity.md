# cost_sensitivity — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f2_management/cost_sensitivity.md); where the two differ, the registration wins.
> Latest outcome: Tier A `VANISHES` and Tier B `VANISHES`, on the headline line and on the declared secondary line; the sweep was graded (G4 PASS) (v4 era) — 2026-10-09 · [record](../../study-results/f2_management/cost_sensitivity.md).
> Nothing else here is a result.

## The question

Does the deployed edge survive realistic trading costs, and at what cost level does it stop being an edge?

The shipped rules rest on gains of +0.02 to +0.04 [R](../../glossary.md#r), about the size of a two-leg round trip. So the study asks whether anything is left.

It asks two things, in order.

1. **The registered point.** At $0.65 per contract and no slippage, do Tier A and Tier B each still show [meanR](../../glossary.md#meanr) above zero, with a date-clustered [CI](../../glossary.md#ci) excluding zero?
2. **The contour.** Across a declared sweep of [cost points](../../glossary.md#cost-point), where does each tier's CI lower bound cross zero?

## What it compares

Every arm starts from gross R and charges its own cost. Stored v4 R is already net of the commission. The study rebuilds gross R as stored R plus `cost_total`, divided by the entry cost basis. Labels are `cost_sensitivity ARM X` and so on ([index](../../arm-index.md#cost_sensitivity)).

| Object | What it does | Kind |
|---|---|---|
| `cost_sensitivity ARM Z` | The book with no cost charged. Never quoted as a result | control |
| `cost_sensitivity ARM X` | $0.65 per contract, per leg, per side, no slippage. Every criterion is graded on this arm alone | PRIMARY |
| `cost_sensitivity ARM SW` | Commission {$0.00, $0.65, $1.00, $1.50} × slippage {0.00, 0.25, 0.50, 1.00} of the quoted spread per leg per side | sensitivity |
| `cost_sensitivity ARM Q` | Census of legs with a missing or degenerate quote, and a three-step fallback ladder | census |
| `cost_sensitivity ARM GAP` | Charges one extra adverse tick at exit on six threshold-triggered exit reasons | sensitivity |

`ARM SW` may never produce a verdict, a shipped rule or a recommended cost level. Two of its cells are the other arms: the zero-cost cell is `ARM Z`, and the registered-point cell is `ARM X`.

`ARM Q` fallback ladder, in order:

1. The same contract's median quoted spread over its own priced path.
2. The median quoted spread of the same ticker's other legs on the same date.
3. Otherwise the position is UNCOSTABLE and excluded, never charged zero.

`ARM GAP` applies to `profit_target`, `trailing_stop`, `underlying_stop`, `dollar_stop`, `be_stop` and `stop_loss`. The tick is $0.05 per leg as the headline and $0.01 as the declared secondary. `time_exit`, `expired` and `cap_open` get no tick.

An expired or assigned leg is charged at entry only. Rows still open at the data end (`cap_open`) are charged at both sides.

## How it is judged

**Measure.** [Net R](../../glossary.md#net-r) per tier: meanR with a 95% date-clustered CI, and net [PF](../../glossary.md#pf) with its own CI. [E](../../glossary.md#e) is never a criterion. The contour is the lowest implied dollars per leg per side at which a tier's CI lower bound is ≤ 0.

**Population.** `load_book()` through the era loader, `include_bs=False`. The v4 era is PRIMARY, and v3 is the era-stability read. The deployed set is the top-3-per-day ladder pick, read as Tier A and Tier B separately, never pooled. Sealed dates are excluded while the seal stands; see [`holdout_seal`](../../pre-registrations/f4_deployment/holdout_seal.md).

**Gates.** Each gate refuses with a non-zero exit, except G4.

- `G1` era identity: the header names the era and export fingerprint.
- `G2` cost is charged twice, never once: charge counts are recomputed independently and must match.
- `G3` grid fix present: an export produced before the B2 pre-fill grid fix is refused. The report prints that refusal in place of v3 numbers.
- `G4` quote provenance: VERDICT-PRODUCING, not a refusal. An `ARM SW` cell with slippage above 0 fails if more than 25% of its charged legs use fallback 2 or are UNCOSTABLE. Then the run prints the census, grades nothing in the sweep and records `UNCOSTABLE`.
- `G5`: no annualised figure, Sharpe or time-to-recover.
- `G6`: every printed count is computed from the run.
- `G7`: no `bs_options_hist` row in any figure.

**Bar.** C1 and C2 are the pass rule, graded on `ARM X`. C3 and C4 can only downgrade.

1. `C0` power floor: a tier needs at least 25 dates and 40 deployed positions, or it prints `UNDERPOWERED` with no outcome number.
2. `C1`: Tier A net meanR > 0 with the CI excluding zero.
3. `C2`: the same for Tier B.
4. `C3` leave-one-out: every leave-one-date-out fold and every leave-one-ticker-out fold keeps the tier's net meanR above zero.
5. `C4` era stability: C1 and C2 hold on both eras with the same sign.

C4 cannot be graded while G3 refuses the v3 export. Whether an ungraded C4 blocks `SURVIVES` is contested, so both lines print.

| Line | Ungraded C4 counts as | Best verdict possible |
|---|---|---|
| Headline | not holding | `FRAGILE` |
| Declared secondary | dropped from the verdict | `SURVIVES` |

## Possible verdicts

Each tier gets its own verdict. There is no combined token.

| Token | What it means |
|---|---|
| `SURVIVES` | C1 and C2 hold, and C3 and C4 hold. The queue proceeds |
| `FRAGILE` | C1 and C2 hold, but C3 or C4 fails. Shipped rules with a delta below the modelled cost are flagged as unmeasured net of cost |
| `VANISHES` | C1 or C2 fails. That tier has no measured edge net of costs, and exit tuning on it stops |
| `UNDERPOWERED` | A tier misses C0. The other tier is still graded |
| `UNCOSTABLE` | G4 fails. It belongs to the sweep, not to the tiers |

If `ARM X` gives `VANISHES` and a cheaper `ARM SW` cell gives `SURVIVES`, the verdict stays `VANISHES`.

## What could ship

Nothing ships under any outcome. The outputs are a verdict per tier, a recorded contour, and a flag on shipped rules whose deltas are smaller than the modelled cost.

## What this study cannot tell you

- What the operator actually paid. It models cost from quoted spreads. Live fills need the journal.
- Whether orders fill. Partial fills, unfilled legs and queue position are out of scope.
- Whether a different cost level would change which exit fired. It re-prices the same exits.
- Anything about the v3 era today. G3 refuses it.
