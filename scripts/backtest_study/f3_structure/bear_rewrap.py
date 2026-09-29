"""Bear structure substitution: is the vertical the wrong WRAPPER for a bear signal?

Bear selection is closed — B1 searched 496 subsets and found 0, the ML arm
returned 0 of 15 cells, and the log records three independent nulls. This study
does not re-open it. It holds the SIGNAL and the ENTRY fixed and changes only
the structure the signal was expressed in.

THE HYPOTHESIS, MECHANICALLY
----------------------------
A bear_put SPREAD sells the lower put. A down move in a single name arrives
with implied vol EXPANDING, and the short leg gives that expansion away — the
wrapper strips out the one thing that makes a bear position pay when it is
right. Two things in the log are what that would look like from the outside:

  - addendum 14, reproduced 08-08: "bear_put is volatility, not direction"
  - the give-back census: 82% of bear rows go green, 56% of those finish at or
    below zero, |MAE|/MFE ~ 1.25, and 124 rows peaked in +1..50% for -$77.2k

A position whose thesis is right and whose vega is short round-trips exactly
like that. If the wrapper is the problem, dropping the short leg fixes it and
NOTHING about selection changes. If it is not, bear give-back is structural and
the shipped hedge framing (<= 1/2 size, |delta| descending) is the final answer.

WHAT IS SUBSTITUTED
-------------------
  long_put   — drop the short leg. Full convexity, full vega. Costs more premium.
  wider      — short leg pushed to the lowest cached strike below it. Keeps some
               financing, recovers most of the vega.
  long_diag  — long leg rolled to the next cached expiry out, short leg left
               alone. Buys vega and time without paying naked premium.

All three price from `backtests/option_history_cache/` alone — every real-priced
spread row has BOTH legs cached (verified 165/165 bear_put, 128/128 bull_call,
85/85 bull_put), so `long_put` in particular needs no new data at all.

THE FROZEN HARNESS IS NOT EDITED
--------------------------------
`harness.py` prices nothing — it replays a mark series. So a substitution is
expressed as a SYNTHETIC ROW (new legs, new entry price, new daily marks) fed
to the same frozen `Trade`/`replay`. The exit logic, clamps and rounding that
every recorded conclusion rests on are byte-identical to the ones that produced
the baseline. `underlying.py` exists for the same reason: widen by adding code,
never by editing that module.

THE RECONSTRUCTION GATE COMES FIRST
-----------------------------------
Before any substitution is believed, the ORIGINAL structure is rebuilt from the
same cache and re-priced by the same code, and must reproduce the row's stored
`entry_option_price` and `daily_price_csv`. A row that fails is excluded from
every substitution cell and counted. Without this the study would be comparing
a substitution to a baseline priced by different code and calling the
difference an effect — quoting the gate's pass rate is what makes the rest
readable.

Read-only. Touches no config, writes no tab. Run:

    python -m scripts.backtest_study run bear_rewrap
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path, parse_history_details  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _defined_risk_bounds, _price_asof  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest.simulate import (  # noqa: E402
    _entry_side_mark, _is_junk_quote, _zero_bid_mark,
    carried_entry_fill, entry_day_fill, junk_day_mark, open_print_allowed,
)
from scripts.backtest_study.f2_management.bear_giveback import (  # noqa: E402
    BEAR_DEBIT, cell_stats, fmt_row, hdr, prod_profile_for, sub,
)
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.lib import hedge_criteria as HC  # noqa: E402
from scripts.backtest_study.lib.harness import Trade, replay  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402

# Production debit sizing, transcribed from config/backtest.yml (portfolio_value
# 50000, risk_per_trade_pct 0.02, stop_loss 0.75). Contracts matter beyond
# reporting: `harness.replay`'s dollar_stop is an ABSOLUTE $1,000 cap, so a
# substitution priced at a different premium and left at the baseline's contract
# count would be handed a different effective stop and the comparison would be
# measuring sizing, not structure.
PORTFOLIO_VALUE = 50000.0
RISK_PER_TRADE_PCT = 0.02
STOP_LOSS = 0.75

# Tolerance for the reconstruction gate, on a 4-decimal CSV round-trip.
RECON_TOL = 0.005          # entry price, absolute dollars
RECON_MARK_TOL = 0.01      # per-day mark, absolute dollars
RECON_MIN_MATCH = 0.95     # share of priced days that must agree

SUBSTITUTIONS = ("long_put", "wider", "long_diag")

# When production started marking a zero-bid leg by `_zero_bid_mark` (robustness
# review B5): the merge of 3e5c2dc onto main, local time, the clock
# `created_datetime` is stamped in. A stored book row written before this was
# priced with the plain mid-else-Latest mark, one written at or after it with
# B5. No column says which (`cost_basis`/`cost_total` are blank on every
# BacktestProxy row, before and after), so the write time is the row's basis.
# On the 2026-09-08 export the book has no row written between 10:31:15 and
# 15:21:14 that day, so the boundary is not a judgement call on any real row.
B5_SINCE = datetime(2026, 9, 8, 15, 5, 25)

# When production started filling a ONE-SIDED entry quote on the side the leg
# actually trades (`_entry_side_mark`, commit 09aa02c): the commit's local time.
# Same convention as B5_SINCE — no column records the rule, so the write time is
# the row's basis. The boundary is not a judgement call on any real row: on the
# 2026-09-19 export nothing was written between 2026-09-08 22:02:15 and the
# 16:45:19 re-price of 2025-04-09, so no row sits between the commit and the
# first row priced under it.
#
# This is a SECOND basis because the rule displaced B5 at entry rather than
# joining it. Under `_entry_side_mark` a zero-bid entry leg fills at the bid or
# the ask, and production's next branch is the PLAIN `_mark` — `_zero_bid_mark`
# is unreachable at entry, so a post-09aa02c row must not be reconstructed with
# it. Daily marks are unaffected and stay on the B5 basis.
SIDE_SINCE = datetime(2026, 9, 19, 12, 50, 45)

# When the side-aware fill started to PRECEDE the entry-day `Open` print
# (next-steps §0 item 9, operator decision 2026-09-22). Before it, a leg that
# printed an Open filled at that print whatever its quote said; at and after it,
# a one-sided quote is filled on the side the leg trades first, and only a
# two-sided or quote-less row keeps the Open. A THIRD basis, on the same
# write-time convention, because it moved the side rule's position without
# changing the rule: a row written between SIDE_SINCE and this is side-aware on
# a carried or zero-volume entry and NOT over a printed Open.
#
# The boundary is the change's authoring time. No stored row was written after
# it on the pre-change code: the whole-book `--redo` that re-prices the 49
# `Open`-fill rows waits for a Barchart refetch and runs after this is merged.
OPEN_SIDE_SINCE = datetime(2026, 9, 22, 12, 0, 0)

# When production started judging every quote with `simulate._is_junk_quote`
# (operator rulings 2026-09-24, commit ad701d7). A FOURTH basis on the same
# write-time convention, and it displaces the three above rather than joining
# them: every zero-bid quote is junk, so `_junk_entry_fill` owns the one-sided
# entry that `_entry_side_mark` used to, and `_junk_day_mark` owns the zero-bid
# daily mark that `_zero_bid_mark` used to (as its ceiling).
#
# The boundary is the FIRST write under the rule, not the commit: the whole-tab
# `--redo` that ad701d7's message records stamped both tabs at 2026-09-24
# 11:48:05, fifty minutes before the commit at 12:42:54. The commit time would
# put those rows on the old basis. Nothing on either tab was written between
# 2026-09-22 22:40:00 and that run, so the boundary is not a judgement call on
# any real row. The rows on the export studies read now were re-written again at
# 13:06 (commission-only costs, which moves no mark and no entry).
JUNK_SINCE = datetime(2026, 9, 24, 11, 48, 5)


# ── cache access ─────────────────────────────────────────────────────────────

_details_cache: dict[tuple, dict] = {}


def leg_details(leg: Leg) -> dict[date, dict]:
    """`{date: row}` for one contract from the shared option-history cache."""
    key = (leg.ticker, leg.expiration, leg.strike, leg.opt_type)
    if key not in _details_cache:
        path = cache_path(HISTORY_CACHE, leg.ticker, leg.expiration, leg.strike,
                          leg.opt_type)
        if not path.exists():
            _details_cache[key] = {}
        else:
            try:
                _details_cache[key] = parse_history_details(path.read_text(),
                                                            require_mark=False)
            except Exception:
                _details_cache[key] = {}
    return _details_cache[key]


def priced_with_b5(row: dict) -> bool:
    """Was this stored book row priced under the B5 zero-bid re-mark?

    Keyed on `created_datetime` against `B5_SINCE`. A row with no parseable
    stamp is taken as B5 (the rule production applies now); no row on the
    2026-09-08 exports lacks one.
    """
    raw = str(row.get("created_datetime") or "").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S") >= B5_SINCE
    except ValueError:
        return True


def priced_with_side(row: dict) -> bool:
    """Was this stored book row's ENTRY priced under the side-aware fill?

    Keyed on `created_datetime` against `SIDE_SINCE`, exactly as
    `priced_with_b5` is keyed against `B5_SINCE`. A row with no parseable stamp
    is taken as side-aware (the rule production applies now).
    """
    raw = str(row.get("created_datetime") or "").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S") >= SIDE_SINCE
    except ValueError:
        return True


def priced_with_open_side(row: dict) -> bool:
    """Did the side-aware fill PRECEDE the Open print when this row was priced?

    Keyed on `created_datetime` against `OPEN_SIDE_SINCE`, exactly as the two
    bases above. A row with no parseable stamp takes the rule production applies
    now.
    """
    raw = str(row.get("created_datetime") or "").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S") >= OPEN_SIDE_SINCE
    except ValueError:
        return True


def priced_with_junk(row: dict) -> bool:
    """Was this stored book row priced under the junk-quote rule?

    Keyed on `created_datetime` against `JUNK_SINCE`, exactly as the three
    bases above. A row with no parseable stamp takes the rule production
    applies now.
    """
    raw = str(row.get("created_datetime") or "").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S") >= JUNK_SINCE
    except ValueError:
        return True


_basis_stack: list[bool] = []
_side_stack: list[bool] = []
_open_side_stack: list[bool] = []
_junk_stack: list[bool] = []


@contextmanager
def basis_of(row: dict):
    """Price on `row`'s basis inside the block — ALL FOUR bases.

    `priced_with_b5` governs the daily mark, `priced_with_side` the entry fill,
    `priced_with_open_side` whether that fill precedes the Open print, and
    `priced_with_junk` whether the junk-quote rule owns both the entry fill and
    the daily mark. They are separate because the rules landed on different
    days; a row written between the first two is B5 on its marks and NOT
    side-aware on its entry.

    Every pricer below takes `b5=None` / `side=None` / `open_side=None` /
    `junk=None` to mean "the innermost basis_of, else the rule production
    applies now". Studies that price variants against a stored book row enter
    this once per row, so the reconstruction and every variant compared with it
    share the row's basis without threading four flags through each helper.
    """
    _basis_stack.append(priced_with_b5(row))
    _side_stack.append(priced_with_side(row))
    _open_side_stack.append(priced_with_open_side(row))
    _junk_stack.append(priced_with_junk(row))
    try:
        yield
    finally:
        _basis_stack.pop()
        _side_stack.pop()
        _open_side_stack.pop()
        _junk_stack.pop()


def each_on_basis(items, row_of):
    """Yield `items`, each inside `basis_of(row_of(item))`.

    A drop-in for `for rec in recs:` that keeps the loop body unindented.
    """
    for item in items:
        with basis_of(row_of(item)):
            yield item


def _resolve_b5(b5: bool | None) -> bool:
    if b5 is not None:
        return b5
    return _basis_stack[-1] if _basis_stack else True


def _resolve_side(side: bool | None) -> bool:
    if side is not None:
        return side
    return _side_stack[-1] if _side_stack else True


def _resolve_open_side(open_side: bool | None) -> bool:
    if open_side is not None:
        return open_side
    return _open_side_stack[-1] if _open_side_stack else True


def _resolve_junk(junk: bool | None) -> bool:
    if junk is not None:
        return junk
    return _junk_stack[-1] if _junk_stack else True


def row_mark(row: dict | None, b5: bool | None = None) -> float | None:
    """The production mark for one cached history row, or None when it has none.

    `_mark` (mid(Bid,Ask) -> Latest) re-marked by the production zero-bid rule,
    `scripts/backtest/simulate.py::_zero_bid_mark` (robustness review B5,
    3e5c2dc): bid 0 / ask 0 -> 0.0, bid 0 / ask > 0 -> ask/2. IMPORTED, not
    restated, so the mirror cannot drift from the rule it mirrors (research may
    import production; production never imports research).

    Only rows that HAVE a `_mark` are re-marked. Production loads its details
    with `require_mark=True`, so a row with no mid and no Latest never reaches
    `_zero_bid_mark` there: it is absent and the leg carries the prior mark
    forward. This cache keeps such rows (`require_mark=False`) and must skip
    them the same way.

    `b5=False` returns the plain `_mark`, the pre-fold mark. `b5=None` takes
    the innermost `basis_of`, else B5. A caller pricing against a stored book
    row uses that row's basis, so the reconstruction AND anything compared with
    it share it; a price with no stored row behind it takes the production rule.
    """
    if row is None or row.get("_mark") is None:
        return None
    zb = _zero_bid_mark(row) if _resolve_b5(b5) else None
    return row["_mark"] if zb is None else zb


def _priced_rows(leg: Leg) -> dict[date, dict]:
    """`leg_details` as PRODUCTION loads it: only rows that carry a `_mark`.

    Production parses its details with `require_mark=True`, so a row with no mid
    and no Latest is absent there — not junk, not a quote, simply not a day.
    """
    return {d: r for d, r in leg_details(leg).items() if r.get("_mark") is not None}


def _junk_day_mark(leg: Leg, rows: dict[date, dict], row_day: date) -> float | None:
    """The daily mark of a JUNK-quoted day, or None when it has no real value.

    PRODUCTION's rule, imported: `simulate.junk_day_mark` over this contract's
    series and rows as production loads them (`_priced_rows`), which is what
    `_simulate._price_leg` calls. Nothing is restated here — the traded-Latest
    step, the carried last good mark and the B5 ceiling all live there.
    """
    series = [(d, rows[d]["_mark"]) for d in sorted(rows)]
    marked = junk_day_mark(rows[row_day], row_day, series, rows, leg.expiration)
    return None if marked is None else marked[0]


def _mark_series(leg: Leg, b5: bool | None = None,
                 junk: bool | None = None) -> list[tuple[date, float | None]]:
    """`leg_series`, keeping a JUNK day with no real value as `(date, None)`.

    Production prices such a day as unpriceable, and every later day carried
    from that snap with it (`_price_leg` re-judges the carried snap's row), so
    the leg — and the whole position — has no value there. A None in the series
    is exactly what `_price_asof` then carries.
    """
    if not (_resolve_b5(b5) and _resolve_junk(junk)):
        marks = ((d, row_mark(r, b5)) for d, r in leg_details(leg).items())
        return sorted((d, m) for d, m in marks if m is not None)
    rows = _priced_rows(leg)
    out: list[tuple[date, float | None]] = []
    for d in sorted(rows):
        r = rows[d]
        if _is_junk_quote(r):
            out.append((d, _junk_day_mark(leg, rows, d)))
        else:
            out.append((d, r["_mark"]))
    return out


def leg_series(leg: Leg, b5: bool | None = None,
               junk: bool | None = None) -> list[tuple[date, float]]:
    """Sorted `[(date, mark)]` for one contract — the shape `_price_asof` wants.

    Off the junk basis each mark is `row_mark`, so a carried-forward zero-bid day
    is carried at its B5 re-mark, exactly as `_simulate._price_leg` re-marked
    the snap it carried before 2026-09-24.

    On the JUNK basis (`priced_with_junk`) a clean quote marks at its `_mark` and
    a junk one at `_junk_day_mark`. The junk basis implies B5 — the later rule
    can only apply where the earlier one does — so `b5=False` turns both off.
    A junk day with no real value is DROPPED here, so a caller carrying this
    series forward carries the previous mark where production has none; only
    `net_marks` (via `_mark_series`) keeps the gap.
    """
    return [(d, m) for d, m in _mark_series(leg, b5, junk) if m is not None]


def leg_entry_series(leg: Leg, b5: bool | None = None,
                     side: bool | None = None) -> list[tuple[date, float]]:
    """`leg_series` for an ENTRY that falls through to a carried mark.

    `_simulate._price_leg` picks the snap by `_mark` PRESENCE and only then
    re-marks the row it found, so selecting on `_mark` here and valuing with the
    entry rule reproduces both the day chosen and the price. With `entry_qty`
    passed (an entry), production applies `_entry_side_mark` and leaves the
    plain snap mark when the quote is two-sided — `_zero_bid_mark` is skipped
    entirely. Off the side basis this is `leg_series` unchanged.
    """
    if not _resolve_side(side):
        return leg_series(leg, b5, junk=False)
    out = []
    for d, r in leg_details(leg).items():
        if r.get("_mark") is None:
            continue                       # production never sees this row
        sm = _entry_side_mark(r, leg.qty)
        out.append((d, r["_mark"] if sm is None else sm))
    return sorted(out)


def cached_puts(ticker: str, expiration: date) -> list[float]:
    """Strikes of every cached PUT on one (ticker, expiry), ascending."""
    prefix = f"{ticker.upper().strip()}_{expiration.strftime('%Y%m%d')}_"
    out = []
    for path in HISTORY_CACHE.glob(f"{prefix}*P.csv"):
        try:
            out.append(float(path.stem.split("_")[-1][:-1]))
        except ValueError:
            continue
    return sorted(out)


def cached_expiries(ticker: str, strike: float, opt_type: str) -> list[date]:
    """Expiries of every cached contract at one (ticker, strike, type), ascending."""
    cp = "C" if opt_type.strip().title() == "Call" else "P"
    out = []
    for path in HISTORY_CACHE.glob(f"{ticker.upper().strip()}_*_{strike:.2f}{cp}.csv"):
        try:
            stamp = path.stem.split("_")[1]
            out.append(date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8])))
        except (ValueError, IndexError):
            continue
    return sorted(out)


# ── pricing (mirrors simulate.py, on the barchart source only) ───────────────

def entry_date_for(legs: list[Leg], grid: list[date]) -> date | None:
    """The first grid day on which EVERY leg has a cached row.

    Production prices all legs on one entry day (the anchor's `_entry_date`,
    the first trading day after the signal under `entry_timing: next_open`).
    Requiring all legs present keeps a substitution from being filled on a
    different day from the baseline it is compared against.
    """
    for day in grid:
        if all(day in leg_details(leg) for leg in legs):
            return day
    return None


def recorded_entry_date(base: Trade) -> date | None:
    """The entry day production ACTUALLY used, read off the stored row.

    `dte_entry` is stamped by `classify._entry_row_from_history` as
    `(expiration - entry_day).days` on the ANCHOR contract, so the day comes
    back exactly: `anchor.expiration - dte_entry`. Read, never re-derived.

    `entry_date_for` below derives a day from the cache instead, and for a
    STORED row that is unsound: production chose its day from the bars it had
    at pricing time, and this cache has since gained bars it never saw (the
    `HISTORY_START_DATE` fix, the far-call fetch and 178 restored files). On the
    2026-09-19 export the two agree on 1,324 of 1,325 records, which is why the
    drift went unnoticed; they disagree on HYG 2025-04-09, where production
    filled on 2025-04-14 off the long leg's first bar and carried the short leg
    forward, and the derived rule waits until 04-16 for both legs and rebuilds a
    different spread (0.47 against the stored 0.97).

    A SUBSTITUTION has no recorded entry day — it was never traded — so it keeps
    deriving one. Only the reconstruction gate, which re-prices a row that
    production already priced, can read the answer instead of guessing it.
    """
    try:
        dte = int(float(base.row.get("dte_entry")))
    except (TypeError, ValueError, AttributeError):
        return None
    if not base.legs:
        return None
    return base.legs[0].expiration - timedelta(days=dte)


def _open_ok(day: date, signal_date: date | None) -> bool:
    """May this entry fill at `day`'s Open print? PRODUCTION's rule, imported:
    `simulate.open_print_allowed` under `entry_timing: next_open` (the book's
    config) — only when the entry day is AFTER the signal day.

    `signal_date=None` is a caller pricing a day off the harness grid, which
    starts the weekday AFTER the signal (`_weekday_grid`), so the answer there
    is always yes.
    """
    return signal_date is None or open_print_allowed(day, signal_date)


def _junk_basis_entry(leg: Leg, day: date,
                      signal_date: date | None = None) -> float | None:
    """`entry_price_of` on the JUNK basis — production's entry choice, IMPORTED.

    `simulate.entry_day_fill` on the entry day's own row (a junk quote by
    `_junk_entry_fill` with the Open print, else the Open, else the mark),
    only when `open_print_allowed`; otherwise, or with no row that day,
    `simulate.carried_entry_fill` on the newest snap on or before the day
    (junk fill WITHOUT its Open print, else the snap's mark) — the two calls
    `_simulate._entry_price_leg` / `_price_leg` make, in that order. None when
    production refuses (`junk_entry_quote`) or has no price. Rows are read as
    production loads them (`_priced_rows`).
    """
    rows = _priced_rows(leg)
    fill = entry_day_fill(rows.get(day), leg.qty, open_print=_open_ok(day, signal_date))
    if fill is not None:
        return fill[0]                  # None is the junk_entry_quote refusal
    snaps = [d for d in sorted(rows) if d <= day and d <= leg.expiration]
    if not snaps:
        return None
    snap = rows[snaps[-1]]
    return carried_entry_fill(snap, snap["_mark"], leg.qty)[0]


def entry_price_of(leg: Leg, day: date, b5: bool | None = None,
                   side: bool | None = None,
                   open_side: bool | None = None,
                   junk: bool | None = None,
                   signal_date: date | None = None) -> float | None:
    """One leg's fill: that day's Open, else its EOD mark, else the most recent
    prior mark carried forward.

    The Open print is read only when `day` is AFTER `signal_date`
    (`_open_ok`, production's `open_print_allowed`, on EVERY basis — the rule
    predates them all). A same-day entry falls straight through to the carried
    mark, which for a day with a row is that day's EOD mark. Pass the signal
    date whenever `day` can be the signal day itself: a RECORDED entry day can
    (`recorded_entry_date`), a grid day cannot.

    Mirrors `_simulate._entry_price_leg` under `entry_timing: next_open` in ALL
    of its branches — Open when it is positive (the row tags these
    `barchart_open`), else the day's mark for a zero-volume open, else
    `_price_leg` under `entry_sources: [barchart]`, which is `_price_asof` over
    the contract's mark series: the last EOD mark on or before the entry day.
    Until 2026-09-04 only the first two were mirrored, and one real row
    (UTHR 2025-12-17 bull_call_spread, short leg bid 0 / no mark on the entry
    day, priced by production off the prior day's mark) failed `reconstructs`
    as `entry_unpriced` and stopped `hedge_structure` at R2 — a gate on the
    STUDY's fidelity to production, which is exactly what it exists to catch.
    Since 2026-09-17 every mark here is `row_mark` (the B5 zero-bid re-mark);
    before that five post-fold rows failed R2 the same way.

    On the SIDE basis (`priced_with_side`, commit 09aa02c) a fourth branch sits
    between the Open print and the mark: a leg whose entry-day quote is
    one-sided is filled on the side it trades (`_entry_side_mark` — sold at the
    bid, bought at the ask), and production's next branch is then the PLAIN
    `_mark` and only when it is positive, because `_zero_bid_mark` is
    unreachable at entry once the side rule owns that case. The same
    substitution applies to the carried-forward fallback, which is why the
    series below is `leg_entry_series` rather than `leg_series`. HYG 2025-04-09
    is the row this branch reconstructs: long 76P at its 0.97 Open print, short
    72P sold into a 0 bid for 0.

    On the OPEN-SIDE basis (`priced_with_open_side`, 2026-09-22) the side branch
    moves AHEAD of the Open print: a one-sided quote fills on its side even when
    the day printed, and only a two-sided or quote-less row keeps the Open.
    Production's `_entry_price_leg` has that order until 2026-09-24. `open_side`
    is only meaningful with `side`; the later rule implies the earlier one.

    On the JUNK basis (`priced_with_junk`, 2026-09-24) `_junk_entry_fill` —
    IMPORTED — prices any junk entry quote ahead of everything else, on the
    entry day's own row (with its Open print) or on the carried snap (without).
    A BOUGHT leg into a junk quote that did not trade is REFUSED, and this
    returns None exactly where production refuses `junk_entry_quote`. It implies
    the three entry bases before it, so `side=False` or `open_side=False` turns
    it off too.
    """
    use_side = _resolve_side(side)
    use_open_side = use_side and _resolve_open_side(open_side)
    if use_open_side and _resolve_junk(junk):
        return _junk_basis_entry(leg, day, signal_date)
    # Pre-junk bases (legacy rules production no longer has) keep their own
    # order below; the Open-after-signal gate is production's on every basis.
    row = leg_details(leg).get(day) if _open_ok(day, signal_date) else None
    if row is not None:
        if use_open_side:
            sm = _entry_side_mark(row, leg.qty)
            if sm is not None:
                return sm
        try:
            op = float(str(row.get("Open", "")).replace(",", "") or 0)
        except ValueError:
            op = 0.0
        if op > 0:
            return op
        if use_side:
            sm = _entry_side_mark(row, leg.qty)
            if sm is not None:
                return sm
            # Production's `mk and mk > 0`: a 0.0 mark falls through to the
            # carried series rather than filling at 0. NOT `row_mark` — the B5
            # re-mark cannot be reached at entry on this basis.
            mk = row.get("_mark")
            if mk is not None and mk > 0:
                return mk
        else:
            # Zero-volume open: that day's mark, B5-re-marked when the contract
            # is bid-less (`row_mark`). Production returned the re-mark even
            # when it was 0.0 (a 0x0 quote), so this tests for None, not > 0.
            mark = row_mark(row, b5)
            if mark is not None:
                return mark
    return _price_asof({"k": leg_entry_series(leg, b5, use_side)}, "k",
                       day, leg.expiration)


def net_entry(legs: list[Leg], day: date, b5: bool | None = None,
              side: bool | None = None,
              open_side: bool | None = None,
              junk: bool | None = None,
              signal_date: date | None = None) -> float | None:
    """Signed net entry price across legs, or None if any leg cannot be filled
    — including a leg production REFUSES (`junk_entry_quote`). `signal_date`
    gates the Open print as in `entry_price_of`."""
    total = 0.0
    for leg in legs:
        p = entry_price_of(leg, day, b5, side, open_side, junk, signal_date)
        if p is None:
            return None
        total += leg.qty * p
    return total


def net_marks(legs: list[Leg], grid: list[date],
              b5: bool | None = None,
              junk: bool | None = None) -> list[float | None]:
    """The daily signed net value over `grid`, carry-forward priced and clamped.

    Same two rules as `_simulate` steps 2-4: `_price_asof` carries the most
    recent mark on or before each day, and `_defined_risk_bounds` clamps the net
    to the structure's arbitrage-free range. The clamp returning None for a
    single leg (`long_put`) and for multi-expiration legs (`long_diag`) is the
    correct production behaviour, not an omission.

    On the junk basis a junk day with no real value leaves the leg — and so the
    day — unpriced, and stays unpriced while that snap is carried
    (`_mark_series`), as production's `_price_leg` does.
    """
    series = {id(leg): _mark_series(leg, b5, junk) for leg in legs}
    clamp = _defined_risk_bounds(legs)
    out: list[float | None] = []
    for day in grid:
        value = 0.0
        for leg in legs:
            p = _price_asof({"k": series[id(leg)]}, "k", day, leg.expiration)
            if p is None:
                value = None
                break
            value += leg.qty * p
        if value is not None and clamp is not None:
            value = max(clamp[0], min(clamp[1], value))
        out.append(value)
    return out


def size_contracts(entry_net: float) -> int:
    """Production debit sizing: risk budget / (premium x stop). Minimum 1."""
    if entry_net <= 0:
        return 1
    budget = PORTFOLIO_VALUE * RISK_PER_TRADE_PCT
    return max(1, int(budget / (entry_net * STOP_LOSS * 100)))


def synth_trade(rec: dict, legs: list[Leg], structure: str) -> Trade | None:
    """A frozen-harness `Trade` for a substituted structure on the same signal.

    Returns None when the substitution cannot be filled or priced. The grid is
    rebuilt by `Trade` from the legs' nearest expiry, which is why `long_diag`
    only ever rolls the LONG leg — moving the near leg would change the path
    window and the comparison would no longer be like-for-like.

    The substitution is marked on the SAME basis as the stored baseline it is
    compared against (`priced_with_b5`): a B5-marked substitution against a
    pre-fold baseline would measure the mark convention, not the structure.
    """
    base: Trade = rec["t"]
    grid = base.grid
    b5 = priced_with_b5(base.row)
    side = priced_with_side(base.row)
    open_side = priced_with_open_side(base.row)
    junk = priced_with_junk(base.row)
    ed = entry_date_for(legs, grid)
    if ed is None:
        return None
    net = net_entry(legs, ed, b5, side, open_side, junk, base.signal_date)
    if net is None or abs(net) <= 1e-9:
        return None

    marks = net_marks(legs, grid, b5, junk)
    if all(m is None for m in marks):
        return None

    leg_str = "\n".join(
        f"{l.ticker}:{l.expiration.isoformat()}:{l.strike:g}:"
        f"{'C' if l.opt_type == 'Call' else 'P'} {l.qty:+d}" for l in legs)
    row = {
        "signal_date": base.signal_date.isoformat(),
        "ticker": base.ticker,
        "structure": structure,
        "entry_option_price": f"{net:.4f}",
        "contracts": str(size_contracts(net)),
        "dte_entry": str(base.dte_entry),
        "legs": leg_str,
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
    }
    try:
        return Trade(row)
    except (AssertionError, ValueError, KeyError):
        return None


# ── the reconstruction gate ──────────────────────────────────────────────────

def reconstructs(rec: dict) -> tuple[bool, str]:
    """Does re-pricing the ORIGINAL structure reproduce the stored row?

    `(ok, reason)`. This is the gate the whole study rests on: a substitution is
    only interpretable against a baseline that THIS code can reproduce.
    """
    base: Trade = rec["t"]
    legs = base.legs
    if not legs:
        return False, "no_legs"
    if any(not leg_details(leg) for leg in legs):
        return False, "leg_not_cached"

    # The day production recorded, not one re-derived from a cache that has
    # grown since (`recorded_entry_date`). Falls back to the derived day only
    # when the row carries no usable `dte_entry`.
    ed = recorded_entry_date(base) or entry_date_for(legs, base.grid)
    if ed is None:
        return False, "no_common_entry_day"
    # Mirror EVERY basis the row was priced on: B5 governs its marks, the
    # side-aware fill (and whether it precedes the Open) its entry. See basis_of.
    b5 = priced_with_b5(base.row)
    junk = priced_with_junk(base.row)
    net = net_entry(legs, ed, b5, priced_with_side(base.row),
                    priced_with_open_side(base.row), junk, base.signal_date)
    if net is None:
        return False, "entry_unpriced"
    if abs(net - base.entry_net) > RECON_TOL:
        return False, "entry_mismatch"

    marks = net_marks(legs, base.grid, b5, junk)
    both = [(a, b) for a, b in zip(marks, base.marks)
            if a is not None and b is not None]
    if not both:
        return False, "no_overlapping_marks"
    agree = sum(1 for a, b in both if abs(a - b) <= RECON_MARK_TOL)
    if agree / len(both) < RECON_MIN_MATCH:
        return False, "mark_mismatch"
    return True, "ok"


# ── the substitutions ────────────────────────────────────────────────────────

def sub_long_put(rec: dict) -> list[Leg] | None:
    """Drop every short leg. Only meaningful on a two-leg vertical."""
    legs = rec["t"].legs
    longs = [l for l in legs if l.qty > 0]
    if len(legs) < 2 or len(longs) != 1:
        return None
    return longs


def sub_wider(rec: dict) -> list[Leg] | None:
    """Push the short leg to the lowest cached strike strictly below it."""
    legs = rec["t"].legs
    longs = [l for l in legs if l.qty > 0]
    shorts = [l for l in legs if l.qty < 0]
    if len(longs) != 1 or len(shorts) != 1:
        return None
    short = shorts[0]
    if short.opt_type != "Put":
        return None
    lower = [k for k in cached_puts(short.ticker, short.expiration) if k < short.strike]
    if not lower:
        return None
    new_short = Leg(ticker=short.ticker, expiration=short.expiration,
                    strike=min(lower), opt_type=short.opt_type, qty=short.qty)
    if not leg_details(new_short):
        return None
    return [longs[0], new_short]


def sub_long_diag(rec: dict) -> list[Leg] | None:
    """Roll the LONG leg to the next cached expiry out; leave the short alone."""
    legs = rec["t"].legs
    longs = [l for l in legs if l.qty > 0]
    shorts = [l for l in legs if l.qty < 0]
    if len(longs) != 1 or len(shorts) != 1:
        return None
    long_leg = longs[0]
    later = [e for e in cached_expiries(long_leg.ticker, long_leg.strike,
                                        long_leg.opt_type)
             if e > long_leg.expiration]
    if not later:
        return None
    new_long = Leg(ticker=long_leg.ticker, expiration=min(later),
                   strike=long_leg.strike, opt_type=long_leg.opt_type,
                   qty=long_leg.qty)
    if not leg_details(new_long):
        return None
    return [new_long, shorts[0]]


BUILDERS = {"long_put": sub_long_put, "wider": sub_wider, "long_diag": sub_long_diag}


# ── replay ───────────────────────────────────────────────────────────────────

def replay_rec(rec: dict, t: Trade) -> dict:
    """Replay one trade on the SHIPPED production profile for its regime cell.

    `prod_profile_for` is imported from `bear_giveback` rather than rebuilt: its
    base -> structure_exit -> regime_exit merge is the one ARM P validated
    against the real book, and a second transcription of the same YAML is how
    the 08-11 close-out ended up quoting a 3x overstated delta.
    """
    out = replay(t, **prod_profile_for(rec, 0.50, True))
    r = out["pnl_pct"]
    return dict(R=r, R_dol=t.dollars(r), exit_reason=out["exit_reason"],
                days_held=out["days_held"])


def build_arm(bear: list[dict]) -> tuple[dict, dict]:
    """`({label: [row]}, gate_diag)` — the baseline and every substitution.

    Rows carry `date`/`R`/`R_dol` so `protocol.py` can consume them directly,
    plus the stored `mfe`/`mae` for the give-back read. MFE/MAE are the
    BASELINE's on baseline rows only; a substitution's path is different, so its
    MFE/MAE are recomputed off its own marks.
    """
    gate = Counter()
    by_label: dict[str, list[dict]] = defaultdict(list)

    for rec in bear:
        ok, why = reconstructs(rec)
        gate[why] += 1
        if not ok:
            continue

        base_out = replay_rec(rec, rec["t"])
        by_label["baseline"].append(dict(
            date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
            source=rec["source"], tier=rec["tier"], mech_cell=rec["mech_cell"],
            mfe=rec["mfe"], mae=rec["mae"], key=id(rec), **base_out))

        for label in SUBSTITUTIONS:
            legs = BUILDERS[label](rec)
            if legs is None:
                gate[f"skip_{label}"] += 1
                continue
            t = synth_trade(rec, legs, label)
            if t is None:
                gate[f"unpriced_{label}"] += 1
                continue
            out = replay_rec(rec, t)
            pnls = [t.pnl_of(m) for m in t.marks if m is not None]
            by_label[label].append(dict(
                date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
                source=rec["source"], tier=rec["tier"], mech_cell=rec["mech_cell"],
                mfe=max(pnls) if pnls else None, mae=min(pnls) if pnls else None,
                key=id(rec), **out))
    return by_label, gate


# ── reporting ────────────────────────────────────────────────────────────────

def report_gate(bear: list[dict], gate: Counter) -> None:
    hdr("GATE — can this code reproduce the stored rows it is about to modify?")
    print("""  Every substitution below is a DIFFERENCE against the baseline replay.
  If the baseline cannot be rebuilt from the cache by the same pricing code,
  that difference is measuring the re-pricer, not the structure. Rows that
  fail are dropped from every cell and counted here.""")
    total = len(bear)
    ok = gate["ok"]
    print(f"\n  bear debit rows            {total:>5}")
    print(f"  reconstructed              {ok:>5}  ({ok / total:.1%})" if total else "")
    for reason, n in sorted(gate.items()):
        if reason == "ok" or reason.startswith(("skip_", "unpriced_")):
            continue
        print(f"    failed: {reason:<24} {n:>5}")
    sub("substitution availability")
    for label in SUBSTITUTIONS:
        print(f"  {label:<12} not-applicable {gate[f'skip_{label}']:>4}   "
              f"unpriceable {gate[f'unpriced_{label}']:>4}")


def report_cells(by_label: dict) -> None:
    hdr("ARM W — the wrapper, on the SHIPPED production exit")
    print("""  Same signal, same entry day, same exit rules. Only the structure differs.
  `gb` = |mean MAE| / mean MFE (path asymmetry), `cap` = mean R / mean MFE
  (how much of the shown profit the exit banked). A wrapper fix should raise
  cap and drop gb; a selection fix would raise MFE, and nothing here can.""")
    print()
    for label in ("baseline",) + SUBSTITUTIONS:
        rows = by_label.get(label) or []
        if rows:
            print(fmt_row(label, cell_stats(rows), width=12))

    for label in SUBSTITUTIONS:
        rows = by_label.get(label) or []
        if not rows:
            continue
        sub(f"{label} — paired against baseline on the same rows")
        keys = {r["key"] for r in rows}
        base = {r["key"]: r for r in by_label["baseline"] if r["key"] in keys}
        paired = [dict(date=r["date"], a=r["R"], b=base[r["key"]]["R"],
                       a_dol=r["R_dol"], b_dol=base[r["key"]]["R_dol"])
                  for r in rows if r["key"] in base]
        if not paired:
            continue
        d_mean = statistics.fmean(p["a"] - p["b"] for p in paired)
        lo, hi = P.boot_ci_paired_by_date(paired, "a", "b")
        d_dol = sum(p["a_dol"] - p["b_dol"] for p in paired)
        print(f"  n={len(paired)}  dR {d_mean:+.3f}  CI [{lo:+.3f}, {hi:+.3f}]  "
              f"d$ {d_dol:+,.0f}")
        mean_g, share, min_g, folds = P.loo_by_date(
            paired, lambda r: r["a"], lambda r: r["b"])
        print(f"  LOO-by-date: mean {mean_g:+.3f}  share+ {share:.0%}  "
              f"MIN {min_g:+.3f}  ({folds} folds)")
        for cut, rs in P.window_cuts(paired).items():
            if rs:
                print(f"    {cut:<16} n={len(rs):>4}  "
                      f"dR {statistics.fmean(r['a'] - r['b'] for r in rs):+.3f}")
        years = {y: statistics.fmean(r["a"] - r["b"] for r in rs)
                 for y, rs in P.by_year(paired).items()}
        print("    by year: " + "  ".join(f"{y} {v:+.3f}" for y, v in years.items()))
        mix = Counter(r["exit_reason"] for r in rows)
        print("    exits: " + "  ".join(f"{k}={v}" for k, v in mix.most_common()))


def report_criteria(by_label: dict) -> None:
    """The pre-registered ship gates, evaluated one by one per substitution.

    Printed as a checklist rather than prose because the log's failure mode is
    a headline that clears three gates and quietly misses a fourth. Sign
    stability across years is the gate that has killed the most candidates here
    (four recorded recurrences of a single window carrying an effect), and the
    pricing-tier split is the one that has most often turned a dollar headline
    into a composition artifact.
    """
    hdr("CRITERIA — the pre-registered gates, per substitution")
    for label in SUBSTITUTIONS:
        rows = by_label.get(label) or []
        if not rows:
            continue
        keys = {r["key"] for r in rows}
        base = {r["key"]: r for r in by_label["baseline"] if r["key"] in keys}
        paired = [dict(date=r["date"], a=r["R"], b=base[r["key"]]["R"],
                       a_dol=r["R_dol"], b_dol=base[r["key"]]["R_dol"],
                       src=r["source"]) for r in rows if r["key"] in base]
        if not paired:
            continue
        sub(label)
        lo, hi = P.boot_ci_paired_by_date(paired, "a", "b")
        print(f"  [{'PASS' if lo > 0 else 'FAIL'}] CI excludes zero          "
              f"dR {statistics.fmean(p['a'] - p['b'] for p in paired):+.3f} "
              f"CI [{lo:+.3f}, {hi:+.3f}]")

        _, share, min_g, folds = P.loo_by_date(paired, lambda r: r["a"],
                                               lambda r: r["b"])
        print(f"  [{'PASS' if min_g > 0 else 'FAIL'}] every LOO fold positive  "
              f"MIN {min_g:+.3f} over {folds} folds (share+ {share:.0%})")

        cuts = {k: statistics.fmean(r["a"] - r["b"] for r in rs)
                for k, rs in P.window_cuts(paired).items() if rs and k != "ALL"}
        ok_cuts = all(v > 0 for v in cuts.values())
        print(f"  [{'PASS' if ok_cuts else 'FAIL'}] both ex-window cuts       "
              + "  ".join(f"{k} {v:+.3f}" for k, v in cuts.items()))

        years = {y: statistics.fmean(r["a"] - r["b"] for r in rs)
                 for y, rs in P.by_year(paired).items()}
        ok_years = all(v > 0 for v in years.values())
        print(f"  [{'PASS' if ok_years else 'FAIL'}] sign-stable every year    "
              + "  ".join(f"{y} {v:+.3f}" for y, v in years.items()))

        tiers = {}
        for src in ("real", "tweak"):
            rs = [p for p in paired if p["src"] == src]
            if rs:
                tiers[src] = (statistics.fmean(p["a"] - p["b"] for p in rs),
                              sum(p["a_dol"] - p["b_dol"] for p in rs), len(rs))
        ok_tiers = all(v[0] > 0 for v in tiers.values())
        print(f"  [{'PASS' if ok_tiers else 'FAIL'}] right-signed both tiers   "
              + "  ".join(f"{k} n={v[2]} dR {v[0]:+.3f} d$ {v[1]:+,.0f}"
                          for k, v in tiers.items()))
        if ok_tiers and len({v[1] > 0 for v in tiers.values()}) > 1:
            print("        NOTE: the tiers agree on R but DISAGREE on dollars — a "
                  "substitution\n              changes premium, hence contracts, so $ "
                  "carries a sizing effect\n              that R does not. Quote R.")


def report_portfolio(by_label: dict, recs: list[dict]) -> None:
    """P1 and P2: does the sleeve pay on the dates the deployed book hurts?"""
    hdr("ARM P — portfolio contribution (P1 worst-decile, P2 correlation)")
    print("""  The criterion is NOT standalone expectancy — that was answered and
  closed. These are the D2 tests: what the sleeve does on the deployed
  book's worst dates, and whether it moves with the sleeve or against it.
  D2's shipped bear read is +0.252 on worst-decile dates, corr -0.132.""")

    ladder = P.top_k_per_day(recs, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)
    if not ladder:
        print("\n  no deployed rows — ladder replay empty")
        return
    # The daily series is `lib/hedge_criteria.daily_series` — one body, the
    # same one D2 reads, so the deployed ladder's dates cannot drift apart
    # between this study and its origin. Only the mean is taken; P1/P2 read no
    # dollars off the deployed side.
    sleeve_daily = {d: mean for d, (mean, _dol, _n)
                    in HC.daily_series(ladder, "R", "R_dol").items()}
    if not sleeve_daily:
        print("\n  no priced ladder rows")
        return
    # What follows is DELIBERATELY NOT `HC.hedge_contribution`, and the
    # difference is arithmetic rather than presentation — see
    # `lib/hedge_criteria.py`. Three things differ, all of them registered here:
    #   * the worst-decile cut is a VALUE cutoff (`v <= cutoff`, so ties are
    #     carried in) with no floor, where D2 takes exactly the
    #     `max(3, n // 10)` worst dates positionally;
    #   * P1's verdict is a bootstrap CI excluding zero, where D2's is a bare
    #     mean > 0, and it is measured on the SUBSTITUTION's own rows rather
    #     than on a paired daily series;
    #   * P2 needs 8 shared dates (D2's floor is 20), passes at corr <= 0
    #     (D2 needs < 0), and its per-year clause is a per-year CORRELATION,
    #     not D2's per-year tail sign.
    # Routing these through the library would move printed figures, so they
    # stay local.
    cutoff = sorted(sleeve_daily.values())[max(0, len(sleeve_daily) // 10 - 1)]
    worst = {d for d, v in sleeve_daily.items() if v <= cutoff}
    print(f"\n  deployed ladder: {len(ladder)} rows / {len(sleeve_daily)} dates; "
          f"worst decile = {len(worst)} dates (mean R <= {cutoff:+.3f})")

    for label in ("baseline",) + SUBSTITUTIONS:
        rows = by_label.get(label) or []
        if not rows:
            continue
        sub(f"{label}")
        on_worst = [r for r in rows if r["date"] in worst]
        if on_worst:
            lo, hi = P.boot_ci_by_date(on_worst, "R")
            m = statistics.fmean(r["R"] for r in on_worst)
            verdict = "MET" if lo > 0 else "not met"
            print(f"  P1 worst-decile: n={len(on_worst):>3}  meanR {m:+.3f}  "
                  f"CI [{lo:+.3f}, {hi:+.3f}]  ${sum(r['R_dol'] for r in on_worst):+,.0f}"
                  f"   -> {verdict}")
        else:
            print("  P1 worst-decile: no rows on those dates")

        paired = [(sleeve_daily[d], statistics.fmean(
                        [r["R"] for r in rows if r["date"] == d]))
                  for d in sorted({r["date"] for r in rows} & set(sleeve_daily))]
        if len(paired) >= 8:
            corr = statistics.correlation([a for a, _ in paired],
                                          [b for _, b in paired])
            print(f"  P2 correlation with deployed sleeve: {corr:+.3f} "
                  f"over {len(paired)} shared dates   "
                  f"-> {'MET' if corr <= 0 else 'not met'}")
            per_year: dict[str, list] = defaultdict(list)
            for d in sorted({r["date"] for r in rows} & set(sleeve_daily)):
                per_year[d[:4]].append((sleeve_daily[d], statistics.fmean(
                    [r["R"] for r in rows if r["date"] == d])))
            parts = []
            for y, pts in sorted(per_year.items()):
                if len(pts) >= 8:
                    c = statistics.correlation([a for a, _ in pts], [b for _, b in pts])
                    parts.append(f"{y} {c:+.3f}")
            if parts:
                print("     by year: " + "  ".join(parts))
        else:
            print("  P2 correlation: too few shared dates")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", default="GWCP", help="subset of G/W/C/P to run")
    a = ap.parse_args(argv)

    recs, diag = load_book(include_bs=False)
    print(f"book: {len(recs)} rows  counts_by_source={diag['counts_by_source']}  "
          f"(bs excluded)")
    bear = [r for r in recs if r["structure"] in BEAR_DEBIT and not r["credit"]]
    print(f"bear debit rows: {len(bear)}  "
          f"({Counter(r['source'] for r in bear)})")

    by_label, gate = build_arm(bear)

    if "G" in a.arms:
        report_gate(bear, gate)
    if "W" in a.arms:
        report_cells(by_label)
    if "C" in a.arms:
        report_criteria(by_label)
    if "P" in a.arms:
        report_portfolio(by_label, recs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
