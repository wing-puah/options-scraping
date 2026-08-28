"""`hedge_timing` — the claims that live in CODE rather than in a report.

The study is pre-registered
(`research/pre-registrations/f4_deployment/hedge_timing.md`) and has not been
run yet, on purpose: registration-before-run has to be visible in git. What can
be pinned before the first run is everything that is a code-BEHAVIOUR claim
rather than a data claim — and each of these is a way the study could be
deterministically, reproducibly wrong while printing a clean report:

  * the verdict grammar is TOTAL. A criterion vector that falls through and
    prints nothing is a study that silently drops an arm.
  * the triggers are CAUSAL. A trigger that reads a bar after the signal date is
    unimplementable live, which is the whole point of computing it.
  * a failed power floor early-returns UNDERPOWERED WITHOUT computing a
    statistic. "Underpowered but here is the number anyway" is how an n=2 read
    gets quoted six months later.
  * H4 carries a no-bear day at f=0 rather than dropping it — the
    `calendar_hedge` lesson: a hedge unavailable exactly when it is needed is
    not a hedge, and dropping the day hides that.
  * the ex-BOTH-windows cut really excludes BOTH month sets. It is computed by
    hand (`protocol.window_cuts` yields the two separately and never their
    intersection), so nothing else checks it.
"""
from __future__ import annotations

import itertools
import math
from datetime import date

from scripts.backtest_study.f4_deployment import hedge_timing as HT

CRITERIA = ("evaluable", "powered", "ci_excludes_zero", "positive",
            "loo_all_same_sign", "years_ok", "cuts_ok", "h2_mirrors")


# ── the verdict grammar is total ─────────────────────────────────────────────

def test_verdict_grammar_is_total() -> None:
    """Every combination of the eight-boolean criterion vector returns exactly
    one non-empty token. A vector with no verdict is an arm that vanishes."""
    seen = set()
    for combo in itertools.product((False, True), repeat=len(CRITERIA)):
        c = dict(zip(CRITERIA, combo))
        v = HT.verdict_for(c)
        assert isinstance(v, str) and v.strip(), c
        assert v in HT.VERDICTS, f"{c} produced an unregistered token {v!r}"
        seen.add(v)
    # Every registered token must be reachable, or the vocabulary is lying.
    assert seen == set(HT.VERDICTS)


def test_the_registered_readings_are_the_ones_produced() -> None:
    base = dict(evaluable=True, powered=True, ci_excludes_zero=True, positive=True,
                loo_all_same_sign=True, years_ok=True, cuts_ok=True, h2_mirrors=False)
    assert HT.verdict_for(base) == "TIMING-CANDIDATE"
    assert HT.verdict_for({**base, "h2_mirrors": True}) == "MARKET-TIMING-PROXY"
    assert HT.verdict_for({**base, "positive": False}) == "CONTRARY"
    assert HT.verdict_for({**base, "cuts_ok": False}) == "UNSTABLE"
    assert HT.verdict_for({**base, "years_ok": False}) == "UNSTABLE"
    assert HT.verdict_for({**base, "loo_all_same_sign": False}) == "UNSTABLE"
    assert HT.verdict_for({**base, "ci_excludes_zero": False}) == "NULL"
    assert HT.verdict_for({**base, "powered": False}) == "UNDERPOWERED"
    assert HT.verdict_for({**base, "evaluable": False}) == "NOT EVALUABLE"


def test_underpowered_wins_over_every_downstream_criterion() -> None:
    """A floor failure is not a lean. Nothing below it may re-colour it."""
    for combo in itertools.product((False, True), repeat=len(CRITERIA) - 2):
        c = dict(zip(CRITERIA[2:], combo), evaluable=True, powered=False)
        assert HT.verdict_for(c) == "UNDERPOWERED"


# ── the triggers are causal ──────────────────────────────────────────────────

def _series(*closes, start=date(2026, 1, 5)):
    """`{date: close}` over consecutive weekdays from `start`."""
    out, d = {}, start
    for c in closes:
        while d.weekday() >= 5:
            d = date.fromordinal(d.toordinal() + 1)
        out[d] = float(c)
        d = date.fromordinal(d.toordinal() + 1)
    return out


def test_gap_reads_only_the_prior_close_and_the_signal_open() -> None:
    closes = _series(100.0, 100.0, 100.0)
    days = sorted(closes)
    d = days[1]
    opens = {d: 100.4}                          # +0.4% gap on D: fires at g=0.003
    assert HT.t_gap(closes, opens, d, 0.003) is True

    # A bar AFTER D cannot change it — neither a later close nor a later open.
    after = date.fromordinal(days[-1].toordinal() + 3)
    closes_with_future = {**closes, after: 1.0}
    opens_with_future = {**opens, after: 1.0, days[2]: 1.0}
    assert HT.t_gap(closes_with_future, opens_with_future, d, 0.003) is True


def test_decline_strict_ignores_sessions_after_the_signal_date() -> None:
    """The run ends AT D. A rally after D must not break it; a rally after D
    must not create one either."""
    closes = _series(105.0, 104.0, 103.0, 102.0, 99.0)
    days = sorted(closes)
    d = days[3]                                  # three lower closes end here
    assert HT.t_decline_strict(closes, d, 3) is True
    # The 5th bar is a further DOWN close; reading it would make N=4 true at D.
    assert HT.t_decline_strict(closes, d, 4) is False
    # And an up-bar after D must not break the run that already ended at D.
    closes_up = {**closes, days[4]: 999.0}
    assert HT.t_decline_strict(closes_up, d, 3) is True


def test_chop_ignores_sessions_after_the_signal_date() -> None:
    """`eff_ratio` runs over the 20 sessions ENDING at D. A violent trend after
    D would move a non-causal implementation; this one must not budge."""
    closes = _series(*[100.0 + (i % 2) * 0.5 for i in range(30)])
    days = sorted(closes)
    d = days[24]
    before = HT.chop_value(closes, d)
    assert before is not None
    after = {**closes, **{days[i]: 500.0 + i for i in range(25, 30)}}
    assert HT.chop_value(after, d) == before
    assert HT.t_chop(after, d, before + 1e-9) is HT.t_chop(closes, d, before + 1e-9)


def test_gap_and_decline_and_chop_on_hand_built_series() -> None:
    closes = _series(100.0, 99.0, 98.5, 99.0, 98.0, 97.0)
    days = sorted(closes)

    # gap: open must clear the PRIOR close by g.
    assert HT.t_gap(closes, {days[2]: 99.0 * 1.004}, days[2], 0.003) is True
    assert HT.t_gap(closes, {days[2]: 99.0 * 1.001}, days[2], 0.003) is False
    assert HT.t_gap(closes, {days[2]: 99.0}, days[2], 0.0) is True      # exactly flat, g=0
    assert HT.t_gap(closes, {}, days[2], 0.003) is False                # no open -> no trigger

    # strict streak, ending at D.
    assert HT.t_decline_strict(closes, days[2], 2) is True
    assert HT.t_decline_strict(closes, days[3], 1) is False             # days[3] closed UP
    assert HT.t_decline_strict(closes, days[0], 1) is False             # no prior bar

    # broad: >=3 lower closes of the last 5 sessions ending at D.
    assert HT.t_decline_broad(closes, days[5], k=3, window=5) is True
    assert HT.t_decline_broad(closes, days[5], k=5, window=5) is False
    assert HT.t_decline_broad(closes, days[2], k=3, window=5) is False  # too few bars

    # chop: a perfectly straight line is maximally efficient (ratio 1.0).
    trend = _series(*[100.0 + i for i in range(25)])
    tdays = sorted(trend)
    assert HT.chop_value(trend, tdays[-1]) == 1.0
    assert HT.t_chop(trend, tdays[-1], 0.163) is False


# ── a failed floor never reaches a statistic ─────────────────────────────────

def _row(d, structure, r, tier="A", dol=100.0):
    return {"date": d, "structure": structure, "R": r, "R_dol": dol,
            "tier": tier, "credit": False, "max_loss_per_contract": 500.0}


STATISTIC_KEYS = ("delta", "ci", "st", "crit", "mean_trigger", "mean_non",
                  "paired_trigger", "paired_non", "own_ci", "best", "rows",
                  "delta_total", "base", "year_totals", "loo_min")


def test_strict_streak_arm_is_underpowered_without_computing_a_mean() -> None:
    """A 2-date book is exactly the strict-run census on the real book. Every
    arm must refuse it by COUNT, before any outcome column is read — so the
    result dict carries no statistic at all, not even a suppressed one."""
    dates = ["2025-06-02", "2025-06-03"]
    bear_by_date = {d: [_row(d, "bear_put_spread", 0.5)] for d in dates}
    ladder_by_date = {d: [_row(d, "bull_call_spread", -0.5)] for d in dates}
    cen = HT.h0_census("DECLINE", lambda d: True, dates, bear_by_date, ladder_by_date)

    assert cen["trigger"]["n_dates"] == 2
    assert cen["powered_h1"] is False and cen["powered_h3"] is False

    for res in (HT.h1_between(bear_by_date, cen),
                HT.h2_between(ladder_by_date, cen),
                HT.h3_paired(bear_by_date, ladder_by_date, cen),
                HT.h4_portfolio({d: 10.0 for d in dates},
                                HT.sleeve_pick(bear_by_date), cen)):
        assert res["verdict"] == "UNDERPOWERED", res["arm"]
        assert res["powered"] is False
        leaked = [k for k in STATISTIC_KEYS if k in res]
        assert not leaked, f"{res['arm']} leaked statistics {leaked} below its floor"


def test_a_powered_census_does_produce_the_statistics() -> None:
    """Guard the guard: the leak check above must not pass by the arms never
    computing anything."""
    dates = [f"2025-06-{d:02d}" for d in range(1, 31)]
    bear_by_date = {d: [_row(d, "bear_put_spread", 0.5)] for d in dates}
    ladder_by_date = {d: [_row(d, "bull_call_spread", 0.1)] for d in dates}
    cen = HT.h0_census("CHOP", lambda d: True, dates, bear_by_date, ladder_by_date)

    assert cen["powered_h1"] is True and cen["powered_h3"] is True
    h1 = HT.h1_between(bear_by_date, cen)
    assert "delta" in h1 and "crit" in h1
    h3 = HT.h3_paired(bear_by_date, ladder_by_date, cen)
    assert "delta" in h3 and h3["verdict"] in HT.VERDICTS


def test_not_evaluable_short_circuits_before_the_floor_check() -> None:
    """An upstream gate failure and a thin census are DIFFERENT refusals. A
    family whose trigger could not be constructed must not be reported as
    merely underpowered — that would read as "we looked and found too little"."""
    dates = [f"2025-06-{d:02d}" for d in range(1, 31)]
    bear_by_date = {d: [_row(d, "bear_put_spread", 0.5)] for d in dates}
    ladder_by_date = {d: [_row(d, "bull_call_spread", 0.1)] for d in dates}
    cen = HT.h0_census("CHOP", lambda d: True, dates, bear_by_date, ladder_by_date)
    assert cen["powered_h3"] is True, "the census itself is powered — only the gate failed"

    for res in (HT.h1_between(bear_by_date, cen, evaluable=False),
                HT.h2_between(ladder_by_date, cen, evaluable=False),
                HT.h3_paired(bear_by_date, ladder_by_date, cen, evaluable=False),
                HT.h4_portfolio({d: 10.0 for d in dates},
                                HT.sleeve_pick(bear_by_date), cen, evaluable=False)):
        assert res["verdict"] == "NOT EVALUABLE", res["arm"]
        assert not [k for k in STATISTIC_KEYS if k in res]


def test_the_report_printers_render_every_branch(capsys) -> None:
    """A smoke test with teeth: the study is not run before it is committed, so
    a format bug in a report line would otherwise first surface on the
    operator's run. Exercise powered, underpowered and not-evaluable output."""
    dates = [f"2025-06-{d:02d}" for d in range(1, 31)]
    bear_by_date = {d: [_row(d, "bear_put_spread", 0.5, dol=200.0)] for d in dates}
    ladder_by_date = {d: [_row(d, "bull_call_spread", 0.1, dol=50.0)] for d in dates}
    dep = HT.daily_dollars([r for rs in ladder_by_date.values() for r in rs])
    cen = HT.h0_census("CHOP", lambda d: d < "2025-06-27", dates,
                       bear_by_date, ladder_by_date)

    HT.print_census(cen)
    HT._print_between(HT.h1_between(bear_by_date, cen), "between-date")
    HT._print_h3(HT.h3_paired(bear_by_date, ladder_by_date, cen))
    HT._print_h4(HT.h4_portfolio(dep, HT.sleeve_pick(bear_by_date), cen))
    HT._print_between(HT.h1_between(bear_by_date, cen, evaluable=False), "between-date")
    HT._print_h3(HT.h3_paired(bear_by_date, ladder_by_date, cen, evaluable=False))
    HT._print_h4(HT.h4_portfolio(dep, HT.sleeve_pick(bear_by_date), cen, evaluable=False))

    out = capsys.readouterr().out
    assert "ARM H1-CHOP" in out and "ARM H3-CHOP" in out and "ARM H4-CHOP" in out
    assert "FLOOR MET" in out
    assert "NOT EVALUABLE — an upstream gate failed" in out


# ── H4 carries a no-bear day rather than dropping it ─────────────────────────

def test_h4_carries_a_day_with_no_bear_row_at_f_zero() -> None:
    dep = {"2025-06-02": 100.0, "2025-06-03": -50.0, "2025-06-04": 25.0}
    sleeve = {"2025-06-02": 400.0, "2025-06-04": -200.0}     # 06-03 has NO bear row

    series = HT.policy_daily(dep, sleeve, 1.0)
    assert [d for d, _v in series] == sorted(dep), "a no-bear day was dropped"
    got = dict(series)
    assert got["2025-06-03"] == -50.0, "the no-bear day must carry at f=0, unhedged"
    assert got["2025-06-02"] == 500.0
    assert got["2025-06-04"] == -175.0


def test_h4_gate_zeroes_an_ungated_day_but_never_removes_it() -> None:
    dep = {"2025-06-02": 100.0, "2025-06-03": -50.0}
    sleeve = {"2025-06-02": 400.0, "2025-06-03": 400.0}
    series = HT.policy_daily(dep, sleeve, 1.0, gated_dates=["2025-06-02"])
    assert dict(series) == {"2025-06-02": 500.0, "2025-06-03": -50.0}
    assert len(series) == 2


def test_h4_baseline_is_the_deployed_book_untouched() -> None:
    dep = {"2025-06-02": 100.0, "2025-06-03": -50.0}
    sleeve = {"2025-06-02": 9999.0}
    assert dict(HT.policy_daily(dep, sleeve, 0.0)) == dep


# ── the hand ex-BOTH-windows cut ─────────────────────────────────────────────

def test_ex_both_windows_excludes_both_month_sets() -> None:
    rows = [{"date": "2025-02-14"}, {"date": "2025-03-14"}, {"date": "2025-04-02"},
            {"date": "2025-05-01"}, {"date": "2026-02-03"}, {"date": "2026-03-31"},
            {"date": "2026-04-30"}, {"date": "2026-05-04"}]
    kept = {r["date"] for r in HT.ex_both_windows(rows)}
    assert kept == {"2025-02-14", "2025-05-01", "2026-05-04"}
    # It is strictly narrower than either single cut, which is the point of
    # computing it by hand: protocol.window_cuts never yields the intersection.
    from scripts.backtest_study.lib import protocol as P
    for name in P.DOMINANT_WINDOWS:
        single = {r["date"] for r in P.window_cuts(rows)[name]}
        assert kept <= single and kept != single


def test_ex_both_months_is_exactly_the_union_of_the_dominant_windows() -> None:
    from scripts.backtest_study.lib import protocol as P
    union = {m for months in P.DOMINANT_WINDOWS.values() for m in months}
    assert set(HT.EX_BOTH_MONTHS) == union


# ── small pinned invariants ──────────────────────────────────────────────────

def test_h2_mirror_needs_opposite_signs_and_a_comparable_size() -> None:
    assert HT.h2_mirror(+0.40, -0.20) is True          # exactly the 0.5x bar
    assert HT.h2_mirror(+0.40, -0.19) is False         # too small to mirror
    assert HT.h2_mirror(+0.40, +0.40) is False         # same sign: not a mirror
    assert HT.h2_mirror(float("nan"), -0.30) is False  # an unpowered arm cannot mirror


def test_same_sign_fails_closed_on_an_empty_cut() -> None:
    """`bear_deploy`'s 2026-08-24 scar: a nan from an EMPTY ex-window cut must
    FAIL the check, never be filtered out of it."""
    assert HT._same_sign(float("nan"), 0.5) is False
    assert HT._same_sign(0.0, 0.5) is False
    assert HT._same_sign(-0.1, -0.5) is True


def test_the_bear_sleeve_excludes_the_credit_bear_structure() -> None:
    """`bear_call_spread` is a credit structure, tier-VETO'd at intake, and is
    not the debit hedge this study is about."""
    assert "bear_call_spread" not in HT.BEAR_DEBIT_STRUCTURES
    assert set(HT.BEAR_DEBIT_STRUCTURES) == {"bear_put_spread", "long_put"}


def test_floors_are_the_registered_numbers() -> None:
    assert HT.FLOOR_TRIGGER_DATES == 25
    assert HT.FLOOR_ROWS == 60
    assert HT.FLOOR_H4_DAYS == 25
    assert HT.HEADLINE_TESTS == 9


def test_series_crosscheck_refuses_two_different_tapes() -> None:
    a = _series(*[100.0 + math.sin(i) for i in range(120)])
    days = sorted(a)
    same = dict(a)
    good = HT.series_crosscheck(a, same)
    assert good["ok"] is True and good["corr"] > HT.SERIES_MIN_CORR

    flipped = {d: (a[d] if i % 3 else 100.0 + 5 * math.cos(i))
               for i, d in enumerate(days)}
    bad = HT.series_crosscheck(a, flipped)
    assert bad["ok"] is False
    assert bad["disagree"], "a refusal must name the dates it refused on"


def test_series_crosscheck_refuses_a_too_short_overlap() -> None:
    a = _series(*[100.0 + i for i in range(10)])
    out = HT.series_crosscheck(a, dict(a))
    assert out["ok"] is False and "30" in out["why"]
