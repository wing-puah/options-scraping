"""Backtest-engine robustness fixes (research/robustness-review.md §Backtest).

Everything here runs on SYNTHETIC price grids — no network, no option-history
cache — so each claim is pinned by construction rather than by a book snapshot:

  B2  a grid day BEFORE the fill is present but UNPRICED (`pre_entry`), so the
      grid keeps its signal-relative origin and length while no P&L, excursion
      or exit can be booked before the position existed
  B1  a transaction-cost model that is exactly zero until it is configured
  B3  a mark carried forward past the bound is tagged `barchart_stale`, and
      `pct_real_days` counts LEG-days
  B5  a zero-bid contract is marked at ask/2, or 0 when nothing is offered
"""
from datetime import date, timedelta

import pytest

import backtest as bt
from backtest import helpers as bt_helpers
from backtest import simulate as sim

SIGNAL = date(2026, 6, 1)          # Monday
EXP = date(2026, 7, 17)
KEY = ("NVDA", "Call", 250.0, "2026-07-17")
SHORT_KEY = ("NVDA", "Call", 270.0, "2026-07-17")


def _cand(**kw):
    return {"ticker": "NVDA", "signal_date": SIGNAL, "play": "long call",
            "market_regime": "", **kw}


def _legs(*specs):
    return [bt.Leg(int(q), t, date.fromisoformat(e), float(k), ot)
            for (q, t, e, k, ot) in specs]


def _entry_row(entry_date, mark=10.0, price=250.0):
    """The synthetic entry row `_entry_row_from_history` would build."""
    return {"Strike": 250.0, "DTE": (EXP - entry_date).days, "IV": "45",
            "Price~": str(price), "Trade": mark, "Expires": EXP.isoformat(),
            "Delta": "0.50", "_entry_date": entry_date}


def _row(mark, bid=None, ask=None, open_=""):
    row = {"Open": open_, "_mark": mark}
    if bid is not None:
        row["Bid"] = str(bid)
    if ask is not None:
        row["Ask"] = str(ask)
    return row


def _cfg(**kw):
    base = {"profit_target": 0.5, "stop_loss": 1.0, "contracts": 1,
            "entry_sources": ["barchart"], "exit_sources": ["barchart"]}
    base.update(kw)
    return base


def _weekdays(start, end):
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _run(legs, series, details, cfg, entry_date=date(2026, 6, 4), structure="long_call"):
    return sim._simulate(_cand(), legs, _entry_row(entry_date), {}, series, cfg,
                         structure=structure, price_fn=lambda tk, dt: None,
                         barchart_details=details)


# ── B2 — no P&L before the fill, with the grid origin left alone ───────────────


def _late_fill_case(cfg=None):
    """Signal Mon 06-01; the contract does not print again until Thu 06-04, so the
    fill lands 3 days after the signal. The 06-01 mark is DOUBLE the entry price:
    before the fix, 06-02 and 06-03 carried it forward and scored +100% against an
    entry struck on 06-04 — a profit-target exit on a day the position did not
    exist.
    """
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    series = {KEY: [(SIGNAL, 20.0), (date(2026, 6, 4), 10.0),
                    (date(2026, 6, 5), 12.0), (date(2026, 6, 8), 16.0)]}
    details = {KEY: {SIGNAL: _row(20.0), date(2026, 6, 4): _row(10.0),
                     date(2026, 6, 5): _row(12.0), date(2026, 6, 8): _row(16.0)}}
    return _run(legs, series, details, cfg or _cfg(path_cap_days=7))


def test_b2_pre_entry_days_are_present_but_unpriced():
    res = _late_fill_case()

    # The grid is still every weekday AFTER the signal through the cap —
    # 06-02, 06-03, 06-04, 06-05, 06-08 — so its ORIGIN and LENGTH are exactly
    # what they were. The two days before the fill carry a blank mark instead of
    # a carried-forward one.
    days = _weekdays(date(2026, 6, 2), SIGNAL + timedelta(days=7))
    marks = res["daily_price_csv"].split(",")
    assert len(marks) == len(days) == 5
    assert marks == ["", "", "10.0000", "12.0000", "16.0000"]
    assert res["daily_pnl_csv"].split(",") == ["", "", "0.00", "200.00", "600.00"]
    # …and the row SAYS why they are blank, rather than looking unpriceable.
    assert res["daily_source_csv"].split(",") == [
        "pre_entry", "pre_entry", "barchart", "barchart", "barchart"]


def test_b2_excursions_and_exit_are_measured_from_the_fill_onward():
    res = _late_fill_case()

    # The pre-entry +100% never existed: MFE is the real +60% on 06-08.
    assert res["mfe_pct"] == 0.6 and res["mfe_day"] == 5
    assert res["mae_pct"] == 0.0 and res["mae_day"] == 3
    assert res["exit_reason"] == "profit_target"
    assert res["realized_pnl_pct"] == 0.6
    # Day indices stay SIGNAL-relative: 06-08 is grid day 5, and the first PRICED
    # day is the fill on 06-04 (grid day 3).
    assert res["days_held"] == 5
    assert res["daily_price_csv"].split(",")[res["days_held"] - 1] == "16.0000"


def test_b2_pre_entry_days_are_not_carried_marks_and_leave_the_denominators():
    """B3's carry-forward must not reach backwards past the fill, and the
    data-quality columns are computed over PRICED days only — 3 of them here, not
    the grid's 5. Pre-entry days leave the denominator; they are not path days."""
    res = _late_fill_case()

    assert "barchart_stale" not in res["daily_source_csv"]
    assert res["pct_real_days"] == 1.0          # 3 real leg-days / 3, never 3/5
    assert res["pct_stale_days"] == 0.0


def test_b2_same_day_fill_grid_is_unchanged():
    """The common case — the fill is the first weekday after the signal — must
    produce exactly the grid it always did, with no pre_entry token."""
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    series = {KEY: [(SIGNAL, 8.0), (date(2026, 6, 2), 10.0), (date(2026, 6, 3), 11.0)]}
    details = {KEY: {date(2026, 6, 2): _row(10.0), date(2026, 6, 3): _row(11.0)}}
    res = _run(legs, series, details, _cfg(path_cap_days=2),
               entry_date=date(2026, 6, 2))

    assert res["daily_price_csv"].split(",") == ["10.0000", "11.0000"]
    assert "pre_entry" not in res["daily_source_csv"]


def test_b2_entry_row_carries_the_grid_origin():
    """`_entry_row_from_history` is where `_entry_date` comes from; a fill 3 days
    after the signal must be reported as such."""
    details = {KEY: {SIGNAL: _row(20.0), date(2026, 6, 4): _row(10.0)}}
    row = bt._entry_row_from_history(details, KEY, SIGNAL, 250.0, EXP, timing="next_open")
    assert row["_entry_date"] == date(2026, 6, 4)
    assert row["DTE"] == (EXP - date(2026, 6, 4)).days


def test_b2_frozen_harness_mark_count_invariant_holds_for_a_late_fill():
    """`scripts/backtest_study/lib/harness.py` (FROZEN) rebuilds the grid from the
    SIGNAL date and asserts `len(marks) == len(grid)`. This is the case that broke
    when the origin moved to the fill: signal 2026-06-01, fill 2026-06-04, nearest
    DTE 46 → 34 grid days, but only 32 priced ones. Keeping the pre-entry days as
    blank tokens is what keeps 34 == 34.

    The row is fed to `harness.Trade` verbatim — `_simulate`'s own output dict is
    already the export row shape — so this is the real assert, not a restatement.
    """
    from scripts.backtest_study.lib import harness

    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    series = {KEY: [(SIGNAL, 20.0), (date(2026, 6, 4), 10.0)]}
    details = {KEY: {SIGNAL: _row(20.0), date(2026, 6, 4): _row(10.0)}}
    # No path_cap_days override: the full 46-day path, the same 120-day cap
    # `harness.PATH_CAP_DAYS` uses.
    res = _run(legs, series, details,
               _cfg(profit_target=None, stop_loss=None))

    grid = bt_helpers._weekday_grid(SIGNAL, SIGNAL + timedelta(days=(EXP - SIGNAL).days))
    marks = res["daily_price_csv"].split(",")
    assert len(grid) == 34
    assert len(marks) == 34
    assert marks[:2] == ["", ""]          # 06-02, 06-03 — before the fill
    assert marks[2] == "10.0000"          # 06-04 — the fill

    t = harness.Trade(res)                # the frozen assert runs in here
    assert len(t.marks) == len(t.grid) == 34
    assert t.marks[:2] == [None, None]


def test_b2_mtm_curve_index_zero_is_still_the_first_session_after_the_signal():
    """`backtest_study/lib/mtm_curve.py` and `f4_deployment/concurrency_correlation.py`
    both read `daily_pnl_csv` index 0 as the first session after the SIGNAL date.
    A late fill must not shift that — index 0 stays 06-02, blank."""
    res = _late_fill_case()
    grid = bt_helpers._weekday_grid(SIGNAL, SIGNAL + timedelta(days=7))

    tokens = res["daily_pnl_csv"].split(",")
    assert len(tokens) == len(grid)
    assert grid[0] == date(2026, 6, 2)
    assert tokens[0] == ""                # the position does not exist yet
    assert grid[tokens.index("0.00")] == date(2026, 6, 4)   # the fill


# ── B1 — transaction costs ─────────────────────────────────────────────────────

def _spread_case(cfg):
    """A 1-lot 250/270 debit vertical. Entry 06-02 at 10.0 − 3.0 = 7.0 net; on
    06-03 it marks 14.0 − 3.5 = 10.5, i.e. +50% gross → profit target.
    Quoted spreads: 0.20 on the long leg, 0.10 on the short, both days."""
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"),
                 ("-1", "NVDA", "2026-07-17", 270, "Call"))
    series = {KEY: [(date(2026, 6, 2), 10.0), (date(2026, 6, 3), 14.0)],
              SHORT_KEY: [(date(2026, 6, 2), 3.0), (date(2026, 6, 3), 3.5)]}
    details = {
        KEY: {date(2026, 6, 2): _row(10.0, bid=9.9, ask=10.1),
              date(2026, 6, 3): _row(14.0, bid=13.9, ask=14.1)},
        SHORT_KEY: {date(2026, 6, 2): _row(3.0, bid=2.95, ask=3.05),
                    date(2026, 6, 3): _row(3.5, bid=3.45, ask=3.55)},
    }
    return _run(legs, series, details, cfg, entry_date=date(2026, 6, 2),
                structure="bull_call_spread")


def test_b1_zero_cost_reproduces_the_old_pnl_exactly():
    unconfigured = _spread_case(_cfg(path_cap_days=2))
    explicit_zero = _spread_case(_cfg(path_cap_days=2, commission_per_contract=0.0,
                                      slippage_frac_of_spread=0.0))

    assert unconfigured["realized_pnl_pct"] == 0.5
    assert unconfigured["realized_pnl_abs"] == 350.0        # 0.5 × 7.0 × 100 × 1
    assert unconfigured["cost_total"] == 0.0
    assert unconfigured["cost_basis"] == ""
    assert explicit_zero == unconfigured


def test_b1_costs_lower_realized_pnl_by_exactly_the_charged_amount():
    res = _spread_case(_cfg(path_cap_days=2, commission_per_contract=0.65,
                            slippage_frac_of_spread=0.25))

    # commission: $0.65 × 2 legs × 1 contract × 2 sides
    commission = 0.65 * 2 * 1 * 2
    # slippage: 25% of each leg's quoted spread, per side, × 100 × 1 contract
    entry_slip = 0.25 * (0.20 + 0.10) * 100
    exit_slip = 0.25 * (0.20 + 0.10) * 100
    expected = commission + entry_slip + exit_slip           # 2.60 + 7.50 + 7.50

    assert res["cost_total"] == pytest.approx(expected)
    assert res["cost_basis"] == "full"
    assert res["realized_pnl_abs"] == pytest.approx(350.0 - expected)
    assert res["realized_pnl_pct"] == pytest.approx(round(0.5 - expected / 700.0, 4))
    # pnl_on_risk_pct is derived from the NET dollar figure.
    assert res["pnl_on_risk_pct"] == pytest.approx((350.0 - expected) / 700.0, abs=1e-4)
    # Path statistics stay GROSS — they tune exits, not costs.
    assert res["mfe_pct"] == 0.5


def test_b1_commission_is_charged_per_leg_per_contract_on_both_sides():
    res = _spread_case(_cfg(path_cap_days=2, commission_per_contract=1.0,
                            slippage_frac_of_spread=0.0))
    assert res["cost_total"] == pytest.approx(4.0)          # 2 legs × 1 lot × 2 sides
    assert res["cost_basis"] == "commission_only"


def test_b1_no_quote_means_no_slippage_and_the_row_says_so():
    """No details map at all → no bid/ask on either side. Slippage falls back to
    zero rather than guessing a spread, and `cost_basis` names both sides."""
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    series = {KEY: [(SIGNAL, 10.0), (date(2026, 6, 2), 10.0), (date(2026, 6, 3), 15.0)]}
    res = sim._simulate(
        _cand(), legs, _entry_row(SIGNAL), {}, series,
        _cfg(path_cap_days=2, commission_per_contract=0.65,
             slippage_frac_of_spread=0.25),
        structure="long_call", price_fn=lambda tk, dt: None)

    assert res["exit_reason"] == "profit_target"
    assert res["cost_basis"] == "no_spread_entry_exit"
    assert res["cost_total"] == pytest.approx(1.30)         # commission only
    assert res["realized_pnl_abs"] == pytest.approx(0.5 * 10 * 100 - 1.30)


# ── B3 — a contract that stops being quoted ────────────────────────────────────

def _vanishing_quotes_case(cfg_extra=None):
    """The contract prints 06-02 → 06-05 and then never again; the path runs to
    06-19. Every later day is the 06-05 mark carried forward."""
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    bars = [date(2026, 6, 2), date(2026, 6, 3), date(2026, 6, 4), date(2026, 6, 5)]
    series = {KEY: [(d, 10.0) for d in bars]}
    details = {KEY: {d: _row(10.0, bid=9.9, ask=10.1) for d in bars}}
    cfg = _cfg(path_cap_days=18, profit_target=None, stop_loss=None)
    cfg.update(cfg_extra or {})
    return _run(legs, series, details, cfg, entry_date=date(2026, 6, 2))


def test_b3_carried_marks_past_the_bound_are_tagged_stale():
    res = _vanishing_quotes_case()
    days = _weekdays(date(2026, 6, 2), date(2026, 6, 19))
    tags = res["daily_source_csv"].split(",")

    assert len(tags) == len(days) == 14
    for day, tag in zip(days, tags):
        stale = (day - date(2026, 6, 5)).days > 5
        assert tag == ("barchart_stale" if stale else "barchart"), day
    # 06-02…06-10 fresh, 06-11…06-19 carried too far.
    assert tags.count("barchart_stale") == 7
    assert res["pct_stale_days"] == 0.5
    # Still REAL data (a frozen quote, not a model), so pct_real_days holds at 1.0
    # — the staleness is what pct_stale_days and the tag are for.
    assert res["pct_real_days"] == 1.0
    assert res["exit_reason"] == "cap_open"


def test_b3_null_bound_carries_forever_the_pre_fix_behaviour():
    res = _vanishing_quotes_case({"max_price_carry_days": None})
    assert "barchart_stale" not in res["daily_source_csv"]
    assert res["pct_stale_days"] == 0.0


def test_b3_pct_real_days_counts_leg_days_not_days():
    """A vertical with ONE modelled leg used to score 1.00 — a day counted as real
    if ANY leg was. Leg-days make it 0.50."""
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"),
                 ("-1", "NVDA", "2026-07-17", 270, "Call"))
    series = {KEY: [(date(2026, 6, 2), 10.0), (date(2026, 6, 3), 11.0)]}
    details = {KEY: {date(2026, 6, 2): _row(10.0), date(2026, 6, 3): _row(11.0)}}
    cfg = _cfg(path_cap_days=2, entry_sources=["barchart", "bs"],
               exit_sources=["barchart", "bs"], profit_target=None, stop_loss=None)
    res = sim._simulate(_cand(), legs, _entry_row(date(2026, 6, 2)), {}, series, cfg,
                        structure="bull_call_spread",
                        price_fn=lambda tk, dt: 255.0, barchart_details=details)

    assert res["daily_source_csv"].split(",") == ["barchart+bs", "barchart+bs"]
    assert res["pct_real_days"] == 0.5


# ── B5 — a zero bid must not fall through to the last trade ────────────────────

@pytest.mark.parametrize("bid,ask,expected", [
    ("0.00", "0.00", 0.0),      # nothing bid, nothing offered → worth nothing
    ("0.00", "2.00", 1.0),      # the true mid of a 0×2.00 market
    ("0", "0.05", 0.025),
    ("1.90", "2.10", None),     # two-sided quote → the row's own mark stands
    (None, None, None),         # no quote columns at all (older cache files)
    ("0.00", None, None),       # a bid with no ask says nothing about value
])
def test_b5_zero_bid_mark_branches(bid, ask, expected):
    row = _row(3.0, bid=bid, ask=ask)
    assert sim._zero_bid_mark(row) == expected


def _zero_bid_path_case(bid, ask, latest):
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    series = {KEY: [(date(2026, 6, 2), 10.0), (date(2026, 6, 3), latest)]}
    details = {KEY: {date(2026, 6, 2): _row(10.0, bid=9.9, ask=10.1),
                     date(2026, 6, 3): _row(latest, bid=bid, ask=ask)}}
    return _run(legs, series, details, _cfg(path_cap_days=2, profit_target=None),
                entry_date=date(2026, 6, 2))


def test_b5_bidless_leg_with_no_offer_is_marked_at_zero():
    # Latest traded 8.00 days ago; the market is now 0 × 0.
    res = _zero_bid_path_case("0.00", "0.00", 8.0)
    assert res["daily_price_csv"].split(",") == ["10.0000", "0.0000"]
    assert res["realized_pnl_pct"] == -1.0
    assert res["exit_reason"] == "stop_loss"


def test_b5_bidless_leg_with_a_live_offer_is_marked_at_half_the_ask():
    res = _zero_bid_path_case("0.00", "2.00", 8.0)
    assert res["daily_price_csv"].split(",") == ["10.0000", "1.0000"]
    assert res["pnl_at_cap_pct"] == -0.9


# ── B1/B3 — the columns must REACH the export, not just the result dict ────────
#
# `write_results` writes with `DictWriter(..., extrasaction="ignore")` and
# `{k: r.get(k, "") for k in key_order}`, so a key `_simulate` emits but the key
# order does not name is DISCARDED IN SILENCE. With the cost knobs on that is the
# un-labelled-basis failure `exit_basis` exists for: NET realized columns on the
# tab with nothing on the row saying costs were charged.

_NEW_TAIL = ["pct_stale_days", "cost_total", "cost_basis"]


def test_new_columns_are_end_appended_to_both_key_orders():
    from scripts.backtest.core import _KEY_ORDER
    from scripts.backtest.proxy import _PROXY_KEY_ORDER

    for order in (_KEY_ORDER, _PROXY_KEY_ORDER):
        assert order[-3:] == _NEW_TAIL, order[-6:]
        # end-APPENDED: `exit_basis`, the previous tail, is still immediately
        # before them, so no existing column moved.
        assert order[-4] == "exit_basis"
        assert len(order) == len(set(order))


def test_cost_columns_survive_the_csv_writer(tmp_path):
    """The regression the reviewer caught: emitted-but-unlisted keys vanish."""
    from scripts.backtest.core import _KEY_ORDER
    from scripts.backtest.shared.results_io import write_results

    res = _late_fill_case(_cfg(path_cap_days=7, commission_per_contract=0.65,
                               slippage_frac_of_spread=0.0))
    assert res["cost_total"] == 1.30      # 1 leg × 1 contract × $0.65 × 2 sides
    assert res["cost_basis"] == "commission_only"

    out = tmp_path / "results.csv"
    write_results([res], key_order=_KEY_ORDER, local_csv=str(out))

    import csv as _csv
    with out.open(newline="", encoding="utf-8") as f:
        header = next(_csv.reader(f))
        row = next(_csv.DictReader(f, fieldnames=header))
    assert header[-3:] == _NEW_TAIL
    assert row["cost_total"] == "1.3"
    assert row["cost_basis"] == "commission_only"
    assert row["pct_stale_days"] == str(res["pct_stale_days"])
    # …and the realized column it qualifies is the NET one.
    assert float(row["realized_pnl_abs"]) == res["realized_pnl_abs"]


def test_gross_rows_say_so_with_an_empty_cost_basis(tmp_path):
    """Costs off ⇒ `cost_basis` blank and the realized columns unchanged, so a
    reader can segregate gross rows from charged ones on the row itself."""
    from scripts.backtest.core import _KEY_ORDER
    from scripts.backtest.shared.results_io import write_results

    gross = _late_fill_case()
    assert gross["cost_basis"] == "" and gross["cost_total"] == 0.0

    out = tmp_path / "results.csv"
    write_results([gross], key_order=_KEY_ORDER, local_csv=str(out))
    import csv as _csv
    with out.open(newline="", encoding="utf-8") as f:
        row = next(_csv.DictReader(f))
    assert row["cost_basis"] == ""
    assert float(row["realized_pnl_pct"]) == 0.6


def test_tab_header_alignment_plan_adds_exactly_the_three_columns():
    """`align_tab_headers.py` derives its target header from `_KEY_ORDER`, so the
    offline plan is what `--dry-run` would report against a live tab still on the
    old header. No Sheets call — `plan()` is pure."""
    import align_tab_headers as ath
    from scripts.backtest.core import _KEY_ORDER
    from scripts.backtest.proxy import _PROXY_KEY_ORDER

    for tab, order in (("BacktestResults", _KEY_ORDER),
                       ("BacktestProxy", _PROXY_KEY_ORDER)):
        target = ath.schema_for(tab)
        assert target == list(order)
        old_header = [c for c in target if c not in _NEW_TAIL]
        rows = [[f"{c}-v" for c in old_header]]
        relocations, blockers = ath.plan(old_header, rows, target)
        # Pure end-append: nothing to move, nothing orphaned.
        assert blockers == []
        assert relocations == {}
        assert [c for c in target if c not in old_header] == _NEW_TAIL
