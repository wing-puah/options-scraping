import asyncio
import csv as csvmod
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

import scrape_flow
from scrape_flow import is_market_hours, _download_and_upload, _already_collected

ET = ZoneInfo("America/New_York")

# Every _download_and_upload call now writes a staleness verdict. Redirect the
# manifest at the module level so no test ever touches the repo's real one.


@pytest.fixture(autouse=True)
def _isolate_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape_flow, "MANIFEST_PATH", tmp_path / "manifest.csv")
    return tmp_path / "manifest.csv"


TARGET = date(2026, 6, 2)


# ── is_market_hours ───────────────────────────────────────────────────────────

def test_during_market_hours():
    now = datetime(2026, 6, 2, 10, 0, tzinfo=ET)   # Tuesday 10:00
    assert is_market_hours(now) is True


def test_at_open():
    now = datetime(2026, 6, 2, 9, 30, tzinfo=ET)
    assert is_market_hours(now) is True


def test_at_close():
    now = datetime(2026, 6, 2, 16, 0, tzinfo=ET)
    assert is_market_hours(now) is True


def test_before_open():
    now = datetime(2026, 6, 2, 9, 29, tzinfo=ET)
    assert is_market_hours(now) is False


def test_after_close():
    now = datetime(2026, 6, 2, 16, 1, tzinfo=ET)
    assert is_market_hours(now) is False


def test_saturday():
    now = datetime(2026, 6, 6, 12, 0, tzinfo=ET)   # Saturday
    assert is_market_hours(now) is False


def test_sunday():
    now = datetime(2026, 6, 7, 12, 0, tzinfo=ET)   # Sunday
    assert is_market_hours(now) is False


# ── _download_and_upload ──────────────────────────────────────────────────────

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def make_session(csv_content: str | None) -> AsyncMock:
    session = AsyncMock()
    session.download_csv.return_value = csv_content
    return session


def make_client(file_exists_id: str | None = None, upload_id: str = "new-file-id") -> MagicMock:
    client = MagicMock()
    client.file_exists.return_value = file_exists_id
    client.upload.return_value = upload_id
    return client


def test_download_skips_when_already_exists():
    session = make_session(None)
    client = make_client(file_exists_id="existing-id")
    run_dt = datetime(2026, 6, 2, 10, 30, tzinfo=ET)

    result = _run(_download_and_upload(
        session, client, "http://example.com", "unusual-stocks", run_dt, "folder-id",
        target_date=TARGET))

    assert result == 0
    session.download_csv.assert_not_called()


def test_download_returns_minus1_on_download_failure():
    session = make_session(None)   # download returns None
    client = make_client(file_exists_id=None)
    run_dt = datetime(2026, 6, 2, 10, 30, tzinfo=ET)

    result = _run(_download_and_upload(
        session, client, "http://example.com", "unusual-stocks", run_dt, "folder-id",
        target_date=TARGET))

    assert result == -1
    client.upload.assert_not_called()


def test_download_returns_0_on_empty_csv():
    session = make_session("Symbol,Volume\n")   # header only, no data rows
    client = make_client(file_exists_id=None)
    run_dt = datetime(2026, 6, 2, 10, 30, tzinfo=ET)

    result = _run(_download_and_upload(
        session, client, "http://example.com", "unusual-stocks", run_dt, "folder-id",
        target_date=TARGET))

    assert result == 0
    client.upload.assert_not_called()


def test_download_uploads_and_returns_row_count(tmp_path):
    csv = "Symbol,Volume\nAAPL,1000\nMSFT,500\n"
    session = make_session(csv)
    client = make_client(file_exists_id=None, upload_id="uploaded-id")
    run_dt = datetime(2026, 6, 2, 10, 30, tzinfo=ET)

    with patch("scrape_flow.Path") as mock_path:
        real_path = MagicMock()
        real_path.__truediv__ = lambda self, x: tmp_path / x
        mock_path.return_value = real_path
        mock_path.side_effect = lambda p: Path(p)

        result = _run(_download_and_upload(
            session, client, "http://example.com", "unusual-stocks", run_dt, "folder-id",
            target_date=TARGET))

    assert result > 0
    client.upload.assert_called_once()


# ── _already_collected ────────────────────────────────────────────────────────

def test_already_collected_true_when_file_exists():
    from datetime import date

    client = MagicMock()
    client.list_files.return_value = [
        {"name": "unusual-stocks-20260602-1600.csv"},
    ]
    assert _already_collected(client, "unusual-stocks", date(2026, 6, 2)) is True


def test_already_collected_false_when_no_file():
    from datetime import date

    client = MagicMock()
    client.list_files.return_value = []
    assert _already_collected(client, "unusual-stocks", date(2026, 6, 2)) is False


def test_already_collected_false_when_different_date():
    from datetime import date

    client = MagicMock()
    client.list_files.return_value = [
        {"name": "unusual-stocks-20260601-1600.csv"},  # June 1, not June 2
    ]
    assert _already_collected(client, "unusual-stocks", date(2026, 6, 2)) is False


# ── staleness guard ───────────────────────────────────────────────────────────

def _flow_csv(rows: list[tuple[str, str, str]]) -> str:
    """Build a minimal flow CSV: (Symbol, Expires, Price~) per row."""
    head = "Symbol,Type,Strike,Expires,Trade,Size,Side,Premium,Time,Price~\n"
    body = "".join(
        f"{sym},Call,540,{exp},1,10,A,1000,10:00 ET,{px}\n" for sym, exp, px in rows
    )
    return head + body


GENUINE = _flow_csv([
    ("SPY",  "2026-06-19", "545.0"),
    ("AAPL", "2026-07-17", "210.0"),
    ("NVDA", "2026-06-05", "130.0"),
])


def _download(session, client, prefix="etfs-flow", **kw):
    run_dt = datetime(2026, 6, 2, 16, 0, tzinfo=ET)
    return _run(_download_and_upload(
        session, client, "http://example.com", prefix, run_dt, "folder-id",
        target_date=TARGET, **kw))


def test_guard_accepts_genuine_payload(tmp_path):
    session, client = make_session(GENUINE), make_client()
    with patch("scrape_flow.Path", side_effect=lambda p: tmp_path / Path(p).name):
        result = _download(session, client, spy_close=545.0)
    assert result == 3
    client.upload.assert_called_once()


def test_guard_rejects_far_dated_fallback_payload():
    """The retention fallback is anchored to the run date, so its expiries sit years out."""
    junk = _flow_csv([("SNDK", "2029-01-19", "1589.4")] * 5)
    session, client = make_session(junk), make_client()

    result = _download(session, client)

    assert result == scrape_flow._REJECTED
    client.upload.assert_not_called()


def test_guard_rejects_expiry_before_target():
    expired = _flow_csv([("SPY", "2026-05-01", "545.0")])
    session, client = make_session(expired), make_client()

    assert _download(session, client) == scrape_flow._REJECTED
    client.upload.assert_not_called()


def test_guard_rejects_spy_price_drift():
    session, client = make_session(GENUINE), make_client()

    # Same payload that passes at 545 is rejected when that date's close was 700.
    assert _download(session, client, spy_close=700.0) == scrape_flow._REJECTED
    client.upload.assert_not_called()


def test_guard_rejects_payload_already_seen_under_another_date():
    session, client = make_session(GENUINE), make_client()
    seen = {}
    from lib.csv_utils import flow_fingerprint, parse_csv
    seen[flow_fingerprint(parse_csv(GENUINE))] = "2024-01-02"

    result = _download(session, client, spy_close=545.0, seen_hashes=seen)

    assert result == scrape_flow._REJECTED
    client.upload.assert_not_called()


def test_allow_stale_records_verdict_but_still_never_uploads(_isolate_manifest):
    junk = _flow_csv([("SNDK", "2029-01-19", "1589.4")] * 5)
    session, client = make_session(junk), make_client()

    result = _download(session, client, allow_stale=True)

    assert result == scrape_flow._REJECTED
    client.upload.assert_not_called()
    with _isolate_manifest.open(newline="", encoding="utf-8") as fh:
        recorded = list(csvmod.DictReader(fh))
    assert [r["verdict"] for r in recorded] == ["reject"]
    assert "median_dte" in recorded[0]["reasons"]


def test_manifest_records_accepted_payload(tmp_path, _isolate_manifest):
    session, client = make_session(GENUINE), make_client()
    with patch("scrape_flow.Path", side_effect=lambda p: tmp_path / Path(p).name):
        _download(session, client, spy_close=545.0)

    with _isolate_manifest.open(newline="", encoding="utf-8") as fh:
        recorded = list(csvmod.DictReader(fh))
    assert len(recorded) == 1
    assert recorded[0]["verdict"] == "ok"
    assert recorded[0]["requested_date"] == "2026-06-02"
    assert recorded[0]["sha256"]
