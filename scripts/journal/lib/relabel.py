"""
Offline re-derivation of the structure label (and tier) of already-journalled rows.

WHY IT EXISTS. Until 2026-09-07 `s02_reconcile.py` named a fill group from the
FILL's signs rather than from the position the group acts on, so every CLOSE
was labelled the mirror image of what it closed: a closed bull call spread
became a `bear_call_spread`, which `ladder_tier()` vetoes. The bug is fixed at
source, but `journal/trades.csv` and the TradeJournal tab still hold the rows
written under it. This module says WHICH of those rows the fix would change.

IT ONLY PRINTS. Nothing here writes `journal/trades.csv`, and nothing here
touches Sheets or the network — the journal's local CSV is the append-only
record and rewriting it in place is not something a diagnostic gets to do.
Repairing the rows is a separate, deliberate act by the operator.

WHAT IT CAN AND CANNOT RE-DERIVE. `trades.csv` records the group's legs (the
canonical `TICKER:YYYY-MM-DD:STRIKE:C +N` grammar) and its NET price, not each
leg's own price. That is enough for every label whose only input is the legs'
signs, strikes and rights — which is every one- and two-leg group, i.e. every
row the bug actually inverted. It is NOT enough for a group of three or more
legs, whose label runs through `decompose_core()` and reads each leg's price;
those rows are counted as NOT RE-DERIVABLE and reported as such rather than
guessed.

THE `(overlay)` SUFFIX IS DROPPED ON A CLOSE, NEVER CARRIED. It is not
recomputable offline — it needs the open book as it stood that day — but on a
CLOSE row it is worse than unknown, it is INVERTED: `mapping._is_overlay()`
only fires on a leg whose `position` is NEGATIVE, and under the bug that
position was the FILL's sign, so a recorded suffix on a CLOSE can only have
come from a SELL-to-close, i.e. the position closed was LONG and was never an
overlay. Re-appending it would print `single long call (overlay)`, a label the
live pipeline cannot emit. So the suffix is dropped and the row is counted in
`overlay_unknown` instead. The mirror case is invisible here by the same
argument: a genuine overlay close (BUY-to-close a short leg) was recorded
WITHOUT a suffix and re-derives without one.

ONE ENCODING, STILL. The label comes from `mapping.classify_structure()` and
the tier from `mapping.ladder_tier()`, with `mapping.position_legs()` doing the
CLOSE orientation the live pipeline does. There is no second copy of any of
those rules here.

    python3 -m scripts.journal relabel                 # journal/trades.csv — the operator CLI
    python3 -m scripts.journal relabel --csv PATH
    python3 -m scripts.journal.lib.relabel             # same, invoked directly as a module
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import TRADES_CSV, Leg
from . import mapping


_LEG_RE = re.compile(
    r"^(?P<symbol>[A-Za-z0-9.\-]+):(?P<expiry>\d{4}-\d{2}-\d{2}):"
    r"(?P<strike>\d+(?:\.\d+)?):(?P<right>[CP])$")

_OVERLAY_SUFFIX = " (overlay)"

# `_vertical_label()` falls back to "mixed C/P vertical (credit)" and friends
# for pairs it cannot name, and that token is read off the group's NET price —
# which the CSV does carry, unlike the per-leg prices. See `_reorient_side()`.
_DEBIT_CREDIT_RE = re.compile(r"\((debit|credit)\)")


@dataclass(frozen=True)
class Relabel:
    """One row whose label and/or tier the fix changes."""

    row: int                      # 1-based data-row number in the CSV
    date: str
    ticker: str
    action: str
    legs: str
    old_structure: str
    new_structure: str
    old_tier: str
    new_tier: str
    note: str = ""
    overlay_dropped: bool = False

    def line(self) -> str:
        struct = ("" if self.old_structure == self.new_structure
                  else f"  structure {self.old_structure!r} -> {self.new_structure!r}")
        tier = ("" if self.old_tier == self.new_tier
                else f"  tier {self.old_tier or '-'} -> {self.new_tier or '-'}")
        note = f"  [{self.note}]" if self.note else ""
        return (f"row {self.row:>3}  {self.date}  {self.ticker:<6} {self.action:<8}"
                f"{struct}{tier}{note}")


def parse_legs(legs_string: str):
    """`TICKER:YYYY-MM-DD:STRIKE:C +N ...` -> list of dicts, or None.

    The same grammar `config.Leg.leg_string()` writes and
    `scripts/backtest/legs.py` parses. Returns None — never a partial list —
    when any token does not parse, so a caller can only ever act on a legs
    string it fully understood.
    """
    tokens = str(legs_string or "").split()
    if not tokens or len(tokens) % 2:
        return None
    out = []
    for contract, qty in zip(tokens[0::2], tokens[1::2]):
        m = _LEG_RE.match(contract)
        if not m:
            return None
        try:
            signed = int(qty)
        except ValueError:
            return None
        if signed == 0 or not qty[0] in "+-":
            return None
        out.append({
            "symbol": m.group("symbol").upper(),
            "expiry": datetime.strptime(m.group("expiry"), "%Y-%m-%d").date(),
            "strike": float(m.group("strike")),
            "right": m.group("right"),
            "qty": signed,
        })
    return out


def _legs_to_objects(parsed) -> list[Leg]:
    """Rebuild `Leg`s from a parsed legs string.

    `fill_price` is 0.0 for every leg: the CSV does not carry per-leg prices,
    and a fabricated one would silently steer `decompose_core()`. Callers must
    therefore only classify groups whose label does not read a price — see
    `_price_dependent()`.
    """
    return [Leg(conid=i, symbol=p["symbol"], expiry=p["expiry"],
                strike=p["strike"], right=p["right"], qty=p["qty"],
                fill_price=0.0, commission=None, exec_id=str(i),
                fill_time=datetime(2000, 1, 1), open_close="?")
            for i, p in enumerate(parsed)]


def _price_dependent(parsed) -> bool:
    """True when the group's label reads a PER-LEG price the CSV lacks.

    That is exactly one shape: three or more legs, where `decompose_core()`
    ranks candidate cores by net debit and the tier is then read off the core.
    One- and two-leg groups are named from signs, strikes and rights, with at
    most a debit/credit token that the GROUP net covers (`_reorient_side`).
    """
    return len(parsed) >= 3


def _reorient_side(label: str, net_price) -> str | None:
    """Flip a label's `(debit)`/`(credit)` token to the closed position's side.

    A label like `mixed C/P vertical (credit)` takes that word from the fill
    group's net, and on a CLOSE the position's side is the opposite: closing a
    long strangle for a $4 credit closes a DEBIT structure. `net_price` in the
    CSV is the fill's own cash (`+debit / -credit`), so negating it gives the
    position's. Returns None when the label carries no such token (nothing to
    do is signalled by the caller, not by a silent pass-through) and raises
    nothing — an unusable `net_price` returns the sentinel `""`.
    """
    if not _DEBIT_CREDIT_RE.search(label):
        return None
    net = _to_float(net_price)
    if net != net:  # NaN — no net recorded, so the side is not recoverable
        return ""
    return _DEBIT_CREDIT_RE.sub("(debit)" if -net > 0 else "(credit)", label)


def _rederive_row(row: dict, index: int) -> tuple[Relabel | None, str]:
    """`(diff_or_None, outcome)` for one CSV row. Outcome is one of
    'skipped', 'unparsed', 'not_rederivable', 'unchanged', 'changed'."""
    action = (row.get("action") or "").strip().upper()
    if action != "CLOSE":
        # OPEN groups were already oriented correctly; ROLL and PARTIAL are
        # deliberately left on the fill-sign reading by the fix itself.
        return None, "skipped"

    parsed = parse_legs(row.get("legs", ""))
    if not parsed:
        return None, "unparsed"
    if _price_dependent(parsed):
        return None, "not_rederivable"

    old_structure = (row.get("structure") or "").strip()
    recorded_overlay = old_structure.endswith(_OVERLAY_SUFFIX)

    pos_legs = mapping.position_legs(_legs_to_objects(parsed), closing=True)
    # No open book — the book as it stood that day is not recoverable from this
    # CSV, so the overlay test cannot run and the re-derived label never carries
    # the suffix. A RECORDED one is dropped rather than carried: see the module
    # docstring — on a CLOSE it can only have been read off the fill's sign, and
    # re-appending it would print a label the live pipeline cannot emit. The
    # drop is reported, not silent.
    new_structure, *_rest = mapping.classify_structure(pos_legs)
    reoriented = _reorient_side(new_structure, row.get("net_price"))
    if reoriented == "":
        return None, "not_rederivable"
    if reoriented is not None:
        new_structure = reoriented

    old_tier = (row.get("tier") or "").strip()
    # Same precedence `s02_reconcile._assign_tier` applies, minus the
    # `core_structure` rung: that only ever fires on a 3+-leg group, which this
    # module has already declined to re-derive. `short_leg_delta` is None
    # because `_short_leg_delta_for_tier()` returns None on a CLOSE anyway.
    #
    # CAVEAT, and it makes the tier count a LOWER BOUND: `ac_structure` wins
    # when present, and the recorded `ac_structure` was itself matched against
    # the INVERTED label. A row whose stale `ac_structure` happens to hold the
    # tier steady is reported as tier-unchanged even though live re-reconciling
    # (which re-matches from the corrected label) could move it.
    tier_structure = ((row.get("ac_structure") or "").strip()
                      or mapping._live_to_canonical(new_structure))
    new_tier, _partial, _reason = mapping.ladder_tier(
        tier_structure, row.get("market_regime") or "",
        _to_float(row.get("dte_at_entry")), None)

    if new_structure == old_structure and new_tier == old_tier:
        return None, "unchanged"
    note = ("recorded (overlay) suffix DROPPED — on a CLOSE it was read off the "
            "fill's sign, so it says the closed position was LONG, which cannot "
            "be an overlay; true overlay status is not recoverable offline"
            if recorded_overlay else "")
    return (Relabel(row=index, date=row.get("date", ""),
                    ticker=row.get("ticker", ""), action=action,
                    legs=row.get("legs", ""), old_structure=old_structure,
                    new_structure=new_structure, old_tier=old_tier,
                    new_tier=new_tier, note=note,
                    overlay_dropped=recorded_overlay),
            "changed")


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def rederive(csv_path=None) -> tuple[list[Relabel], dict]:
    """Read `csv_path` and return `(diffs, summary)`. READ-ONLY."""
    path = Path(csv_path if csv_path is not None else TRADES_CSV)
    summary = {"rows": 0, "close_rows": 0, "structure_changed": 0,
               "tier_changed": 0, "unchanged": 0, "unparsed": 0,
               "not_rederivable": 0, "overlay_unknown": 0}
    diffs: list[Relabel] = []
    if not path.exists():
        summary["missing"] = str(path)
        return diffs, summary

    with open(path, newline="") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=1):
            summary["rows"] += 1
            diff, outcome = _rederive_row(row, i)
            if outcome == "skipped":
                continue
            summary["close_rows"] += 1
            if outcome in ("unparsed", "not_rederivable", "unchanged"):
                summary[outcome] += 1
                continue
            diffs.append(diff)
            if diff.old_structure != diff.new_structure:
                summary["structure_changed"] += 1
            if diff.old_tier != diff.new_tier:
                summary["tier_changed"] += 1
            if diff.overlay_dropped:
                summary["overlay_unknown"] += 1
    return diffs, summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Print which journalled rows the P1 label fix would change. "
                    "Never writes.")
    ap.add_argument("--csv", default=None,
                    help=f"trades CSV to read (default: {TRADES_CSV})")
    args = ap.parse_args(argv)

    diffs, summary = rederive(args.csv)
    if "missing" in summary:
        print(f"no trades CSV at {summary['missing']} — nothing to re-derive")
        return 0

    print(f"{summary['rows']} row(s) read, {summary['close_rows']} CLOSE row(s) "
          f"examined (OPEN/ROLL/PARTIAL are unaffected by the fix)")
    for d in diffs:
        print(d.line())
    print(f"\nstructure would change on {summary['structure_changed']} row(s); "
          f"tier on {summary['tier_changed']}; "
          f"{summary['unchanged']} already correct; "
          f"{summary['not_rederivable']} need per-leg prices the CSV lacks; "
          f"{summary['unparsed']} unparseable legs string(s)")
    if summary["overlay_unknown"]:
        print(f"{summary['overlay_unknown']} row(s) had a recorded (overlay) "
              "suffix DROPPED: it is not recoverable offline, and on a CLOSE the "
              "recorded one was read off the fill's sign. A genuine overlay "
              "close recorded WITHOUT the suffix is equally undetectable here.")
    print("PRINT ONLY — journal/trades.csv and the TradeJournal tab are untouched.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
