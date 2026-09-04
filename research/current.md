# Backtest tuning — current

Most recent entries. Older work is in [`archive/`](archive/); see the
[README](README.md) for the section index. Pruned 2026-08-31: everything up to
2026-08-27 moved to [archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md)
(08-14/15 — era-scoping, suite repair, `selection_order`), [archive/16](archive/16-first-runs-on-v3.md)
(08-19 — first runs of the v3-era studies) and [archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md)
(08-22 → 08-27 — vocabulary, `concurrency_correlation`, the v4 refresh, `bear_deploy`).
Pruned 2026-09-04: 2026-08-28 → 2026-09-02 moved to
[archive/18](archive/18-hedge-programme-exit-basis-and-text-loop.md) (the hedge
programme — `hedge_timing`, `hedge_exposure`, `hedge_concentration` — the
`exit_basis` re-measure and audit, and the text ↔ backtest loop).

**State of play (2026-09-04).** Era v4, on the **166-date backfilled book** —
exports of **2026-09-04 20:31** (535 real / 1,303 proxy / 2,212 analysis rows;
pooled study book 1,143 rows, real 535 + tweak 608; signal dates 2024-01-10 →
2026-04-16). **This is the first book with 2026 signal dates** (13 of them,
2026-01-06 → 2026-04-16, 79 pooled rows), so every `ex_2026_*` cut and
"positive in every year" clause is live for the first time; the neutral-date
campaign that produced them (queue b) is COMPLETE and closed. Where things
stand after the full-suite re-run on it (entry below):

- **No headline verdict moved.** Every study prints the verdict word it
  printed on the 140-date book; what moved is underneath — the per-year
  clause now has a 2026 column and it is negative in most cells, which is the
  first out-of-sample-in-time look any rule has had on v4. It killed
  `next_day_move` ARM R's bear-debit `**` on all three cuts, `exit_from_text`
  E2's pooled candidate, `portfolio_delta` B ceiling 1.50 (only B 1.00 clears),
  two `emission_timing` ARM P sub-cuts, `bear_rewrap` long_diag's year
  criterion (5/5 → 4/5, in the same run its portfolio checks were MET for the
  first time), and it re-FIRED the bear-debit `be_after` rollback census
  (199 arming rows / 110 dates; 2026 −0.0431) — already reverted since 08-24,
  nothing to do. Three censuses, three answers: a 60-row floor on a
  backfilling book is not a decision procedure.
- **Two firsts that HOLD rather than ship** (correlated window): `bear_arm`
  B2's exit-fix criteria are MET (`sl .50 (tighter)` Δ=+0.039 CI[+0.004,+0.071],
  LOO min +0.035, bear-specificity control holds); `financed_spread` F3 off1
  prints **RE-WRAP** (6/7, failing only the anti-re-wrap E3 correlation, and
  its fixed-contracts control spans zero).
- **The hedge programme is closed on triggers and unchanged on the
  instrument.** `hedge_concentration` PRECONDITION-NULL again (ρ +0.00 on
  626 usable sessions); `hedge_exposure` UNDERPOWERED + MEASUREMENT-ONLY with
  ARM M's 40.2% identical to the dollar; `hedge_timing` survivors still 0 but
  the arms moved — H1-GAP NULL → CONTRARY, H3-GAP stronger (−0.506
  [−0.844, −0.157]), H4-GAP CONTRARY → NULL — so the drafted-and-HELD §4
  gap-up prohibition now rests on the paired-R arms alone. `calendar_hedge`
  H3 flipped back to NOT MET at any size (drawdown-bound); it has now read
  NOT MET / DEPLOYABLE / NOT MET on three consecutive exports and is an
  unstable measurement, not a verdict.
- **`concurrency_correlation` X4 settled by hand: NOISE on both eras.** The v3
  companion ran (795 rows / 118 dates, 8 of 13 arms powered, NOISE, same
  sentence). No arm clears X2/X3 in either era, so no arm is or can be
  ADOPT-eligible; 4 of the 8 arms powered in both eras flip sign. The verdict
  is era-stable, the per-arm gains are not. Thread closed.
- **Rollback triggers:** LVOL tef-null STAYS GATED on 73 affected dates
  (median −0.033) — the 08-24 CLEARED did not survive two exports and the
  operator's hold was right; BEAR_HE trail 1/25 UNDERPOWERED; credit sl-none
  0/15 and unreachable by backfill (window starts after 2026-07-13).
- **Data hazards found on this export, not repaired:** four real-priced rows
  present in the local backtest scratch are absent from `BacktestResults`
  (2025-12-22 TSLA/AMD, 2025-09-26 CRWV/HYG) and not proxied either;
  2025-12-26 produced no analysis rows; `text_features` ARM B label coverage
  fell to 89.3% because the label cache does not cover the new rows. Details
  in the entry below and `next-steps.md` §0.

**Open queue** (detail in [`next-steps.md`](next-steps.md)): nothing new is
registered. The v4 composition bridge and the rollback triggers wait on
GENUINELY new dates — the live 2026-08-11 → 2026-09-01 analysis dates, which
have no backtest rows until their options expire; `prompt_eval` §2.9 is a
stability item; `operator_read` (§2.5) waits on the journal. Rollback
triggers are checked at gates, never read from silence.

**Standing hazards carried forward** (each has its full entry in an archive):
the `exit_basis` export column is unlabelled and scrambled on **v3 and
earlier** and those exports are frozen (archive/15) — but it is CLEAN on v4
(re-measured 2026-09-02: 485/485 labelled and internally consistent), so the
rule is now era-scoped rather than absolute, and `BacktestProxy` carries it
only for rows written after the 2026-09-02 writer fix; studies are ERA-scoped and the bare export name is not a
population (archive/15, `lib/era.py`); ARM labels are study-local — cite
`emission_timing ARM P`, never a bare `ARM P` (archive/17, `arm-index.md`);
`study_review --dry-run` overwrites the review/digest artifacts (archive/17);
the `hedge_exposure` registration's plan-time observations describe the `real`
stratum, not the ratified book (`hedge-exposure-errata.md` §RATIFICATION).

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
