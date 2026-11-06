"""The price fetch's --merge: rolled-off dates stay, and a changed close refuses the write."""
import asyncio
import plistlib
from pathlib import Path

from lib.baseline import KEY_TICKERS
from scripts.collector.history import fetch_underlying_ohlc as foh

HEADER = "Time,Open,High,Low,Latest,Volume"
DAILY = Path(foh.__file__).resolve().parents[1] / "daily"


def _csv(*rows):
    """Newest first, as the feed writes it."""
    return "\n".join([HEADER] + [f"{d},1,2,0.5,{c},100" for d, c in rows]) + "\n"


def test_merge_keeps_dates_the_feed_rolled_off_and_sorts_newest_first():
    old = _csv(("2026-01-06", 11), ("2026-01-05", 10))
    new = _csv(("2026-01-07", 12), ("2026-01-06", 11))
    text, problems = foh.merge_history(old, new)
    assert problems == []
    assert [ln.split(",")[0] for ln in text.splitlines()] == ["Time", "2026-01-07", "2026-01-06", "2026-01-05"]


def test_a_changed_close_on_an_existing_date_refuses_the_merge():
    old = _csv(("2026-01-06", 11), ("2026-01-05", 10))
    new = _csv(("2026-01-07", 12), ("2026-01-06", 11), ("2026-01-05", 5))
    text, problems = foh.merge_history(old, new)
    assert text is None and "2026-01-05" in problems[0]


def test_the_old_files_newest_bar_may_be_revised():
    """It may have been written before that session's close settled."""
    old = _csv(("2026-01-06", 11), ("2026-01-05", 10))
    new = _csv(("2026-01-06", 11.5), ("2026-01-05", 10))
    text, problems = foh.merge_history(old, new)
    assert problems == [] and "2026-01-06,1,2,0.5,11.5,100" in text


def test_a_changed_header_or_empty_feed_refuses_the_merge():
    old = _csv(("2026-01-05", 10))
    assert foh.merge_history(old, "Time,Other\n2026-01-05,1\n")[0] is None
    assert foh.merge_history(old, HEADER + "\n")[0] is None


def test_a_non_date_footer_line_is_dropped():
    old = _csv(("2026-01-05", 10))
    new = _csv(("2026-01-06", 11)) + "Downloaded from Barchart\n"
    text, _ = foh.merge_history(old, new)
    assert "Downloaded" not in text


class _Session:
    def __init__(self, text):
        self.text = text

    async def fetch_history_fast(self, url, timeout_ms):
        return self.text


def test_scrape_with_merge_leaves_the_file_alone_when_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(foh, "OHLC_CACHE", tmp_path)
    monkeypatch.setattr(foh, "RESCALED_FILE", tmp_path / "rescaled_tickers.txt")
    monkeypatch.setattr(foh, "HISTORY_CACHE", tmp_path / "none")
    old = _csv(("2026-01-06", 11), ("2026-01-05", 10))
    (tmp_path / "SPY.csv").write_text(old)
    bad = _csv(("2026-01-06", 11), ("2026-01-05", 5))
    stats = asyncio.run(foh._scrape(["SPY"], headless=True, sleep_s=0, session=_Session(bad), merge=True))
    assert stats["refused"] == 1 and stats["fetched"] == 0
    assert (tmp_path / "SPY.csv").read_text() == old


def test_scrape_with_merge_writes_the_union(tmp_path, monkeypatch):
    monkeypatch.setattr(foh, "OHLC_CACHE", tmp_path)
    monkeypatch.setattr(foh, "RESCALED_FILE", tmp_path / "rescaled_tickers.txt")
    monkeypatch.setattr(foh, "HISTORY_CACHE", tmp_path / "none")
    (tmp_path / "SPY.csv").write_text(_csv(("2026-01-05", 10)))
    good = _csv(("2026-01-06", 11))
    stats = asyncio.run(foh._scrape(["SPY"], headless=True, sleep_s=0, session=_Session(good), merge=True))
    assert stats["fetched"] == 1
    assert (tmp_path / "SPY.csv").read_text() == _csv(("2026-01-06", 11), ("2026-01-05", 10))


def test_the_scheduled_job_fetches_exactly_the_baseline_etfs_with_merge():
    script = (DAILY / "refresh_etf_prices.sh").read_text()
    line = next(ln for ln in script.splitlines() if ln.startswith("TICKERS="))
    assert set(line.split('"')[1].split(",")) == set(KEY_TICKERS)
    assert "--force --merge" in script


def test_the_plist_runs_the_script_in_this_repo():
    plist = plistlib.loads((DAILY / "com.wing.options-etf-prices.plist").read_bytes())
    assert plist["Label"] == "com.wing.options-etf-prices"
    assert plist["ProgramArguments"][-1] == "scripts/collector/daily/refresh_etf_prices.sh"
    assert plist["WorkingDirectory"].endswith("/options-trading")
