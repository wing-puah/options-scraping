## exit_from_text — do the model's own trigger / invalidation / horizon lines beat the shipped exits?

<!-- outcome:start -->
> Latest outcome: no `CANDIDATE` cell; 301 cells `UNDERPOWERED`, 17 `NULL` and 18 `CONTRARY`; the pooled `ALL` rows are not a criterion (v4 era) — 2026-09-28 · [record](../../study-results/f2_management/exit_from_text.md).
<!-- outcome:end -->

_Registered 2026-09-02._

## The question

Every emitted play states an entry TRIGGER, an INVALIDATION and a HORIZON. The backtest ignores all three. Does honouring them beat the shipped profiles?

This is an f2 MANAGEMENT study. Signal, entry day, structure, sizing and candidate set are frozen. Each arm changes one thing about an open position, or (E2) whether it is opened. Nothing ships.

The trigger, invalidation and horizon text is a NEW COLUMN FAMILY. It sits in the analysis export. It is never joined to the priced book, and the closed sweep has no numeric counterpart. Each parsed level is observable at entry, because it is printed on the card the operator reads.

## What this study is not

- **Not a re-run of Attempt 9.** Attempt 9 (2026-07-04, NOT validated) tested an underlying-breach stop on 12 credit rows keyed on the SHORT STRIKE. E1 keys on the model's own stated invalidation LEVEL, on the era book, through the frozen harness. Where the two coincide, the study says so. The `level == a strike` split is a requirement, not a diagnostic (see "The strike split").
- **Not a new trail.** No arm re-arms on a peak. Drawdown-from-peak trailing failed three times (Attempts 1, 2, 10) and is not retested.
- **Not a selection study**, except where E2's effect is measured as one and labelled one.
- **Not a re-pricing.** Every arm replays STORED daily grids through the FROZEN `lib/harness.py`. It is import only: no fork, no copy, no edit.

## Population and basis, fixed here

| Fixed | Value |
|---|---|
| Era | PRIMARY `current` (v4), the prompt whose text this is. SECONDARY `--era v3`, identical thresholds, reported separately. **Never pooled** |
| Book | `load_book(include_bs=False)`: real and `strike_expiry_tweak` tiers only. On v4 that exclusion is a NO-OP (zero `bs_options_hist` rows). It still binds on v3 |
| Conditioning | Every arm is conditioned on priceability: an exit rule replays only on a row that priced. The report says so per table |
| Closes | Underlying closes from `lib/underlying.py::load_bars` |
| Bars | Wherever a cut uses bars, the SRC_OHLC / SRC_TILDE split is PRINTED and never pooled silently. SRC_TILDE closes are not real bars |
| Cells | Per STRUCTURE and per `mech_cell` (see "Power floor") |
| Calibration | Rows that do not reproduce their stored exit are EXCLUDED and counted, not failed (see "Calibration gate") |
| Unparseable invalidation | Rows with no parseable invalidation level are their OWN BUCKET: counted, reported as a prompt-robustness finding, never dropped, never imputed |
| Unparseable trigger | Same treatment for unparseable triggers (E2) |

Exit behaviour is REGIME-CONDITIONAL (Attempts 12 and 13b: E-VOL/RANGE/BEAR let winners run, L-VOL/BULL do not). A pooled read is therefore not interpretable. A pooled headline may print for orientation only and is **NOT A CRITERION**.

**The v4 2026 no-op.** The v4 results export carries ZERO 2026 signal dates. So `ex_2026_feb_apr` is identical to `ALL`, ex-BOTH is identical to `ex_2025_mar_apr`, and "positive in every calendar year" reduces to 2024 and 2025 on the PRIMARY era. Every cut prints its `n` beside `ALL`'s, so a reader sees a no-op, not a passed test.

## Plan-time observations, disclosed

Measured 2026-09-02, before any arm ran. They are a census, not a target. A later run prints its own. No number here is a result.

- v4 holds **1,022 priced rows / 148 dates** (2024-01-10 to 2025-11-17). Of these, 1,016 join to AnalysisClaude. 969 analysis rows are unpriced (`excluded_by_book` 611, `not_backtested` 194, `market_row` 164).
- v3 holds 795 / 118, 820 unpriced (priced rows / dates, then unpriced rows).
- The v4 proxy export carries tweak 564 / underlying_trend 473 / unevaluable 107, measured 2026-09-02. v3 carries 295 bs rows.
- On v4 priced rows, `invalidation_level` coverage is **98.8%** and `invalidation_inside_strikes` coverage is **95.0%**. E1's population is nearly the whole priced book. The unparseable bucket is a robustness read, not a power problem.
- Pre-run expectation: every arm is conditioned on about 52% priceability. A 3-arm × structure × `mech_cell` × grid design on 148 v4 dates and 1,022 priced rows will UNDERPOWER most cells. That is expected, not a failure.

## What it compares

Three arms, frozen. No fourth arm is added. Labels: [`exit_from_text E1`, `E2` and `E3`](../../arm-index.md#exit_from_text).

| Arm | What it does | Kind |
|---|---|---|
| `exit_from_text E1` | Exits at the first close of the underlying beyond the parsed invalidation level, in the direction the structure implies. Buffer grid {0%, 1%, 2%} | exit arm |
| `exit_from_text E2` | Enters the play only if its price-level trigger was met within N ∈ {1, 3} sessions of the signal date. Rows not met are NOT ENTERED | selection effect |
| `exit_from_text E3` | Replaces PROD's `time_exit_dte_fraction 0.75` with the emitted `horizon`, a DTE bucket of 14, 60, 180 or 720 | exit arm |

### E1 — invalidation-as-stop

- **Rule.** Exit at the close of the first session whose UNDERLYING close is beyond the parsed invalidation level, in the direction the STRUCTURE SIDE implies. Long-delta structures exit on a close BELOW the level. Short-delta structures exit on a close ABOVE it. Direction is inferred from the structure, never from the outcome.
- **Buffer grid, frozen at {0%, 1%, 2%}.** A 0% level clips marginal touches (Attempt 9: XOM, 109.72 against a 110 level). So 0% is the null arm and 1% or more is the expected shape. This is declared here, not after the run.
- **Straddles and strangles use BREAKEVEN levels, never a strike.** A strike basis fires on day 1 when the short strike is near ATM (Attempt 9). An uncomputable breakeven goes to the unparseable bucket, not to a fallback.
- **LONG-VOL (debit) straddles and strangles** (Wording correction (2026-09-02, at build time):) go to the bucket `long_vol_no_stop_side`, counted and reported with the other buckets. Beyond a breakeven is where a debit straddle WINS, so a breakeven stop would fire on the profit side and would not be an invalidation. Credit (short-vol) straddles and strangles take the breakeven basis unchanged.
- **`iron_condor`, `butterfly` and `calendar`** (Wording correction (2026-09-02, at build time):) go to the bucket `no_structure_side`. They have no delta direction and the straddle/strangle rule does not name them. They are never given a direction by guess.
- **Order against PROD.** The rule "fires AHEAD of the PROD stops", as it would ship. PROD's other exits stay live behind it. Wording correction (2026-09-02, at build time): the variant is the EARLIER of the two. If the text stop fires on the SAME session as the shipped exit, the outcome is unchanged, because pnl and `days_held` are identical. Counting a label-only change as AFFECTED would zero-inflate the affected set.
- **Whipsaw caveat, registered now.** Attempt 9's July-2024 cluster showed an underlying stop does NOT rescue gap and whipsaw losers. It exits them where the mark stop does. A positive E1 cell whose gain concentrates in one correlated event is reported as such. Clause 2 of the bar is the guard.

### E2 — trigger-as-entry-filter

- **Scope.** Only PRICE-LEVEL triggers are testable: the trigger must parse to a numeric price level with a direction.
- **Rule.** The entry counts only if the level was met within **N ∈ {1, 3} sessions** of the signal date on the OHLC cache. Rows not met are **NOT ENTERED**.
- **This is a SELECTION effect and is quoted as one.** The estimand is mean R on the ENTERED subset against the full population. The excluded share prints beside every number. No E2 result may be called an exit improvement.
- **Cell estimator** (Wording correction (2026-09-02, at build time):) E2 changes WHICH rows a date contributes, so there is no within-row pair. Each cell pairs the entered book's date mean against the full population's date mean, on the dates where both exist. The headline numbers print unchanged beside it: mean R entered against the full population, with the excluded share in rows and dates.
- **Conditional-but-unparseable triggers** are their own bucket. They are reported with their n and never folded into either side.
- No trigger arm changes an exit rule. PROD exits run untouched on the entered set.

### E3 — horizon-as-time-exit

- **Rule.** Replace PROD's `time_exit_dte_fraction 0.75` with the emitted `horizon`. On v4, `horizon` is NUMERIC: DTE buckets 14 / 60 / 180 / 720. E3 keys off that number directly, with no text mapping and nothing to tune. The rest is the shipped profile. Where an era's `horizon` is not numeric, the arm does not run on it and says so.
- **Calendar days** (Wording correction (2026-09-02, at build time):) The horizon maps to a CALENDAR-DAY count, once, and is frozen. The frozen engine's time exit compares `(day - signal_date).days >= int(dte_entry * tef)`, in calendar days. The registration first said the horizon is mapped to a "session count" once. A session mapping is unreachable without forking the engine, which this registration forbids (see "What this study is not"). `exit_from_text.horizon_tef` passes `tef = (H + 0.5) / dte_entry`, which makes the engine's `int()` land on exactly H calendar days. The buckets are unchanged.
- **SURVIVAL CONTROL, RUN BEFORE ANY MONOTONE CLAIM.** `horizon` is mechanically coupled to hold length: a long-horizon play is only observed holding long. The 2026-08-19 `macro_event_study` ARM X lesson binds. A monotone table whose bucketing variable is coupled to hold length is a COMPOSITION read until proven otherwise. The control has two parts:
  1. Recompute the horizon table WITHIN `days_held` terciles. The boundaries are computed on the arm population and disclosed.
  2. Print the horizon × hold-length census.
- If the table is non-monotone within the control, or flat inside every hold-length tercile, the cell is `SURVIVAL-ARTIFACT`. No follow-up is queued.

## How it is judged

**Estimand.** Paired [ΔR](../../glossary.md#r) against the shipped book, within row, aggregated by date. The test is `protocol.boot_ci_paired_by_date`, `BOOT_N = 10000`, α = .05. R is quoted, never dollars: E2 changes the entered population and E1/E3 change hold length, so dollar totals are not comparable across arms.

**PF.** Paired [PF](../../glossary.md#pf) prints via `protocol.pf_paired_by_date` (`pf` / `pf_ci_by_date` for levels). A PF claim must ALSO clear the mean-R criterion, because PF alone is gameable by fewer, larger wins. PF never prints without mean R beside it.

**MFE give-back.** Realized R against the post-exit path maximum over the rest of the row's grid prints for every arm. It is DESCRIPTIVE. Where a cell's exits are majority continuation sales, the write-up calls that out.

**Cells** (Wording correction (2026-09-02, at build time):) A cell is arm × structure × `mech_cell` × grid value. The report prints the two marginals (per structure, per `mech_cell`) AND the cross, each with the floor applied to it. The floor text names the full cross "(arm x structure x mech_cell x grid value)", while the population text says "per STRUCTURE and per `mech_cell`"; all three cuts are printed. It also prints the pooled `ALL` row, marked NOT A CRITERION. Nothing is narrowed, and no cut is added after a number is seen.

**Calibration gate.** Rows that do not reproduce their stored exit are excluded and counted.

- Wording correction (2026-09-02, at build time): the gate admits `near` alongside `exact` and `boundary_tie`. A `near` row reproduces its stored exit reason and day with a pnl difference inside `replay_basis.NEAR_MISS_TOL`.
- `superseded` and `hard` rows are dropped from the variant arms and counted in the printed census. Unlike `exit_mechanism_study.calibrate`, which fails the run, they do not. Every arm re-replays, so a non-reproducing row would add a delta measured against a baseline production never ran.
- `Resolved at build (2026-09-28)`, operator ruling: since the 2026-09-24 re-price, a stored row is net of `cost_total` and stops at `path_data_end`. The comparison adds the row's cost back and replays the path cut at `path_data_end` (`lib/replay_basis.py`). So an `open_at_data_end` row matches as the `cap_open` outcome it is. A row with blank `cost_basis` is compared as before. A deferred exit fill (`exit_fill` = `deferred_<n>`) is its own `deferred_fill` class, kept as an outcome and never compared. The gate's bar is unchanged. `deferred_fill` rows leave the variant arms with `superseded` ones, counted in the census.
- `Resolved at build (2026-10-21)`, operator ruling: a pending row is no longer in the book. It is an `open_at_data_end` row still inside its path window at the export's data end (`lib/book.py::is_pending`). A row whose window has closed still matches as `cap_open`. The gate's bar is unchanged.

## Gates

- **Power floor, declared before any count, checked FIRST, blocking everything else.** Per cell (arm × structure × `mech_cell` × grid value): **≥ 60 AFFECTED ROWS and ≥ 25 AFFECTED DATES**.
  - "Affected" is `lib/triggers.py::is_affected`. Base and variant produce different `(exit_reason, days_held, round(pnl, 10))` under the frozen replay. A date where the arm changes nothing is not affected.
  - For E2, "affected" means the entered set differs from the full population on that date.
  - A cell under either floor is **UNDERPOWERED**. It prints with its n, no criterion is evaluated, and nothing is refuted.

## Bar for a candidate

A cell must clear the full conjunction. Failing any one clause is failing.

1. **Paired ΔR** against the SHIPPED book, with the date-clustered bootstrap CI **excluding zero** (`BOOT_N = 10000`, α = .05).
2. **Leave-one-date-out.** **Every** [LOO](../../glossary.md#loo) fold is positive (`protocol.loo_by_date`, read `min_gain`), **AND** the LOO **median fold gain is > 0 AMONG AFFECTED DATES**. This is the 2026-07-22 corrected gate: a zero-inflated delta makes a pooled median untrippable.
3. **Window cuts.** The cell survives `protocol.window_cuts` **AND the ex-BOTH cut added BY HAND**. On v4 both collapse to the 2026 no-op above, and the report says so.
4. **Calendar years.** **Positive in every calendar year present** in the cell's population (`protocol.sign_stable`).
5. **Pricing tiers.** Right-signed on **BOTH pricing tiers**, real and tweak.
6. **Power, re-checked.** ≥ 60 affected rows and ≥ 25 affected dates, re-checked on the evaluated set.
7. **No perturbation flip.** An E1 cell positive at one buffer and sign-flipped at an adjacent one in {0%, 1%, 2%} is a knob artifact and fails. E3's analogue is the survival control, which a cell must survive whatever its ΔR. (Wording correction (2026-09-02, at build time):) E2's analogue is the frozen N grid {1, 3}: a cell positive at one N and sign-flipped at the other is a knob artifact and fails. This can only make an E2 cell harder to pass.

### The strike split

The invalidation level often IS the short strike. Where it is, E1 partly re-tests Attempt 9 rather than the model's judgement. The binding split is `level == a strike` against `level ≠ any strike`. The tolerance is fixed in the module before the run. **The result must be carried by the SECOND cell.** A CANDIDATE whose gain lives only in the first cell is an Attempt-9 restatement, not a text finding.

### Edge cases and descriptive prints

- **Concentration.** Attempt 9's headline was more than 100% explained by one correlated pair. LOO (clause 2) is the guard. Any cell whose gain concentrates in one event is called out even when it passes.
- **Worst-decile cells** print **DESCRIPTIVELY** and are **NOT A CRITERION** (the 2026-08-13 nine-date decile wall).
- **E2 is never like-for-like.** It changes the population, so its excluded share prints and its effect is named a selection effect.

## Possible verdicts

One token per cell.

| Token | When |
|---|---|
| `UNDERPOWERED` | A floor was not met. Census published, nothing read |
| `NULL` | Powered, conjunction not cleared. Recorded |
| `CANDIDATE` | The whole conjunction clears. NOT a ship |
| `CONTRARY` | Powered, CI excludes zero, and the sign is OPPOSITE to the arm's hypothesis (the text-derived exit is reliably WORSE than PROD). A real finding: the emitted invalidation or horizon is actively misleading. It is recorded as such and fed to `text_features`' PROMPT-ROBUSTNESS list |
| `SURVIVAL-ARTIFACT` | E3 only. The raw table is monotone but dies under the survival control. No follow-up queued, per the 2026-08-19 precedent |
| `NO PRE-REGISTERED VERDICT MATCHES` | The catch-all. Printed with its numbers and resolved by hand in `research/current.md` |

Separately and always, the **unparseable buckets** (invalidation, trigger) are reported with their shares as PROMPT-ROBUSTNESS FINDINGS, whatever else happens.

## Anti-tuning

- Three arms. Buffers at three values. N at two values. `horizon` read as the emitted number. Cells cut by structure × `mech_cell`, fixed before any outcome is read.
- Exit profiles other than the arms' own rule, the sizing formula, the structure universe, the entry side and the candidate population are NOT swept.
- No threshold moves and no cell is added after any number is seen.
- **Every cell is reported regardless of outcome.**
- No annualised figure, Sharpe or time-to-recover anywhere.

## What could ship

**Nothing ships automatically.** A `CANDIDATE` becomes a written proposal:

- a `structure_exit` / `regime_exit` cell in `config/backtest.yml`, keyed on the structure and `mech_cell` it was found in, never a global override;
- a matching line in [`docs/deployment-rules.md` §5](../../../docs/deployment-rules.md#s5);
- **its own rollback trigger** against `lib/triggers.py` (affected rows / affected dates / floor / MET | UNDERPOWERED), so the rule is evaluated forward rather than assumed, plus an independent-window confirmation first.

The operator decides. E2 can never ship as an exit rule. If it clears, it is an INTAKE proposal, labelled one.
