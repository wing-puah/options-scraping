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


ENGINES: dict[str, EngineConfig] = {
    "claude": EngineConfig(
        method_file=ROOT / "config/analysis-methods/claude.md",
        tab="AnalysisClaude",
        default_model="opus",
    ),
    "codex": EngineConfig(
        method_file=ROOT / "config/analysis-methods/codex.md",
        tab="AnalysisGPT",
        default_model=None,  # fall back to Codex's configured default model
    ),
}

DEFAULT_ENGINE = "claude"


# ──────────────────────────── Run behaviour ────────────────────────
MAX_ATTEMPTS = 3            # retries for the headless analysis call on failure / bad JSON
REQUEST_TIMEOUT_S = 600     # per-attempt timeout (seconds) for the engine CLI


# ──────────────────────────── Fetch defaults ───────────────────────
DEFAULT_TOP_N = 75          # top-N raw trades per section included alongside summaries
DEFAULT_DAYS = 5            # persistence window — a name recurring across sessions
                            # outweighs a one-day print, so the default run sees the
                            # trailing week (1 = today only, no persistence section)


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
    "invalidation", "data_window_start", "data_window_end",
    "created_datetime",
]


# ──────────────────────── Model output contract ────────────────────
# The JSON the engine must return. Replaces the framework's flat "## Output
# Format" tail (stripped in core.py) so plays come back structured and can be
# expanded into one sheet row per ticker without parsing free text.
#
# Coupled to analysis_to_rows() in core.py: the `plays` item keys
# (ticker/asset_class/pattern/regime/signal/structure/thesis/trigger/invalidation/confidence/signal_type/horizon/alternative_interpretation)
# are read there, so keep them in sync if you edit this. Coverage minimums are
# MIN_STOCK_PLAYS / MIN_ETF_PLAYS above — keep the prose below in sync with them.
ANALYSIS_PROMPT_CONTRACT = """
## Output

Respond with a single JSON object and NOTHING else — no prose, no markdown
fences. Do not use any tools; everything you need is in this prompt.

Schema (all string fields unless noted):

{
  "regime": "Directional + Volatility + Sentiment labels (+ Macro only if cross-asset corroborated) and a one-sentence read. E.g. BEAR + H-VOL + RISK-OFF — elevated VIX, broad index put hedging.",
  "signals": "Market-level tagged signals, pipe-separated — cross-asset/macro patterns ONLY (e.g. index hedging, vol regime, sector rotation). Per-ticker evidence belongs in each play's `signal` field, not here. E.g. [FLOW] broad index put hedging across SPY/QQQ/IWM | [VEGA] VIX call buying 35-40 | [MACRO] dollar bid risk-off.",
  "sector_focus": "Sectors/names with concentrated flow and what it implies.",
  "plays": [
    {
      "ticker": "NVDA",
      "asset_class": "stock|etf",
      "pattern": "HP|RF|VE|SH|DC|MS",
      "regime": "Ticker-specific regime — the volatility / level / posture state for THIS name (e.g. 'BULL + E-VOL — testing 59 breakout, IV30 rising into earnings'). Distinct from the market regime. Leave EMPTY if there is nothing ticker-specific to add beyond the market read — do NOT copy the market regime here.",
      "signal": "Ticker-specific tagged evidence supporting THIS play, pipe-separated. E.g. [FLOW] $10.3M calls vs $0.9M puts | [FLOW] 53x Vol/OI unusual print | [FLOW] explicit ToOpen/BuyToOpen $64 calls | [PRICE] testing breakout at 59. Distinct from the market-level `signals` — this is the per-ticker evidence chain.",
      "structure": "e.g. bull call spread 185/200",
      "thesis": "one sentence",
      "trigger": "what must happen after the snapshot to enter",
      "invalidation": "specific price level / flow reversal / macro condition",
      "confidence": "high|medium|low",
      "signal_type": "REQUIRED, one of directional|hedge|positioning|volatility|financing — what the underlying flow IS, kept separate from how tradeable it is. directional = a genuine view on price (OTM/ATM, opening, horizon matches a thesis); hedge = protection on an existing book (index/sector puts under a bid tape); positioning = exposure management / stock replacement with a directional residue; volatility = gamma/event flow (0-14 DTE clusters, straddle-ish) with no durable direction; financing = conversions / deep-ITM stock-substitute premium — not a market view at all.",
      "horizon": "REQUIRED, one of event|tactical|medium|strategic — the maturity of the play's CITED evidence, per the DTE table: 0-14 DTE event, 15-60 tactical, 60-180 medium, 180+ strategic. Use the dominant bucket of the prints the signal cites (the rollup's Hzn column precomputes this per ticker).",
      "alternative_interpretation": "REQUIRED. The strongest benign reading of the SAME flow — what else this print could be other than the directional thesis above. Choose from (or combine): covered-call sale, long-call liquidation, short-call open, short-call close, delta hedge, convertible-bond hedge (e.g. MSTR), dealer adjustment, structured-product mechanics, portfolio insurance on an existing long, expiry rolling, multi-leg spread leg, adjusted-options / stale-strike feed artifact. Cite the specific evidence that lets you reject this reading — if you cannot, the play is positioning, not a directional bet: downgrade confidence to 'low' or drop the play. One sentence."
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
  If conviction is thin, still meet the minimums but label those ideas
  confidence "low" rather than dropping them. Never fabricate a ticker that does
  not appear in the fetched data — if a section genuinely lacks enough distinct
  names, return what the data supports and note the shortfall in `sector_focus`.

Discipline rules — apply to every play before promoting to medium / high confidence:

- `alternative_interpretation` is REQUIRED on every play, not optional. It is
  the auditable record that the benign-explanation check was performed. A play
  whose `alternative_interpretation` is at least as plausible as the directional
  thesis must be downgraded to 'low' or dropped — do not bury the conflict.
- `signal_type` gates confidence: only 'directional' plays may carry 'high'
  confidence. 'hedge' and 'positioning' plays cap at 'medium' and their thesis
  must be framed as protection/positioning, not a price forecast. 'volatility'
  plays cap at 'low' unless the structure itself is a vol trade (straddle/
  strangle). 'financing' flow is not a play — use it only to flag that a name's
  headline premium is polluted, or drop it.
- `horizon` must be consistent with the thesis: an 'event' horizon (0-14 DTE
  evidence) cannot support a multi-week directional thesis — either find longer-
  dated corroboration or downgrade to 'low' and call it gamma/event flow.
- For bid-side calls and ask-side puts WITHOUT a `SellToOpen` / `BuyToOpen` label,
  the play's `signal` must cite what rules out the closing / overwrite / hedge
  reading. Without that citation, confidence is 'low' at best.
- For structurally polluted underlyings — convertible-bond hedge names (e.g.
  MSTR), BDCs / covered-call ETFs, structured-product underlyings, miners
  traded as crypto proxies, levered or inverse ETFs — the play's `signal` MUST
  cite cross-asset confirmation (BTC / IBIT / COIN / miners for MSTR; the
  underlying index for a levered ETF; the underlying commodity or crypto for a
  miner). Without that confirmation, mark confidence 'low' and frame the entry
  as positioning, not a directional bet.
- For any strike implausibly far from spot for its DTE (e.g. >50% away with
  <60 DTE), do not let the print anchor a directional claim — `ToOpen` at an
  impossible strike is almost always a feed artifact, not a bet. Either exclude
  the print or use the play to flag the anomaly.
"""
