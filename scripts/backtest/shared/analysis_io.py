import logging
from datetime import date

from lib import sheets_client

from ..helpers import _parse_analysis_date

log = logging.getLogger("backtest")


# ─── Analysis loading ──────────────────────────────────────────────────────────

def load_analysis(tab: str, start: date | None, end: date | None) -> tuple[list[dict], dict]:
    """Read the analysis tab. Returns (candidate trades, market_regime_by_date)."""
    rows = sheets_client.get_all_rows(tab)
    market_regime: dict[str, str] = {}
    candidates: list[dict] = []

    for row in rows:
        d_date = _parse_analysis_date(row.get("date", ""))
        if d_date is None:
            continue
        if start and d_date < start:
            continue
        if end and d_date > end:
            continue
        d = d_date.isoformat()

        ticker = str(row.get("ticker", "")).strip()
        if ticker.upper() == "MARKET":
            market_regime[d] = str(row.get("regime", "")).strip()
            continue
        if not str(row.get("play", "")).strip():
            continue

        candidates.append({
            "date": d,
            "signal_date": d_date,
            "ticker": ticker,
            "regime": str(row.get("regime", "")).strip(),
            "signal": str(row.get("signal", "")).strip(),
            "play": str(row.get("play", "")).strip(),
            "invalidation": str(row.get("invalidation", "")).strip(),
            # Per-ticker rollup context now stored on the analysis row itself (blank
            # on rows written before this column existed; _attach_rollup_metrics
            # backfills those from the audit rollup CSV).
            "oi_confirm_pct": str(row.get("oi_confirm_pct", "")).strip(),
            "cpir": str(row.get("cpir", "")).strip(),
            "iv_spread": str(row.get("iv_spread", "")).strip(),
            "iv_skew": str(row.get("iv_skew", "")).strip(),
            "iv_pct": str(row.get("iv_pct", "")).strip(),
        })

    log.info("Loaded %d candidate plays from '%s' (%d market-regime dates)",
             len(candidates), tab, len(market_regime))
    return candidates, market_regime


# Legacy alias — some callers/tests still spell this with the old private name.
_load_analysis = load_analysis
