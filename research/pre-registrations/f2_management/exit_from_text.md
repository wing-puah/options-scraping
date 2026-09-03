## exit_from_text — do the model's own trigger / invalidation / horizon lines beat the shipped exits?

_REGISTERED 2026-09-02; status: DRAFT — becomes immutable on first run._

An f2 MANAGEMENT study. Signal, entry day, structure, sizing and candidate set
are frozen; each arm changes one thing about an open position, or (E2) whether
it is opened.

## Question

Every emitted play states an entry TRIGGER, an INVALIDATION and a HORIZON; the
backtest ignores all three. Does honouring them beat the shipped profiles?
**E1** invalidation-as-stop, **E2** trigger-as-entry-filter, **E3**
horizon-as-time-exit — defined under Arms.

## What this is NOT

- **Not a re-run of Attempt 9.** Attempt 9 (2026-07-04, NOT validated) tested an
  underlying-breach stop on 12 credit rows keyed on the SHORT STRIKE. E1 keys on
  the model's own stated invalidation LEVEL, on the era book, through the frozen
  harness; where the two coincide the study says so (Confounds — the
  `level == a strike` split is a requirement, not a diagnostic).
- **Not a new trail.** No arm re-arms on a peak; drawdown-from-peak trailing
  failed three times (Attempts 1, 2, 10) and is not retested. **Not a selection
  study**, except where E2's effect is measured as one and labelled one.
- **Not a re-pricing.** Every arm replays STORED daily grids through the FROZEN
  `lib/harness.py` — **import only, no fork, no copy, no edit.** Nothing ships.

## Admissibility

The trigger / invalidation / horizon text is a **NEW COLUMN FAMILY**: in the
analysis export, never joined to the priced book, no numeric counterpart in the
closed sweep. Each parsed level is **observable at entry** — printed on the card
the operator reads.

## Population and basis, fixed here

- **PRIMARY: `current` (v4)** — the prompt whose text this is. **SECONDARY:
  `--era v3`**, identical thresholds, reported separately, **never pooled**.
- `load_book(include_bs=False)` — real + strike_expiry_tweak tiers only. **On
  v4 that exclusion is a NO-OP**: the v4 proxy export carries ZERO
  `bs_options_hist` rows (tweak 564 / underlying_trend 473 / unevaluable 107,
  measured 2026-09-02). It still binds on v3 (295 bs rows) and stays in force.
- **Priceability, measured 2026-09-02 (a census, not a target; a later run
  prints its own).** v4 = **1,022 priced rows / 148 dates** (2024-01-10 →
  2025-11-17), 1,016 joined to AnalysisClaude, 969 analysis rows unpriced
  (`excluded_by_book` 611, `not_backtested` 194, `market_row` 164); v3 = 795 /
  118, 820 unpriced. **Every arm is conditioned on ~52% priceability** — an exit
  rule replays only on a row that priced — and the report says so per table.
- Underlying closes from `lib/underlying.py::load_bars`. Wherever a cut uses
  bars the **SRC_OHLC / SRC_TILDE split is PRINTED and never pooled silently** —
  a tilde close is a different measurement from a real bar.
- **Cells: per STRUCTURE and per `mech_cell`.** Attempts 12 and 13b are explicit
  that exit behaviour is REGIME-CONDITIONAL (E-VOL/RANGE/BEAR let winners run,
  L-VOL/BULL do not), so a pooled read is not interpretable; a pooled headline
  may print for orientation only and is **NOT A CRITERION**.
- **Rows with no parseable invalidation level are their OWN BUCKET** — counted,
  reported as a **prompt-robustness finding**, never dropped, never imputed;
  same for unparseable triggers (E2). Measured 2026-09-02 the bucket is small on
  priced rows (`invalidation_level` coverage **98.8%**,
  `invalidation_inside_strikes` **95.0%**), so E1's population is nearly the
  whole priced book and the bucket is a robustness read, not a power problem.
- **The v4 2026 no-op.** The v4 results export carries ZERO 2026 signal dates
  (it ends 2025-11-17), so `ex_2026_feb_apr` ≡ `ALL`, ex-BOTH ≡
  `ex_2025_mar_apr`, and "positive in every calendar year" reduces to 2024 ∧
  2025 on the PRIMARY era. Every cut prints its `n` beside `ALL`'s so a reader
  sees a no-op, not a passed test.

## Arms

Three arms, frozen; no fourth is added.
### E1 — invalidation-as-stop

- **Rule:** exit at the close of the first session whose UNDERLYING close is
  beyond the parsed invalidation level, in the direction the STRUCTURE SIDE
  implies (long-delta exits on a close BELOW, short-delta ABOVE); direction is
  inferred from the structure, never from the outcome.
- **Buffer grid, frozen at {0%, 1%, 2%}.** Attempt 9's transferable observation:
  a 0% level clips marginal touches (XOM, 109.72 vs a 110 level), so 0% is the
  null arm and ≥1% the expected shape — declared here, not after.
- **Straddles and strangles use BREAKEVEN levels, never a strike** (Attempt 9: a
  strike basis fires day 1 when the short strike ≈ ATM); an uncomputable
  breakeven goes to the unparseable bucket, not a fallback.
- **The rule fires AHEAD of the PROD stops**, as it would ship; PROD's other
  exits stay live behind it.
- **The whipsaw caveat is registered, not discovered.** Attempt 9's July-2024
  cluster showed an underlying stop does NOT rescue gap/whipsaw losers — it exits
  them where the mark stop does; a positive E1 cell whose gain concentrates in
  one correlated event is reported as such, criterion 2 being the guard.

### E2 — trigger-as-entry-filter

- **Only PRICE-LEVEL triggers are testable** — in scope only if the trigger
  parses to a numeric price level with a direction. **Rule:** the entry counts
  only if the level was met within **N ∈ {1, 3} sessions** of the signal date on
  the OHLC cache; rows not met are **NOT ENTERED**.
- **This is a SELECTION effect and is quoted as one.** The estimand is mean R on
  the ENTERED subset vs the full population, **the excluded share printing beside
  every number**; no E2 result may be called an exit improvement.
- **Conditional-but-unparseable triggers are their own bucket** — reported with
  their n, never folded into either side. No trigger arm changes an exit rule;
  PROD exits run untouched on the entered set.

### E3 — horizon-as-time-exit

- **Rule:** replace PROD's `time_exit_dte_fraction 0.75` with the emitted
  `horizon`. **On v4 `horizon` is NUMERIC** — DTE buckets 14 / 60 / 180 / 720 —
  so E3 keys off that number directly, no text mapping, nothing to tune; the
  rest is the shipped profile. Where an era's `horizon` is not numeric the arm
  does not run on it and says so.
- **SURVIVAL CONTROL, RUN BEFORE ANY MONOTONE CLAIM.** `horizon` is
  mechanically coupled to hold length — a long-horizon play is only observed
  holding long. The 2026-08-19 `macro_event_study` ARM X lesson binds: a
  monotone table whose bucketing variable is coupled to hold length is a
  COMPOSITION read until proven otherwise. The control: (i) recompute the
  horizon table WITHIN `days_held` terciles (boundaries computed on the arm
  population, disclosed), (ii) print the horizon × hold-length census.
  **Non-monotone within the control, or flat inside every hold-length tercile →
  SURVIVAL-ARTIFACT, no follow-up queued.**

## Metrics

- **Paired ΔR vs PROD**, within row, aggregated by date:
  `protocol.boot_ci_paired_by_date`, `BOOT_N = 10000`, α = .05. **Paired PF**:
  `protocol.pf_paired_by_date` (`pf` / `pf_ci_by_date` for levels).
- **Rule, binding: a PF claim must ALSO clear the mean-R criterion** — PF alone
  is gameable by fewer, larger wins.
- **MFE give-back** — realized R vs the post-exit path maximum over the rest of
  the row's grid — prints for every arm, DESCRIPTIVE except where a cell's exits
  are majority continuation sales, which is called out in the write-up.
- **R is quoted, never dollars** — E2 changes the entered population and E1/E3
  change hold length, so dollar totals are not comparable across arms.

## Power floors

Declared before any count, checked FIRST, blocking everything else.
- **Per cell (arm × structure × mech_cell × grid value): ≥ 60 AFFECTED ROWS and
  ≥ 25 AFFECTED DATES.** "Affected" is `lib/triggers.py::is_affected` — base and
  variant produce different `(exit_reason, days_held, round(pnl, 10))` under the
  frozen replay; a date where the arm changes nothing is not affected. For E2,
  "affected" means the entered set differs from the full population that date.
  A cell under either floor is **UNDERPOWERED**: printed with its n, no
  criterion evaluated, nothing refuted.
- Said plainly now: a 3-arm × structure × mech_cell × grid design on 148 v4
  dates / 1,022 priced rows will UNDERPOWER most cells — expected, not a
  failure.

## Bar for CANDIDATE

The full conjunction, all of it — failing any one is failing:
1. paired ΔR vs the SHIPPED book with **date-clustered bootstrap CI excluding
   zero** (`BOOT_N = 10000`, α = .05);
2. **every** LOO fold positive (`protocol.loo_by_date`, read `min_gain`) **AND**
   the LOO **median fold gain > 0 AMONG AFFECTED DATES** — the 2026-07-22
   corrected gate, since a zero-inflated delta makes a pooled median untrippable;
3. survives `protocol.window_cuts` **AND the ex-BOTH cut added BY HAND**; on v4
   both collapse to the 2026 no-op above and the report says so;
4. **positive in every calendar year present** in the cell's population
   (`protocol.sign_stable`);
5. right-signed on **BOTH pricing tiers** (real and tweak);
6. ≥ 60 affected rows and ≥ 25 affected dates, re-checked on the evaluated set;
7. **no perturbation flip across the buffer grid** — an E1 cell positive at one
   buffer and sign-flipped at an adjacent one in {0%, 1%, 2%} is a knob artifact
   and fails; E3's analogue is the survival control, which a cell must survive
   whatever its ΔR.

Worst-decile cells print **DESCRIPTIVELY**, **NOT A CRITERION** (the 2026-08-13
nine-date decile wall).

## Verdict grammar

Per cell, exactly one of:
- **UNDERPOWERED** — a floor was not met; census published, nothing read.
- **NULL** — powered, conjunction not cleared; recorded. **CANDIDATE** — the
  whole conjunction clears; NOT a ship.
- **CONTRARY** — powered, CI excludes zero, sign OPPOSITE to the arm's hypothesis
  (the text-derived exit is reliably WORSE than PROD). A real finding — the
  emitted invalidation/horizon is actively misleading — recorded as such and fed
  to `text_features`' PROMPT-ROBUSTNESS list.
- **SURVIVAL-ARTIFACT** (E3 only) — the raw table is monotone but dies under the
  survival control; no follow-up queued, per the 2026-08-19 precedent.
- **NO PRE-REGISTERED VERDICT MATCHES** — the catch-all, printed with its numbers
  and resolved by hand in `research/current.md`.

Separately and always: the **unparseable buckets** (invalidation, trigger) are
reported with their shares as PROMPT-ROBUSTNESS FINDINGS whatever else happens.

## What ships if MET

**Nothing automatically.** A CANDIDATE becomes a written proposal:
- a `structure_exit` / `regime_exit` cell in `config/backtest.yml` keyed on the
  structure and `mech_cell` it was found in — never a global override;
- a matching line in `docs/deployment-rules.md` §5;
- **its own rollback trigger** against `lib/triggers.py` (affected rows /
  affected dates / floor / MET | UNDERPOWERED), so the rule is evaluated forward
  rather than assumed, plus an independent-window confirmation first.

The operator decides. E2 can never ship as an exit rule; if it clears it is an
INTAKE proposal, labelled one.

## Known confounds, declared now

- **The invalidation level often IS the short strike** — where it is, E1 partly
  re-tests Attempt 9 rather than the model's judgement. **Pre-declared binding
  split: `level == a strike` vs `level ≠ any strike` (tolerance fixed in the
  module before the run); the result must be carried by the SECOND cell.** A
  CANDIDATE whose gain lives only in the first cell is an Attempt-9 restatement,
  not a text finding.
- **E3 is coupled to hold length** — handled by the survival control above,
  which runs BEFORE any monotone claim. **E2 changes the population**, so its
  comparison is never like-for-like; the excluded share prints and the effect is
  named a selection effect.
- **Concentration.** Attempt 9's headline was >100% explained by one correlated
  pair; LOO (criterion 2) is the guard, and any cell whose gain concentrates in
  one event is called out even when it passes. **SRC_TILDE closes are not real
  bars** — the split prints, never pooled.

## Anti-tuning

Three arms; buffers at three values; N at two; `horizon` read as the emitted
number; cells cut by structure × `mech_cell` and fixed before any outcome is
read. Exit profiles other than the arms' own rule, the sizing formula, the
structure universe, the entry side and the candidate population are NOT swept.
No threshold moves and no cell is added after any number is seen. **Every cell
is reported regardless of outcome.** No annualised figure, Sharpe or
time-to-recover anywhere.

## Build notes

*Not part of the registration — implementation record.*
- Module `scripts/backtest_study/f2_management/exit_from_text.py`; run
  `python -m scripts.backtest_study run exit_from_text` (`--era v3` secondary);
  report `backtests/study_output/exit_from_text-latest.txt`. `lib/harness.py` is
  **NOT touched and NOT copied** — every arm composes around the frozen
  `replay`, the `next_day_move` / `staged_exit` ARM E pattern. Text from
  `lib/text_corpus.py`; closes from `lib/underlying.py`.
- `tests/test_exit_from_text.py` must cover E1 parity on a synthetic path against
  the harness exit vocabulary, the parser edge cases (including the straddle
  breakeven path) and the unparseable buckets.
- A `scripts/study_map/catalog.py` entry with a hand-written VERDICT is REQUIRED
  — no entry fails the test suite — plus a `research/study-map.md` prose mention
  (test-enforced).
- Every report prints `debit_calib`, `n_credit_ungated`, the credit-ungated
  caveat, the era header, priceability, the SRC split and the unparseable
  shares; PF never prints without mean R beside it.

---

## Wording corrections — appended 2026-09-02 at build time

*Not amendments. Nothing below moves a threshold, adds a cell, changes an arm's
definition or touches a verdict rule. Each entry records a place where the
registration's WORDING could not be implemented literally against the frozen
harness or the frozen corpus, and states exactly what the module does instead.
Appended at the end, dated, as the record of what the run actually ran.*

1. **E3's horizon is mapped to a CALENDAR-DAY count, not a "session count".**
   The registration says the horizon is "mapped to a session count once and
   frozen". `lib/harness.py`'s time exit compares
   `(day - signal_date).days >= int(dte_entry * tef)` — calendar days — so a
   session mapping is unreachable without forking the engine, which §Build
   notes forbids. `exit_from_text.horizon_tef` passes
   `tef = (H + 0.5) / dte_entry`, which makes the frozen engine's `int()` land
   on exactly H calendar days. The horizon buckets themselves are unchanged
   and still mapped once.

2. **A text stop that fires on the SAME session as the shipped exit leaves the
   outcome unchanged.** §E1 says the rule "fires AHEAD of the PROD stops"; the
   variant is implemented as the EARLIER of the two, so a tie is not a change.
   On a tie the pnl and `days_held` are identical by construction and only the
   exit LABEL would move; counting a label-only change as AFFECTED would
   zero-inflate the affected set, which is the exact failure criterion 2's
   affected-dates median exists to defend against.

3. **LONG-VOL (debit) straddles and strangles are an unusable bucket, not a
   breakeven stop.** §E1 routes straddles and strangles to breakeven levels.
   Beyond a breakeven is where a DEBIT straddle WINS, so a breakeven-beyond
   stop would fire on the profit side and would not be an invalidation at all.
   Those rows go to the bucket `long_vol_no_stop_side`, counted and reported
   with the other buckets. Credit (short-vol) straddles and strangles take the
   registered breakeven basis unchanged.

4. **`iron_condor` / `butterfly` / `calendar` are their own bucket.** They are
   neither delta-directional (so §E1's structure-side rule gives no direction)
   nor named by the straddle/strangle bullet. They are reported as
   `no_structure_side` rather than being given a direction by guess.

5. **E2's criterion-7 analogue is the N grid.** Criterion 7 is written for E1's
   buffer grid and names the survival control as E3's analogue; E2 is not
   given one. The module uses the frozen N grid {1, 3} the same way: a cell
   positive at one N and sign-flipped at the other is a knob artifact and
   fails. This can only make an E2 cell harder to pass.

6. **E2's cell estimator is paired BY DATE on date means.** §Metrics fixes the
   paired-by-date bootstrap for arms that change an exit within a row; E2
   changes WHICH rows a date contributes, so there is no within-row pair. Each
   cell pairs the entered book's date mean against the full population's date
   mean on the dates where both exist. The registered headline numbers — mean
   R entered vs the full population, with the excluded share in rows and dates
   — print unchanged beside it, and no E2 result is described as an exit
   improvement.

7. **The calibration gate admits `near` alongside `exact` and `boundary_tie`,
   and EXCLUDES rather than aborts.** A `near` row reproduces its stored exit
   reason and day with a pnl difference inside `replay_basis.NEAR_MISS_TOL`,
   which is a reproduction. `superseded` and `hard` rows are dropped from the
   variant arms and counted in the printed census, rather than failing the run
   the way `exit_mechanism_study.calibrate` does: every arm here re-replays,
   so a non-reproducing row would contribute a delta measured against a
   baseline production never ran, which is a finding about the replay and not
   about the text.

8. **Cells are reported at three cuts, not one.** §Population says "per
   STRUCTURE and per `mech_cell`" while §Power floors names the full cross
   "(arm x structure x mech_cell x grid value)". The report prints the two
   marginals AND the cross, each with the floor applied to it, plus the pooled
   `ALL` row marked NOT A CRITERION. Nothing is narrowed and no cut was added
   after a number was seen.
