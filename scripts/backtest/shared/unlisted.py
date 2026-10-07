"""Negative cache: option contracts Barchart does not list.

`fetch_option_histories` caches only contracts that returned rows. A contract
Barchart does not list (a synthesised far expiry, a non-standard weekly) was
therefore re-probed on every run, and each probe cost a ~15s Playwright wait for
a feed request that never comes. This module remembers those contracts in
``backtests/option_history_cache/_unlisted.jsonl`` so a repeat run skips them.

WHAT IS RECORDED. ``lib.barchart.session.HISTORY_NO_FEED`` (the page loaded 2xx,
promptly, logged in, and fired no price-history feed) and ``HISTORY_PAGE_404``
(the contract's PAGE answered 404 — how Barchart answers a contract it does not
list, seen live 2026-09-27). Network, DNS, SSL, closed-browser, login and parse
failures, a 403/429/5xx page, and ANY non-2xx from the feed are never recorded,
and even an evidence outcome is held PENDING until the browser is shown to be online around it
(:class:`EvidenceTracker`) — the 2026-09-25 outage produced hundreds of
`net::ERR_INTERNET_DISCONNECTED` failures that must not read as facts about a
contract. "No rows" is not recorded either: it was the symptom of the
three-month `startDate` bug (see lib/barchart/session.py HISTORY_START_DATE).

EXPIRY. An entry is re-checked after :data:`RECHECK_DAYS`; an EXPIRED contract
confirmed unlisted :data:`EXPIRED_CONFIRMED_CHECKS` times waits
:data:`EXPIRED_CONFIRMED_DAYS`, because a listing cannot appear after expiry. A
contract that later fetches rows is removed. ``--retry-unlisted`` (or
``BACKTEST_RETRY_UNLISTED=1``) ignores the file for one run.

FORMAT. JSONL, one object per contract, keyed by the cache-file stem
(``HYG_20250417_72.00P`` = ticker, expiry, strike, right). The file is rewritten
whole — merged with what is on disk, staged under a per-process name, then
``os.replace``d, all under an exclusive ``flock`` on a sibling ``.lock`` file —
so it is never half-written and two concurrent runs do not drop each other's
entries. A line whose fields do not parse is skipped on read (and so dropped on
the next write) rather than crashing a run after its scraping is done.
"""
from __future__ import annotations

import atexit
import fcntl
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from lib.barchart import options as barchart_options
from lib.barchart.session import (
    HISTORY_ERROR, HISTORY_HTTP_ERROR, HISTORY_NAV_ERROR, HISTORY_NO_FEED,
    HISTORY_NO_ROWS, HISTORY_OK, HISTORY_PAGE_404, HISTORY_SESSION,
)

log = logging.getLogger("backtest")

FILENAME = "_unlisted.jsonl"
RETRY_ENV = "BACKTEST_RETRY_UNLISTED"

RECHECK_DAYS = 30
EXPIRED_CONFIRMED_DAYS = 180
EXPIRED_CONFIRMED_CHECKS = 2

#: A NO_FEED is discarded if any fetch failure (network, HTTP, login, error)
#: happened within this many seconds of it, before or after.
TROUBLE_WINDOW_S = 120
#: ...and it needs a fetch that DID observe the feed (ok / no rows) within this
#: many seconds, proving the session and the feed path worked around it.
FEED_PROOF_WINDOW_S = 1800

#: Outcomes that are evidence the contract is unlisted; each is its own `reason`.
EVIDENCE = frozenset({HISTORY_NO_FEED, HISTORY_PAGE_404})
#: Recorded by `fetch_option_histories` once a BarchartSession has opened —
#: which it only does after verifying the login.
SESSION_OPEN = "session_open"
#: Outcomes that show the session was logged in at that moment.
LOGGED_IN = frozenset({SESSION_OPEN, HISTORY_OK, HISTORY_NO_ROWS, HISTORY_NO_FEED})
#: Outcomes whose page load answered 2xx — the browser was online.
UP = frozenset({HISTORY_OK, HISTORY_NO_ROWS, HISTORY_NO_FEED})
#: Outcomes that prove the feed path itself worked.
FEED_PROOF = frozenset({HISTORY_OK, HISTORY_NO_ROWS})
#: Outcomes that say the fetch, not the contract, failed. None = the session did
#: not report an outcome, which is treated as trouble.
TROUBLE = frozenset({HISTORY_NAV_ERROR, HISTORY_HTTP_ERROR, HISTORY_SESSION,
                     HISTORY_ERROR, None})


def _now() -> float:
    """Wall clock, a seam for tests."""
    return time.time()


def _today() -> date:
    return date.today()


def retry_requested(flag: bool | None = None) -> bool:
    """True when the negative cache is to be ignored for this run."""
    if flag is not None:
        return flag
    return os.getenv(RETRY_ENV, "").strip().lower() in ("1", "true", "yes")


def contract_id(c: dict) -> str:
    """The cache-file stem of a `fetch_option_histories` contract dict."""
    return barchart_options.cache_path(
        Path("."), c["symbol"], c["expiration"], c["strike"], c["opt_type"]).stem


def new_entry(c: dict, reason: str, stamp: str) -> dict:
    return {
        "key": contract_id(c),
        "ticker": c["symbol"].upper().strip(),
        "right": "C" if c["opt_type"].strip().title() == "Call" else "P",
        "strike": float(c["strike"]),
        "expiry": c["expiration"].isoformat(),
        "first_seen": stamp,
        "last_checked": stamp,
        "n_checks": 1,
        "reason": reason,
    }


def _valid(e) -> bool:
    """True when every field the readers use parses: `skip_until` reads
    `expiry`, `last_checked` and `n_checks`; `recorded` increments `n_checks`."""
    try:
        date.fromisoformat(str(e["expiry"])[:10])
        date.fromisoformat(str(e["last_checked"])[:10])
        n = e.get("n_checks", 1)
        return isinstance(e["key"], str) and isinstance(n, int) and not isinstance(n, bool)
    except (KeyError, ValueError, TypeError):
        return False


def load(path: Path) -> dict[str, dict]:
    """``{key: entry}``; a missing file is empty, and a line that is not JSON or
    whose fields do not parse (:func:`_valid`) is skipped."""
    out: dict[str, dict] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            e = None
        if not isinstance(e, dict) or not _valid(e):
            log.warning("Skipping an unreadable line in %s", path)
            continue
        out[e["key"]] = e
    return out


def apply(path: Path, changes: dict[str, dict | None]) -> None:
    """Merge ``changes`` (key → entry, or None to remove) onto the file on disk
    and install it atomically. The read-merge-replace runs under an exclusive
    lock, so a concurrent writer's entries (and removals) survive."""
    if not changes:
        return
    lock = path.with_name(path.name + ".lock")
    with open(lock, "a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            entries = load(path)
            for k, e in changes.items():
                if e is None:
                    entries.pop(k, None)
                else:
                    entries[k] = e
            staged = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            staged.write_text(
                "".join(json.dumps(entries[k], sort_keys=True) + "\n"
                        for k in sorted(entries)),
                encoding="utf-8")
            os.replace(staged, path)
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def skip_until(entry: dict, today: date | None = None) -> date:
    today = today or _today()
    last = date.fromisoformat(str(entry["last_checked"])[:10])
    expired = date.fromisoformat(entry["expiry"]) < today
    confirmed = int(entry.get("n_checks", 1)) >= EXPIRED_CONFIRMED_CHECKS
    days = EXPIRED_CONFIRMED_DAYS if (expired and confirmed) else RECHECK_DAYS
    return last + timedelta(days=days)


def should_skip(entry: dict | None, today: date | None = None) -> bool:
    """True while ``entry`` is inside its TTL — skip the network call."""
    if entry is None:
        return False
    try:
        return (today or _today()) < skip_until(entry, today)
    except (KeyError, ValueError, TypeError):
        return False


def recorded(prior: dict | None, c: dict, reason: str) -> dict:
    """The entry after one more confirmation of ``c`` being unlisted."""
    stamp = datetime.now().replace(microsecond=0).isoformat()
    if prior is None:
        return new_entry(c, reason, stamp)
    return {**prior, "last_checked": stamp,
            "n_checks": int(prior.get("n_checks") or 0) + 1, "reason": reason}


@dataclass
class EvidenceTracker:
    """Holds each evidence outcome until it is shown not to be a fetch failure.

    Both kinds are DROPPED (never recorded, re-probed next run) when any fetch
    failure — network, HTTP, login, error, a session that would not open —
    lies within ``TROUBLE_WINDOW_S`` of them, either side. Beyond that:

    * HISTORY_PAGE_404 also needs a fetch that observed the feed (ok / no
      rows) within ``FEED_PROOF_WINDOW_S``, before or after. A 404 is an HTTP
      answer from Barchart's own server, so the network was up — but a route
      change or a URL-format regression would 404 EVERY contract with nothing
      in the run counting as trouble, and without the proof that run would
      record the whole universe. Unproven, it is re-probed next run, which
      costs little since a 404 returns at once. With proof, it is confirmed
      once the window after it has been observed, or at process exit
      (:func:`flush_at_exit`) if the window is clean up to the last event.
      A 404 page WITHOUT the logged-in marker (Barchart's 404 page
      may not render it) is recorded only if the same browser session was
      logged in earlier: it opened (``SESSION_OPEN`` — `BarchartSession`
      refuses to open unauthenticated), or it served a feed or a marked page.
    * HISTORY_NO_FEED — silence, not an answer — also needs a LATER 2xx page
      load and a fetch that observed the feed within ``FEED_PROOF_WINDOW_S``.
      Still pending at exit, it is dropped: the cost is one repeat probe.
    """
    events: list[tuple] = field(default_factory=list)    # (t, outcome, session, logged_in)
    pending: list[tuple] = field(default_factory=list)   # (t, contract, reason, session, logged_in, path)
    #: Confirmed before the events that proved them were trimmed; handed out by
    #: the next `confirmed()`. Without it a long run kept only its last hour of
    #: 404s: 206 of 277 were dropped on 2026-10-07.
    ready: list[tuple] = field(default_factory=list)     # (contract, reason, path)
    #: First time each session showed it was logged in. Kept apart from
    #: `events` so trimming never erases a login a later 404 leans on.
    logins: list[tuple] = field(default_factory=list)    # (session, t)

    def note(self, outcome: str | None, contract: dict | None = None,
             t: float | None = None, session: object = None,
             logged_in: bool | None = None, path: Path | None = None) -> None:
        t = _now() if t is None else t
        self.events.append((t, outcome, session, logged_in))
        if outcome in EVIDENCE and contract is not None:
            self.pending.append((t, contract, outcome, session, logged_in, path))
        if session is not None and (outcome in LOGGED_IN or logged_in is True) \
                and not any(s is session for s, _ in self.logins):
            self.logins.append((session, t))
        horizon = t - 2 * FEED_PROOF_WINDOW_S
        if self.events and self.events[0][0] < horizon:
            # Settle what the window can settle BEFORE dropping its events,
            # and keep every event a still-pending entry may yet need.
            self.ready.extend(self._qualify())
            cut = min([horizon] + [p[0] - FEED_PROOF_WINDOW_S for p in self.pending])
            self.events = [ev for ev in self.events if ev[0] >= cut]

    def _session_was_logged_in(self, session: object, t: float) -> bool:
        return session is not None and any(
            s is session and ts <= t for s, ts in self.logins)

    def confirmed(self, final: bool = False) -> list[tuple[dict, str, Path | None]]:
        """Pop ``(contract, reason, path)`` for pending entries that qualify,
        plus any settled earlier in the run.
        ``final`` = the process is ending: no later event will come."""
        out, self.ready = self.ready, []
        return out + self._qualify(final)

    def _qualify(self, final: bool = False) -> list[tuple[dict, str, Path | None]]:
        if not self.events:
            return []
        horizon = max(ev[0] for ev in self.events)
        out, keep = [], []
        for item in self.pending:
            t, c, reason, session, logged_in, path = item
            if any(abs(te - t) <= TROUBLE_WINDOW_S and o in TROUBLE
                   for te, o, _, _ in self.events):
                continue                                   # poisoned: drop
            if horizon < t + TROUBLE_WINDOW_S and not final:
                keep.append(item)                          # window not yet seen
                continue
            proof = any(abs(te - t) <= FEED_PROOF_WINDOW_S and o in FEED_PROOF
                        for te, o, _, _ in self.events)
            if reason == HISTORY_PAGE_404:
                if not (logged_in is True or self._session_was_logged_in(session, t)):
                    continue
                if proof:
                    out.append((c, reason, path))
                elif not final and horizon < t + FEED_PROOF_WINDOW_S:
                    keep.append(item)                      # proof may still come
                continue
            if final:
                continue                                   # NO_FEED dies unproven
            later_up = any(te > t and o in UP for te, o, _, _ in self.events)
            if later_up and proof:
                out.append((c, reason, path))
            elif horizon < t + FEED_PROOF_WINDOW_S:
                keep.append(item)                          # proof may still come
        self.pending = keep
        return out

    def reset(self) -> None:
        self.events.clear()
        self.pending.clear()
        self.ready.clear()
        self.logins.clear()


def commit(confirmed: list[tuple[dict, str, Path | None]], default_path: Path | None = None,
           changes: dict | None = None, known: dict | None = None) -> int:
    """Record ``confirmed`` entries. With ``changes`` (the caller's pending
    write for ``default_path``) they are merged into it; otherwise each is
    written straight to its own path. Returns the number recorded."""
    by_path: dict[Path, list] = {}
    for c, reason, path in confirmed:
        by_path.setdefault(path or default_path, []).append((c, reason))
    n = 0
    for path, items in by_path.items():
        if path is None:
            continue
        mine = changes is not None and path == default_path
        target = changes if mine else {}
        prior_src = (known or {}) if mine else load(path)
        for c, reason in items:
            cid = contract_id(c)
            target[cid] = recorded(target.get(cid, prior_src.get(cid)), c, reason)
            n += 1
        if not mine:
            apply(path, target)
    return n


def flush_at_exit() -> None:
    """Record the clean PAGE_404s still pending when the process ends — the
    last ~2 minutes of a run, which would otherwise be re-probed next time."""
    try:
        n = commit(TRACKER.confirmed(final=True))
        if n:
            log.info("%d contract(s) recorded as unlisted on Barchart at exit", n)
    except Exception:  # noqa: BLE001 — never fail an exit over a skip-list
        log.exception("Could not flush the unlisted-contract record at exit")


#: One per process: a proxy run opens a browser session per probe, and a
#: NO_FEED late in one probe is confirmed by the next probe's fetches.
TRACKER = EvidenceTracker()

atexit.register(flush_at_exit)
