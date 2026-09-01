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

⚠️ **NEW STANDING HAZARD — do NOT key anything on the `exit_basis` column.** This
section previously recommended identifying superseded rows by that column. It
exists in `_KEY_ORDER` (`scripts/backtest/core.py:61`) and the writer
(`simulate.py:_exit_basis`) is correct, but it reaches the export as an
**unlabelled 47th column** (the Sheets tab header was never given the name) and
its values are **scrambled relative to their rows**. Measured 2026-08-14: of 67
`BacktestResults` rows created after the trail shipped — every one of which should
carry a basis — **65 are blank**, while **55 `BEAR_HE` and 11 `CREDIT` labels sit
on rows created *before* the column existed**; **7 of 13 `CREDIT`-tagged rows have
a positive entry price**, which `_exit_basis` cannot produce; and no
`BEAR_HE`-tagged row has a `trailing_stop` exit. Root cause is the hazard
CLAUDE.md warns about: `scripts/align_tab_headers.py` checks only the **analysis**
tabs against `config.ROW_COLUMNS` and does **not** cover
`BacktestResults`/`BacktestProxy` against `core._KEY_ORDER`.
`docs/backtest-reference.md`'s "blank = PROD-basis by definition" is **false on
this export**; both that file and `simulate.py` now carry the warning.

- [ ] **Operator action (a Sheets write, NOT taken):** extend
      `align_tab_headers.py` to cover the two backtest tabs against
      `core._KEY_ORDER`, fix the header, then re-verify the values against
      entry-price sign before any study reads the column.
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

- **`hedge_exposure`** (2026-08-31) — run, graded, population **`all` ratified**
  (996 rows / 145 dates). Two verdicts over two objects: the mechanism question
  is **UNDERPOWERED** (all nine τ×f cells fail G-POWER, no direction quoted) and
  ARM M is **MEASUREMENT-ONLY** (the close-bucketed curve understates this
  book's max drawdown by 40.2%). Ships nothing. →
  [`hedge-exposure-errata.md`](hedge-exposure-errata.md) §RATIFICATION +
  §Post-ratification notes, and [`current.md`](current.md) 2026-08-31.
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

### 2.0 `concurrency_correlation` — PRE-REGISTERED 2026-08-22, module STILL NOT WRITTEN

The highest-value unbuilt thing in the repo. The operator's read ("the more that
is being deployed, the less it seems to be working") does **not** resolve to
depth into the ranked list — within-day rank is flat on both eras, so a tighter
top-N is not the answer. What has never been measured is the **size and internal
similarity of the open book**: `account_sim` computes `n_open` and no report
joins it to an outcome.

- Plan: `research/pre-registrations/f4_deployment/concurrency_correlation.md`
  (ARM N null band, ARM D0 descriptive, ARM C concurrency ceiling, ARM K
  clustering ceiling, ARM CK only if both clear alone).
- **Read its dead-end table before writing any code** — two v3 day-level cuts
  looked strong on v3 and vanish on v4, and X7 refuses any arm that turns out to
  be a delta ceiling in disguise.
- Evidence: [archive/17](archive/17-v4-refresh-bear-deploy-and-vocabulary.md)
  §2026-08-22 (late).

### 2.1 The max-drawdown hedge question — `hedge_concentration` RUN: PRECONDITION-NULL (powered); GRADING PENDING

**Status: answered on the admitted book, not yet graded.** The module was
written and run on 2026-08-31 (era v4, sha 9834563, exit 0): Stage 1 cleared
G-POWER-K (`[162, 166, 152]` usable sessions per tercile, 3 dense episodes)
and returned **PRECONDITION-NULL** — contrast −$692, CI95 [−$2,000, +$420];
ρ −0.149, CI95 [−0.383, +0.098]; neither beats the circular-shift null's 5th
percentile; the 2025 dense episode carries the opposite sign. Stage 2 was not
entered. The report's own branch line: *record in `deployment-evidence.md` as
closing the queued max-drawdown question for concentration-gated hedging;
§2.1 closed.* Full read: [`current.md`](current.md) 2026-08-31 (night).

**Background.** `hedge_exposure` did not answer it —
every cell was power-stopped on the ratified population — and the reason is
now settled, not pending an operator answer: the dilution finding (errata
post-ratification note 3) was resolved from disk on 2026-08-31. The operator's
card admits at most 3 positions/day (`config/account-sim.yml`), `account_sim`
takes **221 of 458** ladder-eligible rows from the ratified population, and
`hedge_exposure` held all 996. The study measured a book roughly twice as
diversified as the one the operator runs.

**What was done:** the "third reading" is registered as
[`pre-registrations/f4_deployment/hedge_concentration.md`](pre-registrations/f4_deployment/hedge_concentration.md)
— ratified prices, but the ADMITTED book. Its plan-time census (inputs only)
found the admitted book concentrated almost always (median any-cluster
0.464 vs 0.209; MEGATECH or SEMIS on top 87% of sessions; 93% CONSTITUENT),
so a τ×f hedge grid cannot be powered on it (episodes peak at 20 < 25). The
registration therefore puts the PRECONDITION first — H-C from the 2026-08-29
feasibility pass, now ARM K: does open-book concentration PREDICT forward
mark-to-market drawdown? That is powerable on 498 sessions, and its Ship
criteria give **every** outcome a branch that moves this item: NULL /
GROSS-NOT-CONCENTRATION close the question in `deployment-evidence.md`;
FOUND + Stage 2 UNDERPOWERED re-labels it BLOCKED ON NEW DATES like §2.3;
FOUND + MECHANISM-FOUND drafts-and-holds a §4 amendment.

**What is left, in order:**

1. ~~Write the module.~~ DONE 2026-08-31 — `hedge_concentration.py`, 62 tests,
   `catalog.py` entry, `study-map.md` row, `study-results` record; new
   `lib/forward_drawdown.py`; `lib/mtm_curve.book_curves(target=)` (the
   admitted book reconciles against the replay's own dollars, 221/221, and
   cannot against the stored row — 101 re-sized, 35 re-exited).
2. **`python -m scripts.study_review hedge_concentration`** (never with
   `--dry-run`). The graders should read the report's NOT PRE-REGISTERED
   block (20 choices) against the registration first. On a clean grade AND
   operator sign-off: record the branch in `deployment-evidence.md` and close
   this section. A grading defect reopens the module, never the registration.
3. **Deferred, not dropped — the prose control.** `hedge_exposure` ARM P stays
   inert (ERRATUM 2) and the corrected control — ARM C on concentration-matched
   sessions carrying NO hedge-pressure signal, matched on count — is NOT in
   `hedge_concentration`: the admitted book carries only 19 prose-conditioned
   sessions / 17 episodes at the loosest τ, so it would be another arm that
   can never bite. Register it only when the book has materially more parsed
   dates.

Design material on disk: the 2026-08-29 feasibility pass in
[`current.md`](current.md) and the census entry there dated 2026-08-31 (late).

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

## 3. Standing rules the next session must not re-litigate

**Selection and scoring**

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
- **Never key a study on the `exit_basis` column.** It reaches the export
  unlabelled and scrambled — classify by unreachable exit reasons instead
  (§0c(A), archive/15).
- **`hedge_exposure`'s registration describes the `real` stratum, not the
  ratified book.** Its plan-time exposure table, concentration quantiles and
  504-session universe reproduce on `real` alone; they are not disclosures about
  the ratified 996-row population
  ([`hedge-exposure-errata.md`](hedge-exposure-errata.md) §RATIFICATION).

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
