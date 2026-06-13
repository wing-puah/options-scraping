"""
Shared logging setup for all scripts and library modules.

Call setup_logging() once at the top of each script's main().
Library modules should only call logging.getLogger(__name__) — never configure handlers.
"""
import logging
import logging.handlers
from pathlib import Path

_LOG_DIR = Path(__file__).parent.parent / "logs"
_FMT = "%(asctime)s  %(levelname)-8s  [%(name)s.%(funcName)s]  %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%S"
_configured = False

# Third-party loggers that are too noisy at DEBUG/INFO.
_MUTE_AT_WARNING = [
    "googleapiclient",
    "google",
    "urllib3",
    "httplib2",
    "gspread",
    "playwright",
    "asyncio",
    "filelock",
    "hpack",
    "httpcore",
    "httpx",
]

# Our own logger namespaces — set to the requested level.
_OWN_LOGGERS = ["lib", "barchart_scrape", "prepare_analysis", "analysis_pipeline", "backtest"]


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configure logging for the options-trading app.

    - logs/options.log             (rotated to options.log.YYYY-MM-DD at midnight,
                                    30 days kept)
    - stderr stream handler
    - Root logger at WARNING so third-party libraries stay quiet
    - Our own loggers (lib.*, scrape, fetch, …) at `level`

    Idempotent — only the first call takes effect.
    """
    global _configured
    if _configured:
        return
    _LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # Root at WARNING — catches anything we haven't explicitly silenced.
    root = logging.getLogger()
    root.setLevel(logging.WARNING)

    fh = logging.handlers.TimedRotatingFileHandler(
        _LOG_DIR / "options.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
        utc=False,
    )
    # Rename options.log.YYYY-MM-DD → options.YYYY-MM-DD.log so editors keep syntax highlighting.

    def _log_namer(name: str) -> str:
        p = Path(name)
        # p.name is e.g. "options.log.2026-06-04"; suffix is the date part after the last dot
        parts = p.name.split(".")  # ["options", "log", "2026-06-04"]
        return str(p.parent / f"{parts[0]}.{parts[-1]}.log")
    fh.namer = _log_namer
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # Mute noisy third-party libraries.
    for name in _MUTE_AT_WARNING:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Set our own namespaces to the requested level.
    for name in _OWN_LOGGERS:
        logging.getLogger(name).setLevel(level)

    _configured = True
