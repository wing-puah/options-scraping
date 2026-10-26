"""mechanical_baseline — does a fixed SPY call spread, bought every week, make money on its own?

Registration: `research/pre-registrations/f1_selection/benchmark/mechanical_baseline.md`
(accepted by the operator 2026-10-26). That file is the spec; this module
implements it and adds nothing to its bar. Where the build needed a ruling the
file did not give, the ruling is folded into the registration beside the clause
it amends, tagged `Resolved at build (2026-10-26)`. RESEARCH TIER: nothing ships
from this study.

THE RULE (`ARM X`). On the first NYSE session of each ISO week (signal date D),
buy one ATM / +5% call vertical on SPY at the standard monthly expiry whose DTE
from the entry day is nearest 65. The strikes, the spot and the dip flag are
read on or before D. The fill is the next session's closing mid (one clock),
waiting inside production's five-session window when that day has no quote.

REUSED, NEVER COPIED
--------------------
Geometry, listing and the spot rule are `mechanical_benchmark`'s (`select_m1`,
`UniverseSpot`, `monthly_for`, `AsOfChain`). Pricing is production's
`simulate._simulate` through `mechanical_benchmark.finish`, on the histories
`narrow_to_fit.Chain` loads: entry fill, junk-quote rule, zero-bid mark and the
debit-to-credit refusal are production's own. The exit profile is production's
merge (`structure_sweep.exit_profile` -> `simulate._effective_sim_cfg`), so a
BEAR_HE signal date adds the regime trail. Commission is production's knob
(`structure_sweep.commission_dollars`, which refuses a non-zero slippage).
Exits replay on the FROZEN harness, cut at the data end. `ARM RND` reuses
`mechanical_benchmark`'s `ARM U` build unchanged. The account layer is
`account_sim.simulate` with `narrow_to_fit`'s narrower; the MTM curve is
`mtm_curve.book_curves`.

THE AWAIT GATE. While any PRIMARY trade (SPY, weekly, 65 DTE, window A or B)
awaits a fetch, the run prints its census and `NOT BUILT — AWAITING SCRAPE`
and stops. Nothing is priced before that check: `RuleBook.price` refuses until
`RuleBook.open_outcomes` has confirmed no primary trade awaits, so no outcome
number can be computed, let alone printed, while one does.

No code here fetches. The fetch plan is `fetch_targets()`, imported by
`scripts/collector/study_legs/fetch_mechanical_baseline_legs.py`.

Usage:
  python3 -m scripts.backtest_study run mechanical_baseline
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import logging
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import MechLabeler  # noqa: E402
from lib.parsing import to_float  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f1_selection.regime.dip_buy import BELOW, dip_label  # noqa: E402
from scripts.backtest_study.f3_structure import structure_sweep as SS  # noqa: E402
from scripts.backtest_study.f3_structure.bear_rewrap import recorded_entry_date  # noqa: E402
from scripts.backtest_study.f4_deployment import account_sim as AS  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.f4_deployment import refuse_floor_forward as FWD  # noqa: E402
from scripts.backtest_study.lib import confidence_sequence as CS  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as MC  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import DEBIT_PROD, MECH_TABLE_CSV, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import MAX_LOSS_ABS, replay  # noqa: E402
from scripts.backtest_study.lib.replay_basis import bounded  # noqa: E402

# Era refusals from `load_book` (exit 2 thin era, exit 3 wrong era).
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

REGISTRATION = "research/pre-registrations/f1_selection/benchmark/mechanical_baseline.md"
ACCEPTED = "2026-10-26"

# ── registered constants (the registration's numbers; never re-chosen) ──────
WINDOWS = {"A": (date(2024, 1, 10), date(2026, 9, 22)),
           "B": (date(2022, 3, 1), date(2024, 1, 9))}
FORWARD_START = date(2026, 10, 27)
SPY_ONLY = ("SPY",)
WIDE = ("SPY", "QQQ", "IWM")
UNIVERSES = (SPY_ONLY, WIDE)
WEEKLY, DAILY, DIP_WEEKLY = "weekly", "daily", "dip_weekly"
CADENCES = (WEEKLY, DAILY, DIP_WEEKLY)
TARGET_DTES = (65, 45)
#: C0 floors. ARM X: 40 built trades in window A. Paired: 25 dates and 40
#: pairs. ARM H: 24 months.
C0_X_TRADES = 40
C0_PAIR_DATES = 25
C0_PAIR_PAIRS = 40
C0_H_MONTHS = 24
BOOT_N = 10_000
SEED = 20261026
PBO_S = 16
PBO_MAX = 0.5
FORWARD_MIN_DATES = 30
#: Account-layer budgets. `S-500-*` = $500; `S-STOP` = the harness's $1,000 stop.
BUDGET_500 = 500.0
STOP_1000 = float(MAX_LOSS_ABS)
#: Resolved at build (2026-10-26): ARM H's month blocks are runs of three
#: consecutive months (Künsch's moving blocks). See the registration.
H_BLOCK_MONTHS = 3
#: ARM RND pairs on the daily cadence (registration, ARM RND overlap).
RND_CADENCE = DAILY
#: Tokens.
NOT_BUILT = "NOT BUILT — AWAITING SCRAPE"
UNDERPOWERED = "UNDERPOWERED"
UNWORDED = "UNWORDED"
NULL = "NULL"

SESSION_TABLES = (ROOT / "backtests" / "mech_regime" / "spy_base_rate_daily.csv",
                  ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv")
FETCH_CMD = "python3 scripts/collector/study_legs/fetch_mechanical_baseline_legs.py"

log = logging.getLogger("mechanical_baseline")
hdr = MB.hdr


class AwaitingScrape(RuntimeError):
    """An outcome was asked for while a primary trade awaits a fetch."""


# ════════════════════════════════════════════════════════════════════════════
# Calendar, windows and cells — pure
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass(frozen=True)
class Cell:
    tickers: tuple
    cadence: str
    target: int

    @property
    def label(self) -> str:
        u = "SPY" if self.tickers == SPY_ONLY else "SPY+QQQ+IWM"
        return f"{u} {self.cadence} {self.target}"


PRIMARY = Cell(SPY_ONLY, WEEKLY, 65)
#: Universe x cadence x target DTE: the twelve trade-level cells C5 reads.
CELLS = tuple(Cell(u, c, t) for u in UNIVERSES for c in CADENCES for t in TARGET_DTES)


def load_closes(paths=SESSION_TABLES) -> dict[date, float]:
    """SPY closes by session. The first table wins a shared date; a later
    table only extends the calendar past the first one's end."""
    out: dict[date, float] = {}
    for p in paths:
        if not Path(p).exists():
            continue
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                c = to_float(r.get("spy_close"))
                if c is None:
                    continue
                d = date.fromisoformat(str(r["date"])[:10])
                out.setdefault(d, c)
    return out


def next_session(sessions: list[date]) -> dict[date, date]:
    return {a: b for a, b in zip(sessions, sessions[1:])}


def weekly_dates(sessions) -> set[date]:
    """The first session of each ISO week."""
    first: dict[tuple, date] = {}
    for d in sorted(sessions):
        first.setdefault(d.isocalendar()[:2], d)
    return set(first.values())


def in_window(d: date, window: str) -> bool:
    lo, hi = WINDOWS[window]
    return lo <= d <= hi


def rule_expiry(entry_day: date, target: int) -> date | None:
    """The standard monthly expiry whose DTE from `entry_day` is nearest
    `target`, ties to the earlier. No DTE band: the band passed to
    `monthly_for` only bounds the search, and holds every expiry nearer the
    target than the nearest one can be."""
    return MB.monthly_for(entry_day, target, (1, 2 * target + 62))


class DipFlag:
    """`dip_buy.dip_label` on the SPY close tables, first table that covers D."""

    def __init__(self, paths=SESSION_TABLES):
        self.labelers = [MechLabeler.from_csv(p) for p in paths if Path(p).exists()]

    def __call__(self, d: date) -> str | None:
        for lab in self.labelers:
            got = dip_label(lab, d.isoformat())
            if got is not None:
                return got
        return None


def signal_dates(cadence: str, sessions: list[date], weekly: set[date], dip,
                 lo: date, hi: date) -> tuple[list[date], Counter]:
    """`(dates, census)` of the cadence's signal dates in `[lo, hi]`."""
    nxt = next_session(sessions)
    out, c = [], Counter()
    for d in sessions:
        if not (lo <= d <= hi) or d not in nxt:
            continue
        if cadence == DAILY:
            out.append(d)
            continue
        if d not in weekly:
            continue
        if cadence == DIP_WEEKLY:
            lab = dip(d)
            if lab is None:
                c["dip_unlabelled"] += 1
                continue
            if lab != BELOW:
                c["not_a_dip"] += 1
                continue
        out.append(d)
    return out, c


# ════════════════════════════════════════════════════════════════════════════
# The rule book — selection reads D and nothing later; pricing is gated
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass
class XTrade:
    """One rule trade. `status`: built | await | drop. `reason` names a drop
    (`no_spot` is the registration's "D has no spot")."""
    ticker: str
    signal: date
    entry: date              # planned entry: the session after D
    expiry: date | None
    target: int
    status: str
    reason: str = ""
    k_long: float | None = None
    k_short: float | None = None
    fetch: tuple = ()
    nod1: bool = False       # a leg has no D+1 bid/ask in its cached file


@dataclasses.dataclass
class Priced:
    x: XTrade
    row: dict
    t: object                # bounded harness Trade, 1 contract
    entry_day: date | None
    exit_reason: str
    days_held: int
    exit_sess: date
    R_gross: float
    R_net: float
    commission: float
    R_rnd: float             # ARM U's basis: gross, DEBIT_PROD, 1 contract
    profile: dict


def select(chain, evidence, spot_u, ticker: str, signal: date, entry: date,
           target: int) -> XTrade:
    """The rule's strikes, read on `signal` only. No pricing."""
    exp = rule_expiry(entry, target)
    if exp is None:
        return XTrade(ticker, signal, entry, None, target, "drop", "no_monthly")
    spot = spot_u(ticker, signal, exp)
    if spot is None:
        return XTrade(ticker, signal, entry, exp, target, "drop", "no_spot")
    w = MB.select_m1(chain, evidence, ticker, exp, spot, signal)
    x = XTrade(ticker, signal, entry, exp, target, w.status, w.reason,
               w.k_long, w.k_short, w.fetch)
    if w.status == "built":
        x.nod1 = not all(_has_quote(chain, ticker, exp, k, entry)
                         for k in (w.k_long, w.k_short))
    return x


def _has_quote(chain, ticker, exp, k, day) -> bool:
    r = MB.row_on(chain, MB.call_leg(ticker, exp, k), day)
    return bool(r) and to_float(r.get("Bid")) is not None and to_float(r.get("Ask")) is not None


class RuleBook:
    """Every rule trade, memoised by `(ticker, signal, target)`.

    `price()` refuses until `open_outcomes()` has seen no primary trade await.
    That is the await gate, by construction: no figure can be computed early.
    """

    def __init__(self, chain, evidence, sessions: list[date], sim_cfg: dict | None = None,
                 spot_u=None):
        self.chain, self.evidence, self.sim_cfg = chain, evidence, sim_cfg or {}
        self.sessions = sorted(sessions)
        self.nxt = next_session(self.sessions)
        self.spot_u = spot_u or MB.UniverseSpot(chain)
        self._sel: dict[tuple, XTrade] = {}
        self._px: dict[tuple, Priced | str] = {}
        self._open = False

    def trade(self, ticker: str, signal: date, target: int) -> XTrade | None:
        if signal not in self.nxt:
            return None
        key = (ticker, signal, target)
        if key not in self._sel:
            self._sel[key] = select(self.chain, self.evidence, self.spot_u, ticker,
                                    signal, self.nxt[signal], target)
        return self._sel[key]

    def primary_awaiting(self, weekly: set[date], dip) -> list[XTrade]:
        out = []
        for w in WINDOWS:
            for x in cell_trades(self, PRIMARY, w, weekly, dip)[0]:
                if x is not None and x.status == "await":
                    out.append(x)
        return out

    def open_outcomes(self, weekly: set[date], dip) -> None:
        aw = self.primary_awaiting(weekly, dip)
        if aw:
            raise AwaitingScrape(f"{len(aw)} primary trades await a fetch")
        self._open = True

    def price(self, x: XTrade) -> Priced | str:
        """`Priced` or a drop reason. Raises while the await gate is shut."""
        if not self._open:
            raise AwaitingScrape("outcomes are closed until no primary trade awaits")
        if x.status != "built":
            raise ValueError(f"cannot price a {x.status} trade")
        key = (x.ticker, x.signal, x.target)
        if key not in self._px:
            self._px[key] = price_trade(self.chain, self.sim_cfg, x)
        return self._px[key]


def cell_trades(book: RuleBook, cell: Cell, window: str, weekly, dip,
                lo: date | None = None, hi: date | None = None):
    """`([XTrade | None], date census)` for `cell` over `window` (or `[lo, hi]`)."""
    lo, hi = (lo, hi) if lo is not None else WINDOWS[window]
    dates, c = signal_dates(cell.cadence, book.sessions, weekly, dip, lo, hi)
    out = []
    for d in dates:
        for tk in cell.tickers:
            out.append(book.trade(tk, d, cell.target))
    return out, c


def price_trade(chain, sim_cfg: dict, x: XTrade) -> Priced | str:
    """Production's `_simulate` on the 1-lot vertical, replayed on the frozen
    harness under production's effective debit profile."""
    w = MB.finish(MB.Wrap("built", "", x.k_long, x.k_short), chain, sim_cfg,
                  x.ticker, x.signal, x.entry, x.expiry)
    if w.status != "built":
        return w.reason or "unpriced"
    t = bounded(MB.trade_of(w.row))
    prof, _side = SS.exit_profile(sim_cfg, t.entry_net, x.signal, MB.STRUCTURE)
    out = replay(t, **prof)
    gross = out["pnl_pct"]
    comm = SS.commission_dollars(list(t.legs), 1, sim_cfg)
    net = gross - comm / (abs(t.entry_net) * 100.0)
    dh = int(out["days_held"])
    r_rnd = MB.replay_R(MB.trade_of(w.row), DEBIT_PROD)[0]
    return Priced(x=x, row=w.row, t=t, entry_day=recorded_entry_date(t),
                  exit_reason=out["exit_reason"], days_held=dh,
                  exit_sess=t.grid[min(dh, len(t.grid)) - 1], R_gross=gross,
                  R_net=net, commission=comm, R_rnd=r_rnd, profile=prof)


# ════════════════════════════════════════════════════════════════════════════
# Census — counts only
# ════════════════════════════════════════════════════════════════════════════

def census_counts(trades: list[XTrade | None], dates_census: Counter) -> dict:
    c = Counter(n=0, built=0, await_=0, no_spot=0, drop=0, nod1=0)
    fetch: set = set()
    drops_by_year: Counter = Counter()
    for x in trades:
        if x is None:
            continue
        c["n"] += 1
        if x.status == "await":
            c["await_"] += 1
            fetch |= {(tk, e, round(float(k), 4)) for tk, e, k in x.fetch}
        elif x.status == "drop":
            c["no_spot" if x.reason == "no_spot" else "drop"] += 1
            drops_by_year[(x.signal.year, x.reason)] += 1
        elif x.nod1:
            c["nod1"] += 1
        else:
            c["built"] += 1
    return dict(c=c, fetch=fetch, drops_by_year=drops_by_year, dates=dates_census)


def census_line(cell: Cell, window: str, k: dict) -> str:
    c = k["c"]
    extra = "  ".join(f"{a}={b}" for a, b in sorted(k["dates"].items()))
    return (f"  {cell.label:<22} window {window}  n {c['n']:>4}  built {c['built']:>4}  "
            f"await {c['await_']:>4}  no_spot {c['no_spot']:>3}  drop {c['drop']:>3}  "
            f"nod1 {c['nod1']:>3}  contracts-to-fetch {len(k['fetch']):>4}"
            + (f"  ({extra})" if extra else ""))


def blind_check(book: RuleBook, trades: list[XTrade | None]) -> list[str]:
    """Every decided trade re-selected on a cache cut at its signal date must
    agree (no look-ahead). Awaiting trades are not compared."""
    bad = []
    for x in trades:
        if x is None or x.status == "await":
            continue
        cut = MB.AsOfChain(book.chain, x.signal)
        again = select(cut, book.evidence, MB.UniverseSpot(cut), x.ticker, x.signal,
                       x.entry, x.target)
        same = (again.status == x.status and (again.k_long, again.k_short)
                == (x.k_long, x.k_short)) or (x.status == "drop" and again.status == "drop")
        if not same:
            bad.append(f"{x.ticker} {x.signal}: full {x.status} {x.k_long}/{x.k_short} "
                       f"vs cut {again.status} {again.k_long}/{again.k_short}")
    return bad


def fetch_targets(book: RuleBook, weekly, dip, scope: str = "primary") -> list[dict]:
    """Unique uncached call contracts the awaiting trades name, primary first.

    `scope`: `primary` (the primary cell, both windows) or `all` (every
    parameter cell, both windows). A contract two cells name is listed once,
    under the first. The collector imports this; a re-run re-targets."""
    cells = [PRIMARY] if scope == "primary" else [PRIMARY] + [c for c in CELLS if c != PRIMARY]
    seen: dict = {}
    for cell in cells:
        for w in ("A", "B"):
            for x in cell_trades(book, cell, w, weekly, dip)[0]:
                if x is None or x.status != "await":
                    continue
                for tk, exp, k in x.fetch:
                    seen.setdefault((tk, exp, round(float(k), 4)),
                                    f"{cell.label.replace(' ', ':')}:{w}")
    return [dict(ticker=tk, expiration=exp, strike=k, opt_type="Call", category=cat)
            for (tk, exp, k), cat in sorted(seen.items())]


def build_calendar():
    """`(sessions, weekly, dip)` from the SPY close tables."""
    closes = load_closes()
    sessions = sorted(d for d in closes if d >= date(2022, 1, 1))
    return sessions, weekly_dates(sessions), DipFlag()


def plan(scope: str = "primary") -> list[dict]:
    """The collector's entry point: the fetch plan on the cache as it stands.
    Selection only; nothing is priced and no network is touched."""
    sessions, weekly, dip = build_calendar()
    book = RuleBook(NTF.Chain(), NTF.unlisted_evidence(), sessions)
    return fetch_targets(book, weekly, dip, scope)


# ── ARM RND / ARM BK pairing census ─────────────────────────────────────────

def rnd_slots(b: MB.EraBuild) -> list[tuple]:
    """`(slot, date, expiry)` for every usable ARM U slot (no slot drop)."""
    return [(s, date.fromisoformat(d), e) for s, (d, e, why) in zip(b.slots, b.u_slot)
            if not why]


def rnd_matches(slot_entry: date | None, slot_expiry: date, x_entry: date | None,
                x_expiry: date | None) -> bool:
    """A pair needs the same entry day and the same monthly expiry (the
    signal date is matched by the caller's lookup)."""
    return (slot_entry is not None and x_entry is not None and slot_entry == x_entry
            and x_expiry is not None and slot_expiry == x_expiry)


def rnd_overlap(book: RuleBook, b: MB.EraBuild, cadence: str, target: int,
                weekly, tickers=SPY_ONLY) -> dict:
    """Planned-entry overlap of ARM U slots with the rule (census only)."""
    dates, pairs = set(), set()
    for s, d, exp in rnd_slots(b):
        if cadence == WEEKLY and d not in weekly:
            continue
        xs = [book.trade(tk, d, target) for tk in tickers]
        if any(x is not None and rnd_matches(s.entry_day, exp, x.entry, x.expiry)
               for x in xs):
            dates.add(d)
            pairs.add((s.date, exp))
    tot = built = 0
    for d, e in pairs:
        for tk, _sec in b.universe[d]:
            tot += 1
            built += b.u[(d, tk, e)].status == "built"
    return dict(dates=len(dates), wraps=tot, built=built)


def rnd_floors(b: MB.EraBuild) -> tuple[bool, bool, int, float | None]:
    """`(floor3 passes, floor4b passes, contracts to fetch, median share)` —
    `mechanical_benchmark`'s own census and fetch plan, read not re-derived."""
    c = MB.census(b)
    n_fetch = len(MB.fetch_targets([b]))
    share = c["u"]["median_share"]
    return (share is not None and share >= 1 - MB.U_REDRAW_CAP), n_fetch == 0, n_fetch, share


def book_dates(records: list[dict]) -> dict[str, list[dict]]:
    """Deployed rows (top-3 Tier A/B) by signal date, seal applied."""
    kept, _seal = MB.apply_seal(records)
    out: dict[str, list[dict]] = defaultdict(list)
    for r in MB.deployed(kept):
        out[r["date"]].append(r)
    return dict(out)


def bk_census(book: RuleBook, by_date: dict, tickers, target: int) -> Counter:
    c = Counter()
    for d in sorted(by_date):
        for tk in tickers:
            x = book.trade(tk, date.fromisoformat(d), target)
            c["no_session" if x is None else
              ("await" if x.status == "await" else
               ("drop" if x.status == "drop" else "built"))] += 1
    c["dates"] = len(by_date)
    return c


# ════════════════════════════════════════════════════════════════════════════
# Grading — pure functions on rows (tested on synthetic rows)
# ════════════════════════════════════════════════════════════════════════════

def _sign(v: float) -> int:
    return (v > 0) - (v < 0)


def excludes_zero(ci) -> bool:
    lo, hi = ci
    return (lo > 0) or (hi < 0)


def grade_vs_zero(rows_a: list[dict], rows_b: list[dict], key: str = "R",
                  n: int = BOOT_N, seed: int = SEED) -> dict:
    """ARM X vs zero, C0-C4. Rows: `{date, R}`; a date is one signal date."""
    g = dict(n=len(rows_a), dates=len({r["date"] for r in rows_a}),
             c0=len(rows_a) >= C0_X_TRADES)
    if not g["c0"]:
        g["token"] = UNDERPOWERED
        return g
    g["mean"] = statistics.fmean(r[key] for r in rows_a)
    g["ci"] = P.boot_ci_by_date(rows_a, key, n=n, seed=seed)
    g["c1"] = excludes_zero(g["ci"])
    loo = P.loo_by_date(rows_a, lambda r: r[key], lambda r: 0.0)
    g["loo"] = loo
    g["c2"] = loo[1] == (1.0 if g["mean"] > 0 else 0.0)
    g["stress"] = {}
    for name, rs in P.window_cuts(rows_a).items():
        if name != "ALL":
            g["stress"][name] = statistics.fmean(r[key] for r in rs) if rs else float("nan")
    g["c3"] = all(_sign(v) == _sign(g["mean"]) for v in g["stress"].values())
    g["b_n"] = len(rows_b)
    if rows_b:
        g["b_mean"] = statistics.fmean(r[key] for r in rows_b)
        g["b_ci"] = P.boot_ci_by_date(rows_b, key, n=n, seed=seed)
        g["c4"] = not (g["b_ci"][1] < 0)
        g["c4_alt"] = _sign(g["b_mean"]) == _sign(g["mean"])
    else:
        g["b_mean"] = g["b_ci"] = None
        g["c4"] = g["c4_alt"] = False
    g["token"] = x_token(g)
    return g


def x_token(g: dict) -> str:
    if not g.get("c0"):
        return UNDERPOWERED
    if not g["c1"]:
        return NULL
    if g["mean"] < 0:
        return "LOSES"
    if g["c2"] and g["c3"] and g["c4"]:
        return "PROFITABLE"
    return UNWORDED


def grade_paired(rows: list[dict], n: int = BOOT_N, seed: int = SEED) -> dict:
    """A paired comparison, C0-C3. Rows: `{date, R_T, R_C}`; gain = T - C."""
    dates = {r["date"] for r in rows}
    g = dict(n=len(rows), dates=len(dates),
             c0=len(dates) >= C0_PAIR_DATES and len(rows) >= C0_PAIR_PAIRS)
    if not g["c0"]:
        return g
    g["mean_T"] = statistics.fmean(r["R_T"] for r in rows)
    g["mean_C"] = statistics.fmean(r["R_C"] for r in rows)
    g["gain"] = g["mean_T"] - g["mean_C"]
    g["ci"] = P.boot_ci_paired_by_date(rows, "R_T", "R_C", n=n, seed=seed)
    g["c1"] = excludes_zero(g["ci"])
    loo = P.loo_by_date(rows, lambda r: r["R_T"], lambda r: r["R_C"])
    g["loo"] = loo
    g["c2"] = loo[1] == (1.0 if g["gain"] > 0 else 0.0)
    g["stress"] = {}
    for name, rs in P.window_cuts(rows).items():
        if name != "ALL":
            g["stress"][name] = (statistics.fmean(r["R_T"] - r["R_C"] for r in rs)
                                 if rs else float("nan"))
    g["c3"] = all(_sign(v) == _sign(g["gain"]) for v in g["stress"].values())
    return g


def paired_token(g: dict, pos: str, neg: str) -> str:
    if not g.get("c0"):
        return UNDERPOWERED
    if not g["c1"]:
        return NULL
    if g["gain"] < 0:
        return neg
    if g["c2"] and g["c3"]:
        return pos
    return UNWORDED


def ols(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """`(intercept, slope)` of y on x."""
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    return my - slope * mx, slope


def block_bootstrap_alpha(months: list[tuple], block: int = H_BLOCK_MONTHS,
                          n: int = BOOT_N, seed: int = SEED) -> tuple[float, float]:
    """Moving-block bootstrap CI95 of the OLS intercept over a monthly series
    `[(month, x_ret, m_ret)]`. Blocks are `block` consecutive months."""
    T = len(months)
    if T < 2:
        return (float("nan"), float("nan"))
    b = min(block, T)
    starts = list(range(T - b + 1))
    k = math.ceil(T / b)
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        pick = []
        for _ in range(k):
            s = rng.choice(starts)
            pick.extend(months[s:s + b])
        pick = pick[:T]
        xs = [m for _mo, _x, m in pick]
        if max(xs) - min(xs) < 1e-15:
            continue
        out.append(ols(xs, [x for _mo, x, _m in pick])[0])
    out.sort()
    if not out:
        return (float("nan"), float("nan"))
    return (out[int(0.025 * len(out))], out[min(len(out) - 1, int(0.975 * len(out)))])


def grade_alpha(months: list[tuple], n: int = BOOT_N, seed: int = SEED) -> dict:
    """ARM H, C0-C3 on `[(\"YYYY-MM\", account_ret, spy_ret)]`."""
    g = dict(n=len(months), c0=len(months) >= C0_H_MONTHS)
    if not g["c0"]:
        g["token"] = UNDERPOWERED
        return g
    xs = [m for _mo, _x, m in months]
    ys = [x for _mo, x, _m in months]
    g["alpha"], g["beta"] = ols(xs, ys)
    g["ci"] = block_bootstrap_alpha(months, n=n, seed=seed)
    g["c1"] = excludes_zero(g["ci"])
    folds = []
    for i in range(len(months)):
        rest = months[:i] + months[i + 1:]
        folds.append(ols([m for _a, _x, m in rest], [x for _a, x, _m in rest])[0])
    g["loo_min"], g["loo_max"] = min(folds), max(folds)
    g["c2"] = all(_sign(f) == _sign(g["alpha"]) for f in folds)
    g["stress"] = {}
    for name, mos in P.DOMINANT_WINDOWS.items():
        rest = [m for m in months if m[0] not in mos]
        g["stress"][name] = ols([m for _a, _x, m in rest], [x for _a, x, _m in rest])[0]
    g["c3"] = all(_sign(v) == _sign(g["alpha"]) for v in g["stress"].values())
    if not g["c1"]:
        g["token"] = "DRIFT-ONLY"
    elif g["alpha"] < 0:
        g["token"] = "NEGATIVE-ALPHA"
    elif g["c2"] and g["c3"]:
        g["token"] = "ALPHA"
    else:
        g["token"] = UNWORDED
    return g


def study_token(x: str, h: str, bk: str) -> str:
    """The study-level token, BOOK-BETTER first. ARM RND never enters it.
    Withheld (NOT BUILT) while ARM BK awaits: both BOOK-BETTER and "ARM BK is
    not TRAILS-BOOK" need ARM BK read."""
    if bk == NOT_BUILT or x == NOT_BUILT:
        return NOT_BUILT
    if bk == "TRAILS-BOOK":
        return "BOOK-BETTER"
    if x in (NULL, "LOSES"):
        return "NO-REPLACEMENT"
    if x == "PROFITABLE":
        return "DRIFT-REPLACEMENT" if h == "DRIFT-ONLY" else "REPLACEMENT-CANDIDATE"
    return f"NO STUDY-LEVEL TOKEN (ARM X {x})"


def forward_token(xs: list[float]) -> tuple[str, object]:
    """The forward read: a confidence sequence on per-date mean net R, F2's
    constants, entering the running intersection at the 30-date floor."""
    if len(xs) < FORWARD_MIN_DATES:
        return "STILL-OPEN", None
    step = CS.sequence(xs, FWD.ALPHA, FWD.T_STAR, start=FORWARD_MIN_DATES)[-1]
    if step.run_lo is not None and step.run_lo > 0:
        return "FORWARD-HOLDS", step
    if step.run_hi is not None and step.run_hi < 0:
        return "FORWARD-FAILS", step
    return "STILL-OPEN", step


def pbo_matrix(rows_by_cell: dict, weeks: list[tuple]):
    """`T weeks x N cells x 2 channels (sum net R, trades)`, window A."""
    import numpy as np
    cells = list(rows_by_cell)
    idx = {w: i for i, w in enumerate(weeks)}
    M = np.zeros((len(weeks), len(cells), 2))
    for j, c in enumerate(cells):
        for r in rows_by_cell[c]:
            i = idx.get(date.fromisoformat(r["date"]).isocalendar()[:2])
            if i is not None:
                M[i, j, 0] += r["R"]
                M[i, j, 1] += 1
    return M


# ════════════════════════════════════════════════════════════════════════════
# Rows from priced trades (only reachable once the gate is open)
# ════════════════════════════════════════════════════════════════════════════

def priced_rows(book: RuleBook, trades) -> tuple[list[Priced], Counter]:
    out, drops = [], Counter()
    for x in trades:
        if x is None or x.status != "built":
            continue
        p = book.price(x)
        if isinstance(p, str):
            drops[(x.signal.year, p)] += 1
        else:
            out.append(p)
    return out, drops


def x_rows(ps: list[Priced], key: str = "R_net") -> list[dict]:
    return [dict(date=p.x.signal.isoformat(), R=getattr(p, key), ticker=p.x.ticker)
            for p in ps]


_MECH: list = []


def mech_cell(d: date) -> str | None:
    """The shipped mech cell of `d` (the table `lib/book.py` labels rows from).
    `account_sim` reads it for the skipped-row counterfactuals it records."""
    if not _MECH:
        _MECH.append(MechLabeler.from_csv(MECH_TABLE_CSV) if Path(MECH_TABLE_CSV).exists()
                     else None)
    return _MECH[0].cell(d.isoformat()) if _MECH[0] is not None else None


def account_records(ps: list[Priced]) -> list[dict]:
    """`account_sim` records for priced rule trades. The rule has no tier;
    every trade is admitted to the ladder as Tier A so the account walk takes
    it, in a fixed ticker order within a day."""
    order = {tk: i for i, tk in enumerate(WIDE)}
    out = []
    for p in ps:
        out.append(dict(
            t=p.t, date=p.x.signal.isoformat(), ticker=p.x.ticker,
            structure=MB.STRUCTURE, credit=False, delta=to_float(p.row.get("delta")),
            dte=to_float(p.row.get("dte_entry")), market_regime="", tier="A",
            max_loss_per_contract=to_float(p.row.get("max_loss_per_contract")),
            mech_cell=mech_cell(p.x.signal), profile=p.profile, priced=p,
            rank=-order.get(p.x.ticker, 9)))
    return out


def replayer(rec, contracts, stop, cache=None):
    """`account_sim`'s replay at the rule's own exit profile."""
    return AS.replay_sized(rec, contracts, stop, profile=rec["profile"], cache=cache)


def day_lists(recs: list[dict]):
    return P.ordered_by_day(recs, lambda r: r["rank"])


def run_account(recs, st: AS.Settings, variant: str, sim_cfg: dict, chain, evidence,
                caps: bool = True) -> AS.Sim:
    """One sizing variant through `account_sim.simulate`."""
    base = dict(net_cap=NTF.HEAD_NET_CAP, per_pos_cap=NTF.PER_POS_CAP, compound=False)
    if not caps:
        base.update(AS.UNCONSTRAINED)
    narrower = None
    if variant == "S-1":
        cfg = st.cfg(variant, risk_pct=1e-9, stop_abs=STOP_1000, floor="take", **base)
    elif variant == "S-STOP":
        budget = STOP_1000 / float(sim_cfg.get("stop_loss") or 1.0)
        cfg = st.cfg(variant, risk_pct=budget / st.capital, stop_abs=STOP_1000,
                     floor="take", **base)
    elif variant == "S-500-F2":
        cfg = st.cfg(variant, risk_pct=BUDGET_500 / st.capital, stop_abs=None,
                     floor="refuse", take_floor=False, **base)
    elif variant == "S-500-F3":
        cfg = st.cfg(variant, risk_pct=BUDGET_500 / st.capital, stop_abs=None,
                     floor="narrow", **base)
        narrower = NTF.Narrower(chain, evidence, sim_cfg)
    else:
        raise ValueError(variant)
    return AS.simulate(day_lists(recs), cfg, cache=AS.new_cache(), replayer=replayer,
                       narrower=narrower)


def monthly_series(sim: AS.Sim, closes: dict[date, float], capital: float,
                   sim_cfg: dict, start: date, net: bool = True) -> list[tuple]:
    """`[(\"YYYY-MM\", account return, SPY return)]` on the MTM curve. Net
    subtracts each position's commission at its exit session."""
    pos = sim.signal_pos
    curve = MC.book_curves(pos, target=MC.TARGET_POSITION).mtm
    comm = [(p.exit_sess, SS.commission_dollars(list(p.rec["t"].legs), p.contracts,
                                                sim_cfg)) for p in pos]
    last = max([s for s in curve.sessions] + [start])
    cl_days = sorted(closes)
    months = []
    y, m = start.year, start.month
    while (y, m) <= (last.year, last.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    def month_end(ym):
        y_, m_ = ym
        nxt = date(y_ + 1, 1, 1) if m_ == 12 else date(y_, m_ + 1, 1)
        return nxt - timedelta(days=1)

    def level_at(d):
        lv = 0.0
        for s, v in zip(curve.sessions, curve.levels):
            if s <= d:
                lv = v
            else:
                break
        return lv

    def close_at(d):
        got = [c for c in cl_days if c <= d]
        return closes[got[-1]] if got else None

    prev_eq = capital
    prev_m = close_at(date(start.year, start.month, 1) - timedelta(days=1))
    out = []
    for ym in months:
        e = month_end(ym)
        eq = capital + level_at(e) - (sum(c for s, c in comm if s <= e) if net else 0.0)
        spy = close_at(e)
        if spy is None or prev_m is None or e > cl_days[-1]:
            break
        out.append((f"{ym[0]:04d}-{ym[1]:02d}", eq / prev_eq - 1.0, spy / prev_m - 1.0))
        prev_eq, prev_m = eq, spy
    return out


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def _f(v, fmt="+.3f") -> str:
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else format(v, fmt)


def print_x(name: str, g: dict) -> None:
    if not g.get("c0"):
        print(f"  {name}: {UNDERPOWERED} — {g['n']} built trades (needs {C0_X_TRADES}); "
              f"census only")
        return
    yn = lambda v: "Y" if v else "n"  # noqa: E731
    print(f"  {name}: trades {g['n']} dates {g['dates']}  meanR {_f(g['mean'])} "
          f"CI95 [{_f(g['ci'][0])}, {_f(g['ci'][1])}]")
    print(f"     LOO share positive {_f(g['loo'][1], '.2f')}  stress "
          + "  ".join(f"{k} {_f(v)}" for k, v in g["stress"].items())
          + f"  window B n {g['b_n']} meanR {_f(g['b_mean'])}"
          + (f" CI95 [{_f(g['b_ci'][0])}, {_f(g['b_ci'][1])}]" if g["b_ci"] else ""))
    print(f"     C0 Y  C1 {yn(g['c1'])}  C2 {yn(g['c2'])}  C3 {yn(g['c3'])}  "
          f"C4 {yn(g['c4'])} (alt rule, same sign as window A: {yn(g['c4_alt'])})")


def print_paired(name: str, g: dict) -> None:
    if not g.get("c0"):
        print(f"  {name}: {UNDERPOWERED} — {g['n']} pairs on {g['dates']} dates "
              f"(needs {C0_PAIR_PAIRS} and {C0_PAIR_DATES}); census only")
        return
    yn = lambda v: "Y" if v else "n"  # noqa: E731
    print(f"  {name}: pairs {g['n']} dates {g['dates']}  meanR X {_f(g['mean_T'])} "
          f"vs {_f(g['mean_C'])}  gain {_f(g['gain'])} "
          f"CI95 [{_f(g['ci'][0])}, {_f(g['ci'][1])}]")
    print(f"     LOO share positive {_f(g['loo'][1], '.2f')}  stress "
          + "  ".join(f"{k} {_f(v)}" for k, v in g["stress"].items())
          + f"  C1 {yn(g['c1'])} C2 {yn(g['c2'])} C3 {yn(g['c3'])}")


def print_alpha(name: str, g: dict) -> None:
    if not g.get("c0"):
        print(f"  {name}: {UNDERPOWERED} — {g['n']} months (needs {C0_H_MONTHS})")
        return
    yn = lambda v: "Y" if v else "n"  # noqa: E731
    print(f"  {name}: months {g['n']}  alpha/month {_f(g['alpha'], '+.5f')} "
          f"CI95 [{_f(g['ci'][0], '+.5f')}, {_f(g['ci'][1], '+.5f')}]  "
          f"beta {_f(g['beta'], '+.4f')}")
    print(f"     LOO alpha [{_f(g['loo_min'], '+.5f')}, {_f(g['loo_max'], '+.5f')}]  stress "
          + "  ".join(f"{k} {_f(v, '+.5f')}" for k, v in g["stress"].items())
          + f"  C1 {yn(g['c1'])} C2 {yn(g['c2'])} C3 {yn(g['c3'])}")


def operator_steps() -> None:
    print("  Operator-run steps, in order (none runs from here):")
    print(f"    1. {FETCH_CMD} --dry-run   (then --limit N)")
    print("    2. python3 scripts/backup_research_caches.py push")
    print("    3. re-run this study; a fetch can expose a nearer strike, so steps 1-3")
    print("       repeat until no primary trade awaits")
    print("  It does not run while mechanical_benchmark's ARM U loop runs: one writer.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-v3", action="store_true", help="skip ARM BK's v3 replication")
    args = ap.parse_args(argv)
    logging.getLogger("backtest").setLevel(logging.ERROR)
    logging.getLogger("scripts.backtest").setLevel(logging.ERROR)

    hdr("mechanical_baseline — does a fixed SPY call spread, bought every week, "
        "make money on its own?")
    sim_cfg = SS.load_sim_cfg()
    comm, slip = SS.SIM._cost_knobs(sim_cfg)
    probe, _ = SS.exit_profile(sim_cfg, 1.0, date(2026, 1, 2), MB.STRUCTURE)
    d_ok = all(probe.get(k) == v for k, v in DEBIT_PROD.items())
    print(f"""  Registration {REGISTRATION}
  (accepted by the operator {ACCEPTED}). NOTHING SHIPS FROM THIS STUDY.
  PRIMARY: SPY, weekly (first session of the ISO week), monthly nearest 65 DTE,
  ATM/+5% call vertical, 1 contract, production's effective debit exits.
  windows  A {WINDOWS['A'][0]} -> {WINDOWS['A'][1]} (PRIMARY)  ·  B {WINDOWS['B'][0]} -> \
{WINDOWS['B'][1]} (replication)  ·  forward from {FORWARD_START}
  era      ARM X reads no analysis row; ARM BK and ARM RND read era {era_mod.CURRENT} \
(v3 replication for ARM BK)
  costs    commission ${comm:.2f}/contract/leg/side, slippage {slip:g} (config/backtest.yml)
  exits    production merge == DEBIT_PROD on a no-regime date: {d_ok}  \
(BEAR_HE dates add the regime trail)
  seal     {era_mod.seal_line({'rows': 0, 'dates': 0, 'reader': None})}""")

    sessions, weekly, dip = build_calendar()
    chain = NTF.Chain()
    evidence = NTF.unlisted_evidence()
    book = RuleBook(chain, evidence, sessions, sim_cfg)
    print(f"  calendar {sessions[0]} -> {sessions[-1]}  ({len(sessions)} sessions, "
          f"SPY close tables in backtests/mech_regime/)")

    # ── STAGE 1: census, counts only ─────────────────────────────────────────
    hdr("CENSUS — every cell, both windows (counts only; no outcome read)")
    cens = {}
    for cell in (PRIMARY,) + tuple(c for c in CELLS if c != PRIMARY):
        for w in ("A", "B"):
            trades, dc = cell_trades(book, cell, w, weekly, dip)
            cens[(cell, w)] = (trades, census_counts(trades, dc))
            print(census_line(cell, w, cens[(cell, w)][1]))
        if cell == PRIMARY:
            print("  -- parameter cells --")
    print("\n  PRIMARY drops by year (registration: every drop is printed by year)")
    for w in ("A", "B"):
        dby = cens[(PRIMARY, w)][1]["drops_by_year"]
        if not dby:
            print(f"    window {w}: none")
        for (yr, why), n in sorted(dby.items()):
            print(f"    window {w}  {yr}  {why:<24} {n:>4}")
    prim = [x for w in ("A", "B") for x in cens[(PRIMARY, w)][0]]
    bad = blind_check(book, prim)
    print(f"\n  G-BLIND (selection re-run on a cache cut at D, primary): "
          f"{'PASS' if not bad else 'FAIL'}  {len(bad)} choices differ")
    for b_ in bad[:10]:
        print(f"     {b_}")

    # ARM RND and ARM BK pairing counts.
    hdr("CENSUS — ARM RND overlap and ARM BK pairing (counts only)")
    v4 = v3 = None
    try:
        v4, d4 = load_book(include_bs=False)
        print(f"  era {d4.get('era')}  book {len(v4)} rows  {d4.get('n_dates')} dates")
    except SystemExit as exc:
        print(f"  era {era_mod.CURRENT} refused (exit {exc.code}): ARM BK and ARM RND not built")
    if not args.no_v3:
        try:
            v3, d3 = load_book(era="v3", include_bs=False)
            print(f"  era {d3.get('era')} (ARM BK replication)  book {len(v3)} rows  "
                  f"{d3.get('n_dates')} dates")
        except SystemExit as exc:
            print(f"  era v3 refused (exit {exc.code}); ARM BK replication not read")
    ub = None
    rnd_state = NOT_BUILT
    if v4 is not None:
        ub = MB.build_era(None, chain, evidence, sim_cfg, price=False, records=v4)
        usable = rnd_slots(ub)
        print(f"  ARM U slots (mechanical_benchmark, v4, {ub.seal}): {len(ub.slots)}; "
              f"usable {len(usable)} on {len({d for _s, d, _e in usable})} dates")
        for cad, T in ((DAILY, 65), (DAILY, 45), (WEEKLY, 65)):
            o = rnd_overlap(book, ub, cad, T, weekly)
            print(f"    ARM X {cad} {T}: slot dates sharing date, entry day and expiry "
                  f"{o['dates']:>4}  universe wraps {o['wraps']:>6}  already built "
                  f"{o['built']:>6}")
        f3, f4b, n_fetch, share = rnd_floors(ub)
        print(f"  mechanical_benchmark floor 3 (median priceable share >= "
              f"{1 - MB.U_REDRAW_CAP:.2f}, selection only): {_f(share, '.3f')} "
              f"{'pass' if f3 else 'PENDING'}  ·  floor 4b (contracts to fetch, every arm): "
              f"{n_fetch} {'pass' if f4b else 'PENDING'}")
        rnd_state = "READY" if (f3 and f4b) else NOT_BUILT
        print(f"  ARM RND: {'gradable once ARM X is built' if rnd_state == 'READY' else NOT_BUILT}")
    bk_by = {}
    for name, recs in (("v4", v4), ("v3", v3)):
        if recs is None:
            continue
        bk_by[name] = book_dates(recs)
        c = bk_census(book, bk_by[name], SPY_ONLY, 65)
        print(f"  ARM BK {name}: book dates {c['dates']}  ARM X daily SPY 65 on them: "
              f"built {c['built']}  await {c['await']}  drop {c['drop']}  "
              f"no session {c['no_session']}")

    n_plan = len(fetch_targets(book, weekly, dip, "primary"))
    n_all = len(fetch_targets(book, weekly, dip, "all"))
    print(f"\n  fetch plan: primary {n_plan} unique uncached call contracts; every cell {n_all}")

    # ── THE AWAIT GATE ───────────────────────────────────────────────────────
    try:
        book.open_outcomes(weekly, dip)
    except AwaitingScrape as exc:
        hdr(f"VERDICT: {NOT_BUILT}")
        print(f"  PRIMARY: {NOT_BUILT} — {exc}.")
        print("  No outcome was computed for any arm: no R, no P&L, no CI.")
        operator_steps()
        return 0
    if bad:
        hdr("GATE FAILURE — G-BLIND: a choice used data after its signal date")
        print("  No outcome printed. Exit 1.")
        return 1

    return outcomes(book, cens, weekly, dip, sim_cfg, chain, evidence, ub, rnd_state,
                    bk_by)


def outcomes(book, cens, weekly, dip, sim_cfg, chain, evidence, ub, rnd_state,
             bk_by) -> int:
    """Everything past the await gate. `book.price` raises if it was not opened."""
    closes = load_closes()
    st = AS.load_settings(AS.DEFAULT_CONFIG)
    awaiting = {k: v[1]["c"]["await_"] for k, v in cens.items()}

    def cell_ready(cell):
        return not awaiting[(cell, "A")] and not awaiting[(cell, "B")]

    cache_rows: dict = {}

    def rows_for(cell, w):
        if (cell, w) not in cache_rows:
            cache_rows[(cell, w)] = priced_rows(book, cens[(cell, w)][0])
        return cache_rows[(cell, w)]

    def daily_trades(tickers, target, d: date):
        out = []
        for tk in tickers:
            x = book.trade(tk, d, target)
            out.append(x)
        return out

    def bk_grade(by_date, tickers, target):
        rows, drop, aw = [], Counter(), 0
        for d in sorted(by_date):
            xs = daily_trades(tickers, target, date.fromisoformat(d))
            if any(x is not None and x.status == "await" for x in xs):
                aw += 1
                continue
            vals = []
            for x in xs:
                if x is None or x.status != "built":
                    drop[x.reason if x else "no_session"] += 1
                    continue
                p = book.price(x)
                if isinstance(p, str):
                    drop[p] += 1
                    continue
                vals.append(p.R_net)
            bk = [r["R"] for r in by_date[d] if r.get("R") is not None]
            if not vals or not bk:
                drop["unpaired"] += 1
                continue
            rows.append(dict(date=d, R_T=statistics.fmean(vals), R_C=statistics.fmean(bk)))
        if aw:
            return None, drop, aw
        return grade_paired(rows), drop, 0

    priced_u: dict = {}

    def rnd_grade(tickers, target):
        if rnd_state != "READY" or ub is None:
            return None, "floors", 0
        if "pb" not in priced_u:
            # ARM U priced exactly as mechanical_benchmark prices it, on the
            # same deployed slots the census build read.
            priced_u["pb"] = MB.build_era(None, chain, evidence, sim_cfg, price=True,
                                          records=[s.rec for s in ub.slots])
            priced_u["rows"] = MB.u_rows(priced_u["pb"], "headline")
        pb = priced_u["pb"]
        f3, f4b, _n, _s = rnd_floors(pb)
        if not (f3 and f4b):
            return None, "floors", 0
        urows, pools, unusable = priced_u["rows"]
        it = iter(zip(urows, range(len(urows))))
        rows, pool_of, aw = [], {}, 0
        k = 0
        for s, (d, exp, why) in zip(pb.slots, pb.u_slot):
            if why or d in unusable:
                continue
            if not any(pb.u[(d, tk, exp)].status == "built" for tk, _ in pb.universe[d]):
                continue
            urow, i = next(it)
            xs = daily_trades(tickers, target, date.fromisoformat(d))
            if any(x is not None and x.status == "await" for x in xs):
                aw += 1
                continue
            vals = []
            for x in xs:
                if x is None or x.status != "built":
                    continue
                p = book.price(x)
                if isinstance(p, str) or not rnd_matches(s.entry_day, exp, p.entry_day,
                                                         x.expiry):
                    continue
                vals.append(p.R_rnd)
            if vals:
                pool_of[k] = pools[i]
                rows.append(dict(date=d, R_T=statistics.fmean(vals), R_C=urow["R_C"]))
                k += 1
        if aw:
            return None, "await", aw
        g = grade_paired(rows)
        if g.get("c0"):
            _p5, p95, _m = MB.u_band(rows, pool_of)
            g["p95"] = p95
        return g, "", 0

    def s1_alpha(ps):
        recs = account_records(ps)
        if not recs:
            return dict(n=0, c0=False, token=UNDERPOWERED), None
        sim = run_account(recs, st, "S-1", sim_cfg, chain, evidence, caps=False)
        months = monthly_series(sim, closes, st.capital, sim_cfg,
                                start=WINDOWS["A"][0])
        return grade_alpha(months), sim

    # ── ARM X vs zero (PRIMARY) ──────────────────────────────────────────────
    hdr("ARM X vs zero — PRIMARY (SPY weekly 65), net of commission")
    pa, dra = rows_for(PRIMARY, "A")
    pb_, drb = rows_for(PRIMARY, "B")
    for w, dr in (("A", dra), ("B", drb)):
        for (yr, why), n in sorted(dr.items()):
            print(f"  unpriced (dropped) window {w} {yr} {why:<30} {n:>4}")
    gx = grade_vs_zero(x_rows(pa), x_rows(pb_))
    print_x("ARM X (net)", gx)
    gg = grade_vs_zero(x_rows(pa, "R_gross"), x_rows(pb_, "R_gross"))
    if gg.get("c0"):
        print(f"  gross beside it: meanR {_f(gg['mean'])} CI95 [{_f(gg['ci'][0])}, "
              f"{_f(gg['ci'][1])}]  window B {_f(gg['b_mean'])}")
    open_n = sum(1 for p in pa if p.exit_reason == "cap_open")
    exits = Counter(p.exit_reason for p in pa).most_common()
    print("  exits: " + "  ".join(f"{k}={v}" for k, v in exits)
          + f"  (open at data end {open_n})")
    tok_x = gx["token"]
    print(f"  ARM X vs zero: {tok_x}")

    # ── ARM H ────────────────────────────────────────────────────────────────
    hdr("ARM H — monthly Jensen alpha, S-1 MTM account vs SPY (window A)")
    gh, _sim = s1_alpha(pa)
    print_alpha("ARM H (net)", gh)
    print(f"  ARM H: {gh['token']}")
    ex = []
    for p in pa:
        e0, e1 = p.entry_day, p.exit_sess
        c0 = closes.get(e0) if e0 else None
        c1 = closes.get(e1)
        if c0 and c1:
            ex.append((c1 / c0 - 1.0, p.R_net))
    if len(ex) >= 3:
        a, b = ols([m for m, _r in ex], [r for _m, r in ex])
        print(f"  secondary (no verdict): trade R on SPY's move over the hold, n {len(ex)}  "
              f"R at zero move {a:+.3f}  slope {b:+.3f}")

    # ── ARM RND ──────────────────────────────────────────────────────────────
    hdr("ARM RND — SPY vs a random flow-universe ticker (ARM U basis: gross, "
        "DEBIT_PROD, 1 lot)")
    g_rnd, why, aw = rnd_grade(SPY_ONLY, 65)
    if g_rnd is None:
        tok_rnd = NOT_BUILT
        cause = ("mechanical_benchmark floors 3/4b" if why == "floors"
                 else f"{aw} pair dates await")
        print(f"  ARM RND: {NOT_BUILT} ({cause})")
    else:
        print_paired("ARM RND (daily 65)", g_rnd)
        if g_rnd.get("c0"):
            print(f"     random book p95 over {MB.U_DRAWS} draws (seed {MB.U_SEED}): "
                  f"{_f(g_rnd['p95'])}")
        tok_rnd = paired_token(g_rnd, "SPY-BEATS-RANDOM", "RANDOM-BEATS-SPY")
        print(f"  ARM RND: {tok_rnd}")

    # ── ARM BK ───────────────────────────────────────────────────────────────
    hdr("ARM BK — ARM X (daily SPY 65, net) vs the deployed book (net R as stored)")
    tok_bk = NOT_BUILT
    for name in ("v4", "v3"):
        if name not in bk_by:
            print(f"  ARM BK {name}: not read (era refused)")
            continue
        g, drop, aw = bk_grade(bk_by[name], SPY_ONLY, 65)
        if g is None:
            print(f"  ARM BK {name}: {NOT_BUILT} ({aw} book dates await a fetch)")
            continue
        print_paired(f"ARM BK {name}", g)
        if drop:
            print("     dropped dates: " + "  ".join(f"{k}={v}" for k, v in drop.items()))
        t = paired_token(g, "BEATS-BOOK", "TRAILS-BOOK")
        print(f"  ARM BK {name}: {t}{'' if name == 'v4' else ' (replication)'}")
        if name == "v4":
            tok_bk = t

    # ── Parameters printed both ways ─────────────────────────────────────────
    hdr("PARAMETERS PRINTED BOTH WAYS — no verdict except the primary")
    rows_by_cell = {}
    for cell in CELLS:
        if not cell_ready(cell):
            print(f"  {cell.label:<22} {NOT_BUILT} ({awaiting[(cell, 'A')]} + "
                  f"{awaiting[(cell, 'B')]} trades await)")
            continue
        ra, _ = rows_for(cell, "A")
        rb, _ = rows_for(cell, "B")
        g = grade_vs_zero(x_rows(ra), x_rows(rb))
        gg2 = grade_vs_zero(x_rows(ra, "R_gross"), x_rows(rb, "R_gross"))
        rows_by_cell[cell] = x_rows(ra)
        h, _s = s1_alpha(ra)
        line = (f"  {cell.label:<22} X n {g['n']:>4} meanR net {_f(g.get('mean'))} "
                f"[{_f(g.get('ci', (None, None))[0])}, {_f(g.get('ci', (None, None))[1])}] "
                f"gross {_f(gg2.get('mean'))}  B {_f(g.get('b_mean'))}  "
                f"C4 {'Y' if g.get('c4') else 'n'}/alt {'Y' if g.get('c4_alt') else 'n'}  "
                f"H alpha {_f(h.get('alpha'), '+.5f')}")
        print(line)
    for tickers in UNIVERSES:
        for T in TARGET_DTES:
            lab = f"{'SPY' if tickers == SPY_ONLY else 'SPY+QQQ+IWM'} daily {T}"
            if "v4" in bk_by:
                g, _d, aw = bk_grade(bk_by["v4"], tickers, T)
                print(f"  {lab:<22} ARM BK v4: " + (
                    f"{NOT_BUILT}" if g is None else
                    f"gain {_f(g.get('gain'))} n {g['n']}" if g.get("c0") else
                    f"{UNDERPOWERED} ({g['n']} pairs)"))
            g, why, aw = rnd_grade(tickers, T)
            print(f"  {lab:<22} ARM RND: " + (
                NOT_BUILT if g is None else
                f"gain {_f(g.get('gain'))} n {g['n']}" if g.get("c0") else
                f"{UNDERPOWERED} ({g['n']} pairs)"))

    # ── C5 PBO ───────────────────────────────────────────────────────────────
    hdr(f"C5 OVERFITTING — PBO by CSCV across the twelve cells (S = {PBO_S})")
    if len(rows_by_cell) < len(CELLS):
        print(f"  C5 NOT READ: {len(CELLS) - len(rows_by_cell)} cells await a fetch")
    else:
        import numpy as np  # noqa: F401
        weeks = sorted({d.isocalendar()[:2] for d in book.sessions
                        if in_window(d, "A")})
        M = pbo_matrix(rows_by_cell, weeks)
        Mp, padded = PBO.pad_head(M, PBO_S)
        res = PBO.cscv(Mp, S=PBO_S, metric=PBO.ratio_metric)
        print(f"  T={len(weeks)} ISO weeks (+{padded} empty head rows), N={len(CELLS)} "
              f"cells, metric mean net R per trade")
        print(f"  PBO {res.pbo:.3f}  ({'>= ' if res.pbo >= PBO_MAX else '< '}{PBO_MAX}: "
              f"{'no non-primary cell may be promoted' if res.pbo >= PBO_MAX else 'no bar crossed'})")

    # ── Account layer ────────────────────────────────────────────────────────
    hdr("ACCOUNT LAYER — PRIMARY, window A (printed; no verdict reads it)")
    print(f"  account_sim config: capital ${st.capital:,.0f}, caps per-position "
          f"{NTF.PER_POS_CAP} / net {NTF.HEAD_NET_CAP} (x equity). account_sim books "
          f"gross; commission is subtracted here.")
    recs = account_records(pa)
    for variant in ("S-1", "S-STOP", "S-500-F2", "S-500-F3"):
        sim = run_account(recs, st, variant, sim_cfg, chain, evidence)
        taken = sim.signal_pos
        comm_tot = sum(SS.commission_dollars(list(p.rec["t"].legs), p.contracts, sim_cfg)
                       for p in taken)
        bc = MC.book_curves(taken, target=MC.TARGET_POSITION)
        dd = MC.max_drawdown(bc.mtm.daily) if taken else 0.0
        refused = {k: v for k, v in sim.census.items() if k not in AS.CENSUS_TAKEN}
        dips = Counter()
        dol = Counter()
        for p in taken:
            lab = dip(date.fromisoformat(p.rec["date"])) or "NO_DATA"
            dips[lab] += 1
            dol[lab] += p.dollars
        print(f"  {variant:<9} taken {len(taken):>4}  refused " + (
            "  ".join(f"{k}={v}" for k, v in sorted(refused.items())) or "none")
            + f"  realized ${sim.dollars - comm_tot:+,.0f} net (gross "
              f"${sim.dollars:+,.0f})  MTM max DD ${dd:,.0f}")
        print("            dip classes: " + "  ".join(
            f"{k} n {dips[k]} ${dol[k]:+,.0f}" for k in sorted(dips)))

    # ── Forward read ─────────────────────────────────────────────────────────
    hdr("FORWARD READ — weekly signal dates from 2026-10-27")
    fwd = [d for d in book.sessions if d >= FORWARD_START and d in weekly]
    readable = [d for d in fwd if not era_mod.is_withheld(d.isoformat())]
    print(f"  forward signal dates on the calendar {len(fwd)}; readable past the "
          f"holdout seal {len(readable)}")
    xs = []
    for d in readable:
        x = book.trade("SPY", d, 65)
        if x is None or x.status != "built":
            continue
        p = book.price(x)
        if not isinstance(p, str) and p.exit_reason != "cap_open":
            xs.append(p.R_net)
    ftok, step = forward_token(xs)
    print(f"  forward dates with a closed trade {len(xs)} (floor {FORWARD_MIN_DATES})  "
          f"FORWARD: {ftok}")

    # ── Verdict ──────────────────────────────────────────────────────────────
    word = study_token(tok_x, gh["token"], tok_bk)
    hdr(f"VERDICT: {word}")
    print(f"  ARM X {tok_x}  ·  ARM H {gh['token']}  ·  ARM RND {tok_rnd} (not in the "
          f"study token)  ·  ARM BK {tok_bk}")
    print("  BOOK-BETTER takes precedence. Nothing ships from the retrospective.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
