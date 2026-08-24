## staged_exit

_Registered 2026-08-19._

**Question.** Does a TIME-STAGED exit switch beat the shipped profile? The rule
under test is the operator's own shape: *"by session X, if the position is
±Y against its ORIGINAL entry, do A; otherwise continue exactly as shipped."*
This is an f2 MANAGEMENT study: the signal, the entry day, the structure, the
sizing and the candidate set are all frozen; the only thing any arm changes is
what happens to an already-open position at one pre-declared session.

**What this is NOT — the Attempt-1/2/10 overlap, named first.** This repo has
already tested drawdown-from-peak trailing exits three times (Attempts 1, 2 and
10) and they failed three times. The mechanism of that failure is recorded and
is not in dispute: a trail is **reactive** — it re-arms on every new peak, so it
fires on noise, and **all 21 debit trail exits sold continuations**. A
time-staged switch is a different object: it evaluates **ONCE, at a fixed
session X, on P&L measured against the ORIGINAL entry**, and it **cannot
re-fire**. That single-evaluation, entry-anchored property is the entire
distinction, and it is why this study is admissible at all after three
failures.

The corollary is registered here as a failure mode rather than discovered
later: **any post-X action that tightens a stop or arms a trail reintroduces
the reactive mechanism on the tail.** ARM T does exactly that, deliberately, as
a transfer test — and it is therefore guarded by **G2, the continuation
diagnostic, which is a PASS CRITERION and not a footnote.** A staged cell that
sells continuations fails no matter what its ΔR says. If this study cannot
distinguish itself from Attempt 1 by that measurement, it has no claim to be a
different study.

---

### Population and basis, fixed here

- Era: PRIMARY `--era v3` — `load_book(include_bs=False)`, proxy calibration
  gate ON, the 795-row / 118-date basis. SECONDARY = `current` (v4), reported
  only, carries nothing (34 backfill dates; most cells will power-stop).
  **Never pooled.**
- Population per grid point X = rows whose SHIPPED replay survives past session
  X (`days_held > X`). A row that already exited on or before X is untouched by
  every arm and is excluded from the paired test at that X — including it is
  the zero-inflation that failed `exit_switch_mech`'s LOO median gate.
- Plan-time power measurement (disclosed), measured while designing:
  **513 rows / 114 dates survive past session 5; 415 / 110 past session 10;
  333 / 109 past session 15; 265 / 102 past session 20.** Every X in the frozen
  grid clears the 25-date floor on the whole book — the floor will bite on
  sub-cells, not on the headline. **Wording note (2026-08-19, at build
  time):** these disclosed figures reproduce EXACTLY on the DEBIT slice of the
  book (593 of 795 rows) — they were measured there and mislabelled as the
  whole book. The registered POPULATION WORDING is unrestricted (credits
  included, priced under CREDIT_PROD), and that wording governs: the build
  implements it and G0 prints debit and credit columns side by side with a
  reconciliation paragraph (whole-book survivors: 702/118, 583/117, 473/116,
  385/111). No population, threshold, or criterion changed — only the label on
  a disclosed number. Two consequences follow, both implied by the registered
  grid applied to the registered population: ARM T's "tighten stop to −0.40"
  INTRODUCES a stop on credit rows (whose shipped profile is sl-none since
  Attempt 13) — that is the registered action, disclosed next to the
  credit-ungated caveat; and the trail action is near-inert on this book (all
  32 trail cells power-stop at the pre-declared floor), so ARM T's transfer
  test is effectively carried by the tighten-stop action.
- Comparison is ALWAYS paired against the **SHIPPED book** — the production
  profiles via `bear_giveback.prod_profile_for`, including the bear-keyed
  variants — **never against a clean `DEBIT_PROD` baseline.** Comparing against
  clean `DEBIT_PROD` changed a decision twice in this repo's history; it
  measures the shipped profile's own value, not the staged switch's.

### Arms — frozen at two, no additions

**ARM E — terminal "exit now."** Pure composition around the FROZEN
`harness.replay` (the `next_day_move` precedent): replay the shipped profile
untouched; then, if `days_held > X` and the band condition holds at
`pnl_of(marks[X-1])`, override the result to `(staged_exit, X, that pnl)`. No
fork, no copy, no edit to `harness.py`. ARM E is the arm that can be trusted
without a machinery gate, and it is the arm the headline is read from.

**ARM T — tighten / arm-trail.** `harness.replay` is COPIED into the study
module as `replay_staged(t, stage1, stage2, switch_day)` — loop body verbatim,
the profile swapped at `i >= switch_day`, the peak carried ACROSS the swap. The
harness docstring mandates copy-not-edit and this is a copy; `harness.py` is
not modified.

- **G-FORK (registered here, before the copy exists).** With
  `stage1 == stage2` the fork must reproduce `harness.replay` EXACTLY —
  `(exit_reason, days_held, round(pnl, 10))` — on **all 795 rows at every grid
  value of X**, AND on the full `tests/test_harness_replay.py` fixture. **One
  disagreement fails the run.** A forked replay that has drifted from the frozen
  engine is not a finding about exits; it is a finding about the fork.

Frozen grid — declared now, not swept after a result is seen:

| dimension | values |
|---|---|
| switch session **X** | 5, 10, 15, 20 |
| profit condition | R ≥ +0.50 · R ≥ +0.25 |
| loss condition | R ≤ −0.25 · R ≤ −0.50 |
| parallel dollar cut | ±$250 · ±$500 (via `t.dollars`, same grid, reported alongside R) |
| ARM T action | tighten stop to **−0.40** · arm trail **0.50 / 0.50** |
| else-branch | **always "continue shipped profile"** — no arm has a third outcome |

The ARM T action values are the **shipped `BEAR_HE` values**, used unchanged.
This is a TRANSFER test of an already-deployed setting to a new trigger, not a
new knob: no stop, trail-arm or trail-give value is searched, and none may be
moved after a cell is read.

### Unit and metric

Unit = the signal **DATE** (date-clustered everything). Metric = **within-row
paired ΔR** (staged minus shipped) on the rows the population defines at that
X, aggregated by date via `boot_ci_paired_by_date`. Dollars print alongside
from the parallel `t.dollars` cut as a sanity read; contract counts are
IDENTICAL across arms here (nothing is re-sized), so $ is admissible — but R is
what is quoted in every conclusion.

### Gates (non-zero exit on failure, in order)

- **G0 — POWER, runs FIRST and blocks everything.** Per (arm × X × condition)
  cell: affected rows and affected DATES. **< 25 affected dates OR < 60 affected
  rows → that cell is POWER-STOPPED**, printed with its n, no criterion
  evaluated on it. Declared before the counts are known.
- **G1 — leak guard.** A staged arm must change **ZERO rows outside its
  population**: every row with `days_held <= X` under the shipped profile must
  come back byte-identical `(exit_reason, days_held, round(pnl, 10))`. A single
  changed row means the switch is firing where it was never registered to, and
  fails the run.
- **G-FORK (ARM T only)** — as specified above; exact reproduction at
  `stage1 == stage2` on all 795 rows at every X and on the harness fixture.
- **G2 — CONTINUATION DIAGNOSTIC, AS A PASS CRITERION.** For every cell, compute
  for each staged exit the post-exit path maximum over the remainder of the
  row's own grid. **A cell whose staged exits are MAJORITY followed by a
  post-exit path max > realized + 0.30 R FAILS — regardless of ΔR, CI, LOO or
  any other number.** This is the measurement that separates this study from
  Attempt 1, and it is registered as binding before any cell is computed.

### Bar for a candidate — the full conjunction, all of it

1. paired ΔR > 0 vs the SHIPPED book with **date-clustered bootstrap CI
   excluding zero** (`BOOT_N = 10000`, α = .05);
2. **every** LOO fold positive (read `min_gain`);
3. survives `protocol.window_cuts` **AND the ex-BOTH-windows cut added by
   hand** — `window_cuts()` drops only one window at a time, and the vol_sleeve
   straddle died precisely in the gap that leaves;
4. **positive in every calendar year present** in the cell's population
   (`sign_stable`);
5. right-signed on **BOTH pricing tiers** (real and tweak);
6. ≥ 25 affected dates and ≥ 60 affected rows (G0's floor, re-checked on the
   evaluated set);
7. **passes G2** — the staged exits are NOT majority continuation sales.

Failing any one is failing. Worst-decile cells print **DESCRIPTIVELY** with
their n and are marked **NOT A CRITERION** — 118 dates cannot power a
worst-decile read (the 2026-08-13 nine-date decile wall), and no criterion here
requires one.

### Verdicts, worded now

- **CANDIDATE** (not a ship): a cell clears all seven → queued for an
  independent-window confirmation before it may be proposed for
  `deployment-rules.md`. Nothing ships from a research-tier study.
- **REACTIVE-AGAIN**: a cell clears the R conjunction but FAILS G2 → the staged
  switch is selling continuations exactly as the three trail attempts did; the
  time-staging did not buy immunity from the reactive failure. Recorded in full,
  thread closed for these dates. This is the outcome the prior evidence
  predicts, and naming it now is the point of registering G2 as a criterion.
- **NULL**: cells clear the CI but fail LOO / ex-BOTH / sign stability → window
  artifact, recorded (the `bear_rewrap` +0.085 outcome).
- **POWER-STOPPED**: G0 fails for a cell → census published for it, nothing
  read, no re-run on these dates.

### Anti-tuning

X frozen at four values, conditions at four, actions at two, else-branch at one.
Exit profiles other than the two registered ARM T actions are NOT swept; the
sizing formula, caps, candidate population and entry side are NOT swept. No
threshold is moved and no cell is added after any number is seen. **Every cell
in the grid is reported regardless of outcome**, including the ones that lose
and the ones that power-stop.

### Build notes (not part of the registration)

- Module `scripts/backtest_study/f2_management/staged_exit.py`; run via
  `python -m scripts.backtest_study run staged_exit --era v3`; report to
  `backtests/study_output/staged_exit-latest.txt`.
- `lib/harness.py` is **NOT touched.** `replay_staged` is a deliberate local
  copy inside the study module, gated by G-FORK; it is not promoted to `lib/`.
- `tests/test_staged_exit.py` must exist and must parametrise the G-FORK
  equivalence over the existing `test_harness_replay.py` fixture **before ARM T
  is trusted**.
- A `scripts/study_map/catalog.py` entry with a hand-written VERDICT is
  REQUIRED — a study with no entry fails the test suite — plus a
  `research/study-map.md` prose mention (test-enforced).
- Every report prints `debit_calib`, `n_credit_ungated` and the credit-ungated
  caveat. No annualised figure, Sharpe, or time-to-recover anywhere.
