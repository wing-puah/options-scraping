from unittest.mock import MagicMock

from gc_flow import gc_prefix, _dates_with_compiled


# Two raw snapshots; the second repeats the first's trade (AAA) and adds BBB.
_RAW_1050 = (
    "Symbol,Type,Strike,Expires,Trade,Size,Side,Premium,Time,Volume\n"
    "AAA,Call,100,2026-07-17,2.50,10,ask,1000,10:00:00 ET,100\n"
)
_RAW_1218 = (
    "Symbol,Type,Strike,Expires,Trade,Size,Side,Premium,Time,Volume\n"
    "AAA,Call,100,2026-07-17,2.50,10,ask,1000,10:00:00 ET,175\n"   # same trade, drifted Volume
    "BBB,Put,90,2026-07-17,1.10,5,bid,500,10:05:00 ET,40\n"
)
# A correct compiled file: both unique trades present.
_COMPILED_GOOD = (
    "Symbol,Type,Strike,Expires,Trade,Size,Side,Premium,Time,Volume\n"
    "AAA,Call,100,2026-07-17,2.50,10,ask,1000,10:00:00 ET,175\n"
    "BBB,Put,90,2026-07-17,1.10,5,bid,500,10:05:00 ET,40\n"
)
# A broken compiled file: BBB is missing.
_COMPILED_MISSING = (
    "Symbol,Type,Strike,Expires,Trade,Size,Side,Premium,Time,Volume\n"
    "AAA,Call,100,2026-07-17,2.50,10,ask,1000,10:00:00 ET,175\n"
)

_RAWS = [
    {"id": "r1", "name": "etfs-flow-20260609-1050.csv"},
    {"id": "r2", "name": "etfs-flow-20260609-1218.csv"},
]


def _client(*, raws, listing, content):
    """Mock client: list_files_for_date → raws, list_files → listing, download by id → content."""
    c = MagicMock()
    c.list_files_for_date.return_value = raws
    c.list_files.return_value = listing
    c.download.side_effect = lambda fid, **kwargs: content[fid]
    return c


def test_gc_trashes_when_compiled_covers_all_raw_trades():
    listing = _RAWS + [{"id": "c", "name": "etfs-flow-20260609-compiled.csv"}]
    content = {"r1": _RAW_1050, "r2": _RAW_1218, "c": _COMPILED_GOOD}
    client = _client(raws=_RAWS, listing=listing, content=content)

    stats = gc_prefix(client, "etfs-flow", "2026-06-09")
    assert stats["status"] == "trashed"
    assert stats["trashed"] == 2
    assert {c.args[0] for c in client.trash.call_args_list} == {"r1", "r2"}


def test_gc_keeps_raw_when_compiled_missing():
    listing = list(_RAWS)  # no compiled file present
    content = {"r1": _RAW_1050, "r2": _RAW_1218}
    client = _client(raws=_RAWS, listing=listing, content=content)

    stats = gc_prefix(client, "etfs-flow", "2026-06-09")
    assert stats["status"] == "no-compiled"
    assert stats["trashed"] == 0
    client.trash.assert_not_called()


def test_gc_keeps_raw_when_compiled_incomplete():
    listing = _RAWS + [{"id": "c", "name": "etfs-flow-20260609-compiled.csv"}]
    content = {"r1": _RAW_1050, "r2": _RAW_1218, "c": _COMPILED_MISSING}
    client = _client(raws=_RAWS, listing=listing, content=content)

    stats = gc_prefix(client, "etfs-flow", "2026-06-09")
    assert stats["status"] == "incomplete"
    assert stats["trashed"] == 0
    client.trash.assert_not_called()


def test_gc_dry_run_verifies_but_does_not_trash():
    listing = _RAWS + [{"id": "c", "name": "etfs-flow-20260609-compiled.csv"}]
    content = {"r1": _RAW_1050, "r2": _RAW_1218, "c": _COMPILED_GOOD}
    client = _client(raws=_RAWS, listing=listing, content=content)

    stats = gc_prefix(client, "etfs-flow", "2026-06-09", dry_run=True)
    assert stats["status"] == "trashed"   # verification passed
    assert stats["trashed"] == 0          # but nothing actually trashed
    client.trash.assert_not_called()


def test_gc_no_raw_is_already_clean():
    client = _client(raws=[], listing=[], content={})
    stats = gc_prefix(client, "etfs-flow", "2026-06-09")
    assert stats["status"] == "no-raw"
    client.trash.assert_not_called()


def test_dates_with_compiled_parses_dates():
    client = MagicMock()
    client.list_files.return_value = [
        {"id": "1", "name": "etfs-flow-20260609-compiled.csv"},
        {"id": "2", "name": "etfs-flow-20260610-compiled.csv"},
        {"id": "3", "name": "etfs-flow-20260610-1050.csv"},   # raw snapshot — ignored
    ]
    assert _dates_with_compiled(client, "etfs-flow") == {"2026-06-09", "2026-06-10"}
