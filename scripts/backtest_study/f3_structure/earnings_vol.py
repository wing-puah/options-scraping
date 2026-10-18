"""earnings_vol — does a long straddle or a calendar across earnings pay, without re-wrapping the book?

REGISTERED 2026-10-12, accepted by default the same day, before the first run
and before its fetch: research/pre-registrations/f3_structure/earnings_vol.md.
Every constant, window and verdict word below is that file's. Read it before
changing anything here.

WHAT IT COMPUTES
----------------
On a fixed list of 25 names, for every report in 2024-Q1 .. 2026-Q3, two
non-directional structures entered at the close of session E-5 and closed at
the close of session E (the first session whose open reflects the report):

    ARM S   long ATM straddle, front expiry
    ARM K   long ATM double calendar: sell front call + put, buy back call + put

The entry close (rebased onto the option chain's unadjusted basis), the
candidate strike ladder, both expiries, E and the entry day come from the SAME
pure planner the fetch used (`scripts/collector/study_legs/fetch_earnings_legs.py::
plan_ticker`), and the ATM from its `resolve_atm`: the ladder candidate nearest
the entry close whose front call and put both have an entry-day row, passing
over a failed / unlisted / unquoted candidate and dropping the event
(`front_not_fetched`) at an unfetched one. The ladder depends on the close
alone, so no cache index enters the plan (the old pre-fetch index is gone).

M1 per arm: mean return (P&L / entry debit), median, win rate, profit factor,
MFE and MAE as a share of debit, a season-clustered CI95 (whole calendar
quarters of the report date resampled), halves, leave-one-season-out and per
name. G1: the sleeve's daily MTM against the deployed book's daily MTM
(`account_sim` registered cell -> `mtm_curve.book_curves(TARGET_POSITION)`),
stationary-block CI.

Verdict per arm (registered): `EDGE`, `RE-WRAP`, `CONTRARY` or `NULL`, at mid
fill on in-sample events. The natural fill, the unknown-as-amc events, the
run-up exit (close of E-1) and the 0.10 gate print their own tokens as
secondaries. The 8-config PBO prints as context. Events with E on or after
`era.SEAL_START` are forward and print STILL-OPEN. Nothing ships.

No network. Option quotes come from `backtests/option_history_cache/` only;
closes and the session calendar from agent-trading's `data/history/`. No model
price.

Run:

    python -m scripts.backtest_study run earnings_vol
"""
from __future__ import annotations

import csv
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest.shared import unlisted as UL  # noqa: E402
from scripts.backtest_study.f3_structure import index_vrp as IV  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as pbo_mod  # noqa: E402
from scripts.collector.study_legs import fetch_earnings_legs as FEL  # noqa: E402

REGISTRATION = "research/pre-registrations/f3_structure/earnings_vol.md"
ACCEPTED = "2026-10-12"

# --- registered constants ------------------------------------------------------
SEED = 20261012
BOOT_N = 10_000
BLOCK = 10
COMMISSION = 0.65            # $ per contract per side
G1_BAR = 0.0                 # pass when corr <= 0 (financed_spread E3's bar)
G1_ALT_BAR = 0.10            # printed beside it
TAIL = 0.05                  # the book's worst 5% of sessions
PBO_S = 10
SEASONS = tuple((y, q) for y in (2024, 2025, 2026) for q in (1, 2, 3, 4)
                if (y, q) <= (2026, 3))
H2_FROM = (2025, 3)          # H1 = 2024-Q1 .. 2025-Q2 (6), H2 = 2025-Q3 .. 2026-Q3 (5)
UNIVERSE = FEL.UNIVERSE + FEL.ADDED
SEAL_START = date.fromisoformat(era_mod.SEAL_START)

ARMS = ("S", "K")
FILLS = ("mid", "natural")
EXITS = ("E", "E-1")
CONFIGS = tuple((a, f, x) for a in ARMS for f in FILLS for x in EXITS)
GRADED = {a: (a, "mid", "E") for a in ARMS}

CACHE_DIR = FEL.HISTORY_CACHE
MANIFEST = FEL.MANIFEST_PATH
OUT_CSV = ROOT / "backtests" / "study_output" / "earnings_vol-latest.csv"

EDGE, REWRAP, CONTRARY, NULL = "EDGE", "RE-WRAP", "CONTRARY", "NULL"

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
EXIT_GMTM = 4

# Drop reasons a leg check can return, in the order the census prints them.
LEG_REASONS = ("front_not_fetched", "front_no_candidate",
               "back_failed", "back_unlisted", "back_not_fetched", "back_not_quoted_at_entry",
               "front_missing_exit", "back_missing_exit", "calendar_credit", "no_debit")


# ════════════════════════════════════════════════════════════════════════════
# Seasons
# ════════════════════════════════════════════════════════════════════════════

def season_of(d: date) -> tuple[int, int]:
    """Calendar quarter of the REPORT date."""
    return d.year, (d.month - 1) // 3 + 1


def season_label(s: tuple[int, int]) -> str:
    return f"{s[0]}-Q{s[1]}"


def half_of(s: tuple[int, int]) -> str:
    return "H2" if s >= H2_FROM else "H1"


# ════════════════════════════════════════════════════════════════════════════
# Events — the fetch's own planner
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Event:
    ticker: str
    ann_date: date
    raw_session: str
    plan: FEL.EventPlan
    runup: date

    @property
    def unknown(self) -> bool:
        return self.raw_session == "unknown"

    @property
    def season(self) -> tuple[int, int]:
        return season_of(self.ann_date)


def read_manifest(path: Path = MANIFEST) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def runup_session(e: date, sessions: list[date]) -> date | None:
    i = FEL.session_index(sessions).get(e)
    return sessions[i - 1] if i else None


def plan_events(tickers, *, sessions: list[date], events_by: dict, closes_by: dict,
                prices_by: dict | None = None, rescaled: set | frozenset = frozenset(),
                include_unknown: bool) -> tuple[list[Event], dict]:
    """`(events, {ticker: TickerPlan})` from `FEL.plan_ticker`. `prices_by`
    holds each ticker's `Price~` by day, which sets the close basis only."""
    out, tps = [], {}
    prices_by = prices_by or {}
    for t in tickers:
        evs = events_by.get(t, [])
        closes, src = closes_by.get(t, ({}, ""))
        tp = FEL.plan_ticker(t, events=evs, sessions=sessions, closes=closes, close_source=src,
                             prices=prices_by.get(t, {}), rescaled=t in rescaled,
                             include_unknown=include_unknown)
        tps[t] = tp
        raw = dict(evs)
        for p in tp.plans:
            ru = runup_session(p.e, sessions)
            if ru is None or ru <= p.entry:
                continue
            out.append(Event(t, p.ann_date, raw.get(p.ann_date, p.session), p, ru))
    return out, tps


# ════════════════════════════════════════════════════════════════════════════
# Quotes
# ════════════════════════════════════════════════════════════════════════════

class Quotes:
    """Cached option rows by contract, read lazily; `{date: row}` per file."""

    def __init__(self, cache_dir: Path = CACHE_DIR, unlisted: dict | None = None,
                 failed: set | None = None):
        self.cache_dir = Path(cache_dir)
        self.unlisted = unlisted or {}
        self.failed = failed or set()
        self._rows: dict[Path, dict | None] = {}

    def _path(self, t: str, x: date, k: float, r: str) -> Path:
        return FEL.cache_path(self.cache_dir, t, x, k, "Call" if r == "C" else "Put")

    def rows(self, t: str, x: date, k: float, r: str) -> dict | None:
        p = self._path(t, x, k, r)
        if p not in self._rows:
            if not p.exists():
                self._rows[p] = None
            else:
                by: dict[date, dict] = {}
                with open(p, newline="") as fh:
                    for row in csv.DictReader(fh):
                        try:
                            d = date.fromisoformat(str(row.get("Time", ""))[:10])
                        except ValueError:
                            continue
                        by.setdefault(d, row)
                self._rows[p] = by
        return self._rows[p]

    def row(self, t, x, k, r, d) -> dict | None:
        by = self.rows(t, x, k, r)
        return None if by is None else by.get(d)

    def status(self, t: str, x: date, k: float, r: str, d: date) -> str:
        """ok / not_quoted (file, no row on d) / failed (manifest) / unlisted
        (`_unlisted.jsonl`, whatever its age) / not_fetched — the planner's
        `FEL.LegStatus` vocabulary."""
        by = self.rows(t, x, k, r)
        if by is not None:
            return FEL.OK if d in by else FEL.NOT_QUOTED
        key = UL.contract_id(dict(symbol=t, expiration=x, strike=k,
                                  opt_type="Call" if r == "C" else "Put"))
        if key in self.failed:
            return FEL.FAILED
        return FEL.UNLISTED if key in self.unlisted else FEL.NOT_FETCHED


def _worst(statuses) -> str:
    for s in (FEL.FAILED, FEL.UNLISTED, FEL.NOT_FETCHED, FEL.NOT_QUOTED):
        if s in statuses:
            return s
    return FEL.OK


_REASON = {FEL.NOT_FETCHED: "not_fetched", FEL.UNLISTED: "unlisted", FEL.FAILED: "failed",
           FEL.NOT_QUOTED: "not_quoted_at_entry"}


def pick_atm(ev: Event, q: Quotes) -> tuple[float | None, str]:
    """The ATM strike, by the planner's own walk (`FEL.resolve_atm`): the
    ladder candidate nearest the entry close (ties lower) whose front call AND
    put have an entry-day row. A candidate with a failed, unlisted or unquoted
    leg is passed over; one with a leg never fetched drops the event
    (`front_not_fetched`) rather than move the strike; with every candidate
    passed over the event drops as `front_no_candidate`."""
    pick = FEL.resolve_atm(ev.plan, q.status)
    return pick.strike, pick.reason


# ════════════════════════════════════════════════════════════════════════════
# One trade
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Leg:
    right: str
    expiry: date
    qty: int          # +1 bought, -1 sold


def legs_for(arm: str, front: date, back: date) -> list[Leg]:
    if arm == "S":
        return [Leg("C", front, +1), Leg("P", front, +1)]
    return [Leg("C", front, -1), Leg("C", back, +1), Leg("P", front, -1), Leg("P", back, +1)]


@dataclass
class Trade:
    ev: Event
    arm: str
    fill: str
    exit_rule: str
    strike: float | None
    status: str = "ok"
    debit: float = 0.0             # per share, at the fill basis
    pnl: float = 0.0               # $ per unit, net of commission
    marks: dict = field(default_factory=dict)   # date -> cumulative $ per unit
    n_junk: int = 0
    n_carried: int = 0

    # --- the attributes `index_vrp.sleeve_levels` / `on_axis` read ------------
    @property
    def entry(self) -> date:
        return self.ev.plan.entry

    @property
    def exit_day(self) -> date:
        return self.ev.plan.e if self.exit_rule == "E" else self.ev.runup

    @property
    def expiry(self) -> date:            # the sleeve's "closed on or after" day
        return self.exit_day

    @property
    def held(self) -> list[date]:
        return sorted(self.marks)

    @property
    def size_1k(self) -> int:
        return 1

    # --- per-event measures ----------------------------------------------------
    @property
    def denom(self) -> float | None:
        return self.debit * 100 if self.status == "ok" and self.debit > 0 else None

    @property
    def ret(self) -> float | None:
        return self.pnl / self.denom if self.denom else None

    @property
    def mfe(self) -> float | None:
        return max(self.marks.values()) / self.denom if self.denom else None

    @property
    def mae(self) -> float | None:
        return min(self.marks.values()) / self.denom if self.denom else None


def _exit_px(row, qty: int, fill: str) -> tuple[float, str]:
    """Closing price per share: mid, or natural (a long leg sold at the bid, 0
    with no bid; a short leg bought back at the ask), junk -> `Latest`."""
    if fill == "mid":
        return IV.mid_mark(row)
    return IV.natural_fill(row, sold=qty > 0)


def run_trade(ev: Event, arm: str, fill: str, exit_rule: str, strike: float | None,
              why: str, q: Quotes, sessions: list[date]) -> Trade:
    """Enter at the close of E-5 on that day's rows, mark daily at mid, exit at
    the close of `exit_rule`'s session at the fill basis. No row dated after a
    mark's own day is read for that mark."""
    tr = Trade(ev, arm, fill, exit_rule, strike)
    if strike is None:
        tr.status = why
        return tr
    p = ev.plan
    legs = legs_for(arm, p.front, p.back)
    if arm == "K":
        sts = [q.status(ev.ticker, p.back, strike, r, p.entry) for r in ("C", "P")]
        w = _worst(sts)
        if w != "ok":
            tr.status = "back_" + _REASON[w]
            return tr
    entry_rows = [q.row(ev.ticker, lg.expiry, strike, lg.right, p.entry) for lg in legs]
    if any(r is None for r in entry_rows):          # the front check guarantees this
        tr.status = "front_not_quoted_at_entry"
        return tr
    xd = tr.exit_day
    for lg in legs:
        if q.row(ev.ticker, lg.expiry, strike, lg.right, xd) is None:
            tr.status = ("front" if lg.expiry == p.front else "back") + "_missing_exit"
            return tr

    debit, value = 0.0, 0.0
    for lg, r in zip(legs, entry_rows):
        m, tag = IV.mid_mark(r)
        tr.n_junk += tag != "mid"
        px = m if fill == "mid" else IV.natural_fill(r, sold=lg.qty < 0)[0]
        debit += lg.qty * px
        value += lg.qty * m
    if debit <= 0:
        tr.status = "calendar_credit" if arm == "K" else "no_debit"
        tr.debit = debit
        return tr
    tr.debit = debit
    comm = COMMISSION * len(legs)
    tr.marks[p.entry] = (value - debit) * 100 - comm
    last = [IV.mid_mark(r)[0] for r in entry_rows]
    for d in (s for s in sessions if p.entry < s <= xd):
        if d == xd:
            val = 0.0
            for lg in legs:
                px, tag = _exit_px(q.row(ev.ticker, lg.expiry, strike, lg.right, d), lg.qty, fill)
                tr.n_junk += tag not in ("mid", "natural")
                val += lg.qty * px
            tr.marks[d] = (val - debit) * 100 - 2 * comm
            break
        for i, lg in enumerate(legs):
            r = q.row(ev.ticker, lg.expiry, strike, lg.right, d)
            if r is None:
                tr.n_carried += 1
                continue
            m, tag = IV.mid_mark(r)
            tr.n_junk += tag != "mid"
            last[i] = m
        val = sum(lg.qty * last[i] for i, lg in enumerate(legs))
        tr.marks[d] = (val - debit) * 100 - comm
    if xd not in tr.marks:                          # exit day not on the calendar
        tr.status = "front_missing_exit"
        tr.marks.clear()
        return tr
    tr.pnl = tr.marks[xd]
    return tr


def build_trades(events: list[Event], q: Quotes, sessions: list[date]) -> dict[tuple, list[Trade]]:
    out: dict[tuple, list[Trade]] = {c: [] for c in CONFIGS}
    for ev in sorted(events, key=lambda e: (e.plan.entry, e.ticker)):
        k, why = pick_atm(ev, q)
        for arm, fill, x in CONFIGS:
            out[(arm, fill, x)].append(run_trade(ev, arm, fill, x, k, why, q, sessions))
    return out


def ok(ts: list[Trade]) -> list[Trade]:
    return [t for t in ts if t.status == "ok"]


# ════════════════════════════════════════════════════════════════════════════
# Statistics
# ════════════════════════════════════════════════════════════════════════════

def cluster_ci(values, clusters, n: int = BOOT_N, seed: int = SEED) -> tuple[float, float, int]:
    """CI95 of the pooled event mean, resampling whole clusters with replacement.
    Returns `(lo, hi, number of clusters)`."""
    v = np.asarray(values, float)
    keys = sorted(set(clusters))
    k = len(keys)
    if k < 2 or len(v) < 2:
        return float("nan"), float("nan"), k
    pos = {c: i for i, c in enumerate(keys)}
    ci = np.array([pos[c] for c in clusters])
    sums = np.bincount(ci, weights=v, minlength=k)
    cnts = np.bincount(ci, minlength=k).astype(float)
    idx = np.random.default_rng(seed).integers(0, k, (n, k))
    means = sums[idx].sum(1) / cnts[idx].sum(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi), k


def loso(values, clusters) -> tuple[float, tuple | None]:
    """Minimum pooled mean with one cluster removed, and that cluster."""
    v = np.asarray(values, float)
    cl = list(clusters)
    best = (float("nan"), None)
    for c in sorted(set(cl)):
        keep = np.array([x != c for x in cl])
        if keep.sum() == 0:
            continue
        m = float(v[keep].mean())
        if best[1] is None or m < best[0]:
            best = (m, c)
    return best


def profit_factor(pnls) -> float:
    won = sum(x for x in pnls if x > 0)
    lost = -sum(x for x in pnls if x < 0)
    return won / lost if lost > 0 else float("inf") if won > 0 else float("nan")


@dataclass
class M1:
    n: int
    mean: float
    median: float
    win: float
    pf: float
    mfe: float
    mae: float
    ci: tuple[float, float]
    k: int
    halves: dict
    loso: tuple
    seasons: dict


def m1(trades: list[Trade]) -> M1:
    ts = ok(trades)
    nan = float("nan")
    if not ts:
        return M1(0, nan, nan, nan, nan, nan, nan, (nan, nan), 0,
                  {"H1": (0, nan), "H2": (0, nan)}, (nan, None), {})
    r = [t.ret for t in ts]
    cl = [t.ev.season for t in ts]
    lo, hi, k = cluster_ci(r, cl)
    halves = {}
    for h in ("H1", "H2"):
        sub = [t.ret for t in ts if half_of(t.ev.season) == h]
        halves[h] = (len(sub), float(np.mean(sub)) if sub else nan)
    seasons = {}
    for s in SEASONS:
        sub = [t.ret for t in ts if t.ev.season == s]
        seasons[s] = (len(sub), float(np.mean(sub)) if sub else nan)
    return M1(len(ts), float(np.mean(r)), float(np.median(r)),
              float(np.mean([x > 0 for x in r])), profit_factor([t.pnl for t in ts]),
              float(np.mean([t.mfe for t in ts])), float(np.mean([t.mae for t in ts])),
              (lo, hi), k, halves, loso(r, cl), seasons)


def verdict(ci: tuple[float, float], halves: dict, g1_r: float, bar: float = G1_BAR) -> str:
    """The registered grammar. `halves` maps H1/H2 to `(n, mean)`."""
    lo, hi = ci
    if math.isfinite(hi) and hi < 0:
        return CONTRARY
    h = [halves.get(x, (0, float("nan")))[1] for x in ("H1", "H2")]
    holds = (math.isfinite(lo) and lo > 0
             and all(math.isfinite(m) and m > 0 for m in h))
    if not holds or not math.isfinite(g1_r):
        return NULL
    return EDGE if g1_r <= bar else REWRAP


def open_on(trades: list[Trade], d: date) -> bool:
    return any(t.entry <= d <= t.exit_day for t in trades)


@dataclass
class G1:
    common: int
    r: float
    r_ci: tuple[float, float]
    t1: float
    t1_ci: tuple[float, float]


def g1_read(trades: list[Trade], book_axis: list[date], book_daily: list[float],
            trading: list[date]) -> G1:
    """Sleeve daily MTM change (every open event, one unit each) against the
    book's daily MTM change, on the book sessions where an event is open. The
    sleeve's level on a book session is its level at the last trading day on or
    before it; no later row enters."""
    ts = ok(trades)
    if not ts or not book_axis:
        nan2 = (float("nan"), float("nan"))
        return G1(0, float("nan"), nan2, float("nan"), nan2)
    s = np.asarray(IV.on_axis(ts, book_axis, trading), float)
    b = np.asarray(book_daily, float)
    opened = np.array([open_on(ts, d) for d in book_axis], dtype=bool)
    st = IV.tail_stats(b[opened], s[opened], BLOCK, BOOT_N, SEED)
    return G1(int(opened.sum()), st.r_all, st.r_all_ci, st.t1, st.t1_ci)


def pbo_matrix(trades: dict[tuple, list[Trade]], seasons=SEASONS,
               S: int = PBO_S) -> tuple[np.ndarray, int, int]:
    """Rows = registered seasons by report date (fixed, never by outcome),
    columns = the 8 configs, cell = the season's mean return (0 when the config
    kept no event that season). Trimmed from the head, or zero-padded at the
    head, to a multiple of S. Returns `(M, trimmed, padded)`."""
    cols = []
    for c in CONFIGS:
        by: dict[tuple, list[float]] = defaultdict(list)
        for t in ok(trades.get(c, [])):
            by[t.ev.season].append(t.ret)
        cols.append([float(np.mean(by[s])) if by.get(s) else 0.0 for s in seasons])
    M = np.array(cols, dtype=float).T
    if M.shape[0] >= S:
        trim = M.shape[0] % S
        return M[trim:], trim, 0
    padded, k = pbo_mod.pad_head(M, S)
    return padded, 0, k


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

_f, _ci, hdr = IV._f, IV._ci, IV.hdr


def cfg_label(c: tuple) -> str:
    a, f, x = c
    return f"ARM {a} {f:<7} exit {x:<3}"


def manifest_line(rows: list[dict], path: Path = MANIFEST) -> str:
    if not path.exists():
        return f"fetch manifest: {path.relative_to(ROOT)} ABSENT"
    mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    stamps = [r.get("fetched_at") or "" for r in rows if r.get("fetched_at")]
    last = rows[-1] if rows else {}
    st = Counter(r.get("status", "") for r in rows)
    return (f"fetch manifest: {path.relative_to(ROOT)}  mtime {mtime:%Y-%m-%dT%H:%M:%SZ}  "
            f"latest fetched_at {max(stamps) if stamps else '—'}  last row "
            f"{last.get('ticker', '')} {last.get('expiration', '')} {last.get('strike', '')}"
            f"{last.get('opt_type', '')} {last.get('status', '')}  status {dict(st)}")


def print_census(tps: dict, events: list[Event], unk_events: list[Event],
                 trades: dict, passed: dict) -> None:
    hdr("CENSUS — events planned and dropped (read before any outcome)")
    print(f"   {'name':<6}{'ev':>4}{'unk':>5}{'seal':>5}{'other':>6}{'kept':>6}")
    tot = Counter()
    for t, tp in tps.items():
        other = sum(v for k, v in tp.dropped.items() if k not in ("unknown_session", "sealed"))
        row = dict(ev=tp.events_in_window, unk=tp.dropped["unknown_session"],
                   seal=tp.dropped["sealed"], other=other, kept=len(tp.plans))
        tot.update(row)
        print(f"   {t:<6}{row['ev']:>4}{row['unk']:>5}{row['seal']:>5}{row['other']:>6}"
              f"{row['kept']:>6}   {tp.close_source or 'NO CLOSES'}")
    print(f"   {'TOTAL':<6}{tot['ev']:>4}{tot['unk']:>5}{tot['seal']:>5}{tot['other']:>6}"
          f"{tot['kept']:>6}")
    reasons = Counter()
    for tp in tps.values():
        reasons.update({k: v for k, v in tp.dropped.items() if k not in ("unknown_session", "sealed")})
    print(f"   planner drops other than unknown/sealed: {dict(reasons) or 0}")
    print(f"   events with no run-up session after entry: {tot['kept'] - len(events)}")
    print(f"   unknown-session events planned as amc (secondary only): {len(unk_events)}")
    reb = sum(tp.rebased for tp in tps.values())
    unconf = sum(tp.basis_count("basis_unconfirmed") for tp in tps.values())
    unchk = sum(tp.basis_count("basis_unchecked") for tp in tps.values())
    print(f"   close basis: {reb} event(s) close_rebased onto the option chain's unadjusted "
          f"Price~ ({', '.join(f'{t} {tp.rebased}' for t, tp in tps.items() if tp.rebased) or '-'}"
          f"); {unconf} basis_unconfirmed and {unchk} basis_unchecked kept their close")
    print(f"   ATM ladder: candidates passed over before the ATM (failed / unlisted / unquoted "
          f"at entry): {passed}")
    seasons = Counter(e.season for e in events)
    per = "  ".join(f"{season_label(s)} {seasons.get(s, 0)}" for s in SEASONS)
    print("   events per season: " + per)
    print("\n   per config: kept, and every drop by reason")
    for c in CONFIGS:
        ts = trades[c]
        st = Counter(t.status for t in ts)
        nok = st.pop("ok", 0)
        junk = sum(t.n_junk for t in ok(ts))
        carried = sum(t.n_carried for t in ok(ts))
        print(f"   {cfg_label(c)} events {len(ts)}  kept {nok}  junk-quote legs {junk}  "
              f"carried marks {carried}")
        for r in LEG_REASONS:
            if st.get(r):
                flag = "   <- back expiry not yet listed/quoted on the entry day" \
                    if r == "back_not_quoted_at_entry" else ""
                print(f"        {r:<28}{st[r]:>5}{flag}")
        for r, n in st.items():
            if r not in LEG_REASONS:
                print(f"        {r:<28}{n:>5}")


def print_m1(trades: dict) -> dict:
    hdr("M1 — RETURN PER ARM (return = P&L / entry debit; CI clustered by season)")
    print(f"   cluster bootstrap over report-date seasons, {BOOT_N} draws, seed {SEED}; "
          f"commission ${COMMISSION:.2f}/contract/side in P&L, not in the debit")
    print(f"   {'config':<26}{'n':>4}{'mean':>8}{'median':>8}{'win':>6}{'PF':>6}{'MFE':>7}"
          f"{'MAE':>7}  {'CI95':<18}{'k':>3}  {'H1 n/mean':>13}{'H2 n/mean':>13}  LOSO min")
    out = {}
    for c in CONFIGS:
        r = m1(trades[c])
        out[c] = r
        (n1, h1), (n2, h2) = r.halves["H1"], r.halves["H2"]
        lo_s = f"{_f(r.loso[0])} ({season_label(r.loso[1]) if r.loso[1] else '—'})"
        print(f"   {cfg_label(c):<26}{r.n:>4}{_f(r.mean):>8}{_f(r.median):>8}"
              f"{_f(r.win, '.2f'):>6}{_f(r.pf, '.2f'):>6}{_f(r.mfe):>7}{_f(r.mae):>7}  "
              f"{_ci(r.ci, '+.3f'):<18}{r.k:>3}  {n1:>4}/{_f(h1):>7}  {n2:>4}/{_f(h2):>7}  {lo_s}")
    print("   k = seasons holding a kept event; with ~11 clusters the CI is wide")
    print("\n   per season, graded configs (n / mean return):")
    for a in ARMS:
        r = out[GRADED[a]]
        print(f"   ARM {a}: " + "  ".join(f"{season_label(s)} {r.seasons.get(s, (0, 0))[0]}/"
                                          f"{_f(r.seasons.get(s, (0, float('nan')))[1], '+.2f')}"
                                          for s in SEASONS))
    return out


def print_per_name(trades: dict) -> None:
    hdr("PER NAME — graded configs, printed, no per-name verdict")
    names = sorted({t.ev.ticker for c in CONFIGS for t in trades[c]})
    print(f"   {'name':<6}" + "".join(f"{'ARM ' + a + ' n':>9}{'mean':>8}" for a in ARMS))
    for nm in names:
        line = f"   {nm:<6}"
        for a in ARMS:
            ts = [t for t in ok(trades[GRADED[a]]) if t.ev.ticker == nm]
            line += f"{len(ts):>9}{_f(float(np.mean([t.ret for t in ts])) if ts else None):>8}"
        print(line)


def print_g1(label: str, g: G1) -> None:
    print(f"\n-- {label}")
    print(f"   common sessions with an event open: {g.common}")
    print(f"   G1 corr(sleeve, book) {_f(g.r)}  CI95 {_ci(g.r_ci, '+.3f')} (stationary "
          f"blocks mean {BLOCK}, {BOOT_N} paths, seed {SEED})")
    print(f"   sleeve mean $/session on the book's worst {TAIL:.0%}: {_f(g.t1, '+.2f')}  "
          f"CI95 {_ci(g.t1_ci)}")
    print(f"   G1 at <= {G1_BAR:.2f}: {g1_word(g.r, G1_BAR)};  at <= {G1_ALT_BAR:.2f}: "
          f"{g1_word(g.r, G1_ALT_BAR)}")


def g1_word(r: float, bar: float) -> str:
    if not math.isfinite(r):
        return "NOT EVALUABLE"
    return "PASS" if r <= bar else "FAIL"


def write_csv(path: Path, trades: dict) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["ticker", "ann_date", "session", "unknown_as_amc", "season", "half", "e", "entry",
            "runup", "close_adj", "basis_factor", "close_entry", "front", "back", "strike", "arm", "fill", "exit_rule",
            "exit_day", "status", "debit", "pnl", "ret", "mfe_share", "mae_share",
            "junk_legs", "carried_marks"]
    n = 0
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for c, ts in trades.items():
            for t in ts:
                p, okk = t.ev.plan, t.status == "ok"
                w.writerow([t.ev.ticker, t.ev.ann_date, t.ev.raw_session, int(t.ev.unknown),
                            season_label(t.ev.season), half_of(t.ev.season), p.e, p.entry,
                            t.ev.runup, IV._r(p.close_adj), p.factor, IV._r(p.close), p.front, p.back,
                            "" if t.strike is None else t.strike, t.arm, t.fill, t.exit_rule,
                            t.exit_day, t.status, IV._r(t.debit) if t.debit else "",
                            IV._r(t.pnl) if okk else "", IV._r(t.ret), IV._r(t.mfe),
                            IV._r(t.mae), t.n_junk, t.n_carried])
                n += 1
    return n


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def load_inputs(tickers) -> tuple[list[date], dict, dict, dict, list[str]]:
    sessions = FEL.sessions_from_calendar()
    events_by, closes_by, prices_by, absent = {}, {}, {}, []
    for t in tickers:
        evs = FEL.read_events(t)
        if not evs:
            absent.append(t)
            continue
        events_by[t] = evs
        closes_by[t] = FEL.load_closes(t)
        prices_by[t] = FEL.price_index(t, CACHE_DIR)
    return sessions, events_by, closes_by, prices_by, absent


def main() -> int:
    from scripts.backtest_study.f4_deployment import account_sim as AS
    from scripts.backtest_study.lib.book import load_book

    print("earnings_vol — does a long straddle or a calendar across earnings pay, "
          "without re-wrapping the book?")
    print(f"registration: {REGISTRATION} (accepted by default {ACCEPTED})")
    print(f"seed {SEED}; season-cluster bootstrap {BOOT_N} draws; G1 stationary blocks mean "
          f"{BLOCK}, {BOOT_N} paths")
    print(f"commission ${COMMISSION:.2f} per contract per side; fills at mid, natural printed "
          f"beside; junk quote -> Latest (simulate._is_junk_quote)")
    mrows = read_manifest()
    print(manifest_line(mrows))
    if FEL.SEAL_START != SEAL_START:
        print(f"WARNING: fetch_earnings_legs.SEAL_START {FEL.SEAL_START} != era {SEAL_START}")
    print("Cache only, no fetch, no model price. A report date is treated as known five "
          "sessions ahead; a moved report is a risk the data cannot show. Nothing ships.")

    sessions, events_by, closes_by, prices_by, absent = load_inputs(UNIVERSE)
    print(f"sessions: agent-trading SPY history, {sessions[0]} .. {sessions[-1]}; names with no "
          f"earnings file: {absent or 'none'}")
    rescaled = FEL.read_rescaled()
    kw = dict(sessions=sessions, events_by=events_by, closes_by=closes_by, prices_by=prices_by,
              rescaled=rescaled)
    events, tps = plan_events(UNIVERSE, include_unknown=False, **kw)
    all_unk, _ = plan_events(UNIVERSE, include_unknown=True, **kw)
    unk_events = [e for e in all_unk if e.unknown]

    q = Quotes(CACHE_DIR, UL.load(CACHE_DIR / UL.FILENAME), FEL.manifest_failed(MANIFEST))
    trades = build_trades(events, q, sessions)
    trades_unk = build_trades(unk_events, q, sessions)
    passed = Counter(s for e in events for _, s in FEL.resolve_atm(e.plan, q.status).passed)
    print_census(tps, events, unk_events, trades, dict(passed))

    sealed = sorted((t, a, s) for t, tp in tps.items() for a, s in tp.sealed)
    hdr(f"FORWARD — events with E on or after {SEAL_START} (sealed, never in-sample)")
    listed = ", ".join(f"{t} {a} {s}" for t, a, s in sealed) or "none"
    print(f"   {len(sealed)} event(s): {listed}")
    print("   forward read: STILL-OPEN")

    # --- the book ---------------------------------------------------------
    st = AS.load_settings(AS.DEFAULT_CONFIG)
    recs, diag = load_book()
    era = diag.get("era")
    hdr(f"THE BOOK — era {era}")
    print(f"   {era_mod.seal_line(diag.get('seal', {'rows': 0, 'dates': 0}))}  "
          f"(this study is not a named seal reader)")
    print(f"   load_book: {len(recs)} rows on {len({r['date'] for r in recs})} signal dates")
    print(f"   account_sim: capital ${st.capital:,.0f}, risk {st.risk_pct:.0%}, per-position "
          f"{st.per_pos_cap:.2f}, net cap {IV.REGISTERED_NET_CAP:.2f} (registered cell; the yml "
          f"carries {st.net_cap:.2f}), ARM R, F1, no compounding")
    book = IV.deployed_book(recs, st, IV.REGISTERED_NET_CAP, "deployed (TARGET_POSITION, gross)")
    print(f"   deployed book: {len(book.positions)} positions marked, {book.n_unmarkable} "
          f"unmarkable dropped; sessions {book.axis[0]} .. {book.axis[-1]} ({len(book.axis)})")
    print(f"   G-MTM (TARGET_POSITION): {'PASS' if not book.mismatches else 'FAIL'}"
          f" ({len(book.mismatches)} mismatches)")
    if book.mismatches:
        print("\nREFUSED — G-MTM failed on the graded book; the tolerance is never widened.")
        return EXIT_GMTM

    res = print_m1(trades)
    print_per_name(trades)

    hdr("G1 — CORRELATION WITH THE DEPLOYED BOOK")
    g1s = {}
    for c in CONFIGS:
        g1s[c] = g1_read(trades[c], book.axis, book.daily, sessions)
        print_g1(f"{cfg_label(c)} vs {era} deployed book", g1s[c])

    # --- secondaries -------------------------------------------------------
    hdr("SECONDARY TOKENS — printed, labelled secondary, no verdict")
    secondary = []
    for a in ARMS:
        nat = (a, "natural", "E")
        secondary.append((f"ARM {a} natural fill", verdict(res[nat].ci, res[nat].halves,
                                                           g1s[nat].r)))
        ru = (a, "mid", "E-1")
        secondary.append((f"ARM {a} run-up exit (close of E-1)",
                          verdict(res[ru].ci, res[ru].halves, g1s[ru].r)))
        pool = trades[GRADED[a]] + trades_unk[GRADED[a]]
        mu = m1(pool)
        gu = g1_read(pool, book.axis, book.daily, sessions)
        print(f"   ARM {a} with unknown-as-amc events: n {mu.n} (+{len(ok(trades_unk[GRADED[a]]))})"
              f"  mean {_f(mu.mean)}  CI95 {_ci(mu.ci, '+.3f')} k {mu.k}  H1 "
              f"{_f(mu.halves['H1'][1])}  H2 {_f(mu.halves['H2'][1])}  G1 {_f(gu.r)}")
        secondary.append((f"ARM {a} with unknown-as-amc events", verdict(mu.ci, mu.halves, gu.r)))
        g = GRADED[a]
        secondary.append((f"ARM {a} at the 0.10 gate",
                          verdict(res[g].ci, res[g].halves, g1s[g].r, G1_ALT_BAR)))
    for lab, tok in secondary:
        print(f"   {lab}: {tok}")

    # --- PBO ---------------------------------------------------------------
    hdr("PBO — 2 arms x 2 fills x 2 exits = 8 configs (context, no verdict)")
    M, trim, pad = pbo_matrix(trades)
    print(f"   matrix: {len(SEASONS)} registered seasons x {len(CONFIGS)} configs, cell = the "
          f"season's mean return (0 with no kept event); trimmed {trim} head row(s), padded "
          f"{pad}; S = {PBO_S}")
    try:
        pr = pbo_mod.cscv(M, S=PBO_S)
        print(f"   PBO {pr.pbo:.3f} over {pr.n_combinations} combinations "
              f"(logit = 0 in {pr.n_at_zero}); degradation slope {_f(pr.slope)}; "
              f"P(OOS < 0 | IS best) {_f(pr.prob_loss, '.3f')}")
        print("   IS-best share: " + "  ".join(f"{a}/{f}/{x} {s:.2f}" for (a, f, x), s
                                               in zip(CONFIGS, pr.selection_share())))
    except ValueError as exc:
        print(f"   PBO not computed: {exc}")

    n = write_csv(OUT_CSV, {**trades, **{("unk",) + c: v for c, v in trades_unk.items()}})
    print(f"\nper-event CSV: {OUT_CSV.relative_to(ROOT)} ({n} rows, every arm, fill and exit, "
          f"dropped events included with their status; unknown_as_amc=1 rows are secondary)")

    hdr("VERDICT")
    toks = {}
    for a in ARMS:
        g = GRADED[a]
        r = res[g]
        toks[a] = verdict(r.ci, r.halves, g1s[g].r)
        print(f"  ARM {a} (mid, exit E, in-sample): n {r.n}  mean {_f(r.mean)}  CI95 "
              f"{_ci(r.ci, '+.3f')} over {r.k} seasons;  H1 {_f(r.halves['H1'][1])}  H2 "
              f"{_f(r.halves['H2'][1])};  G1 corr {_f(g1s[g].r)} -> {g1_word(g1s[g].r, G1_BAR)}")
    print(f"  >>> earnings_vol ARM S {toks['S']} / ARM K {toks['K']} <<<")
    for lab, tok in secondary:
        print(f"  secondary, {lab}: {tok}")
    print(f"  forward ({len(sealed)} sealed events): STILL-OPEN")
    print("  Nothing ships.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
