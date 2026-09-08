"""`vol_sleeve`'s synthesis layer, kept because `calendar_hedge` R4 runs it.

WHY THIS MODULE EXISTS
----------------------
`f5_hedging/vol_sleeve.py` was RETIRED AND DELETED on 2026-09-07. Its
verdicts are recorded in `research/study-map.md` (a `DELETED` row in the
hedging family table) and its frozen per-era record is
`research/study-results/f5_hedging/vol_sleeve.md`. Nothing here re-opens it.

What could not be deleted with it is the synthesis layer. `calendar_hedge`'s
gate **R4** builds `vol_sleeve`'s calendar cell TWICE in one process — once
through its own `build_universe`/`evaluate`, once through `synthesize` below —
and requires the two equal row for row. R4 is exactly the test that a second
copy of the entry rule has not drifted from the first, so the second copy has
to keep existing and it has to be THIS one, unchanged. A retirement that left
`synthesize` inside a deleted module would leave R4 with one side.

`scripts/collector/fetch_sweep_legs.py` and
`scripts/collector/fetch_financing_legs.py` read `_strike_index` /
`paired_strikes` from here for the same reason: one encoding of the option
cache's filename convention, not two.

MOVED UNCHANGED
---------------
Every body below is byte-identical to `vol_sleeve.py`'s at the time of the
deletion (git 8c03502). That is the point: `calendar_hedge`'s recorded R4 PASS
is a claim about these exact bodies, so a tidy-up here is a silent change to a
recorded gate. Fix a bug here only with a reconciliation run of
`calendar_hedge` beside it.

`daily()` deliberately does NOT defer to `lib/hedge_criteria.py::daily_series`.
The two disagree on two things, not one: this one returns a mapping
(`mean_R`/`dollars`/`n`) where the criteria library returns a tuple, and it
sums `dol_key` over EVERY row of the date while the library sums it only over
rows that also carry `r_key`. The second is arithmetic, so importing would move
a number.

THE `lib/` LAYERING RULE
------------------------
`greeks.py` states that a module here must not import from a study folder, and
`hedge_instrument.py` restates the cache convention rather than import it for
that reason. This module is the deliberate exception, on the precedent of
`lib/live_select.py`: the pricing helpers come from `f3_structure/bear_rewrap`,
imported and not duplicated, because R4 compares row for row and a third copy
of the entry rule is the failure R4 exists to catch.

Read-only. Touches no config, writes no tab, runs nothing.
"""
from __future__ import annotations

import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _weekday_grid  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.f3_structure.bear_rewrap import (  # noqa: E402
    entry_date_for, leg_details, net_entry, net_marks, reconstructs, size_contracts,
)
from scripts.backtest_study.lib.book import DEBIT_PROD  # noqa: E402
from scripts.backtest_study.lib.harness import PATH_CAP_DAYS, Trade, replay  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402

STRUCTURES = ("straddle", "strangle", "calendar")

# DTE buckets, fixed in the pre-registration.
DTE_BUCKETS = ((0, 21, "<=21"), (22, 45, "22-45"), (46, 90, "46-90"), (91, 10**6, ">90"))


# ── the cache index ──────────────────────────────────────────────────────────

def _strike_index() -> dict[tuple[str, date], dict[float, set[str]]]:
    """`{(ticker, expiry): {strike: {"C","P"}}}` over the whole option cache.

    Built once from one directory listing. `bear_rewrap.cached_puts` globs per
    call, which is fine for a few hundred lookups and not for the ~40k this
    study makes.
    """
    idx: dict[tuple[str, date], dict[float, set[str]]] = defaultdict(dict)
    for path in HISTORY_CACHE.glob("*.csv"):
        parts = path.stem.split("_")
        if len(parts) != 3:
            continue
        ticker, stamp, tail = parts
        try:
            exp = date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
            strike = float(tail[:-1])
        except (ValueError, IndexError):
            continue
        cp = tail[-1]
        if cp not in ("C", "P"):
            continue
        idx[(ticker, exp)].setdefault(strike, set()).add(cp)
    return idx


def paired_strikes(idx, ticker: str, expiry: date) -> list[float]:
    """Strikes with BOTH a call and a put cached — the straddle-able grid."""
    return sorted(k for k, cps in idx.get((ticker, expiry), {}).items()
                  if cps >= {"C", "P"})


def call_expiries(idx, ticker: str, strike: float) -> list[date]:
    """Every expiry with a cached CALL at this strike, ascending."""
    return sorted(exp for (tk, exp), strikes in idx.items()
                  if tk == ticker and "C" in strikes.get(strike, set()))


# ── synthesis ────────────────────────────────────────────────────────────────

def build_legs(structure: str, idx, ticker: str, expiry: date,
               spot: float) -> list[Leg] | None:
    """The legs of one synthesized structure, or None when the grid can't carry it."""
    grid = paired_strikes(idx, ticker, expiry)
    if not grid:
        return None
    k_atm = min(grid, key=lambda k: abs(k - spot))

    if structure == "straddle":
        return [Leg(+1, ticker, expiry, k_atm, "Call"),
                Leg(+1, ticker, expiry, k_atm, "Put")]

    if structure == "strangle":
        below = [k for k in grid if k < spot]
        above = [k for k in grid if k > spot]
        if not below or not above:
            return None
        return [Leg(+1, ticker, expiry, above[0], "Call"),
                Leg(+1, ticker, expiry, below[-1], "Put")]

    if structure == "calendar":
        later = [e for e in call_expiries(idx, ticker, k_atm) if e > expiry]
        if not later:
            return None
        return [Leg(-1, ticker, expiry, k_atm, "Call"),
                Leg(+1, ticker, later[0], k_atm, "Call")]

    raise ValueError(structure)


def synth_trade(signal_date: date, ticker: str, legs: list[Leg],
                structure: str) -> tuple[Trade | None, str]:
    """`(Trade | None, reason)` for a synthesized structure.

    The grid is rebuilt here exactly as `Trade` rebuilds it (weekdays after the
    signal to `min(nearest DTE, path cap)`) rather than borrowed from the source
    row — a synthesized calendar's near leg need not share the source row's
    expiry, and a borrowed grid would then be the wrong length.

    The reason string is not decoration: `calendar` fails far more often than
    the other two and the report has to say WHY (an illiquid far leg with no bar
    on the shared entry day is a different fact about the market than a missing
    strike).
    """
    nearest_dte = min((l.expiration - signal_date).days for l in legs)
    if nearest_dte <= 0:
        return None, "expired_at_signal"
    end = signal_date + timedelta(days=min(nearest_dte, PATH_CAP_DAYS))
    grid = _weekday_grid(signal_date, end)
    if not grid:
        return None, "empty_grid"

    ed = entry_date_for(legs, grid)
    if ed is None:
        return None, "no_common_entry_day"
    if (ed - signal_date).days > U.MAX_ENTRY_LAG_DAYS:
        return None, "entry_lag_too_long"
    net = net_entry(legs, ed)
    if net is None or abs(net) <= 1e-9:
        return None, "entry_unpriced"

    marks = net_marks(legs, grid)
    if not any(m is not None for m in marks):
        return None, "no_marks"

    leg_str = "\n".join(
        f"{l.ticker}:{l.expiration.isoformat()}:{l.strike:g}:"
        f"{'C' if l.opt_type == 'Call' else 'P'} {l.qty:+d}" for l in legs)
    row = {
        "signal_date": signal_date.isoformat(),
        "ticker": ticker,
        "structure": structure,
        "entry_option_price": f"{net:.4f}",
        "contracts": str(size_contracts(net)),
        "dte_entry": str(nearest_dte),
        "legs": leg_str,
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
    }
    try:
        return Trade(row), "ok"
    except (AssertionError, ValueError, KeyError):
        return None, "trade_construction_failed"


def mark_quality(legs: list[Leg], grid: list[date]) -> tuple[float, int]:
    """`(pct_real_days, stale_days_at_cap)` — the honesty check for long premium.

    `net_marks` carries the last mark forward, exactly as production does. On a
    VERTICAL a stale quote largely cancels between the legs; on LONG PREMIUM it
    does not — an option that stops trading as it dies gets frozen at its last
    traded price, and the position's terminal E is then read off a mark the
    market never printed again. So every long-vol number in this report is
    re-cut on freshness, and a headline that only survives on stale marks is
    not a finding.

    `pct_real_days` = share of grid days on which EVERY leg printed a bar that
    day. `stale_days_at_cap` = calendar days between the most stale leg's last
    bar on-or-before the grid end and the grid end itself.
    """
    end = grid[-1]
    per_leg_days = [set(leg_details(leg)) for leg in legs]
    real = sum(1 for day in grid if all(day in days for days in per_leg_days))
    stale = 0
    for days in per_leg_days:
        prior = [d for d in days if d <= end]
        stale = max(stale, (end - max(prior)).days if prior else 10 ** 6)
    return (real / len(grid) if grid else 0.0, stale)


def bucket_of(dte: float) -> str:
    for lo, hi, name in DTE_BUCKETS:
        if lo <= dte <= hi:
            return name
    return ">90"


def path_stats(t: Trade) -> tuple[float | None, float | None, float | None, int]:
    """`(E, MFE, MAE, n_priced)` off the synthetic path — the book's own columns."""
    pls = [t.pnl_of(m) for m in t.marks if m is not None]
    if not pls:
        return None, None, None, 0
    return pls[-1], max(pls), min(pls), len(pls)


def synthesize(book: list[dict], idx, require_recon: bool = True,
               structures: tuple[str, ...] | None = None) -> tuple[list[dict], dict]:
    """One record per (date, ticker, expiry, structure). Plus a diagnostics dict.

    `structures` narrows the build to a subset of `STRUCTURES` (default: all of
    them, this study's own behaviour). It exists so `calendar_hedge`'s R4 can
    rebuild the calendar cell through THIS function — the reference side of a
    same-run comparison — without paying for the straddle and strangle cells it
    does not compare. Narrowing changes no row: the structure loop is
    independent per structure, and only the `diag` counters it never emits go
    missing.
    """
    diag = Counter()
    seen_recon: dict[tuple, bool] = {}

    # The signal universe: (date, ticker) -> {expiry: (spot, iv_entry, source row)}
    universe: dict[tuple[str, str], dict[date, dict]] = defaultdict(dict)
    for rec in book:
        t: Trade = rec["t"]
        key = (rec["date"], rec["ticker"])
        if require_recon:
            if key not in seen_recon:
                ok, _ = reconstructs(rec)
                seen_recon[key] = ok
                diag["recon_pass" if ok else "recon_fail"] += 1
            if not seen_recon[key]:
                continue
        spot = _f(t.row.get("entry_underlying"))
        if spot is None or spot <= 0:
            diag["no_spot"] += 1
            continue
        for leg in t.legs:
            universe[key].setdefault(leg.expiration,
                                     dict(spot=spot, rec=rec))

    diag["ticker_dates"] = len(universe)
    out: list[dict] = []
    for (d, ticker), by_exp in universe.items():
        signal_date = date.fromisoformat(d)
        for expiry, info in by_exp.items():
            spot, src = info["spot"], info["rec"]
            for structure in (STRUCTURES if structures is None else structures):
                legs = build_legs(structure, idx, ticker, expiry, spot)
                if legs is None:
                    diag[f"{structure}_no_grid"] += 1
                    continue
                t, why = synth_trade(signal_date, ticker, legs, structure)
                if t is None:
                    diag[f"{structure}_unpriceable"] += 1
                    diag[f"{structure}_why_{why}"] += 1
                    continue
                E, mfe, mae, n_priced = path_stats(t)
                if E is None:
                    diag[f"{structure}_unpriceable"] += 1
                    diag[f"{structure}_why_no_priced_marks"] += 1
                    continue
                rp = replay(t, **DEBIT_PROD)
                pct_real, stale = mark_quality(legs, t.grid)
                k = legs[0].strike
                out.append(dict(
                    date=d, month=d[:7], ticker=ticker, structure=structure,
                    expiry=expiry.isoformat(), dte=t.dte_entry,
                    bucket=bucket_of(t.dte_entry),
                    E=E, E_dol=t.dollars(E),
                    R=rp["pnl_pct"], R_dol=t.dollars(rp["pnl_pct"]),
                    exit_reason=rp["exit_reason"], days_held=rp["days_held"],
                    mfe=mfe, mae=mae,
                    entry_net=t.entry_net, contracts=t.contracts,
                    moneyness=abs(k - spot) / spot,
                    coverage=n_priced / len(t.grid) if t.grid else 0.0,
                    pct_real=pct_real, stale_at_cap=stale,
                    credit=t.entry_net < 0,
                    iv_entry=src.get("iv_entry"), iv_pct=_finite(src.get("iv_pct")),
                    days_to_earnings=src.get("days_to_earnings"),
                    src_tier=src.get("tier"), source=src.get("source"),
                    t=t,
                ))
                diag[f"{structure}_built"] += 1
    return out, diag


def _f(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _finite(v):
    """None for a missing OR NaN value — the book's numeric columns come off
    pandas, so 71 of its `iv_pct` cells arrive as float('nan') rather than None."""
    return v if (v is not None and isinstance(v, float) and math.isfinite(v)) else None


# ── stats helpers ────────────────────────────────────────────────────────────

def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx <= 0 or sy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def corr_ci(pairs: list[tuple[float, float]], n: int = 2000, seed: int = 20260812):
    """Bootstrap CI of the correlation, resampling DATES (each pair IS a date)."""
    if len(pairs) < 5:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        samp = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        r = pearson([a for a, _ in samp], [b for _, b in samp])
        if r is not None:
            vals.append(r)
    if not vals:
        return (float("nan"), float("nan"))
    vals.sort()
    return (vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))])


def boot_ci_diff_by_date(rows: list[dict], sel, key="E", n: int = 4000,
                         seed: int = 20260812):
    """Date-clustered CI of mean(selected) - mean(rest) on DISJOINT subsets.

    `protocol.boot_ci_paired_by_date` is the wrong tool for a conditioning
    question: it pairs two COLUMNS on the same rows, and an entry condition
    splits the rows instead. Reading two overlapping one-sided CIs and calling
    the gap a difference is the error this replaces.
    """
    by: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    for r in rows:
        if r.get(key) is None:
            continue
        by[str(r["date"])].append((float(r[key]), bool(sel(r))))
    dates = list(by)
    if len(dates) < 5:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        a, b = [], []
        for _ in range(len(dates)):
            for v, is_sel in by[rng.choice(dates)]:
                (a if is_sel else b).append(v)
        if a and b:
            diffs.append(statistics.fmean(a) - statistics.fmean(b))
    if not diffs:
        return (float("nan"), float("nan"))
    diffs.sort()
    return (diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))])


def daily(rows: list[dict], r_key="R", dol_key="R_dol") -> dict[str, dict]:
    """`{date: {mean_R, dollars, n}}` — the unit every portfolio claim is made in."""
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[str(r["date"])].append(r)
    out = {}
    for d, rs in by.items():
        vals = [float(r[r_key]) for r in rs if r.get(r_key) is not None]
        dols = [float(r[dol_key]) for r in rs if r.get(dol_key) is not None]
        if not vals:
            continue
        out[d] = dict(mean_R=statistics.fmean(vals), dollars=sum(dols), n=len(vals))
    return out
