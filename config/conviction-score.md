# Conviction score (0–12, direction-agnostic)

A quant pre-score of how much attention a name warrants, built from normalized
inputs only — so an expensive underlying cannot buy its way up the list with raw
premium. It is **not** a direction call; bull/bear tilt stays in the
`Bull`/`Bear`/`C-P` columns.

## Components

| Part      | Range | What it measures |
| --------- | ----- | ---------------- |
| `flow`    | 0–3   | **Extrinsic-premium** rank within the day, **guarded by contract size** (`min(ext_rank, size_rank + 1)`) |
| `rep`     | 0–2   | Trade repetition — number of trades clustering on the name |
| `cross`   | 0/2   | Also appears in the unusual-activity dataset (cross-section overlap) |
| `voloi`   | 0–2   | Strength of the name's unusual Vol/OI print, if any |
| `otm`     | 0–2   | **OTM-probability-weighted extrinsic** rank within the day (`OTM$` column) — informed-OTM tell |
| `open`    | 0/1   | ≥1 BuyToOpen / SellToOpen / ToOpen label present |
| `persist` | 0–3   | Extra days the name recurs across the window (multi-day, `--days N` only) |

The `flow` component ranks **extrinsic premium** (`Ext$` = premium − intrinsic
value), not raw premium: deep-ITM financing/conversion/stock-replacement trades
are ~1.0 delta and mostly intrinsic — stock exposure, not a bet on a move — so
raw premium let them pose as conviction. A trade missing `Price~`/`Strike` is
never discounted (extrinsic falls back to full premium). Size can only *cap*
the rank, never lift it; absent the `Size` column the cap never binds.

The `otm` component ranks `OTM$` = Σ extrinsic × (1−|delta|) — the
informed-trading measure of Hilliard et al. (2025), *monetary size of the bet ×
risk-neutral probability of expiring OTM*, with |delta| as the P(ITM) proxy. It
rewards economically-sized flow concentrated in **out-of-the-money** contracts
(the leveraged informed bet) on top of the plain extrinsic rank, and is **0 for
any name whose trades carry no `Delta` cell** (absent data is never credited).
This is moneyness/probability, not IV, so it keeps IV out of the score; the
paper's IV-augmented variant (×IV) is deliberately not enabled.

## Pollution / exposure columns

| Column  | What it measures |
| ------- | ---------------- |
| `Ext$`  | Total extrinsic (time-value) premium — the "real options bet" share of `Total$`. Big `Total$` with small `Ext$` = financing/stock-substitute flow (deep-ITM puts on GLD/BABA-style names). |
| `Fin%`  | Share of premium from \|delta\| ≥ 0.85 trades — the stock-substitute fraction of the headline number. High `Fin%` = read the name as positioning/financing, not conviction. |
| `ΔNot$` | Signed delta-adjusted notional (Σ delta × contracts × 100 × spot) — share-equivalent dollar exposure; the conviction-size axis for deep-ITM flow. |
| `Hzn`   | Dominant DTE bucket by extrinsic premium: `event` 0–14, `tact` 15–60, `med` 60–180, `strat` 180+ (e.g. `tact 64%`). An `event`-dominated name is gamma/event flow — it can decay to nothing by tomorrow. |
| `OTM$`  | OTM-probability-weighted extrinsic premium (Σ extrinsic × (1−\|delta\|)) — the input to the `otm` score component. High `OTM$` relative to `Ext$` = bet concentrated in OTM contracts. |

The `Ctts` (contracts) and `$/ct` (premium per contract) columns expose
vol-/price-inflation: big premium + few contracts + high `$/ct` = expensive
options, not real size. A missing opening label scores 0, never negative.

## Directional vol columns (not scored)

These carry a directional read and stay **out** of the direction-agnostic score
(like `Bull`/`Bear`/`C/P`). They feed the framework's Step 5 *Vol alignment* and
the directional thesis, per Lin, Lu & Driessen (2013):

| Column   | What it measures |
| -------- | ---------------- |
| `IVspr`  | Premium-weighted **call IV − put IV** (IV spread). Positive → bullish information; a *positive* predictor of equity returns. `—` when one side has no premium. |
| `IVskew` | Premium-weighted **OTM-put IV − ATM-call IV** (\|delta\| ≤ 0.40 puts vs 0.40–0.60 calls). Steeper (more positive) → downside demand; *negatively* associated with future returns. `—` when either band is empty. |

## Buckets

| Score | Label       |
| ----- | ----------- |
| 0–2   | ignore      |
| 3–5   | watch       |
| 6–8   | candidate   |
| 9+    | high-conv   |

Single-day ceiling is 12; with `--days N` a recurrence bonus (+1 per repeat day,
capped +3) can push the persistence-adjusted score to 15.

A separate **Hedge pressure** section (0–100) precomputes the market-level
hedge read: extrinsic put premium on index/credit/sector hedge ETFs vs total
single-stock extrinsic call premium. Use it as the starting point for the
hedge-pressure vs bear-regime distinction instead of re-deriving it from raw
ratios each day.
