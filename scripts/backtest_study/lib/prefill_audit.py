"""Did this stored row book its exit BEFORE the position was filled?

Reports, never gates — the same contract as `basis_audit.py`.

THE DEFECT
----------
A row's grid starts the weekday after the signal, but the FILL can land several
days later (a contract with no bar until day 3). Until the robustness fold's B2
landed on 2026-09-08, `_simulate` priced those pre-fill days by carry-forward,
so an exit rule could fire — and a realized P&L be booked — on a day the
position did not exist. `simulate.py` now stamps every pre-fill grid day
UNPRICED (`pre_entry`), so no row written since can do it.

The rows written BEFORE that fix are still in the book, and nothing detected
them. TLT 2025-04-01 is the worked example: a `profit_target` on grid day 2 at a
net of exactly `0.0000` sourced `barchart+bs`, two days before its own fill,
recorded as +100%. Re-priced under current code it runs to expiry and books max
loss, -754%. Seventeen rows across the two tabs are of that shape.

HOW IT IS DETECTED
------------------
The fill day is RECORDED, not inferred: `classify._entry_row_from_history`
stamps `dte_entry` as `(expiration - entry_day).days` on the ANCHOR contract, so

    entry_day = legs[0].expiration - dte_entry

comes back exactly. Its 1-based position in the row's own grid is the earliest
`days_held` the row could honestly carry. Anything less booked its exit before
the fill.

This is deliberately read off the row rather than re-derived from the option
cache. The cache has grown since these rows were priced — the
`HISTORY_START_DATE` fix, the far-call fetch and 178 restored files — so a day
derived from it today is not the day production used. That mistake cost a
separate bug hunt on 2026-09-19; see `bear_rewrap.recorded_entry_date`.

WHAT A STUDY SHOULD DO WITH IT
------------------------------
`load_book` stamps `prefill_verdict` / `fill_trusted` on every record and tallies
`diag["prefill_coherence"]`. Nothing is dropped and nothing raises: a study that
pools P&L across the book is reading 17 rows whose realized figure is not a
trade, and should filter on `fill_trusted` before it concludes from one. A study
that re-replays every row from marks is unaffected, because it never reads the
stored outcome.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

# Verdicts that mean "believe this row's realized exit".
TRUSTED = {"ok"}


def entry_index(trade) -> int | None:
    """The 1-based grid position of the day this row was FILLED, or None.

    None when the row cannot answer — no legs, an unparseable `dte_entry`, or a
    fill day that is not on its own grid (a weekend stamp, or a `dte_entry` from
    a leg other than the anchor). An unanswerable row is `absent`, never a
    conflict: not knowing is not the same as being wrong.
    """
    legs = getattr(trade, "legs", None)
    if not legs:
        return None
    try:
        dte = int(trade.dte_entry)
    except (TypeError, ValueError, AttributeError):
        return None
    grid = getattr(trade, "grid", None)
    if not grid:
        return None
    entry_day = legs[0].expiration - timedelta(days=dte)
    # A fill AT OR BEFORE the grid's first day is grid position 1. This is the
    # legacy `entry_timing: signal_eod` shape, where the fill is the SIGNAL day
    # and the grid starts the weekday after it: the position exists for every
    # grid day, so no exit on the grid can precede it. Reporting that as
    # `absent` would blank the audit on a whole timing convention.
    if entry_day <= grid[0]:
        return 1
    try:
        return grid.index(entry_day) + 1
    except ValueError:
        return None


def audit_trade(trade, days_held) -> str:
    """'ok' | 'absent' | 'pre_entry_exit'.

    `days_held` is the row's stored 1-based exit index. A row with no exit index
    (an unpriced `underlying_trend` proxy row, or one that never exited) has no
    claim to check and audits as `absent`.
    """
    if days_held is None:
        return "absent"
    try:
        dh = int(days_held)
    except (TypeError, ValueError):
        return "absent"
    idx = entry_index(trade)
    if idx is None:
        return "absent"
    return "pre_entry_exit" if dh < idx else "ok"


def audit(records) -> tuple[Counter, list[dict]]:
    """`(tally, offenders)` over records carrying `t` (a `Trade`) and `days_held`.

    `offenders` holds only the rows whose exit predates their fill — never the
    `absent` ones, which are simply unanswerable.
    """
    tally: Counter = Counter()
    offenders: list[dict] = []
    for r in records:
        v = audit_trade(r.get("t"), r.get("days_held"))
        tally[v] += 1
        if v not in TRUSTED and v != "absent":
            offenders.append({**r, "prefill_verdict": v})
    return tally, offenders


def format_tally(tally: Counter, total: int | None = None) -> str:
    """One line for a study header. Names the conflict bucket even at zero — a
    check that prints nothing when it passes is a check nobody notices has
    stopped running."""
    n = total if total is not None else sum(tally.values())
    return ("exit-after-fill: "
            f"{tally.get('ok', 0)} ok, "
            f"{tally.get('absent', 0)} unanswerable, "
            f"{tally.get('pre_entry_exit', 0)} pre_entry_exit of {n}")
