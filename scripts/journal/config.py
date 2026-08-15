"""
Data contract for the daily trade journal — the ONE place its shapes are defined.

PRODUCTION TIER. Every other module under `scripts/journal/` reads its record
shapes and column order from here; nothing redefines them locally. The pipeline
is a chain of independently-runnable steps that hand each other these records:

    pull.py      broker  -> RawPull            (journal/raw/, immutable)
    reconcile.py RawPull -> list[PositionEvent]
    risk.py      + greeks -> list[PositionRisk]
    report.py    -> journal/reports/<date>.md
    page.py      -> site/journal-<date>.html
    writer.py    -> Sheets TradeJournal tab + journal/trades.csv
    recommend.py latest analysis + open book -> the deploy card
    recwriter.py the deploy card -> Sheets Recommendations tab
                 + journal/recommendations.csv

THE MISSING/ZERO INVARIANT. A greek of `None` means "the broker did not give us
one". A greek of `0.0` is a real, meaningful market value. These must never be
conflated: a position whose delta is unknown is EXCLUDED from the net
delta-notional total and listed separately, whereas a genuinely delta-neutral
position contributes a true zero. Never default a missing greek to 0.0, and
never sum over a list without first filtering on `delta_source`.

DATA PRIVACY. Everything this contract describes is real trading activity.
`journal/` is gitignored in full (raw pulls carry account identifiers;
trades.csv carries position sizes and P&L). Journal content has exactly THREE
permitted destinations: `journal/`, the Sheets tabs in
TRADE_JOURNAL_SPREADSHEET_ID, and `site/` — which page.py has always written
position sizes and P&L into, and which is gitignored for that reason
(.gitignore). Do not add a path under `journal/` or `site/` to version control,
and do not write journal content anywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------
# Paths — all gitignored (see .gitignore "journal/")
# --------------------------------------------------------------------------
JOURNAL_DIR = ROOT / "journal"
RAW_DIR = JOURNAL_DIR / "raw"          # immutable broker pulls, write-once
REPORTS_DIR = JOURNAL_DIR / "reports"  # <date>.md
TRADES_CSV = JOURNAL_DIR / "trades.csv"
RECOMMENDATIONS_CSV = JOURNAL_DIR / "recommendations.csv"
SITE_DIR = ROOT / "site"               # generated HTML, also gitignored

# Fallback analysis source when Sheets is unreachable — the same exports
# scripts/live_loop/stage1_map_fills.py already reads.
EVAL_DIR = ROOT / "backtests" / "to_evaluate"
AC_CSV_FALLBACK = EVAL_DIR / "analysis - AnalysisClaude.csv"

# --------------------------------------------------------------------------
# Sheets
# --------------------------------------------------------------------------
# Lives in TRADE_JOURNAL_SPREADSHEET_ID, NOT GOOGLE_SPREADSHEET_ID. The journal
# is deliberately a separate spreadsheet from the analysis book so it can be
# shared (or not shared) on its own.
TRADE_JOURNAL_TAB = "TradeJournal"
TRADE_JOURNAL_SPREADSHEET_ENV = "TRADE_JOURNAL_SPREADSHEET_ID"

# The deploy card's own record, in the SAME workbook as TRADE_JOURNAL_TAB: the
# two describe one loop (what was recommended, what was actually traded) and
# separating their workbooks would mean sharing one without the other.
RECOMMENDATIONS_TAB = "Recommendations"

# How many analysis sessions the dashboard's recommendations panel shows.
PAGE_RECENT_REC_SESSIONS = 3

# --------------------------------------------------------------------------
# Broker / pull
# --------------------------------------------------------------------------
# --- Flex, the transport --------------------------------------------------
# A Flex statement needs no local gateway and no daily browser login, but it
# carries neither greeks nor an open-positions section for a trades-only query.
# `flexparse` reconstructs the book by netting fills, so it needs EVERY year of
# export that a still-open position could have been entered in — a partial
# history silently yields a partial book. These are the files it reads by
# default; override with --from-flex.
FLEX_INPUT_DIR = ROOT / "portfolio" / "input"
FLEX_INPUT_GLOB = "trades_*.csv"

# Equity basis for the exposure caps. A Flex trades query carries no
# NetLiquidation field, so it comes from the environment (or --net-liq)
# instead — unless the OpenPositions query happens to carry a NAV section.
# Left unset, the risk section reports "not evaluable" rather than dividing
# by a guess.
NET_LIQUIDATION_ENV = "JOURNAL_NET_LIQUIDATION"

# Barchart is the greek source for the Flex path (see greeks.py). Cached per
# contract so a re-run of the same session costs no scraping.
GREEKS_CACHE_DIR = ROOT / "backtests" / "option_history_cache"

# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------
# deployment-rules.md §0 fixes the entry basis at the NEXT session's open, so a
# fill's signal date is normally the previous trading day. A play entered a day
# or two late is still that play, so we widen the search and record the lag
# rather than scoring it NONE.
SIGNAL_LOOKBACK_DAYS = 3

# ...but bounded in CALENDAR time as well. The lookback above counts dates the
# BOOK has, which is what makes holidays a non-issue — and also what makes an
# unbounded version dangerous: if the book has a gap (a prompt-version cut-over,
# a stretch where the pipeline did not run), "the 3 nearest prior analysis dates"
# can be years earlier, and a fill would be labelled with a signal date from a
# different era entirely. Any candidate older than this is not a plausible cause
# of today's trade, so it is dropped and the event is scored NONE.
MAX_SIGNAL_AGE_DAYS = 10

# The deploy card's staleness bound. ALIASED, not re-typed as another 10, and
# the distinction is worth keeping in view: MAX_SIGNAL_AGE_DAYS answers "could
# this analysis plausibly have CAUSED today's fill" (a backward, forensic
# question reconcile.py asks), while this answers "is this analysis still
# ACTIONABLE" (a forward one). They happen to coincide today, and there is a
# real argument they always should — an analysis too old to explain a trade is
# too old to justify one. If that argument ever breaks, split them here rather
# than editing the number above: tuning the matcher's window must not silently
# change when the card refuses to build.
RECOMMENDATION_MAX_AGE_DAYS = MAX_SIGNAL_AGE_DAYS

# Ranked best-first. DERIVED from scripts/live_loop/mapping.py rather than
# mirrored: the daily journal and the fortnightly audit assign these labels from
# the same `map_entry`, so a hand-kept copy here could only ever drift from it —
# and a category missing from this tuple vanishes silently out of every count
# that iterates it (report.py's tally, page.py's chart).
try:
    from scripts.live_loop.mapping import CONFIDENCES as MATCH_CONFIDENCES  # noqa: F401
except ImportError:  # pragma: no cover - alternate sys.path layout
    from live_loop.mapping import CONFIDENCES as MATCH_CONFIDENCES  # noqa: F401

# Confidences that mean "this fill was not an attempt to trade a play at all",
# so counting them as a miss would misdescribe the operator's discipline. Only
# OVERLAY qualifies: a financing/carry leg sold against a position already open.
NON_ATTEMPT_CONFIDENCES = ("OVERLAY",)

# --------------------------------------------------------------------------
# Risk
# --------------------------------------------------------------------------
ACCOUNT_SIM_YML = ROOT / "config" / "account-sim.yml"

# The caps come from config/account-sim.yml (`caps.per_position` 0.25,
# `caps.net` 2.50, as fractions of equity). That study calls them "a friction
# model, NOT a tuned parameter", which is exactly why they transfer to live use:
# nothing was fitted to P&L. What does NOT transfer is the study's $25k
# `account.capital` — live equity is the broker's NetLiquidation, so the caps
# here bind against the real account.
# `ibkr` is retained though nothing writes it any more: the Client Portal
# transport that did was removed on 2026-08-15, and every pull it left in
# journal/raw/ still replays through --from-raw. Dropping the name would make
# those pulls unreadable, and the deleted transport is not what the invariant
# below is about.
DELTA_SOURCE_IBKR = "ibkr"          # historical: Client Portal model greeks
DELTA_SOURCE_BARCHART = "barchart"  # per-contract EOD history (lib/barchart/options.py)
DELTA_SOURCE_UNAVAILABLE = "unavailable"

# Everything that is NOT `unavailable` is a real measurement and may enter the
# exposure totals. Membership is tested against this set rather than against one
# named source, so adding a third feed never silently drops positions out of the
# net delta figure — the failure mode would be an UNDERSTATED book, which is the
# single most dangerous way this pipeline could be wrong.
DELTA_SOURCES_REAL = frozenset({DELTA_SOURCE_IBKR, DELTA_SOURCE_BARCHART})

OPTION_MULTIPLIER = 100.0  # signed_dn = delta * 100 * contracts * underlying

# --------------------------------------------------------------------------
# Judgment call (the ONLY LLM surface in this pipeline)
# --------------------------------------------------------------------------
JUDGMENT_MODEL = "claude-opus-5"
JUDGMENT_MAX_ATTEMPTS = 3
JUDGMENT_TIMEOUT_S = 300

# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Leg:
    """One option leg of a reconstructed position, identified by conid.

    `qty` is SIGNED in contracts: positive long, negative short. `fill_price` is
    per share, as the broker reports it — multiply by OPTION_MULTIPLIER for cash.
    """

    conid: int
    symbol: str            # underlying ticker
    expiry: date
    strike: float
    right: str             # 'C' | 'P'
    qty: int
    fill_price: float
    # None means the export carried no commission column — NOT that the trade was
    # free. Same missing/zero rule as the greeks: a zero here would understate the
    # cost of every trade in a permanent record.
    commission: float | None
    exec_id: str
    fill_time: datetime    # UTC
    open_close: str        # 'O' | 'C' | '?'
    realized_pnl: float | None = None

    def leg_string(self) -> str:
        """This leg in the repo's canonical grammar: `TICKER:YYYY-MM-DD:STRIKE:C +N`.

        Deliberately the SAME grammar `scripts/backtest/legs.py` parses, so a
        journal row can be fed straight back through the backtest leg parser
        without a translation layer.
        """
        return (f"{self.symbol}:{self.expiry:%Y-%m-%d}:{self.strike:g}:"
                f"{self.right} {self.qty:+d}")


@dataclass(frozen=True)
class Greeks:
    """Per-contract greeks. `None` means ABSENT, never zero — see module docstring."""

    conid: int
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    iv: float | None = None
    underlying_price: float | None = None
    source: str = DELTA_SOURCE_UNAVAILABLE

    @property
    def has_delta(self) -> bool:
        return self.delta is not None and self.source in DELTA_SOURCES_REAL


@dataclass
class PositionEvent:
    """One reconstructed order group — the unit of a journal row.

    Produced by reconcile.py. `action` is OPEN / CLOSE / ROLL / PARTIAL, decided
    from the legs' open_close flags plus realized P&L, never from price signs.
    """

    date: str                 # trade date, YYYY-MM-DD
    trade_datetime_utc: str
    ticker: str
    structure: str            # canonical, e.g. bull_call_spread
    action: str
    legs: list[Leg] = field(default_factory=list)
    contracts: int = 0
    net_price: float = 0.0            # per-share, +debit / -credit
    commission: float | None = None   # None = not reported by the source, not free
    net_cash: float = 0.0             # signed account cash effect; excludes an
    #                                   unreported commission — the report says so
    realized_pnl: float | None = None
    dte_at_entry: float | None = None

    # --- analysis match (reconcile.py) ---
    signal_date: str | None = None
    entry_lag_days: int | None = None
    match_confidence: str = "NONE"
    ac_play: str | None = None
    ac_structure: str | None = None
    # The vertical at the centre of a financed multi-leg structure, when one
    # decomposes (mapping.core_structure). Carries the tier a "3-leg combo"
    # label cannot. Deliberately NOT in JOURNAL_COLUMNS — adding a column means
    # a TradeJournal header change; it is surfaced in `notes` instead.
    core_structure: str | None = None
    market_regime: str | None = None
    mech_cell: str | None = None

    # --- ladder (scripts/live_loop/mapping.ladder_tier) ---
    tier: str | None = None
    tier_reason: str | None = None
    tier_verified: bool = False       # False when the §3 delta gate was unchecked

    entry_slippage: float | None = None
    notes: str = ""
    source_ref: str = ""              # raw pull filename + sorted exec ids

    def legs_string(self) -> str:
        return " ".join(lg.leg_string() for lg in self.legs)

    def conid_key(self) -> str:
        """Stable identity for the position this event acts on.

        Sorted leg conids, so an OPEN and the CLOSE that later unwinds it share
        a key regardless of leg order or fill sequence. This is what a broker
        conid buys us that a price-matched reconstruction never could.
        """
        return "|".join(str(c) for c in sorted(lg.conid for lg in self.legs))


@dataclass
class PositionRisk:
    """An open position marked for exposure. Produced by risk.py."""

    conid_key: str            # sorted leg conids, the stable position identity
    ticker: str
    structure: str
    contracts: int
    legs: list[Leg] = field(default_factory=list)
    position_delta: float | None = None    # net delta across legs, per contract
    delta_notional: float | None = None    # signed_dn
    pct_net_liq: float | None = None
    underlying_price: float | None = None
    short_leg_delta: float | None = None   # feeds the §3 geometry gate
    iv: float | None = None
    delta_source: str = DELTA_SOURCE_UNAVAILABLE
    dte: float | None = None

    @property
    def priced(self) -> bool:
        """True when this position may enter the net delta-notional total."""
        return (self.delta_notional is not None
                and self.delta_source in DELTA_SOURCES_REAL)


@dataclass(frozen=True)
class RecContext:
    """Everything a deploy card knows about ITSELF, as opposed to about a play.

    Threaded from `cmd_recommend` into `recwriter.to_rows` so each persisted row
    can state not just what was recommended but what the card could SEE when it
    recommended it.

    `book_evaluable` is the load-bearing one. When no broker pull dated on or
    before the session exists, `rank()` is handed an empty BookRisk and stamps
    `duplicate_exposure=False` on every candidate — which reads as "not a
    duplicate" when the truth is "not checked". The field is a plain bool and
    cannot carry that distinction (widening it would ripple into
    scripts/backtest_study/live_select.py), so the WRITER resolves it: with
    `book_evaluable=False` it emits a blank cell rather than FALSE. Same
    missing/zero discipline the greeks get, applied at the serialisation seam.
    """

    session_date: str
    as_of_date: str
    staleness_days: int
    analysis_source: str = ""
    net_liq: float | None = None
    book_source: str = ""          # raw pull basename; "" when none qualified
    book_as_of: str = ""           # that pull's own trade_date
    book_evaluable: bool = False
    stale_override: bool = False
    judgment: dict | None = None
    judge_status: str = "not_run"  # not_run | ran | failed
    notes: str = ""
    generated_at: datetime | None = None   # injectable so tests are deterministic


# --------------------------------------------------------------------------
# Sheets / CSV column order — CHANGE IN ONE PLACE ONLY
# --------------------------------------------------------------------------
# Appending a column here means the TradeJournal tab HEADER must gain it too, or
# new rows write an unlabelled trailing column. `python3 scripts/align_tab_headers.py
# --dry-run` is the existing check for exactly this class of drift.
JOURNAL_COLUMNS = [
    "date",
    "trade_datetime_utc",
    "ticker",
    "structure",
    "action",
    "legs",
    "contracts",
    "net_price",
    "commission",
    "net_cash",
    "realized_pnl",
    "dte_at_entry",
    # analysis match
    "signal_date",
    "entry_lag_days",
    "match_confidence",
    "ac_play",
    "ac_structure",
    # ladder
    "tier",
    "tier_reason",
    "tier_verified",
    "entry_slippage",
    # risk
    "position_delta",
    "delta_notional",
    "pct_net_liq",
    "underlying_price",
    "short_leg_delta",
    "iv",
    "delta_source",
    # context
    "mech_cell",
    "market_regime",
    "notes",
    "source_ref",
]

# `source_ref` alone is globally unique (it carries the broker's exec ids), which
# is what makes a re-run of the same date append zero rows. date/ticker are in
# the key for readability when inspecting the _meta fingerprint.
DEDUP_KEY_COLS = ["date", "ticker", "source_ref"]


# --------------------------------------------------------------------------
# Recommendations — the deploy card's own record
# --------------------------------------------------------------------------
# One flat table covering all four roles a card assigns (deploy / hedge / veto /
# tier_c), so "what did the ladder refuse, and was it right" stays answerable
# from the same place as "what did it pick". Same append-at-end header rule as
# JOURNAL_COLUMNS: a column added here means the Recommendations tab HEADER
# must gain it too, or new rows write an unlabelled trailing column.
RECOMMENDATION_COLUMNS = [
    # --- when, and how far from the analysis it ranks -------------------
    "session_date",        # the analysis date the card ranks
    "as_of_date",          # the date the operator was standing on
    "generated_at_utc",
    "staleness_days",      # as_of_date - session_date, in calendar days
    # --- identity ------------------------------------------------------
    "rec_id",
    "generation",          # nth distinct card for this (session, role, ticker, structure)
    # --- what the deterministic ranker decided --------------------------
    "role",                # deploy | hedge | veto | tier_c
    "rank",                # 1-based within role; blank for veto/tier_c
    "deploy",              # top-DEPLOY_BUDGET flag, role=deploy only
    "ticker",
    "structure",
    "market_regime",       # the LABEL only; the full cell is a paragraph
    "tier",
    "tier_partial",
    "tier_reason",
    "score_total",
    "horizon",
    "play",                # the headline, not the full multi-line cell
    "trigger",
    "invalidation",
    "alternative_interpretation",
    "delta",
    "duplicate_exposure",  # blank (NOT False) when book_evaluable is False
    "headroom_ok",         # blank (NOT False) when not evaluable
    "headroom_note",
    "reasons",
    # --- what the model added, and what that is worth -------------------
    "judge_ran",
    "judge_status",        # not_run | ran | failed
    "judge_model",
    "trigger_verdict",
    "trigger_note",
    "alt_verdict",
    "alt_note",
    "demoted",
    "demote_reasons",
    "hedge_pick",
    "judge_lookahead_risk",
    # --- provenance -----------------------------------------------------
    "analysis_source",
    "book_source",         # the raw pull used, or blank
    "book_as_of",          # that pull's own trade_date
    "book_evaluable",
    "net_liq",
    "stale_override",
    "notes",
]

# Excluded from the content hash that forms `rec_id`. These three are the row's
# IDENTITY and its WALL CLOCK, not its content: including them would make every
# re-run look like a new recommendation and defeat the dedup entirely.
REC_IDENTITY_EXCLUDED = ("rec_id", "generation", "generated_at_utc")

# `rec_id` alone is globally unique (it ends in a content hash). session_date and
# ticker are in the key for readability when inspecting the _meta fingerprint —
# the same reason date/ticker are in DEDUP_KEY_COLS.
REC_DEDUP_KEY_COLS = ["session_date", "ticker", "rec_id"]

# Stamped on every row the judgment pass touched. JUDGMENT_MODEL's training
# cutoff OVERLAPS the analysis dates, so on a historical replay the model may be
# recalling an outcome rather than reading a setup. Nothing here can detect that
# — the column exists so a later reader can segregate judge-touched rows instead
# of discovering the contamination after building on them. Same concern
# scripts/backtest_study/live_select.py documents for its own judge layer.
JUDGE_LOOKAHEAD_NOTE = ("model cutoff may postdate session_date — verdicts on "
                        "historical sessions are not evidence")
