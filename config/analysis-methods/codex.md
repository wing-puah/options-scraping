This file has drifted. it needs to to be regenerated.

# Codex Options Analysis Method

This document explains how Codex turns the four Barchart datasets into the
market regime and ticker plays required by `config/analysis-framework.md`.

It is a repeatable decision method, not a claim that a single options trade
reveals the buyer's intent. Options flow is treated as positioning evidence,
then strengthened or weakened through confirmation.

## 1. Validate The Input

For each requested date:

1. Confirm that at least one of the four sections contains data.
2. Note which sections are missing before drawing conclusions.
3. Treat each date independently in range mode.
4. Use the later dates to describe a regime transition only after each day's
   standalone analysis is complete.

The four inputs have different roles:

| Dataset        | Primary Use                                                                 |
| -------------- | --------------------------------------------------------------------------- |
| Unusual stocks | Find names and contracts with elevated volume versus open interest          |
| Unusual ETFs   | Measure broad-market, sector, commodity, credit, and thematic positioning   |
| Stocks flow    | Find large-premium trades and repeated activity in individual names         |
| ETFs flow      | Establish breadth, hedging pressure, sector confirmation, and risk appetite |

## 2. Build The Market Read First

Start with ETFs before selecting individual tickers. The market regime should
not be inferred from one popular stock.

Review evidence in this order:

1. Broad indexes: SPY, QQQ, IWM, DIA, and RSP.
2. Sector and thematic ETFs: SMH, SOXX, IGV, XLE, XOP, and similar products.
3. Risk and defensive proxies: HYG, TLT, GLD, SLV, and volatility products.
4. Speculative-risk proxies: IBIT, BITO, leveraged ETFs, and high-beta themes.

Classify the four regime dimensions:

- Direction: compare upside participation with downside protection. Mixed,
  two-sided positioning normally maps to `RANGE`.
- Volatility: repeated hedges, high IV, short DTE activity, and opposing large
  flows normally map to `E-VOL` or `H-VOL`.
- Macro: infer only when cross-asset evidence is present. Do not invent a macro
  catalyst from options flow alone.
- Sentiment: broad upside participation supports `RISK-ON`; protection across
  indexes, credit, small caps, and speculative assets supports `RISK-OFF`.

When the prepared data includes a **Baseline context** section, normalize the
market read against it. Index put premium exceeding call premium is the
everyday norm, so raw put dominance is not evidence by itself:

- Cite percentiles, not raw ratios, when an aggregate motivates a regime
  dimension or market-level signal (e.g. "SPY C/P at the 12th percentile of
  the trailing window").
- Use strong labels (`RISK-OFF`, `RISK-ON`, `E-VOL`) only when readings sit in
  roughly the outer quintile of the window or several related metrics agree;
  mid-range percentiles favor `RANGE` / neutral.
- Scale trust in the percentiles with the window size the section reports.
  Below roughly 40 prior sessions a percentile moves several points per single
  day, so require a more extreme reading (about ≤10th / ≥90th) or agreement
  from a second related metric before a small-window percentile carries a
  strong label on its own.
- If the section reports insufficient history, state that the read is
  unnormalized and do not present put/call dominance as unusual.

## 3. Score Signal Strength

Codex ranks observations qualitatively using the following evidence. Several
independent confirmations are more important than one extreme number.

### Stronger Evidence

- The same ticker appears in unusual activity and large-premium flow.
- Repeated trades cluster around a ticker, direction, strike area, or expiry.
- A stock signal is confirmed by its sector ETF.
- A market hedge appears across several independent proxies, such as SPY, QQQ,
  IWM, and HYG.
- The trade is marked `BuyToOpen`, `SellToOpen`, or `ToOpen`. The directional
  labels carry side; bare `ToOpen` does not — it establishes only that a
  position is new (a market maker selling and a fund buying print it
  identically), so treat bare `ToOpen` as supporting evidence for new
  positioning, never as evidence of a buyer or a direction on its own.
- Volume materially exceeds open interest.
- The strike and delta are plausible for the stated thesis.

### Weaker Or Ambiguous Evidence

- A single isolated contract.
- Very low-delta, short-DTE calls or puts that resemble lottery tickets.
- Trades at the midpoint with no opening label.
- Large premium caused mainly by an expensive underlying.
- A strike implausibly far from spot for the contract's DTE (for example, more
  than 50% away with under 60 DTE). Usually a feed artifact — adjusted options
  after a split, a stale strike, or a different underlying parsed into the row.
  Flag as a data anomaly and exclude from the regime read until the strike is
  verified against the current chain. A `ToOpen` label at an impossible strike
  does not redeem the print.

Keep, but read as positioning rather than a directional bet — ambiguous intent is
not the absence of signal:

- **Deep ITM options** are a weak directional input: a deep-ITM call bought can
  be stock replacement (bullish exposure), but deep-ITM strikes are also the
  standard leg of conversions/reversals, collars, buy-writes, and financing
  trades — non-directional by construction and indistinguishable in a single
  row. Keep the direction as a low-weight prior, promoted only with
  corroboration elsewhere in the same name. They are never a conviction bet on
  a move — ~1.0 delta, mostly intrinsic — so strip intrinsic value out before
  premium drives the conviction weight. The rollup precomputes this: `Ext$` is
  the intrinsic-stripped (extrinsic) premium, `Fin%` the share of premium from
  |delta| ≥ 0.85 stock-substitute trades, `ΔNot$` the signed delta-adjusted
  notional, and `Hzn` the dominant DTE bucket — read conviction off `Ext$`,
  pollution off `Fin%`, deep-ITM size off `ΔNot$` rather than raw premium.
- **Bid-side calls and ask-side puts** conflate a directional bet, income/hedging,
  and closing, so single-print intent cannot be established. In aggregate they are
  still real positioning — bid-side calls are call-writing pressure, ask-side puts
  are put-buying / hedging demand. Feed them into the regime and the RISK-OFF /
  hedge read, but do not promote either into a stand-alone single-name play.
- **Structurally polluted underlyings.** Some names have non-directional option
  flow embedded in their structure: convertible-bond hedging (e.g. MSTR, where
  dealers short calls and buy puts to hedge the convert), systematic overwriting
  (BDCs, covered-call ETFs), structured-product underlyings, miners traded as
  crypto proxies, and levered or inverse ETFs. Raw put/call balance on these
  tickers is poor evidence of direction — large MSTR put flow may be convert
  mechanics, not bearish conviction. Require cross-asset confirmation before any
  single-name flow on these tickers becomes a directional play: for MSTR, BTC /
  IBIT / COIN / miners; for a miner, the underlying commodity or crypto; for a
  levered ETF, the underlying index. Without confirmation, treat the flow as
  positioning noise rather than a `[FLOW]` signal.

Do not equate:

- Call activity with bullish intent.
- Put activity with bearish intent.
- Large premium with high conviction.
- High volume/open interest with a new opening position.

When intent is ambiguous, describe the observation as "call activity",
"downside positioning", or "hedging pressure" rather than claiming a purchase.

The prepared rollup now includes a numeric **conviction score** (0–10,
direction-agnostic) that pre-aggregates this evidence — **extrinsic-premium**
rank within the day (intrinsic stripped, so financing flow cannot buy rank),
repetition, cross-section overlap, Vol/OI, and opening-label presence — and,
under `--days N`, a **persistence** table across prior days with a
**Persistent names (≥3 days)** callout. Rank candidates by the score, give
extra weight to names that stay high across multiple days, and still apply the
benign-explanation checks above before treating any of it as direction.

## 4. Resolve Conflicting Flow

Mixed flow is useful information rather than noise.

Apply these rules:

1. Prefer breadth over a single ticker.
2. Prefer repeated flow over an isolated print.
3. Prefer cross-dataset and sector confirmation over raw premium size.
4. Treat strong upside flow plus broad downside hedging as hedge pressure (`HP`),
   not as an uncomplicated bullish regime.
5. Treat a later increase in broad protection as a shift toward `RISK-OFF`,
   even when selected stocks still show bullish activity.

The prepared markdown's **Hedge pressure** section precomputes rule 4 as a
0–100 score (extrinsic ETF put demand vs single-stock extrinsic call demand)
with its inputs itemized. Start from that number and its baseline percentile
context rather than re-deriving the hedge read from raw ratios.

The regime sentence must state both the dominant signal and the important
counter-signal.

## 5. Narrow To Tickers

Select two to four plays per date. A ticker normally needs at least two of:

- Repeated or large-premium stock flow.
- Unusual volume/open-interest activity.
- Confirmation from its sector ETF.
- A clear nearby trigger level derived from current price or clustered strikes.
- A structure that fits the market and volatility regime.

Avoid filling the play list merely because a ticker appears in the data.
Separate directional plays from portfolio hedges.

## 6. Select Structure, Trigger, And Invalidation

Choose defined-risk structures by default because the dataset does not include
the user's portfolio size, risk tolerance, or complete volatility surface.

### Structure Rules

- Bullish flow with elevated IV: prefer a bull call spread over a naked call.
- Bearish flow or hedge pressure with elevated IV: prefer a bear put spread.
- Clear volatility expansion without directional agreement: consider a
  long-volatility structure only when both sides have meaningful evidence.
- Use short-volatility structures only when compression evidence is explicit.
- Let the per-ticker `IVpct` column (Barchart's IV percentile — share of the
  prior-1yr days with IV below today's, 0–100) pick debit vs credit once direction
  is set — it normalises across names where the market VIX cannot. **High `IVpct`
  (≥70%)** on a trend name in a slow, positive-gamma grind is the **TF-S** case:
  sell a credit spread (bull put / bear call) rather than buy a debit into rich IV.
  **Low `IVpct` (≤30%)** → debit / long premium (TF). Blank (no scraped row) → fall
  back to the vol-snapshot proxy.
- Default the structure's expiry to **≥45 DTE** (framework Step 4 DTE
  discipline — backtested short-dated structures were worse signals, not just
  worse exits). Go shorter only for an explicit dated catalyst inside the
  window, named in the play.

### Trigger Rules

Triggers should require confirmation after the analysis:

- Bullish: hold a nearby support level, then reclaim or break a relevant strike.
- Bearish: reject resistance, then break a nearby support level.
- Hedge: enter only after the protected index or sector loses the stated level.

### Invalidation Rules

Every play needs a condition that proves the thesis wrong:

- A daily close beyond a specific price level.
- A reversal in the flow pattern.
- Loss of sector confirmation.
- A macro or volatility condition that contradicts the setup.

Trigger and invalidation levels are approximate when only the Barchart snapshot
is available. They should be validated against a current price chart before a
trade is placed.

## 6b. Per-Play Regime And Signal Vs Market Regime And Signal

The output schema carries **two** regime fields and **two** signal fields, with
different roles. Treat them as independent — do not mirror the market read into
a play's fields.

Market-level (top-level fields, written to the MARKET row):

- `regime` — the regime of the tape: direction + volatility + sentiment (+ macro
  when corroborated) for the whole market.
- `signals` — cross-asset and macro patterns (broad index hedging, vol regime,
  sector rotation, credit divergence). Global to the run.

Ticker-level (inside each play, written to that play's row):

- `regime` — the volatility / level / posture state for THIS name, e.g.
  `BULL + E-VOL — testing 59 breakout, IV30 rising into earnings`, or
  `RANGE + L-VOL — pinned at 200, OPEX gravity`. It is the ticker's own setup,
  not the tape's. Leave empty when there is nothing ticker-specific to add — do
  not copy the market regime into this field.
- `signal` — the ticker-specific evidence chain for the play, pipe-separated
  and tagged with the framework vocabulary
  (`[FLOW]/[PRICE]/[MACRO]/[VEGA]/[CAT]`).

A per-play `signal` should cite the concrete prints that survived Section 3
for that ticker — premium balance, Vol/OI, opening labels, sweep codes,
strike/DTE coherence, sector confirmation, nearby price levels. Examples:

- `[FLOW] $10.3M calls vs $0.9M puts | [FLOW] 53x Vol/OI ToOpen $64 calls | [PRICE] testing breakout at 59`
- `[FLOW] ask-side put sweeps across SPY/QQQ/IWM, BuyToOpen labels | [VEGA] VIX call buying 35-40 | [MACRO] credit (HYG) diverging from equity highs`

Rules:

- Do not copy the market `regime` into a play's `regime`, and do not copy the
  market `signals` into a play's `signal`.
- A play's `regime` may be empty. A play's `signal` may not — if a ticker lacks
  enough ticker-specific evidence to populate the signal, the ticker does not
  qualify as a play.

## 7. Confidence And Language

Confidence is emitted numerically, not as a label: a `score` object of three
integer component points, `{ flow, dealer, vol }` (Step 5 rubric), plus two
REQUIRED sibling fields — `key_level` (the specific price threshold the
play's own `structure`/`invalidation`/`trigger` already implies) and
`direction` (`bullish|bearish|neutral`). The other two Step-5 factors, `price`
and `catalyst`, are no longer model-emitted — the pipeline computes them from
fetched price-history and earnings-date data, grounded by `key_level`/
`direction` instead of model recall (`lib/price_catalyst.py`). Emit the three
components plus `key_level`/`direction` only — never a total; the pipeline
sums all five into `score_total` (0–100). Bands are interpretation of that
total, not an output:

- Strong (≥70): repeated, cross-confirmed, and directionally coherent evidence.
- Moderate (40–69): good evidence with a material counter-signal.
- Weak (<40): isolated or ambiguous flow.

Only strong- and moderate-scoring ideas should become plays. Use calibrated
language such as "suggests", "supports", and "indicates"; avoid presenting flow
interpretation as certainty.

Every play also declares `flow_intent` (one of `DIRECTIONAL` / `VOLATILITY` /
`HEDGE` / `SYNTHETIC STOCK`) and `horizon` (one of `14|60|180|720` — the DTE
bucket boundary of the dominant expiry in the cited evidence; the rollup's `Hzn`
column is the per-ticker cross-check), each emitted as its own column beside
`play` — `horizon` is no longer folded into the bracket line, which now carries
only `flow_intent`. `flow_intent` is a **classification, not a confidence cap**
(framework Step 3): `DIRECTIONAL` = a bet price moves a way (playbook
TF/MR/GE/PU); `VOLATILITY` = a bet on the size of the move / implied vol,
direction-agnostic (playbook VC/DP); `HEDGE` = protection on an existing book,
framed as protection not a forecast; `SYNTHETIC STOCK` = mechanical deep-ITM
exposure, strip intrinsic and treat as a soft tell. All four are valid plays
and each carries its own score — score on evidence quality (Step 5 rubric),
weighted by intent (Price-heavy for `DIRECTIONAL`, Vol-heavy for `VOLATILITY`),
independent of `flow_intent`. `DIRECTIONAL` vs `VOLATILITY` follows the
playbook + structure; the opening-view-vs-`HEDGE` line turns on whether an
offsetting position is protected. Bid-side calls / ask-side puts without a `ToOpen` label
read as `HEDGE` or `SYNTHETIC STOCK` until evidence shows new risk opened.
`horizon: 14` evidence cannot carry a multi-week directional thesis.

Also emit market-level `themes`: `[{ theme, tickers, breadth, read }]`. `breadth`
counts **independent** names — correlated agreement (e.g. NVDA/AMD/SMH all
expressing one AI-semis trade) is breadth, never corroboration, and never a
multiplier on any play's `score`.

## 8. June 2-3, 2026 Example

### June 2

- Semiconductor calls appeared across individual names and sector products.
- SPY, QQQ, IWM, HYG, and IBIT downside positioning showed protection beneath
  that upside participation.
- Result: `RANGE + E-VOL + EXP + RISK-ON`, with the rally described as fragile.
- Selected plays combined semiconductor upside setups with a QQQ hedge.

### June 3

- Selected technology names still attracted upside activity.
- Repeated SMH/SOXX puts plus broader index, credit, small-cap, and crypto
  protection strengthened the defensive signal.
- Result: `RANGE + E-VOL + EXP + RISK-OFF`.
- Selected plays included an SMH hedge, a selectively bullish GOOGL setup, and
  an IBIT downside setup.

The shift from `RISK-ON` to `RISK-OFF` came from broader and more repeated
protection, not from the disappearance of all bullish trades.

## 9. Known Limitations

- The prepared input contains all parsed rows per section by default, but is
  still a snapshot rather than a full statistical summary of the trading day; if
  the run is explicitly capped with `--rows N` it falls back to only the last N
  rows per section.
- Trade direction and opening/closing intent are often unavailable.
- Multi-leg spreads may appear as unrelated individual contracts.
- The snapshot does not include price charts, realized volatility, news, or a
  complete volatility surface.
- Regime and macro labels are therefore hypotheses based on available flow, not
  complete market diagnoses.

Per-ticker aggregation, call/put balance, repeated-print clustering, a
direction-agnostic conviction score, and multi-day persistence are now computed
before this step. Remaining work and the rationale behind current choices live in
`config/analysis-roadmap.md` — chiefly a size/contracts aggregate to make
conviction IV-robust. Per-name **IV percentile now ships** as the `IVpct` column
(scraped from Barchart's options-overview history); market-wide VIX term structure
ships in the Vol regime snapshot. Note: premium already embeds IV, so IV is never
multiplied into the score; and realized vol is for stop-sizing only, never a
forward signal.
