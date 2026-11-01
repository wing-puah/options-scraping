"""selloff_put_diagonal: the trigger and its arming, the calm weeks, strike and
expiry selection, the leg-path walker (rolls, put exit, expiry marks), the
package R, the await gate, the grading words, and the collector's dry run.

Synthetic chains only, except the census test, which reads the committed SPY
close tables and checks the registration's nine trigger days and 154 calm
weeks. No network; no option cache is read.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from scripts.backtest.shared import history
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB
from scripts.backtest_study.f1_selection.regime import selloff_put_diagonal as S
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF
from scripts.collector.study_legs import fetch_selloff_put_diagonal_legs as F


# ── helpers ─────────────────────────────────────────────────────────────────

def weekdays(lo: date, hi: date) -> list[date]:
    out, d = [], lo
    while d <= hi:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def contract(quotes: dict) -> tuple[list, dict]:
    """`(series, details)` from `{date: (bid, ask)}`; `None` ask = no quote."""
    series, details = [], {}
    for d in sorted(quotes):
        bid, ask = quotes[d]
        mid = (bid + ask) / 2 if ask is not None and bid > 0 else None
        row = {"Bid": bid, "Ask": ask, "Latest": mid or 0.0, "Volume": 0, "_mark": mid}
        details[d] = row
        if mid is not None:
            series.append((d, mid))
    return series, details


def chain_of(contracts: dict) -> NTF.Chain:
    """A Chain over `{(opt, expiry, strike): {date: (bid, ask)}}`, no files."""
    idx: dict = {}
    for (opt, exp, k) in contracts:
        idx.setdefault(("SPY", exp), {}).setdefault(float(k), set()).add(opt[0])
    ch = NTF.Chain(idx=idx)
    for (opt, exp, k), q in contracts.items():
        ch._memo[("SPY", exp, round(float(k), 4), opt)] = contract(q)
    return ch


def rule(sessions, disarms=(), triggers=()):
    n = len(sessions)
    return S.RuleState(sessions, [0.0] * n, [False] * n, list(triggers), list(disarms))


# ── the trigger ─────────────────────────────────────────────────────────────

def test_arm_states_arms_once_and_disarms_above_recover():
    dd = [None, -0.01, -0.05, -0.07, -0.03, -0.06, -0.019, -0.051, -0.02, -0.01]
    armed, trig, dis = S.arm_states(dd, -0.05, -0.02)
    assert trig == [2, 7]          # -0.06 at 5 does not re-trigger while armed
    assert dis == [6, 9]           # -0.02 at 8 is not above -0.02
    assert armed == [False, False, True, True, True, True, False, True, True, False]


def test_calm_days_take_the_first_qualifying_session_of_each_week():
    sessions = weekdays(date(2024, 1, 1), date(2024, 1, 19))
    n = len(sessions)
    dd = [-0.03] * n
    dd[2] = -0.01      # Wed of week 1
    dd[3] = 0.0        # Thu of week 1: not first
    dd[5] = -0.019     # Mon of week 2
    rs = S.RuleState(sessions, dd, [False] * n, [], [])
    rs.armed[5] = True  # armed: not calm
    dd[7] = -0.02       # Wed of week 2, exactly -2%: within
    got = S.calm_days(rs, sessions[0])
    assert got == [sessions[2], sessions[7]]


def test_census_reproduces_the_registered_triggers_and_calm_weeks():
    closes = S.MBL.load_closes()
    if not closes or max(closes) < S.IN_SAMPLE[1]:
        pytest.skip("SPY close tables not present")
    rs = S.rule_state(closes, S.PRIMARY_TRIGGER)
    assert tuple(S.trigger_days(rs, *S.IN_SAMPLE)) == S.REGISTERED_TRIGGERS
    assert len(S.calm_days(rs, *S.IN_SAMPLE)) == S.REGISTERED_CALM_WEEKS


def test_g_hash_passes_and_catches_an_edit(monkeypatch):
    assert S.gate_hash() == []
    defs = {k: dict(v) for k, v in S.IBH.EPISODE_DEFS.items()}
    defs["E-DD5"]["trigger"] = -0.06
    monkeypatch.setattr(S.IBH, "EPISODE_DEFS", defs)
    assert S.gate_hash()


# ── selection ───────────────────────────────────────────────────────────────

def test_roll_days_and_long_expiries():
    assert S.roll_days(date(2024, 1, 11), 3) == [date(2024, 2, 16), date(2024, 3, 15),
                                                 date(2024, 4, 19)]
    le = S.long_expiries(date(2024, 1, 11))
    # nearest 365 first; a LEAP past 365 is walked too (no upper cap); nothing under 270.
    assert le[0] == date(2025, 1, 17)
    assert date(2026, 1, 16) in le and date(2024, 10, 18) in le
    assert all((e - date(2024, 1, 11)).days >= 270 for e in le)
    dist = [abs((e - date(2024, 1, 11)).days - 365) for e in le]
    assert dist == sorted(dist)


def test_put_walk_and_parity_with_the_call_walk():
    exp, asof = date(2024, 2, 16), date(2024, 1, 10)
    q = {asof: (1.0, 1.1)}
    ch = chain_of({("Call", exp, 95): q, ("Call", exp, 100): q, ("Call", exp, 105): q,
                   ("Put", exp, 100): q, ("Put", exp, 101): {date(2024, 1, 20): (1, 1.1)}})
    ev = {NTF.contract_stem("SPY", exp, 99, "Call")}
    for target in (95.2, 100.4, 104.0, 98.9, 102.6):
        mine = S.nearest_listed(ch, ev, exp, target, 100.0, asof, "Call")
        theirs = MB.nearest_listed(ch, ev, "SPY", exp, target, 100.0, asof)
        assert (mine.status, mine.strike) == (theirs.status, theirs.strike)
    # 101P is cached but first quotes after asof: not listed yet, step on to 100P.
    assert S.nearest_listed(ch, set(), exp, 101.0, 100.0, asof, "Put").strike == 100.0
    aw = S.nearest_listed(ch, set(), exp, 103.0, 100.0, asof, "Put")
    assert aw.status == "await" and aw.fetch == (("Put", exp, 103.0),)


def test_listing_state():
    asof = date(2024, 1, 10)
    early, late, empty = date(2025, 1, 17), date(2024, 12, 20), date(2024, 11, 15)
    ch = chain_of({("Call", early, 90): {date(2023, 12, 1): (11, 11.2)},
                   ("Call", late, 90): {date(2024, 3, 1): (11, 11.2)}})
    L = S.Listing(ch)
    assert L.state(set(), early, "Call", 90, 100, asof)[0] == "yes"
    assert L.state(set(), late, "Call", 90, 100, asof)[0] == "no"
    st, fetch = L.state(set(), empty, "Call", 91, 100, asof)
    assert st == "await" and fetch == (("Call", empty, 90.0),)
    ev = {NTF.contract_stem("SPY", empty, 90, "Call")}
    assert L.state(ev, empty, "Call", 91, 100, asof)[0] == "no"


# ── the walker ──────────────────────────────────────────────────────────────

D, ENTRY = date(2024, 1, 10), date(2024, 1, 11)
E1, E2, E3 = date(2024, 2, 16), date(2024, 3, 15), date(2024, 4, 19)
LONG = ("Call", date(2024, 12, 20), 90.0)
PUT = ("Put", E1, 100.0)
SHORTS = [("Call", E1, 105.0), ("Call", E2, 105.0), ("Call", E3, 105.0)]
SESSIONS = weekdays(date(2024, 1, 2), date(2024, 6, 28))
CLOSES = {d: 100.0 for d in SESSIONS}
CLOSES.update({E2: 107.0, E3: 110.0})


def package(**kw) -> S.Package:
    base = dict(arm="K", signal=D, entry=ENTRY, geom=S.Geom(), status="built", put=PUT,
                long=LONG, shorts=list(SHORTS), rolls=[E1, E2, E3])
    base.update(kw)
    return S.Package(**base)


def walker_chain(put_quotes=None) -> NTF.Chain:
    return chain_of({
        PUT: put_quotes or {ENTRY: (2.9, 3.1), date(2024, 1, 22): (4.9, 5.1)},
        LONG: {ENTRY: (11.9, 12.1), E3: (15.9, 16.1)},
        SHORTS[0]: {ENTRY: (0.95, 1.05), E1: (0.0, 0.05)},     # junk at expiry
        SHORTS[1]: {E1: (0.9, 1.1), E2: (2.0, 2.2)},           # clean at expiry
        SHORTS[2]: {E2: (1.4, 1.6)},                            # no row at expiry
    })


def test_walker_rolls_the_short_and_marks_each_expiry():
    rs = rule(SESSIONS, disarms=[date(2024, 1, 22)])
    p = S.walk_package(walker_chain(), package(), rs, SESSIONS, CLOSES)
    assert isinstance(p, S.Priced), p
    assert p.entry_day == ENTRY
    assert (p.put_in, p.put_out, p.put_exit, p.put_reason) == (3.0, 5.0, date(2024, 1, 22),
                                                               "disarm")
    assert p.short_in == pytest.approx([1.0, 1.0, 1.5])
    # E1 junk -> intrinsic at 100 = 0; E2 clean -> mid 2.1; E3 no row -> intrinsic at 110.
    assert p.short_out == pytest.approx([0.0, 2.1, 5.0])
    assert (p.long_in, p.long_out) == pytest.approx((12.0, 16.0))
    assert p.diag_debit == pytest.approx(11.0)
    assert p.diag_pnl == pytest.approx(4.0 + 1.0 - 1.1 - 3.5)
    assert p.tags["intrinsic"] == 2 and p.clamp_bound == 0


def test_package_R_views_and_commission():
    rs = rule(SESSIONS, disarms=[date(2024, 1, 22)])
    p = S.walk_package(walker_chain(), package(), rs, SESSIONS, CLOSES)
    assert S.package_R(p, net=False) == pytest.approx((2.0 + 0.4) / 14.0)
    assert S.package_R(p) == pytest.approx((240.0 - 0.65 * 10) / 1400.0)
    assert S.package_R(p, 0) == pytest.approx((40.0 - 0.65 * 8) / 1100.0)
    assert S.package_R(p, 1, diag=False) == pytest.approx((200.0 - 1.3) / 300.0)
    assert S.package_R(p, 2) == pytest.approx((440.0 - 0.65 * 12) / 1700.0)
    with pytest.raises(ValueError):
        S.package_R(p, 0, diag=False)


def test_walker_moves_the_entry_inside_the_window_and_drops_without_one():
    late = {date(2024, 1, 12): (2.9, 3.1), date(2024, 1, 22): (4.9, 5.1)}
    ch = walker_chain(late)
    for key in (LONG, SHORTS[0]):
        series, det = ch._memo[("SPY", key[1], key[2], key[0])]
        det[date(2024, 1, 12)] = dict(det[ENTRY])
        series.append((date(2024, 1, 12), det[ENTRY]["_mark"]))
    rs = rule(SESSIONS, disarms=[date(2024, 1, 22)])
    p = S.walk_package(ch, package(), rs, SESSIONS, CLOSES)
    assert p.entry_day == date(2024, 1, 12)
    none = walker_chain({date(2024, 2, 1): (2.9, 3.1)})
    assert S.walk_package(none, package(), rs, SESSIONS, CLOSES) == S.SIM.NO_COMMON_ENTRY_DAY


def test_put_exit_day_rules():
    rs = rule(SESSIONS, disarms=[ENTRY])
    # A disarm on the entry day exits the put the next session.
    assert S.put_exit_day(rs, SESSIONS, D, ENTRY, E1) == (date(2024, 1, 12), "disarm")
    calm = rule(SESSIONS)
    # 36 DTE -> int(27.0) = 27 calendar days -> 2024-02-07 (a Wednesday).
    assert S.put_exit_day(calm, SESSIONS, D, ENTRY, E1) == (date(2024, 2, 7), "time_75")
    short = date(2024, 1, 12)
    assert S.put_exit_day(calm, SESSIONS, D, ENTRY, short) == (short, "expiry")


def test_leg_mark_expiry_rule():
    exp = date(2024, 2, 16)
    leg = S._leg("Put", exp, 100.0)
    ch = chain_of({("Put", exp, 100.0): {exp: (0.0, 0.3)}})
    assert S.leg_mark(ch, leg, exp, 97.5) == (2.5, "intrinsic")
    ch = chain_of({("Put", exp, 100.0): {exp: (2.4, 2.6)}})
    assert S.leg_mark(ch, leg, exp, 97.5) == (pytest.approx(2.5), "close_mid")


# ── the await gate ──────────────────────────────────────────────────────────

def test_await_gate_closes_pricing_until_no_primary_trade_awaits():
    book = S.Book(walker_chain(), set(), CLOSES)
    pk = package()
    with pytest.raises(S.AwaitingScrape):
        book.price(pk)
    book.primary_awaiting = lambda: [package(status="await")]
    with pytest.raises(S.AwaitingScrape):
        book.open_outcomes()
    with pytest.raises(S.AwaitingScrape):
        book.price(pk)
    book.primary_awaiting = lambda: []
    book.open_outcomes()
    book.rules[S.PRIMARY_TRIGGER] = rule(SESSIONS, disarms=[date(2024, 1, 22)])
    assert isinstance(book.price(pk), S.Priced)


def test_census_counts_await_open_and_substitution():
    pks = [package(status="await", fetch=(("Call", E1, 105.0),)),
           package(status="await", fetch=(("Call", E1, 105.0), ("Put", E1, 99.0))),
           package(status="open", reason="open_at_data_end"),
           package(subst=True)]
    k = S.census_counts(pks)
    assert (k["c"]["await_"], k["c"]["open"], k["c"]["built"], k["c"]["subst"]) == (2, 1, 1, 1)
    assert len(k["fetch"]) == 2


# ── grading ─────────────────────────────────────────────────────────────────

def _rows(vals, start=date(2022, 8, 26)):
    big = list(S.BIG_EPISODES)
    dates = big + [start + timedelta(days=30 * i + 1) for i in range(len(vals) - 2)]
    return [dict(date=d.isoformat(), R=v) for d, v in zip(dates, vals)]


def test_vs_zero_tokens():
    g = S.grade_vs_zero(_rows([0.3] * 7), n=200)
    assert S.token(g, "PAYS", "LOSES", "mean") == S.UNDERPOWERED
    g = S.grade_vs_zero(_rows([0.3, 0.4, 0.2, 0.5, 0.3, 0.6, 0.2, 0.4, 0.3]), n=500)
    assert S.token(g, "PAYS", "LOSES", "mean") == "PAYS"
    g = S.grade_vs_zero(_rows([-0.3, -0.4, -0.2, -0.5, -0.3, -0.6, -0.2, -0.4, -0.3]), n=500)
    assert S.token(g, "PAYS", "LOSES", "mean") == "LOSES"
    g = S.grade_vs_zero(_rows([0.5, -0.4, 0.2, -0.5, 0.3, -0.6, 0.2, -0.1, 0.3]), n=500)
    assert S.token(g, "PAYS", "LOSES", "mean") == S.NULL


def test_c3_big_episode_cut_and_unworded():
    g = dict(c0=True, c1=True, c2=True, c3=False, mean=0.2)
    assert S.token(g, "PAYS", "LOSES", "mean") == S.UNWORDED
    rows = _rows([3.0, 3.0, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1])
    g = S.grade_vs_zero(rows, n=200)
    assert g["mean"] > 0 and g["cut_mean"] < 0 and not g["c3"]


def test_vs_calm_and_put_contribution():
    k = _rows([0.5, 0.6, 0.4, 0.5, 0.7, 0.5, 0.6, 0.4, 0.5])
    c = [dict(date=(date(2022, 3, 7) + timedelta(weeks=i)).isoformat(), R=(-1) ** i * 0.1)
         for i in range(60)]
    g = S.grade_vs_calm(k, c, n=500)
    assert g["c0"] and S.token(g, "SELLOFF-ENTRY-HELPS", "SELLOFF-ENTRY-HURTS") == \
        "SELLOFF-ENTRY-HELPS"
    assert not S.grade_vs_calm(k, c[:59], n=50)["c0"]
    pr = [dict(date=r["date"], R_T=r["R"], R_C=r["R"] + 0.2) for r in k]
    gp = S.grade_paired(pr, n=500)
    assert S.token(gp, "PUT-ADDS", "PUT-COSTS") == "PUT-COSTS"


def test_study_and_forward_tokens():
    assert S.study_token(S.NOT_BUILT, "x", "y", None, None) == S.NOT_BUILT
    assert S.study_token("PAYS", "SELLOFF-ENTRY-HELPS", S.NULL, None, None) == \
        "CANDIDATE (PROVISIONAL)"
    assert S.study_token("PAYS", "SELLOFF-ENTRY-HELPS", "PUT-COSTS", "PAYS",
                         "SELLOFF-ENTRY-HELPS") == "DIAGONAL-ONLY (PROVISIONAL)"
    assert S.study_token(S.NULL, S.NULL, S.NULL, S.NULL, S.NULL) == "NO-EDGE (PROVISIONAL)"
    cand = "CANDIDATE (PROVISIONAL)"
    assert S.forward_token(cand, [0.2, 0.3], [0.1]) == "STILL-OPEN"
    assert S.forward_token(cand, [0.2, 0.3, 0.1], [0.1, 0.0, 0.2]) == "CONFIRMED"
    assert S.forward_token(cand, [0.2, -0.3, 0.0], [0.1]) == "NO-EDGE"


def test_pbo_matrix_sums_by_quarter():
    m = S.pbo_matrix({"a": [dict(date="2022-03-02", R=1.0), dict(date="2022-03-30", R=0.5)],
                      "b": [dict(date="2026-09-01", R=-1.0)]})
    assert m.shape == (19, 2)
    assert m[0, 0] == 1.5 and m[-1, 1] == -1.0


# ── the collector ───────────────────────────────────────────────────────────

PLAN = [dict(ticker="SPY", expiration=date(2026, 3, 20), strike=600.0, opt_type="Put",
             category="PRIMARY:K")]


@pytest.fixture
def no_network(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("network fetch attempted")
    monkeypatch.setattr(history, "fetch_option_histories", boom)
    monkeypatch.setattr(F.SPD, "plan", lambda scope: list(PLAN))


def test_collector_dry_run_is_offline(no_network, monkeypatch, capsys):
    def busy(*a, **k):
        raise AssertionError("the dry run must not consult the writer guard")
    monkeypatch.setattr(F, "other_writers", busy)
    assert F.main(["--dry-run", "--list"]) == 0
    out = capsys.readouterr().out
    assert "to fetch (primary): 1" in out and "puts=1" in out and "600.00P" in out


def test_collector_refuses_beside_another_writer(no_network, monkeypatch, capsys):
    monkeypatch.setattr(F, "other_writers", lambda: [("1", "fetch")])
    assert F.main(["--limit", "1"]) == F.EXIT_OTHER_WRITER
    assert "REFUSED" in capsys.readouterr().err


# ── past the gate: the whole outcome path, on one stub price ────────────────

def test_outcomes_runs_end_to_end_on_stub_prices(monkeypatch, tmp_path, capsys):
    rs = rule(SESSIONS, disarms=[date(2024, 1, 22)])
    priced = S.walk_package(walker_chain(), package(), rs, SESSIONS, CLOSES)
    book = S.Book(walker_chain(), set(), CLOSES)
    book._open = True
    monkeypatch.setattr(book, "price", lambda pk: S.dataclasses.replace(priced, pk=pk))
    calm = [date(2022, 3, 7) + timedelta(weeks=i) for i in range(70)]
    cens = {}
    for cell in S.CELLS:
        ks = [package(signal=d, geom=cell.geom) for d in S.REGISTERED_TRIGGERS]
        cs = [package(arm="C", signal=d, geom=cell.geom) for d in calm]
        cens[(cell.geom, "K")] = (ks, S.census_counts(ks))
        cens[(cell.geom, "C")] = (cs, S.census_counts(cs))
    monkeypatch.setattr(S, "OUT_DIR", tmp_path)
    monkeypatch.setattr(S, "TRADES_CSV", tmp_path / "trades.csv")
    monkeypatch.setattr(S, "ROOT", tmp_path)
    monkeypatch.setattr(S, "forward_rows", lambda b: ([], [], 0))
    assert S.outcomes(book, cens, S.COMMISSION) == 0
    out = capsys.readouterr().out
    # Every trade earns the same positive R, and the put out-earns the diagonal.
    assert "ARM K vs zero" in out and "->  PAYS" in out
    assert "STUDY                  NO-EDGE (PROVISIONAL)" in out   # K == C: no entry edge
    assert "PBO" in out and (tmp_path / "trades.csv").exists()
    assert "SECONDARY GRADES" in out and "ARM K vs ARM H" in out
    assert "put leg = bear put spread" in out and "(SECONDARY)" in out


# ── the bear put spread cell ────────────────────────────────────────────────

PUT_SHORT = ("Put", E1, 95.0)
EXIT = date(2024, 1, 22)


def spread_chain(long_exit=(4.9, 5.1), short_exit=(1.4, 1.6)) -> NTF.Chain:
    ch = walker_chain({ENTRY: (2.9, 3.1), EXIT: long_exit})
    ch._memo[("SPY", E1, 95.0, "Put")] = contract(
        {ENTRY: (0.9, 1.1), EXIT: short_exit})
    ch.idx[("SPY", E1)].setdefault(95.0, set()).add("P")
    return ch


def test_put_spread_cell_is_registered_and_shares_the_primary_geometry():
    assert sum(c.geom.put_spread for c in S.CELLS) == 1
    assert not S.PRIMARY.geom.put_spread
    assert len(S.CELLS) == 10


def test_put_spread_walk_exit_and_R():
    rs = rule(SESSIONS, disarms=[EXIT])
    p = S.walk_package(spread_chain(), package(put_short=PUT_SHORT), rs, SESSIONS, CLOSES)
    assert isinstance(p, S.Priced), p
    # long 3.0 in, short 1.0 in -> net debit 2.0; out 5.0 - 1.5 = 3.5; same exit rule.
    assert (p.put_in, p.put_out) == pytest.approx((2.0, 3.5))
    assert (p.put_exit, p.put_reason) == (EXIT, "disarm")
    assert (p.put_short_in, p.put_short_out) == pytest.approx((1.0, 1.5))
    assert p.put_legs == 2 and p.clamp_hit == 0 and p.clamp_bound >= 1
    # put alone: +1.5 pts = $150 less 4 leg-sides; R over the $200 net debit.
    assert S.package_R(p, 1, diag=False) == pytest.approx((150.0 - 0.65 * 4) / 200.0)
    # package: 4 put sides + 2 + 2*3 diagonal sides = 12; debit 2.0 + 11.0 = 13.0.
    gross = (1.5 + p.diag_pnl) * 100.0
    assert S.package_R(p) == pytest.approx((gross - 0.65 * 12) / 1300.0)


def test_put_spread_clamp_binds_on_an_over_wide_net_value():
    rs = rule(SESSIONS, disarms=[EXIT])
    ch = spread_chain(long_exit=(9.9, 10.1), short_exit=(0.0, 0.1))
    p = S.walk_package(ch, package(put_short=PUT_SHORT), rs, SESSIONS, CLOSES)
    # net out 10.0 - 0.05 = 9.95 > width 5 (100 - 95) -> clamped to 5.
    assert p.put_out == pytest.approx(5.0) and p.clamp_hit == 1


def test_put_spread_selection_picks_the_0_95_short_on_the_same_monthly():
    q = {D: (1.0, 1.1)}
    contracts = {PUT: q, PUT_SHORT: q, ("Put", E1, 90.0): q}
    for e in (E1, E2, E3):
        contracts[("Call", e, 105.0)] = q
    contracts[("Call", date(2025, 1, 17), 90.0)] = {date(2023, 12, 1): (11.0, 11.2)}
    ch = chain_of(contracts)
    closes = {d: 100.0 for d in SESSIONS}
    pk = S.select(ch, set(), S.Listing(ch), closes, set(SESSIONS), SESSIONS[-1],
                  S.Geom(put_spread=True), "K", D, ENTRY)
    assert pk.status == "built", (pk.status, pk.reason, pk.fetch)
    assert pk.put == ("Put", E1, 100.0) and pk.put_short == PUT_SHORT
    naked = S.select(ch, set(), S.Listing(ch), closes, set(SESSIONS), SESSIONS[-1],
                     S.Geom(), "K", D, ENTRY)
    assert naked.put_short is None


# ── secondary grades ────────────────────────────────────────────────────────

def test_holm_step_down_adjusts_monotonically_and_caps_at_one():
    h = S.holm({"a": 0.001, "b": 0.02, "c": 0.04, "d": 0.5})
    assert h["a"] == (pytest.approx(0.004), True)
    assert h["b"] == (pytest.approx(0.06), False)        # 3 x 0.02
    assert h["c"] == (pytest.approx(0.08), False)        # 2 x 0.04
    assert h["d"] == (pytest.approx(0.5), False)
    # Monotone: a later p never gets a smaller adjusted value than an earlier one.
    h2 = S.holm({"x": 0.01, "y": 0.011, "z": 0.9})
    assert h2["x"][0] <= h2["y"][0] <= h2["z"][0]
    assert S.holm({"x": 0.6, "y": 0.9})["x"][0] == 1.0  # 2 x 0.6 capped
    assert S.holm({}) == {}


def test_secondary_family_replaces_c1_and_skips_underpowered():
    base = dict(c0=True, c1=True, c2=True, c3=True, gain=1.0, n=10)
    objs = {"a": dict(base, p=0.02), "b": dict(base, p=0.03), "u": dict(n=5, c0=False)}
    out = S.secondary_family(objs)
    # m = 2 powered: a -> 0.04 (reject), b -> 0.04 (monotone); u stays out.
    assert out["a"]["adj_p"] == pytest.approx(0.04) and out["a"]["c1"]
    assert out["b"]["adj_p"] == pytest.approx(0.04)
    assert "adj_p" not in out["u"]
    assert S.token(out["u"], "P", "N") == S.UNDERPOWERED
    tight = S.secondary_family({"a": dict(base, p=0.02), "b": dict(base, p=0.026),
                                "c": dict(base, p=0.9)})
    assert tight["a"]["c1"] is False                      # 3 x 0.02 = 0.06
    assert S.token(tight["a"], "P", "N") == S.NULL


def test_draws_p_and_standing():
    assert S.draws_p(sorted([-1.0, 1.0, 2.0, 3.0] * 25)) > 0.4
    assert S.draws_p([1.0] * 100) == pytest.approx(2 / 101)
    assert S.secondary_standing("PAYS", "SELLOFF-ENTRY-HELPS", "PUT-ADDS", 0.3) \
        == "CANDIDATE (SECONDARY)"
    assert S.secondary_standing("PAYS", "SELLOFF-ENTRY-HELPS", None, 0.6) == "BLOCKED (PBO)"
    assert S.secondary_standing("PAYS", "NULL", None, 0.1) == "-"
    assert S.secondary_standing("PAYS", "SELLOFF-ENTRY-HELPS", "PUT-COSTS", 0.1) == "-"
