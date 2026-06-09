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
DEFAULT_DAYS = 1            # persistence window (1 = no persistence section)

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
]


# ──────────────────────── Model output contract ────────────────────
# The JSON the engine must return. Replaces the framework's flat "## Output
# Format" tail (stripped in core.py) so plays come back structured and can be
# expanded into one sheet row per ticker without parsing free text.
#
# Coupled to analysis_to_rows() in core.py: the `plays` item keys
# (ticker/pattern/structure/thesis/trigger/invalidation) are read there, so keep
# them in sync if you edit this.
ANALYSIS_PROMPT_CONTRACT = """
## Output

Respond with a single JSON object and NOTHING else — no prose, no markdown
fences. Do not use any tools; everything you need is in this prompt.

Schema (all string fields unless noted):

{
  "regime": "Directional + Volatility + Sentiment labels (+ Macro only if cross-asset corroborated) and a one-sentence read. E.g. BEAR + H-VOL + RISK-OFF — elevated VIX, broad index put hedging.",
  "signals": "Tagged signals, pipe-separated. E.g. [FLOW] QQQ put sweeps | [VEGA] VIX call buying 35-40 | [PRICE] NVDA testing 180.",
  "sector_focus": "Sectors/names with concentrated flow and what it implies.",
  "plays": [
    {
      "ticker": "NVDA",
      "pattern": "HP|RF|VE|SH|DC|MS",
      "structure": "e.g. bull call spread 185/200",
      "thesis": "one sentence",
      "trigger": "what must happen after the snapshot to enter",
      "invalidation": "specific price level / flow reversal / macro condition"
    }
  ]
}

Return 2–5 plays, high/medium confidence only. If a day has no actionable
setup, return an empty "plays" array — do not invent one.
"""
