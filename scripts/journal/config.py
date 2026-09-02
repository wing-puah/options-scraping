"""
Data contract for the daily trade journal — the ONE place its shapes are defined.

PRODUCTION TIER. Every other module under `scripts/journal/` reads its record
shapes and column order from here; nothing redefines them locally. The pipeline
is a chain of independently-runnable steps that hand each other these records:

    s01_pull.py       broker  -> RawPull            (journal/raw/, immutable)
    s02_reconcile.py  RawPull -> list[PositionEvent]
    s03_risk.py       + greeks -> list[PositionRisk]
    s04a_report.py    -> journal/reports/<date>.md
    s04b_page.py      -> site/journal-<date>.html
    s05_writer.py     -> Sheets TradeJournal tab + journal/trades.csv
    s05b_bookwriter.py the open book -> Sheets OpenBook tab
                      + journal/open_book.csv
    s06_recommend.py  latest analysis + open book -> the deploy card
    s07_recwriter.py  the deploy card -> Sheets Recommendations tab
                      + journal/recommendations.csv

The `sNN_` prefix IS the running order — the package listing reads as the
pipeline. Everything those steps lean on lives under `scripts/journal/lib/`
(see its `__init__.py`), so nothing unnumbered sits beside the flow.

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
TRADE_JOURNAL_SPREADSHEET_ID, and `site/` — which s04b_page.py has always written
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
OPEN_BOOK_CSV = JOURNAL_DIR / "open_book.csv"
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

# The OPEN BOOK's own record, again in the SAME workbook: TradeJournal says what
# you traded, Recommendations what was proposed, OpenBook what you are HOLDING
# right now and which of those holdings wants attention. The third tab exists
# because the first two answer neither question — a journal row describes a
# trade at the moment it happened and is never revisited, so nothing in it tells
# you that a position opened five weeks ago is now past its §5 exit date.
OPEN_BOOK_TAB = "OpenBook"

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

# Barchart is the greek source for the Flex path (see lib/greeks.py). Cached per
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
# question s02_reconcile.py asks), while this answers "is this analysis still
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
# that iterates it (s04a_report.py's tally, s04b_page.py's chart).
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

# The §5 time-exit fraction is read from the backtest config at run time
# (lib/exit_rules.py) so the journal's printed exit-by dates can never drift
# from the rule the research tier actually replays.
BACKTEST_YML = ROOT / "config" / "backtest.yml"

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
# Open-book triage — what "amiss" means, in one place
# --------------------------------------------------------------------------
# The OpenBook tab exists to be SCANNED, so every row carries a `status` and a
# `flags` cell derived from the numbers beside it. The derivation is here rather
# than in the writer so the vocabulary is greppable and a reader of the tab can
# find the definition of a token they are looking at.
#
# THESE ARE ATTENTION THRESHOLDS, NOT RULES. Nothing downstream reads a verdict
# off a flag: the caps still bind in s03_risk.py, the §5 deadline is still
# computed in lib/exit_rules.py, and colouring a row WATCH neither loosens nor
# tightens either. Changing a number below changes what gets NOTICED, never
# what is true — which is why they are allowed to be round numbers with no
# backtest behind them, unlike anything in docs/deployment-rules.md.
EXIT_DUE_SOON_DAYS = 5        # §5 deadline this close (or closer) → WATCH
EXPIRING_SOON_DTE = 7         # contract expiry this close → WATCH
CAP_NEAR_UTILISATION = 0.80   # this share of a cap used → WATCH

# Severity per flag. ATTENTION = something is wrong or unknown NOW; WATCH = it
# will be soon, or the picture is incomplete; INFO = worth knowing while reading
# the row, but not a problem (it must never move `status`).
BOOK_FLAG_SEVERITY = {
    # --- ATTENTION -------------------------------------------------------
    "EXPIRED": "ATTENTION",              # dte < 0: still in the book past expiry
    "EXIT_OVERDUE": "ATTENTION",         # §5 deadline is in the past
    "UNPRICED_NO_DELTA": "ATTENTION",    # excluded from every exposure total
    "UNPRICED_NO_SPOT": "ATTENTION",     # delta known, cannot be valued
    "TICKER_CAP_BREACH": "ATTENTION",
    "NET_CAP_BREACH": "ATTENTION",
    # --- WATCH -----------------------------------------------------------
    "EXIT_DUE_SOON": "WATCH",
    "EXPIRING_SOON": "WATCH",
    "TICKER_CAP_NEAR": "WATCH",
    "NET_CAP_NEAR": "WATCH",
    "CAPS_NOT_EVALUABLE": "WATCH",       # no NetLiquidation — no cap context
    "MIXED_ENTRY_DATES": "WATCH",        # §5 clock started at the earliest leg
    "UNCLASSIFIED_STRUCTURE": "WATCH",   # the classifier could not name it
    # --- INFO ------------------------------------------------------------
    "SPLIT_EXPIRY": "INFO",              # a calendar/diagonal shown as two rows
    "EXIT_DATE_UNKNOWN": "INFO",         # debit whose entry date is unprovable
}


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

    Produced by s02_reconcile.py. `action` is OPEN / CLOSE / ROLL / PARTIAL, decided
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

    # --- analysis match (s02_reconcile.py) ---
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
    """An open position marked for exposure. Produced by s03_risk.py."""

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
    # §5 time-exit display fields (lib/exit_rules.py) — DISPLAY-ONLY. None means
    # unknown/not applicable, never "no deadline yet"; nothing downstream may
    # read a risk verdict off them.
    entry_date: date | None = None         # earliest opening fill across legs
    exit_by: date | None = None            # entry + 0.75×(expiry−entry), debits only
    entry_date_mixed: bool = False         # legs opened on different dates

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
    scripts/backtest_study/lib/live_select.py), so the WRITER resolves it: with
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


@dataclass(frozen=True)
class BookContext:
    """Everything an open-book snapshot knows about ITSELF, not about a position.

    The mirror of `RecContext`, for the same reason: a row that states its own
    provenance can be judged a year later without the pull it came from. The
    load-bearing fields are `book_reconstructed` (a netted book can be SHORT a
    position entered before the export window — its absence is not evidence of
    a flat book) and `net_liq` (absent, the caps cannot be evaluated at all and
    every row says so rather than showing a utilisation against a guess).
    """

    as_of_date: str                     # the date the book is marked AT
    net_liq: float | None = None
    book_source: str = ""               # raw pull basename
    book_reconstructed: bool = True     # False = the broker's declared book
    snapshot_at: datetime | None = None  # injectable so tests are deterministic
    notes: str = ""


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
    # --- projections (append-at-end; the tab header must gain these too) --
    # Play-shaped fields sitting after the provenance block because the tab is
    # positional and the schema only ever grows at the end. Both derive purely
    # from fields already hashed above (as_of_date + play/horizon), hence their
    # place in REC_IDENTITY_EXCLUDED below.
    "exit_by_earliest",    # §5 projected time-exit deadline, conservative end
    "exit_by_latest",      # same projection at the far end of the DTE range
]

# Excluded from the content hash that forms `rec_id`: the row's IDENTITY, its
# WALL CLOCK, and fields derived ENTIRELY from hashed ones. Including the first
# two would make every re-run look like a new recommendation; the derived
# fields cannot move unless a hashed field moves, so hashing them would only
# force a one-time generation bump on every already-recorded card.
REC_IDENTITY_EXCLUDED = ("rec_id", "generation", "generated_at_utc",
                         "exit_by_earliest", "exit_by_latest")

# `rec_id` alone is globally unique (it ends in a content hash). session_date and
# ticker are in the key for readability when inspecting the _meta fingerprint —
# the same reason date/ticker are in DEDUP_KEY_COLS.
REC_DEDUP_KEY_COLS = ["session_date", "ticker", "rec_id"]

# Stamped on every row the judgment pass touched. JUDGMENT_MODEL's training
# cutoff OVERLAPS the analysis dates, so on a historical replay the model may be
# recalling an outcome rather than reading a setup. Nothing here can detect that
# — the column exists so a later reader can segregate judge-touched rows instead
# of discovering the contamination after building on them. Same concern
# scripts/backtest_study/lib/live_select.py documents for its own judge layer.
JUDGE_LOOKAHEAD_NOTE = ("model cutoff may postdate session_date — verdicts on "
                        "historical sessions are not evidence")


# --------------------------------------------------------------------------
# Open book — what you are holding, and what wants attention
# --------------------------------------------------------------------------
# One row per OPEN POSITION per snapshot. Same append-at-end header rule as
# JOURNAL_COLUMNS and RECOMMENDATION_COLUMNS: a column added here means the
# OpenBook tab HEADER must gain it too, or new rows write an unlabelled
# trailing column.
#
# COLUMN ORDER IS THE POINT. The tab is read left to right on a phone, so the
# order is "what do I need to know about this position", nearest first:
# `status` and `flags` (what is amiss), then the position's exposure and its
# deadline — `delta_notional` and `exit_by` are the two numbers the operator
# acts on — then the ticker total the cap actually binds on, then the detail
# behind the mark, and the identity/provenance columns LAST. Nothing that is a
# fact about the whole BOOK rather than this position is written: the net cap,
# the book counts, NetLiquidation and the pull's caveats live in the report
# and the page, and reach this tab only as a flag on the rows they concern
# (NET_CAP_*, CAPS_NOT_EVALUABLE, SPLIT_EXPIRY). Repeating them on every row
# was the original layout, and it made the tab unreadable.
OPEN_BOOK_COLUMNS = [
    # --- when, and what is wrong ---------------------------------------
    "as_of_date",           # the session the book is marked AT
    "status",               # ATTENTION | WATCH | OK — worst flag on the row
    "flags",                # "; "-joined tokens; BOOK_FLAG_SEVERITY defines them
    # --- the position: exposure and deadline first ----------------------
    "ticker",
    "structure",
    "delta_notional",       # signed dollars; BLANK when unpriced, never 0
    "pct_net_liq",
    "exit_by",              # §5 deadline, debits only (lib/exit_rules.py)
    "days_to_exit_by",      # negative = overdue
    "expiry",
    "dte",
    # --- what the cap binds on: the TICKER's signed total -----------------
    "ticker_delta_notional",
    "ticker_cap_utilisation",   # |ticker total| / per-position cap; >1 = breach
    # --- the detail behind the mark --------------------------------------
    "contracts",
    "legs",                 # canonical grammar, same as JOURNAL_COLUMNS.legs
    "entry_date",
    "position_delta",
    "underlying_price",
    "short_leg_delta",
    "iv",
    "priced",               # False = the delta cells above are blank on purpose
    "delta_source",
    # --- identity and provenance, last -----------------------------------
    "book_id",              # readable prefix + content hash of the row
    "generation",           # nth distinct mark of this position on this date
    "conid_key",            # sorted leg conids — the stable position identity
    "book_source",          # raw pull basename
    "snapshot_utc",
]

# Excluded from the content hash that forms `book_id`: the row's IDENTITY and
# its WALL CLOCK, exactly as REC_IDENTITY_EXCLUDED excludes them. Everything
# else is hashed — including the marks, which is deliberate: a re-run on the
# same day with the same greeks appends nothing, while a genuinely re-marked
# book appends a new generation instead of overwriting the earlier mark.
BOOK_IDENTITY_EXCLUDED = ("book_id", "generation", "snapshot_utc")

# `book_id` alone is globally unique (it ends in a content hash). as_of_date and
# ticker are in the key for readability when inspecting the _meta fingerprint —
# the same reason date/ticker are in DEDUP_KEY_COLS.
BOOK_DEDUP_KEY_COLS = ["as_of_date", "ticker", "book_id"]
