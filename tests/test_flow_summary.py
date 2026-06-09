"""Tests for lib/flow_summary.py — aggregation correctness, not formatting polish."""
from lib.flow_summary import (
    _classify_sentiment,
    _flow_ticker_rows,
    _unusual_ticker_rows,
    _voloi_by_symbol,
    cross_section_tickers,
    filter_by_ticker,
    score_flow_rollup,
    score_label,
    summarize_flow,
    summarize_persistence,
    summarize_unusual,
)


# ---------------------------------------------------------------------------
# Sentiment rules (per config/barchart-reference.md)
# ---------------------------------------------------------------------------

def test_sentiment_call_ask_bullish():
    assert _classify_sentiment("Call", "ask") == "bullish"

def test_sentiment_put_bid_bullish():
    assert _classify_sentiment("Put", "bid") == "bullish"

def test_sentiment_call_bid_bearish():
    assert _classify_sentiment("Call", "bid") == "bearish"

def test_sentiment_put_ask_bearish():
    assert _classify_sentiment("Put", "ask") == "bearish"

def test_sentiment_mid_neutral():
    assert _classify_sentiment("Call", "mid") == "neutral"
    assert _classify_sentiment("Put", "mid") == "neutral"

def test_sentiment_case_insensitive():
    assert _classify_sentiment("CALL", "ASK") == "bullish"


# ---------------------------------------------------------------------------
# Flow aggregation
# ---------------------------------------------------------------------------

def _flow_row(symbol, opt_type, side, premium, *, strike="100", dte="30",
              iv="50%", flag="", time="10:00 ET", size="100"):
    return {
        "Symbol": symbol, "Type": opt_type, "Strike": strike, "DTE": dte,
        "Side": side, "Premium": premium, "Size": size, "IV": iv, "*": flag,
        "Time": time,
    }


def test_flow_rollup_sums_premium_per_ticker():
    rows = [
        _flow_row("AVGO", "Call", "ask", "1000000"),
        _flow_row("AVGO", "Put",  "bid", "500000"),
        _flow_row("MRVL", "Call", "mid", "200000"),
    ]
    rollup = _flow_ticker_rows(rows)
    by_sym = {r["symbol"]: r for r in rollup}
    assert by_sym["AVGO"]["premium_total"] == 1_500_000
    assert by_sym["AVGO"]["premium_call"]  == 1_000_000
    assert by_sym["AVGO"]["premium_put"]   == 500_000
    assert by_sym["MRVL"]["premium_total"] == 200_000


def test_flow_rollup_sorted_by_total_premium():
    rows = [
        _flow_row("SMALL",  "Call", "ask", "100"),
        _flow_row("BIG",    "Call", "ask", "1000000"),
        _flow_row("MEDIUM", "Call", "ask", "5000"),
    ]
    rollup = _flow_ticker_rows(rows)
    assert [r["symbol"] for r in rollup] == ["BIG", "MEDIUM", "SMALL"]


def test_flow_rollup_counts_sentiment():
    rows = [
        _flow_row("X", "Call", "ask", "100"),  # bullish
        _flow_row("X", "Call", "ask", "100"),  # bullish
        _flow_row("X", "Put",  "ask", "100"),  # bearish
        _flow_row("X", "Call", "mid", "100"),  # neutral
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["bullish"] == 2
    assert r["bearish"] == 1
    assert r["neutral"] == 1


def test_flow_rollup_counts_opening_flags():
    rows = [
        _flow_row("X", "Call", "ask", "100", flag="BuyToOpen"),
        _flow_row("X", "Call", "ask", "100", flag="SellToOpen"),
        _flow_row("X", "Call", "mid", "100", flag="ToOpen"),
        _flow_row("X", "Call", "ask", "100", flag=""),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["buy_to_open"]  == 1
    assert r["sell_to_open"] == 1
    assert r["to_open"]      == 1


def test_flow_rollup_weighted_dte():
    # 1M premium @ DTE 10, 1M premium @ DTE 30 → weighted avg = 20
    rows = [
        _flow_row("X", "Call", "ask", "1000000", dte="10"),
        _flow_row("X", "Call", "ask", "1000000", dte="30"),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["dte_w"] == 20.0


def test_flow_rollup_biggest_trade():
    rows = [
        _flow_row("X", "Call", "ask", "100"),
        _flow_row("X", "Put",  "bid", "9999999", strike="850"),
        _flow_row("X", "Call", "ask", "100"),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["biggest"][0] == 9_999_999
    assert r["biggest"][1] == "Put"
    assert r["biggest"][2] == "850"


def test_flow_handles_commas_and_percent_in_numbers():
    rows = [_flow_row("X", "Call", "ask", "1,500,000", iv="125.5%", dte="14")]
    r = _flow_ticker_rows(rows)[0]
    assert r["premium_total"] == 1_500_000
    assert r["iv_w"] == 125.5


def test_flow_skips_blank_symbols():
    rows = [
        _flow_row("", "Call", "ask", "100"),
        _flow_row("AAPL", "Call", "ask", "100"),
    ]
    rollup = _flow_ticker_rows(rows)
    assert len(rollup) == 1
    assert rollup[0]["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Conviction scoring (direction-agnostic)
# ---------------------------------------------------------------------------

def test_score_label_buckets():
    assert score_label(0) == "ignore"
    assert score_label(2) == "ignore"
    assert score_label(3) == "watch"
    assert score_label(5) == "watch"
    assert score_label(6) == "candidate"
    assert score_label(8) == "candidate"
    assert score_label(9) == "high-conv"
    assert score_label(13) == "high-conv"


def test_score_maxes_out_with_full_corroboration():
    # Top premium of the day, heavy repetition, in unusual, big Vol/OI, opening label.
    rows = [_flow_row("BIG", "Call", "ask", "1000000", flag="BuyToOpen") for _ in range(10)]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup, unusual_syms={"BIG"}, voloi_by_sym={"BIG": 30.0})
    r = rollup[0]
    assert r["score_parts"] == {"flow": 3, "rep": 2, "cross": 2, "voloi": 2, "open": 1, "persist": 0}
    assert r["score"] == 10
    assert r["score_label"] == "high-conv"


def test_flow_rollup_sums_size_and_premium_per_contract():
    rows = [
        _flow_row("X", "Call", "ask", "100", size="40"),
        _flow_row("X", "Call", "ask", "100", size="60"),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["size_total"] == 100
    assert r["prem_per_ct"] == 2.0  # $200 premium / 100 contracts


def test_score_flow_size_guard_discounts_thin_size_never_boosts():
    # EXPENSIVE: top premium but almost no contracts (vol-/price-inflated).
    # BIGSIZE:   low premium but most of the day's contracts (lottery-ish).
    rows = [
        _flow_row("EXPENSIVE", "Call", "ask", "9000000", size="10"),
        *[_flow_row("BIGSIZE", "Call", "ask", "1000000", size="500") for _ in range(3)],
    ]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup)
    flow = {r["symbol"]: r["score_parts"]["flow"] for r in rollup}
    # Top-premium-but-thin-size is capped below its raw premium rank of 3.
    assert flow["EXPENSIVE"] < 3
    # Fat-size-but-cheap is NOT lifted above its premium rank of 0.
    assert flow["BIGSIZE"] == 0


def test_score_flow_falls_back_to_premium_when_size_absent():
    # No Size column anywhere → size cap never binds → flow == premium rank.
    rows = [
        {"Symbol": "BIG", "Type": "Call", "Side": "ask", "Premium": "9000000"},
        {"Symbol": "SMALL", "Type": "Call", "Side": "ask", "Premium": "100"},
    ]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup)
    flow = {r["symbol"]: r["score_parts"]["flow"] for r in rollup}
    assert flow["BIG"] == 3     # top premium, unguarded
    assert flow["SMALL"] == 0   # bottom premium


def test_score_isolated_tiny_name_is_ignore():
    rows = [
        *[_flow_row("BIG", "Call", "ask", "1000000", flag="BuyToOpen") for _ in range(10)],
        _flow_row("TINY", "Call", "mid", "100"),  # 1 trade, no flag, not in unusual
    ]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup, unusual_syms={"BIG"}, voloi_by_sym={"BIG": 30.0})
    tiny = next(r for r in rollup if r["symbol"] == "TINY")
    assert tiny["score"] == 0
    assert tiny["score_label"] == "ignore"


def test_score_missing_opening_label_is_zero_not_negative():
    # No opening flag, no cross-section, no Vol/OI — but top premium + repetition.
    rows = [_flow_row("X", "Call", "ask", "1000000") for _ in range(5)]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup)  # no unusual data at all
    r = rollup[0]
    assert r["score_parts"]["open"] == 0
    assert r["score_parts"]["cross"] == 0
    assert r["score"] == 4  # flow 3 + rep 1 (5 trades) — never goes negative


def test_score_is_direction_agnostic():
    # Identical size/repetition/labels, opposite direction → identical score.
    bull = [_flow_row("BULL", "Call", "ask", "500000", flag="BuyToOpen") for _ in range(6)]
    bear = [_flow_row("BEAR", "Put", "ask", "500000", flag="SellToOpen") for _ in range(6)]
    rollup = _flow_ticker_rows(bull + bear)
    score_flow_rollup(rollup, unusual_syms={"BULL", "BEAR"}, voloi_by_sym={"BULL": 12.0, "BEAR": 12.0})
    by_sym = {r["symbol"]: r["score"] for r in rollup}
    assert by_sym["BULL"] == by_sym["BEAR"]


def test_score_persistence_bonus_caps_at_three():
    rows = [_flow_row("X", "Call", "ask", "1000000", flag="BuyToOpen")]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup, persist_days_by_sym={"X": 9})
    assert rollup[0]["score_parts"]["persist"] == 3


def test_voloi_by_symbol_takes_max():
    rows = [_un_row("X", "Call", "10.0"), _un_row("X", "Put", "48.5"), _un_row("Y", "Call", "5.0")]
    out = _voloi_by_symbol(rows)
    assert out["X"] == 48.5
    assert out["Y"] == 5.0


def test_summarize_flow_rollup_sorted_by_score():
    # WEAK has bigger premium but no corroboration; STRONG wins on score.
    rows = [
        _flow_row("WEAK", "Call", "mid", "9000000"),  # 1 trade, no flag, not unusual
        *[_flow_row("STRONG", "Call", "ask", "500000", flag="BuyToOpen") for _ in range(8)],
    ]
    out = summarize_flow(rows, "Stocks Flow", top_n=5,
                         unusual_rows=[_un_row("STRONG", "Call", "30.0")])
    rollup_section = out.split("top")[0]
    assert rollup_section.index("STRONG") < rollup_section.index("WEAK")


# ---------------------------------------------------------------------------
# Persistence (multi-day)
# ---------------------------------------------------------------------------

def test_persistence_includes_recurring_excludes_single_day():
    days = [
        {"date": "2026-06-01", "flow_rows": [
            _flow_row("AAA", "Call", "ask", "1000000", flag="BuyToOpen"),
            _flow_row("BBB", "Call", "ask", "1000000"),  # only day 1
        ], "unusual_rows": []},
        {"date": "2026-06-02", "flow_rows": [
            _flow_row("AAA", "Call", "ask", "1000000", flag="BuyToOpen"),
        ], "unusual_rows": []},
        {"date": "2026-06-03", "flow_rows": [
            _flow_row("AAA", "Call", "ask", "1000000", flag="BuyToOpen"),
        ], "unusual_rows": []},
    ]
    out = summarize_persistence(days, "Stocks flow")
    assert "AAA" in out
    assert "BBB" not in out          # single-day name excluded from persistence
    assert "3/3" in out              # AAA present all three days


def test_persistence_trajectory_marks_absent_days():
    days = [
        {"date": "2026-06-01", "flow_rows": [_flow_row("AAA", "Call", "ask", "1000000")], "unusual_rows": []},
        {"date": "2026-06-02", "flow_rows": [], "unusual_rows": []},  # AAA absent
        {"date": "2026-06-03", "flow_rows": [_flow_row("AAA", "Call", "ask", "1000000")], "unusual_rows": []},
    ]
    out = summarize_persistence(days, "Stocks flow")
    assert "AAA" in out
    assert "2/3" in out              # present on 2 of 3 days
    assert "—" in out               # absent middle day shown as a gap


def test_persistence_empty_window():
    assert "_No data._" in summarize_persistence([], "Stocks flow")


def test_persistence_no_recurring_names():
    days = [
        {"date": "2026-06-01", "flow_rows": [_flow_row("AAA", "Call", "ask", "100")], "unusual_rows": []},
        {"date": "2026-06-02", "flow_rows": [_flow_row("BBB", "Call", "ask", "100")], "unusual_rows": []},
    ]
    out = summarize_persistence(days, "Stocks flow")
    assert "two or more days" in out


# ---------------------------------------------------------------------------
# Unusual aggregation
# ---------------------------------------------------------------------------

def _un_row(symbol, opt_type, voloi, *, strike="100", dte="14", volume="1000", moneyness="ATM"):
    return {
        "Symbol": symbol, "Type": opt_type, "Strike": strike, "DTE": dte,
        "Volume": volume, "Vol/OI": voloi, "Moneyness": moneyness,
    }


def test_unusual_rollup_max_voloi_and_call_put():
    rows = [
        _un_row("X", "Call", "10.5"),
        _un_row("X", "Put",  "48.48"),
        _un_row("X", "Call", "3.2"),
    ]
    r = _unusual_ticker_rows(rows)[0]
    assert r["calls"] == 2
    assert r["puts"]  == 1
    assert r["max_voloi"] == 48.48
    assert r["biggest"][1] == "Put"


def test_unusual_rollup_sorted_by_max_voloi():
    rows = [
        _un_row("LOW",  "Call", "2.0"),
        _un_row("HIGH", "Call", "99.0"),
        _un_row("MID",  "Call", "10.0"),
    ]
    rollup = _unusual_ticker_rows(rows)
    assert [r["symbol"] for r in rollup] == ["HIGH", "MID", "LOW"]


def test_unusual_dte_range():
    rows = [
        _un_row("X", "Call", "5.0", dte="7"),
        _un_row("X", "Call", "5.0", dte="45"),
        _un_row("X", "Call", "5.0", dte="14"),
    ]
    r = _unusual_ticker_rows(rows)[0]
    assert r["dte_min"] == 7
    assert r["dte_max"] == 45


# ---------------------------------------------------------------------------
# Cross-section + filter
# ---------------------------------------------------------------------------

def test_cross_section_overlap():
    flow = [{"Symbol": "AVGO"}, {"Symbol": "MRVL"}, {"Symbol": "TSLA"}]
    unusual = [{"Symbol": "AVGO"}, {"Symbol": "AAPL"}, {"Symbol": "TSLA"}]
    assert cross_section_tickers(flow, unusual) == ["AVGO", "TSLA"]


def test_cross_section_no_overlap():
    flow = [{"Symbol": "A"}]
    unusual = [{"Symbol": "B"}]
    assert cross_section_tickers(flow, unusual) == []


def test_filter_by_ticker_case_insensitive():
    rows = [{"Symbol": "AVGO"}, {"Symbol": "mrvl"}, {"Symbol": "AVGO"}]
    assert len(filter_by_ticker(rows, "avgo")) == 2
    assert len(filter_by_ticker(rows, "MRVL")) == 1


# ---------------------------------------------------------------------------
# Markdown output smoke tests — just confirm structure exists
# ---------------------------------------------------------------------------

def test_summarize_flow_empty():
    out = summarize_flow([], "Stocks Flow")
    assert "_No data available._" in out


def test_summarize_flow_includes_rollup_and_top_trades():
    rows = [_flow_row("AVGO", "Call", "ask", "1000000")]
    out = summarize_flow(rows, "Stocks Flow", top_n=5)
    assert "ticker rollup" in out
    assert "top 1 trades by premium" in out
    assert "AVGO" in out


def test_summarize_unusual_empty():
    assert "_No data available._" in summarize_unusual([], "Unusual")


def test_summarize_unusual_includes_rollup_and_top_rows():
    rows = [_un_row("AVGO", "Call", "12.5")]
    out = summarize_unusual(rows, "Unusual Stocks", top_n=5)
    assert "ticker rollup" in out
    assert "top 1 rows by Vol/OI" in out
    assert "AVGO" in out
