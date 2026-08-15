"""
Step 2 — group the day's fills into positions, classify each one, and match it
against the analysis that (maybe) proposed it.

PRODUCTION TIER, pure computation. Reads a validated rawpull dict (see
lib/rawpull.py) plus the analysis book (see lib/analysis.py) and returns
`list[PositionEvent]` (see config.py) — no network, no Sheets, no file writes.

THIS IS THE DAILY COUNTERPART OF `scripts/live_loop/stage1_map_fills.py`.
Both turn live fills into a structure label, a signal-date match and a
deployment-ladder tier, and both call the SAME encoding of those rules
(`scripts/live_loop/mapping.py`) so the two can never disagree about a tier.
The one structural difference: stage1 infers contract identity by joining a
fill price to an open position's `average_price` within a tolerance, because
its hand-pasted MCP snapshot carries no broker contract id. Every fill here
carries a real `conid` (rawpull.validate() refuses a pull where that is not
true), so identity is exact and that price-matching inference is simply not
needed — every leg's `match` is populated straight from the Leg itself.

That same exact identity is also what lets `_merge_legs_by_conid()` fold the
broker's FILLS back into the operator's LEGS: one contract filled in three
parts is 3 contracts of a one-leg position, not a "3-leg combo". Everything
downstream of the merge — structure, contract count, net price, commission,
DTE, tier, and `PositionEvent.conid_key()` — reads the merged legs. The one
deliberate exception is `source_ref`, which stays keyed on the PRE-merge
executions because it is the journal's dedup key.
"""

from __future__ import annotations

import logging
import math
from dataclasses import replace
from datetime import date as _date
from datetime import datetime as _datetime
from pathlib import Path

from . import s03_risk as risk
from .lib import analysis
from .config import Leg, OPTION_MULTIPLIER, PositionEvent
from .lib.rawpull import contract_for, fill_to_leg, greeks_map

try:  # `python3 -m scripts.journal...` — ROOT is on sys.path
    from scripts.live_loop import mapping
except ImportError:  # tests/conftest.py puts scripts/ on sys.path directly
    from live_loop import mapping

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def reconcile(raw: dict, ac_df=None) -> list[PositionEvent]:
    """Group `raw`'s fills into positions and return one PositionEvent each.

    `ac_df` defaults to `analysis.load()`'s dataframe only when not supplied —
    callers that already have the book (e.g. to share it with risk/report
    steps) should pass it through rather than pay for a second load.
    """
    if ac_df is None:
        ac_df, _source = analysis.load()

    pairs, n_settlement = _fills_to_legs(raw)
    if n_settlement:
        log.info(
            "Dropped %d zero-price settlement row(s) before grouping "
            "(expiry/assignment bookkeeping, not real fills — price == 0 and "
            "no realized P&L to corroborate)", n_settlement)

    positions_adapter = _positions_adapter(raw)
    greeks = greeks_map(raw)
    regime_by_date = analysis.market_regime_by_date(ac_df)
    mech_cell_by_date = analysis.mech_cell_by_date(ac_df)

    events = []
    for legs in _group_legs(pairs):
        events.append(_build_event(legs, positions_adapter, greeks, raw, ac_df,
                                   regime_by_date, mech_cell_by_date))
    return events


# --------------------------------------------------------------------------
# 1. Fills -> legs -> groups
# --------------------------------------------------------------------------
def _fills_to_legs(raw: dict) -> tuple[list[tuple[dict, Leg]], int]:
    """Build a Leg for every fill, dropping zero-price settlement rows.

    A settlement row (price == 0 AND no/zero realized_pnl) is expiry/assignment
    bookkeeping IBKR stamps outside market hours, not a fill — the identical
    distinction `scripts/live_loop/stage1_map_fills.py::reconstruct()` makes. A
    zero-price row that DOES carry a nonzero realized_pnl is real expiration
    P&L and stays in scope.

    Returns `(fill, Leg)` pairs (not bare Legs) because grouping needs the raw
    fill's `order_id`, which Leg does not carry.
    """
    pairs: list[tuple[dict, Leg]] = []
    dropped = 0
    for fill in raw.get("trades", []):
        leg = fill_to_leg(raw, fill)
        if leg.fill_price == 0 and not leg.realized_pnl:
            dropped += 1
            continue
        pairs.append((fill, leg))
    return pairs, dropped


def _group_key(fill: dict):
    """order_id when present, else the fill's exact trade_time.

    A combo order fills every leg at the same instant, so trade_time is a safe
    fallback identity when the broker fill carries no order_id.
    """
    oid = fill.get("order_id")
    if oid not in (None, "", 0):
        return ("order", oid)
    return ("time", str(fill.get("trade_time")))


def _group_legs(pairs: list[tuple[dict, Leg]]) -> list[list[Leg]]:
    groups: dict = {}
    order: list = []
    for fill, leg in pairs:
        key = _group_key(fill)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(leg)
    return [groups[k] for k in order]


def _merge_legs_by_conid(legs: list[Leg]) -> tuple[list[Leg], list[str]]:
    """Collapse legs that share a conid into ONE leg per contract.

    A broker reports FILLS, not positions: buying 2 contracts of one strike can
    arrive as two separate executions, and this module turns every fill into its
    own `Leg`. Left alone that makes a 2-contract 77/80 vertical read as a
    "4-leg combo (credit)" at half the true contract count, and 3 fills of one
    long call read as a "3-leg combo". A conid IS the contract, so legs sharing
    one are the same leg filled in parts and must be summed. Legs with DISTINCT
    conids are never touched — a genuine 3-leg combo (three different contracts)
    stays a 3-leg combo.

    Merge rules per conid, all chosen so nothing is silently invented:
      qty          summed (signed)
      fill_price   sum(qty_i * price_i) / sum(qty_i) — SIGNED-quantity weighted,
                   so `qty_merged * price_merged == sum(qty_i * price_i)` exactly
                   and the event's `net_cash` is unchanged by merging
      commission   None if ANY part is None, else the sum — the same
                   all-or-nothing rule `_build_event` applies across legs
      realized_pnl sum of the non-None parts, else None
      fill_time    the earliest part
      open_close   the shared flag, or '?' when the parts disagree
      exec_id      the parts joined with '+', so the executions stay traceable

    REFUSE TO MERGE when any conid's parts do not all carry the same NONZERO qty
    sign: `sum(qty)` can be zero (a division by zero, and that contract's whole
    `net_cash` contribution would be lost), and a signed-weighted average across
    opposite signs is not a price of anything. In that case the WHOLE event is
    left unmerged and a note says so — an over-labelled event is recoverable, a
    fabricated price is not.

    Returns `(legs, notes)`; `legs` is the input list unchanged when there is
    nothing to merge or when merging was refused.
    """
    by_conid: dict[int, list[Leg]] = {}
    for lg in legs:
        by_conid.setdefault(lg.conid, []).append(lg)

    multi = {conid: grp for conid, grp in by_conid.items() if len(grp) > 1}
    if not multi:
        return legs, []

    mixed = sorted(conid for conid, grp in multi.items()
                   if len({(lg.qty > 0) - (lg.qty < 0) for lg in grp}) > 1
                   or any(lg.qty == 0 for lg in grp))
    if mixed:
        return legs, [
            f"fills on conid(s) {mixed} carry opposite (or zero) signed "
            "quantities within one fill group — legs left UNMERGED, so this "
            "event reports one leg per fill: a signed-quantity-weighted average "
            "price across opposite signs is meaningless and the net quantity can "
            "be zero"]

    merged: list[Leg] = []
    for conid, grp in by_conid.items():
        if len(grp) == 1:
            merged.append(grp[0])
            continue
        qty = sum(lg.qty for lg in grp)
        price = sum(lg.qty * lg.fill_price for lg in grp) / qty
        commission = (None if any(lg.commission is None for lg in grp)
                      else sum(lg.commission for lg in grp))
        pnl_parts = [lg.realized_pnl for lg in grp if lg.realized_pnl is not None]
        flags = {lg.open_close for lg in grp}
        merged.append(replace(
            grp[0],
            qty=qty,
            fill_price=price,
            commission=commission,
            realized_pnl=sum(pnl_parts) if pnl_parts else None,
            fill_time=min(lg.fill_time for lg in grp),
            open_close=flags.pop() if len(flags) == 1 else "?",
            exec_id="+".join(lg.exec_id for lg in grp),
        ))

    merged.sort(key=lambda lg: (lg.fill_time, lg.conid))
    return merged, [
        f"{len(legs)} fills merged into {len(merged)} leg(s): "
        f"{len(multi)} contract(s) filled in multiple parts (quantities summed, "
        "price is the signed-quantity-weighted average, so net cash is unchanged)"]


# --------------------------------------------------------------------------
# 2. Adapters into the stage1 shape mapping.py expects
# --------------------------------------------------------------------------
# `classify_structure()` and `map_entry()` (scripts/live_loop/mapping.py) were
# written against stage1's hand-reconstructed shape:
#   entry  = {"legs": [{"trade": {side, price, commission}, "match": pos|None}]}
#   positions = [{"is_option", "symbol", "expiry", "strike", "right", "position"}]
# The adapters below present our Leg objects and rawpull's own open-position
# snapshot in that shape. They do NOT re-derive structure/tier logic — that
# stays exactly where deployment-rules.md's one encoding lives.
def _entry_adapter(legs: list[Leg]) -> dict:
    legs_out = []
    for lg in legs:
        # 0.0 rather than None for an unreported commission is safe HERE and
        # only here: mapping.classify_structure uses it for a net-with-commission
        # figure this module discards, and the structure label itself does not
        # depend on it. The costed value the journal records keeps its None.
        trade = {"side": "BUY" if lg.qty > 0 else "SELL",
                 "price": lg.fill_price, "commission": lg.commission or 0.0}
        # `match` is never None here — see the module docstring: a real conid
        # means identity is always known, unlike stage1's price-matched infer.
        match = {"position": lg.qty, "strike": lg.strike, "expiry": lg.expiry,
                 "right": lg.right, "symbol": lg.symbol}
        legs_out.append({"trade": trade, "match": match})
    return {"legs": legs_out}


def _parse_expiry(v) -> _date | None:
    if v is None:
        return None
    if isinstance(v, _date):
        return v
    return _datetime.strptime(str(v)[:10], "%Y-%m-%d").date()


def _positions_adapter(raw: dict) -> list[dict]:
    """The open book in `classify_structure()`'s `positions` shape.

    `s01_pull.py` only ever writes OPTION positions into `raw["positions"]`
    (`_is_option()` filters stock rows before the pull is built), so
    `is_option` is unconditionally True here. Expiry is parsed to a `date`
    (matching Leg.expiry) rather than left as the raw "YYYY-MM-DD" string —
    `_is_overlay()` compares expiries with `!=`, and a date never equals the
    string that spells it, so leaving it unparsed would silently defeat every
    overlay check.
    """
    out = []
    for p in raw.get("positions", []):
        conid = int(p["conid"])
        c = contract_for(raw, conid)
        out.append({
            "conid": conid,
            "position": float(p.get("position") or 0),
            "symbol": str(c["symbol"]).upper(),
            "expiry": _parse_expiry(c.get("expiry")),
            "strike": float(c["strike"]) if c.get("strike") is not None else None,
            "right": str(c["right"]).upper()[:1] if c.get("right") else None,
            "is_option": True,
        })
    return out


# --------------------------------------------------------------------------
# 3. Action classification
# --------------------------------------------------------------------------
def _classify_action(legs: list[Leg]) -> tuple[str, list[str]]:
    """OPEN / CLOSE / ROLL / PARTIAL from the legs' open_close flags, corroborated
    by realized_pnl. NEVER from the sign of net price — a credit is not a close.

    Per-leg resolution:
      'O'                          -> opening
      'C'                          -> closing
      '?' with a nonzero realized_pnl -> closing (corroborated)
      '?' with no/zero realized_pnl   -> UNRESOLVED

    Group-level (in this priority order):
      PARTIAL  any leg is UNRESOLVED — reconcile() genuinely cannot tell
               whether that leg opened or closed the position, and guessing is
               exactly the silent-failure mode this pipeline exists to avoid.
      ROLL     the group has BOTH an opening and a closing leg (a combo that
               unwinds one structure while putting on another in one order) —
               this is the ONLY case the brief names explicitly.
      CLOSE    every (resolved) leg is closing.
      OPEN     every (resolved) leg is opening (the default residual case).
    """
    opens = closes = unresolved = 0
    notes = []
    for lg in legs:
        if lg.open_close == "O":
            opens += 1
        elif lg.open_close == "C":
            closes += 1
        elif lg.realized_pnl:
            closes += 1
        else:
            unresolved += 1
    if unresolved:
        notes.append(
            f"{unresolved} leg(s) carry an unresolved open/close flag ('?' with "
            "no realized P&L to corroborate) — action is a best-effort PARTIAL, "
            "not a guess")
        return "PARTIAL", notes
    if opens and closes:
        return "ROLL", notes
    if closes:
        return "CLOSE", notes
    return "OPEN", notes


# --------------------------------------------------------------------------
# 4. Analysis matching
# --------------------------------------------------------------------------
def _match_to_analysis(struct_label: str, entry: dict, ticker: str,
                       event_date: str, ac_df) -> dict:
    """Walk candidate signal dates nearest-first; the first non-NONE match wins.

    `entry_lag_days` is the candidate's POSITION in
    `analysis.candidate_signal_dates()`'s nearest-first list (0 = nearest) —
    i.e. trading days counted over the BOOK's own dates, per the brief, not a
    calendar day-count.
    """
    core_struct = mapping.core_structure(entry)
    candidates = analysis.candidate_signal_dates(ac_df, event_date)
    if not candidates:
        return {"signal_date": None, "entry_lag_days": None,
                "match_confidence": "NONE", "ac_play": None, "ac_structure": None,
                "core_structure": core_struct,
                "note": "no analysis date precedes this fill within the lookback window"}

    inv_row = {"structure": struct_label, "entry": entry}
    for i, sig in enumerate(candidates):
        result = mapping.map_entry(inv_row, sig, ticker, ac_df)
        if result["confidence"] != "NONE":
            return {"signal_date": sig, "entry_lag_days": i,
                    "match_confidence": result["confidence"],
                    "ac_play": result["ac_play"], "ac_structure": result["ac_structure"],
                    "core_structure": result.get("core_structure") or core_struct,
                    "note": None}
    # Nothing matched at any lookback distance — keep the nearest as the record
    # rather than dropping the match entirely (brief: "keep the nearest
    # candidate as signal_date and confidence NONE").
    return {"signal_date": candidates[0], "entry_lag_days": 0,
            "match_confidence": "NONE", "ac_play": None, "ac_structure": None,
            "core_structure": core_struct, "note": None}


# --------------------------------------------------------------------------
# 5. Deployment-ladder tier
# --------------------------------------------------------------------------
def _short_leg_delta_for_tier(action: str, legs: list[Leg], greeks: dict):
    """A real short-leg delta ONLY for a currently-open position.

    "Currently open" is read off the pull itself, not off our own action
    classification: `s01_pull.py` populates `raw["greeks"]` for the OPEN book
    only, so a leg's conid appearing there already means the broker still
    shows the position open. A CLOSE is excluded outright regardless (its
    legs are typically gone from the book by the time of the pull, but a
    same-day open+close round-trip could coincidentally still show stale
    greeks, and a closed position's delta is not what §3's gate is about).
    """
    if action == "CLOSE":
        return None
    if not all(lg.conid in greeks for lg in legs):
        return None
    return risk.short_leg_delta(legs, greeks)


def _assign_tier(event: PositionEvent, greeks: dict) -> None:
    # Tier the EMITTED play's structure when one was matched, exactly like
    # stage1_map_fills.py does — a SUBSTITUTED live structure must not shift
    # the tier the analysis row itself would have received, or the two
    # pipelines (daily journal vs fortnightly audit) would disagree on the
    # same fill. Only fall back to the live-traded structure when nothing
    # matched at all (ac_structure is None).
    #
    # `core_structure` sits between the two. A financed vertical's LABEL is
    # "3-leg combo (debit)", which canonicalises to "unknown" and lands on the
    # Tier-C residual — but the position genuinely is the core vertical plus a
    # short leg, and that vertical has a real tier. Read it off the decomposed
    # core rather than the label: `_live_to_canonical` matches bare substrings
    # ("bull_call" in s), so encoding the core into the label instead would flip
    # a tier silently as a side effect of a cosmetic rename.
    tier_structure = (event.ac_structure or event.core_structure
                      or mapping._live_to_canonical(event.structure))
    sld = _short_leg_delta_for_tier(event.action, event.legs, greeks)
    tier, partial, reason = mapping.ladder_tier(
        tier_structure, event.market_regime, event.dte_at_entry, sld)
    event.tier = tier
    event.tier_reason = reason
    event.tier_verified = not partial


# --------------------------------------------------------------------------
# 6. Entry slippage
# --------------------------------------------------------------------------
def _entry_slippage_notes(ac_play: str | None, legs: list[Leg]) -> list[str]:
    """Strike mismatch is recorded; a numeric slippage figure is never invented.

    There is no reference/modeled entry price sourceable at reconcile time (no
    backtest row exists for a same-day fill — the same conclusion Step D of
    stage1_map_fills.py reaches: NOT_BACKTESTED). `net_price` is what was PAID,
    not a price to diff against itself, so `entry_slippage` stays None and the
    reason is always recorded rather than left implicit.
    """
    notes = []
    if ac_play:
        play_strikes = mapping.play_strikes(ac_play)
        fill_strikes = {lg.strike for lg in legs}
        if play_strikes and fill_strikes and play_strikes != fill_strikes:
            notes.append(
                f"fill strikes {sorted(fill_strikes)} differ from the matched "
                f"play's strikes {sorted(play_strikes)}")
    notes.append(
        "entry_slippage left None: no modeled/reference entry price is "
        "sourceable at reconcile time — net_price is what was paid, not a "
        "reference to diff it against, and inventing one is worse than a blank")
    return notes


# --------------------------------------------------------------------------
# 7. Assembly
# --------------------------------------------------------------------------
def _dte_at_entry(legs: list[Leg], event_date: _date) -> float:
    """Real DTE of the nearest-dated leg — not the play-text proxy."""
    nearest_expiry = min(lg.expiry for lg in legs)
    return float((nearest_expiry - event_date).days)


def _pull_filename(raw: dict) -> str:
    path = raw.get("_path")
    if path:
        return Path(path).name
    # Fallback for a raw dict reconciled in-process without a save/load
    # round-trip (rawpull.load() is what sets "_path"). Still deterministic
    # and stable across re-runs of the SAME pull.
    return f"ibkr-{raw.get('trade_date')}-{raw.get('pulled_at_utc')}"


def _source_ref(raw: dict, legs: list[Leg]) -> str:
    """The TradeJournal/CSV dedup key: pull filename + every exec id, sorted.

    MUST be computed from the PRE-merge legs (`_build_event`'s `source_legs`).
    Two reasons, and the second is the load-bearing one: the merged leg's
    `exec_id` is a '+'-joined composite, so sorting it would surface one token
    per contract instead of one per execution; and the resulting string has to
    stay BYTE-IDENTICAL to the keys already written to `journal/trades.csv`
    (e.g. `ibkr-2026-07-24-1648.json:112365669,112365782,112365808,112365899`).
    Anything else silently re-appends every multi-fill row ever journalled.
    """
    exec_ids = ",".join(sorted(lg.exec_id for lg in legs))
    return f"{_pull_filename(raw)}:{exec_ids}"


def _build_event(legs: list[Leg], positions_adapter: list[dict], greeks: dict,
                 raw: dict, ac_df, regime_by_date: dict, mech_cell_by_date: dict
                 ) -> PositionEvent:
    legs = sorted(legs, key=lambda lg: (lg.fill_time, lg.conid))
    # The PRE-merge legs, kept for `_source_ref` alone — see the note there.
    source_legs = legs
    legs, merge_notes = _merge_legs_by_conid(legs)
    notes: list[str] = list(merge_notes)

    tickers = {lg.symbol for lg in legs}
    ticker = legs[0].symbol
    if len(tickers) > 1:
        notes.append(f"fill group spans multiple underlyings {sorted(tickers)} — "
                     "reported under the first leg's ticker")

    fill_dt = min(lg.fill_time for lg in legs)
    event_date = fill_dt.date()

    entry = _entry_adapter(legs)
    struct_label, net_price, _net_wc, _status, cs_note, is_overlay = \
        mapping.classify_structure(entry, positions_adapter)
    if cs_note:
        notes.append(cs_note)

    action, action_notes = _classify_action(legs)
    notes.extend(action_notes)

    # All-or-nothing across legs, the same rule s03_risk.py applies to delta: a
    # group is only as costed as its least-costed leg. Summing the known legs
    # and calling the rest zero would report a total that looks whole.
    commission = (None if any(lg.commission is None for lg in legs)
                  else sum(lg.commission for lg in legs))
    net_cash = (sum(-(lg.qty * lg.fill_price * OPTION_MULTIPLIER) for lg in legs)
                - (commission or 0.0))
    realized_vals = [lg.realized_pnl for lg in legs if lg.realized_pnl]
    realized_pnl = sum(realized_vals) if realized_vals else None
    # gcd, not min: a ratio spread (e.g. a 1x2 backspread, qty +1/-2) has a real
    # "how many times was this ratio traded" answer distinct from its smallest
    # leg — gcd recovers that; min would just report the smallest leg's raw
    # size, which only coincides with gcd on a 1:1 ratio (every plain vertical
    # here, so the two choices agree on the common case).
    contracts = math.gcd(*(abs(lg.qty) for lg in legs))
    dte_at_entry = _dte_at_entry(legs, event_date)

    event = PositionEvent(
        date=event_date.isoformat(),
        trade_datetime_utc=fill_dt.isoformat(),
        ticker=ticker,
        structure=struct_label,
        action=action,
        legs=legs,
        contracts=contracts,
        net_price=net_price,
        commission=commission,
        net_cash=net_cash,
        realized_pnl=realized_pnl,
        dte_at_entry=dte_at_entry,
    )

    match = _match_to_analysis(struct_label, entry, ticker, event.date, ac_df)
    event.signal_date = match["signal_date"]
    event.entry_lag_days = match["entry_lag_days"]
    event.match_confidence = match["match_confidence"]
    event.ac_play = match["ac_play"]
    event.ac_structure = match["ac_structure"]
    event.core_structure = match.get("core_structure")
    if event.core_structure:
        notes.append(f"core structure {event.core_structure} "
                     f"(financed: {struct_label})")
    if match["note"]:
        notes.append(match["note"])

    # A financing/carry leg sold against a position already open was never an
    # attempt to trade a play, so scoring it NONE would count it as trading
    # off-plan. Recorded as OVERLAY and excluded from the match tally instead.
    # Only when nothing matched: if it DID match a play, that is the more
    # informative fact and it keeps its confidence.
    if is_overlay and event.match_confidence == "NONE":
        event.match_confidence = "OVERLAY"
        notes.append("financing/carry overlay on an existing same-ticker "
                     "position — not a play attempt, excluded from the match tally")

    # Market-level reads keyed on the SIGNAL date, never a play row — the
    # invariant lib/analysis.py's docstring pins.
    event.market_regime = regime_by_date.get(event.signal_date)
    event.mech_cell = mech_cell_by_date.get(event.signal_date)

    _assign_tier(event, greeks)

    event.entry_slippage = None
    notes.extend(_entry_slippage_notes(event.ac_play, legs))

    event.notes = "; ".join(notes)
    event.source_ref = _source_ref(raw, source_legs)
    return event
