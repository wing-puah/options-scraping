import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))                          # lib.*
sys.path.insert(0, str(_ROOT / "scripts"))              # compile_flow, backtest.*, etc.
sys.path.insert(0, str(_ROOT / "scripts" / "collector"))  # scrape_flow, enrich_oi, fetch_*

# Env vars the production code reads as a FALLBACK when a caller passes nothing,
# and which the operator's real `.env` supplies. `scripts/journal/__main__.py`
# calls `load_dotenv()` at import, so importing it anywhere in the session leaks
# the operator's real values into `os.environ` for every test that runs after —
# and a test asserting "absent means None" then passes or fails depending on
# whose machine it runs on. Cleared per-test so the default path is always the
# unconfigured one; a test that wants a value sets it with `monkeypatch.setenv`,
# which runs after this fixture and therefore still wins.
_ENV_FALLBACKS = (
    "JOURNAL_NET_LIQUIDATION",
    "IBKR_ACCOUNT_ID",
    "IBKR_FLEX_TOKEN",
    "IBKR_FLEX_QUERY_ID",              # legacy; scrubbed while the fallback lives
    "IBKR_FLEX_QUERY_TRADES_ID",
    "IBKR_FLEX_OPEN_POSITIONS_QUERY_ID",
    "TRADE_JOURNAL_SPREADSHEET_ID",
)


@pytest.fixture(autouse=True)
def _isolate_operator_env():
    saved = {k: os.environ.pop(k, None) for k in _ENV_FALLBACKS}
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
