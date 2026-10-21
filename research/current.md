# Backtest tuning — current

The recent end of the log. Dated entries run below the state of play. Older
work is in [`archive/`](archive/), indexed by the [README](README.md).
Conventions for this folder: terms in [`glossary.md`](glossary.md), study-local
labels in [`arm-index.md`](arm-index.md), house style in
[`writing-guide.md`](writing-guide.md).

## State of play

**2026-10-15: where the programme stands.** The gate reads `WAIT` until
`dip_buy` grades, with a backstop of 2027-10-13
([plan](next-steps.md#plan-20261013)).

| Step | State |
|---|---|
| P0, the kill rule | registered 2026-10-13 as `programme_gate` |
| P1, same-ticker read | `ARM M1` `CONTRARY`, corrected 2026-10-15 ([entry](#2026-10-15--mechanical_benchmark-p1-corrected-the-contrary-survives-the-spot-fix-and-the-tier-port)) |
| P2, SPY read | `DOES-NOT-BEAT`, post hoc ([entry](#2026-10-15--spy_benchmark-the-picks-do-not-beat-a-spy-call-spread-gross)) |
| P3, the tier port | done 2026-10-13 |

Two follow-ups are filed in [`next-steps.md`](next-steps.md) under *Waiting
on the operator*, items 16 and 17:

- The cache backup never prunes. Each push is a full archive of about 530MB,
  and the per-batch pushes filled the operator's Drive on 2026-10-13/14.
- The spot reads calls only. Adding puts would cut `ARM M1`'s
  `no_spot_at_signal` drops from 8 to 6; it is not adopted.

**2026-10-14: the SPY-only benchmark is registered post hoc and built; it awaits a 149-contract fetch**
([entry](#2026-10-14--spy-only-benchmark-registered-post-hoc)).

**2026-10-14: a mechanical ATM/+5% call spread on the same tickers beat the picks, gross; `mechanical_benchmark` `ARM M1` meets `CONTRARY`, and `programme_gate` reads `WAIT`**
([entry](#2026-10-14--mechanical_benchmark-the-mechanical-spread-beats-the-picks-on-their-own-tickers)).

**2026-10-13: the keep-or-retire rule for the flow layer is registered before any P1 result; `programme_gate` reads `WAIT`**
([entry](#2026-10-13--programme_gate-registered-before-any-p1-result)).

**2026-10-13: the SOTA paper's 18.3% rests on one seed and a checkpoint picked on its test window; it adds no evidence for this book**
([entry](#2026-10-13--external-read-sota-paper-adds-no-evidence-for-this-book)).

**2026-10-13: neither a long earnings straddle nor a calendar pays; `earnings_vol` prints `NULL` on both arms**
([entry](#2026-10-13--earnings_vol-neither-earnings-structure-pays-and-the-calendars-edge-is-the-spread)).

**2026-10-12: a short SPY condor loses in the book's bad months but not on its bad days; `index_vrp` prints `NO-TAIL-LINK`**
([entry](#2026-10-12--index_vrp-a-short-spy-condor-shares-the-books-bad-months-not-its-bad-days)).

**2026-10-12: nothing known at entry predicts whether the underlying moves the play's way; `direction_hit` prints `NULL`**
([entry](#2026-10-12--direction_hit-nothing-known-at-entry-predicts-the-underlyings-direction)).

**2026-10-12: the regime map finds one condition both eras agree on: Tier A makes money on falling-market dates**
([entry](#2026-10-12--regime_map-tier-a-on-falling-market-dates-is-the-one-cell-both-eras-agree-on)).

**2026-10-12: a walk-forward rule-switching adapter prints `ADAPTS` on v4
in-sample dates, from one switch onto a hindsight rule; v3 never switches,
and the forward read waits behind the seal**
([entry](#2026-10-12--adaptive_ladder-the-walk-forward-adapter-beats-m0-once-on-a-menu-built-in-hindsight)).

**2026-10-12: an exploratory read found v4 a bull tape where only the vetoes
lift the ladder above random picks; its one lead, `dip_buy`, is registered
and waits behind the seal**
([entry](#2026-10-12--exploratory-read-v4-is-a-bull-tape-and-the-vetoes-are-its-only-ladder-edge)).

**2026-10-09: seven parked drafts were accepted by default and run; nothing
ships** ([entry](#2026-10-09--parked-drafts-accepted-by-default-and-run)).

**The suite reads the re-priced book again (2026-09-28), and 13 verdicts
moved.** On 2026-10-01 a bigger stop failed to rescue the 1-contract floor
([entry](#2026-10-01--entry-window-and-narrow_to_fits-cached-cells)). On 2026-09-29 the operator ruled on the five items it raised, and
the registered `account_sim` cell re-ran `NOT FEASIBLE`
([entry](#2026-09-29--operator-rulings-the-150-cell-and-the-2026-column)). The loader rulings are built, every calibration gate passes, and the
run is recorded
([entry](#2026-09-28--loader-rulings-and-suite-re-run--the-book-reads-again)).
The tables below still describe the 09-19 book until this block is rewritten.

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
| `emission_timing` | [ARM P](arm-index.md#emission_timing) sub-cut 2 | repeats that had already moved against the play clear all six, at −0.2579 | [record](study-results/f1_selection/signal/emission_timing.md) |
| `bear_rewrap` | [long_diag](arm-index.md#bear_rewrap) | 4 of 5 again, failing the year clause; the P1 portfolio check is met on no substitution | [record](study-results/f3_structure/bear_rewrap.md) |
| `bear_arm` | [B2](arm-index.md#bear_arm) exit fix | `NOT met`: `sl .50` Δ=+0.030, CI [−0.003, +0.061] | [record](study-results/f1_selection/bear/bear_arm.md) |
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
| credit sl-none | floor met on 2026-10-06 (50 rows over 23 dates); not fired, not settled ([evidence](deployment-evidence.md#open-pre-registered-rollback-triggers)) |

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

## 2026-10-21 — pending open rows leave the outcome book

**A trade still inside its path window is no longer graded as an outcome.**
The study loader drops it and says how many it dropped. Nothing ships:
production, the backtest and the tabs are unchanged.

Operator ruling, 2026-10-21, made by the main session on the operator's
delegation. Population: the pre-reprice v4 exports in
`backtests/to_evaluate/`, exported 2026-10-21 13:34, before the in-place
re-price finished. Their latest `path_data_end` is 2026-10-16.

### The rule

- An `open_at_data_end` row whose path window has NOT closed is **pending**.
  Outcome studies exclude it.
- An `open_at_data_end` row whose window HAS closed stays a
  [`cap_open`](glossary.md#cap_open) outcome at its last mark, as ruled on
  [2026-09-28](#2026-09-28--loader-rulings-and-suite-re-run--the-book-reads-again).
  Its data simply stopped, often because the contract stopped quoting.
  Dropping it would drop illiquid losers.

Why: a trade still inside its window is graded on an interim mark. Since
`308be6a` the daily loop re-prices these rows in place, so each one becomes
an outcome on its own once it finishes.

### How the window is decided

- **Window end.** `signal + min(nearest leg DTE, path cap)`. The loader calls
  production's own `path_end()` in `scripts/backtest/shared/history.py`. That
  is the function `plays.build_needed_ends` uses, and the same end
  `simulate._simulate` computes. The [path cap](glossary.md#path-cap) is 120
  days.
- **As-of.** The latest `path_data_end` across both exports, called the
  export's data end. It is a property of the data. A file's mtime changes on
  a copy, and the latest signal date can trail the data.
- **Closed.** No weekday session falls after the as-of and on or before the
  window end. A window ending on a Saturday is closed by the Friday before.

### What it does to the current exports

Counts are rows in each file, before the loader's own filters.

| Export | `open_at_data_end` | Pending, excluded | Window closed, kept |
|---|---|---|---|
| `BacktestResults` | 210 | 163 | 47 |
| `BacktestProxy` | 84 | 65 | 19 |

These are the pre-reprice exports. The re-price running now will finish
some pending rows and move their data end, so the next export's counts
will differ.

### What moved on the refreshed exports (2026-10-21 14:48)

**The flow layer's keep-or-retire picture did not move, but `PG-M` is now
unread.** The gate still reads `WAIT`. Nothing ships.

The exports now hold 1,103 results, 2,142 proxy and 3,546 analysis rows. The
re-price and the 10-19/10-20 plays finished. The loader excludes 188 pending
rows and keeps 16 closed-window `cap_open` rows.

| Input | Before (2026-10-15 / 10-12) | Now (2026-10-21) |
|---|---|---|
| `dip_buy` forward | `STILL-OPEN`, 0 of 30 dates per arm | `STILL-OPEN`, 0 of 30 dates per arm; 27 rows on 11 signal dates sealed |
| `dip_buy` SPY census | 2 days since 2026-09-23, 0 below | 20 days, 3 below the 50-day SMA |
| `dip_buy` v4 Tier A+B, below - above (post hoc) | `+0.096  CI95 [-0.164, +0.322]`, n 112 / 630 | `+0.091  CI95 [-0.187, +0.334]`, n 105 / 598 |
| `dip_buy` v4 Tier A, below - above (post hoc) | `+0.306  CI95 [+0.062, +0.537]` | `+0.280  CI95 [+0.007, +0.538]` |
| `mechanical_benchmark` | `SAME-TICKER READ`, `ARM M1` `CONTRARY` | `NOT BUILT — AWAITING SCRAPE` |
| `programme_gate` | `WAIT`, row 4 (`PG-M` `CONTRARY`) | `WAIT`, row 5 (`PG-M` `NOT READ`) |

- **Why `mechanical_benchmark` lost its read.** The re-price replaced rows and
  the new plays added others. Floor 4a now counts 15 `ARM M1`/`ARM M2` pairs
  awaiting a fetch, where it counted 0. No arm prints a grade until they are
  fetched. The fetch plan lists 6 `M1` and 25 `M2` current-era contracts.
- **After the fetch, still `NOT BUILT`.** Five fetch rounds took `ARM M1` to 0
  awaiting, `ARM M2` to 2 and `ARM M2L` to 9, with no network errors. Floor 4a
  still counts 2 `ARM M2` pairs, so no arm is graded. One more round may close it.
- **The 2026-10-15 `CONTRARY` stands.** This run neither confirms nor
  reverses it. It cannot be re-read on the new exports until the operator runs
  the fetch.
- **The gate.** `PG-M` is `NOT READ`, `PG-D` is `STILL-OPEN`, so row 5 reads
  `WAIT`. Under `PG-UNPOWERED` set to `burden on the picks`, a `NOT BUILT`
  would count as `DOES NOT BEAT` and row 4 would read `WAIT` too. The outcome
  is the same. `dip_buy` needs about 138 more forward signal dates for its
  below arm, and the seal has not lifted.

### The rulings as built

| Ruling | What the code does now | Where |
|---|---|---|
| Pending rows leave the book | `load_book` drops them by default and prints a `pending:` line to stderr. `diag["pending"]` holds the counts by source and the as-of. | `lib/book.py::is_pending`, `load_book` |
| Closed-window open rows stay | Admitted as `cap_open` on the Trade cut at `path_data_end`, unchanged since 2026-09-28. | `lib/book.py`, `replay_basis.bounded` |
| One window rule | The window end comes from production's `path_end()`, never a second copy. | `lib/book.py::window_end` |
| Studies that grade open rows themselves keep them | `adaptive_ladder`, `refuse_floor_forward` and `index_bear_hedge` pass `include_pending=True`. Each record carries `pending`. | the three study modules |

### What is unresolved

- **Three registered studies keep pending rows.** Their registrations say
  what to do with an open row, and the new default would change what their
  gates read.
  - [`adaptive_ladder`](arm-index.md#adaptive_ladder) counts an open row at
    its stored mark and never treats it as known.
  - [`refuse_floor_forward`](arm-index.md#refuse_floor_forward) stops its
    complete prefix before the first date holding an open position.
  - `index_bear_hedge`'s G-OPEN gate counts open rows in the sleeve.

  None of the three registrations was tagged. Bringing `adaptive_ladder`
  under the ruling needs an operator decision.
- **Four registrations were tagged.** `account_sim`, `hedge_timing`,
  `exit_from_text` and `volume_signal` each carry the 2026-09-28 calibration
  clause. Each gained a `Resolved at build (2026-10-21)` line: pending rows
  leave the book, and the gate's bar is unchanged.
- **Recent dates keep their fast exits.** On a date inside the window, the
  rows that already hit a stop or target stay, while their still-open
  siblings leave. A study pooling recent dates leans toward quick exits until
  the re-price finishes those rows. `refuse_floor_forward`'s complete prefix
  guards against this; the default loader does not.
- **`ticker_class_regime` is a draft.** Its GR1 counts open rows and now sees
  only closed-window ones. Its author should say which it means before it is
  accepted.

Next: the item in [`next-steps.md` §2.11](next-steps.md#s2-11)
is marked resolved.

## 2026-10-21 — regime_confirm: a BEAR flip that persists is not a proven sell-off signal

**Waiting for a mech BEAR flip to hold, with other stress signs agreeing, did
not reliably pick out the flips that became a 10% fall.** Nothing ships.
`regime_watch` keeps printing, but on this result it should not call a flip
"confirmed". The thresholds in `lib/regime_watch.py` stay as they are.

Population: yfinance daily closes to 2026-10-20, no book export. Run
2026-10-21, git `a323040`. Record:
[`regime_confirm.md`](study-results/f1_selection/regime/regime_confirm.md).

A [real shift](glossary.md#real-shift) is a close at least 10% below the
decision close within 60 sessions. `RC0` acts on every
[flip](glossary.md#regime-flip). The two graded rules
([`regime_confirm`](arm-index.md#regime_confirm)) are below.

| Rule | Data | Events (clusters) | Real-shift rate | Every flip | Difference, 95% CI | Token |
|---|---|---|---|---|---|---|
| `RC1`: 3 BEAR sessions and 2 of 4 stress signs | QQQ + IWM | 35 (23) | 34.3% | 21.2% | +0.131 [−0.034, +0.327] | `NULL` |
| `RC-200`: 3 BEAR sessions and below the 200-day SMA | ^GSPC 1950–1992 | 22 (19) | 13.6% | 9.3% | +0.043 [−0.074, +0.182] | `NULL` |

- **Retrospective verdict: `RETRO-NULL`.** Both rules point the right way,
  but neither interval clears zero. Both rules passed their floors.
- **The clean holdout is the weak one.** Before 1993 the 200-day break added
  about four points to a 9% base rate.
- **No secondary survives BH.** The stress signs alone at the flip
  (`RC-C` on QQQ + IWM) printed `SUPPORTED` before correction, at BH q 0.12.
- **Forward: `STILL-OPEN`.** No flip after 2026-10-21 yet. The SPY flip of
  2026-10-19 lasted one session and is printed as a case only.

Next: nothing joins [`next-steps.md`](next-steps.md). A forward re-run needs
`-- --refresh`, because the close cache does not refetch on its own.

## 2026-10-17 — results moved out of pre-registrations

**Three run results left `trigger_entry`'s registration and are kept here.**
`study_review` hands the whole registration to two blind graders, so a
registration must not carry its own study's outcome. These lines were written
into the file with the first run's commit (`4fc17ac`, 2026-09-04). No other
record held them. Source:
[`trigger_entry.md`](pre-registrations/f1_selection/signal/trigger_entry.md),
"Wording corrections".

- Correction 2, G-SYNTH: "on v4 all 840 of them reproduce."
- Correction 4, pricing tiers: "On the v4 PRIMARY run every ARM T cell carries
  both tiers, so this makes no difference to any number recorded here".
- Correction 5, `first_cross` vs `trigger_met`: "0 disagreements on both eras."

## 2026-10-15 — spy_benchmark: the picks do not beat a SPY call spread, gross

**Across the same dates, the deployed picks did not beat a SPY ATM/+5% call
spread, gross of costs.** [`spy_benchmark`](arm-index.md#spy_benchmark)
prints `DOES-NOT-BEAT`. The point estimate is negative, but its CI spans zero,
so there is no evidence the picks add value over the index. It is not
`CONTRARY`. Nothing ships.

_Registration: [`spy_benchmark.md`](pre-registrations/f1_selection/benchmark/spy_benchmark.md),
accepted by default 2026-10-14, post hoc · era v4, exports of 2026-10-06,
post-P3 tiers · run 2026-10-15 at git `c8b1f4e`, working tree dirty · report:
`backtests/study_output/spy_benchmark-20261015.txt` · recorded in
[study-results](study-results/f1_selection/benchmark/spy_benchmark.md)._

**In production.** Nothing changes. The study is not a
[`programme_gate`](pre-registrations/f4_deployment/programme_gate.md) input;
its result is recorded beside the gate, which still reads `WAIT`.

**Evidence.** Gain is the picks' paired [meanR](glossary.md#meanr) minus the
SPY wrap's, with a date-clustered
[CI95](glossary.md#ci95-date-clustered-bootstrap). The headline is
`SB-UNIT = pick` on `DEBIT_PROD`, both sides gross.

| Cut | Pairs | Dates | Gain in R | CI95 | C0 | C1 | C2 | `CONTRARY` | Prints |
|---|---|---|---|---|---|---|---|---|---|
| Headline, `SB-UNIT = pick` | 381 | 190 | `-0.031` | `[-0.134, +0.074]` | Y | n | n | n | `DOES-NOT-BEAT` |
| `SB-UNIT = date` | 190 | 190 | `-0.030` | `[-0.144, +0.081]` | Y | n | n | n | `DOES-NOT-BEAT` |
| Declared secondary, own §5 row, per pick | 381 | 190 | `-0.019` | `[-0.134, +0.095]` | Y | n | n | n | `DOES-NOT-BEAT` |
| Declared secondary, own §5 row, per date | 190 | 190 | `-0.024` | `[-0.157, +0.099]` | Y | n | n | n | `DOES-NOT-BEAT` |

| Headline | meanR, picks | meanR, SPY | [PF](glossary.md#pf-profit-factor), picks | PF, SPY | Tier A gain | Tier B gain |
|---|---|---|---|---|---|---|
| `ARM SPY` | `+0.093` | `+0.124` | 1.28 | 1.53 | `-0.067` | `-0.015` |

**The census.** The population is 563 deployed picks on 243 dates. Every
v4 SPY leg is fetched: the run plans 0 more contracts.

| Object | Count |
|---|---|
| SPY wraps built | 388 |
| Dropped, `dte_ge_180` | 111 |
| Dropped, `expiry_not_listed_at_signal` | 59 |
| Dropped, `no_spot_at_signal` | 3 |
| Dropped, `no_listed_strike` or `dte_lt_7` | 1 each |
| Pairs after pricing | 381 on 190 dates |
| Floor 2 tier gap after pricing | 0.078 (max 0.1), pass |

**Build rulings, all made before any SPY outcome printed.** Each is in the
registration.

- **Ruling B.** A wrap whose expiry SPY had not yet listed on the signal date
  drops as `expiry_not_listed_at_signal`, instead of awaiting a fetch that
  cannot build it. It was amended the same day to need at least 5 cached
  contracts at that expiry, all first trading after the signal date.
- **The inherited no-spot drop.** When no cached SPY contract has a row on
  the signal date, the pair drops as `ARM M1`'s do. Three pairs drop this
  way, all on Sunday 2024-07-28.
- **The 613C fetch-planning fix.** The fetch planner now skips a strike the
  unlisted skip-list has evidence against. Without it, SPY 2025-04-25 613C
  was requested again on every run. It changes what is fetched, never what
  is built.

**What it means.**

- The picks did not show value over buying the index spread on the same
  dates. They did not clearly lose to it either.
- It is gross of costs, and post hoc: it was proposed after
  `cost_sensitivity`, `direction_hit` and the P1 read were seen.
- Ticker choice against a random name, `mechanical_benchmark`'s `ARM U`,
  stays untested.

**Next.** P2 is done in [`next-steps.md`](next-steps.md#plan-20261013). The
v3 SPY legs stay unfetched; they are optional.

---

## 2026-10-15 — mechanical_benchmark P1 corrected: the CONTRARY survives the spot fix and the tier port

**The P1 result stands: `ARM M1` still meets `CONTRARY` after two fixes.**
On the book's own tickers and expiries, the mechanical ATM/+5% call spread
still beats the picks, gross. Nothing ships, and `programme_gate` still reads
`WAIT`.

_Era v4 · exports of 2026-10-06 · run 2026-10-15 at git `c8b1f4e`, working
tree dirty · report:
`backtests/study_output/mechanical_benchmark-p1corr-20261015.txt`, pairs in
`mechanical_benchmark-pairs-p1corr-20261015.csv` · recorded in
[study-results](study-results/f1_selection/benchmark/mechanical_benchmark.md)._
The original P1 record, `mechanical_benchmark-p1-20261014.txt`, stays as
written; this correction sits beside it.

**In production.** Nothing changes.

**Why it was re-run.**

- **The spot fix.** `UniverseSpot` gave up after 20 probes. A pick whose
  expiry was not yet listed then dropped as `no_spot_at_signal`, even when
  other expiries priced that day. The
  [2026-10-15 build ruling](pre-registrations/f1_selection/benchmark/mechanical_benchmark.md)
  fixes the code; the rule is unchanged.
- **P3, the tier port.** It moved 34 v4 Tier B rows to VETO, out of the
  deployed set.
- About 30 more `ARM M1` contracts were fetched before the run.

**Evidence.** The run prints `SAME-TICKER READ — ARM U NOT BUILT`. Headline
basis: `DEBIT_PROD` on both sides, gross.
[meanR](glossary.md#meanr) and [CI95](glossary.md#ci95-date-clustered-bootstrap)
are as in the 2026-10-14 entry.

| Object | Run | Pairs | Dates | Gain in R | CI95 | C0 | C1 | C2 | `CONTRARY` |
|---|---|---|---|---|---|---|---|---|---|
| `ARM M1` (PRIMARY) | P1, 2026-10-14 | 405 | 208 | `-0.099` | `[-0.183, -0.023]` | Y | n | n | Y |
| `ARM M1` (PRIMARY) | corrected | 386 | 201 | `-0.101` | `[-0.187, -0.021]` | Y | n | n | Y |
| `ARM M2` (SECONDARY) | P1, 2026-10-14 | 345 | 191 | `-0.138` | `[-0.350, +0.032]` | Y | n | n | n |
| `ARM M2` (SECONDARY) | corrected | 329 | 184 | `-0.122` | `[-0.333, +0.048]` | Y | n | n | n |

| Corrected run | meanR, picks | meanR, mechanic | [PF](glossary.md#pf-profit-factor), picks | PF, mechanic | [LOO](glossary.md#loo--leave-one-date-out) share positive |
|---|---|---|---|---|---|
| `ARM M1` | `+0.130` | `+0.231` | 1.42 | 1.84 | 0.00 |
| `ARM M2` | `+0.164` | `+0.286` | 1.56 | 1.69 | 0.00 |

**The census change, by cause.** Each arm cell is built / awaiting /
dropped. The middle column came from a scratch toggle, not a recorded run.

| Object | P1, 2026-10-14 | After P3 only | Corrected run |
|---|---|---|---|
| Deployed picks | 582 on 249 dates | — | 563 on 243 dates |
| `ARM M1` | 405 / 0 / 177 | 386 / 0 / 177 | 386 / 0 / 177 |
| `ARM M2` | 345 / 0 / 237 | 329 / 0 / 234 | 329 / 0 / 234 |

- **P3 carries the whole change in pairs.**
- **The spot fix built nothing.** It brought 27 `ARM M1` slots back from
  `no_spot_at_signal`. Fifteen of them awaited the fetch and then dropped;
  the other 12 dropped at once.

| Drop reason | P1, 2026-10-14 | Corrected run |
|---|---|---|
| `ARM M1` `no_spot_at_signal` | 35 | 8 |
| `ARM M1` `no_listed_strike` | 17 | 44 |
| `ARM M2` `no_spot_at_signal` | 35 | 8 |
| `ARM M2` `no_target_delta` | 31 | 58 |

**Caveats.** These cuts print beside the headline and carry no verdict.

| Object | Gain in R | CI95 |
|---|---|---|
| `ARM M1`, Tier A only | `-0.002` | not printed |
| `ARM M1`, Tier B only | `-0.150` | not printed |
| `ARM M1` ex 2026 Feb–Apr | `-0.068` | `[-0.146, +0.004]` |
| `ARM M1` ex 2025 Mar–Apr | `-0.123` | `[-0.212, -0.044]` |
| `ARM M1`, each side under its own §5 row | `-0.078` | `[-0.173, +0.012]` |

The gap still sits almost entirely in Tier B, as on 2026-10-14.

**The `programme_gate` read, 2026-10-15: `WAIT`, "P1 negative, `dip_buy`
open".**

| Input | Reads | Why |
|---|---|---|
| `PG-M` | `CONTRARY` | `ARM M1` still meets the `CONTRARY` condition |
| `PG-D` | `STILL-OPEN` | `dip_buy` has no verdict of record |
| Gate | `WAIT` | Row 4, unchanged; the backstop is still 2027-10-13 |

Both `PG-ARMS` settings give the same read, since `ARM M1` is in each.

**Next.** In [`next-steps.md`](next-steps.md#plan-20261013), P1 and the gate
read cite this run. Item 15's fetch sizes now come from it.

---

## 2026-10-14 — SPY-only benchmark registered (post hoc)

**`spy_benchmark` is registered and built, and it prints `NOT BUILT —
AWAITING SCRAPE`.** It asks whether the deployed picks beat a SPY call spread
bought on the same dates. No outcome exists yet. Nothing ships.

_Registration: [`spy_benchmark.md`](pre-registrations/f1_selection/benchmark/spy_benchmark.md),
accepted by default 2026-10-14 · era v4, exports of 2026-10-06, post-P3 tiers
· report: `backtests/study_output/spy_benchmark-latest.txt`._

**In production.** Nothing changes. The study ships no rule, and it is not a
[`programme_gate`](pre-registrations/f4_deployment/programme_gate.md) input:
its result is recorded beside the gate.

**It is post hoc.** It was proposed after `cost_sensitivity`, `direction_hit`
and the P1 same-ticker read were seen. Those reads make a negative result more
likely, so it is weaker evidence than a planned test.

**The design.** [`ARM SPY`](arm-index.md#spy_benchmark) is
`mechanical_benchmark`'s `ARM M1` wrap moved onto SPY. The module imports that
study's strike choice, pricing, deployed set, seal and criteria.

| Choice | Default | Printed beside it |
|---|---|---|
| Expiry | the pick's own expiry, as `ARM M1` | — |
| `SB-UNIT`, a date with several picks | one row per pick; SPY repeats; date-clustered CI | one row per date: mean pick R against the top-ranked pick's SPY wrap |
| Exit profile | `DEBIT_PROD` on both sides, gross | each side under its own [§5](../docs/deployment-rules.md#s5) row |
| Era | v4 only | v3 with `--v3`, once its legs are fetched |

**The census.** It runs on an unpriced build, so no SPY wrap was priced.

| Object | Count |
|---|---|
| Deployed picks, post-P3 | 563 on 243 dates |
| Picks on SPY itself | 2 |
| SPY wraps built from the cache | 239 |
| Awaiting a fetch | 212 |
| Dropped by scope (DTE ≥ 180 or < 7) | 112 |
| SPY contracts to fetch, v4 | 149 |
| SPY contracts to fetch, v3, optional | 56 |

The fetch plan reads SPY's close from the mech-regime table when the stock
bars stop short. That only names strikes; the choice still reads SPY's cached
contracts.

**Next.** P2 in [`next-steps.md`](next-steps.md#plan-20261013) waits on the
operator's approval of the 149-contract v4 fetch.

---

## 2026-10-14 — mechanical_benchmark: the mechanical spread beats the picks on their own tickers

_Corrected 2026-10-15: the `CONTRARY` survives a re-run after the spot fix and P3 ([entry](#2026-10-15--mechanical_benchmark-p1-corrected-the-contrary-survives-the-spot-fix-and-the-tier-port))._

**On v4, a fixed ATM/+5% call spread on the same ticker and expiry beat the
picks, gross of costs.** [`mechanical_benchmark`](arm-index.md#mechanical_benchmark)'s
`ARM M1` meets the `CONTRARY` condition. The model's choice of structure,
strike, expiry and timing added no value on these tickers, and on `ARM M1` it
subtracted. Nothing ships.

_Era v4 · exports of 2026-10-06 · run 2026-10-14 at git `4536515` plus the
two uncommitted 2026-10-13 build rulings · report:
`backtests/study_output/mechanical_benchmark-p1-20261014.txt`, pairs in
`mechanical_benchmark-pairs-p1-20261014.csv` · recorded in
[study-results](study-results/f1_selection/benchmark/mechanical_benchmark.md)._

**In production.** Nothing changes. The study ships no rule under any outcome,
and [`programme_gate`](pre-registrations/f4_deployment/programme_gate.md)
reads `WAIT` (below).

**The operator reads this first.** The
[registration](pre-registrations/f1_selection/benchmark/mechanical_benchmark.md#verdicts-worded-now)
says a `CONTRARY` is surfaced to the operator before any further study runs.
The report prints the same line. P2 and the P5 suite re-run wait on that.

**Evidence.** The run prints `SAME-TICKER READ — ARM U NOT BUILT`. Headline
basis: `DEBIT_PROD` on both sides, gross. Gain is the picks' paired
[meanR](glossary.md#meanr) minus the counterpart's, with a date-clustered
[CI95](glossary.md#ci95-date-clustered-bootstrap).

| Object | Pairs | Dates | Gain in R | CI95 | C0 | C1 | C2 | `CONTRARY` |
|---|---|---|---|---|---|---|---|---|
| `mechanical_benchmark` `ARM M1` (PRIMARY) | 405 | 208 | `-0.099` | `[-0.183, -0.023]` | Y | n | n | Y |
| `mechanical_benchmark` `ARM M2` (SECONDARY) | 345 | 191 | `-0.138` | `[-0.350, +0.032]` | Y | n | n | n |

| Object | meanR, picks | meanR, mechanic | [PF](glossary.md#pf-profit-factor), picks | PF, mechanic | [LOO](glossary.md#loo--leave-one-date-out) share positive |
|---|---|---|---|---|---|
| `ARM M1` | `+0.143` | `+0.242` | 1.47 | 1.89 | 0.00 |
| `ARM M2` | `+0.176` | `+0.314` | 1.60 | 1.77 | 0.00 |

The census, printed beside the outcome as the registration requires. The
population is 582 deployed picks on 249 dates.

| Object | Built | Dropped | Largest drop reason | Floor 2 tier gap |
|---|---|---|---|---|
| `ARM M1` | 405 | 177 | `dte_ge_180` 111 | 0.019 (max 0.1), pass |
| `ARM M2` | 345 | 237 | `dte_ge_180` 111 | — |

**What it means.**

- **The wrap did not earn its keep.** On the book's own tickers and expiries,
  a rule with no model made more R per pair than the picks' own structures.
- **It is gross of costs.** Both sides are priced the same way from the
  stored marks. Costs are `cost_sensitivity`'s question.
- **It does not test ticker choice.** Both sides trade the ticker the model
  chose. `ARM U`, the random-ticker null, answers that, and it is not built.

**Caveats.** These cuts print beside the headline and carry no verdict.

| Object | Gain in R | CI95 |
|---|---|---|
| `ARM M1`, Tier A only | `-0.002` | not printed |
| `ARM M1`, Tier B only | `-0.143` | not printed |
| `ARM M1` ex 2026 Feb–Apr | `-0.068` | `[-0.145, +0.002]` |
| `ARM M1` ex 2025 Mar–Apr | `-0.120` | `[-0.205, -0.043]` |
| `ARM M1`, each side under its own §5 row | `-0.078` | `[-0.167, +0.008]` |

- The gap sits almost entirely in Tier B.
- Dropping the 2026 Feb–Apr window, or replaying each side under its own
  [§5](../docs/deployment-rules.md#s5) row, brings the CI's upper end to zero
  or just past it.

**What was not run.**

- v3 was not fetched (`--no-v3`), so v3 prints no outcome.
- `ARM M2L`, a declared secondary, still has pairs awaiting a fetch.
- `ARM U` is not built, so no study-level verdict prints.

**How the fetch ran.** About 64 batches over 2026-10-13/14, with one final
Drive backup pushed. The fetch order changed mid-fetch, under the 2026-10-13
ruling. That ruling changes the order only: a check on one cache built the
same pairs under both orders.

**After P3.** P3 moves 87 v4 rows to VETO. `mechanical_benchmark` reads the
book's tier directly, so its deployed set and its A/B tier-gain lines will
move on the next suite run. This record is the pre-P3 run.

**The `programme_gate` read, 2026-10-14: `WAIT`, "P1 negative, `dip_buy`
open".** The gate's registration says each read is recorded here and in the
P0 row of [next-steps](next-steps.md#plan-20261013).

| Input | Reads | Why |
|---|---|---|
| `PG-M` | `CONTRARY` | `ARM M1` meets the `CONTRARY` condition |
| `PG-D` | `STILL-OPEN` | [`dip_buy`](study-results/f1_selection/regime/dip_buy.md) has no verdict of record |
| Gate | `WAIT` | Row 4: `PG-M` is `CONTRARY` and `PG-D` is `STILL-OPEN` |

- **The parameters do not change it.** `PG-M` reads `CONTRARY` under both
  `PG-ARMS` settings, since `ARM M1` is in each. No arm clears C1, so
  `BEATS` is out either way. Both arms clear C0, so `PG-UNPOWERED` never
  applies.
- **Nothing retires until `dip_buy` grades.** That needs about seven months
  of forward dates after the seal lifts.
- **The backstop is 2027-10-13.** Under the default, a `dip_buy` still
  unread then counts as not positive, and row 4 becomes `RETIRE`. A
  prompt-version bump that freezes `dip_buy` brings it forward.

**Next.** In [`next-steps.md`](next-steps.md#plan-20261013), P1 is done and
item 15 is resolved for `ARM M1` and `ARM M2` on v4. The v3 and `ARM M2L`
legs and `ARM U` stay unfetched. P2 is the operator's choice.

---

## 2026-10-13 — programme_gate registered before any P1 result

**The kill rule is registered, and it reads `WAIT`.** If the picks do not beat
`mechanical_benchmark`'s same-ticker arms and `dip_buy` grades `NULL` or
`CONTRARY`, the flow-selection layer retires. If either read is positive, it
stays. Nothing ships.

_Registration: [`programme_gate.md`](pre-registrations/f4_deployment/programme_gate.md),
accepted by default 2026-10-13 · inputs: no `mechanical_benchmark` outcome
printed (`NOT BUILT — AWAITING SCRAPE`), `dip_buy` `STILL-OPEN`._

**In production.** Nothing changes. `RETIRE` would let the operator consider
a mechanical dip rule at $500, or stopping. Either needs its own registration.

**The gate.** The first matching row wins.

| `PG-M`, P1 on v4 | `PG-D`, `dip_buy` | Gate |
|---|---|---|
| `BEATS` | any | `KEEP` |
| any | `SUPPORTED` | `KEEP` |
| `CONTRARY` or `DOES NOT BEAT` | `NULL` or `CONTRARY` | `RETIRE` |
| `CONTRARY` or `DOES NOT BEAT` | `STILL-OPEN` | `WAIT` |
| `NOT READ` | not `SUPPORTED` | `WAIT` |

`BEATS` means `ARM M1` or `ARM M2` clears
[`mechanical_benchmark`](arm-index.md#mechanical_benchmark)'s C0, C1 and C2,
with neither arm `CONTRARY`.

**Contested choices, printed both ways.**

| Parameter | Default | Other setting |
|---|---|---|
| `PG-ARMS` | `M1 or M2`, as that study's `STRUCTURE-ONLY` reads it | `M1 only` |
| `PG-UNPOWERED` | An `UNDERPOWERED` or `NOT BUILT` P1 counts as not beating | It leaves P1 unread |
| `PG-BACKSTOP` | On 2027-10-13 a missing read counts as not positive | The operator decides |

P2, the ticker-choice read, is not an input. The operator's rule names only
the same-ticker arms.

**Unresolved.** P1 cannot print per-arm grades yet. The study waits for every
census floor, including `ARM U`'s, so a same-ticker fetch alone still prints
`NOT BUILT — AWAITING SCRAPE`. Default: P1 adds a same-ticker path, ruled in
`mechanical_benchmark.md` before its run.

**Next.** P0 is done. P1 waits on the operator's yes and that build change
([next-steps](next-steps.md#plan-20261013)).

---

## 2026-10-13 — external read: SOTA paper adds no evidence for this book

**The paper's 18.3% is one seed on one six-month window, with the checkpoint
picked on that window.** It does not show an LLM options edge, and nothing in
this repo changes on it. The Reddit title's "183%" misreads the paper's 18.32%.

_Source: Xie and Liu, "SOTA: Stock Options Trading Agents Guided by
Option-Implied Return Distributions", [arXiv:2610.10407](https://arxiv.org/abs/2610.10407),
7 October 2026. Read by Claude; not replicated._

**In production.** Nothing changes.

**What it claims.** A post-trained Qwen model picks a strategy family per name.
Deterministic resolvers pick the contracts. The test is nine large caps plus
SPY, 2025-03-03 to 2025-08-29.

| Policy | Total return | Sharpe | Max drawdown |
|---|---|---|---|
| SOTA, no news | +18.32% | 1.60 | 8.96% |
| SOTA, with news | −2.72% | −0.16 | 31.69% |
| Best rule baseline | −5.22% | −13.46 | 5.22% |

**Why it is weak evidence.**

- **The checkpoint was chosen on the test window.** Every saved checkpoint was
  scored on it and step 20 was reported. That is a pick from many configs with
  no PBO read ([`pbo_ledger`](arm-index.md#pbo_ledger)).
- **One seed, no confidence intervals.** The trade count is not reported.
- **No buy-and-hold benchmark.** The window runs from the April 2025 sell-off
  through the rebound, when long SPY also gained.
- **The baselines lose 28–55%.** Beating them says little.
- **Training-cutoff leakage is not addressed.**

**Where it agrees with this repo.**

- **News hurt** (−2.72%). This repo's text studies also read `NULL` on
  news-driven text.
- **Fills at mid plus $0.65 a contract**, the same cost basis as the
  backtest.
- **A related benchmark, LiveOption**
  ([arXiv:2609.33470](https://arxiv.org/abs/2609.33470)), found LLM earnings
  bets negative for all six models. Small 0DTE gains vanished once the
  half-spread was charged. Both match `earnings_vol` and `cost_sensitivity`.

**Next.** None from the paper. The programme plan is
[next-steps](next-steps.md#plan-20261013).

---

## 2026-10-13 — earnings_vol: neither earnings structure pays, and the calendar's edge is the spread

**`earnings_vol` prints `NULL` on both arms.** A long ATM straddle and a long
ATM double calendar held across 25 names' earnings reports earn no return
clear of zero over 11 seasons. Neither moves with the book. Nothing ships.

_Registration: [`earnings_vol.md`](pre-registrations/f3_structure/earnings_vol.md),
accepted by default 2026-10-12 and saved before the fetch and the first run ·
era v4, exports 2026-10-06 · 272 in-sample events, 2024-Q1 → 2026-Q3 ·
report: `backtests/study_output/earnings_vol-latest.txt` · recorded in
[study-results](study-results/f3_structure/earnings_vol.md)._

**In production.** Nothing changes. Earnings vol is not a non-directional
sleeve for this book at mid fills, and it loses at natural fills.

### The graded arms

Return is P&L over the entry debit. CIs are clustered by earnings season (11
clusters). [MFE and MAE](glossary.md#mfe) are shares of the debit.

| Object | n | Mean | CI95 | Halves | MFE / MAE | Token |
|---|---|---|---|---|---|---|
| [`earnings_vol` ARM S](arm-index.md#earnings_vol), straddle, mid | 271 | +0.019 | [−0.085, +0.123] | +0.064 / −0.036 | +0.315 / −0.269 | `NULL` |
| `earnings_vol` ARM K, [double calendar](glossary.md#double-calendar), mid | 161 | +0.073 | [−0.024, +0.170] | +0.079 / +0.067 | +0.361 / −0.296 | `NULL` |
| ARM K, natural fill | 161 | −0.133 | [−0.225, −0.039] | −0.154 / −0.108 | +0.199 / −0.412 | `CONTRARY`, secondary |
| ARM S, run-up exit (close before the report) | 272 | +0.020 | [−0.019, +0.068] | +0.033 / +0.004 | +0.107 / −0.085 | `NULL`, secondary |

- **The calendar fails one clause.** Both halves are positive and the gate
  passes; only the CI reaches below zero. That is the closest any vol cell in
  this repo has come, and it is still not a result.
- **Its edge is the bid-ask spread.** The same trades lose 13% of debit when
  bought at the ask and sold at the bid. Four legs cross the spread twice.
- **The straddle is flat.** It wins 39% of the time, and the report's move
  pays for the run-up's decay and no more.

### The gate

| Object | Correlation with the book's daily MTM | CI95 | Token |
|---|---|---|---|
| `earnings_vol` G1, ARM S | −0.066 | [−0.159, +0.035] | PASS |
| `earnings_vol` G1, ARM K | −0.018 | [−0.117, +0.092] | PASS |

Unlike `vol_sleeve`, a calendar fixed by earnings dates does not re-wrap the
book.

**Caveats.**

- **85 calendars could not be built.** The back weekly was not yet quoted on
  the entry day, so ARM K keeps 161 of 272 events. The survivors lean towards
  events whose back expiry was a monthly.
- **The fetch ran twice.** The first plan took strikes from split-adjusted
  closes (NFLX, NVDA, AVGO) and from a strike grid guessed from a sparse cache.
  The planner was fixed and a second fetch probed the true nearest strike. No
  outcome was read in between; the ruling is folded into the registration.
- **The names are mega-caps.** Gao, Xing & Zhang (2018) found the straddle
  premium in small, volatile, illiquid firms, so this null does not contradict
  them.
- **The motivating hint was post hoc.** `vol_sleeve`'s calendar × earnings cut
  (archive/12) is not confirmed: the registered calendar here is `NULL`.
- **[PBO](arm-index.md#pbo_ledger) is 0.262** over the 8 printed configs. The
  graded calendar cell is the in-sample best in 77% of splits, which says it
  was the strongest cell, not that it is real.

**Next.** No new queue item. [`next-steps.md`](next-steps.md) item 10 closes.
The two non-directional ideas this session tested are both `NULL`.

---

## 2026-10-12 — index_vrp: a short SPY condor shares the book's bad months, not its bad days

**`index_vrp` prints `NO-TAIL-LINK`.** A monthly short SPY iron condor lost
money in two of the three stress windows where the book lost. On the book's
worst 5% of days it neither lost nor gained. Nothing ships.

_Registration: [`index_vrp.md`](pre-registrations/f3_structure/index_vrp.md),
accepted by default 2026-10-12 and saved before the first run · era v4,
exports 2026-10-06 · deployed book: 253 positions, 707 sessions · sleeve:
55 monthly cycles per underlying from 2022-03, real cached quotes · report:
`backtests/study_output/index_vrp-latest.txt` · recorded in
[study-results](study-results/f3_structure/index_vrp.md)._

**In production.** Nothing changes. Short index vol is still rejected as a
standalone trade (agent-trading 0047), and this study gives no reason to add
it as a sleeve.

### The premium

Neither underlying shows a [variance risk premium](glossary.md#vrp) in this
sample once the straddle is settled at expiry.

| Underlying | Premium, share of spot | CI95 | IV − RV, vol points | Token |
|---|---|---|---|---|
| SPY | +0.0019 | [−0.0057, +0.0086] | +1.15 [−0.85, +2.69] | `NO-PREMIUM` |
| GLD | −0.0053 | [−0.0140, +0.0030] | +0.16 | `NO-PREMIUM` |

SPY's high-VIX tercile is the one cell with a clear premium in vol form,
+3.41 points, CI95 [+1.56, +5.33]. It holds 14 cycles and is a descriptive
cut.

### The overlap, graded

Graded object: [`index_vrp` ARM C](arm-index.md#index_vrp), the SPY condor at
0.16 delta, mid fill, against the deployed v4 book.

| Measure | Book | Sleeve |
|---|---|---|
| W2 Aug 2024, window P&L | −$490 | +$266 |
| W3 Mar–Apr 2025 | −$1,556 | −$2,082 |
| W4 Feb–Apr 2026 | −$3,045 | −$959 |
| T1, sleeve $ per session on the book's worst 5% | — | −7.66 [−54.90, +44.31] |
| T3, daily correlation, all common sessions | — | −0.038 [−0.198, +0.130] |
| T4, realized max drawdown on $25,000 | 58.2% | 55.7% combined |

- **Same months, different days.** The condor lost in March–April 2025 and
  February–April 2026, which meets the window clause. It lost at expiry
  settlement, after the move, not on the days the book fell. So T1 straddles
  zero and the verdict is `NO-TAIL-LINK`, not `LOSES-TOGETHER`.
- **Every secondary prints the same token**: GLD, the natural fill, the 0.30
  delta, the stored book, the unregistered 2.50 cap cell, and v3.
- **2022 has no book.** The sleeve made +$484 there. A beta proxy fitted on
  later data puts the book at −$6,743 in 2022; it is descriptive only.

**Caveats.**

- **T5 compares two different sessions.** The [O2](arm-index.md#ruin_bound)
  overlay picks each book's own peak-reserve session: 2024-01-30 for the book
  alone (57.1% of equity), 2026-06-05 with the sleeve (50.8%). The lower
  combined figure reflects higher equity before the shock, not
  diversification. A defined-risk condor can only add its max loss to an O2
  shock.
- **The SPY condor is roughly flat**: +$337 over 55 cycles at mid. Its five
  worst cycles expired in 2022-05, 2023-11, 2025-04, 2025-05 and 2026-04.
- **221 junk-quote marks** on the SPY condor fell back to `Latest`, mostly on
  the far wings. The build rulings are folded into the registration.

**Next.** No new queue item. Short index vol is closed for this book: it
neither pays on these quotes nor hedges the book's worst days.

---

## 2026-10-12 — direction_hit: nothing known at entry predicts the underlying's direction

**`direction_hit` prints `NULL`: a walk-forward model on 17 entry-time
features ranks the plays that hit no better than chance on v4.** Its
probabilities are worse than the base rate in every population. Nothing
ships.

_Registration: [`direction_hit.md`](pre-registrations/f1_selection/signal/direction_hit.md),
accepted by default 2026-10-12 and saved before the first run · era v4,
exports 2026-10-06, 1,528 directional rows with a hit · v3 beside it, 782
rows · report: `backtests/study_output/direction_hit-latest.txt` · recorded
in [study-results](study-results/f1_selection/signal/direction_hit.md)._

**In production.** Nothing changes. The [direction hit](glossary.md#direction-hit)
decides most of R, and nothing the card can see at entry predicts it.

### The base rate

| Population | v4 hit | v3 hit |
|---|---|---|
| Bull plays | 58.7% | 62.7% |
| Bear plays | 42.5% | 36.5% |
| Tier A/B | 58.5% | 67.1% |
| All directional | 52.4% | 50.4% |

Bear plays lose the direction bet more often than they win it, in both eras.

### The graded model

| Object | Era | Out-of-sample rows, dates | [AUC](glossary.md#auc), CI95 | [Brier skill](glossary.md#brier-skill), CI95 |
|---|---|---|---|---|
| [`direction_hit`](arm-index.md#direction_hit) model, all directional | v4 | 1,140, 202 | 0.525 [0.484, 0.563] | −0.077 [−0.123, −0.032] |
| Same | v3 | 584, 90 | 0.564 [0.514, 0.614] | −0.135 [−0.212, −0.054] |
| Tier A/B, secondary | v4 | 453, 166 | 0.519 [0.468, 0.576] | −0.128 [−0.203, −0.051] |
| Tier A/B, secondary | v3 | 169, 55 | 0.486 [0.389, 0.585] | −0.182 [−0.345, −0.006] |

- **Worse than knowing nothing.** Every Brier skill is below zero. Predicting
  the training months' own hit rate beats the model.
- **No feature group helps.** [PBO](arm-index.md#pbo_ledger) is 0.085 on v4,
  because the intercept-only model is the in-sample best in 72% of splits.
- **The alternatives agree.** Stronger shrinkage (C = 0.1) gives AUC 0.524.
  A fixed 10-session hit, which no exit touches, gives 0.522.
- **v3 alone clears 0.5**, but its Brier skill is negative too.

### The univariate screen

Two of the 17 features pass [BH](glossary.md#bh) on v4. Neither is a usable
signal.

| Feature | v4 lift | v4 BH q | v3 lift, raw p |
|---|---|---|---|
| Index ETF (`F14`), hit where 1 minus where 0 | −0.099 | 0.038 | −0.070, 0.210 |
| Sector (`F17`), between-level variance | +0.007 | 0.008 | +0.011, 0.001 |
| Own 20-day return, aligned (`F15`, reversal) | +0.030 | 0.963 | −0.131, 0.002 |
| Own close over its 50-day SMA (`F16`, trend) | −0.014 | 0.963 | −0.169, 0.000 |
| cpir, aligned (`F9`) | 0.000 | 1.000 | +0.004, 0.967 |
| iv_spread, aligned (`F10`) | +0.007 | 0.963 | −0.051, 0.292 |

- **Sector is composition.** Metals plays hit 73% on v4 and rates plays 37%.
  That is which underlyings trended in this sample, not a forward signal.
- **Index ETFs hit less often**, 44% against 54%.
  [`ticker_class`](arm-index.md#ticker_class) found them no different on R
  with direction held fixed.
- **The literature features are flat on v4.** Short-term reversal shows on
  v3 only, and on v3 the trend feature points the wrong way for momentum.

**Caveats.**

- **Bars end in August 2026.** The stock-bar cache was last refreshed then, so
  265 v4 directional rows (120 of them Tier A/B) have no bar at the signal or
  the exit. Most are June to September 2026 signal dates.
- **The feature list was drawn up after** the exploratory read had tested 26
  features against R. The registration discloses it.
- **The papers measured a broad universe.** They sorted many stocks by each
  signal; this book holds only the analysis's own picks. A null here does not
  contradict them.

**Next.** A new [next-steps](next-steps.md#pick-up) item: refresh the stock-bar
cache and re-run. The forward read is `STILL-OPEN` behind the seal.

---

## 2026-10-12 — regime_map: Tier A on falling-market dates is the one cell both eras agree on

**Tier A makes money when SPY is below its 50-day SMA, and on mechanical
BEAR dates, in both eras. No other tier and market condition replicates
after correction.** These are the dates `dip_buy` waits on, seen from the
map. Nothing ships.

_Registration: [`regime_map.md`](pre-registrations/f1_selection/regime/regime_map.md),
accepted by default 2026-10-12 and saved before the first run · era v4,
exports 2026-10-06, 1,850 rows over 280 dates, R net of cost · v3 beside it,
795 rows, R gross · report: `backtests/study_output/regime_map-latest.txt` ·
recorded in [study-results](study-results/f1_selection/regime/regime_map.md)._

**In production.** Nothing changes. The map describes; a rule taken from a
cell needs its own registration, a PBO read and forward dates.

### What was graded

Each tier (A, B, C, VETO) against each of six market labels, one at a time:
76 cells per era. Each cell is graded against zero, with [BH](glossary.md#bh)
across the era's whole map. A cell needs 30 positions and 10 dates, or it
prints `THIN` ([`regime_map`](arm-index.md#regime_map)).

### The two replicated cells

| Object | Era | Positions, dates | [meanR](glossary.md#meanr), CI95 | BH q | [MFE](glossary.md#mfe) / MAE | [Capture](glossary.md#capture) |
|---|---|---|---|---|---|---|
| `A x RM-MDIR=BEAR` | v4 net | 59, 30 | +0.367 [+0.167, +0.565] | 0.010 | +1.17 / −0.38 | 0.33 |
| Same | v3 gross | 117, 46 | +0.393 [+0.205, +0.588] | 0.000 | +1.26 / −0.51 | 0.34 |
| `A x RM-SMA=below` | v4 net | 65, 35 | +0.332 [+0.133, +0.522] | 0.019 | +1.12 / −0.40 | 0.33 |
| Same | v3 gross | 119, 47 | +0.383 [+0.194, +0.582] | 0.000 | +1.26 / −0.51 | 0.33 |
| `A x RM-SMA=above`, for contrast | v4 net | 148, 60 | +0.026 [−0.112, +0.167] | 0.737 | +0.83 / −0.57 | 0.12 |

- **One finding, not two.** A mechanical BEAR date is always below the SMA.
- **The gain is in the path.** On dip dates Tier A runs further in its favour,
  falls less against it, and keeps a third of its peak instead of an eighth.
- **Part of it is the sell-off windows.** Without them both v4 cells stay
  positive on the raw CI but lose BH (q 0.160 and 0.192).

### The rest of the map

| Graded cells | `POSITIVE` | `NEGATIVE` | `NULL` | `THIN` |
|---|---|---|---|---|
| v4, net | 2 | 1 | 45 | 28 |
| v3, gross | 17 | 8 | 19 | 32 |

- **v4's one negative cell** is Tier C on the model's C-VOL dates, −0.261
  [−0.371, −0.142]. v3 reads `NULL` there.
- **Tier B in a calm bull tape is positive before correction.** On the raw
  CI, eight cells replicate. Five are Tier B, mostly on calm or rising-market
  labels, for example SPY above its SMA: +0.117 [+0.010, +0.218] on v4.
- **v3 grades far more cells.** It is mostly sell-off dates, where tiers
  separate sharply.

**Caveats.**

- **Not blind.** The exploratory read printed Tier A by these labels before
  the registration was written; the registration says so.
- **Tier C mixes in bear debits**, which the deploy card treats as hedge-only
  ([§1.4](../docs/deployment-rules.md#s1)).
- [`dip_buy DB1`](arm-index.md#dip_buy) stays the graded dip-minus-above
  contrast. This map grades each half against zero only.

**Next.** The two cells are read forward once the seal lifts. They join
[next-steps item 6](next-steps.md#pick-up).

---

## 2026-10-12 — adaptive_ladder: the walk-forward adapter beats M0 once, on a menu built in hindsight

**The adapter prints `ADAPTS` on the in-sample v4 dates, but the whole gain
is one switch to a rule the exploratory read had already picked.** In April
2026 it left the shipped ladder for bull_call_spreads ranked lowest score
first, and stayed there. Before that it held the shipped ladder. On v3 it
never switches. Nothing ships.

_Registration: [`adaptive_ladder.md`](pre-registrations/f1_selection/regime/adaptive_ladder.md),
accepted by default 2026-10-12 · era v4, exports 2026-10-06, 1,753 non-veto
rows over 278 dates, 224 graded · v3 beside it, R gross of cost · report:
`backtests/study_output/adaptive_ladder-latest.txt` · recorded in
[study-results](study-results/f1_selection/regime/adaptive_ladder.md)._

**In production.** Nothing changes. A forward `ADAPTS` would at most let the
operator consider a deployment-rules change.

### What was graded

A fixed procedure, not a rule. Six selection rules form the menu
([`adaptive_ladder M0–M5`](arm-index.md#adaptive_ladder)). On the first
signal date of each month the adapter scores every rule on positions whose
exit came before that date, over the last 120 days. It switches when a
challenger with 20 positions has a lower bound above the incumbent's mean.
The graded figure is adapter minus `M0` in [slot R](glossary.md#slot-r) per
date, with a month-block [CI](glossary.md#ci).

### Walk-forward, v4, in-sample dates

| Book | Positions | [meanR](glossary.md#meanr) | Slot R per date | Total R | Max drawdown, R |
|---|---|---|---|---|---|
| Adapter, default | 424 | +0.075 | +0.048 | +32.0 | 23.6 |
| `M0`, shipped | 441 | +0.029 | +0.019 | +12.7 | 39.0 |
| `M1`, ascending | 441 | +0.096 | +0.063 | +42.5 | 24.7 |
| `M5`, oracle in hindsight | 385 | +0.137 | +0.078 | +52.7 | 14.1 |

| Comparison | Adapter − `M0` per date, CI95 | Verdict |
|---|---|---|
| All 224 graded dates | +0.029 [+0.001, +0.064] | **`ADAPTS`** |
| Ex Mar–Apr 2025 and Feb–Apr 2026 | +0.034 [+0.001, +0.074] | `ADAPTS`, not graded |
| 2024 and 2025 | 0.000 | No switch |
| 2026 | +0.064 [+0.007, +0.131] | `ADAPTS`, not graded |

- **One switch.** `M0` to `M5` on 2026-04-02; `M0` held 64% of graded dates
  and `M5` 36%.
- **The lower bound sits at the floor.** The CI clears zero by 0.001.
- **The grid agrees in sign, not in kind.** Of 12 configurations, 10 beat
  `M0` on the point estimate and 4 clear zero. The plain-mean margin switches
  11 to 30 times and clears zero in none.
- **[PBO](arm-index.md#pbo_ledger) 0.16** over the 18 books. `M5` is the
  in-sample best in half the splits.

### Why this is weaker than it reads

- **The menu is hindsight.** `M1`, `M3`, `M4` and `M5` came from reading these
  dates on the same day. Static `M5` and `M1` beat `M0` in-sample by more than
  the adapter does.
- **v3 does not replicate.** The default never leaves `M0`, which is also the
  hindsight best there. `M5` loses to `M0` on v3, −0.052 [−0.087, −0.013].
- **The gain is one regime.** It is the 2026 tape, after a sell-off, on a
  rule that bets on bull_call_spreads.

**Forward.** `STILL-OPEN`: 0 of 30 forward dates, behind the seal. The rule
held entering the forward window is `M5`.

**Next.** `adaptive_ladder` joins the forward reads waiting on dates in
[next-steps item 6](next-steps.md#pick-up).

---

## 2026-10-12 — exploratory read: v4 is a bull tape, and the vetoes are its only ladder edge

**On v4 the Tier A/B ladder is a bet on direction, and the vetoes carry
its whole lead over random picks.** A pick's R mostly tracks its underlying's
move over the hold. Among non-vetoed plays the ladder sits at the median of
random top-3 books, and below every random bull_call_spread book. This read is
exploratory and unregistered. Nothing ships.

_Era v4, exports 2026-10-06: 1,850 priced rows over 280 dates. Era v3 for
contrast: 795 rows over 118 dates. Tiers from `mapping.ladder_tier` · scripts
and outputs in the session scratchpad, not the repo · raw CIs, no
multiplicity control unless stated._

**In production.** Nothing changes. One lead was registered and run; see the
[next entry](#2026-10-12--dip_buy-accepted-by-default-forward-still-open-behind-the-seal).

### The tape

v4 is mostly a rising market, and v3 is mostly a falling one. Any v3-to-v4
comparison is partly a comparison of tapes.

| Measure | v4 | v3 |
|---|---|---|
| Signal dates with SPY above its 50-day SMA | 78% | 33% |
| Signal dates inside the Mar–Apr 2025 or Feb–Apr 2026 sell-offs | 12.5% | 53% |
| Tier A+B picks whose underlying rose over the hold | 52% | 67% |

### The ladder is a direction bet

Tier A+B [R](glossary.md#r), regressed on the underlying's own return over
the hold.

| Era | Slope | R² | R at zero move, [CI95](glossary.md#ci) | Positions |
|---|---|---|---|---|
| v4 | +4.68 | 0.47 | +0.005 [−0.057, +0.059] | 741 |
| v3 | +4.66 | 0.43 | +0.127 [+0.035, +0.238] | 294 |

The slope is the same in both eras. What v4 lacks is the intercept: with no
move, a v4 pick earns nothing. It also lacks the rising underlyings, so the
v3-to-v4 gap is mostly the tape.

### The vetoes carry the v4 edge

Each null draws three random plays per date from a pool, 10,000 times. The
table gives the percentile of the ladder's A/B-only top-3
[meanR](glossary.md#meanr) in that null.

| Null pool | v4, all dates | v4, ex sell-offs | v3, all dates | v3, ex sell-offs |
|---|---|---|---|---|
| Every play | 99.7 | 99.7 | 100.0 | 100.0 |
| Every non-veto play | 55.3 | 42.3 | 97.2 | 48.6 |
| Every bull_call_spread | 0.0 | 0.7 | 95.6 | 63.1 |

- **The vetoes are the edge.** Against every play the ladder wins in both
  eras. Against non-vetoed plays it wins only on v3, and only inside the
  sell-off windows.
- **The tie-break picks worse spreads on v4.** Within tier the ladder
  ranks by `score_total`, highest first. Ranking lowest first lifts the v4
  ladder's meanR from +0.084 to +0.131, per the `dip_buy` run below.

### What survives the screen

A permutation screen tested 26 features, shuffled within date, with BH
correction. Only one survives on v4: bull_call_spread against every other
structure, q 0.013.

| Feature | v4 difference in meanR | v3 difference in meanR |
|---|---|---|
| bull_call_spread vs the rest | +0.189 | +0.424 |

A [PBO](arm-index.md#pbo_ledger) read over 28 single-feature selection rules
puts the selection's overfitting odds at 0.48 on v4 and 0.33 on v3. One rule
ranked high in both: Tier A/B on a [dip date](glossary.md#dip-date). It is
the most frequent in-sample winner on v3 and second on v4.

| Tier A, v4 | meanR, CI95 |
|---|---|
| Dip dates | +0.332 [+0.14, +0.52] |
| Above dates | +0.026 [−0.11, +0.17] |

### Three hypotheses, one registered

| Hypothesis | Where it went |
|---|---|
| Tier A/B do better on dip dates | Registered as [`dip_buy`](pre-registrations/f1_selection/regime/dip_buy.md), forward only |
| A positive cpir helps | A printed split inside `dip_buy`, never graded |
| A lower `score_total` helps within bull_call_spread | A printed tie-break inside `dip_buy`, never graded |

**Caveats.** Every lead here was found by looking at these dates, so none can
be confirmed on them. The sell-off windows were chosen from the outcomes. The
v4 book holds 195 positions marked open at the data end. The PBO rule medians
used the full sample, a mild leak.

**Next.** `dip_buy` waits on forward dates and the seal. No queue item closes.

---

## 2026-10-12 — dip_buy accepted by default: forward STILL-OPEN behind the seal

**`dip_buy` prints `STILL-OPEN`: the forward dates it grades are sealed, and
neither arm has a date yet.** It grades one population, v4 signal dates from
the seal's start. The in-sample eras are printed as post hoc context only.
Nothing ships.

_Registration: [`dip_buy.md`](pre-registrations/f1_selection/regime/dip_buy.md),
accepted by default 2026-10-12 · era v4, exports 2026-10-06, v3 beside it ·
report: `backtests/study_output/dip_buy-latest.txt` · recorded in
[study-results](study-results/f1_selection/regime/dip_buy.md)._

**In production.** Nothing changes. A forward `SUPPORTED` would at most let
the operator consider a deployment-rules change.

### The registration's choices

| Choice | Default |
|---|---|
| Dip label | `lib/mech_regime.py` `below_sma`: SPY close strictly below its 50-day SMA, as of the signal date |
| Why not `mech_cell` | It does not encode this flag; its BEAR also needs a falling 20-day return |
| Graded statistic | Tier A+B meanR, dip minus above, date-clustered CI |
| Forward population | v4 signal dates on or after `era.SEAL_START`, readable once the seal lifts |
| Floor per arm | 30 signal dates and 60 positions |
| Verdict of record | The first run printing anything but `STILL-OPEN` |
| Printed both ways, not graded | `score_total` tie-break order; cpir split at 0.92 |

The study is not a named sealed reader, because the
[seal](pre-registrations/f4_deployment/holdout_seal.md)'s list closed on
2026-10-09. Its forward read waits for the unseal.

**Expected wait.** SPY was below its SMA on 21% of v4 signal dates. At that
rate the dip arm needs about 142 forward signal dates, roughly seven months.
In a steady rally it may never fill.

### In-sample context, post hoc

| Object | v4 | v3 |
|---|---|---|
| [`dip_buy DB1`](arm-index.md#dip_buy), dip minus above | +0.096 [−0.164, +0.322] | +0.199 [−0.050, +0.428] |
| Dip arm meanR | +0.192, 112 positions, 46 dates | +0.450, 161 positions, 53 dates |
| Above arm meanR | +0.096, 630 positions, 197 dates | +0.252, 131 positions, 35 dates |
| Ladder top-3 vs random bull_call_spreads, descending tie-break | 0.0th percentile | 94.8th percentile |
| The same, ascending tie-break | 12.9th percentile | 85.9th percentile |

The pooled sign agrees across eras, and neither interval clears zero. Tier A
and Tier B split in opposite directions in the two eras, so the graded object
is the pooled contrast.

**Also changed.** `lib/mech_regime.py` gained the `spy_below_sma` field,
the same SMA as before with no threshold moved. Four studies now read the seal
date from `lib/era.py` instead of a copy, closing
[next-steps item 4](next-steps.md#pick-up).

**Next.** `dip_buy` joins the forward reads waiting on dates in
[next-steps item 6](next-steps.md#pick-up).

---

## 2026-10-09 — parked drafts accepted by default and run

**Seven parked items were accepted on their drafters' defaults, built and run.
Nothing ships.** Two studies find a loss that is cut but not removed. One gives
the operator a sizing reading. Four wait: on the holdout seal, on forward
dates, or on a fetch.

**In production.** Nothing changes. Every default can be revisited by the
operator; a revisit after a result is a new registration, never an edit.

| Item | What it asks | As printed | Entry |
|---|---|---|---|
| `holdout_seal` (N5) | Hide outcomes on new dates until 40 have priced | `priced sealed dates: 0 of 40` | [entry](#2026-10-09--holdout_seal-accepted-by-default-sealed-from-2026-09-23) |
| `narrow_to_fit` floor (item 14) | Refuse a narrowed debit under 20% of its width | `NULL` at $1,000, `NARROW-FEASIBLE` at $500, as before | [entry](#2026-10-09--narrow_to_fit-a-20-net-floor-changes-no-verdict) |
| `index_bear_hedge` (item 13) | Do index bears pay as crash insurance? | `STILL-OPEN`, forward only | [entry](#2026-10-09--index_bear_hedge-forward-still-open-in-sample-the-insurance-cost-more-than-it-paid) |
| `bear_fast_exit` (§2.4) | Does a fast bear-debit exit pay after costs? | `BLEED-CUT (C7 PENDING)` | [entry](#2026-10-09--bear_fast_exit--a-session-1-exit-cuts-the-bear-debit-loss-and-still-loses) |
| `ruin_bound` (item 5) | Which cap cell keeps ruin under a fixed bound? | `SAFEST ELIGIBLE CELL: N250-F2 G-none` at $500 | [entry](#2026-10-09--ruin_bound--refusing-the-unaffordable-pick-keeps-ruin-away-nothing-passes-at-1000) |
| `cost_sensitivity` (N1) | At what cost does the Tier A/B edge vanish? | `VANISHES` on both tiers | [entry](#2026-10-09--cost-sensitivity-n1-both-tiers-vanish-and-there-was-no-gross-edge-to-lose) |
| `mechanical_benchmark` (N2) | Do the picks beat a mechanical call spread? | `NOT BUILT — AWAITING SCRAPE` | [entry](#2026-10-09--mechanical_benchmark--not-built-yet-awaiting-a-scrape-nothing-ships) |

What the operator should look at:

- **`ruin_bound` at $1,000.** No cell meets the bounds at the operator's own
  sizing. At $500 only the F2 cells (refuse the unaffordable pick) pass.
- **`cost_sensitivity`.** Neither tier clears zero even before costs on v4.
- **`mechanical_benchmark`.** Its verdict waits on a fetch only the operator
  can approve ([next-steps item 15](next-steps.md#pick-up)).

---

## 2026-10-09 — `holdout_seal` accepted by default: sealed from 2026-09-23

**The holdout seal now starts on 2026-09-23, not 2026-08-11.** Research code
reads no outcome on a signal date from 2026-09-23 on until 40 of those dates
have priced and the one registered Tier A/B read has run. Nothing ships.

_Registration: [`holdout_seal.md`](pre-registrations/f4_deployment/holdout_seal.md),
accepted by default 2026-10-09 on the drafter's defaults · census of the
2026-10-06 exports, counts only._

**In production.** Nothing changes. The journal and the deploy card are
outside the seal.

**Why the start moved.** Runs from 2026-09-28 to 2026-10-07 printed outcomes
on 2026-08-11 → 2026-09-22: `account_sim`'s episode E9, the 2026 column,
`narrow_to_fit` and `pbo_ledger`. No export has held a priced row on
2026-09-23 or later.

| Export (2026-10-06) | Rows on sealed dates | Priced sealed dates |
|---|---|---|
| `BacktestResults` | 0 | 0 |
| `BacktestProxy` | 10, on one date | 0 |
| `AnalysisClaude` | 105, on 9 dates | — |

**Who may read sealed dates.**

| Reader | From | What |
|---|---|---|
| The unseal read | 2026-09-23 | Tier A and B meanR and PF on the deployed set, once |
| `refuse_floor_forward` | 2026-10-08 | Its registered cells |
| `ticker_class` | 2026-10-08 | Forward P1 only |
| `narrow_to_fit` | 2026-10-08 | Its forward sign read, not yet built |
| `v4_bridge` | any date | Its five composition tests, no outcome |

The list is closed: a forward read accepted from today waits for the unseal.
Only 2026-09-23 → 2026-10-07 stays unread by everyone. From 2026-10-08 the
named readers print pooled cells, never the tier split.

**The guard.** `lib/era.py` holds the dates and the reader list. `load_book`
withholds sealed records by default and prints a `SEAL:` line. The four
studies that open the exports themselves filter with `drop_sealed`.
`tests/test_holdout_seal.py` fails on any study that resolves an export path
without the filter. `make seal-census` prints the unseal count.

**Next.** [§2.2](next-steps.md#s2-2) can run `v4_bridge` now on
2026-08-11 → 2026-09-22. [§2.6](next-steps.md#s2-6)'s triggers read unsealed
dates only until the unseal.

---

## 2026-10-09 — narrow_to_fit: a 20% net floor changes no verdict

**A floor on a narrowed spread's net debit changes no `narrow_to_fit`
verdict.** The registered no-floor rule stays the headline in both
registrations. The floored line prints beside it as a declared secondary.

**In production.** Nothing ships. The report closes "Nothing in this report
is a shippable rule."

_Era v4, exports `2026-10-06 23:39`, a 1,850-row book. Reports:
`backtests/study_output/narrow_to_fit-latest.txt` (run `2026-10-09 22:58`)
and `refuse_floor_forward-latest.txt`. Labels in
[arm-index](arm-index.md#narrow_to_fit)._

### The rule

- A narrowed debit spread whose net debit is under 20% of its width is
  refused into `narrow_no_fit`, reason `below_net_floor`. The walk does not
  step on to a narrower strike.
- Credit spreads are never floored. A tiny credit leaves max loss near the
  width, so it cannot size up.
- It answers [next-steps §0, item 14](next-steps.md#pick-up): MU 2026-09-21
  fit at $0.06 on a 40-wide spread and sized to 83 contracts.
- Both registrations carry it as `Resolved at build (2026-10-09)`. No signal
  date on or after 2026-10-08 had a row in any export when it was fixed.

### Verdicts, PRIMARY

| Line | Role | Verdict | Narrowed subset N4 meanR [CI95] | Positions / dates |
|---|---|---|---|---|
| (R, F3, $1,000) | headline | `NULL` | +0.110 [−0.117, +0.338] | 70 / 58 |
| (R, F3, $1,000) + 20% floor | declared secondary | `NULL` | +0.084 [−0.153, +0.322] | 67 / 55 |
| (R, F3, $500) | secondary | `NARROW-FEASIBLE` | +0.248 [+0.113, +0.383] | 198 / 141 |
| (R, F3, $500) + 20% floor | declared secondary | `NARROW-FEASIBLE` | +0.249 [+0.110, +0.388] | 187 / 133 |
| `refuse_floor_forward` (R, F3, $500) + 20% floor | declared secondary | `STILL-OPEN` | no forward date yet | 0 / 0 |

| Account, net 1.50, PRIMARY | n | Total $ | meanR | maxDD $ | N2 median maxDD |
|---|---|---|---|---|---|
| (R, F3, $1,000) | 203 | 21,576 | +0.184 | −9,685 | 31.8% |
| (R, F3, $1,000) + 20% floor | 197 | 18,298 | +0.169 | −9,685 | 32.5% |
| (R, F3, $500) | 304 | 24,661 | +0.221 | −3,882 | 13.6% |
| (R, F3, $500) + 20% floor | 296 | 24,320 | +0.219 | −4,411 | 14.3% |

| Picks the floor refused, PRIMARY | Count |
|---|---|
| At $1,000 | 12 |
| At $500 | 31 |

### What this does not mean

- On this book the floored line is seen, not tested. The 20% was picked after
  item 14's in-sample read. Its test is `refuse_floor_forward`'s forward
  line.
- The no-floor output is unchanged line for line from the 2026-10-07 run.

**Next.** Next-steps item 14 closes. Nothing new is queued.

---

## 2026-10-09 — `index_bear_hedge`: forward STILL-OPEN; in-sample, the insurance cost more than it paid

**Graded on future sell-offs only, the index bear sleeve reads `STILL-OPEN`.** No sell-off has
started since acceptance, and the holdout seal keeps the forward window shut until it lifts.

**In production.** Nothing ships. No verdict here can remove the
[§4](../docs/deployment-rules.md#s4) bear sleeve.

_Era v4 · exports 2026-10-06 23:39 · book 1,850 rows · report
`backtests/study_output/index_bear_hedge-latest.txt` · recorded in
[study-results](study-results/f5_hedging/index_bear_hedge.md) · labels in
[arm-index](arm-index.md#index_bear_hedge). The v3 run is filed as
`backtests/study_output/index_bear_hedge-v3-20261009.txt`._

### The forward lines

| Line | As printed |
|---|---|
| headline | `FORWARD VERDICT (headline, floor 5 episodes): STILL-OPEN` |
| declared secondary | `FORWARD EARLY READ (declared secondary, floor 2 episodes): STILL-OPEN` |

The registration was accepted by default on 2026-10-09 with OD4 set to forward only. Every
open decision is answered beside the text it amends in the
[registration](pre-registrations/f5_hedging/index_bear_hedge.md).

### The in-sample description, which is not a verdict

The sleeve cut the deployed book's drawdown in every sell-off on both eras, and lost more
between sell-offs than it made inside them. These sell-offs may sit in the analysing model's
training data, so the study prints them as a description and grades nothing (OD4).

| Figure | v4 | v3, same sell-offs |
|---|---|---|
| evaluable E-DD5 episodes | 5 | 4 |
| episodes where the sleeve cut drawdown | 5 | 4 |
| sum of drawdown cut, `ΔDD_e` | +$51,428 | +$23,936 |
| permutation p, one-sided | 0.001 | 0.002 |
| carry outside episodes, `C` | −$84,041 | −$26,972 |
| ten sessions after each trough | −$30,513 | −$21,864 |
| NET over the span | −$43,947 | −$6,365 |
| full-span [MTM](glossary.md#mark-to-market-basis) [maxDD](glossary.md#maxdd), book alone | −$52,075 | −$17,456 |
| the same, hedged | −$67,770 | −$11,424 |
| break-even sell-offs per 252 sessions, `f*` | 2.72 | 1.67 |
| corr(sleeve, book) outside episodes | −0.579 | −0.596 |
| observed sell-offs per 252 sessions, SPY/VIX file | 1.96 | 1.96 |
| OD5 base rate, SPY since 1993 | 1.92 | 1.92 |

- Sell-offs come about twice a year. On v4 the sleeve needs more than markets give to break
  even. On v3 it needs fewer, but the post-trough sessions still make NET negative.
- The post-trough loss is the bear spreads giving back their gains as the market bounces.
  It counts on neither side of `f*`.
- `RB1` to `RB4` hold on both eras and `RB5` is quiet: single-stock bears protected less
  than index bears.

### What it changes

Item 13 in [`next-steps.md`](next-steps.md) closes. The forward read re-runs when the holdout
seal lifts and a sell-off that starts after 2026-10-09 has closed its buffer.

---

## 2026-10-09 — `bear_fast_exit` — a session-1 exit cuts the bear-debit loss and still loses

**Every fast exit loses less than the shipped bear-debit exit, and none pays
after commission.** The registered verdict is `BLEED-CUT (C7 PENDING)`, carried
by `TS 1` alone: exit at the entry-day close.

**In production.** Nothing changes. A BLEED-CUT ships nothing, and the forward
criterion C7 waits on the holdout seal.

_Report `backtests/study_output/bear_fast_exit-20261009-225853.txt`, sha
4699bd9, exports 2026-10-06 23:39. The registration was
[accepted by default](pre-registrations/f2_management/bear_fast_exit.md)
on 2026-10-09._

| Era | Role | Bear-debit rows | Dates |
|---|---|---|---|
| v4 | Primary | 686 | 261 |
| v3 | Replication | 329 | 109 |

### Headline: $0.65 per contract, no slippage

[Net R](glossary.md#net-r) with date-clustered [CIs](glossary.md#ci). ΔR is
paired against the shipped exit.

| Arm | v4 net meanR | v4 ΔR | v3 net meanR | v3 ΔR |
|---|---|---|---|---|
| Shipped | −0.144 [−0.215, −0.071] | — | −0.113 [−0.231, +0.010] | — |
| TP 0.10 | −0.033 [−0.078, +0.012] | +0.111 [+0.056, +0.167] | −0.028 [−0.097, +0.038] | +0.085 [−0.014, +0.183] |
| TP 0.20 | −0.050 [−0.102, +0.003] | +0.094 [+0.045, +0.145] | −0.036 [−0.113, +0.040] | +0.076 [−0.006, +0.160] |
| TP 0.30 | −0.054 [−0.113, +0.006] | +0.090 [+0.047, +0.134] | −0.045 [−0.134, +0.043] | +0.068 [−0.000, +0.136] |
| TS 1 | −0.017 [−0.049, +0.016] | +0.127 [+0.063, +0.190] | +0.018 [−0.017, +0.052] | +0.130 [+0.012, +0.246] |
| TS 2 | −0.010 [−0.040, +0.022] | +0.134 [+0.071, +0.198] | +0.000 [−0.043, +0.044] | +0.113 [−0.001, +0.222] |
| TS 3 | −0.011 [−0.042, +0.023] | +0.133 [+0.069, +0.199] | −0.022 [−0.074, +0.033] | +0.091 [−0.016, +0.194] |
| TS 5 | −0.028 [−0.067, +0.013] | +0.116 [+0.057, +0.174] | −0.036 [−0.105, +0.033] | +0.077 [−0.023, +0.173] |
| OP 0.25 or session 5 | −0.014 [−0.049, +0.023] | +0.130 [+0.068, +0.192] | −0.009 [−0.069, +0.049] | +0.104 [−0.007, +0.213] |

What it says:

- **Every arm cuts the v4 loss.** Each paired CI clears zero, and the C5
  folds stay positive.
- **No arm pays.** No net level clears zero on either era.
- **Only `TS 1` replicates on v3, and only just.** Eight arms on two eras
  give about one such pass by chance, which is why C7 is required.
- **The declared 25%-of-spread line prints the same verdict.** Its levels sit
  lower, close to the plan-time read.
- **The hedge-sleeve conflict stands.** A fast exit removes the protection
  the §4 sleeve is held for, and only
  [`hedge_portfolio`](arm-index.md#hedge_portfolio) can price that.

**Next.** The fast-exit bullet in [`next-steps.md`](next-steps.md) §2.4 is
closed as a loss cut. C7 reads once, when the seal lifts. No new item.

---

## 2026-10-09 — `ruin_bound` — refusing the unaffordable pick keeps ruin away; nothing passes at $1,000

**At $500 the safest eligible cell is net cap 2.50 with the F2 refusal and no
guardrail (`SAFEST ELIGIBLE CELL: N250-F2 G-none`). At the operator's $1,000
sizing no cell meets the bounds.** Nothing ships: the study is a reading for
the operator, and `config/account-sim.yml` is unchanged.

_Era v4, exports of `2026-10-06`. The book holds 1,850 rows on 280 dates,
none on or after the seal. The
[registration](pre-registrations/f4_deployment/ruin_bound.md) was accepted by
default on `2026-10-09`. The run drew 5,000 paths, seed `20261009`._

The study resamples the account walk in blocks. It asks which of 24
configurations earns the most while ruin stays under fixed bounds. Ruin means
losing half the account. The configurations are six cap cells times four
guardrails ([arms](arm-index.md#ruin_bound)).

| Cell, PRIMARY, L = 45, $500 | P(ruin) | p95 marked DD | p99 | Median $ over H |
|---|---|---|---|---|
| N250-F2 G-none (chosen) | 0.0% [0.0, 0.1] | 24.1% | 30.6% | +$14,268 |
| N150-F2 G-none | 0.0% | 24.3% | 30.6% | +$11,345 |
| N150-F1 G-none (registered headline) | 17.8% | 86.7% | 101.5% | +$6,062 |
| N250-F1 G-none (tracked config) | 25.8% | 102.9% | 123.4% | +$10,408 |
| N250-F2 G-none at $1,000 | 5.6% | 74.0% | 94.9% | +$24,551 |

- **The ruin risk sits in the one-contract floor.** Every F1 cell fails the
  bar at $500. Taking a pick whose one contract costs more than the budget
  (F1) loses half the account on about one path in six.
- **Refusing that pick (F2) keeps ruin near zero.** All eight N150-F2 and
  N250-F2 configurations meet every clause on both populations at every block
  length. N100-F2 fails only A1.
- **No riskier cell earns its drawdown.** N150-F2 against S has a per-date CI
  of [-31.4, +3.7] dollars, -$2,816 in total.
- **The guardrails add little at $500.** On the eligible cells they rarely
  fire. At $1,000 the kill switch cuts ruin to zero but leaves the p95
  drawdown past 30%.

Two gate rulings followed a 100-path smoke run and are tagged in the
registration. The reserve now includes commission (R3), and R5 is read path by
path up to the shock. On the 5,000-path run the full-H R5 order held in 288 of
288 cells anyway. All gates pass, R2 matches `simulate()` on all 24 cells, and
576 truncation checks pass.

**Next.** [Next-steps item 5](next-steps.md#waiting-on-the-operator) gains this
reading. Whether F2 should be the primary arm stays a question for a new
registration. Nothing changes the tracked cap until the operator does it by
hand.

---

## 2026-10-09 — cost sensitivity (N1): both tiers vanish, and there was no gross edge to lose

**Neither tier has a measured edge on v4, net of costs or before them.**
[`cost_sensitivity`](arm-index.md#cost_sensitivity) printed `VANISHES` for
Tier A and Tier B at $0.65 per contract with no slippage. Both tiers' gross
intervals already include zero, so commission does not remove an edge.

**In production.** Nothing changes; the registration ships no rule. Under its
`VANISHES` wording, exit tuning on both tiers stops until a later book shows an
edge. Deployment stays an operator decision
([deployment-evidence](deployment-evidence.md#caveats-on-the-ladder-as-a-whole)).

_Era v4, exports `2026-10-06 23:39`, sha `4004356`. The deployed top-3/day set
is 582 positions on 249 dates, `2024-01-10 → 2026-09-22`.
[Record](study-results/f2_management/cost_sensitivity.md)._

### Registration

Accepted by default on 2026-10-09
([registration](pre-registrations/f2_management/cost_sensitivity.md)). The
draft predated the 2026-09-24 commission-only re-price, so the stored R is
already net of the `ARM X` commission. The study adds `cost_total` back to get
gross R and charges every arm on that.

### ARM X, the graded arm

[meanR](glossary.md#meanr), [CI](glossary.md#ci) and [PF](glossary.md#pf) are
net of $0.65 per contract per leg per side.

| Tier | Positions | Dates | Net meanR | 95% CI | Net PF | PF CI |
|---|---|---|---|---|---|---|
| A | 187 | 95 | +0.108 | [−0.016, +0.237] | 1.37 | [0.95, 1.98] |
| B | 395 | 177 | +0.088 | [−0.026, +0.193] | 1.25 | [0.94, 1.67] |

### The contour

| Tier | Gross meanR (`ARM Z`) | Gross CI | Point estimate first below zero | Positions in slippage cells |
|---|---|---|---|---|
| A | +0.114 | [−0.010, +0.243] | slippage 0.50 of the spread, any commission | 180 of 187 |
| B | +0.095 | [−0.019, +0.201] | slippage 0.50 of the spread, any commission | 371 of 395 |

The quote census passed G4: 6.4% of leg-sides needed fallback 2 or were
uncostable, against a 25% bar.

### What did not grade

- **C4, era stability.** The frozen v3 export has no `cost_basis`, so G3
  refuses it. Both verdict lines agree anyway, because C1 and C2 fail first.
- **C3, leave-one-out.** Not graded, since it only applies to a tier that
  passed C1 or C2.

### Next

N1 closes in [next-steps](next-steps.md). It adds no new item. The missing
gross edge on v4 is the existing "v4 transfer is unvalidated" caveat, now
measured.

---

## 2026-10-09 — mechanical_benchmark — not built yet, awaiting a scrape; nothing ships

The study cannot yet say whether the picks beat a mechanical call spread. Its
census runs first and stops at `NOT BUILT — AWAITING SCRAPE`, because most
counterpart legs are not cached. Nothing ships.

_Era v4, with v3 as the stability read · exports 2026-10-06 23:39 · report:
`backtests/study_output/mechanical_benchmark-latest.txt` · recorded in
[study-results](study-results/f1_selection/benchmark/mechanical_benchmark.md)._

**In production.** Nothing changes.

**What the census found (v4).**

| Arm | Built | Awaiting fetch | Dropped | Contracts to fetch |
|---|---|---|---|---|
| [`ARM M1`](arm-index.md#mechanical_benchmark) | 168 | 275 | 139 | 399 |
| `ARM M2` | 39 | 365 | 178 | 311 |
| `ARM M2L` | 277 | 133 | 172 | 51 |
| `ARM U` (universe wraps) | 1,162 | 51,107 | 56 | 32,106 |

The population is 582 deployed picks on 249 dates. 111 of the drops are picks
with DTE of 180 or more, which the registration puts out of scope.

**Why it stops.** A pair whose nearest listed strike is not cached waits for a
fetch instead of being built on another strike. The cached strikes are the ones
the book traded, so reading the cached subset would bias the comparison toward
zero. `ARM U` is the arm that decides the question, and it needs stock bars for
1,978 universe tickers before its strikes can even be named.

**The registration.** Accepted by default on the drafter's defaults. The
rulings sit beside the text they amend in the
[pre-registration](pre-registrations/f1_selection/benchmark/mechanical_benchmark.md). Two
matter most. The counterpart uses the pick's own expiry. The strike choice
reads only rows dated on or before the signal date.

**Next.** A new queue item in [`next-steps.md`](next-steps.md) (item 15): the
operator decides whether to run the fetch, starting with the 710 same-ticker
contracts.

---

## 2026-10-07 — narrow_to_fit graded: headline NULL, $500 NARROW-FEASIBLE

**Narrowing an unaffordable spread does not rescue the $1,000 cell, and at
$500 it reads as feasible in-sample.** The headline (R, F3, $1,000) prints
`NULL`. The secondary (R, F3, $500) prints `NARROW-FEASIBLE`, meeting all five
criteria. The registration says the secondary never changes the headline.

**In production.** Nothing ships. The report closes "Nothing in this report is
a shippable rule." (R, F3, $500) becomes a candidate to be tested forward,
beside F2.

_Era v4 · exports 2026-10-06 23:39 · reports:
`backtests/study_output/narrow_to_fit-latest.txt` and
`pbo_ledger-latest.txt` · recorded in
[study-results](study-results/f4_deployment/narrow_to_fit.md) · labels in
[arm-index](arm-index.md#narrow_to_fit)._

### The scrape that cleared GN5

Two confirming passes of `fetch_substitute_legs.py --scope between` ran after
commit `fc716c3`. That commit made an expired contract's empty feed count as
evidence that the strike is unlisted. It counts only after two separate runs
agree, as the registration's `Resolved at build (2026-10-07)` clause states.
Commit `3412470` had already stopped the tracker dropping 404s older than an
hour.

| Pass | Empty strikes re-asked | Returned rows |
|---|---|---|
| 1 | about 1,934 | 2 |
| 2 | 1,950 | 0 |

An empty feed is therefore reliable evidence. The two strikes in pass 1 are
probably the NVDA pre-split feed-error strikes, or one RKLB 2025-10-31 68.50C.

| Skip-list entry | Count |
|---|---|
| `no_rows`, two checks | 1,623 |
| `no_rows`, one check | 327 |
| `http_404` | 3,271 |

The cache was pushed as `research-caches-20261007-1954`.

### Verdicts, PRIMARY

| Object | Q1: N1 / N2 median maxDD / N3 | Q2: N4 meanR, CI95 | N5 | Verdict |
|---|---|---|---|---|
| (R, F3, $1,000), net 1.50 | no / 31.8% / no | +0.110 [−0.117, +0.338] | not met | `NULL` |
| (R, F3, $500), net 1.50 | met / 13.6% / met | +0.248 [+0.113, +0.383] | met | `NARROW-FEASIBLE` |
| (R, F1, $1,000), stop basis | no / 34.0% / no | — | — | `NOT FEASIBLE` |
| F4, $500 budget, $1,000 stop | no / 31.5% / no | — | — | `NOT FEASIBLE` |

[N1–N5](arm-index.md#narrow_to_fit) are the registered criteria;
[meanR](glossary.md#meanr) and [maxDD](glossary.md#maxdd) are in the glossary.
Both gates that print rather than exit now clear.

| Gate | $1,000 | $500 | Bar |
|---|---|---|---|
| GN5, unpriced share of over-budget picks | 5% | 9% | 10% or less |
| GN0, narrowed positions / dates | 70 / 58 | 198 / 141 | 60 / 25 |

| Cell, PRIMARY | Positions | Total $ | meanR | maxDD $ |
|---|---|---|---|---|
| (R, F3, $500), net 1.50 | 304 | 24,661 | 0.221 | −3,882 |
| (R, F3, $500), net 2.50 | 383 | 37,505 | 0.261 | −4,391 |
| (R, F2, $500), net 1.50 | 163 | 12,837 | 0.207 | −2,808 |
| (R, F1, $500), net 1.50 | 234 | 4,719 | 0.114 | −11,050 |

### Overfitting read

`pbo_ledger` now carries the four F3 cells as a third configuration set. The
[probability of backtest overfitting](arm-index.md#pbo_ledger) (PBO) is the
share of splits whose in-sample best lands at or below the out-of-sample
median.

| Set | N | PBO total | PBO maxdd | PBO meanR | PBO bar |
|---|---|---|---|---|---|
| PRIMARY, ledger | 51 | 78.4% | 0.0% | 41.4% | 53.8% |
| PRIMARY, + ticker-cap | 59 | 69.4% | 0.0% | 32.4% | 42.2% |
| PRIMARY, + ticker-cap + F3 | 63 | 47.0% | 0.2% | 33.6% | 23.8% |
| SECONDARY, ledger | 51 | 71.5% | 0.0% | 58.2% | 40.6% |
| SECONDARY, + ticker-cap | 59 | 55.7% | 0.0% | 47.5% | 29.0% |
| SECONDARY, + ticker-cap + F3 | 63 | 35.0% | 0.0% | 33.9% | 15.5% |

PBO falls because one F3 cell wins most splits and keeps winning out of
sample. In PRIMARY, (R, F3, $500) at net 2.50 is the in-sample pick as below.

| Metric | In-sample pick | Below OOS median when picked | Full-path rank |
|---|---|---|---|
| total | 48% | 0% | 1 of 63 |
| maxdd | 4% | 2% | 9 of 63 |
| meanR | 24% | 1% | 1 of 63 |
| bar | 69% | 0% | 1 of 63 |

SECONDARY reads the same way. The registered cap cell, (R, F3, $500) at net
1.50, is almost never the in-sample pick, though it ranks near the top on the
full path.

| (R, F3, $500), net 1.50 | PRIMARY | SECONDARY |
|---|---|---|
| In-sample pick, any metric | 1% or less | 9% or less |
| Full-path rank, of 63 | 3rd to 8th | 3rd to 7th |

The bare-ledger PBO moved from 78.9% to 78.4% since 2026-10-06. That run read
the earlier 1,795-row book, so the two are not the same population.

### What this does not mean

- **It is the secondary.** The headline is `NULL`, and the registration says
  the secondary verdict never changes it.
- **It is one of many.** The sizing ledger has scored more than 60
  configurations on this one path. A low PBO says the F3 $500 cells rank
  persistently here, not that they will earn on new dates.
- **The 2026 year is weak.** N5 passes, but the narrowed subset's 2026 meanR,
  +0.095, is the lowest of its three years.
- **It is not shippable.** Only a forward grade on dates after acceptance can
  make it a rule.

**Next.** [`next-steps.md`](next-steps.md) §0 replaces the scrape state with
this result. The operator decides whether (R, F3, $500) joins the F2 forward
registration draft. The cap cell stays at 1.50.

---

## 2026-10-07 — `ticker_class`: index ETFs are not more reliable

**Index ETFs carry no more reliable edge than single stocks once direction is held
fixed.** The primary contrast reads NULL. The four secondary contrasts read NULL or
UNDERPOWERED. Picking a best group is fragile, with a PBO of 0.367. The v3 replication
reads NULL as well, with a PBO of 0.845.

**In production.** Nothing changes. A NULL files nothing, by the registration's ship
criteria.

_Era v4 · exports 2026-10-06 23:39 · reports: `backtests/study_output/ticker_class-latest.txt`
and the v3 file beside it · registration
[`ticker_class`](pre-registrations/f1_selection/benchmark/ticker_class.md), labels in
[arm-index](arm-index.md#ticker_class)._

### Rulings

| Item | Ruling |
|---|---|
| In-sample book | Signal dates before 2026-08-11: 1,721 rows over 251 dates |
| Registration | Accepted 2026-10-07 with all seven recommendations |
| Group table | Fixed and hashed before any outcome was read; GT3 checks the hash |
| Trial ledger | A separate selection ledger, five trials, outside the three-arm cap |
| Forward window | Signal dates after 2026-10-07; 2026-08-11 to 2026-10-07 is in neither window |

### Contrasts, v4, net of cost

| Object | G1 meanR | Comparison meanR | Difference, CI95 | Verdict |
|---|---|---|---|---|
| P1, G1 vs single stocks | −0.089 | −0.058 | −0.031 [−0.149, +0.086] | NULL |
| S1, bear, G1 vs big tech | −0.187 | −0.170 | −0.017 [−0.194, +0.171] | NULL |
| S2, bear, G1 vs semis | −0.187 | −0.177 | −0.010 [−0.182, +0.155] | NULL |
| S3, bear, G1 vs rest | −0.187 | +0.018 | −0.205 [−0.382, −0.026] | NULL |
| S4, bull, G1 vs country | +0.295 | +0.320 | −0.024 [−0.359, +0.321] | UNDERPOWERED |

S3's CI is unadjusted. At its Holm level it is [−0.423, +0.025], so it is not CONTRARY.
S4 fails power on the index side, which has 48 bull positions.

### What did move

| Reading | Value |
|---|---|
| G1 share of the book's drawdown episode, 2025-12 → 2026-08 | 46% of the R, on 12% of positions |
| Median exit capture, bear: G1 / big tech / semis / rest | −1.22 / −0.66 / −0.67 / +0.10 |
| P1 difference by year: 2024 / 2025 / 2026 | +0.055 / +0.105 / −0.382 |
| v3 P1, bear in effect | +0.215 [+0.005, +0.427], voided by PBO |

These are printed readings, not verdicts. The two eras disagree in sign on P1.

### Unresolved

- **Index bear puts and the drawdown.** G1 carries a large share of the 2025-12 → 2026-08
  drawdown. This overlaps the existing [bear_position_study](study-results/f1_selection/bear/bear_position_study.md)
  demotion, since 80% of G1 is bear. No new cut is graded here.
- **PBO ties.** 2,333 of 12,870 CSCV splits land exactly on the median, and PBO counts them
  against the selection.
- **The forward read** is STILL-OPEN with 0 forward dates.

**Next.** No queue change. The forward grade re-runs P1 once each side has 30 signal
dates after 2026-10-07.

### Addendum: regime, exploratory

**The `mech_cell` regime does not explain the gap; the late-2025 period does.** This read is
exploratory. It grades nothing and files nothing. The forward study
[`ticker_class_regime`](pre-registrations/f1_selection/benchmark/ticker_class_regime.md) was drafted and
hashed before it ran.

_Same in-sample book as above · script and output in the session scratchpad, not the repo ·
raw CIs with no multiplicity control._

| Cut, bear plays, G1 vs S | G1 / S positions | Difference, CI95 |
|---|---|---|
| LVOL | 149 / 210 | −0.088 [−0.242, +0.067] |
| BEAR_HE | 27 / 46, thin | +0.109 [−0.185, +0.420] |
| BEAR_HE minus LVOL | — | +0.197 [−0.142, +0.542] |
| Before 2025-12-01 | 135 / 183 | +0.028 [−0.132, +0.197] |
| 2025-12-01 → 2026-08-10 | 54 / 97, thin | −0.378 [−0.589, −0.165] |
| LVOL, 2025-12-01 → 2026-08-10 | 41 / 71, thin | −0.406 [−0.621, −0.179] |
| Bull plays, LVOL | 41 / 582, thin | +0.256 [+0.065, +0.437] |

The 2025-12-01 boundary was taken from the drawdown episode, so it is outcome-informed. The
late-period loss sits inside LVOL. There, index bear puts hit 20% against 43% for single stocks.

`load_book()` labels unmapped rows `PROD`, not `NONE`. The draft was corrected for that and the
change is logged in it.

### Addendum: regime, all dates, exploratory

**No regime pattern survives the number of looks, and the two eras disagree in sign.** The
operator set the forward study aside and asked for every existing date instead. This read
spends the 2026-08-11 → 2026-09-22 dates the draft had kept unread. It grades nothing.

_Every v4 and v3 backtest date · script and output in the session scratchpad._

| Era | Rows | Dates |
|---|---|---|
| v4, all dates | 1,850 | 280 |
| v3 | 790 | 118 |

| Era | Tests run | Smallest BH q | Survives BH q ≤ 0.10 | Survives Bonferroni |
|---|---|---|---|---|
| v4 | 51 | 0.122 | none | none |
| v3 | 45 | 0.099 | bear BEAR × H-VOL grid cell | none |

The v3 survivor fails three robustness checks: median R, the exit-free E, and the later half
all flip sign. v4 cannot test it, since its G1 side is thin there.

| Bear plays, G1 − S | v4 all dates | v3 |
|---|---|---|
| BULL trend | −0.132 | −0.012 |
| Non-BULL trend | −0.035 | +0.280 |
| L-VOL | −0.088 | +0.120 |
| H/E-VOL | −0.162 | +0.202 |

On v4 every bear gap is negative. On v3, three of four are positive. Five of seven contrasts
disagree in sign across eras. Closed positions only change no sign on v4.

The strongest v4 reads are the 2025-12 → 2026-08 period: −0.410 non-BULL, −0.406 L-VOL. Both
pass every robustness check they can take, but their boundary is outcome-informed and their q
is 0.122. On v3 the same months read positive.

**Next.** No queue change. The forward draft stays a draft; the operator set it aside.

### Addendum: root cause of the late loss, exploratory

**The market shifted: no index sell-off came, and index bear spreads need one.** The loss is
not in the model's picks or the backtest. Almost all of it falls in 2026-04-08 → 2026-08-10,
after v3's last date.

| v4 bear plays | G1 positions | G1 meanR | S meanR | Gap |
|---|---|---|---|---|
| Before 2025-12-01 | 135 | −0.114 | −0.142 | +0.028 |
| 2025-12-01 → 2026-04-07 | 23 | −0.129 | +0.053 | −0.18, CI crosses 0 |
| 2026-04-08 → 2026-08-10 | 31 | −0.547 | −0.015 | −0.53 [−0.74, −0.32] |

| Market, from `spy_vix_daily_full.csv` | Before 2025-12-01 | 2026-04-08 → 2026-08-10 |
|---|---|---|
| Days followed by a 20-day SPY drop of 5% or more | 5.9% | 0% |
| Worst 20-day SPY move | −12.3% | −3.4% |

Over the late stretch SPY rose 14% and VIX fell from 21 to 15.5.

| Candidate cause | Finding | Knowable at entry |
|---|---|---|
| No sell-off | Realised move in sigma units absorbs 84–89% of the G1 × period interaction | No |
| Single-stock bears improved | About 37% of the gap change; skill or luck not separable | No |
| Exit timing, Dec–Apr | Time exits fired before the March 2026 sell-off; 22 positions | No |
| Strikes, tier, mix, pricing basis, cost, open marks | Unchanged, or the gap survives removing them | — |
| Put richness, skew, VIX, momentum | Higher late, but they do not predict within the earlier period | Yes, but null |

v3 is not counter-evidence. On the 13 dates both eras analysed, G1 bear reads the same:
v3 −0.137, v4 −0.125.

An index bear spread loses on average unless a crash arrives. A G1-vs-S contrast therefore
mostly counts how many sell-offs fell in its sample. Its effective sample size is the
number of sell-off episodes, not positions.

**Next.** No queue change. Any future test of index bear plays needs power counted in
sell-off episodes, and belongs with the hedge programme rather than selection.

---

## 2026-10-06 — sizing levers: ticker cap, credit census, overfitting

**No sizing lever is proven, and picking one from the ledger is mostly luck.**
Capping a ticker's signed total changes no verdict. The credit stop census now
has its floor and does not fire. The probability of backtest overfitting on the
sizing ledger is 74% to 79% on total return.

**In production.** Nothing changes. Every item is filed in
[deployment-evidence](deployment-evidence.md#sizing-and-drawdown-candidates--open-2026-10-06),
marked concrete or to be tested.

_Era v4 · exports 2026-09-27 15:57 · 2026-09-28 book · reports:
`backtests/study_output/account_sim-ticker-cap-20261006.txt` and the
`pbo_ledger` run._

### Rulings

| Item | Ruling |
|---|---|
| F2, refuse the floor | Graded continuously on post-acceptance dates; forward; registration is a draft |
| Overfitting tests | Standing: a candidate from many configurations carries a PBO read plus forward grading |
| Ticker cap | Read as conformance with production `s03_risk`, not a new arm |
| F3 scrape scope | Owed |

### Ticker cap, primary, ARM R

| Cell | maxDD before → after | meanR before → after |
|---|---|---|
| (R, F1, $500), net 1.50 | 50.4% → 61.7% | +0.099 → +0.144 |
| (R, F2, $500), net 1.50 | 11.0% → 11.2% | +0.200 → +0.230 |
| (R, F1, $1,000), net 1.50 | 33.9% → 35.5% | +0.111 → +0.104 |
| (R, F2, $1,000), net 1.50 | 34.9% → 19.7% | +0.178 → +0.207 |
| (R, F2, $1,000), net 2.50 | 48.2% → 19.7% | +0.182 → +0.222 |

### Credit sl-none census

| Population | sl-none | `sl 1x` | Δ |
|---|---|---|---|
| Real rows, 50 over 23 dates (census code) | +$12,753 | +$10,781 | −$1,972 |
| Registered, 56 rows over 25 dates | +$13,710 | +$10,910 | −$2,799 |

`NOT FIRED`, not settled: 23 of 50 rows are still open. If XLE 07-22 and GLD
08-25 both finish at max loss, the gap is about +$16.

### Probability of backtest overfitting

| Ledger | PBO total | PBO maxdd | PBO meanR | PBO bar |
|---|---|---|---|---|
| Primary | 78.9% | 0.0% | 44.9% | 50.0% |
| Primary plus ticker-cap | 79.1% | 0.0% | 39.8% | 47.4% |
| Secondary | 73.9% | 0.0% | 60.6% | 41.7% |
| Secondary plus ticker-cap | 73.0% | 0.0% | 57.6% | 39.7% |

The 0% on maxdd is mechanical, since sizing sets drawdown.

### Unresolved

- **Tweak rows in the credit census.** The code reads real rows only. The
  default stays real-only until the operator decides.
- **The F3 scrape scope.** 862 contracts, or about 4,411 with `--scope between`.
- **F2 acceptance.** `refuse_floor_forward.md` is a draft.
- **Four items to be tested:** resting stops, the credit veto, earnings-in-hold
  exclusion, and F3. Details in deployment-evidence.

**Next.** No queue change. The credit census is re-read after the entry-window
redo ([`next-steps.md`](next-steps.md) §0 step 2).

---

## 2026-10-01 — entry window, and `narrow_to_fit`'s cached cells

**A bigger stop does not rescue the 1-contract floor.** Every cached
take-the-floor cell of [`narrow_to_fit`](pre-registrations/f4_deployment/narrow_to_fit.md)
reads `NOT FEASIBLE`, because A1's CI crosses zero. The headline F3 cells wait
on the substitute-leg scrape.

**In production.** The backtest now refuses a leg with no real quote by the
5th trading day after the signal, as `stale_leg_at_entry`. A leg first quoted
later inside that window moves the entry to that day. The redo of the affected
dates is not run yet.

### Rulings

| Item | Ruling |
|---|---|
| Entry window | 5 trading days; a late entry inside it is allowed |
| Seeded skip-list entries | Drop all 2,703; the redo re-checks them |
| `narrow_to_fit` | Registered; headline `(R, F3, $1,000)` |

### Cached cells, primary, ARM R

| Cell | Cap net | n | A1 meanR [CI] | A3 maxDD |
|---|---|---|---|---|
| F1, $500 | 1.50 | 226 | +0.099 [−0.015, +0.211] | 50.4% |
| F1, $1,000 | 1.50 | 181 | +0.111 [−0.037, +0.253] | 33.9% |
| F4, $500 sizing, $1,000 stop | 1.50 | 213 | +0.094 [−0.048, +0.226] | 31.1% |
| F2, $500 | 1.50 | 158 | +0.200 [+0.071, +0.326] | 11.0% |
| F2, $1,000 | 1.50 | 170 | +0.178 [+0.037, +0.308] | 34.9% |

- The $1,000 stop alone cuts maxDD from 50.4% to 31.1%. It does not lift A1.
- F2 at $500 still passes every gate but A5. It stays a post-hoc comparator.
- The 2.50 cap cell reads the same way. The full report is
  `backtests/study_output/narrow_to_fit-cached-20261001.txt`.
- The cached cells ran before the registration was committed. Their text was
  final when they ran, and the headline cells have not run.

### Profit factor

| Cell | n | PF ($) | PF (R) | A3 maxDD |
|---|---|---|---|---|
| F1, $500 | 226 | 1.04 | 1.32 | 50.4% |
| F1, $1,000 | 181 | 1.20 | 1.32 | 33.9% |
| F4, $500 sizing, $1,000 stop | 213 | 1.20 | 1.26 | 31.1% |
| F2, $500 | 158 | 1.75 | 1.73 | 11.0% |
| F2, $1,000 | 170 | 1.36 | 1.64 | 34.9% |

PF ($) is gross winning dollars over gross losing dollars; PF (R) is the same on per-trade R, ignoring size. The 2.50 cell and SECONDARY are in `narrow_to_fit-cached-pf-20261001.csv`.

- F2 at $500 has the best PF on both bases.
- F1 at $500 earns less per dollar lost than per R lost. The likely cause is
  the 1-contract floor's oversize positions. That cause is inferred, not
  tested.

### Unresolved

- **The F3 scrape is not funded.** It is about 867 contracts, about 3.6 h.
- **`bear_rewrap` does not apply the entry window**
  ([next-steps §2.11](next-steps.md#s2-11)).

---

## 2026-09-29 — operator rulings, the 1.50 cell and the 2026 column

**Nothing ships, and the registered 1.50 cap cell is no longer feasible.**
The operator ruled on the five open items from the
[09-28 entry](#2026-09-28--loader-rulings-and-suite-re-run--the-book-reads-again).
A re-run of the registered cell on the 09-28 book fails A1 and A3. In 2026 the
A/B ladder reads flat, and its losses sit in one pocket.

**In production.** Nothing changes.

### Rulings

| Item | Ruling |
|---|---|
| Bear debit stop | No config change. The census is about `be_after`, off since 2026-08-24. `sl .50` is not adopted |
| `path_data_end` cut | Kept in every study's replays |
| VETO rows in `regime_gap_reread` | No registration. The study's real-only and post-13c cuts now print the pooled numbers, so fix the split first |
| BEAR_HE clause | [§5](../docs/deployment-rules.md#s5) stands; an observation until its census is powered |
| `account_sim` cap cell | Open; the re-run below changes the question |

### The registered 1.50 cell on the 09-28 book

Run once with a copied config. The `-latest` files and site pages were
restored after it, and the report is not recorded.

| Primary, $25k, (R, F1) | Net cap 1.50 | Net cap 2.50 |
|---|---|---|
| Positions / dates | 226 / 135 | 321 / 170 |
| A1 meanR, CI | +0.099 [−0.015, +0.211] | +0.106 [+0.003, +0.206] |
| A1 2026 | −0.205 | −0.260 |
| A3 maxDD | 50.4% | 74.8% |
| Verdict | `NOT FEASIBLE` | `NOT FEASIBLE` |

On 09-21 the same cell read `FEASIBLE` at 20.3% on 142 positions. The book
has since gained June to September 2026 and the 09-24 re-price. No rung of the
capital ladder passes A1 under 1.50. (R, F2) meets A1, A2, A3, A4 and A6 under
both caps, failing A5; adopting it would need a new registration.

### The 2026 column, descriptive

Stored `realized_pnl_pct`, `load_book` defaults, date-clustered CI.

| Tier A+B | n | meanR [CI] |
|---|---|---|
| 2024 | 279 | +0.170 [+0.041, +0.296] |
| 2025 | 240 | +0.218 [+0.073, +0.354] |
| 2026 | 229 | −0.066 [−0.212, +0.073] |
| 2026, real `bull_call_spread` | 129 | +0.129 [+0.027, +0.232] |
| 2026, tweak `bull_put_spread` | 21 | −1.045 |
| 2026, clipped at −1 R | 229 | +0.02 (2025: +0.26) |
| 2026, the 20 rows past −1 R | 20 | −40 R summed (all 229: −15 R) |

- A+B no longer separates from tier C in 2026.
- The loss is credit-tail severity: a handful of rows past −1 R outweigh
  the rest. The worst 12 are tier-B `bull_put_spread`, most of them GLD and AMD.
- Selection holds: median MFE is +0.89 against +1.00 in 2025.
- Clipped at −1 R, 2026 is still weaker than 2025: flat, not negative.
- 103 of the 229 rows are marks rather than closed trades.

### Unresolved

- **`pnl_at_cap_pct` is not a current mark on `open_at_data_end` rows.** It
  runs on carried marks, and differs by more than one point on 58 of 148
  rows (operator count, 2026-09-28).
- **Two rows were entered after their last real quote.** GLD
  `bull_call_spread` (signal 2026-09-18, data end 08-14) and FSLR
  `bear_put_spread` (signal 09-15, data end 07-06). No other stored row has
  `path_data_end` before its signal date. Proposed rule, not built: refuse
  an entry when `path_data_end` precedes the entry day, as
  `stale_leg_at_entry`. Operator ruling owed.
- **The open rows concentrate in SMH.** Five of the ten largest
  `open_at_data_end` losers are SMH `bear_put_spread` rows, −$4,233
  together. They are one bet, not five.
- **The unlisted skip-list holds 2,703 seeded entries** that never passed the
  evidence gate; 651 carry a 2026-09-25 first-seen date, the outage day.
  Operator ruling owed on dropping them.
- **The study loader carries a second tier encoding.**
  `lib/book.py::ladder_tier` is a port, not an import, of
  `mapping.ladder_tier()`, and it lacks the credit-in-RANGE+L-VOL veto. Every
  tier cut in the research tier, the 2026 table above included, uses it.
  Pointing it at `mapping` changes study output, so it waits on the operator.
- **The backfill supervisor is not stuck; it is stopped.** Nothing has run it
  since 2026-09-24. Its GLD empties are deep in-the-money puts that the
  near-money filter admitted, not 404s or a range bug.

---

## 2026-09-28 — loader rulings and suite re-run — the book reads again

**The suite reads the re-priced book again, and 13 verdicts moved.** The
operator's three loader rulings and the mirror ruling are built, every
calibration gate passes, and the suite was re-run and recorded. This entry
supersedes the [2026-09-27 entry](#2026-09-27--suite-re-run--ten-studies-stop-and-the-other-22-read-a-book-the-loader-misreads),
whose run was never recorded.

**In production.** Nothing changes. Two moves bear on shipped rules and are
flagged below for the operator; neither edits
[`deployment-rules.md`](../docs/deployment-rules.md).

| Provenance | Value |
|---|---|
| Era, exports | v4, pulled 2026-09-27 15:57 |
| Rows | 1,012 real, 2,029 proxy, 3,346 analysis |
| Pooled book | 1,795 rows over 280 dates, 2024-01-10 to 2026-09-22 |
| Code | `de5a6f3` plus the uncommitted work of 09-24 to 09-28 |
| Records | [study-results](study-results/), one new v4 section per study |

### The rulings as built

Each is folded as `Resolved at build (2026-09-28)` into the
[architecture](../docs/architecture.md) and the registrations whose gate it
changes.

| Ruling | What the code does now | Where |
|---|---|---|
| Add the row's cost back | The replay is compared with the stored figure plus `cost_total`, in production's own rounding. Blank `cost_basis` compares as before. | `lib/replay_basis.py::reproduces_pnl` |
| `open_at_data_end` rows stay as `cap_open` | Every replay runs on the Trade cut at `path_data_end`, the calibration's and every study's. `carried` rows are compared on the same cut. | `replay_basis.bounded`, `lib/book.py` |
| Count how much is marks | `load_book` prints a `book outcomes:` line into every report that loads the book. | `book.path_outcomes` |
| Deferred fills are a superseded basis | Their own `deferred_fill` class: kept, counted, never compared. `no_two_sided` rows are compared, because production filled them on the trigger day. | `replay_basis.classify` |
| Mirrors follow production | `hedge_instrument` fills and marks through `simulate`'s shared functions. `open_fill_legs` asks what `entry_day_fill` would do. | `lib/hedge_instrument.py`, `lib/reprice_targets.py` |

| Returned book, 1,795 rows | Count |
|---|---|
| `open_at_data_end`, a mark at the data end | 192 |
| `carried` | 126 |
| Deferred exit fills | 43 |
| `no_two_sided` | 21 |

### Calibration before and after

| Debit rows | 09-27 loader | 09-28 loader |
|---|---|---|
| Real, 762 | 3 reproduce, 745 hard | 722 reproduce; 25 deferred, 14 superseded, 1 boundary tie, 0 hard |
| Proxy tweak, 575 | 0 reproduce | 541 reproduce, 14 deferred admitted, 1 hard |
| Credit, 250 | not reported | 247 exact, 3 deferred |

The one hard proxy row is AAPL 2025-04-09, a `dollar_stop` and `stop_loss`
tie at the same pnl. The boundary-tie check nudges only the pt and sl
thresholds, so it stays excluded; nothing was loosened to admit it.

### What moved

Every run exited 0 after three fixes made during the run (below). Drivers:
population (a), the 09-24 re-price (b), today's loader basis (c). No move can
split (a) from (b), because both changed in one run.

| Study | 09-19 | 09-28 | Likely driver |
|---|---|---|---|
| `bear_arm` B2 | `NOT met` | `MET`, `sl .50` Δ=+0.033 | (b) or (c) |
| `mech_regime_recut` | `OR-VETO REJECTED` | `OR-veto passes this criterion` | not separable |
| `text_features` | every feature NULL | `invalidation_level`, `trigger_level` CANDIDATE | (a); label coverage 51.1% |
| `exit_drawdown` | 7 `UNDERPOWERED` | U/a, U/b `REACTIVE-AGAIN` | (a) |
| `exit_from_text` E2 | `CANDIDATE` | `NULL` | not separable |
| `staged_exit` | NULL in substance | `REACTIVE-AGAIN` | (c) or (a) |
| `volume_signal` | `PATH-VOL-PROXY` | `NULL — the volume column is CLOSED` | not separable |
| `financed_spread` | F4-d20 $100 `RE-WRAP` | every cell `NULL` | not separable |
| `account_sim` | A1 holds, A3 fails | `NOT FEASIBLE`, A1 fails too | (a) and (b); 2026 at −0.260 |
| `concurrency_correlation` | `RESTATEMENT` | `NOISE` | not separable |
| `portfolio_delta` | `NOISE` | `DELTA-DOSE-RESPONSE`, descriptive | (a) |
| `hedge_sizing` | D1 4 candidates | D1 `NOT MET` | not separable |
| `hedge_timing` H4 | `NULL` | `UNSTABLE` | (b): H4 is the dollar arm |

Unchanged tokens: `bear_position_study`, `emission_timing`,
`macro_event_study`, `trigger_entry`, `v4_bridge`, `exit_switch_*`,
`selection_order`, `ladder_overlay`, `hedge_portfolio` (both),
`hedge_structure`, `bear_rewrap`. The rest moved numbers only. Verbatim
lines are in each record and in `catalog.py`.

### Moves that touch shipped rules

- **Gap-up prohibition, [§4](../docs/deployment-rules.md#s4).**
  `hedge_timing` H3-GAP is `CONTRARY` again, −0.457 CI [−0.744, −0.177]. The
  09-27 `NULL` was a loader artifact, so the prohibition keeps its support.
- **Bear debit stop.** `bear_arm` B2 now meets its exit-fix criteria at
  `sl .50`, while the rollback census still prints
  `REVERT CONDITION FIRED`. The 2026 cell alone straddles zero. Operator
  decision; the default is no config change.
- **BEAR_HE clause.** `exit_switch_structure_study` Q2 reads Δ=−5.0875
  with 23% retained. It is still an observation, because its census is
  underpowered at 12 affected dates.
- **Ladder.** A and B still beat C, but VETO rows now average the same as A
  (`regime_gap_reread`). No study prints a verdict on a `bull_call_spread`
  tier cell.

### Fixes made during the run

- `trigger_entry` G-SYNTH failed on 275 rows, because
  `emission_timing.synth_trade` rebuilt from the cut Trade. It now builds
  from the uncut row and cuts the synthetic at the same date.
- `account_sim`'s chart pages refused the report, because the loader's
  stderr line landed inside the CONFIGURATION block. The book now loads
  before that block prints.
- `config/macro-events.yml` gained the Jul 2026 FOMC minutes, released
  2026-08-19 per the Fed's calendar page, so `macro_event_study` G0 passes.
  `make mech-regime` now runs through 2026-09-25.

### Unresolved

- **Variant replays of open rows stop at the data end.** The loader hands
  studies the cut Trade, which follows production's rule. The default was
  chosen so a `cap_open` outcome stays one under every profile; reverting
  means handing `t` uncut in `book.py`.
- **`prompt_eval`** was skipped as designed; it needs its own invocation.
- The AAPL 2025-04-09 dollar-stop tie is one excluded proxy row.

**Next.** [`next-steps.md`](next-steps.md) §2.11 closes the loader and
mirror items. The two rule-bearing moves wait on the operator.

---

## 2026-09-27 — suite re-run — ten studies stop, and the other 22 read a book the loader misreads

**The first suite run on the re-priced book cannot be read.** The re-price
changed what a stored row means, and the research book loader still compares
each row with the frozen harness on the old terms. So 745 of 762 real debit
rows fail calibration, and 575 proxy rows fall out of the pooled book. Ten
studies stop on their gates. The other 22 print, but on a book that is not the
one they name.

**In production.** Nothing changes. No verdict in `catalog.py` was edited, and
nothing was appended to [study-results](study-results/). A verdict printed on
this book would be recorded as the v4 answer and then have to be disowned.

| Provenance | Value |
|---|---|
| Era, exports | v4, pulled 2026-09-27 15:57 |
| Rows | 1,012 real, 2,029 proxy, 3,346 analysis |
| Pooled book | 1,241 rows over 269 dates; 1,325 over 207 on 09-19 |
| Code | `de5a6f3` plus the uncommitted mirror work |
| Reports | `backtests/study_output/`; the 09-19 set was copied aside first |

### Why the calibration fails

The loader replays every stored debit row under the frozen
[harness](../scripts/backtest_study/lib/harness.py) and admits it only if the
exit, the day and `realized_pnl_pct` match. Three changes since 09-19 break
that match, and none is a pricing error.

| Cause | Real debit rows | Proxy debit rows |
|---|---|---|
| Stored P&L is net of commission; the replay is gross | 559 | 469 |
| `path_status` is `open_at_data_end` | 119 | 32 |
| `path_status` is `carried` | 51 | 44 |
| The exit filled on a later day (`exit_fill` `deferred_n`) | 16 | 12 |
| Reproduces, or differs only by an old exit rule | 17 | 18 |

- **Cost.** Every row now carries `cost_basis` `commission_only`. The replay
  matches the exit and the day, and misses the P&L by exactly the row's cost.
  `lib/mtm_curve.py` already adds the cost back for the same reason
  (2026-09-23), and the loader does not.
- **Open rows.** 148 real rows and 44 proxy rows are positions still open
  when their data ran out, stamped `cap_open` at `path_data_end`. Their stored
  mark path still runs the full grid on carried marks, so the replay keeps
  going past the data end. The real ones enter every study as closed outcomes.
- **Deferred fills.** The frozen harness fills on the trigger day. Production
  has filled on the next two-sided day since 2026-09-19.

### What each study did

| Study | Outcome | Cause |
|---|---|---|
| `bear_position_study`, `exit_switch_mech_study`, `exit_switch_structure_study` | `*** HARNESS VALIDATION FAILED — STOPPING per pre-registration. ***` | calibration |
| `exit_mechanism_study`, and its credit arm | `CALIBRATION FAILED — variant numbers below are NOT trustworthy.` | calibration |
| `account_sim`, and its compounding arm | `GATES: FAILED — G2`, on `calibrated debit picks re-replayed: 0` | calibration |
| `exit_drawdown` | `*** G-CAL FAILED: account_sim's own G2-G5 did not pass` | inherits `account_sim` |
| `trigger_entry` | crashed: `StatisticsError: fmean requires at least one data point` | no row passed its calibration gate |
| `hedge_structure` | `reconstructs: 1239 / 1241  (99.8%)`, `R2 FAIL` | two open QQQ bear puts; see below |
| `macro_event_study` | `*** G0 REFUSAL: calendar does not cover the book span for ['fomc_minutes'] — extend config/macro-events.yml, do not narrow the book. ***` | the book now ends 2026-09-22 |
| `prompt_eval` | usage error, no sub-command | designed; not a study run |
| 22 others | exit 0 | on the misread book |

**The two `hedge_structure` failures are a different cause.** QQQ 2026-08-26
and 2026-09-14 are open positions priced on 2026-09-24. The cache gained
quotes for 09-23 and 09-24 after that, so the mirror's marks and the stored
carried marks disagree from 09-23 on. A row priced on a still-growing cache
will keep doing this until its options expire.

### The 22 that printed

None of these moves can be read. The population changed (+19 analysis dates,
+40 result rows) and the loader dropped three quarters of the proxy debit rows
in the same run, so no move can be split into the two. They are listed so
the next valid run has something to compare with.

| Study | 09-19 record | This run |
|---|---|---|
| [`hedge_timing`](arm-index.md#hedge_timing) | H3-GAP `CONTRARY` | H3-GAP `NULL`; H4-CHOP and H4-GAP `UNSTABLE` |
| [`hedge_sizing`](arm-index.md#hedge_sizing) | D1 candidates 4; D2, D3 `NOT MET` | D1 `NOT MET`; D2, D3 `MET` |
| `mech_regime_recut` | `OR-VETO REJECTED` | `OR-veto passes this criterion` |
| `volume_signal` | `PATH-VOL-PROXY` | `NULL` |
| `selection_order` | `ORDERING-IS-NOISE` | `UNDERPOWERED` |
| `concurrency_correlation` | `RESTATEMENT` | `NOISE` |
| `hedge_portfolio` admitted arm | `PRECONDITION-NULL` | `UNDERPOWERED` |
| [`financed_spread`](arm-index.md#financed_spread) | F4-d20 $100 `RE-WRAP` | F4-d10 pt50 and $100 `RE-WRAP`; every F4-d20 cell `UNDERPOWERED` |
| [`exit_from_text`](arm-index.md#exit_from_text) | E2 MECH LVOL N=3 `CANDIDATE` | every cell `UNDERPOWERED`; 5 of 1,241 rows passed its gate |
| `ladder_overlay` | every v4 cell `NULL` | L-F4, L-T0 and L-T0-TEF `UNDERPOWERED` |
| `bear_arm`, `v4_bridge`, `hedge_portfolio`, `portfolio_delta`, `ml_combination`, `bear_rewrap` | — | same verdict tokens, numbers moved |
| `text_features`, `staged_exit`, `next_day_move`, `bear_giveback`, `regime_gap_reread`, `emission_timing` | — | numbers only |

The `hedge_timing` line matters most once the book is fixed. H3-GAP is the only
support left for the gap-up prohibition in
[§4](../docs/deployment-rules.md#s4). If a valid run also prints `NULL`, the
prohibition has no study behind it.

### What changed since the 09-19 run

The re-price and the pricing rules are in the 2026-09-23 and 2026-09-24
entries below. In one list:

- **The whole book was re-priced on 2026-09-24.** It first ran at $0.65 a
  contract plus 25% of the quoted spread, then again commission-only
  ([entry](#2026-09-24-latest--backtest-costs--commission-only-the-operator-fills-spreads-at-the-mid)).
  The end-of-data guard stamps `path_status` and `path_data_end`. BacktestResults went
  from 603 to 972 rows.
- **Repairs on the tabs.** Two concurrent sessions left 461 duplicate keys,
  repaired by a `--cache-only --redo`. The 2025-07-29 EEM and COIN orphans and
  the corrupt IBIT "bot" row were deleted. All 99 plays that left
  BacktestResults are on BacktestProxy.
- **Junk quotes** ([entry](#2026-09-24-earlier--backtest-pricing--a-junk-quote-is-no-longer-a-price-a-mark-or-a-spread)).
  A bought leg into a junk quote with no trade is refused as
  `junk_entry_quote`. A junk side pays commission only.
- **Proxy `skip_reason`.** A row the snap or probe priced from real history now
  reads `snap_priced`, not `no_history`.
- **The `bear_rewrap` mirror follows the junk rule.** Production's entry and
  junk-mark choices are shared functions in `scripts/backtest/simulate.py`,
  and the mirror imports them. Production output was byte-identical over
  10,156 simulations. Reconstruction on the 09-24 book went from 1,154 to
  1,159 of 1,159. `overlay_campaign._row_spread` now calls production's
  `_leg_spread`. The three registrations that promised an unchanged
  `bear_rewrap` carry a `Resolved at build (2026-09-24)` note.
- **Nineteen analysis dates were added**, 2026-06-01 to 2026-07-14. That
  brought AnalysisClaude to 3,346 rows and BacktestResults to 1,012.
- **An unlisted-contract skip list.** `_unlisted.jsonl` records contracts
  Barchart does not list, and `--retry-unlisted` overrides it. A dead contract
  now costs 1 to 3 seconds instead of about 15
  ([architecture](../docs/architecture.md)).

### A descriptive read of the re-priced book

Not a registered study, and computed on the 972-row export, before the 19 new
dates. It was not recomputed on this export.

| Cut | Result |
|---|---|
| Closed book | −$25 a trade, CI −$108 to +$59: no edge |
| A/B against C ([ladder](glossary.md#tier-ladder-abcveto)) | holds |
| `bull_call_spread` | +$167 a trade, CI +$32 to +$306, about half its old edge |
| `bull_call_spread` by tier | neither tier clears zero alone; NVDA carries it |
| 2026 loss | one CAR strangle, −$17.9k |
| 2026 closed trades | 39% reached +10% MFE and still closed at a loss |

### Unresolved

- **The loader and the stored rows disagree.** Three rulings are owed before
  the suite can run. Should calibration add the row's cost back, as
  `mtm_curve` does? What is an `open_at_data_end` row to a study: excluded, or
  an outcome? Is a deferred fill a superseded basis, like a `trailing_stop`
  row? The default is that nothing runs. Each changes what a gate admits,
  which is why none was changed here.
- **Two research mirrors are deferred.** `lib/hedge_instrument.py` still marks
  at the raw mid, and what G-FILL calls "fillable" depends on the ruling.
  `lib/reprice_targets.py::open_fill_legs` still uses the pre-junk entry test.
- **2026-06-29 has a partial counterpart IV.** Repeated SSL errors stopped
  the fetch, so that date was analysed with some IV columns blank.
- **The 06-01 to 06-08 scrapes hit the 500-row cap.** Six sessions' flow
  files may be truncated, and their analyses read what survived.
- **29 old proxy rows on the double-analysis dates were deleted** by another
  session on 2026-09-24. Copies are in the `_snapshot-*` files.
- **Legacy `no_history`.** Proxy rows written before 2026-09-24 keep the old
  label, even when the snap priced them.
- **The 7-ETF backfill supervisor is stuck** in a loop on GLD 2022-06-03
  puts.
- **`macro_event_study` needs its calendar extended** for `fomc_minutes`, and
  the mech-regime table ends 2026-09-18 (`make mech-regime`).
- **Operator decisions owed from the 09-19 run.** The `account_sim` capital
  question, the `bear_arm` revert print and the BEAR_HE observation are still
  open. The four stored-book re-price items are done
  ([next-steps](next-steps.md) §0).

**Next.** The loader rulings go to the top of
[next-steps](next-steps.md#s2-11) §2.11. The suite re-runs, and records, after
them.

---

## 2026-09-24 (latest) — backtest costs — commission only; the operator fills spreads at the mid

The backtest now charges commission and no slippage. The operator fills
spreads at the combo mid on entry and on exit, so the 25%-of-spread charge
was a cost the account does not pay. Both v4 tabs were re-priced. Net P&L
on BacktestResults moved from −$50.4k to −$7.1k. Gross is unchanged, so the
book still shows no edge before costs.

_Operator decision 2026-09-24 · `config/backtest.yml`
`slippage_frac_of_spread` 0.25 → 0, commission stays $0.65 · `--redo
--cache-only`, signals 2024-01-10 to 2026-09-23 · before:
`_snapshot-*-pre-commission-only-20260924.csv` in `backtests/to_evaluate/`._

### The re-run

Final tabs, after the 32 orphan rows below were deleted. "Before" is the
pre-change snapshot restricted to the rows still on the tab.

| Tab | Measure | Before (0.25) | After (commission only) |
|---|---|---|---|
| BacktestResults | Priced rows | 970 | 972 |
| BacktestResults | Net P&L | −$50,373 | −$7,137 |
| BacktestResults | Total cost | $51,410 | $7,214 |
| BacktestResults | Gross P&L | +$1,037 | +$77 |
| BacktestResults | Win rate | 47.9% | 49.6% |
| BacktestProxy | Priced rows | 697 | 697 |
| BacktestProxy | Net P&L | −$50,998 | −$14,955 |
| BacktestProxy | Total cost | $42,530 | $6,487 |
| BacktestProxy | Gross P&L | −$8,468 | −$8,468 |

On the 970 BacktestResults rows that match by identity key, gross moved on
one row. GLD 2026-08-25 held one day longer because its cache gained a day.
The rest of the gross change is two GLD rows that moved over from the proxy.
A commission-only row costs $2.60 at the median and $122.20 at most (HYG, 47
contracts).

### Why the change is not tuning

The [cost_sensitivity](pre-registrations/f2_management/cost_sensitivity.md)
anti-tuning rule bars a cost level chosen to make the edge survive. This one
rests on the operator's order practice, not on a result. It was still made
after the −$50.2k was seen, and the registration says so. The 25% point stays
in the sweep. The registration is still a DRAFT.

Not measured: mid orders that never fill, and the gap between the EOD mid and
the fill-time mid. Flex records the fill price, not the quote.

### 32 orphan rows deleted

- **32 orphan rows, 3 on BacktestResults and 29 on BacktestProxy.** No play on
  AnalysisClaude matched them, so no `--redo` could reach them. They were
  uncosted or on the old cost basis, and studies loaded them. The operator
  deleted them 2026-09-24. Both tabs now have 0 orphans and 0 duplicate keys.
  Copies are in `_snapshot-*-pre-orphan-delete-20260924.csv`.
- **BacktestResults.** IBIT with `signal_date = "bot"`, and EEM and COIN
  2025-07-29, `cost_basis = full`, written 2026-08-21.
- **The "bot" row was damaged on the Sheet, not written that way.** Another
  session's `--redo` wrote it as IBIT 2025-07-16. Its first 47 columns still
  matched that row. Its last six (`pct_stale_days` to `path_data_end`) came
  from a different row. No code in the repo writes "bot".

  | Cell | As the run wrote it | On the Sheet |
  |---|---|---|
  | `signal_date` | 2025-07-16 | bot |
  | `cost_total` | $36.60 | $450.80 |
  | `cost_basis` | full | no_spread_exit |
  | `path_data_end` | 2025-08-29 | 2026-09-16 |
  | Last six columns from | IBIT 2025-07-16 | LQD 2026-07-13 |
  | Time | written 12:52 | damaged before the 13:06 re-run |

  The pattern matches the 2026-09-23 partial-range sort in the Sheets UI,
  plus a typed cell.
- **The rest of the tab is clean.** The 13:06 `--redo` rewrote every other
  row. The final tab matches that run's output cell for cell on 972 rows. The
  "bot" row survived only because no `--redo` date range covers an
  unparseable date.
- **BacktestProxy.** All 29 are `no_history` rows from 2026-08-21 to 08-27.
  They sit on 2024-09-16, 2025-07-29, 2025-09-10 and 2025-09-18. Three of
  those are the known double-analysis dates, so those rows most likely
  backtest the discarded run's plays. 2025-07-29 is not on that list, and why
  its rows orphaned is unexplained. 7 of the 29 carry a realized P&L.
- **No row was lost.** A first reading said the re-run dropped 24 proxy rows
  on those dates. It did not: all 24 were rewritten at 13:06.
- **A second proxy `--redo` ran at the same time,** from another session,
  12:53, without `--cache-only`. Its rows do not appear on the tab, and the
  tab has no duplicate keys.

---

## 2026-09-24 (earlier) — backtest pricing — a junk quote is no longer a price, a mark or a spread

A quote with no bid, or wider than twice the legacy Cboe width limit, is now
JUNK. The backtest no longer charges slippage on its spread, marks a day at its
mid, or fills a bought leg at its ask. It ships in the working tree,
uncommitted; no stored row and no Sheets tab changed. Total cost on the local
re-run fell from $226k to $51k, and gross P&L fell to about zero.

_Local re-run, `--cache-only`, `sheet_tab: null` · signals 2024-01-01 to
2026-09-23 · before: `backtests/results.csv`, 1,020 rows (full-tab `--redo`
of 2026-09-24, copied aside as `results_pre-junkquote_20260924.csv`) · after:
993 rows · 985 rows match on (date, ticker, play, structure)._

### The rule

Two operator rulings, both 2026-09-24. A quote is junk when `bid <= 0`, or
`ask − bid > mid`, or `ask − bid > 2 × W(bid)`. W is the legacy Cboe maximum
bid/ask differential that market makers once had to quote inside (Cboe Rule 8.7
bid/ask differentials); the table is in the reference linked below. **The 2×
multiplier is a judgement call, not from the source**: the old limit bound a
live quote, and an end-of-day snapshot is looser. The mid test stays because it
catches tiny quotes the width test misses, such as `0.02 × 0.07`. One
predicate, `simulate._is_junk_quote`, feeds every consumer. The full table is in
[backtest-reference](../docs/backtest-reference.md#notes).

- **Cost.** A junk leg-side pays commission only. `cost_basis` reads
  `no_spread_<side>`.
- **Marks.** A junk day marks at its `Latest` when the contract traded that
  day. Otherwise the last good mark is carried and tagged `barchart_stale`.
- **B5.** When a junk quote has no bid, the carried mark is capped at
  `_zero_bid_mark` (`ask/2`, or 0). A dead contract is never carried at an
  older, higher mark.
- **Entry.** A sold leg into no bid fills at 0. A traded contract fills at its
  print. A sold leg with a bid fills at the bid. A bought leg with no trade is
  refused as `junk_entry_quote`.

### The HYG row that exposed it

HYG 2024-05-15, bull put spread 76/74, 5 contracts, 0.21 credit. The 74P was
quoted `0.09 × 5.00` against a 0.11 trade. Its mid of 2.545 clamped the spread's
value to 0, so the profit target fired on day one.

| | Before | After |
|---|---|---|
| Exit | profit_target, day 1 | profit_target, day 20 |
| Gross P&L | $105.00 | $85.00 |
| `cost_total` | $1,250.50 | $23.00 |
| `cost_basis` | full | no_spread_entry_exit |
| Net P&L | −$1,145.50 | +$62.00 |

### The re-run

| Measure | Before | After |
|---|---|---|
| Rows | 1,020 | 993 |
| Gross P&L, all rows | +$10,536 | +$20,546 |
| Total cost, all rows | $226,303 | $131,784 |
| Gross P&L, 985 matched rows | +$13,709 | +$18,474 |
| Cost, 985 matched rows | $193,759 | $130,895 |
| Matched rows whose net P&L moved > $1 | — | 98 |
| Refused `junk_entry_quote` | — | 22 (12 HYG) |
| Rows with cost > 50% of \|gross\| | — | 135 |

| Ticker | Cost before | Cost after |
|---|---|---|
| HYG | $62,876 | $14,040 |
| KRE | $10,592 | $3,852 |
| EWZ | $9,043 | $2,428 |
| XLE | $8,714 | $2,748 |
| EEM | $4,654 | $924 |
| MU | $6,592 | $6,516 |
| SMH | $6,498 | $6,565 |
| NVDA | $6,074 | $6,074 |

Of the 35 rows that left, 22 are junk refusals. The rest are cache state, not
this rule: GLD and MU contracts whose cached history no longer reaches the
signal date on a `--cache-only` run. The 8 new rows are the same effect.

### The width line, added the same day

The first line (`spread > mid` alone) left quotes like HYG 2024-04-12's 76P,
`1.88 × 5.00` against a 1.91 trade, as clean. Its mid fired the profit target
on day one and it paid $1,872 of slippage. The width line makes it junk.

| Measure | Mid line only | Mid + width line |
|---|---|---|
| Rows | 993 | 970 |
| Gross P&L | +$20,546 | +$1,037 |
| Total cost | $131,784 | $51,410 |
| HYG cost | $14,040 | $4,684 |
| Rows with cost > 50% of \|gross\| | 135 | 60 |
| Refused `junk_entry_quote` | 22 | 48 (16 HYG) |
| HYG 2024-04-12: exit | profit_target, day 1 | dollar_stop, day 44 |
| HYG 2024-04-12: cost, net | $1,903, −$175 | $31, −$499 |

Gross P&L fell because the mids of wide quotes had been booking profit
targets. What cost remains sits mostly on large counts of cheap spreads (22 to
33 contracts) against quotes inside the line.

Research mirrors now diverge from production; none was changed. They are
filed in [next-steps §2.11](next-steps.md#s2-11).

---

## 2026-09-23 (evening) — mtm_curve — the book equity curve was gross of costs, the rows were net

The mark-to-market curve now charges each row's `cost_total`, so it reconciles
against that row's own `realized_pnl_abs` again. Nothing ships: no study ran and
no stored row changed. `tests/test_mtm_curve.py` still fails on the export, for
a second and separate defect described below.

_Era v4 · exports as pulled 2026-09-23 · 669 result rows, 1,396 pooled
positions · no study run._

### The defect in the curve

`simulate.py::_apply_costs` charges commission and slippage once and subtracts
the total from `realized_pnl_abs` and `realized_pnl_pct`. It leaves
`daily_pnl_csv` gross, and says so. `lib/mtm_curve.py` builds the whole book
equity curve from `daily_pnl_csv`, and gate G-MTM compares that curve's exit
mark against `realized_pnl_abs`. Since the cost model was turned on
(2026-09-22, commit 8831f96) the two are on different bases, so G-MTM read every
transaction cost as a disagreement.

| Row | Marked exit | Booked | Gap | Row's `cost_total` |
|---|---|---|---|---|
| INTC 2026-06-12 bull put spread | 360.00 | 344.40 | 15.60 | 15.60 |
| MU 2026-07-07 bear put spread | -1,148.50 | -1,403.60 | 255.10 | 255.10 |

Both rows hold one contract, and each gap is that row's own round-trip charge to
the cent. All 71 mismatches on the export have this one cause.

### The fix

`book_curves` subtracts `row_cost(rec)` from a position's exit mark under target
`stored_row`. The charge lands on the exit session, because that is the only day
the row dates it: `_apply_costs` records one figure and no entry-side or
exit-side split. Under target `position_dollars` the marks stay gross, since
that target is a replay through the frozen harness, which predates the cost
model. A row whose `cost_total` is blank is charged nothing, so every figure
recorded before 2026-09-22 comes back unchanged. `BookCurves.n_cost_netted`
counts the positions that were charged.

### The second defect: the export's cost columns are corrupt

The last four columns of `BacktestResults` did not survive the write to the tab.
On the export, the 71 rows written 2026-09-22 carry a blank `pct_stale_days`,
`cost_total`, `cost_basis` and `exit_fill`, and 16 of those values landed on
unrelated rows, including rows written weeks earlier. The local run files
`backtests/results_20260922_*.csv` hold the right values: on all 80 of their
rows `cost_total` equals the marked exit minus the booked dollars, to the cent.

| Check on the export | Rows |
|---|---|
| Netted of costs | 71 |
| Of those, `cost_total` blank | 55 |
| Of those, carrying another row's `cost_total` | 16 |
| Older rows carrying a spilled `cost_total` | 54 |

A repaired copy of the export, rebuilt from the local run files, reconciles
1,396 of 1,396 positions at $0.00 and leaves the realized curve byte-identical
to `account_sim.equity_curve`. That is the evidence the code fix is right. The
repair was not installed: the tab itself still holds the corrupt copy, so the
next `export_tabs.py` run would undo it.

### What happens next

One queue item, not yet written into [`next-steps.md`](next-steps.md) because
another session holds that file. Repair the `BacktestResults` tab's last four
columns from the local run files, then re-export. Until that lands,
`hedge_portfolio` and `tests/test_mtm_curve.py` fail G-MTM, which is the right
answer on a book whose rows contradict themselves.

---

## 2026-09-23 (later) — backtest engine — a simulated path may no longer outlive its price data

No exit rule fires on a day after the last real quote. Nothing ships beyond the
code change: no stored row was re-priced, no study ran, and the two new columns
are blank on every row already written.

_Era v4 · code change only, no export re-pulled · the defect was measured on the
local run of 24 backfilled June–July 2026 dates recorded
[above](#2026-09-23--junejuly-2026-backfill--24-dates-analysed-on-v4-11-priced-the-rest-pending)._

**The defect.** `path_cap_days` is 120 and `_snap_asof` carries the last scrape
forward over every later day, so a July signal simulated into November against
frozen marks. The engine had no guard for it. Two kinds of row came out of that:
a rule fired on a session that had not happened, or a play with no exit was
stamped `cap_open` at the cap as if the path had genuinely run that long.

| In the local run of 24 dates | Count |
|---|---|
| Simulated | 154 |
| Genuine outcome | 133 |
| `cap_open` on carried marks | 11 |
| A rule fired after the last real quote | 10 |

**The rule.** The last real quote, for a position, is the earliest of its legs'
last real sessions. A spread is only as live as its deadest leg: once one leg
stops printing, the net mark is part frozen. Interior gaps truncate nothing —
this is each leg's last session, not a run of consecutive ones.

**The behaviour.** A position still open when the data stops is marked there and
kept. `days_held` and the realized P&L are that day's, and `exit_reason` is
`cap_open` rather than `expired`, because the path did not reach expiry. The
marked path, MFE/MAE and `pnl_at_cap_pct` still span the whole grid, so a play
that exits before its data ends is unchanged.

**The columns.** `path_status` and `path_data_end`, appended at the end of both
backtest tabs. `path_data_end` is the ISO date of that last real quote.
Definitions: [backtest-reference](../docs/backtest-reference.md).

| `path_status` | The exit |
|---|---|
| `complete` | fired on a day every leg quoted for itself |
| `carried` | fired on a day a leg's mark was carried into, which an interior gap can still produce |
| `open_at_data_end` | never fired; the data stopped first |

**Stored rows written before today may hold a fabricated exit, and nothing on
them says so.** Both columns are blank there, and blank means unknown rather
than clean. The known population is the June–July 2026 run in the table above:
11 rows stamped `cap_open` on carried marks and 10 whose rule fired after the
last quote. Two of those rows reached `BacktestResults` — `GLW` on 2026-07-16
and `VLO` on 2026-07-30. No count is claimed for v3 or for earlier v4 dates,
because the defect was never measured there.

**Next.** [`next-steps.md`](next-steps.md) gains nothing new; the re-price
decision on the stored book already sits with the operator. The tab headers owe
the two columns before the next append, which is
`python3 scripts/align_tab_headers.py`.

## 2026-09-23 — backtest pricing — Black-Scholes is abolished; four entry refusals, real per-leg greeks

The backtest no longer produces a model price, delta or IV. Nothing ships
beyond that code change: no stored row was re-priced and no study ran. The
operator ruled it; the proxy's `bs` tier was already off, and now the main
backtest's is gone too.

_Uncommitted working tree, `main`, 2026-09-23. Reference:
[No model prices](../docs/backtest-reference.md#no-model-prices-2026-09-23)._

### The rule

| Case | Behaviour |
|---|---|
| Entry leg with no real price | Refused, `no_real_entry_price` |
| Path day with no new quote | Last real mark carried, tagged stale past 5 days |
| `bs` in a source list, or `proxy.bs_fallback: true` | The run refuses to start |

### Two defects it exposed

**A credit priced to a debit was sized on a fake premium.** TLT 2025-04-04, a
90/85 bull put spread, filled the 85P at a stale 1.61 Open. Its quote was
0.68/0.81. The entry netted a 0.35 debit, and the sizer bought 38 contracts
against about $500 of risk each. The old docstring called this case
conservative. It was the opposite. It is now refused as `credit_priced_to_debit`.

**One corrupt cache file set a whole position's underlying and greeks.**
`META_20270115_630.00P.csv` held another contract's history: `Price~` near $155
against about $640 on every sibling. Non-anchor legs took a Black-Scholes delta
at the anchor's IV and underlying, so that one file reached every leg. The file
is quarantined in `backtests/option_history_cache/_quarantine/`, never deleted.

### What changed in code

| Change | Where |
|---|---|
| `bs` pricer, `_bs_delta`, yfinance underlying fetch deleted | `scripts/backtest/helpers.py`, `simulate.py` |
| Proxy `bs_options_hist` rung deleted | `scripts/backtest/proxy.py` |
| `credit_priced_to_debit` and `non_monotonic_entry_quote` refusals added | `simulate.py`, `classify.CREDIT_STRUCTURES` |
| Each leg's `delta`, `iv`, `Price~` read from its own row | `simulate.py` |
| `entry_underlying` = median of the legs' `Price~` | `simulate.py` |
| A fetch more than 25% off its same-expiry siblings is refused | `shared/history.py` |

The underlying OHLC cache was considered for `entry_underlying` and the guard,
and rejected. It is split-adjusted while `Price~` is as-traded, so it disagrees
with 2,112 good option files by exact split multiples.

### Dry-run check

| Date | Result |
|---|---|
| 2025-04-04 | TLT refused as `credit_priced_to_debit`; XLI refused as `no_real_entry_price` |
| 2026-07-16 | META unpriced: its 630P anchor is quarantined; 7 plays priced with real greeks |

Both runs were cache-only against a local-only config.

### What is unresolved

- The stored book was priced under the old rules. `bs`-tagged rows and the TLT
  row stay in the tabs until a dated `--redo`. That is an operator decision.
- A research sensitivity tier still prices by Black-Scholes:
  `overlay_campaign.ModelPrices` (`ladder_overlay`'s `[MODEL]` arm). Its pricer
  now lives in that module; production cannot import it.
- The live META 630P history has not been re-scraped. The next non-cache-only
  run will fetch it, and the sibling guard will judge it.

## 2026-09-23 — June–July 2026 backfill — 24 dates analysed on v4, 11 priced, the rest pending

June and July 2026 are now partly on the v4 book. Roughly half the sessions
carry analysis rows, and under half of those carry result rows. Nothing ships,
and no study ran. The operator ruled these dates admissible as v4 evidence, so
the population behind every study export has moved and the suite is owed a
re-run.

_Era v4 · exports re-pulled 2026-09-23 · caches pushed as
`research-caches-20260923-1202.tar.gz`._

| Export after the run | Rows | Dates |
|---|---|---|
| `AnalysisClaude` | 3,084 | 263 |
| `BacktestResults` | 669 | 204 |
| `BacktestProxy` (unchanged) | 1,665 | 208 |

**The operator ruling.** A backfilled session outside `[2024-01, 2026-05]`
counts as v4 evidence, because no shipped rule was fitted on it. That is the
exception to the "backfill dates do not count" line in
[next-steps.md](next-steps.md#s2-2) §2.2, and June–July 2026 are the first
dates it admits.

**What ran.**

| Step | Result |
|---|---|
| Sessions in scope | 43 (June–July, minus Juneteenth and the 3 July holiday) |
| Analysed into `AnalysisClaude` | 24 dates, 279 rows, one run per date |
| Refused as already analysed | 0 |
| Failed | 0 |
| Not attempted | 18, listed in `backtests/pending_analyze_dates_2026-06_07.txt` |
| Backtested | 11 dates, 71 rows |
| Proxy rows written | 0, see the frozen-tail finding below |

The 18 pending dates were stopped by the operator part-way through, to save
tokens, not by any guard. Enrichment for them is done except for four dates
noted below, so a resume is a plain loop over that file.

**The model-recall caveat is resolved for these dates.** The engine's default
model is `claude-opus-5` (`scripts/analysis_pipeline/config.py`), whose
knowledge cutoff is May 2026. A June or July 2026 session sits after that, so
the analysis cannot be recall of that day's tape, unlike the 2024–2025
backfill. Neither this repo nor the `claude-api` skill documents the cutoff;
it is stated by the running agent's own session context, which is the weakest
part of this claim.

**A backtest of a play that has not expired prices its tail from a frozen
quote.** This is the reason no proxy row was written and only 11 of 24 dates
were priced. `path_cap_days` is 120, so a July signal can run to November, and
`_snap_asof` carries the last real quote forward over every grid day past the
last scrape. The path then reaches its cap and the row is stamped `cap_open`
or `expired`, and a time exit can fire on a day that has not happened yet. A
local-only run of all 24 dates showed the size of it.

| Rows in the local run | Count |
|---|---|
| Simulated | 154 of 255 plays, the rest unpriced or vetoed |
| Genuine outcome, path closed on or before 2026-09-21 | 133 |
| Path runs past it: `cap_open` on carried marks | 11 |
| Path runs past it: a rule fired on a day after the last quote | 10 |

Only the 11 dates whose rows were all genuine were written to the tab. Two
rows still slipped in, because re-scraping priced two contracts that had timed
out in the local run: `GLW` on 2026-07-16 and `VLO` on 2026-07-30, both
`cap_open` at day 86, both keyed `created_datetime` 2026-09-22. They are not
final outcomes and the operator should decide whether to delete them; the
already-backtested guard means a later re-price needs `--redo`.

Two further columns read wrong on any row whose path outlives the data.
`pct_stale_days` counts the frozen tail as stale days, so it is inflated even
when the exit fired early, and `pnl_at_cap_pct` marks the cap at a carried
quote. Proxy rows have the same defect: every one of the 30 evaluated locally
sits on an expiry past the last quote, which is why none was written.

**Data gaps found on the way.**

| Gap | Dates |
|---|---|
| No flow on Drive at all, no date folder | 2026-06-08 |
| Historical scrape capped at 501 rows per file | 2026-06-01 to 2026-06-05 |
| Counterpart-IV and price-catalyst still unfilled after network errors | 06-25, 06-26, 06-29, 06-30 |

Barchart never refused a login, even with the SPY backfill chain holding the
same session. What failed was the network: 145 contract feeds timed out during
the backtest scrape, and an overnight run hit repeated SSL and read timeouts.

The 71 result rows were priced by the code at `f007ac2`. The working tree has
since abolished the Black-Scholes tier, so a re-price of these dates under the
new engine will not reproduce them.

**One test now fails, and these rows are what exposed it.**
`tests/test_mtm_curve.py::test_realized_basis_is_byte_identical_to_account_sim_equity_curve`
reports one mismatch, `GLW` on 2026-07-29, of $15.60. That is the cost charge
on the row: the research mark-to-market curve recomputes a gross path, while
the stored row is now net of commission and slippage. These are the first
cost-bearing rows in the export, so the gap had nothing to bite on before. The
fix belongs with the cost-model work, not here.

**Next.** [next-steps.md](next-steps.md#s2-2) §2.2 records the ruling. The
suite re-run is owed on the moved population, and the 18 pending dates plus
the unpriced plays stay open.

## 2026-09-22 (evening) — journal repair lands, cost model on, five queue items decided

A refused Barchart login no longer kills a journal run, the forked
TradeJournal is merged into one 156-row book, and the backtest cost model is
switched on. The operator also resolved five items in
[next-steps.md](next-steps.md#s0). No study ran; these are commits landing on
`main` plus the operator's own decisions.

_Commits `5c4c818` through `8831f96`, `main`, 2026-09-22. Reprice census:
`backtests/study_output/reprice-targets-2026-09-22.csv`._

**Journal: a Barchart login refusal degrades instead of failing.**
`BarchartAuthError` closes the browser and lets the run continue without
greeks (`5c4c818`). CI now chains three retry jobs on fresh runners,
degrading only the journal's last attempt; scrapers retry the same way with
no degrade path (`36d3a61`).

**TradeJournal: the forked halves are merged.** After 2026-09-08, the local
`trades.csv` held 149 rows (07-01 to 09-08) and Drive's copy held 30 (09-09
to 09-17), while the tab carried their 179-row union. Dedup keyed on the pull
filename rather than the fill ids, so the 08-14, 08-28 and 09-14 sessions
were written two to five times over (`9aeb036`).

`python3 -m scripts.journal repair --merge-drive --apply` (`aa30549`) merged
the two files and re-derived the pre-fix CLOSE rows from their original
pulls. Zero rows were refused, and the tab, the local CSV and Drive now all
hold 156 rows.

| What the repair did | Count |
|---|---|
| Duplicate rows collapsed | 23 (11 local, 12 Drive) |
| Pre-fix CLOSE rows re-derived | 10 |

| Row | Tier before | Tier after |
|---|---|---|
| GLD bull call | VETO | B |
| IWM bear put | B | C |
| GLD 445C buy-back | SUBSTITUTED B | NONE |
| NVDA 245C buy-back | SUBSTITUTED B | OVERLAY |
| TSM 470C buy-back | SUBSTITUTED B | OVERLAY |

`journal/open_book.csv` is forked the same way, 84 local rows against 171 on
Drive, and is not repaired yet.

**Operator decisions on the queue.** Five [next-steps.md](next-steps.md#s0)
items were resolved or given a plan; none ships without more work.

| §0 item | Decision |
|---|---|
| 6, 7, 9 | Re-price all of them; stale or wrong-strike rows should not sit on the sheet |
| 8 | Cost model on, $0.65 a contract plus 25% of the quoted spread, per leg per side (`8831f96`); a whole-book `--redo` follows the SPY backfill and a Barchart refetch |
| 5 | Draft [`ruin_bound`](pre-registrations/f4_deployment/ruin_bound.md): pick a cap cell and a guardrail by a rule fixed before any run |
| 10, 11 | Bear debits stay in use; the fast-exit draft is the study, not a config change |

**The re-price plan, not yet run.** `reprice_targets.py` (`0a68bdf`) is the
offline census behind items 6, 7 and 9. The stored book has not moved; the
script only writes the `--redo` plan.

| Category | Rows |
|---|---|
| Pre-fill | 17 (up from the earlier count of 14) |
| Wrong-strike | 6 |
| `Open`-fill | 49 |
| Total | 67 rows over 61 dates |
| Need a fresh Barchart fetch first | 6 |

The same commit makes a one-sided entry-day quote fill on its own side ahead
of the `Open` print, mirrored in `bear_rewrap`'s own write-time basis; no
stored row reconstructs differently under either change. A dated
`scripts.backtest --redo` now also deletes a proxy row whose play has since
priced on `BacktestResults`, so a re-price cannot leave a play on both tabs
(`ec9d515`).

**Stage 2 stays unbuilt.** The live-vs-tier P&L tally still has no
pre-registration.

| Tier | Closes |
|---|---|
| A | 2 |
| B | 4 |
| C | 14 |
| VETO | 2 |
| Total | 22 over 12 signal dates |

That is below the 25-date and 30-to-50-row floors in
[§2.5](next-steps.md#s2-5).

**Next.** [`next-steps.md`](next-steps.md) §0's re-price items stay open
pending the SPY backfill and the Barchart refetch. The capital item waits on
the operator's `ruin_bound` blanks, and the bear items wait on the
`bear_fast_exit` registration.

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
