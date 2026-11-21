"""Unit tests for scripts/journal/greeks.py — the Barchart fallback for the open
book's greeks when a pull (e.g. an IBKR Flex CSV) carries none.

Everything here is synthetic; a fake `session` object supplies canned Barchart
CSV text through the one `fetch_history_fast(url, timeout_ms)` call `enrich()`
ever makes, so no test opens a browser or touches the network — the same
convention `tests/test_counterpart_history.py` uses for the scrape script this
module's per-contract fetch is modelled on.
"""
from datetime import date

import pytest

from scripts.journal.lib import rawpull
from scripts.journal.lib import greeks
from scripts.journal.config import DELTA_SOURCE_BARCHART, DELTA_SOURCE_UNAVAILABLE

HEADER = ("Time,Open,High,Low,Latest,Change,%Change,Volume,Open Int,IV,Delta,"
          "Gamma,Theta,Vega,Rho,Theo,Price~,Bid,Ask")

CONID = 111
SYMBOL = "AAA"
EXPIRY = date(2026, 9, 18)
STRIKE = 100.0
AS_OF = date(2026, 8, 14)


def _opt_row(d: date, iv="", delta="", gamma="", theta="", vega="") -> str:
    fields = [d.isoformat(), "1.00", "1.10", "0.90", "1.00", "0", "0%", "10", "5",
              str(iv), str(delta), str(gamma), str(theta), str(vega), "", "", "", "", ""]
    return ",".join(fields)


def _opt_csv(rows) -> str:
    """rows = [(date, iv, delta, gamma, theta, vega)] -> an option-history CSV."""
    return "\n".join([HEADER] + [_opt_row(*r) for r in rows]) + "\n"


def _under_row(d: date, latest) -> str:
    fields = [d.isoformat(), "1.00", "1.10", "0.90", str(latest), "0", "0%", "10", "5",
              "", "", "", "", "", "", "", "", "", ""]
    return ",".join(fields)


def _under_csv(rows) -> str:
    """rows = [(date, latest)] -> an underlying (stock) history CSV."""
    return "\n".join([HEADER] + [_under_row(*r) for r in rows]) + "\n"


class _Session:  # pylint: disable=too-few-public-methods
    """Fake BarchartSession: routes on '%7C' (present only in the option URL,
    lib.barchart.options.option_history_url's pipe-encoded contract string)."""

    def __init__(self, option_csv=None, underlying_csv=None):
        self.option_csv = option_csv
        self.underlying_csv = underlying_csv
        self.calls: list[str] = []

    async def fetch_history_fast(self, url, _timeout_ms):
        self.calls.append(url)
        return self.option_csv if "%7C" in url else self.underlying_csv


class _NeverCalledSession:  # pylint: disable=too-few-public-methods
    async def fetch_history_fast(self, url, _timeout_ms):
        raise AssertionError(f"dry_run must not fetch, but was asked for {url}")


def _raw(positions=None, contracts=None) -> dict:
    return {
        "schema_version": rawpull.SCHEMA_VERSION,
        "pulled_at_utc": "2026-08-14T20:00:00Z",
        "trade_date": "2026-08-14",
        "source": "flex-csv",
        "trades": [],
        "positions": positions or [],
        "contracts": contracts or {},
    }


def _one_position_raw() -> dict:
    return _raw(
        positions=[{"conid": CONID, "position": 1, "avg_cost": 1.0,
                    "mkt_price": 1.0, "unrealized_pnl": 0.0}],
        contracts={str(CONID): {"symbol": SYMBOL, "sec_type": "OPT", "strike": STRIKE,
                                "expiry": EXPIRY.isoformat(), "right": "C",
                                "multiplier": 100}},
    )


# --------------------------------------------------------------------------
# Normal enrichment
# --------------------------------------------------------------------------
def test_normal_enrichment_sources_delta_and_iv_in_points():
    raw = _one_position_raw()
    session = _Session(
        option_csv=_opt_csv([(AS_OF, 45.20, 0.62, 0.01, -0.05, 0.10)]),
        underlying_csv=_under_csv([(AS_OF, 187.34)]),
    )

    result = greeks.enrich(raw, as_of=AS_OF, session=session)

    g = result["greeks"][str(CONID)]
    assert g["source"] == DELTA_SOURCE_BARCHART
    assert g["delta"] == pytest.approx(0.62)
    assert g["gamma"] == pytest.approx(0.01)
    assert g["theta"] == pytest.approx(-0.05)
    assert g["vega"] == pytest.approx(0.10)
    # IV stays in POINTS (45.20, not 0.4520) — the repo's documented exception
    # to the decimal-fraction convention (see s04a_report.py's iv_fmt()).
    assert g["iv"] == pytest.approx(45.20)
    assert result["underlying_prices"]["AAA"] == pytest.approx(187.34)

    # The input dict is never mutated, and it never carried "greeks" to begin with.
    assert "greeks" not in raw
    assert result is not raw
    rawpull.validate(result)  # enrich() already calls this; re-check it holds


# --------------------------------------------------------------------------
# No Barchart data at all for the contract
# --------------------------------------------------------------------------
def test_contract_with_no_barchart_data_stays_unavailable_never_zero():
    raw = _one_position_raw()
    session = _Session(option_csv=None, underlying_csv=_under_csv([(AS_OF, 187.34)]))

    result = greeks.enrich(raw, as_of=AS_OF, session=session)

    g = result["greeks"][str(CONID)]
    assert g == {"delta": None, "gamma": None, "theta": None, "vega": None,
                 "iv": None, "source": DELTA_SOURCE_UNAVAILABLE}


# --------------------------------------------------------------------------
# The sharp edge: a genuinely 0.0 delta is a real, sourced value
# --------------------------------------------------------------------------
def test_zero_delta_is_kept_as_a_real_sourced_value():
    raw = _one_position_raw()
    session = _Session(
        option_csv=_opt_csv([(AS_OF, 12.0, 0.0, 0.0, -0.01, 0.02)]),
        underlying_csv=_under_csv([(AS_OF, 187.34)]),
    )

    result = greeks.enrich(raw, as_of=AS_OF, session=session)

    g = result["greeks"][str(CONID)]
    assert g["source"] == DELTA_SOURCE_BARCHART
    assert g["delta"] == 0.0
    assert g["delta"] is not None


# --------------------------------------------------------------------------
# As-of fallback: latest row ON OR BEFORE as_of
# --------------------------------------------------------------------------
def test_as_of_fallback_picks_latest_row_on_or_before_the_date():
    raw = _one_position_raw()
    older = date(2026, 8, 12)
    newer = date(2026, 8, 13)  # closest row before AS_OF (2026-08-14); no exact match
    session = _Session(
        option_csv=_opt_csv([
            (older, 40.0, 0.50, 0.01, -0.04, 0.09),
            (newer, 42.0, 0.55, 0.01, -0.04, 0.09),
        ]),
        underlying_csv=_under_csv([(newer, 186.00)]),
    )

    result = greeks.enrich(raw, as_of=AS_OF, session=session)

    g = result["greeks"][str(CONID)]
    assert g["delta"] == pytest.approx(0.55)   # from `newer`, not `older`
    assert g["iv"] == pytest.approx(42.0)
    assert result["underlying_prices"]["AAA"] == pytest.approx(186.00)


# --------------------------------------------------------------------------
# No-lookahead: a row dated AFTER as_of is never selected
# --------------------------------------------------------------------------
def test_row_after_as_of_is_never_selected():
    raw = _one_position_raw()
    future = date(2026, 8, 15)  # one calendar day AFTER as_of
    session = _Session(
        option_csv=_opt_csv([(future, 45.0, 0.60, 0.01, -0.05, 0.10)]),
        underlying_csv=_under_csv([(future, 190.00)]),
    )

    result = greeks.enrich(raw, as_of=AS_OF, session=session)

    g = result["greeks"][str(CONID)]
    assert g["source"] == DELTA_SOURCE_UNAVAILABLE
    assert g["delta"] is None
    # The future-dated underlying row is withheld the same way — no lookahead spot.
    assert "AAA" not in result["underlying_prices"]


# --------------------------------------------------------------------------
# dry_run performs no network call at all
# --------------------------------------------------------------------------
def test_dry_run_touches_no_network_and_returns_input_unchanged():
    raw = _one_position_raw()
    session = _NeverCalledSession()

    result = greeks.enrich(raw, as_of=AS_OF, dry_run=True, session=session)

    assert result is raw
    assert "greeks" not in result
    assert "underlying_prices" not in result


def test_dry_run_with_no_open_positions_is_a_trivial_no_op():
    raw = _raw()
    result = greeks.enrich(raw, as_of=AS_OF, dry_run=True, session=_NeverCalledSession())
    assert result is raw


# --------------------------------------------------------------------------
# Cache freshness (2026-11-21: laptop runs priced QQQ at a months-old close)
# --------------------------------------------------------------------------

def _seed_underlying(tmp_path, rows):
    path = tmp_path / f"{SYMBOL}_underlying.csv"
    path.write_text(_under_csv(rows), encoding="utf-8")
    return path


def _enrich_with_cache(tmp_path, session):
    return greeks.enrich(_one_position_raw(), as_of=AS_OF, cache_dir=tmp_path,
                         session=session)


def test_stale_cached_underlying_is_refetched_and_replaced(tmp_path):
    path = _seed_underlying(tmp_path, [(date(2026, 7, 1), 50.0), (date(2026, 7, 2), 51.0)])
    fresh = _under_csv([(date(2026, 7, 1), 50.0), (date(2026, 7, 2), 51.0),
                        (AS_OF, 99.0)])
    session = _Session(option_csv=_opt_csv([(AS_OF, "40%", "0.5", "", "", "")]),
                       underlying_csv=fresh)
    out = _enrich_with_cache(tmp_path, session)
    assert out["underlying_prices"][SYMBOL] == 99.0
    assert any("%7C" not in u for u in session.calls)
    assert path.read_text(encoding="utf-8") == fresh


def test_fresh_cached_underlying_is_not_refetched(tmp_path):
    _seed_underlying(tmp_path, [(AS_OF, 77.0)])
    session = _Session(option_csv=_opt_csv([(AS_OF, "40%", "0.5", "", "", "")]),
                       underlying_csv=_under_csv([(AS_OF, 1.0)]))
    out = _enrich_with_cache(tmp_path, session)
    assert out["underlying_prices"][SYMBOL] == 77.0
    assert all("%7C" in u for u in session.calls)


def test_weekend_as_of_accepts_friday_row(tmp_path):
    friday = date(2026, 11, 20)
    _seed_underlying(tmp_path, [(friday, 77.0)])
    session = _Session(option_csv=_opt_csv([(friday, "40%", "0.5", "", "", "")]),
                       underlying_csv=_under_csv([(friday, 1.0)]))
    out = greeks.enrich(_one_position_raw(), as_of=date(2026, 11, 22),
                        cache_dir=tmp_path, session=session)
    assert out["underlying_prices"][SYMBOL] == 77.0
    assert all("%7C" in u for u in session.calls)


def test_shorter_refetch_never_shrinks_the_cached_history(tmp_path):
    old_rows = [(date(2026, 1, 2), 10.0), (date(2026, 7, 2), 51.0)]
    path = _seed_underlying(tmp_path, old_rows)
    session = _Session(option_csv=_opt_csv([(AS_OF, "40%", "0.5", "", "", "")]),
                       underlying_csv=_under_csv([(AS_OF, 99.0)]))
    out = _enrich_with_cache(tmp_path, session)
    assert out["underlying_prices"][SYMBOL] == 99.0
    assert path.read_text(encoding="utf-8") == _under_csv(old_rows)


def test_failed_refetch_falls_back_to_the_stale_cache(tmp_path):
    _seed_underlying(tmp_path, [(date(2026, 7, 2), 51.0)])
    session = _Session(option_csv=_opt_csv([(AS_OF, "40%", "0.5", "", "", "")]),
                       underlying_csv=None)
    out = _enrich_with_cache(tmp_path, session)
    assert out["underlying_prices"][SYMBOL] == 51.0


def test_stale_cached_option_history_is_refetched(tmp_path):
    from lib.barchart import options as barchart_options
    opt_path = barchart_options.cache_path(tmp_path, SYMBOL, EXPIRY, STRIKE, "Call")
    opt_path.write_text(_opt_csv([(date(2026, 7, 2), "30%", "0.2", "", "", "")]),
                        encoding="utf-8")
    session = _Session(option_csv=_opt_csv([(date(2026, 7, 2), "30%", "0.2", "", "", ""),
                                            (AS_OF, "45%", "0.6", "", "", "")]),
                       underlying_csv=_under_csv([(AS_OF, 99.0)]))
    out = _enrich_with_cache(tmp_path, session)
    assert out["greeks"][str(CONID)]["delta"] == 0.6
