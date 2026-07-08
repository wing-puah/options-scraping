"""
Barchart underlying-stock price-history URL builder.

Reuses the exact same ``core-api/v1/historical/get`` feed the option-history
scraper uses (``BarchartSession.fetch_history_csv``/``fetch_history_fast``) —
just a plain symbol instead of an encoded contract string. Parsing is shared
too: ``lib.barchart_options.parse_history_series``/``parse_history_details``
(the CSV schema is identical; bid/ask just come back blank for a stock, which
``_mark()`` already falls back on via ``Latest``).
"""
from __future__ import annotations

_BASE = "https://www.barchart.com/stocks/quotes"


def stock_history_url(symbol: str) -> str:
    """Build the Barchart price-history page URL for a plain stock symbol."""
    return f"{_BASE}/{symbol.upper().strip()}/price-history/historical"
