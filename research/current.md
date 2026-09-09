# Backtest tuning — current

The recent end of the log. Dated entries run below the state of play. Older
work is in [`archive/`](archive/), indexed by the [README](README.md).
Conventions for this folder: terms in [`glossary.md`](glossary.md), study-local
labels in [`arm-index.md`](arm-index.md), house style in
[`writing-guide.md`](writing-guide.md).

## State of play

Population refreshed 2026-09-08; every verdict below was read on 2026-09-04.
Nothing new ships. The whole suite was re-run on the first book that carries
2026 signal dates, and no headline verdict moved. Two studies produced a
first-time candidate and both are held, because the new dates are a correlated
backfill window rather than a fresh one.

This block is the authoritative summary of where the research stands.
[`overview.md`](overview.md) restates parts of it, and [`next-steps.md`](next-steps.md)
§0 points here. If either disagrees with this block, this block wins.

### The population

| Field | Value |
|---|---|
| Era | `v4`, the 193-date backfilled book |
| Exports | all three re-pulled 2026-09-08; deduplicated, and every result row joins its play |
| Real results | 598 over 193 dates |
| Proxy rows | 1,665 |
| Analysis rows | 2,677 over 228 dates, one analysis run per date |
| Pooled study book | 1,374 rows over 208 dates, being 598 real plus 776 tweak |
| Signal dates | 2024-01-10 → 2026-05-07 |
| 2026 signal dates | 29 carry pooled rows, 26 of them real; 2026-01-06 to 2026-05-07, 161 pooled rows |

Every verdict summarised below was read on the 166-date book of 2026-09-04. The
42 dates of queues C, D and E landed on 2026-09-08 and NO study has run since,
so the numbers in the tables below are the last recorded ones, not this book's
([the queue entry](archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md#2026-09-08-fifth--queues-c-d-and-e-are-run-42-dates-added-and-the-2026-column-now-samples-march)).

This is the first book with 2026 signal dates, so every `ex_2026_*` cut and
every "positive in every year" clause runs for the first time. It is also the
first that samples the March 2026 drawdown, on five priced sessions. Queue b,
the neutral-date campaign, and queues C, D and E, which finished its selection,
are all complete and closed.

### Where the 2026 column bit

Every study still prints the verdict word it printed on the 140-date book. What
moved is underneath the verdict: the per-year clause now has a 2026 column, that
column is negative in most cells, and it is the first look out of sample in time
that any rule has had on `v4`. [meanR](glossary.md#meanr) and
[CI](glossary.md#ci) are defined in the glossary. Arm labels are study-local, so
each is given with its study.

| Study | Arm or cut | What changed | Record |
|---|---|---|---|
| `next_day_move` | [ARM R](arm-index.md#next_day_move), bear-debit | lost its `**` on all three cuts | [record](study-results/f2_management/next_day_move.md) |
| `exit_from_text` | [E2](arm-index.md#exit_from_text), pooled | the pooled candidate is gone | [record](study-results/f2_management/exit_from_text.md) |
| `portfolio_delta` | [ARM B](arm-index.md#portfolio_delta) ceiling 1.50 | dropped out, so only ceiling 1.00 clears | [record](study-results/f4_deployment/portfolio_delta.md) |
| `emission_timing` | [ARM P](arm-index.md#emission_timing) sub-cuts | two of them fail | [record](study-results/f1_selection/emission_timing.md) |
| `bear_rewrap` | `long_diag` year criterion | 5/5 fell to 4/5, and in the same run its portfolio checks were `MET` for the first time | [record](study-results/f3_structure/bear_rewrap.md) |
| bear-debit `be_after` | rollback census | re-fired on 199 arming rows over 110 dates, 2026 −0.0431 | [plan](pre-registrations/f2_management/rollback_triggers.md) |

`be_after` was already reverted on 2026-08-24, so its census re-firing asks for
nothing. That census has now given three answers on three runs: a 60-row floor
on a backfilling book is not a decision procedure.

### Two firsts that hold rather than ship

Both sit in the correlated window, so neither promotes a rule.

| Study | Arm | What it prints |
|---|---|---|
| `bear_arm` | [B2](arm-index.md#bear_arm) exit fix | criteria `MET` for the first time: `sl .50 (tighter)` Δ=+0.039, CI [+0.004, +0.071], [LOO](glossary.md#loo) min +0.035, and the bear-specificity control holds |
| `financed_spread` | [F3](arm-index.md#financed_spread) off1 | `RE-WRAP` at 6/7, failing only the anti-re-wrap E3 correlation; its fixed-contracts control spans zero |

### The hedge programme

The trigger studies are closed and the instrument is unchanged. The gap-up
prohibition in [§4](../docs/deployment-rules.md#s4) was accepted on 2026-09-06
and rests on `hedge_timing`'s paired-[R](glossary.md#r) arms alone. The sleeve
stays, so finding an indicator for when to open a hedge is now an open queue
item with nothing in it ([`next-steps.md`](next-steps.md) §2.10).

The spine is [`f5_hedging/README.md`](../scripts/backtest_study/f5_hedging/README.md):
the four studies grouped by the question each answers, what each one last
printed, why each stopped, and what would unblock it.

### `concurrency_correlation` is closed

No arm clears [X2 or X3](arm-index.md#concurrency_correlation) in either era, so
no arm is or can be `ADOPT`-eligible. [X4](arm-index.md#concurrency_correlation),
the era-stability criterion, was settled by hand: `NOISE` on both eras. The `v3` companion ran on 795 rows over
118 dates, powered 8 of 13 arms, and printed the same sentence. 4 of the 8 arms
powered in both eras flip sign, so the verdict is era-stable while the per-arm
gains are not. The thread is closed, and the run is in the
[record](study-results/f4_deployment/concurrency_correlation.md).

### Rollback triggers

Each trigger is checked at its gate, with numbers. A trigger that printed
nothing has not been checked, and that is not the same as "not met". The
[plan](pre-registrations/f2_management/rollback_triggers.md) holds each floor.

| Trigger | On this export |
|---|---|
| LVOL tef-null | `STAYS GATED` on 73 affected dates, median −0.033. The 2026-08-24 `CLEARED` did not survive two exports, so the operator's hold was right |
| BEAR_HE trail | `UNDERPOWERED` at 1 date of 25 |
| credit sl-none | 0 of 15, and unreachable by backfill because the window starts after 2026-07-13 |

### Known defects in this export, not repaired

- **The exports are refreshed and deduplicated.** All three were re-pulled on
  2026-09-08 after queues C, D and E finished. `BacktestResults` holds 598 rows
  over 193 dates, and no identity key repeats on it or on `BacktestProxy`. Tab
  and export agree on each. The suite has NOT been re-run on them.
  Details: [`next-steps.md`](next-steps.md) §0.
- **The rows did not all run under one code version.** The six queue-D dates
  retried on 2026-09-08 ran after merge `3e5c2dc`, so they carry the cost
  columns and the pre-entry grid fix; every other row predates it. Split them on
  `cost_total` or `pct_stale_days` being non-blank — NOT on `cost_basis`, which
  is blank everywhere while both cost knobs are 0.
- **Every `BacktestProxy` row is blank in `pct_stale_days`, `cost_total` and
  `cost_basis`.** `proxy.py::_evaluate` never copies them onto the row. Open, one
  line, [`next-steps.md`](next-steps.md) §2.11.
- **The 5 surviving 2025-09-18 rows carry a `market_regime` from a LATER
  analysis run than their own play.** The backtest stamps each play with the
  newest `MARKET` row on its date, and 2025-09-18 was analysed twice, so those
  rows read `BULL + C-VOL` where the run that proposed them read `RANGE +
  L-VOL`. That follows from keeping the newer copy, and is not repaired. Any
  regime cut on 2025-09-18 sees the later label.
- **RESOLVED.** The 12 `BacktestResults` rows whose play no longer existed were
  dropped on 2026-09-07, so no result row joins the wrong play any more. Record:
  [2026-09-07 later](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-07-later--the-12-stale-backtest-rows-are-dropped-and-the-backtest-can-no-longer-double-a-row).
- **Two rows on 2025-07-29 still cannot join, and are KEPT on purpose.** `COIN`
  and `EEM` have no `AnalysisClaude` row, from a cause unrelated to the repair:
  the analysis rows that proposed them went missing separately, so the backtest
  row is now the only surviving record that those plays were ever proposed. They
  fail the join outright rather than landing on another play, which studies
  already count as unjoined. Dropping them would destroy evidence to tidy a
  count.
- 2025-12-26 produced no analysis rows.
- `text_features` [ARM B](arm-index.md#text_features) label coverage fell to
  89.3%, because the label cache does not cover the new rows.

Detail is in the 2026-09-04 entry below and in
[`next-steps.md`](next-steps.md) §0.

### The open queue

Nothing new is registered. The queue itself is
[`next-steps.md`](next-steps.md) §2.

- The v4 composition bridge and the rollback triggers wait on genuinely new
  dates. Those are the live analysis dates 2026-08-11 → 2026-09-01, which have
  no backtest rows until their options expire.
- `prompt_eval` ([§2.9](next-steps.md#s2-9)) is open but is not an edge search.
  It tests whether a prompt gives the same regime label on the same inputs,
  because the variance run traced the tier-mix swing to that label flipping.
  Nothing in the book says a prompt change moves P&L, so it waits behind §2.2.
- `operator_read` ([§2.5](next-steps.md#s2-5)) waits on the journal.

### Known traps carried forward

Each is a way to misread the data that has already caught someone once. None
blocks any work; each has its full entry in an archive volume.

- **`exit_basis` is era-scoped, not corrupt.** The column is unlabelled and
  scrambled on `v3` and earlier, and those exports are frozen
  ([archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md)).
  It is clean on `v4`, re-measured 2026-09-02 at 485/485 labelled and
  internally consistent. `BacktestProxy` carries it only for rows written after
  the 2026-09-02 writer fix.
- **Studies are era-scoped.** The bare export name does not name a population;
  `lib/era.py` is the single encoding (archive/15).
- **Arm labels are study-local.** Cite `emission_timing ARM P`, never a bare
  `ARM P` ([archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md),
  [`arm-index.md`](arm-index.md)).
- **`study_review --dry-run` overwrites** the review and digest artifacts
  (archive/17).
- **The `hedge_portfolio` registration describes the wrong stratum.** Its
  plan-time observations describe the `real` stratum, not the ratified book.
  The RATIFICATION that says so was folded out of `hedge-exposure-errata.md`
  into the registration itself on 2026-09-02, and now lives in
  [Population and basis](pre-registrations/f5_hedging/hedge_portfolio.md).
  The errata file is deleted; dated entries below keep its name as history.

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
  Archive 19 holds `hedge_concentration` GRADED, `concurrency_correlation`'s
  first run, the first book with 2026 dates, `exit_drawdown`'s registration
  and UNDERPOWERED run, the overview/glossary rewrite, the gap-up hedge
  prohibition, the SPY and stale-row duplicate repairs with their two new
  write guards, the 40 unrun pre-registered dates, the robustness review, and
  the hedge-programme criteria consolidation. Archive 20 holds the hedge
  studies' rename, the robustness fold landing on main, the hedge-programme
  plan's deletion into `f5_hedging/README.md`, `exit_drawdown`'s ARM P ACK and
  errata fold, queues C/D/E, the sleeve-sizing fold onto
  `lib/hedge_criteria.sleeve_pick`, and the far-call fetch that restored 178
  lost cache files while `hedge_structure` stayed blocked at R2.

---

## 2026-09-09 — journal — the July to mid-August fills are journalled; the live walk-forward has 55 mapped rows over 20 signal dates

**The journal is the live walk-forward's Stage 1 collector, and it now covers
every session since analysis coverage began.** Nothing ships. The 26 sessions
from 2026-07-01 to 2026-08-13 were never journalled, because the daily loop
started on 2026-08-14. They were replayed offline today from the Flex exports in
`portfolio/input/` through the journal's own parse, reconcile and trade-writer
steps, and 107 rows were appended to `journal/trades.csv` and the TradeJournal
tab. Dedup is on the broker execution id, so re-running appends nothing.

_Sources: `trades_2025.csv`, `trades_2026.csv`, `trades_ytd_fetched.csv`, netted
together. Sessions before 2026-08-11 matched against `v3_AnalysisClaude` only;
2026-08-11 onward against `AnalysisClaude`. No greek enrichment, so
`delta_source` is unavailable on the replayed rows and tier §3 is unverified on 3
of them._

**Why the split by tab.** The v4 tab holds re-runs back to 2024 that were produced
after August. A July fill matched against one of those would be matched to an
analysis the operator never saw. The v3 tab is what was live until 2026-08-10.

**The strike and expiry point.** The operator often opens a different strike or
expiry from the emitted play. The matcher already handles that: a same-family
structure with other strikes is STRUCTURE, a naked leg where a spread was emitted
is SUBSTITUTED, and expiry is not part of the match at all. Strike differences
are recorded in `notes`, never used to reject a match.

| Journal after the replay | Count |
|---|---|
| Rows | 145 over 34 sessions, 2026-07-01 to 2026-09-04 |
| Mapped rows (EXACT, STRUCTURE, CORE, SUBSTITUTED) | 55 over 20 signal dates |
| Mapped opens / closes | 32 / 22 |
| NONE | 67, of which 12 predate the first v3 analysis date 2026-07-08 |
| OVERLAY | 23 |

| Tier | Mapped rows | Opens | Closed with realized P&L | Realized $ |
|---|---|---|---|---|
| A | 3 | 3 | 0 | 0 |
| B | 21 | 11 | 9 | +626 |
| C | 29 | 16 | 13 | +388 |
| VETO | 2 | 2 | 0 | 0 |

**This decides nothing.** No tier-A position has closed, so the A > B > C question
cannot be posed. Stage 2, the live-vs-tier P&L reading, is not written; the old
stage1 caveat put its gate at 30 to 50 closed positions and the mapped book has
22 closes. The `operator_read` floor in §2.5 of 25 dates is at 20.

**What stays unmapped.** Most of the 67 NONE rows are short-dated MU options,
straddle-shaped mixed C/P verticals, and closes of positions opened before
coverage. None of those are the analysis's plays. One label reads oddly: a CRWV
short put is labelled `(overlay)` by structure but matched SUBSTITUTED, and the
two vocabularies should agree.

**Queue.** [`next-steps.md` §2.5](next-steps.md#s2-5) loses its "no recorded
movement" warning and gains the census. The replay script is a one-off in the
session scratchpad, not in the repo; if a second Flex gap appears, a `backfill`
command on `scripts.journal` is the right home for it.
