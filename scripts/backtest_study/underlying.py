"""Underlying daily bars for the study tier: real stock OHLC, with a close-only fallback.

Infrastructure, not a study. `scripts/backtest_study/run.py` lists it in INFRA.

WHY THIS EXISTS SEPARATELY FROM `harness.py`
--------------------------------------------
`Trade._load_underlying` (harness.py) reads `Price~` off the SHORT legs' cached
option files. That gives one price per day and nothing for a position with no
short leg — 22 of the 795-row book, every `long_call`/`long_put`. Both limits
are worth removing, and NEITHER is removed there: `harness.py` is frozen, every
recorded conclusion rests on its exact behaviour, and `bear_giveback` ARM U's
published numbers must keep reproducing. The widening lives here, in new code.

THE FALLBACK CHAIN
------------------
1. `backtests/underlying_ohlc_cache/{TICKER}.csv` — real stock bars from
   `scripts/collector/fetch_underlying_ohlc.py`. Open, high, low, close.
2. `Price~` from up to `_MAX_TILDE_FILES` of the ticker's cached OPTION files —
   close only (`o`/`h`/`l` are None). This is what recovers the long-only rows,
   and it is per-TICKER rather than per-leg, so it does not care which legs a
   given position held.

Every bar carries `source`, and callers are expected to report the split rather
than silently pool them: a study arm that needs an open has a different row
count from one that only needs a close, and conflating the two misstates the
denominator every conclusion is quoted against.

`Price~` is the underlying quote stamped on an option row, so on the fallback
path a "close" is the underlying's price at the option's EOD snapshot — close
enough to a settlement close for a daily move (the collector's split gate
measures the gap at a median of 0.000% where both exist), but not identical.

SPLIT-ADJUSTED TICKERS — WHAT IS AND IS NOT BROKEN
--------------------------------------------------
Barchart serves stock history currently-adjusted while cached `Price~` was
captured unadjusted at the time, so for a ticker that split in between, the two
series differ by exactly the split ratio. Measured on the 2026-08-12 scrape,
6 of 104 tickers: XLE 2.000, CVNA 5.000, AVGO / MSTR / NFLX / SMCI 10.000 —
constant to three decimals, and AVGO/MSTR step 10 -> 1 exactly at their ex-date.
A constant exact ratio is what an adjustment looks like; a wrong symbol could
not produce one.

That distinction decides the handling:

  SAFE — every window in `move_windows` is a RATIO of two points on the SAME
  series, so a constant scale factor cancels. Percentage and sigma moves on an
  adjusted ticker are exactly as valid as on any other, and those are what the
  study buckets on.

  NOT SAFE — absolute dollar moves (they are on the adjusted basis, while the
  book's `entry_underlying` is unadjusted) and any comparison that mixes a
  scraped bar with a cached `Price~` or with `entry_underlying`. Callers get
  `rescaled_tickers()` so they can drop those rows from $-denominated cells
  only, not from the study.

The FALLBACK path carries the opposite hazard. `Price~` is the unadjusted
real-time price, so the tilde series has a genuine 10x DISCONTINUITY at an
ex-split date, and a window straddling it reads as a ~-90% session move.
`_SPLIT_ARTIFACT_PCT` guards that; it can only ever bite W1C, since a close-only
series has no open and therefore yields no W0/W1/WG at all.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.barchart.options import parse_history_details  # noqa: E402
from lib.parsing import to_float  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402

OHLC_CACHE = ROOT / "backtests" / "underlying_ohlc_cache"
RESCALED_FILE = OHLC_CACHE / "rescaled_tickers.txt"

# Cached option files sampled per ticker on the fallback path. Contracts on the
# same ticker quote the same underlying, so a handful covers the span; the
# median across them absorbs the odd stale row without reading hundreds of files.
_MAX_TILDE_FILES = 8

# A close-only (unadjusted `Price~`) window bigger than this is treated as a
# split discontinuity, not a session move. Real one-day moves this large exist
# — earnings gaps — but on the fallback path a 10x step is far commoner, and a
# fabricated -90% would dominate any mean it landed in.
_SPLIT_ARTIFACT_PCT = 0.35

# How far after the signal an entry session may legitimately fall. A holiday
# (or a Friday signal) moves it a day or two; anything longer is a gap in the
# bar series, and anchoring the position there would invent a fill.
MAX_ENTRY_LAG_DAYS = 5

TRADING_DAYS_PER_YEAR = 252

SRC_OHLC = "ohlc"
SRC_TILDE = "price_tilde"


@dataclass(frozen=True)
class Bar:
    """One session. `o`/`h`/`l` are None on the close-only fallback path."""
    c: float
    o: float | None = None
    h: float | None = None
    l: float | None = None
    source: str = SRC_OHLC

    @property
    def has_ohlc(self) -> bool:
        return self.o is not None


# --- loaders ------------------------------------------------------------------

@lru_cache(maxsize=None)
def rescaled_tickers() -> frozenset[str]:
    """Tickers whose scraped bars sit on a split-adjusted basis.

    Their percentage moves are valid (a constant ratio cancels); their absolute
    dollar moves are not comparable with the book's unadjusted prices. See the
    module docstring — this is a $-cell exclusion, not a row exclusion.
    """
    if not RESCALED_FILE.exists():
        return frozenset()
    out = set()
    for line in RESCALED_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.split()[0].upper())
    return frozenset(out)


@lru_cache(maxsize=None)
def _load_ohlc_cache(ticker: str) -> dict[date, Bar]:
    path = OHLC_CACHE / f"{ticker}.csv"
    if not path.exists():
        return {}
    try:
        details = parse_history_details(path.read_text(), require_mark=False)
    except Exception:
        return {}
    out: dict[date, Bar] = {}
    for d, row in details.items():
        c = to_float(row.get("Latest"))
        if c is None or c <= 0:
            continue
        out[d] = Bar(c=c, o=to_float(row.get("Open")), h=to_float(row.get("High")),
                     l=to_float(row.get("Low")), source=SRC_OHLC)
    return out


@lru_cache(maxsize=None)
def _load_tilde(ticker: str) -> dict[date, Bar]:
    """Close-only bars from `Price~` across the ticker's cached option files."""
    if not HISTORY_CACHE.exists():
        return {}
    per_day: dict[date, list[float]] = {}
    for path in sorted(HISTORY_CACHE.glob(f"{ticker}_*.csv"))[:_MAX_TILDE_FILES]:
        try:
            details = parse_history_details(path.read_text(), require_mark=False)
        except Exception:
            continue
        for d, row in details.items():
            v = to_float(row.get("Price~"))
            if v is not None and v > 0:
                per_day.setdefault(d, []).append(v)
    return {d: Bar(c=sorted(vs)[len(vs) // 2], source=SRC_TILDE)
            for d, vs in per_day.items()}


def load_bars(ticker: str) -> dict[date, Bar]:
    """`{date: Bar}` for a ticker: real OHLC where available, else close-only.

    A split-adjusted ticker is NOT diverted to the fallback. Its bars are
    internally consistent, so every ratio the study takes off them is correct,
    and the unadjusted `Price~` series it would fall back to is both sparser and
    discontinuous at the ex-date — strictly worse on the measure that matters.
    """
    ticker = ticker.upper().strip()
    bars = _load_ohlc_cache(ticker)
    return bars if bars else _load_tilde(ticker)


# --- position-relative geometry ------------------------------------------------

def entry_day(trade, sessions: set[date] | None = None) -> date | None:
    """The session the position was actually filled in.

    Entry is the next trading day's OPEN (`entry_timing: next_open`), and
    `_weekday_grid` is documented as "weekdays AFTER the signal date", so
    `marks[0]` is already that session — there is no pre-entry mark to skip.

    `sessions` (the dates the underlying actually traded) is how a market holiday
    is skipped. The grid is WEEKDAY-based and the option marks carry forward, so
    a closed day looks like a perfectly good entry: 23 of 795 book rows resolve
    to Juneteenth 2024, the 2025-01-09 mourning closure, Presidents' Day 2026 or
    Good Friday 2026 without this. The repo has no holiday calendar —
    `trading_days` in scrape_flow is weekdays only — so the bar series IS the
    calendar.

    `MAX_ENTRY_LAG_DAYS` bounds the skip. A holiday moves entry by a day or two;
    a longer jump means the BAR SERIES has a hole, and silently anchoring the
    position days later would invent a fill that never happened. Better to
    return None and be counted as unusable.
    """
    for day, mark in zip(trade.grid, trade.marks):
        if day <= trade.signal_date or mark is None:
            continue
        if sessions is not None and day not in sessions:
            continue
        if (day - trade.signal_date).days > MAX_ENTRY_LAG_DAYS:
            return None
        return day
    return None


def sessions_from(bars: dict[date, Bar], start: date, n: int) -> list[date]:
    """The `n` bar dates on or after `start`, in order (fewer if the data runs out)."""
    return sorted(d for d in bars if d >= start)[:n]


def prior_session(bars: dict[date, Bar], before: date) -> date | None:
    """The last bar date strictly before `before`."""
    earlier = [d for d in bars if d < before]
    return max(earlier) if earlier else None


def sigma_1d(iv_entry: float | None) -> float | None:
    """The one-session move the entry IV was pricing, as a fraction of spot.

    `iv_entry` is the book's `iv_entry_pct` column, which despite the name holds
    a DECIMAL FRACTION — `simulate.py` writes the same sigma it feeds
    Black-Scholes, so 0.3295 means 33% IV (verified: 406/406 real rows in
    0.028..1.294). Passing IV points here would understate the move 100x and
    collapse every sigma bucket.

    `None` when IV is missing — a missing sigma must propagate, never silently
    become a bucket.
    """
    if iv_entry is None or iv_entry <= 0:
        return None
    return iv_entry * math.sqrt(1.0 / TRADING_DAYS_PER_YEAR)


def move_windows(trade, bars: dict[date, Bar]) -> dict:
    """The three pre-registered windows plus the close-only degradation.

    Keys, each `{abs, pct}` or None when the bars cannot support it:
      W0  entry open  -> entry close   PRIMARY. The session you bought into.
      W1  entry open  -> next close    2-session confirmation.
      WG  signal close-> entry open    the gap. NOT tradeable — it is already
                                       inside the fill — measured to price what
                                       the next-open entry basis costs.
      W1C entry close -> next close    close-only fallback, for rows with no
                                       open. Reported separately, never pooled
                                       with W0/W1.

    Also returns `entry_day`, `source`, and `has_ohlc` so callers can report
    coverage instead of quietly dropping rows.
    """
    out = {"entry_day": None, "source": None, "has_ohlc": False,
           "W0": None, "W1": None, "WG": None, "W1C": None}
    if not bars:
        return out
    ed = entry_day(trade, sessions=set(bars))
    if ed is None:
        return out
    out["entry_day"] = ed

    session_days = sessions_from(bars, ed, 2)
    if not session_days or session_days[0] != ed:
        # No bar on the entry session itself — nothing here can be anchored.
        return out
    entry_bar = bars[ed]
    out["source"] = entry_bar.source
    out["has_ohlc"] = entry_bar.has_ohlc
    next_bar = bars[session_days[1]] if len(session_days) > 1 else None

    close_only = entry_bar.source == SRC_TILDE

    def win(a: float | None, b: float | None) -> dict | None:
        if a is None or b is None or a <= 0:
            return None
        pct = (b - a) / a
        if close_only and abs(pct) > _SPLIT_ARTIFACT_PCT:
            # Unadjusted series stepping across an ex-split date, not a move.
            return None
        return {"abs": b - a, "pct": pct}

    out["W0"] = win(entry_bar.o, entry_bar.c)
    if next_bar is not None:
        out["W1"] = win(entry_bar.o, next_bar.c)
        out["W1C"] = win(entry_bar.c, next_bar.c)
    prev = prior_session(bars, ed)
    if prev is not None:
        out["WG"] = win(bars[prev].c, entry_bar.o)
    return out
