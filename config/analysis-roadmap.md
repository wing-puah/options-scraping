# Analysis Roadmap & Design Rationale

Deferred improvements and the reasoning behind current design choices, captured
from review discussions. Shipped behavior lives in `analysis-framework.md` and
`analysis-methods/`; this file is the backlog plus the "why we did / didn't"
record so the next change doesn't undo a deliberate decision.

---

## Shipped (for reference)

- **Macro made optional** in the regime call — assigned only with cross-asset
  corroboration, never inferred from options flow alone.
- **Direction-agnostic conviction score** (0–10) in the quant layer
  (`lib/flow_summary.py`), computed from normalized inputs and surfaced as the
  `Score` column.
- **Multi-day persistence** tracking (`--days N` in `scripts/prepare_analysis.py`)
  — recurring names with premium and score trajectories, recomputed from raw
  daily data (no stored state).

---

## Design rationale — premium, IV, and the conviction score

**Premium already embeds IV; do not multiply them.** Premium = option price ×
size × 100, and the price itself rises with vol (vega; an ATM option ≈
0.4·S·σ·√T). So IV is *already inside* the premium number. Weighting premium *by*
IV would double-count vol and systematically inflate high-IV names — exactly the
over-reading the framework exists to resist.

Consequences, locked in deliberately:

- **IV is not a score input or multiplier.** It is a *separate axis*: premium
  answers "how much money showed up?"; IV answers "how should it be deployed —
  buy or sell vol?". Keep them orthogonal.
- **The score ranks premium *within the day*,** not absolute dollars — this
  normalizes the market-wide vol level so an expensive or high-IV name can't buy
  rank with raw premium.
- **If anything, IV should *discount* premium-as-conviction.** Equal premium at
  higher IV = fewer contracts = less real positioning. ($10M at 30% IV is ~4× the
  actual size of $10M at 120% IV.)
- The cleanest IV-robust positioning measure is **total contracts (Size)**, not
  premium — see backlog item 1.

> Do not "improve" the score by folding IV into the premium component. That is a
> regression, not an upgrade.

---

## Backlog

### 1. Size / contracts aggregate (near-term, cheap, no new deps)

The rollup currently aggregates premium and trade *count* per ticker, but not
summed `Size` (contracts). Adding it gives an IV- and price-independent measure
of real positioning, letting the score cross-check premium:

- big premium + big size → real positioning
- big premium + small size → just expensive vol / deep ITM

This is the most direct answer to "weigh premium against IV" and needs only a new
accumulator in `_flow_ticker_rows` plus a column. Could also become a score
component (size rank within day) alongside premium rank.

### 2. Forward-looking vol layer (DEFERRED — wanted, not now)

The genuinely forward signals for play selection, in rough priority:

- **IV rank / percentile** (per name) — where today's IV sits in its own trailing
  range. The single most useful "rich or cheap" read.
- **VIX term structure** (VIX vs VIX3M/VIX9D) — forward market-wide vol regime;
  backwardation = acute near-term fear that tends to mean-revert.
- **IV term structure** (front vs back month) and **skew** (put vs call IV) per
  name — forward measures of stress and directional/crash demand.

**Data caveat (the blocker):** barchart.com displays IV rank and VIX term
structure **live only — no historical series.** Split by feasibility:

- **VIX term structure history is actually free** via yfinance indices
  (`^VIX`, `^VIX9D`, `^VIX3M`, `^VIX6M`) — long history, trivial pull. Do this
  first when the layer is picked up.
- **Per-name IV rank history is the hard part** — it needs each name's historical
  IV, which Barchart shows live-only and most free sources don't keep. Two paths:
  (a) a paid surface/IV-history vendor; (b) **start logging our own daily
  snapshots** of IV rank into Drive. The scraper already runs ~2×/day, so a
  historical series accrues from whenever we start — *every delayed day is lost
  history*, so if this layer is wanted "eventually," starting the snapshot log
  early is nearly free and strictly better than waiting.

Per-name IV rank/term/skew needs the option chain/surface (yfinance option chain
or a vendor), which is heavier than the flow CSVs we read today.

### 3. RV / ATR context (low priority — sizing only, NOT a forward signal)

Realized vol is **backward-looking and must never be a trade trigger.** It does
not predict; "IV > trailing RV, therefore sell" is the naive-VRP trap. Legitimate
uses are narrow:

- **Stop / invalidation sizing** — place levels outside the noise band (ATR from
  the same OHLC tells you a normal day's range).
- **The realized leg** when measuring the variance risk premium over a holding
  period.
- A *baseline reference* that makes IV legible — but the forward decision stays
  IV-driven (see item 2).

If built, scope as an optional `--context` flag enriching only the top-scored
names via yfinance OHLC. Do not present RV as a vol signal in the output.

### 4. Sector-breadth (mostly already covered — do not over-build)

ETF-flow scoring already delivers theme-level breadth (SMH/SOXX/IGV/XLE/XOP all
get conviction scores). The only net-new piece is auto-attributing each single
stock to its sector ETF, which:

- needs a curated ticker→sector constituent map that goes stale (no sector column
  in the Barchart CSVs);
- overlaps the existing cross-section overlap + the LLM's "does SMH confirm the
  semis names?" step.

If ever built, do it at the **regime level** (a small curated map of ~8 themes
feeding the regime read), **not** as a per-ticker score component — a per-ticker
breadth bonus inflates a whole sector uniformly and does not improve the
intra-day ranking the score exists to provide. On-demand only.

### 5. Delta-adjusted notional, and greeks for the vol read (near-term, cheap)

The method now says deep-ITM should be sized by **delta-adjusted notional**
(`Delta × Size × 100 × underlying` = share-equivalent exposure), not raw premium,
because premium there is mostly intrinsic and overstates the bet. The feed already
carries `Delta`, so this is a new accumulator in `_flow_ticker_rows` alongside the
size aggregate of item 1 — no new deps. Use it as the conviction *size* axis so a
deep-ITM strike cannot buy rank with intrinsic-inflated premium while still keeping
its direction.

- **Pair with item 1:** premium rank, summed Size, and delta-adj notional are three
  views of "how much real exposure showed up"; deep-ITM separates them (big premium,
  big notional, modest Size).
- **Gamma/vega are ~0 deep ITM** — do *not* apply them there. They are informative
  for **ATM/OTM** prints and the **buy-vs-sell-vol** read, where they'd need a
  Black-Scholes greeks calc (all inputs — S, K, DTE, IV — are in the feed). Scope
  greeks as part of the deferred vol layer (item 2), not the deep-ITM fix.

### 6. DTE as a first-class feature (near-term, cheap)

`DTE` is a column but the score and rollup don't use it; the method reads it only
at play-selection. Bucket it in the rollup so the same side/premium is interpreted
by maturity (per the method's DTE table): `~0–14` event/gamma, `~15–60` tactical,
`~60–180` macro/catalyst protection, `180+` strategic / stock replacement. Cheapest
form is a per-ticker premium-by-DTE-bucket split surfaced to the LLM; it does not
need to enter the numeric score, only the rollup the model reads.

### 7. Next-day OI delta — open vs close confirmation (medium, high value)

The `*` opening label (`To Open` / `BuyToOpen` / `SellToOpen`, from
`size > OI + vol − size`) is a same-day *estimate* of opening activity. The
**actual** confirmation is the strike's **open-interest change the next session**:
OI up ≈ genuinely opening; OI flat/down ≈ closing or rolling. We already store
daily snapshots and recompute persistence from raw data (`--days N`), so this joins
naturally onto that machinery — match each prior-day print to the same
symbol/strike/expiry the next day and diff OI. This is the single strongest
open-vs-close discriminator available to us and is currently unused. Highest-value
item after the cheap ones. Cost: a cross-day strike-level join keyed on
symbol+strike+expiry; only meaningful in `--days N` / persistence runs.

### 8. Spread-leg detection — cut the biggest false-positive source (medium)

Gross premium overstates conviction when a print is one leg of a spread (a "5000
calls bought" that is really a debit vertical). Two tiers, both feasible:

- **Free now — `Code` flags.** Barchart's multi-leg condition codes already mark a
  print as part of a complex order: `MLET, MLAT, MLCT, MLFT, MESL, MASL, MFSL,
  TLET, TLCT, TLFT, TESL, TASL, TFSL, CBMO, MCTP`. Flag any print whose `Code` is
  one of these as a probable spread leg and **discount its directional weight /
  premium** before it drives conviction. This ships before Barchart's "coming soon"
  full-leg display.
- **Heuristic pairing.** Cluster same-`Symbol`, same-`Time` prints with opposite
  strikes/sides and comparable Size to reconstruct verticals, risk-reversals,
  collars, straddles/strangles, then interpret the *structure* rather than each leg.
  More code and false-positive-prone; do after the code-flag tier proves out.

---

## Phased evolution of the analysis engine

The analysis is intended to move along three phases as the quant layer matures.
The point is **not** to replace the LLM wholesale, but to push deterministic,
backtestable work down into code over time and keep the LLM for the judgment that
genuinely needs it — while measuring, at every step, whether each phase actually
generates alpha. The phases coexist; they are different *sources* of plays that
the backtest scores side by side (see "Alpha attribution" below).

### Phase 1 — LLM judgment on the rollup (current, shipped)

The engine reads the prepared markdown rollup (premium aggregation, call/put
balance, repeated-print clustering, conviction `Score`, multi-day persistence) and
returns the structured `plays` JSON. All interpretation — regime, corroboration,
direction, structure — is the model's. This is the baseline every later phase is
measured against.

### Phase 2 — scripted option-feature layer feeding the LLM (next)

Compute the features a discretionary options trader actually checks, in code,
before the LLM step, so the model reasons over a richer, pre-digested feature set
instead of re-deriving everything from raw prints. The decision inputs to script,
in rough priority:

- **Put/call ratio** — per ticker and aggregate, computed by premium, by Size, and
  by count (they diverge, and the divergence is itself signal). Cheap, no new deps.
- **Gamma / dealer-gamma exposure (GEX)** — needs a Black-Scholes greeks calc
  (inputs S/K/DTE/IV all in the feed; see item 5). Per-strike and per-name gamma,
  and a market-wide GEX read for the regime layer.
- **IV features** — IV rank/percentile, term structure, and skew (put vs call IV).
  This is the deferred vol layer (item 2); the **blocker is IV history**, so start
  the daily IV snapshot log early — every delayed day is lost history.
- The already-scoped quant features that belong in this layer: summed Size +
  delta-adjusted notional (items 1, 5), DTE bucketing (item 6), next-day OI delta
  (item 7), spread-leg flags (item 8).

This is "a lot more features to go through" — they accrete into `lib/flow_summary.py`
and the rollup, and most also become candidate score components. Phase 2 still ends
in the LLM `plays` JSON; what changes is the quality of what the model sees.

### Phase 3 — code-based / systematic alpha (eventual)

Once the feature set is rich and its relationship to realized P&L is understood
("something that could be determined over time"), express the play-generation
mapping itself in code — a deterministic rule set or a fitted/calibrated model that
emits plays directly from the features, with parameters tuned against backtest
outcomes rather than per-run judgment. It must emit the **same `ROW_COLUMNS`
play schema** so the backtest treats it identically to an LLM source. The LLM does
not necessarily disappear — it can become a reviewer/override layer or be reserved
for regimes the systematic model handles poorly — but the alpha is generated in
code and is reproducible.

### Alpha attribution — the standing requirement across all phases

The phases only mean something if we can tell **which source is actually making
money.** This is the missing infrastructure and the throughline of the whole plan:

- **Tag every play with its producing source/phase.** Mirror the existing
  engine→tab pattern (`AnalysisClaude` / `AnalysisGPT` in the engine registry):
  either a tab per source or a new `source` column in `ROW_COLUMNS` (also touch the
  sheet header and `analysis_to_rows()` in `core.py`). Granularity wanted:
  `p1-claude`, `p1-gpt`, `p2-claude`, `p3-systematic`, …
- **Backtest groups P&L by source.** `backtest.py` is already analysis-driven and
  reads a tab of plays; extend it to attribute results per source so each phase
  gets its **own** checkpoint stats (win rate, avg P&L at each `exit_days`),
  instead of one blended number. That is the "different indication on the backtest"
  per phase — the head-to-head that says whether Phase 2 features or Phase 3 code
  beat the Phase 1 baseline, and whether either beats just buying the headline flow.
- **Continuously re-check that alpha is still there.** The analysis is a live
  hypothesis, not a settled method — realized P&L must feed back. Add a standing
  step (and a note in the method file) to periodically run the attribution backtest,
  compare current alpha by source against its own history, and flag decay. A phase
  that stops beating the baseline gets demoted; the method file gets updated from
  what the backtest shows, not from intuition.
