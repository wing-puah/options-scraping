"""Tests for lib.counterpart_iv — counterpart-leg selection and sidecar lookup."""
from datetime import date

from lib.counterpart_iv import build_iv_lookup, contract_key, needed_counterparts


def _row(symbol, opt_type, strike, expires, dte):
    """Minimal flow row (real column names) for counterpart selection."""
    return {"Symbol": symbol, "Type": opt_type, "Strike": strike,
            "Expires": expires, "DTE": dte}


def test_needed_counterparts_single_sided_call_needs_put():
    rows = [_row("X", "Call", "100", "2026-08-21T16:30:00-05:00", "30")]
    got = needed_counterparts(rows)
    assert len(got) == 1
    c = got[0]
    assert c["opt_type"] == "put"
    assert c["strike"] == 100.0
    assert c["expiration"] == date(2026, 8, 21)
    assert c["key"] == contract_key("X", "put", 100.0, date(2026, 8, 21))


def test_needed_counterparts_matched_pair_needs_nothing():
    rows = [
        _row("X", "Call", "100", "2026-08-21T16:30:00-05:00", "30"),
        _row("X", "Put", "100", "2026-08-21T16:30:00-05:00", "30"),
    ]
    assert needed_counterparts(rows) == []


def test_needed_counterparts_excludes_out_of_window():
    # DTE 5 and DTE 200 are outside the 10–60 window → no counterpart fetched.
    rows = [
        _row("X", "Call", "100", "2026-07-06T16:30:00-05:00", "5"),
        _row("Y", "Put", "50", "2027-06-18T16:30:00-05:00", "200"),
    ]
    assert needed_counterparts(rows) == []


def test_needed_counterparts_dedupes_across_trades():
    # Two call trades on the same contract → a single put counterpart.
    rows = [
        _row("X", "Call", "100", "2026-08-21T16:30:00-05:00", "30"),
        _row("X", "Call", "100", "2026-08-21T16:30:00-05:00", "30"),
    ]
    assert len(needed_counterparts(rows)) == 1


def test_build_iv_lookup_parses_and_drops_blank_iv():
    rows = [
        {"Symbol": "X", "Type": "Put", "Strike": "100",
         "Expires": "2026-08-21", "iv": "40.5", "oi": "500", "vol": "12"},
        # Blank IV (Barchart returned nothing) → dropped from the lookup.
        {"Symbol": "X", "Type": "Call", "Strike": "110",
         "Expires": "2026-08-21", "iv": "", "oi": "", "vol": ""},
    ]
    lut = build_iv_lookup(rows)
    assert set(lut) == {"X"}
    assert len(lut["X"]) == 1
    c = lut["X"][0]
    assert c["opt_type"] == "put"
    assert c["strike"] == 100.0
    assert c["expiry"] == "2026-08-21"
    assert c["iv"] == 40.5
    assert c["oi"] == 500.0
    assert c["vol"] == 12.0
