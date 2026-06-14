"""VIX term structure snapshot for the LLM analysis prompt.

Fetches four CBOE indices from Yahoo Finance and formats them as a compact
markdown section. All four are standard CBOE products available on Yahoo:
  ^VIX   — 30-day implied vol (the benchmark)
  ^VIX9D — 9-day (event / near-term risk)
  ^VIX3M — 3-month (term structure anchor; old VXV)
  ^VVIX  — vol of vol (cost of hedging with options)

Derived signals:
  term_ratio  = VIX / VIX3M  (>1 → backwardation, <1 → contango)
  event_ratio = VIX9D / VIX  (>1 → near-term event vol elevated)

SPX skew is not included — it requires options chain data not available
from this feed. Check it manually before entering VC / DP plays.

Caching: results are written to .cache/vol_snapshot_YYYY-MM-DD.json in the
project root and reused on subsequent calls (within the same day or for
historical dates). Failure is soft — a network outage never blocks a run.
"""
import json
import logging
import math
from datetime import date, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

_TICKERS = {
    "VIX":   "^VIX",
    "VIX9D": "^VIX9D",
    "VIX3M": "^VIX3M",
    "VVIX":  "^VVIX",
}

_VVIX_ELEVATED = 100.0

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


def _cache_path(d: date) -> Path:
    return _CACHE_DIR / f"vol_snapshot_{d.isoformat()}.json"


def _load_cache(d: date) -> dict[str, float] | None:
    p = _cache_path(d)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return None


def _save_cache(d: date, data: dict[str, float]) -> None:
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        _cache_path(d).write_text(json.dumps(data))
    except Exception:
        log.warning("vol_snapshot: could not write cache", exc_info=True)


def fetch_vol_snapshot(date_str: str | None = None) -> dict[str, float] | None:
    """Fetch VIX term structure data for a trading date (or today if None).

    Returns a dict with keys: VIX, VIX9D, VIX3M, VVIX, term_ratio,
    event_ratio. Caches to .cache/vol_snapshot_YYYY-MM-DD.json — historical
    dates are never re-fetched; today's result is reused within the same day.
    Returns None on any failure so callers can degrade gracefully.
    """
    d = date.fromisoformat(date_str) if date_str else date.today()

    cached = _load_cache(d)
    if cached is not None:
        log.debug("vol_snapshot: cache hit for %s", d)
        return cached

    try:
        import yfinance as yf

        start = (d - timedelta(days=7)).isoformat()
        end   = (d + timedelta(days=1)).isoformat()

        tickers = list(_TICKERS.values())
        data = yf.download(tickers, start=start, end=end,
                           auto_adjust=True, progress=False)

        if data.empty:
            log.warning("vol_snapshot: yfinance returned empty for %s", d)
            return None

        closes = data["Close"]
        candidates = [idx for idx in closes.index if idx.date() <= d]
        if not candidates:
            log.warning("vol_snapshot: no data at or before %s", d)
            return None
        row = closes.loc[max(candidates)]

        result: dict[str, float] = {}
        for name, ticker in _TICKERS.items():
            val = row.get(ticker)
            if val is None:
                continue
            try:
                f = float(val)
                if not math.isnan(f):
                    result[name] = round(f, 2)
            except (TypeError, ValueError):
                pass

        if not result:
            return None

        if "VIX" in result and "VIX3M" in result and result["VIX3M"] > 0:
            result["term_ratio"] = round(result["VIX"] / result["VIX3M"], 3)
        if "VIX9D" in result and "VIX" in result and result["VIX"] > 0:
            result["event_ratio"] = round(result["VIX9D"] / result["VIX"], 3)

        _save_cache(d, result)
        return result

    except Exception:
        log.warning("vol_snapshot: fetch failed", exc_info=True)
        return None


def vol_snapshot_md(snap: dict[str, float]) -> str:
    """Format a vol snapshot dict as a markdown section for the LLM prompt."""
    if not snap:
        return ""

    lines = ["## Vol regime snapshot"]

    vix    = snap.get("VIX")
    vix9d  = snap.get("VIX9D")
    vix3m  = snap.get("VIX3M")
    vvix   = snap.get("VVIX")
    term_r = snap.get("term_ratio")
    event_r = snap.get("event_ratio")

    if vix is not None and vix3m is not None and term_r is not None:
        structure = "backwardation" if term_r > 1 else "contango"
        lines.append(f"VIX {vix} / VIX3M {vix3m} → ratio {term_r:.3f} ({structure})")
        if term_r > 1.05:
            lines.append("_Backwardation: fade VC; avoid naked premium selling; prefer long convexity._")
        elif term_r < 0.90:
            lines.append("_Steep contango: VC and DP conditions supported; premium selling rational._")
    elif vix is not None:
        lines.append(f"VIX {vix}")

    if vix9d is not None and vix is not None and event_r is not None:
        note = ("near-term event risk elevated — extend DTE past catalyst or buy event vol"
                if event_r > 1 else "normal near-term pricing")
        lines.append(f"VIX9D {vix9d} / VIX {vix} → ratio {event_r:.3f} ({note})")

    if vvix is not None:
        note = "elevated — defined-risk structures mandatory" if vvix >= _VVIX_ELEVATED else "normal"
        lines.append(f"VVIX {vvix} — {note}")

    lines.append("_(SPX skew not included — check manually before VC / DP entries.)_")

    return "\n".join(lines)
