from pathlib import Path

RESULTS_PATH = Path(__file__).resolve().parent.parent.parent / "backtests"
HISTORY_CACHE = RESULTS_PATH / "option_history_cache"

_EXPIRATION_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d")

# Structures the backtest cannot price (they need a stock leg). Matched as bare
# substrings against the play's primary text, so they must name the STRUCTURE and
# not a word that also occurs in prose: the bare "covered" this used to hold fired
# on rationale text like "the downside deserves to be covered", which rejected a
# perfectly priceable `bear put spread 470/440` as unsupported.
_UNSUPPORTED_PATTERNS = (
    "covered call", "covered-call",
    "covered put", "covered-put",
    "covered write", "covered-write",
    "covered strangle", "covered-strangle",
    "buy-write", "buy write", "buywrite",
)
