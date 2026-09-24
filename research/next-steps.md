# Next steps — the queue

This file is the queue and nothing else. Every item leads with its status, then
what it is waiting on, then the decision or finding in one line, then links.
Nothing here restates a result: for where the research stands, read the
[State of play](current.md#state-of-play) block at the top of
[`current.md`](current.md), which is authoritative. Section numbers are
**stable labels** cited from code, tests and the archive, so a closed item keeps
its number as a one-line stub with a link. Written 2026-08-31, cut to queue-only
2026-09-05.

<a id="s0"></a>
## 0. Repo state — read first

- **Era and population.** `v4`, the 193-date backfilled book, all three exports
  re-pulled 2026-09-19. The results tab is 598 rows over 193 dates. The
  analysis tab is 2,781 rows over 237 dates, with one analysis run per date.
  Both are deduplicated, tab and export agree on each, and every result
  row joins its play except two kept on purpose. Counts and the date range:
  [the population](current.md#the-population).
- **Most of the queue waits on genuinely new dates.** `AnalysisClaude` carries
  2026-08-11 → 2026-09-18 from the daily pipeline with no backtest rows, because
  those options have not expired. §2.2 and §2.6 wait on them. The 42 dates
  queues C, D and E just added do NOT qualify — they sit inside
  `[2024-01, 2026-05]`, the same correlated window
  ([where the 2026 column bit](current.md#where-the-2026-column-bit)).
- **Tests green, and the suite ran 2026-09-19 on these exports.** Every
  non-retired study ran, and 18 of 31 verdicts moved
  ([entry](current.md#2026-09-20--suite-re-run-read-in-full--18-of-31-verdicts-moved-two-touch-shipped-rules),
  [per-study rows](study-map.md#operator-reading-2026-09-20)). The previous
  full run was 2026-09-04 on the 166-date book
  ([`current.md` 2026-09-04 late](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-04-late--first-book-with-2026-dates-export-refreshed-suite-re-run-nothing-ships-the-year-clause-bites-campaign-b-closed)).
- **How this book was built.** `BacktestResults` lost 16 duplicate rows and
  gained 4 re-priced ones on 2026-09-06. It then lost the 12 stale rows and
  gained the daily pipeline's on 2026-09-07. It gained the 42 queue dates on
  2026-09-08, and `BacktestProxy` had its 9 rows on 2025-04-09 re-priced on
  2026-09-19. The analysis tab lost the 37 rows of a duplicated run on
  2026-09-07 and gained the same 42 dates. The population moves next only when
  the operator decides one of the re-price items below.
- **The option-history cache LOST 178 FILES between the 2026-09-05 snapshot and
  2026-09-08, and the scraper was asking Barchart for three months of history.**
  Found 2026-09-08 ([record](archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md#2026-09-08-eighth--far-call-fetch-run-twice-the-scraper-was-re-issuing-the-pages-three-month-default-range-fixed-178-lost-cache-files-restored-hedge_structure-stays-blocked-at-r2)). The captured price-history feed request
  carries the page's default `startDate=` three months back, so a re-issued request for
  an expired contract returned no rows; `lib/barchart/session.py` now pins the floor at
  2020-01-01. `scripts/backtest/shared/history.py` unlinks a shallow cache file before that
  refetch, so every empty refetch deleted a file. The 178 were restored from the snapshot;
  every file scraped since it has no copy until `backup_research_caches.py push` runs.
  The unlink is filed in [§2.11](#s2-11).
- **RESOLVED 2026-09-07 — six missing option-history files, not two, restored from the `research-caches-20260905-1111.tar.gz` Drive snapshot; `hedge_structure` then read `reconstructs: 1180 / 1180 (100.0%)` and `R2 PASS` on that export, until the 2026-09-08 retries deleted three more (above; restored again)** ([record](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-07-fifth--hedge-programme--criteria-consolidated-two-studies-deleted)).
- **Two hardcoded date tables are still PARTLY no-ops.**
  [`mech_regime_recut`](study-results/f1_selection/mech_regime_recut.md) §(b)
  and [`regime_gap_reread`](study-results/f1_selection/regime_gap_reread.md)
  §0 both list `2026-03-06`, `03-12`, `03-20`, `03-27`. Queue C added `03-20`
  with real rows and `03-12` with analysis rows only. `03-06` and `03-27` are in
  no export and were never in the neutral-date selection, so both tables stay
  half-empty however the suite is re-run.
- **Robustness review, 2026-09-07.** [`robustness-review.md`](robustness-review.md).
  Two of its items changed every number a run prints: the backtest had no cost
  model, and it could book P&L on days before the fill. Both were built
  2026-09-07 in a worktree and landed on main 2026-09-08 (`3e5c2dc`), so the
  2026-09-19 suite run read code that carries them. Only the rows written
  since carry the columns, which is why the book mixes pricing regimes. Status
  of every item: §2.11.
- **Rescaled tickers.** `backtests/underlying_ohlc_cache/rescaled_tickers.txt`
  lists 13 tickers after the 2026-09-05 rebuild, NVDA and GE newly among them.
  Every OHLC consumer withholds absolute dollars and cross-series comparisons on
  those; ratios stay valid
  ([`current.md` 2026-09-05](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-05-later--overviewmd-and-glossarymd-rewritten-for-a-reader-who-has-lost-the-thread-the-long-dated-blind-spot-is-scoped-debit-only)).

### Waiting on the operator

Decisions owed. None of these is a study.

1. **DONE 2026-09-06** — four missing rows re-priced, 16 `BacktestResults`
   duplicates dropped, export refreshed to 524 rows / 159 dates; the re-priced
   724-DTE TSLA row is one row inside the §2.7 long-dated blind spot, not a
   lifting of it
   ([record](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-06-later--the-spy-duplicate-and-15-older-duplicate-rows-are-dropped-the-export-is-524-rows-analysisclaude-keeps-both-runs)).

2. **DONE 2026-09-07** — the 12 stale rows dropped, `BacktestResults` 543 rows
   over 168 dates, every row joins its play; `COIN` and `EEM` on `2025-07-29`
   still fail to join and are KEPT on purpose (their analysis rows went missing
   from an unrelated cause); `scripts.backtest` now refuses a play its results
   tab already holds
   ([record](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-07-later--the-12-stale-backtest-rows-are-dropped-and-the-backtest-can-no-longer-double-a-row)).

3. **DONE 2026-09-08** — queues C, D and E are run. C added 13 dates inside
   2026. D added 24 before it, and E 5 at the moved right edge. That is 42
   dates, of which 35 priced. The results tab is 598 rows over 193 dates. The
   2026 column went from 11 to 26 dates, with five March sessions inside the
   drawdown. Seven of the 42 produced only `BacktestProxy` rows, which is the
   pricer rather than a half-run date. The suite measured them on 2026-09-19
   ([record](archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md#2026-09-08-fifth--queues-c-d-and-e-are-run-42-dates-added-and-the-2026-column-now-samples-march)).

4. **RESOLVED 2026-09-08** — `exit_drawdown` ARM P's dollars ban is SCOPED:
   account-level drawdown prints in dollars by default, `--arm-p-share` for the
   share-of-capital presentation; no graded cell changes, every ARM P cut was
   UNDERPOWERED
   ([pre-registration](pre-registrations/f2_management/exit_drawdown.md), ARM
   P's STATUS bullet).

5. **OPEN — the `NOT FEASIBLE AT $25,000` print belongs to an unregistered cap
   cell.** The tracked config carries a net cap of 2.50 × equity, raised by the
   operator on 2026-08-13. The registration's headline cell is (0.25, 1.50)
   ([entry](current.md#2026-09-21--account_sim--the-registered-cap-cell-prints-feasible-the-run-on-record-does-not),
   [plan](account-sim-feasibility-plan.md)).

   - **What the registered cell prints.** Run on 2026-09-21 it reads
     `>>> FEASIBLE <<<`, meeting every criterion on both populations, at 20.3%
     PRIMARY. Marked to market rather than realized on close, the same cell
     reads 25.9% PRIMARY and 44.8% SECONDARY, past the bar on that basis.
   - **First decision.** Fold the cap change and the 2026-08-14 verdict
     wording into the registration as `Resolved at build` tags, and say which
     cell the tracked config should carry.
   - **Second decision.** Change capital or sizing, or accept the drawdown.
   - **Neither the 1.50 cell nor the registered arm F2 may be adopted on its
     P&L.** The registration forbids adopting a cap value that way. Both
     figures had also been seen before this run: 20.3% in the cap grid, and
     F2's 8.7% in the arms table on every run.
   - **Default if nothing is decided.** Nothing changes, and the study keeps
     printing the verdict on the tracked cell.
   - **Sizing throttles closed 2026-09-22.** A Turtle-ladder or ARM D-shaped
     drawdown throttle does not fix this
     ([entry](current.md#2026-09-22--account_sim--a-turtle-drawdown-throttle-is-inert-at-25000-closed-unregistered)).
   - **A draft registration for "accept a deeper drawdown, but guard against
     ruin".** [`ruin_bound`](pre-registrations/f4_deployment/ruin_bound.md)
     picks a cap cell and guardrail by a rule fixed in advance. The operator
     fills its bounds before any code is written. It runs only after item 8
     and full cost coverage.

6. **DECIDED 2026-09-22 — re-price the pre-fill rows.** Stale or incorrect
   data should not sit on the sheet, so exclusion is no longer the plan: the
   fuller census widened the count from 14 to 17. Waits on item 8's
   Barchart refetch
   ([decision](current.md#2026-09-22-evening--journal-repair-lands-cost-model-on-five-queue-items-decided),
   [census](current.md#2026-09-20-later--stored-book--a-cache-only-re-price-moves-370-of-2234-rows)).

7. **DECIDED 2026-09-22 — re-price the six wrong-strike rows.** They are `NVDA`
   2024-11-26, `IWM` 2024-03-25 and `SPY` 2025-05-09 on `BacktestResults`, and
   `FCX` 2024-08-23, `PINS` 2024-02-27 and `IWM` 2024-02-06 on `BacktestProxy`.
   Same operator ruling as item 6: re-price, do not leave them
   ([decision](current.md#2026-09-22-evening--journal-repair-lands-cost-model-on-five-queue-items-decided),
   [entry](current.md#2026-09-20-third--backtest-classifier--six-priced-rows-used-strikes-from-the-narrative-fixed)).

8. **OPEN, cost model now ON — the whole-book re-price.** The backtest prices
   net of $0.65 a contract plus 25% of the quoted spread from 2026-09-22
   onward (`8831f96`); every stored row stays gross until this re-price runs.
   Still blocked on a Barchart refetch: 80 `BacktestResults` rows cannot be
   priced offline, 57 with no cache file and 20 a shallow one. The `--redo`
   plan itself is written, not run
   ([decision + plan](current.md#2026-09-22-evening--journal-repair-lands-cost-model-on-five-queue-items-decided),
   [census](current.md#2026-09-20-later--stored-book--a-cache-only-re-price-moves-370-of-2234-rows)).

9. **DECIDED 2026-09-22 — re-price the 49 `Open`-fill rows.** The entry rule
   is now side-aware ahead of the `Open` print (`0a68bdf`); the operator's
   ruling is to re-price rather than leave them, same as items 6 and 7. Waits
   on item 8
   ([decision](current.md#2026-09-22-evening--journal-repair-lands-cost-model-on-five-queue-items-decided),
   [census](current.md#2026-09-20-later--stored-book--a-cache-only-re-price-moves-370-of-2234-rows)).

10. **OPEN — `bear_arm` prints `REVERT CONDITION FIRED`.** The report asks for
    a production config change on the bear-debit `be_after 0.50` stop, which
    was already reverted on 2026-08-24. The operator still deploys bear debits
    and closes them fast; that belief is now a draft study, not a config
    change: [`bear_fast_exit`](pre-registrations/f2_management/bear_fast_exit.md)
    (§2.4). Default: no config change
    ([record](study-results/f1_selection/bear_arm.md)).

11. **OPEN — the shipped BEAR_HE clause reads negative.**
    `exit_switch_structure_study` Q2 prints Δ=−4.5205 with 47% retained on the
    shipped key. That is an observation rather than a registered trigger: the
    census in `exit_switch_mech_study` is underpowered at 8 affected dates of
    25. Stays open behind the same bear-debit question as item 10; the
    default is that §5 stands
    ([operator reading](study-map.md#operator-reading-2026-09-20)).

<a id="s0c"></a>
## 0c. Study suite — historical, resolved 2026-08-14

The 2026-08-14 six-failure diagnosis. Nothing here is a live task. Code and
tests still cite it as "§0c(A)", "§0c(B)", "§0c(C)", so the labels stay and
point at the record:

- **(A) The `DEBIT_PROD` exact-replay gate** — fixed by classifying rows
  exact / near / superseded / HARD instead of asserting bit-exact replay. The
  diagnosis, the measured 12 superseded rows and why they are kept:
  [archive/15 §study-suite triage FIXED](archive/15-era-scoping-suite-repair-and-selection-order.md#2026-08-14--study-suite-triage-fixed-the-exact-replay-gate-now-classifies-instead-of-asserting-bear_position_studys-r-is-re-replayed-and-the-exit_basis-column-turns-out-to-be-unusable).
  Pinned by `tests/test_exit_replay_gate.py`.
- **(B) `combined_exit_study` and `underlying_exit_study`** — retired
  2026-08-14, deleted 2026-09-05; inputs unrecoverable. The record is
  [`study-map.md` §management](study-map.md#management), the trail
  [archive/02](archive/02-credit-debit-split-attempts-8-12.md). Do not
  resurrect them against surviving files.
- **(C) `v4_bridge` exit 3** is a designed refusal, not a defect. How the
  runner learned the word:
  [archive/15 §`run --all` is GREEN](archive/15-era-scoping-suite-repair-and-selection-order.md#2026-08-14--run---all-is-green-two-dead-studies-retired-and-designed-refusal-is-now-a-status-the-runner-understands-rather-than-a-failure).
- **`exit_basis`** is readable on `v4`, unreadable on `v3`, and never the way
  to ask whether a row replays. Rule and evidence: §3 below and
  [archive/18 §`exit_basis` re-measured](archive/18-hedge-programme-exit-basis-and-text-loop.md#2026-09-02--exit_basis-re-measured-the-ban-was-right-for-v3-and-wrong-for-v4-the-proxy-half-never-wrote-at-all).

<a id="s1"></a>
## 1. Closed since the last handoff

One line each. Do not re-open; follow the link for the detail.

| Closed | Date | Outcome | Record |
|---|---|---|---|
| `AnalysisClaude` doubled dates | 2026-09-07 | 37 rows of the earlier run deleted on 3 dates; the pipeline now REFUSES a date it has analysed. One decision left behind, §0 | [`current.md`](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-07--the-three-doubled-analysis-dates-are-repaired-the-pipeline-now-refuses-a-date-it-has-analysed) |
| Neutral-date campaign, queue b | 2026-09-04 | COMPLETE; exports refreshed to 166 dates; suite re-run; nothing ships | [`current.md`](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-04-late--first-book-with-2026-dates-export-refreshed-suite-re-run-nothing-ships-the-year-clause-bites-campaign-b-closed) |
| `concurrency_correlation` | 2026-09-04 | NOISE on both eras; `RESTATEMENT` on 2026-09-19, still nothing queued | §2.0 |
| `hedge_concentration` | 2026-09-04 | PRECONDITION-NULL, graded | §2.1 |
| `trigger_entry` | 2026-09-04 | LATE-ENTRY on v4 and v3 | [record](study-results/f1_selection/trigger_entry.md) |
| Text thread as an edge search | 2026-09-04 | `text_features` NULL, `exit_from_text` E1 CONTRARY, `prompt_eval` variance floor set. §2.9 survives as a stability item only | [archive/18](archive/18-hedge-programme-exit-basis-and-text-loop.md#2026-09-02--the-text--backtest-loop-built-and-first-run-text-is-the-last-untested-column-family-and-it-nulls-the-models-own-stop-is-contrary-on-bull-calls), [`current.md`](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-04--hedge_concentration-graded-and-21-closed-concurrency_correlation-built-and-first-run-noise) |
| `exit_drawdown` | 2026-09-05 | UNDERPOWERED on PRIMARY; the two powered `all` cells NULL | [record](study-results/f2_management/exit_drawdown.md), [`current.md`](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-05--exit_drawdown-new-f2-walk-forward-exit-hypotheses-on-account-level-drawdown--underpowered-on-primary-the-two-powered-all-cells-are-null) |
| `hedge_portfolio` | 2026-08-31 | UNDERPOWERED, and ARM M MEASUREMENT-ONLY; population `all` ratified | [record](study-results/f5_hedging/hedge_portfolio.md), [pre-registration](pre-registrations/f5_hedging/hedge_portfolio.md) |
| `hedge_timing` | 2026-08-28 | GAP-UP CONTRARY; §4 prohibition ACCEPTED 2026-09-06. The hedge stays; its trigger is §2.10 | [`deployment-evidence.md`](deployment-evidence.md#hedge-timing-triggers-2026-08-28--one-prohibition-accepted-2026-09-06-one-closed-question-one-untestable-habit) |
| `hedge_sizing` | 2026-08-24 | pick line PULLED; far-OTM prohibition retained; sleeve is operator policy | [archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md#2026-08-24-late--bear_deploy-registered-and-graded-pick-line-pulled-sleeve-relabelled-operator-policy-far-otm-prohibition-retained) |
| `selection_order` | 2026-08-14 | UNDERPOWERED at G0; do not re-run on these dates | [archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md#2026-08-14--selection_order-run-power-stopped-at-g0-every-re-ordering-moves-714-of-the-book-so-no-arm-reaches-the-pre-registered-floor--nothing-read-nothing-refuted) |
| `volume_signal` | 2026-08-13 | NULL; the volume column is closed | [archive/14](archive/14-volume-signal-demotion-and-audit.md#2026-08-13--volume_signal-run-null--the-volume-column-is-closed) |

<a id="s2"></a>
## 2. Open queue

The numbers are stable labels, not a ranking. Pick-up order is roughly §2.2,
§2.5, §2.10, §2.9, then the parked items as dates arrive.

<a id="s2-0"></a>
### 2.0 `concurrency_correlation` — CLOSED, nothing ships

CLOSED and still closed. The 2026-09-19 run prints `RESTATEMENT`: K 5 /
same-direction-and-sector clears X2 and X3, then loses the gain under the X7
delta control, so it restates `portfolio_delta`'s ARM B and ARM D rather than
adding anything. No arm clears the whole conjunction and nothing is queued.

One thing did change. X4, the era-stability criterion, prints `PENDING` by
construction on a single-era run, so the 2026-09-04 hand settlement of it is
withdrawn. Nothing rested on it: every arm was already capped below adoption
([record](study-results/f4_deployment/concurrency_correlation.md),
[entry](current.md#2026-09-20--suite-re-run-read-in-full--18-of-31-verdicts-moved-two-touch-shipped-rules),
[arm labels](arm-index.md#concurrency_correlation)).

<a id="s2-1"></a>
### 2.1 The max-drawdown hedge question — CLOSED 2026-09-04

CLOSED 2026-09-04. `hedge_concentration` Stage 1 is PRECONDITION-NULL on a
powered read, graded clean under the two-analyst protocol; Stage 2 never ran.
Do not re-open, and do not register a fourth trigger study over these dates and
columns: every mechanical rule for WHEN to hedge is tested and none survives,
WHETHER the sleeve pays has never been powered, and the operator's hedge-open
request is §2.10
([closure](deployment-evidence.md#the-queued-max-drawdown-question-is-closed-for-concentration-gated-hedging-2026-09-04-hedge_concentration-stage-1),
[the distinction it rests on](deployment-evidence.md#the-hedge-trigger-is-dead-the-hedge-instrument-is-unmeasured-closing-note-2026-09-04),
[DELETED row in `study-map.md`](study-map.md#hedging); the record was deleted
2026-09-08 and is held in git at `44bbfb2`). The deferred ARM C prose control is
parked in §2.7.

<a id="s2-2"></a>
### 2.2 v4 composition bridge — OPEN, waits on new dates

`v4_bridge` prints `VERDICT: LADDER UNVALIDATED ON v4`, and on the 2026-09-19
book four of the five pre-registered composition tests shift. The exception is
credit share, which is within noise; structure mix, plays per day, bear share
and ladder tier mix all move
([record](study-results/f1_selection/v4_bridge.md)). Per the
[pre-registration](pre-registrations/f1_selection/v4_bridge.md): keep deploying
under the v3-derived rules and do not re-derive the ladder on v4 rows yet.

- **Unblocks when** the live 2026-08/09 dates price, or later ones. Backfill
  dates do not count (§0), with one exception the operator ruled on 2026-09-22:
  a backfilled date outside `[2024-01, 2026-05]` counts as v4 evidence, because
  no shipped rule was fitted on it. June and July 2026 are the first such dates
  ([entry](current.md#2026-09-23--junejuly-2026-backfill--24-dates-analysed-on-v4-11-priced-the-rest-pending)).
  The model-recall caveat is resolved for them: the engine's default model is
  `claude-opus-5`, whose knowledge cutoff is May 2026, so a June or July 2026
  session sits after it and the analysis cannot be recall of that day's tape.
  The cutoff is stated by the running agent's own session context; neither this
  repo nor the `claude-api` skill documents it.
- **Do not** lower `MIN_V4_DATES`, and do not point `--v4-csv` at a v3 export.
  Its exit 3 is the designed refusal (§0c(C)).

<a id="s2-3"></a>
### 2.3 Calendar-as-hedge — BLOCKED ON NEW DATES

Nothing to run until the book has materially more dates. What the study asked,
what each gate last read, and why the fill rate rather than the date count is
the wall are in the spine,
[Q2](../scripts/backtest_study/f5_hedging/README.md#q2-what-to-hedge-with).

- **Unblocks when** the book grows: the worst-decile cell needs roughly 320
  deployed dates, twice the book
  ([walls](../scripts/backtest_study/f5_hedging/README.md#known-walls)).
- **The far leg is fetchable.** `fetch_far_legs.py` (2026-09-08) fetches the calendar's
  far call for every anchor whose near-expiry grid names K*; the study's R2 gate, not
  the cache, is what blocks the post-fetch read ([record](archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md#2026-09-08-eighth--far-call-fetch-run-twice-the-scraper-was-re-issuing-the-pages-three-month-default-range-fixed-178-lost-cache-files-restored-hedge_structure-stays-blocked-at-r2)). The 601 anchors
  with no paired grid still need `fetch_sweep_legs.py`'s near put.
- **Read H3 with this caveat:** its drawdown basis is qualified in the spine,
  [Q3](../scripts/backtest_study/f5_hedging/README.md#q3-how-much-to-hedge), and in
  [`deployment-evidence.md`](deployment-evidence.md#the-curve-d3-was-read-on-understates-drawdown-2026-08-31-hedge_portfolio-arm-m).
- Carry-forwards, post-hoc and not candidates: the RANGE+C/L-VOL calendar cell
  and the H2 clause amendment, both in the
  [record](study-results/f5_hedging/hedge_structure.md).

<a id="s2-4"></a>
### 2.4 Bear sub-0.50 give-back — the `be_after` route is closed; the pattern is not

CLOSED as a route, with nothing to run: `bear_giveback` found the give-back
lives in the underlying's path, not the option mark
([record](study-results/f2_management/bear_giveback.md)), and the shipped
breakeven stop was reverted 2026-08-24 when its rollback trigger fired
([`deployment-evidence.md`](deployment-evidence.md#the-bear-debit-peak-triggered-breakeven-stop-shipped-2026-08-11--reverted-2026-08-24)).

- **The trigger** fired 08-24, un-fired 08-27, fired again 09-04 on the 2026
  column alone, and on 2026-09-19 fires on all three of its clauses. The stop
  is already reverted, so there is nothing to do, and nothing un-reverts
  without a fresh registration. The lesson is that a 60-row floor on a
  backfilling book is not a decision procedure (§2.6).
- **No longer held:** [`bear_arm` B2](arm-index.md#bear_arm)'s exit-fix
  criteria were met by `sl .50` on 2026-09-04 and are `NOT met` on 2026-09-19,
  at Δ=+0.030 with CI [−0.003, +0.061]
  ([record](study-results/f1_selection/bear_arm.md)).
- **Drafted 2026-09-22, waits on the operator:** a fast exit, meaning a small
  profit target or a stop after a few sessions, was never tested on bear
  debits.
  [`bear_fast_exit`](pre-registrations/f2_management/bear_fast_exit.md) is
  the draft. It runs only after the whole-book re-price (§0, item 8). The
  exploratory read expects a loss cut that still loses after costs
  ([entry](current.md#2026-09-22-later--bear-debits--a-fast-exit-cuts-the-loss-still-loses-after-costs)).

<a id="s2-5"></a>
### 2.5 Live walk-forward — the journal is collecting it; Stage 2 is not written

OPEN, waiting on live fills. v3 tuning is closed and live fills are meant to be
the evidence. The `SUBSTITUTED` match category shipped 2026-08-11
([archive/10](archive/10-post-closeout-ops-and-live-evals.md)). Still open: the
Stage 1/2 fill mapping, and the live-vs-tier eval of whether realized live P&L
orders A > B > C. Also worth tracking: the operator substituting a naked leg
where a spread was emitted, an untested instrument.

The daily journal (`make journal`) IS the Stage 1 fill mapping: every run
matches the day's Flex fills to the emitted plays, stamps a tier, and appends to
`journal/trades.csv`. On 2026-09-09 the 26 sessions from 2026-07-01 to
2026-08-13 that predate the daily loop were replayed into it, so the journal now
covers every session since analysis coverage began on 2026-07-08
([entry](archive/21-ladder-overlay-closed-the-journal-walk-forward-and-the-pricer-mirror.md#2026-09-09--journal--the-july-to-mid-august-fills-are-journalled-the-live-walk-forward-has-55-mapped-rows-over-20-signal-dates)).
Stage 2, the live-vs-tier P&L reading, is NOT written: nothing tallies the
journal by tier. Census on 2026-09-09:

| | Count | Gate |
|---|---|---|
| Mapped rows over signal dates | 55 over 20 | `operator_read` floor 25 dates |
| Mapped closes with realized P&L | 22, all tier B or C | Stage 2 gate 30 to 50 closes |
| Tier-A closes | 0 | the A > B > C question needs at least one |

**The operator-read test belongs here** — to pre-register before any code, f4,
`operator_read`. `text_features` showed the signal text carries no
machine-readable edge ([record](study-results/f1_selection/text_features.md)),
but the operator reads it qualitatively to decide what to trade, so its value is
realised in the PICK and only the journal can measure that.

- **Design.** Among ladder-eligible plays per date, compare TAKEN (journal
  `EXACT`, `STRUCTURE`, `CORE`, `SUBSTITUTED`) against NOT TAKEN, paired by
  date, on [R](glossary.md#r) and [PF](glossary.md#pf) with
  `protocol.pf_paired_by_date` never without mean R. The declared covariate is
  the entry-session price move, because `next_day_move` showed day-0
  confirmation is a confound
  ([record](study-results/f2_management/next_day_move.md)).
- **Floor:** at least 25 dates with 2 eligible plays and 1 taken. Census first;
  the journal may not have it yet.
- A positive result is a statement about the operator's read, not the prompt.
  Do NOT test this with a stripped-text `prompt_eval` candidate, which would
  remove exactly what the operator reads.

<a id="s2-6"></a>
### 2.6 Rollback triggers — a trigger that printed nothing has not been checked

OPEN; three of the four triggers wait on new dates. The census prints on every
relevant study run. The table of triggers and floors is
[`deployment-evidence.md` §Open pre-registered rollback triggers](deployment-evidence.md#open-pre-registered-rollback-triggers);
the plan is the
[pre-registration](pre-registrations/f2_management/rollback_triggers.md).
Reading on the 2026-09-19 book:

| Trigger | Reading | What it waits on |
|---|---|---|
| bear-debit `be_after 0.50` | all three clauses fire on 242 arming rows over 134 dates; already reverted (§2.4) | an operator confirmation, item 10 in §0 |
| LVOL tef-null | `STAYS GATED` on 80 affected dates, median −0.011; one of its four clauses fails | new dates |
| BEAR_HE trail | `UNDERPOWERED`, 8 affected dates of 25 | new dates |
| credit sl-none | 0 fresh `bull_put` rows of 15; the window starts after 2026-07-13, unreachable by backfill | live dates after July 2026 |

The `be_after` census has now given four answers on four runs, which is the
lesson recorded in §2.4: a 60-row floor on a backfilling book is not a
decision procedure. The LVOL cell's one failing clause is the median among
affected dates; the 08-24 `CLEARED` never survived two exports, so the
operator's hold was right.

<a id="s2-7"></a>
### 2.7 Parked or blocked long-term

Each of these is blocked on what its bullet names; none is scheduled.

- **Credit exit knobs** — unvalidated; needs a credit-heavy window. The v4
  credit book calibrates exactly and the corrected baseline is in place, but the
  fresh window starts after 2026-07-13, so no backfill can reach it. Census and
  the `sl 1x` comparator print on every credit run
  ([record](study-results/f2_management/exit_mechanism_study-credit.md)).
- **Long-dated blind spot** — `h ≥ 180` is unpriceable with real data and the
  BS proxy tier is OFF. Never read BS proxy rows as long-dated evidence.
  **Debit side only** (operator, 2026-09-05): the credit knobs above do not wait
  on this
  ([`current.md` 2026-09-05](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-05-later--overviewmd-and-glossarymd-rewritten-for-a-reader-who-has-lost-the-thread-the-long-dated-blind-spot-is-scoped-debit-only)).
- **Per-regime exit switch** — `STAYS GATED` on the 2026-09-19 book. The
  mech-keyed switch fails two of six criteria; the structure-keyed one now
  fails four of six, and its Q2 line reads the shipped BEAR_HE clause
  negative, which is item 11 in §0
  ([mech](study-results/f2_management/exit_switch_mech_study.md),
  [structure](study-results/f2_management/exit_switch_structure_study.md)).
- **`portfolio_delta` ARM B ceiling 1.00 — CLOSED 2026-09-19.** The study
  prints `NOISE` and no ceiling clears, so the parked
  CANDIDATE-FOR-INDEPENDENT-WINDOW is withdrawn and nothing waits on a window.
  Criterion 1 alone fails. Its paired mean gain is +0.0519 R, on a CI of
  [−0.0333, +0.1407]
  ([record](study-results/f4_deployment/portfolio_delta.md),
  [arm labels](arm-index.md#portfolio_delta)).
- **`exit_drawdown`'s design** — parked on dates, not design. Any CANDIDATE
  from it would need the independent window, never a re-cut of these dates.
  The ARM P ack is owed first (§0).
- **Prompt and infra** — the `analysis_pipeline/core.py` refactor is deferred;
  the PostToolUse hook still never runs pytest; the delegation-nudge hook is
  advisory by design.
- **`hedge_portfolio` ARM C prose control** — deferred from §2.1, not dropped:
  concentration-matched sessions with no hedge-pressure signal. Register it
  only when the book has materially more parsed dates; today it would be
  another arm that cannot bite
  ([pre-registration](pre-registrations/f5_hedging/hedge_portfolio.md)).
- **`scripts.backtest` already-run guard — DONE 2026-09-07.** The backtest
  refuses a play its results tab already holds (`_drop_already_backtested`,
  commit `a9b51c8`), matching the analysis-side guard shipped the same day; the
  2025-12-22 `SPY` row came from a backtest re-run, not a doubled analysis.

<a id="s2-8"></a>
### 2.8 Per-play `invalidation` exits — CLOSED 2026-09-02, do not build

CLOSED 2026-09-02, do not build. `exit_from_text` answered it: the model's own
invalidation level as an underlying-close stop is CONTRARY on
`bull_call_spread` / LVOL and NULL or UNDERPOWERED elsewhere on v4. The
`bear_put_spread` cells are still NULL on the 2026-09-19 book, but the only
criterion they now fail is the CI, and the year column is positive at the 1%
and 2% buffers ([record](study-results/f2_management/exit_from_text.md),
[arm labels](arm-index.md#exit_from_text); the original gap and its two parser
cautions: [archive/00](archive/00-backtest-engine-backlog-2026-06.md)).

The study did print its first `CANDIDATE` on 2026-09-19, but on E2 rather than
E1. E2 is an intake filter and can never ship as an exit rule, so this section
stays closed
([entry](current.md#2026-09-20--suite-re-run-read-in-full--18-of-31-verdicts-moved-two-touch-shipped-rules)).

<a id="s2-9"></a>
### 2.9 `prompt_eval` — a STABILITY item, not an edge item

OPEN but do not pick it up ahead of §2.2: it is a v5 prompt bump if adopted, and
nothing in the book says it changes P&L. Harness built 2026-09-03
([pre-registration](pre-registrations/f1_selection/prompt_eval.md)). The
PROD × 3 variance run is DONE: floor 0.0419 on paired ΔR, below which no
difference may be claimed ([record](study-results/f1_selection/prompt_eval.md)).

- **The one candidate worth writing:** a WRITTEN decision rule for
  BULL/RANGE/BEAR over rollup fields the model already cites, so identical
  inputs give an identical label. The variance run's tier-mix swing traced to
  that label flipping on 2 of 5 dates
  ([`current.md`](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-04--hedge_concentration-graded-and-21-closed-concurrency_correlation-built-and-first-run-noise)).
- **Do not write** the "adopt `mech_regime`" candidate: mech-only selection is
  refuted on v3 and null on v4
  ([record](study-results/f1_selection/mech_regime_recut.md)).
- **Test repeatability before P&L.** Read the candidate's per-date regime labels
  and tier mix across three repeats against PROD's. Only a steady label goes on
  to the 40-date backfill score.

```bash
# repeatability first (~30 opus calls); a used --run-dir is refused
python -m scripts.backtest_study run prompt_eval -- run --candidate <dir> \
  --dates backtests/prompt_eval/variance-dates.txt --repeats 3 --date-set OTHER \
  --run-dir backtests/prompt_eval/repeat-$(date +%Y%m%d) \
  --variance-json backtests/prompt_eval/variance-20260903/variance.json
# then the backfill score (~80 opus calls)
python -m scripts.backtest_study run prompt_eval -- run --candidate <dir> \
  --dates backtests/prompt_eval/backfill-dates.txt \
  --run-dir backtests/prompt_eval/backfill-$(date +%Y%m%d) \
  --variance-json backtests/prompt_eval/variance-20260903/variance.json
# and per new live date
python -m scripts.backtest_study run prompt_eval -- accumulate --candidate <dir> \
  --date YYYY-MM-DD --run-dir backtests/prompt_eval/live
```

<a id="s2-10"></a>
### 2.10 A hedge-open indicator — OPEN, no candidate yet

The sleeve stays and WHEN to open one is an open question with nothing in it:
the operator accepted the [§4](../docs/deployment-rules.md#s4) gap-up
prohibition on 2026-09-06 and keeps hedging. It waits on a signal the book does
not carry yet. The four candidates that have been tested, and why each died, are
in the spine,
[Q1](../scripts/backtest_study/f5_hedging/README.md#q1-when-to-open-a-hedge).

- **What does NOT count as a candidate:** another timing rule cut from these
  dates and these columns (§2.1), or a re-read of the close-bucketed curve
  ([basis](../scripts/backtest_study/f5_hedging/README.md#q3-how-much-to-hedge)).
- **What would count:** hedge flow in the analysis, or a live exposure reading
  from the journal — measured on the mark-to-market curve
  (`backtest_study/lib/mtm_curve.py`), on dates chosen without a rule. Both
  sources are the same ones §2.5 waits on.
- **Census first, as with `operator_read`.** Before any registration, count how
  many book dates carry the proposed signal at all. Three of the four dead
  triggers died on power, not on sign.

<a id="s2-11"></a>
### 2.11 Robustness follow-ups — OPEN, nothing waits on dates

The queue from [`robustness-review.md`](robustness-review.md), in its
[suggested order](robustness-review.md#order). The seven investigations there
(cost sensitivity, same-date benchmark, beta decomposition, live slippage,
sealed holdout, join attrition, programme-wide null) are candidates, not
registered studies: each gets its own pre-registration before it runs. The code
fixes are not studies and need none.

**Status 2026-09-07 (later).** Twelve items built and reviewer-approved, none
committed ([log](archive/19-2026-column-exit-drawdown-and-duplicate-repairs.md#2026-09-07-later--robustness-review-twelve-items-built-six-landed-in-the-tree-six-wait-in-two-worktrees-for-the-campaign-to-end)).

| Where | Items | Next |
|---|---|---|
| Main, committed | P1, P2, P3, P6, P8, A5 | done |
| Main, merged `3e5c2dc` | B1, B2, B3, B5, A1, A4 | done |
| Drafts, not registered | N1, N2, N5 | operator accepts each, after the decisions each names |
| Not started | A2, A3, B4, B6, B7, P4, P5, P7, N3, N4, N6, N7 | A2/A3 need the tab header; P5 is the Stage 2 build |

The `3e5c2dc` merge landed 2026-09-08, after the queue-D campaign stopped with
six failed dates. Both results-tab headers gained `pct_stale_days`,
`cost_total` and `cost_basis`, and the suite is 3,878 green. The six failed
queue-D dates (2025-03-19, 03-24, 03-27, 04-09, 04-23, 04-28) were retried after
the merge and all six priced, so they are the only rows in the book that ran
under the cost model and the pre-entry grid fix.

**What the merge left.** Found 2026-09-08 when the queues finished; the list
has grown since. One line each, with the entry that holds the story.

| Item | Status | Date | Story |
|---|---|---|---|
| The split is not readable on `cost_basis` | prose only, done | 2026-09-08 | below |
| `history.py` unlinks a cache file before a refetch that can fail | RESOLVED | 2026-09-19 | [entry](current.md#2026-09-19-later--the-option-history-cache-is-no-longer-deleted-before-a-refetch-and-proxy-rows-carry-the-cost-columns) |
| Proxy rows carry none of the three cost columns | RESOLVED in code, not backfilled | 2026-09-19 | [entry](current.md#2026-09-19-later--the-option-history-cache-is-no-longer-deleted-before-a-refetch-and-proxy-rows-carry-the-cost-columns) |
| B5's zero-bid re-mark is not mirrored by `bear_rewrap` | RESOLVED | 2026-09-17 | [archive/21](archive/21-ladder-overlay-closed-the-journal-walk-forward-and-the-pricer-mirror.md#2026-09-17--bear_rewrap-pricer--b5-zero-bid-re-mark-mirrored-r2-at-1320--1321) |
| B5 on a stale one-sided quote fabricates a credit | RESOLVED; the stored row re-priced | 2026-09-19 | [entry](current.md#2026-09-19--backtest-entry-pricing--a-sold-leg-with-no-bid-fills-at-0-and-a-debit-that-prices-to-a-credit-is-refused), [re-price](current.md#2026-09-19-later-still--the-2025-04-09-re-price-and-the-two-mirror-drifts-it-exposed-hedge_structure-unblocked) |
| `bear_rewrap`'s mirror derived the entry day instead of reading it | RESOLVED, verdict-neutral | 2026-09-19 | [entry](current.md#2026-09-19-later-still--the-2025-04-09-re-price-and-the-two-mirror-drifts-it-exposed-hedge_structure-unblocked) |
| The exit fill keeps the sign-independent liquidation mark | RESOLVED, not backfilled | 2026-09-19 | [entry](current.md#2026-09-19-fourth--the-exit-fills-on-the-next-two-sided-day-not-on-the-trigger-days-bid-less-mark), [column](../docs/backtest-reference.md#how-the-exit-was-filled--exit_fill) |
| The 17 legacy rows whose exit was booked before their fill | DETECTED, 14 reach the book | 2026-09-19 | [diagnosis](current.md#2026-09-19-fifth--tlt-2025-04-01-is-not-a-new-defect-it-is-a-phantom-pre-entry-exit-and-16-others-like-it), [detector](current.md#2026-09-19-sixth--the-14-pre-fill-exits-are-now-detected-not-just-counted) |
| The stored book no longer reproduces under current code | MEASURED; four decisions owed | 2026-09-20 | [census](current.md#2026-09-20-later--stored-book--a-cache-only-re-price-moves-370-of-2234-rows), §0 items 6 to 9 |
| A third of the suite was truncated in its own record | FIXED | 2026-09-20 | below |
| Two per-era records carried a junk excerpt | FIXED | 2026-09-20 | below |
| A `bear_put_spread` can be built strike-inverted | RESOLVED | 2026-09-20 | [entry](current.md#2026-09-20-third--backtest-classifier--six-priced-rows-used-strikes-from-the-narrative-fixed), below |
| Six `bear put spread` plays classify as `bear_call_spread` | OPEN | 2026-09-20 | below |
| A leg quoted `bid == 0` can still fill at that day's `Open` print | OPEN, operator decision | 2026-09-08 | below, §0 item 9 |
| The debit-to-credit gate also fires on BS-modelled legs | MOOT: BS abolished | 2026-09-23 | below |
| A credit priced to a debit was sized on its fake premium (TLT 2025-04-04) | RESOLVED in code, not re-priced | 2026-09-23 | [entry](current.md#2026-09-23--backtest-pricing--black-scholes-is-abolished-four-entry-refusals-real-per-leg-greeks) |
| One corrupt cache file (META 630P) set a position's underlying and greeks | RESOLVED, file quarantined | 2026-09-23 | [entry](current.md#2026-09-23--backtest-pricing--black-scholes-is-abolished-four-entry-refusals-real-per-leg-greeks) |
| Junk quotes set the cost, the daily mark and the entry fill | RESOLVED in code, uncommitted, not re-priced | 2026-09-24 | [entry](current.md#2026-09-24-latest--backtest-pricing--a-junk-quote-is-no-longer-a-price-a-mark-or-a-spread) |
| Research mirrors do not follow the junk-quote rule | OPEN | 2026-09-24 | below |
| Wide quotes just inside the junk line still dominate cost | RESOLVED by the width line | 2026-09-24 | [entry](current.md#2026-09-24-latest--backtest-pricing--a-junk-quote-is-no-longer-a-price-a-mark-or-a-spread) |

The rest of this section is the detail that lives nowhere else.

**Research mirrors do not follow the junk-quote rule (2026-09-24).** Production
now judges every quote with `simulate._is_junk_quote`. These research paths
still price the old way. None was changed.

| Mirror | What it still does |
|---|---|
| `f3_structure/bear_rewrap.py` | Marks by `_zero_bid_mark`, fills entries by `_entry_side_mark`: a bought zero-bid leg pays the ask, a junk day marks at its mid |
| `lib/overlay_campaign.py::CachePrices` | Prices through `bear_rewrap`, and `_row_spread` charges slippage on junk spreads |
| `lib/hedge_instrument.py` | Marks off `_mark`, the raw mid |
| `lib/reprice_targets.py` | Claims rows with `_entry_side_mark`, the pre-junk entry test |

`tests/test_bear_rewrap_zero_bid.py::test_the_mirror_and_production_agree_on_an_open_print_entry`
now fails for this reason: production refuses the bought zero-bid leg, the
mirror pays the ask.

**The `cost_basis` split.** `_apply_costs` writes `cost_basis` empty whenever
both cost knobs are 0, which they are, so it is blank on every
`BacktestResults` row. Split the two populations on `cost_total` or
`pct_stale_days` being non-blank instead. That is 14 rows, the six retried
queue-D dates.

**A third of the suite was truncated in its own record.** The recorder cut the
conclusion block at `MAX_EXCERPT_LINES = 12` with no marker, so a section
quoting 12 of 358 lines read as complete. Thirteen of 35 studies sat exactly
at the cap, and three separate readers reported that truncation as ambiguity
in the study: `staged_exit` ("only 10 grid cells are recorded"),
`text_features` ("ARM B is not determinable") and `exit_from_text`.

Fixed 2026-09-20 in three parts. The cap is now 40 lines, which quotes 11 of
the 13 whole. That costs about 11 KB a suite run. The section now states what
it cut
(`40 of 357 block lines; 317 not quoted`). A block that is still cut carries a
tally of the study's own verdict words
(`UNDERPOWERED 294, NULL 27, CONTRARY 15, CANDIDATE 4`). The tally is a count
rather than a paraphrase, and it renders outside the fence so the quote stays
verbatim. The two that stay truncated enumerate a parameter grid rather than
state an answer, which is the argument for a tally over a higher cap.

**Two per-era records carried a junk excerpt and could not detect a verdict
change.** The title regex in `scripts/study_map/summary.py` matched
`\bVERDICT\b`, which does not match the plural `VERDICTS`, because `\b` wants
a non-word character after the T. Both `financed_spread` and `ladder_overlay`
title their banner `VERDICTS`. So both fell through to the `matched` fallback
and recorded a line of the report's own explanatory prose as their answer, for
four runs. One of them reads "...say POWER-STOPPED and mean the".

Found 2026-09-20 comparing the suite re-run against the previous one, when the
record could not answer whether either study had moved. Both now record their
real `VERDICTS` block, every cell token. The disclaimer regex was widened in
step, because widening the positive rule alone would have made
`NO VERDICTS ARE READ FROM ANYTHING BELOW` a conclusion — the in-sample leak
it exists to stop, and a test caught it.

Both fixes land a commit later than the run they were found on. The recorder
keys on (era, sha, inputs), so the `8e9b6a7` sections keep their truncated and
junk excerpts, and the first usable before/after is the next suite run's.

**A `bear_put_spread` can be built strike-inverted — resolved 2026-09-20.**
`IWM` 2024-03-25 on `BacktestResults` is labelled `bear_put_spread` with legs
long 204P / short 210P, which is a bull put spread's leg order. It priced to a
−2.89 credit and was labelled CREDIT. The root cause turned out to be strike
extraction rather than leg order: those strikes came from the play's
narrative, while its header names a 200/185 bear put. The parser now reads the
header, and a vertical whose strikes are in the wrong order for its direction
is refused with `skip_reason = inverted_vertical`.

**Six `bear put spread` plays classify as `bear_call_spread`.** Their
narrative mentions bear call spreads and the classifier takes the label from
it. They are AVGO, ITB, LLY, MU, TLT and SMH. All six are vetoed before
pricing, so nothing prices wrong today. Count them again after any change to
the structure parser.

**A leg quoted `bid == 0` can still fill at that day's `Open` print.** The
2026-09-19 entry rule sits below the entry-day `Open` fill, so it reaches only
legs that had no print. A census of the 2026-09-08 exports found legs quoted
`bid 0` with an ask on the entry day that filled at a print anyway.

| Tab | Rows | Share | Sign flips | Median move | Max move | Predate the B5 fold |
|---|---|---|---|---|---|---|
| `BacktestResults` | 22 of 598 | 3.7% | 3 | 0.65 | 4.06 | 21 of 22 |
| `BacktestProxy`, priced | 27 of 776 | 3.5% | 3 | 0.99 | 4.89 | 26 of 27 |

They concentrate in illiquid ETF puts: HYG dominates both, then LQD, XLI, XLE,
EEM and FXI. A print on a contract nobody bids for is as questionable as the
mid was. This was deliberately not changed, because almost every one of those
rows predates the B5 fold, so extending the rule there would re-price four
months of already-recorded pre-fold evidence. The decision is item 9 in §0:
leave the `Open` fill alone, or extend the side rule with a before and after.

**The exit-fill census is approximate.** It reconstructs the exit day from
`days_held` over a business-day grid rather than reading it from the stored
grid, so its counts are an order of magnitude and not a row list.

**Black-Scholes is abolished (2026-09-23).** The backtest has no model tier
now, so the note below is moot for new rows. It stays because the stored rows
it counts still exist. Re-pricing them is a `--redo` the operator has not
ordered.

**The debit-to-credit gate also fires on BS-modelled legs.**
`_refuse_debit_priced_to_credit` cannot tell a modelled mark from a quoted
one, and in the proxy's method-2 `bs` tier a modelled short leg can
legitimately price above a real long leg. Such a play is now refused rather
than written. Two committed test fixtures built exactly this shape and had to
be corrected. A deliberate `bs_fallback: true` study will see fewer rows than
it did before 2026-09-19.

Measured 2026-09-19, it is effectively moot.

| Population | BS-tagged leg-days |
|---|---|
| `BacktestResults` | 17 of 33,548 (0.05%) |
| `BacktestProxy` | 101 of 47,010 (0.21%) |

591 of 598 results rows are 100% real-priced. The `bs` tier is off in the
proxy (`bs_fallback: false` since 2026-08-11), studies load `include_bs=False`,
and BS survives only as the last entry in
`exit_sources: [barchart, reappearance, bs]`. Note this in any `bs_fallback`
study's write-up. No exemption is worth building for a population this size
unless such a study is actually registered.

The drafts are [`cost_sensitivity.md`](pre-registrations/f2_management/cost_sensitivity.md),
[`mechanical_benchmark.md`](pre-registrations/f1_selection/mechanical_benchmark.md) and
[`holdout_seal.md`](pre-registrations/f4_deployment/holdout_seal.md). `holdout_seal`
names the conflict with §2.2 and §2.6 and leaves the choice open.

<a id="s2-12"></a>
### 2.12 Hedge programme follow-ups — both picked up 2026-09-08; one read still blocked

Two items left over from the 2026-09-07 consolidation, both worked 2026-09-08. The
plan was deleted once executed; the programme's four questions are
[`f5_hedging/README.md`](../scripts/backtest_study/f5_hedging/README.md).

| Item | What it is | Why it is open |
|---|---|---|
| Far-call fetch (Q2) — COLLECTOR BUILT AND RUN 2026-09-08; the read is blocked | `scripts/collector/fetch_far_legs.py`: for every (date, ticker, near expiry) the book entered, the call at the paired ATM strike on the ticker's first later cached expiry; imports `fetch_sweep_legs.py`'s manifest and scrape loop, own manifest `backtests/sweep_cache/far_legs_manifest.csv`. | Pre-run note and outcome in `current.md` ([note](archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md#2026-09-08-seventh--far-call-fetch-for-hedge_structure-q2-pre-run-note-then-the-fetch-r2-fails-on-the-new-export-before-any-of-it), [outcome](archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md#2026-09-08-eighth--far-call-fetch-run-twice-the-scraper-was-re-issuing-the-pages-three-month-default-range-fixed-178-lost-cache-files-restored-hedge_structure-stays-blocked-at-r2)). The first run fetched almost nothing because the scraper re-issued the page's three-month default range; fixed in `session.py` and re-run. `hedge_structure` cannot print H0 on this export because R2 fails on five post-fold rows (§2.11); re-run the study once that is decided. |
| Two sleeve-sizing bodies outside the library — CLOSED 2026-09-08 | `account_sim` and `portfolio_delta` each picked one position a day in its own sorted copy. | Both call `lib/hedge_criteria.sleeve_pick` now, and both printed identically before and after on the 2026-09-08 export ([record](archive/20-hedge-programme-reorg-queues-cde-and-cache-loss.md#2026-09-08-sixth--the-two-sleeve-sizing-bodies-in-account_sim--portfolio_delta-are-folded-onto-libhedge_criteriasleeve_pick-identical-print)). |

<a id="s2-13"></a>
### 2.13 `ladder_overlay` — CLOSED 2026-09-16; nothing ships, no cell beats the plain spread

CLOSED 2026-09-16, nothing ships: registered 2026-09-10, run on v4 the same
evening once the 11,551-contract scrape finished and the cache snapshot was
pushed, and on v3 on 2026-09-16; all ten graded cells print `NULL` on v4, six
print `NULL` and the four sell-at-entry cells are `UNDERPOWERED` on v3, and two
analysts and the validator agreed on every number. Three build rulings are
folded into the registration tagged `Resolved at build`; nothing is left open,
and the thread re-opens only on genuinely new dates (§0)
([write-up](archive/21-ladder-overlay-closed-the-journal-walk-forward-and-the-pricer-mirror.md#2026-09-16--ladder_overlay--nothing-ships-no-ladder-or-naked-put-cell-beats-the-plain-spread-on-v4-or-v3),
[record](study-results/f3_structure/ladder_overlay.md),
[registration](pre-registrations/f3_structure/ladder_overlay.md)).

<a id="s3"></a>
## 3. Standing rules — settled, do not re-open

One line each, with the evidence.

**Selection and scoring**

- Trigger-gated entry is LATE-ENTRY; E2's census gap was the day-0 move, not
  the text ([`trigger_entry`](study-results/f1_selection/trigger_entry.md)).
- The day-X / ±Y% / ±$Z exit formula is `staged_exit` and it is null; do not
  re-register it under a days or DTE anchor
  ([record](study-results/f2_management/staged_exit.md)).
- Walk-forward exit selection on account-level drawdown is UNDERPOWERED on
  PRIMARY and NULL where powered; do not re-register `exit_drawdown`'s arms on
  these dates ([record](study-results/f2_management/exit_drawdown.md)).
- No further text study (§1).
- `score_total` is decision-irrelevant; selection is structure × regime × entry
  geometry ([`deployment-evidence.md`](deployment-evidence.md#why-the-tiers)).
- The ML/selection search is closed; re-open on new columns only, tested within
  structure ([`ml_combination`](study-results/f1_selection/ml_combination.md)).
- `bear_call_spread` is intake-vetoed; bear debit is selection-vetoed at
  [§1](../docs/deployment-rules.md#s1) and lives in the
  [§4](../docs/deployment-rules.md#s4) sleeve only
  ([archive/14](archive/14-volume-signal-demotion-and-audit.md#2026-08-13--bear_put-demotion-mechanism-chosen-card-level-selection-veto-14-hedge-sleeve-carved-out)).

**Populations and pricing**

- v3 and v4 rows are never pooled; the score scales differ
  ([glossary](glossary.md)).
- Real and tweak pricing tiers only; filter legacy `bs` rows by `proxy_method`.
- Studies are era-scoped and the bare export filename names no population;
  `lib/era.py` is the single encoding
  ([archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md)).
- `exit_basis` is readable on v4, not v3, and never for a REPLAY question.
  Classify replay by unreachable exit reasons in `lib/replay_basis.py`;
  `lib/basis_audit.py` reports coherence and never gates (§0c,
  [archive/18](archive/18-hedge-programme-exit-basis-and-text-loop.md#2026-09-02--exit_basis-re-measured-the-ban-was-right-for-v3-and-wrong-for-v4-the-proxy-half-never-wrote-at-all)).
- `hedge_portfolio`'s registration describes the `real` stratum, not the
  ratified `all` book
  ([pre-registration](pre-registrations/f5_hedging/hedge_portfolio.md)).

**Vocabulary and process**

- ARM labels are study-local; always qualify with the study, and look labels up
  in [`arm-index.md`](arm-index.md)
  ([archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md#2026-08-24-docs--arm-labels-are-study-local-and-stay-single-letters-researcharm-indexmd-indexes-every-one-by-study)).
- A rollback trigger with no recorded census has not been checked. It is not
  "not met" until the numbers say so (§2.6).
- `study_review … --dry-run` CLOBBERS review artifacts; never use it as a
  read-only check
  ([archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md#2026-08-24--pre-registrations-consolidated-to-one-template-study_review-dry-run-clobbered-two-reviews-artifacts)).
- Never hardcode a figure off one export, in code or in report prose
  ([archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md#2026-08-24-late--bear_deploy-registered-and-graded-pick-line-pulled-sleeve-relabelled-operator-policy-far-otm-prohibition-retained)).
