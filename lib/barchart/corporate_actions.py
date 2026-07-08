"""
Barchart corporate actions (earnings/dividend dates) — feed URL + parser.

The fetch (Playwright feed interception) lives on
``BarchartSession.fetch_corporate_actions``; this module holds the pure pieces:
the page URL and the JSON row parser. Confirmed live capture (MU) returns the
full history in one response (no pagination), rows shaped
``{"date": "06/24/2026", "eventType": "Earnings", "value": "$25.11"}``.
"""
from __future__ import annotations

from datetime import date, datetime

from lib.parsing import to_float

_BASE = "https://www.barchart.com/stocks/quotes"


def corporate_actions_url(symbol: str) -> str:
    """The corporate-actions page URL for a symbol."""
    return f"{_BASE}/{symbol.upper().strip()}/price-history/corporate-actions"


def parse_corporate_actions(rows: list[dict]) -> list[dict]:
    """Feed ``data`` rows → ``[{"date": date, "event_type": str, "value": float | None}]``,
    sorted ascending by date. Rows with an unparseable date are skipped;
    ``event_type`` is passed through as-is (filtering by type is the caller's job).
    """
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            d = datetime.strptime(str(row.get("date", "")).strip(), "%m/%d/%Y").date()
        except ValueError:
            continue
        out.append({
            "date": d,
            "event_type": row.get("eventType"),
            "value": to_float(row.get("value")),
        })
    out.sort(key=lambda r: r["date"])
    return out
