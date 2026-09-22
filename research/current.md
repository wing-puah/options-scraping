# Backtest tuning — current

The recent end of the log. Dated entries run below the state of play. Older
work is in [`archive/`](archive/), indexed by the [README](README.md).
Conventions for this folder: terms in [`glossary.md`](glossary.md), study-local
labels in [`arm-index.md`](arm-index.md), house style in
[`writing-guide.md`](writing-guide.md).

## State of play

The suite was re-run on 2026-09-19 and **18 of 31 verdicts moved**. Nothing
ships. Two of the moves bear on shipped rules, and seven decisions now wait on
the operator: those two, the capital question, and four about the stored book
([entry](#2026-09-20--suite-re-run-read-in-full--18-of-31-verdicts-moved-two-touch-shipped-rules)).

This block is the authoritative summary of where the research stands.
[`overview.md`](overview.md) restates parts of it, and
[`next-steps.md`](next-steps.md) §0 points here. If either disagrees with this
block, this block wins.

### The population

| Field | Value |
|---|---|
| Era | `v4`, the 193-date backfilled book |
| Exports | re-pulled 2026-09-19, deduplicated; every result row joins its play but two |
| Real results | 598 over 193 dates |
| Proxy rows | 1,665 |
| Analysis rows | 2,781 over 237 dates, one analysis run per date |
| Pooled study book | 1,325 rows over 207 dates, being 598 real plus 727 tweak |
| Signal dates | 2024-01-10 → 2026-05-07 |
| 2026 signal dates | 29 carry pooled rows, 26 of them real; 2026-01-06 to 2026-05-07, 155 pooled rows |

Every number below was read on a book that mixes pricing regimes. The cost
model, the entry side rule and the exit-fill rule each reached only part of it,
and a cache-only re-price moves 370 of 2,234 stored rows
([census](#2026-09-20-later--stored-book--a-cache-only-re-price-moves-370-of-2234-rows)).

### Where the 2026 column bit

The 2026 column is negative in most per-year cells and still costs cells their
year clause. It is no longer the only thing moving verdicts: on
`portfolio_delta` the duplicate and stale-row repairs of 2026-09-06 and 09-07
carried most of the drop, and the 39 added dates the rest. Per-study rows are
in the [study map](study-map.md#operator-reading-2026-09-20).
[meanR](glossary.md#meanr) and [CI](glossary.md#ci) are defined in the
glossary; arm labels are study-local, so each is given with its study.

| Study | Arm or cut | What it prints now | Record |
|---|---|---|---|
| `next_day_move` | [ARM R](arm-index.md#next_day_move) bear debit | `worse than -0.5 sigma` has its `**` back and clears all six criteria | [record](study-results/f2_management/next_day_move.md) |
| `exit_from_text` | [E2](arm-index.md#exit_from_text) | a first `CANDIDATE`, and the pooled cell clears again | [record](study-results/f2_management/exit_from_text.md) |
| `portfolio_delta` | [ARM B](arm-index.md#portfolio_delta) | `NOISE`; no ceiling clears, criterion 1 alone failing at +0.0519 R, CI [−0.0333, +0.1407] | [record](study-results/f4_deployment/portfolio_delta.md) |
| `concurrency_correlation` | [K 5](arm-index.md#concurrency_correlation) same direction and sector | `RESTATEMENT` of `portfolio_delta`; X4 prints `PENDING`, so the 2026-09-04 hand settlement is withdrawn | [record](study-results/f4_deployment/concurrency_correlation.md) |
| `emission_timing` | [ARM P](arm-index.md#emission_timing) sub-cut 2 | repeats that had already moved against the play clear all six, at −0.2579 | [record](study-results/f1_selection/emission_timing.md) |
| `bear_rewrap` | [long_diag](arm-index.md#bear_rewrap) | 4 of 5 again, failing the year clause; the P1 portfolio check is met on no substitution | [record](study-results/f3_structure/bear_rewrap.md) |
| `bear_arm` | [B2](arm-index.md#bear_arm) exit fix | `NOT met`: `sl .50` Δ=+0.030, CI [−0.003, +0.061] | [record](study-results/f1_selection/bear_arm.md) |
| `account_sim` | [A3](arm-index.md#account_sim) | `NOT FEASIBLE AT $25,000` on the tracked cap cell; the registered cell prints `FEASIBLE` | [entry](#2026-09-21--account_sim--the-registered-cap-cell-prints-feasible-the-run-on-record-does-not), [plan](account-sim-feasibility-plan.md) |
| `exit_switch_structure_study` | Q1 and Q2 | `STAYS GATED`, now failing four of six; Q2 reads the shipped BEAR_HE clause at Δ=−4.5205, 47% retained | [record](study-results/f2_management/exit_switch_structure_study.md) |

Two of these bear on shipped rules. The `bear_arm` rollback census fires all
three of its clauses, and the report asks for a production config change on a
stop that was reverted in 2026-08. In `exit_switch_structure_study` the Q2
line is an observation rather than a registered trigger, because the census
that would fire is underpowered. Both are filed in
[`next-steps.md`](next-steps.md) under
*Waiting on the operator*, with `account_sim`'s capital question.

### Two firsts that hold rather than ship

Both 2026-09-04 firsts are gone: `bear_arm` B2 no longer meets its criteria,
and `financed_spread`'s `RE-WRAP` token left F3 off1, which is now `NULL`. Two
other cells clear in their place, and neither promotes a rule.

| Study | Arm | What it prints |
|---|---|---|
| `exit_from_text` | [E2](arm-index.md#exit_from_text) MECH LVOL N=3 | a first `CANDIDATE`, ΔR +0.071, CI [+0.011, +0.128], every criterion passing. An intake filter, never an exit rule |
| `financed_spread` | [F4-d20 $100](arm-index.md#financed_spread) | `RE-WRAP` at 6/7, failing only the anti-re-wrap E3 correlation at +0.180; its fixed-contracts control excludes zero |

### The hedge programme

The trigger studies are closed and the instrument is unchanged. The gap-up
prohibition in [§4](../docs/deployment-rules.md#s4) was accepted on 2026-09-06
and now rests on `hedge_timing`'s H3-GAP arm alone, because H1-GAP moved from
`CONTRARY` to `NULL` on this run. The sleeve stays, so finding an indicator for
when to open a hedge is an open queue item with nothing in it
([`next-steps.md`](next-steps.md) §2.10).

The spine is [`f5_hedging/README.md`](../scripts/backtest_study/f5_hedging/README.md):
the four studies grouped by the question each answers, what each one last
printed, why each stopped, and what would unblock it.

### Rollback triggers

Each trigger is checked at its gate, with numbers. A trigger that printed
nothing has not been checked, and that is not the same as "not met". The
[plan](pre-registrations/f2_management/rollback_triggers.md) holds each floor.

| Trigger | On this export |
|---|---|
| LVOL tef-null | `STAYS GATED` on 106 rows over 80 affected dates, median −0.011; one of its four clauses fails, the median among affected dates |
| BEAR_HE trail | `UNDERPOWERED` at 8 affected dates of 25 |
| bear-debit `be_after` | 242 arming rows over 134 dates, and all three clauses fire |
| credit sl-none | 0 of 15, and unreachable by backfill because the window starts after 2026-07-13 |

`be_after` was already reverted on 2026-08-24, so the shipped stop is off
whatever the census says. The report prints `REVERT CONDITION FIRED` and asks
for a production config change all the same, which is an operator decision
rather than a new finding.

### Known defects in this export, not repaired

- **The rows did not all run under one code version.** The six queue-D dates
  retried on 2026-09-08 carry the cost columns and the pre-entry grid fix;
  every other row predates it. Split them on `cost_total` or `pct_stale_days`
  being non-blank — not on `cost_basis`, which is blank everywhere while both
  cost knobs are 0.
- **Almost every `BacktestProxy` row is blank in `pct_stale_days`, `cost_total`
  and `cost_basis`.** `proxy.py::_evaluate` never copied them onto the row;
  fixed 2026-09-19 but not backfilled, so only the 9 rows re-priced on
  2025-04-09 carry them. [`next-steps.md`](next-steps.md) §2.11.
- **Four groups of stored rows are wrong or unverifiable**: the 14 pre-fill
  exits, the six wrong-strike rows, the 49 `Open`-fill rows, and 80
  `BacktestResults` rows that cannot be priced offline at all. Each is a
  decision in [`next-steps.md`](next-steps.md) under *Waiting on the operator*;
  the numbers are in the
  [census](#2026-09-20-later--stored-book--a-cache-only-re-price-moves-370-of-2234-rows).
- **Six `bear put spread` plays classify as `bear_call_spread`**, because their
  narrative mentions bear call spreads. All six are vetoed before pricing, so
  nothing prices wrong today
  ([entry](#2026-09-20-third--backtest-classifier--six-priced-rows-used-strikes-from-the-narrative-fixed)).
- **The 5 surviving 2025-09-18 rows carry a `market_regime` from a later
  analysis run than their own play.** That date was analysed twice and the
  backtest stamps the newest `MARKET` row, so the rows read `BULL + C-VOL`
  where the run that proposed them read `RANGE + L-VOL`.
- **Two rows on 2025-07-29 cannot join, and are kept on purpose.** `COIN` and
  `EEM` lost the analysis rows that proposed them, so the backtest row is the
  only surviving record of the play. Studies count them as unjoined.
- 2025-12-26 produced no analysis rows.
- `text_features` [ARM B](arm-index.md#text_features) label coverage is 74.9%,
  992 of 1,325 priced rows, because the label cache does not cover the new
  rows.

### The open queue

The queue itself is [`next-steps.md`](next-steps.md) §2. `ladder_overlay`,
registered 2026-09-10, ran on both eras and closed 2026-09-16 with every graded
cell `NULL`
([entry](archive/21-ladder-overlay-closed-the-journal-walk-forward-and-the-pricer-mirror.md#2026-09-16--ladder_overlay--nothing-ships-no-ladder-or-naked-put-cell-beats-the-plain-spread-on-v4-or-v3)).

- The v4 composition bridge and the rollback triggers wait on genuinely new
  dates. Those are the live analysis dates 2026-08-11 → 2026-09-18, which have
  no backtest rows until their options expire.
- `prompt_eval` ([§2.9](next-steps.md#s2-9)) is open but is not an edge search.
  It tests whether a prompt gives the same regime label on the same inputs,
  because the variance run traced the tier-mix swing to that label flipping.
  Nothing in the book says a prompt change moves P&L, so it waits behind §2.2.
- `operator_read` ([§2.5](next-steps.md#s2-5)) waits on the journal.

### Known traps carried forward

Each is a way to misread the data that has already caught someone once. None
blocks any work; each has its full entry in an archive volume.

- **`exit_basis` is era-scoped, not corrupt.** It is unlabelled and scrambled
  on the frozen `v3` exports
  ([archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md)),
  and clean on `v4`, re-measured 2026-09-02 at 485/485 labelled. `BacktestProxy`
  carries it only for rows written after the 2026-09-02 writer fix.
- **Studies are era-scoped.** The bare export name does not name a population;
  `lib/era.py` is the single encoding (archive/15).
- **Arm labels are study-local.** Cite `emission_timing ARM P`, never a bare
  `ARM P` ([archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md),
  [`arm-index.md`](arm-index.md)).
- **`study_review --dry-run` overwrites** the review and digest artifacts
  (archive/17).
- **The `hedge_portfolio` registration describes the wrong stratum.** Its
  plan-time observations describe the `real` stratum, not the ratified book.
  The ruling that says so was folded out of `hedge-exposure-errata.md` into
  [the registration](pre-registrations/f5_hedging/hedge_portfolio.md) on
  2026-09-02. The errata file is deleted; dated entries below keep its name.

### What was pruned from this log

- Pruned 2026-08-31: everything up to 2026-08-27.
  [archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md) took
  08-14 and 08-15, being era-scoping, suite repair and `selection_order`.
  [archive/16](archive/16-first-runs-on-v3.md) took 08-19, the first runs of
  the `v3`-era studies.
  [archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md) took 08-22
  to 08-27, being vocabulary, `concurrency_correlation`, the `v4` refresh and
  `hedge_sizing`.
- Pruned 2026-09-04: 2026-08-28 to 2026-09-02, into
  [archive/18](archive/18-hedge-programme-exit-basis-and-text-loop.md). That
  volume holds the hedge programme (`hedge_timing`, `hedge_portfolio`,
  `hedge_concentration`), the `exit_basis` re-measure and audit, and the text
  to backtest loop.
- Pruned 2026-09-09: 2026-09-04 to 2026-09-07, into
  [archive/19](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md),
  and 2026-09-08, into
  [archive/20](archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md).
- Archive 19 holds `hedge_concentration` GRADED, `concurrency_correlation`'s
  first run, the first book with 2026 dates, and `exit_drawdown`'s
  registration and UNDERPOWERED run. It also holds the overview/glossary
  rewrite, the gap-up hedge prohibition, and the SPY and stale-row duplicate
  repairs with their two new write guards. Last are the 40 unrun
  pre-registered dates, the robustness review, and the hedge-programme
  criteria consolidation.
- Archive 20 holds the hedge studies' rename, the robustness fold landing on
  main, and the hedge-programme plan's deletion into `f5_hedging/README.md`.
  It also holds `exit_drawdown`'s ARM P ACK and errata fold, queues C/D/E, and
  the sleeve-sizing fold onto `lib/hedge_criteria.sleeve_pick`. Last is the
  far-call fetch that restored 178 lost cache files while `hedge_structure`
  stayed blocked at R2.

---

## 2026-09-22 (later) — bear debits — a fast exit cuts the loss, still loses after costs

A bear debit closed within a few sessions, or at a small profit, loses less
than one run on the shipped exit, but it does not make money once trading
costs are charged. This is an exploratory read, not a verdict. Nothing ships,
and a study is drafted to test it properly.

_Eras v4 and v3, never pooled. Exports 2026-09-19. Bear debit rows, real and
tweak: 483 rows on v4, 199 dates. On v3, 332 rows, 109 dates. Scratch
scripts in the session scratchpad, not committed. Draft:
[`bear_fast_exit`](pre-registrations/f2_management/bear_fast_exit.md)._

**In production.** Nothing changes. Bear debits stay vetoed as a selection
([§1.4](../docs/deployment-rules.md#s1)) and keep the shipped exit
([§5](../docs/deployment-rules.md#s5)).

**Why this was asked.** The operator still deploys some bear debit spreads
and closes them quickly. No bear-debit test had a profit target below 0.75 or
a stop measured in sessions. The closest were
[`staged_exit` ARM E](arm-index.md#staged_exit), whole book from session 5
on, and [`next_day_move` ARM R](arm-index.md#next_day_move), a day-0 cut.

**Evidence.** Paired against the shipped exit through the frozen harness.
Net is at $0.65 per contract plus 25% of the quoted spread, per leg per side,
on rows whose entry spread is at most half the debit.

| Arm | Era | Δ gross vs shipped | [CI](glossary.md#ci) | Net [meanR](glossary.md#meanr) | Net CI |
|---|---|---|---|---|---|
| Shipped | v4 | — | — | −0.207 | [−0.301, −0.114] |
| Close at session 3 | v4 | +0.112 | [+0.034, +0.191] | −0.061 | [−0.098, −0.021] |
| pt +0.20 or session 3 | v4 | +0.116 | [+0.035, +0.199] | −0.066 | [−0.099, −0.032] |
| Shipped | v3 | — | — | −0.172 | [−0.299, −0.038] |
| pt +0.20 or session 3 | v3 | +0.111 | [−0.003, +0.220] | −0.087 | [−0.134, −0.041] |

- Gross meanR under every fast exit is close to zero. The round trip costs
  more than that, so every fast arm is negative net of cost on both eras.
- The loss cut is real on v4 but thin on v3. On v3 real rows no fast exit
  separates from the shipped one.
- The cut comes from both tails: the fast exit stops the deep losers early
  and also cuts the big winners short. Bear debits that end profitable peak
  late, at a median of session 13 on v4.

| Shipped outcome (v4) | Rows | Mean R, shipped | Mean R, pt +0.20 or session 3 |
|---|---|---|---|
| Winners above +0.50 R | 146 | +1.17 | +0.29 |
| Losers at −0.50 R or worse | 259 | −0.79 | −0.11 |

**The operator's live bear debits.** Classified from opening fills, because
the journal mislabels some closing bull call spreads. The count is far too
small to judge an edge.

| Opened in | Opened | Closed | Median hold | Realized | Per dollar of debit |
|---|---|---|---|---|---|
| 2025-02 → 2026-09 | 31 | 29 | 5 calendar days | +$761 | +0.061 |
| 2025 | 15 | 15 | 4 calendar days | +$1,759 | +0.395 |
| 2026 | 16 | 14 | 5.5 calendar days | −$998 | −0.124 |

Two cheap spreads that returned several times their debit carry the 2025
figure.

**Caveats.** The arms were read before the draft was written, so this book
cannot confirm one; the draft requires a forward read on new dates. The cost
model here is a scratch copy on a subset of rows. The study must charge cost
on every row through `cost_sensitivity`'s quote fallback.

**Next.** [`next-steps.md`](next-steps.md) §2.4 gains the draft, which waits on
the operator and on the whole-book re-price.

## 2026-09-22 — account_sim — a Turtle drawdown throttle is inert at $25,000, closed unregistered

A Turtle-style position-size throttle does not shrink `account_sim`'s
drawdown at $25,000, and eighteen exploratory reads close the question.
Nothing ships and nothing is registered.

_Era v4. Exports 2026-09-19. Tracked cell: 211 PRIMARY positions, 292
SECONDARY. Registered cell: 142 PRIMARY, 206 SECONDARY. Exploratory scratch,
not a study: `backtests/feasibility_plan_20260922/turtle_exploratory/run_turtle.py`
→ `out.txt`, design memo `turtle_design_memo.md` (both gitignored). Plan:
[account-sim-feasibility-plan.md](account-sim-feasibility-plan.md)._

**In production.** Nothing changes. The shipped ladder
([§1](../docs/deployment-rules.md#s1)) and the exit profile
([§5](../docs/deployment-rules.md#s5)) stay as they are. No arm slot is
spent, because nothing was registered.

**Why this was tested.** [`exit_drawdown` ARM D](arm-index.md#exit_drawdown)
is a flat ×0.5 sizing throttle on realized equity. Its one powered read
already printed `SECONDARY-NULL`, $993 deeper than the shipped book.
*Original Turtle Trading Rules* (Curtis Faith), Ch. 3 "Adjusting Trading
Size," printed p. 17, describes a gentler step ladder that restores only at
the year's starting equity, so this test asks whether ARM D's slower cousin
fares any better.

**The 18 configs.** Three mechanisms — contracts only (the faithful
transcription), delta-cap scaling, and both together — run on two equity
bases, mark-to-market and realized-on-close, across the tracked and
registered cap cells and both populations. Eighteen reads in total, on the
trial ledger below.

| Cell | Variant | Basis | PRIMARY realized maxDD |
|---|---|---|---|
| tracked 0.25/2.50 | baseline | – | 35.0% |
| tracked 0.25/2.50 | T/ladder | mtm | 35.7% |
| tracked 0.25/2.50 | T/ladder | realized | 35.7% |
| tracked 0.25/2.50 | T/caps | mtm | 35.0% |
| tracked 0.25/2.50 | T/caps | realized | 35.0% |
| tracked 0.25/2.50 | T/both | mtm | 35.7% |
| tracked 0.25/2.50 | T/both | realized | 35.7% |

PRIMARY spans 35.0–35.7% across all six variants against a 35.0% baseline.
The baseline's own noise band, already on record, runs 21.0% to 34.7%
(block-bootstrap, block length 10).

| Cell | Variant | Basis | SECONDARY realized maxDD | Δ vs 40.8% baseline |
|---|---|---|---|---|
| tracked 0.25/2.50 | T/ladder | mtm | 41.5% | +0.7 |
| tracked 0.25/2.50 | T/ladder | realized | 41.5% | +0.7 |
| tracked 0.25/2.50 | T/caps | mtm | 37.9% | −2.9 |
| tracked 0.25/2.50 | T/caps | realized | 45.7% | +4.9 |
| tracked 0.25/2.50 | T/both | mtm | 38.0% | −2.8 |
| tracked 0.25/2.50 | T/both | realized | 53.5% | +12.7 |

SECONDARY moves −2.9 to +12.7 points across the six variants and flips sign
by basis, so the mechanism reads as unstable rather than protective.

**The faithful rule — contracts only — is nearly inert.** Scaling contracts
alone changes eight to seventeen rows per read on the tracked cell, out of
211 PRIMARY and 292 SECONDARY taken positions. Most of the book cannot get
smaller: 177 of 211 PRIMARY positions already sit at the one-contract floor
([capital adequacy](glossary.md#capital-adequacy)).

**Every criterion movement is a failure the throttle caused, never an
improvement.**

| Cell | Population | Variant, basis | Clause | Baseline | With throttle |
|---|---|---|---|---|---|
| tracked 0.25/2.50 | SECONDARY | T/both, realized | A1 edge survival | met | fails |
| tracked 0.25/2.50 | SECONDARY | T/both, realized | A2 attrition | met | fails |
| registered 0.25/1.50 | SECONDARY | T/ladder, realized | A3 no blowup | 23.5%, met | 25.4%, fails |

The registered cell's own A3 bar is 25% of capital; the faithful ladder
pushes SECONDARY's realized drawdown from 23.5% to 25.4%, over it.

**Why, structurally.**

- **The annual reference misses PRIMARY's second-deepest drawdown.** The
  ladder log shows no step between the 2024-01-10 and 2025-01-16 REBASE
  entries, on every tracked-cell variant, even though 2024-07-10 to
  2024-08-26 is a 22.4%-of-capital drawdown by the study's own episode
  table. A trigger keyed to the year's starting equity cannot fire inside a
  year it never re-crosses.
- **A late-window trigger buys one throttled entry.** The 2025-03-03 step
  lands inside DD1 (2025-01-10 to 2025-04-09). Only one entry inside that
  window falls after the step, before the window closes, costing $161
  against baseline. Every contract-scaling variant agrees on that figure.
- **Restoration lags for months.** Four of the six tracked-cell variants
  restore to full size; the gap from the first throttle step runs four to
  six months on those that do, and two never restore inside the run's
  window. Size comes back only after the market's own recovery is already
  underway.
- **Cutting contracts frees cap headroom, so the book grows.** The clearest
  case is the tracked cell's T/ladder read on the realized basis, where
  taken positions rise from 211 to 217 even though the throttle is meant to
  shrink risk.

**Verdict.** Closed 2026-09-22. Nothing is registered and no arm slot is
spent. The [feasibility plan](account-sim-feasibility-plan.md)'s trial
ledger gains all eighteen configurations.

**Next.** [`next-steps.md`](next-steps.md) item 5 notes the closure and
still points at the [plan](account-sim-feasibility-plan.md). No new queue
item opens.

---

## 2026-09-21 — account_sim — the registered cap cell prints FEASIBLE, the run on record does not

The registered cap cell prints `>>> FEASIBLE <<<` on all six criteria. The
`NOT FEASIBLE AT $25,000` verdict on record belongs to a different cell: since
2026-08-13 the tracked config has carried a net cap the registration never
named. Nothing ships. This is a conformance run, not a fix — the registration
forbids adopting a cap value on its P&L, and reconciling the config with the
registration is the operator's decision.

_Era v4. Exports 2026-09-19, 598 real and 1,665 proxy rows over 193 dates.
Reports: `backtests/study_output/account_sim-latest.txt` (the tracked cell) and
`net150/account_sim-latest.txt` (the registered cell), both at git `d8713ce`
with the working tree dirty. Evidence folder
`backtests/feasibility_plan_20260921/` (gitignored). Plan:
[account-sim-feasibility-plan.md](account-sim-feasibility-plan.md)._

**In production.** Nothing changes. The shipped ladder
([§1](../docs/deployment-rules.md#s1)) and the exit profile
([§5](../docs/deployment-rules.md#s5)) are untouched, and no criterion,
threshold, arm or verdict moved. The report gained seven disclosure blocks and
the study gained two pure modules under `scripts/backtest_study/lib/`.

**The two cap cells.** The registration fixes the headline at per-position 0.25
× net 1.50. The tracked config carries 2.50, raised by the operator on
2026-08-13 ([record](archive/13-account-sim-and-calendar-hedge.md)) with no
`Resolved at build` note in the registration.

| Cell, per-position × net | PRIMARY verdict | A3 realized | Positions | SECONDARY A3 |
|---|---|---|---|---|
| 0.25 × 2.50, the tracked config | `NOT FEASIBLE AT $25,000` | 35.0% | 211 | 40.8% |
| 0.25 × 1.50, the registered cell | `FEASIBLE` | 20.3% | 142 | 23.5% |

At the registered cell every criterion is met on both populations. At the
tracked cell [A3](arm-index.md#account_sim) alone fails on both. The registered
cell also turns the SECONDARY drawdown that never recovered into one that does:
38.4% becomes 22.9%, recovered 2026-07-27.

**Both bases.** A3's registered basis is realized on close, so every reading
above is realized. On the
[mark-to-market basis](glossary.md#mark-to-market-basis) — marked on every
session a position was open — each book is deeper, and the registered cell's
PRIMARY reading sits just above the bar. Every position reconciles on both
bases, with no stale mark and no missing price path.

| Book | Realized on close | Marked to market |
|---|---|---|
| Tracked cell, PRIMARY, 211 positions | 35.0% | 42.1% |
| Tracked cell, SECONDARY, 292 | 40.8% | 67.0% |
| Registered cell, PRIMARY, 142 | 20.3% | 25.9% |
| Registered cell, SECONDARY, 206 | 23.5% | 44.8% |
| v3 control, PRIMARY, 72 | 17.4% | 28.1% |
| v3 control, SECONDARY, 160 | 25.1% | 35.2% |

**The four arm cells, scored for the first time.**
[F2](arm-index.md#account_sim) refuses any pick whose one contract costs more
than the budget, and the registration calls the F1-against-F2 contrast the
study's central object. Until this run the report tabulated F2's dollars
against nothing.

| Cap cell | Arm | PRIMARY | SECONDARY |
|---|---|---|---|
| 2.50 | (R, F1) headline | A3 fails | A3 fails |
| 2.50 | (R, F2) | six of six met | A1, A5, A6 fail |
| 2.50 | (D, F1) | A3 fails | A3 fails |
| 2.50 | (D, F2) | A5 fails | A1, A5, A6 fail |
| 1.50 | (R, F1) headline | six of six met | six of six met |
| 1.50 | (R, F2) | A2 fails at 53% | A1, A2, A6 fail |
| 1.50 | (D, F1) | six of six met | A3, A5 fail |
| 1.50 | (D, F2) | A5 fails | A1, A5, A6 fail |

F2 is weaker than the plan hoped. Its best reading is the tracked cell's
PRIMARY, where it meets every criterion on 137 positions with
[A2](arm-index.md#account_sim) at 77% of B2. At the registered cell it fails A2
at 53%. The A2 denominator stays unresolved: B2 keeps the one-contract floor on
every cell, so F2 is measured against a book that still takes the picks it
refuses. That is the registered clause and it did not change.

**The bootstrap band.** The realized drawdown is resampled in blocks of 5, 10
and 20 exit sessions. One seed drives 2,000 draws on every cell, and the range
below spans the three block lengths.

| Cell and population | Realized | Its own percentile | Paths past 25% |
|---|---|---|---|
| Tracked, PRIMARY | 35.0% | 71st–82nd | 44–66% |
| Tracked, SECONDARY | 40.8% | 55th–70th | 73–88% |
| Registered, PRIMARY | 20.3% | 65th–79th | 8–12% |
| Registered, SECONDARY | 23.5% | 52nd–63rd | 30–42% |
| Tracked (R, F2), PRIMARY | 8.7% | 47th–66th | 0.0–0.1% |

Three caveats travel with those numbers. The resample holds each session's
dollar P&L as realized, so sizing, cap refusals and the dollar stop are not
re-simulated. A single max drawdown is a noisy order statistic, and this block
measures that noise and nothing else. There is no decision rule here: 25% is
the operator's own tolerance rather than an estimate, and a wide band never
licenses a pass. One seed drives every cell, so the bands are correlated and
must never be differenced.

**[Capital adequacy](glossary.md#capital-adequacy), outcome-blind.** This asks
only whether one contract of a play fits 2% of a given capital. It reads no
P&L, no exit reason and nothing about which plays the walk took. The cut below
is the ladder-eligible candidates on the PRIMARY dates, which is the population
A4 partitions.

| Capital | Share one contract fits |
|---|---|
| $25,000 | 39%, 175 of 444 |
| $35,000 | 51%, 225 of 444 |
| $50,000 | 70%, 313 of 444 |
| $34,600 | 50.0%, the smallest capital reaching half |
| $56,450 | 75.0% |
| $87,750 | 90.1% |

Every share is a FLOOR and every capital a lower bound. Before the census the
loaded book had already dropped 888 rows with no usable price path, 49 proxy
debit rows failing exact calibration and one duplicate. Those drops condition
on post-entry data and plausibly on cost. This is also not the capital ladder,
which asks which rung's simulation meets the criteria — an outcome-dependent
question. The two can disagree and neither answers the other.

**The bear sleeve, per window.** [ARM H](arm-index.md#account_sim) is reported,
never adopted; its live pick line was pulled on 2026-08-24. Availability binds
rather than size: inside the SECONDARY drawdown from 2025-11-03 the sleeve
filled 9 times, was refused 15 times by the caps, and lost $423. Over the whole
run the sleeve costs $6,311 on PRIMARY and $6,812 on SECONDARY. It buys 2.4 and
1.0 points of drawdown in return.

**The dollar stop is not a bound.** It is checked on daily marks, never
intraday, so a position that gaps through it books more than the stop.

| Population | Dollar-stop exits | Losing more than $500 | Mean loss | Mean overshoot |
|---|---|---|---|---|
| PRIMARY | 37 of 211 | 37 | −$659 | −$159 |
| SECONDARY | 61 of 292 | 61 | −$646 | −$146 |

**What the cache cannot confirm** (all figures here _exploratory_, from scratch
scripts in `census_join/`). No position in any drawdown window is one of the 14
pre-fill rows or the six wrong-strike rows. One window row carries a leg filled
at the `Open` price, on 2026-03-25, and it is immaterial. Four of DD1's 28
exits — `NVDA` three times and `TLT` — can no longer be re-priced offline, and
a Drive cache pull added no files. Two are missing a leg file outright and two
carry the shallow three-month history, so they need a Barchart refetch rather
than a pull.

Those four rows carry −$1,475 of DD1's −$8,755, or 16.8%. Read that as about
six of the 35 points resting on rows the cache cannot confirm. Do not read it
as a drawdown without them: removing rows changes which picks the walk takes.

**The v3 control** is a composition control, not an out-of-sample test — the
same market path, a different set of plays. It does not reproduce the v4
failure, because v3's dense episodes miss the January–February 2025 entries.
A3 is met at 17.4% on 72 positions, and SECONDARY reads 25.1%, just past the
bar. The verdict, quoted verbatim: `FEASIBILITY NOT CONFIRMED (A1-A3 hold; A5
and/or A6 fail; stability/robustness not established on this window)`. The
capital shortage is the same shape: 34% of ladder-eligible candidates fit one
contract at $25,000.

**`selection_order` on the current era**, quoted verbatim: `ORDERING-IS-NOISE —
no arm separates from the O4 band. The adverse-ordering read from account_sim
was an ARTIFACT of which picks the cap happened to exclude. Record it and CLOSE
the thread.` So adverse ordering is not an explanation for anything above.

**What is owed by the operator.**

- **Fold two rulings into the registration**, as `Resolved at build` tags: the
  2026-08-13 cap change and the 2026-08-14 verdict wording. Then decide which
  cap cell the tracked config should carry. Written as what was decided and
  when, never as "this passes A3". This is step 2 of the
  [plan](account-sim-feasibility-plan.md).
- **[Item 5](next-steps.md#waiting-on-the-operator) itself** — change capital or
  sizing, or accept the drawdown. It stays open, restated to this run.
- **The scrape decision** the four unpriceable rows wait on, which is
  [item 8](next-steps.md#waiting-on-the-operator).

**Next.** [`next-steps.md`](next-steps.md) item 5 stays open and is rewritten.
The plan's Phase 0 is done. So are steps 1, 3 and 5. Step 2 is the operator's
and step 4 is untouched. Phase 3 now starts from whether any new arm is needed
at all.

---

## 2026-09-20 (sixth) — account_sim — re-run identical; the floor carries the drawdown; a plan is filed

**The re-run prints the same verdict, and most of the 35.0% is the
one-contract floor.** Nothing ships. The work is ordered in
[`account-sim-feasibility-plan.md`](account-sim-feasibility-plan.md).

_Era v4 · exports 2026-09-19 · report `backtests/study_output/account_sim-latest.txt`
at git `1c163c5`, recorded in
[study-results](study-results/f4_deployment/account_sim.md) · evidence folder
`backtests/feasibility_plan_20260920/` (gitignored)._

**The re-run.** The report differs from the previous print only in its run
stamp and git line. The compounding arm also fails A3.

| Arm | Max drawdown | [A3](arm-index.md#account_sim) |
|---|---|---|
| Fixed capital, PRIMARY | 35.0% | not met |
| Fixed capital, SECONDARY | 40.8% | not met |
| Compounding, PRIMARY | 34.2% | not met |

**What the investigation found.** Figures marked _exploratory_ come from
scratch scripts over the positions CSV, not from the study.

| Finding | Figure |
|---|---|
| Positions whose one contract costs more than the $500 budget | 124 of 211 |
| Max drawdown with exact fractional contracts, any capital | 23.9% (_exploratory_) |
| Share of the window loss carried by floor positions | 90% (17 of 28 exits) |
| Second-deepest PRIMARY drawdown, July–August 2024 | 22.4% |
| SECONDARY drawdown from 2025-11-03, never recovered | 38.4% |
| Registered arm F2 (refuse the floor), PRIMARY | 8.7%, meanR +0.319, 137 positions |

**Three things the plan rests on.**

- Arm F2 is registered and printed on every run, and it has never been scored
  against A1–A6. It costs 39% of the dollars. Its A4 and A5 are unknown, and an
  _exploratory_ A1 fails on SECONDARY's thin 2026 slice.
- The run uses `caps.net` 2.50. The registration names (0.25, 1.50) as the
  headline cell and carries no note of the 2026-08-13 change.
- Lowering `risk_per_trade_pct` is mostly a tighter dollar stop, because most
  positions are already at one contract. The knob table in the fourth entry
  below called it "smaller positions"; that description is wrong.

**What is ruled out.** A value from the knob table, a Kelly or
volatility-scaled budget, a concentration cap, another de-risk trigger, and an
entry-side regime gate. The plan gives the reason for each.

**The 2026-09-05 flip.** Of the 28 window positions, 27 were priced in August
2026, before the last feasible print. The walk took different rows as the book
grew. The 09-05 export is gone, so this cannot be proved.

**Next.** [Item 5](next-steps.md#waiting-on-the-operator) stays open and
points at the plan. The first steps print what the study already computes and
need no registration.

## 2026-09-20 (fifth) — check_prose — unreadable prose is rejected when it is written

**A hook now checks every edit to `research/` and `docs/` prose against the
[writing guide](writing-guide.md#the-automatic-check).** Nothing in the
research changes.

**What it does.** `scripts/check_prose.py` counts words per table cell, per
sentence and per paragraph, figures per sentence, heading length and capitals
used for emphasis. It runs after every Edit or Write, in the main session and
in subagents. A failure goes back to the writer, who rewrites the block.

**What it does not do.** It cannot rewrite text, and it does not see edits made
through the shell. `make check-prose` covers those. It reports only the blocks
an edit touched, because the older files fail it wholesale.

**Next.** [`next-steps.md`](next-steps.md) §2.11 was the worst case and was
rewritten the same day. No new item.

## 2026-09-20 (fourth) — account_sim — the capital ladder prints again; no registered rung passes A3

**The drawdown fits the 25% bar from $75,000 up, and at no registered
capital.** Nothing ships: $75,000 is a post-hoc rung, printed in its own
labelled block.

_Era v4 · exports 2026-09-19 · report: `backtests/study_output/account_sim-latest.txt`
· [pre-registration](pre-registrations/f4_deployment/account_sim.md)._

**The rule.** The registration prints the ladder "On NOT FEASIBLE". Since the
2026-08-14 amendment that includes the case where
[A1](arm-index.md#account_sim) holds and A3 fails.

**What the code did.** It printed the ladder only when A1 failed, so today's
verdict printed no ladder. The ladder also tested A1 and A2 only.

**What changed.** The trigger is now the verdict itself. Each rung prints its
max drawdown and A3, from the same clause `evaluate()` uses. The registered
line about A1 and A2 is unchanged, word for word. Rungs above $50,000 come from
a new `grids.capital_ladder_posthoc` list and print under a post-hoc banner.

| Capital | Max drawdown | A3 | Set |
|---|---|---|---|
| $25,000 | 35.0% | no | registered |
| $35,000 | 26.7% | no | registered |
| $50,000 | 27.1% | no | registered |
| $75,000 | 22.1% | yes | post-hoc |
| $100,000 | 19.2% | yes | post-hoc |
| $150,000 | 19.7% | yes | post-hoc |
| $250,000 | 21.4% | yes | post-hoc |

A1 and A2 hold at every rung. The primary block did not move: the report diff
is the ladder, the config echo and the run stamp.

**Why capital matters at all.** Sizing is proportional, so drawdown as a share
of capital should not depend on capital. The exception is the one-contract
floor. At $25,000 the risk budget is $500, and most picks risk more than that
on a single contract. The floor still buys that contract, so a position carries
up to 3% of capital instead of the configured 2%.

**Where the drawdown is.** It is a January–April 2025 cluster, not the March
2026 sessions. The peak is 2025-01-10 and the trough 2025-04-09, across 28
one-contract bull call spreads. The worst single position is COIN at −$878.

**When it flipped.** The last FEASIBLE run was 2026-09-05 on 535 rows. The
first failing run was 2026-09-08 on 598 rows, and every run since is
numerically identical. The cost columns are not the cause: they are zero on
every row. Population growth and the re-marks landed in the same three days,
and the 09-05 export is gone, so the two cannot be separated.

**Open decision.** What to do about a book that is not feasible at the
operator's capital is not settled. The measured options at $25,000 are below;
none is a recommendation, and choosing one to clear the bar would be tuning.

| Knob | Value | Max drawdown | Cost |
|---|---|---|---|
| `risk_per_trade_pct` | 2% → 1.25% | 18.0% | smaller positions |
| `risk_per_trade_pct` | 2% → 1.5% | 25.1% | still fails |
| `caps.net` | 2.50 → 1.50 | 20.3% | positions 211 → 142 |
| `max_positions_per_day` | 3 → 2 | 26.7% | still fails |

**Next.** Filed in [`next-steps.md`](next-steps.md) under *Waiting on the
operator*.

## 2026-09-20 (third) — backtest classifier — six priced rows used strikes from the narrative; fixed

**The strike parser could take its numbers from a play's narrative instead of
its header, and six priced rows were priced on the wrong strikes.** The parser
is fixed. The six stored rows are not re-priced.

_Era v4 · exports 2026-09-19 · 2,545 play texts, 2,263 stored rows checked._

**The bug.** `classify.py::_extract_strikes` tried a three-strike pattern on
the whole play text before the two-strike one. A narrative such as "open
interest at 204/210/211" matched first. Nothing checked the result against the
structure, so a wrong pair that happened to be validly ordered passed every
gate.

| Date | Ticker | Tab | Header says | Priced on |
|---|---|---|---|---|
| 2024-11-26 | NVDA | BacktestResults | bull call 145/160 | 140/145 |
| 2024-03-25 | IWM | BacktestResults | bear put 200/185 | 204/210 |
| 2025-05-09 | SPY | BacktestResults | bear put 550/510 | 530/510 |
| 2024-08-23 | FCX | BacktestProxy | bull call 45/50 | 45/47 |
| 2024-02-27 | PINS | BacktestProxy | bull call 36/40 | 36/39 |
| 2024-02-06 | IWM | BacktestProxy | bull call 196/210 | 201/208 |

The three proxy rows are not strike tweaks. `proxy_detail` shows the tweak
changed the expiry only, or tweaked the strikes the parser had already grabbed.
None of the six is among the 14 pre-fill rows or the 49 `Open`-fill rows.

**The fix.** Strikes come from the header, the text before the second `|`. The
whole text is the fallback when the header has none, which happens on 5 of
2,545 texts. A vertical whose strikes are in the wrong order for its direction
is refused with `skip_reason = inverted_vertical`, the same way a debit priced
to a credit is refused. After the header fix no real text names a vertical
inverted, so the refusal drops nothing today.

**Effect on classification.** 12 of 2,545 texts classify to different strikes.
No structure label and no credit flag moves. All 12 butterfly and condor plays
are unchanged. `shared/identity.py` is untouched, so row identity is the same.

**Not fixed.** Six `bear put spread` plays are classified `bear_call_spread`
because their narrative mentions bear call spreads. All six are already vetoed
before pricing, so nothing prices wrong today. Filed in §2.11.

**Next.** The six rows join the re-price decision in the entry below.
`tests/test_backtest.py` gained 18 tests; the suite is 3,878 green.

## 2026-09-20 (later) — stored book — a cache-only re-price moves 370 of 2,234 rows

**The stored book does not reproduce under current code, and most of the
movement comes from the cache rather than the code.** Nothing was written: this
is a measurement, run from the cache with every Sheets writer disabled.

_Era v4 · exports 2026-09-19 · code `80b0f3f` · 598 BacktestResults + 1,636 of
1,665 BacktestProxy rows · per-row table and scripts:
`backtests/reprice_census_20260920/`._

| Tab | Rows | Moved | Moved > 0.10 [R](glossary.md#r) | Sign flips | Lost pricing | Newly priced |
|---|---|---|---|---|---|---|
| BacktestResults | 598 | 135 | 38 | 20 | 80 | 0 |
| BacktestProxy | 1,636 | 235 | 77 | 31 | 21 | 53 |

**Causes, moved rows.**

| Cause | Rows | Code or cache |
|---|---|---|
| Exit fill deferred to the next two-sided day | 61 | code (`51c95bd`) |
| Same entry, different exit path | 60 | cache is deeper |
| No local cache file | 57 | cache gap |
| Newly priceable | 53 | cache is deeper |
| Entry side rule | 41 | code (`09aa02c`) |
| Entry day moved | 39 | cache is deeper |
| Other unpriceable | 24 | cache gap |
| Falls to `underlying_trend` | 19 | cache is deeper |
| Exit booked before the fill | 14 | code (B2) |
| Refused, debit priced to a credit | 1 | code |

So about 117 rows move because the code changed, and the rest because the cache
did. A row that moved is not always a row that was wrong. HYG and LQD dominate
the largest moves, on thin one-sided quotes.

**The 14 pre-fill rows.** All 14 re-price cleanly, all 14 move, and 9 flip
sign. The choice between excluding and re-pricing them barely matters to the
book:

| Book | [meanR](glossary.md#meanr) | Rows |
|---|---|---|
| Stored as it is | +0.0395 | 1,364 |
| The 14 excluded | +0.0427 | 1,350 |
| The 14 re-priced | +0.0457 | 1,364 |
| Whole book re-priced, rows priced both times | +0.0329 → +0.0210 | 1,263 |
| The 14 alone | −0.2709 → +0.3377 | 14 |

**The `Open`-fill rows.** The census of 49 rows reproduces: 22 results and 27
proxy. 17 are HYG. Six would flip sign under the side rule, and three overlap
the 14. The shift in their mean cannot be estimated from the entry price alone,
because several stored entries are near zero.

**What blocks an honest full re-price.** 80 BacktestResults rows cannot be
priced offline at all. 57 have no cache file and 20 have a shallow one, the
damage the three-month `startDate` default left. A full re-price needs a
Barchart refetch first.

**Recommendation, not yet decided.** Exclude the 14 through `fill_trusted`
rather than `--redo` them. Re-price the six wrong-strike rows, because those
are wrong rather than old. Leave the whole-book re-price until the cache gap is
refetched.

**Next.** All three decisions are filed in [`next-steps.md`](next-steps.md)
under *Waiting on the operator*.

## 2026-09-20 — suite re-run read in full — 18 of 31 verdicts moved, two touch shipped rules

**The 2026-09-19 suite run moved far more than the two verdicts first
reported.** Nothing ships and no rule is changed here. Two results bear on
shipped rules and wait on the operator.

_Era v4 · exports 2026-09-19 · 598 real / 1,665 proxy rows · code `8e9b6a7` ·
every report under `backtests/study_output/` · recorded in
[study-results](study-results/)._

**In production.** Nothing changes. `docs/deployment-rules.md` is not edited.

**What was stale.** Commit `f27724d` recorded the run but no hand-written
surface was updated. [`study-map.md`](study-map.md), `catalog.py`,
[`overview.md`](overview.md) and
[`deployment-evidence.md`](deployment-evidence.md) now quote the new run. The per-study rows are in the
[study map](study-map.md#operator-reading-2026-09-20).

| Of 31 catalogued studies | Count |
|---|---|
| Moved a verdict token or a registered criterion | 18 |
| Moved numbers only | 9 |
| Unchanged | 4 |

**The two that touch a shipped rule.**

| Study | What it prints now | Rule | Standing |
|---|---|---|---|
| `exit_switch_structure_study` | `shipped BEAR_HE clause  Δ=-4.5205`, `retained 47%`; 09-04 read +0.7735 and 0% | [§5](../docs/deployment-rules.md#s5) BEAR_HE trail | an observation; the registered rollback census is still underpowered at 8 of 25 dates |
| `bear_arm` | [B2](arm-index.md#bear_arm) exit fix `NOT met`, and `REVERT CONDITION FIRED` | bear exit profile | the report asks for a production config change |

**Other moves worth knowing.**

| Study | Move |
|---|---|
| `account_sim` | FEASIBLE → `NOT FEASIBLE AT $25,000`; entry above |
| `portfolio_delta` | CANDIDATE → `NOISE`; criterion 1 alone fails at `+0.0519 R CI95 [-0.0333, +0.1407]` |
| `concurrency_correlation` | NOISE → `RESTATEMENT`; it restates `portfolio_delta` and does not ship |
| `exit_from_text` | first `CANDIDATE`, `E2 MECH LVOL N=3`; an intake filter, so a proposal only |
| `hedge_timing` | H1-GAP CONTRARY → `NULL`; the [§4](../docs/deployment-rules.md#s4) gap-up prohibition now rests on H3-GAP alone |
| `trigger_entry` | tally now `{'LATE-ENTRY': 3}` |

**Why `portfolio_delta` moved.** The candidate was never robust: its interval
cleared zero by 0.0131 on one arm. Restricting the new export to the old 166
dates already fails criterion 1, at `+0.0771 R CI95 [-0.0093, +0.1727]`. So the
duplicate and stale-row repairs of 2026-09-06 and 09-07 carried most of the
drop, and the 39 added dates the rest. The study code did not move the verdict.
Nothing in production depended on it.

**Caveats.** Every one of these was read on a book that mixes pricing regimes
(entry below). The moves were found by comparing the catalog with the newest
record, and the quoted lines were checked against the reports.

**Next.** The State of play block above is rewritten to this run. Two decisions
are filed under *Waiting on the operator* in [`next-steps.md`](next-steps.md).

## 2026-09-19 (sixth) — the 14 pre-fill exits are now detected, not just counted

**`scripts/backtest_study/lib/prefill_audit.py` finds every stored row whose
exit was booked before its fill, on every `load_book` call.** It reports and
never gates, the same contract as
[`basis_audit.py`](../scripts/backtest_study/lib/basis_audit.py).

_Population: v4, the 2026-09-19 exports. 14 of the 1,325-row pooled book._

### Why a detector rather than a fix

The defect is already fixed — B2 stamps pre-fill grid days `pre_entry`, and no
row written since 2026-09-08 can carry it. What was missing is that the rows
written BEFORE the fix are still in the book and nothing found them. A census
run by hand once is not a check; it does not run again next week.

| | Count |
|---|---|
| pooled book | 1,325 |
| `ok` | 1,311 |
| `pre_entry_exit` | **14** |
| unanswerable | 0 |

The 17 found in the raw tabs become 14 here: three never reach the book, dropped
by the proxy calibration gate or for having no path.

### The fill day is READ, never re-derived

`entry_day = legs[0].expiration - dte_entry`, off the row's own stamp. Deriving
it from the option cache would be wrong, because that cache has grown since
these rows were priced — the `HISTORY_START_DATE` fix, the far-call fetch and
178 restored files. That is the same mistake that cost a separate hunt earlier
the same day, in `bear_rewrap`'s mirror, and the module says so where someone
would otherwise repeat it.

One case is deliberately NOT flagged: a fill at or before the grid's first day
is position 1. That is the legacy `entry_timing: signal_eod` shape, where the
fill IS the signal day and the grid starts after it, so no exit on the grid can
precede it. Treating it as unanswerable would have blanked the audit on a whole
timing convention rather than cleared it.

### What a study should do

`python3 -m scripts.backtest_study.lib.book --validate` prints the tally and
names every offending row. A study that pools stored outcomes filters on
`fill_trusted`; one that re-replays from marks never reads the stored outcome
and is unaffected either way.

---

## 2026-09-19 (fifth) — TLT 2025-04-01 is not a new defect: it is a phantom pre-entry exit, and 16 others like it

**The −754% is the CORRECT number.** The stored +100% was a `profit_target`
booked two grid days BEFORE the position was filled, on a Black-Scholes mark.
That is the phantom pre-entry P&L the robustness fold's B2 removed on
2026-09-08, and TLT is one of 17 legacy rows still carrying it.

_Population: v4, the 2026-09-19 exports. 1,375 rows across both tabs carry a
path and a `days_held`._

### What actually happened

The entry did not move. It is byte-identical in both rows — `px=0.6` on the
short 89P, `px=0.25` on the long 86P, both `barchart_open`, `entry_option_price`
−0.35. The hypothesis filed earlier that day, that a −754% credit row meant its
entry had moved, was wrong.

| Grid day | Stored row | Current code |
|---|---|---|
| 1 | −1.6790, `bs+bs` | blank, `pre_entry` |
| 2 | **0.0000**, `barchart+bs` → `profit_target`, +100% | blank, `pre_entry` |
| 3 | −0.4650, `barchart+barchart` | −0.4650, the FILL |
| … | | runs to expiry |
| 38 | −2.9900 | −2.9900 → `expired`, −754% |

`dte_entry` puts the fill on grid day 3. The stored row exited on day 2, at a
net of exactly zero produced with one leg modelled. A bull put spread sold for
0.35 credit against a 3.00 width finishing at −2.99 is max loss, and
`pnl_on_risk_pct` −0.9962 says so.

### The census

Recovering each row's fill day from `dte_entry` and comparing it with
`days_held` finds every row of this shape exactly:

| | Count |
|---|---|
| rows with a path and a `days_held` | 1,375 |
| exit booked BEFORE the fill | **17** (15 proxy, 2 results) |
| of those, priced by `bs` on ≥1 leg that day | 13 |
| **created AFTER the 2026-09-08 fold** | **0** |

The newest is stamped 2026-09-07 00:18:58. **The fix holds** — no row written
since can carry this. The 17 are legacy rows to re-price or exclude, not a live
defect, and their P&L is where the damage sits: +4.97, +4.48, +3.60, +2.03,
+1.93 and −4.24, −2.35 among them, all on days the position did not exist.

### QQQ 2025-04-28 is a different and benign cause

Not pricing at all: the proxy's expiry SNAP moved, 2025-08-29 → 2025-10-24, as
the cache gained contracts. The new pick has no usable history for that strike
pair, so the row falls to `underlying_trend` and prints no P&L. Nothing is
mispriced; a different contract was chosen.

### What this changes for the queue

A deliberate re-price of the book is now better understood, not blocked. The
three causes that move a stored row are separated: the exit-fill rule (3 of 61
on April 2025), `09aa02c`'s entry rule, and these 17 phantom exits. Only the
last is a defect in the stored numbers, and it is bounded and enumerable.

---

## 2026-09-19 (fourth) — the exit FILLS on the next two-sided day, not on the trigger day's bid-less mark

**The exit trigger and the exit fill are now two different days.** A rule fires
on the marked path as it always did; if that day has no bid on every leg, the
FILL is carried to the next priced day that does, `days_held` becomes that day,
and a new `exit_fill` column says which happened. Nothing is backfilled.

_Population: v4. Measured on both tabs, and A/B'd on the April 2025 proxy rows._

### The rule

`_zero_bid_mark` values a leg quoted `bid 0 / ask N` at `ask/2`. That is the
right LIQUIDATION mark for a mark-to-market path and the wrong price for a FILL,
because nothing is bid — the same confusion between the two jobs that
[the entry fix](#2026-09-19--backtest-entry-pricing--a-sold-leg-with-no-bid-fills-at-0-and-a-debit-that-prices-to-a-credit-is-refused)
corrected at the other end of the trade.

| `exit_fill` | Meaning |
|---|---|
| `same_day` | the trigger day was fillable |
| `deferred_n` | carried n grid days to the next two-sided quote |
| `no_two_sided` | no fillable day ever arrived; the fill stays on the trigger mark and the row is flagged |
| `""` | written before 2026-09-19 |

The marked path, MFE/MAE and which rule fired are all untouched. A deferral
moves WHEN the position closed and AT WHAT, never WHY. `cap_open` / `expired`
take the last priced day by construction and are never deferred.

### Scale, measured both ways

| Measure | Result |
|---|---|
| one-sided exit-day leg quotes, both tabs | 79 / 2,707 (2.9%) |
| rows with at least one | 72 / 1,375 (5.2%) |
| April 2025 proxy rows moved, rule OFF vs ON, one cache | 3 / 61 (4.9%) |

The A/B is the honest number: same code, same cache, only the rule toggled. All
three movers are HYG bear put spreads, and they move in BOTH directions —
−0.379 → −0.571, −0.843 → −0.519, −0.552 → +0.698. This is not a bias. It
replaces a price nobody was bidding with one that was there.

The −0.552 → +0.698 row is the shape to understand: a trailing stop triggered on
day 6 into a dead market and could not be filled until day 10, by which time the
position had recovered. That is what being unable to get out actually does, and
it cuts the other way just as often.

### A separate divergence, found while measuring

Re-pricing April 2025 under current code moved **8 of 57** stored proxy rows,
and only 3 of those are the exit-fill rule. The other 5 are the entry rule of
`09aa02c` plus a cache that is deeper than the one those rows were priced on.
Two are large:

| Row | Stored | Re-priced now |
|---|---|---|
| TLT 2025-04-01 | `profit_target`, day 2, +100% | `expired`, day 38, −754% |
| QQQ 2025-04-28 | `stop_loss`, day 30, −75% | `direction_only`, unpriced |

**Not diagnosed, and not this change.** It is recorded because it says something
the queue should know: the stored book no longer reproduces under current code
on more rows than the mirror work implied, so a full re-price would move more
than the exit-fill rule alone. TLT at −754% in particular is a credit row whose
entry moved; it wants a look before anyone re-prices the book on purpose.

---

## 2026-09-19 (later still) — the 2025-04-09 re-price, and the two mirror drifts it exposed; `hedge_structure` unblocked

**`hedge_structure` runs again: R2 is 1,322 / 1,322 and the study reaches a
verdict for the first time since 2026-09-08.** Nothing ships — H0 FILL is NOT
MET and H2 is NOT EVALUABLE on a power floor (n=2 on the worst-decile dates).
Getting there took the stored HYG row re-priced and TWO drifts fixed in the
research mirror.

_Population: v4, the 2026-09-19 16:45 exports (598 results rows, 1,665 proxy
rows, 2,781 analysis rows). The book is the 2026-09-08 one with 2025-04-09
re-priced._

### The re-price

`proxy --date 2025-04-09 --redo --cache-only` replaced all 9 rows on that date.
Two changed materially.

| Ticker | Before | After | Why |
|---|---|---|---|
| HYG | −0.37 entry, CREDIT, +100% | +0.97 entry, BEAR_HE, −100% | the side-aware entry rule (09aa02c) |
| SPY | `underlying_trend`, blank P&L | `strike_expiry_tweak`, 6.20 entry, −77% | the cache is deeper than it was |

SPY is a side effect of the date-level `--redo`, not of the pricing change: the
restored and re-fetched cache now carries a priceable pair, so a direction-only
verdict became a real priced row. The other seven are unchanged but for the cost
columns, which populate for the first time.

### Drift 1 — the mirror priced the ENTRY with a liquidation rule

`bear_rewrap` imported `_zero_bid_mark` and applied it at entry. `09aa02c`
displaced it there with `_entry_side_mark`, and production's next branch is the
PLAIN mark, so `_zero_bid_mark` is now unreachable at entry. The mirror
therefore needs a SECOND write-time basis beside `B5_SINCE`:

| Row written | Daily marks | Entry fill |
|---|---|---|
| before 2026-09-08 15:05:25 | plain mark | plain mark |
| 09-08 15:05:25 → 09-19 12:50:45 | B5 re-mark | B5 re-mark |
| after 2026-09-19 12:50:45 | B5 re-mark | side-aware |

The boundary is not a judgement call: nothing was written between 2026-09-08
22:02:15 and the 16:45:19 re-price.

### Drift 2 — the mirror DERIVED the entry day instead of reading it

This is the one that mattered, and it is the more general lesson.
`entry_date_for` picks the first grid day on which EVERY leg has a cached bar.
Production picked its day from the bars it held AT PRICING TIME, off the ANCHOR
leg alone, and carried the other legs forward. Those are different questions,
and the cache has since gained bars production never saw — the
`HISTORY_START_DATE` fix, the far-call fetch, and the 178 restored files.

On HYG they diverge: production filled 2025-04-14 off the long leg's first bar;
the mirror waited until 04-16 for both legs and rebuilt a 0.47 debit against the
stored 0.97.

**The day never needed deriving — it is recorded.** `dte_entry` is stamped as
`(expiration − entry_day).days` on the anchor, so the day reads back exactly.
The gate now reads it.

| | agree | differ |
|---|---|---|
| recorded vs derived entry day, 1,325 records | 1,324 | 1 (HYG 2025-04-09) |

That 1,324 is why the drift went unnoticed for so long, and why a rule change
would have been the wrong fix: the first rule I tried — mirror production's
anchor rule — reproduced HYG and broke 13 `bull_put_spread` rows that pass
today, because for those the anchor leg has bars now that it did not have then.
Reading the stamp is immune to that; re-deriving never can be.

A SUBSTITUTION has no recorded entry day — it was never traded — so it keeps
deriving one.

### What moved

Both gates now pass everything: bear debit 483/483, full universe 1,325/1,325.

| Study | Before | After | Verdict |
|---|---|---|---|
| `bear_rewrap` `long_diag` | dR +0.153, CI [+0.025, +0.281] | dR +0.159, CI [+0.035, +0.288] | unchanged, still clear of 0 |
| `bear_rewrap` `long_put` | dR −0.027, CI spans 0 | dR −0.022, CI spans 0 | unchanged null |
| `bear_rewrap` `wider` | dR −0.065, CI spans 0 | dR −0.064, CI spans 0 | unchanged null |
| `financed_spread` baseline | n=918 | n=919 | unchanged |

The cell counts move because the BOOK was re-priced, not because the mirror was.
The mirror change is verdict-neutral by construction: the gate read 482 ok / 1
fail both with and without the side basis, and the recorded-day fix moves one
row.

---

## 2026-09-19 (later) — the option-history cache is no longer deleted before a refetch, and proxy rows carry the cost columns

**Two code fixes from the [§2.11](next-steps.md#s2-11) queue. Neither changes a
price, a verdict or a recorded row.** The first stops a failed refetch from
destroying a cache file; the second stops the proxy writer from dropping three
columns it already computes.

_No population: these are code-behaviour claims, pinned in `tests/`, not data
claims. Suite 3,757 green._

### The cache is kept until a complete fetch replaces it

`scripts/backtest/shared/history.py` unlinked a cache file whose history did not
reach back far enough, then refetched. When the refetch returned no rows, nothing
was kept. That is how 178 files were lost between the 2026-09-05 snapshot and
2026-09-08 ([record](archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md#2026-09-08-eighth--far-call-fetch-run-twice-the-scraper-was-re-issuing-the-pages-three-month-default-range-fixed-178-lost-cache-files-restored-hedge_structure-stays-blocked-at-r2)).

The file is now never unlinked on the way in. A fetched file is staged beside the
cache and installed with `os.replace`, the same way
[`export_tabs.py`](../scripts/export_tabs.py) installs a pulled tab.

The run's own behaviour is unchanged. A shallow series is still dropped from the
in-memory maps, so a play that needed the earlier dates still prices as no-data.
The fix is about what survives on disk, not what a run prices on.

The underlying trigger was already gone: the scraper was re-issuing the page's
default three-month `startDate`, fixed in `lib/barchart/session.py`. The unlink
was the second half of that loss and stayed fragile on its own.
`tests/test_backtest_history_cache.py` pins all four cases.

### Proxy rows carry `pct_stale_days`, `cost_total` and `cost_basis`

`proxy.py::_evaluate` copied `_RESULT_COLS + _BASIS_COLS` off the simulation and
never `_COST_COLS`, so all 1,665 stored proxy rows are blank in those three
columns even on the priced tiers. `BacktestResults` carried them. This is the
same shape as the `exit_basis` gap fixed 2026-09-02, and the comment two lines
above the copy loop describes it.

| | `BacktestResults` | `BacktestProxy` before | `BacktestProxy` after |
|---|---|---|---|
| `pct_stale_days` | written | blank | written |
| `cost_total` | written | blank | written |
| `cost_basis` | blank while both cost knobs are 0 | blank | blank while both cost knobs are 0 |

`cost_basis` staying blank is the costs-off convention, not a remaining gap.

**The fix does not backfill.** The 1,665 rows already on the tab stay blank until
a `--redo` re-run, so a study that splits the proxy book on `cost_total` reads
every stored row as "not run under the cost model" — which is true of all of
them today.

---

## 2026-09-19 — backtest entry pricing — a sold leg with no bid fills at 0, and a debit that prices to a credit is refused

**Two production changes to `scripts/backtest/`: entry pricing is side-aware on a
one-sided quote, and a debit structure that prices to a net credit is no longer
written at all.** Nothing about study conclusions ships — this changes what the
ENGINE does, so the next run of either writer will differ from the tab on a small
number of rows. No recorded row was re-priced; that stays an operator decision.

_Population: v4, the 2026-09-08 22:38 exports (598 results rows, 1,665 proxy
rows). Row counts below were taken over both exports._

### The rule

Two separate rules, in the order the engine applies them.

**Entry pricing.** A leg whose entry-day quote has no bid is filled on the side it
actually trades: the BID, which is 0, when the leg is SOLD, and the ASK when it is
BOUGHT. Before, entry reused `_zero_bid_mark` — a LIQUIDATION rule, written for
daily marks and sign-independent — which handed a leg being sold half the ask as
premium RECEIVED.

The scope is deliberately narrow. The rule governs only an entry that falls
through to the quote-derived mark. An entry-day `Open` print still wins ahead of
it, and a genuine two-sided quote prices exactly as before. A row with no Bid and
no Ask column at all is NO QUOTE DATA, not a zero bid, and keeps its existing
fallback — that distinction is the whole change and is pinned by test.

**The gate.** A structure whose canonical name fixes it as a DEBIT
(`bull_call_spread`, `bear_put_spread`, `long_call`, `long_put`) that prices to
`entry_net < 0` is not priceable. No row is written. The real backtest tallies it
`debit_priced_to_credit`; the proxy puts that in `skip_reason` and appends the
reason to `proxy_detail`. The gate runs before the exit profile is chosen, so
`exit_basis = CREDIT` can no longer be reached from a fabricated credit.

### What it changes on the three known rows

| Row | Before | After |
|---|---|---|
| HYG 2025-04-09 (proxy) | entry −0.37, `exit_basis` CREDIT, +100% | entry **+0.97**, `exit_basis` BEAR_HE, **−100%** |
| SMH 2024-07-17 (proxy) | entry −0.50, `exit_basis` CREDIT, +448% | **refused**, `debit_priced_to_credit` |
| IWM 2024-03-25 (results) | entry −2.89, `exit_basis` CREDIT, −108% | **refused**, `debit_priced_to_credit` |

HYG is the one the entry rule fixes: the short 72P had no bar on the fill day, so
the entry carried its 04-10 `bid 0 / ask 2.68` snap and `ask/2` gave 1.34. It now
prices at 0 and the spread is a 0.97 debit, tagged `barchart_side`.

SMH and IWM are different: both legs printed, two-sided, on the entry day, so the
entry rule does not touch them. SMH's short 235P printed 8.05 against its own 7.00
ask — a bad print. IWM's legs are strike-inverted for their label: a bear put
spread long the 204P and short the 210P is not one, which is a CLASSIFICATION
defect, not a quote defect. The gate catches both because the arithmetic is the
same. **The classifier was not fixed here**; that is a separate item.

### What was deliberately not done

Legs quoted `bid == 0` on the entry day but filled at an `Open` print number 22
rows in BacktestResults and 27 in BacktestProxy. Extending the side-aware rule
over the `Open` print would reprice all of them — and 21 of the 22 and 26 of the
27 PREDATE the B5 fold, so it would rewrite four months of already-recorded
pre-fold evidence. That was not asked for and was not done.

| Shape | BacktestResults | BacktestProxy | of which pre-B5 |
|---|---|---|---|
| entry through the zero-bid path (repriced by this change) | 0 | 1 | 0 |
| `bid == 0` at entry but filled at an `Open` print (untouched) | 22 | 27 | 21 / 26 |

The exit fill was also left alone. `_price_leg` still uses `_zero_bid_mark` on
every daily mark, including the one the exit is taken at, and the same asymmetry
exists there: closing a LONG leg into a 0 bid receives `ask/2` rather than 0. The
case for changing it is weaker — a liquidation mark is the right question for a
mark-to-market path, and the exit day is picked by rules that read that path — but
it is not settled, and it is filed rather than decided.

### What happens next

[`next-steps.md`](next-steps.md) §2.11: the HYG fabricated-credit row is closed,
one row is added for the exit-side asymmetry, and one for the strike-inverted
`bear_put_spread` classification. `hedge_structure`'s R2 blocker is NOT closed —
the stored HYG row still holds −0.37 and only a re-price changes that.
