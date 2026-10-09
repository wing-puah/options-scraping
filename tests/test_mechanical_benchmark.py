"""mechanical_benchmark's geometry rules, on synthetic chains.

research/pre-registrations/f1_selection/mechanical_benchmark.md, Build notes:
band matching, degenerate-pair rejection, entry-dated-only selection and the
paired-drop symmetry. No test reads the real exports or the option cache.
"""
from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.backtest_study.f1_selection import mechanical_benchmark as MB
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF

T = "AAA"
EXP = date(2026, 3, 20)
SIG = date(2026, 1, 5)


def chain_of(quotes: dict[float, dict[date, tuple]], ticker=T, expiry=EXP) -> NTF.Chain:
    """A Chain whose calls at `expiry` carry `{strike: {day: (mark, spot, delta)}}`."""
    idx = {(ticker, expiry): {float(k): {"C"} for k in quotes}}
    ch = NTF.Chain(idx=idx)
    for k, days in quotes.items():
        series = sorted((d, m) for d, (m, _s, _dl) in days.items())
        details = {d: {"_mark": m, "Price~": str(s), "Delta": "" if dl is None else str(dl)}
                   for d, (m, s, dl) in days.items()}
        ch._memo[(ticker, expiry, round(float(k), 4), "Call")] = (series, details)
    return ch


# ── bands ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dte,band", [
    (6, None), (7, (7, 21)), (20, (7, 21)), (21, (21, 45)), (44, (21, 45)),
    (45, (45, 90)), (89, (45, 90)), (90, (90, 180)), (179, (90, 180)),
    (180, None), (700, None), (None, None), ("x", None),
])
def test_band_of(dte, band):
    assert MB.band_of(dte) == band


def test_slot_out_of_scope_drops(monkeypatch):
    class _T:
        def __init__(self, dte):
            from scripts.backtest.legs import Leg
            self.legs = [Leg(1, T, EXP, 100.0, "Call"), Leg(-1, T, EXP, 105.0, "Call")]
            self.row = {"dte_entry": str(dte)}
            self.ticker = T
            self.signal_date = SIG
    for dte, why in ((200, "dte_ge_180"), (5, "dte_lt_7"), (60, "")):
        rec = {"t": _T(dte), "date": SIG.isoformat(), "tier": "A",
               "structure": "bull_call_spread"}
        assert MB.slot_of(rec).drop == why


def test_slot_not_a_vertical():
    from scripts.backtest.legs import Leg

    class _T:
        legs = [Leg(1, T, EXP, 100.0, "Call"), Leg(-1, T, EXP + timedelta(days=7), 105.0, "Call")]
        row = {"dte_entry": "60"}
        ticker = T
        signal_date = SIG
    rec = {"t": _T(), "date": SIG.isoformat(), "tier": "B", "structure": "x"}
    assert MB.slot_of(rec).drop == "not_a_vertical"


# ── geometry ─────────────────────────────────────────────────────────────────

def test_grid_around_nearest_first_ties_lower():
    pts = MB.grid_around(102.5, 5.0, [])
    assert pts[:2] == [100.0, 105.0]          # equidistant: the lower strike first
    assert MB.grid_around(101.0, 1.0, [100.5])[0] == 101.0


def test_degenerate_pairs():
    assert MB.is_degenerate(100.0, 100.0)
    assert MB.is_degenerate(105.0, 100.0)
    assert MB.is_degenerate(None, 105.0)
    assert not MB.is_degenerate(100.0, 105.0)


def test_select_m1_degenerate_is_dropped_not_widened():
    # Only one listed strike near spot 10; every other grid strike is
    # evidenced unlisted, so both targets land on it.
    days = {SIG: (1.0, 10.0, 0.5)}
    ch = chain_of({10.0: days})
    near = set(MB.grid_around(10.0, 0.5, [10.0])) | set(MB.grid_around(10.5, 0.5, [10.0]))
    ev = {NTF.contract_stem(T, EXP, k, "Call") for k in near if k != 10.0}
    w = MB.select_m1(ch, ev, T, EXP, 10.0, SIG)
    assert w.status == "drop" and w.reason == "degenerate"


def test_monthly_expiries_holiday_thursday():
    assert MB.good_friday(2025) == date(2025, 4, 18)
    assert date(2025, 4, 17) in MB.monthly_expiries(date(2025, 4, 1), date(2025, 4, 30))
    assert MB.monthly_expiries(date(2026, 6, 1), date(2026, 6, 30)) == [date(2026, 6, 18)]
    assert MB.monthly_expiries(date(2026, 1, 1), date(2026, 1, 31)) == [date(2026, 1, 16)]


def test_monthly_for_stays_in_band():
    entry = date(2026, 1, 12)
    e = MB.monthly_for(entry, 40, (21, 45))
    assert e == date(2026, 2, 20) and 21 <= (e - entry).days < 45
    assert MB.monthly_for(date(2026, 1, 6), 40, (21, 45)) is None   # Feb 20 is day 45
    assert MB.monthly_for(date(2026, 1, 6), 10, (7, 21)) == date(2026, 1, 16)
    # a band with no monthly expiry inside it gives none
    assert MB.monthly_for(date(2026, 1, 17), 8, (7, 9)) is None


# ── listing and entry-dated selection ───────────────────────────────────────

def test_nearest_listed_skips_evidence_and_unlisted_and_awaits_uncached():
    before = SIG - timedelta(days=3)
    after = SIG + timedelta(days=3)
    ch = chain_of({100.0: {before: (5.0, 100.0, 0.5)},
                   101.0: {after: (4.0, 100.0, 0.45)}})
    # 100 is listed before the signal: chosen at target 100
    assert MB.nearest_listed(ch, set(), T, EXP, 100.0, 100.0, SIG).strike == 100.0
    # target 101: 101 is cached but first quoted AFTER the signal -> not listed;
    # 102 is the next nearest, uncached and un-evidenced -> await it
    s = MB.nearest_listed(ch, set(), T, EXP, 101.2, 100.0, SIG)
    assert s.status == "await" and s.fetch == (102.0,)
    # with 102 evidenced unlisted, the walk steps on to 100
    ev = {NTF.contract_stem(T, EXP, 102.0, "Call")}
    assert MB.nearest_listed(ch, ev, T, EXP, 101.2, 100.0, SIG).strike == 100.0


def test_selection_reads_nothing_after_the_signal():
    """G2's property: the choice on a cache cut at the signal date is identical."""
    pre = SIG - timedelta(days=1)
    post = SIG + timedelta(days=10)
    q = {k: {pre: (1.0, 100.0, d), post: (2.0, 120.0, d - 0.2)}
         for k, d in ((95.0, 0.7), (100.0, 0.5), (105.0, 0.3), (110.0, 0.15))}
    q[115.0] = {post: (1.0, 120.0, 0.4)}       # listed only after the signal
    ch = chain_of(q)
    ev = {NTF.contract_stem(T, EXP, k, "Call") for k in (90.0, 120.0, 85.0, 125.0)}
    cut = MB.AsOfChain(ch, SIG)
    for fn in (lambda c: MB.select_m1(c, ev, T, EXP, 100.0, SIG),
               lambda c: MB.select_m2(c, ev, T, EXP, 100.0, 0.5, pre)):
        a, b = fn(ch), fn(cut)
        assert (a.status, a.k_long, a.k_short) == (b.status, b.k_long, b.k_short)
    assert MB.spot_on(cut, [MB.call_leg(T, EXP, 100.0)], post) is None


def test_nearest_delta_proven_and_awaiting():
    d0 = SIG
    q = {100.0: {d0: (5.0, 100.0, 0.52)}, 105.0: {d0: (3.0, 100.0, 0.35)}}
    ch = chain_of(q)
    # target 0.40: nearest known is 105 (0.35); delta must rise -> walk DOWN,
    # 102.5 is an uncached grid strike between 105 and 100 -> await
    s = MB.nearest_delta(ch, set(), T, EXP, 0.40, 100.0, d0)
    assert s.status == "await" and s.fetch == (102.5,)
    ev = {NTF.contract_stem(T, EXP, 102.5, "Call")}
    s = MB.nearest_delta(ch, ev, T, EXP, 0.40, 100.0, d0)
    assert s.status == "built" and s.strike == 105.0


def test_net_and_bought_delta_targets():
    from scripts.backtest.legs import Leg
    q = {100.0: {SIG: (5.0, 100.0, 0.55)}, 110.0: {SIG: (2.0, 100.0, 0.25)}}
    ch = chain_of(q)
    legs = [Leg(1, T, EXP, 100.0, "Call"), Leg(-1, T, EXP, 110.0, "Call")]
    assert MB.net_delta_target(ch, legs, SIG) == pytest.approx(0.30)
    assert MB.bought_delta_target(ch, legs, SIG) == pytest.approx(0.55)
    assert MB.net_delta_target(ch, legs, SIG + timedelta(days=1)) is None


# ── paired-drop symmetry ─────────────────────────────────────────────────────

def _slot(d, drop="", tier="A"):
    return MB.Slot(rec={"t": None, "mech_cell": "PROD"}, date=d, ticker=T, tier=tier,
                   structure="bull_call_spread", band=(45, 90), expiry=EXP,
                   signal=SIG, entry_day=SIG + timedelta(days=1), dte=60, drop=drop)


def test_a_dropped_pair_leaves_every_arm():
    slots = [_slot("2026-01-05"), _slot("2026-01-06", drop="dte_ge_180")]
    m = {a: [MB.Wrap("await", "x"), MB.Wrap("drop", "dte_ge_180")] for a in MB.ARMS_M}
    b = MB.EraBuild("t", slots, m, [], {}, {}, "")
    assert MB.g4_pairing(b) == []
    for a in MB.ARMS_M:
        assert MB.pair_rows(b, a, "headline") == []      # nothing built, nothing paired
    b.m["M1"] = b.m["M1"][:1]
    assert MB.g4_pairing(b)


def test_floor2_ignores_scope_drops_and_awaiting():
    slots = [_slot("d1", tier="A"), _slot("d2", drop="dte_ge_180", tier="A"),
             _slot("d3", tier="B"), _slot("d4", tier="B")]
    wraps = [MB.Wrap("drop", "no_listed_strike"), MB.Wrap("drop", "dte_ge_180"),
             MB.Wrap("built"), MB.Wrap("await")]
    assert MB.tier_unbuildable(slots, wraps) == {"A": (1, 1), "B": (0, 1)}
    assert MB.tier_gap(MB.tier_unbuildable(slots, wraps)) == 1.0


def test_fetch_targets_dedup():
    w = MB.Wrap("await", "x", fetch=((T, EXP, 100.0), (T, EXP, 105.0)))
    b = MB.EraBuild("current", [_slot("d")], {"M1": [w], "M2": [w], "M2L": []},
                    [], {("d", "BBB", EXP): MB.Wrap("await", "y", fetch=(("BBB", EXP, 50.0),))},
                    {}, "")
    tg = MB.fetch_targets([b])
    assert [(t["ticker"], t["strike"], t["category"]) for t in tg] == [
        ("AAA", 100.0, "M1:current"), ("AAA", 105.0, "M1:current"),
        ("BBB", 50.0, "U:current")]


# ── verdicts, seal, statistics ───────────────────────────────────────────────

def test_verdict_precedence():
    under = {"c0": False}
    ok2 = {"c0": True, "c1": True, "c2": True}
    ok3 = {"c0": True, "c1": True, "c2": True, "c3": True, "c4": True}
    null = {"c0": True, "c1": False}
    assert MB.verdict(under, under, under, False) == "UNDERPOWERED"
    assert MB.verdict(ok2, null, null, False) == "STRUCTURE-ONLY"
    assert MB.verdict(null, null, ok3, False) == "BASE-RATE"
    assert MB.verdict(null, null, ok3, True) == "SELECTION-CONFIRMED"
    assert MB.verdict(null, null, null, False) == "NULL"
    assert MB.verdict({"c0": True, "c1": False, "contrary": True}, null, null,
                      False) == "CONTRARY"
    assert MB.verdict({"c0": True, "c1": True, "c2": False}, null, null,
                      False) == "UNWORDED"


def test_seal_withholds_sealed_dates():
    recs = [{"date": "2026-09-22"}, {"date": "2026-09-23"}, {"date": "2026-10-08"}]
    kept, line = MB.apply_seal(recs)
    assert [r["date"] for r in kept] == ["2026-09-22"]
    assert "withheld 2 rows" in line


def test_counterpart_is_one_lot_and_profiles():
    assert MB.profile_for({"credit": True}, "headline") == MB.DEBIT_PROD
    assert MB.profile_for({"credit": True}, "own") == MB.CREDIT_PROD
    assert MB.profile_for({"credit": False, "mech_cell": "BEAR_HE"}, "own") == MB.BEAR_HE_PROD
    assert MB.BEAR_HE_PROD["trail"] == 0.50 and MB.BEAR_HE_PROD["trig"] == 0.50


def test_u_band_is_seeded():
    rows = [{"date": "d"}] * 3
    pools = {0: [0.1, -0.2], 1: [0.3], 2: [0.0, 0.5, -0.5]}
    a = MB.u_band(rows, pools, draws=200)
    b = MB.u_band(rows, pools, draws=200)
    assert a[:2] == b[:2] and a[0] <= a[1]


def test_no_forbidden_statistic_and_no_raw_export_read():
    src = Path(MB.__file__).read_text()
    names = {n.id.lower() for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Name)} | \
        {n.name.lower() for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef)}
    for word in ("sharpe", "annualis", "annualiz", "recover"):
        assert not [n for n in names if word in n], word
    src = src.lower()
    # the book comes only through load_book, so the seal applies to it
    for word in ("resolve_paths(", "default_results_csv", "eval_dir"):
        assert word not in src, word


def test_registered_constants():
    assert MB.BANDS == ((7, 21), (21, 45), (45, 90), (90, 180))
    assert (MB.LONG_MULT, MB.SHORT_MULT, MB.K_DEPLOY) == (1.00, 1.05, 3)
    assert MB.U_DRAWS >= 1000 and MB.U_REDRAW_CAP == 0.25
    assert (MB.C0_MIN_DATES, MB.C0_MIN_PAIRS) == (25, 40)
