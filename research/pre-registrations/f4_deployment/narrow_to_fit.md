## narrow_to_fit — does narrowing an unaffordable spread beat refusing it?

_Registered 2026-10-01._

The operator accepted this file and answered its open decisions on the same
day. The answers are folded into the text and listed under
[Rulings at acceptance](#rulings-at-acceptance).

## Question

When a pick's one-contract max loss is over budget, is it better to narrow
the spread until it fits, or to refuse it?

[`account_sim`](../../arm-index.md#account_sim) offers two answers today, and
neither is what the operator does.

- **[F1](../../glossary.md#f1-vs-f2)** takes the pick at one contract, over
  budget. It is the registered headline.
- **F2** refuses the pick.
- **The operator** keeps the pick and substitutes strikes so it fits, and
  closes it on a $1,000 loss rather than sizing off a $500 max loss (operator,
  2026-10-01).

On the 2026-09-28 book F2 beats F1 heavily, but F2 refuses 68% of the
candidates it sizes. That result mixes two effects:

1. **Affordability.** One oversized contract per pick drives the drawdown.
2. **Selection.** The wide spreads F2 refuses were bad trades.

Narrowing separates them. A narrowed pick keeps the ticker, the direction,
the expiry and the leg the tier rule keys on, at a size the budget affords.

- If the narrowed picks still earn, the problem was affordability and
  refusing them throws away edge.
- If they lose, F2's gain came from refusing bad trades, and F2 stays a
  post-hoc result.

The headline budget is $1,000, the operator's real stop. The operator closes
a spread on a $1,000 loss and called a $500 max-loss bound "very
conservative". The $500 cells are reported beside it as comparators.

A second question rides along: does the $1,000 stop, rather than the $500
budget, change the account's feasibility?

## What this is NOT

- **Not an edge search.** Selection is frozen (`protocol.top_k_per_day`,
  `ladder_rank`, `ladder_eligible`). So are the exits (the shipped profiles,
  [§5](../../../docs/deployment-rules.md#s5)) and the replay harness
  (`lib/harness.py`). Narrowing changes the strikes of a pick the ladder
  already chose; it never adds or removes a pick.
- **Not a budget sweep.** Exactly two budgets run. The smaller is the
  registered 2% of capital. The larger is the operator's stated dollar stop,
  which is also the frozen harness's own `MAX_LOSS_ABS`. Neither is adopted
  on its P&L.
- **Not a re-run of the feasibility plan's knob table.** That table moved the
  risk percentage down and so moved the stop with it
  ([feasibility plan](../../account-sim-feasibility-plan.md#what-the-investigation-found)).
  Here the stop and the sizing budget are separated by cell `F4`, so a stop
  effect cannot pass as a sizing effect.
- **Not ARM D.** Downsizing on a cap breach is `account_sim`'s
  [ARM D](../../arm-index.md#account_sim). Every cell here runs under ARM R
  (reject on a cap breach), to keep the trial count down.

## Definitions

### Sizing today, stated exactly

Every `account_sim` cell sizes on a [MAX-LOSS
basis](../../glossary.md#max-loss-budget-sizing):

```
contracts = max(1, int(budget / max_loss_per_contract))      # risk_contracts()
budget    = capital × risk_per_trade_pct = $25,000 × 0.02 = $500
stop      = budget                                            # Cfg.stop
```

`max_loss_per_contract` is `entry_net × 100` on debit rows. On credit rows it
is the width less the credit, the broker-margin figure. F1 keeps the
`max(1, …)` floor. F2 refuses any pick where `max_loss_per_contract > budget`
(census bucket `min1_refusal`).

Reserved capital is `contracts × max_loss_per_contract`, held from the entry
session through the exit session.

### The dollar stop, stated exactly

The frozen harness carries one position-level [dollar
stop](../../glossary.md#dollar_stop), `MAX_LOSS_ABS = $1,000`. It fires when
the position's dollars at the daily close reach −$1,000. `account_sim` applies
any other stop through a scaling identity (`replay_sized`):

- Replay the row at `contracts × (1000 / stop)` contracts, then divide the
  dollars by the same factor.
- The factor is 2 at the $500 stop and 1 at the harness's own stop. Both are
  exact integers, and the code asserts it.
- Gate G2 calibrates the identity at factor 1 against the stored rows.

The stop is checked on daily closes, so a gap books more than the stop. On
the 2026-09-28 PRIMARY headline, 79 of 321 taken positions exited on the
dollar stop, with a worst loss of −$1,654.

**Consequence.** F1 already caps an oversized one-contract position at the
$500 stop. Its "budget breach" is a breach of max loss, not of realized loss.
The operator's complaint is that $500 is too tight for the spreads they hold,
not that F1 lets losses run.

### Narrow-to-fit (cell family `F3`)

For a pick whose one-contract max loss exceeds the budget:

1. **Keep** the ticker, the expiry, the right, and the anchor leg. The
   anchor leg is the leg the tier rule keys on: the bought leg of a debit
   vertical, the sold leg of a credit vertical (operator ruling 2).
2. **Move the other leg inward**, one listed strike at a time, starting from
   the proposed strike.
3. **Take the widest** listed strike at which one contract's max loss, priced
   from the entry-day fill, is at or under the budget.
4. **Size** the narrowed spread with the same `risk_contracts()` rule. It is
   one contract or more by construction.
5. **Refuse** the pick, bucket `narrow_no_fit`, if no listed strike between
   the two legs fits.
6. **Refuse** it, bucket `narrow_tier_break`, if the narrowed legs fail the
   pick's tier rule at entry. For a `bull_put_spread` that is the
   [§3](../../../docs/deployment-rules.md#s3) short-leg delta band, checked
   through `mapping.ladder_tier()`.
7. **Refuse** it, bucket `narrow_unpriced`, if the substitute leg has no
   usable price on the entry day or on any held session.

A pick that already fits is never touched, so on affordable picks `F3` and
F1 take the same trade.

A **listed** strike is one Barchart returns a history for, with a quote on
the entry day. The unlisted skip-list
(`backtests/option_history_cache/_unlisted.jsonl`) is not evidence: it holds
2,703 seeded entries that never passed the evidence gate
([entry](../../current.md#2026-09-29--operator-rulings-the-150-cell-and-the-2026-column)).
A network error, 403 or 5xx never marks a strike unlisted.

*Resolved at build (2026-10-07).* An expired contract whose page loads and
whose feed holds no rows is a strike Barchart returns no history for. It
counts as unlisted only when all three hold:

- it expired at least 7 days before the fetch, so its history is final;
- no fetch failure lies within two minutes of the answer;
- two separate runs gave the same answer (`n_checks >= 2`).

Until then it stays `unproven`. The 2026-10-07 scrape left 1,934 such
answers, which no earlier text ruled on.

*Resolved at build (2026-10-09).* The registered rule above, with no price
floor, stays the headline. A net floor prints beside it as a declared
secondary line, and it never changes a verdict.

- **The floored line.** The walk is the same. If the widest strike that fits
  gives a debit spread whose net debit is under 20% of its width, the pick is
  refused into `narrow_no_fit`, reason `below_net_floor`. The walk does not
  step on to a narrower strike.
- **Credit spreads are never floored.** A tiny credit leaves max loss near the
  width, so it cannot size up.
- **Why.** A near-zero net sizes to many contracts. MU 2026-09-21 fit at $0.06
  on a 40-wide spread and sized to 83 contracts
  ([next-steps §0, item 14](../../next-steps.md#pick-up)).
- **Where it prints.** Beside `(R, F3, $1,000)` and `(R, F3, $500)`, graded
  on the same N1–N5 and verdict table, and labelled declared secondary.
- **On this book it is seen, not tested.** The 20% was picked after item 14's
  in-sample read. Its clean test is the forward grade in
  [`refuse_floor_forward`](refuse_floor_forward.md#cells).
- **Fixed before any forward date priced.** On the 2026-10-06 exports no
  signal date on or after 2026-10-08 has a row, and no date on or after
  2026-09-23 has a priced one.

### Stop-decoupled floor (cell `F4`)

`F4` sizes like F1 at the $500 budget, but its dollar stop is $1,000. It
takes the floor as F1 does. Nothing in it is narrowed.

The operator's own description is "risk per contract = min(max loss, dollar
stop), size off that, stop at $1,000". When the budget equals the
stop, that rule is **exactly F1 at that budget**. Where max loss exceeds the
stop, both give one contract stopped at the stop. Below it, both give
`int(stop / max loss)`.
It is therefore registered once, as `(R, F1, $1,000)`, and not as a
duplicate cell.

`F4` is what the formula adds when the stop and the budget differ. It splits
the move from `(R, F1, $500)` to `(R, F1, $1,000)` into two steps:

| Step | What changes | Cells |
|---|---|---|
| Stop effect | Stop $500 → $1,000; contracts unchanged | `(R, F1, $500)` → `F4` |
| Size effect | Contracts on cheap spreads double; stop unchanged | `F4` → `(R, F1, $1,000)` |

## Dependencies

| Prerequisite | Why it binds | Cells it blocks |
|---|---|---|
| A `Cfg` stop field separate from the budget, in `account_sim.py` | Built 2026-10-01 as `Cfg.stop_abs` | none now |
| A floor rule with three values (take, refuse, narrow) on `Cfg` | `take_floor` is a bool today | `F3` |
| The substitute-leg scrape ([census](#substitute-leg-census)), not funded at acceptance | `F3` needs a priced substitute leg the cache does not hold | `F3` |
| The shared entry-fill and junk-mark functions in `scripts/backtest/simulate.py`, stable | `F3` prices the substitute leg through them (commit `237e7a5`) | `F3` |
| `backup_research_caches.py pull` on the run machine | The cache is the price source | all |

## Population and basis, fixed here

- **Era.** v4 (`current`), through `load_book(include_bs=False)`. The report
  header names the era. There is no v3 run (operator ruling 5).
- **The date count is not fixed here.** It is whatever the era resolves at
  run time.
- **PRIMARY and SECONDARY** are `account_sim`'s:
  [dense episodes and the full book](../../glossary.md#primary-dense-episodes-vs-secondary-full-book).
  PRIMARY carries the verdict. SECONDARY may block a verdict but never carries
  one alone.
- **The account** is `account_sim`'s: $25,000 starting capital, 3 positions a
  day, `ladder_rank` order, the same ledger and the same reserved-capital
  rule.
- **Cap cells.** The headline runs on the registered `(0.25, 1.50)` cell. The
  tracked `(0.25, 2.50)` cell runs as a robustness cell. A verdict must hold on
  both. This makes the open cap-cell decision
  ([next-steps, waiting item 5](../../next-steps.md#waiting-on-the-operator))
  irrelevant to the verdict.
- **Cost.** Commission only, the shipped basis since 2026-09-24. Slippage is 0
  because the operator fills spreads at mid. The substitute leg pays the same
  commission as any leg.
- **Rows `load_book` drops stay dropped.** A narrowed version of an
  unpriceable stored row is never built.

### Rulings at acceptance

Operator, 2026-10-01.

| # | Decision | Ruling |
|---|---|---|
| 1 | Headline budget | $1,000. `(R, F3, $1,000)` is the headline; `(R, F3, $500)` is secondary |
| 2 | Which leg moves on a credit spread | The long (protective) leg; the sold leg stays |
| 3 | Keep `F4` | Yes |
| 4 | Fund the substitute-leg scrape | Not now; asked separately. The `F3` cells wait on it |
| 5 | Run on v3 | No |
| 6 | Labels | `F3` and `F4` |
| 7 | Run the cached cells before the scrape | Yes |

## Plan-time observations, disclosed

Read on 2026-10-01 while drafting, from the 2026-09-27 exports and the
2026-09-28 `account_sim` report. **The F1 and F2 rows at $500 were seen
before this file was written.** Nothing at $1,000, and nothing narrowed, has
been run.

### What `account_sim` printed (PRIMARY, $500, ARM R)

| Object | Cap cell | n | Dates | Total | [meanR](../../glossary.md#meanr) | [maxDD](../../glossary.md#maxdd) |
|---|---|---|---|---|---|---|
| `account_sim` (R, F1) | 0.25, 2.50 | 321 | 170 | $6,860 | +0.106 | −$18,711 |
| `account_sim` (R, F2) | 0.25, 2.50 | 180 | 122 | $15,401 | +0.214 | −$2,800 |
| `account_sim` (R, F1) | 0.25, 1.50 | 226 | 135 | — | +0.099 | 50.4% of capital |

- **F2 refuses 455 of the 671 candidates it sizes** on the 2.50 cell.
- **(R, F2) meets A1, A2, A3, A4 and A6 and fails A5** on both cap cells
  ([entry](../../current.md#2026-09-29--operator-rulings-the-150-cell-and-the-2026-column)).
  Its A5 ratio moves +34 points on the ex-2025 Mar–Apr cut.
- **The 2026 loss is a credit tail.** The 12 worst 2026 rows are tier-B
  `bull_put_spread`. A narrower credit spread has a smaller tail, so `F3`
  may help through that route alone.

### Substitute-leg census

Offline, from the cache directory listing; no network was touched. The
candidates are every ladder-eligible pick the walk can reach on the full
book.

| Measure | $500 budget | $1,000 budget |
|---|---|---|
| Candidates, full book | 748 on 245 dates | 748 on 245 dates |
| One contract over budget | 514 | 262 |
| …of which `bull_call_spread` | 378 | 185 |
| …of which `bull_put_spread` | 136 | 77 |
| Over budget and not a two-leg vertical | 0 | 0 |
| Estimated target strike already cached | 187 | 80 |
| Estimated target strike not cached | 327 | 182 |
| Unique uncached target contracts | 297 | 168 |

| Scrape scope | Unique uncached contracts | At ~15 s each |
|---|---|---|
| Target strike only, both budgets | 462 | about 1.9 h |
| Target plus the next-wider strike, both budgets | 867 | about 3.6 h |
| Every strike between the legs, both budgets | 4,482 | about 18.7 h |

How to read it:

- **The target is an estimate.** It prices each strike with Black-Scholes at
  the legs' mean entry IV. The real choice uses entry-day fills, so the
  middle row is the realistic plan. It proves the chosen strike fits and the
  next-wider one does not.
- **The strike grid is inferred.** It is the finer of the cached strikes'
  spacing and a standard listing step by price, so some strikes it counts
  may not be listed.
- **The census moved the short leg on every row,** including credit spreads.
  Open decision 2 would move the long leg of a credit spread instead. That
  changes which put is fetched, not how many.
- **Coverage is not price.** A cached file can be range-truncated
  ([§2.11](../../next-steps.md#211-robustness-follow-ups--open-nothing-waits-on-dates)).
  A substitute counts as priced only if its history covers the held window.

## Arms

All cells run under `account_sim` ARM R. Each cell is one (floor rule, sizing
budget, dollar stop) triple.

| Object | Object type | Floor rule | Budget | Stop | Data | Role |
|---|---|---|---|---|---|---|
| `narrow_to_fit` (R, F3, $1,000) | cell | narrow | $1,000 | $1,000 | scrape | **HEADLINE** |
| `narrow_to_fit` (R, F1, $1,000) | cell | take | $1,000 | $1,000 | cached | the operator's stop-basis rule |
| `narrow_to_fit` (R, F2, $1,000) | control | refuse | $1,000 | $1,000 | cached | comparator at the headline budget |
| `narrow_to_fit` (R, F3, $500) | cell | narrow | $500 | $500 | scrape | secondary |
| `narrow_to_fit` (R, F1, $500) | control | take | $500 | $500 | cached | the registered `account_sim` headline |
| `narrow_to_fit` (R, F2, $500) | control | refuse | $500 | $500 | cached | the post-hoc result in question |
| `narrow_to_fit` F4 | cell | take | $500 | $1,000 | cached | the stop effect alone |

Three new objects enter the
[trial ledger](../../account-sim-feasibility-plan.md#phase-3--candidate-rules-one-registration),
which caps new arms on this era at three: the narrow rule `F3`, the $1,000
level, and the decoupled stop `F4`. The ledger is printed with every report.

*Resolved at build (2026-10-09).* Two declared secondary lines join the
table: `(R, F3, $1,000) + 20% net floor` and `(R, F3, $500) + 20% net floor`
([the floor](#narrow-to-fit-cell-family-f3)). They are not new arms and carry
no verdict. The ledger prints them as seen on this book.

## Unit and metric

- **Account metrics** are `account_sim`'s: total dollars, maxDD on the
  realized-on-close curve, and A1–A6 scored by the same `evaluate()`.
- **The narrowed subset** is the set of picks `F3` narrowed and took. Its
  metric is meanR on each position's own entry basis, with a date-clustered
  [CI](../../glossary.md#ci), `BOOT_N = 10000`, α = 0.05.
- **The paired contrast** puts each narrowed position beside the same pick
  under F1, using [R_dol](../../glossary.md#r_dol--e_dol) per pick.
  `protocol.boot_ci_paired_by_date` gives the CI. It prints and grades
  nothing.
- **Unit** is the signal date for every CI.

## Gates

Each gate exits non-zero on failure, except GN0 and GN5, which print.

- **G2–G5** are `account_sim`'s, unchanged, run on every cell that uses
  cached rows only.
- **GN0 POWER — prints.** The narrowed subset needs at least 25 dates and 60
  positions in PRIMARY. Below either, the cell prints `UNDERPOWERED` and its
  census, and Q2 is not graded.
- **GN1 REFUSE IDENTITY.** `F3` with every narrowing forced to refuse must
  reproduce `(R, F2)` at the same budget, position for position.
- **GN2 STOP IDENTITY.** `F4` with its stop set back to $500 must reproduce
  `(R, F1, $500)`, position for position. A pytest pins it on a synthetic
  book.
- **GN3 PRICING MIRROR.** The narrowed-spread builder, run at a stored row's
  own strikes, must reproduce that row's entry net and daily marks on every
  `commission_only` row it is tried on.
- **GN4 STRIKE BLINDNESS.** Every substitute history is truncated after its
  entry day and the strike choice re-run. The chosen strikes must be
  identical. This is the `account_sim` G5 idea applied to the chain.
- **GN5 COVERAGE — prints.** If more than 10% of the over-budget picks in
  PRIMARY end as `narrow_unpriced`, the `F3` cells print `AWAITING SCRAPE`
  with the census and grade nothing.
- **GN6 Nothing new, nothing hardcoded.** No annualised figure, Sharpe
  or time-to-recover. Every count is computed by the run.

## Bar for a candidate

Two questions, graded in this order on PRIMARY.

**Q1 — is the headline cell feasible?** `(R, F3, $1,000)` must meet all of:

- **N1** `account_sim`'s FEASIBLE: A1∧A2∧A3∧A5∧A6, on both cap cells.
- **N2 deflated bar.** The median max drawdown over the cell's own
  block-bootstrap paths (`lib/path_bootstrap.py`, block length 10) is at or
  under 25% of capital.
- **N3 transfer.** Take each drawdown window of `(R, F1, $500)` that reaches
  10% of capital or deeper. Inside every such window, the cell's own deepest
  drawdown is shallower. This holds on PRIMARY and SECONDARY.

**Q2 — do the narrowed picks earn?** The narrowed subset is the headline
cell's: picks whose one contract costs more than $1,000, narrowed and taken.

- **N4** meanR of the narrowed subset is above zero, CI excluding zero.
- **N5** it keeps its sign ex-2025 Mar–Apr and ex-2026 Feb–Apr
  ([window re-cuts](../../glossary.md#window-dominance-re-cuts)), and in
  every calendar year present with at least 10 narrowed positions.

**A5 window re-cuts are pre-committed** to the two `account_sim` already uses,
`ex-2025_mar_apr` and `ex-2026_feb_apr`, from `protocol.window_cuts`. No other
window is cut.

**`(R, F3, $500)`** is graded on N1–N5 and prints its own verdict line from
the table below. **`(R, F1, $1,000)` and `F4`** are graded on N1–N3 and print
the stop-basis line. None of them changes the headline verdict.
*Resolved at build (2026-10-09):* each floored F3 line is graded on N1–N5
like its cell and prints its own verdict line beside it.

## Verdicts, worded now

| Verdict | When | What it means |
|---|---|---|
| **NARROW-FEASIBLE** | Q1 and Q2 both pass | Narrowing keeps the edge and the account survives at the $1,000 budget. Refusing these picks throws away edge |
| **AFFORDABILITY** | Q2 passes, Q1 fails | The narrowed picks earn, but the account still fails a bar |
| **SELECTION** | N4's CI sits wholly at or below zero | The over-budget picks were bad trades; F2's gain was selection, and F2 stays post-hoc |
| **NULL** | N4's CI straddles zero, GN0 passes | Narrowing neither rescues nor condemns the refused picks; Q1 prints as a line, not a verdict |
| **UNDERPOWERED** | GN0 stops Q2 | Census only |
| **AWAITING SCRAPE** | GN5 fires | Census only; the fix is the scrape, never a lower gate |

Expected outcome, written now: no strong prior. The 2026 credit tail argues
for AFFORDABILITY. F2's drawdown gain being so much larger than its meanR gain
argues that floor size, not pick quality, drove F1's losses.

The stop-basis line reads one of three ways for each of
`(R, F1, $1,000)` and `F4`:

- **STOP-FEASIBLE** — N1–N3 pass.
- **STOP-HURTS** — maxDD is deeper than `(R, F1, $500)`'s on PRIMARY.
- **NOT FEASIBLE** — anything else.

## Anti-tuning

- **The cells are fixed at seven,** as tabled under [Arms](#arms). No other
  budget, no other stop, and no D cells. A new cell is a new registration.
  *Resolved at build (2026-10-09):* the two floored F3 lines are declared
  secondaries, not cells. The floor share is fixed at 20% and is not re-tuned.
- **A cell is never adopted on its P&L.** A verdict is read from the bar
  above, never from comparing totals across cells.
- **The strike rule is fixed:** widest that fits, from entry-day fills. It is
  not re-tuned to "nearest the original delta" or "narrowest" after a run.
- **No v3 run.** The feasibility plan's v3 transfer clause does not apply to
  this study (operator ruling 5).
- **Forward read.** Signal dates after acceptance are scored once the
  `holdout_seal` decision allows, with at least 15 dates. A NARROW-FEASIBLE
  verdict is not acted on before that read keeps its sign.

## Ship criteria

Nothing ships from this study directly. A NARROW-FEASIBLE verdict, confirmed
by the forward read, lets the operator consider a deploy-card rule: "narrow an
unaffordable spread to fit; refuse if nothing fits". That rule would need its
own [§2](../../../docs/deployment-rules.md#s2) change, a rollback trigger, and
a `deployment-evidence.md` entry in the same commit. A STOP-FEASIBLE line
licenses nothing; it informs the operator's choice of budget.

## Build notes

Not part of the registration.

### Pitfalls, fixed in advance

- **Lookahead in the strike choice.** The choice reads the entry-day fill of
  each candidate strike, through `simulate.entry_day_fill` and
  `open_print_allowed`, and nothing later. A strike whose history is short
  after entry is never skipped for one whose history is complete; that pick
  is `narrow_unpriced`. GN4 checks it.
- **Junk quotes.** The substitute leg goes through `junk_day_mark` and
  `last_good_mark`, imported from `scripts/backtest/simulate.py`, never
  copied. A debit priced to a credit is refused, as in production.
- **Exits on a different shape.** The shipped profile applies unchanged, as
  fractions of the narrowed position's own entry net. A narrowed debit spread
  whose max gain is under 0.90 of its debit can never reach the profit
  target. The report prints how many positions this hits. Nothing re-keys
  the target.
- **Delta-notional.** The narrowed position's delta is the anchor leg's
  stored delta plus the substitute leg's entry-day `Delta` from the cache,
  with Black-Scholes only when the cache has none. It feeds both caps.
- **Breakeven moves.** A narrower debit spread breaks even at a lower price
  for a call; the report prints the median breakeven shift. It grades
  nothing.

### Running the cached cells

- **`(R, F1, $1,000)` and `(R, F2, $1,000)` run** with no code
  change: a copied config with `risk_per_trade_pct: 0.04`. The scaling factor
  is then 1, which is exact. A `--config` run overwrites the default
  artifacts, so follow the copy-aside and diff procedure in
  `docs/architecture.md` §account_sim.
- **`F4` needs no new data.** Its replay is `replay_sized(rec, c, 1000)` on
  the existing marks. It runs through a copied config with the optional
  `account.dollar_stop: 1000`, which sets `Cfg.stop_abs`. Absent or null, the
  stop is the budget and the default report is unchanged.
- **`F3` needs the scrape** in the census. Fetch the target strike and the
  next-wider strike per pick first, about 867 contracts for both budgets.
  Run `backup_research_caches.py push` after it.

### Module

A new `f4_deployment/narrow_to_fit.py` that imports `account_sim.simulate`
and adds the narrow floor rule. The stop field already lives on `Cfg`. It writes its own report stem, so no
`account_sim` artifact is overwritten. Arm labels go to
[`arm-index.md`](../../arm-index.md#narrow_to_fit).
