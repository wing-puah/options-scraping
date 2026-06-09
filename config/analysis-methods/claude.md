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
  `SellToOpen`, `ToOpen`) is present.
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

- **Deep-ITM options** are still a directional input — a deep-ITM call bought is
  bullish exposure (often stock replacement), a deep-ITM put bearish. What they
  are not is a conviction-weighted bet on a _move_: they are ~1.0 delta and mostly
  intrinsic value, so their premium reflects stock exposure, not optionality.
  Strip intrinsic value out before letting premium drive the conviction weight,
  and size conviction by **delta-adjusted notional** (delta × Size × 100 ×
  underlying — the share-equivalent exposure), not raw premium: 100 deep-ITM calls
  and 10 are different conviction, and that is the axis that separates them.
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

**Read every print through its DTE — same side and premium mean different things
by maturity.** Treat DTE as a first-class interpretive axis, not just an
expiry-matching check at play-selection:

- **~0–14 DTE** — an event/earnings bet or a same-week gamma play; expires before
  most theses resolve.
- **~15–60 DTE** — tactical directional or hedging positioning.
- **~60–180 DTE** — macro / catalyst protection or a medium-horizon view.
- **180+ DTE / LEAPs** — strategic positioning or stock replacement; large
  notional here is a stance, not a near-term signal.

Before promoting any signal, ask what the _benign_ explanation is and whether the
data rules it out. Large call premium can be a covered-call sale or a spread leg;
an index put sweep can be routine hedging of a long book; high volume-to-OI can
be expiry-day rolling. If the innocent reading survives, the observation stays a
description — "call activity," "downside positioning," "hedging pressure" — and
does not become a directional claim.

Never equate call with bullish, put with bearish, premium with conviction, or
volume with a new position.

The prepared rollup now carries a **conviction score** per ticker that
pre-computes much of this ladder — premium *rank within the day*, repetition,
cross-section overlap, Vol/OI, and opening-label presence — and, under `--days N`,
a **persistence** view across prior days. Use the score to triage where attention
goes, and treat a high score that recurs across days as stronger than a one-day
spike. It is deliberately direction-agnostic — it never decides bull vs bear — and
it is necessary, not sufficient: a high-scoring name still has to clear the
benign-explanation check above before it becomes a directional claim.

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
bid. The regime sentence must name both the dominant signal and the strongest
counter-signal; when they genuinely balance, call it `RANGE` and explain the
tension rather than forcing a direction.

## Select names and structures

Pick **two to five** plays. Quality over coverage — appearing in the data is not
a reason to be on the list. A name normally needs at least two of: repeated or
large-premium flow, unusual volume/OI, sector-and-index confirmation, a clear
nearby trigger level, and a structure that fits the regime. Keep directional
plays and portfolio hedges separate, and make sure a regime-consistent hedge is
present whenever the read is `RISK-OFF` or hedge-pressure.

Default to **defined-risk** structures. The dataset gives no portfolio size, risk
tolerance, or full volatility surface, so uncapped risk is never justified from
flow alone.

- Bullish flow into elevated IV → bull call spread, not a naked call (you would
  be paying rich premium).
- Bearish flow or hedge pressure into elevated IV → bear put spread.
- Genuine volatility expansion with no directional winner → long
  straddle/strangle, but only when both sides carry real evidence.
- Short-volatility structures (condor, strangle, calendar) only when compression
  is explicit (`C-VOL`).
- Match DTE to the catalyst: if the thesis rests on a `[CAT]` event, the expiry
  must clear it.

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

## Confidence and language

Assign confidence, then let it gate the output:

- **High** — repeated, cross-confirmed, directionally coherent, and survives the
  benign-explanation check.
- **Medium** — solid evidence with a material counter-signal (which is named in
  the play text).
- **Low** — isolated or ambiguous; stays a description, never a play.

Only high- and medium-confidence ideas become plays. Use calibrated verbs —
"suggests," "supports," "indicates," "consistent with" — and never "proves" or
"shows the buyer intended."

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
to make conviction IV-robust, and a deferred forward-looking vol layer (IV rank,
VIX term structure). Note: premium already embeds IV, so IV is never multiplied
into the score; and realized vol is for stop-sizing only, never a forward signal.
