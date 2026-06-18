# Flow rollup reference

Per-ticker aggregation produced by `_flow_ticker_rows()` in `lib/flow_summary.py`.
The rollup table is what the LLM reads (markdown) and what the audit CSV stores.
For the conviction score that ranks tickers, see `config/conviction-score.md`.

## What "rollup" means

Each compiled flow CSV has one row per executed trade. The rollup collapses all
trades for a ticker into a single row of aggregated signals — the input to both
the LLM analysis and the conviction scorer.

---

## Premium columns

| Column | Computation | Notes |
|--------|------------|-------|
| `Total$` | Σ premium across all trades | Raw headline number; can be inflated by deep-ITM financing flow |
| `Call$` | Σ premium, call trades only | |
| `Put$` | Σ premium, put trades only | |
| `C/P` | `Call$ / Put$` | > 1 = call-heavy; ∞ when no put premium |
| `Ext$` | Σ extrinsic = Σ max(premium − intrinsic_per_share × size × 100, 0) | Strips ITM intrinsic. Missing Price~/Strike → extrinsic = full premium (no discount) |
| `OTM$` | Σ extrinsic × (1−\|delta\|) | OTM-probability-weighted extrinsic (Hilliard et al. 2025). Only trades with a Delta cell contribute; absent data is never credited. Rewards OTM informed flow. |
| `Fin%` | Σ premium where \|delta\| ≥ 0.85 / Total$ | Stock-substitute fraction. High = read as positioning/financing, not directional conviction |
| `ΔNot$` | Σ delta × size × 100 × spot | Signed share-equivalent dollar exposure. Positive = net long delta |

---

## Size columns

| Column | Computation |
|--------|------------|
| `Trades` | Count of raw flow rows for this ticker |
| `Ctts` | Σ Size (number of option contracts) |
| `$/ct` | Total$ / Ctts — premium per contract; high = expensive/high-IV/deep-ITM options |

---

## Sentiment columns

Classified per trade by `_classify_sentiment(opt_type, side)` using Barchart's
conventions (call-on-ask = bullish, put-on-bid = bullish, call-on-bid = bearish,
put-on-ask = bearish, anything-mid = neutral):

| Column | Computation |
|--------|------------|
| `Bull` | Count of bullish trades |
| `Bear` | Count of bearish trades |
| `Mid` | Count of neutral (mid) trades |

---

## Opening-flag columns

Parsed from the `*` column (BuyToOpen / SellToOpen / ToOpen):

| Column | Computation |
|--------|------------|
| `BTO` | Count of BuyToOpen trades |
| `STO` | Count of SellToOpen trades |
| `ToOpen` | Count of ToOpen trades |

Any non-zero BTO/STO/ToOpen feeds the `open` (+1) conviction score component.

---

## Time / horizon columns

| Column | Computation | Notes |
|--------|------------|-------|
| `wDTE` | Premium-weighted average DTE | |
| `Hzn` | Dominant DTE bucket by **extrinsic** premium | Extrinsic, not raw premium, so financing/ITM trades don't skew the horizon. Buckets: `event` ≤14, `tact` ≤60, `med` ≤180, `strat` >180. Example: `tact 64%` = 64% of extrinsic premium falls in the tactical bucket. |

---

## IV columns

| Column | Computation | Notes |
|--------|------------|-------|
| `wIV%` | Premium-weighted average IV (all trades) | |
| `IVspr` | Premium-weighted call IV − put IV | Positive → bullish IV skew. Lin, Lu & Driessen (2013): positive predictor of returns. `—` when either side has no premium. |
| `IVskew` | OTM-put IV − ATM-call IV | OTM-put band: \|delta\| ≤ 0.40. ATM-call band: 0.40–0.60. Steeper positive → downside demand; negative predictor of returns. `—` when either band is empty. |

`IVspr` and `IVskew` are directional reads — kept **out of the direction-agnostic
conviction score** but available to the LLM for Step 5 vol-alignment.

---

## OI enrichment columns *(populated D+1 after enrich_oi.py)*

These columns are only non-blank when the compiled file has been enriched.
The per-ticker values are aggregated from `oi_change` (D-day OI change per contract).

### Rollup summary (one value per ticker)

| Column | Computation | Notes |
|--------|------------|-------|
| `OIConf%` | `count(oi_change > 0) / count(enriched contracts) × 100` | % of this ticker's contracts where OI *increased* on trade day — the open-confirmation rate. 100% = all flow confirmed as opening; 0% = all closing/rolling. |
| `CPIR` | `oi_change_calls / (oi_change_calls + oi_change_puts)` | Call-put OI information ratio (Hu et al. 2023, ref 03). > 0.5 = call-skewed OI opening = bullish informed flow. `—` when net OI change is 0 across both sides. |

### OI breakdown section (per-ticker DTE × moneyness table)

Appended after raw trades. Shows `oi_change` summed by **DTE bucket × moneyness band**
so the LLM can see *where* the OI is opening or closing:

**DTE buckets:** `event` (≤14), `tact` (≤60), `med` (≤180), `strat` (>180)

**Moneyness bands** (computed as `(strike − spot) / spot × 100` for calls,
`(spot − strike) / spot × 100` for puts — positive = OTM):

| Band | Range |
|------|-------|
| `deep-OTM` | > +10% |
| `OTM` | +2% to +10% |
| `ATM` | −2% to +2% |
| `ITM` | −2% to −10% |
| `deep-ITM` | < −10% |

Positive cell value = net new OI (opening trades confirmed). Negative = net OI
decrease (closing/rolling). Only populated DTE/moneyness cells are shown; rows
and columns with all-zero are omitted. The section is absent entirely when no
enriched data is available for the date.

**Signal interpretation:**
- `deep-OTM` / `event` + large positive: speculative opening into near-term catalyst
- `OTM` / `tact`: directional bet, tactical horizon
- `ITM` or `deep-ITM` negative: closing/rolling of existing stock-substitute position
- `strat` + positive across any band: long-horizon positioning (LEAP-style)

---

## Biggest trade

`(premium, type, strike, side, dte)` of the single largest-premium trade for
the ticker — shown verbatim in the rollup for anchor context.

---

## Columns not in the rollup but in the raw trade tables

Raw trade tables (top-N trades per top-N tickers) pass through every column from
the compiled CSV except the drop list. Currently dropped:

- `Price~`, `Expiration Date`, `Bid x Size`, `Ask x Size`, `Trade`, `Time` — noise
- All enriched columns (`oi_d`, `oi_prev`, `oi_change`, `vol_d`, `eod_iv/delta/gamma/vega`, `oi_enriched_on`) — shown only in the aggregated OI section, not per-row

---

## See also

- `config/conviction-score.md` — scoring rubric (how rollup fields map to the 0–12 conviction score)
- `config/barchart-reference.md` — raw column definitions from the Barchart CSV
- `config/analysis-framework.md` — how the LLM uses these columns in its 5-step process
- `references/references_key_insight` — academic references behind the signal design
