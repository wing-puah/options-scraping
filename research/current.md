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

## 2026-09-17 — bear_rewrap pricer — B5 zero-bid re-mark mirrored, R2 at 1,320 / 1,321

**The research pricer now marks a zero-bid leg the way production does, and
`hedge_structure`'s R2 drops from five failures to one.** Nothing ships. The one
remaining failure is not a B5 row: it is the HYG 2025-04-09 row already filed as
a fabricated credit, and it fails on its entry day. `hedge_structure` stays
blocked at R2 until that row is decided.

_Population: v4, the 2026-09-08 22:38 exports (598 results rows, 1,665 proxy
rows); `hedge_structure` R2 over 1,321 ticker-dates._

**The rule.** Production (`scripts/backtest/simulate.py::_zero_bid_mark`, the
B5 fix merged in 3e5c2dc) marks a leg quoted bid 0 at ask/2, or at 0 when
nothing is offered. It applies to the daily marks, to a carried-forward snap,
and to a zero-volume entry day. A row with no mid and no Latest is never
re-marked, because production never loads it.

**The implementation.** `bear_rewrap.py` imports `_zero_bid_mark` rather than
restating it, through one helper, `row_mark`. `leg_series`, `entry_price_of`,
`net_entry` and `net_marks` all go through it. Research importing production is
the existing direction; production still imports nothing from research.

**Why the basis follows the stored row.** B5 on every row broke rows that were
priced before the fold. No column records which rule a row was priced under:
`cost_basis` is blank on all rows and the cost columns are blank on every proxy
row. The write time does. Rows stamped at or after the merge, 2026-09-08
15:05:25, get B5. Older rows keep the plain mark. On this export no row was
written between 10:31:15 and 15:21:14 that day, so the cut decides no real row.

| R2 on 1,321 ticker-dates | Pass | Fail |
|---|---|---|
| Old mirror, no B5 | 1,316 | 5 (4 mark, 1 entry) |
| B5 applied to every row | 1,143 | 178 (177 pre-fold rows now fail) |
| B5 on rows written after the merge | 1,320 | 1 (HYG entry) |

**Variants share the baseline's basis.** A study that prices a substitute,
overlay or financed leg against a stored row prices it on that row's basis
(`bear_rewrap.basis_of`; `financed_spread` and `ladder_overlay` wrap their row
loops). A first run without this marked substitutes with B5 against pre-fold
baselines. It moved `bear_rewrap`'s `long_diag` dR from +0.154 to +0.119 and
its CI across zero. That move came from mixing two mark rules in one comparison,
not from the structure, so it was discarded. A price with no stored row behind it,
such as a `hedge_structure` sleeve, takes the production rule.

**The residual failure.** Production filled HYG on 04-14, the long leg's first
bar, and carried the short 72P's 04-10 snap (bid 0 / ask 2.68, re-marked to
1.34). The net was −0.37 on a bear put spread. `entry_date_for` needs a bar on
every leg, so it picks 04-16 and gets 0.47. On 04-14 the mirror reproduces −0.37
and 35 / 35 marks. Mirroring production's entry day would pass R2 by admitting
the fabricated credit, so it was not done.

**What the re-runs moved.** Each study's verdicts are unchanged. The only
movement is the rows the fixed gate now admits.

| Study | Rows admitted before → after | Verdict lines |
|---|---|---|
| `bear_rewrap` | 480 → 481 (XLF 2025-04-09) | unchanged; `long_diag` dR +0.154 → +0.153, CI [+0.025, +0.281] |
| `financed_spread` | 916 → 918 | unchanged; F0 dR −0.155 → −0.140 |
| `ladder_overlay` | 446 → 447 cores | unchanged; G1 and G1b PASS |
| `hedge_structure` | R2 1,316 → 1,320 | still R2 FAIL; H0 not printed |

**Unresolved.**
- HYG 2025-04-09 blocks `hedge_structure`. The default is to leave R2
  all-or-nothing and the row as stored. Re-pricing it after the §2.11 carried-snap
  fix would clear R2. Choosing that is the operator's call.
- `hedge_structure`'s checkpoint store (`synth_results.csv`) is keyed on the
  cache, not on the mark rule. Rows it built before today used the plain mark.
  When R2 clears, run the study with `--redo` so no sleeve mixes the two rules.
- `lib/hedge_instrument.py` restates the plain mark for the hedge puts, and its
  pre-registration names that rule. It prices no stored row and was left alone.

**Queue.** [`next-steps.md` §2.11](next-steps.md#s2-11): the B5-mirror row is
resolved, and the HYG row now also names the R2 block.

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

## 2026-09-09 — journal — `scripts/live_loop/` is gone; its rules module is `scripts/journal/lib/mapping.py` and speaks the journal's own types

The live-loop package is deleted. Its rules module, the one encoding of
[deployment-rules §1–§3](../docs/deployment-rules.md#s1) plus the structure
classifier and the play matcher, now lives inside the journal at
`scripts/journal/lib/mapping.py`. `stage1_map_fills.py` is retired: its data
source was a hand-pasted IBKR snapshot, the newest is dated 2026-08-12, and the
daily journal reads Flex with strike and expiry on every fill, so the reconcile
step already does what the fortnightly script did. The two snapshots and their
reports stay under `backtests/live_loop/` as protected data.

The move also removed the adapter layer. Mapping was written against the
snapshot script's hand-built dict shape, so the reconcile step, the book
grouper and the relabel diagnostic each carried code whose only job was to
dress the journal's `Leg` objects up as that shape. Mapping now takes `Leg`s
directly and the adapters are deleted. The closing-fill sign inversion, the
P1 fix from the robustness review, is a named function
`mapping.position_legs(legs, closing=True)` instead of a side effect inside an
adapter. Two dead branches went with it: the classifier's "identity could not
be pinned" path, unreachable when every leg carries a contract id, and the
unused `leg_desc` helper.

Behaviour is unchanged, checked two ways:

| Check | Result |
|---|---|
| Every raw pull in `journal/raw/` re-reconciled before and after, journal row fields keyed on `source_ref` | 159 events compared, 0 differ |
| Test suite | 3527 passed (3520 before; the seven new tests pin `position_legs`, `net_price` and classifier labels the old fixtures never reached) |

The research tier's live-select arm still imports `ladder_tier()`; it is the
one sanctioned research-to-production import, now stated as "the arm imports
from `scripts/journal/`". The evaluation half of the walk-forward, live P&L
by tier and taken versus not taken, was never in the deleted script in a
usable form and is still not written. It belongs to the f4 study queued in
[next-steps §2.5](next-steps.md#s2-5), after its registration.

Provenance: working tree on main after commit 2226888, uncommitted;
`make check-doc-links` 0 broken.

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
