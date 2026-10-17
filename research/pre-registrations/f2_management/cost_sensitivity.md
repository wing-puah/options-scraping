## cost_sensitivity — at what cost per leg does the Tier A/B edge vanish?

<!-- outcome:start -->
> Latest outcome: Tier A `VANISHES` and Tier B `VANISHES`, on the headline line and on the declared secondary line; the sweep was graded (G4 PASS) (v4 era) — 2026-10-09 · [record](../../study-results/f2_management/cost_sensitivity.md).
<!-- outcome:end -->

_Registered 2026-10-09. Immutable in substance from that date._

**STATUS: ACCEPTED BY DEFAULT 2026-10-09 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).**

Every open point is answered beside the text it amends, tagged
**Resolved at build (2026-10-09)**. All of those defaults were fixed before the
build read any outcome column. Where a choice was genuinely contested, it is a
parameter and the report prints both: the headline, fixed here, and a declared
secondary.

## The question

Does the deployed edge survive realistic trading costs, and at what cost level
does it stop being an edge?

The shipped rules rest on gains of +0.02 to +0.04 [R](../../glossary.md#r). A
realistic round trip on a two-leg vertical is of the same order. So the question
is not "how much does cost shave off"; it is "is there anything left".

It asks two things, in order:

1. **The registered point.** At $0.65 per contract and no slippage, do Tier A
   and Tier B each still show [meanR](../../glossary.md#meanr) > 0 with a
   date-clustered [CI](../../glossary.md#ci) excluding zero?
2. **The contour.** Across a declared sweep of
   [cost points](../../glossary.md#cost-point), where does each tier's CI lower
   bound cross zero? That number answers "at what cost does the edge vanish".
   It is reported as a shape, not a menu.

When drafted (2026-09-07), no cost term existed in `scripts/backtest/`,
`scripts/backtest_study/`, `config/backtest.yml` or `config/account-sim.yml`
([robustness review B1](../../robustness-review.md#backtest)). Every queued item
assumed an edge that may be a cost artefact
([suggested order](../../robustness-review.md#order), step 2).

> **Resolved at build (2026-10-09) — the book is no longer gross.** B1 landed
> on 2026-09-08 and costs were switched on 2026-09-22. On 2026-09-24 the whole
> v4 book was re-priced at $0.65 per contract with no slippage, because the
> operator fills spreads at the mid. Every stored row now reads
> `cost_basis = commission_only`, so the stored R is already net of the `ARM X`
> commission. The study still asks the same question. It starts every arm from
> gross R and charges its own cost, as [Population and basis](#population-and-basis-fixed-here)
> says.

## What this study is not

- **Not a selection study.** The ladder is FROZEN
  ([§2](../../../docs/deployment-rules.md#s2),
  [top-k/day](../../glossary.md#top-kday)). No column is added to selection and
  no tier rule is touched.
- **Not an exit study.** The shipped exit profiles
  ([§5](../../../docs/deployment-rules.md#s5)) are frozen. The study re-prices
  the same exits; it does not re-choose them. If a cost level would have changed
  which exit fired, that is out of scope. It is stated as a limit, not modelled.
- **Not a live-slippage study.** It models cost from quoted spreads in
  `backtests/option_history_cache/`. What the operator actually paid needs the
  journal ([next-steps §2.5](../../next-steps.md#s2-5)).
- **Not a fill-probability study.** It assumes every registered order fills at
  the modelled price. Partial fills, unfilled legs and queue position are out of
  scope.

## Dependencies

Three things must land before the study is built. Run earlier, its number
only looks net-of-cost.

| Prerequisite | What it is | Why it binds |
|---|---|---|
| B1 cost knobs | `commission_per_contract` and `slippage_frac_of_spread` under `simulation:` in `config/backtest.yml`, charged at entry and exit in `scripts/backtest/simulate.py` | The study never invents its own cost path |
| B2 pre-fill grid fix | Price grid starts at the entry date, not signal date + 1 | About 4% of positions carry a pre-entry day, a P&L the position never had |
| One suite re-run | `BacktestResults` re-run once, after both fixes | Exports must post-date both; two re-runs would pool two populations |

If the export was produced before the grid fix, the study REFUSES to run (G3).

> **Resolved at build (2026-10-09) — all three have landed.** B1 and B2 merged
> together in `3e5c2dc` on 2026-09-08. The one re-run is the 2026-09-24
> whole-book re-price, the first full re-run after both fixes. The 2026-10-06
> exports post-date it.

## Population and basis, fixed here

- **Population.** `lib/book.py::load_book()`, era-scoped by `lib/era.py`,
  `include_bs=False`. Real and `strike_expiry_tweak` rows only.
  `bs_options_hist` rows are excluded everywhere and may not be re-admitted for
  any arm.
- **Era.** The current era (v4) is PRIMARY. v3 is run as the era-stability read
  and reported. The report header names the era it ran on.

  > **Resolved at build (2026-10-09).** The v3 read runs in the same process as
  > the v4 one, through the same gates. The frozen v3 export predates B1 and B2
  > and has no `cost_basis` column, so G3 refuses it. The report prints that
  > refusal in place of the v3 numbers. Its effect on C4 is under
  > [C4](#bar-for-a-candidate).
- **The date count is NOT fixed here.** The population is every signal date the
  era resolves at run time with at least one real-or-tweak row. No count is
  written into this file, and none may be written into the module
  ([standing rule](../../robustness-review.md#method), M-class; a stored
  `expected_positions` fingerprints a snapshot, not a hypothesis).
- **Deployed set.** `protocol.top_k_per_day(book, ladder_rank, k=3,
  ladder_eligible)`, the shipped card. The study never re-selects. Tier A and
  Tier B are read separately, never pooled into one "A/B" number.
- **Sealed dates are excluded, by rule.** Every signal date inside the window
  sealed by [`holdout_seal`](../f4_deployment/holdout_seal.md) is dropped from
  every arm. It is also dropped from every census count that feeds an outcome
  figure, for as long as that seal stands. The study prints per-tier net meanR
  and net PF, which the seal forbids on a sealed date. The exclusion tracks the
  seal, not a date list. If the operator declines `holdout_seal`, this clause is
  inert and the population is the whole era.

  > **Resolved at build (2026-10-09).** `holdout_seal` was accepted on
  > 2026-10-09 with the seal starting 2026-09-23. This study is not one of its
  > named readers. It reads the book only through `load_book()` without
  > `sealed_read`, which withholds every sealed row, and it opens no export
  > itself. So its population ends at 2026-09-22 until the seal lifts. The
  > report prints the loader's seal line.
- **Cost basis.** A position's cost is charged per LEG, at entry and at exit,
  in dollars per contract. It is then divided by that position's entry cost
  basis (`abs(entry_option_price) × 100`) to become a delta in R. Leg count
  comes from the `legs` column and is cross-checked against `entry_leg_detail`.

  > **Resolved at build (2026-10-09) — how the cost grid relates to the stored
  > basis.** The stored R is net of production's charge, `cost_total`: $0.65 ×
  > Σ|qty| × contracts × 2 sides on every row.
  >
  > - **Gross first.** The study rebuilds gross R as stored R plus
  >   `cost_total` / (|`entry_option_price`| × 100 × contracts). That undoes
  >   exactly what `simulate._apply_costs` subtracted. `lib/replay_basis.py`
  >   adds the cost back the same way for calibration.
  > - **Every arm charges from gross.** `ARM Z` is gross R. `ARM X` and each
  >   `ARM SW` cell charge their own cost onto gross R. `ARM X` recomputes the
  >   commission from the leg count and never reuses `cost_total`.
  > - **Where `ARM X` and the stored R differ.** Production charges an `expired`
  >   row at both sides; this registration charges it at entry only. So `ARM X`
  >   net R equals stored R on every row except `expired` ones, where it is one
  >   side's commission higher. G2 checks both statements row by row.
  > - **The config knobs name the stored basis.** The module reads
  >   `commission_per_contract` and `slippage_frac_of_spread` from
  >   `config/backtest.yml`. If `cost_total` disagrees with them, G2 refuses.
  >   `ARM X` is not taken from the config. `ARM X` and the grid are registered
  >   here, so a later config change cannot move them.
  > - **Rows still open at the data end** (`cap_open`) are charged at both
  >   sides, as production charges them. The position still has to be closed,
  >   and charging that exit is the conservative choice.
- **Quoted spread.** `Ask − Bid` from the leg's own row in
  `backtests/option_history_cache/<TICKER>_<YYYYMMDD>_<STRIKE><C|P>.csv`, on the
  entry date and on the exit date. Never interpolated across dates.

  > **Resolved at build (2026-10-09).** The entry date is the recorded fill day,
  > `legs[0].expiration − dte_entry`, read the way `lib/prefill_audit.py` reads
  > it. The exit date is the grid day at `days_held`, the day production prices
  > its exit spread. A quote is degenerate under the three tests in `ARM Q`, and
  > also under production's junk-quote rule (2026-09-24). In code, a quote is
  > usable only when `simulate._leg_spread` returns a spread above zero. Without
  > the junk rule, the sweep would charge spreads production refuses to use.
- **An expired or assigned leg is charged at entry only.** A leg that goes to
  expiry carries no exit cost. `exit_reason` `expired` decides this, not the
  price path.

## Plan-time observations, disclosed

Read on 2026-09-07 while drafting. Nothing here is a result. Each line names
what it was read from.

| Observation | Source |
|---|---|
| Zero hits for commission, slippage or fee across the backtest, the studies and both configs | grep, [robustness review B1](../../robustness-review.md#backtest) |
| Shipped rule deltas run +0.02 to +0.04 R | [robustness review, short answer](../../robustness-review.md#short-answer) |
| `bull_call_spread` carries +$79.4k against a whole book of +$12.3k | [§7.2](../../../docs/deployment-rules.md#s7-2) |
| The option history cache carries `Bid` and `Ask` columns per contract-day | cache header |
| Exits realise at the closing mark, so a gap books more than the target and less than the stop; symmetric by construction | [robustness review B4](../../robustness-review.md#backtest) |

The last line is why `ARM GAP` exists. B4's own fix note says "fold into the
cost study as a sensitivity", and this registration does that.

## What it compares

Labels are study-local: cite `cost_sensitivity ARM X`, never a bare `ARM X`
([index](../../arm-index.md#cost_sensitivity)).

| Arm | What it does | Kind |
|---|---|---|
| `ARM Z` | ZERO-COST CONTROL | reference only |
| `ARM X` | THE REGISTERED COST POINT | PRIMARY |
| `ARM SW` | THE SWEEP: commission × slippage grid | SENSITIVITY ONLY |
| `ARM Q` | QUOTE AVAILABILITY: census plus fallback ladder | census |
| `ARM GAP` | ADVERSE-FILL SENSITIVITY: one extra exit tick | sensitivity |

### ARM Z — zero-cost control

The book exactly as it prints today, with no cost charged. It carries no
verdict and is never quoted as a result of this study.

### ARM X — the registered cost point (PRIMARY)

$0.65 per contract, per leg, per side. No slippage. Every criterion below is
graded on this arm and no other.

Why no slippage: the operator fills spreads at the combo mid, on entry and on
exit. A per-leg share of the quoted spread is a cost the account does not pay.
This point was 25% of the spread until 2026-09-24. It changed AFTER the v4 book
was seen net of that 25% (−$50.2k). The reason is the operator's execution, not
that result. The 25% point stays in `ARM SW` as sensitivity.

Not covered: mid orders that never fill, and the gap between the EOD mid and
the fill-time mid. Flex records the fill price, not the quote.

### ARM SW — the sweep (SENSITIVITY ONLY)

The grid below locates each tier's breakeven contour. `ARM SW` may never
produce a verdict, a shipped rule or a recommended cost level.

| Knob | Grid |
|---|---|
| commission per contract | $0.00, $0.65, $1.00, $1.50 |
| slippage, as a fraction of the quoted spread per leg per side | 0.00, 0.25, 0.50, 1.00 |

> **Resolved at build (2026-10-09).** The ($0.00, 0.00) cell is `ARM Z` and the
> ($0.65, 0.00) cell is `ARM X`. The report prints each once and marks them in
> the grid. A cell with slippage above zero is costed only on positions whose
> every leg-side has a quote, directly or by fallback. So its position count can
> be lower than `ARM X`'s. Each cell prints its own count.

### ARM Q — quote availability

A census of legs whose entry or exit quote is missing or degenerate: `Bid` or
`Ask` absent, `Ask ≤ Bid`, or `Bid = 0`. Such a leg is charged under one
declared fallback, in this order. The fallback used is tagged and counted per
arm.

1. The same contract's median quoted spread over its own priced path.
2. Failing that, the median quoted spread of the same ticker's other legs on
   the same date.
3. Failing that, the position is UNCOSTABLE. It is excluded from every cost
   total, never charged zero.

Excluding a position is not the same as charging it nothing. The missing-greek
rule is the model: an absent quote is `None`, never `0.0`.

> **Resolved at build (2026-10-09) — what each fallback reads.**
>
> - **Fallback 1, "its own priced path"**: the contract's usable spreads on the position's grid days,
>   from the fill day through the exit day.
> - **Fallback 2, "the same ticker's other legs on the same date"**: every other leg in the costed population on the same
>   ticker, with a usable quote on that date. That includes the position's own
>   other legs and other positions' legs. It never scans the cache for contracts
>   the book did not hold.
> - A leg-side that needs fallback 1 or 2 is tagged with it. A position with
>   any uncostable leg-side is uncostable as a whole.

### ARM GAP — adverse-fill sensitivity

On rows whose exit is `profit_target`, `trailing_stop`, `underlying_stop`,
`dollar_stop`, `be_stop` or `stop_loss`, charge one additional adverse tick at
exit on top of `ARM X`.

- Those six are EVERY threshold-triggered exit the frozen harness can fire
  (`scripts/backtest_study/lib/harness.py`).
- Each realises at the close of the day its threshold is crossed. So B4's
  asymmetry applies to all six identically.
- None may be dropped for being a dollar or an underlying threshold rather than
  a percentage one.
- The remaining reasons are NOT charged the tick. `time_exit` fires on a
  calendar date. `expired` and `cap_open` end the path rather than cross a
  level, so there is nothing to fill through.

It is sensitivity only. It answers "does the close-only grid's symmetry hide the
cost result", and it carries no verdict.

> **Resolved at build (2026-10-09) — the size of a tick.** The draft did not
> say. A tick is charged per leg, per contract, at exit, × |qty|. Two sizes are
> defensible, so the report prints both as declared lines:
>
> | Line | Tick per leg | Why |
> |---|---|---|
> | Headline | $0.05 | Standard minimum increment for an option at $3 or more outside the penny program; the larger, conservative choice |
> | Declared secondary | $0.01 | Penny-program and combo-order increment |

## How it is judged

- **Unit**: a deployed position, keyed the way
  `scripts/backtest/shared/identity.py` keys it.
- **Metric**: [net R](../../glossary.md#net-r), the stored
  [R](../../glossary.md#r) minus the modelled cost, in the same units.
  [E](../../glossary.md#e) is reported alongside but is never a criterion,
  because a held-to-cap figure has no exit leg to charge.
- **Headline** per tier: net meanR with a 95% date-clustered CI
  (`protocol.boot_ci_by_date`), and net [PF](../../glossary.md#pf) with its own
  date-clustered CI.
- **Contour** per tier: the smallest cost level on the `ARM SW` grid at which
  the net meanR CI lower bound is ≤ 0. It is quoted as the pair (commission,
  slippage fraction) and as the implied dollars per leg per side.

> **Resolved at build (2026-10-09).**
>
> - **"Smallest" on a two-axis grid** means lowest implied dollars per leg per
>   side: commission + fraction × the tier's mean quoted spread × 100. The mean
>   spread is taken over the tier's leg-sides with a direct quote. For each
>   commission row, the report also prints the first slippage fraction that
>   crosses, so the shape is visible. A tier that never crosses prints "no
>   crossing on the grid".
> - **E** (`pnl_at_cap_pct`) stays gross in production. So the report prints it
>   once per tier, gross, labelled as such. It is never netted and never graded.
> - **Selection is fixed before costs.** Top-3/day runs once on the loaded book.
>   Costs change no pick.

## Gates

Each gate exits non-zero on failure and prints nothing. There is ONE exception,
declared here so it cannot be read either way after the run. **G4 is
verdict-producing, not a refusal.** If G4 fails, the run prints its census and
the UNCOSTABLE verdict, and exits zero.

- **G1 ERA IDENTITY.** The report header names the era and the export
  fingerprint. A wrong or thin era refuses (`lib/era.py`, exits 2 and 3). No
  study-local snapshot pin may dodge this.
- **G2 COST IS CHARGED TWICE, NEVER ONCE.** Every costed position is charged at
  entry and at exit, except an expired leg, which is charged at entry only. The
  run recomputes the charge count independently and FAILS on any mismatch.

  > **Resolved at build (2026-10-09).** G2 makes three checks and exits 5 on any
  > failure.
  >
  > 1. The side count from the charging code must equal a separate count read
  >    off `exit_reason`.
  > 2. The leg count from `legs` must equal the line count of
  >    `entry_leg_detail`.
  > 3. On every `commission_only` row, the stored `cost_total` must equal the
  >    config commission at both sides, within a cent. That proves the gross-R
  >    rebuild undoes what production charged.
- **G3 GRID FIX PRESENT.** If the export was produced before the B2 pre-fill
  grid fix, the run refuses. The check is on the export's own provenance, not on
  a flag the operator passes.

  > **Resolved at build (2026-10-09) — the provenance mark.** Only code that
  > carries B1 and B2 writes `cost_basis`, because both landed in one merge. If
  > the export has no `cost_basis` column, or any row in the loaded population
  > has it blank, G3 refuses. It exits 4.
- **G4 QUOTE PROVENANCE. VERDICT-PRODUCING, NOT A REFUSAL** — the one gate that
  does not exit non-zero. The fallback share is printed per arm. `ARM X` charges
  no slippage, so it reads no quote and passes G4 trivially. Any `ARM SW` cell
  with slippage above 0 FAILS G4 if more than 25% of its charged legs are priced
  from fallback 2 or are UNCOSTABLE. On failure the run prints the per-arm quote
  census, prints NO outcome number, grades no criterion, and records the verdict
  UNCOSTABLE. A refusal would print no census, and the census is the useful
  output of that failure.

  > **Resolved at build (2026-10-09) — what a G4 failure blanks.** Every
  > slippage cell reads the same quotes, so G4 passes or fails for all of them
  > at once. Its share is fallback-2 plus uncostable leg-sides over all
  > leg-sides the cells need a quote for. On failure the slippage cells print
  > the census and `UNCOSTABLE` in place of numbers. The contour then runs over
  > the commission axis only. `ARM X` reads no quote, so C0 to C4 are still
  > graded on it. `UNCOSTABLE` is then the verdict of the sweep, not of the
  > tiers.
- **G5 NO NEW STATISTIC.** No annualised figure, no Sharpe, no time-to-recover,
  per the standing research-tier rule.
- **G6 NO HARDCODED CENSUS.** Every count, share and range printed in prose is
  computed from the run. A measured quantity frozen into a string literal FAILS
  review.
- **G7 PRICING-TIER HONESTY.** Every dollar and R figure is quoted real+tweak.
  No figure may pool `bs_options_hist` rows.

## Bar for a candidate

The study ships no rule. It certifies, or refuses to certify, that the deployed
edge is net-positive. C1 and C2 are the registered pass rule and are graded on
`ARM X` alone. C3 and C4 are supporting and can only downgrade, never reverse.

0. **C0 POWER FLOOR.** A tier is read only if it has at least 25 dates and at
   least 40 deployed positions after top-3/day. Below either, that tier prints
   **UNDERPOWERED**: census only, no outcome number printed at all. The floor
   may not be lowered to make a tier readable. Given the v4 tier-mix shift
   recorded by [`v4_bridge`](../f1_selection/benchmark/v4_bridge.md), Tier A is
   expected to be the binding one.
1. **C1 TIER A NET-POSITIVE.** Tier A net meanR > 0 with its 95% date-clustered
   CI excluding zero, under `ARM X`.
2. **C2 TIER B NET-POSITIVE.** The same, for Tier B.
3. **C3 LEAVE-ONE-OUT.** Dropping any single date, and separately any single
   ticker, leaves each passing tier's net meanR positive
   ([LOO](../../glossary.md#loo)).
4. **C4 ERA STABILITY.** C1 and C2 hold on both eras with the same sign.

> **Resolved at build (2026-10-09).**
>
> - **C0** counts the tier's deployed positions under `ARM X`, which can cost
>   every position.
> - **C3** passes when every leave-one-date-out fold and every
>   leave-one-ticker-out fold keeps that tier's `ARM X` net meanR above zero.
> - **C4 cannot be graded today.** G3 refuses the v3 export (see
>   [Era](#population-and-basis-fixed-here)). Whether an ungraded C4 blocks SURVIVES is
>   contested. The wording says SURVIVES needs C4 to hold, and an unread era has
>   not held. Against that, C3 and C4 "can only downgrade", and an ungraded check
>   has shown no failure. So it is a parameter and both lines print:
>
>   | Line | Ungraded C4 counts as | Best verdict possible today |
>   |---|---|---|
>   | Headline | not holding | FRAGILE |
>   | Declared secondary | dropped from the verdict | SURVIVES |

## Verdicts, worded now

| Token | When | Consequence |
|---|---|---|
| **SURVIVES** | C1 and C2 both hold, and C3 and C4 both hold | The edge is net-positive at the registered cost point. The contour is recorded. The queue proceeds |
| **FRAGILE** | C1 and C2 hold, but C3 or C4 fails | The edge is net-positive only on this book or only with every date in it. Nothing new ships. Every shipped rule whose delta is smaller than the modelled cost is flagged in [`deployment-evidence.md`](../../deployment-evidence.md) as unmeasured net of cost |
| **VANISHES** | Either C1 or C2 fails | The tier that fails is recorded as having no measured edge net of costs. Exit tuning on that tier stops ([suggested order](../../robustness-review.md#order), step 2). Deployment is an operator decision, not this study's |
| **UNDERPOWERED** | No tier clears C0 | Census printed, nothing concluded |
| **UNCOSTABLE** | G4 fails, which per [Gates](#gates) prints rather than refuses | The cache does not carry enough real quotes to answer the question. The quote census is the recorded result, no criterion is graded, and the fix is a quote backfill, not a lower gate |

> **Resolved at build (2026-10-09) — one verdict per tier.** The verdicts above
> are worded for both tiers together, but [What could ship](#what-could-ship)
> records a verdict per tier. So each tier is graded on its own: C0 first, then
> its own C1 or C2, then C3 and C4. A tier below C0 is UNDERPOWERED while the
> other tier is still graded. There is no combined token. `UNCOSTABLE` belongs
> to the sweep (see G4).

## Anti-tuning

**No cost level may be chosen because it makes the edge survive.** The
registered point is $0.65 per contract per leg per side, no slippage. It was set
from the operator's fills, not from any run. The sweep is a shape and never a
menu.

- If `ARM X` gives VANISHES and some lower point on the `ARM SW` grid gives
  SURVIVES, the verdict is VANISHES. The lower point is reported as part of the
  contour and is not a finding.
- `ARM GAP` and `ARM SW` may not be promoted to primary after the fact.
- The fallback ladder in `ARM Q` is fixed here. It may not be reordered after
  seeing which order costs more.

## What could ship

None. This study ships no rule under any outcome. Its outcomes are a recorded
verdict per tier, a recorded contour, and, on FRAGILE or VANISHES, a flag
against the shipped rules whose deltas are smaller than the modelled cost.
