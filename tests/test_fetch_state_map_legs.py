"""fetch_state_map_legs: the list comes from `q4_fetch_list`, the dry run is
offline, a 404 is recorded unlisted and a network error is not. No network."""
from __future__ import annotations

from datetime import date

import pytest

from lib.barchart import session as bs
from scripts.backtest.shared import history, unlisted
from scripts.collector.study_legs.f1_selection import fetch_state_map_legs as F

PLAN = [dict(ticker="SPY", expiration=date(2026, 4, 17), strike=632.0,
             opt_type="Put", category="state_map:S-EVOL")]


@pytest.fixture
def no_network(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("network fetch attempted")
    monkeypatch.setattr(history, "fetch_option_histories", boom)
    monkeypatch.setattr(F, "plan", lambda: list(PLAN))


def test_plan_is_q4_fetch_list(monkeypatch):
    """`plan` feeds the study's own trades through `q4_fetch_list` and nothing else."""
    import numpy as np
    cal = F.SM.Cal(["2022-02-01"], np.array([1.0]), np.array([1.0]), np.array([1.0]),
                   np.array([1.0]), np.array([1.0]))
    monkeypatch.setattr(F.SM, "load_inputs", lambda r: ([], {}, {}, {}, {}, []))
    monkeypatch.setattr(F.SM, "build_cal", lambda *a: cal)
    monkeypatch.setattr(F.SM, "cut_cal", lambda c, e: c)
    monkeypatch.setattr(F.SM, "write_mech_csv", lambda *a: None)
    monkeypatch.setattr(F.SM, "labels_from_labeler",
                        lambda *a: type("L", (), {"vol": "v"})())
    monkeypatch.setattr(F.SM, "mech_labels", lambda *a: None)
    monkeypatch.setattr(F.SM, "state_flags", lambda a, b: {})
    monkeypatch.setattr(F.SM, "q4_env", lambda: (None, set(), 0.0))
    monkeypatch.setattr(F.SM, "q4_trades", lambda *a, **k: ["T"])
    monkeypatch.setattr(F.SM, "q4_fetch_list", lambda trades: PLAN if trades == ["T"] else [])
    assert F.plan() == PLAN


def test_dry_run_fetches_nothing(no_network, monkeypatch, capsys):
    def busy(*a, **k):
        raise AssertionError("the dry run must not consult the writer guard")
    monkeypatch.setattr(F, "other_writers", busy)
    assert F.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "to fetch: 1" in out and "632.00P" in out and "[dry-run] nothing fetched" in out


def test_refuses_beside_another_writer(no_network, monkeypatch, capsys):
    monkeypatch.setattr(F, "other_writers", lambda: [("1", "fetch")])
    assert F.main([]) == F.EXIT_OTHER_WRITER
    assert "REFUSED" in capsys.readouterr().err


def test_network_outage_exits_6_and_records_nothing(monkeypatch):
    monkeypatch.setattr(F, "other_writers", lambda: [])
    monkeypatch.setattr(F, "plan", lambda: list(PLAN))

    async def outage(*a, **k):
        raise history.NetworkOutage(1, 1)
    monkeypatch.setattr(history, "fetch_option_histories", outage)
    assert F.main([]) == history.EXIT_NETWORK_OUTAGE


_CSV = ('Time,Open,High,Low,Latest,Change,%Change,Volume,"Open Int",IV,Delta,Gamma,'
        "Theta,Vega,Rho,Theo,Price~,Bid,Ask\n"
        "2026-03-02,4.50,4.60,4.40,4.50,0.05,1.00%,10,100,"
        "0.30,-0.40,0.01,-0.02,0.05,0.01,4.50,100.00,4.45,4.55\n")


clock = [1_000_000.0]


def _session(outcomes):
    """{strike: outcome}; OK returns one row, anything else returns nothing."""
    class _S:
        def __init__(self, *a, **k):
            self.last_history_outcome = None
            self.last_history_logged_in = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def fetch_history_csv(self, url, timeout_ms):
            clock[0] += 150.0       # the unlisted proof needs time between live fetches
            strike = float(url.split("%7C")[-1].split("/")[0][:-1])
            self.last_history_outcome = outcomes[strike]
            return _CSV if outcomes[strike] == bs.HISTORY_OK else None
    return _S


def _put(strike):
    return dict(PLAN[0], strike=float(strike))


@pytest.mark.parametrize("outcome,recorded", [(bs.HISTORY_PAGE_404, True),
                                              (bs.HISTORY_NAV_ERROR, False),
                                              (bs.HISTORY_HTTP_ERROR, False)])
def test_a_404_is_skip_listed_and_a_network_error_or_refusal_is_not(
        tmp_path, monkeypatch, outcome, recorded):
    monkeypatch.setattr(history, "HISTORY_CACHE", tmp_path)
    monkeypatch.setattr(history, "FETCH_PAUSE_S", 0)
    monkeypatch.setattr(unlisted, "_now", lambda: clock[0])
    monkeypatch.delenv(unlisted.RETRY_ENV, raising=False)
    monkeypatch.setenv("BARCHART_EMAIL", "x@example.com")
    monkeypatch.setenv("BARCHART_PASSWORD", "pw")
    monkeypatch.setattr(history, "BarchartSession",
                        _session({630.0: bs.HISTORY_OK, 632.0: outcome, 634.0: bs.HISTORY_OK}))
    try:
        F.asyncio.run(F.fetch([_put(630), _put(632), _put(634)], True, 1000))
    except history.NetworkOutage:
        pass
    held = unlisted.load(tmp_path / unlisted.FILENAME)
    assert bool(held) is recorded
