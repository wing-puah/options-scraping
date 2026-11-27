## tier_contrast_forward — does the tier gate select, on dates no one has seen

<!-- outcome:start -->
> Latest outcome: built 2026-11-28; first run `STILL-OPEN`. No forward row has loaded yet, so both arms hold 0 closed positions — 2026-11-28 · [record](../../study-results/f4_deployment/tier_contrast_forward.md).
<!-- outcome:end -->

_Registered 2026-11-28._

**STATUS: ACCEPTED BY DEFAULT 2026-11-28 on the drafter's recommended
defaults. Second read done 2026-11-28, before the build and before any outcome.**
Its rulings are tagged `Resolved at second read (2026-11-28)` beside the rules they
amend. A revisit after a result is a NEW registration, never an edit.

## The question

On signal dates after 2026-11-27, do Tier A and Tier B plays earn more [R](../../glossary.md#r) per position than Tier C plays?

The deploy ladder takes Tier A and Tier B and refuses Tier C ([`docs/deployment-rules.md`](../../../docs/deployment-rules.md) §1 to §3 and §7.1). That refusal is a claim that the gate SELECTS. On v4 no graded test of that claim exists:

- `v4_bridge` prints `LADDER UNVALIDATED`.
- [`holdout_seal`](holdout_seal.md) graded Tier A and Tier B against zero only. Its one read was `UNDERPOWERED`.
- `regime_map` tests each cell against zero. A 2026-11-28 check showed its eight NEGATIVE Tier C cells restate "Tier C loses" ([entry](../../current.md#regime_map-against-uninformative-labels-the-cells-show-the-tier-not-the-regime)).

The in-sample tier means are now printed, so any in-sample contrast would be graded after a look. The only clean test is forward. This file fixes that test.

## What this study is not

- It is not a test against zero. "Tier A+B made money" can mean the market rose. A contrast on the same dates removes market direction, so it asks only whether the gate picks the better plays.
- It does not grade Tier A against Tier B, the ladder's ranking, `top_k`, sizing or exits.
- It does not grade the deployed set. It grades every closed v4 row the gate would take or refuse.
- It cannot change a live rule. See [What could ship](#what-could-ship).

## Definitions

- **Tier.** The value `ladder_tier()` in `scripts/journal/lib/mapping.py` returns, through the `book_tier()` adapter in `scripts/backtest_study/lib/book.py`. The module never re-derives a tier.
- **What the tier reads.** Four fields: the structure, the analysis `market_regime` of the signal date, `dte_entry` and the entry-day `delta`. Each is fixed by the entry close at the latest. None comes from the holding path or the exit. _Resolved at second read (2026-11-28): the draft said "the fields the analysis row held"; two of the four come from the backtest row's entry day._
- **Arm AB.** Rows whose tier is `A` or `B`.
- **Arm C.** Rows whose tier is `C`.
- **Position.** One `BacktestResults` row. A play is backtested once per results tab, so one row is one position.
- **Closed.** Not pending under `is_pending()` in `lib/book.py` at the export's as-of date. A row marked `open_at_data_end` after its window ends counts as closed, and its count per arm is printed. _Resolved at second read (2026-11-28): the draft named a `path_status` value the book does not use._
- **The contrast.** Mean R of arm AB minus mean R of arm C, over the graded window.
- **The graded window.** Defined in [Population and basis](#population-and-basis-fixed-here). It is fixed by the floors, not by the run date.

## Dependencies

- The analysis pipeline keeps emitting v4 plays. The operator may stop it in the move to a mechanical book. Then the read lapses and says so.
- The backtest keeps pricing those plays into the v4 `BacktestResults` tab.
- The module `scripts/backtest_study/f4_deployment/tier_contrast_forward.py` is OWED. It must be built and its tests must pass before the first forward row can close. No outcome can exist before the build.

## Population and basis, fixed here

- **Export.** The v4 `BacktestResults` export, through `load_book`, era-scoped, `include_bs=False`. Pricing tiers real and `strike_expiry_tweak` only.
- **Dates.** Signal date on or after 2026-11-28. Every row dated 2026-11-27 or earlier is out.
- **Era.** The module sets `STUDY_ERA = "v4"` and refuses a mismatched export, as its siblings do. `--era v3` is refused, because v3 has no forward dates.
- **Vetoed rows.** Out of both arms. Their count is printed.
- **Proxy rows.** `BacktestProxy` rows are out of the primary. Their per-tier counts and the same contrast are printed separately and never graded.
- **Complete prefix.** The forward dates before the first date that still holds a pending A, B or C row. Only prefix rows count.
- **The graded window ends at D\*.** D\* is the earliest prefix date at which both floors hold. A later run date never moves D\*.
- **Why the prefix.** Every row on a prefix date is closed. So the sample cannot lean toward short holds, and pending rows cannot choose it. A run date only decides how far the prefix reaches, never which rows on a date count.
- **Its limit.** One long-dated pending row stalls the prefix until its window ends. That delays the read but does not bias it. The `STILL-OPEN` line names the date of the pending row that ends the prefix, so a stall is visible. _Resolved at second read (2026-11-28)._
- **Sunset cut.** Floors count only signal dates on or before 2028-11-27. A run after that date still fires if D\* falls inside it. _Resolved at second read (2026-11-28): the draft tied the sunset to the run date._

_Floors._ Each arm needs at least **377 closed positions** on at least **120 signal dates** inside the prefix. _Resolved at second read (2026-11-28): the draft's 60 on 30 detected only about 0.51 R, so the one read would almost surely have printed `UNDERPOWERED-BY-DESIGN`. The derivation is in [Power](#power-fixed-now)._

## Plan-time observations, disclosed

- The drafter has seen the in-sample tier means on the 2026-11-27 book, below ([entry](../../current.md#regime_map-against-uninformative-labels-the-cells-show-the-tier-not-the-regime)). §7.1 of the deploy rules prints similar figures.

| Tier | Mean R, 2026-11-27 book | Rows |
|---|---|---|
| A | +0.081 | 207 |
| B | +0.063 | 538 |
| C | -0.115 | 1,052 |
| A+B | +0.068 | 745 |

- Those means are why the forward test is the only clean one. They are not used as a target anywhere below.
- No row dated after 2026-11-27 was read, counted or priced for this file.
- The `holdout_seal` lifted on 2026-11-26, so no seal binds these dates.
- In-sample, Tier C had more rows per signal date than Tier A and B together. The floors should bind on arm AB first.
- The second reader read the same table and the row and date counts. The floors and the reference use counts and spread only, never the means.

## What it compares

| Arm | Rows | Role |
|---|---|---|
| AB | Tier A or B, closed, in the graded window | Taken by the gate |
| C | Tier C, closed, in the graded window | Refused by the gate |

### AB

Every row the ladder would take, before `top_k`, sizing or book checks.

### C

Every row the ladder would refuse for its tier. Vetoed rows are not Tier C.

## How it is judged

**One graded test.** The contrast, with a date-clustered bootstrap. There is no multiplicity.

- **Bootstrap.** Resample signal dates with replacement, 10,000 draws. Each drawn date brings all its AB and C rows. The resampling unit is the date, as in `regime_map`'s `cell_stats`.
- **p-value.** Two-sided: twice the smaller of the shares of draws at or below 0 and at or above 0, capped at 1.
- **Pass.** Contrast above 0 with p < 0.05.

**Printed, never graded:**

1. A minus C, and B minus C, each with its interval.
2. Each tier's mean R against zero, with its interval.
3. The contrast with exit marks capped inside the closing quote ([the exit-mark finding](../../current.md#capped-exit-marks-and-the-live-candidates-selection_order-o3-does-not-survive)).
4. The within-date contrast: for each date with both arms, that date's AB mean minus its C mean; then the mean over those dates, with a date bootstrap. This is the robustness line. If its sign differs from the graded contrast, the report says so in one line.
5. Rows and dates per tier, vetoed rows, and proxy rows.
6. The option-cache state at the run (check 12 below).

## Power, fixed now

The power is set from in-sample dispersion only. The in-sample contrast is not a target.

- **Dispersion.** The 2026-11-27 date-clustered intervals imply a per-row R standard deviation near 1.0, if rows were independent. A+B: half-width 0.079 on 745 rows gives about 1.10. C: half-width 0.056 on 1,052 rows gives about 0.92. The frozen value is **σ = 1.0 R**.
- **Detectable effect.** The test runs at 80% power and two-sided 0.05. Then MDE = 2.80 × σ × √(DE × (1/n_AB + 1/n_C)).
- **Design effect: DE = 1.5.** Rows on one date share a market. In-sample, arm AB had about 3.2 rows per date (745 on 236). DE = 1.5 allows a within-date correlation near 0.23 at that size. The σ above already comes from date-clustered intervals, so 1.5 is a margin on top, on the safe side.
- **Reference effect: 0.25 R.** R is the return on the entry premium. A gate that refuses more than half the tiered plays has to earn its keep per position. At the operator's $1,000 stop, 0.25 R is about $250 a position. A smaller edge is not worth a rule that halves the play count. The reference is fixed on that ground, not on any observed contrast. _Resolved at second read (2026-11-28): the draft called 0.25 R "a quarter of the stop"; R is a return on premium, not on the stop._
- **The floor that follows.** The standard two-sample formula gives the positions per arm. The date floor keeps rows per date near the in-sample size that DE assumes.

| Term | Value |
|---|---|
| Formula | n = DE × 2 × (z₀.₉₇₅ + z₀.₈)² × σ² / Δ² |
| (z₀.₉₇₅ + z₀.₈)² | (1.96 + 0.84)² = 7.85 |
| σ, Δ, DE | 1.0 R, 0.25 R, 1.5 |
| n per arm | 376.8, rounded up to **377** |
| Dates per arm | **120**, so about 3.1 rows per date |
- **Time to fire.** In-sample, arm AB had about 2.65 rows per signal date (745 over about 281 tiered dates). 377 AB rows then need about 142 signal dates. With one signal date per trading day, that is about late June 2027. Closing the last windows adds about two to three months, so the read should fire near September 2027. Arm C (about 3.7 rows per date) fills first.
- **Sunset check.** At half that accrual the read fires near spring 2028. The sunset of 2028-11-27 leaves room, so it stays.
- **Realized MDE.** At the read, MDE = 2.80 × the bootstrap standard error of the contrast. It uses the realized spread and clustering, not σ. If the spread is wider than assumed, MDE exceeds 0.25 R and the word is `UNDERPOWERED-BY-DESIGN`. _Resolved at second read (2026-11-28): the draft computed MDE from the frozen σ, so a wider realized spread could never print that word._

The module prints the planning MDE and the realized MDE beside the verdict.

## Gates

On the firing run, in order. A failed gate prints `REFUSED (gate)` and writes no forward-read file. The next run retries on the same window, because D\* does not move.

- **G1 era.** The export is v4. `STUDY_ERA` matches.
- **G2 calibration.** Before the read, shuffle tier labels across rows within each date, among that date's AB and C rows. Run the full bootstrap test on 500 shuffles. Print the share with p < 0.05. If it exceeds **0.075** (1.5 times nominal), the bootstrap is too liberal on this data.
- **G2 fallback.** Then the graded p-value is the within-date permutation p-value instead: 10,000 such shuffles, two-sided, the share with an absolute contrast at or above the observed one. The read still fires, and the report names the fallback. _Resolved at second read (2026-11-28): the draft refused and said "fix and rerun", but nothing could be fixed on true data, so the read would stall for ever._
- **Why the shuffle is a fair null.** It keeps each date's rows, R values and arm sizes, and breaks only the link between tier and R. Under it the contrast is zero by construction. At 500 shuffles the rate's standard error is about 0.010. So a correctly sized test almost never trips the bound.
- **Seeds and prints.** All draws use seeds fixed in the module. A refused run prints the failed gate and its own figure only, never a contrast, mean or p-value. So a refusal leaks nothing about the result. _Resolved at second read (2026-11-28)._
- **G3 window.** Every graded row is closed and dated 2026-11-28 to D\*. Each row's tier comes from `ladder_tier()`.
- **G4 cache.** The option-cache state is recorded in the report. A missing record refuses.

## The read, one shot

- Before the floors hold, the run prints `STILL-OPEN` and counts only: rows and dates per arm in the prefix. No mean, interval or p-value prints.
- The read fires ONCE, on the first run at which both floors hold and the gates pass.
- It is stored in `backtests/study_output/tier_contrast_forward-forward-read.json`, with the row identity keys, D\*, each R, and every printed figure. The output cleaner pins this file.
- Every later run prints that file and regrades nothing.
- **Look log.** Every run, before or after the read, appends one line to `backtests/study_output/tier_contrast_forward-looks.jsonl`: run date, prefix end, counts per arm, and the token printed. Peeks stay visible.
- **Sunset 2028-11-27.** If no D\* exists on signal dates up to then, once every forward row dated to then has closed, the word is `LAPSED`.
- **Pipeline stop.** If v4 plays stop being emitted, and the floors still fail once every v4 row has closed, the word is `LAPSED`, with the reason.
- **Peeks elsewhere.** Other modules, such as `regime_map` and `v4_bridge`, may print v4 tier means that include forward dates. Such a print is a peek this file cannot log. It cannot move the result, because the floors, D\*, the statistic and the words are fixed here. Any change after such a peek is a new registration. _Resolved at second read (2026-11-28)._

## Verdicts, worded now

Once a read is stored, every run prints its stored token and nothing below applies. Before that, first match wins. The list is exhaustive. _Resolved at second read (2026-11-28): the draft's `STILL-OPEN` and `LAPSED` rows left a gap after a pipeline stop with rows still pending, and disagreed with the pipeline-stop rule._

| Token | When | What it triggers |
|---|---|---|
| `REFUSED (gate)` | G1, G3 or G4 fails | Fix and rerun. No read is stored |
| `STILL-OPEN` | No D\* yet, and a forward row dated on or before 2028-11-27 is pending or may still be emitted | Counts only |
| `LAPSED` | No D\* yet, no such row is pending, and the sunset has passed or v4 emission has stopped | The gate stays ungraded on v4. Recorded as such |
| `GATE-SELECTS` | Contrast above 0, p < 0.05 | First forward evidence that the gate selects. Independent review before it is cited |
| `GATE-INVERTED` | Contrast below 0, p < 0.05 | Tier C beat A+B. Flagged to the operator at once |
| `UNDERPOWERED-BY-DESIGN` | Neither of the above, and realized MDE > 0.25 R | Prints "could not see one". It never reads as no effect |
| `NULL` | Neither of the above, and realized MDE ≤ 0.25 R | No contrast of the reference size. Flagged to the operator |

## Design checks, answered

1. **Benchmark at the rule's own exposure.** Not applicable. Both arms are per-position mean R on the same dates. Neither holds less.
2. **Drawdown test power.** Not applicable. There is no drawdown test.
3. **Calibration.** Gate G2: within-date label shuffles, 1.5 times nominal. If it trips, the permutation p-value grades instead.
4. **Power and an underpowered word.** σ = 1.0 R, DE 1.5, reference 0.25 R. The floor gives 80% power at the reference. A wider realized spread prints `UNDERPOWERED-BY-DESIGN`.
5. **Fallback block.** None. The unit is the signal date and there is no fallback.
6. **PBO ranking.** Not applicable. One fixed contrast, nothing picked from many.
7. **Base rates beside count tables.** No count table is graded. Per-tier counts are census only.
8. **Every date fixed.** The window starts 2026-11-28 and ends at D\*, the earliest prefix date meeting the floors. The run date never changes it. The sunset cuts signal dates, not run dates.
9. **Clean of the idea's source.** The idea and the tier means come from the book through 2026-11-27. Every graded date is later.
10. **Data gates.** G1, G3 and G4 check era, window and cache. None tests a feed against itself, and none refuses a true outcome. G2 no longer refuses; it switches the p-value.
11. **Mutation tests.** Listed in [Required mechanics tests](#required-mechanics-tests).
12. **Cache state and exit marks.** G4 records the cache. Printed figure 3 caps exit marks inside the closing quote.
13. **Independent review.** A `GATE-SELECTS` is reviewed before it is cited: the headline rebuilt without the module's functions, and the module run on data with no effect.

## Required mechanics tests

Each test must fail under the named one-step change.

| Test | Mutation it must fail under |
|---|---|
| Tier comes from `ladder_tier()` | The module recomputes the tier from score fields |
| Rows dated on or before 2026-11-27 are out | The date filter becomes `>= 2026-11-27`, or is removed |
| The bootstrap resamples dates | It resamples rows instead |
| Sign of the contrast, on a planted +0.5 R AB effect | The contrast is computed as C minus AB |
| One-shot rule: a second run after the read prints the stored file | The second run recomputes from the export |
| Floor: 376 AB positions, or 119 AB dates, prints `STILL-OPEN` | The floor check uses `>` 376 on rows only, or drops the date floor |
| D\* is the earliest prefix date meeting the floors | D\* is the run date's prefix end |
| A pending row ends the prefix | Pending rows are dropped and later dates still count |
| Calibration shuffles within date | The shuffle runs across the whole window |
| G2 fallback grades by permutation p-value | A tripped G2 refuses, or keeps the bootstrap p-value |
| Realized MDE comes from the bootstrap standard error | It comes from the frozen σ |
| A refused run prints no contrast | The refused run prints the contrast |
| Vetoed rows are in neither arm | Vetoed rows join arm C |

## Anti-tuning

- The floors, σ, DE, the reference effect, the 0.075 bound and the sunset are fixed now. None moves because the early counts look good or bad.
- The graded window ends at D\*. It is never extended to make a result readable.
- The printed figures are not graded after the run. No cut by regime, structure, DTE or year is added.
- A or B against C, the capped-mark contrast and the within-date contrast never replace the graded contrast.
- The read is not repeated. A second look is a new registration on new dates.

## What could ship

Nothing ships from this study under any outcome. No live rule changes.

- `GATE-SELECTS` records the first forward support for the gate.
- `GATE-INVERTED` or `NULL` is a flag for the operator. Changing `docs/deployment-rules.md` is the operator's call.
- `UNDERPOWERED-BY-DESIGN` and `LAPSED` leave the gate where it is today: unvalidated on v4.
