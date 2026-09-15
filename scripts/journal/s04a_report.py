"""
Step 4a — render the day's journal as fixed-width markdown.

PRODUCTION TIER, pure rendering. Takes exactly what `s02_reconcile.py` and `s03_risk.py`
already produced (`list[PositionEvent]`, `BookRisk`) plus a small `meta` dict the
caller assembles from `s01_pull.py`/`lib/analysis.py`'s own return values, and turns them
into `journal/reports/<date>.md`. No network, no Sheets, no broker calls, and no
statistic this module did not receive — a single day's fills do not support a
win rate or an annualised anything.

`meta` is a plain dict, not a dataclass, because the four keys this module reads
are the only contract it needs and every one is optional-with-a-fallback: a
caller missing one still gets a report, just with the corresponding line stating
plainly that the information was not recorded rather than fabricating a zero.

    date              str    trade date, YYYY-MM-DD
    pull_source       str    e.g. "ibkr-cpapi" (RawPull.source)
    pull_file         str    path to the immutable raw pull this ran from
    analysis_source   str    'sheets' | a CSV path | 'none' (analysis.load()'s
                              own second return value) — anything other than
                              'sheets' triggers the loud stale-fallback line
    net_liquidation   float  account equity the exposure caps bind against
    dropped_settlement  list  optional — zero-price settlement rows the
                                reconcile step dropped before entry reconstruction
    skipped_non_option  list  optional — non-option fills the pull step counted
                                but did not carry through (see s01_pull.py)

Money renders with thousands separators; deltas to 3dp; percentages as
percentages (the repo stores share-type fractions as decimals — 0.045, not
4.5 — EXCEPT `iv`, which per repo convention stays in points). `None` renders as
an em dash and is never confused with a genuine 0.0 (the missing/zero invariant
in config.py) — every formatter below checks `is None`, never truthiness.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .config import (CAP_NEAR_UTILISATION, OPTION_MULTIPLIER, REPORTS_DIR,
                     MATCH_CONFIDENCES, NON_ATTEMPT_CONFIDENCES, PositionEvent)
from .s03_risk import BookRisk
from .lib import exit_rules

EM_DASH = "—"


# --------------------------------------------------------------------------
# Formatting — the missing/zero invariant lives here, in ONE place, so every
# section renders None and 0.0 the same (distinct) way. Shared with s04b_page.py so
# the two never quietly drift into disagreeing about what a number looks like.
# --------------------------------------------------------------------------
def em(v) -> str:
    return EM_DASH if v is None else str(v)


def money(v: float | None, *, signed: bool = False) -> str:
    if v is None:
        return EM_DASH
    sign = "-" if v < 0 else ("+" if signed and v > 0 else "")
    return f"{sign}${abs(v):,.2f}"


def delta3(v: float | None) -> str:
    """3dp. A genuine 0.0 renders `0.000`, never an em dash — see config.py."""
    return EM_DASH if v is None else f"{v:.3f}"


def pct(v: float | None, digits: int = 1) -> str:
    """`v` is a decimal fraction (0.045 = 4.5%), per the repo-wide convention."""
    return EM_DASH if v is None else f"{v * 100:.{digits}f}%"


def iv_fmt(v: float | None, digits: int = 2) -> str:
    """IV is the one share-type field the repo keeps in POINTS, not a fraction."""
    return EM_DASH if v is None else f"{v:.{digits}f}%"


def num(v: float | None, digits: int = 1) -> str:
    return EM_DASH if v is None else f"{v:.{digits}f}"


def isodate(v) -> str:
    """A date cell. None means unknown/not applicable — em dash, never a guess."""
    return EM_DASH if v is None else v.isoformat()


def cell(s: str | None) -> str:
    """Make a string safe to place inside a markdown table cell.

    Analysis play text is pipe-delimited by construction
    (`PATTERN | structure | thesis`), so dropping it into a table raw splits one
    cell into four and silently misaligns every column after it — the tier and
    confidence end up under the wrong headers. Newlines do the same to rows.
    """
    s = (s or "").replace("\n", " ").replace("\r", " ")
    return s.replace("|", "\\|")


def truncate(s: str | None, n: int = 70) -> str:
    """Shorten for display. Escapes pipes/newlines too — every caller is a table cell."""
    s = cell(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def _pct_net_liq(delta_notional: float | None, pct_net_liq: float | None,
                 net_liq: float | None) -> float | None:
    """Prefer a value the caller already set on the record; else derive it here
    the same way s05_writer.py's `to_row` does (s03_risk.py never populates the field
    itself, so most callers reach this branch)."""
    if pct_net_liq is not None:
        return pct_net_liq
    if delta_notional is not None and net_liq:
        return delta_notional / net_liq
    return None


# --------------------------------------------------------------------------
# build()
# --------------------------------------------------------------------------
def build(events: list[PositionEvent], book: BookRisk, meta: dict) -> str:
    lines: list[str] = []

    def emit(line: str = "") -> None:
        lines.append(line)

    date = meta.get("date") or ""
    net_liq = meta.get("net_liquidation")
    analysis_source = meta.get("analysis_source")

    emit(f"# Trade Journal — {date or EM_DASH}")
    emit("")
    emit("_Generated by `scripts/journal/report.py` (pure rendering, no network)._")
    emit("")

    try:
        report_day = dt.date.fromisoformat(str(date))
    except ValueError:
        report_day = None

    # ================= AT A GLANCE =================
    for line in _at_a_glance(book, net_liq, report_day):
        emit(line)

    # ================= 1. HEADER =================
    emit("## 1. Header")
    emit("")
    emit(f"- **Date:** {date or EM_DASH}")
    emit(f"- **Pull source:** `{meta.get('pull_source') or EM_DASH}` · "
         f"`{meta.get('pull_file') or EM_DASH}`")
    if analysis_source == "sheets":
        emit("- **Analysis source:** sheets (live book)")
    elif analysis_source in (None, "none"):
        emit("- **Analysis source:** NONE — no analysis book was available "
             "(Sheets unreachable and no CSV fallback on disk)")
    else:
        emit(f"- **Analysis source:** CSV fallback `{analysis_source}`")
    emit(f"- **Account NetLiquidation:** {money(net_liq)}")
    emit("")
    if analysis_source not in ("sheets",):
        emit("> **⚠ STALE ANALYSIS SOURCE.** Matches in §3 below come from "
             f"`{analysis_source or 'no analysis at all'}`, NOT the live Sheets book. "
             "Treat every match/tier/confidence in this report as provisional until "
             "it is re-run against the live book.")
        emit("")
    if net_liq is None:
        emit("> **⚠ NO NetLiquidation.** Exposure caps and every %-of-NetLiq figure "
             "below cannot be evaluated.")
        emit("")

    # What this pull's SOURCE could not see. Sits in the header rather than a
    # footnote because it qualifies the numbers a reader meets first — a
    # reconstructed book and a broker-reported one are not the same claim, and
    # nothing further down the report would tell them apart.
    caveats = [c for c in (meta.get("book_notes") or []) if c]
    if caveats:
        emit("> **⚠ SOURCE LIMITS.** This pull could not see everything:")
        for note in caveats:
            emit(f"> - {cell(note)}")
        emit("")

    # ================= 2. TODAY'S ACTIVITY =================
    emit("## 2. Today's activity")
    emit("")
    if not events:
        emit("No position events today.")
        emit("")
    else:
        emit("| Ticker | Structure | Action | Legs | Contracts | Net Price | "
             "Commission | Realized P&L |")
        emit("|--------|-----------|--------|------|-----------|-----------|"
             "------------|---------------|")
        for e in events:
            emit(f"| {cell(e.ticker)} | {cell(e.structure)} | {cell(e.action)} | "
                 f"{cell(e.legs_string())} | "
                 f"{e.contracts} | {money(e.net_price, signed=True)} | "
                 f"{money(e.commission)} | {money(e.realized_pnl, signed=True)} |")
        emit("")
        emit(f"**{len(events)} position event(s) today.**")
        emit("")

    # ================= 3. ANALYSIS MATCH =================
    emit("## 3. Analysis match")
    emit("")
    if not events:
        emit("No events to match this run.")
        emit("")
    else:
        emit("| Ticker | Signal Date | Entry Lag | Confidence | Matched Play | "
             "Tier | Tier Reason | Tier Basis |")
        emit("|--------|-------------|-----------|------------|--------------|"
             "------|-------------|------------|")
        for e in events:
            lag = f"{e.entry_lag_days}d" if e.entry_lag_days is not None else EM_DASH
            play = truncate(e.ac_play, 70) if e.ac_play else EM_DASH
            basis = "VERIFIED" if e.tier_verified else "unverified"
            emit(f"| {cell(e.ticker)} | {e.signal_date or EM_DASH} | {lag} | "
                 f"{e.match_confidence} | {play} | {e.tier or EM_DASH} | "
                 f"{cell(e.tier_reason) or EM_DASH} | {basis} |")
        emit("")
        # Displayed tally: every event, OPEN and CLOSE alike — this is the
        # per-confidence breakdown of what the match layer said about today's
        # rows, not the attempt count below.
        tally = {c: sum(1 for e in events if e.match_confidence == c)
                 for c in MATCH_CONFIDENCES}
        emit("**Confidence tally:** "
             + ", ".join(f"{k}={v}" for k, v in tally.items()) + ".")
        # ATTEMPT POPULATION IS OPEN EVENTS ONLY. A CLOSE now matches too (the
        # P1 orientation fix), and it names the play the group UNWINDS — not a
        # second attempt to trade it. Counting every event as an attempt makes
        # a same-play open+close report 2/2 for what was ONE attempt. An
        # OVERLAY was never an attempt either — a financing leg sold against a
        # position already open — and stays excluded from both sides of the
        # ratio, same as before.
        opens = [e for e in events if e.action == "OPEN"]
        attempt_tally = {c: sum(1 for e in opens if e.match_confidence == c)
                         for c in MATCH_CONFIDENCES}
        not_attempts = sum(attempt_tally.get(c, 0) for c in NON_ATTEMPT_CONFIDENCES)
        attempts = len(opens) - not_attempts
        matched = sum(v for k, v in attempt_tally.items()
                      if k != "NONE" and k not in NON_ATTEMPT_CONFIDENCES)
        emit(f"**{matched}/{attempts} play attempt(s) matched an analysis play** "
             f"({attempt_tally['EXACT']} EXACT, {attempt_tally['STRUCTURE']} STRUCTURE "
             f"traded the emitted play; {attempt_tally['CORE']} CORE traded it as the "
             f"core of a financed structure; {attempt_tally['SUBSTITUTED']} SUBSTITUTED "
             f"traded a different, same-direction structure; {attempt_tally['NONE']} "
             "unmatched) (attempts counted on OPEN events only).")
        if not_attempts:
            emit(f"**{not_attempts} financing/carry overlay(s)** excluded from the "
                 "ratio above — sold against a position already open, never a "
                 "play attempt.")
        emit("")

    # ================= 4. OPEN BOOK =================
    emit("## 4. Open book")
    emit("")
    all_positions = list(book.positions) + list(book.unpriced)
    if not all_positions:
        emit("No open positions.")
        emit("")
    else:
        emit("| Ticker | Structure | Contracts | DTE | Position Delta | "
             "Delta-Notional | % NetLiq | Underlying Px | IV | Exit by |")
        emit("|--------|-----------|-----------|-----|-----------------|"
             "-----------------|----------|----------------|-----|---------|")
        for p in sorted(all_positions, key=lambda p: (p.ticker, p.structure)):
            pnl = _pct_net_liq(p.delta_notional, p.pct_net_liq, net_liq)
            exit_cell = isodate(p.exit_by) + ("\\*" if p.entry_date_mixed
                                              and p.exit_by is not None else "")
            if (p.exit_by is not None and report_day is not None
                    and p.exit_by < report_day):
                exit_cell += " ⚠ OVERDUE"
            emit(f"| {p.ticker} | {p.structure} | {p.contracts} | {num(p.dte, 1)} | "
                 f"{delta3(p.position_delta)} | {money(p.delta_notional, signed=True)} | "
                 f"{pct(pnl)} | {money(p.underlying_price)} | {iv_fmt(p.iv)} | "
                 f"{exit_cell} |")
        emit("")
        emit(f"**{len(all_positions)} open position(s)** "
             f"({len(book.positions)} priced, {len(book.unpriced)} excluded — see §5).")
        emit("")
        tef = exit_rules.time_exit_fraction()
        if tef is None:
            emit("> `Exit by`: the §5 debit time exit is DISABLED in "
                 "config/backtest.yml (`time_exit_dte_fraction: null`) — no "
                 "dates are computed.")
        else:
            emit(f"> `Exit by` = entry + {tef:.0%} of the entry-to-expiry span "
                 "(`deployment-rules.md` §5), a DEADLINE — exit on or before it. "
                 "Blank on a credit spread (credits carry no time exit) and blank "
                 "where the entry date is not provable from any export we hold. "
                 "\\* = the legs were opened on different dates; the earliest is used.")
        emit("")

    # ================= 5. EXPOSURE =================
    emit("## 5. Exposure")
    emit("")
    caps = book.caps
    emit(f"- Net delta-notional: {money(book.net_delta_notional, signed=True)}")
    emit(f"- Gross delta-notional: {money(book.gross_delta_notional)}")
    if caps is not None:
        emit(f"- Per-position cap: {money(caps.per_position_dollars)} "
             f"({caps.per_position:.2f}x equity)")
        emit(f"- Net cap: {money(caps.net_dollars)} ({caps.net:.2f}x equity)")
        emit(f"- Net utilisation: {pct(book.net_utilisation)}")
        emit(f"- Net headroom: {money(book.net_headroom)}")
    else:
        emit("- Caps: NOT LOADED — NetLiquidation was unavailable, so the "
             "per-position and net delta-notional caps could not be evaluated. "
             "The dollar totals above carry no cap context.")
    emit(f"- Positions excluded (no delta): {len(book.unpriced)}")
    emit("")
    # The per-ticker table that used to sit here moved to AT A GLANCE at the
    # top: it is the view the operator acts on, and it was buried under the
    # whole open book.
    if book.ticker_exposure and caps is not None:
        emit("Per-ticker exposure, cap use and overage: see **At a glance** at the top.")
        emit("")
    emit(f"**{len(book.breaches)} breach(es).**")
    if book.breaches:
        emit("")
        for b in book.breaches:
            emit(f"- {b}")
    emit("")
    if not book.complete:
        emit("> **⚠ INCOMPLETE BOOK — FLOOR, NOT THE REAL EXPOSURE.** "
             f"{len(book.unpriced)} position(s) are excluded from every total above "
             "for want of a delta (see §6). The net/gross delta-notional and "
             "utilisation figures are therefore a FLOOR on the book's true exposure, "
             "never the complete picture — do not size a new position off "
             "`net_headroom` while this holds.")
        emit("")
    else:
        sources = sorted({p.delta_source for p in book.positions if p.delta_source})
        # Name the source rather than saying "broker": on the Flex path these are
        # Barchart END-OF-DAY greeks, not live broker model greeks, and a reader
        # sizing a position off this needs to know which one they are looking at.
        via = f" (via {', '.join(sources)})" if sources else ""
        emit(f"Book is **complete** — every open position carries a delta{via}, "
             "so the totals above are the whole exposure, not a floor.")
        emit("")

    # ================= 6. NOT COVERED =================
    for line in _not_covered(book, meta):
        emit(line)

    return "\n".join(lines)


def _ticker_summaries(book: BookRisk, net_liq: float | None,
                      report_day: dt.date | None) -> list[dict]:
    """One summary per ticker, over priced AND unpriced positions.

    Totals come from `book.ticker_exposure` — the figure `assess()` checked the
    cap against — so this table and the breach list can never disagree about a
    ticker. Everything else is arithmetic on those totals or read off the
    positions. A ticker with an unpriced position keeps its partial total and
    says how many positions it is missing; a ticker with only unpriced
    positions has no total at all, never a zero.
    """
    caps = book.caps
    cap = caps.per_position_dollars if caps is not None else None
    by_ticker: dict[str, list] = {}
    for p in list(book.positions) + list(book.unpriced):
        by_ticker.setdefault(p.ticker, []).append(p)

    rows = []
    for ticker, members in by_ticker.items():
        priced = [p for p in members if p.priced]
        total = book.ticker_exposure.get(ticker) if priced else None
        if priced and total is None:
            # A BookRisk built without assess() (caps missing) has no
            # ticker_exposure; sum what is priced rather than show nothing.
            total = sum(p.delta_notional for p in priced)
        shares = (sum(p.position_delta * OPTION_MULTIPLIER for p in priced)
                  if priced else None)
        spot = next((p.underlying_price for p in members
                     if p.underlying_price is not None), None)
        util = abs(total) / cap if total is not None and cap else None
        excess = abs(total) - cap if util is not None and util > 1 else None
        room = cap - abs(total) if util is not None and util <= 1 else None
        if caps is None:
            status = "CAPS N/A" if priced else "UNPRICED"
        elif not priced:
            status = "UNPRICED"
        elif excess is not None:
            status = "BREACH"
        elif util >= CAP_NEAR_UTILISATION:
            status = "NEAR"
        else:
            status = "OK"
        exits = [p.exit_by for p in members if p.exit_by is not None]
        next_exit = min(exits) if exits else None
        rows.append(dict(
            ticker=ticker, status=status, shares=shares, total=total,
            pct_net_liq=(total / net_liq if total is not None and net_liq else None),
            util=util, excess=excess,
            excess_shares=(excess / spot if excess is not None and spot else None),
            room=room, next_exit=next_exit,
            overdue=(next_exit is not None and report_day is not None
                     and next_exit < report_day),
            members=sorted(members, key=lambda p: -abs(p.delta_notional or 0.0)),
            unpriced_n=len(members) - len(priced)))

    order = {"BREACH": 0, "NEAR": 1, "OK": 2, "CAPS N/A": 2, "UNPRICED": 3}
    rows.sort(key=lambda r: (order[r["status"]], -(r["util"] or 0.0),
                             -abs(r["total"] or 0.0), r["ticker"]))
    return rows


def _at_a_glance(book: BookRisk, net_liq: float | None,
                 report_day: dt.date | None) -> list[str]:
    """The per-ticker view the operator acts on, first thing in the report.

    Deliberately worded so none of its lines match the figures
    `s04b_page.extract_report_figures()` reads out of §5 (no
    "Net delta-notional:", no "**N breach(es).**"): the page parses the first
    match, and two copies of a number are two chances to disagree.
    """
    rows = _ticker_summaries(book, net_liq, report_day)
    caps = book.caps
    out = ["## At a glance", ""]
    if not rows:
        out += ["No open positions.", ""]
        return out

    net = (book.net_delta_notional if caps is not None
           else sum(p.delta_notional for p in book.positions if p.priced))
    parts = [f"**NetLiq** {money(net_liq)}"]
    if caps is not None:
        parts.append(f"**Book Δ$** {money(net, signed=True)} of "
                     f"{money(caps.net_dollars)} net cap ({pct(book.net_utilisation)})")
        parts.append(f"**Per-ticker cap** {money(caps.per_position_dollars)}")
        over = [r for r in rows if r["status"] == "BREACH"]
        net_over = abs(net) > caps.net_dollars
        parts.append(f"**Tickers over cap:** {len(over)}"
                     + (" · **NET CAP BREACHED**" if net_over else ""))
    else:
        parts.append(f"**Book Δ$** {money(net, signed=True)} (caps not loaded)")
    overdue = sum(1 for p in list(book.positions) + list(book.unpriced)
                  if p.exit_by is not None and report_day is not None
                  and p.exit_by < report_day)
    parts.append(f"**Exits overdue:** {overdue}")
    out += [" · ".join(parts), ""]

    out.append("| Ticker | Status | Δ Shares | Delta-Notional | % NetLiq | % of Cap | "
               "Over Cap By | Room Left | Next Exit-by | Positions |")
    out.append("|--------|--------|----------|----------------|----------|----------|"
               "-------------|-----------|--------------|-----------|")
    for r in rows:
        shares = EM_DASH if r["shares"] is None else f"{r['shares']:+.1f}"
        if r["excess"] is None:
            over = EM_DASH
        else:
            over = f"**{money(r['excess'])}**"
            if r["excess_shares"] is not None:
                over += f" (≈{r['excess_shares']:.1f} Δ sh)"
        exit_cell = isodate(r["next_exit"]) + (" ⚠ OVERDUE" if r["overdue"] else "")
        members = "; ".join(
            f"{p.structure} {p.delta_notional:+,.0f}" if p.priced
            else f"{p.structure} (no delta)"
            for p in r["members"])
        status = f"**{r['status']}**" if r["status"] == "BREACH" else r["status"]
        out.append(
            f"| {cell(r['ticker'])} | {status} | {shares} | "
            f"{money(r['total'], signed=True)} | {pct(r['pct_net_liq'])} | "
            f"{pct(r['util'])} | {over} | {money(r['room'])} | {exit_cell} | "
            f"{cell(members)} |")
    out.append("")
    notes = [f"`Δ Shares` = share-equivalent delta (Σ position delta × {OPTION_MULTIPLIER:g}); "
             "`Over Cap By` ≈ Δ sh is how much share-equivalent delta must come off "
             "to get back under the cap."]
    if caps is not None:
        notes.append(f"`NEAR` = at least {CAP_NEAR_UTILISATION:.0%} of the per-ticker cap.")
    if not book.complete:
        notes.append("⚠ Some positions have no delta — their tickers' totals are a "
                     "FLOOR (see §5).")
    out += ["> " + " ".join(notes), ""]
    return out


def _tally_line(label: str, items, describe=str) -> str:
    """One '- **label (n):** a, b.' bullet, distinguishing 0 from NOT MEASURED.

    `None` means the upstream step never reported the figure; `[]` means it
    reported none. Collapsing those two into "0" would claim a check was run
    that never was — the exact failure §6 exists to prevent.
    """
    if items is None:
        return f"- **{label}:** not recorded for this run (the upstream step did not report it)."
    if not items:
        return f"- **{label}:** 0."
    return f"- **{label} ({len(items)}):** " + ", ".join(describe(x) for x in items) + "."


def _contract_of(diagnostic: str) -> str:
    """The contract a book-diagnostic line is about, without its explanation.

    Each line reads `"SYM 32.0C 2027-01-15 (conid 728924541): <why>"`. Only the
    identifier is wanted where the `<why>` is identical across every item in the
    bucket. Falls back to the whole string if the shape ever changes — better a
    long line than a silently truncated one.
    """
    head = str(diagnostic).split(":", 1)[0]
    return head.split(" (conid", 1)[0].strip() or str(diagnostic)


def _not_covered(book: BookRisk, meta: dict) -> list[str]:
    """§6 — everything the pipeline did not, or could not, do.

    Split out of `build()` so each bullet is one call rather than one branch;
    the section is the report's conscience and is easiest to audit on its own.
    """
    def pos(p):
        return f"{p.ticker} {p.structure}"

    no_delta = [p for p in book.unpriced if p.position_delta is None]
    no_spot = [p for p in book.unpriced
               if p.position_delta is not None and p.underlying_price is None]

    all_positions = list(book.positions) + list(book.unpriced)
    no_entry_date = [p for p in all_positions if p.entry_date is None]
    mixed_entry = [p for p in all_positions if p.entry_date_mixed]

    # What "skipped_non_option" names depends on which book this pull carries.
    # A reconstructed book only ever saw FILLS, so a non-option name there is a
    # trade this pipeline does not model. A DECLARED book is a statement of
    # holdings, so the same field there names a position that is genuinely open
    # and genuinely unmodelled — a stronger claim, and the one the operator
    # needs. Labelling both "fills" would understate the second.
    non_option_label = ("Non-option fills skipped" if meta.get("book_reconstructed", True)
                        else "Non-option positions held (not modelled)")

    # The declared-vs-netted book cross-check, DEMOTED here from §1. A saved
    # Flex trades query covers a far shorter period than a position's life, so
    # most disagreements say only "the export cannot see back that far" — a
    # coverage statement, not a discrepancy, and 28 of them at the top of the
    # report drown the one that would matter. `unexplained` is the finding;
    # the other two buckets are counted so the check is visibly still running.
    # Absent (an older raw pull, or the netted path) means never measured, and
    # `_tally_line` says so rather than printing a reassuring 0.
    diag = meta.get("book_diagnostics") or {}
    return [
        "## 6. Not covered",
        "",
        _tally_line("Dropped settlement rows", meta.get("dropped_settlement")),
        _tally_line(non_option_label, meta.get("skipped_non_option")),
        _tally_line("Positions with no delta", no_delta, pos),
        _tally_line("Symbols with no spot price", no_spot, pos),
        _tally_line("Open positions with no entry date (§4 exit-by not "
                    "computable)", no_entry_date, pos),
        _tally_line("Open positions whose legs were opened on different dates",
                    mixed_entry, pos),
        # The two EXPLAINED buckets are named by contract only. Their full
        # sentences all say the same thing — "the export's window is shorter
        # than the position's life" — so printing 28 copies of it here would
        # just move the §1 wall of text rather than remove it. The UNEXPLAINED
        # bucket keeps its full wording: it is the actual finding, and it is
        # normally empty.
        _tally_line("Book cross-check: declared positions the trades export "
                    "cannot see (no fill in its window)",
                    diag.get("not_cross_checkable") if diag else None, _contract_of),
        _tally_line("Book cross-check: differences explained by a gap in export "
                    "coverage",
                    diag.get("coverage_explained") if diag else None, _contract_of),
        _tally_line("Book cross-check: differences NOT explained — a missing "
                    "fill or a corporate action",
                    diag.get("unexplained") if diag else None),
        "",
    ]


def write(text: str, date: str) -> Path:
    """Write the report to `journal/reports/<date>.md`. Overwrites on re-run —
    the report is a rendering of the day's events, not evidence, so re-running
    the pipeline for the same date is expected to refresh it."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{date}.md"
    path.write_text(text, encoding="utf-8")
    return path
