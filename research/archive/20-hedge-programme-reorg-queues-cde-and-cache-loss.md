# Archive 20 — 2026-09-08: hedge programme reorg, queues C/D/E, and the cache loss

_Status: historical (covers 2026-09-08). Conclusions stand as of 2026-09-09. Live record: [current.md](../current.md)._

Covers 2026-09-08. The four hedge studies were renamed after the question
each answers, and the two studies deleted earlier lost their leftover files.
The robustness fold from 2026-09-07 landed on main: results-tab headers
gained the new cost columns, and queue D stopped with six failed dates. The
hedge-programme plan was deleted now that it is executed, and its spine moved
into `f5_hedging/README.md`, with follow-ups filed in next-steps §2.12.
`exit_drawdown`'s ARM P dollars reading was ACKed by the operator and is now
the SCOPED, in-force reading; its errata file was folded into the
pre-registration and deleted. Queues C, D and E ran, adding 42 dates, and the
2026 column now samples March. The two sleeve-sizing bodies duplicated in
`account_sim` and `portfolio_delta` were folded onto one function,
`lib/hedge_criteria.sleeve_pick`, and print identically. A far-call fetch was
run for `hedge_structure` Q2, but R2 failed on the new export before the
fetch could be evaluated. The fetch was re-run: the scraper had been
re-issuing the page's three-month default date range instead of the pinned
history start, which was fixed, and the 178 option-history cache files lost
on 2026-09-05 were restored. `hedge_structure` still stops at R2 on the grown
cache.

## 2026-09-08 — hedge programme — three studies renamed after their question; the two deleted studies lose their leftover files

**The four hedge studies are now named after the question each answers in
[`f5_hedging/README.md`](../../scripts/backtest_study/f5_hedging/README.md), and nothing else changed.** Operator
decision, 2026-09-08. Every arm, gate and criterion label is as registered, and
every figure is the one on record.

| Was | Is | Question |
|---|---|---|
| `bear_deploy` | `hedge_sizing` | [Q3](../../scripts/backtest_study/f5_hedging/README.md#q3), and the origin of `D2`/`D3` |
| `calendar_hedge` | `hedge_structure` | [Q2](../../scripts/backtest_study/f5_hedging/README.md#q2) |
| `hedge_exposure` | `hedge_portfolio` | [Q4](../../scripts/backtest_study/f5_hedging/README.md#q4) |
| `hedge_timing` | unchanged | [Q1](../../scripts/backtest_study/f5_hedging/README.md#q1) |

What moved with each name: the module in `f5_hedging/`, its tests, its
pre-registration (one prose line added under the registration date, nothing in
substance), its per-era record (file and H1 only; the recorded sections still
quote the old name verbatim), and the local report stems under
`backtests/study_output/`, because `hedge_structure` globs its own stem for the
resume checkpoint. The archive keeps the old names; only its link targets were
repointed. [`arm-index.md`](../arm-index.md) carries an alias anchor under each old
name so an old link still lands.

**`vol_sleeve` and `hedge_concentration` now leave only their DELETED rows.**
Their pre-registrations and frozen records were deleted (operator: leftover
files of a deleted study are bloat), together with their gitignored report and
review files and a stale bytecode cache. Git holds both files at `44bbfb2`; the
DELETED rows in [`study-map.md`](../study-map.md#hedging) are the record, and every
link that pointed at the deleted files now points there.

**Next.** Nothing opens or closes. Deliverable 3 (the far-call fetch note) and
the two sleeve-sizing bodies in `account_sim` / `portfolio_delta` stay where the
plan (deleted 2026-09-08) left them.

## 2026-09-08 (later) — robustness fold LANDED on main; results-tab headers aligned; queue D stopped with six failed dates

**The six robustness items that waited in the two worktrees are on main, at
merge `3e5c2dc`.** B1 (cost knobs), B2 (pre-entry grid days unpriced), B3, B5,
A1 (empty-table skip and zero-play refusal) and A4 (per-play validation). The
merge was clean; the suite passes at 3,502.

**The landing condition was met by a stop, not a finish.** Queue D's ledger ends
`ANALYZE-BT STOPPED` at 03:09 with six dates failed: 2025-03-19, 03-24, 03-27,
04-09, 04-23, 04-28. The operator chose to land now. Any retry of those six runs
under the cost model and the grid fix; the 18 queue-D dates already done ran
under the old code, and their rows carry blank cost columns. Read the two
populations apart on `cost_basis`.

**Both results-tab headers were realigned**, append-at-end, no data column
moved:

| Tab | Was | Is | Added |
|---|---|---|---|
| BacktestResults | 47 | 50 | `pct_stale_days`, `cost_total`, `cost_basis` |
| BacktestProxy | 46 | 49 | the same three |

**Next.** [`next-steps.md`](../next-steps.md#s2-11) §2.11 marks the branch done.
The one study-suite re-run the fold calls for is still owed, and the six failed
dates are a retry (`RETRY_PARTIAL=1`) the operator decides on. The
`robustness-fold` worktree and branch are removed, fully merged.

## 2026-09-08 (third) — hedge programme: plan deleted, spine moved into `f5_hedging/README.md`, follow-ups filed in §2.12

**The consolidation plan is deleted, not archived** (operator, 2026-09-08). It
was executed on 2026-09-07 and its status section was history; git `be6cfd0`
is the last commit holding it. The six code and test comments that cited its
sections now cite `lib/hedge_criteria.py`, whose docstring carries the one
working rule worth keeping: a copy is folded in only on an identical print, and
a different print is a finding.

**The spine is now [`scripts/backtest_study/f5_hedging/README.md`](../../scripts/backtest_study/f5_hedging/README.md)**,
beside the studies named after its four questions. Every inbound link is
repointed and the link checker now scans `scripts/**/README.md`.

**The two open items moved to [`next-steps.md` §2.12](../next-steps.md#s2-12):**
the far-call fetch pre-run note for Q2, and the two sleeve-sizing bodies in
`account_sim` / `portfolio_delta`.

## 2026-09-08 (fourth) — `exit_drawdown` ARM P dollars ACK recorded; the SCOPED reading is in force

**`exit_drawdown ARM P`'s account-level drawdown is quoted in dollars. The
operator approved this today, and the study's last open item closes.**

Why an ACK was needed: the plan has two clauses that disagree. One says "quote
R, not dollars, for ARM P". The other asks for the account-level drawdown, which
is a whole-book dollar figure on one ledger and has no natural R. The study
applied the R-only rule to the per-row and paired comparisons and used dollars
for the account-level figure, but would not let that choice stand without the
operator confirming it. The operator's reason: a whole-book drawdown of one
ledger is clearest in dollars.

**What changed in code.** The module prints ARM P's account-level drawdown, its
improvement and the CI bounds in dollars by default. The pre-ACK opt-in
`--arm-p-dollars` is gone. `--arm-p-share` is the new opt-in for the
share-of-capital form, and its banner names the rule in force and says the flag
departs from it. The STATUS bullet in the
[registration](../pre-registrations/f2_management/exit_drawdown.md) and §4 of the
errata (folded into the registration 2026-09-08) record the ACK, and
[`next-steps.md`](../next-steps.md) §0 item 4 is resolved.

**What did not move.** No graded artefact. Clause 1 is a scale-free ratio, so
the verdict is identical either way, and no run ever displayed either form:
every ARM P cell on the 2026-09-05 runs of both eras was UNDERPOWERED and
printed its census only. The graded report, the two analyst gradings and the
study-results record stand as written.

## 2026-09-08 (fifth) — `exit_drawdown` errata FOLDED into the registration; the file is gone

**Two documents made the design unreadable, so there is now one.**
`research/exit_drawdown-errata.md` is deleted and everything it held is in
[`pre-registrations/f2_management/exit_drawdown.md`](../pre-registrations/f2_management/exit_drawdown.md).
The operator: "if it has changed and updated the preregistration, it should be
folded in. it's impossible to have the exit_drawdown document and this errata
and know what's going on."

**What was folded, and where.** Each build-time ruling now sits directly after
the registered sentence it amends, opening with a bold **`Resolved at build
(2026-09-05):`** tag. The registered sentences are untouched — nothing was
deleted or reworded — so a reader can still tell a ruling taken while the module
was built from a commitment made before it.

| Errata section | Now lives in |
|---|---|
| §1 G1's DIRECTION half on ARM O's volume leg | the G1 bullet under "Gates" |
| §2 ARM P's ledger releases at the LATER half | ARM P, the "TWO synthetic `Pos`" bullet |
| §3 ARM D collapses to the EARLIEST block (and the superseded modal reading) | the ARM D section |
| §5 clause 5's sidecar, and vacuous-on-absent | clause 5 under "Bar for a candidate" |
| §6 G1's CHANGE half tallied per variant | the G1 bullet under "Gates" |
| §7 G-CAL reads `run_gates` in-process, lines printed | the G-CAL bullet under "Gates" |

§4 needed no folding: ARM P's dollars ACK was already recorded in the
registration's STATUS bullet earlier today, and the one detail only the errata
carried — that between the build and the ACK the module printed a
share-of-capital form behind a banner, and that no graded run displayed either
form — is now in that bullet.

**The recorded labels still resolve.** The graded report
(`backtests/study_output/exit_drawdown-latest.txt`) and both analyst gradings
cite readings by label — "reading 1", "correction 2", (a) through (i). A table
headed "Build-time resolutions, by recorded label" in the registration's "Build
notes" maps every label to the section that now holds it.

**Nothing graded moves.** No ruling changed meaning; only where it is written
changed. The report, the two analyst gradings and the
[study-results record](../study-results/f2_management/exit_drawdown.md) stand as
they are. `scripts/study_review/` now grades `exit_drawdown` against the
registration alone — the generic `research/<study>-errata.md` discovery
mechanism is untouched and simply finds no file, which is the normal case.

**The rule is now in CLAUDE.md.** A build-time ruling that changes what a gate
refuses or how a clause is read is folded in and tagged, never kept in a
separate file.

## 2026-09-08 (fifth) — queues C, D and E are run: 42 dates added, and the 2026 column now samples March

**All 42 dates the neutral-date rule dropped in step 4 are analysed, and 35 of
them priced.** Nothing ships: this is population, not a result, and no study has
run on the new book. The book gains 55 real rows over 25 signal dates, and its
2026 column grows from 11 dates to 26, five of them March sessions inside the
drawdown the sample previously missed.

_Era v4 · all three exports re-pulled and installed 2026-09-08 · 598 real /
1,665 proxy rows over 193 / 208 dates · 2,677 analysis rows over 228 dates, one
run per date · no study run on this export._

**In production.** Nothing changes. No rule was read off these dates.

**What ran.** Every date in all three queues reached both steps. A date with no
real rows still produced proxy rows, so nothing in the queue was left half-run.

| Queue | Dates | Analysed | With real rows | Proxy only |
|---|---|---|---|---|
| C, 2026 sessions | 13 | 13 | 11 | `2026-03-09`, `2026-03-12` |
| D, pre-2026 | 24 | 24 | 20 | `2024-08-12`, `2024-09-06`, `2025-05-14`, `2025-12-09` |
| E, moved right edge | 5 | 5 | 4 | `2026-04-21` |

Queue D's ledger ends `ANALYZE-BT COMPLETE`. Its six dates that failed on
2026-09-07 (`2025-03-19`, `03-24`, `03-27`, `04-09`, `04-23`, `04-28`) were
retried on 2026-09-08 and all six priced.

**The population.**

| Field | 2026-09-07 export | This export |
|---|---|---|
| Real results | 543 over 168 dates | 598 over 193 dates |
| Proxy rows | 1,380 | 1,665 |
| Analysis rows | 2,325 over 198 dates | 2,677 over 228 dates |
| Pooled study book | 1,183 over 177 dates | 1,374 over 208 dates, being 598 real plus 776 tweak |
| Signal dates | 2024-01-10 → 2026-04-16 | 2024-01-10 → 2026-05-07 |
| 2026 signal dates, pooled | 11 dates, 79 rows | 29 dates, 161 rows |
| 2026 dates with real rows | 11 | 26, of which 5 are March |

The book is still clean at the identity layer: no key repeats on
`BacktestResults`, every date carries one analysis run, and the only rows that
fail to join a play are the two 2025-07-29 rows kept on purpose.

**Seven dates priced nothing, and that is the pricer, not a failure.** Their 73
plays were all skipped, 53 for `no_history` and 20 for `unpriced`, and each
landed on `BacktestProxy` with a fallback verdict. Nothing about those dates
needs re-running.

**The pre- and post-cost-model rows cannot be told apart on `cost_basis`.** The
[2026-09-08 (later)](#2026-09-08-later--robustness-fold-landed-on-main-results-tab-headers-aligned-queue-d-stopped-with-six-failed-dates)
entry and [`next-steps.md`](../next-steps.md) §2.11 both said to split them there.
That does not work: `_apply_costs` writes `cost_basis` empty whenever both cost
knobs are 0, which they are, so the column is blank on all 598 rows. The
separator is `cost_total` or `pct_stale_days` being non-blank, which holds on 14
rows over the six retried dates and nowhere else.

**Every proxy row is blank in the three new columns, and that is a bug.**
`proxy.py::_evaluate` copies `_RESULT_COLS + _BASIS_COLS` from the simulation
onto the row and never `_COST_COLS`, so `pct_stale_days`, `cost_total` and
`cost_basis` stay at their blank default even on priced tiers. It is the same
shape as the `exit_basis` gap fixed on 2026-09-02, which the comment two lines
above the copy loop describes. Confirmed on the local scratch: the last proxy
run wrote 7 priced rows with all three blank, while the real backtest's scratch
row carries `pct_stale_days` and `cost_total`. The fix is one line; it is
[`next-steps.md`](../next-steps.md) §2.11's newest row and nothing has been changed
yet.

**Caveats.**

- The 42 dates did not run under one code version. The six retried queue-D
  dates ran after merge `3e5c2dc`, so they carry the cost columns and the
  pre-entry grid fix; the other 36 ran before it and may hold pre-entry P&L on
  about 4% of positions. A `--redo` is what levels them.
- The two hardcoded 2026-03 date tables are still partly no-ops.
  [`mech_regime_recut`](../study-results/f1_selection/mech_regime_recut.md) §(b) and
  [`regime_gap_reread`](../study-results/f1_selection/regime_gap_reread.md) §0 both
  list `2026-03-06`, `03-12`, `03-20`, `03-27`. The export now holds `03-20`
  with real rows and `03-12` with analysis rows only; `03-06` and `03-27` are in
  no export and were never in the selection.
- These dates sit inside `[2024-01, 2026-05]`, so they do not make the window
  independent. §2.2 and §2.6 still wait on dates after 2026-08-11.
- The honest expectation was written before the run: adding the March sessions
  moves every per-year criterion that has a 2026 cell, and may move it either
  way. Nothing has been measured yet.

**Next.** [`next-steps.md`](../next-steps.md) §0 item 3 closes. The study-suite
re-run the robustness fold already owed is now owed on a book that grew again,
and it is the run that reads what these dates do.

## 2026-09-08 (sixth) — the two sleeve-sizing bodies in `account_sim` / `portfolio_delta` are folded onto `lib/hedge_criteria.sleeve_pick`; identical print

**Both simulators now pick the day's bear sleeve through
`lib/hedge_criteria.sleeve_pick`, and the fold changed no printed figure.**
Nothing ships; this is the second item of
[`next-steps.md` §2.12](../next-steps.md#s2-12), and it is closed.

_Era v4 · exports installed 2026-09-08 · 598 real / 1,665 proxy / 2,677
analysis rows · both studies run before and after the edit on this export, git
working tree otherwise unchanged between the two runs._

**The rule.** One bear-debit position per signal date, ranked by `|delta|`
descending, ties to the first row in the day's order, an unpriced candidate
unrankable. That is `sleeve_pick` under a picker that returns `None` for a
missing delta. `account_sim.sleeve_rank` is that picker, defined once;
`portfolio_delta` imports it.

**What the copies did.** `account_sim.simulate` (ARM H) and
`portfolio_delta.simulate_banded` (the shipped sleeve and ARM H*) each sorted the
day's candidates by `|delta|` with a missing delta ranked last, took the first,
and then skipped it if it had no delta or no max loss. `sorted(reverse=True)` is
stable and `max()` returns the first maximum, so the tie-break is the same; a
missing delta ranked at −1 could only win a day with no priced candidate, which
both versions then skip. The one behaviour worth naming survives unchanged: a
chosen row with no max loss is skipped, never replaced by the runner-up.

**Reconciliation, under the rule in `lib/hedge_criteria.py`'s docstring.** The
recorded sections in `research/study-results/` were printed on older exports,
so the comparison is the same export before and after the edit.

| Study | Report diff | Positions CSV |
|---|---|---|
| `account_sim` | timestamp and elapsed-time lines only | byte-identical |
| `portfolio_delta` | timestamp and elapsed-time lines only | not written by this study |

ARM H on this export, for the record: 73 sleeve positions with the sleeve on
against 236 signal positions (PRIMARY), 92 against 322 (SECONDARY). Those are
the study's lines, not a new reading.

**Pinned.** `tests/test_portfolio_delta.py::
test_both_simulators_take_the_row_hedge_criteria_sleeve_pick_chooses` runs both
simulators on a day with an unpriced first candidate, a `|delta|` tie and a
runner-up, and on a day whose pick has no max loss.

**Next.** §2.12 keeps only the far-call fetch, below.

## 2026-09-08 (seventh) — far-call fetch for `hedge_structure` Q2: pre-run note, then the fetch; R2 fails on the new export before any of it

**A new collector, `scripts/collector/fetch_far_legs.py`, fetches the one
contract `hedge_structure`'s calendar reads and the cache does not hold: the
call at K* on the ticker's first later cached expiry.** No rule changes and
nothing ships. This note is written BEFORE the fetch runs, so the numbers it
would move are on record first. It closes the first item of
[`next-steps.md` §2.12](../next-steps.md#s2-12) as far as the collector goes;
the post-fetch `hedge_structure` read is blocked by a gate failure that has
nothing to do with the fetch (below).

_Era v4 · exports installed 2026-09-08 · 598 real / 1,665 proxy / 2,677
analysis rows · `load_book(include_bs=False)` gives 1,324 records over 208
dates · option cache 43,019 contracts before the fetch (the study's
PROVENANCE line prints the exact count)._

**The rule, as registered.** The
[registration](../pre-registrations/f5_hedging/hedge_structure.md) freezes the
code rather than restating the pick: `sleeve_synth.build_legs("calendar")`.
Short the call at K* on the near expiry the book entered, long the call at the
same K* on the first later expiry that holds a call at K* in the cache. K* is
the paired strike (call AND put cached) nearest the entry's spot. "Listed"
means "in `backtests/option_history_cache/`" and nothing else; the
registration never reads the flow CSV. An anchor with no paired grid names no
K*, and an anchor whose ticker has no later cached expiry names no far leg.

**Current behaviour.** The calendar is fillable on about half the deployed
dates and a quarter to a third of the worst decile, so H0 fails and the primary
is never read. Last recorded read, 2026-09-07 tabs, before the 42 queue dates:

| Line | 2026-09-07 run `hedge_structure-20260907-234321.txt` |
|---|---|
| deployed dates | 156 |
| worst-decile deployed dates | 15 |
| P1 fillable on deployed dates | 80 / 156 = 51.3% FAIL |
| P1 fillable on worst-decile dates | 4 / 15 = 26.7% FAIL |

**What the fetch targets.** The collector walks the study's own universe
(first record's spot per (date, ticker, leg expiry), whole pooled book, not
only deployed dates) and asks, per anchor, whether the call at K* at the
ticker's first later cached expiry is there. Its dry run on this export:

| Anchor outcome | Count |
|---|---|
| anchors (date, ticker, near expiry) | 1,322 |
| no paired grid at the near expiry, no K* | 601 |
| ticker has no later cached expiry | 8 |
| far call at K* already cached | 196 |
| far call missing, a target | 517 |
| distinct contracts to fetch | 348 |

Top tickers among the 348: NVDA 35, IWM 33, GLD 28, TSLA 25, QQQ 18, TLT 18.
The 601 no-grid anchors are the larger half and this fetch does not touch
them: they need the near-expiry PUT at K*, which is `fetch_sweep_legs.py`'s
`put_calendar` target. Whether Barchart lists K* at the far expiry is not
known in advance; a contract with no bars is recorded `failed` in
`backtests/sweep_cache/far_legs_manifest.csv` and never written to the cache.

**Two things the fetch changes that are not a rule change.** First, on an
anchor where a call at K* is cached at a further expiry but not at the first
later one, the study today pairs with the further one; after the fetch it pairs
with the first, so an already-built calendar can change value. The post-fetch
print is a new population, not a delta. Second, the far expiry is evidenced by a
contract observed at some point, not proven listed on the entry date; a far
call whose own history starts after the entry session fails `no_common_entry_day`
in the study, which is the right outcome.

**Found while taking the baseline.** Two things, neither caused by the fetch.

- `backtests/sweep_cache/synth_results.csv` had a 23-column header over rows of
  24 fields, so every stored row read back with `cache_sig` blank and the
  study recomputed everything on every run; the store only grew. `--redo`
  rewrites the file with the full header, so the baseline run below fixed it
  (2,813 rows, 24 columns, now readable).
- **The baseline run FAILS R2 on this export**, before H0 prints:

| R2 on the 2026-09-08 export | Count |
|---|---|
| reconstructs | 1,311 / 1,321 |
| `leg_not_cached` | 5 |
| `mark_mismatch` | 4 |
| `entry_mismatch` | 1 |

  The five `leg_not_cached` keys need three files the cache held on
  2026-09-07 and holds no more: `GLD_20250627_295.00P`, `GLD_20250627_285.00P`,
  `TSLA_20250627_290.00C`. They are not in the 2026-09-05 Drive snapshot, so they
  are refetched from Barchart in the same session as the far calls. The five
  mismatch rows all sit on 2025-03-24, 2025-04-09 and 2025-04-28, three of the
  six queue-D dates retried on 2026-09-08 under the cost model and grid fix; the
  registered reconstruction does not reproduce them. That is a robustness-fold
  consequence and is filed under [§2.11](../next-steps.md#s2-11), with the
  diagnosis appended below once it is in.

**Next.** The fetch runs now. Then `fetch_far_legs.py --dry-run` is re-run to
print how many of the 517 target anchors are now `cached`, and
`hedge_structure --redo` is re-run; if R2 still fails on the five mismatch rows
the H0 read waits on §2.11 and this note says so.

## 2026-09-08 (eighth) — far-call fetch run twice: the scraper was re-issuing the page's three-month default range, fixed; 178 lost cache files restored; hedge_structure stays blocked at R2

**The first fetch came back empty for every contract expired before 2026-06-08,
and the cause was ours: the scraper captures the price-history feed request
the page fires and re-issues it verbatim, and that request carries the page's
default range, `startDate=` three months back.** The operator pointed at the
page's two-year toggle. The floor is now pinned in
`lib/barchart/session.py::_augment_history_url` (`HISTORY_START_DATE`), and the
fetch was re-run with `--retry-failed`. Nothing ships. Two other things found on
the way stand: the backtest's refetch path deletes cache files, and the
robustness fold's zero-bid re-mark is not mirrored by the registered
reconstruction, so `hedge_structure` cannot print H0 on this export.

_Era v4 · exports installed 2026-09-08 · same book as the pre-run note above ·
first fetch 22:57 to 23:20 under the default range, second after the fix ·
option cache 43,019 contracts before, 43,224 after the first fetch and the
restore._

**What went wrong in the first fetch, and the correction.** The captured feed
URL read `...&limit=1000&startDate=2026-06-08&...`. Re-issued for a contract
that expired before that date it returns no rows, which the first run recorded
as "no data" 320 times and this log first wrote up as a Barchart limit. It is
not: the page's range toggle sends an earlier `startDate`, and the feed accepts
one far back.

| Probe, INTC 2025-01-17 47P, expired | Rows |
|---|---|
| captured request, `startDate=2026-06-08` | 0 |
| `startDate=2023-01-01` | 421, 2023-05-04 to 2025-01-17 |
| `startDate=2020-01-01` | 421, the same |

Two probe requests re-navigating the same page inside one session returned
HTTP 403; the first request of a session did not, so the 403 is a repeat-visit
block and not the parameter. `_augment_history_url` now rewrites `startDate=`
to the 2020-01-01 floor on every capture, which both the collector and the
backtest's own refetch go through. Pinned by
`tests/test_backtest.py::test_augment_history_url_pins_start_date_below_the_pages_default`.
The files scraped in July and August carry a year or more of bars, so the page's
default moved recently; the logs only hold full feed URLs from 2026-09-08 and
cannot date it.

**First fetch, under the default range.** All 348 targets attempted once;
manifest `backtests/sweep_cache/far_legs_manifest.csv`.

| Outcome | Contracts |
|---|---|
| fetched, written to the cache | 27 |
| already present (restored below) | 1 |
| no data, expiry before 2026-06-08 | 317 |
| no data, expiry on or after 2026-06-08 | 3 |

Every fetched file's history started on 2026-06-08 or later, which is what the
default range would produce. The second fetch's tally is appended at the end of
this entry.

**Cache files are being deleted by the backtest, and 178 were restored.**
`scripts/backtest/shared/history.py` unlinks a cache file whose earliest bar is
more than five days after the signal date, then refetches; when the feed returns
no rows it keeps nothing, and nothing writes the file back. Under the default
range every such refetch of an expired contract was empty, so the 2025-04-28
retry on 2026-09-08 deleted 20 files, three of them the ones R2 named. With the
floor pinned the refetch would now succeed, but an unlink before a request that
can fail stays fragile and is filed. Comparing the 2026-09-05 Drive snapshot to
the directory:

| Set | Files |
|---|---|
| in the snapshot | 42,219 |
| local before restore | 43,030 |
| in the snapshot, missing locally | 178 |
| local, not in the snapshot (scraped since) | 989 |

The 178 were extracted from the local copy of the snapshot with an additive
extract that overwrites nothing, the same rule `backup_research_caches.py pull`
applies. The 989 scraped since 2026-09-05 have no copy anywhere until the next
`push`. Both are in [`next-steps.md` §2.11](../next-steps.md#s2-11).

**R2 after the restore.** `hedge_structure --redo` on this export:

| R2 | Count |
|---|---|
| reconstructs | 1,316 / 1,321 |
| `leg_not_cached` | 0 |
| `mark_mismatch` | 4 |
| `entry_mismatch` | 1 |

The five are the rows the pre-run note named, and the cause is now known: the
fold's B5 zero-bid re-mark (`simulate.py::_zero_bid_mark`, merge `3e5c2dc`)
marks a leg with `bid 0` at `ask / 2`, and `bear_rewrap.reconstructs`, which the
registration freezes, still prices mid-else-Latest. On every day the gate counts
as disagreeing, the stored figure equals the B5 figure exactly. R2 is
all-or-nothing, so any export holding post-fold rows that met a zero bid stops
the study before H0. Mirroring B5 in the reconstruction is a change to
registered code and is the operator's decision, filed in §2.11.

One of the five is a genuine pricing defect rather than a mirror gap. HYG
2025-04-09, a proxy bear put spread: the short leg had no bar on the fill day,
the six-day-old carried snap read `bid 0 / ask 2.68`, B5 marked it 1.34, the
entry came out at −0.37 on a debit structure, and the exit basis keyed CREDIT
and booked +100%. Any post-fold row with a negative entry on a debit structure
should be read as suspect until that is fixed. Filed in §2.11.

**Next.** §2.12's two items are worked; the far-call read waits on §2.11's B5
decision. The suite re-run the fold calls for will meet the same R2 stop in
`hedge_structure`; `bear_rewrap` uses the same reconstruction but drops and
counts a failing row instead of stopping, so its tally moves by five. Fix the
unlink before the re-run.

**Second fetch, after the fix (`--retry-failed`, 2026-09-08 23:40 to 2026-09-09
00:06).** Every one of the 320 first-run failures was re-asked.

| Outcome, 349-row manifest | Contracts |
|---|---|
| fetched, written to the cache | 326 |
| no data | 21 |
| a valid file with under two bars, not written | 2 |

The 21 are spread over 2024 to 2026 expiries with no pattern by date, which is
what a strike the chain never listed at that expiry looks like; they stay
`failed` in the manifest and are not re-hit unless `--retry-failed` is passed.

| Collector census | Before any fetch | After the first | After the second |
|---|---|---|---|
| anchors with the far call at K* cached | 196 | 241 | 666 |
| anchors still missing it | 517 | 472 | 58 |
| anchors with no paired grid | 601 | 601 | 590 |
| option cache, contracts | 43,019 | 43,224 | 43,517 |

The no-grid count moved because the restored and fetched files completed a few
near-expiry pairs. `hedge_structure --redo` on the grown cache still stops at
R2 with the same five rows (`reconstructs 1,316 / 1,321`), so H0 is not read;
the fill lines will print once §2.11's B5 item is decided, and the cache is
ready for them.
