# Backtest Results — Column Reference

Column definitions for the `BacktestResults` Google Sheet (and the mirror
`backtests/results.csv`), written by [`scripts/backtest.py`](../scripts/backtest.py).

Each row is **one simulated play** — a non-MARKET ticker row from the analysis tab
that carried a play, matched to its real flow contract and tracked day-by-day from
entry to expiry (or the `path_cap_days` cap, whichever comes first).

There are **no per-checkpoint (`d1`/`d5`/`d21`…) columns**. Every P&L figure is
derived from the full daily mark series stored in `daily_price_csv`; analysis code
samples whatever holding horizons it wants from that path.

---

## Entry & contract identity

<!-- prettier-ignore -->
| Column | Definition |
|--------|-----------|
| **signal_date** | Analysis date the play was proposed (ISO `YYYY-MM-DD`). The entry fill is taken on the FIRST trading day AFTER this date under `simulation.entry_timing: next_open` (the default — the analysis is produced after the close), or on this date's EOD mark under `signal_eod`. |
| **ticker** | Underlying symbol. |
| **structure** | Resolved trade structure label: `long_call`, `long_put`, `bull_call_spread`, `bear_put_spread`, `bull_put_spread`, `bear_call_spread`, `short_put`, `short_call`, `iron_condor`, or `explicit_legs` (the play named its legs directly). Kept as a grouping label; the authoritative position is `legs`. |
| **legs** | The full position as one or more signed legs, one per line, in the form `<TICKER>:<YYYY-MM-DD>:<STRIKE>:<C\|P> <signed_qty>` — e.g. `NVDA:2026-07-17:250:C +1` / `NVDA:2026-07-17:270:C -1`. The signed quantity is **last** so the cell never starts with `+`/`-` (Google Sheets would coerce a leading sign into a formula); parsing also accepts the legacy quantity-first form. `qty` is the per-unit ratio (sign = long/short); a separate `contracts` column holds the risk-sized number of units. Each leg carries **its own expiration**, so calendar / diagonal / ratio spreads are representable. The position is fully generic in leg count — any structure (single leg, vertical, ratio, butterfly, condor, box, iron condor, …) is just a list of signed legs. To backtest a hand-authored structure, write its legs (one per line) in the play cell; it is recognised as `explicit_legs`, bypasses the freeform classifier, and same-contract legs are merged (e.g. `+2` / `-1` → `+1`). Replaces the old `k_long` / `k_short` / `expiration` / `opt_type` columns. |
| **entry_leg_detail** | Per-leg raw entry breakdown (sits beside `legs`) so the netted `entry_option_price`, `iv_entry_pct` and `delta` can be validated leg-by-leg. One line per leg, aligned with `legs`: `<TICKER>:<EXP>:<STRIKE>:<C\|P> <±qty>  px=<raw price> iv=<entry IV %> delta=<delta> [<source>]`. `entry_option_price` = `Σ qty·px` and `delta` = `Σ qty·delta`. The anchor leg's `delta` is the real flow value; all other legs' deltas are Black-Scholes model deltas at the entry IV. Each line leads with the contract (never a sign) so the cell stays sheet-safe. |
| **contracts** | Risk-sized number of units of the `legs` structure. Debit (`entry_option_price > 0`): fixed-fractional sizing on the premium paid (`abs(entry_option_price) × stop_loss`). Credit (`entry_option_price < 0`): sized on the structure's STRUCTURAL max loss (`max_loss_per_contract`, below), not the credit received — a thin credit on a wide/naked structure would otherwise be wildly oversized against the risk budget. When a credit's max loss can't be bounded (naked short call, multi-expiration credit), falls back to `1` and logs a warning. See `_size_contracts` in [`scripts/backtest/simulate.py`](../scripts/backtest/simulate.py). |
| **dte_entry** | Days to expiration at entry (anchor leg), measured from the entry day — one less than the signal-date DTE when the entry is the next day's open. |
| **iv_entry_pct** | Implied vol of the anchor contract at entry (%). |
| **delta** | **Net position delta** at entry = `Σ qty·delta` over the legs (the anchor leg uses the real flow delta, other legs the Black-Scholes model delta at entry IV; the same per-leg deltas appear in `entry_leg_detail`). |
| **entry_underlying** | Underlying price (`Price~`) at entry. |

## Entry pricing

<!-- prettier-ignore -->
| Column | Definition |
|--------|-----------|
| **entry_option_price** | **Signed** net per share, in option points: `Σ qty·price` over the legs. **Positive = net debit (paid), negative = net credit (received).** Its **absolute value** is the denominator for every P&L figure; `daily_price_csv` marks carry the same signed convention. |
| **entry_premium_total** | `abs(entry_option_price) × 100 × contracts` — dollar cost/credit of the position. |
| **entry_source** | How each leg was priced at entry, joined with `+` in leg order. `barchart_open` = the entry day's real Open (the `next_open` fill); `barchart` = real Barchart EOD mark (the entry day had a blank Open — zero-volume — or the fill fell back to the signal day's EOD because no later day existed in the staleness window); `real` = anchor flow `Trade` price; `bs` = Black-Scholes. E.g. `barchart_open`, `barchart_open+barchart`, `real+bs`. All legs are priced on ONE shared entry day. Every structure — including explicit multi-leg of any leg count — is priced real-first per leg; only *synthesized* iron condors (wings at non-listed strikes) are priced uniform-BS and report `bs` (all legs modelled at one IV for internal consistency). |
| **market_regime** | The market-level regime for that date (from the MARKET row), truncated at the first em-dash — e.g. `BULL TREND`. |
| **regime** | The play's ticker-specific regime label carried from the analysis row (not the market read). |
| **play** | The play text (truncated to 300 chars). |

## Flow-rollup context (joined)

Per-ticker signal context from that signal date's scored rollup, kept separate from
the model's `signal` evidence. As of the analysis-pipeline change these are written
onto the analysis row itself at analysis time (the `oi_confirm_pct` / `cpir` /
`iv_spread` columns on AnalysisClaude / AnalysisGPT), so the backtest reads them
straight off the row. For rows written before those columns existed, the backtest
backfills from `audit/<date>-rollup.csv` by `(signal_date, ticker)`
(`_attach_rollup_metrics` in [`scripts/backtest/core.py`](../scripts/backtest/core.py));
blank when neither the row nor an audit file has the value. See
[`config/rollup-reference.md`](rollup-reference.md) for the full definitions.

<!-- prettier-ignore -->
| Column | Definition |
|--------|-----------|
| **oi_confirm_pct** | `OIConfirmPct` — share of the ticker's flow trades whose next-day OI change confirmed an opening position (ref-03 open-confirmation). Decimal fraction (0.45 = 45%). |
| **cpir** | `CPIR` — Call-Put Information Ratio `OIFC / (OIFC + OIFP)`, in `[0,1]`. > 0.5 = call-skewed informed opening (bullish); < 0.5 = put-skewed. |
| **iv_spread** | `IVSpread` — OI-weighted (call IV − put IV) across matched strike/expiry pairs, 10–60 DTE, on settlement IV (Cremers/Weinbaum). Positive → bullish (a positive predictor of returns). Missing counterpart legs are backfilled from Barchart price-history (`scripts/collector/fetch_counterpart_iv.py`), so coverage depends on whether that date's `counterpart-iv-*.csv` sidecar has been built. ⚠️ The old ≈ −25 BEAR veto was tuned on the prior premium-weighted/unmatched definition — **re-derive** before applying. `—`/empty when no matched pair. |

## Realized exit & excursions (path-derived)

These summarise the **full daily path**. The realized exit is the **first** day a
rule triggers — frozen at that day's mark (never a later live mark).

<!-- prettier-ignore -->
| Column | Definition |
|--------|-----------|
| **realized_pnl_pct** | Realized P&L % at the exit, from the single signed formula `(V_exit − entry_net) / abs(entry_net)` where `V` is the position's signed net mark. Profit is positive for both debit and credit positions (a credit has `entry_net < 0` and profits as `V` rises toward 0). |
| **realized_pnl_abs** | Realized P&L in dollars (`realized_pnl_pct × abs(entry_option_price) × 100 × contracts`). |
| **days_held** | Trading days from entry to the realized exit. |
| **exit_reason** | Why the trade closed: `profit_target` (hit `+profit_target`), `stop_loss` (hit `−stop_loss`), `expired` (held to expiry with no trigger; path ran the full DTE), `cap_open` (still open at `path_cap_days` because DTE exceeded the cap), `no_data` (no day could be priced). |
| **mfe_pct** | **Max Favorable Excursion** — the best P&L % the trade ever reached over the _whole_ path, independent of the exit rule. Use this to tune the profit target. |
| **mfe_day** | Trading-day index (1-based) where MFE occurred. |
| **mae_pct** | **Max Adverse Excursion** — the worst P&L % over the whole path. Use this to tune the stop. |
| **mae_day** | Trading-day index (1-based) where MAE occurred. |
| **pnl_at_cap_pct** | P&L % on the last priced day of the path (the "held to the end / never exited" comparison). |
| **pct_real_days** | Fraction (%) of priced path days marked from **real** data (Barchart / flow reappearance) vs Black-Scholes. A data-quality gauge: low values mean the path is mostly modelled. |

## The daily path

<!-- prettier-ignore -->
| Column | Definition |
|--------|-----------|
| **daily_price_csv** | Comma-separated **signed net position mark (`Σ qty·price`), one value per trading day** from the day after entry to `min(nearest-leg DTE, path_cap_days)`. Same signed units as `entry_option_price`. An **empty token** (`,,`) is a day no source could price (any unpriceable leg blanks the whole day). Reconstruct the P&L path by splitting on `,`, dropping empties, and applying `(mark − entry_option_price) / abs(entry_option_price)` (see `pnl_path()` in [`scripts/chart_backtest.py`](../scripts/chart_backtest.py)). |
| **daily_pnl_csv** | Comma-separated **absolute dollar P&L per SINGLE contract, one value per trading day**, on the exact same day grid + blank-token convention as `daily_price_csv`: `(mark − entry_option_price) · 100`. Per-contract — **NOT** scaled by `contracts` (that scaling lives in `realized_pnl_abs`/`mfe_abs`). |

## Structural risk (credit/debit, Attempt 8)

Independent of the daily path — computed once at simulate time from the position's
legs and `entry_option_price`, not from the day-by-day marks. Placed at the
**physical end** of the sheet schema (`_KEY_ORDER`, after `daily_pnl_csv`) for the
same append-alignment reason as `daily_pnl_csv`: `append_rows` only writes a header
on an empty tab, so inserting a column mid-schema would misalign every existing row.

<!-- prettier-ignore -->
| Column | Definition |
|--------|-----------|
| **max_loss_per_contract** | Structural worst-case loss per contract, in dollars: `_max_loss_per_unit(legs, entry_option_price) × 100`. Debit = the premium paid (`entry_option_price × 100`) — same convention as the existing sizing, so a net-debit ratio with naked short legs understates true risk here too. Credit = `(entry_option_price − worst expiration payoff) × 100`, i.e. the credit received minus the structure's floor. **Blank (`""`)** when the max loss can't be bounded (net short calls, multi-expiration credit/calendar/diagonal) — `_size_contracts` falls back to 1 contract with a warning in that case. |
| **pnl_on_risk_pct** | `realized_pnl_abs / (max_loss_per_contract × contracts)`, a **decimal fraction** (0.20 = 20%) of the position's own structural risk budget, rounded to 4dp. For debit trades this is mathematically identical to `realized_pnl_pct` (the denominator is the same premium paid). For credit trades it re-expresses the premium-relative `realized_pnl_pct` against the structure's true max loss instead — the number that matters for comparing risk-adjusted return across credit and debit plays on one scale. **Blank (`""`)** when `max_loss_per_contract` is blank, or when `realized_pnl_abs` isn't numeric (`exit_reason == "no_data"`). |

## Model score & horizon (joined off the analysis row)

Carried straight off the analysis row (not produced by simulation), so each
component can be measured against realized P&L and pruned. `horizon` sits beside
`play`; the `score_*` block is appended at the end. Blank on rows written before
these columns existed. These replaced the old high/medium/low `confidence` label.

<!-- prettier-ignore -->
| Column | Definition |
|--------|-----------|
| **horizon** | The play's DTE bucket boundary (`14`\|`60`\|`180`\|`720`) — the dominant expiry of the cited evidence. Read off its own analysis-row column (legacy rows: regex-scraped from the play bracket). Drives expiry synthesis when no explicit month/day is named (`_resolve_expiry`). |
| **score_total** | Sum of the five component points below (0–100), computed at row-expansion time — never model-produced. Interpretation only: ≥70 strong · 40–69 moderate · <40 weak. |
| **score_flow** / **score_dealer** / **score_price** / **score_vol** / **score_catalyst** | The five framework Step-5 evidence-quality factors, each an integer point award. Per-factor maxima are intent-weighted (DIRECTIONAL/HEDGE/SYNTHETIC STOCK: 25/25/20/15/15; VOLATILITY: 20/25/10/25/20). |

## Exit basis

<!-- prettier-ignore -->
| Column | Definition |
|--------|-----------|
| **exit_basis** | Which exit profile governed the simulation of this row. `PROD` = the base `simulation:` block. `CREDIT` = the `simulation.credit:` override (any row with `entry_option_price < 0`; credits are never regime-switched). `BEAR_HE` = the mechanical-regime exit override fired (`simulation.regime_exit.cells`, shipped 2026-07-22 — see `config/deployment-rules.md` §Exit management). `NONE` = BacktestProxy `underlying_trend` tier only, where no exit rules run at all. **Blank (`""`) = the row was written before this column existed, i.e. PROD-basis by definition.** <br><br>Both tabs are **append-only with no dedup**, so a full re-run leaves old and new rows side by side. When pooling rows across runs, filter on this column (plus `created_datetime`) rather than assuming one basis — a bare `python3 -m scripts.backtest` re-simulates the ENTIRE analysis tab, not just new dates. |

---

## Notes

- **Pricing priority per day** (`exit_sources` in `config/backtest.yml`): `barchart`
  (real per-contract daily history, marked to Bid/Ask mid) → `reappearance` (real
  flow `Trade` when the contract recurs) → `bs` (Black-Scholes, last resort).
  Real marks are looked up **as-of** the day (most recent on-or-before), never
  forward-looking. Days with no real mark carry the last real value forward; pure
  no-data days are empty in `daily_price_csv`.
- **BS-filled days hold entry IV constant**, so stretches priced by Black-Scholes
  are smooth/deterministic in the underlying. `pct_real_days` tells you how much of
  a path to trust.
- **Path cap**: `path_cap_days` (default 120) bounds far-dated/LEAP paths.
  `cap_open` rows were still alive at the cap — their `realized_pnl_pct` is the mark
  at the cap, not a closed trade.
- All settings that shape these columns (`profit_target`, `stop_loss`,
  `path_cap_days`, `exit_sources`, `spread_width_pct`, `contracts`, `risk_free_rate`)
  live in [`config/backtest.yml`](backtest.yml).

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

<!-- prettier-ignore -->
| Column | Definition |
|--------|-----------|
| **skip_reason** | Why the real backtest produced no row: `unsupported` (structure has no handler), `no_strike` / `no_expiry` (play text unparseable), `no_history` (contract's Barchart history missing or not covering the entry window), `unpriced` (history covers the window but the sim still couldn't price entry). |
| **proxy_method** | Which rung of the fallback chain produced the verdict: `strike_expiry_tweak` → `bs_options_hist` → `underlying_trend` → `unevaluable`. |
| **proxy_detail** | Method-specific evidence. Tweaks are recorded as `orig → used` per leg; BS rows note the donor contract + entry sigma; trend rows carry `direction_correct=True/False` and the underlying move. |
| **legs / legs_original** | `legs` = the position actually priced (tweaked legs for method 1, the play's own legs otherwise); `legs_original` = the play's own legs. Same sheet-safe leg format as `BacktestResults`. |
| _(result columns)_ | Same names and definitions as `BacktestResults` (`entry_*`, `realized_pnl_pct`, `exit_reason`, `mfe_*`/`mae_*`, `daily_price_csv`, …) so the two tabs union downstream. Blank for `underlying_trend` (P&L not computable — `exit_reason` = `direction_only`) and `unevaluable` rows. |

**Fallback chain semantics** (one verdict per play, most-realistic first):

1. `strike_expiry_tweak` — every leg snaps to the nearest listed contract WITH
   history (bounded by `proxy.max_strike_steps` strike steps and
   `proxy.max_expiry_deviation_days` days); priced through the normal real-first
   path, so `entry_source`/`pct_real_days` read as usual. Legs that share an
   original expiration are pinned to ONE snapped expiration (a vertical can't
   silently become a diagonal); if the pin can't be satisfied the method fails
   over to 2 instead of pricing a mangled structure.
2. `bs_options_hist` — the play's **actual** legs are Black-Scholes-priced per
   day using a nearby donor contract's history: `Price~` as the underlying series
   and `IV/100` as a per-day sigma. No yfinance anywhere.
3. `underlying_trend` — direction-only verdict from the donor's `Price~` path vs
   the structure's bullish/bearish bias; neutral structures skip to 4.
4. `unevaluable` — no usable options history at all, or the play never built.

Exit rules, sizing and the risk-free rate come from the **same `simulation:` /
`credit:` blocks** the real backtest uses, so P&L columns are directly comparable.
Contract discovery is cache-first (`backtests/option_history_cache/`); with
`proxy.probe_barchart: true` (default) missing neighbors are scraped from Barchart
and land in the cache. `--cache-only` disables scraping. All `proxy:` keys live in
[`config/backtest.yml`](backtest.yml).

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
[`config/backtest-tuning/`](backtest-tuning/archive/01-exit-rules-attempts-1-7.md) §Financing & IVSpread gates):

- **Financing penalty** — `FinancingShare` > 0.60 demotes the name; stock-substitute
  positioning, not a directional bet. Baked into the score
  ([`config/conviction-score.md`](conviction-score.md), `FinPenalty` column).
- **IVSpread directional gate** — a BEAR play with `IVSpread` below ≈ −25 is
  buying overpriced panic-hedge puts. Direction-bearing, so it stays in Step 5 /
  the directional thesis, not the agnostic score.

To carry these through to actual P&L, re-run the full pipeline (LLM) for the
dates, then re-run the backtest on the refreshed analysis rows.
