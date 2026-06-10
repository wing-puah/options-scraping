from unittest.mock import MagicMock

from lib.drive_client import DriveClient
from compile_flow import compiled_name, dedup_rows


# ── compiled_name ─────────────────────────────────────────────────────────────

def test_compiled_name():
    assert compiled_name("etfs-flow", "2026-06-09") == "etfs-flow-20260609-compiled.csv"
    assert compiled_name("stocks-flow", "2026-06-09") == "stocks-flow-20260609-compiled.csv"


# ── dedup_rows ────────────────────────────────────────────────────────────────

def _trade(symbol, time, volume, premium="1000"):
    """A minimal flow row; Volume drifts between snapshots, identity columns don't."""
    return {
        "Symbol": symbol, "Type": "Call", "Strike": "100", "Expires": "2026-07-17",
        "Trade": "2.50", "Size": "10", "Side": "ask", "Premium": premium,
        "Time": time, "Volume": volume, "Open Int": "5",
    }


def test_dedup_rows_empty():
    df, n = dedup_rows([])
    assert n == 0 and df.empty


def test_dedup_drops_same_trade_despite_volume_drift():
    # Same trade identity seen in two snapshots; Volume differs (scrape-time drift).
    rows = [
        _trade("AAA", "10:00:00 ET", "100"),   # earlier snapshot
        _trade("BBB", "10:05:00 ET", "200"),
        _trade("AAA", "10:00:00 ET", "175"),   # later snapshot — same trade
    ]
    df, n = dedup_rows(rows)
    assert n == 1
    assert len(df) == 2


def test_dedup_keeps_latest_snapshot_values():
    # keep='last' → the most-settled Volume wins for a recurring trade.
    rows = [_trade("AAA", "10:00:00 ET", "100"), _trade("AAA", "10:00:00 ET", "175")]
    df, n = dedup_rows(rows)
    assert n == 1
    assert df.iloc[0]["Volume"] == "175"


def test_dedup_distinct_trades_kept():
    rows = [_trade("AAA", "10:00:00 ET", "100"), _trade("AAA", "10:01:00 ET", "100")]
    df, n = dedup_rows(rows)
    assert n == 0
    assert len(df) == 2


# ── DriveClient.list_files_for_date ───────────────────────────────────────────

def _svc_with(files):
    svc = MagicMock()
    svc.files.return_value.list.return_value.execute.return_value = {"files": files}
    return svc


def test_list_files_for_date_filters_and_sorts():
    svc = _svc_with([
        {"id": "3", "name": "etfs-flow-20260609-1218.csv"},
        {"id": "1", "name": "etfs-flow-20260609-1050.csv"},
        {"id": "x", "name": "etfs-flow-20260609-compiled.csv"},  # derived — excluded
        {"id": "y", "name": "etfs-flow-20260610-0930.csv"},      # other date — excluded
    ])
    client = DriveClient(svc, "root")
    files = client.list_files_for_date("etfs-flow", "2026-06-09")
    assert [f["name"] for f in files] == [
        "etfs-flow-20260609-1050.csv",
        "etfs-flow-20260609-1218.csv",
    ]


def test_list_files_for_date_empty():
    client = DriveClient(_svc_with([]), "root")
    assert client.list_files_for_date("stocks-flow", "2026-06-09") == []
