import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from lib.barchart import options as barchart_options
from lib.barchart import BarchartSession

from ..config import RESULTS_PATH, HISTORY_CACHE
from ..helpers import _to_float
from . import unlisted

log = logging.getLogger("backtest")

#: A fetched option history whose `Price~` sits further than this (median
#: relative difference) from its SIBLINGS' `Price~` is refused. Every contract
#: of one ticker and expiry reads the same underlying on the same day, so two
#: honest files agree to within rounding; the file this guard was written for
#: (META_20270115_630.00P, quarantined 2026-09-23) read ~$155 against ~$640.
UNDERLYING_MISMATCH_FRAC = 0.25

#: Seconds between successful history fetches (a test seam).
FETCH_PAUSE_S = 2

#: A dead browser is reopened at most this many times per `fetch_option_histories`
#: call; the next death (or a reopen that fails) stops the fetching.
MAX_SESSION_REOPENS = 2

#: Outage guard. After ``OUTAGE_MIN_FETCHES`` fetch outcomes, a share of
#: network-failure outcomes above ``BACKTEST_OUTAGE_MAX_SHARE`` raises
#: :class:`NetworkOutage`.
OUTAGE_MIN_FETCHES = 20
OUTAGE_MAX_SHARE_DEFAULT = 0.25
OUTAGE_SHARE_ENV = "BACKTEST_OUTAGE_MAX_SHARE"
OUTAGE_MIN_ENV = "BACKTEST_OUTAGE_MIN_FETCHES"

#: Exit code of `scripts.backtest` and `scripts.backtest.proxy` on a network
#: outage. 5 is BARCHART_AUTH_EXIT_CODE (login refused); 1 crash; 2 usage.
EXIT_NETWORK_OUTAGE = 6

_DEAD_SESSION_RE = re.compile(
    r"TargetClosedError|Target page, context or browser has been closed"
    r"|browser has been closed|has been disconnected|browser.{0,20}disconnected"
    r"|Connection closed|Browser closed", re.I)
_NETWORK_ERR_RE = re.compile(
    r"net::ERR_|NameResolution|ERR_INTERNET_DISCONNECTED|ERR_NETWORK_CHANGED"
    r"|ERR_NAME_NOT_RESOLVED|Timeout \d+ms exceeded|TimeoutError", re.I)


class NetworkOutage(RuntimeError):
    """Too many fetches failed with network errors: the machine is offline (or
    asleep), and the run's evidence is poisoned. Callers must abort before any
    write; `n_failed` of `n_total` fetches failed."""

    def __init__(self, n_failed: int, n_total: int):
        self.n_failed, self.n_total = n_failed, n_total
        super().__init__(f"network outage: {n_failed} of {n_total} fetches failed "
                         f"with network errors")


def is_dead_session(text: str | None) -> bool:
    """True when an exception's text says the Playwright browser is gone."""
    return bool(text) and _DEAD_SESSION_RE.search(text) is not None


def is_network_failure(outcome: str | None, error: str | None) -> bool:
    """True for a NAV_ERROR / ERROR outcome whose error text is a network or
    timeout error (and not a dead browser, which has its own path)."""
    if outcome not in (unlisted.HISTORY_NAV_ERROR, unlisted.HISTORY_ERROR) or not error:
        return False
    return not is_dead_session(error) and _NETWORK_ERR_RE.search(error) is not None


def _outage_limits() -> tuple[int, float]:
    try:
        share = float(os.getenv(OUTAGE_SHARE_ENV, OUTAGE_MAX_SHARE_DEFAULT))
    except ValueError:
        share = OUTAGE_MAX_SHARE_DEFAULT
    try:
        n = int(os.getenv(OUTAGE_MIN_ENV, OUTAGE_MIN_FETCHES))
    except ValueError:
        n = OUTAGE_MIN_FETCHES
    return n, share


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

#: Per-contract fetch-plan statuses (`FetchPlan.status`).
PLAN_CACHED = "cached"          # a cache file covers the window: no network call
PLAN_STALE = "stale"            # a cache file exists but is too shallow (either end): refetched
PLAN_MISSING = "missing"        # no cache file: scraped
PLAN_UNLISTED = "unlisted"      # in the negative cache: priced as no-data, no call
PLAN_UNCACHED = "uncached"      # --cache-only and no cache file: priced as no-data

#: Statuses that cost a Barchart fetch.
PLAN_SCRAPES = frozenset({PLAN_STALE, PLAN_MISSING})

#: A cached file whose latest bar sits more than this many weekday sessions
#: before the date the path needs (`needed_ends`) is FORWARD-stale.
FORWARD_TOLERANCE_SESSIONS = 3


# ─── Forward staleness: does a cached file reach the end of its window? ────────
# A file scraped while a contract was still trading stops on its fetch day. The
# plays that use it then price `open_at_data_end` forever, because the start
# check below never looks at the end. These helpers decide how far a file must
# reach. Sessions are counted in WEEKDAYS: the repo has no shared NYSE holiday
# calendar (backfill_chain.py carries a private approximation), and the
# 3-session tolerance absorbs a holiday.

def last_completed_session(today: date | None = None) -> date:
    """The latest weekday strictly before ``today``. Today's session is never
    counted complete: a mid-session run must not demand today's bar."""
    d = (today or date.today()) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def weekday_sessions_between(a: date, b: date) -> int:
    """Weekdays ``d`` with ``a < d <= b`` (0 when ``b <= a``)."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def path_end(signal_date: date, expirations, path_cap_days: int) -> date:
    """The last calendar day a play's path can reach: the same
    ``signal + min(nearest DTE, path_cap)`` that ``simulate._simulate`` uses."""
    nearest_dte = min((e - signal_date).days for e in expirations)
    return signal_date + timedelta(days=min(nearest_dte, path_cap_days))


def needed_end(play_end: date, today: date | None = None) -> date:
    """How far a contract's cache must reach: the play's path end, capped at
    the last completed session."""
    return min(play_end, last_completed_session(today))


def is_forward_stale(latest_bar: date | None, fetched_on: date, end: date) -> bool:
    """True when a cached file should be refetched to reach ``end``.

    Stale only while BOTH hold: the latest bar is more than
    ``FORWARD_TOLERANCE_SESSIONS`` sessions short of ``end``, and the file was
    fetched BEFORE ``end`` (its window was still open). A file fetched on or
    after ``end`` is FINAL: Barchart had every bar it will ever have, so a
    contract that simply stopped trading is never refetched again. Strictly
    before, not on-or-before: a same-day refetch of a sparse contract would
    repeat on every run of that day and return the same bars.
    """
    if fetched_on >= end:
        return False
    if latest_bar is None:
        return True
    return weekday_sessions_between(latest_bar, end) > FORWARD_TOLERANCE_SESSIONS


@dataclass
class FetchPlan:
    """What `fetch_option_histories` WOULD do, decided from disk alone.

    Building one reads the cache directory and the negative cache, and never
    opens a browser. `scripts.backtest --dry-run` prints it instead of fetching;
    a real run hands it straight back to `fetch_option_histories(plan=...)` so
    the cache is read once.
    """
    series_map: dict = field(default_factory=dict)
    details_map: dict = field(default_factory=dict)
    to_scrape: list = field(default_factory=list)
    status: dict = field(default_factory=dict)          # {contract_key: PLAN_*}
    #: Keys queued (PLAN_STALE) ONLY because their file stops short of the
    #: window's end. Their cached bars stay in the maps, so a failed refetch
    #: prices on what the file already holds.
    stale_forward: set = field(default_factory=set)
    known_unlisted: dict = field(default_factory=dict)
    unlisted_path: Path | None = None

    def count(self, *statuses: str) -> int:
        return sum(1 for s in self.status.values() if s in statuses)

    def hold(self, keys) -> int:
        """Take ``keys`` off the scrape queue: they are priced from whatever the
        cache holds, exactly as under ``--cache-only`` (a missing file is
        no-data). Used for contracts only a cache-changed re-price needs, which
        must never cost a fetch. Returns how many were held."""
        keys = set(keys)
        held = [c for c in self.to_scrape if c["key"] in keys]
        self.to_scrape = [c for c in self.to_scrape if c["key"] not in keys]
        for c in held:
            self.stale_forward.discard(c["key"])
            if c["key"] not in self.series_map:
                self.series_map[c["key"]] = []
                self.status[c["key"]] = PLAN_UNCACHED
            else:
                self.status[c["key"]] = PLAN_CACHED
        return len(held)


def plan_option_histories(
    contracts: list[dict],
    needed_dates: dict[tuple, date] | None = None,
    cache_only: bool = False,
    retry_unlisted: bool | None = None,
    needed_ends: dict[tuple, date] | None = None,
) -> FetchPlan:
    """Partition ``contracts`` into cached / to-scrape / skipped, from disk only.

    Arguments mean what they mean on :func:`fetch_option_histories`. The
    returned maps hold every contract whose cache is usable as-is; a stale or
    missing one is queued in ``to_scrape``; a known-unlisted one is priced as
    no-data (``series_map[key] = []``), exactly like a failed fetch.

    ``needed_ends`` ({contract_key: date}) adds the FORWARD check
    (:func:`is_forward_stale`, judged on the file's mtime date). A
    forward-stale file is queued as ``PLAN_STALE`` and listed in
    ``plan.stale_forward``; unlike a start-shallow file its bars stay in the
    maps. Nothing is ever unlinked.
    """
    _STALENESS_DAYS = 5
    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    plan = FetchPlan(unlisted_path=HISTORY_CACHE / unlisted.FILENAME)
    plan.known_unlisted = {} if cache_only else unlisted.load(plan.unlisted_path)
    retry = unlisted.retry_requested(retry_unlisted)
    series_map, details_map = plan.series_map, plan.details_map

    def _queue(c: dict, status: str, forward_only: bool = False) -> None:
        if not retry and unlisted.should_skip(plan.known_unlisted.get(unlisted.contract_id(c))):
            if forward_only:
                # The file is still good for what it holds; skip only the call.
                return
            # Exactly what a failed fetch leaves behind, minus the network call.
            series_map[c["key"]] = []
            details_map.pop(c["key"], None)
            plan.status[c["key"]] = PLAN_UNLISTED
            return
        plan.status[c["key"]] = status
        plan.to_scrape.append(c)

    for c in contracts:
        cache = barchart_options.cache_path(
            HISTORY_CACHE, c["symbol"], c["expiration"], c["strike"], c["opt_type"])
        if cache.exists():
            text = cache.read_text(encoding="utf-8")
            series_map[c["key"]] = barchart_options.parse_history_series(text)
            details_map[c["key"]] = barchart_options.parse_history_details(text)
            plan.status[c["key"]] = PLAN_CACHED
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
                    _queue(c, PLAN_STALE)
                    continue
            end = needed_ends.get(c["key"]) if needed_ends else None
            if end is not None:
                series = series_map.get(c["key"], [])
                latest = max((d for d, _ in series), default=None)
                fetched_on = date.fromtimestamp(cache.stat().st_mtime)
                if is_forward_stale(latest, fetched_on, end):
                    log.info("Cache for %s latest=%s, needed through %s, fetched %s "
                             "— refetching", c["key"], latest, end, fetched_on)
                    plan.stale_forward.add(c["key"])
                    _queue(c, PLAN_STALE, forward_only=True)
                    if plan.status[c["key"]] != PLAN_STALE:
                        plan.stale_forward.discard(c["key"])
        elif not cache_only:
            _queue(c, PLAN_MISSING)
        else:
            plan.status[c["key"]] = PLAN_UNCACHED
            log.debug("--cache-only: no cache for %s, skipping", c["key"])
    return plan


async def fetch_option_histories(
    contracts: list[dict], headless: bool, timeout_ms: int = 15000,
    needed_dates: dict[tuple, date] | None = None,
    cache_only: bool = False,
    retry_unlisted: bool | None = None,
    plan: FetchPlan | None = None,
    needed_ends: dict[tuple, date] | None = None,
) -> tuple[dict[tuple, list], dict[tuple, dict]]:
    """Scrape (and cache) per-contract Barchart price history.

    contracts: list of {key, symbol, opt_type, strike, expiration(date)}.
    needed_dates: {contract_key: earliest_signal_date} — if a cached file's earliest
      row is more than 5 days after the needed date, the cache is stale and re-scraped.
    needed_ends: {contract_key: last date the path needs} — the forward check
      (see :func:`plan_option_histories`).
    retry_unlisted: ignore the negative cache (`shared/unlisted.py`) and probe
      known-unlisted contracts again; None reads BACKTEST_RETRY_UNLISTED.
      A contract skipped as known-unlisted is priced exactly like a failed
      fetch (`series_map[key] = []`) — it just costs no network call.
    plan: a :func:`plan_option_histories` result for these same arguments, so a
      caller that already planned (to print or warn) does not read the cache
      twice. None = plan here.
    Returns (series_map, details_map):
      series_map:  {contract_key: [(date, price), ...]}  — for _price_asof exit lookups
      details_map: {contract_key: {date: row_dict}}      — for building entry rows
    """
    if plan is None:
        plan = plan_option_histories(contracts, needed_dates, cache_only, retry_unlisted,
                                     needed_ends=needed_ends)
    email = os.getenv("BARCHART_EMAIL", "")
    password = os.getenv("BARCHART_PASSWORD", "")
    cookies_path = Path(os.getenv(
        "COOKIES_PATH", str(RESULTS_PATH.parent / "cookies" / "barchart_session.json")))

    series_map, details_map = plan.series_map, plan.details_map
    to_scrape = plan.to_scrape
    known_unlisted, unlisted_path = plan.known_unlisted, plan.unlisted_path
    n_skipped_unlisted = plan.count(PLAN_UNLISTED)

    def _load_cache(c: dict, text: str) -> None:
        series_map[c["key"]] = barchart_options.parse_history_series(text)
        details_map[c["key"]] = barchart_options.parse_history_details(text)

    log.info("Barchart history: %d cached, %d to scrape (%d stale-forward)",
             plan.count(PLAN_CACHED), len(to_scrape), len(plan.stale_forward))
    if n_skipped_unlisted:
        log.info("%d contracts skipped as known-unlisted (%s; --retry-unlisted to "
                 "re-probe)", n_skipped_unlisted, unlisted_path.name)
    if not to_scrape:
        return series_map, details_map
    if not (email and password):
        log.warning("BARCHART_EMAIL/PASSWORD not set — skipping Barchart history "
                    "(legs without cached history will be refused at entry)")
        return series_map, details_map

    tracker = unlisted.TRACKER
    changes: dict[str, dict | None] = {}
    try:
        await _scrape(to_scrape, email, password, cookies_path, headless, timeout_ms,
                      series_map, details_map, _load_cache, tracker,
                      known_unlisted, changes, unlisted_path)
    except BaseException:
        # The session itself failed (login refused, browser died): that is
        # trouble around every NO_FEED still pending, never evidence.
        tracker.note(None)
        raise
    finally:
        _commit_unlisted(tracker, known_unlisted, changes, unlisted_path)
    return series_map, details_map


def _commit_unlisted(tracker, known: dict, changes: dict, path: Path) -> None:
    """Record every entry the tracker now confirms, and write the file. Runs in
    a `finally` after the scrape, so nothing here may raise: a skip-list failure
    must never cost a run its prices."""
    try:
        n = unlisted.commit(tracker.confirmed(), path, changes, known)
        if n:
            log.info("%d contract(s) recorded as unlisted on Barchart → %s", n, path.name)
        unlisted.apply(path, changes)
    except Exception:  # noqa: BLE001 — never fail a run over a skip-list
        log.exception("Could not update %s (the run's prices are unaffected)", path)


async def _open_session(email, password, cookies_path, headless, tracker):
    """Open a BarchartSession (login or cookie reuse) and note it as logged in.
    Opening at all means the login was verified (BarchartSession raises
    otherwise) — the proof a marker-less 404 page later leans on."""
    session = BarchartSession(email, password, cookies_path, headless)
    await session.__aenter__()
    tracker.note(unlisted.SESSION_OPEN, session=session)
    return session


async def _close_session(session) -> None:
    try:
        await session.__aexit__(None, None, None)
    except Exception:  # noqa: BLE001 — a dead browser may refuse to close
        log.debug("closing the Barchart session failed", exc_info=True)


async def _scrape(to_scrape, email, password, cookies_path, headless, timeout_ms,
                  series_map, details_map, _load_cache, tracker, known_unlisted,
                  changes, unlisted_path=None) -> None:
    min_fetches, max_share = _outage_limits()
    n_fetches = n_net = reopens = 0
    session = await _open_session(email, password, cookies_path, headless, tracker)
    try:
        i = 0
        while i < len(to_scrape):
            c = to_scrape[i]
            url = barchart_options.option_history_url(
                c["symbol"], c["expiration"], c["strike"], c["opt_type"])
            log.info("[%d/%d] Barchart history: %s", i + 1, len(to_scrape), url)
            error = None
            try:
                csv_text = await session.fetch_history_csv(url, timeout_ms)
                outcome = getattr(session, "last_history_outcome", None)
                error = getattr(session, "last_history_error", None)
            except Exception as e:
                log.exception("Barchart history scrape failed for %s", c["key"])
                csv_text, outcome = None, None
                error = f"{type(e).__name__}: {e}"
            if csv_text and outcome is None:
                outcome = unlisted.HISTORY_OK
            tracker.note(outcome, c, session=session, path=unlisted_path,
                         logged_in=getattr(session, "last_history_logged_in", None))
            if not csv_text and is_dead_session(error):
                # The browser is gone. This contract was not fetched: it is
                # left exactly as a failed fetch leaves it (no cache file, no
                # skip-list entry) and is retried on a fresh session.
                await _close_session(session)
                if reopens >= MAX_SESSION_REOPENS:
                    log.error("Barchart browser died again after %d reopen(s) — "
                              "STOPPING: %d of %d contract(s) left unfetched "
                              "(nothing cached or recorded as unlisted for them)",
                              reopens, len(to_scrape) - i, len(to_scrape))
                    session = None
                    break
                reopens += 1
                log.warning("Barchart browser died (%s) — reopening the session "
                            "(%d of %d)", error, reopens, MAX_SESSION_REOPENS)
                try:
                    session = await _open_session(
                        email, password, cookies_path, headless, tracker)
                except Exception:  # noqa: BLE001
                    log.exception("Could not reopen the Barchart session — STOPPING: "
                                  "%d of %d contract(s) left unfetched (nothing "
                                  "cached or recorded as unlisted for them)",
                                  len(to_scrape) - i, len(to_scrape))
                    session = None
                    break
                continue                      # same contract, new session
            n_fetches += 1
            if is_network_failure(outcome, error):
                n_net += 1
            if n_fetches >= min_fetches and n_net / n_fetches > max_share:
                log.error("Network outage: %d of %d fetches failed with network "
                          "errors", n_net, n_fetches)
                raise NetworkOutage(n_net, n_fetches)
            i += 1
            if not csv_text:
                # setdefault: a forward-stale contract keeps the bars its file
                # already holds; a missing or start-stale one has none (popped).
                series_map.setdefault(c["key"], [])
                continue
            cid = unlisted.contract_id(c)
            if cid in known_unlisted or cid in changes:
                changes[cid] = None          # it lists now: forget it
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
                series_map.setdefault(c["key"], [])
                continue
            # Stage then os.replace, the same way export_tabs.py installs a
            # pulled tab: a cache file is never half-written, and an existing
            # one is only ever superseded by a complete fetch.
            staged = cache.with_suffix(cache.suffix + ".tmp")
            staged.write_text(csv_text, encoding="utf-8")
            os.replace(staged, cache)
            _load_cache(c, csv_text)
            await asyncio.sleep(FETCH_PAUSE_S)
    finally:
        if session is not None:
            await _close_session(session)
    # A stop leaves the rest priced as no-data, like a failed fetch.
    for c in to_scrape[i:]:
        series_map.setdefault(c["key"], [])
