## ticker_pattern — do the ten most-traded names carry an effect of their own?

<!-- outcome:start -->
> Latest outcome (v4, exports dated 2026-10-21, before the one-clock re-price):
> `>>> ticker_pattern P1 (omnibus, ten names, v4): TICKER-EFFECT <<<`
> `>>> ticker_pattern P2 (per-name, Holm m=10, split-half): FLAGGED GLD <<<`
> `>>> ticker_pattern PBO (CSCV, pick-the-best-name): 0.274 <<<`
> P1 p = 0.0383, printed "selection fragile". The v3 replication reads `NULL` (PBO veto 0.533) — 2026-10-23 · [record](../../../study-results/f1_selection/benchmark/ticker_pattern.md).
<!-- outcome:end -->

_Registered 2026-10-23._

## The question

Among the ten most-traded names in the backtest book, is there any per-ticker effect once the tape and the play's direction and side are held fixed? If there is, which names carry it, and does it replicate across the two halves of the book?

The operator asked whether these ten names each show a pattern of their own, and asked for push-back where the evidence is unreliable. This file answers in three steps:

1. **P1**, one omnibus test over the ten names together.
2. **P2**, a per-name test, graded only when P1 finds an effect.
3. **Step 3**, a second registration, written only when P2 flags a name (see [Step 3, fixed here](#step-3-fixed-here)).

## What this study is not

- **Not a ticker filter.** Nothing here changes `ladder_tier()`, the deploy card or `docs/deployment-rules.md`.
- **Not a group study.** [ticker_class](ticker_class.md) compared fixed groups of tickers. Its "no per-ticker verdict" clause binds that study only. This file names no group.
- **Not a ranking of names by P&L.** A raw per-name meanR mixes direction, side and the week's tape into the name. The descriptive table prints it, and nothing is graded on it.
- **Not a structure, exit or sizing study.** Each row keeps the structure and exit the backtest gave it.
- **Not a forward read.** The holdout seal withholds signal dates from 2026-09-23. This study is not a sealed reader.

## Definitions

### The ten names, fixed here

The rule: the top 5 ETFs and the top 5 single stocks by row count on `BacktestResults`, in the 2026-10-21 export.

| Class | Names, in rule order |
|---|---|
| ETF | IWM, SMH, TLT, QQQ, GLD |
| Stock | NVDA, TSLA, META, MU, AMD |

The next names by the same rule are SPY (31 rows), HYG (30) and AAPL (27). They are excluded. The list does not change when a later export changes the counts.

### Direction and side

Direction comes from `ticker_class.direction(structure)`: `bull_*`, `long_call` and `short_put` are bull; `bear_*` and `long_put` are bear. Only bull and bear rows are graded. Neutral and other rows are printed in the descriptive table.

Side is the record's `credit` flag from `load_book()`: credit when the entry price is not positive, debit otherwise.

### Strata

A stratum is one (ISO week of the signal date, direction, side) cell over the ten names' graded rows. A stratum is **informative** when it holds rows of at least two distinct names. Rows in other strata are dropped from P1 and P2, and their count is printed.

### Scores and the omnibus statistic

Inside each informative stratum of n_s rows, rank R ascending, with tied values given their average rank (midrank). Each row's score is

  a_i = midrank_i / (n_s + 1) − 0.5.

Scores sum to zero in every stratum. This is van Elteren's stratified rank score. Ranks make a credit row's large negative R count as one bad rank, not as a multiple of the stratum's spread.

For name t with n_t informative rows, S_t = Σ a_i over t's rows. The omnibus statistic is

  T = Σ_t S_t² / n_t, over names with n_t > 0.

A positive S_t means the name's plays rank above its peers' plays in the same week, direction and side.

The **mean-scale T** is the same formula with a_i replaced by R_i minus the stratum's mean R. It is printed beside T, with its own p from the same draws, and never graded.

### Permutation null

The null permutes name labels within strata. The rows are sorted by stratum code; one draw is `argsort(code + U(0,1))` over the rows, so each stratum's labels are shuffled and no label leaves its stratum. N_PERM is 20,000, from `numpy.random.default_rng(20261023)`. The p-value is

  p = (1 + #{T* ≥ T}) / (1 + N_PERM).

The per-name p-value from the same draws is p_t = (1 + #{|S_t*| ≥ |S_t|}) / (1 + N_PERM).

### The floor

A name **clears the floor** when it has at least 30 informative rows on at least 20 distinct signal dates.

### The median-n name

Sort the ten names by informative row count, ascending, ties alphabetical. The median-n name is the 5th, the lower median. The planted-power gate and the design-power table plant their single-name effect on it.

### Halves

Sort the distinct ISO weeks that hold an informative row. H1 is the first ⌊W/2⌋ weeks, H2 the rest. A stratum lies inside one week, so every score belongs to exactly one half.

### Analysis-date lag

The lag is the analysis row's `created_datetime` date minus its analysis date, in days. The analysis row is joined on (date, ticker, 60-character play prefix), first-written row first, exactly as `lib/book.py` joins it.

| Lag | Class |
|---|---|
| ≤ 1 day | LIVE |
| 2–7 days | NEAR |
| > 7 days | RETRO |
| blank, unjoined or negative | UNKNOWN |

A RETRO row was written by a model that may already have seen the outcome. The class is printed per name and never graded.

## Dependencies

- `scripts/backtest_study/lib/book.py::load_book` for the book, the seal, the pending flag and the era refusals.
- `scripts/backtest_study/f1_selection/benchmark/ticker_class.py` for `direction`, `holm`, `month_span`, `trim_to_multiple` and `std_point`. Its PBO constants are declared again locally and pinned equal by a test.
- `scripts/backtest_study/lib/pbo.py::cscv` with `ratio_metric`.
- `scripts/backtest_study/lib/protocol.py::boot_ci_by_date` and `window_cuts`.
- The one-clock entry re-price (`--redo`, queued for 2026-10-24). The post-re-price export is the read of record.

## Population and basis, fixed here

- **Era.** v4, from the bare exports in `backtests/to_evaluate/` (`STUDY_ERA=current`). v3 is a separately labelled replication, run with `--era v3`. The two are never pooled.
- **Loader.** One call: `load_book(include_pending=True)`, every other argument at its default. That means real rows plus `strike_expiry_tweak` proxy rows, `bs` rows excluded, and the proxy calibration gate on. The holdout seal applies, so signal dates from 2026-09-23 are withheld.
- **Pending rows.** Dropped by the study, so the per-name pending count prints.
- **Untrusted and blank rows.** Rows with `fill_trusted` false, and rows with no R, are dropped. Their counts print.
- **Path status.** `complete`, `carried` and closed-window `open_at_data_end` rows are all kept. A `carried` row is a real exit with partly stale marks, and dropping them drops losers. A closed-window open row is the `cap_open` outcome at its last mark. A blank `path_status` (rows written before 2026-09-23, and all of v3) is kept.
- **Metric.** R, the stored `realized_pnl_pct`. On v4 it is net of `cost_total`. v3 predates the cost model, so v3 R is gross. `pnl_on_risk_pct` is printed beside R.
- **Proxy rows.** Included as the loader includes them. Each name prints its `n_results` and `n_tweak`. P1 is repeated on real-only rows and on complete-only rows.

## Plan-time observations, disclosed

These come from a census of descriptor columns on 2026-10-23. No outcome column was read for it, except the facts the main session supplied, marked below.

**The v4 book.** After the seal it holds 1,850 rows over 280 dates, 2024-01-10 to 2026-09-22. The seal withholds 136 rows on 19 dates. Each of the ten names has at most one row per signal date.

| Name | Informative rows, v4 | Informative rows, v3 | LIVE rows, v4 |
|---|---|---|---|
| IWM | 109 | 47 | 4 |
| SMH | 81 | 27 | 9 |
| TLT | 60 | 21 | 7 |
| QQQ | 42 | 27 | 5 |
| GLD | 64 | 44 | 18 |
| NVDA | 96 | 53 | 7 |
| TSLA | 59 | 31 | 1 |
| META | 51 | 16 | 5 |
| MU | 56 | 14 | 10 |
| AMD | 46 | 15 | 6 |

- **Informative share.** On v4, 664 of 807 graded rows (0.82) sit in informative strata. On v3 it is 295 of 342 (0.86).
- **v3 is thin.** Only IWM, NVDA, GLD and TSLA reach 30 informative rows on v3. The v3 GP0 bar is therefore 4 names, not 8.
- **Backfill.** 251 of 301 analysis dates were written by the model in Aug–Sep 2026. Only 47 dates have a `created_datetime` within a day of the analysis date. The LIVE column above counts the loaded book, pending rows included: most of every name's rows are RETRO, so a per-name pattern can be model recall.
- **Pending rows.** 35 of the ten names' loaded rows are pending at the export as-of 2026-10-20.
- **Supplied: R is return on premium.** Credits have tiny denominators: 44 rows sit below −1.0, and 40 of them are credits. `pnl_on_risk_pct` is the return on risk. This is why P1 grades ranks, not means.
- **Supplied: noise.** The pooled SD of `realized_pnl_pct` is 0.885. A name's meanR at n = 30 to 94 has an SE of about 0.09 to 0.18.
- **Supplied: what explains returns.** Play direction and the shared tape on a date explain the book's returns. That is why the strata hold week, direction and side fixed.
- **Supplied: the exports will move.** The 2026-10-21 exports predate the 2026-10-23 one-clock entry-pricing rule. A `--redo` re-price is queued, and every figure will move on re-run.
- **An unregistered pass.** The 2026-10-22 descriptive pass of the 2026 book (`research/current.md`, entry dated 2026-10-22) read about 30 cuts on the bare export, including 83 rows on sealed dates. It is disclosed here and is never cited as evidence.

## What it compares

| Object | Object type | Population | Role |
|---|---|---|---|
| P1 | omnibus, ten names, strata (week, direction, side) | informative rows | PRIMARY, graded |
| P2 | per-name, Holm m = 10, split-half | informative rows | graded only when P1 = TICKER-EFFECT |
| PBO | CSCV, pick-the-best-name | informative rows by month | veto on P1 and P2 |
| PBO-D | CSCV on direction-standardised monthly meanR | graded rows by month | diagnostic, printed |
| S-DATE | P1 on strata (date, direction) | graded rows | sensitivity, qualifier |
| S-MONTH | P1 on strata (month, direction, side) | graded rows | sensitivity, qualifier |
| X-2025 | P1 without Mar–Apr 2025 | graded rows | window cut, qualifier |
| X-2026 | P1 without Feb–Apr 2026 | graded rows | window cut, qualifier |
| R-REAL | P1 on real rows only | graded rows | sensitivity, printed |
| R-COMPLETE | P1 on `complete` rows only | graded rows | sensitivity, printed |
| DP | design-power table on synthetic outcomes | the real informative strata | printed |
| D0 | descriptive table, one row per name | outcome rows, all directions | printed, never graded |

### P1 — the omnibus

T and its permutation p, as defined above. P1 reads TICKER-EFFECT when p ≤ 0.05, and NULL otherwise, subject to the gates and the PBO veto.

### P2 — per name

For each of the ten names: S_t, n_t, p_t from the P1 draws, and the Holm-adjusted p_t over all ten names (`ticker_class.holm`, m = 10). A name below the floor stays in the Holm family and cannot be flagged.

The effect size θ_t is the mean, over t's informative rows, of R_i minus the mean R of the other names' rows in the same stratum. Its CI comes from `protocol.boot_ci_by_date` (10,000 draws). The CI conditions on the peers, so it is optimistic. The permutation p is the graded number.

Each name also prints S_t and n_t in H1 and in H2, and S_t on real-only rows (strata rebuilt on those rows).

### PBO — the veto

The selection being tested is "pick the best name".

- **Matrix.** T × 10 × 2: for each signal month and name, [Σ a_i, count] over the name's informative rows.
- **T.** Every calendar month from the first to the last informative month (`ticker_class.month_span`). The earliest months are trimmed until 16 divides T (`ticker_class.trim_to_multiple`). A month where a name has no row stays blank, never zero-filled.
- **Run.** `pbo.cscv(M, S=16, metric=pbo.ratio_metric)`. A block's statistic is a name's mean score over the block's non-blank rows. A name blank across a whole block ranks worst.

| PBO | Reading |
|---|---|
| ≤ 0.25 | supports a verdict |
| 0.25 – 0.50 | a TICKER-EFFECT is printed with "selection fragile" |
| > 0.50, or not computable | veto: P1 reads NULL and no name is flagged |

The thresholds are `ticker_class`'s `PBO_SUPPORT` and `PBO_VETO`.

**PBO-D** repeats the CSCV on each name's direction-standardised monthly meanR (bear and bull weighted by the ten names' pooled bear/bull mix, renormalised over the directions present that month). It is printed, never graded.

### Sensitivities and window cuts

S-DATE, S-MONTH, X-2025, X-2026, R-REAL and R-COMPLETE each rebuild their strata from the graded rows they keep, then compute T and p with the P1 draw settings (20,000 draws, seed 20261023). X-2025 and X-2026 are the cuts `protocol.window_cuts` names `ex_2025_mar_apr` and `ex_2026_feb_apr`.

### DP — design power

A NULL is read at the size it could detect. DP uses the real informative strata and labels and no outcome column. Each simulated row gets

  R = tape_w + ε + effect_t,

where tape_w ~ N(0, 0.5²) is shared by every row in ISO week w, and ε is a t-variate with 4 degrees of freedom scaled to SD 0.8.

| Scenario | effect_t |
|---|---|
| one name +0.20 R | +0.20 on the median-n name, 0 elsewhere |
| one name +0.35 R | +0.35 on the median-n name |
| one name +0.50 R | +0.50 on the median-n name |
| spread SD 0.15 | each name N(0, 0.15²), drawn per simulation |
| spread SD 0.20 | each name N(0, 0.20²), drawn per simulation |

Each scenario runs 200 simulations of 500 within-stratum permutations, seed 20261025. Power is the share of simulations with p ≤ 0.05.

### D0 — the descriptive table

One row per name, never graded:

- n, `n_results` / `n_tweak`, and `complete` / `carried` / `cap_open` (closed-window open) / blank counts;
- pending share of the loaded rows;
- bull, bear and neutral shares; the top two structures; the credit share;
- win rate, meanR, median R and the 10%-trimmed meanR;
- mean `pnl_on_risk_pct`;
- median `dte` and median `days_held`;
- meanR by `mech_cell`, cells under 10 rows hidden;
- the exit-reason mix;
- LIVE, NEAR, RETRO and UNKNOWN row counts.

## How it is judged

P1 is the only primary verdict. P2 is graded only when P1 reads TICKER-EFFECT. The PBO read can veto both, and never supports them on its own.

The order of checks is fixed: the gates first (UNDERPOWERED), then the PBO veto, then P1's p-value (NULL or TICKER-EFFECT).

**Qualifiers.** On a TICKER-EFFECT headline, a qualifier is appended when X-2025 or X-2026 has p > 0.10, or when S-DATE or S-MONTH has p > 0.20. A qualifier never changes the verdict token.

## Gates

- **GE era.** `load_book()` resolves the era and the header names it. A mismatched export exits 3 and a thin era exits 2, as the loader does.
- **GP0 power.** At least 8 names clear the floor (4 on v3). On failure: UNDERPOWERED.
- **GP1 informative share.** At least 60% of graded rows sit in informative strata. On failure: UNDERPOWERED.
- **GP2 planted power.** A planted +0.50 R on the median-n name is detected in at least 80% of 200 simulations. Each simulation permutes the real R within strata, which removes any real name effect. It then adds +0.50 to the median-n name's informative rows, rescores, and runs 500 within-stratum permutations. Detected means p ≤ 0.05. Seed 20261024. On failure: UNDERPOWERED.

## Bar for a candidate

A name is **FLAGGED** only when all six hold:

1. P1 reads TICKER-EFFECT, and the PBO veto has not fired.
2. The name clears the floor.
3. Its Holm-adjusted p_t is below 0.05 (m = 10).
4. It has at least 15 informative rows in H1 and in H2. Otherwise it reads NOT REPLICABLE.
5. S_t has the same sign in H1, in H2 and in the full sample.
6. S_t on real-only rows has the same sign as in the full sample.

## Verdicts, worded now

| Verdict | When |
|---|---|
| P1 TICKER-EFFECT | GP0–GP2 pass, PBO ≤ 0.50, and p ≤ 0.05 |
| P1 NULL | GP0–GP2 pass and p > 0.05; or PBO > 0.50 (the veto) |
| P1 UNDERPOWERED | any of GP0, GP1 or GP2 fails. The census prints and nothing is concluded. |
| P2 FLAGGED | a name meets all six bar clauses; the banner lists every flagged name |
| P2 NOT FLAGGED | P2 is graded and the name fails a clause; the failed clause prints |
| P2 NOT REPLICABLE | P2 is graded and the name has fewer than 15 informative rows in a half |
| P2 none graded | P1 is not TICKER-EFFECT. The per-name table still prints. |

The banner, in a section titled VERDICT:

```
>>> ticker_pattern P1 (omnibus, ten names, <era>): NULL | TICKER-EFFECT | UNDERPOWERED <<<
>>> ticker_pattern P2 (per-name, Holm m=10, split-half): <FLAGGED names, or "none graded"> <<<
>>> ticker_pattern PBO (CSCV, pick-the-best-name): <value> <<<
```

An outcome not named here goes to the nearest label above, with a printed qualification.

## Step 3, fixed here

- **P1 = TICKER-EFFECT and at least one name FLAGGED.** A second registration is written. It takes the next ten names by the same rule, with their own omnibus and their own Holm family. Each flagged name gets a closed cut list: `mech_cell`, debit vs credit, bull vs bear, with at least 30 informative rows per side. Its forward confirmation is filed "to be tested" in `research/deployment-evidence.md` until `era.SEAL_LIFTED`.
- **P1 = TICKER-EFFECT and no name FLAGGED.** One "to be tested" line is filed in `research/deployment-evidence.md`, and step 3 stops.
- **P1 = NULL.** Step 3 closes on these dates.
- **P1 = UNDERPOWERED.** Nothing is concluded. The study re-runs as the era accrues.

## v3 replication

`--era v3` runs the same code on the same ten names, with the v3 GP0 bar of 4 names. Its banner names era v3 and prints "v3 replication (same ten names)". v3 covers the same market path, so it can only note agreement with the v4 verdict. It never confirms or refutes it, and the two eras are never pooled.

## Anti-tuning

- The ten names, the primary stratum, the score, the statistic, N_PERM, the three seeds, the floor, the gates, the bar and the PBO thresholds are fixed here.
- No name, stratum or cut is added after a run. Each is a new registration.
- The post-re-price export (one-clock entry pricing, `--redo` queued for 2026-10-24) is the read of record. The study is a one-command re-run: `python3 -m scripts.backtest_study run ticker_pattern`.
- The 2026-10-22 descriptive pass is never cited as evidence for or against any name.

## What could ship

Nothing ships from this study. A confirmed read files a "to be tested" entry in `research/deployment-evidence.md`. A `docs/deployment-rules.md` change waits for a forward confirmation and a separate operator ruling.
