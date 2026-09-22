"""Tests for scripts/collector/fetch_iv_percentile.py's BarchartAuthError handling.

Two things are pinned here, both added 2026-09-22 alongside the CI fresh-runner
retry (journal.yml / scrape.yml / enrich-oi.yml / fetch-counterpart-iv.yml):

1. `main()`'s per-(prefix, date) loop must NOT swallow a Barchart LOGIN refusal
   into a generic "error" status and keep going — a refused login is IP-level,
   so every remaining pending pair would fail the same way, and swallowing it
   left this script exiting 0 even when every enrichment failed (see the
   module's `except BarchartAuthError: raise` clause).
2. The `__main__` guard maps an unhandled `BarchartAuthError` to the shared
   `BARCHART_AUTH_EXIT_CODE`, not Python's default 1, so a chained CI job can
   tell "retry on a fresh runner" apart from a real bug.
"""
import sys

import pytest

import fetch_iv_percentile
from fetch_iv_percentile import BARCHART_AUTH_EXIT_CODE, BarchartAuthError
from compile_flow import FLOW_PREFIXES


def _set_args(monkeypatch, *, date="2026-09-01"):
    monkeypatch.setattr(sys, "argv", ["fetch_iv_percentile.py", "--date", date])
    monkeypatch.setattr(fetch_iv_percentile, "get_drive_client", lambda: object())


def test_a_refused_login_propagates_instead_of_being_recorded_as_an_error(monkeypatch):
    _set_args(monkeypatch)
    calls = []

    def boom(client, prefix, d, **kw):
        calls.append(prefix)
        raise BarchartAuthError("Barchart authentication failed.")

    monkeypatch.setattr(fetch_iv_percentile, "enrich_prefix", boom)

    with pytest.raises(BarchartAuthError):
        fetch_iv_percentile.main()

    # Only the FIRST (prefix, date) pair was attempted — the refusal is
    # IP-level, so burning through the rest of FLOW_PREFIXES would only waste
    # doomed logins, not surface new information.
    assert calls == [FLOW_PREFIXES[0]]


def test_any_other_enrichment_failure_is_still_recorded_and_the_run_continues(monkeypatch):
    """Only the auth failure short-circuits the loop — a real bug in one
    (prefix, date) pair must not cost the others their chance to enrich."""
    _set_args(monkeypatch)
    calls = []

    def boom(client, prefix, d, **kw):
        calls.append(prefix)
        raise RuntimeError("something else broke")

    monkeypatch.setattr(fetch_iv_percentile, "enrich_prefix", boom)

    fetch_iv_percentile.main()  # must NOT raise

    assert calls == list(FLOW_PREFIXES)  # every prefix was still attempted


def test_main_with_auth_exit_maps_a_refused_login_to_the_shared_exit_code(monkeypatch):
    def boom():
        raise BarchartAuthError("Barchart authentication failed.")

    monkeypatch.setattr(fetch_iv_percentile, "main", boom)

    with pytest.raises(SystemExit) as exc_info:
        fetch_iv_percentile._main_with_auth_exit()

    assert exc_info.value.code == BARCHART_AUTH_EXIT_CODE
    assert BARCHART_AUTH_EXIT_CODE == 5


def test_main_with_auth_exit_leaves_a_clean_run_alone(monkeypatch):
    calls = []
    monkeypatch.setattr(fetch_iv_percentile, "main", lambda: calls.append(1))

    fetch_iv_percentile._main_with_auth_exit()  # must not raise/exit

    assert calls == [1]
