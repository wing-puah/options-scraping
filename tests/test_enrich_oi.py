import asyncio
from datetime import date
from unittest.mock import MagicMock

import pytest

import enrich_oi
from enrich_oi import (
    ENRICH_COLUMNS,
    _already_enriched,
    _apply_enrichment,
    _compiled_dates,
    _compute_enrichment,
    _distinct_contracts,
    _enrichable_dates,
    _row_contract,
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
    details = {D: _hist_row("500"), date(2026, 6, 10): _hist_row("650")}
    e = _compute_enrichment(details, D)
    assert e["oi_d"] == "500"
    assert e["oi_next"] == "650"
    assert e["oi_change"] == "150"
    assert e["vol_d"] == "100"
    assert e["eod_iv"] == "45.2"
    assert e["eod_delta"] == "0.3"
    assert e["eod_gamma"] == "0.02"
    assert e["eod_vega"] == "0.1"


def test_oi_next_uses_next_trading_day_not_calendar():
    # Friday D, then Monday — Sat/Sun absent from the series.
    details = {D: _hist_row("500"), date(2026, 6, 12): _hist_row("700")}
    e = _compute_enrichment(details, D)
    assert e["oi_next"] == "700"
    assert e["oi_change"] == "200"


def test_negative_oi_change():
    details = {D: _hist_row("800"), date(2026, 6, 10): _hist_row("600")}
    assert _compute_enrichment(details, D)["oi_change"] == "-200"


def test_missing_d_row_blanks_d_columns():
    # Only the next day is present — no exact row on D.
    details = {date(2026, 6, 10): _hist_row("650")}
    e = _compute_enrichment(details, D)
    assert e["oi_d"] == "" and e["vol_d"] == ""
    assert e["eod_iv"] == "" and e["eod_delta"] == ""
    assert e["oi_next"] == "650"
    assert e["oi_change"] == ""  # needs both ends


def test_no_next_day_blanks_change():
    details = {D: _hist_row("500")}  # D is the latest row (e.g. expired)
    e = _compute_enrichment(details, D)
    assert e["oi_d"] == "500"
    assert e["oi_next"] == "" and e["oi_change"] == ""


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


# ── _apply_enrichment ─────────────────────────────────────────────────────────

def test_apply_enrichment_preserves_and_appends_columns():
    r1 = _flow_row("GSK", "Put", "50.00")
    r1["Premium"] = "1000"
    r2 = _flow_row("GSK", "Put", "50.00")  # same contract, different trade
    r2["Premium"] = "2000"
    key = _row_contract(r1)["key"]
    enrichment = {key: {c: str(i) for i, c in enumerate(ENRICH_COLUMNS)}}

    out = _apply_enrichment([r1, r2], enrichment)
    # original columns preserved
    assert out[0]["Premium"] == "1000" and out[1]["Premium"] == "2000"
    # both rows of the same contract get identical enrichment
    for c in ENRICH_COLUMNS:
        assert out[0][c] == out[1][c] == enrichment[key][c]
    # column order: originals first, ENRICH_COLUMNS appended in order
    assert list(out[0].keys())[-len(ENRICH_COLUMNS):] == ENRICH_COLUMNS


def test_apply_enrichment_blanks_unmatched_contract():
    out = _apply_enrichment([_flow_row()], {})
    assert all(out[0][c] == "" for c in ENRICH_COLUMNS)


# ── _already_enriched ─────────────────────────────────────────────────────────

def test_already_enriched_detects_columns():
    enriched = {**_flow_row(), **{c: "" for c in ENRICH_COLUMNS}}
    assert _already_enriched([enriched]) is True
    assert _already_enriched([_flow_row()]) is False
    assert _already_enriched([]) is False


# ── date enumeration ──────────────────────────────────────────────────────────

def _client_with_compiled(dates_by_prefix):
    """MagicMock client whose list_files(prefix) returns compiled files."""
    client = MagicMock()

    def list_files(prefix):
        return [{"id": d, "name": f"{prefix}-{d.replace('-', '')}-compiled.csv"}
                for d in dates_by_prefix.get(prefix, [])]

    client.list_files.side_effect = list_files
    return client


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
    assert _enrichable_dates(client) == ["2026-06-09", "2026-06-10"]


# ── enrich_prefix (Drive integration, mocked) ─────────────────────────────────

_FLOW_CSV = (
    "Symbol,Type,Strike,Expires,Premium\n"
    "GSK,Put,50.00,2026-08-21T16:30:00-05:00,1000\n"
    "GSK,Put,50.00,2026-08-21T16:30:00-05:00,2000\n"
)


def _drive_client(csv_text, compiled_present=True):
    client = MagicMock()
    client.list_files.return_value = (
        [{"id": "fid", "name": "etfs-flow-20260609-compiled.csv"}] if compiled_present else []
    )
    client.download.return_value = csv_text
    client.get_or_create_date_folder.return_value = "folder"
    return client


def test_enrich_prefix_skips_when_no_compiled():
    client = _drive_client("", compiled_present=False)
    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=False, cache_only=False, force=False)
    assert res["status"] == "no-compiled"
    client.upload.assert_not_called()


def test_enrich_prefix_uploads_augmented_csv(monkeypatch, tmp_path):
    client = _drive_client(_FLOW_CSV)

    async def fake_fetch(contracts, trade_date, headless, cache_only=False, timeout_ms=15000):
        return {c["key"]: {date(2026, 6, 9): _hist_row("500"),
                           date(2026, 6, 10): _hist_row("650")}
                for c in contracts}

    monkeypatch.setattr(enrich_oi, "_fetch_histories", fake_fetch)

    uploaded = {}

    def capture_upload(local_path, name, folder_id):
        uploaded["rows"] = enrich_oi.parse_csv(local_path.read_text())
        return "newid"

    client.upload.side_effect = capture_upload

    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=False, cache_only=False, force=False)
    assert res["status"] == "enriched"
    assert res["contracts"] == 1 and res["with_next"] == 1
    client.upload.assert_called_once()
    rows = uploaded["rows"]
    assert len(rows) == 2
    for r in rows:
        assert r["oi_change"] == "150"
        assert r["Premium"] in ("1000", "2000")  # originals preserved


def test_enrich_prefix_dry_run_does_not_upload(monkeypatch):
    client = _drive_client(_FLOW_CSV)

    async def fake_fetch(contracts, trade_date, headless, cache_only=False, timeout_ms=15000):
        return {c["key"]: {} for c in contracts}

    monkeypatch.setattr(enrich_oi, "_fetch_histories", fake_fetch)

    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=True, cache_only=False, force=False)
    assert res["status"] == "enriched"
    client.upload.assert_not_called()


def test_enrich_prefix_skips_already_enriched(monkeypatch):
    enriched_csv = (
        "Symbol,Type,Strike,Expires,Premium," + ",".join(ENRICH_COLUMNS) + "\n"
        "GSK,Put,50.00,2026-08-21T16:30:00-05:00,1000," + ",".join([""] * len(ENRICH_COLUMNS)) + "\n"
    )
    client = _drive_client(enriched_csv)
    called = {"fetch": False}

    async def fake_fetch(*a, **k):
        called["fetch"] = True
        return {}

    monkeypatch.setattr(enrich_oi, "_fetch_histories", fake_fetch)

    res = enrich_prefix(client, "etfs-flow", "2026-06-09",
                        headless=True, dry_run=False, cache_only=False, force=False)
    assert res["status"] == "already-enriched"
    assert called["fetch"] is False
    client.upload.assert_not_called()
