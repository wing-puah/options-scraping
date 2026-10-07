## refuse_floor_forward — do refusing and narrowing an unaffordable pick hold up on new dates?

_Registered 2026-10-07. First forward date 2026-10-08._

The operator accepted this file on 2026-10-07 and answered its ten open
decisions with the recommended option. The answers are folded into the text
and listed under [Answers, 2026-10-07](#answers-2026-10-07).

**What this file sets up.** Two registered cells become standing candidates,
graded on every suite run alongside the other studies:

- `account_sim`'s F2, which refuses an unaffordable pick;
- `narrow_to_fit`'s `(R, F3, $500)`, which narrows it until it fits.

Each grade reads only signal dates from 2026-10-08 onward, through a
confidence sequence that stays valid however often it is looked at. Nothing
ships from it directly.

The operator's ruling, 2026-10-06: "keep it [F2] as something that will
continuously be graded with the rest of the strategies." On 2026-10-07 the
operator added `(R, F3, $500)` as a second graded cell, after it printed
`NARROW-FEASIBLE` as `narrow_to_fit`'s secondary.

## Question

On signal dates that arrive after this file was accepted, does each of two
cells keep a positive mean R and a survivable drawdown?

- [`account_sim`](../../arm-index.md#account_sim)'s cell
  [F2](../../glossary.md#f1-vs-f2): refuse any pick whose one-contract max
  loss exceeds the budget.
- [`narrow_to_fit`](../../arm-index.md#narrow_to_fit)'s cell `(R, F3, $500)`:
  narrow such a pick to the widest listed spread that fits the budget, and
  refuse it if none fits.

Both look good on the current book, but both were seen before anyone named
them candidates. The current book has no unread dates left, so only new dates
can confirm them.

## What this is NOT

- **Not a new arm.** F2 is `account_sim`'s own registered cell, defined in
  its [registration](account_sim.md) on 2026-08-13. `(R, F3, $500)` is
  `narrow_to_fit`'s registered secondary, defined in its
  [registration](narrow_to_fit.md) on 2026-10-01. Nothing about how either
  sizes, refuses, narrows, exits or ranks changes here.
- **Not a grade on dates already read.** The forward statistic never pools a
  date from before 2026-10-08. That book is printed beside it as context.
- **Not an edge search.** Selection
  (`protocol.top_k_per_day(book, ladder_rank, k=3, ladder_eligible)`), the
  exits ([§5](../../../docs/deployment-rules.md#s5)) and the frozen replay
  harness (`lib/harness.py`) are all unchanged.
- **Not a ship.** A confirmed grade lets the operator consider a rule change.
  It changes nothing by itself.
- **Not a decay monitor.** The grade asks whether each cell's forward mean is
  positive. A rule that later stops working is caught by its rollback
  trigger, written when the rule ships.

## The trial ledger

The [trial ledger](../../account-sim-feasibility-plan.md#phase-3--candidate-rules-one-registration)
caps new arms "on this era" at three, and
[`narrow_to_fit`](narrow_to_fit.md) spent them (`F3`, the $1,000 level,
`F4`). This file adds no arm, so it is outside that cap:

- The ledger's stated reason is that "more than 70 configurations have been
  scored against the 25% bar on this one path". Forward dates are a different
  path. No configuration has been scored on them.
- F2 is one of `account_sim`'s four registered cells.
- `(R, F3, $500)` is one of `narrow_to_fit`'s seven registered cells, and the
  narrow rule `F3` is already one of the three arms the ledger counts.

A literal reading of "this era" would block the file, because forward dates
are era v4. The operator ruled that the cap does not bind forward dates
([answer 1](#answers-2026-10-07)).

## Definitions

### F2, stated exactly

From `scripts/backtest_study/f4_deployment/account_sim.py::simulate`:

```
contracts = max(1, int(budget / max_loss_per_contract))      # risk_contracts()
if max_loss_per_contract > budget and not take_floor:        # F2: take_floor=False
    census["min1_refusal"] += 1                              # refused, logged
    continue                                                 # the slot is NOT used
```

- `budget` is $25,000 × 0.02 = $500. The dollar stop equals the budget.
- `max_loss_per_contract` is `entry_net × 100` on a debit row. On a credit
  row it is the width less the credit.
- **A refused pick does not use one of the day's three slots.** The next
  ladder-eligible candidate in `ladder_rank` order is considered in its place.
  An unsizable pick, by contrast, does use its slot. A rule written from this
  file must say the same thing.
- Every other step is `account_sim` [ARM R](../../arm-index.md#account_sim):
  a cap breach rejects the pick.

### F3 at $500, stated exactly

`(R, F3, $500)` is `narrow_to_fit`'s
[narrow-to-fit rule](narrow_to_fit.md#narrow-to-fit-cell-family-f3) at the
$500 budget and the $500 stop, under ARM R. In short:

1. A pick whose one-contract max loss is at or under $500 is taken as F1
   takes it.
2. An over-budget pick keeps its ticker, expiry, right and anchor leg, and its
   other leg moves inward to the widest listed strike at which one contract,
   priced from the entry-day fill, fits $500.
3. It is refused into `narrow_no_fit`, `narrow_tier_break` or
   `narrow_unpriced` when nothing fits, the tier changes, or the substitute
   leg has no usable price.

**A refused pick does not use a slot**, as in F2. The strike rule, the tier
check, the listed-strike evidence and the refusal buckets are
`narrow_to_fit`'s. This study imports them (`Narrower`, `Chain`,
`unlisted_evidence`) and never re-implements them.

An empty feed for an expired contract counts as evidence that a strike is
unlisted only under `narrow_to_fit`'s rule resolved at build on 2026-10-07:
it expired at least 7 days before the fetch, no fetch failure lies within two
minutes of the answer, and two separate runs agree (`n_checks >= 2`).

### Substitute legs on forward dates

F3 needs substitute-leg histories that the cache does not hold for a new
date.

- **Before an F3 look**, `scripts/collector/fetch_substitute_legs.py --scope
  between` is run on the current exports. It fetches only uncached strikes,
  so in practice it fetches the forward dates' substitute legs.
- **Coverage, per look.** `narrow_to_fit`'s GN5 rule applies to the forward
  F3 cell: if more than 10% of the over-budget PRIMARY picks end
  `narrow_unpriced`, read on the (0.25, 1.50) cap cell as in
  `narrow_to_fit`, both F3 cap cells print `AWAITING SCRAPE` for that look.
- **That look only.** F2 is still graded on it, and the next look tests
  coverage again. The fix is the scrape, never a lower bar.

### `account_sim`'s criteria, for reference

They are computed by `criteria_scores()`, the one body `evaluate()` uses.
Under [The grade](#the-grade) they are either replaced by a sequential
version or printed as context.

| Criterion | What it computes |
|---|---|
| A1 | meanR over taken positions > 0, date-clustered 95% [CI](../../glossary.md#ci) excluding zero, mean positive in every calendar year present |
| A2 | Constrained dollars ÷ B2's dollars on the constrained run's own dates, at least 60% |
| A3 | No ledger over-reservation, and realized-on-close [maxDD](../../glossary.md#maxdd) at most 25% of $25,000 |
| A4 | Every exclusion attributes to exactly one census bucket and the counts sum |
| A5 | The A2 ratio moves at most 15 points under each [window re-cut](../../glossary.md#window-dominance-re-cuts) |
| A6 | A1 on the debit-only subset |

**B2** is the unconstrained $25,000 book on [max-loss
sizing](../../glossary.md#max-loss-budget-sizing). It keeps the one-contract
floor on every cell. So a cell's A2 compares it with a book that still takes
the picks the cell refuses or narrows. That denominator question is
unresolved in the
[feasibility plan](../../account-sim-feasibility-plan.md#what-is-unresolved).

## Population and basis, fixed here

### The forward population

**Every v4 signal date from 2026-10-08 onward.** It has no closing date.

Dates before 2026-10-08 are excluded because they have been read, or will be
read by the export re-pull and suite runs. The census below shows it.

### Why the post-2026-08-11 dates are not forward dates

The feasibility plan calls the post-2026-08-11 live dates "the only unspent
population". On the current exports that is no longer true. A census of the
2026-09-27 exports, counts only:

| Export (2026-09-27 15:57) | Rows on signal dates ≥ 2026-08-11 | Last signal date |
|---|---|---|
| `BacktestResults` | 113 | 2026-09-22 |
| `BacktestProxy` | 217 | 2026-09-23 |
| `AnalysisClaude` | 384 | 2026-09-25 |

Those rows have already been read with outcomes:

| Run | What it printed on those dates |
|---|---|
| `account_sim`, 2026-09-28 | Dense episode E9, 2026-08-11 → 2026-09-22, 29 dates, 64 deployed picks, inside PRIMARY. Every F1 and F2 row in that report includes them |
| 2026-09-29 entry, the 2026 column | Tier A+B meanR for 2026, 229 rows, including these dates. It names GLD (signal 2026-09-18) and FSLR (signal 2026-09-15) rows individually |
| 2026-09-29, the 1.50 cell re-run | The same book as 2026-09-28 |
| `narrow_to_fit` cached cells, 2026-10-01 | The same E9 episode, on all six sections |
| `narrow_to_fit` graded run, 2026-10-07 | Every F3 row, on the 2026-10-06 exports, through 2026-09-22 |

The handoff's redo list ([next-steps §0](../../next-steps.md#pick-up))
re-prices 2026-08-25, 2026-09-15 and 2026-09-18. A redo re-prices a date
that was already read, so it does not make the date unread.

Dates from 2026-09-26 to 2026-10-07 are in no export today. They will enter
one when the exports are re-pulled, and the suite will read them then, so
they are not forward dates ([answer 2](#answers-2026-10-07)).

### What the forward population holds

- **Era.** v4, loaded through `load_book(include_bs=False)`, real and
  `strike_expiry_tweak` rows only. Dates from two prompt versions are never
  pooled. A version bump freezes the grade at the last v4 date
  ([answer 9](#answers-2026-10-07)).
- **The account starts fresh.** $25,000 and an empty ledger on the first
  forward date. No position is carried in from before it.
- **PRIMARY and SECONDARY** are `account_sim`'s
  [dense episodes and full book](../../glossary.md#primary-dense-episodes-vs-secondary-full-book),
  restricted to forward dates. Live dates arrive daily, so the two will often
  be identical. PRIMARY carries the grade.
- **Cost.** Commission only, the shipped basis since 2026-09-24. Slippage is
  0, because the operator fills spreads at mid. A substitute leg pays the same
  commission as any leg.
- **Entry.** The production entry rule in force at each look, including the
  5-trading-day entry window (`stale_leg_at_entry`) ruled on 2026-10-01.
- **Rows `load_book` drops stay dropped.** Every look prints the drop counts
  for forward dates. A narrowed version of a dropped row is never built.

### Cells

| Object | Object type | Floor rule | Budget | Cap cell | Role |
|---|---|---|---|---|---|
| `refuse_floor_forward` (R, F2, $500) | cell | refuse | $500 | (0.25, 1.50) | **HEADLINE**, registered cap cell |
| `refuse_floor_forward` (R, F2, $500) | cell | refuse | $500 | (0.25, 2.50) | **HEADLINE**, tracked cap cell |
| `refuse_floor_forward` (R, F3, $500) | cell | narrow | $500 | (0.25, 1.50) | **HEADLINE**, registered cap cell |
| `refuse_floor_forward` (R, F3, $500) | cell | narrow | $500 | (0.25, 2.50) | **HEADLINE**, tracked cap cell |
| `refuse_floor_forward` (R, F1, $500) | control | take | $500 | both | `account_sim`'s headline; the transfer comparator |
| `refuse_floor_forward` (R, F2, $1,000) | control | refuse | $1,000 | both | Printed, not graded ([answer 7](#answers-2026-10-07)) |

F2 and F3 are two graded cells, and each gets its own verdict line. Neither
verdict moves the other.

**Each cell's grade must hold on both cap cells.** Which cap cell the tracked
config carries is still open
([next-steps, waiting item 5](../../next-steps.md#waiting-on-the-operator)),
and the operator has asked that the config not change yet. Grading both
keeps that choice out of this verdict, as `narrow_to_fit` does.

### The seen book, printed beside it

Every look also prints F2 and F3 on the dates before 2026-10-08: the same
cells, `account_sim`'s A1–A6 as registered. It is labelled "seen — context
only". **It never enters the forward statistic**, its intervals, or its
verdicts.

## The grade

### Why a confidence sequence

Grading on every suite run means an open-ended number of looks. A fixed-sample
CI read again after each new date rejects a true null far more often than its
stated 5%. A rule that stops at the first look where the CI clears zero will
eventually clear it on a strategy with no edge at all.

Two published families correct for this.

| Family | How it controls repeated looks | Fit here |
|---|---|---|
| Group-sequential alpha spending (Lan and DeMets 1983) | Spends a fixed error budget across looks, against a maximum sample fixed in advance | Poor. It needs a planned end, and looks after the budget is spent have no error guarantee. The operator wants no end |
| Anytime-valid confidence sequences (Howard, Ramdas, McAuliffe, Sekhon 2021; Waudby-Smith, Arbour, Sinha, Kennedy, Ramdas 2024) | An interval that covers the true mean at every time at once, with stated probability | Good. Valid under any number of looks, taken whenever the suite happens to run |

**This file uses the asymptotic confidence sequence** of Waudby-Smith et al.
(2024), which rests on the time-uniform boundaries of Howard et al. (2021).

| Source | Use here |
|---|---|
| Howard, Ramdas, McAuliffe, Sekhon (2021), "Time-uniform, nonparametric, nonasymptotic confidence sequences", *Annals of Statistics* 49(2), [arXiv:1810.08240](https://arxiv.org/abs/1810.08240) | The normal-mixture boundary, and the result that a running intersection of a confidence sequence is still one |
| Waudby-Smith, Arbour, Sinha, Kennedy, Ramdas (2024), "Time-uniform central limit theory and asymptotic confidence sequences", *Annals of Statistics* 52(6), 2613–2640, [arXiv:2103.06476](https://arxiv.org/abs/2103.06476) | The boundary below (Theorem 2.2, Eq. 8), with the variance estimated from the data, and the choice of `ρ` (Appendix B.2, Eq. 50) |
| Lan and DeMets (1983), "Discrete sequential boundaries for clinical trials", *Biometrika* 70(3) | The alternative, not used |

Why the asymptotic version and not Howard et al.'s exact empirical-Bernstein
sequence: the exact one needs a hard bound on each observation and pays for it
with a much wider interval. With R bounded to [−2, +2] it needs roughly four
times as many forward dates to confirm the in-sample effect. The cost of the
asymptotic version is that its guarantee holds only approximately at small
samples. The minimum counts below exist for that reason
([answer 3](#answers-2026-10-07)).

### The statistic

One observation per forward signal date, per cell and cap cell.

- **Unit.** A forward signal date on which the cell took at least one
  position. Dates on which it took none add nothing.
- **Value.** `X_i` is the mean R of that date's taken positions. R is the
  row's realized R as `account_sim` books it. A narrowed F3 position's R is
  on its own narrowed entry basis.
- **Order.** Signal-date order. The observation index `t` counts these dates.
- **Complete prefix.** The sequence stops before the first forward date that
  still holds an open position. A position is open when its replay ends
  `cap_open` on a row whose `path_status` is `open_at_data_end`. A position
  that exited, expired or reached the path cap is closed. So each look
  appends dates and never reaches past an unfinished one.

This is a date-weighted mean, where `account_sim`'s A1 weights positions.
Each cell takes at most three a day, so the two differ little. Every look
prints both.

Treating dates as the independent unit is the same assumption the registered
date-clustered CI makes. It holds only approximately: positions opened on
nearby dates share market moves.

### The boundary

At each `t`, with `μ̂_t` the mean of `X_1 … X_t` and `σ̂_t` their standard
deviation (divisor `t`):

```
half_width_t = σ̂_t · sqrt( 2(t·ρ² + 1) / (t²·ρ²) · log( sqrt(t·ρ² + 1) / α ) )
interval_t   = [ μ̂_t − half_width_t ,  μ̂_t + half_width_t ]
ρ            = sqrt( (−2·log α + log(−2·log α + 1)) / t* )
```

This is Theorem 2.2, Eq. (8), of Waudby-Smith et al. (2024), a two-sided
(1 − α) asymptotic confidence sequence, with `σ̂_t² = (1/t)·ΣX_i² − μ̂_t²`.
The `ρ` line is the closed form of their Appendix B.2, Eq. (50).

| Constant | Value | Why |
|---|---|---|
| α | 0.0125 per sequence, two-sided | Four graded sequences (F2 and F3, each on two cap cells). 0.05 split four ways (Bonferroni), so the family holds at 0.05 |
| `t*` | 150 dates | Where the interval is tightest. It changes width, never validity. 150 is near where the in-sample effects would be confirmed |
| `ρ` | 0.27133 (`ρ²` = 0.073618) | Eq. (50) at α = 0.0125, `t*` = 150 |
| Start of the intersection | the first `t` that meets the minimum counts | Before that the asymptotic approximation is not trusted |

**The graded interval is the running intersection** from that start:
the largest lower bound and the smallest upper bound seen at any `t` so far.
Howard et al. (2021) show the intersection keeps the coverage. It makes a
verdict, once reached, permanent.

The intersection is taken over every `t` in the sequence, not only over the
looks. So the verdict depends on the data and never on when the suite ran.

If the intersection ever becomes empty, the look prints `CS EMPTY`. That is
evidence the assumptions failed. The cell reads `STILL-OPEN` and the operator
is told.

### What counts as a look

**A look is any run of this study's module**, on whatever exports are on disk.
A suite run, a single run and a re-run all count. Their number and timing are
unrestricted, because the confidence sequence is valid under any of them.

Every look is logged with its date, export timestamp, git sha, `t` and the
interval, per cell and cap cell. If a re-price has changed an `X_i` already
in the sequence, the look recomputes the whole sequence on current values and
lists each changed date. A re-price is not chosen by outcome. A re-price made
to rescue a verdict is forbidden under [Anti-tuning](#anti-tuning).

### Minimum counts

No verdict reads from a sequence's interval until it holds at least
**30 dates** and **60 taken positions**, both in PRIMARY. Below either, the
cell reads `STILL-OPEN` and prints its census and its interval
([answer 5](#answers-2026-10-07)).

30 dates matches `MIN_ERA_DATES`. The counts guard the asymptotic
approximation, not the multiple-look correction, which needs no minimum.

The one exception is the drawdown breach, which is an observed fact rather
than an estimate. It fires at any count.

### Verdicts

Each cap cell of each graded cell gets one verdict at every look: the first
row, from the top, whose condition holds.

| Verdict | When | What it means |
|---|---|---|
| **AWAITING SCRAPE** | F3 only: GN5 fires on this look | F3 is not graded on this look. Census only |
| **FORWARD-REFUTED (drawdown)** | Realized-on-close maxDD on the forward account exceeds 25% of $25,000, on PRIMARY or SECONDARY | The account does not survive the cell. Permanent |
| **FORWARD-REFUTED (edge)** | Minimum counts met, and the interval's upper bound is below **+0.10 R** | Forward dates rule out an edge worth trading. The look also says whether the upper bound is below zero. Permanent |
| **FORWARD-CONFIRMED** | Minimum counts met, and the interval's lower bound is above zero | The cell earns a positive mean on dates nobody had seen. Permanent unless a drawdown breach follows |
| **STILL-OPEN** | Anything else | Not yet decidable. The normal state for months |

The drawdown is `account_sim`'s A3 curve, on the forward account's closed
positions. A position still open at the data end enters the curve once it
closes.

Each graded cell's verdict line is the worse of its two cap cells, so
`FORWARD-CONFIRMED` needs both. Worst to best: `FORWARD-REFUTED`,
`AWAITING SCRAPE`, `STILL-OPEN`, `FORWARD-CONFIRMED`. F2 and F3 each print
their own line; there is no combined verdict.

The +0.10 R bar applies to both cells. It is half of F2's in-sample PRIMARY
meanR at the registered cell (+0.200), rounded, and about half of F3's
(+0.221). It is the edge size below which changing the floor rule is not
worth it. It was set after seeing those figures
([answer 4](#answers-2026-10-07)).

`account_sim`'s A1 year rule is not used: the sequence already grades the
forward mean at every date, which is a stricter check than one sign per year.

### Context printed at every look, never graded

These are `account_sim`'s other clauses on the forward population, for each
graded cell. They have no sequential error control, so they inform the
operator and gate a ship (see [Ship criteria](#ship-criteria)). They never set
a verdict ([answer 6](#answers-2026-10-07)).

| Label | What it prints |
|---|---|
| A2-reg | The cell's dollars ÷ B2 dollars on the cell's own forward dates, as registered |
| A2-all | The cell's dollars ÷ B2 dollars on every forward date B2 traded |
| A2-cap | The cell's dollars ÷ B2 run with the cell's own floor rule, on the cell's dates. Disclosure only |
| FW5 | A2-reg with each calendar month of forward dates dropped in turn; the largest move in points |
| A6 | The same confidence sequence on the debit-only subset |
| FWD | Median maxDD over the cell's block-bootstrap paths (`lib/path_bootstrap.py`, block length 10, the printed seed), against 25% |
| FWT | For every forward drawdown of `(R, F1, $500)` reaching 10% of capital: the cell's deepest drawdown inside it |
| MTM maxDD | The marked-to-market drawdown on the forward account |
| SECONDARY | The confidence sequence on SECONDARY |

`account_sim`'s two registered re-cuts drop March–April 2025 and
February–April 2026. Neither holds a forward date, so FW5's leave-one-month-out
replaces them on this population.

### Expected outcome, written now

`STILL-OPEN` for a long time. The planning table uses a per-date SD of 0.755,
taken from seen data (see the disclosures), for both cells. It is not used by
the grade, which estimates `σ̂_t` from forward dates.

| True forward mean R | Forward dates needed for a verdict, roughly |
|---|---|
| +0.20, F2's in-sample effect | about 175 to confirm |
| +0.22, F3's in-sample effect | about 145 to confirm |
| +0.003, F2's in-sample 2026 mean | about 790 to refute at +0.10 |

In-sample, F2 traded on 122 PRIMARY dates where F1 traded on 170, and F3 on
174 where F1 traded on 138. If live analysis runs most trading days, 175 F2
dates is roughly a year of signals and 145 F3 dates about eight months, plus
the time for the last positions to close.

## Gates

Each gate exits non-zero on failure, except GN5, which prints.

- **G2–G5** are `account_sim`'s, unchanged, run on the forward book.
- **GN5 COVERAGE — prints.** `narrow_to_fit`'s, on the forward F3 cell, as
  under [Substitute legs](#substitute-legs-on-forward-dates).
- **FW2 FORWARD IDENTITY.** The run refuses if any date in a forward sequence
  precedes 2026-10-08, or if the seen-book context block contains one that
  does not.
- **FW3 NOTHING HARDCODED.** Every count is computed by the run. No
  annualised figure, Sharpe ratio or time-to-recover is printed.
- **FW4 SEQUENCE CHECK.** The run recomputes the interval at the previous
  look's `t` from the current data. If it differs and no changed `X_i`
  explains it, the run fails.

## Plan-time observations, disclosed

**All of the following was seen before this file was written.** Every figure
is at the $500 budget under ARM R unless the row says otherwise.

### What `account_sim` printed on F2

| Run and book | Cap cell | Pop. | n | Dates | meanR [CI] | maxDD | A2 | A5 moves (ex-25, ex-26) | Failed |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-21, exports 09-19 | 2.50 | PRIMARY | 137 | 82 | +0.319 | 8.7% | 77% | — | none |
| 2026-09-21, exports 09-19 | 2.50 | SECONDARY | — | — | — | 10.1% | — | — | A1, A5, A6 |
| 2026-09-21, exports 09-19 | 1.50 | PRIMARY | — | — | — | — | 53% | — | A2 |
| 2026-09-28, exports 09-27 | 2.50 | PRIMARY | 180 | 122 | +0.214 [+0.087, +0.337] | 11.2% | 104% | +34, −11 | A5 |
| 2026-09-28, exports 09-27 | 2.50 | SECONDARY | 194 | 132 | +0.178 [+0.026, +0.317] | 11.4% | 113% | +75, −12 | A5 |
| 2026-10-01 cached, exports 09-27 | 1.50 | PRIMARY | 158 | 111 | +0.200 [+0.071, +0.326] | 11.0% | 74% | +18, −6 | A5 |
| 2026-10-01 cached, exports 09-27 | 1.50 | SECONDARY | 170 | 120 | +0.163 [−0.001, +0.309] | 11.4% | 84% | +33, −7 | A1, A5 |

Sources: the
[2026-09-21 entry](../../current.md#2026-09-21--account_sim--the-registered-cap-cell-prints-feasible-the-run-on-record-does-not),
`backtests/study_output/account_sim-latest.txt` (2026-09-28), the
[2026-09-29 entry](../../current.md#2026-09-29--operator-rulings-the-150-cell-and-the-2026-column),
and `backtests/study_output/narrow_to_fit-cached-20261001.txt`, section
`b500_n150`.

### What A5's failure means

**F2 fails A5 because its ratio is unstable, not because one window carries
its edge.** Dropping March–April 2025 raises F2's A2 ratio, so F2 did
relatively worse than B2 in that window.

| Cap cell, PRIMARY | A2, all dates | A2 without 2025 Mar–Apr | Move |
|---|---|---|---|
| 1.50 (cached, 2026-10-01) | 74% | 92% | +18 points |
| 2.50 (2026-09-28) | 104% | 139% | +34 points |

### What `narrow_to_fit` printed on F3 at $500

From `backtests/study_output/narrow_to_fit-latest.txt`, run 2026-10-07
20:00, exports 2026-10-06 23:39, 1,850-row book over 280 dates, and the
[2026-10-07 entry](../../current.md#2026-10-07--narrow_to_fit-graded-headline-null-500-narrow-feasible).

| Object | Cap cell | Pop. | n | Dates | Total $ | meanR | maxDD $ |
|---|---|---|---|---|---|---|---|
| `narrow_to_fit` (R, F3, $500) | 1.50 | PRIMARY | 304 | 174 | 24,661 | +0.221 | −3,882 |
| `narrow_to_fit` (R, F3, $500) | 2.50 | PRIMARY | 383 | 191 | 37,505 | +0.261 | −4,391 |
| `narrow_to_fit` (R, F2, $500) | 1.50 | PRIMARY | 163 | 113 | 12,837 | +0.207 | −2,808 |
| `narrow_to_fit` (R, F1, $500) | 1.50 | PRIMARY | 234 | 138 | 4,719 | +0.114 | −11,050 |

| Criterion, (R, F3, $500), PRIMARY | Net 1.50 | Net 2.50 |
|---|---|---|
| N1, `account_sim` FEASIBLE | met | met |
| N2, median bootstrap maxDD | 13.6% | 11.5% |
| N3, shallower in every F1 window | met | met |

| Narrowed subset, net 1.50, PRIMARY | Value |
|---|---|
| Positions / dates | 198 / 141 |
| N4 meanR [CI95] | +0.248 [+0.113, +0.383] |
| Year 2024 / 2025 / 2026 meanR | +0.286 / +0.409 / +0.095 |
| GN5, unpriced share of over-budget picks | 41 of 445, 9% |
| Paired contrast vs F1, mean R_dol | +53 [−44, +154] |

The verdict was `NARROW-FEASIBLE`, the secondary's line; the headline
`(R, F3, $1,000)` printed `NULL`.

### What `pbo_ledger` printed with F3 in the ledger

From `backtests/study_output/pbo_ledger-latest.txt`, 2026-10-07, with the
four F3 cells as a third configuration set (N = 63).

| Set, PRIMARY | PBO total | PBO maxdd | PBO meanR | PBO bar |
|---|---|---|---|---|
| ledger + ticker-cap | 69.4% | 0.0% | 32.4% | 42.2% |
| ledger + ticker-cap + F3 | 47.0% | 0.2% | 33.6% | 23.8% |

| (R, F3, $500) | In-sample pick, any metric | Full-path rank, of 63 |
|---|---|---|
| Net 2.50, PRIMARY | 4% to 69% by metric | 1st under total, meanR and bar |
| Net 1.50, PRIMARY | 1% or less | 3rd to 8th |
| Net 1.50, SECONDARY | 9% or less | 3rd to 7th |

A low PBO says the F3 $500 cells rank persistently on this one path, not
that they will earn on new dates.

### Other figures seen

| Figure | Value | Source |
|---|---|---|
| F2's refusals, 2.50, PRIMARY, 09-28 | 455 of 671 sized candidates, 68% | `account_sim-latest.txt` |
| F2's 2026 year mean, both cap cells, PRIMARY | +0.003 | same, and the cached report |
| F2 path bootstrap, 2.50, PRIMARY, 09-21 | 8.7% at its 47th–66th percentile; 0.0–0.1% of paths past 25% | 2026-09-21 entry |
| F2 PF ($) and PF (R), $500, 1.50, PRIMARY | 1.75 and 1.73 | [2026-10-01 entry](../../current.md#2026-10-01--entry-window-and-narrow_to_fits-cached-cells) |
| (R, F2, $1,000), 1.50, PRIMARY | 170 positions, meanR +0.178 [+0.037, +0.308], maxDD 34.9%, A2 26% | cached report, `b1000_n150` |
| (R, F2, $1,000), 2.50, PRIMARY | 225 positions, meanR +0.182, maxDD 48.2%, A2 42% | cached report, `b1000_n250` |
| One contract fits 2% of $25,000 | 39% of ladder-eligible PRIMARY candidates | 2026-09-21 entry, capital adequacy |
| Per-date SD of mean R, F1 taken positions with max loss ≤ $500, PRIMARY | 0.755 over 92 dates | `account_sim-positions-latest.csv`, 2026-10-06, for planning only |
| R range on those positions | −1.66 to +1.37 | same |

The positions CSV holds only the `(R, F1)` cell, so the SD and range above
come from F1's affordable positions, the closest available stand-in for both
F2 and F3.

### What these observations shaped

- **Both graded budgets are $500**, because those are the cells seen to pass.
  The $1,000 F2 cell was seen to fail A3, and is printed, not graded.
- **F3 joined as a graded cell** after its `NARROW-FEASIBLE` line and the
  PBO read above were seen.
- **The refute bar of +0.10 R** is about half the in-sample meanR of each
  cell.
- **The planning table** uses the seen SD. Neither the SD nor the range
  enters the boundary.
- **A5 becomes FW5, printed not graded**, because the registered cuts hold no
  forward date.

## Relation to `holdout_seal`

[`holdout_seal`](holdout_seal.md) is still a draft, and it is already
breached. It seals every signal date on or after 2026-08-11, and the
2026-09-28, 2026-09-29, 2026-10-01 and 2026-10-07 runs printed outcome
figures on 2026-08-11 → 2026-09-22. It needs a later start, or an explicit
list of spent dates, before anyone accepts it.

**This file does not depend on the seal.** Its forward dates start on
2026-10-08, and its grade is built to be read repeatedly.

The two conflict only if the seal is later accepted with a window that
overlaps these forward dates. The seal allows one read with no sizing arm;
this file reads two sizing cells on every suite run. The seal exists to
protect fixed-sample tests from repeated looks, which a confidence sequence
does not need. So if the seal is accepted, it names this study as a standing
read it permits, and its start moves past the dates already read
([answer 8](#answers-2026-10-07)).

## Relation to `narrow_to_fit`

[`narrow_to_fit`](narrow_to_fit.md) registers its own forward read on
"signal dates after acceptance", with at least 15 dates, and says a
`NARROW-FEASIBLE` verdict is not acted on before that read keeps its sign.

The two forward reads overlap on `(R, F3, $500)`. This file's grade is the
stricter one and is the one a ship of F3 needs: `narrow_to_fit`'s sign check
may still print whenever that study runs, but on its own it licenses nothing.

`narrow_to_fit`'s controls include `(R, F2, $500)` and `(R, F2, $1,000)`.
This file does not need F2 kept unseen, so they may print whenever
`narrow_to_fit` runs. They stay controls there; F2's and F3's grades come only
from this file's module. Routine `account_sim` and `narrow_to_fit` runs also
print both cells on a book that includes forward dates. That is each study's
own in-sample figure and never this grade.

## Anti-tuning

- **The cells are fixed** as tabled under [Cells](#cells): F2 and F3 graded
  at $500, F1 and F2 at $1,000 printed. No other budget, no ARM D cell, no
  other cap cell, no other floor rule. A new cell is a new registration.
- **The boundary is fixed:** α, `t*`, `ρ`, the minimum counts and the +0.10 R
  bar never change, in either direction.
- **The F3 rule is fixed:** `narrow_to_fit`'s widest-that-fits strike rule
  from entry-day fills, its tier check and its evidence rule, imported as
  they stand in that registration.
- **No sub-population grade.** No regime, structure, tier, DTE or month cut is
  graded. FW5 and A6 are printed context.
- **No restart.** A sequence is never reset to a later first date. A grade
  on a different population needs its own registration.
- **Code changes during the sequence.** Every look lists the commits since
  2026-10-07 that touch pricing, the loader, `account_sim` or
  `narrow_to_fit`. A change that alters which positions a cell takes is never
  made to move a verdict.

## Ship criteria

**Nothing ships from this file directly.** Each graded cell can license at
most one proposal, read at its own confirming look, on both cap cells.

| Cell | A `FORWARD-CONFIRMED` line lets the operator consider this change to [§2](../../../docs/deployment-rules.md#s2) |
|---|---|
| F2 | "Skip a survivor whose one-contract max loss exceeds 2% of capital; the next survivor in tier order takes its slot" |
| F3 | "Narrow an unaffordable survivor to the widest spread that fits 2% of capital; refuse it if none fits, and the next survivor takes its slot" |

The proposal also needs, at the confirming look and on both cap cells:

- A2-reg and A2-all both at least 60%;
- FW5's largest move at most 15 points;
- FWD's median maxDD at most 25%.

The change itself would need, in the same commit:

- the §2 text, stating the sizing basis it assumes (max loss, not
  production's risk-to-stop basis);
- a rollback trigger, written then, on live fills;
- a [`deployment-evidence.md`](../../deployment-evidence.md) entry citing
  the confirming look;
- the deploy card's one-contract affordability line (feasibility plan step
  4), which does not exist yet.

If both cells confirm, the operator chooses at most one of the two changes;
they are alternative answers to the same unaffordable pick.

A `FORWARD-REFUTED` line closes that cell as a candidate for its §2 change.
The study keeps printing, so the record stays complete.

## Answers, 2026-10-07

The operator answered every decision with the recommended option.

| # | Decision | Ruling |
|---|---|---|
| 1 | Does the trial ledger's cap bind forward dates? | No. The ledger counts trials on dates already read, and both cells are registered cells |
| 2 | First forward date | The day after acceptance, 2026-10-08. Earlier dates will be read by the export re-pull and suite runs |
| 3 | Sequential method | The asymptotic confidence sequence. The exact sequence needs about four times the dates; alpha spending needs an end the operator ruled out |
| 4 | Refute bar | +0.10 R, about half the in-sample meanR. A bar of 0 would leave a cell with no edge `STILL-OPEN` forever |
| 5 | Minimum counts | 30 dates and 60 positions per sequence before an interval verdict |
| 6 | A2 and FW5 | Printed context, required only for a ship proposal. Grading them at every look reintroduces the problem this file solves |
| 7 | The $1,000 F2 cell | Printed, not graded. It failed A3 in-sample, and the $1,000 question belongs to `narrow_to_fit` |
| 8 | `holdout_seal` | If the seal is accepted, it names this study as a permitted standing read, and its start moves past the dates already read |
| 9 | A prompt version bump | The grade freezes at the last v4 date; a v5 grade is a new registration |
| 10 | A v3 control | None. v3 is the same market path, not out of sample |

The operator also added `(R, F3, $500)` as the second graded cell, with α
split across four sequences.

## Build notes

Not part of the registration.

- **Module.** `scripts/backtest_study/f4_deployment/refuse_floor_forward.py`
  imports `account_sim`'s simulation and `narrow_to_fit`'s `Narrower`,
  `Chain` and `unlisted_evidence`. It filters the book to forward dates after
  `load_book` and writes its own report stem
  (`refuse_floor_forward-latest.txt`). It writes no `account_sim` or
  `narrow_to_fit` artifact and no site page.
- **Era checks.** `lib/era.py` checks the whole era before the forward
  filter, so its refusals still fire. Before any forward date has a loaded
  row, the module prints the census and `STILL-OPEN` for every cell, logs the
  look, and exits 4, which it declares in `DESIGNED_REFUSAL_EXIT_CODES`.
- **The confidence sequence.** `scripts/backtest_study/lib/confidence_sequence.py`,
  one pure function from the ordered `X_i` to every step and its running
  intersection. The boundary and `ρ` were checked against Theorem 2.2,
  Eq. (8), and Appendix B.2, Eq. (50), of the arXiv version. It is pinned by
  `tests/test_confidence_sequence.py`: a hand-computed fixture, and a coverage
  simulation across repeated looks at α = 0.0125.
- **The look log.** `scripts/study_results.py::record` is idempotent on
  (era, git sha, input row counts), so two looks could collapse into one
  record. The module keeps its own append-only log,
  `research/study-results/f4_deployment/refuse_floor_forward-looks.jsonl`,
  one JSON line per look with every sequence's dates and values. FW4 reads
  the previous look from it.
- **Where it surfaces.** A `refuse_floor_forward` entry in
  `scripts/study_map/catalog.py` (family `deployment`, state `open`), and a
  line in `research/study-map.md`. `run --all` runs it on every suite run.
  `python3 -m scripts.study_review refuse_floor_forward` finds this
  registration by name.
- **Labels.** `FW2`, `FW3`, `FW4`, `FW5`, `FWD`, `FWT`, A2-reg, A2-all,
  A2-cap and the F2 and F3 cell labels are in
  [`arm-index.md`](../../arm-index.md#refuse_floor_forward). "Confidence
  sequence" is in [`glossary.md`](../../glossary.md#confidence-sequence).
