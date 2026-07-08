# Claude Options Analysis Method

How Claude reads the four Barchart datasets and produces the regime, signals,
plays, and invalidations defined in `config/analysis-framework.md`.

This is a decision procedure, written to be auditable: it records what evidence
is used and how it is weighed, not a private train of thought. The shared
framework owns the vocabulary and the output schema; this file owns the
judgment.

## What the data actually is

Each row is a record of contracts that _traded_, not a labeled bet. Nothing in
it states who was buying, why, or whether the position is opening or closing.
Three quantities carry most of the information:

- **Volume** — how much attention a contract drew today.
- **Open interest** — how many positions already existed. Volume far above OI
  means new positioning; volume below OI usually means churn or closing.
- **Premium** — dollars at risk, which is what "large flow" measures, but it is
  inflated by expensive underlyings and deep-ITM strikes.

So the honest object of the analysis is _where capital and attention
concentrated_, from which positioning is inferred. Intent — bullish, bearish,
hedge, spread leg — is always a hypothesis layered on top, never a reading off
the row. The whole method is built to keep that distinction.

## Read the aggregate before any single name

The most common mistake with flow data is narrating one dramatic print. The
regime does not live in any one row; it lives in the shape of the whole day.
Before picking names, characterize that shape — roughly is fine:

- Did premium lean to calls or puts? On indexes/ETFs or single names? Toward
  upside or downside strikes?
- Is activity broad (many tickers, many sectors) or concentrated in one or two?
- Are the index and credit ETFs pointed the same way as the single-stock flow,
  or against it?

These tallies, even approximate, are the backbone of the regime call. A single
ticker can never overturn the aggregate; it can only add color to it.

When the prepared rollup includes a **Baseline context** section, read every
aggregate through it. Index put premium exceeding call premium is the
unconditional norm — books are hedged with puts every day — so raw put
dominance carries no regime information by itself; what carries information is
where today sits in its own trailing window.

- Cite the percentile, not the raw ratio, when an aggregate motivates a regime
  dimension or a market-level `[FLOW]` signal — "QQQ C/P 0.29, 12th percentile
  of the window", not "puts dwarf calls".
- Reserve strong sentiment/volatility labels (`RISK-OFF`, `RISK-ON`, `E-VOL`)
  for readings in roughly the outer quintile of the window (≤20th / ≥80th
  percentile), or for several related metrics leaning the same way. Mid-range
  percentiles pull the dimension toward `RANGE` / neutral, and the regime
  sentence should say the baseline is why.
- Scale trust in the percentiles with the window size the section reports.
  Below ~40 prior sessions a percentile moves several points per single day,
  so the outer-quintile gate alone is not enough: require a more extreme
  reading (roughly ≤10th / ≥90th) or agreement from a second related metric
  before a small-window percentile carries a strong label on its own.
- When the section reports insufficient history, fall back to the single-day
  read but say so — and never present put/call dominance as abnormal without
  a window to measure it against.

## Establish the regime

Classify all four dimensions from the framework, working top-down from the
broadest instruments inward:

1. **Indexes** — SPY, QQQ, IWM, DIA, RSP. Is upside broad or carried by one name?
2. **Sectors / themes** — SMH, SOXX, IGV, XLE, XOP, etc. What leads, what lags?
3. **Risk vs. defensive** — HYG, LQD, TLT, GLD, SLV, volatility products. Is
   credit confirming equities or diverging from them?
4. **Speculative** — IBIT, BITO, leveraged and high-beta themes. The risk-
   appetite thermometer.

Mapping to the four dimensions:

- **Direction** — net upside participation vs. downside protection. When both
  sides are large and index-wide, that is `RANGE`, not a weak trend.
- **Volatility** — short-DTE clustering, elevated IV, large opposing flows, and
  repeated hedges point to `E-VOL` / `H-VOL`; IV draining after an event points
  to `C-VOL`.
- **Macro** — assign a macro label only with cross-asset corroboration (rates,
  gold, and credit moving together). Equity options alone do not establish a
  macro catalyst.
- **Sentiment** — broad upside is `RISK-ON`; protection spanning indexes,
  credit, small caps, and speculative names is `RISK-OFF`.

The regime is the lens for everything after it: structure choice, which side to
favor, and how aggressive to be all follow from it.

## Weigh each signal by corroboration

Treat one print as a data point and corroboration as a signal. A signal's weight
rises with the number of _independent_ ways it is confirmed:

- It appears in both the unusual-activity and the large-premium flow datasets.
- It repeats — several prints clustering on one direction, strike zone, or expiry
  rather than a lone trade.
- It is confirmed up the chain: the stock by its sector ETF, the sector by the
  index.
- Volume materially exceeds open interest, and an opening label (`BuyToOpen`,
  `SellToOpen`, `ToOpen`) is present. The directional labels carry side; bare
  `ToOpen` does **not** — it establishes only that a position is new. A market
  maker selling a call and a fund buying one print the same label, so bare
  `ToOpen` is supporting evidence for "new positioning," never evidence of a
  buyer or a direction on its own.
- The strike, delta, and DTE are coherent with the thesis being claimed.

Discount or set aside (these carry little usable signal):

- A single isolated contract with no companion print — **but** an isolated print
  escapes the discount when it is a multi-exchange **sweep** (a `Code` of
  `ISOI`/`SLAI`/`SLCI`), carries the `*` **opening label** (`To Open` /
  `BuyToOpen` / `SellToOpen`), or shows abnormal **Size**. Gate the exception on
  size, sweep, or opening flag — never on premium/notional, which only re-imports
  the deep-ITM / expensive-underlying inflation. The strongest print of the day is
  sometimes a lone institutional block.
- Midpoint fills with no opening label.
- Premium that is large only because the underlying is expensive.
- **A strike implausibly far from spot for the contract's DTE** (e.g. >50% away
  with <60 DTE). Treat as a likely feed artifact — adjusted options after a
  split, a stale strike, or a different underlying parsed into the row — not as
  a real bet. Flag as a data anomaly and exclude from the regime read until the
  strike is verified against the current chain. Do not let "ToOpen at an
  impossible strike" anchor a directional claim.

Do **not** blanket-discount low delta. A 5-delta, short-dated wing is usually a
lottery ticket — but the same contract with abnormal Volume, Volume far above OI,
and a `*` opening label can be one of the day's stronger signals. The
discriminator is not delta; it is whether premium and Size are meaningful. Route
low-delta prints through the same Vol/OI + opening-label ladder as everything
else, and read what survives as a **volatility / event** signal (cheap convexity
ahead of a catalyst), not a directional-conviction anchor — it is as consistent
with a tail hedge as with a bet.

Keep, but read as _positioning_ rather than a directional bet — ambiguous intent
is not the absence of signal:

- **Deep-ITM options** are a *weak* directional input. A deep-ITM call bought
  can be stock replacement (bullish exposure) — but deep-ITM strikes are also
  the standard leg of conversions/reversals, collars, buy-writes, and
  financing trades, all non-directional by construction and indistinguishable
  in a single row. Keep the direction as a low-weight prior, promoted only
  when something else in the same name corroborates it. What they
  are not is a conviction-weighted bet on a _move_: they are ~1.0 delta and mostly
  intrinsic value, so their premium reflects stock exposure, not optionality.
  Strip intrinsic value out before letting premium drive the conviction weight,
  and size conviction by **delta-adjusted notional** (delta × Size × 100 ×
  underlying — the share-equivalent exposure), not raw premium: 100 deep-ITM calls
  and 10 are different conviction, and that is the axis that separates them.
  The rollup **precomputes all of this**: `Ext$` is the intrinsic-stripped
  (extrinsic) premium, `Fin%` is the share of premium from |delta| ≥ 0.85
  stock-substitute trades, and `ΔNot$` is the signed delta-adjusted notional.
  Read a name's real options demand off `Ext$`, its financing pollution off
  `Fin%`, and its deep-ITM size off `ΔNot$` — do not re-derive them from raw
  premium.
  Gamma/vega are ~0 this deep, so they differentiate nothing here — save them for
  the ATM/OTM and volatility reads. Do not discard the direction.
- **Bid-side calls and ask-side puts.** `Side` alone establishes only that the
  resting side was lifted — for a bid-side call, the **seller was aggressive and
  the buyer passive**; it does *not* establish who opened. The print could be a
  long-call liquidation, a covered-call open, a short-call open, or a short-call
  close. So the honest single-print read is a **net reduction in demand for upside
  exposure**, not "call-writing pressure" — upgrade to writing/short-open pressure
  only when the `SellToOpen` label is actually present. Symmetrically, ask-side
  puts are demand for downside protection.
- **Weight ask-side puts harder than ask-side calls** in the regime call. Puts
  carry intent more cleanly — they are less polluted by overwriting and yield
  programs than calls — so they are information-dense. But that density exists
  *because* institutions hedge with puts: heavy ask-side put buying should pull the
  `RISK-OFF` / volatility dimensions, **not** be read as a directional price-down
  forecast (one hedges longs one intends to keep). This is the same hedge-pressure
  logic weighted below — puts simply get more pull there than calls get on the
  upside.
- **Structurally polluted underlyings.** Some names have known non-directional
  option flow embedded in their structure: convertible-bond hedging (e.g. MSTR,
  where dealers short calls and buy puts to hedge the convert, not to express a
  view), systematic overwriting (BDCs, covered-call ETFs), structured-product
  underlyings, miners traded as crypto proxies, and levered or inverse ETFs.
  For these, raw put/call balance is a poor positioning read in isolation —
  large put flow on MSTR may be convert-hedge mechanics, not bearish conviction.
  Require cross-asset confirmation before promoting any single-name flow on
  these tickers to a directional play: for MSTR, agreement from BTC / IBIT /
  COIN / miners; for a miner, the underlying commodity or crypto; for a levered
  ETF, the underlying index. Without confirmation, the flow is positioning
  noise, not a `[FLOW]` signal.

**Read every print through its DTE — same side and premium mean different things
by maturity.** Treat DTE as a first-class interpretive axis, not just an
expiry-matching check at play-selection:

- **~0–14 DTE** — an event/earnings bet or a same-week gamma play; expires before
  most theses resolve.
- **~15–60 DTE** — tactical directional or hedging positioning.
- **~60–180 DTE** — macro / catalyst protection or a medium-horizon view.
- **720 DTE / LEAPs** — strategic positioning or stock replacement; large
  notional here is a stance, not a near-term signal.

The rollup's `Hzn` column precomputes the dominant bucket per ticker (by
extrinsic premium, e.g. `tact 64%`), and every play declares its own `horizon`
as the DTE bucket boundary (`14`/`60`/`180`/`720`). A name dominated by `14`
(≤14 DTE) prints is gamma/event flow that can vanish by tomorrow — it cannot
anchor a multi-week directional thesis.

Before promoting any signal, ask what the _benign_ explanation is and whether the
data rules it out. Large call premium can be a covered-call sale or a spread leg;
an index put sweep can be routine hedging of a long book; high volume-to-OI can
be expiry-day rolling. If the innocent reading survives, the observation stays a
description — "call activity," "downside positioning," "hedging pressure" — and
does not become a directional claim.

Never equate call with bullish, put with bearish, premium with conviction, or
volume with a new position.

The prepared rollup now carries a **conviction score** per ticker that
pre-computes much of this ladder — **extrinsic-premium** rank within the day
(intrinsic stripped, so financing flow cannot buy rank), repetition,
cross-section overlap, Vol/OI, and opening-label presence — and, under `--days N`,
a **persistence** view across prior days. Use the score to triage where attention
goes, and treat a high score that recurs across days as stronger than a one-day
spike; the persistence section's **Persistent names (≥3 days)** callout lists
exactly those names. It is deliberately direction-agnostic — it never decides
bull vs bear — and it is necessary, not sufficient: a high-scoring name still
has to clear the benign-explanation check above before it becomes a directional
claim.

## Reconcile contradictions

Mixed flow is the normal state, not noise to be averaged. Directional bets and
hedges coexist every day. Resolve in this priority:

1. Breadth outranks any single ticker.
2. Repeated flow outranks one large isolated print.
3. Cross-dataset and sector confirmation outrank raw premium size.
4. Credit (HYG/LQD) diverging from equity upside is weighted heavily — it tends
   to lead.

Strong single-name upside sitting underneath broad index/credit protection is
**hedge pressure** — a fragile rally, not a clean bull regime. A later increase
in broad protection is a shift toward `RISK-OFF` even while selected stocks stay
bid. The prepared markdown's **Hedge pressure** section precomputes this as a
0–100 score (extrinsic ETF put demand vs single-stock extrinsic call demand)
with its inputs itemized — start the hedge-pressure vs bear-regime call from
that number and its baseline percentile context, then adjust for what the score
cannot see (opening labels, strike placement, persistence). The regime sentence
must name both the dominant signal and the strongest counter-signal; when they
genuinely balance, call it `RANGE` and explain the tension rather than forcing
a direction.

## Select names and structures

Coverage follows the pipeline contract: **at least 5 stock plays and 3 ETF
plays**, ordered strongest first. The floor exists so every run produces a
testable record — quality is enforced by the score, not by the
count. A name still needs at least two of: repeated or large-premium flow,
unusual volume/OI, sector-and-index confirmation, a clear nearby trigger level,
and a structure that fits the regime. A name that clears fewer than two makes
the list only as explicit weak-scoring positioning, never dressed up as
conviction. Keep directional plays and portfolio hedges separate, and make sure
a regime-consistent hedge is present whenever the read is `RISK-OFF` or
hedge-pressure.

Do not spend play slots on copies of one trade. SPY, QQQ, and IWM bear put
spreads under a hedge-pressure regime are the same hedge three times: pick the
strongest expression (most skewed call/put balance, best opening-label
evidence), make that the hedge play, and cite the sibling indexes as
corroboration inside its `signal`. Fill the remaining ETF slots with
differentiated exposures the data actually supports — sector (IGV/SMH/XLE),
credit (HYG/LQD), duration (TLT), metals (GLD/SLV) — before adding a second
index hedge expressing the same view.

Every play runs the framework's two layers — **playbook → structure** (Step 4).
Layer 1 picks the playbook (Step 2: dealer → crowdedness → vol richness → price);
Layer 2 picks the structure from the playbook's view + IV using the framework's
combined table. Apply that table — do not restate it. The judgment on top of it:

- Work market-structure-down; never pick a structure first and retrofit a
  playbook. A structure that contradicts the playbook's bias is invalid — fix
  the playbook, not the number.
- Default to **defined-risk**: the dataset gives no portfolio size, risk
  tolerance, or full volatility surface, so uncapped risk is never justified
  from flow alone. Short-volatility structures (condor, strangle, calendar)
  only when compression is explicit (`C-VOL` or VC/DP).
- Match DTE to the catalyst: if the thesis rests on a `[CAT]` event, the expiry
  must clear it.
- Let the per-ticker **`IVpct`** column pick debit vs credit once direction is
  set — it is the "rich vs cheap" read that normalises across names (40% IV is
  rich on KO, cheap on NVDA), which the market VIX cannot. A trend name in a
  slow, positive-gamma grind with **high `IVpct` (≥70%)** is the **TF-S** case:
  sell a credit spread (bull put / bear call), because a debit into rich IV pays
  for premium the slow move can't overcome. **Low `IVpct` (≤30%)** → IV cheap →
  debit / long premium (TF). `IVpct` is Barchart's IV percentile (share of the
  prior-1yr days with IV below today's); blank when the name has no scraped row —
  then fall back to the vol snapshot proxy.

Before emitting any play, check that it is internally coherent — every number
in the play must refer to the same spot:

- Strikes, trigger levels, and invalidation levels must be mutually consistent
  with the underlying's current price as read from the prints. A bull call
  spread struck entirely below the trigger level (both legs already deep ITM at
  entry), or a trigger naming prices the structure cannot meaningfully interact
  with, means one of the numbers is wrong — re-derive spot from the data before
  writing any of them.
- Mirroring an opened structure is legitimate, but the thesis must say so, and
  the strikes still have to make sense from today's spot.
- Exactly **one** structure per play, with explicit strikes and a single DTE
  range — never "X or Y". The `play` field is parsed by the backtester;
  alternatives make the row untestable.

## Per-play regime and signal vs market regime and signal

The output schema has **two** regime fields and **two** signal fields, and they
answer different questions. Treat them as independent — never mirror the market
read into a play's fields.

**Market-level (top-level fields, written to the MARKET row):**

- `regime` — the regime of the tape: direction + volatility + sentiment (+ macro
  only if cross-asset corroborated) for the whole market.
- `signals` — cross-asset and macro patterns (broad index hedging, vol regime,
  sector rotation, credit divergence). Global to the run.

**Ticker-level (inside each play, written to that play's row):**

- `regime` — the volatility / level / posture state for THIS name (e.g.
  `BULL + E-VOL — testing 59 breakout, IV30 rising into earnings`, or
  `RANGE + L-VOL — pinned at 200, OPEX gravity`). It is the ticker's own
  setup, not the tape's. Leave **empty** when there is nothing ticker-specific
  to add beyond the market read — do NOT copy the market regime here.
- `signal` — the ticker-specific evidence chain for that play, pipe-separated
  and tagged with the framework vocabulary
  (`[FLOW]/[PRICE]/[MACRO]/[VEGA]/[CAT]`). The auditable "why this name, why
  this side."

A per-play `signal` should cite the concrete prints that survived the
corroboration ladder for that ticker — premium balance, Vol/OI, opening labels,
sweep codes, strike/DTE coherence, sector/index confirmation, nearby price
levels. Examples:

- `[FLOW] $10.3M calls vs $0.9M puts | [FLOW] 53x Vol/OI ToOpen $64 calls | [PRICE] testing breakout at 59`
- `[FLOW] ask-side put sweeps across SPY/QQQ/IWM, BuyToOpen labels | [VEGA] VIX call buying 35-40 | [MACRO] credit (HYG) diverging from equity highs`

Rules:

- Do NOT copy the market `regime` into a play's `regime`, and do NOT copy the
  market `signals` into a play's `signal`.
- A play's `regime` may be empty; a play's `signal` may NOT — if a ticker lacks
  enough ticker-specific evidence to fill the signal, it does not qualify as a
  play.

## Triggers and invalidation

Every play needs an entry that requires _confirmation after the snapshot_, and a
condition that proves it wrong.

Triggers:

- Bullish — hold a named support, then reclaim or break a relevant strike.
- Bearish — reject resistance, then lose a nearby support.
- Hedge — enter only once the protected index or sector loses the stated level.

Invalidation — at least one of:

- A daily close beyond a specific price level.
- A reversal in the flow pattern that generated the idea.
- Loss of the sector or credit confirmation.
- A macro or volatility condition that contradicts the setup.

Levels drawn from a single Barchart snapshot are approximate and must be checked
against a live chart before any trade.

## Classify every play: flow_intent and horizon

Each play declares what its flow IS (`flow_intent` — one of the four in framework
Step 3) and the maturity of its evidence (`horizon`). Step 3 owns the definitions
and the detection tests (extrinsic-bulk for DIRECTIONAL/VOLATILITY, playbook +
structure to split those two, the offsetting-book check to split an opening view
from a HEDGE); apply them, don't restate them. The method emphasis: `flow_intent`
is a **classification, not a confidence cap** — label it honestly, never tag
protection or mechanical exposure as `DIRECTIONAL`/`VOLATILITY` to dodge the
evidence test, then let confidence float on evidence quality (Step 5).

`horizon` is one of `14|60|180|720` — the DTE bucket boundary of the dominant
expiry in the cited prints (≤14 → 14, 15–60 → 60, 61–180 → 180, 181+ →
`720`). The rollup's `Hzn` column (e.g. `tact 64%`) shows the dominant bucket
as a cross-check. Horizon must be able to contain the thesis: `14` evidence
cannot carry a multi-week directional claim. `horizon` is emitted as its own
column beside `play` — it is no longer folded into the play cell's bracket
line, which now carries only `flow_intent`.

## Confidence and language

Confidence is no longer a single label — the output is the framework's Step 5
rubric, but the model now emits only three of its five components: a `score`
object of `{ flow, dealer, vol }` integer points, sized by the intent-set
weights, plus two REQUIRED sibling fields — `key_level` (the specific price
threshold the play's own `structure`/`invalidation`/`trigger` already implies)
and `direction` (`bullish|bearish|neutral`). The other two Step-5 factors,
`price` and `catalyst`, are no longer model judgment — the pipeline computes
them from fetched price-history and earnings-date data, grounded by
`key_level`/`direction` instead of the model's own recall
(`lib/price_catalyst.py`). Emit the three components plus `key_level`/
`direction`; do not compute or emit a total — the pipeline sums all five into
`score_total` (0–100) downstream. Confidence is **independent of
`flow_intent`**: a HEDGE or DIRECTIONAL play scores wherever its evidence puts
it. The method emphasis on what each band of the *summed total* looks like in
this data (interpretation only — never emitted directly):

- **Strong (≥70)** — repeated, cross-confirmed, coherent, and survives the
  benign-explanation check.
- **Moderate (40–69)** — solid evidence with a material counter-signal, which
  is named in the play text.
- **Weak (<40)** — isolated or ambiguous; never a conviction bet. A weak idea
  may still fill a coverage slot, but it must be framed as positioning, name the
  unresolved conflict in its text, and gate its trigger on the missing
  confirmation (e.g. a crypto proxy waiting on BTC/IBIT agreement). Guardrails
  hold the total here by withholding points (typically zeroing `price` and
  `catalyst`), not by writing a label.

Strong and moderate ideas are the real plays; weak entries exist only to
satisfy the coverage floor honestly rather than by inflating the score. Use
calibrated verbs — "suggests," "supports," "indicates," "consistent with" —
and never "proves" or "shows the buyer intended."

Also emit market-level `themes`: `[{ theme, tickers, breadth, read }]`,
grouping the day's plays into narrative clusters. `breadth` counts
**independent** names, not raw tickers — correlated agreement (e.g.
NVDA/AMD/SMH all expressing one AI-semis trade) is breadth, never
corroboration, and `themes` never changes a play's `score`.

## Data scope

By default the prepared markdown contains **all** parsed rows per section (the
full trading day). It is truncated only when a run is explicitly capped with
`--rows N`, which keeps the last N rows. When the full day is too large to take
in one pass, fix the regime from the smaller ETF/unusual sections first, then
work the large single-stock sections **ticker by ticker** rather than truncating
— that preserves every row's signal. Capping the tail is a last resort; when used
or when working a subset, flag any conclusion that depends on rows not actually
in view.

## Limitations and failure modes

- The input is a snapshot of traded contracts, not a statistical summary of the
  day; aggregate claims are only as good as what was captured.
- Direction and opening/closing intent are frequently unavailable.
- Multi-leg spreads can appear as unrelated single contracts, distorting a name's
  apparent direction.
- No price charts, realized volatility, news, or full volatility surface is
  present, so macro and regime labels are hypotheses, not diagnoses.
- The standing temptation is to over-read one striking print; the aggregate and
  the corroboration ladder exist to resist it.

The quant layer now supplies per-ticker premium aggregation, call/put balance,
repeated-print clustering, a direction-agnostic conviction score, and multi-day
persistence ahead of this step. Remaining work and the rationale behind current
choices live in `config/analysis-roadmap.md` — chiefly a size/contracts aggregate
to make conviction IV-robust. Per-name **IV percentile now ships** as the `IVpct`
column (scraped from Barchart's options-overview history), alongside the directional
IV skew; market-wide VIX term structure ships in the "Vol regime snapshot".
Note: premium already embeds IV, so IV is never multiplied into the score; and
realized vol is for stop-sizing only, never a forward signal.
