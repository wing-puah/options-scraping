# Analysis Framework

This is the vocabulary and structure used for all LLM analysis of options flow data.
Use these labels consistently.

---

## Step 1 — Regime Identification

Classify the current market. **Directional, Volatility, and Sentiment are required** —
they are readable from options flow. **Macroeconomic is optional**: assign a macro
label only when cross-asset evidence _outside this dataset_ corroborates it (rates,
CPI/employment prints, gold, credit spreads moving together). Equity options flow
alone does not establish a macro regime — omit the macro label rather than guessing.

Combine the labels you can support, e.g. "BEAR + H-VOL + RISK-OFF" (no macro claim),
or "RANGE + H-VOL + RECS + RISK-OFF" only when the macro leg is corroborated.

### Directional

| Label | Meaning                                                            |
| ----- | ------------------------------------------------------------------ |
| BULL  | Rising prices, higher highs, strong earnings/economic expansion    |
| BEAR  | Sustained decline (≥20% from highs), fear and pessimism dominant   |
| RANGE | Oscillating between support/resistance, no clear catalyst or trend |

### Volatility

| Label | Meaning                                                           |
| ----- | ----------------------------------------------------------------- |
| L-VOL | Low IV, steady predictable moves — "Goldilocks"                   |
| H-VOL | High IV, large erratic swings, crisis or regime shift             |
| C-VOL | Volatility compressing — stabilising after a spike                |
| E-VOL | Volatility expanding — new risks or catalysts increasing movement |

### Macroeconomic — optional, only with cross-asset corroboration

| Label | Meaning                                                                                  |
| ----- | ---------------------------------------------------------------------------------------- |
| EXP   | Expansionary — high growth, low inflation, ideal for equities                            |
| INFL  | Inflationary/Reflationary — rising prices, recovery, commodities/value outperform        |
| STAG  | Stagflation — stagnant growth + high inflation, hardest regime for both stocks and bonds |
| RECS  | Recessionary — negative growth, falling demand, safe havens (GLD, Treasuries) in demand  |

### Sentiment

| Label    | Meaning                                                                       |
| -------- | ----------------------------------------------------------------------------- |
| RISK-ON  | Investors buying risky assets (Tech, Crypto, Small Caps), selling safe assets |
| RISK-OFF | Investors fleeing to defensive sectors (Utilities, Staples) or Cash           |

### Market-condition qualifier — optional

| Label | Meaning                                                                              |
| ----- | ------------------------------------------------------------------------------------ |
| HP    | Hedge pressure — index/sector at/near highs while large downside hedging accumulates |

HP describes the whole tape (institutions keeping longs but buying broad protection), not
a single name's setup. Append it to the regime read — e.g. "BULL + C-VOL + RISK-OFF + HP" —
when index/ETF put hedging dominates the day's premium. It colours every play's context
but is never itself a per-play setup label.

---

## Step 2 — Signal Identification

Tag each observation with the signal type that generated it.

### Signal Types

| Tag     | Meaning                                                             | Example                               |
| ------- | ------------------------------------------------------------------- | ------------------------------------- |
| [FLOW]  | Options flow — unusual activity, put/call ratio, sweeps, blocks     | Put sweeps on QQQ while index rallied |
| [PRICE] | Technical price structure — support, resistance, breakout, range    | NVDA testing 180 key support          |
| [MACRO] | Geopolitical or economic events                                     | Fed hold, CPI print, war escalation   |
| [VEGA]  | Implied volatility behaviour — VIX spikes, IV expansion/compression | VIX call buying at 35–40              |
| [CAT]   | Corporate catalyst — earnings, guidance, product launch             | NVDA earnings in 2 weeks              |

### Setup Patterns

A setup is the named situation a single ticker is in. **Each setup fixes a directional
bias and the structures it may use.** A play's structure must be drawn from its setup's
allowed list, and its direction must match the setup's bias — see the binding rule in
Step 4. The entry trigger that activates a setup comes from the Trigger Conditions table
below.

Allowed structures are listed **debit (buy premium) · credit (sell premium)**. Direction
picks the setup; **IV picks the side** — buy premium when IV is low or expected to rise,
sell premium when IV is high or expected to fall.

| Setup                     | Arises when                                                | Bias            | Allowed structures (debit · credit)                  |
| ------------------------- | ---------------------------------------------------------- | --------------- | ---------------------------------------------------- |
| BO (Breakout)             | BULL — price breaks resistance with follow-through         | Bullish         | long call, bull call spread · short put, bull put spread |
| PB (Pullback buy)         | BULL — shallow dip to support inside an uptrend            | Bullish         | long call, bull call spread · short put, bull put spread |
| RF (Resistance fade)      | RANGE/BULL — price approaches resistance, momentum fading  | Bearish         | long put, bear put spread · short call, bear call spread |
| DC (Dead cat bounce)      | BEAR — sharp selloff then weak rebound                     | Bearish         | long put, bear put spread · short call, bear call spread |
| VE (Volatility expansion) | E-VOL — macro/event uncertainty, IV rising                 | Non-directional | long straddle/strangle, backspread, long convexity   |
| SH (Safe haven flow)      | RISK-OFF — risk event + safe-haven demand (GLD, TLT)       | Long-haven      | calls on GLD/TLT, defensive / long-convexity hedges  |
| MS (Macro shock)          | Sudden macro event + volatility spike                      | Non-directional | long convexity, OTM put/call, VIX calls              |

"Fade, don't chase" (RF / DC) is **always a bearish structure** — short put and bull call
spread are bullish and must never appear under RF/DC. A bullish breakout or continuation is
BO or PB, not RF. Naked shorts (short put / short call) carry undefined risk and assignment
exposure — prefer the defined-risk spread on high-IV names.

### Trigger Conditions

| Trigger               | Conditions                                                                | Interpretation                                                      |
| --------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Price extension       | Intraday move ≈ 2× expected move or 1.5–2× recent daily ATR               | Price may be extended — reversal or consolidation probability rises |
| Reversal signal       | Rapid reversal + strong candle at support/resistance, elevated IV         | Selling momentum exhausting; short-term bounce likely               |
| IV spike              | VIX or underlying IV rises sharply in short time                          | Greater uncertainty being priced; option premiums elevated          |
| IV compression        | VIX or IV drops sharply post-event                                        | Premiums contracting; selling vol structures favourable             |
| Positioning imbalance | Crowded longs/shorts, strong hedging flows, exaggerated reactions         | Squeeze or forced unwind risk elevated                              |
| Trend breakout        | Price breaks above resistance or below support with follow-through        | Repositioning underway; trend continuation possible                 |
| Momentum continuation | Series of higher highs/lows, large directional candles, shallow pullbacks | Trend strong; directional structures favoured                       |

---

## Step 3 — Sector / Ticker Narrowing

From the flow data, identify which sectors and specific names show concentrated or unusual activity.
Cross-reference unusual activity (high Vol/OI) with options flow (large premium, sweeps, BuyToOpen labels).
Names appearing in both datasets carry stronger signal weight.

---

## Step 4 — Possible Play

For each high-conviction ticker, walk the chain explicitly: **regime → setup → trigger → play.**
Name the setup the ticker is in (Step 2), confirm its trigger condition is met, then propose
a structure **drawn from that setup's allowed list** with a direction matching the setup's bias.

**Binding rule:** a structure that contradicts its setup's bias — e.g. `RF | bull call spread` —
is invalid. If your directional thesis is bullish, the setup must be BO or PB; if bearish, RF or
DC. Pick the setup that matches the thesis, then pick the structure from that setup, never the
other way around.

Produce a full slate every run: **at least 5 stock plays and at least 3 ETF plays**
(8+ total), ordered strongest conviction first, drawn from the highest-scoring names
in the data — stock plays from the stock sections, ETF plays from the ETF sections.
When conviction is thin, still meet the minimums but mark those ideas low confidence
rather than dropping them; never invent a ticker absent from the data. This is in
addition to the always-present market read (regime + signals + sector focus).

Format each play as:

> **[TICKER]** — [setup label] | [structure] | [thesis in one sentence]
> Trigger: [what must happen for entry]

Structure selection — pick from the setup's allowed list (Step 2). Direction is already
fixed by the setup; **IV picks debit vs credit:**

- Bullish (BO/PB), low or rising IV → debit: long call, bull call spread
- Bullish (BO/PB), high or falling IV → credit: short put, bull put spread
- Bearish (RF/DC), low or rising IV → debit: long put, bear put spread
- Bearish (RF/DC), high or falling IV → credit: bear call spread, short call
- RANGE + H-VOL → iron condor, short strangle, sell premium
- VE / E-VOL (volatility expanding) → long straddle/strangle, back-spread, long convexity
- C-VOL (volatility compressing) → calendar spreads, diagonal spreads, sell premium
- MS / tail risk → OTM put/call, VIX calls, long convexity hedge

---

## Step 5 — Invalidation

For each play, state what would make the thesis wrong.
Be specific — name price levels, flow reversals, or macro events that would trigger a cut or adjustment.

Format:

> **[TICKER]** invalidation: [specific condition]

---

## Output Format

Respond with a JSON object with exactly these keys (all plain strings):

```json
{
  "regime": "Labels + one-sentence read. Include the macro label only when corroborated by cross-asset evidence; otherwise omit it. E.g. BEAR + H-VOL + RISK-OFF — elevated VIX, put hedging dominant across index ETFs, no sustained RISK-ON rotation.",
  "signals": "Tagged signal list. E.g. [FLOW] Heavy QQQ put sweeps | [VEGA] VIX call buying 35-40 | [PRICE] NVDA testing 180 support",
  "sector_focus": "Sectors/names with concentrated flow and what it implies. Cross-reference unusual activity + flow.",
  "plays": "At least 5 stock + 3 ETF plays (8+), each tagged asset_class stock|etf and a confidence, with setup, structure, thesis, trigger. E.g. 1. NVDA (stock, high) — PB | Bull call spread 185/200 | Call buying into a dip to support suggests accumulation. Trigger: hold above 180.",
  "invalidation": "Per-ticker invalidation conditions. E.g. NVDA: daily close < 178 with volume. QQQ: sustained hold above 460."
}
```

Respond with JSON only — no markdown fences, no extra text.
