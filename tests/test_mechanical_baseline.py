"""mechanical_baseline's rule, gates and verdict words, on synthetic data.

research/pre-registrations/f1_selection/benchmark/mechanical_baseline.md: the
weekly cadence, the expiry choice, the signal-date-only decision, the await
gate, ARM RND's pairing key, BOOK-BETTER's precedence and the window bounds.
No test reads the real exports or the option cache, and none touches the
network.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from scripts.backtest_study.f1_selection.benchmark import mechanical_baseline as M
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB
from scripts.backtest_study.f4_deployment import account_sim as AS
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF
from scripts.backtest_study.lib import era

TK = "SPY"


def chain_of(quotes: dict, ticker=TK) -> NTF.Chain:
    """`{expiry: {strike: {day: (mark, spot)}}}` -> a Chain of calls with a
    bid/ask on every quoted day."""
    idx = {(ticker, e): {float(k): {"C"} for k in ks} for e, ks in quotes.items()}
    ch = NTF.Chain(idx=idx)
    for e, ks in quotes.items():
        for k, days in ks.items():
            series = sorted((d, m) for d, (m, _s) in days.items())
            details = {d: {"_mark": m, "Price~": str(s), "Bid": str(m - 0.05),
                           "Ask": str(m + 0.05)} for d, (m, s) in days.items()}
            ch._memo[(ticker, e, round(float(k), 4), "Call")] = (series, details)
    return ch


def weekdays(lo: date, hi: date, skip=()) -> list[date]:
    out, d = [], lo
    while d <= hi:
        if d.weekday() < 5 and d not in skip:
            out.append(d)
        d += timedelta(days=1)
    return out


# ── cadence ──────────────────────────────────────────────────────────────────

def test_weekly_is_the_first_session_of_each_iso_week():
    # 2024-01-15 (MLK day) is not a session: that week's first session is Tuesday.
    sess = weekdays(date(2024, 1, 8), date(2024, 1, 26), skip={date(2024, 1, 15)})
    assert M.weekly_dates(sess) == {date(2024, 1, 8), date(2024, 1, 16), date(2024, 1, 22)}


def test_iso_week_straddling_new_year():
    # 2024-12-30 and 2025-01-02 share ISO week 2025-W01; 2025-01-01 is a holiday.
    sess = weekdays(date(2024, 12, 23), date(2025, 1, 10), skip={date(2024, 12, 25),
                                                                 date(2025, 1, 1)})
    w = M.weekly_dates(sess)
    assert date(2024, 12, 30) in w and date(2025, 1, 2) not in w
    assert date(2025, 1, 6) in w


def test_dip_weekly_keeps_only_weekly_dip_dates():
    sess = weekdays(date(2024, 2, 5), date(2024, 2, 23))
    weekly = M.weekly_dates(sess)
    dip = {date(2024, 2, 5): "below", date(2024, 2, 12): "above",
           date(2024, 2, 19): None}.get
    got, c = M.signal_dates(M.DIP_WEEKLY, sess, weekly, dip, sess[0], sess[-1])
    assert got == [date(2024, 2, 5)]
    assert c == {"not_a_dip": 1, "dip_unlabelled": 1}
    daily, _ = M.signal_dates(M.DAILY, sess, weekly, dip, sess[0], sess[-1])
    assert daily == sess[:-1]            # the last session has no D+1


# ── expiry ───────────────────────────────────────────────────────────────────

def test_expiry_nearest_target_from_the_entry_day():
    # entry 2026-01-06: Feb 20 is 45 days out, Mar 20 is 73 -> Mar 20 for 65
    assert M.rule_expiry(date(2026, 1, 6), 65) == date(2026, 3, 20)
    assert M.rule_expiry(date(2026, 1, 6), 45) == date(2026, 2, 20)


def test_expiry_tie_goes_to_the_earlier():
    entry = date(2026, 1, 28)     # Mar 20 is 51 days out, Apr 17 is 79: both 14 off 65
    assert (date(2026, 3, 20) - entry).days == 51
    assert (date(2026, 4, 17) - entry).days == 79
    assert M.rule_expiry(entry, 65) == date(2026, 3, 20)


def test_expiry_is_measured_from_d_plus_1_not_d():
    # D = Friday 2026-01-30; the entry day is the next session, Monday 02-02.
    sess = weekdays(date(2026, 1, 26), date(2026, 2, 6))
    exp = date(2026, 4, 17)
    ch = chain_of({exp: {k: {date(2026, 1, 30): (5.0, 100.0)} for k in (100.0, 105.0)}})
    book = M.RuleBook(ch, set(), sess)
    x = book.trade(TK, date(2026, 1, 30), 65)
    assert x.entry == date(2026, 2, 2) and x.expiry == M.rule_expiry(date(2026, 2, 2), 65)


# ── decision on D only ───────────────────────────────────────────────────────

def _decision_chain(D: date, exp: date, post_spot: float) -> NTF.Chain:
    pre = D - timedelta(days=3)
    post = D + timedelta(days=1)
    q = {k: {pre: (5.0, 100.0), D: (5.0, 100.0), post: (6.0, post_spot)}
         for k in (100.0, 105.0, 120.0, 125.0)}
    q[102.5] = {post: (4.0, post_spot)}            # listed only after D
    return chain_of({exp: q})


def test_decision_uses_only_rows_on_or_before_d():
    D, entry = date(2026, 1, 5), date(2026, 1, 6)
    exp = M.rule_expiry(entry, 65)
    ev = {NTF.contract_stem(TK, exp, k, "Call") for k in (97.5, 107.5, 110.0, 95.0)}
    ch = _decision_chain(D, exp, post_spot=120.0)
    x = M.select(ch, ev, MB.UniverseSpot(ch), TK, D, entry, 65)
    assert (x.status, x.k_long, x.k_short) == ("built", 100.0, 105.0)
    # the same choice on a cache cut at D (no look-ahead) ...
    cut = MB.AsOfChain(ch, D)
    y = M.select(cut, ev, MB.UniverseSpot(cut), TK, D, entry, 65)
    assert (y.status, y.k_long, y.k_short) == (x.status, x.k_long, x.k_short)
    # ... and a different D+1 spot changes nothing
    ch2 = _decision_chain(D, exp, post_spot=80.0)
    z = M.select(ch2, ev, MB.UniverseSpot(ch2), TK, D, entry, 65)
    assert (z.k_long, z.k_short) == (100.0, 105.0)


def test_blind_check_passes_on_a_decided_trade():
    D = date(2026, 1, 5)
    sess = [D, date(2026, 1, 6)]
    exp = M.rule_expiry(date(2026, 1, 6), 65)
    ev = {NTF.contract_stem(TK, exp, k, "Call") for k in (97.5, 107.5, 110.0, 95.0)}
    book = M.RuleBook(_decision_chain(D, exp, 120.0), ev, sess)
    assert M.blind_check(book, [book.trade(TK, D, 65)]) == []


def test_no_spot_on_d_is_a_drop():
    D, entry = date(2026, 1, 5), date(2026, 1, 6)
    exp = M.rule_expiry(entry, 65)
    ch = chain_of({exp: {100.0: {entry: (5.0, 100.0)}}})        # quoted only on D+1
    x = M.select(ch, set(), MB.UniverseSpot(ch), TK, D, entry, 65)
    assert (x.status, x.reason) == ("drop", "no_spot")


# ── the await gate ───────────────────────────────────────────────────────────

def _awaiting_book():
    """A primary week in window A whose ATM strike is not cached."""
    D, entry = date(2024, 1, 16), date(2024, 1, 17)
    sess = [D, entry]
    exp = M.rule_expiry(entry, 65)
    ch = chain_of({exp: {k: {D: (5.0, 102.0)} for k in (95.0, 100.0, 105.0, 110.0)}})
    return M.RuleBook(ch, set(), sess), D, sess


def test_await_gate_refuses_every_price():
    book, D, sess = _awaiting_book()
    x = book.trade(TK, D, 65)
    assert x.status == "await" and x.fetch
    weekly = M.weekly_dates(sess)
    assert [a.signal for a in book.primary_awaiting(weekly, lambda d: None)] == [D]
    with pytest.raises(M.AwaitingScrape):
        book.price(x)
    with pytest.raises(M.AwaitingScrape):
        book.open_outcomes(weekly, lambda d: None)
    with pytest.raises(M.AwaitingScrape):          # still shut after the refusal
        book.price(x)


def test_fetch_plan_names_the_awaited_strike():
    book, _D, sess = _awaiting_book()
    t = M.fetch_targets(book, M.weekly_dates(sess), lambda d: None, "primary")
    assert t and all(r["opt_type"] == "Call" and r["ticker"] == TK for r in t)
    assert t[0]["category"].startswith("SPY:weekly:65:A")


def test_main_prints_no_outcome_while_a_primary_trade_awaits(monkeypatch, capsys):
    book, D, sess = _awaiting_book()
    monkeypatch.setattr(M, "build_calendar",
                        lambda: (sess, M.weekly_dates(sess), lambda d: None))
    monkeypatch.setattr(M.NTF, "Chain", lambda *a, **k: book.chain)
    monkeypatch.setattr(M.NTF, "unlisted_evidence", lambda *a, **k: set())

    def refuse(*a, **k):
        raise SystemExit(3)
    monkeypatch.setattr(M, "load_book", refuse)

    def boom(*a, **k):
        raise AssertionError("outcomes reached while a primary trade awaits")
    monkeypatch.setattr(M, "outcomes", boom)
    monkeypatch.setattr(M, "price_trade", boom)
    assert M.main(["--no-v3"]) == 0
    out = capsys.readouterr().out
    assert f"VERDICT: {M.NOT_BUILT}" in out
    for word in ("meanR", "CI95", "alpha", "realized $", "gain "):
        assert word not in out


# ── ARM RND pairing ──────────────────────────────────────────────────────────

def test_rnd_pairs_only_on_matching_entry_day_and_expiry():
    e, x = date(2026, 3, 20), date(2026, 1, 6)
    assert M.rnd_matches(x, e, x, e)
    assert not M.rnd_matches(x, e, x + timedelta(days=1), e)      # entry day differs
    assert not M.rnd_matches(x, e, x, date(2026, 4, 17))          # expiry differs
    assert not M.rnd_matches(None, e, x, e)
    assert not M.rnd_matches(x, e, None, e)


def test_rnd_overlap_matches_signal_date_entry_and_expiry():
    D, entry = date(2026, 1, 5), date(2026, 1, 6)
    exp = M.rule_expiry(entry, 65)
    sess = [D, entry, date(2026, 1, 7)]
    ev = {NTF.contract_stem(TK, exp, k, "Call") for k in (97.5, 107.5, 110.0, 95.0)}
    book = M.RuleBook(_decision_chain(D, exp, 120.0), ev, sess)

    class S:
        def __init__(self, d, entry_day):
            self.date, self.entry_day = d.isoformat(), entry_day
    good, late, other = S(D, entry), S(D, entry + timedelta(days=1)), S(D, entry)
    b = MB.EraBuild(era="v4", slots=[good, late, other],
                    m={}, u_slot=[(D.isoformat(), exp, ""), (D.isoformat(), exp, ""),
                                  (D.isoformat(), date(2026, 4, 17), "")],
                    u={(D.isoformat(), "AAA", exp): MB.Wrap("built"),
                       (D.isoformat(), "AAA", date(2026, 4, 17)): MB.Wrap("await")},
                    universe={D.isoformat(): [("AAA", "stocks")]}, seal="")
    o = M.rnd_overlap(book, b, M.DAILY, 65, M.weekly_dates(sess))
    assert o == dict(dates=1, wraps=1, built=1)


# ── verdict words ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("x,h,bk,want", [
    ("PROFITABLE", "ALPHA", "TRAILS-BOOK", "BOOK-BETTER"),
    ("NULL", "DRIFT-ONLY", "TRAILS-BOOK", "BOOK-BETTER"),
    ("LOSES", "NEGATIVE-ALPHA", "TRAILS-BOOK", "BOOK-BETTER"),
    ("PROFITABLE", "ALPHA", "BEATS-BOOK", "REPLACEMENT-CANDIDATE"),
    ("PROFITABLE", "ALPHA", "NULL", "REPLACEMENT-CANDIDATE"),
    ("PROFITABLE", "DRIFT-ONLY", "NULL", "DRIFT-REPLACEMENT"),
    ("NULL", "ALPHA", "BEATS-BOOK", "NO-REPLACEMENT"),
    ("LOSES", "DRIFT-ONLY", "NULL", "NO-REPLACEMENT"),
    ("PROFITABLE", "ALPHA", M.NOT_BUILT, M.NOT_BUILT),
])
def test_study_token_book_better_first(x, h, bk, want):
    assert M.study_token(x, h, bk) == want


def _rows(vals, start=date(2024, 1, 10)):
    return [dict(date=(start + timedelta(days=7 * i)).isoformat(), R=v)
            for i, v in enumerate(vals)]


def test_x_vs_zero_tokens():
    assert M.grade_vs_zero(_rows([0.1] * 39), [])["token"] == M.UNDERPOWERED
    up = M.grade_vs_zero(_rows([0.30, 0.20] * 25), _rows([0.1, 0.2] * 10, date(2022, 3, 2)))
    assert up["token"] == "PROFITABLE" and up["c4"] and up["c4_alt"]
    down = M.grade_vs_zero(_rows([-0.30, -0.20] * 25), [])
    assert down["token"] == "LOSES"
    noise = M.grade_vs_zero(_rows([1.0, -1.0] * 25), [])
    assert noise["token"] == M.NULL
    # C4 fails when window B's CI sits wholly below zero: UNWORDED, not PROFITABLE
    bad_b = M.grade_vs_zero(_rows([0.30, 0.20] * 25), _rows([-0.3, -0.2] * 10, date(2022, 3, 2)))
    assert not bad_b["c4"] and bad_b["token"] == M.UNWORDED


def test_paired_tokens():
    rows = [dict(date=f"2025-{m:02d}-{d:02d}", R_T=0.3, R_C=0.1 + 0.01 * (d % 3))
            for m in (1, 5, 6, 7, 8, 9) for d in range(1, 9)]
    g = M.grade_paired(rows)
    assert M.paired_token(g, "BEATS-BOOK", "TRAILS-BOOK") == "BEATS-BOOK"
    inv = [dict(r, R_T=r["R_C"], R_C=r["R_T"]) for r in rows]
    assert M.paired_token(M.grade_paired(inv), "BEATS-BOOK", "TRAILS-BOOK") == "TRAILS-BOOK"
    assert M.paired_token(M.grade_paired(rows[:20]), "B", "T") == M.UNDERPOWERED


def test_alpha_grade_recovers_a_known_intercept():
    import random
    rng = random.Random(1)
    months = []
    for i in range(36):
        m = rng.gauss(0.01, 0.04)
        months.append((f"{2024 + i // 12}-{i % 12 + 1:02d}", 0.02 + 0.5 * m
                       + rng.gauss(0, 0.002), m))
    g = M.grade_alpha(months, n=2000)
    assert abs(g["alpha"] - 0.02) < 0.003 and abs(g["beta"] - 0.5) < 0.05
    assert g["token"] == "ALPHA"
    flat = [(mo, 0.5 * m + rng.gauss(0, 0.01), m) for mo, _x, m in months]
    assert M.grade_alpha(flat, n=2000)["token"] in ("DRIFT-ONLY", "NEGATIVE-ALPHA", "ALPHA",
                                                    M.UNWORDED)
    assert M.grade_alpha(months[:23])["token"] == M.UNDERPOWERED


def test_forward_is_still_open_below_the_floor():
    assert M.forward_token([0.5] * 29)[0] == "STILL-OPEN"
    assert M.forward_token([0.5, 0.6] * 40)[0] == "FORWARD-HOLDS"


# ── windows and the seal ─────────────────────────────────────────────────────

def test_windows_are_contiguous_and_stop_before_the_seal():
    a_lo, a_hi = M.WINDOWS["A"]
    b_lo, b_hi = M.WINDOWS["B"]
    assert b_hi + timedelta(days=1) == a_lo
    assert a_hi.isoformat() < era.SEAL_START == "2026-09-23"
    assert era.is_withheld("2026-09-23") and not era.is_withheld(a_hi.isoformat())
    sess = weekdays(date(2026, 9, 21), date(2026, 9, 25))
    got, _ = M.signal_dates(M.DAILY, sess, M.weekly_dates(sess), lambda d: None, a_lo, a_hi)
    assert got == [date(2026, 9, 21), date(2026, 9, 22)]
    assert M.in_window(date(2024, 1, 9), "B") and not M.in_window(date(2024, 1, 9), "A")
    assert M.FORWARD_START == date(2026, 10, 27) and era.is_withheld("2026-10-27")


def test_twelve_cells_and_the_primary():
    assert len(M.CELLS) == 12 and M.PRIMARY in M.CELLS
    assert M.PRIMARY == M.Cell(("SPY",), "weekly", 65)


# ── sizing: S-STOP is production's own contract count ───────────────────────

@pytest.mark.parametrize("debit", [3.0, 5.0, 8.88, 13.4, 14.0, 20.0])
def test_s_stop_sizes_as_production(debit):
    from scripts.backtest.legs import Leg
    from scripts.backtest.simulate import _size_contracts
    from scripts.backtest_study.f3_structure import structure_sweep as SS
    sim_cfg = SS.load_sim_cfg()
    legs = [Leg(1, TK, date(2026, 3, 20), 600.0, "Call"),
            Leg(-1, TK, date(2026, 3, 20), 630.0, "Call")]
    budget = M.STOP_1000 / sim_cfg["stop_loss"]
    assert AS.risk_contracts(debit * 100, budget) == _size_contracts(debit, legs, sim_cfg)


# ── the account layer runs on account_sim's own machinery ───────────────────

def _priced(signal: date, debit: float, drift: float) -> M.Priced:
    """A synthetic priced 1-lot SPY call vertical (no cache, no pricing)."""
    from scripts.backtest.helpers import _weekday_grid
    from scripts.backtest_study.lib.harness import Trade
    from scripts.backtest_study.lib.replay_basis import bounded
    from scripts.backtest_study.f3_structure import structure_sweep as SS
    exp = M.rule_expiry(signal + timedelta(days=1), 65)
    grid = _weekday_grid(signal, exp)
    marks = [round(debit * (1 + drift * i / len(grid)), 4) for i in range(len(grid))]
    row = {"signal_date": signal.isoformat(), "ticker": TK, "structure": MB.STRUCTURE,
           "entry_option_price": f"{debit:.4f}", "contracts": "1",
           "dte_entry": str((exp - grid[0]).days),
           "legs": f"{TK}:{exp.isoformat()}:600:C +1\n{TK}:{exp.isoformat()}:630:C -1",
           "daily_price_csv": ",".join(f"{m:.4f}" for m in marks),
           "daily_pnl_csv": ",".join(f"{(m - debit) * 100:.2f}" for m in marks),
           "delta": "0.30", "entry_underlying": "600", "path_data_end": "",
           "max_loss_per_contract": f"{debit * 100:.2f}"}
    t = bounded(Trade(row))
    sim_cfg = SS.load_sim_cfg()
    prof, _ = SS.exit_profile(sim_cfg, t.entry_net, signal, MB.STRUCTURE)
    x = M.XTrade(TK, signal, grid[0], exp, 65, "built", k_long=600.0, k_short=630.0)
    return M.Priced(x=x, row=row, t=t, entry_day=grid[0], exit_reason="", days_held=1,
                    exit_sess=grid[0], R_gross=0.0, R_net=0.0, commission=2.6,
                    R_rnd=0.0, profile=prof)


def test_account_variants_and_monthly_alpha_run_on_synthetic_trades():
    from scripts.backtest_study.f3_structure import structure_sweep as SS
    sim_cfg = SS.load_sim_cfg()
    st = AS.load_settings(AS.DEFAULT_CONFIG)
    ps = [_priced(date(2024, 1, 16) + timedelta(days=7 * i), 4.0 + (i % 3), 0.4)
          for i in range(30)]
    recs = M.account_records(ps)
    ch = NTF.Chain(idx={})
    for v in ("S-1", "S-STOP", "S-500-F2", "S-500-F3"):
        sim = M.run_account(recs, st, v, sim_cfg, ch, set())
        assert len(sim.signal_pos) + len(sim.skipped) == len(recs)    # all accounted for
    s1 = M.run_account(recs, st, "S-1", sim_cfg, ch, set(), caps=False)
    assert len(s1.signal_pos) == len(recs) and all(p.contracts == 1 for p in s1.signal_pos)
    f2 = M.run_account(recs, st, "S-500-F2", sim_cfg, ch, set(), caps=False)
    assert all(p.rec["max_loss_per_contract"] <= M.BUDGET_500 for p in f2.signal_pos)
    closes = {d: 400.0 + 0.1 * i for i, d in enumerate(weekdays(date(2023, 12, 1),
                                                                date(2025, 6, 30)))}
    months = M.monthly_series(s1, closes, st.capital, sim_cfg, start=M.WINDOWS["A"][0])
    assert months[0][0] == "2024-01" and all(len(m) == 3 for m in months)
