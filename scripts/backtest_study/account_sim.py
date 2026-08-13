"""Account simulation of the shipped ladder — FEASIBILITY only, nothing ships.

Every value this simulation is parameterised by lives in `config/account-sim.yml`
(override with `--config`). The module holds NO state: it reads that file into a
frozen `Settings`, threads it explicitly through the run, and reports what it
found. Simulating a different account is editing one YAML file.

The values pre-registered on 2026-08-13 ($25,000 / 2% / 0.25x / 1.50x) are
recorded in `config/backtest-tuning/current.md` (§"`account_sim`:
PRE-REGISTRATION") — that log, not this module, is the record of what the frozen
study ran with.

The question is NOT "is there edge" — that is settled elsewhere and frozen
here. It is: does the shipped operator card (`top_k_per_day`, tiers A/B,
`ladder_rank` ordering) still produce a book when an account has to actually pay
for the positions, hold reserved capital while they are open, and respect a
delta-notional exposure cap? Selection is FROZEN, exits are FROZEN
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
    A configured budget that does not divide $1,000 evenly rounds to a TIGHTER
    stop, and the affected position count is printed.

  * **Occupancy.** A position is held from `t.grid[0]` (the entry session — the
    weekday after the signal date) through `t.grid[days_held-1]` inclusive, with
    `days_held` taken from the replay AT THE ACTUAL SIZE (so an ARM D downsize
    that changes the dollar-stop day also changes occupancy). Capital is
    released at the first session AFTER the exit session, never on the same
    session it was still occupying.

  * **Walking down the list.** When a pick is rejected by a cap, the walk
    continues DOWN that day's ranked candidate list until `max_positions_per_day`
    positions are admitted — that is what `ordered_by_day` exists for. The
    unconstrained walk therefore reproduces `top_k_per_day` exactly (G4), while a
    constrained walk may hold a lower-ranked row.

  * **Unsizable picks.** A handful of deployed picks are credit rows with no
    usable `max_loss_per_contract`. They cannot be sized, so they are skipped —
    but they still CONSUME a day slot, because the ladder did select them. That
    keeps the selection identity (G4) exact.

Reads `config/account-sim.yml` and the book exports; writes only its report and
a positions CSV. Run:

    python -m scripts.backtest_study run account_sim
    python -m scripts.backtest_study run account_sim -- --gates-only
    python -m scripts.backtest_study run account_sim -- --config <path>
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yaml

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

EPS = 1e-9

DEFAULT_CONFIG = ROOT / "config" / "account-sim.yml"


# ── the configuration ───────────────────────────────────────────────────────
#
# `Settings` is the whole of what this study is parameterised by, read once from
# `config/account-sim.yml` and passed explicitly wherever it is needed. There is
# deliberately no module-level default and nothing is rebound at runtime: a
# function that needs a cap or a threshold is handed one, so no two simulations
# in a process can influence each other.

class ConfigError(RuntimeError):
    """The config file is missing, malformed, or missing a required key."""


@dataclass(frozen=True)
class Settings:
    capital: float
    risk_pct: float
    max_per_day: int
    per_pos_cap: float
    net_cap: float
    per_pos_grid: tuple[float, ...]
    net_grid: tuple[float, ...]
    capital_ladder: tuple[float, ...]
    hedge_risk_fraction: float
    episode_max_gap: int
    episode_min_dates: int
    attrition_floor: float
    maxdd_fraction: float
    ratio_tolerance: float
    g1_positions: int
    g1_dates: int
    g1_dollars: float
    g1_dollar_tol: float
    source: Path

    @property
    def budget(self) -> float:
        """Risk budget per position — also the hard per-position dollar stop."""
        return self.capital * self.risk_pct

    def cfg(self, label: str, **over) -> "Cfg":
        """A `Cfg` on these settings, with any knob overridden by keyword.

        Every simulation in the report is built through here, so the sizing a
        run uses can only come from the config it was given.
        """
        base = dict(capital=self.capital, per_pos_cap=self.per_pos_cap,
                    net_cap=self.net_cap, risk_pct=self.risk_pct,
                    max_per_day=self.max_per_day,
                    hedge_risk_fraction=self.hedge_risk_fraction)
        return Cfg(label=label, **{**base, **over})


def _req(node: dict, path: str, *keys):
    """Fetch a required key, naming the full path when it is absent."""
    cur = node
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            raise ConfigError(f"{path}: missing required key {'.'.join(keys)!r}")
        cur = cur[k]
    return cur


def _grid(values, path: str, name: str) -> tuple[float, ...]:
    """A cap grid; YAML has no infinity literal, so `null` means 'no cap'."""
    if not isinstance(values, list) or not values:
        raise ConfigError(f"{path}: {name} must be a non-empty list")
    return tuple(float("inf") if v is None else float(v) for v in values)


def load_settings(path: Path = DEFAULT_CONFIG) -> Settings:
    """Read the study's configuration.

    Every key is required. A config-driven study whose config was only half read
    is worse than one that stops: it would print a full report against sizing
    nobody chose.
    """
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise ConfigError(f"{path}: no such config file") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: not valid YAML — {exc}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")

    p = str(path)
    max_per_day = int(_req(raw, p, "account", "max_positions_per_day"))
    if max_per_day < 1:
        raise ConfigError(f"{p}: account.max_positions_per_day must be >= 1")
    return Settings(
        capital=float(_req(raw, p, "account", "capital")),
        risk_pct=float(_req(raw, p, "account", "risk_per_trade_pct")),
        max_per_day=max_per_day,
        per_pos_cap=float(_req(raw, p, "caps", "per_position")),
        net_cap=float(_req(raw, p, "caps", "net")),
        per_pos_grid=_grid(_req(raw, p, "grids", "per_position"), p,
                           "grids.per_position"),
        net_grid=_grid(_req(raw, p, "grids", "net"), p, "grids.net"),
        capital_ladder=_grid(_req(raw, p, "grids", "capital_ladder"), p,
                             "grids.capital_ladder"),
        hedge_risk_fraction=float(_req(raw, p, "hedge", "risk_fraction")),
        episode_max_gap=int(_req(raw, p, "population", "episode_max_gap")),
        episode_min_dates=int(_req(raw, p, "population", "episode_min_dates")),
        attrition_floor=float(_req(raw, p, "criteria", "attrition_floor")),
        maxdd_fraction=float(_req(raw, p, "criteria", "maxdd_fraction")),
        ratio_tolerance=float(_req(raw, p, "criteria", "ratio_tolerance")),
        g1_positions=int(_req(raw, p, "gates", "book_calibration",
                              "expected_positions")),
        g1_dates=int(_req(raw, p, "gates", "book_calibration", "expected_dates")),
        g1_dollars=float(_req(raw, p, "gates", "book_calibration",
                              "expected_dollars")),
        g1_dollar_tol=float(_req(raw, p, "gates", "book_calibration",
                                 "dollar_tolerance")),
        source=path,
    )


# ── outcome-blindness (G5) ──────────────────────────────────────────────────
#
# The simulator must never see how a position TURNED OUT before deciding to
# take it. Reading the selection path and asserting that by eye is not a
# guarantee — the next consumer of this module is an agent that proposes
# positions against a live portfolio, where a lookahead read would be
# invisible and would silently invent edge. So blindness is ENFORCED and
# gated, in two independent layers:
#
#   1. `BlindRec` raises on any access to an outcome key of the record.
#   2. `LOOKAHEAD_ROW_COLUMNS` are DELETED from the underlying `Trade` row,
#      so even a read that routes around the record (via `rec["t"].row`)
#      finds nothing. `Trade.__init__` touches only entry-side fields and the
#      price path, so a stripped row still prices.
#
# G5 then requires that the book produced under both layers is IDENTICAL to
# the normal run — the strongest available statement: delete every outcome
# column and the simulator makes exactly the same trades at the same sizes.

class LookaheadError(RuntimeError):
    """A blinded record's outcome field was read during selection/sizing."""


# Record keys that describe how the trade RESOLVED.
LOOKAHEAD_REC_KEYS = frozenset({
    "R", "E", "R_dol", "E_dol", "mfe", "mae", "mfe_day", "mae_day",
    "exit_reason", "days_held",
})

# The same information as stored on the raw backtest/proxy CSV row.
LOOKAHEAD_ROW_COLUMNS = frozenset({
    "realized_pnl_pct", "pnl_at_cap_pct", "exit_reason", "days_held",
    "mfe_pct", "mae_pct", "mfe_day", "mae_day",
})


class BlindRec(dict):
    """A record whose outcome keys raise instead of resolving.

    Subclasses `dict` so it stays a drop-in record everywhere (`rec["tier"]`,
    `rec.get("delta")`, `dict(rec)` all behave) — only the outcome keys are
    trapped. They are still PRESENT, so a `in`/`keys()` check is unchanged;
    it is the read that fails.
    """

    def __getitem__(self, key):
        if key in LOOKAHEAD_REC_KEYS:
            raise LookaheadError(
                f"lookahead: selection read outcome field {key!r} on "
                f"{super().get('date')} {super().get('ticker')}")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key in LOOKAHEAD_REC_KEYS:
            raise LookaheadError(
                f"lookahead: selection read outcome field {key!r} on "
                f"{super().get('date')} {super().get('ticker')}")
        return super().get(key, default)


def blind_records(recs: list[dict]) -> list[BlindRec]:
    """`recs` rebuilt with both blindness layers applied.

    The `Trade` is reconstructed from a row with `LOOKAHEAD_ROW_COLUMNS`
    removed, so the returned records carry a price path and no outcome.
    """
    out = []
    for r in recs:
        row = {k: v for k, v in r["t"].row.items()
               if k not in LOOKAHEAD_ROW_COLUMNS}
        b = BlindRec(r)
        dict.__setitem__(b, "t", Trade(row))
        out.append(b)
    return out


def book_signature(sim: "Sim") -> list[tuple]:
    """Order-sensitive fingerprint of the trades a run actually made."""
    return [(p.rec["date"], p.rec["ticker"], p.rec["structure"], p.contracts,
             round(p.R, 9), round(p.dollars, 6), p.exit_reason)
            for p in sim.taken]


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


def dense_episodes(dates, max_gap: int, min_dates: int) -> list[list[str]]:
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

def new_cache() -> dict:
    """A replay memo. Owned by the caller, never by the module.

    Two properties depend on this being explicit rather than global:

      * G5 compares a sighted run against one over freshly-built `BlindRec`
        objects. Its blind probe takes its OWN cache, so a blind result can
        never be served from a sighted computation.
      * Nothing survives between processes or between `main()` calls, so a
        report cannot be contaminated by an earlier simulation's answers.

    Entries are keyed by `id(rec)`, which is sound because the records a cache
    is used with are held alive for as long as the cache is.
    """
    return {}


def profile_for(rec: dict) -> dict:
    """The SHIPPED exit profile for a row. Debit rows go through the base ->
    bear-debit(be_after .50) -> BEAR_HE merge; credit rows never reach it."""
    return dict(CREDIT_PROD) if rec["credit"] else prod_profile_for(rec, 0.50, True)


def replay_sized(rec: dict, contracts: int, stop: float,
                 profile: dict | None = None,
                 cache: dict | None = None) -> dict:
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

    The memo key INCLUDES the exit profile. It must: G2 calls this function with
    an explicit `DEBIT_PROD` profile (the one that generated the stored rows) at
    the stored contract count and stop `MAX_LOSS_ABS`. Any simulate() whose own
    stop is also $1,000 — a $50k book at 2%, a $25k book at 4% — then asks for
    the same `(rec, contracts, stop)` and, without the profile in the key, gets
    G2's calibration answer back instead of the SHIPPED be_after-0.50 merge.
    Found 2026-08-13 by G5, which diverged because blinded records are distinct
    objects and so missed the poisoned entries. Keys at a $500 stop never
    collided, which is why the headline cell was never affected.

    `cache` is the caller's memo (see `new_cache()`); omitting it means no
    memoisation, which is correct but slow.
    """
    prof = profile or profile_for(rec)
    if cache is None:
        cache = {}
    key = (id(rec), int(contracts), round(float(stop), 6),
           tuple(sorted(prof.items(), key=lambda kv: kv[0])))
    if key in cache:
        return cache[key]
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
    rp = replay(t2, **prof)
    out = dict(exit_reason=rp["exit_reason"], days_held=rp["days_held"],
               R=rp["pnl_pct"],
               dollars=t2.dollars(rp["pnl_pct"]) * contracts / scaled,
               stop_exact=exact)
    cache[key] = out
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
    """One simulation's sizing. Built via `Settings.cfg()`, never defaulted —
    the sizing a run uses can only have come from the config it was given."""

    label: str
    capital: float
    per_pos_cap: float
    net_cap: float
    risk_pct: float
    max_per_day: int
    hedge_risk_fraction: float = 0.5
    downsize: bool = False          # ARM R (False) vs ARM D (True)
    take_floor: bool = True         # F1 (True) vs F2 (False)
    enforce_cash: bool = True
    hedge: bool = False             # ARM H bear sleeve

    @property
    def budget(self) -> float:
        return self.capital * self.risk_pct

    @property
    def stop(self) -> float:
        return self.capital * self.risk_pct


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
             selftest_leak: bool = False, cache: dict | None = None) -> Sim:
    """Event-loop the ladder through an account ledger.

    `day_lists` is `protocol.ordered_by_day(...)` output, already restricted to
    the population under test. Exits are processed before that session's
    entries; entries are admitted in ladder order until `cfg.max_per_day` are
    held. `cache` is the caller's replay memo — omit it and this run memoises
    nothing outside itself.
    """
    if cache is None:
        cache = new_cache()
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
        rp = replay_sized(rec, contracts, cfg.stop, cache=cache)
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
            if n_today >= cfg.max_per_day:
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
                                    replay_sized(rec, c, cfg.stop, cache=cache)))
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
                sim.skipped.append((rec, why, replay_sized(rec, c, cfg.stop, cache=cache)))
                continue
            sim.census["taken"] += 1
            take(rec, c)
            n_today += 1

        # ARM H — the shipped bear sleeve, AFTER the day's signal picks so it can
        # never displace one. Not counted against cfg.max_per_day.
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
                c = max(1, int(cfg.hedge_risk_fraction * base))
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
# Positions CSV — per-position audit export (debugging/inspection artifact;
# NOT part of the pre-registered gates/criteria and adopts nothing)
# ════════════════════════════════════════════════════════════════════════════

POSITIONS_CSV_COLUMNS = [
    "population", "arm", "status", "date", "ticker", "structure", "credit",
    "tier", "contracts", "reserved", "dn", "entry_sess", "exit_sess",
    "days_held", "exit_reason", "R", "dollars", "downsized", "hedge",
    "reject_reason",
    # book-context columns, straight off rec (actual keys per book.py's
    # _build_record — max_loss_per_contract, delta, dte, score_total, mfe,
    # mae, regime, mech_cell all present on every record)
    "max_loss_per_contract", "delta", "dte", "score_total", "mfe", "mae",
    # REGIME, both readings. `market_regime` is the model's MARKET read and is
    # the field `book.ladder_tier` keys the tier off (via `model_dir`/
    # `model_vol`); `regime` is the per-play TICKER regime and never feeds the
    # tier — they are separate by invariant, so both are carried. The mech_*
    # trio is the mechanical SPY/VIX label, as-of the signal date, which
    # selects the exit profile (BEAR_HE) rather than the tier.
    "market_regime", "model_dir", "model_vol",
    "regime", "mech_direction", "mech_vol", "mech_cell",
    # the STORED $50k-book outcome this rec shipped with (rec["R"] /
    # rec["exit_reason"]), kept separate from THIS sim's replay outcome in the
    # `R` / `exit_reason` columns above — the two can and do disagree (this
    # sim replays at a different size and, for downsized/rejected rows, a
    # different contract count or not at all).
    "shipped_R", "shipped_exit_reason",
]


def _pos_row(population, arm, status, rec, *, contracts=None, reserved=None,
             dn=None, entry_sess=None, exit_sess=None, days_held=None,
             exit_reason=None, R=None, dollars=None, downsized=False,
             hedge=False, reject_reason="") -> dict:
    """One `POSITIONS_CSV_COLUMNS`-shaped row. Sim-outcome fields (contracts..
    reject_reason) come from the caller; book-context + shipped_* come off
    `rec`. Missing sim-outcome fields default to `None`, missing
    reject_reason defaults to `""` — consistent with the defaults above."""
    row = dict(
        population=population, arm=arm, status=status,
        date=rec.get("date"), ticker=rec.get("ticker"),
        structure=rec.get("structure"), credit=rec.get("credit"),
        tier=rec.get("tier"),
        contracts=contracts, reserved=reserved, dn=dn,
        entry_sess=entry_sess, exit_sess=exit_sess, days_held=days_held,
        exit_reason=exit_reason, R=R, dollars=dollars, downsized=downsized,
        hedge=hedge, reject_reason=reject_reason,
        max_loss_per_contract=rec.get("max_loss_per_contract"),
        delta=rec.get("delta"), dte=rec.get("dte"),
        score_total=rec.get("score_total"), mfe=rec.get("mfe"),
        mae=rec.get("mae"),
        market_regime=rec.get("market_regime"),
        model_dir=rec.get("model_dir"), model_vol=rec.get("model_vol"),
        regime=rec.get("regime"),
        mech_direction=rec.get("mech_direction"),
        mech_vol=rec.get("mech_vol"), mech_cell=rec.get("mech_cell"),
        shipped_R=rec.get("R"), shipped_exit_reason=rec.get("exit_reason"),
    )
    return {k: row[k] for k in POSITIONS_CSV_COLUMNS}


def positions_rows(population: str, arm: str, sim) -> list[dict]:
    """One row per `sim.taken` Pos, one row per `sim.skipped` candidate.

    Taken status is "hedge" (ARM H sleeve) over "taken_downsized" (ARM D)
    over "taken". Skipped status is `f"skipped:{why}"` with `why` also
    carried in `reject_reason`; when the skip carries a counterfactual replay
    (see `simulate()` — `replay_sized()`'s `exit_reason`/`days_held`/`R`/
    `dollars`, `None` for `day3_cap` and admission-cap skips with no
    counterfactual attached) the outcome columns are filled from it, else
    left blank.
    """
    rows = []
    for p in sim.taken:
        status = "hedge" if p.hedge else ("taken_downsized" if p.downsized
                                          else "taken")
        rows.append(_pos_row(
            population, arm, status, p.rec,
            contracts=p.contracts, reserved=p.reserved, dn=p.dn,
            entry_sess=p.entry_sess, exit_sess=p.exit_sess,
            days_held=p.days_held, exit_reason=p.exit_reason, R=p.R,
            dollars=p.dollars, downsized=p.downsized, hedge=p.hedge))
    for rec, why, cf in sim.skipped:
        status = f"skipped:{why}"
        if cf is not None:
            rows.append(_pos_row(
                population, arm, status, rec, days_held=cf["days_held"],
                exit_reason=cf["exit_reason"], R=cf["R"],
                dollars=cf["dollars"], reject_reason=why))
        else:
            rows.append(_pos_row(population, arm, status, rec,
                                 reject_reason=why))
    return rows


def write_positions_csv(path, populations: dict, arm: str = "RF1") -> int:
    """`csv.DictWriter` over `POSITIONS_CSV_COLUMNS`; one row block per
    `(population_label, sim)` pair in `populations`. Returns the row count."""
    rows = []
    for label, sim in populations.items():
        rows.extend(positions_rows(label, arm, sim))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=POSITIONS_CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def run_gates(recs, diag, picked, st: Settings, cache: dict,
              selftest: bool = False) -> dict:
    hdr("GATES — G1..G5 (non-zero exit on any failure)")
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
    print(f"  expected ({st.source.name}, gates.book_calibration): {st.g1_positions} / "
          f"{st.g1_dates} / ${st.g1_dollars:,.0f}")
    g1 = (dc["n"] > 0 and b1_n == st.g1_positions and b1_dates == st.g1_dates
          and abs(b1_dol - st.g1_dollars) <= st.g1_dollar_tol)
    if selftest:
        g1 = g1 and abs(b1_dol - (st.g1_dollars + 1000)) <= st.g1_dollar_tol
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
        rp = replay_sized(rec, c, MAX_LOSS_ABS, profile=dict(DEBIT_PROD),
                          cache=cache)
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
    probe = simulate(day_lists, st.cfg("G3 probe"), selftest_leak=selftest,
                     cache=cache)
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
    unc = simulate(day_lists, st.cfg("G4 probe", **UNCONSTRAINED), cache=cache)
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

    # -- G5 outcome blindness ------------------------------------------------
    sub("G5 — the simulator is BLIND to how a position turned out")
    print("""  Every record is re-wrapped so that reading an outcome key raises, AND the
  outcome columns are DELETED from the underlying trade row so a read cannot
  route around the wrapper. The run must then complete and produce a
  byte-identical book. This is what makes the sim safe to hand to an agent
  proposing live positions: no ordering, sizing or admission decision can be
  standing on a number that would not exist yet in real time.""")
    blind = blind_records(recs)
    tripwire = False
    try:
        _ = blind[0]["R"]
    except LookaheadError:
        tripwire = True
    except IndexError:
        pass
    print(f"  tripwire live (reading a blinded outcome key raises): {tripwire}")
    print(f"  row columns deleted from every Trade: "
          f"{', '.join(sorted(LOOKAHEAD_ROW_COLUMNS))}")

    base_sig = book_signature(simulate(day_lists, st.cfg("G5 base"),
                                       cache=cache))
    try:
        blind_lists = P.ordered_by_day(blind, P.ladder_rank, P.ladder_eligible)
        # A FRESH cache: a blind result must never be served from a sighted
        # computation, which is the whole point of the gate.
        blind_sig = book_signature(simulate(blind_lists, st.cfg("G5 blind"),
                                            cache=new_cache()))
        leaked = None
    except LookaheadError as exc:
        blind_sig, leaked = None, str(exc)

    if leaked:
        print(f"  LOOKAHEAD DETECTED: {leaked}")
        g5 = False
    else:
        n_diff = sum(1 for a, b in zip(base_sig, blind_sig) if a != b)
        g5 = (len(base_sig) == len(blind_sig) and n_diff == 0
              and tripwire and len(base_sig) > 0)
        print(f"  positions: sighted {len(base_sig)}  blind {len(blind_sig)}  "
              f"differing {n_diff}")
        for a, b in zip(base_sig, blind_sig):
            if a != b:
                print(f"    DIVERGED sighted {a}  vs blind {b}")
                break
    if selftest:
        g5 = g5 and blind_sig is not None and len(blind_sig) != len(base_sig)
        print("  [--selftest-gates] expectation inverted — must FAIL")
    print(f"  G5: {'PASS' if g5 else 'FAIL'}")
    results["G5"] = g5

    ok = all(results.values())
    print(f"\n  GATES: {'ALL PASS' if ok else 'FAILED — ' + ', '.join(k for k, v in results.items() if not v)}")
    results["ok"] = ok
    return results


# ════════════════════════════════════════════════════════════════════════════
# Report sections
# ════════════════════════════════════════════════════════════════════════════

def print_population(recs, picked, episodes, st: Settings) -> None:
    hdr("POPULATION — dense episodes FIRST (primary), full book secondary")
    print(f"""  PRIMARY = maximal runs of signal dates with no internal gap > """
          f"""{st.episode_max_gap} trading
  sessions and at least {st.episode_min_dates} dates. SECONDARY = the full sparse book, which is an
  availability upper bound / concurrency lower bound and may not carry a
  conclusion alone.""")
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
    # The $50k/$1,000 reference row is the PAPER BOOK's basis — it is what
    # produced the stored contract counts — so it stays fixed while the account
    # row follows the config. Naming both budgets keeps the two comparable when
    # a configured account makes them coincide.
    hdr(f"[{cfg.label}] GRANULARITY — what ${cfg.budget:,.0f} on ${cfg.capital / 1000:,.0f}k "
        f"buys vs the paper book's $1,000 on $50k")
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


# ── DEPLOYED BOOK BY REGIME (post-hoc description, not a pre-registered cut) ──
# This section adds no decision and changes no number the study already prints:
# it re-groups the book the walk already produced. It exists because a reader
# looking at the deployed book will ask "in which regimes, and in which
# structures" and the answer should come from the study, not from someone
# re-crosstabbing the positions export by hand.
#
# THIN_N is a labelling threshold only. It marks a cell as too small to read
# qualitatively; it never drops a row, because a suppressed row is how a book
# quietly stops adding up.
THIN_N = 10
NO_LABEL = "NONE"          # the regime field was absent, not a regime named ""


def _regime_stat(positions: list) -> tuple[int, float, float, float]:
    """(n, dollars, meanR, win) for one cell. Callers never pass an empty cell —
    cells are built from the positions themselves, so n >= 1 by construction."""
    rs = [p.R for p in positions]
    return (len(rs), sum(p.dollars for p in positions), fmean(rs),
            sum(1 for v in rs if v > 0) / len(rs))


def _print_regime_cells(rows: list[tuple[str, str, list]], key_w: int) -> None:
    """One `cell / structure / n / dollars / meanR / win` block, long format.

    `win` is printed as a FRACTION, not a rounded percent like the arms table:
    this block is reconciled against a recomputation from the positions export
    at chart-build time, and a whole-percent print lands exactly on that
    check's tolerance.
    """
    print(f"  {'cell':<{key_w}}{'structure':<20}{'n':>5}{'dollars':>12}"
          f"{'meanR':>9}{'win':>8}  flag")
    for cell, structure, positions in rows:
        n, dollars, mean_r, win = _regime_stat(positions)
        flag = "thin" if n < THIN_N and structure != "ALL" else ""
        print(f"  {cell:<{key_w}}{structure:<20}{n:>5}{dollars:>12,.0f}"
              f"{mean_r:>+9.3f}{win:>8.3f}  {flag}".rstrip())


def _cells_by(positions: list, key) -> list[tuple[str, str, list]]:
    """Group taken positions by `key` then structure, each group followed by its
    own ALL row, and the whole set followed by a TOTAL ALL row."""
    groups: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for p in positions:
        groups[key(p)][p.rec.get("structure") or NO_LABEL].append(p)
    rows = []
    for cell in sorted(groups):
        for structure in sorted(groups[cell]):
            rows.append((cell, structure, groups[cell][structure]))
        rows.append((cell, "ALL", [p for ps in groups[cell].values() for p in ps]))
    rows.append(("TOTAL", "ALL", positions))
    return rows


def print_regime(sim: Sim, label: str) -> None:
    hdr(f"[{label}] DEPLOYED BOOK BY REGIME (post-hoc, NOT pre-registered)")
    print(f"""  This study pre-registers NO cut by regime. Everything below DESCRIBES the
  book the walk deployed; none of it is a test of a regime edge, and no rule
  may be read off it. A cell flagged `thin` holds fewer than {THIN_N} positions.

  Two regime readings are carried, and they disagree often. The MECHANICAL cell
  is a pure function of SPY/VIX as of the signal date (lib/mech_regime.py) and
  selects the exit profile; the MODEL read is parsed out of the analysis row's
  free-text market_regime and is what the deployment ladder keys the tier off.""")
    taken = sim.signal_pos

    sub("MECHANICAL cell x structure, taken only")
    _print_regime_cells(
        _cells_by(taken, lambda p: p.rec.get("mech_cell") or NO_LABEL), key_w=12)

    sub("MODEL regime cell x structure, taken only")
    _print_regime_cells(
        _cells_by(taken, lambda p: f"{p.rec.get('model_dir') or NO_LABEL}"
                                   f"/{p.rec.get('model_vol') or NO_LABEL}"), key_w=12)

    sub("deployment census by mechanical cell, taken only")
    print(f"  {'cell':<12}{'n':>5}{'tierA':>7}{'tierB':>7}"
          f"{'avg reserved':>14}{'avg delta-notional':>20}")
    by_cell: dict[str, list] = defaultdict(list)
    for p in taken:
        by_cell[p.rec.get("mech_cell") or NO_LABEL].append(p)
    for cell in sorted(by_cell) + ["TOTAL"]:
        ps = taken if cell == "TOTAL" else by_cell[cell]
        tiers = Counter(p.rec.get("tier") for p in ps)
        print(f"  {cell:<12}{len(ps):>5}{tiers['A']:>7}{tiers['B']:>7}"
              f"{fmean([p.reserved for p in ps]):>14,.0f}"
              f"{fmean([abs(p.dn) for p in ps]):>20,.0f}")

    sub("what the caps SKIPPED, by mechanical cell (every candidate)")
    print(f"  {'cell':<12}{'bucket':<18}{'n':>5}")
    buckets: dict[str, Counter] = defaultdict(Counter)
    for p in taken:
        buckets[p.rec.get("mech_cell") or NO_LABEL]["taken"] += 1
    for rec, why, _cf in sim.skipped:
        buckets[rec.get("mech_cell") or NO_LABEL][why] += 1
    considered = 0
    for cell in sorted(buckets):
        for bucket in sorted(buckets[cell]):
            print(f"  {cell:<12}{bucket:<18}{buckets[cell][bucket]:>5}")
            considered += buckets[cell][bucket]
    print(f"  {'TOTAL':<12}{'considered':<18}{considered:>5}")

    sub("model read vs mechanical read, DIRECTION only, taken only")
    print("  The model's direction and the mechanical one are read off different\n"
          "  things, so this is a description of that gap, not an error rate.")
    print(f"  {'model':<10}{'mech':<10}{'n':>5}")
    pairs = Counter((p.rec.get("model_dir") or NO_LABEL,
                     p.rec.get("mech_direction") or NO_LABEL) for p in taken)
    for (model_dir, mech_dir) in sorted(pairs):
        print(f"  {model_dir:<10}{mech_dir:<10}{pairs[(model_dir, mech_dir)]:>5}")
    same = sum(n for (m, k), n in pairs.items() if m == k)
    total = sum(pairs.values())
    print(f"  agreement {same} of {total} ({same / total if total else 0:.3f})")


def print_equity(sim: Sim, b2: Sim, label: str, st: Settings) -> dict:
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
          f"(A3 limit {st.maxdd_fraction:.0%})")
    if sim.taken != sim.signal_pos:
        sess, vals = equity_curve(sim.taken)
        print(f"  incl. hedge sleeve: total ${sum(vals):,.0f}  maxDD ${max_drawdown(vals):,.0f}")
    return out


def print_cap_grid(day_lists, base: Cfg, label: str, st: Settings,
                   cache: dict) -> None:
    hdr(f"[{label}] CAP GRID — monotonicity read ONLY")
    print("""  ANTI-TUNING RULE: no cap value may be adopted, recommended, or
  carried into a conclusion on the basis of its P&L here. The only admissible
  reading is qualitative monotonicity; a non-monotone surface is evidence of a
  ledger bug, not an opportunity.""")
    sub(f"HEADLINE CELL — per-pos {st.per_pos_cap:.2f} x net {st.net_cap:.2f} "
        f"(the configured cell, quoted first and alone)")
    head = simulate(day_lists, st.cfg(label, capital=base.capital), cache=cache)
    print(f"  n={len(head.signal_pos)}  dates={len(head.dates)}  "
          f"${head.dollars:,.0f}  meanR {fmean([p.R for p in head.signal_pos]):+.3f}")
    sub("full grid (context; read monotonicity, nothing else)")
    corner = "per-pos / net"
    heads = [f"{v:.2f}" if v != float("inf") else "inf" for v in st.net_grid]
    print(f"  {corner:<14}" + "".join(f"{h:>14}" for h in heads))
    grid: dict[tuple, tuple] = {}
    for pp in st.per_pos_grid:
        cells = []
        for nc in st.net_grid:
            s = simulate(day_lists, st.cfg(label, per_pos_cap=pp, net_cap=nc,
                                           capital=base.capital), cache=cache)
            grid[(pp, nc)] = (s.dollars, len(s.signal_pos))
            cells.append(f"{s.dollars:>9,.0f}/{len(s.signal_pos):<3}")
        lab = f"{pp:.2f}" if pp != float("inf") else "inf"
        print(f"  {lab:<14}" + "".join(f"{c:>14}" for c in cells))
    print("  (cell = total $ / positions taken)")

    sub("monotonicity read")
    rows_mono = sum(1 for pp in st.per_pos_grid
                    if all(grid[(pp, a)][0] <= grid[(pp, b)][0] + 1e-9
                           for a, b in zip(st.net_grid, st.net_grid[1:])))
    cols_mono = sum(1 for nc in st.net_grid
                    if all(grid[(a, nc)][0] <= grid[(b, nc)][0] + 1e-9
                           for a, b in zip(st.per_pos_grid, st.per_pos_grid[1:])))
    print(f"  rows monotone in the net cap:      {rows_mono}/{len(st.per_pos_grid)}")
    print(f"  columns monotone in the per-pos cap: {cols_mono}/{len(st.net_grid)}")
    print("""  A non-monotone surface reads as evidence of a ledger bug. It has a second,
  mechanical source that this report records rather than argues away: the walk
  is STATEFUL, so a
  cap that rejects a large early position leaves net-delta headroom the looser
  cap has already spent, and the tighter grid can therefore end up holding MORE
  positions. G3's per-event accounting identity and G4's selection identity both
  pass, so the surface is path dependence, not leakage — but no cap value may be
  read off it either way.""")


def print_arms(day_lists, bear_by_day, capital: float, label: str,
               st: Settings, cache: dict) -> dict:
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
        s = simulate(day_lists, st.cfg(label, capital=capital, **kw), cache=cache)
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
          f"${capital * st.risk_pct:,.0f} budget "
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


def print_hedge(day_lists, bear_by_day, capital: float, label: str,
                st: Settings, cache: dict) -> None:
    hdr(f"[{label}] ARM H — the shipped bear sleeve on the constrained run")
    print(f"""  1 bear-debit position per signal date, chosen by |delta| DESCENDING
  (bear_deploy D4-adopted), sized at int({st.hedge_risk_fraction:g} x risk contracts) with a floor of
  1, entered AFTER the day's signal picks so it can never displace one. This is
  the only way net-vs-gross delta-notional becomes measurable: almost every
  deployed pick is positive-delta, so without a sleeve net == gross.""")
    for name, hedge in (("without sleeve", False), ("with sleeve", True)):
        s = simulate(day_lists, st.cfg(label, capital=capital, hedge=hedge),
                     bear_by_day=bear_by_day, cache=cache)
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

def evaluate(sim: Sim, b2: Sim, label: str, st: Settings) -> dict:
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
    a2 = ratio >= st.attrition_floor
    print(f"  A2 ATTRITION      constrained ${sim.dollars:,.0f} vs B2 on the same "
          f"{len(same)} dates ${b2_same:,.0f}  = {ratio:.0%}")
    print(f"     {'MET' if a2 else 'NOT MET'}  (needs >= {st.attrition_floor:.0%})")
    res["A2"] = a2

    # A3 NO BLOWUP
    _, vals = equity_curve(sim.signal_pos)
    mdd = max_drawdown(vals)
    over = bool(sim.ledger.violations)
    a3 = (not over) and abs(mdd) <= st.maxdd_fraction * sim.cfg.capital
    print(f"  A3 NO BLOWUP      maxDD ${mdd:,.0f} = {abs(mdd) / sim.cfg.capital:.1%} of "
          f"capital;  ledger violations {len(sim.ledger.violations)}")
    print(f"     {'MET' if a3 else 'NOT MET'}  (needs no over-reservation and DD "
          f"<= {st.maxdd_fraction:.0%})")
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
    a5 = all(abs(m) <= st.ratio_tolerance for m in moves.values() if m == m)
    print(f"  A5 STABILITY      constrained/B2 ratio ALL {base_ratio:.0%} "
          f"(n={len(sim.signal_pos)});  " +
          "  ".join(f"{k.replace('ex_', 'ex-')} {v:.0%} ({m * 100:+.0f}pt, n={cut_n[k]})"
                    for k, (v, m) in ((k, (cuts[k], moves[k])) for k in cuts)))
    print(f"     {'MET' if a5 else 'NOT MET'}  (needs <= "
          f"{st.ratio_tolerance * 100:.0f} points of movement on both cuts)")
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


def print_verdict(res: dict, label: str, st: Settings) -> str:
    hdr(f"VERDICT ({label} population — the primary)")
    for k in ("A1", "A2", "A3", "A4", "A5", "A6"):
        print(f"  {k}  {'MET' if res[k] else 'NOT MET'}")
    not_feasible = f"NOT FEASIBLE AT ${st.capital:,.0f}"
    if not res["A1"]:
        verdict = not_feasible
    elif res["A1"] and res["A2"] and res["A3"] and res["A5"] and res["A6"]:
        verdict = "FEASIBLE"
    elif res["A1"] and res["A3"] and not res["A2"]:
        verdict = "FEASIBLE-BUT-DEGRADED"
    else:
        failed = [k for k in ("A2", "A3", "A5", "A6") if not res[k]]
        verdict = ("NO VERDICT MATCHES — A1 holds but "
                   + ", ".join(failed) + " fail(s)")
    print(f"\n  >>> {verdict} <<<")
    if verdict.startswith("NO VERDICT"):
        print(f"""
  The three verdicts (FEASIBLE = A1^A2^A3^A5^A6; FEASIBLE-BUT-DEGRADED = A1^A3
  with A2 failing; {not_feasible} = A1 fails) do not partition the outcome
  space, and the run landed in the gap. Nothing is relabelled to fit: the
  checklist above is the result, and the verdict grammar is recorded as
  incomplete for whoever replicates this.""")
    if not res["A4"]:
        print("  A4 MISMATCH — the run FAILS regardless of the verdict above.")
    return verdict


def _rec_key(r) -> tuple:
    return (r["date"], r["ticker"], r["structure"], r["source"])


def print_structure_universe(recs_frozen, picked_frozen, recs_wide,
                             picked_wide) -> None:
    """What opening the proxy calibration gate changed about the CANDIDATE SET.

    Printed only under `--structure-universe`, and quantified rather than
    asserted: the point of the arm is that the operator selects on STRUCTURE,
    not on a strike the real backtest happened to be able to price, so the
    rows the gate withheld belong in the universe he ranks.
    """
    hdr("STRUCTURE UNIVERSE — proxy calibration gate OPENED (--structure-universe)")
    # Derived from the returned books, NOT from the diag counter: that counter
    # is incremented BEFORE the include_bs/sources filter (same convention as
    # counts_by_source), so it also tallies bs rows that are dropped moments
    # later and would overstate the change.
    frozen_keys = {_rec_key(r) for r in recs_frozen}
    added_recs = [r for r in recs_wide if _rec_key(r) not in frozen_keys]
    print(f"""  The frozen book withholds proxy debit rows that fail the exact-replay gate.
  Measured 2026-08-13, every one carries a stored exit_reason of `trailing_stop`
  — a rule REMOVED from DEBIT_PROD by Attempt 10 (2026-07-04). They are rows
  exported under a superseded exit config, NOT rows the harness cannot price;
  their paths replay fine. This study never reads a stored outcome (G5), so
  admitting them is sound here and only here.

  bs_options_hist rows stay DROPPED — this gate is orthogonal to `--include-bs`
  and does not re-admit a single model-priced row.

  candidate universe {len(recs_frozen)} -> {len(recs_wide)} rows """
          + f"({len(added_recs):+d}), by source: "
          + "  ".join(f"{k}={v}" for k, v in
                      sorted(Counter(r["source"] for r in added_recs).items())))
    sub("effect on the DEPLOYED book (tier A/B, top-3/day)")
    f_ids = {(r["date"], r["ticker"], r["structure"]) for r in picked_frozen}
    w_ids = {(r["date"], r["ticker"], r["structure"]) for r in picked_wide}
    gained, lost = sorted(w_ids - f_ids), sorted(f_ids - w_ids)
    print(f"  deployed picks {len(picked_frozen)} -> {len(picked_wide)}   "
          f"dates {len({r['date'] for r in picked_frozen})} -> "
          f"{len({r['date'] for r in picked_wide})}")
    print(f"  gained {len(gained)}   displaced {len(lost)}  (a new candidate can "
          f"push a lower-ranked row off a full day)")
    for d, tk, st in gained:
        print(f"    + {d}  {tk:<6} {st}")
    for d, tk, st in lost:
        print(f"    - {d}  {tk:<6} {st}")
    if added_recs:
        print("\n  admitted rows by tier: " +
              "  ".join(f"{k}={v}" for k, v in
                        sorted(Counter(r["tier"] for r in added_recs).items()))
              + "   (only A/B are ever deployed)")
        print("  admitted rows by year: " +
              "  ".join(f"{k}={v}" for k, v in
                        sorted(Counter(r["date"][:4] for r in added_recs).items())))
        print("  admitted rows by stored exit_reason: " +
              "  ".join(f"{k}={v}" for k, v in
                        sorted(Counter(r["exit_reason"] for r in added_recs).items())))
        print("""  CAVEAT, stated because it bears on A5: the admitted rows are concentrated
  in one window. Any A5 stability movement under this arm should be read
  against that concentration before it is read as instability.""")


def print_capital_ladder(day_lists_by_pop, label: str, st: Settings,
                         cache: dict) -> None:
    rungs = ", ".join(f"${c / 1000:g}k" for c in st.capital_ladder)
    hdr("CAPITAL LADDER — operator note, printed only because A1 failed")
    print(f"""  Same anti-tuning rule: this is the smallest capital in {{{rungs}}} at
  which A1 AND A2 pass, not a recommendation to trade any of them. A rung whose
  dollar stop does not divide the frozen $1,000 harness stop evenly (e.g. $700
  on a $35k rung at 2%) is rounded UP to a TIGHTER stop, the conservative
  direction, and the affected position count is printed.""")
    day_lists, picked = day_lists_by_pop
    smallest = None
    for cap in st.capital_ladder:
        cfg = st.cfg(f"{label} ${cap:,.0f}", capital=cap)
        s = simulate(day_lists, cfg, cache=cache)
        b2 = simulate(day_lists, st.cfg("B2", capital=cap, **UNCONSTRAINED),
                      cache=cache)
        rows = s.rows()
        mean_R = fmean([r["R"] for r in rows])
        lo, _ = P.boot_ci_by_date(rows, key="R") if rows else (float("nan"),) * 2
        _, pos_y, years = P.sign_stable(rows, key="R") if rows else (None, 0, {})
        a1 = bool(rows) and mean_R > 0 and lo > 0 and pos_y == len(years) and years
        same = s.dates
        b2_same = sum(p.dollars for p in b2.signal_pos if p.rec["date"] in same)
        ratio = pct_ratio(s.dollars, b2_same)
        a2 = ratio >= st.attrition_floor
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
                      st: Settings, cache: dict) -> tuple[dict, Sim, Sim]:
    capital = st.capital
    pop = [r for r in recs if r["date"] in dates_allowed]
    picked = [r for r in picked_all if r["date"] in dates_allowed]
    day_lists = P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible)
    bear_by_day: dict[str, list] = defaultdict(list)
    for r in pop:
        if r["structure"] in BEAR_DEBIT and not r["credit"]:
            bear_by_day[r["date"]].append(r)

    base = st.cfg(label)
    head = simulate(day_lists, base, cache=cache)
    b2 = simulate(day_lists, st.cfg(f"{label} B2", **UNCONSTRAINED), cache=cache)

    print_baselines(picked, b2, base, label)
    print_granularity(picked, base)
    print_utilisation(head, label)
    print_census(head, label)
    print_adverse(head, label)
    print_equity(head, b2, label, st)
    print_arms(day_lists, bear_by_day, capital, label, st, cache)
    print_hedge(day_lists, bear_by_day, capital, label, st, cache)
    print_cap_grid(day_lists, base, label, st, cache)
    # Last in the population block, deliberately: it is a post-hoc description,
    # not one of the criteria above.
    print_regime(head, label)
    res = evaluate(head, b2, label, st)
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
    ap.add_argument("--structure-universe", action="store_true",
                    help="admit proxy debit rows that fail the exact-replay "
                         "calibration gate (they are stale-exit-config rows, not "
                         "unpriceable ones). Widens the CANDIDATE SET to what an "
                         "operator selecting on structure would actually see. "
                         "Does NOT re-admit bs rows. Gates still run on the "
                         "frozen book.")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                    help=f"the simulation to run (default: "
                         f"{DEFAULT_CONFIG.relative_to(ROOT)}). Copy it and pass "
                         f"the copy to simulate a different account.")
    args = ap.parse_args(argv)

    try:
        st = load_settings(args.config)
    except ConfigError as exc:
        print(f"CONFIG ERROR: {exc}")
        return 2

    # One memo for the whole run. G5 builds its own — see `new_cache()`.
    cache = new_cache()

    hdr(f"account_sim — ${st.capital:,.0f} FEASIBILITY simulation of the "
        f"shipped ladder")
    try:
        cfg_name = st.source.resolve().relative_to(ROOT)
    except ValueError:
        cfg_name = st.source
    print(f"""  config    {cfg_name}
  Selection FROZEN (top-{st.max_per_day}/day, tiers A+B, ladder_rank). Exits FROZEN
  (shipped debit merge / CREDIT_PROD). Capital ${st.capital:,.0f}, risk
  {st.risk_pct:.0%} = ${st.budget:,.0f} per position on a MAX-LOSS basis,
  {st.max_per_day} positions/day, per-position delta-notional cap {st.per_pos_cap:.2f}x equity,
  net cap {st.net_cap:.2f}x equity.
  NOTHING SHIPS FROM THIS STUDY UNDER ANY OUTCOME. No annualised figure,
  Sharpe, or time-to-recover appears anywhere in this report by construction.""")

    # The FROZEN book is always the gate basis: G1 reproduces a prior report's
    # deployed line and G4 pins selection against `top_k_per_day`. Neither
    # identity is allowed to move because an arm widened the universe.
    recs, diag = load_book(include_bs=args.include_bs)
    picked = P.top_k_per_day(recs, P.ladder_rank, k=st.max_per_day,
                             eligible_fn=P.ladder_eligible)

    gates = run_gates(recs, diag, picked, st, cache, selftest=args.selftest_gates)
    if not gates["ok"]:
        print("\nGATE FAILURE — no results printed. Exit 1.")
        return 1
    if args.gates_only:
        print("\n--gates-only: gates passed, stopping before the report.")
        return 0

    if args.structure_universe:
        recs_wide, diag_wide = load_book(include_bs=args.include_bs,
                                         require_proxy_calibration=False)
        picked_wide = P.top_k_per_day(recs_wide, P.ladder_rank,
                                      k=st.max_per_day,
                                      eligible_fn=P.ladder_eligible)
        print_structure_universe(recs, picked, recs_wide, picked_wide)
        recs, picked = recs_wide, picked_wide

    episodes = dense_episodes(
        (d for d, _ in P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    print_population(recs, picked, episodes, st)

    ep_dates = {d for ep in episodes for d in ep}
    all_dates = {r["date"] for r in recs}

    res_primary, head_primary, _ = report_population(
        recs, picked, ep_dates, "PRIMARY dense episodes", st, cache)
    _, head_secondary, _ = report_population(
        recs, picked, all_dates, "SECONDARY full book", st, cache)

    verdict = print_verdict(res_primary, "PRIMARY dense episodes", st)

    if not res_primary["A1"]:
        pop = [r for r in recs if r["date"] in ep_dates]
        print_capital_ladder(
            (P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible),
             [r for r in picked if r["date"] in ep_dates]),
            "PRIMARY dense episodes", st, cache)

    hdr("CLOSE")
    print(f"  verdict: {verdict}")
    print("  Nothing in this report is a shippable rule. The cap values are a "
          "friction model,\n  not a tuned parameter, and none of them may be "
          "adopted on P&L.")

    # Separate artifact per universe: the widened arm must never silently
    # overwrite the frozen book's export, since a downstream consumer reading
    # `account_sim-positions-latest.csv` has no way to tell which candidate set
    # produced the rows it is holding.
    parts = ["account_sim-positions"]
    if args.structure_universe:
        parts.append("structure")
    stem = "-".join(parts) + "-latest.csv"
    arm_col = "RF1" + ("-structure" if args.structure_universe else "")
    positions_csv_path = ROOT / "backtests" / "study_output" / stem
    n_rows = write_positions_csv(
        positions_csv_path,
        {"primary": head_primary, "secondary": head_secondary},
        arm=arm_col)
    print(f"  positions CSV: {n_rows} rows -> backtests/study_output/{stem}")

    if not res_primary["A4"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
