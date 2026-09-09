"""
Group the broker's open option legs into logical positions, then mark them.

PRODUCTION TIER, pure computation. `s01_pull.py` returns the open book as a flat
list of contracts and quantities — the broker has no concept of "this long call
and that short call are one bull call spread". This module reassembles them so
exposure is reported per POSITION rather than per leg.

GROUPING RULE, and its honest limit. Legs are grouped by (underlying, expiry).
A vertical shares both, so it reassembles correctly. A CALENDAR or DIAGONAL
spans two expiries and therefore appears as two separate positions here.

That is a deliberate choice, not an oversight. The alternative — grouping by
underlying alone — merges genuinely unrelated positions on the same ticker
(a core long plus a hedge overlay) into one fictional structure, which
misreports both. Splitting a calendar overstates position COUNT but keeps every
delta-notional figure correct, because delta-notional is additive across legs:
the book's net exposure is identical either way.

The split is therefore PRESENTATIONAL ONLY, and nothing downstream reads a risk
verdict off it: `s03_risk.py` checks the per-position cap against each TICKER's
signed total (see its docstring), so a core vertical and the shorter-dated short
leg financing it net against each other regardless of landing in two groups
here. A presentation choice must not change a risk verdict.

`split_multi_expiry` names the affected groups so the report can say so out
loud rather than leaving the reader to infer it.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime

from ..config import Greeks, Leg, PositionRisk
from . import mapping
from .rawpull import open_legs
from ..s03_risk import mark_position

log = logging.getLogger(__name__)


def _structure_label(legs: list[Leg]) -> str:
    """Canonical structure for a leg group, via the shared classifier.

    `mapping.classify_structure()` takes the journal's own `Leg` objects, so
    there is nothing to adapt: the rules stay in the one module that encodes
    them. An open position is never a CLOSE, so the legs need no orientation
    (see `mapping.position_legs`), and the open book is not passed because the
    overlay test is about a fill sitting on top of a position, not about a
    position describing itself.
    """
    try:
        label = mapping.classify_structure(legs)[0]
    except Exception as exc:  # noqa: BLE001 - a label is cosmetic; exposure is not
        log.warning("Could not classify %s legs (%s) — labelling 'unclassified'",
                    len(legs), exc)
        return "unclassified"
    return label


def _contracts(legs: list[Leg]) -> int:
    """Position size in structures, not legs.

    The smallest |qty| across legs: a 1x1 vertical is one spread, and a 3x3 is
    three. An unbalanced group (say 3x1) is reported at the smaller count with a
    warning, because calling it 3 would overstate what is actually spread.
    """
    if not legs:
        return 0
    sizes = {abs(lg.qty) for lg in legs}
    if len(sizes) > 1:
        log.warning("Unbalanced leg quantities %s on %s — reporting the smaller count",
                    sorted(sizes), legs[0].symbol)
    return min(sizes)


def open_positions(raw: dict, greeks: dict[int, Greeks],
                   as_of: date | None = None) -> tuple[list[PositionRisk], list[str]]:
    """`(positions, notes)` — the open book marked for exposure.

    `notes` names anything the reader should not have to infer: multi-expiry
    holdings that were split, and symbols with no spot price.
    """
    as_of = as_of or date.today()
    legs = open_legs(raw)
    prices = raw.get("underlying_prices") or {}

    # Per-leg entry dates for the §5 exit-by display. Optional v1 field: an
    # older pull simply has none, and every position renders an em dash.
    entry_dates: dict[int, date | None] = {}
    for p in raw.get("positions") or []:
        ed = p.get("entry_date")
        entry_dates[int(p["conid"])] = (
            datetime.strptime(str(ed)[:10], "%Y-%m-%d").date() if ed else None)

    groups: dict[tuple[str, date], list[Leg]] = defaultdict(list)
    for lg in legs:
        groups[(lg.symbol, lg.expiry)].append(lg)

    by_symbol: dict[str, set] = defaultdict(set)
    for symbol, expiry in groups:
        by_symbol[symbol].add(expiry)

    notes: list[str] = []
    for symbol, expiries in sorted(by_symbol.items()):
        if len(expiries) > 1:
            notes.append(
                f"{symbol} holds legs in {len(expiries)} expiries "
                f"({', '.join(sorted(e.isoformat() for e in expiries))}) — reported as "
                "separate positions; a calendar/diagonal is split. This is presentational: "
                "net delta-notional is additive across legs, and the per-position cap is "
                "evaluated on the per-TICKER signed sum, so the split changes neither total "
                "nor cap verdict.")

    positions: list[PositionRisk] = []
    for (symbol, expiry), grp in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        grp.sort(key=lambda lg: (lg.right, lg.strike))
        conid_key = "|".join(str(c) for c in sorted(lg.conid for lg in grp))
        # Group entry date, all-or-nothing like the delta: one unknown leg makes
        # the whole group unknown (a spread dated off one leg is a wrong date,
        # not a partial one). Legs opened on different dates take the EARLIEST —
        # the §5 clock starts when the position first went on — and are flagged
        # so the report can say so.
        leg_dates = [entry_dates.get(lg.conid) for lg in grp]
        if any(d is None for d in leg_dates):
            group_entry, mixed = None, False
        else:
            group_entry, mixed = min(leg_dates), len(set(leg_dates)) > 1
        positions.append(mark_position(
            conid_key=conid_key, ticker=symbol, structure=_structure_label(grp),
            contracts=_contracts(grp), legs=grp, greeks=greeks,
            underlying_price=prices.get(symbol),
            dte=float((expiry - as_of).days),
            entry_date=group_entry, expiry=expiry, entry_date_mixed=mixed,
        ))

    missing_spot = sorted({p.ticker for p in positions if p.underlying_price is None})
    if missing_spot:
        notes.append(
            f"No spot price for {', '.join(missing_spot)} — their delta-notional could not "
            "be valued and they are excluded from exposure totals, NOT counted as zero.")

    return positions, notes
