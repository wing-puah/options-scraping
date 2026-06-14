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

## Step 2 — Signal Tagging and Playbook Selection

Tag each observation with the signal type that generated it.

### Signal Types

| Tag     | Meaning                                                             | Example                               |
| ------- | ------------------------------------------------------------------- | ------------------------------------- |
| [FLOW]  | Options flow — unusual activity, put/call ratio, sweeps, blocks     | Put sweeps on QQQ while index rallied |
| [PRICE] | Technical price structure — support, resistance, breakout, range    | NVDA testing 180 key support          |
| [MACRO] | Geopolitical or economic events                                     | Fed hold, CPI print, war escalation   |
| [VEGA]  | Implied volatility behaviour — VIX spikes, IV expansion/compression | VIX call buying at 35–40              |
| [CAT]   | Corporate catalyst — earnings, guidance, product launch             | NVDA earnings in 2 weeks              |

### Master Playbooks

A playbook names the **edge source** — the structural reason this situation is expected to pay. Select the playbook by answering four questions in order, from market structure down to price:

1. **Dealer positioning** — Are dealers long or short gamma? Positive gamma suppresses realized vol and pins price near large OI strikes. Negative gamma amplifies moves — dealers must hedge by buying into rallies and selling into declines, which accelerates trends.
2. **Crowdedness** — Is the book one-sided? Extreme put/call flow balance, large OI clusters on one strike, and flow concentrated in one direction signal a crowded position susceptible to forced unwind.
3. **Vol richness** — Is IV cheap or expensive relative to what is likely to happen? Use VIX term structure (contango vs backwardation), VVIX, and skew — not absolute VIX level alone. VIX 20 in contango-and-falling is a different environment from VIX 20 in backwardation-and-rising.
4. **Price** — Use price action last, to confirm timing and direction.

| Playbook | Short | Edge source | Arises when | Bias |
| -------- | ----- | ----------- | ----------- | ---- |
| Trend Following | TF | Momentum + dealer hedge-chasing | Sustained directional move; negative gamma forces dealers to amplify | With trend |
| Mean Reversion | MR | Stretched positioning + overpriced IV | Price ≈2× ATR from mean; elevated skew; crowd extended in one direction | Opposite extension |
| Gamma Expansion | GE | Negative gamma acceleration on breakout | Range compression → breakout; dealers short gamma and must chase | With breakout direction |
| Volatility Compression | VC | IV overpriced post-spike | VX1/VX2 restoring contango; VVIX falling; C-VOL regime | Non-directional |
| Positioning Unwind | PU | Forced repositioning from crowded book | Large one-sided OI + catalyst or sentiment shift; hedging flow reversal | With unwind direction |
| Dealer Pinning | DP | Dealer suppression of realized vol near large OI | High positive gamma; large OI cluster at nearby strike; realized vol declining | Non-directional (range around pin strike) |

**SH (safe-haven flow)** maps to PU or TF on defensive assets (GLD/TLT). **MS (macro shock)** maps to GE (sudden negative-gamma break) or VC (post-shock IV normalization).

#### VIX Term Structure

Absolute VIX level is an incomplete signal — the same reading can call for opposite structures. Characterize term structure before selecting structure or DTE:

| Signal | Reading | Implication |
| ------ | ------- | ----------- |
| VX1/VX2 < 1 (contango) | Normal carry | VC and DP viable; premium-selling reasonable |
| VX1/VX2 > 1 (backwardation) | Panic / crisis | Fade VC; prefer long convexity; backwardation can persist |
| VIX9D/VIX elevated | Near-term event risk | Short-dated structures expensive; extend DTE past catalyst or buy event vol directly |
| VVIX elevated (>100) | Vol-of-vol high | Straddles/strangles expensive to hold; prefer defined-risk spreads |
| SPX skew steep | Crash demand elevated | Selling puts into steep skew is dangerous; downside bid for a reason |
| SPX skew flat / inverting | Tail protection cheap or unwinding | VC or DP supported; put-spread selling rational |

### Trigger Conditions

| Trigger | Conditions | Dealer / positioning catalyst | Playbook |
| ------- | ---------- | ----------------------------- | -------- |
| Price extension | Intraday move ≈2× expected move or 1.5–2× ATR | Skew steepening; crowd extended in extension direction | MR |
| Reversal signal | Strong candle at S/R; elevated IV; momentum exhausting | Positioning overcrowded; flow reversing direction | MR, PU |
| IV spike | VIX / underlying IV rises sharply | VX1/VX2 flips to backwardation; VVIX spikes | GE, PU |
| IV compression | IV drops sharply post-event | VX1/VX2 restores contango; VVIX falling | VC, DP |
| Positioning imbalance | Crowded longs/shorts; exaggerated reactions | Large one-sided OI; hedge ratio extreme | PU |
| Trend breakout | Price breaks resistance/support with follow-through | Dealers short gamma → forced to buy/sell into move | TF, GE |
| Momentum continuation | Higher highs/lows; large directional candles; shallow pullbacks | Dealer delta-hedging amplifying the move | TF |
| Dealer pin | Price orbiting large OI strike; realized vol declining | Dealers long gamma → absorb flow, sell rallies, buy dips | DP |

---

## Step 3 — Possible Play

For each high-conviction ticker, select a playbook and then a structure using two layers.
Prioritise names that appear in both the unusual-activity and flow datasets — cross-dataset overlap is already scored as a conviction signal in the prepared rollup.

**Layer 1 — Select the playbook** using the four-question order from Step 2 (dealer → crowdedness → vol richness → price). The playbook is the edge source; the trigger condition table in Step 2 confirms the environment is active.

**Layer 2 — Select the structure** using directional view and IV. The playbook fixes the bias; IV and DTE determine how aggressively to express it:

| View | Aggressive (low or rising IV) | Moderate | Conservative (high or falling IV) |
| ---- | ----------------------------- | -------- | --------------------------------- |
| Bullish | Long call | Call spread | Short put |
| Bearish | Long put | Put spread | Short call |
| Vol expansion | Straddle | Strangle | Calendar |
| Vol compression | Short strangle | Iron condor | Butterfly |
| Pinning (DP) | Iron condor | Short strangle | Butterfly |

For **TF / MR**, diagonal spreads and calendars are valid when stable IV + time-structure edge is present (trend continuation into a catalyst window; or MR where front-month vol is elevated but the longer leg is cheap).

For **GE (Gamma Expansion)**, cross-check VIX term structure: contango → long ATM/slightly-OTM weekly or debit spread; backwardation → defined-risk debit spread or backspread (cap premium paid); VVIX elevated → defined-risk only.

**Binding rule:** Select the playbook from the market read, determine the view from the playbook's environment, then select the structure from the view + IV table — never the reverse. A structure that contradicts the playbook's bias is invalid. Default to **defined-risk** structures (spreads, condors, butterflies). Naked calls or puts require very low IV + very high conviction; when VVIX is elevated, defined-risk is mandatory.

Produce a full slate every run: **at least 5 stock plays and at least 3 ETF plays**
(8+ total), ordered strongest conviction first, drawn from the highest-scoring names
in the data — stock plays from the stock sections, ETF plays from the ETF sections.
When conviction is thin, still meet the minimums but mark those ideas low confidence
rather than dropping them; never invent a ticker absent from the data. This is in
addition to the always-present market read (regime + signals + sector focus).

Format each play as:

> **[TICKER]** — [playbook label] | [structure] | [thesis in one sentence]
> Trigger: [what must happen for entry]

---

## Step 4 — Invalidation

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
  "plays": "At least 5 stock + 3 ETF plays (8+), each tagged asset_class stock|etf and a confidence, with playbook, structure, thesis, trigger. E.g. 1. NVDA (stock, high) — TF | Bull call spread 185/200 | Repeated call flow into momentum continuation with dealers short gamma. Trigger: hold above 180.",
  "invalidation": "Per-ticker invalidation conditions. E.g. NVDA: daily close < 178 with volume. QQQ: sustained hold above 460."
}
```

Respond with JSON only — no markdown fences, no extra text.
