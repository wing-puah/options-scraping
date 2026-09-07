"""Tests for `calendar_hedge`'s ARM H sizing floor.

`_typed()` converts a stored calendar candidate row into a report row and
computes `hedge_contracts` under ARM H's pre-registered half-size convention
(`HEDGE_SIZE = 0.5`, "<= 1/2 a position", `docs/deployment-rules.md` §4).

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

The whole ARM H programme is underpowered on this book (next-steps.md
§2.3), so none of this changes any conclusion — only the sizing floor's own
behaviour and what the census discloses about it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from scripts.backtest_study.f3_structure.calendar_hedge import (  # noqa: E402
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


# ════════════════════════════════════════════════════════════════════════════
# The three bodies calendar_hedge deleted on 2026-09-07, kept here as literals
# ════════════════════════════════════════════════════════════════════════════
# H2(c)'s year clause, H3's `_sweep` and `bear_sleeve_dollars`' 1-per-day pick
# were this study's own copies of `bear_deploy` D2/D3 until they were replaced
# by `lib/hedge_criteria.py` (research/hedge-programme-plan.md §"The shared
# criteria library"). The study reconciled BYTE-IDENTICAL on era v4, which
# pins the merge on the ONE population the export happens to hold. These tests
# pin it on synthetic series instead: the deleted body is copied verbatim
# below and asserted equal to the library's on inputs the export does not
# contain — a year that falls under the six-date minimum, a sweep no fraction
# clears, a tie between two picks on the same day.
#
# They are here rather than in tests/test_hedge_criteria.py because what they
# pin is CALENDAR_HEDGE's claim that its rule is D2's verbatim, not the
# library's own behaviour, which the committed fixture covers.

from scripts.backtest_study.lib import hedge_criteria as HC  # noqa: E402


def _old_year_clause(dep_dates, dep):
    """`h2_contribution`'s (c) loop as it stood before 2026-09-07."""
    out = []
    for y in sorted({d[:4] for d in dep_dates}):
        ys = [d for d in dep_dates if d[:4] == y]
        if len(ys) < 6:
            out.append((y, len(ys), False, []))
            continue
        order = sorted(ys, key=lambda d: dep[d]["dollars"])
        out.append((y, len(ys), True, order[:max(2, len(ys) // 4)]))
    return out


def _new_year_clause(dep_dates, dep):
    return [(yc.year, yc.n_dates, yc.evaluated, list(yc.tail_dates))
            for yc in HC.year_tails(dep_dates, key=lambda d: dep[d]["dollars"])]


def _synthetic_dep(spec):
    """`{date: {"dollars": ...}}` from `{year: [dollars, ...]}`."""
    dep = {}
    for year, vals in spec.items():
        for i, v in enumerate(vals):
            dep[f"{year}-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}"] = {"dollars": float(v)}
    return dep


@pytest.mark.parametrize("spec", [
    # a full year, a year one date under the minimum, and a year of exactly it
    {"2024": [-9, -8, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2],
     "2025": [-5, -4, -3, -2, 1],
     "2026": [-3, -2, -1, 0, 1, 2]},
    # ties in the ordering key: the tail must take the same dates in the same
    # order, which is `sorted`'s stability and not an accident
    {"2024": [0, 0, 0, 0, 0, 0, 0, 0]},
    # a single year, all positive: the "worst" quartile is still cut
    {"2025": [1, 2, 3, 4, 5, 6, 7]},
])
def test_the_year_clause_the_study_deleted_equals_the_library(spec):
    dep = _synthetic_dep(spec)
    dep_dates = sorted(dep)
    assert _new_year_clause(dep_dates, dep) == _old_year_clause(dep_dates, dep)


def _old_sweep(base_daily, sleeve, dates, fractions):
    """`_sweep`'s arithmetic and verdict as they stood before 2026-09-07."""
    out, base = [], None
    for f in fractions:
        daily = [base_daily.get(d, 0.0) + f * sleeve.get(d, 0.0) for d in dates]
        tot, mdd, worst = sum(daily), HC.max_drawdown(daily), min(daily)
        neg = sum(1 for v in daily if v < 0)
        if f == 0.0:
            base = (tot, mdd, worst)
        out.append(dict(f=f, total=tot, mdd=mdd, worst=worst, neg=neg))
    ok = [o for o in out if o["f"] > 0 and o["mdd"] >= base[1] - 1e-9
          and o["worst"] >= base[2] - 1e-9]
    best = max(ok, key=lambda o: o["f"]) if ok else None
    return out, base, best


def _new_sweep(base_daily, sleeve, dates, fractions):
    out, base, _ = HC.sweep({d: (0.0, base_daily.get(d, 0.0), 0) for d in dates},
                            {d: sleeve.get(d, 0.0) for d in dates},
                            fractions)
    return out, base, HC.sizing_verdict(out, base).best


@pytest.mark.parametrize("book,sleeve", [
    # the hedge helps at every size: the largest fraction wins
    ([-300.0, 200.0, -100.0, 50.0], [80.0, -10.0, 120.0, -5.0]),
    # the hedge harms the drawdown: NOT MET, no fallback to a smaller size
    ([-300.0, 200.0, -100.0, 50.0], [-80.0, -60.0, -40.0, -20.0]),
    # a sleeve on a day the book is flat still costs something
    ([0.0, 0.0, -500.0, 0.0], [-25.0, -25.0, 300.0, -25.0]),
])
def test_the_sweep_the_study_deleted_equals_the_library(book, sleeve):
    from scripts.backtest_study.f3_structure.calendar_hedge import SIZE_FRACTIONS

    dates = [f"2025-01-{i + 1:02d}" for i in range(len(book))]
    base_daily = dict(zip(dates, book))
    sleeve_d = dict(zip(dates, sleeve))

    old_out, old_base, old_best = _old_sweep(base_daily, sleeve_d, dates,
                                             SIZE_FRACTIONS)
    new_out, new_base, new_best = _new_sweep(base_daily, sleeve_d, dates,
                                             SIZE_FRACTIONS)

    assert [(r.f, r.total, r.mdd, r.worst, r.neg) for r in new_out] == \
           [(o["f"], o["total"], o["mdd"], o["worst"], o["neg"]) for o in old_out]
    assert (new_base.total, new_base.mdd, new_base.worst) == old_base
    assert (new_best is None) == (old_best is None)
    if old_best is not None:
        assert (new_best.f, new_best.total, new_best.mdd) == \
               (old_best["f"], old_best["total"], old_best["mdd"])


def _old_bear_pick(book, dates, bear_debit):
    """`bear_sleeve_dollars`' picking loop as it stood before 2026-09-07."""
    from collections import defaultdict

    by_day = defaultdict(list)
    for r in book:
        if r["structure"] in bear_debit and not r["credit"] and r.get("delta") is not None:
            by_day[str(r["date"])].append(r)
    out = {}
    for d in dates:
        rs = by_day.get(d) or []
        if not rs:
            continue
        out[d] = max(rs, key=lambda r: abs(float(r["delta"])))
    return out


def test_the_bear_pick_the_study_deleted_equals_the_library():
    bear_debit = {"bear_put"}
    book = [
        # two candidates the same day, the second the larger |delta|
        {"date": "2025-01-06", "structure": "bear_put", "credit": False,
         "delta": -0.20, "id": "a"},
        {"date": "2025-01-06", "structure": "bear_put", "credit": False,
         "delta": 0.55, "id": "b"},
        # a TIE: first-wins, which is max()'s rule on both sides
        {"date": "2025-01-07", "structure": "bear_put", "credit": False,
         "delta": -0.40, "id": "c"},
        {"date": "2025-01-07", "structure": "bear_put", "credit": False,
         "delta": 0.40, "id": "d"},
        # excluded: wrong structure, a credit, and a missing delta
        {"date": "2025-01-08", "structure": "bull_call", "credit": False,
         "delta": -0.90, "id": "e"},
        {"date": "2025-01-08", "structure": "bear_put", "credit": True,
         "delta": -0.90, "id": "f"},
        {"date": "2025-01-08", "structure": "bear_put", "credit": False,
         "delta": None, "id": "g"},
        # a date outside the sweep's date list
        {"date": "2025-01-09", "structure": "bear_put", "credit": False,
         "delta": -0.99, "id": "h"},
    ]
    dates = ["2025-01-06", "2025-01-07", "2025-01-08"]

    cands = [r for r in book if r["structure"] in bear_debit and not r["credit"]
             and r.get("delta") is not None]
    new = HC.sleeve_pick(cands, lambda r: abs(float(r["delta"])), dates=dates)
    old = _old_bear_pick(book, dates, bear_debit)

    assert list(new) == list(old) == ["2025-01-06", "2025-01-07"]
    assert {d: r["id"] for d, r in new.items()} == {d: r["id"] for d, r in old.items()}
    assert new["2025-01-06"]["id"] == "b" and new["2025-01-07"]["id"] == "c"
