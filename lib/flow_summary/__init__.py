"""Aggregate parsed Barchart CSV rows into compact, LLM-friendly summaries.

Package layout:
- ``_helpers`` — small stateless parse / format / bucket helpers (low-churn)
- ``core``     — the aggregation logic: per-ticker rollup, conviction scoring,
                 ref-03 OI factor measures, hedge pressure, persistence, and the
                 markdown / CSV renderers

The public API is re-exported here so existing ``from lib.flow_summary import …``
call sites keep working after the split into a package.
"""
from lib.flow_summary._helpers import (
    _classify_sentiment,
    _fmt_money,
    _to_float,
    _to_int,
)
from lib.flow_summary.core import (
    FLOW_CSV_COLUMNS,
    HEDGE_TICKERS,
    OI_BREAKDOWN_CSV_COLUMNS,
    _finalize_oi_factors,
    _flow_ticker_rows,
    _voloi_by_symbol,
    build_scored_flow_rollup,
    cross_section_md,
    cross_section_tickers,
    filter_by_ticker,
    flow_rollup_csv,
    hedge_pressure,
    hedge_pressure_md,
    oi_breakdown_csv,
    persistence_callout_md,
    rows_to_markdown_raw,
    score_flow_rollup,
    score_label,
    summarize_flow,
    summarize_persistence,
)

__all__ = [
    "FLOW_CSV_COLUMNS",
    "HEDGE_TICKERS",
    "OI_BREAKDOWN_CSV_COLUMNS",
    "build_scored_flow_rollup",
    "cross_section_md",
    "cross_section_tickers",
    "filter_by_ticker",
    "flow_rollup_csv",
    "hedge_pressure",
    "hedge_pressure_md",
    "oi_breakdown_csv",
    "persistence_callout_md",
    "rows_to_markdown_raw",
    "score_flow_rollup",
    "score_label",
    "summarize_flow",
    "summarize_persistence",
    # Re-exported helpers used by lib.baseline / tests.
    "_classify_sentiment",
    "_finalize_oi_factors",
    "_flow_ticker_rows",
    "_fmt_money",
    "_to_float",
    "_to_int",
    "_voloi_by_symbol",
]
