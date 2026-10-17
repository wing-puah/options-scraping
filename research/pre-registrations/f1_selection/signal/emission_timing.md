## emission_timing — does entry timing relative to the signal degrade a play?

<!-- outcome:start -->
> Latest outcome: no PRIMARY v3 verdict is recorded. On v4, which is not PRIMARY: `ARM P` `NULL`; `ARM L` `LAG-TOLERANT` — 2026-09-28. The same report also prints `CANDIDATE` cells under those verdicts: `ARM P` repeats against the play, and `ARM L` low-tercile lags · [record](../../../study-results/f1_selection/signal/emission_timing.md).
<!-- outcome:end -->

_Registered 2026-08-19._

## The question

Does the TIMING of an entry relative to the signal degrade it? Two arms share one theme.

- **ARM P (persistence):** does a re-emitted play perform worse (the signal is stale, the move already happened) or better (confirmation)?
- **ARM L (fill lag):** does an entry filled 1, 2 or 3 sessions after the signal lose the edge?

These are entry-timing questions, not selection-rule questions. No arm changes which structures are eligible or how they are exited.

### Admissibility, stated FIRST

Selection is CLOSED in this repo. Structure × regime × entry geometry is settled, `score_total` is decision-irrelevant, and the ML search was null across 15 cells. It reopens on **NEW COLUMNS ONLY.**

This study is admissible because it introduces two new columns:

- the **emission ordinal**: is this the first time this (ticker, structure) has been emitted, or a repeat?
- the **pre-signal price_vector**: where the underlying had already travelled BEFORE the signal.

Both are computable from the era book and the cached bars. Both are **observable at entry**: an operator could read either at the moment of the decision.

## What this study is not

- **Not a re-test of the day-0 underlying move.** That column is not admissible and no arm re-tests it. `next_day_move` ARM C already tested it, and that result stands. **Gate G3 enforces this by assertion**: no arm may construct a feature from the signal day's own underlying move, and the run fails if one does.
- **Not an exit study.** Shipped profiles are used throughout, replayed by the FROZEN `harness.replay`.
- **Not a sizing study.** Contracts are re-sized by the production formula so the lag is not confounded with size, and G2 forbids quoting dollars across lags.
- **Not a test of intraday entry timing.** Daily marks cannot represent a fill inside the session. Nothing in this study may be read as evidence about intraday entry timing.

## Population and basis, fixed here

One era carries the study. The other is reported and carries nothing.

| Fixed | Value |
|---|---|
| PRIMARY era | `--era v3`: `load_book(include_bs=False)`, proxy calibration gate ON, the 795-row / 118-date basis |
| SECONDARY era | `current` (v4): reported only, carries nothing (34 backfill dates; most cells will power-stop) |
| Pooling | **Never pooled** |
| Underlying bars | `underlying.load_bars` |

Wherever a cut uses bars, the **SRC_OHLC / SRC_TILDE split is PRINTED** and the two sources are never pooled silently. A tilde-sourced move is a different measurement from a real bar.

## What it compares

Two arms, one theme, plus a conditioning cut on the lag ladder.

| Object | What it does | Kind |
|---|---|---|
| [emission_timing ARM P](../../../arm-index.md#emission_timing-arm-p) | Compares repeat emissions with the first emission of the same (ticker, structure). The ordinal is capped at {1st, 2nd, 3rd, 4th+} | arm |
| [emission_timing ARM L](../../../arm-index.md#emission_timing) | Builds a synthetic trade for each lag L ∈ {0, 1, 2, 3} sessions after the signal. Each lag is compared with L = 0 | arm |
| Conditioning cut | Reports the lag ladder within pre-signal `price_vector` terciles | cut |

### ARM P — emission persistence

- **First emission** is the earliest date per **(ticker, structure)** in the era book. The ordinal is capped at **{1st, 2nd, 3rd, 4th+}**. Plan-time counts (disclosed, measured while designing): **210 / 100 / 78 / 407.**
- **Join convention, frozen:** `book.py`'s `created_datetime`-sorted keep-first rule. Same-day duplicate emissions collapse to one and **cannot fake a repeat**. Without this rule, a single session's duplicate rows would manufacture the entire effect.
- **The test is WITHIN-DATE PAIRED**, the `hedge_sizing` D4 method, because it cancels the date's own return level. Plan-time measurement (disclosed): **82 of 118 dates carry BOTH a first and a repeat emission.**
- The estimand is the paired **Δ(mean R), repeat minus first, computed inside each date**. It is aggregated by `boot_ci_paired_by_date`.

**Two frozen sub-cuts, declared now. No third cut is added after any number is seen.**

1. **Consecutive-date repeats versus gapped ones.** A repeat the next session is a different object from a repeat three weeks later. Frozen definition of consecutive: "previous emission fell on the immediately preceding date present in the era book". The book is the session calendar, and the repo has no holiday calendar. This gives **151 rows**. The stricter calendar-next-weekday diagnostic, 106, prints alongside.
2. **Repeats split by whether the underlying had already moved the play's way** since the first emission (`underlying.load_bars`; SRC_OHLC / SRC_TILDE split printed, never pooled). This states the "the move already happened" hypothesis as a measurable cut.

### ARM L — signal-to-fill lag

**Construction.** A synthetic `Trade` is built per lag **L ∈ {0, 1, 2, 3}**, anchored at `grid[L-1]`.

- `signal_date` ← `grid[L-1]`.
- Entry ← `marks[L]`.
- `dte_entry` is reduced by the calendar days the anchor moved (0 at L=0).
- `daily_price_csv` ← `marks[L:]`, **right-padded with blanks** to the recomputed grid length.
- Contracts are **re-sized by the production formula** at the lagged entry price. Tests pin this.

The anchor is `grid[L-1]` because the harness grid is weekdays AFTER `signal_date`, so `grid[0]` is already the fill session. At L=0 the anchor is the ORIGINAL `signal_date`. This lines up `entry ← marks[L]`, `daily_price_csv ← marks[L:]` and the padding. L=0 then reproduces the stored trade exactly except for the fill price, which is what "L=0 is the baseline" requires.

**Padding.** The padding decision is registered with its measurement (disclosed): **262 / 795 rows are 120-day cap-truncated.** Right-padding is behaviour-neutral, because the shipped profiles cannot fire on a blank mark. DROPPING the truncated rows would bias the population toward short-dated trades, the population the lag question is most sensitive to. **The padded-row count PRINTS in every report.**

**Baseline.** **L = 0 is the BASELINE for every lag comparison.** L = 0 is a day-0 **CLOSE** fill, built the same way as L = 1..3. The close-vs-open basis change therefore **cancels** and the estimand is **lag-only**. The **stored book** prints alongside as a REFERENCE line only; it is not the comparator. The recorded prior finding that the **overnight gap ≈ 0** on this book is quoted there, so a reader can see why the two are close without the study leaning on it.

**Coverage** (disclosed plan-time measurement): **794 / 795 rows price at lag 1; 795 / 795 at lags 2 and 3.**

**Degenerate entries.** Lag priceability excludes `marks[L] == 0.0` (R denominator explosion) in addition to `None`. These are 5 rows, counted as `degenerate_zero_entry` and never silently dropped.

### Conditioning — the pre-signal price_vector

The lag ladder is ALSO reported **within pre-signal `price_vector` terciles**.

- Coverage, disclosed: the plan-time 785/795 measured JOIN failure only (10 rows). A further 63 rows join but carry a blank `price_vector` cell. The true conditioned population is **722 / 795 rows populated**.
- All 73 unpopulated rows form the **MISSING cell**. It is reported, never imputed and never folded into a tercile. It power-stops at 16 dates.
- Terciles are cut on the **FULL book** and **FROZEN** before any lag result is read. They are not re-cut per lag, which would make the cells move under the comparison.
- **NaN-tercile trap, noted here because it has bitten before:** a NaN sorts into a tercile edge silently. The filter is `v == v` on the raw value, applied before the cut. The excluded count prints.

## How it is judged

**Unit.** The unit is the signal **DATE**. Everything is date-clustered.

| Arm | Metric |
|---|---|
| ARM P | Within-date paired Δ(mean R), repeat − first |
| ARM L | Within-row paired [ΔR](../../../glossary.md#r) against the L = 0 baseline, aggregated by date |

Both run through `boot_ci_paired_by_date`, `BOOT_N = 10000`, α = .05.

**R is quoted, never dollars**, across lags or ordinals. Contract counts differ by construction once the entry price moves.

## Gates

Each gate exits non-zero on failure. The gates run in this order.

- **G0 — POWER. Runs FIRST and blocks everything.** At least **25 affected DATES** per cell. **The per-tercile lag cells must clear the floor INDIVIDUALLY.** A pooled pass does not license a tercile read. A cell under the floor is POWER-STOPPED, printed with its n, and no criterion is evaluated on it. Said plainly now, before any count: **this is the likeliest stop for this study**, because a 3-lag × 3-tercile grid divides 118 dates nine ways.
- **G1 — construction.** For every synthetic `Trade`, `len(marks) == len(grid)`. **Any Trade construction failure FAILS the run.** A silently dropped row would make the lag ladder a comparison between different populations. The padded-row count prints here.
- **G2 — sizing census.** The contract-count distribution per lag is printed. **No dollar figure is quoted across lags** anywhere in the study or the write-up.
- **G3 — no-day-0-move assertion.** This is an assertion, not a convention. No arm may read the signal day's own underlying move, and the run fails if one does. `next_day_move` ARM C stands and is not re-tested.

## Bar for a candidate

A cell is a CANDIDATE only if it clears the full conjunction, all of it. Failing any one clause is failing.

1. The paired ΔR **date-clustered bootstrap CI excludes zero** (`BOOT_N = 10000`, α = .05).
2. **Every** leave-one-date-out (LOO) fold is positive (read `min_gain`).
3. The cell survives `protocol.window_cuts` **AND the ex-BOTH-windows cut added by hand**. `window_cuts()` drops only one window at a time, and the vol_sleeve straddle died precisely in the gap that leaves.
4. The cell is **positive in every calendar year present** in its population (`sign_stable`).
5. The cell is right-signed on **BOTH pricing tiers** (real and tweak).
6. The cell has at least 25 affected dates (G0's floor, re-checked on the evaluated set).

Worst-decile cells print **DESCRIPTIVELY** with their n and are marked **NOT A CRITERION**. 118 dates cannot power a worst-decile read (the 2026-08-13 nine-date decile wall), and no criterion here requires one.

## Verdicts, worded now

| Token | When | Consequence |
|---|---|---|
| `STALE-ENTRY-PENALTY` | Repeats and/or lagged fills are reliably worse under the full conjunction | A candidate, NOT a ship. It proposes a candidate INTAKE rule (prefer first emissions, fill same session), queued for an independent-window confirmation before it may reach `deployment-rules.md` |
| `LAG-TOLERANT` | No lag in {1, 2, 3} separates from L = 0 under the conjunction | **The signal does not decay within three sessions.** A publishable operational finding, not a null: a missed same-day fill is not a lost trade. It is recorded as a finding in its own right |
| `LAG-SENSITIVE` | The ladder degrades monotonically with L but fails the conjunction (LOO / ex-BOTH / sign stability) | Directional evidence recorded, no rule proposed |
| `NULL` | Cells clear a CI but fail the rest | Window artifact, recorded |
| `POWER-STOPPED` | G0 fails for a cell | Census published for it, nothing read, no re-run on these dates |

## Anti-tuning

Everything that could be swept is frozen.

- Lags are at four values, ordinals at four buckets, terciles at three (cut on the full book), sub-cuts at two.
- The exit profiles, sizing formula, structure universe and candidate population are NOT swept.
- No new selection column beyond the two named under "Admissibility" is introduced.

No threshold is moved and no cell is added after any number is seen. **Every cell is reported regardless of outcome**, including the ones that lose and the ones that power-stop. No annualised figure, Sharpe, or time-to-recover appears anywhere.

## What could ship

Nothing ships from this study. `STALE-ENTRY-PENALTY` would queue an intake rule, which needs an independent-window confirmation before it may reach `deployment-rules.md`. `LAG-TOLERANT` is an operator finding in its own right.
