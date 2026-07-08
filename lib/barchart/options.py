"""
Barchart per-contract historical option prices.

Given an option contract, builds its Barchart price-history URL and parses the
downloaded CSV into a daily price series. This is the real-data source for
backtest exits (a replacement for Black-Scholes modelling).

Contract URL format (pipe is URL-encoded as %7C):
  https://www.barchart.com/stocks/quotes/{SYMBOL}%7C{YYYYMMDD}%7C{STRIKE}{C|P}/price-history/historical

CSV columns (as of 2026):
  Time, Open, High, Low, Latest, Change, %Change, Volume, Open Int, IV, Delta,
  Gamma, Theta, Vega, Rho, Theo, Price~, Bid, Ask

Marking: we use the mid of Bid/Ask as the tradeable price, because `Latest` is a
last-trade price that goes stale on zero-volume days. Falls back to Latest.
"""
import logging
from datetime import date
from pathlib import Path

from lib.csv_utils import parse_csv
from lib.parsing import to_float

log = logging.getLogger(__name__)

_BASE = "https://www.barchart.com/stocks/quotes"


def option_history_url(symbol: str, expiration: date, strike: float, opt_type: str) -> str:
    """Build the Barchart price-history URL for one option contract."""
    cp = "C" if opt_type.strip().title() == "Call" else "P"
    sym = symbol.upper().strip()
    exp = expiration.strftime("%Y%m%d")
    return f"{_BASE}/{sym}%7C{exp}%7C{strike:.2f}{cp}/price-history/historical"


def _mark(row: dict):
    """Best tradeable price for a row: mid(Bid,Ask) → Latest."""
    bid, ask = to_float(row.get("Bid")), to_float(row.get("Ask"))
    if bid and ask and bid > 0 and ask > 0:
        return (bid + ask) / 2
    latest = to_float(row.get("Latest"))
    return latest if latest and latest > 0 else None


def parse_history_series(csv_text: str) -> list[tuple[date, float]]:
    """Parse a Barchart option price-history CSV into a sorted [(date, mark)] series."""
    series: list[tuple[date, float]] = []
    for row in parse_csv(csv_text):
        t = str(row.get("Time", "")).strip()
        try:
            d = date.fromisoformat(t)
        except ValueError:
            continue
        mark = _mark(row)
        if mark is not None:
            series.append((d, mark))
    series.sort(key=lambda x: x[0])
    return series


def parse_history_details(csv_text: str, require_mark: bool = True) -> dict[date, dict]:
    """Parse a Barchart history CSV into {date: row_dict} with a pre-computed '_mark' key.

    Rows with a non-date Time are excluded. The '_mark' key holds mid(Bid,Ask) →
    Latest, the same value parse_history_series uses. Rows with no computable mark
    are excluded by default (pricing callers need a mark); pass require_mark=False
    to keep them with '_mark' set to None (callers that only need IV/OI/greeks,
    e.g. the counterpart-IV fetch).
    """
    out: dict[date, dict] = {}
    for row in parse_csv(csv_text):
        t = str(row.get("Time", "")).strip()
        try:
            d = date.fromisoformat(t)
        except ValueError:
            continue
        mark = _mark(row)
        if mark is not None or not require_mark:
            out[d] = {**row, "_mark": mark}
    return out


def cache_path(cache_dir: Path, symbol: str, expiration: date, strike: float, opt_type: str) -> Path:
    cp = "C" if opt_type.strip().title() == "Call" else "P"
    return cache_dir / f"{symbol.upper().strip()}_{expiration.strftime('%Y%m%d')}_{strike:.2f}{cp}.csv"
