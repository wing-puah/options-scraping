## state_map — which market states come before SPY sell-offs, and is the confirmed bear state too late?

<!-- outcome:start -->
> Latest outcome: not run — draft of 2026-11-21.
<!-- outcome:end -->

_Registered ____-__-__ (DRAFT — not registered; becomes immutable in substance when the operator accepts it)._

**STATUS: DRAFT, ACCEPTED BY DEFAULT on the drafter's recommended parameters (the operator's
standing rule of 2026-10-09), pending the second reader.** Drafted 2026-11-21. No forward return,
hit rate, lift, episode count or episode outcome was computed before this file was written. The
registration date is stamped when the second reader's fixes are folded in and the file is
committed. Contested choices are parameters printed both ways, with one named as the headline.

A fresh second reader checked the draft on 2026-11-21, before any outcome existed. Its read was
FREEZE AFTER MINOR EDITS. Its three blocking findings and every minor one are folded in below.

## The question

The operator asked whether any pattern marks a bull, bear or range-bound market early enough to
trade the bear side. SPY fell 11.5% from 2026-10-06 to 2026-11-20, and the bear plays paid only
inside that window.

The 2024–2026 play data holds about three sell-offs, too few to answer this. SPY and VIX closes go
back to 1993, which gives dozens of sell-offs. This study uses that long history and reads no play
row for its graded questions.

It asks five questions.

| Label | Question | Role |
|---|---|---|
| Q1 | How many days does SPY spend in each mechanical state, how long does a state last, and how do states follow each other? | Descriptive, no verdict |
| Q2 | Before a sell-off starts, does any of nine state variables turn on more often than on matched calm days? | Primary |
| Q3 | Once the mechanical BEAR or E-VOL state prints, does SPY keep falling, or is the move already over? | Primary |
| Q4 | What would a fixed SPY put spread opened on each Q3 signal have paid, at real prices, from 2022? | Secondary, printed with a THIN flag, decides nothing |
| Q5 | How did the book's bear and bull rows do in each state at entry? | Secondary, descriptive, no verdict |

What each verdict word would mean for the operator:

| Word | Question | Meaning |
|---|---|---|
| `LEADS` | Q2 | The variable was on more often in the 10 sessions before a top. This says nothing about how often it fires without a top |
| `COINCIDENT` | Q2 | The variable turns on during the fall, not before the top. It marks a fall already under way |
| `NO-FORECAST` | Q2 | No warning before the top was shown |
| `UNDERPOWERED` | Q2, Q3 | Too few sell-offs or signals to judge. Nothing is concluded |
| `ROOM-LEFT` | Q3 | After the signal SPY kept falling, more than after an ordinary day. A bear trade at the next close still had a fall to catch |
| `TOO-LATE` | Q3 | After the signal SPY did better than after an ordinary day. The fall was over |
| `NULL` | Q3 | No difference from an ordinary day was shown |

No verdict changes a rule.

**Two limits to read first.**

- **Q2 looks backward from known tops.** Its onset is the peak, which is only known after the
  fall. It compares how often a variable was on before tops with how often it was on in calm
  stretches. It does not measure how often a sell-off follows when the variable turns on. Two
  printed-only tables show that side, with no verdict.
- **The peak is a 63-session high by construction.** Price rules are pushed off before it and on
  after it (see [the bias](#the-q2-statistic)).

## What this study is not

- **Not a selection re-test.** [`lessons.md`](../../../lessons.md) line 24 says bear debit has no
  standalone selection edge and not to re-test it. Q5 slices the book by market state at entry and
  prints what each slice did. It grades nothing, and no slice becomes a pick rule.
- **Not a re-grade of earlier studies.** [`market_read`](market_read.md) tested the model's label,
  [`baseline_read`](baseline_read.md) the hedging flow, and [`regime_confirm`](regime_confirm.md) a
  persisting mech BEAR flip against a 10% fall. [`tail_breach`](tail_breach.md) tested one-day
  moves scaled by VIX. This study asks about sell-off onsets and fixed-horizon SPY returns after a
  state change, on 1993 history.
- **Not a hedge study.** It sizes no hedge and reads no sleeve. Q4 prices one fixed structure as a
  description.
- **Not intraday.** Every label and outcome uses daily closes.
- **Not pooled across eras.** Q1–Q4 read unversioned market closes. Q5 reads play rows, with v4 as
  the population and v3 as a replication, never a pool.
- **Not a ship.** Nothing in production, on the deploy card or in `ladder_tier()` reads it.

## Definitions

### Price basis

- **Unadjusted close** (`Close`) feeds the mechanical label, the sell-off episodes and the
  price-based candidates. It matches the production label and `index_bear_hedge`'s episodes.
- **Adjusted close** (`Adj Close`) feeds every SPY return used as an outcome, and realised
  volatility. It folds in dividends, so returns are total returns.
- **Credit** uses the HYG/IEF ratio of `Adj Close`, as `lib/regime_watch.py::_credit_change` does.
  Unadjusted HYG drifts down by its distributions.
- **VIX and VIX3M.** The yfinance `Close` of `^VIX` and `^VIX3M`, matched to SPY sessions by exact
  date.
- **Session index.** `i` counts SPY sessions with a close. A date with no SPY close is not a
  session.

### The mechanical state

The state is `lib/mech_regime.py::MechLabeler`, read unchanged. The study writes
`backtests/state_map/spy_vix_mech.csv` (date, spy_close, vix_close) and calls
`MechLabeler.from_csv` on it. No threshold moves.

| Part | Rule, as the code has it |
|---|---|
| BEAR | SPY close below its 50-day SMA and 20-session return below 0 |
| BULL | SPY close above its 50-day SMA and 20-session return above 0 |
| RANGE | Otherwise |
| E-VOL | VIX at or above 30, or VIX up 25% or more over 5 sessions |
| H-VOL | VIX at or above 20, and not E-VOL |
| L-VOL | Otherwise |

A session with `ok` false has no state. It leaves every count and is counted.

**SMA length, a parameter.** The headline is the 50-day SMA above. A twin replaces 50 by 200 in
the BEAR and BULL rules, with the 20-session return and the vol part unchanged. It is labelled
`BEAR200` and is printed beside the headline in Q1 and Q3, never graded.

`MechLabeler`'s window lengths are hard-coded constants (`SMA_WINDOW = 50`). So `BEAR200` needs a
copy of `compute_mech_table` that takes the SMA length as a parameter. `tests/test_state_map.py`
pins the copy, run at length 50, to `MechLabeler` on every session.

### Windows

| Window | Sessions | Use |
|---|---|---|
| Discovery | First usable session to 2015-12-31 | Printed. Its sign enters the bar as a check |
| Test | 2016-01-01 to 2026-09-22 | Every graded verdict |
| Gap | 2026-09-23 to 2026-11-20 | In no population |
| Forward | From 2026-11-21 | The one-shot forward read |

- **No close after 2026-09-22 enters the in-sample run.** The study cuts every series at
  2026-09-22 (`IN_SAMPLE_END`) before it computes anything.
- **Windows past the cut.** A window that needs a later close is dropped and counted.
- **Why 2026-09-22.** Closes after it were seen in the 2026-11-21 bear peek and in the
  regime-watch row (see the plan-time observations).
- **The seal.** 2026-09-22 is also the day before the holdout seal starts.
- **Short-history candidates.** VIX3M starts 2006-07-17 and HYG 2007-04-11. Their test window is
  the same as every other candidate's.
- **Their discovery window** starts at their first session with the full runway.
- **Waiver.** When a discovery window holds fewer than 10 episodes, the discovery check is waived
  and the report says so.

### Sell-off episodes

Episodes come from `scripts/backtest_study/f5_hedging/index_bear_hedge.py::episodes`, imported
unchanged and hash-checked against `EPISODE_DEFS_SHA256`. They run on the unadjusted SPY close.

| Definition | Rule in `EPISODE_DEFS` | Role |
|---|---|---|
| `E-DD8` | Close at least 8% below its 63-session high; ends at the first close back above −2%, or 42 sessions after the last trigger | Headline |
| `E-DD5` | The same with a 5% trigger | Secondary, printed both ways |

- Episodes fewer than 10 sessions apart, trough to next peak, merge (`merge_gap` 10).
- **Trigger, `g`.** The first session whose close is at least 8% below the highest close of the 63
  sessions ending at it: the code's `drawdowns` value at or below −0.08.
- **Onset, `p`.** The session of that 63-session high, latest on a tie. At `g` the rolling high is
  `c_p`, so `g` is also the first session after `p` with a close at or below 0.92 × `c_p`. For
  `E-DD5` read 5% and 0.95.
- **Merged episodes.** `p` is the earliest peak, as the code keeps it. `g` is the trigger of the
  first sub-episode.
- **Trough.** As the code defines it, earliest on a tie.
- **Unclosed episodes.** An episode whose trough is not yet fixed at the 2026-09-22 cut (the
  code's `closed` is false) is dropped and counted.
- **Window of an episode.** The window that holds its onset `p`. An episode needs `g` on or before
  2026-09-22.
- **Exclusion zone.** Sessions from `p − 21` to `trough + 21`, for every episode of the same
  definition. Zones are read from the episodes of both windows.
- **Follow-on episode.** One whose 10-session lead window touches an earlier episode's exclusion
  zone, in either window. Its lead window sits in the aftermath of the last fall, when VIX is
  still high.
- **Follow-ons** leave the graded Q2 cells and are printed in a twin that keeps them.

`E-DD8` is the headline because an 8% fall is the size a bear spread is meant for. `E-DD5` holds
more episodes, and more of them are noise.

### Q2 candidates, fixed here

Each candidate is a state that is on or off at the close of session `t`. It reads closes on or
before `t`, never later. A candidate with too little history at `t` is missing.

| Label | On at the close of `t` when | First session with the full runway |
|---|---|---|
| `C1` | VIX close at or above 20 | The first SPY session, 1993-01-29 |
| `C2` | VIX close's midrank percentile in the 252 VIX closes on the SPY sessions strictly before `t` is 0.80 or above | After 252 prior SPY sessions |
| `C3` | VIX close up 25% or more on the VIX close 5 sessions earlier | After 5 prior SPY sessions |
| `C4` | VIX close above the VIX3M close | 2006-07-17 |
| `C5` | SPY close below the mean of the 50 SPY closes ending at `t` | The 50th SPY session |
| `C6` | SPY close below the mean of the 200 SPY closes ending at `t` | The 200th SPY session |
| `C7` | SPY close below the SPY close 20 sessions earlier | After 20 prior SPY sessions |
| `C8` | 21-session realised vol above the VIX close | After 21 SPY returns |
| `C9` | HYG/IEF `Adj Close` ratio down more than 1% over 20 sessions | 20 sessions after HYG starts, 2007 |

- **Midrank percentile (`C2`).** (count below + half the count equal) / 252, as `tail_breach`'s
  `X2`. It is the share of the prior year's closes below today's, with ties counted half.
- **Realised vol (`C8`).** `√(mean of r²) × √252 × 100` over the 21 log returns of `Adj Close`
  ending at `t`.
- **Credit (`C9`).** The `regime_confirm` `C-CR` rule and `regime_watch` code: the change is
  rounded to 9 decimals, so −1.0% exactly is not on.
- **Thresholds.** Each comes from a rule the repo already uses.

  | Source | Candidates |
  |---|---|
  | The mech label's H-VOL line and E-VOL jump | `C1`, `C3` |
  | The mech label's BEAR halves | `C5`, `C7` |
  | `regime_confirm`'s conditions | `C6`, `C9` |
  | `tail_breach`'s predictors | `C2`, `C4`, `C8` |

- **One new number.** `C2`'s 0.80 line. It was set before any figure was read.
- **VIX level buckets**, printed only:

  | Bucket | VIX close |
  |---|---|
  | Low | below 15 |
  | Mid | 15 to below 20 |
  | High | 20 to below 30 |
  | Extreme | 30 and up |

### Lead and coincident windows

| Window | Sessions | Role |
|---|---|---|
| Lead, `W` = 10 | `p − 10` to `p − 1` | Headline |
| Lead, `W` = 5 and `W` = 21 | `p − W` to `p − 1` | Parameters, printed both ways |
| Coincident | `p` to `g` | Splits `COINCIDENT` from `NO-FORECAST`, for `C1`–`C4`, `C8`, `C9` |
| Trigger-anchored lead | `g − W` to `g − 1` | Printed only |

### Matched calm days

For each episode `e`, its **control sessions** are every session `d` that meets all of these:

- `d` lies in the same window as `p`, and within 252 sessions of `p` on either side.
- `d` lies in no exclusion zone of any episode of the same definition, in either window.
- The control lead window `d − W` to `d − 1` also lies in no exclusion zone.
- The control lead window has every candidate value the episode's has.
- For the coincident contrast only, `d` to `d + (g − p)` lies in no exclusion zone.

An episode with fewer than 20 control sessions leaves the cell and is counted.

### The Q2 statistic

For candidate `k` and episode `e`:

- `f_e` is the share of the lead window's sessions on which `k` is on.
- `f_d` is the same share over the control lead window of control session `d`.
- **Lift**, `x_e = f_e − mean of f_d` over `e`'s controls.

`L_k` = 100 × (mean of `x_e` over the cell's episodes). It is in percentage points of sessions. An
`L_k` of +20 means the candidate was on in 20 more sessions per 100 before a top than in the
matched calm windows.

A positive `L_k` means the candidate was on more often in the 10 sessions before a top than in
calm stretches near it. It says nothing about how often the candidate fires without a top.

The **coincident lift** `L_k^coin` is the same, with the coincident window `p` to `g` and control
windows `d` to `d + (g − p)`.

An episode with any missing value of `k` in its window leaves `k`'s cell only, and is counted.

**A built-in bias, disclosed.** The onset `p` is a 63-session high by construction.

- In the lead window SPY is therefore usually above its 50-day SMA and up over 20 sessions.
- So `C5` and `C7` are pushed toward a negative lead lift.
- They are pushed toward a positive coincident lift as SPY falls to `g`.
- `C6` can still be on at a 63-session high, in a rally inside a longer fall.

The bias is part of the question. A price rule that only turns on once the fall is under way is
not early warning.

**`C5`, `C6` and `C7` leave the coincident family.** A fall of 8% from a 63-session high makes
"below the 50-day SMA" and "20-session return below 0" close to certain by `g`, and "below the
200-day SMA" far more likely. Their coincident lift is largely true by construction. It prints as
`COINCIDENT (mechanical)`, and the Q2 READ ignores it.

### The other side of Q2, printed only

The lift reads from known tops backward. Two tables look forward from the variable instead. They
carry no verdict, enter no Holm family and no PBO grid.

| Table | What it prints, per candidate, test and discovery windows |
|---|---|
| `TURN-ON` | Of the candidate's off-to-on turn-ons, the share followed by an `E-DD8` trigger `g` within 21 sessions. Beside it, the share of all sessions followed by a trigger within 21 sessions |
| `G-LEAD` | The lift computed on the trigger-anchored lead window `g − W` to `g − 1`, with the same controls |

A turn-on is a session on which the candidate is on and was off the session before. Turn-ons
inside an exclusion zone are counted separately.

### Q3 signals and outcomes

**Onset of a state.** A session `D` on which the state holds, where none of the 10 sessions before
`D` held it and all 10 had a state. The re-arm is 10 sessions, the same as `merge_gap`.

| Label | State | Role |
|---|---|---|
| `S-BEAR` | mech direction BEAR | Graded |
| `S-EVOL` | mech vol E-VOL | Graded |
| `S-BEAR200` | `BEAR200` | Printed only |
| `S-BOTH` | BEAR and E-VOL on the same session | Printed only |

**Entry.** The label is known at `D`'s close, so the trade is taken at the close of `D + 1`.

| Outcome | Definition | Role |
|---|---|---|
| `r_h` | `ln(A[D+1+h] / A[D+1])`, `A` the `Adj Close`, `h` in 5, 10, 21 | Graded |
| `ff_h` | `min(0, min(A[D+2 … D+1+h]) / A[D+1] − 1)`, the further fall to come | Printed only |
| `r_h^0` | `r_h` from `D`'s close instead of `D + 1`'s | Printed only |
| `done` | For an onset inside an `E-DD8` episode: `(c_p − c_{D+1}) / (c_p − c_trough)` on the unadjusted close | Printed only |

`done` is the share of the episode's eventual peak-to-trough fall that had already happened at the
entry close.

**Other days.** Every test-window session that is not an onset of the same signal, with its own
`r_h` from its next close, `ln(A[t+1+h] / A[t+1])`.

**The Q3 statistic.** For signal `s` and horizon `h`:

`D_{s,h}` = mean `r_h` over onsets − mean `r_h` over other days.

A negative `D` means SPY did worse after the signal than after an ordinary day.

**Cells.**

| Cell | Signal | `h` |
|---|---|---|
| `B5`, `B10`, `B21` | `S-BEAR` | 5, 10, 21 |
| `V5`, `V10`, `V21` | `S-EVOL` | 5, 10, 21 |

`B10` is the headline cell. It is the direct test of "the bear state prints and the move is gone",
over about two weeks.

**Clusters.** Onsets 10 sessions apart can still share part of a 10- or 21-session window. So
every Q3 cell groups its onsets by the calendar month of `D`. A cluster is one month's onsets. The
bootstrap resamples clusters, the report prints each cell's cluster count, and the floor of 10
counts clusters, not onsets.

### Q4 structure

On each `S-BEAR` and `S-EVOL` onset with `D` from 2022-02-01, the study prices one fixed bear put
spread.

| Item | Rule |
|---|---|
| Spot | SPY unadjusted close on `D + 1` |
| Long leg | 1 put, strike nearest spot × 1.00 on the listed grid |
| Short leg | 1 put, strike nearest spot × 0.95 on the listed grid |
| Expiry | `mechanical_baseline.rule_expiry(D + 1, 30)`: the standard monthly expiry nearest 30 DTE |
| Entry | Both legs at the closing mid of `D + 1`, via `simulate.entry_day_fill` |
| Exit | The close of `D + 1 + h`, `h` in 5, 10, 21, marked by `simulate.junk_day_mark`; intrinsic value if expiry comes first |
| R | P&L over the entry debit, net of commission |

- The strike walk is `selloff_put_diagonal`'s put walk on `mechanical_benchmark`'s listing grid.
- The defined-risk clamp is `helpers._defined_risk_bounds`.
- A spread that would open as a credit is refused and counted.
- A leg with no price is counted as unpriced, and the trade leaves the cell.

### Q5 slices

- **State at entry.** The record's `mech_direction` and `mech_vol`, from `lib/book.py`'s labeler.
- **Direction.** `ticker_class.direction(structure)`: bull or bear. Other rows print as "other".
- **Source.** Real-priced rows and proxy (`tweak`) rows, split. `bs` rows are out.
- **Lag bin.** Days from the signal date to the analysis row's `created_datetime`, binned as
  [`market_read`](market_read.md) defines it (LIVE, NEAR, RETRO, UNKNOWN). A RETRO row, written
  more than a week late, came from a model that may know what came next.
- **Figures per cell.** Rows, signal dates, mean [R](../../../glossary.md#r), mean
  [MFE and MAE](../../../glossary.md#mfe), [capture](../../../glossary.md#capture), and a
  date-clustered [CI95](../../../glossary.md#ci95-date-clustered-bootstrap) on mean R.

### Terms used here

| Term | Meaning |
|---|---|
| Lift | How much more often a candidate was on before a top than in matched calm windows, in percentage points of sessions |
| Exclusion zone | The sessions from 21 before an episode's peak to 21 after its trough. Calm days never fall in one |
| Midrank | A percentile that counts ties as half below |
| Holm | A step-down correction for testing several things at once. The smallest p faces the strictest bar |
| PBO / CSCV | The chance that the best cell of a grid in one half of the history ranks below the median in the other half, over every split. `lib/pbo.py` holds the method and its source |
| THIN | Fewer units than the floor. Counts print, figures carry the flag or are withheld, and nothing is concluded |
| MFE / MAE | The best and worst open P&L a position reached ([glossary](../../../glossary.md#mfe)) |
| Capture | Sum of R over sum of MFE ([glossary](../../../glossary.md#capture)) |

## Dependencies

- `backtests/state_map/` SPY, `^VIX`, `^VIX3M`, HYG and IEF (date, close, adj_close), fetched by
  the module from yfinance with `auto_adjust=False`, the `tail_breach` pattern. `end` is exclusive,
  so today's bar is never fetched. `--refresh` refetches.
- `backtests/mech_regime/spy_base_rate_daily.csv` and `spy_vix_daily_full.csv`, read only by the
  cross-checks in the gates.
- `backtests/regime_watch/history.csv`, read only by gate GL.
- `lib/mech_regime.py::MechLabeler`, unchanged.
- `scripts/backtest_study/f5_hedging/index_bear_hedge.py`: `EPISODE_DEFS`, `EPISODE_DEFS_SHA256`,
  `episodes`, `drawdowns`, unchanged.
- `scripts/backtest_study/lib/pbo.py::cscv` and `ratio_metric`.
- `scripts/backtest_study/f1_selection/benchmark/ticker_class.py`: `holm` and `direction`.
- `scripts/backtest_study/lib/era.py`: `requested_era`, `drop_sealed`, `seal_line`,
  `require_dates`, `SEAL_START`, `SEAL_LIFTED`.
- `scripts/backtest_study/lib/book.py::load_book`, for Q5 only.
- Q4 only: `scripts/backtest/simulate.py` (`entry_day_fill`, `junk_day_mark`, `_cost_knobs`),
  `helpers._defined_risk_bounds`, `mechanical_baseline.rule_expiry`, `mechanical_benchmark`'s
  listing grid and the SPY files in `backtests/option_history_cache/`. Contracts missing from the
  cache are listed by a `plan()` for the study-legs collector. The list follows the rule above,
  never an outcome.

## Population and basis, fixed here

- **Q1–Q4 era.** The inputs carry no prompt version. The report prints `era: current (inputs are
  unversioned market closes)`.
- **Q5 era.** `era.requested_era()` and `load_book(era=…)`, which refuses a wrong or mixed era
  (exit 3). v4 is the population. `--era v3` runs Q5 only, as a replication, and prints that Q1–Q4
  were not re-run. The v3 report is copied aside as `-v3-<date>` before the v4 `-latest.txt` is
  restored.
- **Seal.** The [holdout seal](../../f4_deployment/holdout_seal.md) binds signal dates of emitted
  plays. Q1–Q4 read no play, flow signal or backtest row, so it does not bind them, as in
  `tail_breach`. Q5 loads the book with no `sealed_read`, so every signal date from
  `era.SEAL_START` (2026-09-23) is withheld. This study is not in `era.SEALED_READERS`.
- **Q5 rows.** Real and `tweak` rows, `fill_trusted` only, pending open rows out. Every drop is
  counted. `era.require_dates` refuses fewer than 30 pre-seal signal dates (exit 2).
- **Report header.** Era, the three windows, the seal state, the git sha, the dirty flag, the
  input files and each series' first and last date read.
- **Q2 population.** `E-DD8` episodes, follow-ons out, with `p` in the test window and `g` on or
  before 2026-09-22.
- **Q3 population.** Onsets with `D` in the test window and `D + 1 + h` on or before 2026-09-22.
- **Q4 population.** Onsets from 2022-02-01 whose exit close is on or before 2026-09-22.
- **Forward population.** Defined under the verdicts, below.

## Plan-time observations, disclosed

Every check below was made on 2026-11-21, before this file was written. The drafter counted rows
and date ranges. No return, lift, hit rate or episode was computed.

### Inputs on disk

| File | Rows | From | To |
|---|---|---|---|
| `backtests/tail_breach/SPY.csv` | 8,507 | 1993-01-29 | 2026-11-13 |
| `backtests/tail_breach/VIX.csv` | 9,288 | 1990-01-02 | 2026-11-13 |
| `backtests/tail_breach/VIX3M.csv` | 5,116 | 2006-07-17 | 2026-11-13 |
| `backtests/regime_confirm/HYG.csv` | 4,914 | 2007-04-11 | 2026-10-20 |
| `backtests/regime_confirm/IEF.csv` | 6,096 | 2002-07-30 | 2026-10-20 |
| `backtests/mech_regime/spy_base_rate_daily.csv` | 8,471 | 1993-01-29 | 2026-09-24 |
| `backtests/mech_regime/spy_vix_daily_full.csv` | 873 | 2023-06-01 | 2026-11-20 |
| `backtests/regime_watch/history.csv` | 254 | 2025-10-22 | 2026-11-20 |
| SPY files in `backtests/option_history_cache/` | 15,768 | expiry 2022-02-25 | expiry 2027-09-17 |

The drafter saw the last row of each file while counting. Those closes fall after 2026-09-22, in
the gap or the forward window.

### The 2026-11-21 bear peek

The [entry](../../../current.md#2026-11-21--bear-strategies-in-2026-peek-ungraded-sealed-dates)
read sealed play rows at the operator's request. It is logged in the seal's
[disclosed reads](../../f4_deployment/holdout_seal.md#disclosed-reads-of-sealed-dates).

| What it showed | Value |
|---|---|
| SPY, 2026-10-06 to 2026-11-20 | 779.09 to 689.81, −11.5% |
| v4 bear plays, 2026-01-01 to 09-22 | −$76,819 |
| v4 bear plays, sealed window | +$90,375 |

- **What it spends here.** The current sell-off is known. It is in the gap and in no population.
- **Q5.** The 2026 pre-seal figure above is the bear rows of Q5's own population, summed in
  dollars. Q5 is descriptive, so this does not change a verdict.

### The regime-watch row for 2026-11-20

| Field | Value |
|---|---|
| Status | CONFIRMED, BEAR streak 16 |
| Mech state | BEAR, E-VOL |
| VIX | 35.89 |
| VIX / VIX3M | 1.16 |
| SPY against its 200-day SMA | 689.81 against 732.76 |
| HYG/IEF 20-session change | −1.41% |
| Confirmations on | 4 of 4 |

So on that date `C1`, `C4`, `C6` and `C9` were on. The date is in the gap.

### Reads of nearly the same events

- **`regime_confirm`'s exploration (2026-10-21), on 97 SPY mech BEAR flips.** The median 60-day
  return from the flip was +3.9%. The share followed by a 10% fall was 11%. 56% of BEAR runs lasted
  3 sessions or fewer. Those flips are close to Q3's `S-BEAR` onsets, with no re-arm. Its horizon
  of 60 sessions is longer than any of Q3's.
- **The vol-expansion count (2026-11-06,
  [entry](../../../current.md#2026-11-06--long-straddles-and-backspreads-after-a-vol-expansion-untested-one-spy-study-proposed),
  [next-steps item 18](../../../next-steps.md#waiting-on-the-operator)).** It read 140 E-VOL
  onsets from 1993 to 2022, with a 5-session re-arm. SPY's absolute move after them was no larger,
  relative to implied, than on other days, and VIX usually fell. It also printed SPY and VIX moves
  after 23 onsets from 2023-06 to 2026-09-22, and VIX fell in 15 of the 23. Those onsets overlap
  `S-EVOL` in both windows. That count read absolute moves, while Q3 reads signed returns.
- **`tail_breach` (2026-11-14).** Breaches of twice the VIX-implied move ran at a steady rate in
  2024–2026. Its forecast was `UNDERPOWERED` at 9 test episodes against a floor of 10.
  `tail_breach_intraday`'s VIX forecast printed `NO-FORECAST`.

### Studies that already read these episodes and candidates

| Study | What it read that this study also reads |
|---|---|
| [`index_bear_hedge`](../../f5_hedging/index_bear_hedge.md) | The `E-DD` episodes of 2023–2026, with the book's hedge P&L printed per episode |
| [`tail_rebound`](tail_rebound.md) | SPY's path after tail falls from 1993, the 2023–2026 falls among them |
| [`regime_confirm`](regime_confirm.md) | `C1`, `C4`, `C6` and `C9` at mech BEAR flips, test window included |
| [`tail_breach`](tail_breach.md) | `C2`, `C4` and `C8` as its predictors `X2`, `X3`, `X4`, on 2024–2026 |

So part of the test window is not blind for these candidates. The candidate list was taken from
the plan, not from those results.

### Prior verdicts on nearby questions

| Study | Verdict | What it says for this study |
|---|---|---|
| [`market_read`](market_read.md) | `NO-FORECAST` | The model's MARKET label does not forecast SPY |
| [`baseline_read`](baseline_read.md) | `NO-FORECAST` | Heavy hedging follows a fall and does not lead it |
| [`direction_hit`](../signal/direction_hit.md) | `NULL` | Nothing at entry predicts the underlying's direction |
| [`regime_map`](regime_map.md) | Tier A on dip dates positive, both eras | Tier A did well on falling-market dates |
| [`regime_confirm`](regime_confirm.md) | `RETRO-NULL` | A persisting BEAR flip with stress signs did not beat every flip at calling a 10% fall |
| [`tail_rebound`](tail_rebound.md) | `NO-EDGE` | No rebound edge after SPY tail falls, 1993 on |
| [`selloff_put_diagonal`](selloff_put_diagonal.md) | `NO-EDGE` (provisional) | A sell-off entry paid, but no more than calm weeks |

`regime_map`'s dip date is SPY below its 50-day SMA, which is `C5`. `selloff_put_diagonal` priced
SPY puts on `E-DD5` sell-offs from 2022, so Q4's ground is partly read.

**Q5's ground is partly read too.** The 2026-10-22 descriptive pass found that bull plays on
market BULL dates lost and bear plays on those dates won. It read 83 sealed rows. The 2026-10-12
read found that v4's A/B R tracks the underlying's direction.

### General knowledge, not counted

The drafter knows from public market history that the test window holds roughly ten falls of 8%
or more, among them those of 2020 and 2022. No episode was counted on the data. The Q2 floor is 10
test episodes, so `UNDERPOWERED` on the headline is a real possibility. The floor was set without
knowing the count.

**There is no fallback.** If `E-DD8` prints `UNDERPOWERED`, `E-DD5` stays ungraded. Its words
print as "secondary, not graded" either way.

### A prior, not evidence

The plan expects the confirmed bear state to be coincident, not leading. The likely useful output
is Q3: how much fall is left after the signal, split by VIX state.

## What it compares

| Object | Object type | What it is | Role |
|---|---|---|---|
| Q1 tables | descriptive cut | Days per state, run lengths, transitions | Printed only |
| `C1`–`C9` | arm | One Q2 candidate each, lead lift `L_k` on `E-DD8`, `W` = 10 | Primary, Holm m = 9 |
| `C1`–`C4`, `C8`, `C9` coincident | arm | Coincident lift `L_k^coin` | Holm m = 6; only splits `COINCIDENT` from `NO-FORECAST` |
| `C5`–`C7` coincident | descriptive cut | Coincident lift, true by construction | Printed as `COINCIDENT (mechanical)` when it would pass; ignored by the READ |
| `TURN-ON`, `G-LEAD` | descriptive cut | The forward-looking side of Q2 | Printed only |
| Calm days | control | Each episode's matched control sessions | The reference for every lift |
| `B5`–`B21`, `V5`–`V21` | arm | Q3 cells, `D_{s,h}` | Primary, Holm m = 6; `B10` is the headline |
| Other days | control | Every non-onset test session | The reference for every `D` |
| Q4 trades | descriptive cut | One put spread per onset from 2022, real prices | Printed with THIN, no verdict |
| Q5 slices | descriptive cut | Play rows by state, direction, source and lag bin | Printed only, no verdict |
| `FORWARD` | population scope | Q2 and Q3 on the forward population | Forward verdict |

### Q1, the state map

Printed for the discovery and test windows separately, for the headline label and for `BEAR200`:

- sessions in each of the nine cells (direction × vol), and unlabelled sessions;
- run length per direction and per vol: count, median, mean, 90th percentile, longest;
- day-to-day transition counts and shares, for direction, for vol and for the full cell;
- the share of sessions in each direction by calendar year.

### Q2, early warning

For each candidate, the test-window lead lift is graded. Printed beside it, never graded:

- `W` = 5 and `W` = 21;
- `E-DD5` episodes, with its own verdict words marked "secondary, not graded";
- the twin that keeps follow-on episodes;
- the discovery-window lift and its CI;
- the VIX level buckets in lead windows and in control windows;
- per episode: `p`, `g`, trough, control count and each candidate's lead share;
- the `TURN-ON` and `G-LEAD` tables;
- `C5`–`C7` coincident lifts, marked mechanical.

### Q3, after the signal

Each cell's `D` is graded. Printed beside it, never graded:

- `S-BEAR200` and `S-BOTH`, at each `h`;
- `ff_h` against other days, and the share of onsets with a further fall of 3% and of 5%;
- `r_h^0`, the same-close entry;
- `done`, per onset and its median, for `E-DD8` and `E-DD5` episodes;
- `S-BEAR` cells split by vol state at the onset (L-VOL, H-VOL, E-VOL);
- a 5-session re-arm;
- the discovery-window `D` and its CI;
- `D` with 42-session blocks for other days.

### Q4, real prices

Per trade: `D`, strikes, expiry, entry debit, R at each `h`, and SPY's `r_h`. Per cell (signal ×
`h`): trades priced, trades unpriced, mean R. A cell with fewer than 10 priced trades prints THIN.
Q4 prints no verdict word in any case.

**Await gate.** Q4 prices nothing until every trade has a cache file or a recorded refusal.
Until then it prints its census and `AWAITING SCRAPE`. Q1–Q3 and Q5 run regardless.

### Q5, the book by state

LIVE and RETRO are split first, before any other cut. Every table is printed three ways: LIVE,
RETRO, and all lag bins together.

| Table | Rows |
|---|---|
| Direction × mech direction | bull, bear × BULL, RANGE, BEAR |
| Direction × mech vol | bull, bear × L-VOL, H-VOL, E-VOL |
| Direction × cell | bull, bear × the nine cells |

Each table splits real and `tweak` rows. A cell with fewer than 20 rows or fewer than 10 signal
dates prints its counts and THIN, and its figures are withheld.

## How it is judged

### Bootstrap

- **Q2.** Episodes are the unit. Each draw resamples the cell's test episodes with replacement,
  as many as the cell holds. An episode carries its own lift, so its controls travel with it.
- **Q2 shared draws.** One set of draws over episode indices, with each cell using its members.
- **Q3.** Calendar-month clusters of onsets are the unit. Each draw resamples the cell's clusters
  with replacement, as many as the cell holds.
- **Q3 other days.** In the same draw, other days are resampled in fixed 21-session blocks
  (`i // 21`), as `market_read` does.
- **Q3 shared draws.** One set of draws over cluster indices, with each cell using its members.
- 10,000 draws, seed 20261121.
- **Why not days.** Lead windows, control windows and forward returns overlap across neighbouring
  days. A per-day bootstrap would treat them as independent.

### CI and p-values

- **CI.** The 2.5th and 97.5th percentiles of the draws. Each CI prints its half-width.
- **p-value.** Two-sided: twice the smaller of the share of draws at or below 0 and the share at or
  above 0, capped at 1.

### Multiple comparisons

| Family | Members | m |
|---|---|---|
| Q2 lead | `C1`–`C9`, lead lift | 9 |
| Q2 coincident | `C1`–`C4`, `C8`, `C9`, coincident lift | 6 |
| Q3 | `B5`, `B10`, `B21`, `V5`, `V10`, `V21` | 6 |

Holm at 0.05 within each family, with `ticker_class.holm`. Q1, Q4 and Q5 test nothing.

Controls are shared by nearby episodes, so lifts are not fully independent. The episode bootstrap
does not remove this, and the report says so.

### PBO / CSCV

The selection being guarded against is "pick the best cell from a grid". `lib/pbo.py::cscv` runs
once per grid, over the whole history from 1995.

| Grid | Configs | N | Per-period value |
|---|---|---|---|
| Q2 | `C1`–`C9` × `W` in 5, 10, 21, on `E-DD8` | 27 | [sum of lead lifts, episode count] for episodes with `p` in the year |
| Q3 | `S-BEAR`, `S-EVOL` × `h` in 5, 10, 21 | 6 | [sum of `z`, onset count] for onsets in the year |

- **Only graded configs.** `S-BEAR200` and `S-BOTH` are printed only, so they stay out of the Q3
  grid and cannot veto. `lib/pbo.py` needs at least 2 configs, so N = 6 is valid.
- **Same population.** The Q2 grid uses the graded cell's episodes, follow-ons out.
- **Rows.** Calendar years, T = 32, cut into S = 16 blocks of two years. The data spans 34 years,
  so the two earliest (1993 and 1994) are trimmed. The trim is by date only.
- **Metric.** `pbo.ratio_metric`, so a half's value is the mean over its episodes or onsets.
- **Empty years.** A year with no episode or onset is [0, 0]. It adds nothing to either sum.
- **Short histories.** `C4` and `C9` are [0, 0] before their first year with the full runway. A
  half holds 16 years and at most 12 fall before 2007, so every half has data for them.
- **Q3's `z`.** `(m_h − r_h) / sd_h` per onset. It puts the three horizons on one scale, and a
  larger `z` means more room left.
- **`z` uses the whole span.** `m_h` and `sd_h` are the mean and standard deviation of `r_h` over
  every session from 1993 to the cut, in both halves. That is harmless here: they shift and scale
  every onset of a horizon alike, so a ranking within a horizon does not change.

| PBO | Reading |
|---|---|
| ≤ 0.25 | Supports a verdict |
| 0.25 – 0.50 | The verdict prints with "selection fragile" |
| > 0.50 | Veto. Every Q2 candidate prints `NO-FORECAST`, or every Q3 cell prints `NULL`, with "PBO veto" |

These are the `ticker_class` and `ticker_pattern` thresholds. PBO enters only as a veto, never as
evidence.

## Gates

- **GE, inputs.** All five series exist or can be fetched, none is empty, and SPY reaches
  2026-09-22. Any failure refuses (exit 3).
- **GB, basis.** The `tail_breach` checks: SPY's `Close` to `Adj Close` ratio never rises by more
  than 0.01% and never moves by more than 2% between sessions. SPY close and VIX agree with
  `spy_base_rate_daily.csv` within 0.5% on every common date. Any failure refuses (exit 3).
- **GL, labels.** The study's labels match `spy_vix_daily_full.csv` run through `MechLabeler`, and
  the `mech_direction` and `mech_vol` of `regime_watch/history.csv`, on common dates up to
  2026-09-22. More than 1% of common dates disagreeing refuses (exit 3). Every disagreement prints.
- **GH, episode definitions.** `index_bear_hedge.episode_defs_hash()` equals
  `EPISODE_DEFS_SHA256`. A mismatch refuses (exit 5).
- **GR, episode reconciliation.** On `spy_vix_daily_full.csv` cut at 2026-09-22, the study's
  `E-DD8` and `E-DD5` episodes match `index_bear_hedge`'s on peak and trough. Only episodes whose
  peak is at least 63 sessions after 2023-06-01 are compared. A mismatch refuses (exit 3).
- **GX, no lookahead.** Every candidate and every label at `t` reads closes on or before `t`.
  `tests/test_state_map.py` changes or removes every later close and requires identical values.
  Each run recomputes 60 evenly spaced sessions on series cut at that session, and stops with an
  error on any difference.
- **GC, the cut.** The in-sample report is identical when every close after 2026-09-22 is changed.
  The test file checks it.
- **GN, floors.** Below its floor a cell prints `UNDERPOWERED`. Forward cells print `STILL-OPEN`
  instead.
- **Q5 era.** `load_book` refuses a wrong or mixed era (exit 3) and `era.require_dates` a thin one
  (exit 2).

| Population | Floor |
|---|---|
| Q2 cell, test | 10 episodes with a defined lift, each with at least 20 controls |
| Q3 cell, test | 10 calendar-month clusters of onsets with a closed window |
| Discovery check | 10 episodes, or 10 onset clusters, else the check is waived and the report says so |
| Q4 cell | 10 priced trades, else THIN |
| Q5 cell | 20 rows on 10 signal dates, else THIN |
| Forward Q2 cell | 10 forward episodes |
| Forward Q3 cell | 10 forward onset clusters |

**Why 10.** It is the episode floor `tail_breach` used. Below about 10 units, a resampled draw can
hold only two or three episodes, and the CI measures which ones were drawn rather than the effect.

## Bar for a candidate

No result here makes a candidate rule. A `LEADS` or a `ROOM-LEFT` files "to be tested" in
[`deployment-evidence.md`](../../../deployment-evidence.md), pending the forward read.

## Verdicts, worded now

### Q2, per candidate

The first matching row wins.

**`UNDERPOWERED`.** Fewer than 10 test episodes with a defined lift. The census prints and nothing
is concluded.

**`LEADS`.** All four hold:

1. The lead lift's CI lower bound is above 0.
2. Its Holm-adjusted p is below 0.05 (lead family, m = 9).
3. The discovery-window lift is above 0, or the discovery check is waived.
4. The Q2 PBO is 0.50 or below.

**`COINCIDENT`.** Not `LEADS`, the candidate is one of `C1`–`C4`, `C8`, `C9`, and all three hold:

1. The coincident lift's CI lower bound is above 0.
2. Its Holm-adjusted p is below 0.05 (coincident family, m = 6).
3. The Q2 PBO is 0.50 or below.

**`COINCIDENT (mechanical)`.** For `C5`, `C6` or `C7` only: not `LEADS`, and their coincident lift
meets conditions 1 and 3 above on its raw p below 0.05. It is printed, never graded.

**`NO-FORECAST`.** Otherwise. This includes a negative lead lift, every candidate under the PBO
veto, and `C5`–`C7` when they are not `LEADS`, whatever their mechanical line prints.

In plain words:

- `LEADS` means the variable was on more often in the 10 sessions before a top. This says nothing
  about how often it fires without a top.
- `COINCIDENT` means it turned on during the fall to the 8% line, not before the top. It marks a
  fall in progress, which the mech label already does.
- `NO-FORECAST` means neither showed.

**Q2 READ.** `LEADS` if any candidate prints `LEADS`. Otherwise `COINCIDENT` if any prints
`COINCIDENT`, which `COINCIDENT (mechanical)` never counts as. Otherwise `NO-FORECAST`, unless all
nine print `UNDERPOWERED`, which gives `UNDERPOWERED`.

### Q3, per cell

The first matching row wins.

**`UNDERPOWERED`.** Fewer than 10 test onset clusters with a closed window. The census prints and
nothing is concluded.

**`ROOM-LEFT`.** All five hold:

1. The CI upper bound of `D` is below 0.
2. Its Holm-adjusted p is below 0.05 (m = 6).
3. The mean onset `r_h` is below 0.
4. The discovery-window `D` is below 0, or the discovery check is waived.
5. The Q3 PBO is 0.50 or below.

**`TOO-LATE`.** All four hold:

1. The CI lower bound of `D` is above 0.
2. Its Holm-adjusted p is below 0.05 (m = 6).
3. The discovery-window `D` is above 0, or the discovery check is waived.
4. The Q3 PBO is 0.50 or below.

**`NULL`.** Otherwise, printed with the half-width.

In plain words:

- `ROOM-LEFT` means SPY fell after the signal, and did worse than after an ordinary day. A bear
  trade opened at the next close had a fall left to catch.
- `TOO-LATE` means SPY did better after the signal than after an ordinary day. The fall was over
  and a bear trade opened on the signal lost ground.
- `NULL` means no difference from an ordinary day was shown.

**Why `ROOM-LEFT` also needs a falling mean.** A put spread pays on a fall, not on lagging the
market's usual drift. When `D`'s CI is below 0 but the mean onset `r_h` is 0 or above, the cell
prints `NULL` with the note "below normal drift, no fall".

**Q3 READ** is `B10`'s verdict. The other five cells print their own words.

### Forward

- **Opens 2026-11-21.** One shot, for Q2 and Q3, on frozen definitions. No discovery check and no
  PBO veto apply forward, because nothing is selected.
- **Forward Q2 episodes.** `E-DD8` episodes whose peak `p` is at least 11 sessions after
  2026-11-20, so the whole lead window is forward.
- **The current sell-off.** An episode that merges with one peaking on or before 2026-11-20 is
  part of the current sell-off and is out.
- **Its exclusion zone.** The current episode's trough is fixed on the first forward run at which
  the code marks it closed. Its zone, to trough + 21, then applies to forward controls and to the
  follow-on rule. Until then no forward control is drawn.
- **Forward controls.** Forward sessions within 252 sessions of `p`, under the same calm-day rule.
- **Forward Q3 onsets.** Onsets on or after 2026-11-21 whose 10 re-arm sessions also fall on or
  after 2026-11-21. So the BEAR and E-VOL runs in force on 2026-11-20 never count.
- **Onsets inside the current zone.** Forward onsets inside the current episode's exclusion zone
  leave the graded forward cell. They print in a split of their own.
- **Forward other days.** Forward sessions.
- **Holm.** The same families, m = 9, 6 and 6.
- **Words.** The in-sample tokens, with `STILL-OPEN` in place of `UNDERPOWERED`. A cell stays
  `STILL-OPEN` until it reaches its floor of 10.
- **Verdict of record.** The first forward run in which a cell prints a token other than
  `STILL-OPEN`. Later forward runs are descriptive.
- **Expected wait.** An 8% sell-off comes about once a year, so forward Q2 needs a decade or more.
  Q3 onsets come more often. `STILL-OPEN` is the expected forward word for years.

### The banner

The report's section titled VERDICT prints:

```
>>> state_map Q2 READ (state variables before E-DD8 onsets, 10-session lead, test 2016-01-01 to 2026-09-22): LEADS | COINCIDENT | NO-FORECAST | UNDERPOWERED <<<
>>> state_map Q2 CANDIDATES (Holm m=9): C1 <w> C2 <w> C3 <w> C4 <w> C5 <w> C6 <w> C7 <w> C8 <w> C9 <w> <<<
>>> state_map Q3 READ (B10: SPY 10 sessions after a mech BEAR onset vs other days, test 2016-01-01 to 2026-09-22): ROOM-LEFT | TOO-LATE | NULL | UNDERPOWERED <<<
>>> state_map Q3 CELLS (Holm m=6): B5 <w> B10 <w> B21 <w> V5 <w> V10 <w> V21 <w> <<<
>>> state_map PBO: Q2 <value> Q3 <value> <<<
>>> state_map Q4 (SPY put spread on Q3 signals, 2022 on): DESCRIPTIVE, THIN <<<
>>> state_map FORWARD (episodes and onsets after 2026-11-20): Q2 <w> Q3 <w> <<<
```

Q4 prints `DESCRIPTIVE` without THIN only when every cell holds 10 priced trades. Q1 and Q5 print
no banner line.

## Anti-tuning

- **Fixed here, the inputs.** The mech label and its thresholds, the episode definitions, the nine
  candidates and their thresholds, and the windows and their dates.
- **Fixed here, the design.** The lead and coincident windows, the calm-day rule, the follow-on
  rule, the re-arm, the month clusters, the horizons, the D + 1 entry and the Q4 structure.
- **Fixed here, the judging.** The floors, the seed, the blocks, the Holm families, the PBO grids
  and thresholds, and the verdict words.
- The parameters printed both ways (`E-DD5`, `W` of 5 and 21, `BEAR200`) and every printed-only
  cut appear as they fall. None is used to re-grade.
- No other candidate, threshold, horizon, episode definition or window is graded.
- A result on Q4 or Q5 never selects a Q2 candidate or a Q3 cell.
- The in-sample run reads no close after 2026-09-22, and the forward read opens on 2026-11-21. No
  later run moves either date.
- This registration becomes immutable in substance once it is registered. Editorial consolidation
  only after that.

## What could ship

Nothing ships from this study.

- A `LEADS` or a `ROOM-LEFT` files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md), pending the forward read.
- Any rule built on a result here, such as a bear entry on a state signal, needs its own
  registration and an operator decision.
- No verdict here changes a tier, a veto, a size class, an exit, the deploy card or the hedge
  sleeve in [§4](../../../../docs/deployment-rules.md#s4).
