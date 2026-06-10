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

| Dataset | Primary Use |
|---------|-------------|
| Unusual stocks | Find names and contracts with elevated volume versus open interest |
| Unusual ETFs | Measure broad-market, sector, commodity, credit, and thematic positioning |
| Stocks flow | Find large-premium trades and repeated activity in individual names |
| ETFs flow | Establish breadth, hedging pressure, sector confirmation, and risk appetite |

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

## 3. Score Signal Strength

Codex ranks observations qualitatively using the following evidence. Several
independent confirmations are more important than one extreme number.

### Stronger Evidence

- The same ticker appears in unusual activity and large-premium flow.
- Repeated trades cluster around a ticker, direction, strike area, or expiry.
- A stock signal is confirmed by its sector ETF.
- A market hedge appears across several independent proxies, such as SPY, QQQ,
  IWM, and HYG.
- The trade is marked `BuyToOpen`, `SellToOpen`, or `ToOpen`.
- Volume materially exceeds open interest.
- The strike and delta are plausible for the stated thesis.

### Weaker Or Ambiguous Evidence

- A single isolated contract.
- Very low-delta, short-DTE calls or puts that resemble lottery tickets.
- Trades at the midpoint with no opening label.
- Large premium caused mainly by an expensive underlying.

Keep, but read as positioning rather than a directional bet — ambiguous intent is
not the absence of signal:

- **Deep ITM options** remain a directional input: a deep-ITM call bought is
  bullish exposure (often stock replacement), a deep-ITM put bearish. They are not
  a conviction bet on a move — ~1.0 delta, mostly intrinsic — so strip intrinsic
  value out before premium drives the conviction weight, but do not discard the
  direction.
- **Bid-side calls and ask-side puts** conflate a directional bet, income/hedging,
  and closing, so single-print intent cannot be established. In aggregate they are
  still real positioning — bid-side calls are call-writing pressure, ask-side puts
  are put-buying / hedging demand. Feed them into the regime and the RISK-OFF /
  hedge read, but do not promote either into a stand-alone single-name play.

Do not equate:

- Call activity with bullish intent.
- Put activity with bearish intent.
- Large premium with high conviction.
- High volume/open interest with a new opening position.

When intent is ambiguous, describe the observation as "call activity",
"downside positioning", or "hedging pressure" rather than claiming a purchase.

The prepared rollup now includes a numeric **conviction score** (0–10,
direction-agnostic) that pre-aggregates this evidence — premium rank within the
day, repetition, cross-section overlap, Vol/OI, and opening-label presence — and,
under `--days N`, a **persistence** table across prior days. Rank candidates by the
score, give extra weight to names that stay high across multiple days, and still
apply the benign-explanation checks above before treating any of it as direction.

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

Codex uses confidence implicitly:

- High: repeated, cross-confirmed, and directionally coherent evidence.
- Medium: good evidence with a material counter-signal.
- Low: isolated or ambiguous flow.

Only high- and medium-confidence ideas should become plays. Use calibrated
language such as "suggests", "supports", and "indicates"; avoid presenting flow
interpretation as certainty.

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
conviction IV-robust, and a deferred forward-looking vol layer (IV rank, VIX term
structure). Note: premium already embeds IV, so IV is never multiplied into the
score; and realized vol is for stop-sizing only, never a forward signal.
