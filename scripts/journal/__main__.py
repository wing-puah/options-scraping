"""
Entry point for the daily trade journal.

    python3 -m scripts.journal                     fetch -> reconcile -> risk -> report -> write
    python3 -m scripts.journal --date 2026-08-14
    python3 -m scripts.journal pull                broker pull only
    python3 -m scripts.journal recommend           deploy card for the NEXT session
    python3 -m scripts.journal recommend --as-of 2026-08-15   replay a past morning
    python3 -m scripts.journal recommend --no-persist         print it, record nothing
    python3 -m scripts.journal --offline           read portfolio/input/ only, no network
    python3 -m scripts.journal --from-raw <path>   replay a past pull, no network
    python3 -m scripts.journal --dry-run           write nothing; show what it would write
    python3 -m scripts.journal --no-llm            deterministic only

DATA SOURCE. Flex, and only Flex — a statement fetched with `IBKR_FLEX_TOKEN`
by default, or read off disk with `--offline`. It needs no local software and
no daily login, which is the whole reason it is the transport; what it costs is
greeks (enriched from Barchart) and NetLiquidation (supply `--net-liq`).

THE CARD'S TIME BOUND. `recommend` is built AS OF a date (default today) and may
read nothing published after it — not a later analysis session, not a later
broker pull. Analysis older than RECOMMENDATION_MAX_AGE_DAYS is refused unless
`--allow-stale`; analysis dated AFTER the as-of date is refused unconditionally,
because that is lookahead rather than staleness. Every card is recorded to the
Recommendations tab and journal/recommendations.csv, append-only.

EXIT CODES. 0 success; 2 a usage/config problem, INCLUDING a broker pull this
pipeline will not stand behind, and an analysis book too old (or too new) to
build a deploy card from — an OpenPositions statement that declares a flat
book while the fills say otherwise is refused rather than journalled. A journal
recording an empty day because a source came back empty looks exactly like a day
you chose not to trade, and nothing about it prompts a second look. 3 the broker
refused us: a bad token, an unknown query, or the Flex Web Service's per-token
rate limit (error 1018), which a default run now meets far more often than the
old read-from-disk one did.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from dotenv import load_dotenv

from lib.ibkr.flex import FlexError

from . import analysis, book, flexparse, rawpull, report, risk, writer
from .config import (DOCS_DIR, FLEX_INPUT_DIR, FLEX_INPUT_GLOB,
                     NET_LIQUIDATION_ENV, RAW_DIR, REPORTS_DIR, ROOT)

# Repo convention: the entry point loads .env (see scripts/build_baseline.py,
# scripts/auth_drive.py). Without this, IBKR_FLEX_TOKEN / the two query ids /
# IBKR_ACCOUNT_ID / TRADE_JOURNAL_SPREADSHEET_ID never reach os.environ, and the
# default (fetching) run fails as though no token had ever been configured.
load_dotenv(ROOT / ".env")

log = logging.getLogger("journal")

EXIT_USAGE = 2
EXIT_BROKER = 3

# The Flex service's own code for "you have asked for too many statements".
# Named because the remedy is nothing like the other failures': wait, then
# re-run. Nothing is misconfigured.
FLEX_RATE_LIMITED = 1018


def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="python3 -m scripts.journal",
        description="Daily trade journal: what you traded, what proposed it, what you now hold.")
    p.add_argument("command", nargs="?", default="run",
                   choices=["run", "pull", "recommend"],
                   help="run (default) | pull | recommend")
    p.add_argument("--date", help="session to journal (YYYY-MM-DD); default today")
    p.add_argument("--from-raw", metavar="PATH",
                   help="replay an existing broker pull instead of calling the API")
    p.add_argument("--account", help="IBKR account id (default: IBKR_ACCOUNT_ID)")

    src = p.add_argument_group(
        "data source",
        "Flex, fetched with IBKR_FLEX_TOKEN by default: no local gateway, no daily "
        "browser login. It carries no greeks (Barchart fills them in) and no equity "
        "(see --net-liq).")
    src.add_argument("--from-flex", nargs="+", metavar="CSV",
                     help=f"Flex export file(s) to net the open book from; defaults to "
                          f"every {FLEX_INPUT_GLOB} in {FLEX_INPUT_DIR.name}/, which the "
                          "fetched statement is netted together with. Naming files here "
                          "implies --offline unless --flex-web is also passed")
    src.add_argument("--from-flex-positions", metavar="CSV",
                     help="Flex OpenPositions export; when given, the open book is "
                          "READ from it (a declared book) instead of reconstructed "
                          "by netting --from-flex fills, and the netted book "
                          "becomes a cross-check instead. Also implies --offline")
    src.add_argument("--flex-web", action=argparse.BooleanOptionalAction, default=None,
                     help="fetch the statement with IBKR_FLEX_TOKEN/"
                          "IBKR_FLEX_QUERY_TRADES_ID (and "
                          "IBKR_FLEX_OPEN_POSITIONS_QUERY_ID if set). On by default; "
                          "--no-flex-web reads only what is on disk")
    # SUPPRESS so this alias contributes no default of its own — the tri-state
    # (None = "decide from whether files were named") belongs to --flex-web.
    src.add_argument("--offline", dest="flex_web", action="store_false",
                     default=argparse.SUPPRESS,
                     help="alias for --no-flex-web: touch no broker network at all")
    src.add_argument("--net-liq", type=float, metavar="USD",
                     help=f"account equity for the exposure caps. A Flex trades query "
                          f"carries none; without it (or ${NET_LIQUIDATION_ENV}) the caps "
                          "report 'not evaluable' rather than guessing")
    src.add_argument("--no-greeks", action="store_true",
                     help="skip the Barchart greek fetch; positions stay unpriced and "
                          "the exposure totals are reported as a floor")
    rc = p.add_argument_group(
        "recommend",
        "The deploy card's time bound. Every card is built AS OF a date and may "
        "never read anything published after it.")
    rc.add_argument("--as-of", metavar="YYYY-MM-DD",
                    help="the day the card stands on (default today). Bounds BOTH the "
                         "analysis session and the broker book. Pair it with --date to "
                         "replay a past morning honestly: --date alone leaves as-of at "
                         "today, so an old session is correctly refused as stale")
    rc.add_argument("--allow-stale", action="store_true",
                    help="build the card even though the analysis is past the max-age "
                         "bound. Marked as stale on the card and on every persisted row. "
                         "Does NOT permit a session dated after --as-of; that is "
                         "lookahead and is always refused")
    rc.add_argument("--no-persist", action="store_true",
                    help="print the deploy card but record it nowhere")
    p.add_argument("--dry-run", action="store_true",
                   help="compute and report, but write nothing. (For `run` this also "
                        "skips saving the broker pull; for `recommend` it means the "
                        "card is printed and not recorded.)")
    p.add_argument("--no-llm", action="store_true", help="skip the judgment pass entirely")
    p.add_argument("--no-sheets", action="store_true", help="write the local CSV only")
    p.add_argument("--no-page", action="store_true", help="skip the HTML page")
    p.add_argument("--page-only", action="store_true",
                   help="rebuild the report and page from the newest pull; write nothing else")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)


def _latest_raw():
    """Newest pull on disk, for --page-only / a --from-raw with no path."""
    pulls = sorted(RAW_DIR.glob("ibkr-*.json")) if RAW_DIR.exists() else []
    return pulls[-1] if pulls else None


def _raw_on_or_before(session: str):
    """Newest pull whose trade_date is NOT AFTER `session`, or None.

    The deploy card's book picker, and the reason it exists is that
    `_latest_raw()` is a lookahead the moment you plan anything but today:
    ranking a past session against the newest pull on disk shows the card
    positions that were opened after that session, then reports cap headroom
    and duplicate exposure against them.

    The filename carries the trade date (`pull.raw_path`), so it prefilters
    cheaply — but the filename is a CONVENIENCE and `raw["trade_date"]` is the
    truth, so each candidate is confirmed after loading and skipped if the two
    disagree.
    """
    if not RAW_DIR.exists():
        return None
    for path in sorted(RAW_DIR.glob("ibkr-*.json"), reverse=True):
        stamp = path.stem.split("-")
        if len(stamp) >= 4 and "-".join(stamp[1:4]) > session:
            continue
        try:
            raw = rawpull.load(path)
        except Exception as exc:  # noqa: BLE001 - a bad pull is not this step's problem
            log.warning("Skipping unreadable pull %s (%s)", path.name, exc)
            continue
        trade_date = str(raw.get("trade_date") or "")
        if trade_date and trade_date > session:
            log.debug("Skipping %s — its trade_date %s is after the session %s",
                      path.name, trade_date, session)
            continue
        return path, raw
    return None


def _book_context(session: str):
    """`(book_risk, net_liq, provenance)` for a deploy card's session.

    Falls back to an EMPTY book rather than a newer one. That degradation is
    deliberate and must stay visible downstream: `rank()` derives duplicate
    exposure from the open book, so an empty book makes every candidate look
    un-duplicated. `provenance["evaluable"]` is what lets the card and the
    persisted rows say "not checked" instead of "clear".
    """
    found = _raw_on_or_before(session)
    if found is None:
        log.warning("No broker pull dated on or before %s — ranking WITHOUT cap "
                    "headroom or duplicate-exposure checks (they will be reported "
                    "as not evaluated, never as clear)", session)
        return risk.BookRisk(), None, {
            "evaluable": False, "source": "", "as_of": "",
            "note": "No broker pull dated on or before this session was available."}

    path, raw = found
    # Mark the book AT THE SESSION, not at date.today(): `as_of` drives DTE and
    # the expired-contract drop in book.open_positions, so today's date would
    # stamp a past-session card with today's DTE. cmd_run has always done this.
    book_risk, _, _ = _build_book(raw, date.fromisoformat(session))
    return book_risk, raw.get("net_liquidation"), {
        "evaluable": True, "source": path.name,
        "as_of": str(raw.get("trade_date") or ""), "note": ""}


def _use_web_service(args) -> bool:
    """Whether this invocation fetches, or reads only what is on disk.

    Fetching is the default: the exports in `portfolio/input/` go stale the
    moment a fill lands, and a journal quietly built from last month's book is
    the failure this pipeline exists to avoid. Naming files, though, is a
    statement of intent — an offline replay of a specific export — so it turns
    the fetch OFF unless `--flex-web` says otherwise explicitly.
    """
    if args.flex_web is not None:
        return args.flex_web
    return not (args.from_flex or args.from_flex_positions)


def _fetch(args) -> dict:
    """Get a pull from Flex, the pipeline's one transport — see _parse_args."""
    from . import pull as pull_mod

    return pull_mod.pull_flex(
        args.from_flex, trade_date=args.date, net_liquidation=args.net_liq,
        account_id=args.account, use_web_service=_use_web_service(args),
        enrich=not args.no_greeks, positions_source=args.from_flex_positions,
        # Keep the fetched statements beside the pull, so a parse that goes
        # wrong can still be looked at afterwards. Never in a dry run.
        statement_dir=None if args.dry_run else RAW_DIR)


def _load_raw(args) -> dict:
    """Get a validated pull, from disk or from the broker."""
    if args.from_raw:
        return rawpull.load(args.from_raw)
    if args.page_only:
        latest = _latest_raw()
        if latest is None:
            raise SystemExit("--page-only needs an existing pull in journal/raw/ — run a pull first")
        log.info("Rebuilding from %s", latest)
        return rawpull.load(latest)

    raw = _fetch(args)
    if not args.dry_run:
        from . import pull as pull_mod
        raw["_path"] = str(pull_mod.save(raw))
    return raw


def _build_book(raw: dict, as_of: date):
    """Open positions marked for exposure, plus the caps they are judged against.

    A missing NetLiquidation does not abort the run — the journal itself is still
    worth writing. It degrades the exposure section to 'not evaluable' and says
    so, rather than inventing an equity figure to divide by.
    """
    greeks = rawpull.greeks_map(raw)
    positions, notes = book.open_positions(raw, greeks, as_of=as_of)
    net_liq = raw.get("net_liquidation")
    if net_liq is None:
        log.error("No NetLiquidation in the pull — exposure caps cannot be evaluated")
        notes.append("NetLiquidation missing from the broker pull — the exposure caps could "
                     "not be evaluated. Position deltas below are still real.")
        return risk.BookRisk(positions=[p for p in positions if p.priced],
                             unpriced=[p for p in positions if not p.priced],
                             caps=None), positions, notes
    return risk.assess(positions, risk.load_caps(net_liq)), positions, notes


def cmd_run(args) -> int:
    raw = _load_raw(args)
    session = raw.get("trade_date") or args.date or date.today().isoformat()

    ac_df, ac_source = analysis.load()

    from . import reconcile as reconcile_mod
    events = reconcile_mod.reconcile(raw, ac_df)
    log.info("Reconciled %d position event(s) from %d fill(s)",
             len(events), len(raw.get("trades") or []))

    as_of = date.fromisoformat(session)
    book_risk, positions, notes = _build_book(raw, as_of)

    meta = {
        "date": session,
        "pull_source": raw.get("source"),
        "pull_file": raw.get("_path", "(unsaved — dry run)"),
        "analysis_source": ac_source,
        "net_liquidation": raw.get("net_liquidation"),
        "dropped_settlement": getattr(reconcile_mod, "LAST_DROPPED_SETTLEMENT", 0),
        "skipped_non_option": raw.get("skipped_non_option") or [],
        # Which book this pull carries. The report reads it to say whether the
        # non-option names it lists are unmodelled FILLS (netted book — all it
        # ever saw were trades) or unmodelled HOLDINGS (declared book).
        # Defaulting True on absence keeps every pre-existing pull's wording.
        "book_reconstructed": raw.get("book_reconstructed", True),
        "book_notes": notes + _source_caveats(raw),
        # The declared-vs-netted cross-check, classified into
        # not_cross_checkable / coverage_explained / unexplained (see
        # `flexparse._book_diff_warnings`). Absent on any pull written before
        # the cross-check was classified, so `.get()` and an empty default —
        # never a KeyError on replaying an older raw file.
        "book_diagnostics": raw.get("book_diagnostics") or {},
    }

    text = report.build(events, book_risk, meta)
    if not args.dry_run:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        log.info("Report written to %s", report.write(text, session))
    print(text)

    if not args.no_page and not args.dry_run:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        from . import page
        out = page.build(events, book_risk, meta, DOCS_DIR / f"journal-{session}.html")
        page.build(events, book_risk, meta, DOCS_DIR / "journal-latest.html")
        log.info("Page written to %s", out)

    if args.page_only:
        return 0

    summary = writer.write(
        events, {p.conid_key: p for p in positions}, raw.get("net_liquidation"),
        dry_run=args.dry_run, skip_sheets=args.no_sheets)
    log.info("Journal write: %s", summary)
    if summary.get("sheets_error"):
        # Not fatal: the local CSV already holds every row.
        log.warning("Sheets copy did not update (%s) — rows are safe locally",
                    summary["sheets_error"])
    return 0


def _source_caveats(raw: dict) -> list[str]:
    """What this pull's transport could NOT see, in the report's own words.

    A Flex statement is a smaller thing than a Client Portal pull, and the
    differences all bias the same way — towards a book that looks more complete
    and cheaper than it was. Stating them beside the numbers is the only thing
    that stops a reader treating the two sources as interchangeable.

    One line here is PROVENANCE rather than limitation. This list is rendered
    under "This pull could not see everything", and a declared book is the one
    thing on this transport that IS complete — leaving that unsaid invites the
    reader to discount the book along with everything else in the block, so it
    is stated positively and in one line.
    """
    notes = list(raw.get("book_warnings") or [])
    if raw.get("book_reconstructed") is False:
        notes.append(
            "Open positions are the broker's DECLARED OpenPositions book, read "
            "straight from the Flex statement — authoritative, not reconstructed. "
            "The trades export is only a cross-check on it; where the two "
            "disagree is reported separately, not treated as doubt about the book.")
    if raw.get("book_reconstructed"):
        span = raw.get("flex_span") or []
        window = f" from fills spanning {span[0]} to {span[1]}" if len(span) == 2 else ""
        notes.append(
            f"Open positions were RECONSTRUCTED by netting{window}, not read from a "
            "broker positions endpoint. A position entered before that window would "
            "be missing or understated.")
    if raw.get("commissions_included") is False:
        notes.append(
            "This export carries no commission column, so net prices and realized "
            "P&L below EXCLUDE commission. They are not the cash that hit the account.")
    return notes


def cmd_pull(args) -> int:
    from . import pull as pull_mod
    raw = _fetch(args)
    if args.dry_run:
        log.info("DRY RUN — pulled %d fill(s), %d open position(s); nothing written",
                 len(raw["trades"]), len(raw["positions"]))
        return 0
    print(pull_mod.save(raw))
    return 0


def cmd_recommend(args) -> int:
    from . import recommend as rec
    from . import recwriter
    from .config import RecContext

    ac_df, ac_source = analysis.load()
    # The day the card STANDS ON. Everything it may look at is bounded by this:
    # the analysis session below, and the broker book in _book_context.
    as_of = args.as_of or date.today().isoformat()
    try:
        date.fromisoformat(as_of)
    except ValueError:
        log.error("--as-of must be YYYY-MM-DD, got %r", as_of)
        return EXIT_USAGE

    # NOT analysis.latest_date(): that is unbounded, and would hand the card a
    # session published after the day it is planning for.
    session = args.date or analysis.latest_date_on_or_before(ac_df, as_of)
    if not session:
        log.error("No analysis rows dated on or before %s — nothing to recommend from",
                  as_of)
        return EXIT_USAGE

    try:
        staleness, stale_note = rec.check_freshness(
            session, as_of, allow_stale=args.allow_stale)
    except rec.StaleAnalysis as exc:
        log.error("%s", exc)
        return EXIT_USAGE

    book_risk, net_liq, prov = _book_context(session)

    candidates, rejected = rec.rank(ac_df, session, book_risk, net_liq)

    judged = None
    judge_status = "not_run"
    if not args.no_llm:
        context = _judgment_context(session, ac_source, book_risk)
        try:
            judged = rec.judge(candidates, context)
            judge_status = "ran" if judged.get("ran") else "failed"
        except Exception as exc:  # noqa: BLE001 - the card must stand without the model
            # The deterministic card IS the recommendation; the model only
            # annotates it. Losing the annotation must never lose the card.
            judge_status = "failed"
            log.warning("Judgment pass failed (%s) — printing the deterministic card", exc)

    # PRINT BEFORE PERSISTING. A disk error or a missing credential must never
    # cost you the card on screen — the record is a convenience, the card is the
    # product.
    print(rec.render(candidates, rejected, judged,
                     date=session, source=ac_source, net_liq=net_liq,
                     as_of=as_of, staleness_days=staleness, stale_note=stale_note,
                     book_evaluable=prov["evaluable"], book_note=prov["note"]))

    if args.no_persist:
        return 0

    notes = " ".join(n for n in (stale_note, prov["note"]) if n)
    ctx = RecContext(
        session_date=session, as_of_date=as_of, staleness_days=staleness,
        analysis_source=ac_source, net_liq=net_liq,
        book_source=prov["source"], book_as_of=prov["as_of"],
        book_evaluable=prov["evaluable"], stale_override=bool(args.allow_stale),
        judgment=judged, judge_status=judge_status, notes=notes)

    summary = recwriter.write(candidates, rejected, ctx,
                              dry_run=args.dry_run, skip_sheets=args.no_sheets)
    log.info("Recommendations: %d row(s) → CSV, %d → Sheets, %d already recorded",
             summary["csv_written"], summary["sheets_written"],
             summary["skipped_duplicate"])
    if summary.get("sheets_error"):
        log.warning("Sheets copy did not update (%s) — rows are safe locally",
                    summary["sheets_error"])
    return 0


def _judgment_context(session: str, ac_source: str, book_risk) -> str:
    """The situational text the judgment pass is allowed to reason over.

    Deliberately narrow: the date, where the analysis came from, and what is
    already open. It does NOT include tiers, scores or the ranking, because the
    model's job is to say whether each trigger has fired — not to re-rank a list
    the rules already ordered.
    """
    held = ", ".join(sorted({p.ticker for p in book_risk.positions})) or "none"
    lines = [f"Session being planned: {session}",
             f"Analysis source: {ac_source}",
             f"Tickers already held in the open book: {held}"]
    if book_risk.caps is not None:
        lines.append(f"Net delta-notional headroom: ${book_risk.net_headroom:,.0f}")
    if not book_risk.complete:
        lines.append(f"NOTE: {len(book_risk.unpriced)} open position(s) lack a broker "
                     "delta, so the exposure figures are a floor, not the full picture.")
    return "\n".join(lines)


def main(argv=None) -> int:
    args = _parse_args(argv)
    _setup_logging(args.verbose)
    try:
        if args.command == "pull":
            return cmd_pull(args)
        if args.command == "recommend":
            return cmd_recommend(args)
        return cmd_run(args)
    except rawpull.RawPullError as exc:
        log.error("Unusable broker pull: %s", exc)
        return EXIT_USAGE
    except flexparse.FlexParseError as exc:
        # A statement this pipeline will not stand behind. Loud and fatal on
        # purpose — see the EXIT CODES note in the module docstring.
        log.error("%s", exc)
        log.error("Refusing to write a journal from that pull.")
        return EXIT_USAGE
    except FlexError as exc:
        # The service said no. A traceback here would read like a bug in this
        # pipeline; every one of these is a condition at IBKR's end, and the
        # rate limit in particular just wants a few minutes and a re-run.
        log.error("%s", exc)
        if exc.code == FLEX_RATE_LIMITED:
            log.error("The Flex token is rate-limited — wait a few minutes and "
                      "re-run, or use --offline to journal from the exports in "
                      "portfolio/input/ meanwhile.")
        return EXIT_BROKER


if __name__ == "__main__":
    sys.exit(main())
