"""
User-tunable settings for the options analysis pipeline.

This is the one file to edit when you want to change *how* the pipeline behaves —
which engines exist, their models, where results are written, retry/timeout
limits, the default fetch window, and the JSON contract handed to the model. The
pipeline logic lives in `core.py` and imports these values; it should not need
editing for routine configuration changes.
"""
from dataclasses import dataclass
from pathlib import Path

# Repo root (…/options-trading), derived from this file's location.
ROOT = Path(__file__).resolve().parent.parent.parent


# ───────────────────────────── Engines ─────────────────────────────
# The pipeline is model-agnostic. Each engine runs the analysis as an isolated
# headless CLI call, reads its own model-specific method file (layered on the
# shared framework), and writes its own Google Sheets tab.
#
# To add an engine: add an entry here AND a matching runner in core.py
# (`_RUNNERS`) that knows how to invoke its CLI.

@dataclass(frozen=True)
class EngineConfig:
    method_file: Path           # model-specific judgment doc, layered on the framework
    tab: str                    # Google Sheets tab this engine appends to
    default_model: str | None   # used when --model is omitted; None = let the CLI decide
    fallback_model: str | None = None  # used on retry attempts 2+ when default_model set


ENGINES: dict[str, EngineConfig] = {
    "claude": EngineConfig(
        method_file=ROOT / "config/analysis-methods/claude.md",
        tab="AnalysisClaude",
        default_model="claude-opus-4-8",
    ),
    "codex": EngineConfig(
        method_file=ROOT / "config/analysis-methods/codex.md",
        tab="AnalysisGPT",
        default_model=None,  # fall back to Codex's configured default model
    ),
}

DEFAULT_ENGINE = "claude"

# Ticker-focused runs (--tickers) write here instead of the engine's daily tab,
# so focused one-off analyses never mix with the full-market daily runs that
# backtest.py / `/options summary` read. Auto-created by sheets_client.append_rows.
TICKER_SPECIFIC_TAB = "AnalysisTickerSpecific"


# ──────────────────────────── Run behaviour ────────────────────────
MAX_ATTEMPTS = 3            # retries for the headless analysis call on failure / bad JSON
REQUEST_TIMEOUT_S = 600     # per-attempt timeout (seconds) for the engine CLI


# ──────────────────────────── Fetch defaults ───────────────────────
DEFAULT_TOP_N = 20          # top-N tickers by score to show raw trades for
DEFAULT_RAW_N = 20          # raw trade rows per ticker (top N by premium)
# persistence window — outweighs a one-day print; default run sees the trailing week
# (1 = today only, no persistence section)
DEFAULT_DAYS = 5


# ──────────────────────── Play coverage targets ────────────────────
# Minimum plays the contract asks each run to return, split by asset class, on
# top of the always-present market read (regime/signals/sector_focus). The
# pipeline logs a non-fatal warning when a run comes back short — it never blocks
# a write, since thin days legitimately yield weaker setups.
MIN_STOCK_PLAYS = 5
MIN_ETF_PLAYS = 3

# Shared analysis vocabulary/framework, layered under each engine's method file.
FRAMEWORK_FILE = ROOT / "config/analysis-framework.md"


# ──────────────────────────── Sheets schema ────────────────────────
# Column order MUST match the AnalysisClaude / AnalysisGPT header exactly —
# sheets_client.append_rows writes values positionally, and backtest.py reads
# these names. Changing this means also updating the sheet header AND
# analysis_to_rows() in core.py.
ROW_COLUMNS = [
    "date", "ticker", "regime", "signal", "play",
    # `horizon` (14|60|180|720 DTE bucket) is deliberately mid-schema — right
    # beside `play` — so it reads at a glance and the backtest can pull it off a
    # dedicated column instead of regex-scraping the play bracket. Because
    # append_rows writes positionally, this insertion required a one-time sheet
    # migration (scripts/migrate_tab_columns.py) to shift existing rows.
    "horizon",
    "trigger",
    "invalidation", "data_window_start", "data_window_end",
    "created_datetime",
    # Per-ticker flow-rollup context joined from that date's audit/<date>-rollup.csv
    # at row-expansion time (NOT produced by the LLM — deterministic, kept separate
    # from the model's `signal` evidence). Grouped together at the END so existing
    # tab rows stay column-aligned. See ROLLUP_METRIC_COLS / analysis_to_rows().
    "oi_confirm_pct", "cpir", "iv_spread", "iv_skew", "iv_pct",
    # Model evidence-quality score, exposed as its component breakdown (framework
    # Step 5) so each factor can be measured against realized P&L and pruned. These
    # replace the old high/medium/low `confidence` band. Appended at the END (after
    # the rollup block) per the append-at-end convention — only the header needed
    # extending, no row shift. `score_total` is summed in code, not model-produced.
    "score_total", "score_flow", "score_dealer", "score_price", "score_vol",
    "score_catalyst",
]

# Analysis-row key -> `score` sub-field (framework Step-5 factor). The model emits
# the five component points; analysis_to_rows sums them into `score_total`.
SCORE_COMPONENT_COLS = {
    "score_flow": "flow",
    "score_dealer": "dealer",
    "score_price": "price",
    "score_vol": "vol",
    "score_catalyst": "catalyst",
}

# Analysis-row key -> scored-rollup CSV column (lib/flow_summary FLOW_CSV_COLUMNS).
# These are joined onto each play row by ticker so the entry-day flow evidence is
# stored alongside the play (and read back by the backtest) rather than living only
# in the transient audit file. See config/rollup-reference.md for definitions.
ROLLUP_METRIC_COLS = {
    "oi_confirm_pct": "OIConfirmPct",
    "cpir": "CPIR",
    "iv_spread": "IVSpread",
    "iv_skew": "IVSkew",
    "iv_pct": "IVPct",
}


# ──────────────────────── Model output contract ────────────────────
# The JSON the engine must return. Replaces the framework's flat "## Output
# Format" tail (stripped in core.py) so plays come back structured and can be
# expanded into one sheet row per ticker without parsing free text.
#
# Coupled to analysis_to_rows() in core.py: the `plays` item keys
# (ticker/asset_class/pattern/regime/signal/structure/thesis/trigger/invalidation/
# score/flow_intent/horizon/alternative_interpretation) and the market-level
# `themes` key are read there, so keep them in sync if you edit this. `score` is a
# structured object of the five Step-5 factors (it replaced the old high/medium/low
# `confidence` string). Coverage minimums are MIN_STOCK_PLAYS / MIN_ETF_PLAYS
# above — keep the prose below in sync with them.
ANALYSIS_PROMPT_CONTRACT = """
## Output

Respond with a single JSON object and NOTHING else — no prose, no markdown
fences. Do not use any tools; everything you need is in this prompt.

Schema (all string fields unless noted):

{
  "regime": "Directional + Volatility + Sentiment labels (+ Macro only if cross-asset corroborated, + HP qualifier when the broad tape is at/near highs while large downside hedging accumulates) and a one-sentence read. HP is a market-condition qualifier here, NOT a per-play setup. E.g. BULL + C-VOL + RISK-OFF + HP — indexes near highs but broad index put hedging dominates premium.",
  "signals": "Market-level tagged signals, pipe-separated — cross-asset/macro patterns ONLY (e.g. index hedging, vol regime, sector rotation). Per-ticker evidence belongs in each play's `signal` field, not here. E.g. [FLOW] broad index put hedging across SPY/QQQ/IWM | [VEGA] VIX call buying 35-40 | [MACRO] dollar bid risk-off.",
  "sector_focus": "Sectors/names with concentrated flow and what it implies.",
  "themes": [
    {
      "theme": "short thematic label, e.g. 'AI semis' or 'downside index hedging'",
      "tickers": ["NVDA", "AMD", "SMH", "SOXX"],
      "breadth": "integer — count of INDEPENDENT names expressing the theme",
      "read": "one line — what the cluster's flow implies"
    }
  ],
  "plays": [
    {
      "ticker": "NVDA",
      "asset_class": "stock|etf",
      "pattern": "TF|MR|GE|VC|PU|DP — the playbook (Step 2). TF (trend following) and GE (gamma expansion) bias WITH the trend/breakout direction; MR (mean reversion) bias OPPOSITE the extension; PU (positioning unwind) bias WITH the unwind direction; VC (volatility compression) and DP (dealer pinning) are non-directional. HP is NOT a value here — it lives in the market regime. The `structure` direction MUST match this playbook's bias.",
      "regime": "Ticker-specific regime — the volatility / level / posture state for THIS name (e.g. 'BULL + E-VOL — testing 59 breakout, IV30 rising into earnings'). Distinct from the market regime. Leave EMPTY if there is nothing ticker-specific to add beyond the market read — do NOT copy the market regime here.",
      "signal": "Ticker-specific tagged evidence supporting THIS play, pipe-separated. E.g. [FLOW] $10.3M calls vs $0.9M puts | [FLOW] 53x Vol/OI unusual print | [FLOW] explicit ToOpen/BuyToOpen $64 calls | [PRICE] testing breakout at 59. Distinct from the market-level `signals` — this is the per-ticker evidence chain.",
      "structure": "Option structure from the two-layer table (Step 4): playbook fixes the bias, IV picks aggressive/moderate/conservative. Bullish: long call / call spread / short put. Bearish: long put / put spread / short call. Vol expansion: straddle / strangle / calendar. Vol compression or DP: short strangle / iron condor / butterfly. TF/MR with time-structure edge: diagonal spread or calendar. TF-S (trend following, SLOW grind: high IVpct + positive-gamma/contango, no catalyst) takes a CREDIT spread (bull put if bullish, bear call if bearish) NOT a debit. e.g. bull call spread 185/200",
      "thesis": "one sentence",
      "trigger": "what must happen after the snapshot to enter",
      "invalidation": "specific price level / flow reversal / macro condition",
      "score": {
        "flow": "integer — flow-confirmation points (repetition/clustering, cross-dataset overlap, extrinsic-premium concentration). Max 25 for DIRECTIONAL/HEDGE/SYNTHETIC STOCK, 20 for VOLATILITY.",
        "dealer": "integer — dealer-alignment points (dealer gamma supports the play). Max 25.",
        "price": "integer — price-confirmation points (key level held/broken with follow-through). Max 20 for DIRECTIONAL/HEDGE/SYNTHETIC STOCK, 10 for VOLATILITY.",
        "vol": "integer — vol-alignment points (IV/term structure/skew fit the structure). Max 15 for DIRECTIONAL/HEDGE/SYNTHETIC STOCK, 25 for VOLATILITY.",
        "catalyst": "integer — catalyst-support points (a dated catalyst within the horizon corroborates). Max 15 for DIRECTIONAL/HEDGE/SYNTHETIC STOCK, 20 for VOLATILITY. Do NOT return a total — the five are summed downstream to a 0-100 score."
      },
      "flow_intent": "REQUIRED, one of DIRECTIONAL|VOLATILITY|HEDGE|SYNTHETIC STOCK — what the flow IS. A classification, not a tradeability cap; each intent carries its own score. DIRECTIONAL = a bet price moves a particular way (extrinsic-heavy, opening, no offsetting book; playbook TF/MR/GE/PU; invalidated by a price level). VOLATILITY = a bet on the size of the move / implied vol, direction-agnostic (straddle/strangle/condor/calendar; playbook VC/DP; invalidated by IV collapse or decay without a move). HEDGE = protection on an existing book (index/sector puts under a bid tape, collars) — the defining feature is the offsetting position protected; framed as protection, never a forecast. SYNTHETIC STOCK = mechanical deep-ITM (~1.0 delta) exposure, conversions, stock-replacement, boxes — mostly intrinsic, a soft tell; strip intrinsic before ranking. DIRECTIONAL vs VOLATILITY follows the playbook + structure; opening-view vs HEDGE turns on whether an offsetting underlying position is protected. Bid-side calls / ask-side puts without a ToOpen label read as HEDGE or SYNTHETIC STOCK until evidence shows new risk opened.",
      "horizon": "REQUIRED, one of 14|60|180|720 — the DTE bucket boundary of the dominant expiry in the play's CITED evidence: ≤14 DTE → 14, 15–60 DTE → 60, 61–180 DTE → 180, 181+ DTE → 720. Use the dominant bucket of the prints the signal cites (the rollup's Hzn column precomputes this per ticker).",
      "alternative_interpretation": "REQUIRED. The strongest benign reading of the SAME flow — what else this print could be other than the directional thesis above. Choose from (or combine): covered-call sale, long-call liquidation, short-call open, short-call close, delta hedge, convertible-bond hedge (e.g. MSTR), dealer adjustment, structured-product mechanics, portfolio insurance on an existing long, expiry rolling, multi-leg spread leg, adjusted-options / stale-strike feed artifact. Cite the specific evidence that lets you reject this reading — if you cannot, the play is positioning, not a directional bet: score it low (zero price+catalyst, total under 40) or drop the play. One sentence."
    }
  ]
}

Coverage — every run must return BOTH a market read and a full play list:

- Market read: always fill `regime`, `signals`, AND `sector_focus`. Together
  they are the market analysis; none may be blank.
- Plays: return AT LEAST 5 stock plays (asset_class "stock") and AT LEAST 3 ETF
  plays (asset_class "etf") — 8+ total — ordered strongest conviction first.
  Draw the names from the highest-scoring tickers in the fetched data; stock
  plays from the stock flow/unusual sections, ETF plays from the ETF sections.
  If conviction is thin, still meet the minimums but score those ideas low
  (small components, total well under 40) rather than dropping them — never
  inflate a thin idea's score to look tradeable. Never fabricate a ticker that
  does not appear in the fetched data — if a section genuinely lacks enough
  distinct names, return what the data supports and note the shortfall in
  `sector_focus`.

Discipline rules — apply to every play before awarding it a strong score:

- Playbook–structure binding (validity gate, not a score gate): the `structure`
  direction MUST match the `pattern` bias. TF/GE (directional with trend) take ONLY
  structures aligned with the breakout direction; MR takes ONLY structures opposite
  the extension; PU takes ONLY structures aligned with the unwind direction; VC/DP
  are non-directional (condor / strangle / butterfly). A mismatched pair — e.g.
  `MR | bull call spread` on a name in an uptrend — is invalid output: pick the
  playbook that matches the directional thesis, never the reverse. Within the
  playbook's bias, IV chooses aggressive/moderate/conservative — sell premium
  (credit) into high IV, buy premium (debit) into low/rising IV. Read the
  per-ticker **IVpct** column (0-100 percentile of the name's IV in its OWN
  trailing range — the "rich vs cheap" read that normalises across names; blank
  when history is thin, then fall back to the market VIX proxy). HIGH IVpct
  (>=70) on a trend name in a slow, positive-gamma grind is the TF-S case → use a
  CREDIT spread (bull put / bear call), not a debit — a debit into rich IV buys
  premium a slow move can't overcome. LOW IVpct (<=30) → IV is cheap → debit /
  long premium (TF). Default to defined-risk spreads; naked calls or puts require
  very low IV + a very high score.
- `alternative_interpretation` is REQUIRED on every play, not optional. It is
  the auditable record that the benign-explanation check was performed. A play
  whose `alternative_interpretation` is at least as plausible as the directional
  thesis must be scored low (zero the price+catalyst factors, total under 40) or
  dropped — do not bury the conflict.
- `flow_intent` is a classification, NOT a score cap. Label it correctly
  and let the score float on evidence quality. HEDGE and SYNTHETIC STOCK are
  valid plays — a HEDGE framed as protection can score high; a
  DIRECTIONAL can score low. The discipline is label honesty: a hedge thesis is
  framed as protection (never a price forecast), a SYNTHETIC STOCK thesis as
  exposure (strip intrinsic, soft tell), and you must never tag protection or
  mechanical exposure as DIRECTIONAL/VOLATILITY to dodge the evidence test. Drop
  a name only when its flow is pure financing noise with nothing to say.
- `horizon` must be consistent with the thesis: short-dated evidence (≤14 DTE)
  cannot support a multi-week directional thesis — either find longer-dated
  corroboration or score it low and call it gamma/event flow.
- For bid-side calls and ask-side puts WITHOUT a `SellToOpen` / `BuyToOpen` label,
  the play's `signal` must cite what rules out the closing / overwrite / hedge
  reading. Without that citation, the score is low at best.
- For structurally polluted underlyings — convertible-bond hedge names (e.g.
  MSTR), BDCs / covered-call ETFs, structured-product underlyings, miners
  traded as crypto proxies, levered or inverse ETFs — the play's `signal` MUST
  cite cross-asset confirmation (BTC / IBIT / COIN / miners for MSTR; the
  underlying index for a levered ETF; the underlying commodity or crypto for a
  miner). Without that confirmation, score it low and frame the entry
  as positioning, not a directional bet.
- For any strike implausibly far from spot for its DTE (e.g. >50% away with
  <60 DTE), do not let the print anchor a directional claim — `ToOpen` at an
  impossible strike is almost always a feed artifact, not a bet. Either exclude
  the print or use the play to flag the anomaly.
"""


# Appended after ANALYSIS_PROMPT_CONTRACT when a run is ticker-focused
# (--tickers). It OVERRIDES the coverage section above: instead of the
# 5-stock/3-ETF minimum drawn from the highest-scoring names, the model returns
# plays ONLY for the requested tickers. `{tickers}` is filled with the list.
ANALYSIS_FOCUS_OVERRIDE = """
## Focus override (ticker-specific run)

This is a TICKER-FOCUSED run. The following overrides the Coverage section above:

- Return plays ONLY for these tickers: {tickers}.
- Return ONE play per requested ticker that has supporting flow in the fetched
  data. If a requested ticker has no usable flow, SKIP it (do not fabricate a
  play, and do not substitute a different name). The 5-stock / 3-ETF coverage
  minimums DO NOT apply here.
- Still return the full market read — `regime`, `signals`, AND `sector_focus` —
  computed from the full-market context sections (these were NOT narrowed to the
  focus tickers).
- Every play must still obey ALL discipline rules above (playbook–structure
  binding, required `alternative_interpretation`, honest `flow_intent`, horizon
  consistency, pollution checks).
"""
