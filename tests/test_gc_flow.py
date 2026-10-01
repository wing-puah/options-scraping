from unittest.mock import MagicMock

from gc_flow import gc_prefix, gc_unusual_prefix, _dates_with_compiled, _dates_with_snapshots


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


def test_gc_trashes_when_raw_uses_new_exp_date_column():
    """Barchart's post-2026-07-14 export uses Exp Date instead of Expires/DTE.

    compile_flow.py normalizes this (Exp Date -> Expires) before dedup/upload, so
    the compiled file's identity keys carry Expires. Raw snapshots must be
    normalized the same way before comparison, or every trade with a blank
    Expires + populated Exp Date looks "missing" and gc_flow never trashes.
    """
    raw = (
        "Symbol,Type,Strike,Exp Date,Trade,Size,Side,Premium,Time,Volume\n"
        "AAA,Call,100,2026-07-17,2.50,10,ask,1000,10:00:00 ET,100\n"
    )
    compiled = (
        "Symbol,Type,Strike,Expires,Trade,Size,Side,Premium,Time,Volume\n"
        "AAA,Call,100,2026-07-17,2.50,10,ask,1000,10:00:00 ET,100\n"
    )
    raws = [{"id": "r1", "name": "etfs-flow-20260717-1050.csv"}]
    listing = raws + [{"id": "c", "name": "etfs-flow-20260717-compiled.csv"}]
    content = {"r1": raw, "c": compiled}
    client = _client(raws=raws, listing=listing, content=content)

    stats = gc_prefix(client, "etfs-flow", "2026-07-17")
    assert stats["status"] == "trashed"
    assert stats["trashed"] == 1


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


# ── The unusual pass: no compiled file, so keep the richest snapshot ──────────

def _unusual(n_rows: int) -> str:
    head = "Symbol,Price,Type,Strike,Exp Date,Volume,Open Int,Vol/OI\n"
    return head + "".join(
        f"T{i},10,Call,100,2026-07-17,500,10,50\n" for i in range(n_rows)
    )


_UNUSUAL_SNAPS = [
    {"id": "u1", "name": "unusual-stocks-20260609-1050.csv"},
    {"id": "u2", "name": "unusual-stocks-20260609-1218.csv"},
    {"id": "u3", "name": "unusual-stocks-20260609-1605.csv"},
]


def test_gc_unusual_keeps_the_richest_snapshot():
    """The fullest export survives even when a later, shorter one exists."""
    content = {"u1": _unusual(40), "u2": _unusual(500), "u3": _unusual(12)}
    client = _client(raws=_UNUSUAL_SNAPS, listing=_UNUSUAL_SNAPS, content=content)

    stats = gc_unusual_prefix(client, "unusual-stocks", "2026-06-09")
    assert stats["status"] == "deduped"
    assert stats["raw"] == 3
    assert stats["trashed"] == 2
    assert {c.args[0] for c in client.trash.call_args_list} == {"u1", "u3"}


def test_gc_unusual_breaks_a_tie_to_the_newest():
    """Equal row counts keep the file download_for_date would already have read."""
    content = {"u1": _unusual(60), "u2": _unusual(60), "u3": _unusual(60)}
    client = _client(raws=_UNUSUAL_SNAPS, listing=_UNUSUAL_SNAPS, content=content)

    stats = gc_unusual_prefix(client, "unusual-stocks", "2026-06-09")
    assert stats["trashed"] == 2
    assert {c.args[0] for c in client.trash.call_args_list} == {"u1", "u2"}


def test_gc_unusual_single_snapshot_is_untouched():
    snaps = _UNUSUAL_SNAPS[:1]
    client = _client(raws=snaps, listing=snaps, content={"u1": _unusual(40)})

    stats = gc_unusual_prefix(client, "unusual-stocks", "2026-06-09")
    assert stats["status"] == "single"
    assert stats["trashed"] == 0
    client.trash.assert_not_called()


def test_gc_unusual_keeps_everything_when_nothing_parses():
    """A day of empty exports is a scrape failure, not a set of extras to thin."""
    content = {"u1": "", "u2": "", "u3": ""}
    client = _client(raws=_UNUSUAL_SNAPS, listing=_UNUSUAL_SNAPS, content=content)

    stats = gc_unusual_prefix(client, "unusual-etfs", "2026-06-09")
    assert stats["status"] == "unreadable"
    assert stats["trashed"] == 0
    client.trash.assert_not_called()


def test_gc_unusual_dry_run_trashes_nothing():
    content = {"u1": _unusual(40), "u2": _unusual(500), "u3": _unusual(12)}
    client = _client(raws=_UNUSUAL_SNAPS, listing=_UNUSUAL_SNAPS, content=content)

    stats = gc_unusual_prefix(client, "unusual-stocks", "2026-06-09", dry_run=True)
    assert stats["status"] == "deduped"
    assert stats["trashed"] == 0
    client.trash.assert_not_called()


def test_gc_unusual_no_snapshots_is_already_clean():
    client = _client(raws=[], listing=[], content={})
    stats = gc_unusual_prefix(client, "unusual-stocks", "2026-06-09")
    assert stats["status"] == "no-raw"
    client.trash.assert_not_called()


def test_dates_with_snapshots_only_reports_dates_holding_extras():
    client = MagicMock()
    client.list_files.return_value = [
        {"id": "1", "name": "unusual-stocks-20260609-1050.csv"},
        {"id": "2", "name": "unusual-stocks-20260609-1218.csv"},
        {"id": "3", "name": "unusual-stocks-20260610-1050.csv"},   # lone snapshot — skipped
        {"id": "4", "name": "unusual-stocks-20260611-compiled.csv"},  # not a snapshot
        {"id": "5", "name": "unusual-stocks-notes.csv"},           # off-convention
    ]
    assert _dates_with_snapshots(client, "unusual-stocks") == {"2026-06-09"}
