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
3. **Vol richness** — Is IV cheap or expensive relative to what is likely to happen? Read the rollup's "Vol regime snapshot" — VIX/VIX3M term structure (contango vs backwardation), VIX9D/VIX, VVIX — not absolute VIX level alone. VIX 20 in contango-and-falling is a different environment from VIX 20 in backwardation-and-rising.
4. **Price** — Use price action last, to confirm timing and direction.

| Playbook               | Short | Edge source                                      | Arises when                                                                    | Bias                                      |
| ---------------------- | ----- | ------------------------------------------------ | ------------------------------------------------------------------------------ | ----------------------------------------- |
| Trend Following        | TF    | Momentum + dealer hedge-chasing                  | Sustained directional move; negative gamma forces dealers to amplify           | With trend                                |
| Mean Reversion         | MR    | Stretched positioning + overpriced IV            | Price ≈2× ATR from mean; elevated skew; crowd extended in one direction        | Opposite extension                        |
| Gamma Expansion        | GE    | Negative gamma acceleration on breakout          | Range compression → breakout; dealers short gamma and must chase               | With breakout direction                   |
| Volatility Compression | VC    | IV overpriced post-spike                         | VIX/VIX3M restoring contango; VVIX falling; C-VOL regime                       | Non-directional                           |
| Positioning Unwind     | PU    | Forced repositioning from crowded book           | Large one-sided OI + catalyst or sentiment shift; hedging flow reversal        | With unwind direction                     |
| Dealer Pinning         | DP    | Dealer suppression of realized vol near large OI | High positive gamma; large OI cluster at nearby strike; realized vol declining | Non-directional (range around pin strike) |

**SH (safe-haven flow)** maps to PU or TF on defensive assets (GLD/TLT). **MS (macro shock)** maps to GE (sudden negative-gamma break) or VC (post-shock IV normalization).

#### VIX Term Structure

Absolute VIX level is an incomplete signal — the same reading can call for opposite structures. Characterize term structure before selecting structure or DTE. The prepared rollup carries a **"Vol regime snapshot"** section (`lib/vol_snapshot.py`) with the exact metrics below — `term_ratio` = VIX/VIX3M, `event_ratio` = VIX9D/VIX, and VVIX; read it rather than guessing the regime:

| Signal                              | Reading                            | Implication                                                                          |
| ----------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------ |
| VIX/VIX3M < 1 (contango)            | Normal carry                       | VC and DP viable; premium-selling reasonable                                         |
| VIX/VIX3M > 1 (backwardation)       | Panic / crisis                     | Fade VC; prefer long convexity; backwardation can persist                            |
| VIX9D/VIX > 1 (event ratio)         | Near-term event risk               | Short-dated structures expensive; extend DTE past catalyst or buy event vol directly |
| VVIX elevated (>100)                | Vol-of-vol high                    | Straddles/strangles expensive to hold; prefer defined-risk spreads                   |
| SPX skew steep                      | Crash demand elevated              | Selling puts into steep skew is dangerous; downside bid for a reason                 |
| SPX skew flat / inverting           | Tail protection cheap or unwinding | VC or DP supported; put-spread selling rational                                      |

(SPX skew is not in the snapshot — it needs the options chain; check it manually before VC / DP entries.)

### Trigger Conditions

| Trigger               | Conditions                                                      | Dealer / positioning catalyst                            | Playbook |
| --------------------- | --------------------------------------------------------------- | -------------------------------------------------------- | -------- |
| Price extension       | Intraday move ≈2× expected move or 1.5–2× ATR                   | Skew steepening; crowd extended in extension direction   | MR       |
| Reversal signal       | Strong candle at S/R; elevated IV; momentum exhausting          | Positioning overcrowded; flow reversing direction        | MR, PU   |
| IV spike              | VIX / underlying IV rises sharply                               | VIX/VIX3M flips to backwardation (>1); VVIX spikes       | GE, PU   |
| IV compression        | IV drops sharply post-event                                     | VIX/VIX3M restores contango (<1); VVIX falling           | VC, DP   |
| Positioning imbalance | Crowded longs/shorts; exaggerated reactions                     | Large one-sided OI; hedge ratio extreme                  | PU       |
| Trend breakout        | Price breaks resistance/support with follow-through             | Dealers short gamma → forced to buy/sell into move       | TF, GE   |
| Momentum continuation | Higher highs/lows; large directional candles; shallow pullbacks | Dealer delta-hedging amplifying the move                 | TF       |
| Dealer pin            | Price orbiting large OI strike; realized vol declining          | Dealers long gamma → absorb flow, sell rallies, buy dips | DP       |

---

## Step 3 — Flow Intent

Classify what each play's premium is *doing*, as a per-play `flow_intent`. This
is a **classification, not a filter** — all four are valid plays we produce.
Label each correctly so protective flow is never read as a directional bet, and
mechanical exposure never inflates conviction.

**What each intent means** — the substance of the bet, not the detection test:

| `flow_intent`       | The bet                                                                                                                                                                                          |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **DIRECTIONAL**     | A bet that price moves a particular way. Profits from the move; invalidated by a price level. No offsetting book being protected.                                                                |
| **VOLATILITY**      | A bet on the *size* of the move / on implied vol, direction-agnostic — straddles, strangles, condors, calendars. Profits from realized-vs-implied vol; invalidated by IV collapse or decay without a move. |
| **HEDGE**           | Protection on an existing book — downside insurance, collars, put spreads held against longs. The defining feature is the *offsetting position being protected*; framed as protection, never a forecast. |
| **SYNTHETIC STOCK** | Mechanical exposure via deep-ITM options (~1.0 delta), conversions/reversals, stock-replacement, boxes. Premium is mostly intrinsic — exposure/financing, not a bet on a move.                    |

**How to detect / disambiguate** — the tests that assign the label:

- **Extrinsic premium** (premium − intrinsic) must be the bulk of the flow for
  DIRECTIONAL or VOLATILITY. Near-1.0-delta, mostly-intrinsic prints are
  **SYNTHETIC STOCK** — strip the intrinsic before ranking (`Ext$` / `Fin%` in
  the rollup already do this). SYNTHETIC STOCK is a soft positioning tell, not a
  high-confidence call on a near-term move.
- **DIRECTIONAL vs VOLATILITY** follows the playbook from Step 2 (TF/MR/GE/PU
  directional; VC/DP volatility) and the structure confirms it — a one-sided
  debit/credit spread is DIRECTIONAL; a straddle/strangle/condor/calendar is
  VOLATILITY.
- **Opening view vs HEDGE** turns on whether an *offsetting underlying position*
  is being protected. Bid-side calls / ask-side puts without a `ToOpen` label, overwrites,
  and closing flow read as **HEDGE** or **SYNTHETIC STOCK** until evidence (a
  `ToOpen` label, cross-asset confirmation) shows new risk being opened. This is
  the "don't read someone else's protection as your directional signal" rule.
- **Opening, not closing** — the premium must open new risk; a close is not a play.

`flow_intent` is **not** a confidence cap — confidence is scored separately in
Step 5, and the rubric is *weighted by intent* (Price-heavy for DIRECTIONAL,
Vol-heavy for VOLATILITY). Each intent carries its own confidence: a HEDGE can be
high-confidence (strong evidence the protection is warranted), a DIRECTIONAL can
be low. The only hard rule is correctness of the label — never tag protection or
mechanical exposure as DIRECTIONAL/VOLATILITY to dodge the evidence test.

---

## Step 4 — Possible Play

For each high-conviction ticker, select a playbook and then a structure using two layers.
Prioritise names that appear in both the unusual-activity and flow datasets — cross-dataset overlap is already scored as a conviction signal in the prepared rollup.

**Layer 1 — Select the playbook** using the four-question order from Step 2 (dealer → crowdedness → vol richness → price). The playbook is the edge source; the trigger condition table in Step 2 confirms the environment is active.

**Layer 2 — Select the structure.** Each playbook fixes a `flow_intent` and a view; IV and DTE then determine how aggressively to express it. One table carries the whole chain — playbook → intent → view → structure — so none dangle:

| Playbook                   | `flow_intent`            | View                                        | Aggressive (low IVpct / rising IV)   | Moderate                     | Conservative (high IVpct / falling IV) |
| -------------------------- | ------------------------ | ------------------------------------------- | ------------------------------------- | ---------------------------- | ----------------------------------- |
| **TF** Trend Following     | DIRECTIONAL              | Bullish / Bearish — momentum / breakout     | Long call / put                       | Debit spread / diagonal      | Credit spread                       |
| **TF-S** Trend Following — Slow | DIRECTIONAL         | Bullish / Bearish — slow grind, no catalyst | Credit spread (bull put / bear call)  | Credit spread                | Credit spread                       |
| **MR** Mean Reversion      | DIRECTIONAL              | Bullish / Bearish (counter-extension)       | Long call / put                       | Debit spread                 | Credit spread                       |
| **GE** Gamma Expansion     | DIRECTIONAL / VOLATILITY | Breakout direction, or Vol expansion        | Long ATM/OTM weekly, or long straddle | Debit spread / long strangle | Defined-risk debit / backspread     |
| **PU** Positioning Unwind  | DIRECTIONAL              | Bullish / Bearish (unwind direction)        | Long call / put                       | Debit spread                 | Credit spread                       |
| **VC** Vol Compression     | VOLATILITY               | Vol compression                             | Short strangle                        | Iron condor                  | Butterfly                           |
| **DP** Dealer Pinning      | VOLATILITY               | Pinning                                     | Short strangle                        | Iron condor                  | Butterfly                           |

**TF vs TF-S — choosing between them.** Weigh these factors in order; TF-S (credit) needs the *cluster*, not any one flag:

1. **Per-ticker IV percentile (primary rich/cheap read).** The rollup's `IVpct` column is Barchart's options-overview IV percentile — the share of the prior-1-year days whose IV closed below today's, scraped per date (see `lib/iv_history.py`) and shown as a percentage (stored as a decimal fraction, so 70% = 0.70). It normalises across names (a 40% IV is rich on KO, cheap on NVDA), which absolute IV and VIX cannot. **High IVpct (≥70%) → IV is rich → a debit spread buys expensive premium a slow move can't overcome → prefer TF-S / credit. Low IVpct (≤30%) → IV is cheap → debit / long premium (TF).** Backtest: debit spreads in the top IV tercile had a *negative* median return vs +21% in the bottom tercile — buying rich IV is the losing regime.
2. **Dealer gamma / GEX.** Positive gamma (spot above the flip) → dealers absorb flow, suppress realized vol → slow grind → TF-S. Negative gamma → dealers amplify → momentum → TF. This is the definitive gate; until per-name GEX is in the rollup (Phase 2 — see roadmap), the vol snapshot is the proxy.
3. **Realized vs implied vol.** A slow grinder has realized vol well below implied → theta edge favours the credit seller.
4. **Trend character.** Slow grind (shallow slope, price hugging a moving average, no gaps) → TF-S; range-break / gap / expanding candles → TF.
5. **VIX contango + no catalyst.** Deep contango (VIX/VIX3M < 0.85), no E-VOL, no HP, no near-term event → grind → TF-S.

- **TF (momentum/breakout):** debit structures capture the acceleration. Signs: LOW IVpct or rising IV, E-VOL, breakout from range, VIX/VIX3M rising toward or above 1, negative-gamma OI cluster being breached.
- **TF-S (slow grinder):** **credit spreads** (bull put spread for bullish, bear call spread for bearish) — the edge is time decay + "price doesn't breach the short strike," not "price moves far." Signs: HIGH IVpct, BULL + L-VOL + stable, VIX/VIX3M well in contango (<0.85), no E-VOL, no HP, no near-term catalyst, price grinding along a slow trend.

> **Preferred read — IV percentile, with a fallback.** `IVpct` (Barchart's per-ticker IV percentile) is the preferred rich/cheap input and should drive the TF-vs-TF-S call whenever it is present. It is **blank when the name wasn't enriched** (`fetch_iv_percentile` hasn't scraped it onto the compiled flow file, or Barchart returned no in-window row). When `IVpct` is blank, fall back to the proxy: dealer-gamma/GEX read → else the vol snapshot (contango + stable L-VOL + no E-VOL + no catalyst → treat as positive-gamma / TF-S and prefer credit) → else absolute IV level. The vol snapshot is already injected into every rollup.

For **TF / MR**, diagonal spreads and calendars are valid when stable IV + time-structure edge is present (trend continuation into a catalyst window; or MR where front-month vol is elevated but the longer leg is cheap).

> **Calendar / Diagonal format** — include BOTH expirations explicitly in the play text, near expiry first, separated by ` / `: e.g. `buy Jun 20 / Sep 19 500 call calendar` (same strike, two expirations) or `buy Jun 20 / Sep 19 480/500 call diagonal` (two strikes together, two expirations). The near-month leg is always short (sold), the far-month leg is always long (bought). Without two explicit expiration dates, the backtest classifier cannot build the two-leg position.

For **GE (Gamma Expansion)**, cross-check VIX term structure: contango → long ATM/slightly-OTM weekly or debit spread; backwardation → defined-risk debit spread or backspread (cap premium paid); VVIX elevated → defined-risk only.

**Binding rule:** Select the playbook from the market read, determine the view from the playbook's environment, then select the structure from the view + IV — never the reverse. A structure that contradicts the playbook's bias is invalid. Default to **defined-risk** structures (spreads, condors, butterflies). Naked calls or puts require very low IV + very high conviction; when VVIX is elevated, defined-risk is mandatory.

The two `flow_intent`s that sit **outside** the six alpha playbooks — their edge source is risk management / mechanics, not an alpha edge — do not route through the ladder above:

| Purpose                  | `flow_intent`       | Structure                                                                                            |
| ------------------------ | ------------------- | --------------------------------------------------------------------------------------------------- |
| Regime-driven protection | **HEDGE**           | protective puts, collars, put spreads vs. longs; sized to the book, not a target                     |
| Mechanical exposure      | **SYNTHETIC STOCK** | usually flagged not traded; if expressed, deep-ITM option for exposure — strip intrinsic from ranking |

**IV note — IV sets the ladder direction.** Pick **aggressive when IV is low or rising** (buy premium — long options / debit structures), **conservative when IV is high or falling** (sell premium — credit / defined-risk), moderate in between. The same view yields opposite structures: a *Bullish* read is a long call in cheap/rising IV but a short put or credit spread in rich/falling IV. Selecting a debit structure into high IV (or a credit structure into cheap IV) is a mismatch — fix the structure, not the view.

Produce a full slate every run: **at least 5 stock plays and at least 3 ETF plays**
(8+ total), ordered strongest conviction first, drawn from the highest-scoring names
in the data — stock plays from the stock sections, ETF plays from the ETF sections.
When conviction is thin, still meet the minimums but let those ideas score weak
(Step 5) rather than dropping them; never invent a ticker absent from the data. This is in
addition to the always-present market read (regime + signals + sector focus).

Format each play as:

> **[TICKER]** — [playbook label] | [structure] | [thesis in one sentence]
> Trigger: [what must happen for entry]

---

## Step 5 — Confidence

Confidence is conviction in the play's **own thesis**, scored on evidence
quality. It is **independent of `flow_intent`** — no intent caps it — but the
factor *weights* depend on the intent: a directional play lives or dies on price,
a volatility play on IV. The output is the five component scores themselves — a
`score` object of `{ flow, dealer, price, vol, catalyst }` integer points, one
per factor below. The model emits the components, not a total; the pipeline sums
them into `score_total` (0–100) downstream.

| Factor                 | Directional | Volatility | What earns it                                                                                                |
| ---------------------- | ----------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| **Flow confirmation**  | 25          | 20         | repetition / clustering, cross-dataset overlap (unusual + flow), extrinsic-premium concentration             |
| **Dealer alignment**   | 25          | 25         | dealer gamma supports the play — short gamma behind a trend/breakout; long gamma behind a pin                |
| **Price confirmation** | 20          | 10         | price action confirms — key level held or broken with follow-through, structure intact                       |
| **Vol alignment**      | 15          | 25         | IV / term structure / skew fit the chosen structure (cheap-or-rising IV for debit; rich-or-falling for credit) |
| **Catalyst support**   | 15          | 20         | a dated catalyst within the horizon corroborates the thesis (earnings, macro print, product event)           |

**HEDGE** and **SYNTHETIC STOCK** use the Directional weighting, but score the
relevant thesis: a HEDGE on whether the protection is genuine and well-placed
(not a price forecast), a SYNTHETIC STOCK on whether real exposure is being
built — it typically totals Weak and is flagged rather than traded.

**Per-name directional vol read (`IVspr` / `IVskew`).** The rollup carries two
direction-bearing vol columns (Lin, Lu & Driessen 2013) — use them to confirm
*Flow confirmation* and *Vol alignment*, never as standalone triggers:

- **`IVspr`** = OI-weighted (call IV − put IV) across matched strike/expiry pairs
  (10–60 DTE). **Positive → bullish** information (a positive predictor of equity
  returns); strongly negative corroborates a bearish thesis.
- **`IVskew`** = OTM-put IV − ATM-call IV (closest-moneyness contract each,
  10–60 DTE). **Steeper/more positive → downside demand**, negatively associated
  with future returns — it warns against selling puts and supports a bearish/hedge
  read.
- Both effects **roughly double around earnings/analyst events** — weight them up
  when a dated `[CAT]` sits inside the play's horizon, and ignore a side shown as
  `—` (no matched pair / empty band — computed on the traded-flow subset, so this
  is common and a proxy for the paper's chain-level measure, not proof of absence).

The `otm` conviction component (`OTM$` column) separately rewards
economically-sized **OTM** flow — the leveraged informed bet — but it is
direction-agnostic; read direction from `IVspr`/`IVskew` and the sentiment
columns, never from `OTM$`.

Bands are read off the summed total, never emitted directly: **Strong (was
"High") ≥ 70 · Moderate ("Medium") 40–69 · Weak ("Low") < 40.**

Guardrails — these override the component scores *downward* only, by
withholding points rather than by writing a label:

- If the play's `alternative_interpretation` is at least as plausible as the
  thesis → hold the total under 40 (zero the `price` and `catalyst` components,
  or drop the play). The benign-explanation check is mandatory.
- Short-dated-only evidence (≤14 DTE) cannot support a multi-week thesis →
  hold the total under 40, or re-tag as gamma/event flow.
- Polluted underlyings (convertible-hedge names, levered/inverse ETFs, miners as
  crypto proxies) without cross-asset confirmation → hold the total under 40.

`horizon` (`14|60|180|720`, Step 3/4) is emitted as its own column beside
`play`, not folded into the play cell's bracket line — the bracket now carries
only `flow_intent`.

---

## Step 5b — Themes

Group the day's plays into narrative themes and emit a `themes` array:
`[{ theme, tickers, breadth, read }]`. This is roadmap item 14 (Theme table),
now a live output rather than a backlog idea.

- **`breadth`** = the count of **independent** names expressing the theme —
  not a raw ticker count.
- **Correlated agreement is breadth, not corroboration.** Three AI-semis names
  (e.g. NVDA/AMD/SMH) calling the same trade is one trade expressed thrice, the
  same desks and the same macro — collapse them into one theme with
  `breadth: 3`, never read the repetition as three independent confirmations.
  Breadth across genuinely independent asset classes (equity + credit +
  duration + metals) counts for more than breadth piled up inside one sector.
- `themes` is **presentation-only**: it makes the day's story auditable at a
  glance and gives the regime sentence its evidence trail, but it never
  multiplies or otherwise changes any play's `score`.

---

## Step 6 — Invalidation

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
  "plays": "At least 5 stock + 3 ETF plays (8+), each tagged asset_class stock|etf, a flow_intent (DIRECTIONAL|VOLATILITY|HEDGE|SYNTHETIC STOCK), and a confidence, with playbook, structure, thesis, trigger. E.g. 1. NVDA (stock, DIRECTIONAL, high) — TF | Bull call spread 185/200 | Repeated call flow into momentum continuation with dealers short gamma. Trigger: hold above 180.",
  "invalidation": "Per-ticker invalidation conditions. E.g. NVDA: daily close < 178 with volume. QQQ: sustained hold above 460."
}
```

Respond with JSON only — no markdown fences, no extra text.
