## ticker_regime_move — does a play's own regime label forecast that ticker's stock move?

<!-- outcome:start -->
> Latest outcome: not run.
<!-- outcome:end -->

_Registered 2026-11-27._

## The question

Each play row carries its own `regime` text, such as `BEAR + C-VOL` or `BULL + E-VOL`. It is
the model's read of that ticker, not of the market. Does that label forecast the ticker's own
stock move?

Two contrasts answer it. Both use stock closes only.

- **D, direction.** Mean 21-session return net of the ticker's own beta to SPY,
  BULL-labelled rows minus BEAR-labelled rows. It is read inside own-trend strata, so the
  label must add to a mechanical trend flag.
- **S, size.** Mean scaled absolute 10-session move, E-VOL-labelled rows minus rows with
  another vol token. The scale is the ticker's own trailing realised vol, so the label must
  add to it.

## What this study is not

- **Not a selection, sizing or exit rule.** It reads no option price, position, tier or R.
- **Not a test of the MARKET row.** [`market_read`](market_read.md) graded that label against
  SPY (`NO-FORECAST`).
- **Not a re-grade of `direction_hit`.** [`direction_hit`](../signal/direction_hit.md) graded
  17 entry features against the picks' direction (`NULL`). The per-play label was not one of
  them.
- **Not a test of the `signal` column.** Its tag is `[FLOW]` on 3,483 of 3,500 v4 play rows,
  so it cannot split the rows. Its tags are printed as a count table only.
- **Not a search.** The graded family is closed at D and S. Every other table is printed and
  never graded. A lead seen there needs a new registration.
- **Not pooled across eras.** `--era v3` is a replication, never a pool.
- **Not a ship.** Only a forward `SUPPORTED` files "to be tested" in
  [`deployment-evidence.md`](../../../deployment-evidence.md). An in-sample word files
  nothing. No production code changes either way.

## Definitions

### Rows

- **Play rows.** Rows of the era's analysis export whose `ticker` is not `MARKET`.
- **One row per (date, ticker).** Several plays can share a date and ticker.
  - Heads agree when `parse_label(...).dir` is equal on every row.
  - If they agree, the first row in the export file's row order is kept.
  - If they differ, the pair is `AMBIGUOUS`. It is dropped and counted.
- **SPY rows are dropped and counted.** SPY's excess over itself is zero.

### The label, parsed from its head

The parse is `market_read.parse_label`, imported and unchanged.

| Field | Rule |
|---|---|
| head | The text before the first of `—`, `" - "`, `". "`, `": "` or `" ("` |
| `dir` | The first of BULL, BEAR, RANGE in the head, as a whole word |
| `vol` | The first of E-VOL, H-VOL, L-VOL, C-VOL in the head |

- **OTHER.** A head with no direction word. The row is dropped and counted. No refusal
  threshold applies; the share is printed.
- **RANGE rows** are in neither arm of D. They are printed.
- **Transition.** A head with two or more distinct direction words, such as `BEAR→BULL`. The
  row leaves D and is counted. It stays in S.
- **No vol token.** The row leaves S only.

### Calendar and closes

- **Calendar.** The SPY sessions with a non-blank close in
  `backtests/mech_regime/spy_vix_daily_full.csv`. `i` is the signal date's session index.
- **Exact sessions only.** A signal date that is not a session is dropped and counted.
- **Ticker closes.** `lib/underlying.py::load_bars(ticker)`. `c[s]` is the ticker's close on
  calendar session `s`. A window needs a close on its first and last session, or the row is
  dropped from that outcome and counted.
- **OHLC bars only.** A ticker whose bars come from the close-only `Price~` fallback
  (`SRC_TILDE`) is dropped and counted.
- **Split guard.** A session-to-session log return `r` is a split step when both rows of
  the table below hold. A row with a split step in a window is dropped from that outcome.
  Other large steps stay in. Drops are printed per direction label.

  | Test | Rule |
  |---|---|
  | Size | `abs(r)` exceeds `underlying_features._MAX_ABS_LOG_RETURN`, which is 0.30 |
  | Ratio | `exp(abs(r))` is within 5% of one of 1.5, 2, 3, 4, 5, 10 |

- **Gaps.** A session with no bar inside a window drops the row from that outcome. It is
  counted.

### Outcomes per row

| Outcome | Definition | Graded in |
|---|---|---|
| `bres_h` | `ln(c[i+h] / c[i]) − β × ln(spy[i+h] / spy[i])`, for `h` in 10, 21 | `bres21`: D |
| `exret_h` | The same with β fixed at 1 | Printed only |
| `absz10` | `abs(ln(c[i+10] / c[i])) / (rv20 × sqrt(10 / 252))` | S |

- β is the first value of `underlying_features.beta_corr_spy(bars, d)`: the trailing beta to
  SPY, from bars on or before the signal date only. A row with no β leaves D and is counted.
  Without β, a high-beta name would beat SPY in a rising tape on beta alone.
- `rv20` is `underlying_features.rv20(bars, d)`: annualised, bars on or before the signal date
  only. A row with no `rv20` leaves S and is counted.
- Every close in an outcome window is strictly after the signal date, except `c[i]` itself.
- A window that runs past the calendar's end is dropped and counted.

### The own-trend flag (D's strata)

- `above`: the ticker's close on the signal date is over the mean of its last 50 closes on or
  before that date.
- `below`: it is at or under that mean.
- A row with fewer than 50 bars, or with no bar on the signal date, has no flag. It leaves D
  and stays in the printed unstratified contrast.

### Lag bin

`market_read.lag_bin`, imported and unchanged. Lag is `created_datetime[:10]` minus `date`.

| Lag bin | Lag |
|---|---|
| LIVE | 0 or 1 day |
| NEAR | 2 to 7 days |
| RETRO | more than 7 days |
| UNKNOWN | blank, or negative |

A RETRO label was written after the fact, by a model that may know what the stock did next.

### Bootstrap block

A block is `i // 21` on the SPY calendar. Every row whose signal date falls in one block
travels together in every draw, across all tickers. This carries both the cross-section on a
date and the overlap of neighbouring windows.

## Population and basis, fixed here

- **Era.** `era.requested_era()`, then `resolve_paths` and `enforce`. A mismatch refuses
  (exit 3). Only the analysis export is read. Every report header names the era.
- **Seal.** `era.drop_sealed(rows, date_key="date")` with no reader. The seal lifted on
  2026-11-26, so no v4 date is withheld today.
- **In-sample.** Signal dates whose 21-session window closes on or before 2026-11-25, the
  calendar's last session at registration. This set never grows. The first run is the
  in-sample verdict of record.
- **Gap.** Signal dates after that, up to 2026-11-27. They are counted and never graded.
- **Forward.** Signal dates after 2026-11-27 whose lag bin is LIVE. They are never pooled
  with in-sample rows. A forward row that is not LIVE is counted and never graded.
- **Minimum.** `era.require_dates` with a minimum of 60 in-sample dates. A thin era refuses
  (exit 2).

## What it compares

| Object | What it measures | Role |
|---|---|---|
| D | BULL minus BEAR mean `bres21`, standardised over the `above` and `below` strata | graded |
| S | E-VOL minus other-vol mean `absz10` | graded |
| D-raw | BULL minus BEAR mean `bres21`, unstratified | printed |
| D-plain | D on `exret21`, the excess with β fixed at 1 | printed |
| D-twin | `above` minus `below` mean `bres21` | printed control |
| D10 | D on `bres10` | printed |
| Lag cuts | D, D-raw and S on LIVE rows and on RETRO rows | printed |
| Grid | Mean `bres21` and `absz10` per `dir` × `vol` cell, with row counts | printed |
| Signal tags | Count of the `signal` column's leading tags | printed |
| Block 42 | D and S with blocks of `i // 42` | printed sensitivity |

**D, exactly.** Within each stratum, take BULL mean minus BEAR mean. Weight each stratum by
its share of the BULL and BEAR rows that hold `bres21`, over both strata. D is the weighted
sum. Both strata always enter; a thin stratum is never dropped. The study computes D with
its own function, not `market_read.strat_diff`, whose entry gates differ.

## Statistics

- 10,000 block draws, seed 20261127. Blocks are resampled with replacement, as many as the
  population holds. D and S share the draws.
- 95% percentile interval. Two-sided `p = 2 × min(share ≤ 0, share ≥ 0)`, capped at 1.
- D and S are one Holm family (m = 2) at 0.05. An ungradable contrast enters at `p = 1`.
- A draw in which a stratum has an empty arm is discarded for D. The count is printed. If
  more than 5% of draws are discarded, D is `UNDERPOWERED`.

## Floors

| Contrast | Floor |
|---|---|
| D | In each stratum, each arm holds at least 50 rows in at least 6 blocks |
| S | Each arm holds at least 200 rows in at least 12 blocks |
| Forward D, forward S | The same floor, each on forward rows only |

## Verdict words

Each of D and S prints one word.

| Word | Rule |
|---|---|
| `UNDERPOWERED` | Its floor is not met |
| `IN-SAMPLE-ONLY` | In-sample: floor met, interval wholly above 0, Holm-adjusted p under 0.05 |
| `SUPPORTED` | Forward: the same rule. This word never prints in-sample |
| `CONTRARY` | Floor met, interval wholly below 0, Holm-adjusted p under 0.05 |
| `NULL` | Floor met, and none of the rows above |

The READ line prints D's word under one of these names:

| D's word | READ |
|---|---|
| `IN-SAMPLE-ONLY` | `IN-SAMPLE-ONLY` |
| `NULL` | `NO-FORECAST` |
| `CONTRARY` | `CONTRARY` |
| `UNDERPOWERED` | `UNDERPOWERED` |

The forward line prints one word per contrast. A contrast prints `STILL-OPEN` until its own
forward floor is met, then its forward word. The forward Holm family is m = 2, with an unmet
contrast at `p = 1`. A contrast's forward verdict of record is the first forward run that
prints a word other than `STILL-OPEN` for it.

## How to read the result

- `IN-SAMPLE-ONLY`: BULL-labelled tickers out-ran BEAR-labelled ones, beyond beta and their
  own trend flag. Most in-sample labels are RETRO, so the model may have known the path. The
  word files nothing. Wait for the forward read, which uses LIVE labels only.
- `NO-FORECAST`: the per-play direction label says nothing about the stock's move on this
  evidence. Do not size or pick on it.
- D `CONTRARY`: BEAR-labelled tickers out-ran BULL-labelled ones. Do not act on the label,
  and do not invert it without a new registration.
- S `IN-SAMPLE-ONLY`: E-VOL-labelled tickers moved more than their trailing vol implied. It
  files nothing in-sample. A forward `SUPPORTED` would bear on structure choice, and needs
  its own registration.
- S `NULL`: the vol tag says nothing that trailing realised vol does not.
- S `CONTRARY`: E-VOL-labelled tickers moved less than the others, relative to trailing vol.
  The tag may mark vol that has already peaked.
- `UNDERPOWERED`: too few rows or blocks. It is not evidence for or against.

## Known limits

- An era holds about 34 blocks. A percentile interval from so few blocks is probably too
  narrow.
- One ticker can appear in many blocks. The bootstrap treats blocks as exchangeable and does
  not cluster by ticker.
- Rows near a block edge have windows that reach into the next block. The block-42 line shows
  how much this matters.
- Most v4 labels were backfilled. The lag cuts are the only guard, and they are not graded.
- The rows are the tickers the model chose to write a play on. The result says nothing about
  tickers it passed over.

## Plan-time observations, disclosed

- Counts only were read before this file was written: 3,500 v4 play rows on 278 tickers and
  327 dates. A crude first-word split gave BULL 1,679, RANGE 767, BEAR 657. Three label
  strings and three signal strings were looked at.
- No close, return or backtest row was joined to a label before registration.
- The drafter knew the earlier results: `market_read` `NO-FORECAST`, `direction_hit` `NULL`,
  `state_map` `COINCIDENT` and `NULL`.
- The floors and the two contrasts were set without any outcome.
- A second reader checked this file on 2026-11-27, before any outcome. Its rulings are
  folded in above: the beta-adjusted outcome, the narrower split guard, the frozen in-sample
  set, LIVE-only forward rows and the `IN-SAMPLE-ONLY` word.

## Dependencies

- `scripts/backtest_study/f1_selection/regime/market_read.py`: `parse_label`, `lag_bin`,
  `load_calendar`, `Pop`, `Draws`, `Result`, `summarize`, `mean_diff`.
- `scripts/backtest_study/f1_selection/benchmark/ticker_class.py::holm`.
- `scripts/backtest_study/lib/underlying.py`: `load_bars`, `SRC_TILDE`.
- `scripts/backtest_study/lib/underlying_features.py`: `rv20`, `beta_corr_spy`,
  `trailing_bars`, `_MAX_ABS_LOG_RETURN`.
- `scripts/backtest_study/lib/era.py`.

## Run

```
python -m scripts.backtest_study run ticker_regime_move
python -m scripts.backtest_study run ticker_regime_move --era v3
```
