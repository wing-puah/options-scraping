"""The CONCENTRATION series and its trigger — `hedge_exposure`'s independent
variable.

Implements the Arms section of
`research/pre-registrations/f4_deployment/hedge_exposure.md`: the per-session
open-book reconstruction, the per-cluster signed delta-notional, the
concentration measure the committed tau grid is applied to, the
DIRECT/CONSTITUENT stratification the study's binding asymmetric reading rule
needs, the hedge-flow signal ARM CS conditions on, and the power census gate
G-CENSUS prints and gate G-POWER reads.

This module computes NOTHING about outcomes. No P&L, no drawdown, no hedge
instrument, no fill, no verdict — those belong to the arms module. What it
answers is only: *on which sessions was the book concentrated, in what, and
was that concentration DIRECT or CONSTITUENT.*

--- The lookahead line, drawn explicitly (gate G-BLIND) ----------------------
There are two layers here and only one of them is the trigger.

  1. OCCUPANCY (`open_book_by_session`) — WHICH positions are open on a
     session. This consumes `days_held`, which is an outcome field: the book
     being replayed already happened, and how long a position was held is part
     of how it resolved. That is legitimate here for the same reason a
     counterfactual overlay is legitimate at all: the study asks what an
     overlay would have done to a book that was already traded, so the book's
     own path is the fixture, not a signal. It is NOT a decision the trigger
     is allowed to make.

  2. TRIGGER (`session_concentration` and everything downstream) — GIVEN the
     open set, how concentrated it is. This reads only entry-dated fields:
     `ticker`, `delta`, `contracts`, `entry_underlying`. It never reads
     `realized_pnl_pct`, `exit_reason`, `mfe`/`mae`, `days_held`, or anything
     dated after the session.

The two are kept apart in the code, not merely in the docstring: occupancy is
returned as INDICES into the caller's record list, so the trigger layer can be
re-run over the identical occupancy with `account_sim.blind_records` applied.
`blind_trigger_check()` does exactly that and reports whether the triggered
session set is identical, which is what G-BLIND asks for.

--- `days_held` is a TRADING-day index, and the pre-registration's session
    universe was computed on the CALENDAR reading -------------------------
`harness.replay` returns `days_held=i` where `i` is the 1-based position in
`Trade.grid`, and `_weekday_grid` is "weekdays AFTER the signal date". So the
field counts WEEKDAY sessions held, and `account_sim` reads it that way
(`exit_sess = t.grid[min(days_held, len(grid)) - 1]`).

The pre-registration's session universe, however, is stated as
`[signal_date, signal_date + days_held]` — a CALENDAR span — and that reading
is what reproduces its committed figures exactly: 504 sessions, the per-cluster
exposure table, the quantiles, and the trigger census. The trading-day reading
gives 551 sessions on the same book. Both are implemented (`HOLDING_CALENDAR`,
`HOLDING_TRADING`); the DEFAULT is `HOLDING_CALENDAR`, because that is the
population the pre-registration committed to and a study may not quietly run on
a different one. `holding_disagreement()` reports the gap so it is visible in
the report rather than buried here.

--- A missing greek is None, never 0.0 --------------------------------------
`signed_delta_notional` returns None — NOT 0.0 — when `delta` or
`entry_underlying` is absent, and such a position is excluded from BOTH the
per-cluster numerator and the book-gross denominator, with the count carried on
every `SessionConcentration`. This deliberately DIVERGES from
`account_sim.signed_dn`, which returns 0.0 for the same input: there a zero
merely fails to consume cap headroom, here a zero would silently shrink the
denominator of the study's independent variable and move the trigger.
"""
from __future__ import annotations

import re
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.parsing import to_float  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import sectors  # noqa: E402
from scripts.backtest_study.lib import underlying as und  # noqa: E402

# ════════════════════════════════════════════════════════════════════════════
# Committed constants — fixed in the pre-registration, not tunable here
# ════════════════════════════════════════════════════════════════════════════

#: The tau grid. 3 tau x 3 f = 9 cells; "No post-hoc threshold search."
TAU_GRID: tuple[float, ...] = (0.30, 0.35, 0.40)

#: The risk fractions, carried here so one module owns the committed grid.
F_GRID: tuple[float, ...] = (0.25, 0.50, 1.00)

#: G-POWER: a cell below this many trigger DATES is UNDERPOWERED and carries no
#: verdict. UNDERPOWERED is not a lean.
MIN_TRIGGER_DATES = 25

#: ARM CS's hedge-flow condition. The parsed median is 35, so >= 50 is the
#: upper ~third of parsed dates.
HEDGE_PRESSURE_CUT = 50

#: The committed extraction regex, verbatim. A date with no parse is NO SIGNAL.
HEDGE_PRESSURE_RE = re.compile(
    r"hedge[- ]pressure[^0-9]{0,15}(\d{1,3})\s*/\s*100", re.IGNORECASE)

#: Which reading of `days_held` bounds a position's open span. See the module
#: docstring: CALENDAR is the pre-registration's, TRADING is the field's own.
HOLDING_CALENDAR = "calendar"
HOLDING_TRADING = "trading"
HOLDINGS = (HOLDING_CALENDAR, HOLDING_TRADING)

#: Which concentration series a trigger reads. ANY is the pre-registration's
#: primary measure; CONSTITUENT is the operator's literal practice, registered
#: as a stratum to report and expected to be power-stopped.
MEASURE_ANY = "any"
MEASURE_CONSTITUENT = "constituent"
MEASURES = (MEASURE_ANY, MEASURE_CONSTITUENT)

#: The session calendar. Weekdays alone over-count by the market holidays in
#: the book's span; the OHLC cache for this ticker is the repo's own record of
#: which weekdays actually traded, and using it is what makes the calendar
#: reading land on the pre-registration's 504 sessions rather than 525.
SESSION_CALENDAR_TICKER = "SPY"

#: A top cluster at least this much of whose gross exposure sits in the proxy
#: instrument itself makes the session DIRECT. NOT a pre-registered number —
#: the pre-registration names the two strata but does not define the cut. A
#: simple majority is the least surprising operationalisation and the raw
#: share is carried on every session (`top_direct_share`) so a reader can
#: re-cut it without re-running anything.
DIRECT_MAJORITY = 0.50


class SessionCalendarMissing(RuntimeError):
    """No session calendar on disk — the concentration series is not
    computable, and falling back to bare weekdays would silently change the
    population from the pre-registration's 504 sessions."""


# ════════════════════════════════════════════════════════════════════════════
# Session calendar
# ════════════════════════════════════════════════════════════════════════════

_SESSIONS_CACHE: frozenset[date] | None = None


def trading_sessions() -> frozenset[date]:
    """Every date the market actually traded, from the underlying OHLC cache.

    Refuses rather than degrading: `backtests/underlying_ohlc_cache/` is
    restored by `scripts/backup_research_caches.py pull`, and a study that
    quietly substituted weekdays for sessions would report a different session
    universe under the same name.
    """
    global _SESSIONS_CACHE
    if _SESSIONS_CACHE is None:
        bars = und.load_bars(SESSION_CALENDAR_TICKER)
        if not bars:
            raise SessionCalendarMissing(
                f"no bars for {SESSION_CALENDAR_TICKER} in {und.OHLC_CACHE} — "
                f"run `python3 scripts/backup_research_caches.py pull` (or "
                f"`scripts/collector/fetch_underlying_ohlc.py`) before this study.")
        _SESSIONS_CACHE = frozenset(bars)
    return _SESSIONS_CACHE


# ════════════════════════════════════════════════════════════════════════════
# Per-position exposure — entry-dated only
# ════════════════════════════════════════════════════════════════════════════

def default_contracts(rec) -> int:
    """The book's own contract count for `rec` (`Trade.contracts`).

    This is what the pre-registration's plan-time census was computed on. A
    caller running the concentration series against `account_sim`'s SIZED book
    passes its own `contracts_fn` instead; the measure is unchanged, only the
    sizing basis is.
    """
    return int(rec["t"].contracts)


def signed_delta_notional(rec, contracts: int | None = None) -> float | None:
    """`delta x contracts x 100 x entry_underlying`, or None when unpriceable.

    None — never 0.0. See the module docstring: a zero here would shrink the
    concentration denominator and move the trigger, which is exactly the
    conflation `CLAUDE.md`'s greek invariant forbids.
    """
    d = rec["delta"]
    if d is None:
        return None
    u = to_float(rec["t"].row.get("entry_underlying"))
    if u is None:
        return None
    n = default_contracts(rec) if contracts is None else int(contracts)
    return float(d) * 100.0 * n * float(u)


# ════════════════════════════════════════════════════════════════════════════
# LAYER 1 — OCCUPANCY (a replay of a book that already happened)
# ════════════════════════════════════════════════════════════════════════════

def exit_bound(rec, holding: str = HOLDING_CALENDAR) -> date:
    """The last date `rec` is counted open on, under `holding`.

    CALENDAR: `signal_date + days_held` days, the pre-registration's span.
    TRADING:  `Trade.grid[days_held - 1]`, `account_sim`'s own `exit_sess`.

    READS `days_held` — an outcome field. This function is the occupancy layer
    and is never called from the trigger layer.
    """
    if holding not in HOLDINGS:
        raise ValueError(f"holding must be one of {HOLDINGS}, got {holding!r}")
    dh = rec["days_held"]
    t = rec["t"]
    if dh is None:
        # No recorded holding period: count the position on its signal date
        # alone rather than inventing a span. Counted by `occupancy_diag`.
        return t.signal_date
    if holding == HOLDING_TRADING:
        if not t.grid:
            return t.signal_date
        return t.grid[min(int(dh), len(t.grid)) - 1]
    return t.signal_date + timedelta(days=int(dh))


def open_book_by_session(recs, holding: str = HOLDING_CALENDAR,
                         sessions: frozenset[date] | None = None
                         ) -> dict[date, tuple[int, ...]]:
    """`{session: (index into `recs`, ...)}` for every session the book is open.

    Indices, not records, on purpose: the trigger layer is re-run over this
    same occupancy with blinded records substituted (gate G-BLIND), and that
    comparison is only meaningful if both runs see an identical open set.

    A position is open on session `s` when
    `signal_date <= s <= exit_bound(rec, holding)` and `s` is a real trading
    session. The signal date itself is INCLUDED — that is the reading which
    reproduces the pre-registration's 504-session universe.
    """
    cal = trading_sessions() if sessions is None else sessions
    out: dict[date, list[int]] = defaultdict(list)
    for i, rec in enumerate(recs):
        start = rec["t"].signal_date
        end = exit_bound(rec, holding)
        d = start
        while d <= end:
            if d in cal:
                out[d].append(i)
            d += timedelta(days=1)
    return {s: tuple(idxs) for s, idxs in sorted(out.items())}


def occupancy_from_positions(positions, sessions: frozenset[date] | None = None
                             ) -> dict[date, tuple[int, ...]]:
    """`{session: (index into `positions`, ...)}` over `[entry_sess, exit_sess]`.

    The occupancy of a SIMULATED book, where the span is the simulator's own
    `[entry_sess, exit_sess]` rather than the one `exit_bound()` derives from
    the ROW's stored `days_held`. `account_sim.simulate()` re-sizes and
    RE-EXITS what it admits — a position it downsized or replayed to a
    different exit day is open over a different window than its row says — so
    `open_book_by_session` would describe a book that was not held.

    Extended BY PARAMETER, not by copy: the caller pairs this with
    `contracts_by_position()` and passes both to `concentration_series()`,
    which is unchanged. `positions` is duck-typed on `account_sim.Pos`
    (`.entry_sess`, `.exit_sess`); indices are into `positions`, so the caller
    passes `[p.rec for p in positions]` as the record list and the two line up.

    Same inclusive rule and same session calendar as `open_book_by_session`:
    every real trading session in `[entry_sess, exit_sess]`.
    """
    cal = trading_sessions() if sessions is None else sessions
    out: dict[date, list[int]] = defaultdict(list)
    for i, p in enumerate(positions):
        d = p.entry_sess
        while d <= p.exit_sess:
            if d in cal:
                out[d].append(i)
            d += timedelta(days=1)
    return {s: tuple(idxs) for s, idxs in sorted(out.items())}


def contracts_by_position(positions):
    """A `contracts_fn` returning the SIM's sized contract count per record.

    `default_contracts()` reads `Trade.contracts` — the book row's own size,
    which is not what an admission model held. This closes over the positions
    by record IDENTITY (`id(rec)`), not by (date, ticker), because a caller may
    legitimately hold two positions on records that compare equal, and because
    the blinded re-run pairs each sighted position with a DIFFERENT record
    object carrying the same contracts.

    Raises `KeyError` on a record that is not one of `positions`' — better than
    silently falling back to the row's own count, which would move the trigger.
    """
    by_id = {id(p.rec): int(p.contracts) for p in positions}

    def contracts_fn(rec) -> int:
        return by_id[id(rec)]

    return contracts_fn


def occupancy_diag(recs, holding: str = HOLDING_CALENDAR,
                   sessions: frozenset[date] | None = None) -> dict:
    """Shape of the occupancy map, for the report header."""
    occ = open_book_by_session(recs, holding, sessions)
    ses = sorted(occ)
    return {
        "holding": holding,
        "n_rows": len(recs),
        "n_signal_dates": len({r["date"] for r in recs}),
        "n_sessions": len(ses),
        "session_range": (ses[0], ses[-1]) if ses else (None, None),
        "n_rows_no_days_held": sum(1 for r in recs if r["days_held"] is None),
        "max_open": max((len(v) for v in occ.values()), default=0),
    }


def holding_disagreement(recs, sessions: frozenset[date] | None = None) -> dict:
    """Session counts under BOTH readings of `days_held`, plus their overlap.

    Printed rather than resolved. The pre-registration committed to the
    calendar reading; the field itself is a trading-day index. A study may not
    silently pick the other one, so the gap is reported.
    """
    cal = set(open_book_by_session(recs, HOLDING_CALENDAR, sessions))
    trd = set(open_book_by_session(recs, HOLDING_TRADING, sessions))
    return {
        "calendar_sessions": len(cal),
        "trading_sessions": len(trd),
        "shared": len(cal & trd),
        "calendar_only": len(cal - trd),
        "trading_only": len(trd - cal),
        "field_semantics": ("days_held is a 1-based index into Trade.grid "
                            "(weekdays AFTER the signal date)"),
        "used": HOLDING_CALENDAR,
        "why": ("the pre-registration's session universe (504) and every "
                "committed plan-time figure reproduce on the calendar reading"),
    }


# ════════════════════════════════════════════════════════════════════════════
# LAYER 2 — TRIGGER (entry-dated fields only; blind-safe)
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ClusterExposure:
    """One cluster's exposure inside one session's open book."""

    name: str
    proxy: str
    hedgeable: bool
    n: int                  # priced positions
    net: float              # signed delta notional, summed
    gross: float            # |signed delta notional|, summed
    direct_gross: float     # the part of `gross` that IS the proxy instrument
    constituent_net: float  # signed, excluding the proxy instrument itself

    @property
    def direct_share(self) -> float | None:
        return self.direct_gross / self.gross if self.gross else None

    @property
    def stratum(self) -> str | None:
        s = self.direct_share
        if s is None:
            return None
        return sectors.DIRECT if s >= DIRECT_MAJORITY else sectors.CONSTITUENT


@dataclass(frozen=True)
class SessionConcentration:
    """The independent variable on one session.

    `concentration` is the pre-registration's primary measure: the largest
    absolute per-cluster signed delta notional as a share of book gross.
    `constituent_concentration` is the same measure computed over CONSTITUENT
    legs only — the operator's literal practice, registered as a stratum.
    """

    session: date
    n_open: int
    n_priced: int
    n_unpriced: int
    book_gross: float
    concentration: float
    top_cluster: str | None
    top_proxy: str | None
    top_hedgeable: bool
    top_direct_share: float | None
    stratum: str | None
    constituent_concentration: float
    constituent_top_cluster: str | None
    clusters: tuple[ClusterExposure, ...]


def _cluster_exposures(recs, idxs, contracts_fn=None) -> tuple[list, int, int, float]:
    """`([ClusterExposure], n_priced, n_unpriced, book_gross)` for one session."""
    acc: dict[str, dict] = {}
    n_priced = n_unpriced = 0
    gross_total = 0.0
    for i in idxs:
        rec = recs[i]
        ticker = rec["ticker"]
        dn = signed_delta_notional(
            rec, None if contracts_fn is None else contracts_fn(rec))
        if dn is None:
            n_unpriced += 1
            continue
        n_priced += 1
        gross_total += abs(dn)
        name = sectors.cluster_for(ticker)
        cell = acc.setdefault(name, dict(n=0, net=0.0, gross=0.0,
                                         direct_gross=0.0, constituent_net=0.0))
        cell["n"] += 1
        cell["net"] += dn
        cell["gross"] += abs(dn)
        if sectors.stratum(ticker) == sectors.DIRECT:
            cell["direct_gross"] += abs(dn)
        else:
            cell["constituent_net"] += dn
    out = [
        ClusterExposure(
            name=name,
            proxy=sectors.proxy_of_cluster(name),
            hedgeable=sectors.is_hedgeable(name),
            n=c["n"], net=c["net"], gross=c["gross"],
            direct_gross=c["direct_gross"],
            constituent_net=c["constituent_net"],
        )
        for name, c in acc.items()
    ]
    out.sort(key=lambda c: (-abs(c.net), c.name))
    return out, n_priced, n_unpriced, gross_total


def session_concentration(recs, idxs, session: date,
                          contracts_fn=None) -> SessionConcentration:
    """The concentration reading for one session's open set.

    THE TRIGGER LAYER. Reads `ticker`, `delta`, `contracts` and
    `entry_underlying` and nothing else — safe under `BlindRec`.
    """
    cls, n_priced, n_unpriced, gross = _cluster_exposures(recs, idxs, contracts_fn)

    if not gross or not cls:
        return SessionConcentration(
            session=session, n_open=len(idxs), n_priced=n_priced,
            n_unpriced=n_unpriced, book_gross=gross, concentration=0.0,
            top_cluster=None, top_proxy=None, top_hedgeable=False,
            top_direct_share=None, stratum=None,
            constituent_concentration=0.0, constituent_top_cluster=None,
            clusters=tuple(cls))

    top = cls[0]                       # already ordered by |net| desc
    con = max(cls, key=lambda c: (abs(c.constituent_net), c.name))
    con_val = abs(con.constituent_net) / gross
    return SessionConcentration(
        session=session,
        n_open=len(idxs),
        n_priced=n_priced,
        n_unpriced=n_unpriced,
        book_gross=gross,
        concentration=abs(top.net) / gross,
        top_cluster=top.name,
        top_proxy=top.proxy,
        top_hedgeable=top.hedgeable,
        top_direct_share=top.direct_share,
        stratum=top.stratum,
        constituent_concentration=con_val,
        constituent_top_cluster=con.name if con_val > 0 else None,
        clusters=tuple(cls),
    )


def concentration_series(recs, occupancy: dict | None = None,
                         holding: str = HOLDING_CALENDAR,
                         sessions: frozenset[date] | None = None,
                         contracts_fn=None) -> list[SessionConcentration]:
    """The whole series, one `SessionConcentration` per open session, in order.

    Pass `occupancy` to reuse an already-computed open-book map — required for
    the G-BLIND comparison, where sighted and blinded runs must share it.
    """
    occ = (open_book_by_session(recs, holding, sessions)
           if occupancy is None else occupancy)
    return [session_concentration(recs, idxs, s, contracts_fn)
            for s, idxs in sorted(occ.items())]


# ════════════════════════════════════════════════════════════════════════════
# Trigger selection and date clustering
# ════════════════════════════════════════════════════════════════════════════

def measure_of(sc: SessionConcentration, measure: str = MEASURE_ANY) -> float:
    if measure == MEASURE_ANY:
        return sc.concentration
    if measure == MEASURE_CONSTITUENT:
        return sc.constituent_concentration
    raise ValueError(f"measure must be one of {MEASURES}, got {measure!r}")


def triggered_sessions(series, tau: float, measure: str = MEASURE_ANY,
                       stratum: str | None = None,
                       hedge_pressure: dict | None = None,
                       cut: int = HEDGE_PRESSURE_CUT) -> list[date]:
    """Sessions whose concentration is `>= tau`, in order.

    `stratum` restricts to DIRECT or CONSTITUENT sessions (the top cluster's
    own composition). `hedge_pressure` additionally applies ARM CS's condition:
    a session survives only when its date parsed a score `>= cut`. A date with
    NO parse is NO SIGNAL and is dropped — the conservative direction, fixed in
    the pre-registration.
    """
    out = []
    for sc in series:
        if measure_of(sc, measure) < tau:
            continue
        if stratum is not None and sc.stratum != stratum:
            continue
        if hedge_pressure is not None:
            v = hedge_pressure.get(sc.session.isoformat())
            if v is None or v < cut:
                continue
        out.append(sc.session)
    return out


def episodes(triggered, universe) -> list[tuple[date, ...]]:
    """`triggered` split into maximal runs of CONSECUTIVE sessions.

    The open book barely changes from one session to the next, so a run of
    triggered sessions is one occasion, not N independent ones. This is the
    clustering `n_trigger_dates` counts by default.
    """
    order = {s: i for i, s in enumerate(sorted(universe))}
    runs: list[list[date]] = []
    prev = None
    for s in sorted(triggered):
        if prev is None or order.get(s, -10 ** 9) != order.get(prev, 10 ** 9) + 1:
            runs.append([])
        runs[-1].append(s)
        prev = s
    return [tuple(r) for r in runs]


def book_signal_dates(recs) -> frozenset[date]:
    """The book's own signal dates — the sessions on which the simulator acts."""
    return frozenset(date.fromisoformat(r["date"]) for r in recs)


def trigger_date_counts(triggered, series, recs) -> dict:
    """Every date-clustered count of a triggered set, all of them reported.

    The pre-registration asks G-POWER for ">= 25 trigger DATES (date-clustered,
    not sessions)" but does not define the clustering, and each session already
    IS one date. Three readings are therefore printed, never one:

      `sessions`      — the raw session count (no clustering at all).
      `episodes`      — maximal runs of consecutive triggered sessions; the
                        DEFAULT `n_trigger_dates` returns, and the strictest.
      `book_dates`    — triggered sessions that are also book SIGNAL dates,
                        i.e. sessions on which the ledger actually admits.
    """
    universe = [sc.session for sc in series]
    eps = episodes(triggered, universe)
    sig = book_signal_dates(recs)
    return {
        "sessions": len(triggered),
        "episodes": len(eps),
        "book_dates": len([s for s in triggered if s in sig]),
    }


# ════════════════════════════════════════════════════════════════════════════
# The hedge-flow signal (ARM CS)
# ════════════════════════════════════════════════════════════════════════════

def _analysis_csv(path=None) -> Path:
    return Path(path) if path else era_mod.resolve_paths()["analysis"]


def hedge_pressure_by_date(path=None) -> tuple[dict[str, int], dict]:
    """`({iso date: score}, diag)` parsed from `AnalysisClaude`'s `regime` prose.

    The regex is the committed one. A date with NO parse is absent from the
    mapping and means NO SIGNAL (do not hedge) — never a zero, which would read
    as "measured, low".

    `diag` carries what the pre-registration asks to be verified: how many of
    the analysis dates parsed, and whether the value is constant within a date
    (`n_dates_multivalued` must be 0; if it is not, the study must say so
    rather than picking one).
    """
    import csv

    src = _analysis_csv(path)
    if not src.exists():
        raise FileNotFoundError(f"analysis export not found at {src}")

    per_date: dict[str, set[int]] = defaultdict(set)
    all_dates: set[str] = set()
    n_rows = n_rows_parsed = 0
    with src.open(newline="") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("date") or "").strip()
            if not d:
                continue
            all_dates.add(d)
            n_rows += 1
            m = HEDGE_PRESSURE_RE.search(row.get("regime") or "")
            if m:
                n_rows_parsed += 1
                per_date[d].add(int(m.group(1)))

    multi = sorted(d for d, v in per_date.items() if len(v) > 1)
    out = {d: sorted(v)[0] for d, v in per_date.items()}
    vals = sorted(out.values())
    diag = {
        "source": str(src),
        "n_rows": n_rows,
        "n_rows_parsed": n_rows_parsed,
        "n_dates": len(all_dates),
        "n_dates_parsed": len(out),
        "coverage": (len(out) / len(all_dates)) if all_dates else float("nan"),
        "n_dates_multivalued": len(multi),
        "multivalued_dates": multi,
        "min": vals[0] if vals else None,
        "max": vals[-1] if vals else None,
        "median": statistics.median(vals) if vals else None,
        "cut": HEDGE_PRESSURE_CUT,
        "n_dates_at_or_above_cut": sum(1 for v in vals if v >= HEDGE_PRESSURE_CUT),
    }
    return out, diag


# ════════════════════════════════════════════════════════════════════════════
# G-BLIND — the trigger under blinded records
# ════════════════════════════════════════════════════════════════════════════

def blind_trigger_check(recs, taus=TAU_GRID, holding: str = HOLDING_CALENDAR,
                        sessions: frozenset[date] | None = None,
                        contracts_fn=None) -> dict:
    """Re-run the TRIGGER layer over blinded records and compare, per gate G-BLIND.

    The occupancy map is computed ONCE from sighted records and shared, because
    occupancy is the replay fixture and is not part of the trigger (see the
    module docstring). Everything downstream — cluster nets, book gross,
    concentration, stratum — is recomputed from `account_sim.blind_records`,
    whose outcome keys raise on read.

    Returns `{"identical": bool, ...}`. The caller prints `LOOKAHEAD DETECTED`
    and refuses when `identical` is False; this module never exits.
    """
    # Deferred: `account_sim` is a study module and imports this package's lib;
    # importing it at module level here would invert the dependency. Same
    # pattern as `live_select.join_entry_check`'s deferred account_sim import.
    from scripts.backtest_study.f4_deployment.account_sim import blind_records

    occ = open_book_by_session(recs, holding, sessions)
    sighted = concentration_series(recs, occ, contracts_fn=contracts_fn)
    blind = concentration_series(blind_records(list(recs)), occ,
                                 contracts_fn=contracts_fn)

    mismatches: list[dict] = []
    for tau in taus:
        for measure in MEASURES:
            a = triggered_sessions(sighted, tau, measure)
            b = triggered_sessions(blind, tau, measure)
            if a != b:
                mismatches.append({"tau": tau, "measure": measure,
                                   "sighted": len(a), "blind": len(b)})
    strata_a = [sc.stratum for sc in sighted]
    strata_b = [sc.stratum for sc in blind]
    values_match = all(
        abs(x.concentration - y.concentration) < 1e-12
        and abs(x.constituent_concentration - y.constituent_concentration) < 1e-12
        for x, y in zip(sighted, blind))
    return {
        "n_sessions": len(sighted),
        "identical": not mismatches and strata_a == strata_b and values_match,
        "trigger_set_mismatches": mismatches,
        "stratum_mismatches": sum(1 for x, y in zip(strata_a, strata_b) if x != y),
        "values_match": values_match,
    }


# ════════════════════════════════════════════════════════════════════════════
# G-CENSUS — the power census, printed before any outcome column is read
# ════════════════════════════════════════════════════════════════════════════

def _pct(vals, q: float) -> float:
    """Linear-interpolated percentile — the method that reproduces the
    pre-registration's quantiles (median .301 / p75 .398 / p90 .572)."""
    if not vals:
        return float("nan")
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * (q / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def exposure_table(recs, contracts_fn=None) -> list[dict]:
    """Per-cluster rows / share of book exposure / direct%, over the whole book.

    The plan-time table the pre-registration discloses. Computed from entry
    fields only; no session loop and no outcome column.
    """
    rows: dict[str, dict] = {}
    total = 0.0
    for rec in recs:
        name = sectors.cluster_for(rec["ticker"])
        cell = rows.setdefault(name, dict(cluster=name,
                                          proxy=sectors.proxy_of_cluster(name),
                                          hedgeable=sectors.is_hedgeable(name),
                                          rows=0, gross=0.0, direct_gross=0.0,
                                          unpriced=0))
        cell["rows"] += 1
        dn = signed_delta_notional(
            rec, None if contracts_fn is None else contracts_fn(rec))
        if dn is None:
            cell["unpriced"] += 1
            continue
        cell["gross"] += abs(dn)
        total += abs(dn)
        if sectors.stratum(rec["ticker"]) == sectors.DIRECT:
            cell["direct_gross"] += abs(dn)
    out = sorted(rows.values(), key=lambda c: -c["gross"])
    for c in out:
        c["share"] = c["gross"] / total if total else float("nan")
        c["direct_pct"] = (c["direct_gross"] / c["gross"]) if c["gross"] else None
    return out


def census(recs, taus=TAU_GRID, holding: str = HOLDING_CALENDAR,
           sessions: frozenset[date] | None = None,
           contracts_fn=None, analysis_csv=None) -> dict:
    """Everything G-CENSUS prints, as data. Reads no outcome column except
    `days_held`, and only through the occupancy layer.

    That INPUT property is what G-CENSUS is for, and it is the only thing the
    report may claim for it. It is NOT a claim about print order — the study
    module reconciles the curve (G-MTM) and measures the two curves (ARM M)
    above this census, so outcome-derived dollars are on the page first — and
    G-CENSUS has NO FAILING PATH: it is a discipline, not a gate. The gate that
    refuses on lookahead is G-BLIND (`blind_trigger_check`).
    """
    occ = open_book_by_session(recs, holding, sessions)
    series = concentration_series(recs, occ, contracts_fn=contracts_fn)
    hp, hp_diag = hedge_pressure_by_date(analysis_csv)

    anyv = [sc.concentration for sc in series]
    consv = [sc.constituent_concentration for sc in series]

    cells: list[dict] = []
    for tau in taus:
        for measure in MEASURES:
            for stratum in (None, sectors.DIRECT, sectors.CONSTITUENT):
                trig = triggered_sessions(series, tau, measure, stratum)
                counts = trigger_date_counts(trig, series, recs)
                cs = triggered_sessions(series, tau, measure, stratum,
                                        hedge_pressure=hp)
                cells.append({
                    "tau": tau, "measure": measure, "stratum": stratum,
                    **counts,
                    "powered": counts["episodes"] >= MIN_TRIGGER_DATES,
                    "arm_cs_sessions": len(cs),
                    "arm_cs_episodes": len(episodes(cs, [s.session for s in series])),
                    "unhedgeable_sessions": sum(
                        1 for sc in series
                        if sc.session in set(trig) and not sc.top_hedgeable),
                })

    return {
        "occupancy": occupancy_diag(recs, holding, sessions),
        "holding_disagreement": holding_disagreement(recs, sessions),
        "exposure": exposure_table(recs, contracts_fn),
        "unhedgeable": sectors.unhedgeable(),
        "quantiles": {
            "any": {q: _pct(anyv, q) for q in (50, 75, 90)},
            "constituent": {q: _pct(consv, q) for q in (50, 75, 90)},
        },
        "hedge_pressure": hp_diag,
        "cells": cells,
        "min_trigger_dates": MIN_TRIGGER_DATES,
        "series": series,
    }


def census_lines(c: dict) -> list[str]:
    """`census()` rendered for a report. Quotes its own numbers, adds none."""
    occ, hd = c["occupancy"], c["holding_disagreement"]
    L = [
        "CONCENTRATION CENSUS (G-CENSUS) — INPUTS are entry-dated fields "
        "only",
        "  (ticker / delta / contracts / entry_underlying, plus days_held "
        "through the",
        "   occupancy layer alone, which is the replay fixture and not a "
        "trigger input.",
        "   G-CENSUS is a DISCIPLINE, not a check: it has no failing path.)",
        f"  book: {occ['n_rows']} rows / {occ['n_signal_dates']} signal dates",
        f"  sessions open ({occ['holding']} reading of days_held): "
        f"{occ['n_sessions']}  {occ['session_range'][0]} .. {occ['session_range'][1]}",
        f"  days_held semantics: {hd['field_semantics']}",
        f"  session count calendar={hd['calendar_sessions']} "
        f"trading={hd['trading_sessions']} shared={hd['shared']} "
        f"— using {hd['used']}: {hd['why']}",
        "",
        "  cluster     rows    share   direct%  proxy  hedgeable",
    ]
    for r in c["exposure"]:
        dp = "   n/a" if r["direct_pct"] is None else f"{r['direct_pct'] * 100:6.1f}"
        L.append(f"  {r['cluster']:<10s} {r['rows']:5d}  {r['share'] * 100:6.1f}%  "
                 f"{dp}  {r['proxy']:<5s}  {'yes' if r['hedgeable'] else 'NO'}")
    for name, why in c["unhedgeable"].items():
        L.append(f"    UNHEDGEABLE {name}: {why}")

    q = c["quantiles"]
    L += [
        "",
        f"  concentration any-cluster    median {q['any'][50]:.3f}  "
        f"p75 {q['any'][75]:.3f}  p90 {q['any'][90]:.3f}",
        f"  concentration constituent    median {q['constituent'][50]:.3f}  "
        f"p75 {q['constituent'][75]:.3f}  p90 {q['constituent'][90]:.3f}",
    ]

    hp = c["hedge_pressure"]
    L += [
        "",
        f"  hedge-pressure parse: {hp['n_dates_parsed']}/{hp['n_dates']} dates "
        f"({hp['coverage'] * 100:.0f}%), multivalued dates "
        f"{hp['n_dates_multivalued']}, span {hp['min']}-{hp['max']}, "
        f"median {hp['median']}, >= {hp['cut']}: {hp['n_dates_at_or_above_cut']}",
        "  a date with no parse is NO SIGNAL (do not hedge)",
        "",
        f"  TRIGGER POWER (G-POWER floor: {c['min_trigger_dates']} dates; "
        f"episodes is the reading it is read against)",
        "   tau  measure      stratum       sessions episodes book_dates  power  ARM-CS",
    ]
    for cell in c["cells"]:
        st = cell["stratum"] or "-all-"
        L.append(f"  {cell['tau']:.2f}  {cell['measure']:<12s} {st:<12s} "
                 f"{cell['sessions']:8d} {cell['episodes']:8d} "
                 f"{cell['book_dates']:10d}  "
                 f"{'ok' if cell['powered'] else 'UNDERPOWERED':<12s} "
                 f"{cell['arm_cs_sessions']:5d}")
    L.append("  UNDERPOWERED is not a lean — no direction is quoted from such a cell.")
    return L


def _main(argv=None) -> int:
    import argparse

    from scripts.backtest_study.lib.book import load_book

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sources", default="real",
                    help="comma-separated book sources (default: real, the "
                         "population the pre-registration's figures were "
                         "computed on); 'all' for real+tweak")
    ap.add_argument("--blind", action="store_true",
                    help="also run the G-BLIND comparison")
    args = ap.parse_args(argv)

    recs, diag = load_book(include_bs=False)
    if args.sources != "all":
        want = {s.strip() for s in args.sources.split(",") if s.strip()}
        recs = [r for r in recs if r["source"] in want]
    print(f"era={diag['era']} loaded={len(recs)} rows sources={args.sources}")
    for line in census_lines(census(recs)):
        print(line)
    if args.blind:
        print()
        print("G-BLIND:", blind_trigger_check(recs))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
