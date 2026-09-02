"""As-of-entry VOLUME features for the study tier. Infrastructure, not a study.

Pre-registered in `research/current.md` (2026-08-13,
`volume_signal`). Three features and no more; windows are the standing
`underlying_features` constants, not knobs.

  os_ratio  — flow-scrape option contracts x 100 / share volume, SAME session.
              Johnson & So (2012, JFE). The numerator is the Barchart unusual-
              flow feed's contract count (`Contracts` in audit/<date>-rollup.csv),
              NOT total listed option volume — an "unusual-O/S". Only the tercile
              order is ever read, so scale constants are irrelevant.
  rvolz20   — z-score of ln(volume) at the signal session against the trailing
              20 sessions ending the PRIOR session (the baseline excludes the
              day being scored). Gervais/Kaniel/Mingelgrin (2001); Lee &
              Swaminathan (2000).
  amihud20  — mean of |session log return| / (close x volume) over the 20
              sessions ending at the signal date. Amihud (2002). A control.

Split handling (frozen at pre-registration): tickers in `rescaled_tickers()`
keep `os_ratio` (same-day numerator and denominator, internally consistent) and
have `rvolz20`/`amihud20` WITHHELD — a split steps the share count and
fabricates exactly the volume spike the z-score is looking for. Sessions whose
paired close return exceeds `_MAX_ABS_LOG_RETURN` are dropped from the trailing
windows along with their volume, mirroring `underlying_features._log_returns`.

No lookahead: every feature is as-of the signal date; the book's entry basis is
the NEXT session's open, so signal-session volume is decision-time information.
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.parsing import to_float  # noqa: E402
from scripts.backtest_study.lib.underlying import Bar, rescaled_tickers  # noqa: E402
from scripts.backtest_study.lib.underlying_features import (  # noqa: E402
    RV_WINDOW, _MAX_ABS_LOG_RETURN, _MIN_RV_OBS, trailing_bars,
)

AUDIT_DIR = ROOT / "audit"

VOLUME_KEYS = ("os_ratio", "rvolz20", "amihud20")


# ── option-volume join ───────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_contracts() -> dict[tuple[str, str], float]:
    """`{(date_iso, TICKER): contracts}` from every audit/<date>-rollup.csv.

    `Contracts` is the rollup's per-symbol total contract count for that date's
    flow scrape. First occurrence of a symbol in a file wins (symbols do not
    repeat across sections in practice; a repeat would be the same feed row).
    """
    out: dict[tuple[str, str], float] = {}
    if not AUDIT_DIR.exists():
        return out
    for path in sorted(AUDIT_DIR.glob("*-rollup.csv")):
        d = path.name[:10]
        try:
            with path.open() as fh:
                for row in csv.DictReader(fh):
                    sym = (row.get("Symbol") or "").upper().strip()
                    c = to_float(row.get("Contracts"))
                    if sym and c is not None and c > 0:
                        out.setdefault((d, sym), c)
        except OSError:
            continue
    return out


# ── window plumbing ──────────────────────────────────────────────────────────

def _clean_window(bars: list[Bar]) -> list[Bar]:
    """Bars whose close step from the previous bar is not a split artifact.

    The first bar has no prior close to test and is kept; a bar following a
    dropped one is tested against the last KEPT close, matching the intent of
    `underlying_features._log_returns` (drop the fabricated step, keep the rest).
    """
    out: list[Bar] = []
    for b in bars:
        if b.c is None or b.c <= 0:
            continue
        if out:
            r = math.log(b.c / out[-1].c)
            if abs(r) > _MAX_ABS_LOG_RETURN:
                continue
        out.append(b)
    return out


# ── the three features ───────────────────────────────────────────────────────

def os_ratio(bars: dict[date, Bar], as_of: date,
             contracts: float | None) -> float | None:
    """Unusual-O/S: flow contracts x 100 / share volume, both at `as_of`.

    Exact-date match only — a prior session's share volume against the signal
    date's flow count would be a different (and unregistered) feature.
    """
    if contracts is None or contracts <= 0:
        return None
    bar = bars.get(as_of)
    if bar is None or bar.v is None or bar.v <= 0:
        return None
    return contracts * 100.0 / bar.v


def rvolz20(bars: dict[date, Bar], as_of: date) -> float | None:
    """z of ln(volume) at `as_of` vs the RV_WINDOW sessions ending the prior one."""
    window = _clean_window(trailing_bars(bars, as_of, RV_WINDOW + 1))
    if not window:
        return None
    day0 = window[-1]
    base = [b.v for b in window[:-1] if b.v is not None and b.v > 0]
    if day0.v is None or day0.v <= 0 or len(base) < _MIN_RV_OBS:
        return None
    logs = [math.log(v) for v in base]
    sd = statistics.pstdev(logs)
    if sd <= 0:
        return None
    return (math.log(day0.v) - statistics.fmean(logs)) / sd


def amihud20(bars: dict[date, Bar], as_of: date) -> float | None:
    """Amihud illiquidity: mean |log return| / (close x volume), x 1e9 to print.

    The scale factor is cosmetic — only terciles are read — it just keeps the
    coverage table out of scientific notation.
    """
    window = _clean_window(trailing_bars(bars, as_of, RV_WINDOW + 1))
    ratios = []
    for prev, cur in zip(window, window[1:]):
        if cur.v is None or cur.v <= 0:
            continue
        ratios.append(abs(math.log(cur.c / prev.c)) / (cur.c * cur.v))
    if len(ratios) < _MIN_RV_OBS:
        return None
    return statistics.fmean(ratios) * 1e9


# ── the aggregate ────────────────────────────────────────────────────────────

def features(bars: dict[date, Bar], as_of: date, ticker: str,
             contracts: float | None) -> dict:
    """All three features for one (ticker, signal date), plus coverage fields.

    `rescaled` marks the split-adjusted basis; when True the two WINDOW_KEYS
    are withheld per the pre-registration, never silently recomputed.
    """
    rescaled = ticker.upper().strip() in rescaled_tickers()
    return {
        "os_ratio": os_ratio(bars, as_of, contracts),
        "rvolz20": None if rescaled else rvolz20(bars, as_of),
        "amihud20": None if rescaled else amihud20(bars, as_of),
        "vol_rescaled": rescaled,
        "has_contracts": contracts is not None and contracts > 0,
    }


def coverage(rows: list[dict]) -> dict:
    """`{feature: {n, pct}}` plus the join and withholding counts (G2 print)."""
    total = len(rows)
    out: dict = {
        "n_rows": total,
        "contracts_join": sum(1 for r in rows if r.get("has_contracts")),
        "rescaled_withheld": sum(1 for r in rows if r.get("vol_rescaled")),
    }
    for key in VOLUME_KEYS:
        n = sum(1 for r in rows if r.get(key) is not None)
        out[key] = {"n": n, "pct": (n / total) if total else 0.0}
    return out


def terciles(rows: list[dict], key: str) -> tuple[float, float] | None:
    """(lo, hi) tercile boundaries of `key` over rows where it is not None.

    NaN-safe copy of `underlying_features.terciles` semantics: boundaries from
    the sorted values at the 1/3 and 2/3 positions; None when fewer than 3
    usable values or the boundaries collapse.
    """
    vals = sorted(float(r[key]) for r in rows
                  if r.get(key) is not None and not math.isnan(float(r[key])))
    if len(vals) < 3:
        return None
    lo = vals[len(vals) // 3]
    hi = vals[(2 * len(vals)) // 3]
    if not lo < hi:
        return None
    return (lo, hi)


def tercile_of(value: float | None, bounds: tuple[float, float] | None) -> str | None:
    """LOW / MID / HIGH, or None when the value or the boundaries are missing."""
    if value is None or bounds is None:
        return None
    lo, hi = bounds
    if value < lo:
        return "LOW"
    if value >= hi:
        return "HIGH"
    return "MID"
