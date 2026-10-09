"""The holdout seal guard in scripts/backtest_study/lib/era.py.

research/pre-registrations/f4_deployment/holdout_seal.md (accepted by default
2026-10-09). These pin the code behaviour the registration relies on: which
dates are withheld from whom, that the guard withholds rather than refuses,
that the census counts only, and that no study module opens the exports
itself without passing them through the seal.

All fixtures are synthetic CSVs in tmp_path; nothing reads the real exports.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
import pytest

from scripts.backtest_study.lib import book, era
from tests.test_studies_book import (SIGNAL, _row, _stamp_calibrating,
                                     _write_csv)

ROOT = Path(__file__).resolve().parents[1]
STUDY_DIR = ROOT / "scripts" / "backtest_study"


# ── the dates, fixed by the registration ────────────────────────────────────

def test_registered_constants():
    """The registration's numbers. Changing one is a new registration."""
    assert era.SEAL_START == "2026-09-23"
    assert era.UNSEAL_PRICED_DATES == 40
    assert era.SEAL_LIFTED is None
    assert era.SEALED_READERS == {
        "holdout_seal": "2026-09-23",
        "refuse_floor_forward": "2026-10-08",
        "ticker_class": "2026-10-08",
        "narrow_to_fit": "2026-10-08",
    }


@pytest.mark.parametrize("date,reader,withheld", [
    ("2026-09-22", None, False),            # last spent date: open to all
    ("2026-09-23", None, True),             # first sealed date
    ("2027-03-01", None, True),             # the seal has no end date
    ("2026-09-23", "refuse_floor_forward", True),   # the gap stays sealed
    ("2026-10-07", "ticker_class", True),
    ("2026-10-08", "refuse_floor_forward", False),  # its own forward dates
    ("2026-10-08", "narrow_to_fit", False),
    ("2026-09-23", "holdout_seal", False),  # the one read sees everything
    ("2026-09-23 09:30:00", None, True),    # a timestamp suffix is ignored
    ("", None, False),
])
def test_is_withheld(date, reader, withheld):
    assert era.is_withheld(date, reader) is withheld


def test_unknown_reader_raises():
    with pytest.raises(ValueError, match="not a permitted sealed reader"):
        era.is_withheld("2026-10-08", "account_sim")


def test_lifted_seal_withholds_nothing(monkeypatch):
    monkeypatch.setattr(era, "SEAL_LIFTED", "2027-01-15")
    assert era.seal_floor(None) is None
    assert not era.is_withheld("2026-09-30")
    assert "lifted 2027-01-15" in era.seal_line({"rows": 0, "dates": 0, "reader": None})


# ── the filters ─────────────────────────────────────────────────────────────

def test_drop_sealed_rows_and_census():
    rows = [{"signal_date": d} for d in
            ("2026-09-22", "2026-09-23", "2026-09-23", "2026-10-08")]
    kept, info = era.drop_sealed(rows)
    assert [r["signal_date"] for r in kept] == ["2026-09-22"]
    assert info == {"rows": 3, "dates": 2, "reader": None}
    kept, info = era.drop_sealed(rows, reader="refuse_floor_forward")
    assert [r["signal_date"] for r in kept] == ["2026-09-22", "2026-10-08"]
    assert info["rows"] == 2


def test_drop_sealed_frame():
    df = pd.DataFrame({"signal_date": ["2026-09-01", "2026-09-30", "2026-10-09"],
                       "x": [1, 2, 3]})
    kept, info = era.drop_sealed_frame(df)
    assert kept["x"].tolist() == [1]
    assert info["rows"] == 2 and info["dates"] == 2
    kept, _ = era.drop_sealed_frame(df, reader="ticker_class")
    assert kept["x"].tolist() == [1, 3]


# ── load_book withholds, and still loads ───────────────────────────────────

@pytest.fixture
def one_row_book(tmp_path, monkeypatch):
    monkeypatch.setattr(book, "MECH_TABLE_CSV", tmp_path / "no_mech.csv")
    row = _stamp_calibrating(_row(ticker="AAA"), book.DEBIT_PROD)
    paths = dict(results=tmp_path / "r.csv", proxy=tmp_path / "p.csv",
                 analysis=tmp_path / "a.csv")
    _write_csv(paths["results"], [row])
    return paths


def _load(paths, **kw):
    return book.load_book(results_csv=paths["results"], proxy_csv=paths["proxy"],
                          analysis_csv=paths["analysis"], check_era=False, **kw)


def test_load_book_keeps_unsealed_rows(one_row_book):
    recs, diag = _load(one_row_book)
    assert len(recs) == 1
    assert diag["seal"]["rows"] == 0


def test_load_book_withholds_sealed_rows(one_row_book, monkeypatch, capsys):
    # Move the seal onto the fixture's signal date rather than re-dating the fixture.
    monkeypatch.setattr(era, "SEAL_START", SIGNAL.isoformat())
    recs, diag = _load(one_row_book)
    assert recs == []
    assert diag["seal"] == {"rows": 1, "dates": 1, "reader": None}
    assert "SEAL: withheld 1 rows on 1 signal dates" in capsys.readouterr().err


def test_load_book_named_reader_sees_from_its_floor(one_row_book, monkeypatch):
    monkeypatch.setattr(era, "SEAL_START", "2024-01-01")
    monkeypatch.setitem(era.SEALED_READERS, "refuse_floor_forward", SIGNAL.isoformat())
    recs, _ = _load(one_row_book, sealed_read="refuse_floor_forward")
    assert len(recs) == 1


def test_load_book_unknown_reader_raises_before_reading(tmp_path):
    with pytest.raises(ValueError):
        book.load_book(results_csv=tmp_path / "absent.csv", check_era=False,
                       sealed_read="account_sim")


# ── the census counts, and reads no outcome column ─────────────────────────

def _write(path, fields, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def test_seal_census_counts_priced_dates(tmp_path):
    rf = ["signal_date", "entry_option_price", "daily_price_csv", "realized_pnl_pct"]
    _write(tmp_path / "r.csv", rf, [
        {"signal_date": "2026-09-22", "entry_option_price": "1", "daily_price_csv": "1,2"},
        {"signal_date": "2026-09-23", "entry_option_price": "1", "daily_price_csv": "1,2"},
        {"signal_date": "2026-09-24", "entry_option_price": "", "daily_price_csv": ""},
    ])
    pf = rf + ["proxy_method"]
    _write(tmp_path / "p.csv", pf, [
        {"signal_date": "2026-09-25", "entry_option_price": "1", "daily_price_csv": "1",
         "proxy_method": "strike_expiry_tweak"},
        {"signal_date": "2026-09-26", "entry_option_price": "1", "daily_price_csv": "1",
         "proxy_method": "bs_options_hist"},
    ])
    _write(tmp_path / "a.csv", ["date", "ticker"],
           [{"date": "2026-09-29", "ticker": "AAA"}])
    c = era.seal_census({"results": tmp_path / "r.csv", "proxy": tmp_path / "p.csv",
                         "analysis": tmp_path / "a.csv"})
    assert c["exports"]["results"] == {"rows": 2, "dates": 2, "exists": True}
    assert c["exports"]["analysis"]["rows"] == 1
    assert c["priced_dates"] == 2           # 09-23 real, 09-25 tweak; bs never counts
    assert c["condition_met"] is False


def test_census_never_names_an_outcome_column():
    """The census is a count. It may test that a row is priced, never what it made."""
    src = Path(era.__file__).read_text()
    body = src[src.index("def _priced"):src.index("def print_seal_census")]
    for col in ("pnl", "realized", "mfe", "mae", "exit_", "pl_"):
        assert col not in body, col


# ── no study opens the exports around the seal ─────────────────────────────

# Modules that resolve the export paths themselves but read no outcome from
# them, each with the reason. Everything else that resolves a path must pass
# its rows through `drop_sealed` / `drop_sealed_frame` or go through load_book.
CENSUS_ONLY = {
    "run.py": "report headers: paths, row counts, era",
    "lib/era.py": "the guard itself",
    "lib/book.py": "load_book applies the guard",
    "lib/concentration.py": "parses analysis prose; outcomes come via load_book",
    "lib/text_corpus.py": "analysis text; outcomes come via load_book",
    "lib/live_select.py": "evaluation-method and structure census",
    "f1_selection/prompt_eval.py": "era label and play counts; arm books via load_book",
    "f1_selection/v4_bridge.py": "composition of emitted plays (analysis export only)",
    "f4_deployment/refuse_floor_forward.py": "export row counts; its book via load_book",
}
_PATH_USE = re.compile(r"resolve_paths\(|DEFAULT_RESULTS_CSV|DEFAULT_PROXY_CSV|"
                       r"\bEVAL_DIR\b|BR_PATH|BP_PATH")


def test_every_export_reader_passes_the_seal():
    offenders = []
    for path in sorted(STUDY_DIR.rglob("*.py")):
        rel = path.relative_to(STUDY_DIR).as_posix()
        src = path.read_text()
        if not _PATH_USE.search(src) or rel in CENSUS_ONLY:
            continue
        if "drop_sealed" not in src:
            offenders.append(rel)
    assert not offenders, (
        "these modules open the exports without the holdout seal; filter their "
        f"rows with era.drop_sealed / drop_sealed_frame, or load via load_book: {offenders}")


def test_census_only_list_is_current():
    """A stale allow-list entry would hide a later outcome read."""
    for rel in CENSUS_ONLY:
        assert (STUDY_DIR / rel).exists(), rel
