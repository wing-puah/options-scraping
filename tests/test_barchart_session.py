"""Barchart login retry + failure diagnosis.

These drive :meth:`BarchartSession._authenticate` against a fake Playwright page
rather than a browser: the failure being guarded here (a submit that is accepted
and leaves the page on /login) only reproduces from a GitHub-runner IP, so a test
that needed the real site could not assert on it at all.
"""
import asyncio
import json
import time

from lib.barchart.session import BarchartSession


# ── Fakes ─────────────────────────────────────────────────────────────────────

class FakePage:
    """Minimal Playwright Page. `lands_on` scripts one URL per goto/submit pair."""

    def __init__(self, outcomes, body="Sign in", error_text=None):
        # outcomes: URL the page shows after each submit, consumed one per attempt
        self._outcomes = list(outcomes)
        self.url = ""
        self._body = body
        self._error_text = error_text
        self.submits = 0
        self.screenshots = 0

    async def goto(self, url, **kw):
        self.url = url

    async def fill(self, selector, value):
        pass

    async def click(self, selector):
        self.submits += 1
        self.url = self._outcomes.pop(0) if self._outcomes else self.url

    async def wait_for_function(self, expr, **kw):
        if "/login" in self.url:
            raise TimeoutError("still on login")

    async def wait_for_selector(self, selector, **kw):
        raise TimeoutError("no marker")

    async def inner_text(self, selector):
        # A real body contains the error element's text too — keep that true here,
        # or the challenge-hint scan looks broken when it is the fake that is wrong.
        return f"{self._body} {self._error_text}" if self._error_text else self._body

    async def query_selector_all(self, selector):
        if self._error_text and "error" in selector:
            return [FakeElement(self._error_text)]
        return []

    async def screenshot(self, **kw):
        self.screenshots += 1

    async def content(self):
        return f"<html>{self._body}</html>"


class FakeElement:
    def __init__(self, text):
        self._text = text

    async def inner_text(self):
        return self._text


class FakeContext:
    def __init__(self, page):
        self.page = page
        self.closed = False

    async def new_page(self):
        return self.page

    async def add_cookies(self, cookies):
        pass

    async def cookies(self):
        return [{"name": "session", "value": "x"}]

    async def close(self):
        self.closed = True


class FakeBrowser:
    """Hands out a fresh context per new_context() so retries can be counted."""

    def __init__(self, page):
        self.page = page
        self.contexts = []

    async def new_context(self, **kw):
        ctx = FakeContext(self.page)
        self.contexts.append(ctx)
        return ctx


def build(tmp_path, outcomes, **page_kw):
    page = FakePage(outcomes, **page_kw)
    s = BarchartSession("a@b.c", "pw", tmp_path / "cookies.json", headless=True)
    s._browser = FakeBrowser(page)
    s._context = FakeContext(page)
    s._page = page
    return s, page


LOGIN = "https://www.barchart.com/login"
HOME = "https://www.barchart.com/"


# ── Retry ─────────────────────────────────────────────────────────────────────

def test_login_succeeds_first_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(BarchartSession, "_LOGIN_RETRY_DELAY", 0.0)
    s, page = build(tmp_path, [HOME])
    assert asyncio.run(s._authenticate()) is True
    assert page.submits == 1


def test_login_retries_and_recovers(tmp_path, monkeypatch):
    """The whole point of the retry: a run that would have died on attempt 1 now
    completes. A fresh CI login failed ~50% of the time on 2026-09-03."""
    monkeypatch.setattr(BarchartSession, "_LOGIN_RETRY_DELAY", 0.0)
    s, page = build(tmp_path, [LOGIN, LOGIN, HOME])
    assert asyncio.run(s._authenticate()) is True
    assert page.submits == 3


def test_login_gives_up_after_all_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(BarchartSession, "_LOGIN_RETRY_DELAY", 0.0)
    s, page = build(tmp_path, [LOGIN] * 5)
    assert asyncio.run(s._authenticate()) is False
    assert page.submits == BarchartSession._LOGIN_ATTEMPTS


def test_retry_uses_a_fresh_browser_context(tmp_path, monkeypatch):
    """A challenge cookie set on the way in would ride along in a reused context,
    so each retry must start from a new one — and close the old one."""
    monkeypatch.setattr(BarchartSession, "_LOGIN_RETRY_DELAY", 0.0)
    s, _ = build(tmp_path, [LOGIN, LOGIN, HOME])
    first = s._context
    asyncio.run(s._authenticate())
    assert len(s._browser.contexts) == 2      # one per retry, not per attempt
    assert first.closed


def test_backoff_grows_between_attempts(tmp_path, monkeypatch):
    delays = []
    monkeypatch.setattr(BarchartSession, "_LOGIN_RETRY_DELAY", 4.0)

    async def fake_sleep(d):
        delays.append(d)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    s, _ = build(tmp_path, [LOGIN] * 3)
    asyncio.run(s._authenticate())
    assert delays == [4.0, 8.0]


# ── Diagnosis ─────────────────────────────────────────────────────────────────

def test_diagnosis_reports_a_rendered_form_error(tmp_path, monkeypatch):
    monkeypatch.setattr(BarchartSession, "_LOGIN_RETRY_DELAY", 0.0)
    s, page = build(tmp_path, [LOGIN], error_text="Too many failed attempts.")
    page.url = LOGIN
    msg = asyncio.run(s._diagnose_login_failure())
    assert "Too many failed attempts." in msg
    assert "too many" in msg  # also flagged as a challenge hint


def test_diagnosis_quotes_the_body_when_nothing_rendered(tmp_path):
    """The failure actually seen in CI renders NO error — the body excerpt is the
    only evidence distinguishing it from a rejection, so it must be logged."""
    s, page = build(tmp_path, [LOGIN], body="Sign in Please enter your credentials.")
    page.url = LOGIN
    msg = asyncio.run(s._diagnose_login_failure())
    assert "no error rendered" in msg
    assert "Please enter your credentials." in msg


def test_diagnosis_survives_a_page_that_cannot_be_read(tmp_path):
    """A diagnosis that raised would replace the real failure with its own."""
    s, page = build(tmp_path, [LOGIN])
    page.url = LOGIN

    async def boom(*a, **kw):
        raise RuntimeError("page gone")

    page.inner_text = boom
    page.query_selector_all = boom
    msg = asyncio.run(s._diagnose_login_failure())
    assert LOGIN in msg


def test_debug_artifacts_are_opt_in(tmp_path, monkeypatch):
    """The failed page holds a filled-in email field — never dump it unasked."""
    monkeypatch.delenv("BARCHART_DEBUG_DIR", raising=False)
    s, page = build(tmp_path, [LOGIN])
    page.url = LOGIN
    asyncio.run(s._diagnose_login_failure())
    assert page.screenshots == 0

    out = tmp_path / "debug"
    monkeypatch.setenv("BARCHART_DEBUG_DIR", str(out))
    asyncio.run(s._diagnose_login_failure())
    assert page.screenshots == 1
    assert list(out.glob("login-fail-*.html"))


# ── Cookie reuse ──────────────────────────────────────────────────────────────

def test_fresh_cookies_short_circuit_the_login(tmp_path, monkeypatch):
    """The marker sits in a collapsed dropdown: it is attached, never visible.
    Waiting for visibility reported every live session as expired and forced a
    needless fresh login — the exact call that fails in CI."""
    monkeypatch.setattr(BarchartSession, "_LOGIN_RETRY_DELAY", 0.0)
    cookies = tmp_path / "cookies.json"
    cookies.write_text(json.dumps([{"name": "session", "value": "x"}]))
    s, page = build(tmp_path, [HOME])

    seen = {}

    async def wait_for_selector(selector, **kw):
        seen.update(kw)
        return object()

    page.wait_for_selector = wait_for_selector
    assert asyncio.run(s._authenticate()) is True
    assert seen.get("state") == "attached"
    assert page.submits == 0


def test_stale_cookies_are_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(BarchartSession, "_LOGIN_RETRY_DELAY", 0.0)
    cookies = tmp_path / "cookies.json"
    cookies.write_text(json.dumps([]))
    old = time.time() - BarchartSession._COOKIE_MAX_AGE - 60
    import os
    os.utime(cookies, (old, old))
    s, page = build(tmp_path, [HOME])
    assert asyncio.run(s._authenticate()) is True
    assert page.submits == 1


def test_login_saves_cookies_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(BarchartSession, "_LOGIN_RETRY_DELAY", 0.0)
    cookies = tmp_path / "cookies.json"
    s, _ = build(tmp_path, [HOME])
    asyncio.run(s._authenticate())
    assert json.loads(cookies.read_text()) == [{"name": "session", "value": "x"}]
