"""
IBKR Flex Web Service — token-authenticated report API.

This is a *different* IBKR surface than `lib.ibkr.client`: no local gateway,
no browser login, no port — just an HTTPS GET with a long-lived token. The
protocol is a two-step handshake (SendRequest to queue the report,
GetStatement to fetch it) because Flex statements are generated
asynchronously on IBKR's side; a query for a wide date range can take the
service several seconds to assemble, so both steps can come back with
"not ready yet" (error code 1019) rather than the finished report/reference.
Transport and parsing only, mirroring `IBKRClient`'s role for the Client
Portal Gateway — no business logic here.

An error envelope is told apart from a report body by its `<Status>`, and
`Fail` is NOT the only non-success value — a rate limit (1018) comes back as
`Warn`. Anything carrying an `<ErrorCode>` is therefore an error whatever its
status says, because the one thing this module must never do is hand an error
envelope downstream as if it were a statement: the parser then diagnoses the
sections the envelope does not have instead of the error it actually is.

A Flex query is scoped to the SECTIONS it was saved with, so "trades" and
"open positions" are two separate queries with two separate ids
(`IBKR_FLEX_QUERY_TRADES_ID`, `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID`) against
ONE token. `send_request`/`fetch` therefore take an optional per-call
`query_id`, so both run through a single client rather than duplicating the
token handling — the one part of this module that must not be copied around.

CRITICAL: the token is a long-lived secret (effectively a password with no
rotation prompt) — it must never be written to a log, including inside a
logged request URL, which is why every logged URL goes through
`_redact_url` rather than being logged raw.
"""
from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

log = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"

# The two env vars naming the saved queries. A Flex query is scoped to the
# SECTIONS it was defined with, so trades and open positions are normally two
# separate saved queries with two separate ids — hence the "TRADES" in the
# first name. Pointing BOTH at one query saved with both sections is supported
# and costs one handshake instead of two; `scripts/journal/flexparse.py` splits
# the sections apart.
_QUERY_ID_ENV = "IBKR_FLEX_QUERY_TRADES_ID"
POSITIONS_QUERY_ID_ENV = "IBKR_FLEX_OPEN_POSITIONS_QUERY_ID"

# The two retryable Flex errors, both of them transient states of the service
# rather than anything wrong with the request: 1019 is "the statement is still
# being assembled", 1018 is "you have asked this token for too much too
# quickly" — which the journal trips routinely, because it runs TWO handshakes
# (trades then positions) back to back on one token. Every other code (bad
# token, unknown query, no data for the period, ...) is fatal and must surface
# immediately rather than being polled against.
_STATEMENT_IN_PROGRESS_CODE = 1019
_RATE_LIMITED_CODE = 1018
_RETRYABLE_CODES = frozenset({_STATEMENT_IN_PROGRESS_CODE, _RATE_LIMITED_CODE})


class FlexError(RuntimeError):
    """A fatal (non-retryable) response from the Flex Web Service.

    Carries `.code` and `.message` separately from the exception text so a
    caller can branch on the numeric IBKR error code (e.g. to special-case
    "no data for that period") without parsing prose out of `str(exc)`.
    """

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Flex Web Service error {code}: {message}")


def _redact_url(url: str) -> str:
    """Strip the `t=` (token) query parameter before a URL is logged.

    `requests` builds the fully-qualified URL — including every query
    param we passed — onto `Response.url`; logging that verbatim would put
    the token in plaintext on disk. Every other param (q, v, ...) is
    harmless and kept, since redacting the whole URL would make the log
    useless for debugging.
    """
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [(key, "REDACTED" if key == "t" else value) for key, value in query]
    return urlunsplit(parsed._replace(query=urlencode(redacted)))


def _try_parse_envelope(text: str) -> ET.Element | None:
    """Parse `text` as a Flex status envelope, or report that it isn't one.

    Both steps of the handshake can return either a `<...Response>` XML
    envelope (carrying `<Status>Success|Fail</Status>`) or, on a successful
    GetStatement, the raw report body verbatim (CSV text for a CSV-format
    query; XML with no `<Status>` element for an XML-format one). Those two
    shapes are told apart by whether the parsed root has a `<Status>` child
    at all — not by whether the text parses as XML, since a real XML-format
    report body IS valid XML but is never a status envelope. Returns None
    for anything that isn't a status envelope (including non-XML text,
    which `ElementTree` would otherwise raise on).
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    if root.find("Status") is None:
        return None
    return root


def trades_query_id_from_env() -> str | None:
    """The trades query id, or None when it is not configured.

    Read at construction rather than at call time so `FlexClient()` with no
    args is exactly what `os.environ` held when it was built — the same
    contract every other `lib.ibkr` client has.
    """
    return os.environ.get(_QUERY_ID_ENV) or None


def positions_query_id_from_env() -> str | None:
    """The OpenPositions query id, or None when the operator has not made one.

    Returning None rather than raising is deliberate: the positions query is
    OPTIONAL. Without it the journal still runs, netting the open book from
    fills exactly as it did before — see `scripts/journal/flexparse.py`.
    """
    return os.environ.get(POSITIONS_QUERY_ID_ENV) or None


class FlexClient:
    """Client for the IBKR Flex Web Service's two-step report handshake.

    The transport is injectable — pass `session` to run fully offline in
    tests, mirroring `IBKRClient`.
    """

    def __init__(
        self,
        token: str | None = None,
        query_id: str | None = None,
        *,
        session: requests.Session | None = None,
        base_url: str | None = None,
        max_attempts: int = 10,
        poll_delay: float = 5.0,
        rate_limit_delay: float = 30.0,
        timeout: float = 30.0,
    ) -> None:
        # Falling back to the env vars here (rather than at call time) means
        # a caller that constructs `FlexClient()` with no args gets exactly
        # what `os.environ` holds at construction, which is what every other
        # `lib.ibkr` client does — predictable, and easy to override per-test.
        self.token = token or os.environ.get("IBKR_FLEX_TOKEN")
        self.query_id = query_id or trades_query_id_from_env()
        self.session = session if session is not None else requests.Session()
        self.base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self.max_attempts = max_attempts
        self.poll_delay = poll_delay
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout

    # -- config guards -------------------------------------------------

    def _require_token(self) -> None:
        # Raised here, not left to surface as an HTTP 401 further down —
        # a bare auth failure from IBKR's servers reads like a broken
        # integration; naming the missing env var points straight at the fix.
        if not self.token:
            raise RuntimeError(
                "IBKR_FLEX_TOKEN is not set. Add it to your .env (see .env.example)."
            )

    def _resolve_query_id(self, query_id: str | None) -> str:
        """The query to run: an explicit override, else the client's default.

        The override exists so ONE client (one token, one session, one retry
        policy) can drive both saved queries. Constructing a second client per
        query would work too, but would duplicate the token handling — the one
        part of this module that must not be copied around.
        """
        resolved = query_id or self.query_id
        if not resolved:
            raise RuntimeError(
                f"{_QUERY_ID_ENV} is not set. Add it to your .env (see .env.example)."
            )
        return resolved

    # -- transport -------------------------------------------------------

    def _get_with_retry(self, url: str, params: dict) -> tuple[ET.Element | None, str]:
        """GET `url`, polling through the retryable Flex errors — 1019
        ("statement generation in progress") and 1018 ("too many requests") —
        on either step of the handshake. See the module docstring for why both
        steps can return them.

        Returns `(envelope, text)`: `envelope` is the parsed `<Status>`
        element's root when the response is a SUCCESSFUL status envelope, or
        None when it's a raw report body (the success case for GetStatement).
        An envelope is judged on its `<ErrorCode>`, not only on a `Fail`
        status, because a rate limit arrives as `Warn` and would otherwise be
        returned to the caller as though it were a statement. Any error that
        isn't retryable — or a retryable one once `max_attempts` is exhausted
        — raises `FlexError` immediately.
        """
        attempt = 0
        while True:
            attempt += 1
            resp = self.session.request("GET", url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            text = resp.text
            log.debug("Flex GET %s -> %d bytes", _redact_url(getattr(resp, "url", url)), len(text))

            envelope = _try_parse_envelope(text)
            if envelope is None:
                return None, text
            status = envelope.findtext("Status")
            code = int(envelope.findtext("ErrorCode") or 0)
            if status == "Success" and not code:
                return envelope, text

            message = envelope.findtext("ErrorMessage") or ""
            if code in _RETRYABLE_CODES and attempt < self.max_attempts:
                # A rate limit needs a longer wait than a statement that is
                # merely still assembling: polling it at `poll_delay` is what
                # provoked it in the first place.
                delay = (self.rate_limit_delay if code == _RATE_LIMITED_CODE
                         else self.poll_delay)
                log.warning(
                    "Flex statement not ready yet (error %d: %s, attempt %d/%d) "
                    "— retrying in %.1fs",
                    code, message, attempt, self.max_attempts, delay,
                )
                if delay:
                    time.sleep(delay)
                continue

            log.error("Flex Web Service error %d (status %s): %s", code, status, message)
            raise FlexError(code, message)

    # -- public API --------------------------------------------------------

    def send_request(self, query_id: str | None = None) -> tuple[str, str]:
        """Step 1: queue the report. Returns `(reference_code, statement_url)`.

        `query_id` overrides the client's default for this call only — how the
        open-positions query is run through the same client as the trades one.
        """
        self._require_token()
        resolved = self._resolve_query_id(query_id)
        url = f"{self.base_url}/SendRequest"
        params = {"t": self.token, "q": resolved, "v": "3"}
        envelope, _ = self._get_with_retry(url, params)
        if envelope is None:
            # SendRequest always answers with a status envelope, success or
            # fail — landing here means the service returned something else
            # entirely, which we treat as a fatal (unretryable) surprise.
            raise FlexError(0, "SendRequest returned a non-envelope response")
        reference_code = envelope.findtext("ReferenceCode")
        statement_url = envelope.findtext("Url")
        if not reference_code or not statement_url:
            raise FlexError(0, "SendRequest succeeded but omitted ReferenceCode/Url")
        return reference_code, statement_url

    def get_statement(self, reference_code: str, statement_url: str) -> str:
        """Step 2: fetch the report body at `statement_url` for `reference_code`.

        Returns the raw report text verbatim (CSV for a CSV-format query).
        `query_id` plays no part here — `reference_code` already identifies
        the queued report — so only the token is required.
        """
        self._require_token()
        params = {"q": reference_code, "t": self.token, "v": "3"}
        envelope, text = self._get_with_retry(statement_url, params)
        if envelope is not None:
            # A report body is never a status envelope, so an envelope here is
            # the service answering something other than the statement. Errors
            # already raised inside `_get_with_retry`; this catches the
            # remaining shape (a bare Success envelope with no report) so that
            # NOTHING but an actual statement can be returned to the caller —
            # the downstream parser would otherwise diagnose the envelope's
            # missing sections instead of the transport problem.
            raise FlexError(0, "GetStatement returned a "
                               f"<{envelope.tag}> status envelope, not a report body")
        return text

    def fetch(self, query_id: str | None = None) -> str:
        """Run the full handshake and return the report body.

        `query_id` selects which saved query to run, defaulting to the
        client's own. Two calls on one client fetch two different statements.
        """
        reference_code, statement_url = self.send_request(query_id)
        return self.get_statement(reference_code, statement_url)
