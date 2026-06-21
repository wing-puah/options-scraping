"""
Fetch options flow data from Google Drive and format as compact markdown for
LLM analysis (the 'fetch' step of the analysis pipeline).

Public API used by core.py:
  fetch_data(date_str, *, top_n, days) → str
  fetch_scored_csv(date_str) → str        (machine-readable rollup CSV)
  _last_n_trading_days(end_iso, n) → list[str]
  _latest_available_date(client) → str | None
"""
import logging
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from lib.baseline import BASELINE_TAB, baseline_context_md, compute_daily_baseline
from lib.csv_utils import parse_csv
from lib.drive_client import FILE_PREFIXES, get_drive_client
from lib.sheets_client import get_all_rows
from lib.vol_snapshot import fetch_vol_snapshot, vol_snapshot_md
from lib.flow_summary import (
    build_scored_flow_rollup,
    cross_section_md,
    filter_by_ticker,
    flow_rollup_csv,
    hedge_pressure_md,
    oi_breakdown_csv,
    persistence_callout_md,
    rows_to_markdown_raw,
    summarize_flow,
    ticker_metrics,
)

log = logging.getLogger("analysis_pipeline.fetch")

_SCORE_LEGEND_DOC = Path(__file__).parent.parent.parent / "config" / "conviction-score.md"


def _score_legend() -> str:
    try:
        body = _SCORE_LEGEND_DOC.read_text().strip()
    except OSError:
        return "> Conviction score: see config/conviction-score.md"
    return "\n".join("> " + line if line else ">" for line in body.splitlines())


def _date_from_filename(name: str, prefix: str) -> str | None:
    """Parse the YYYY-MM-DD trading date out of a `{prefix}-YYYYMMDD-HHMM.csv` name."""
    rest = name[len(prefix) + 1:]
    compact = rest.split("-", 1)[0]
    if len(compact) == 8 and compact.isdigit():
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
    return None


def _latest_available_date(client) -> str | None:
    """Newest trading date for which stock-flow data exists in Drive."""
    files = client.list_files("stocks-flow")
    for f in files:
        d = _date_from_filename(f["name"], "stocks-flow")
        if d:
            return d
    return None


def _last_n_trading_days(end_iso: str, n: int) -> list[str]:
    """The n weekdays ending at end_iso (inclusive), oldest → newest."""
    d = date.fromisoformat(end_iso)
    out: list[str] = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(out))


# Section kind drives which summarizer is applied.
# (key, title, kind) — kind ∈ {"flow", "unusual"}
_ANALYSIS_SECTIONS = [
    ("unusual-stocks", FILE_PREFIXES["unusual-stocks"], "unusual"),
    ("unusual-etfs",   FILE_PREFIXES["unusual-etfs"],   "unusual"),
    ("stocks-flow",    FILE_PREFIXES["stocks-flow"],    "flow"),
    ("etfs-flow",      FILE_PREFIXES["etfs-flow"],      "flow"),
]

_FLOW_UNUSUAL_PAIR = {"stocks-flow": "unusual-stocks", "etfs-flow": "unusual-etfs"}


def _load_rows(client, prefix: str, date_str: str | None) -> list[dict]:
    """Fetch one section's CSV from Drive and parse to row dicts. [] on miss."""
    try:
        if date_str:
            name, content = client.download_for_date(prefix, date_str)
        else:
            name, content = client.download_latest(prefix)
        if not content:
            log.warning("No Drive file found for prefix '%s'", prefix)
            return []
        log.info("Fetched '%s' for prefix '%s'", name, prefix)
        return parse_csv(content)
    except Exception:
        log.exception("Could not fetch prefix '%s'", prefix)
        return []


def fetch_data(
    date_str: str | None = None,
    *,
    raw: bool = False,
    ticker: str | None = None,
    focus_tickers: list[str] | None = None,
    top_n: int = 75,
    raw_n: int = 20,
    days: int = 1,
    baseline: bool = True,
    vol: bool = True,
    audit_csv_path: "Path | None" = None,
) -> str:
    """Fetch Drive data and format for LLM consumption.

    raw=True → emit every row per section (heavy context).
    ticker=SYM → filter every section to that symbol and emit raw.
    focus_tickers=[...] → keep the full scored pipeline (scoring + market
        context sections), but narrow the per-ticker flow rollup + raw trades to
        those symbols. Distinct from `ticker`, which strips everything to raw.
    Otherwise → scored rollup (top_n tickers) + top raw_n raw trades per flow
    section. Unusual rows are fetched for scoring only — no separate table.
    days>1 appends a multi-day persistence callout.
    """
    client = get_drive_client()
    section_rows: dict[str, list[dict]] = {}

    for key, _title, _kind in _ANALYSIS_SECTIONS:
        section_rows[key] = _load_rows(client, key, date_str)

    if ticker:
        sections_out = []
        for key, title, _kind in _ANALYSIS_SECTIONS:
            filtered = filter_by_ticker(section_rows[key], ticker)
            sections_out.append(rows_to_markdown_raw(filtered, f"{title} — {ticker.upper()} only"))
        return "\n\n".join(sections_out)

    if raw:
        sections_out = []
        for key, title, _kind in _ANALYSIS_SECTIONS:
            sections_out.append(rows_to_markdown_raw(section_rows[key], title))
        return "\n\n".join(sections_out)

    focus = {t.strip().upper() for t in focus_tickers if t.strip()} if focus_tickers else None

    sections_out = []
    if focus:
        sections_out.append(
            "**Focus tickers:** " + ", ".join(sorted(focus)) +
            " — per-ticker flow tables below are narrowed to these names; "
            "market-level sections (regime, hedge pressure, baseline) remain full-market."
        )
    if vol:
        snap = fetch_vol_snapshot(date_str)
        md = vol_snapshot_md(snap) if snap else ""
        if md:
            sections_out.append(md)
    sections_out.append(_score_legend())
    for key, title, kind in _ANALYSIS_SECTIONS:
        if kind != "flow":
            continue
        rows = section_rows[key]
        unusual = section_rows[_FLOW_UNUSUAL_PAIR[key]]
        sections_out.append(summarize_flow(rows, title, top_n=top_n, raw_n=raw_n, unusual_rows=unusual, focus=focus))

    sections_out.append(cross_section_md(section_rows["stocks-flow"], section_rows["unusual-stocks"]))
    sections_out.append(hedge_pressure_md(section_rows["stocks-flow"], section_rows["etfs-flow"]))

    if baseline:
        md = _baseline_section(section_rows, date_str, client)
        if md:
            sections_out.append(md)

    if days > 1:
        sections_out.extend(_persistence_sections(client, date_str, days))

    if audit_csv_path is not None:
        _write_audit_csv(section_rows, audit_csv_path)

    return "\n\n".join(sections_out)


def _write_audit_csv(section_rows: dict[str, list[dict]], path: Path) -> None:
    sections = []
    for flow_key, label in (("stocks-flow", "stocks"), ("etfs-flow", "etfs")):
        rows = section_rows[flow_key]
        if rows:
            unusual = section_rows[_FLOW_UNUSUAL_PAIR[flow_key]]
            sections.append((label, build_scored_flow_rollup(rows, unusual)))
    if not sections:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(flow_rollup_csv(sections), encoding="utf-8")
    log.info("Audit CSV written to %s", path)

    # Companion long-format OI / put-call breakdown (DTE × moneyness + raw
    # call/put OI sums). Skipped when no ticker has enriched OI data.
    oi_csv = oi_breakdown_csv(sections)
    if oi_csv:
        oi_path = path.with_name(path.name.replace("-rollup.csv", "-oi-breakdown.csv"))
        oi_path.write_text(oi_csv, encoding="utf-8")
        log.info("OI breakdown CSV written to %s", oi_path)


def _baseline_section(section_rows: dict[str, list[dict]], date_str: str | None, client) -> str:
    anchor = date_str or _latest_available_date(client)
    if not anchor:
        return ""
    today_row = compute_daily_baseline(
        anchor, section_rows["stocks-flow"], section_rows["etfs-flow"])
    try:
        history = get_all_rows(BASELINE_TAB)
    except Exception:
        log.warning("Baseline history unavailable — omitting baseline section", exc_info=True)
        return ""
    return baseline_context_md(today_row, history, anchor)


def fetch_scored_csv(date_str: str | None = None) -> str:
    """Build the scored flow rollup (stocks + ETFs) for a date as a CSV string."""
    client = get_drive_client()
    sections = []
    for flow_key, label in (("stocks-flow", "stocks"), ("etfs-flow", "etfs")):
        flow_rows = _load_rows(client, flow_key, date_str)
        if not flow_rows:
            continue
        unusual = _load_rows(client, _FLOW_UNUSUAL_PAIR[flow_key], date_str)
        sections.append((label, build_scored_flow_rollup(flow_rows, unusual)))
    return flow_rollup_csv(sections)


def fetch_ticker_metrics(date_str: str | None = None) -> dict[str, dict]:
    """Drive flow (stocks + ETFs) for a date → ``{SYMBOL: {oi_confirm_pct, cpir, iv_spread}}``.

    The single recompute call the rollup backfill needs: Drive I/O lives here, the
    pure computation in :func:`lib.flow_summary.ticker_metrics`. The three metrics
    don't depend on the unusual-activity rows, so only the flow sections are loaded.
    ETF symbols are merged after stocks (the two symbol sets are disjoint)."""
    client = get_drive_client()
    out: dict[str, dict] = {}
    for flow_key in ("stocks-flow", "etfs-flow"):
        rows = _load_rows(client, flow_key, date_str)
        if rows:
            out.update(ticker_metrics(rows))
    return out


def _persistence_sections(client, date_str: str | None, days: int) -> list[str]:
    """Load the trailing `days` trading days and emit persistent-name callouts."""
    anchor = date_str or _latest_available_date(client)
    if not anchor:
        return ["## Persistence\n\n_No data available to anchor a window._\n"]

    window = _last_n_trading_days(anchor, days)
    log.info("Persistence window: %s", ", ".join(window))

    stock_days, etf_days = [], []
    for d in window:
        stock_days.append({
            "date": d,
            "flow_rows": _load_rows(client, "stocks-flow", d),
            "unusual_rows": _load_rows(client, "unusual-stocks", d),
        })
        etf_days.append({
            "date": d,
            "flow_rows": _load_rows(client, "etfs-flow", d),
            "unusual_rows": _load_rows(client, "unusual-etfs", d),
        })

    date_range = f"{window[0]} → {window[-1]}"
    lines = [f"## Persistence ({days} days: {date_range})\n"]
    for title, day_list in (("Stocks", stock_days), ("ETFs", etf_days)):
        callout = persistence_callout_md(day_list, title)
        lines.append(callout if callout else f"_{title}: no names recurring ≥3 days._")
    return ["\n".join(lines)]
