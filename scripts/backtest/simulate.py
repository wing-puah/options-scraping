import logging
import math
from datetime import timedelta

from .helpers import (
    _to_float, _row_iv, _contract_key,
    _weekday_grid,
    _defined_risk_bounds, _max_loss_per_unit,
)
from .classify import CREDIT_STRUCTURES, DEBIT_STRUCTURES
from .legs import format_legs, merge_legs

log = logging.getLogger("backtest")


# ─── Quote handling: staleness, zero bids, spreads ─────────────────────────────
# Three properties of a Barchart mark the simulation used to be blind to. All
# three are read off the per-contract history ROW (``barchart_details``), which
# carries Bid/Ask; the price SERIES carries only the pre-computed mark.

# How many CALENDAR days a Barchart mark may be carried forward before the day is
# tagged `barchart_stale` (robustness review B3). The price is still used — the
# tag is what changes, so a frozen contract stops reading as a live quote in
# `daily_source_csv` / `pct_stale_days`. 5 days is the same staleness convention
# `_entry_row_from_history` and the history cache already use (a Friday mark
# covers the following Wednesday). Config: `simulation.max_price_carry_days`;
# set it to null to carry forever (the pre-2026-09-07 behaviour).
_DEFAULT_MAX_CARRY_DAYS = 5


def _snap_asof(series, key, day, expiration=None):
    """``(price, snap_date)`` for the most recent scrape on-or-before ``day``.

    Identical carry-forward to ``helpers._price_asof``, but it also returns WHICH
    day the mark came from, so the caller can tell a fresh quote from one carried
    forward across a contract that stopped printing. ``(None, None)`` when there
    is no usable snap.
    """
    snaps = series.get(key)
    if not snaps:
        return None, None
    best = (None, None)
    for snap_date, price in snaps:
        if snap_date > day:
            break
        if expiration and snap_date > expiration:
            break
        best = (price, snap_date)
    return best


def _bid_ask(row) -> tuple[float | None, float | None]:
    """``(bid, ask)`` off a Barchart history row; ``None`` per side when the column
    is absent or unparseable (older cache files, synthesised rows in tests)."""
    if not row:
        return None, None
    return _to_float(row.get("Bid")), _to_float(row.get("Ask"))


def _zero_bid_mark(row) -> float | None:
    """The liquidation mark for a ZERO-BID contract, or None to keep the row's own
    ``_mark`` (robustness review B5).

    ``lib/barchart/options.py::_mark`` is mid(Bid,Ask) and falls through to
    ``Latest`` — a LAST TRADE price — whenever either side of the quote is missing
    or zero. On a contract that has gone bid-less that last trade can be days old
    and far above anything the position could actually be closed at, so the leg
    stays "valued" while its real liquidation value is near zero. Rule:

      bid == 0, ask == 0  → 0.0        (nothing is bid and nothing is offered)
      bid == 0, ask  > 0  → ask / 2    (the true mid of a 0×ask market)
      otherwise           → None       (a two-sided quote, or no quote data)

    Sign-independent: it is a property of the CONTRACT's market, so a short leg is
    re-marked the same way (a naked short at a 0 bid is closed for near nothing).
    """
    bid, ask = _bid_ask(row)
    if bid is None or bid > 0 or ask is None:
        return None
    return 0.0 if ask <= 0 else ask / 2


def _entry_side_mark(row, qty) -> float | None:
    """The ENTRY mark for a leg whose entry-day quote is ONE-SIDED, or None to
    leave that leg's entry pricing unchanged (2026-09-19).

    `_zero_bid_mark` above is a LIQUIDATION rule and stays that, for the daily
    mark-to-market it was written for. At ENTRY it is the wrong rule, because it
    is sign-independent: on a 0 × ask market it hands a leg being SOLD half the
    ask as premium RECEIVED. Nothing is bid, so nothing is received. On the HYG
    2025-04-09 proxy row that turned a six-day-old `bid 0 / ask 2.68` snap on the
    short 72P into 1.34 of credit, took the bear put spread's entry to −0.37, and
    `_exit_basis` then keyed it CREDIT and booked +100%
    (research/next-steps.md §2.11).

    An entry fill happens on the side the leg actually trades, so:

    SCOPE. It governs EVERY barchart entry fill whose quote is one-sided: the
    quote-derived mark (the branch `_zero_bid_mark` used to own) and, since
    2026-09-22, the entry-day `Open` print too, which it now PRECEDES (see
    `_entry_price_leg`). Before 2026-09-22 the Open print won ahead of it. Rules:

      quote is two-sided (bid > 0)        → None   (mid / the source chain below,
                                                    UNCHANGED — this rule does not
                                                    convert the book to touch
                                                    pricing)
      no quote at all (no Ask column)     → None   (no quote data is not a zero
                                                    bid: the existing fallback or
                                                    skip behaviour decides)
      bid absent or 0, leg SOLD (qty < 0) → 0.0    (the BID. Nothing is bid, so no
                                                    credit is received.)
      bid absent or 0, leg BOUGHT (qty>0) → ask    (the ASK, clamped at 0)

    A REAL zero bid is a quote whose bid side is 0; that is a number, and 0.0 is
    the right mark for it. NO QUOTE DATA is the absence of one and must never be
    read as "bid 0, therefore it sells for 0" — hence the `ask is None` guard,
    which is what separates the two cases.

    This is touch pricing, the same side `simulation.slippage_frac_of_spread` at
    0.5 would fill at — but it is a PRICE, not a cost: it applies whatever the
    cost knobs say, and the caller nulls the leg's quoted spread so slippage is
    not charged a second time on a leg already filled at the touch.
    """
    bid, ask = _bid_ask(row)
    if ask is None:
        return None          # no quote data — not a zero-bid market
    if bid is not None and bid > 0:
        return None          # genuine two-sided quote — pricing unchanged
    if qty < 0:
        return 0.0           # sold at the bid, and the bid is 0
    return ask if ask > 0 else 0.0


def _leg_spread(row) -> float | str | None:
    """Quoted bid/ask spread in option points; None when the row carries no
    usable two-sided quote (slippage then falls back to 0 and the row says so
    through `cost_basis`); `JUNK_SPREAD` when the quote is junk
    (`_is_junk_quote`, 2026-09-24) — that leg-side charges commission only."""
    if _is_junk_quote(row):
        return JUNK_SPREAD
    bid, ask = _bid_ask(row)
    if bid is None or ask is None or ask <= 0 or bid < 0 or ask < bid:
        return None
    return ask - bid


# ─── Junk quotes (operator ruling 2026-09-24) ─────────────────────────────────
# Barchart's end-of-day history carries quotes nobody could trade at: HYG
# 2024-07-19 74P on 2024-05-16 printed Latest 0.11 against `bid 0.09 / ask 5.00`,
# and on 05-21 Latest 0.07 against `bid 0 / ask 4.80`. The mid of the first is
# 2.545 — 23× the option's price. Before this rule the cost model charged a
# quarter of that 4.91 spread as slippage (the HYG 2024-05-15 bull put spread:
# $1,250 of cost on a $105 credit), and the daily mark used the mid.
#
# ONE test, applied everywhere a quote is read: cost, daily marks, exit marks
# and entry fills. The rules that consume it are `_leg_spread` (cost),
# `_junk_entry_fill` (entry) and the daily branch of `_simulate._price_leg`.

#: Sentinel "quoted spread" of a leg whose quote is junk: slippage is charged
#: at 0 on that leg-side and the row's `cost_basis` says `no_spread_<side>`.
JUNK_SPREAD = "junk"

#: `skip_reason` / refusal code for a BOUGHT leg whose entry-day quote is junk
#: and which did not trade that day: there is no real price to pay.
JUNK_ENTRY_REFUSAL = "junk_entry_quote"


#: Legacy Cboe maximum bid/ask differential by BID price — the pre-electronic
#: "quote width" obligation on market makers (Cboe Rule 8.7 bid/ask
#: differentials): ``(bid below this, max width)``, the last row open-ended.
#: Operator ruling 2026-09-24.
QUOTE_WIDTH_LIMITS = ((2.0, 0.25), (5.0, 0.40), (10.0, 0.50), (20.0, 0.80),
                      (float("inf"), 1.00))

#: A quote is junk past this multiple of the legacy width. A JUDGEMENT CALL
#: (operator, 2026-09-24), not from the Cboe rule: the legacy limit bound a
#: market maker's live quote, and an end-of-day snapshot is looser.
QUOTE_WIDTH_MULTIPLE = 2.0


def _legacy_width(bid: float) -> float:
    """W(bid): the legacy Cboe maximum bid/ask differential at this bid."""
    for upper, width in QUOTE_WIDTH_LIMITS:
        if bid < upper:
            return width
    return QUOTE_WIDTH_LIMITS[-1][1]


def _is_junk_quote(row) -> bool:
    """True when the row's quote is JUNK (operator rulings 2026-09-24):

        bid <= 0                                   no bid
        or  ask - bid > mid                        ask more than 3x the bid
        or  ask - bid > QUOTE_WIDTH_MULTIPLE * W(bid)   wider than twice the
                                                   legacy Cboe width limit

    The width test is the main line; the mid test is kept because it catches
    tiny quotes the width test misses (`0.02 x 0.07`: spread 0.05 < 0.50).

    A row with no Ask is NOT junk — it is NO QUOTE, and every consumer keeps its
    existing no-quote behaviour. A bid column that is blank while an ask is
    quoted counts as no bid, so it is junk. `bid 0.05 / ask 0.08` is a normal
    cheap quote (spread 0.03 < mid 0.065) and is not junk.
    """
    bid, ask = _bid_ask(row)
    if ask is None:
        return False
    if bid is None or bid <= 0:
        return True
    spread = ask - bid
    return (spread > (bid + ask) / 2
            or spread > QUOTE_WIDTH_MULTIPLE * _legacy_width(bid))


def _traded_price(row) -> float | None:
    """The day's ``Latest`` when the contract TRADED that day (Volume > 0 and
    Latest > 0), else None. On a no-volume day ``Latest`` is an older last
    trade, not that day's price."""
    if not row:
        return None
    vol, latest = _to_float(row.get("Volume")), _to_float(row.get("Latest"))
    if vol and vol > 0 and latest and latest > 0:
        return latest
    return None


def _junk_entry_fill(row, qty, open_print: bool = True):
    """The ENTRY fill for a leg whose entry quote is junk, or None when the
    quote is not junk (the existing entry chain then decides unchanged).

    Returns ``(price, tag)``, or ``(None, JUNK_ENTRY_REFUSAL)`` when no real
    price exists. In order:

      1. SOLD leg, no bid        → 0.0 (`_entry_side_mark`: nothing is bid,
                                   nothing is received; precedes any print)
      2. the contract TRADED     → the day's Open print (when ``open_print`` and
                                   Open > 0), else its Latest
      3. SOLD leg, bid > 0       → the bid (a real bid, however wide the ask)
      4. BOUGHT leg              → refused. The ask of a junk quote is not a
                                   price anyone paid: `bid 0.09 / ask 5.00` on
                                   a 0.11 option must never fill at 5.00.

    ``open_print`` is False when ``row`` is not the entry day's own row (a
    carried snap): an old session's Open is not an entry-day fill.
    """
    if not _is_junk_quote(row):
        return None
    if qty < 0:
        side = _entry_side_mark(row, qty)
        if side is not None:
            return side, "barchart_side"
    if _traded_price(row) is not None:
        op = _to_float(row.get("Open"))
        if open_print and op and op > 0:
            return op, "barchart_open"
        return _traded_price(row), "barchart_last"
    if qty < 0:
        bid, _ = _bid_ask(row)
        return bid, "barchart_side"
    return None, JUNK_ENTRY_REFUSAL


def _cost_knobs(cfg: dict) -> tuple[float, float]:
    """``(commission_per_contract, slippage_frac_of_spread)`` — the transaction-cost
    model (robustness review B1). BOTH DEFAULT TO 0, so an unconfigured run and
    every number recorded before 2026-09-07 are reproduced exactly.

    `commission_per_contract` is charged per LEG per CONTRACT at entry and again at
    exit. `slippage_frac_of_spread` is the fraction of the QUOTED spread given up
    per leg on each side, in the adverse direction — 0.5 fills at the touch
    (bid when closing a long, ask when opening one), 0.25 splits mid and touch.
    """
    return (_to_float(cfg.get("commission_per_contract")) or 0.0,
            _to_float(cfg.get("slippage_frac_of_spread")) or 0.0)


_MECH_LABELERS: dict[str, object] = {}
_MECH_STALE_WARNED: set[str] = set()


def _mech_labeler(csv_path: str):
    """Cached MechLabeler per CSV path. Returns None if the file is missing —
    a missing SPY/VIX table disables the regime override rather than failing
    the run, since every pre-override result stays reproducible without it."""
    if csv_path not in _MECH_LABELERS:
        from pathlib import Path
        p = Path(csv_path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parents[2] / p
        if not p.exists():
            log.warning("regime_exit: SPY/VIX table not found at %s — "
                        "regime exit overrides DISABLED for this run", p)
            _MECH_LABELERS[csv_path] = None
        else:
            from lib.mech_regime import MechLabeler
            _MECH_LABELERS[csv_path] = MechLabeler.from_csv(p)
    return _MECH_LABELERS[csv_path]


def _regime_override(sim_cfg: dict, signal_date) -> tuple[str, dict] | None:
    """`(cell_name, exit-rule overrides)` for the mechanical regime cell of
    `signal_date`, or None when no override applies.

    The cell name is returned alongside the overrides so the result row can
    record WHICH basis it was simulated on (see `_exit_basis`) — a row that
    only carries numbers is indistinguishable from a PROD-basis row.

    DEBIT ONLY, by the addendum-4 spec: credit PROD has no time exit and was
    not part of the study, so credits are never regime-switched here.
    """
    cfg = sim_cfg.get("regime_exit")
    if not isinstance(cfg, dict) or not cfg.get("enabled") or not signal_date:
        return None
    cells = cfg.get("cells")
    if not isinstance(cells, dict) or not cells:
        return None
    labeler = _mech_labeler(cfg.get("spy_vix_csv", ""))
    if labeler is None:
        return None

    d = str(signal_date)[:10]
    last = labeler.last_date
    if last and d > last and d not in _MECH_STALE_WARNED:
        _MECH_STALE_WARNED.add(d)
        log.warning("regime_exit: signal date %s is past the SPY/VIX table end "
                    "(%s) — labelling as-of %s. Refresh with "
                    "`make mech-regime`", d, last, last)
    cell = labeler.cell(d)
    if cell is None:
        return None
    override = cells.get(cell)
    return (cell, override) if isinstance(override, dict) else None


# ─── Pricing sources: real quotes only ─────────────────────────────────────────

#: Every source a leg may be priced from. Both are REAL prices: `barchart` is the
#: contract's own Barchart history, `reappearance` a later flow print of the
#: same contract. Black-Scholes (`bs`) was the third until 2026-09-23, when the
#: operator abolished model pricing from the backtest: no price, delta or IV
#: may be model-generated. A leg with no real price is now refused at entry and
#: carried at its last real mark on a path day (tagged `barchart_stale` once
#: that mark is older than `max_price_carry_days`).
PRICING_SOURCES = frozenset({"barchart", "reappearance"})
DEFAULT_EXIT_SOURCES = ("barchart", "reappearance")

#: Config keys that existed only to feed the Black-Scholes pricer. Listing one
#: is refused, not ignored: a config that still names them was written for an
#: engine that no longer exists.
_ABOLISHED_SIM_KEYS = ("risk_free_rate", "uniform_bs_min_legs")


def validate_pricing_config(sim_cfg: dict) -> None:
    """Raise ``ValueError`` when ``sim_cfg`` asks for a model price.

    Refuses `bs` (or any unknown name) in `entry_sources` / `exit_sources`, and
    the abolished BS-only keys. Called by both CLIs before any fetch and by
    `_simulate` itself, so no caller can reach a model price by config.
    """
    for field in ("entry_sources", "exit_sources"):
        sources = sim_cfg.get(field)
        if sources is None:
            continue
        bad = [s for s in sources if s not in PRICING_SOURCES]
        if bad:
            raise ValueError(
                f"simulation.{field} lists {bad}: only real-price sources "
                f"{sorted(PRICING_SOURCES)} are allowed. Black-Scholes ('bs') was "
                f"abolished from the backtest on 2026-09-23 (no model prices, "
                f"deltas or IVs); see docs/backtest-reference.md.")
    stale = [k for k in _ABOLISHED_SIM_KEYS if k in sim_cfg]
    if stale:
        raise ValueError(
            f"simulation config sets {stale}: these fed the Black-Scholes pricer, "
            f"abolished 2026-09-23. Remove them.")


# ─── Entry refusals: positions that are NOT PRICEABLE ─────────────────────────
# Each refusal leaves `{}` as the result and fills the caller's `refusal` dict,
# so `core.py` tallies it under its own name and `proxy.py` writes it into the
# row's `skip_reason`. Checked in this order; the first that fires is recorded.

#: `skip_reason` / refusal code for a leg with no real price on the entry day.
NO_REAL_ENTRY_PRICE = "no_real_entry_price"

#: `skip_reason` / refusal code for a debit structure whose entry priced negative.
DEBIT_CREDIT_REFUSAL = "debit_priced_to_credit"

#: `skip_reason` / refusal code for a credit structure whose entry priced positive.
CREDIT_DEBIT_REFUSAL = "credit_priced_to_debit"

#: `skip_reason` / refusal code for an entry whose same-expiry legs are priced
#: against strike order (a put above a higher-strike put, a call above a
#: lower-strike call).
NON_MONOTONIC_REFUSAL = "non_monotonic_entry_quote"

#: Every refusal code `_simulate` can record, in check order.
ENTRY_REFUSALS = (NO_REAL_ENTRY_PRICE, JUNK_ENTRY_REFUSAL, DEBIT_CREDIT_REFUSAL,
                  CREDIT_DEBIT_REFUSAL, NON_MONOTONIC_REFUSAL)


def _refuse_debit_priced_to_credit(structure: str, entry_net: float) -> bool:
    """True when this position is NOT PRICEABLE: a structure whose name fixes it
    as a DEBIT priced to a net CREDIT at entry (2026-09-19).

    You pay to open a bull call spread, a bear put spread or a long option. A
    negative entry net on one of them is never a cheap fill — it is a leg priced
    off a quote that does not exist, and every number downstream inherits it: the
    credit sizing profile, `_exit_basis`'s CREDIT label, and a realized P&L
    computed against a premium that was never received. The gate runs BEFORE
    `_effective_sim_cfg`, so no such row can reach the credit exit profile or be
    labelled CREDIT.

    The structure set is `classify.DEBIT_STRUCTURES`, which derives from
    `lib/structure_names.canonical_debit_spreads()` — the classifier's own
    vocabulary, not a list written here. The mirror is
    `_refuse_credit_priced_to_debit`.
    """
    return entry_net < 0 and structure in DEBIT_STRUCTURES


def _refuse_credit_priced_to_debit(structure: str, entry_net: float) -> bool:
    """True when a structure whose name fixes it as a CREDIT priced to a net
    DEBIT at entry (2026-09-23). The mirror of `_refuse_debit_priced_to_credit`.

    You are paid to open a bull put spread or a bear call spread. A positive
    entry net on one means the leg you sell is quoted BELOW the leg you buy
    further out of the money. That is a bad quote, not a cheap trade.

    It is also not conservative. Until 2026-09-23 this case was let through on
    the claim that sizing it "on premium paid" was the cautious side. It is the
    opposite: `_size_contracts` sizes a debit on the premium, and a mispriced
    credit's premium is a tiny number unrelated to its risk. TLT 2025-04-04,
    bull_put_spread 90/85: the 85P priced off a stale Open print of 1.61 while
    that day's quote was 0.68/0.81. The entry came out as a +0.35 DEBIT, the
    sizer divided the risk budget by $35 and bought 38 contracts. The true risk
    was the $500 width per contract, about 38 × $500. See
    research/next-steps.md §2.11.

    The structure set is `classify.CREDIT_STRUCTURES`, which derives from
    `lib/structure_names.canonical_credit_spreads()` plus the two naked shorts.
    """
    return entry_net > 0 and structure in CREDIT_STRUCTURES


def _monotonicity_violation(legs: list, prices: list, tags: list) -> str | None:
    """Detail string when two same-expiry, same-type legs are priced against
    strike order at entry; None when every pair is ordered (2026-09-23).

    A put's value never falls as its strike rises, and a call's never rises. A
    lower-strike put priced ABOVE a higher-strike put (or the call mirror) is a
    quote no market can hold, so the entry built on it is refused as a bad
    quote. Equal prices pass (both legs at 0 is common far out of the money).

    A leg filled at the touch because its quote was one-sided (`barchart_side`)
    is skipped: that price is the side it trades on, not the contract's value,
    and a sold leg at a 0 bid beside a bought leg at its ask is a real market.
    """
    groups: dict[tuple, list] = {}
    for leg, p, tag in zip(legs, prices, tags):
        if tag and tag.startswith("barchart_side"):
            continue
        groups.setdefault((leg.expiration, leg.opt_type), []).append((leg.strike, p))
    for (exp, opt_type), pts in groups.items():
        pts.sort()
        for (k_lo, p_lo), (k_hi, p_hi) in zip(pts, pts[1:]):
            if k_lo == k_hi:
                continue
            bad = p_lo > p_hi + 1e-9 if opt_type == "Put" else p_hi > p_lo + 1e-9
            if bad:
                cp = "P" if opt_type == "Put" else "C"
                return (f"{exp.isoformat()} {k_lo:g}{cp}@{p_lo:g} vs "
                        f"{k_hi:g}{cp}@{p_hi:g}: priced against strike order")
    return None


_BEAR_DEBIT_STRUCTURES = ("bear_put_spread", "long_put")


def _structure_override(sim_cfg: dict, entry_net: float, structure: str) -> dict | None:
    """Exit-rule overrides keyed on the position's STRUCTURE, or None.

    Only one cell exists — `bear_debit` (bear_put_spread / long_put on the debit
    side) — and the narrowness IS the finding, not an implementation shortcut:
    the same `be_after: 0.50` applied to the NON-bear debit book measured
    +0.234 → +0.209, a LOSS of 0.026 (bear_arm study, 2026-08-11). Widening this
    to "all debits" destroys value. Credits get nothing: the credit side showed
    no reproducible change and its only bear structure, bear_call_spread, is
    structure-vetoed at intake with 0 emissions.
    """
    if entry_net < 0:
        return None
    cfg = sim_cfg.get("structure_exit")
    if not isinstance(cfg, dict) or not cfg.get("enabled"):
        return None
    cells = cfg.get("cells")
    if not isinstance(cells, dict):
        return None
    if structure not in _BEAR_DEBIT_STRUCTURES:
        return None
    override = cells.get("bear_debit")
    return override if isinstance(override, dict) else None


def _exit_basis(sim_cfg: dict, entry_net: float, signal_date=None,
                structure: str = "") -> str:
    """Which exit profile governed this simulation — written to every result row.

    Vocabulary: {PROD, CREDIT, BEAR_DEBIT, <regime cell>} — plus EMPTY, which
    means the row predates this column, i.e. it was simulated before the
    mech-regime override shipped (2026-07-22) and is PROD-basis by definition.
    Every row a current run writes carries a value, so a full re-run produces a
    complete single-basis book that can be read on its own and older rows
    ignored.

    ⚠️ ERA-SCOPED TRUST. This function has always been correct; what broke was
    the trip to the sheet. On the **v3 and earlier** tabs the header was never
    given the column name, so the value landed in a nameless trailing field and
    the labels came out scrambled (measured 2026-08-14: 65 of 67 post-trail rows
    blank; 55 `BEAR_HE` labels on rows predating the column; 7 of 13 `CREDIT`
    tags on positive-entry-price rows, which the branch below cannot produce).
    Those exports are frozen — the column is permanently unreadable there.

    On **v4 it is clean**, because the version bump recreated the tabs empty and
    `append_rows` wrote a full header. Re-measured 2026-09-02 on the 2026-08-27
    export: the header matches `core._KEY_ORDER` 47/47, all 485 rows carry a
    basis (PROD 260 / CREDIT 113 / BEAR_DEBIT 95 / BEAR_HE 17), no `CREDIT` row
    has a positive entry price, and the `BEAR_HE` and `BEAR_DEBIT` rows do carry
    the `trailing_stop` / `be_stop` exits that define those cells.
    `scripts/align_tab_headers.py` now covers both backtest tabs against their
    writers' key orders, so a future header gap is caught rather than discovered.
    Contract note and the per-era caveats: docs/backtest-reference.md
    `exit_basis`; history: research/archive/15 §2026-08-14.

    Reported in merge-precedence order, so the label always names the profile
    that actually governed the exit:

      CREDIT      — credit block (never structure- or regime-switched)
      <cell>      — a mech-regime cell fired. Named ahead of BEAR_DEBIT because
                    regime merges LAST; on BEAR_HE it nulls `be_after`, so the
                    cell genuinely is the governing profile.
      BEAR_DEBIT  — structure_exit's bear_debit cell armed the `be_after`
                    breakeven stop and no regime cell overrode it (2026-08-11).
      PROD        — base config only.

    BEAR_DEBIT exists so that `exit_basis == "PROD"` keeps meaning "base config
    only" for every row. Without it a bear debit that ran the breakeven stop would
    report PROD and be pooled with rows that did not — the exact ambiguity this
    column was added to prevent.
    """
    if entry_net < 0:
        return "CREDIT"
    hit = _regime_override(sim_cfg, signal_date)
    if hit:
        return hit[0]
    if _structure_override(sim_cfg, entry_net, structure):
        return "BEAR_DEBIT"
    return "PROD"


def _effective_sim_cfg(sim_cfg: dict, entry_net: float, signal_date=None,
                       structure: str = "") -> dict:
    """Debit (entry_net >= 0) simulates on the base `sim_cfg` unchanged. Credit
    (entry_net < 0) merges `sim_cfg['credit']` over the base — presence-based, so
    a key the credit block doesn't mention keeps its debit value, while an
    explicit YAML `null` in the credit block overrides to None and disables that
    rule (e.g. `time_exit_dte_fraction: null` turns off the time exit for credits
    without touching the debit config). No-op when `credit` isn't a dict (absent
    or misconfigured) — credit positions then just run the debit profile.

    Debits additionally take two overrides, merged with the SAME presence-based
    semantics, in this order:

        base → structure (simulation.structure_exit) → regime (simulation.regime_exit)

    Regime is merged LAST deliberately. It is how the BEAR_HE cell suppresses
    `be_after` with an explicit `null`: on a BEAR_HE date the 0.50/0.50 trail
    already dominates the peak-triggered breakeven stop (the trail's floor, peak−0.50, is
    ≥ 0 exactly when the breakeven stop arms at peak ≥ 0.50, and the trail is checked
    first), so stacking them is a measured no-op and each rule stays inside the
    envelope it was measured in. See the A3 confirmation in
    `backtests/study_output/bear_arm-latest.txt` ("BE @.50 + trail .50 trig .50").

    Credits are never structure- or regime-switched."""
    if entry_net >= 0:
        eff = sim_cfg
        struct_hit = _structure_override(sim_cfg, entry_net, structure)
        if struct_hit:
            eff = {**eff, **struct_hit}
        hit = _regime_override(sim_cfg, signal_date)
        if hit:
            eff = {**eff, **hit[1]}
        return eff
    credit = sim_cfg.get("credit")
    if not isinstance(credit, dict):
        return sim_cfg
    return {**sim_cfg, **credit}


def _size_contracts(entry_net: float, legs: list, sim_cfg: dict) -> int:
    """Fixed-fractional position sizing: size so that hitting the worst case costs
    at most risk_per_trade_pct × portfolio_value. Minimum 1 contract; a separate
    dollar stop in _summarize_path enforces the budget cap when 1 contract already
    exceeds it. Falls back to sim_cfg['contracts'] when portfolio_value is unset.

    Debit (entry_net > 0): sized on premium paid, per the existing formula.
    Credit (entry_net < 0): sized on STRUCTURAL max loss (_max_loss_per_unit), not
    the credit received — a small credit on a wide/naked structure understates the
    true worst case (the original oversizing bug). When the max loss can't be
    bounded (naked short call, multi-expiration credit), falls back to 1 contract
    and logs a warning; the position still appears in results with contracts=1,
    the portfolio dollar_stop still caps the realized loss, and the blank
    `max_loss_per_contract` on the result flags it as unsized."""
    portfolio = sim_cfg.get("portfolio_value")
    risk_pct = sim_cfg.get("risk_per_trade_pct")

    if entry_net < 0:
        if portfolio and risk_pct:
            mlpu = _max_loss_per_unit(legs, entry_net)
            if mlpu is not None and mlpu > 0:
                dollar_risk = portfolio * risk_pct
                return max(1, math.floor(dollar_risk / (mlpu * 100)))
            log.warning(
                "Credit position has unbounded/uncomputable max loss — sizing to "
                "1 contract:\n%s", format_legs(legs))
            return 1
        return sim_cfg.get("contracts", 1)

    # Debit: existing premium × stop formula, verbatim.
    stop = sim_cfg.get("stop_loss", 1.0)
    if portfolio and risk_pct and stop > 0 and entry_net > 0:
        dollar_risk = portfolio * risk_pct
        loss_per_contract = entry_net * 100 * stop
        return max(1, math.floor(dollar_risk / loss_per_contract))
    return sim_cfg.get("contracts", 1)


def _max_loss_abs(sim_cfg: dict) -> float | None:
    """Dollar loss cap per trade from portfolio config. None when not configured."""
    portfolio = sim_cfg.get("portfolio_value")
    risk_pct = sim_cfg.get("risk_per_trade_pct")
    if portfolio and risk_pct:
        return portfolio * risk_pct
    return None


# ─── Path summarizer ───────────────────────────────────────────────────────────

def _summarize_path(grid_marks, entry_net, profit_target, stop_loss,
                    contracts, cap_reached_expiry, max_loss_abs=None,
                    time_exit_day=None, trailing_stop_trigger=None,
                    trailing_stop_pct=None, loss_days_exit=None,
                    be_after=None, grid_fillable=None,
                    data_end_idx=None, grid_real=None, path_data_end=None) -> dict:
    """Turn a day-by-day signed-value grid into the path string, realized exit, and MFE/MAE.

    Day indices (`days_held`, `mfe_day`, `mae_day`) are 1-based positions in the
    grid, which starts the weekday AFTER the signal date — SIGNAL-relative, the
    same convention as `time_exit_day` and `path_cap_days` and the one the frozen
    research harness rebuilds and asserts against.

    A grid day the position did not exist on yet is present but UNPRICED: the grid
    build stamps every weekday before the entry date with `p=None` and the source
    tag `pre_entry` (robustness review B2). Unpriced days are skipped by every scan
    below, so no P&L, MFE/MAE or exit can be booked before the fill; they hold the
    grid's length and index origin fixed while contributing nothing. They also do
    not reach `pct_real_days` / `pct_stale_days`, which are computed over PRICED
    days only, so a late fill shrinks those denominators rather than diluting them.

    Each grid mark holds the position's signed net value V = Σ qty·price. P&L is
    the single unified formula `(V − entry_net) / abs(entry_net)`, correct for both
    debit (entry_net > 0) and credit (entry_net < 0) positions with no flag.

    Everything here is GROSS of transaction costs: the exit rules are defined on
    marks, so commission/slippage are charged once in `_simulate` against the
    realized figures rather than shifting the thresholds the path is scanned with.

    Realized exit = the FIRST exit condition crossed (frozen at that day's mark).
    MFE/MAE are measured over the WHOLE path so exit params can be tuned in analysis.

    Exit priority:
      1. profit_target  — activates trailing from peak (floor guarantee); exits only if
                          no trailing_stop_trigger/pct is configured (disabled when None)
      2. trailing_stop  — trails from peak once trailing_stop_trigger is reached OR
                          profit_target activates it (whichever comes first)
      3. dollar_stop    — hard per-trade $ loss cap from portfolio sizing
      4. be_stop        — peak-triggered breakeven stop: once peak P&L reaches be_after, the
                          stop tightens from -stop_loss to 0 (disabled when None)
      5. stop_loss      — hard % loss floor
      6. loss_days_exit — N consecutive trading days in loss
      7. time_exit_day  — calendar days from entry; graceful time-based close

    THE TRIGGER AND THE FILL ARE TWO DIFFERENT DAYS (2026-09-19). The rules above
    scan the MARKED path and fire on the first day a condition is crossed; that
    day is unchanged by anything here. But a position cannot be traded out into a
    market with no bid, and `_zero_bid_mark` values such a day at `ask/2`, so
    booking the exit there credits a long leg for a price nobody was bidding.
    When `grid_fillable` says the trigger day has no two-sided quote, the FILL is
    carried to the next priced day that does, and `days_held` becomes that day —
    the position really was still open. `exit_fill` records which happened:

      same_day        the trigger day was fillable (the overwhelming majority)
      deferred_<n>    carried n grid days to the next two-sided quote
      no_two_sided    the trigger fired and no fillable day ever arrived, so the
                      fill stays on the trigger day's mark, as it was before this
                      rule. The row is flagged rather than silently repriced.

    `grid_fillable=None` disables the whole rule and reproduces the pre-2026-09-19
    behaviour exactly, which is what the frozen research harness and every stored
    row predate.

    NO RULE MAY FIRE PAST THE LAST REAL QUOTE (2026-09-23). `data_end_idx` is the
    1-based index of the last grid day a real quote covers (see `_leg_data_end`).
    Every day after it is a carried mark on a session that may not have happened,
    so the exit scan stops there and the fill deferral above cannot reach past it.
    A position still open at that point is marked THERE — `days_held` is that day,
    the P&L is that day's — and labelled `open_at_data_end`. It is never dropped:
    the row exists, honestly, and `path_data_end` says where the data stopped.
    Two columns report it:

      path_status     complete          the exit fired on a day every leg quoted
                      carried           it fired on a day at least one leg's mark
                                        was carried into (an interior gap; the
                                        one case this cannot cleanly prevent)
                      open_at_data_end  the data ran out before any exit fired
                      ""                unknown — the caller supplied neither
                                        input, which is every stored row
      path_data_end   ISO date of the last real quote the path could use

    `data_end_idx=None` and `grid_real=None` together disable the rule and leave
    both columns blank, which reproduces the pre-2026-09-23 behaviour exactly.
    What does NOT change: the marked path, MFE/MAE and `pnl_at_cap_pct` are still
    measured over the WHOLE grid, so a play that exits before the data ends is
    byte-identical to what this engine produced yesterday.

    The be_stop slot is LOAD-BEARING: it sits between dollar_stop and stop_loss
    to mirror the frozen research harness (scripts/backtest_study/lib/harness.py
    `replay`, pt → trail → underlying → dollar → be_stop → sl → tef). Every
    recorded be_after conclusion was measured at that precedence; moving it
    changes the numbers.
    """
    denom = abs(entry_net)

    def pnl_of(v):
        return (v - entry_net) / denom

    prices, sources, pnl_dollars = [], [], []
    for (_, _, p, src) in grid_marks:
        prices.append("" if p is None else f"{p:.4f}")
        # `src` survives an unpriced day so `pre_entry` reaches daily_source_csv;
        # an unpriceable day still carries the empty token it always did.
        sources.append(src or "")
        # Per-SINGLE-CONTRACT dollar P&L: (V − entry_net)·100, deliberately NOT
        # scaled by `contracts` (unlike realized_pnl_abs). Same day grid + blank
        # tokens as daily_price_csv.
        pnl_dollars.append("" if p is None else f"{(p - entry_net) * 100:.2f}")
    out = {
        "daily_price_csv": ",".join(prices),
        "daily_source_csv": ",".join(sources),
        "daily_pnl_csv": ",".join(pnl_dollars),
    }

    priced = [(dt, d, p, src) for (dt, d, p, src) in grid_marks if p is not None]
    if not priced:
        out.update({"realized_pnl_pct": "", "realized_pnl_abs": "", "days_held": "",
                    "exit_reason": "no_data", "mfe_pct": "", "mfe_abs": "", "mfe_day": "",
                    "mae_pct": "", "mae_abs": "", "mae_day": "", "pnl_at_cap_pct": "",
                    "pct_real_days": "", "pct_stale_days": "", "exit_fill": "",
                    "path_status": "", "path_data_end": ""})
        return out

    mfe, mae, mfe_day, mae_day = -1e18, 1e18, None, None
    exit_reason = realized_p = None
    days_held = last_priced_idx = None
    peak_pnl = -1e18
    trailing_active = False
    loss_streak = 0
    for grid_idx, (dt, d, p, src) in enumerate(grid_marks, start=1):
        if p is None:
            continue
        last_priced_idx = grid_idx
        pl = pnl_of(p)
        if pl > mfe:
            mfe, mfe_day = pl, grid_idx
        if pl < mae:
            mae, mae_day = pl, grid_idx
        if exit_reason is None and (data_end_idx is None or grid_idx <= data_end_idx):
            peak_pnl = max(peak_pnl, pl)
            if trailing_stop_trigger is not None and peak_pnl >= trailing_stop_trigger:
                trailing_active = True
            loss_streak = loss_streak + 1 if pl < 0 else 0

            if profit_target is not None and pl >= profit_target:
                exit_reason, realized_p, days_held = "profit_target", p, grid_idx
            elif (trailing_active and trailing_stop_pct is not None
                  and pl <= peak_pnl - trailing_stop_pct):
                exit_reason, realized_p, days_held = "trailing_stop", p, grid_idx
            elif max_loss_abs is not None and pl * denom * 100 * contracts <= -max_loss_abs:
                exit_reason, realized_p, days_held = "dollar_stop", p, grid_idx
            elif be_after is not None and peak_pnl >= be_after and pl <= 0:
                exit_reason, realized_p, days_held = "be_stop", p, grid_idx
            elif stop_loss is not None and pl <= -stop_loss:
                exit_reason, realized_p, days_held = "stop_loss", p, grid_idx
            elif loss_days_exit is not None and loss_streak >= loss_days_exit:
                exit_reason, realized_p, days_held = "loss_days", p, grid_idx
            elif time_exit_day is not None and d >= time_exit_day:
                exit_reason, realized_p, days_held = "time_exit", p, grid_idx

    # Defer the FILL off an unfillable trigger day. Done before the cap_open /
    # expired fallback below, which has no later day to move to by construction.
    exit_fill = "same_day"
    if (exit_reason is not None and days_held is not None
            and grid_fillable is not None and not grid_fillable[days_held - 1]):
        # The deferral stops at the data end for the same reason the scan does:
        # a fill on a carried mark is a fill on a session that may not exist.
        fill_limit = len(grid_marks) if data_end_idx is None else data_end_idx
        nxt = next((i for i in range(days_held, fill_limit)
                    if grid_marks[i][2] is not None and grid_fillable[i]), None)
        if nxt is None:
            exit_fill = "no_two_sided"
        else:
            exit_fill = f"deferred_{nxt + 1 - days_held}"
            realized_p, days_held = grid_marks[nxt][2], nxt + 1

    truncated = False
    if exit_reason is None:
        idx = last_priced_idx
        if data_end_idx is not None and data_end_idx < last_priced_idx:
            # Still open when the data stopped. Mark it at the last priced day the
            # data covers, not at the cap. When the data ended before the fill,
            # the entry day is the only mark that is not fabricated.
            within = [g for g, (_, _, p, _) in enumerate(grid_marks, start=1)
                      if p is not None and g <= data_end_idx]
            idx = within[-1] if within else next(
                g for g, (_, _, p, _) in enumerate(grid_marks, start=1) if p is not None)
            truncated = True
        realized_p, days_held = grid_marks[idx - 1][2], idx
        # `expired` would claim the path reached expiry; a truncated one did not.
        exit_reason = "expired" if (cap_reached_expiry and not truncated) else "cap_open"

    if data_end_idx is None and grid_real is None:
        path_status = ""                       # unknown — never backfilled
    elif truncated:
        path_status = "open_at_data_end"
    elif grid_real is not None and not grid_real[days_held - 1]:
        path_status = "carried"
    else:
        path_status = "complete"

    out["exit_fill"] = exit_fill
    out["path_status"] = path_status
    out["path_data_end"] = path_data_end.isoformat() if path_data_end else ""
    realized_pnl = pnl_of(realized_p)
    cap_p = priced[-1][2]
    # LEG-days, not days (robustness review B3/B7). The old count called a day
    # "real" when ANY leg was real, so a vertical with one modelled leg scored the
    # same 1.00 as one priced entirely from Barchart. Each priced day contributes
    # one unit per leg; `pct_stale_days` is the share of those leg-days whose mark
    # was carried forward past `max_price_carry_days`, which is the honesty check
    # for a contract that stopped being quoted — those days still count as real
    # (they ARE quotes, just frozen ones), so `pct_real_days` keeps its
    # real-vs-model meaning across eras.
    leg_days = real_leg_days = stale_leg_days = 0
    for (_, _, _, s) in priced:
        tags = s.split("+") if s else []
        leg_days += len(tags)
        real_leg_days += sum(1 for t in tags if t != "bs")
        stale_leg_days += sum(1 for t in tags if t == "barchart_stale")

    out.update({
        "realized_pnl_pct": round(realized_pnl, 4),
        "realized_pnl_abs": round(realized_pnl * denom * 100 * contracts, 2),
        "days_held": days_held,
        "exit_reason": exit_reason,
        "mfe_pct": round(mfe, 4),
        "mfe_abs": round(mfe * denom * 100 * contracts, 2),
        "mfe_day": mfe_day,
        "mae_pct": round(mae, 4),
        "mae_abs": round(mae * denom * 100 * contracts, 2),
        "mae_day": mae_day,
        "pnl_at_cap_pct": round(pnl_of(cap_p), 4),
        "pct_real_days": round(real_leg_days / leg_days, 4) if leg_days else "",
        "pct_stale_days": round(stale_leg_days / leg_days, 4) if leg_days else "",
    })
    return out


# ─── Transaction costs ─────────────────────────────────────────────────────────

def _apply_costs(result: dict, cfg: dict, legs: list, contracts: int,
                 entry_net: float, entry_spread_units, grid_spread_units,
                 entry_junk: bool = False, grid_spread_junk=None) -> None:
    """Charge commission + slippage on the round trip and write `cost_total` /
    `cost_basis` onto ``result``, netting the realized P&L columns (B1).

    ``entry_spread_units`` / the exit day's entry in ``grid_spread_units`` are
    ``Σ |qty|·spread`` in option points for that side, or None when any leg had no
    two-sided quote that day. A missing spread charges NO slippage on that side and
    says so in `cost_basis` — never a guessed one.

        commission = commission_per_contract · Σ|qty| · contracts · 2 sides
        slippage   = slippage_frac_of_spread · Σ|qty|·spread · 100 · contracts,
                     once per side, always adverse

    A JUNK-quote leg (`_is_junk_quote`, 2026-09-24) charges commission only:
    its spread is left out of that side's units, the other legs on the side
    still pay slippage, and ``entry_junk`` / ``grid_spread_junk[day]`` put the
    side into `no_spread_<side>` — the same label a missing quote earns, since
    in both cases the side was not charged its full quoted spread.

    What is netted: `realized_pnl_abs`, `realized_pnl_pct` and (downstream, since it
    is derived from `realized_pnl_abs`) `pnl_on_risk_pct`. What stays GROSS:
    `mfe_*`, `mae_*`, `pnl_at_cap_pct`, `daily_pnl_csv` — path statistics used to
    tune exits, which is a different question from what the round trip cost.
    """
    commission_per_contract, slip_frac = _cost_knobs(cfg)
    if not commission_per_contract and not slip_frac:
        result["cost_total"] = 0.0
        result["cost_basis"] = ""
        return

    units = sum(abs(leg.qty) for leg in legs) * contracts
    cost = commission_per_contract * units * 2

    exit_spread_units, exit_junk = None, False
    days_held = result.get("days_held")
    if isinstance(days_held, int) and 1 <= days_held <= len(grid_spread_units):
        exit_spread_units = grid_spread_units[days_held - 1]
        if grid_spread_junk is not None:
            exit_junk = grid_spread_junk[days_held - 1]

    if slip_frac:
        for side_units in (entry_spread_units, exit_spread_units):
            if side_units is not None:
                cost += slip_frac * side_units * 100 * contracts
        sides = (("entry", entry_spread_units, entry_junk),
                 ("exit", exit_spread_units, exit_junk))
        missing = [name for name, v, junk in sides if v is None or junk]
        basis = "full" if not missing else "no_spread_" + "_".join(missing)
    else:
        basis = "commission_only"

    result["cost_total"] = round(cost, 2)
    result["cost_basis"] = basis

    realized_abs, realized_pct = result.get("realized_pnl_abs"), result.get("realized_pnl_pct")
    if isinstance(realized_abs, (int, float)) and isinstance(realized_pct, (int, float)):
        result["realized_pnl_abs"] = round(realized_abs - cost, 2)
        position_dollars = abs(entry_net) * 100 * contracts
        if position_dollars:
            result["realized_pnl_pct"] = round(realized_pct - cost / position_dollars, 4)


# ─── Entry greeks and underlying: real values only ─────────────────────────────

#: Legs whose `Price~` disagree by more than this fraction get a warning: they
#: cannot all be reading the same underlying on the same day.
_UNDERLYING_DISAGREE_FRAC = 0.05


def _real_greek(row, name: str) -> float | None:
    """A greek (or `IV`) off one history row, or None when it is not real.

    Barchart writes SENTINEL sessions whose IV, Delta, Gamma, Theta, Vega, Rho
    and Theo are all literally 0 while the mark is real. A real option never
    quotes zero implied vol, so a missing-or-zero IV marks the row's whole greek
    block as absent — the rule `backtest_study/lib/greeks.leg_greek` uses. A
    missing greek is None, never 0.0.
    """
    if not row:
        return None
    iv = _to_float(row.get("IV"))
    if not iv:
        return None
    return iv if name == "IV" else _to_float(row.get(name))


def _entry_underlying(ticker: str, leg_prices: list, signal_date=None) -> float | None:
    """The entry-day underlying: the MEDIAN of the legs' own `Price~` that day.

    Until 2026-09-23 this was the ANCHOR leg's `Price~` alone, so one history
    file holding another contract's data (META_20270115_630.00P) set the whole
    position's underlying. A median needs a majority of legs to be wrong
    before it moves. Warns when the legs disagree by more than 5% of the
    median: at least one leg's file is then not reading this ticker.

    NOT the underlying OHLC cache (`backtests/underlying_ohlc_cache/`). That
    cache is split-ADJUSTED; option-history `Price~` is as-traded. On a split
    ticker (NVDA, NFLX, MSTR, SMCI 10:1; XLE 2:1; CVNA, CRWD, NOW, GE, AVGO)
    the two differ by an exact multiple, and reading the OHLC close here would
    put every pre-split row on the wrong basis.
    """
    if not leg_prices:
        return None
    srt = sorted(leg_prices)
    n = len(srt)
    median = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    spread = (srt[-1] - srt[0]) / median if median else 0.0
    if spread > _UNDERLYING_DISAGREE_FRAC:
        log.warning("entry_underlying: %s %s legs disagree on Price~ (%s) by "
                    "%.0f%% — a leg's history file may hold another contract",
                    signal_date, ticker, ", ".join(f"{v:g}" for v in leg_prices),
                    spread * 100)
    return median


# ─── Iron condor strike resolution ──────────────────────────────────────────────

def _iron_condor_strikes(
    strikes: list, K_sp_anchor: float, S_entry: float, spread_pct: float
) -> tuple[float, float, float, float]:
    """
    Resolve all four IC strikes as (K_lp, K_sp, K_sc, K_lc) — ascending.
      K_lp = long put  (wing)
      K_sp = short put (income leg)
      K_sc = short call (income leg)
      K_lc = long call  (wing)
    """
    if len(strikes) >= 4:
        s = sorted(strikes)
        return s[0], s[1], s[2], s[3]
    if len(strikes) == 2:
        K_sp, K_sc = sorted(strikes)
        return K_sp * (1 - spread_pct), K_sp, K_sc, K_sc * (1 + spread_pct)
    K_sp = K_sp_anchor
    d = abs(S_entry - K_sp) / S_entry if S_entry > 0 else spread_pct
    K_sc = S_entry * (1 + d)
    return K_sp * (1 - spread_pct), K_sp, K_sc, K_sc * (1 + spread_pct)


# ─── Generic leg-list simulation ─────────────────────────────────────────────────

def _simulate(candidate, legs, entry_row, contract_index, barchart_series, sim_cfg,
              structure="", anchor_idx=0,
              barchart_details=None, refusal=None):
    """Simulate one position expressed as a list of signed Legs.

    For each leg, pricing follows the source priority from sim_cfg['exit_sources']:
      barchart → reappearance. Both are REAL prices; there is no model tier
    (Black-Scholes was abolished 2026-09-23, see `PRICING_SOURCES`). A leg with
    no real price at entry refuses the position (`no_real_entry_price`); on a
    path day the last real mark is carried forward and tagged stale.

    Steps:
      1. price each leg at entry
      2. price each leg on each trading day
      3. multiply by qty (sign)
      4. multiply by contracts
      5. daily_price_csv + realized exit + MFE/MAE

    Returns a result dict, or {} if the position cannot be priced.
    barchart_series / contract_index map contract_key -> sorted [(date, price)].
    barchart_details maps contract_key -> {date: full_row} (incl. 'Open'); when
    provided and sim_cfg['entry_timing'] is "next_open", entry legs are priced at
    the entry_row's '_entry_date' (the first trading day after the signal) using
    that day's Open, falling back to that day's EOD mark. When absent, entry is
    the legacy signal-day EOD mark.

    ``refusal`` is an optional dict the caller owns: when the position is refused
    for a REASON worth recording (rather than merely unpriceable), it is filled
    with ``{"reason", "detail"}`` before ``{}`` is returned. Every other skip
    leaves it untouched, so an empty dict means "unpriced" as it always did. Both
    writers pass the Play's own dict, which is how `core.py` tallies the refusal
    and `proxy.py` puts it in the row's `skip_reason`.
    """
    validate_pricing_config(sim_cfg)
    legs = merge_legs(legs)
    if not legs:
        return {}

    # The anchor's IV is REPORTED (`iv_entry_pct`), never used to price: with no
    # model tier there is nothing for it to feed, so a blank IV no longer makes
    # the position unpriceable. DTE still gates, because the time exit needs it.
    iv = _row_iv(entry_row)
    dte_entry = _to_float(entry_row.get("DTE"))
    if not (dte_entry and dte_entry > 0):
        return {}
    dte_entry = int(dte_entry)

    ticker = candidate["ticker"]
    signal_date = candidate["signal_date"]
    exit_sources = sim_cfg.get("exit_sources", list(DEFAULT_EXIT_SOURCES))
    entry_sources = sim_cfg.get("entry_sources", ["barchart"])
    # Quote-staleness bound: a PRICING property of the data, so it is read off the
    # base config and never from the credit/regime/structure exit profiles.
    max_carry_days = sim_cfg.get("max_price_carry_days", _DEFAULT_MAX_CARRY_DAYS)

    def _key(leg):
        return _contract_key(leg.ticker, leg.opt_type, leg.strike, leg.expiration.isoformat())

    def _detail_row(key, day):
        """The Barchart history row for exactly ``day`` (never carried forward), or
        None when this run has no details map / no row that day."""
        return (barchart_details or {}).get(key, {}).get(day)

    def _last_good_mark(key, before, expiration):
        """``(mark, date)`` of the newest barchart snap strictly before ``before``
        whose quote is usable: a non-junk quote (its mid), or a junk quote on a
        day the contract traded (its Latest). None when there is none."""
        for snap_date, mark in reversed(barchart_series.get(key) or []):
            if snap_date >= before or (expiration and snap_date > expiration):
                continue
            row = _detail_row(key, snap_date)
            if not _is_junk_quote(row):
                return mark, snap_date
            traded = _traded_price(row)
            if traded is not None:
                return traded, snap_date
        return None

    def _junk_day_mark(key, leg, row, q_day):
        """The DAILY mark for a leg whose quote on ``q_day`` is junk (2026-09-24).

        ``(price, tag, snap)``, or None when there is no real value at all:

          1. the contract traded on q_day → that day's Latest (`barchart_last`)
          2. else the last good mark (`_last_good_mark`), carried and tagged
             `barchart_stale` whatever its age — a junk day is never a quote —
          3. B5 CEILING: when the junk quote has NO BID, `_zero_bid_mark` (ask/2,
             or 0 when nothing is offered) caps step 2. A bid-less contract is
             worth about nothing on liquidation, so it is never carried at an
             older, higher mark; a junk ask of 4.80 caps nothing on a 0.11
             option, a `0 x 0.05` quote marks it at 0.025. When the ceiling
             binds, or there is no good mark to carry, the mark is the
             ceiling, tagged `barchart` off the day's own quote.

        A wide junk quote WITH a bid and no good mark behind it is unpriceable
        from barchart; the next source is tried.
        """
        traded = _traded_price(row)
        if traded is not None:
            return traded, "barchart_last", q_day
        good = _last_good_mark(key, q_day, leg.expiration)
        ceiling = _zero_bid_mark(row)
        if good is not None and (ceiling is None or good[0] <= ceiling):
            return good[0], "barchart_stale", good[1]
        if ceiling is not None:
            return ceiling, "barchart", q_day
        return None

    def _price_leg(leg, day, d, sources=None, entry_qty=None):
        """``(price, source_tag, quoted_spread, one_sided, snap)``.

        ``snap`` is the session the mark actually came FROM. It equals ``day`` on
        a real quote and is EARLIER on one carried forward; ``None`` when the leg
        could not be priced at all. It is what `path_status` / `path_data_end`
        are built from — see `_leg_data_end` below.

        ``one_sided`` is True when the quote this mark came from had NO BID —
        the market `_zero_bid_mark` / `_entry_side_mark` exist for. Nothing can
        be filled into such a market, so `_summarize_path` uses it to defer an
        exit FILL to the next day that has a two-sided quote (2026-09-19). It is
        a property of the quote, not of the mark: a leg priced by
        `reappearance` has no quote to judge and reports False.

        The spread is the leg's quoted bid/ask width in option points on the day
        the mark came from, or None when that day has no two-sided quote — it is
        what the slippage term is charged against. Barchart marks are tagged
        `barchart_stale` once carried forward past `max_carry_days`.

        ``entry_qty`` is the leg's SIGNED quantity when this call is pricing an
        ENTRY, and None on every daily mark. It switches the one-sided-quote rule
        from the liquidation mark (`_zero_bid_mark`) to the side-aware fill
        (`_entry_side_mark`): a leg being sold into a 0-bid market is filled at
        0, not at half the ask. This branch is the one the HYG 2025-04-09 row
        came through — no bar on the fill day, so the entry fell back to a
        CARRIED snap and was re-marked by the liquidation rule.
        """
        if sources is None:
            sources = exit_sources
        key = _key(leg)
        for src in sources:
            if src == "barchart":
                p, snap = _snap_asof(barchart_series, key, day, leg.expiration)
                if p is None:
                    continue
                # The quote this day is judged by: the day's OWN row when it is
                # junk (it may carry no `_mark` and so be absent from the series,
                # e.g. `bid 0 / ask 0.01 / Latest 0`), else the row the mark came
                # from, exactly as before 2026-09-24.
                row, q_day = _detail_row(key, snap), snap
                if snap != day and day <= leg.expiration:
                    today = _detail_row(key, day)
                    if today is not None and _is_junk_quote(today):
                        row, q_day = today, day
                spread = _leg_spread(row)
                one_sided = _zero_bid_mark(row) is not None
                tag = "barchart"
                if entry_qty is not None:
                    fill = _junk_entry_fill(row, entry_qty, open_print=False)
                    if fill is not None:
                        # A refusal comes back as (None, JUNK_ENTRY_REFUSAL).
                        return fill[0], fill[1], spread, one_sided, q_day
                elif _is_junk_quote(row):
                    marked = _junk_day_mark(key, leg, row, q_day)
                    if marked is None:
                        continue
                    p, tag, snap = marked
                    if tag == "barchart_stale":
                        return p, tag, spread, one_sided, snap
                stale = (max_carry_days is not None and snap is not None
                         and (day - snap).days > max_carry_days)
                return p, ("barchart_stale" if stale else tag), spread, one_sided, snap
            elif src == "reappearance":
                # `_snap_asof` selects exactly what `helpers._price_asof` did —
                # the most recent snap on or before `day`, bounded by expiry — and
                # additionally reports WHICH day it came from.
                p, snap = _snap_asof(contract_index, key, day, leg.expiration)
                if p is not None:
                    return p, "real", None, False, snap
        return None, None, None, False, None

    # Step 1 — entry price for each leg, every leg on the SAME entry day (the
    # anchor's _entry_date: the next trading day under entry_timing "next_open",
    # else the signal day). Under next_open a leg is filled at that day's Open,
    # unless that day's quote is junk (then `_junk_entry_fill`, 2026-09-24),
    # falling back to that day's EOD mark when Open is blank (zero-volume day);
    # without barchart_details (or for a leg with no row on the entry day) pricing
    # carries forward the most recent EOD mark on-or-before the entry day.
    entry_timing = sim_cfg.get("entry_timing", "next_open")
    entry_date = (entry_row.get("_entry_date") or signal_date) if barchart_details \
        else signal_date
    entry_d = (entry_date - signal_date).days
    use_open = entry_timing == "next_open" and entry_date > signal_date

    def _entry_price_leg(leg):
        """``(price, source_tag, quoted_spread)`` for one leg on the entry day."""
        if use_open and "barchart" in entry_sources:
            row = (barchart_details.get(_key(leg)) or {}).get(entry_date)
            if row is not None:
                spread = _leg_spread(row)
                # A JUNK entry-day quote (2026-09-24) is filled by
                # `_junk_entry_fill`, AHEAD of the Open print: a SOLD leg into
                # no bid receives 0 (the 2026-09-22 one-sided rule, which every
                # zero-bid quote now reaches through this test); otherwise the
                # day's trade print when the contract traded; otherwise a sold
                # leg at its bid and a bought leg REFUSED — a junk ask is never
                # a fill. A clean two-sided quote, or a row with no quote data,
                # still fills at the Open print exactly as before. The junk
                # leg's spread is `JUNK_SPREAD`, so it is charged commission
                # only.
                fill = _junk_entry_fill(row, leg.qty, open_print=True)
                if fill is not None:
                    return fill[0], fill[1], spread
                op = _to_float(row.get("Open"))
                if op and op > 0:
                    return op, "barchart_open", spread
                mk = row.get("_mark")
                if mk and mk > 0:
                    return mk, "barchart", spread
        # The entry does not use `one_sided` — `_junk_entry_fill` has already
        # priced the leg on the side it trades, above and in `_price_leg`.
        return _price_leg(leg, entry_date, entry_d, sources=entry_sources,
                          entry_qty=leg.qty)[:3]

    def _leg_greek_row(leg):
        """``(day, row)`` — the history row this leg's entry greeks are read from:
        its own row ON the entry day, else the row its carried entry mark came
        from (the most recent on or before the entry day). ``(None, None)`` when
        the leg has no history row at all (e.g. priced by `reappearance`)."""
        rows = (barchart_details or {}).get(_key(leg)) or {}
        if entry_date in rows:
            return entry_date, rows[entry_date]
        _, snap = _snap_asof(barchart_series, _key(leg), entry_date, leg.expiration)
        if snap is not None and snap in rows:
            return snap, rows[snap]
        return None, None

    def _refuse(reason, detail):
        log.warning("SKIP %-22s %s %s | %s", reason, signal_date, ticker, detail)
        if refusal is not None:
            refusal["reason"] = reason
            refusal["detail"] = detail
        return {}

    def _cp(leg):
        return "C" if leg.opt_type == "Call" else "P"

    entry_prices, entry_tags = [], []
    entry_spread_units, entry_spread_complete, entry_spread_junk = 0.0, True, False
    for leg in legs:
        p, tag, spread = _entry_price_leg(leg)
        if p is None and tag == JUNK_ENTRY_REFUSAL:
            # Bought into a junk quote on a day the contract did not trade:
            # the only price on offer is a junk ask, which is not a fill.
            return _refuse(JUNK_ENTRY_REFUSAL,
                           f"{leg.ticker}:{leg.expiration.isoformat()}:{leg.strike:g}:"
                           f"{_cp(leg)} bought into a junk quote with no trade on "
                           f"or before {entry_date}")
        if p is None:
            # No real price for this leg on the entry day. There is no model
            # tier to fall back to, so the position is not priceable.
            return _refuse(NO_REAL_ENTRY_PRICE,
                           f"{leg.ticker}:{leg.expiration.isoformat()}:{leg.strike:g}:"
                           f"{_cp(leg)} has no real price on or before {entry_date}")
        entry_prices.append(p)
        entry_tags.append(tag)
        if spread == JUNK_SPREAD:
            entry_spread_junk = True     # commission only on this leg-side
        elif spread is None:
            entry_spread_complete = False
        else:
            entry_spread_units += abs(leg.qty) * spread

    entry_net = sum(leg.qty * p for leg, p in zip(legs, entry_prices))
    if abs(entry_net) <= 1e-9:
        return {}

    # A polarity-fixed structure that priced to the wrong side is NOT PRICEABLE,
    # and neither is an entry whose legs are quoted against strike order. All
    # three are refused here, before `_effective_sim_cfg` and `_exit_basis`, so
    # such a row can never take the wrong sizing/exit profile or basis label.
    fills = " ".join(f"{lg.qty:+d}@{p:g}" for lg, p in zip(legs, entry_prices))
    if _refuse_debit_priced_to_credit(structure, entry_net):
        return _refuse(DEBIT_CREDIT_REFUSAL,
                       f"{structure} priced to a net CREDIT of {entry_net:.4f} at "
                       f"entry ({fills})")
    if _refuse_credit_priced_to_debit(structure, entry_net):
        return _refuse(CREDIT_DEBIT_REFUSAL,
                       f"{structure} priced to a net DEBIT of {entry_net:.4f} at "
                       f"entry ({fills})")
    bad_order = _monotonicity_violation(legs, entry_prices, entry_tags)
    if bad_order:
        return _refuse(NON_MONOTONIC_REFUSAL, f"{structure} {bad_order} ({fills})")

    # Credit structures get their own sizing (structural max loss, not premium
    # received) and exit profile (config/backtest.yml simulation.credit block).
    eff_cfg = _effective_sim_cfg(sim_cfg, entry_net, signal_date, structure)

    # Per-leg entry greeks, each from THAT LEG's own history row (2026-09-23).
    # Until then every non-anchor leg carried a Black-Scholes delta computed at
    # the ANCHOR's IV and underlying, so one bad anchor file corrupted every
    # leg's greek. Now: the leg's own `Delta` / `IV` / `Price~` off its entry-day
    # row, else the row its entry mark came from. A leg with no real delta
    # prints `delta=` blank, and the net `delta` is None — all-or-nothing, the
    # same rule the journal applies (a missing greek is None, never 0.0).
    detail_lines, net_delta, leg_underlyings = [], 0.0, []
    for leg, p, tag in zip(legs, entry_prices, entry_tags):
        greek_day, row = _leg_greek_row(leg)
        dlt = _real_greek(row, "Delta")
        leg_iv = _real_greek(row, "IV")
        leg_s = _to_float(row.get("Price~")) if row else None
        if leg_s is not None and leg_s > 0:
            leg_underlyings.append(leg_s)
        if dlt is None or net_delta is None:
            net_delta = None
        else:
            net_delta += leg.qty * dlt
        at = f" greeks@{greek_day.isoformat()}" if greek_day and greek_day != entry_date else ""
        detail_lines.append(
            f"{leg.ticker}:{leg.expiration.isoformat()}:{leg.strike:g}:{_cp(leg)} {leg.qty:+d}"
            f"  px={p:g} iv={'' if leg_iv is None else f'{leg_iv:g}%'}"
            f" delta={'' if dlt is None else f'{dlt:.3f}'}"
            f" S={'' if leg_s is None else f'{leg_s:g}'}{at} [{tag}]")

    S_entry = _entry_underlying(ticker, leg_underlyings, signal_date)

    _v_clamp = _defined_risk_bounds(legs)

    # Steps 2-4 — for each trading day, price each leg and net by qty.
    nearest_dte = min((leg.expiration - signal_date).days for leg in legs)
    path_cap = sim_cfg.get("path_cap_days", 120)
    cap_reached_expiry = nearest_dte <= path_cap
    end_date = signal_date + timedelta(days=min(nearest_dte, path_cap))

    # ─── The data end: no rule may fire past the last real quote ───────────────
    # A carried-forward mark is not a session that happened. `path_cap_days` is
    # 120, so a July signal simulates into November, and `_snap_asof` happily
    # carries the last scrape over every day in between. Until 2026-09-23 the
    # engine had no guard for that: on the June–July 2026 backfill 10 of 154
    # simulated plays fired an exit rule on a day after the last real quote, and
    # 11 more were stamped `cap_open` at the cap on frozen marks.
    #
    # LAST REAL QUOTE, for a POSITION, is the EARLIEST of its legs' last real
    # sessions. A spread is only as live as its deadest leg: once one leg stops
    # printing, the net mark is part frozen, so every later day is already partly
    # fabricated. Taking the LATEST leg instead would let a still-quoted long leg
    # license an exit priced off a short leg that has not traded for weeks.
    # Interior gaps truncate nothing — this is each leg's LAST session, not a run
    # of consecutive ones — so a leg that simply skipped a Tuesday is unaffected.
    def _leg_data_end(leg):
        """The last session this leg has a real quote for, within the path."""
        key = _key(leg)
        for src in exit_sources:
            series = barchart_series if src == "barchart" else contract_index
            _, snap = _snap_asof(series, key, end_date, leg.expiration)
            if snap is not None:
                return snap
        return None

    leg_data_ends = [_leg_data_end(leg) for leg in legs]
    path_data_end = (min(leg_data_ends)
                     if leg_data_ends and None not in leg_data_ends else None)

    # The grid ORIGIN is unchanged and must stay unchanged: the first weekday AFTER
    # the signal date, exactly what `_weekday_grid` returns. EVERY day index this
    # engine reports stays SIGNAL-relative — `days_held`, `mfe_day`, `mae_day`,
    # `time_exit_day`, `path_cap_days` — because three things outside this file
    # rebuild that grid from `signal_date` and index into it positionally:
    # `backtest_study/lib/harness.py` asserts `len(marks) == len(_weekday_grid(
    # signal_date, end))` (it is FROZEN — the mark count is its contract),
    # `backtest_study/lib/mtm_curve.py` and `f4_deployment/concurrency_correlation.py`
    # both take index 0 as the first session after the signal. Moving the origin
    # would break all three and pool two day-index conventions on one tab.
    #
    # What changed (robustness review B2, 2026-09-07) is the MARK, not the grid: a
    # grid day BEFORE the entry date is present but UNPRICED — value None, source
    # tag `pre_entry`, blank token in `daily_price_csv`/`daily_pnl_csv`. The fill
    # can land up to `_ENTRY_STALENESS_DAYS` after the signal
    # (classify.py::_entry_row_from_history), and those in-between days used to be
    # priced by carrying an old mark forward and compared against an entry struck
    # later, which booked MFE/MAE — and on ~4% of positions a realized exit — on
    # days the position did not exist yet. Unpriced days are skipped by every scan
    # in `_summarize_path`, so the first PRICED day is now the entry day. The
    # common case (entry = the first weekday after the signal) is unchanged.
    #
    # Not pricing them is also what keeps the B3 carry-forward honest: a pre-entry
    # day never asks `_price_leg` for a mark, so no stale quote is carried backwards
    # into a day before the fill.
    #
    # `d` is SIGNAL-relative as it always was: the clock the time exit measures.
    # `grid_fillable[i]` — could the WHOLE position be traded out on that day?
    # False when any leg's mark came from a quote with no bid: there is no bid to
    # sell a long into and no offer worth paying on a dead market, so an exit
    # cannot be FILLED there even though it can be MARKED there (2026-09-19).
    # The marks themselves are untouched — `_zero_bid_mark` is still the
    # liquidation mark the path is valued at, and the exit rules still scan that
    # path. This only moves WHERE the fill is taken once a rule has fired.
    # `grid_real[i]` — did EVERY leg print its own quote on that day? False as
    # soon as one leg's mark was carried forward, which is what separates
    # `path_status=complete` from `carried`.
    grid_marks, grid_spread_units, grid_fillable, grid_real = [], [], [], []
    grid_spread_junk = []
    for day in _weekday_grid(signal_date, end_date):
        d = (day - signal_date).days
        if day < entry_date:
            grid_marks.append((day, d, None, "pre_entry"))
            grid_spread_units.append(None)
            grid_spread_junk.append(False)
            grid_fillable.append(False)
            grid_real.append(False)
            continue
        value, tags = 0.0, []
        spread_units, spread_complete, spread_junk = 0.0, True, False
        day_one_sided, day_all_real = False, True
        for leg in legs:
            p, tag, spread, one_sided, snap = _price_leg(leg, day, d)
            if p is None:
                value = None
                break
            value += leg.qty * p
            tags.append(tag)
            day_one_sided = day_one_sided or one_sided
            day_all_real = day_all_real and snap == day
            if spread == JUNK_SPREAD:
                spread_junk = True
            elif spread is None:
                spread_complete = False
            else:
                spread_units += abs(leg.qty) * spread
        if value is not None and _v_clamp is not None:
            value = max(_v_clamp[0], min(_v_clamp[1], value))
        grid_marks.append((day, d, value, "+".join(tags) if value is not None else ""))
        grid_spread_units.append(
            spread_units if (value is not None and spread_complete) else None)
        grid_spread_junk.append(spread_junk)
        grid_fillable.append(value is not None and not day_one_sided)
        grid_real.append(value is not None and day_all_real)

    # 1-based index of the last grid day on or before the data end; 0 when the
    # data ended before the path began. None disables the rule, which happens
    # only when a leg has no dated quote at all.
    data_end_idx = (sum(1 for (day, _, _, _) in grid_marks if day <= path_data_end)
                    if path_data_end is not None else None)

    # Step 5 — daily_price_csv + realized exit + MFE/MAE.
    contracts = _size_contracts(entry_net, legs, eff_cfg)
    profit_target = eff_cfg.get("profit_target", 0.50)
    stop_loss = eff_cfg.get("stop_loss", 1.00)
    _tex_frac = eff_cfg.get("time_exit_dte_fraction")
    time_exit_day = int(dte_entry * _tex_frac) if _tex_frac else None
    loss_days_exit = eff_cfg.get("loss_days_exit")
    be_after = eff_cfg.get("be_after")

    _pos_value = abs(entry_net) * 100 * contracts
    _portfolio = eff_cfg.get("portfolio_value")

    def _effective_threshold(pct_of_premium_key, pct_of_portfolio_key):
        opts = []
        v = eff_cfg.get(pct_of_premium_key)
        if v is not None:
            opts.append(v * _pos_value)
        p = eff_cfg.get(pct_of_portfolio_key)
        if p is not None and _portfolio:
            opts.append(p * _portfolio)
        if not opts or _pos_value == 0:
            return None
        return min(opts) / _pos_value

    trailing_stop_trigger = _effective_threshold(
        "trailing_stop_trigger", "trailing_stop_portfolio_trigger_pct")
    trailing_stop_pct = _effective_threshold(
        "trailing_stop_pct", "trailing_stop_portfolio_trail_pct")

    result = {
        "signal_date": signal_date.isoformat(),
        "ticker": ticker,
        "structure": structure,
        "legs": format_legs(legs),
        "contracts": contracts,
        "dte_entry": dte_entry,
        # Blank, never 0.0, when the anchor row's IV is absent or the all-zero
        # sentinel (see `_real_greek`).
        "iv_entry_pct": round(iv, 4) if iv else "",
        "delta": round(net_delta, 4) if net_delta is not None else "",
        "entry_underlying": S_entry if S_entry is not None else "",
        "entry_option_price": round(entry_net, 4),
        "entry_premium_total": round(abs(entry_net) * 100 * contracts, 2),
        "entry_source": "+".join(entry_tags),
        "entry_leg_detail": "\n".join(detail_lines),
        "regime": candidate.get("regime", ""),
        "play": candidate["play"][:300],
        "horizon": candidate.get("horizon", ""),
        "oi_confirm_pct": candidate.get("oi_confirm_pct", ""),
        "cpir": candidate.get("cpir", ""),
        "iv_spread": candidate.get("iv_spread", ""),
        "iv_skew": candidate.get("iv_skew", ""),
        "iv_pct": candidate.get("iv_pct", ""),
        "score_total": candidate.get("score_total", ""),
        "score_flow": candidate.get("score_flow", ""),
        "score_dealer": candidate.get("score_dealer", ""),
        "score_price": candidate.get("score_price", ""),
        "score_vol": candidate.get("score_vol", ""),
        "score_catalyst": candidate.get("score_catalyst", ""),
    }

    result.update(_summarize_path(
        grid_marks, entry_net, profit_target, stop_loss, contracts,
        cap_reached_expiry, _max_loss_abs(eff_cfg),
        time_exit_day=time_exit_day,
        trailing_stop_trigger=trailing_stop_trigger,
        trailing_stop_pct=trailing_stop_pct,
        loss_days_exit=loss_days_exit,
        be_after=be_after,
        grid_fillable=grid_fillable,
        data_end_idx=data_end_idx,
        grid_real=grid_real,
        path_data_end=path_data_end,
    ))

    # Transaction costs (robustness review B1). Charged ONCE, against the realized
    # figures, after the path has been scanned — the exit rules are defined on
    # marks, so costs must not move the thresholds the path is read with. Both
    # knobs default to 0, which reproduces every pre-2026-09-07 number exactly.
    _apply_costs(result, eff_cfg, legs, contracts, entry_net,
                 entry_spread_units if entry_spread_complete else None,
                 grid_spread_units, entry_junk=entry_spread_junk,
                 grid_spread_junk=grid_spread_junk)

    # Which exit profile this row was simulated on. Empty on rows written before
    # 2026-07-22 = PROD-basis; see _exit_basis.
    result["exit_basis"] = _exit_basis(sim_cfg, entry_net, signal_date, structure)

    # Structural risk columns — independent of the daily path, so computed once
    # here rather than threaded through _summarize_path. Blank when the max loss
    # can't be bounded (mirrors the sizing fallback above).
    mlpu = _max_loss_per_unit(legs, entry_net)
    max_loss_per_contract = round(mlpu * 100, 2) if mlpu is not None else ""
    realized_pnl_abs = result.get("realized_pnl_abs")
    pnl_on_risk_pct = (
        round(realized_pnl_abs / (max_loss_per_contract * contracts), 4)
        if max_loss_per_contract not in ("", 0)
        and isinstance(realized_pnl_abs, (int, float))
        else ""
    )
    result["max_loss_per_contract"] = max_loss_per_contract
    result["pnl_on_risk_pct"] = pnl_on_risk_pct
    return result
