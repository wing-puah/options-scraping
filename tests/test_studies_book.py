"""Unit tests for backtests/study/book.py — the pooled cross-structure book
loader. All fixtures are tiny synthetic CSVs written to tmp_path; nothing here
touches the real (gitignored, untracked) backtests/to_evaluate/ exports or the
network, so these must stay green regardless of what's on the laptop.
"""
from datetime import date, timedelta

import pytest

from scripts.backtest.helpers import _weekday_grid
from backtests.study import book
from backtests.study.harness import Trade, replay

SIGNAL = date(2024, 3, 4)     # Monday
EXPIRY = date(2024, 3, 15)    # Friday, 11 calendar days out
DTE = (EXPIRY - SIGNAL).days
GRID_LEN = len(_weekday_grid(SIGNAL, SIGNAL + timedelta(days=min(DTE, 120))))

_BASE = {
    "market_regime": "BULL L-VOL", "regime": "BULL L-VOL", "horizon": "short",
    "delta": "0.30", "iv_entry_pct": "40", "entry_premium_total": "100",
    "max_loss_per_contract": "100", "mfe_pct": "0.5", "mae_pct": "-0.1",
    "mfe_day": "3", "mae_day": "1", "score_total": "10", "score_flow": "1",
    "score_dealer": "1", "score_price": "1", "score_vol": "1", "score_catalyst": "1",
    "pnl_at_cap_pct": "1.10", "created_datetime": "2024-03-04 09:00:00",
}


def _row(ticker="AAA", structure="long_call", entry=1.00, marks=None, contracts=1,
        legs=None, opt_type="C", **extra):
    legs = legs or f"{ticker}:{EXPIRY.isoformat()}:100:{opt_type} +1"
    if marks is None:
        marks = [1.00] * (GRID_LEN - 1) + [2.10]  # last day: pl = +1.10
    row = dict(_BASE)
    row.update({
        "signal_date": SIGNAL.isoformat(), "ticker": ticker, "structure": structure,
        "legs": legs, "contracts": str(contracts), "dte_entry": str(DTE),
        "entry_option_price": str(entry),
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
        "play": f"[DIRECTIONAL]\n{ticker} test play {structure}",
    })
    row.update(extra)
    return row


def _stamp_calibrating(row, prod):
    """Fill exit_reason/days_held/realized_pnl_pct from an ACTUAL replay of the
    row's own marks under `prod`, so the calibration gate passes."""
    t = Trade(dict(row))
    rp = replay(t, **prod)
    row["exit_reason"] = rp["exit_reason"]
    row["days_held"] = str(rp["days_held"])
    row["realized_pnl_pct"] = str(round(rp["pnl_pct"], 4))
    return row


def _stamp_noncalibrating(row):
    """Stored outcome that cannot match any replay of these marks."""
    row["exit_reason"] = "time_exit"
    row["days_held"] = "999"
    row["realized_pnl_pct"] = "-0.9999"
    return row


def _write_csv(path, rows, extra_fields=()):
    import csv
    fieldnames = sorted(set().union(*[r.keys() for r in rows]) | set(extra_fields)) if rows else []
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)


@pytest.fixture
def paths(tmp_path):
    return dict(
        results=tmp_path / "results.csv",
        proxy=tmp_path / "proxy.csv",
        analysis=tmp_path / "no_such_analysis.csv",  # deliberately absent by default
    )


@pytest.fixture(autouse=True)
def _isolate_mech_table(tmp_path, monkeypatch):
    """Every test gets its own (missing) mech table unless it opts in, so
    results never depend on the laptop-only backtests/mech_regime/ file."""
    monkeypatch.setattr(book, "MECH_TABLE_CSV", tmp_path / "no_such_mech_table.csv")


def _load(paths, **kw):
    return book.load_book(results_csv=paths["results"], proxy_csv=paths["proxy"],
                          analysis_csv=paths["analysis"], **kw)


# ── dup drop against the real book ──────────────────────────────────────────

def test_proxy_dup_of_real_row_is_dropped(paths):
    real_row = _row(ticker="AAA", structure="long_call")
    _stamp_calibrating(real_row, book.DEBIT_PROD)
    _write_csv(paths["results"], [real_row])

    dup_row = _row(ticker="AAA", structure="long_call", proxy_method="strike_expiry_tweak")
    _stamp_calibrating(dup_row, book.DEBIT_PROD)
    _write_csv(paths["proxy"], [dup_row])

    records, diag = _load(paths)
    assert diag["n_dup_dropped"] == 1
    assert [r["source"] for r in records] == ["real"]


# ── bs excluded by default, included with the flag ──────────────────────────

def test_bs_rows_excluded_by_default(paths):
    _write_csv(paths["results"], [])
    bs_row = _row(ticker="BBB", structure="bull_call_spread", proxy_method="bs_options_hist")
    _stamp_calibrating(bs_row, book.DEBIT_PROD)
    _write_csv(paths["proxy"], [bs_row])

    records, diag = _load(paths, include_bs=False)
    assert records == []
    assert diag["counts_by_source"]["bs"] == 1  # still counted in the full parse

    records, diag = _load(paths, include_bs=True)
    assert len(records) == 1
    assert records[0]["source"] == "bs"


# ── credit admitted ungated; non-reproducing debit proxy excluded ──────────

def test_credit_proxy_row_admitted_without_calibration_gate(paths):
    _write_csv(paths["results"], [])
    credit_row = _row(ticker="CCC", structure="bull_put_spread", entry=-1.00,
                      opt_type="P", proxy_method="strike_expiry_tweak")
    _stamp_noncalibrating(credit_row)  # would fail any exact-replay gate
    _write_csv(paths["proxy"], [credit_row])

    records, diag = _load(paths)
    assert len(records) == 1
    rec = records[0]
    assert rec["credit"] is True
    assert rec["calibrated"] is False
    assert diag["n_credit_ungated"] == 1
    assert diag["n_proxy_excluded_non_exact"] == 0


def test_noncalibrating_debit_proxy_row_is_excluded(paths):
    _write_csv(paths["results"], [])
    bad_row = _row(ticker="DDD", structure="bull_call_spread", entry=1.00,
                   proxy_method="strike_expiry_tweak")
    _stamp_noncalibrating(bad_row)  # exit_reason/days_held/pnl don't match the replay
    _write_csv(paths["proxy"], [bad_row])

    records, diag = _load(paths)
    assert records == []
    assert diag["n_proxy_excluded_non_exact"] == 1


def test_real_debit_row_kept_even_on_hard_calibration_mismatch(paths):
    """Real rows are never dropped by the gate — mismatches are diagnostic only."""
    row = _row(ticker="EEE", structure="bull_call_spread", entry=1.00)
    _stamp_noncalibrating(row)
    _write_csv(paths["results"], [row])
    _write_csv(paths["proxy"], [])

    records, diag = _load(paths)
    assert len(records) == 1
    assert records[0]["calibrated"] is False
    assert diag["debit_calib"] == {"n": 1, "exact": 0, "near": 0, "hard": 1}


# ── numeric parse: missing stays None, never 0 ──────────────────────────────

def test_missing_numeric_fields_parse_to_none(paths):
    row = _row(ticker="FFF", structure="long_call", delta="", iv_entry_pct="",
              mfe_pct="", score_vol="")
    _stamp_calibrating(row, book.DEBIT_PROD)
    _write_csv(paths["results"], [row])
    _write_csv(paths["proxy"], [])

    records, _ = _load(paths)
    rec = records[0]
    assert rec["delta"] is None
    assert rec["iv_entry"] is None
    assert rec["mfe"] is None
    assert rec["score_vol"] is None
    # sanity: a populated field on the same row is NOT None
    assert rec["max_loss_per_contract"] == 100.0


# ── mech_cell fallback ──────────────────────────────────────────────────────

def test_mech_cell_falls_back_to_prod_when_table_missing(paths):
    """The autouse fixture points MECH_TABLE_CSV at a nonexistent file."""
    row = _row(ticker="GGG", structure="long_call")
    _stamp_calibrating(row, book.DEBIT_PROD)
    _write_csv(paths["results"], [row])
    _write_csv(paths["proxy"], [])

    records, diag = _load(paths)
    assert records[0]["mech_cell"] == "PROD"
    assert records[0]["mech_direction"] is None
    assert diag["mech_table_warning"] is not None


def test_mech_cell_falls_back_to_prod_before_table_lookback(tmp_path, monkeypatch, paths):
    """Table COVERS the signal date (last_date is past it, so no coverage
    warning) but there aren't 50 rows of history yet -> unlabelled -> PROD."""
    import csv as _csv
    p = tmp_path / "mech.csv"
    with open(p, "w", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["date", "spy_close", "vix_close"])
        d = date(2024, 2, 1)
        while d <= date(2024, 3, 10):  # 39 rows total: never reaches the 50-SMA window
            w.writerow([d.isoformat(), "480.0", "13.0"])
            d += timedelta(days=1)
    monkeypatch.setattr(book, "MECH_TABLE_CSV", p)

    row = _row(ticker="HHH", structure="long_call")
    _stamp_calibrating(row, book.DEBIT_PROD)
    _write_csv(paths["results"], [row])
    _write_csv(paths["proxy"], [])

    records, diag = _load(paths)
    assert records[0]["mech_cell"] == "PROD"
    # table exists and covers the date, so no "missing/stale table" warning —
    # this is the "labelled fine, no override cell" / "no 50-SMA yet" case.
    assert diag["mech_table_warning"] is None


# ── source/include_bs filtering leaves diag counts intact ──────────────────

def test_sources_filter_overrides_include_bs(paths):
    _write_csv(paths["results"], [])
    tweak_row = _row(ticker="III", structure="bull_call_spread",
                     proxy_method="strike_expiry_tweak")
    _stamp_calibrating(tweak_row, book.DEBIT_PROD)
    bs_row = _row(ticker="JJJ", structure="bull_call_spread",
                  proxy_method="bs_options_hist")
    _stamp_calibrating(bs_row, book.DEBIT_PROD)
    _write_csv(paths["proxy"], [tweak_row, bs_row])

    records, _ = _load(paths, include_bs=True, sources={"bs"})
    assert [r["source"] for r in records] == ["bs"]
