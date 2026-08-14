"""Tests for `calendar_hedge`'s ARM H sizing floor.

`_typed()` converts a stored calendar candidate row into a report row and
computes `hedge_contracts` under ARM H's pre-registered half-size convention
(`HEDGE_SIZE = 0.5`, "<= 1/2 a position", `config/deployment-rules.md` §4).

Fixed 2026-08-14 (recorded follow-up from 2026-08-13): at `contracts == 1`,
`int(HEDGE_SIZE * 1) == 0` used to be floored back UP to 1 — a FULL-size
hedge where the arm specifies half. The floor now SKIPS the position instead
(`hedge_contracts` / `H_dol` are `None`).

This is a SIZING fact ONLY. An earlier version of this fix also filtered
`calendar_hedge.py`'s `keep` (the candidate universe) on `hedge_contracts`,
which silently moved H0 — a RECORDED gate (75.6% deployed / 66.7%
worst-decile, MET) — from MET to NOT MET, because "fillable but unsizable"
got conflated with "unfillable". That was wrong and has been reverted: `keep`
/ `strict` / H0's fill gate are computed exactly as before the floor change,
an unsizable candidate can still be picked by the day's rule, and it
contributes $0 wherever ARM H sums or correlates dollars (same treatment as
"no pick that day"), disclosed in the census rather than excluded from it.

The whole ARM H programme is power-stopped on this book (next-steps.md
§2.3), so none of this changes any conclusion — only the sizing floor's own
behaviour and what the census discloses about it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from scripts.backtest_study.calendar_hedge import (  # noqa: E402
    HEDGE_SIZE, apply_pick, h0_fill, h2_contribution, h3_sizing, _typed,
)


def _row(contracts, entry_net=1.0, pnl_pct=0.10):
    return {"entry_net": str(entry_net), "contracts": str(contracts),
            "pnl_pct": str(pnl_pct), "fillable_strict": "True"}


def _pick(date, ticker, hedge_contracts, h_dol, r=0.05):
    return {"date": date, "ticker": ticker, "expiry": "2025-02-01",
            "exit_reason": "x", "R": r, "E": 0.02,
            "hedge_contracts": hedge_contracts, "H_dol": h_dol}


# ── `_typed`: the floor itself ───────────────────────────────────────────────

def test_half_size_convention_is_still_one_half():
    # The remaining assertions assume this; a change here is a threshold
    # change and out of scope for the sizing-floor fix alone.
    assert HEDGE_SIZE == 0.5


def test_half_size_floor_skips_at_one_contract_instead_of_rounding_up():
    out = _typed(_row(contracts=1))
    assert out["hedge_contracts"] is None
    assert out["H_dol"] is None


def test_half_size_floor_sizes_normally_at_two_contracts():
    out = _typed(_row(contracts=2, entry_net=1.0, pnl_pct=0.10))
    assert out["hedge_contracts"] == 1
    assert out["H_dol"] == pytest.approx(0.10 * 1.0 * 100 * 1)


def test_half_size_floor_sizes_normally_at_four_contracts():
    out = _typed(_row(contracts=4))
    assert out["hedge_contracts"] == 2


def test_half_size_floor_skips_at_zero_contracts_too():
    # contracts == 0 is not a real candidate, but the floor must not error
    # or silently produce a truthy hedge size for it.
    out = _typed(_row(contracts=0))
    assert out["hedge_contracts"] is None
    assert out["H_dol"] is None


# ── regression: the floor must not move the candidate universe / H0 ─────────

def test_unsizable_candidate_is_still_pickable_and_counts_toward_h0(capsys):
    """A `contracts == 1` candidate is unsizable (`hedge_contracts` None) but
    remains STRICT-fillable, so `apply_pick` still picks it for its date and
    `h0_fill` still counts that date as filled — the floor is sizing-only."""
    unsizable = _typed(_row(contracts=1))
    unsizable["date"], unsizable["ticker"] = "2025-01-06", "AAA"
    fillable_by_date = {"2025-01-06": [unsizable]}
    picks = apply_pick(fillable_by_date, rule=lambda r: (0, r["ticker"]))
    capsys.readouterr()

    assert "2025-01-06" in picks, "an unsizable candidate must still be picked"
    assert picks["2025-01-06"]["hedge_contracts"] is None

    met = h0_fill(fillable_by_date, dep_dates=["2025-01-06"],
                   worst_dates=["2025-01-06"], picks=picks)
    capsys.readouterr()
    assert met is True, "H0 must count a fillable-but-unsizable pick as filled"


def test_h0_fill_counts_are_identical_whether_or_not_the_floor_fires(capsys):
    """H0's fill fraction depends only on which dates got a pick, never on
    `hedge_contracts`/`H_dol` — pin that by comparing a run where the floor
    fires (unsizable) against an otherwise-identical run where it doesn't."""
    dep_dates = ["2025-01-06", "2025-01-07", "2025-01-08"]
    worst_dates = ["2025-01-06"]

    def _run(hedge_contracts, h_dol):
        fillable_by_date = {
            "2025-01-06": [_pick("2025-01-06", "AAA", hedge_contracts, h_dol)],
            "2025-01-07": [_pick("2025-01-07", "BBB", 1, 50.0)],
            "2025-01-08": [],
        }
        picks = apply_pick(fillable_by_date, rule=lambda r: (0, r["ticker"]))
        met = h0_fill(fillable_by_date, dep_dates, worst_dates, picks)
        capsys.readouterr()
        return met

    met_unsizable = _run(None, None)     # floor fires
    met_sizable = _run(1, 25.0)          # floor does not fire

    assert met_unsizable == met_sizable is True


# ── downstream $ consumers must coalesce None -> $0, not raise ──────────────

def test_h2_contribution_does_not_raise_on_an_unsizable_pick(capsys):
    dep_dates = ["2025-01-06", "2025-01-07", "2025-01-08"]
    worst_dates = ["2025-01-06"]
    dep = {"2025-01-06": {"dollars": -300.0, "mean_R": -0.3},
           "2025-01-07": {"dollars": -100.0, "mean_R": -0.1},
           "2025-01-08": {"dollars": -200.0, "mean_R": -0.2}}
    picks = {"2025-01-06": _pick("2025-01-06", "AAA", None, None),
             "2025-01-07": _pick("2025-01-07", "BBB", 1, 50.0, r=0.10)}
    res = h2_contribution([], picks, dep, dep_dates, worst_dates)
    capsys.readouterr()
    assert res["verdict"] in ("MET", "NOT MET", "NOT EVALUABLE")


def test_h2_contribution_coalesces_none_h_dol_the_same_as_an_explicit_zero(capsys):
    dep_dates = ["2025-01-06", "2025-01-07", "2025-01-08"]
    worst_dates = ["2025-01-06"]
    dep = {"2025-01-06": {"dollars": -300.0, "mean_R": -0.3},
           "2025-01-07": {"dollars": -100.0, "mean_R": -0.1},
           "2025-01-08": {"dollars": -200.0, "mean_R": -0.2}}

    def _picks(hdol):
        return {"2025-01-06": _pick("2025-01-06", "AAA",
                                     None if hdol is None else 1, hdol),
                "2025-01-07": _pick("2025-01-07", "BBB", 1, 50.0, r=0.10)}

    res_none = h2_contribution([], _picks(None), dep, dep_dates, worst_dates)
    capsys.readouterr()
    res_zero = h2_contribution([], _picks(0.0), dep, dep_dates, worst_dates)
    capsys.readouterr()
    assert res_none == res_zero


def test_h3_sizing_does_not_raise_on_an_unsizable_pick(capsys):
    dep_dates = ["2025-01-06", "2025-01-07"]
    dep = {"2025-01-06": {"dollars": -300.0}, "2025-01-07": {"dollars": -100.0}}
    picks = {"2025-01-06": _pick("2025-01-06", "AAA", None, None)}
    h3_sizing(picks, dep, dep_dates, book=[])
    capsys.readouterr()  # must not raise
