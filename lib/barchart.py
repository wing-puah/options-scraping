"""
Barchart browser session — authentication and CSV download.

BarchartSession manages a single Playwright browser instance with cookie reuse.
Use as an async context manager; inject into scrapers rather than constructing inline.
"""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext

log = logging.getLogger(__name__)


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
