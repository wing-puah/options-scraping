"""Tests for lib/flow_summary/ — aggregation correctness, not formatting polish."""
import csv
import io

import pytest

from lib.flow_summary import (
    FLOW_CSV_COLUMNS,
    _classify_sentiment,
    _flow_ticker_rows,
    _voloi_by_symbol,
    build_scored_flow_rollup,
    cross_section_tickers,
    filter_by_ticker,
    flow_rollup_csv,
    hedge_pressure,
    hedge_pressure_md,
    oi_breakdown_csv,
    score_flow_rollup,
    score_label,
    summarize_flow,
    summarize_persistence,
    ticker_metrics,
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
# Extrinsic premium / delta exposure / horizon (pollution columns)
# ---------------------------------------------------------------------------

def _rich_row(symbol, opt_type, side, premium, *, spot, strike, delta,
              size="100", dte="30", iv="50%", flag="", time="10:00 ET"):
    """Flow row with the columns the extrinsic/delta aggregates read."""
    return {
        "Symbol": symbol, "Price~": spot, "Type": opt_type, "Strike": strike,
        "DTE": dte, "Side": side, "Premium": premium, "Size": size, "IV": iv,
        "Delta": delta, "*": flag, "Time": time,
    }


def test_extrinsic_strips_intrinsic_from_deep_itm():
    # Deep-ITM put: spot 380, strike 450 → intrinsic $70/share. 100 contracts
    # at $70.50 → premium 705,000 but only 5,000 of real time value.
    rows = [_rich_row("GLD", "Put", "mid", "705000",
                      spot="380", strike="450", delta="-0.95")]
    r = _flow_ticker_rows(rows)[0]
    assert r["premium_total"] == 705_000
    assert r["ext_total"] == pytest.approx(5_000)
    assert r["ext_put"] == pytest.approx(5_000)
    assert r["ext_call"] == 0.0


def test_extrinsic_otm_keeps_full_premium():
    # OTM put (spot 600, strike 550): zero intrinsic → all premium is extrinsic.
    rows = [_rich_row("SMH", "Put", "ask", "2000000",
                      spot="600", strike="550", delta="-0.30")]
    r = _flow_ticker_rows(rows)[0]
    assert r["ext_total"] == 2_000_000
    assert r["fin_share"] == 0.0


def test_extrinsic_falls_back_to_premium_when_spot_missing():
    # No Price~ column → no intrinsic computable → never discounted.
    rows = [_flow_row("X", "Put", "mid", "705000", strike="450")]
    r = _flow_ticker_rows(rows)[0]
    assert r["ext_total"] == 705_000


def test_financing_share_counts_high_delta_premium():
    rows = [
        _rich_row("X", "Put", "mid", "900000", spot="380", strike="450", delta="-0.95"),
        _rich_row("X", "Put", "ask", "100000", spot="380", strike="350", delta="-0.30"),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["fin_share"] == pytest.approx(0.9)


def test_delta_notional_is_signed_share_equivalent_dollars():
    # -0.30 delta × 100 contracts × 100 shares × $600 spot = -$1.8M exposure.
    rows = [_rich_row("SMH", "Put", "ask", "2000000",
                      spot="600", strike="550", delta="-0.30")]
    r = _flow_ticker_rows(rows)[0]
    assert r["delta_notional"] == pytest.approx(-1_800_000)


def test_horizon_dominant_dte_bucket_by_extrinsic():
    rows = [
        _rich_row("X", "Call", "ask", "100000", spot="100", strike="120", delta="0.20", dte="7"),
        _rich_row("X", "Call", "ask", "300000", spot="100", strike="120", delta="0.25", dte="45"),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["horizon"] == "tact 75%"


def test_score_flow_ranks_extrinsic_not_raw_premium():
    # FINANCED: day's biggest raw premium, almost all intrinsic (deep ITM).
    # REALBET:  smaller raw premium, all extrinsic (OTM).
    # filler names give the rank buckets a population.
    rows = [
        _rich_row("FINANCED", "Put", "mid", "14100000",
                  spot="380", strike="450", delta="-0.95", size="2000"),
        _rich_row("REALBET", "Put", "ask", "5000000",
                  spot="600", strike="550", delta="-0.30", size="2000"),
        *[_rich_row(f"F{i}", "Call", "ask", "50000",
                    spot="100", strike="110", delta="0.30") for i in range(4)],
    ]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup)
    by_sym = {r["symbol"]: r for r in rollup}
    # 14.1M premium − 14M intrinsic (70 × 2000 × 100) = 0.1M extrinsic.
    assert by_sym["FINANCED"]["ext_total"] == pytest.approx(100_000)
    assert by_sym["REALBET"]["score_parts"]["flow"] > by_sym["FINANCED"]["score_parts"]["flow"]


# ---------------------------------------------------------------------------
# Hedge pressure
# ---------------------------------------------------------------------------

def test_hedge_pressure_pure_hedging_scores_100():
    etf = [_rich_row("SPY", "Put", "ask", "1000000", spot="700", strike="650", delta="-0.30")]
    hp = hedge_pressure([], etf)
    assert hp["score"] == 100
    assert hp["label"] == "panic"
    assert hp["by_ticker"] == {"SPY": 1_000_000.0}


def test_hedge_pressure_pure_stock_calls_scores_0():
    stock = [_rich_row("NVDA", "Call", "ask", "1000000", spot="180", strike="200", delta="0.30")]
    hp = hedge_pressure(stock, [])
    assert hp["score"] == 0
    assert hp["label"] == "risk-on"


def test_hedge_pressure_balanced_is_hedge_pressure_bucket():
    stock = [_rich_row("NVDA", "Call", "ask", "1000000", spot="180", strike="200", delta="0.30")]
    etf = [_rich_row("QQQ", "Put", "ask", "1000000", spot="700", strike="650", delta="-0.30")]
    hp = hedge_pressure(stock, etf)
    assert hp["score"] == 50
    assert hp["label"] == "hedge-pressure"


def test_hedge_pressure_ignores_deep_itm_financing_puts():
    # Deep-ITM SPY put is intrinsic — not hedge demand.
    stock = [_rich_row("NVDA", "Call", "ask", "1000000", spot="180", strike="200", delta="0.30")]
    etf = [_rich_row("SPY", "Put", "mid", "7050000",
                     spot="650", strike="720", delta="-0.97", size="1000")]
    hp = hedge_pressure(stock, etf)
    # 7.05M premium − 7M intrinsic = 50K extrinsic vs 1M stock calls → ~5.
    assert hp["score"] == 5
    assert hp["label"] == "risk-on"


def test_hedge_pressure_non_hedge_etf_puts_do_not_count():
    stock = [_rich_row("NVDA", "Call", "ask", "1000000", spot="180", strike="200", delta="0.30")]
    etf = [_rich_row("XLE", "Put", "ask", "9000000", spot="90", strike="80", delta="-0.30")]
    hp = hedge_pressure(stock, etf)
    assert hp["score"] == 0  # XLE is not a hedge vehicle


def test_hedge_pressure_no_data_returns_none_and_md_degrades():
    assert hedge_pressure([], []) is None
    assert "_No flow data to compute._" in hedge_pressure_md([], [])


def test_hedge_pressure_md_smoke():
    etf = [_rich_row("SPY", "Put", "ask", "1000000", spot="700", strike="650", delta="-0.30")]
    out = hedge_pressure_md([], etf)
    assert "## Hedge pressure" in out
    assert "100/100" in out
    assert "PANIC" in out


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
    # otm is 0: _flow_row carries no Delta cell, so OTM-prob weighting never fires.
    # fin_penalty is 0: these rows carry no Delta, so fin_share is 0 (no financing).
    # oi_confirm is 0: _flow_row carries no oi_change, so open-confirmation is absent.
    assert r["score_parts"] == {
        "flow": 3, "rep": 2, "cross": 2, "voloi": 2, "otm": 0, "open": 1, "persist": 0,
        "oi_confirm": 0, "fin_penalty": 0,
    }
    assert r["score"] == 10
    assert r["score_label"] == "high-conv"


def _fin_penalty_for(deep_prem, otm_prem):
    """Score a single name whose premium splits between a deep-ITM (|delta| 0.95)
    financing leg and an OTM (|delta| 0.30) leg, and return its fin_penalty."""
    rows = [
        _rich_row("X", "Put", "mid", str(deep_prem), spot="380", strike="450", delta="-0.95"),
        _rich_row("X", "Put", "ask", str(otm_prem), spot="380", strike="350", delta="-0.30"),
    ]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup)
    return rollup[0]["score_parts"]["fin_penalty"]


def test_financing_penalty_scales_with_dominance():
    # Direction-agnostic demotion: penalty deepens as the |delta|≥0.85 financing
    # share rises past 0.60 / 0.75 / 0.90. Below 0.60 a real bet is untouched.
    assert _fin_penalty_for(500_000, 500_000) == 0    # fin_share 0.50 — spared
    assert _fin_penalty_for(650_000, 350_000) == -2   # 0.65
    assert _fin_penalty_for(800_000, 200_000) == -3   # 0.80
    assert _fin_penalty_for(950_000, 50_000) == -4    # 0.95


def test_financing_penalty_clamps_total_at_zero():
    # A pure deep-ITM financing name (fin_share 1.0) takes the full −4; total
    # score is clamped to ≥0, never negative.
    rows = [_rich_row("X", "Put", "mid", "900000", spot="380", strike="450", delta="-0.95")]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup)
    assert rollup[0]["score_parts"]["fin_penalty"] == -4
    assert rollup[0]["score"] >= 0


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


def test_persistence_callout_lists_names_on_three_plus_days():
    day = lambda d, syms: {"date": d, "flow_rows": [
        _flow_row(s, "Call", "ask", "1000000") for s in syms], "unusual_rows": []}
    days = [
        day("2026-06-01", ["AAA", "BBB"]),
        day("2026-06-02", ["AAA", "BBB"]),
        day("2026-06-03", ["AAA"]),
    ]
    out = summarize_persistence(days, "Stocks flow")
    assert "Persistent names (≥3 days):" in out
    assert "AAA 3/3" in out
    assert "BBB" not in out.split("\n\n")[1]  # 2-day name stays out of the callout


def test_persistence_no_callout_below_three_days():
    days = [
        {"date": "2026-06-01", "flow_rows": [_flow_row("AAA", "Call", "ask", "100")], "unusual_rows": []},
        {"date": "2026-06-02", "flow_rows": [_flow_row("AAA", "Call", "ask", "100")], "unusual_rows": []},
    ]
    out = summarize_persistence(days, "Stocks flow")
    assert "Persistent names" not in out


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
# OTM-probability weighting + IV spread/skew (papers 03 & 04)
# ---------------------------------------------------------------------------

def _flow_row_d(symbol, opt_type, side, premium, *, delta, strike="100",
                spot="100", iv="50%", size="100", dte="30",
                expiry="2026-08-21", oi="500"):
    """Flow row carrying Delta + Price~ so OTM/IV signals can fire.

    Defaults pass the Lin/Lu/Driessen data filters (positive OI, in-bounds IV,
    spot ≥ $5, in-window DTE) so pair/skew tests fire unless a test opts out.
    """
    return {
        "Symbol": symbol, "Type": opt_type, "Strike": strike, "Price~": spot,
        "Expires": expiry, "DTE": dte, "Side": side, "Premium": premium,
        "Size": size, "IV": iv, "Delta": delta, "Open Int": oi,
        "*": "", "Time": "10:00 ET",
    }


def test_otm_ext_weights_by_one_minus_abs_delta():
    # Same OTM call premium (intrinsic 0), different delta → otm_ext scales 1−|delta|.
    near = _flow_row_d("NEAR", "Call", "ask", "100000", delta="0.20", strike="120", spot="100")
    deep = _flow_row_d("DEEP", "Call", "ask", "100000", delta="0.80", strike="105", spot="100")
    by_sym = {r["symbol"]: r for r in _flow_ticker_rows([near, deep])}
    # ext is full premium for both (OTM → no intrinsic); otm_ext = ext × (1−|delta|).
    assert by_sym["NEAR"]["otm_ext"] == pytest.approx(100_000 * 0.80)
    assert by_sym["DEEP"]["otm_ext"] == pytest.approx(100_000 * 0.20)


def test_otm_ext_zero_without_delta_cell():
    # No Delta cell → otm_ext stays 0 (absent data is never credited).
    rows = [_flow_row("X", "Call", "ask", "100000")]
    assert _flow_ticker_rows(rows)[0]["otm_ext"] == 0.0


def test_otm_component_rewards_otm_flow_and_zero_when_absent():
    rows = [
        # OTM-heavy name: low delta, sizeable extrinsic.
        *[_flow_row_d("OTM", "Call", "ask", "1000000", delta="0.15", strike="130", spot="100") for _ in range(3)],
        # ITM/financing name: high delta → tiny otm_ext.
        *[_flow_row_d("ITM", "Call", "ask", "1000000", delta="0.95", strike="50", spot="100") for _ in range(3)],
        # No-delta name → otm component must be 0, not top-bucket.
        *[_flow_row("NODELTA", "Call", "ask", "1000000") for _ in range(3)],
    ]
    rollup = _flow_ticker_rows(rows)
    score_flow_rollup(rollup)
    parts = {r["symbol"]: r["score_parts"]["otm"] for r in rollup}
    assert parts["OTM"] > parts["ITM"]
    assert parts["NODELTA"] == 0


def test_iv_spread_is_matched_pair_call_minus_put():
    # Matched pair: same strike + expiry → OI-weighted (IV_call − IV_put).
    rows = [
        _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%",
                    strike="100", expiry="2026-08-21", oi="500"),
        _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="40%",
                    strike="100", expiry="2026-08-21", oi="500"),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["iv_spread"] == pytest.approx(20.0)   # 60 − 40
    assert r["iv_call_w"] == pytest.approx(60.0)
    assert r["iv_put_w"] == pytest.approx(40.0)


def test_iv_spread_oi_weights_across_matched_pairs():
    # Two matched pairs, different OI → OI-weighted average of the per-pair diffs.
    rows = [
        # Pair A: diff +10, OI 900.
        _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%",
                    strike="100", expiry="2026-08-21", oi="900"),
        _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="50%",
                    strike="100", expiry="2026-08-21", oi="900"),
        # Pair B: diff −10, OI 100.
        _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="40%",
                    strike="110", expiry="2026-08-21", oi="100"),
        _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="50%",
                    strike="110", expiry="2026-08-21", oi="100"),
    ]
    r = _flow_ticker_rows(rows)[0]
    # (10·900 + (−10)·100) / (900 + 100) = 8000/1000 = 8.0
    assert r["iv_spread"] == pytest.approx(8.0)


def test_iv_spread_none_when_no_matched_pair():
    # Call and put at DIFFERENT strikes → no matched pair → None.
    rows = [
        _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%", strike="100"),
        _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="40%", strike="90"),
    ]
    assert _flow_ticker_rows(rows)[0]["iv_spread"] is None


def test_iv_spread_none_when_one_side_absent():
    rows = [_flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%")]
    assert _flow_ticker_rows(rows)[0]["iv_spread"] is None


def test_iv_spread_excludes_out_of_window_dte():
    # Matched strike/expiry but DTE outside 10–60 → excluded → None.
    rows = [
        _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%", dte="5"),
        _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="40%", dte="5"),
    ]
    assert _flow_ticker_rows(rows)[0]["iv_spread"] is None


def test_iv_skew_is_otm_put_minus_atm_call():
    rows = [
        # ATM call: K/S = 100/100 = 1.0 (band [0.95, 1.05]), IV 30.
        _flow_row_d("X", "Call", "ask", "100000", delta="0.50", iv="30%",
                    strike="100", spot="100"),
        # OTM put: K/S = 90/100 = 0.90 (band [0.80, 0.95]), IV 55 → steep skew.
        _flow_row_d("X", "Put", "ask", "100000", delta="-0.20", iv="55%",
                    strike="90", spot="100"),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["iv_skew"] == pytest.approx(25.0)     # 55 − 30


def test_iv_skew_picks_closest_moneyness_contract():
    rows = [
        _flow_row_d("X", "Call", "ask", "100000", delta="0.50", iv="30%",
                    strike="100", spot="100"),
        # Two in-band OTM puts: K/S 0.94 (closest to 0.95) IV 55 vs K/S 0.82 IV 70.
        _flow_row_d("X", "Put", "ask", "100000", delta="-0.20", iv="55%",
                    strike="94", spot="100"),
        _flow_row_d("X", "Put", "ask", "100000", delta="-0.10", iv="70%",
                    strike="82", spot="100"),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["iv_skew"] == pytest.approx(25.0)     # uses K/S 0.94 put (55), not 0.82 (70)


def test_iv_skew_none_when_put_band_empty():
    # Only an ATM put (K/S 1.0) — outside the OTM-put band → no skew.
    rows = [
        _flow_row_d("X", "Call", "ask", "100000", delta="0.50", iv="30%",
                    strike="100", spot="100"),
        _flow_row_d("X", "Put", "ask", "100000", delta="-0.50", iv="55%",
                    strike="100", spot="100"),
    ]
    assert _flow_ticker_rows(rows)[0]["iv_skew"] is None


def test_counterpart_iv_completes_single_sided_pair():
    # Only a call traded at 100/2026-08-21 → no matched pair on flow alone.
    rows = [_flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%",
                        strike="100", expiry="2026-08-21", oi="500")]
    assert _flow_ticker_rows(rows)[0]["iv_spread"] is None
    # Backfilled put counterpart (settlement IV 40) completes the pair → 60 − 40.
    backfill = {"X": [{"opt_type": "put", "strike": 100.0, "expiry": "2026-08-21",
                       "iv": 40.0, "oi": 500.0, "vol": None}]}
    r = _flow_ticker_rows(rows, backfill)[0]
    assert r["iv_spread"] == pytest.approx(20.0)


def test_counterpart_iv_does_not_override_traded_leg():
    # Both legs traded (real spread 20). A stray backfill for the put leg must not
    # replace the real settlement IV — first-seen (the traded leg) wins.
    rows = [
        _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%",
                    strike="100", expiry="2026-08-21", oi="500"),
        _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="40%",
                    strike="100", expiry="2026-08-21", oi="500"),
    ]
    backfill = {"X": [{"opt_type": "put", "strike": 100.0, "expiry": "2026-08-21",
                       "iv": 10.0, "oi": 999.0, "vol": None}]}
    assert _flow_ticker_rows(rows, backfill)[0]["iv_spread"] == pytest.approx(20.0)


def test_counterpart_iv_fills_skew_band():
    # ATM call only (no OTM put in band) → no skew on flow alone.
    rows = [_flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="30%",
                        strike="100", spot="100")]
    assert _flow_ticker_rows(rows)[0]["iv_skew"] is None
    # Backfilled OTM put (K/S 0.90, IV 55) fills the put band → 55 − 30.
    backfill = {"X": [{"opt_type": "put", "strike": 90.0, "expiry": "2026-08-21",
                       "iv": 55.0, "oi": 100.0, "vol": None}]}
    assert _flow_ticker_rows(rows, backfill)[0]["iv_skew"] == pytest.approx(25.0)


def test_iv_spread_excludes_out_of_bounds_iv():
    # Paper filter (iii): settlement IV outside [3, 200] points drops the leg,
    # so neither an extreme-IV pair nor a sub-minimum one forms.
    for bad_iv in ("331%", "2.5%"):
        rows = [
            _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv=bad_iv,
                        strike="100", expiry="2026-08-21"),
            _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="40%",
                        strike="100", expiry="2026-08-21"),
        ]
        assert _flow_ticker_rows(rows)[0]["iv_spread"] is None


def test_iv_spread_excludes_zero_oi_leg():
    # Paper filter (v): a leg with no open interest never enters a pair.
    rows = [
        _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%",
                    strike="100", expiry="2026-08-21", oi="0"),
        _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="40%",
                    strike="100", expiry="2026-08-21", oi="500"),
    ]
    assert _flow_ticker_rows(rows)[0]["iv_spread"] is None


def test_iv_spread_excludes_sub_5_dollar_underlying():
    # Paper filter (ii): sub-$5 names are dropped from both measures.
    rows = [
        _flow_row_d("PENNY", "Call", "ask", "100000", delta="0.5", iv="60%",
                    strike="4", spot="4"),
        _flow_row_d("PENNY", "Put", "bid", "100000", delta="-0.5", iv="40%",
                    strike="4", spot="4"),
    ]
    r = _flow_ticker_rows(rows)[0]
    assert r["iv_spread"] is None
    assert r["iv_skew"] is None


def test_iv_spread_excludes_sub_minimum_trade_price():
    # Paper filter (iv): a leg whose trade print is below $0.125 is dropped;
    # a missing/unparseable Trade cell is never a reason to drop.
    call = _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%",
                       strike="100", expiry="2026-08-21")
    put = _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="40%",
                      strike="100", expiry="2026-08-21")
    call["Trade"] = "0.10"
    assert _flow_ticker_rows([call, put])[0]["iv_spread"] is None
    call["Trade"] = "0.13"
    assert _flow_ticker_rows([call, put])[0]["iv_spread"] == pytest.approx(20.0)


def test_counterpart_iv_skipped_for_sub_5_dollar_underlying():
    # Backfilled legs on a known sub-$5 name are dropped wholesale.
    rows = [_flow_row_d("PENNY", "Call", "ask", "100000", delta="0.5", iv="60%",
                        strike="4", spot="4", expiry="2026-08-21")]
    backfill = {"PENNY": [{"opt_type": "put", "strike": 4.0, "expiry": "2026-08-21",
                           "iv": 40.0, "oi": 500.0, "vol": None}]}
    assert _flow_ticker_rows(rows, backfill)[0]["iv_spread"] is None


def test_matched_pair_uses_eod_settlement_iv_when_present():
    # eod_iv (a fraction) is the settlement IV and overrides the intraday snapshot:
    # 0.70/0.30 → 70/30 points → spread 40, not the intraday 60 − 40 = 20.
    call = _flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%",
                       strike="100", expiry="2026-08-21", oi="500")
    put = _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="40%",
                      strike="100", expiry="2026-08-21", oi="500")
    call["eod_iv"], put["eod_iv"] = "0.70", "0.30"
    assert _flow_ticker_rows([call, put])[0]["iv_spread"] == pytest.approx(40.0)


def test_otm_and_iv_columns_render_in_rollup_md():
    rows = [_flow_row_d("X", "Call", "ask", "100000", delta="0.5", iv="60%"),
            _flow_row_d("X", "Put", "bid", "100000", delta="-0.5", iv="40%")]
    out = summarize_flow(rows, "Stocks Flow", top_n=5, raw_n=0)
    for col in ("OTM$", "IVspr", "IVskew"):
        assert col in out


# ---------------------------------------------------------------------------
# Unusual aggregation
# ---------------------------------------------------------------------------

def _un_row(symbol, opt_type, voloi, *, strike="100", dte="14", volume="1000", moneyness="ATM"):
    return {
        "Symbol": symbol, "Type": opt_type, "Strike": strike, "DTE": dte,
        "Volume": volume, "Vol/OI": voloi, "Moneyness": moneyness,
    }


# Unusual rows no longer get their own rollup/table — they feed scoring inline
# (cross-section overlap + Vol/OI strength). `_un_row` is retained as a helper
# for the scoring/voloi tests above; the removed `_unusual_ticker_rows` and
# `summarize_unusual` functions and their tests have been dropped accordingly.


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
    assert "trades per ticker" in out
    assert "AVGO" in out


def test_summarize_flow_includes_pollution_columns():
    rows = [_rich_row("GLD", "Put", "mid", "705000",
                      spot="380", strike="450", delta="-0.95")]
    out = summarize_flow(rows, "ETFs Flow", top_n=5)
    for col in ("Ext$", "Fin%", "ΔNot$", "Hzn"):
        assert col in out
    assert "100%" in out  # GLD row reads as pure financing


# ---------------------------------------------------------------------------
# OI factor measures (ref 03: OIFC/OIFP/CPIR) + breakdown audit CSV
# ---------------------------------------------------------------------------

def _oi_row(symbol, opt_type, side, premium, *, spot, strike, dte, oi_change,
            delta="0.5", size="100", iv="50%", exp=""):
    r = _rich_row(symbol, opt_type, side, premium,
                  spot=spot, strike=strike, delta=delta, dte=dte, size=size, iv=iv)
    r["oi_change"] = oi_change
    r["Expires"] = exp
    return r


def test_oi_factors_none_without_enrichment():
    rows = [_flow_row("AVGO", "Call", "ask", "1000000")]  # no oi_change column
    row = {r["symbol"]: r for r in _flow_ticker_rows(rows)}["AVGO"]
    assert row["oifc"] is None
    assert row["oifp"] is None
    assert row["cpir"] is None
    assert row["cpira"] is None


def test_oifc_weights_by_price_and_p_otm():
    # One call contract: ΔOI=500, price = premium/(size·100) = 250000/(100·100)
    # = $25/share, P(OTM) = 1−|delta| = 1−0.5 = 0.5.
    # OIFC = 500 × 25 × 0.5 = 6250.
    rows = [_oi_row("AVGO", "Call", "ask", "250000",
                    spot="100", strike="110", dte="10", oi_change="500", delta="0.5")]
    row = {r["symbol"]: r for r in _flow_ticker_rows(rows)}["AVGO"]
    assert row["oifc"] == pytest.approx(6250.0)
    assert row["oifp"] == pytest.approx(0.0)
    assert row["cpir"] == 1.0  # all-call OI factor → fully call-skewed


def test_cpir_is_oifc_over_oifc_plus_oifp():
    rows = [
        _oi_row("AVGO", "Call", "ask", "250000", spot="100", strike="110",
                dte="10", oi_change="500", delta="0.5"),
        _oi_row("AVGO", "Put",  "bid", "250000", spot="100", strike="90",
                dte="100", oi_change="500", delta="-0.5"),
    ]
    row = {r["symbol"]: r for r in _flow_ticker_rows(rows)}["AVGO"]
    # Symmetric inputs → OIFC == OIFP → CPIR = 0.5.
    assert row["oifc"] == pytest.approx(row["oifp"])
    assert row["cpir"] == 0.5


def test_oi_change_deduped_per_contract():
    # Three trade rows on the SAME contract (same strike+exp), each carrying the
    # identical oi_change enrich_oi writes onto every row. ΔOI must be counted
    # ONCE, not 3×. price = Σpremium/(Σsize·100) = 300000/(300·100) = $10,
    # P(OTM)=0.5 → OIFC = 500 × 10 × 0.5 = 2500.
    rows = [
        _oi_row("AVGO", "Call", "ask", "100000", spot="100", strike="110",
                dte="10", oi_change="500", delta="0.5", size="100", exp="2026-07-17"),
        _oi_row("AVGO", "Call", "ask", "100000", spot="100", strike="110",
                dte="10", oi_change="500", delta="0.5", size="100", exp="2026-07-17"),
        _oi_row("AVGO", "Call", "ask", "100000", spot="100", strike="110",
                dte="10", oi_change="500", delta="0.5", size="100", exp="2026-07-17"),
    ]
    row = {r["symbol"]: r for r in _flow_ticker_rows(rows)}["AVGO"]
    assert row["oifc"] == pytest.approx(2500.0)


def test_oi_confirm_pct_counts_contracts_not_rows():
    # Two contracts: one opening (ΔOI>0), one closing (ΔOI<0). Three rows on the
    # opening contract must not inflate the confirm rate → 1/2 = 50% (stored as
    # the decimal fraction 0.5, not 50).
    rows = [
        _oi_row("AVGO", "Call", "ask", "100000", spot="100", strike="110",
                dte="10", oi_change="500", exp="2026-07-17"),
        _oi_row("AVGO", "Call", "ask", "100000", spot="100", strike="110",
                dte="10", oi_change="500", exp="2026-07-17"),
        _oi_row("AVGO", "Put",  "bid", "100000", spot="100", strike="90",
                dte="10", oi_change="-300", exp="2026-07-17"),
    ]
    row = {r["symbol"]: r for r in _flow_ticker_rows(rows)}["AVGO"]
    assert row["oi_confirm_pct"] == 0.5
    assert row["oi_n"] == 2


def test_oi_confirm_pct_excludes_flat_oi():
    # One open (+), one close (−), one flat (ΔOI==0). The flat contract is
    # ambiguous, not a failed confirmation, so it drops out of the denominator:
    # confirm = opens / (opens + closes) = 1/2 = 0.5 over oi_n == 2 moving contracts.
    rows = [
        _oi_row("AVGO", "Call", "ask", "100000", spot="100", strike="110",
                dte="10", oi_change="500", exp="2026-07-17"),
        _oi_row("AVGO", "Put",  "bid", "100000", spot="100", strike="90",
                dte="10", oi_change="-300", exp="2026-07-17"),
        _oi_row("AVGO", "Call", "ask", "100000", spot="100", strike="120",
                dte="10", oi_change="0", exp="2026-07-17"),
    ]
    row = {r["symbol"]: r for r in _flow_ticker_rows(rows)}["AVGO"]
    assert row["oi_confirm_pct"] == 0.5
    assert row["oi_n"] == 2


def test_oi_confirm_pct_all_flat_is_none():
    # Every enriched contract is flat → no moving contracts → confirm is None (the
    # name drops out of the ratio rather than reading a misleading 0). OIFC/OIFP
    # stay present (has_oi keys on any-enriched, not moving).
    rows = [
        _oi_row("AVGO", "Call", "ask", "100000", spot="100", strike="110",
                dte="10", oi_change="0", exp="2026-07-17"),
        _oi_row("AVGO", "Put",  "bid", "100000", spot="100", strike="90",
                dte="10", oi_change="0", exp="2026-07-17"),
    ]
    row = {r["symbol"]: r for r in _flow_ticker_rows(rows)}["AVGO"]
    assert row["oi_confirm_pct"] is None
    assert row["oi_n"] == 0
    assert row["oifc"] == 0.0 and row["oifp"] == 0.0


def test_oi_confirm_points_bands_and_gate():
    from lib.flow_summary.core import _oi_confirm_points
    # Neutral when absent or under-sampled — absence is never a penalty.
    assert _oi_confirm_points(None, 10) == 0
    assert _oi_confirm_points(0.9, None) == 0
    assert _oi_confirm_points(0.9, 2) == 0          # oi_n < _OI_CONFIRM_MIN_N (3)
    # Bands, with a sufficient moving-contract sample.
    assert _oi_confirm_points(0.80, 5) == 2
    assert _oi_confirm_points(0.60, 5) == 2         # inclusive lower edge
    assert _oi_confirm_points(0.50, 5) == 1
    assert _oi_confirm_points(0.40, 5) == 1         # inclusive lower edge
    assert _oi_confirm_points(0.30, 5) == -1
    assert _oi_confirm_points(0.25, 5) == -1        # inclusive lower edge
    assert _oi_confirm_points(0.10, 5) == -2
    assert _oi_confirm_points(0.0, 5) == -2


def test_oi_confirm_feeds_conviction_score():
    # Four distinct opening contracts (oi_n=4 ≥ 3, confirm=1.0) → +2; four distinct
    # closing contracts (confirm=0.0) → −2. Verifies the component reaches the score.
    def _contracts(sym, sign):
        return [
            _oi_row(sym, "Call", "ask", "100000", spot="100", strike=str(110 + i),
                    dte="10", oi_change=str(sign * 500), exp="2026-07-17")
            for i in range(4)
        ]
    rollup = _flow_ticker_rows(_contracts("OPENS", 1) + _contracts("CLOSE", -1))
    score_flow_rollup(rollup)
    parts = {r["symbol"]: r["score_parts"]["oi_confirm"] for r in rollup}
    assert parts["OPENS"] == 2
    assert parts["CLOSE"] == -2


def test_oi_breakdown_csv_empty_without_enrichment():
    rollup = build_scored_flow_rollup([_flow_row("AVGO", "Call", "ask", "1000000")])
    assert oi_breakdown_csv([("stocks", rollup)]) == ""


def test_oi_breakdown_csv_reconciles_to_oifc_oifp():
    rows = [
        _oi_row("AVGO", "Call", "ask", "250000", spot="100", strike="110",
                dte="10", oi_change="500", delta="0.5"),
        _oi_row("AVGO", "Put",  "bid", "250000", spot="100", strike="90",
                dte="100", oi_change="400", delta="-0.5"),
    ]
    rollup = build_scored_flow_rollup(rows)
    text = oi_breakdown_csv([("stocks", rollup)])
    parsed = list(csv.DictReader(io.StringIO(text)))
    # Two non-empty (dte, moneyness) cells → two rows, DTE-bucket ordered
    # (≤14 → 14, then 61–180 → 180), using the prompt's horizon convention.
    assert [r["DTEBucket"] for r in parsed] == ["14", "180"]
    assert all(r["Moneyness"] == "OTM" for r in parsed)
    # Per-cell call/put OIF contributions reconcile to the per-ticker OIFC/OIFP.
    call_total = sum(float(r["CallOIF"]) for r in parsed)
    put_total = sum(float(r["PutOIF"]) for r in parsed)
    assert call_total == pytest.approx(float(parsed[0]["OIFC"]))
    assert put_total == pytest.approx(float(parsed[0]["OIFP"]))
    # CPIR repeats and equals OIFC/(OIFC+OIFP).
    cpir = float(parsed[0]["CPIR"])
    assert cpir == pytest.approx(call_total / (call_total + put_total), abs=0.01)
    assert all(r["Section"] == "stocks" and r["Symbol"] == "AVGO" for r in parsed)


# ---------------------------------------------------------------------------
# ticker_metrics() — the recompute seam used by the rollup backfill. Must agree
# cell-for-cell with the OIConfirmPct / CPIR / IVSpread columns of the audit CSV.
# ---------------------------------------------------------------------------

def test_ticker_metrics_matches_flow_rollup_csv():
    rows = [
        _oi_row("AVGO", "Call", "ask", "250000", spot="100", strike="110",
                dte="10", oi_change="500", delta="0.5", iv="60%"),
        _oi_row("AVGO", "Put",  "bid", "250000", spot="100", strike="90",
                dte="100", oi_change="400", delta="-0.5", iv="40%"),
        _oi_row("NVDA", "Call", "ask", "300000", spot="120", strike="130",
                dte="20", oi_change="-200", delta="0.4", iv="55%"),
    ]
    metrics = ticker_metrics(rows)
    # Same source rows through the audit-CSV path → identical formatted strings.
    csv_text = flow_rollup_csv([("stocks", build_scored_flow_rollup(rows))])
    parsed = {r["Symbol"]: r for r in csv.DictReader(io.StringIO(csv_text))}

    assert set(metrics) == set(parsed)
    col = {"oi_confirm_pct": "OIConfirmPct", "cpir": "CPIR", "iv_spread": "IVSpread"}
    for sym, m in metrics.items():
        for key, csv_col in col.items():
            assert str(m[key]) == parsed[sym][csv_col], (sym, key)


def test_ticker_metrics_blank_when_no_enrichment():
    # No oi_change column → OI factors None → blank cells (not "None"/0).
    rows = [_flow_row("AVGO", "Call", "ask", "1000000")]
    m = ticker_metrics(rows)["AVGO"]
    assert m["oi_confirm_pct"] == "" and m["cpir"] == ""
