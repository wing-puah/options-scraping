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

## Financing penalty (the `FinPenalty` column)

The `flow`/`otm` ranks already strip intrinsic, but a name can still rank high on
absolute extrinsic while its premium is **dominated** by |delta| ≥ 0.85
financing/conversion legs — stock-substitute positioning, not a bet on a move.
The `Fin%` column flagged this advisorily; the score now acts on it:

| `Fin%` (FinancingShare) | Penalty |
| ----------------------- | ------- |
| > 0.90 | −4 |
| > 0.75 | −3 |
| > 0.60 | −2 |
| ≤ 0.60 | 0 |

It is **direction-agnostic** (a quality discount, not a bull/bear call) and the
total is clamped to ≥ 0. The 0.60 floor came from the Mar-2025 panic backtest:
names with `Fin%` > 0.6 won **33%** (avg **−28%**) vs **86%** (avg **+57%**)
below it, while borderline real bets (GLD at 0.53) were left untouched. A bear
play is **doubly** suspect when high `Fin%` coincides with a deeply negative
`IVspr` (panic put-IV inflation) — see the directional vol note below.

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

## OI open-confirmation (the `OIConfirm` column)

Every other component reads only the trade's own day. `OIConfirm` is the one
**forward-confirmed** term: it reads the strike's **next-session open-interest
change** (ref-03 open-confirmation, produced by `enrich_oi.py`). `OIConfirmPct`
is the share of the ticker's **moving** contracts that opened —
`opens / (opens + closes)` — with flat contracts (ΔOI == 0) **excluded** from the
denominator, since an unchanged-OI day is ambiguous, not a failed confirmation.
`OIN` is the moving-contract sample behind that percentage.

| `OIConfirmPct` | Points |
| -------------- | ------ |
| ≥ 0.60 | +2 |
| ≥ 0.40 | +1 |
| ≥ 0.25 | −1 |
| < 0.25 | −2 |

**Neutral (0) when the data is absent or thin.** The enrichment lags one
session, so the *latest* date a live `analyze` run scores has no next-day OI yet
and every name reads 0 here — absence is never a penalty. Names with fewer than
`_OI_CONFIRM_MIN_N` (3) moving contracts also score 0, so a single opening print
can't earn a full bonus. Backfilled / backtested dates carry it in full. The
−1/−2 penalty encodes the backtest finding that `OIConfirm < 40%` names
underperform (their premium was closing/rolling flow, not new positioning). The
bands are tunable — retune from the attribution backtest. ⚠️ A 2026-07-08
check on the 116-row next-open-basis `backtests/results.csv` window found
`OIConfirmPct` ≈ **uncorrelated** with realized P&L (r ≈ −0.03, vs the +0.40 on
the original Mar-2025 n=20 that set these bands) — retune before trusting the
±2/±1 points as anything more than a placeholder.

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

Both are built faithfully to the paper's appendix (A.1/A.2), after
Cremers & Weinbaum (2010) and Xing, Zhang & Zhao (2010), including the
appendix data filters on every leg (traded or backfilled): the **10–60 DTE**
window, IV within **[3, 200] points**, **positive open interest**, underlying
**≥ $5**, and option price **≥ $0.125** (trade print / counterpart mark as the
quote-mid proxy; unknown price never drops a leg). The paper's stock-volume /
option-volume-not-missing filters are not observable in this data source:

| Column   | What it measures |
| -------- | ---------------- |
| `IVspr`  | **IV spread** — the open-interest-weighted mean of (`IV_call − IV_put`) across **matched pairs** (same strike **and** expiration), on each contract's **settlement IV**. A put-call-parity deviation; positive → bullish, a *positive* predictor of equity returns. `—` when no matched call/put pair exists. |
| `IVskew` | **IV skew** — `IV(OTM put) − IV(ATM call)`, one contract each, on **settlement IV**: the OTM put with moneyness `K/S ∈ [0.80, 0.95]` closest to 0.95, and the ATM call with `K/S ∈ [0.95, 1.05]` closest to 1.0. Steeper (more positive) → downside demand; *negatively* associated with future returns. `—` when either band is empty. |

**Validity concern — flow subset vs. full chain (backfilled).** Lin/Lu/Driessen
compute both measures across the *entire daily option chain*. The traded flow
(Barchart's ~100 largest trades/symbol) rarely carries both legs of a matched
pair, so on flow alone `IVspr` is ~98% empty. The missing counterpart legs are
therefore **backfilled** from Barchart per-contract price-history — the
settlement IV as of the trade date D (`scripts/collector/fetch_counterpart_iv.py` → per-date sidecar
→ `lib/counterpart_iv.build_iv_lookup` → the rollup), which lifts matched-pair
coverage materially. It remains a *reconstruction* of the paper's chain-level
statistic, not the validated statistic itself, and where no sidecar exists it
falls back to flow-only. **Predictive power on the reconstructed signal is
unverified** — backtest before trusting either directionally.

**Directional gate (Step-5 use, not auto-applied to the score):** in the
Mar-2025 backtest, `IVspr` was the single best directional confirmation —
positive/mildly-negative spreads won; **extreme** negative spreads lost. A BEAR
play whose `IVspr` is deeply negative is buying puts whose IV is massively
inflated by panic hedging (overpriced crash insurance that mean-reverts).
⚠️ **STALE:** the specific **≈ −25** threshold (and the example plays) were
derived from the *old* unmatched, premium-weighted, all-DTE spread definition.
The matched-pair OI-weighted spread above has a different distribution — and
the paper data filters added 2026-07-02 (IV bounds, positive OI, $5 underlying,
min price) shift it again — so the threshold must be **re-derived** from a
fresh backtest before use. This is
*direction-bearing*, so it deliberately stays out of the agnostic score — treat
it as a veto on the play, not a deduction on the name.

## IV percentile (structure selection, not scored, not directional)

`IVpct` is **Barchart's options-overview IV percentile** for the name — the share
of the prior-1-year days whose IV closed below that day's IV. It is scraped per
historical date from Barchart (`scripts/collector/fetch_iv_percentile.py` →
`lib/barchart/iv_history.py` → appended as `iv`/`iv_rank`/`iv_pct` columns onto the
compiled flow file, enrich-in-place like OI) and read back as-of the trade date off
those rows, so no percentile is computed on our side. Stored as a decimal fraction
(0.70) per the percentages-as-decimals convention; shown as a % in the rollup. It is neither a conviction
component nor a directional read — it is the per-ticker **rich/cheap** input that
picks the *structure* once direction is set (framework Step 4). HIGH IVpct (≥70%) →
IV rich → prefer credit / TF-S; LOW IVpct (≤30%) → IV cheap → debit / long premium
(TF). It normalises across names where absolute IV and the market VIX cannot (40%
IV is rich on KO, cheap on NVDA). `—` when the tab has no scraped row for the name
(not yet cached, or the ticker fell outside the scraped universe) — then fall back
to the dealer-gamma / vol-snapshot proxy.

## Price read (grounds score_price / score_catalyst, not a conviction component)

Two deterministic per-ticker columns precompute what the framework's Step-5
price and catalyst factors need, so the model's `direction`/`key_level` are
anchored in the actual chart/calendar rather than its own recall:

| Column   | What it measures |
| -------- | ---------------- |
| `PxVec`  | **Signed price-trend vector**, −1..+1: sign is direction (**+** bullish / **−** bearish / **≈0** range-bound) and `|value|` is trend strength. A single collapse of the four non-key price sub-signals `score_price` weights (nearness to the 50d high/low, price-vs-SMA20, SMA20-vs-SMA50, 5d follow-through), renormalised over whichever are present. The **same** value is reused by `score_price` — the rollup read and the score never disagree. `—` when the name has no enriched price history. |
| `Earn`   | **Days to next earnings** as of the trade date (from the Barchart corporate-actions feed, no look-ahead). When the play's `horizon` window spans it, that earnings event grounds `score_catalyst`. `—` when no upcoming earnings date is known. |

Both come from `scripts/collector/fetch_price_catalyst.py` (Barchart underlying
price history + corporate actions → `lib/price_catalyst.py` pickers → columns on
the compiled flow file), read back as-of the trade date — same enrich-in-place /
read-off-the-row pattern as `IVpct`. Neither is a conviction-score component nor
part of the market read: `PxVec` is the deterministic price signal a trend
play's direction should agree with (a mean-reversion play deliberately opposes
it), and `Earn` is the primary dated catalyst. Both also land on the
`AnalysisClaude`/`AnalysisGPT`/`AnalysisTickerSpecific` rows as the snake_case
`price_vector`/`days_to_earnings` columns, joined onto each play row by ticker at
row-expansion time (same mechanism as `oi_confirm_pct`/`iv_pct`).

## Buckets

| Score | Label       |
| ----- | ----------- |
| 0–2   | ignore      |
| 3–5   | watch       |
| 6–8   | candidate   |
| 9+    | high-conv   |

`Score`/`ScoreLabel` also land on the `AnalysisClaude`/`AnalysisGPT`/
`AnalysisTickerSpecific` sheet rows, as `ConvictionScore`/`ConvictionScoreLabel`
columns (previously only in the audit CSV) — joined onto each play row by
ticker at row-expansion time, the same mechanism already used for
`oi_confirm_pct`/`cpir`/`iv_spread`/`iv_pct`.

Single-day **raw** ceiling is 14 (before `FinPenalty`, including a full +2
`OIConfirm`); with `--days N` a recurrence bonus (+1 per repeat day, capped +3)
can push the persistence-adjusted score to 17. `OIConfirm` (−2) and `FinPenalty`
(−4) are the two negative terms, and the total is clamped to ≥ 0 — so a heavily
financing-dominated or closing-flow name drops out of `high-conv` even when its
raw flow looks strong.

A separate **Hedge pressure** section (0–100) precomputes the market-level
hedge read: extrinsic put premium on index/credit/sector hedge ETFs vs total
single-stock extrinsic call premium. Use it as the starting point for the
hedge-pressure vs bear-regime distinction instead of re-deriving it from raw
ratios each day.
