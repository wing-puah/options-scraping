"""Unit tests for the `ladder_overlay` study,
`scripts/backtest_study/f3_structure/ladder_overlay.py`.

The registration (`research/pre-registrations/f3_structure/ladder_overlay.md`)
is binding: every cell, gate, census clause and verdict token in it must be
printed by the module under its registered label, and nothing may be added as a
criterion. What is pinned here is the part a report cannot show you —

  * the CELL TABLE: every registered label present exactly once, on its
    registered axes;
  * `L-BASE` is the book row replayed as-is, not a re-priced synthetic, so the
    baseline every ΔR is paired against cannot differ from itself;
  * the core-exit axis: X-SHIP vs X-TEF vs X-EXP as three values off ONE shipped
    profile;
  * the naked-put denominator: the CORE's max-loss dollars, never the put's own
    credit;
  * G0's refusal wording, G1b's identity in both directions (a match, and a
    forced mismatch that fails the run), and the `[MODEL]` tier's refusal to
    reach a criterion;
  * the AWAITING SCRAPE path off a manifest with a pending row;
  * the VERDICT GRAMMAR: every state maps to exactly one token and every token
    is reachable — no hole.

Everything is synthetic — a fake per-contract cache injected over
`bear_rewrap.leg_details` (the `tests/test_financed_spread_f4.py` /
`tests/test_overlay_campaign.py` pattern), fake OHLC bars, a stubbed
`ladder_targets` on the engine's `_LT` seam, and a hand-written manifest. No
network, no real option history, no `backtests/` reads.
"""
import csv
import itertools
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from scripts.backtest.legs import Leg
from scripts.backtest_study.f3_structure import bear_rewrap as BR
from scripts.backtest_study.f3_structure import financed_spread as FS
from scripts.backtest_study.f3_structure import ladder_overlay as LO
from scripts.backtest_study.lib import greeks as GK
from scripts.backtest_study.lib import overlay_campaign as OC
from scripts.backtest_study.lib.harness import Trade
from scripts.backtest_study.lib.underlying import Bar

TK = "AAA"
SIGNAL = date(2024, 6, 3)          # a Monday
FAR = date(2024, 8, 16)            # the core's expiry (a third Friday)
NEAR = date(2024, 6, 21)           # the first tranche's expiry
CORE_LEGS = [Leg(1, TK, FAR, 100.0, "Call"), Leg(-1, TK, FAR, 110.0, "Call")]
CORE_NET = 3.0


# ── fixtures ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FakeCore:
    """Duck-typed stand-in for `ladder_targets.CoreSpec`."""

    ticker: str
    expiry: date
    lo: float
    hi: float
    entry_day: date
    grid: tuple
    spot_entry: float | None = None


def _rows(marks: dict, iv="30.0"):
    return {d: {"_mark": m, "Open": "0", "IV": iv} for d, m in marks.items()}


@pytest.fixture()
def cache(monkeypatch):
    """A per-leg fake option cache keyed by contract identity."""
    store: dict[tuple, dict] = {}

    def put(leg, marks, iv="30.0"):
        store[(leg.ticker, leg.expiration, leg.strike, leg.opt_type)] = _rows(marks, iv)

    def leg_details(leg):
        return store.get((leg.ticker, leg.expiration, leg.strike, leg.opt_type), {})

    monkeypatch.setattr(BR, "leg_details", leg_details)
    put.store = store
    return put


class FakeLadderTargets:
    """The `ladder_targets` entry points the engine calls, on the `_LT` seam."""

    def __init__(self, calls=(115.0, 120.0, 125.0), puts=(95.0, 100.0, 105.0)):
        self.calls, self.puts = list(calls), list(puts)

    def eligible_expiries(self, day, remaining_dte, expiries):
        lo = day + timedelta(days=FS.DIAG_MIN_DAYS)
        hi = day + timedelta(days=int(remaining_dte * FS.DIAG_MAX_DTE_FRAC))
        return sorted(e for e in expiries if lo <= e <= hi)

    def cached_strikes(self, ticker, expiry, opt_type):
        return list(self.puts) if opt_type == "Put" else list(self.calls)

    def core_of(self, rec):
        return rec.get("_core")


@pytest.fixture()
def ladder(monkeypatch):
    """Both seams: the engine's `_LT`, and the name `raw_targets` swaps in for
    gate G1b (which deliberately reads the LIVE module, not the run's memo)."""
    stub = FakeLadderTargets()
    monkeypatch.setattr(OC, "_LT", stub)
    monkeypatch.setattr(LO, "LT", stub)
    return stub


@pytest.fixture()
def deltas(monkeypatch):
    """Per-strike per-contract |Delta|, signed short the way `leg_greek` does."""
    table = {115.0: 0.34, 120.0: 0.21, 125.0: 0.08,
             105.0: 0.42, 100.0: 0.29, 95.0: 0.11,
             110.0: 0.45}

    def leg_greek(leg, day, name):
        if leg.strike not in table:
            return None
        base = table[leg.strike] * abs(leg.qty)
        if name == "Delta":
            return -base if leg.qty < 0 else base
        return 0.05 * abs(leg.qty) * (-1 if leg.qty < 0 else 1)

    monkeypatch.setattr(GK, "leg_greek", leg_greek)
    return table


def _trade(marks: list[float], entry_net: float = CORE_NET, contracts: int = 2,
           legs=None) -> Trade:
    legs = legs or CORE_LEGS
    leg_str = "\n".join(
        f"{lg.ticker}:{lg.expiration.isoformat()}:{lg.strike:g}:"
        f"{'C' if lg.opt_type == 'Call' else 'P'} {lg.qty:+d}" for lg in legs)
    row = {
        "signal_date": SIGNAL.isoformat(), "ticker": TK,
        "structure": "bull_call_spread",
        "entry_option_price": f"{entry_net:.4f}", "contracts": str(contracts),
        "dte_entry": str((FAR - SIGNAL).days), "legs": leg_str,
        "daily_price_csv": ",".join(f"{m:.4f}" for m in marks),
    }
    return Trade(row)


def _grid_len() -> int:
    t = _trade([0.0])  # will raise on the assert; build the grid the long way
    return len(t.grid)


def _make_rec(marks=None):
    """A `load_book`-shaped record whose `t` walks the core's own weekday grid."""
    probe_legs = CORE_LEGS
    leg_str = "\n".join(
        f"{lg.ticker}:{lg.expiration.isoformat()}:{lg.strike:g}:C {lg.qty:+d}"
        for lg in probe_legs)
    # One throwaway Trade to learn the grid length, then the real one.
    from scripts.backtest.helpers import _weekday_grid
    end = SIGNAL + timedelta(days=min((FAR - SIGNAL).days, 120))
    grid = _weekday_grid(SIGNAL, end)
    marks = marks or [CORE_NET + 0.1 * i for i in range(len(grid))]
    row = {
        "signal_date": SIGNAL.isoformat(), "ticker": TK,
        "structure": "bull_call_spread",
        "entry_option_price": f"{CORE_NET:.4f}", "contracts": "2",
        "dte_entry": str((FAR - SIGNAL).days), "legs": leg_str,
        "daily_price_csv": ",".join(f"{m:.4f}" for m in marks),
    }
    t = Trade(row)
    rec = dict(date=SIGNAL.isoformat(), ticker=TK, structure="bull_call_spread",
               source="real", tier="A", mech_cell="PROD", mech_vol="L-VOL",
               model_vol="L-VOL", mfe=0.4, mae=-0.2, credit=False, t=t)
    rec["_core"] = FakeCore(ticker=TK, expiry=FAR, lo=100.0, hi=110.0,
                            entry_day=grid[0], grid=tuple(grid), spot_entry=101.0)
    return rec, rec["_core"], grid


def _price_core(cache, grid, values=None):
    """Price the core legs so their NET is `values[i]`: the long leg carries the
    whole net, the short leg is worth 0."""
    values = values or [CORE_NET + 0.1 * i for i in range(len(grid))]
    cache(CORE_LEGS[0], dict(zip(grid, values)))
    cache(CORE_LEGS[1], {d: 0.0 for d in grid})


def _bars(grid, closes=None):
    closes = closes or [101.0] * len(grid)
    return {d: Bar(c=c, o=c) for d, c in zip(grid, closes)}


def _base_row(rec, grid):
    out = FS.replay_at(rec["t"], LO.exit_profile(rec, rec["t"].entry_net, LO.X_SHIP),
                       rec["t"].contracts)
    return dict(date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
                source=rec["source"], tier=OC.CACHE_TIER, ladder_tier=rec["tier"],
                mech_cell=rec["mech_cell"], mech_vol=rec["mech_vol"],
                model_vol=rec["model_vol"], mfe=rec["mfe"], mae=rec["mae"],
                key=id(rec), core_dte=(FAR - grid[0]).days, **out)


def _build(rec, core, cell, grid, bars=None, expiries=(NEAR,)):
    return LO.build_cell_row(
        rec, core, cell, _base_row(rec, grid),
        GK.entry_greeks(list(rec["t"].legs), core.entry_day),
        list(expiries), bars or _bars(grid), 1, rec["t"].contracts, CORE_NET,
        Counter(), Counter(), 0.0, 0.0)


# ── the cell table ───────────────────────────────────────────────────────────

REGISTERED_PRIMARY = ("L-BASE", "L-F4", "L-T0", "L-GAP", "L-RUN",
                      "L-T0-TEF", "L-GAP-TEF", "L-RUN-TEF")
REGISTERED_NAKED = ("N-CORE", "N-ROLL")
REGISTERED_SENSITIVITY = ("S-D30", "S-BBUY", "S-BUP", "S-XEXP", "S-GAP103",
                          "S-DTE60", "S-MODEL x1.00", "S-MODEL x0.75",
                          "S-MODEL x1.25")


def test_every_registered_label_is_built_exactly_once():
    """The registration's three tables, transcribed. A label that is missing is
    a cell the study cannot report; a label built twice is a cell that would be
    counted twice in every census."""
    labels = [c.label for c in LO.CELLS]
    assert len(labels) == len(set(labels)), "a label is built twice"
    assert set(labels) == set(REGISTERED_PRIMARY + REGISTERED_NAKED
                              + REGISTERED_SENSITIVITY)
    by_group = {g: tuple(c.label for c in LO.CELLS if c.group == g)
                for g in (LO.PRIMARY, LO.NAKED, LO.SENSITIVITY)}
    assert by_group[LO.PRIMARY] == REGISTERED_PRIMARY
    assert by_group[LO.NAKED] == REGISTERED_NAKED
    assert set(by_group[LO.SENSITIVITY]) == set(REGISTERED_SENSITIVITY)


def test_the_primary_cells_carry_the_registered_axes():
    """|Δ| 0.20, BHOLD, Call on all eight; the trigger/roll/exit table verbatim."""
    want = {
        "L-BASE": (None, None, LO.X_SHIP),
        "L-F4": (OC.T0, OC.R0, LO.X_SHIP),
        "L-T0": (OC.T0, OC.R1, LO.X_SHIP),
        "L-GAP": (OC.TGAP, OC.R1, LO.X_SHIP),
        "L-RUN": (OC.TRUN, OC.R1, LO.X_SHIP),
        "L-T0-TEF": (OC.T0, OC.R1, LO.X_TEF),
        "L-GAP-TEF": (OC.TGAP, OC.R1, LO.X_TEF),
        "L-RUN-TEF": (OC.TRUN, OC.R1, LO.X_TEF),
    }
    for label, (trig, roll, exit_) in want.items():
        c = LO.CELL_BY_LABEL[label]
        assert c.exit == exit_, label
        if trig is None:
            assert c.spec is None, label
            continue
        assert (c.spec.trigger, c.spec.roll) == (trig, roll), label
        assert c.spec.breach == OC.BHOLD and c.spec.opt_type == OC.CALL, label
        assert c.spec.target == 0.20, label


def test_the_naked_and_sensitivity_cells_carry_the_registered_axes():
    n_core, n_roll = LO.CELL_BY_LABEL["N-CORE"], LO.CELL_BY_LABEL["N-ROLL"]
    assert n_core.replaces_core and n_core.fixed_put and n_core.spec.roll == OC.R0
    assert n_roll.replaces_core and not n_roll.fixed_put
    assert n_roll.spec.roll == OC.R1 and n_roll.spec.target == 0.30
    assert n_core.spec.opt_type == n_roll.spec.opt_type == OC.PUT

    assert LO.CELL_BY_LABEL["S-D30"].spec.target == 0.30
    assert LO.CELL_BY_LABEL["S-BBUY"].spec.breach == OC.BBUY
    assert LO.CELL_BY_LABEL["S-BUP"].spec.breach == OC.BUP
    assert LO.CELL_BY_LABEL["S-XEXP"].exit == LO.X_EXP
    assert LO.CELL_BY_LABEL["S-GAP103"].gap == 0.03
    assert LO.CELL_BY_LABEL["S-DTE60"].min_core_dte == 60
    scales = {LO.CELL_BY_LABEL[f"S-MODEL x{s}"].sigma_scale
              for s in ("1.00", "0.75", "1.25")}
    assert scales == {1.00, 0.75, 1.25}
    assert all(LO.CELL_BY_LABEL[f"S-MODEL x{s}"].is_model
               for s in ("1.00", "0.75", "1.25"))


def test_the_frozen_thresholds_are_the_registered_ones():
    """G0's floor, E3's floor, the gap sensitivity and the cost sensitivity may
    not be tuned after a number is seen."""
    assert (LO.MIN_ROWS, LO.MIN_DATES) == (60, 25)
    assert LO.MIN_SHARED_DATES == 8
    assert LO.SENS_GAP == 0.03 and LO.SENS_MIN_CORE_DTE == 60
    assert (LO.SENS_COMMISSION, LO.SENS_SLIPPAGE) == (0.65, 0.5)
    assert LO.G1B_TOL == 0.01


# ── L-BASE: the book row, not a re-priced synthetic ──────────────────────────

def test_l_base_is_the_book_row_replayed_not_a_rebuilt_synthetic(
        cache, ladder, deltas):
    """`L-BASE` is what every ΔR is paired against. Rebuilding it from re-priced
    marks would leave the baseline differing from ITSELF by the reconstruction
    tolerance, and every cell's ΔR would carry that difference."""
    rec, core, grid = _make_rec()
    _price_core(cache, grid)
    base = _base_row(rec, grid)
    row = _build(rec, core, LO.CELL_BY_LABEL["L-BASE"], grid)
    assert row is not None
    assert row["n_tranches"] == 0
    assert row["entry_net"] == pytest.approx(rec["t"].entry_net)
    assert row["R"] == pytest.approx(base["R"])
    assert row["R"] - row["base_R"] == pytest.approx(0.0)
    # with no tranche there is nothing to re-cost, so the stress series IS the
    # cell's own R — criterion 8 is a re-costing, never a different campaign.
    assert row["R_stress"] == pytest.approx(row["R"])


# ── the core-exit axis ───────────────────────────────────────────────────────

def test_x_ship_x_tef_x_exp_are_three_values_off_one_shipped_profile():
    rec, _core, _grid = _make_rec()
    ship = LO.exit_profile(rec, CORE_NET, LO.X_SHIP)
    tef = LO.exit_profile(rec, CORE_NET, LO.X_TEF)
    exp = LO.exit_profile(rec, CORE_NET, LO.X_EXP)

    shipped, sign = FS.profile_for(rec, CORE_NET)
    assert sign == "debit" and ship == shipped

    # X-TEF drops ONLY the profit target.
    assert tef["pt"] is None
    assert {k: v for k, v in tef.items() if k != "pt"} == \
           {k: v for k, v in ship.items() if k != "pt"}

    # X-EXP is dollar_stop and the path cap: nothing else survives.
    assert all(exp[k] is None for k in ("pt", "sl", "trig", "trail", "tef",
                                        "be_after"))
    # ... and the naked cells' "n/a — the put is the position" is the same shape.
    assert LO.exit_profile(rec, CORE_NET, LO.X_NONE) == exp


def test_x_tef_holds_past_a_profit_target_the_shipped_profile_would_take(
        cache, ladder, deltas):
    """The TEF cells answer "does holding the core longer beat taking the
    target". They can only answer it if the target is actually absent."""
    _n = len(_make_rec()[2])
    # a jump past the shipped profile's profit target on grid day 2
    rec, core, grid = _make_rec(
        marks=[CORE_NET if i < 2 else CORE_NET * 2.5 for i in range(_n)])
    _price_core(cache, grid, list(rec["t"].marks))
    ship = FS.replay_at(rec["t"], LO.exit_profile(rec, CORE_NET, LO.X_SHIP),
                        rec["t"].contracts)
    tef = FS.replay_at(rec["t"], LO.exit_profile(rec, CORE_NET, LO.X_TEF),
                       rec["t"].contracts)
    assert ship["exit_reason"] == "profit_target"
    assert tef["exit_reason"] != "profit_target"


# ── the naked-put denominator ────────────────────────────────────────────────

def test_the_naked_put_denominator_is_the_cores_max_loss_not_the_put_credit(
        cache, ladder, deltas):
    """The N cells REPLACE the core, so R is quoted on the CORE's max-loss
    dollars — the only denominator that keeps ΔR against the same L-BASE
    comparable. Sizing a naked short on the credit RECEIVED is the original
    oversizing bug and is never done here."""
    rec, core, grid = _make_rec()
    _price_core(cache, grid)
    put = Leg(-1, TK, FAR, 100.0, "Put")
    cache(put, {d: 1.2 - 0.1 * i for i, d in enumerate(grid)})

    row = _build(rec, core, LO.CELL_BY_LABEL["N-CORE"], grid)
    assert row is not None
    assert row["n_tranches"] == 1
    assert row["first_strike"] == core.lo and row["first_expiry"] == core.expiry
    # the core is a debit, so its structural max loss per unit IS the debit
    assert row["entry_net"] == pytest.approx(CORE_NET)
    assert row["entry_net"] != pytest.approx(row["credit_total"])
    # the put is left open at the end of the grid — its expiry IS the core's,
    # and the harness grid stops at min(core expiry, 120-day cap).
    assert row["open_at_grid_end"] == 1


def test_the_naked_put_cell_is_struck_at_the_cores_own_long_strike(
        cache, ladder, deltas):
    """N-CORE is not delta-picked: it is the put at the core's LONG strike and
    the core's OWN expiry, which is why it does not go through `sell_tranche`."""
    rec, core, grid = _make_rec()
    _price_core(cache, grid)
    cache(Leg(-1, TK, FAR, 100.0, "Put"), {d: 1.0 for d in grid})
    prices = OC.CachePrices()
    tr, why = LO.fixed_put_tranche(core, prices, _bars(grid), 1)
    assert why == "ok"
    assert (tr.leg.strike, tr.leg.expiration, tr.leg.opt_type) == \
           (core.lo, core.expiry, OC.PUT)
    assert tr.open_day == grid[0]


def test_a_put_close_through_the_strike_marks_the_tranche_breached(cache, ladder):
    rec, core, grid = _make_rec()
    cache(Leg(-1, TK, FAR, 100.0, "Put"), {d: 1.0 for d in grid})
    prices = OC.CachePrices()
    clear, _ = LO.fixed_put_tranche(core, prices, _bars(grid, [101.0] * len(grid)), 1)
    hit, _ = LO.fixed_put_tranche(
        core, prices, _bars(grid, [101.0] * (len(grid) - 1) + [99.0]), 1)
    assert clear.breached is False
    assert hit.breached is True


# ── G0 ───────────────────────────────────────────────────────────────────────

def _built(cells, rows_by_label, g1b=()):
    return dict(cells_active=tuple(cells), cells=dict(rows_by_label),
                census={c.label: Counter(candidates=1, built=1) for c in cells},
                tranche_census={}, baseline=[], g1=Counter(ok=1), g1b=list(g1b))


def test_g0_prints_the_floor_and_refuses_a_thin_cell_by_name(capsys):
    cell = LO.CELL_BY_LABEL["L-T0"]
    rows = [dict(date=f"2025-01-{i + 1:02d}") for i in range(4)]
    power = LO.gate_g0(_built([cell], {cell.label: rows}), set())
    out = capsys.readouterr().out
    assert power[cell.label] is False
    assert LO.UNDERPOWERED in out
    assert f"{LO.MIN_DATES}" in out and f"{LO.MIN_ROWS}" in out
    # the n is printed, not just the token
    assert "        4       4" in out


def test_g0_calls_an_awaiting_cell_awaiting_not_underpowered(capsys):
    cell = LO.CELL_BY_LABEL["L-T0"]
    LO.gate_g0(_built([cell], {cell.label: []}), {cell.label})
    out = capsys.readouterr().out
    assert LO.AWAITING in out
    assert "not in the cache yet" in out


# ── G1b — the F4 identity, both directions ───────────────────────────────────

@pytest.fixture()
def f4_world(cache, ladder, deltas, monkeypatch):
    """A core whose T0/R0 campaign and `financed_spread`'s F4-d20 `hold` build
    the SAME contract off the same fake cache."""
    rec, core, grid = _make_rec()
    _price_core(cache, grid)
    for k in (115.0, 120.0, 125.0):
        cache(Leg(-1, TK, NEAR, k, "Call"),
              {d: max(0.05, 0.80 - 0.05 * i) for i, d in enumerate(grid)})
    monkeypatch.setattr(FS, "cached_ticker_expiries", lambda tk: [NEAR, FAR])
    monkeypatch.setattr(FS, "cached_calls",
                        lambda tk, exp: [115.0, 120.0, 125.0] if exp == NEAR else [])
    return rec, core, grid


def test_g1b_matches_the_financed_spread_f4_series_to_the_cent(f4_world, capsys):
    rec, core, grid = f4_world
    got = LO.f4_identity_record(rec, core, [NEAR, FAR], _bars(grid), 1)
    assert got["status"] == "match", got
    assert got["max_diff"] <= LO.G1B_TOL
    assert got["n_days"] > 0
    assert LO.gate_g1b(_built([], {}, g1b=[got])) is True
    assert "G1b PASS" in capsys.readouterr().out


def test_g1b_fails_the_run_on_any_divergence_that_is_not_settle_intrinsic(
        f4_world, monkeypatch, capsys):
    """A mismatch is a BUILD BUG, never "a difference of method": the rolling
    engine is then not a demonstrated superset of the single-tranche one."""
    rec, core, grid = f4_world
    real = FS.f4_net_marks
    monkeypatch.setattr(FS, "f4_net_marks",
                        lambda *a, **k: [None if m is None else m + 0.5
                                         for m in real(*a, **k)])
    got = LO.f4_identity_record(rec, core, [NEAR, FAR], _bars(grid), 1)
    assert got["status"] == "mismatch"
    assert got["max_diff"] > LO.G1B_TOL
    assert LO.gate_g1b(_built([], {}, g1b=[got])) is False
    out = capsys.readouterr().out
    assert "G1b FAIL" in out
    assert "DIVERGENCES THAT ARE NOT settle_intrinsic" in out


def test_g1b_lists_a_settle_intrinsic_row_separately_and_still_passes(capsys):
    """The ONE construction under which the two may legitimately disagree: a
    breached tranche that stopped printing settles at intrinsic here and at the
    stale mark in F4, which has no breach concept. Listed, never averaged in."""
    rows = [dict(date="2025-01-02", ticker="AAA", status="match", n_days=10,
                 max_diff=0.0, settle_intrinsic=False),
            dict(date="2025-02-03", ticker="BBB", status="settle_intrinsic",
                 n_days=10, max_diff=4.25, settle_intrinsic=True)]
    assert LO.gate_g1b(_built([], {}, g1b=rows)) is True
    out = capsys.readouterr().out
    assert "listed, never averaged" in out
    assert "BBB" in out and "4.2500" in out
    assert "G1b PASS" in out


def test_the_g1b_failure_returns_the_gate_failed_exit_code():
    """A gate failure is a REAL failure and must NOT be reported as a designed
    refusal — `run.py` would then promote a broken report to `-latest.txt`."""
    assert LO.EXIT_GATE_FAILED == 1
    assert LO.EXIT_GATE_FAILED not in LO.DESIGNED_REFUSAL_EXIT_CODES


# ── the [MODEL] tier may never reach a criterion ─────────────────────────────

def _priced(label, n=80, r=0.4, tier=OC.CACHE_TIER):
    return [dict(date=f"2025-{1 + i % 12:02d}-{1 + i % 27:02d}", ticker="AAA",
                 source="real" if i % 2 else "tweak", tier=tier, cell=label,
                 R=r, R_dol=100.0, base_R=0.0, base_R_dol=0.0, R_stress=r,
                 fixed_R=r, fixed_R_dol=100.0)
            for i in range(n)]


def test_a_model_row_reaching_a_criterion_fails_the_run():
    """The `[MODEL]` tier is a SENSITIVITY, never evidence. A model row reaching
    a criterion is the same class of error as pooling two prompt versions."""
    rows = _priced("S-MODEL x1.00", tier=OC.MODEL_TIER)
    with pytest.raises(LO.ModelTierLeak):
        LO.evaluate(LO.CELL_BY_LABEL["S-MODEL x1.00"], rows, True, (None, 0),
                    False)


def test_an_untagged_row_is_refused_too():
    """An untagged row is indistinguishable from a model row that lost its
    label, so it is refused rather than assumed to be evidence."""
    rows = _priced("L-T0")
    for r in rows:
        r.pop("tier")
    with pytest.raises(LO.ModelTierLeak):
        LO.evaluate(LO.CELL_BY_LABEL["L-T0"], rows, True, (None, 0), False)


def test_cache_tier_rows_pass_the_guard_and_are_evaluated():
    verdict, checks = LO.evaluate(LO.CELL_BY_LABEL["L-T0"], _priced("L-T0"),
                                  True, (None, 0), False)
    assert verdict in LO.VERDICTS
    assert [c[0][0] for c in checks] == list("12345678")


def test_the_model_cells_are_sensitivity_and_never_earn_a_verdict(capsys):
    cells = [LO.CELL_BY_LABEL[f"S-MODEL x{s}"] for s in ("1.00", "0.75", "1.25")]
    built = _built(cells, {c.label: _priced(c.label, tier=OC.MODEL_TIER)
                           for c in cells})
    verdicts = LO.report_criteria(built, {c.label: True for c in cells}, {}, set())
    assert verdicts == {}
    assert "SENSITIVITY, no verdict" in capsys.readouterr().out


# ── AWAITING SCRAPE ──────────────────────────────────────────────────────────

def _manifest(tmp_path, rows):
    p = tmp_path / "ladder_manifest.csv"
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=("ticker", "expiration", "strike",
                                           "opt_type", "category", "status",
                                           "fetched_at", "reason"))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def _mrow(cat, status):
    return dict(ticker="AAA", expiration="2024-06-21", strike="120",
                opt_type="C", category=cat, status=status, fetched_at="",
                reason="")


def test_a_pending_manifest_row_puts_every_cell_that_needs_it_awaiting(tmp_path):
    p = _manifest(tmp_path, [_mrow("ladder_call_t0", "pending"),
                             _mrow("ladder_call_roll", "fetched"),
                             _mrow("ladder_put_core", "fetched"),
                             _mrow("ladder_put_short", "fetched")])
    census = LO.manifest_census(p)
    assert LO.pending_categories(census) == {"ladder_call_t0"}
    awaiting = LO.awaiting_cells(census)
    assert "L-BASE" not in awaiting          # needs nothing fetched
    assert {"L-F4", "L-T0", "L-GAP", "L-RUN", "S-D30"} <= awaiting
    assert "N-CORE" not in awaiting and "N-ROLL" not in awaiting


def test_a_fully_fetched_manifest_leaves_nothing_awaiting(tmp_path):
    p = _manifest(tmp_path, [_mrow(c, "fetched") for c in LO.CATEGORIES])
    assert LO.pending_categories(LO.manifest_census(p)) == set()
    assert LO.awaiting_cells(LO.manifest_census(p)) == set()


def test_a_missing_manifest_means_every_category_is_pending(tmp_path):
    census = LO.manifest_census(tmp_path / "nope.csv")
    assert census["exists"] is False
    assert LO.pending_categories(census) == set(LO.CATEGORIES)


def test_an_awaiting_cell_evaluates_no_criterion_and_is_not_a_null():
    verdict, checks = LO.evaluate(LO.CELL_BY_LABEL["L-T0"], _priced("L-T0"),
                                  True, (0.5, 30), True)
    assert verdict == LO.AWAITING
    assert checks == []


def test_the_awaiting_census_prints_targets_cached_and_pending(tmp_path, capsys):
    p = _manifest(tmp_path, [_mrow("ladder_call_t0", "pending"),
                             _mrow("ladder_call_t0", "fetched"),
                             _mrow("ladder_put_short", "failed")])
    census = LO.manifest_census(p)
    LO.report_scrape(census, LO.awaiting_cells(census))
    out = capsys.readouterr().out
    for cat in LO.CATEGORIES:
        assert cat in out
    assert "targets" in out and "fetched" in out and "pending" in out
    assert LO.AWAITING in out


def test_awaiting_scrape_exits_clean_and_era_refusals_stay_literal():
    """AWAITING SCRAPE exits 0 — the registration says so and financed_spread
    does the same — so `run.py` promotes the census report to `-latest.txt` as a
    clean run. `DESIGNED_REFUSAL_EXIT_CODES` still covers `load_book`'s era
    refusals and must stay a literal set: `run.py` reads it by AST parse, and an
    alias or a `frozenset(...)` call is invisible to it."""
    assert LO.EXIT_AWAITING_SCRAPE == 0
    assert LO.EXIT_GATE_FAILED not in LO.DESIGNED_REFUSAL_EXIT_CODES
    src = (LO.ROOT / "scripts" / "backtest_study" / "f3_structure"
           / "ladder_overlay.py").read_text()
    assert "\nDESIGNED_REFUSAL_EXIT_CODES = {2, 3}\n" in src


# ── the verdict grammar ──────────────────────────────────────────────────────

def test_every_verdict_token_is_reachable_and_no_state_has_none():
    """The grammar is TOTAL: every combination of the eight clauses, the power
    floor and E3's evaluability maps to exactly one registered token, and every
    registered token is produced by some combination. A hole here is a cell that
    would print no verdict — which the registration forbids ("every PRIMARY and
    naked-put cell is reported with its n and a verdict token regardless of
    outcome")."""
    seen = set()
    tri = (True, False, None)
    for awaiting, powered_ok, has_pairs in itertools.product((True, False),
                                                             repeat=3):
        for gates in itertools.product((True, False), repeat=6):
            for c7, c8 in itertools.product(tri, tri):
                v = LO.verdict_of(awaiting=awaiting, powered_ok=powered_ok,
                                  has_pairs=has_pairs, r_gates=list(gates),
                                  c7=c7, c8=c8)
                assert v in LO.VERDICTS, (awaiting, powered_ok, gates, c7, c8)
                seen.add(v)
    assert seen == set(LO.VERDICTS), f"unreachable: {set(LO.VERDICTS) - seen}"


def test_the_grammar_reads_each_token_the_way_the_registration_words_it():
    all_pass = [True] * 6
    kw = dict(awaiting=False, powered_ok=True, has_pairs=True)
    assert LO.verdict_of(r_gates=all_pass, c7=True, c8=True, **kw) == "CANDIDATE"
    assert LO.verdict_of(r_gates=all_pass, c7=False, c8=True, **kw) == "RE-WRAP"
    assert LO.verdict_of(r_gates=all_pass, c7=True, c8=False, **kw) == \
        "BREACH-DOMINATED"
    # E3 NOT EVALUABLE can never be a CANDIDATE.
    assert LO.verdict_of(r_gates=all_pass, c7=None, c8=True, **kw) == "NULL"
    # 1-6 pass, 7 fails, 8 fails is neither RE-WRAP (8 is part of that token)
    # nor BREACH-DOMINATED (1-7 are part of that one).
    assert LO.verdict_of(r_gates=all_pass, c7=False, c8=False, **kw) == "NULL"
    # a failed R gate is a NULL whatever E3 says ...
    assert LO.verdict_of(r_gates=[True] * 5 + [False], c7=True, c8=True,
                         **kw) == "NULL"
    # ... and the power floor and the scrape outrank everything.
    assert LO.verdict_of(r_gates=all_pass, c7=True, c8=True, awaiting=False,
                         powered_ok=False, has_pairs=True) == LO.UNDERPOWERED
    assert LO.verdict_of(r_gates=all_pass, c7=True, c8=True, awaiting=True,
                         powered_ok=True, has_pairs=True) == LO.AWAITING


def test_breach_dominated_is_never_softened_into_candidate():
    """Criterion 8 flipping the sign is its own recorded outcome."""
    rows = _priced("L-T0", r=0.4)
    for r in rows:
        r["R_stress"] = -0.4              # intrinsic on every breached tranche
    verdict, checks = LO.evaluate(LO.CELL_BY_LABEL["L-T0"], rows, True,
                                  (-0.2, 30), False)
    names = {c[0]: c[1] for c in checks}
    assert names["8 right-signed under breach-stress"] is False
    assert verdict == "BREACH-DOMINATED"


def test_a_positive_sleeve_correlation_is_a_re_wrap_whatever_the_delta_r():
    rows = _priced("L-T0", r=0.4)
    verdict, _ = LO.evaluate(LO.CELL_BY_LABEL["L-T0"], rows, True, (+0.61, 30),
                             False)
    assert verdict == "RE-WRAP"


# ── criterion 8 is a re-costing, not a different campaign ────────────────────

def test_breach_stress_recosts_only_breached_tranches_at_intrinsic(cache, ladder):
    rec, core, grid = _make_rec()
    leg = Leg(-1, TK, NEAR, 120.0, "Call")
    clean = OC.Tranche(leg=leg, open_day=grid[0], credit=0.80,
                       close_day=grid[3], close_cost=0.30,
                       close_reason=OC.SETTLE_MARK)
    hit = OC.Tranche(leg=leg, open_day=grid[0], credit=0.80, close_day=grid[3],
                     close_cost=0.30, close_reason=OC.SETTLE_MARK, breached=True)
    bars = _bars(grid, [130.0] * len(grid))
    out = LO.stress_tranches([clean, hit], bars, list(grid))
    assert out[0] is clean                                   # untouched
    assert out[1].close_cost == pytest.approx(130.0 - 120.0)  # intrinsic


def test_breach_stress_closes_a_breached_tranche_left_open_at_the_grid_end(
        cache, ladder):
    """Leaving it marked is exactly the forgiveness clause 8 exists to remove."""
    rec, core, grid = _make_rec()
    leg = Leg(-1, TK, FAR, 105.0, "Call")
    live = OC.Tranche(leg=leg, open_day=grid[0], credit=1.0,
                      close_reason=OC.OPEN_AT_GRID_END, breached=True)
    out = LO.stress_tranches([live], _bars(grid, [120.0] * len(grid)), list(grid))
    assert out[0].close_day == grid[-1]
    assert out[0].close_cost == pytest.approx(15.0)


# ── the CSV ──────────────────────────────────────────────────────────────────

def test_the_rows_csv_separates_the_pricing_tier_from_the_ladder_tier(tmp_path):
    """`tier` is what `assert_not_model` reads and must be cache/model; the
    book's A/B/C ladder tier rides along under its own name so the two can never
    be confused by a reader or a chart layer."""
    cell = LO.CELL_BY_LABEL["L-T0"]
    rows = [dict(_priced("L-T0", n=1)[0], ladder_tier="A")]
    path, n = LO.write_rows_csv(_built([cell], {cell.label: rows}),
                                tmp_path / "rows.csv")
    assert n == 1
    got = list(csv.DictReader(path.open()))[0]
    assert got["tier"] == OC.CACHE_TIER
    assert got["ladder_tier"] == "A"
    assert "tier" in LO.CSV_COLUMNS and "ladder_tier" in LO.CSV_COLUMNS


# ── the S-GAP103 threshold swap leaves no trace ──────────────────────────────

def test_the_gap_sensitivity_restores_the_primary_threshold(cache, ladder):
    primary = OC.TGAP_MIN_GAP
    with LO.gap_threshold(LO.SENS_GAP):
        assert OC.TGAP_MIN_GAP == LO.SENS_GAP
    assert OC.TGAP_MIN_GAP == primary
    try:
        with LO.gap_threshold(LO.SENS_GAP):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert OC.TGAP_MIN_GAP == primary, "a sensitivity left a trace on the primary"


def test_the_memo_delegates_everything_it_does_not_cache():
    from scripts.backtest_study.lib import ladder_targets as LT
    memo = LO._MemoTargets(LT)
    assert memo.core_of is LT.core_of
    assert memo.eligible_expiries is LT.eligible_expiries
    calls = []

    class _Stub:
        def cached_strikes(self, ticker, expiry, opt_type):
            calls.append((ticker, expiry, opt_type))
            return [1.0]

    memo = LO._MemoTargets(_Stub())
    assert memo.cached_strikes("AAA", FAR, "Call") == [1.0]
    assert memo.cached_strikes("AAA", FAR, "Call") == [1.0]
    assert len(calls) == 1
