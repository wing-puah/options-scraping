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
last-trade price that goes stale on zero-volume days. Falls back to Latest, then
the theoretical (Theo) value.
"""
import logging
from datetime import date
from pathlib import Path

from lib.csv_utils import parse_csv

log = logging.getLogger(__name__)

_BASE = "https://www.barchart.com/stocks/quotes"


def _to_float(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if s == "" or s in ("-", "N/A", "n/a"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def option_history_url(symbol: str, expiration: date, strike: float, opt_type: str) -> str:
    """Build the Barchart price-history URL for one option contract."""
    cp = "C" if opt_type.strip().title() == "Call" else "P"
    sym = symbol.upper().strip()
    exp = expiration.strftime("%Y%m%d")
    return f"{_BASE}/{sym}%7C{exp}%7C{strike:.2f}{cp}/price-history/historical"


def _mark(row: dict):
    """Best tradeable price for a row: mid(Bid,Ask) → Latest → Theo."""
    bid, ask = _to_float(row.get("Bid")), _to_float(row.get("Ask"))
    if bid and ask and bid > 0 and ask > 0:
        return (bid + ask) / 2
    latest = _to_float(row.get("Latest"))
    if latest and latest > 0:
        return latest
    theo = _to_float(row.get("Theo"))
    return theo if theo and theo > 0 else None


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


def cache_path(cache_dir: Path, symbol: str, expiration: date, strike: float, opt_type: str) -> Path:
    cp = "C" if opt_type.strip().title() == "Call" else "P"
    return cache_dir / f"{symbol.upper().strip()}_{expiration.strftime('%Y%m%d')}_{strike:.2f}{cp}.csv"
