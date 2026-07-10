import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from scrape_flow import is_market_hours, _download_and_upload, _already_collected

ET = ZoneInfo("America/New_York")


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

    result = _run(_download_and_upload(session, client, "http://example.com", "unusual-stocks", run_dt, "folder-id"))

    assert result == 0
    session.download_csv.assert_not_called()


def test_download_returns_minus1_on_download_failure():
    session = make_session(None)   # download returns None
    client = make_client(file_exists_id=None)
    run_dt = datetime(2026, 6, 2, 10, 30, tzinfo=ET)

    result = _run(_download_and_upload(session, client, "http://example.com", "unusual-stocks", run_dt, "folder-id"))

    assert result == -1
    client.upload.assert_not_called()


def test_download_returns_0_on_empty_csv():
    session = make_session("Symbol,Volume\n")   # header only, no data rows
    client = make_client(file_exists_id=None)
    run_dt = datetime(2026, 6, 2, 10, 30, tzinfo=ET)

    result = _run(_download_and_upload(session, client, "http://example.com", "unusual-stocks", run_dt, "folder-id"))

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

        result = _run(_download_and_upload(session, client, "http://example.com", "unusual-stocks", run_dt, "folder-id"))

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
