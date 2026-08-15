"""
Group the broker's open option legs into logical positions, then mark them.

PRODUCTION TIER, pure computation. `pull.py` returns the open book as a flat
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
verdict off it: `risk.py` checks the per-position cap against each TICKER's
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

from .config import Greeks, Leg, PositionRisk
from .rawpull import contract_for
from .risk import mark_position

log = logging.getLogger(__name__)


def _legs_from_positions(raw: dict) -> list[Leg]:
    """Turn each open position row into a Leg.

    `position` is signed contracts as the broker reports it, so it carries the
    long/short direction directly — unlike a fill, where the side does.
    """
    legs: list[Leg] = []
    for p in raw.get("positions") or []:
        conid = int(p["conid"])
        c = contract_for(raw, conid)
        qty = int(round(float(p.get("position") or 0)))
        if qty == 0:
            continue
        if not c.get("expiry") or c.get("strike") is None:
            log.warning("conid %s has no strike/expiry — excluded from the open book", conid)
            continue
        legs.append(Leg(
            conid=conid,
            symbol=str(c["symbol"]).upper(),
            expiry=datetime.strptime(str(c["expiry"])[:10], "%Y-%m-%d").date(),
            strike=float(c["strike"]),
            right=str(c["right"]).upper()[:1],
            qty=qty,
            fill_price=float(p.get("avg_cost") or 0) / 100.0,
            commission=0.0,
            exec_id=f"pos:{conid}",
            fill_time=datetime.now(),
            open_close="O",
        ))
    return legs


def _structure_label(legs: list[Leg]) -> str:
    """Canonical structure for a leg group, via the shared classifier.

    Presents the legs in the shape `scripts/live_loop/mapping.classify_structure`
    expects rather than duplicating its rules — that function is shared with the
    fortnightly audit and must stay the single implementation.
    """
    try:
        from scripts.live_loop import mapping
    except ImportError:  # pragma: no cover - alternate sys.path layout
        from live_loop import mapping

    adapted = {"legs": [{"trade": {"side": "BUY" if lg.qty > 0 else "SELL",
                                   "price": lg.fill_price,
                                   "commission": lg.commission,
                                   "symbol": lg.symbol},
                         "match": {"symbol": lg.symbol, "strike": lg.strike,
                                   "expiry": lg.expiry.isoformat(),
                                   "right": lg.right, "position": lg.qty}}
                        for lg in legs]}
    try:
        label = mapping.classify_structure(adapted, [])[0]
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
    legs = _legs_from_positions(raw)
    prices = raw.get("underlying_prices") or {}

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
        positions.append(mark_position(
            conid_key=conid_key, ticker=symbol, structure=_structure_label(grp),
            contracts=_contracts(grp), legs=grp, greeks=greeks,
            underlying_price=prices.get(symbol),
            dte=float((expiry - as_of).days),
        ))

    missing_spot = sorted({p.ticker for p in positions if p.underlying_price is None})
    if missing_spot:
        notes.append(
            f"No spot price for {', '.join(missing_spot)} — their delta-notional could not "
            "be valued and they are excluded from exposure totals, NOT counted as zero.")

    return positions, notes
