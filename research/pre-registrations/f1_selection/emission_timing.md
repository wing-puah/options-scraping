## emission_timing — does entry timing relative to the signal degrade a play?

_Registered 2026-08-19._

**Admissibility, stated FIRST.** Selection is CLOSED in this repo — structure ×
regime × entry geometry settled, `score_total` decision-irrelevant, the ML
search null across 15 cells — and it reopens on **NEW COLUMNS ONLY.** This study
is admissible because it introduces exactly that, two of them:

- the **emission ordinal** — is this the first time this (ticker, structure) has
  been emitted, or a repeat?
- the **pre-signal price_vector** — where the underlying had already travelled
  BEFORE the signal.

Both are new, both are computable from the era book and the cached bars, and
both are **observable at entry**: an operator could read either at the moment of
the decision.

## Question

Does the TIMING of an entry relative to the signal degrade it? Two arms, one
theme.

- **ARM P (persistence):** does a re-emitted play perform worse (the signal is
  stale, the move already happened) or better (confirmation)?
- **ARM L (fill lag):** does an entry filled 1, 2 or 3 sessions after the signal
  lose the edge?

These are entry-timing questions, not selection-rule questions: no arm changes
which structures are eligible or how they are exited.

## What this is NOT

- **Not a re-test of the day-0 underlying move.** That column is not admissible
  and is not re-tested here under any arm. `next_day_move` ARM C already tested
  it and that result stands; re-testing it under a new study name would be a
  second look at a closed question. **Gate G3 enforces this by assertion**, not
  by intention — no arm may construct a feature from the signal day's own
  underlying move, and the run fails if one does.
- **Not an exit study** — shipped profiles throughout, replayed by the FROZEN
  `harness.replay`.
- **Not a sizing study** — contracts are re-sized by the production formula so
  the lag is not confounded with size, and G2 forbids quoting dollars across
  lags.

## Population and basis, fixed here

One era carries the study; the other is reported and carries nothing.

- Era: PRIMARY `--era v3` — `load_book(include_bs=False)`, proxy calibration
  gate ON, the 795-row / 118-date basis. SECONDARY = `current` (v4), reported
  only, carries nothing (34 backfill dates; most cells will power-stop).
  **Never pooled.**
- Underlying bars via `underlying.load_bars`. Wherever a cut uses bars, the
  **SRC_OHLC / SRC_TILDE split is PRINTED and the two sources are never pooled
  silently** — a tilde-sourced move is a different measurement from a real bar.

## Arms

Two arms, one theme, plus a conditioning cut on the lag ladder.

### ARM P — emission persistence

- **First emission** = the earliest date per **(ticker, structure)** in the era
  book. The ordinal is capped at **{1st, 2nd, 3rd, 4th+}**. Plan-time counts
  (disclosed, measured while designing): **210 / 100 / 78 / 407.**
- **Join convention, frozen:** `book.py`'s `created_datetime`-sorted keep-first
  rule. Same-day duplicate emissions therefore collapse to one and **cannot fake
  a repeat** — without this, a single session's duplicate rows would manufacture
  the entire effect.
- **The test is WITHIN-DATE PAIRED** — the `bear_deploy` D4 method, because it
  cancels the date's own return level, which is the dominant nuisance variable
  in this book. Plan-time measurement (disclosed): **82 of 118 dates carry BOTH
  a first and a repeat emission.** The estimand is the paired **Δ(mean R),
  repeat minus first, computed inside each date**, aggregated by
  `boot_ci_paired_by_date`.
- **Two frozen sub-cuts, declared now. No third cut is added after any number is
  seen.**
  1. **Consecutive-date repeats vs gapped ones** — a repeat the next session is
     a different object from a repeat three weeks later. Frozen definition of
     consecutive: "previous emission fell on the immediately preceding date
     present in the era book" (the book is the session calendar; the repo has no
     holiday calendar) — **151 rows**; the stricter calendar-next-weekday
     diagnostic, 106, prints alongside.
  2. **Repeats split by whether the underlying had already moved the play's
     way** since the first emission (`underlying.load_bars`; SRC_OHLC /
     SRC_TILDE split printed, never pooled). This is the "the move already
     happened" hypothesis stated as a measurable cut instead of a narrative.

### ARM L — signal-to-fill lag

- A synthetic `Trade` is constructed per lag **L ∈ {0, 1, 2, 3}**, anchored at
  `grid[L-1]`: `signal_date` ← `grid[L-1]`; entry ← `marks[L]`; `dte_entry`
  reduced by the calendar days the anchor moved (0 at L=0); `daily_price_csv` ←
  `marks[L:]`, **right-padded with blanks** to the recomputed grid length;
  contracts **re-sized by the production formula** at the lagged entry price.
  Pinned by tests.
- **Why that anchor:** the harness grid is weekdays AFTER `signal_date`, so
  `grid[0]` is already the fill session. Anchoring at `grid[L-1]` — the ORIGINAL
  `signal_date` at L=0 — lines up `entry ← marks[L]`,
  `daily_price_csv ← marks[L:]`, and the padding, and makes L=0 reproduce the
  stored trade exactly except for the fill price, which is what "L=0 is the
  baseline" requires.
- **The padding decision is registered, with its measurement (disclosed):
  262 / 795 rows are 120-day cap-truncated.** Right-padding is
  behaviour-neutral — the shipped profiles cannot fire on a blank mark — whereas
  DROPPING the truncated rows would bias the population toward short-dated
  trades, which is exactly the population the lag question is most sensitive to.
  **The padded-row count PRINTS in every report.**
- **L = 0 is the BASELINE for every lag comparison.** L = 0 is a day-0 **CLOSE**
  fill, constructed identically to L = 1..3, so the close-vs-open basis change
  **cancels** and the estimand is **lag-only**. The **stored book** prints
  alongside as a REFERENCE line only — it is not the comparator — and the
  recorded prior finding that the **overnight gap ≈ 0** on this book is quoted
  there so a reader can see why the two are close without the study leaning on
  it.
- **Intraday fills remain untestable on this data and this registration says so
  now.** Daily marks cannot represent a fill inside the session; nothing in this
  study may be read as evidence about intraday entry timing.
- Coverage (disclosed plan-time measurement): **794 / 795 rows price at lag 1;
  795 / 795 at lags 2 and 3.**
- **Degenerate entries.** Lag priceability excludes `marks[L] == 0.0` (R
  denominator explosion) in addition to `None` — 5 rows, counted as
  `degenerate_zero_entry`, never silently dropped.

### Conditioning — the pre-signal price_vector

The lag ladder is ALSO reported **within pre-signal `price_vector` terciles**.

- Coverage, disclosed: the plan-time 785/795 measured JOIN failure only (10
  rows). A further 63 rows join but carry a blank `price_vector` cell, so the
  true conditioned population is **722 / 795 rows populated**. All 73 unpopulated
  rows form the **MISSING cell**, reported, never imputed and never folded into
  a tercile — it power-stops at 16 dates.
- Terciles are cut on the **FULL book** and **FROZEN** before any lag result is
  read — not re-cut per lag, which would make the cells move under the
  comparison.
- **NaN-tercile trap, noted here because it has bitten before:** a NaN sorts
  into a tercile edge silently. The filter is `v == v` on the raw value, applied
  before the cut, and the excluded count prints.

## Unit and metric

The unit is the signal **DATE** — everything is date-clustered.

- ARM P = within-date paired Δ(mean R), repeat − first.
- ARM L = within-row paired ΔR vs the L = 0 baseline, aggregated by date.
- Both run through `boot_ci_paired_by_date`, `BOOT_N = 10000`, α = .05.

**R is quoted, never dollars**, across lags or ordinals — contract counts differ
by construction once the entry price moves.

## Gates

Each gate exits non-zero on failure, and they run in this order.

- **G0 — POWER, runs FIRST and blocks everything.** ≥ **25 affected DATES** per
  cell. **The per-tercile lag cells must clear the floor INDIVIDUALLY** — a
  pooled pass does not license a tercile read. Said plainly now, before any
  count: **this is the likeliest stop for this study**, because a 3-lag ×
  3-tercile grid divides 118 dates nine ways. A cell under the floor is
  POWER-STOPPED, printed with its n, and no criterion is evaluated on it.
- **G1 — construction.** For every synthetic `Trade`: `len(marks) == len(grid)`.
  **Any Trade construction failure FAILS the run** — a silently dropped row
  would make the lag ladder a comparison between different populations. The
  padded-row count prints here.
- **G2 — sizing census.** Contract-count distribution per lag, printed. **No
  dollar figure is quoted across lags** anywhere in the study or the write-up.
- **G3 — no-day-0-move assertion.** An assertion, not a convention: no arm may
  read the signal day's own underlying move. The run fails if one does.
  `next_day_move` ARM C stands and is not re-tested.

## Bar for a candidate

Calling a cell a CANDIDATE takes the full conjunction, all of it — failing any
one is failing:

1. paired ΔR with **date-clustered bootstrap CI excluding zero**
   (`BOOT_N = 10000`, α = .05);
2. **every** LOO fold positive (read `min_gain`);
3. survives `protocol.window_cuts` **AND the ex-BOTH-windows cut added by
   hand** — `window_cuts()` drops only one window at a time, and the vol_sleeve
   straddle died precisely in the gap that leaves;
4. **positive in every calendar year present** in the cell's population
   (`sign_stable`);
5. right-signed on **BOTH pricing tiers** (real and tweak);
6. ≥ 25 affected dates (G0's floor, re-checked on the evaluated set).

Worst-decile cells print **DESCRIPTIVELY** with their n and are marked **NOT A
CRITERION** — 118 dates cannot power a worst-decile read (the 2026-08-13
nine-date decile wall), and no criterion here requires one.

## Verdicts, worded now

- **STALE-ENTRY-PENALTY** (candidate, NOT a ship): repeats and/or lagged fills
  are reliably worse under the full conjunction → proposes a candidate INTAKE
  rule (prefer first emissions, fill same session) queued for an
  independent-window confirmation before it may reach `deployment-rules.md`.
- **LAG-TOLERANT** (publishable operational finding): no lag in {1, 2, 3}
  separates from L = 0 under the conjunction → **the signal does not decay
  within three sessions.** This is a genuinely useful operator result, not a
  null: it says a missed same-day fill is not a lost trade, and it is recorded as
  a finding in its own right.
- **LAG-SENSITIVE**: the ladder degrades monotonically with L but fails the
  conjunction (LOO / ex-BOTH / sign stability) → directional evidence recorded,
  no rule proposed.
- **NULL**: cells clear a CI but fail the rest → window artifact, recorded.
- **POWER-STOPPED**: G0 fails for a cell → census published for it, nothing
  read, no re-run on these dates.

## Anti-tuning

Everything that could be swept is frozen:

- lags at four values, ordinals at four buckets, terciles at three cut on the
  full book, sub-cuts at two;
- the exit profiles, sizing formula, structure universe and candidate population
  are NOT swept;
- no new selection column beyond the two named at the top is introduced.

No threshold is moved and no cell is added after any number is seen. **Every
cell is reported regardless of outcome**, including the ones that lose and the
ones that power-stop. No annualised figure, Sharpe, or time-to-recover anywhere.

## Build notes

*Not part of the registration — implementation record.*

- Module `scripts/backtest_study/f1_selection/emission_timing.py`; run via
  `python -m scripts.backtest_study run emission_timing --era v3`; report to
  `backtests/study_output/emission_timing-latest.txt`.
- `lib/harness.py` untouched — every synthetic replays through the frozen
  `replay`; no fork, no copy.
- `tests/test_emission_timing.py` must cover the first-emission derivation
  (including the same-day duplicate case) and the lag padding path.
- A `scripts/study_map/catalog.py` entry with a hand-written VERDICT is
  REQUIRED — a study with no entry fails the test suite — plus a
  `research/study-map.md` prose mention (test-enforced).
- Every report prints `debit_calib`, `n_credit_ungated` and the credit-ungated
  caveat.
- Sizing note recorded for the grader: contracts are re-sized by the
  production formula at EVERY lag including L=0, because the harness
  `dollar_stop` fires on a contract-dependent dollar threshold — holding the
  stored count would drift the stop's effective R with the lag and make the
  ladder a sizing artifact.
