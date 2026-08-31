"""Tests for `hedge_exposure`'s concentration series and trigger.

What is pinned here is METHODOLOGICAL, not populational: no count off the live
export appears in this file (a stored figure fingerprints a snapshot, per
CLAUDE.md). The properties tested are the ones a wrong answer would be silent
about — an absent greek treated as zero, the trigger reading an outcome field,
the constituent measure quietly counting the proxy, the committed constants
drifting.
"""
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest_study.lib import concentration as C  # noqa: E402
from scripts.backtest_study.lib import sectors  # noqa: E402


# ── fixtures ────────────────────────────────────────────────────────────────

class _Trade:
    """The bits of `harness.Trade` the trigger layer touches."""

    def __init__(self, signal_date, contracts, underlying, n_grid=10):
        self.signal_date = signal_date
        self.contracts = contracts
        self.row = {"entry_underlying": None if underlying is None else str(underlying)}
        d, grid = signal_date + timedelta(days=1), []
        while len(grid) < n_grid:
            if d.weekday() < 5:
                grid.append(d)
            d += timedelta(days=1)
        self.grid = grid


def _rec(ticker, delta, contracts=1, underlying=100.0, day="2025-01-06",
         days_held=3):
    sd = date.fromisoformat(day)
    return {
        "date": day, "ticker": ticker, "delta": delta, "days_held": days_held,
        "t": _Trade(sd, contracts, underlying),
    }


def _weekdays(start, n):
    out, d = [], date.fromisoformat(start)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


CAL = frozenset(_weekdays("2025-01-01", 40))


# ── committed constants (anti-tuning pin) ───────────────────────────────────

def test_committed_constants_are_the_preregistered_ones():
    assert C.TAU_GRID == (0.30, 0.35, 0.40)
    assert C.F_GRID == (0.25, 0.50, 1.00)
    assert C.HEDGE_PRESSURE_CUT == 50
    assert C.MIN_TRIGGER_DATES == 25
    assert C.HEDGE_PRESSURE_RE.pattern == \
        r"hedge[- ]pressure[^0-9]{0,15}(\d{1,3})\s*/\s*100"
    assert C.HEDGE_PRESSURE_RE.flags & re.IGNORECASE


# ── a missing greek is None, never 0.0 ──────────────────────────────────────

def test_missing_delta_is_none_not_zero():
    assert C.signed_delta_notional(_rec("NVDA", None)) is None


def test_missing_entry_underlying_is_none_not_zero():
    assert C.signed_delta_notional(_rec("NVDA", 0.5, underlying=None)) is None


def test_a_real_zero_delta_is_a_value():
    assert C.signed_delta_notional(_rec("NVDA", 0.0)) == 0.0


def test_unpriceable_positions_leave_the_denominator_alone():
    """An absent greek must not shrink book gross — that would move the trigger."""
    priced = [_rec("NVDA", 0.5), _rec("HYG", -0.5)]
    with_blank = priced + [_rec("TSLA", None)]
    occ_a = {date(2025, 1, 6): tuple(range(len(priced)))}
    occ_b = {date(2025, 1, 6): tuple(range(len(with_blank)))}
    a = C.concentration_series(priced, occ_a)[0]
    b = C.concentration_series(with_blank, occ_b)[0]
    assert b.n_unpriced == 1 and a.n_unpriced == 0
    assert b.book_gross == pytest.approx(a.book_gross)
    assert b.concentration == pytest.approx(a.concentration)


def test_signed_delta_notional_formula():
    assert C.signed_delta_notional(_rec("NVDA", 0.4, contracts=3, underlying=50.0)) \
        == pytest.approx(0.4 * 100 * 3 * 50.0)


# ── the concentration measure ───────────────────────────────────────────────

def test_concentration_is_top_cluster_net_over_book_gross():
    recs = [_rec("NVDA", 0.5), _rec("AMD", 0.5), _rec("HYG", -0.5)]
    sc = C.concentration_series(recs, {date(2025, 1, 6): (0, 1, 2)})[0]
    assert sc.top_cluster == "SEMIS"
    assert sc.concentration == pytest.approx(2 / 3)


def test_offsetting_legs_net_inside_a_cluster():
    """Signed, not gross: a long and a short in one cluster cancel."""
    recs = [_rec("NVDA", 0.5), _rec("AMD", -0.5), _rec("HYG", 0.5)]
    sc = C.concentration_series(recs, {date(2025, 1, 6): (0, 1, 2)})[0]
    assert sc.top_cluster == "CREDIT"
    assert sc.concentration == pytest.approx(1 / 3)


def test_unmapped_ticker_is_broad_not_dropped():
    recs = [_rec("ZZZZ", 0.5), _rec("NVDA", 0.5)]
    sc = C.concentration_series(recs, {date(2025, 1, 6): (0, 1)})[0]
    assert {c.name for c in sc.clusters} == {sectors.BROAD, "SEMIS"}


def test_unhedgeable_cluster_keeps_its_identity():
    """ENERGY/FINL/CRYPTO/INTL are never folded into BROAD."""
    sc = C.concentration_series([_rec("COIN", 0.5)],
                                {date(2025, 1, 6): (0,)})[0]
    assert sc.top_cluster == "CRYPTO"
    assert sc.top_proxy == "IBIT"
    assert sc.top_hedgeable is False


def test_empty_book_session_is_zero_not_an_error():
    sc = C.session_concentration([], (), date(2025, 1, 6))
    assert sc.concentration == 0.0 and sc.top_cluster is None


# ── DIRECT vs CONSTITUENT ───────────────────────────────────────────────────

def test_proxy_position_is_direct():
    sc = C.concentration_series([_rec("SMH", 0.5)], {date(2025, 1, 6): (0,)})[0]
    assert sc.stratum == sectors.DIRECT
    assert sc.top_direct_share == pytest.approx(1.0)


def test_single_name_position_is_constituent():
    sc = C.concentration_series([_rec("NVDA", 0.5)], {date(2025, 1, 6): (0,)})[0]
    assert sc.stratum == sectors.CONSTITUENT
    assert sc.top_direct_share == pytest.approx(0.0)


def test_stratum_follows_the_majority_of_the_top_cluster():
    recs = [_rec("SMH", 0.6), _rec("NVDA", 0.2)]
    sc = C.concentration_series(recs, {date(2025, 1, 6): (0, 1)})[0]
    assert sc.stratum == sectors.DIRECT
    assert sc.top_direct_share == pytest.approx(0.75)


def test_constituent_measure_excludes_the_proxy_leg():
    """The proxy's own exposure must not inflate the constituent series."""
    recs = [_rec("SMH", 0.9), _rec("NVDA", 0.1)]
    sc = C.concentration_series(recs, {date(2025, 1, 6): (0, 1)})[0]
    assert sc.concentration == pytest.approx(1.0)
    assert sc.constituent_concentration == pytest.approx(0.1)
    assert sc.constituent_top_cluster == "SEMIS"


# ── occupancy: the two readings of days_held ────────────────────────────────

def test_calendar_and_trading_readings_differ_and_both_are_available():
    rec = _rec("NVDA", 0.5, day="2025-01-06", days_held=5)
    cal = C.exit_bound(rec, C.HOLDING_CALENDAR)
    trd = C.exit_bound(rec, C.HOLDING_TRADING)
    assert cal == date(2025, 1, 11)          # +5 calendar days
    assert trd == rec["t"].grid[4]           # 5th weekday after the signal
    assert cal != trd


def test_default_holding_is_the_preregistered_calendar_reading():
    recs = [_rec("NVDA", 0.5, days_held=5)]
    a = C.open_book_by_session(recs, sessions=CAL)
    b = C.open_book_by_session(recs, C.HOLDING_CALENDAR, sessions=CAL)
    assert a == b


def test_occupancy_includes_the_signal_date_and_the_exit_bound():
    recs = [_rec("NVDA", 0.5, day="2025-01-06", days_held=3)]
    occ = C.open_book_by_session(recs, sessions=CAL)
    assert min(occ) == date(2025, 1, 6)
    assert max(occ) == date(2025, 1, 9)


def test_occupancy_skips_non_sessions():
    """A weekend/holiday inside the span is not a session."""
    recs = [_rec("NVDA", 0.5, day="2025-01-10", days_held=4)]   # Fri + 4 days
    occ = C.open_book_by_session(recs, sessions=CAL)
    assert date(2025, 1, 11) not in occ and date(2025, 1, 12) not in occ
    assert date(2025, 1, 13) in occ


def test_missing_days_held_does_not_invent_a_span():
    recs = [_rec("NVDA", 0.5, days_held=None)]
    occ = C.open_book_by_session(recs, sessions=CAL)
    assert list(occ) == [date(2025, 1, 6)]
    assert C.occupancy_diag(recs, sessions=CAL)["n_rows_no_days_held"] == 1


def test_bad_holding_is_refused():
    with pytest.raises(ValueError):
        C.exit_bound(_rec("NVDA", 0.5), "trading-days-ish")


def test_holding_disagreement_reports_both_counts():
    recs = [_rec("NVDA", 0.5, days_held=5)]
    d = C.holding_disagreement(recs, sessions=CAL)
    assert d["used"] == C.HOLDING_CALENDAR
    assert d["calendar_sessions"] and d["trading_sessions"]


# ── the trigger layer reads no outcome field ────────────────────────────────

def test_trigger_layer_never_reads_an_outcome_field():
    """`session_concentration` must survive records whose outcome keys raise."""
    class _Trap(dict):
        def __getitem__(self, k):
            assert k not in {"R", "E", "days_held", "exit_reason", "mfe", "mae"}, k
            return super().__getitem__(k)

        def get(self, k, default=None):
            assert k not in {"R", "E", "days_held", "exit_reason", "mfe", "mae"}, k
            return super().get(k, default)

    recs = [_Trap(_rec("NVDA", 0.5)), _Trap(_rec("HYG", -0.2))]
    sc = C.session_concentration(recs, (0, 1), date(2025, 1, 6))
    assert sc.top_cluster == "SEMIS"


# ── trigger selection, clustering, ARM CS gating ────────────────────────────

def _series(values, start="2025-01-01"):
    days = _weekdays(start, len(values))
    return [C.SessionConcentration(
        session=d, n_open=1, n_priced=1, n_unpriced=0, book_gross=1.0,
        concentration=v, top_cluster="SEMIS", top_proxy="SMH",
        top_hedgeable=True, top_direct_share=0.0,
        stratum=sectors.CONSTITUENT, constituent_concentration=v,
        constituent_top_cluster="SEMIS", clusters=())
        for d, v in zip(days, values)]


def test_triggered_sessions_uses_a_closed_lower_bound():
    ser = _series([0.29, 0.30, 0.31])
    assert len(C.triggered_sessions(ser, 0.30)) == 2


def test_measure_selects_the_series():
    ser = _series([0.9])
    assert C.measure_of(ser[0], C.MEASURE_CONSTITUENT) == 0.9
    with pytest.raises(ValueError):
        C.measure_of(ser[0], "whatever")


def test_stratum_filter_applies():
    ser = _series([0.9, 0.9])
    ser[0] = type(ser[0])(**{**ser[0].__dict__, "stratum": sectors.DIRECT})
    assert len(C.triggered_sessions(ser, 0.3, stratum=sectors.DIRECT)) == 1
    assert len(C.triggered_sessions(ser, 0.3, stratum=sectors.CONSTITUENT)) == 1


def test_no_hedge_pressure_parse_means_no_signal():
    ser = _series([0.9, 0.9, 0.9])
    hp = {ser[0].session.isoformat(): 80, ser[1].session.isoformat(): 10}
    got = C.triggered_sessions(ser, 0.3, hedge_pressure=hp)
    assert got == [ser[0].session]          # low score out, unparsed date out


def test_episodes_cluster_consecutive_sessions():
    ser = _series([0.9, 0.9, 0.0, 0.9])
    universe = [s.session for s in ser]
    trig = C.triggered_sessions(ser, 0.3)
    eps = C.episodes(trig, universe)
    assert [len(e) for e in eps] == [2, 1]


def test_trigger_date_counts_report_every_reading():
    ser = _series([0.9, 0.9])
    recs = [_rec("NVDA", 0.5, day=ser[0].session.isoformat())]
    counts = C.trigger_date_counts([s.session for s in ser], ser, recs)
    assert counts == {"sessions": 2, "episodes": 1, "book_dates": 1}


# ── hedge-pressure extraction ───────────────────────────────────────────────

def _analysis_csv(tmp_path, rows):
    p = tmp_path / "analysis - AnalysisClaude.csv"
    lines = ["date,ticker,regime"]
    lines += [f'{d},{t},"{r}"' for d, t, r in rows]
    p.write_text("\n".join(lines) + "\n")
    return p


def test_hedge_pressure_parses_the_committed_shapes(tmp_path):
    src = _analysis_csv(tmp_path, [
        ("2025-01-06", "MARKET", "BULL + L-VOL, hedge-pressure 62/100 today"),
        ("2025-01-07", "MARKET", "CHOP; Hedge Pressure of 15 / 100"),
        ("2025-01-08", "MARKET", "BEAR + H-VOL, no numeric read"),
    ])
    hp, diag = C.hedge_pressure_by_date(src)
    assert hp == {"2025-01-06": 62, "2025-01-07": 15}
    assert "2025-01-08" not in hp          # no parse == NO SIGNAL, not 0
    assert diag["n_dates"] == 3 and diag["n_dates_parsed"] == 2
    assert diag["n_dates_multivalued"] == 0


def test_hedge_pressure_flags_a_multivalued_date(tmp_path):
    src = _analysis_csv(tmp_path, [
        ("2025-01-06", "MARKET", "hedge-pressure 62/100"),
        ("2025-01-06", "NVDA", "hedge-pressure 20/100"),
    ])
    _, diag = C.hedge_pressure_by_date(src)
    assert diag["n_dates_multivalued"] == 1
    assert diag["multivalued_dates"] == ["2025-01-06"]


def test_hedge_pressure_regex_does_not_reach_across_prose(tmp_path):
    """The committed 0-15 character gap is what keeps an unrelated NN/100 out."""
    src = _analysis_csv(tmp_path, [
        ("2025-01-06", "MARKET",
         "hedge-pressure is not something we can score here; breadth 70/100"),
    ])
    hp, _ = C.hedge_pressure_by_date(src)
    assert hp == {}


def test_missing_analysis_export_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        C.hedge_pressure_by_date(tmp_path / "nope.csv")


# ── exposure table ──────────────────────────────────────────────────────────

def test_exposure_table_shares_sum_to_one():
    recs = [_rec("NVDA", 0.5), _rec("HYG", -0.25), _rec("IWM", 0.25)]
    rows = C.exposure_table(recs)
    assert sum(r["share"] for r in rows) == pytest.approx(1.0)
    assert {r["cluster"] for r in rows} == {"SEMIS", "CREDIT", "SMALL"}


def test_exposure_table_counts_unpriced_rows_without_pricing_them():
    recs = [_rec("NVDA", None), _rec("NVDA", 0.5)]
    row = C.exposure_table(recs)[0]
    assert row["rows"] == 2 and row["unpriced"] == 1


# ── occupancy from a SIMULATED book (hedge_concentration) ───────────────────
#
# `account_sim.simulate()` re-sizes and RE-EXITS what it admits, so the ROW's
# stored `days_held` describes a different position than the one that was held.
# These two helpers are the "extend by parameter, not by copy" the
# hedge_concentration registration asks for: the caller supplies the SIM's own
# window and the SIM's own contract counts, and `session_concentration` — the
# measure itself — is untouched.

class _Pos:
    """The bits of `account_sim.Pos` the occupancy layer touches."""

    def __init__(self, rec, contracts, entry_sess, exit_sess):
        self.rec = rec
        self.contracts = contracts
        self.entry_sess = entry_sess
        self.exit_sess = exit_sess


def test_occupancy_from_positions_is_the_inclusive_sim_window():
    rec = _rec("NVDA", 0.5, day="2025-01-06", days_held=1)
    pos = [_Pos(rec, 3, date(2025, 1, 7), date(2025, 1, 9))]
    occ = C.occupancy_from_positions(pos, CAL)
    assert sorted(occ) == [date(2025, 1, 7), date(2025, 1, 8), date(2025, 1, 9)]
    assert all(v == (0,) for v in occ.values())


def test_occupancy_from_positions_ignores_the_rows_stored_days_held():
    """The whole point: a position the sim re-exited is open over the SIM's
    window, not the one `exit_bound()` derives from the row."""
    rec = _rec("NVDA", 0.5, day="2025-01-06", days_held=30)
    pos = [_Pos(rec, 1, date(2025, 1, 7), date(2025, 1, 8))]
    assert sorted(C.occupancy_from_positions(pos, CAL)) == [
        date(2025, 1, 7), date(2025, 1, 8)]


def test_occupancy_from_positions_skips_non_sessions():
    rec = _rec("NVDA", 0.5, day="2025-01-06")
    pos = [_Pos(rec, 1, date(2025, 1, 9), date(2025, 1, 13))]
    got = sorted(C.occupancy_from_positions(pos, CAL))
    assert date(2025, 1, 11) not in got and date(2025, 1, 12) not in got
    assert got == [date(2025, 1, 9), date(2025, 1, 10), date(2025, 1, 13)]


def test_occupancy_from_positions_indexes_into_positions():
    a = _rec("NVDA", 0.5, day="2025-01-06")
    b = _rec("HYG", -0.25, day="2025-01-06")
    pos = [_Pos(a, 1, date(2025, 1, 7), date(2025, 1, 7)),
           _Pos(b, 1, date(2025, 1, 7), date(2025, 1, 8))]
    occ = C.occupancy_from_positions(pos, CAL)
    assert occ[date(2025, 1, 7)] == (0, 1)
    assert occ[date(2025, 1, 8)] == (1,)


def test_contracts_by_position_returns_the_sims_size_not_the_rows():
    rec = _rec("NVDA", 0.5, contracts=1)
    fn = C.contracts_by_position([_Pos(rec, 7, date(2025, 1, 7),
                                       date(2025, 1, 8))])
    assert C.default_contracts(rec) == 1
    assert fn(rec) == 7


def test_contracts_by_position_keys_on_record_IDENTITY():
    """Two equal-looking records are two positions; a (date, ticker) key would
    conflate them, and the blinded re-run pairs each position with a DIFFERENT
    record object carrying the same contracts."""
    a = _rec("NVDA", 0.5, contracts=1)
    b = _rec("NVDA", 0.5, contracts=1)
    fn = C.contracts_by_position([_Pos(a, 2, date(2025, 1, 7), date(2025, 1, 7)),
                                  _Pos(b, 5, date(2025, 1, 7), date(2025, 1, 7))])
    assert fn(a) == 2 and fn(b) == 5


def test_contracts_by_position_raises_on_a_foreign_record():
    """Better than silently falling back to the row's own count, which would
    move the trigger without saying so."""
    mine = _rec("NVDA", 0.5)
    fn = C.contracts_by_position([_Pos(mine, 3, date(2025, 1, 7),
                                       date(2025, 1, 7))])
    with pytest.raises(KeyError):
        fn(_rec("NVDA", 0.5))


def test_the_series_runs_over_the_sim_window_at_the_sim_contracts():
    """End to end: the two helpers feed `concentration_series` unchanged."""
    a = _rec("NVDA", 0.5, contracts=1)          # SEMIS
    b = _rec("TLT", 0.5, contracts=1)           # RATES
    pos = [_Pos(a, 3, date(2025, 1, 7), date(2025, 1, 7)),
           _Pos(b, 1, date(2025, 1, 7), date(2025, 1, 7))]
    recs = [p.rec for p in pos]
    series = C.concentration_series(
        recs, occupancy=C.occupancy_from_positions(pos, CAL),
        contracts_fn=C.contracts_by_position(pos))
    assert [sc.session for sc in series] == [date(2025, 1, 7)]
    # 3 contracts of NVDA against 1 of TLT: the sim's sizing decides the top
    # cluster, and the row's own `contracts` (1 each) would have tied.
    assert series[0].top_cluster == "SEMIS"
    assert series[0].concentration == pytest.approx(0.75)
