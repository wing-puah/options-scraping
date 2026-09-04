"""The `trigger_entry` indexing rule and its gates, pinned before the study is trusted.

WHY THIS EXISTS
---------------
`research/pre-registrations/f1_selection/trigger_entry.md` registers this file
BEFORE the module existed, and makes it a precondition rather than a nicety:

    "`tests/test_trigger_entry.py` must exist and must pin: the k-indexing (a
    crossing at session k fills at `marks[k-1]`), `first_cross` returning None
    when nothing crosses within N, G-SYNTH at lag 0 over the
    `tests/test_harness_replay.py` fixture (imported, never copied), the leak
    guard on a no-direction row, `trigger_met` inclusivity in both directions, a
    holiday not consuming an N, a credit row's synthetic having a positive denom
    and a sane contract count, and a close-only (`SRC_TILDE`, o/h/l None) bar
    never raising."

The indexing rule is the whole study. `Trade.grid` is `_weekday_grid(signal_date,
end)` — "weekdays AFTER the signal date" — so `marks[0]` is already the fill
session, while `trigger_met` counts sessions on the BAR SERIES, which skips
market holidays. Those two calendars agree on most rows and NOT on all of them,
and an off-by-one between them would fill the position on a session that never
crossed the level while every printed number stayed plausible. That is the
failure mode this file exists to catch: not a crash, a study that quietly
measures the wrong fill.

G-SYNTH is the other half. If `synth_trade(rec, 0)` did not reproduce the stored
trade's timing, every window above it would be measuring a construction bug
rather than a trigger. The fixture and its loaders are imported from
`tests/test_harness_replay.py` rather than re-read here, so the two files can
never disagree about what the frozen expectations are — and a case added there
is automatically covered here.

Everything below runs on SYNTHETIC trades and the frozen fixture. Nothing reads
the live exports, so growing the book cannot make a case here rot.
"""
from __future__ import annotations

from datetime import date

import pytest

from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study.f1_selection.emission_timing import synth_trade
from scripts.backtest_study.f1_selection.trigger_entry import (
    ARM_L_LAGS,
    TRIGGER_N,
    arm_t_outcome,
    first_cross,
    grid_lag,
    in_scope,
    session_date,
)
from scripts.backtest_study.f2_management.exit_from_text import trigger_met
from scripts.backtest_study.lib import underlying as U
from scripts.backtest_study.lib.harness import Trade, replay
from tests.test_harness_replay import CASES, _trade

SIGNAL = date(2025, 1, 6)          # a Monday
EXPIRY = date(2025, 2, 14)

# No profit target, no stop, no time exit: the shipped replay on a flat path runs
# to the end of the grid, so nothing but the entry lag can move a synthetic.
NO_RULES = dict(pt=None, sl=None, trig=None, trail=None, tef=None)


def _synthetic(marks: list, *, entry: str = "1.00", credit: bool = False) -> Trade:
    """A one-contract trade whose marks are handed in directly.

    `entry_option_price = 1.00` makes `denom` 1.0, so `pnl_of(m) == m - 1` and
    the mark IS the readable quantity. The credit variant flips the leg signs so
    `_max_loss_per_unit` has a real structural width to size against.
    """
    grid = _weekday_grid(SIGNAL, EXPIRY)
    assert len(marks) <= len(grid), "test wants more marks than the grid holds"
    padded = list(marks) + [marks[-1]] * (len(grid) - len(marks))
    legs = (f"TEST:{EXPIRY.isoformat()}:100:C -1\nTEST:{EXPIRY.isoformat()}:110:C +1"
            if credit else
            f"TEST:{EXPIRY.isoformat()}:100:C +1\nTEST:{EXPIRY.isoformat()}:110:C -1")
    return Trade({
        "signal_date": SIGNAL.isoformat(),
        "ticker": "TEST",
        "structure": "bull_call_spread",
        "entry_option_price": entry,
        "contracts": "1",
        "dte_entry": str((EXPIRY - SIGNAL).days),
        "legs": legs,
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in padded),
    }, load_underlying=False)


def _bars(closes: dict, source: str = U.SRC_OHLC) -> dict:
    """`{date: Bar}` from `{date: close}`. OHLC bars carry an open; the tilde
    tier deliberately does not — that is the point of the close-only case."""
    if source == U.SRC_OHLC:
        return {d: U.Bar(c=c, o=c, h=c, l=c, source=source) for d, c in closes.items()}
    return {d: U.Bar(c=c, source=source) for d, c in closes.items()}


def _rec(t: Trade, bars: dict, level: float, direction: str,
         profile: dict = NO_RULES) -> dict:
    """The minimal record shape the arm functions read, with `_scope` resolved."""
    ed = U.entry_day(t, sessions=set(bars))
    assert ed is not None, "the synthetic must resolve an entry session"
    return dict(
        t=t, date=SIGNAL.isoformat(), ticker="TEST", structure="bull_call_spread",
        source="real", credit=t.entry_net < 0, mech_cell="PROD",
        _profile=dict(profile), _shipped=replay(t, **profile),
        _scope=dict(level=level, direction=direction, entry_day=ed, bars=bars,
                    bar_source=next(iter({b.source for b in bars.values()}), None)),
    )


# ── the frozen grid ──────────────────────────────────────────────────────────

def test_the_grid_is_the_registered_one():
    """Guard the guard: every assertion below is about a grid the registration
    froze. A silent widening would make the rest of this file test something
    else."""
    assert TRIGGER_N == (1, 3, 5)
    assert ARM_L_LAGS == (1, 3)


# ── the indexing rule ────────────────────────────────────────────────────────

def test_a_crossing_at_session_k_fills_at_marks_k_minus_1():
    """THE registered mapping: session k = 1 is `entry_day` = `marks[0]`.

    Bars are flat at 100 and cross 105 on the THIRD session. `first_cross` must
    report k = 3 and the synthetic must be filled at `marks[2]` — the mark on
    that session, not the one before or after it. A ±1 error here would fill on
    a session that never crossed the level, and every printed number would still
    look plausible.
    """
    t = _synthetic([1.10, 1.20, 1.30, 1.40, 1.50, 1.60])
    days = t.grid[:6]
    closes = dict(zip(days, [100.0, 100.0, 105.0, 100.0, 100.0, 100.0]))
    bars = _bars(closes)
    rec = _rec(t, bars, 105.0, "above")

    assert rec["_scope"]["entry_day"] == t.grid[0] == days[0]
    assert first_cross(bars, days[0], 105.0, "above", 5) == 3
    o = arm_t_outcome(rec, 5)
    assert o["status"] == "entered"
    assert o["k"] == 3
    assert o["lag"] == 2                      # k - 1, the registered rule
    assert o["t"].entry_net == pytest.approx(t.marks[2])
    assert o["t"].signal_date == t.grid[1]    # anchored at grid[lag - 1]


def test_first_cross_is_none_when_nothing_crosses_within_n():
    """The NOT-ENTERED branch. The level is crossed on session 4, so N=1 and N=3
    must both report None and the row must come back byte-identical to shipped —
    a window that "nearly" fired is not a fill."""
    t = _synthetic([1.10] * 8)
    days = t.grid[:6]
    bars = _bars(dict(zip(days, [100.0, 100.0, 100.0, 105.0, 105.0, 105.0])))
    rec = _rec(t, bars, 105.0, "above")

    assert first_cross(bars, days[0], 105.0, "above", 1) is None
    assert first_cross(bars, days[0], 105.0, "above", 3) is None
    assert first_cross(bars, days[0], 105.0, "above", 5) == 4
    for n in (1, 3):
        o = arm_t_outcome(rec, n)
        assert o["status"] == "not_entered"
        assert o["out"] is rec["_shipped"]


def test_first_cross_agrees_with_the_imported_trigger_met_in_both_directions():
    """One definition of "met", and it is `exit_from_text.trigger_met`'s.

    `first_cross(...) is not None` must be identical to `trigger_met(...)` on
    every window, or the study is re-implementing the thing it says it imports.
    """
    t = _synthetic([1.10] * 8)
    days = t.grid[:6]
    bars = _bars(dict(zip(days, [100.0, 98.0, 105.0, 100.0, 100.0, 100.0])))
    for direction, level in (("above", 105.0), ("below", 98.0), ("above", 999.0)):
        for n in (1, 2, 3, 5):
            assert (first_cross(bars, days[0], level, direction, n) is not None) \
                == trigger_met(bars, days[0], level, direction, n), \
                (direction, level, n)


def test_trigger_met_is_inclusive_in_both_directions():
    """"Holds 34" is met by a close of exactly 34 — `>=` above, `<=` below.

    This is the OPPOSITE convention from `harness.replay`'s strict underlying
    breach, and deliberately so: a trigger is a condition the operator would
    have called satisfied AT the level. Asserted on both sides so a one-sided
    tightening cannot pass.
    """
    t = _synthetic([1.10] * 8)
    days = t.grid[:3]
    bars = _bars(dict(zip(days, [34.0, 34.0, 34.0])))
    assert trigger_met(bars, days[0], 34.0, "above", 1) is True
    assert trigger_met(bars, days[0], 34.0, "below", 1) is True
    assert first_cross(bars, days[0], 34.0, "above", 1) == 1
    assert first_cross(bars, days[0], 34.0, "below", 1) == 1
    assert first_cross(bars, days[0], 34.01, "above", 3) is None
    assert first_cross(bars, days[0], 33.99, "below", 3) is None


def test_a_market_holiday_does_not_consume_one_of_the_n():
    """Sessions are counted on the BAR SERIES, not on the weekday grid.

    The second weekday of the grid has NO bar (a holiday). With N = 2 the two
    sessions are grid[0] and grid[2], so a cross on grid[2] IS inside the
    window — a grid-based count would have spent the second N on the closed day
    and missed it. The fill then lands at `marks[2]`, the crossing session's own
    mark, which is `grid_lag`'s answer and NOT `k - 1 = 1`.
    """
    t = _synthetic([1.10, 1.20, 1.30, 1.40, 1.50, 1.60])
    g = t.grid
    bars = _bars({g[0]: 100.0, g[2]: 105.0, g[3]: 100.0, g[4]: 100.0})
    rec = _rec(t, bars, 105.0, "above")

    assert U.sessions_from(bars, g[0], 2) == [g[0], g[2]]
    assert first_cross(bars, g[0], 105.0, "above", 2) == 2
    assert session_date(bars, g[0], 2) == g[2]
    assert grid_lag(t, g[2]) == 2

    o = arm_t_outcome(rec, 2)
    assert o["status"] == "entered"
    assert o["k"] == 2 and o["lag"] == 2      # the disclosed k-1 divergence
    assert o["t"].entry_net == pytest.approx(t.marks[2])


def test_grid_lag_is_none_past_the_end_of_the_grid():
    """A crossing session beyond the trade's own path is a COUNTED exclusion,
    never a silent re-anchor to some other session."""
    t = _synthetic([1.10] * 8)
    assert grid_lag(t, t.grid[-1]) == len(t.grid) - 1
    assert grid_lag(t, EXPIRY.replace(year=2030)) is None


# ── G-SYNTH: lag 0 reproduces the stored trade ───────────────────────────────

@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_g_synth_lag0_reproduces_the_stored_trade_on_the_frozen_fixture(case):
    """`synth_trade(rec, 0)` changes the FILL PRICE and the CONTRACT COUNT, and
    nothing else.

    `signal_date`, `dte_entry`, the weekday grid and the whole mark path must
    come back identical, on every case in the frozen fixture — all nine exit
    reasons, both signs of entry, the rounding and truncation cases, the
    unpriced day inside the path. If lag 0 shifted any of those, every ARM T
    window would be measuring a construction bug rather than a trigger.
    """
    t = _trade(case)
    rec = dict(t=t, ticker=case["ticker"], date=case["signal_date"])
    st, pad, status = synth_trade(rec, 0)
    if st is None:
        # A row with no usable day-0 mark has nothing to reproduce; it is a
        # counted exclusion in G2, not a pass and not a failure.
        assert status in ("no_mark_at_lag", "degenerate_zero_entry"), status
        return
    assert pad == 0, "lag 0 recomputes the SAME grid, so it can never need padding"
    assert st.signal_date == t.signal_date
    assert st.dte_entry == t.dte_entry
    assert st.grid == t.grid
    assert st.marks == t.marks
    assert st.entry_net == pytest.approx(t.marks[0])


def test_the_g_synth_gate_actually_covers_the_whole_fixture():
    """Guard the guard: the parametrisation must not quietly shrink."""
    assert len(CASES) >= 28, f"fixture shrank to {len(CASES)} cases"


def test_lag0_is_not_trivially_the_stored_trade():
    """The synthetic must be ABLE to differ, or every assertion above is
    satisfied by a `synth_trade` that returned its input.

    At least one fixture case must come back with a different fill price — a
    day-0 CLOSE mark is not the stored next-open fill.
    """
    moved = 0
    for case in CASES:
        t = _trade(case)
        st, _pad, _s = synth_trade(dict(t=t, ticker=case["ticker"],
                                        date=case["signal_date"]), 0)
        if st is not None and st.entry_net != t.entry_net:
            moved += 1
    assert moved > 0, "no fixture row's fill price moved at lag 0"


# ── G3: the leak guard ───────────────────────────────────────────────────────

def test_a_trigger_with_no_direction_is_out_of_scope_and_never_moves():
    """The registered `no_direction` bucket, and the leak guard on it.

    "PLTR 34" parses to a level with no direction word, so `in_scope` refuses
    it, and `arm_t_outcome` must return the SHIPPED result — the same object,
    not merely an equal one. The keying is evaluated inside the outcome
    function, so this is the real guard and not a restatement of a pre-filter.
    """
    t = _synthetic([1.10, 1.20, 1.30, 1.40])
    rec = dict(t=t, date=SIGNAL.isoformat(), ticker="TEST",
               structure="bull_call_spread", source="real", credit=False,
               mech_cell="PROD", _profile=dict(NO_RULES),
               _shipped=replay(t, **NO_RULES),
               text={"trigger": "PLTR 34 on the tape"},
               features={"trigger_level": 34.0})
    sc, bucket = in_scope(rec, {"TEST": _bars(dict(zip(t.grid[:3], [34.0] * 3)))})
    assert sc is None
    assert bucket == "conditional_unparseable: no direction"

    rec["_scope"] = sc
    for n in TRIGGER_N:
        o = arm_t_outcome(rec, n)
        assert o["status"] == "out_of_scope"
        assert o["out"] is rec["_shipped"], \
            "an out-of-scope row must come back as the SHIPPED object, untouched"


def test_a_row_with_no_trigger_text_is_out_of_scope():
    """The other end of the parse census: blank text is `no_trigger_text`, which
    is a COUNTED bucket and never an imputed level."""
    t = _synthetic([1.10] * 4)
    rec = dict(t=t, ticker="TEST", text={"trigger": "   "}, features={})
    sc, bucket = in_scope(rec, {"TEST": _bars({t.grid[0]: 100.0})})
    assert sc is None and bucket == "no_trigger_text"


# ── credit rows ──────────────────────────────────────────────────────────────

def test_a_credit_row_synthetic_has_a_positive_denom_and_a_sane_contract_count():
    """`pnl_of` / `dollars` denominate on `abs(entry_net)`, so a credit
    synthetic whose denom went to zero or negative would score nonsense, and a
    contract count of zero would make the harness dollar_stop unreachable.

    Sizing on the credit side is STRUCTURAL (`_max_loss_per_unit`), not the
    debit stop-loss formula, so this pins the branch the debit cases never
    reach.
    """
    t = _synthetic([-1.00, -0.90, -0.80, -0.70, -0.60], entry="-1.00", credit=True)
    assert t.entry_net < 0 and t.denom > 0
    for lag in (0, 1, 2):
        st, _pad, status = synth_trade(dict(t=t, ticker="TEST",
                                            date=SIGNAL.isoformat()), lag)
        assert st is not None, status
        assert st.entry_net < 0
        assert st.denom > 0
        assert st.contracts >= 1
        assert st.contracts == int(st.contracts)


# ── the close-only bar tier ──────────────────────────────────────────────────

def test_a_close_only_tilde_bar_never_raises():
    """`SRC_TILDE` bars carry NO open, high or low — that is one of the two
    reasons the registration makes this study CLOSE-ONLY.

    Every bar-touching path must run on them: `entry_day`, `sessions_from`,
    `trigger_met`, `first_cross`, and the whole ARM T outcome. An `AttributeError`
    on `bar.o` here would be a study that silently excluded the tilde tier
    instead of reporting it.
    """
    t = _synthetic([1.10, 1.20, 1.30, 1.40, 1.50])
    days = t.grid[:5]
    bars = _bars(dict(zip(days, [100.0, 100.0, 105.0, 100.0, 100.0])),
                 source=U.SRC_TILDE)
    assert all(b.o is None and b.h is None and b.l is None for b in bars.values())
    assert all(not b.has_ohlc for b in bars.values())

    rec = _rec(t, bars, 105.0, "above")
    assert rec["_scope"]["bar_source"] == U.SRC_TILDE
    assert trigger_met(bars, days[0], 105.0, "above", 5) is True
    assert first_cross(bars, days[0], 105.0, "above", 5) == 3
    o = arm_t_outcome(rec, 5)
    assert o["status"] == "entered"
    assert o["t"].entry_net == pytest.approx(t.marks[2])
