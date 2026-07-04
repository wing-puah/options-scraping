import logging
from datetime import date

import pytest
import backtest as bt
from lib import barchart_options as bo
from lib.barchart import BarchartSession


# ── price-history JSON feed scraping (BarchartSession helpers) ──────────────────

def test_augment_history_url_lifts_limit_and_adds_bidask():
    feed = ("https://www.barchart.com/proxies/core-api/v1/historical/get"
            "?symbol=GOOGL%7C20260717%7C425.00C"
            "&fields=tradeTime.format(m/d/Y),lastPrice,theoreticalValue"
            "&type=eod&orderBy=tradeTime&orderDir=desc&limit=65&raw=1")
    out = BarchartSession._augment_history_url(feed)
    assert "limit=1000" in out and "limit=65" not in out
    assert "%2CbidPrice%2CaskPrice&type=eod" in out
    # fields value (commas/parens) must survive untouched — no urlencode mangling.
    assert "tradeTime.format(m/d/Y)" in out


def test_reissue_history_url_swaps_symbol_to_page_contract():
    api = ("https://www.barchart.com/proxies/core-api/v1/historical/get"
           "?symbol=GOOGL%7C20260717%7C425.00C"
           "&fields=tradeTime.format(m/d/Y),lastPrice&type=eod&limit=1000&raw=1")
    page = "https://www.barchart.com/stocks/quotes/GSK%7C20260821%7C50.00P/price-history/historical"
    out = BarchartSession._reissue_history_url(api, page)
    assert "symbol=GSK%7C20260821%7C50.00P" in out
    assert "GOOGL" not in out
    # everything else (fields/limit/order) survives untouched
    assert "limit=1000" in out and "type=eod" in out


def test_reissue_history_url_unparseable_page_returns_api_unchanged():
    api = "https://www.barchart.com/proxies/core-api/v1/historical/get?symbol=X%7C1%7C1C"
    assert BarchartSession._reissue_history_url(api, "https://example.com/no-match") == api


def test_augment_history_url_idempotent_on_bidask():
    feed = ("https://www.barchart.com/proxies/core-api/v1/historical/get"
            "?fields=lastPrice,bidPrice,askPrice&type=eod&limit=65")
    out = BarchartSession._augment_history_url(feed)
    assert out.count("bidPrice") == 1  # not duplicated


def test_history_rows_to_csv_matches_legacy_schema():
    rows = [{
        "tradeTime": "06/11/2026",
        "raw": {"tradeTime": "2026-06-11", "openPrice": 0.98, "lastPrice": 1.09,
                "theoreticalValue": 1.08, "bidPrice": 0.9, "askPrice": 1.26,
                "volume": 332, "openInterest": 1588},
    }]
    csv_text = BarchartSession._history_rows_to_csv(rows)
    header, row1 = csv_text.splitlines()[:2]
    assert header.startswith("Time,Open,High,Low,Latest,")
    assert header.endswith(",Bid,Ask")
    # raw dict (ISO date + numeric mark fields) drives the values parse_history_series reads.
    series = bo.parse_history_series(csv_text)
    assert series == [(date(2026, 6, 11), (0.9 + 1.26) / 2)]


# ── classify_play ──────────────────────────────────────────────────────────────

def test_classify_long_call():
    assert bt.classify_play("NVDA — MS | long call | momentum")["structure"] == "long_call"


def test_classify_long_put():
    out = bt.classify_play("SPY — DC | buy puts | hedge")
    assert out["structure"] == "long_put"
    assert out["option_type"] == "Put"


def test_classify_bull_call_spread():
    assert bt.classify_play("AVGO — HP | Bull call spread 185/200 | x")["structure"] == "bull_call_spread"


def test_classify_bear_put_spread():
    assert bt.classify_play("QQQ — RF | bear put spread 460/450 | x")["structure"] == "bear_put_spread"


def test_classify_unsupported_premium_selling():
    assert bt.classify_play("X — | covered call | x")["structure"] == "unsupported"


def test_classify_calendar():
    out = bt.classify_play("buy Jun 20 / Sep 19 500 call calendar")
    assert out["structure"] == "calendar"
    assert out["option_type"] == "Call"
    assert out["strikes"] == [500.0]
    assert out["is_credit"] is False

    out_put = bt.classify_play("sell Jun 20 / Sep 19 490 put calendar")
    assert out_put["structure"] == "calendar"
    assert out_put["option_type"] == "Put"
    assert out_put["is_credit"] is True


def test_classify_diagonal():
    out = bt.classify_play("buy Jun 20 / Sep 19 480/500 call diagonal")
    assert out["structure"] == "diagonal"
    assert out["option_type"] == "Call"
    assert sorted(out["strikes"]) == [480.0, 500.0]
    assert out["is_credit"] is False


def test_classify_straddle():
    out = bt.classify_play("SPY — RANGE | sell straddle 500 Jun 20 | sell vol")
    assert out["structure"] == "straddle"
    assert out["option_type"] == "Call"
    assert out["is_credit"] is True
    assert out["strikes"] == [500.0]


def test_classify_strangle():
    out = bt.classify_play("SPY — RANGE | sell strangle 490/510 Jun 20 | sell vol")
    assert out["structure"] == "strangle"
    assert out["is_credit"] is True
    assert out["strikes"] == [490.0, 510.0]


def test_classify_butterfly():
    out = bt.classify_play("NVDA — BULL | buy call butterfly 480/500/520 Jun 20")
    assert out["structure"] == "butterfly"
    assert out["option_type"] == "Call"
    assert out["is_credit"] is False
    assert out["strikes"] == [480.0, 500.0, 520.0]


def test_classify_condor():
    out = bt.classify_play("SPY — RANGE | buy call condor 480/490/510/520 Jun 20")
    assert out["structure"] == "condor"
    assert out["option_type"] == "Call"
    assert out["is_credit"] is False
    assert out["strikes"] == [480.0, 490.0, 510.0, 520.0]


def test_classify_iron_condor():
    out = bt.classify_play("SPX — RANGE | iron condor | sell premium")
    assert out["structure"] == "iron_condor"
    assert out["is_credit"] is True
    assert out["option_type"] is None


def test_classify_iron_condor_with_4_strikes():
    out = bt.classify_play("SPY — RANGE | iron condor 480/490/510/520 Jun 20")
    assert out["structure"] == "iron_condor"
    assert out["strikes"] == [480.0, 490.0, 510.0, 520.0]


def test_classify_short_put():
    out = bt.classify_play("NVDA — BEAR | short put 220 Jun 20 | sell premium into high IV")
    assert out["structure"] == "short_put"
    assert out["option_type"] == "Put"
    assert out["is_credit"] is True


def test_classify_short_call():
    out = bt.classify_play("SPY — BEAR | sell call 530 Jun 18 | bearish")
    assert out["structure"] == "short_call"
    assert out["option_type"] == "Call"
    assert out["is_credit"] is True


def test_classify_bear_call_spread():
    out = bt.classify_play("SPY — BEAR | bear call spread 510/520 Jun 18 | fade the rally")
    assert out["structure"] == "bear_call_spread"
    assert out["option_type"] == "Call"
    assert out["strikes"] == [510.0, 520.0]
    assert out["is_credit"] is True


def test_classify_bull_put_spread():
    out = bt.classify_play("AAPL — BULL | bull put spread 190/185 Jun 18 | support hold")
    assert out["structure"] == "bull_put_spread"
    assert out["option_type"] == "Put"
    assert out["strikes"] == [190.0, 185.0]
    assert out["is_credit"] is True


def test_classify_existing_debit_carries_is_credit_false():
    assert bt.classify_play("NVDA — bull call spread 250/260")["is_credit"] is False
    assert bt.classify_play("SPY — buy puts 500")["is_credit"] is False


def test_classify_straddle_call_and_put():
    # "call and put" in straddle text — straddle is now supported.
    assert bt.classify_play("X — straddle: call and put")["structure"] == "straddle"


def test_classify_empty():
    assert bt.classify_play("")["structure"] == "unsupported"


# ── strike extraction ───────────────────────────────────────────────────────────

def test_extract_strikes_spread():
    assert bt._extract_strikes("Bull call spread 485/510 Jun 18") == [485.0, 510.0]


def test_extract_strikes_decimal_spread():
    assert bt._extract_strikes("Bull call spread 107.5/115 June 18") == [107.5, 115.0]


def test_extract_strikes_single_long():
    assert bt._extract_strikes("Long calls 225 June 26") == [225.0]


def test_extract_strikes_bear_put_long_is_higher_first():
    assert bt._extract_strikes("Bear put spread 600/580 Jun 18") == [600.0, 580.0]


def test_classify_carries_strikes():
    out = bt.classify_play("INTC — RF | Bull call spread 107.5/115 June 18")
    assert out["structure"] == "bull_call_spread"
    assert out["strikes"] == [107.5, 115.0]


# ── Expires (ISO datetime) parsing ──────────────────────────────────────────────

def test_parse_expiration_iso_datetime():
    assert bt._parse_expiration("2026-06-18T16:30:00-05:00") == date(2026, 6, 18)


def test_parse_expiration_bare_date():
    assert bt._parse_expiration("2026-08-21") == date(2026, 8, 21)


def test_parse_expiration_fallback():
    fb = date(2026, 1, 1)
    assert bt._parse_expiration("nonsense", fb) == fb


# ── field parsing ──────────────────────────────────────────────────────────────

def test_opt_price_reads_trade_column():
    assert bt._opt_price({"Trade": "8.60"}) == 8.60


def test_opt_price_handles_currency():
    assert bt._opt_price({"Trade": "$1,234.50"}) == 1234.50


def test_opt_price_none_when_missing():
    assert bt._opt_price({"Price~": "248.76"}) is None  # underlying, not option price


def test_row_iv_percent_to_fraction():
    assert bt._row_iv({"IV": "71.8%"}) == 0.718


# ── entry matching ─────────────────────────────────────────────────────────────

def _flow_row(sym, typ, strike, trade, premium, side="Ask"):
    return {"Symbol": sym, "Type": typ, "Strike": strike, "Trade": trade,
            "Premium": premium, "Side": side, "Expiration Date": "2026-07-17",
            "DTE": "30", "IV": "50", "Price~": "250", "Delta": "0.45"}


def test_match_entry_picks_largest_premium():
    cand = {"ticker": "NVDA"}
    rows = [
        _flow_row("NVDA", "Call", "250", "5.0", "500000"),
        _flow_row("NVDA", "Call", "260", "3.0", "900000"),  # largest premium
        _flow_row("AAPL", "Call", "200", "9.0", "999999"),  # wrong symbol
    ]
    best = bt._match_entry(cand, "Call", rows, "any")
    assert best["Strike"] == "260"


def test_match_entry_respects_type():
    cand = {"ticker": "NVDA"}
    rows = [_flow_row("NVDA", "Put", "250", "5.0", "500000")]
    assert bt._match_entry(cand, "Call", rows, "any") is None


def test_match_entry_respects_side():
    cand = {"ticker": "NVDA"}
    rows = [_flow_row("NVDA", "Call", "250", "5.0", "500000", side="Bid")]
    assert bt._match_entry(cand, "Call", rows, "Ask") is None
    assert bt._match_entry(cand, "Call", rows, "any") is not None


def test_match_entry_picks_closest_to_play_strike():
    cand = {"ticker": "INTC"}
    rows = [
        _flow_row("INTC", "Call", "110", "9.0", "9000000"),   # biggest premium, wrong strike
        _flow_row("INTC", "Call", "107.5", "3.0", "100000"),  # the play's long strike
    ]
    best = bt._match_entry(cand, "Call", rows, "any", long_strike=107.5)
    assert best["Strike"] == "107.5"


def test_extract_expiration_month_day():
    assert bt._extract_expiration("Bull call spread 300/340 Jun 18", date(2026, 6, 3)) == date(2026, 6, 18)
    assert bt._extract_expiration("Long calls 225 June 26", date(2026, 6, 2)) == date(2026, 6, 26)


def test_extract_expiration_rolls_to_next_year():
    # 'Jan 15' referenced from June → next January.
    assert bt._extract_expiration("calls Jan 15", date(2026, 6, 2)) == date(2027, 1, 15)


def test_match_entry_prefers_named_expiry_on_equal_strike():
    cand = {"ticker": "MRVL"}
    near = _flow_row("MRVL", "Call", "300", "9.0", "100000")
    far = _flow_row("MRVL", "Call", "300", "9.0", "9000000")  # bigger premium, far expiry
    near["Expires"] = "2026-06-18T16:30:00-05:00"
    far["Expires"] = "2028-06-16T16:30:00-05:00"
    best = bt._match_entry(cand, "Call", [far, near], "any",
                           long_strike=300.0, target_exp=date(2026, 6, 18))
    assert best["Expires"].startswith("2026-06-18")


def test_match_entry_skips_zero_iv_junk():
    cand = {"ticker": "NVDA"}
    junk = _flow_row("NVDA", "Call", "0.5", "215", "136000000")
    junk["IV"] = "0.00%"
    real = _flow_row("NVDA", "Call", "225", "8.0", "500000")
    best = bt._match_entry(cand, "Call", [junk, real], "any")
    assert best["Strike"] == "225"


# ── reappearance lookup ────────────────────────────────────────────────────────

def test_reappearance_returns_first_on_or_after_checkpoint():
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    index = {key: [(date(2026, 6, 1), 5.0), (date(2026, 6, 4), 7.5), (date(2026, 6, 10), 9.0)]}
    assert bt._reappearance_price(index, key, date(2026, 6, 4), date(2026, 7, 17)) == 7.5
    assert bt._reappearance_price(index, key, date(2026, 6, 5), date(2026, 7, 17)) == 9.0


def test_reappearance_none_after_expiry():
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    index = {key: [(date(2026, 8, 1), 9.0)]}
    assert bt._reappearance_price(index, key, date(2026, 6, 5), date(2026, 7, 17)) is None


def test_reappearance_none_when_unknown():
    assert bt._reappearance_price({}, ("X", "Call", 1.0, "x"), date(2026, 1, 1), None) is None


# ── simulate (real entry + real exit, no network via injected price_fn) ─────────

def _legs(*specs):
    """Build a leg list from ('+1', 'NVDA', '2026-07-17', 250, 'Call') tuples."""
    return [bt.Leg(int(q), t, date.fromisoformat(e), float(k), ot)
            for (q, t, e, k, ot) in specs]


def test_simulate_barchart_entry_and_real_exit():
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": "BULL + L-VOL"}
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "8.0", "800000")
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    barchart_series = {key: [(date(2026, 6, 1), 8.0)]}  # entry priced from Barchart EOD
    # Contract reappears at +60% on day 3. exit_sources excludes barchart so the
    # single entry-day snap doesn't carry forward and win the exit too.
    contract_index = {key: [(date(2026, 6, 4), 12.8)]}
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "exit_sources": ["reappearance"]}

    res = bt._simulate(cand, legs, entry_row, contract_index, barchart_series, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: None)

    assert res["entry_option_price"] == 8.0
    assert res["entry_source"] == "barchart"
    assert res["legs"] == "NVDA:2026-07-17:250:C +1"
    # Per-leg raw breakdown is line-aligned with legs and validates the net.
    assert res["entry_leg_detail"].startswith("NVDA:2026-07-17:250:C +1  px=8")
    assert res["realized_pnl_pct"] == 0.6
    assert res["exit_reason"] == "profit_target"
    assert res["pct_real_days"] == 1.0   # reappearance, not Black-Scholes


def test_simulate_barchart_takes_precedence_over_reappearance():
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "8.0", "800000")
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    # Reappearance says 12.8 (+60%); Barchart says 16.0 (+100%) and must win.
    contract_index = {key: [(date(2026, 6, 4), 12.8)]}
    barchart_series = {key: [(date(2026, 6, 1), 8.0), (date(2026, 6, 4), 16.0)]}
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "exit_sources": ["barchart", "reappearance", "bs"], "contracts": 1}

    res = bt._simulate(cand, legs, entry_row, contract_index, barchart_series, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: None)

    # Barchart's 16.0 (+100%) must win over reappearance's 12.8 (+60%).
    assert res["realized_pnl_pct"] == 1.0
    assert res["exit_reason"] == "profit_target"


def test_simulate_falls_back_to_bs_when_no_reappearance():
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "8.0", "800000")
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    barchart_series = {key: [(date(2026, 6, 1), 8.0)]}  # entry priced from Barchart EOD
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "exit_sources": ["bs"]}

    # No contract index and exit forced to BS → underlying jumps to 300 (deep ITM).
    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: 300.0)

    assert res["pct_real_days"] == 0.0   # all marks are Black-Scholes (0/n = 0)
    assert res["realized_pnl_pct"] > 0


def test_simulate_rejects_degenerate_spread():
    # Two legs on the SAME contract (long 340 / short 340) net to zero → empty
    # position after merge → not simulable, returns {}.
    cand = {"ticker": "MRVL", "signal_date": date(2026, 6, 1), "play": "bull call spread",
            "market_regime": ""}
    legs = _legs(("+1", "MRVL", "2026-07-17", 340, "Call"),
                 ("-1", "MRVL", "2026-07-17", 340, "Call"))
    entry_row = _flow_row("MRVL", "Call", "340", "5.0", "100000")
    res = bt._simulate(cand, legs, entry_row, {}, {}, {"exit_days": [3]},
                       structure="bull_call_spread", price_fn=lambda tk, dt: None)
    assert res == {}


def test_simulate_spread_prices_short_leg_from_barchart():
    # Bull call spread 300/320: both legs have real Barchart history, so the short
    # leg is netted from real data (not BS) at both entry and exit.
    cand = {"ticker": "MRVL", "signal_date": date(2026, 6, 1),
            "play": "bull call spread 300/320", "market_regime": ""}
    legs = _legs(("+1", "MRVL", "2026-07-17", 300, "Call"),
                 ("-1", "MRVL", "2026-07-17", 320, "Call"))
    entry_row = _flow_row("MRVL", "Call", "300", "10.0", "800000")
    long_key = ("MRVL", "Call", 300.0, "2026-07-17")
    short_key = ("MRVL", "Call", 320.0, "2026-07-17")
    barchart_series = {
        long_key:  [(date(2026, 6, 1), 10.0), (date(2026, 6, 4), 16.0)],
        short_key: [(date(2026, 6, 1), 4.0),  (date(2026, 6, 4), 6.0)],
    }
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0, "contracts": 1}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="bull_call_spread", price_fn=lambda tk, dt: None)

    # Entry priced from Barchart EOD for both legs (long 10, short 4) → debit 6.
    assert res["entry_option_price"] == 6.0
    assert res["entry_source"] == "barchart+barchart"
    # Exit both legs real Barchart: 16 - 6 = 10 vs debit 6 → +66.7%.
    assert abs(res["realized_pnl_pct"] - 0.6667) < 0.0001
    assert res["exit_reason"] == "profit_target"
    assert res["pct_real_days"] == 1.0


def test_simulate_spread_short_leg_falls_back_to_bs():
    # Only the long leg has Barchart history; the short strike never traded, so the
    # short leg is modelled with Black-Scholes (tagged +bs).
    cand = {"ticker": "MRVL", "signal_date": date(2026, 6, 1),
            "play": "bull call spread 300/320", "market_regime": ""}
    legs = _legs(("+1", "MRVL", "2026-07-17", 300, "Call"),
                 ("-1", "MRVL", "2026-07-17", 320, "Call"))
    entry_row = _flow_row("MRVL", "Call", "300", "10.0", "800000")
    long_key = ("MRVL", "Call", 300.0, "2026-07-17")
    barchart_series = {long_key: [(date(2026, 6, 1), 10.0), (date(2026, 6, 4), 16.0)]}
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0, "contracts": 1,
               "entry_sources": ["barchart", "bs"]}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="bull_call_spread", price_fn=lambda tk, dt: 305.0)

    assert res["entry_source"] == "barchart+bs"   # short leg modelled with BS at entry
    assert "MRVL:2026-07-17:320:C -1" in res["legs"]


def test_simulate_daily_path_realized_exit_and_excursions():
    # Long call, entry 10. Daily Barchart marks dip then rip past the target.
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "10.0", "800000")
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    barchart_series = {key: [
        (date(2026, 6, 1), 10.0),   # entry
        (date(2026, 6, 2), 8.0),    # -20%
        (date(2026, 6, 3), 11.0),   # +10%
        (date(2026, 6, 4), 16.0),   # +60% → first profit_target trigger
        (date(2026, 6, 5), 20.0),   # +100% (the true MFE, after the exit)
    ]}
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: None)

    assert res["realized_pnl_pct"] == 0.6            # frozen at the first +50% day
    assert res["exit_reason"] == "profit_target"
    assert res["days_held"] == 3                     # 06-02,06-03,06-04 → 3 trading days
    assert res["mfe_pct"] == 1.0                     # excursion is over the WHOLE path
    assert res["mfe_abs"] == 1000.0                  # 1.0 × 10 × 100 × 1 contract
    assert res["mae_pct"] == -0.2
    assert res["mae_abs"] == -200.0                  # −0.2 × 10 × 100 × 1 contract
    assert res["mfe_day"] == 4 and res["mae_day"] == 1
    assert res["pct_real_days"] == 1.0
    assert res["daily_price_csv"].startswith("8.0000,11.0000,16.0000,20.0000")
    # daily_pnl_csv = per-contract $ P&L, same grid: (mark − entry 10) × 100.
    assert res["daily_pnl_csv"].startswith("-200.00,100.00,600.00,1000.00")
    assert (len(res["daily_pnl_csv"].split(","))
            == len(res["daily_price_csv"].split(",")))


def test_summarize_path_daily_pnl_is_per_contract_not_position_scaled():
    # daily_pnl_csv is per SINGLE contract: (mark − entry 10) × 100, independent
    # of `contracts` (=3 here). realized_pnl_abs, by contrast, DOES scale ×3.
    # A blank (unpriceable) day stays blank and keeps the grid aligned.
    gm = [(date(2026, 6, 2), 1, 8.0, "barchart"),
          (date(2026, 6, 3), 2, 11.0, "barchart"),
          (date(2026, 6, 4), 3, None, None),
          (date(2026, 6, 5), 4, 20.0, "barchart")]
    out = bt._summarize_path(gm, 10.0, 0.5, 1.0, 3, True)
    assert out["daily_pnl_csv"] == "-200.00,100.00,,1000.00"
    assert (len(out["daily_pnl_csv"].split(","))
            == len(out["daily_price_csv"].split(",")))
    assert out["realized_pnl_abs"] == 3000.0  # 1.0 × 10 × 100 × 3 contracts (scaled)


def test_simulate_path_cap_open_when_dte_exceeds_cap():
    # Flat price, never triggers; DTE 200 > cap 120 → held open at the cap.
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = _legs(("+1", "NVDA", "2026-12-18", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "10.0", "800000")
    entry_row["DTE"] = "200"
    entry_row["Expiration Date"] = "2026-12-18"
    key = ("NVDA", "Call", 250.0, "2026-12-18")
    barchart_series = {key: [(date(2026, 6, 1), 10.0), (date(2026, 6, 2), 10.0)]}  # carries forward flat
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "exit_sources": ["barchart"], "path_cap_days": 120}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: None)

    assert res["exit_reason"] == "cap_open"
    assert res["realized_pnl_pct"] == 0.0  # flat path, decimal 0 = 0%


def test_simulate_path_expired_when_dte_within_cap():
    # Flat price, never triggers; DTE 10 <= cap → path runs to expiry → 'expired'.
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = _legs(("+1", "NVDA", "2026-06-11", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "10.0", "800000")
    entry_row["DTE"] = "10"
    entry_row["Expiration Date"] = "2026-06-11"
    key = ("NVDA", "Call", 250.0, "2026-06-11")
    barchart_series = {key: [(date(2026, 6, 1), 10.0), (date(2026, 6, 2), 10.0)]}
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "exit_sources": ["barchart"], "path_cap_days": 120}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: None)

    assert res["exit_reason"] == "expired"


def test_simulate_no_data_when_no_exit_available():
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "8.0", "800000")
    sim_cfg = {"exit_days": [3], "entry_sources": ["bs"]}

    # Entry priced via BS (underlying only available on signal_date); no exit
    # source has any data for later days → path has no priced marks → "no_data".
    res = bt._simulate(cand, legs, entry_row, {}, {}, sim_cfg,
                       structure="long_call",
                       price_fn=lambda tk, dt: 300.0 if dt == date(2026, 6, 1) else None)
    assert res["exit_reason"] == "no_data"


# ── barchart_options module ─────────────────────────────────────────────────────

def test_parse_analysis_date_iso_and_locale():
    assert bt._parse_analysis_date("2026-06-02") == date(2026, 6, 2)
    assert bt._parse_analysis_date("02/06/2026") == date(2026, 6, 2)   # DD/MM/YYYY (Sheets locale)
    assert bt._parse_analysis_date("") is None
    assert bt._parse_analysis_date("garbage") is None


def test_option_history_url_matches_barchart_format():
    url = bo.option_history_url("CDNS", date(2026, 8, 21), 370.0, "Put")
    assert url == ("https://www.barchart.com/stocks/quotes/"
                   "CDNS%7C20260821%7C370.00P/price-history/historical")


def test_option_history_url_call():
    url = bo.option_history_url("nvda", date(2026, 7, 17), 250.0, "Call")
    assert "NVDA%7C20260717%7C250.00C" in url


# Real Barchart header captured from a live download (note stale Latest on 0-volume days).
_SAMPLE = (
    'Time,Open,High,Low,Latest,Change,%Change,Volume,"Open Int",IV,Delta,Gamma,'
    "Theta,Vega,Rho,Theo,Price~,Bid,Ask\n"
    "2026-06-04,22.1,22.1,21.91,21.91,0,0.00%,10001,207,51.43%,-0.30,0.003,-0.20,0.65,-0.26,21.0,404.17,20,22\n"
    "2026-06-02,21.91,21.91,21.91,21.91,0,0.00%,0,207,55.56%,-0.27,0.003,-0.21,0.64,-0.25,21.0,416.39,18.7,22.5\n"
    '"Downloaded from Barchart.com as of 06-04-2026 09:16am CDT"\n'
)


def test_parse_history_series_marks_to_mid():
    series = bo.parse_history_series(_SAMPLE)
    assert len(series) == 2                      # footer dropped
    assert series[0][0] == date(2026, 6, 2)      # sorted ascending
    assert series[0][1] == (18.7 + 22.5) / 2     # mid, not the stale Latest=21.91
    assert series[1][1] == (20 + 22) / 2


def test_parse_history_series_skips_non_date_rows():
    assert bo.parse_history_series("Time,Bid,Ask\nnot-a-date,1,2\n") == []


# ── credit structure simulation ────────────────────────────────────────────────

def test_simulate_short_put_profit_when_option_decays():
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "short put 220",
            "market_regime": "RANGE + L-VOL"}
    legs = _legs(("-1", "NVDA", "2026-07-17", 220, "Put"))
    entry_row = _flow_row("NVDA", "Put", "220", "5.0", "500000")
    key = ("NVDA", "Put", 220.0, "2026-07-17")
    # Reappearance at entry (day 0) too, since entry pricing has no Barchart data.
    contract_index = {key: [(date(2026, 6, 1), 5.0), (date(2026, 6, 4), 2.0)]}  # option decays
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "entry_sources": ["reappearance"],
               "exit_sources": ["reappearance"]}

    res = bt._simulate(cand, legs, entry_row, contract_index, {}, sim_cfg,
                       structure="short_put", price_fn=lambda tk, dt: None)

    assert res["entry_option_price"] == -5.0   # signed: net credit received
    assert res["entry_source"] == "real"
    assert abs(res["realized_pnl_pct"] - 0.6) < 0.001   # (−2 − (−5)) / 5 = 60%
    assert res["exit_reason"] == "profit_target"


def test_simulate_short_put_loss_when_option_appreciates():
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "short put 220",
            "market_regime": ""}
    legs = _legs(("-1", "NVDA", "2026-07-17", 220, "Put"))
    entry_row = _flow_row("NVDA", "Put", "220", "5.0", "500000")
    key = ("NVDA", "Put", 220.0, "2026-07-17")
    contract_index = {key: [(date(2026, 6, 1), 5.0), (date(2026, 6, 4), 12.0)]}  # option goes against us
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "entry_sources": ["reappearance"],
               "exit_sources": ["reappearance"]}

    res = bt._simulate(cand, legs, entry_row, contract_index, {}, sim_cfg,
                       structure="short_put", price_fn=lambda tk, dt: None)

    assert abs(res["realized_pnl_pct"] - (-1.4)) < 0.001  # (−12 − (−5)) / 5 = -140%
    assert res["exit_reason"] == "stop_loss"


def test_simulate_bull_put_spread_credit():
    # Bull put spread: sold 490P / bought 480P.  Both legs have Barchart history.
    cand = {"ticker": "SPY", "signal_date": date(2026, 6, 1),
            "play": "bull put spread 490/480", "market_regime": "RANGE + L-VOL"}
    # Sold 490P (anchor, short) / bought 480P (long hedge).
    legs = _legs(("-1", "SPY", "2026-07-17", 490, "Put"),
                 ("+1", "SPY", "2026-07-17", 480, "Put"))
    entry_row = _flow_row("SPY", "Put", "490", "4.0", "400000")
    sold_key  = ("SPY", "Put", 490.0, "2026-07-17")
    hedge_key = ("SPY", "Put", 480.0, "2026-07-17")
    barchart_series = {
        sold_key:  [(date(2026, 6, 1), 4.0), (date(2026, 6, 4), 1.5)],  # sold leg decays
        hedge_key: [(date(2026, 6, 1), 1.5), (date(2026, 6, 4), 0.5)],  # hedge decays too
    }
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0, "contracts": 1}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="bull_put_spread", price_fn=lambda tk, dt: None)

    # Entry credit: −sold (4) + hedge (1.5), both from Barchart = −2.5 (signed)
    assert res["entry_option_price"] == -2.5
    assert res["entry_source"] == "barchart+barchart"
    # Exit net: −1.5 + 0.5 = −1.0  →  P&L = (−1.0 − (−2.5)) / 2.5 = 60%
    assert abs(res["realized_pnl_pct"] - 0.6) < 0.001
    assert res["exit_reason"] == "profit_target"


def test_simulate_iron_condor_profit_in_range():
    # Underlying stays at centre; all legs decay → credit mostly kept.
    cand = {"ticker": "SPY", "signal_date": date(2026, 6, 1),
            "play": "iron condor 480/490/510/520 Jun 20", "market_regime": "RANGE + H-VOL"}
    legs = bt.iron_condor_legs("SPY", date(2026, 7, 17), 480.0, 490.0, 510.0, 520.0)
    entry_row = _flow_row("SPY", "Put", "490", "3.0", "300000")
    entry_row["Price~"] = "500"
    entry_row["Trade"] = ""   # no real anchor — all 4 legs priced by BS consistently

    sim_cfg = {"profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "spread_width_pct": 0.02, "risk_free_rate": 0.05,
               "entry_sources": ["bs"], "exit_sources": ["bs"]}

    # Underlying stays at 500 — well inside the condor wings.
    res = bt._simulate(cand, legs, entry_row, {}, {}, sim_cfg,
                       structure="iron_condor", anchor_idx=1,
                       price_fn=lambda tk, dt: 500.0)

    assert res["structure"] == "iron_condor"
    assert res["entry_source"] == "bs+bs+bs+bs"   # all four legs modelled
    assert res["entry_option_price"] < 0           # signed: net credit
    assert res["realized_pnl_pct"] > 0             # premium decays → profit


# ── leg parsing / formatting / mapping ───────────────────────────────────────────

def test_parse_legs_canonical_and_legacy():
    # Canonical (qty last) and legacy (qty first) forms both parse identically.
    expected = [
        bt.Leg(3, "AMD", date(2025, 10, 16), 130.0, "Call"),
        bt.Leg(-2, "AMD", date(2025, 9, 15), 140.0, "Put"),
    ]
    assert bt.parse_legs("AMD:2025-10-16:130:C +3\nAMD:2025-09-15:140:P -2") == expected
    assert bt.parse_legs("+3 AMD:2025-10-16:130:C\n-2 AMD:2025-09-15:140:P") == expected


def test_parse_legs_ignores_prose_and_returns_none_when_absent():
    assert bt.parse_legs("Bull call spread 185/200 Jun 18") is None
    # A leg-string can sit alongside prose; only the leg line is parsed.
    legs = bt.parse_legs("calendar idea:\nSPY:2026-09-18:500:C +1\nrationale: term structure")
    assert legs == [bt.Leg(1, "SPY", date(2026, 9, 18), 500.0, "Call")]


def test_format_legs_round_trip():
    # format_legs emits the canonical (qty last) form, which round-trips.
    s = "AMD:2025-10-16:130:C +3\nAMD:2025-09-15:140:P -2"
    assert bt.format_legs(bt.parse_legs(s)) == s


def test_legs_from_structure_debit_and_credit():
    # Debit vertical: long anchor at K, short contra at K_short.
    debit = bt.legs_from_structure("bull_call_spread", "Call", "NVDA",
                                   date(2026, 7, 17), 300.0, 320.0, False)
    assert debit == [bt.Leg(1, "NVDA", date(2026, 7, 17), 300.0, "Call"),
                     bt.Leg(-1, "NVDA", date(2026, 7, 17), 320.0, "Call")]
    # Credit vertical: short anchor at K, long contra at K_short.
    credit = bt.legs_from_structure("bull_put_spread", "Put", "SPY",
                                    date(2026, 7, 17), 490.0, 480.0, True)
    assert credit == [bt.Leg(-1, "SPY", date(2026, 7, 17), 490.0, "Put"),
                      bt.Leg(1, "SPY", date(2026, 7, 17), 480.0, "Put")]


def test_classify_play_recognises_explicit_legs_over_keyword():
    # Explicit leg-string short-circuits freeform classification.
    out = bt.classify_play("calendar spread\n+1 AMD:2026-10-16:130:C\n-1 AMD:2026-07-17:130:C")
    assert out["structure"] == "explicit_legs"
    assert len(out["legs"]) == 2


# ── defined-risk value bounds ──────────────────────────────────────────────────

def test_defined_risk_bounds_debit_spread():
    legs = _legs(("+1", "HYG", "2026-09-20", 77, "Put"),
                 ("-1", "HYG", "2026-09-20", 74, "Put"))
    assert bt._defined_risk_bounds(legs) == (0.0, 3.0)


def test_defined_risk_bounds_credit_spread():
    legs = _legs(("-1", "SPY", "2026-09-20", 520, "Call"),
                 ("+1", "SPY", "2026-09-20", 530, "Call"))
    assert bt._defined_risk_bounds(legs) == (-10.0, 0.0)


def test_defined_risk_bounds_none_for_ratio_spread():
    # +1 / -2 has a net call qty of -1 — unbounded as S→∞.
    legs = _legs(("+1", "AMD", "2026-07-17", 130, "Call"),
                 ("-2", "AMD", "2026-07-17", 140, "Call"))
    assert bt._defined_risk_bounds(legs) is None


def test_defined_risk_bounds_none_for_single_leg():
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    assert bt._defined_risk_bounds(legs) is None


def test_defined_risk_bounds_long_call_butterfly():
    # +1/-2/+1 call fly: value bounded in [0, wing width = 10].
    legs = _legs(("+1", "AMD", "2026-07-17", 120, "Call"),
                 ("-2", "AMD", "2026-07-17", 130, "Call"),
                 ("+1", "AMD", "2026-07-17", 140, "Call"))
    assert bt._defined_risk_bounds(legs) == (0.0, 10.0)


def test_defined_risk_bounds_iron_condor():
    # Explicit IC: long put wing / short put / short call / long call wing.
    legs = _legs(("+1", "SPY", "2026-07-17", 480, "Put"),
                 ("-1", "SPY", "2026-07-17", 490, "Put"),
                 ("-1", "SPY", "2026-07-17", 510, "Call"),
                 ("+1", "SPY", "2026-07-17", 520, "Call"))
    # Worst case at either wing = -(10 width); best (between shorts) = 0.
    assert bt._defined_risk_bounds(legs) == (-10.0, 0.0)


def test_defined_risk_bounds_none_for_calendar():
    # Different expirations → not a single-expiration intrinsic payoff.
    legs = _legs(("-1", "SPY", "2026-06-19", 500, "Call"),
                 ("+1", "SPY", "2026-09-18", 500, "Call"))
    assert bt._defined_risk_bounds(legs) is None


def test_defined_risk_bounds_none_for_extra_naked_call():
    # Net call qty +1 (long fly plus an extra long call) → unbounded above.
    legs = _legs(("+1", "AMD", "2026-07-17", 120, "Call"),
                 ("-2", "AMD", "2026-07-17", 130, "Call"),
                 ("+2", "AMD", "2026-07-17", 140, "Call"))
    assert bt._defined_risk_bounds(legs) is None


def test_simulate_debit_spread_impossible_mark_clamped_to_max_loss():
    # Reproduces the HYG 2024-08-13 case: short leg priced higher than long on
    # the first daily mark, producing an impossible negative net. Must clamp to 0
    # so realized P&L cannot exceed 100% loss (the debit paid).
    cand = {"ticker": "HYG", "signal_date": date(2026, 6, 1),
            "play": "bear put spread 77/74", "market_regime": ""}
    legs = _legs(("+1", "HYG", "2026-09-20", 77, "Put"),
                 ("-1", "HYG", "2026-09-20", 74, "Put"))
    entry_row = {**_flow_row("HYG", "Put", "77", "0.245", "1000"),
                 "DTE": "38", "IV": "8.87%", "Price~": "78.38"}
    long_key  = ("HYG", "Put", 77.0, "2026-09-20")
    short_key = ("HYG", "Put", 74.0, "2026-09-20")
    # Day 1: long drops to 0.05, short jumps to 0.31 (stale scrape) → raw net −0.26.
    barchart_series = {
        long_key:  [(date(2026, 6, 1), 0.245), (date(2026, 6, 2), 0.05)],
        short_key: [(date(2026, 6, 1), 0.19),  (date(2026, 6, 2), 0.31)],
    }
    sim_cfg = {"profit_target": 5.0, "stop_loss": 1.0, "contracts": 1,
               "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="bear_put_spread", price_fn=lambda tk, dt: None)

    assert res["entry_option_price"] == pytest.approx(0.055, abs=1e-9)
    assert res["realized_pnl_pct"] == pytest.approx(-1.0)   # clamped: max loss = debit
    assert res["mae_pct"] == pytest.approx(-1.0)             # never exceeds 100% loss


def test_simulate_credit_spread_impossible_mark_clamped_to_max_gain():
    # Bear call spread (credit). If per-leg prices produce net > 0 (impossible for a
    # credit spread), the mark is clamped to 0 — max gain is the premium received.
    cand = {"ticker": "SPY", "signal_date": date(2026, 6, 1),
            "play": "bear call spread 520/530", "market_regime": ""}
    legs = _legs(("-1", "SPY", "2026-09-20", 520, "Call"),
                 ("+1", "SPY", "2026-09-20", 530, "Call"))
    # Sold 520C at 2.0, bought 530C at 1.5 → net credit −0.5.
    entry_row = {**_flow_row("SPY", "Call", "520", "2.0", "1000"),
                 "DTE": "100", "IV": "20%", "Price~": "510"}
    sold_key  = ("SPY", "Call", 520.0, "2026-09-20")
    hedge_key = ("SPY", "Call", 530.0, "2026-09-20")
    # Day 1: sold leg collapses but hedge stays high → raw net +0.40 (impossible).
    barchart_series = {
        sold_key:  [(date(2026, 6, 1), 2.0), (date(2026, 6, 2), 0.10)],
        hedge_key: [(date(2026, 6, 1), 1.5), (date(2026, 6, 2), 0.50)],
    }
    sim_cfg = {"profit_target": 5.0, "stop_loss": 5.0, "contracts": 1,
               "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="bear_call_spread", price_fn=lambda tk, dt: None)

    assert res["entry_option_price"] == pytest.approx(-0.5, abs=1e-9)
    # Clamped to 0 → P&L = (0 − (−0.5)) / 0.5 = 100% (max gain, not phantom beyond).
    assert res["mfe_pct"] == pytest.approx(1.0)


def test_simulate_ratio_spread_not_clamped():
    # +1/−2 is NOT a 1:1 vertical: no clamping, so a mark outside [0, spread_width]
    # is recorded as-is. Here the short leg rips → net goes deeply negative.
    cand = {"ticker": "AMD", "signal_date": date(2026, 6, 1),
            "play": "ratio spread", "market_regime": ""}
    legs = _legs(("+1", "AMD", "2026-07-17", 130, "Call"),
                 ("-2", "AMD", "2026-07-17", 140, "Call"))
    entry_row = _flow_row("AMD", "Call", "130", "10.0", "800000")
    k130 = ("AMD", "Call", 130.0, "2026-07-17")
    k140 = ("AMD", "Call", 140.0, "2026-07-17")
    # Entry net: +1×10 − 2×3 = 4. Day 1: +1×8 − 2×9 = −10 (outside [0,10]).
    barchart_series = {
        k130: [(date(2026, 6, 1), 10.0), (date(2026, 6, 2), 8.0)],
        k140: [(date(2026, 6, 1), 3.0),  (date(2026, 6, 2), 9.0)],
    }
    sim_cfg = {"profit_target": 5.0, "stop_loss": 5.0, "contracts": 1,
               "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="explicit_legs", price_fn=lambda tk, dt: None)

    # mae reflects the real (unclamped) net: (−10 − 4) / 4 = −3.5 (−350%).
    assert res["entry_option_price"] == pytest.approx(4.0)
    assert res["mae_pct"] == pytest.approx(-3.5)


# ── multi-leg simulation (ratio + calendar) ─────────────────────────────────────

def test_simulate_ratio_spread_nets_by_quantity():
    # 1x130 long vs 2x140 short — a ratio spread; net by signed qty.
    cand = {"ticker": "AMD", "signal_date": date(2026, 6, 1),
            "play": "ratio", "market_regime": ""}
    legs = _legs(("+1", "AMD", "2026-07-17", 130, "Call"),
                 ("-2", "AMD", "2026-07-17", 140, "Call"))
    entry_row = _flow_row("AMD", "Call", "130", "10.0", "800000")
    k130 = ("AMD", "Call", 130.0, "2026-07-17")
    k140 = ("AMD", "Call", 140.0, "2026-07-17")
    barchart_series = {
        k130: [(date(2026, 6, 1), 10.0), (date(2026, 6, 4), 12.0)],
        k140: [(date(2026, 6, 1), 3.0),  (date(2026, 6, 4), 2.0)],
    }
    sim_cfg = {"profit_target": 5.0, "stop_loss": 5.0, "contracts": 1,
               "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="explicit_legs", price_fn=lambda tk, dt: None)

    # Entry net: +1·10 − 2·3 = 4 (debit).
    assert res["entry_option_price"] == 4.0
    # Exit net: +1·12 − 2·2 = 8 → P&L = (8 − 4)/4 = 100%.
    assert abs(res["realized_pnl_pct"] - 1.0) < 0.001


def test_simulate_calendar_path_bounded_by_near_leg():
    # Calendar: short near leg (expires 2026-06-19), long far leg (2026-09-18).
    cand = {"ticker": "SPY", "signal_date": date(2026, 6, 1),
            "play": "calendar", "market_regime": ""}
    legs = _legs(("-1", "SPY", "2026-06-19", 500, "Call"),
                 ("+1", "SPY", "2026-09-18", 500, "Call"))
    entry_row = _flow_row("SPY", "Call", "500", "5.0", "500000")
    entry_row["Price~"] = "500"
    sim_cfg = {"profit_target": 5.0, "stop_loss": 5.0, "contracts": 1,
               "entry_sources": ["bs"], "exit_sources": ["bs"], "risk_free_rate": 0.05}

    res = bt._simulate(cand, legs, entry_row, {}, {}, sim_cfg,
                       structure="explicit_legs", anchor_idx=1,
                       price_fn=lambda tk, dt: 500.0)

    # The path stops at the NEAR leg's expiry (~18 days), not the far leg's.
    n_days = len([t for t in res["daily_price_csv"].split(",")])
    assert n_days <= 14   # ~13 weekdays in the 18-day near-leg window
    assert res["entry_option_price"] != 0


# ── same-contract merge ─────────────────────────────────────────────────────────

def test_merge_legs_combines_same_contract():
    legs = _legs(("+2", "AMD", "2026-07-17", 130, "Call"),
                 ("-1", "AMD", "2026-07-17", 130, "Call"),
                 ("+1", "AMD", "2026-07-17", 140, "Call"))
    merged = bt.merge_legs(legs)
    # +2 and -1 on 130C net to +1; 140C untouched; first-seen order preserved.
    assert [(leg.qty, leg.strike) for leg in merged] == [(1, 130.0), (1, 140.0)]


def test_merge_legs_drops_net_zero():
    legs = _legs(("+1", "AMD", "2026-07-17", 130, "Call"),
                 ("-1", "AMD", "2026-07-17", 130, "Call"))
    assert bt.merge_legs(legs) == []


def test_simulate_merges_same_contract_into_single_leg():
    # +2 / -1 on the same contract should net to a +1 single leg, not be rejected.
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "x",
            "market_regime": ""}
    legs = _legs(("+2", "NVDA", "2026-07-17", 250, "Call"),
                 ("-1", "NVDA", "2026-07-17", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "8.0", "800000")
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    barchart_series = {key: [(date(2026, 6, 1), 8.0), (date(2026, 6, 4), 12.0)]}
    sim_cfg = {"profit_target": 5.0, "stop_loss": 5.0, "contracts": 1,
               "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="explicit_legs", price_fn=lambda tk, dt: None)

    assert res["legs"] == "NVDA:2026-07-17:250:C +1"
    assert res["entry_option_price"] == 8.0  # single +1 leg, not +2−1 double-counted


# ── arbitrary N-leg real per-leg pricing ────────────────────────────────────────

def test_simulate_explicit_four_leg_prices_per_leg_not_uniform_bs():
    # An explicit 4-leg iron condor must price each leg from real Barchart history
    # (real-first), NOT force uniform Black-Scholes the way a *synthesized* IC does.
    cand = {"ticker": "SPY", "signal_date": date(2026, 6, 1), "play": "ic",
            "market_regime": ""}
    legs = _legs(("+1", "SPY", "2026-07-17", 480, "Put"),
                 ("-1", "SPY", "2026-07-17", 490, "Put"),
                 ("-1", "SPY", "2026-07-17", 510, "Call"),
                 ("+1", "SPY", "2026-07-17", 520, "Call"))
    entry_row = {**_flow_row("SPY", "Put", "490", "3.0", "1000"),
                 "DTE": "46", "IV": "20%", "Price~": "500"}
    series = {
        ("SPY", "Put", 480.0, "2026-07-17"):  [(date(2026, 6, 1), 1.0)],
        ("SPY", "Put", 490.0, "2026-07-17"):  [(date(2026, 6, 1), 3.0)],
        ("SPY", "Call", 510.0, "2026-07-17"): [(date(2026, 6, 1), 2.0)],
        ("SPY", "Call", 520.0, "2026-07-17"): [(date(2026, 6, 1), 0.8)],
    }
    sim_cfg = {"profit_target": 5.0, "stop_loss": 5.0, "contracts": 1,
               "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, series, sim_cfg,
                       structure="explicit_legs", anchor_idx=1,
                       price_fn=lambda tk, dt: None)

    # Real per-leg: the anchor is its flow Trade, the rest are Barchart — never all-bs.
    assert "bs" not in res["entry_source"]
    assert "barchart" in res["entry_source"]
    # Net credit: +1·1.0 −1·3.0 −1·2.0 +1·0.8 = −3.2.
    assert res["entry_option_price"] == pytest.approx(-3.2, abs=1e-9)


def test_simulate_explicit_five_leg_nets_by_quantity():
    # A 5-leg call ladder — proves netting has no hidden 2/4-leg assumption.
    cand = {"ticker": "AMD", "signal_date": date(2026, 6, 1), "play": "ladder",
            "market_regime": ""}
    legs = _legs(("+1", "AMD", "2026-07-17", 100, "Call"),
                 ("+1", "AMD", "2026-07-17", 105, "Call"),
                 ("+1", "AMD", "2026-07-17", 110, "Call"),
                 ("+1", "AMD", "2026-07-17", 115, "Call"),
                 ("+1", "AMD", "2026-07-17", 120, "Call"))
    entry_row = {**_flow_row("AMD", "Call", "100", "5.0", "1000"),
                 "DTE": "46", "IV": "30%", "Price~": "110"}
    series = {
        ("AMD", "Call", 100.0, "2026-07-17"): [(date(2026, 6, 1), 5.0)],
        ("AMD", "Call", 105.0, "2026-07-17"): [(date(2026, 6, 1), 4.0)],
        ("AMD", "Call", 110.0, "2026-07-17"): [(date(2026, 6, 1), 3.0)],
        ("AMD", "Call", 115.0, "2026-07-17"): [(date(2026, 6, 1), 2.0)],
        ("AMD", "Call", 120.0, "2026-07-17"): [(date(2026, 6, 1), 1.0)],
    }
    sim_cfg = {"profit_target": 5.0, "stop_loss": 5.0, "contracts": 1,
               "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, series, sim_cfg,
                       structure="explicit_legs", price_fn=lambda tk, dt: None)

    assert res["entry_option_price"] == pytest.approx(15.0)  # 5+4+3+2+1


def test_simulate_butterfly_impossible_mark_clamped_to_wing_width():
    # Long call fly +1/−2/+1 (120/130/140): value clamped to [0, 10]. An impossible
    # daily mark above the wing width must clamp so MFE cannot exceed the defined max.
    cand = {"ticker": "AMD", "signal_date": date(2026, 6, 1), "play": "fly",
            "market_regime": ""}
    legs = _legs(("+1", "AMD", "2026-07-17", 120, "Call"),
                 ("-2", "AMD", "2026-07-17", 130, "Call"),
                 ("+1", "AMD", "2026-07-17", 140, "Call"))
    entry_row = {**_flow_row("AMD", "Call", "120", "12.0", "1000"),
                 "DTE": "46", "IV": "30%", "Price~": "130"}
    k120 = ("AMD", "Call", 120.0, "2026-07-17")
    k130 = ("AMD", "Call", 130.0, "2026-07-17")
    k140 = ("AMD", "Call", 140.0, "2026-07-17")
    # Entry net: +1·12 −2·4 +1·1 = 5 (inside [0,10]).
    # Day 2 raw: +1·20 −2·1 +1·0 = 18 (impossible) → clamp to 10.
    series = {
        k120: [(date(2026, 6, 1), 12.0), (date(2026, 6, 4), 20.0)],
        k130: [(date(2026, 6, 1), 4.0),  (date(2026, 6, 4), 1.0)],
        k140: [(date(2026, 6, 1), 1.0),  (date(2026, 6, 4), 0.0)],
    }
    sim_cfg = {"profit_target": 5.0, "stop_loss": 5.0, "contracts": 1,
               "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, series, sim_cfg,
                       structure="explicit_legs", price_fn=lambda tk, dt: None)

    assert res["entry_option_price"] == pytest.approx(5.0)
    # Clamped to 10 → MFE = (10 − 5)/5 = 100%, not the phantom (18 − 5)/5 = 260%.
    assert res["mfe_pct"] == pytest.approx(1.0)


# ── anchor selection for explicit legs ──────────────────────────────────────────

def test_choose_anchor_skips_leg_without_history():
    # First-long leg (illiquid 600C wing) has no Barchart history; the anchor must
    # fall back to a leg that does, so the play is not dropped as unpriced.
    from backtest.core import _choose_anchor

    legs = _legs(("+1", "SPY", "2026-07-17", 600, "Call"),   # no history
                 ("-1", "SPY", "2026-07-17", 500, "Put"))     # has history
    signal = date(2026, 6, 1)
    short_key = ("SPY", "Put", 500.0, "2026-07-17")
    details = {short_key: {date(2026, 6, 2): {
        "Price~": "500", "IV": "20%", "_mark": 5.0, "Delta": "-0.3"}}}

    idx, row = _choose_anchor(legs, details, signal)
    assert idx == 1            # the short put, not the historyless long wing
    assert row is not None


# ── credit/debit sizing & exit split (Attempt 8) ────────────────────────────────

def test_payoff_floor_put_credit_spread():
    legs = _legs(("-1", "SPY", "2026-07-17", 490, "Put"),
                 ("+1", "SPY", "2026-07-17", 480, "Put"))
    assert bt._payoff_floor(legs) == -10.0


def test_payoff_floor_naked_short_put():
    legs = _legs(("-1", "NVDA", "2026-07-17", 220, "Put"))
    assert bt._payoff_floor(legs) == -220.0  # floors at S=0 = -strike


def test_payoff_floor_none_for_naked_short_call():
    # Net call qty < 0 → payoff → -inf as S→∞, no floor.
    legs = _legs(("-1", "NVDA", "2026-07-17", 300, "Call"))
    assert bt._payoff_floor(legs) is None


def test_payoff_floor_none_for_multi_expiration():
    legs = _legs(("-1", "SPY", "2026-06-19", 500, "Call"),
                 ("+1", "SPY", "2026-09-18", 500, "Call"))
    assert bt._payoff_floor(legs) is None


def test_max_loss_per_unit_debit_is_premium():
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    assert bt._max_loss_per_unit(legs, 8.0) == 8.0


def test_max_loss_per_unit_credit_vertical():
    legs = _legs(("-1", "SPY", "2026-07-17", 490, "Put"),
                 ("+1", "SPY", "2026-07-17", 480, "Put"))
    assert bt._max_loss_per_unit(legs, -2.5) == 7.5  # -2.5 - (-10)


def test_max_loss_per_unit_none_for_naked_short_call():
    legs = _legs(("-1", "NVDA", "2026-07-17", 300, "Call"))
    assert bt._max_loss_per_unit(legs, -5.0) is None


def test_size_contracts_credit_vertical_sizes_on_structural_risk():
    # 5-wide bull put spread, credit 0.5. Pre-fix (premium-based) sizing would
    # give floor(1000 / (0.5*100*1.0)) = 20 contracts against a 2% ($1,000) risk
    # budget on a $50k book — true structural worst case is $450/contract, not $50.
    legs = _legs(("-1", "SPY", "2026-07-17", 100, "Put"),
                 ("+1", "SPY", "2026-07-17", 95, "Put"))
    sim_cfg = {"portfolio_value": 50000, "risk_per_trade_pct": 0.02}
    assert bt._size_contracts(-0.5, legs, sim_cfg) == 2


def test_size_contracts_naked_short_put_floors_at_one_contract():
    # Structural max loss ($21,500/contract) dwarfs the $1,000 risk budget —
    # floor(dollar_risk / loss_per_contract) is 0, clamped up to 1. Single leg
    # must not crash _payoff_floor / _max_loss_per_unit.
    legs = _legs(("-1", "NVDA", "2026-07-17", 220, "Put"))
    sim_cfg = {"portfolio_value": 50000, "risk_per_trade_pct": 0.02}
    assert bt._size_contracts(-5.0, legs, sim_cfg) == 1
    assert bt._max_loss_per_unit(legs, -5.0) == 215.0  # populated, not blank


def test_size_contracts_debit_ignores_credit_block():
    # A present `credit:` block must not leak into the debit branch — stop_loss
    # is read straight off the top-level sim_cfg (0.75), never the nested block's
    # 1.00 (which would give floor(1000/400)=2, not 3).
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    sim_cfg = {"portfolio_value": 50000, "risk_per_trade_pct": 0.02, "stop_loss": 0.75,
               "credit": {"stop_loss": 1.00}}
    assert bt._size_contracts(4.0, legs, sim_cfg) == 3


def test_effective_sim_cfg_credit_explicit_none_overrides():
    sim_cfg = {"profit_target": 0.90, "trailing_stop_trigger": 0.50,
               "credit": {"profit_target": 0.65, "trailing_stop_trigger": None}}
    eff = bt._effective_sim_cfg(sim_cfg, -2.5)
    assert eff["profit_target"] == 0.65
    assert eff["trailing_stop_trigger"] is None   # explicit null disables, not inherited


def test_effective_sim_cfg_debit_returns_base_unchanged():
    sim_cfg = {"profit_target": 0.90, "credit": {"profit_target": 0.65}}
    assert bt._effective_sim_cfg(sim_cfg, 3.0) is sim_cfg  # untouched for entry_net >= 0


def test_simulate_unbounded_credit_falls_back_to_one_contract(caplog):
    # Naked short call: credit but _max_loss_per_unit is None (unbounded upside
    # risk) → sizing falls back to 1 contract + warning; both new risk columns
    # stay blank since the max loss can't be bounded.
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "short call 300",
            "market_regime": ""}
    legs = _legs(("-1", "NVDA", "2026-07-17", 300, "Call"))
    entry_row = _flow_row("NVDA", "Call", "300", "5.0", "500000")
    key = ("NVDA", "Call", 300.0, "2026-07-17")
    contract_index = {key: [(date(2026, 6, 1), 5.0), (date(2026, 6, 4), 2.0)]}
    sim_cfg = {"profit_target": 0.5, "stop_loss": 1.0,
               "entry_sources": ["reappearance"], "exit_sources": ["reappearance"],
               "portfolio_value": 50000, "risk_per_trade_pct": 0.02}

    with caplog.at_level(logging.WARNING, logger="backtest"):
        res = bt._simulate(cand, legs, entry_row, contract_index, {}, sim_cfg,
                           structure="short_call", price_fn=lambda tk, dt: None)

    assert res["contracts"] == 1
    assert res["max_loss_per_contract"] == ""
    assert res["pnl_on_risk_pct"] == ""
    assert any("unbounded" in r.message.lower() for r in caplog.records)


def test_simulate_credit_exit_uses_credit_profile_not_debit():
    # Debit defaults (pt=0.90, trailing/time-exit active) would NOT exit this
    # path at day 3 (+66% of the credit); the credit override (pt=0.65, no
    # trailing, no time exit) does. Regression guard: existing credit tests that
    # set no `credit:` block (test_simulate_short_put_*, etc.) still run the
    # debit profile unchanged.
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "short put 220",
            "market_regime": "RANGE + L-VOL"}
    legs = _legs(("-1", "NVDA", "2026-07-17", 220, "Put"))
    entry_row = _flow_row("NVDA", "Put", "220", "5.0", "500000")
    key = ("NVDA", "Put", 220.0, "2026-07-17")
    contract_index = {key: [
        (date(2026, 6, 1), 5.0),   # entry
        (date(2026, 6, 2), 3.0),   # +40%
        (date(2026, 6, 3), 2.5),   # +50%
        (date(2026, 6, 4), 1.7),   # +66% → credit profit_target (0.65) fires here
        (date(2026, 6, 5), 1.0),   # +80% — never reached, exit already frozen
    ]}
    sim_cfg = {
        "profit_target": 0.90, "stop_loss": 0.75,
        "trailing_stop_trigger": 0.50, "trailing_stop_pct": 0.25,
        "time_exit_dte_fraction": 0.75,
        "contracts": 1, "entry_sources": ["reappearance"], "exit_sources": ["reappearance"],
        "credit": {
            "profit_target": 0.65, "stop_loss": 1.00,
            "trailing_stop_trigger": None, "trailing_stop_pct": None,
            "time_exit_dte_fraction": None,
        },
    }

    res = bt._simulate(cand, legs, entry_row, contract_index, {}, sim_cfg,
                       structure="short_put", price_fn=lambda tk, dt: None)

    assert res["exit_reason"] == "profit_target"
    assert res["days_held"] == 3
    assert 0.65 <= res["realized_pnl_pct"] <= 0.70


def test_pnl_on_risk_pct_debit_matches_realized_pnl_pct():
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "10.0", "800000")
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    barchart_series = {key: [(date(2026, 6, 1), 10.0), (date(2026, 6, 2), 16.0)]}
    sim_cfg = {"profit_target": 0.5, "stop_loss": 1.0, "contracts": 1,
               "exit_sources": ["barchart"]}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: None)

    assert res["max_loss_per_contract"] == 1000.0   # entry premium (10) × 100
    # Debit: same premium is both the P&L denominator and the risk denominator.
    assert res["pnl_on_risk_pct"] == res["realized_pnl_pct"]


def test_pnl_on_risk_pct_credit_spread_scales_by_structural_risk():
    # Same setup as test_simulate_bull_put_spread_credit (60% of the 2.5 credit).
    cand = {"ticker": "SPY", "signal_date": date(2026, 6, 1),
            "play": "bull put spread 490/480", "market_regime": "RANGE + L-VOL"}
    legs = _legs(("-1", "SPY", "2026-07-17", 490, "Put"),
                 ("+1", "SPY", "2026-07-17", 480, "Put"))
    entry_row = _flow_row("SPY", "Put", "490", "4.0", "400000")
    sold_key  = ("SPY", "Put", 490.0, "2026-07-17")
    hedge_key = ("SPY", "Put", 480.0, "2026-07-17")
    barchart_series = {
        sold_key:  [(date(2026, 6, 1), 4.0), (date(2026, 6, 4), 1.5)],
        hedge_key: [(date(2026, 6, 1), 1.5), (date(2026, 6, 4), 0.5)],
    }
    sim_cfg = {"profit_target": 0.5, "stop_loss": 1.0, "contracts": 1}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="bull_put_spread", price_fn=lambda tk, dt: None)

    # entry credit -2.5, floor -10 → max_loss_per_contract = 7.5 × 100 = 750.
    assert res["max_loss_per_contract"] == 750.0
    assert abs(res["realized_pnl_pct"] - 0.6) < 0.001
    # pnl_on_risk_pct re-expresses the 60%-of-credit gain against the $750
    # structural risk instead of the $250 credit: (0.6*2.5*100)/750 = 0.2.
    assert abs(res["pnl_on_risk_pct"] - 0.2) < 0.001
