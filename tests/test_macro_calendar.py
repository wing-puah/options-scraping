"""Tests for scripts/backtest_study/lib/macro_calendar.py and the calendar file.

Two populations: behaviour tests run on a hand-built in-memory fixture;
schema / coverage / spot-check tests run on the real `config/macro-events.yml`.
The spot-check dates are hardcoded ON PURPOSE — they are official published
release dates (public record transcribed at authoring time), not figures read
off one export, so this is the one place hardcoded dates belong.
"""
from __future__ import annotations

from datetime import date

import pytest

from scripts.backtest_study.lib import macro_calendar as MC


# ---------------------------------------------------------------------------
# fixture calendar: three types, one unscheduled event, tight verified windows
# ---------------------------------------------------------------------------

FIXTURE = {
    "meta": {
        "compiled": date(2026, 8, 19),
        "verified_through": {
            "fomc": date(2026, 12, 31),
            "cpi": date(2026, 6, 30),
            "nfp": date(2026, 12, 31),
        },
    },
    "events": [
        {"date": date(2026, 1, 28), "type": "fomc", "release_et": "14:00",
         "label": "Jan 2026 decision"},
        {"date": date(2026, 3, 18), "type": "fomc", "release_et": "14:00",
         "label": "Mar 2026 decision"},
        {"date": date(2026, 2, 6), "type": "fomc", "release_et": "14:00",
         "label": "emergency action", "unscheduled": True},
        {"date": date(2026, 2, 11), "type": "cpi", "release_et": "08:30",
         "label": "Jan 2026 CPI"},
        {"date": date(2026, 3, 11), "type": "cpi", "release_et": "08:30",
         "label": "Feb 2026 CPI"},
        {"date": date(2026, 2, 6), "type": "nfp", "release_et": "08:30",
         "label": "Jan 2026 employment situation"},
    ],
}


@pytest.fixture()
def cal() -> MC.MacroCalendar:
    return MC.MacroCalendar.parse(FIXTURE)


# -- boundary conventions ----------------------------------------------------

def test_next_event_is_strictly_after_as_of(cal):
    # as_of ON an event date: that event is not "next".
    assert cal.next_event(date(2026, 1, 28), "fomc").date == date(2026, 3, 18)
    assert cal.next_event(date(2026, 1, 27), "fomc").date == date(2026, 1, 28)


def test_last_event_includes_as_of_itself(cal):
    assert cal.last_event(date(2026, 1, 28), "fomc").date == date(2026, 1, 28)
    assert cal.last_event(date(2026, 1, 27), "fomc") is None


def test_count_between_is_start_exclusive_end_inclusive(cal):
    # start ON the Jan decision: it is excluded; end ON the Mar decision: included.
    assert cal.count_between(date(2026, 1, 28), date(2026, 3, 18), "fomc") == 2
    # (the unscheduled 02-06 action counts — it happened during the window)
    assert cal.count_between(date(2026, 1, 28), date(2026, 3, 17), "fomc") == 1
    assert cal.count_between(date(2026, 3, 18), date(2026, 3, 18), "fomc") == 0


# -- pre_open ----------------------------------------------------------------

@pytest.mark.parametrize("et,expected", [
    ("08:30", True),   # CPI/NFP/PCE print before the open
    ("14:00", False),  # FOMC statement / minutes land after the entry fill
    ("09:30", False),  # at-the-open is NOT pre-open
])
def test_pre_open(et, expected):
    e = MC.Event(date(2026, 1, 1), "cpi", et, "x")
    assert e.pre_open is expected


# -- verified_through refusal -------------------------------------------------

def test_next_event_past_verified_through_is_none_not_nothing_ahead(cal):
    # cpi verified through 2026-06-30; a July query must answer None even
    # though the file simply has no later cpi entry either way.
    assert cal.covers(date(2026, 7, 1), "cpi") is False
    assert cal.next_event(date(2026, 7, 1), "cpi") is None
    # inside the window but with no later event in file: also None (honest).
    assert cal.next_event(date(2026, 4, 1), "cpi") is None
    assert cal.covers(date(2026, 4, 1), "cpi") is True


# -- unscheduled semantics -----------------------------------------------------

def test_unscheduled_excluded_forward_included_backward(cal):
    # Forward from Feb 1: the 02-06 emergency action is NOT knowable in advance.
    assert cal.next_event(date(2026, 2, 1), "fomc").date == date(2026, 3, 18)
    # Backward from Feb 10: it happened, and it is the latest fomc event.
    assert cal.last_event(date(2026, 2, 10), "fomc").date == date(2026, 2, 6)


# -- event_read / window_read ---------------------------------------------------

def test_event_read_day0_pre_and_post_open(cal):
    # 2026-02-06 has an 08:30 nfp (in the entry price) and a 14:00 unscheduled
    # fomc action (the position sits in front of it).
    r = MC.event_read(cal, date(2026, 2, 6), types=("fomc", "nfp"))
    assert r["on_asof_nfp"] == "pre_open"
    assert r["on_asof_fomc"] == "post_open"
    assert r["days_since_last_nfp"] == 0
    # strictly-after: neither day-0 event is "next"
    assert r["days_to_next_fomc"] == (date(2026, 3, 18) - date(2026, 2, 6)).days


def test_event_read_pooled_forward_requires_every_type_covered(cal):
    # July 2026: cpi is past verified_through, so the pooled forward pair must
    # be None even though fomc/nfp are still covered (an unverified schedule
    # could hide an earlier event).
    r = MC.event_read(cal, date(2026, 7, 1), types=("fomc", "cpi", "nfp"))
    assert r["days_to_next_macro"] is None
    assert r["next_macro_type"] is None
    # backward pooling always answers
    assert r["days_since_last_macro"] is not None


def test_window_read_counts(cal):
    r = MC.window_read(cal, date(2026, 1, 28), date(2026, 3, 18),
                       hold_end=date(2026, 2, 20), types=("fomc", "cpi"))
    assert r["n_fomc_in_dte"] == 2      # 02-06 unscheduled + 03-18; 01-28 excluded
    assert r["n_cpi_in_dte"] == 2
    assert r["n_fomc_in_hold"] == 1     # 02-06 only
    assert r["n_cpi_in_hold"] == 1      # 02-11
    assert r["n_macro_in_dte"] == 4
    assert r["n_macro_in_hold"] == 2


def test_window_read_without_hold_end_reports_none(cal):
    r = MC.window_read(cal, date(2026, 1, 28), date(2026, 3, 18),
                       types=("fomc",))
    assert r["n_fomc_in_hold"] is None
    assert r["n_macro_in_hold"] is None


# -- loader validation -----------------------------------------------------------

def test_parse_rejects_unknown_type():
    bad = {"meta": FIXTURE["meta"],
           "events": [{"date": date(2026, 1, 1), "type": "gdp",
                       "release_et": "08:30", "label": "x"}]}
    with pytest.raises(ValueError, match="unknown type"):
        MC.MacroCalendar.parse(bad)


def test_parse_rejects_duplicate_type_date():
    bad = {"meta": FIXTURE["meta"],
           "events": [FIXTURE["events"][0], dict(FIXTURE["events"][0])]}
    with pytest.raises(ValueError, match="duplicate"):
        MC.MacroCalendar.parse(bad)


def test_parse_rejects_missing_verified_through():
    bad = {"meta": {"compiled": date(2026, 8, 19), "verified_through": {}},
           "events": FIXTURE["events"][:1]}
    with pytest.raises(ValueError, match="verified_through missing"):
        MC.MacroCalendar.parse(bad)


def test_parse_rejects_malformed_release_et():
    bad = {"meta": FIXTURE["meta"],
           "events": [{"date": date(2026, 1, 1), "type": "cpi",
                       "release_et": "830", "label": "x"}]}
    with pytest.raises(ValueError, match="release_et"):
        MC.MacroCalendar.parse(bad)


# ---------------------------------------------------------------------------
# the real file: schema, coverage, structural cross-checks, source spot-checks
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real() -> MC.MacroCalendar:
    return MC.MacroCalendar.from_yaml()


def test_real_file_loads_all_five_types(real):
    cov = real.coverage()
    for t in MC.EVENT_TYPES:
        assert cov[t]["n"] > 0, f"no {t} events in config/macro-events.yml"
        assert cov[t]["verified_through"] is not None


def test_real_file_covers_both_eras_book_range(real):
    # Data claim; population: the v3 book (2024-06-17..2026-04-07) and the
    # current-era exports (2024-01-10..2025-01-13). Every type must span both.
    lo, hi = date(2024, 1, 10), date(2026, 4, 7)
    cov = real.coverage()
    for t in MC.EVENT_TYPES:
        assert cov[t]["first"] <= lo, f"{t} starts after the book: {cov[t]['first']}"
        assert cov[t]["last"] >= hi, f"{t} ends before the book: {cov[t]['last']}"


def test_real_file_event_cadence_is_sane(real):
    """Loose per-year counts — catches a dropped quarter, not off-by-one-day."""
    for t, (lo, hi) in {"fomc": (7, 9), "cpi": (10, 13),
                        "nfp": (10, 13), "pce": (9, 13)}.items():
        for year in (2024, 2025):
            n = len(real.events((t,), date(year, 1, 1), date(year, 12, 31)))
            assert lo <= n <= hi, f"{t} {year}: {n} events, expected {lo}-{hi}"


def test_real_file_minutes_lag_decisions_by_about_three_weeks(real):
    """Structural property of the release policy — catches a mis-transcribed
    pair that an eight-date spot-check would miss."""
    decisions = [e.date for e in real.events(("fomc",)) if not e.unscheduled]
    for m in real.events(("fomc_minutes",)):
        lags = [(m.date - d).days for d in decisions if 0 < (m.date - d).days <= 30]
        assert any(19 <= lag <= 23 for lag in lags), (
            f"minutes {m.date} ({m.label}) is not 19-23 days after any decision")


def test_real_file_source_spot_checks(real):
    """Hand-pinned against the official schedules at authoring time
    (federalreserve.gov/monetarypolicy/fomccalendars.htm, bls.gov/schedule,
    bea.gov/news/schedule). Public record, not export-derived figures."""
    pins = [
        ("fomc", date(2024, 6, 12)),          # Jun 2024 decision
        ("fomc_minutes", date(2024, 7, 3)),   # Jun 2024 minutes
        ("fomc", date(2025, 3, 19)),          # Mar 2025 decision
        ("fomc", date(2026, 1, 28)),          # Jan 2026 decision
        ("fomc", date(2027, 12, 8)),          # Dec 2027 decision (forward tail)
        # BLS / BEA pins appended from the fetched schedules:
        ("cpi", SPOT_CPI),
        ("nfp", SPOT_NFP),
        ("pce", SPOT_PCE),
    ]
    have = {(e.type, e.date) for e in real.events()}
    for t, d in pins:
        assert (t, d) in have, f"expected {t} on {d} per the official schedule"


def test_real_file_release_times(real):
    for e in real.events(("fomc", "fomc_minutes")):
        assert e.release_et == "14:00", f"{e.type} {e.date}: {e.release_et}"
        assert not e.pre_open
    for e in real.events(("cpi", "nfp")):
        assert e.release_et == "08:30", f"{e.type} {e.date}: {e.release_et}"
        assert e.pre_open
    # BEA moved three releases to 10:00 ET (Nov 2024, Apr 2025, and the
    # shutdown-era Dec 2025 / Jan 2026 pair) — those are POST-open.
    for e in real.events(("pce",)):
        assert e.release_et in ("08:30", "10:00"), f"pce {e.date}: {e.release_et}"
        assert e.pre_open is (e.release_et == "08:30")


# Pinned from the fetched official schedules (bls.gov/schedule/<YYYY>/home.htm,
# bea.gov/news/schedule) at authoring time, 2026-08-19.
SPOT_CPI = date(2024, 6, 12)   # May 2024 CPI
SPOT_NFP = date(2024, 7, 5)    # Jun 2024 employment situation
SPOT_PCE = date(2024, 6, 28)   # May 2024 personal income & outlays


def test_real_file_keeps_the_2025_shutdown_gap(real):
    """The BLS 2025 schedule page shows NO October-2025-reference release for
    either series: Sep 2025 CPI was delayed to 2025-10-24 and the next CPI is
    2025-12-18; Sep 2025 employment situation was delayed to 2025-11-20 and
    the next is 2025-12-16. The gap is real — a future re-transcription must
    not "fix" it by interpolating the usual cadence."""
    assert real.count_between(date(2025, 10, 24), date(2025, 12, 17), "cpi") == 0
    assert (real.last_event(date(2025, 11, 19), "nfp").date
            == date(2025, 9, 5))
