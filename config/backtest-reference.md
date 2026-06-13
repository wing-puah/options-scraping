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

| Column | Definition |
|--------|-----------|
| **signal_date** | Analysis date the play was proposed (ISO `YYYY-MM-DD`). Entry is at this day's flow print. |
| **ticker** | Underlying symbol. |
| **structure** | Resolved trade structure: `long_call`, `long_put`, `bull_call_spread`, `bear_put_spread`, `bull_put_spread`, `bear_call_spread`, `short_put`, `short_call`, `iron_condor`. |
| **opt_type** | `Call`, `Put`, or `IC` (iron condor). |
| **k_long** | Primary/long leg strike (for credit structures, the sold leg; for iron condors, the short put anchor). |
| **k_short** | Contra-leg strike, or `""` for single-leg. Iron condors store `lp/sc/lc` (long-put / short-call / long-call). |
| **expiration** | Raw expiration string from the flow row (ISO datetime with offset). |
| **dte_entry** | Days to expiration at entry. |
| **iv_entry_pct** | Implied vol of the matched contract at entry (%). |
| **delta** | Delta of the matched long leg at entry (flow row value; blank for iron condors). |
| **entry_underlying** | Underlying price (`Price~`) at entry. |

## Entry pricing

| Column | Definition |
|--------|-----------|
| **entry_option_price** | Net price paid (debit) or received (credit) per share, in option points. For spreads this is `long_leg − contra_leg`. **This is the denominator for every P&L figure and the unit of `daily_price_csv`.** |
| **entry_premium_total** | `entry_option_price × 100 × contracts` — dollar cost/credit of the position. |
| **entry_source** | How each leg was priced at entry. `real` = actual flow `Trade` price; `bs` = Black-Scholes; for spreads it is `<long>+<contra>`, e.g. `real+barchart`, `real+bs`, `bs+barchart`. Iron condors are fully `bs` (all four legs modelled for internal consistency). |
| **regime** | The play's ticker-specific regime label carried from the analysis row (not the market read). |
| **play** | The play text (truncated to 300 chars). |

## Realized exit & excursions (path-derived)

These summarise the **full daily path**. The realized exit is the **first** day a
rule triggers — frozen at that day's mark (never a later live mark).

| Column | Definition |
|--------|-----------|
| **realized_pnl_pct** | Realized P&L % at the exit. For debit structures `(exit − entry)/entry`; for credit structures `(entry − exit)/entry` (profit when the position decays). |
| **realized_pnl_abs** | Realized P&L in dollars (`realized_pnl_pct × entry_option_price × 100 × contracts`). |
| **days_held** | Trading days from entry to the realized exit. |
| **exit_reason** | Why the trade closed: `profit_target` (hit `+profit_target`), `stop_loss` (hit `−stop_loss`), `expired` (held to expiry with no trigger; path ran the full DTE), `cap_open` (still open at `path_cap_days` because DTE exceeded the cap), `no_data` (no day could be priced). |
| **mfe_pct** | **Max Favorable Excursion** — the best P&L % the trade ever reached over the *whole* path, independent of the exit rule. Use this to tune the profit target. |
| **mfe_day** | Trading-day index (1-based) where MFE occurred. |
| **mae_pct** | **Max Adverse Excursion** — the worst P&L % over the whole path. Use this to tune the stop. |
| **mae_day** | Trading-day index (1-based) where MAE occurred. |
| **pnl_at_cap_pct** | P&L % on the last priced day of the path (the "held to the end / never exited" comparison). |
| **pct_real_days** | Fraction (%) of priced path days marked from **real** data (Barchart / flow reappearance) vs Black-Scholes. A data-quality gauge: low values mean the path is mostly modelled. |

## The daily path

| Column | Definition |
|--------|-----------|
| **daily_price_csv** | Comma-separated **net option/spread mark, one value per trading day** from the day after entry to `min(DTE, path_cap_days)`. Same units as `entry_option_price`. An **empty token** (`,,`) is a day no source could price. Reconstruct the P&L path by splitting on `,`, dropping empties, and applying the credit/debit sign vs `entry_option_price` (see `pnl_path()` in [`scripts/chart_backtest.py`](../scripts/chart_backtest.py)). |

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
