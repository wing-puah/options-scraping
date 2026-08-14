"""Tests for the per-ticker IV-percentile layer:
- lib/barchart/iv_history.parse_iv_history (feed-row parsing, fuzzy field mapping)
- lib/iv_history: enrichment columns, as-of-date cell pick + its provenance status,
  flow-row iv_pct / iv_pct_status readers
- scripts/collector/fetch_iv_percentile._fetch_series (fetch_error vs empty_series) and
  its depth-exhaustion threshold, driven by fake sessions.
Pure functions, no network, no credentials."""
import asyncio

import pytest

from lib.barchart.iv_history import parse_iv_history
from lib.iv_history import (
    IV_ALL_COLUMNS,
    IV_ENRICH_COLUMNS,
    IV_MARKER_COLUMN,
    IV_STATUS_COLUMN,
    IV_STATUS_EMPTY,
    IV_STATUS_ERROR,
    IV_STATUS_OK,
    IV_STATUS_OUT_OF_WINDOW,
    IV_STATUS_STALE,
    LOOKUP_STALENESS_DAYS,
    as_of_iv_cells,
    as_of_iv_cells_with_status,
    iv_coverage_from_flow_rows,
    iv_pct_from_flow_rows,
)


@pytest.fixture(autouse=True)
def _restore_event_loop():
    """The _fetch_series cases call asyncio.run, which closes the loop and clears the
    global current loop on 3.11. Restore one after each test so later async-using
    modules (test_scraper, test_gc_flow) still find a current event loop — same
    fixture as tests/test_enrich_oi.py."""
    yield
    asyncio.set_event_loop(asyncio.new_event_loop())


# ---------------------------------------------------------------------------
# parse_iv_history
# ---------------------------------------------------------------------------

def test_parse_typed_toplevel_fields():
    rows = [
        {"tradeTime": "2026-06-30", "impliedVolatility": 0.55, "ivRank": 62.0, "ivPercentile": 71.0},
        {"tradeTime": "2026-06-29", "impliedVolatility": 0.50, "ivRank": 40.0, "ivPercentile": 55.0},
    ]
    out = parse_iv_history(rows)
    assert set(out) == {"2026-06-30", "2026-06-29"}
    assert out["2026-06-30"] == {"iv": 0.55, "iv_rank": 62.0, "iv_pct": 71.0}


def test_parse_real_feed_schema():
    """Field names + shape from the live options-historical/get feed (top-level display
    strings + a `raw` sub-dict of numbers; percentile/rank on a 0–100 scale)."""
    rows = [{
        "date": "2026-06-30",
        "weightedImpliedVolatility": "55.32%",
        "impliedVolatilityRank1y": "62.10%",
        "impliedVolatilityPercentile1y": "71.00%",
        "raw": {"date": "2026-06-30", "weightedImpliedVolatility": 0.5532,
                "impliedVolatilityRank1y": 62.10, "impliedVolatilityPercentile1y": 71.0},
    }]
    out = parse_iv_history(rows)
    assert out["2026-06-30"]["iv_pct"] == 71.0
    assert out["2026-06-30"]["iv_rank"] == 62.1
    assert out["2026-06-30"]["iv"] == 55.32


def test_parse_nested_field_dicts_prefer_value_scale():
    rows = [{
        "date": "2026-06-30",
        "impliedVolatilityPercentile1y": {"raw": 0.71, "value": "71.00%"},
    }]
    # The formatted `value` (0–100 scale) wins over the fractional `raw`.
    assert parse_iv_history(rows)["2026-06-30"]["iv_pct"] == 71.0


def test_parse_falls_back_to_raw_and_mdy_date_and_pct_strings():
    rows = [{"raw": {"tradeTime": "06/30/2026", "ivPercentile": "71%", "ivRank": "62"}}]
    out = parse_iv_history(rows)
    assert out["2026-06-30"]["iv_pct"] == 71.0
    assert out["2026-06-30"]["iv_rank"] == 62.0
    assert out["2026-06-30"]["iv"] is None  # no IV field present


def test_parse_drops_rows_with_no_iv_fields_or_bad_date():
    rows = [
        {"tradeTime": "2026-06-30"},                       # no IV fields → dropped
        {"impliedVolatility": 0.5, "ivPercentile": 40},    # no date → dropped
        {"tradeTime": "not-a-date", "ivPercentile": 40},   # bad date → dropped
    ]
    assert parse_iv_history(rows) == {}
    assert parse_iv_history(None) == {}


# ---------------------------------------------------------------------------
# enrichment column contract
# ---------------------------------------------------------------------------

def test_enrich_column_contract():
    assert IV_ENRICH_COLUMNS == ["iv", "iv_rank", "iv_pct"]
    assert IV_MARKER_COLUMN == "iv_pct_enriched_on"
    assert IV_STATUS_COLUMN == "iv_pct_status"
    assert IV_ALL_COLUMNS == ["iv", "iv_rank", "iv_pct", "iv_pct_enriched_on", "iv_pct_status"]


def test_status_vocabulary_is_exactly_five_stable_strings():
    """These strings land in the compiled flow file, the rollup CSV and the analysis
    tab — renaming one orphans every row already written with it."""
    assert [IV_STATUS_OK, IV_STATUS_STALE, IV_STATUS_OUT_OF_WINDOW,
            IV_STATUS_EMPTY, IV_STATUS_ERROR] == [
        "ok", "stale_fallback", "out_of_window", "empty_series", "fetch_error"]


# ---------------------------------------------------------------------------
# as_of_iv_cells
# ---------------------------------------------------------------------------

def test_as_of_exact_date_formats_decimals_and_points():
    series = {"2026-06-30": {"iv": 55.32, "iv_rank": 62.0, "iv_pct": 71.0}}
    cells = as_of_iv_cells(series, "2026-06-30")
    assert cells == {"iv": "55.32", "iv_rank": "0.62", "iv_pct": "0.71"}
    assert list(cells) == IV_ENRICH_COLUMNS  # no marker (caller adds it)


def test_as_of_most_recent_on_or_before_within_staleness():
    series = {"2026-06-26": {"iv": 50.0, "iv_rank": 40.0, "iv_pct": 55.0}}  # 4 days before
    assert as_of_iv_cells(series, "2026-06-30")["iv_pct"] == "0.55"


def test_as_of_skips_too_stale_and_future_rows():
    series = {
        "2026-06-15": {"iv": 50.0, "iv_rank": 40.0, "iv_pct": 60.0},  # > staleness → skip
        "2026-07-05": {"iv": 60.0, "iv_rank": 80.0, "iv_pct": 80.0},  # after anchor → skip
    }
    assert as_of_iv_cells(series, "2026-06-30") == {"iv": "", "iv_rank": "", "iv_pct": ""}
    assert (0 - LOOKUP_STALENESS_DAYS) < 0  # staleness constant is a positive window


def test_as_of_none_fields_blank():
    series = {"2026-06-30": {"iv": None, "iv_rank": None, "iv_pct": 71.0}}
    cells = as_of_iv_cells(series, "2026-06-30")
    assert cells == {"iv": "", "iv_rank": "", "iv_pct": "0.71"}


def test_as_of_bad_anchor_returns_blanks():
    assert as_of_iv_cells({"2026-06-30": {"iv_pct": 71.0}}, "not-a-date") == {
        "iv": "", "iv_rank": "", "iv_pct": ""}


# ---------------------------------------------------------------------------
# as_of_iv_cells_with_status — the depth/provenance discrimination
# ---------------------------------------------------------------------------

def test_status_exact_hit_is_ok():
    series = {"2026-06-30": {"iv": 55.32, "iv_rank": 62.0, "iv_pct": 71.0}}
    cells, status = as_of_iv_cells_with_status(series, "2026-06-30")
    assert status == IV_STATUS_OK
    assert cells["iv_pct"] == "0.71"


def test_status_within_staleness_window_is_stale_fallback():
    series = {"2026-06-26": {"iv": 50.0, "iv_rank": 40.0, "iv_pct": 55.0}}  # 4 days before
    cells, status = as_of_iv_cells_with_status(series, "2026-06-30")
    assert status == IV_STATUS_STALE
    assert cells["iv_pct"] == "0.55"


def test_status_series_entirely_after_anchor_is_out_of_window():
    """The depth signal: Barchart's ~2yr history is measured from the RUN date, so a
    backfill of an old date gets a series that starts AFTER the date asked for. That is
    exhausted retention, NOT a missing name — and it can never be filled by a re-run."""
    series = {"2026-07-01": {"iv": 60.0, "iv_rank": 80.0, "iv_pct": 80.0},
              "2026-07-05": {"iv": 61.0, "iv_rank": 81.0, "iv_pct": 81.0}}
    cells, status = as_of_iv_cells_with_status(series, "2026-06-30")
    assert status == IV_STATUS_OUT_OF_WINDOW
    assert cells == {"iv": "", "iv_rank": "", "iv_pct": ""}


def test_status_empty_series_is_empty_series():
    assert as_of_iv_cells_with_status({}, "2026-06-30") == (
        {"iv": "", "iv_rank": "", "iv_pct": ""}, IV_STATUS_EMPTY)


def test_status_gap_older_than_staleness_is_empty_not_out_of_window():
    """A row BEFORE the anchor proves retention still reaches this date — the blank is
    an ordinary feed gap, so it must not be mistaken for depth exhaustion."""
    series = {"2026-06-15": {"iv": 50.0, "iv_rank": 40.0, "iv_pct": 60.0},  # too stale
              "2026-07-05": {"iv": 60.0, "iv_rank": 80.0, "iv_pct": 80.0}}  # after anchor
    assert as_of_iv_cells_with_status(series, "2026-06-30")[1] == IV_STATUS_EMPTY


def test_status_bad_anchor_is_fetch_error_never_a_depth_signal():
    series = {"2026-07-05": {"iv_pct": 80.0}}
    cells, status = as_of_iv_cells_with_status(series, "not-a-date")
    assert status == IV_STATUS_ERROR      # a caller bug, bucketed away from out_of_window
    assert cells == {"iv": "", "iv_rank": "", "iv_pct": ""}


def test_as_of_iv_cells_is_a_thin_wrapper_over_the_status_variant():
    series = {"2026-06-26": {"iv": 50.0, "iv_rank": 40.0, "iv_pct": 55.0}}
    for anchor in ("2026-06-30", "not-a-date"):
        assert as_of_iv_cells(series, anchor) == as_of_iv_cells_with_status(series, anchor)[0]


# ---------------------------------------------------------------------------
# _fetch_series — the producer's fetch_error vs empty_series split
# ---------------------------------------------------------------------------

class _RaisingSession:
    async def fetch_options_overview_history(self, *a, **kw):
        raise RuntimeError("barchart said no")


class _EmptySession:
    async def fetch_options_overview_history(self, *a, **kw):
        return []


def test_fetch_series_exception_is_fetch_error():
    import fetch_iv_percentile as f
    series, status = asyncio.run(
        f._fetch_series(_RaisingSession(), "NVDA", "2026-06-18", "2026-06-30", 100))
    assert (series, status) == ({}, IV_STATUS_ERROR)


def test_fetch_series_empty_feed_is_empty_series():
    import fetch_iv_percentile as f
    series, status = asyncio.run(
        f._fetch_series(_EmptySession(), "NVDA", "2026-06-18", "2026-06-30", 100))
    assert (series, status) == ({}, IV_STATUS_EMPTY)


def test_depth_exhausted_banner_trips_only_past_the_declared_share():
    """The banner is the operator's only warning that a whole date is past the
    retention edge, so the threshold is a pre-declared constant, not a guess."""
    import fetch_iv_percentile as f
    n = 100
    over = int(f.DEPTH_EXHAUSTED_SHARE * n) + 1
    assert f._depth_exhausted({IV_STATUS_OUT_OF_WINDOW: over}, n)
    assert not f._depth_exhausted({IV_STATUS_OUT_OF_WINDOW: over - 2}, n)
    assert not f._depth_exhausted({IV_STATUS_OK: n}, n)
    assert not f._depth_exhausted({}, 0)          # nothing pending → never trips


# ---------------------------------------------------------------------------
# iv_pct_from_flow_rows (consumer)
# ---------------------------------------------------------------------------

def test_iv_pct_from_flow_rows_one_per_symbol_first_nonblank():
    rows = [
        {"Symbol": "nvda", "iv_pct": "0.71"},
        {"Symbol": "NVDA", "iv_pct": "0.71"},   # duplicate row for same ticker
        {"Symbol": "KO", "iv_pct": ""},         # blank → skipped
        {"Symbol": "AMD", "iv_pct": "0.52"},
    ]
    assert iv_pct_from_flow_rows(rows) == {"NVDA": 0.71, "AMD": 0.52}


def test_iv_pct_from_flow_rows_empty():
    assert iv_pct_from_flow_rows([]) == {}
    assert iv_pct_from_flow_rows(None) == {}


# ---------------------------------------------------------------------------
# iv_coverage_from_flow_rows (provenance consumer)
# ---------------------------------------------------------------------------

def test_iv_coverage_from_flow_rows_one_per_symbol_first_nonblank():
    rows = [
        {"Symbol": "nvda", "iv_pct": "0.71", "iv_pct_status": "ok"},
        {"Symbol": "NVDA", "iv_pct": "0.71", "iv_pct_status": "ok"},   # duplicate row
        {"Symbol": "KO", "iv_pct": "", "iv_pct_status": ""},           # blank → skipped
        {"Symbol": "AMD", "iv_pct": "", "iv_pct_status": "out_of_window"},
    ]
    assert iv_coverage_from_flow_rows(rows) == {"NVDA": "ok", "AMD": "out_of_window"}


def test_iv_coverage_from_flow_rows_pre_status_rows_are_blank_not_an_error():
    """Rows enriched before the column existed carry no status — the column just stays
    empty rather than the reader failing or inventing one."""
    assert iv_coverage_from_flow_rows([{"Symbol": "NVDA", "iv_pct": "0.71"}]) == {}
    assert iv_coverage_from_flow_rows([]) == {}
    assert iv_coverage_from_flow_rows(None) == {}
