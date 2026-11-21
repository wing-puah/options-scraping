"""signal_call_calendar — research/pre-registrations/f1_selection/regime/signal_call_calendar.md.

Synthetic data only: a seeded SPY/VIX random walk and option chains built in memory. No
option cache file, no close table and no network is read. The lookahead (GX) and cut (GC)
tests mutate every later close and quote and require identical choices and an identical
in-sample report.
"""
from __future__ import annotations

import ast
import contextlib
import io
import math
from datetime import date, timedelta

import numpy as np
import pytest

from scripts.backtest_study import run as runner
from scripts.backtest_study.f1_selection.regime import signal_call_calendar as S
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF
from scripts.collector.study_legs.f1_selection import fetch_signal_call_calendar_legs as F

SM = S.SM


# ── synthetic market ────────────────────────────────────────────────────────

def weekdays(lo: date, hi: date) -> list[date]:
    out, d = [], lo
    while d <= hi:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def synth_cal(seed: int = 11, lo: date = date(2020, 6, 1), hi: date = date(2026, 11, 20)) -> SM.Cal:
    """A seeded SPY random walk near 100 with sell-offs, and a VIX that rises in them."""
    rng = np.random.default_rng(seed)
    days = weekdays(lo, hi)
    n = len(days)
    r = rng.normal(0.0007, 0.007, n)
    for start in rng.choice(np.arange(60, max(61, n - 40)), min(8, max(0, n - 100)), replace=False):
        r[start:start + 8] -= 0.012
    close = 100 * np.exp(np.cumsum(r))
    peak = np.maximum.accumulate(close)
    vix = 13 + 150 * (1 - close / peak) + rng.normal(0, 0.4, n)
    vix3m = vix * 0.95 + 1.5
    adj = close * np.exp(np.arange(n) * 0.00005)
    nan = np.full(n, np.nan)
    return SM.Cal([d.isoformat() for d in days], close, adj, vix, vix3m, nan)


class FakeChain:
    """Every SPY monthly call from 20 to 300 in steps of 1, quoted on every session from
    200 days before expiry. `bump` (date, factor) scales every quote after the date;
    `unlisted` maps (expiry, strike) to the first quoted date; `missing` drops contracts."""

    def __init__(self, cal: SM.Cal, bump=None, unlisted=None, missing=(), first=None):
        self.cal, self.bump = cal, bump
        self.unlisted, self.missing = dict(unlisted or {}), set(missing)
        self.sessions = [date.fromisoformat(d) for d in cal.dates]
        self.spot = dict(zip(self.sessions, cal.close.tolist()))
        exps = S.MB.monthly_expiries(date(2020, 1, 1), date(2028, 12, 31))
        self.idx = {("SPY", e): {float(k): {"C"} for k in range(20, 301)
                                 if (e, float(k)) not in self.missing} for e in exps}
        self._memo: dict = {}

    def cached(self, ticker, expiry, strike, opt_type) -> bool:
        return opt_type == "Call" and "C" in self.idx.get((ticker, expiry), {}).get(round(float(strike), 4), set())

    def strikes(self, ticker, expiry):
        return sorted(self.idx.get((ticker, expiry), {}))

    def history(self, leg):
        key = (leg.expiration, round(leg.strike, 4), leg.opt_type)
        if key not in self._memo:
            series, details = [], {}
            if self.cached("SPY", leg.expiration, leg.strike, leg.opt_type):
                lo = self.unlisted.get((leg.expiration, float(leg.strike)), leg.expiration - timedelta(days=200))
                for d in self.sessions:
                    if d < lo or d > leg.expiration:
                        continue
                    S0, K = self.spot[d], float(leg.strike)
                    t = max((leg.expiration - d).days, 0) / 365.0
                    mid = max(0.0, S0 - K) + 0.06 * S0 * math.sqrt(t) * math.exp(-((S0 - K) / (0.12 * S0)) ** 2)
                    if self.bump and d > self.bump[0]:
                        mid *= self.bump[1]
                    mid = round(max(mid, 0.03), 4)
                    row = {"Bid": round(mid - 0.02, 4), "Ask": round(mid + 0.02, 4), "Latest": mid,
                           "Volume": 10, "_mark": mid}
                    details[d] = row
                    series.append((d, mid))
            self._memo[key] = (series, details)
        return self._memo[key]


def mutate_after(cal: SM.Cal, cut: str, factor: float = 1.37) -> SM.Cal:
    k = sum(1 for d in cal.dates if d <= cut)
    out = SM.Cal(list(cal.dates), cal.close.copy(), cal.adj.copy(), cal.vix.copy(), cal.vix3m.copy(),
                 cal.credit.copy())
    for arr in (out.close, out.adj, out.vix, out.vix3m):
        arr[k:] *= factor
    return out


def quotes(q: dict) -> tuple[list, dict]:
    series, details = [], {}
    for d in sorted(q):
        bid, ask = q[d]
        mid = (bid + ask) / 2
        details[d] = {"Bid": bid, "Ask": ask, "Latest": mid, "Volume": 0, "_mark": mid}
        series.append((d, mid))
    return series, details


def chain_of(contracts: dict) -> NTF.Chain:
    """A Chain over `{(expiry, strike): {date: (bid, ask)}}` (calls), no files."""
    idx: dict = {}
    for (exp, k) in contracts:
        idx.setdefault(("SPY", exp), {}).setdefault(float(k), set()).add("C")
    ch = NTF.Chain(idx=idx)
    for (exp, k), q in contracts.items():
        ch._memo[("SPY", exp, round(float(k), 4), "Call")] = quotes(q)
    return ch


@pytest.fixture(scope="module")
def full():
    return synth_cal()


def run_in_sample(full_cal, chain, boot_n=200):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = S.in_sample(full_cal, chain, set(), boot_n=boot_n, pbo_fn=lambda M: float(np.round(M.sum(), 6)) % 1)
    return buf.getvalue(), out


# ── leg selection ───────────────────────────────────────────────────────────

def test_short_leg_is_the_monthly_nearest_30_dte_with_at_least_21():
    assert S.short_expiry(date(2024, 1, 11)) == date(2024, 2, 16)      # 36 DTE; Jan 19 (8) too near
    assert S.short_expiry(date(2024, 1, 18)) == date(2024, 2, 16)      # Jan 19 is 1 DTE
    assert S.short_expiry(date(2024, 1, 29)) == date(2024, 3, 15)      # Feb 16 is 18 DTE < 21
    for entry in weekdays(date(2023, 1, 2), date(2024, 12, 31)):
        e = S.short_expiry(entry)
        assert 21 <= (e - entry).days <= 56
        assert e in S.MB.monthly_expiries(entry, entry + timedelta(days=60))


def test_long_leg_is_strictly_later_and_nearest_60_or_90():
    entry = date(2024, 1, 11)
    se = S.short_expiry(entry)
    assert S.long_expiry(entry, se, 60) == date(2024, 3, 15)
    assert S.long_expiry(entry, se, 90) == date(2024, 4, 19)
    entry = date(2024, 1, 29)                                       # short Mar 15 (46 DTE)
    se = S.short_expiry(entry)
    assert S.long_expiry(entry, se, 60) == date(2024, 4, 19)        # strictly after the short's
    for entry in weekdays(date(2023, 1, 2), date(2024, 12, 31)):
        se = S.short_expiry(entry)
        for dte in (60, 90):
            le = S.long_expiry(entry, se, dte)
            assert le > se
            later = S.MB.monthly_expiries(se + timedelta(days=1), se + timedelta(days=400))
            assert min(abs((x - entry).days - dte) for x in later) == abs((le - entry).days - dte)


def _sel_chain(entry, short_strikes, long_strikes, late=(), long_late=()):
    se, le = S.short_expiry(entry), S.long_expiry(entry, S.short_expiry(entry), 60)
    q = {entry - timedelta(days=5): (1.0, 1.1)}
    late_q = {entry + timedelta(days=3): (1.0, 1.1)}
    c = {(se, k): (late_q if k in late else q) for k in short_strikes}
    c.update({(le, k): (late_q if k in long_late else q) for k in long_strikes})
    return chain_of(c), se, le


def test_strike_is_the_listed_strike_nearest_spot_x103_on_the_short_grid():
    entry = date(2024, 1, 11)
    grid = range(90, 116)
    ch, se, le = _sel_chain(entry, grid, grid)
    s = S.select(ch, set(), entry, 100.0, 1.03, 60)
    assert (s.status, s.strike, s.short_exp, s.long_exp) == ("built", 103.0, se, le)
    # 103 cached but first quoted after the entry: not listed yet, the walk steps to 102 (tie: lower).
    ch, *_ = _sel_chain(entry, grid, grid, late={103})
    assert S.select(ch, set(), entry, 100.0, 1.03, 60).strike == 102.0
    # 102 skip-listed on evidence as well: 104.
    ev = {NTF.contract_stem("SPY", se, 102.0, "Call")}
    assert S.select(ch, ev, entry, 100.0, 1.03, 60).strike == 104.0
    # The parameter strikes walk the same grid.
    ch, *_ = _sel_chain(entry, grid, grid)
    assert S.select(ch, set(), entry, 100.0, 1.00, 60).strike == 100.0
    assert S.select(ch, set(), entry, 100.0, 1.05, 60).strike == 105.0


def test_long_strike_unlisted_drops_and_uncached_awaits():
    entry = date(2024, 1, 11)
    grid = range(90, 116)
    ch, se, le = _sel_chain(entry, grid, [k for k in grid if k != 103])
    s = S.select(ch, set(), entry, 100.0, 1.03, 60)
    assert (s.status, s.reason, s.fetch) == ("await", "long_strike_not_cached", (("Call", le, 103.0),))
    ch, se, le = _sel_chain(entry, grid, grid, long_late={103})
    assert S.select(ch, set(), entry, 100.0, 1.03, 60).reason == "long_strike_unlisted"
    ch, se, le = _sel_chain(entry, grid, [k for k in grid if k != 103])
    ev = {NTF.contract_stem("SPY", le, 103.0, "Call")}
    assert S.select(ch, ev, entry, 100.0, 1.03, 60).reason == "long_strike_unlisted"
    # An uncached short strike awaits, and the long at that strike is fetched with it.
    ch, se, le = _sel_chain(entry, [k for k in grid if k != 103], [k for k in grid if k != 103])
    s = S.select(ch, set(), entry, 100.0, 1.03, 60)
    assert s.status == "await" and set(s.fetch) == {("Call", se, 103.0), ("Call", le, 103.0)}


def test_selection_reads_nothing_after_the_entry_session(full):
    """GX: every later close and quote changed; every choice identical."""
    base = FakeChain(full)
    checked = 0
    for D in range(300, full.n - 30, 37):
        entry = date.fromisoformat(full.dates[D + 1])
        later = FakeChain(mutate_after(full, full.dates[D + 1]), bump=(entry, 2.9))
        for mult in (1.00, 1.03, 1.05):
            for dte in (60, 90):
                a = S.select(base, set(), entry, float(full.close[D + 1]), mult, dte)
                b = S.select(later, set(), entry, float(full.close[D + 1]), mult, dte)
                assert a == b and a.status == "built"
                checked += 1
    assert checked > 100


# ── R, refusals and the floor ───────────────────────────────────────────────

def _book_for(entry, exit_day, long_q, short_q, h=21, skip=()):
    """A one-entry Book: `long_q`, `short_q` are {date: (bid, ask)}; `skip` drops sessions."""
    days = [d for d in weekdays(entry - timedelta(days=3), exit_day + timedelta(days=5)) if d not in skip]
    n = len(days)
    cal = SM.Cal([d.isoformat() for d in days], np.full(n, 100.0), np.full(n, 100.0), np.full(n, 20.0),
                 np.full(n, 21.0), np.full(n, np.nan))
    se, le = S.short_expiry(entry), S.long_expiry(entry, S.short_expiry(entry), 60)
    ch = chain_of({(le, 103.0): long_q, (se, 103.0): short_q})
    book = S.Book(cal, ch, set())
    D = cal.pos[entry.isoformat()] - 1
    sel = S.Sel("built", "", 103.0, se, le)
    e = S.Entry("K-BEAR", D, cal.dates[D], entry, 100.0, S.Geom(h=h), sel)
    book.open_outcomes([e])
    return book, e


def test_cost_is_four_leg_sides_and_R_is_bounded_at_minus_one():
    assert S.COST == pytest.approx(4 * 0.65)
    assert S.r_of(-0.5, 2.0) == pytest.approx(-1.0)                       # floored at 0
    assert S.r_of(0.0, 2.0) == pytest.approx(-1.0)
    assert S.r_of(3.0, 2.0) == pytest.approx((100.0 - 2.60) / 202.60)
    for v in np.linspace(-5, 10, 31):
        assert S.r_of(float(v), 1.7) >= -1.0 - 1e-12


def test_a_negative_exit_value_is_floored_and_counted():
    entry = date(2024, 1, 11)
    days = weekdays(entry, entry + timedelta(days=40))
    exit_day = days[21]
    long_q = {d: (2.95, 3.05) for d in days}
    short_q = {d: (0.95, 1.05) for d in days}
    long_q[exit_day], short_q[exit_day] = (1.45, 1.55), (1.95, 2.05)
    book, e = _book_for(entry, exit_day, long_q, short_q)
    p = book.price(e)
    assert p.debit == pytest.approx(2.0)
    assert p.floored and p.value == 0.0
    assert p.R == pytest.approx(-1.0) and p.gross == pytest.approx(-1.0)
    assert p.exit_day == exit_day and p.exit_reason == "h21" and p.clamp == 0
    assert p.mae >= -1.0


def test_a_debit_priced_to_a_credit_or_zero_is_refused():
    entry = date(2024, 1, 11)
    days = weekdays(entry, entry + timedelta(days=40))
    for lq, sq in (((0.95, 1.05), (1.15, 1.25)), ((0.95, 1.05), (0.95, 1.05))):
        book, e = _book_for(entry, days[21], {d: lq for d in days}, {d: sq for d in days})
        assert book.price(e) == "debit_priced_to_credit"


def test_no_entry_quote_and_exit_unmarked():
    entry = date(2024, 1, 11)
    days = weekdays(entry, entry + timedelta(days=40))
    lq = {d: (2.95, 3.05) for d in days}
    sq = {d: (0.95, 1.05) for d in days if d != entry}
    book, e = _book_for(entry, days[21], lq, sq)
    assert book.price(e) == "no_entry_quote"
    # Quotes stop after five sessions: production's daily mark carries them, tagged stale.
    lq = {d: (2.95, 3.05) for d in days[:5]}
    sq = {d: (0.95, 1.05) for d in days[:5]}
    book, e = _book_for(entry, days[21], lq, sq)
    p = book.price(e)
    assert p.stale == 2 and p.exit_reason == "h21"
    # The short expires before the exit with no quote and no close that day: unmarked.
    se = S.short_expiry(entry)
    book, e = _book_for(entry, entry + timedelta(days=45), lq, sq, h=30, skip={se})
    assert book.price(e) == "exit_unmarked"


def test_the_await_gate_shuts_pricing():
    cal = synth_cal(lo=date(2023, 1, 2), hi=date(2023, 6, 30))
    book = S.Book(cal, FakeChain(cal), set())
    e = book.entries("K-BEAR", [10], S.HEAD)[0]
    with pytest.raises(S.AwaitingScrape):
        book.price(e)
    aw = S.Entry("CALM", 10, cal.dates[10], e.entry, e.spot, S.HEAD, S.Sel("await", "strike_not_cached"))
    with pytest.raises(S.AwaitingScrape):
        book.open_outcomes([e, aw])


# ── populations ─────────────────────────────────────────────────────────────

def test_truncation_keeps_only_entries_whose_21_session_exit_is_on_or_before_the_cut(full):
    cal = SM.cut_cal(full, S.IN_SAMPLE_END)
    assert cal.dates[-1] <= S.IN_SAMPLE_END
    pop = S.in_sample_pop(cal)
    for s in S.SIGNALS:
        kept = pop.signals[s]
        assert all(cal.dates[d + 1 + 21] <= S.IN_SAMPLE_END for d in kept)
        assert len(kept) + pop.trunc[s] == len(pop.onsets[s])
        assert all(cal.dates[d] >= S.IN_SAMPLE_START for d in pop.onsets[s])
    assert all(d + 1 + 21 < cal.n for d in pop.calm)
    assert S.truncate([1, 5, 9], 31) == ([1, 5], 1)          # 9 + 22 = 31 is past the last index


def test_calm_days_are_disjoint_from_the_signals():
    cal = synth_cal(lo=date(2023, 1, 2), hi=date(2023, 3, 31))
    n = cal.n
    bear, evol, ok = np.zeros(n, bool), np.zeros(n, bool), np.ones(n, bool)
    bear[5], evol[9] = True, True
    flags = {"S-BEAR": (bear, ok), "S-EVOL": (evol, ok)}
    calm = [date.fromisoformat(cal.dates[i]) for i in (3, 5, 9, 12)]
    Ds, overlap = S.split_calm(calm, cal, flags)
    assert Ds == [3, 12] and overlap == 2


def test_gs_gate_set_equals_q4_trades(full, monkeypatch):
    cal = SM.cut_cal(full, S.IN_SAMPLE_END)
    pop = S.in_sample_pop(cal)
    gs = S.gate_gs(FakeChain(cal), set(), cal, pop)
    assert sum(len(a) for a, _ in gs.values()) > 0
    assert all(a == b for a, b in gs.values())
    real = SM.q4_trades
    monkeypatch.setattr(SM, "q4_trades", lambda *a, **k: real(*a, **k)[1:])
    gs = S.gate_gs(FakeChain(cal), set(), cal, pop)
    assert any(a != b for a, b in gs.values())
    with pytest.raises(S.Refused) as exc, contextlib.redirect_stdout(io.StringIO()):
        S.in_sample(full, FakeChain(full), set(), boot_n=50, pbo_fn=lambda M: 0.1)
    assert exc.value.code == S.EXIT_GS


def test_forward_split_excludes_runs_in_force_and_the_current_zone():
    anchor = 100
    ons = [95, 105, 110, 111, 130, 160]
    graded, inz, excluded = S.forward_split(ons, anchor, (90, 140))
    assert excluded == 2                        # 105 and 110: their re-arm sessions start before the anchor
    assert inz == [111, 130] and graded == [160]
    graded, inz, excluded = S.forward_split(ons, anchor, None)
    assert graded == [111, 130, 160] and inz == []


def test_forward_population_reads_only_onsets_after_the_anchor(full):
    pop = S.forward_pop(full)
    anchor = SM.idx_on_or_before(full, S.FORWARD_ANCHOR)
    for s in S.SIGNALS:
        assert all(d >= anchor + SM.REARM + 1 for d in pop.onsets[s] + pop.in_zone[s])


# ── the cut ─────────────────────────────────────────────────────────────────

def test_the_in_sample_report_ignores_every_close_and_quote_after_the_cut(full):
    """GC: identical in-sample report when every later close and quote changes, and a
    different one when an earlier quote changes (the check can fail)."""
    base_txt, base = run_in_sample(full, FakeChain(full))
    assert "IN-SAMPLE WORDS" in base_txt and "await" not in base
    cut = date.fromisoformat(S.IN_SAMPLE_END)
    later_txt, _ = run_in_sample(mutate_after(full, S.IN_SAMPLE_END), FakeChain(full, bump=(cut, 3.1)))
    assert later_txt == base_txt
    early_txt, _ = run_in_sample(full, FakeChain(full, bump=(date(2024, 6, 1), 1.2)))
    assert early_txt != base_txt


def test_in_sample_stops_at_the_await_gate_when_a_headline_contract_is_missing(full):
    cal = SM.cut_cal(full, S.IN_SAMPLE_END)
    pop = S.in_sample_pop(cal)
    D = pop.calm[0]
    entry = date.fromisoformat(cal.dates[D + 1])
    se = S.short_expiry(entry)
    k = S.SPD.nearest_listed(FakeChain(cal), set(), se, float(cal.close[D + 1]) * 1.03,
                             float(cal.close[D + 1]), entry, "Call").strike
    txt, out = run_in_sample(full, FakeChain(full, missing={(se, k)}))
    assert "await" in out and "OUTCOMES" not in txt and "fetch list" in txt


# ── verdicts ────────────────────────────────────────────────────────────────

def grade(lo=0.05, hi=0.3, padj=0.01, glo=0.02, ghi=0.2, gpadj=0.01, k=12):
    st = S.Stat(40, k, (lo + hi) / 2, lo, hi, 0.005, (glo + ghi) / 2, glo, ghi, 0.005)
    return S.Grade(st, padj, gpadj)


def test_verdict_first_match():
    assert S.verdict(grade(), 12, 12, 0.1, grade()) == (S.CP, [])
    assert S.verdict(grade(glo=-0.01), 12, 12, 0.1, grade(glo=-0.01))[0] == S.PNS
    assert S.verdict(grade(gpadj=0.2), 12, 12, 0.1, grade(gpadj=0.2))[0] == S.PNS
    assert S.verdict(grade(lo=-0.4, hi=-0.1), 12, 12, 0.1, None)[0] == S.CONTRARY
    assert S.verdict(grade(lo=-0.4, hi=-0.1, padj=0.07), 12, 12, 0.1, None)[0] == S.NULL
    assert S.verdict(grade(lo=-0.1, hi=0.2), 12, 12, 0.1, None)[0] == S.NULL
    assert S.verdict(grade(padj=0.06), 12, 12, 0.1, None)[0] == S.NULL


def test_verdict_underpowered_comes_first():
    assert S.verdict(grade(), 9, 12, 0.1, grade())[0] == S.UNDERPOWERED
    assert S.verdict(grade(), 12, 9, 0.1, grade())[0] == S.UNDERPOWERED
    assert S.verdict(grade(), 9, 12, 0.9, grade())[0] == S.UNDERPOWERED


def test_verdict_pbo_veto_not_computed_and_fragile():
    for g in (grade(), grade(glo=-0.1), grade(lo=-0.4, hi=-0.1), grade(lo=-0.1)):
        assert S.verdict(g, 12, 12, 0.51, g) == (S.NULL, ["PBO veto"])
        assert S.verdict(g, 12, 12, None, g) == (S.NULL, ["PBO not computed"])
    assert S.verdict(grade(), 12, 12, 0.50, grade()) == (S.CP, ["selection fragile"])
    assert S.verdict(grade(), 12, 12, 0.25, grade()) == (S.CP, [])


def test_verdict_exit_drop_sensitive():
    assert S.verdict(grade(), 12, 12, 0.1, grade(lo=-0.01)) == (S.NULL, ["exit-drop sensitive"])
    assert S.verdict(grade(), 12, 12, 0.1, grade(glo=-0.01)) == (S.NULL, ["exit-drop sensitive"])
    assert S.verdict(grade(glo=-0.1), 12, 12, 0.1, grade(glo=-0.1, padj=0.2)) == (S.NULL, ["exit-drop sensitive"])
    # CONTRARY carries no exit-drop clause.
    assert S.verdict(grade(lo=-0.4, hi=-0.1), 12, 12, 0.1, grade(lo=0.1))[0] == S.CONTRARY


def test_forward_verdict_has_no_pbo_clause_and_stays_open_below_the_floor():
    assert S.verdict(grade(), 9, 50, None, grade(), forward=True)[0] == S.STILL_OPEN
    assert S.verdict(grade(), 10, 0, None, grade(), forward=True) == (S.CP, [])
    assert S.verdict(grade(lo=-0.4, hi=-0.1), 10, 0, None, None, forward=True)[0] == S.CONTRARY


def test_holm_is_m2_per_family():
    adj = S.holm2({"K-BEAR": 0.02, "K-EVOL": 0.04})
    assert adj == {"K-BEAR": pytest.approx(0.04), "K-EVOL": pytest.approx(0.04)}
    adj = S.holm2({"K-BEAR": 0.02, "K-EVOL": float("nan")})
    assert adj["K-BEAR"] == pytest.approx(0.04) and adj["K-EVOL"] == 1.0
    adj = S.holm2({"K-BEAR": 0.001})
    assert adj["K-BEAR"] == pytest.approx(0.002)


def test_bootstrap_is_cluster_month_seeded_and_two_sided():
    arm = [(f"2023-{m:02d}-1{i}", 0.1 + 0.01 * i) for m in range(1, 13) for i in range(2)]
    calm = [(f"2023-{m:02d}-05", -0.05) for m in range(1, 13)]
    a, b = S.boot(arm, calm, 500), S.boot(arm, calm, 500)
    assert (a.lo, a.hi, a.glo) == (b.lo, b.hi, b.glo)
    assert a.k == 12 and a.n == 24 and a.lo > 0 and a.p == 0.0 and a.glo > 0
    assert a.gain == pytest.approx(a.mean + 0.05)
    assert S.boot_p(np.array([-1.0, 1.0, 2.0, 3.0])) == pytest.approx(0.5)
    assert S.boot([], None).k == 0


def test_pbo_grid_is_19_quarters_padded_to_20_by_12_configs():
    rows = {i: [("2022-02-15", 0.1), ("2026-09-01", -0.2)] for i in range(12)}
    M = S.pbo_grid(rows)
    assert M.shape == (20, 12, 2)
    assert M[0].sum() == 0 and M[1, 0, 1] == 1 and M[-1, 0, 0] == pytest.approx(-0.2)
    assert S.pbo_of(np.zeros((19, 12, 2))) is None


# ── fetch list and collector ────────────────────────────────────────────────

def test_contract_census_dedupes_and_counts_named():
    e1 = date(2024, 1, 11)
    se, le = date(2024, 2, 16), date(2024, 3, 15)
    aw = S.Sel("await", "strike_not_cached", 103.0, se, le, (("Call", se, 103.0), ("Call", le, 103.0)))
    built = S.Sel("built", "", 104.0, se, le)
    ents = {("headline", "K-BEAR"): [S.Entry("K-BEAR", 1, "2024-01-10", e1, 100.0, S.HEAD, aw)],
            ("headline", "CALM"): [S.Entry("CALM", 1, "2024-01-10", e1, 100.0, S.HEAD, aw),
                                   S.Entry("CALM", 2, "2024-01-10", e1, 100.0, S.HEAD, built)]}
    named, rows = S.contract_census(chain_of({}), ents)
    assert len(named) == 4 and len(rows) == 2
    assert {r["category"] for r in rows} == {"signal_call_calendar:K-BEAR:headline"}


def test_collector_plan_is_the_study_fetch_list(monkeypatch):
    plan = [dict(ticker="SPY", expiration=date(2024, 3, 15), strike=103.0, opt_type="Call",
                 category="signal_call_calendar:K-BEAR:headline")]
    monkeypatch.setattr(F.SCC, "fetch_list", lambda: list(plan))
    assert F.plan() == plan


def test_collector_dry_run_counts_and_fetches_nothing(monkeypatch, capsys):
    from scripts.backtest.shared import history
    plan = [dict(ticker="SPY", expiration=date(2024, 3, 15), strike=103.0, opt_type="Call",
                 category="signal_call_calendar:K-BEAR:headline")]

    async def boom(*a, **k):
        raise AssertionError("network fetch attempted")
    monkeypatch.setattr(history, "fetch_option_histories", boom)
    monkeypatch.setattr(F, "plan", lambda: list(plan))
    monkeypatch.setattr(F, "other_writers", lambda: (_ for _ in ()).throw(AssertionError("guard")))
    assert F.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "to fetch: 1" in out and "103.00C" in out and "[dry-run] nothing fetched" in out


def test_collector_refuses_beside_another_writer(monkeypatch, capsys):
    monkeypatch.setattr(F, "other_writers", lambda: [("1", "fetch")])
    monkeypatch.setattr(F, "plan", lambda: (_ for _ in ()).throw(AssertionError("planned")))
    assert F.main([]) == F.EXIT_OTHER_WRITER
    assert "REFUSED" in capsys.readouterr().err


# ── the runner ──────────────────────────────────────────────────────────────

def test_the_runner_discovers_the_study_by_stem():
    found = runner.discover()
    assert found["signal_call_calendar"].startswith("signal_call_calendar — after a mech BEAR or E-VOL")
    src = (S.ROOT / "scripts/backtest_study/f1_selection/regime/signal_call_calendar.py").read_text()
    assert S.REGISTRATION in ast.get_docstring(ast.parse(src))
    assert (S.ROOT / S.REGISTRATION).exists()
    assert S.DESIGNED_REFUSAL_EXIT_CODES == {3}


def test_banner_prints_the_registered_lines(capsys):
    S.banner({"K-BEAR": (S.NULL, ["PBO veto"]), "K-EVOL": (S.UNDERPOWERED, [])}, 0.612,
             {"K-BEAR": S.STILL_OPEN, "K-EVOL": S.STILL_OPEN})
    out = capsys.readouterr().out
    assert ">>> signal_call_calendar K-BEAR (call calendar after S-BEAR, 1.03 strike, 30/60 DTE, 21 sessions " \
           "or short expiry, 2022-02-01 to 2026-09-22): NULL <<<" in out
    assert ">>> signal_call_calendar K-EVOL (call calendar after S-EVOL" in out and "UNDERPOWERED <<<" in out
    assert ">>> signal_call_calendar PBO: 0.612 <<<" in out
    assert (">>> signal_call_calendar FORWARD (onsets from 2026-11-21, current sell-off out): "
            "K-BEAR STILL-OPEN K-EVOL STILL-OPEN <<<") in out
    assert out.count("second structure on one signal set; geometry set after Q4") == 4
