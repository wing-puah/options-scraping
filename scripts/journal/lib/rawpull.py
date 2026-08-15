"""
The on-disk shape of a broker pull — the contract between `s01_pull.py` and everything downstream.

PRODUCTION TIER, dependency-free on purpose. `s01_pull.py` imports `lib.ibkr` and
talks to the gateway; `s02_reconcile.py` and `s03_risk.py` must NOT. They read this
normalised dict instead, so the broker client's response shapes stay behind one
boundary and swapping transport (Client Portal today, Flex or TWS tomorrow) is a
change to `s01_pull.py` alone.

The file it describes is IMMUTABLE. `journal/raw/ibkr-<date>-<HHMM>.json` is
written once and never edited: it is the primary evidence for every journal row,
and re-running the pipeline must re-derive conclusions from it rather than
mutate it. Replay any past pull with `--from-raw`.

Schema (v1):

    {
      "schema_version": 1,
      "pulled_at_utc":  "2026-08-14T20:15:03Z",
      "trade_date":     "2026-08-14",     # the session the pull is FOR
      "source":         "ibkr-cpapi",
      "account_id":     "U1234567",
      "net_liquidation": 123456.78,        # equity basis for the risk caps
      "trades":    [ Fill,     ... ],
      "positions": [ Position, ... ],
      "contracts": { "<conid>": Contract },
      "greeks":    { "<conid>": Greek    },
      "underlying_prices": { "NVDA": 175.20 }
    }

    Fill      {exec_id, conid, symbol, side ("BUY"/"SELL"), size, price,
               commission, net_amount, realized_pnl, trade_time (ISO-8601 UTC),
               order_id, open_close ("O"/"C"/"?")}
    Position  {conid, position (signed contracts), avg_cost, mkt_price,
               unrealized_pnl}
    Contract  {symbol (underlying), sec_type, strike, expiry ("YYYY-MM-DD"),
               right ("C"/"P"), multiplier}
    Greek     {delta, gamma, theta, vega, iv, source ("ibkr"/"unavailable")}

A greek that the broker never returned is `null`, NEVER 0.0 — see the
missing/zero invariant in config.py. `validate()` enforces that distinction is at
least representable, and refuses a pull that is internally inconsistent.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from ..config import (DELTA_SOURCE_UNAVAILABLE, DELTA_SOURCES_REAL, Greeks, Leg)

SCHEMA_VERSION = 1

_REQUIRED_TOP = ("schema_version", "pulled_at_utc", "trade_date", "source",
                 "trades", "positions", "contracts")


class RawPullError(ValueError):
    """A pull file that cannot be trusted to build a journal from."""


def validate(raw: dict) -> None:
    """Raise RawPullError unless `raw` is a usable pull.

    Deliberately strict. A malformed pull that is merely *tolerated* produces a
    journal that looks complete and is not — the single worst outcome for a
    record whose whole job is to be the truth about what you traded.
    """
    missing = [k for k in _REQUIRED_TOP if k not in raw]
    if missing:
        raise RawPullError(f"pull is missing required key(s): {', '.join(missing)}")

    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise RawPullError(
            f"pull schema_version {version!r} != {SCHEMA_VERSION} — refusing to "
            "read a pull written by a different pipeline version")

    contracts = raw.get("contracts") or {}
    unresolved = sorted({str(t.get("conid")) for t in raw["trades"]
                         if str(t.get("conid")) not in contracts})
    if unresolved:
        # Every fill must be pinned to a real contract. This is precisely what
        # conid-based identity buys over the old price-matching reconstruction,
        # so a gap here means the secdef lookup silently failed and the journal
        # would record trades whose strike/expiry are guesses.
        raise RawPullError(
            f"{len(unresolved)} fill conid(s) have no contract detail: "
            f"{', '.join(unresolved[:8])}{'...' if len(unresolved) > 8 else ''}")

    for cid, g in (raw.get("greeks") or {}).items():
        source = g.get("source")
        if source in DELTA_SOURCES_REAL and g.get("delta") is None:
            raise RawPullError(
                f"conid {cid} claims delta_source={source} but carries a null delta — "
                "a missing greek must be marked unavailable, not sourced")


def load(path: str | Path) -> dict:
    """Read and validate a pull file."""
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    validate(raw)
    raw.setdefault("_path", str(path))
    return raw


def save(raw: dict, path: str | Path) -> Path:
    """Write a pull ONCE. Refuses to overwrite an existing file.

    A pull is evidence. Re-running the pipeline must never silently replace the
    record of what the broker actually said at the time.
    """
    validate(raw)
    path = Path(path)
    if path.exists():
        raise RawPullError(
            f"{path} already exists — broker pulls are immutable evidence and are "
            "never overwritten; use a new timestamp or --from-raw to replay this one")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, sort_keys=True, default=str),
                    encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Typed views over the raw dict
# --------------------------------------------------------------------------
def contract_for(raw: dict, conid: int) -> dict:
    c = (raw.get("contracts") or {}).get(str(conid))
    if c is None:
        raise RawPullError(f"no contract detail for conid {conid}")
    return c


def greeks_map(raw: dict) -> dict[int, Greeks]:
    """`{conid: Greeks}`, preserving the missing-vs-zero distinction."""
    out: dict[int, Greeks] = {}
    for cid, g in (raw.get("greeks") or {}).items():
        conid = int(cid)
        out[conid] = Greeks(
            conid=conid,
            delta=g.get("delta"), gamma=g.get("gamma"), theta=g.get("theta"),
            vega=g.get("vega"), iv=g.get("iv"),
            underlying_price=g.get("underlying_price"),
            source=g.get("source", DELTA_SOURCE_UNAVAILABLE),
        )
    return out


def _parse_date(v) -> date:
    if isinstance(v, date):
        return v
    return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()


def fill_to_leg(raw: dict, fill: dict) -> Leg:
    """Build a Leg from a fill plus its resolved contract.

    `qty` is signed from the fill side: BUY is long, SELL is short. The broker's
    own `size` is always positive, so the sign must come from the side and
    nowhere else.
    """
    conid = int(fill["conid"])
    c = contract_for(raw, conid)
    size = abs(int(fill["size"]))
    qty = size if str(fill["side"]).upper() == "BUY" else -size
    return Leg(
        conid=conid,
        symbol=str(c["symbol"]).upper(),
        expiry=_parse_date(c["expiry"]),
        strike=float(c["strike"]),
        right=str(c["right"]).upper()[:1],
        qty=qty,
        fill_price=float(fill["price"]),
        # `is None`, never truthiness: a genuinely zero commission is a real
        # value and must stay 0.0, while an absent one must stay absent.
        commission=(None if fill.get("commission") is None
                    else float(fill["commission"])),
        exec_id=str(fill["exec_id"]),
        fill_time=datetime.fromisoformat(str(fill["trade_time"]).replace("Z", "+00:00")),
        open_close=str(fill.get("open_close") or "?").upper()[:1],
        realized_pnl=fill.get("realized_pnl"),
    )
