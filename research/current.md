# Backtest tuning — current

The recent end of the log. Dated entries run below the state of play. Older
work is in [`archive/`](archive/), indexed by the [README](README.md).
Conventions for this folder: terms in [`glossary.md`](glossary.md), study-local
labels in [`arm-index.md`](arm-index.md), house style in
[`writing-guide.md`](writing-guide.md).

## State of play

Refreshed 2026-09-04. Nothing new ships. The whole suite was re-run on the
first book that carries 2026 signal dates, and no headline verdict moved. Two
studies produced a first-time candidate and both are held, because the new
dates are a correlated backfill window rather than a fresh one.

This block is the authoritative summary of where the research stands.
[`overview.md`](overview.md) and [`next-steps.md`](next-steps.md) §0 restate
parts of it. If either disagrees with this block, this block wins.

### The population

| Field | Value |
|---|---|
| Era | `v4`, the 166-date backfilled book |
| Exports | 2026-09-04 20:31 |
| Real results | 535 |
| Proxy rows | 1,303 |
| Analysis rows | 2,212 |
| Pooled study book | 1,143 rows, being 535 real plus 608 tweak |
| Signal dates | 2024-01-10 → 2026-04-16 |
| 2026 signal dates | 13, from 2026-01-06 to 2026-04-16, 79 pooled rows |

This is the first book with 2026 signal dates. Every `ex_2026_*` cut and every
"positive in every year" clause is live for the first time. The neutral-date
campaign that produced those dates, queue b, is complete and closed.

### Where the 2026 column bit

Every study still prints the verdict word it printed on the 140-date book. What
moved is underneath the verdict. The per-year clause now has a 2026 column, it
is negative in most cells, and it is the first look out of sample in time that
any rule has had on `v4`. [meanR](glossary.md#meanr) and
[CI](glossary.md#ci) are defined in the glossary.
Arm labels are study-local, so each is given with its study.

| Study | Arm or cut | What changed | Record |
|---|---|---|---|
| `next_day_move` | [ARM R](arm-index.md#next_day_move), bear-debit | lost its `**` on all three cuts | [record](study-results/f2_management/next_day_move.md) |
| `exit_from_text` | [E2](arm-index.md#exit_from_text), pooled | the pooled candidate is gone | [record](study-results/f2_management/exit_from_text.md) |
| `portfolio_delta` | [ARM B](arm-index.md#portfolio_delta) ceiling 1.50 | dropped out, so only ceiling 1.00 clears | [record](study-results/f4_deployment/portfolio_delta.md) |
| `emission_timing` | [ARM P](arm-index.md#emission_timing) sub-cuts | two of them fail | [record](study-results/f1_selection/emission_timing.md) |
| `bear_rewrap` | `long_diag` year criterion | 5/5 fell to 4/5, and in the same run its portfolio checks were `MET` for the first time | [record](study-results/f3_structure/bear_rewrap.md) |
| bear-debit `be_after` | rollback census | re-fired on 199 arming rows over 110 dates, 2026 −0.0431 | [plan](pre-registrations/f2_management/rollback_triggers.md) |

The `be_after` rule was already reverted on 2026-08-24, so its census re-firing
asks for nothing. That census has now given three answers on three runs. A
60-row floor on a backfilling book is not a decision procedure.

### Two firsts that hold rather than ship

Both sit in the correlated window, so neither promotes a rule.

| Study | Arm | Reading |
|---|---|---|
| `bear_arm` | [B2](arm-index.md#bear_arm) exit fix | criteria `MET` for the first time: `sl .50 (tighter)` Δ=+0.039, CI [+0.004, +0.071], [LOO](glossary.md#loo) min +0.035, and the bear-specificity control holds |
| `financed_spread` | [F3](arm-index.md#financed_spread) off1 | prints `RE-WRAP` at 6/7, failing only the anti-re-wrap E3 correlation, and its fixed-contracts control spans zero |

### The hedge programme

Closed on triggers, unchanged on the instrument. The drafted gap-up prohibition
in [§4](../docs/deployment-rules.md#s4) is still held, and it now rests on
`hedge_timing`'s paired-[R](glossary.md#r) arms alone.

| Study | Verdict | Detail |
|---|---|---|
| [`hedge_concentration`](study-results/f4_deployment/hedge_concentration.md) | `PRECONDITION-NULL` again | ρ +0.00 on 626 usable sessions |
| [`hedge_exposure`](study-results/f4_deployment/hedge_exposure.md) | `UNDERPOWERED` plus `MEASUREMENT-ONLY` | [ARM M](arm-index.md#hedge_exposure)'s 40.2% is identical to the dollar |
| [`hedge_timing`](study-results/f4_deployment/hedge_timing.md) | survivors still 0 | [H1-GAP](arm-index.md#hedge_timing) `NULL` → `CONTRARY`. H3-GAP stronger at −0.506, CI [−0.844, −0.157]. H4-GAP `CONTRARY` → `NULL` |
| [`calendar_hedge`](study-results/f3_structure/calendar_hedge.md) | [H3](arm-index.md#calendar_hedge) back to `NOT MET` at any size | drawdown-bound. Three consecutive exports read `NOT MET`, `DEPLOYABLE`, `NOT MET`, so this is an unstable measurement and not a verdict |

### `concurrency_correlation` is closed

X4, the era-stability criterion, was settled by hand: `NOISE` on both eras. The
`v3` companion ran on 795 rows over 118 dates, powered 8 of 13 arms, and
printed the same sentence. No arm clears
[X2 or X3](arm-index.md#concurrency_correlation) in either era, so no arm is or
can be `ADOPT`-eligible. 4 of the 8 arms powered in both eras flip sign. The
verdict is era-stable and the per-arm gains are not. The thread is closed, and
the run is in the [record](study-results/f4_deployment/concurrency_correlation.md).

### Rollback triggers

Checked at their gates, never read from silence. The
[plan](pre-registrations/f2_management/rollback_triggers.md) holds each floor.

| Trigger | Reading on this export |
|---|---|
| LVOL tef-null | `STAYS GATED` on 73 affected dates, median −0.033. The 2026-08-24 `CLEARED` did not survive two exports, so the operator's hold was right |
| BEAR_HE trail | `UNDERPOWERED` at 1 date of 25 |
| credit sl-none | 0 of 15, and unreachable by backfill because the window starts after 2026-07-13 |

### Data hazards on this export, not repaired

- Four real-priced rows sit in the local backtest scratch but not in
  `BacktestResults`, and are not proxied either. They are 2025-12-22 TSLA and
  AMD, and 2025-09-26 CRWV and HYG.
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
- **The `hedge_exposure` registration describes the wrong stratum.** Its
  plan-time observations describe the `real` stratum, not the ratified book
  (`hedge-exposure-errata.md` §RATIFICATION).

### What was pruned from this log

- Pruned 2026-08-31: everything up to 2026-08-27.
  [archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md) took
  08-14 and 08-15, being era-scoping, suite repair and `selection_order`.
  [archive/16](archive/16-first-runs-on-v3.md) took 08-19, the first runs of
  the `v3`-era studies.
  [archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md) took 08-22
  to 08-27, being vocabulary, `concurrency_correlation`, the `v4` refresh and
  `bear_deploy`.
- Pruned 2026-09-04: 2026-08-28 to 2026-09-02, into
  [archive/18](archive/18-hedge-programme-exit-basis-and-text-loop.md). That
  volume holds the hedge programme (`hedge_timing`, `hedge_exposure`,
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
mechanical triggers (0 of 9 survivors, GAP-UP CONTRARY), `hedge_exposure`
power-stopped every cell of a concentration × fraction grid, and now
`hedge_concentration` refutes concentration at its **precondition** on a powered
sample. The **instrument** has never been powered — `bear_deploy` D2 flipped
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
`study-results/f4_deployment/hedge_concentration.md` (both v4).

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
passes no subcommand) and **`calendar_hedge`, exit 1 at R2**:
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
`calendar_hedge` — R2 now `1122 / 1122 (100.0%) PASS`. The gate did its job:
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
1.39. `calendar_hedge` VERDICT byte-identical (H0 FILL NOT MET 51.0% / 28.6%;
H2 NOT EVALUABLE, (b) n=4) but **H3 DEPLOYABLE at f=1.00 → NOT MET at any
size** on both baselines (drawdown-bound; baseline max DD −10,968 →
−12,529 and −11,467 → −15,425) — three runs, three readings; H2(c) 3/3
years is carried by ONE 2026 position on 2 dates.

*f4 deployment.* `account_sim` FEASIBLE (A1–A6 MET on PRIMARY: 148 positions
/ 76 dates / $22,217 / meanR +0.348; A3 15.0%; G2–G5 PASS); the SECONDARY
full book (260 / 129 / $21,855 / +0.231) fails A1 (`2026:-0.062`) AND A3
(35.7%) — no verdict reads from it, but FEASIBLE is a two-year, dense-episode
claim (episodes end 2025-09-26). Compounding NOT FEASIBLE, A3 25.7%,
byte-identical. `bear_deploy` D1–D4 NOT MET; D5 post-hoc gates 8 → 2; D4
`|delta| low first` +0.084 [−0.028, +0.197], adopted 0. `hedge_timing`
survivors 0; H1-GAP NULL → CONTRARY (−0.245 [−0.458, −0.026]), H3-GAP −0.506
[−0.844, −0.157], H4-GAP CONTRARY → NULL (`cuts_ok` fails), H4-CHOP and
H4-DECLINE UNSTABLE → NULL; streak N=4 n_dates=4 / N=5 n_dates=2
UNDERPOWERED. `portfolio_delta` CANDIDATE-FOR-INDEPENDENT-WINDOW for **B
ceiling 1.00 only** (+0.1081 [+0.0131, +0.2205]); B 1.50 `FAILS c1` on
primary ([−0.0120, +0.1527]) and `FAILS c4` on secondary (2026 −0.0878).
`hedge_concentration` PRECONDITION-NULL, contrast $−173.65 [$−1,205.66,
$893.81], ρ +0.0000 [−0.2198, +0.2231], terciles [216, 215, 195].
`hedge_exposure` unchanged; the `real` stratum crossed its floor (reported,
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

Registered, built, run, graded and recorded the same day. It is the first study
in the repo to judge an exit rule on the **account's mark-to-market curve**
(`lib/mtm_curve.py`) rather than on per-row R, and the first to choose an exit
threshold **out of sample**. Nothing ships from it under any outcome, by
construction.

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
  short-strike breach); `bear_giveback` had located the give-back pattern in the
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
re-registering that formula under another anchor; this study is not it, and one
of its arms walked into it anyway (below).

**Population.** Era v4, the 166-date book, exports of 2026-09-04 (535 real /
1,303 proxy / 2,212 analysis; pooled study book 1,143 rows, real 535 + tweak
608, bs 0; 2024-01-10 → 2026-04-16). Two cuts in ONE report:

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
  everywhere too — and one cell there is a complete no-op rather than a thin
  one: `exit_drawdown ARM P/half` changes `0 rows / 0 dates` on v3's `all` cut
  (`ARM P/half              48         0          0`), so v3 says nothing about
  partial scale-out at all. Everything on v3 is UNDERPOWERED; it neither
  corroborates nor contradicts v4, and clause 5 reads VACUOUS on every powered
  v4 cell for exactly that reason.

**The design.** `walk_forward_splits(dates, block=15, embargo_days=120,
min_train_dates=40)` — purged, expanding, the embargo set EQUAL to the path cap
so no training label can still be open when a block's test dates start. Two
stages, both registered before any number was seen: (1) keep every configuration
whose TRAIN mean R is within 0.02 of the best; (2) among the survivors,
`simulate()` on the TRAIN day-lists only and take the SMALLEST **train** MTM max
drawdown. The blocks' TEST books are then stitched into one OOS book and the
curve is marked through `mtm_curve`. Gates all pass on both cuts: **G-COV**
(every census printed before any conditional number), **G-FORK** (with its own
rule disabled every overlay reproduces `account_sim.replay_sized` field for
field — `2286/2286 exact`; `lib/harness.py` is neither edited nor copied),
**G-CAL** (`positions   direct 84   study baseline 84`, `book_signature`
identical, and `account_sim`'s own `G2: PASS` / `G3: PASS  (0 violations)` /
`G4: PASS` / `G5: PASS` / `GATES: ALL PASS` run **in-process** and lifted
verbatim), **G1** (every auxiliary series shifted one session forward: PRIMARY
`4164` comparisons, `2119` firing sessions changed, **0 moved earlier**; `all`
`7444 / 3858 / 0`), **G-MTM** (785 PRIMARY / 1,514 `all` positions reconcile to
the frozen harness at $0.01 per contract), and **G0**, the power floor, which
runs first and blocks everything.

**PRIMARY: every cell fails G0 before any drawdown or ΔR clause is evaluated.**
Floor, registered before any count was known: **< 25 affected DATES or < 60
affected ROWS is UNDERPOWERED** — census printed, nothing concluded, no re-run
on these dates. Baseline book `84 positions / 40 dates   max DD $-5,466
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

`tally: {'UNDERPOWERED': 7, 'SECONDARY-UNDERPOWERED': 1}`. G0 runs first and
blocks every criterion, so **no PRIMARY cell has a drawdown or ΔR figure of its
own anywhere in the report** — the census is the whole output, which is what
"nothing concluded" means here and why no PRIMARY arm-versus-shipped dollar
figure can be quoted from this run. Not one cell is close: the best-populated, `exit_drawdown ARM O/vol`, reaches 35 rows against a
60-row floor, and `exit_drawdown ARM W/prod` — the shipped grid point itself —
changes **0 rows / 0 dates**, which is what makes the arm-level token
unreadable. The floor counts the `changed` column ONLY; `arm-only`/`base-only`
are reserve-release knock-ons (an earlier exit freed a reserve and admitted a
later position) and are printed as a DISCLOSED, NON-GATING breakdown rather than
counted towards power, which would have inflated it in the permissive direction.
`exit_drawdown ARM D`'s counts are its own registered SIZING definition of
"affected" (positions ENTERED at the halved budget, and the dates one was),
re-derived from the book and reconciled against `simulate()`'s own
`throttle_dates`. One thinness is STRUCTURAL rather than date-driven and is
worth naming: on PRIMARY `exit_drawdown ARM P` could split only **13 of the 77
ledger positions** — `EXCLUDED: credit 13   n = 1 (cannot be halved) 51` — so at
this $500 risk budget a scale-out arm is mostly untestable by construction, not
merely underpowered on these dates (`all`: 21 split of 155, 102 excluded at
n = 1).

**The two powered cells, both on `all`, both negative.** Baseline there is
`162 positions / 76 dates   max DD $-14,238 (-57.0% of capital)   Ulcer 19.452%
  TUW 92.6%`.

- **`exit_drawdown ARM O/vol` — the volume-climax exit. VERDICT: NULL.**
  `max DD   shipped $   -14,238   arm $    -7,194   (-57.0% / -28.8% of
  capital)`, i.e. `$+7,045 = +49.5% of the shipped drawdown` — and it fails
  three ways. (1) `block-bootstrap CI95 [-268, +13,843] (n=2000, chronological
  moving block)   FAIL` — the interval contains zero. (2) `paired DeltaR by date
  -0.054   CI95 [-0.130, +0.017]   lower bound > -0.02   FAIL` — it buys the
  drawdown cut with return. (7) `CONT: 55/77 early exits (71%) followed by a
  post-exit max > realized+0.30 R   (strict any-recovery share 92%, DISCLOSED,
  not the gate)   FAIL`. Clauses 3 (3/3 years agree), 4 (real / tweak same sign)
  and 5 (VACUOUS) pass and do not save it. **Name it what it is: this is the
  reactive null — Attempts 1/2/10 and `staged_exit` — measured at ACCOUNT level
  for the first time.** Every earlier refutation was a per-row R estimand; this
  one halves the account's marked drawdown on its face and *still* fails, on the
  same mechanism (selling continuations) and at the same rate band the trails
  failed on. The account curve does not rehabilitate a reactive exit. Thread
  closed for these dates.
- **`exit_drawdown ARM D/throttle` — the drawdown throttle. VERDICT:
  SECONDARY-NULL.** `max DD   shipped $   -14,238   arm $   -11,467   (-57.0% /
  -45.9% of capital)`, `$+2,771 = +19.5% of the shipped drawdown`, and again
  (1) `CI95 [-2,257, +6,644]   FAIL`, (2) `paired DeltaR by date -0.031   CI95
  [-0.069, -0.000]   lower bound > -0.02   FAIL`, and (4)
  `pricing tiers: real $-379 (n=68)  tweak $+2,616 (n=107)   FAIL` — **the real
  rows got WORSE and only the tweak rows improved**, which is the single most
  disqualifying shape a sizing rule can have. Clause 3 passes 2/3 on a first
  half worth `$+4`, which is noise wearing a PASS — and the 2/3 is itself a
  SILENT NO-OP disclosed only in the printed line: `years: 2024 n/a (eval dates
  13, aff 0)`, i.e. the throttle never fired on any 2024 evaluated date, so the
  year cut is signless there and the clause clears on the two years that HAVE a
  sign. (Clause 3's registered signless rule is written for the HALVES, where a
  signless half fails; the `>= 2 of the 3 years` half of the clause has no such
  rule, which is why a year that never fired passes silently.) `exit_drawdown
  ARM D` has no clause 7 by
  registration (a sizing rule moves no exit, so its continuation rate is the
  baseline's by construction). It could never have shipped from f2 anyway; the
  most it could ever have done is queue an f4 registration, and it does not.
- **`exit_drawdown ARM W`'s arm-level token is UNDERPOWERED and `PROD-ROBUST` is
  NOT claimed** — `too few dates to say whether PROD survived`. Recorded as the
  report prints it (see the disagreement log).

**The honest read on "robustness": the in-family best is not stable across
blocks.** This is the finding that outlives the tokens. On `all`'s 7 blocks the
walk-forward re-picks a *different* winner as the train window grows:
`exit_drawdown ARM W/wf` `pt 0.90 / sl off / tef off` for blocks 0–2 → `pt 1.10
/ sl off / tef off` → `pt 1.10 / sl off / tef 0.75`
(`{'pt 0.90 / sl off / tef off': 3, 'pt 1.10 / sl off / tef off': 2,
'pt 1.10 / sl off / tef 0.75': 2}`); `exit_drawdown ARM U/a` and `U/b`
`k 3.0` → `k 1.5` (`{'k 3.0': 3, 'k 1.5': 4}`); `exit_drawdown ARM O/oi`
`X 0.40` → `X 0.25` (`{'X 0.40': 3, 'X 0.25': 4}`); `exit_drawdown ARM D`
`d 0.10` → `d 0.05` (`{'d 0.10': 3, 'd 0.05': 4}`). Only `O/vol` (no threshold
to pick) and `W/prod` (a one-point grid) are stable, and on PRIMARY's 3 blocks
the drift is not visible at all — three blocks is not enough window to see it.
A knob whose best value moves with the training window is not a knob with a
value; it is a knob being fitted.

The **in-sample DISCLOSURE gap** measures what that fitting is worth, and it is
the size of the tuning bias every earlier in-sample exit read in this repo
carried. On PRIMARY the best full-window configuration reaches max DD $−4,127
(`exit_drawdown ARM O/oi`, `X 0.25`) .. $−5,275 (`ARM U`, `k 1.5`) against a
shipped $−5,466; on `all`, $−8,118 (`exit_drawdown ARM U`, `k 1.5`) .. $−13,167
(`exit_drawdown ARM O/oi`)
against $−14,238. Every one of those looks better than the honest out-of-sample
book, and none of them is a result — the report prints them under
`NO VERDICT IS READ FROM ANYTHING BELOW` precisely so the gap is visible rather
than inferred. `exit_drawdown ARM D`'s own collapse is disclosed the same way:
`Cfg.dd_throttle` is ONE value for a whole simulation, so the per-block
selection has to collapse before the stitched book runs, and it collapses to the
EARLIEST block's choice (`d 0.10`) — the only collapse that uses no information
after its own TRAIN window. A modal collapse would have replayed block 0's TEST
dates under a `d` fitted on train sets containing them. Both grid values'
stitched books are printed beside it (`d 0.05` $−11,177 / `d 0.10` $−11,467 on
`all`; identical $−5,466 on PRIMARY) so the reader can see what the collapse
cost.

**Disagreement log (two-analyst grading, `study_review exit_drawdown`).** The
graded round: **A and B agree on every row, and the validator found no
violations** — every quoted figure (G0's per-cell counts, the `25 dates / 60
rows` floor, G-FORK's `2286/2286`, G-CAL's `direct 84 / study baseline 84` and
its G2–G5 lines, G-MTM's `785 positions … $0.01`, G1's `4166 / 2119 / 0`,
G-COV's census lines, and the eight PRIMARY cells' affected-date list
`16, 0, 14, 16, 9, 28, 6, 8`) reproduces character-for-character on both sides.
Both correctly refused to import any `all`-cut number into a verdict cell, which
the validator flagged as the easiest place either analyst could have smuggled
one in. **The graded artifact is the run at sha `e1af7f8`**, so its G1 total is
quoted here as the grading saw it; the RECORDED run at `efd9b76` (same verdicts,
same cells) prints `4164 / 2119 / 0` on PRIMARY, because pinning
`SHIPPED_BE_AFTER` moved two rows across ARM O's ≥20%-blank boundary — see the
`be_after` trap below.

- **One coverage gap, not a violation.** Analyst B's table stops after clause 7
  and never grades the report's separate `ARM W arm-level token` line; A grades
  it `NOT EVALUABLE`. B took no position, so it cannot be adjudicated from the
  source. **Main-session decision: record the token as the report prints it —
  `ARM W arm-level token: UNDERPOWERED`, `PROD-ROBUST is NOT claimed` — and note
  that analyst A read it NOT EVALUABLE.** The two are not in conflict: the
  report's own token is the record, and A's grade says a reader could not
  independently evaluate it, which on `W/prod` changing 0 rows is correct.
- **The EARLIER round is where the grading did its work.** It reopened the
  **MODULE** — a grading defect reopens the module, never the registration — on
  three REPORTING defects, all fixed and the study re-run: (a) **G-COV
  ordering** — `exit_drawdown ARM P`'s split census printed BELOW the G0 cell
  table that already carried that arm's affected counts, against the
  registration's unqualified "a conditional figure printed above its coverage
  line is a reporting defect"; `exit_drawdown ARM P`'s and `ARM D`'s censuses now
  print in G-COV with `ARM U`'s and `ARM O`'s, above every cell table. (b) **`run_gates` was
  asserted, not carried** — G-CAL claimed `account_sim`'s G2–G5 pass but
  delegated them to a separate invocation outside the process and printed no
  result, and the two analysts split exactly there (one graded G-CAL MET on the
  narrower printed claim, one declined to grade it). They are now called
  in-process and their PASS/FAIL lines printed inside this report. (c) **one
  invocation now carries BOTH cuts** — the PRIMARY headline and the disclosed
  `all` cut in one report, which is what "run as a disclosed secondary cut and
  printed beside it" always said. Verdicts did not move.
- **The fourth wording correction** (2026-09-05, build, fourth) records the two
  repairs that turned on readings the registration left ambiguous: **(h)**
  G-CAL's parenthetical named `account_sim --selftest-gates`, which is the
  OPPOSITE of the check (below); **(i)** clause 5's referent is the SECONDARY
  era's PRIMARY cell, **never its `all` cut** — `all` carries no verdict, so an
  `all` cell is not verdict-carrying and cannot contradict one. The sidecar now
  records its POPULATION beside its era, only the PRIMARY cut writes one, and a
  sidecar naming any other population (or none, as the pre-correction files do)
  is REFUSED with clause 5 printing VACUOUS and the reason. The no-OOS path also
  now records its cells before returning, so v3's all-UNDERPOWERED cell set is
  the honest referent instead of no file at all.

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
  not a study argument: put it BEFORE the `--`
  (`run exit_drawdown --era v3`). After the `--` it reaches the study module,
  which does not parse it, and the run silently proceeds on the CURRENT era —
  producing a "v3" report that is v4.
- **The v3 sidecar must be stamped with its population.** Fixed under correction
  (i) above; before it, a v3 `all` run's sidecar would have been read as v4
  PRIMARY's clause-5 referent, crossing two CUTS exactly the way a stale
  filename crosses two ERAS.
- **`fetch_underlying_ohlc.py --skip-existing` REWROTE `rescaled_tickers.txt`
  and dropped six attestations.** The file was rewritten in full by a run that
  only fetched 68 of 145 tickers, so AVGO, CVNA, MSTR, NFLX, SMCI and XLE — all
  still on a rescaled basis, their CSVs untouched — vanished from it. Absence
  read as "not rescaled". **Fixed today**: `write_rescaled()` now MERGES (a run
  attests only the tickers it actually split-checked; every other prior line is
  kept verbatim, and an empty run writes nothing), and a new standalone offline
  `--recheck-rescaled` re-derives the flag for every cached ticker from disk and
  is the one path allowed a full rewrite. **13 tickers are flagged now**,
  including **NVDA (0.9000 over 216 days — the 10:1 split)** and **GE (0.2000
  over 31 days — the spinoff step)**, neither of which was in the file before.
  This CHANGES WHAT `volume_features` AND EVERY OTHER OHLC CONSUMER WITHHOLD
  from here on: absolute dollars and cross-series comparisons on a flagged
  ticker are invalid (ratios are fine — a constant factor cancels). The counts,
  since three different ones are in play: **11** attested before today's partial
  run, **5** left after it rewrote the file, **13** after the offline rebuild —
  so two tickers are newly flagged versus yesterday and eight versus the file the
  partial run left standing.
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
  `exit_mechanism_study`'s stale
  `CREDIT_PROD` (2026-08-24). Fixed the same day: `SHIPPED_BE_AFTER` is pinned to
  the config (`None` when the block is disabled) and test-pinned, and the study
  was re-run and re-recorded at `efd9b76`, whose basis line now reads
  `base -> BEAR_HE (the bear-debit be_after block is DISABLED in
  config/backtest.yml, so no breakeven stop is merged)`.
  **The pin is not figure-neutral OUTSIDE the deployed book**, and that is worth
  stating rather than discovering: `be_after` did move shipped `days_held`
  somewhere OUTSIDE the deployed book (whose positions, max DD, Ulcer and TUW are
  identical across the two runs), so between `e1af7f8` and `efd9b76` ARM O's
  hold-window census shifts — `>= 20% blank` 16 → 17 on the PRIMARY population
  and 8 → 9 on the OOS-evaluated rows, `USABLE by ARM O` 421 → 420 and
  216 → 215, and G1's PRIMARY comparison total `4166` → `4164`. Nothing that
  carries a verdict changed.
  **Closed the same evening:** `account_sim` was re-run at the committed sha
  `d69a802` (its last two `be_after-0.50` strings — the G2 prose and the
  `replay_sized` docstring — retired in that commit) and re-recorded; the PRIMARY
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
wait on. Until then: **on these dates the exit question is closed for all five
arms.** UNDERPOWERED publishes its census and is **not re-run on these dates**;
the grid is not re-cut, no arm is re-registered under a different anchor, and
the two `all` NULLs are recorded as NULLs and not read as findings on a cut that
carries no verdict.

Records: `study-results/f2_management/exit_drawdown.md` — the GRADED run is v4 at
sha `e1af7f8`, and **the RECORDED run this entry is read against is the same run
re-run at `efd9b76`**, after the `SHIPPED_BE_AFTER` pin (identical verdicts and
cells; the pin's only effect is the basis line and ARM O's hold-window census,
above) — plus the v4/v3 runs at `e19d3b4`;
`pre-registrations/f2_management/exit_drawdown.md`
(four dated wording corrections), `study_output/exit_drawdown-census-2026-09-05.txt`.
The v3 SECONDARY run was likewise re-run at `efd9b76`
(`study_output/exit_drawdown-v3-2026-09-05.txt`) and is recorded at that sha
beside the v4 section. Recording trap fixed the same evening (`d69a802`):
`scripts/study_map/summary.py` quoted the LAST banner containing `VERDICT`, and
this report's last banner is `DISCLOSURE, in-sample — NO VERDICT IS READ FROM
ANYTHING BELOW` (the disclosed `all` cut prints after the verdict summary), so
two sections had recorded in-sample numbers as the study's answer; a negated
title is now skipped, the two mis-recorded (uncommitted) sections were dropped
and re-recorded, and the committed record quotes `VERDICT SUMMARY`.

## 2026-09-05 (later) — `overview.md` and `glossary.md` rewritten for a reader who has lost the thread; the long-dated blind spot is scoped DEBIT-ONLY

Nothing ships and no number moved. One queue item narrowed: the long-dated
blind spot ([`next-steps.md`](next-steps.md) [§2.7](next-steps.md#s2-7)) is now
recorded as a **debit-side** gap only. The operator does not hold credit
positions at a `horizon` of 180 or 720 days, so the parked credit exit knobs in
the same bullet do not wait on long-dated price history. Everything else in
this entry is presentation.

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
The verdicts are unchanged and
the **record is now [`study-map.md`](study-map.md#management)**, whose two rows
were rewritten to carry the question, the verdict, why the study cannot run,
and the [archive/02](archive/02-credit-debit-split-attempts-8-12.md) trail.
[`next-steps.md`](next-steps.md) §0c(B) rewritten to match.
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
