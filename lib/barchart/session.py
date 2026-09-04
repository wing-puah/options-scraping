"""
Barchart browser session — authentication and CSV download.

BarchartSession manages a single Playwright browser instance with cookie reuse.
Use as an async context manager; inject into scrapers rather than constructing inline.
"""
import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext

from lib.logger import safe_err

log = logging.getLogger(__name__)


class BarchartSession:
    _BASE = "https://www.barchart.com"
    _USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    _COOKIE_MAX_AGE = 8 * 3600  # seconds
    _LOGIN_MARKER_TIMEOUT = 10000  # ms to wait for the logged-in header marker
    # The account menu is rendered into the header on a logged-in page and absent on a
    # logged-out one, but it sits inside a collapsed dropdown, so it is ATTACHED and
    # never VISIBLE. Waiting for the default "visible" state therefore timed out on
    # every live session — see the state="attached" note in _authenticate.
    _LOGIN_MARKER = (
        "[data-ng-controller='AccountDropdownCtrl'], .user-account, [class*='account']"
    )
    # A fresh login from a GitHub-hosted runner started failing intermittently on
    # 2026-09-03 — 5 of that day's 10 fresh logins across scrape.yml and
    # flow-pacemaker.yml, against zero failures in the preceding weeks. The submit is
    # accepted, no error renders, and the page simply stays on /login. The same
    # credentials logged in 3/3 from a residential IP the next day, and every
    # cookie-reuse run that day succeeded, so what is being refused is the login POST
    # from that IP, not the account.
    #
    # Retrying is therefore worth more than failing the run: at the observed per-attempt
    # rate, 3 tries turn a ~50% failure into ~12%. It is NOT a fix — if the rate keeps
    # climbing the answer is to stop logging in fresh every run (persist the cookie
    # jar between CI runs), and the diagnosis logged below is what tells us which.
    _LOGIN_ATTEMPTS = 3
    _LOGIN_RETRY_DELAY = 8.0  # seconds, doubled per attempt
    # Logged, not acted on: these say whether a failure was an explicit challenge or the
    # silent stay-on-/login we are actually seeing. Retrying is unconditional either way
    # — an attempt costs seconds, and guessing "this one is hopeless" off page text is
    # how a transient block turns into a skipped scrape.
    _CHALLENGE_HINTS = (
        "captcha", "unusual activity", "too many", "temporarily blocked",
        "rate limit", "are you a robot", "verify you are human", "access denied",
    )

    def __init__(
        self,
        email: str,
        password: str,
        cookies_path: Path,
        headless: bool = True,
    ) -> None:
        self._email = email
        self._password = password
        self._cookies_path = cookies_path
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        # Cached (augmented_feed_url, headers) from the last successful price-history
        # navigation, so further contracts can re-issue the feed without a page load.
        self._history_feed: tuple[str, dict] | None = None

    async def __aenter__(self) -> "BarchartSession":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context(user_agent=self._USER_AGENT)
        self._page = await self._context.new_page()
        if not await self._authenticate():
            raise RuntimeError("Barchart authentication failed.")
        return self

    async def __aexit__(self, *_) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _authenticate(self) -> bool:
        if await self._try_cached_cookies():
            return True

        # A fresh login is the failure-prone path (see _LOGIN_ATTEMPTS): retry it on a
        # clean context rather than failing the whole run on one blocked attempt.
        outcome = "no login attempt made"
        for attempt in range(1, self._LOGIN_ATTEMPTS + 1):
            if attempt > 1:
                delay = self._LOGIN_RETRY_DELAY * (2 ** (attempt - 2))
                log.warning(
                    "Retrying Barchart login in %.0fs (attempt %d/%d)",
                    delay, attempt, self._LOGIN_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                await self._reset_context()

            outcome = await self._login_once()
            if outcome is None:
                return True
            log.warning("Barchart login attempt %d/%d failed — %s",
                        attempt, self._LOGIN_ATTEMPTS, outcome)

        log.error(
            "Login failed: still on login page after submit "
            "(%d attempts) — last diagnosis: %s",
            self._LOGIN_ATTEMPTS, outcome,
        )
        return False

    async def _try_cached_cookies(self) -> bool:
        """Load cookies from disk and report whether they carry a live session."""
        cookies_fresh = (
            self._cookies_path.exists()
            and (time.time() - self._cookies_path.stat().st_mtime) < self._COOKIE_MAX_AGE
        )
        if not cookies_fresh:
            return False

        log.debug("Loading cached Barchart cookies")
        await self._context.add_cookies(json.loads(self._cookies_path.read_text()))
        await self._goto_with_retry(f"{self._BASE}/options/unusual-activity/stocks")
        # Wait for the marker rather than querying the instant domcontentloaded
        # fires — the header renders late, and a bare query_selector here reports
        # a live session as expired.
        #
        # state="attached", NOT the default "visible": the marker lives inside a
        # collapsed account dropdown, so on a perfectly live session it is in the DOM
        # and invisible. Waiting for visibility timed out on EVERY cookie-reuse run —
        # the log then said "Cached session expired" and the /login navigation below
        # immediately disproved it with "Already authenticated". That cost 10s and,
        # worse, made a working cookie path look broken while the real login failures
        # were happening.
        try:
            await self._page.wait_for_selector(
                self._LOGIN_MARKER, state="attached",
                timeout=self._LOGIN_MARKER_TIMEOUT,
            )
            log.info("Reusing cached Barchart session")
            return True
        except Exception:
            log.info("Cached session expired — re-logging in")
            return False

    async def _login_once(self) -> str | None:
        """One fill-and-submit pass. Returns None on success, else a diagnosis string.

        The diagnosis is the whole point of this being a separate method: a bare
        "still on login page" said nothing about WHY, so a run that failed in CI and
        succeeded locally was undiagnosable. Report the URL we ended on, any error text
        the form rendered, and whether the page reads as a bot challenge.
        """
        log.info("Logging in to Barchart")
        await self._goto_with_retry(f"{self._BASE}/login")
        if "/login" not in self._page.url:
            # Barchart bounces an already-authenticated visitor off /login, so the form
            # never renders and the fill below would time out the whole run. The marker
            # check above was simply wrong about this session.
            log.info("Already authenticated — /login redirected to '%s'", self._page.url)
            await self._save_cookies()
            return None

        await self._page.fill("input[name='email']", self._email)
        await self._page.fill("input[name='password']", self._password)
        await self._page.click("button[type='submit']")

        try:
            await self._page.wait_for_function(
                "() => !window.location.pathname.startsWith('/login')",
                timeout=15000,
            )
        except Exception:
            pass

        if "/login" in self._page.url:
            return await self._diagnose_login_failure()

        await self._save_cookies()
        log.info("Login successful — session saved")
        return None

    async def _diagnose_login_failure(self) -> str:
        """Describe a stuck-on-/login page. Never raises — a diagnosis that blew up
        would replace the real failure with its own.
        """
        parts = [f"url={self._page.url}"]
        try:
            text = " ".join((await self._page.inner_text("body")).split())
        except Exception:
            text = ""

        hits = [h for h in self._CHALLENGE_HINTS if h in text.lower()]
        if hits:
            parts.append(f"challenge hints={hits}")

        form_error = await self._first_error_text()
        if form_error:
            parts.append(f"form error={form_error!r}")

        if not hits and not form_error:
            parts.append(f"no error rendered; body[:200]={text[:200]!r}")

        await self._dump_debug_artifacts()
        return " | ".join(parts)

    async def _first_error_text(self) -> str:
        """First non-empty error message the login form is rendering, or ""."""
        for sel in (".error", "[class*='error']", "[role='alert']"):
            try:
                for el in await self._page.query_selector_all(sel):
                    msg = " ".join((await el.inner_text()).split())
                    if msg:
                        return msg
            except Exception:
                continue
        return ""

    async def _dump_debug_artifacts(self) -> None:
        """Screenshot + HTML of the failed login, when BARCHART_DEBUG_DIR is set.

        Off by default, and deliberately not set by any workflow: the page holds a
        filled-in email field, so this writes credentials-adjacent content. Set the var
        on a hand-dispatched debugging run and upload the directory as an artifact.
        """
        debug_dir = os.getenv("BARCHART_DEBUG_DIR", "").strip()
        if not debug_dir:
            return
        try:
            out = Path(debug_dir)
            out.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%dT%H%M%S")
            await self._page.screenshot(path=str(out / f"login-fail-{stamp}.png"),
                                        full_page=True)
            (out / f"login-fail-{stamp}.html").write_text(await self._page.content())
            log.info("Wrote login-failure artifacts to '%s'", out)
        except Exception as e:
            log.warning("Could not write login-failure artifacts: %s", safe_err(e))

    async def _reset_context(self) -> None:
        """Drop the browser context and open a clean one.

        Whatever gets an attempt refused may well be pinned to the context — a
        challenge or throttle cookie set on the way in. Retrying in the same context
        would then just replay it, so the retry starts from clean state. NOT verified
        against the live failure (it does not reproduce off a runner IP); it is the
        cheap assumption, and costs one browser context per retry if it is wrong.
        """
        old = self._context
        self._context = await self._browser.new_context(user_agent=self._USER_AGENT)
        self._page = await self._context.new_page()
        self._history_feed = None
        if old is not None:
            try:
                await old.close()
            except Exception:
                pass

    async def _save_cookies(self) -> None:
        self._cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self._cookies_path.write_text(json.dumps(await self._context.cookies()))

    async def _goto_with_retry(self, url: str, timeout_ms: int = 30000,
                                max_retries: int = 2, base_delay: float = 5.0) -> None:
        """Navigate with retry, backing off on transient timeouts (auth's own page loads
        aren't covered by _get_with_retry, which only retries authenticated feed GETs).
        """
        for attempt in range(max_retries + 1):
            try:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                return
            except Exception:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    log.warning("Navigation to '%s' failed — retrying in %.0fs (%d/%d)",
                                url, delay, attempt + 1, max_retries)
                    await asyncio.sleep(delay)
                else:
                    raise

    # Headers we must NOT copy from the captured request onto a re-issued one.
    # `cookie` would pin a snapshot of the session into `_history_feed` and go stale
    # over a long run — the browser context supplies the live one; `accept-encoding`
    # is Playwright's to negotiate, since it decodes the body for us.
    _SKIP_HEADERS = frozenset({"cookie", "accept-encoding", "content-length", "host"})

    @classmethod
    def _passthrough_headers(cls, headers: dict) -> dict:
        """Headers to replay when re-issuing a feed request the page itself fired.

        Copy everything the browser sent apart from :attr:`_SKIP_HEADERS` and HTTP/2
        pseudo-headers (`:authority`, `:method`, …), which Playwright rejects.

        This used to be an allowlist of ("x-xsrf-token", "referer"). Barchart stopped
        sending `x-xsrf-token` on the core-api feeds and now gates them on the
        `sec-fetch-*` metadata instead, so the allowlist reduced to a lone `referer`
        and every re-issued feed came back 403 ({"error":"Forbidden"}) — silently, as
        a skipped contract. Verified 2026-08-29: referer alone → 403, referer plus the
        sec-fetch trio → 200. Replaying the full header set keeps working whichever
        header they gate on next, so do NOT narrow this back to an allowlist.
        """
        return {
            k: v for k, v in headers.items()
            if not k.startswith(":") and k.lower() not in cls._SKIP_HEADERS
        }

    async def _get_with_retry(self, url: str, headers: dict, timeout_ms: int,
                              max_retries: int = 3, base_delay: float = 10.0):
        """GET via the page's authenticated request context, retrying on HTTP 429.

        Barchart rate-limits when a run hits its core-api feed rapidly (e.g. enriching
        many contracts back-to-back). A 429 is transient, so back off exponentially
        (base_delay * 2**attempt seconds) and retry up to max_retries times, returning
        whatever the last attempt got (including a still-429'd response) so callers
        keep their existing resp.ok / resp.status handling unchanged.
        """
        resp = await self._page.request.get(url, headers=headers, timeout=timeout_ms)
        attempt = 0
        while resp.status == 429 and attempt < max_retries:
            delay = base_delay * (2 ** attempt)
            log.warning(
                "HTTP 429 from '%s' — backing off %.0fs before retry %d/%d",
                url, delay, attempt + 1, max_retries,
            )
            await asyncio.sleep(delay)
            resp = await self._page.request.get(url, headers=headers, timeout=timeout_ms)
            attempt += 1
        return resp

    # Columns of the legacy "Download" CSV, kept identical so cached files and
    # lib.barchart.options.parse_history_series keep working unchanged.
    _HISTORY_COLUMNS = (
        ("Time", "tradeTime"), ("Open", "openPrice"), ("High", "highPrice"),
        ("Low", "lowPrice"), ("Latest", "lastPrice"), ("Change", "priceChange"),
        ("%Change", "percentChange"), ("Volume", "volume"), ("Open Int", "openInterest"),
        ("IV", "impliedVolatility"), ("Delta", "delta"), ("Gamma", "gamma"),
        ("Theta", "theta"), ("Vega", "vega"), ("Rho", "rho"),
        ("Theo", "theoreticalValue"), ("Price~", "baseLastPrice"),
        ("Bid", "bidPrice"), ("Ask", "askPrice"),
    )

    async def fetch_history_csv(self, url: str, timeout_ms: int = 30000) -> str | None:
        """
        Scrape one option's full price history WITHOUT the metered Download button.

        The price-history page renders its grid from a JSON feed
        (`/proxies/core-api/v1/historical/get`). We let the page fire that request,
        capture its authenticated URL + headers, then re-issue it with a high row
        limit and bid/ask fields added. The feed returns the entire series in one
        response, so there is no pagination to walk. Returns CSV text in the same
        column schema as the old download (so callers/cache stay unchanged), or None.
        """
        log.info("Navigating to '%s'", url)
        try:
            async with self._page.expect_request(
                lambda r: "core-api/v1/historical/get" in r.url, timeout=timeout_ms
            ) as req_info:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            req = await req_info.value
        except Exception:
            log.exception("Did not observe the price-history feed request on '%s'", url)
            return None

        headers = await req.all_headers()
        api_url = self._augment_history_url(req.url)
        pass_headers = self._passthrough_headers(headers)
        # Remember this authenticated feed so fetch_history_fast can re-issue it for
        # other contracts without navigating to each one's page.
        self._history_feed = (api_url, pass_headers)

        try:
            resp = await self._get_with_retry(api_url, pass_headers, timeout_ms)
            if not resp.ok:
                log.warning("History feed returned HTTP %d for '%s'", resp.status, url)
                return None
            payload = await resp.json()
        except Exception:
            log.exception("History feed fetch/parse failed for '%s'", url)
            return None

        rows = payload.get("data") or []
        if not rows:
            log.warning("History feed returned no rows for '%s'", url)
            return None

        csv_text = self._history_rows_to_csv(rows)
        log.info("Scraped %d price-history rows from '%s'", len(rows), url)
        return csv_text

    async def fetch_history_fast(self, page_url: str, timeout_ms: int = 30000) -> str | None:
        """Like fetch_history_csv but WITHOUT a per-contract page load.

        The price-history feed is authenticated by the session cookie + x-xsrf-token,
        not by the specific page, so once one navigation has captured the feed request
        (`_history_feed`) we can re-issue it for any other contract by swapping the
        `symbol=` param and pointing the Referer at that contract's page. This turns a
        full browser navigation per contract into a single JSON request — the big win
        when enriching ~1000 contracts.

        Falls back to fetch_history_csv (full navigation) when no feed is cached yet or
        the direct re-issue fails, so data is never silently lost — at worst it is as
        slow as before for that contract, and the navigation refreshes the cached feed.
        """
        if self._history_feed is None:
            return await self.fetch_history_csv(page_url, timeout_ms)

        api_url, headers = self._history_feed
        reissue_url = self._reissue_history_url(api_url, page_url)
        # Keep the captured x-xsrf-token; point Referer at this contract's own page so
        # the request looks identical to what that page would have fired.
        headers = {**headers, "referer": page_url}
        try:
            resp = await self._get_with_retry(reissue_url, headers, timeout_ms)
            if resp.ok:
                payload = await resp.json()
                rows = payload.get("data") or []
                if rows:
                    log.info("Re-issued price-history feed for '%s' — %d rows", page_url, len(rows))
                    return self._history_rows_to_csv(rows)
                log.warning("Re-issued feed returned no rows for '%s' — re-navigating", page_url)
            else:
                log.warning("Re-issued feed HTTP %d for '%s' — re-navigating", resp.status, page_url)
        except Exception as e:
            log.error("Re-issued feed failed for '%s' — re-navigating: %s", page_url, safe_err(e))

        return await self.fetch_history_csv(page_url, timeout_ms)

    async def fetch_options_overview_history(self, symbol: str, start: str | None = None,
                                             end: str | None = None,
                                             timeout_ms: int = 30000) -> list[dict] | None:
        """Scrape a symbol's daily options-overview IV history (IV / IV rank / IV
        percentile) via the page's core-api feed. Returns the feed's JSON ``data`` rows
        (list of dicts) or None.

        ``start``/``end`` (``YYYY-MM-DD``) restrict the feed to a date window — the few
        days around a trade date the enricher needs — so the payload is a handful of
        rows, not the full series. When omitted, the whole series is pulled.

        Same interception approach as :meth:`fetch_history_csv`: navigate to the
        options-history page, capture the authenticated core-api request it fires, then
        re-issue it (windowed, or with the row cap lifted). Parsing the rows into a
        {date: iv/iv_rank/iv_pct} series lives in :mod:`lib.barchart.iv_history` (pure),
        so this only does the fetch.

        The feed is the core-api ``options-historical/get`` endpoint (verified from a
        live capture). NB it contains ``historical/get`` as a substring, so the match
        keys on the fuller ``options-historical/get`` to avoid colliding with the
        price-history feed (``…/v1/historical/get``).
        """
        from lib.barchart.iv_history import options_history_url

        url = options_history_url(symbol)
        log.info("Navigating to options-history '%s'", url)

        def _is_iv_feed(r) -> bool:
            return "core-api" in r.url and "options-historical/get" in r.url

        try:
            async with self._page.expect_request(_is_iv_feed, timeout=timeout_ms) as req_info:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            req = await req_info.value
        except Exception:
            log.exception("Did not observe the options-history feed request on '%s'", url)
            return None

        headers = await req.all_headers()
        api_url = self._augment_iv_history_url(req.url, start, end)
        pass_headers = self._passthrough_headers(headers)

        try:
            resp = await self._get_with_retry(api_url, pass_headers, timeout_ms)
            if not resp.ok:
                log.warning("Options-history feed HTTP %d for '%s'", resp.status, symbol)
                return None
            payload = await resp.json()
        except Exception:
            log.exception("Options-history feed fetch/parse failed for '%s'", symbol)
            return None

        rows = payload.get("data") or []
        log.info("Scraped %d options-history rows for '%s'", len(rows), symbol)
        return rows

    async def fetch_corporate_actions(self, symbol: str, timeout_ms: int = 30000) -> list[dict] | None:
        """Scrape a symbol's corporate actions (earnings/dividend dates) via the page's
        core-api feed. Returns the feed's JSON ``data`` rows (list of dicts) or None.

        Same interception approach as :meth:`fetch_options_overview_history`: navigate
        to the corporate-actions page, capture the authenticated core-api request it
        fires, then re-issue it. Unlike the IV-history feed, NO URL augmentation is
        needed — the page's default request already returns the full history in one
        response (confirmed live: 126 rows back to 2021+ for MU, no pagination/limit).
        Parsing the rows into ``[{date, event_type, value}]`` lives in
        :mod:`lib.barchart.corporate_actions` (pure), so this only does the fetch.
        """
        from lib.barchart.corporate_actions import corporate_actions_url

        url = corporate_actions_url(symbol)
        log.info("Navigating to corporate-actions '%s'", url)

        def _is_corp_actions_feed(r) -> bool:
            return "core-api" in r.url and "corporateActions" in r.url

        try:
            async with self._page.expect_request(_is_corp_actions_feed, timeout=timeout_ms) as req_info:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            req = await req_info.value
        except Exception:
            log.exception("Did not observe the corporate-actions feed request on '%s'", url)
            return None

        headers = await req.all_headers()
        pass_headers = self._passthrough_headers(headers)

        try:
            resp = await self._get_with_retry(req.url, pass_headers, timeout_ms)
            if not resp.ok:
                log.warning("Corporate-actions feed HTTP %d for '%s'", resp.status, symbol)
                return None
            payload = await resp.json()
        except Exception:
            log.exception("Corporate-actions feed fetch/parse failed for '%s'", symbol)
            return None

        rows = payload.get("data") or []
        log.info("Scraped %d corporate-actions rows for '%s'", len(rows), symbol)
        return rows

    @staticmethod
    def _augment_iv_history_url(feed_url: str, start: str | None = None,
                               end: str | None = None) -> str:
        """Restrict the feed to a ``start``..``end`` window when given, else lift the row
        cap so the full daily series returns in one response.

        Barchart's grids paginate via ``limit`` (and sometimes ``maxRecords``); ~1000
        daily bars is ~4 CALENDAR years (250 trading days/yr), not two — measured
        2026-08-14, see below. Edited textually to avoid re-encoding the
        comma/paren-bearing ``fields`` param (same reasoning as _augment_history_url).

        VERIFIED 2026-08-14 against the live feed, so the param names are no longer a
        guess: a 2025-06-02..2025-06-13 request returned 10 rows, 10/10 inside the
        window. The unwindowed call returned n=1000 spanning 2022-08-17 → 2026-08-13,
        identical across SPY/AAPL/NVDA/XOM/KO — so the retention floor is a
        market-wide rolling ~1000-bar window, not a per-name one. The limit is kept
        generous so an ignored window would still return recent rows.
        """
        url = feed_url
        if start and end:
            for key, val in (("startDate", start), ("endDate", end)):
                if f"{key}=" in url:
                    url = re.sub(rf"{key}=[^&]*", f"{key}={val}", url)
                else:
                    url += ("&" if "?" in url else "?") + f"{key}={val}"
        if "limit=" in url:
            url = re.sub(r"limit=\d+", "limit=1000", url)
        else:
            url += ("&" if "?" in url else "?") + "limit=1000"
        url = re.sub(r"maxRecords=\d+", "maxRecords=1000", url)
        return url

    @staticmethod
    def _reissue_history_url(api_url: str, page_url: str) -> str:
        """Swap the feed's `symbol=` to the contract encoded in page_url.

        The page URL ends `/quotes/{ENCODED_SYMBOL}/price-history/historical`, and the
        feed already carries that same encoded symbol in `symbol=`, so substitution is
        a straight textual swap (no re-encoding).
        """
        m = re.search(r"/quotes/([^/]+)/price-history", page_url)
        if not m:
            return api_url
        symbol = m.group(1)
        if "symbol=" in api_url:
            return re.sub(r"symbol=[^&]*", f"symbol={symbol}", api_url, count=1)
        return api_url + ("&" if "?" in api_url else "?") + f"symbol={symbol}"

    @staticmethod
    def _augment_history_url(feed_url: str) -> str:
        """Lift the row cap and ensure bid/ask are in the `fields` list (string-safe).

        We edit the captured URL textually rather than re-encoding query params:
        the `fields` value contains commas/parens (e.g. `tradeTime.format(m/d/Y)`)
        that urlencode would mangle into a 400.
        """
        # 1000 daily bars >> any option's lifetime; the feed rejects limits above ~1000.
        url = re.sub(r"limit=\d+", "limit=1000", feed_url)
        if "limit=" not in url:
            url += ("&" if "?" in url else "?") + "limit=1000"
        if "bidPrice" not in url:
            # Append to the fields list — sits right before the next `&` param.
            if "&type=" in url:
                url = url.replace("&type=", "%2CbidPrice%2CaskPrice&type=", 1)
            else:
                url = re.sub(r"(fields=[^&]*)", r"\1%2CbidPrice%2CaskPrice", url, count=1)
        return url

    @classmethod
    def _history_rows_to_csv(cls, rows: list[dict]) -> str:
        """Map JSON feed rows to the legacy Download CSV schema (uses each row's `raw`)."""
        import csv as _csv
        import io

        buf = io.StringIO()
        writer = _csv.writer(buf)
        writer.writerow([label for label, _ in cls._HISTORY_COLUMNS])
        for row in rows:
            raw = row.get("raw") or {}
            out = []
            for _, key in cls._HISTORY_COLUMNS:
                val = raw.get(key, row.get(key, ""))
                out.append("" if val is None else val)
            writer.writerow(out)
        return buf.getvalue()

    async def _dismiss_modal(self) -> None:
        """Close Barchart's newsletter/ad modal if present.

        Its `.reveal-modal-bg` backdrop sits over the whole page and intercepts pointer
        events, so a plain `.click()` on the download button retries for 30s and never
        lands. Clicking the backdrop (its own `ng-click="close($event)"`) or Escape
        dismisses it.
        """
        try:
            backdrop = await self._page.query_selector(".reveal-modal-bg")
            if backdrop and await backdrop.is_visible():
                await backdrop.click(timeout=2000)
                await self._page.wait_for_selector(".reveal-modal-bg", state="hidden", timeout=5000)
        except Exception:
            try:
                await self._page.keyboard.press("Escape")
            except Exception:
                pass

    async def download_csv(self, url: str, max_retries: int = 3, base_delay: float = 5.0) -> str | None:
        """Navigate to url, click the first visible download button, return CSV text.

        The click→`expect_download` handshake occasionally times out with no HTTP
        error involved (modal reappearing after dismissal, slow render, a network
        blip before the download fires) — same transient-failure shape as the 429s
        `_get_with_retry` backs off on. Retry the click in place (re-dismissing the
        modal and re-locating the button each attempt, since a reload could have
        reset the DOM) rather than re-navigating, which would cost another full
        page load per attempt.
        """
        log.info("Navigating to '%s'", url)
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self._page.wait_for_load_state("networkidle", timeout=20000)
        await self._dismiss_modal()

        for attempt in range(max_retries + 1):
            download_btn = None
            for el in await self._page.query_selector_all("a.download, a[class*='download']"):
                try:
                    if await el.is_visible():
                        download_btn = el
                        break
                except Exception:
                    pass

            if not download_btn:
                log.warning("No visible download button on '%s'", url)
                return None

            try:
                await self._dismiss_modal()
                async with self._page.expect_download(timeout=20000) as dl_info:
                    await download_btn.click()
                dl = await dl_info.value
                tmp = Path(f"/tmp/barchart_{id(dl)}.csv")
                await dl.save_as(str(tmp))
                content = tmp.read_text(encoding="utf-8", errors="replace")
                tmp.unlink(missing_ok=True)
                log.info("Downloaded CSV from '%s' — %d bytes", url, len(content))
                return content
            except Exception:
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    log.warning(
                        "CSV download attempt %d/%d failed on '%s' — retrying in %.0fs",
                        attempt + 1, max_retries + 1, url, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    log.exception("CSV download failed on '%s' after %d attempts", url, max_retries + 1)
                    return None
