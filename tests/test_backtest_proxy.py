from datetime import date
import logging

import pytest

import backtest as bt
import backtest.plays as plays_mod
import backtest.proxy as proxy
from lib.barchart import options as bo

SIGNAL = date(2026, 6, 1)
EXP = date(2026, 6, 20)

_CFG = {"max_strike_steps": 6, "max_expiry_deviation_days": 14}
_SIM_CFG = {"contracts": 1, "profit_target": 0.5, "stop_loss": 1.0,
            "entry_sources": ["barchart"], "exit_sources": ["barchart", "reappearance"],
            "path_cap_days": 120}
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


# ── Barchart history CSV fixture writer (schema per lib/barchart/options.py) ────

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


def test_classify_and_build_structure_veto():
    c = {"ticker": "TSLA", "play": "bear call spread 250/260 exp 2026-08-21",
         "signal_date": SIGNAL}
    play, reason = bt.classify_and_build(
        dict(c), _SPREAD_PCT, structure_veto=("bear_call_spread",))
    assert play is None
    assert reason == ("vetoed", "structure=bear_call_spread")
    # same play builds normally when the veto list doesn't name it
    play, reason = bt.classify_and_build(dict(c), _SPREAD_PCT)
    assert reason is None or reason[0] != "vetoed"


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
        ("2026-06-03", 250.0, "45.0", "0.55", 15.5, 16.5),  # exit mark 16.0 (+63%)
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
        ("2026-06-02", 250.0, "45.0", "0.55", 15.5, 16.5),  # exit mark 16.0 (+88%)
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
    # must fail (→ the direction-only verdict) instead of building a diagonal
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


# ── 4. The Black-Scholes tier is gone ───────────────────────────────────────────

def test_method2_bs_tier_no_longer_exists():
    # Deleted 2026-09-23: model prices were abolished from the backtest.
    assert not hasattr(proxy, "_method2")
    assert not hasattr(bt, "_method2")


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


def test_evaluate_falls_to_underlying_trend_when_no_snappable_contract(cache_dir):
    # Donor 30 strike-steps away: outside Method 1's snap bound (max_strike_steps 6).
    # There is no model tier between the two, so this bullish play lands on
    # Method 3's direction-only verdict with blank P&L.
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 400.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.50", 9.0, 11.0),
        ("2026-06-02", 260.0, "45.0", "0.50", 9.0, 11.0),
    ])

    row = bt._evaluate(play, None, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-08-11T10:00:00", False)

    assert row["proxy_method"] == "underlying_trend"
    assert row["exit_reason"] == "direction_only"
    assert row["realized_pnl_pct"] == ""


def test_evaluate_refuses_bs_fallback_config(cache_dir):
    # `bs_fallback: true` asks for the deleted Black-Scholes tier: refused loudly.
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    with pytest.raises(ValueError, match="bs_fallback"):
        bt._evaluate(play, None, c, {**_CFG, "bs_fallback": True}, _SIM_CFG,
                     _SPREAD_PCT, "2026-08-11T10:00:00", False)
    proxy.validate_proxy_config({**_CFG, "bs_fallback": False})  # off is harmless


def test_evaluate_unevaluable_when_fallback_chain_exhausted(cache_dir):
    # Straddle (neutral structure) with a completely empty cache for its ticker:
    # Method 1 (no snap candidate) and Method 3 (neutral) both fall through
    # -> unevaluable, but with a real skip_reason from the anchor.
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


def test_evaluate_relabels_no_history_when_the_snap_prices_a_neighbour(cache_dir):
    # The named 250C has no cache, so the pre-chain reason is `no_history`; the
    # snap then prices the 255C from real history. The written row must not
    # read as a failure: `no_history` becomes `snap_priced`.
    c = _long_call_candidate()
    play, reason = bt.classify_and_build(c, _SPREAD_PCT)
    assert bt._skip_reason(play, None) == "no_history"
    _write_history(cache_dir, "NVDA", EXP, 255.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0),
        ("2026-06-02", 250.0, "45.0", "0.55", 9.8, 10.2),
        ("2026-06-03", 250.0, "45.0", "0.55", 15.0, 17.0),
    ])

    row = bt._evaluate(play, reason, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-07-06T10:00:00", False)

    assert row["proxy_method"] == "strike_expiry_tweak"
    assert row["entry_source"] == "barchart_open"
    assert row["skip_reason"] == proxy.SNAP_PRICED == "snap_priced"
    assert "→" in row["proxy_detail"]


def test_evaluate_relabels_no_history_when_the_probe_fetches_the_named_contract(
        cache_dir, monkeypatch):
    # The anchor's own contract is missing before the chain; the probe scrapes
    # it (stubbed here) and method 1 prices it with no tweak at all.
    c = _long_call_candidate()
    play, reason = bt.classify_and_build(c, _SPREAD_PCT)

    def fake_probe(leg, signal_date, cfg, sim_cfg, step):
        _write_history(cache_dir, "NVDA", EXP, 250.0, "Call", [
            ("2026-06-01", 250.0, "45.0", "0.50", 8.0, 9.0),
            ("2026-06-02", 250.0, "45.0", "0.50", 9.8, 10.2),
            ("2026-06-03", 250.0, "45.0", "0.50", 15.0, 17.0),
        ])
        proxy._details_cache.clear()
        return proxy._cache_contracts("NVDA")

    monkeypatch.setattr(proxy, "_probe_pool", fake_probe)
    row = bt._evaluate(play, reason, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-07-06T10:00:00", True)

    assert row["proxy_method"] == "strike_expiry_tweak"
    assert row["proxy_detail"] == "all legs had listed history"
    assert row["skip_reason"] == "snap_priced"


def test_evaluate_keeps_no_history_on_the_direction_only_tier(cache_dir):
    # Method 1 cannot price (donor far outside the snap bound), so the play
    # really found no real price: `no_history` stays.
    c = _long_call_candidate()
    play, reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 400.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.50", 9.0, 11.0),
        ("2026-06-02", 260.0, "45.0", "0.50", 9.0, 11.0),
    ])

    row = bt._evaluate(play, reason, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-08-11T10:00:00", False)

    assert row["proxy_method"] == "underlying_trend"
    assert row["skip_reason"] == "no_history"


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

def _run_main(monkeypatch, argv, cand, existing_keys, tested_keys=frozenset()):
    """Drive proxy.main() with all sheet/network I/O stubbed; returns what it
    deleted and wrote."""
    calls = {"deleted": None, "written": None}
    monkeypatch.setattr(proxy, "load_analysis", lambda tab, s, e: ([cand], {}))
    monkeypatch.setattr(proxy, "_load_tested_keys", lambda tab: set(tested_keys))
    monkeypatch.setattr(proxy, "_load_proxy_keys", lambda tab: existing_keys)

    def fake_delete(tab, match_fn):
        calls["deleted"] = (tab, match_fn)
        return 1

    monkeypatch.setattr(proxy.sheets_client, "delete_rows_where", fake_delete)
    def fake_write(rows, **kw):
        # The real write_results runs the --redo delete between the local CSV
        # and the Sheets append; mirror that slot here.
        if kw.get("before_sheet") and not kw.get("dry_run"):
            kw["before_sheet"]()
        calls.update(written=rows)

    monkeypatch.setattr(proxy, "write_results", fake_write)
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


# ── 10b. cross-tab duplicates (a play re-priced onto BacktestResults) ────────────
# `scripts.backtest --redo` can price a play the proxy used to stand in for once
# the history cache has grown. The proxy then skips it as tested, but its OLD
# proxy row stays — the play sits on both tabs. --redo deletes that row (inside
# its date bound); a plain run only warns.

def test_redo_deletes_proxy_row_now_on_results_tab(monkeypatch, cache_dir, caplog):
    cand = _frozen_candidate()
    key = bt._identity_key(SIGNAL, "NVDA", cand["play"])
    outside = bt._identity_key(date(2026, 5, 1), "AMD", "long call 100 Jun 20")

    with caplog.at_level(logging.WARNING, logger="backtest"):
        calls = _run_main(monkeypatch, ["--date", SIGNAL.isoformat(), "--redo", "--cache-only"],
                          cand, {key, outside}, tested_keys={key, outside})

    assert not calls["written"]  # the play is tested: nothing re-evaluated
    tab, match_fn = calls["deleted"]
    assert tab == "BacktestProxy"
    # Sheets reparses the date into locale form (DD/MM); the key still matches.
    assert match_fn({"signal_date": "01/06/2026", "ticker": "nvda", "play": cand["play"]})
    # A cross-tab duplicate OUTSIDE the date bound is left alone.
    assert not match_fn({"signal_date": "2026-05-01", "ticker": "AMD",
                         "play": "long call 100 Jun 20"})
    assert "NVDA" in caplog.text and "Deleting" in caplog.text


def test_redo_dry_run_reports_cross_tab_duplicate_without_deleting(monkeypatch, cache_dir,
                                                                    caplog):
    cand = _frozen_candidate()
    key = bt._identity_key(SIGNAL, "NVDA", cand["play"])

    with caplog.at_level(logging.WARNING, logger="backtest"):
        calls = _run_main(monkeypatch,
                          ["--date", SIGNAL.isoformat(), "--redo", "--cache-only", "--dry-run"],
                          cand, {key}, tested_keys={key})

    assert calls["deleted"] is None
    assert "Would delete" in caplog.text


def test_plain_run_warns_on_cross_tab_duplicate_but_never_deletes(monkeypatch, cache_dir,
                                                                    caplog):
    cand = _frozen_candidate()
    key = bt._identity_key(SIGNAL, "NVDA", cand["play"])

    with caplog.at_level(logging.WARNING, logger="backtest"):
        calls = _run_main(monkeypatch, ["--date", SIGNAL.isoformat(), "--cache-only"],
                          cand, {key}, tested_keys={key})

    assert calls["deleted"] is None
    assert not calls["written"]
    assert "ALSO on" in caplog.text and "--redo" in caplog.text


def test_cross_tab_duplicates_respects_bound_and_unparsed_dates():
    k_in = bt._identity_key(SIGNAL, "NVDA", "a")
    k_out = bt._identity_key(date(2026, 7, 1), "NVDA", "a")
    k_proxy_only = bt._identity_key(SIGNAL, "AMD", "b")
    k_undated = (None, "SPY", "c")
    got = proxy._cross_tab_duplicates({k_in, k_out, k_proxy_only, k_undated},
                                      {k_in, k_out, k_undated}, SIGNAL, SIGNAL)
    assert got == {k_in}
    assert proxy._cross_tab_duplicates({k_in, k_out}, {k_in, k_out}, None, None) == {k_in, k_out}


def test_redo_requires_date_bounds(monkeypatch):
    monkeypatch.setattr("sys.argv", ["proxy", "--redo"])
    with pytest.raises(SystemExit):
        proxy.main()


# ── 11. exit_basis reaches the row (regression, 2026-09-02) ──────────────────────
# `exit_basis` is declared in _PROXY_KEY_ORDER via _BASIS_COLS, but _evaluate's
# copy loop iterated _RESULT_COLS alone, so no method's value ever reached the
# row: the whole BacktestProxy tab was blank in that column, in every era. The
# column names which exit profile governed a row (PROD/CREDIT/BEAR_DEBIT/a
# regime cell), so a study stratifying by profile would have read the entire
# proxy book as a single basis. See docs/backtest-reference.md `exit_basis`.

def test_evaluate_stamps_exit_basis_on_a_priced_tier(cache_dir):
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 255.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0),
        ("2026-06-02", 250.0, "45.0", "0.55", 15.0, 17.0),
    ])

    row = bt._evaluate(play, None, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-07-06T10:00:00", False)

    assert row["proxy_method"] == "strike_expiry_tweak"
    # A debit play outside every override cell — the base config governed it.
    assert row["exit_basis"] == "PROD"


def test_evaluate_stamps_none_on_the_direction_only_tier(cache_dir):
    # Method 3 runs no exit rules at all, so its basis is neither PROD nor a
    # cell. "NONE" is explicit precisely so it is not confused with blank.
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 400.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.50", 9.0, 11.0),
        ("2026-06-02", 260.0, "45.0", "0.50", 9.0, 11.0),
    ])

    row = bt._evaluate(play, None, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-08-11T10:00:00", False)

    assert row["proxy_method"] == "underlying_trend"
    assert row["exit_basis"] == "NONE"


def test_unevaluable_rows_carry_no_basis(cache_dir):
    # Nothing was simulated, so there is no profile to name. Blank, not "NONE".
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)

    row = bt._evaluate(play, None, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-08-11T10:00:00", False)

    assert row["proxy_method"] == "unevaluable"
    assert row.get("exit_basis", "") == ""


# ── 11. Cost columns reach the proxy row ────────────────────────────────────────

def test_evaluate_copies_cost_columns_onto_a_priced_row(cache_dir):
    """`_COST_COLS` joined the `_evaluate` copy loop on 2026-09-19.

    `_simulate` always stamped `pct_stale_days` / `cost_total` / `cost_basis`,
    and `_PROXY_KEY_ORDER` always declared them, but the loop copied only
    `_RESULT_COLS + _BASIS_COLS`, so every priced proxy row reached the tab
    blank in all three while BacktestResults carried them — the same shape as
    the `exit_basis` gap fixed 2026-09-02.
    """
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 255.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0),
        ("2026-06-02", 250.0, "45.0", "0.55", 9.8, 10.2),
        ("2026-06-03", 250.0, "45.0", "0.55", 15.0, 17.0),
    ])

    # Costs ON, so `cost_total` and `cost_basis` are both non-default and a
    # blank cell cannot be mistaken for the costs-off convention.
    sim_cfg = dict(_SIM_CFG, commission_per_contract=0.65,
                   slippage_frac_of_spread=0.25)
    row = bt._evaluate(play, None, c, _CFG, sim_cfg, _SPREAD_PCT,
                       "2026-07-06T10:00:00", False)

    assert row["proxy_method"] == "strike_expiry_tweak"
    assert row["cost_total"] > 0
    assert row["cost_basis"] != ""
    assert row["pct_stale_days"] != ""


def test_evaluate_leaves_cost_basis_blank_when_costs_are_off(cache_dir):
    """Costs off writes `cost_basis` empty and `cost_total` 0.0 — the same
    convention BacktestResults uses, so the copy must not invent a value."""
    c = _long_call_candidate()
    play, _reason = bt.classify_and_build(c, _SPREAD_PCT)
    _write_history(cache_dir, "NVDA", EXP, 255.0, "Call", [
        ("2026-06-01", 250.0, "45.0", "0.55", 8.0, 9.0),
        ("2026-06-02", 250.0, "45.0", "0.55", 15.0, 17.0),
    ])

    row = bt._evaluate(play, None, c, _CFG, _SIM_CFG, _SPREAD_PCT,
                       "2026-07-06T10:00:00", False)

    assert row["cost_basis"] == ""
    assert row["pct_stale_days"] != ""
