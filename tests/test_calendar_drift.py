"""calendar_drift: window membership, cost, placebo, overlap, cycles, Holm and
the verdict table, on SYNTHETIC calendars and series only. No figure here comes
from real returns. One test reads the tracked config/fomc-history.yml for its
shape (sorted, weekdays, eight a year or a listed exception)."""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest
import yaml

from scripts.backtest_study.f1_selection.signal import calendar_drift as cd


def weekdays(start: str, end: str, skip: tuple[str, ...] = ()) -> list[str]:
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5 and d.isoformat() not in skip:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def cal_of(dates, seed=1, adj=None):
    if adj is None:
        rng = np.random.default_rng(seed)
        adj = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(dates)))
    return cd.Cal(list(dates), np.asarray(adj, dtype=float))


# ── window membership ───────────────────────────────────────────────────────

def test_pf_window_is_the_decision_day_alone():
    dates = weekdays("2015-01-01", "2015-03-31")
    ev = cd.pf_events(dates, ["2015-01-28", "2015-03-18", "2015-06-17"])
    assert [tuple(dates[d] for d in e.days) for e in ev] == [("2015-01-28",), ("2015-03-18",)]


def test_tom_last_session_need_not_be_the_calendar_month_end():
    # 2015-05-31 is a Sunday: the last session of May is Friday 2015-05-29.
    dates = weekdays("2015-05-01", "2015-06-30")
    ev = cd.tom_events(dates)
    may = [e for e in ev if dates[e.first][:7] == "2015-05"][0]
    assert [dates[d] for d in may.days] == ["2015-05-29", "2015-06-01", "2015-06-02", "2015-06-03"]
    assert not may.open


def test_tom_skips_a_holiday_and_crosses_a_year_boundary():
    # A synthetic holiday on 2014-12-31 and 2015-01-01: L is 2014-12-30.
    dates = weekdays("2014-12-01", "2015-01-31", skip=("2014-12-31", "2015-01-01"))
    ev = cd.tom_events(dates)
    dec = [e for e in ev if dates[e.first][:7] == "2014-12"][0]
    assert [dates[d] for d in dec.days] == ["2014-12-30", "2015-01-02", "2015-01-05", "2015-01-06"]


def test_tom_window_past_the_data_and_the_final_session_are_open():
    dates = weekdays("2015-05-01", "2015-06-02")
    ev = cd.tom_events(dates)
    assert [e.open for e in ev] == [True, True]          # May runs past the data; 06-02 unsettled
    assert [dates[d] for d in ev[1].days] == ["2015-06-02"]


def test_window_membership_never_reads_a_price():
    """GX: change every later price; no window and no set membership may move."""
    dates = weekdays("2010-01-01", "2013-12-31")
    decisions = [dates[i] for i in range(15, len(dates), 30)]
    c1 = cal_of(dates, seed=1)
    adj2 = c1.adj.copy()
    adj2[len(dates) // 2:] *= np.linspace(0.5, 3.0, len(dates) - len(dates) // 2)
    c2 = cal_of(dates, adj=adj2)
    for arm, evs in (("PF", cd.pf_events(dates, decisions)), ("TOM", cd.tom_events(dates))):
        for c in (c1, c2):
            assert evs == (cd.pf_events(c.dates, decisions) if arm == "PF" else cd.tom_events(c.dates))
        b1 = cd.build_book(c1, arm, "GRADED", evs, "2013-12-31", None)
        b2 = cd.build_book(c2, arm, "GRADED", evs, "2013-12-31", None)
        assert b1.events == b2.events
        assert set(b1.in_vals) == set(b2.in_vals) and set(b1.out_vals) == set(b2.out_vals)


# ── cost, sets and the undefined-return rule ────────────────────────────────

def test_cost_is_c_over_n_on_window_days_only():
    dates = weekdays("2012-01-01", "2012-06-30")
    c = cal_of(dates)
    evs = cd.tom_events(dates)
    bk = cd.build_book(c, "TOM", "GRADED", evs, "2012-06-30", None)
    for d, v in bk.in_vals.items():
        assert v == pytest.approx(c.r[d] - cd.COST / 4)
    for d, v in bk.out_vals.items():
        assert v == c.r[d]
    pf = cd.pf_events(dates, ["2012-03-13"])
    bp = cd.build_book(c, "PF", "GRADED", pf, "2012-06-30", None)
    (d, v), = bp.in_vals.items()
    assert v == pytest.approx(c.r[d] - cd.COST)
    assert d not in bp.out_vals


def test_event_with_an_undefined_return_is_dropped_and_its_days_are_in_neither_set():
    # SPY's first session is a month's last: r at index 0 is undefined.
    dates = ["1993-01-29"] + weekdays("1993-02-01", "1993-04-30")
    c = cal_of(dates)
    evs = cd.tom_events(dates)
    assert dates[evs[0].first] == "1993-01-29"
    assert cd.classify(evs[0], c, "TOM", "2026-11-27", None) == "undefined"
    bk = cd.build_book(c, "TOM", "PRIOR", evs, "2026-11-27", None)
    assert bk.census["undefined"] == 1
    assert all(d not in bk.in_vals and d not in bk.out_vals for d in evs[0].days)
    assert len(bk.events) == len([e for e in evs if not e.open]) - 1


def test_gap_event_and_other_period_days_are_in_neither_set():
    dates = weekdays("2008-11-01", "2009-02-27")
    c = cal_of(dates)
    evs = cd.tom_events(dates)
    graded = cd.build_book(c, "TOM", "GRADED", evs, "2009-01-30", None)
    dec08 = [e for e in evs if dates[e.first][:7] == "2008-12"][0]
    jan09 = [e for e in evs if dates[e.first][:7] == "2009-01"][0]
    # Dec 2008 is a PRIOR event: its January days are in neither GRADED set.
    assert all(d not in graded.in_vals and d not in graded.out_vals for d in dec08.days)
    # Jan 2009's turn starts on the registration date and ends after it: a gap event.
    assert cd.classify(jan09, c, "TOM", "2009-01-30", None) == "gap"
    assert graded.census["gap"] == 1


def test_forward_days_start_after_registration_and_pf_stops_at_the_horizon():
    dates = weekdays("2026-11-02", "2028-02-29")
    c = cal_of(dates)
    pf = cd.pf_events(dates, ["2026-12-09", "2027-12-15"])
    bk = cd.build_book(c, "PF", "FORWARD", pf, "2026-11-27", "2027-12-31")
    assert min(dates[d] for d in bk.out_vals) == "2026-11-30"
    assert max(dates[d] for d in bk.out_vals) <= "2027-12-31"
    assert len(bk.events) == 2


# ── cycles, bootstrap, placebo, overlap ─────────────────────────────────────

def test_cycles_end_at_each_event_and_the_tail_is_one_cycle():
    in_vals = {3: 1.0, 8: 2.0}
    out_vals = {0: 0.1, 1: 0.1, 2: 0.1, 5: 0.2, 9: 0.3, 10: 0.3}
    s_in, n_in, s_out, n_out = cd.cycle_sums(in_vals, out_vals, [3, 8])
    assert list(n_in) == [1, 1, 0] and list(n_out) == [3, 1, 2]
    assert list(s_in) == [1.0, 2.0, 0.0]
    # Empty tail dropped.
    assert len(cd.cycle_sums({3: 1.0}, {1: 0.0}, [3])[0]) == 1


def test_bootstrap_p_and_ci_follow_the_tail_breach_convention():
    r = cd.summarize(0.5, np.array([-1.0, 1.0, 2.0, 3.0]), 4, 1, 1)
    assert r.p == pytest.approx(0.5)
    assert cd.summarize(1.0, np.array([1.0, 2.0]), 2, 1, 1).p == 0.0
    assert cd.summarize(float("nan"), np.array([1.0]), 1, 1, 1).p == 1.0


def _flat_book(arm, n_sessions, event_days, n_win):
    dates = weekdays("2012-01-02", "2014-12-31")[:n_sessions]
    c = cal_of(dates)
    evs = [cd.Event(arm, tuple(range(d, d + n_win))) for d in event_days]
    window = {d for e in evs for d in e.days}
    in_vals = {d: float(c.r[d]) - cd.COST / n_win for d in window}
    out_vals = {i: float(c.r[i]) for i in range(1, n_sessions) if i not in window}
    return c, cd.Book(arm, "GRADED", evs, in_vals, out_vals, {"range": (dates[0], dates[-1])})


def test_pf_placebo_shifts_six_later_and_drops_other_arm_days():
    c, bk = _flat_book("PF", 200, [20, 60, 100], 1)
    other = {66}                                # 60 + 6 is a TOM window day
    pin, ref, bnd, dropped = cd.placebo(bk, other, {20, 60, 100})
    assert set(pin) == {26, 106} and dropped == 1
    assert bnd == [26, 66, 106]
    assert 66 in ref and 26 not in ref and 106 not in ref
    assert pin[26] == pytest.approx(c.r[26] - cd.COST)


def test_tom_placebo_shifts_ten_earlier_keeping_length_and_cost():
    c, bk = _flat_book("TOM", 200, [50, 120], 4)
    pin, ref, bnd, dropped = cd.placebo(bk, set(), {d for e in bk.events for d in e.days})
    assert sorted(pin) == [40, 41, 42, 43, 110, 111, 112, 113] and dropped == 0
    assert bnd == [43, 113]
    assert pin[40] == pytest.approx(c.r[40] - cd.COST / 4)
    assert not set(pin) & set(ref)


def test_overlap_rule_removes_events_without_moving_days_to_out():
    _, pf = _flat_book("PF", 200, [20, 61, 100], 1)
    tom_days = {60, 61, 62, 63}
    iv, ov, bnd, n = cd.ex_overlap(pf, tom_days, {20, 61, 100})
    assert n == 1 and set(iv) == {20, 100} and 61 not in ov and bnd == [20, 100]
    _, tom = _flat_book("TOM", 200, [60, 120], 4)
    iv, ov, bnd, n = cd.ex_overlap(tom, set(), {61, 20})
    assert n == 1 and set(iv) == {120, 121, 122, 123}
    assert not ({60, 61, 62, 63} & set(ov)) and bnd == [123]


def test_leave_one_year_out_assigns_events_to_their_last_session_year():
    dates = weekdays("2012-12-03", "2013-01-31")
    c = cal_of(dates)
    evs = cd.tom_events(dates)
    bk = cd.build_book(c, "TOM", "GRADED", evs, "2013-01-31", None)
    split = cd.year_split(bk, c)
    dec = [e for e in bk.events if dates[e.first][:7] == "2012-12"][0]
    assert all(d in split["2013"][0] for d in dec.days)


# ── Holm and the verdict table ──────────────────────────────────────────────

def test_holm_m2():
    adj = cd.holm({"PF": 0.03, "TOM": 0.01})
    assert adj["TOM"][0] == pytest.approx(0.02)
    assert adj["PF"][0] == pytest.approx(0.03)
    adj = cd.holm({"PF": 1.0, "TOM": 0.03})       # an UNDERPOWERED arm enters with p = 1
    assert adj["TOM"][0] == pytest.approx(0.06) and adj["PF"][0] == 1.0


def R(lo, hi, point=None):
    return cd.Result((lo + hi) / 2 if point is None else point, lo, hi, 0.0, 10, 10, 10)


@pytest.mark.parametrize("res,powered,p,gates,forward,want", [
    (R(0.1, 0.2), False, 0.0, (1, 1, 1), False, "UNDERPOWERED"),
    (R(0.1, 0.2), False, 0.0, (1, 1, 1), True, "STILL-OPEN"),
    (cd.Result(0.1, float("nan"), float("nan"), 0.0, 1, 1, 1), True, 0.0, (1, 1, 1), False,
     "UNDERPOWERED"),
    (R(-0.3, -0.1), True, 0.01, (0, 0, 0), False, "REVERSED"),
    (R(-0.3, -0.1), True, 0.20, (1, 1, 1), False, "NULL"),
    (R(0.1, 0.3), True, 0.01, (1, 1, 1), False, "STILL-PAYS"),
    (R(0.1, 0.3), True, 0.01, (1, 0, 1), False, "FRAGILE"),
    (R(0.1, 0.3), True, 0.01, (1, 1, 0), True, "FRAGILE"),
    (R(0.1, 0.3), True, 0.06, (1, 1, 1), False, "NULL"),
    (R(-0.1, 0.3), True, 0.01, (1, 1, 1), False, "NULL"),
])
def test_verdict_table_first_match(res, powered, p, gates, forward, want):
    assert cd.verdict(res, powered, p, *map(bool, gates), forward=forward) == want


# ── the FOMC history file ───────────────────────────────────────────────────

def test_fomc_history_file_parses_sorted_weekdays_eight_a_year_or_exception():
    raw = yaml.safe_load(cd.HISTORY_YML.read_text())
    dates = [e["date"] for e in raw["decisions"]]
    assert all(isinstance(d, date) for d in dates)
    assert dates == sorted(dates) and len(set(dates)) == len(dates)
    assert all(d.weekday() < 5 for d in dates)
    assert dates[0] >= date(1994, 1, 1) and dates[-1] <= date(2023, 5, 31)
    exc = raw["meta"]["exceptions"]
    for y in range(1994, 2023):
        n = sum(1 for d in dates if d.year == y)
        assert n == 8 or (y in exc and str(exc[y]).strip()), y
    assert set(raw["decisions"][0]) >= {"date", "label"}
    fomc = cd.load_fomc()
    assert cd.gf_calendar_problems(fomc) == []


def test_gf_flags_a_short_year_without_an_exception():
    hist = [f"{y}-{m:02d}-15" for y in range(1994, 2023) for m in (1, 3, 4, 6, 7, 9, 10, 12)]
    hist = [d for d in hist if date.fromisoformat(d).weekday() < 5] + []
    fomc = cd.Fomc(sorted(hist), ["2023-06-14"], {}, "2027-12-31")
    probs = cd.gf_calendar_problems(fomc)
    assert any("no meta.exceptions reason" in p for p in probs)
    assert any("join gap" in p for p in probs)


# ── end to end on a synthetic world ─────────────────────────────────────────

def _synthetic_world(tmp_path, monkeypatch):
    dates = ["1993-01-29"] + weekdays("1993-02-01", "2026-11-27")
    rng = np.random.default_rng(7)
    adj = 50 * np.cumprod(1 + rng.normal(0.0003, 0.011, len(dates)))
    close = adj * 1.0
    spy = tmp_path / "SPY.csv"
    spy.write_text("date,close,adj_close\n" + "".join(
        f"{d},{float(c)!r},{float(a)!r}\n" for d, c, a in zip(dates, close, adj)))
    sessions = set(dates)
    hist = []
    for y in range(1994, 2023):
        for m in (1, 3, 4, 6, 7, 9, 10, 12):
            d = date(y, m, 15)
            while d.isoformat() not in sessions:
                d += timedelta(days=1)
            hist.append(d.isoformat())
    hist += ["2023-02-15", "2023-03-15", "2023-05-03"]
    hy = tmp_path / "hist.yml"
    hy.write_text(yaml.safe_dump({"meta": {"exceptions": {}},
                                  "decisions": [{"date": date.fromisoformat(d), "label": "x"}
                                                for d in hist]}))
    macro = []
    for y in range(2023, 2028):
        for m in (1, 3, 4, 6, 7, 9, 10, 12):
            d = date(y, m, 14)
            if d < date(2023, 6, 14):
                continue
            while d.weekday() >= 5 or (d.isoformat() <= "2026-11-27" and d.isoformat() not in sessions):
                d += timedelta(days=1)
            macro.append({"date": d, "type": "fomc", "release_et": "14:00", "label": "x"})
    my = tmp_path / "macro.yml"
    my.write_text(yaml.safe_dump({"meta": {"compiled": date(2026, 11, 27),
                                           "verified_through": {"fomc": date(2027, 12, 31)}},
                                  "events": macro}))
    monkeypatch.setattr(cd, "BOOT_N", 200)
    monkeypatch.delenv("STUDY_ERA", raising=False)
    return spy, hy, my


def test_end_to_end_prints_the_three_banner_lines(tmp_path, monkeypatch, capsys):
    spy, hy, my = _synthetic_world(tmp_path, monkeypatch)
    rc = cd.run(spy_path=spy, history_path=hy, macro_path=my, check_git=False)
    out = capsys.readouterr().out
    assert rc == 0
    banners = [ln.strip() for ln in out.splitlines() if ln.strip().startswith(">>> calendar_drift")]
    assert len(banners) == 3
    assert banners[0].startswith(f">>> calendar_drift PF ({cd.BANNER['PF']}): ")
    assert banners[1].startswith(f">>> calendar_drift TOM ({cd.BANNER['TOM']}): ")
    assert banners[2] == (">>> calendar_drift FORWARD (events after the registration date): "
                          "PF STILL-OPEN TOM STILL-OPEN <<<")
    words = {b.split(": ")[-1].rstrip(" <").strip() for b in banners[:2]}
    assert words <= {"STILL-PAYS", "FRAGILE", "NULL", "REVERSED", "UNDERPOWERED"}
    assert "PRIOR (pre-publication, not graded)" in out


def test_ge_refuses_a_series_that_stops_before_registration(tmp_path, monkeypatch, capsys):
    spy, hy, my = _synthetic_world(tmp_path, monkeypatch)
    lines = spy.read_text().splitlines()
    spy.write_text("\n".join(lines[:-1]) + "\n")      # drop 2026-11-27
    assert cd.main.__module__ == cd.__name__
    with pytest.raises(cd.Refused) as exc:
        cd.run(spy_path=spy, history_path=hy, macro_path=my, check_git=False)
    assert exc.value.code == 3


def test_missing_file_and_wrong_era_refuse(tmp_path, monkeypatch):
    with pytest.raises(cd.Refused) as exc:
        cd.load_spy(False, tmp_path / "none.csv")
    assert exc.value.code == 3 and "--refresh" in exc.value.message
    monkeypatch.setenv("STUDY_ERA", "v3")
    with pytest.raises(cd.Refused) as exc:
        cd.check_era()
    assert exc.value.code == 2


def test_gb_refuses_a_split_step(tmp_path, monkeypatch):
    spy, hy, my = _synthetic_world(tmp_path, monkeypatch)
    rows = spy.read_text().splitlines()
    head, body = rows[0], rows[1:]
    mid = len(body) // 2
    fixed = []
    for i, ln in enumerate(body):
        d, c, a = ln.split(",")
        fixed.append(f"{d},{float(c) * (2 if i >= mid else 1)!r},{a}")
    spy.write_text(head + "\n" + "\n".join(fixed) + "\n")
    with pytest.raises(cd.Refused) as exc:
        cd.run(spy_path=spy, history_path=hy, macro_path=my, check_git=False)
    assert exc.value.code == 3 and "GB" in exc.value.message


def test_tom_counts_on_a_full_synthetic_calendar_are_one_per_month():
    dates = ["1993-01-29"] + weekdays("1993-02-01", "2026-11-27")
    evs = cd.tom_events(dates)
    months = {d[:7] for d in dates}
    assert len(evs) == len(months)
    assert math.isclose(sum(not e.open for e in evs), len(months) - 1)
