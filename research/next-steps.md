# Next steps — session handoff

Written 2026-08-31, so a fresh session can pick up without re-deriving state.
Read this plus the **State of play (2026-08-31)** block at the top of
[`current.md`](current.md) — that block is the authoritative summary; this file
is the queue. Evidence trails live in [`current.md`](current.md),
[`archive/`](archive/) and [`deployment-evidence.md`](deployment-evidence.md).

## 0. Repo state — READ FIRST

- **Era `v4` is current.** The book is the **140-date backfilled** one; the
  studies run on exports of **2026-08-27 20:34** (485 real results / 1,111
  proxy / 1,893 analysis rows; signal dates 2024-01-10 → 2025-11-04). There are
  still **zero 2026 signal dates**, so every `ex_2026_*` window cut and
  "positive in every year" clause is a silent no-op
  ([archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md) §2026-08-27).
- **Tests green as last recorded: 2,560 passed** (2026-08-31, end of the
  `hedge_exposure` thread — [`current.md`](current.md)). The last full study-suite
  re-run was **2026-08-27**: 25 studies recorded for era v4, only the 2 retired
  studies lack reports; the HYG boundary-tie that had blocked the four debit
  exit studies is fixed
  ([archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md) §2026-08-27 fix 2).
- **The live thread is the hedge programme.** `hedge_exposure` is run, graded and
  ratified, and it ships nothing; its follow-up `hedge_concentration` was
  registered, built and RUN on 2026-08-31 — **PRECONDITION-NULL, a powered
  null** — and awaits `study_review` grading before §2.1 closes. See §1 and §2.1.
- **Where the old §0/§0b/§1 went.** The 2026-08-14 study-suite repair, era-scoping
  and `selection_order` story is now
  [archive/15](archive/15-era-scoping-suite-repair-and-selection-order.md); the
  2026-08-13 decisions (bear_put demotion → card veto §1.4, OIConfirm out of the
  Score, −25 IVspr veto retired, codex retired) are in
  [archive/14](archive/14-volume-signal-demotion-and-audit.md) and archive/15.
  Do not re-derive either here.

## 0c. Study suite — was 6 FAILING, **ALL RESOLVED 2026-08-14**; `run --all` exits 0

*Historical diagnosis from 2026-08-14, resolved that day. Kept verbatim because
code and tests cite it as "next-steps.md §0c(A)" / "§0c(B)"
(`scripts/study_map/catalog.py`, `scripts/backtest_study/f2_management/{combined,underlying}_exit_study.py`,
`tests/test_backtest_study_run.py`, `tests/test_exit_replay_gate.py`,
`tests/test_study_map.py`). Nothing below is a live task.*

The six failures were **three unrelated causes**. All three are fixed; the full
write-up is in [`current.md`](current.md) §2026-08-14 (two entries: the gate
correction and the runner/retirement work). Kept here in short form because the
*reasoning* behind two of the choices should not be re-derived.

**(A) The DEBIT_PROD exact-replay gate — FIXED by classifying, not by asserting.**
`bear_position_study`, `exit_switch_mech_study`, `exit_switch_structure_study`
all stopped on a gate demanding every real debit row replay bit-exactly under
`DEBIT_PROD`. Production stopped having that property on 2026-07-22, when
`31cb935` shipped `regime_exit.cells.BEAR_HE` (trail .50/.50): it resolves a
per-row effective config (`simulate.py:150-165`) while the frozen harness takes
flat call args and never sees the signal date. No export could ever satisfy it.

`harness_gate()` in `exit_switch_mech_study.py` is now the **single**
implementation, called by all three studies. It classifies each row **exact /
near-rounding-tie / superseded-basis / HARD** and stops only on HARD.
Superseded-basis is identified mechanically, not by date heuristic:
`unreachable_reasons(prod)` computes the exit reasons `replay()` cannot emit
under a profile (for `DEBIT_PROD`: `trailing_stop`, `underlying_stop`,
`be_stop`), so a stored row carrying one of those was by construction written
under a different config. Measured: **289 exact / 0 near / 12 superseded / 0
HARD**, calibrated totals matching to the cent, the whole −$5,145.00 isolated and
reported. The 12 rows are **kept and re-replayed** — they are precisely the rows
where the shipped rule changed the outcome, so dropping them would bias the cell
under test. Proxy admission is unchanged (exact-only): a pre-registered
POPULATION choice, not part of the gate.

`bear_position_study.py`'s `R` is now `replay(t, **DEBIT_PROD)["pnl_pct"]`
instead of the stored `realized_pnl_pct`. Contamination measured on the same
book both ways: **12 rows, −$5,145.06**; bear_put mean R −0.1016 → −0.1069,
`long_put` −0.570 → −0.627 (n=7). It made the bear book look *better* than it
was, so the correction **strengthens** the demote reading — re-run verdict is
still **DEMOTE TO VETO** and card veto §1.4 stands. (A naive row-level diff
reports "95.7% of rows changed" — that is 4-decimal CSV round-trip noise; at a
`NEAR_MISS_TOL` threshold it is 12 rows.) 15 tests in
`tests/test_exit_replay_gate.py` pin all of this, including that a **true HARD
row still exits 1**.

⚠️ **`exit_basis` — the hazard is now ERA-SCOPED, and the operator action below
is DONE (2026-09-02).** This section originally recommended identifying
superseded rows by that column, then banned it outright. The accurate rule:

- **v3 and earlier — permanently unreadable.** The writer
  (`simulate.py::_exit_basis`) was always correct, but the Sheets tab header was
  never given the name, so values reached the export as an **unlabelled 47th
  column**, **scrambled relative to their rows**. Measured 2026-08-14: of 67
  `BacktestResults` rows created after the trail shipped — every one of which
  should carry a basis — **65 are blank**, while **55 `BEAR_HE` and 11 `CREDIT`
  labels sit on rows created *before* the column existed**; **7 of 13
  `CREDIT`-tagged rows have a positive entry price**, which `_exit_basis` cannot
  produce; and no `BEAR_HE`-tagged row has a `trailing_stop` exit. Those exports
  are frozen, so this never gets repaired.
- **v4 — clean.** The 2026-08-11 version bump recreated the tabs empty and
  `append_rows` wrote a full header. Re-measured 2026-09-02 on the 2026-08-27
  export: header matches `core._KEY_ORDER` **47/47**, **485/485 rows labelled**
  (`PROD` 260 / `CREDIT` 113 / `BEAR_DEBIT` 95 / `BEAR_HE` 17), **no** `CREDIT`
  row on a positive entry price, and the `BEAR_HE` / `BEAR_DEBIT` rows **do**
  carry the `trailing_stop` / `be_stop` exits that define those cells. A study
  may stratify a v4 book by exit profile — that is what the column is for.
- **`BacktestProxy` — blank in every era, for a different reason.** Not
  corruption: `proxy.py::_evaluate` copied only `_RESULT_COLS` into the row
  while `exit_basis` sits in `_BASIS_COLS`, so no method's value ever reached
  the sheet (all 1,111 rows blank, including 461 `underlying_trend` rows that
  `proxy.py` explicitly sets to `"NONE"`). **Fixed 2026-09-02**; the tab carries
  a basis only for rows written by a proxy run after that, so re-run before
  reading it.
- **Still classify mechanically to ask whether a row REPLAYS.**
  `lib/replay_basis.py` deliberately does not read the column, and that does not
  change: the column names the profile a row was WRITTEN under, which is a
  different question, and the classifier must work on v3 too.

- [x] **Operator action — DONE 2026-09-02, and no Sheets write was needed.**
      `align_tab_headers.py` now resolves a target schema PER TAB (`SCHEMAS` /
      `schema_for`): analysis tabs → `config.ROW_COLUMNS`, `BacktestResults` →
      `core._KEY_ORDER`, `BacktestProxy` → `proxy._PROXY_KEY_ORDER`, with
      `vN_` renames mapping to the same schema. It targeted `ROW_COLUMNS` for
      every tab before, which is exactly how the column landed nameless. Both
      backtest tabs are in `DEFAULT_TABS`, so a bare `--dry-run` sweeps them.
      The live v4 headers already agree 47/47 and 46/46 — the check is a guard
      against the next key-order change, not a repair. The values were
      re-verified against entry-price sign (0 violations). 5 tests in
      `tests/test_align_tab_headers.py`, 3 in `tests/test_backtest_proxy.py`.
- [x] **Minor follow-up (DONE 2026-08-24):** `book.py`'s `diag["debit_calib"]`
      now tallies the four-way split (`superseded` key added; classifier shared
      via `lib/replay_basis.py`) and the three print sites show it. It used to
      count those 12 as `hard`, using the old vocabulary. Harmless there (it never gates and
      always keeps real debit rows) but misleading in the three reports that
      print it (`account_sim.py:1062`, `calendar_hedge.py:634`,
      `volume_signal.py:97`). Aligning it to the four-way split changes no
      admission decision and no study's numbers — three print sites. Its
      docstring already carries the correction.

**(B) `combined_exit_study` and `underlying_exit_study` — RETIRED.** Inputs are
deleted gitignored scratch and were never recoverable. `catalog.py`'s `Study`
gained a `retired` field (orthogonal to `state`: retirement is about whether a
study can be RUN, not what it argued) plus `retired_studies()`; `--all` skips
them with the reason printed, `run <name>` still runs one explicitly after a
notice, and the study-map page renders a `retired` pill and caveat. **Do not
repoint them at surviving files** — `results.csv` is 4 rows on 2 dates today
(Attempt 12 ran on 94 real debit + 22 credit), `results_proxy.csv` was always an
author transposition of the writer's `proxy_results.csv`, and although
`v2_results_nocreditdiff.csv` IS the genuine rename, `underlying_exit_study`'s
other input has 0 credit rows so it would emit an empty report anyway. Numbers
off a 4-row wrong-vintage book would read as a fresh confirmation. Porting
`combined_exit_study` to `book.py` stays a design decision, not a loader swap
(it imports `Trade`/`replay` from the older `exit_mechanism_study.py`, not the
frozen `harness.py`). Count rows with `csv.DictReader`, never `wc -l`.

**(C) `v4_bridge` exit 3 — now a first-class DESIGNED REFUSAL.** It was never a
defect: it is the pre-registered refusal to compare a v3 book against itself.
A study may now declare `DESIGNED_REFUSAL_EXIT_CODES = {…}` as a module constant,
read by `run.py` via `ast` (never imported, same as `discover()`); such an exit
promotes `-latest.txt`, prints under **DESIGNED REFUSALS (not failures)**, and is
excluded from the return code. `v4_bridge` declares `{2, 3}`. Other studies stop
on their own pre-registered calibration or power gates and are equally correct to
do so. `MIN_V4_DATES` was NOT lowered and `--v4-csv` was NOT pointed at a v3
export. `study_map` was taught the same two words (it was still printing
`exit 3 [failure]` and `never run`), importing `run.py`'s `_refusal_codes` and
`catalog`'s retired set rather than re-deriving either — `--check` now reads
`refused (exit 3)` and `retired`. **An undeclared non-zero exit on a
refusal-capable study still classifies as `failure`**, and that is pinned by a
test: the refusal path must never swallow a real failure.

## 1. Closed since the last handoff

One line each. None of these needs re-opening; follow the pointer if you need
the detail.

- **`trigger_entry`** (2026-09-04) — trigger-gated entry re-priced at the
  crossing session's close: **LATE-ENTRY** (N=3 −0.014, N=5 −0.026; v3 ×3);
  `exit_from_text` E2's +0.21/−0.05 gap was the day-0 move (ARM C bands
  +0.63 → −0.42). Entry-mechanics thread closed on these dates. →
  [`current.md`](current.md) 2026-09-04,
  [`study-results/f1_selection/trigger_entry.md`](study-results/f1_selection/trigger_entry.md).
- **Text thread as an edge search** (2026-09-04) — `text_features` NULL,
  `exit_from_text` E1 CONTRARY / E3 fails survival, `prompt_eval` variance floor:
  no further text study queued; §2.9 survives only as a prompt-STABILITY item.
  The operator's day-X / ±Y% / ±$Z exit formula is `staged_exit` (0/40 powered
  cells, day-5 loss cuts significantly harmful) — do not rebuild it, a
  DTE-remaining anchor included (the 75%-DTE time exit already is one). →
  [`current.md`](current.md) 2026-09-04.
- **`hedge_exposure`** (2026-08-31) — run, graded, population **`all` ratified**
  (996 rows / 145 dates). Two verdicts over two objects: the mechanism question
  is **UNDERPOWERED** (all nine τ×f cells fail G-POWER, no direction quoted) and
  ARM M is **MEASUREMENT-ONLY** (the close-bucketed curve understates this
  book's max drawdown by 40.2%). Ships nothing. →
  [`pre-registrations/f4_deployment/hedge_exposure.md`](pre-registrations/f4_deployment/hedge_exposure.md)
  §Population and basis (RATIFICATION consolidated there 2026-09-02), and
  [`current.md`](current.md) 2026-08-31.
- **`hedge_timing`** (2026-08-28) — GAP-UP came back **CONTRARY** on both money
  arms; §4 prohibition **drafted and HELD** for the operator to accept or reject.
  Chop and the broad decline NULL; the strict 4–5-day streak untestable (2 book
  dates). → [`deployment-evidence.md`](deployment-evidence.md) §Hedge-timing
  triggers.
- **`bear_deploy`** (2026-08-24) — graded; the §4 **pick line is PULLED** (pick
  is now operator discretion), the far-OTM prohibition **retained**, the sleeve
  relabelled **operator policy**. → archive/17.
- **`selection_order`** (2026-08-14) — UNDERPOWERED at G0; do not re-run on
  these dates. → archive/15.
- **`volume_signal`** (2026-08-13) — NULL; the volume column is closed, no
  version bump. → archive/14.

## 2. Open queue, in rough priority order

The numbers are **stable labels**, not a ranking — `calendar_hedge.py` cites
§2.3 and the archived backlog cites §2.4 and §2.7, so they keep their meaning.
The order below is roughly the order to pick things up.

### 2.0 `concurrency_correlation` — BUILT AND RUN 2026-09-04: **NOISE** on era v4; X4 pending the v3 companion

**Status: answered on this era, not yet on both.** The module was written and
run 2026-09-04 (era v4, exit 0). It is the study for the operator's read that
"the more that is being deployed, the less it seems to be working" — which does
NOT resolve to depth into the ranked list (within-day rank is flat on both
eras). What it measures instead is the SIZE and internal SIMILARITY of the open
book at each position's entry.

`VERDICT: NOISE` — all 11 powered arms sit inside ARM N's band. Neither the size
of the open book nor its internal similarity degrades per-position outcome, at
any ceiling on either grid. PRIMARY = 3 dense episodes / 87 dates / 218
positions; SECONDARY = the full 129-date book. `K 3 / same-underlying` and
`K 5 / same-underlying` are UNDERPOWERED (21 and 7 moved dates against the
pre-declared floor of 25) and print census only. ARM CK NOT RUN — the
registration runs the conjunction only if ARM C and ARM K each clear alone, and
neither did.

Three things the run established that were not knowable at registration, all
printed rather than assumed:

- **ARM K / same-direction IS ARM C on a different grid.** The book is long-only
  by construction (`{1: 321}`, 321 of 321 positions have same-direction count ==
  open count), so that relation carries no information ARM C does not. The run
  checks this and excludes the degenerate relation from ARM CK.
- **X7's delta control barely discriminates on this book.** 110 of 129 dates sit
  in the `[2.0,inf)` band of |net delta-notional| / capital at session open, so
  only ONE band is readable — and one readable band is the whole sample
  re-labelled, not a control. X7 cannot PASS on it, which the report says in
  those words.
- **ARM D0's descriptive shape is not flat but is not an arm either.** Mean R
  falls across the same-direction-and-sector bands (`[0,3)` +0.4533 → `[6,10)`
  −0.1256 on SECONDARY) and across raw concurrency (`[6,10)` +0.5118 →
  `[20,inf)` +0.1783). Registered as DESCRIPTIVE ONLY and it stays that way: no
  band is adopted, and the ceiling arms that would act on the shape are all
  inside the null band.

**What is left:** the **v3 companion run** for X4 (era stability), which one run
cannot do — `lib/era.py` binds one run to one era and pinning a second era's
export to dodge that is what the guard exists to prevent. The report prints the
command and CAPS every arm at CANDIDATE-PENDING-X4 until it is done:

```bash
python -m scripts.backtest_study run concurrency_correlation --era v3
```

On a NOISE verdict X4 changes nothing that ships (nothing does), so this is a
completeness item, not a blocker. Grade with `python -m scripts.study_review
concurrency_correlation` (never `--dry-run`) once the companion exists.

### 2.1 The max-drawdown hedge question — **CLOSED 2026-09-04** (`hedge_concentration` PRECONDITION-NULL, graded)

**Do not re-open this section.** Run 2026-09-04 (era v4, sha `64689d0`, exit 0),
graded the same day under the two-analyst protocol: A and B agreed on all 21
gate/clause rows, no violations, no mis-transcriptions, validator called the
pair "unusually clean". Both flagged the module's two disclosed substitutions
(G-MTM against `TARGET_POSITION`; G-POWER against episodes) rather than glossing
them — they were already in the report's twenty-item NOT PRE-REGISTERED block. A
grading defect would have reopened the MODULE; none was found.

Stage 1 cleared G-POWER-K (`[172, 172, 152]` usable sessions per tercile, floor
60 each; 3 dense episodes, floor 3 — met exactly at the floor) and returned
**PRECONDITION-NULL**: contrast `$-767.93` CI95 `[$-2,186.47, $349.09]`, ρ
`-0.1648` CI95 `[-0.4021, +0.0809]`, neither beating the circular-shift null's
5th percentile. Clauses 1/2/3/5 fail; the two that PASS are the CONTROLS, so it
is not a gross-exposure effect in disguise. Stage 2 was not entered.

Recorded in [`deployment-evidence.md`](deployment-evidence.md) §"The queued
max-drawdown question is CLOSED for concentration-gated hedging" — and, beside
it, §"The hedge trigger is dead; the hedge INSTRUMENT is unmeasured", which is
the distinction this closure rests on and must be quoted with it:

> Every mechanical rule for deciding WHEN to open the hedge has now been tested
> and none survives. WHETHER the sleeve pays has never been powered. The
> evidence contradicts hedging on a mechanical trigger and says nothing either
> way about hedging on judgment.

**Do not register a fourth trigger study.** What would move the sleeve is an
INSTRUMENT test on a mark-to-market curve (`lib/mtm_curve.py`), on dates chosen
without a rule, and it waits on dates rather than on design.

**Deferred, not dropped — the prose control.** `hedge_exposure` ARM P stays
inert (ERRATUM 2) and the corrected control — ARM C on concentration-matched
sessions carrying NO hedge-pressure signal, matched on count — is NOT in
`hedge_concentration`: the admitted book carries only 19 prose-conditioned
sessions / 17 episodes at the loosest τ, so it would be another arm that can
never bite. Register it only when the book has materially more parsed dates.

### 2.2 v4 composition bridge — RUNS now; the answer is "ladder unvalidated on v4"

**Status changed since the last handoff.** `v4_bridge` no longer refuses: it ran
on 2026-08-24 and again 2026-08-27 and prints `VERDICT: LADDER UNVALIDATED ON v4`
(`research/study-results/f1_selection/v4_bridge.md`). Four of the five
pre-registered tests shift (structure mix, plays per day, bear share, ladder tier
mix); only credit share holds.

Per the pre-registration: **keep deploying under the v3-derived rules and do NOT
re-derive the ladder on v4 rows yet.** What still waits on data is genuinely new
(non-backfill, post-2025-11-04) dates. Do not lower `MIN_V4_DATES` and do not
point `--v4-csv` at a v3 export — its exit 3 was always the designed refusal
(§0c(C)), not a defect.

### 2.3 Calendar-as-hedge — BLOCKED ON NEW DATES

Unchanged. The whole calendar/put-calendar/diagonal hedge programme terminates at
one wall: 9 worst-decile dates cannot power a worst-decile criterion under a
1/day sleeve (all 30 `calendar_hedge` ARM S cells underpowered; H2 underpowered
at n=6). Carry-forwards recorded in the log: the RANGE+C/L-VOL calendar cell
(n=15, post-hoc) and the H2 clause amendment (the power floor should suspend only
clause (b)). On the v4 book the study has not got past its own gates either
(H0 FILL NOT MET, H2 NOT EVALUABLE), so **H3 has never been evaluated at all**.

New qualification, 2026-08-31: `calendar_hedge` H3 is "`bear_deploy` D3 verbatim",
and D3's drawdown leg is read on the close-bucketed curve that `hedge_exposure`
ARM M found wanting — see [`deployment-evidence.md`](deployment-evidence.md)
§"The curve D3 was read on understates drawdown". Prospective only; no verdict
moves. Nothing to run until the book has materially more dates.

### 2.4 Bear sub-0.50 give-back — the `be_after` route is closed; the pattern is not

`bear_giveback` ran and the `be_after` grid does **not** ship. The shipped
breakeven stop (`structure_exit.enabled`) was **REVERTED 2026-08-24** when its rollback
trigger fired, so there is no live baseline for the grid to add to either. Where
the study says the pattern actually lives: in the **underlying**, not the mark —
`peak within 3d` n=18, give-back 89%, meanR −0.374 against `peak >20d` n=83,
give-back 51%, meanR +0.203 (`scripts/study_map/catalog.py`, `bear_giveback`).

Live wrinkle: on the grown 140-date book the same trigger **un-fires** (165
arming rows, per-year deltas positive → HOLD). **Nothing un-reverts without a
fresh registration** — and the lesson recorded alongside it is that a 60-row
floor on a still-backfilling book produced a trigger decision that did not
survive the next export (archive/17 §2026-08-27).

### 2.5 Live walk-forward — still the intended evidence source, no recorded movement

v3 tuning is closed and live fills are meant to be the evidence source. The
`SUBSTITUTED` match category shipped 2026-08-11. Open: Stage 1/2 fill-mapping and
the live-vs-tier feedback eval (does realized live P&L order A > B > C?). Also
worth tracking: the operator substituting a naked leg where a spread was emitted
— an untested instrument.

⚠️ No log entry since 2026-08-13 records progress here. That is silence, not
evidence of no progress — check the live-loop artifacts before re-planning it.

**2026-09-03 — the OPERATOR-READ test belongs here, and it is worth running.**
`text_features` (2026-09-02) closed the question "does the signal TEXT carry a
machine-readable edge?": NULL in every arm, both eras — do not re-run it on
these dates. But the operator reads `signal` qualitatively, with the price
movement, to decide what is worth trading — so the text's value is realised in
the operator's PICK, and only the journal can measure that. The test, to
pre-register before any code (f4, `operator_read`): among LADDER-ELIGIBLE plays
per date, TAKEN (journal `EXACT`/`STRUCTURE`/`CORE`/`SUBSTITUTED` matches) vs
NOT TAKEN, paired by date, on R and PF (`protocol.pf_paired_by_date`, never
without mean R), with the entry-session price move as the declared covariate
(`next_day_move` already showed day-0 confirmation is a confound, so the read
must be conditioned on it, not credited with it). Floor: ≥25 dates with ≥2
eligible plays and ≥1 taken — a census first; the journal may not have it yet.
A positive result is a statement about the operator's read, not about the
prompt; a null means the ladder alone is as good as the ladder plus the read.
Do NOT test this with a stripped-text `prompt_eval` candidate — that would
remove exactly what the operator reads.

### 2.6 Rollback triggers — accumulating; check at gates, never read silence as "not met"

The table is in [`deployment-evidence.md`](deployment-evidence.md) §"Open
pre-registered rollback triggers". First census + evaluations ran 2026-08-24
(`research/pre-registrations/f2_management/rollback_triggers.md`; the census now
prints on every relevant study run):

| Trigger | Census (2026-08-24) | Outcome |
|---|---|---|
| bear-debit `be_after 0.50` | 92 arming rows / 53 dates ≥ floor 60 | **FIRED → REVERTED** (un-fires on the 08-27 book; see §2.4) |
| LVOL tef-null (corrected gate) | 31 affected dates ≥ 25 | all four criteria pass — CLEARED, operator **HELD** the ship pending genuinely new dates |
| BEAR_HE trail | 1 affected date of 25 | UNDERPOWERED — the census is the result |
| credit sl-none | 0 fresh bull_put rows of 15 | UNDERPOWERED — `sl 1x` comparator now printed by every credit run |

Two stale report strings to fix before they propagate (found 2026-08-27, not yet
done): `bear_arm.py:442` still prints the census header as "shipped 2026-08-11"
with no knowledge that `structure_exit.enabled` is now `false`, and
`account_sim.py:1940` still cites "bear_deploy D4-adopted" for a pick line that
was pulled.

### 2.7 Parked / blocked long-term

- **Credit exit knobs** — unvalidated; needs a credit-heavy window (every
  historical winner is the Mar-TSLA cluster). The v4 credit book calibrates
  exactly (single-basis era, 113/113 exact as of 08-27) and the corrected
  baseline is in place, but there are no 2026 dates, so the Attempt-13 trigger
  has **0 fresh bull_put rows**. Operator kept the thread parked; census +
  `sl 1x` comparator print on every credit run.
- **Long-dated blind spot** — h ≥ 180 is unpriceable with real data and the BS
  proxy tier is OFF (`proxy.bs_fallback: false`). Blocked on real long-dated
  history; never read BS proxy rows as evidence for long-dated.
- **Per-regime exit switch** — STAYS GATED on the 140-date book
  (`exit_switch_mech_study`, `exit_switch_structure_study`, 2026-08-27).
- **`portfolio_delta` ARM B ceiling 1.50** — clears the full adoption
  conjunction on both populations but costs dollars and comes off a correlated
  window; labelled **CANDIDATE-FOR-INDEPENDENT-WINDOW**, queued, nothing ships
  (archive/17 §2026-08-27 fix).
- **`analyze_bt_queue.sh` backfill partials** — 20 dates stuck as
  permanently-skipped partials. **Five of them already have analysis rows in the
  tab**, so `RETRY_PARTIAL=1` on queue b would duplicate them and the tab has no
  dedup to catch it; the other fifteen wrote nothing and are safe to retry
  (archive/17 §2026-08-22).
- **Prompt/infra** — the `analysis_pipeline/core.py` refactor is deferred; the
  PostToolUse hook still never runs pytest. The delegation-nudge PreToolUse hook
  is advisory by design (`systemMessage` only, no `permissionDecision`).

### 2.8 Exit engine ignores per-play `invalidation` conditions — the last live item from the archived backlog

**ANSWERED 2026-09-02 by `exit_from_text` (f2), and the answer is: do not
build it.** The model's own invalidation level, evaluated as an underlying-close
stop on the frozen replay, is CONTRARY on `bull_call_spread` / `LVOL` (dR −0.045,
CI [−0.083, −0.008], every criterion true toward the negative sign) and NULL or
UNDERPOWERED elsewhere on v4; the only positive cells are v3 `bear_put_spread`
at a 1–2% buffer — a re-read item when 2026 dates reach v4, never a ship from a
secondary era. The parser hazard below was honoured (unparseable levels are
their own reported bucket, 1.1%). `invalidation_exit` stays unshipped on
evidence, not on backlog. The text below is kept as the record of the original
gap.

Carried here so archiving the backlog loses nothing. The old
`research/backlog.md` is now
[archive/00](archive/00-backtest-engine-backlog-2026-06.md); its triage closed
every item except this one.

**The gap:** the backtest exits on fixed horizons, profit targets, stops and
trails, and otherwise holds to expiry. Each analysis row carries an
`invalidation` string (e.g. *"AAPL close < 290"*, *"SMH reclaims 570"*), and
`backtest/shared/analysis_io.py` reads it — but only as a passthrough field.
Nothing parses it and no exit fires on it, so `invalidation_exit` is the one
terminal status that never ships.

**What implementing it means:** parse the condition, evaluate it against daily
underlying closes, exit at that day's spread mark, add the `invalidation_exit`
status. Two cautions, both from the archive:

- The strings are free-form model output. A parser that silently fails to match
  must record **that**, not fall through to "condition never met" — the latter
  understates exits and flatters the book.
- `scripts/backtest_study/lib/harness.py` is the **frozen** replay engine. A new
  exit reason belongs in the backtest engine, not there.

Do not quote any P&L figure from that archive: it is all on the superseded
pre-2026-07-06 entry basis, and the v1 exports store `pnl_pct` as `"1.64%"`
strings.

### 2.9 `prompt_eval` — harness built, noise floor running; a candidate needs an OPERATOR hypothesis

**Status 2026-09-04: a STABILITY item, not an edge item.** The text thread is
closed as an edge search (§1); the only candidate worth writing is the
BULL/RANGE written decision rule below, judged on label repeatability first.
It is a v5 prompt bump if adopted, and nothing in the book says it changes
P&L — do not pick it up ahead of §2.0–§2.2.


Built and committed 2026-09-03 (`01dcb97`); registration
`pre-registrations/f1_selection/prompt_eval.md`. Date sets declared by rule in
`backtests/prompt_eval/{variance,backfill}-dates.txt`. The PROD × 3 variance run
was interrupted by the account session limit and resumed into
`backtests/prompt_eval/variance-20260903/` (log beside it); when it ends, append
the noise floor to `current.md`. Then, only with a COMMITTED candidate directory
holding `analysis-framework.md`, `claude.md` and `CANDIDATE.md`:

```bash
python -m scripts.backtest_study run prompt_eval -- run --candidate <dir> \
  --dates backtests/prompt_eval/backfill-dates.txt \
  --run-dir backtests/prompt_eval/backfill-$(date +%Y%m%d) \
  --variance-json backtests/prompt_eval/variance-20260903/variance.json   # ~80 opus calls
python -m scripts.backtest_study run prompt_eval -- accumulate --candidate <dir> \
  --date YYYY-MM-DD --run-dir backtests/prompt_eval/live                  # each new live date
```

**Resuming the variance run after a sleep/kill (2026-09-03).** The run is a
detached `nohup` process; a laptop sleep or reboot ends it. Nothing scraped is
lost (every contract history is in the shared cache) and every finished
analysis is skipped on relaunch. To pick it up:

```bash
pgrep -f "prompt_eval variance" || echo ENDED          # is it alive?
ls backtests/prompt_eval/variance-*/variance.json        # done if this exists
# if ENDED and no variance.json: seed a FRESH run dir with the finished analyses
src=backtests/prompt_eval/variance-20260903; dst=backtests/prompt_eval/variance-$(date +%Y%m%d)-b
mkdir -p $dst && for r in prod-r1 prod-r2 prod-r3; do
  [ -d $src/$r/analysis ] && mkdir -p $dst/$r && cp -R $src/$r/analysis $dst/$r/; done
nohup python -m scripts.backtest_study run prompt_eval -- variance \
  --dates backtests/prompt_eval/variance-dates.txt --repeats 3 --run-dir $dst > $dst.log 2>&1 &
```

A repeat whose five `<date>-rows.csv` files exist costs no model call; only
its pricing is redone (fast on a warm cache). The proxy step is slow because
Barchart throttles the scrape (~80 contracts/hour); its log is written only
when the step ends. When `variance.json` lands, append the noise floor (mean-R
spread and emission-count spread across repeats, per date) to `current.md`
under the 2026-09-02 text-loop entry and commit.

Fresh `--run-dir` every run (a used one is refused). `text_features` produced
nothing for `draft` to work from, so the first candidate is the operator's
hypothesis about what would make the signal more useful TO READ — not a
data-derived edit and not a text ablation (see §2.5).

**2026-09-04 — first candidate hypothesis, and what NOT to write.** The variance
run's tier-mix swing traces to the DIRECTIONAL regime label flipping between
BULL and RANGE on the same numbers (2 of 5 dates; see `current.md` 2026-09-04).
Do not write the "adopt `mech_regime` direction/vol" candidate: mech-only
selection is refuted on v3 (`mech_regime_recut` addendum 3) and null on v4
(paired-by-date CI spans zero, only 22/145 dates differ). Write instead a
candidate that keeps the flow-based read but adds a WRITTEN decision rule for
BULL/RANGE/BEAR over rollup fields the model already cites (index C/P percentile,
hedge-pressure score, PxVec), so identical inputs give an identical label. Test
repeatability BEFORE P&L — it needs no 40 dates:

```bash
python -m scripts.backtest_study run prompt_eval -- run --candidate <dir> \
  --dates backtests/prompt_eval/variance-dates.txt --repeats 3 --date-set OTHER \
  --run-dir backtests/prompt_eval/repeat-$(date +%Y%m%d) \
  --variance-json backtests/prompt_eval/variance-20260903/variance.json   # ~30 opus calls
```

Read the CANDIDATE arm's per-date regime labels and tier mix across the three
repeats against PROD's (`<run>/<arm>-r*/analysis/<date>.json`). If the label
still flips, the rule is not doing its job and the 40-date score is not worth
buying. Only a candidate that holds the label steady goes on to the backfill
command above.

## 3. Standing rules the next session must not re-litigate

**Selection and scoring**

- **Trigger-gated entry is LATE-ENTRY** (`trigger_entry`, 2026-09-04, v4 + v3).
  Any "enter only when the trigger fires" proposal must first explain why
  re-pricing at the crossing close would not remove the edge again; E2's census
  gap is the day-0 move, not the text.
- **The day-X / ±Y% / ±$Z exit formula is `staged_exit`, and it is null** —
  0/40 powered cells, day-5 loss cuts significantly harmful, 50–79%
  continuation sales. Do not re-register it under another anchor (days-since-
  entry or DTE-remaining) on these dates.
- **No further text study.** `text_features` NULL, `exit_from_text` E1
  CONTRARY, `prompt_eval` variance floor; §2.9 is a stability item only.
- `score_total` is decision-irrelevant (tie-break only). Selection is
  structure × regime × entry geometry.
- The ML/selection search is **closed**. Re-open on **new columns only**, tested
  within structure from the first look.
- `bear_call_spread` is intake-vetoed; bear debit is selection-vetoed at card
  §1.4 and lives in the §4 hedge sleeve only.

**Populations and pricing**

- **v3 and v4 rows are never pooled.** The v4 score scale is 0–50 (0–55 for
  VOLATILITY) and is not comparable to v3's 0–100.
- **Real + tweak pricing tiers only**; filter legacy `bs` rows by `proxy_method`.
- **Studies are ERA-scoped and the bare export filename does not name a
  population** — `lib/era.py` is the single encoding; run a past era with
  `--era v3` (archive/15).
- **`exit_basis` is readable on v4, not on v3 — and never for a REPLAY
  question.** v3 and earlier reach the export unlabelled and scrambled and are
  frozen that way; v4 is clean (485/485, verified 2026-09-02) and may be used to
  stratify by exit profile; `BacktestProxy` needs a re-run after the 2026-09-02
  writer fix before it carries anything. To ask whether a row *replays* under a
  profile, still classify by unreachable exit reasons — `lib/replay_basis.py`,
  which works on every era (§0c(A), archive/15).
  **Audited since 2026-09-02** — `scripts/backtest_study/lib/basis_audit.py` runs on every `load_book()` and prints a coherence line (currently `485 coherent, 0 sign_conflict, 0 cell_conflict, 0 unreachable_reason`). It REPORTS and never gates: gating the book on a LABEL would block the exit-profile studies the column exists to serve, and would block them hardest on v3, where the label is known-bad and the ROWS are fine. Stratify on the record's `basis_trusted`; do not assume, and do not re-derive by hand.
- **`hedge_exposure`'s registration describes the `real` stratum, not the
  ratified book.** Its plan-time exposure table, concentration quantiles and
  504-session universe reproduce on `real` alone; they are not disclosures about
  the ratified 996-row population
  ([`pre-registrations/f4_deployment/hedge_exposure.md`](pre-registrations/f4_deployment/hedge_exposure.md)
  §Population and basis).

**Vocabulary and process**

- **ARM labels are study-local.** Always qualify a citation with its study —
  `emission_timing ARM P`, never a bare `ARM P` (four studies own an ARM P).
  Look any label up in [`arm-index.md`](arm-index.md) (archive/17 §2026-08-24 docs).
- **Never read silence as "trigger not met."** Rollback triggers are evaluated at
  their gates, with numbers ([`deployment-evidence.md`](deployment-evidence.md)).
- **`study_review … --dry-run` CLOBBERS artifacts.** It overwrites the
  `-review-*` / `-digest-latest.md` files with 51-byte placeholders; two reviews
  were lost this way. Never use it as a read-only check (archive/17 §2026-08-24).
- **Never hardcode a figure off one export** — and the rule covers report
  *prose*, not just code: `bear_deploy` D3's write-up hardcoded a v3-era figure
  while its own table printed a different one (archive/17 §2026-08-24 late).
