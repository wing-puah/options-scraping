"""`bear_deploy`'s D1 window check must FAIL CLOSED on an empty ex-window cut.

D1 is pre-registered (`research/pre-registrations/f4_deployment/bear_deploy.md`)
as re-screening "the identical pre-declared clause vocabulary" as `bear_arm`'s
B1, so the two must agree on what "survives both window cuts" means. They did
not: B1 rejects a subset whose ex-window cut has no rows (its `stat()` returns
None and the gate tests `c is not None`), while D1 computed the cut with
`fmean` — which returns nan on no rows — and then filtered nan OUT of its
`all()`. The window check therefore passed VACUOUSLY on exactly the subsets
ground rule 4 exists to reject: those lying entirely inside a dominant window.

Deterministic, reproducible, and wrong — and invisible to a grader reading the
printed report, which shows only the verdict. Hence a test rather than a
re-read: this is a code-behaviour claim, so it belongs in `tests/`.
"""
from __future__ import annotations

import math

from scripts.backtest_study.f1_selection import bear_arm
from scripts.backtest_study.f4_deployment.bear_deploy import cuts_pass, fmean
from scripts.backtest_study.lib import protocol as P

NAN = float("nan")


def test_empty_cut_fails_rather_than_being_waived() -> None:
    assert cuts_pass({"ex_2025_mar_apr": NAN, "ex_2026_feb_apr": 0.10}) is False


def test_both_cuts_empty_fails() -> None:
    assert cuts_pass({"ex_2025_mar_apr": NAN, "ex_2026_feb_apr": NAN}) is False


def test_negative_cut_fails() -> None:
    assert cuts_pass({"ex_2025_mar_apr": -0.01, "ex_2026_feb_apr": 0.20}) is False


def test_non_negative_cuts_pass() -> None:
    assert cuts_pass({"ex_2025_mar_apr": 0.0, "ex_2026_feb_apr": 0.20}) is True


def test_subset_wholly_inside_a_dominant_window_yields_an_empty_cut() -> None:
    """The end-to-end shape of the bug: every row inside Mar-Apr 2025."""
    rows = [{"date": "2025-03-14", "Rb": 0.5}, {"date": "2025-04-02", "Rb": 0.5}]
    cuts = {name: fmean([r["Rb"] for r in rs])
            for name, rs in P.window_cuts(rows).items() if name != "ALL"}

    assert math.isnan(cuts["ex_2025_mar_apr"]), "the dominant-window cut must empty out"
    # The old guard: `all(v >= 0 for v in cuts.values() if v == v)` — nan filtered
    # out, so a window-dominated subset sailed through the anti-window-fit check.
    assert all(v >= 0 for v in cuts.values() if v == v) is True
    assert cuts_pass(cuts) is False


def test_d1_and_b1_agree_on_the_empty_cut() -> None:
    """B1's encoding of the same criterion, pinned alongside so neither drifts."""
    assert bear_arm.stat([], "E") is None            # B1: no rows -> gate fails
    assert cuts_pass({"ex_2025_mar_apr": NAN}) is False   # D1: now likewise
