import asyncio
import logging
import os
from datetime import date
from pathlib import Path

from lib.barchart import options as barchart_options
from lib.barchart import BarchartSession

from ..config import RESULTS_PATH, HISTORY_CACHE
from ..helpers import _to_float

log = logging.getLogger("backtest")

#: A fetched option history whose `Price~` sits further than this (median
#: relative difference) from its SIBLINGS' `Price~` is refused. Every contract
#: of one ticker and expiry reads the same underlying on the same day, so two
#: honest files agree to within rounding; the file this guard was written for
#: (META_20270115_630.00P, quarantined 2026-09-23) read ~$155 against ~$640.
UNDERLYING_MISMATCH_FRAC = 0.25


def _sibling_price_tilde(symbol: str, expiration: date, own: Path) -> dict:
    """``{date: median Price~}`` across the cached files of the same ticker AND
    expiry, excluding ``own``.

    Siblings, not the underlying OHLC cache: that cache is split-ADJUSTED while
    option-history `Price~` is as-traded, so on a split ticker (NVDA 10:1, XLE
    2:1, ...) it disagrees with every good file by an exact multiple. Siblings
    of one expiry were all traded on the same basis.
    """
    prefix = f"{symbol.upper().strip()}_{expiration.strftime('%Y%m%d')}_"
    by_day: dict = {}
    for path in HISTORY_CACHE.glob(prefix + "*.csv"):
        if path.name == own.name:
            continue
        try:
            rows = barchart_options.parse_history_details(
                path.read_text(encoding="utf-8"), require_mark=False)
        except Exception:
            continue
        for d, row in rows.items():
            v = _to_float(row.get("Price~"))
            if v is not None and v > 0:
                by_day.setdefault(d, []).append(v)
    return {d: sorted(vs)[len(vs) // 2] for d, vs in by_day.items()}


def underlying_mismatch(details: dict, siblings: dict) -> str | None:
    """Detail string when a history's `Price~` disagrees wildly with its
    siblings' (``_sibling_price_tilde``) on overlapping dates, else None.

    None also when there is nothing to compare — no sibling file, or no
    overlapping date. No evidence is not a failure, so the guard never blocks
    a contract it cannot check.
    """
    diffs = []
    for d, row in details.items():
        ref = siblings.get(d)
        px = _to_float(row.get("Price~"))
        if ref and px and px > 0:
            diffs.append(abs(px - ref) / ref)
    if not diffs:
        return None
    diffs.sort()
    median = diffs[len(diffs) // 2]
    if median <= UNDERLYING_MISMATCH_FRAC:
        return None
    return (f"Price~ is {median:.0%} (median over {len(diffs)} days) away from its "
            f"sibling contracts' — the history belongs to another contract")


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
                    # The file is NOT unlinked here. It was until 2026-09-19,
                    # and a refetch that returned no rows then kept nothing: the
                    # scraper was re-issuing the page's default three-month
                    # `startDate`, which is empty for an expired contract, and
                    # 178 cache files were destroyed that way between the
                    # 2026-09-05 snapshot and 2026-09-08. The range is fixed in
                    # lib/barchart/session.py, but a shallow cache is still the
                    # only copy of scraped history that exists — losing it on a
                    # failed fetch is never an improvement over keeping it. The
                    # new text replaces it atomically below, on success only.
                    # The maps are still popped, so a failed refetch prices as
                    # no-data exactly as before: shallow history is dropped
                    # from THIS run, not from the disk.
                    to_scrape.append(c)
        elif not cache_only:
            to_scrape.append(c)
        else:
            log.debug("--cache-only: no cache for %s, skipping", c["key"])

    log.info("Barchart history: %d cached, %d to scrape", len(series_map), len(to_scrape))
    if not to_scrape:
        return series_map, details_map
    if not (email and password):
        log.warning("BARCHART_EMAIL/PASSWORD not set — skipping Barchart history "
                    "(legs without cached history will be refused at entry)")
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
            # Refuse a history that is not this ticker's (2026-09-23). Nothing is
            # written and nothing is unlinked: a shallow cache already on disk
            # stays exactly as it was, and this run prices the contract as
            # no-data.
            cache = barchart_options.cache_path(
                HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            bad = underlying_mismatch(
                barchart_options.parse_history_details(csv_text, require_mark=False),
                _sibling_price_tilde(c["symbol"], c["expiration"], cache))
            if bad:
                log.error("REJECTED Barchart history for %s: %s — not cached",
                          c["key"], bad)
                series_map[c["key"]] = []
                continue
            # Stage then os.replace, the same way export_tabs.py installs a
            # pulled tab: a cache file is never half-written, and an existing
            # one is only ever superseded by a complete fetch.
            staged = cache.with_suffix(cache.suffix + ".tmp")
            staged.write_text(csv_text, encoding="utf-8")
            os.replace(staged, cache)
            _load_cache(c, csv_text)
            await asyncio.sleep(2)

    return series_map, details_map
