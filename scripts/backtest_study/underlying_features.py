"""Underlying price-STATE features at entry — the new column family for the study tier.

Infrastructure, not a study. Listed in `run.py`'s INFRA, same as `underlying.py`.

WHY THIS EXISTS AT ALL
----------------------
Every column the book has argued about so far came from the option tape or from
a cross-sectional equity-return paper, and the 07-21 sweep left exactly three
standing: `delta` and `dte` (bull_put) and `iv_spread` (bear_put). The ML
combination search then returned a clean null across 15 model x strategy cells
and pre-committed to re-opening **only on new COLUMNS, never on new models**.

This module is that re-open. `underlying.py` landed real daily O/H/L/C for 104
tickers, which makes a whole family computable for the first time: realized
vol, its downside half, a high-low range estimator, an ATR, a trend-vs-chop
ratio, and the gap between implied and realized vol. None of it existed when
B1 searched 496 subsets, so none of it was in that search.

`vrp` deserves a specific note. Of the eleven reference papers, ten are
cross-sectional predictors validated on decile sorts over thousands of names
and decades; this book's effective sample is the DATE count (~118), which is
why they keep dying. Paper 11 (forecasting volatility) is the only time-series
result in the set — it finds a simple EWMA/MA vol estimate is not beaten by
GARCH for an option-pricing loss — and a small-sample time-series result is the
only kind this book can actually test. `vrp` is that hook, and it closes the
reference set.

NO LOOK-AHEAD
-------------
Every function takes an `as_of` date and reads only bars ON OR BEFORE it. The
features describe what was knowable at entry; a feature that peeked would make
any conditioning rule built on it unimplementable live, which is the whole
point of computing them. `lib/price_catalyst.py` holds the same invariant for
the production scorer, and its `as_of_price_cells` already covers 20/50-bar
high-low nearness — that is deliberately NOT duplicated here.

COVERAGE IS PART OF THE ANSWER
------------------------------
`rv_park` and `atr14_pct` need a high and a low, so they exist only on the
`SRC_OHLC` path; on `underlying.py`'s close-only `Price~` fallback they are
None. That means they carry a DIFFERENT DENOMINATOR from `rv20`/`eff_ratio`,
and a study that pools the two misstates every mean it quotes. `coverage()`
exists so a report can print the split rather than silently dropping rows.

Split-adjusted tickers are fine here: every feature is a ratio of two points on
the same series, and a constant scale factor cancels. Nothing in this module is
$-denominated, so `underlying.rescaled_tickers()` is not a filter for it — see
`underlying.py`'s module docstring for which cells DO need that exclusion.

Pure functions over bar sequences, plus one cached market-series loader. No
globals, no model imports.
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.underlying import (  # noqa: E402
    SRC_OHLC, TRADING_DAYS_PER_YEAR, Bar,
)

MARKET_SERIES = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"

# Window lengths. Standard rather than tuned: 20 sessions is a month of tape and
# is what `lib/price_catalyst.py` already uses for its trailing window, 14 is
# Wilder's ATR default, 60 is a quarter for the market-beta fit. These are NOT
# knobs to sweep — a study that sweeps them is searching, and the pre-registered
# gate lists in the plan are short on purpose.
RV_WINDOW = 20
ATR_WINDOW = 14
EFF_WINDOW = 20
BETA_WINDOW = 60

# Minimum usable observations per feature. Below this the estimator is noise
# dressed as a number, and returning None keeps it out of a bucket rather than
# letting a 3-bar "realized vol" set a tercile boundary.
_MIN_RV_OBS = 15
_MIN_ATR_OBS = 10
_MIN_EFF_OBS = 15
_MIN_BETA_OBS = 40

# A single-session log return larger than this is treated as a data artifact,
# not a move. `underlying.py` guards the same failure on the close-only path
# (`_SPLIT_ARTIFACT_PCT`) because an unadjusted `Price~` series steps by the
# split ratio at an ex-date; a 10x step here would otherwise dominate any
# realized-vol mean it landed in. Real earnings gaps sit well inside it.
_MAX_ABS_LOG_RETURN = 0.30

_ANNUALIZE = math.sqrt(TRADING_DAYS_PER_YEAR)


# ── bar selection ────────────────────────────────────────────────────────────

def trailing_bars(bars: dict[date, Bar], as_of: date, n: int) -> list[Bar]:
    """The last `n` bars on or before `as_of`, oldest first.

    The no-look-ahead gate for this whole module: every feature below consumes
    this and nothing else, so the `<= as_of` comparison lives in exactly one
    place.
    """
    days = sorted(d for d in bars if d <= as_of)
    return [bars[d] for d in days[-n:]] if days else []


def _closes(bars: list[Bar]) -> list[float]:
    return [b.c for b in bars if b.c and b.c > 0]


def _log_returns(closes: list[float]) -> list[float]:
    """Session log returns, with split-artifact steps dropped rather than clipped.

    Dropping beats winsorizing here: a clipped 10x step still contributes a
    fabricated 30% session to the mean, whereas a dropped one only costs an
    observation, and `_MIN_*_OBS` already refuses to score a series that lost
    too many.
    """
    out = []
    for prev, cur in zip(closes, closes[1:]):
        if prev <= 0 or cur <= 0:
            continue
        r = math.log(cur / prev)
        if abs(r) > _MAX_ABS_LOG_RETURN:
            continue
        out.append(r)
    return out


# ── volatility features ──────────────────────────────────────────────────────

def rv20(bars: dict[date, Bar], as_of: date) -> float | None:
    """Annualised close-to-close realized vol over `RV_WINDOW` sessions.

    Returned as a DECIMAL FRACTION (0.33 = 33% vol), matching the units of the
    book's `iv_entry_pct` — see `vrp` for why that matters.
    """
    rets = _log_returns(_closes(trailing_bars(bars, as_of, RV_WINDOW + 1)))
    if len(rets) < _MIN_RV_OBS:
        return None
    return statistics.pstdev(rets) * _ANNUALIZE


def rv_parkinson(bars: dict[date, Bar], as_of: date) -> float | None:
    """Annualised Parkinson high-low range vol. OHLC path only — None otherwise.

    More efficient than close-to-close for the same window (it uses the whole
    session's range rather than two points), which is exactly why it is worth
    having despite the narrower coverage: sigma^2 = mean(ln(h/l)^2) / (4 ln 2).
    """
    window = trailing_bars(bars, as_of, RV_WINDOW)
    ratios = [math.log(b.h / b.l) ** 2
              for b in window
              if b.source == SRC_OHLC and b.h and b.l and b.l > 0 and b.h >= b.l]
    if len(ratios) < _MIN_RV_OBS:
        return None
    return math.sqrt(statistics.fmean(ratios) / (4.0 * math.log(2.0))) * _ANNUALIZE


def semivar_dn(bars: dict[date, Bar], as_of: date) -> float | None:
    """Annualised DOWNSIDE deviation — the same window, negative sessions only.

    Separated from `rv20` on purpose. A bear position is a bet on the shape of
    the left tail specifically, and a name whose vol is all upside gaps is a
    different animal from one that bleeds down; total vol cannot tell them
    apart. Deviation is taken about zero, not about the mean, so it reads as
    "how much downside was there", not "how dispersed was the downside".
    """
    rets = _log_returns(_closes(trailing_bars(bars, as_of, RV_WINDOW + 1)))
    if len(rets) < _MIN_RV_OBS:
        return None
    downside = [min(r, 0.0) ** 2 for r in rets]
    return math.sqrt(statistics.fmean(downside)) * _ANNUALIZE


def atr14_pct(bars: dict[date, Bar], as_of: date) -> float | None:
    """Average True Range over `ATR_WINDOW`, as a fraction of the last close.

    OHLC path only. Simple mean of the true ranges rather than Wilder's
    smoothing — the difference is a weighting of the same window and nothing
    downstream reads an ATR level, only its tercile.
    """
    window = trailing_bars(bars, as_of, ATR_WINDOW + 1)
    if len(window) < 2:
        return None
    trs = []
    for prev, cur in zip(window, window[1:]):
        if cur.source != SRC_OHLC or cur.h is None or cur.l is None:
            continue
        if prev.c is None or prev.c <= 0:
            continue
        trs.append(max(cur.h - cur.l, abs(cur.h - prev.c), abs(cur.l - prev.c)))
    if len(trs) < _MIN_ATR_OBS:
        return None
    last_close = window[-1].c
    if not last_close or last_close <= 0:
        return None
    return statistics.fmean(trs) / last_close


def eff_ratio(bars: dict[date, Bar], as_of: date) -> float | None:
    """Kaufman efficiency ratio over `EFF_WINDOW`: |net move| / sum |session moves|.

    In [0, 1]. Near 0 the name went nowhere by a long road (chop); near 1 it
    travelled in a straight line (trend). This is the feature the give-back
    finding points at most directly — 82% of bear rows go green and 56% of those
    finish at or below zero, which is what a position round-tripping through
    chop looks like, and total vol is blind to the distinction.
    """
    closes = _closes(trailing_bars(bars, as_of, EFF_WINDOW + 1))
    if len(closes) < _MIN_EFF_OBS:
        return None
    path = sum(abs(b - a) for a, b in zip(closes, closes[1:]))
    if path <= 0:
        return None
    return abs(closes[-1] - closes[0]) / path


def vrp(bars: dict[date, Bar], as_of: date, iv_entry: float | None) -> float | None:
    """Vol risk premium at entry: implied minus realized, in decimal fractions.

    UNITS TRAP, and it has bitten this repo before: the book's column is named
    `iv_entry_pct` but holds a DECIMAL FRACTION — `simulate.py` writes the same
    sigma it feeds Black-Scholes, so 0.3295 means 33% IV (verified 406/406 real
    rows in 0.028..1.294, see `underlying.sigma_1d`). Passing IV POINTS here
    would report a vol premium ~100x too large and every sign test built on it
    would still "work", just on garbage. Callers pass the column through
    unchanged.

    Positive = the option was pricing more movement than the tape had been
    delivering (you are paying up for vol); negative = implied is cheap against
    realized. For a long-premium structure the sign is the interesting part.
    """
    if iv_entry is None or iv_entry <= 0:
        return None
    realized = rv20(bars, as_of)
    if realized is None:
        return None
    return iv_entry - realized


# ── market coupling ──────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def market_closes() -> dict[date, float]:
    """SPY daily closes from the mech-regime series. `{}` when the file is absent.

    Same file the mech studies read, so a beta computed here and a `mech_cell`
    read elsewhere are anchored to the identical market series.
    """
    if not MARKET_SERIES.exists():
        return {}
    out: dict[date, float] = {}
    with MARKET_SERIES.open() as fh:
        for row in csv.DictReader(fh):
            try:
                d = date.fromisoformat(str(row["date"])[:10])
                v = float(row["spy_close"])
            except (ValueError, KeyError, TypeError):
                continue
            if v > 0:
                out[d] = v
    return out


def beta_corr_spy(bars: dict[date, Bar], as_of: date) -> tuple[float | None, float | None]:
    """`(beta, correlation)` of the name against SPY over `BETA_WINDOW` sessions.

    Paired on the dates BOTH series traded — an unpaired fit would silently
    align a holiday against a session and read as a spurious move. Returns
    `(None, None)` when the overlap is too thin or either series is flat.
    """
    market = market_closes()
    if not market:
        return (None, None)
    days = sorted(d for d in bars if d <= as_of and d in market)[-(BETA_WINDOW + 1):]
    if len(days) < _MIN_BETA_OBS + 1:
        return (None, None)

    asset, mkt = [], []
    for prev, cur in zip(days, days[1:]):
        a_prev, a_cur = bars[prev].c, bars[cur].c
        m_prev, m_cur = market[prev], market[cur]
        if min(a_prev, a_cur, m_prev, m_cur) <= 0:
            continue
        ra, rm = math.log(a_cur / a_prev), math.log(m_cur / m_prev)
        if abs(ra) > _MAX_ABS_LOG_RETURN or abs(rm) > _MAX_ABS_LOG_RETURN:
            continue
        asset.append(ra)
        mkt.append(rm)

    if len(asset) < _MIN_BETA_OBS:
        return (None, None)
    var_m = statistics.pvariance(mkt)
    sd_a, sd_m = statistics.pstdev(asset), statistics.pstdev(mkt)
    if var_m <= 0 or sd_a <= 0 or sd_m <= 0:
        return (None, None)
    cov = statistics.fmean([(a - statistics.fmean(asset)) * (m - statistics.fmean(mkt))
                            for a, m in zip(asset, mkt)])
    return (cov / var_m, cov / (sd_a * sd_m))


# ── the aggregate ────────────────────────────────────────────────────────────

FEATURE_KEYS = ("rv20", "rv_park", "semivar_dn", "atr14_pct", "eff_ratio",
                "vrp", "beta_spy60", "corr_spy60")

# The features that need a high and a low, and so exist only on the OHLC path.
OHLC_ONLY_KEYS = ("rv_park", "atr14_pct")


def features(bars: dict[date, Bar], as_of: date,
             iv_entry: float | None = None) -> dict:
    """Every feature for one (ticker, entry date), plus the coverage fields.

    Returns `FEATURE_KEYS` (each `float | None`) alongside `source`, `n_bars`
    and `has_ohlc`. The coverage fields are not decoration — `rv_park` and
    `atr14_pct` are None on the close-only path, so a caller that reports a mean
    over them without reporting `has_ohlc` is quoting an unstated denominator.
    """
    trailing = trailing_bars(bars, as_of, max(RV_WINDOW, ATR_WINDOW, EFF_WINDOW) + 1)
    last = trailing[-1] if trailing else None
    beta, corr = beta_corr_spy(bars, as_of)
    return {
        "rv20": rv20(bars, as_of),
        "rv_park": rv_parkinson(bars, as_of),
        "semivar_dn": semivar_dn(bars, as_of),
        "atr14_pct": atr14_pct(bars, as_of),
        "eff_ratio": eff_ratio(bars, as_of),
        "vrp": vrp(bars, as_of, iv_entry),
        "beta_spy60": beta,
        "corr_spy60": corr,
        "source": last.source if last else None,
        "n_bars": len(trailing),
        "has_ohlc": bool(last and last.has_ohlc),
    }


def coverage(rows: list[dict]) -> dict:
    """`{feature: {n, pct}}` plus the bar-source split, for the report header.

    Every study using these features prints this before any conditional mean.
    The OHLC-only features legitimately have a smaller denominator and the
    report has to say so.
    """
    total = len(rows)
    out = {"n_rows": total,
           "by_source": {}, "has_ohlc": sum(1 for r in rows if r.get("has_ohlc"))}
    for r in rows:
        src = r.get("source") or "none"
        out["by_source"][src] = out["by_source"].get(src, 0) + 1
    for key in FEATURE_KEYS:
        n = sum(1 for r in rows if r.get(key) is not None)
        out[key] = {"n": n, "pct": (n / total) if total else 0.0,
                    "ohlc_only": key in OHLC_ONLY_KEYS}
    return out


def terciles(rows: list[dict], key: str) -> tuple[float, float] | None:
    """The two cut points splitting non-null `key` into thirds, or None if too thin.

    Cuts come from the study population itself rather than from a fixed level,
    because none of these features has a meaningful absolute scale across
    tickers — 30% realized vol is calm for one name and a crisis for another.
    """
    # NaN is filtered, not just None: the book's numeric columns come off pandas
    # and a missing cell arrives as float('nan'), which sorts unpredictably and
    # silently corrupts BOTH cut points (2026-08-12: 71 NaN `iv_pct` rows put the
    # "bottom tercile" cut at 0.92 and swept 69% of the population into it).
    vals = sorted(float(r[key]) for r in rows
                  if r.get(key) is not None and math.isfinite(float(r[key])))
    if len(vals) < 9:
        return None
    return (vals[len(vals) // 3], vals[2 * len(vals) // 3])
