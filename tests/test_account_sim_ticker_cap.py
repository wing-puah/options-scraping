"""Tests for `account_sim --ticker-cap`, the per-ticker cap CONFORMANCE arm.

Operator ruling 2026-10-06: production caps a TICKER's signed total
delta-notional at `caps.per_position x equity`; `account_sim.admission()` used
to check each new position alone. These tests pin three things:

  * stacking same-ticker positions past the cap is refused (`ticker_delta`),
    and the walk refills the slot from further down the day's list,
  * the sum is SIGNED — a long and a short on one ticker net,
  * the research rule and production's `s03_risk.assess` ticker-total rule
    agree on a shared synthetic book. This TEST imports both; the research
    module itself never imports `scripts/journal/`.
"""
import itertools
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from scripts.backtest_study import run as study_runner  # noqa: E402
from scripts.backtest_study.f4_deployment import account_sim  # noqa: E402
from scripts.backtest_study.f4_deployment.account_sim import (  # noqa: E402
    Cfg, admission, positions_artifact, simulate, sleeve_artifact,
    solve_contracts,
)
from scripts.backtest_study.lib.harness import Trade  # noqa: E402
from scripts.journal.config import DELTA_SOURCE_IBKR, PositionRisk  # noqa: E402
from scripts.journal.s03_risk import Caps, assess, headroom_for  # noqa: E402

CAPITAL = 25_000.0
CAP_DOLLARS = 0.25 * CAPITAL          # $6,250


def _cfg(**kw):
    base = dict(label="t", capital=CAPITAL, per_pos_cap=0.25, net_cap=1.50,
                risk_pct=0.02, max_per_day=3)
    base.update(kw)
    return Cfg(**base)


def _rec(signal: date, ticker: str, delta: float, underlying=100.0,
         mlpc=500.0, dte=30):
    """One contract at the $500 budget; dn = delta x 100 x underlying."""
    exp = signal + timedelta(days=dte)
    d, n = signal + timedelta(days=1), 0
    while d <= exp:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    row = {"signal_date": signal.isoformat(), "ticker": ticker,
           "structure": "long_call", "contracts": "1", "dte_entry": str(dte),
           "entry_option_price": "2.0", "entry_underlying": str(underlying),
           "legs": f"{ticker}:{exp.isoformat()}:100:C +1",
           "daily_price_csv": ",".join(["2.0"] * n)}
    return {"t": Trade(row), "credit": False, "structure": "long_call",
            "mech_cell": "PROD", "max_loss_per_contract": mlpc,
            "delta": delta, "date": signal.isoformat(), "ticker": ticker}


def _hold_to_end(rec, contracts, stop, cache=None):
    """A replayer that holds every position for its whole grid at zero P&L,
    so occupancy (not the exit model) is the only thing under test."""
    return dict(exit_reason="expiry", days_held=len(rec["t"].grid), R=0.0,
                dollars=0.0, stop_exact=True)


D1, D2 = date(2025, 1, 6), date(2025, 1, 7)


# ── stacking ────────────────────────────────────────────────────────────────

def _stack_day_lists():
    # $5,000 of delta-notional each: under the $6,250 cap alone, $10,000 stacked.
    return [(D1.isoformat(), [_rec(D1, "NVDA", 0.50)]),
            (D2.isoformat(), [_rec(D2, "NVDA", 0.50), _rec(D2, "AMD", 0.10)])]


def test_without_the_ticker_cap_same_ticker_positions_stack():
    sim = simulate(_stack_day_lists(), _cfg(), replayer=_hold_to_end)
    assert [p.rec["ticker"] for p in sim.signal_pos] == ["NVDA", "NVDA", "AMD"]
    assert sim.census["ticker_delta"] == 0 and not sim.ticker_refusals


def test_ticker_cap_refuses_the_stack_and_refills_the_slot():
    sim = simulate(_stack_day_lists(), _cfg(ticker_cap=True),
                   replayer=_hold_to_end)
    assert [p.rec["ticker"] for p in sim.signal_pos] == ["NVDA", "AMD"]
    assert sim.census["ticker_delta"] == 1
    assert [(r["ticker"], refilled) for r, refilled in sim.ticker_refusals] == [
        ("NVDA", True)]
    # The refusal sits in the A4 partition only when the arm is on.
    assert "ticker_delta" in account_sim.census_exclusions(sim.cfg)
    assert "ticker_delta" not in account_sim.census_exclusions(_cfg())
    assert "ticker_delta" not in account_sim.CENSUS_BUCKETS


def test_ticker_cap_frees_once_the_first_position_exits():
    # Day 1's NVDA exits after one session; a later NVDA is then admitted.
    later = date(2025, 1, 13)
    day_lists = [(D1.isoformat(), [_rec(D1, "NVDA", 0.50)]),
                 (later.isoformat(), [_rec(later, "NVDA", 0.50)])]

    def one_day(rec, contracts, stop, cache=None):
        return dict(exit_reason="x", days_held=1, R=0.0, dollars=0.0,
                    stop_exact=True)

    sim = simulate(day_lists, _cfg(ticker_cap=True), replayer=one_day)
    assert len(sim.signal_pos) == 2 and sim.census["ticker_delta"] == 0


def test_arm_d_downsizes_to_fit_the_ticker_total():
    # Open NVDA $5,000; a 2-contract NVDA candidate at $2,500/contract stacks
    # to $10,000 at full size and $7,500 at one — still over $6,250, so
    # nothing fits; at $1,000/contract one contract fits ($6,000).
    open_dn = 5_000.0
    assert solve_contracts(2, 250.0, 2_500.0, 1e9, open_dn, _cfg(),
                           ticker_open=open_dn) == 0
    assert solve_contracts(2, 250.0, 1_000.0, 1e9, open_dn, _cfg(),
                           ticker_open=open_dn) == 1
    # Without a ticker total the standalone rule takes both.
    assert solve_contracts(2, 250.0, 1_000.0, 1e9, open_dn, _cfg()) == 2


# ── sign handling ───────────────────────────────────────────────────────────

def test_admission_attributes_stack_vs_standalone_breaches():
    cfg = _cfg()
    # under the cap alone, over it stacked -> the new bucket
    assert admission(0.0, 5_000.0, 1e9, 0.0, cfg, ticker_open=5_000.0) == (
        False, "ticker_delta")
    # over the cap alone and stacked -> the existing bucket
    assert admission(0.0, 7_000.0, 1e9, 0.0, cfg, ticker_open=1_000.0) == (
        False, "per_pos_delta")
    # no ticker total -> exactly the old rule
    assert admission(0.0, 5_000.0, 1e9, 0.0, cfg) == (True, None)


def test_a_long_and_a_short_on_one_ticker_net():
    cfg = _cfg()
    # a short against an open long nets toward zero
    assert admission(0.0, -5_000.0, 1e9, 0.0, cfg, ticker_open=5_000.0) == (
        True, None)
    # a short OVER the cap alone is admitted when the open long nets it under
    assert admission(0.0, -8_000.0, 1e9, 0.0, cfg, ticker_open=5_000.0) == (
        True, None)
    # ... and the netting does not reach across tickers
    assert admission(0.0, -8_000.0, 1e9, 0.0, cfg, ticker_open=0.0) == (
        False, "per_pos_delta")
    # two shorts stack like two longs
    assert admission(0.0, -4_000.0, 1e9, 0.0, cfg, ticker_open=-4_000.0) == (
        False, "ticker_delta")


def test_simulate_nets_a_short_against_an_open_long():
    day_lists = [(D1.isoformat(), [_rec(D1, "NVDA", 0.50)]),
                 (D2.isoformat(), [_rec(D2, "NVDA", -0.80)])]
    on = simulate(day_lists, _cfg(ticker_cap=True), replayer=_hold_to_end)
    off = simulate(day_lists, _cfg(), replayer=_hold_to_end)
    assert len(on.signal_pos) == 2 and on.census["ticker_netted_in"] == 1
    assert len(off.signal_pos) == 1 and off.census["per_pos_delta"] == 1


# ── research rule == production's ticker-total rule ─────────────────────────

def _prod_position(i: int, ticker: str, dn: float) -> PositionRisk:
    return PositionRisk(conid_key=str(i), ticker=ticker, structure="s",
                        contracts=1, delta_notional=dn,
                        delta_source=DELTA_SOURCE_IBKR)


BOOK = [("NVDA", 4_000.0), ("NVDA", 1_500.0), ("AMZN", -3_000.0),
        ("GLD", 6_000.0), ("TLT", -2_000.0), ("TLT", 2_500.0)]
CANDIDATES = [-9_000.0, -7_000.0, -4_000.0, -1_000.0, 0.0, 500.0, 750.0,
              2_000.0, 6_250.0, 7_000.0, 12_000.0]


@pytest.mark.parametrize("ticker,cand", list(itertools.product(
    ["NVDA", "AMZN", "GLD", "TLT", "MSFT"], CANDIDATES)))
def test_research_ticker_rule_agrees_with_s03_risk(ticker, cand):
    """Same book, same candidate: research admits iff production's `assess`
    flags no breach for that ticker after adding it (and `headroom_for`, its
    admission form, agrees). The net cap is set out of reach on both sides so
    only the per-position/ticker rule is compared."""
    open_dn = sum(dn for t, dn in BOOK if t == ticker)
    research_ok, why = admission(0.0, cand, 1e12, 0.0,
                                 _cfg(net_cap=1e9, enforce_cash=False),
                                 ticker_open=open_dn)

    caps = Caps(per_position=0.25, net=1e9, net_liq=CAPITAL)
    book = [_prod_position(i, t, dn) for i, (t, dn) in enumerate(BOOK)]
    after = assess(book + [_prod_position(99, ticker, cand)], caps)
    prod_ok = not any(b.startswith(f"{ticker}:") for b in after.breaches)
    head_ok, _ = headroom_for(assess(book, caps), cand, ticker=ticker)

    assert research_ok == prod_ok == head_ok, (ticker, cand, why, after.breaches)


def test_research_module_never_imports_the_journal():
    src = Path(account_sim.__file__).read_text()
    assert "from scripts.journal" not in src and "import scripts.journal" not in src


# ── artifacts ───────────────────────────────────────────────────────────────

def test_ticker_cap_writes_its_own_csv_stems():
    stem, arm = positions_artifact(compounding=False, structure_universe=False,
                                   ticker_cap=True)
    assert stem == "account_sim-positions-ticker-cap-latest.csv"
    assert arm == "RF1-ticker-cap"
    assert sleeve_artifact(compounding=False, structure_universe=False,
                           ticker_cap=True) == "account_sim-sleeve-ticker-cap-latest.csv"
    # the default stems are untouched
    assert positions_artifact(compounding=False, structure_universe=False) == (
        "account_sim-positions-latest.csv", "RF1")


@pytest.mark.parametrize("argv,want", [([], False), (["--ticker-cap"], True)])
def test_main_forwards_the_ticker_cap_flag(monkeypatch, capsys, argv, want):
    seen = {}

    def _fake(path, *, compound_enabled=False, ticker_cap_enabled=False):
        seen["ticker_cap_enabled"] = ticker_cap_enabled
        raise account_sim.ConfigError("stopped before the book is loaded")

    monkeypatch.setattr(account_sim, "load_settings", _fake)
    assert account_sim.main(argv) == 2
    assert seen["ticker_cap_enabled"] is want


def test_runner_files_ticker_cap_under_its_own_report_stem():
    plan = study_runner.arm_plan("account_sim", ["--ticker-cap"])
    assert [(stem, charts) for stem, _a, charts in plan] == [
        ("account_sim-ticker-cap", ())]
