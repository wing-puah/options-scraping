"""Unit tests for the day-0 underlying-move tier: the bar loader
(`scripts/backtest_study/lib/underlying.py`) and the pieces of
`scripts/backtest_study/f2_management/next_day_move.py` that decide what a row means.

Everything is synthetic and written to tmp_path — nothing here reads the real
(gitignored) caches under backtests/ or touches the network, so these stay green
regardless of what has been scraped on the laptop.
"""
from datetime import date, timedelta

import pytest

from scripts.backtest.helpers import _weekday_grid
from scripts.backtest_study.f2_management import next_day_move as ndm
from scripts.backtest_study.lib import underlying as und
from scripts.backtest_study.lib.harness import Trade
from scripts.collector import fetch_underlying_ohlc as foh

SIGNAL = date(2024, 3, 4)      # Monday
EXPIRY = date(2024, 3, 15)     # Friday
DTE = (EXPIRY - SIGNAL).days
GRID = _weekday_grid(SIGNAL, SIGNAL + timedelta(days=min(DTE, 120)))

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
          "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")


def _ohlc_csv(rows) -> str:
    """rows = [(date, open, high, low, close)] -> a Barchart-schema history CSV."""
    out = [HEADER]
    for d, o, h, l, c in rows:
        out.append(f"{d.isoformat()},{o},{h},{l},{c},0,0%,100,0,,,,,,,,,,")
    return "\n".join(out) + "\n"


def _tilde_csv(rows) -> str:
    """rows = [(date, price_tilde)] -> an OPTION history CSV carrying `Price~`."""
    out = [HEADER]
    for d, p in rows:
        out.append(f"{d.isoformat()},1,1,1,1,0,0%,10,0,,,,,,,,{p},,")
    return "\n".join(out) + "\n"


@pytest.fixture(autouse=True)
def _isolate_caches(tmp_path, monkeypatch):
    """Point both cache dirs at tmp_path and clear every lru_cache.

    The loaders memoise per ticker, so without this a test would see whatever a
    previous test (or the real cache) had already loaded.
    """
    ohlc = tmp_path / "ohlc"
    opts = tmp_path / "opts"
    ohlc.mkdir()
    opts.mkdir()
    monkeypatch.setattr(und, "OHLC_CACHE", ohlc)
    monkeypatch.setattr(und, "RESCALED_FILE", ohlc / "rescaled_tickers.txt")
    monkeypatch.setattr(und, "HISTORY_CACHE", opts)
    for fn in (und._load_ohlc_cache, und._load_tilde, und.rescaled_tickers):
        fn.cache_clear()
    yield ohlc, opts
    for fn in (und._load_ohlc_cache, und._load_tilde, und.rescaled_tickers):
        fn.cache_clear()


def _trade(marks=None, entry=1.00, ticker="AAA") -> Trade:
    if marks is None:
        marks = [1.00] * len(GRID)
    row = {
        "signal_date": SIGNAL.isoformat(), "ticker": ticker, "structure": "long_call",
        "legs": f"{ticker}:{EXPIRY.isoformat()}:100:C +1", "contracts": "1",
        "dte_entry": str(DTE), "entry_option_price": str(entry),
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
    }
    return Trade(row)


# --- the loader ---------------------------------------------------------------

def test_ohlc_cache_is_parsed_with_full_bars(_isolate_caches):
    ohlc, _ = _isolate_caches
    (ohlc / "AAA.csv").write_text(_ohlc_csv([(date(2024, 3, 5), 10, 12, 9, 11)]))
    bars = und.load_bars("AAA")
    bar = bars[date(2024, 3, 5)]
    assert (bar.o, bar.h, bar.l, bar.c) == (10, 12, 9, 11)
    assert bar.source == und.SRC_OHLC and bar.has_ohlc


def test_falls_back_to_price_tilde_close_only(_isolate_caches):
    """No OHLC file -> Price~ from the option caches, with no open/high/low.

    This is the path that recovers positions with no short leg, which
    harness.Trade._load_underlying cannot see at all.
    """
    _, opts = _isolate_caches
    (opts / "AAA_20240315_100.00C.csv").write_text(
        _tilde_csv([(date(2024, 3, 5), 42.0)]))
    bars = und.load_bars("AAA")
    bar = bars[date(2024, 3, 5)]
    assert bar.c == 42.0
    assert bar.o is None and bar.h is None and bar.l is None
    assert bar.source == und.SRC_TILDE and not bar.has_ohlc


def test_ohlc_wins_over_tilde_when_both_exist(_isolate_caches):
    ohlc, opts = _isolate_caches
    (ohlc / "AAA.csv").write_text(_ohlc_csv([(date(2024, 3, 5), 10, 12, 9, 11)]))
    (opts / "AAA_20240315_100.00C.csv").write_text(
        _tilde_csv([(date(2024, 3, 5), 42.0)]))
    assert und.load_bars("AAA")[date(2024, 3, 5)].c == 11


def test_rescaled_ticker_keeps_its_ohlc(_isolate_caches):
    """A split-adjusted ticker is a BASIS warning, not a quarantine.

    Its ratios are valid (a constant factor cancels) and the unadjusted fallback
    is discontinuous at the ex-date, so diverting it there would be strictly
    worse on the measure the study actually uses.
    """
    ohlc, opts = _isolate_caches
    (ohlc / "rescaled_tickers.txt").write_text("# comment\nAAA\t0.9000\t93\n")
    (ohlc / "AAA.csv").write_text(_ohlc_csv([(date(2024, 3, 5), 10, 12, 9, 11)]))
    (opts / "AAA_20240315_100.00C.csv").write_text(
        _tilde_csv([(date(2024, 3, 5), 110.0)]))
    assert und.rescaled_tickers() == frozenset({"AAA"})
    assert und.load_bars("AAA")[date(2024, 3, 5)].c == 11


def test_rescaled_file_absent_is_empty_not_an_error(_isolate_caches):
    assert und.rescaled_tickers() == frozenset()


# --- entry-day resolution -----------------------------------------------------

def test_entry_day_is_the_first_grid_day_which_is_already_post_signal():
    """`_weekday_grid` is "weekdays AFTER the signal date", so marks[0] is the
    entry session itself — there is no pre-entry mark to skip past."""
    t = _trade()
    assert GRID[0] == SIGNAL + timedelta(days=1)
    assert und.entry_day(t, set(GRID)) == GRID[0]


def test_entry_day_skips_a_market_holiday():
    """The grid is weekday-based and marks carry forward, so a closed day looks
    like a fine entry. The bar series is the only trading calendar available."""
    t = _trade()
    sessions = set(GRID) - {GRID[0]}          # GRID[0] was a holiday
    assert und.entry_day(t, sessions) == GRID[1]


def test_entry_day_skips_a_day_with_no_mark():
    marks = [1.0] * len(GRID)
    marks[0] = None
    t = _trade(marks=marks)
    assert und.entry_day(t, set(GRID)) == GRID[1]


def test_entry_day_without_sessions_ignores_the_calendar():
    t = _trade()
    assert und.entry_day(t) == GRID[0]


def test_entry_day_refuses_to_anchor_across_a_gap_in_the_bar_series():
    """A holiday shifts entry a day or two. A week-long jump is missing DATA,
    and anchoring there would invent a fill that never happened."""
    t = _trade()
    late = {d for d in GRID if (d - SIGNAL).days > und.MAX_ENTRY_LAG_DAYS}
    assert und.entry_day(t, late) is None


# --- sigma normalisation ------------------------------------------------------

def test_sigma_1d_treats_iv_as_a_decimal_fraction():
    """`iv_entry_pct` holds a FRACTION (0.3295 = 33% IV), not points — passing
    points would understate the move 100x and collapse every sigma bucket."""
    assert und.sigma_1d(0.3295) == pytest.approx(0.3295 / (252 ** 0.5), rel=1e-9)


@pytest.mark.parametrize("bad", [None, 0, -0.5])
def test_sigma_1d_propagates_missing_iv(bad):
    """A missing sigma must stay missing, never silently become a bucket."""
    assert und.sigma_1d(bad) is None


# --- the three windows --------------------------------------------------------

def _bars_for_windows():
    """Signal day sits BEFORE the grid, since the grid starts at signal+1."""
    d0, d1 = GRID[0], GRID[1]
    return {
        SIGNAL: und.Bar(o=95.0, h=101.0, l=94.0, c=100.0),  # signal day
        d0: und.Bar(o=102.0, h=112.0, l=101.0, c=110.0),    # entry session
        d1: und.Bar(o=110.0, h=122.0, l=109.0, c=121.0),    # next session
    }


def test_move_windows_computes_all_three_plus_the_close_only_one():
    t = _trade()
    w = und.move_windows(t, _bars_for_windows())
    assert w["entry_day"] == GRID[0]
    assert w["W0"]["pct"] == pytest.approx((110 - 102) / 102)      # entry open->close
    assert w["W1"]["pct"] == pytest.approx((121 - 102) / 102)      # entry open->next close
    assert w["WG"]["pct"] == pytest.approx((102 - 100) / 100)      # signal close->entry open
    assert w["W1C"]["pct"] == pytest.approx((121 - 110) / 110)     # close->close
    assert w["W0"]["abs"] == pytest.approx(8.0)


def test_close_only_rows_yield_no_open_based_window():
    """A fallback row has no open, so W0/W1/WG are unavailable and only the
    close-to-close window survives. They must never be pooled."""
    bars = {SIGNAL: und.Bar(c=100.0, source=und.SRC_TILDE),
            GRID[0]: und.Bar(c=110.0, source=und.SRC_TILDE),
            GRID[1]: und.Bar(c=121.0, source=und.SRC_TILDE)}
    w = und.move_windows(_trade(), bars)
    assert w["W0"] is None and w["W1"] is None and w["WG"] is None
    assert w["W1C"]["pct"] == pytest.approx(0.1)


def test_split_discontinuity_on_the_fallback_path_is_not_reported_as_a_move():
    """`Price~` is unadjusted, so it steps 10x at an ex-split date. That is a
    corporate action, not a -90% session."""
    bars = {GRID[0]: und.Bar(c=1000.0, source=und.SRC_TILDE),
            GRID[1]: und.Bar(c=100.0, source=und.SRC_TILDE)}
    assert und.move_windows(_trade(), bars)["W1C"] is None


def test_bars_that_never_reach_the_grid_anchor_nothing():
    late = GRID[-1]
    w = und.move_windows(_trade(), {late: und.Bar(o=1, h=1, l=1, c=1)})
    assert w["W0"] is None and w["source"] is None and w["entry_day"] is None


# --- direction mapping --------------------------------------------------------

@pytest.mark.parametrize("structure,sign", [
    ("bull_call_spread", 1), ("bull_put_spread", 1), ("long_call", 1), ("short_put", 1),
    ("bear_put_spread", -1), ("bear_call_spread", -1), ("long_put", -1),
])
def test_direction_sign_maps_every_directional_structure(structure, sign):
    assert ndm.direction_sign(structure) == sign


@pytest.mark.parametrize("structure", ["straddle", "strangle", "iron_condor", ""])
def test_direction_sign_is_none_for_non_directional_structures(structure):
    """Vol structures have no direction to conform to and must not be forced
    into a conformity bucket."""
    assert ndm.direction_sign(structure) is None


def test_every_vol_structure_is_unmapped():
    assert all(ndm.direction_sign(s) is None for s in ndm.VOL_STRUCTURES)


def test_bullish_and_bearish_sets_do_not_overlap():
    assert not (ndm.BULLISH & ndm.BEARISH)


# --- the day-0 cut wrapper ----------------------------------------------------

def _rec(sigma_move, day0_i=2, day0_pnl=-0.10, structure="bear_put_spread",
         credit=False, marks=None):
    return {"t": _trade(marks=marks), "structure": structure, "credit": credit,
            "W0_sigma": sigma_move, "day0_i": day0_i, "day0_pnl": day0_pnl,
            "mech_cell": "PROD"}


PROFILE = dict(pt=0.90, sl=0.75, trig=None, trail=None, tef=0.75)


def test_cut_fires_when_the_stock_did_not_confirm():
    rec = _rec(sigma_move=-1.2)
    out = ndm.apply_day0_cut(rec, PROFILE, theta=0.0)
    assert out["exit_reason"] == "day0_cut"
    assert out["days_held"] == 2 and out["pnl_pct"] == -0.10


def test_cut_does_not_fire_when_the_stock_confirmed():
    rec = _rec(sigma_move=+1.2)
    assert ndm.apply_day0_cut(rec, PROFILE, theta=0.0)["exit_reason"] != "day0_cut"


def test_theta_none_is_the_untouched_shipped_replay():
    rec = _rec(sigma_move=-5.0)
    assert (ndm.apply_day0_cut(rec, PROFILE, None)
            == ndm.apply_day0_cut(rec, PROFILE, theta=None))


def test_missing_sigma_never_triggers_a_cut():
    """A row with no entry IV has no sigma; it must fall through to production
    rather than be treated as a non-confirmation."""
    rec = _rec(sigma_move=None)
    assert ndm.apply_day0_cut(rec, PROFILE, theta=0.0)["exit_reason"] != "day0_cut"


def test_cut_cannot_resurrect_a_position_production_already_closed():
    """Production stopping out on the signal day happens BEFORE the entry
    session, so a day-0 cut must not overwrite it with a later exit."""
    marks = [0.10] + [1.00] * (len(GRID) - 1)   # -90% on marks[0] -> stop_loss day 1
    rec = _rec(sigma_move=-2.0, day0_i=2, marks=marks)
    base = ndm.apply_day0_cut(rec, PROFILE, None)
    assert base["days_held"] == 1
    assert ndm.apply_day0_cut(rec, PROFILE, theta=0.0) == base


def test_keying_is_evaluated_inside_the_wrapper_not_by_prefiltering():
    """The leak guard is only a real test if a non-keyed row CAN be handed to
    the rule and is still left alone."""
    bear = _rec(sigma_move=-2.0, structure="bear_put_spread")
    bull = _rec(sigma_move=-2.0, structure="bull_call_spread")
    keyed = ndm.is_bear_debit
    assert ndm.apply_day0_cut(bear, PROFILE, 0.0, keyed_to=keyed)["exit_reason"] == "day0_cut"
    assert ndm.apply_day0_cut(bull, PROFILE, 0.0, keyed_to=keyed) == \
        ndm.apply_day0_cut(bull, PROFILE, None)


def test_credit_rows_take_the_credit_profile_not_the_debit_one():
    """config/backtest.yml: the structure_exit and regime_exit merges are
    debit-only ("Credits never reach it"). Replaying a credit under debit knobs
    is a baseline production does not run."""
    credit = ndm.shipped_profile(_rec(0.0, structure="bull_put_spread", credit=True))
    debit = ndm.shipped_profile(_rec(0.0, structure="bear_put_spread", credit=False))
    assert credit["pt"] == 0.65 and credit["sl"] is None
    assert debit["pt"] == 0.90 and debit["sl"] == 0.75


def test_bear_debit_keying_requires_both_structure_and_sign():
    assert ndm.is_bear_debit(_rec(0.0, structure="bear_put_spread", credit=False))
    assert not ndm.is_bear_debit(_rec(0.0, structure="bear_put_spread", credit=True))
    assert not ndm.is_bear_debit(_rec(0.0, structure="bull_call_spread", credit=False))


# --- fetch_underlying_ohlc.write_rescaled / recheck_rescaled ------------------
# The 2026-09-05 regression: a partial --tickers run rewrote rescaled_tickers.txt
# in full, dropping every ticker it hadn't just fetched. write_rescaled() now
# takes the set of tickers actually CHECKED this run and only touches those.

@pytest.fixture
def _isolate_foh_caches(tmp_path, monkeypatch):
    ohlc = tmp_path / "foh_ohlc"
    opts = tmp_path / "foh_opts"
    ohlc.mkdir()
    opts.mkdir()
    monkeypatch.setattr(foh, "OHLC_CACHE", ohlc)
    monkeypatch.setattr(foh, "RESCALED_FILE", ohlc / "rescaled_tickers.txt")
    monkeypatch.setattr(foh, "HISTORY_CACHE", opts)
    return ohlc, opts


def _rescaled_syms(text: str) -> dict[str, tuple[float, int]]:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        out[parts[0]] = (float(parts[1]), int(parts[2]))
    return out


def test_partial_run_keeps_prior_lines_for_unchecked_tickers(_isolate_foh_caches):
    """OLD_UNCHECKED wasn't touched this run and must survive verbatim."""
    ohlc, _ = _isolate_foh_caches
    foh.RESCALED_FILE.write_text(
        "# header\nOLD_UNCHECKED\t0.9000\t50\nFLAGGED_BEFORE\t0.8000\t60\n"
        "CLEAN_BEFORE\t0.6000\t70\n")
    foh.write_rescaled({"CLEAN_BEFORE": (0.6500, 71)},
                       checked={"FLAGGED_BEFORE", "CLEAN_BEFORE"})
    result = _rescaled_syms(foh.RESCALED_FILE.read_text())
    # unchecked ticker's prior line survives untouched
    assert result["OLD_UNCHECKED"] == (0.9000, 50)
    # checked-and-no-longer-flagged ticker is removed
    assert "FLAGGED_BEFORE" not in result
    # checked-and-flagged ticker gets this run's new verdict, not the old one
    assert result["CLEAN_BEFORE"] == (0.6500, 71)
    assert "merged with prior entries not re-checked this run" in foh.RESCALED_FILE.read_text()


def test_partial_run_can_newly_flag_a_previously_clean_ticker(_isolate_foh_caches):
    """unflagged -> flagged: a ticker with no prior line gets added when checked
    this run and found rescaled."""
    ohlc, _ = _isolate_foh_caches
    foh.RESCALED_FILE.write_text("# header\nKEEP_ME\t0.5000\t40\n")
    foh.write_rescaled({"NEWLY_FLAGGED": (0.7000, 20)},
                       checked={"NEWLY_FLAGGED"})
    result = _rescaled_syms(foh.RESCALED_FILE.read_text())
    assert result["KEEP_ME"] == (0.5000, 40)
    assert result["NEWLY_FLAGGED"] == (0.7000, 20)


def test_empty_run_writes_nothing(_isolate_foh_caches):
    """A run that fetched/checked nothing must not touch the file at all —
    not even to leave it byte-identical; the write call itself is skipped."""
    ohlc, _ = _isolate_foh_caches
    original = "# header\nSOMETHING\t0.9000\t10\n"
    foh.RESCALED_FILE.write_text(original)
    before_mtime = foh.RESCALED_FILE.stat().st_mtime_ns
    foh.write_rescaled({}, checked=set())
    assert foh.RESCALED_FILE.read_text() == original
    assert foh.RESCALED_FILE.stat().st_mtime_ns == before_mtime


def test_empty_run_with_no_existing_file_creates_nothing(_isolate_foh_caches):
    ohlc, _ = _isolate_foh_caches
    foh.write_rescaled({}, checked=set())
    assert not foh.RESCALED_FILE.exists()


def test_recheck_rewrites_in_full_dropping_stale_entries_not_in_cache(_isolate_foh_caches):
    """--recheck-rescaled's path (full_rewrite=True) is the one allowed to
    replace the whole file — including dropping a stale entry for a ticker
    that no longer has a cached CSV at all, since it checked everything that
    exists and that ticker isn't part of "everything"."""
    ohlc, opts = _isolate_foh_caches
    # Stale line for a ticker with no cached CSV any more.
    foh.RESCALED_FILE.write_text("# header\nGONE_TICKER\t0.9000\t10\n")

    # SPLIT1: OHLC close is ~10x the cached option Price~ -> flagged.
    (ohlc / "SPLIT1.csv").write_text(_ohlc_csv([(date(2024, 3, 5), 100, 100, 100, 100)]))
    (opts / "SPLIT1_20240315_100.00C.csv").write_text(
        _tilde_csv([(date(2024, 3, 5), 10.0)]))

    # CLEAN1: OHLC matches Price~ -> not flagged, but WAS checked.
    (ohlc / "CLEAN1.csv").write_text(_ohlc_csv([(date(2024, 3, 5), 50, 50, 50, 50)]))
    (opts / "CLEAN1_20240315_100.00C.csv").write_text(
        _tilde_csv([(date(2024, 3, 5), 50.0)]))

    rescaled = foh.recheck_rescaled()
    assert set(rescaled) == {"SPLIT1"}
    med, n = rescaled["SPLIT1"]
    assert med == pytest.approx(9.0)  # |100-10|/10
    assert n == 1

    foh.write_rescaled(rescaled, full_rewrite=True)
    text = foh.RESCALED_FILE.read_text()
    result = _rescaled_syms(text)
    assert set(result) == {"SPLIT1"}          # CLEAN1 not flagged, GONE_TICKER dropped
    assert "merged with prior entries" not in text  # full rewrite, nothing merged
