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
| **structure** | Resolved trade structure label: `long_call`, `long_put`, `bull_call_spread`, `bear_put_spread`, `bull_put_spread`, `bear_call_spread`, `short_put`, `short_call`, `iron_condor`, or `explicit_legs` (the play named its legs directly). Kept as a grouping label; the authoritative position is `legs`. |
| **legs** | The full position as one or more signed legs, one per line, in the form `<TICKER>:<YYYY-MM-DD>:<STRIKE>:<C\|P> <signed_qty>` — e.g. `NVDA:2026-07-17:250:C +1` / `NVDA:2026-07-17:270:C -1`. The signed quantity is **last** so the cell never starts with `+`/`-` (Google Sheets would coerce a leading sign into a formula); parsing also accepts the legacy quantity-first form. `qty` is the per-unit ratio (sign = long/short); a separate `contracts` column holds the risk-sized number of units. Each leg carries **its own expiration**, so calendar / diagonal / ratio spreads are representable. Replaces the old `k_long` / `k_short` / `expiration` / `opt_type` columns. |
| **entry_leg_detail** | Per-leg raw entry breakdown (sits beside `legs`) so the netted `entry_option_price`, `iv_entry_pct` and `delta` can be validated leg-by-leg. One line per leg, aligned with `legs`: `<TICKER>:<EXP>:<STRIKE>:<C\|P> <±qty>  px=<raw price> iv=<entry IV %> delta=<delta> [<source>]`. `entry_option_price` = `Σ qty·px` and `delta` = `Σ qty·delta`. The anchor leg's `delta` is the real flow value; all other legs' deltas are Black-Scholes model deltas at the entry IV. Each line leads with the contract (never a sign) so the cell stays sheet-safe. |
| **contracts** | Risk-sized number of units of the `legs` structure (fixed-fractional sizing on `abs(entry_option_price)`). |
| **dte_entry** | Days to expiration at entry (anchor leg). |
| **iv_entry_pct** | Implied vol of the anchor contract at entry (%). |
| **delta** | **Net position delta** at entry = `Σ qty·delta` over the legs (the anchor leg uses the real flow delta, other legs the Black-Scholes model delta at entry IV; the same per-leg deltas appear in `entry_leg_detail`). |
| **entry_underlying** | Underlying price (`Price~`) at entry. |

## Entry pricing

| Column | Definition |
|--------|-----------|
| **entry_option_price** | **Signed** net per share, in option points: `Σ qty·price` over the legs. **Positive = net debit (paid), negative = net credit (received).** Its **absolute value** is the denominator for every P&L figure; `daily_price_csv` marks carry the same signed convention. |
| **entry_premium_total** | `abs(entry_option_price) × 100 × contracts` — dollar cost/credit of the position. |
| **entry_source** | How each leg was priced at entry, joined with `+` in leg order. `real` = anchor flow `Trade` price; `barchart` = real Barchart history; `bs` = Black-Scholes. E.g. `real`, `real+barchart`, `real+bs`. Uniform-BS positions (≥ `uniform_bs_min_legs` legs, e.g. iron condors) report `bs` (all legs modelled at one IV for internal consistency). |
| **regime** | The play's ticker-specific regime label carried from the analysis row (not the market read). |
| **play** | The play text (truncated to 300 chars). |

## Realized exit & excursions (path-derived)

These summarise the **full daily path**. The realized exit is the **first** day a
rule triggers — frozen at that day's mark (never a later live mark).

| Column | Definition |
|--------|-----------|
| **realized_pnl_pct** | Realized P&L % at the exit, from the single signed formula `(V_exit − entry_net) / abs(entry_net)` where `V` is the position's signed net mark. Profit is positive for both debit and credit positions (a credit has `entry_net < 0` and profits as `V` rises toward 0). |
| **realized_pnl_abs** | Realized P&L in dollars (`realized_pnl_pct × abs(entry_option_price) × 100 × contracts`). |
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
| **daily_price_csv** | Comma-separated **signed net position mark (`Σ qty·price`), one value per trading day** from the day after entry to `min(nearest-leg DTE, path_cap_days)`. Same signed units as `entry_option_price`. An **empty token** (`,,`) is a day no source could price (any unpriceable leg blanks the whole day). Reconstruct the P&L path by splitting on `,`, dropping empties, and applying `(mark − entry_option_price) / abs(entry_option_price)` (see `pnl_path()` in [`scripts/chart_backtest.py`](../scripts/chart_backtest.py)). |

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
