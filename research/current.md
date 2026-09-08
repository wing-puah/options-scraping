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
([the queue entry](#2026-09-08-fifth--queues-c-d-and-e-are-run-42-dates-added-and-the-2026-column-now-samples-march)).

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
no arm is or can be `ADOPT`-eligible. X4, the era-stability criterion, was
settled by hand: `NOISE` on both eras. The `v3` companion ran on 795 rows over
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

### Data hazards on this export, not repaired

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
  [2026-09-07 later](#2026-09-07-later--the-12-stale-backtest-rows-are-dropped-and-the-backtest-can-no-longer-double-a-row).
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
- `prompt_eval`, §2.9, is a stability item.
- `operator_read`, §2.5, waits on the journal.

### Standing hazards carried forward

Each has its full entry in an archive volume.

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

---

## 2026-09-04 — `hedge_concentration` GRADED and §2.1 CLOSED; `concurrency_correlation` BUILT and first-run: NOISE

Two items, and the second is the one nobody had built.

**`hedge_concentration` graded; the max-drawdown question is closed.** Re-run
2026-09-04 (era v4, sha `64689d0`, exit 0) on a slightly larger export than the
08-31 first run — `ADMITTED (taken + taken_downsized) 225 / 112 dates` — and
graded the same day under the two-analyst protocol. **A and B agreed on all 21
gate/clause rows, no violations, no mis-transcriptions**; the validator called
the pair "unusually clean" and found nothing to adjudicate. Both independently
disclosed the module's two live substitutions rather than glossing them — G-MTM
read against `TARGET_POSITION` instead of the registration's literal
stored-column check (the sim re-sized 101 positions and re-exited 35, so the
stored target cannot reconcile), and G-POWER read against episodes instead of
the registered trigger-DATE count. Both were already in the report's twenty-item
NOT PRE-REGISTERED block, which is what that block is for. The figures moved
slightly on the larger book and the verdict did not: G-POWER-K PASS
(`[172, 172, 152]` usable sessions per tercile against a floor of 60 each; 3
dense episodes against a floor of 3, **met exactly at the floor**), contrast
`$-767.93 CI95 [$-2,186.47, $349.09]`, ρ `-0.1648 CI95 [-0.4021, +0.0809]`,
neither beating ARM KN's 5th percentile. Clauses 1/2/3/5 fail; the two that PASS
are the CONTROLS (ARM KG keeps the sign across gross terciles, both ex-window
cuts retain it), so it is not a gross-exposure effect in disguise — it is no
effect. Stage 2 never opened. Recorded in `deployment-evidence.md` and
`next-steps.md` §2.1 is **closed**.

**The closing note the closure needs.** Written into `deployment-evidence.md`
beside it, because the hedge programme reads as uniformly negative and is not. A
hedge is two claims — WHEN to put it on, and WHETHER the thing you put on pays.
Everything powered is about the **trigger**: `hedge_timing` killed three
mechanical triggers (0 of 9 survivors, GAP-UP CONTRARY), `hedge_portfolio`
power-stopped every cell of a concentration × fraction grid, and now
`hedge_concentration` refutes concentration at its **precondition** on a powered
sample. The **instrument** has never been powered — `hedge_sizing` D2 flipped
MET → NOT MET on the v4 refresh, D3 was never met at any size, and neither
hedge study reached a cell. So "not shown to work" is the absence of a
measurement, not a measurement of absence. That is what decides the §4 sleeve:
the evidence contradicts hedging **on a mechanical trigger** and says nothing
either way about hedging **on judgment**, so keeping the sleeve as operator
policy is consistent with the record and so is dropping it. **Do not register a
fourth trigger study.** What would move it is an instrument test on a
mark-to-market curve (`lib/mtm_curve.py`), on dates chosen without a rule, and
that waits on dates rather than on design.

**`concurrency_correlation` built and run — the last registration with no
module.** Registered 2026-08-22, written 2026-09-04, first run the same day (era
v4, exit 0). It is the study for the operator's read that "the more that is
being deployed, the less it seems to be working" — which does NOT resolve to
depth into the ranked list (within-day rank is flat on both eras). What it
measures is the SIZE and internal SIMILARITY of the open book at each position's
entry: `account_sim` computes `n_open` and no report had ever joined it to an
outcome.

`VERDICT: NOISE` — **all 11 powered arms sit inside ARM N's band**, at any
ceiling on either grid. PRIMARY 3 dense episodes / 87 dates / 218 positions;
SECONDARY the full 129-date, 321-position book. `K 3` and `K 5 /
same-underlying` are UNDERPOWERED (21 and 7 moved dates against the pre-declared
floor of 25) and print census only. ARM CK is NOT RUN: the registration runs the
conjunction only if ARM C and ARM K each clear alone, and neither did.

Three things the run established rather than assumed, all printed:

- **`ARM K / same-direction` IS `ARM C` on a different grid.** The book is
  long-only by construction (`{1: 321}`; 321 of 321 positions have
  same-direction count == open count), so that relation carries no information
  ARM C does not. The run *checks* this instead of assuming
  `portfolio_delta`'s long-only census, and excludes the degenerate relation
  from ARM CK — a conjunction of an arm with itself is not a conjunction.
- **X7's delta control barely discriminates on this book.** 110 of 129 dates
  sit in the `[2.0,inf)` band of |net delta-notional| / capital at session open,
  leaving exactly ONE readable band — and one readable band is the whole sample
  re-labelled, not a control. X7 cannot PASS on it and the report says so in
  those words. That is a limitation of the control, not evidence for any arm.
- **ARM D0's descriptive shape is not flat.** Mean R falls across
  same-direction-and-sector count (`[0,3)` +0.4533 → `[6,10)` −0.1256 on
  SECONDARY) and across raw concurrency (`[6,10)` +0.5118 → `[20,inf)` +0.1783).
  It is registered DESCRIPTIVE ONLY and stays that way: every ceiling arm that
  would *act* on the shape is inside the null band, which is exactly the case
  the ARM N control exists to catch.

One design note worth keeping. The first implementation froze each arm's open
count at session open, following the registration's annotation clause
literally. That makes every ceiling a **DAY gate** — it admits all of a day's
picks or none — under which X2's within-date paired gain is identically
`+0.0000` on every date the arm keeps. A degenerate estimator, not a null. The
arms therefore use a count that runs WITHIN the session in ladder order (the
same walk `account_sim` makes down a day's ranked list), while ARM D0's
descriptive annotation keeps the registration's session-open rule and G2 checks
that one. Both read only the session they stand on. Disclosed as choice 3 of 21
in the report's NOT PRE-REGISTERED block.

X4 (era stability) is **not evaluable in a single run** — `lib/era.py` binds one
run to one era, and pinning a second era's export to dodge that is what the
guard exists to prevent — so every arm is CAPPED at CANDIDATE-PENDING-X4 and the
report prints the `--era v3` companion command. On a NOISE verdict that is a
completeness item, not a blocker. Gates G1–G6 and X8 all pass (G2 re-derives all
321 annotations a second way, 0 disagreements; G3 set-equality against
`top_k_per_day`; G4 attribution sums on every arm).

Records: `study-results/f4_deployment/concurrency_correlation.md`,
`study-results/f5_hedging/hedge_concentration.md` (both v4).

## 2026-09-04 (late) — first book with 2026 dates: export refreshed, suite re-run, nothing ships, the year clause bites; campaign b CLOSED

**The export.** Queue b (`scripts/analyze_bt_queue.sh backtests/enrich_queue_b.txt`)
reached `ANALYZE-BT COMPLETE` at 2026-09-04T10:48Z. Each date ran
`make analyze-bt ARGS="--date D"` — the `ARGS` make variable reaches the
`backtest` recipe too, so every backtest was per-date (the scratch
`results_*.csv` files each hold one date) and no bare backtest was run:
`scripts/backtest/core.py` has NO dedup against `BacktestResults`, and a bare
run would have doubled every priced row. `make export-tabs` (dry-run, then
install) pulled era v4 ×3:

| tab | rows | dates | was (2026-09-02 export) |
|---|---|---|---|
| BacktestResults | 535 | 158 | 494 / 142 |
| BacktestProxy | 1,303 | 166 | 1,144 / 147 |
| AnalysisClaude | 2,212 | 185 | 1,975 / 165 |

21 new backtested signal dates: 2025-11-25, seven in Dec-2025, and **13 in
2026** (01-06, 01-09, 01-14, 01-20, 01-23, 01-28, 02-10, 02-27, 04-08, 04-13,
04-16). `book --validate`: pooled 1,143 rows (real 535 / tweak 608) over 166
dates 2024-01-10 → 2026-04-16, by year 2024=611 / 2025=453 / **2026=79**;
debit calibration 392/408 exact, 1 near-rounding-tie, 1 boundary-tie, 0
hard; `exit_basis` coherence 621 coherent, 522 unlabelled, 0 conflicts.
`AnalysisClaude` also holds the live 2026-08-11 → 2026-09-01 dates with no
backtest rows — unexpired, not a gap.

**Duplicate triage first, because three dates ran twice.** 2026-01-20, 01-23
and 04-13 failed once on 09-03 (`FAILED rc=2`) and were re-run with
`RETRY_PARTIAL=1` on 09-04; the pipeline appends to the tab BEFORE the
backtest, so a failure after the append would have doubled them. No
`results_*.csv` was written in any of the three windows (the backtest never
ran), and the export shows **no duplicated `(date, ticker, play)` group on any
of the 21 new dates** (11–13 analysis rows each), so the failures were
pre-append. Counted the way `backtests/partial_analyze_dates.md` did on 08-25.
Two other things the triage found:

- **Four real-priced rows are in the scratch files but NOT in the tab**, and
  not in `BacktestProxy` either: 2025-12-22 TSLA and AMD `bull_call_spread`
  (the SPY row from the same run IS there, same `created_datetime`), and
  2025-09-26 CRWV `bull_call_spread` / HYG `bear_put_spread` (a manual run
  after an INTERRUPTED ledger line). No code path deletes `BacktestResults`
  rows (`delete_rows_where` is only called by the proxy on `--redo`, on its
  own tab), so either the append lost them or someone removed them. NOT
  repaired: the population is what the tab holds, and the rows have no
  provenance either way. If they are to be restored: `make backtest
  ARGS="--date 2025-12-22"` and `--date 2025-09-26`, never a bare run.
- **2025-12-26 has zero analysis rows** though the ledger records it done (a
  two-minute run; no inputs cached for that half-session). Left as is.

**The suite.** `make study-all RECORD=1`: 34 invocations, every study exit 0
except `prompt_eval` (exit 2, the designed argparse refusal — bare `--all`
passes no subcommand) and **`hedge_structure`, exit 1 at R2**:
`reconstructs: 1121 / 1122 (99.9%)  failed: entry_unpriced 1`. The row was
UTHR 2025-12-17 `bull_call_spread` 520/570 Jan-16: on the entry day
(12-18) the 570C had `Open 0`, bid 0 and no mark. Production's
`_simulate._entry_price_leg` has THREE branches — Open, else the day's mark,
else `_price_leg` → `_price_asof` (the most recent mark on or before the
day, 2.875 from 12-17, which is what the tab's entry 14.325 = 17.2 − 2.875
shows it used) — and `bear_rewrap.entry_price_of`, the study-side mirror that
`reconstructs()` rests on, had only the first two. Added the third
(`scripts/backtest_study/f3_structure/bear_rewrap.py`, two tests in
`tests/test_financed_spread_f4.py`; 335 f3 tests pass) and re-ran the four
studies that import it: `bear_rewrap`, `vol_sleeve`, `financed_spread`,
`hedge_structure` — R2 now `1122 / 1122 (100.0%) PASS`. The gate did its job:
it stops on the STUDY's fidelity to production, and that is what was short.
Not a harness edit; `lib/harness.py` untouched.

Also fixed while the suite ran, then re-run: the two stale report strings from
08-27 (`bear_arm.py`'s census header now says REVERTED 2026-08-24;
`account_sim.py`'s ARM H block says the D4 pick line was PULLED), and
`exit_from_text`'s hard-coded "the v4 export carries ZERO 2026 signal dates"
declaration, which was true of the registration's export and false of this
one — it now computes the 2026 date count from the book and prints whichever
world it is in. `make study-record` appended one section per study
(era v4 · sha e59356f, working tree dirty — the fixes above were uncommitted
when the reports were written; `exit_from_text` is re-recorded at the
committing sha). `concurrency_correlation --era v3` ran as the X4 companion
and is recorded as its own `era v3` section.

**What the first 2026 column did — by family.** Verdict words are the same
everywhere; these are the moves underneath, quoted from the reports.

*f1 selection.* `bear_arm` be_after-0.50 census: FLOOR MET (199 arming rows /
110 dates), (a) +$2,535.50 PASS, (b) +0.0600 PASS, (c) `2024:+0.0148
2025:+0.0047 2026:-0.0431 [FIRE]` — the third census (08-24 FIRED 92 / 08-27
HOLD 165 / 09-04 FIRED 199) and the rule has been reverted since 08-24, so
nothing changes. `bear_arm` B2 EXIT FIX **MET for the first time**: `sl .50
(tighter) Δ=+0.039 CI[+0.004, +0.071] LOO min gain +0.035`, non-bear control
+0.140 → +0.113, 2026 n=23 CI spans zero — a correlated-window re-read, holds,
promotes nothing. `bear_position_study` DEMOTE TO VETO on n=368 (E −0.222
[−0.349, −0.087], halves −0.388 / −0.045; on R the CI now spans zero —
the criteria are on E). `emission_timing`: candidates 3 → 1 (ARM L `T1_low
L=3`); two ARM P cells fail criterion 4 on 2026 sign flips (+0.2948,
+0.5415). `ml_combination` NULL, M3 −0.045 [−0.160, +0.074], first real
three-year test (2026 −0.251). `v4_bridge` LADDER UNVALIDATED, 5/5 shift,
2,025 plays / 184 dates. `mech_regime_recut` OR-VETO REJECTED, subset n=41
mean +0.0526 (the 08-27 net-flat caveat relieved). `text_features`
unchanged but ARM B coverage 1021/1143 (89.3%, `claude calls=0`) — the label
cache does not cover the new rows; ARM B is not quotable at this population
until a live-label run. `trigger_entry` NULL / LATE-ENTRY ×2 (N=3 −0.0121).
`regime_gap_reread` §5d ρ −0.0686 p=0.19 n=365 — non-replication confirmed
at v3's n. Two hardcoded 2026-03 tables (`mech_regime_recut` §(b),
`regime_gap_reread` §0) stay empty: the export's 2026 dates are Jan/Feb/Apr.

*f2 management.* `next_day_move` ARM R bear-debit **loses `**` on all
three cuts**: wrong-sign +0.074 [−0.005, +0.148], −0.5σ +0.043 [−0.003,
+0.090], flat band +0.087 [−0.011, +0.177]; 2026 −0.153 / −0.143 / −0.258
(n=21). `exit_from_text` E2 pooled N=3 CANDIDATE → NULL (`2026 -0.043 (n=11)
FAIL`); tally `{'UNDERPOWERED': 278, 'NOT A CRITERION (pooled)': 8, 'NULL':
22, 'CONTRARY': 8, 'SURVIVAL-ARTIFACT': 2}`; the v3 `bear_put_spread` re-read
item is ANSWERED — powered on v4 (336 rows) and NULL at every buffer, 2026
−0.302 / −0.134 / −0.039. `exit_switch_mech_study` STAYS GATED ×2; LVOL
census 100 rows / 73 dates FLOOR MET, `median among affected dates` −0.0330
FAIL, halves +10.07 / −0.20 FAIL; BEAR_HE 1/25 UNDERPOWERED.
`exit_switch_structure_study` STAYS GATED (2 of 6) but the Q2 guard read
inverted — structure trail Δ +4.6539 (was −0.8920), complement +3.8804
retained 83% (was 187%), complement criterion PASS. `exit_mechanism_study`
PROD $+25,363 on 408 debit rows; best Δ-LOO `BE ratchet @.75` +2,142; `trail
.40 trig .75` +200 is the first positive out-of-fold reactive cell. Credit
census 0 fresh of 15 (window after 2026-07-13 — unreachable by backfill);
sl-none still wins, Δ −$584 / Δ-LOO −$1,306. `staged_exit` NULL, 51/96
powered, six cells significantly HARMFUL. `bear_giveback`: rule 4 fails on
2026 for every `be_after` candidate; gradient `peak within 3d n=39 87%
−0.445` vs `peak >20d n=176 47% +0.236`. `volume_signal` PATH-VOL-PROXY,
r_sep −0.0290.

*f3 structure.* `bear_rewrap` long_diag 5/5 → **4/5** (`[FAIL] sign-stable
every year 2024 +0.195 2025 +0.259 2026 -0.106`) while ARM P **P1 is MET for
the first time** (n=16 +0.499 [+0.202, +0.743]) and P2 −0.326 MET; 391 bear
debit rows reconstructed 100%; `ex_2026_feb_apr` drops 1 of 189 long_diag
rows — the year clause tests 2026, the window cut does not. `financed_spread`
**F3 off1 → RE-WRAP** (dR +0.217 [+0.056, +0.401], all six other criteria
PASS incl. `2026 +0.353`, fails E3 corr +0.159; fixed-contracts control
+0.102 [−0.102, +0.301] spans zero); F2 off1 −0.497 [−1.084, −0.085] harmful;
F4-d20 UNDERPOWERED 36 rows / 33 dates (rows floor 60). `vol_sleeve` Q2 IS
NULL verbatim, CLOSED stands; straddle/strangle still wrong-signed
(+0.220 / +0.187), calendar −0.211, calendar cell 133 rows meanR +0.303 PF
1.39. `hedge_structure` VERDICT byte-identical (H0 FILL NOT MET 51.0% / 28.6%;
H2 NOT EVALUABLE, (b) n=4) but **H3 DEPLOYABLE at f=1.00 → NOT MET at any
size** on both baselines (drawdown-bound; baseline max DD −10,968 →
−12,529 and −11,467 → −15,425) — three runs, three readings; H2(c) 3/3
years is carried by ONE 2026 position on 2 dates.

*f4 deployment.* `account_sim` FEASIBLE (A1–A6 MET on PRIMARY: 148 positions
/ 76 dates / $22,217 / meanR +0.348; A3 15.0%; G2–G5 PASS); the SECONDARY
full book (260 / 129 / $21,855 / +0.231) fails A1 (`2026:-0.062`) AND A3
(35.7%) — no verdict reads from it, but FEASIBLE is a two-year, dense-episode
claim (episodes end 2025-09-26). Compounding NOT FEASIBLE, A3 25.7%,
byte-identical. `hedge_sizing` D1–D4 NOT MET; D5 post-hoc gates 8 → 2; D4
`|delta| low first` +0.084 [−0.028, +0.197], adopted 0. `hedge_timing`
survivors 0; H1-GAP NULL → CONTRARY (−0.245 [−0.458, −0.026]), H3-GAP −0.506
[−0.844, −0.157], H4-GAP CONTRARY → NULL (`cuts_ok` fails), H4-CHOP and
H4-DECLINE UNSTABLE → NULL; streak N=4 n_dates=4 / N=5 n_dates=2
UNDERPOWERED. `portfolio_delta` CANDIDATE-FOR-INDEPENDENT-WINDOW for **B
ceiling 1.00 only** (+0.1081 [+0.0131, +0.2205]); B 1.50 `FAILS c1` on
primary ([−0.0120, +0.1527]) and `FAILS c4` on secondary (2026 −0.0878).
`hedge_concentration` PRECONDITION-NULL, contrast $−173.65 [$−1,205.66,
$893.81], ρ +0.0000 [−0.2198, +0.2231], terciles [216, 215, 195].
`hedge_portfolio` unchanged; the `real` stratum crossed its floor (reported,
no verdict). `selection_order` ORDERING-IS-NOISE; its PRIMARY population has no 2026 term
at all and the SECONDARY's 2026 cell is n=3 dates. `concurrency_correlation` NOISE on v4
(PRIMARY 3 episodes / 88 dates, SECONDARY 147 dates, 11/13 powered, ARM CK
NOT RUN, X7 121/147 in one band) and **NOISE on v3** (795 rows / 118 dates,
8/13 powered) — X4 settled: the null replicates, zero arms clear X2/X3 in
either era so none is ADOPT-eligible, and 4 of 8 dual-powered arms flip sign
(C ceiling 5 and 8, K5/same-direction, K3/same-dir-and-sector).

**What ships: nothing.** Every first this run produced is on the correlated
window and the registrations say what that means: hold, promote nothing.
The one operator item is the §4 gap-up prohibition, still drafted-and-held,
now carried by H3/H1 and not by H4's dollars (`deployment-evidence.md`).

**Housekeeping.** `scripts/analyze_bt_queue.sh` deleted per its own header
(campaign landed); ledger and date lists stay in `backtests/`. `current.md`
rotated: 2026-08-28 → 2026-09-02 moved verbatim to
[archive/18](archive/18-hedge-programme-exit-basis-and-text-loop.md), with
the status stamp and README rows. `catalog.py` / `study-map.md` verdicts
brought current for every mover above; `overview.md`, `next-steps.md`,
`deployment-evidence.md` (third census; hedge_timing re-read) updated.

## 2026-09-05 — `exit_drawdown` (NEW, f2): walk-forward exit hypotheses on account-level drawdown — UNDERPOWERED on PRIMARY; the two powered `all` cells are NULL

No exit rule can be judged on this book. Every PRIMARY cell fails the power
floor, and the only two cells with enough rows to read sit on the disclosed
`all` cut, where both are negative: `exit_drawdown ARM O/vol` is `NULL` and
`exit_drawdown ARM D/throttle` is `SECONDARY-NULL`. Nothing ships from this
study under any outcome, by construction. It is the first study in the repo to
judge an exit rule on the **account's mark-to-market curve**
(`lib/mtm_curve.py`) rather than on per-row R, and the first to choose an exit
threshold **out of sample**.

_Era v4, the 166-date book · exports of 2026-09-04 · 535 real / 1,303 proxy /
2,212 analysis rows · pooled study book 1,143 rows (real 535 + tweak 608, bs 0),
2024-01-10 → 2026-04-16 · registered, built, run, graded and recorded the same
day · record: [study-results](study-results/f2_management/exit_drawdown.md)._

**In production.** Nothing changes.

**The question, and why these five arms.** Every standing exit null was reached
on a per-row R estimand under a full-window, in-sample parameter choice. The
operator's queued question is "MAX DRAWDOWN, not timing", and `account_sim`
already deploys the ladder through a $25,000 ledger, so the missing piece was
never a new estimator — it was a curve nobody had pointed a rule at. The five
arms are the ones the record had *not* already refuted:

- `exit_drawdown ARM W` — walk-forward selection over the shipped pt × sl × tef
  grid, with `W/prod` (the shipped point itself) as its own control. All
  pt/sl/tef tuning to date was full-window and in-sample;
  `protocol.walk_forward_splits` existed and had never been pointed at the grid.
- `exit_drawdown ARM U` — an underlying ATR stop on debit verticals, ATR14
  FROZEN at entry. Only CREDITS were ever given an underlying stop (the
  short-strike breach); `bear_giveback` had found the give-back pattern in the
  UNDERLYING rather than in the mark, and nothing acted on that.
- `exit_drawdown ARM O` — a flow-unwind exit off the entry long leg's own
  `Open Int` path, read LAGGED one session, plus one volume-climax variant.
  `backtests/option_history_cache/` has carried per-session `Open Int` and
  `Volume` for every priced leg for months and **no study had ever read the OI
  path**.
- `exit_drawdown ARM P` — partial scale-out, exactly computable from stored
  paths and never measured.
- `exit_drawdown ARM D` — a deployment-level drawdown THROTTLE on sizing,
  labelled SECONDARY throughout and carried only as a comparator: it is the most
  direct lever on the account curve and it can never be an exit finding.

The standing nulls this had to avoid re-finding are the reactive family —
Attempts 1/2/10's drawdown-from-peak trails and `staged_exit`'s day-X formula
(0/40 powered cells, six harmful CIs on the 09-04 book). §3 already forbids
re-registering that formula under another anchor. This study is not it, and one
of its arms walked into it anyway (below).

**The two cuts, in ONE report.**

- **PRIMARY = dense episodes** — 3 episodes covering **88 dates**, 621 rows
  (478 debit / 143 credit). After the purged walk-forward and a **45-date
  burn-in** (2024-01-10 .. 2024-10-23, 325 rows, excluded from the headline, not
  silently replayed), the evaluated population is **43 OOS dates / 296 rows**.
  PRIMARY is the dense-episode cut because `account_sim`'s FEASIBLE verdict is
  itself a dense-episode claim.
- **`all` = the full book** — 166 dates, 1,143 rows (854 debit / 289 credit),
  75-date burn-in, **91 OOS dates / 607 rows**. Disclosed secondary cut,
  **carries no verdict**, never pooled with PRIMARY and never read as
  corroborating it: it is the same era's wider date set, not an independent
  population.
- **v3, run and recorded the same day as the SECONDARY era.** On its PRIMARY
  population **no test block survives the 120-day embargo on 46 dates** —
  `blocks 0   OOS (test) dates 0   burn-in dates 46`, so every arm reads
  `UNDERPOWERED   (no OOS dates)`. Its `all` cut does split (3 blocks, 43 OOS
  dates, baseline 41 positions / 24 dates, max DD $−6,182) and is UNDERPOWERED
  everywhere too. One cell there is a complete no-op rather than a thin one:
  `exit_drawdown ARM P/half` changes `0 rows / 0 dates` on v3's `all` cut
  (`ARM P/half              48         0          0`), so v3 says nothing about
  partial scale-out at all. Everything on v3 is UNDERPOWERED, so it neither
  corroborates nor contradicts v4, and clause 5 reads VACUOUS on every powered
  v4 cell for exactly that reason.

**The design.** `walk_forward_splits(dates, block=15, embargo_days=120,
min_train_dates=40)` — purged, expanding, the embargo set EQUAL to the path cap
so no training label can still be open when a block's test dates start. Two
stages, both registered before any number was seen: (1) keep every configuration
whose TRAIN mean R is within 0.02 of the best; (2) among the survivors,
`simulate()` on the TRAIN day-lists only and take the SMALLEST **train** MTM max
drawdown. The blocks' TEST books are then stitched into one OOS book and the
curve is marked through `mtm_curve`.

Every gate passes on both cuts.

| Gate | What it checks, and what it printed |
|---|---|
| G-COV | every census printed before any conditional number |
| G-FORK | with its own rule disabled, every overlay reproduces `account_sim.replay_sized` field for field — `2286/2286 exact`; `lib/harness.py` is neither edited nor copied |
| G-CAL | `positions   direct 84   study baseline 84`, `book_signature` identical, and `account_sim`'s own `G2: PASS` / `G3: PASS  (0 violations)` / `G4: PASS` / `G5: PASS` / `GATES: ALL PASS` run **in-process** and lifted verbatim |
| G1 | every auxiliary series shifted one session forward: PRIMARY `4164` comparisons, `2119` firing sessions changed, **0 moved earlier**; `all` `7444 / 3858 / 0` |
| G-MTM | 785 PRIMARY / 1,514 `all` positions reconcile to the frozen harness at $0.01 per contract |
| G0 | the power floor; it runs first and blocks everything |

**PRIMARY: every cell fails G0 before any drawdown or ΔR clause is evaluated.**
The floor was registered before any count was known: **< 25 affected DATES or
< 60 affected ROWS is UNDERPOWERED** — census printed, nothing concluded, no
re-run on these dates. Baseline book `84 positions / 40 dates   max DD $-5,466
(-21.9% of capital)   Ulcer 7.093%   TUW 91.8%`. Verbatim:

```
  cell             curve pos  aff rows  aff dates   changed  arm-only  base-only  status
  ARM W/wf                84        19         16        19         4          4  UNDERPOWERED
  ARM W/prod              84         0          0         0         0          0  UNDERPOWERED
  ARM U/a                 86        15         14        15         5          3  UNDERPOWERED
  ARM U/b                 86        18         16        18         5          3  UNDERPOWERED
  ARM O/oi                88        12          9        12         7          3  UNDERPOWERED
  ARM O/vol               97        35         28        35        14          1  UNDERPOWERED
  ARM P/half              90         6          6         6         2          9  UNDERPOWERED
  ARM D/throttle          86        16          8         -         -          -  UNDERPOWERED
```

`tally: {'UNDERPOWERED': 7, 'SECONDARY-UNDERPOWERED': 1}`. Because G0 runs first
and blocks every criterion, **no PRIMARY cell has a drawdown or ΔR figure of its
own anywhere in the report** — the census is the whole output. That is what
"nothing concluded" means here, and why no PRIMARY arm-versus-shipped dollar
figure can be quoted from this run. Not one cell is close: the best-populated,
`exit_drawdown ARM O/vol`, reaches 35 rows against a 60-row floor, and
`exit_drawdown ARM W/prod` — the shipped grid point itself — changes **0 rows /
0 dates**, which is what makes the arm-level token unreadable.

Three details of the count:

- The floor counts the `changed` column ONLY. `arm-only` and `base-only` are
  reserve-release knock-ons — an earlier exit freed a reserve and admitted a
  later position — and are printed as a DISCLOSED, NON-GATING breakdown rather
  than counted towards power, which would have inflated it in the permissive
  direction.
- `exit_drawdown ARM D`'s counts use its own registered SIZING definition of
  "affected": positions ENTERED at the halved budget, and the dates one was.
  They are re-derived from the book and reconciled against `simulate()`'s own
  `throttle_dates`.
- One thinness is STRUCTURAL rather than date-driven. On PRIMARY
  `exit_drawdown ARM P` could split only **13 of the 77 ledger positions** —
  `EXCLUDED: credit 13   n = 1 (cannot be halved) 51` — so at this $500 risk
  budget a scale-out arm is mostly untestable by construction, not merely
  underpowered on these dates (`all`: 21 split of 155, 102 excluded at n = 1).

**The two powered cells, both on `all`, both negative.** Baseline there is
`162 positions / 76 dates   max DD $-14,238 (-57.0% of capital)   Ulcer 19.452%
  TUW 92.6%`.

- **`exit_drawdown ARM O/vol` — the volume-climax exit. VERDICT: NULL.**
  It halves the marked drawdown — `max DD   shipped $   -14,238   arm $
  -7,194   (-57.0% / -28.8% of capital)`, i.e. `$+7,045 = +49.5% of the shipped
  drawdown` — and still fails three clauses. (1)
  `block-bootstrap CI95 [-268, +13,843] (n=2000, chronological moving block)   FAIL` — the interval contains zero. (2) `paired DeltaR by date -0.054   CI95 [-0.130, +0.017]   lower bound
  > -0.02   FAIL`: it buys the drawdown cut with return. (7) `CONT: 55/77 early
  exits (71%) followed by a post-exit max > realized+0.30 R   (strict
  any-recovery share 92%, DISCLOSED, not the gate)   FAIL`. Clauses 3 (3/3 years
  agree), 4 (real / tweak same sign) and 5 (VACUOUS) pass and do not save it.
  **Name it what it is: this is the reactive null — Attempts 1/2/10 and
  `staged_exit` — measured at ACCOUNT level for the first time.** Every earlier
  refutation used a per-row R estimand; this one fails on the same mechanism
  (selling continuations) and in the same rate band the trails failed on. The
  account curve does not rehabilitate a reactive exit. Thread closed for these
  dates.
- **`exit_drawdown ARM D/throttle` — the drawdown throttle. VERDICT:
  SECONDARY-NULL.** `max DD   shipped $   -14,238   arm $   -11,467   (-57.0% /
  -45.9% of capital)`, `$+2,771 = +19.5% of the shipped drawdown`, and again
  (1) `CI95 [-2,257, +6,644]   FAIL`, (2) `paired DeltaR by date -0.031   CI95
  [-0.069, -0.000]   lower bound > -0.02   FAIL`, and (4)
  `pricing tiers: real $-379 (n=68)  tweak $+2,616 (n=107)   FAIL` — **the real
  rows got WORSE and only the tweak rows improved**, which is the single most
  disqualifying shape a sizing rule can have. Clause 3 passes 2/3 on a first
  half worth `$+4`, which is noise wearing a PASS, and the 2/3 is itself a
  SILENT NO-OP disclosed only in the printed line `years: 2024 n/a (eval dates
  13, aff 0)`: the throttle never fired on any 2024 evaluated date, so the year
  cut is signless there and the clause clears on the two years that HAVE a sign.
  (Clause 3's registered signless rule is written for the HALVES, where a
  signless half fails; the `>= 2 of the 3 years` half of the clause has no such
  rule, which is why a year that never fired passes silently.) `exit_drawdown
  ARM D` has no clause 7 by registration, because a sizing rule moves no exit
  and its continuation rate is the baseline's by construction. It could never
  have shipped from f2 anyway; the most it could ever have done is queue an f4
  registration, and it does not.
- **`exit_drawdown ARM W`'s arm-level token is UNDERPOWERED and `PROD-ROBUST` is
  NOT claimed** — `too few dates to say whether PROD survived`. Recorded as the
  report prints it (see the disagreement log).

**The finding that outlives the tokens: the in-family best is not stable across
blocks.** On `all`'s 7 blocks the walk-forward re-picks a *different* winner as
the train window grows.

| Arm | Winner as the window grows | Tally |
|---|---|---|
| `exit_drawdown ARM W/wf` | `pt 0.90 / sl off / tef off` for blocks 0–2 → `pt 1.10 / sl off / tef off` → `pt 1.10 / sl off / tef 0.75` | `{'pt 0.90 / sl off / tef off': 3, 'pt 1.10 / sl off / tef off': 2, 'pt 1.10 / sl off / tef 0.75': 2}` |
| `exit_drawdown ARM U/a` and `U/b` | `k 3.0` → `k 1.5` | `{'k 3.0': 3, 'k 1.5': 4}` |
| `exit_drawdown ARM O/oi` | `X 0.40` → `X 0.25` | `{'X 0.40': 3, 'X 0.25': 4}` |
| `exit_drawdown ARM D` | `d 0.10` → `d 0.05` | `{'d 0.10': 3, 'd 0.05': 4}` |

Only `O/vol` (no threshold to pick) and `W/prod` (a one-point grid) are stable,
and on PRIMARY's 3 blocks the drift is not visible at all — three blocks is not
enough window to see it. A knob whose best value moves with the training window
is not a knob with a value; it is a knob being fitted.

The **in-sample DISCLOSURE gap** measures what that fitting is worth, and it is
the size of the tuning bias every earlier in-sample exit read in this repo
carried.

| Cut | Best full-window configuration | Shipped |
|---|---|---|
| PRIMARY | max DD $−4,127 (`exit_drawdown ARM O/oi`, `X 0.25`) .. $−5,275 (`ARM U`, `k 1.5`) | $−5,466 |
| `all` | $−8,118 (`exit_drawdown ARM U`, `k 1.5`) .. $−13,167 (`exit_drawdown ARM O/oi`) | $−14,238 |

Every one of those looks better than the honest out-of-sample book, and none of
them is a result. The report prints them under
`NO VERDICT IS READ FROM ANYTHING BELOW` precisely so the gap is visible
rather than inferred.
`exit_drawdown ARM D`'s own collapse is disclosed the same way: `Cfg.dd_throttle`
is ONE value for a whole simulation, so the per-block selection has to collapse
before the stitched book runs, and it collapses to the EARLIEST block's choice
(`d 0.10`) — the only collapse that uses no information after its own TRAIN
window. A modal collapse would have replayed block 0's TEST dates under a `d`
fitted on train sets containing them. Both grid values' stitched books are
printed beside it (`d 0.05` $−11,177 / `d 0.10` $−11,467 on `all`; identical
$−5,466 on PRIMARY) so the reader can see what the collapse cost.

**Disagreement log (two-analyst grading, `study_review exit_drawdown`).** In the
graded round **A and B agree on every row, and the validator found no
violations.** Every quoted figure reproduces character-for-character on both
sides: G0's per-cell counts,
the `25 dates / 60 rows` floor, G-FORK's `2286/2286`, G-CAL's `direct 84 / study baseline 84` and its G2–G5 lines,
G-MTM's `785 positions … $0.01`, G1's `4166 / 2119 / 0`, G-COV's census lines,
and the eight PRIMARY cells' affected-date list `16, 0, 14, 16, 9, 28, 6, 8`.
Both correctly refused to import any `all`-cut number into a verdict cell, which
the validator flagged as the easiest place either analyst could have smuggled
one in. **The graded artifact is the run at sha `e1af7f8`**, so its G1 total is
quoted here as the grading saw it; the RECORDED run at `efd9b76` (same verdicts,
same cells) prints `4164 / 2119 / 0` on PRIMARY, because pinning
`SHIPPED_BE_AFTER` moved two rows across ARM O's ≥20%-blank boundary — see the
`be_after` trap below.

- **One coverage gap, not a violation.** Analyst B's table stops after clause 7
  and never grades the report's separate `ARM W arm-level token` line; A grades
  it `NOT EVALUABLE`. B took no position, so the point cannot be adjudicated
  from the source. **Main-session decision: record the token as the report
  prints it — `ARM W arm-level token: UNDERPOWERED`,
  `PROD-ROBUST is NOT claimed` — and note that analyst A read it NOT
  EVALUABLE.** The two do not
  conflict: the report's own token is the record, and A's grade says a reader
  could not independently evaluate it, which on `W/prod` changing 0 rows is
  correct.
- **The EARLIER round is where the grading did its work.** It reopened the
  **MODULE** — a grading defect reopens the module, never the registration — on
  three REPORTING defects. All three were fixed and the study re-run, and
  verdicts did not move. (a) **G-COV ordering**: `exit_drawdown ARM P`'s split
  census printed BELOW the G0 cell table that already carried that arm's
  affected counts, against the registration's unqualified "a conditional figure
  printed above its coverage line is a reporting defect". `ARM P`'s and
  `ARM D`'s censuses now print in G-COV with `ARM U`'s and `ARM O`'s, above
  every cell table. (b) **`run_gates` was asserted, not carried**: G-CAL claimed
  `account_sim`'s G2–G5 pass but delegated them to a separate invocation outside
  the process and printed no result, and the two analysts split exactly there
  (one graded G-CAL MET on the narrower printed claim, one declined to grade
  it). They are now called in-process and their PASS/FAIL lines printed inside
  this report. (c) **one invocation now carries BOTH cuts**: the PRIMARY
  headline and the disclosed `all` cut in one report, which is what "run as a
  disclosed secondary cut and printed beside it" always said.
- **Two rulings the grading forced**, recorded on 2026-09-05 while the module
  was built and labelled **(h)** and **(i)**, settled ambiguities the
  registration had left. **(h)** G-CAL's parenthetical named
  `account_sim --selftest-gates`, which is the OPPOSITE of the check (below);
  it now reads as §7 of `exit_drawdown-errata.md` (folded into the registration
  2026-09-08). **(i)** clause 5's referent is the SECONDARY era's PRIMARY cell,
  **never its `all` cut**: `all` carries no verdict, so an `all` cell is not
  verdict-carrying and cannot contradict one. That referent rule is now folded
  into clause 5 of the registration's own "Bar for a candidate", and the sidecar
  it turns on is errata §5. The sidecar records its POPULATION beside its era,
  only the PRIMARY cut writes one, and a sidecar naming any other population (or
  none, as the pre-correction files do) is REFUSED with clause 5 printing
  VACUOUS and the reason. The no-OOS path also now records its cells before
  returning, so v3's all-UNDERPOWERED cell set is the honest referent instead of
  no file at all.
- **The four corrections were CONSOLIDATED on 2026-09-06, and the grading is
  still traceable.** The registration now states one final design read top to
  bottom. Readings 1, (g) and (i)'s referent rule are folded into the
  registration's own G1 bullet under "Gates" and clauses 4 and 5 under "Bar for
  a candidate" (reading 1's measurement moved with it, into "Build notes"),
  because each narrows a clause without changing what it refuses. The rest —
  reading 2 (ARM O's volume leg), (a), (b) superseded by (f), (c), (d)'s
  sidecar, (e) and (h) — are in `exit_drawdown-errata.md` (folded into the
  registration 2026-09-08), which `study_review` inlines beside the registration
  as AUTHORITY, each under the label the report and the two analyst gradings
  cite it by. They are NOT folded because each changes what a gate refuses, what
  an arm does or how a clause is read, and writing one into the registration's
  own prose would present a build-time decision as a pre-commitment. The graded
  report and both analyst files are untouched, and every letter they cite
  resolves in the errata's concordance table.

**Traps found, all of them the kind that would have been silent.**

- **`account_sim --selftest-gates` INVERTS every gate's expectations.** It adds 1
  to `days_held` in G2, injects a $1 leak into G3's identity, and inverts G4's
  and G5's comparisons, so a healthy build must print `GATES: FAILED`. It is a
  check on the CHECKER. **A run of it that PASSES means the gates are broken** —
  never cite a passing `--selftest-gates` as evidence a study's host simulation
  is sound.
- **The runner keys reports by STEM only, so two eras race on `-latest.txt`.**
  Running `--era v3` overwrites the v4 headline in
  `backtests/study_output/exit_drawdown-latest.txt`. The **era-named copies are
  the durable path** (`exit_drawdown-v4-2026-09-05.txt`,
  `-v3-2026-09-05.txt`, and the `-all-` variants); `-latest.txt` is whichever
  era ran last and must be re-checked against its own header before anything is
  quoted from it.
- **`-- --era v3` is swallowed by the runner.** `--era` is the runner's own flag,
  not a study argument, so it goes BEFORE the `--`
  (`run exit_drawdown --era v3`). After the `--` it reaches the study module,
  which does not parse it, and the run silently proceeds on the CURRENT era —
  producing a "v3" report that is v4.
- **The v3 sidecar must be stamped with its population.** Fixed under correction
  (i) above; before it, a v3 `all` run's sidecar would have been read as v4
  PRIMARY's clause-5 referent, crossing two CUTS exactly the way a stale
  filename crosses two ERAS.
- **`fetch_underlying_ohlc.py --skip-existing` REWROTE `rescaled_tickers.txt`
  and dropped six attestations.** A run that fetched only 68 of 145 tickers
  rewrote the file in full, so AVGO, CVNA, MSTR, NFLX, SMCI and XLE — all still
  on a rescaled basis, their CSVs untouched — vanished from it, and their
  absence read as "not rescaled". **Fixed today**: `write_rescaled()` now MERGES
  (a run attests only the tickers it actually split-checked, every other prior
  line is kept verbatim, and an empty run writes nothing), and a new standalone
  offline `--recheck-rescaled` re-derives the flag for every cached ticker from
  disk and is the one path allowed a full rewrite. **13 tickers are flagged
  now**, including **NVDA (0.9000 over 216 days — the 10:1 split)** and **GE
  (0.2000 over 31 days — the spinoff step)**, neither of which was in the file
  before. This CHANGES WHAT `volume_features` AND EVERY OTHER OHLC CONSUMER
  WITHHOLD from here on: absolute dollars and cross-series comparisons on a
  flagged ticker are invalid, while ratios are fine because a constant factor
  cancels. Three counts are in play: **11** attested before today's partial run,
  **5** left after it rewrote the file, **13** after the offline rebuild — two
  tickers newly flagged versus yesterday and eight versus the file the partial
  run left standing.
- **The pairing baseline's LABEL named a reverted rule.** `account_sim.py`
  hardcoded `SHIPPED_BE_AFTER = 0.50`, so `profile_for` kept applying the
  bear-debit break-even stop to bear-debit rows and the PRE-pin reports'
  (`e19d3b4`, `e1af7f8`) basis line read
  `base -> bear-debit be_after .50 -> BEAR_HE` — but `config/backtest.yml` has
  had `structure_exit.enabled: false` since the 2026-08-24 revert.
  (`regime_exit`'s BEAR_HE is genuinely still enabled; only `be_after` was
  stale.) **Measured impact: ZERO `be_stop` exits in ANY `account_sim` or
  `exit_drawdown` baseline book** (`account_sim-positions-latest.csv` and both
  `exit_drawdown` reports), so **no verdict, no cell, no baseline book and no
  clause figure moves** across the pin. Same class of latent defect as
  `exit_mechanism_study`'s stale `CREDIT_PROD` (2026-08-24). Fixed the same day:
  `SHIPPED_BE_AFTER` is pinned to the config (`None` when the block is disabled)
  and test-pinned, and the study was re-run and re-recorded at `efd9b76`, whose
  basis line now reads `base -> BEAR_HE (the bear-debit be_after block is
  DISABLED in config/backtest.yml, so no breakeven stop is merged)`.

  **The pin is not figure-neutral OUTSIDE the deployed book**, which is worth
  stating rather than discovering. `be_after` did move shipped `days_held`
  somewhere outside the deployed book — whose positions, max DD, Ulcer and TUW
  are identical across the two runs — so between `e1af7f8` and `efd9b76` ARM O's
  hold-window census shifts: `>= 20% blank` 16 → 17 on the PRIMARY population
  and 8 → 9 on the OOS-evaluated rows, `USABLE by ARM O` 421 → 420 and
  216 → 215, and G1's PRIMARY comparison total `4166` → `4164`. Nothing that
  carries a verdict changed.

  **Closed the same evening:** `account_sim` was re-run at the committed sha
  `d69a802` (its last two `be_after-0.50` strings — the G2 prose and the
  `replay_sized` docstring — retired in that commit) and re-recorded. The PRIMARY
  headline is unchanged under the pin (`total $22,217 · maxDD $-3,750 · worst
  session $-2,796`), and its CONFIGURATION block now prints `bear-debit breakeven
  stop  disabled — simulation.structure_exit.enabled is false in
  config/backtest.yml`.

**Data.** The OHLC cache was missing 68 of the 145 current-era book tickers; all
68 were fetched (0 failed) and **the cache now covers all 145**. v3's 103
tickers were already complete. Post-fetch census: 0/145 missing files, 115 with
a fully covered entry-session span and 30 with missing sessions — **every single
missing session inspected by hand is an NYSE holiday that falls on a weekday**
(Presidents Day, Good Friday, Juneteenth, Independence Day, the 2025-01-09
National Day of Mourning), which `harness._weekday_grid` includes because it
excludes weekends only. Those are not scrapeable gaps and were not re-fetched;
they read as unpriced sessions, never as a flat move. OI coverage on the current
era: 1,144 of 1,151 evaluated (record, long-leg) rows at ≥80% `Open Int`
presence, 26,291 of 26,338 sessions present (99.8%). `backup_research_caches.py
push` ran 2026-09-05 11:13 (`research-caches-20260905-1111.tar.gz`, 229.6M) —
note it covers `live_loop` / `option_history_cache` / `to_evaluate` only, NOT
`underlying_ohlc_cache`, which is treated as re-fetchable stock history.

**What would move it, and what is closed.** The only thing that moves the
PRIMARY question is **more OOS dates**, and the only ones that are not more of
this same correlated window are the **live 2026-08/09 dates once their options
expire and price** — the independent window §2.2 and the rollback triggers also
wait on them. Until then, **on these dates the exit question is closed for all
five arms.** UNDERPOWERED publishes its census and is **not re-run on these
dates**; the grid is not re-cut, no arm is re-registered under a different
anchor, and the two `all` NULLs are recorded as NULLs, not read as findings on a
cut that carries no verdict.

**Records.** `study-results/f2_management/exit_drawdown.md` — the GRADED run is
v4 at sha `e1af7f8`, and **the RECORDED run this entry is read against is the
same run re-run at `efd9b76`**, after the `SHIPPED_BE_AFTER` pin (identical
verdicts and cells; the pin's only effect is the basis line and ARM O's
hold-window census, above) — plus the v4/v3 runs at `e19d3b4`. Also
`pre-registrations/f2_management/exit_drawdown.md` (with
`exit_drawdown-errata.md` beside it — folded into the registration 2026-09-08)
and `study_output/exit_drawdown-census-2026-09-05.txt`. The v3 SECONDARY run was
likewise re-run at `efd9b76`
(`study_output/exit_drawdown-v3-2026-09-05.txt`) and is recorded at that sha
beside the v4 section.

A recording trap was fixed the same evening (`d69a802`).
`scripts/study_map/summary.py` quoted the LAST banner containing `VERDICT`, and
this report's last banner is
`DISCLOSURE, in-sample — NO VERDICT IS READ FROM ANYTHING BELOW` (the disclosed `all` cut prints after the verdict summary). Two sections had therefore recorded in-sample numbers as the study's
answer. A negated title is now skipped, the two mis-recorded (uncommitted)
sections were dropped and re-recorded, and the committed record quotes
`VERDICT SUMMARY`.

## 2026-09-05 (later) — `overview.md` and `glossary.md` rewritten for a reader who has lost the thread; the long-dated blind spot is scoped DEBIT-ONLY

Nothing ships and no number moved. One queue item narrowed: the long-dated
blind spot ([`next-steps.md`](next-steps.md) [§2.7](next-steps.md#s2-7)) is now
recorded as a **debit-side** gap only. The operator does not hold credit
positions at a `horizon` of 180 or 720 days, so the parked credit exit knobs in
the same bullet do not wait on long-dated price history. Everything else in
this entry is prose.

_No study run. Documents touched: [`overview.md`](overview.md),
[`glossary.md`](glossary.md), [`next-steps.md`](next-steps.md). Under
[`writing-guide.md`](writing-guide.md), adopted earlier the same day._

**In production.** Nothing changes.

**What changed in the prose.** Operator review of `overview.md` found the page
was readable only by someone who already knew the answers. The fixes:

| Was | Now |
|---|---|
| `§2.1`, `§2.2`, `§0` as bare numbers | linked; `next-steps.md` gained stable `<a id="sN">` anchors, matching the `deployment-rules.md` convention |
| bare `ARM C`, `H3`, `X2`, `B2`, `D5`, `H0` | linked to [`arm-index.md`](arm-index.md), each carrying its definition as markdown hover text |
| no route from the overview to a study's plan | every family table gained a **Plan** column linking the study's [`pre-registrations/`](pre-registrations/) file; a dash means the study predates the system |
| terms redefined inline (`CI`, `LOO`, `n`, `BEAR_HE`) | linked only, so there is one definition to keep current |
| `catalog.py` called "the hand-written verdict file" | corrected — an agent drafts those entries; the file is where a verdict is stored as prose, not a second opinion |
| "lost its `**` on all three cuts" | the marker is explained (CI excludes zero AND every LOO fold positive), the three cuts are named, and the CI half is separated from the 2026 sign flip |
| "day-5 and day-20 loss cuts" | replaced by the six harmful cells with their CIs; the real split is two day-5 loss cuts and four early profit exits |
| "the diagonal cut" | named as the `long_diag` re-wrap, one of three substitutions, with its five gates in a table |
| "clears the full conjunction" | "clears every one of its adoption criteria at once" |
| "do not re-litigate" | "settled, do not re-open", here and in `next-steps.md` §3 |
| "checked at their gates, never read from silence" | spelled out: a trigger that printed nothing usually has not reached its power floor, which is not the same as passing |
| `hedge_concentration` as "concentration does not predict drawdown" | given its own paragraph — the two-stage design is now explicit, so the `PRECONDITION-NULL` reads as "stage 2, does the hedge help, never ran" |
| two `RETIRED` rows with no verdict | see the deletion below |
| attempts table copied out of the archive index | the copy is DELETED. The section now points at [`archive/README.md`](archive/README.md) §Section index, names the two attempts still live in production, says why there is no attempt 14, and notes that the same index continues past 13 in date order into `current.md`. The link had been pointing at `README.md`, which has no such section |

[`glossary.md`](glossary.md)'s [LOO](glossary.md#loo) entry gained the
correction that matters most for reading any study here: **the fold is the KEPT
set, not the held-out one.** The dropped date is never scored. LOO here is a
robustness check — "would this rule still win if any one date had not
happened" — not a generalisation check.

**The two retired management studies are DELETED.** `combined_exit_study.py`
and `underlying_exit_study.py` are removed from the tree, along with their
`catalog.py` entries, `run.py`'s `DEFAULT_ARGS` line, and the
`f2_management/__init__.py` listing. Both were retired 2026-08-14 when their
gitignored scratch inputs proved unrecoverable; neither could be run, so
neither could ever revisit the rule it settled. **Neither ever shipped
anything** — `combined_exit_study` was a `reference` study that confirmed the
production exit profile was already the best global config (its one consequence
was starting the two switch studies), and `underlying_exit_study` was a `null`.
The verdicts are unchanged and the **record is now
[`study-map.md`](study-map.md#management)**, whose two rows were rewritten to
carry the question, the verdict, why the study cannot run, and the
[archive/02](archive/02-credit-debit-split-attempts-8-12.md) trail.
[`next-steps.md`](next-steps.md) §0c(B) was rewritten to match.
[`overview.md`](overview.md) drops them entirely: neither shipped, so two
deleted studies on a page about where things stand is cognitive load without
value (operator, 2026-09-05). `study-map.md` is where they are found.

The **retirement mechanism is kept** — `Study.retired`, `retired_studies()`,
`run --all`'s skip, the study-map `retired` pill — for a future case where the
module is still worth reading. No study carries the field now, so its tests no
longer borrow a real study as their subject: `tests/test_study_map.py` marks
one synthetically via `monkeypatch`, and both that file and
`tests/test_backtest_study_run.py` gained a test pinning that nothing is
retired by inheritance. Study count 34 → 33.

**Next.** No new item. `make check-doc-links` and the full suite (3,279) pass.

## 2026-09-06 — the gap-up hedge prohibition is ACCEPTED; the four missing rows are re-priced; a hedge-open indicator becomes the open item

Three operator decisions, no study run and no verdict moved. The drafted §4
gap-up prohibition is accepted, the hedge sleeve continues, and the missing
real-priced rows are back on the tab.

_Era v4 · exports still 2026-09-04 20:31 · `BacktestResults` now 540 rows
against the export's 535._

**In production.** [§4](../docs/deployment-rules.md#s4) gains one line: do not
open the hedge because the day gapped up. It rests on
[`hedge_timing`](arm-index.md#hedge_timing) H3-GAP, a paired excess of −0.506
[R](glossary.md#r) against ordinary days (CI [−0.844, −0.157], every
[LOO](glossary.md#loo) fold, all cuts). It is a restriction accepted on a
correlated window, not a shipped rule, and it bans the gap as the REASON to
hedge. Hedging concentrated exposure on a day that happens to gap is untested
and not covered. The "gating bought no drawdown protection" half of the
2026-08-28 draft is dropped, because the 166-date re-read moved H4-GAP to
`NULL`.

**The sleeve stays, so the trigger question is open.** Four candidate
indicators have been tested and none survives.

| Trigger | Study | Verdict |
|---|---|---|
| gap-up | `hedge_timing` H1/H3-GAP | `CONTRARY`, now prohibited |
| chop | `hedge_timing` H1/H3-CHOP | `NULL` |
| SPY down-run | `hedge_timing` DECLINE | `NULL` powered, `UNDERPOWERED` at the strict rule |
| book concentration | [`hedge_concentration`](arm-index.md#hedge_concentration) ARM K | `PRECONDITION-NULL` |

Finding one is now [`next-steps.md`](next-steps.md) §2.10. It does not reopen
the 2026-09-04 closure: a fourth timing study cut from these dates and these
columns is still refused, and a candidate has to bring a column the book does
not carry yet — hedge flow, or a live exposure figure — read on the
mark-to-market curve.

**The four missing rows are re-priced.** Both dates were re-run per date on
2026-09-06 and all four rows priced real, both legs `barchart_open`.

| Date | Ticker | Structure | DTE | Realized | Exit |
|---|---|---|---|---|---|
| 2025-12-22 | TSLA | `bull_call_spread` | 724 | −46.7% | `dollar_stop` |
| 2025-12-22 | AMD | `bull_call_spread` | 87 | −11.5% | `time_exit` |
| 2025-09-26 | CRWV | `bull_call_spread` | 172 | −78.1% | `stop_loss` |
| 2025-09-26 | HYG | `bear_put_spread` | 25 | +282.4% | `profit_target` |

Two consequences, neither repaired. The 2025-12-22 re-run re-emitted SPY
`bear_put_spread`, which was already on the append-only tab, so that row is
there twice; the copies are identical but for `created_datetime`. And no study
sees any of this until `scripts/export_tabs.py` refreshes
`backtests/to_evaluate/`, which changes the population every study runs on. The
TSLA row is 724 DTE and priced fully real, which is one row inside the
long-dated blind spot rather than a lifting of it.

**Prose.** `exit_drawdown`'s ARM P "dollars ban is scoped" passage was cut from
two defensive paragraphs to two short bullets. The conflict is stated in one
sentence, the chosen reading in one, and the operator's ACK is still owed —
substance unchanged, which the diff shows. The house rule behind the cut is now
[`writing-guide.md`](writing-guide.md) rule 9.

**Next.** [`next-steps.md`](next-steps.md) §0 item 1 closes as an operator task,
§2.10 opens, and the ARM P ack is still owed.

## 2026-09-06 (later) — the SPY duplicate and 15 older duplicate rows are DROPPED; the export is 524 rows; `AnalysisClaude` keeps both runs

The book had been counting 16 rows twice. It no longer does. The cause is
untouched and sits one layer up, in `AnalysisClaude`.

_Era v4 · exports 2026-09-06 · `BacktestResults` 524 rows over 159 dates, tab
and export in agreement, zero duplicate groups._

**What was dropped.** 16 rows in all: the 2025-12-22 SPY `bear_put_spread` copy
from the morning's re-run, then 15 older copies across 13 groups. In every group
the copy with the LATER `created_datetime` was kept, on the operator's
instruction. The tab has no git history, so both tabs were snapshotted to
`backtests/to_evaluate/_snapshot-*-pre-dedup-20260906.csv` before the delete.

| Signal date | Groups | Rows dropped | Survivor stamp |
|---|---|---|---|
| 2024-09-16 | 7 | 9 | `2026-08-26 23:55:16` |
| 2025-09-10 | 1 | 1 | `2026-08-27 11:33:20` |
| 2025-09-18 | 5 | 5 | `2026-08-27 12:17:09` |

`ORCL` and `RH` on 2024-09-16 had three rows each and the later two shared a
stamp, so the timestamp could not separate them. They were separated by which
ANALYSIS run each came from, read off `score_total`: `ORCL` 29 and `RH` 28 are
the earlier analysis, 28 and 27 the later. The later analysis survives, which
is the same rule as everywhere else.

| Tab | Before | After |
|---|---|---|
| `BacktestResults` | 540 rows | 524 rows, 159 dates |
| local export | 539 rows | 524 rows, 159 dates |

**One consequence, recorded rather than repaired.** The backtest stamps every
play with the newest `MARKET` row on its date. 2025-09-18 was analysed twice
and the second run does not contain `MU`, `MSTR`, `QQQ`, `SMH` or `XLI` at all.
So their surviving rows pair a play from the first run with the second run's
market read: `BULL + C-VOL` where the run that proposed them said
`RANGE + L-VOL`. Keeping the newer copy is what the operator asked for, and on
these five rows the older copy was the internally consistent one. Any regime
cut on 2025-09-18 sees the later label.

**The cause is untouched, and it is not a duplicate problem.** Exactly three
analysis dates carry two `created_datetime` stamps, and they are the same three
dates: 2024-09-16, 2025-09-10, 2025-09-18. The pipeline has no date dedup, so
re-analysing a date appends rather than replaces. But the two runs did not
produce copies — they produced DIFFERENT plays.

| Date | Analysis rows | The two runs |
|---|---|---|
| 2024-09-16 | 22 | 11 and 11; the first has `QQQ` and `MU`, the second `SPY` and `META` |
| 2025-09-10 | 25 | 12 and 13; the later adds `IBIT` and `IREN` |
| 2025-09-18 | 26 | 14 and 12; 8 tickers differ and the `MARKET` regime flips |

33 extra analysis rows. Deleting one run is a decision about the population,
not a repair, so nothing was deleted. Until it is made, a backtest re-run over
these dates re-emits both runs' plays and the duplicates come back.

**Next.** The suite has not been re-run. It can be, on a book that is now clean
at the backtest layer; the `AnalysisClaude` decision is
[`next-steps.md`](next-steps.md) §0 item 2.

## 2026-09-06 (third) — 40 pre-registered dates were never run; the 2026 sample misses its own crash

The neutral-date campaign dropped 40 of its 192 selected dates, and 13 of them
are the 2026 sessions that carry the March drawdown. Nothing ships. Three
queues are written and none has been run.

_Era v4 · exports 2026-09-06 · 524 real rows over 159 dates · selection rule
[`backtests/neutral_dates_v1.md`](../backtests/neutral_dates_v1.md)._

**The bug.** Step 4 of the selection rule subtracts "any date present in
`analysis - AnalysisClaude.csv`". That export was a v3 export when the rule ran
on 2026-08-14, so 37 dates were dropped for being in a population v4 no longer
draws from. Three more have no rows in any era. Recomputing `index % 3 == 0`
over `[2024-01-02, 2026-04-16]` against the current v4 export reproduces the
192 and finds the 40.

**Why the 13 matter.** The v4 book's eleven 2026 dates sit either side of the
March fall without sampling it. SPY closed 683 on 2026-01-02 and 632
on 2026-03-30, then 773 by 2026-09-03.

| 2026 dates | n | VIX mean | VIX range |
|---|---|---|---|
| in the book | 11 | 17.66 | 14.49 – 21.04 |
| dropped by step 4 | 13 | 23.18 | 16.34 – 30.61 |

All seven March sessions are in the second row. The book's own 2026 rows are
positive — [meanR](glossary.md#meanr) +0.231 on n=31, win 0.61 — so the
negative 2026 column in several studies is a statement about effects, not about
the year.

**The right edge has moved.** The bound 2026-04-16 was 2026-08-14 minus
`path_cap_days: 120`. Today's frontier is 2026-05-09. Re-running the rule over
the longer window gives 197 = the same 192 plus 5 new dates, because appending
sessions cannot shift the modulo phase. The left edge could not be patched this
way, and that asymmetry is already recorded in the selection file.

**The queues.**

| Queue | Dates | Collection state | Runner |
|---|---|---|---|
| `backtests/enrich_queue_c.txt` | 13, all 2026 | enriched in 2026; needs the probe below | `analyze_bt_queue.sh` |
| `backtests/enrich_queue_d.txt` | 24, pre-2026 | enriched in 2024-25; needs the probe below | `analyze_bt_queue.sh` |
| `backtests/enrich_queue_e.txt` | 5, 2026-04-21 → 05-07 | never collected | `scrape_and_enrich.sh`, then analyze |

**Probe the Drive files before running C or D.** Both queues assume the
compiled flow CSV is still in Drive with its enrichment columns. The v3 export
proves those columns existed when the dates were current. It does not prove the
files are there today. `--skip-llm` fetches from Drive, writes the audit CSV
and never touches Sheets, so it settles it for free:

```bash
for d in $(cat backtests/enrich_queue_c.txt.done); do
  python3 -m scripts.analysis_pipeline --date $d --skip-llm >/dev/null 2>&1 \
    && echo "$d ok" || echo "$d NEEDS SCRAPE+ENRICH"
done
```

A date that prints `NEEDS SCRAPE+ENRICH` moves to a scrape queue in the
`enrich_queue_e.txt` format. The `.done` seeding marks these dates enriched, so
`analyze_bt_queue.sh` will not check for itself.

`scripts/analyze_bt_queue.sh` was restored from `973922a`; it had been deleted
when campaign b closed. Excluded from queue D: 2024-01-02 and 2024-01-05 sit at
the proven Barchart retention floor, and 2025-12-26 already produced zero
analysis rows. 2026-02-24 is in queue C but has one v3 row and no enrichment,
so expect it to yield little.

**Stated before the run.** These dates were selected on calendar position alone
in 2026-08-14, before any 2026 outcome was read. The omission is a mechanical
fault in step 4. Running them finishes the registered selection rather than
making a new one, and needs no new registration. The 2026 column has already
been read once, so the honest expectation is written here rather than after:
adding the March sessions will move every per-year criterion that currently has
a 2026 cell, and it may move them either way.

**What this does not do.** The 13 sit inside `[2024-01, 2026-04]`, so they do
not make the window independent. §2.2 and §2.6 stay blocked on dates after
2026-08-11. `protocol.DOMINANT_WINDOWS` already re-cuts every result without
`ex_2026_feb_apr`, so the crash sessions will be excluded by construction in
the robustness cut.

**Next.** [`next-steps.md`](next-steps.md) §0 gains the queues as an operator
item. The two hardcoded 2026-03 tables stop being no-ops once queue C runs.

## 2026-09-07 later — the 12 stale backtest rows are dropped, and the backtest can no longer double a row

The evidence base is 543 rows and every one of them joins the play that
proposed it. Nothing ships: this is a data repair and a guard, not a result.
The 12 rows the morning's analysis repair left pointing at a play that no
longer existed are gone, and `scripts.backtest` now refuses to write a play its
results tab already holds.

_Era `v4` · all three exports re-pulled 2026-09-07 · `BacktestResults` 543 rows
over 168 dates · pooled study book 1,183 rows over 177 dates._

### The 12 rows are dropped

The operator's decision from the morning entry, taken. The rows were identified
by the same key the studies join on, so "a row a study cannot join" and "a row
this deleted" are the same set by construction.

| | Rows |
|---|---|
| `BacktestResults` before | 555 |
| dropped | 12 |
| after | 543 |

A row-level diff against a pre-delete snapshot
(`backtests/to_evaluate/_snapshot-BacktestResults-pre-dedup-20260907.csv`) shows
exactly those 12 gone, nothing else removed and nothing added.

The evidence base moves 524 → 543, not 524 → 512. The morning entry framed the
choice as "524 → 512" against an export that was already 31 rows behind the tab.
The count went UP because the daily pipeline had added more rows than the repair
took away.

**What this changes for the studies.** Nothing recomputes. Entry, exit and P&L
were priced at backtest time, and deleting a play row reprices nothing. What
changes is the join: [`text_features`](arm-index.md#text_features) no longer
reads the wrong play's text on 7 rows, and
[`mech_regime_recut`](study-results/f1_selection/mech_regime_recut.md) and
[`regime_gap_reread`](study-results/f1_selection/regime_gap_reread.md) will
print a different join coverage.

**Two rows were deliberately not dropped.** `2025-07-29` `COIN` and `EEM` also
fail to join, from an unrelated cause. Their analysis rows went missing
separately, three minutes after the backtest that read them, so the backtest row
is the only surviving record that those plays were ever proposed. They fail the
join outright rather than landing on a different play, which is the safe failure
and the one studies already count. Dropping them would destroy evidence to tidy
a count.

### Neither results tab holds a duplicate

Checked directly on the refreshed exports, on the identity key both writers use.

| Tab | Rows | Repeated identity keys |
|---|---|---|
| `BacktestResults` | 543 | 0 |
| `BacktestProxy` | 1,380 | 0 |

One proxy row overlaps a real row on (date, ticker, structure) rather than on
the identity key. `load_book` already drops it in favour of the real row; it is
that function's pooling rule, not a duplicate on a tab.

### The backtest now refuses to write a play it has already written

The hole the morning entry named as open is closed. It was a real one: the
2025-12-22 `SPY` duplicate found on 2026-09-06 came from a re-run of
`scripts.backtest`, and 15 older duplicates came with it.

A backtest re-run is not the same failure as a doubled analysis, and the
difference is worth stating. A second analysis run proposes *different plays*.
A second backtest run reprices the *same play* on whatever the exit config, the
cached Barchart history and the classifier say today — so the two rows disagree
about the exit, the basis and the P&L while looking equally authoritative.
`exit_basis` exists because that already happened once, across the 2026-07-22
exit change.

| | Behaviour |
|---|---|
| play already on `BacktestResults` | dropped before the Barchart fetch |
| play already on `BacktestProxy` | dropped before evaluation, as before |
| every candidate is a duplicate | logged, exit 0 |
| `--redo` | re-simulates and DELETES the old rows before appending; needs a date bound |
| `output.sheet_tab: null` | not checked, and no Sheets read — the local CSV is rewritten, not appended |

Two details carry the weight. The check sits before the Barchart fetch, for the
same reason the analysis guard sits before the first model call: a guard that
costs a run to reach is not a guard. And `--redo` deletes before it appends,
because the reverse order produces exactly the duplicate it exists to prevent.

**One key, one copy.** `scripts/backtest/shared/identity.py` now holds the
`(date, TICKER, 60-char play prefix)` key that both writers use. Two copies
would let the real backtest and the proxy disagree about what a duplicate is.
It is deliberately the same 60-char normalisation the study loader joins on, so
the writers' notion of row identity and the studies' are one notion. Contract:
`docs/architecture.md` §"The already-backtested guard"; tests:
`tests/test_backtest_dup_guard.py`.

**Next.** [`next-steps.md`](next-steps.md) §0 loses its operator decision. The
suite still has to be re-run deliberately, now on a settled population.

---

## 2026-09-07 — the three doubled analysis dates are repaired; the pipeline now REFUSES a date it has analysed

The root cause is closed at both ends. 37 rows of the earlier analysis run were
deleted from `AnalysisClaude`, and the pipeline can no longer create the
condition again. The repair left 12 backtest rows pointing at plays that are
gone, which is the finding worth carrying forward.

_Era v4 · `AnalysisClaude` 2,325 rows over 198 dates, one run per date, tab and
export in agreement._

### What was deleted

Three dates carried two `created_datetime` stamps. The LATER run was kept on
each, the same rule applied to `BacktestResults` on 2026-09-06.

| Date | Before | Dropped | Kept |
|---|---|---|---|
| 2024-09-16 | 22 | 11 (`2026-08-26 0:49:52`) | 11 |
| 2025-09-10 | 25 | 12 (`2026-08-26 14:52:42`) | 13 |
| 2025-09-18 | 26 | 14 (`2026-08-27 0:45:51`) | 12 |

The tab went 2,362 → 2,325 rows; a row-level diff against the pre-delete
snapshot (`backtests/to_evaluate/_snapshot-AnalysisClaude-pre-dedup-20260907.csv`)
shows exactly those 37 gone and nothing else touched, nothing added. No date
carries two stamps now. `export_tabs.py` re-pulled: the export was ALSO stale by
the daily pipeline's rows since 2026-09-06, so it moved 2,224 → 2,325 over 198
dates rather than down.

### The finding: 12 backtest rows now point at a play that no longer exists

This is the cost of the repair and it is not the regime flip already recorded.
5 rows lose their analysis row outright. **7 keep a (date, ticker) match and
join to a DIFFERENT play** — the join does not fail, it silently returns the
wrong one.

| Date | Ticker | What the join does now |
|---|---|---|
| 2024-09-16 | `MU`, `QQQ` | orphaned — no analysis row |
| 2025-09-18 | `MSTR`, `MU`, `XLI` | orphaned — no analysis row |
| 2024-09-16 | `IWM` | `bear put 215/195` → joins `bear put 210/195` |
| 2024-09-16 | `TSM` | `bull call 180/…` → joins `bull call 175/…` |
| 2024-09-16 | `EEM`, `MSTR` | joins a same-structure play at other strikes |
| 2025-09-10 | `NVDA` | `bull call 180/…` → joins a **`bear put 175/155`**; the direction flips |
| 2025-09-18 | `QQQ` | `bear put 570/530` → joins `bear put 585/555` |
| 2025-09-18 | `SMH` | `bull call 320/…` → joins `bull call 325/…` |

`SMH` on 2025-09-18 has TWO backtest rows, one from each analysis run, and both
survive — the second is now the one joining the wrong play.

**What this affects.** Any study reading a play THROUGH the join:
[`text_features`](arm-index.md#text_features) reads the play text, and
[`mech_regime_recut`](study-results/f1_selection/mech_regime_recut.md) and
[`regime_gap_reread`](study-results/f1_selection/regime_gap_reread.md) print
join coverage, so they will show 7 of 524 rows landing on a different row than
before plus 5 no longer landing at all.

**What it does NOT affect.** The 524 result rows themselves. Entry, exit,
pricing and P&L were computed at backtest time from the play as it then stood;
deleting an analysis row does not reprice anything. Total orphans in the export
are 7, of which 2 (`2025-07-29` `COIN` and `EEM`) pre-date this repair and are
unrelated.

**Not repaired, and it is a decision, not a bug.** Dropping the 12 rows would
change the evidence base 524 → 512 and is the operator's call.

### The correction to the 2026-09-06 entry

That entry said the later 2025-09-18 run "does not contain MU, MSTR, QQQ, SMH or
XLI at all". Three of those are right — `MU`, `MSTR`, `XLI` are absent. `QQQ`
and `SMH` ARE in the later run, with different strikes, which is why they became
wrong-play joins rather than orphans. The entry's own headline claim (5 backtest
rows on 2025-09-18 carry a later run's regime) stands: they are `MSTR`, `MU`,
`QQQ`, `SMH` and `XLI`, attributed by matching play text.

### The pipeline now refuses a date it has already analysed

`scripts/analysis_pipeline/core.py::_drop_already_analysed`. `append_rows`
appends, and the analysis step is not deterministic, so a second run on a date
does not duplicate it — it proposes different plays and the tab pools two
populations into one. The guard refuses such a date in ONE Sheets read taken
before the first fetch, so it costs no LLM spend to reach.

| | Behaviour |
|---|---|
| date already on the tab | refused; exit 1 if nothing is left to do |
| `--start`/`--end` | analysed dates refused, new ones run, exit 0 |
| `--tickers` | keyed on (date, TICKER) — a new name on an analysed date runs |
| `--dry-run` | warns and runs; it writes nothing, so it cannot double anything |
| `--skip-llm`, `--output-dir` | not checked — neither can reach `append_rows` |
| `--allow-duplicate-date` | the override; appends beside the existing rows |

`--output-dir` stays a separate structural guard: a candidate prompt's rows for
a NEW date pass this one, and must still never reach the tab. Contract and
tests: `docs/architecture.md` §"The already-analysed guard",
`tests/test_analysis_pipeline_dup_guard.py`.

**The backtest has the same shape of hole and it is NOT closed.** The
2025-12-22 `SPY` duplicate on 2026-09-06 came from a re-run of
`scripts.backtest`, not from a doubled analysis. Nothing stops that recurring.

## 2026-09-07 (later) — robustness review: twelve items built, six landed in the tree, six wait in two worktrees for the campaign to end

Every item the [review](robustness-review.md) marked workable while queues C and
E run is built and approved by an independent reviewer. Nothing is committed.
The main tree is green on 3,406 tests and `make check-doc-links`. The
backtest-engine and analysis-guard changes sit in two git worktrees because the
campaign imports those files per date.

| Item | Outcome | Where |
|---|---|---|
| P1 closed spread inverted | fixed; `python3 -m scripts.journal relabel` diffs past rows offline | main tree |
| P2 no-NetLiq bypassed `assess()` | fixed; `assess(caps=None)` always computes totals | main tree |
| P3 failed Sheets write never retried | fixed; writers diff the tab's own ids against all local rows | main tree |
| P6 scrape exit 0 on zero rows | fixed; per-prefix floor in the watchdog | main tree |
| P8 journal unscheduled | weekday workflow + watchdog stage; needs the CI secret | main tree |
| A5 stale "held back" messages | fixed | main tree |
| B1 cost model | knobs default 0; three columns end-appended | worktree `-5` |
| B2 pre-fill P&L | pre-entry grid days present but UNPRICED; day indices unchanged | worktree `-5` |
| B3 stale carry | bounded, `barchart_stale` tag, leg-day `pct_real_days` | worktree `-5` |
| B5 zero bid | 0 when ask is 0, else ask/2 | worktree `-5` |
| A1 empty-table analysis | skip before the LLM; zero plays refused | worktree `-6` |
| A4 per-play validation | keys and enums checked; attempt count in the manifest | worktree `-6` |
| N1, N2, N5 | DRAFT pre-registrations, indexed, not registered | `research/pre-registrations/` |

### What building them found

- **The journal's past CLOSE rows are a known-inverted cohort.** 18 of 18
  CLOSE rows in `journal/trades.csv` carry an inverted `structure` and 3 an
  inverted `tier` (GLD ×2 on 2026-08-28 read VETO, are B; IWM on 2026-08-31
  read B, is C). The same rows are on the `TradeJournal` tab. Repair needs a
  `journal/` edit and a Sheets write, neither done. Until then
  `date < 2026-09-07 AND action == CLOSE` is excluded from any Stage 2 join.
- **The report's "attempts matched" headline now counts OPEN events only.**
  With closes matching their play, a same-play open+close read 2/2 for one
  attempt. `s04a_report.py` and `s04b_page.py` each carry the rule
  independently, as with the cap rule.
- **B2 keeps the grid origin.** The first pass moved the grid to the entry
  date and broke the frozen harness's `len(marks) == len(grid)` and
  `mtm_curve`'s index-0 assumption. The landed design marks pre-fill days
  unpriced with a `pre_entry` source tag, so no exit, MFE or MAE books on
  them. Rows written before the fix may hold pre-entry P&L (about 4% of
  positions per the review); a `--redo` re-price cleans them. `mtm_curve`'s
  carried-forward count rises for late fills and nothing gates on it.
- **B1's three cost columns need both results-tab headers aligned** before
  the first write after the merge (`align_tab_headers.py`). With the knobs at
  0, every recorded number is unchanged.
- **Both worktrees branched from `294764a`, five commits behind `main`.**
  `scripts/backtest/core.py` is touched by both the worktree and `a9b51c8`.
  Merge by hand, not by assuming a clean apply.
- **The campaign is running three copies of `analyze_bt_queue.sh`**, one on
  queue C and two on queue E, against the script's own rule. The second E
  copy flagged 2026-05-04 SKIPPED-PARTIAL while the first was still running
  it. Read E's ledger against the tab before trusting it.
- **Two draft decisions are the operator's before acceptance.** N1 reads
  "$0.65 per contract plus 25% of the spread per leg" as per leg PER SIDE and
  charges it twice. N5 seals on-or-after 2026-08-11, unseals at 40 priced
  dates, and leaves the §2.2 conflict open with two options.
- **Two latent items, not fixed.** `s04b_page.py` raises `ReconcileError` on
  a zero-event day (pre-existing). `account_sim`'s exposure window still
  starts at `grid[0]`, a pre-entry session for a late fill (pre-existing).
- `tests/test_arm_index.py` now scans the family folders; it had matched only
  the README. One false positive (`ARM MRVL`, two tickers) is pinned.

Next, after the campaign ends: merge the two worktrees, align the headers,
re-run the suite once, then accept and run N1 and N2.

## 2026-09-07 (fourth) — hedge_structure — the new dates do not unblock it; two cached legs have gone missing

The 12 backtest dates the campaign has added so far move the calendar sleeve's
worst-decile cell from 4 positions to 5. The power floor is 10, so
[H2](arm-index.md#hedge_structure) stays `NOT EVALUABLE` and nothing ships. The
wall is the fill rate, not the date count. The sleeve fills on half the deployed
dates and a third of the worst decile, and the new dates fill at that same rate,
so the cell reaches 10 only at roughly twice today's deployed dates.

_Era v4 · live tabs staged 2026-09-07 20:23 and NOT installed · 569 real /
1,523 proxy rows over 180 / 192 dates · report kept in the session scratchpad,
not in `backtests/study_output/`, and nothing appended to study-results._

**In production.** Nothing changes. [§4](../docs/deployment-rules.md#s4) keeps
its one sleeve.

**How it was run.** `export_tabs.py --dest` staged the live tabs outside
`backtests/to_evaluate/`, and the study's `main()` ran with `era.EVAL_DIR`
pointed at the staging directory. The installed export and every `-latest.txt`
are untouched. The checkpoint store `backtests/sweep_cache/synth_results.csv`
did gain rows, keyed by cache signature, as any run would. Two rows were set
aside for the projection; the next paragraph says why.

**A stop before the power floor.** The live tabs fail R2 with
`leg_not_cached 2`. The short legs of IWM 2026-05-29 245P (signal 2026-04-13)
and MSTR 2025-06-27 420C (signal 2025-06-05) have no file in
`backtests/option_history_cache/`. Both rows are on the installed 2026-09-07
export too, and the MSTR row passed R2 on 2026-09-04, so the file was lost
between that run and today. Until the two files are back, `hedge_structure`
exits 1 at R2 on the next suite run, and the three studies that share the
reconstruction check should be expected to stop the same way.
`scripts/backtest/shared/history.py` writes the cache on a miss, so a
`--redo` of the two signal dates refetches them; `backup_research_caches.py
pull` restores them if the Drive snapshot holds them. Operator's call which.

**Evidence.** The primary H2 block, P1 under the production exit profile.

| Line | 2026-09-04 export, recorded | live tabs 2026-09-07, projection |
|---|---|---|
| Deployed dates | 147 | 163 |
| Worst-decile dates | 14 | 16 |
| H0 fill, deployed dates | 75 / 147 = 51.0% FAIL | 83 / 163 = 50.9% FAIL |
| H0 fill, worst decile | 4 / 14 = 28.6% FAIL | 5 / 16 = 31.2% FAIL |
| H2(a) date-level corr | −0.100, CI [−0.228, +0.017], MET | −0.102, CI [−0.221, +0.003], MET |
| H2(b) worst-decile cell | n=4, [meanR](glossary.md#meanr) +0.810, `UNDERPOWERED` | n=5, meanR +0.557, `UNDERPOWERED` |
| H2(c) worst-quartile tail | positive in 3/3 years | positive in 3/3 years |
| H2 | `NOT EVALUABLE` | `NOT EVALUABLE` |
| H3 sizing | NOT MET at any size | NOT MET at any size, drawdown-bound |

What the cell needs, at the fill rates the book has shown:

| Fill on worst-decile dates | Worst-decile dates for n ≥ 10 | Deployed dates implied |
|---|---|---|
| 31%, observed | 32 | ≈ 320 |
| 60%, the H0 floor | 17 | ≈ 170 |

Dates still in the pipeline: 15 from queue D, and the 19 live sessions
2026-08-11 → 2026-09-04 that price from December 2026. Together they reach about
197 deployed dates and a cell of about 6.

**Caveats.** The projection drops two rows, so it is not the figure a recorded
run will print; the recorded run is the one that goes in study-results. The
fill rate is a property of what the option cache holds, two expiries at one
strike on the entry session, and no collector fetches that for the H arm;
`fetch_sweep_legs.py` serves ARM S and was last run 2026-08-13.

**Next.** [`next-steps.md`](next-steps.md) §2.3 stays blocked and now states
the size of the wall. §0 gains the two missing cache files as a hazard to clear
before the suite re-run.

## 2026-09-07 (fifth) — hedge programme — criteria consolidated, two studies deleted

**The hedge contribution rule, the sizing rule and the drawdown function now
have one body each, and no report moved.** Six modules carried a copy of
`hedge_sizing`'s `D2`, four carried its `D3`, and the drawdown function existed
three times. Seven reports were reconciled one at a time, and every body is
byte-identical before and after. Two modules are gone: `vol_sleeve` is
retired into [`hedge_structure`](arm-index.md#hedge_structure) gate `R4`, and
`hedge_concentration` is now
[`hedge_portfolio`](arm-index.md#hedge_portfolio)'s `--admitted` arm.

_Era v4 · installed export 2026-09-07 12:17 · pooled study book 1,183 rows over
177 dates · plan in `hedge-programme-plan.md` (deleted 2026-09-08 once executed; git `be6cfd0` holds it), spine
in [`f5_hedging/README.md`](../scripts/backtest_study/f5_hedging/README.md)._

**In production.** Nothing changes. No verdict, gate or arm label moved, and
[§4](../docs/deployment-rules.md#s4) keeps its one sleeve.

**What the library holds.** `scripts/backtest_study/lib/hedge_criteria.py` owns
one contribution rule, one sizing rule, the 1-per-day sleeve picker and the
daily-series builder, transcribed from `hedge_sizing` with every threshold and
tie-break intact. It re-exports `max_drawdown` from `lib/mtm_curve.py` rather
than holding a second body. It prints nothing and owns no fraction grid, because
a narrowed grid is a registered choice and stays in the study.
`tests/test_hedge_criteria.py` pins it against a hand-written 16-case fixture,
the way `tests/test_harness_replay.py` pins the frozen engine.

**Evidence.** One row per study. "Body identical" compares the report with the
runner's header and footer stripped.

| Study | What moved to the library | Body identical | Commit |
|---|---|---|---|
| `hedge_sizing` | the reference for `D2` and `D3`; its six functions are now wrappers; post-hoc `D5`'s inlined comparison in the follow-up | yes, both runs | `a9b713a`, `90e21a5` |
| `hedge_timing` | the `max_drawdown` fork and `daily_dollars`; `ARM H4`'s two inlined size comparisons in the follow-up | yes, both runs | `8c03502`, `90e21a5` |
| `vol_sleeve` | module DELETED; its synthesis layer is now `lib/sleeve_synth.py` | yes, via `hedge_structure` | `5be4ba6` |
| `hedge_structure` | the per-year tail cut, the sizing sweep and verdict, the sleeve pick | yes | `4ed865f` |
| `hedge_concentration` | module DELETED into `hedge_portfolio --admitted`; no criterion moved | yes | `7187ca2` |
| `hedge_portfolio` | nothing; it carries neither rule | yes, after a cache-attributed delta, see Caveats | `7187ca2` |
| `bear_rewrap` | the daily series only | yes | `3d20781` |
| `financed_spread` | the daily series only | yes | `0d27a37` |

Two library behaviours the fixture makes visible and does not change. An empty
sleeve passes the sizing rule vacuously at the largest fraction, so a study must
read the position count beside the verdict. And `least_harmful` is now computed
on every sweep rather than only in the `NOT MET` branch, unprinted either way.

**Review.** An independent review of the eight commits on 2026-09-08 found the
size comparison still inlined twice in `hedge_timing` `ARM H4` and once in
`hedge_sizing`'s post-hoc `D5`, so the sizing rule had two bodies after the first
pass. Commit `90e21a5` gives the library the scalar form, `unharmed`, routes all
three through it, and renames `hedge_timing`'s `sleeve_pick`, which shadowed the
library's helper with different `None` handling. Both reports reconciled again.

**Findings.** No copy disagreed with the library. Every report body reconciled.
Four things were recorded during the work and are quoted here verbatim, in the
words of the step that found them.

> R2 still FAILS after restoring exactly the two files named in this step.
> `python3 -m scripts.backtest_study run hedge_structure` (2026-09-07 22:08:48,
> era v4, book 1183 rows/177 dates) reports `reconstructs: 1177 / 1180 (99.7%)`
> with `failed: leg_not_cached 3` and `R2 FAIL`, exit code 1.

> Read-only diagnostic (scratchpad/diag_leg_not_cached.py, imports
> hedge_structure.load_book + bear_rewrap.reconstructs directly, no repo writes)
> identified the 3 failing (date,ticker) keys and the specific uncached legs:
> KEY ('2025-06-05','SPY') needs SPY 2025-07-25 555.00P (the 585.00P leg is
> cached); KEY ('2025-03-06','KWEB') needs KWEB 2025-04-25 35.00P AND 32.00P
> (both legs uncached); KEY ('2025-01-07','TSLA') needs TSLA 2025-02-28 360.00P
> (the 400.00P leg is cached). None of these three keys involve IWM 2026-05-29
> or MSTR 2025-06-27 at all — the two files this step was scoped to restore were
> not the blocker for any of the three currently-failing keys.

> All four of those additional missing files (SPY_20250725_555.00P.csv,
> KWEB_20250425_35.00P.csv, KWEB_20250425_32.00P.csv,
> TSLA_20250228_360.00P.csv) DO exist in the already-downloaded
> research-caches-20260905-1111.tar.gz snapshot (confirmed by `tar -tzf`
> listing) but were left un-extracted since restoring them was outside this
> step's explicit scope (only the two named IWM/MSTR files were authorized).

> FINDING-OF-FACT (not a mismatch): bear_rewrap ARM P's bucket arithmetic
> genuinely differs from lib/hedge_criteria's D2 in three ways, so it was NOT
> routed through the library. (1) Worst-decile cut: bear_rewrap takes a VALUE
> cutoff -- cutoff = sorted(values)[max(0, n//10 - 1)] then {d : v <= cutoff},
> so ties are carried in and there is no floor; hedge_criteria.hedge_contribution
> takes the positional order[:max(DECILE_MIN=3, n//10)]. On the current v4 export
> the two are not guaranteed to select the same date set. (2) P1's verdict is a
> bootstrap CI excluding zero (P.boot_ci_by_date, lo > 0) measured on the
> SUBSTITUTION's own rows on those dates; D2's is a bare tail mean > 0 on a
> paired bear daily series. (3) P2 requires 8 shared dates and passes at
> corr <= 0, where D2's power floor is MIN_COMMON_DATES=20 and it needs
> corr < 0; and bear_rewrap's per-year clause is a per-year CORRELATION
> (>=8 points), where D2's is the per-year worst-quartile tail sign over
> MIN_TAIL_YEARS. Only the daily-series build was arithmetically identical
> (str-keyed date buckets, statistics.fmean over non-None R; book rows carry str
> dates and float R, so bear_rewrap's float() cast and direct r['date'] key were
> identity), and that is what now calls HC.daily_series(ladder, 'R', 'R_dol'),
> taking the mean leg only.

The first three are resolved. Six files were restored from
`research-caches-20260905-1111.tar.gz`, and `hedge_structure` now reads
`reconstructs: 1180 / 1180 (100.0%)` and `R2 PASS` on the installed export. The
fourth stands: `bear_rewrap` `ARM P` keeps its own cutoff and its own `P1`/`P2`
verdicts, because routing them through the library would move printed figures
under registered labels.

**Caveats.** The plan's two start conditions were overridden, by the operator,
after checking that neither risk reached this work. Queue D writes to Sheets and
to the option cache, not to the installed export, and every reconciliation read
the same export. The robustness worktrees touch no file under
`scripts/backtest_study/`.

The one moving input was the option cache, which
`scripts/backtest/shared/history.py` refreshes in place: a file whose history
does not reach back to the signal date is deleted and refetched, so the file
count moves while the queue runs. That made `hedge_portfolio`'s `ARM N` null
band cache-sensitive. Its two p95 figures in the whole-book report moved between
two runs 21 minutes apart, +0.3825 to +0.3704 and +0.3465 to +0.3549, because
queue D was writing option history under the study (43,047 to 43,038 contract
files). The pre-merge module run on the later cache prints the after report byte
for byte, so the delta is the cache and not the merge; the merge was proved
against a fixed cache and nothing the study concludes moves. But a report quoted
from a run taken while a queue writes to the cache is not reproducible line for
line.

**Next.** [`next-steps.md`](next-steps.md) §0 closes its missing-cache-file
hazard. Nothing else opens or closes. The two sleeve-sizing bodies outside the
sweep shape, in `account_sim` and `portfolio_delta`, stay named in the plan and
out of scope.

## 2026-09-08 — hedge programme — three studies renamed after their question; the two deleted studies lose their leftover files

**The four hedge studies are now named after the question each answers in
[`f5_hedging/README.md`](../scripts/backtest_study/f5_hedging/README.md), and nothing else changed.** Operator
decision, 2026-09-08. Every arm, gate and criterion label is as registered, and
every figure is the one on record.

| Was | Is | Question |
|---|---|---|
| `bear_deploy` | `hedge_sizing` | [Q3](../scripts/backtest_study/f5_hedging/README.md#q3), and the origin of `D2`/`D3` |
| `calendar_hedge` | `hedge_structure` | [Q2](../scripts/backtest_study/f5_hedging/README.md#q2) |
| `hedge_exposure` | `hedge_portfolio` | [Q4](../scripts/backtest_study/f5_hedging/README.md#q4) |
| `hedge_timing` | unchanged | [Q1](../scripts/backtest_study/f5_hedging/README.md#q1) |

What moved with each name: the module in `f5_hedging/`, its tests, its
pre-registration (one prose line added under the registration date, nothing in
substance), its per-era record (file and H1 only; the recorded sections still
quote the old name verbatim), and the local report stems under
`backtests/study_output/`, because `hedge_structure` globs its own stem for the
resume checkpoint. The archive keeps the old names; only its link targets were
repointed. [`arm-index.md`](arm-index.md) carries an alias anchor under each old
name so an old link still lands.

**`vol_sleeve` and `hedge_concentration` now leave only their DELETED rows.**
Their pre-registrations and frozen records were deleted (operator: leftover
files of a deleted study are bloat), together with their gitignored report and
review files and a stale bytecode cache. Git holds both files at `44bbfb2`; the
DELETED rows in [`study-map.md`](study-map.md#hedging) are the record, and every
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

**Next.** [`next-steps.md`](next-steps.md#s2-11) §2.11 marks the branch done.
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

**The spine is now [`scripts/backtest_study/f5_hedging/README.md`](../scripts/backtest_study/f5_hedging/README.md)**,
beside the studies named after its four questions. Every inbound link is
repointed and the link checker now scans `scripts/**/README.md`.

**The two open items moved to [`next-steps.md` §2.12](next-steps.md#s2-12):**
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
[registration](pre-registrations/f2_management/exit_drawdown.md) and §4 of the
errata (folded into the registration 2026-09-08) record the ACK, and
[`next-steps.md`](next-steps.md) §0 item 4 is resolved.

**What did not move.** No graded artefact. Clause 1 is a scale-free ratio, so
the verdict is identical either way, and no run ever displayed either form:
every ARM P cell on the 2026-09-05 runs of both eras was UNDERPOWERED and
printed its census only. The graded report, the two analyst gradings and the
study-results record stand as written.

## 2026-09-08 (fifth) — `exit_drawdown` errata FOLDED into the registration; the file is gone

**Two documents made the design unreadable, so there is now one.**
`research/exit_drawdown-errata.md` is deleted and everything it held is in
[`pre-registrations/f2_management/exit_drawdown.md`](pre-registrations/f2_management/exit_drawdown.md).
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
[study-results record](study-results/f2_management/exit_drawdown.md) stand as
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
entry and [`next-steps.md`](next-steps.md) §2.11 both said to split them there.
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
[`next-steps.md`](next-steps.md) §2.11's newest row and nothing has been changed
yet.

**Caveats.**

- The 42 dates did not run under one code version. The six retried queue-D
  dates ran after merge `3e5c2dc`, so they carry the cost columns and the
  pre-entry grid fix; the other 36 ran before it and may hold pre-entry P&L on
  about 4% of positions. A `--redo` is what levels them.
- The two hardcoded 2026-03 date tables are still partly no-ops.
  [`mech_regime_recut`](study-results/f1_selection/mech_regime_recut.md) §(b) and
  [`regime_gap_reread`](study-results/f1_selection/regime_gap_reread.md) §0 both
  list `2026-03-06`, `03-12`, `03-20`, `03-27`. The export now holds `03-20`
  with real rows and `03-12` with analysis rows only; `03-06` and `03-27` are in
  no export and were never in the selection.
- These dates sit inside `[2024-01, 2026-05]`, so they do not make the window
  independent. §2.2 and §2.6 still wait on dates after 2026-08-11.
- The honest expectation was written before the run: adding the March sessions
  moves every per-year criterion that has a 2026 cell, and may move it either
  way. Nothing has been measured yet.

**Next.** [`next-steps.md`](next-steps.md) §0 item 3 closes. The study-suite
re-run the robustness fold already owed is now owed on a book that grew again,
and it is the run that reads what these dates do.

## 2026-09-08 (sixth) — the two sleeve-sizing bodies in `account_sim` / `portfolio_delta` are folded onto `lib/hedge_criteria.sleeve_pick`; identical print

**Both simulators now pick the day's bear sleeve through
`lib/hedge_criteria.sleeve_pick`, and the fold changed no printed figure.**
Nothing ships; this is the second item of
[`next-steps.md` §2.12](next-steps.md#s2-12), and it is closed.

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
[`next-steps.md` §2.12](next-steps.md#s2-12) as far as the collector goes;
the post-fetch `hedge_structure` read is blocked by a gate failure that has
nothing to do with the fetch (below).

_Era v4 · exports installed 2026-09-08 · 598 real / 1,665 proxy / 2,677
analysis rows · `load_book(include_bs=False)` gives 1,324 records over 208
dates · option cache 43,019 contracts before the fetch (the study's
PROVENANCE line prints the exact count)._

**The rule, as registered.** The
[registration](pre-registrations/f5_hedging/hedge_structure.md) freezes the
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
  consequence and is filed under [§2.11](next-steps.md#s2-11), with the
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
`push`. Both are in [`next-steps.md` §2.11](next-steps.md#s2-11).

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
