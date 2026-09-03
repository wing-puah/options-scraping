"""
Options flow analysis pipeline (script-first, model-agnostic).

The sole entry point for producing an analysis. Run it as a module:

    python3 -m scripts.analysis_pipeline                  # latest date, claude → AnalysisClaude
    python3 -m scripts.analysis_pipeline --date 2026-04-21 --dry-run

User-tunable settings (engines, models, tabs, retries, defaults, prompt
contract) live in `config.py`. Implementation lives in `core.py`.
"""
from .config import ANALYSIS_PROMPT_CONTRACT, ENGINES, EngineConfig, ROW_COLUMNS
from .core import (
    _RUNNERS,
    _dates_to_process,
    _extract_json,
    _strip_output_section,
    analysis_to_rows,
    build_prompt,
    main,
    run_engine,
    write_local_output,
)

__all__ = [
    "ANALYSIS_PROMPT_CONTRACT", "ENGINES", "EngineConfig", "ROW_COLUMNS",
    "_RUNNERS", "_dates_to_process", "_extract_json", "_strip_output_section",
    "analysis_to_rows", "build_prompt", "main", "run_engine", "write_local_output",
]
