"""$25k account simulation of the shipped ladder — FEASIBILITY only, nothing ships.

Pre-registered 2026-08-13 in `config/backtest-tuning/current.md`
(§"`account_sim`: PRE-REGISTRATION"). Every constant, arm, cap, criterion and
verdict string below is transcribed from that section; this module may not
change them after the run.

The question is NOT "is there edge" — that is settled elsewhere and frozen
here. It is: does the shipped operator card (`top_k_per_day`, k=3, tiers A/B,
`ladder_rank` ordering) still produce a book when a $25,000 account has to
actually pay for the positions, hold reserved capital while they are open, and
respect a delta-notional exposure cap? Selection is FROZEN, exits are FROZEN
(`bear_giveback.prod_profile_for(rec, 0.50, True)` for debit rows,
`book.CREDIT_PROD` for credit rows). The only new machinery is the ledger.

Mechanics worth knowing before reading any number:

  * **Dollar-stop scaling identity.** `harness.MAX_LOSS_ABS` is frozen at
    $1,000 (a $50k book at 2%). A $25k book stops at $500. Replaying a position
    of `c` contracts at `c x 2` contracts under the frozen harness makes the
    harness's $1,000 test fire at exactly the loss a $500 stop would fire at on
    `c` contracts; dividing the resulting dollars by 2 recovers the true P&L.
    Realized R is size-independent EXCEPT through that branch, which is why the
    identity is exact rather than an approximation. Calibrated at scale=1 by G2.

  * **Occupancy.** A position is held from `t.grid[0]` (the entry session — the
    weekday after the signal date) through `t.grid[days_held-1]` inclusive, with
    `days_held` taken from the replay AT THE ACTUAL SIZE (so an ARM D downsize
    that changes the dollar-stop day also changes occupancy). Capital is
    released at the first session AFTER the exit session, never on the same
    session it was still occupying.

  * **Stated interpretation (not in the pre-registration).** When a pick is
    rejected by a cap, the walk continues DOWN that day's ranked candidate list
    until three positions are admitted — that is what `ordered_by_day` exists
    for. The unconstrained walk therefore reproduces `top_k_per_day` exactly
    (G4), while a constrained walk may hold a lower-ranked row.

  * **Unsizable picks.** 2 of the 220 deployed picks are credit rows with no
    usable `max_loss_per_contract`. They cannot be sized, so they are skipped —
    but they still CONSUME a day slot, because the ladder did select them. That
    keeps the selection identity (G4) exact.

Read-only. Touches no config, writes nothing. Run:

    python -m scripts.backtest_study run account_sim
    python -m scripts.backtest_study run account_sim --gates-only
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study import protocol as P  # noqa: E402
from scripts.backtest_study.bear_deploy import max_drawdown  # noqa: E402
from scripts.backtest_study.bear_giveback import (  # noqa: E402
    BEAR_DEBIT, hdr, prod_profile_for, sub,
)
from scripts.backtest_study.book import CREDIT_PROD, DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.harness import (  # noqa: E402
    MAX_LOSS_ABS, Trade, _pct, _to_float, replay,
)

# ── pre-registered constants (config/backtest-tuning/current.md 2026-08-13) ──
STARTING_CAPITAL = 25_000.0
RISK_PER_TRADE_PCT = 0.02
MAX_POSITIONS_PER_DAY = 3
PER_POSITION_CAP = 0.25            # x equity, delta-notional
NET_CAP = 1.50                     # x equity, |net| delta-notional

PER_POS_GRID = (0.15, 0.25, 0.40, float("inf"))
NET_GRID = (1.00, 1.50, 2.50, float("inf"))

EPISODE_MAX_GAP = 5                # trading sessions between consecutive dates
EPISODE_MIN_DATES = 10
CAPITAL_LADDER = (25_000.0, 35_000.0, 50_000.0)

# B1 target: the deployed line the 2026-08-12 vol_sleeve report printed on these
# same exports. Gated, not merely quoted.
B1_EXPECTED_N = 220
B1_EXPECTED_DATES = 90
B1_EXPECTED_DOLLARS = 63_553.0
B1_DOLLAR_TOL = 1.0

# A-criteria thresholds, pre-registered.
A2_ATTRITION_FLOOR = 0.60
A3_MAXDD_FRACTION = 0.25
A5_RATIO_TOLERANCE = 0.15

EPS = 1e-9


# ════════════════════════════════════════════════════════════════════════════
# Pure helpers (unit-tested in tests/test_studies_account_sim.py)
# ════════════════════════════════════════════════════════════════════════════

def risk_contracts(max_loss_per_contract, budget: float):
    """`max(1, int(budget / max_loss))` — the pre-registered MAX-LOSS sizing.

    `None` when the row carries no usable max loss (unsizable, not zero-sized).
    """
    if max_loss_per_contract is None or max_loss_per_contract <= 0:
        return None
    return max(1, int(budget / max_loss_per_contract))


def admission(reserved: float, dn_signed: float, cash: float, net_open: float,
              cfg: "Cfg") -> tuple[bool, str | None]:
    """`(ok, binding_constraint)` — the FIRST failing constraint, in fixed order.

    Fixed order cash -> per-position delta -> net delta is what makes A4's
    "exactly ONE binding constraint" well defined.
    """
    if cfg.enforce_cash and reserved > cash + EPS:
        return False, "cash"
    if abs(dn_signed) > cfg.per_pos_cap * cfg.capital + EPS:
        return False, "per_pos_delta"
    if abs(net_open + dn_signed) > cfg.net_cap * cfg.capital + EPS:
        return False, "net_delta"
    return True, None


def solve_contracts(max_c: int, unit_reserved: float, unit_dn: float,
                    cash: float, net_open: float, cfg: "Cfg") -> int:
    """Largest integer contract count in [1, max_c] passing EVERY cap; 0 = none."""
    for c in range(max_c, 0, -1):
        ok, _ = admission(c * unit_reserved, c * unit_dn, cash, net_open, cfg)
        if ok:
            return c
    return 0


class Ledger:
    """Cash / reserved / realized with the G3 accounting identity self-checked
    after EVERY event (stronger than the pre-registered per-session check).

    Invariant: `cash + reserved == capital + realized`, and cash never negative
    (the A3 'never over-reserves' condition — admission already refuses a
    position whose reserve exceeds cash, so a negative cash is a ledger bug).
    """

    def __init__(self, capital: float):
        self.capital = float(capital)
        self.cash = float(capital)
        self.reserved = 0.0
        self.realized = 0.0
        self.violations: list[str] = []
        self.checks = 0
        self._leak = 0.0          # --selftest-gates only

    def can_open(self, reserved: float, enforce: bool = True) -> bool:
        return (not enforce) or reserved <= self.cash + EPS

    def open(self, reserved: float, tag: str = "") -> None:
        self.cash -= reserved
        self.reserved += reserved
        self._check(f"open {tag}")

    def close(self, reserved: float, pnl: float, tag: str = "") -> None:
        self.cash += reserved + pnl
        self.reserved -= reserved
        self.realized += pnl
        self._check(f"close {tag}")

    def _check(self, where: str) -> None:
        self.checks += 1
        lhs = self.cash + self.reserved + self._leak
        rhs = self.capital + self.realized
        if abs(lhs - rhs) > 1e-6:
            self.violations.append(
                f"identity broken at {where}: cash {self.cash:,.2f} + reserved "
                f"{self.reserved:,.2f} != capital {self.capital:,.2f} + realized "
                f"{self.realized:,.2f}  (delta {lhs - rhs:+,.6f})")
        if self.cash < -1e-9:
            self.violations.append(f"cash negative at {where}: {self.cash:,.2f}")


def sessions_between(a: str | date, b: str | date) -> int:
    """Weekday sessions strictly between two dates (holidays not modelled)."""
    d = date.fromisoformat(str(a)[:10])
    e = date.fromisoformat(str(b)[:10])
    n = 0
    while d < e:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def dense_episodes(dates, max_gap: int = EPISODE_MAX_GAP,
                   min_dates: int = EPISODE_MIN_DATES) -> list[list[str]]:
    """Maximal runs of signal dates with no internal gap > `max_gap` sessions."""
    ds = sorted(set(str(d) for d in dates))
    if not ds:
        return []
    runs = [[ds[0]]]
    for prev, cur in zip(ds, ds[1:]):
        if sessions_between(prev, cur) <= max_gap:
            runs[-1].append(cur)
        else:
            runs.append([cur])
    return [r for r in runs if len(r) >= min_dates]


# ── replay at an arbitrary size under an arbitrary dollar stop ───────────────

_MEMO: dict[tuple, dict] = {}


def profile_for(rec: dict) -> dict:
    """The SHIPPED exit profile for a row. Debit rows go through the base ->
    bear-debit(be_after .50) -> BEAR_HE merge; credit rows never reach it."""
    return dict(CREDIT_PROD) if rec["credit"] else prod_profile_for(rec, 0.50, True)


def replay_sized(rec: dict, contracts: int, stop: float,
                 profile: dict | None = None) -> dict:
    """Replay `rec` at `contracts` contracts under a `stop`-dollar hard stop.

    THE SCALING IDENTITY. The harness's dollar stop is frozen at
    `MAX_LOSS_ABS` ($1,000) and fires when `pnl x denom x 100 x contracts <=
    -1000`. Rebuilding the same row with `contracts x (MAX_LOSS_ABS / stop)`
    moves that test to exactly `pnl x denom x 100 x contracts <= -stop`, and
    dividing the dollars back by the same factor recovers the true P&L. Exact
    whenever the scaled count is an integer — asserted for the study's $500
    stop (factor 2), and only ever inexact on the $35k rung of the capital
    ladder, where it is rounded UP (a tighter stop, the conservative side) and
    flagged via `stop_exact`.
    """
    key = (id(rec), int(contracts), round(float(stop), 6))
    if key in _MEMO:
        return _MEMO[key]
    scaled_exact = MAX_LOSS_ABS * contracts / stop
    scaled = int(round(scaled_exact))
    exact = abs(scaled_exact - scaled) < 1e-9
    if not exact:
        scaled = int(math.ceil(scaled_exact))
    if abs(stop - MAX_LOSS_ABS / 2.0) < 1e-9 or abs(stop - MAX_LOSS_ABS) < 1e-9:
        assert exact, f"scaling identity non-integral: {scaled_exact}"
    row = dict(rec["t"].row)
    row["contracts"] = str(scaled)
    t2 = Trade(row)
    rp = replay(t2, **(profile or profile_for(rec)))
    out = dict(exit_reason=rp["exit_reason"], days_held=rp["days_held"],
               R=rp["pnl_pct"],
               dollars=t2.dollars(rp["pnl_pct"]) * contracts / scaled,
               stop_exact=exact)
    _MEMO[key] = out
    return out


def signed_dn(rec: dict, contracts: int) -> float:
    """Signed delta-notional: `delta x 100 x contracts x entry_underlying`."""
    d = rec.get("delta")
    u = _to_float(rec["t"].row.get("entry_underlying"))
    if d is None or u is None:
        return 0.0
    return float(d) * 100.0 * contracts * float(u)


# ════════════════════════════════════════════════════════════════════════════
# Simulation
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Cfg:
    label: str = ""
    capital: float = STARTING_CAPITAL
    per_pos_cap: float = PER_POSITION_CAP
    net_cap: float = NET_CAP
    downsize: bool = False          # ARM R (False) vs ARM D (True)
    take_floor: bool = True         # F1 (True) vs F2 (False)
    enforce_cash: bool = True
    hedge: bool = False             # ARM H bear sleeve

    @property
    def budget(self) -> float:
        return self.capital * RISK_PER_TRADE_PCT

    @property
    def stop(self) -> float:
        return self.capital * RISK_PER_TRADE_PCT


UNCONSTRAINED = dict(per_pos_cap=float("inf"), net_cap=float("inf"),
                     enforce_cash=False)


@dataclass
class Pos:
    rec: dict
    contracts: int
    reserved: float
    dn: float
    entry_sess: date
    exit_sess: date
    days_held: int
    R: float
    dollars: float
    exit_reason: str
    downsized: bool = False
    hedge: bool = False


@dataclass
class Sim:
    cfg: Cfg
    taken: list = field(default_factory=list)
    skipped: list = field(default_factory=list)     # (rec, reason, counterfactual)
    census: Counter = field(default_factory=Counter)
    downsize_reason: Counter = field(default_factory=Counter)
    ledger: Ledger | None = None
    stop_inexact: int = 0

    # -- derived views -------------------------------------------------------
    @property
    def signal_pos(self) -> list[Pos]:
        return [p for p in self.taken if not p.hedge]

    def rows(self, hedge: bool = False) -> list[dict]:
        src = self.taken if hedge else self.signal_pos
        return [dict(date=p.rec["date"], R=p.R, R_dol=p.dollars, E=p.R,
                     credit=p.rec["credit"], structure=p.rec["structure"],
                     ticker=p.rec["ticker"]) for p in src]

    @property
    def dollars(self) -> float:
        return sum(p.dollars for p in self.signal_pos)

    @property
    def dates(self) -> set:
        return {p.rec["date"] for p in self.signal_pos}


def simulate(day_lists, cfg: Cfg, bear_by_day: dict | None = None,
             selftest_leak: bool = False) -> Sim:
    """Event-loop the ladder through an account ledger.

    `day_lists` is `protocol.ordered_by_day(...)` output, already restricted to
    the population under test. Exits are processed before that session's
    entries; entries are admitted in ladder order until three are held.
    """
    sim = Sim(cfg=cfg)
    led = Ledger(cfg.capital)
    if selftest_leak:
        led._leak = 1.0             # --selftest-gates: a deliberate $1 leak
    sim.ledger = led
    open_pos: list[Pos] = []
    net_open = 0.0

    def release_before(sess) -> None:
        nonlocal net_open
        for p in sorted([q for q in open_pos if q.exit_sess < sess],
                        key=lambda q: q.exit_sess):
            led.close(p.reserved, p.dollars, f"{p.rec['ticker']} {p.rec['date']}")
            open_pos.remove(p)
            net_open -= p.dn

    def take(rec, contracts, downsized=False, hedge=False):
        nonlocal net_open
        rp = replay_sized(rec, contracts, cfg.stop)
        if not rp["stop_exact"]:
            sim.stop_inexact += 1
        t = rec["t"]
        pos = Pos(rec=rec, contracts=contracts,
                  reserved=rec["max_loss_per_contract"] * contracts,
                  dn=signed_dn(rec, contracts),
                  entry_sess=t.grid[0],
                  exit_sess=t.grid[min(rp["days_held"], len(t.grid)) - 1],
                  days_held=rp["days_held"], R=rp["R"], dollars=rp["dollars"],
                  exit_reason=rp["exit_reason"], downsized=downsized, hedge=hedge)
        led.open(pos.reserved, f"{rec['ticker']} {rec['date']}")
        open_pos.append(pos)
        sim.taken.append(pos)
        net_open += pos.dn
        return pos

    for d, ranked in day_lists:
        entry_sess = ranked[0]["t"].grid[0]
        release_before(entry_sess)

        n_today = 0
        for rec in ranked:
            if n_today >= MAX_POSITIONS_PER_DAY:
                sim.census["day3_cap"] += 1
                sim.skipped.append((rec, "day3_cap", None))
                continue
            mlpc = rec["max_loss_per_contract"]
            c = risk_contracts(mlpc, cfg.budget)
            if c is None:
                # Unsizable, but the ladder DID select it — it burns the slot.
                sim.census["unsizable"] += 1
                sim.skipped.append((rec, "unsizable", None))
                n_today += 1
                continue
            if mlpc > cfg.budget and not cfg.take_floor:
                sim.census["min1_refusal"] += 1
                sim.skipped.append((rec, "min1_refusal",
                                    replay_sized(rec, c, cfg.stop)))
                continue
            unit_dn = signed_dn(rec, 1)
            ok, why = admission(c * mlpc, c * unit_dn, led.cash, net_open, cfg)
            if not ok and cfg.downsize:
                c2 = solve_contracts(c, mlpc, unit_dn, led.cash, net_open, cfg)
                if c2 > 0:
                    sim.downsize_reason[why] += 1
                    sim.census["taken_downsized"] += 1
                    take(rec, c2, downsized=True)
                    n_today += 1
                    continue
            if not ok:
                sim.census[why] += 1
                sim.skipped.append((rec, why, replay_sized(rec, c, cfg.stop)))
                continue
            sim.census["taken"] += 1
            take(rec, c)
            n_today += 1

        # ARM H — the shipped bear sleeve, AFTER the day's signal picks so it can
        # never displace one. Not counted against MAX_POSITIONS_PER_DAY.
        if cfg.hedge and bear_by_day and d in bear_by_day:
            cands = sorted(bear_by_day[d],
                           key=lambda r: abs(r["delta"]) if r.get("delta") is not None else -1,
                           reverse=True)
            for rec in cands[:1]:
                if rec.get("delta") is None or not rec["max_loss_per_contract"]:
                    continue
                base = risk_contracts(rec["max_loss_per_contract"], cfg.budget)
                if base is None:
                    continue
                c = max(1, int(0.5 * base))
                ok, _ = admission(c * rec["max_loss_per_contract"], c * signed_dn(rec, 1),
                                  led.cash, net_open, cfg)
                if ok:
                    sim.census["hedge_taken"] += 1
                    take(rec, c, hedge=True)
                else:
                    sim.census["hedge_rejected"] += 1

    for p in sorted(open_pos, key=lambda q: q.exit_sess):
        led.close(p.reserved, p.dollars, "final")
    return sim


# ════════════════════════════════════════════════════════════════════════════
# Post-hoc series
# ════════════════════════════════════════════════════════════════════════════

def session_series(sim: Sim) -> dict:
    """session -> dict(reserved, gross, net, n_open) over every occupied session."""
    out: dict[date, dict] = defaultdict(lambda: dict(reserved=0.0, gross=0.0,
                                                     net=0.0, n=0))
    for p in sim.taken:
        for s in p.rec["t"].grid:
            if s < p.entry_sess or s > p.exit_sess:
                continue
            cell = out[s]
            cell["reserved"] += p.reserved
            cell["gross"] += abs(p.dn)
            cell["net"] += p.dn
            cell["n"] += 1
    return dict(sorted(out.items()))


def equity_curve(positions) -> tuple[list, list]:
    """(sessions, realized dollars booked on that session) ordered by exit."""
    by = defaultdict(float)
    for p in positions:
        by[p.exit_sess] += p.dollars
    sess = sorted(by)
    return sess, [by[s] for s in sess]


def fmean(vals):
    vals = [v for v in vals if v is not None and v == v]
    return statistics.fmean(vals) if vals else float("nan")


def pct_ratio(a: float, b: float) -> float:
    return a / b if b not in (0, None) and abs(b) > 1e-12 else float("nan")


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def run_gates(recs, diag, picked, selftest: bool = False) -> dict:
    hdr("GATES — G1..G4 (non-zero exit on any failure)")
    results = {}

    # -- G1 book calibration + B1 reproduction ------------------------------
    sub("G1 — book calibration quoted, B1 line reproduced")
    dc = diag["debit_calib"]
    print(f"  debit_calib      n={dc['n']}  exact={dc['exact']}  "
          f"near={dc['near']}  hard={dc['hard']}")
    print(f"  n_credit_ungated {diag['n_credit_ungated']}  (admitted WITHOUT the "
          f"exact-replay gate — book.py's credit caveat)")
    b1_n = len(picked)
    b1_dates = len({r["date"] for r in picked})
    b1_dol = sum(r["R_dol"] for r in picked if r.get("R_dol") is not None)
    print(f"  B1 (stored contracts, stored R): {b1_n} positions / {b1_dates} dates "
          f"/ ${b1_dol:,.0f}")
    print(f"  expected (vol_sleeve 2026-08-12, same exports): {B1_EXPECTED_N} / "
          f"{B1_EXPECTED_DATES} / ${B1_EXPECTED_DOLLARS:,.0f}")
    g1 = (dc["n"] > 0 and b1_n == B1_EXPECTED_N and b1_dates == B1_EXPECTED_DATES
          and abs(b1_dol - B1_EXPECTED_DOLLARS) <= B1_DOLLAR_TOL)
    if selftest:
        g1 = g1 and abs(b1_dol - (B1_EXPECTED_DOLLARS + 1000)) <= B1_DOLLAR_TOL
        print("  [--selftest-gates] G1 target perturbed by +$1,000 — must FAIL")
    print(f"  G1: {'PASS' if g1 else 'FAIL'}")
    results["G1"] = g1

    # -- G2 replay identity at scale=1 --------------------------------------
    sub("G2 — scaling identity calibrated at scale=1 against the stored rows")
    print("""  The identity code path is run with factor 1 (stop = the harness's own
  $1,000) at the STORED contract count, under DEBIT_PROD — the profile that
  GENERATED the stored rows. It must reproduce (exit_reason, days_held,
  round(R,4)) exactly. Calibrating against the shipped be_after-0.50 merge
  instead would be testing an exit change, not the identity.""")
    n_ok = n_bad = 0
    bad_examples = []
    for rec in picked:
        if rec["credit"] or not rec["calibrated"]:
            continue
        c = rec["t"].contracts
        rp = replay_sized(rec, c, MAX_LOSS_ABS, profile=dict(DEBIT_PROD))
        want = (rec["exit_reason"], int(rec["days_held"]),
                round(_pct(rec["t"].row["realized_pnl_pct"]), 4))
        got = (rp["exit_reason"], rp["days_held"], round(rp["R"], 4))
        if selftest:
            got = (got[0], got[1] + 1, got[2])
        if want == got:
            n_ok += 1
        else:
            n_bad += 1
            if len(bad_examples) < 5:
                bad_examples.append((rec["date"], rec["ticker"], want, got))
    n_credit = sum(1 for r in picked if r["credit"])
    n_uncal = sum(1 for r in picked if not r["credit"] and not r["calibrated"])
    print(f"  calibrated debit picks re-replayed: {n_ok + n_bad}  exact={n_ok}  "
          f"mismatched={n_bad}")
    for d, tk, want, got in bad_examples:
        print(f"    MISMATCH {d} {tk}: want {want} got {got}")
    print(f"  credit picks (counted, NOT gated — book.py admits them ungated): "
          f"{n_credit}")
    print(f"  debit picks failing book.py's own calibration (excluded from G2): "
          f"{n_uncal}")
    if selftest:
        print("  [--selftest-gates] days_held inverted by +1 — must FAIL")
    g2 = (n_bad == 0 and (n_ok + n_bad) > 0)
    print(f"  G2: {'PASS' if g2 else 'FAIL'}")
    results["G2"] = g2

    # -- G3 ledger self-check ------------------------------------------------
    sub("G3 — ledger accounting identity, checked after every event")
    day_lists = P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)
    probe = simulate(day_lists, Cfg(label="G3 probe"), selftest_leak=selftest)
    led = probe.ledger
    print(f"  events checked: {led.checks}   positions: {len(probe.signal_pos)}")
    print(f"  final cash ${led.cash:,.2f}  reserved ${led.reserved:,.2f}  "
          f"realized ${led.realized:,.2f}  (capital ${led.capital:,.2f})")
    for v in led.violations[:5]:
        print(f"    VIOLATION {v}")
    if selftest:
        print("  [--selftest-gates] $1 leak injected into the identity — must FAIL")
    g3 = not led.violations
    print(f"  G3: {'PASS' if g3 else 'FAIL'}  ({len(led.violations)} violations)")
    results["G3"] = g3

    # -- G4 selection identity ----------------------------------------------
    sub("G4 — unconstrained walk reproduces top_k_per_day by set equality")
    unc = simulate(day_lists, Cfg(label="G4 probe", **UNCONSTRAINED))
    got_ids = {id(p.rec) for p in unc.signal_pos}
    got_ids |= {id(r) for r, why, _ in unc.skipped if why == "unsizable"}
    want_ids = {id(r) for r in picked}
    g4 = got_ids == want_ids
    print(f"  walk picks {len(got_ids)} (incl. {unc.census['unsizable']} unsizable "
          f"slot-burners)  vs top_k_per_day {len(want_ids)}")
    print(f"  symmetric difference: {len(got_ids ^ want_ids)}")
    if selftest:
        g4 = g4 and len(got_ids ^ want_ids) > 0
        print("  [--selftest-gates] expectation inverted — must FAIL")
    print(f"  G4: {'PASS' if g4 else 'FAIL'}")
    results["G4"] = g4

    ok = all(results.values())
    print(f"\n  GATES: {'ALL PASS' if ok else 'FAILED — ' + ', '.join(k for k, v in results.items() if not v)}")
    results["ok"] = ok
    return results


# ════════════════════════════════════════════════════════════════════════════
# Report sections
# ════════════════════════════════════════════════════════════════════════════

def print_population(recs, picked, episodes) -> None:
    hdr("POPULATION — dense episodes FIRST (primary), full book secondary")
    print("""  PRIMARY = maximal runs of signal dates with no internal gap > 5 trading
  sessions and at least 10 dates. SECONDARY = the full sparse book, which is an
  availability upper bound / concurrency lower bound and may not carry a
  conclusion alone (pre-registration, 'Population').""")
    dates = sorted({r["date"] for r in picked})
    print(f"\n  deployed signal dates: {len(dates)}  ({dates[0]} .. {dates[-1]})")
    sub("dense episodes")
    ep_dates = set()
    for i, ep in enumerate(episodes, 1):
        n_rows = sum(1 for r in picked if r["date"] in set(ep))
        span = sessions_between(ep[0], ep[-1])
        print(f"  E{i}  {ep[0]} .. {ep[-1]}   {len(ep):>3} dates over {span:>3} "
              f"sessions   {n_rows:>3} deployed picks")
        ep_dates |= set(ep)
    print(f"  total: {len(episodes)} episodes, {len(ep_dates)} dates, "
          f"{sum(1 for r in picked if r['date'] in ep_dates)} deployed picks")
    excluded = [d for d in dates if d not in ep_dates]
    print(f"  excluded from PRIMARY: {len(excluded)} isolated dates")


def print_baselines(picked, b2: Sim, cfg: Cfg, label: str) -> dict:
    hdr(f"[{label}] B1 / B2 BASELINES")
    b1_n = len(picked)
    b1_dol = sum(r["R_dol"] for r in picked if r.get("R_dol") is not None)
    b1_R = fmean([r["R"] for r in picked])
    print(f"  B1  stored contracts, stored outcomes     "
          f"n={b1_n:>4}  dates={len({r['date'] for r in picked}):>3}  "
          f"${b1_dol:>10,.0f}  meanR {b1_R:+.3f}")
    b2_rows = b2.rows()
    print(f"  B2  ${cfg.capital:,.0f} max-loss sizing, unconstrained  "
          f"n={len(b2_rows):>4}  dates={len(b2.dates):>3}  "
          f"${b2.dollars:>10,.0f}  meanR {fmean([r['R'] for r in b2_rows]):+.3f}")
    print(f"\n  B1 -> B2 isolates GRANULARITY (contract counts), B2 -> constrained "
          f"isolates the CAPS.")
    print(f"  B2/B1 dollar ratio {pct_ratio(b2.dollars, b1_dol):.2f}x — the small "
          f"account holds fewer contracts, so the dollar book shrinks by SIZE before "
          f"any\n  constraint is applied. B1's stored counts are a $50k book's.")
    return dict(b1_n=b1_n, b1_dol=b1_dol, b2_dol=b2.dollars)


def print_granularity(picked, cfg: Cfg) -> None:
    hdr(f"[{cfg.label}] GRANULARITY — what 2% of $25k buys vs 2% of $50k")
    rows = [(r, r["max_loss_per_contract"]) for r in picked]
    usable = [(r, m) for r, m in rows if m and m > 0]
    print(f"  deployed picks {len(rows)}   with usable max_loss {len(usable)}   "
          f"unsizable {len(rows) - len(usable)}")
    for cap, budget in ((50_000.0, 1_000.0), (cfg.capital, cfg.budget)):
        cs = [risk_contracts(m, budget) for _, m in usable]
        dist = Counter(cs)
        floor = sum(1 for _, m in usable if int(budget / m) == 0)
        breach = sum(1 for _, m in usable if m > budget)
        top = "  ".join(f"{k}c:{v}" for k, v in sorted(dist.items())[:8])
        print(f"\n  ${cap:,.0f} account / ${budget:,.0f} budget")
        print(f"    contracts distribution: {top}"
              + ("  ..." if len(dist) > 8 else ""))
        print(f"    mean {fmean(cs):.2f} contracts   median {statistics.median(cs):.1f}")
        print(f"    1-contract FLOOR share   {floor}/{len(usable)} "
              f"({floor / len(usable):.0%})  (int(budget/max_loss) == 0)")
        print(f"    budget-BREACH share      {breach}/{len(usable)} "
              f"({breach / len(usable):.0%})  (max_loss > budget at 1 contract)")
        risks = [m * risk_contracts(m, budget) / cap for _, m in usable]
        print(f"    realized per-position risk %: median {statistics.median(risks):.1%}  "
              f"p90 {sorted(risks)[int(0.9 * len(risks))]:.1%}  max {max(risks):.1%}")


def print_utilisation(sim: Sim, label: str) -> None:
    hdr(f"[{label}] UTILISATION — reserved capital and delta-notional")
    ser = session_series(sim)
    if not ser:
        print("  no occupied sessions.")
        return
    cap = sim.cfg.capital
    by_month: dict[str, list] = defaultdict(list)
    for s, v in ser.items():
        by_month[s.isoformat()[:7]].append(v)
    print(f"  {'month':<9} {'sess':>5} {'res% avg':>9} {'res% max':>9} "
          f"{'gross avg':>10} {'gross max':>10} {'net avg':>9} {'net max':>9} "
          f"{'open avg':>9} {'open max':>9}")
    for m, vs in sorted(by_month.items()):
        print(f"  {m:<9} {len(vs):>5} "
              f"{fmean([v['reserved'] / cap for v in vs]):>9.2f} "
              f"{max(v['reserved'] / cap for v in vs):>9.2f} "
              f"{fmean([v['gross'] / cap for v in vs]):>10.2f} "
              f"{max(v['gross'] / cap for v in vs):>10.2f} "
              f"{fmean([abs(v['net']) / cap for v in vs]):>9.2f} "
              f"{max(abs(v['net']) / cap for v in vs):>9.2f} "
              f"{fmean([v['n'] for v in vs]):>9.1f} "
              f"{max(v['n'] for v in vs):>9d}")
    sub("10 most-constrained sessions (by reserved capital / equity)")
    worst = sorted(ser.items(), key=lambda kv: -kv[1]["reserved"])[:10]
    for s, v in worst:
        print(f"  {s}  reserved ${v['reserved']:>9,.0f} ({v['reserved'] / cap:>5.2f}x)  "
              f"gross {v['gross'] / cap:>5.2f}x  net {abs(v['net']) / cap:>5.2f}x  "
              f"open {v['n']:>3}")


def print_census(sim: Sim, label: str) -> bool:
    hdr(f"[{label}] BINDING-CONSTRAINT CENSUS (A4 self-check)")
    c = sim.census
    order = ["taken", "taken_downsized", "cash", "per_pos_delta", "net_delta",
             "min1_refusal", "day3_cap", "unsizable"]
    total = sum(c[k] for k in order)
    for k in order:
        print(f"  {k:<18} {c[k]:>5}")
    print(f"  {'TOTAL considered':<18} {total:>5}")
    n_cand = total  # every candidate falls in exactly one bucket by construction
    hedge = c["hedge_taken"] + c["hedge_rejected"]
    if hedge:
        print(f"  (hedge sleeve, outside the day cap: taken {c['hedge_taken']}  "
              f"rejected {c['hedge_rejected']})")
    if sim.downsize_reason:
        print("  downsizes by binding constraint: " +
              "  ".join(f"{k}={v}" for k, v in sim.downsize_reason.items()))
    n_taken = c["taken"] + c["taken_downsized"]
    ok = (n_taken == len(sim.signal_pos)
          and total == n_taken + c["cash"] + c["per_pos_delta"] + c["net_delta"]
          + c["min1_refusal"] + c["day3_cap"] + c["unsizable"])
    print(f"  A4 sum check: taken {n_taken} == positions {len(sim.signal_pos)} and "
          f"buckets partition {n_cand} candidates -> {'OK' if ok else 'MISMATCH'}")
    binding = [(k, c[k]) for k in ("cash", "per_pos_delta", "net_delta",
                                   "min1_refusal", "day3_cap") if c[k]]
    if binding:
        top = max(binding, key=lambda kv: kv[1])
        print(f"  MOST BINDING constraint: {top[0]} ({top[1]} of "
              f"{sum(v for _, v in binding)} exclusions)")
    return ok


def print_adverse(sim: Sim, label: str) -> None:
    hdr(f"[{label}] ADVERSE-ORDERING CHECK — rejected vs taken counterfactual R")
    print("""  If the constraints systematically skip the BETTER picks, the account is
  not merely smaller than the paper book, it is adversely selected. The
  counterfactual R is the rejected pick replayed at the size it would have
  been given.""")
    taken_R = [p.R for p in sim.signal_pos]
    groups: dict[str, list] = defaultdict(list)
    for rec, why, cf in sim.skipped:
        if cf is not None:
            groups[why].append(cf["R"])
    print(f"\n  taken                n={len(taken_R):>4}  meanR {fmean(taken_R):+.3f}")
    for why, vals in sorted(groups.items()):
        print(f"  rejected [{why:<14}] n={len(vals):>4}  meanR {fmean(vals):+.3f}  "
              f"delta vs taken {fmean(vals) - fmean(taken_R):+.3f}")
    n_day3 = sum(1 for _, why, _ in sim.skipped if why == "day3_cap")
    print(f"  (day3_cap skips carry no counterfactual replay: {n_day3} candidates "
          f"never reached)")


def print_equity(sim: Sim, b2: Sim, label: str) -> dict:
    hdr(f"[{label}] EQUITY CURVE — constrained vs B2, and drawdown")
    print("  REALIZED curve: P&L is booked on the session a position exits, the same")
    print("  basis bear_deploy.max_drawdown is used on elsewhere. Open positions are")
    print("  not marked to market, so this understates intra-position drawdown.")
    out = {}
    for name, s in (("constrained", sim), ("B2 unconstrained", b2)):
        sess, vals = equity_curve(s.signal_pos)
        mdd = max_drawdown(vals)
        tot = sum(vals)
        print(f"  {name:<18} sessions={len(sess):>4}  total ${tot:>10,.0f}  "
              f"maxDD ${mdd:>10,.0f}  worst session ${min(vals) if vals else 0:>9,.0f}")
        out[name] = dict(total=tot, mdd=mdd)
    cap = sim.cfg.capital
    mdd = out["constrained"]["mdd"]
    print(f"\n  constrained maxDD {abs(mdd) / cap:.1%} of ${cap:,.0f} starting capital "
          f"(A3 limit {A3_MAXDD_FRACTION:.0%})")
    if sim.taken != sim.signal_pos:
        sess, vals = equity_curve(sim.taken)
        print(f"  incl. hedge sleeve: total ${sum(vals):,.0f}  maxDD ${max_drawdown(vals):,.0f}")
    return out


def print_cap_grid(day_lists, base: Cfg, label: str) -> None:
    hdr(f"[{label}] CAP GRID — monotonicity read ONLY")
    print("""  ANTI-TUNING RULE (pre-registered): no cap value may be adopted,
  recommended, or carried into a conclusion on the basis of its P&L here. The
  only admissible reading is qualitative monotonicity; a non-monotone surface
  is evidence of a ledger bug, not an opportunity.""")
    sub(f"HEADLINE CELL — per-pos {PER_POSITION_CAP:.2f} x net {NET_CAP:.2f} "
        f"(pre-registered, quoted first and alone)")
    head = simulate(day_lists, Cfg(label=label, per_pos_cap=PER_POSITION_CAP,
                                   net_cap=NET_CAP, capital=base.capital))
    print(f"  n={len(head.signal_pos)}  dates={len(head.dates)}  "
          f"${head.dollars:,.0f}  meanR {fmean([p.R for p in head.signal_pos]):+.3f}")
    sub("full grid (context; read monotonicity, nothing else)")
    corner = "per-pos / net"
    heads = [f"{v:.2f}" if v != float("inf") else "inf" for v in NET_GRID]
    print(f"  {corner:<14}" + "".join(f"{h:>14}" for h in heads))
    grid: dict[tuple, tuple] = {}
    for pp in PER_POS_GRID:
        cells = []
        for nc in NET_GRID:
            s = simulate(day_lists, Cfg(label=label, per_pos_cap=pp, net_cap=nc,
                                        capital=base.capital))
            grid[(pp, nc)] = (s.dollars, len(s.signal_pos))
            cells.append(f"{s.dollars:>9,.0f}/{len(s.signal_pos):<3}")
        lab = f"{pp:.2f}" if pp != float("inf") else "inf"
        print(f"  {lab:<14}" + "".join(f"{c:>14}" for c in cells))
    print("  (cell = total $ / positions taken)")

    sub("monotonicity read")
    rows_mono = sum(1 for pp in PER_POS_GRID
                    if all(grid[(pp, a)][0] <= grid[(pp, b)][0] + 1e-9
                           for a, b in zip(NET_GRID, NET_GRID[1:])))
    cols_mono = sum(1 for nc in NET_GRID
                    if all(grid[(a, nc)][0] <= grid[(b, nc)][0] + 1e-9
                           for a, b in zip(PER_POS_GRID, PER_POS_GRID[1:])))
    print(f"  rows monotone in the net cap:      {rows_mono}/{len(PER_POS_GRID)}")
    print(f"  columns monotone in the per-pos cap: {cols_mono}/{len(NET_GRID)}")
    print("""  A non-monotone surface is pre-registered as evidence of a ledger bug. It has
  a second, mechanical source that the pre-registration did not anticipate and
  that this report records rather than argues away: the walk is STATEFUL, so a
  cap that rejects a large early position leaves net-delta headroom the looser
  cap has already spent, and the tighter grid can therefore end up holding MORE
  positions. G3's per-event accounting identity and G4's selection identity both
  pass, so the surface is path dependence, not leakage — but no cap value may be
  read off it either way.""")


def print_arms(day_lists, bear_by_day, capital: float, label: str) -> dict:
    hdr(f"[{label}] ARMS — R vs D, F1 vs F2, and ARM H")
    print("  HEADLINE CELL = (R, F1): reject on breach, take the 1-contract floor.")
    print("  That is what production does; the other three are reported, not adopted.\n")
    print(f"  {'arm':<28}{'n':>5}{'dates':>7}{'total $':>12}{'meanR':>9}"
          f"{'win':>7}{'maxDD $':>11}")
    out = {}
    for key, arm_label, kw in (
            ("RF1", "(R, F1)  HEADLINE", dict(downsize=False, take_floor=True)),
            ("RF2", "(R, F2)", dict(downsize=False, take_floor=False)),
            ("DF1", "(D, F1)", dict(downsize=True, take_floor=True)),
            ("DF2", "(D, F2)", dict(downsize=True, take_floor=False))):
        s = simulate(day_lists, Cfg(label=label, capital=capital, **kw))
        rs = [p.R for p in s.signal_pos]
        _, vals = equity_curve(s.signal_pos)
        print(f"  {arm_label:<28}{len(rs):>5}{len(s.dates):>7}{s.dollars:>12,.0f}"
              f"{fmean(rs):>9.3f}"
              f"{(sum(1 for v in rs if v > 0) / len(rs) if rs else float('nan')):>7.0%}"
              f"{max_drawdown(vals):>11,.0f}")
        out[key] = s
    f1, f2 = out["RF1"], out["RF2"]
    n_refused = f2.census["min1_refusal"]
    examined = (sum(f2.census[k] for k in ("taken", "taken_downsized", "cash",
                                           "per_pos_delta", "net_delta",
                                           "min1_refusal")))
    print(f"\n  F1 vs F2 — the study's central object: F2 refuses the "
          f"{n_refused} sized candidates whose\n  1-contract max loss exceeds the "
          f"${capital * RISK_PER_TRADE_PCT:,.0f} budget "
          f"({pct_ratio(n_refused, examined):.0%} of the {examined} candidates it "
          f"sized).")
    print(f"  positions {len(f1.signal_pos)} -> {len(f2.signal_pos)}   "
          f"total ${f1.dollars:,.0f} -> ${f2.dollars:,.0f} "
          f"({f2.dollars - f1.dollars:+,.0f})   "
          f"meanR {fmean([p.R for p in f1.signal_pos]):+.3f} -> "
          f"{fmean([p.R for p in f2.signal_pos]):+.3f}")
    d1 = out["DF1"]
    print(f"  R vs D — downsizing rescues {d1.census['taken_downsized']} picks the "
          f"reject arm dropped;\n  total ${f1.dollars:,.0f} -> ${d1.dollars:,.0f} "
          f"({d1.dollars - f1.dollars:+,.0f})")
    return out


def print_hedge(day_lists, bear_by_day, capital: float, label: str) -> None:
    hdr(f"[{label}] ARM H — the shipped bear sleeve on the constrained run")
    print("""  1 bear-debit position per signal date, chosen by |delta| DESCENDING
  (bear_deploy D4-adopted), sized at int(0.5 x risk contracts) with a floor of
  1, entered AFTER the day's signal picks so it can never displace one. This is
  the only way net-vs-gross delta-notional becomes measurable: only 1 of the
  220 deployed picks is negative-delta, so without a sleeve net == gross.""")
    for name, hedge in (("without sleeve", False), ("with sleeve", True)):
        s = simulate(day_lists, Cfg(label=label, capital=capital, hedge=hedge),
                     bear_by_day=bear_by_day)
        ser = session_series(s)
        if not ser:
            continue
        gross = fmean([v["gross"] / capital for v in ser.values()])
        net = fmean([abs(v["net"]) / capital for v in ser.values()])
        gmax = max(v["gross"] / capital for v in ser.values())
        nmax = max(abs(v["net"]) / capital for v in ser.values())
        sig = [p for p in s.taken if not p.hedge]
        hed = [p for p in s.taken if p.hedge]
        print(f"\n  {name}")
        print(f"    signal positions {len(sig):>4}  ${sum(p.dollars for p in sig):>10,.0f}"
              f"   sleeve positions {len(hed):>4}  ${sum(p.dollars for p in hed):>10,.0f}")
        print(f"    total ${sum(p.dollars for p in s.taken):>10,.0f}   "
              f"gross avg {gross:.2f}x max {gmax:.2f}x   net avg {net:.2f}x max {nmax:.2f}x")
        print(f"    net/gross divergence: avg {gross - net:+.2f}x  max-session "
              f"{gmax - nmax:+.2f}x")
        if hedge:
            print(f"    sleeve rejected by caps on {s.census['hedge_rejected']} dates")


# ════════════════════════════════════════════════════════════════════════════
# Criteria + verdict
# ════════════════════════════════════════════════════════════════════════════

def evaluate(sim: Sim, b2: Sim, label: str) -> dict:
    hdr(f"[{label}] CRITERIA A1-A6")
    rows = sim.rows()
    res = {}

    # A1 EDGE SURVIVAL
    mean_R = fmean([r["R"] for r in rows])
    lo, hi = P.boot_ci_by_date(rows, key="R") if rows else (float("nan"),) * 2
    _, pos_years, years = P.sign_stable(rows, key="R") if rows else (None, 0, {})
    a1 = bool(rows) and mean_R > 0 and lo > 0 and pos_years == len(years) and years
    print(f"  A1 EDGE SURVIVAL  meanR {mean_R:+.3f}  CI95 [{lo:+.3f},{hi:+.3f}]  "
          f"years " + "  ".join(f"{y}:{m:+.3f}" for y, m in years.items()))
    print(f"     {'MET' if a1 else 'NOT MET'}  (needs mean>0, CI excluding zero, "
          f"every year positive)")
    res["A1"] = a1

    # A2 ATTRITION — same dates
    same = sim.dates
    b2_same = sum(p.dollars for p in b2.signal_pos if p.rec["date"] in same)
    ratio = pct_ratio(sim.dollars, b2_same)
    a2 = ratio >= A2_ATTRITION_FLOOR
    print(f"  A2 ATTRITION      constrained ${sim.dollars:,.0f} vs B2 on the same "
          f"{len(same)} dates ${b2_same:,.0f}  = {ratio:.0%}")
    print(f"     {'MET' if a2 else 'NOT MET'}  (needs >= {A2_ATTRITION_FLOOR:.0%})")
    res["A2"] = a2

    # A3 NO BLOWUP
    _, vals = equity_curve(sim.signal_pos)
    mdd = max_drawdown(vals)
    over = bool(sim.ledger.violations)
    a3 = (not over) and abs(mdd) <= A3_MAXDD_FRACTION * sim.cfg.capital
    print(f"  A3 NO BLOWUP      maxDD ${mdd:,.0f} = {abs(mdd) / sim.cfg.capital:.1%} of "
          f"capital;  ledger violations {len(sim.ledger.violations)}")
    print(f"     {'MET' if a3 else 'NOT MET'}  (needs no over-reservation and DD "
          f"<= {A3_MAXDD_FRACTION:.0%})")
    res["A3"] = a3

    # A4 ATTRIBUTION — computed by print_census, re-derived here
    c = sim.census
    n_taken = c["taken"] + c["taken_downsized"]
    total = n_taken + c["cash"] + c["per_pos_delta"] + c["net_delta"] + \
        c["min1_refusal"] + c["day3_cap"] + c["unsizable"]
    a4 = (n_taken == len(sim.signal_pos)
          and total == sum(c[k] for k in ("taken", "taken_downsized", "cash",
                                          "per_pos_delta", "net_delta",
                                          "min1_refusal", "day3_cap", "unsizable")))
    print(f"  A4 ATTRIBUTION    {total} candidates partition exactly into "
          f"{n_taken} taken + exclusions")
    print(f"     {'MET' if a4 else 'NOT MET'}  (mismatch FAILS the run)")
    res["A4"] = a4

    # A5 STABILITY
    cuts, cut_n = {}, {}
    for name in ("ex_2025_mar_apr", "ex_2026_feb_apr"):
        months = P.DOMINANT_WINDOWS[name]
        kept = [p for p in sim.signal_pos if p.rec["date"][:7] not in months]
        c_dol = sum(p.dollars for p in kept)
        b_dol = sum(p.dollars for p in b2.signal_pos
                    if p.rec["date"][:7] not in months and p.rec["date"] in same)
        cuts[name] = pct_ratio(c_dol, b_dol)
        cut_n[name] = len(kept)
    base_ratio = ratio
    moves = {k: (v - base_ratio) for k, v in cuts.items()}
    a5 = all(abs(m) <= A5_RATIO_TOLERANCE for m in moves.values() if m == m)
    print(f"  A5 STABILITY      constrained/B2 ratio ALL {base_ratio:.0%} "
          f"(n={len(sim.signal_pos)});  " +
          "  ".join(f"{k.replace('ex_', 'ex-')} {v:.0%} ({m * 100:+.0f}pt, n={cut_n[k]})"
                    for k, (v, m) in ((k, (cuts[k], moves[k])) for k in cuts)))
    print(f"     {'MET' if a5 else 'NOT MET'}  (needs <= "
          f"{A5_RATIO_TOLERANCE * 100:.0f} points of movement on both cuts)")
    res["A5"] = a5

    # A6 CREDIT SENSITIVITY — A1 on the debit-only subset
    deb = [r for r in rows if not r["credit"]]
    if deb:
        d_mean = fmean([r["R"] for r in deb])
        d_lo, d_hi = P.boot_ci_by_date(deb, key="R")
        _, d_pos, d_years = P.sign_stable(deb, key="R")
        a6 = d_mean > 0 and d_lo > 0 and d_pos == len(d_years) and bool(d_years)
        print(f"  A6 CREDIT SENS.   debit-only n={len(deb)}  meanR {d_mean:+.3f}  "
              f"CI95 [{d_lo:+.3f},{d_hi:+.3f}]  years " +
              "  ".join(f"{y}:{m:+.3f}" for y, m in d_years.items()))
    else:
        a6 = False
        print("  A6 CREDIT SENS.   no debit rows")
    print(f"     {'MET' if a6 else 'NOT MET'}  (A1 must hold on debit-only)")
    res["A6"] = a6
    return res


def print_verdict(res: dict, label: str) -> str:
    hdr(f"VERDICT ({label} population — the pre-registered primary)")
    for k in ("A1", "A2", "A3", "A4", "A5", "A6"):
        print(f"  {k}  {'MET' if res[k] else 'NOT MET'}")
    if not res["A1"]:
        verdict = "NOT FEASIBLE AT $25k"
    elif res["A1"] and res["A2"] and res["A3"] and res["A5"] and res["A6"]:
        verdict = "FEASIBLE"
    elif res["A1"] and res["A3"] and not res["A2"]:
        verdict = "FEASIBLE-BUT-DEGRADED"
    else:
        failed = [k for k in ("A2", "A3", "A5", "A6") if not res[k]]
        verdict = ("NO PRE-REGISTERED VERDICT MATCHES — A1 holds but "
                   + ", ".join(failed) + " fail(s)")
    print(f"\n  >>> {verdict} <<<")
    if verdict.startswith("NO PRE-REGISTERED"):
        print("""
  The three pre-registered verdicts (FEASIBLE = A1^A2^A3^A5^A6;
  FEASIBLE-BUT-DEGRADED = A1^A3 with A2 failing; NOT FEASIBLE AT $25k = A1
  fails) do not partition the outcome space, and the run landed in the gap.
  Nothing is relabelled to fit: the checklist above is the result, and the
  verdict grammar is recorded as incomplete for whoever replicates this.""")
    if not res["A4"]:
        print("  A4 MISMATCH — the run FAILS regardless of the verdict above.")
    return verdict


def print_capital_ladder(day_lists_by_pop, label: str) -> None:
    hdr("CAPITAL LADDER — operator note, printed only because A1 failed")
    print("""  Same anti-tuning rule: this is the smallest capital in {25k, 35k, 50k} at
  which A1 AND A2 pass, not a recommendation to trade any of them. The $35k rung
  cannot express its $700 dollar stop exactly through the frozen $1,000 harness
  (700 does not divide 1000); it is rounded UP to a TIGHTER stop, the
  conservative direction, and the affected position count is printed.""")
    day_lists, picked = day_lists_by_pop
    smallest = None
    for cap in CAPITAL_LADDER:
        cfg = Cfg(label=f"{label} ${cap:,.0f}", capital=cap)
        s = simulate(day_lists, cfg)
        b2 = simulate(day_lists, Cfg(label="B2", capital=cap, **UNCONSTRAINED))
        rows = s.rows()
        mean_R = fmean([r["R"] for r in rows])
        lo, _ = P.boot_ci_by_date(rows, key="R") if rows else (float("nan"),) * 2
        _, pos_y, years = P.sign_stable(rows, key="R") if rows else (None, 0, {})
        a1 = bool(rows) and mean_R > 0 and lo > 0 and pos_y == len(years) and years
        same = s.dates
        b2_same = sum(p.dollars for p in b2.signal_pos if p.rec["date"] in same)
        ratio = pct_ratio(s.dollars, b2_same)
        a2 = ratio >= A2_ATTRITION_FLOOR
        print(f"  ${cap:>7,.0f}  n={len(rows):>4}  ${s.dollars:>10,.0f}  "
              f"meanR {mean_R:+.3f} CI-lo {lo:+.3f}  attrition {ratio:>5.0%}  "
              f"A1 {'MET' if a1 else 'no':<3}  A2 {'MET' if a2 else 'no':<3}"
              + (f"  [{s.stop_inexact} inexact-stop positions]" if s.stop_inexact else ""))
        if a1 and a2 and smallest is None:
            smallest = cap
    print(f"\n  smallest capital passing A1 AND A2: "
          + (f"${smallest:,.0f}" if smallest else "none of the three"))


# ════════════════════════════════════════════════════════════════════════════
# Driver
# ════════════════════════════════════════════════════════════════════════════

def report_population(recs, picked_all, dates_allowed, label: str,
                      capital: float = STARTING_CAPITAL) -> tuple[dict, Sim, Sim]:
    pop = [r for r in recs if r["date"] in dates_allowed]
    picked = [r for r in picked_all if r["date"] in dates_allowed]
    day_lists = P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible)
    bear_by_day: dict[str, list] = defaultdict(list)
    for r in pop:
        if r["structure"] in BEAR_DEBIT and not r["credit"]:
            bear_by_day[r["date"]].append(r)

    base = Cfg(label=label, capital=capital)
    head = simulate(day_lists, base)
    b2 = simulate(day_lists, Cfg(label=f"{label} B2", capital=capital, **UNCONSTRAINED))

    print_baselines(picked, b2, base, label)
    print_granularity(picked, base)
    print_utilisation(head, label)
    print_census(head, label)
    print_adverse(head, label)
    print_equity(head, b2, label)
    print_arms(day_lists, bear_by_day, capital, label)
    print_hedge(day_lists, bear_by_day, capital, label)
    print_cap_grid(day_lists, base, label)
    res = evaluate(head, b2, label)
    return res, head, b2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gates-only", action="store_true",
                    help="run G1-G4 and stop")
    ap.add_argument("--selftest-gates", action="store_true",
                    help="invert one expectation inside EVERY gate; the run MUST "
                         "then fail (demonstrates the gates can fire)")
    ap.add_argument("--include-bs", action="store_true",
                    help="include bs_options_hist proxy rows (dropped as evidence "
                         "2026-08-11; off by default)")
    args = ap.parse_args(argv)

    hdr("account_sim — $25,000 FEASIBILITY simulation of the shipped ladder")
    print(f"""  Pre-registered 2026-08-13. Selection FROZEN (top-3/day, tiers A+B,
  ladder_rank). Exits FROZEN (shipped debit merge / CREDIT_PROD). Capital
  ${STARTING_CAPITAL:,.0f}, risk {RISK_PER_TRADE_PCT:.0%} = ${STARTING_CAPITAL * RISK_PER_TRADE_PCT:,.0f} per
  position on a MAX-LOSS basis, {MAX_POSITIONS_PER_DAY} positions/day,
  per-position delta-notional cap {PER_POSITION_CAP:.2f}x equity, net cap {NET_CAP:.2f}x equity.
  NOTHING SHIPS FROM THIS STUDY UNDER ANY OUTCOME. No annualised figure,
  Sharpe, or time-to-recover appears anywhere in this report by construction.""")

    recs, diag = load_book(include_bs=args.include_bs)
    picked = P.top_k_per_day(recs, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)
    episodes = dense_episodes(d for d, _ in P.ordered_by_day(
        recs, P.ladder_rank, P.ladder_eligible))

    print_population(recs, picked, episodes)
    gates = run_gates(recs, diag, picked, selftest=args.selftest_gates)
    if not gates["ok"]:
        print("\nGATE FAILURE — no results printed. Exit 1.")
        return 1
    if args.gates_only:
        print("\n--gates-only: gates passed, stopping before the report.")
        return 0

    ep_dates = {d for ep in episodes for d in ep}
    all_dates = {r["date"] for r in recs}

    res_primary, head_primary, _ = report_population(
        recs, picked, ep_dates, "PRIMARY dense episodes")
    report_population(recs, picked, all_dates, "SECONDARY full book")

    verdict = print_verdict(res_primary, "PRIMARY dense episodes")

    if not res_primary["A1"]:
        pop = [r for r in recs if r["date"] in ep_dates]
        print_capital_ladder(
            (P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible),
             [r for r in picked if r["date"] in ep_dates]),
            "PRIMARY dense episodes")

    hdr("CLOSE")
    print(f"  verdict: {verdict}")
    print("  Nothing in this report is a shippable rule. The cap values are a "
          "friction model,\n  not a tuned parameter; the pre-registration forbids "
          "adopting any of them on P&L.")
    if not res_primary["A4"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
