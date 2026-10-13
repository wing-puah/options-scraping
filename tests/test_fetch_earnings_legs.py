"""earnings_vol fetch planner: events -> contracts, on synthetic data. No network."""
from datetime import date, timedelta

from scripts.collector import fetch_earnings_legs as fe


def _sessions(start=date(2026, 1, 5), n=120, holidays=()):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5 and d not in holidays:
            out.append(d)
        d += timedelta(days=1)
    return out


SESS = _sessions()


def _closes(base=100.0):
    return {d: base + i for i, d in enumerate(SESS)}


def _plan(ann, session, closes=None, expiries=None, prices=None, rescaled=False):
    return fe.plan_event(
        "XYZ", ann, session, sessions=SESS, closes=_closes() if closes is None else closes,
        expiries=expiries or (lambda entry, e: fe.weekly_fridays(entry, e + timedelta(days=60))),
        prices=prices, rescaled=rescaled)


def _write(cache, t, x, k, r, days, price=100.0):
    path = fe.cache_path(cache, t, x, k, "Call" if r == "C" else "Put")
    rows = "".join(f"{d},1,{price}\n" for d in sorted(days, reverse=True))
    path.write_text("Time,Latest,Price~\n" + rows)
    return path


def test_event_session_bmo_amc_dmh():
    ann = date(2026, 3, 10)                      # Tuesday
    nxt = date(2026, 3, 11)
    assert fe.event_session(ann, "bmo", SESS) == ann
    assert fe.event_session(ann, "amc", SESS) == nxt
    assert fe.event_session(ann, "dmh", SESS) == nxt
    assert fe.event_session(ann, "unknown", SESS) is None


def test_amc_on_friday_rolls_to_monday():
    assert fe.event_session(date(2026, 3, 13), "amc", SESS) == date(2026, 3, 16)


def test_entry_is_five_sessions_before_E_skipping_holiday():
    sess = _sessions(holidays={date(2026, 3, 11)})
    e = date(2026, 3, 16)
    # sessions back from Mon 3/16: 3/13, 3/12, 3/10, 3/9, 3/6 -> entry 3/6
    assert fe.entry_session(e, sess) == date(2026, 3, 6)


def test_front_and_back_expiry():
    p, why = _plan(date(2026, 3, 10), "amc")     # E = Wed 3/11
    assert why == "" and p.e == date(2026, 3, 11) and p.entry == date(2026, 3, 4)
    assert p.front == date(2026, 3, 13)          # first Friday after E
    assert p.back == date(2026, 4, 10)           # >= front + 28d


def test_event_on_friday_front_is_next_friday():
    p, _ = _plan(date(2026, 3, 12), "amc")       # E = Fri 3/13
    assert p.e == date(2026, 3, 13) and p.front == date(2026, 3, 20)


# ── the candidate ladder ──────────────────────────────────────────────────────

def test_ladder_ordering_ties_lower_and_three_percent_bound():
    # 0.5: 101/101.5, 1: 101/102, 2.5: 100/102.5, 5: 100/105, 10: 100/110
    assert fe.strike_ladder(101.2) == (101.0, 101.5, 102.0, 100.0, 102.5)
    lad = fe.strike_ladder(101.2)
    assert 105.0 not in lad and 110.0 not in lad        # 3.8% and 8.7% away
    assert all(abs(k - 101.2) <= 0.03 * 101.2 for k in lad)
    # a tie goes to the lower strike: 102.25 is 0.25 from 102 and 102.5
    assert fe.strike_ladder(102.25)[:2] == (102.0, 102.5)
    # a 5-wide grid near 900 sits 5th: four finer candidates are nearer
    assert fe.strike_ladder(901.3).index(900.0) == 4
    assert fe.strike_ladder(115.0) == (115.0,)          # on every grid; 110/120 are > 3%


def test_ladder_holds_the_nearest_strike_of_every_grid():
    for close in (20.13, 47.9, 101.2, 233.33, 901.3, 1303.4):
        lad = fe.strike_ladder(close)
        for g in fe.LADDER_INCREMENTS:
            near = min((round(g * (close // g), 2), round(g * (close // g + 1), 2)),
                       key=lambda k: (abs(k - close), k))
            if abs(near - close) <= 0.03 * close:
                assert near in lad


def test_plan_candidates_come_from_the_entry_close():
    closes = _closes()
    p, _ = _plan(date(2026, 3, 10), "amc", closes=closes)
    assert p.candidates == fe.strike_ladder(closes[p.entry]) and p.close == closes[p.entry]


# ── the close basis ───────────────────────────────────────────────────────────

def _prices(entry, value, n_files=3, sessions=SESS, back=5):
    i = sessions.index(entry)
    return {d: [value] * n_files for d in sessions[max(0, i - back): i + 1]}


def test_rebases_x10_before_a_split_and_not_after():
    ann = date(2026, 3, 10)
    entry = _plan(ann, "amc")[0].entry
    closes = {d: 60.0 for d in SESS}                 # split-adjusted bars
    pre, _ = _plan(ann, "amc", closes=closes, prices=_prices(entry, 600.0))
    assert pre.factor == 10.0 and pre.rebased and pre.close == 600.0 and pre.close_adj == 60.0
    assert pre.candidates == fe.strike_ladder(600.0)
    post, _ = _plan(ann, "amc", closes=closes, prices=_prices(entry, 60.4))
    assert post.factor == 1.0 and not post.rebased and post.close == 60.0


def test_a_single_bad_price_file_does_not_rebase():
    ann = date(2026, 3, 10)
    entry = _plan(ann, "amc")[0].entry
    closes = {d: 60.0 for d in SESS}
    prices = _prices(entry, 60.0)
    prices[entry] = [60.0, 600.0, 60.1]               # one file prints x10
    p, _ = _plan(ann, "amc", closes=closes, prices=prices)
    assert p.factor == 1.0 and p.basis == ""
    # the only file on the only day printing x10 is one observation: not enough
    p2, _ = _plan(ann, "amc", closes=closes, prices={entry: [600.0]})
    assert p2.factor == 1.0 and p2.basis == "basis_unconfirmed"
    # a whole-chain glitch on the entry day is outvoted by the days before it
    glitch = _prices(entry, 60.0)
    glitch[entry] = [15.6] * 5                        # ~1/4, like SPY 177.54 vs 679.68
    p3, _ = _plan(ann, "amc", closes=closes, prices=glitch)
    assert p3.factor == 1.0


def test_no_price_near_entry():
    ann = date(2026, 3, 10)
    entry = _plan(ann, "amc")[0].entry
    i = SESS.index(entry)
    far = {SESS[i - 6]: [600.0] * 3}                  # six sessions back: outside the window
    closes = {d: 60.0 for d in SESS}
    assert _plan(ann, "amc", closes=closes, prices=far, rescaled=True)[1] == "no_unadjusted_close"
    p, why = _plan(ann, "amc", closes=closes, prices=far)
    assert why == "" and p.factor == 1.0 and p.basis == "basis_unchecked"
    # nearest earlier session within five is used when the entry day has none
    near = {SESS[i - 3]: [600.0] * 3, SESS[i - 4]: [600.0] * 3}
    assert _plan(ann, "amc", closes=closes, prices=near)[0].factor == 10.0


def test_nearest_factor():
    assert fe.nearest_factor(10.3) == 10.0
    assert fe.nearest_factor(0.101) == 0.1
    assert fe.nearest_factor(1.04) == 1.0
    assert fe.nearest_factor(7.0) is None             # no plausible factor within 5%


def test_holiday_friday_expiry_shifts_to_thursday():
    sess = set(_sessions(holidays={date(2026, 4, 3)}))   # Good Friday
    fr = fe.weekly_fridays(date(2026, 3, 30), date(2026, 4, 10), sess)
    assert fr == [date(2026, 4, 2), date(2026, 4, 10)]


def test_drops_are_labelled():
    assert _plan(date(2026, 3, 10), "unknown")[1] == "unknown_session"
    assert _plan(date(2026, 3, 10), "amc", closes={})[1] == "no_close"
    assert _plan(date(2026, 1, 6), "bmo")[1] == "no_entry_session"
    assert _plan(date(2026, 3, 10), "amc", expiries=lambda a, b: [])[1] == "no_expiry"


def test_nothing_after_entry_decides_basis_candidates_or_expiry():
    ann = date(2026, 3, 10)
    base = {d: 60.0 for d in SESS}
    p1, _ = _plan(ann, "amc", closes=base, prices=_prices(_plan(ann, "amc")[0].entry, 600.0))
    entry = p1.entry
    later_closes = {d: (v * 3 if d > entry else v) for d, v in base.items()}
    later_prices = _prices(entry, 600.0)
    for d in SESS:
        if d > entry:
            later_prices[d] = [60.0] * 9                 # a future "split" in Price~
    p2, _ = _plan(ann, "amc", closes=later_closes, prices=later_prices)
    assert (p1.close, p1.factor, p1.candidates, p1.front, p1.back) == \
        (p2.close, p2.factor, p2.candidates, p2.front, p2.back)

    seen = []

    def exp(entry, e):
        seen.append((entry, e))
        return fe.weekly_fridays(entry, e + timedelta(days=60))
    p3, _ = _plan(ann, "amc", expiries=exp)
    assert seen == [(p3.entry, p3.e)]


# ── the passes ────────────────────────────────────────────────────────────────

def _one_plan():
    big = _sessions(date(2026, 1, 5), 270)
    closes = {d: 101.2 for d in big}
    events = [(date(2026, 3, 10), "amc"), (date(2026, 3, 12), "unknown"),
              (date(2023, 12, 1), "bmo"), (date(2026, 9, 24), "amc")]
    tp = fe.plan_ticker("XYZ", events=events, sessions=big, closes=closes, close_source="t")
    return tp


def test_plan_ticker_window_and_seal():
    tp = _one_plan()
    assert tp.events_in_window == 3                 # 2023 event outside the window
    assert tp.dropped["unknown_session"] == 1 and tp.dropped["sealed"] == 1
    assert len(tp.plans) == 1 and tp.plans[0].candidates == (101.0, 101.5, 102.0, 100.0, 102.5)


def test_front_pass_width_and_resolution(tmp_path):
    tp = _one_plan()
    p = tp.plans[0]
    st = fe.LegStatus(tmp_path)
    _, front, back = fe.plan_phases([tp], st, width=2)
    assert front == {("XYZ", p.front, k, r) for k in (101.0, 101.5) for r in "CP"} and not back
    # 101 unlisted (call), 101.5 failed (put): both passed over; 102 cached without
    # an entry row: passed over; 100 confirmed -> ATM; 102.5 never targeted
    st = fe.LegStatus(tmp_path, unlisted={fe.contract_stem("XYZ", p.front, 101.0, "C")},
                      failed={fe.contract_stem("XYZ", p.front, 101.5, "P")})
    for r in "CP":
        _write(tmp_path, "XYZ", p.front, 102.0, r, [p.e])
        _write(tmp_path, "XYZ", p.front, 100.0, r, [p.entry, p.e])
    pick = fe.resolve_atm(p, st)
    assert pick.strike == 100.0 and [k for k, _ in pick.passed] == [101.0, 101.5, 102.0]
    # the 101.5 call is unfetched but its put failed: passed over, never targeted
    rows, front, back = fe.plan_phases([tp], st, width=4)
    assert front == set()
    assert back == {("XYZ", p.back, 100.0, r) for r in "CP"}
    assert rows["XYZ"].resolved == 1 and rows["XYZ"].front_failed == 1
    # --retry-failed: the failed put is unfetched again, so the walk re-targets
    # 101.5 (both legs not on disk) before reaching the confirmed 100
    st2 = fe.LegStatus(tmp_path, unlisted={fe.contract_stem("XYZ", p.front, 101.0, "C")})
    _, front2, back2 = fe.plan_phases([tp], st2, width=4)
    assert front2 == {("XYZ", p.front, 101.5, r) for r in "CP"} and back2 == set()
    assert len(fe.target_records(front2)) == 2


def test_back_pass_never_refetches_and_skips_failed(tmp_path):
    tp = _one_plan()
    p = tp.plans[0]
    for r in "CP":
        _write(tmp_path, "XYZ", p.front, 101.0, r, [p.entry])
    _write(tmp_path, "XYZ", p.back, 101.0, "C", [p.e])          # cached, no entry row
    st = fe.LegStatus(tmp_path, failed={fe.contract_stem("XYZ", p.back, 101.0, "P")})
    rows, front, back = fe.plan_phases([tp], st)
    assert front == set() and back == set()
    assert rows["XYZ"].back_cached == 1 and rows["XYZ"].back_failed == 1


def test_read_closes_accepts_both_schemas(tmp_path):
    at = tmp_path / "AT.csv"
    at.write_text("date,open,high,low,close,volume\n2024-01-02,1,1,1,10.5,9\n")
    bc = tmp_path / "BC.csv"
    bc.write_text("Time,Open,High,Low,Latest,Change\n2024-01-03,1,1,1,11.25,0\n")
    assert fe.read_closes(at) == {date(2024, 1, 2): 10.5}
    assert fe.read_closes(bc) == {date(2024, 1, 3): 11.25}
