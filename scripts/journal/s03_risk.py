"""
Step 3 — mark the open book for delta exposure and check it against the
deployment caps.

PRODUCTION TIER, pure computation — no network, no I/O beyond reading
`config/account-sim.yml`. Feed it positions plus the greeks `s01_pull.py` fetched
and it returns `PositionRisk` records and a `BookRisk` summary.

WHERE THE CAPS COME FROM. `config/account-sim.yml` sets `caps.per_position`
(0.25) and `caps.net` (2.50) as fractions of equity. That study is research tier
and its conclusions do not automatically ship — but these two numbers are
explicitly "a friction model, NOT a tuned parameter", fitted to nothing, so
reusing them as a live exposure guide does not smuggle a backtest conclusion
into production. What does NOT carry over is the study's $25,000
`account.capital`: live equity is the broker's NetLiquidation, so the caps bind
against the real account and the study's own denominator is ignored.

THE FORMULA is the study's, unchanged, so a live book and a simulated one are
directly comparable:

    signed_dn = delta x 100 x contracts x underlying_price

generalised across legs — a spread's delta-notional is the sum of its legs'
signed contributions, which reduces to the single-leg form for a naked option.

WHAT THE PER-POSITION CAP BINDS ON: the signed sum of `delta_notional` across
every position on a TICKER, not each position alone. `lib/book.py` groups open legs
by (underlying, expiry), so a core vertical and the shorter-dated short leg sold
to finance it land in two different groups — and that short leg exists precisely
to cut the ticker's directional exposure. Checking each group alone reports a
breach the operator has already hedged. Netting per ticker is what the cap was
always trying to measure; the (underlying, expiry) split is a presentation
choice, and a presentation choice must not change a risk verdict.

The NET cap is unaffected: it already sums the whole book, and delta-notional is
additive, so no grouping decision can move it.

THE MISSING/ZERO INVARIANT. A position whose delta the broker did not return is
NOT worth zero delta — it is worth an unknown delta. Such positions are excluded
from every total and reported separately, and `BookRisk.complete` is False so a
caller can refuse to act on a partial picture. Never sum without filtering on
`PositionRisk.priced`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import yaml

from .config import (ACCOUNT_SIM_YML, DELTA_SOURCE_UNAVAILABLE,
                     OPTION_MULTIPLIER, Greeks, Leg, PositionRisk)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Caps:
    """Exposure caps as fractions of equity, plus the equity they bind against."""

    per_position: float
    net: float
    net_liq: float

    @property
    def per_position_dollars(self) -> float:
        return self.per_position * self.net_liq

    @property
    def net_dollars(self) -> float:
        return self.net * self.net_liq


@dataclass
class BookRisk:
    """The whole open book's exposure, and how much cap room is left."""

    positions: list[PositionRisk] = field(default_factory=list)
    unpriced: list[PositionRisk] = field(default_factory=list)
    caps: Caps | None = None
    net_delta_notional: float = 0.0
    gross_delta_notional: float = 0.0
    breaches: list[str] = field(default_factory=list)
    # Signed delta-notional per ticker — what the per-position cap is checked
    # against. Defaulted so a caller building a BookRisk by hand (tests, and
    # anything that only wants the totals) does not have to supply it.
    ticker_exposure: dict[str, float] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """False when any open position lacks a delta.

        The totals are still correct for what they cover, but they understate
        the book. A caller sizing a new position off `net_headroom` while this
        is False is working from a floor, not the real number.
        """
        return not self.unpriced

    @property
    def net_utilisation(self) -> float | None:
        if self.caps is None or self.caps.net_dollars == 0:
            return None
        return abs(self.net_delta_notional) / self.caps.net_dollars

    @property
    def net_headroom(self) -> float | None:
        """Dollars of delta-notional still deployable under the net cap."""
        if self.caps is None:
            return None
        return max(0.0, self.caps.net_dollars - abs(self.net_delta_notional))


def load_caps(net_liq: float, path=ACCOUNT_SIM_YML) -> Caps:
    """Read the two caps out of config/account-sim.yml and bind them to live equity."""
    if net_liq is None or net_liq <= 0:
        raise ValueError(
            f"NetLiquidation must be a positive number to evaluate caps, got {net_liq!r}")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    caps = cfg.get("caps") or {}
    try:
        per_position = float(caps["per_position"])
        net = float(caps["net"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"{path} is missing a usable caps.per_position / caps.net — "
            "refusing to guess an exposure limit") from exc
    return Caps(per_position=per_position, net=net, net_liq=float(net_liq))


def position_delta(legs: list[Leg], greeks: dict[int, Greeks]) -> float | None:
    """Net delta of a position, in contract terms. None if ANY leg lacks a delta.

    All-or-nothing on purpose: a spread priced on one leg only is not a partially
    known delta, it is a wrong one — the missing leg is precisely the hedge.
    """
    if not legs:
        return None
    total = 0.0
    for lg in legs:
        g = greeks.get(lg.conid)
        if g is None or not g.has_delta:
            return None
        total += g.delta * lg.qty
    return total


def short_leg_delta(legs: list[Leg], greeks: dict[int, Greeks]) -> float | None:
    """|delta| of the short leg that binds deployment-rules.md §3.

    A vertical has one short leg. If several are short, the one closest to the
    money (largest |delta|) is the binding one, so that is what is returned.
    """
    shorts = []
    for lg in legs:
        if lg.qty >= 0:
            continue
        g = greeks.get(lg.conid)
        if g is not None and g.has_delta:
            shorts.append(abs(g.delta))
    return max(shorts) if shorts else None


def delta_source(legs: list[Leg], greeks: dict[int, Greeks]) -> str:
    """Where this position's delta actually came from.

    Read off the legs rather than assumed: the two transports source deltas
    differently (the Client Portal path from the broker, the Flex path from
    Barchart EOD), and `delta_source` is written to the permanent journal row.
    Stamping a broker name on a scraped delta would misdescribe the evidence
    every later reader relies on to judge how much to trust the exposure.

    Mixed sources across legs are reported as such rather than collapsed to
    one, because a position half-marked from a different feed is exactly the
    case worth noticing.
    """
    found = sorted({greeks[lg.conid].source for lg in legs
                    if lg.conid in greeks and greeks[lg.conid].has_delta})
    if not found:
        return DELTA_SOURCE_UNAVAILABLE
    return found[0] if len(found) == 1 else "+".join(found)


def mark_position(conid_key: str, ticker: str, structure: str, contracts: int,
                  legs: list[Leg], greeks: dict[int, Greeks],
                  underlying_price: float | None,
                  dte: float | None = None) -> PositionRisk:
    """Build one PositionRisk. Leaves delta fields None when unpriceable."""
    pdelta = position_delta(legs, greeks)
    iv = next((greeks[lg.conid].iv for lg in legs
               if lg.conid in greeks and greeks[lg.conid].iv is not None), None)

    dn = None
    source = DELTA_SOURCE_UNAVAILABLE
    if pdelta is not None and underlying_price is not None:
        dn = pdelta * OPTION_MULTIPLIER * underlying_price
        source = delta_source(legs, greeks)
    elif pdelta is not None:
        log.warning("%s %s: have delta but no underlying price — cannot value exposure",
                    ticker, structure)

    return PositionRisk(
        conid_key=conid_key, ticker=ticker, structure=structure,
        contracts=contracts, legs=legs,
        position_delta=pdelta, delta_notional=dn,
        underlying_price=underlying_price,
        short_leg_delta=short_leg_delta(legs, greeks),
        iv=iv, delta_source=source, dte=dte,
    )


def per_ticker_delta_notional(positions: list[PositionRisk]) -> dict[str, float]:
    """Signed delta-notional summed per ticker, over PRICED positions only.

    The unit the per-position cap binds on — see the module docstring. Unpriced
    positions are excluded rather than counted as zero, the same rule every other
    total here follows: a ticker whose exposure is partly unknown gets a partial
    sum and the report says the totals are a floor.

    Sorted by ticker so breach messages come out in a stable order.
    """
    totals: dict[str, float] = {}
    for p in positions:
        if not p.priced:
            continue
        totals[p.ticker] = totals.get(p.ticker, 0.0) + p.delta_notional
    return dict(sorted(totals.items()))


def assess(positions: list[PositionRisk], caps: Caps) -> BookRisk:
    """Total the book, compute cap utilisation, and flag every breach.

    Breaches are reported for ALL tickers that exceed the cap, not just the
    first — the caller is looking at a book that already exists, so there is
    nothing to be gained by short-circuiting the way an admission check would.

    The per-position cap is checked against each TICKER's signed total, not
    each position's own delta-notional. A financing short leg at another expiry
    is a different position here but the same directional risk, and netting it
    is the whole point of having sold it.
    """
    priced = [p for p in positions if p.priced]
    unpriced = [p for p in positions if not p.priced]

    net = sum(p.delta_notional for p in priced)
    gross = sum(abs(p.delta_notional) for p in priced)
    by_ticker = per_ticker_delta_notional(priced)

    breaches: list[str] = []
    for ticker, total in by_ticker.items():
        if abs(total) <= caps.per_position_dollars:
            continue
        # Name the constituents so the netting is auditable from the report
        # alone — a bare ticker total invites the reader to go and re-derive it.
        parts = ", ".join(
            f"{p.structure} {p.delta_notional:+,.0f}"
            for p in priced if p.ticker == ticker)
        n = sum(1 for p in priced if p.ticker == ticker)
        breaches.append(
            f"{ticker}: |net delta-notional across {n} position(s)| "
            f"${abs(total):,.0f} exceeds the per-position cap "
            f"${caps.per_position_dollars:,.0f} ({caps.per_position:.2f}x equity) "
            f"[{parts}]")
    if abs(net) > caps.net_dollars:
        breaches.append(
            f"BOOK: |net delta-notional| ${abs(net):,.0f} exceeds the net cap "
            f"${caps.net_dollars:,.0f} ({caps.net:.2f}x equity)")

    for p in unpriced:
        log.warning("%s %s excluded from exposure totals — no delta from broker",
                    p.ticker, p.structure)

    return BookRisk(positions=priced, unpriced=unpriced, caps=caps,
                    net_delta_notional=net, gross_delta_notional=gross,
                    breaches=breaches, ticker_exposure=by_ticker)


def headroom_for(book: BookRisk, candidate_dn: float,
                 ticker: str | None = None) -> tuple[bool, str | None]:
    """Would adding `candidate_dn` of delta-notional still fit under both caps?

    Returns `(ok, binding_constraint)` — the FIRST failing cap, checked
    per-position then net, the same fixed order
    `scripts/backtest_study/f4_deployment/account_sim.py::admission` uses so that "exactly one
    binding constraint" stays well defined.

    Pass `ticker` to check the candidate against that ticker's EXISTING signed
    exposure, which is what `assess()` flags a breach on — otherwise the deploy
    card and the journal would be using two different definitions of the same
    cap. It loosens admission on a ticker already carrying a short overlay and
    tightens it on one carrying a long core, both correctly. Omitting `ticker`
    keeps the standalone-candidate behaviour unchanged.
    """
    if book.caps is None:
        return False, "no caps loaded"
    existing = (per_ticker_delta_notional(book.positions).get(ticker, 0.0)
                if ticker else 0.0)
    if abs(existing + candidate_dn) > book.caps.per_position_dollars:
        return False, "per_pos_delta"
    if abs(book.net_delta_notional + candidate_dn) > book.caps.net_dollars:
        return False, "net_delta"
    return True, None
