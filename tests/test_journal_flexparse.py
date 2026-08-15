"""Tests for the IBKR Flex export → rawpull parser.

The Flex path has no greeks and no open-positions section, so most of what can
go wrong here is a QUIET wrongness: a netted book that looks complete, a
commission silently zeroed, a strike coerced from a blank cell. These tests are
weighted towards those, not towards the happy path.
"""

import io

import pytest

from scripts.journal import flexparse
from scripts.journal.config import DELTA_SOURCE_UNAVAILABLE
from scripts.journal.flexparse import FlexParseError

HEADER = ("Description,UnderlyingSymbol,Open/CloseIndicator,Quantity,TradePrice,"
          "CostBasis,FifoPnlRealized,Strike,Expiry,DateTime,Put/Call,AssetClass,"
          "Symbol,TradeID,Conid,Buy/Sell")


def row(*, tid="1", conid="100", sym="NVDA", oc="O", qty="1", price="5.00",
        cost="500", pnl="0", strike="220", expiry="2026-09-18", right="C",
        dt="2026-08-14;103000", side="BUY", asset="OPT", desc="NVDA 220 C"):
    return (f"{desc},{sym},{oc},{qty},{price},{cost},{pnl},{strike},{expiry},"
            f"{dt},{right},{asset},{sym}  260918C00220000,{tid},{conid},{side}")


def csv_text(*rows):
    return io.StringIO("\n".join([HEADER, *rows]) + "\n")


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------
def test_a_single_fill_becomes_a_valid_pull():
    raw = flexparse.parse(csv_text(row()))
    assert raw["source"] == "ibkr-flex"
    assert raw["trade_date"] == "2026-08-14"
    assert len(raw["trades"]) == 1
    fill = raw["trades"][0]
    assert fill["exec_id"] == "1"
    assert fill["conid"] == 100
    assert fill["side"] == "BUY"
    assert fill["size"] == 1
    assert fill["price"] == 5.0
    assert fill["open_close"] == "O"


def test_contract_identity_comes_from_the_export_not_inference():
    raw = flexparse.parse(csv_text(row(strike="222.5", expiry="2026-09-18", right="P")))
    contract = raw["contracts"]["100"]
    assert contract["strike"] == 222.5
    assert contract["expiry"] == "2026-09-18"
    assert contract["right"] == "P"


def test_yyyymmdd_expiry_is_accepted():
    raw = flexparse.parse(csv_text(row(expiry="20260918")))
    assert raw["contracts"]["100"]["expiry"] == "2026-09-18"


def test_non_option_rows_are_excluded():
    raw = flexparse.parse(csv_text(row(), row(tid="2", conid="200", asset="STK")))
    assert [f["conid"] for f in raw["trades"]] == [100]


def test_an_export_with_no_option_rows_raises():
    with pytest.raises(FlexParseError, match="no option rows"):
        flexparse.parse(csv_text(row(asset="STK")))


def test_a_missing_column_is_fatal_rather_than_silently_wrong():
    text = io.StringIO("UnderlyingSymbol,Quantity\nNVDA,1\n")
    with pytest.raises(FlexParseError, match="missing column"):
        flexparse.parse(text)


# --------------------------------------------------------------------------
# The quiet-wrongness cases
# --------------------------------------------------------------------------
def test_commission_is_none_not_zero():
    """A trades-only Flex query has no commission column. Zero would understate
    the cost of every trade in a permanent record."""
    raw = flexparse.parse(csv_text(row()))
    assert raw["trades"][0]["commission"] is None
    assert raw["commissions_included"] is False


def test_greeks_start_explicitly_unavailable_never_zero():
    raw = flexparse.parse(csv_text(row()))
    greek = raw["greeks"]["100"]
    assert greek["delta"] is None
    assert greek["source"] == DELTA_SOURCE_UNAVAILABLE


def test_a_blank_strike_raises_rather_than_becoming_zero():
    with pytest.raises(FlexParseError, match="empty Strike"):
        flexparse.parse(csv_text(row(strike="")))


def test_an_unrecognised_side_refuses_to_guess_direction():
    with pytest.raises(FlexParseError, match="refusing to guess direction"):
        flexparse.parse(csv_text(row(side="X")))


def test_a_row_without_a_tradeid_raises_because_dedup_keys_on_it():
    with pytest.raises(FlexParseError, match="no TradeID"):
        flexparse.parse(csv_text(row(tid="")))


def test_timestamps_are_not_claimed_to_be_utc():
    raw = flexparse.parse(csv_text(row()))
    assert "Z" not in raw["trades"][0]["trade_time"]
    assert "+00:00" not in raw["trades"][0]["trade_time"]
    assert raw["trade_time_tz"]


# --------------------------------------------------------------------------
# Netting the open book
# --------------------------------------------------------------------------
def test_a_fully_closed_position_is_not_in_the_open_book():
    raw = flexparse.parse(csv_text(
        row(tid="1", oc="O", side="BUY"),
        row(tid="2", oc="C", side="SELL", dt="2026-08-14;150000")))
    assert raw["positions"] == []


def test_net_size_is_signed_from_side_not_from_the_quantity_column():
    """A query exporting absolute quantities must not invert the book."""
    raw = flexparse.parse(csv_text(
        row(tid="1", qty="2", side="BUY"),
        row(tid="2", qty="1", side="SELL", dt="2026-08-14;150000")))
    assert raw["positions"][0]["position"] == 1


def test_the_book_nets_across_every_file_given():
    opened = csv_text(row(tid="1", side="BUY", dt="2025-06-02;100000"))
    closed = csv_text(row(tid="2", side="SELL", oc="C", dt="2026-08-14;100000"))
    raw = flexparse.parse([opened, closed])
    assert raw["positions"] == []
    assert raw["flex_span"] == ["2025-06-02", "2026-08-14"]


def test_fills_are_filtered_to_the_session_but_the_book_is_not():
    raw = flexparse.parse(csv_text(
        row(tid="1", conid="100", side="BUY", dt="2026-08-13;100000"),
        row(tid="2", conid="200", side="BUY", dt="2026-08-14;100000", strike="230")),
        trade_date="2026-08-14")
    assert [f["exec_id"] for f in raw["trades"]] == ["2"]
    assert len(raw["positions"]) == 2


def test_a_duplicate_tradeid_across_files_is_counted_once():
    first = csv_text(row(tid="1", side="BUY"))
    second = csv_text(row(tid="1", side="BUY"))
    raw = flexparse.parse([first, second])
    assert raw["positions"][0]["position"] == 1


# --------------------------------------------------------------------------
# Provenance — the netted book saying what it could not see
# --------------------------------------------------------------------------
def test_a_position_opening_with_a_close_is_flagged_as_truncated_history():
    raw = flexparse.parse(csv_text(row(tid="1", oc="C", side="SELL")))
    assert any("predates the oldest export" in w for w in raw["book_warnings"])


def test_an_expired_contract_is_excluded_from_the_book_and_named():
    raw = flexparse.parse(csv_text(
        row(tid="1", expiry="2026-01-16", side="BUY", dt="2025-12-01;100000")),
        trade_date="2026-08-14")
    assert raw["positions"] == []
    assert any("expired on 2026-01-16" in w for w in raw["book_warnings"])


def test_the_pull_declares_that_its_book_was_reconstructed():
    raw = flexparse.parse(csv_text(row()))
    assert raw["book_reconstructed"] is True


# --------------------------------------------------------------------------
# Equity basis
# --------------------------------------------------------------------------
def test_net_liquidation_is_none_when_not_supplied():
    raw = flexparse.parse(csv_text(row()))
    assert raw["net_liquidation"] is None


def test_net_liquidation_can_be_passed_in():
    raw = flexparse.parse(csv_text(row()), net_liquidation=51234.5)
    assert raw["net_liquidation"] == 51234.5


def test_net_liquidation_falls_back_to_the_environment(monkeypatch):
    monkeypatch.setenv("JOURNAL_NET_LIQUIDATION", "40000")
    raw = flexparse.parse(csv_text(row()))
    assert raw["net_liquidation"] == 40000.0


def test_a_missing_file_names_the_path():
    with pytest.raises(FlexParseError, match="not found"):
        flexparse.parse("/nonexistent/flex.csv")


# --------------------------------------------------------------------------
# The XML wire format
# --------------------------------------------------------------------------
# A Flex query is saved as either delimited text or XML in Account Management,
# and the web service returns whichever that query specifies. Reading only one
# format is not a cosmetic gap: the parser rejected an XML statement for
# "missing" all 13 required columns, which reads as a broken query rather than
# a format mismatch and sends the operator to reconfigure a query that is fine.
def xml_text(*trades, from_date="2025-01-02", to_date="2026-08-13",
             period="LastYear"):
    body = "\n".join(trades)
    return io.StringIO(
        '<FlexQueryResponse queryName="trades" type="AF">\n'
        '<FlexStatements count="1">\n'
        f'<FlexStatement accountId="U1234567" fromDate="{from_date}" '
        f'toDate="{to_date}" period="{period}" whenGenerated="2026-08-14;125139">\n'
        f"<Trades>\n{body}\n</Trades>\n"
        "</FlexStatement>\n</FlexStatements>\n</FlexQueryResponse>\n")


def xml_trade(*, tid="1", conid="100", sym="NVDA", oc="O", qty="1", price="5.00",
              cost="500", pnl="0", strike="220", expiry="2026-09-18", right="C",
              dt="2026-08-14;103000", side="BUY", asset="OPT"):
    return (f'<Trade description="{sym} {strike} {right}" underlyingSymbol="{sym}" '
            f'openCloseIndicator="{oc}" quantity="{qty}" tradePrice="{price}" '
            f'cost="{cost}" fifoPnlRealized="{pnl}" strike="{strike}" '
            f'expiry="{expiry}" dateTime="{dt}" putCall="{right}" '
            f'assetCategory="{asset}" symbol="{sym}  260918C00220000" '
            f'tradeID="{tid}" conid="{conid}" buySell="{side}" />')


def test_an_xml_statement_parses_like_the_csv_one():
    raw = flexparse.parse(xml_text(xml_trade()))
    assert raw["source"] == "ibkr-flex"
    assert raw["trade_date"] == "2026-08-14"
    fill = raw["trades"][0]
    assert fill["exec_id"] == "1"
    assert fill["conid"] == 100
    assert fill["side"] == "BUY"
    assert fill["price"] == 5.0
    assert fill["open_close"] == "O"


def test_the_two_wire_formats_produce_the_same_pull():
    """The whole point of renaming attributes at the reader: nothing downstream
    should be able to tell which format the statement arrived in."""
    from_csv = flexparse.parse(csv_text(row()))
    from_xml = flexparse.parse(xml_text(xml_trade()))
    for key in ("trades", "positions", "contracts", "greeks"):
        assert from_csv[key] == from_xml[key], key


def test_xml_contract_identity_survives_the_rename():
    raw = flexparse.parse(xml_text(xml_trade(strike="222.5", right="P")))
    contract = raw["contracts"]["100"]
    assert contract["strike"] == 222.5
    assert contract["right"] == "P"
    assert contract["sec_type"] == "OPT"   # assetCategory, not AssetClass


def test_xml_commission_is_absent_not_zero():
    raw = flexparse.parse(xml_text(xml_trade()))
    assert raw["trades"][0]["commission"] is None
    assert raw["commissions_included"] is False


def test_a_statement_with_no_trades_names_the_window_it_searched():
    with pytest.raises(FlexParseError, match="2026-08-13"):
        flexparse.parse(xml_text(from_date="2026-08-13", to_date="2026-08-13"))


def test_malformed_xml_is_not_silently_read_as_csv():
    with pytest.raises(FlexParseError, match="not parseable XML"):
        flexparse.parse(io.StringIO("<FlexQueryResponse><oops>\n"))


# --------------------------------------------------------------------------
# Short statement windows
# --------------------------------------------------------------------------
# This is the failure `_provenance_warnings` structurally CANNOT catch. Those
# checks inspect positions present in the rows; a contract opened last month and
# untouched since leaves no row at all in a one-day statement, so the netted
# book is short by a whole position with nothing anomalous to point at.
def test_a_single_day_statement_says_the_book_is_incomplete():
    raw = flexparse.parse(xml_text(xml_trade(dt="2026-08-13;095354"),
                                   from_date="2026-08-13", to_date="2026-08-13",
                                   period="LastBusinessDay"))
    assert any("MISSING ENTIRELY" in w for w in raw["book_warnings"])


def test_a_full_year_statement_carries_no_window_warning():
    raw = flexparse.parse(xml_text(xml_trade(), period="LastYear"))
    assert not any("MISSING ENTIRELY" in w for w in raw["book_warnings"])


def test_the_window_warning_lifts_when_another_export_supplies_the_history():
    """A short web-service statement passed ALONGSIDE the yearly exports is not
    a problem — the netting is fed from both. Warning on it anyway would train
    the operator to ignore the one case that matters."""
    raw = flexparse.parse([
        csv_text(row(tid="9", conid="777", dt="2025-06-02;100000")),
        xml_text(xml_trade(dt="2026-08-13;095354"),
                 from_date="2026-08-13", to_date="2026-08-13",
                 period="LastBusinessDay"),
    ])
    assert not any("MISSING ENTIRELY" in w for w in raw["book_warnings"])


def test_a_web_service_statement_is_named_not_shown_as_a_memory_address():
    with pytest.raises(FlexParseError, match="Flex web-service statement"):
        flexparse.parse(xml_text(from_date="2026-08-13", to_date="2026-08-13"))


# --------------------------------------------------------------------------
# Coverage gaps — the failure neither `_window_warning` nor
# `_provenance_warnings` can catch: a span NO source covers at all, where a
# position closed inside it leaves no closing fill anywhere and still nets
# open with nothing anomalous in the rows to point at.
# --------------------------------------------------------------------------
def test_a_csv_export_ending_before_a_one_day_statement_produces_a_gap_warning():
    """The real shape: a yearly CSV export ends well before a fetched
    LastBusinessDay statement, leaving a multi-week hole. AMD is still open
    at the end of the CSV and would net as open even if it closed in the gap."""
    csv_export = csv_text(
        row(tid="1", conid="100", sym="AMD", side="BUY", dt="2026-07-24;100000"))
    one_day_statement = xml_text(
        xml_trade(tid="2", conid="200", sym="NVDA", side="BUY", dt="2026-08-13;095354"),
        from_date="2026-08-13", to_date="2026-08-13", period="LastBusinessDay")
    raw = flexparse.parse([csv_export, one_day_statement])
    gap_warnings = [w for w in raw["book_warnings"] if "No source covers" in w]
    assert len(gap_warnings) == 1
    warning = gap_warnings[0]
    assert "2026-07-25 to 2026-08-12" in warning
    assert "19 calendar day" in warning
    assert "AMD" in warning
    assert "portfolio/input/" in warning


def test_contiguous_sources_produce_no_gap_warning():
    first = csv_text(row(tid="1", side="BUY", dt="2026-08-10;100000"))
    second = csv_text(row(tid="2", conid="200", side="BUY", dt="2026-08-11;100000",
                          strike="230"))
    raw = flexparse.parse([first, second])
    assert not any("No source covers" in w for w in raw["book_warnings"])


def test_a_friday_to_monday_step_is_not_reported_as_a_gap():
    """2026-08-14 is a Friday; the next session is Monday 2026-08-17. Only
    weekend days lie between them, so this is not a coverage gap."""
    friday = csv_text(row(tid="1", side="BUY", dt="2026-08-14;100000"))
    monday = csv_text(row(tid="2", conid="200", side="BUY", dt="2026-08-17;100000",
                          strike="230"))
    raw = flexparse.parse([friday, monday])
    assert not any("No source covers" in w for w in raw["book_warnings"])


def test_a_position_last_touched_after_the_gap_is_not_named_at_risk():
    """AMD's last fill is BEFORE the gap and it is still open at the end of
    both files, so it is at risk. MU is only ever touched on the far side of
    the gap (inside the one-day statement), so it could not have been closed
    in the hole and must not be named."""
    csv_export = csv_text(
        row(tid="1", conid="100", sym="AMD", side="BUY", dt="2026-07-24;100000"))
    one_day_statement = xml_text(
        xml_trade(tid="2", conid="200", sym="MU", side="BUY", dt="2026-08-13;095354"),
        from_date="2026-08-13", to_date="2026-08-13", period="LastBusinessDay")
    raw = flexparse.parse([csv_export, one_day_statement])
    gap_warnings = [w for w in raw["book_warnings"] if "No source covers" in w]
    assert len(gap_warnings) == 1
    assert "AMD" in gap_warnings[0]
    assert "MU" not in gap_warnings[0]


def test_a_declared_xml_window_closes_a_gap_the_observed_span_would_report():
    """The XML statement declares 2026-08-01..2026-08-13 even though its only
    fill is on 2026-08-13. Trusting the declared window (not the observed
    fill dates) proves the whole span was covered, closing what the
    observed-span fallback would have reported as a gap."""
    earlier = csv_text(row(tid="1", side="BUY", dt="2026-07-31;100000"))
    wide_statement = xml_text(
        xml_trade(tid="2", conid="200", side="BUY", dt="2026-08-13;095354", strike="230"),
        from_date="2026-08-01", to_date="2026-08-13", period="LastMonth")
    raw = flexparse.parse([earlier, wide_statement])
    assert not any("No source covers" in w for w in raw["book_warnings"])


# --------------------------------------------------------------------------
# parse_positions() — the declared OpenPositions book
# --------------------------------------------------------------------------
POSITIONS_HEADER = ("ClientAccountID,AssetClass,Symbol,Description,Conid,UnderlyingSymbol,"
                    "Multiplier,Strike,Expiry,Put/Call,ReportDate,Quantity,MarkPrice,"
                    "PositionValue,OpenPrice,CostBasisPrice,CostBasisMoney,"
                    "FifoPnlUnrealized,Side,LevelOfDetail")


def position_row(*, account="U1234567", asset="OPT", sym="NVDA", desc="NVDA 220 C",
                 conid="100", underlying="NVDA", mult="100", strike="220",
                 expiry="2026-09-18", right="C", report_date="2026-08-14",
                 qty="2", mark="6.00", value="1200", open_px="5.00",
                 cost_price="5.00", cost_money="1000", pnl="200", side="Long",
                 level="SUMMARY"):
    return (f"{account},{asset},{sym},{desc},{conid},{underlying},{mult},{strike},"
            f"{expiry},{right},{report_date},{qty},{mark},{value},{open_px},"
            f"{cost_price},{cost_money},{pnl},{side},{level}")


def positions_csv_text(*rows):
    return io.StringIO("\n".join([POSITIONS_HEADER, *rows]) + "\n")


def positions_xml_text(*positions, from_date="2026-08-14", to_date="2026-08-14",
                       period="LastBusinessDay"):
    body = "\n".join(positions)
    return io.StringIO(
        '<FlexQueryResponse queryName="positions" type="AF">\n'
        '<FlexStatements count="1">\n'
        f'<FlexStatement accountId="U1234567" fromDate="{from_date}" '
        f'toDate="{to_date}" period="{period}" whenGenerated="2026-08-14;125139">\n'
        f"<OpenPositions>\n{body}\n</OpenPositions>\n"
        "</FlexStatement>\n</FlexStatements>\n</FlexQueryResponse>\n")


def xml_position(*, asset="OPT", sym="NVDA", desc="NVDA 220 C", conid="100",
                 underlying="NVDA", mult="100", strike="220", expiry="2026-09-18",
                 right="C", report_date="2026-08-14", qty="2", mark="6.00",
                 value="1200", open_px="5.00", cost_price="5.00",
                 cost_money="1000", pnl="200", side="Long", level="SUMMARY"):
    return (f'<OpenPosition assetCategory="{asset}" symbol="{sym}" description="{desc}" '
            f'conid="{conid}" underlyingSymbol="{underlying}" multiplier="{mult}" '
            f'strike="{strike}" expiry="{expiry}" putCall="{right}" '
            f'reportDate="{report_date}" position="{qty}" markPrice="{mark}" '
            f'positionValue="{value}" openPrice="{open_px}" costBasisPrice="{cost_price}" '
            f'costBasisMoney="{cost_money}" fifoPnlUnrealized="{pnl}" side="{side}" '
            f'levelOfDetail="{level}" />')


def test_parse_positions_csv_and_xml_produce_identical_output():
    from_csv = flexparse.parse_positions(positions_csv_text(position_row()))
    from_xml = flexparse.parse_positions(positions_xml_text(xml_position()))
    for key in ("positions", "contracts", "net_liquidation",
                "skipped_non_option", "report_date"):
        assert from_csv[key] == from_xml[key], key


def test_parse_positions_maps_to_the_rawpull_position_shape():
    raw = flexparse.parse_positions(positions_csv_text(position_row()))
    pos = raw["positions"][0]
    assert pos == {"conid": 100, "position": 2.0, "avg_cost": 5.0,
                   "mkt_price": 6.0, "unrealized_pnl": 200.0}
    contract = raw["contracts"]["100"]
    assert contract["strike"] == 220
    assert contract["right"] == "C"
    assert contract["expiry"] == "2026-09-18"


def test_xml_quantity_attribute_is_position_not_quantity():
    """The XML element's quantity attribute is literally named `position`, not
    `quantity` — getting this wrong silently reads every declared position as
    size zero."""
    raw = flexparse.parse_positions(positions_xml_text(xml_position(qty="5")))
    assert raw["positions"][0]["position"] == 5.0


def test_non_option_positions_are_skipped_and_named():
    raw = flexparse.parse_positions(positions_csv_text(
        position_row(),
        position_row(conid="200", asset="STK", sym="CSPX", underlying="CSPX")))
    assert [p["conid"] for p in raw["positions"]] == [100]
    assert "CSPX" in raw["skipped_non_option"]


def test_a_missing_required_column_is_fatal():
    text = io.StringIO("Conid,Quantity\n100,2\n")
    with pytest.raises(FlexParseError, match="missing column"):
        flexparse.parse_positions(text)


# --- LevelOfDetail: the double-counting trap -------------------------------
def test_summary_rows_win_over_lot_rows_when_both_are_present():
    """A query saved at both SUMMARY and LOT granularity must not sum both —
    a LOT row and its SUMMARY row describe the SAME contracts twice over."""
    raw = flexparse.parse_positions(positions_csv_text(
        position_row(qty="3", level="SUMMARY"),
        position_row(qty="1", level="LOT"),
        position_row(qty="2", level="LOT")))
    assert raw["positions"][0]["position"] == 3


def test_lot_rows_are_summed_when_no_summary_row_exists():
    raw = flexparse.parse_positions(positions_csv_text(
        position_row(qty="1", level="LOT"),
        position_row(qty="2", level="LOT")))
    assert raw["positions"][0]["position"] == 3


def test_unlabelled_duplicate_conid_raises_rather_than_guessing():
    """No LevelOfDetail column at all, and the same conid appears twice —
    summing them would silently double-count the position, so this must
    raise rather than guess which row (if either) is the real one."""
    header = "Conid,Quantity,AssetClass,Strike,Expiry,Put/Call,UnderlyingSymbol"
    text = io.StringIO(
        f"{header}\n100,2,OPT,220,2026-09-18,C,NVDA\n100,1,OPT,220,2026-09-18,C,NVDA\n")
    with pytest.raises(FlexParseError, match="appears more than once"):
        flexparse.parse_positions(text)


def test_a_single_unlabelled_row_per_conid_is_accepted():
    header = "Conid,Quantity,AssetClass,Strike,Expiry,Put/Call,UnderlyingSymbol"
    text = io.StringIO(f"{header}\n100,2,OPT,220,2026-09-18,C,NVDA\n")
    raw = flexparse.parse_positions(text)
    assert raw["positions"][0]["position"] == 2.0


# --- NetLiquidation: detected, never assumed --------------------------------
def test_net_liquidation_is_none_when_no_nav_section_is_present():
    raw = flexparse.parse_positions(positions_csv_text(position_row()))
    assert raw["net_liquidation"] is None


def test_net_liquidation_is_read_from_a_bundled_nav_section_csv():
    # The OpenPositions section's own header MUST come first — `csv.DictReader`
    # takes the very first line as THE header for the whole file, so a NAV
    # block ahead of it would make the positions rows unreadable. A bundled
    # NAV/Account-Information section is realistically appended, not prepended.
    text = (POSITIONS_HEADER + "\n" + position_row() + "\n"
            + "ClientAccountID,NetLiquidation,Cash\nU1234567,51234.50,1000\n")
    raw = flexparse.parse_positions(io.StringIO(text))
    assert raw["net_liquidation"] == 51234.50


def test_net_liquidation_is_read_from_a_bundled_nav_section_xml():
    body = xml_position()
    text = io.StringIO(
        '<FlexQueryResponse queryName="positions" type="AF">\n'
        '<FlexStatements count="1">\n'
        '<FlexStatement accountId="U1234567" fromDate="2026-08-14" '
        'toDate="2026-08-14" period="LastBusinessDay" whenGenerated="2026-08-14;125139">\n'
        f"<OpenPositions>\n{body}\n</OpenPositions>\n"
        '<EquitySummaryByReportDateInBase reportDate="2026-08-14" total="51234.5" />\n'
        "</FlexStatement>\n</FlexStatements>\n</FlexQueryResponse>\n")
    raw = flexparse.parse_positions(text)
    assert raw["net_liquidation"] == 51234.5


# --------------------------------------------------------------------------
# parse(..., positions_source=...) — the declared path
# --------------------------------------------------------------------------
def test_book_reconstructed_is_false_on_the_declared_path():
    raw = flexparse.parse(csv_text(row()), positions_source=positions_csv_text(position_row()))
    assert raw["book_reconstructed"] is False


def test_book_reconstructed_is_true_without_a_positions_source():
    raw = flexparse.parse(csv_text(row()))
    assert raw["book_reconstructed"] is True


def test_a_declared_book_that_disagrees_with_the_netted_book_warns_naming_both_counts():
    """A SIZE mismatch where BOTH books carry the conid is unexplainable by any
    window story — the export demonstrably saw the contract. It stays a finding,
    in its original wording; only the bucket it is delivered in has moved."""
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="1"))
    positions = positions_csv_text(position_row(conid="100", qty="3"))
    raw = flexparse.parse(trades, positions_source=positions)
    diffs = [w for w in raw["book_diagnostics"]["unexplained"]
             if "declared OpenPositions book shows" in w]
    assert len(diffs) == 1
    assert "+3" in diffs[0]
    assert "+1" in diffs[0]
    assert "conid 100" in diffs[0]
    # ...and it no longer crowds the SOURCE LIMITS block.
    assert not any("declared OpenPositions book shows" in w
                   for w in raw["book_warnings"])


def test_a_declared_book_that_agrees_with_the_netted_book_is_silent():
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="2"))
    positions = positions_csv_text(position_row(conid="100", qty="2"))
    raw = flexparse.parse(trades, positions_source=positions)
    assert not any("declared OpenPositions book shows" in w for w in raw["book_warnings"])
    # Both lists, so this cannot pass by reading whichever one happens to be
    # empty: agreement means the cross-check found nothing anywhere.
    assert raw["book_diagnostics"]["unexplained"] == []
    assert raw["book_diagnostics"]["not_cross_checkable"] == []
    assert raw["book_diagnostics"]["coverage_explained"] == []


# --- classifying the disagreements ------------------------------------------
def test_a_declared_position_the_export_never_saw_is_not_cross_checkable():
    """The 28-line failure. With a "Last Business Day" trades query, everything
    opened earlier is absent from the export entirely — that is evidence of
    nothing, so it must not read as an alarm."""
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="2"))
    positions = positions_csv_text(
        position_row(conid="100", qty="2"),
        position_row(conid="999", sym="AMD", desc="AMD 150 C", underlying="AMD",
                     strike="150", expiry="2026-10-16", qty="2"))
    raw = flexparse.parse(trades, positions_source=positions)
    diag = raw["book_diagnostics"]
    assert len(diag["not_cross_checkable"]) == 1
    assert "conid 999" in diag["not_cross_checkable"][0]
    assert diag["unexplained"] == []
    assert not any("999" in w for w in raw["book_warnings"])


def test_a_conid_whose_rows_net_to_zero_is_still_a_finding():
    """The trap in the suppression rule. This conid HAS rows — an open and a
    close — so the export saw the position closed while the broker still shows
    it open. Suppressing on "netting gives absent" rather than "no rows at all"
    would silently swallow exactly the contradiction the cross-check exists for."""
    trades = csv_text(row(tid="1", conid="100", oc="O", side="BUY", qty="2"),
                      row(tid="2", conid="100", oc="C", side="SELL", qty="2"))
    positions = positions_csv_text(position_row(conid="100", qty="2"))
    raw = flexparse.parse(trades, positions_source=positions)
    diag = raw["book_diagnostics"]
    assert diag["not_cross_checkable"] == []
    assert len(diag["unexplained"]) == 1
    assert "conid 100" in diag["unexplained"][0]
    assert "absent" in diag["unexplained"][0]


def test_a_netted_position_missing_from_the_declared_book_is_explained_by_a_coverage_hole():
    """Netted-present / declared-absent, with a two-month hole no source covers
    after the position's last fill. A close inside that hole leaves no closing
    fill to net, so the NETTED side is the wrong one — not a missing fill."""
    old = csv_text(row(tid="1", conid="200", side="BUY", qty="2",
                       expiry="2026-09-18", dt="2026-06-01;103000"))
    recent = csv_text(row(tid="2", conid="100", side="BUY", qty="2",
                          dt="2026-08-14;103000"))
    positions = positions_csv_text(position_row(conid="100", qty="2"))
    raw = flexparse.parse([old, recent], positions_source=positions)
    diag = raw["book_diagnostics"]
    assert len(diag["coverage_explained"]) == 1
    assert "conid 200" in diag["coverage_explained"][0]
    assert diag["unexplained"] == []


def test_a_netted_position_missing_from_the_declared_book_stays_a_finding_if_covered():
    """Same shape, but every day from the position's last fill to the session is
    covered. Nothing could have closed it unseen, so the declared book dropping
    it is a real disagreement and stays a finding."""
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="2",
                          dt="2026-08-14;103000"),
                      row(tid="2", conid="200", side="BUY", qty="2",
                          expiry="2026-09-18", dt="2026-08-14;110000"))
    positions = positions_csv_text(position_row(conid="100", qty="2"))
    raw = flexparse.parse(trades, positions_source=positions)
    diag = raw["book_diagnostics"]
    assert diag["coverage_explained"] == []
    assert len(diag["unexplained"]) == 1
    assert "conid 200" in diag["unexplained"][0]


def test_book_diagnostics_carries_the_three_buckets_even_with_no_declared_book():
    """A consumer counting the buckets must not have to tell "the cross-check
    did not run" from "the key is missing" by probing for the key."""
    raw = flexparse.parse(csv_text(row()))
    assert raw["book_diagnostics"] == {
        "not_cross_checkable": [], "coverage_explained": [], "unexplained": []}


def test_reconstruction_only_warnings_are_skipped_on_the_declared_path():
    """A position opening with a CLOSE would normally flag truncated history
    (`_provenance_warnings`) — that guard exists only to caveat a RECONSTRUCTED
    book, so it must not fire when the book is declared instead."""
    trades = csv_text(row(tid="1", conid="100", oc="C", side="SELL"))
    positions = positions_csv_text(position_row(conid="100", qty="-1"))
    raw = flexparse.parse(trades, positions_source=positions)
    assert not any("predates the oldest export" in w for w in raw["book_warnings"])


def test_a_declared_position_with_no_matching_fill_still_validates():
    """The conid never appears in any trade fill — only `parse_positions`'s
    own contracts cover it, so `contracts` must be the UNION of trades- and
    positions-derived detail or `rawpull.validate()` rejects the pull."""
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="1"))
    positions = positions_csv_text(
        position_row(conid="100", qty="1"),
        position_row(conid="999", sym="AMD", desc="AMD 150 C", underlying="AMD",
                     strike="150", expiry="2026-10-16", qty="2"))
    raw = flexparse.parse(trades, positions_source=positions)
    assert any(p["conid"] == 999 for p in raw["positions"])
    assert "999" in raw["contracts"]
    from scripts.journal import rawpull
    rawpull.validate(raw)  # must not raise


def test_declared_positions_contracts_take_precedence_over_trades_contracts():
    """`contracts` is a union; the declared side is kept for a conid both
    sides describe, since it is the more authoritative source for the book."""
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="1"))
    positions = positions_csv_text(position_row(conid="100", qty="1"))
    raw = flexparse.parse(trades, positions_source=positions)
    assert raw["contracts"]["100"]["strike"] == 220


def test_a_declared_non_option_holding_reaches_the_pull_rather_than_vanishing():
    """The declared section is the first thing on this transport that can SEE a
    stock holding — netting only ever ran over option fills. "You hold none" and
    "this pipeline does not model them" are different statements, so the name
    must survive onto the pull for the report to print."""
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="1"))
    positions = positions_csv_text(
        position_row(conid="100", qty="1"),
        position_row(conid="777", asset="STK", sym="CSPX", desc="ISHARES CORE S&P 500",
                     underlying="CSPX", strike="", expiry="", right="", qty="40"))
    raw = flexparse.parse(trades, positions_source=positions)
    assert raw["skipped_non_option"] == ["CSPX"]
    # ...and it is NOT smuggled into the book it cannot price.
    assert not any(p["conid"] == 777 for p in raw["positions"])


def test_a_reconstructed_pull_reports_no_non_option_names():
    """Not because there were none — because a trades-only netting pass never
    looked. The empty list here is the honest answer for that path."""
    raw = flexparse.parse(csv_text(row()))
    assert raw["skipped_non_option"] == []


def test_net_liquidation_from_the_positions_source_is_used_when_not_passed_explicitly():
    trades = csv_text(row())
    text = (POSITIONS_HEADER + "\n" + position_row() + "\n"
            + "ClientAccountID,NetLiquidation,Cash\nU1234567,60000,1000\n")
    raw = flexparse.parse(trades, positions_source=io.StringIO(text))
    assert raw["net_liquidation"] == 60000.0


# --------------------------------------------------------------------------
# A declared book of NOTHING — the 2026-08-15 failure
# --------------------------------------------------------------------------
def test_an_empty_declared_book_is_refused_when_the_fills_say_otherwise():
    """The failure this guard exists for: the OpenPositions statement came back
    with zero rows while eighteen contracts were open, and a declared book is
    authoritative, so the journal printed "No open positions" and called the
    book complete. A flat book is the one answer a reader does not question.

    Untouched by the diff cross-check being demoted to `book_diagnostics`: this
    guard runs BEFORE it and raises rather than warning, so no amount of
    reclassification downstream can turn it back into a quiet line."""
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="1"))
    with pytest.raises(FlexParseError) as exc:
        flexparse.parse(trades, positions_source=positions_csv_text())
    message = str(exc.value)
    assert "EMPTY" in message
    assert "1 live position" in message
    assert "NVDA" in message


def test_an_empty_declared_book_is_fine_when_the_fills_agree():
    """A genuinely flat account must still journal cleanly."""
    trades = csv_text(row(tid="1", conid="100", oc="O", side="BUY", qty="1"),
                      row(tid="2", conid="100", oc="C", side="SELL", qty="1"))
    raw = flexparse.parse(trades, positions_source=positions_csv_text())
    assert raw["positions"] == []
    assert raw["book_reconstructed"] is False


def test_an_empty_declared_book_is_fine_when_the_only_netted_position_expired():
    """After an expiry the fills keep netting non-zero while the broker's book
    is genuinely flat. That is not a contradiction, so it must not raise."""
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="1",
                          expiry="2026-07-17", dt="2026-08-14;103000"))
    raw = flexparse.parse(trades, positions_source=positions_csv_text())
    assert raw["positions"] == []


def test_a_statement_with_no_openpositions_section_at_all_raises():
    """Zero rows because the query has no such section is a misconfiguration,
    not a flat book — and it is the one case the operator can act on."""
    trades_xml = io.StringIO(
        '<FlexQueryResponse queryName="trades" type="AF"><FlexStatements count="1">'
        '<FlexStatement accountId="U1234567"><Trades>'
        '<Trade conid="100" symbol="NVDA" /></Trades>'
        "</FlexStatement></FlexStatements></FlexQueryResponse>")
    with pytest.raises(FlexParseError, match="IBKR_FLEX_OPEN_POSITIONS_QUERY_ID"):
        flexparse.parse_positions(trades_xml)


def test_an_empty_openpositions_section_parses_as_a_flat_book():
    """The section is there and says nothing is held — that is an answer, and
    `parse()` is where it gets cross-examined against the fills."""
    declared = flexparse.parse_positions(positions_xml_text())
    assert declared["positions"] == []


def test_an_expired_netted_contract_is_not_diffed_against_the_declared_book():
    """An option that expired worthless has no closing fill, so netting reports
    it open forever. Diffing that against the declared book would leave a
    standing warning nothing can ever clear."""
    trades = csv_text(row(tid="1", conid="100", side="BUY", qty="1",
                          expiry="2026-07-17", dt="2026-08-14;103000"),
                      row(tid="2", conid="200", side="BUY", qty="2",
                          expiry="2026-09-18", dt="2026-08-14;103000"))
    positions = positions_csv_text(position_row(conid="200", qty="2"))
    raw = flexparse.parse(trades, positions_source=positions)
    assert not any("declared OpenPositions book shows" in w
                   for w in raw["book_warnings"])
    # Checked against BOTH keys — an expired contract must not merely be
    # reclassified into a quieter bucket, it must not be diffed at all.
    assert raw["book_diagnostics"] == {
        "not_cross_checkable": [], "coverage_explained": [], "unexplained": []}
