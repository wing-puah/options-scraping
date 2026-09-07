"""Frozen-fixture regression test for the shared hedge criteria.

WHY THIS EXISTS
---------------
`scripts/backtest_study/lib/hedge_criteria.py` is one body per rule for a
question six study modules ask: what a hedge sleeve does in the book's tail
(the contribution rule, `bear_deploy` D2) and how much of it the book can carry
(the sizing rule, `bear_deploy` D3). Before it existed, each study carried its
own copy, and two of those copies said in their own docstrings that they were
copied rather than imported precisely so a change elsewhere could never move
their recorded numbers.

Consolidating them keeps that promise only if the arithmetic is pinned. The
failure mode is not a crash: it is a criterion that keeps returning plausible
figures which no longer mean what `research/study-results/` records they mean.
So this file is `tests/test_harness_replay.py` applied to the criteria —
`tests/fixtures/hedge_criteria.csv`, one row per case, each case built from
that row ALONE and asserted EXACTLY.

WHERE THE EXPECTED VALUES COME FROM
-----------------------------------
Every one of them is hand-computed, and every row's `why` column carries the
derivation. That is deliberate and it is the whole point of the file: an
expectation produced by running the code under test records what the code does
today, not what the rule says, and the next person to change the rule would
"fix" the fixture to match. Nothing here is generated, and there is no
generator script to regenerate it with.

The inputs are small and synthetic for the same reason. A case built out of the
live export would move whenever the book grows — the exact rot that killed the
four hardcoded study gates deleted on 2026-08-15 (see `run.py` and
`research/current.md`). These series carry no book rows, no dates from the real
book's population, and no broker or account fields.

WHAT IS PINNED
--------------
  - the contribution rule at every branch that decides a verdict: a tail that
    clears and one that does not, a correlation of each sign, the per-year
    clause failing on one year while the pooled tail passes, a year below the
    six-date minimum being reported but not counted, an EMPTY cut dropped
    rather than reported as a zero, an UNDEFINED cut failing the rule closed,
    and a cell below the power floor returning nothing at all;
  - the sizing rule where it can surprise: a sweep whose winner is NOT the
    largest tested fraction, a sweep no fraction clears (which returns none,
    and reports the least-harmful size separately as context), and an empty
    sleeve passing vacuously at the largest fraction — recorded so that
    fail-open stays visible;
  - the tie-breaks, which are `max()`'s first-wins on both the sleeve picker
    and the least-harmful size, and are the kind of thing a rewrite silently
    reverses;
  - the daily-series builder's two exclusions (no return = not in the series;
    no dollars = in it, contributing none);
  - `max_drawdown` on a curve that only rises, one that never gets above flat,
    and one ordinary peak-to-trough — plus the identity check that this module
    re-exports `lib/mtm_curve.py`'s function rather than owning a second body.

Assertions are exact at the fixture's stated precision of six decimal places,
the way the harness fixture is exact at four. A tolerance would defeat the
point: the fixture exists to notice a change, not to accommodate one.

KNOWN GAPS
----------
  - The decile cut is exercised only where its `max(3, n // 10)` FLOOR binds;
    a case where `n // 10` wins needs 40+ overlapping dates, which is more
    hand-typed series than the branch is worth. The quartile cut's formula IS
    exercised (20 dates gives `max(3, 5)` = 5, and 24 gives 6).
  - `hedge_timing`'s gated-policy empty cut, which must fail CLOSED, is not
    here: that criterion has not moved into the library yet
    (`research/hedge-programme-plan.md` §Q1). The library's own fail-closed
    branch — an undefined tail — is covered.

If a case here fails, the fix is almost never the fixture. Either the change to
`hedge_criteria.py` was unintended, or a rule is genuinely being changed — in
which case the studies that quote it have to be re-run and re-recorded, which
is a study decision and not a test edit.
"""
import csv
import math
from pathlib import Path

import pytest

from scripts.backtest_study.lib import hedge_criteria as HC

FIXTURE = Path(__file__).parent / "fixtures" / "hedge_criteria.csv"


def _cases():
    with open(FIXTURE, newline="") as fh:
        return list(csv.DictReader(fh))


CASES = _cases()


# ── the fixture's own little formats, parsed here and nowhere else ───────────

def _num(tok):
    """`none` is a missing value; everything else is a float (`nan` included)."""
    return None if tok == "none" else float(tok)


def _series(text):
    """`date:R:dollars;...` -> the daily series shape, `date -> (R, $, n)`."""
    out = {}
    for entry in (e for e in text.split(";") if e):
        d, r, dol = entry.split(":")
        out[d] = (float(r), float(dol), 1)
    return out


def _rows(text):
    """`date:R:dollars:sortkey;...` -> the row dicts a study would hand over."""
    rows = []
    for entry in (e for e in text.split(";") if e):
        d, r, dol, key = entry.split(":")
        rows.append({"date": d, "R": _num(r), "dol": _num(dol), "key": _num(key)})
    return rows


def _sleeve(text):
    """`date:dollars;...` -> a sleeve's dollars by date."""
    return {e.split(":")[0]: float(e.split(":")[1])
            for e in (e for e in text.split(";") if e)}


def _fractions(text):
    return tuple(float(f) for f in text.split("|") if f)


def _expect(text):
    """`name=value;...` -> the outcome the row claims, name by name."""
    return dict(e.split("=", 1) for e in text.split(";") if e)


def _six(v):
    """One canonical rendering at the fixture's stated precision."""
    return "nan" if isinstance(v, float) and math.isnan(v) else f"{round(float(v), 6):.6f}"


# ── each criterion, evaluated from the fixture row alone ─────────────────────

def _outcome(case) -> dict:
    crit = case["criterion"]

    if crit == "d2":
        kw = {"min_common": int(case["min_common"])} if case["min_common"] else {}
        hc = HC.hedge_contribution(_series(case["dep_series"]),
                                   _series(case["bear_series"]), **kw)
        if hc is None:
            return {"none": True}
        return {
            "none": False,
            "n_common": len(hc.common),
            "corr": hc.corr,
            "tail_r": hc.tail_r,
            "tail_n": len(hc.tail.dates),
            "tail_dollars": hc.tail.bear_dollars,
            "tail_win": hc.tail.bear_win_rate,
            "ok_years": hc.ok_years,
            "tot_years": hc.tot_years,
            "met": hc.met,
            "buckets": "|".join(b.name for b in hc.buckets),
            "years_reported": len(hc.years),
        }

    if crit == "d3":
        rows, base, dates = HC.sweep(_series(case["dep_series"]),
                                     _sleeve(case["sleeve"]),
                                     _fractions(case["fractions"]))
        v = HC.sizing_verdict(rows, base)
        return {
            "dates": len(dates),
            "base_total": base.total,
            "base_mdd": base.mdd,
            "base_worst": base.worst,
            "base_neg": base.neg,
            "base_dev": base.downside_dev,
            "best_f": v.best.f if v.best else None,
            "best_total": v.best.total if v.best else None,
            "least_f": v.least_harmful.f if v.least_harmful else None,
        }

    if crit == "sleeve":
        veto = {d for d in case["gate_veto"].split(";") if d}
        gate = (lambda d, rs: d not in veto) if veto else None
        got = HC.sleeve_dollars(_rows(case["rows"]), lambda r: r["key"],
                                dol_key="dol", gate=gate)
        return {"sleeve": {d: _six(v) for d, v in got.items()}}

    if crit == "daily":
        got = HC.daily_series(_rows(case["rows"]), "R", "dol")
        return {"daily": {d: (_six(r), _six(dol), n) for d, (r, dol, n) in got.items()}}

    if crit == "mdd":
        return {"mdd": HC.max_drawdown([float(v) for v in case["series"].split(";") if v])}

    raise AssertionError(f'{case["case_id"]}: unknown criterion {crit!r} — a typo '
                         f"here would silently skip the case rather than fail it")


def _agrees(got, want: str) -> bool:
    """Exact agreement at the fixture's precision. No tolerance anywhere."""
    if isinstance(got, bool):
        return want in ("TRUE", "FALSE") and got is (want == "TRUE")
    if got is None:
        return want == "NONE"
    if isinstance(got, int):
        return got == int(want)
    if isinstance(got, float):
        return _six(got) == ("nan" if want == "nan" else _six(float(want)))
    if isinstance(got, str):
        return got == want
    if isinstance(got, dict):
        return got == _want_map(want)
    raise AssertionError(f"no comparison for {type(got)}")


def _want_map(want: str) -> dict:
    """`date:a[:b:c]|...` -> the same canonical shape `_outcome` builds."""
    out = {}
    for entry in (e for e in want.split("|") if e):
        parts = entry.split(":")
        if len(parts) == 2:
            out[parts[0]] = _six(parts[1])
        else:
            out[parts[0]] = (_six(parts[1]), _six(parts[2]), int(parts[3]))
    return out


# ── the cases ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_criterion_reproduces_the_hand_computed_outcome(case):
    """Each fixture row's criterion returns exactly what the row records.

    See this file's docstring before touching the fixture: the expected values
    were computed by hand, and rewriting one to match new behaviour rebases
    every study that quotes the rule onto a criterion that did not produce it.
    """
    got = _outcome(case)
    want = _expect(case["expect"])
    assert want, f'{case["case_id"]}: a row that expects nothing checks nothing'
    for name, text in want.items():
        assert name in got, (f'{case["case_id"]}: the fixture expects "{name}", '
                             f"which this criterion does not report")
        assert _agrees(got[name], text), (
            f'{case["case_id"]}: {name} is {got[name]!r}, recorded as {text!r}. '
            f'{case["why"]}')


# ── fixture self-checks: guard the guard ─────────────────────────────────────
# A fixture that quietly lost its interesting rows would still pass every case
# above. These assert the coverage the docstring claims, branch by branch.

def _d2_expectations():
    return {c["case_id"]: _expect(c["expect"]) for c in CASES if c["criterion"] == "d2"}


def test_fixture_covers_a_tail_that_clears_and_one_that_does_not():
    """The tail clause decides more verdicts than anything else in the rule."""
    tails = [float(e["tail_r"]) for e in _d2_expectations().values() if "tail_r" in e
             and e["tail_r"] != "nan"]
    assert any(t > 0 for t in tails) and any(t < 0 for t in tails)


def test_fixture_covers_a_correlation_of_each_sign():
    """A hedge needs the correlation NEGATIVE; a sign flip in the criterion
    would pass every positively-correlated sleeve if only one sign were here."""
    corrs = [float(e["corr"]) for e in _d2_expectations().values() if "corr" in e
             and e["corr"] != "nan"]
    assert any(c > 0 for c in corrs) and any(c < 0 for c in corrs)


def test_fixture_covers_a_year_clause_that_fails_on_one_year():
    """The reproduction clause has to be able to sink an otherwise-passing
    sleeve on its own — the Mar-Apr-2025 failure in one number."""
    assert any(e.get("met") == "FALSE" and float(e.get("tail_r", "nan")) > 0
               and float(e.get("corr", "nan")) < 0
               and int(e["ok_years"]) < HC.MIN_TAIL_YEARS
               and int(e["tot_years"]) >= HC.MIN_TAIL_YEARS
               for e in _d2_expectations().values())


def test_fixture_covers_a_year_below_the_date_minimum():
    """A thin year is REPORTED and not COUNTED. If it entered the denominator
    a two-year sleeve would fail for having a third, tiny year."""
    assert any("years_reported" in e and int(e["years_reported"]) > int(e["tot_years"])
               for e in _d2_expectations().values())


def test_fixture_covers_an_empty_cut_and_an_undefined_one():
    """Two different things, and both have been bugs: an EMPTY cut is dropped
    from the bucket list rather than printed as a zero, and an UNDEFINED one
    fails the rule closed rather than passing it vacuously."""
    assert any("negative dates" not in e.get("buckets", "negative dates")
               for e in _d2_expectations().values())
    assert any(e.get("tail_r") == "nan" and e.get("met") == "FALSE"
               for e in _d2_expectations().values())


def test_fixture_covers_a_cell_below_the_power_floor():
    """Below the floor the criterion returns nothing at all — there is no
    'weak MET' to quote."""
    assert any(e.get("none") == "TRUE" for e in _d2_expectations().values())


def test_fixture_covers_a_sweep_whose_winner_is_not_the_largest_fraction():
    """If the winner were always the largest tested size the rule would be
    doing nothing, and a bug that always returned `max(fractions)` would pass."""
    found = False
    for c in CASES:
        if c["criterion"] != "d3":
            continue
        e = _expect(c["expect"])
        if e.get("best_f") not in (None, "NONE"):
            found = found or float(e["best_f"]) < max(_fractions(c["fractions"]))
    assert found


def test_fixture_covers_a_sweep_no_fraction_clears():
    """NOT MET is a verdict, not an error, and it must not fall back to the
    least-harmful size."""
    assert any(_expect(c["expect"]).get("best_f") == "NONE"
               for c in CASES if c["criterion"] == "d3")


def test_fixture_covers_a_drawdown_series_that_only_rises():
    """A curve that never falls has no drawdown — zero, not the smallest gain,
    and not the first level."""
    assert any(_expect(c["expect"]).get("mdd") == "0.0"
               for c in CASES if c["criterion"] == "mdd")


def test_fixture_case_ids_are_unique():
    """Duplicate ids would collapse parametrize output and could hide a row."""
    ids = [c["case_id"] for c in CASES]
    assert len(ids) == len(set(ids))


def test_every_fixture_row_states_why_it_is_there():
    """The `why` column is the fixture's comment field, and it carries the hand
    derivation. A row without one is a row nobody can decide about when it
    fails."""
    assert all(c["why"].strip() for c in CASES)


def test_fixture_carries_no_broker_or_account_fields():
    """These are synthetic series, not fills. Nothing account-identifying may
    enter a tracked fixture — see CLAUDE.md's `/journal/` rule."""
    banned = {"account", "account_id", "acct", "source_ref", "exec_id",
              "net_liq", "netliquidation", "conid"}
    assert not (set(CASES[0]) & banned)


def test_every_criterion_in_the_library_has_at_least_one_case():
    """The library's entry points, named here so adding one without a case is
    a failure rather than an omission."""
    assert {c["criterion"] for c in CASES} == {"d2", "d3", "sleeve", "daily", "mdd"}


def test_the_library_re_exports_the_one_drawdown_implementation():
    """Not a copy, not a wrapper: the same function object as `lib/mtm_curve`'s
    and `bear_deploy`'s, which is what keeps the sizing rule's drawdown and the
    equity curve's the same measurement."""
    from scripts.backtest_study.f4_deployment.bear_deploy import max_drawdown as bd_mdd
    from scripts.backtest_study.lib.mtm_curve import max_drawdown as curve_mdd

    assert HC.max_drawdown is curve_mdd is bd_mdd


def test_the_sleeve_picker_is_the_body_behind_the_sleeve_cases():
    """`sleeve_pick` has no fixture criterion of its own because it is not a
    separate rule: `sleeve_dollars` IS it, plus reading one column off the
    chosen row. `calendar_hedge.bear_sleeve_dollars` reads the same pick and
    prices it instead, so this identity is what makes the two the same sleeve
    (research/hedge-programme-plan.md §"Q3, how much to hedge")."""
    for case in [c for c in CASES if c["criterion"] == "sleeve"]:
        rows = _rows(case["rows"])
        veto = {d for d in case["gate_veto"].split(";") if d}
        gate = (lambda d, rs: d not in veto) if veto else None
        picks = HC.sleeve_pick([r for r in rows if r.get("dol") is not None],
                               lambda r: r["key"], gate=gate)
        dollars = HC.sleeve_dollars(rows, lambda r: r["key"], dol_key="dol",
                                    gate=gate)
        assert {d: r["dol"] for d, r in picks.items()} == dollars


def test_the_year_cut_is_the_body_behind_the_d2_cases():
    """`year_tails` has no fixture criterion of its own for the same reason:
    it is D2's year clause with the MEASUREMENT left to the caller, so every
    d2 case exercises it. `calendar_hedge` H2(c) calls it with its own
    ordering key and measures the picks it has, which is why the cut had to
    come out of `hedge_contribution` rather than stay inside it."""
    for case in [c for c in CASES if c["criterion"] == "d2"]:
        kw = {"min_common": int(case["min_common"])} if case["min_common"] else {}
        dep, bear = _series(case["dep_series"]), _series(case["bear_series"])
        hc = HC.hedge_contribution(dep, bear, **kw)
        if hc is None:
            continue
        cuts = HC.year_tails(hc.common, key=lambda d: dep[d][0])
        assert [(c.year, c.n_dates, c.evaluated, list(c.tail_dates)) for c in cuts] == \
               [(y.year, y.n_overlap, y.evaluated, list(y.tail_dates)) for y in hc.years]


# ── the scalar size rule is the one body `qualifies` wraps ───────────────────
def test_unharmed_is_the_body_qualifies_delegates_to():
    """`hedge_timing` ARM H4 and `bear_deploy` D5 build their own daily paths and
    call `unharmed` on bare figures; `qualifies` is the SweepRow form. Both must
    agree on every side of both comparisons, including the eps-equal edge."""
    base = HC.SweepRow(f=0.0, total=0.0, mdd=-100.0, worst=-40.0, neg=0, downside_dev=0.0)
    for mdd, worst, want in [(-100.0, -40.0, True), (-100.0 - 1e-9, -40.0, True),
                             (-100.0 - 2e-9, -40.0, False), (-99.0, -40.0 - 2e-9, False),
                             (-50.0, -10.0, True)]:
        row = HC.SweepRow(f=0.5, total=0.0, mdd=mdd, worst=worst, neg=0, downside_dev=0.0)
        assert HC.unharmed(mdd, worst, base.mdd, base.worst) is want
        assert HC.qualifies(row, base) is HC.unharmed(mdd, worst, base.mdd, base.worst)
