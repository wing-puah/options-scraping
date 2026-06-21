"""Signed-leg position model.

A position is a list of `Leg`s, each carrying its own quantity (signed, the
per-unit ratio: + long, − short), ticker, expiration, strike, and option type.
This generalises the old single-leg / vertical / iron-condor special cases to
arbitrary structures (calendar, diagonal, ratio, …).

Serialised form (one leg per line), with the signed quantity LAST so a cell never
starts with ``+`` / ``-`` (Google Sheets coerces a leading sign into a formula):

    AMD:2025-10-16:130:C +3
    AMD:2025-09-15:140:C -2

i.e. ``<TICKER>:<YYYY-MM-DD>:<STRIKE>:<C|P> <signed_qty>``. Parsing also accepts the
older leading-quantity form (``+3 AMD:2025-10-16:130:C``) for back-compat.
"""
import re
from datetime import date
from typing import NamedTuple


class Leg(NamedTuple):
    qty: int          # signed per-unit ratio: + long, − short
    ticker: str
    expiration: date
    strike: float
    opt_type: str     # "Call" | "Put"


# Quantity LAST (canonical, sheet-safe): TICKER:EXP:STRIKE:CP +N
_LEG_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z.\-]*)\s*:\s*(\d{4}-\d{2}-\d{2})\s*:\s*"
    r"(\d+(?:\.\d+)?)\s*:\s*([CPcp])\s+([+-]?\d+)\s*$"
)
# Quantity FIRST (legacy): +N TICKER:EXP:STRIKE:CP
_LEG_RE_LEADING = re.compile(
    r"^\s*([+-]?\d+)\s+([A-Za-z][A-Za-z.\-]*)\s*:\s*"
    r"(\d{4}-\d{2}-\d{2})\s*:\s*(\d+(?:\.\d+)?)\s*:\s*([CPcp])\s*$"
)

_CP = {"c": "Call", "p": "Put"}


def _parse_leg_line(line: str) -> Leg | None:
    """Parse one leg line in either the canonical (qty last) or legacy (qty first)
    form. Returns None for non-matching lines and zero-quantity legs."""
    m = _LEG_RE.match(line)
    if m:
        ticker, exp, strike, cp, qty = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    else:
        m = _LEG_RE_LEADING.match(line)
        if not m:
            return None
        qty, ticker, exp, strike, cp = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    q = int(qty)
    if q == 0:
        return None
    return Leg(qty=q, ticker=ticker.upper(), expiration=date.fromisoformat(exp),
               strike=float(strike), opt_type=_CP[cp.lower()])


def parse_legs(text: str) -> list[Leg] | None:
    """Parse an explicit leg-string out of a play cell.

    Returns the legs when at least one line matches the leg grammar, else None
    (so the caller falls back to freeform classification). Non-matching lines are
    ignored, which lets a leg-string sit alongside prose in the same cell. Both the
    canonical (qty last) and legacy (qty first) orderings are accepted.
    """
    if not text:
        return None
    legs: list[Leg] = []
    for line in str(text).splitlines():
        leg = _parse_leg_line(line)
        if leg is not None:
            legs.append(leg)
    return legs or None


def merge_legs(legs: list[Leg]) -> list[Leg]:
    """Combine legs that name the same contract, summing their signed quantities.

    Legs sharing (ticker, expiration, strike, opt_type) are folded into one with the
    summed quantity; legs that net to zero are dropped. First-seen order is preserved.
    This lets a structure repeat a contract (e.g. +2 / -1 → +1) instead of being
    rejected as degenerate.
    """
    order: list[tuple] = []
    totals: dict[tuple, int] = {}
    by_key: dict[tuple, Leg] = {}
    for leg in legs:
        key = (leg.ticker, leg.expiration, round(leg.strike, 4), leg.opt_type)
        if key not in totals:
            order.append(key)
            by_key[key] = leg
        totals[key] = totals.get(key, 0) + leg.qty
    merged = []
    for key in order:
        q = totals[key]
        if q == 0:
            continue
        merged.append(by_key[key]._replace(qty=q))
    return merged


def format_legs(legs: list[Leg]) -> str:
    """Serialise legs to the multi-line column string (quantity last, sheet-safe)."""
    out = []
    for leg in legs:
        cp = "C" if leg.opt_type == "Call" else "P"
        out.append(f"{leg.ticker}:{leg.expiration.isoformat()}:"
                   f"{leg.strike:g}:{cp} {leg.qty:+d}")
    return "\n".join(out)


def legs_from_structure(_structure: str, opt_type: str, ticker: str, exp: date,
                        K: float, K_short: float | None, is_credit: bool) -> list[Leg]:
    """Map a classified single-leg / vertical structure onto signed legs.

    The anchor leg sits at strike ``K`` (the leg matched to flow); its sign is
    long for debit structures and short for credit structures. The contra leg, if
    any, takes the opposite sign at ``K_short``. This reproduces the old
    ``entry_price = primary − contra`` / ``is_credit`` semantics under the unified
    signed-net P&L formula. Iron condors are built separately (see
    ``iron_condor_legs``) because their wings depend on the entry underlying.
    """
    anchor_qty = -1 if is_credit else 1
    legs = [Leg(anchor_qty, ticker, exp, round(K, 4), opt_type)]
    if K_short is not None:
        legs.append(Leg(-anchor_qty, ticker, exp, round(K_short, 4), opt_type))
    return legs


def iron_condor_legs(ticker: str, exp: date, K_lp: float, K_sp: float,
                     K_sc: float, K_lc: float) -> list[Leg]:
    """Four iron-condor legs (long-put wing, short put, short call, long-call wing).

    The short put (index 1) is the flow-matched anchor.
    """
    return [
        Leg(1,  ticker, exp, round(K_lp, 4), "Put"),
        Leg(-1, ticker, exp, round(K_sp, 4), "Put"),
        Leg(-1, ticker, exp, round(K_sc, 4), "Call"),
        Leg(1,  ticker, exp, round(K_lc, 4), "Call"),
    ]
