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
from lib.counterpart_iv import build_iv_lookup, sidecar_name
from lib.iv_history import iv_pct_from_flow_rows
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


def _load_counterpart_iv(client, date_str: str | None) -> dict[str, list[dict]]:
    """Load the per-date counterpart-IV sidecar → ``build_iv_lookup`` dict ({} on miss).

    The sidecar (``scripts/fetch_counterpart_iv.py``) holds settlement IV for counterpart legs
    that didn't trade, so the matched-pair ``iv_spread`` / skew reads see the fuller
    chain. Keyed to the resolved date (latest folder when ``date_str`` is None), so
    live and backtest read the same file. Any failure degrades gracefully to
    flow-only metrics.
    """
    try:
        d = date_str
        if d is None:
            folders = client.list_date_folders()
            if not folders:
                return {}
            d = max(folders)
        folder = client.find_date_folder(d)
        if folder is None:
            return {}
        fid = client.file_exists(sidecar_name(d), folder)
        if not fid:
            return {}
        return build_iv_lookup(parse_csv(client.download(fid, name=sidecar_name(d))))
    except Exception:
        log.exception("Could not load counterpart IV for %s", date_str)
        return {}


def _load_iv_pct(flow_rows: list[dict]) -> dict[str, float]:
    """``{UPPER_SYMBOL: iv_pct}`` read off the enriched flow rows' ``iv_pct`` column.

    The column is written by ``scripts/fetch_iv_percentile.py`` (scrapes Barchart's
    options-overview history per ticker, appends iv/iv_rank/iv_pct to the compiled flow
    file), so fetch does no scraping or tab lookup — it just reads the as-of-date value
    already on the row. Degrades to ``{}`` on any failure or when a name wasn't
    enriched; the rollup then shows a blank IVpct and the framework falls back to the
    VIX proxy / absolute IV (Step 4).
    """
    try:
        return iv_pct_from_flow_rows(flow_rows)
    except Exception:
        log.exception("Could not read IV percentile from flow rows")
        return {}


def load_flow_rows_for_scoring(date_str: str | None) -> list[dict]:
    """Re-download the compiled stocks-flow + etfs-flow rows for `date_str` (or the
    latest date when None), already carrying scripts/fetch_price_catalyst.py's
    price/earnings enrichment columns. A small independent Drive read — mirrors
    how _load_counterpart_iv/_load_iv_pct re-derive their own inputs rather than
    threading a bigger object through fetch_data's return value."""
    try:
        client = get_drive_client()
        return (_load_rows(client, "stocks-flow", date_str)
                + _load_rows(client, "etfs-flow", date_str))
    except Exception:
        log.exception("Could not load flow rows for scoring (%s)", date_str)
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

    counterpart_iv = _load_counterpart_iv(client, date_str)
    iv_pct = _load_iv_pct(section_rows["stocks-flow"] + section_rows["etfs-flow"])

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
        sections_out.append(summarize_flow(rows, title, top_n=top_n, raw_n=raw_n,
                                            unusual_rows=unusual, focus=focus,
                                            counterpart_iv=counterpart_iv, iv_pct=iv_pct))

    sections_out.append(cross_section_md(section_rows["stocks-flow"], section_rows["unusual-stocks"]))
    sections_out.append(hedge_pressure_md(section_rows["stocks-flow"], section_rows["etfs-flow"]))

    if baseline:
        md = _baseline_section(section_rows, date_str, client)
        if md:
            sections_out.append(md)

    if days > 1:
        sections_out.extend(_persistence_sections(client, date_str, days))

    if audit_csv_path is not None:
        _write_audit_csv(section_rows, audit_csv_path, counterpart_iv, iv_pct)

    return "\n\n".join(sections_out)


def _write_audit_csv(section_rows: dict[str, list[dict]], path: Path,
                     counterpart_iv: dict[str, list[dict]] | None = None,
                     iv_pct: dict[str, float] | None = None) -> None:
    sections = []
    for flow_key, label in (("stocks-flow", "stocks"), ("etfs-flow", "etfs")):
        rows = section_rows[flow_key]
        if rows:
            unusual = section_rows[_FLOW_UNUSUAL_PAIR[flow_key]]
            sections.append((label, build_scored_flow_rollup(rows, unusual, counterpart_iv, iv_pct)))
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
    counterpart_iv = _load_counterpart_iv(client, date_str)
    flow_by_key = {k: _load_rows(client, k, date_str) for k in ("stocks-flow", "etfs-flow")}
    iv_pct = _load_iv_pct(flow_by_key["stocks-flow"] + flow_by_key["etfs-flow"])
    sections = []
    for flow_key, label in (("stocks-flow", "stocks"), ("etfs-flow", "etfs")):
        flow_rows = flow_by_key[flow_key]
        if not flow_rows:
            continue
        unusual = _load_rows(client, _FLOW_UNUSUAL_PAIR[flow_key], date_str)
        sections.append((label, build_scored_flow_rollup(flow_rows, unusual, counterpart_iv, iv_pct)))
    return flow_rollup_csv(sections)


def fetch_ticker_metrics(date_str: str | None = None) -> dict[str, dict]:
    """Drive flow (stocks + ETFs) for a date → ``{SYMBOL: {oi_confirm_pct, cpir, iv_spread}}``.

    The single recompute call the rollup backfill needs: Drive I/O lives here, the
    pure computation in :func:`lib.flow_summary.ticker_metrics`. The three metrics
    don't depend on the unusual-activity rows, so only the flow sections are loaded.
    ETF symbols are merged after stocks (the two symbol sets are disjoint)."""
    client = get_drive_client()
    counterpart_iv = _load_counterpart_iv(client, date_str)
    flow_by_key = {k: _load_rows(client, k, date_str) for k in ("stocks-flow", "etfs-flow")}
    iv_pct = _load_iv_pct(flow_by_key["stocks-flow"] + flow_by_key["etfs-flow"])
    out: dict[str, dict] = {}
    for flow_key in ("stocks-flow", "etfs-flow"):
        rows = flow_by_key[flow_key]
        if rows:
            out.update(ticker_metrics(rows, counterpart_iv, iv_pct))
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
