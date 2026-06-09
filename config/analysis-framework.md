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

| Setup                     | Trigger                                          | Interpretation                                |
| ------------------------- | ------------------------------------------------ | --------------------------------------------- |
| HP (Hedge pressure)       | Market rally + downside hedging appears          | Rally may not hold; institutions still hedged |
| RF (Resistance fade)      | Price approaches resistance + momentum weakening | Fade the move, not chase it                   |
| VE (Volatility Expansion) | Macro uncertainty + volatility rising            | Long vol / long convexity structures favoured |
| SH (Safe haven flow)      | Risk event + safe-haven demand (GLD, TLT)        | Risk-off positioning underway                 |
| DC (Dead cat bounce)      | Sharp selloff + weak rebound                     | Sell the bounce, not buy the dip              |
| MS (Macro shock)          | Sudden macro event + volatility spike            | Reactive vol — fades quickly or escalates     |

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

For each high-conviction ticker, propose a trade structure consistent with the regime and signal.

Format each play as:

> **[TICKER]** — [setup label] | [structure] | [thesis in one sentence]
> Trigger: [what must happen for entry]

Structure selection guide:

- BULL + L-VOL → long calls, bull call spreads, buy ATM/OTM calls
- BEAR + H-VOL → bear put spreads, buy puts, short calls (sell premium into high IV)
- RANGE + H-VOL → iron condor, short strangle, sell premium
- E-VOL (volatility expanding) → long straddle/strangle, back-spread, long convexity
- C-VOL (volatility compressing) → calendar spreads, diagonal spreads, sell premium
- Tail risk / macro shock → OTM put/call, VIX calls, long convexity hedge

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
  "plays": "Numbered plays with setup, structure, thesis, trigger. E.g. 1. NVDA — HP | Bull call spread 185/200 | Call buying on dip + hedge pressure suggests institutional accumulation. Trigger: hold above 180.",
  "invalidation": "Per-ticker invalidation conditions. E.g. NVDA: daily close < 178 with volume. QQQ: sustained hold above 460."
}
```

Respond with JSON only — no markdown fences, no extra text.
