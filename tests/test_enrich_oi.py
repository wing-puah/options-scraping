import asyncio
import sys
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from lib.drive_client import DriveClient, FlowCorpus

import enrich_oi
from compile_flow import FLOW_PREFIXES
from enrich_oi import (
    ALL_COLUMNS,
    ENRICH_COLUMNS,
    MARKER_COLUMN,
    _clear_columns,
    _compiled_dates,
    _compute_enrichment,
    _distinct_contracts,
    _done_keys,
    _ensure_columns,
    _enrichable_dates,
    _latest_compiled_date,
    _latest_enrichable_date,
    _row_contract,
    _scrape_and_fill,
    enrich_prefix,
)

D = date(2026, 6, 9)


@pytest.fixture(autouse=True)
def _restore_event_loop():
    """enrich_prefix calls asyncio.run, which closes the loop and clears the global
    current loop on 3.11. Restore one after each test so later async-using modules
    (test_scraper, test_gc_flow) still find a current event loop."""
    yield
    asyncio.set_event_loop(asyncio.new_event_loop())


# ── _compute_enrichment ───────────────────────────────────────────────────────

def _hist_row(oi, vol="100", iv="45.2", delta="0.30", gamma="0.02", vega="0.10"):
    return {"Open Int": oi, "Volume": vol, "IV": iv,
            "Delta": delta, "Gamma": gamma, "Vega": vega}


def test_compute_enrichment_basic():
    # D-1 = June 8, D = June 9
    details = {date(2026, 6, 8): _hist_row("450"), D: _hist_row("500")}
    e = _compute_enrichment(details, D)
    assert e["oi_d"] == "500"
    assert e["oi_prev"] == "450"
    assert e["oi_change"] == "50"   # oi_d - oi_prev = 500 - 450
    assert e["vol_d"] == "100"
    assert e["eod_iv"] == "0.452"   # 45.2 scraped ÷ 100 → decimal for Sheets % formatting
    assert e["eod_delta"] == "0.3"
    assert e["eod_gamma"] == "0.02"
    assert e["eod_vega"] == "0.1"
    # _compute_enrichment returns only the data columns; the marker is added later.
    assert MARKER_COLUMN not in e


def test_oi_prev_uses_prior_trading_day_not_calendar():
    # Monday D — Friday is the prior trading day; Sat/Sun absent from the series.
    monday = date(2026, 6, 8)   # Monday
    friday = date(2026, 6, 5)   # Friday before
    details = {friday: _hist_row("700"), monday: _hist_row("500")}
    e = _compute_enrichment(details, monday)
    assert e["oi_prev"] == "700"
    assert e["oi_change"] == "-200"   # oi_d - oi_prev = 500 - 700


def test_negative_oi_change():
    # OI fell on trade day: oi_d < oi_prev → negative oi_change
    details = {date(2026, 6, 8): _hist_row("1000"), D: _hist_row("800")}
    assert _compute_enrichment(details, D)["oi_change"] == "-200"


def test_missing_d_row_blanks_d_columns():
    # Only the prior day is present — no exact row on D.
    details = {date(2026, 6, 8): _hist_row("650")}
    e = _compute_enrichment(details, D)
    assert e["oi_d"] == "" and e["vol_d"] == ""
    assert e["eod_iv"] == "" and e["eod_delta"] == ""
    assert e["oi_prev"] == "650"
    assert e["oi_change"] == ""  # needs both ends


def test_no_prev_day_blanks_change():
    details = {D: _hist_row("500")}  # D is the only/earliest row in series
    e = _compute_enrichment(details, D)
    assert e["oi_d"] == "500"
    assert e["oi_prev"] == "" and e["oi_change"] == ""


def test_contract_absent_from_history_all_blank():
    e = _compute_enrichment({}, D)
    assert e == {c: "" for c in ENRICH_COLUMNS}


# ── _row_contract / _distinct_contracts ───────────────────────────────────────

def _flow_row(symbol="GSK", typ="Put", strike="50.00", expires="2026-08-21T16:30:00-05:00"):
    return {"Symbol": symbol, "Type": typ, "Strike": strike, "Expires": expires}


def test_row_contract_parses_iso_datetime_expiry():
    c = _row_contract(_flow_row())
    assert c is not None
    assert c["symbol"] == "GSK"
    assert c["opt_type"] == "Put"
    assert c["strike"] == 50.0
    assert c["expiration"] == date(2026, 8, 21)


def test_row_contract_unparseable_returns_none():
    assert _row_contract(_flow_row(strike="n/a")) is None
    assert _row_contract({"Symbol": "X"}) is None


def test_distinct_contracts_dedups_and_counts_unparseable():
    rows = [
        _flow_row("GSK", "Put", "50.00"),
        _flow_row("GSK", "Put", "50.00"),   # duplicate contract, different trade
        _flow_row("AAPL", "Call", "200.00"),
        _flow_row(strike="bad"),            # unparseable
    ]
    contracts, unparseable = _distinct_contracts(rows)
    assert len(contracts) == 2
    assert unparseable == 1


# ── column state + resume marker ──────────────────────────────────────────────

def test_ensure_columns_adds_blanks_and_preserves_values():
    r = _flow_row()
    r["oi_d"] = "500"  # already filled by a prior partial run
    _ensure_columns([r])
    assert all(c in r for c in ALL_COLUMNS)
    assert r["oi_d"] == "500"          # preserved
    assert r["oi_change"] == ""        # newly added blank
    assert r[MARKER_COLUMN] == ""


def test_clear_columns_resets_all():
    r = {**_flow_row(), **{c: "x" for c in ALL_COLUMNS}}
    _clear_columns([r])
    assert all(r[c] == "" for c in ALL_COLUMNS)
    assert r["Symbol"] == "GSK"  # original untouched


def test_done_keys_uses_marker_not_data():
    done = {**_flow_row("GSK"), MARKER_COLUMN: "2026-06-17"}      # attempted
    empty_marked = {**_flow_row("AAPL", "Call", "200.00"),       # attempted, no data
                    MARKER_COLUMN: "2026-06-17"}
    pending = {**_flow_row("TSLA", "Call", "300.00"), MARKER_COLUMN: ""}
    keys = _done_keys([done, empty_marked, pending])
    assert _row_contract(done)["key"] in keys
    assert _row_contract(empty_marked)["key"] in keys     # marked => done despite no data
    assert _row_contract(pending)["key"] not in keys


# ── date enumeration ──────────────────────────────────────────────────────────

def _client_with_compiled(dates_by_prefix, snapshots_by_prefix=None):
    """MagicMock client whose flow_corpus() reflects the given files.

    Date discovery reads ONE bounded FlowCorpus index rather than probing Drive per
    date, so flow_corpus() is the boundary to mock. `dates_by_prefix` is
    {prefix: [date, ...]} of compiled files; `snapshots_by_prefix` is
    {prefix: {date: count}} of raw snapshots.
    """
    client = MagicMock()
    snapshots_by_prefix = snapshots_by_prefix or {}
    all_dates = sorted({d for ds in dates_by_prefix.values() for d in ds}
                       | {d for ds in snapshots_by_prefix.values() for d in ds})
    files: dict[str, dict[str, dict]] = {}

    def _entry(date_str, prefix):
        return files.setdefault(date_str, {}).setdefault(
            prefix, {"compiled": False, "snapshots": 0})

    for prefix, ds in dates_by_prefix.items():
        for d in ds:
            _entry(d, prefix)["compiled"] = True
    for prefix, counts in snapshots_by_prefix.items():
        for d, n in counts.items():
            _entry(d, prefix)["snapshots"] = n

    client.flow_corpus.return_value = FlowCorpus(
        folders={d: f"folder-{d}" for d in all_dates}, files=files)
    return client


def _corpus_svc(dates):
    """Mock Drive service serving `dates` worth of folders + compiled files.

    Used to count the REAL number of Drive round trips date discovery costs.
    """
    folders = [{"id": f"folder-{d}", "name": d} for d in dates]

    def _list(**kw):
        resp = MagicMock()
        if "google-apps.folder" in kw["q"]:
            resp.execute.return_value = {"files": folders}
        else:
            prefix = kw["q"].split("name contains '")[1].split("-'")[0]
            resp.execute.return_value = {"files": [
                {"id": f"{prefix}-{d}",
                 "name": f"{prefix}-{d.replace('-', '')}-compiled.csv",
                 "parents": [f"folder-{d}"]}
                for d in dates]}
        return resp

    svc = MagicMock()
    svc.files.return_value.list.side_effect = _list
    return svc


def test_compiled_dates_unions_prefixes_and_sorts():
    client = _client_with_compiled({
        "etfs-flow": ["2026-06-10", "2026-06-09"],
        "stocks-flow": ["2026-06-09", "2026-06-11"],
    })
    assert _compiled_dates(client) == ["2026-06-09", "2026-06-10", "2026-06-11"]


def test_enrichable_dates_excludes_latest():
    client = _client_with_compiled({
        "etfs-flow": ["2026-06-09", "2026-06-10", "2026-06-11"],
        "stocks-flow": [],
    })
    assert _enrichable_dates(client) == ["2026-06-09", "2026-06-10", "2026-06-11"]


def test_latest_compiled_date_matches_last_of_full_list():
    client = _client_with_compiled({
        "etfs-flow": ["2026-06-10", "2026-06-09"],
        "stocks-flow": ["2026-06-09", "2026-06-11"],
    })
    assert _latest_compiled_date(client) == "2026-06-11"


def test_latest_enrichable_date_matches_last_of_full_list():
    client = _client_with_compiled({
        "etfs-flow": ["2026-06-09", "2026-06-10", "2026-06-11"],
        "stocks-flow": [],
    })
    assert _latest_enrichable_date(client) == "2026-06-11"


def test_latest_enrichable_date_none_when_nothing_enrichable():
    client = _client_with_compiled({"etfs-flow": [], "stocks-flow": []})
    assert _latest_enrichable_date(client) is None


def test_enrichable_dates_needs_a_single_snapshot_on_EVERY_prefix():
    """The snapshot fallback is `all` prefixes, not `any` — fetch_counterpart_iv
    deliberately uses `any`, and the two must not converge by accident."""
    client = _client_with_compiled(
        {"etfs-flow": [], "stocks-flow": []},
        snapshots_by_prefix={"etfs-flow": {"2026-06-09": 1, "2026-06-10": 1},
                             "stocks-flow": {"2026-06-09": 1, "2026-06-10": 3}},
    )
    assert _enrichable_dates(client) == ["2026-06-09"]


@pytest.mark.parametrize("n_dates", [50, 500])
def test_date_discovery_cost_is_flat_in_corpus_size(n_dates):
    """Regression: date discovery used to cost a file_exists per prefix per date —
    two to six Drive round trips for EVERY date folder, thousands of calls on a
    real corpus, paid again on every no-op run. It must now be one bounded index:
    one query for the date folders plus one per prefix, whatever the corpus size."""
    dates = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(n_dates)]
    svc = _corpus_svc(dates)
    client = DriveClient(svc, "root-id")

    assert _compiled_dates(client) == dates
    assert svc.files.return_value.list.call_count == 1 + len(FLOW_PREFIXES)


def test_explicit_date_does_not_scan_the_corpus(monkeypatch, capsys):
    """The reported bug: `--date D` on an already-enriched date fell through to the
    'Nothing enriched' tail, which indexed the WHOLE corpus just to print a date
    list the operator never asked for. scrape_and_enrich.sh calls every stage that
    way, once per date, so this ran on every no-op."""
    client = MagicMock()
    client.find_date_folder.return_value = None      # => no source file => nothing enriched
    monkeypatch.setattr(enrich_oi, "get_drive_client", lambda: client)
    monkeypatch.setattr(sys, "argv", ["enrich_oi.py", "--date", "2026-06-09"])

    enrich_oi.main()

    client.flow_corpus.assert_not_called()
    assert "Enrichable dates in Drive" not in capsys.readouterr().out


def test_no_arg_run_still_lists_dates_and_indexes_only_once(monkeypatch, capsys):
    """The listing is still worth printing when the operator named no date — but the
    corpus must be indexed ONCE and shared with the tail, not built again to print it.
    """
    client = _client_with_compiled({"etfs-flow": ["2026-06-09"], "stocks-flow": []})
    client.find_date_folder.return_value = None      # => nothing enriched
    monkeypatch.setattr(enrich_oi, "get_drive_client", lambda: client)
    monkeypatch.setattr(sys, "argv", ["enrich_oi.py"])

    enrich_oi.main()

    assert client.flow_corpus.call_count == 1
    assert "Enrichable dates in Drive: 2026-06-09" in capsys.readouterr().out


# ── _scrape_and_fill (incremental fill, checkpoint, marker) ────────────────────

# A Barchart price-history CSV the real parse_history_details can read (needs a
# mark via Bid/Ask or Latest, and an ISO Time).
def _history_csv(rows):
    header = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,"
              "Delta,Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")
    lines = [header]
    for d, oi, vol in rows:
        lines.append(f"{d},1,1,1,1.50,0,0,{vol},{oi},44.1,-0.40,0.02,-0.01,0.10,0,1.5,1.5,1.45,1.55")
    return "\n".join(lines) + "\n"


class _FakeSession:
    """Stands in for an entered BarchartSession; returns fixture CSV per symbol."""

    def __init__(self, csv_by_symbol):
        self._csv = csv_by_symbol
        self.calls = []

    async def fetch_history_fast(self, url, timeout_ms=15000):
        self.calls.append(url)
        for sym, csv in self._csv.items():
            if f"/{sym}%7C" in url:
                return csv
        return None


def test_scrape_and_fill_fills_marks_and_checkpoints():
    client = MagicMock()
    client.get_or_create_date_folder.return_value = "folder"
    rows = [_flow_row("GSK"), _flow_row("AAPL", "Call", "200.00"), _flow_row("TSLA", "Call", "300.00")]
    _ensure_columns(rows)
    contracts, _ = _distinct_contracts(rows)
    pending = list(contracts.values())

    session = _FakeSession({
        "GSK":  _history_csv([("2026-06-08", "500", "100"), ("2026-06-09", "650", "5")]),
        "AAPL": _history_csv([("2026-06-08", "800", "20"), ("2026-06-09", "600", "3")]),
        # TSLA absent → Barchart returns None → empty, but still marked.
    })

    stats = asyncio.run(_scrape_and_fill(
        client, "etfs-flow", "2026-06-09", rows, pending, D, "2026-06-17",
        headless=True, file_name="etfs-flow-20260609-compiled.csv",
        checkpoint_every=2, sleep_s=0, session=session))

    assert stats["processed"] == 3
    assert stats["with_next"] == 2                      # GSK + AAPL have a prior day
    # every contract attempted → every row marked, even TSLA (no data)
    assert all(r[MARKER_COLUMN] == "2026-06-17" for r in rows)
    by_sym = {r["Symbol"]: r for r in rows}
    assert by_sym["GSK"]["oi_change"] == "150"
    assert by_sym["AAPL"]["oi_change"] == "-200"
    assert by_sym["TSLA"]["oi_d"] == "" and by_sym["TSLA"]["oi_change"] == ""
    # checkpoint at 2 contracts + finally flush = 2 uploads
    assert client.upload.call_count == 2


def test_scrape_and_fill_flushes_despite_scrape_failure():
    """A per-contract scrape failure is swallowed; the finally still persists work."""
    client = MagicMock()
    client.get_or_create_date_folder.return_value = "folder"
    rows = [_flow_row("GSK"), _flow_row("AAPL", "Call", "200.00")]
    _ensure_columns(rows)
    contracts, _ = _distinct_contracts(rows)
    pending = list(contracts.values())

    class _BoomSession(_FakeSession):
        async def fetch_history_fast(self, url, timeout_ms=15000):
            if "AAPL" in url:
                raise RuntimeError("boom")
            return await super().fetch_history_fast(url, timeout_ms)

    session = _BoomSession({"GSK": _history_csv([("2026-06-09", "500", "100"),
                                                 ("2026-06-10", "650", "5")])})
    stats = asyncio.run(_scrape_and_fill(
        client, "etfs-flow", "2026-06-09", rows, pending, D, "2026-06-17",
        headless=True, file_name="etfs-flow-20260609-compiled.csv",
        checkpoint_every=99, sleep_s=0, session=session))
    assert stats["processed"] == 2
    assert client.upload.call_count == 1  # finally flush only (checkpoint_every not hit)
    assert all(r[MARKER_COLUMN] == "2026-06-17" for r in rows)


# ── enrich_prefix (Drive integration, mocked) ─────────────────────────────────

_FLOW_CSV = (
    "Symbol,Type,Strike,Expires,Premium\n"
    "GSK,Put,50.00,2026-08-21T16:30:00-05:00,1000\n"
    "GSK,Put,50.00,2026-08-21T16:30:00-05:00,2000\n"
)


def _drive_client(csv_text, compiled_present=True):
    client = MagicMock()
    client.find_date_folder.return_value = "folder"
    client.file_exists.return_value = "fid" if compiled_present else None
    client.download.return_value = csv_text
    client.get_or_create_date_folder.return_value = "folder"
    return client


def test_enrich_prefix_skips_when_no_compiled_and_no_single_raw():
    client = _drive_client("", compiled_present=False)
    client.list_files_for_date.return_value = []  # no raw snapshots either
    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=False, force=False)
    assert res["status"] == "no-compiled"
    client.upload.assert_not_called()


def test_enrich_prefix_uses_single_raw_when_no_compiled(monkeypatch):
    client = _drive_client(_FLOW_CSV, compiled_present=False)
    client.list_files_for_date.return_value = [
        {"id": "rawid", "name": "etfs-flow-20260609-0930.csv"}
    ]
    seen = {}

    async def fake_scrape(cl, prefix, date_str, rows, pending, trade_date, run_date, **kwargs):
        seen["file_name"] = kwargs["file_name"]
        return {"with_next": 0, "processed": len(pending)}

    monkeypatch.setattr(enrich_oi, "_scrape_and_fill", fake_scrape)

    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=False, force=False)
    assert res["status"] == "enriched"
    assert seen["file_name"] == "etfs-flow-20260609-0930.csv"
    client.download.assert_called_once_with("rawid", name="etfs-flow-20260609-0930.csv")


def test_enrich_prefix_uploads_augmented_csv(monkeypatch):
    client = _drive_client(_FLOW_CSV)

    async def fake_scrape(cl, prefix, date_str, rows, pending, trade_date, run_date,
                          **kwargs):
        for row in rows:
            row.update({**_compute_enrichment(
                {date(2026, 6, 8): _hist_row("500"), trade_date: _hist_row("650")},
                trade_date), enrich_oi.MARKER_COLUMN: run_date})
        enrich_oi._upload_rows(cl, date_str, rows, kwargs["file_name"])
        return {"with_next": 1, "processed": len(pending)}

    monkeypatch.setattr(enrich_oi, "_scrape_and_fill", fake_scrape)

    uploaded = {}

    def capture_upload(local_path, name, folder_id):
        uploaded["rows"] = enrich_oi.parse_csv(local_path.read_text())
        return "newid"

    client.upload.side_effect = capture_upload

    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=False, force=False)
    assert res["status"] == "enriched"
    assert res["contracts"] == 1 and res["with_next"] == 1
    rows = uploaded["rows"]
    assert len(rows) == 2
    for r in rows:
        assert r["oi_change"] == "150"
        assert r["Premium"] in ("1000", "2000")  # originals preserved
        assert r[enrich_oi.MARKER_COLUMN]        # marked
    # column order: originals first, ALL_COLUMNS appended in order
    assert list(rows[0].keys())[-len(ALL_COLUMNS):] == ALL_COLUMNS


def test_enrich_prefix_dry_run_previews_without_scraping(monkeypatch):
    client = _drive_client(_FLOW_CSV)
    called = {"scrape": False}

    async def fake_scrape(*a, **k):
        called["scrape"] = True
        return {"with_next": 0, "processed": 0}

    monkeypatch.setattr(enrich_oi, "_scrape_and_fill", fake_scrape)

    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=True, force=False)
    assert res["status"] == "enriched"
    assert res["pending"] == 1 and res["processed"] == 0
    assert called["scrape"] is False   # dry-run hits no network
    client.upload.assert_not_called()


def test_enrich_prefix_skips_already_enriched(monkeypatch):
    # Every contract row already carries the marker → nothing pending.
    enriched_csv = (
        "Symbol,Type,Strike,Expires,Premium," + ",".join(ALL_COLUMNS) + "\n"
        "GSK,Put,50.00,2026-08-21T16:30:00-05:00,1000,500,650,150,100,44.1,-0.4,0.02,0.1,2026-06-16\n"
    )
    client = _drive_client(enriched_csv)
    called = {"scrape": False}

    async def fake_scrape(*a, **k):
        called["scrape"] = True
        return {"with_next": 0, "processed": 0}

    monkeypatch.setattr(enrich_oi, "_scrape_and_fill", fake_scrape)

    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=False, force=False)
    assert res["status"] == "complete"
    assert called["scrape"] is False
    client.upload.assert_not_called()


def test_enrich_prefix_force_rescrapes_marked(monkeypatch):
    # Already marked, but --force clears and re-scrapes.
    enriched_csv = (
        "Symbol,Type,Strike,Expires,Premium," + ",".join(ALL_COLUMNS) + "\n"
        "GSK,Put,50.00,2026-08-21T16:30:00-05:00,1000,500,650,150,100,44.1,-0.4,0.02,0.1,2026-06-16\n"
    )
    client = _drive_client(enriched_csv)
    seen_pending = {}

    async def fake_scrape(cl, prefix, date_str, rows, pending, *a, **k):
        seen_pending["n"] = len(pending)
        return {"with_next": 0, "processed": len(pending)}

    monkeypatch.setattr(enrich_oi, "_scrape_and_fill", fake_scrape)

    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=False, force=True)
    assert res["status"] == "enriched"
    assert seen_pending["n"] == 1  # the marked contract is pending again under --force
