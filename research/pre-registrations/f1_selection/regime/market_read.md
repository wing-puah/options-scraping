## market_read — does the model's MARKET regime label forecast SPY, beyond the mechanical label?

<!-- outcome:start -->
> Latest outcome: v4, run 2026-10-23 · [record](../../../study-results/f1_selection/regime/market_read.md).
>
> ```
> >>> market_read P1 (model BULL - non-BULL, 21d fwd SPY, v4 pre-seal): NULL <<<
> >>> market_read P2 (P1 within mech direction): NULL <<<
> >>> market_read READ (P1+P2): NO-FORECAST <<<
> >>> market_read P3 (sizing, E-VOL, 21d drawdown, Holm m=2): NULL <<<
> >>> market_read P4 (recall, RETRO - LIVE): STILL-OPEN <<<
> >>> market_read FORWARD (P1, P2, dates after registration): STILL-OPEN <<<
> ```
<!-- outcome:end -->

_Registered 2026-10-23._

## The question

Does the model's MARKET regime label forecast SPY over the hold horizon? And does it add anything
beyond the [mechanical label](../../../glossary.md#mech_cell) computed from the same closes?

The operator sizes trades on this label. The [§1](../../../../docs/deployment-rules.md#s1) vetoes
and the [§2](../../../../docs/deployment-rules.md#s2) tiers key on the
[market regime](../../../glossary.md#regime). No study has tested that label against what SPY did
next.

Two co-primary contrasts answer the question:

- **P1.** Mean 21-session forward SPY log return, model BULL dates minus model non-BULL dates.
- **P2.** P1 inside mechanical-direction strata. It asks whether the model's call adds anything
  once the mechanical direction is held fixed.

Two secondaries follow:

- **P3, sizing.** Are model E-VOL dates followed by deeper SPY drawdowns?
- **P4, recall.** Is any in-sample edge larger on backfilled labels than on labels written live?

## What this study is not

- **Not a selection or exit rule.** It reads no position, no tier and no R. Its outcome is SPY's
  own path.
- **Not a test of the per-play regime.** That label is ticker-level. It differs from the market
  row on 297 of 300 dates.
- **Not a re-grade of earlier studies.** [`direction_hit`](../signal/direction_hit.md) graded the
  picks' direction (`NULL`). [`regime_confirm`](regime_confirm.md) graded the mechanical BEAR flip
  (`RETRO-NULL`). [`regime_map`](regime_map.md) is descriptive. None tested the MARKET label
  against forward SPY.
- **Not pooled across eras.** v3 and v4 are different tapes. `--era v3` is a replication, never a
  pool.
- **Not a ship.** A confirmed read files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md) and changes no production code.

## Definitions

### The label, parsed from its head

The MARKET row's `regime` is free text. The tokeniser reads only its head, so prose later in the
string cannot change the label.

| Field | Rule |
|---|---|
| head | The text before the first of `—`, `" - "`, `". "`, `": "` or `" ("` |
| `dir` | The first of BULL, BEAR, RANGE in the head, as a whole word |
| `vol` | The first of E-VOL, H-VOL, L-VOL, C-VOL in the head |
| `risk` | RISK-ON, RISK-OFF, or none |
| `HP` | Present when HP is a whole token in the head |

- **Transition.** A head such as "RANGE-to-BEAR" reads as RANGE, its first direction, and is
  flagged as a transition.
- **OTHER.** A head with no direction. It is census only. The run refuses (exit 2) when OTHER
  dates exceed 2% of the population.
- **No vol token.** The date leaves P3 only.
- **Model non-BULL.** BEAR or RANGE. OTHER dates are in neither arm.
- **C-VOL.** The framework's "volatility compressing" call. The mechanical label has no
  counterpart.

### Lag bin

Lag is `created_datetime[:10]` minus `date`, in days. It partitions dates and never predicts.

| Lag bin | Lag |
|---|---|
| LIVE | 0 or 1 day |
| NEAR | 2 to 7 days |
| RETRO | more than 7 days |
| UNKNOWN | blank, or negative |

A RETRO label was written after the fact, by a model that may know what SPY did next.

### Duplicate dates

v3 holds two dates with two MARKET rows each. When the two rows' directions differ, the date is
AMBIGUOUS. It leaves every graded statistic and is printed as a test-retest finding.

### Calendar and the mechanical label

- **Calendar.** The SPY sessions with a non-blank close in
  `backtests/mech_regime/spy_vix_daily_full.csv`. The session index `i` counts from the table's
  first session.
- **Exact sessions only.** A signal date must be a session. An off-calendar date is dropped and
  counted, never mapped as-of.
- **Mechanical label.** `MechLabeler.label(d)`, kept only when `ok` is true and the mapped date
  equals `d`. Direction and vol follow `lib/mech_regime.py` unchanged.

### Outcomes per date

`c` is SPY's unadjusted close; `i` is the signal date's session index.

| Outcome | Definition | Graded in |
|---|---|---|
| `ret_h` | `ln(c[i+h] / c[i])`, for `h` in 5, 10, 21 | `ret21` only: P1, P2, P4 |
| `rv21` | SD (ddof 1) of the 21 daily log returns ending at `i+21`, in % per day, not annualised | Printed only |
| `mae21` | `min(0, min(c[i+1..i+21]) / c[i] − 1)` | Printed only |
| `dd21` | `−mae21`, the drawdown depth, zero or positive | P3 |

A window that runs past the table's end is dropped. The drops are counted per horizon.

### Bootstrap block

A block is `i // 21`: a fixed 21-session run of the SPY calendar. All dates in one block travel
together in every draw.

Two other units were considered and rejected. Chaining dates whose windows overlap collapses each
era into one cluster at a gap of 21 sessions. A per-date bootstrap treats overlapping windows as
independent.

## Dependencies

- `scripts/backtest_study/lib/era.py`: `requested_era`, `resolve_paths`, `enforce`,
  `drop_sealed`, `seal_line`, `require_dates`, `SEAL_START` and `SEAL_LIFTED`.
- `lib/mech_regime.py::MechLabeler`, read unchanged. No threshold moves.
- `backtests/mech_regime/spy_vix_daily_full.csv`. Refresh it with `make mech-regime` before a
  forward run.
- The era's analysis export, MARKET rows only. No backtest row, R or P&L column is read.

## Population and basis, fixed here

- **Era.** `era.requested_era()`, then `resolve_paths` and `enforce` on the three export paths. A
  mismatch refuses (exit 3). The study reads only the analysis export. Every report header names
  the era.
- **Rows.** The MARKET rows (`ticker == MARKET`) of the analysis export.
- **Seal.** `era.drop_sealed(rows, date_key="date")`, with no reader, and `seal_line` prints the
  count. This study is not in `era.SEALED_READERS` (see the
  [holdout seal](../../f4_deployment/holdout_seal.md) and the
  [sealed window](../../../glossary.md#sealed-window)). Signal dates from 2026-09-23 are withheld.
- **Windows may cross the seal.** The seal binds signal dates. A pre-seal date's 21-session window
  may run past 2026-09-23.
- **In-sample: P1, P2, P3.** Signal dates before `era.SEAL_START`, read at run time (today
  2026-09-23). This stays true after the seal lifts.
- **P4.** RETRO and LIVE dates. Its LIVE bin grows: live dates from 2026-09-23 on join once
  `era.SEAL_LIFTED` is set and their windows close.
- **Forward: P1, P2.** Signal dates after 2026-10-23 (`FWD_AFTER`). None is read until
  `era.SEAL_LIFTED` is set.
- **The gap.** Signal dates from 2026-09-23 through 2026-10-23 are in neither the in-sample nor the
  forward population. They can enter P4's LIVE bin only.
- **Era floor.** `era.require_dates(n, era, minimum=60)` on the in-sample dates. Below it the run
  refuses (exit 2).
- **Drops, each counted and printed.** Off-calendar dates, dates with no mechanical label, OTHER
  and AMBIGUOUS dates, and windows past the table's end.

## Plan-time observations, disclosed

Every figure below was counted on 2026-10-23, before this file was written. No outcome was read:
no forward SPY return, drawdown or volatility was computed on any date.

_Exports: v4 `backtests/to_evaluate/analysis - AnalysisClaude.csv`, v3
`analysis - v3_AnalysisClaude.csv` beside it._

### When the labels were written

v4 holds 301 MARKET rows, one per date, from 2024-01-10 to 2026-10-20.

| v4 lag, all 301 rows | Rows | Dates covered |
|---|---|---|
| within 1 day | 47 | 2026-08-11 to 2026-10-20 |
| within 3 days | 3 | — |
| 30 to over 900 days | 251 | 2024-01 to 2026-07-31, backfilled in Aug–Sep 2026 |

| Pre-seal lag bin | v4 dates | v3 dates |
|---|---|---|
| LIVE | 28 | 23 |
| NEAR | 2 | 1 |
| RETRO | 251 | 116 |

- Every v4 BEAR label (13) is backfilled. The live v4 labels are BULL 26 and RANGE 21.
- v3 holds 142 MARKET rows on 140 dates. 2026-02-19 and 2026-03-06 each carry two rows, and on
  both dates the two rows disagree, BEAR against RANGE.

### The label is free text

All 301 v4 strings are distinct. Their heads take 49 forms on all rows, 47 on pre-seal rows.

The loader's `book.model_direction` scans the whole string by substring, in the order BULL, BEAR,
RANGE. It finds BEAR on 24 of the 301 v4 rows, and on 22 pre-seal dates. The head says BEAR on 13
in both counts. The rest are RANGE labels that mention BEAR in their prose. That is why this study
parses the head only.

| Head parse, pre-seal | v4 dates | v3 rows |
|---|---|---|
| BULL | 157 | 36 |
| RANGE | 111 | 77, one a RANGE-to-BEAR transition |
| BEAR | 13 | 29, all backfilled |
| OTHER | 0 | 0 |

On v3 the whole-string scan finds BEAR on 34 rows, against 29 by head.

| v4 vol token, pre-seal | Dates |
|---|---|
| L-VOL | 178 |
| E-VOL | 68 |
| C-VOL | 27 |
| H-VOL | 8 |

### The labels overlap

| v4 pre-seal overlap | Count |
|---|---|
| BULL dates whose head also says RISK-ON | 145 of 157 |
| E-VOL dates whose head also says RISK-OFF | 55 of 68 |
| Model BULL dates that are also mech BULL | 138 of 157 |

So P3's RISK-OFF twin largely repeats the E-VOL contrast, and P1 largely repeats the mechanical
direction. P2 exists for the second reason.

| v4 pre-seal, mech direction | Model BULL | Model non-BULL |
|---|---|---|
| BULL | 138 | 46 |
| RANGE | 16 | 26 |
| BEAR | 3 | 51 |

Mech BEAR falls below P2's stratum floor on its model BULL arm.

### Data checks

- **Stored against recomputed.** The stored `mech_cell` equals the recomputed `MechLabeler` cell
  on every pre-seal date, on v4 and v3 (0 mismatches).
- **Table span.** The SPY/VIX table runs from 2023-06-01 to 2026-10-22. Every pre-seal 21-session
  window closes inside it.
- **Blank closes.** Two rows carry no SPY close (2026-05-25 and 2026-09-07), so they are not
  sessions.
- **Off-calendar dates.** v4 has one (2024-07-28, a Sunday). v3 has one (2025-01-09, a day the
  market was closed).
- **Blocks.** v4's pre-seal dates fall in 33 blocks and v3's in 21. Of these, v4's 28 LIVE dates
  fall in 2.

### The two eras are different tapes

| MARKET dates on which SPY closed above its 50-day SMA | Share |
|---|---|
| v4, pre-seal | 78% |
| v3 | 38% |

### A prior, not evidence

An unregistered pass on 2026-10-22 read play P&L against these labels. It is the "Market cuts"
section of the entry "the 2026 book, described" in [`current.md`](../../../current.md).

- Plays agreeing with their ticker regime lost (−$226 per trade, CI clear of zero).
- Bull plays on market BULL dates lost. Bear plays on market BULL dates won.
- Neither VIX nor SPY at entry had a rank correlation with return on risk.

It read 83 sealed rows. It reads positions, not SPY's path, and it carries no weight here.

### Other disclosures

- **Sizing.** The shipped [sizing rule](../../../../docs/deployment-rules.md#s2-sizing) keys on the
  mechanical [dip flag](../../../glossary.md#dip-date), not on the model label.
- **Recall.** The RETRO labels were written after the fact, by a model whose training data may
  cover those dates. Model recall is a standing risk. P4 measures it on this population; it cannot
  remove it.

## What it compares

| Object | Object type | Contrast | Role |
|---|---|---|---|
| P1 | arm | Mean `ret21`, model BULL minus model non-BULL | Co-primary |
| P1m | control | Mean `ret21`, mech BULL minus mech non-BULL, same dates | Printed beside P1 |
| P1 − P1m | descriptive cut | The paired difference, on shared draws | Printed beside P1 |
| P2 | arm | P1 standardised within mechanical-direction strata | Co-primary, incremental |
| P3 | arm | Mean `dd21`, model E-VOL minus not E-VOL, standardised within mechanical vol | Secondary, Holm |
| P4 | arm | P2 on RETRO minus P2 on LIVE | Secondary, Holm |
| FORWARD | population scope | P1 and P2 on signal dates after 2026-10-23 | Forward verdict |

### P1, the label's own forecast

P1 asks whether SPY rose more after model BULL dates than after the rest. P1m runs the same
contrast with the mechanical direction on the same dates. P1, P1m and their paired difference come
from the same block draws.

### P2, what the mechanical label does not cover

- **Strata.** Mechanical direction: BULL, RANGE, BEAR.
- **Stratum floor.** A stratum enters when each arm holds 10 or more dates in 3 or more blocks.
- **Weights.** Each entering stratum's share of the dates in all entering strata. The weights are
  fixed once on the full sample and do not change across draws.
- **Statistic.** The weighted mean, over entering strata, of model BULL minus model non-BULL mean
  `ret21`.
- **Empty arms.** A draw in which an entering stratum has an empty arm is discarded. The discards
  are counted and printed.

### P3, the sizing read

P3 asks whether model E-VOL dates are followed by deeper SPY drawdowns, which would argue for
smaller size on those dates.

- **Arms.** E-VOL against every other vol token (H-VOL, L-VOL, C-VOL). Dates with no vol token are
  out.
- **Strata.** Mechanical vol: L-VOL, and H-VOL with E-VOL pooled. Stratum floor, weights and
  empty-arm rule are P2's.
- **Why E-VOL.** It is the vol token the §2 Tier A rule keys on. A BULL against non-BULL drawdown
  contrast would re-test P1, so it is printed instead.
- **Sign.** `dd21` is zero or positive. A deeper drawdown after E-VOL dates makes the difference
  positive, so `SUPPORTED` means the token warned.
- **Printed twins.** The same contrast for RISK-OFF and for HP; P3 unstratified; the mechanical
  E-VOL comparator; the contrast on `rv21`; and the share of dates per arm with `mae21` below −3%
  and below −5%.

### P4, the recall check

- **Statistic.** P2 computed on RETRO dates minus P2 computed on LIVE dates, on shared block draws.
  NEAR and UNKNOWN dates are out. Both bins use P2's entering strata and weights.
- **Tape gauge.** The same RETRO-minus-LIVE gap for P1m, printed beside it. It shows how much the
  two bins' tapes differ with no model involved.
- **Today.** LIVE holds 28 dates in 2 blocks, so P4 prints `STILL-OPEN` at registration. It
  reaches its floor around April 2027 at the earliest. That needs the seal lifted, and LIVE must
  accrue mechanical non-BULL dates.

### Printed only, never graded

- The vocabulary census: every distinct string, mapped to its `dir`, `vol`, `risk` and `HP`.
- Counts: OTHER, transition, off-calendar, sealed, AMBIGUOUS, and windows past the table's end.
- Model-against-mechanical confusion matrices, for direction and for vol.
- Lag bin by label.
- The vol token against `rv21`, within mechanical vol.
- `ret5` and `ret10`.
- P1 and P2 with the window starting at the next session's close.
- The mandatory window cuts: excluding March–April 2025, and excluding February–April 2026.
- Every table cut three ways: `ALL`, RETRO and LIVE.

## How it is judged

- **Bootstrap.** Resample blocks with replacement, as many as the population holds, for 10,000
  draws. The seed is 20260811.
- **Shared draws.** Every arm, stratum and paired difference in one run comes from the same draws.
- **CI.** The 95% percentile interval ([CI](../../../glossary.md#ci), here clustered by block, not
  by date). Every CI prints its half-width, so a `NULL` reads "spans 0 at ±x".
- **Sensitivity.** The same statistics on 42-session blocks (`i // 42`), printed and never graded.
- **p-values.** Two-sided, from the same draws: twice the smaller of the share of draws at or
  below 0 and the share at or above 0, capped at 1.

**Multiple comparisons.**

- P1 and P2 form an intersection. Each is read at 5%, with no correction.
- P3 and P4 form a Holm family with m = 2. P4 enters at p = 1 until it is gradable.
- A P3 `SUPPORTED` or `CONTRARY`, or a P4 `RECALL-FLAGGED`, stands only when its Holm-adjusted p is
  below 0.05. Otherwise P3 prints `NULL` and P4 prints `RECALL-NOT-SHOWN`.

## Gates

- **Era.** `era.enforce` refuses a wrong or mixed era (exit 3).
- **Era floor.** `era.require_dates` refuses fewer than 60 in-sample dates (exit 2).
- **Parse.** OTHER above 2% of the population's dates refuses the run (exit 2).
- **Floors.** A contrast below its floor, or with a NaN statistic, prints `UNDERPOWERED`. P4 and
  FORWARD print `STILL-OPEN` instead.

| Contrast | Floor |
|---|---|
| P1, P3 | 20 dates and 12 blocks per arm |
| P2 | Each stratum: 10 dates and 3 blocks per arm. At least one stratum enters |
| P4 | RETRO: 24 blocks. LIVE: 8 blocks and 60 dates |
| FORWARD | 60 dates in 8 blocks, all with closed 21-session windows |

The forward floor replaces P1's in-sample per-arm floor, which 8 blocks could not meet. Forward P2
keeps P2's stratum floor.

## Verdicts, worded now

**P1, P2 and P3:**

| Token | When |
|---|---|
| `SUPPORTED` | Floors met, CI lower bound above 0 |
| `CONTRARY` | Floors met, CI upper bound below 0 |
| `NULL` | Floors met, CI spans 0; printed with its half-width |
| `UNDERPOWERED` | A floor unmet, or the statistic is NaN; census printed, nothing concluded |

For P3, `SUPPORTED` means E-VOL dates fell further, which argues for smaller size on them.
`CONTRARY` means they fell less.

**READ, combining P1 and P2.** The first matching row wins.

| P1 | P2 | READ | In plain words |
|---|---|---|---|
| `CONTRARY`, either | | `CONTRARY` | The label points the wrong way |
| `UNDERPOWERED`, either | | `UNDERPOWERED` | Too few dates to judge |
| `SUPPORTED` | `SUPPORTED` | `MODEL-ADDS` | The label forecasts SPY and adds to the mechanical label |
| `SUPPORTED` | `NULL` | `MECH-COVERS` | The label forecasts SPY; the mechanical label on the same closes carries it |
| `NULL` | `SUPPORTED` | `INCREMENTAL-ONLY` | No forecast overall, but an edge with mechanical direction held fixed |
| `NULL` | `NULL` | `NO-FORECAST` | Neither |

Any in-sample `SUPPORTED` prints "recall unexcluded" beside it until P4 prints
`RECALL-NOT-SHOWN`.

**P4:**

| Token | When |
|---|---|
| `RECALL-FLAGGED` | Floors met, CI wholly above 0, point estimate above the tape gauge's, and Holm-adjusted p below 0.05 |
| `RECALL-NOT-SHOWN` | Floors met, and not flagged |
| `STILL-OPEN` | A floor unmet |

**FORWARD.** P1 and P2 on forward dates take the P1/P2 tokens above, with `STILL-OPEN` in place of
`UNDERPOWERED`. The FORWARD line prints their READ combination. The verdict of record is the first
forward run that prints a token other than `STILL-OPEN`. Later forward runs are descriptive.

**The banner.** The report's section titled VERDICT prints:

```
>>> market_read P1 (model BULL - non-BULL, 21d fwd SPY, <era> pre-seal): <word> <<<
>>> market_read P2 (P1 within mech direction): <word> <<<
>>> market_read READ (P1+P2): MODEL-ADDS | MECH-COVERS | INCREMENTAL-ONLY | NO-FORECAST | CONTRARY | UNDERPOWERED <<<
>>> market_read P3 (sizing, E-VOL, 21d drawdown, Holm m=2): <word> <<<
>>> market_read P4 (recall, RETRO - LIVE): RECALL-FLAGGED | RECALL-NOT-SHOWN | STILL-OPEN <<<
>>> market_read FORWARD (P1, P2, dates after registration): STILL-OPEN <<<
```

## Anti-tuning

- Fixed here: the tokeniser and its separators, the lag bins, the horizons, the floors, the
  21-session block, the seed and the verdict words.
- The window cuts, the 42-session blocks, the next-session start, `ret5` and `ret10` are printed as
  they fall. None is used to re-grade.
- No other label token, stratum or horizon is graded.
- This registration is immutable in substance from 2026-10-23. Editorial consolidation only.

## What could ship

Nothing ships from this study.

- A confirmed read files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md). It changes no production code.
- `NO-FORECAST`, `CONTRARY` or `UNDERPOWERED` changes nothing.
- No verdict here changes a tier, a veto, a size class or an exit.
