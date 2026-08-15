"""
Step 1 — pull the day's fills, the open book, equity and greeks from IBKR.

PRODUCTION TIER. The ONLY module in this package that touches the network or
imports `lib.ibkr`; everything downstream reads the normalised file this writes
(see `rawpull.py`). Swapping broker transport is a change here and nowhere else.

ONE TRANSPORT. `pull_flex()` reads a Flex statement — fetched with a token
(`lib.ibkr.flex`, the default) or read off disk from an export the operator
produces by hand. It needs no local software and no daily login, and NEVER has
greeks. Whether it has a declared open-positions section depends on whether a
second query (`IBKR_FLEX_OPEN_POSITIONS_QUERY_ID` / `--from-flex-positions`) is
configured: with it, the book is the declared one and the netted-from-fills book
is only a cross-check; without it, the book is RECONSTRUCTED by netting fills
(`flexparse`). Delta is always enriched from Barchart (`greeks`) either way.
What this path cannot see, it says: see `book_warnings`.

The Client Portal Gateway transport was removed on 2026-08-15 — it needed a
locally-run, browser-logged-in gateway for greeks and NetLiquidation that
Barchart and `--net-liq` now supply. Pulls it wrote (`source: ibkr-cpapi`) still
replay through `--from-raw`; nothing about the v1 schema changed.

FAILING LOUD IS THE POINT. Every failure mode here is designed to be noisy: a
journal that records "no trades today", or a flat book, because a source came
back empty is worse than no journal at all — it looks like evidence, it reads
like a flat day, and nothing about it invites a second look.

WHAT IS AND IS NOT PULLED. Options only. Stock and other non-option fills are
counted and named in `skipped_non_option` rather than dropped in silence — the
book carries stock positions (e.g. CSPX) that this pipeline does not model, and
the difference between "you had none" and "we did not look" must stay visible.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from . import flexparse, rawpull
from .config import FLEX_INPUT_DIR, FLEX_INPUT_GLOB, GREEKS_CACHE_DIR, RAW_DIR

log = logging.getLogger(__name__)


def raw_path(trade_date: str, now: datetime | None = None):
    """`journal/raw/ibkr-<date>-<HHMM>.json`. The timestamp keeps pulls immutable:
    a second pull on the same day is a NEW file, never an overwrite."""
    now = now or datetime.now(timezone.utc)
    return RAW_DIR / f"ibkr-{trade_date}-{now:%H%M}.json"


# --------------------------------------------------------------------------
# Flex — the transport
# --------------------------------------------------------------------------
def flex_sources(explicit=None, *, statement=None) -> list:
    """The export files to net the open book from, newest last.

    Defaults to EVERY `trades_*.csv` in `portfolio/input/` rather than just the
    current year. A position entered in a prior year and still open is
    invisible to a single-year export, and the netted book would be quietly
    short by exactly that position — the failure this ordering avoids.

    `statement` is a freshly fetched statement to net TOGETHER with that
    history, not instead of it. A saved Flex query has a fixed period, and the
    common ones ("Last Business Day", "Month to Date") are far shorter than the
    life of an open position; since the book is netted from fills, a short
    statement does not merely understate a position, it omits every position it
    did not touch. Netting it with the yearly exports fixes that without the
    operator re-scoping the query, and costs nothing when the query is already
    wide — `parse()` dedupes on TradeID, so the overlap collapses.

    Missing exports are fatal WITHOUT a statement (there would be nothing to
    read) and merely narrowing WITH one — that pull is still valid, and
    `flexparse` records the narrower window in `book_warnings`.
    """
    if explicit:
        # Only strings become paths. `flexparse.parse` also accepts in-memory CSV
        # (a StringIO), which is how a token-fetched statement and every test
        # reach it; coercing those to Path would break both.
        on_disk = [Path(p) if isinstance(p, str) else p for p in explicit]
    else:
        on_disk = sorted(FLEX_INPUT_DIR.glob(FLEX_INPUT_GLOB))

    if not on_disk:
        if statement is None:
            raise FileNotFoundError(
                f"No Flex export found at {FLEX_INPUT_DIR}/{FLEX_INPUT_GLOB}. Export one "
                "from IBKR (Reporting > Flex Queries) or pass --from-flex <path>.")
        log.info("No local export to widen the statement with — the book will be "
                 "netted from the statement's own window only")
        return [statement]

    if statement is None:
        return on_disk
    log.info("Netting the statement together with %d local export(s): %s",
             len(on_disk), ", ".join(str(getattr(p, "name", p)) for p in on_disk))
    return [*on_disk, statement]


def _save_statement(directory, kind: str, text: str, now: datetime | None = None):
    """Keep a fetched statement verbatim beside the pull, or do nothing.

    A fetched statement is otherwise unrecoverable: the pull records what was
    PARSED out of it, so when the parse is the thing in question there is no
    evidence left to look at. That is exactly how the 2026-08-15 empty-book
    failure became un-diagnosable after the fact. `journal/` is gitignored in
    full, so these carry no further than the machine.

    `directory=None` writes nothing — how `--dry-run` and the tests stay
    side-effect free.
    """
    if directory is None:
        return None
    now = now or datetime.now(timezone.utc)
    ext = "xml" if text.lstrip().startswith("<") else "csv"
    path = Path(directory) / f"flex-{now:%Y-%m-%d-%H%M}-{kind}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    log.info("Saved the fetched %s statement to %s", kind, path)
    return path


def pull_flex(sources=None, *, use_web_service: bool,
              trade_date: str | None = None,
              net_liquidation: float | None = None, account_id: str | None = None,
              enrich: bool = True,
              as_of: date | None = None, positions_source=None,
              statement_dir=None) -> dict:
    """Build a validated pull from a Flex statement.

    `use_web_service` has NO default on purpose. Fetching is the CLI's default
    (`__main__._use_web_service`), so a default of False here would be the
    opposite of what the pipeline does, and a new in-process caller that simply
    omitted it would silently journal from whatever stale exports happen to be
    in `portfolio/input/` — the exact failure the CLI default exists to
    prevent. Making it explicit costs one keyword and removes the trap.

    `use_web_service=True` fetches the statement with `IBKR_FLEX_TOKEN` /
    `IBKR_FLEX_QUERY_TRADES_ID` and nets it TOGETHER with the exports on disk,
    rather than instead of them — see `_web_sources` for why a saved query's
    period is usually too short to reconstruct an open book from on its own.
    Either way the parse, the netting and the enrichment are identical, so a
    token run and a hand-exported run produce the same journal from the same
    fills.

    `positions_source` is the declared OpenPositions statement — a path, or
    `None` for the offline default of "no declared book, reconstruct one".
    When `use_web_service` is on and `positions_source` was not already given,
    AND `IBKR_FLEX_OPEN_POSITIONS_QUERY_ID` names a second saved query, a
    second handshake is run through the SAME `FlexClient` (one token, one
    session) to fetch it — the positions query is entirely optional, so its
    absence is not an error, only the reconstruction path this pipeline always
    had. An explicit `positions_source` (the `--from-flex-positions` path)
    always wins over the web fetch, for the same offline-replay reason
    `--from-flex` wins over `--flex-web` for trades.

    `statement_dir` is where a fetched statement is kept verbatim — see
    `_save_statement`. None (the default) writes nothing.

    `enrich=False` skips the Barchart greek fetch. The pull is still valid and
    still writes a journal; every position simply stays `delta_source=
    unavailable`, and the report labels the exposure totals a FLOOR rather than
    counting an absent delta as zero.
    """
    statement = None
    if use_web_service:
        from lib.ibkr.flex import (FlexClient, positions_query_id_from_env,
                                   trades_query_id_from_env)
        log.info("Fetching Flex statement via the web service (no gateway needed)")
        client = FlexClient()
        trades_text = client.fetch()
        _save_statement(statement_dir, "trades", trades_text)
        statement = io.StringIO(trades_text)
        statement.name = "the Flex web-service statement"

        if positions_source is None:
            positions_query_id = positions_query_id_from_env()
            if positions_query_id and positions_query_id == trades_query_id_from_env():
                # ONE query saved with BOTH sections: the statement already in
                # hand is the declared book too. Fetching it again would be a
                # second handshake for a byte-identical answer — and the section
                # split happens in `flexparse`, which reads each reader's own
                # section out of the one text.
                log.info("The OpenPositions query IS the trades query (%s) — "
                         "reading both sections from the one statement",
                         positions_query_id)
                positions_source = io.StringIO(trades_text)
                positions_source.name = "the Flex web-service statement"
            elif positions_query_id:
                log.info("Fetching the OpenPositions statement via the web "
                         "service (query %s)", positions_query_id)
                positions_text = client.fetch(query_id=positions_query_id)
                _save_statement(statement_dir, "positions", positions_text)
                positions_source = io.StringIO(positions_text)
                positions_source.name = "the Flex web-service OpenPositions statement"

    parsed = flexparse.parse(flex_sources(sources, statement=statement),
                             trade_date=trade_date, net_liquidation=net_liquidation,
                             account_id=account_id, positions_source=positions_source)

    if not enrich:
        log.warning("Skipping the greek enrichment — every position will be "
                    "unpriced and the exposure totals will be a floor")
        return parsed

    from . import greeks as greeks_mod
    return greeks_mod.enrich(parsed, as_of=as_of or date.fromisoformat(parsed["trade_date"]),
                             cache_dir=GREEKS_CACHE_DIR)


def save(raw: dict, path=None):
    """Write the pull immutably and return its path."""
    path = path or raw_path(raw["trade_date"])
    written = rawpull.save(raw, path)
    log.info("Wrote broker pull to %s (%d fill(s), %d open position(s))",
             written, len(raw["trades"]), len(raw["positions"]))
    return written
