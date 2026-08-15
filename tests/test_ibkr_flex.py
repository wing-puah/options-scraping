"""Unit tests for `lib.ibkr.flex` — fully offline, mocked transport, no network.

Covers the behaviours the module docstring calls out as load-bearing:
  - the happy-path two-step handshake (SendRequest -> GetStatement)
  - error 1019 ("statement generation in progress") is polled and retried,
    on either step, until it resolves or `max_attempts` is exhausted
  - any other error code is fatal immediately, carrying code + message
  - a missing token/query_id raises before any network call, naming the var
  - the token is never written to logs, even when a URL is logged
  - a successful GetStatement can return a raw (non-XML) report body verbatim
"""
from __future__ import annotations

import logging

import pytest
import requests

from lib.ibkr.flex import (FlexClient, FlexError,
                           positions_query_id_from_env,
                           trades_query_id_from_env)

_SUCCESS_ENVELOPE = """<FlexStatementResponse timestamp="now">
<Status>Success</Status>
<ReferenceCode>123456789</ReferenceCode>
<Url>https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement</Url>
</FlexStatementResponse>"""

_IN_PROGRESS_ENVELOPE = """<FlexStatementResponse timestamp="now">
<Status>Fail</Status>
<ErrorCode>1019</ErrorCode>
<ErrorMessage>Statement generation in progress. Please try again shortly.</ErrorMessage>
</FlexStatementResponse>"""

_FATAL_ENVELOPE = """<FlexStatementResponse timestamp="now">
<Status>Fail</Status>
<ErrorCode>1003</ErrorCode>
<ErrorMessage>Invalid token or query ID.</ErrorMessage>
</FlexStatementResponse>"""

# The rate limit, verbatim from a real pull: note the status is Warn, NOT Fail
# — the shape that used to be handed downstream as if it were a statement.
_RATE_LIMITED_ENVELOPE = """<FlexStatementResponse timestamp='15 August, 2026 04:46 AM EDT'>
<Status>Warn</Status>
<ErrorCode>1018</ErrorCode>
<ErrorMessage>Too many requests have been made from this token. Please try again shortly.</ErrorMessage>
</FlexStatementResponse>"""

_CSV_BODY = "ClientAccountID,Symbol,TradeDate\nU1234567,AAPL,20260814\n"


# --------------------------------------------------------------------------
# Fake transport
# --------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, text, url, status_code=200):
        self.text = text
        self.url = url
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


class QueueSession:
    """Fake `requests.Session` — pops a queued response per call, in order.

    Mirrors `lib.ibkr.client`'s test double: `FlexClient` calls
    `session.request(method, url, **kwargs)`, never `.get()`, so a fake only
    needs to implement `.request()`.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(responses, **kwargs) -> FlexClient:
    session = QueueSession(responses)
    kwargs.setdefault("token", "s3cr3t-token")
    kwargs.setdefault("query_id", "998877")
    kwargs.setdefault("poll_delay", 0)  # no real sleeping in tests
    kwargs.setdefault("rate_limit_delay", 0)
    return FlexClient(session=session, **kwargs)


def send_url(base="https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"):
    return f"{base}/SendRequest"


STATEMENT_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement"


# --------------------------------------------------------------------------
# happy path
# --------------------------------------------------------------------------

def test_fetch_two_step_success():
    client = make_client([
        FakeResponse(_SUCCESS_ENVELOPE, send_url() + "?t=s3cr3t-token&q=998877&v=3"),
        FakeResponse(_CSV_BODY, STATEMENT_URL + "?q=123456789&t=s3cr3t-token&v=3"),
    ])
    body = client.fetch()
    assert body == _CSV_BODY
    assert len(client.session.calls) == 2


def test_send_request_returns_reference_code_and_url():
    client = make_client([FakeResponse(_SUCCESS_ENVELOPE, send_url())])
    reference_code, statement_url = client.send_request()
    assert reference_code == "123456789"
    assert statement_url == STATEMENT_URL


def test_get_statement_returns_raw_body_verbatim():
    client = make_client([FakeResponse(_CSV_BODY, STATEMENT_URL)])
    body = client.get_statement("123456789", STATEMENT_URL)
    assert body == _CSV_BODY


# --------------------------------------------------------------------------
# 1019 retry
# --------------------------------------------------------------------------

def test_1019_retried_then_succeeds():
    client = make_client([
        FakeResponse(_IN_PROGRESS_ENVELOPE, send_url()),
        FakeResponse(_IN_PROGRESS_ENVELOPE, send_url()),
        FakeResponse(_SUCCESS_ENVELOPE, send_url()),
    ], max_attempts=5)
    reference_code, statement_url = client.send_request()
    assert reference_code == "123456789"
    assert statement_url == STATEMENT_URL
    assert len(client.session.calls) == 3


def test_1019_retried_on_get_statement_step():
    client = make_client([
        FakeResponse(_IN_PROGRESS_ENVELOPE, STATEMENT_URL),
        FakeResponse(_CSV_BODY, STATEMENT_URL),
    ], max_attempts=5)
    body = client.get_statement("123456789", STATEMENT_URL)
    assert body == _CSV_BODY
    assert len(client.session.calls) == 2


def test_1019_exceeding_max_attempts_raises():
    client = make_client([
        FakeResponse(_IN_PROGRESS_ENVELOPE, send_url()),
        FakeResponse(_IN_PROGRESS_ENVELOPE, send_url()),
        FakeResponse(_IN_PROGRESS_ENVELOPE, send_url()),
    ], max_attempts=3)
    with pytest.raises(FlexError) as exc_info:
        client.send_request()
    assert exc_info.value.code == 1019
    assert len(client.session.calls) == 3


# --------------------------------------------------------------------------
# 1018 rate limit — a `Warn`, not a `Fail`
# --------------------------------------------------------------------------

def test_rate_limited_envelope_is_never_returned_as_a_statement():
    """The regression: `<Status>Warn</Status>` with error 1018 used to fall
    through as the report body, so `flexparse` was handed IBKR's error XML and
    reported "this query has no OpenPositions section" — sending the operator
    to re-save a query that was fine all along."""
    client = make_client([FakeResponse(_RATE_LIMITED_ENVELOPE, STATEMENT_URL)],
                         max_attempts=1)
    with pytest.raises(FlexError) as exc_info:
        client.get_statement("123456789", STATEMENT_URL)
    assert exc_info.value.code == 1018
    assert "Too many requests" in exc_info.value.message


def test_rate_limit_is_retried_then_succeeds():
    client = make_client([
        FakeResponse(_RATE_LIMITED_ENVELOPE, STATEMENT_URL),
        FakeResponse(_CSV_BODY, STATEMENT_URL),
    ], max_attempts=5)
    assert client.get_statement("123456789", STATEMENT_URL) == _CSV_BODY
    assert len(client.session.calls) == 2


def test_rate_limit_waits_longer_than_a_statement_still_generating(monkeypatch):
    slept = []
    monkeypatch.setattr("lib.ibkr.flex.time.sleep", slept.append)
    client = make_client([
        FakeResponse(_IN_PROGRESS_ENVELOPE, send_url()),
        FakeResponse(_RATE_LIMITED_ENVELOPE, send_url()),
        FakeResponse(_SUCCESS_ENVELOPE, send_url()),
    ], max_attempts=5, poll_delay=5.0, rate_limit_delay=30.0)
    client.send_request()
    assert slept == [5.0, 30.0]


def test_success_envelope_from_get_statement_is_refused():
    """Belt and braces: only an actual report body may leave `get_statement`,
    so nothing that isn't a statement can reach the parser."""
    client = make_client([FakeResponse(_SUCCESS_ENVELOPE, STATEMENT_URL)])
    with pytest.raises(FlexError, match="not a report body"):
        client.get_statement("123456789", STATEMENT_URL)


# --------------------------------------------------------------------------
# fatal errors
# --------------------------------------------------------------------------

def test_fatal_error_code_raises_with_code_and_message():
    client = make_client([FakeResponse(_FATAL_ENVELOPE, send_url())])
    with pytest.raises(FlexError) as exc_info:
        client.send_request()
    assert exc_info.value.code == 1003
    assert exc_info.value.message == "Invalid token or query ID."
    assert "1003" in str(exc_info.value)
    assert "Invalid token or query ID." in str(exc_info.value)


def test_fatal_error_is_not_retried():
    # Only one response queued — a retry would raise IndexError from the
    # fake session popping an empty list, proving no second call happened.
    client = make_client([FakeResponse(_FATAL_ENVELOPE, send_url())])
    with pytest.raises(FlexError):
        client.send_request()
    assert len(client.session.calls) == 1


# --------------------------------------------------------------------------
# missing config
# --------------------------------------------------------------------------

def test_missing_token_raises_before_any_network_call(monkeypatch):
    monkeypatch.delenv("IBKR_FLEX_TOKEN", raising=False)
    session = QueueSession([])
    client = FlexClient(token=None, query_id="998877", session=session)
    with pytest.raises(RuntimeError, match="IBKR_FLEX_TOKEN"):
        client.send_request()
    assert client.session.calls == []


def test_missing_query_id_raises_before_any_network_call(monkeypatch):
    monkeypatch.delenv("IBKR_FLEX_QUERY_TRADES_ID", raising=False)
    session = QueueSession([])
    client = FlexClient(token="s3cr3t-token", query_id=None, session=session)
    with pytest.raises(RuntimeError, match="IBKR_FLEX_QUERY_TRADES_ID"):
        client.send_request()
    assert client.session.calls == []


def test_get_statement_does_not_require_query_id(monkeypatch):
    monkeypatch.delenv("IBKR_FLEX_QUERY_TRADES_ID", raising=False)
    session = QueueSession([FakeResponse(_CSV_BODY, STATEMENT_URL)])
    client = FlexClient(token="s3cr3t-token", query_id=None, session=session)
    assert client.get_statement("123456789", STATEMENT_URL) == _CSV_BODY


# --------------------------------------------------------------------------
# Two query ids, one token — the trades/positions query split
# --------------------------------------------------------------------------
def test_trades_query_id_from_env_is_none_when_unset(monkeypatch):
    monkeypatch.delenv("IBKR_FLEX_QUERY_TRADES_ID", raising=False)
    assert trades_query_id_from_env() is None


def test_trades_query_id_env_is_the_client_default(monkeypatch):
    monkeypatch.setenv("IBKR_FLEX_QUERY_TRADES_ID", "current-id")
    client = FlexClient(token="s3cr3t-token", session=QueueSession([]))
    assert client.query_id == "current-id"


def test_per_call_query_id_override_reaches_the_wire(monkeypatch):
    """One client, one token, drives BOTH the trades and the open-positions
    query — the override is how `fetch(query_id=...)` selects which without
    constructing a second client."""
    session = QueueSession([
        FakeResponse(_SUCCESS_ENVELOPE, send_url()),
    ])
    client = FlexClient(token="s3cr3t-token", query_id="trades-id", session=session)
    client.send_request(query_id="positions-id")
    method, url, kwargs = session.calls[0]
    assert kwargs["params"]["q"] == "positions-id"


def test_default_query_id_used_when_no_override_given():
    session = QueueSession([FakeResponse(_SUCCESS_ENVELOPE, send_url())])
    client = FlexClient(token="s3cr3t-token", query_id="trades-id", session=session)
    client.send_request()
    _, _, kwargs = session.calls[0]
    assert kwargs["params"]["q"] == "trades-id"


def test_positions_query_id_from_env_is_none_when_unset(monkeypatch):
    monkeypatch.delenv("IBKR_FLEX_OPEN_POSITIONS_QUERY_ID", raising=False)
    assert positions_query_id_from_env() is None


def test_positions_query_id_from_env_returns_the_configured_id(monkeypatch):
    monkeypatch.setenv("IBKR_FLEX_OPEN_POSITIONS_QUERY_ID", "pos-id")
    assert positions_query_id_from_env() == "pos-id"


# --------------------------------------------------------------------------
# token redaction
# --------------------------------------------------------------------------

def test_token_never_appears_in_logs(caplog):
    caplog.set_level(logging.DEBUG, logger="lib.ibkr.flex")
    client = make_client([
        FakeResponse(_IN_PROGRESS_ENVELOPE, send_url() + "?t=s3cr3t-token&q=998877&v=3"),
        FakeResponse(_SUCCESS_ENVELOPE, send_url() + "?t=s3cr3t-token&q=998877&v=3"),
    ])
    client.send_request()
    assert "s3cr3t-token" not in caplog.text


def test_fatal_error_message_logged_without_token(caplog):
    caplog.set_level(logging.DEBUG, logger="lib.ibkr.flex")
    client = make_client([FakeResponse(_FATAL_ENVELOPE, send_url() + "?t=s3cr3t-token&q=998877&v=3")])
    with pytest.raises(FlexError):
        client.send_request()
    assert "s3cr3t-token" not in caplog.text


# --------------------------------------------------------------------------
# non-XML statement body
# --------------------------------------------------------------------------

def test_non_xml_statement_body_returned_verbatim():
    weird_body = "not xml at all, just << some report >> text\nline two"
    client = make_client([FakeResponse(weird_body, STATEMENT_URL)])
    assert client.get_statement("123456789", STATEMENT_URL) == weird_body
