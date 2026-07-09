"""Tests for lib/price_catalyst.py: as-of price/earnings cell pickers (no
look-ahead), the flow-row read-back, and the deterministic play scoring rule.
Pure functions, no network."""
from datetime import date, timedelta

from lib.price_catalyst import (
    PRICE_CATALYST_ENRICH_COLUMNS,
    PRICE_CATALYST_MARKER_COLUMN,
    as_of_earnings_cells,
    as_of_price_cells,
    catalyst_read,
    compute_play_scores,
    price_catalyst_from_flow_rows,
    price_read,
)


# ---------------------------------------------------------------------------
# enrichment column contract
# ---------------------------------------------------------------------------

def test_enrich_column_contract():
    assert PRICE_CATALYST_ENRICH_COLUMNS == [
        "price_d", "price_5d_ago", "price_20d_high", "price_20d_low", "price_sma20",
        "price_50d_high", "price_50d_low", "price_sma50",
        "next_earnings", "last_earnings",
    ]
    assert PRICE_CATALYST_MARKER_COLUMN == "price_catalyst_enriched_on"


# ---------------------------------------------------------------------------
# as_of_price_cells
# ---------------------------------------------------------------------------

def _bars(start_day: int, count: int, price_fn=lambda i: 100.0 + i):
    """Build (date, price) bars for day-of-month start_day..start_day+count-1."""
    return [(date(2026, 6, start_day + i), price_fn(i)) for i in range(count)]


def test_as_of_price_cells_basic():
    # 10 ascending bars, June 1..10, trade_date = June 10 (last bar).
    series = _bars(1, 10)
    cells = as_of_price_cells(series, date(2026, 6, 10))
    assert cells["price_d"] == 109.0  # June 10 -> 100 + 9
    assert cells["price_5d_ago"] == 104.0  # June 5 -> 100 + 4 (index -6 from end)
    assert cells["price_20d_high"] == 109.0
    assert cells["price_20d_low"] == 100.0
    assert cells["price_sma20"] == sum(100.0 + i for i in range(10)) / 10
    # Only 10 bars available; the 50d window falls back to all of them, same as 20d.
    assert cells["price_50d_high"] == 109.0
    assert cells["price_50d_low"] == 100.0
    assert cells["price_sma50"] == sum(100.0 + i for i in range(10)) / 10


def test_as_of_price_cells_no_look_ahead():
    """A bar dated AFTER trade_date, with an extreme price, must never affect
    price_d, price_5d_ago, the 20d high/low, or the SMA."""
    series = _bars(1, 10)  # June 1..10
    trade_date = date(2026, 6, 10)
    baseline = as_of_price_cells(series, trade_date)

    future_series = series + [(date(2026, 6, 11), 999999.0)]
    with_future = as_of_price_cells(future_series, trade_date)

    assert with_future == baseline


def test_as_of_price_cells_fewer_than_six_bars_no_5d_ago():
    series = _bars(1, 3)
    cells = as_of_price_cells(series, date(2026, 6, 3))
    assert cells["price_5d_ago"] is None
    assert cells["price_d"] == 102.0


def test_as_of_price_cells_fewer_than_twenty_bars_uses_available():
    series = _bars(1, 10)
    cells = as_of_price_cells(series, date(2026, 6, 10))
    # Only 10 bars available; window is all of them.
    assert cells["price_20d_high"] == 109.0
    assert cells["price_20d_low"] == 100.0


def test_as_of_price_cells_fifty_day_window_wider_than_twenty_day():
    # 60 ascending bars: the 20d window only sees the last 20 (140..159), the
    # 50d window sees the last 50 (110..159) — distinct high/low/SMA.
    series = [(date(2026, 1, 1) + timedelta(days=i), 100.0 + i) for i in range(60)]
    trade_date = date(2026, 1, 1) + timedelta(days=59)
    cells = as_of_price_cells(series, trade_date)
    assert cells["price_20d_high"] == 159.0
    assert cells["price_20d_low"] == 140.0
    assert cells["price_50d_high"] == 159.0
    assert cells["price_50d_low"] == 110.0
    assert cells["price_sma50"] == sum(range(110, 160)) / 50


def test_as_of_price_cells_fewer_than_fifty_bars_uses_available():
    series = _bars(1, 10)
    cells = as_of_price_cells(series, date(2026, 6, 10))
    # Only 10 bars available; the 50d window falls back to all of them.
    assert cells["price_50d_high"] == 109.0
    assert cells["price_50d_low"] == 100.0


def test_as_of_price_cells_empty_series_all_none():
    cells = as_of_price_cells([], date(2026, 6, 10))
    assert cells == {
        "price_d": None, "price_5d_ago": None,
        "price_20d_high": None, "price_20d_low": None, "price_sma20": None,
        "price_50d_high": None, "price_50d_low": None, "price_sma50": None,
    }


def test_as_of_price_cells_no_bars_on_or_before_trade_date():
    series = [(date(2026, 6, 15), 100.0)]
    cells = as_of_price_cells(series, date(2026, 6, 1))
    assert cells["price_d"] is None


# ---------------------------------------------------------------------------
# as_of_earnings_cells
# ---------------------------------------------------------------------------

def test_as_of_earnings_cells_next_and_last():
    actions = [
        {"date": date(2026, 3, 18), "event_type": "Earnings", "value": 12.20},
        {"date": date(2026, 6, 24), "event_type": "Earnings", "value": 25.11},
        {"date": date(2026, 7, 6), "event_type": "Dividend", "value": 0.15},  # not Earnings
    ]
    cells = as_of_earnings_cells(actions, date(2026, 5, 1))
    assert cells == {"next_earnings": date(2026, 6, 24), "last_earnings": date(2026, 3, 18)}


def test_as_of_earnings_cells_exactly_on_trade_date_is_last_not_next():
    actions = [{"date": date(2026, 6, 24), "event_type": "Earnings", "value": 25.11}]
    cells = as_of_earnings_cells(actions, date(2026, 6, 24))
    assert cells == {"next_earnings": None, "last_earnings": date(2026, 6, 24)}


def test_as_of_earnings_cells_no_earnings():
    assert as_of_earnings_cells([], date(2026, 6, 24)) == {"next_earnings": None, "last_earnings": None}
    assert as_of_earnings_cells(None, date(2026, 6, 24)) == {"next_earnings": None, "last_earnings": None}


# ---------------------------------------------------------------------------
# price_catalyst_from_flow_rows
# ---------------------------------------------------------------------------

def test_price_catalyst_from_flow_rows_reads_back_first_occurrence():
    rows = [
        {
            "Symbol": "mu", "price_d": "109.0", "price_5d_ago": "104.0",
            "price_20d_high": "109.0", "price_20d_low": "100.0", "price_sma20": "104.5",
            "price_50d_high": "115.0", "price_50d_low": "95.0", "price_sma50": "103.2",
            "next_earnings": "2026-06-24", "last_earnings": "2026-03-18",
        },
        {"Symbol": "MU", "price_d": "999"},  # duplicate ticker row — ignored
    ]
    out = price_catalyst_from_flow_rows(rows)
    assert out["MU"]["price_d"] == 109.0
    assert out["MU"]["price_50d_high"] == 115.0
    assert out["MU"]["price_50d_low"] == 95.0
    assert out["MU"]["price_sma50"] == 103.2
    assert out["MU"]["next_earnings"] == date(2026, 6, 24)
    assert out["MU"]["last_earnings"] == date(2026, 3, 18)


def test_price_catalyst_from_flow_rows_blank_cells_are_none():
    rows = [{"Symbol": "KO", "price_d": "", "next_earnings": ""}]
    out = price_catalyst_from_flow_rows(rows)
    assert out["KO"]["price_d"] is None
    assert out["KO"]["next_earnings"] is None


def test_price_catalyst_from_flow_rows_empty():
    assert price_catalyst_from_flow_rows([]) == {}
    assert price_catalyst_from_flow_rows(None) == {}


# ---------------------------------------------------------------------------
# compute_play_scores
# ---------------------------------------------------------------------------

TRADE_DATE = date(2026, 6, 1)


def test_compute_play_scores_missing_key_level_zeros_price():
    cells = {"price_d": 100.0}
    play = {"direction": "bullish", "flow_intent": "DIRECTIONAL", "horizon": "60"}
    out = compute_play_scores(cells, play, TRADE_DATE)
    assert out["score_price"] == 0


def test_compute_play_scores_missing_price_d_zeros_price():
    cells = {}
    play = {"key_level": 100.0, "direction": "bullish", "flow_intent": "DIRECTIONAL", "horizon": "60"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 0


def test_compute_play_scores_catalyst_exactly_at_horizon_edge_inclusive():
    horizon = 60
    next_earnings = TRADE_DATE + timedelta(days=horizon)  # exactly at the edge
    cells = {"next_earnings": next_earnings, "last_earnings": None}
    play = {"flow_intent": "DIRECTIONAL", "horizon": str(horizon)}
    out = compute_play_scores(cells, play, TRADE_DATE)
    assert out["score_catalyst"] == 15  # full max for DIRECTIONAL


def test_compute_play_scores_catalyst_one_day_past_horizon_is_zero():
    horizon = 60
    next_earnings = TRADE_DATE + timedelta(days=horizon + 1)
    cells = {"next_earnings": next_earnings, "last_earnings": None}
    play = {"flow_intent": "DIRECTIONAL", "horizon": str(horizon)}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_catalyst"] == 0


def test_compute_play_scores_catalyst_last_earnings_half_credit_at_edge():
    horizon = 60
    last_earnings = TRADE_DATE - timedelta(days=horizon)  # exactly at the edge
    cells = {"next_earnings": None, "last_earnings": last_earnings}
    play = {"flow_intent": "DIRECTIONAL", "horizon": str(horizon)}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_catalyst"] == 7  # 15 // 2


def test_compute_play_scores_catalyst_missing_horizon_is_zero():
    cells = {"next_earnings": TRADE_DATE + timedelta(days=1)}
    play = {"flow_intent": "DIRECTIONAL"}  # no horizon
    assert compute_play_scores(cells, play, TRADE_DATE)["score_catalyst"] == 0


def test_compute_play_scores_bullish_full_credit():
    cells = {"price_d": 110.0, "price_5d_ago": 105.0}
    play = {"key_level": 100.0, "direction": "bullish", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 20


def test_compute_play_scores_bullish_level_held_no_followthrough():
    # Above level but not trending up. Key-level (0.30) outweighs 5d follow-through
    # (0.15, demoted per Jegadeesh/Lehmann short-term reversal), so with only these
    # two inputs present the renormalized fraction is 0.30/0.45 -> 13, not the old
    # equal-partner 10.
    cells = {"price_d": 110.0, "price_5d_ago": 115.0}
    play = {"key_level": 100.0, "direction": "bullish", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 13


def test_compute_play_scores_bearish_full_credit():
    cells = {"price_d": 90.0, "price_5d_ago": 95.0}
    play = {"key_level": 100.0, "direction": "bearish", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 20


def test_compute_play_scores_neutral_within_pin_band_full_credit():
    cells = {"price_d": 101.0}  # within 3% of 100
    play = {"key_level": 100.0, "direction": "neutral", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 20


def test_compute_play_scores_neutral_outside_pin_band_zero():
    cells = {"price_d": 110.0}  # 10% away from 100
    play = {"key_level": 100.0, "direction": "neutral", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 0


def test_compute_play_scores_missing_direction_treated_as_neutral():
    cells = {"price_d": 100.5}
    play = {"key_level": 100.0, "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 20


def test_compute_play_scores_volatility_point_caps():
    cells = {"price_d": 110.0, "price_5d_ago": 105.0, "next_earnings": TRADE_DATE + timedelta(days=5)}
    play = {"key_level": 100.0, "direction": "bullish", "flow_intent": "VOLATILITY", "horizon": "14"}
    out = compute_play_scores(cells, play, TRADE_DATE)
    assert out["score_price"] == 10  # VOLATILITY price max is 10, not 20
    assert out["score_catalyst"] == 20  # VOLATILITY catalyst max is 20, not 15


def test_compute_play_scores_hedge_and_synthetic_stock_use_directional_caps():
    cells = {"price_d": 110.0, "price_5d_ago": 105.0}
    for intent in ("HEDGE", "SYNTHETIC STOCK"):
        play = {"key_level": 100.0, "direction": "bullish", "flow_intent": intent, "horizon": "14"}
        assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 20


def test_score_price_bullish_all_columns_confirm_full_credit():
    cells = {"price_d": 120.0, "price_5d_ago": 110.0, "price_sma20": 112.0, "price_sma50": 108.0,
             "price_20d_high": 121.0, "price_20d_low": 100.0,
             "price_50d_high": 120.0, "price_50d_low": 90.0}  # price_d == 50d high -> nearness 1.0
    play = {"key_level": 115.0, "direction": "bullish", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 20


def test_score_price_bearish_all_columns_confirm_full_credit():
    cells = {"price_d": 90.0, "price_5d_ago": 100.0, "price_sma20": 98.0, "price_sma50": 104.0,
             "price_20d_high": 110.0, "price_20d_low": 90.0,
             "price_50d_high": 120.0, "price_50d_low": 90.0}  # price_d == 50d low -> nearness 1.0
    play = {"key_level": 95.0, "direction": "bearish", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 20


def test_score_price_bullish_mixed_signals_graded():
    # key held (0.30) + trend vs sma20 (0.15) + mid-range nearness (0.25 * 0.5),
    # follow-through and sma-alignment fail -> 0.575 * 20 = 11.5 -> half-up 12.
    cells = {"price_d": 110.0, "price_5d_ago": 115.0, "price_sma20": 105.0, "price_sma50": 106.0,
             "price_50d_high": 130.0, "price_50d_low": 90.0}
    play = {"key_level": 100.0, "direction": "bullish", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 12


def test_score_price_nearness_falls_back_to_20d_window_when_50d_missing():
    # No 50d columns (older enriched file): nearness comes from the 20d range.
    # price_d at the 20d LOW on a bullish play -> nearness 0 drags the score down
    # (0.30 / 0.55 -> 11); if the fallback were dropped instead, key-level alone
    # would renormalize to a perfect 20.
    cells = {"price_d": 101.0, "price_20d_high": 120.0, "price_20d_low": 101.0}
    play = {"key_level": 100.0, "direction": "bullish", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 11


def test_score_price_missing_sma50_only_renormalizes():
    # sma-alignment needs both SMAs so it drops; the rest renormalize over 0.85:
    # key + nearness + trend pass, follow-through fails -> 0.70 / 0.85 -> 16.
    cells = {"price_d": 110.0, "price_5d_ago": 115.0, "price_sma20": 105.0,
             "price_20d_high": 110.0, "price_20d_low": 100.0}
    play = {"key_level": 100.0, "direction": "bullish", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 16


def test_score_price_degenerate_flat_window_gives_half_nearness():
    # high == low -> nearness 0.5, not a crash: (0.30 + 0.25*0.5) / 0.55 -> 15.
    cells = {"price_d": 100.0, "price_50d_high": 100.0, "price_50d_low": 100.0}
    play = {"key_level": 100.0, "direction": "bullish", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 15


def test_score_price_neutral_graded_pin_decay():
    # distance = 1.5x band -> pin credit 0.5; only the pin has data -> 10.
    cells = {"price_d": 104.5}
    play = {"key_level": 100.0, "direction": "neutral", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 10


def test_score_price_neutral_structure_credit_without_pin():
    # Pin missed outright (distance > 2x band) but price sits at its 20d mean, the
    # level is inside the 20d range, and 5d drift is small -> 0.50 fraction -> 10.
    cells = {"price_d": 110.0, "price_5d_ago": 112.0, "price_sma20": 109.0,
             "price_20d_high": 115.0, "price_20d_low": 95.0}
    play = {"key_level": 100.0, "direction": "neutral", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 10


def test_score_price_rounds_half_up_not_bankers():
    # VOLATILITY max 10: key held (0.30) + trend vs sma20 (0.15), nearness 0 (at the
    # 50d low), follow-through and alignment fail -> 0.45 * 10 = 4.5 -> 5 (banker's
    # round() would give 4).
    cells = {"price_d": 110.0, "price_5d_ago": 115.0, "price_sma20": 105.0, "price_sma50": 106.0,
             "price_50d_high": 150.0, "price_50d_low": 110.0}
    play = {"key_level": 100.0, "direction": "bullish", "flow_intent": "VOLATILITY", "horizon": "14"}
    assert compute_play_scores(cells, play, TRADE_DATE)["score_price"] == 5


def test_score_price_neutral_key_level_zero_no_division_error():
    play = {"key_level": 0.0, "direction": "neutral", "flow_intent": "DIRECTIONAL", "horizon": "14"}
    assert compute_play_scores({"price_d": 0.0}, play, TRADE_DATE)["score_price"] == 20  # exact match
    assert compute_play_scores({"price_d": 1.0}, play, TRADE_DATE)["score_price"] == 0


# ---------------------------------------------------------------------------
# price_read — the single signed price-trend vector (rollup surface + score reuse)
# ---------------------------------------------------------------------------

def test_price_read_all_bullish_signals_max_positive():
    # Every sub-signal confirms in the bullish frame -> vector +1.0.
    cells = {"price_d": 120.0, "price_5d_ago": 110.0, "price_sma20": 112.0, "price_sma50": 108.0,
             "price_20d_high": 121.0, "price_20d_low": 100.0,
             "price_50d_high": 120.0, "price_50d_low": 90.0}  # price_d == 50d high -> nearness 1.0
    assert price_read(cells) == 1.0


def test_price_read_all_bearish_signals_max_negative():
    # A downtrend reads as every bullish-frame sub-signal failing -> vector -1.0.
    cells = {"price_d": 90.0, "price_5d_ago": 100.0, "price_sma20": 98.0, "price_sma50": 104.0,
             "price_20d_high": 110.0, "price_20d_low": 90.0,
             "price_50d_high": 120.0, "price_50d_low": 90.0}  # price_d == 50d low -> nearness 0.0
    assert price_read(cells) == -1.0


def test_price_read_mixed_signals_between_bounds():
    # nearness 0.5 + trend pass, sma-align + follow-through fail -> 0.275/0.70 bull
    # fraction -> vector 2*0.3929 - 1 = -0.21 (same blend _score_price weights).
    cells = {"price_d": 110.0, "price_5d_ago": 115.0, "price_sma20": 105.0, "price_sma50": 106.0,
             "price_50d_high": 130.0, "price_50d_low": 90.0}
    assert round(price_read(cells), 2) == -0.21


def test_price_read_flat_window_is_zero():
    # Only nearness has data and the window is flat -> nearness 0.5 -> vector 0.0.
    cells = {"price_d": 100.0, "price_50d_high": 100.0, "price_50d_low": 100.0}
    assert price_read(cells) == 0.0


def test_price_read_none_when_price_d_missing():
    assert price_read({}) is None
    assert price_read({"price_5d_ago": 100.0}) is None


def test_price_read_none_when_no_subsignals_present():
    # price_d present but nothing to compare it against -> None, never a spurious -1.
    assert price_read({"price_d": 100.0}) is None


def test_price_read_sign_agrees_with_score_price_direction():
    # The vector's sign matches which play direction _score_price rewards on the
    # same cells — the reuse guarantee: a bullish trend scores the bullish play
    # higher than the bearish one, and price_read is positive.
    cells = {"price_d": 120.0, "price_5d_ago": 110.0, "price_sma20": 112.0, "price_sma50": 108.0,
             "price_50d_high": 120.0, "price_50d_low": 90.0}
    assert price_read(cells) > 0
    bull = compute_play_scores(cells, {"key_level": 100.0, "direction": "bullish",
                                       "flow_intent": "DIRECTIONAL", "horizon": "14"}, TRADE_DATE)
    bear = compute_play_scores(cells, {"key_level": 100.0, "direction": "bearish",
                                       "flow_intent": "DIRECTIONAL", "horizon": "14"}, TRADE_DATE)
    assert bull["score_price"] > bear["score_price"]


# ---------------------------------------------------------------------------
# catalyst_read — earnings proximity as day-deltas
# ---------------------------------------------------------------------------

def test_catalyst_read_day_deltas():
    cells = {"next_earnings": date(2026, 6, 24), "last_earnings": date(2026, 3, 18)}
    cat = catalyst_read(cells, date(2026, 6, 1))
    assert cat["days_to_next_earnings"] == 23   # 6/24 − 6/1
    assert cat["days_since_last_earnings"] == 75  # 6/1 − 3/18
    assert cat["next_earnings"] == date(2026, 6, 24)
    assert cat["last_earnings"] == date(2026, 3, 18)


def test_catalyst_read_missing_dates_are_none():
    cat = catalyst_read({}, date(2026, 6, 1))
    assert cat["days_to_next_earnings"] is None and cat["days_since_last_earnings"] is None
    assert catalyst_read(None, date(2026, 6, 1))["days_to_next_earnings"] is None
