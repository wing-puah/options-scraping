from datetime import date

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
    assert bt.classify_play("X — | short strangle | x")["structure"] == "unsupported"
    assert bt.classify_play("X — | covered call | x")["structure"] == "unsupported"
    assert bt.classify_play("X — | butterfly spread | x")["structure"] == "unsupported"


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


def test_classify_unsupported_ambiguous():
    # Mentions both call and put with no spread keyword → not safely simulatable.
    assert bt.classify_play("X — straddle: call and put")["structure"] == "unsupported"


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
    junk = _flow_row("NVDA", "Call", "0.5", "215", "136000000"); junk["IV"] = "0.00%"
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


def test_simulate_real_entry_and_real_exit():
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": "BULL + L-VOL"}
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "8.0", "800000")
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    # Contract reappears at +60% on day 3.
    contract_index = {key: [(date(2026, 6, 4), 12.8)]}
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1}

    res = bt._simulate(cand, legs, entry_row, contract_index, {}, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: None)

    assert res["entry_option_price"] == 8.0
    assert res["entry_source"] == "real"
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
    barchart_series = {key: [(date(2026, 6, 4), 16.0)]}
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
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1}

    # No contract index → must use BS; underlying jumps to 300 (deep ITM).
    res = bt._simulate(cand, legs, entry_row, {}, {}, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: 300.0)

    assert res["pct_real_days"] == 0.0   # all marks are Black-Scholes (0/n = 0)
    assert res["realized_pnl_pct"] > 0


def test_simulate_rejects_degenerate_spread():
    # Two legs on the SAME contract (long 340 / short 340) → degenerate, rejected.
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

    # Entry long is the real flow Trade (10); short is real Barchart (4) → debit 6.
    assert res["entry_option_price"] == 6.0
    assert res["entry_source"] == "real+barchart"
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
    barchart_series = {long_key: [(date(2026, 6, 4), 16.0)]}
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0, "contracts": 1}

    res = bt._simulate(cand, legs, entry_row, {}, barchart_series, sim_cfg,
                       structure="bull_call_spread", price_fn=lambda tk, dt: 305.0)

    assert res["entry_source"] == "real+bs"   # short leg modelled with BS at entry
    assert "MRVL:2026-07-17:320:C -1" in res["legs"]


def test_simulate_daily_path_realized_exit_and_excursions():
    # Long call, entry 10. Daily Barchart marks dip then rip past the target.
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = _legs(("+1", "NVDA", "2026-07-17", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "10.0", "800000")
    key = ("NVDA", "Call", 250.0, "2026-07-17")
    barchart_series = {key: [
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


def test_simulate_path_cap_open_when_dte_exceeds_cap():
    # Flat price, never triggers; DTE 200 > cap 120 → held open at the cap.
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = _legs(("+1", "NVDA", "2026-12-18", 250, "Call"))
    entry_row = _flow_row("NVDA", "Call", "250", "10.0", "800000")
    entry_row["DTE"] = "200"
    entry_row["Expiration Date"] = "2026-12-18"
    key = ("NVDA", "Call", 250.0, "2026-12-18")
    barchart_series = {key: [(date(2026, 6, 2), 10.0)]}  # carries forward flat
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
    barchart_series = {key: [(date(2026, 6, 2), 10.0)]}
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
    sim_cfg = {"exit_days": [3]}

    res = bt._simulate(cand, legs, entry_row, {}, {}, sim_cfg,
                       structure="long_call", price_fn=lambda tk, dt: None)
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
    contract_index = {key: [(date(2026, 6, 4), 2.0)]}  # option decays
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "exit_sources": ["reappearance"]}

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
    contract_index = {key: [(date(2026, 6, 4), 12.0)]}  # option goes against us
    sim_cfg = {"exit_days": [3], "profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "exit_sources": ["reappearance"]}

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

    # Entry credit: −real sold (4) + real hedge from barchart (1.5) = −2.5 (signed)
    assert res["entry_option_price"] == -2.5
    assert res["entry_source"].startswith("real")
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

    sim_cfg = {"profit_target": 0.5, "stop_loss": 1.0,
               "contracts": 1, "spread_width_pct": 0.02, "risk_free_rate": 0.05,
               "exit_sources": ["bs"], "uniform_bs_min_legs": 4}

    # Underlying stays at 500 — well inside the condor wings.
    res = bt._simulate(cand, legs, entry_row, {}, {}, sim_cfg,
                       structure="iron_condor", anchor_idx=1,
                       price_fn=lambda tk, dt: 500.0)

    assert res["structure"] == "iron_condor"
    assert res["entry_source"] == "bs"        # all four legs modelled
    assert res["entry_option_price"] < 0      # signed: net credit
    assert res["realized_pnl_pct"] > 0        # premium decays → profit


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


def test_classify_play_recognises_explicit_legs_over_unsupported_keyword():
    # "calendar" alone is unsupported, but an explicit leg-string is accepted.
    out = bt.classify_play("calendar spread\n+1 AMD:2026-10-16:130:C\n-1 AMD:2026-07-17:130:C")
    assert out["structure"] == "explicit_legs"
    assert len(out["legs"]) == 2


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
               "exit_sources": ["bs"], "risk_free_rate": 0.05}

    res = bt._simulate(cand, legs, entry_row, {}, {}, sim_cfg,
                       structure="explicit_legs", anchor_idx=1,
                       price_fn=lambda tk, dt: 500.0)

    # The path stops at the NEAR leg's expiry (~18 days), not the far leg's.
    n_days = len([t for t in res["daily_price_csv"].split(",")])
    assert n_days <= 14   # ~13 weekdays in the 18-day near-leg window
    assert res["entry_option_price"] != 0
