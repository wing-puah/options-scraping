from pathlib import Path

RESULTS_PATH = Path(__file__).resolve().parent.parent.parent / "backtests"
HISTORY_CACHE = RESULTS_PATH / "option_history_cache"

_EXPIRATION_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d")

_UNSUPPORTED_PATTERNS = (
    "condor",
    "strangle", "straddle", "calendar", "diagonal",
    "covered",
    "butterfly",
)
