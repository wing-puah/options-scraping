"""
IBKR Flex trade export → the `rawpull` schema.

PRODUCTION TIER, and deliberately dependency-free on the network: this module
turns a CSV that already exists on disk into the exact dict `rawpull.validate()`
accepts, so every downstream step (`reconcile`, `risk`, `report`, `writer`) runs
unchanged. It is the second broker transport, sitting beside the Client Portal
path in `s01_pull.py` — see that module's note that swapping transport is a change
there and nowhere else.

WHY A SECOND SOURCE. The Client Portal path needs a locally-run Gateway that
must be re-logged-in through a browser roughly daily. The Flex Web Service needs
none of that — a token and a query id, or simply a CSV the operator already
exports by hand. The trade-off is what the report carries, and the two gaps are
load-bearing enough to state up front:

  * NO GREEKS. A Flex statement has no delta, so exposure for this path is
    enriched separately from Barchart (`lib/greeks.py`). Until that runs, every
    position is `delta_source=unavailable` — never zero. See the missing/zero
    invariant in config.py.
  * NO OPEN-POSITIONS SECTION in a trades-only query — CONDITIONALLY. Without
    a second, separately-saved OpenPositions query, the open book is
    RECONSTRUCTED by netting signed quantity per conid across every row given.
    That is exact if and only if the rows cover each position's whole life,
    which is why `parse()` takes a LIST of files (pass every year you hold) and
    why `_provenance_warnings()` names each position whose history demonstrably
    starts before the window rather than letting a half-seen position pass as
    real. A THIRD guard, `_coverage_gap_warnings()`, catches the failure
    neither of those can: a calendar span that NO source covers at all, where
    a position closed inside the hole leaves no closing fill anywhere and
    still nets open, with nothing anomalous in the rows to point at. Passing
    `parse(..., positions_source=<OpenPositions statement>)` replaces all of
    that with a declared book (`parse_positions()`) — the netted book then
    becomes a CROSS-CHECK on the declared one instead of the answer itself;
    see `_book_diff_warnings()`.

WHAT THE COLUMNS ARE. A trades-only Flex query exports 16 fields:

    Description, UnderlyingSymbol, Open/CloseIndicator, Quantity, TradePrice,
    CostBasis, FifoPnlRealized, Strike, Expiry, DateTime, Put/Call, AssetClass,
    Symbol, TradeID, Conid, Buy/Sell

`Conid` is the important one: contract identity is EXACT, so this path never
price-matches to recover a strike the way the old hand-pasted MCP snapshots had
to. `TradeID` is unique per execution and becomes `exec_id`, which is what the
journal dedupes on.

TWO WIRE FORMATS, SAME FIELDS. A Flex query is defined as either delimited text
or XML, and the choice is made in Account Management when the query is saved —
the web service returns whichever that query specifies, so a caller cannot
assume one. XML names the same 16 fields as camelCase attributes on a `<Trade>`
element (`underlyingSymbol`, `openCloseIndicator`, `assetCategory`, ...).
`_read_rows` detects the format and renames the XML attributes to the CSV
column names once, so every function below this point sees exactly one shape.

TIMESTAMPS ARE NOT UTC. Flex writes `DateTime` as `YYYY-MM-DD;HHMMSS` in the
ACCOUNT'S configured timezone, with no offset recorded anywhere in the file.
Rather than stamp a `Z` on a local time and make it wrong, this module emits a
naive ISO-8601 string and sets `trade_time_tz` on the pull so the ambiguity is
recorded instead of hidden. Nothing downstream compares these across zones —
grouping keys on equality and the journal keys on calendar date.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import rawpull
from ..config import DELTA_SOURCE_UNAVAILABLE

log = logging.getLogger(__name__)

SOURCE = "ibkr-flex"

# The account timezone is not recorded in the export; see the module docstring.
TRADE_TIME_TZ = "account-local (IBKR Flex; no offset in the export, not converted)"

OPTION_ASSET_CLASSES = {"OPT", "FOP"}

# Named in the errors below so the operator is pointed at the thing to fix.
# Spelled out rather than imported from `lib.ibkr.flex`, which owns it: this
# module is pure parsing and imports no transport — see the module docstring.
POSITIONS_QUERY_ID_ENV = "IBKR_FLEX_OPEN_POSITIONS_QUERY_ID"

# Every column the parser actually reads. A Flex query missing one of these
# produces a journal with silently wrong contents rather than an error, so the
# check is up front and fatal.
REQUIRED_COLUMNS = (
    "UnderlyingSymbol", "Open/CloseIndicator", "Quantity", "TradePrice",
    "FifoPnlRealized", "Strike", "Expiry", "DateTime", "Put/Call",
    "AssetClass", "TradeID", "Conid", "Buy/Sell",
)

# XML `<Trade>` attribute → the CSV column carrying the same field. Applied in
# `_rows_from_xml` so the two wire formats converge before any parsing logic
# runs; see the module docstring. Note the two that are NOT simple case changes:
# `cost` is the CSV's CostBasis and `assetCategory` is its AssetClass.
XML_TRADE_ATTRS = {
    "description": "Description",
    "underlyingSymbol": "UnderlyingSymbol",
    "openCloseIndicator": "Open/CloseIndicator",
    "quantity": "Quantity",
    "tradePrice": "TradePrice",
    "cost": "CostBasis",
    "costBasis": "CostBasis",
    "fifoPnlRealized": "FifoPnlRealized",
    "strike": "Strike",
    "expiry": "Expiry",
    "dateTime": "DateTime",
    "putCall": "Put/Call",
    "assetCategory": "AssetClass",
    "symbol": "Symbol",
    "tradeID": "TradeID",
    "conid": "Conid",
    "buySell": "Buy/Sell",
    "multiplier": "Multiplier",
}

# The columns a Flex OpenPositions query exports (CSV names). Mirrors
# REQUIRED_COLUMNS above but for the declared-book section rather than Trades —
# see `parse_positions`.
REQUIRED_POSITION_COLUMNS = (
    "Conid", "Quantity", "AssetClass", "Strike", "Expiry", "Put/Call",
    "UnderlyingSymbol",
)

# Columns that ONLY a Trades export has — a position has no execution id, no
# side and no open/close indicator. They exist because REQUIRED_POSITION_COLUMNS
# is entirely a SUBSET of a trades header: every one of those seven columns is
# present on a Trade row too, so the missing-column check CANNOT tell a trades
# export from a positions one, and a trades CSV aimed at the positions query
# parses cleanly into one "declared position" per fill. That book is then
# treated as AUTHORITATIVE (`book_reconstructed=False`) — a confidently wrong
# book, which is worse than any error. The XML branch is safe by construction
# (it looks for an `<OpenPositions>` element); this is the delimited format's
# equivalent, and the reverse direction needs no guard because a positions
# header fails REQUIRED_COLUMNS outright.
TRADES_ONLY_COLUMNS = ("TradeID", "Buy/Sell", "Open/CloseIndicator")

# XML `<OpenPosition>` attribute -> the CSV column carrying the same field.
# NOTE the one attribute that is NOT a case change of its CSV name: the XML
# quantity attribute is `position` (IBKR's XML calls the signed contract count
# "position", matching the rawpull field name it becomes), while the CSV
# column for the same value is `Quantity`. Getting this wrong would silently
# read every declared position as size zero.
XML_POSITION_ATTRS = {
    "assetCategory": "AssetClass",
    "symbol": "Symbol",
    "description": "Description",
    "conid": "Conid",
    "underlyingSymbol": "UnderlyingSymbol",
    "multiplier": "Multiplier",
    "strike": "Strike",
    "expiry": "Expiry",
    "putCall": "Put/Call",
    "reportDate": "ReportDate",
    "position": "Quantity",
    "markPrice": "MarkPrice",
    "positionValue": "PositionValue",
    "openPrice": "OpenPrice",
    "costBasisPrice": "CostBasisPrice",
    "costBasisMoney": "CostBasisMoney",
    "fifoPnlUnrealized": "FifoPnlUnrealized",
    "side": "Side",
    "levelOfDetail": "LevelOfDetail",
}

# Flex `period` values that cover too little history for the netted open book to
# be trustworthy. The book is reconstructed by netting fills per conid, so a
# statement covering one session can only ever see positions touched THAT
# session — anything opened earlier is absent entirely, which no per-position
# check can detect. See `_window_warning`.
SHORT_PERIODS = {"LastBusinessDay", "Today", "LastWeek", "LastMonth"}


class FlexParseError(ValueError):
    """A Flex export that cannot be turned into a trustworthy pull."""


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------
def _label(source) -> str:
    """A name for a source that reads well in an error, a log line or the
    report's SOURCE LIMITS block. A token-fetched statement has no filename —
    `repr(StringIO)` there would put a memory address in front of the operator
    where the answer they need is 'the one you just downloaded'."""
    if isinstance(source, io.StringIO):
        return getattr(source, "name", None) or "the Flex web-service statement"
    return str(source)


def _source_text(source: str | Path | io.StringIO) -> str:
    if isinstance(source, io.StringIO):
        return source.getvalue()
    path = Path(source)
    if not path.exists():
        raise FlexParseError(f"Flex export not found: {path}")
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _xml_root(text: str, source) -> ET.Element:
    """Parse Flex XML text into its root element, or raise a FlexParseError
    naming the source. Shared by every XML reader in this module (trades and
    positions alike) so a malformed statement is reported identically
    regardless of which section it was meant to carry.
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise FlexParseError(
            f"Flex export {_label(source)} is not parseable XML: {exc}") from exc
    if root.find("Status") is not None:
        # Not a statement at all: a Flex Web Service STATUS ENVELOPE, which the
        # transport is supposed to have raised on (lib/ibkr/flex.py). Saying so
        # here too is what keeps a saved one replayable — otherwise the section
        # checks below diagnose an envelope's missing sections as a
        # misconfigured query, which is exactly the wrong place to send the
        # operator looking.
        code = root.findtext("ErrorCode") or "?"
        message = root.findtext("ErrorMessage") or root.findtext("Status") or ""
        raise FlexParseError(
            f"Flex export {_label(source)} is not a statement — it is the Flex "
            f"Web Service's own error response (code {code}: {message}). "
            "Nothing is wrong with the saved query; re-run the pull.")
    return root


def _rows_from_xml(text: str, source) -> tuple[list[dict], dict]:
    """`<Trade>` elements of an XML Flex statement, renamed to CSV columns.

    Also returns the `<FlexStatement>` window (account, fromDate, toDate,
    period), which the delimited format does not carry at all. That window is
    the only way to detect a statement too short to reconstruct the open book
    from, so it is read here and judged in `_window_warning`.
    """
    root = _xml_root(text, source)

    statement = root.find(".//FlexStatement")
    meta = dict(statement.attrib) if statement is not None else {}

    rows = [{XML_TRADE_ATTRS[k]: v for k, v in el.attrib.items() if k in XML_TRADE_ATTRS}
            for el in root.iter("Trade")]
    if not rows:
        # Distinguish "the query ran and found nothing" from "the query is not a
        # trades query" — the first is a real, ordinary day, the second is a
        # misconfiguration that would otherwise read as a flat one.
        window = (f"{meta.get('fromDate', '?')} to {meta.get('toDate', '?')}"
                  f" (period {meta.get('period', '?')})")
        raise FlexParseError(
            f"Flex statement {_label(source)} contains no <Trade> elements for {window}. "
            "Either there were no trades in that window, or the query's sections "
            "do not include Trades at the execution level.")
    return rows, meta


SECTION_TRADES = "trades"
SECTION_POSITIONS = "positions"
SECTION_OTHER = "other"


def _csv_section_kind(fields: list[str]) -> str:
    """Which section a delimited statement's HEADER line introduces.

    Judged on the column names alone. The positions test must exclude the
    trades-only columns as well as require its own, because
    REQUIRED_POSITION_COLUMNS is a subset of a trades header — see
    TRADES_ONLY_COLUMNS. A data row lands on `other` harmlessly: its fields are
    values, which never spell out a full set of column names.
    """
    names = set(fields)
    if set(REQUIRED_COLUMNS) <= names:
        return SECTION_TRADES
    if set(REQUIRED_POSITION_COLUMNS) <= names and not set(TRADES_ONLY_COLUMNS) & names:
        return SECTION_POSITIONS
    return SECTION_OTHER


def _csv_sections(text: str) -> list[tuple[str, list[str]]]:
    """Split a delimited Flex statement into `(kind, lines)`, headers included.

    A Flex CSV bundles sections back to back with NO marker other than each
    section's own header line (the layout `_net_liquidation_from_csv` has
    always assumed). Two independent signals open a new section, and either
    alone is enough:

      * the line is a RECOGNISED header (trades or positions), or
      * its field count differs from the section it would otherwise join —
        sections exist precisely because their column sets differ, so their
        widths differ too.

    The width rule is what stops an unrecognised trailing block (a NAV /
    Account Information section, say) from being folded into its neighbour and
    arriving as garbage rows. Blank lines separate nothing and join nothing.
    """
    sections: list[tuple[str, list[str]]] = []
    width: int | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = next(csv.reader([line]), [])
        kind = _csv_section_kind(fields)
        opens_section = (not sections
                         or kind in (SECTION_TRADES, SECTION_POSITIONS)
                         or len(fields) != width)
        if opens_section:
            sections.append((kind, [line]))
            width = len(fields)
        else:
            sections[-1][1].append(line)
    return sections


def _csv_section(text: str, kind: str, source) -> str | None:
    """The text of `text`'s `kind` section, or None to use `text` as it stands.

    None for a single-section statement is deliberate rather than lazy: it
    hands the caller back the ORIGINAL text untouched, so every one-section
    export — which is every export this pipeline has ever seen — takes a code
    path identical to the one it took before sections existed, down to the
    error messages.
    """
    sections = _csv_sections(text)
    if len(sections) <= 1:
        return None
    matching = [lines for section_kind, lines in sections if section_kind == kind]
    if not matching:
        return None
    if len(matching) > 1:
        raise FlexParseError(
            f"Flex export {_label(source)} carries {len(matching)} {kind} "
            "sections. A statement holds at most one of each; reading them as "
            "one section would merge two different reporting windows.")
    return "\n".join(matching[0]) + "\n"


def _read_rows(source: str | Path | io.StringIO) -> tuple[list[dict], dict]:
    """Rows of one Flex statement, as dicts keyed by the CSV column names.

    Accepts a path or in-memory text, in EITHER wire format — the format is
    detected from the content rather than the filename, because a token-fetched
    statement arrives as bare text with no name at all. A multi-section
    delimited statement is carved down to its Trades section first; a
    single-section one is read exactly as it always was.
    """
    text = _source_text(source)
    if text.lstrip().startswith("<"):
        return _rows_from_xml(text, source)

    body = _csv_section(text, SECTION_TRADES, source)
    rows = list(csv.DictReader(io.StringIO(text if body is None else body)))
    if not rows:
        raise FlexParseError(f"Flex export {_label(source)} has no data rows")

    missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
    if missing:
        raise FlexParseError(
            f"Flex export {_label(source)} is missing column(s): {', '.join(missing)}. "
            "The query must include them — a trades query with columns removed "
            "produces a journal that looks complete and is not.")
    return rows, {}


# --------------------------------------------------------------------------
# OpenPositions — the declared book (see `parse_positions`)
# --------------------------------------------------------------------------
def _net_liquidation_from_xml(root: ET.Element) -> float | None:
    """NetLiquidation from a NAV/Account-Information section, DETECTED off the
    parsed tree rather than assumed present — an OpenPositions query is not
    required to carry one. IBKR's NAV section is the `EquitySummaryByReport
    DateInBase` element (figure on its `total` attribute); some query
    configurations instead emit a bare `NetLiquidation` element. Either is
    accepted; neither present means the query has no NAV section, and this
    returns None rather than guessing at one.
    """
    for el in root.iter():
        if el.tag in ("EquitySummaryByReportDateInBase", "NetLiquidation"):
            for attr in ("netLiquidation", "total", "value"):
                if attr in el.attrib:
                    value = _opt_num(el.attrib[attr])
                    if value is not None:
                        return value
    return None


def _net_liquidation_from_csv(text: str) -> float | None:
    """Same detection for the delimited wire format.

    A Flex Web Service CSV can bundle several sections (Trades, OpenPositions,
    NAV/Account Information, ...) into one file with no section marker other
    than each section's own header line, since their column sets differ. This
    scans for a header line naming a `NetLiquidation` column and reads the
    value directly beneath it — it does not assume the OpenPositions section
    itself carries the figure, because it never does.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines[:-1]):
        header = next(csv.reader([line]), [])
        if "NetLiquidation" in header:
            idx = header.index("NetLiquidation")
            data = next(csv.reader([lines[i + 1]]), [])
            if idx < len(data):
                value = _opt_num(data[idx])
                if value is not None:
                    return value
    return None


def _localname(tag) -> str:
    """An XML tag with any `{namespace}` prefix stripped.

    Flex statements are not namespaced today, but matching on the localname
    costs nothing and means a namespaced statement reads as a book with no
    positions in it — the one failure mode this module must never have.
    """
    return str(tag).rsplit("}", 1)[-1]


def _read_position_rows(source) -> tuple[list[dict], dict, float | None]:
    """Rows of one Flex OpenPositions statement, its declared window (XML
    only), and its NetLiquidation if the query happens to carry a NAV section.

    Mirrors `_read_rows`/`_rows_from_xml` (CSV/XML detection, XML attribute
    rename) but is deliberately NOT built on top of them: `_rows_from_xml`
    raises when it finds zero `<Trade>` elements, because an empty trades
    statement usually means the query's sections are wrong. Here the two cases
    are separable and are separated — an `<OpenPositions>` section with no
    children is the ordinary flat book, while NO such section at all is a
    query saved without it, and only the second raises. (A statement that
    declares a flat book while the fills say otherwise is caught later, in
    `parse()`.)
    """
    text = _source_text(source)
    if text.lstrip().startswith("<"):
        root = _xml_root(text, source)
        statement = root.find(".//FlexStatement")
        meta = dict(statement.attrib) if statement is not None else {}
        rows = [{XML_POSITION_ATTRS[k]: v for k, v in el.attrib.items()
                 if k in XML_POSITION_ATTRS}
                for el in root.iter() if _localname(el.tag) == "OpenPosition"]
        if not rows and not any(_localname(el.tag) == "OpenPositions"
                                for el in root.iter()):
            raise FlexParseError(
                f"Flex statement {_label(source)} carries no OpenPositions "
                f"section at all — {POSITIONS_QUERY_ID_ENV} is pointing at a "
                "query saved without it (a trades query, most likely). Add the "
                "Open Positions section to that query, or unset the variable to "
                "go back to netting the book from fills.")
        return rows, meta, _net_liquidation_from_xml(root)

    # The Positions section only — but `_net_liquidation_from_csv` below still
    # gets the WHOLE text, because the NAV figure lives in a different section
    # of the same statement and has always been found by scanning across them.
    body = _csv_section(text, SECTION_POSITIONS, source)
    reader = csv.DictReader(io.StringIO(text if body is None else body))
    header = reader.fieldnames or []
    trades_only = [c for c in TRADES_ONLY_COLUMNS if c in header]
    if trades_only:
        # Checked BEFORE the missing-column test, which a trades header passes —
        # see TRADES_ONLY_COLUMNS for why that check cannot catch this.
        raise FlexParseError(
            f"Flex export {_label(source)} is a TRADES export, not an "
            f"OpenPositions one — its header carries {', '.join(trades_only)}, "
            f"which a position never has. {POSITIONS_QUERY_ID_ENV} is pointing "
            "at the trades query; point it at one saved with the Open Positions "
            "section, or unset it to net the book from fills. (A statement "
            "carrying BOTH sections is fine — those are split apart before this "
            "check; this one has no positions section at all.) Reading it as a "
            "declared book would turn every fill into an open position.")
    missing = [c for c in REQUIRED_POSITION_COLUMNS if c not in header]
    if missing:
        raise FlexParseError(
            f"Flex export {_label(source)} is missing column(s): {', '.join(missing)}. "
            "The OpenPositions query must include them.")
    rows = list(reader)
    return rows, {}, _net_liquidation_from_csv(text)


def _position_label(row: dict) -> str:
    """How an OpenPositions row is named in an error. Trades rows use their
    TradeID instead (`_trade_label`) — a position row carries no TradeID at
    all, only a Conid."""
    return f"Conid={str(row.get('Conid') or '').strip()}"


def _level_of_detail(row: dict) -> str:
    return str(row.get("LevelOfDetail") or "").strip().upper()


def _select_level(rows: list[dict], source) -> list[dict]:
    """Resolve the LevelOfDetail correctness trap before any row is summed.

    An OpenPositions query can be saved at SUMMARY level, LOT level, or BOTH
    at once. Summing every row when both are present double-counts the
    position — a LOT row and the SUMMARY row for the same conid describe the
    SAME contracts at two granularities, not two different holdings. The rule:

      * If any row is explicitly SUMMARY, keep ONLY the SUMMARY rows and drop
        every LOT row outright — SUMMARY already IS the netted total per
        conid, so re-summing it against the LOT detail would double it.
      * Otherwise every row present is a LOT and the caller sums them per
        conid.
      * If the LevelOfDetail column is absent from the export ENTIRELY, there
        is no way to tell a LOT-level export from a SUMMARY-level one that
        happens to have exactly one row per conid — so every row is TREATED
        as summary-level (kept as one row per conid) rather than summed, but
        that assumption is checked: more than one row for the same conid with
        no LevelOfDetail column is exactly the silent-double-count failure
        this function exists to prevent, so it raises naming the conid rather
        than guessing which row is real.
    """
    has_level_column = any("LevelOfDetail" in r for r in rows)
    if not has_level_column:
        seen: set[str] = set()
        for r in rows:
            conid = str(r.get("Conid") or "").strip()
            if conid in seen:
                raise FlexParseError(
                    f"conid {conid} appears more than once in {_label(source)}'s "
                    "OpenPositions rows with no LevelOfDetail column — cannot "
                    "tell whether these are duplicate SUMMARY rows or "
                    "unlabelled LOT rows, and summing them would risk silently "
                    "double-counting the position.")
            seen.add(conid)
        return rows

    summary_rows = [r for r in rows if _level_of_detail(r) == "SUMMARY"]
    return summary_rows if summary_rows else rows


def parse_positions(source) -> dict:
    """Parse one Flex OpenPositions statement, in EITHER wire format, into the
    rawpull `Position`/`Contract` shapes.

    This is the DECLARED book — a statement of fact from the broker, as
    opposed to the book `_net_positions` reconstructs by netting fills. See
    `parse()`'s `positions_source` parameter for how the two are reconciled.

    Returns:
        {
          "positions": [Position, ...],   # rawpull shape, signed contracts
          "contracts": {"<conid>": Contract, ...},
          "net_liquidation": float | None,   # from a NAV section, if present
          "skipped_non_option": [ticker, ...],
          "report_date": "YYYY-MM-DD" | None,
          "meta": {...},                  # the declared XML window, if any
        }
    """
    rows, meta, net_liq = _read_position_rows(source)

    option_rows = [r for r in rows if _is_option(r)]
    skipped = sorted({
        str(r.get("UnderlyingSymbol") or r.get("Symbol") or "").strip().upper()
        for r in rows if not _is_option(r)
    })

    selected = _select_level(option_rows, source)

    by_conid: dict[str, list[dict]] = defaultdict(list)
    for r in selected:
        conid = str(int(_num(r.get("Conid"), "Conid", _position_label(r))))
        by_conid[conid].append(r)

    positions = []
    contracts: dict[str, dict] = {}
    for conid, conid_rows in sorted(by_conid.items(), key=lambda kv: int(kv[0])):
        rep = conid_rows[0]
        label = _position_label(rep)
        net = sum(_num(r.get("Quantity"), "Quantity", _position_label(r))
                  for r in conid_rows)
        if abs(net) < 1e-9:
            continue
        positions.append({
            "conid": int(conid),
            "position": net,
            "avg_cost": _opt_num(rep.get("CostBasisPrice")),
            "mkt_price": _opt_num(rep.get("MarkPrice")),
            "unrealized_pnl": _opt_num(rep.get("FifoPnlUnrealized")),
        })
        contracts[conid] = {
            "symbol": str(rep.get("UnderlyingSymbol") or "").strip().upper(),
            "sec_type": str(rep.get("AssetClass") or "OPT").strip().upper(),
            "strike": _num(rep.get("Strike"), "Strike", label),
            "expiry": _expiry(rep.get("Expiry"), label),
            "right": _right(rep.get("Put/Call"), label),
            "multiplier": _opt_num(rep.get("Multiplier")) or 100.0,
        }

    report_dates = sorted(
        d for d in (_row_date(r.get("ReportDate")) for r in option_rows) if d)
    report_date = report_dates[-1].isoformat() if report_dates else None

    return {
        "positions": positions,
        "contracts": contracts,
        "net_liquidation": net_liq,
        "skipped_non_option": skipped,
        "report_date": report_date,
        "meta": meta,
    }


def _window_warning(meta: dict, source) -> str | None:
    """Warn when a statement's window is too short to net an open book from.

    This is a DIFFERENT failure from the ones `_provenance_warnings` catches.
    Those inspect positions that appear in the rows; this one is about
    positions that appear NOWHERE — a contract opened last month and untouched
    since leaves no row in a one-day statement, so netting reports the book as
    smaller than it is with nothing anomalous to point at. Only the declared
    window reveals it.
    """
    period = str(meta.get("period") or "").strip()
    from_date, to_date = meta.get("fromDate"), meta.get("toDate")
    single_day = bool(from_date) and from_date == to_date
    if period not in SHORT_PERIODS and not single_day:
        return None
    return (
        f"Statement {_label(source)} covers only {from_date}..{to_date} (period "
        f"{period or 'unspecified'}). The open book is netted from fills, so "
        "positions opened before that window are MISSING ENTIRELY, not merely "
        "understated — the exposure totals below are not the whole book. Widen "
        "the Flex query's period, or pass the on-disk yearly exports with "
        "--from-flex alongside it.")


def _row_date(value) -> date | None:
    """Calendar date of one row's `DateTime` cell, or `None` if unparseable.

    Deliberately tolerant, unlike `_trade_time`: this runs over EVERY row read
    from a source, including ones later dropped by `_is_option`, purely to
    prove which days a source touched. A row it can't parse just contributes
    no coverage evidence rather than aborting the whole pull.
    """
    s = str(value or "").strip()
    for fmt in ("%Y-%m-%d;%H%M%S", "%Y%m%d;%H%M%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _source_coverage(meta: dict, rows: list[dict]) -> tuple[date, date] | None:
    """The calendar span one Flex source covers, for coverage-gap detection.

    Prefers the declared XML window (`fromDate`/`toDate` on `<FlexStatement>`)
    when present — it is authoritative, and correctly asserts coverage of the
    WHOLE range even across days with no fills. Falls back to the observed
    min/max fill date across every row read from the source when no window is
    declared (every delimited-text export has none), taken from rows BEFORE
    the `_is_option` filter — a stock or forex fill still proves that day was
    covered.

    The fallback is only a LOWER BOUND on true coverage: a source could
    genuinely span a wider range than its earliest/latest fill with no way to
    prove it here. That biases towards a FALSE-POSITIVE gap warning at the
    edge of an otherwise-contiguous pair of files, which is the correct
    direction to be wrong in — the alternative is silently missing a real one.
    """
    from_date, to_date = meta.get("fromDate"), meta.get("toDate")
    if from_date and to_date:
        return date.fromisoformat(from_date), date.fromisoformat(to_date)
    dates = sorted(d for d in (_row_date(r.get("DateTime")) for r in rows) if d)
    if not dates:
        return None
    return dates[0], dates[-1]


def _is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def _gap_between(end: date, next_start: date) -> list[date]:
    """Calendar dates strictly between two coverage intervals."""
    days = []
    cur = end + timedelta(days=1)
    while cur < next_start:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _merge_coverage(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Merge overlapping/adjacent per-source coverage intervals.

    Two intervals are adjacent — no gap between them — when the second starts
    the calendar day after the first ends, or when only weekend days separate
    them (a Friday close stepping to a Monday open is not a coverage gap).
    Deliberately no market-holiday calendar: a spurious one-day gap over a
    holiday is an acceptable false positive, the same bias `_source_coverage`
    states for its own fallback.
    """
    ordered = sorted(intervals)
    merged: list[tuple[date, date]] = []
    for start, end in ordered:
        if merged:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
                continue
            gap = _gap_between(prev_end, start)
            if not gap or all(_is_weekend(d) for d in gap):
                merged[-1] = (prev_start, max(prev_end, end))
                continue
        merged.append((start, end))
    return merged


def _is_option(row: dict) -> bool:
    return str(row.get("AssetClass") or "").strip().upper() in OPTION_ASSET_CLASSES


# --------------------------------------------------------------------------
# Field coercion
# --------------------------------------------------------------------------
def _num(value, field: str, row_label: str) -> float:
    """Parse a required numeric cell, or say exactly which row was unusable.

    Deliberately not tolerant. A blank strike or quantity silently coerced to
    zero would write a real-looking journal row describing a contract that does
    not exist.

    `row_label` is the whole identifying phrase, not a bare id, because this
    runs over two different row types: a trade row is identified by its
    TradeID, an OpenPositions row only by its Conid.
    """
    text = str(value or "").strip().replace(",", "")
    if not text:
        raise FlexParseError(f"row {row_label} has an empty {field}")
    try:
        return float(text)
    except ValueError as exc:
        raise FlexParseError(
            f"row {row_label} has an unparseable {field}: {value!r}") from exc


def _opt_num(value):
    """Parse an optional numeric cell; blank/unparseable becomes None, not 0."""
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _side(value, row_label: str) -> str:
    """Normalise Buy/Sell. The sign of every leg derives from this, so an
    unrecognised value raises rather than defaulting — quietly calling an
    unknown side a SELL would invert a position in the permanent record."""
    s = str(value or "").strip().upper()
    if s.startswith("B"):
        return "BUY"
    if s.startswith("S"):
        return "SELL"
    raise FlexParseError(
        f"row {row_label} has an unrecognised Buy/Sell {value!r} — "
        "refusing to guess direction")


def _right(value, row_label: str) -> str:
    r = str(value or "").strip().upper()[:1]
    if r not in ("C", "P"):
        raise FlexParseError(
            f"row {row_label} has an unrecognised Put/Call {value!r}")
    return r


def _open_close(value) -> str:
    """First character of Open/CloseIndicator.

    IBKR writes `C;O` when one execution closes a position and opens the
    opposite side. The leading character is the part that classifies the
    group, and `reconcile` detects the both-directions case from the legs
    themselves, so taking the first character loses nothing it relies on.
    """
    s = str(value or "").strip().upper()
    return s[:1] if s[:1] in ("O", "C") else "?"


def _expiry(value, row_label: str) -> str:
    """Flex writes Expiry as YYYY-MM-DD (ISO) or YYYYMMDD depending on query format."""
    s = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise FlexParseError(f"row {row_label} has an unparseable Expiry {value!r}")


def _trade_time(value, row_label: str) -> str:
    """`YYYY-MM-DD;HHMMSS` → naive ISO-8601. See the module docstring on tz."""
    s = str(value or "").strip()
    for fmt in ("%Y-%m-%d;%H%M%S", "%Y%m%d;%H%M%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue
    # A date with no time is still usable — it keeps the row in the right
    # session, and grouping falls back to equality on whatever string is here.
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue
    raise FlexParseError(f"row {row_label} has an unparseable DateTime {value!r}")


# --------------------------------------------------------------------------
# Shaping
# --------------------------------------------------------------------------
def _trade_label(row: dict) -> str:
    """How a TRADES row is named in an error. Positions rows use their Conid
    instead (`_position_label`) — they carry no TradeID at all."""
    return f"TradeID={str(row.get('TradeID') or '').strip()}"


def _fill(row: dict) -> dict:
    """One Flex execution → the rawpull Fill shape.

    `commission` is None, not 0.0: a trades-only Flex query carries no
    commission column at all, and a zero would understate the cost of every
    trade in the permanent record. `net_amount` is likewise absent.
    """
    trade_id = str(row.get("TradeID") or "").strip()
    if not trade_id:
        raise FlexParseError(
            "a row has no TradeID — the journal dedupes on it, so a pull "
            "without one would re-append the same fill on every run")
    label = _trade_label(row)
    return {
        "exec_id": trade_id,
        "conid": int(_num(row.get("Conid"), "Conid", label)),
        "symbol": str(row.get("UnderlyingSymbol") or "").strip().upper(),
        "side": _side(row.get("Buy/Sell"), label),
        "size": abs(_num(row.get("Quantity"), "Quantity", label)),
        "price": _num(row.get("TradePrice"), "TradePrice", label),
        "commission": None,
        "net_amount": _opt_num(row.get("CostBasis")),
        "realized_pnl": _opt_num(row.get("FifoPnlRealized")),
        "trade_time": _trade_time(row.get("DateTime"), label),
        "order_id": None,   # absent from Flex; reconcile groups on trade_time
        "open_close": _open_close(row.get("Open/CloseIndicator")),
    }


def _contract(row: dict) -> dict:
    label = _trade_label(row)
    return {
        "symbol": str(row.get("UnderlyingSymbol") or "").strip().upper(),
        "sec_type": str(row.get("AssetClass") or "OPT").strip().upper(),
        "strike": _num(row.get("Strike"), "Strike", label),
        "expiry": _expiry(row.get("Expiry"), label),
        "right": _right(row.get("Put/Call"), label),
        "multiplier": _opt_num(row.get("Multiplier")) or 100.0,
    }


def _signed_qty(row: dict) -> float:
    """Signed contracts for this execution.

    Flex already signs `Quantity` (negative on a sell), but the sign is
    re-derived from Buy/Sell rather than trusted, so a query configured to
    export absolute quantities cannot silently invert the netted book.
    """
    label = _trade_label(row)
    size = abs(_num(row.get("Quantity"), "Quantity", label))
    return size if _side(row.get("Buy/Sell"), label) == "BUY" else -size


def _net_positions(rows: list[dict]) -> tuple[list[dict], dict[int, list[dict]]]:
    """Net signed quantity per conid → the open book.

    Returns the non-zero positions plus the per-conid row lists, which
    `_provenance_warnings` needs to judge whether a position's history is
    fully contained in the files given.
    """
    by_conid: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_conid[int(_num(row.get("Conid"), "Conid", _trade_label(row)))].append(row)

    positions = []
    for conid, conid_rows in sorted(by_conid.items()):
        net = sum(_signed_qty(r) for r in conid_rows)
        if abs(net) < 1e-9:
            continue
        positions.append({
            "conid": conid,
            "position": net,
            # A Flex trades query carries no mark, and the journal must not
            # invent one. Average cost IS derivable from the fills, but only
            # for a position whose whole life is in the window, so it is left
            # to the enrichment step rather than half-computed here.
            "avg_cost": None,
            "mkt_price": None,
            "unrealized_pnl": None,
        })
    return positions, by_conid


def _position_last_fill(rows: list[dict]) -> date | None:
    """Latest fill date among one position's rows.

    Feeds `_coverage_gap_warnings`: a position last touched before a gap
    starts is exactly the one that could have been closed inside it and would
    still net non-zero, since its closing fill (if any) is nowhere any
    source read.
    """
    dates = [d for d in (_row_date(r.get("DateTime")) for r in rows) if d]
    return max(dates) if dates else None


def _position_entry_date(rows: list[dict], held_qty: float) -> date | None:
    """Date of the fill that OPENED the currently-held position, or None.

    Walks the conid's fills in time order accumulating signed quantity and
    returns the date the running position last left zero (or flipped sign) into
    the held direction without returning to zero afterward.

    None whenever the walk cannot be the position's true history: no rows, a
    flat holding, or a final running quantity that disagrees with `held_qty` —
    the latter means the position's life started before the export window
    (exactly the condition `_provenance_warnings` flags), and a date read off a
    partial history would be a guess, not a record. On the netted book the
    equality holds by construction; on a declared book it is the test.
    """
    if not rows or abs(held_qty) < 1e-9:
        return None
    running = 0.0
    entry: date | None = None
    for r in sorted(rows, key=lambda r: str(r.get("DateTime") or "")):
        prev = running
        running += _signed_qty(r)
        if abs(running) < 1e-9:
            entry = None
        elif prev * running <= 0:  # left zero, or flipped sign without touching it
            entry = _row_date(r.get("DateTime"))
    if entry is None or abs(running - held_qty) > 1e-9:
        return None
    return entry


def _coverage_gap_warnings(coverage: list[tuple[date, date]], positions: list[dict],
                           by_conid: dict[int, list[dict]],
                           contracts: dict[str, dict]) -> list[str]:
    """Warn about calendar spans that NO source covers at all.

    A third, distinct failure from `_window_warning` (one statement's window
    is too short) and `_provenance_warnings` (a position IN THE ROWS starts
    with a close, or has expired): here the problem is a stretch of days no
    source touches AT ALL. A position closed inside that stretch leaves no
    closing fill anywhere, so netting reports it open with nothing anomalous
    to point at — the AMD/META/MU failure this function exists to catch.

    Only reported when it would affect the presented book: a gap with no open
    position last-touched before it starts names nobody, and a warning naming
    nobody is noise, so it is skipped.
    """
    merged = _merge_coverage(coverage)
    if len(merged) < 2:
        return []

    last_fill = {pos["conid"]: _position_last_fill(by_conid.get(pos["conid"], []))
                 for pos in positions}

    def _ticker(conid) -> str:
        return contracts.get(str(conid), {}).get("symbol") or str(conid)

    # Counted in TICKERS, not legs. `positions` is one entry per conid, so a
    # vertical is two of them while the report collapses it to one row — a
    # warning saying "9 of 17" beside a report saying "10 open positions" reads
    # as a third, contradictory number. Tickers are the unit both agree on.
    book_tickers = {_ticker(pos["conid"]) for pos in positions}

    warnings = []
    for (_prev_start, prev_end), (next_start, _next_end) in zip(merged, merged[1:]):
        gap_start = prev_end + timedelta(days=1)
        gap_end = next_start - timedelta(days=1)
        days = (gap_end - gap_start).days + 1
        at_risk = sorted({
            _ticker(conid) for conid, last in last_fill.items()
            if last is not None and last < gap_start
        })
        if not at_risk:
            continue
        warnings.append(
            f"No source covers {gap_start.isoformat()} to {gap_end.isoformat()} "
            f"({days} calendar day{'s' if days != 1 else ''}). The open book is "
            "netted from fills, so a position CLOSED inside that span leaves no "
            "closing fill anywhere and still nets non-zero — "
            f"{len(at_risk)} of {len(book_tickers)} ticker(s) in the open book "
            f"are affected: {', '.join(at_risk)}. Export a fresh Flex trades "
            "statement covering this span into portfolio/input/."
        )
    return warnings


def _provenance_warnings(positions: list[dict], by_conid: dict[int, list[dict]],
                         contracts: dict[str, dict], as_of: date) -> list[str]:
    """Name every reconstructed position that the files cannot fully account for.

    Two distinct problems, both of which make a netted book quietly wrong:

      * The rows for a conid begin with a CLOSE. Its opening trade happened
        before the earliest file given, so the net is short by that amount.
      * The position is already expired as of the session being journalled.
        Netting has no concept of expiry, so an option that expired worthless
        still shows a non-zero net forever.

    These are reported, never silently corrected — the fix is to pass more
    years of export, and the operator has to know that is what is needed.
    """
    warnings = []
    for pos in positions:
        conid = pos["conid"]
        rows = sorted(by_conid[conid], key=lambda r: str(r.get("DateTime")))
        detail = contracts.get(str(conid), {})
        label = (f"{detail.get('symbol', '?')} {detail.get('strike', '?')}"
                 f"{detail.get('right', '?')} {detail.get('expiry', '?')}")

        if rows and _open_close(rows[0].get("Open/CloseIndicator")) == "C":
            warnings.append(
                f"{label} (conid {conid}) opens with a CLOSE — its entry predates the "
                f"oldest export supplied, so its net size of {pos['position']:+g} is "
                "understated. Include the earlier year's export.")

        expiry = detail.get("expiry")
        if expiry and date.fromisoformat(expiry) < as_of:
            warnings.append(
                f"{label} (conid {conid}) expired on {expiry}, before the {as_of} "
                f"session, but nets to {pos['position']:+g}. Netting cannot see "
                "expiry or assignment; treat it as closed.")
    return warnings


def _drop_expired(positions: list[dict], contracts: dict[str, dict],
                  as_of: date) -> list[dict]:
    """Remove positions whose contract already expired before `as_of`.

    Kept separate from the warning above on purpose: the operator is told the
    netting could not see the expiry, AND the position is excluded, so an
    expired contract can never contribute phantom delta to the exposure total.
    """
    live = []
    for pos in positions:
        expiry = contracts.get(str(pos["conid"]), {}).get("expiry")
        if expiry and date.fromisoformat(expiry) < as_of:
            continue
        live.append(pos)
    return live


def _refuse_a_contradicted_flat_book(declared: list[dict], netted: list[dict],
                                     contracts: dict[str, dict], as_of: date,
                                     source) -> None:
    """Refuse a declared book of NOTHING that the fills flatly contradict.

    This is the failure that produced a journal reading "No open positions" and
    "Book is complete" on 2026-08-15 while eighteen live contracts were open:
    the OpenPositions statement came back with zero rows, and a declared book is
    authoritative, so nothing downstream had any way to doubt it. Every other
    disagreement between the two books is a per-conid `book_warnings` entry and
    stays one — a warning is the right weight when the book is mostly right. An
    EMPTY declared book against a non-empty netted one is different in kind:
    there is no book left to warn about, and a flat one is exactly what a
    reader would not question.

    Expired contracts are dropped from the netted side first: after an expiry
    the fills genuinely do keep netting non-zero while the broker's book is
    genuinely flat, and that is not a contradiction.
    """
    live_netted = _drop_expired(netted, contracts, as_of)
    if declared or not live_netted:
        return
    tickers = sorted({contracts.get(str(p["conid"]), {}).get("symbol", "?")
                      for p in live_netted})
    raise FlexParseError(
        f"The declared OpenPositions book from {_label(source)} is EMPTY, but "
        f"netting the trades export gives {len(live_netted)} live position(s) "
        f"({', '.join(tickers)}). Refusing to journal a flat book on that "
        "evidence. Either the statement was generated before IBKR had finished "
        "assembling the day's positions (re-run later in the session), or "
        f"{POSITIONS_QUERY_ID_ENV} points at a query that no longer reports "
        "them. Run with --offline to journal from the netted book meanwhile, "
        "or pass a hand-downloaded statement with --from-flex-positions.")


def _empty_book_diagnostics() -> dict[str, list[str]]:
    """The three buckets `_book_diff_warnings` sorts disagreements into, empty.

    Always the same three keys, on every path — a consumer counting them must
    never have to tell "this pull ran no cross-check" apart from "this key is
    missing" by probing for the key.
    """
    return {"not_cross_checkable": [], "coverage_explained": [], "unexplained": []}


def _uncovered_time_after(merged: list[tuple[date, date]], last_fill: date | None,
                          as_of: date) -> bool:
    """Is there calendar time NO source covers, after this position's last fill?

    Two shapes count. An INTERNAL hole between two merged coverage intervals
    that opens after the last fill — the position could have been closed inside
    it, leaving no closing fill anywhere to net against. And a TRAILING hole:
    coverage stops before the session being journalled, so the same is true of
    everything after it.

    Returns False when the position has no datable fill at all — refusing to
    excuse a disagreement on evidence that does not exist is the conservative
    direction, and lands the conid in the unexplained bucket instead.
    """
    if not merged or last_fill is None:
        return False
    for (_prev_start, prev_end), (_next_start, _next_end) in zip(merged, merged[1:]):
        if prev_end + timedelta(days=1) > last_fill:
            return True
    return merged[-1][1] < as_of


def _book_diff_warnings(declared: list[dict], netted: list[dict],
                        contracts: dict[str, dict],
                        by_conid: dict[int, list[dict]],
                        coverage: list[tuple[date, date]],
                        as_of: date) -> tuple[list[str], dict[str, list[str]]]:
    """Reconcile a DECLARED OpenPositions book against the one netted from fills.

    This diff is the entire reason `parse()` still computes the netted book
    when a positions section is supplied: any conid where the two disagree —
    present in one only, or a different net size — means either a fill is
    missing from the trades export, or a corporate action moved the position
    outside of ordinary trading (a split, an assignment).

    But most disagreements are NOT evidence of either. A saved trades query's
    period ("Last Business Day", "Month to Date") is routinely far shorter than
    a position's life, so every contract opened before that window disagrees
    with the declared book by construction. Listing those beside the real
    findings is how a SOURCE LIMITS block reaches 28 lines of expected noise and
    stops being read at all. So each disagreeing conid is CLASSIFIED, and only
    the third bucket is returned as a finding:

      * `not_cross_checkable` — declared present, netted absent, and the trades
        export holds NO ROW AT ALL for this conid. There is nothing to
        contradict; the export simply never saw the contract. Note the test is
        `conid not in by_conid`, NOT "netting gives absent" — a conid that HAS
        rows which net to exactly zero means the export saw both an open and a
        close while the broker still shows the position open. That is a real
        contradiction and stays unexplained.
      * `coverage_explained` — netted present, declared absent, with uncovered
        calendar time after the position's last fill. A close inside that hole
        leaves no closing fill for netting to find, so the netted side is the
        one that is wrong, and the fix is a fresh export rather than an
        investigation.
      * `unexplained` — everything else, in the original wording. A SIZE
        mismatch where both books carry the conid is here unconditionally: no
        window story explains two different non-zero counts for a contract the
        export demonstrably saw.

    The cross-check is DEMOTED by this, never removed. Every bucket is returned
    for the report to count, and the unexplained ones are the return value.
    """
    declared_by_conid = {p["conid"]: p["position"] for p in declared}
    netted_by_conid = {p["conid"]: p["position"] for p in netted}
    conids = sorted(set(declared_by_conid) | set(netted_by_conid))
    merged = _merge_coverage(coverage) if coverage else []

    diagnostics = _empty_book_diagnostics()
    for conid in conids:
        d = declared_by_conid.get(conid)
        n = netted_by_conid.get(conid)
        if d is not None and n is not None and abs(d - n) < 1e-9:
            continue
        detail = contracts.get(str(conid), {})
        label = (f"{detail.get('symbol', '?')} {detail.get('strike', '?')}"
                 f"{detail.get('right', '?')} {detail.get('expiry', '?')}")
        d_text = f"{d:+g}" if d is not None else "absent"
        n_text = f"{n:+g}" if n is not None else "absent"

        if d is not None and n is None and conid not in by_conid:
            diagnostics["not_cross_checkable"].append(
                f"{label} (conid {conid}): declared {d_text}; the trades export "
                "carries no fill for this contract at all, so it cannot be "
                "cross-checked — the export's window is shorter than the "
                "position's life.")
            continue

        if d is None and n is not None and _uncovered_time_after(
                merged, _position_last_fill(by_conid.get(conid, [])), as_of):
            diagnostics["coverage_explained"].append(
                f"{label} (conid {conid}): netting the trades export gives "
                f"{n_text} while the declared book does not carry it, and no "
                "source covers the calendar time after its last fill — a close "
                "inside that span leaves no closing fill to net.")
            continue

        diagnostics["unexplained"].append(
            f"{label} (conid {conid}): the declared OpenPositions book shows "
            f"{d_text}, but netting the trades export gives {n_text}. Either a "
            "fill is missing from the trades export, or a corporate action "
            "moved the position outside ordinary trading.")
    return diagnostics["unexplained"], diagnostics


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def parse(sources, *, trade_date: str | None = None,
          net_liquidation: float | None = None,
          account_id: str | None = None,
          positions_source=None) -> dict:
    """Build a validated raw-pull dict from one or more Flex trade exports.

    `sources` is a path, CSV text in a StringIO, or a list of either. Pass EVERY
    year of export you still hold positions from: fills are filtered to
    `trade_date`, but the open book is netted across everything given, so a
    partial history yields a partial book (and says so — see
    `_provenance_warnings`).

    `trade_date` defaults to the most recent session present in the files.
    `net_liquidation` has no home in a trades-only Flex query; pass it (or set
    JOURNAL_NET_LIQUIDATION) to make the exposure caps evaluable. Left None,
    the risk section degrades to "not evaluable" rather than dividing by a guess.

    `positions_source` is a SINGLE OpenPositions statement (path, StringIO, or
    None) — a declared, not reconstructed, book. When given, it REPLACES the
    netted book as `positions`/`book_reconstructed=False`, but the netted book
    is still computed and diffed against it. This is the whole value of having
    both: the declared book is a statement of fact, the netted one is a
    cross-check on whether the trades export actually explains it.

    Every disagreement is CLASSIFIED rather than warned about — see
    `_book_diff_warnings`. All three buckets land on the pull as
    `book_diagnostics` (an additive top-level key; `rawpull.validate()` checks
    only that the REQUIRED keys are present and rejects no extra ones, so this
    is not a schema-version change and every consumer reads it with `.get()`).
    A disagreement the export's own window explains is a count in there and
    nothing more; only the `unexplained` bucket is a finding, and the report
    renders it. `book_warnings` on this path therefore carries the statement-
    window notes alone — it is NOT the place every disagreement surfaces.
    """
    if isinstance(sources, (str, Path, io.StringIO)):
        sources = [sources]
    sources = list(sources)
    if not sources:
        raise FlexParseError("no Flex export supplied")

    rows: list[dict] = []
    window_warnings: list[str] = []
    coverage: list[tuple[date, date]] = []
    for src in sources:
        read, meta = _read_rows(src)
        found = [r for r in read if _is_option(r)]
        log.info("Read %d option row(s) from %s", len(found), _label(src))
        rows.extend(found)
        warning = _window_warning(meta, src)
        if warning:
            window_warnings.append((str(meta.get("fromDate") or ""), warning))
        span = _source_coverage(meta, read)
        if span:
            coverage.append(span)
    if not rows:
        raise FlexParseError(
            f"no option rows in {len(sources)} export(s) — check AssetClass is exported")

    # De-duplicate on TradeID so overlapping year files cannot double-count a
    # fill into the netted book. Later files win, which is harmless: the rows
    # are identical when the ids match.
    deduped = {str(r.get("TradeID") or "").strip(): r for r in rows}
    if len(deduped) != len(rows):
        log.info("Dropped %d duplicate TradeID row(s) across the exports",
                 len(rows) - len(deduped))
    rows = list(deduped.values())

    fills_all = [_fill(r) for r in rows]
    trade_contracts = {str(f["conid"]): _contract(r) for f, r in zip(fills_all, rows)}

    sessions = sorted({f["trade_time"][:10] for f in fills_all})
    trade_date = trade_date or sessions[-1]
    as_of = date.fromisoformat(trade_date)

    todays = [f for f in fills_all if f["trade_time"][:10] == trade_date]
    if not todays:
        # Not an error. A day with no fills is a real and common outcome, and
        # unlike the Client Portal path there is no session that could have
        # silently expired to fake one.
        log.info("No fills on %s (export spans %s to %s, %d fill(s))",
                 trade_date, sessions[0], sessions[-1], len(fills_all))

    # A short statement window only matters if nothing ELSE supplied the earlier
    # history. When another export in `sources` carries fills predating the short
    # window, the netted book is fed from that instead and the warning would be
    # a false alarm — so it is judged against the fills actually read, not the
    # declared window alone.
    window_notes = [note for from_date, note in window_warnings
                    if not (from_date and sessions[0] < from_date)]

    netted_positions, by_conid = _net_positions(rows)

    if positions_source is not None:
        # The declared path: the OpenPositions section is the book, the netted
        # one becomes a cross-check rather than the answer. The three
        # reconstruction-only warnings below (`_provenance_warnings`,
        # `_coverage_gap_warnings`, `_drop_expired`) exist ONLY to caveat a
        # book built by netting fills, so they do not apply here — the
        # reconciliation diff replaces them, and the report never gets
        # quieter without getting more certain about the same thing.
        declared = parse_positions(positions_source)
        positions = declared["positions"]
        contracts = {**trade_contracts, **declared["contracts"]}
        _refuse_a_contradicted_flat_book(positions, netted_positions, contracts,
                                         as_of, positions_source)
        book_reconstructed = False
        # Diffed against the LIVE netted book for the same reason the guard
        # above is: an option that expired worthless has no closing fill, so
        # netting reports it open forever. Left in, every past expiry would
        # accumulate as a standing warning that nothing can ever clear.
        unexplained, book_diagnostics = _book_diff_warnings(
            positions, _drop_expired(netted_positions, contracts, as_of), contracts,
            by_conid, coverage, as_of)
        # The cross-check is DEMOTED, not removed: its findings no longer crowd
        # the SOURCE LIMITS block, but a genuinely missing fill is still logged
        # at WARNING here and still reaches the report through
        # `book_diagnostics`. Only the classified-as-expected buckets go quiet.
        for note in unexplained:
            log.warning("%s", note)
        warnings = window_notes
        # The declared section is the first thing on this transport that can
        # SEE a non-option holding — netting only ever ran over option fills,
        # so the trades path had nothing to report here. Carry the names
        # through: "you hold none" and "this pipeline does not model them"
        # are different statements, and only one of them is true.
        skipped_non_option = declared["skipped_non_option"]
        if net_liquidation is None:
            net_liquidation = declared.get("net_liquidation")
    else:
        contracts = trade_contracts
        skipped_non_option = []
        # No declared book to diff against, so the cross-check never ran. The
        # keys are still present and empty rather than absent — see
        # `_empty_book_diagnostics`.
        book_diagnostics = _empty_book_diagnostics()
        provenance_notes = _provenance_warnings(netted_positions, by_conid, contracts, as_of)
        positions = _drop_expired(netted_positions, contracts, as_of)
        # Gap risk is judged against the FINAL open book (expired contracts
        # already dropped) — an expired contract is already flagged and
        # excluded above, so naming it again here as "at risk" from a
        # coverage hole would be noise.
        gap_notes = _coverage_gap_warnings(coverage, positions, by_conid, contracts)
        warnings = window_notes + gap_notes + provenance_notes
        book_reconstructed = True

    # Entry date per open position, derived from the fills the exports hold.
    # Additive OPTIONAL field on the v1 Position shape (no SCHEMA_VERSION bump:
    # readers use .get("entry_date"), absence means unknown, and a bump would
    # make every existing pull in journal/raw/ unreplayable). None — rendered as
    # an em dash — whenever the fills cannot prove the entry, never a guess.
    for pos in positions:
        entry = _position_entry_date(by_conid.get(int(pos["conid"]), []),
                                     float(pos.get("position") or 0))
        pos["entry_date"] = entry.isoformat() if entry else None

    for warning in warnings:
        log.warning("%s", warning)

    if net_liquidation is None:
        env = os.getenv("JOURNAL_NET_LIQUIDATION")
        net_liquidation = float(env) if env else None
    if net_liquidation is None:
        log.warning("No NetLiquidation — a Flex trades query carries none. Set "
                    "JOURNAL_NET_LIQUIDATION or pass --net-liq to evaluate the "
                    "exposure caps; delta-notional itself is unaffected.")

    raw = {
        "schema_version": rawpull.SCHEMA_VERSION,
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(),
        "trade_date": trade_date,
        "source": SOURCE,
        "account_id": account_id or os.getenv("IBKR_ACCOUNT_ID"),
        "net_liquidation": net_liquidation,
        "trades": todays,
        "positions": positions,
        "contracts": contracts,
        # Flex has no greeks at all. Every open contract starts explicitly
        # unavailable so that a pull used without the Barchart enrichment step
        # reports a FLOOR, and never mistakes an absent delta for a flat one.
        "greeks": {str(p["conid"]): {"delta": None, "gamma": None, "theta": None,
                                     "vega": None, "iv": None,
                                     "source": DELTA_SOURCE_UNAVAILABLE}
                   for p in positions},
        "underlying_prices": {},
        "skipped_non_option": skipped_non_option,
        # Provenance the report prints so a reader is never left inferring what
        # this pull could and could not see.
        "trade_time_tz": TRADE_TIME_TZ,
        "commissions_included": False,
        "book_reconstructed": book_reconstructed,
        "book_warnings": warnings,
        # The declared-vs-netted cross-check, classified. Three lists of
        # message strings: `not_cross_checkable` and `coverage_explained` are
        # disagreements the trades export's own window accounts for (a count,
        # not a finding), `unexplained` is what actually needs looking at.
        # Additive and optional — read it with `.get()`.
        "book_diagnostics": book_diagnostics,
        "flex_sources": [str(s) for s in sources if not isinstance(s, io.StringIO)],
        "flex_span": [sessions[0], sessions[-1]],
    }
    rawpull.validate(raw)
    # Say which book this is. "netted from N rows" on a declared pull would
    # describe work that did not happen, and the whole point of the declared
    # path is that the operator can tell the two apart at a glance.
    provenance = (f"netted from {len(rows)} row(s)" if book_reconstructed
                  else "declared by the OpenPositions query")
    log.info("Flex pull for %s: %d fill(s), %d open position(s) %s%s",
             trade_date, len(todays), len(positions), provenance,
             f", {len(warnings)} warning(s)" if warnings else "")
    return raw
