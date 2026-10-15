"""spy_benchmark: pairing under both units, no look-ahead, and the AWAITING stop.

research/pre-registrations/f1_selection/benchmark/spy_benchmark.md. Synthetic
chains only; no test reads the real exports or the option cache.
"""
from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB
from scripts.backtest_study.f1_selection.benchmark import spy_benchmark as SB
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF

SPY = "SPY"
EXP1 = date(2026, 3, 20)
EXP2 = date(2026, 4, 17)
SIG = date(2026, 1, 5)
PRE = SIG - timedelta(days=1)
POST = SIG + timedelta(days=10)


def chain_of(quotes: dict) -> NTF.Chain:
    """`{(expiry, strike): {day: (mark, spot)}}` -> a Chain of SPY calls."""
    idx: dict = {}
    for exp, k in quotes:
        idx.setdefault((SPY, exp), {})[float(k)] = {"C"}
    ch = NTF.Chain(idx=idx)
    for (exp, k), days in quotes.items():
        series = sorted((d, m) for d, (m, _s) in days.items())
        details = {d: {"_mark": m, "Price~": str(s), "Delta": "0.5"}
                   for d, (m, s) in days.items()}
        ch._memo[(SPY, exp, round(float(k), 4), "Call")] = (series, details)
    return ch


def full_chain(exps=(EXP1, EXP2)) -> NTF.Chain:
    q = {}
    for exp in exps:
        for k in range(95, 112):
            q[(exp, float(k))] = {SIG: (1.0, 100.0), POST: (2.0, 120.0)}
    return chain_of(q)


def _slot(d: str, ticker="AAA", tier="A", expiry=EXP1, drop="", source="real"):
    return MB.Slot(rec={"t": None, "mech_cell": "PROD", "source": source,
                        "model_dir": "BULL"},
                   date=d, ticker=ticker, tier=tier, structure="bull_call_spread",
                   band=(45, 90), expiry=expiry, signal=SIG,
                   entry_day=SIG + timedelta(days=1), dte=60, drop=drop)


def _build(monkeypatch, slots, chain, evidence=frozenset()):
    monkeypatch.setattr(SB.MB, "deployed", lambda recs: recs)
    monkeypatch.setattr(SB.MB, "slot_of", lambda s: s)
    monkeypatch.setattr(SB.MB, "apply_seal", lambda recs: (recs, "seal"))
    monkeypatch.setattr(SB.MB, "ohlc_close", lambda *a: 100.0)   # never the real bars
    return SB.build_era(None, chain, set(evidence), {}, price=False, records=slots)


# ── the arm is ARM M1 on SPY ─────────────────────────────────────────────────

def test_spy_wrap_is_m1_geometry_at_the_picks_expiry(monkeypatch):
    b = _build(monkeypatch, [_slot("2026-01-05", expiry=EXP2)], full_chain())
    w = b.wraps[0]
    assert w.status == "built" and (w.k_long, w.k_short) == (100.0, 105.0)
    assert SB.census(b)["status"]["built"] == 1


def test_picks_sharing_an_expiry_share_one_spy_wrap(monkeypatch):
    slots = [_slot("2026-01-05", "AAA", expiry=EXP1), _slot("2026-01-05", "BBB", expiry=EXP1),
             _slot("2026-01-05", "CCC", expiry=EXP2)]
    b = _build(monkeypatch, slots, full_chain())
    assert b.wraps[0] is b.wraps[1] and b.wraps[0] is not b.wraps[2]
    assert SB.census(b)["distinct"] == 2


def test_a_scope_drop_stays_a_drop_and_g4_counts_every_slot(monkeypatch):
    slots = [_slot("2026-01-05"), _slot("2026-01-06", drop="dte_ge_180")]
    b = _build(monkeypatch, slots, full_chain())
    assert [w.status for w in b.wraps] == ["built", "drop"]
    assert SB.g4_pairing(b) == []
    b.wraps = b.wraps[:1]
    assert SB.g4_pairing(b)


# ── pairing: SB-UNIT = pick and = date ───────────────────────────────────────

def test_pair_rows_repeat_spy_and_date_rows_take_the_top_pick(monkeypatch):
    slots = [_slot("2026-01-05", "AAA", tier="A", expiry=EXP1),
             _slot("2026-01-05", "BBB", tier="B", expiry=EXP2),
             _slot("2026-01-06", "CCC", tier="A", expiry=EXP1)]
    for s, r in zip(slots, (0.6, 0.2, -0.4)):
        s.rec["t"] = r
    spy1 = MB.Wrap("built", "", 100.0, 105.0, row={"R": 0.1})
    spy2 = MB.Wrap("built", "", 100.0, 105.0, row={"R": 0.3})
    b = SB.SpyBuild("current", slots, [spy1, spy2, spy1], "seal")
    monkeypatch.setattr(SB.MB, "trade_of", lambda row: row)
    monkeypatch.setattr(SB.MB, "replay_R",
                        lambda t, prof: (t["R"], 0.0) if isinstance(t, dict) else (t, 0.0))
    rows = SB.pair_rows(b, "headline")
    assert [(r["ticker"], r["R_T"], r["R_C"]) for r in rows] == [
        ("AAA", 0.6, 0.1), ("BBB", 0.2, 0.3), ("CCC", -0.4, 0.1)]
    d = SB.rows_for("date", rows)
    assert [(r["date"], r["n_picks"], r["R_T"], r["R_C"]) for r in d] == [
        ("2026-01-05", 2, pytest.approx(0.4), 0.1), ("2026-01-06", 1, -0.4, 0.1)]
    assert SB.rows_for("pick", rows) is rows


def test_unbuilt_wraps_leave_the_comparison(monkeypatch):
    slots = [_slot("2026-01-05"), _slot("2026-01-06")]
    b = SB.SpyBuild("current", slots, [MB.Wrap("await", "x"), MB.Wrap("drop", "y")], "s")
    monkeypatch.setattr(SB.MB, "replay_R", lambda *a: pytest.fail("an outcome was read"))
    assert SB.pair_rows(b, "headline") == []


# ── no look-ahead (G2) ───────────────────────────────────────────────────────

def test_choice_reads_nothing_after_the_signal(monkeypatch):
    q = {(EXP1, k): {SIG: (1.0, 100.0)} for k in (100.0, 104.0)}
    q[(EXP1, 105.0)] = {POST: (1.0, 120.0)}            # listed only after the signal
    near = MB.grid_around(100.0, 1.0, [100.0, 104.0, 105.0]) + \
        MB.grid_around(105.0, 1.0, [100.0, 104.0, 105.0])
    ev = {NTF.contract_stem(SPY, EXP1, k, "Call") for k in near if k not in (100.0, 104.0, 105.0)}
    ch = chain_of(q)
    b = _build(monkeypatch, [_slot("2026-01-05", expiry=EXP1)], ch, ev)
    # 105 is nearest the x1.05 target but first quoted after the signal: not listed
    assert (b.wraps[0].k_long, b.wraps[0].k_short) == (100.0, 104.0)
    assert SB.g2_blind(b, ch, ev) == []
    # a full-cache choice that disagrees with the cut cache is caught
    b.wraps[0] = MB.Wrap("built", "", 100.0, 105.0)
    assert SB.g2_blind(b, ch, ev)


def test_spot_is_read_on_the_signal_date_only(monkeypatch):
    q = {(EXP1, k): {POST: (1.0, 120.0)} for k in range(95, 112)}
    ch = chain_of(q)
    assert MB.UniverseSpot(ch)(SPY, SIG, EXP1) is None    # the later rows are never read
    b = _build(monkeypatch, [_slot("2026-01-05", expiry=EXP1)], ch)
    # nothing is chosen; with 17 contracts all quoted later, ruling B drops it
    assert (b.wraps[0].status, b.wraps[0].reason) == ("drop", SB.EXPIRY_NOT_LISTED)


# ── the AWAITING stop ────────────────────────────────────────────────────────

def test_uncached_strike_awaits_and_is_a_fetch_target(monkeypatch):
    q = {(EXP1, 100.0): {SIG: (1.0, 100.0)}}            # no strike near 105 cached
    b = _build(monkeypatch, [_slot("2026-01-05", expiry=EXP1)], chain_of(q))
    assert b.wraps[0].status == "await"
    tg = SB.fetch_targets([b])
    assert tg and all(t["ticker"] == SPY and t["category"] == "SPY:current" for t in tg)
    state, lines = SB.floors(SB.census(b), len(tg))
    assert state in ("AWAITING", "FAIL")


def _census(built=60, wait=0, f2=None, f1_now=30, f1_bound=30):
    from collections import Counter
    return dict(status=Counter({"built": built, "await": wait, "drop": 4}),
                f1_now=f1_now, f1_bound=f1_bound,
                f2=f2 or {"A": (2, 30), "B": (2, 30)}, bands=Counter())


def test_floors():
    assert SB.floors(_census(), 0)[0] == "PASS"
    assert SB.floors(_census(wait=3), 5)[0] == "AWAITING"
    assert SB.floors(_census(), 2)[0] == "AWAITING"
    assert SB.floors(_census(f1_now=3, f1_bound=10), 5)[0] == "FAIL"
    assert SB.floors(_census(f2={"A": (0, 30), "B": (12, 30)}), 0)[0] == "FAIL"
    assert SB.study_word("AWAITING") == SB.AWAITING
    assert SB.study_word("FAIL") == SB.NOT_BUILT
    assert SB.study_word("PASS") is None


def test_main_awaiting_prices_and_replays_nothing(monkeypatch, capsys):
    w = MB.Wrap("await", "x", fetch=((SPY, EXP1, 105.0),))
    b = SB.SpyBuild("current", [_slot(f"2026-01-{d:02d}") for d in range(1, 31)],
                    [w] * 30, "seal")
    monkeypatch.setattr(SB.NTF, "Chain", lambda: None)
    monkeypatch.setattr(SB.NTF, "unlisted_evidence", lambda: set())
    monkeypatch.setattr(SB.NTF, "_sim_cfg", lambda: {})
    monkeypatch.setattr(SB, "load_book", lambda **k: ([], {"era": "current"}))
    monkeypatch.setattr(SB, "build_era", lambda *a, **k: b)
    monkeypatch.setattr(SB, "priced", lambda *a: pytest.fail("a SPY wrap was priced"))
    monkeypatch.setattr(SB, "pair_rows", lambda *a: pytest.fail("an outcome was read"))
    assert SB.main([]) == 0
    out = capsys.readouterr().out
    assert "VERDICT: NOT BUILT — AWAITING SCRAPE" in out
    assert "SPY:current=1" in out
    for token in ("BEATS-SPY", "DOES-NOT-BEAT", "VERDICT (headline"):
        assert token not in out, token


# ── verdicts and hygiene ─────────────────────────────────────────────────────

def test_verdict_precedence():
    assert SB.verdict({"c0": False, "contrary": True}) == "UNDERPOWERED"
    assert SB.verdict({"c0": True, "contrary": True}) == "CONTRARY"
    assert SB.verdict({"c0": True, "c1": True, "c2": True}) == "BEATS-SPY"
    assert SB.verdict({"c0": True, "c1": True, "c2": False}) == "DOES-NOT-BEAT"
    assert SB.verdict({"c0": True, "c1": False}) == "DOES-NOT-BEAT"


def test_reuses_mechanical_benchmark_and_adds_no_statistic():
    src = Path(SB.__file__).read_text()
    tree = ast.parse(src)
    names = {n.id.lower() for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
        {n.name.lower() for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for word in ("sharpe", "annualis", "annualiz", "recover"):
        assert not [n for n in names if word in n], word
    # the geometry and C0 are mechanical_benchmark's, never re-encoded here
    for const in ("LONG_MULT", "SHORT_MULT", "C0_MIN_DATES", "C0_MIN_PAIRS", "BANDS"):
        assert f"{const} =" not in src, const
    for word in ("resolve_paths(", "default_results_csv", "eval_dir"):
        assert word not in src.lower(), word
    assert SB.UNITS[0] == "pick"


def test_no_spot_on_the_signal_date_drops_as_m1_does(monkeypatch):
    """Resolved at build (2026-10-15): SPY 2024-07-28 was a Sunday, so no
    cached contract carries a row that day. The pair drops as
    `no_spot_at_signal`, ARM M1's own drop, instead of awaiting forever."""
    sunday = date(2026, 1, 4)
    q = {(EXP1, float(k)): {PRE - timedelta(days=1): (1.0, 99.0), SIG: (1.0, 100.0)}
         for k in range(95, 112)}
    ch = chain_of(q)
    slot = _slot("2026-01-04", expiry=EXP1)
    slot.signal = sunday
    b = _build(monkeypatch, [slot], ch)
    w = b.wraps[0]
    assert (w.status, w.reason) == ("drop", "no_spot_at_signal") and not w.fetch
    assert w.reason == MB.select_m1(ch, set(), SPY, EXP1, None, sunday).reason
    assert SB.fetch_targets([b]) == []
    assert SB.g2_blind(b, ch, set()) == []


# ── ruling B: an expiry SPY had not listed on the signal date (2026-10-15) ───

FAR = date(2026, 6, 19)


def _unlisted_far(strikes, pre_strike=None):
    """SPY priced at 100 on SIG via EXP1; every FAR contract first quoted
    after the signal, except `pre_strike` when given."""
    q = {(EXP1, float(k)): {SIG: (1.0, 100.0)} for k in range(95, 112)}
    for k in strikes:
        q[(FAR, float(k))] = {POST: (1.0, 120.0)}
    if pre_strike is not None:
        q[(FAR, float(pre_strike))] = {PRE: (1.0, 99.0), POST: (1.0, 120.0)}
    return chain_of(q)


def test_feb_2027_shape_drops_as_expiry_not_listed(monkeypatch, capsys):
    """The seven Feb-2027 pairs: every cached contract at the pick's expiry
    is first quoted after the signal, and at least five are cached. The
    pairs drop rather than await a fetch forever."""
    ch = _unlisted_far(range(95, 112))
    slots = [_slot("2026-01-05", f"T{i}", tier="AB"[i % 2], expiry=FAR) for i in range(7)]
    b = _build(monkeypatch, slots, ch)
    assert [w.reason for w in b.wraps] == [SB.EXPIRY_NOT_LISTED] * 7
    assert all(w.status == "drop" and not w.fetch for w in b.wraps)
    assert SB.fetch_targets([b]) == []
    c = SB.census(b)
    assert c["reasons"][SB.EXPIRY_NOT_LISTED] == 7
    assert c["f2"] == {"A": (4, 4), "B": (3, 3)}        # floor 2 counts the drop
    _state, lines = SB.floors(c, 0)
    assert any(ln.lstrip().startswith("2  in-scope dropped share by tier") for ln in lines)
    SB.print_census(b, c)
    assert f"not built: {SB.EXPIRY_NOT_LISTED}" in capsys.readouterr().out
    assert SB.g2_blind(b, ch, set()) == []              # a cut cache agrees


def test_fewer_than_the_minimum_cached_contracts_still_awaits(monkeypatch):
    """Four cached strikes, all first quoted after the signal, are too few to
    show the expiry was not listed: the pair awaits a fetch."""
    n = SB.EXPIRY_NOT_LISTED_MIN_CONTRACTS
    assert n == 5
    few = _unlisted_far(range(101, 101 + n - 1))
    assert not SB.expiry_not_listed(few, SPY, FAR, SIG)
    b = _build(monkeypatch, [_slot("2026-01-05", expiry=FAR)], few)
    w = b.wraps[0]
    assert w.status == "await" and w.reason == "strike_not_cached"
    assert (SPY, FAR, 100.0) in w.fetch
    # one more, still off the ATM target, is enough: the strike span is not read
    enough = _unlisted_far(range(101, 101 + n))
    assert SB.expiry_not_listed(enough, SPY, FAR, SIG)
    b = _build(monkeypatch, [_slot("2026-01-05", expiry=FAR)], enough)
    assert (b.wraps[0].status, b.wraps[0].reason) == ("drop", SB.EXPIRY_NOT_LISTED)


def test_an_expiry_with_a_row_on_or_before_the_signal_is_unaffected(monkeypatch):
    b = _build(monkeypatch, [_slot("2026-01-05", expiry=FAR)],
               _unlisted_far(range(95, 112), pre_strike=100))
    w = b.wraps[0]
    assert w.reason != SB.EXPIRY_NOT_LISTED
    # the normal walk runs: 100 is the only listed strike, so both legs land
    # on it and the pair drops as degenerate, never as an unlisted expiry
    assert (w.status, w.reason) == ("drop", "degenerate")
    # a put quoted before the signal blocks the ruling too
    ch = _unlisted_far(range(95, 112))
    ch.idx[(SPY, FAR)][100.0] = {"C", "P"}
    ch._memo[(SPY, FAR, 100.0, "Put")] = ([(PRE, 1.0)], {PRE: {"_mark": 1.0, "Price~": "99"}})
    assert not SB.expiry_not_listed(ch, SPY, FAR, SIG)
    assert SB.expiry_not_listed(_unlisted_far(range(95, 112)), SPY, FAR, SIG)
