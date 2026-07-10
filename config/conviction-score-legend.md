# Conviction score (0–14 raw, less a financing penalty; direction-agnostic)

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
| `OIConfirm` | −2/−1/+1/+2 | **Next-day OI open-confirmation** share (ref-03) — forward-confirmed; 0 when absent/under-sampled (see below) |
| `FinPenalty` | −4/−3/−2/0 | **Financing-dominance demotion** — negative term (see below) |

`flow` ranks **extrinsic premium** (`Ext$` = premium − intrinsic value), not
raw premium — deep-ITM financing/conversion/stock-replacement trades are
~1.0 delta and mostly intrinsic. `otm` ranks `OTM$` = Σ extrinsic ×
(1−|delta|) — monetary size of the bet × risk-neutral probability of
expiring OTM, with |delta| as the P(ITM) proxy. Both are **0 for any name
whose trades carry no `Delta` cell** (absent data is never credited); this is
moneyness, not IV, so IV stays out of the score.

## Financing penalty (the `FinPenalty` column)

The `flow`/`otm` ranks already strip intrinsic, but a name can still rank high
on absolute extrinsic while its premium is **dominated** by |delta| ≥ 0.85
financing/conversion legs — stock-substitute positioning, not a bet on a move.
The `Fin%` column flags this; the score acts on it:

| `Fin%` (FinancingShare) | Penalty |
| ----------------------- | ------- |
| > 0.90 | −4 |
| > 0.75 | −3 |
| > 0.60 | −2 |
| ≤ 0.60 | 0 |

It is **direction-agnostic** (a quality discount, not a bull/bear call) and
the total is clamped to ≥ 0.

## OI open-confirmation (the `OIConfirm` column)

Every other component reads only the trade's own day. `OIConfirm` is the one
**forward-confirmed** term: it reads the strike's **next-session open-interest
change** (ref-03 open-confirmation). `OIConfirmPct` is the share of the
ticker's **moving** contracts that opened — `opens / (opens + closes)` — with
flat contracts (ΔOI == 0) **excluded** from the denominator, since an
unchanged-OI day is ambiguous, not a failed confirmation.

| `OIConfirmPct` | Points |
| -------------- | ------ |
| ≥ 0.60 | +2 |
| ≥ 0.40 | +1 |
| ≥ 0.25 | −1 |
| < 0.25 | −2 |

**Neutral (0) when the data is absent or thin.** Enrichment lags one session,
so the *latest* date a live `analyze` run scores has no next-day OI yet and
every name reads 0 — absence is never a penalty. Names with fewer than 3
moving contracts also score 0, so a single opening print can't earn a full
bonus.

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

These carry a directional read and stay **out** of the direction-agnostic
score (like `Bull`/`Bear`/`C/P`). They feed the framework's Step 5 *Vol
alignment* and the directional thesis:

| Column   | What it measures |
| -------- | ---------------- |
| `IVspr`  | **IV spread** — open-interest-weighted mean of (`IV_call − IV_put`) across **matched pairs** (same strike **and** expiration), on each contract's **settlement IV**. A put-call-parity deviation; positive → bullish, a *positive* predictor of equity returns. `—` when no matched call/put pair exists. |
| `IVskew` | **IV skew** — `IV(OTM put) − IV(ATM call)`, one contract each, on **settlement IV**: the OTM put closest to 0.95 moneyness (`K/S ∈ [0.80, 0.95]`), the ATM call closest to 1.0 (`K/S ∈ [0.95, 1.05]`). Steeper (more positive) → downside demand; *negatively* associated with future returns. `—` when either band is empty. |

⚠️ Thresholds unvalidated — use as Step-5 confirmation, never a standalone
trigger; ignore `—` cells.

## IV percentile (structure selection, not scored, not directional)

`IVpct` is **Barchart's options-overview IV percentile** for the name — the
share of the prior-1-year days whose IV closed below that day's IV. Stored as
a decimal fraction (0.70) per the percentages-as-decimals convention; shown
as a % in the rollup. It is neither a conviction component nor a directional
read — it is the per-ticker **rich/cheap** input that picks the *structure*
once direction is set (framework Step 4). HIGH IVpct (≥70%) → IV rich →
prefer credit / TF-S; LOW IVpct (≤30%) → IV cheap → debit / long premium
(TF). It normalises across names where absolute IV and the market VIX cannot
(40% IV is rich on KO, cheap on NVDA). `—` when the name has no scraped IV
history — then fall back to the dealer-gamma / vol-snapshot proxy.

## Price read (grounds score_price / score_catalyst, not a conviction component)

| Column   | What it measures |
| -------- | ---------------- |
| `PxVec`  | **Signed price-trend vector**, −1..+1: sign is direction (**+** bullish / **−** bearish / **≈0** range-bound) and `|value|` is trend strength. A single collapse of the four non-key price sub-signals `score_price` weights (nearness to the 50d high/low, price-vs-SMA20, SMA20-vs-SMA50, 5d follow-through), renormalised over whichever are present. The **same** value is reused by `score_price` — the rollup read and the score never disagree. `—` when the name has no enriched price history. |
| `Earn`   | **Days to next earnings** as of the trade date (no look-ahead). When the play's `horizon` window spans it, that earnings event grounds `score_catalyst`. `—` when no upcoming earnings date is known. |

Neither is a conviction-score component nor part of the market read: `PxVec`
is the deterministic price signal a trend play's direction should agree with
(a mean-reversion play deliberately opposes it), and `Earn` is the primary
dated catalyst.

## Buckets

| Score | Label       |
| ----- | ----------- |
| 0–2   | ignore      |
| 3–5   | watch       |
| 6–8   | candidate   |
| 9+    | high-conv   |

Single-day **raw** ceiling is 14 (before `FinPenalty`, including a full +2
`OIConfirm`); with `--days N` a recurrence bonus (+1 per repeat day, capped
+3) can push the persistence-adjusted score to 17. `OIConfirm` (−2) and
`FinPenalty` (−4) are the two negative terms, and the total is clamped to
≥ 0 — so a heavily financing-dominated or closing-flow name drops out of
`high-conv` even when its raw flow looks strong.

See the separate **Hedge pressure** section (0–100) for the market-level
hedge read: extrinsic put premium on index/credit/sector hedge ETFs vs total
single-stock extrinsic call premium.
