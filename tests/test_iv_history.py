"""Tests for the per-ticker IV-percentile layer:
- lib/barchart_iv_history.parse_iv_history (feed-row parsing, fuzzy field mapping)
- lib/iv_history: enrichment columns, as-of-date cell pick, flow-row iv_pct reader.
Pure functions, no network."""
from lib.barchart_iv_history import parse_iv_history
from lib.iv_history import (
    IV_ALL_COLUMNS,
    IV_ENRICH_COLUMNS,
    IV_MARKER_COLUMN,
    LOOKUP_STALENESS_DAYS,
    as_of_iv_cells,
    iv_pct_from_flow_rows,
)


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
    assert IV_ALL_COLUMNS == ["iv", "iv_rank", "iv_pct", "iv_pct_enriched_on"]


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
