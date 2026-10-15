"""mechanical_benchmark's geometry rules, on synthetic chains.

research/pre-registrations/f1_selection/benchmark/mechanical_benchmark.md, Build notes:
band matching, degenerate-pair rejection, entry-dated-only selection and the
paired-drop symmetry. No test reads the real exports or the option cache.
"""
from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB
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


# ── fetch order cannot change a build (Resolved at build 2026-10-13) ────────

def _bs_delta(k: float, spot=100.0, sig=0.30, days=74) -> float:
    import math
    from statistics import NormalDist
    st = sig * math.sqrt(days / 365.0)
    return NormalDist().cdf((math.log(spot / k) + st * st / 2) / st)


def _old_delta_fetch(chain, evidence, ticker, expiry, target, spot, kstar, known,
                     walk, asof):
    """The pre-2026-10-13 choice: the open strike next to k*."""
    return next((k,) for k in walk if MB._open(chain, evidence, ticker, expiry, k))


def _run_fetch_loop(monkeypatch, target, old: bool):
    """Alternate select_m2 and a synthetic fetch until nothing awaits.

    World: strikes on the 2.5 grid are listed with a Black-Scholes delta;
    every other strike 404s (evidence). The cache starts with 100 and 101,
    so the walk steps at 1.0 and most of its probes are off the grid.
    Returns (final wrap, rounds, requests, the wrap at every round)."""
    if old:
        monkeypatch.setattr(MB, "delta_fetch", _old_delta_fetch)
        monkeypatch.setattr(MB, "listed_fetch", lambda *a: a[-1])
    else:
        monkeypatch.undo()

    def quote(k):
        return {SIG: (1.0, 100.0, _bs_delta(k))}
    ch = chain_of({100.0: quote(100.0), 101.0: quote(101.0)})
    for k in (100.0, 101.0):
        ch._memo[(T, EXP, k, "Call")][1][SIG]["IV"] = "30.0"
    ev: set[str] = set()
    seen, rounds, reqs = [], 0, 0
    while True:
        w = MB.select_m2(ch, ev, T, EXP, 100.0, target, SIG)
        seen.append(w)
        if w.status != "await":
            return w, rounds, reqs, seen, ch, ev
        rounds += 1
        reqs += len(w.fetch)
        assert rounds < 200
        for _tk, _exp, k in w.fetch:
            if abs(k / 2.5 - round(k / 2.5)) < 1e-9:
                ch.idx[(T, EXP)][float(k)] = {"C"}
                ch._memo[(T, EXP, round(k, 4), "Call")] = (
                    [(SIG, 1.0)], {SIG: {"_mark": 1.0, "Price~": "100.0",
                                         "Delta": str(_bs_delta(k)), "IV": "30.0"}})
            else:
                ev.add(NTF.contract_stem(T, EXP, k, "Call"))


@pytest.mark.parametrize("target", [0.15, 0.22, 0.31, 0.45, 0.62, 0.80])
def test_fetch_order_cannot_change_a_build(monkeypatch, target):
    """Old and new fetch orders end in the SAME built pair, and on every cache
    state the new order passes through, the old choice builds the same thing:
    the target choice reads into `fetch` and nothing else."""
    w_old, r_old, _q, _s, _c, _e = _run_fetch_loop(monkeypatch, target, old=True)
    w_new, r_new, _q, seen, _c, _e = _run_fetch_loop(monkeypatch, target, old=False)
    assert w_new.status == "built"
    assert (w_old.status, w_old.k_long, w_old.k_short) == \
        (w_new.status, w_new.k_long, w_new.k_short)
    assert r_new <= r_old
    # Replay the new run's intermediate caches under the old choice.
    monkeypatch.undo()
    _w, _r, _q, _s, ch, ev = _run_fetch_loop(monkeypatch, target, old=False)
    monkeypatch.setattr(MB, "delta_fetch", _old_delta_fetch)
    monkeypatch.setattr(MB, "listed_fetch", lambda *a: a[-1])
    again = MB.select_m2(ch, ev, T, EXP, 100.0, target, SIG)
    assert (again.status, again.reason, again.k_long, again.k_short) == \
        (w_new.status, w_new.reason, w_new.k_long, w_new.k_short)


def test_fetch_order_only_touches_fetch(monkeypatch):
    """On a cache where a pair awaits, old and new choices agree on status,
    reason and strikes; only the named strikes differ."""
    def quote(k):
        return {SIG: (1.0, 100.0, _bs_delta(k))}
    ch = chain_of({100.0: quote(100.0), 101.0: quote(101.0)})
    for k in (100.0, 101.0):
        ch._memo[(T, EXP, k, "Call")][1][SIG]["IV"] = "30.0"
    new = MB.select_m2(ch, set(), T, EXP, 100.0, 0.22, SIG)
    monkeypatch.setattr(MB, "delta_fetch", _old_delta_fetch)
    old = MB.select_m2(ch, set(), T, EXP, 100.0, 0.22, SIG)
    assert old.fetch == ((T, EXP, 102.0),)
    assert (new.status, new.reason, new.k_long, new.k_short) == \
        (old.status, old.reason, old.k_long, old.k_short)
    # the new choice jumps toward the Black-Scholes strike for delta 0.22,
    # (~112) on the standard 2.5 grid
    assert all(k >= 110 and abs(k / 2.5 - round(k / 2.5)) < 1e-9 for _t, _e, k in new.fetch)


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


# ── floors by arm (Resolved at build 2026-10-13) ─────────────────────────────

def _census(m1_await=0, m2_await=0, f2=None, share=0.02, share_bound=0.90, u_await=500):
    from collections import Counter
    m1 = dict(status=Counter({"built": 60, "await": m1_await, "drop": 4}), f1_now=30,
              f1_bound=30, f1_full_now=20, f1_literal=0,
              f2=f2 or {"A": (2, 30), "B": (2, 30)}, bands=Counter({"45-90": 60}))
    m2 = dict(status=Counter({"built": 60, "await": m2_await, "drop": 4}))
    return {"arms": {"M1": m1, "M2": m2},
            "u": dict(median_share=share, median_share_bound=share_bound,
                      wraps=Counter({"built": 10, "await": u_await}),
                      dates_no_universe=[])}


def test_u_awaiting_reads_the_same_ticker_arms():
    same, full, lines = MB.floors(_census(), n_fetch=900)
    assert (same, full) == ("PASS", "AWAITING")
    assert MB.study_word(same, full) == MB.SAME_TICKER_READ
    text = "\n".join(lines)
    assert "[gates ARM U and the study verdict]" in [ln for ln in lines if ln.startswith("  3")][0]
    assert "[gates M1 M2 M2L]" in [ln for ln in lines if ln.startswith("  4a")][0]
    assert "[gates ARM U and the study verdict]" in [ln for ln in lines if ln.startswith("  4b")][0]
    assert "[gates every arm]" in text


def test_floor3_fail_holds_back_only_arm_u():
    same, full, _ = MB.floors(_census(share_bound=0.10), n_fetch=0)
    assert (same, full) == ("PASS", "FAIL")
    assert MB.study_word(same, full) == MB.SAME_TICKER_READ


@pytest.mark.parametrize("m1_await,m2_await", [(3, 0), (0, 2)])
def test_m1_m2_awaiting_is_still_awaiting_scrape(m1_await, m2_await):
    same, full, _ = MB.floors(_census(m1_await=m1_await, m2_await=m2_await), n_fetch=5)
    assert same == "AWAITING"
    assert MB.study_word(same, full) == "NOT BUILT — AWAITING SCRAPE"


def test_floor2_fail_kills_every_arm():
    same, full, _ = MB.floors(_census(f2={"A": (0, 30), "B": (12, 30)}, u_await=0),
                              n_fetch=0)
    assert (same, full) == ("FAIL", "FAIL")
    assert MB.study_word(same, full) == "NOT BUILT"


def test_every_floor_passing_runs_the_full_verdict():
    same, full, _ = MB.floors(_census(share=0.80, u_await=0), n_fetch=0)
    assert MB.study_word(same, full) is None


def test_main_prints_same_ticker_read_without_arm_u(monkeypatch, capsys):
    """U awaiting, M1/M2 fetched: per-arm grades print under the partial
    label, ARM U is never graded, and no study-level token prints."""
    slots = [_slot(f"2026-01-{d:02d}") for d in range(1, 31)]
    for s in slots:
        s.rec["source"] = "real"
    m = {"M1": [MB.Wrap("built")] * 30, "M2": [MB.Wrap("built")] * 30,
         "M2L": [MB.Wrap("await", "x")] * 30}
    b = MB.EraBuild("current", slots, m, [], {}, {}, "seal")
    rows = [dict(date=f"2026-01-{d:02d}", ticker=T, tier=t, structure="bull_call_spread",
                 band="45-90", model_dir="BULL", R_T=0.30 + 0.01 * d, R_C=0.0,
                 E_T=0, E_C=0, k_long=1, k_short=2)
            for d in range(1, 31) for t in ("A", "B")]
    calls = []
    monkeypatch.setattr(MB.NTF, "Chain", lambda: None)
    monkeypatch.setattr(MB.NTF, "unlisted_evidence", lambda: set())
    monkeypatch.setattr(MB.NTF, "_sim_cfg", lambda: {})
    monkeypatch.setattr(MB, "load_book", lambda **k: ([], {"era": "current"}))
    monkeypatch.setattr(MB, "build_era", lambda *a, **k: b)
    monkeypatch.setattr(MB, "census", lambda _b: _census())
    monkeypatch.setattr(MB, "print_census", lambda *a: None)
    monkeypatch.setattr(MB, "fetch_targets", lambda _b: [{"category": "U:current"}])
    monkeypatch.setattr(MB, "tickers_without_underlying", lambda _b: [])
    monkeypatch.setattr(MB, "g2_blind", lambda *a: [])
    monkeypatch.setattr(MB, "g5_mirror", lambda *a: (0, []))
    monkeypatch.setattr(MB, "pair_rows", lambda _b, a, basis: calls.append(a) or rows)
    monkeypatch.setattr(MB, "u_rows", lambda *a: pytest.fail("ARM U was graded"))
    monkeypatch.setattr(MB, "write_pairs", lambda by: calls.append(sorted(by)))
    assert MB.main(["--no-v3"]) == 0
    out = capsys.readouterr().out
    assert f"VERDICT (headline basis): {MB.SAME_TICKER_READ}" in out
    assert "ARM M1  C0 Y  C1 Y  C2 Y  clears C0-C2 Y  CONTRARY n" in out
    assert "ARM M2  C0 Y" in out
    assert "M2L   not graded: pairs await a fetch" in out
    assert "U     not graded: ARM U floors AWAITING" in out
    for token in ("SELECTION-CONFIRMED", "STRUCTURE-ONLY", "BASE-RATE", "UNWORDED",
                  "VERDICT: NOT BUILT", "VERDICT (headline basis): NULL",
                  "VERDICT (headline basis): UNDERPOWERED"):
        assert token not in out, token
    assert "M2L" not in calls and ["M1", "M2"] in calls


def test_main_m1_awaiting_prints_no_outcome(monkeypatch, capsys):
    b = MB.EraBuild("current", [], {a: [] for a in MB.ARMS_M}, [], {}, {}, "seal")
    monkeypatch.setattr(MB.NTF, "Chain", lambda: None)
    monkeypatch.setattr(MB.NTF, "unlisted_evidence", lambda: set())
    monkeypatch.setattr(MB.NTF, "_sim_cfg", lambda: {})
    monkeypatch.setattr(MB, "load_book", lambda **k: ([], {"era": "current"}))
    monkeypatch.setattr(MB, "build_era", lambda *a, **k: b)
    monkeypatch.setattr(MB, "census", lambda _b: _census(m1_await=4))
    monkeypatch.setattr(MB, "print_census", lambda *a: None)
    monkeypatch.setattr(MB, "fetch_targets", lambda _b: [{"category": "M1:current"}])
    monkeypatch.setattr(MB, "tickers_without_underlying", lambda _b: [])
    monkeypatch.setattr(MB, "pair_rows", lambda *a: pytest.fail("an outcome was read"))
    assert MB.main(["--no-v3"]) == 0
    out = capsys.readouterr().out
    assert "VERDICT: NOT BUILT — AWAITING SCRAPE" in out
    assert MB.SAME_TICKER_READ not in out


def test_u_planning_skips_evidenced_strikes():
    """ARM U's no-spot planning names no skip-listed strike (the same walk as
    `nearest_listed`), and nothing already cached."""
    ch = chain_of({100.0: {SIG + timedelta(days=30): (5.0, 100.0, 0.5)}})
    assert set(MB.plan_m1_fetch(ch, set(), T, EXP, 100.0)) == {(T, EXP, 105.0)}
    ev = {NTF.contract_stem(T, EXP, 105.0, "Call")}
    assert set(MB.plan_m1_fetch(ch, ev, T, EXP, 100.0)) == {(T, EXP, 102.5)}   # next grid strike, tie: lower


# ── UniverseSpot: the walk reads every cached call (fixed 2026-10-15) ────────

def multi_chain(quotes: dict, ticker=T) -> NTF.Chain:
    """`{(expiry, strike): {day: spot}}` -> a Chain of `ticker` calls."""
    idx: dict = {}
    for exp, k in quotes:
        idx.setdefault((ticker, exp), {})[float(k)] = {"C"}
    ch = NTF.Chain(idx=idx)
    for (exp, k), days in quotes.items():
        ch._memo[(ticker, exp, round(float(k), 4), "Call")] = (
            sorted((d, 1.0) for d in days),
            {d: {"_mark": 1.0, "Price~": str(s)} for d, s in days.items()})
    return ch


def test_spot_found_when_the_pick_expiry_is_unlisted_on_the_signal_date():
    """Regression: SPY 2025-03-03. The pick's expiry carried more than
    `SPOT_CONTRACTS * 4` strikes, none listed yet on the signal date, so the
    old capped walk spent every probe there and returned None, although
    another expiry was priced that day."""
    later = date(2026, 4, 17)
    post = SIG + timedelta(days=20)
    q = {(later, float(k)): {post: 130.0} for k in range(70, 70 + MB.SPOT_CONTRACTS * 4 + 10)}
    q.update({(EXP, float(k)): {SIG: 100.0 + (k - 100) * 0.01, post: 130.0}
              for k in range(95, 106)})
    ch = multi_chain(q)
    spot = MB.UniverseSpot(ch)
    # the first five priced calls by strike, 95-99: median 99.97
    assert spot(T, SIG, later) == pytest.approx(99.97)
    # read on the signal date only: a cache cut there gives the same spot (G2)
    assert MB.UniverseSpot(MB.AsOfChain(ch, SIG))(T, SIG, later) == spot(T, SIG, later)
    # and the M1 walk on the priced expiry now builds instead of no_spot_at_signal
    w = MB.select_m1(ch, set(), T, EXP, spot(T, SIG, later), SIG)
    assert w.status == "built" and (w.k_long, w.k_short) == (100.0, 105.0)


def test_spot_is_none_only_when_nothing_is_priced_that_day():
    post = SIG + timedelta(days=20)
    ch = multi_chain({(EXP, float(k)): {post: 130.0} for k in range(90, 130)})
    spot = MB.UniverseSpot(ch)
    assert spot(T, SIG, EXP) is None            # a later row is never read
    assert spot(T, post, EXP) == 130.0
    assert spot("ZZZ", SIG, EXP) is None


def test_spot_probe_order_is_unchanged_for_five_found():
    """The pick expiry's strikes middle-out come first, as before the fix."""
    later = date(2026, 4, 17)
    q = {(EXP, float(k)): {SIG: 50.0} for k in range(90, 110)}
    q.update({(later, float(k)): {SIG: 100.0 + k} for k in range(90, 99)})
    spot = MB.UniverseSpot(multi_chain(q))
    assert spot(T, SIG, later) == 100.0 + 94          # 9 strikes, middle 94, 5 middle-out
    assert spot(T, SIG, EXP) == 50.0
