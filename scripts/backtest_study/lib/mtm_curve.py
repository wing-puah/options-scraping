"""The MARK-TO-MARKET book equity curve — the basis `hedge_exposure` concludes from.

Implements the "Population and basis" bullet on the equity curve and gate
**G-MTM** of `research/pre-registrations/f4_deployment/hedge_exposure.md`, plus
the primary / co-primary path metrics under §"Unit and metric" (max drawdown in
dollars, Ulcer index, time-under-water).

--- Why this module exists ---------------------------------------------------
`account_sim.equity_curve()` buckets a position's whole result on its
`exit_sess`, and its own `print_equity()` says so: *"Open positions are not
marked to market, so this understates intra-position drawdown."* Every hedge
verdict on record (`bear_deploy` D3, `calendar_hedge` H3, `hedge_timing` H4)
rests on that curve — while a hedge's function is precisely to cushion the
intra-position path the curve omits. This module builds the curve that does not
omit it, and returns BOTH curves from one call so a caller cannot silently mix
bases.

--- What `daily_pnl_csv` actually is (verified, not assumed) ------------------
Written by `scripts/backtest/simulate.py::_summarize_path`:

    pnl_dollars.append("" if p is None else f"{(p - entry_net) * 100:.2f}")

so each token is:

  * **CUMULATIVE from entry, not a per-day increment** — it is the position's
    unrealized P&L level `(mark - entry_net) x 100`, not a difference against
    the previous day.
  * **per SINGLE contract**, deliberately unscaled by `contracts` (unlike
    `realized_pnl_abs`). Dollars for a sized position are `token x contracts`,
    which is exactly `Trade.dollars(Trade.pnl_of(mark))`.
  * on the **same grid as `daily_price_csv`**: `helpers._weekday_grid(signal_date,
    end)`, which is *"Weekdays AFTER the signal date through end_inclusive"* —
    so index 0 is the first session after the signal, NOT the signal date, and
    index `days_held - 1` is the exit session. That grid is `Trade.grid`, which
    `harness.py` asserts is the same length as the marks, and which
    `account_sim` already uses as `entry_sess = t.grid[0]` /
    `exit_sess = t.grid[days_held - 1]`. This module follows the same
    convention, so its session window is byte-identical to the one
    `account_sim.session_series` computes exposure on — which is the point: the
    concentration trigger and the drawdown path must speak about the same
    sessions. The pre-registration describes the window informally as
    `[signal_date, signal_date + days_held]`; the signal date itself carries no
    mark and no P&L, so the two differ only by a leading flat session.
  * **blank ("") wherever the position was unpriceable that day**, keeping the
    grid aligned. Blanks are carried forward here (a stale mark, not a zeroed
    position) and counted, so the caller can report them rather than discover
    them. On the v4 export there are none inside any `[entry, exit]` window.

The grid runs PAST the exit (to expiry or the 120-day path cap); only
`[entry_sess, exit_sess]` is used.

--- Reconciliation (G-MTM) ---------------------------------------------------
Cumulative MTM at a position's exit index must equal the dollars the BOOK
recorded for it — `realized_pnl_abs`, the column `simulate.py` wrote, read off
the row and never off the caller.

That target matters, and it is the 2026-08-29 errata's F2. This gate used to
compare `mtm_at_exit` against `pos.dollars`, which `hedge_exposure` filled from
the same `replay_sized()` call it took `days_held` from: one replay on both
sides of an equals sign, a gate that passed 485/485 at $0.0000 because it could
not do anything else. It now compares two INDEPENDENT stored columns — the
`daily_pnl_csv` token at the stored exit index, scaled by the row's contracts,
against `realized_pnl_abs` — so a wrong exit index, a wrong contract scaling or
a row whose columns genuinely disagree makes it FAIL. `pos.dollars` is still
what the curve carries after the exit; it is no longer what the gate checks.

The tolerance is an ARGUMENT (`tolerance=`, default `TOL_DOLLARS`), never a
constant buried in a comparison, so a caller that loosens it has to say so in
its own report. It is applied PER CONTRACT (`tolerance_for`), because
`daily_pnl_csv` is written per single contract and its rounding error scales
with the position's size.

Nothing here computes an annualised figure, a Sharpe ratio, or a
time-to-recover — the standing research-tier ban.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# `daily_pnl_csv` is written at 2 decimals per single contract, so one cent per
# CONTRACT is the finest distinction the column can express. The reconciliation
# target is the row's own `realized_pnl_abs`, written by the same simulate run
# from the same exit mark, so on the v4 export the agreement is exact and this
# is headroom, not slack. Scaled per contract by `tolerance_for()` below.
TOL_DOLLARS = 0.01

MTM = "mark_to_market"
REALIZED = "realized_on_close"

# Below the running peak by more than this (dollars) counts as under water.
# Guards float noise on a curve that is flat at its peak.
_UNDERWATER_EPS = 1e-9


# ════════════════════════════════════════════════════════════════════════════
# Types
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Curve:
    """A book equity curve on the session axis.

    `daily` is the per-session CHANGE in book equity — the shape
    `bear_deploy.max_drawdown` and `account_sim.equity_curve` both speak — and
    `levels` is its running sum, i.e. cumulative book P&L from a zero start.
    """
    basis: str
    sessions: list[date]
    daily: list[float]
    levels: list[float]

    def __len__(self) -> int:
        return len(self.sessions)


@dataclass(frozen=True)
class PathStats:
    """Path shape of one curve. `max_dd` is <= 0 dollars; `ulcer` is in PERCENT
    of peak account equity; `tuw` is a share of open sessions in [0, 1]."""
    basis: str
    n_sessions: int
    total: float
    max_dd: float
    ulcer: float
    tuw: float
    worst_session: float


@dataclass(frozen=True)
class Mismatch:
    """One position whose cumulative MTM at exit disagrees with its STORED
    booked P&L (`realized_pnl_abs`). `booked` is that stored figure — never the
    caller's own `pos.dollars`, which is what made this gate unfalsifiable."""
    date: str
    ticker: str
    structure: str
    contracts: int
    entry_sess: date
    exit_sess: date
    days_held: int
    mtm_at_exit: float | None
    booked: float | None
    diff: float | None


@dataclass(frozen=True)
class BookCurves:
    """Both bases for the same book, plus the G-MTM reconciliation result.

    Returned together on purpose: the pre-registration reads every verdict off
    `mtm` and keeps `realized` only for comparability with prior hedge
    verdicts, so handing back one without the other invites mixing them.
    """
    mtm: Curve
    realized: Curve
    tolerance: float
    n_positions: int
    n_reconciled: int
    n_carried_forward: int
    mismatches: list[Mismatch] = field(default_factory=list)

    @property
    def reconciles(self) -> bool:
        """G-MTM: every position's MTM at exit matched its booked P&L."""
        return not self.mismatches

    @property
    def worst_mismatch(self) -> float:
        """Largest absolute disagreement, in dollars. 0.0 when none."""
        vals = [abs(m.diff) for m in self.mismatches if m.diff is not None]
        return max(vals) if vals else 0.0


# ════════════════════════════════════════════════════════════════════════════
# Per-position marks
# ════════════════════════════════════════════════════════════════════════════

def _pnl_tokens(row: dict) -> list[float | None]:
    """`daily_pnl_csv` -> per-single-contract cumulative dollars, blanks as None."""
    raw = row.get("daily_pnl_csv") or ""
    return [None if tok.strip() == "" else float(tok) for tok in raw.split(",")]


def tolerance_for(contracts: int, tolerance: float = TOL_DOLLARS) -> float:
    """G-MTM's allowance for ONE position, in dollars.

    `daily_pnl_csv` is written at 2 decimals PER SINGLE CONTRACT, so the finest
    distinction the column can express at N contracts is `tolerance x N`. A
    flat dollar allowance would be tighter on a 66-contract HYG position than
    on a 1-contract NVDA one for no reason in the data.
    """
    return tolerance * max(1, int(contracts))


def stored_booked(rec) -> float | None:
    """The BOOK's own booked realized dollars for one record — G-MTM's target.

    `realized_pnl_abs` is what `scripts/backtest/simulate.py` wrote next to
    `daily_pnl_csv`, at the row's own contract count; `R_dol`
    (`realized_pnl_pct x denom x 100 x contracts`) is the fallback for a row
    that predates the column, and carries the extra rounding of a 4-decimal
    percentage.

    Read off the RECORD — never off a caller's `pos.dollars`. A caller that
    replays the row is free to put its replayed dollars in `pos.dollars`; this
    keeps the gate pointed at the stored outcome so the two can DISAGREE, which
    is the whole point of a reconciliation.
    """
    if not rec:
        return None
    t = rec.get("t")
    row = getattr(t, "row", None) or {}
    raw = row.get("realized_pnl_abs")
    if raw is not None and str(raw).strip() != "":
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    v = rec.get("R_dol")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def stored_realized(pos) -> float | None:
    """`stored_booked` for a position, or None when its record carries neither
    stored column (a synthesised instrument, or a hand-built fixture)."""
    return stored_booked(getattr(pos, "rec", None))


def position_marks(pos) -> tuple[list[date], list[float], int]:
    """`(sessions, cumulative MTM dollars, n_carried_forward)` for one position.

    Covers `[entry_sess, exit_sess]` inclusive, on the position's OWN price
    grid (`Trade.grid`) — so the first session is the first weekday AFTER the
    signal date, matching `account_sim.Pos.entry_sess`. Values are cumulative
    P&L in dollars at the position's contract count, measured from the entry
    premium, and equal the booked realized dollars at the exit session (G-MTM).

    `pos` is duck-typed on `account_sim.Pos`: `.rec["t"]` (a `harness.Trade`),
    `.contracts`, `.days_held`. A caller whose instrument is not a book row —
    a synthesised proxy-put hedge, say — may instead attach `.mtm_sessions`
    and `.mtm_dollars` and this function will use them verbatim, so the hedge
    modules never have to fake a `daily_pnl_csv`.

    A blank (unpriceable) day carries the previous mark forward; a blank before
    any priced day is 0.0. Both are counted in the third return value — a
    stale mark is a real limitation of the curve and the caller reports it.
    """
    override_s = getattr(pos, "mtm_sessions", None)
    override_d = getattr(pos, "mtm_dollars", None)
    if override_s is not None and override_d is not None:
        if len(override_s) != len(override_d):
            raise ValueError("mtm_sessions and mtm_dollars differ in length")
        return list(override_s), [float(v) for v in override_d], 0

    t = pos.rec["t"]
    grid = t.grid
    tokens = _pnl_tokens(t.row)
    if len(tokens) != len(grid):
        raise ValueError(
            f"{pos.rec.get('ticker')} {pos.rec.get('date')}: "
            f"{len(tokens)} daily_pnl_csv tokens vs {len(grid)} grid days")

    dh = pos.days_held
    if dh is None:
        raise ValueError(
            f"{pos.rec.get('ticker')} {pos.rec.get('date')}: no days_held — "
            f"a position with no exit index has no [entry, exit] window")
    end = min(int(dh), len(grid))          # same clamp as account_sim's exit_sess
    contracts = int(pos.contracts)

    sessions, dollars, carried = [], [], 0
    last = 0.0
    for i in range(end):
        tok = tokens[i]
        if tok is None:
            carried += 1
        else:
            last = tok * contracts
        sessions.append(grid[i])
        dollars.append(last)
    return sessions, dollars, carried


# ════════════════════════════════════════════════════════════════════════════
# Book curves + G-MTM
# ════════════════════════════════════════════════════════════════════════════

def book_curves(positions, *, tolerance: float = TOL_DOLLARS) -> BookCurves:
    """Both equity curves for `positions`, on one shared session axis.

    The axis is the SESSION UNIVERSE the pre-registration fixes: every session
    on which at least one position is open, i.e. the union of
    `[entry_sess, exit_sess]` over the book. Both curves are reported on it so
    time-under-water and Ulcer share a denominator and stay comparable.

    Book equity level at session `s` is, per position:
      * 0                       before its entry session
      * its cumulative MTM      on `[entry_sess, exit_sess]`
      * its booked realized $   after its exit session

    which is continuous at the exit precisely because G-MTM holds. The
    realized-on-close curve books the whole result on `exit_sess` and nothing
    before it — `account_sim.equity_curve`'s basis, restated on this axis.

    `tolerance` is the G-MTM allowance in DOLLARS, defaulting to
    `TOL_DOLLARS` (= $0.01, the write resolution of `daily_pnl_csv`).
    """
    positions = list(positions)
    if not positions:
        empty = Curve(MTM, [], [], []), Curve(REALIZED, [], [], [])
        return BookCurves(mtm=empty[0], realized=empty[1], tolerance=tolerance,
                          n_positions=0, n_reconciled=0, n_carried_forward=0,
                          mismatches=[])

    marks: list[tuple[object, list[date], list[float]]] = []
    carried_total = 0
    axis: set[date] = set()
    for p in positions:
        sess, dol, carried = position_marks(p)
        carried_total += carried
        marks.append((p, sess, dol))
        axis.update(sess)

    sessions = sorted(axis)
    index = {s: i for i, s in enumerate(sessions)}
    n = len(sessions)

    mtm_levels = [0.0] * n
    realized_levels = [0.0] * n
    mismatches: list[Mismatch] = []
    n_reconciled = 0

    for p, sess, dol in marks:
        booked = float(p.dollars) if p.dollars is not None else None
        mtm_at_exit = dol[-1] if dol else None

        # --- G-MTM, per position -------------------------------------------
        # The target is the row's STORED booked dollars, not `p.dollars`:
        # comparing against `p.dollars` let a caller check one replay against
        # itself. A record carrying NEITHER stored column has nothing
        # independent to check against, and the gate degrades to the caller's
        # own figure — stated here, not hidden, and it is the fixture case.
        target = stored_realized(p)
        if target is None:
            target = booked
        diff = (None if (target is None or mtm_at_exit is None)
                else mtm_at_exit - target)
        if diff is not None and abs(diff) <= tolerance_for(p.contracts, tolerance):
            n_reconciled += 1
        else:
            rec = p.rec
            mismatches.append(Mismatch(
                date=rec.get("date"), ticker=rec.get("ticker"),
                structure=rec.get("structure"), contracts=int(p.contracts),
                entry_sess=sess[0] if sess else None,
                exit_sess=sess[-1] if sess else None,
                days_held=p.days_held, mtm_at_exit=mtm_at_exit,
                booked=target, diff=diff))

        # --- accumulate both bases -----------------------------------------
        # `_carry_gaps` adds this position's mark to EVERY axis session in
        # [entry, exit], including any the position's own grid skipped.
        first = index[sess[0]]
        last = index[sess[-1]]
        _carry_gaps(mtm_levels, index, sess, dol, first, last)
        if booked is not None:
            for j in range(last + 1, n):
                mtm_levels[j] += booked
                realized_levels[j] += booked
            realized_levels[last] += booked

    mtm_daily = _to_daily(mtm_levels)
    realized_daily = _to_daily(realized_levels)
    return BookCurves(
        mtm=Curve(MTM, sessions, mtm_daily, mtm_levels),
        realized=Curve(REALIZED, sessions, realized_daily, realized_levels),
        tolerance=tolerance, n_positions=len(positions),
        n_reconciled=n_reconciled, n_carried_forward=carried_total,
        mismatches=mismatches)


def _carry_gaps(levels: list[float], index: dict, sess: list[date],
                dol: list[float], first: int, last: int) -> None:
    """Add this position's mark to EVERY axis session in `[first, last]`.

    Sessions the position's own grid skipped — a day another book row's grid
    supplied — inherit the last known mark. The position is open on them, so
    its contribution must not read as zero.
    """
    own = {index[s]: v for s, v in zip(sess, dol)}
    last_v = 0.0
    for i in range(first, last + 1):
        if i in own:
            last_v = own[i]
        levels[i] += last_v


def _to_daily(levels: list[float]) -> list[float]:
    """Level curve -> per-session change, from a zero start."""
    out, prev = [], 0.0
    for v in levels:
        out.append(v - prev)
        prev = v
    return out


# ════════════════════════════════════════════════════════════════════════════
# Path statistics
# ════════════════════════════════════════════════════════════════════════════

def max_drawdown(series):
    """Max peak-to-trough drawdown of a cumulative dollar curve, in DOLLARS.

    `series` is per-session CHANGES; the peak is seeded at 0.0, so a book that
    never gets above flat still reports its full fall. The return is <= 0.

    THE research tier's one drawdown implementation. It lived in
    `f4_deployment/bear_deploy.py` until 2026-08-29 and was imported UPWARDS
    from here — a `lib/` module executing an f4 study at import time. Moved
    here (this module already owns Ulcer and time-under-water, which speak the
    same shape) and re-exported by `bear_deploy` under its old name, so
    `bear_deploy` D3's dollar-drawdown criterion and this study's clause 1 are
    the same function object and cannot drift apart. Behaviour is byte-for-byte
    what it was.
    """
    peak, mdd = 0.0, 0.0
    cum = 0.0
    for v in series:
        cum += v
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    return mdd


def ulcer_index(levels, capital: float) -> float:
    """RMS percentage drawdown across the curve's sessions, in PERCENT.

    Drawdown is measured on ACCOUNT EQUITY (`capital + cumulative P&L`) against
    its running peak, seeded at `capital` — a P&L curve starts at zero and has
    no percentage of its own to speak of. `capital` is required and must be
    positive; the peak is monotone and starts at `capital`, so the denominator
    is never zero.
    """
    if capital is None or capital <= 0:
        raise ValueError("ulcer_index needs a positive capital base")
    levels = list(levels)
    if not levels:
        return float("nan")
    peak = float(capital)
    acc = 0.0
    for v in levels:
        eq = capital + v
        peak = max(peak, eq)
        dd = 100.0 * (eq - peak) / peak
        acc += dd * dd
    return math.sqrt(acc / len(levels))


def time_under_water(levels) -> float:
    """Share of sessions strictly below the running peak, in [0, 1].

    The peak is seeded at 0.0 — the book starts flat, and a session at a fresh
    high is not under water. Scale-free, so it needs no capital base.
    """
    levels = list(levels)
    if not levels:
        return float("nan")
    peak = 0.0
    under = 0
    for v in levels:
        peak = max(peak, v)
        if v < peak - _UNDERWATER_EPS:
            under += 1
    return under / len(levels)


def path_stats(curve: Curve, capital: float) -> PathStats:
    """The study's primary + co-primary metrics for one curve.

    `max_dd` reuses `bear_deploy.max_drawdown` on the per-session changes —
    never re-derived here, because `bear_deploy` D3's dollar-drawdown criterion
    is carried verbatim into this study's bar.
    """
    if not curve.sessions:
        return PathStats(basis=curve.basis, n_sessions=0, total=0.0, max_dd=0.0,
                         ulcer=float("nan"), tuw=float("nan"),
                         worst_session=float("nan"))
    return PathStats(
        basis=curve.basis,
        n_sessions=len(curve.sessions),
        total=curve.levels[-1],
        max_dd=max_drawdown(curve.daily),
        ulcer=ulcer_index(curve.levels, capital),
        tuw=time_under_water(curve.levels),
        worst_session=min(curve.daily),
    )
