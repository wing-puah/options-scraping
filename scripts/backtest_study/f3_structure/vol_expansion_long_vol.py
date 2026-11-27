"""vol_expansion_long_vol — after a SPY E-VOL onset, does a long straddle or a 1x2 backspread pay, and beat calm weeks?

Registration: `research/pre-registrations/f3_structure/vol_expansion_long_vol.md`
(accepted by the operator on the defaults 2026-11-27, second read passed). That
file is the spec; every constant and verdict word here is its. Where the build
needed a ruling the file did not give, the ruling is folded into the
registration beside the clause it amends, tagged `Resolved at build
(2026-11-27)`. RESEARCH TIER: nothing ships from this study.

WHAT IT COMPUTES. An onset `D` is a session whose frozen mechanical vol label
(`lib/mech_regime.py::compute_mech_table`, `mech_vol == "E-VOL"`) is `E-VOL`
after five labelled, non-`E-VOL` sessions. On the next close `F` it opens three
structures on SPY's standard monthly nearest 30 DTE (at least 21): a long ATM
straddle (`ARM S`), a call 1x2 (`ARM BC`, -1 ATM +2 at spot x 1.05) and a put
1x2 (`ARM BP`, -1 ATM +2 at spot x 0.95). Each closes at `F + 5` sessions on
its own fixed exit. `ARM C` opens the same three structures on calm ISO weeks.
R is net P&L over the most the unit can lose at expiry, commission included.

OWN FIXED EXIT. `price_trade` marks every leg on the exit session with
`selloff_put_diagonal.leg_mark`. It never calls the frozen harness,
`_simulate`, `_exit_basis` or `book.py`'s profiles, so a credit 1x2 cannot
reach `CREDIT_PROD`. `helpers._defined_risk_bounds` is called for a count only.

THE AWAIT GATE. `Book.price` raises until `Book.open_outcomes` has seen every
headline entry (the three arms and `ARM C`) cached or refused. While it is
shut the run prints its census and `NOT BUILT — AWAITING SCRAPE`. A
non-headline cell still awaiting prints `NOT BUILT` for that cell, and PBO
prints "not computed".

THE CUT. Every in-sample series is cut at 2026-09-22 before anything is
computed: both label tables, SPY's closes, and every option history
(`CutChain`). The gap 2026-09-23 to 2026-11-26 is in no population.

REUSED, NEVER COPIED. Label: `compute_mech_table`. Expiry: `mechanical_benchmark.
monthly_for`. Strikes: `daily_vol_structure.walk_strike` on a fixed $1 step.
Entry: `simulate.entry_day_fill`, `_monotonicity_violation`; count only:
`_entry_outside_bounds`, `_defined_risk_bounds`. Exit mark:
`selloff_put_diagonal.leg_mark`, with the mark's own date checked through
`simulate._snap_asof` and `junk_day_mark`. Holm: `selloff_put_diagonal.holm`.
PBO: `lib/pbo.py` `cscv`, `ratio_metric`, `pad_head`. Spot:
`state_map.build_cal`. No model price anywhere.

No code here fetches. The fetch plan is `plan()`, imported by
`scripts/collector/study_legs/f3_structure/fetch_vol_expansion_legs.py`.

Usage:
  python3 -m scripts.backtest_study run vol_expansion_long_vol
  python3 -m scripts.backtest_study run vol_expansion_long_vol --dry-run
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import math
import os
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import compute_mech_table  # noqa: E402
from scripts.backtest import simulate as SIM  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _defined_risk_bounds  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f1_selection.regime import selloff_put_diagonal as SPD  # noqa: E402
from scripts.backtest_study.f1_selection.regime import state_map as SM  # noqa: E402
from scripts.backtest_study.f3_structure import daily_vol_structure as DVS  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402

REGISTRATION = "research/pre-registrations/f3_structure/vol_expansion_long_vol.md"
ACCEPTED = "2026-11-27"

#: GE (inputs) exits 3; GL (label agreement) exits 2. Both are designed refusals.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
EXIT_GL, EXIT_GE = 2, 3

# ── registered constants (the registration's numbers; never re-chosen) ──────
TICKER = "SPY"
IN_SAMPLE = (date(2022, 3, 1), date(2026, 9, 22))
CUT = IN_SAMPLE[1]
GAP = (date(2026, 9, 23), date(2026, 11, 26))
FORWARD_START = date(2026, 11, 27)
SUNSET = date(2031, 11, 27)
REARM = 5
HOLD, HOLD_LONG = 5, 10
HOLDS = (HOLD, HOLD_LONG)
#: The sessions after `D` that every candidate entry needs on or before the cut.
D_PLUS = 1 + HOLD_LONG
#: Expiry rules: `monthly_for(F, dte, band)`.
EXPIRY_RULES = {"H": (30, (21, 122)), "L": (60, (45, 122))}
EXPIRY_LABEL = {"H": "headline ~30 DTE (>=21)", "L": "~60 DTE (>=45)"}
STEP = 1.0
WING = {"BC": 1.05, "BP": 0.95}
COMMISSION = 0.65            # $ per contract per side
STOP_DOLLARS = 1000.0
C0_ARM = 20
C0_CALM = 60
BOOT_N = 10_000
SEED = 20261127
ALPHA = 0.05
PBO_MAX = 0.5
PBO_S = 20
PBO_QUARTERS = ((2022, 1), (2026, 3))
SELLOFF_WINDOWS = DVS.SELLOFF_WINDOWS
EXIT_DROPS = ("no_exit_quote", "stale_exit_mark")
ARMS = ("S", "BC", "BP")
CONTRACTS = {"S": 2, "BC": 3, "BP": 3}


@dataclasses.dataclass(frozen=True)
class Cell:
    n: int
    arm: str
    hold: int
    expiry: str                        # "H" headline | "L" 60 DTE


CELLS = tuple(Cell(i + 1, arm, hold, exp)
              for i, (arm, exp, hold) in enumerate(
                  (a, e, h) for a in ARMS for e in ("H", "L") for h in HOLDS))
HEADLINE = {arm: next(c for c in CELLS if c.arm == arm and c.hold == HOLD and c.expiry == "H")
            for arm in ARMS}

# ── tokens ───────────────────────────────────────────────────────────────────
LVP = "LONG-VOL-PAYS"
PNS = "PAYS-NOT-SIGNAL"
CONTRARY = "CONTRARY"
NULL = "NULL"
UNDERPOWERED = "UNDERPOWERED"
STILL_OPEN = "STILL-OPEN"
NOT_BUILT = "NOT BUILT — AWAITING SCRAPE"
PEEK_NOTE = "VIX direction after 23 in-window onsets was printed before registration"
CAVEATS = ("A long-straddle `CONTRARY` is not evidence for selling straddles, because no "
           "short side is graded.",
           "A backspread result says nothing about tail loss beyond five sessions or about "
           "margin.")
BANNER = {
    "S": "ARM S (ATM straddle after E-VOL onset, D+1 close to D+6 close, monthly ~30 DTE, "
         "2022-03-01 to 2026-09-22)",
    "BC": "ARM BC (call 1x2 -1 ATM +2 at 1.05, same)",
    "BP": "ARM BP (put 1x2 -1 ATM +2 at 0.95, same)",
}

# ── inputs ───────────────────────────────────────────────────────────────────
INSAMPLE_TABLE = ROOT / "backtests" / "mech_regime" / "spy_base_rate_daily.csv"
FORWARD_TABLE = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"
SPY_CSV = ROOT / "backtests" / "state_map" / "SPY.csv"
RW_HISTORY = ROOT / "backtests" / "regime_watch" / "history.csv"
RW_BACKFILLED = ROOT / "backtests" / "regime_watch" / "backfilled.csv"
OUT_DIR = ROOT / "backtests" / "study_output"
TRADES_CSV = OUT_DIR / "vol_expansion_long_vol-trades.csv"
FETCH_CMD = "python3 scripts/collector/study_legs/f3_structure/fetch_vol_expansion_legs.py"


class AwaitingScrape(RuntimeError):
    """An outcome was asked for while a headline entry awaits a fetch."""


class Refused(RuntimeError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _d(s) -> date:
    return s if isinstance(s, date) else date.fromisoformat(str(s)[:10])


# ════════════════════════════════════════════════════════════════════════════
# The label, onsets and calm weeks — pure
# ════════════════════════════════════════════════════════════════════════════

def read_table(path: Path) -> list[dict]:
    """`date, spy_close, vix_close` rows as strings, file order."""
    with Path(path).open(newline="") as fh:
        return [{"date": r["date"][:10], "spy_close": r.get("spy_close", ""),
                 "vix_close": r.get("vix_close", "")} for r in csv.DictReader(fh)]


def vol_labels(rows: list[dict], end: date | None = None) -> list[tuple[date, str | None]]:
    """`[(session, mech_vol)]` from `compute_mech_table`, oldest first.

    Rows after `end` are cut BEFORE the label is computed. A session is a row
    with a SPY close (`compute_mech_table` drops the rest)."""
    keep = [r for r in rows if end is None or _d(r["date"]) <= end]
    fd, tmp = tempfile.mkstemp(suffix=".csv", prefix="vol_expansion_")
    try:
        with os.fdopen(fd, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["date", "spy_close", "vix_close"])
            w.writeheader()
            for r in keep:
                w.writerow(r)
        table = compute_mech_table(tmp)
    finally:
        os.unlink(tmp)
    return [(_d(r["date"]), r["mech_vol"]) for r in table]


def find_onsets(labels: list[tuple[date, str | None]]) -> tuple[list[date], Counter]:
    """Onset sessions, and what blocked other `E-VOL` sessions.

    An onset is `E-VOL` where none of the 5 sessions before is `E-VOL` and all 5
    carry a vol label. An `E-VOL` session with no `E-VOL` before it but an
    unlabelled (or missing) prior session is `no_rearm_history`; one inside a
    run is `in_run`."""
    out, why = [], Counter()
    for i, (d, v) in enumerate(labels):
        if v != "E-VOL":
            continue
        prior = [labels[j][1] for j in range(max(0, i - REARM), i)]
        if "E-VOL" in prior:
            why["in_run"] += 1
        elif len(prior) < REARM or any(p is None for p in prior):
            why["no_rearm_history"] += 1
        else:
            out.append(d)
    return out, why


def find_calm_weeks(labels: list[tuple[date, str | None]], lo: date,
                    hi: date | None) -> tuple[list[date], Counter]:
    """`ARM C` entry sessions and the weeks that fail.

    Each ISO week's first session `D`, when `D` is inside `[lo, hi]`. Calm: no
    `E-VOL` on `D` or the 5 sessions before, all 6 labelled. A week failing it
    is counted, by reason."""
    first: dict[tuple, int] = {}
    for i, (d, _v) in enumerate(labels):
        first.setdefault(d.isocalendar()[:2], i)
    out, why = [], Counter()
    for _wk, i in sorted(first.items(), key=lambda kv: kv[1]):
        d = labels[i][0]
        if d < lo or (hi is not None and d > hi):
            continue
        six = [labels[j][1] for j in range(max(0, i - REARM), i + 1)]
        if "E-VOL" in six:
            why["evol_in_six"] += 1
        elif len(six) < REARM + 1 or any(v is None for v in six):
            why["unlabelled_in_six"] += 1
        else:
            out.append(d)
    return out, why


def gl_mismatch(lab_a, lab_b, end: date) -> tuple[date | None, list[date], list[date]]:
    """Gate GL: `(start, only_in_a, only_in_b)` onset dates from the production
    table's eleventh row to `end`."""
    if len(lab_b) < 11:
        return None, [], []
    start = lab_b[10][0]
    oa = {d for d in find_onsets(lab_a)[0] if start <= d <= end}
    ob = {d for d in find_onsets(lab_b)[0] if start <= d <= end}
    return start, sorted(oa - ob), sorted(ob - oa)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ════════════════════════════════════════════════════════════════════════════
# Option histories, cut at a date
# ════════════════════════════════════════════════════════════════════════════

class CutChain:
    """A chain whose histories stop at `end` (None: no cut). The in-sample run
    reads no option quote after 2026-09-22 through it."""

    def __init__(self, chain, end: date | None):
        self.chain, self.end = chain, end
        self.idx = chain.idx

    def cached(self, ticker, expiry, strike, opt_type) -> bool:
        return self.chain.cached(ticker, expiry, strike, opt_type)

    def strikes(self, ticker, expiry):
        return self.chain.strikes(ticker, expiry)

    def history(self, leg: Leg):
        series, details = self.chain.history(leg)
        if self.end is None:
            return series, details
        return ([(d, m) for d, m in series if d <= self.end],
                {d: r for d, r in details.items() if d <= self.end})


# ════════════════════════════════════════════════════════════════════════════
# Selection — reads F's close and the listing as of F, nothing later
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass
class Entry:
    """One `(D, expiry rule)` entry: the expiry, the strikes and each arm's
    status (`built` | `await` | `drop`)."""
    signal: date
    fill: date
    exits: dict                        # hold -> exit session
    kind: str
    expiry: date | None = None
    spot: float | None = None
    atm: float | None = None
    wing: dict = dataclasses.field(default_factory=dict)       # arm -> strike
    status: dict = dataclasses.field(default_factory=dict)     # arm -> status
    reason: dict = dataclasses.field(default_factory=dict)     # arm -> reason
    fetch: dict = dataclasses.field(default_factory=dict)      # arm -> ((opt, e, k), ...)
    refetch: dict = dataclasses.field(default_factory=dict)

    @property
    def dte(self) -> int | None:
        return (self.expiry - self.fill).days if self.expiry else None


def _leg(opt: str, expiry: date, strike: float, qty: int) -> Leg:
    return Leg(qty, TICKER, expiry, float(strike), opt)


def select_entry(chain, evidence: set[str], signal: date, fill: date, exits: dict,
                 spot: float | None, kind: str) -> Entry:
    """Expiry and strikes for one entry. No price is read."""
    en = Entry(signal, fill, exits, kind, spot=spot)

    def drop_all(why):
        for a in ARMS:
            en.status[a], en.reason[a] = "drop", why
        return en

    if spot is None:
        return drop_all("no_spot")
    dte, band = EXPIRY_RULES[kind]
    expiry = MB.monthly_for(fill, dte, band)
    if expiry is None:
        return drop_all("no_monthly")
    en.expiry = expiry
    atm = DVS.walk_strike(chain, evidence, TICKER, expiry, spot, STEP, fill, ("Call", "Put"))
    if atm.status == "drop":
        return drop_all(atm.reason)
    en.atm = atm.strike if atm.status == "built" else None
    for a in ARMS:
        sels = [atm]
        if a != "S":
            opt = "Call" if a == "BC" else "Put"
            w = DVS.walk_strike(chain, evidence, TICKER, expiry, spot * WING[a], STEP, fill,
                                (opt,))
            if w.status == "built" and atm.status == "built":
                beyond = w.strike > atm.strike if a == "BC" else w.strike < atm.strike
                if not beyond:
                    w = DVS.Sel("drop", reason="no_listed_strike")
            if w.status == "built":
                en.wing[a] = w.strike
            sels.append(w)
        drops = [s for s in sels if s.status == "drop"]
        if drops:
            en.status[a], en.reason[a] = "drop", drops[0].reason
            continue
        fetch = tuple(f for s in sels for f in s.fetch)
        if fetch:
            en.status[a] = "await"
            en.reason[a] = next(s.reason for s in sels if s.status == "await")
            en.fetch[a] = fetch
            en.refetch[a] = tuple(f for s in sels for f in s.refetch)
            continue
        en.status[a], en.reason[a] = "built", ""
    return en


def structure_legs(arm: str, expiry: date, atm: float, wing: float | None) -> list[Leg]:
    if arm == "S":
        return [_leg("Call", expiry, atm, 1), _leg("Put", expiry, atm, 1)]
    opt = "Call" if arm == "BC" else "Put"
    return [_leg(opt, expiry, atm, -1), _leg(opt, expiry, wing, 2)]


# ════════════════════════════════════════════════════════════════════════════
# Pricing — one clock at entry, own fixed exit
# ════════════════════════════════════════════════════════════════════════════

def max_loss_points(arm: str, atm: float, wing: float | None, net: float) -> float:
    """`L`: the most one unit can lose at expiry, in option points."""
    if arm == "S":
        return net
    width = (wing - atm) if arm == "BC" else (atm - wing)
    return width + net


def exit_mark(chain, leg: Leg, day: date):
    """`(price, tag)` on `day`, or a drop reason.

    `selloff_put_diagonal.leg_mark` gives the price. A leg with no row on `day`
    is `no_exit_quote`. The mark's own source date is checked, not only the
    tag: a carried mark (`barchart_stale`, or any snap dated before `day`) is
    `stale_exit_mark`."""
    series, details = chain.history(leg)
    row = details.get(day)
    if row is None:
        return "no_exit_quote"
    m = SPD.leg_mark(chain, leg, day, None, None)
    if m is None:
        return "no_exit_quote"
    if SIM._is_junk_quote(row):
        jm = SIM.junk_day_mark(row, day, series, details, leg.expiration)
        src = jm[2] if jm is not None else None
    else:
        _p, src = SIM._snap_asof({"k": series}, "k", day, leg.expiration)
    if m[1] == "barchart_stale" or src != day:
        return "stale_exit_mark"
    return m


def _iv(row) -> float | None:
    """A row's cached IV in vol points; a zero or missing IV is None."""
    try:
        v = float((row or {}).get("IV"))
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


def atm_iv(chain, expiry: date, atm: float, day: date) -> float | None:
    """Mean IV of the ATM call and put on `day`, in vol points as cached."""
    vals = []
    for opt in ("Call", "Put"):
        row = chain.history(_leg(opt, expiry, atm, 1))[1].get(day)
        v = _iv(row)
        if v is None:
            return None
        vals.append(v)
    return sum(vals) / 2


@dataclasses.dataclass
class Priced:
    arm: str
    signal: date
    fill: date
    exit: date
    hold: int
    expiry: date
    atm: float
    wing: float | None
    net: float                         # N, points; negative is a credit
    max_loss: float                    # L, points
    exit_value: float
    comm: float                        # $ round trip
    sold_at_bid: bool
    outside_bounds: bool
    mfe: float | None
    mae: float | None
    stop_R: float
    stopped: bool
    move_ratio: float | None
    iv_change: float | None
    spot_fill: float
    tags: Counter

    @property
    def basis(self) -> float:
        return self.max_loss * 100.0 + self.comm

    @property
    def pnl(self) -> float:
        return (self.exit_value - self.net) * 100.0 - self.comm

    @property
    def R(self) -> float:
        return self.pnl / self.basis

    @property
    def pnl_spot(self) -> float:
        return self.pnl / (self.spot_fill * 100.0)


def price_trade(chain, en: Entry, arm: str, hold: int, sessions: list[date],
                spots: dict[date, float]) -> Priced | str:
    """One built entry, one arm, one hold. `Priced`, or a printed drop reason.

    Entry: `entry_day_fill` on F's own closing quote, signed quantity. No leg
    moves to another day. Exit: `exit_mark` on `F + hold`. Never the harness."""
    if en.status.get(arm) != "built":
        raise ValueError(f"cannot price a {en.status.get(arm)} entry")
    exit_day = en.exits[hold]
    if spots.get(en.fill) is None or spots.get(exit_day) is None:
        return "no_spot"
    legs = structure_legs(arm, en.expiry, en.atm, en.wing.get(arm))
    prices, tags = [], []
    for lg in legs:
        fill = SIM.entry_day_fill(chain.history(lg)[1].get(en.fill), lg.qty)
        if fill is None:
            return "no_entry_quote"
        if fill[0] is None:
            return SIM.JUNK_ENTRY_REFUSAL
        prices.append(fill[0])
        tags.append(fill[1])
    if SIM._monotonicity_violation(legs, prices, tags):
        return SIM.NON_MONOTONIC_REFUSAL
    net = sum(lg.qty * p for lg, p in zip(legs, prices))
    L = max_loss_points(arm, en.atm, en.wing.get(arm), net)
    if L <= 0 or (arm == "S" and net <= 0):
        return "nonpositive_max_loss"
    outside = SIM._entry_outside_bounds(_defined_risk_bounds(legs), net)
    sold_bid = any(lg.qty < 0 and t == SIM.CLOSE_SIDE_TAG for lg, t in zip(legs, tags))
    comm = COMMISSION * 2 * sum(abs(lg.qty) for lg in legs)
    basis = L * 100.0 + comm
    marks = []
    tagc = Counter(tags)
    for lg in legs:
        m = exit_mark(chain, lg, exit_day)
        if isinstance(m, str):
            return m
        marks.append(m[0])
        tagc[m[1]] += 1
    exit_value = sum(lg.qty * m for lg, m in zip(legs, marks))
    # the daily path F+1 .. exit: MFE, MAE and the stop cell
    i0 = sessions.index(en.fill)
    path = []
    for day in sessions[i0 + 1:i0 + 1 + hold]:
        ms = [exit_mark(chain, lg, day) for lg in legs]
        if any(isinstance(m, str) for m in ms):
            continue
        v = sum(lg.qty * m[0] for lg, m in zip(legs, ms))
        path.append((v - net) * 100.0 - comm)
    rs = [p / basis for p in path]
    stop = next((p for p in path if p <= -STOP_DOLLARS), None)
    final_pnl = (exit_value - net) * 100.0 - comm
    iv0 = atm_iv(chain, en.expiry, en.atm, en.fill)
    iv1 = atm_iv(chain, en.expiry, en.atm, exit_day)
    s0, s1 = spots[en.fill], spots[exit_day]
    ratio = (abs(math.log(s1 / s0)) / (0.8 * (iv0 / 100.0) * math.sqrt(hold / 252.0))
             if iv0 else None)
    return Priced(arm=arm, signal=en.signal, fill=en.fill, exit=exit_day, hold=hold,
                  expiry=en.expiry, atm=en.atm, wing=en.wing.get(arm), net=net,
                  max_loss=L, exit_value=exit_value, comm=comm, sold_at_bid=sold_bid,
                  outside_bounds=outside,
                  mfe=max(rs) if rs else None, mae=min(rs) if rs else None,
                  stop_R=(stop if stop is not None else final_pnl) / basis,
                  stopped=stop is not None, move_ratio=ratio,
                  iv_change=(iv1 - iv0) if (iv0 is not None and iv1 is not None) else None,
                  spot_fill=s0, tags=tagc)


# ════════════════════════════════════════════════════════════════════════════
# The book — selection memoised; pricing gated
# ════════════════════════════════════════════════════════════════════════════

class Book:
    """Every entry of one population, memoised by `(D, expiry rule)`.

    `price()` refuses until `open_outcomes()` has seen no headline entry
    await. That is the await gate, by construction."""

    def __init__(self, chain, evidence: set[str], labels, spots: dict[date, float],
                 lo: date, hi: date | None, end: date | None, forward: bool = False):
        self.chain, self.evidence, self.spots = chain, evidence, spots
        self.labels = labels
        self.sessions = [d for d, _ in labels]
        self.pos = {d: i for i, d in enumerate(self.sessions)}
        self.lo, self.hi, self.end, self.forward = lo, hi, end, forward
        onsets, self.onset_why = find_onsets(labels)
        calm, self.calm_why = find_calm_weeks(labels, lo, hi)
        if forward:
            # Forward onsets: D and its 5 re-arm sessions on or after FORWARD_START.
            onsets = [d for d in onsets if self.pos[d] >= REARM
                      and self.sessions[self.pos[d] - REARM] >= lo]
        self.onsets_all = [d for d in onsets if d >= lo and (hi is None or d <= hi)]
        self.calm_all = calm
        need = 1 + HOLD if forward else D_PLUS
        self.truncated = Counter()
        self.onsets = self._eligible(self.onsets_all, need, "onset")
        self.calm = self._eligible(self.calm_all, need, "calm")
        self._sel: dict = {}
        self._px: dict = {}
        self._open = False

    def _eligible(self, ds: list[date], need: int, what: str) -> list[date]:
        """In-sample: `D + 11` on or before the cut. Forward: `D + 6` exists
        (an entry still open is counted, not dropped)."""
        out = []
        for d in ds:
            i = self.pos[d]
            if i + need >= len(self.sessions) or (self.end is not None
                                                  and self.sessions[i + need] > self.end):
                self.truncated[what] += 1
                continue
            out.append(d)
        return out

    def entry(self, d: date, kind: str) -> Entry:
        key = (d, kind)
        if key not in self._sel:
            i = self.pos[d]
            fill = self.sessions[i + 1]
            exits = {h: self.sessions[i + 1 + h] for h in HOLDS
                     if i + 1 + h < len(self.sessions)}
            self._sel[key] = select_entry(self.chain, self.evidence, d, fill, exits,
                                          self.spots.get(fill), kind)
        return self._sel[key]

    def onset_entries(self, kind: str) -> list[Entry]:
        return [self.entry(d, kind) for d in self.onsets]

    def calm_entries(self) -> list[Entry]:
        return [self.entry(d, "H") for d in self.calm]

    def headline_awaiting(self) -> int:
        n = 0
        for en in self.onset_entries("H") + self.calm_entries():
            n += sum(en.status[a] == "await" for a in ARMS)
        return n

    def cell_awaits(self, cell: Cell) -> bool:
        return any(en.status[cell.arm] == "await" for en in self.onset_entries(cell.expiry))

    def open_outcomes(self) -> None:
        n = self.headline_awaiting()
        if n:
            raise AwaitingScrape(f"{n} headline arm-entries (onsets and ARM C) await a fetch")
        self._open = True

    def price(self, en: Entry, arm: str, hold: int) -> Priced | str:
        if not self._open:
            raise AwaitingScrape("outcomes are closed until no headline entry awaits")
        key = (en.signal, en.kind, arm, hold)
        if key not in self._px:
            if hold not in en.exits:
                self._px[key] = "open_at_data_end"
            else:
                self._px[key] = price_trade(self.chain, en, arm, hold, self.sessions,
                                            self.spots)
        return self._px[key]

    def priced(self, entries: list[Entry], arm: str, hold: int):
        """`(priced trades, drops Counter, exit-dropped dates)`. Refusals at
        selection count under their own reason."""
        out, drops, xd = [], Counter(), []
        for en in entries:
            st = en.status[arm]
            if st != "built":
                drops[en.reason[arm] if st == "drop" else "await"] += 1
                continue
            p = self.price(en, arm, hold)
            if isinstance(p, str):
                drops[p] += 1
                if p in EXIT_DROPS:
                    xd.append(en.signal)
            else:
                out.append(p)
        return out, drops, xd


def load_spots(end: date | None) -> dict[date, float]:
    """SPY unadjusted closes from `backtests/state_map/SPY.csv`, as
    `state_map.build_cal` reads them, cut at `end`."""
    rows = [r for r in SM.read_series(SPY_CSV) if end is None or _d(r[0]) <= end]
    cal = SM.build_cal(rows, {}, {}, {}, {})
    return {_d(d): float(c) for d, c in zip(cal.dates, cal.close)}


def build_books(chain=None, evidence=None) -> tuple[Book, Book]:
    """`(in-sample, forward)` books on the cache as it stands. Nothing priced."""
    base = chain if chain is not None else NTF.Chain()
    ev = evidence if evidence is not None else NTF.unlisted_evidence()
    lab_in = vol_labels(read_table(INSAMPLE_TABLE), CUT)
    lab_fw = vol_labels(read_table(FORWARD_TABLE), None)
    ins = Book(CutChain(base, CUT), ev, lab_in, load_spots(CUT), IN_SAMPLE[0], IN_SAMPLE[1],
               CUT)
    fwd = Book(CutChain(base, None), ev, lab_fw, load_spots(None), FORWARD_START, None, None,
               forward=True)
    return ins, fwd


def fetch_targets(book: Book, scope: str = "primary") -> list[dict]:
    """Unique uncached contracts the awaiting in-sample entries name.

    `primary`: the headline cells' onsets and `ARM C`. `all`: also the 60-DTE
    onset cells. A contract two entries name is listed once, under the first.
    A shallow cached file carries `needed`, the date that makes
    `fetch_option_histories` re-fetch it. The collector imports this."""
    groups = [("H", book.onset_entries("H"), "onset_H"), ("H", book.calm_entries(), "calm_H")]
    if scope == "all":
        groups.append(("L", book.onset_entries("L"), "onset_L"))
    seen: dict = {}
    needed: dict = {}
    for _kind, ens, cat in groups:
        for en in ens:
            for a in ARMS:
                if en.status[a] != "await":
                    continue
                for o, e, k in en.fetch[a]:
                    key = (o, e, round(float(k), 4))
                    seen.setdefault(key, cat)
                    if (o, e, k) in en.refetch.get(a, ()):
                        d = en.fill - timedelta(days=DVS.REFETCH_MARGIN)
                        needed[key] = min(needed.get(key, d), d)
    return [dict(ticker=TICKER, expiration=e, strike=k, opt_type=o, category=cat,
                 needed=needed.get((o, e, k)))
            for (o, e, k), cat in sorted(seen.items(), key=lambda kv: (kv[0][1], kv[0][2],
                                                                       kv[0][0]))]


def plan(scope: str = "primary") -> list[dict]:
    """The collector's entry point. Selection only; nothing is priced and no
    network is touched."""
    return fetch_targets(build_books()[0], scope)


# ════════════════════════════════════════════════════════════════════════════
# Grading — pure functions on `{date, R}` rows (tested on synthetic rows)
# ════════════════════════════════════════════════════════════════════════════

def month(d) -> str:
    return str(d)[:7]


def quarter(d: date) -> tuple[int, int]:
    return d.year, (d.month - 1) // 3 + 1


def _sign(v: float) -> int:
    return (v > 0) - (v < 0)


def _mean(rows) -> float | None:
    return statistics.fmean(r["R"] for r in rows) if rows else None


def _clusters(rows) -> tuple[np.ndarray, np.ndarray]:
    by: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by[month(r["date"])].append(float(r["R"]))
    keys = sorted(by)
    return (np.array([sum(by[k]) for k in keys], dtype=float),
            np.array([len(by[k]) for k in keys], dtype=float))


def _draw_means(rng, sums: np.ndarray, counts: np.ndarray, n: int) -> np.ndarray:
    k = len(sums)
    idx = rng.integers(0, k, size=(n, k))
    return sums[idx].sum(axis=1) / counts[idx].sum(axis=1)


def p_two_sided(draws: np.ndarray) -> float:
    """Twice the smaller of the share of draws at or below 0 and at or above 0,
    capped at 1."""
    n = len(draws)
    return min(1.0, 2.0 * min(float(np.sum(draws <= 0)), float(np.sum(draws >= 0))) / n)


def _ci(draws: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(lo), float(hi)


def bootstrap(arm_rows: list[dict], calm_rows: list[dict], n: int = BOOT_N,
              seed: int = SEED) -> dict:
    """Month-cluster bootstrap. In each draw the arm's clusters and `ARM C`'s
    clusters are each resampled on their own; the gain is their difference."""
    out = dict(mean=_mean(arm_rows), mean_c=_mean(calm_rows), ci=None, p=None,
               gain=None, gain_ci=None, gain_p=None)
    if not arm_rows:
        return out
    rng = np.random.default_rng(seed)
    a_s, a_c = _clusters(arm_rows)
    da = _draw_means(rng, a_s, a_c, n)
    out["ci"], out["p"] = _ci(da), p_two_sided(da)
    if calm_rows:
        c_s, c_c = _clusters(calm_rows)
        dc = _draw_means(rng, c_s, c_c, n)
        dg = da - dc
        out["gain"] = out["mean"] - out["mean_c"]
        out["gain_ci"], out["gain_p"] = _ci(dg), p_two_sided(dg)
    return out


def in_selloff(d) -> bool:
    d = _d(d)
    return any(a <= d <= b for a, b in SELLOFF_WINDOWS)


def c2_check(arm_rows: list[dict], calm_rows: list[dict]) -> dict:
    """C2: each month holding an arm trade removed in turn, from the arm and
    `ARM C`. The mean (and the gain) must keep the full sample's sign."""
    m, mc = _mean(arm_rows), _mean(calm_rows)
    months = sorted({month(r["date"]) for r in arm_rows})
    mean_ok = m is not None
    gain_ok = m is not None and mc is not None
    folds_m, folds_g = [], []
    for k in months:
        fm = _mean([r for r in arm_rows if month(r["date"]) != k])
        fc = _mean([r for r in calm_rows if month(r["date"]) != k])
        if fm is None or _sign(fm) != _sign(m):
            mean_ok = False
        else:
            folds_m.append(fm)
        if fm is None or fc is None or mc is None or _sign(fm - fc) != _sign(m - mc):
            gain_ok = False
        else:
            folds_g.append(fm - fc)
    return dict(mean=mean_ok, gain=gain_ok, folds_m=folds_m, folds_g=folds_g)


def c3_check(arm_rows: list[dict], calm_rows: list[dict]) -> dict:
    """C3: every `D` in the sell-off windows removed from both; signs kept."""
    m, mc = _mean(arm_rows), _mean(calm_rows)
    a = [r for r in arm_rows if not in_selloff(r["date"])]
    c = [r for r in calm_rows if not in_selloff(r["date"])]
    fm, fc = _mean(a), _mean(c)
    mean_ok = m is not None and fm is not None and _sign(fm) == _sign(m)
    gain_ok = (None not in (m, mc, fm, fc)) and _sign(fm - fc) == _sign(m - mc)
    return dict(mean=mean_ok, gain=gain_ok, n=len(a), n_c=len(c), cut_mean=fm,
                cut_gain=(fm - fc) if (fm is not None and fc is not None) else None)


def holm_family(pvals: dict[str, float | None]) -> dict[str, float]:
    """Holm-adjusted p per arm; an arm with no p-value enters as 1.0 (m = 3)."""
    full = {a: (1.0 if pvals.get(a) is None else pvals[a]) for a in ARMS}
    return {a: adj for a, (adj, _rej) in SPD.holm(full, ALPHA).items()}


def grade(arm_rows: list[dict], calm_rows: list[dict], n: int = BOOT_N,
          seed: int = SEED) -> dict:
    """Unadjusted statistics, C2 and C3 for one arm against its `ARM C` column."""
    g = dict(n=len(arm_rows), n_c=len(calm_rows))
    g.update(bootstrap(arm_rows, calm_rows, n, seed))
    c2 = c2_check(arm_rows, calm_rows)
    c3 = c3_check(arm_rows, calm_rows)
    g.update(c2_mean=c2["mean"], c2_gain=c2["gain"], c3_mean=c3["mean"], c3_gain=c3["gain"],
             loo_m=(min(c2["folds_m"]), max(c2["folds_m"])) if c2["folds_m"] else None,
             cut_mean=c3["cut_mean"], cut_gain=c3["cut_gain"], cut_n=c3["n"])
    return g


def apply_holm(grades: dict[str, dict]) -> None:
    """Adds `p_adj` and `gain_p_adj` in place: two families of three."""
    hm = holm_family({a: g.get("p") for a, g in grades.items()})
    hg = holm_family({a: g.get("gain_p") for a, g in grades.items()})
    for a, g in grades.items():
        g["p_adj"], g["gain_p_adj"] = hm[a], hg[a]


def conditions(g: dict, word: str, forward: bool = False) -> list[str]:
    """The failing conditions of `word` on grade `g` (PBO and the exit-drop
    check are not in here). Empty means every listed condition holds."""
    fails = []
    ci, gci = g.get("ci"), g.get("gain_ci")
    c3m = True if forward else g.get("c3_mean")
    c3g = True if forward else g.get("c3_gain")
    if word in (LVP, PNS):
        if not (ci and ci[0] > 0 and g.get("p_adj", 1.0) < ALPHA):
            fails.append("sign")
    elif word == CONTRARY:
        if not (ci and ci[1] < 0 and g.get("p_adj", 1.0) < ALPHA):
            fails.append("sign")
    if word == LVP and not (gci and gci[0] > 0 and g.get("gain_p_adj", 1.0) < ALPHA):
        fails.append("gain")
    if not g.get("c2_mean") or (word == LVP and not g.get("c2_gain")):
        fails.append("C2 fails")
    if not c3m or (word == LVP and not c3g):
        fails.append("C3 fails")
    return fails


def decide(g: dict, g_drop_pos: dict | None, g_drop_neg: dict | None,
           pbo: float | None, pbo_state: str, forward: bool = False) -> tuple[str, str]:
    """The arm's verdict, first match. `(word, reason)`.

    `g_drop_pos` / `g_drop_neg`: the exit-drop re-run grades (dropped trades at
    R = -1, or at the arm's largest priced R), None when there is no exit drop.
    `pbo_state`: `ok` (computed), `await` (a cell awaits a fetch) or `other`.
    Forward: no C3 and no C4; `STILL-OPEN` replaces `UNDERPOWERED`."""
    if g["n"] < C0_ARM or g["n_c"] < C0_CALM:
        return (STILL_OPEN if forward else UNDERPOWERED), ""
    reasons: list[str] = []

    def exit_drop_ok(word, gd) -> bool:
        return gd is None or not conditions(gd, word, forward)

    for word in (LVP, PNS):
        fails = conditions(g, word, forward)
        if word == PNS and "sign" not in fails:
            reasons += [f for f in fails if f in ("C2 fails", "C3 fails")]
        if fails:
            continue
        if not exit_drop_ok(word, g_drop_pos):
            if word == PNS:
                reasons.append("exit-drop sensitive")
            continue
        if not forward:
            if pbo_state == "await":
                return NOT_BUILT, "a PBO cell awaits a fetch"
            if pbo_state != "ok" or pbo is None:
                if word == PNS:
                    reasons.append("PBO not computed")
                continue
            if pbo >= PBO_MAX:
                if word == PNS:
                    reasons.append("PBO veto")
                continue
        return word, ""
    fails = conditions(g, CONTRARY, forward)
    if "sign" not in fails:
        reasons += [f for f in fails if f in ("C2 fails", "C3 fails")]
        if not fails:
            if exit_drop_ok(CONTRARY, g_drop_neg):
                return CONTRARY, ""
            reasons.append("exit-drop sensitive")
    return NULL, "; ".join(dict.fromkeys(reasons))


def exit_drop_rows(rows: list[dict], dropped: list[date], value: float) -> list[dict]:
    """The arm's rows plus every exit-dropped onset trade at `value`."""
    return rows + [dict(date=d.isoformat(), R=value) for d in dropped]


def regrade_exit_drop(arm: str, rows: list[dict], calm_rows: list[dict],
                      dropped: list[date], grades: dict[str, dict], value: float,
                      n: int = BOOT_N, seed: int = SEED) -> dict | None:
    """The exit-drop re-run: bootstrap, Holm (the other arms keep their
    original p), C2 and C3 on the arm's rows with the drops set to `value`.
    `ARM C` keeps its exit drops out. None when the arm has no exit drop."""
    if not dropped:
        return None
    g = grade(exit_drop_rows(rows, dropped, value), calm_rows, n, seed)
    pm = {a: grades[a].get("p") for a in ARMS}
    pg = {a: grades[a].get("gain_p") for a in ARMS}
    pm[arm], pg[arm] = g.get("p"), g.get("gain_p")
    g["p_adj"], g["gain_p_adj"] = holm_family(pm)[arm], holm_family(pg)[arm]
    return g


def pbo_matrix(rows_by_cell: dict[int, list[dict]]) -> np.ndarray:
    """`T quarters x 12 cells x [sum R, count]`, 2022 Q1 to 2026 Q3."""
    qs, cur = [], PBO_QUARTERS[0]
    while cur <= PBO_QUARTERS[1]:
        qs.append(cur)
        cur = (cur[0] + 1, 1) if cur[1] == 4 else (cur[0], cur[1] + 1)
    idx = {q: i for i, q in enumerate(qs)}
    cells = sorted(rows_by_cell)
    M = np.zeros((len(qs), len(cells), 2))
    for j, c in enumerate(cells):
        for r in rows_by_cell[c]:
            i = idx.get(quarter(_d(r["date"])))
            if i is not None:
                M[i, j, 0] += r["R"]
                M[i, j, 1] += 1
    return M


def run_pbo(rows_by_cell: dict[int, list[dict]]):
    M = pbo_matrix(rows_by_cell)
    Mp, padded = PBO.pad_head(M, PBO_S)
    return PBO.cscv(Mp, S=PBO_S, metric=PBO.ratio_metric), M.shape[0], padded


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def _f(v, fmt="+.3f") -> str:
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else format(v, fmt)


def _ci_s(ci) -> str:
    if not ci:
        return "[n/a]"
    return f"[{ci[0]:+.3f}, {ci[1]:+.3f}] (half-width {(ci[1] - ci[0]) / 2:.3f})"


def hdr(title: str) -> None:
    MB.hdr(title)


def git_state() -> tuple[str, bool]:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                    capture_output=True, text=True).stdout.strip())
    except Exception:  # noqa: BLE001 — provenance is best-effort
        return "unknown", True
    return sha, dirty


def gate_ge() -> list[str]:
    """GE: both label tables, SPY.csv and the option cache exist; the
    in-sample table and SPY.csv reach 2026-09-22."""
    bad = []
    for p in (INSAMPLE_TABLE, FORWARD_TABLE, SPY_CSV, HISTORY_CACHE):
        if not Path(p).exists():
            bad.append(f"missing {Path(p).relative_to(ROOT)}")
    if bad:
        return bad
    last_in = max(_d(r["date"]) for r in read_table(INSAMPLE_TABLE))
    if last_in < CUT:
        bad.append(f"in-sample table ends {last_in}, before {CUT}")
    last_spy = max(_d(r[0]) for r in SM.read_series(SPY_CSV))
    if last_spy < CUT:
        bad.append(f"SPY.csv ends {last_spy}, before {CUT}")
    return bad


def logged_mech_vol() -> dict[date, str]:
    """`regime_watch`'s logged `mech_vol` per date, when the row is not
    backfilled and its `mech_asof` equals the date."""
    if not RW_HISTORY.exists():
        return {}
    back = set()
    if RW_BACKFILLED.exists():
        with RW_BACKFILLED.open(newline="") as fh:
            back = {_d(r["date"]) for r in csv.DictReader(fh)}
    out = {}
    with RW_HISTORY.open(newline="") as fh:
        for r in csv.DictReader(fh):
            d = _d(r["date"])
            if d not in back and (r.get("mech_asof") or "")[:10] == d.isoformat():
                out[d] = r.get("mech_vol") or ""
    return out


def census(book: Book, title: str) -> None:
    """Counts only: onsets, calm weeks, and each arm's coverage per cell."""
    hdr(f"CENSUS — {title} (counts only; no price read)")
    print(f"  onsets: {len(book.onsets_all)} in the window, {len(book.onsets)} candidate "
          f"entries, n_truncated {book.truncated['onset']}; blocked E-VOL sessions over the "
          f"whole table: " + ", ".join(f"{k} {v}" for k, v in sorted(book.onset_why.items())))
    for d in book.onsets_all:
        i = book.pos[d]
        f = book.sessions[i + 1] if i + 1 < len(book.sessions) else None
        flag = "" if d in book.onsets else "  (truncated)"
        print(f"    {d}  F {f}{flag}")
    print(f"  calm weeks (ARM C): {len(book.calm_all)} calm in the window, {len(book.calm)} "
          f"candidate entries, n_truncated {book.truncated['calm']}; weeks with no calm "
          f"entry: " + (", ".join(f"{k} {v}" for k, v in sorted(book.calm_why.items()))
                        or "none"))
    print(f"\n  {'cell':<6}{'arm':<4}{'expiry':<26}{'n':>5}{'built':>7}{'await':>7}"
          f"{'drop':>6}{'legs':>6}  awaits and drops by reason")
    rows = [(f"{c.n}", c.arm, EXPIRY_LABEL[c.expiry], book.onset_entries(c.expiry))
            for c in CELLS if c.hold == HOLD]
    rows += [("C-" + a, a, EXPIRY_LABEL["H"], book.calm_entries()) for a in ARMS]
    for name, arm, lab, ens in rows:
        st = Counter(en.status[arm] for en in ens)
        why = Counter(f"{en.status[arm]}:{en.reason[arm]}" for en in ens
                      if en.status[arm] != "built")
        legs = {(o, e, round(float(k), 4)) for en in ens if en.status[arm] == "await"
                for o, e, k in en.fetch[arm]}
        print(f"  {name:<6}{arm:<4}{lab:<26}{len(ens):>5}{st['built']:>7}{st['await']:>7}"
              f"{st['drop']:>6}{len(legs):>6}  "
              + (", ".join(f"{k} {v}" for k, v in sorted(why.items())) or "-"))
    print("  legs = unique contracts that cell's awaiting entries name in this round")
    print(f"  headline arm-entries awaiting a fetch (the await gate): {book.headline_awaiting()}")
    print("  (the 10-session cells share their 5-session cell's entries and contracts;"
          " cells 1-12 are listed in the registration)")


def operator_steps() -> None:
    print("  Operator-run steps, in order (none runs from here):")
    print(f"    1. {FETCH_CMD} --dry-run --list   (then the real fetch, --scope primary)")
    print("    2. python3 scripts/backup_research_caches.py push")
    print("    3. re-run this study; a fetch can prove a strike unlisted and expose the next,")
    print("       so steps 1-3 repeat until no headline entry awaits; then --scope all")
    print("  It does not run beside another option-cache writer: one writer.")


def print_header(sha: str, dirty: bool, ins: Book, fwd: Book) -> None:
    spy = SM.read_series(SPY_CSV)
    print(f"""  Registration {REGISTRATION}
  (accepted by the operator on the defaults {ACCEPTED}). NOTHING SHIPS FROM THIS STUDY.
  era: current (inputs are unversioned market closes and option quotes)
  windows  in-sample D {IN_SAMPLE[0]} -> {IN_SAMPLE[1]}  ·  gap {GAP[0]} -> {GAP[1]} (in no \
population)  ·  forward from {FORWARD_START}  ·  sunset {SUNSET}
  seal     era.SEAL_START {era_mod.SEAL_START}, era.SEAL_LIFTED {era_mod.SEAL_LIFTED}; the lift \
does not move this window
  git      {sha}{' (dirty)' if dirty else ''}
  inputs
    {INSAMPLE_TABLE.relative_to(ROOT)}  sha256 {sha256(INSAMPLE_TABLE)}
       read {ins.sessions[0]} -> {ins.sessions[-1]} (cut at {CUT})
    {FORWARD_TABLE.relative_to(ROOT)}  sha256 {sha256(FORWARD_TABLE)}
       read {fwd.sessions[0]} -> {fwd.sessions[-1]}
    {SPY_CSV.relative_to(ROOT)}  file {spy[0][0]} -> {spy[-1][0]}; in-sample read \
{min(ins.spots)} -> {max(ins.spots)}
    {Path(HISTORY_CACHE).relative_to(ROOT)}/ SPY files (in-sample histories cut at {CUT})
  costs    commission ${COMMISSION:.2f}/contract/side, slippage 0 (registered)
  label    compute_mech_table mech_vol == E-VOL; re-arm {REARM} sessions; strike step ${STEP:g}""")


def gl_section(lab_a, lab_b) -> int:
    start, only_a, only_b = gl_mismatch(lab_a, lab_b, CUT)
    hdr("GATE GL — onset dates agree between the two label tables")
    if start is None:
        print("  GL: the production table has fewer than 11 rows. REFUSED. Exit 2.")
        return EXIT_GL
    n = len([d for d in find_onsets(lab_a)[0] if start <= d <= CUT])
    if only_a or only_b:
        print(f"  GL FAIL on D {start} -> {CUT}")
        print(f"    onsets only in the in-sample table:  {', '.join(map(str, only_a)) or 'none'}")
        print(f"    onsets only in the production table: {', '.join(map(str, only_b)) or 'none'}")
        print("  The registration names no recovery path. REFUSED. Exit 2.")
        return EXIT_GL
    print(f"  GL PASS: {n} onsets on D {start} -> {CUT}, identical in both tables")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="Census only: onsets, calm weeks and leg coverage; no P&L.")
    args = ap.parse_args(argv)

    hdr("vol_expansion_long_vol — after a SPY E-VOL onset, do a long straddle or a 1x2 "
        "backspread pay, and more than on calm weeks?")
    bad = gate_ge()
    if bad:
        hdr("GATE FAILURE — GE")
        for b in bad:
            print(f"  GE: {b}")
        print("  No census, no outcome. Exit 3.")
        return EXIT_GE
    lab_a = vol_labels(read_table(INSAMPLE_TABLE), CUT)
    lab_b = vol_labels(read_table(FORWARD_TABLE), CUT)
    ins, fwd = build_books()
    sha, dirty = git_state()
    print_header(sha, dirty, ins, fwd)
    print("  GE PASS")
    rc = gl_section(lab_a, lab_b)
    if rc:
        return rc

    census(ins, "in-sample")
    n_p = len(fetch_targets(ins, "primary"))
    n_a = len(fetch_targets(ins, "all"))
    print(f"\n  fetch plan: primary (headline onsets + ARM C) {n_p} unique uncached contracts; "
          f"all cells {n_a}")
    print("  (one round: each awaiting leg names its nearest open strike; a fetch can expose "
          "the next)")
    forward_census(fwd)

    if args.dry_run:
        hdr("DRY RUN — census only; no price was read")
        operator_steps()
        return 0
    try:
        ins.open_outcomes()
    except AwaitingScrape as exc:
        hdr("VERDICT")
        print(f"  {NOT_BUILT} — {exc}.")
        print("  No outcome was computed for any arm: no R, no P&L, no CI.")
        for a in ARMS:
            print(f">>> vol_expansion_long_vol {BANNER[a]}: {NOT_BUILT} — {PEEK_NOTE} <<<")
        print(">>> vol_expansion_long_vol PBO (12 cells, gates all three arms): not computed <<<")
        print(f">>> vol_expansion_long_vol FORWARD (onsets from {FORWARD_START}): "
              + " ".join(f"ARM {a} {STILL_OPEN}" for a in ARMS) + " <<<")
        print(f"  forward: {len(fwd.onsets_all)} forward onsets; floor {C0_ARM} priced trades "
              f"per arm and {C0_CALM} calm weeks per column")
        operator_steps()
        print("  Nothing ships from this study.")
        return 0
    return outcomes(ins, fwd)


def forward_census(fwd: Book) -> None:
    hdr(f"FORWARD — onsets from {FORWARD_START} (counts only)")
    logged = logged_mech_vol()
    print(f"  forward table ends {fwd.sessions[-1]}; forward onsets {len(fwd.onsets_all)} "
          f"({len(fwd.onsets)} with an exit session); forward calm weeks "
          f"{len(fwd.calm_all)} ({len(fwd.calm)} with an exit session)")
    for d in fwd.onsets_all:
        print(f"    {d}  regime_watch logged mech_vol: {logged.get(d, 'no live row')}")


def outcomes(ins: Book, fwd: Book) -> int:
    """Everything past the await gate. `Book.price` raises if it was not opened."""
    def rows(ps):
        return [dict(date=p.signal.isoformat(), R=p.R) for p in ps]

    hdr("PRICING — every cell and ARM C column; drops by reason")
    cell_data, calm_data = {}, {}
    for c in CELLS:
        if ins.cell_awaits(c):
            cell_data[c.n] = None
            print(f"  cell {c.n:>2} {c.arm:<2} hold {c.hold:>2} {c.expiry}: {NOT_BUILT}")
            continue
        ps, drops, xd = ins.priced(ins.onset_entries(c.expiry), c.arm, c.hold)
        cell_data[c.n] = (ps, drops, xd)
        print(f"  cell {c.n:>2} {c.arm:<2} hold {c.hold:>2} {c.expiry}: priced {len(ps):>3}  "
              f"drops " + (", ".join(f"{k} {v}" for k, v in sorted(drops.items())) or "none"))
    for a in ARMS:
        for h in HOLDS:
            ps, drops, _xd = ins.priced(ins.calm_entries(), a, h)
            calm_data[(a, h)] = ps
            print(f"  C-{a:<3} hold {h:>2} H: priced {len(ps):>3}  drops "
                  + (", ".join(f"{k} {v}" for k, v in sorted(drops.items())) or "none"))

    hdr("COUNTS — per headline arm and ARM C column")
    for a in ARMS:
        hc = HEADLINE[a]
        ps = cell_data[hc.n][0]
        cps = calm_data[(a, HOLD)]
        for lab, pp in ((f"ARM {a}", ps), (f"C-{a}", cps)):
            cr = sum(p.net < 0 for p in pp)
            print(f"  {lab:<7} n {len(pp):>3}  R<-1 {sum(p.R < -1 for p in pp):>2}  "
                  f"sold leg at bid {sum(p.sold_at_bid for p in pp):>2}  "
                  + (f"credit {cr} debit {len(pp) - cr}  " if a != "S" else "")
                  + f"_entry_outside_bounds would refuse {sum(p.outside_bounds for p in pp)}")

    # ── graded arms ──────────────────────────────────────────────────────────
    hdr("GRADED ARMS — headline cell (5 sessions, monthly ~30 DTE) vs ARM C")
    grades, arm_rows, calm_rows, xdrops = {}, {}, {}, {}
    for a in ARMS:
        ps, _d0, xd = cell_data[HEADLINE[a].n]
        arm_rows[a], calm_rows[a], xdrops[a] = rows(ps), rows(calm_data[(a, HOLD)]), xd
        grades[a] = grade(arm_rows[a], calm_rows[a])
    apply_holm(grades)
    # ── PBO ──────────────────────────────────────────────────────────────────
    hdr("C4 — PBO by CSCV over the 12 cells, onset trades, quarter blocks")
    pbo, pbo_state = None, "ok"
    if any(v is None for v in cell_data.values()):
        pbo_state = "await"
        print("  not computed: a cell awaits a fetch")
    else:
        try:
            res, T, padded = run_pbo({n: rows(v[0]) for n, v in cell_data.items()})
            pbo = res.pbo
            share = res.selection_share()
            print(f"  quarters {T} (+{padded} zero pad)  S {PBO_S}  combinations "
                  f"{res.n_combinations}  PBO {pbo:.3f}  "
                  f"({'bars promotion' if pbo >= PBO_MAX else 'below 0.50'})")
            print("  n_star share per cell (a half with no trades makes every cell NaN and "
                  "picks cell 1): " + "  ".join(f"{c.n}:{s:.3f}" for c, s in zip(CELLS, share)))
        except ValueError as exc:
            pbo_state = "other"
            print(f"  not computed: {exc}")

    words = {}
    for a in ARMS:
        g = grades[a]
        priced_R = [r["R"] for r in arm_rows[a]]
        gpos = regrade_exit_drop(a, arm_rows[a], calm_rows[a], xdrops[a], grades, -1.0)
        gneg = (regrade_exit_drop(a, arm_rows[a], calm_rows[a], xdrops[a], grades,
                                  max(priced_R)) if priced_R else None)
        words[a] = decide(g, gpos, gneg, pbo, pbo_state)
        print(f"  ARM {a}: n {g['n']}  meanR {_f(g['mean'])} CI95 {_ci_s(g['ci'])}  "
              f"p {_f(g['p'], '.4f')}  Holm p {_f(g['p_adj'], '.4f')}")
        print(f"     ARM C (C-{a}) n {g['n_c']}  meanR {_f(g['mean_c'])}  gain {_f(g['gain'])} "
              f"CI95 {_ci_s(g['gain_ci'])}  p {_f(g['gain_p'], '.4f')}  "
              f"Holm p {_f(g['gain_p_adj'], '.4f')}")
        loo = g["loo_m"]
        loo_s = f"[{loo[0]:+.3f}, {loo[1]:+.3f}]" if loo else "n/a"
        print(f"     C2 mean {'Y' if g['c2_mean'] else 'n'} gain {'Y' if g['c2_gain'] else 'n'}"
              f" (LOO meanR {loo_s})"
              f"  C3 mean {'Y' if g['c3_mean'] else 'n'} gain {'Y' if g['c3_gain'] else 'n'}"
              f" (cut n {g['cut_n']} meanR {_f(g['cut_mean'])} gain {_f(g['cut_gain'])})")
        print(f"     exit drops {len(xdrops[a])}"
              + (f"; re-run at R=-1 meanR {_f(gpos['mean'])} CI95 {_ci_s(gpos['ci'])}"
                 if gpos else ""))
        print(f"     -> {words[a][0]}" + (f" ({words[a][1]})" if words[a][1] else ""))

    printed_only(ins, cell_data, calm_data, grades)

    # ── forward ──────────────────────────────────────────────────────────────
    fw_words = forward_words(fwd)

    hdr("VERDICT")
    for a in ARMS:
        w, why = words[a]
        g = grades[a]
        extra = ""
        if w == NULL:
            hw = (g["ci"][1] - g["ci"][0]) / 2 if g.get("ci") else None
            extra = f" (half-width {_f(hw, '.3f')}" + (f"; {why}" if why else "") + ")"
        print(f">>> vol_expansion_long_vol {BANNER[a]}: {w}{extra} — {PEEK_NOTE} <<<")
    pbo_s = f"{pbo:.3f}" if pbo is not None else "not computed"
    print(f">>> vol_expansion_long_vol PBO (12 cells, gates all three arms): {pbo_s} <<<")
    print(f">>> vol_expansion_long_vol FORWARD (onsets from {FORWARD_START}): "
          + " ".join(f"ARM {a} {fw_words[a]}" for a in ARMS) + " <<<")
    for c in CAVEATS:
        print(f"  {c}")
    print("  Nothing ships from this study.")
    write_trades(cell_data, calm_data)
    return 0


def printed_only(ins: Book, cell_data: dict, calm_data: dict, grades: dict) -> None:
    hdr("PRINTED ONLY — the 12 cells, ARM C, diagnostics (no verdict)")
    print(f"  {'cell':<5}{'arm':<4}{'hold':>5} {'exp':<4}{'n':>4}  {'meanR':>7}  CI95"
          f"{'':<32}gain vs ARM C")
    for c in CELLS:
        if cell_data[c.n] is None:
            print(f"  {c.n:<5}{c.arm:<4}{c.hold:>5} {c.expiry:<4}  {NOT_BUILT}")
            continue
        rs = [dict(date=p.signal.isoformat(), R=p.R) for p in cell_data[c.n][0]]
        cr = ([dict(date=p.signal.isoformat(), R=p.R) for p in calm_data[(c.arm, c.hold)]]
              if c.expiry == "H" else [])
        b = bootstrap(rs, cr)
        print(f"  {c.n:<5}{c.arm:<4}{c.hold:>5} {c.expiry:<4}{len(rs):>4}  {_f(b['mean']):>7}  "
              f"{_ci_s(b['ci']):<36}{_f(b['gain']) if c.expiry == 'H' else '-'}")
    print("\n  ARM C columns (headline expiry):")
    for a in ARMS:
        for h in HOLDS:
            rs = [dict(date=p.signal.isoformat(), R=p.R) for p in calm_data[(a, h)]]
            b = bootstrap(rs, [])
            print(f"    C-{a:<3} hold {h:>2}  n {len(rs):>4}  meanR {_f(b['mean'])}  "
                  f"CI95 {_ci_s(b['ci'])}")
    print("\n  Diagnostics, headline expiry, 5-session hold (MFE/MAE on the daily mark path,"
          " R formula):")
    print(f"  {'object':<8}{'n':>4} {'MFE':>8} {'MAE':>8} {'capture':>8} {'move/IV':>8} "
          f"{'dIV':>7} {'stopR':>8} {'stops':>6}")

    def diag(lab, ps):
        mfe = [p.mfe for p in ps if p.mfe is not None]
        mae = [p.mae for p in ps if p.mae is not None]
        mr = [p.move_ratio for p in ps if p.move_ratio is not None]
        di = [p.iv_change for p in ps if p.iv_change is not None]
        smfe = sum(p.mfe for p in ps if p.mfe is not None)
        cap = (sum(p.R for p in ps if p.mfe is not None) / smfe) if smfe else None
        m = lambda v: statistics.fmean(v) if v else None  # noqa: E731
        print(f"  {lab:<8}{len(ps):>4} {_f(m(mfe)):>8} {_f(m(mae)):>8} {_f(cap):>8} "
              f"{_f(m(mr), '.3f'):>8} {_f(m(di), '+.2f'):>7} "
              f"{_f(m([p.stop_R for p in ps])):>8} {sum(p.stopped for p in ps):>6}")
    for a in ARMS:
        diag(f"ARM {a}", cell_data[HEADLINE[a].n][0])
        diag(f"C-{a}", calm_data[(a, HOLD)])
    print("\n  Per trade, headline cells:")
    print(f"  {'arm':<4}{'D':<11} {'F':<11} {'expiry':<11}{'DTE':>4} {'ATM':>6} {'wing':>6} "
          f"{'N':>7} {'L':>7} {'R':>7} {'$':>9}  exit")
    for a in ARMS:
        hc = HEADLINE[a]
        ens = {en.signal: en for en in ins.onset_entries("H")}
        done = {p.signal: p for p in cell_data[hc.n][0]}
        for d, en in ens.items():
            p = done.get(d)
            if p is not None:
                print(f"  {a:<4}{d!s:<11} {p.fill!s:<11} {p.expiry!s:<11}{en.dte:>4} "
                      f"{p.atm:>6g} {(p.wing or 0):>6g} {p.net:>+7.2f} {p.max_loss:>7.2f} "
                      f"{p.R:>+7.3f} {p.pnl:>+9.2f}  {p.exit}")
            else:
                why = en.reason[a] if en.status[a] != "built" else ins.price(en, a, HOLD)
                print(f"  {a:<4}{d!s:<11} {en.fill!s:<11} {str(en.expiry):<11}"
                      f"{(en.dte or 0):>4}  dropped: {why}")


def forward_words(fwd: Book) -> dict[str, str]:
    """The forward read on the headline cells. Floors equal C0; no C3, no C4."""
    out = {}
    if not fwd.onsets:
        return {a: STILL_OPEN for a in ARMS}
    fwd._open = fwd.headline_awaiting() == 0
    if not fwd._open:
        return {a: STILL_OPEN for a in ARMS}
    grades, ar, cr, xd = {}, {}, {}, {}
    for a in ARMS:
        ps, _dr, x = fwd.priced(fwd.onset_entries("H"), a, HOLD)
        cps, _dc, _xc = fwd.priced(fwd.calm_entries(), a, HOLD)
        ar[a] = [dict(date=p.signal.isoformat(), R=p.R) for p in ps]
        cr[a] = [dict(date=p.signal.isoformat(), R=p.R) for p in cps]
        xd[a] = x
        grades[a] = grade(ar[a], cr[a])
    apply_holm(grades)
    for a in ARMS:
        pr = [r["R"] for r in ar[a]]
        gp = regrade_exit_drop(a, ar[a], cr[a], xd[a], grades, -1.0)
        gn = regrade_exit_drop(a, ar[a], cr[a], xd[a], grades, max(pr)) if pr else None
        out[a] = decide(grades[a], gp, gn, None, "ok", forward=True)[0]
    return out


def write_trades(cell_data: dict, calm_data: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["population", "cell", "arm", "hold", "signal", "fill", "exit", "expiry", "atm",
            "wing", "N", "L", "exit_value", "commission", "R", "pnl_dollars", "pnl_share_spot",
            "mfe", "mae", "stop_R", "stopped", "move_ratio", "atm_iv_change", "sold_at_bid"]
    with TRADES_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()

        def put(pop, cell, p):
            w.writerow(dict(population=pop, cell=cell, arm=p.arm, hold=p.hold, signal=p.signal,
                            fill=p.fill, exit=p.exit, expiry=p.expiry, atm=p.atm, wing=p.wing,
                            N=round(p.net, 4), L=round(p.max_loss, 4),
                            exit_value=round(p.exit_value, 4), commission=p.comm,
                            R=round(p.R, 6), pnl_dollars=round(p.pnl, 2),
                            pnl_share_spot=round(p.pnl_spot, 6), mfe=p.mfe, mae=p.mae,
                            stop_R=round(p.stop_R, 6), stopped=p.stopped,
                            move_ratio=p.move_ratio, atm_iv_change=p.iv_change,
                            sold_at_bid=p.sold_at_bid))
        for n, v in cell_data.items():
            if v is not None:
                for p in v[0]:
                    put("onset", n, p)
        for (a, h), ps in calm_data.items():
            for p in ps:
                put("calm", f"C-{a}", p)
    shown = TRADES_CSV.relative_to(ROOT) if TRADES_CSV.is_relative_to(ROOT) else TRADES_CSV
    print(f"  trades -> {shown}")


if __name__ == "__main__":
    raise SystemExit(main())
