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

The queue itself is [`next-steps.md`](next-steps.md) §2. `ladder_overlay`,
registered 2026-09-10, ran on both eras and closed 2026-09-16 with every graded
cell `NULL`
([entry](#2026-09-16--ladder_overlay--nothing-ships-no-ladder-or-naked-put-cell-beats-the-plain-spread-on-v4-or-v3)).

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
- Pruned (dream rotation) 2026-09-09: the two 2026-09-09 journal entries,
  into [archive/21](archive/21-journal-replay-and-live-loop-fold.md). That
  volume holds the July–August fills replay (26 sessions from 2026-07-01 to
  2026-08-13 backfilled before the daily loop started 2026-08-14, first v3
  analysis date 2026-07-08, v3/v4 tab split at 2026-08-10) and the
  `scripts/live_loop/` retirement into `scripts/journal/lib/mapping.py`,
  superseding the 2026-08-12-dated `stage1_map_fills.py` snapshot.

---

## 2026-09-16 — ladder_overlay — nothing ships; no ladder or naked-put cell beats the plain spread on v4 or v3

Wrapping a bull call spread in a rolled short-call ladder does not beat running
the spread to the shipped [§5](../docs/deployment-rules.md#s5) exits, and
neither naked-put substitute does either. All ten graded cells print `NULL` on
v4, and on v3 the six powered cells print `NULL` and the four sell-at-entry
cells are `UNDERPOWERED`
([record](study-results/f3_structure/ladder_overlay.md)). The one confidence
interval clear of zero is on the wrong side: selling the call on the entry day
and rolling it costs about a quarter of an R against the plain spread.

_Era v4 · exports 2026-09-08 22:38 · 598 real / 1,665 proxy rows · 447
bull-call cores over 165 dates · report
`backtests/study_output/ladder_overlay-latest.txt` (run 2026-09-10 22:17, sha
8aed569, after the 11,551-contract scrape finished at 22:15 and the cache
snapshot was pushed at 22:16) · v3 companion run 2026-09-16, 242 cores over 89
dates, filed as `ladder_overlay-v3-2026-09-16.txt` · review 2026-09-10: two
analysts and the validator agreed on every number and every verdict._

**In production.** Nothing changes. The §5 debit exits stay and no overlay
enters the deploy card. The
[pre-registration](pre-registrations/f3_structure/ladder_overlay.md) allowed at
most a CANDIDATE queued for confirmation, and none appeared.

**Evidence.** [ΔR](glossary.md#paired-ci) is the cell's R minus the plain
spread's R on the same row, with a date-clustered
[CI95](glossary.md#ci95-date-clustered-bootstrap). Criteria are the
registration's eight; cell labels are in
[`arm-index.md`](arm-index.md#ladder_overlay).

| Cell (v4) | What it does | ΔR | CI95 | Dates | Criteria failed | Verdict |
|---|---|---|---|---|---|---|
| L-F4 | one call sold at entry, never rolled | −0.225 | [−0.477, +0.001] | 71 | 1, 2, 3, 4, 5, 7, 8 | NULL |
| L-T0 | sold at entry, rolled each slot | −0.255 | [−0.528, −0.011] | 71 | 1, 2, 3, 4, 5, 7, 8 | NULL |
| L-T0-TEF | L-T0 with no profit target | −0.310 | [−0.591, −0.053] | 71 | 1, 2, 3, 4, 5, 7, 8 | NULL |
| L-GAP | sold after a gap-up, rolled | +0.078 | [−0.012, +0.168] | 122 | 1, 4, 7 | NULL |
| L-RUN | sold after a sustained rise, rolled | +0.045 | [−0.048, +0.135] | 121 | 1, 4, 7 | NULL |
| L-GAP-TEF | L-GAP with no profit target | +0.102 | [−0.038, +0.234] | 122 | 1, 4, 7 | NULL |
| L-RUN-TEF | L-RUN with no profit target | +0.071 | [−0.074, +0.203] | 121 | 1, 4, 7 | NULL |
| N-CORE | short put at the long strike, in place of the core | −0.018 | [−0.181, +0.144] | 165 | 1, 2, 3, 4, 5, 7, 8 | NULL |
| N-ROLL | rolled short-dated put, in place of the core | −0.007 | [−0.157, +0.144] | 154 | 1, 2, 3, 4, 5, 7, 8 | NULL |

| Cell (v3) | ΔR | CI95 | Dates | Verdict |
|---|---|---|---|---|
| L-F4, L-T0, L-T0-TEF | — | — | 33 (41 rows) | UNDERPOWERED |
| L-GAP | −0.042 | [−0.245, +0.099] | 62 | NULL |
| L-RUN | −0.065 | [−0.199, +0.044] | 58 | NULL |
| L-GAP-TEF | +0.090 | [−0.141, +0.273] | 62 | NULL |
| L-RUN-TEF | +0.047 | [−0.122, +0.201] | 58 | NULL |
| N-CORE | +0.008 | [−0.228, +0.253] | 89 | NULL |
| N-ROLL | −0.274 | [−0.478, −0.073] | 69 | NULL |

**What the two eras agree on.** Selling the call on the entry day hurts. On v4
the three sell-at-entry cells are negative with the CI clear of zero for two of
them; on v3 the same cells are too thin to read. Waiting for a gap-up or a run
before selling is the only pattern that is positive on v4, and those four cells
clear the leave-one-date-out, window, pricing-tier and breach-stress criteria.
They still fail three: the CI includes zero, 2026 is a negative year, and
their P&L is positively correlated with the deployed book (E3 between +0.16 and
+0.38), which is the re-wrap pattern `financed_spread` printed before. A larger
book that pushed the CI clear of zero would therefore print RE-WRAP, not
CANDIDATE, and RE-WRAP closes the thread. On v3 the same four cells split two
positive, two negative, all inside their intervals. The rolled naked put is the
one cell with a CI wholly below zero on v3 and it is flat on v4.

**Costs.** The book runs at zero commission and zero slippage. The report's
sensitivity line re-costs every cell at $0.65 a contract and half the quoted
spread; it turns N-ROLL's 2,062 opens and closes from +$69k gross to −$15k net,
and takes the trigger cells down by a fifth to a quarter. It is printed with n
and changes no verdict.

**Registration gaps, folded in as build rulings.** The review found three
places where the report resolved something the registration did not say.
Each was decided in code on 2026-09-10 before any cell had a verdict, so each
is now in the registration tagged `Resolved at build`.

- `NULL` in the registration meant "clears the CI but fails stability". The
  code's `verdict_of()` makes NULL the total default: it also covers a CI that
  includes zero or lies below it, a criterion 5 or 6 failure, an E3 that is
  NOT EVALUABLE, and the corner where 1–6 pass and both 7 and 8 fail. There is
  no CONTRARY token, so a cell that loses with a clear CI prints NULL and the
  write-up says so in words, as above.
- E1/E2 are registered "at the common entry day". A trigger cell holds no
  tranche on that day, so the report gates its geometry at the first sale day
  and prints both columns. Naked-put cells replace the core, so their direction
  is printed and not gated.
- G1b compares "the shared rows". The report names what is not shared and lists
  each separately: rows where F4 had no leg (353), rows F4 excluded and the
  campaign sold (7), rows the campaign opened after entry (4), and 8 pre-fill
  grid days. The 82 rows both sides priced match to $0.0000 a day.

**Two review questions, answered from the code.** The scrape's target set grew
from the registered 11,502 to 11,551 because `ladder_targets.py` reads the
ticker's strike ladder and expiry list off the option cache, so targets appear
as the scrape lands; every graded cell was still AWAITING SCRAPE until the
manifest's last write, so no target was added after an outcome was seen. The
criterion-5 labels `real` and `tweak` are the export file a row came from,
which is the same thing as its pricing tier in this book: every
`BacktestResults` row is real-priced and `bs` proxy rows are dropped before the
study runs.

**Caveats.** `S-D30` (the 0.30-delta ladder) is underpowered on both eras, so
the delta target was tested at 0.20 only. `S-DTE60` is underpowered too, so
the ≥60-DTE question stays with the
[long-dated blind spot](next-steps.md#s2). The 2026 column is the same
correlated backfill window every other study reads; nothing here has seen a
genuinely new date.

**Next.** [`next-steps.md` §2.13](next-steps.md#s2-13) closes. No new item.
The ladder thread re-opens only on genuinely new dates, and only if the
trigger cells' re-wrap correlation has moved.

Provenance: working tree on main after commit 2d72047, uncommitted; the v3
report is filed under its own name because `run.py` gives both eras one
`-latest.txt`, and the v4 report was restored as the current one.
