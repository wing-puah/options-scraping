# Backtest Results — Column Reference

Column definitions for the `BacktestResults` Google Sheet (and the mirror
`backtests/results.csv`), written by [`scripts/backtest/`](../scripts/backtest/).

Each row is **one simulated play** — a non-MARKET ticker row from the analysis tab
that carried a play, matched to its real flow contract and tracked day-by-day from
entry to expiry (or the `path_cap_days` cap, whichever comes first).

There are **no per-checkpoint (`d1`/`d5`/`d21`…) columns**. Every P&L figure is
derived from the full daily mark series stored in `daily_price_csv`; analysis code
samples whatever holding horizons it wants from that path.

---

## Entry & contract identity

| Column | Definition |
|--------|-----------|
| **signal_date** | Analysis date the play was proposed (ISO `YYYY-MM-DD`). The entry fill is taken on the FIRST trading day AFTER this date under `simulation.entry_timing: next_open` (the default — the analysis is produced after the close), or on this date's EOD mark under `signal_eod`. |
| **ticker** | Underlying symbol. |
| **structure** | Resolved trade structure label: `long_call`, `long_put`, `bull_call_spread`, `bear_put_spread`, `bull_put_spread`, `bear_call_spread`, `short_put`, `short_call`, `iron_condor`, or `explicit_legs` (the play named its legs directly). Kept as a grouping label; the authoritative position is `legs`. |
| **legs** | The full position as one or more signed legs, one per line, in the form `<TICKER>:<YYYY-MM-DD>:<STRIKE>:<C\|P> <signed_qty>` — e.g. `NVDA:2026-07-17:250:C +1` / `NVDA:2026-07-17:270:C -1`. The signed quantity is **last** so the cell never starts with `+`/`-` (Google Sheets would coerce a leading sign into a formula); parsing also accepts the legacy quantity-first form. `qty` is the per-unit ratio (sign = long/short); a separate `contracts` column holds the risk-sized number of units. Each leg carries **its own expiration**, so calendar / diagonal / ratio spreads are representable. The position is fully generic in leg count — any structure (single leg, vertical, ratio, butterfly, condor, box, iron condor, …) is just a list of signed legs. To backtest a hand-authored structure, write its legs (one per line) in the play cell; it is recognised as `explicit_legs`, bypasses the freeform classifier, and same-contract legs are merged (e.g. `+2` / `-1` → `+1`). Replaces the old `k_long` / `k_short` / `expiration` / `opt_type` columns. |
| **entry_leg_detail** | One line per leg, aligned with `legs`: `<leg>  px=<price> iv=<IV %> delta=<delta> S=<Price~> [<source>]`. Each leg's greeks come from its own history row. A blank `iv` or `delta` means no real value. See [No model prices](#no-model-prices-2026-09-23). |
| **contracts** | Risk-sized number of units of the `legs` structure. Debit (`entry_option_price > 0`): fixed-fractional sizing on the premium paid (`abs(entry_option_price) × stop_loss`). Credit (`entry_option_price < 0`): sized on the structure's STRUCTURAL max loss (`max_loss_per_contract`, below), not the credit received — a thin credit on a wide/naked structure would otherwise be wildly oversized against the risk budget. When a credit's max loss can't be bounded (naked short call, multi-expiration credit), falls back to `1` and logs a warning. See `_size_contracts` in [`scripts/backtest/simulate.py`](../scripts/backtest/simulate.py). |
| **dte_entry** | Days to expiration at entry (anchor leg), measured from the entry day — one less than the signal-date DTE when the entry is the next day's open. |
| **iv_entry_pct** | Implied vol of the anchor contract at entry, as a decimal fraction. Blank when the anchor row has no real IV (since 2026-09-23). |
| **delta** | Net position delta at entry, `Σ qty·delta`, each leg's own cached Barchart delta. Blank when any leg lacks a real delta: all-or-nothing, never `0.0`. Rows before 2026-09-23 used a model delta on non-anchor legs. |
| **entry_underlying** | Underlying at entry: the median of the legs' own `Price~` on the entry day. Before 2026-09-23 it was the anchor leg's `Price~` alone. |

## Entry pricing

| Column | Definition |
|--------|-----------|
| **entry_option_price** | **Signed** net per share, in option points: `Σ qty·price` over the legs. **Positive = net debit (paid), negative = net credit (received).** Its **absolute value** is the denominator for every P&L figure; `daily_price_csv` marks carry the same signed convention. |
| **entry_premium_total** | `abs(entry_option_price) × 100 × contracts` — dollar cost/credit of the position. |
| **entry_source** | Each leg's entry pricing, joined with `+` in leg order: `barchart_open` (Open print), `barchart` (EOD mark), `barchart_side` (junk quote, sold at the bid), `barchart_last` (junk quote, traded Latest), `real` (flow print). `bs` only before 2026-09-23. |
| **market_regime** | The market-level regime for that date (from the MARKET row), truncated at the first em-dash — e.g. `BULL TREND`. |
| **regime** | The play's ticker-specific regime label carried from the analysis row (not the market read). |
| **play** | The play text (truncated to 300 chars). |

## Flow-rollup context (joined)

Per-ticker signal context from that signal date's scored rollup, kept separate from
the model's `signal` evidence. As of the analysis-pipeline change these are written
onto the analysis row itself at analysis time (the `oi_confirm_pct` / `cpir` /
`iv_spread` columns on AnalysisClaude / AnalysisTickerSpecific), so the backtest reads them
straight off the row. For rows written before those columns existed, the backtest
backfills from `audit/<date>-rollup.csv` by `(signal_date, ticker)`
(`_attach_rollup_metrics` in [`scripts/backtest/core.py`](../scripts/backtest/core.py));
blank when neither the row nor an audit file has the value. See
[`docs/rollup-reference.md`](rollup-reference.md) for the full definitions.

| Column | Definition |
|--------|-----------|
| **oi_confirm_pct** | `OIConfirmPct` — share of the ticker's flow trades whose next-day OI change confirmed an opening position (ref-03 open-confirmation). Decimal fraction (0.45 = 45%). |
| **cpir** | `CPIR` — Call-Put Information Ratio `OIFC / (OIFC + OIFP)`, in `[0,1]`. > 0.5 = call-skewed informed opening (bullish); < 0.5 = put-skewed. |
| **iv_spread** | `IVSpread` — OI-weighted (call IV − put IV) across matched strike/expiry pairs, 10–60 DTE, on settlement IV (Cremers/Weinbaum). Positive → bullish (a positive predictor of returns). Missing counterpart legs are backfilled from Barchart price-history (`scripts/collector/fetch_counterpart_iv.py`), so coverage depends on whether that date's `counterpart-iv-*.csv` sidecar has been built. ⚠️ The old ≈ −25 BEAR veto was tuned on the prior premium-weighted/unmatched definition — **re-derive** before applying. `—`/empty when no matched pair. |

## Realized exit & excursions (path-derived)

These summarise the **full daily path**. The realized exit is the **first** day a
rule triggers — frozen at that day's mark (never a later live mark).

| Column | Definition |
|--------|-----------|
| **realized_pnl_pct** | Realized P&L % at the exit, from the single signed formula `(V_exit − entry_net) / abs(entry_net)` where `V` is the position's signed net mark. Profit is positive for both debit and credit positions (a credit has `entry_net < 0` and profits as `V` rises toward 0). |
| **realized_pnl_abs** | Realized P&L in dollars (`realized_pnl_pct × abs(entry_option_price) × 100 × contracts`). |
| **days_held** | The 1-based index of the exit day in `daily_price_csv` — **SIGNAL-relative**, counted on the grid of weekdays AFTER the signal date. That origin has never moved and must not (see "No P&L before the fill" below): `time_exit_dte_fraction`, `path_cap_days`, the frozen research harness and the study loaders all count on the same clock. For the usual case — the fill IS the first weekday after the signal — it is also the trading days held. When the fill lands later, the days before it are blank (`pre_entry`) and this index exceeds the true holding period by the fill lag; `daily_source_csv` says exactly how many. |
| **exit_reason** | Why the trade closed: `profit_target`, `stop_loss`, `expired` (held to expiry with no trigger), `cap_open` (still open at `path_cap_days`, or at the data end — see `path_status`), `no_data` (no day could be priced). |
| **mfe_pct** | **Max Favorable Excursion** — the best P&L % the trade ever reached over the _whole_ path, independent of the exit rule. Use this to tune the profit target. |
| **mfe_day** | Trading-day index (1-based) where MFE occurred — same signal-relative grid as `days_held`. Never lands on a `pre_entry` day (they carry no mark). |
| **mae_pct** | **Max Adverse Excursion** — the worst P&L % over the whole path. Use this to tune the stop. |
| **mae_day** | Trading-day index (1-based) where MAE occurred — same signal-relative grid as `days_held`. Never lands on a `pre_entry` day (they carry no mark). |
| **pnl_at_cap_pct** | P&L % on the last priced day of the path (the "held to the end / never exited" comparison). |
| **pct_real_days** | Share of priced leg-days marked from real data (Barchart or flow reappearance). Rows since 2026-09-23 always read 1.0. On older rows the rest are Black-Scholes leg-days. Counted per leg since 2026-09-07. |
| **pct_stale_days** | Fraction of priced leg-days whose mark was **carried forward** past `simulation.max_price_carry_days` (default 5 calendar days) — the honesty check for a contract that stopped being quoted. A strike that vanishes (a split, a dead wing) used to be carried at its last price to the end of the path with nothing on the row saying so; one v4 row exits `cap_open` at +72% on 70 frozen days. Same priced-days denominator as `pct_real_days`, so `pre_entry` days are outside it. Those days are still REAL data (a frozen quote, not a model), so they stay in `pct_real_days` — this column and the `barchart_stale` tag in `daily_source_csv` are where the staleness shows. Blank on `no_data` rows. **New 2026-09-07** — blank on every earlier row. |

## The daily path

| Column | Definition |
|--------|-----------|
| **daily_price_csv** | Comma-separated **signed net position mark (`Σ qty·price`), one value per trading day** from the weekday AFTER the signal date through `min(nearest-leg DTE, path_cap_days)`. Same signed units as `entry_option_price`. An **empty token** (`,,`) is a day with no mark — either no source could price it (any unpriceable leg blanks the whole day) or, since 2026-09-07, the position did not exist yet (`pre_entry` in `daily_source_csv`; see "No P&L before the fill"). Reconstruct the P&L path by splitting on `,`, dropping empties, and applying `(mark − entry_option_price) / abs(entry_option_price)` (see `pnl_path()` in [`scripts/chart_backtest.py`](../scripts/chart_backtest.py)). |
| **daily_pnl_csv** | Comma-separated **absolute dollar P&L per SINGLE contract, one value per trading day**, on the exact same day grid + blank-token convention as `daily_price_csv`: `(mark − entry_option_price) · 100`. Per-contract — **NOT** scaled by `contracts` (that scaling lives in `realized_pnl_abs`/`mfe_abs`). GROSS of transaction costs, like every other path column. |
| **daily_source_csv** | Each day's mark source, legs joined with `+`: `barchart`, `barchart_last` (junk day that traded), `barchart_stale` (carried past the bound, or over a junk day), `real` (flow), `pre_entry` (unpriced). `bs` only before 2026-09-23. Empty = unpriced. |

## No P&L before the fill (robustness review B2, 2026-09-07)

**The grid origin did not move, and must not.** `daily_price_csv` /
`daily_pnl_csv` / `daily_source_csv` still start on the first weekday AFTER the
signal date, and `days_held` / `mfe_day` / `mae_day` are still 1-based indices on
that grid — the same clock `time_exit_dte_fraction` and `path_cap_days` use.
Three things outside the backtest rebuild that grid from `signal_date` and index
into it positionally: the FROZEN `scripts/backtest_study/lib/harness.py` asserts
the mark count equals the grid length, and both
`scripts/backtest_study/lib/mtm_curve.py` and
`f4_deployment/concurrency_correlation.py` read index 0 as the first session after
the signal.

**What changed is the MARK, not the grid.** The fill can land up to 5 days after
the signal — `classify.py::_entry_row_from_history` accepts the first Barchart
print within its staleness window as the entry day. Every grid day before that
fill used to be priced by carrying an older mark forward and comparing it against
an entry struck later, so MFE/MAE — and on about **4% of positions a realized
exit** — were booked on days the position did not exist. Those days are now
**present but unpriced**: a blank token in `daily_price_csv` and `daily_pnl_csv`,
tagged `pre_entry` in `daily_source_csv`. Nothing scans them, so no P&L,
excursion, profit-target, stop or trailing exit can be booked before the fill, and
the first PRICED day is the entry day. The carry-forward bound (`pre_entry` days
never call the pricer) means a stale quote cannot reach backwards past the fill
either.

Consequences, all deliberate:

- The grid keeps its length, so the harness invariant and the two index-0 readers
  are unaffected.
- `pct_real_days` and `pct_stale_days` are computed over priced days, so
  `pre_entry` days leave the denominator rather than counting as unreal.
- On a late fill `days_held` exceeds the true holding period by the fill lag —
  it is a grid index, not a holding count. Subtract the leading `pre_entry` tokens
  in `daily_source_csv` for the holding period.
- Nothing is unchanged for the common case: when the fill IS the first weekday
  after the signal there are no `pre_entry` days and every column is byte-identical
  to what it was.

⚠️ **Rows written before 2026-09-07 may carry pre-entry P&L.** A `pre_entry` token
never appears on them; their pre-fill days look like ordinary `barchart` marks.
The way to clean a row is to re-price it — `python3 -m scripts.backtest --config
config/backtest.yml --date YYYY-MM-DD --redo`, which deletes the existing rows and
re-simulates them (it refuses to run without a date bound). That re-run also picks
up B3 (leg-day `pct_real_days`, `barchart_stale`) and B5 (zero-bid marking), so
expect a diff on more than the late-fill rows even with both cost knobs at 0.

## Structural risk (credit/debit, Attempt 8)

Independent of the daily path — computed once at simulate time from the position's
legs and `entry_option_price`, not from the day-by-day marks. Placed at the
**physical end** of the sheet schema (`_KEY_ORDER`, after `daily_pnl_csv`) for the
same append-alignment reason as `daily_pnl_csv`: `append_rows` only writes a header
on an empty tab, so inserting a column mid-schema would misalign every existing row.

| Column | Definition |
|--------|-----------|
| **max_loss_per_contract** | Structural worst-case loss per contract, in dollars: `_max_loss_per_unit(legs, entry_option_price) × 100`. Debit = the premium paid (`entry_option_price × 100`) — same convention as the existing sizing, so a net-debit ratio with naked short legs understates true risk here too. Credit = `(entry_option_price − worst expiration payoff) × 100`, i.e. the credit received minus the structure's floor. **Blank (`""`)** when the max loss can't be bounded (net short calls, multi-expiration credit/calendar/diagonal) — `_size_contracts` falls back to 1 contract with a warning in that case. |
| **pnl_on_risk_pct** | `realized_pnl_abs / (max_loss_per_contract × contracts)`, a **decimal fraction** (0.20 = 20%) of the position's own structural risk budget, rounded to 4dp. For debit trades this is mathematically identical to `realized_pnl_pct` (the denominator is the same premium paid). For credit trades it re-expresses the premium-relative `realized_pnl_pct` against the structure's true max loss instead — the number that matters for comparing risk-adjusted return across credit and debit plays on one scale. **Blank (`""`)** when `max_loss_per_contract` is blank, or when `realized_pnl_abs` isn't numeric (`exit_reason == "no_data"`). |

## Transaction costs (robustness review B1, 2026-09-07)

Until 2026-09-07 nothing in this repo charged commission or slippage: every leg
was filled at the mark, in and out, in the backtest, the proxy and every study.
The rules that shipped rest on gains of +0.02 to +0.04 R, and one realistic round
trip is of that order — so the whole edge has never been measured net of costs.
`config/backtest.yml` now carries `simulation.commission_per_contract` and
`simulation.slippage_frac_of_spread`, **both defaulting to 0**, which reproduces
every number recorded before that date exactly. Turning them on is a deliberate
act with its own before/after; the cost-sensitivity study
(`research/robustness-review.md` N1) is what they exist for.

What the charge nets: `realized_pnl_pct`, `realized_pnl_abs` and — because it is
derived from the latter — `pnl_on_risk_pct`. What stays GROSS: `mfe_*`, `mae_*`,
`pnl_at_cap_pct`, `daily_pnl_csv`. Exit rules are scanned on marks, so costs never
move the thresholds a path is read with; they are charged once, on the round trip,
after the exit is known.

**In the export schema**, appended at the END of `_KEY_ORDER`
(`scripts/backtest/core.py`) and `_PROXY_KEY_ORDER` (`scripts/backtest/proxy.py`)
in the order `pct_stale_days`, `cost_total`, `cost_basis` — so `cost_basis` is the
last column on both tabs. ⚠️ Per the header rule in `CLAUDE.md`, Sheets appends
positionally: the `BacktestResults` and `BacktestProxy` tab headers must gain these
three, in that order, BEFORE the next run appends, or the new rows write three
unlabelled trailing columns. `python3 scripts/align_tab_headers.py --dry-run`
reports the gap and `python3 scripts/align_tab_headers.py` closes it.

Read `cost_basis` before reading any realized figure: an EMPTY `cost_basis` means
both knobs were 0 and `realized_pnl_pct` / `realized_pnl_abs` / `pnl_on_risk_pct`
are GROSS. That pairing is the point — an unlabelled basis is the failure
`exit_basis` exists for, and a tab that pools cost-charged and gross rows with
nothing to segregate on would repeat it.

| Column | Definition |
|--------|-----------|
| **cost_total** | Dollars of commission + slippage charged on the ROUND TRIP for the whole position (all legs, all contracts, both sides). `commission_per_contract × Σ\|qty\| × contracts × 2`, plus `slippage_frac_of_spread × Σ(\|qty\|·spread) × 100 × contracts` once per side, where `spread` is that leg's quoted ask − bid on the day the side's mark came from. Slippage is always adverse. `0.0` when both knobs are 0 (the default), in which case nothing is netted. |
| **cost_basis** | What the charge could see. `""` = costs off; `commission_only` = no slippage configured; `full` = slippage on both sides. `no_spread_<side>` = that side was short-charged: a leg with no quote zeroes the side's slippage, a junk-quote leg pays none. |

## How the exit was FILLED — `exit_fill`

Shipped 2026-09-19, appended at the very end of both backtest tabs.

The exit rules scan the MARKED path and fire on the first day a condition is
crossed. That day is the TRIGGER. It is not always a day the position could
actually be traded out on: `_zero_bid_mark` values a leg quoted `bid 0 / ask N`
at `ask/2`, which is the right liquidation mark for a mark-to-market path and
the wrong price for a FILL, because nothing is bid. Booking the exit there
credits a long leg at a price nobody was offering to pay.

So the trigger and the fill are two different days. When the trigger day has no
two-sided quote on every leg, the fill is carried to the next priced day that
does, `days_held` becomes that later day, and this column says what happened.

| Value | Meaning |
|--------|-----------|
| **same_day** | The trigger day was fillable. The overwhelming majority of rows. |
| **deferred_`n`** | The trigger day was not fillable, so the fill was carried `n` grid days to the next day that was. `days_held`, the realized P&L and the day slippage is charged on are all that later day's. |
| **no_two_sided** | The trigger fired and no fillable day ever arrived before the path ended. The fill stays on the trigger day's mark — the pre-2026-09-19 behaviour — and the row is FLAGGED rather than silently priced at something unobtainable. |
| **`""`** | Written before 2026-09-19, when the exit always filled on the trigger day. |

What does NOT change: the marked path, `daily_price_csv`, MFE/MAE, and which
rule fired. A deferral moves WHEN the position closed and AT WHAT, not WHY.

`cap_open` and `expired` are never deferred — they take the last priced day by
construction, so there is no later day to move to.

**Scale.** Measured on both tabs before the rule shipped, 79 of 2,707 exit-day
leg quotes were one-sided (2.9%), touching 72 of 1,375 rows (5.2%). Re-pricing
April 2025 with the rule on and off, on one cache, moved 3 of 61 proxy rows
(4.9%) — all HYG bear put spreads, and in BOTH directions (−0.38 → −0.57,
−0.84 → −0.52, −0.55 → +0.70). It is not a systematic bias in either direction;
it replaces an unobtainable price with a real one.

**This was not backfilled.** Every row written before 2026-09-19 is blank here
and was filled on its trigger day. Re-pricing the recorded book is a separate
decision.

## The path may not outlive the data — `path_status`, `path_data_end`

Shipped 2026-09-23, appended at the very end of both backtest tabs.

**No exit rule may fire on a day after the last real quote.** `path_cap_days` is
120 and the engine carries the last scrape forward over every later day, so a
July signal used to simulate into November against frozen marks. Two things went
wrong on such a row: a rule could fire on a session that had not happened, and a
play with no exit was stamped `cap_open` at the cap as if the path had genuinely
run that long. A local run of 24 backfilled June–July 2026 dates measured both.

| Rows in that local run | Count |
|---|---|
| Simulated | 154 |
| Genuine outcome | 133 |
| `cap_open` on carried marks | 11 |
| A rule fired after the last real quote | 10 |

**The last real quote, for a position, is the earliest of its legs' last real
sessions.** A spread is only as live as its deadest leg: once one leg stops
printing, the net mark is part frozen. Taking the latest leg instead would let a
still-quoted long leg license an exit priced off a short leg that has not traded
for weeks. Interior gaps truncate nothing — this is each leg's last session, not
a run of consecutive ones.

A position still open at that point is marked there, not dropped. `days_held` is
that day, the realized P&L is that day's mark, and `exit_reason` is `cap_open`
rather than `expired`, because the path did not reach expiry.

| Value of `path_status` | Meaning |
|--------|-----------|
| **complete** | The exit fired on a day every leg quoted for itself. |
| **carried** | It fired on a day at least one leg's mark was carried into — an interior gap, the one case the rule cannot cleanly prevent. |
| **open_at_data_end** | The data ran out before any exit fired, so the row is marked at the last real quote instead of at the cap. |
| **`""`** | Written before 2026-09-23, when the question was never asked. |

`path_data_end` is the ISO date of that last real quote. Blank on a `no_data`
row and on every row written earlier.

**What does not change.** The marked path, `daily_price_csv`, MFE/MAE and
`pnl_at_cap_pct` are still measured over the whole grid, so a play that exits
before the data ends is identical to what the engine produced before. That
leaves `pnl_at_cap_pct` as the one figure still read off a possibly carried
mark; `path_data_end` is how to tell whether it is.

**This was not backfilled.** Both columns are blank on every stored row, and a
blank means unknown rather than clean. Re-pricing the recorded book is a
separate decision; a dated `--redo` is the cleanup.

## Model score & horizon (joined off the analysis row)

Carried straight off the analysis row (not produced by simulation), so each
component can be measured against realized P&L and pruned. `horizon` sits beside
`play`; the `score_*` block is appended at the end. Blank on rows written before
these columns existed. These replaced the old high/medium/low `confidence` label.

⚠️ **Two eras in one schema.** The results schema is deliberately frozen across
the v3→v4 prompt cut-over, so `score_flow`/`score_dealer` still exist as columns
but are **blank on every v4 row** and `score_total` changes scale (0–100 → 0–50).
Any analysis that pools v3 and v4 rows must split on era before touching the
score block — see the two rows below.

| Column | Definition |
|--------|-----------|
| **horizon** | The play's DTE bucket boundary (`14`\|`60`\|`180`\|`720`) — the dominant expiry of the cited evidence. Read off its own analysis-row column (legacy rows: regex-scraped from the play bracket). Drives expiry synthesis when no explicit month/day is named (`_resolve_expiry`). |
| **score_total** | Sum of the surviving component points below, computed at row-expansion time — never model-produced. **v4 rows: 0–50** (0–55 for VOLATILITY intent); interpretation only, ≥35 strong · 20–34 moderate · <20 weak. **v3 and earlier rows: 0–100** (≥70 / 40–69 / <40) because they still summed five factors. The two scales are **not comparable — never pool them.** Decision-irrelevant either way: it survives only as a deterministic tie-break. |
| **score_price** / **score_vol** / **score_catalyst** | The three framework Step-5 evidence-quality factors from v4 onward, each an integer point award. Per-factor maxima are intent-weighted (DIRECTIONAL/HEDGE/SYNTHETIC STOCK: 20/15/15; VOLATILITY: 10/25/20). |
| **score_flow** / **score_dealer** | **Retired in v4** (2026-08-11) — dropped from the prompt and from the analysis-row schema after the ML combination study found the score block decision-irrelevant, and because `score_dealer` was judged off a vol-snapshot proxy rather than real per-name dealer gamma. Both columns are deliberately **kept in `RESULT_COLUMNS`** so pooled v3+v4 exports stay schema-stable; they are simply **blank on v4 rows**. On v3 rows they carry the old intent-weighted maxima (DIRECTIONAL/HEDGE/SYNTHETIC STOCK: 25/25; VOLATILITY: 20/25). |

## Exit basis

| Column | Definition |
|--------|-----------|
| **exit_basis** | Which exit profile governed the simulation of this row. `PROD` = the base `simulation:` block. `CREDIT` = the `simulation.credit:` override (any row with `entry_option_price < 0`; credits are never regime-switched). `BEAR_HE` = the mechanical-regime exit override fired (`simulation.regime_exit.cells`, shipped 2026-07-22 — see `docs/deployment-rules.md` §Exit management). `BEAR_DEBIT` = the structure-keyed `be_after` peak-triggered breakeven stop governed this row (`simulation.structure_exit.cells.bear_debit`, shipped 2026-08-11 — `bear_put_spread`/`long_put` on the debit side, outside a regime cell). `NONE` = BacktestProxy `underlying_trend` tier only, where no exit rules run at all.<br><br>Reported in **merge-precedence order** (`CREDIT` → regime cell → `BEAR_DEBIT` → `PROD`), so the label always names the profile that actually governed the exit. A regime cell outranks `BEAR_DEBIT` because regime merges LAST: on `BEAR_HE` it sets `be_after: null`, since the 0.50/0.50 trail already dominates the breakeven stop there. This ordering is what keeps `PROD` meaning **base config only** for every row. **Blank (`""`) = the row was written before this column existed, i.e. PROD-basis by definition** — that is the intent, and it holds on the **v4** export (where nothing is blank) but NOT on v3 or on `BacktestProxy`: see the era note below. <br><br>⚠️ **TRUST THIS COLUMN PER ERA — v4 yes, v3 and earlier no.**<br><br>**v4 (current): usable.** Re-measured 2026-09-02 on the 2026-08-27 export — the tab header matches `scripts/backtest/core._KEY_ORDER` 47/47, all 485 rows carry a basis (`PROD` 260 / `CREDIT` 113 / `BEAR_DEBIT` 95 / `BEAR_HE` 17), no `CREDIT` row has a positive entry price, and the `BEAR_HE` / `BEAR_DEBIT` rows do carry the `trailing_stop` / `be_stop` exits that define those cells. The 2026-08-11 version bump recreated the tabs empty, and `append_rows` writes a header on an empty tab, which is what repaired it.<br><br>**v3 and earlier: permanently unreadable.** Those tab headers were never given the column name, so the values land in a nameless trailing field and are scrambled relative to their rows (measured 2026-08-14: of the 67 rows created after the BEAR_HE trail shipped — every one of which should carry a basis — 65 are blank, while 55 `BEAR_HE` and 11 `CREDIT` labels sit on rows created *before* the column existed; 7 of 13 `CREDIT`-tagged rows have a **positive** entry price, which `_exit_basis` cannot produce; and no `BEAR_HE`-tagged row has a `trailing_stop` exit). Those exports are frozen, so this never gets fixed. **"Blank = PROD-basis by definition" is the intent and is FALSE on a v3 export.**<br><br>**BacktestProxy: blank until the tab is re-run.** The column was declared in `_PROXY_KEY_ORDER` from the start, but `proxy.py::_evaluate` copied only `_RESULT_COLS` into the row, so no method's value ever reached the sheet — all 1,111 rows are blank in every era. Fixed 2026-09-02; the tab carries a basis only for rows written by a run after that.<br><br>**What changed structurally:** `scripts/align_tab_headers.py` now covers both backtest tabs against `core._KEY_ORDER` / `proxy._PROXY_KEY_ORDER` (it previously targeted `analysis_pipeline.config.ROW_COLUMNS` for every tab, which is the gap that let the column land nameless). Run `--dry-run` after any key-order change.<br><br>**Checked, not trusted (2026-09-02).** `scripts/backtest_study/lib/basis_audit.py` audits the label on every `load_book()` call and prints a coherence line; it REPORTS and never gates, because `_exit_basis` feeds nothing, so a bad label cannot move a simulated number — it can only mislead a stratification. Three checks: `CREDIT` ⇔ negative entry (the unconditional first branch, so provable from the row alone), a regime label against `MechLabeler.cell()` re-derived from the SPY/VIX table (independent of the sheet), and the stored `exit_reason` reachable under the claimed profile. All three are **one-directional** except the first: a basis can be ARMED without GOVERNING — on the v4 book 112 rows are labelled non-PROD but only 14 carry an outcome the base profile could not have produced, so `BEAR_HE` + `profit_target` is correct, not a conflict. Current reading: **485 coherent, 0 conflicts of any kind**; on an unreadable era every row audits as *unlabelled*, so v3 studies are untouched. A study that stratifies should filter on the record's `basis_trusted`.<br><br>**When NOT to use it even on v4:** to ask whether a row *replays* under some profile. The column names the profile the row was WRITTEN under; the audit confirms that label is self-consistent, which is still not the same as the row reproducing. Use `unreachable_reasons()` / `classify()` in `scripts/backtest_study/lib/replay_basis.py`, which key off the fact that `replay()` can only emit an exit reason whose governing knob is set. Stratifying a v4 book by exit profile is what the column IS for.<br><br>Both tabs are **append-only with no dedup**, so a full re-run leaves old and new rows side by side. When pooling rows across runs, filter on this column (plus `created_datetime`) rather than assuming one basis — a bare `python3 -m scripts.backtest` re-simulates the ENTIRE analysis tab, not just new dates. |

---

## Notes

- **Pricing priority per day** (`exit_sources` in `config/backtest.yml`): `barchart`
  (real per-contract daily history, marked to Bid/Ask mid), then `reappearance` (real
  flow `Trade` when the contract recurs). There is no model tier.
  Real marks are looked up as-of the day (most recent on or before), never
  forward-looking. Days with no new real mark carry the last real value forward;
  pure no-data days are empty in `daily_price_csv`.
- **A carried mark is bounded and labelled** (`simulation.max_price_carry_days`,
  default 5 calendar days): the price is still carried, but past the bound the day
  is tagged `barchart_stale` and counted in `pct_stale_days`. The bound applies to
  the `barchart` source only — a `reappearance` mark can still be carried without
  limit, which is rarer (it is sparse by nature) but has the same shape.
- **A zero bid is not a last trade.** `lib/barchart/options.py::_mark` falls through
  to `Latest` whenever either side of the quote is missing or zero, so a contract
  that has gone bid-less kept the price of its last trade, which can be days old and
  far above anything the position could be closed at. Since 2026-09-07 the
  simulation re-marks such a day off the quote instead: `0 × 0` → **0**, `0 × ask` →
  **ask/2** (robustness review B5). Bounded to days whose cached history row carries
  Bid/Ask; a row without them keeps the old mark.

  **DAILY MARKS ONLY since 2026-09-19.** That rule is a liquidation mark and it is
  sign-independent, so at ENTRY it handed a leg being SOLD half the ask as premium
  RECEIVED. An entry that falls through to the quote-derived mark is now priced on
  the side the leg trades: **bid (0) when sold, ask when bought**
  (`simulate._entry_side_mark`, `entry_source` tag `barchart_side`). Since
  2026-09-22 the rule also precedes an entry-day `Open` print. A two-sided quote
  is untouched, and still fills at the Open.
- **A junk quote is never a price (2026-09-24).** A quote is JUNK when
  `bid <= 0`, or `ask − bid > mid`, or `ask − bid > 2 × W(bid)`.
  `simulate._is_junk_quote` is the one test. W is the legacy Cboe maximum
  bid/ask width (`QUOTE_WIDTH_LIMITS`); the 2× is a judgement call.

  | Bid | W |
  |---|---|
  | under $2 | 0.25 |
  | $2 to under $5 | 0.40 |
  | $5 to under $10 | 0.50 |
  | $10 to under $20 | 0.80 |
  | $20 and up | 1.00 |
 A row with no Ask is NO QUOTE, not
  junk. HYG's 74P printed 0.11 against `0.09 × 5.00`; its mid was 2.545.

  | Where | Rule on a junk quote |
  |---|---|
  | Cost | That leg-side pays commission only; `cost_basis` says `no_spread_<side>` |
  | Daily and exit mark | The day's Latest if it traded (Volume > 0), tag `barchart_last` |
  | Same, no trade | The last good mark, carried and tagged `barchart_stale` |
  | Same, no bid | As above, but capped at the B5 mark: `ask/2`, or 0 |
  | Entry, sold leg, no bid | 0 — nothing is bid |
  | Entry, traded | The day's Open print, else its Latest |
  | Entry, sold leg, a bid | The bid |
  | Entry, bought leg, no trade | Refused: `junk_entry_quote` |

  The cap keeps B5's intent. A bid-less contract is worth about nothing, so it
  is never carried at an older, higher mark. A junk ask of 4.80 caps nothing.

  Every zero-bid quote is junk, so this supersedes the entry rule above: a
  bought leg no longer pays the ask. The exit-fill deferral (`exit_fill`) still
  keys on a zero bid only.
- **A debit structure that prices to a credit is refused.** `bull_call_spread`,
  `bear_put_spread`, `long_call` and `long_put` are debits by name
  (`classify.DEBIT_STRUCTURES`, derived from
  `lib/structure_names.canonical_debit_spreads()`). One of them priced to
  `entry_net < 0` is not a cheap fill — it is a leg priced off a quote that does not
  exist, or legs built in the wrong order for their label. Since 2026-09-19 no such
  row is written: the real backtest tallies it `debit_priced_to_credit`, the proxy
  puts that in `skip_reason` and appends the reason to `proxy_detail`. The gate runs
  before the exit profile is chosen, so `exit_basis = CREDIT` is unreachable from it.
  The mirror is below, under "No model prices".
- **Path cap**: `path_cap_days` (default 120) bounds far-dated/LEAP paths.
  `cap_open` rows were still alive at the cap — their `realized_pnl_pct` is the mark
  at the cap, not a closed trade. Since 2026-09-23 a path also stops at its data
  end, and `path_status` says which of the two ended it.
- All settings that shape these columns (`profit_target`, `stop_loss`,
  `path_cap_days`, `exit_sources`, `spread_width_pct`, `contracts`,
  `commission_per_contract`, `slippage_frac_of_spread`, `max_price_carry_days`)
  live in [`config/backtest.yml`](../config/backtest.yml).

## No model prices (2026-09-23)

Black-Scholes is gone from the backtest. No price, delta or IV on a new row is
model-generated. The operator ruled it on 2026-09-23.

What happens when a real price is missing:

| Where | Behaviour |
|---|---|
| Entry, a leg has no real price | The play is refused: `no_real_entry_price`, naming the leg |
| A path day, a leg has no new quote | The last real mark is carried; past `max_price_carry_days` it is tagged `barchart_stale` |
| Config lists `bs`, `risk_free_rate`, `uniform_bs_min_legs` or `proxy.bs_fallback: true` | The run refuses to start |

Five entry refusals are written as `skip_reason` on the proxy row and tallied by
the real backtest. They are checked in this order.

| Reason | Fires when |
|---|---|
| `no_real_entry_price` | A leg has no real price on the entry day |
| `junk_entry_quote` | A bought leg's entry quote is junk and the contract did not trade (2026-09-24) |
| `debit_priced_to_credit` | A debit structure (`bull_call_spread`, `bear_put_spread`, long single legs) nets a credit |
| `credit_priced_to_debit` | A credit structure (`bull_put_spread`, `bear_call_spread`, short single legs) nets a debit |
| `non_monotonic_entry_quote` | Two same-expiry legs are priced against strike order |

A credit priced to a debit used to be let through. That was not conservative.
The sizer treats a debit's premium as its risk. TLT 2025-04-04, a 90/85 bull put
spread, priced to a 0.35 debit off a stale 1.61 Open on the 85P. The sizer bought
38 contracts against a true risk near $500 each.

The strike-order check compares legs of one type and one expiry. A put never
costs more than a higher-strike put, and a call never costs more than a
lower-strike call. A leg filled at the touch on a one-sided quote is not judged.

Per-leg greeks come from each leg's own history row. The row is the entry day's,
or the row the leg's carried entry mark came from. Barchart's all-zero sentinel
rows count as missing. The net `delta` is blank if any leg's delta is missing.

`entry_underlying` is the median of the legs' `Price~`. It is never the
underlying OHLC cache: that cache is split-adjusted and `Price~` is as-traded.

A fetched history is refused when its `Price~` sits more than 25% from its
sibling contracts' (same ticker and expiry) on shared dates. Nothing is written
and nothing is unlinked. This guard exists because of
`META_20270115_630.00P.csv`, now in `backtests/option_history_cache/_quarantine/`.

Legacy `bs` rows remain in the frozen v1 to v3 exports. Studies drop them at read
time; see `scripts/backtest_study/lib/book.py`.

## BacktestProxy — untested plays, proxy-evaluated

Written by [`scripts/backtest/proxy.py`](../scripts/backtest/proxy.py)
(`python3 -m scripts.backtest.proxy`) to the `BacktestProxy` tab (mirror
`backtests/proxy_results.csv`). Each row is **one analysis play that never made it
into `BacktestResults`** — usually because its exact contract has no Barchart data —
with the reason it was skipped and a best-effort proxy verdict.

**Identity / join key**: `(signal_date, ticker, play-text prefix)` — normalized
(date-parsed, ticker upper-cased, play whitespace-collapsed + lower-cased, first
60 chars) on both sides so Sheets locale reparse can't break the join, and multiple
plays on one ticker/date stay distinct. Re-runs are idempotent: candidates whose
key already exists in `BacktestProxy` are dropped before writing. `--redo`
(requires `--date` or `--start`/`--end`) overrides the freeze for the bounded
window: matching rows are deleted from the tab and the plays re-evaluated — use it
after a classifier/pricing fix to refresh rows produced by the old code.

```bash
python3 -m scripts.backtest.proxy --config config/backtest.yml                  # all dates
python3 -m scripts.backtest.proxy --config config/backtest.yml --date 2026-04-21
python3 -m scripts.backtest.proxy --config config/backtest.yml --start … --end …
python3 -m scripts.backtest.proxy --config config/backtest.yml --dry-run        # no sheet/CSV write
python3 -m scripts.backtest.proxy --config config/backtest.yml --cache-only    # no Barchart scraping
python3 -m scripts.backtest.proxy --config config/backtest.yml --date 2026-04-21 --redo  # re-evaluate + replace
```

| Column | Definition |
|--------|-----------|
| **skip_reason** | Why the real backtest wrote no row. Build-time: `unsupported`, `no_strike`, `no_expiry`, `inverted_vertical`, `vetoed`. Cache: `no_history`, `unpriced`, `snap_priced` (see below). Entry refusals: the four listed under [No model prices](#no-model-prices-2026-09-23); `proxy_detail` carries the legs and the net. |
| **proxy_method** | Which rung produced the verdict: `strike_expiry_tweak`, then `underlying_trend`, then `unevaluable`. Older rows can carry `bs_options_hist`, the deleted model tier; exclude them from any evidence read. |
| **proxy_detail** | Method-specific evidence. Tweaks are recorded as `orig → used` per leg. Trend rows carry `direction_correct=True/False` and the underlying move. Legacy `bs_options_hist` rows note a donor contract and sigma. |
| **legs / legs_original** | `legs` = the position actually priced (tweaked legs for method 1, the play's own legs otherwise); `legs_original` = the play's own legs. Same sheet-safe leg format as `BacktestResults`. |
| _(result columns)_ | Same names and definitions as `BacktestResults` (`entry_*`, `realized_pnl_pct`, `exit_reason`, `mfe_*`/`mae_*`, `daily_price_csv`, …) so the two tabs union downstream. Blank for `underlying_trend` (P&L not computable — `exit_reason` = `direction_only`) and `unevaluable` rows. |

**The cache reasons** name what the chain found, not only the named contract.

| `skip_reason` | Meaning |
|---|---|
| `unpriced` | The named anchor has history at the signal date; the real backtest skipped it for another reason |
| `snap_priced` | The named anchor had no history; method 1 then priced the play from real history |
| `no_history` | The named anchor had no history, and the chain priced nothing real |

A `snap_priced` row either moved a leg (`proxy_detail` shows `orig → used`) or
priced the named contract after the probe fetched it (`all legs had listed history`).
A `no_history` row is always `underlying_trend` or `unevaluable`.

Rows written before 2026-09-24 still say `no_history` where they priced real.
On those, read `proxy_method` first: `strike_expiry_tweak` means priced real.
The label was set before the snap ran.

**Fallback chain semantics** (one verdict per play, most-realistic first):

1. `strike_expiry_tweak` — every leg snaps to the nearest listed contract WITH
   history (bounded by `proxy.max_strike_steps` strike steps and
   `proxy.max_expiry_deviation_days` days); priced through the normal real-first
   path, so `entry_source`/`pct_real_days` read as usual. Legs that share an
   original expiration are pinned to ONE snapped expiration (a vertical can't
   silently become a diagonal); if the pin can't be satisfied the method fails
   over to 2 instead of pricing a mangled structure.
2. `underlying_trend` — direction-only verdict from the donor's `Price~` path vs
   the structure's bullish/bearish bias; neutral structures skip to 3. This is
   where directional plays without a snappable contract land.
3. `unevaluable` — no usable options history at all, or the play never built.

The model rung `bs_options_hist` sat between 1 and 2. It was switched off on
2026-08-11 and deleted on 2026-09-23. Its rows were model-priced end to end and
attenuated every measured effect (`research/current.md`, 2026-08-11 addendum).

Exit rules and sizing come from the **same `simulation:` /
`credit:` blocks** the real backtest uses, so P&L columns are directly comparable.
Contract discovery is cache-first (`backtests/option_history_cache/`); with
`proxy.probe_barchart: true` (default) missing neighbors are scraped from Barchart
and land in the cache. `--cache-only` disables scraping. All `proxy:` keys live in
[`config/backtest.yml`](../config/backtest.yml).

## Inspecting signal-quality gates (`--skip-llm`)

The backtest reads the stored LLM plays, **not** the conviction score — so a
score change (e.g. the `FinPenalty`) only reaches the backtest after the analysis
pipeline is re-run. To see the gate's effect on the scored rollup directly,
re-run the fetch step:

```bash
python3 -m scripts.analysis_pipeline --skip-llm --date 2025-03-13
```

This regenerates `audit/<date>-rollup.csv` + `-oi-breakdown.csv` with the current
scoring — including the `FinPenalty` column and the penalized `Score` — so you
can confirm financing-dominated names (high `FinancingShare`) have dropped out of
`high-conv`. The two signal-quality gates validated on the Mar-2025 window (see
[`research/archive/01`](../research/archive/01-exit-rules-attempts-1-7.md) §Financing & IVSpread gates):

- **Financing penalty** — `FinancingShare` > 0.60 demotes the name; stock-substitute
  positioning, not a directional bet. Baked into the score
  ([`docs/conviction-score.md`](conviction-score.md), `FinPenalty` column).
- **IVSpread directional gate** — a BEAR play with `IVSpread` below ≈ −25 is
  buying overpriced panic-hedge puts. Direction-bearing, so it stays in Step 5 /
  the directional thesis, not the agnostic score.

To carry these through to actual P&L, re-run the full pipeline (LLM) for the
dates, then re-run the backtest on the refreshed analysis rows.
