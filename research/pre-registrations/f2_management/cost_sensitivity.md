## cost_sensitivity — at what cost per leg does the Tier A/B edge vanish?

_Registered ____-__-__ (DRAFT — not registered; becomes immutable in substance when the operator accepts it)._

**STATUS: DRAFT.** Until acceptance every number, arm, gate and verdict
below may be edited. After acceptance none of them may. The registration
date is filled in on acceptance and is the only date this file then
carries.

## Question

Does the deployed edge survive realistic trading costs, and at what cost level
does it stop being an edge?

The backtest fills every leg at the bid/ask mid, in and out. No commission,
fee or slippage term exists anywhere in `scripts/backtest/`,
`scripts/backtest_study/`, `config/backtest.yml` or `config/account-sim.yml`
([robustness review B1](../../robustness-review.md#backtest)). The rules that
shipped rest on gains of +0.02 to +0.04 [R](../../glossary.md#r). A realistic
round trip on a two-leg vertical is of the same order. So the question is not
"how much does cost shave off"; it is "is there anything left".

Two things are asked, in order:

1. **The registered point.** At $0.65 per contract plus 25% of the quoted
   spread per leg per side, do Tier A and Tier B each still show
   [meanR](../../glossary.md#meanr) > 0 with a date-clustered
   [CI](../../glossary.md#ci) excluding zero?
2. **The contour.** Across a declared sweep of
   [cost points](../../glossary.md#cost-point), where does each
   tier's CI lower bound cross zero? That number is the answer to "at what
   cost does the edge vanish", and it is reported as a shape, not a menu.

### Why this study exists

Every queued item assumes an edge that may be a cost artefact
([suggested order](../../robustness-review.md#order), step 2). Nothing in the
repo has ever charged a cent. No study can be read as net of costs, including
the ones that shipped rules.

## What this is NOT

- **Not a selection study.** The ladder is FROZEN
  ([§2](../../../docs/deployment-rules.md#s2),
  [top-k/day](../../glossary.md#top-kday)). No column is added to selection and
  no tier rule is touched.
- **Not an exit study.** The shipped exit profiles
  ([§5](../../../docs/deployment-rules.md#s5)) are frozen. This study re-prices
  the same exits, it does not re-choose them. If a cost level would have
  changed which exit fired, that is out of scope and is stated as a limit
  rather than modelled.
- **Not a live-slippage study.** It models cost from quoted spreads in
  `backtests/option_history_cache/`. What the operator actually paid is a
  different question and needs the journal
  ([next-steps §2.5](../../next-steps.md#s2-5)).
- **Not a fill-probability study.** It assumes every registered order fills at
  the modelled price. Partial fills, unfilled legs and queue position are out
  of scope.

## Dependencies

Three things must land before the study is built. Running it earlier produces a
number that looks net-of-cost and is not.

| Prerequisite | What it is | Why it binds |
|---|---|---|
| B1 cost knobs | `commission_per_contract` and `slippage_frac_of_spread` under `simulation:` in `config/backtest.yml`, charged at entry and exit in `scripts/backtest/simulate.py` | The study reads the knobs. It never invents its own cost path. |
| B2 pre-fill grid fix | Price grid starts at the entry date, not signal date + 1 | About 4% of positions carry at least one pre-entry day today. A cost read on those rows nets a cost against a P&L the position never had. |
| One suite re-run | `BacktestResults` re-run once, after both fixes | The exports this study reads must post-date both. Two re-runs would pool two populations. |

The study REFUSES to run against an export produced before the grid fix (gate
G3). That refusal is the point: it costs a run to discover, which is cheaper
than a wrong headline.

## Population and basis, fixed here

- **Population.** `lib/book.py::load_book()`, era-scoped by `lib/era.py`,
  `include_bs=False`. Real and `strike_expiry_tweak` rows only.
  `bs_options_hist` rows are excluded everywhere and may not be re-admitted for
  any arm.
- **Era.** The current era (v4) is PRIMARY. v3 is run as the era-stability
  read and reported. The report header names the era it ran on.
- **The date count is NOT fixed here.** The population is stated by rule: every
  signal date the era resolves at run time with at least one real-or-tweak row.
  No count is written into this file and none may be written into the module
  ([standing rule](../../robustness-review.md#method), M-class; a stored
  `expected_positions` fingerprints a snapshot, not a hypothesis).
- **Deployed set.** `protocol.top_k_per_day(book, ladder_rank, k=3,
  ladder_eligible)` — the shipped card. This study never re-selects. Tier A and
  Tier B are read separately, never pooled into one "A/B" number.
- **Sealed dates are excluded, by rule.** Every signal date inside the window
  sealed by [`holdout_seal`](../f4_deployment/holdout_seal.md) is dropped from
  every arm, and from every census count that feeds an outcome figure, for as
  long as that seal stands. This study prints per-tier net meanR and net PF,
  which is exactly what the seal forbids on a sealed date, and its population is
  stated by rule — so without this clause it would sweep the seal the moment a
  live date priced. The exclusion tracks the seal rather than a date list. If
  the operator declines `holdout_seal`, this clause is inert and the population
  is the whole era.
- **Cost basis.** A position's cost is charged per LEG, at entry and at exit,
  in dollars per contract, then divided by that position's entry cost basis
  (`abs(entry_option_price) × 100`) to become a delta in R. Leg count comes
  from the `legs` column and is cross-checked against `entry_leg_detail`.
- **Quoted spread.** `Ask − Bid` from the leg's own row in
  `backtests/option_history_cache/<TICKER>_<YYYYMMDD>_<STRIKE><C|P>.csv`, on
  the entry date and on the exit date. Never interpolated across dates.
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
cost study as a sensitivity", and that is what this registration does with it.

## Arms

- **`ARM Z` — ZERO-COST CONTROL.** The book exactly as it prints today, no
  cost charged. Reference only. It carries no verdict and is never quoted as a
  result of this study.
- **`ARM X` — THE REGISTERED COST POINT. PRIMARY.** $0.65 per contract plus
  25% of the quoted spread, per leg, per side. Every criterion below is graded
  on this arm and no other.
- **`ARM SW` — THE SWEEP. SENSITIVITY ONLY.** The grid below, run to locate
  each tier's breakeven contour. `ARM SW` may never produce a verdict, a
  shipped rule or a recommended cost level.

  | Knob | Grid |
  |---|---|
  | commission per contract | $0.00, $0.65, $1.00, $1.50 |
  | slippage, as a fraction of the quoted spread per leg per side | 0.00, 0.25, 0.50, 1.00 |

- **`ARM Q` — QUOTE AVAILABILITY.** Census of legs whose entry or exit quote is
  missing or degenerate (`Bid` or `Ask` absent, `Ask ≤ Bid`, or `Bid = 0`).
  Such a leg is charged under one declared fallback, in this order, and the
  fallback used is tagged and counted per arm:

  1. the same contract's median quoted spread over its own priced path;
  2. failing that, the median quoted spread of the same ticker's other legs on
     the same date;
  3. failing that, the position is UNCOSTABLE and is excluded from every cost
     total, never charged zero.

  Excluding a position is not the same as charging it nothing. The
  missing-greek rule is the model: an absent quote is `None`, never `0.0`.
- **`ARM GAP` — ADVERSE-FILL SENSITIVITY.** On rows whose exit is
  `profit_target`, `trailing_stop`, `underlying_stop`, `dollar_stop`,
  `be_stop` or `stop_loss`, charge one additional adverse tick at exit on top
  of `ARM X`. Those six are EVERY threshold-triggered exit the frozen harness
  can fire (`scripts/backtest_study/lib/harness.py`); each realises at the
  close of the day its threshold is crossed, so B4's asymmetry applies to all
  six identically and none may be dropped for being a dollar or an underlying
  threshold rather than a percentage one. The remaining reasons are NOT
  charged the tick: `time_exit` fires on a calendar date, `expired` and
  `cap_open` end the path rather than crossing a level, so there is nothing to
  fill through. Sensitivity only. It answers "does the close-only grid's
  symmetry hide the cost result", and it carries no verdict.

## Unit and metric

- **Unit** is a deployed position, keyed the way
  `scripts/backtest/shared/identity.py` keys it.
- **Metric** is [net R](../../glossary.md#net-r): the stored
  [R](../../glossary.md#r) minus the modelled cost, expressed in the same
  units. [E](../../glossary.md#e) is reported
  alongside but is never a criterion here, because a held-to-cap figure has no
  exit leg to charge.
- **Headline** per tier: net meanR with a 95% date-clustered CI
  (`protocol.boot_ci_by_date`), and net [PF](../../glossary.md#pf) with its own
  date-clustered CI.
- **Contour** per tier: the smallest cost level on the `ARM SW` grid at which
  the net meanR CI lower bound is ≤ 0, quoted as the pair (commission,
  slippage fraction) and as the implied dollars per leg per side.

## Gates

Each gate exits non-zero on failure, with ONE exception declared here so it
cannot be read either way after the run: **G4 is verdict-producing, not a
refusal.** A failing G4 prints its census and the UNCOSTABLE verdict, and the
run exits zero. Every other gate refuses and prints nothing.

- **G1 ERA IDENTITY.** The report header names the era and the export
  fingerprint. A wrong or thin era refuses (`lib/era.py`, exits 2 and 3). No
  study-local snapshot pin may dodge this.
- **G2 COST IS CHARGED TWICE, NEVER ONCE.** Every costed position is charged at
  entry and at exit, except an expired leg, which is charged at entry only. The
  run recomputes the charge count independently and FAILS on any mismatch.
- **G3 GRID FIX PRESENT.** The run refuses an export produced before the B2
  pre-fill grid fix. The check is on the export's own provenance, not on a
  flag the operator passes.
- **G4 QUOTE PROVENANCE. VERDICT-PRODUCING, NOT A REFUSAL — the one gate that
  does not exit non-zero.** The fallback share is printed per arm. `ARM X`
  FAILS G4 if more than 25% of its charged legs are priced from fallback 2 or
  are UNCOSTABLE. A cost study whose costs are mostly guessed is not a cost
  study — but the census of what is missing is the useful output of that
  failure, and a refusal would print no census at all. So on failure the run
  prints the per-arm quote census, prints NO outcome number, grades no
  criterion, and records the verdict UNCOSTABLE.
- **G5 NO NEW STATISTIC.** No annualised figure, no Sharpe, no
  time-to-recover, per the standing research-tier rule.
- **G6 NO HARDCODED CENSUS.** Every count, share and range printed in prose is
  computed from the run. A measured quantity frozen into a string literal FAILS
  review.
- **G7 PRICING-TIER HONESTY.** Every dollar and R figure is quoted real+tweak.
  No figure may pool `bs_options_hist` rows.

## Bar for a candidate

The study does not ship a rule. It certifies, or refuses to certify, that the
deployed edge is net-positive. C1 and C2 are the registered pass rule and are
graded on `ARM X` alone. C3 and C4 are supporting and can only downgrade, never
reverse.

- **C0 POWER FLOOR.** A tier is read only if it has at least 25 dates and at
  least 40 deployed positions after top-3/day. Below either, that tier prints
  **UNDERPOWERED**: census only, no outcome number printed at all. The floor
  may not be lowered to make a tier readable. Given the v4 tier-mix shift
  recorded by
  [`v4_bridge`](../f1_selection/v4_bridge.md), Tier A is expected to be the
  binding one.
- **C1 TIER A NET-POSITIVE.** Tier A net meanR > 0 with its 95% date-clustered
  CI excluding zero, under `ARM X`.
- **C2 TIER B NET-POSITIVE.** The same, for Tier B.
- **C3 LEAVE-ONE-OUT.** Dropping any single date, and separately any single
  ticker, leaves each passing tier's net meanR positive
  ([LOO](../../glossary.md#loo)).
- **C4 ERA STABILITY.** C1 and C2 hold on both eras with the same sign.

## Verdicts, worded now

- **SURVIVES** — C1 and C2 both hold, and C3 and C4 both hold. The edge is
  net-positive at the registered cost point. The contour is recorded. The
  queue proceeds.
- **FRAGILE** — C1 and C2 hold, but C3 or C4 fails. The edge is net-positive
  only on this book or only with every date in it. Nothing new ships, and every
  shipped rule whose delta is smaller than the modelled cost is flagged in
  [`deployment-evidence.md`](../../deployment-evidence.md) as unmeasured net of
  cost.
- **VANISHES** — either C1 or C2 fails. The tier that fails is recorded as
  having no measured edge net of costs. Exit tuning on that tier stops
  ([suggested order](../../robustness-review.md#order), step 2). Deployment is
  an operator decision, not this study's.
- **UNDERPOWERED** — no tier clears C0. Census printed, nothing concluded.
- **UNCOSTABLE** — G4 fails, which per §Gates prints rather than refuses. The
  cache does not carry enough real quotes to answer the question. The quote
  census is the recorded result, no criterion is graded, and the fix is a quote
  backfill, not a lower gate.

## Anti-tuning

**No cost level may be chosen because it makes the edge survive.** The
registered point is $0.65 per contract plus 25% of the quoted spread per leg
per side, fixed here, before any run. The sweep is a shape and never a menu.

If `ARM X` gives VANISHES and some lower point on the `ARM SW` grid gives
SURVIVES, the verdict is VANISHES. The lower point is reported as part of the
contour and is not a finding.

`ARM GAP` and `ARM SW` may not be promoted to primary after the fact. The
fallback ladder in `ARM Q` is fixed here and may not be reordered after seeing
which order costs more.

## Ship criteria

None. This study ships no rule under any outcome. Its outcomes are a recorded
verdict per tier, a recorded contour, and — on FRAGILE or VANISHES — a flag
against the shipped rules whose deltas are smaller than the modelled cost.

## Build notes

Not part of the registration. Implementation only.

- Family `f2_management/`. No `scripts/study_map/catalog.py` entry until the
  module exists.
- The module reads the cost knobs from `config/backtest.yml`. It does not
  define its own defaults, so a config change and a study change cannot drift.
- Quotes come from the existing cache. The module performs no network fetch.
- `tests/` gets the arithmetic: per-leg charge, the twice-not-once rule, the
  expired-leg exemption, and the fallback ladder's ordering.
