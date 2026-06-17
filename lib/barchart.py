"""
Barchart browser session — authentication and CSV download.

BarchartSession manages a single Playwright browser instance with cookie reuse.
Use as an async context manager; inject into scrapers rather than constructing inline.
"""
import asyncio
import json
import logging
import re
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext

log = logging.getLogger(__name__)


def _safe_err(exc: BaseException) -> str:
    """Return exception string with the Playwright 'Call log:' section stripped.

    Playwright appends the full HTTP call log (headers, cookies, tokens) to error
    messages when a request context is disposed on interrupt. Strip it so credentials
    never appear in logs.
    """
    s = str(exc)
    cut = s.find("\nCall log:")
    return s[:cut] if cut != -1 else s


class BarchartSession:
    _BASE = "https://www.barchart.com"
    _USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    _COOKIE_MAX_AGE = 8 * 3600  # seconds

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
        cookies_fresh = (
            self._cookies_path.exists()
            and (time.time() - self._cookies_path.stat().st_mtime) < self._COOKIE_MAX_AGE
        )
        if cookies_fresh:
            log.debug("Loading cached Barchart cookies")
            await self._context.add_cookies(json.loads(self._cookies_path.read_text()))
            await self._page.goto(
                f"{self._BASE}/options/unusual-activity/stocks",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            if await self._page.query_selector(
                "[data-ng-controller='AccountDropdownCtrl'], .user-account, [class*='account']"
            ):
                log.info("Reusing cached Barchart session")
                return True
            log.info("Cached session expired — re-logging in")

        log.info("Logging in to Barchart")
        await self._page.goto(f"{self._BASE}/login", wait_until="domcontentloaded", timeout=30000)
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
            log.error("Login failed: still on login page after submit")
            return False

        self._cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self._cookies_path.write_text(json.dumps(await self._context.cookies()))
        log.info("Login successful — session saved")
        return True

    # Columns of the legacy "Download" CSV, kept identical so cached files and
    # lib.barchart_options.parse_history_series keep working unchanged.
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
        pass_headers = {k: headers[k] for k in ("x-xsrf-token", "referer") if k in headers}
        # Remember this authenticated feed so fetch_history_fast can re-issue it for
        # other contracts without navigating to each one's page.
        self._history_feed = (api_url, pass_headers)

        try:
            resp = await self._page.request.get(api_url, headers=pass_headers, timeout=timeout_ms)
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
            resp = await self._page.request.get(reissue_url, headers=headers, timeout=timeout_ms)
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
            log.error("Re-issued feed failed for '%s' — re-navigating: %s", page_url, _safe_err(e))

        return await self.fetch_history_csv(page_url, timeout_ms)

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

    async def download_csv(self, url: str) -> str | None:
        """Navigate to url, click the first visible download button, return CSV text."""
        log.info("Navigating to '%s'", url)
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self._page.wait_for_load_state("networkidle", timeout=20000)

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
            log.exception("CSV download failed on '%s'", url)
            return None
