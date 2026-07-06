from datetime import date

import pytest

import backtest as bt
import backtest.plays as plays_mod
import backtest.proxy as proxy
from backtest.classify import _entry_row_from_history
from backtest.helpers import _contract_key
from lib import barchart_options as bo

SIGNAL = date(2026, 6, 1)
EXP = date(2026, 6, 20)

_CFG = {"max_strike_steps": 6, "max_expiry_deviation_days": 14}
_SIM_CFG = {"contracts": 1, "profit_target": 0.5, "stop_loss": 1.0,
            "entry_sources": ["barchart"], "exit_sources": ["barchart", "reappearance", "bs"],
            "path_cap_days": 120, "risk_free_rate": 0.05}
_SPREAD_PCT = 0.02


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Isolated HISTORY_CACHE for both proxy.py's own lookups and plays.py's expiry
    resolution, so tests never touch the real backtests/option_history_cache/."""
    d = tmp_path / "option_history_cache"
    d.mkdir()
    monkeypatch.setattr(proxy, "HISTORY_CACHE", d)
    monkeypatch.setattr(plays_mod, "HISTORY_CACHE", d)
    proxy._details_cache.clear()
    return d


# ── Barchart history CSV fixture writer (schema per lib/barchart_options.py) ────

_HEADER = ('Time,Open,High,Low,Latest,Change,%Change,Volume,"Open Int",IV,Delta,Gamma,'
           "Theta,Vega,Rho,Theo,Price~,Bid,Ask\n")


def _hist_row(d, underlying, iv, delta, bid, ask):
    return (f"{d},{bid},{bid},{bid},{bid},0,0.00%,100,50,{iv},{delta},"
            f"0.003,-0.20,0.65,-0.26,{underlying},{underlying},{bid},{ask}\n")


def _write_history(cache_dir, symbol, expiration, strike, opt_type, rows):
    """rows: list of (date_str, underlying_price, iv_str, delta_str, bid, ask)."""
    path = bo.cache_path(cache_dir, symbol, expiration, strike, opt_type)
    text = _HEADER + "".join(_hist_row(*r) for r in rows)
    text += '"Downloaded from Barchart.com as of 06-04-2026 09:16am CDT"\n'
    path.write_text(text, encoding="utf-8")
    return path


def _long_call_candidate(ticker="NVDA", play="long call 250 Jun 20", signal=SIGNAL):
    return {"ticker": ticker, "play": play, "signal_date": signal, "date": signal.isoformat(),
            "regime": "BULL", "market_regime": "BULL + L-VOL"}


# ── 1. Untested join ────────────────────────────────────────────────────────────

def test_identity_key_normalizes_locale_dates_and_whitespace():
    # "6/25/2026" is ambiguous only under %d/%m/%Y (day=6, month=25 -> invalid), so
    # it unambiguously resolves as %m/%d/%Y -> June 25. Ticker case and play-text
    # whitespace/casing also must not affect the key.
    k1 = bt._identity_key(date(2026, 6, 25), "nvda", "  Long   call 250  ")
    k2 = bt._identity_key("6/25/2026", "NVDA", "Long call 250")
    assert k1 == k2


def test_identity_key_distinguishes_different_plays_same_ticker_date():
    k1 = bt._identity_key(date(2026, 6, 25), "NVDA", "Long call 250")
    k2 = bt._identity_key(date(2026, 6, 25), "NVDA", "Bull call spread 250/260")
    assert k1 != k2


def test_find_untested_drops_matching_tested_rows_with_locale_dates(monkeypatch):
    monkeypatch.setattr(proxy.sheets_client, "get_all_rows", lambda tab: [
        {"signal_date": "6/25/2026", "ticker": "NVDA", "play": "Long call 250"},
    ])
    tested = bt._load_tested_keys("BacktestResults")

    candidates = [
        {"signal_date": date(2026, 6, 25), "ticker": "NVDA", "play": "Long call 250"},
        {"signal_date": date(2026, 6, 25), "ticker": "NVDA", "play": "Bull call spread 250/260"},
        {"signal_date": date(2026, 6, 26), "ticker": "NVDA", "play": "Long call 250"},
    ]
    untested = bt._find_untested(candidates, tested)

    assert [c["play"] for c in untested] == ["Bull call spread 250/260", "Long call 250"]
    assert untested[1]["signal_date"] == date(2026, 6, 26)


# ── 2. Skip-reason mapping ───────────────────────────────────────────────────────

def test_classify_and_build_unsupported_skip_reason():
    play, reason = bt.classify_and_build(
        {"ticker": "XOM", "play": "covered call 100", "signal_date": SIGNAL}, _SPREAD_PCT)
    assert play is None
    assert reason[0] == "unsupported"


def test_classify_and_build_no_strike_skip_reason():
    play, reason = bt.classify_and_build(
        {"ticker": "NVDA", "play": "long call", "signal_date": SIGNAL}, _SPREAD_PCT)
    assert play is None
    assert reason[0] == "no_strike"


def test_classify_and_build_no_expiry_skip_reason(cache_dir):
    # No explicit month in the play text, no DTE hint, and an empty HISTORY_CACHE
    # (via the fixture) so no cache-derived expiry can be synthesised either.
    play, reason = bt.classify_and_build(
        {"ticker": "NVDA", "play": "long call 250", "signal_date": SIGNAL}, _SPREAD_PCT)
    assert play is None
    assert reason[0] == "no_expiry"


def test_skip_reason_no_history_when_cache_file_absent(cache_dir):
    play, reason = bt.classify_and_build(_long_call_candidate(), _SPREAD_PCT)
    assert reason is None
    assert bt._skip_reason(play, None) == "no_history"


def test_skip_reason_unpriced_when_cache_covers_signal_date(cache_dir):
    play, reason = bt.classify_and_build(_long_call_candidate(), _SPREAD_PCT)
    assert reason is None
    _write_history(cache_dir, "NVDA", EXP, 250.0, "Call",
                    [(SIGNAL.isoformat(), 250.0, "40.0", "0.50", 8.0, 9.0)])
    # Entry-window data is present and priceable at the anchor's own strike/expiry,
    # so _skip_reason reports "unpriced" (the real backtest must have skipped it
    # for some other reason) rather than "no_history".
    assert bt._skip_reason(play, None) == "unpriced"


# ── 3. Method 1: strike/expiry tweak ─────────────────────────────────────────────

def test_method1_snaps_to_nearest_cached_strike_and_prices_from_barchart(cache_dir):
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    assert play.legs == [bt.Leg(1, "NVDA", EXP, 250.0, "Call")]

    # No cache for the exact 250C; a 255C (1 strike-step away at the inferred/
    # fallback step of 5.0) has history covering the signal window. The fixture
    # writes Open = bid, so under the default entry_timing (next_open) the fill
    # is the day-after-signal Open of 9.8.
    _write_history(cache_dir, "NVDA", EXP, 255.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0),    # signal-day mark 8.5
        ("2026-06-02", 250.0, "45.0", "0.55", 9.8, 10.2),   # entry Open 9.8
        ("2026-06-03", 250.0, "45.0", "0.55", 15.0, 17.0),  # exit mark 16.0 (+63%)
    ])

    pool = bt._cache_contracts("NVDA")
    step = bt._infer_strike_step([p["strike"] for p in pool]) or bt._strike_step(250.0)
    assert step == 5.0  # single cached strike -> falls back to _strike_step(250)

    outcome, pool = bt._method1(play, c, _CFG, _SIM_CFG, _SPREAD_PCT, pool, step, allow_probe=False)

    assert outcome is not None
    proxy_method, detail, result, used_legs = outcome
    assert proxy_method == "strike_expiry_tweak"
    assert "→" in detail
    assert "255" in used_legs
    assert result["entry_option_price"] == pytest.approx(9.8)
    assert result["entry_source"] == "barchart_open"
    assert result["exit_reason"] == "profit_target"
    assert result["realized_pnl_pct"] == pytest.approx(0.6327, abs=0.001)


def test_method1_signal_eod_timing_reproduces_legacy_entry(cache_dir):
    # entry_timing: signal_eod must reproduce the old basis — the signal day's
    # EOD mark (mid bid/ask), never the next day's Open.
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 255.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0),    # entry mark 8.5
        ("2026-06-02", 250.0, "45.0", "0.55", 15.0, 17.0),  # exit mark 16.0 (+88%)
    ])
    pool = bt._cache_contracts("NVDA")
    eod_cfg = {**_SIM_CFG, "entry_timing": "signal_eod"}

    outcome, pool = bt._method1(play, c, _CFG, eod_cfg, _SPREAD_PCT, pool, 5.0,
                                allow_probe=False)

    assert outcome is not None
    _method, _detail, result, _used = outcome
    assert result["entry_option_price"] == pytest.approx(8.5)
    assert result["entry_source"] == "barchart"
    assert result["exit_reason"] == "profit_target"
    assert result["realized_pnl_pct"] == pytest.approx(0.8824, abs=0.001)


def test_method1_returns_none_when_no_neighbor_within_strike_bound(cache_dir):
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 255.0, "Call",
                    [("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0)])
    pool = bt._cache_contracts("NVDA")

    tight_cfg = {"max_strike_steps": 0, "max_expiry_deviation_days": 14}
    outcome, pool = bt._method1(play, c, tight_cfg, _SIM_CFG, _SPREAD_PCT, pool, 5.0,
                                allow_probe=False)

    assert outcome is None


def _vertical_candidate():
    return {"ticker": "NVDA", "play": "bull call spread 250/260 Jun 20",
            "signal_date": SIGNAL, "date": SIGNAL.isoformat(),
            "regime": "BULL", "market_regime": "BULL + L-VOL"}


def test_method1_keeps_vertical_legs_on_one_snapped_expiry(cache_dir):
    # Real regression (MU 2024-06-17): each leg snapped independently, so a
    # vertical's legs landed on two different expiries — an accidental diagonal.
    # The 250C only has history at Jun 26; the 260C has history at BOTH Jun 20
    # (its exact expiry) and Jun 26. Once the first leg pins the group to Jun 26,
    # the short leg must follow it there, not take its exact-date Jun 20 match.
    c = _vertical_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    assert [leg.expiration for leg in play.legs] == [EXP, EXP]

    far = date(2026, 6, 26)
    _write_history(cache_dir, "NVDA", far, 250.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0),
        ("2026-06-02", 255.0, "45.0", "0.60", 15.0, 17.0),
    ])
    _write_history(cache_dir, "NVDA", EXP, 260.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.30", 5.0, 6.0),
        ("2026-06-02", 255.0, "45.0", "0.35", 7.0, 8.0),
    ])
    _write_history(cache_dir, "NVDA", far, 260.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.32", 4.0, 5.0),
        ("2026-06-02", 255.0, "45.0", "0.37", 6.0, 8.0),
    ])

    pool = bt._cache_contracts("NVDA")
    step = bt._infer_strike_step([p["strike"] for p in pool])
    outcome, pool = bt._method1(play, c, _CFG, _SIM_CFG, _SPREAD_PCT, pool, step,
                                allow_probe=False)

    assert outcome is not None
    _method, _detail, _result, used_legs = outcome
    assert used_legs.count("2026-06-26") == 2
    assert "2026-06-20" not in used_legs


def test_method1_fails_over_when_pinned_expiry_has_no_short_leg(cache_dir):
    # Same setup minus the 260C@Jun26 file: the pin can't be satisfied, so method 1
    # must fail (→ BS fallback on the actual legs) instead of building a diagonal
    # from the 250C@Jun26 + 260C@Jun20 that ARE individually available.
    c = _vertical_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)

    far = date(2026, 6, 26)
    _write_history(cache_dir, "NVDA", far, 250.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0),
    ])
    _write_history(cache_dir, "NVDA", EXP, 260.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.30", 5.0, 6.0),
    ])

    pool = bt._cache_contracts("NVDA")
    step = bt._infer_strike_step([p["strike"] for p in pool])
    outcome, pool = bt._method1(play, c, _CFG, _SIM_CFG, _SPREAD_PCT, pool, step,
                                allow_probe=False)

    assert outcome is None


# ── 4. Method 2: Black-Scholes off a donor's Price~/IV history ──────────────────

def test_method2_prices_via_bs_off_donor_iv_and_records_sigma(cache_dir):
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 260.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.50", 9.0, 11.0),
        ("2026-06-02", 250.0, "70.0", "0.50", 9.0, 11.0),
    ])
    pool = bt._cache_contracts("NVDA")

    outcome, pool = bt._method2(play, c, _CFG, _SIM_CFG, _SPREAD_PCT, pool, 5.0, allow_probe=False)

    assert outcome is not None
    proxy_method, detail, result, used_legs = outcome
    assert proxy_method == "bs_options_hist"
    assert result["entry_source"] == "bs"
    assert "sigma 0.450" in detail  # entry-day (2026-06-01) IV = 45.0 / 100
    assert used_legs == "NVDA:2026-06-20:250:C +1"


def test_method2_iv_fn_varies_sigma_across_days_vs_a_fixed_iv_run(cache_dir):
    # Same donor as above (day1 IV=45%, day2 IV=70%, Price~ held flat at 250 so any
    # mark difference is attributable to sigma alone). Reconstruct the same
    # synthetic entry_row _method2 would build, then compare a per-day-varying
    # iv_fn against a fixed-sigma run using the identical price_fn.
    donor_path = _write_history(cache_dir, "NVDA", EXP, 260.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.50", 9.0, 11.0),
        ("2026-06-02", 250.0, "70.0", "0.50", 9.0, 11.0),
    ])
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    leg = play.legs[0]

    details = bo.parse_history_details(donor_path.read_text(encoding="utf-8"))
    key = _contract_key("NVDA", "Call", leg.strike, leg.expiration.isoformat())
    entry_row = _entry_row_from_history({key: details}, key, SIGNAL, leg.strike, leg.expiration)
    assert entry_row is not None

    price_series = [(date(2026, 6, 1), 250.0), (date(2026, 6, 2), 250.0)]
    iv_series = [(date(2026, 6, 1), 0.45), (date(2026, 6, 2), 0.70)]

    def _asof(series, day):
        best = None
        for d, v in series:
            if d <= day:
                best = v
        return best

    def price_fn(_tk, day):
        return _asof(price_series, day)

    def iv_fn_varying(day):
        return _asof(iv_series, day)

    def iv_fn_fixed(day):
        return 0.45

    bs_cfg = {**_SIM_CFG, "entry_sources": ["bs"], "exit_sources": ["bs"]}
    res_varying = bt._simulate(c, play.legs, entry_row, {}, {}, bs_cfg,
                               structure=play.structure, anchor_idx=play.anchor_idx,
                               price_fn=price_fn, iv_fn=iv_fn_varying)
    res_fixed = bt._simulate(c, play.legs, entry_row, {}, {}, bs_cfg,
                             structure=play.structure, anchor_idx=play.anchor_idx,
                             price_fn=price_fn, iv_fn=iv_fn_fixed)

    assert res_varying and res_fixed
    assert res_varying["daily_price_csv"] != res_fixed["daily_price_csv"]


# ── 5. iv_fn back-compat ─────────────────────────────────────────────────────────

def test_simulate_iv_fn_omitted_matches_explicit_none():
    cand = {"ticker": "NVDA", "signal_date": date(2026, 6, 1), "play": "long call",
            "market_regime": ""}
    legs = [bt.Leg(1, "NVDA", date(2026, 7, 17), 250.0, "Call")]
    entry_row = {"Strike": "250", "DTE": "46", "IV": "40%", "Price~": "250",
                 "Trade": "", "Delta": "0.5"}
    sim_cfg = {"profit_target": 0.5, "stop_loss": 1.0, "contracts": 1, "exit_sources": ["bs"]}

    res_omitted = bt._simulate(cand, legs, entry_row, {}, {}, sim_cfg,
                               structure="long_call", price_fn=lambda tk, dt: 300.0)
    res_explicit_none = bt._simulate(cand, legs, entry_row, {}, {}, sim_cfg,
                                     structure="long_call", price_fn=lambda tk, dt: 300.0,
                                     iv_fn=None)

    assert res_omitted == res_explicit_none


# ── 6. Method 3: direction-only verdict ──────────────────────────────────────────

def test_method3_direction_only_bullish_correct(cache_dir):
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 260.0, "Call", [
        ("2026-06-01", 250.0, "", "0.50", 8.0, 9.0),   # entry underlying 250, IV blank
        ("2026-06-05", 260.0, "", "0.50", 9.0, 10.0),   # underlying rose to 260
    ])
    pool = bt._cache_contracts("NVDA")

    outcome, pool = bt._method3(play, c, _CFG, _SIM_CFG, _SPREAD_PCT, pool, 5.0, allow_probe=False)

    assert outcome is not None
    proxy_method, detail, result, used_legs = outcome
    assert proxy_method == "underlying_trend"
    assert result["exit_reason"] == "direction_only"
    assert "direction_correct=True" in detail
    assert result["entry_underlying"] == pytest.approx(250.0)
    # P&L columns are simply absent from the result dict for this method.
    assert "realized_pnl_pct" not in result
    assert "daily_price_csv" not in result


def test_method3_neutral_structure_returns_none():
    c = {"ticker": "SPY", "play": "sell straddle 500 Jun 20", "signal_date": SIGNAL,
         "date": SIGNAL.isoformat()}
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    assert play.structure == "straddle"
    assert play.legs  # MultiLegPlay builds legs eagerly

    outcome, pool = bt._method3(play, c, _CFG, _SIM_CFG, _SPREAD_PCT, [], 5.0, allow_probe=False)

    assert outcome is None


# ── 7. Unevaluable ───────────────────────────────────────────────────────────────

def test_evaluate_unevaluable_when_play_never_built():
    c = {"ticker": "XOM", "play": "covered call 100", "signal_date": SIGNAL,
         "date": SIGNAL.isoformat(), "regime": "BULL", "market_regime": "BULL + L-VOL"}
    play, reason = bt.classify_and_build(c, _SPREAD_PCT)
    assert play is None and reason[0] == "unsupported"

    row = bt._evaluate(play, reason, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-07-06T10:00:00", False)

    assert row["skip_reason"] == "unsupported"
    assert row["proxy_method"] == "unevaluable"
    assert row["proxy_detail"] == reason[1]
    assert row["ticker"] == "XOM"
    assert row["legs"] == ""
    assert row["realized_pnl_pct"] == ""
    assert row["daily_price_csv"] == ""


def test_evaluate_unevaluable_when_fallback_chain_exhausted(cache_dir):
    # Straddle (neutral structure) with a completely empty cache for its ticker:
    # Method 1 (no snap candidate), Method 2 (no donor), Method 3 (neutral) all
    # fall through -> unevaluable, but with a real skip_reason from the anchor.
    c = {"ticker": "SPY", "play": "sell straddle 500 Jun 20", "signal_date": SIGNAL,
         "date": SIGNAL.isoformat(), "regime": "RANGE", "market_regime": "RANGE + H-VOL"}
    play, reason = bt.classify_and_build(c, _SPREAD_PCT)
    assert reason is None

    row = bt._evaluate(play, reason, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-07-06T10:00:00", False)

    assert row["skip_reason"] == "no_history"
    assert row["proxy_method"] == "unevaluable"
    assert row["proxy_detail"] == "no usable options history for any fallback"
    assert row["legs"] == row["legs_original"]


# ── 8. Dedup / idempotency ───────────────────────────────────────────────────────

def test_find_untested_drops_candidates_already_in_backtest_proxy(monkeypatch):
    monkeypatch.setattr(proxy.sheets_client, "get_all_rows", lambda tab: [
        {"signal_date": "2026-06-25", "ticker": "NVDA", "play": "Long call 250"},
    ])
    existing = bt._load_proxy_keys("BacktestProxy")
    candidates = [{"signal_date": date(2026, 6, 25), "ticker": "NVDA", "play": "Long call 250"}]

    remaining = bt._find_untested(candidates, existing)

    assert remaining == []


# ── 9. Schema ─────────────────────────────────────────────────────────────────

def test_evaluate_row_schema_and_decimal_percentages(cache_dir):
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 255.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0),
        ("2026-06-02", 250.0, "45.0", "0.55", 15.0, 17.0),
    ])

    row = bt._evaluate(play, None, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-07-06T10:00:00", False)

    assert set(bt._PROXY_KEY_ORDER) <= set(row.keys())
    assert row["proxy_method"] == "strike_expiry_tweak"
    # iv_entry_pct is a decimal fraction (0.45), not 45.
    assert 0 < row["iv_entry_pct"] < 1
    assert row["iv_entry_pct"] == pytest.approx(0.45)


# ── 10. --redo (re-evaluate frozen rows) ─────────────────────────────────────────

def _run_main(monkeypatch, argv, cand, existing_keys):
    """Drive proxy.main() with all sheet/network I/O stubbed; returns what it
    deleted and wrote."""
    calls = {"deleted": None, "written": None}
    monkeypatch.setattr(proxy, "load_analysis", lambda tab, s, e: ([cand], {}))
    monkeypatch.setattr(proxy, "_load_tested_keys", lambda tab: set())
    monkeypatch.setattr(proxy, "_load_proxy_keys", lambda tab: existing_keys)

    def fake_delete(tab, match_fn):
        calls["deleted"] = (tab, match_fn)
        return 1

    monkeypatch.setattr(proxy.sheets_client, "delete_rows_where", fake_delete)
    monkeypatch.setattr(proxy, "write_results", lambda rows, **kw: calls.update(written=rows))
    monkeypatch.setattr("sys.argv", ["proxy"] + argv)
    proxy.main()
    return calls


def _frozen_candidate():
    return {"ticker": "NVDA", "play": "long call 250 Jun 20",
            "signal_date": SIGNAL, "date": SIGNAL.isoformat(), "regime": "BULL"}


def test_redo_reevaluates_and_deletes_existing_rows(monkeypatch, cache_dir):
    cand = _frozen_candidate()
    key = bt._identity_key(SIGNAL, "NVDA", cand["play"])

    calls = _run_main(monkeypatch, ["--date", SIGNAL.isoformat(), "--redo", "--cache-only"],
                      cand, {key})

    assert calls["written"] is not None and len(calls["written"]) == 1
    assert calls["written"][0]["ticker"] == "NVDA"
    tab, match_fn = calls["deleted"]
    assert match_fn({"signal_date": SIGNAL.isoformat(), "ticker": "NVDA",
                     "play": cand["play"]})
    assert not match_fn({"signal_date": "2026-06-02", "ticker": "NVDA",
                         "play": cand["play"]})


def test_redo_dry_run_skips_deletion(monkeypatch, cache_dir):
    cand = _frozen_candidate()
    key = bt._identity_key(SIGNAL, "NVDA", cand["play"])

    calls = _run_main(monkeypatch,
                      ["--date", SIGNAL.isoformat(), "--redo", "--cache-only", "--dry-run"],
                      cand, {key})

    assert calls["deleted"] is None


def test_without_redo_existing_proxy_rows_stay_frozen(monkeypatch, cache_dir):
    cand = _frozen_candidate()
    key = bt._identity_key(SIGNAL, "NVDA", cand["play"])

    calls = _run_main(monkeypatch, ["--date", SIGNAL.isoformat(), "--cache-only"],
                      cand, {key})

    assert calls["deleted"] is None
    assert not calls["written"]  # nothing re-evaluated


def test_redo_requires_date_bounds(monkeypatch):
    monkeypatch.setattr("sys.argv", ["proxy", "--redo"])
    with pytest.raises(SystemExit):
        proxy.main()
