# Next steps — the queue

This file is the queue and nothing else. Written 2026-08-31, cut to queue-only
2026-09-05. Every item says what it is waiting on and links to where its
evidence lives. Nothing here restates a result: for where the research stands,
read the [State of play](current.md#state-of-play) block at the top of
[`current.md`](current.md), which is authoritative. Section numbers are
**stable labels** cited from code, tests and the archive, so a closed item
keeps its number as a one-line stub with a link.

<a id="s0"></a>
## 0. Repo state — read first

- **Era and population.** `v4`, the 166-date backfilled book, exports of
  2026-09-04 20:31. Counts and the date range are in
  [the population](current.md#the-population).
- **What most of the queue waits on: genuinely new dates.** `AnalysisClaude`
  carries 2026-08-11 → 2026-09-01 from the daily pipeline with no backtest rows,
  because those options have not expired. §2.2 and §2.6 wait on them. The 13
  backfilled 2026 dates do NOT qualify. They are a correlated window
  ([where the 2026 column bit](current.md#where-the-2026-column-bit)).
- **Tests green, suite green.** Last full study-suite run 2026-09-04 on the
  166-date book, every non-retired study ran, and the one gate stop was a
  study-side pricer gap fixed the same session
  ([`current.md` 2026-09-04 late](current.md#2026-09-04-late--first-book-with-2026-dates-export-refreshed-suite-re-run-nothing-ships-the-year-clause-bites-campaign-b-closed)).
- **Two hardcoded date tables are still no-ops by construction.**
  [`mech_regime_recut`](study-results/f1_selection/mech_regime_recut.md) §(b)
  and [`regime_gap_reread`](study-results/f1_selection/regime_gap_reread.md)
  §0 list 2026-03 dates the export does not hold.
- **Rescaled tickers.** `backtests/underlying_ohlc_cache/rescaled_tickers.txt`
  lists 13 tickers after the 2026-09-05 rebuild, NVDA and GE newly among them.
  Every OHLC consumer withholds absolute dollars and cross-series comparisons on
  those; ratios stay valid
  ([`current.md` 2026-09-05](current.md#2026-09-05-later--overviewmd-and-glossarymd-rewritten-for-a-reader-who-has-lost-the-thread-the-long-dated-blind-spot-is-scoped-debit-only)).

### Waiting on the operator

Decisions owed. None of these is a study.

1. **Four real-priced rows are missing from `BacktestResults`** and are not in
   `BacktestProxy` either: 2025-12-22 TSLA and AMD `bull_call_spread`,
   2025-09-26 CRWV `bull_call_spread` and HYG `bear_put_spread`. They sit in the
   local backtest scratch with no provenance for why they are absent, so a study
   population is not patched from them. To restore, re-run per date and never
   bare, because there is no dedup
   ([data hazards](current.md#data-hazards-on-this-export-not-repaired)):

   ```bash
   make backtest ARGS="--date 2025-12-22"
   make backtest ARGS="--date 2025-09-26"
   ```

2. **The drafted gap-up hedge prohibition in
   [§4](../docs/deployment-rules.md#s4)** is HELD for the operator to accept or
   reject
   ([`deployment-evidence.md` §Hedge-timing triggers](deployment-evidence.md#hedge-timing-triggers-2026-08-28--one-drafted-and-held-prohibition-one-closed-question-one-untestable-habit)).
3. **`exit_drawdown` ARM P's "dollars ban is scoped" ack** is owed before any
   ARM P cell is ever read. Without it the module defaults to quoting
   account-level drawdown as a share of starting capital. No run has displayed
   the banner yet because every ARM P cut was UNDERPOWERED
   ([pre-registration](pre-registrations/f2_management/exit_drawdown.md)).

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
| Neutral-date campaign, queue b | 2026-09-04 | COMPLETE; exports refreshed to 166 dates; suite re-run; nothing ships | [`current.md`](current.md#2026-09-04-late--first-book-with-2026-dates-export-refreshed-suite-re-run-nothing-ships-the-year-clause-bites-campaign-b-closed) |
| `concurrency_correlation` | 2026-09-04 | NOISE on both eras | §2.0 |
| `hedge_concentration` | 2026-09-04 | PRECONDITION-NULL, graded | §2.1 |
| `trigger_entry` | 2026-09-04 | LATE-ENTRY on v4 and v3 | [record](study-results/f1_selection/trigger_entry.md) |
| Text thread as an edge search | 2026-09-04 | `text_features` NULL, `exit_from_text` E1 CONTRARY, `prompt_eval` variance floor set. §2.9 survives as a stability item only | [archive/18](archive/18-hedge-programme-exit-basis-and-text-loop.md#2026-09-02--the-text--backtest-loop-built-and-first-run-text-is-the-last-untested-column-family-and-it-nulls-the-models-own-stop-is-contrary-on-bull-calls), [`current.md`](current.md#2026-09-04--hedge_concentration-graded-and-21-closed-concurrency_correlation-built-and-first-run-noise) |
| `exit_drawdown` | 2026-09-05 | UNDERPOWERED on PRIMARY; the two powered `all` cells NULL | [record](study-results/f2_management/exit_drawdown.md), [`current.md`](current.md#2026-09-05--exit_drawdown-new-f2-walk-forward-exit-hypotheses-on-account-level-drawdown--underpowered-on-primary-the-two-powered-all-cells-are-null) |
| `hedge_exposure` | 2026-08-31 | UNDERPOWERED, and ARM M MEASUREMENT-ONLY; population `all` ratified | [record](study-results/f4_deployment/hedge_exposure.md), [pre-registration](pre-registrations/f4_deployment/hedge_exposure.md) |
| `hedge_timing` | 2026-08-28 | GAP-UP CONTRARY on both money arms; §4 prohibition drafted and HELD (§0) | [`deployment-evidence.md`](deployment-evidence.md#hedge-timing-triggers-2026-08-28--one-drafted-and-held-prohibition-one-closed-question-one-untestable-habit) |
| `bear_deploy` | 2026-08-24 | pick line PULLED; far-OTM prohibition retained; sleeve is operator policy | [archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md#2026-08-24-late--bear_deploy-registered-and-graded-pick-line-pulled-sleeve-relabelled-operator-policy-far-otm-prohibition-retained) |
| `selection_order` | 2026-08-14 | UNDERPOWERED at G0; do not re-run on these dates | [archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md#2026-08-14--selection_order-run-power-stopped-at-g0-every-re-ordering-moves-714-of-the-book-so-no-arm-reaches-the-pre-registered-floor--nothing-read-nothing-refuted) |
| `volume_signal` | 2026-08-13 | NULL; the volume column is closed | [archive/14](archive/14-volume-signal-demotion-and-audit.md#2026-08-13--volume_signal-run-null--the-volume-column-is-closed) |

<a id="s2"></a>
## 2. Open queue

The numbers are stable labels, not a ranking. Pick-up order is roughly §2.2,
§2.5, §2.9, then the parked items as dates arrive.

<a id="s2-0"></a>
### 2.0 `concurrency_correlation` — CLOSED 2026-09-04

NOISE on both eras. X4, era stability, was read by hand against the
registration's rule: no arm clears X2 or X3 in either era, so no arm is
ADOPT-eligible, and 4 of the 8 arms powered in both eras flip sign. The
verdict is era-stable and the per-arm gains are not. Nothing ships, nothing is
queued. [Record](study-results/f4_deployment/concurrency_correlation.md),
[summary](current.md#concurrency_correlation-is-closed),
[arm labels](arm-index.md#concurrency_correlation).

<a id="s2-1"></a>
### 2.1 The max-drawdown hedge question — CLOSED 2026-09-04

`hedge_concentration` Stage 1 is PRECONDITION-NULL on a powered read, graded
clean under the two-analyst protocol; Stage 2 never ran. Do not re-open, and
**do not register a fourth trigger study**: every mechanical rule for WHEN to
hedge has been tested and none survives, while WHETHER the sleeve pays has
never been powered. What would move it is an instrument test on a
mark-to-market curve on dates chosen without a rule, and that waits on dates.
[Closure](deployment-evidence.md#the-queued-max-drawdown-question-is-closed-for-concentration-gated-hedging-2026-09-04-hedge_concentration-stage-1),
[the distinction it rests on](deployment-evidence.md#the-hedge-trigger-is-dead-the-hedge-instrument-is-unmeasured-closing-note-2026-09-04),
[record](study-results/f4_deployment/hedge_concentration.md).

Deferred, not dropped: the corrected prose control (`hedge_exposure` ARM C on
concentration-matched sessions with no hedge-pressure signal). Register it only
when the book has materially more parsed dates; today it would be another arm
that cannot bite
([pre-registration](pre-registrations/f4_deployment/hedge_exposure.md)).

<a id="s2-2"></a>
### 2.2 v4 composition bridge — OPEN, waits on new dates

`v4_bridge` prints `VERDICT: LADDER UNVALIDATED ON v4`, and on the 166-date
book all five pre-registered composition tests shift
([record](study-results/f1_selection/v4_bridge.md)). Per the
[pre-registration](pre-registrations/f1_selection/v4_bridge.md): keep deploying
under the v3-derived rules and do not re-derive the ladder on v4 rows yet.

- **Unblocks when** the live 2026-08/09 dates price, or later ones. Backfill
  dates do not count (§0).
- **Do not** lower `MIN_V4_DATES`, and do not point `--v4-csv` at a v3 export.
  Its exit 3 is the designed refusal (§0c(C)).

<a id="s2-3"></a>
### 2.3 Calendar-as-hedge — BLOCKED ON NEW DATES

`calendar_hedge` has not passed its own gates on any v4 export: H0 fill NOT
MET, H2 NOT EVALUABLE, and H3 read NOT MET, DEPLOYABLE, NOT MET on three
consecutive exports, so H3 is recorded as an unstable measurement rather than a
verdict either way ([record](study-results/f3_structure/calendar_hedge.md),
[hedge programme](current.md#the-hedge-programme)). The wall is structural: 9
worst-decile dates cannot power a worst-decile criterion under a 1/day sleeve.

- **Unblocks when** the book has materially more dates. Nothing to run until
  then.
- **Read H3 with this caveat:** it is `bear_deploy` D3 verbatim, and D3's
  drawdown leg is read on the close-bucketed curve that understates drawdown
  ([`deployment-evidence.md`](deployment-evidence.md#the-curve-d3-was-read-on-understates-drawdown-2026-08-31-hedge_exposure-arm-m)).
- Carry-forwards, post-hoc and not candidates: the RANGE+C/L-VOL calendar cell
  and the H2 clause amendment, both in the record.

<a id="s2-4"></a>
### 2.4 Bear sub-0.50 give-back — the `be_after` route is closed; the pattern is not

`bear_giveback` found the give-back lives in the underlying's path, not the
option mark ([record](study-results/f2_management/bear_giveback.md)). The
shipped breakeven stop was reverted 2026-08-24 when its rollback trigger fired
([`deployment-evidence.md`](deployment-evidence.md#the-bear-debit-peak-triggered-breakeven-stop-shipped-2026-08-11--reverted-2026-08-24)).

- **Status of the trigger:** fired 08-24, un-fired 08-27, fires again 09-04 on
  the 2026 column alone. Already reverted, so nothing to do, and the lesson is
  that a 60-row floor on a backfilling book is not a decision procedure (§2.6).
  Nothing un-reverts without a fresh registration.
- **Held, not queued:** [`bear_arm` B2](arm-index.md#bear_arm)'s exit-fix
  criteria are MET for the first time by `sl .50`. A correlated-window read
  holds a rule and promotes nothing
  ([two firsts](current.md#two-firsts-that-hold-rather-than-ship),
  [record](study-results/f1_selection/bear_arm.md)).

<a id="s2-5"></a>
### 2.5 Live walk-forward — the intended evidence source; no recorded movement

v3 tuning is closed and live fills are meant to be the evidence. The
`SUBSTITUTED` match category shipped 2026-08-11
([archive/10](archive/10-post-closeout-ops-and-live-evals.md)). Open: the
Stage 1/2 fill mapping and the live-vs-tier eval, whether realized live P&L
orders A > B > C. Also worth tracking: the operator substituting a naked leg
where a spread was emitted, an untested instrument.

⚠️ No log entry since 2026-08-13 records progress. A missing entry means
nobody wrote one, not that nothing happened. Check the live-loop artifacts
before re-planning.

**The operator-read test belongs here** (to pre-register before any code, f4,
`operator_read`). `text_features` showed the signal text carries no
machine-readable edge ([record](study-results/f1_selection/text_features.md)),
but the operator reads it qualitatively to decide what to trade, so its value
is realised in the PICK and only the journal can measure that. Design in one
paragraph: among ladder-eligible plays per date, TAKEN (journal `EXACT`,
`STRUCTURE`, `CORE`, `SUBSTITUTED`) against NOT TAKEN, paired by date, on
[R](glossary.md#r) and [PF](glossary.md#pf) with `protocol.pf_paired_by_date`
never without mean R, and the entry-session price move as the declared
covariate, because `next_day_move` showed day-0 confirmation is a confound
([record](study-results/f2_management/next_day_move.md)). Floor: at least 25
dates with 2 eligible plays and 1 taken. Census first; the journal may not have
it yet. A positive result is a statement about the operator's read, not the
prompt. Do NOT test this with a stripped-text `prompt_eval` candidate, which
would remove exactly what the operator reads.

<a id="s2-6"></a>
### 2.6 Rollback triggers — a trigger that printed nothing has not been checked

The table of triggers and floors is
[`deployment-evidence.md` §Open pre-registered rollback triggers](deployment-evidence.md#open-pre-registered-rollback-triggers);
the plan is the
[pre-registration](pre-registrations/f2_management/rollback_triggers.md). The
census prints on every relevant study run. Reading on the 166-date book:

| Trigger | Reading | What it waits on |
|---|---|---|
| bear-debit `be_after 0.50` | fires again on the 2026 column; already reverted (§2.4) | nothing |
| LVOL tef-null | STAYS GATED; the 08-24 CLEARED did not survive two exports, so the operator's hold was right | new dates |
| BEAR_HE trail | UNDERPOWERED, 1 affected date of 25 | new dates |
| credit sl-none | 0 fresh `bull_put` rows of 15; the window starts after 2026-07-13, unreachable by backfill | live dates after July 2026 |

<a id="s2-7"></a>
### 2.7 Parked or blocked long-term

- **Credit exit knobs** — unvalidated; needs a credit-heavy window. The v4
  credit book calibrates exactly and the corrected baseline is in place, but
  the fresh window starts after 2026-07-13, so no backfill can reach it. Census
  and the `sl 1x` comparator print on every credit run
  ([record](study-results/f2_management/exit_mechanism_study-credit.md)).
- **Long-dated blind spot** — `h ≥ 180` is unpriceable with real data and the
  BS proxy tier is OFF. Never read BS proxy rows as long-dated evidence.
  **Debit side only** (operator, 2026-09-05): the credit knobs above do not wait
  on this
  ([`current.md` 2026-09-05](current.md#2026-09-05-later--overviewmd-and-glossarymd-rewritten-for-a-reader-who-has-lost-the-thread-the-long-dated-blind-spot-is-scoped-debit-only)).
- **Per-regime exit switch** — STAYS GATED on the 166-date book; two of six
  criteria still fail
  ([mech](study-results/f2_management/exit_switch_mech_study.md),
  [structure](study-results/f2_management/exit_switch_structure_study.md)).
- **`portfolio_delta` ARM B ceiling 1.00** — clears the adoption conjunction on
  the dense-episode population off a correlated window:
  CANDIDATE-FOR-INDEPENDENT-WINDOW, nothing ships. Ceiling 1.50 dropped out
  2026-09-04 ([record](study-results/f4_deployment/portfolio_delta.md),
  [arm labels](arm-index.md#portfolio_delta)).
- **`exit_drawdown`'s design** — parked on dates, not design. Any CANDIDATE
  from it would need the independent window, never a re-cut of these dates.
  The ARM P ack is owed first (§0).
- **Prompt and infra** — the `analysis_pipeline/core.py` refactor is deferred;
  the PostToolUse hook still never runs pytest; the delegation-nudge hook is
  advisory by design.

<a id="s2-8"></a>
### 2.8 Per-play `invalidation` exits — CLOSED 2026-09-02, do not build

Answered by `exit_from_text`: the model's own invalidation level as an
underlying-close stop is CONTRARY on `bull_call_spread` / LVOL and NULL or
UNDERPOWERED elsewhere on v4. The v3 `bear_put_spread` re-read was answered
2026-09-04 on the 166-date book: NULL at every buffer, 2026 negative.
`invalidation_exit` stays unshipped on evidence
([record](study-results/f2_management/exit_from_text.md),
[arm labels](arm-index.md#exit_from_text)). The original gap and its two
parser cautions: [archive/00](archive/00-backtest-engine-backlog-2026-06.md).

<a id="s2-9"></a>
### 2.9 `prompt_eval` — a STABILITY item, not an edge item

Harness built 2026-09-03
([pre-registration](pre-registrations/f1_selection/prompt_eval.md)). The
PROD × 3 variance run is DONE: floor 0.0419 on paired ΔR, below which no
difference may be claimed ([record](study-results/f1_selection/prompt_eval.md)).
Do not pick this up ahead of §2.2; it is a v5 prompt bump if adopted, and
nothing in the book says it changes P&L.

- **The one candidate worth writing:** a WRITTEN decision rule for
  BULL/RANGE/BEAR over rollup fields the model already cites, so identical
  inputs give an identical label. The variance run's tier-mix swing traced to
  that label flipping on 2 of 5 dates
  ([`current.md`](current.md#2026-09-04--hedge_concentration-graded-and-21-closed-concurrency_correlation-built-and-first-run-noise)).
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
- `hedge_exposure`'s registration describes the `real` stratum, not the
  ratified `all` book
  ([pre-registration](pre-registrations/f4_deployment/hedge_exposure.md)).

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
