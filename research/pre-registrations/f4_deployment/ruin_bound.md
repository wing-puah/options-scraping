## ruin_bound — which cap cell earns the most while ruin stays under a stated bound?

<!-- outcome:start -->
> Latest outcome: headline ($500 budget and stop) `SAFEST ELIGIBLE CELL: N250-F2 G-none`; declared secondary ($1,000 budget and stop) `NO CELL MEETS THE BOUNDS` — 2026-10-10 · [record](../../study-results/f4_deployment/ruin_bound.md).
<!-- outcome:end -->

_Registered 2026-10-09._

**STATUS: ACCEPTED BY DEFAULT 2026-10-09 on the drafter's recommended
defaults; the operator may revisit (a revisit after a result is a NEW
registration, never an edit).** Each answer is tagged
`Resolved at build (2026-10-09)` where it sits. Every bound, parameter and
verdict rule was fixed before the module read any outcome column. Two gate
rulings came later, after a 100-path smoke run failed gates R3 and R5; neither
moves a bound.

## The question

The operator will accept a deeper drawdown if it buys a higher return, as long
as a clear guardrail prevents ruin (request of 2026-09-22). This study turns
that into a rule fixed before any run:

> Among the candidate cap cells and guardrails, choose the one with the
> highest return whose probability of ruin over a horizon H, and whose p95 and
> p99 max drawdown, all stay under bounds the operator writes down first.

It answers a risk-budget question. It does not re-test the edge. Whether the
ladder has an edge stays with [`account_sim`](../../arm-index.md#account_sim)'s
[A1](../../glossary.md#criteria-a1a6), which this study requires and does not
replace.

The `account_sim` registration forbids adopting a cap value on its P&L, and that
rule stands. A cell may be chosen here only because it meets a decision rule
written down before the resampled distribution exists.

The account stays $25,000, as in `account_sim`. The operator sizes and stops on
$1,000 a position and called the $500 budget too conservative
([narrow_to_fit](narrow_to_fit.md)).

## What this study is not

- **Not an edge search.** Selection is frozen (`protocol.top_k_per_day`,
  `ladder_rank`, `ladder_eligible`). So are the exits (the shipped profiles,
  [§5](../../../docs/deployment-rules.md#s5)) and the replay harness
  (`lib/harness.py`).
- **Not a forecast.** A resample recombines one history. It cannot produce a
  market the history did not contain. The stress overlays are assumptions the
  operator picks, not estimates.
- **Not a new sizing study.** The risk budget stays at 2% of capital on a
  max-loss basis, as `account_sim` registered it. Kelly and volatility-scaled
  budgets are ruled out by the
  [feasibility plan](../../account-sim-feasibility-plan.md#what-is-ruled-out-and-why).
  Resolved at build (2026-10-09): the budget is a parameter with two declared
  values. The headline is the registered 2% ($500 budget and stop). The
  operator's $1,000 budget and stop is a declared secondary. It runs the same
  design and prints its own verdict line, which never feeds the headline.
- **Not a size throttle.** The Turtle ladder and `exit_drawdown`'s ARM D shrink
  size in a drawdown; both are closed
  ([entry](../../current.md#2026-09-22--account_sim--a-turtle-drawdown-throttle-is-inert-at-25000-closed-unregistered)).
  The guardrails here stop or cap entries. They do not resize them.
- **Not a change to production.** The result is a reading for the operator. It
  changes no tracked cap, no config file and no production rule.

### What a resample cannot tell on this book

A resample can say how bad the order of this history could have been, not how
bad a different market could be. The tail beyond the sample comes only from the
overlays, which are the operator's assumptions. The report header states this.

- **Small sample.** PRIMARY is 356 sessions, about 18 blocks at a 20-session
  block. Its p99 drawdown is an arrangement of known losses.
- **One window.** Every date sits inside 2024-01 → 2026-05: one bull market,
  shocks in August 2024 and April 2025, no 2020 crash, no 2022-length bear.
- **One factor.** The book is 100% long delta. Block resampling keeps the
  correlation of a broad selloff only inside a block.
- **Era v4 is thin.** The resample draws only from the backfilled book.
  Resolved at build (2026-10-09): the seal now starts on 2026-09-23, so the
  priced dates from 2026-08-11 to 2026-09-22 are in the book and the resample.
- **Live density is higher.** PRIMARY has signals on about a third of its
  sessions; overlay O3 tests the denser case.
- **Defined risk bounds the true worst case** at the capital reserved. So G-M is
  the one guardrail whose protection does not depend on the sample.
- **Not modelled:** early assignment, gap-through fills beyond the daily mark,
  and broker margin changes. The dollar stop already overshoots on every stop
  exit.

## Definitions

### Ruin

The account is **ruined** on a path if its
[mark-to-market](../../glossary.md#mark-to-market-basis) equity closes at or
below `(1 − X_ruin) × starting capital` on any session inside the horizon H.

- `X_ruin` = **0.50** (equity at or below $12,500 on a $25,000 account).
  Resolved at build (2026-10-09), the drafter's default. At half the account a
  $1,000 stop is 8% of equity, and the 2% budget no longer fits most candidates
  ([capital adequacy](../../glossary.md#capital-adequacy)). That is operating
  ruin.
- A **margin-call proxy** is also counted: any session where reserved capital
  exceeds equity. With cash enforced and every position defined-risk, this must
  never happen. A non-zero count is a ledger bug and fails gate R3. Resolved at
  build (2026-10-09): the gating count uses equity as `capital + realized`,
  which is `cash + reserved`, so it fires only on negative cash. On the marked
  basis, a book of losing open positions can make reserved exceed equity with no
  ledger fault. That marked count is printed and gates nothing.

### P(ruin)

The share of resampled paths that are ruined within H, printed with its binomial
95% interval. At the registered path count, a bound near 1% is resolved to
about a third of a point. Resolved at build (2026-10-09): the interval is the
Wilson score interval. The bar is read on the point estimate; the interval is
printed beside it.

### Horizon H

The number of sessions one resampled path runs.

- H = **the length of the pooled PRIMARY session series, computed at run
  time.** It asks "what if another history like this one happened", and never
  extrapolates past the sample's own length. Resolved at build (2026-10-09),
  the drafter's default. SECONDARY uses its own series length, by the same
  rule.
- Resolved at build (2026-10-09), what the session series is: every weekday on
  which some ladder-eligible candidate of the population could be open, from its
  entry session to its replayed exit at the cell's budget and stop. Overlapping
  spans merge. (Bare episode spans would break gate R2.) The series is built per
  budget, because the replayed exit depends on the stop.
- Any return quoted over H is dollars over H sessions. It is never converted to
  a rate, annualised, or turned into a Sharpe ratio, as the `account_sim`
  registration requires.
- Resolved at build (2026-10-09): a position still open at the end of H counts
  in the marked equity, so ruin and drawdown see it. It is left out of the
  dollars over H, which are realized on close.

### Max drawdown basis

Max drawdown is measured on the mark-to-market basis, as a fraction of starting
capital, matching `mtm_curve.max_drawdown`. The realized-on-close figure A3 uses
is printed beside it but never decides. On 2026-09-21 the MTM figure was deeper
on every book, by 5.6 to 26.2 points.

### Cost basis

Resolved at build (2026-10-09). The frozen harness and `account_sim`'s walk
book gross dollars.

- Every figure this study decides on is net of cost. Each position is charged
  its row's `cost_total` per contract (`cost_total` over the row's contracts),
  times its own contracts, on its exit session.
- The mark on the exit session carries the same charge, as `mtm_curve` does for
  a stored row.
- The reserve on the net basis is the max loss plus that commission, the cash
  the position can cost. A 100-path smoke run on 2026-10-09 found R3 failing
  without it.
- Gate R2 runs on the gross basis, because that is what it compares against.
- A1 (clause B6) stays `account_sim`'s own test on the gross replay R,
  unchanged.

### Stress overlay

A deterministic loss applied to a resampled path, to represent a market the
sample never saw. Each overlay is defined under
[What it compares](#what-it-compares).

## Dependencies

Nothing is built or run until all of these land. Each is a hard gate, not a
preference.

1. **The whole-book re-price**, [next-steps item
   8](../../next-steps.md#waiting-on-the-operator). The book mixes pricing
   regimes, and 80 `BacktestResults` rows cannot be priced offline.
2. **The cost model on every row the walk can take.** On 2026-09-21,
   `cost_total` was filled on 4 of 211 taken PRIMARY positions. Cost moves the
   left tail. Gate R1 refuses the run below 100% coverage of taken positions.
3. **Items 6, 7 and 9** are decided, either way. Each changes which rows exist.
4. **Item 5's first decision.** The `Resolved at build` tags for the 2026-08-13
   cap change go into the `account_sim` registration first. This study then
   treats the registered and the tracked cap cells as two candidates on equal
   footing.
5. **[`holdout_seal`](holdout_seal.md)**, whichever option the operator
   accepts. This study reads no signal date on or after 2026-08-11.

Resolved at build (2026-10-09), the state of each dependency:

| # | State on 2026-10-09 |
|---|---|
| 1 | Done 2026-09-24, commission-only, because the operator fills spreads at the mid |
| 2 | Met on the 2026-10-06 exports: 776 of 776 ladder-eligible candidates carry `cost_total` and `cost_basis` (`commission_only`). Gate R1 still checks every taken position at run time |
| 3 | Done by the same re-price |
| 4 | Not taken by the operator. Under the 2026-10-09 policy this study does not wait; it already runs the registered and the tracked cells side by side |
| 5 | Decided. The seal starts on 2026-09-23. This file was accepted after 2026-10-08, so it reads signal dates up to 2026-09-22 only |

The seal's own date replaces the 2026-08-11 line in item 5.

## Population and basis, fixed here

- **Era.** The current era, resolved by `lib/era.py`. The report header names
  it. A wrong or thin era is refused (exit 3 / exit 2), never worked around.
- **Decision population.** PRIMARY dense episodes, as `account_sim` defines
  them (`episode_max_gap` 5, `episode_min_dates` 10), concatenated in date order
  into one session series. Empty sessions inside an episode are kept, because
  they carry the book's real signal density.
- **Check population.** SECONDARY, the full sparse book. A cell must meet the
  bounds on both populations to be chosen. SECONDARY holds the
  2025-11 → 2026-03 drawdown that PRIMARY never saw.
- **Control.** `--era v3`, printed and never read by the decision. It is the
  same market path with different plays: a composition control, not an
  out-of-sample test.
- **Account.** $25,000 fixed base, 2% max-loss budget, three positions per day,
  cash enforced, frozen exits. This is `config/account-sim.yml`'s account block,
  read as it stands at acceptance and printed verbatim. The declared secondary
  changes only the budget and stop, to $1,000 each.

### Resampling method

A **stationary block bootstrap** (Politis and Romano 1994) over sessions. The
account walk is re-run on every resampled path.

- **The unit is a session**, carrying its ranked candidate list (it may be
  empty). Each candidate carries its outcomes relative to its entry session:
  exit offset, exit reason, and daily marks, at any contract count, from the
  frozen harness.
- **A path** is H sessions, assembled from blocks whose lengths are geometric
  with mean L. A block starts at a uniform session and wraps from the end of the
  series back to the start.
- **Positions travel with their entry session.** A position keeps its own exit
  offset and marks, even past its block's end. So L must be long relative to
  the holding period.
- **The ledger is re-simulated**, not re-ordered. `account_sim.simulate()`
  walks each path with the cell's caps, sizing and guardrail, so sizing, cap
  refusals, cash and the dollar stop all respond to the resampled order (unlike
  `lib/path_bootstrap.py`, its caveat (a)).

Resolved at build (2026-10-09), how the resample is built:

- **The walk.** A vectorised copy of `simulate()`'s ARM R loop walks every path,
  in `lib/ruin_walk.py`. Gate R2 proves it reproduces `simulate()` on the
  realized walk for every cell.
- **Identity.** At L equal to the series length the path is the series itself,
  taken in order from its first session. That is the walk R2 compares.
- **O3's resample** draws blocks from the sub-series of sessions that carry a
  candidate list, so a block runs over consecutive signal sessions. The path is
  still H sessions long.

### Block length

- **Primary L** = max(20, p75 of held sessions on the realized walk, rounded up
  to a multiple of 5) sessions. The p75 is printed before any result.
- **Sensitivity L** = half and 1.5 × the primary L, rounded to a multiple of 5.
- The decision must hold at every L where H / L ≥ 8. A cell that passes at one
  such L and fails at another is not eligible.
- If H / L < 8 at some L, that L is printed, labelled too few blocks, and not
  read.
- If H / L < 8 at the primary L, the verdict is `UNDERPOWERED`.

Resolved at build (2026-10-09):

- **The realized walk the p75 is read from** is the registered headline cell,
  N150-F1 with no guardrail, on PRIMARY, at the headline budget. One L serves
  every configuration, both populations and both budgets, so the cells stay on
  common random numbers.
- **Rounding.** Every L is rounded up to a multiple of 5. So half of 45 becomes
  25, not 20.

### Draws and seed

- 5,000 paths per configuration per overlay.
- One seed, set at acceptance as the registration date in `YYYYMMDD` form. The
  same index stream drives every cell, so cells are compared on common random
  numbers. Their percentiles are correlated and are never differenced as if
  independent.
- Resolved at build (2026-10-09): the seed is **20261009**. O0, O1 and O2 share
  one index stream per budget, population and L. O3 has its own stream, because
  it draws from a different set of sessions.

## Plan-time observations, disclosed

These figures were known while designing this study, measured on pre-cost
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

Resolved at build (2026-10-09), what else was known before the first run. These
came from the census while the module was built, on the 2026-10-06 exports,
before any outcome figure of this study existed.

| Fact | Value |
|---|---|
| Book rows / signal dates, through 2026-09-22 | 1,850 / 280 |
| PRIMARY dense episodes | 9 |
| Ladder-eligible candidates carrying a cost | 776 of 776 |
| p75 of held sessions, N150-F1 realized walk, PRIMARY | 45 |
| A1 on the 1.50 cell, 2026-09-28 book | fails, CI crossing zero ([next-steps item 5](../../next-steps.md#waiting-on-the-operator)) |

Clause B6 needs A1, so a cell that fails it cannot be chosen however the
resample reads.

The [feasibility plan's](../../account-sim-feasibility-plan.md) trial ledger
already holds more than 70 configurations scored against the 25% bar on this
one path. This study adds 24 configurations and three new guardrail arms, which
uses the plan's cap of three new arms on this era.

## What it compares

Every configuration is a cap cell × a guardrail, run under each overlay. All 24
are reported. One is chosen by the rule under
[Bar for a candidate](#bar-for-a-candidate), or none is.

### The cap cells

The per-position cap is fixed at 0.25 × equity. Net cap and floor vary. All
three net values are already on `account_sim`'s registered grid; no new cap
value is introduced.

| Cell | Net cap | Floor ([F1 vs F2](../../glossary.md#f1-vs-f2)) |
|---|---|---|
| N100-F1 | 1.00 | F1, take the one-contract floor |
| N150-F1 | 1.50 | F1, the `account_sim` registered headline |
| N250-F1 | 2.50 | F1, the tracked config since 2026-08-13 |
| N100-F2 | 1.00 | F2, refuse a pick whose one contract exceeds the budget |
| N150-F2 | 1.50 | F2 |
| N250-F2 | 2.50 | F2 |

ARM R (reject) runs throughout; ARM D and ARM H are not re-run here.

### The guardrails

Three new arms plus none. Each reads only equity and positions as of the close
of the session it acts on, never anything later.

| Guardrail | Rule | Value, resolved at build (2026-10-09) |
|---|---|---|
| G-none | No guardrail beyond the cell's caps | — |
| G-M, max open risk | Refuse a new position if total reserved capital would exceed `m` × current MTM equity | `m` = 0.50. Half the account at risk at once is the most a single bad week may cost |
| G-K, kill switch | Stop all new entries for the rest of H once MTM equity is `k` below its running peak; open positions run to their shipped exits | `k` = 0.25. It fires at A3's own drawdown bar, well before the ruin line |
| G-C, circuit breaker | After a session whose MTM loss is at least `c` × equity, take no new entries for the next `b` sessions | `c` = 0.05, `b` = 5. A 5% day is a market shock on this book; one week out lets it settle |

Resolved at build (2026-10-09), when each guardrail reads equity:

- Entries fill at the next open. So a guardrail acting on session t reads the
  marked equity at the close of session t − 1. Session 0 reads starting capital.
- G-K's `k` is a fraction of the running peak of marked equity, which starts at
  capital. That is the convention ARM D's throttle uses.
- G-C's loss is the drop from the close of t − 1 to the close of t, as a
  fraction of equity at t − 1. The pause covers sessions t + 1 to t + `b`.
- G-M counts reserved capital after the session's earlier entries. A refused
  pick does not use one of the three daily slots, as a cap refusal does not.
- G-K and G-C block every entry while they are on.

Further rules:

- **G-M**: when `account_sim` was registered, reserved over equity had a median
  of 0.27 and a p90 of 0.83 on the unconstrained book. The run prints the
  current distribution first.
- **G-K** is the operator's "clear guardrail against ruin". It never restarts
  inside H, because a restart is an operator decision. A peak-keyed trigger can
  miss a slow drawdown ([lessons](../../lessons.md)), so the report counts the
  paths where ruin happened without G-K firing.

### Stress overlays

| Overlay | What it does | Value, resolved at build (2026-10-09) |
|---|---|---|
| O0 | None. The resample alone | — |
| O1, correlated gap | Once per path, at the session with the most reserved capital, every open long-delta position loses the smaller of its max loss and its absolute delta-notional × `g`. Short-delta gains are not credited | `g` = 0.10, about the 2020-03-16 S&P 500 close-to-close fall, the worst day outside the sample's window |
| O2, total loss | At the same session, every open position loses its full max loss. The defined-risk ceiling, deterministic per path | — |
| O3, live density | Resample only from sessions that carry a candidate list, so every session emits | — |

O1 puts the gap at the worst moment on purpose; a random placement would average
the shock away.

Resolved at build (2026-10-09), how a shock lands:

- The session is found on the same path's O0 walk: the first session where
  reserved capital, after that session's entries, is at its path maximum. The
  path is then walked again with the shock, so the guardrails and cash respond.
- The shock hits every position open at that session's close, including those
  entered that day and those exiting that day.
- Under O1 the loss is subtracted from the position's mark from that session
  on, and from its booked dollars at exit. Neither may go below minus its max
  loss.
- Under O2 the position is marked at minus its max loss from that session on,
  and books that at its own exit.
- Positions keep their own exit sessions, so a shocked position holds its
  reserve until it closes.
- The O2 loss in clause B5 is the drop in marked equity the shock causes, over
  marked equity just before it.

## How it is judged

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
  the post-model cost columns (`cost_total`, `cost_basis`). Anything below 100%
  refuses the run.
- **R2 — identity.** With L equal to the series length, no guardrail and no
  overlay, the resampled walk reproduces `account_sim`'s realized walk for the
  same cell: the same positions, dollars and max drawdown. Resolved at build
  (2026-10-09): for each of the six cells it compares the positions taken (row,
  contracts, dollars, exit reason), the realized max drawdown, and the marked
  max drawdown from `mtm_curve.book_curves`. The marked figure may differ by one
  cent per contract, the `daily_pnl_csv` write resolution.
- **R3 — ledger.** On every path, at every session, `cash + Σreserved ==
  capital + Σrealized` (the `account_sim` G3 identity), and reserved never
  exceeds equity. Resolved at build (2026-10-09): "equity"
  here is `capital + realized`; see the margin-call proxy under [Ruin](#ruin).
- **R4 — outcome blindness.** Guardrails and selection read no outcome field.
  This reuses `account_sim`'s G5 blind-record check. Resolved at build
  (2026-10-09): R4 runs `account_sim`'s G2-G5 on both budget bases. It adds a
  truncation check: on every realized walk, every outcome after a cut session is
  scrambled, and no entry decision up to that session may change.
- **R5 — overlay order.** A violation is a bug, not a finding. Resolved at build
  (2026-10-09): R5 is checked path by path, up to the
  shock. The three walks are the same until the shock session, and the shock
  only lowers equity. So on every shocked path, equity at the shock must be
  O2 ≤ O1 ≤ O0. Ruin by the shock under O0 must imply it under O1, then O2. Any
  break is a bug.
  - The full-H order, P(ruin) under O2 ≥ O1 ≥ O0 for every configuration, is
    printed as a disclosure that gates nothing. It is not a property of a
    correct walk: after the shock, cash is lower and G-M refuses more, which can
    avert a ruin O0 runs into later. The 100-path smoke run showed it in 2 of
    288 cells, both G-M.

## Bar for a candidate

A configuration is **eligible** only if every clause below holds, at every
readable block length, on both PRIMARY and SECONDARY.

| Clause | Test | Bound, resolved at build (2026-10-09) | Reason in one line |
|---|---|---|---|
| B1 ruin, base | P(ruin within H) under O0 ≤ `p_ruin` | `p_ruin` = 0.01 | One history in a hundred losing half the account is the most a plan should carry |
| B2 ruin, stressed | P(ruin within H) under O1 and O3 ≤ `p_ruin_stress` | `p_ruin_stress` = 0.05 | A shock the sample never held may cost more, but not one path in twenty |
| B3 typical bad case | p95 MTM max drawdown under O0 ≤ `D95` | `D95` = 0.30 | Five points past A3's 25% bar is the deeper drawdown the operator asked to accept |
| B4 severe case | p99 MTM max drawdown under O0 ≤ `D99` | `D99` = 0.45 | Short of the 50% ruin line, so a p99 path can still be traded |
| B5 defined-risk ceiling | p99 O2 loss ≤ `R_max` of equity | `R_max` = 0.60 | A total-loss day may not cost more than 60% of equity, so that day alone does not ruin a healthy account |
| B6 edge | `account_sim` A1 holds on the realized walk, unchanged | — | — |

Resolved at build (2026-10-09): the same bounds apply to the declared $1,000
secondary. Only the budget changes there, never a bound. `D95` is the "accept a
worse drawdown" the operator asked for.

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

Resolved at build (2026-10-09):

- **"Riskier"** means a higher p95 marked max drawdown than S, under O0, at the
  primary L, on PRIMARY.
- **The advantage in step 2** must be positive: the CI's lower end is above
  zero. A CI wholly below zero excludes zero too, but it is a disadvantage.
- **The step 2 rows** are one per PRIMARY signal date carrying a candidate. A
  configuration's figure for a date is the net dollars of the positions it
  entered on that date, 0 when it entered none.
- **Ties in step 1** go to the earlier configuration in the arms order above.

Step 2 reads the realized walk, not the resample, on purpose: a resampled
return gap is nearly the realized gap repeated 5,000 times.

## Verdicts, worded now

| Token | Meaning |
|---|---|
| `RISKIER CELL EARNS ITS DRAWDOWN: <config>` | A configuration other than S passed step 2 and was chosen |
| `SAFEST ELIGIBLE CELL: <config>` | S was eligible and nothing riskier earned its drawdown |
| `NO CELL MEETS THE BOUNDS` | No configuration is eligible. The answer then points at capital, through the capital adequacy census, never at looser bounds |
| `UNDERPOWERED` | H / L < 8 at the primary L on PRIMARY. Nothing is chosen |

Resolved at build (2026-10-09): the report prints two verdict lines, each in the
wording above.

- `HEADLINE ($500 budget and stop): <verdict>` is the registered answer.
- `DECLARED SECONDARY ($1,000 budget and stop): <verdict>` runs the same rule on
  the operator's own sizing. It is a second reading, never a tie-break or a
  fallback for the headline.
- The v3 control prints the realized walk of every configuration, with no
  resample. No line of it is scored.

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

## What could ship

At most two things may ship, and only by the operator's hand after reading the
report.

- **The chosen cell's caps** into `config/account-sim.yml`. Production's
  exposure caps read that file, so this changes the live deploy card's cap
  check. The change carries a `Resolved at build` tag in the `account_sim`
  registration, naming this study's verdict.
- **The chosen guardrail**, if any, as an attention flag first. It is built in
  both `s03_risk.py` and `s04b_page.py` by hand, as the cap rule is. It becomes
  a hard stop only after a live-date read the operator registers separately.

Nothing ships on `NO CELL MEETS THE BOUNDS` or `UNDERPOWERED`. Nothing ships
before every dependency above has landed.

Resolved at build (2026-10-09): the first run is a reading for the operator. It
edits no file outside this study. The tracked cap in `config/account-sim.yml`
keeps its value whatever the verdict says. Either item above ships only if the
operator makes that change by hand.
