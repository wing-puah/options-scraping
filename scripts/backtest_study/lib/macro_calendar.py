"""Scheduled US macro events (FOMC, minutes, CPI, NFP, PCE) as as-of features.

Infrastructure, not a study. Listed in `run.py`'s INFRA, same as `underlying.py`.

The data lives in `config/macro-events.yml` — hand-authored from the official
Fed / BLS / BEA schedules cited in its `meta.sources`; every date is public
record, transcribed, never estimated. The file/data split (code here, YAML in
`config/`) is the same shape `account_sim` already has with
`config/account-sim.yml`. Nothing under `scripts/backtest/`, `scripts/journal/`
or repo `lib/` imports this module.

NO LOOK-AHEAD — the boundary conventions, each one a test
---------------------------------------------------------
- `next_event(as_of)` is STRICTLY after `as_of`; `last_event(as_of)` is on or
  before. Same convention as `lib/price_catalyst.as_of_earnings_cells`, so a
  reader who knows one knows the other.
- `next_event` returns None when `as_of` is past that type's
  `verified_through` — a query beyond the published schedule must never answer
  "nothing ahead". A silent zero there would feed straight into a proximity
  bucket. This is `book._load_mech_labeler`'s stale-table warning promoted to a
  hard None.
- `count_between(start, end)` is start-EXCLUSIVE, end-INCLUSIVE — "did an event
  land during the hold", given the book's entry fill is at the entry session's
  open (`harness._weekday_grid` starts at signal+1).
- Events marked `unscheduled: true` (inter-meeting actions) are EXCLUDED from
  `next_event` — an emergency meeting is not knowable in advance, so counting
  it forward is look-ahead — and INCLUDED in `last_event`/`count_between`: it
  did happen and it did move the tape.
- Forward-looking distances are legitimate decision-time information because
  these schedules are published a year or more in advance — unlike earnings,
  which move. The residual look-ahead the file cannot detect (a date announced
  after the fact) is disclosed via `meta.compiled` and the pre-registration.

WHY `release_et` EXISTS (not decoration)
----------------------------------------
The book enters at the NEXT session's open, so any event on the signal date is
already in the entry price regardless of clock time. The column matters for
exactly one case: an event on the ENTRY session itself. An 08:30 ET CPI/NFP/PCE
prints before the 09:30 open and is in the entry fill; a 14:00 ET FOMC
statement or minutes release lands after it, so the position sits in front of
the event on day 0. `Event.pre_open` is that distinction, and `event_read`'s
`on_asof_*` field carries it; it cannot be recovered from the date alone.

Pure functions over one YAML file. No model imports, no production imports.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CALENDAR_YML = ROOT / "config" / "macro-events.yml"
EVENT_TYPES = ("fomc", "fomc_minutes", "cpi", "nfp", "pce")
OPEN_ET = "09:30"


@dataclass(frozen=True)
class Event:
    date: date
    type: str
    release_et: str  # "HH:MM" Eastern
    label: str
    unscheduled: bool = False

    @property
    def pre_open(self) -> bool:
        """True when the release prints before the 09:30 ET open.

        At-the-open ("09:30") is NOT pre-open: the fill cannot be assumed to
        contain a print landing the same minute.
        """
        return self.release_et < OPEN_ET


class MacroCalendar:
    """The parsed calendar plus the per-type as-of queries."""

    def __init__(self, events: list[Event], verified_through: dict[str, date],
                 compiled: date, path: Path | None = None):
        self._events = sorted(events, key=lambda e: (e.date, e.type))
        self._by_type: dict[str, list[Event]] = {t: [] for t in EVENT_TYPES}
        for e in self._events:
            self._by_type[e.type].append(e)
        self._verified_through = verified_through
        self.compiled = compiled
        self.path = path

    # -- construction ------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Path = CALENDAR_YML) -> "MacroCalendar":
        return _load(str(path))

    @classmethod
    def parse(cls, raw: dict, path: Path | None = None) -> "MacroCalendar":
        meta = raw.get("meta") or {}
        vt_raw = meta.get("verified_through") or {}
        compiled = _as_date(meta.get("compiled"), "meta.compiled")
        verified_through = {t: _as_date(d, f"meta.verified_through.{t}")
                            for t, d in vt_raw.items()}

        events: list[Event] = []
        seen: set[tuple[str, date]] = set()
        for i, entry in enumerate(raw.get("events") or []):
            etype = entry.get("type")
            if etype not in EVENT_TYPES:
                raise ValueError(f"events[{i}]: unknown type {etype!r} "
                                 f"(expected one of {EVENT_TYPES})")
            edate = _as_date(entry.get("date"), f"events[{i}].date")
            release_et = entry.get("release_et")
            if (not isinstance(release_et, str) or len(release_et) != 5
                    or release_et[2] != ":" or not release_et.replace(":", "").isdigit()):
                raise ValueError(f"events[{i}]: release_et must be 'HH:MM', "
                                 f"got {release_et!r}")
            key = (etype, edate)
            if key in seen:
                raise ValueError(f"events[{i}]: duplicate (type, date) {key}")
            seen.add(key)
            events.append(Event(date=edate, type=etype, release_et=release_et,
                                label=str(entry.get("label", "")),
                                unscheduled=bool(entry.get("unscheduled", False))))

        present = {e.type for e in events}
        missing_vt = present - set(verified_through)
        if missing_vt:
            raise ValueError(f"meta.verified_through missing for types "
                             f"present in events: {sorted(missing_vt)}")
        return cls(events, verified_through, compiled, path)

    # -- coverage ----------------------------------------------------------

    def verified_through(self, etype: str) -> date:
        return self._verified_through[etype]

    def covers(self, as_of: date, etype: str) -> bool:
        return as_of <= self._verified_through[etype]

    def coverage(self) -> dict[str, dict]:
        out = {}
        for t in EVENT_TYPES:
            evs = self._by_type[t]
            out[t] = {
                "n": len(evs),
                "first": evs[0].date if evs else None,
                "last": evs[-1].date if evs else None,
                "verified_through": self._verified_through.get(t),
            }
        return out

    # -- queries -----------------------------------------------------------

    def events(self, types: tuple[str, ...] = EVENT_TYPES,
               start: date | None = None, end: date | None = None) -> list[Event]:
        """All events of `types`, date-inclusive on both ends. Listing helper —
        the as-of semantics live in next/last/count_between."""
        return [e for e in self._events if e.type in types
                and (start is None or e.date >= start)
                and (end is None or e.date <= end)]

    def next_event(self, as_of: date, etype: str) -> Event | None:
        """First SCHEDULED event of `etype` STRICTLY after `as_of`; None past
        `verified_through` (unknown is not 'nothing ahead') or when the
        verified window holds no later event."""
        if not self.covers(as_of, etype):
            return None
        for e in self._by_type[etype]:
            if e.date > as_of and not e.unscheduled:
                return e
        return None

    def last_event(self, as_of: date, etype: str) -> Event | None:
        """Latest event of `etype` ON OR BEFORE `as_of`, unscheduled included —
        it happened, and backward-looking is always knowable."""
        out = None
        for e in self._by_type[etype]:
            if e.date > as_of:
                break
            out = e
        return out

    def events_between(self, start: date, end: date,
                       types: tuple[str, ...] = EVENT_TYPES) -> list[Event]:
        """Events with start < date <= end (start-exclusive, end-inclusive)."""
        return [e for e in self._events
                if e.type in types and start < e.date <= end]

    def count_between(self, start: date, end: date, etype: str) -> int:
        return len(self.events_between(start, end, (etype,)))


# -- as-of feature reads (what a study attaches per record) -----------------

def event_read(cal: MacroCalendar, as_of: date,
               types: tuple[str, ...] = EVENT_TYPES) -> dict:
    """Per-type proximity at `as_of` (a record's ENTRY session, not its signal
    date), plus pooled macro fields.

    Forward fields are None when that type's schedule is not verified through
    `as_of`. The pooled forward pair requires EVERY type covered — an uncovered
    schedule could hide an earlier event, so a pooled minimum over the covered
    subset would be look-ahead-shaped optimism. Backward pooling has no such
    problem and always answers.

    `on_asof_<t>` is None / "pre_open" / "post_open" for an event landing ON
    `as_of` itself — the one case where clock time decides whether the entry
    fill already contains the print (see module docstring).
    """
    out: dict = {}
    nexts: list[tuple[int, str]] = []
    lasts: list[tuple[int, str]] = []
    all_covered = True
    for t in types:
        nxt = cal.next_event(as_of, t)
        lst = cal.last_event(as_of, t)
        covered = cal.covers(as_of, t)
        all_covered &= covered
        out[f"next_{t}"] = nxt.date if nxt else None
        out[f"days_to_next_{t}"] = (nxt.date - as_of).days if nxt else None
        out[f"last_{t}"] = lst.date if lst else None
        out[f"days_since_last_{t}"] = (as_of - lst.date).days if lst else None
        on = lst if lst and lst.date == as_of else None
        out[f"on_asof_{t}"] = None if on is None else (
            "pre_open" if on.pre_open else "post_open")
        if nxt:
            nexts.append(((nxt.date - as_of).days, t))
        if lst:
            lasts.append(((as_of - lst.date).days, t))
    if all_covered and nexts:
        d, t = min(nexts)
        out["days_to_next_macro"], out["next_macro_type"] = d, t
    else:
        out["days_to_next_macro"], out["next_macro_type"] = None, None
    if lasts:
        d, t = min(lasts)
        out["days_since_last_macro"], out["last_macro_type"] = d, t
    else:
        out["days_since_last_macro"], out["last_macro_type"] = None, None
    return out


def window_read(cal: MacroCalendar, entry_session: date, expiry: date,
                hold_end: date | None = None,
                types: tuple[str, ...] = EVENT_TYPES) -> dict:
    """Event counts inside a position's windows, start-exclusive from the
    entry session (a day-0 event is `event_read`'s `on_asof_*` case, not a
    window count). `n_*_in_dte` is census-only on this book — near-constant,
    pre-declared non-readable in the study's registration."""
    out: dict = {}
    total_dte = total_hold = 0
    for t in types:
        n = cal.count_between(entry_session, expiry, t)
        out[f"n_{t}_in_dte"] = n
        total_dte += n
        if hold_end is not None:
            h = cal.count_between(entry_session, hold_end, t)
            out[f"n_{t}_in_hold"] = h
            total_hold += h
        else:
            out[f"n_{t}_in_hold"] = None
    out["n_macro_in_dte"] = total_dte
    out["n_macro_in_hold"] = total_hold if hold_end is not None else None
    return out


@lru_cache(maxsize=4)
def _load(path_str: str) -> MacroCalendar:
    path = Path(path_str)
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}
    return MacroCalendar.parse(raw, path)


def _as_date(value, where: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"{where}: expected a date, got {value!r}")
