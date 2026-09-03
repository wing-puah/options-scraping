import csv
import logging
from datetime import date
from pathlib import Path

from lib import sheets_client

from ..helpers import _parse_analysis_date

log = logging.getLogger("backtest")


# ─── Analysis loading ──────────────────────────────────────────────────────────

def _rows_to_candidates(rows, start: date | None,
                        end: date | None) -> tuple[list[dict], dict]:
    """Map raw analysis rows (dicts keyed by ROW_COLUMNS) onto candidate trades.

    Shared by :func:`load_analysis` (Sheets rows) and :func:`load_analysis_csv`
    (a local rows CSV written by ``scripts.analysis_pipeline --output-dir``), so
    both sources produce byte-identical candidate dicts.
    """
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
            # Dedicated horizon column (blank on legacy rows — classify falls back
            # to regex-scraping the play bracket for those). See _resolve_expiry.
            "horizon": str(row.get("horizon", "")).strip(),
            # Per-ticker rollup context now stored on the analysis row itself (blank
            # on rows written before this column existed; _attach_rollup_metrics
            # backfills those from the audit rollup CSV).
            "oi_confirm_pct": str(row.get("oi_confirm_pct", "")).strip(),
            "cpir": str(row.get("cpir", "")).strip(),
            "iv_spread": str(row.get("iv_spread", "")).strip(),
            "iv_skew": str(row.get("iv_skew", "")).strip(),
            "iv_pct": str(row.get("iv_pct", "")).strip(),
            # Model evidence-quality score, component breakdown + summed total
            # (blank on legacy rows). Carried through to the results tab so each
            # factor can be measured against realized P&L.
            "score_total": str(row.get("score_total", "")).strip(),
            "score_flow": str(row.get("score_flow", "")).strip(),
            "score_dealer": str(row.get("score_dealer", "")).strip(),
            "score_price": str(row.get("score_price", "")).strip(),
            "score_vol": str(row.get("score_vol", "")).strip(),
            "score_catalyst": str(row.get("score_catalyst", "")).strip(),
        })

    return candidates, market_regime


def load_analysis(tab: str, start: date | None, end: date | None) -> tuple[list[dict], dict]:
    """Read the analysis tab. Returns (candidate trades, market_regime_by_date)."""
    candidates, market_regime = _rows_to_candidates(
        sheets_client.get_all_rows(tab), start, end)
    log.info("Loaded %d candidate plays from '%s' (%d market-regime dates)",
             len(candidates), tab, len(market_regime))
    return candidates, market_regime


def load_analysis_csv(path, start: date | None, end: date | None) -> tuple[list[dict], dict]:
    """Read a LOCAL analysis rows CSV (schema = analysis_pipeline ROW_COLUMNS).

    The local counterpart of :func:`load_analysis`: same candidate dicts, no
    Sheets call. Used by prompt-evaluation runs, where the analysis under test
    was written to a run directory and must never reach the AnalysisClaude tab.
    """
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    candidates, market_regime = _rows_to_candidates(rows, start, end)
    log.info("Loaded %d candidate plays from '%s' (%d market-regime dates)",
             len(candidates), csv_path, len(market_regime))
    return candidates, market_regime
