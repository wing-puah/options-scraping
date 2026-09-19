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
| Exports | re-pulled 2026-09-08, then again 2026-09-19 after 2025-04-09 was re-priced; deduplicated, and every result row joins its play |
| Real results | 598 over 193 dates |
| Proxy rows | 1,665 |
| Analysis rows | 2,781 over 237 dates on the 2026-09-19 export, one analysis run per date |
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
- **Almost every `BacktestProxy` row is blank in `pct_stale_days`, `cost_total`
  and `cost_basis`.** `proxy.py::_evaluate` never copied them onto the row; fixed
  2026-09-19, but NOT backfilled, so only the 9 rows re-priced on 2025-04-09
  carry them. Treat the rest as "did not run under the cost model", which is
  true of them. [`next-steps.md`](next-steps.md) §2.11.
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
([entry](archive/21-ladder-overlay-closed-the-journal-walk-forward-and-the-pricer-mirror.md#2026-09-16--ladder_overlay--nothing-ships-no-ladder-or-naked-put-cell-beats-the-plain-spread-on-v4-or-v3)).

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
