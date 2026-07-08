# Analysis Roadmap & Design Rationale

Deferred improvements and the reasoning behind current design choices, captured
from review discussions. Shipped behavior lives in `analysis-framework.md` and
`analysis-methods/`; this file is the backlog plus the "why we did / didn't"
record so the next change doesn't undo a deliberate decision.

---

## Shipped (for reference)

- **Macro made optional** in the regime call — assigned only with cross-asset
  corroboration, never inferred from options flow alone.
- **Direction-agnostic conviction score** (0–14 raw, less a financing penalty) in
  the quant layer (`lib/flow_summary/`), computed from normalized inputs and
  surfaced as the `Score` column. Components: `flow`/`rep`/`cross`/`voloi`/`otm`/
  `open`/`persist`, the forward-confirmed `OIConfirm` (±, item 7), and the negative
  `fin_penalty` — see `config/conviction-score.md`.
- **Multi-day persistence** tracking (`--days N` in the analysis pipeline,
  `scripts/analysis_pipeline/`)
  — recurring names with premium and score trajectories, recomputed from raw
  daily data (no stored state).
- **Market-level regime baseline** (June 2026) — one aggregate row per trading
  date in the `BaselineDaily` sheet tab (section C/P by premium / contracts /
  count, put-dominance breadth, key-ticker premiums, prem-weighted DTE / SPY IV),
  written daily by `scripts/build_baseline.py` via the compile workflow
  (idempotent, self-healing `--backfill`). The pipeline fetch
  (`scripts/analysis_pipeline/fetch.py`) injects a
  "Baseline context" section — today vs a staleness-aware trailing window
  (≤60 sessions within 120 days) as percentiles — and the method files gate
  strong regime labels (`RISK-OFF`/`E-VOL`) on outer-quintile readings. Pure
  logic in `lib/baseline.py`. Rationale: index put premium > call premium is
  the unconditional norm; only the percentile says whether today is unusual.
- **Play coherence + coverage rules in the method files** (June 2026) —
  strikes/trigger/invalidation must agree on one spot; exactly one structure
  per play (backtester parses the `play` field); no redundant correlated index
  hedges; coverage floor (5 stock / 3 ETF) reconciled with confidence gating
  (low-confidence entries fill the floor as positioning, never dressed up).
- **Extrinsic-premium ranking + pollution columns** (June 2026, from external
  review of the 06-11 analysis) — the score's `flow` component now ranks
  **extrinsic premium** (premium − intrinsic, floored at 0; falls back to full
  premium when `Price~`/`Strike` are missing) instead of raw premium, so
  deep-ITM financing/conversion flow can no longer buy rank. The rollup also
  carries `Ext$`, `Fin%` (share of premium from |delta| ≥ 0.85 trades),
  `ΔNot$` (signed delta-adjusted notional — backlog item 5, now shipped), and
  `Hzn` (dominant DTE bucket by extrinsic: event 0–14 / tact 15–60 / med
  60–180 / strat 180+ — backlog item 6, now shipped). Gamma/vega remain
  deferred to the vol layer (gamma is not in the feed and is ~0 deep ITM
  anyway).
- **Hedge-pressure score** (June 2026) — first-class 0–100 metric in the
  prepared markdown: `100 × hedge_put_ext / (hedge_put_ext + stock_call_ext)`
  over HEDGE_TICKERS (SPY/QQQ/IWM/DIA/RSP/HYG/LQD/SMH/SOXX), extrinsic-only so
  financing puts don't count as hedge demand. Static buckets (risk-on /
  neutral / hedge-pressure / risk-off / panic); the method files gate it on
  baseline percentile context. Replaces the daily qualitative rediscovery.
- **Play classification: `flow_intent` + `horizon`** (June 2026, revised) —
  every play declares what its flow IS (`DIRECTIONAL` / `VOLATILITY` / `HEDGE` /
  `SYNTHETIC STOCK`) and the maturity of its cited evidence (event / tactical /
  medium / strategic). `flow_intent` is a classification, **not** a confidence
  cap — all four are valid plays and confidence is scored separately on evidence
  quality (framework Step 5 rubric: flow/dealer/price/vol/catalyst → 0–100,
  intent-weighted — Price-heavy for DIRECTIONAL, Vol-heavy for VOLATILITY). The
  earlier design gated confidence by type (only directional could be high) and
  lumped all views into one `VIEW` value; that collapsed two axes and was
  dropped. Horizon must still contain the thesis
  (1-DTE clusters can no longer anchor multi-week calls). Folded into the play
  cell's bracket line (`flow_intent` upper-cased) — no sheet-schema change.
- **Persistence surfaced by default** (June 2026) — pipeline `DEFAULT_DAYS`
  1 → 5 so every run sees the trailing week, and the persistence section leads
  with a **Persistent names (≥3 days)** callout.
- **VIX term structure snapshot** (June 2026) — `lib/vol_snapshot.py` pulls four
  CBOE indices from yfinance (`^VIX`/`^VIX9D`/`^VIX3M`/`^VVIX`) and derives
  `term_ratio` (VIX/VIX3M; >1 → backwardation) and `event_ratio` (VIX9D/VIX;
  >1 → near-term event vol elevated). The pipeline fetch injects a compact
  markdown section into the rollup; soft-fail with a daily cache
  (`.cache/vol_snapshot_YYYY-MM-DD.json`). This is the free, history-trivial
  first slice of the forward vol layer (item 2) — per-name IV rank / term / skew
  remain deferred on the IV-history blocker. SPX skew is omitted (needs the
  options chain).

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

### 2. Forward-looking vol layer (PARTIAL — VIX term structure shipped; per-name IV deferred)

The organizing principle when this layer lands: **flow → thesis, then
volatility → structure.** Today the structure choice (spread vs naked vs
straddle, strike width) is derived from the same flow that produced the
thesis, which conflates two decisions. Flow should pick the name and the
direction; expected move, IV rank, and skew should pick the structure and the
strikes. Until the vol data exists, the method files' defined-risk default is
the stand-in.

The genuinely forward signals for play selection, in rough priority:

- ~~**IV rank / percentile** (per name) — where today's IV sits in its own trailing
  range. The single most useful "rich or cheap" read.~~ — **SHIPPED July 2026** as
  the `IVpct` column (`lib/barchart_iv_history.py` + `scripts/fetch_iv_percentile.py` →
  enriched onto the compiled flow file). Source: Barchart's **options-overview history** page carries
  a per-date IV percentile series up to ~2 years, so the "no historical series"
  blocker below turned out not to apply — no self-logging needed. Drives the TF-vs-TF-S
  structure choice (framework Step 4).
- ~~**VIX term structure** (VIX vs VIX3M/VIX9D)~~ — **SHIPPED June 2026**
  (`lib/vol_snapshot.py`, see Shipped above). Forward market-wide vol regime;
  backwardation = acute near-term fear that tends to mean-revert.
- **IV term structure** (front vs back month) and **skew** (put vs call IV) per
  name — forward measures of stress and directional/crash demand.

**Data caveat (the blocker):** barchart.com displays IV rank and VIX term
structure **live only — no historical series.** Split by feasibility:

- ~~**VIX term structure history is actually free** via yfinance indices~~ —
  **DONE** (`lib/vol_snapshot.py` pulls `^VIX`/`^VIX9D`/`^VIX3M`/`^VVIX` and
  injects the snapshot into the rollup).
- ~~**Per-name IV rank history is the hard part**~~ — **RESOLVED July 2026.** It
  turned out Barchart's **options-overview history** page (`…/options-history`, a
  Premier feature) exposes a per-date IV / IV-rank / IV-percentile series up to ~2
  years — a full historical series, not live-only. `scripts/fetch_iv_percentile.py`
  scrapes it per ticker (windowed to the trade date) and enriches the as-of-date
  values onto the compiled flow file, so neither a paid vendor nor self-logging was
  needed. (The IV *term structure* / skew per name is
  still not built.)

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

### 5. Delta-adjusted notional, and greeks for the vol read — SHIPPED June 2026

`ΔNot$` (signed `Delta × Size × 100 × underlying`) and `Fin%` now ship in the
rollup, and the score's `flow` component ranks extrinsic premium so a deep-ITM
strike cannot buy rank with intrinsic-inflated premium — see Shipped above.
What remains deferred (with the vol layer, item 2): **greeks for the
buy-vs-sell-vol read.** Gamma/vega are ~0 deep ITM and not in the feed; they
are informative for ATM/OTM prints and would need a Black-Scholes calc (all
inputs — S, K, DTE, IV — are in the feed).

### 6. DTE as a first-class feature — SHIPPED June 2026

Per-ticker `Hzn` column (dominant DTE bucket by extrinsic premium) ships in the
rollup, and every play declares a `horizon` field — see Shipped above. As
designed, the buckets do not enter the numeric score.

### 7. Next-day OI delta — open vs close confirmation — SHIPPED & CONSUMED (July 2026)

The `*` opening label (`To Open` / `BuyToOpen` / `SellToOpen`, from
`size > OI + vol − size`) is a same-day *estimate* of opening activity. The
**actual** confirmation is the strike's **open-interest change the next session**:
OI up ≈ genuinely opening; OI flat/down ≈ closing or rolling.

`scripts/enrich_oi.py` computes per-contract `oi_change` (D+1 OI − D OI), and
`_finalize_oi_factors` (`lib/flow_summary/core.py`) rolls it up per ticker into
`oi_confirm_pct = opens / (opens + closes)` (flat ΔOI excluded from the
denominator — a no-change day is ambiguous, not a failed confirmation) with an
`oi_n` sample count. **As of July 2026 this feeds the conviction score**: the
`OIConfirm` component adds +2/+1 for high open-confirmation and −1/−2 for low
(the TODO-P3 `OIConfirm<40%` underperformance), neutral when absent or when
`oi_n < 3`. Because enrichment lags one session, the *latest* live date scores
0 here — the signal is fully present only on backfilled / backtested dates.
Bands are tunable; retune from the attribution backtest. See
`config/conviction-score.md`.

Remaining (optional): a per-strike (rather than per-ticker) confirmation view in
the `--days N` persistence output.

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

### 9. Spot-price grounding for play levels (near-term, cheap, high value)

Every trigger and invalidation level is currently reverse-engineered from
strike clustering — the model has no actual spot. That is the root cause of
strike/trigger incoherence (e.g. the 2026-06-10 WULF play: 16/20 call spread
with a "holds 24, breaks 26" trigger — one set of numbers had to be wrong).
The method file's coherence check helps, but the model is still inferring spot
from prints. Fix: fetch the last price for the top-scored names (yfinance, one
number per ticker) into the rollup so strikes, triggers, and invalidations all
anchor to a verified spot. Shares the yfinance OHLC fetch with item 3 — build
them together behind the same `--context`-style enrichment.

### 10. Play validity window — staleness handling (near-term, contract-only)

Analysis often runs T+1 evening: a full session has passed since the snapshot,
so "loses 722 on a daily close" may have already triggered or invalidated
before the row is written. The backtest sidesteps this with its own entry
matching, but for live use each play should carry an explicit entry-validity
window (e.g. "valid for entry through T+3") in the contract, and the method
files should state what a trigger means when N sessions have already elapsed.
Cheapest fix is a contract field + method-file rule; the alternative
(same-evening runs) is an ops change, not an analysis change.

### 11. Earnings / catalyst calendar (near-term, cheap)

`[CAT]` tags are currently inferred from flow shape ("front-week contracts
present implying an event") when earnings dates are a free deterministic
lookup (yfinance). Inject next-earnings-date for top-scored names into the
rollup so catalysts are facts, the DTE-vs-catalyst matching rule can actually
bind, and IV richness can be read against a known event date.

### 12. Cross-engine agreement as a signal (cheap, uses what we already pay for)

Claude and Codex analyze the same data independently and the results are never
compared. Agreement on a name and direction between independent engines is
corroboration — arguably stronger than several rungs of the single-engine
ladder — and it is currently discarded. Cheapest form: a post-run diff of the
day's AnalysisClaude vs AnalysisGPT rows (ticker ∩ direction), printed with the
run report and/or written as a flag column. Later, the backtest can test
whether agreed plays actually outperform single-engine plays (see alpha
attribution).

### 13. Two-axis scoring — directional vs hedging pressure (medium, builds on the conviction score)

The rollup's conviction score is deliberately direction-agnostic, and the
method files handle the hedge/directional distinction qualitatively ("QQQ
isn't bearish, QQQ is heavily hedged"). The numeric version would split each
ticker's flow into a **directional score** and a **hedging score**: downside
flow on index/credit ETFs and ask-side puts on broad proxies load the hedging
axis; single-name flow with opening labels, Vol/OI, and strike/DTE coherence
loads the directional axis. Two numbers per ticker in the rollup table lets
the LLM (and later the backtest) distinguish "the market is bearish" from
"the market is hedged" mechanically instead of by prose discipline. Sits
naturally on the existing scoring code in the rollup; no new data needed.

### 14. Theme table — cross-ticker narrative aggregation — SHIPPED July 2026

Group the day's signals into themes (e.g. long AI: MSFT/AMD/NVDA; risk-off
hedge: SPY/QQQ/IWM; duration bid: TLT) and emit a theme → supporting-tickers
table with a **breadth** count. Makes the day's story auditable at a glance
and gives the regime sentence its evidence trail.

Now a live output: the model emits a market-level `themes` array —
`[{ theme, tickers, breadth, read }]` — per framework Step 5b
(`config/analysis-framework.md`) and both method files. Presentation-only, as
designed: it never multiplies or otherwise changes a play's `score`.

**Caveat that must be built in:** correlated agreement is not corroboration.
MSFT/AMD/NVDA call flow is one AI trade expressed three times — the same desks
and the same macro — exactly like the SPY/QQQ/IWM triple hedge the method
files already collapse. So the output is *theme breadth* (how many names
express it), never a multiplied "narrative confidence" score; breadth across
genuinely independent asset classes (equity + credit + duration + metals)
counts for more than breadth within one sector.

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

- **Put/call ratio** — the market-level aggregate (by premium, Size, and count,
  with trailing-window percentiles) **shipped** with the baseline layer; what
  remains is the **per-ticker** version — today's C/P for a name against that
  name's own history, which needs per-ticker daily rows (a `ScoredRollupDaily`
  archive tab fed by `fetch_scored_csv` would supply it).
- **Gamma / dealer-gamma exposure (GEX)** — needs a Black-Scholes greeks calc
  (inputs S/K/DTE/IV all in the feed; see item 5). Per-strike and per-name gamma,
  and a market-wide GEX read for the regime layer. GEX is also the **second gate
  for structure selection in TF plays** (framework Step 4): positive dealer gamma
  → slow grinder → credit spread (TF-S); negative dealer gamma → momentum /
  breakout → debit (TF). Until GEX ships, the vol snapshot (contango + stable
  L-VOL + no E-VOL + no catalyst) is the proxy gate. Backtest evidence: BULL
  market plays with debit structures show near-zero MFE and −68% realized/MFE
  capture — the slow-grinder problem that TF-S is designed to fix.
- **IV features** — IV rank/percentile **SHIPPED** as `IVpct` (scraped from
  Barchart's options-overview history, July 2026 — see item 2 above; the "IV
  history" blocker didn't apply). Term structure and skew (put vs call IV) per name
  remain deferred.
- The already-scoped quant features that belong in this layer: summed Size +
  delta-adjusted notional (items 1, 5), DTE bucketing (item 6), spread-leg flags
  (item 8). Next-day OI delta (item 7) is **already in this layer** — it feeds the
  conviction score as the `OIConfirm` component (July 2026).

This is "a lot more features to go through" — they accrete into `lib/flow_summary/`
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
- **Group by score band and pattern code too.** PARTIALLY ANSWERED 2026-07-08:
  the retired high/medium/low labels were audited across the 292-row v1 backtest
  set and **did not discriminate** — share of plays reaching +30% MFE: high 68% /
  medium 72% / low 77% (realized win rate 57/56/62%). That is the baseline the
  numeric `score_total` redesign must beat, and the reason its validation is
  load-bearing: every backtested row predates the scoring redesign, so the
  `score_total`/`score_*` columns in `backtests/results.csv` are still entirely
  empty. **Validation recipe (no new infrastructure):** the score columns are
  already joined onto analysis rows at row-expansion and flow through to
  BacktestResults — once enough post-redesign dates are backtested, group
  realized P&L and MFE-basis worked-rate by `score_total` band (<40 / 40–69 /
  ≥70) straight off the results CSV. Pattern-code attribution remains open
  (2026-07-08 distribution note: TF = 73% of all plays; VC/DP ≈ zero pending the
  GEX input; GE weak on MFE in the current window at n=8).
- **Continuously re-check that alpha is still there.** The analysis is a live
  hypothesis, not a settled method — realized P&L must feed back. Add a standing
  step (and a note in the method file) to periodically run the attribution backtest,
  compare current alpha by source against its own history, and flag decay. A phase
  that stops beating the baseline gets demoted; the method file gets updated from
  what the backtest shows, not from intuition.
