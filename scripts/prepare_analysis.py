"""
Reads options flow data from Google Drive and prints compact markdown to stdout
for LLM analysis.

Default behavior (no flags): emits per-ticker rollups + the top-N largest raw
trades per section. This keeps Claude's context small enough to reason over
the full day's data without truncation.

Modes:
- Default (summary): ticker rollups + top-N raw trades. Use this for /options analyze.
- --raw: dump every row verbatim (old behavior). Heavy on context — use only when
  the summary loses something important.
- --ticker SYMBOL: filter to a single ticker, then dump that ticker's rows raw.
  Use after the summary surfaces a name worth drilling into.

Date selection:
- (default) latest file per prefix
- --date YYYY-MM-DD: most recent file for that date
"""
import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.logger import setup_logging
from lib.baseline import BASELINE_TAB, baseline_context_md, compute_daily_baseline
from lib.csv_utils import parse_csv
from lib.drive_client import FILE_PREFIXES, get_drive_client
from lib.flow_summary import (
    FLOW_CSV_COLUMNS,
    build_scored_flow_rollup,
    cross_section_md,
    filter_by_ticker,
    flow_rollup_csv,
    hedge_pressure_md,
    rows_to_markdown_raw,
    summarize_flow,
    summarize_persistence,
    summarize_unusual,
)

log = logging.getLogger("prepare_analysis")

# The Score column's meaning lives in one reference doc so it is easy to find and
# edit; we inline it into the markdown stream as a one-line pointer + the doc body.
_SCORE_LEGEND_DOC = Path(__file__).parent.parent / "config" / "conviction-score.md"


def _score_legend() -> str:
    """The conviction-score explainer, read from its reference doc (quoted)."""
    try:
        body = _SCORE_LEGEND_DOC.read_text().strip()
    except OSError:
        return "> Conviction score: see config/conviction-score.md"
    # Blockquote it so it reads as a legend in the LLM-facing markdown stream.
    return "\n".join("> " + line if line else ">" for line in body.splitlines())


def _date_from_filename(name: str, prefix: str) -> str | None:
    """Parse the YYYY-MM-DD trading date out of a `{prefix}-YYYYMMDD-HHMM.csv` name."""
    rest = name[len(prefix) + 1:]            # "YYYYMMDD-HHMM.csv"
    compact = rest.split("-", 1)[0]
    if len(compact) == 8 and compact.isdigit():
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
    return None


def _latest_available_date(client) -> str | None:
    """Newest trading date for which stock-flow data exists in Drive."""
    files = client.list_files("stocks-flow")  # newest first
    for f in files:
        d = _date_from_filename(f["name"], "stocks-flow")
        if d:
            return d
    return None


def _last_n_trading_days(end_iso: str, n: int) -> list[str]:
    """The n weekdays ending at end_iso (inclusive), oldest → newest.

    Weekday-only, matching the rest of the system; days with no Drive data just
    come back empty and show as '—' in the persistence trajectory.
    """
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


# Which unusual section corroborates each flow section, for the conviction score.
_FLOW_UNUSUAL_PAIR = {"stocks-flow": "unusual-stocks", "etfs-flow": "unusual-etfs"}


def fetch_data(
    date_str: str | None = None,
    *,
    raw: bool = False,
    ticker: str | None = None,
    top_n: int = 75,
    days: int = 1,
    baseline: bool = True,
) -> str:
    """Fetch Drive data and format for LLM consumption.

    raw=True → emit every row per section (old behavior; heavy context).
    ticker=SYM → filter every section to that symbol and emit raw.
    Otherwise → emit scored per-ticker rollup + top-N raw trades per section +
    cross-section. days>1 also appends a multi-day persistence section.
    """
    client = get_drive_client()
    section_rows: dict[str, list[dict]] = {}

    for key, _title, _kind in _ANALYSIS_SECTIONS:
        section_rows[key] = _load_rows(client, key, date_str)

    # --ticker: filter then dump raw, scoped to one symbol across all sections.
    if ticker:
        sections_out = []
        for key, title, _kind in _ANALYSIS_SECTIONS:
            filtered = filter_by_ticker(section_rows[key], ticker)
            sections_out.append(rows_to_markdown_raw(filtered, f"{title} — {ticker.upper()} only"))
        return "\n\n".join(sections_out)

    # --raw: every row in every section.
    if raw:
        sections_out = []
        for key, title, _kind in _ANALYSIS_SECTIONS:
            sections_out.append(rows_to_markdown_raw(section_rows[key], title))
        return "\n\n".join(sections_out)

    # Default: scored per-section summaries + cross-section.
    sections_out = [_score_legend()]
    for key, title, kind in _ANALYSIS_SECTIONS:
        rows = section_rows[key]
        if kind == "flow":
            unusual = section_rows[_FLOW_UNUSUAL_PAIR[key]]
            sections_out.append(summarize_flow(rows, title, top_n=top_n, unusual_rows=unusual))
        else:
            sections_out.append(summarize_unusual(rows, title, top_n=top_n))

    sections_out.append(cross_section_md(section_rows["stocks-flow"], section_rows["unusual-stocks"]))

    # Hedge pressure: broad ETF put protection vs single-stock bullish demand,
    # extrinsic-only, as one precomputed 0–100 number instead of a daily
    # qualitative rediscovery.
    sections_out.append(hedge_pressure_md(section_rows["stocks-flow"], section_rows["etfs-flow"]))

    # Baseline: today's aggregates vs the trailing BaselineDaily window, so the
    # regime read is normalized against history instead of a lone cross-section.
    if baseline:
        md = _baseline_section(section_rows, date_str, client)
        if md:
            sections_out.append(md)

    # days>1: load the trailing window and append persistence tracking.
    if days > 1:
        sections_out.extend(_persistence_sections(client, date_str, days))

    return "\n\n".join(sections_out)


def _baseline_section(section_rows: dict[str, list[dict]], date_str: str | None, client) -> str:
    """The `## Baseline context` markdown section, or "" when unavailable.

    Today's row is computed in-process from the already-fetched sections (the
    sheet does not need to contain today); only the history is read from the
    BaselineDaily tab. Sheets being unreachable degrades to omitting the
    section — it must never block an analysis run.
    """
    anchor = date_str or _latest_available_date(client)
    if not anchor:
        return ""
    today_row = compute_daily_baseline(
        anchor, section_rows["stocks-flow"], section_rows["etfs-flow"])
    try:
        from lib.sheets_client import get_all_rows
        history = get_all_rows(BASELINE_TAB)
    except Exception:
        log.warning("Baseline history unavailable — omitting baseline section", exc_info=True)
        return ""
    return baseline_context_md(today_row, history, anchor)


def fetch_scored_csv(date_str: str | None = None) -> str:
    """Build the scored flow rollup (stocks + ETFs) for a date as a CSV string.

    This is the machine-readable twin of the markdown rollup tables: one row per
    ticker, tagged by section, carrying the conviction score and its components.
    The legend lives in config/conviction-score.md, not in the data file.
    """
    client = get_drive_client()
    sections = []
    for flow_key, label in (("stocks-flow", "stocks"), ("etfs-flow", "etfs")):
        flow_rows = _load_rows(client, flow_key, date_str)
        if not flow_rows:
            continue
        unusual = _load_rows(client, _FLOW_UNUSUAL_PAIR[flow_key], date_str)
        sections.append((label, build_scored_flow_rollup(flow_rows, unusual)))
    return flow_rollup_csv(sections)


def _persistence_sections(client, date_str: str | None, days: int) -> list[str]:
    """Load the trailing `days` trading days and build stock + ETF persistence tables."""
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

    return [
        summarize_persistence(stock_days, "Stocks flow", top_n=30),
        summarize_persistence(etf_days, "ETF flow", top_n=20),
    ]


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Fetch data for this trading date (YYYY-MM-DD).")
    parser.add_argument("--raw", action="store_true",
                        help="Dump every row verbatim (old behavior). Heavy on context.")
    parser.add_argument("--ticker",
                        help="Filter every section to this ticker and emit raw rows.")
    parser.add_argument("--top", type=int, default=75,
                        help="Top-N raw trades to include alongside each summary (default: 75).")
    parser.add_argument("--days", type=int, default=1,
                        help="Trailing trading-day window for persistence tracking "
                             "(default: 1 = no persistence section). E.g. --days 5.")
    parser.add_argument("--no-baseline", action="store_true",
                        help="Skip the baseline-context section (no Sheets read).")
    parser.add_argument("--csv", metavar="PATH",
                        help="Write the scored flow rollup (stocks + ETFs) to PATH as "
                             "CSV instead of printing markdown. '-' writes to stdout.")
    args = parser.parse_args()

    if args.csv:
        log.info("Building scored CSV — date=%s", args.date or "latest")
        csv_text = fetch_scored_csv(date_str=args.date)
        if args.csv == "-":
            print(csv_text, end="")
        else:
            Path(args.csv).write_text(csv_text)
            log.info("Wrote scored rollup CSV to %s", args.csv)
        return

    log.info(
        "Fetching data — date=%s mode=%s top=%s days=%s",
        args.date or "latest",
        "ticker=" + args.ticker.upper() if args.ticker else ("raw" if args.raw else "summary"),
        args.top,
        args.days,
    )
    print(fetch_data(date_str=args.date, raw=args.raw, ticker=args.ticker,
                     top_n=args.top, days=args.days, baseline=not args.no_baseline))


if __name__ == "__main__":
    main()
