"""The stored row's own basis in `lib/replay_basis.py` — the three operator
rulings of 2026-09-28 that let the frozen harness calibrate a re-priced row:

  1. the stored P&L is net of `cost_total`; the comparison adds it back
     (a row with blank `cost_basis` is compared as before);
  2. the replay stops at `path_data_end`, so an `open_at_data_end` row
     reproduces as the `cap_open` outcome production booked;
  3. a deferred exit fill is its own `deferred_fill` bucket, never HARD;
     `no_two_sided` is compared as normal.

Synthetic rows only; the harness itself is untouched and pinned elsewhere
(tests/test_harness_replay.py).
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study.lib import book
from scripts.backtest_study.lib import mtm_curve as MC
from scripts.backtest_study.lib import replay_basis as RB
from scripts.backtest_study.lib.book import DEBIT_PROD
from scripts.backtest_study.lib.harness import Trade, replay

SIGNAL = date(2024, 3, 4)            # Monday
EXPIRY = date(2024, 5, 3)            # 60 calendar days: tef 0.75 fires on day 45
DTE = (EXPIRY - SIGNAL).days
GRID = _weekday_grid(SIGNAL, SIGNAL + timedelta(days=min(DTE, 120)))
UNREACH = RB.unreachable_reasons(DEBIT_PROD)
DATA_END_IDX = 10                    # 1-based grid index of the last real quote


def _row(marks, contracts=2, **extra):
    row = {
        "signal_date": SIGNAL.isoformat(), "ticker": "AAA", "structure": "long_call",
        "legs": f"AAA:{EXPIRY.isoformat()}:100:C +1", "contracts": str(contracts),
        "dte_entry": str(DTE), "entry_option_price": "1.0",
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
        "daily_pnl_csv": ",".join("" if m is None else f"{(m - 1.0) * 100:.2f}"
                                  for m in marks),
    }
    row.update(extra)
    return row


def _stamp(row, cost_total=None, prod=DEBIT_PROD, trade=None):
    """Stored outcome as PRODUCTION writes it: the gross replay, then net of
    the cost in `simulate._apply_costs`'s own two rounding steps."""
    t = trade or Trade(dict(row))
    rp = replay(t, **prod)
    gross = round(rp["pnl_pct"], 4)
    pos_dollars = t.denom * 100 * t.contracts
    row["exit_reason"] = rp["exit_reason"]
    row["days_held"] = str(rp["days_held"])
    abs_gross = round(rp["pnl_pct"] * pos_dollars, 2)
    if cost_total is None:
        row["realized_pnl_pct"] = str(gross)
        row["realized_pnl_abs"] = str(abs_gross)
        row["cost_basis"] = ""
    else:
        row["realized_pnl_pct"] = str(round(gross - cost_total / pos_dollars, 4))
        row["realized_pnl_abs"] = str(round(abs_gross - cost_total, 2))
        row["cost_total"] = str(cost_total)
        row["cost_basis"] = "commission_only"
    return row


def _winner():
    """Hits the 0.90 profit target on day 5."""
    return [1.0, 1.2, 1.4, 1.6, 1.95] + [1.95] * (len(GRID) - 5)


# ── ruling 1: the cost goes back on before comparing ───────────────────────

def test_a_net_of_cost_row_reproduces_once_the_cost_is_added_back():
    row = _stamp(_row(_winner()), cost_total=2.60)
    kind, want, got = RB.classify(Trade(row), DEBIT_PROD, UNREACH)
    assert kind == "exact"
    assert want == got == ("profit_target", 5, 0.95)


def test_the_same_net_figure_without_a_cost_basis_is_still_hard():
    """A pre-cost-model row (blank `cost_basis`) is compared as before: its
    stored figure is taken as gross, so a net number cannot hide there."""
    row = _stamp(_row(_winner()), cost_total=2.60)
    row["cost_basis"] = ""
    assert RB.classify(Trade(row), DEBIT_PROD, UNREACH)[0] == "hard"


def test_a_wrong_cost_does_not_reproduce():
    row = _stamp(_row(_winner()), cost_total=2.60)
    row["cost_total"] = "9.10"
    assert RB.classify(Trade(row), DEBIT_PROD, UNREACH)[0] not in ("exact", "near")


def test_stored_gross_dollars_is_abs_plus_cost():
    row = _stamp(_row(_winner()), cost_total=2.60)
    t = Trade(row)
    assert RB.stored_gross_dollars(t) == pytest.approx(190.0)
    assert RB.replay_dollars(t, DEBIT_PROD) == pytest.approx(190.0)


# ── ruling 2: the replay stops at the data end ──────────────────────────────

def _open_at_data_end_row(cost_total=2.60):
    """Flat until the data ends on grid day 10, carried after it. Production
    books it `cap_open` on day 10; a full-length replay walks the carried
    marks to the day-45 time exit instead."""
    marks = [1.0] * len(GRID)
    row = _row(marks, path_status="open_at_data_end",
               path_data_end=GRID[DATA_END_IDX - 1].isoformat(), exit_fill="same_day")
    t_cut = RB.bounded(Trade(dict(row)))
    return _stamp(row, cost_total=cost_total, trade=t_cut)


def test_bounded_cuts_at_the_data_end_and_never_claims_expiry():
    t = Trade(_open_at_data_end_row())
    v = RB.bounded(t)
    assert len(v.grid) == len(v.marks) == DATA_END_IDX
    assert v.cap_reached_expiry is False
    assert v.uncut_grid_len == len(GRID)
    assert len(t.grid) == len(GRID)          # the original is not touched


def test_an_open_at_data_end_row_reproduces_as_cap_open():
    row = _open_at_data_end_row()
    assert (row["exit_reason"], row["days_held"]) == ("cap_open", str(DATA_END_IDX))
    t = Trade(row)
    assert replay(t, **DEBIT_PROD)["exit_reason"] == "time_exit"   # the old failure
    assert RB.classify(t, DEBIT_PROD, UNREACH)[0] == "exact"


def test_bounded_is_a_no_op_without_a_data_end_or_past_the_last_mark():
    t = Trade(_row(_winner()))
    assert RB.bounded(t) is t
    marks = [1.0] * DATA_END_IDX + [None] * (len(GRID) - DATA_END_IDX)
    t2 = Trade(_row(marks, path_data_end=GRID[DATA_END_IDX - 1].isoformat()))
    assert RB.bounded(t2) is t2


def test_a_data_end_before_the_first_mark_keeps_the_first_priced_day():
    marks = [None, None, 1.0] + [1.0] * (len(GRID) - 3)
    t = Trade(_row(marks, path_data_end=(SIGNAL - timedelta(days=1)).isoformat()))
    v = RB.bounded(t)
    assert len(v.marks) == 3 and v.marks[-1] == 1.0


def test_mtm_curve_reads_a_bounded_trade():
    row = _open_at_data_end_row()
    t = RB.bounded(Trade(row))
    pos = SimpleNamespace(rec={"t": t, "ticker": "AAA", "date": SIGNAL.isoformat()},
                          contracts=2, days_held=DATA_END_IDX)
    sessions, dollars, _ = MC.position_marks(pos)
    assert len(sessions) == DATA_END_IDX
    assert dollars[-1] == pytest.approx(0.0)


# ── ruling 3: a deferred fill is a superseded basis ─────────────────────────

def test_a_deferred_fill_is_its_own_bucket_never_hard():
    row = _stamp(_row(_winner()), cost_total=2.60)
    row["exit_fill"] = "deferred_2"
    row["days_held"] = "7"                   # filled two days after the trigger
    assert RB.classify(Trade(row), DEBIT_PROD, UNREACH)[0] == "deferred_fill"


def test_no_two_sided_is_compared_as_normal():
    """Production filled it on the trigger day's mark, as the harness does."""
    row = _stamp(_row(_winner()), cost_total=2.60)
    row["exit_fill"] = "no_two_sided"
    assert RB.classify(Trade(row), DEBIT_PROD, UNREACH)[0] == "exact"
    row["days_held"] = "7"
    assert RB.classify(Trade(row), DEBIT_PROD, UNREACH)[0] == "hard"


# ── the loader: outcomes kept, counted, and the record's Trade is cut ───────

def _write(path, rows):
    import csv
    fields = sorted(set().union(*[r.keys() for r in rows])) if rows else ["signal_date"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(book, "MECH_TABLE_CSV", tmp_path / "none.csv")
    return tmp_path / "results.csv", tmp_path / "proxy.csv"


def test_load_book_keeps_open_and_deferred_rows_and_counts_them(paths, capsys):
    results, proxy = paths
    real_open = _open_at_data_end_row()
    deferred = _stamp(_row(_winner(), ticker="BBB"), cost_total=2.60)
    deferred.update(ticker="BBB", exit_fill="deferred_2", days_held="7",
                    proxy_method="strike_expiry_tweak",
                    # the export's data reaches the open row's window end, so
                    # that row's window is CLOSED and it stays an outcome
                    path_status="complete", path_data_end=GRID[-1].isoformat())
    _write(results, [real_open])
    _write(proxy, [deferred])
    recs, diag = book.load_book(results, proxy, None, check_era=False)
    assert len(recs) == 2
    by_src = {r["source"]: r for r in recs}
    assert by_src["real"]["calibrated"] is True
    assert len(by_src["real"]["t"].grid) == DATA_END_IDX
    assert by_src["tweak"]["calibrated"] is False
    assert diag["n_proxy_admitted_deferred"] == 1
    assert diag["path_outcomes"]["open_at_data_end"] == 1
    assert diag["path_outcomes"]["deferred_fill"] == 1
    assert "1 open_at_data_end" in capsys.readouterr().err
    assert diag["pending"]["n"] == 0
    assert diag["pending"]["n_closed_window_open"] == 1


# ── ruling 2026-10-21: a row still inside its path window is PENDING ────────

def _complete_row(ticker, data_end_idx):
    """A finished row whose data reaches grid day `data_end_idx`: it sets the
    export's as-of and is never itself pending."""
    row = _stamp(_row(_winner()), cost_total=2.60)
    row.update(ticker=ticker, path_status="complete",
               path_data_end=GRID[data_end_idx - 1].isoformat())
    return row


def test_window_end_is_productions_path_end():
    from scripts.backtest.shared.history import path_end
    t = Trade(_open_at_data_end_row())
    assert book.window_end(t) == path_end(SIGNAL, [EXPIRY], 120) == EXPIRY


def test_is_pending_only_for_open_rows_with_a_session_left():
    t_open = Trade(_open_at_data_end_row())
    assert book.is_pending(t_open, GRID[DATA_END_IDX - 1]) is True
    assert book.is_pending(t_open, EXPIRY) is False          # window closed
    assert book.is_pending(t_open, EXPIRY - timedelta(days=1)) is True
    t_done = Trade(_complete_row("CCC", 20))
    assert book.is_pending(t_done, SIGNAL) is False         # never pending


def test_a_window_ending_on_a_weekend_is_closed_by_the_friday_before():
    sat = date(2024, 5, 4)
    row = _open_at_data_end_row()
    row["legs"] = f"AAA:{sat.isoformat()}:100:C +1"
    t = Trade(row)                    # same weekday grid: Saturday adds no day
    assert book.window_end(t) == sat
    assert book.is_pending(t, EXPIRY) is False                # Friday 2024-05-03


def test_load_book_excludes_a_pending_open_row_and_says_so(paths, capsys):
    results, proxy = paths
    pending = _open_at_data_end_row()                 # data end day 10
    done = _complete_row("CCC", 20)                   # as-of = day 20 < window end
    _write(results, [pending, done])
    _write(proxy, [])
    recs, diag = book.load_book(results, proxy, None, check_era=False)
    assert [r["ticker"] for r in recs] == ["CCC"]
    assert recs[0]["pending"] is False
    assert diag["pending"]["as_of"] == GRID[19].isoformat()
    assert diag["pending"]["n"] == 1
    assert diag["pending"]["by_source"]["real"] == 1
    assert diag["pending"]["n_closed_window_open"] == 0
    assert diag["path_outcomes"]["open_at_data_end"] == 0
    err = capsys.readouterr().err
    assert "pending: 1 open_at_data_end rows" in err and "excluded" in err


def test_load_book_admits_a_closed_window_open_row(paths, capsys):
    results, proxy = paths
    closed = _open_at_data_end_row()
    done = _complete_row("CCC", len(GRID))            # as-of = the window end
    _write(results, [closed, done])
    _write(proxy, [])
    recs, diag = book.load_book(results, proxy, None, check_era=False)
    by_t = {r["ticker"]: r for r in recs}
    assert set(by_t) == {"AAA", "CCC"}
    assert by_t["AAA"]["exit_reason"] == "cap_open"
    assert by_t["AAA"]["calibrated"] is True
    assert len(by_t["AAA"]["t"].grid) == DATA_END_IDX
    assert diag["pending"]["n"] == 0
    assert diag["pending"]["n_closed_window_open"] == 1
    assert "1 closed-window open rows kept" in capsys.readouterr().err


def test_a_complete_row_is_untouched_by_the_pending_rule(paths):
    results, proxy = paths
    done = _complete_row("CCC", 20)
    _write(results, [done])
    _write(proxy, [])
    recs, diag = book.load_book(results, proxy, None, check_era=False)
    assert len(recs) == 1 and recs[0]["pending"] is False
    assert recs[0]["exit_reason"] == "profit_target"
    assert diag["pending"]["n"] == 0


def test_include_pending_keeps_and_flags_the_pending_row(paths, capsys):
    results, proxy = paths
    _write(results, [_open_at_data_end_row(), _complete_row("CCC", 20)])
    _write(proxy, [])
    recs, diag = book.load_book(results, proxy, None, check_era=False,
                                include_pending=True)
    flags = {r["ticker"]: r["pending"] for r in recs}
    assert flags == {"AAA": True, "CCC": False}
    assert diag["pending"]["n"] == 1 and diag["pending"]["kept"] is True
    assert "kept (include_pending)" in capsys.readouterr().err


def test_a_pending_proxy_row_is_counted_under_its_source(paths):
    results, proxy = paths
    prox = _open_at_data_end_row()
    prox.update(ticker="DDD", proxy_method="strike_expiry_tweak")
    _write(results, [_complete_row("CCC", 20)])
    _write(proxy, [prox])
    recs, diag = book.load_book(results, proxy, None, check_era=False)
    assert [r["ticker"] for r in recs] == ["CCC"]
    assert diag["pending"]["by_source"] == {"real": 0, "tweak": 1}
