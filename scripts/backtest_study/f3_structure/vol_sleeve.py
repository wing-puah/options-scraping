"""Vol sleeve: synthesized straddle / strangle / calendar at the dates the engine signalled.

Pre-registered in `research/current.md` §2026-08-12 "`vol_sleeve`:
PRE-REGISTRATION", written BEFORE this file was run. The three questions and
their non-null gates are fixed there; nothing here may be reworded after seeing
a table.

WHY THIS COULD NOT BE ASKED BEFORE
----------------------------------
The book is 96% directional verticals. 21 of 1,607 analysis plays classify as
straddle/strangle, 3 ever reached `BacktestResults`, and ZERO calendars have
ever been priced. So the log holds no evidence about a volatility sleeve — not
weak evidence, none. The blocker was DATA: a straddle needs a call AND a put at
one strike/expiry, and the option cache was built from directional legs, so it
held a same-strike pair on 15 of the 481 (ticker, expiry) groups the book
entered. `scripts/collector/fetch_counterpart_history.py` closed that gap —
1,322/1,337 mirrors cached, 481/481 groups — with REAL Barchart marks under the
existing filename convention, so the pricing path below needed no new code.

WHAT IS SYNTHESIZED
-------------------
At every `(ticker, signal_date, expiry)` the pooled book actually entered, using
the row's own `entry_underlying` as spot S:

  straddle  long call + long put at K* = the cached strike nearest S
  strangle  long put at the nearest cached strike BELOW S, long call ABOVE
  calendar  short near-expiry call + long next-cached-expiry call, both at K*

The strike grid is WHAT THE BOOK TRADED, so "nearest to spot" means nearest
strike flow touched, not nearest listed. That is a real basis caveat and the
report quotes the |K-S|/S distribution rather than burying it.

THE FROZEN HARNESS IS NOT EDITED
--------------------------------
`harness.py` prices nothing — it replays a mark series — so a synthesized
structure is expressed as a SYNTHETIC ROW (legs, entry price, daily marks) fed
to the same frozen `Trade`/`replay` under `DEBIT_PROD`. Exit logic, clamps and
rounding are byte-identical to every recorded conclusion. Pricing helpers are
imported from `bear_rewrap` rather than re-implemented, for the same reason:
two copies of the entry rule would eventually disagree.

THE RECONSTRUCTION GATE COMES FIRST
-----------------------------------
A ticker-date is only used if THIS code, re-pricing the ORIGINAL book row from
the same cache, reproduces its stored `entry_option_price` and
`daily_price_csv`. Without that the study would price synthetics with code never
checked against anything. Pass rate is quoted before any result.

Read-only. Touches no config, writes no tab. Run:

    python -m scripts.backtest_study run vol_sleeve
"""
from __future__ import annotations

import argparse
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
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import cell_stats, fmt_row, hdr, sub  # noqa: E402
from scripts.backtest_study.f3_structure.bear_rewrap import (  # noqa: E402
    entry_date_for, leg_details, net_entry, net_marks, reconstructs, size_contracts,
)
from scripts.backtest_study.lib.book import DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import PATH_CAP_DAYS, Trade, replay  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402
from scripts.backtest_study.lib import underlying_features as UF  # noqa: E402

STRUCTURES = ("straddle", "strangle", "calendar")

# DTE buckets, fixed in the pre-registration.
DTE_BUCKETS = ((0, 21, "<=21"), (22, 45, "22-45"), (46, 90, "46-90"), (91, 10**6, ">90"))

MIN_CELL_N = 30          # Q1 gate: no cell below this is read at all
WORST_DECILE = 0.10      # Q2 hedge test, same cut as bear_deploy D2
WORST_QUARTILE = 0.25
HEDGE_SIZE = 0.5         # the shipped bear-sleeve convention: <= 1/2 size


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


def synthesize(book: list[dict], idx, require_recon: bool = True) -> tuple[list[dict], dict]:
    """One record per (date, ticker, expiry, structure). Plus a diagnostics dict."""
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
            for structure in STRUCTURES:
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


def max_drawdown(series: list[float]) -> float:
    """Peak-to-trough of the cumulative sum. Ported from bear_deploy."""
    cum, peak, worst = 0.0, 0.0, 0.0
    for v in series:
        cum += v
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def fmt_ci(ci) -> str:
    lo, hi = ci
    if lo != lo:
        return "        (thin)   "
    return f"[{lo:>+6.3f}, {hi:>+6.3f}]"


# ── Q1 ───────────────────────────────────────────────────────────────────────

def q1(rows: list[dict]) -> dict:
    hdr("Q1 — unconditional E by structure and DTE")
    print("  E = held to the path cap (no exit rule). R = the SHIPPED debit exits")
    print("  (pt .90 / sl .75 / tef .75) replayed through the frozen harness.")
    print("  A cell is read only at n >= %d; the gate needs a date-clustered CI"
          % MIN_CELL_N)
    print("  excluding zero AND the same sign in every year present.")

    non_null = []
    for structure in STRUCTURES:
        srows = [r for r in rows if r["structure"] == structure]
        if not srows:
            continue
        sub(f"{structure}  (n={len(srows)}, {len({r['date'] for r in srows})} dates)")
        print(f"  {'cell':<14} {'n':>4}  {'meanE':>7}  {'CI95 (E)':>18}  "
              f"{'meanR':>7}  {'win':>5}  {'$R':>10}   years(E)")
        cells = [("ALL", srows)] + [
            (name, [r for r in srows if r["bucket"] == name])
            for _, _, name in DTE_BUCKETS]
        for name, cell in cells:
            if not cell:
                continue
            e_vals = [r["E"] for r in cell]
            r_vals = [r["R"] for r in cell]
            ci = P.boot_ci_by_date(cell, key="E") if len(cell) >= 5 else (float("nan"),) * 2
            stable, pos, means = P.sign_stable(cell, key="E")
            yr = " ".join(f"{y}:{m:+.2f}" for y, m in means.items())
            print(f"  {name:<14} {len(cell):>4}  {statistics.fmean(e_vals):>+7.3f}  "
                  f"{fmt_ci(ci):>18}  {statistics.fmean(r_vals):>+7.3f}  "
                  f"{sum(1 for v in r_vals if v > 0) / len(r_vals):>5.0%}  "
                  f"{sum(r['R_dol'] for r in cell):>10,.0f}   {yr}")
            if len(cell) >= MIN_CELL_N and ci[0] == ci[0] \
                    and (ci[0] > 0 or ci[1] < 0) and stable:
                non_null.append(f"{structure}/{name}")

        credits = [r for r in srows if r["credit"]]
        if credits:
            print(f"  note: {len(credits)} rows priced as a NET CREDIT at entry "
                  f"(calendar inversion) — kept, sign handled by pnl_of.")

    sub("FRESHNESS SENSITIVITY — is the headline made of carried-forward marks?")
    print("  A long-premium position whose legs stop trading gets frozen at the last")
    print("  printed quote, and its terminal E is then a price the market never")
    print("  reprinted. Verticals largely cancel this between legs; these do not.")
    print(f"  {'cut':<34} {'n':>5}  {'meanE':>7}  {'CI95 (E)':>18}  {'meanR':>7}")
    for structure in STRUCTURES:
        srows = [r for r in rows if r["structure"] == structure]
        if not srows:
            continue
        for label, sel in (("all", lambda r: True),
                           ("final mark <= 3d stale", lambda r: r["stale_at_cap"] <= 3),
                           ("+ >=50% real (uncarried) days",
                            lambda r: r["stale_at_cap"] <= 3 and r["pct_real"] >= 0.5)):
            cell = [r for r in srows if sel(r)]
            if not cell:
                continue
            ci = P.boot_ci_by_date(cell, key="E") if len(cell) >= 5 else (float("nan"),) * 2
            print(f"  {structure + ' — ' + label:<34} {len(cell):>5}  "
                  f"{statistics.fmean([r['E'] for r in cell]):>+7.3f}  {fmt_ci(ci):>18}  "
                  f"{statistics.fmean([r['R'] for r in cell]):>+7.3f}")

    sub("CONCENTRATION — the mandatory ex-window cuts, and the carrying dates")
    print("  Long vol pays in bursts, so a positive mean is exactly what a couple of")
    print("  crisis weeks would produce. Both dominant windows in this book are")
    print("  volatility events (2025-03/04, 2026-02..04) — if the effect is only")
    print("  those, it is a window artifact and not a sleeve.")
    for structure in STRUCTURES:
        srows = [r for r in rows if r["structure"] == structure]
        if not srows:
            continue
        cuts = P.window_cuts(srows)
        # The standard cuts drop ONE dominant window each, and the carrying dates
        # here span both — so the cut that actually bites is dropping them together.
        both_months = {m for months in P.DOMINANT_WINDOWS.values() for m in months}
        cuts["ex_BOTH_windows"] = [r for r in srows if str(r["date"])[:7] not in both_months]
        for name, cut in cuts.items():
            if not cut:
                continue
            ci = P.boot_ci_by_date(cut, key="E")
            print(f"  {structure:<10} {name:<18} n={len(cut):>4}  "
                  f"E {statistics.fmean([r['E'] for r in cut]):>+6.3f}  CI {fmt_ci(ci)}")
        by_date = defaultdict(float)
        for r in srows:
            by_date[str(r["date"])] += r["R_dol"]
        top = sorted(by_date.items(), key=lambda kv: -kv[1])[:5]
        tot = sum(by_date.values())
        print(f"    top-5 dates carry ${sum(v for _, v in top):,.0f} of ${tot:,.0f} "
              f"({sum(v for _, v in top) / tot:.0%} of $R): "
              + ", ".join(f"{d} ${v:,.0f}" for d, v in top))

    print()
    if non_null:
        print(f"  Q1 NON-NULL cells: {', '.join(non_null)}")
    else:
        print("  Q1 IS NULL — no structure/DTE cell clears n>=%d with a CI excluding"
              % MIN_CELL_N)
        print("  zero and a stable sign across years.")
    return dict(non_null=non_null)


# ── Q2 ───────────────────────────────────────────────────────────────────────

def q2(rows: list[dict], book: list[dict]) -> dict:
    hdr("Q2 — date-level correlation with the DEPLOYED ladder")
    print("  The deployed book is the shipped operator card, replayed: top-3 per day,")
    print("  tiers A and B only (docs/deployment-rules.md). This is the")
    print("  diversification test, and it can pass even when Q1 is negative —")
    print("  a sleeve that pays on the days the book bleeds is a hedge, not an edge.")

    picked = P.top_k_per_day(book, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)
    dep = daily(picked)
    print(f"\n  deployed: {len(picked)} positions over {len(dep)} dates, "
          f"${sum(v['dollars'] for v in dep.values()):,.0f}")

    results = {}
    for label, cell in [("POOLED", rows)] + [(s, [r for r in rows if r["structure"] == s])
                                             for s in STRUCTURES]:
        if not cell:
            continue
        vol = daily(cell)
        both = sorted(set(dep) & set(vol))
        sub(f"{label}  ({len(cell)} rows, {len(vol)} dates, {len(both)} overlapping)")
        if len(both) < 10:
            print("  too few overlapping dates to read.")
            continue

        pr = [(dep[d]["mean_R"], vol[d]["mean_R"]) for d in both]
        pd_ = [(dep[d]["dollars"], vol[d]["dollars"]) for d in both]
        r_mean = pearson([a for a, _ in pr], [b for _, b in pr])
        r_dol = pearson([a for a, _ in pd_], [b for _, b in pd_])
        ci_mean, ci_dol = corr_ci(pr), corr_ci(pd_)
        print(f"  corr(daily mean R)   {r_mean:>+6.3f}   CI95 {fmt_ci(ci_mean)}")
        print(f"  corr(daily $)        {r_dol:>+6.3f}   CI95 {fmt_ci(ci_dol)}")

        # The hedge test: what the sleeve does on the deployed book's worst days.
        order = sorted(both, key=lambda d: dep[d]["dollars"])
        tails = {}
        for cut, name in ((WORST_DECILE, "worst decile"), (WORST_QUARTILE, "worst quartile")):
            k = max(1, int(len(order) * cut))
            tail_dates = set(order[:k])
            trows = [r for r in cell if str(r["date"]) in tail_dates]
            if not trows:
                continue
            ci = P.boot_ci_by_date(trows, key="R")
            dep_dol = sum(dep[d]["dollars"] for d in tail_dates)
            print(f"  {name:<15} dates={k:>3}  deployed ${dep_dol:>9,.0f}   "
                  f"sleeve meanR {statistics.fmean([r['R'] for r in trows]):>+6.3f} "
                  f"CI95 {fmt_ci(ci)}  ${sum(r['R_dol'] for r in trows):>9,.0f}  "
                  f"n={len(trows)}")
            tails[name] = (statistics.fmean([r["R"] for r in trows]), ci)

        # Portfolio effect. The sleeve is normalised to ONE AVERAGE POSITION per
        # date (the date's mean $, not its sum) — the synthesizer emits ~6x as
        # many rows per day as the ladder deploys, so summing them would compare
        # a 14-position sleeve against a 3-position book and call the size
        # difference a hedge. Averaging is choice-free; picking WHICH structure
        # to hold each day would be a selection rule, and none is pre-registered.
        dep_series = [dep[d]["dollars"] for d in both]
        unit = {d: vol[d]["dollars"] / vol[d]["n"] for d in both}
        print(f"  book alone            total ${sum(dep_series):>10,.0f}   maxDD "
              f"${max_drawdown(dep_series):>10,.0f}")
        for mult in (HEDGE_SIZE, 1.0):
            mix = [dep[d]["dollars"] + mult * unit[d] for d in both]
            print(f"  + {mult:g} avg sleeve position  total ${sum(mix):>10,.0f}   maxDD "
                  f"${max_drawdown(mix):>10,.0f}")
        results[label] = dict(r_mean=r_mean, ci_mean=ci_mean, tails=tails)

    pooled = results.get("POOLED", {})
    non_null = False
    reasons = []
    if pooled:
        lo, hi = pooled["ci_mean"]
        if lo == lo and hi < 0:
            non_null = True
            reasons.append(f"corr {pooled['r_mean']:+.3f} CI excludes zero on the negative side")
        for name, (mean_r, ci) in pooled.get("tails", {}).items():
            if ci[0] == ci[0] and ci[0] > 0:
                non_null = True
                reasons.append(f"{name}: sleeve meanR {mean_r:+.3f}, CI excludes zero above")
    print()
    if non_null:
        print("  Q2 NON-NULL — " + "; ".join(reasons))
    else:
        print("  Q2 IS NULL — the sleeve is neither reliably anti-correlated with the")
        print("  deployed book nor reliably positive on its worst dates.")
    # The gate is POOLED by pre-registration. Per-structure passes are reported
    # so they are not lost, and labelled so they are not read as passes.
    for label in STRUCTURES:
        res = results.get(label)
        if not res:
            continue
        hits = [f"{n} meanR {m:+.3f} CI {fmt_ci(c)}"
                for n, (m, c) in res.get("tails", {}).items() if c[0] == c[0] and c[0] > 0]
        if res["ci_mean"][1] == res["ci_mean"][1] and res["ci_mean"][1] < 0:
            hits.append(f"corr {res['r_mean']:+.3f} CI {fmt_ci(res['ci_mean'])}")
        if hits:
            print(f"  POST-HOC (subgroup, NOT the pre-registered gate) — {label}: "
                  + "; ".join(hits))
    return dict(non_null=non_null, reasons=reasons, per_structure=results)


# ── Q3 (conditional) ─────────────────────────────────────────────────────────

def attach_features(rows: list[dict]) -> dict:
    """`vrp` (and its coverage) per row, computed as of the session before entry."""
    cov = Counter()
    for r in rows:
        bars = U.load_bars(r["ticker"])
        if not bars:
            cov["no_bars"] += 1
            r["vrp"] = None
            continue
        signal = date.fromisoformat(r["date"])
        as_of = U.prior_session(bars, signal + timedelta(days=1)) or signal
        feats = UF.features(bars, as_of, r.get("iv_entry"))
        r["vrp"] = feats["vrp"]
        r["source_bars"] = feats["source"]
        r["has_ohlc"] = feats["has_ohlc"]
        cov["vrp" if feats["vrp"] is not None else "no_vrp"] += 1
    return dict(cov)


def q3(rows: list[dict]) -> None:
    hdr("Q3 — pre-registered entry conditions")
    cov = attach_features(rows)
    print(f"  feature coverage: {cov}")
    print("  Conditions were named in the pre-registration and are not chosen here.")

    for structure in ("POOLED",) + STRUCTURES:
        cell = rows if structure == "POOLED" else [r for r in rows
                                                   if r["structure"] == structure]
        if len(cell) < MIN_CELL_N:
            continue
        sub(f"{structure}  (n={len(cell)})")

        print(f"  {'condition':<30} {'n':>4}  {'meanE':>6}  {'vs rest':>7}  "
              f"{'diff CI95 (date-clustered)':>26}")

        def show(label, sel):
            got = [r for r in cell if sel(r)]
            rest = [r for r in cell if not sel(r)]
            if not got or not rest:
                print(f"  {label:<30} (one side empty: {len(got)}/{len(rest)})")
                return
            d_ci = boot_ci_diff_by_date(cell, sel, key="E")
            verdict = "" if (d_ci[0] != d_ci[0] or d_ci[0] <= 0 <= d_ci[1]) else "  <- excludes 0"
            print(f"  {label:<30} {len(got):>4}  "
                  f"{statistics.fmean([r['E'] for r in got]):>+6.3f}  "
                  f"{statistics.fmean([r['E'] for r in rest]):>+7.3f}  "
                  f"{fmt_ci(d_ci):>26}{verdict}")

        show("vrp < 0 (implied cheap)", lambda r: r.get("vrp") is not None and r["vrp"] < 0)
        show("earnings inside DTE",
             lambda r: r.get("days_to_earnings") is not None
             and 0 <= r["days_to_earnings"] <= r["dte"])
        cuts = UF.terciles(cell, "iv_pct")
        if cuts:
            show(f"iv_pct bottom tercile (<{cuts[0]:.2f})",
                 lambda r: r.get("iv_pct") is not None and r["iv_pct"] < cuts[0])
        else:
            print("  iv_pct: too thin for terciles")


# ── report ───────────────────────────────────────────────────────────────────

def population(rows: list[dict], diag: dict, book: list[dict]) -> None:
    hdr("POPULATION — what was built, and what it is priced from")
    print(f"  book rows (real+tweak)        {len(book):>6}")
    print(f"  reconstruction gate           {diag.get('recon_pass', 0)} pass / "
          f"{diag.get('recon_fail', 0)} fail   "
          f"(a ticker-date is only used if THIS code reproduces its stored row)")
    print(f"  signal ticker-dates usable    {diag.get('ticker_dates', 0):>6}")
    print(f"  synthesized rows              {len(rows):>6}   "
          f"over {len({r['date'] for r in rows})} dates, "
          f"{len({r['ticker'] for r in rows})} tickers")
    for s in STRUCTURES:
        cell = [r for r in rows if r["structure"] == s]
        print(f"    {s:<10} built {diag.get(f'{s}_built', 0):>5}   "
              f"no grid {diag.get(f'{s}_no_grid', 0):>5}   "
              f"unpriceable {diag.get(f'{s}_unpriceable', 0):>5}")
        why = {k[len(s) + 5:]: v for k, v in diag.items() if k.startswith(f"{s}_why_")}
        if why:
            print("      unpriceable because: "
                  + "  ".join(f"{k}={v}" for k, v in sorted(why.items(),
                                                            key=lambda kv: -kv[1])))
        if cell:
            mny = sorted(r["moneyness"] for r in cell)
            covs = sorted(r["coverage"] for r in cell)
            print(f"      |K-S|/S  median {mny[len(mny) // 2]:.3f}  "
                  f"p90 {mny[int(0.9 * len(mny))]:.3f}   "
                  f"path coverage median {covs[len(covs) // 2]:.2f}  "
                  f"p10 {covs[int(0.1 * len(covs))]:.2f}")

    sub("years")
    for y, rs in P.by_year(rows).items():
        print(f"  {y}  n={len(rs):>5}  dates={len({r['date'] for r in rs}):>4}")

    sub("exit mix under the shipped debit profile")
    for s in STRUCTURES:
        cell = [r for r in rows if r["structure"] == s]
        if not cell:
            continue
        mix = Counter(r["exit_reason"] for r in cell)
        print(f"  {s:<10} " + "  ".join(f"{k}={v}" for k, v in mix.most_common()))

    sub("headline (shipped exits) — the numbers every later table sits on")
    for s in STRUCTURES:
        cell = [r for r in rows if r["structure"] == s]
        if cell:
            print(fmt_row(s, cell_stats(cell, key="R")))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-bs", action="store_true",
                    help="include bs_options_hist source rows (default off, and "
                         "they are evidence-excluded since 2026-08-11)")
    ap.add_argument("--no-recon-gate", action="store_true",
                    help="skip the reconstruction gate (sensitivity only)")
    ap.add_argument("--force-q3", action="store_true",
                    help="run Q3 even if the pre-registered gate does not open "
                         "(printed as a DEVIATION)")
    args = ap.parse_args()

    book, _bdiag = load_book(include_bs=args.include_bs)
    idx = _strike_index()

    rows, diag = synthesize(book, idx, require_recon=not args.no_recon_gate)
    if not rows:
        print("No synthesizable rows — nothing to report.")
        return 1

    population(rows, diag, book)
    r1 = q1(rows)
    r2 = q2(rows, book)

    hdr("Q3 GATE")
    open_gate = bool(r1["non_null"]) or r2["non_null"]
    print(f"  Q1 non-null: {bool(r1['non_null'])}   Q2 non-null: {r2['non_null']}")
    if open_gate:
        print("  GATE OPEN — Q3 runs.")
        q3(rows)
    elif args.force_q3:
        print("  GATE CLOSED but --force-q3 was passed. Everything below is a")
        print("  RECORDED DEVIATION from the pre-registration and is exploratory.")
        q3(rows)
    else:
        print("  GATE CLOSED — Q3 is NOT run, per the pre-registration. Conditioning")
        print("  on entry features after two nulls is where this log has produced")
        print("  its false positives before; that is the whole point of the gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
