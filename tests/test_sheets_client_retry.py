"""
Tests for lib/sheets_client.RetryingHTTPClient — the transient-failure retry.

The policy has two edges that matter more than the backoff itself: an auth
failure must NOT be retried (waiting cannot fix a revoked token, and backing
off through one hides the diagnosis), and `values:append` must NOT be retried
(a repeated append can duplicate a row on a tab with no dedup key).
"""
from __future__ import annotations

import pytest
from gspread.exceptions import APIError
from gspread.http_client import HTTPClient

from lib import sheets_client

APPEND_URL = "https://sheets.googleapis.com/v4/spreadsheets/ID/values/Tab!A1:append"
VALUES_URL = "https://sheets.googleapis.com/v4/spreadsheets/ID/values/Tab!A1:Z1000"
GRID_URL = "https://sheets.googleapis.com/v4/spreadsheets/ID:batchUpdate"
CLEAR_URL = "https://sheets.googleapis.com/v4/spreadsheets/ID/values:batchClear"


class _FakeResponse:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = f"status {status_code}"

    def json(self):
        return {"error": {"code": self.status_code, "message": self.text,
                          "status": "ERROR"}}


def _api_error(status):
    return APIError(_FakeResponse(status))


def _client(outcomes, monkeypatch):
    monkeypatch.setattr(sheets_client.time, "sleep", lambda _s: None)

    class _Client(sheets_client.RetryingHTTPClient):
        def __init__(self):
            self.outcomes = list(outcomes)
            self.calls = 0

    def _base_request(self, method, endpoint, *args, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(HTTPClient, "request", _base_request)
    return _Client()


def test_transient_error_is_retried_then_succeeds(monkeypatch):
    client = _client([_api_error(503), _api_error(500), "ok"], monkeypatch)
    assert client.request("get", VALUES_URL) == "ok"
    assert client.calls == 3


def test_auth_error_fails_immediately(monkeypatch):
    """401/403 mean the token is bad — retrying only delays the real message."""
    client = _client([_api_error(401), "never reached"], monkeypatch)
    with pytest.raises(APIError):
        client.request("get", VALUES_URL)
    assert client.calls == 1


def test_not_found_fails_immediately(monkeypatch):
    client = _client([_api_error(404), "never reached"], monkeypatch)
    with pytest.raises(APIError):
        client.request("get", VALUES_URL)
    assert client.calls == 1


def test_append_is_never_retried(monkeypatch):
    """A repeated append can duplicate a row; the run must die instead."""
    client = _client([_api_error(503), "never reached"], monkeypatch)
    with pytest.raises(APIError):
        client.request("post", APPEND_URL)
    assert client.calls == 1


def test_grid_mutation_is_never_retried(monkeypatch):
    """`<id>:batchUpdate` covers insert/delete rows — not safe to repeat."""
    client = _client([_api_error(503), "never reached"], monkeypatch)
    with pytest.raises(APIError):
        client.request("post", GRID_URL)
    assert client.calls == 1


def test_values_write_and_batch_clear_are_retried(monkeypatch):
    """A fixed-range PUT and a batchClear are idempotent — repeating is safe."""
    put = _client([_api_error(503), "ok"], monkeypatch)
    assert put.request("put", VALUES_URL) == "ok"
    assert put.calls == 2

    clear = _client([_api_error(503), "ok"], monkeypatch)
    assert clear.request("post", CLEAR_URL) == "ok"
    assert clear.calls == 2


def test_connection_error_is_retried(monkeypatch):
    client = _client([sheets_client.RequestsConnectionError("boom"), "ok"], monkeypatch)
    assert client.request("get", VALUES_URL) == "ok"
    assert client.calls == 2


def test_gives_up_after_max_attempts_and_reraises_api_error(monkeypatch):
    outcomes = [_api_error(503)] * sheets_client._RETRY_MAX_ATTEMPTS
    client = _client(outcomes, monkeypatch)
    with pytest.raises(APIError):
        client.request("get", VALUES_URL)
    assert client.calls == sheets_client._RETRY_MAX_ATTEMPTS


def test_retry_after_header_is_honoured():
    response = _FakeResponse(429, headers={"Retry-After": "7"})
    assert sheets_client._retry_delay(0, response) == 7.0


def test_retry_after_is_capped():
    response = _FakeResponse(429, headers={"Retry-After": "9999"})
    assert sheets_client._retry_delay(0, response) == sheets_client._RETRY_MAX_DELAY


def test_backoff_grows_and_is_jittered():
    lo, hi = [], []
    for attempt in range(4):
        delays = [sheets_client._retry_delay(attempt) for _ in range(50)]
        ceiling = min(sheets_client._RETRY_BASE_DELAY * 2 ** attempt,
                      sheets_client._RETRY_MAX_DELAY)
        assert all(ceiling * 0.5 <= d <= ceiling for d in delays)
        lo.append(min(delays))
        hi.append(max(delays))
    assert hi == sorted(hi)          # grows
    assert len(set(lo)) > 1          # jittered, not a fixed schedule
