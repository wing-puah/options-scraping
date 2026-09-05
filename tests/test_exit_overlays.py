"""Tests for `scripts/backtest_study/lib/exit_overlays.py`.

The module is a COMPOSITION around the FROZEN harness, and the two things that
can go wrong with a composition are the two things tested hardest here:

  1. **G-FORK** — with its rule disabled, an overlay must reproduce
     `account_sim.replay_sized` field for field. If that identity holds, every
     arm's comparison against the shipped book is a comparison of the RULE and
     not of a second, subtly different replay engine. The identity is asserted
     against the SAME committed fixture `tests/test_harness_replay.py` pins the
     frozen engine with (`tests/fixtures/harness_replay.csv`), so a change to
     either file's expectations cannot quietly diverge from the other's, and
     over a grid of `pt`/`sl`/`tef` profiles on top.

  2. **LOOK-AHEAD** — the registration's information set says an exit decided at
     the close of session `d` may read marks/bars/`Volume` `<= d` and
     `Open Int` `<= d-1`. Three tests attack that directly: an explicit lag test
     (session `i` must decide on `t.grid[i-2]`, NEVER on `t.grid[i-1]`), a
     perturbation test (change every auxiliary value dated AFTER the decision
     session — the decision must not move), and the G1 shift test (push the whole
     series one session later — no exit may move EARLIER).

Everything else here is the boundary behaviour the study leans on: the
earlier-of tie order in both orderings, missing data returning `None` rather
than a fabricated exit, the blank-vs-literal-zero distinction in `load_oi`, the
two halves of a scale-out, and memo-key distinctness across overlay params (the
2026-08-13 G5 bug class).

Synthetic paths, not book rows: `backtests/` is gitignored and a fresh checkout
has none of it, so every case below is constructed in-file except the G-FORK
identity, which reads the committed fixture.
"""
import csv
import inspect
import statistics
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.backtest.helpers import _weekday_grid
from scripts.backtest.legs import Leg
from scripts.backtest_study.f4_deployment.account_sim import replay_sized
from scripts.backtest_study.lib import exit_overlays as X
from scripts.backtest_study.lib.harness import MAX_LOSS_ABS, Trade, replay
from scripts.backtest_study.lib.underlying import SRC_OHLC, Bar

FIXTURE = Path(__file__).parent / "fixtures" / "harness_replay.csv"

# The knob names the fixture spells out, in `harness.replay`'s own order. Same
# list as `tests/test_harness_replay.py`; read off the fixture rather than
# imported from `book.DEBIT_PROD`, so a change to the production constants
# cannot redefine what these cases mean.
KNOBS = ("pt", "sl", "trig", "trail", "tef", "be_after", "und_buffer")


def _fixture_cases():
    with open(FIXTURE, newline="") as fh:
        return list(csv.DictReader(fh))


CASES = _fixture_cases()


def _fixture_profile(case: dict) -> dict:
    return {k: (None if case[k] == "" else float(case[k])) for k in KNOBS}


def _fixture_rec(case: dict) -> dict:
    """A minimal `rec` — what `replay_sized` and `replay_overlaid` actually read.

    `load_underlying=False`: the real loader reads the ~337MB scraped option
    cache under `backtests/`, which a fresh checkout does not have. Neither
    replay path carries `t.underlying` onto the rebuilt scaled trade anyway, so
    an `und_buffer` fixture row simply never fires its underlying stop — in BOTH
    implementations, which is exactly what the identity is asserting.
    """
    t = Trade({
        "signal_date": case["signal_date"],
        "ticker": case["ticker"],
        "structure": case["structure"],
        "entry_option_price": case["entry_option_price"],
        "contracts": case["contracts"],
        "dte_entry": case["dte_entry"],
        "legs": case["legs"],
        "daily_price_csv": case["daily_price_csv"],
    }, load_underlying=False)
    return {"t": t, "credit": not (t.entry_net > 0),
            "structure": case["structure"], "date": case["signal_date"]}


# ── synthetic trades ─────────────────────────────────────────────────────────

SIGNAL = date(2026, 1, 5)      # a Monday
DTE = 14
EXPIRY = SIGNAL + timedelta(days=DTE)
GRID = _weekday_grid(SIGNAL, EXPIRY)      # 10 weekday sessions, Jan 6 .. Jan 19


def _trade(marks, structure="bull_call_spread", entry=1.00, contracts=4) -> Trade:
    """A synthetic `Trade` on `GRID`. `marks` must be one value per grid day."""
    assert len(marks) == len(GRID), f"{len(marks)} marks vs {len(GRID)} grid days"
    return Trade({
        "signal_date": SIGNAL.isoformat(),
        "ticker": "TEST",
        "structure": structure,
        "entry_option_price": f"{entry}",
        "contracts": str(contracts),
        "dte_entry": str(DTE),
        "legs": (f"TEST:{EXPIRY.isoformat()}:100:C +1\n"
                 f"TEST:{EXPIRY.isoformat()}:110:C -1"),
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
    })


FLAT = [1.00] * len(GRID)      # every session at the entry price: pnl 0 throughout


def _bar_dates() -> list[date]:
    """Weekdays spanning well before the signal (ATR needs 14 prior sessions)
    through the end of the grid."""
    out, d = [], date(2025, 11, 3)
    while d <= EXPIRY + timedelta(days=3):
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _bars(overrides: dict[date, float] | None = None) -> dict[date, Bar]:
    """A flat 100.00 OHLC series with a 2.00 daily range, plus close overrides.

    The constant range makes ATR14 exactly 2% of the close, so `k` translates
    into a round dollar distance: `k=1.5` -> 3.00 against the entry close.
    """
    overrides = overrides or {}
    out = {}
    for d in _bar_dates():
        c = overrides.get(d, 100.0)
        out[d] = Bar(c=c, o=c, h=c + 1.0, l=c - 1.0, source=SRC_OHLC, v=1000.0)
    return out


def _shift_forward(series: dict, ordered: list[date]) -> dict:
    """`series` moved one session LATER along `ordered`: the value dated
    `ordered[j]` becomes the value dated `ordered[j+1]`. G1's shift."""
    out = {}
    for j, d in enumerate(ordered[:-1]):
        if d in series:
            out[ordered[j + 1]] = series[d]
    return out


# ════════════════════════════════════════════════════════════════════════════
# G-FORK — the disabled overlay IS `replay_sized`
# ════════════════════════════════════════════════════════════════════════════

FIELDS = ("exit_reason", "days_held", "R", "dollars", "stop_exact")

# $1,000 is the frozen `MAX_LOSS_ABS` (scale factor 1) and $500 the study's own
# stop (factor 2) — both assert integrality inside the scaling block. $700 is a
# deliberate NON-integral factor, so `stop_exact=False` is exercised too and the
# ceil-rounding branch is compared rather than assumed.
STOPS = (MAX_LOSS_ABS, MAX_LOSS_ABS / 2.0, 700.0)


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_gfork_disabled_overlay_equals_replay_sized(case):
    """Every fixture row, every stop, every field: `make_replayer(DISABLED)` and
    `replay_sized` return the identical dict.

    Exact equality, never approximate — the frozen engine's rounding is part of
    what is being pinned, and a tolerance would hide a drifting composition.
    """
    rec = _fixture_rec(case)
    prof = _fixture_profile(case)
    replayer = X.make_replayer(X.DISABLED)
    for stop in STOPS:
        for contracts in (1, int(case["contracts"]), 3):
            want = replay_sized(rec, contracts, stop, profile=prof)
            got = replayer(rec, contracts, stop, profile=prof)
            assert [got[f] for f in FIELDS] == [want[f] for f in FIELDS], (
                f'{case["case_id"]} contracts={contracts} stop={stop}')


# A small, explicit corner of ARM W's registered 36-point grid: both ends of
# `pt`, `sl` on and off, `tef` on and off. The identity must not depend on which
# rules a profile happens to arm.
KNOB_GRID = [
    (0.60, 0.50, 0.60),
    (0.90, 0.75, 0.75),
    (1.10, None, None),
    (0.75, None, 0.60),
    (0.60, 0.75, None),
]


@pytest.mark.parametrize("pt,sl,tef", KNOB_GRID)
def test_gfork_holds_across_the_knob_grid(pt, sl, tef):
    """G-FORK over `knob_profile` points rather than the fixture's own profiles.

    ARM W replays the book under arbitrary grid points, so the identity has to
    survive profiles the fixture never recorded — including `sl=None` and
    `tef=None`, where a composition that "helpfully" defaulted a missing knob
    would diverge from the frozen engine's keyword defaults.
    """
    prof = X.knob_profile(pt, sl, tef)
    replayer = X.make_replayer(X.DISABLED)
    for case in CASES:
        rec = _fixture_rec(case)
        want = replay_sized(rec, 2, MAX_LOSS_ABS, profile=prof)
        got = replayer(rec, 2, MAX_LOSS_ABS, profile=prof)
        assert [got[f] for f in FIELDS] == [want[f] for f in FIELDS], case["case_id"]


def test_disabled_overlay_never_touches_the_data_loaders():
    """G-FORK must not depend on `backtests/` being present.

    A disabled overlay arms no rule, so no bar/OI/volume loader may be called at
    all. Loaders that raise prove it: if the identity above quietly loaded a
    series it would pass on the maintainer's machine and fail on a fresh
    checkout.
    """
    def boom(rec):
        raise AssertionError("a disabled overlay read an auxiliary series")

    replayer = X.make_replayer(X.DISABLED, bars_for=boom, oi_for=boom, vol_for=boom)
    rec = _fixture_rec(CASES[0])
    got = replayer(rec, 2, MAX_LOSS_ABS, profile=_fixture_profile(CASES[0]))
    assert got["exit_reason"] == CASES[0]["expect_exit_reason"]


def test_replayer_signature_matches_replay_sized():
    """Both replayer factories are drop-ins: same parameter names, kinds and
    defaults as `replay_sized`, so `simulate(..., replayer=...)` can call either
    positionally or by keyword."""
    def shape(fn):
        return [(p.name, p.kind, p.default)
                for p in inspect.signature(fn).parameters.values()]

    want = shape(replay_sized)
    assert shape(X.make_replayer(X.DISABLED)) == want
    assert shape(X.make_blockwise_replayer(lambda d: None, {}, X.DISABLED)) == want


def test_credit_rows_are_never_overlaid():
    """Every arm keeps `CREDIT_PROD` on a credit row, so an armed overlay must be
    inert there — and, being inert, must reproduce `replay_sized` exactly."""
    credit = [c for c in CASES if float(c["entry_option_price"]) <= 0]
    assert credit, "the fixture lost its credit rows"
    armed = X.make_replayer(X.Overlay(atr_k=0.001, oi_x=0.01, vol_climax=True),
                            bars_for=lambda rec: _bars(),
                            oi_for=lambda rec: {},
                            vol_for=lambda rec: {})
    for case in credit:
        rec = _fixture_rec(case)
        prof = _fixture_profile(case)
        want = replay_sized(rec, 2, MAX_LOSS_ABS, profile=prof)
        got = armed(rec, 2, MAX_LOSS_ABS, profile=prof)
        assert [got[f] for f in FIELDS] == [want[f] for f in FIELDS], case["case_id"]


# ════════════════════════════════════════════════════════════════════════════
# compose_earlier — the earlier-of, in both orderings
# ════════════════════════════════════════════════════════════════════════════

def test_compose_takes_the_overlay_when_it_fires_first():
    t = _trade(FLAT)
    base = replay(t, pt=None, sl=None, tef=None)      # runs to the end
    out = X.compose_earlier(t, base, [("atr_stop", 3)])
    assert (out["exit_reason"], out["days_held"]) == ("atr_stop", 3)
    assert out["pnl_pct"] == pytest.approx(0.0)


def test_compose_keeps_the_harness_when_it_fires_first():
    """The other ordering. The harness exits at session 2; an overlay firing at
    7 must leave the frozen engine's own reason, day and value untouched."""
    marks = list(FLAT)
    marks[1] = 2.00                                   # +100% on session 2
    t = _trade(marks)
    base = replay(t, pt=0.90, sl=None, tef=None)
    assert (base["exit_reason"], base["days_held"]) == ("profit_target", 2)
    out = X.compose_earlier(t, base, [("atr_stop", 7)])
    assert out == base


def test_compose_breaks_an_exact_tie_to_the_harness():
    """Tie order (1): a composition may only ever move an exit EARLIER, never
    relabel one that the frozen engine already owns."""
    marks = list(FLAT)
    marks[2] = 2.00
    t = _trade(marks)
    base = replay(t, pt=0.90, sl=None, tef=None)
    assert base["days_held"] == 3
    out = X.compose_earlier(t, base, [("atr_stop", 3)])
    assert out["exit_reason"] == "profit_target"


def test_compose_breaks_an_overlay_tie_by_declared_order():
    """Tie order (2): among overlays, the first in the sequence wins."""
    t = _trade(FLAT)
    base = replay(t, pt=None, sl=None, tef=None)
    assert X.compose_earlier(t, base, [("atr_stop", 4), ("oi_unwind", 4)]
                             )["exit_reason"] == "atr_stop"
    assert X.compose_earlier(t, base, [("oi_unwind", 4), ("atr_stop", 4)]
                             )["exit_reason"] == "oi_unwind"


def test_compose_advances_past_an_unpriced_session():
    """An overlay cannot transact on a day with no mark, so it advances to the
    next priced session exactly as `harness.replay` skips a `None`."""
    marks = list(FLAT)
    marks[2] = None                                   # session 3 unpriced
    t = _trade(marks)
    base = replay(t, pt=None, sl=None, tef=None)
    out = X.compose_earlier(t, base, [("atr_stop", 3)])
    assert out["days_held"] == 4


def test_compose_clamps_out_of_range_sessions():
    """Clamped to `1..len(grid)` so the downstream `Pos.exit_sess` index math
    always holds."""
    t = _trade(FLAT)
    base = replay(t, pt=None, sl=None, tef=None)
    assert X.compose_earlier(t, base, [("atr_stop", 0)])["days_held"] == 1
    assert X.compose_earlier(t, base, [("atr_stop", -5)])["days_held"] == 1
    # Past the end clamps to the last session, which is where the base already
    # is — so the base stands rather than being relabelled.
    assert X.compose_earlier(t, base, [("atr_stop", 999)]) == base


def test_compose_drops_an_overlay_with_no_priced_session_left():
    """Nothing priced at or after the clamped session: the overlay cannot fire
    and is dropped, rather than exiting on a mark that does not exist."""
    marks = FLAT[:6] + [None] * 4
    t = _trade(marks)
    base = replay(t, pt=None, sl=None, tef=None)
    assert X.compose_earlier(t, base, [("atr_stop", 8)]) == base


def test_compose_ignores_none_sessions():
    t = _trade(FLAT)
    base = replay(t, pt=None, sl=None, tef=None)
    assert X.compose_earlier(t, base, [("atr_stop", None), ("oi_unwind", None)]) == base


def test_compose_reports_the_harness_rounding():
    """An overlay exit must report `round(pnl_of(m), 10)` — the frozen engine's
    own clamp — so an overlay and a harness exit on the same session agree."""
    marks = list(FLAT)
    marks[3] = 0.3500
    t = _trade(marks, entry=1.40)
    base = replay(t, pt=None, sl=None, tef=None)
    out = X.compose_earlier(t, base, [("atr_stop", 4)])
    assert out["pnl_pct"] == round((0.3500 - 1.40) / 1.40, 10)
    assert out["pnl_pct"] == -0.75          # not -0.7499999999999999


# ════════════════════════════════════════════════════════════════════════════
# knob_profile
# ════════════════════════════════════════════════════════════════════════════

def test_knob_profile_off_means_none():
    assert X.knob_profile(0.90, 0.75, 0.75) == {"pt": 0.90, "sl": 0.75, "tef": 0.75}
    assert X.knob_profile(1.10, None, None) == {"pt": 1.10, "sl": None, "tef": None}
    # `None` is OFF, and `replay`'s keyword defaults read it that way: a profile
    # with `sl=None` runs no stop loss at all.
    t = _trade([1.00, 0.10] + [1.00] * 8)
    assert replay(t, **X.knob_profile(None, None, None))["exit_reason"] in (
        "expired", "cap_open")
    assert replay(t, **X.knob_profile(None, 0.75, None))["exit_reason"] == "stop_loss"


# ════════════════════════════════════════════════════════════════════════════
# ARM U — the ATR stop
# ════════════════════════════════════════════════════════════════════════════

def test_atr_stop_fires_on_the_first_adverse_session():
    """Flat 2.00-range bars -> ATR14 = 2% of a 100.00 close, so k=1.5 is a 3.00
    distance. The close drops to 96.00 on grid session 4."""
    bars = _bars({GRID[3]: 96.0})
    t = _trade(FLAT, structure="bull_call_spread")
    assert X.atr_stop_session(t, bars, 1.5) == 4
    # k=3.0 is a 6.00 distance — a 4.00 move does not reach it.
    assert X.atr_stop_session(t, bars, 3.0) is None


def test_atr_stop_direction_comes_from_the_structure():
    """A bear structure is hurt by an UP move and a bull structure by a DOWN
    one; the same bar series must fire on one and not the other."""
    up = _bars({GRID[3]: 104.0})
    assert X.atr_stop_session(_trade(FLAT, structure="bull_call_spread"), up, 1.5) is None
    assert X.atr_stop_session(_trade(FLAT, structure="bear_put_spread"), up, 1.5) == 4

    down = _bars({GRID[3]: 96.0})
    assert X.atr_stop_session(_trade(FLAT, structure="bull_call_spread"), down, 1.5) == 4
    assert X.atr_stop_session(_trade(FLAT, structure="bear_put_spread"), down, 1.5) is None


def test_atr_stop_excludes_a_structure_with_no_direction():
    """Not a `bull_*`/`bear_*` vertical -> `None` (an EXCLUSION), never a guessed
    direction. Widening this would widen the arm's registered population."""
    bars = _bars({GRID[3]: 60.0})
    for structure in ("long_call", "long_put", "iron_condor", ""):
        assert X.atr_stop_session(_trade(FLAT, structure=structure), bars, 1.5) is None


def test_atr_stop_is_none_without_bars():
    """Missing bars -> `None`, counted as an exclusion. Never a zero move."""
    assert X.atr_stop_session(_trade(FLAT), {}, 1.5) is None


def test_atr_stop_is_none_on_the_close_only_fallback():
    """`Price~` bars have no high/low, so `atr14_pct` is `None` and the row is
    excluded — the registration's two ATR exclusions (below min-obs, and
    close-only) fall out of the same check."""
    bars = {d: Bar(c=100.0, source="price_tilde") for d in _bar_dates()}
    bars[GRID[3]] = Bar(c=60.0, source="price_tilde")
    assert X.atr_stop_session(_trade(FLAT), bars, 1.5) is None


def test_atr_stop_is_none_when_the_series_is_too_short():
    """Below `underlying_features._MIN_ATR_OBS` there is no ATR, so no stop."""
    days = [d for d in _bar_dates() if d >= GRID[0] - timedelta(days=7)]
    bars = {d: Bar(c=(60.0 if d == GRID[3] else 100.0), o=100.0, h=101.0, l=99.0,
                   source=SRC_OHLC) for d in days}
    assert X.atr_stop_session(_trade(FLAT), bars, 1.5) is None


def test_atr_stop_skips_a_grid_day_with_no_bar():
    """A holiday inside the WEEKDAY grid is an unpriced session, not a flat
    move: the rule waits for the next session that actually has a bar."""
    bars = _bars({GRID[4]: 96.0})
    del bars[GRID[3]]
    t = _trade(FLAT)
    assert X.atr_stop_session(t, bars, 1.5) == 5


# ════════════════════════════════════════════════════════════════════════════
# ARM O — the flow-unwind exit, and its one-session lag
# ════════════════════════════════════════════════════════════════════════════

def _oi(values: dict[int, float | None]) -> dict[date, float | None]:
    """`{grid index (0-based) -> Open Int}` as a dated series, default 100."""
    out = {}
    for j, d in enumerate(GRID):
        out[d] = values.get(j, 100.0)
    return out


def test_oi_unwind_reads_the_previous_session_never_the_current_one():
    """THE LAG, stated as a discriminating case.

    The collapse is dated `GRID[3]` (grid index 3 = session 4). Under the
    registered lag, the value dated `t.grid[i-2]` is the one usable at session
    `i`, so index 3 is read at session 5. An implementation that read a
    session's OWN OI would answer 4 — the off-by-one this test exists to catch.
    """
    t = _trade(FLAT)
    series = _oi({3: 10.0})
    assert X.oi_unwind_session(t, series, 0.25) == 5
    # And the raw lag lookup agrees, independently of the rule.
    lag = X.lagged_by_session(t, series)
    assert lag[5] == 10.0
    assert lag[4] == 100.0


def test_oi_lag_leaves_session_one_unevaluable():
    """Session 1 is the entry session; there is no prior grid session to read,
    so the rule can never fire there however low the entry-day OI is."""
    t = _trade(FLAT)
    lag = X.lagged_by_session(t, _oi({0: 0.0}))
    assert lag[0] is None and lag[1] is None
    assert lag[2] == 0.0
    assert len(lag) == len(GRID) + 1


def test_oi_unwind_thresholds_on_the_running_max():
    t = _trade(FLAT)
    # Rises to 200 (dated index 2, read at session 4), then falls to 140 at
    # index 5 -> read at session 7. 140 <= 0.75 * 200 fires at X=0.25;
    # 140 > 0.60 * 200 does not fire at X=0.40.
    series = _oi({2: 200.0, 3: 200.0, 4: 200.0, 5: 140.0, 6: 140.0,
                  7: 140.0, 8: 140.0, 9: 140.0})
    assert X.oi_unwind_session(t, series, 0.25) == 7
    assert X.oi_unwind_session(t, series, 0.40) is None


def test_oi_literal_zero_is_a_full_unwind_and_blank_is_not():
    """The registration's sharpest distinction: `0` fires, blank is skipped."""
    t = _trade(FLAT)
    assert X.oi_unwind_session(t, _oi({4: 0.0}), 0.40) == 6
    assert X.oi_unwind_session(t, _oi({4: None}), 0.40) is None


def test_oi_unwind_needs_a_positive_running_max():
    """A leg whose lagged OI has never been positive has nothing to unwind;
    firing on `0 <= 0` there would be arithmetic, not a flow read."""
    t = _trade(FLAT)
    assert X.oi_unwind_session(t, {d: 0.0 for d in GRID}, 0.25) is None


def test_oi_unwind_is_none_without_a_series():
    assert X.oi_unwind_session(_trade(FLAT), {}, 0.25) is None


def test_oi_missing_days_are_skipped_not_read_as_a_drop():
    """A grid day absent from the series is skipped exactly as an unpriced mark
    is — never read as a 100% drop."""
    t = _trade(FLAT)
    series = {d: 100.0 for d in GRID}
    for j in (3, 4, 5):
        del series[GRID[j]]
    assert X.oi_unwind_session(t, series, 0.25) is None


def test_oi_blank_share_measures_the_lagged_series():
    t = _trade(FLAT)
    assert X.oi_blank_share(t, _oi({})) == 0.0
    # 3 blanks among the 9 evaluable sessions (session 1 is never evaluable).
    assert X.oi_blank_share(t, _oi({0: None, 1: None, 2: None})) == pytest.approx(3 / 9)
    assert X.oi_blank_share(t, {}, hold_sessions=1) is None


# ════════════════════════════════════════════════════════════════════════════
# ARM O — the volume-climax variant
# ════════════════════════════════════════════════════════════════════════════

def _vol(values: dict[int, float | None], default=100.0) -> dict[date, float | None]:
    return {d: values.get(j, default) for j, d in enumerate(GRID)}


def test_vol_climax_needs_both_the_spike_and_an_adverse_mark():
    """3x the expanding median AND the mark closed against the position."""
    marks = list(FLAT)
    marks[4] = 0.80                       # session 5 is down
    t = _trade(marks)
    assert X.vol_climax_session(t, _vol({4: 500.0})) == 5
    # Same spike on a session whose mark is NOT against the position: no fire.
    assert X.vol_climax_session(_trade(FLAT), _vol({4: 500.0})) is None
    # Adverse mark without the spike: no fire.
    assert X.vol_climax_session(t, _vol({})) is None


def test_vol_climax_median_is_expanding_not_whole_period():
    """The median is taken over sessions up to AND INCLUDING `d`.

    Here the volume ramps to a huge level LATE. A whole-period median would be
    dragged up by those later sessions and would suppress the early spike; the
    expanding median, which cannot see them, fires on it. That difference is the
    leak G1 exists to catch, asserted directly.

    (Note the spike must land on the THIRD observation at the earliest: with two
    observations the median is their mean, and no single value can be 3x the
    mean of itself and a positive other. That is a property of the registered
    rule, not a tuned start-up window.)
    """
    t = _trade([1.00] + [0.80] * (len(GRID) - 1))
    series = _vol({2: 400.0}, default=100.0)
    for j in range(3, len(GRID)):
        series[GRID[j]] = 100000.0
    assert X.vol_climax_session(t, series) == 3
    # The whole-period median of the same series is 50,200 — on which the spike
    # never fires. An implementation that took it would answer None here.
    assert statistics.median([v for v in series.values()]) > 3 * 400.0


def test_vol_climax_skips_missing_volumes():
    """A missing volume is skipped, never read as zero — a zero would drag the
    median down and fabricate a spike on the next session."""
    marks = [1.00, 0.80, 0.80] + [0.80] * 7
    t = _trade(marks)
    series = _vol({0: None, 1: None, 2: None})
    assert X.vol_climax_session(t, series) is None
    assert X.vol_climax_session(t, {}) is None


# ════════════════════════════════════════════════════════════════════════════
# G1 — the leak guard, in both halves
# ════════════════════════════════════════════════════════════════════════════

def test_perturbing_a_series_after_the_decision_session_changes_nothing():
    """Half one of no-lookahead: values dated AFTER the session that decided the
    exit cannot reach that decision. Asserted for all three auxiliary series."""
    t_flat = _trade(FLAT)

    # ATR: fires at session 4 off the bar dated GRID[3].
    bars = _bars({GRID[3]: 96.0})
    assert X.atr_stop_session(t_flat, bars, 1.5) == 4
    poisoned = dict(bars)
    for d in _bar_dates():
        if d > GRID[3]:
            poisoned[d] = Bar(c=1.0, o=1.0, h=2.0, l=0.5, source=SRC_OHLC)
    assert X.atr_stop_session(t_flat, poisoned, 1.5) == 4

    # OI: fires at session 5 off the value dated GRID[3].
    oi = _oi({3: 10.0})
    assert X.oi_unwind_session(t_flat, oi, 0.25) == 5
    oi_poisoned = dict(oi)
    for j in range(4, len(GRID)):
        oi_poisoned[GRID[j]] = 1e9
    assert X.oi_unwind_session(t_flat, oi_poisoned, 0.25) == 5

    # Volume: fires at session 3 off the value dated GRID[2].
    marks = [1.00] + [0.80] * (len(GRID) - 1)
    t_dn = _trade(marks)
    vol = _vol({2: 400.0})
    assert X.vol_climax_session(t_dn, vol) == 3
    vol_poisoned = dict(vol)
    for j in range(3, len(GRID)):
        vol_poisoned[GRID[j]] = 1e9
    assert X.vol_climax_session(t_dn, vol_poisoned) == 3


def test_shifting_a_series_one_session_later_never_moves_an_exit_earlier():
    """Half two of G1: push every auxiliary series one session forward. A rule
    reading the future would exit EARLIER; a rule reading only the past can only
    exit at the same session or later (or not at all)."""
    t_flat = _trade(FLAT)
    bar_days = _bar_dates()

    bars = _bars({GRID[3]: 96.0})
    before = X.atr_stop_session(t_flat, bars, 1.5)
    after = X.atr_stop_session(t_flat, _shift_forward(bars, bar_days), 1.5)
    assert before == 4
    assert after is None or after >= before
    assert after == 5           # and it moved by exactly the shift

    oi = _oi({3: 10.0})
    before = X.oi_unwind_session(t_flat, oi, 0.25)
    after = X.oi_unwind_session(t_flat, _shift_forward(oi, GRID), 0.25)
    assert before == 5
    assert after is None or after >= before

    marks = [1.00] + [0.80] * (len(GRID) - 1)
    t_dn = _trade(marks)
    vol = _vol({2: 400.0})
    before = X.vol_climax_session(t_dn, vol)
    after = X.vol_climax_session(t_dn, _shift_forward(vol, GRID))
    assert before == 3
    assert after is None or after >= before


# ════════════════════════════════════════════════════════════════════════════
# load_oi / load_volume — blank vs literal zero
# ════════════════════════════════════════════════════════════════════════════

HEADER = "Time,Open,High,Low,Latest,Volume,Open Int,IV,Delta,Price~,Bid,Ask"


def _write_leg_file(tmp_path: Path, leg: Leg, rows: list[str]) -> None:
    p = X.leg_cache_path(leg, tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join([HEADER] + rows) + "\n")
    X._leg_flow.cache_clear()


def test_load_oi_keeps_blank_and_literal_zero_distinct(tmp_path):
    """`None` (blank) is MISSING; `0.0` is a real full unwind. Conflating them
    either fabricates exits or hides them, so the reader must not."""
    leg = Leg(qty=1, ticker="TEST", expiration=date(2026, 1, 19), strike=100.0,
              opt_type="Call")
    _write_leg_file(tmp_path, leg, [
        "2026-01-06,1,1,1,1,500,1234,50,0.5,100,0.9,1.1",
        "2026-01-07,1,1,1,1,,0,50,0.5,100,0.9,1.1",       # OI 0, Volume blank
        "2026-01-08,1,1,1,1,700,,50,0.5,100,0.9,1.1",     # OI blank
    ])
    oi = X.load_oi(leg, tmp_path)
    assert oi[date(2026, 1, 6)] == 1234.0
    assert oi[date(2026, 1, 7)] == 0.0
    assert oi[date(2026, 1, 8)] is None
    # A key exists for every dated row, so "blank" and "absent" stay different.
    assert set(oi) == {date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)}

    vol = X.load_volume(leg, tmp_path)
    assert vol[date(2026, 1, 6)] == 500.0
    assert vol[date(2026, 1, 7)] is None
    assert vol[date(2026, 1, 8)] == 700.0


def test_load_oi_of_a_missing_file_is_empty(tmp_path):
    leg = Leg(qty=1, ticker="NOPE", expiration=date(2026, 1, 19), strike=1.0,
              opt_type="Put")
    X._leg_flow.cache_clear()
    assert X.load_oi(leg, tmp_path) == {}
    assert X.load_volume(leg, tmp_path) == {}
    assert X.load_oi(None) == {}


def test_entry_long_leg_is_the_single_long_leg():
    t = _trade(FLAT)
    leg = X.entry_long_leg(t)
    assert leg is not None and leg.qty > 0 and leg.strike == 100.0
    # No long leg, and two long legs, are both undecidable -> None.
    exp = EXPIRY.isoformat()
    short_only = _trade(FLAT)
    short_only.legs = [leg for leg in short_only.legs if leg.qty < 0]
    assert X.entry_long_leg(short_only) is None
    two_longs = Trade({**_trade(FLAT).row,
                       "legs": f"TEST:{exp}:100:C +1\nTEST:{exp}:110:C +1"})
    assert X.entry_long_leg(two_longs) is None


# ════════════════════════════════════════════════════════════════════════════
# ARM P — partial scale-out
# ════════════════════════════════════════════════════════════════════════════

def test_partial_scaleout_returns_both_halves():
    """The `pt` half takes the shipped target; the rest half replays the same
    profile with `pt=None` and runs on."""
    marks = list(FLAT)
    marks[3] = 2.00                                  # +100% on session 4
    marks[6] = 1.50
    t = _trade(marks, contracts=4)
    prof = X.knob_profile(0.90, 0.75, None)
    pt_half, rest_half = X.partial_scaleout(t, prof)
    assert (pt_half["exit_reason"], pt_half["days_held"]) == ("profit_target", 4)
    assert pt_half["contracts"] == 2 and pt_half["half"] == "pt"
    assert rest_half["exit_reason"] in ("expired", "cap_open")
    assert rest_half["contracts"] == 2 and rest_half["half"] == "rest"


def test_partial_scaleout_splits_an_odd_count_ceil_then_floor():
    t = _trade(FLAT, contracts=5)
    pt_half, rest_half = X.partial_scaleout(t, X.knob_profile(0.90, 0.75, None))
    assert (pt_half["contracts"], rest_half["contracts"]) == (3, 2)


def test_partial_scaleout_refuses_a_single_contract():
    """`n = 1` cannot be split — one half would be zero contracts, which is not
    a position. Such rows are EXCLUDED from ARM P and counted."""
    assert X.partial_scaleout(_trade(FLAT, contracts=1),
                              X.knob_profile(0.90, 0.75, None)) is None


def test_partial_scaleout_halves_see_their_own_dollar_stop():
    """Each half is replayed on its OWN rebuilt trade, because the frozen dollar
    stop scales with the contract count: a half-size position must not be
    stopped out on a full-size threshold.

    `entry_net` 1.00, 20 contracts -> the full position's dollar stop
    (`pnl x 1 x 100 x 20 <= -1000`) needs -0.50, while each 10-contract half
    needs -1.00. A -0.60 mark therefore stops the WHOLE position but neither
    half — so a correct split reports no `dollar_stop` at all.
    """
    marks = list(FLAT)
    marks[3] = 0.40                                  # -60%
    t = _trade(marks, contracts=20)
    assert replay(t, pt=None, sl=None, tef=None)["exit_reason"] == "dollar_stop"
    pt_half, rest_half = X.partial_scaleout(t, X.knob_profile(None, None, None))
    assert pt_half["exit_reason"] != "dollar_stop"
    assert rest_half["exit_reason"] != "dollar_stop"


# ════════════════════════════════════════════════════════════════════════════
# The memo key — the 2026-08-13 G5 bug class
# ════════════════════════════════════════════════════════════════════════════

def _overlay_rec():
    """A synthetic `rec` whose bars fire the ATR stop at session 4.

    `mech_cell` is carried because the SHIPPED profile is a real lookup:
    `default_profile_for` -> `account_sim.profile_for` -> `prod_profile_for`
    merges the regime exit last and reads it. A book `rec` always has it."""
    t = _trade(FLAT)
    return {"t": t, "credit": False, "structure": t.structure,
            "mech_cell": "PROD", "date": SIGNAL.isoformat()}


def test_memo_keys_are_distinct_across_overlay_params():
    """One shared cache, several overlays: each must get its OWN entry, and the
    answers must not cross-contaminate.

    This is the failure `replay_sized`'s docstring records for the exit profile
    (found by G5 on 2026-08-13), lifted to the overlay params. `k=1.5` exits at
    the ATR stop and `k=3.0` does not; a key that omitted `atr_k` would serve
    the first answer to the second.
    """
    rec = _overlay_rec()
    bars = _bars({GRID[3]: 96.0})
    prof = X.knob_profile(None, None, None)
    cache = {}
    kw = dict(bars_for=lambda r: bars, oi_for=lambda r: {}, vol_for=lambda r: {})

    tight = X.make_replayer(X.Overlay(atr_k=1.5, label="k1.5"), **kw)
    loose = X.make_replayer(X.Overlay(atr_k=3.0, label="k3.0"), **kw)

    a = tight(rec, 2, MAX_LOSS_ABS, profile=prof, cache=cache)
    b = loose(rec, 2, MAX_LOSS_ABS, profile=prof, cache=cache)
    assert a["exit_reason"] == "atr_stop" and a["days_held"] == 4
    assert b["exit_reason"] != "atr_stop"
    assert len(cache) == 2
    # Re-asking is served from the memo and still gives each its own answer.
    assert tight(rec, 2, MAX_LOSS_ABS, profile=prof, cache=cache) == a
    assert loose(rec, 2, MAX_LOSS_ABS, profile=prof, cache=cache) == b
    assert len(cache) == 2


def test_memo_key_separates_every_overlay_field():
    """Each field of `Overlay` — including the reporting-only label — lands in
    the key. Over-keying costs a recomputation; under-keying is the bug."""
    rec = _overlay_rec()
    prof = X.knob_profile(0.90, 0.75, None)
    cache = {}
    kw = dict(bars_for=lambda r: _bars(), oi_for=lambda r: _oi({}),
              vol_for=lambda r: _vol({}))
    specs = [
        X.Overlay(),
        X.Overlay(atr_k=1.5),
        X.Overlay(atr_k=3.0),
        X.Overlay(atr_k=1.5, atr_replaces_sl=True),
        X.Overlay(oi_x=0.25),
        X.Overlay(oi_x=0.40),
        X.Overlay(vol_climax=True),
        X.Overlay(vol_climax=True, vol_mult=5.0),
        X.Overlay(profile=X.knob_profile(0.60, 0.50, 0.60)),
        X.Overlay(atr_k=1.5, label="a"),
        X.Overlay(atr_k=1.5, label="b"),
    ]
    for spec in specs:
        X.make_replayer(spec, **kw)(rec, 2, MAX_LOSS_ABS, profile=prof, cache=cache)
    assert len(cache) == len(specs)


def test_overlay_keys_cannot_collide_with_replay_sized_keys():
    """A caller may hand ONE `new_cache()` to both `replay_sized` and an overlay
    replayer. The keys differ structurally (5 elements vs 4), so neither can
    serve the other — and with the overlay disabled both still agree."""
    rec = _fixture_rec(CASES[0])
    prof = _fixture_profile(CASES[0])
    cache = {}
    want = replay_sized(rec, 2, MAX_LOSS_ABS, profile=prof, cache=cache)
    got = X.make_replayer(X.DISABLED)(rec, 2, MAX_LOSS_ABS, profile=prof, cache=cache)
    assert len(cache) == 2
    assert [got[f] for f in FIELDS] == [want[f] for f in FIELDS]


def test_atr_replaces_sl_changes_the_profile_and_the_key():
    """ARM U variant (b): the ATR stop REPLACES `sl`, so the row replays with
    `sl=None`. Variant (a) leaves the shipped `sl` alone."""
    marks = list(FLAT)
    marks[2] = 0.20                                  # -80%: trips sl .75
    rec = {"t": _trade(marks), "credit": False}
    prof = X.knob_profile(None, 0.75, None)
    kw = dict(bars_for=lambda r: _bars(), oi_for=lambda r: {}, vol_for=lambda r: {})
    added = X.make_replayer(X.Overlay(atr_k=1.5), **kw)(rec, 2, MAX_LOSS_ABS, profile=prof)
    replaced = X.make_replayer(X.Overlay(atr_k=1.5, atr_replaces_sl=True), **kw)(
        rec, 2, MAX_LOSS_ABS, profile=prof)
    assert added["exit_reason"] == "stop_loss"
    assert replaced["exit_reason"] != "stop_loss"


# ════════════════════════════════════════════════════════════════════════════
# ARM U variant (b) — the sl-strip is scoped to rows the ATR rule GOVERNS
# ════════════════════════════════════════════════════════════════════════════
#
# The registration EXCLUDES a row the ATR rule cannot fire on ("EXCLUDED and
# counted": no bars, no entry anchor, a close-only `Price~` series, `atr14_pct`
# None, no `bull_`/`bear_` direction). Variant (b) REPLACES `sl` with that stop,
# so stripping the stop before asking whether the rule governs the row leaves it
# with NEITHER — an unregistered naked-stop arm whose book would be read as ARM
# U's. These are the G-FORK identity again, on an ARMED overlay: an excluded row
# must equal `replay_sized` field for field.

def _ohlc_bar(close: float) -> Bar:
    return Bar(c=close, o=close, h=close + 1.0, l=close - 1.0, source=SRC_OHLC)


EXCLUDED_BAR_SERIES = {
    "no bars at all": lambda: {},
    "close-only `Price~` (no high/low, so no true range)":
        lambda: {d: Bar(c=100.0, source="price_tilde") for d in _bar_dates()},
    "series too short for ATR14":
        lambda: {d: _ohlc_bar(100.0)
                 for d in _bar_dates() if d >= GRID[0] - timedelta(days=7)},
}


@pytest.mark.parametrize("why", sorted(EXCLUDED_BAR_SERIES))
def test_arm_u_b_leaves_an_excluded_rows_stop_alone(why):
    """A row ARM U cannot govern replays the SHIPPED profile, `sl` included."""
    marks = list(FLAT)
    marks[2] = 0.20                                  # -80%: trips sl .75
    rec = {"t": _trade(marks), "credit": False}
    prof = X.knob_profile(None, 0.75, None)
    bars = EXCLUDED_BAR_SERIES[why]()
    armed = X.make_replayer(X.Overlay(atr_k=1.5, atr_replaces_sl=True),
                            bars_for=lambda r: bars,
                            oi_for=lambda r: {}, vol_for=lambda r: {})
    want = replay_sized(rec, 2, MAX_LOSS_ABS, profile=prof)
    got = armed(rec, 2, MAX_LOSS_ABS, profile=prof)
    assert want["exit_reason"] == "stop_loss", "the case stopped exercising sl"
    assert [got[f] for f in FIELDS] == [want[f] for f in FIELDS], why


def test_arm_u_b_leaves_the_stop_alone_without_a_direction():
    """`long_call` has no `bull_`/`bear_` direction, so ARM U cannot govern it
    however good the bars are."""
    marks = list(FLAT)
    marks[2] = 0.20
    rec = {"t": _trade(marks, structure="long_call"), "credit": False}
    prof = X.knob_profile(None, 0.75, None)
    armed = X.make_replayer(X.Overlay(atr_k=1.5, atr_replaces_sl=True),
                            bars_for=lambda r: _bars(),
                            oi_for=lambda r: {}, vol_for=lambda r: {})
    want = replay_sized(rec, 2, MAX_LOSS_ABS, profile=prof)
    got = armed(rec, 2, MAX_LOSS_ABS, profile=prof)
    assert want["exit_reason"] == "stop_loss"
    assert [got[f] for f in FIELDS] == [want[f] for f in FIELDS]


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_arm_u_b_on_a_barless_book_is_the_gfork_identity(case):
    """The whole committed fixture, with ARM U/b ARMED and no bars anywhere:
    every row must reproduce `replay_sized` exactly, because every row is an
    ARM U exclusion. This is the gate the naked-stop bug would have failed."""
    rec = _fixture_rec(case)
    prof = _fixture_profile(case)
    armed = X.make_replayer(X.Overlay(atr_k=2.0, atr_replaces_sl=True),
                            bars_for=lambda r: {},
                            oi_for=lambda r: {}, vol_for=lambda r: {})
    for stop in STOPS:
        want = replay_sized(rec, 2, stop, profile=prof)
        got = armed(rec, 2, stop, profile=prof)
        assert [got[f] for f in FIELDS] == [want[f] for f in FIELDS], case["case_id"]


def test_arm_u_b_does_strip_the_stop_when_the_rule_governs():
    """The other half of the scoping: on a governable row variant (b) still
    replaces `sl`, or the fix would have disarmed the arm."""
    marks = list(FLAT)
    marks[2] = 0.20
    rec = {"t": _trade(marks), "credit": False}
    prof = X.knob_profile(None, 0.75, None)
    got = X.make_replayer(X.Overlay(atr_k=1.5, atr_replaces_sl=True),
                          bars_for=lambda r: _bars(),
                          oi_for=lambda r: {}, vol_for=lambda r: {})(
        rec, 2, MAX_LOSS_ABS, profile=prof)
    assert got["exit_reason"] != "stop_loss"


def test_atr_governs_is_the_single_exclusion_test():
    """`atr_governs` and `atr_stop_session` must agree about what is excluded —
    one encoding, two callers (the sl-strip and the firing session)."""
    t = _trade(FLAT)
    assert X.atr_governs(t, _bars(), 1.5) is True
    for build in EXCLUDED_BAR_SERIES.values():
        assert X.atr_governs(t, build(), 1.5) is False
        assert X.atr_stop_session(t, build(), 1.5) is None
    assert X.atr_governs(_trade(FLAT, structure="long_call"), _bars(), 1.5) is False


# ════════════════════════════════════════════════════════════════════════════
# ARM O — the >= 20%-blank exclusion binds at the READ boundary
# ════════════════════════════════════════════════════════════════════════════

def test_a_row_over_the_blank_threshold_is_read_as_no_series(monkeypatch):
    """The registration EXCLUDES a row blank on >= 20% of its hold sessions. The
    exclusion has to bind where the series is READ — applied only in the census
    it would be a number in a report while the arm went on exiting the row."""
    rec = _overlay_rec()
    t = rec["t"]
    # 3 blanks among 9 evaluable sessions = 33% >= 20%.
    blanked = _oi({0: None, 1: None, 2: None})
    monkeypatch.setattr(X, "load_oi", lambda leg, cache_dir=None: blanked)
    monkeypatch.setattr(X, "entry_long_leg", lambda tr: object())
    assert X.oi_blank_share(t, blanked) >= X.OI_BLANK_EXCLUSION
    assert X.default_oi_for(rec) == {}


def test_the_blank_denominator_is_the_hold_window_not_the_whole_grid(monkeypatch):
    """The registration excludes a row blank on ">= 20% of its HOLD SESSIONS".

    Measured over the whole weekday grid instead — out to expiry, or the
    120-day path cap on a real row — a short hold's blanks are diluted by
    sessions the position was never held through, and rows the registration
    excludes are ADMITTED into ARM O. That is the permissive direction the
    exclusion exists to close.

    This row exits at session 3 on the shipped profit target, so its hold
    window has TWO evaluable sessions and one blank is 50% of it; the same
    blank is 1 of 9 = 11% of the grid. The two readings disagree, and the read
    boundary must take the hold one."""
    marks = list(FLAT)
    marks[2] = 2.00                                  # +100%: shipped pt fires
    rec = _overlay_rec()
    rec["t"] = _trade(marks)
    assert X.shipped_hold_sessions(rec) == 3

    one_blank = _oi({0: None})
    monkeypatch.setattr(X, "load_oi", lambda leg, cache_dir=None: one_blank)
    monkeypatch.setattr(X, "entry_long_leg", lambda tr: object())

    assert X.oi_blank_share(rec["t"], one_blank) < X.OI_BLANK_EXCLUSION
    assert X.oi_blank_share(rec["t"], one_blank, 3) >= X.OI_BLANK_EXCLUSION
    assert X.default_oi_for(rec) == {}                # the HOLD reading binds


def test_a_row_under_the_blank_threshold_is_read_whole(monkeypatch):
    rec = _overlay_rec()
    ok = _oi({0: None})                       # 1 of 9 = 11% < 20%
    monkeypatch.setattr(X, "load_oi", lambda leg, cache_dir=None: ok)
    monkeypatch.setattr(X, "entry_long_leg", lambda tr: object())
    assert X.default_oi_for(rec) == ok


def test_an_excluded_row_can_never_fire_the_unwind(monkeypatch):
    """End to end: an over-threshold row's series reads empty, and an empty
    series makes the rule return `None`, so the arm cannot exit it."""
    rec = _overlay_rec()
    # A collapse that WOULD fire, on a row that is too blank to be read.
    blanked = _oi({0: None, 1: None, 2: None, 6: 1.0})
    monkeypatch.setattr(X, "load_oi", lambda leg, cache_dir=None: blanked)
    monkeypatch.setattr(X, "entry_long_leg", lambda tr: object())
    assert X.oi_unwind_session(rec["t"], blanked, 0.25) is not None
    assert X.oi_unwind_session(rec["t"], X.default_oi_for(rec), 0.25) is None


def test_the_blank_threshold_is_declared_once():
    """One constant, in the module that reads the series; the study re-exports
    it rather than declaring a second literal that could drift."""
    from scripts.backtest_study.f2_management import exit_drawdown as S
    assert S.OI_BLANK_EXCLUSION is X.OI_BLANK_EXCLUSION == 0.20


def test_overlay_profile_overrides_the_shipped_knobs():
    """ARM W: the cell's own `pt`/`sl`/`tef` replace the row's shipped profile."""
    marks = list(FLAT)
    marks[3] = 1.70                                  # +70%
    rec = {"t": _trade(marks), "credit": False}
    kw = dict(bars_for=lambda r: {}, oi_for=lambda r: {}, vol_for=lambda r: {})
    shipped = X.knob_profile(0.90, 0.75, None)
    out = X.make_replayer(X.Overlay(profile=X.knob_profile(0.60, 0.75, None)), **kw)(
        rec, 2, MAX_LOSS_ABS, profile=shipped)
    assert (out["exit_reason"], out["days_held"]) == ("profit_target", 4)
    plain = X.make_replayer(X.DISABLED, **kw)(rec, 2, MAX_LOSS_ABS, profile=shipped)
    assert plain["exit_reason"] != "profit_target"


# ════════════════════════════════════════════════════════════════════════════
# The blockwise replayer
# ════════════════════════════════════════════════════════════════════════════

def test_blockwise_replayer_dispatches_by_block():
    """Walk-forward stitching: each row replays under the configuration its
    OWN block's TRAIN fit selected."""
    rec = _overlay_rec()
    bars = _bars({GRID[3]: 96.0})
    kw = dict(bars_for=lambda r: bars, oi_for=lambda r: {}, vol_for=lambda r: {})
    prof = X.knob_profile(None, None, None)
    cache = {}

    fires = X.make_blockwise_replayer(lambda d: "B1", {"B1": X.Overlay(atr_k=1.5)}, **kw)
    inert = X.make_blockwise_replayer(lambda d: "B2", {"B2": X.Overlay(atr_k=3.0)}, **kw)
    assert fires(rec, 2, MAX_LOSS_ABS, profile=prof, cache=cache)["exit_reason"] == "atr_stop"
    assert inert(rec, 2, MAX_LOSS_ABS, profile=prof, cache=cache)["exit_reason"] != "atr_stop"
    assert len(cache) == 2


def test_blockwise_replayer_refuses_an_unmapped_date_without_a_default():
    """Burn-in dates must not be silently replayed under the shipped profile and
    folded into the headline: an unmapped date raises unless the caller says out
    loud what should happen to it."""
    rec = _overlay_rec()
    kw = dict(bars_for=lambda r: {}, oi_for=lambda r: {}, vol_for=lambda r: {})
    strict = X.make_blockwise_replayer(lambda d: None, {}, **kw)
    with pytest.raises(KeyError):
        strict(rec, 2, MAX_LOSS_ABS, profile=X.knob_profile(0.90, 0.75, None))

    lenient = X.make_blockwise_replayer(lambda d: None, {}, X.DISABLED, **kw)
    assert lenient(rec, 2, MAX_LOSS_ABS,
                   profile=X.knob_profile(0.90, 0.75, None))["exit_reason"]


# ════════════════════════════════════════════════════════════════════════════
# Small helpers
# ════════════════════════════════════════════════════════════════════════════

def test_first_priced_at_or_after_skips_unpriced_days():
    t = _trade([1.00, None, None, 1.00] + [1.00] * 6)
    assert X.first_priced_at_or_after(t, 1) == 1
    assert X.first_priced_at_or_after(t, 2) == 4
    assert X.first_priced_at_or_after(t, 11) is None


def test_mark_pnl_at_uses_the_frozen_rounding():
    t = _trade([1.40, 0.3500] + [1.40] * 8, entry=1.40)
    assert X.mark_pnl_at(t, 2) == -0.75
    assert X.mark_pnl_at(t, 0) is None
    assert X.mark_pnl_at(t, 99) is None


def test_bar_coverage_reports_why_a_row_is_in_or_out():
    t = _trade(FLAT)
    cov = X.bar_coverage(t, _bars())
    assert cov["has_bars"] and cov["has_ohlc"]
    assert cov["entry_day"] == GRID[0]
    assert cov["atr14_pct"] == pytest.approx(0.02)
    assert X.bar_coverage(t, {})["has_bars"] is False


def test_overlay_reason_vocabulary_is_disjoint_from_the_harness():
    """An overlay exit must be identifiable from its reason alone, so none of
    the three may collide with one of `harness.replay`'s nine."""
    harness_reasons = {c["expect_exit_reason"] for c in CASES}
    assert len(harness_reasons) == 9
    assert set(X.OVERLAY_REASONS).isdisjoint(harness_reasons)
