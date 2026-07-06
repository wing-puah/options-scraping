import asyncio
import logging
import os
from datetime import date
from pathlib import Path

from lib import barchart_options
from lib.barchart import BarchartSession

from ..config import RESULTS_PATH, HISTORY_CACHE

log = logging.getLogger("backtest")


# ─── Barchart historical option prices ─────────────────────────────────────────

async def fetch_option_histories(
    contracts: list[dict], headless: bool, timeout_ms: int = 15000,
    needed_dates: dict[tuple, date] | None = None,
    cache_only: bool = False,
) -> tuple[dict[tuple, list], dict[tuple, dict]]:
    """Scrape (and cache) per-contract Barchart price history.

    contracts: list of {key, symbol, opt_type, strike, expiration(date)}.
    needed_dates: {contract_key: earliest_signal_date} — if a cached file's earliest
      row is more than 5 days after the needed date, the cache is stale and re-scraped.
    Returns (series_map, details_map):
      series_map:  {contract_key: [(date, price), ...]}  — for _price_asof exit lookups
      details_map: {contract_key: {date: row_dict}}      — for building entry rows
    """
    _STALENESS_DAYS = 5
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    email = os.getenv("BARCHART_EMAIL", "")
    password = os.getenv("BARCHART_PASSWORD", "")
    cookies_path = Path(os.getenv(
        "COOKIES_PATH", str(RESULTS_PATH.parent / "cookies" / "barchart_session.json")))

    series_map: dict[tuple, list] = {}
    details_map: dict[tuple, dict] = {}
    to_scrape: list[dict] = []

    def _load_cache(c: dict, text: str) -> None:
        series_map[c["key"]] = barchart_options.parse_history_series(text)
        details_map[c["key"]] = barchart_options.parse_history_details(text)

    for c in contracts:
        cache = barchart_options.cache_path(
            HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
        if cache.exists():
            text = cache.read_text(encoding="utf-8")
            _load_cache(c, text)
            if cache_only:
                continue
            # Re-scrape if cache doesn't reach back to the earliest signal date.
            needed = needed_dates.get(c["key"]) if needed_dates else None
            if needed is not None:
                series = series_map.get(c["key"], [])
                earliest = min((d for d, _ in series), default=None)
                if earliest is None or (earliest - needed).days > _STALENESS_DAYS:
                    log.info(
                        "Cache for %s earliest=%s, needed=%s — refetching",
                        c["key"], earliest, needed,
                    )
                    series_map.pop(c["key"], None)
                    details_map.pop(c["key"], None)
                    cache.unlink()
                    to_scrape.append(c)
        elif not cache_only:
            to_scrape.append(c)
        else:
            log.debug("--cache-only: no cache for %s, skipping", c["key"])

    log.info("Barchart history: %d cached, %d to scrape", len(series_map), len(to_scrape))
    if not to_scrape:
        return series_map, details_map
    if not (email and password):
        log.warning("BARCHART_EMAIL/PASSWORD not set — skipping Barchart history (BS fallback will be used)")
        return series_map, details_map

    async with BarchartSession(email, password, cookies_path, headless) as session:
        for i, c in enumerate(to_scrape, 1):
            url = barchart_options.option_history_url(
                c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            log.info("[%d/%d] Barchart history: %s", i, len(to_scrape), url)
            try:
                csv_text = await session.fetch_history_csv(url, timeout_ms)
            except Exception:
                log.exception("Barchart history scrape failed for %s", c["key"])
                csv_text = None
            if not csv_text:
                series_map[c["key"]] = []
                continue
            cache = barchart_options.cache_path(
                HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            cache.write_text(csv_text, encoding="utf-8")
            _load_cache(c, csv_text)
            await asyncio.sleep(2)

    return series_map, details_map
