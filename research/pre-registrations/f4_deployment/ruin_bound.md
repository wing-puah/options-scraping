## ruin_bound — which cap cell earns the most while ruin stays under a stated bound?

_Registered ____-__-__ (DRAFT — not registered; becomes immutable in substance when the operator accepts it)._

**STATUS: DRAFT — NOT REGISTERED until the operator signs.** Until
acceptance every number, arm, gate, bound and verdict below may be edited.
After acceptance none of them may. The registration date is filled in on
acceptance and is the only date this file then carries. Every
`OPERATOR-TO-FILL` blank must hold a value before acceptance; a blank left
empty means the file is not accepted.

## Question

The operator will accept a deeper drawdown if it buys a higher return, as long
as a clear guardrail prevents ruin (request of 2026-09-22). This study turns
that into a rule fixed before any run:

> Among the candidate cap cells and guardrails, choose the one with the
> highest return whose probability of ruin over a horizon H, and whose p95 and
> p99 max drawdown, all stay under bounds the operator writes down first.

It answers a risk-budget question. It does not re-test the edge. Whether the
ladder has an edge at all stays with
[`account_sim`](../../arm-index.md#account_sim)'s
[A1](../../glossary.md#criteria-a1a6), which this study requires and does not
replace.

### Why a pre-registration is needed

The `account_sim` registration forbids adopting a cap value on its P&L. That
rule stands. A cell may be chosen here only because it meets a decision rule
written down before the resampled distribution exists. Eyeballing the cap grid
and picking the cell that looks best is exactly what this file exists to
prevent.

## What this is NOT

- **Not an edge search.** Selection is frozen (`protocol.top_k_per_day`,
  `ladder_rank`, `ladder_eligible`), and so are the exits (the shipped profiles,
  [§5](../../../docs/deployment-rules.md#s5)) and the replay harness
  (`lib/harness.py`).
- **Not a forecast.** A resample recombines one history. It cannot produce a
  market the history did not contain. The stress overlays below are
  assumptions the operator picks, not estimates.
- **Not a new sizing study.** The risk budget stays at 2% of capital on a
  max-loss basis, as `account_sim` registered it. Kelly and volatility-scaled
  budgets are ruled out by the
  [feasibility plan](../../account-sim-feasibility-plan.md#what-is-ruled-out-and-why).
- **Not a size throttle.** The Turtle ladder and `exit_drawdown`'s ARM D shrink
  size in a drawdown; both are closed
  ([entry](../../current.md#2026-09-22--account_sim--a-turtle-drawdown-throttle-is-inert-at-25000-closed-unregistered)).
  The guardrails here stop or cap entries. They do not resize them.

## Definitions

### Ruin

The account is **ruined** on a path if its
[mark-to-market](../../glossary.md#mark-to-market-basis) equity closes at or
below `(1 − X_ruin) × starting capital` on any session inside the horizon H.

- `X_ruin` = **OPERATOR-TO-FILL**. Recommended default: **0.50** (equity at or
  below $12,500 on a $25,000 account).
- Why half: the 2% budget halves with the account. The
  [capital adequacy](../../glossary.md#capital-adequacy) census already finds
  that most candidates do not fit one contract at $25,000, and far fewer would
  at half that. The strategy can no longer be run as registered. That is
  operating ruin, well before equity reaches zero.
- A **margin-call proxy** is also counted: any session where reserved capital
  exceeds equity. With cash enforced and every position defined-risk, this
  must never happen. A non-zero count is a ledger bug and fails gate R3.

### P(ruin)

The share of resampled paths that are ruined within H. It is printed with its
binomial 95% interval. At the registered path count, a bound near 1% is
resolved to about a third of a point.

### Horizon H

The number of sessions one resampled path runs.

- H = **OPERATOR-TO-FILL**. Recommended default: **the length of the pooled
  PRIMARY session series, computed at run time.** That asks "what if another
  history like this one happened", and never extrapolates past the sample's
  own length.
- Any return quoted over H is dollars over H sessions. It is never converted to
  a rate, annualised, or turned into a Sharpe ratio, as the `account_sim`
  registration requires.

### Max drawdown basis

Max drawdown is measured on the mark-to-market basis, as a fraction of
starting capital, matching `mtm_curve.max_drawdown`. The realized-on-close
figure A3 uses is printed beside it but never decides. On 2026-09-21 the MTM
figure was deeper on every book, by 5.6 to 26.2 points.

### Stress overlay

A deterministic loss applied to a resampled path to represent a market the
sample never saw. Each overlay is defined under [Arms](#arms).

## Dependencies

Nothing is built or run until all of these land. Each is a hard gate, not a
preference.

1. **The whole-book re-price**, [next-steps item
   8](../../next-steps.md#waiting-on-the-operator). The book mixes pricing
   regimes today, and 80 `BacktestResults` rows cannot be priced offline.
2. **The cost model on every row the walk can take.** On 2026-09-21,
   `cost_total` was filled on 4 of 211 taken PRIMARY positions. Ruin is a
   left-tail question and cost moves the tail. Gate R1 refuses the run below
   100% coverage of taken positions.
3. **Items 6, 7 and 9** are decided, either way. Each changes which rows exist.
4. **Item 5's first decision.** The `Resolved at build` tags for the 2026-08-13
   cap change go into the `account_sim` registration first. This study then
   treats the registered and the tracked cap cells as two candidates on equal
   footing.
5. **[`holdout_seal`](holdout_seal.md)**, whichever option the operator
   accepts. This study reads no signal date on or after 2026-08-11.

## Population and basis, fixed here

- **Era.** The current era, resolved by `lib/era.py`. The report header names
  it. A wrong or thin era is refused (exit 3 / exit 2), never worked around.
- **Decision population.** PRIMARY dense episodes, as `account_sim` defines
  them (`episode_max_gap` 5, `episode_min_dates` 10), concatenated in date
  order into one session series. Empty sessions inside an episode are kept,
  because they carry the book's real signal density.
- **Check population.** SECONDARY, the full sparse book. A cell must meet the
  bounds on both populations to be chosen. SECONDARY holds the
  2025-11 → 2026-03 drawdown that PRIMARY never saw.
- **Control.** `--era v3`, printed and never read by the decision. It is the
  same market path with different plays, so it is a composition control, not
  an out-of-sample test.
- **Account.** $25,000 fixed base, 2% max-loss budget, three positions per
  day, cash enforced, frozen exits. This is `config/account-sim.yml`'s account
  block, read as it stands at acceptance and printed verbatim.

### Resampling method

A **stationary block bootstrap** (Politis and Romano 1994) over sessions, and
the account walk is re-run on every resampled path.

- **The unit is a session**, carrying that session's ranked candidate list (it
  may be empty). Each candidate carries its outcomes relative to its entry
  session: exit offset, exit reason, and daily marks, at any contract count,
  from the frozen harness.
- **A path** is H sessions, assembled from blocks whose lengths are geometric
  with mean L. A block starts at a uniform session and wraps from the end of
  the series back to the start.
- **Positions travel with their entry session.** A position entered in a block
  keeps its own exit offset and marks, even past the block's end. So
  concurrency across a block boundary is synthetic. That is why L must be long
  relative to the holding period.
- **The ledger is re-simulated**, not re-ordered. `account_sim.simulate()`
  walks each path with the cell's caps, sizing and guardrail. Sizing, cap
  refusals, cash and the dollar stop all respond to the resampled order. This
  is the difference from `lib/path_bootstrap.py`, which holds each session's
  dollars as realized (its caveat (a)).

### Block length

- **Primary L** = max(20, p75 of held sessions on the realized walk, rounded up
  to a multiple of 5) sessions. The p75 is printed before any result.
- **Sensitivity L** = half and 1.5 × the primary L, rounded to a multiple of 5.
- The decision must hold at every L where H / L ≥ 8. A cell that passes at one
  such L and fails at another is not eligible. An L with H / L < 8 is printed,
  labelled too few blocks, and not read.
- If H / L < 8 at the primary L, too few independent blocks exist and the
  verdict is `UNDERPOWERED`.

### Draws and seed

- 5,000 paths per configuration per overlay.
- One seed, set at acceptance as the registration date in `YYYYMMDD` form.
  The same index stream drives every cell, so cells are compared on common
  random numbers. Their percentiles are correlated and are never differenced
  as if independent.

## Plan-time observations, disclosed

These figures are known while designing this study, measured on pre-cost
exports. Every cap cell below has already been seen on the realized path.

_Era v4 · exports 2026-09-19 · reports at git `4c7db30`
([entry](../../current.md#2026-09-21--account_sim--the-registered-cap-cell-prints-feasible-the-run-on-record-does-not))._

| Fact | Value |
|---|---|
| PRIMARY episodes / dates / sessions | 5 / 127 / 356 |
| PRIMARY exit sessions, tracked cell | 162 |
| Taken positions, tracked cell (0.25, 2.50), PRIMARY | 211 |
| Taken positions, registered cell (0.25, 1.50), PRIMARY | 142 |
| Tracked cell maxDD, realized / MTM, PRIMARY | 35.0% / 42.1% |
| Tracked cell maxDD, realized / MTM, SECONDARY | 40.8% / 67.0% |
| Registered cell maxDD, realized / MTM, PRIMARY | 20.3% / 25.9% |
| Registered cell maxDD, realized / MTM, SECONDARY | 23.5% / 44.8% |
| Paths past 25%, existing re-order bootstrap, tracked PRIMARY | 44–66% |
| Paths past 25%, existing re-order bootstrap, registered PRIMARY | 8–12% |
| Positions at the one-contract floor, tracked PRIMARY | 177 of 211 |
| Dollar-stop exits that lost more than the $500 stop | 37 of 37 |
| Taken positions carrying `cost_total` | 4 of 211 |
| Book delta direction | 100% long |

The [feasibility plan's](../../account-sim-feasibility-plan.md) trial ledger
already holds more than 70 configurations scored against the 25% bar on this
one path. This study adds 24 configurations and three new guardrail arms,
which uses the plan's cap of three new arms on this era.

### What a resample can and cannot tell on this book

**A Monte Carlo can say how bad the order of this history could have been. It
cannot say how bad a different market could be.** That limit shapes the whole
design.

- **Small sample.** PRIMARY is 356 sessions. At a 20-session block that is
  about 18 independent blocks. The p99 of a max drawdown is set by how the two
  or three worst blocks stack. It is an arrangement of known losses, not a
  measurement of unknown ones.
- **One correlated window.** Every date sits inside 2024-01 → 2026-05, one
  bull market with two sharp shocks (August 2024 and April 2025). There is no
  2020 crash and no 2022-length bear market. A resample can stack bad blocks
  but can never make any one block worse than the worst the sample holds.
- **One factor.** The book is 100% long delta, concentrated in megacap tech,
  semiconductors and crypto. A broad selloff hits every open position at once.
  Block resampling keeps that correlation only inside a block.
- **Era v4 is thin.** The live dates since 2026-08-11 are sealed and mostly
  unpriced. The resample draws only from the backfilled book.
- **Concurrency.** Positions overlap for weeks. Resampling single sessions
  would break that and understate drawdowns. Hence blocks, and the rule that L
  covers the p75 holding period.
- **Live density is higher.** The daily pipeline emits every session. PRIMARY
  has signals on about a third of its sessions. More signals mean more
  concurrent risk, so overlay O3 tests the denser case.
- **Defined risk bounds the true worst case.** Every position is a spread whose
  maximum loss is reserved in cash. The worst possible loss on any session is
  the capital reserved at that moment. That number needs no simulation. It is
  why guardrail M below, which caps reserved capital, is the one guardrail
  whose protection does not depend on the sample.
- **What the outside-model risks are.** Early assignment on a short leg,
  gap-through fills beyond the daily mark, and broker margin changes are not
  modelled. The dollar stop already overshoots on every stop exit.

So the tail beyond the sample comes only from the overlays, and the overlays
are the operator's assumptions. The study states this in its report header.

## Arms

Every configuration is a cap cell × a guardrail, run under each overlay. All
24 are reported. One is chosen, by the rule under
[Bar for a candidate](#bar-for-a-candidate), or none is.

### The cap cells

Per-position cap fixed at 0.25 × equity. Net cap and floor vary. All three net
values are already on `account_sim`'s registered grid; no new cap value is
introduced.

| Cell | Net cap | Floor ([F1 vs F2](../../glossary.md#f1-vs-f2)) |
|---|---|---|
| N100-F1 | 1.00 | F1, take the one-contract floor |
| N150-F1 | 1.50 | F1, the `account_sim` registered headline |
| N250-F1 | 2.50 | F1, the tracked config since 2026-08-13 |
| N100-F2 | 1.00 | F2, refuse a pick whose one contract exceeds the budget |
| N150-F2 | 1.50 | F2 |
| N250-F2 | 2.50 | F2 |

ARM R (reject) throughout; ARM D and ARM H are not re-run here.

### The guardrails

Three new arms plus none. Each reads only equity and positions as of the close
of the session it acts on, never anything later.

| Guardrail | Rule | Default, OPERATOR-TO-FILL |
|---|---|---|
| G-none | No guardrail beyond the cell's caps | — |
| G-M, max open risk | Refuse a new position if total reserved capital would exceed `m` × current MTM equity | `m` = 0.50 |
| G-K, kill switch | Stop all new entries for the rest of H once MTM equity is `k` below its running peak; open positions run to their shipped exits | `k` = 0.25 |
| G-C, circuit breaker | After a session whose MTM loss is at least `c` × equity, take no new entries for the next `b` sessions | `c` = 0.05, `b` = 5 |

Why these three.

- **G-M** bounds the correlated worst case directly. If every open position
  hit max loss at once, the account loses at most `m` of equity. When
  `account_sim` was registered, reserved over equity had a median of 0.27 and
  a p90 of 0.83 on the unconstrained book, so 0.50 binds on the heavy sessions
  only. Those are old exports; the run prints the current distribution first.
- **G-K** is the operator's "clear guardrail against ruin". It never restarts
  inside H, because a restart is an operator decision the model cannot make. A
  peak-keyed trigger can miss a slow drawdown
  ([lessons](../../lessons.md)); the report counts the paths where ruin
  happened without G-K firing.
- **G-C** reacts to a single-day shock, the shape the overlays assume. It is
  the only guardrail that can act inside one block.

### Stress overlays

| Overlay | What it does | Default, OPERATOR-TO-FILL |
|---|---|---|
| O0 | None. The resample alone | — |
| O1, correlated gap | Once per path, at the session with the most reserved capital, every open long-delta position loses the smaller of its max loss and its absolute delta-notional × `g`. Short-delta gains are not credited | `g` = 0.10, about the 2020-03-16 S&P 500 close-to-close fall |
| O2, total loss | At the same session, every open position loses its full max loss. The defined-risk ceiling, deterministic per path | — |
| O3, live density | Resample only from sessions that carry a candidate list, so every session emits | — |

O1 puts the gap at the worst moment on purpose. A random placement would
average the shock away.

## Unit and metric

Per configuration, overlay, population and block length:

| Metric | Basis |
|---|---|
| P(ruin within H), with binomial 95% interval | MTM equity |
| p50, p95, p99 of max drawdown | MTM, fraction of starting capital |
| Median dollars over H, and its p5 | Realized on close at the end of H |
| Worst O2 loss, p99 across paths | Fraction of equity at that session |
| Taken positions, median per path | Count |
| Guardrail firings, share of paths | Count |

The realized walk (block length = series length, no overlay) is printed first
for every configuration, as the anchor the resample must reproduce.

## Gates

A failing gate exits non-zero and prints no verdict.

- **R0 — era.** `lib/era.py` refuses a wrong or thin era.
- **R1 — cost coverage.** Every taken position on every realized walk carries
  the post-model cost columns (`cost_total`, `cost_basis`). Anything below
  100% refuses the run.
- **R2 — identity.** With L equal to the series length, no guardrail and no
  overlay, the resampled walk reproduces `account_sim`'s realized walk for the
  same cell: the same positions, dollars and max drawdown.
- **R3 — ledger.** On every path, at every session, `cash + Σreserved ==
  capital + Σrealized` (the `account_sim` G3 identity), and reserved never
  exceeds equity.
- **R4 — outcome blindness.** Guardrails and selection read no outcome field.
  This reuses `account_sim`'s G5 blind-record check.
- **R5 — overlay order.** For every configuration, P(ruin) under O2 ≥ O1 ≥
  O0. A violation is a bug, not a finding.

## Bar for a candidate

A configuration is **eligible** only if every clause below holds, at every
readable block length, on both PRIMARY and SECONDARY.

| Clause | Test | Bound, OPERATOR-TO-FILL | Recommended default |
|---|---|---|---|
| B1 ruin, base | P(ruin within H) under O0 ≤ `p_ruin` | `p_ruin` = ____ | 0.01 |
| B2 ruin, stressed | P(ruin within H) under O1 and O3 ≤ `p_ruin_stress` | `p_ruin_stress` = ____ | 0.05 |
| B3 typical bad case | p95 MTM max drawdown under O0 ≤ `D95` | `D95` = ____ | 0.30 |
| B4 severe case | p99 MTM max drawdown under O0 ≤ `D99` | `D99` = ____ | 0.45 |
| B5 defined-risk ceiling | p99 O2 loss ≤ `R_max` of equity | `R_max` = ____ | 0.60 |
| B6 edge | `account_sim` A1 holds on the realized walk, unchanged | — | — |

Why the defaults sit where they do.

- `D95` lets the typical bad case run five points past A3's 25% bar. That is
  the "accept a worse drawdown" the operator asked for.
- `D99` stays short of the ruin line, so a p99 path is still tradeable.
- `R_max` keeps a total-loss day from reaching ruin by itself.

### The decision rule

1. Take the eligible configuration with the lowest p95 MTM max drawdown under
   O0, at the primary L, on PRIMARY. Call it **S**, the safest eligible.
2. A riskier eligible configuration displaces S only if its per-date dollar
   advantage over S, on the realized PRIMARY walk, has a date-clustered paired
   95% [CI](../../glossary.md#paired-ci) excluding zero
   (`protocol.boot_ci_paired_by_date`).
3. If more than one riskier configuration passes step 2, choose the one with
   the highest median dollars over H under O0.
4. If no configuration is eligible, none is chosen.

Step 2 reads the realized walk, not the resample, on purpose. Every path is a
recombination of the same positions, so a resampled return gap between two
cells is nearly the realized gap repeated 5,000 times. It would look precise
without being evidence. A deeper drawdown is bought only with a return the
dates themselves can distinguish.

## Verdicts, worded now

- **`RISKIER CELL EARNS ITS DRAWDOWN: <config>`** — a configuration other than S
  passed step 2 and was chosen.
- **`SAFEST ELIGIBLE CELL: <config>`** — S was eligible and nothing riskier
  earned its drawdown.
- **`NO CELL MEETS THE BOUNDS`** — no configuration is eligible. The answer
  then points at capital, through the capital adequacy census, never at looser
  bounds.
- **`UNDERPOWERED`** — H / L < 8 at the primary L on PRIMARY. Nothing is
  chosen.

## Anti-tuning

- Every blank is filled before any code is written. After acceptance no bound,
  overlay size, guardrail parameter, H, L rule, seed or path count changes.
- No cap cell, guardrail or overlay is added after the first run. A new one is
  a new registration and counts against the next era's arm cap.
- The decision reads only the rule above. The full 24 × 4 table is printed and
  never used to pick a configuration by eye.
- If the verdict is `NO CELL MEETS THE BOUNDS`, the bounds are not loosened to
  find one. That would be the P&L-driven cap choice `account_sim` forbids.
- The v3 control and the realized-walk figures never enter the decision beyond
  step 2 and B6.

## Ship criteria

At most two things may ship, and only by the operator's hand after reading the
report.

- **The chosen cell's caps** into `config/account-sim.yml`. Production's
  exposure caps read that file, so this changes the live deploy card's cap
  check. The change carries a `Resolved at build` tag in the `account_sim`
  registration, naming this study's verdict.
- **The chosen guardrail**, if any, as an attention flag first. It is built in
  both `s03_risk.py` and `s04b_page.py` by hand, as the cap rule is. It becomes
  a hard stop only after a live-date read the operator registers separately.

Nothing ships on `NO CELL MEETS THE BOUNDS` or `UNDERPOWERED`, and nothing ships
before every dependency above has landed.

## Build notes

Not part of the registration. What already exists and should be reused:

| Need | Existing code |
|---|---|
| The account walk, caps, cash, F1/F2 | `f4_deployment/account_sim.py::simulate`, `Cfg`, `Ledger`, `admission` |
| Sized replays, memoised | `account_sim.py::replay_sized` with `new_cache()` |
| Candidate day lists | `protocol.ordered_by_day`, `ladder_rank`, `ladder_eligible` |
| Dense episodes | `account_sim.py::dense_episodes` |
| MTM marks and max drawdown | `lib/mtm_curve.py::position_marks`, `book_curves`, `max_drawdown` |
| Circular block indices, identity at L = n | `lib/path_bootstrap.py::_resample_indices`, extended to geometric block lengths |
| Percentiles | `lib/forward_drawdown.py::pctile` |
| Paired date-clustered CI | `protocol.boot_ci_paired_by_date` |
| Outcome blindness | `account_sim.py::blind_records` and the G5 check |
| Ledger identity | `account_sim.py` G3 |
| Capital adequacy for the `NO CELL` answer | `lib/capital_adequacy.py` |

What is new:

- A **stationary sampler**. `path_bootstrap._resample_indices` draws fixed
  blocks; the geometric-length version is a small extension beside it, not a
  change to it.
- A **re-timing adapter** that rebuilds `day_lists` and each position's entry,
  exit and mark sessions on the resampled calendar. `simulate()` itself should
  need only a session list it walks in order.
- **Guardrail hooks** inside the walk. `Cfg.dd_throttle` shows the pattern:
  a `None` default that leaves the frozen path byte-identical.
- Runtime. The full design is about 2.9 million account walks (configurations
  × overlays × block lengths × populations × paths). Replays are memoised by
  `(row, contracts, stop)`, so the walk is ledger arithmetic only, but budget
  for a multi-hour run or parallelise by configuration.
