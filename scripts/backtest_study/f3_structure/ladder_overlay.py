"""Does a rolled short-call ladder beat selling the spread, and would a naked put beat both?

The operator's real trades are mostly this shape: a long-dated bull call spread
(the CORE) plus a SHORTER-DATED short call sold against it, replaced when it
expires. `financed_spread` ARM F4 sells that leg ONCE, at entry, never rolled,
and its registration says twice that "a rolling campaign is a separate future
registration". This is that registration
(`research/pre-registrations/f3_structure/ladder_overlay.md`), and this module is
its report.

Four questions, in the order they matter:

  1. is the ladder profitable versus closing the core at the shipped §5 exits?
  2. when should the short call be sold — at entry (T0), on a gap-up (TGAP), on
     a sustained rise (TRUN), or never (TNEVER) — and does holding the core
     longer while rolling short calls beat the profit target (the TEF cells), or
     does the short strike get breached too often (G4)?
  3. how does the answer behave under a fixed-volatility scenario (the `[MODEL]`
     tier, a SENSITIVITY) and across market-regime cuts (evidence)?
  4. would a naked short put in place of the core have yielded more (N cells)?

WHAT THIS MODULE OWNS AND WHAT IT BORROWS
-----------------------------------------
It owns the CELL TABLE, the gates, the report and the verdicts. It owns no
pricing and no campaign mechanics:

  * `lib/overlay_campaign.py` is the engine — triggers, the tranche lifecycle,
    the multi-tranche net-mark algebra, the cost model, the `[MODEL]` tier and
    the G1b identity. Never edited here.
  * `lib/ladder_targets.py` is the ONE owner of "which contracts does a campaign
    owe a core", shared with `scripts/collector/fetch_ladder_legs.py`.
  * `financed_spread` supplies the population/report idiom by import —
    `profile_for`, `replay_at`, `paired_rows`, `ex_both_cut`, `n_dates`,
    `powered`, `sleeve_daily`, `cell_corr`, `size_contracts`, the near-expiry
    and candidate machinery — and its ARM F4 construction is what gate G1b
    reproduces. Never refactored: its published cell means are pinned.
  * `bear_rewrap` supplies the pricing path (`reconstructs`, `net_entry`,
    `leg_details`, `leg_series`, `entry_price_of`). `lib/harness.py` is frozen.

AWAITING SCRAPE
---------------
Every ladder and naked-put cell needs contracts at expiries the BOOK never
traded. `scripts/collector/fetch_ladder_legs.py` fetches them into
`backtests/sweep_cache/ladder_manifest.csv`'s four categories. While that
manifest still holds PENDING rows for a category a cell needs, that cell carries
the verdict AWAITING SCRAPE: no criterion is evaluated on it and nothing about
it is a finding. The run still builds every cell on the CACHED SUBSET and still
runs G0/G1/G1b/G2/G3/G4 — the machinery is proved before the scrape ends, not
after — and exits 0, as the registration says and as `financed_spread` does for
its own AWAITING SCRAPE: the census IS the study's current, quotable status.
`DESIGNED_REFUSAL_EXIT_CODES` covers only `load_book`'s era refusals.

Read-only. Touches no config, writes no tab, scrapes nothing. Run:

    python3 -m scripts.backtest_study run ladder_overlay
    python3 -m scripts.backtest_study run ladder_overlay --era v3
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest.helpers import (  # noqa: E402
    _defined_risk_bounds, _max_loss_per_unit,
)
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import (  # noqa: E402
    cell_stats, fmt_row, hdr, sub,
)
from scripts.backtest_study.f3_structure import bear_rewrap as BR  # noqa: E402
from scripts.backtest_study.f3_structure import financed_spread as FS  # noqa: E402
from scripts.backtest_study.lib import greeks as GK  # noqa: E402
from scripts.backtest_study.lib import ladder_targets as LT  # noqa: E402
from scripts.backtest_study.lib import overlay_campaign as OC  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import underlying as UL  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.lib.harness import Trade  # noqa: E402

# Exit codes this study returns as a DESIGNED refusal rather than a failure:
# 2 = AWAITING SCRAPE (a cell's contracts are not cached yet) AND `lib/era.py`'s
# thin-era refusal, which shares the code; 3 = `load_book`'s era guard refusing
# an export set that is not the era asked for. `run.py` reads this by AST parse
# and never imports the module, so it MUST stay a literal module-level
# assignment — an alias or a `frozenset(...)` CALL would be invisible to the
# parse and a correct refusal would be reported as FAILED with its report
# deleted. A gate failure (G1b identity, G2 clamp attribution, E1 geometry, a
# MODEL-tier leak) is a REAL failure and exits 1, not a refusal.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

EXIT_GATE_FAILED = 1
EXIT_AWAITING_SCRAPE = 0   # registration: AWAITING SCRAPE exits 0 (financed_spread precedent)

# ── pre-registered constants (frozen; do not tune after a number is seen) ────

MIN_DATES = 25              # G0 floor — dates
MIN_ROWS = 60               # G0 floor — rows
MIN_SHARED_DATES = FS.MIN_SHARED_DATES      # E3 floor — 8 shared dates

#: G1b tolerance: this study's L-F4 mark series must equal `financed_spread`'s
#: F4 d20 hold series to a CENT A DAY on the shared rows.
G1B_TOL = 0.01
G1B_TARGET = OC.F4_IDENTITY_TARGET          # 0.20, imported not restated

#: The registered T-GAP sensitivity (`S-GAP103`). The PRIMARY threshold lives in
#: `overlay_campaign.TGAP_MIN_GAP` and is never touched.
SENS_GAP = 0.03

#: The one labelled cost sensitivity: $0.65 per contract per side and half the
#: quoted spread. SENSITIVITY ONLY — never a criterion, never a verdict.
SENS_COMMISSION = 0.65
SENS_SLIPPAGE = 0.5

#: Cores at least this many days from entry to expiry — the `S-DTE60` subset.
SENS_MIN_CORE_DTE = 60

CONFIG_PATH = ROOT / "config" / "backtest.yml"
ROWS_CSV = ROOT / "backtests" / "study_output" / "ladder_overlay-rows.csv"
MANIFEST_PATH = ROOT / "backtests" / "sweep_cache" / "ladder_manifest.csv"

#: The collector's four categories, in the order it fetches them.
CATEGORIES = ("ladder_call_t0", "ladder_call_roll", "ladder_put_core",
              "ladder_put_short")

# Core-exit axis. Three values, two of them PRIMARY.
X_SHIP, X_TEF, X_EXP, X_NONE = "X-SHIP", "X-TEF", "X-EXP", "X-NONE"
EXIT_DESC = {
    X_SHIP: "the shipped §5 debit profile for the baseline row's regime cell",
    X_TEF: "the same profile with NO profit target — held to the §5 time exit",
    X_EXP: "no profit target, no stop, no time exit: dollar_stop and the "
           "120-day path cap only (SENSITIVITY)",
    X_NONE: "n/a — the put IS the position: dollar_stop and the path cap only",
}

# Cell groups. Only PRIMARY and NAKED may earn a verdict.
PRIMARY, NAKED, SENSITIVITY = "PRIMARY", "NAKED", "SENSITIVITY"

# The verdict vocabulary, worded in the registration. Nothing else may be
# printed as a verdict.
VERDICTS = ("CANDIDATE", "RE-WRAP", "NULL", "UNDERPOWERED", "BREACH-DOMINATED",
            "AWAITING SCRAPE")
UNDERPOWERED = "UNDERPOWERED"
AWAITING = "AWAITING SCRAPE"


#: Re-exported so a caller can catch the guard without importing the engine.
ModelTierLeak = OC.ModelTierLeak


@dataclass(frozen=True)
class Cell:
    """One registered cell: a campaign, a core exit, a pricing tier, a label.

    `label` is the registration's own token and is what every table prints.
    `cats` is the set of scrape categories the cell's contracts come from — an
    empty set means the cell needs nothing fetched (only `L-BASE`).
    """

    label: str
    group: str
    exit: str
    desc: str
    spec: OC.CampaignSpec | None = None     # None == the no-overlay baseline
    cats: tuple[str, ...] = ()
    tier: str = OC.CACHE_TIER
    sigma_scale: float | None = None
    gap: float | None = None                # T-GAP threshold override
    min_core_dte: int | None = None         # cores >= N days only
    replaces_core: bool = False             # the naked-put cells
    fixed_put: bool = False                 # N-CORE's struck-at-the-core put

    @property
    def is_model(self) -> bool:
        return self.tier == OC.MODEL_TIER


def _call(trigger: str, roll: str, breach: str = OC.BHOLD,
          target: float = 0.20) -> OC.CampaignSpec:
    return OC.CampaignSpec(trigger=trigger, roll=roll, breach=breach,
                           target=target, opt_type=OC.CALL)


_T0_CATS = ("ladder_call_t0",)
_ROLL_CATS = ("ladder_call_t0", "ladder_call_roll")

# ── THE CELL TABLE — every label in the registration, built exactly once ─────
#
# PRIMARY: 8 ladder cells, all at |Delta| 0.20, BHOLD, call tranches.
# NAKED:   2 cells that REPLACE the core and are paired against the same L-BASE.
# SENSITIVITY: printed with n, never a criterion, never pooled with PRIMARY.
CELLS: tuple[Cell, ...] = (
    Cell("L-BASE", PRIMARY, X_SHIP,
         "the core alone — the baseline every ΔR is paired against"),
    Cell("L-F4", PRIMARY, X_SHIP,
         "one tranche at entry, never rolled — the G1b replication anchor",
         spec=_call(OC.T0, OC.R0), cats=_T0_CATS),
    Cell("L-T0", PRIMARY, X_SHIP, "sell at entry, roll each slot",
         spec=_call(OC.T0, OC.R1), cats=_ROLL_CATS),
    Cell("L-GAP", PRIMARY, X_SHIP, "sell after a gap-up, roll each slot",
         spec=_call(OC.TGAP, OC.R1), cats=_ROLL_CATS),
    Cell("L-RUN", PRIMARY, X_SHIP, "sell after a sustained rise, roll each slot",
         spec=_call(OC.TRUN, OC.R1), cats=_ROLL_CATS),
    Cell("L-T0-TEF", PRIMARY, X_TEF, "L-T0 held past the profit target",
         spec=_call(OC.T0, OC.R1), cats=_ROLL_CATS),
    Cell("L-GAP-TEF", PRIMARY, X_TEF, "L-GAP held past the profit target",
         spec=_call(OC.TGAP, OC.R1), cats=_ROLL_CATS),
    Cell("L-RUN-TEF", PRIMARY, X_TEF, "L-RUN held past the profit target",
         spec=_call(OC.TRUN, OC.R1), cats=_ROLL_CATS),

    Cell("N-CORE", NAKED, X_NONE,
         "a short put at the core's LONG strike and expiry, in place of the core",
         spec=OC.CampaignSpec(trigger=OC.T0, roll=OC.R0, breach=OC.BHOLD,
                              target=0.30, opt_type=OC.PUT),
         cats=("ladder_put_core",), replaces_core=True, fixed_put=True),
    Cell("N-ROLL", NAKED, X_NONE,
         "a short-dated |Δ| 0.30 put rolled on the ladder's slot schedule",
         spec=OC.CampaignSpec(trigger=OC.T0, roll=OC.R1, breach=OC.BHOLD,
                              target=0.30, opt_type=OC.PUT),
         cats=("ladder_put_short",), replaces_core=True),

    Cell("S-D30", SENSITIVITY, X_SHIP, "L-T0 at the |Δ| 0.30 target",
         spec=_call(OC.T0, OC.R1, target=0.30), cats=_ROLL_CATS),
    Cell("S-BBUY", SENSITIVITY, X_SHIP, "L-T0 buying the tranche back on a breach",
         spec=_call(OC.T0, OC.R1, breach=OC.BBUY), cats=_ROLL_CATS),
    Cell("S-BUP", SENSITIVITY, X_SHIP,
         "L-T0 buying back and rolling up-and-out on a breach",
         spec=_call(OC.T0, OC.R1, breach=OC.BUP), cats=_ROLL_CATS),
    Cell("S-XEXP", SENSITIVITY, X_EXP, "L-T0 held to the 120-day path cap",
         spec=_call(OC.T0, OC.R1), cats=_ROLL_CATS),
    Cell("S-GAP103", SENSITIVITY, X_SHIP, "L-GAP at a 1.03 gap threshold",
         spec=_call(OC.TGAP, OC.R1), cats=_ROLL_CATS, gap=SENS_GAP),
    Cell("S-DTE60", SENSITIVITY, X_SHIP, "L-T0 on cores >= 60 DTE only",
         spec=_call(OC.T0, OC.R1), cats=_ROLL_CATS,
         min_core_dte=SENS_MIN_CORE_DTE),
    Cell("S-MODEL x1.00", SENSITIVITY, X_SHIP,
         "L-T0 repriced at a CONSTANT entry-day IV", spec=_call(OC.T0, OC.R1),
         cats=_ROLL_CATS, tier=OC.MODEL_TIER, sigma_scale=1.00),
    Cell("S-MODEL x0.75", SENSITIVITY, X_SHIP,
         "L-T0 repriced at 0.75x the entry-day IV, held constant",
         spec=_call(OC.T0, OC.R1), cats=_ROLL_CATS, tier=OC.MODEL_TIER,
         sigma_scale=0.75),
    Cell("S-MODEL x1.25", SENSITIVITY, X_SHIP,
         "L-T0 repriced at 1.25x the entry-day IV, held constant",
         spec=_call(OC.T0, OC.R1), cats=_ROLL_CATS, tier=OC.MODEL_TIER,
         sigma_scale=1.25),
)

CELL_BY_LABEL = {c.label: c for c in CELLS}
BASE_LABEL = "L-BASE"

#: The regime columns the PRIMARY cells are additionally cut on. `mech_cell` is
#: the mechanical SPY/VIX cell; `mech_vol` and `model_vol` are the book's own
#: L-VOL / H-VOL reads (`lib/book.py::model_vol`).
REGIME_KEYS = ("mech_cell", "mech_vol", "model_vol")


# ── small shared helpers ─────────────────────────────────────────────────────

def _mean(vals) -> float:
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else float("nan")


def n_dates(rows: list[dict]) -> int:
    return FS.n_dates(rows)


def powered(rows: list[dict]) -> bool:
    """G0's floor, evaluated on this study's own constants."""
    return len(rows) >= MIN_ROWS and n_dates(rows) >= MIN_DATES


@contextmanager
def gap_threshold(value: float | None):
    """Run a campaign at a non-default T-GAP threshold, then put it back.

    `overlay_campaign.TGAP_MIN_GAP` is a FROZEN module constant read at call
    time by `trigger_days`, and the engine takes no threshold argument. The one
    registered alternative (`S-GAP103`, T-GAP at 1.03) therefore has to be
    driven by swapping the constant for the duration of that cell's build. It is
    restored unconditionally, and the PRIMARY value is never written back
    differently — a sensitivity may not leave a trace on the primary.
    """
    if value is None:
        yield
        return
    prev = OC.TGAP_MIN_GAP
    OC.TGAP_MIN_GAP = value
    try:
        yield
    finally:
        OC.TGAP_MIN_GAP = prev


@contextmanager
def raw_targets():
    """Read the strike ladder LIVE, off `ladder_targets` itself, for one block.

    The run installs a memoising snapshot on the engine's `_LT` seam (see
    `_MemoTargets`). Gate G1b compares two constructions that read the ladder
    through DIFFERENT paths — the campaign through `_LT`, `financed_spread`
    through its own `cached_calls` glob — so a scrape landing files mid-run could
    let them see different ladders and manufacture a divergence that is about
    timing, not code. Inside this block both glob the same directory at the same
    moment.
    """
    prev = OC._LT
    OC._LT = LT
    try:
        yield
    finally:
        OC._LT = prev


def cost_knobs() -> tuple[float, float]:
    """`(commission_per_contract, slippage_frac_of_spread)` from
    `config/backtest.yml`, the SAME two numbers `simulate._cost_knobs` reads.

    Both ship at 0, so gross == net unless the config has been edited; the run
    states the values it used in the header either way.
    """
    try:
        import yaml
        cfg = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    except Exception:                                   # pragma: no cover
        return 0.0, 0.0
    sim = cfg.get("simulation") or {}
    return (float(sim.get("commission_per_contract") or 0.0),
            float(sim.get("slippage_frac_of_spread") or 0.0))


_bars_cache: dict[str, dict] = {}


def bars_for(ticker: str) -> dict:
    if ticker not in _bars_cache:
        _bars_cache[ticker] = UL.load_bars(ticker)
    return _bars_cache[ticker]


class _MemoTargets:
    """A memoising passthrough over `lib/ladder_targets.py`, installed on the
    engine's own `_LT` seam.

    `cached_strikes` globs the ~44k-file option cache once per
    (ticker, expiry, type), and a rolled campaign asks for the same slot's ladder
    again in every cell. This caches the answer and DELEGATES everything else by
    attribute, so `ladder_targets` stays the one owner of the target set —
    nothing is reimplemented here, only remembered.

    A side effect worth stating: the cache is a SNAPSHOT taken at first ask, so a
    scrape landing files mid-run cannot make two cells disagree about what was on
    disk. That is the behaviour we want; the run's own header names the era and
    the manifest census names the fill state.
    """

    def __init__(self, mod):
        self._mod = mod
        self._strikes: dict[tuple, list[float]] = {}

    def __getattr__(self, name):
        return getattr(self._mod, name)

    def cached_strikes(self, ticker: str, expiry, opt_type: str) -> list[float]:
        key = (ticker, expiry, opt_type)
        if key not in self._strikes:
            self._strikes[key] = self._mod.cached_strikes(ticker, expiry, opt_type)
        return self._strikes[key]


def install_target_memo() -> None:
    """Put the memo in front of `ladder_targets` on the engine's `_LT` seam."""
    if not isinstance(OC._LT, _MemoTargets):
        OC._LT = _MemoTargets(LT)


# ── the scrape manifest — the AWAITING SCRAPE census ─────────────────────────

def manifest_census(path: Path | None = None) -> dict:
    """`{category: Counter}` plus totals, read from the collector's manifest.

    The manifest holds the targets that were NOT already cached when the
    collector derived them, one row per contract, with `status` in
    pending/fetched/failed. It is the only record of what the scrape still owes,
    and it is read here rather than re-derived so the study and the collector
    can never disagree about whether a category is complete.
    """
    path = path or MANIFEST_PATH
    per: dict[str, Counter] = defaultdict(Counter)
    if not path.exists():
        return dict(per={}, exists=False, path=path)
    with path.open() as fh:
        for row in csv.DictReader(fh):
            cat = (row.get("category") or "").strip() or "?"
            status = (row.get("status") or "").strip() or "?"
            per[cat]["targets"] += 1
            per[cat][status] += 1
    return dict(per=dict(per), exists=True, path=path)


def pending_categories(census: dict) -> set[str]:
    """Categories the scrape has not finished. A missing manifest means nothing
    has been derived yet, so EVERY category is pending."""
    if not census.get("exists"):
        return set(CATEGORIES)
    per = census["per"]
    return {cat for cat in CATEGORIES if per.get(cat, Counter())["pending"] > 0}


def awaiting_cells(census: dict) -> set[str]:
    """Labels whose contracts are not all cached yet."""
    pend = pending_categories(census)
    return {c.label for c in CELLS if set(c.cats) & pend}


# ── population ───────────────────────────────────────────────────────────────

def population(recs: list[dict]) -> tuple[list[tuple[dict, LT.CoreSpec]], Counter]:
    """`bull_call_spread` cores via `ladder_targets.core_of`, with the census.

    `core_of` is the ONE owner of "is this row a core": two-leg, single-expiry,
    long the lower Call strike and short the higher one, read off the GEOMETRY
    rather than the `structure` label, with a common entry day
    (`bear_rewrap.entry_date_for`). Everything else is excluded and counted —
    a three-leg row, a multi-expiry row, a bear structure, a row with no common
    entry day.
    """
    keep: list[tuple[dict, LT.CoreSpec]] = []
    why: Counter = Counter()
    for rec in recs:
        why["book_rows"] += 1
        if rec.get("structure") != "bull_call_spread":
            why["excl_not_bull_call_spread"] += 1
            continue
        why["labelled_bull_call"] += 1
        core = LT.core_of(rec)
        if core is None:
            why["excl_not_a_core"] += 1
            continue
        legs = list(rec["t"].legs)
        if len({lg.expiration for lg in legs}) != 1:    # defensive; core_of pins it
            why["excl_multi_expiry"] += 1
            continue
        keep.append((rec, core))
        why["kept"] += 1
    return keep, why


# ── the naked-put arm: a campaign with no core ───────────────────────────────

def fixed_put_tranche(core: LT.CoreSpec, prices, bars: dict, unit: int
                      ) -> tuple[OC.Tranche | None, str]:
    """`N-CORE`'s tranche: a short put at the core's OWN long strike and expiry.

    Not delta-picked and not rollable, so it does not go through
    `overlay_campaign.sell_tranche` (whose whole job is the |Delta| pick inside
    the roll window — a window that by construction EXCLUDES the core's own
    expiry). The lifecycle is the degenerate one: the put's expiry IS the core's,
    and the harness grid stops at `min(core expiry, 120-day path cap)`, so the
    tranche can never settle inside the grid. It is left `open_at_grid_end`,
    exactly as `run_campaign` leaves such a tranche, with `breached` recorded
    the same way — the underlying's CLOSE at or below the strike on any live day,
    read through the engine's own carry-back rule so there is no second copy of
    "what was the close that day".
    """
    leg = Leg(qty=-unit, ticker=core.ticker, expiration=core.expiry,
              strike=core.lo, opt_type=OC.PUT)
    grid = [d for d in core.grid if d >= core.entry_day]
    open_day = next((d for d in grid if prices.has_real_row(leg, d)), None)
    if open_day is None:
        return None, OC.SKIP_NO_CACHED_CANDIDATE
    credit = prices.entry(leg, open_day)
    if credit is None:
        return None, OC.SKIP_NO_ENTRY_PRICE
    tr = OC.Tranche(leg=leg, open_day=open_day, credit=credit,
                    close_reason=OC.OPEN_AT_GRID_END)
    breached = any(OC._breach_hit(tr, OC.PUT, OC._close_asof(bars, d))
                   for d in core.grid if d >= open_day)
    return replace(tr, breached=breached), "ok"


def naked_trade(rec: dict, tranches, denom: float, contracts: int,
                structure: str, prices) -> Trade | None:
    """A frozen-harness `Trade` for a naked-put cell, or None.

    `campaign_trade` always marks the CORE legs, and an N cell has no core: the
    put IS the position. So the value series is `campaign_net_marks` over an
    EMPTY core leg list — the tranche contributions alone — lifted by the R
    denominator, which for these cells is the core's MAX-LOSS DOLLARS
    (`_max_loss_per_unit` on the core leg set) so ΔR stays comparable against the
    same `L-BASE`.

    The LEG STRING still carries the CORE legs, for `campaign_trade`'s reason:
    `Trade` rebuilds the path window from the leg string's nearest expiry, and
    the pairing is only like-for-like if both sides walk the same grid. Nothing
    downstream reads `t.legs` here — no exit profile used by an N cell sets
    `und_buffer`, the only harness rule that touches `t.short_legs`.
    """
    base: Trade = rec["t"]
    if not denom or abs(denom) <= 1e-9:
        return None
    marks = OC.campaign_net_marks([], tranches, base.grid, prices,
                                  credit_received=True)
    if all(m is None for m in marks):
        return None
    lifted = [None if m is None else denom + m for m in marks]
    leg_str = "\n".join(
        f"{lg.ticker}:{lg.expiration.isoformat()}:{lg.strike:g}:"
        f"{'C' if lg.opt_type == OC.CALL else 'P'} {lg.qty:+d}" for lg in base.legs)
    row = {
        "signal_date": base.signal_date.isoformat(),
        "ticker": base.ticker,
        "structure": structure,
        "entry_option_price": f"{denom:.4f}",
        "contracts": str(contracts),
        "dte_entry": str(base.dte_entry),
        "legs": leg_str,
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in lifted),
    }
    try:
        return Trade(row)
    except (AssertionError, ValueError, KeyError):
        return None


# ── breach stress (criterion 8) ──────────────────────────────────────────────

def stress_tranches(tranches, bars: dict, grid) -> list[OC.Tranche]:
    """Re-cost every BREACHED tranche at INTRINSIC instead of its settlement mark.

    Criterion 8 is a RE-COSTING of the recorded campaign, not a different
    campaign: the same tranches, the same days, the same triggers — only the
    price paid to be rid of a breached short changes, from whatever mark
    settled it to the intrinsic value the underlying's close implies. A breached
    tranche still LIVE at the end of the grid is closed on the last grid day at
    intrinsic, because leaving it marked is exactly the forgiveness the clause
    exists to remove. An unbreached tranche is untouched.
    """
    if not grid:
        return list(tranches)
    last = grid[-1]
    out: list[OC.Tranche] = []
    for tr in tranches:
        if not tr.breached:
            out.append(tr)
            continue
        day = tr.close_day or last
        spot = OC._close_asof(bars, min(day, tr.leg.expiration))
        if spot is None:
            out.append(tr)
            continue
        out.append(replace(tr, close_day=day, close_cost=OC._intrinsic(tr.leg, spot),
                           close_reason=tr.close_reason or OC.SETTLE_INTRINSIC))
    return out


# ── exit profiles ────────────────────────────────────────────────────────────

def exit_profile(rec: dict, core_net: float, which: str) -> dict:
    """The registered core-exit axis, as three values off ONE shipped profile.

    X-SHIP  `financed_spread.profile_for` — the shipped §5 debit merge for the
            BASELINE row's regime cell (base -> structure_exit -> regime_exit,
            including the bear-keyed `be_after` where the baseline carries it).
            A ladder core is a debit by construction, so the credit branch is
            unreachable here and its use would be a build bug.
    X-TEF   the SAME profile with the profit target removed and nothing else
            touched — the registration's "no profit target, hold to the §5 time
            exit".
    X-EXP   no profit target, no stop, no trailing, no time exit: `dollar_stop`
            and the 120-day path cap only. SENSITIVITY.
    X-NONE  the naked-put cells, where the registration writes the core exit as
            "n/a — the put is the position". Same shape as X-EXP.
    """
    prof, _sign = FS.profile_for(rec, core_net)
    if which == X_SHIP:
        return dict(prof)
    if which == X_TEF:
        return dict(prof, pt=None)
    return dict(prof, pt=None, sl=None, trig=None, trail=None, tef=None,
                be_after=None)


# ── build ────────────────────────────────────────────────────────────────────

def build(pop: list[tuple[dict, LT.CoreSpec]], cells: tuple[Cell, ...],
          commission: float, slippage: float) -> dict:
    """Everything every gate and cell reads, built in one pass over the cores.

    Returns `baseline` rows, `cells` ({label: [row]}), the G1 reconstruction
    census, the per-cell construction census, the G1b identity records, the
    clamp/sizing/breach tallies and the per-row campaign detail the CSV writes.
    """
    g1: Counter = Counter()
    census: dict[str, Counter] = defaultdict(Counter)
    tranche_census: dict[str, Counter] = defaultdict(Counter)
    baseline: list[dict] = []
    out_cells: dict[str, list[dict]] = defaultdict(list)
    g1b: list[dict] = []

    # Every price in the body is on the stored row's B5 basis (bear_rewrap.basis_of).
    for rec, core in BR.each_on_basis(pop, lambda item: item[0]["t"].row):
        ok, why = BR.reconstructs(rec)
        g1[why] += 1
        if not ok:
            continue

        base_t: Trade = rec["t"]
        entry_day = core.entry_day
        unit = OC.core_unit(rec)
        contracts = base_t.contracts
        bars = bars_for(core.ticker)
        expiries = FS.cached_ticker_expiries(core.ticker)
        core_dte = (core.expiry - entry_day).days

        core_net = BR.net_entry(list(base_t.legs), entry_day)
        if core_net is None or core_net <= 0:
            g1["excl_core_entry_unpriced_or_credit"] += 1
            continue

        base_prof = exit_profile(rec, base_t.entry_net, X_SHIP)
        base_out = FS.replay_at(base_t, base_prof, contracts)
        base_g = GK.entry_greeks(list(base_t.legs), entry_day)
        base_row = dict(
            date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
            source=rec["source"], tier=OC.CACHE_TIER, ladder_tier=rec["tier"],
            mech_cell=rec["mech_cell"], mech_vol=rec["mech_vol"],
            model_vol=rec["model_vol"], mfe=rec["mfe"], mae=rec["mae"],
            key=id(rec), core_dte=core_dte, **base_out)
        baseline.append(base_row)

        # ── G1b: this study's T0/R0/BHOLD campaign vs financed_spread's own
        #    F4 d20 `hold` series, on the SAME row, computed once per core.
        g1b.append(f4_identity_record(rec, core, expiries, bars, unit))

        for cell in cells:
            census[cell.label]["candidates"] += 1
            if cell.min_core_dte is not None and core_dte < cell.min_core_dte:
                census[cell.label]["skip_core_dte_subset"] += 1
                continue

            row = build_cell_row(rec, core, cell, base_row, base_g, expiries,
                                 bars, unit, contracts, core_net,
                                 census[cell.label], tranche_census[cell.label],
                                 commission, slippage)
            if row is not None:
                census[cell.label]["built"] += 1
                out_cells[cell.label].append(row)

    return dict(baseline=baseline, cells=dict(out_cells), g1=g1,
                census=dict(census), tranche_census=dict(tranche_census),
                g1b=g1b, cells_active=cells)


def f4_identity_record(rec: dict, core: LT.CoreSpec, expiries, bars: dict,
                       unit: int) -> dict:
    """One row of gate G1b: `(this engine's marks, financed_spread's F4 marks)`.

    LEFT is `overlay_campaign.f4_identity` — the T0/R0/BHOLD campaign at the
    F4 delta target. RIGHT is `financed_spread`'s OWN construction for the
    F4 d20 `hold` cell, called through its published functions rather than
    reimplemented. Both are MARK series; R is deliberately NOT compared, because
    this study's denominator is the core debit and F4's is the financed net.

    TWO SCOPINGS, both stated rather than buried, and neither of them a softened
    gate:

    * DAYS ON OR AFTER THE COMMON ENTRY DAY. The harness grid starts at the
      SIGNAL date and the fill is the next trading day, so a grid day before the
      fill is one of the `pre_entry` phantom days the robustness review already
      names (B2). `f4_net_marks` marks its short leg on those days — a leg that
      was not yet sold — while a campaign has no tranche until it opens one. The
      identity is a claim about the position's LIFE, which begins at the fill;
      the excluded pre-entry days are counted and printed.
    * ROWS WHERE THE CAMPAIGN OPENED ITS TRANCHE ON THE ENTRY DAY. F4 requires
      the picked contract to have a row ON the entry day and skips it otherwise;
      `sell_tranche` opens on the first grid day the contract PRINTS. Where those
      differ, the campaign has done something F4 never does — which is the
      superset relation itself, not a failure of it. Such rows carry
      `opened_after_entry`, are listed separately and are never averaged in.

    Both sides read the strike ladder through the RAW `ladder_targets` module
    for the duration of this call (`raw_targets`), not through the run's memo
    snapshot: a scrape landing files mid-run could otherwise let the two
    constructions see different ladders and manufacture a divergence that is
    about timing rather than code.
    """
    base_t: Trade = rec["t"]
    entry_day = core.entry_day
    out = dict(date=rec["date"], ticker=rec["ticker"], status="", n_days=0,
               max_diff=None, settle_intrinsic=False, pre_entry_days=0,
               open_day=None)

    with raw_targets():
        marks, tranches, camp_census = OC.f4_identity(
            rec, expiries=expiries, bars=bars, target=G1B_TARGET, detail=True)
        plan = FS.f4_row_plan(rec, "bull", entry_day)
        legs, _why = FS.build_f4(rec, plan, G1B_TARGET, entry_day)
    out["settle_intrinsic"] = bool(camp_census.get(OC.SETTLE_INTRINSIC))

    if legs is None:
        out["status"] = ("no_f4_leg" if not tranches
                         else "campaign_sold_f4_excluded")
        return out
    if not tranches:
        out["status"] = "no_campaign_tranche"
        return out

    short_leg = legs[-1]
    if tranches[0].open_day != entry_day:
        # The campaign opened on the first day the contract PRINTED; F4 requires
        # the entry-day row and skips the candidate otherwise. That is the
        # superset relation, not a break in it.
        out["status"] = "opened_after_entry"
        out["open_day"] = tranches[0].open_day
        return out
    if (short_leg.expiration, short_leg.strike) != \
            (tranches[0].leg.expiration, tranches[0].leg.strike):
        out["status"] = "different_contract"
        return out

    credit = FS.f4_entry_credit(short_leg, entry_day)
    net = BR.net_entry(legs, entry_day)
    if credit is None or credit <= 0 or net is None:
        out["status"] = "f4_credit_unpriced"
        return out
    n_prod, _ = FS.size_contracts(net, legs)
    buyback = FS.f4_buyback(short_leg, list(base_t.grid), entry_day, credit,
                            n_prod, "hold")
    theirs = FS.f4_net_marks(list(base_t.legs), short_leg, list(base_t.grid),
                             buyback)

    live = [(d, a, b) for d, a, b in zip(base_t.grid, marks, theirs)
            if d >= entry_day]
    out["pre_entry_days"] = len(base_t.grid) - len(live)
    diffs = [abs(a - b) for _d, a, b in live if a is not None and b is not None]
    shape = sum(1 for _d, a, b in live if (a is None) != (b is None))
    out["n_days"] = len(diffs)
    out["max_diff"] = max(diffs) if diffs else None
    if not diffs:
        out["status"] = "no_shared_day"
    elif shape:
        out["status"] = "unpriced_day_mismatch"
    elif out["max_diff"] <= G1B_TOL:
        out["status"] = "match"
    elif out["settle_intrinsic"]:
        out["status"] = "settle_intrinsic"
    else:
        out["status"] = "mismatch"
    return out


def build_cell_row(rec, core, cell: Cell, base_row: dict, base_g: dict,
                   expiries, bars, unit: int, contracts: int, core_net: float,
                   census: Counter, tcensus: Counter,
                   commission: float, slippage: float) -> dict | None:
    """One (core, cell) result row, or None with the exclusion counted."""
    base_t: Trade = rec["t"]
    entry_day = core.entry_day
    core_legs = list(base_t.legs)

    if cell.is_model:
        prices = OC.ModelPrices(cell.sigma_scale, bars)
        prices.register_all(core_legs, entry_day)
    else:
        prices = OC.CachePrices()

    # ── the campaign
    tranches: list[OC.Tranche] = []
    if cell.spec is not None:
        if cell.fixed_put:
            tr, why = fixed_put_tranche(core, prices, bars, unit)
            tcensus[why] += 1
            if tr is None:
                census[f"skip_{why}"] += 1
                return None
            tranches = [tr]
        else:
            with gap_threshold(cell.gap):
                tranches, camp = OC.run_campaign(core, cell.spec, prices, bars,
                                                 list(expiries), unit=unit)
            for k, v in camp.items():
                tcensus[k] += v
            if not tranches:
                census["skip_no_tranche"] += 1
                return None
        if cell.is_model:
            # The engine leaves registration to the study (its docstring says so):
            # each tranche prices off ITS OWN entry-day IV, held constant.
            for tr in tranches:
                prices.register(tr.leg, tr.open_day)

    # ── the synthetic and its replay
    if cell.spec is None:
        # L-BASE is not a synthetic: it IS the book row, replayed at the same
        # contract count under the same shipped profile. Rebuilding it from
        # re-priced marks would leave the baseline every ΔR is paired against
        # differing from itself by the reconstruction tolerance.
        denom, t = base_t.entry_net, base_t
    elif cell.replaces_core:
        denom = _max_loss_per_unit(core_legs, core_net)
        if denom is None or denom <= 0:
            census["skip_no_max_loss"] += 1
            return None
        t = naked_trade(rec, tranches, denom, contracts, cell.label, prices)
    else:
        denom = core_net
        t = OC.campaign_trade(rec, tranches, core_net, contracts, cell.label,
                              prices)
    if t is None:
        census["skip_unpriceable_path"] += 1
        return None

    prof = exit_profile(rec, core_net, cell.exit)
    out = FS.replay_at(t, prof, contracts)

    # ── criterion 8's re-costing, on the SAME campaign
    r_stress = None
    if tranches:
        stressed = stress_tranches(tranches, bars, list(base_t.grid))
        if cell.replaces_core:
            t_s = naked_trade(rec, stressed, denom, contracts, cell.label, prices)
        else:
            t_s = OC.campaign_trade(rec, stressed, core_net, contracts,
                                    cell.label, prices)
        if t_s is not None:
            r_stress = FS.replay_at(t_s, prof, contracts)["R"]
    else:
        r_stress = out["R"]

    # ── exposure at the common entry day (E1/E2) and at the first sale
    live_at_entry = [tr for tr in tranches if tr.open_day <= entry_day
                     and (tr.close_day is None or entry_day < tr.close_day)]
    cell_legs = (([] if cell.replaces_core else list(core_legs))
                 + [tr.leg for tr in live_at_entry])
    g_entry = GK.entry_greeks(cell_legs, entry_day) if cell_legs else {}
    first = tranches[0] if tranches else None
    g_sale = {}
    base_g_sale = {}
    if first is not None:
        g_sale = GK.entry_greeks(
            ([] if cell.replaces_core else list(core_legs)) + [first.leg],
            first.open_day)
        base_g_sale = GK.entry_greeks(core_legs, first.open_day)

    # ── clamp attribution (G2)
    live_days = sum(1 for d in base_t.grid
                    if any(tr.live_on(d) for tr in tranches))
    full_legs = list(core_legs) + [tr.leg for tr in tranches]
    clamp_full = None if cell.replaces_core else _defined_risk_bounds(full_legs)
    clamp_core = _defined_risk_bounds(core_legs)

    # ── sizing (G3) and the reg-T margin proxy (naked cells only)
    size_legs = [tr.leg for tr in tranches] if cell.replaces_core else full_legs
    size_net = (-sum(tr.credit * abs(tr.leg.qty) for tr in tranches)
                if cell.replaces_core else core_net)
    n_would, unbounded = (FS.size_contracts(size_net, size_legs)
                          if size_legs else (contracts, False))
    margin = None
    if cell.replaces_core and first is not None:
        spot = OC._close_asof(bars, first.open_day)
        if spot is not None:
            k = first.leg.strike
            margin = (max(0.20 * spot - max(0.0, spot - k), 0.10 * k)
                      + first.credit) * 100

    # ── the campaign's transaction costs
    costs = OC.costs_of(tranches, contracts, commission, slippage, prices)
    sens = OC.costs_of(tranches, contracts, SENS_COMMISSION, SENS_SLIPPAGE, prices)

    pnls = [t.pnl_of(m) for m in t.marks if m is not None]
    breached = [tr for tr in tranches if tr.breached]
    breach_r = [abs(tr.leg.qty) * ((tr.close_cost or 0.0) - tr.credit) / abs(denom)
                for tr in breached if tr.close_cost is not None]

    return dict(
        date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
        source=rec["source"], tier=cell.tier, ladder_tier=rec["tier"],
        mech_cell=rec["mech_cell"], mech_vol=rec["mech_vol"],
        model_vol=rec["model_vol"], key=id(rec), cell=cell.label,
        group=cell.group, core_dte=base_row["core_dte"],
        entry_net=denom, core_net=core_net,
        n_tranches=len(tranches), n_breached=len(breached),
        n_live_days=live_days, n_grid_days=len(base_t.grid),
        clamped_full=clamp_full is not None, clamped_core=clamp_core is not None,
        settle_mark=sum(1 for tr in tranches
                        if tr.close_reason == OC.SETTLE_MARK),
        settle_intrinsic=sum(1 for tr in tranches
                             if tr.close_reason == OC.SETTLE_INTRINSIC),
        open_at_grid_end=sum(1 for tr in tranches
                             if tr.close_reason == OC.OPEN_AT_GRID_END),
        breach_r_mean=(_mean(breach_r) if breach_r else None),
        breach_r_worst=(max(breach_r) if breach_r else None),
        credit_total=sum(abs(tr.leg.qty) * tr.credit for tr in tranches),
        first_strike=(first.leg.strike if first else None),
        first_expiry=(first.leg.expiration if first else None),
        first_open=(first.open_day if first else None),
        R_stress=r_stress,
        cost_gross_dol=out["R_dol"], cost_total=costs.total,
        cost_basis=costs.basis, cost_net_dol=costs.net(out["R_dol"]),
        sens_cost_total=sens.total, sens_net_dol=sens.net(out["R_dol"]),
        n_would_size=n_would, unbounded_size=unbounded, margin_proxy=margin,
        mfe=max(pnls) if pnls else None, mae=min(pnls) if pnls else None,
        base_R=base_row["R"], base_R_dol=base_row["R_dol"],
        base_contracts=contracts, base_net=base_t.entry_net,
        fixed_R=out["R"], fixed_R_dol=out["R_dol"],
        d_delta=_delta(g_entry, base_g, "delta"),
        d_vega=_delta(g_entry, base_g, "vega"),
        d_delta_sale=_delta(g_sale, base_g_sale, "delta"),
        base_delta=base_g.get("delta"), base_vega=base_g.get("vega"),
        **out)


def _num(v: float, width: int, spec: str = "+.3f") -> str:
    """A float column that prints an em dash rather than `+nan` for "no rows"."""
    return ("—" if v != v else format(v, spec)).rjust(width)


def _delta(a: dict, b: dict, key: str):
    if not a or not b or a.get(key) is None or b.get(key) is None:
        return None
    return a[key] - b[key]


# ── report: header ───────────────────────────────────────────────────────────

def report_header(recs: list[dict], diag: dict, pop: list, why: Counter,
                  commission: float, slippage: float) -> None:
    hdr("ladder_overlay — does a rolled short-call ladder beat selling the spread?")
    print(f"  era {diag['era']}   book {len(recs)} rows / {diag['n_dates']} dates   "
          f"{diag['date_range'][0]} .. {diag['date_range'][1]}")
    print("  by source: " + "  ".join(
        f"{k}={v}" for k, v in sorted(Counter(r["source"] for r in recs).items())))
    print("  registration  research/pre-registrations/f3_structure/"
          "ladder_overlay.md")
    print("  engine        lib/overlay_campaign.py   targets  lib/ladder_targets.py"
          "   harness FROZEN")
    if diag.get("mech_table_warning"):
        print(f"  WARNING: {diag['mech_table_warning']}")

    sub("population — bull_call_spread CORES (ladder_targets.core_of)")
    print(f"  kept {why['kept']} cores of {why['labelled_bull_call']} "
          f"bull_call_spread rows, out of {why['book_rows']} book rows")
    for k, v in sorted(why.items()):
        if k.startswith("excl_"):
            print(f"    excluded: {k[5:]:<30} {v:>5}")
    if len(pop) != why["kept"]:
        print(f"  *** BUILD-ONLY --limit-rows: only the first {len(pop)} of those "
              "are built. NOT the study.")
    print("""
  A core is read off the LEG GEOMETRY, not off the `structure` label: two legs,
  ONE expiry, long the lower Call strike and short the higher one, with a common
  entry day. A three-leg row, a multi-expiry row and a bear structure are not
  cores here — they are excluded and counted above.""")

    sub("pricing, sizing, exits — pinned by the registration")
    print(f"""  DENOMINATOR   ladder cells: the CORE debit (`entry_net` = the spread's own
                net). Tranche credits are never folded into it. Naked-put cells:
                the core's MAX-LOSS DOLLARS (`_max_loss_per_unit`), so ΔR is
                against the same baseline.
  CONTRACTS     every cell runs at the BASELINE CORE's production count, overlay
                ratio 1:1. No cell can win on size.
  SETTLEMENT    a tranche open at its own expiry settles at its LAST REAL MARK; a
                BREACHED tranche with no mark within {OC.SETTLE_STALE_SESSIONS} sessions of expiry settles
                at INTRINSIC and is counted (`settle_intrinsic`).
  CLAMP         `_defined_risk_bounds` on the CORE ONLY, and only on days with no
                live tranche. A short call beyond the core's hi strike is
                uncovered above its own strike.
  COSTS         config/backtest.yml: commission_per_contract = {commission:g},
                slippage_frac_of_spread = {slippage:g}. Charged on EVERY tranche
                open and close. """
          + ("Both are 0, so gross == net below."
             if not commission and not slippage else
             "GROSS and NET both print below.")
          + f"""
                One labelled SENSITIVITY line re-costs every cell at
                ${SENS_COMMISSION:.2f}/contract and {SENS_SLIPPAGE:g} of the quoted spread. That line
                is a sensitivity and is never a criterion.
  TRIGGERS      T-GAP open >= {1 + OC.TGAP_MIN_GAP:.3f} x prior close; T-RUN close >= {1 + OC.TRUN_MIN_RUN:.2f} x entry
                close AND {OC.TRUN_RISING_CLOSES} consecutive higher closes. Both fire at most once per
                empty slot and sell on the NEXT grid day. T0 sells ON the entry day.
  STRIKES       the {OC.N_CANDIDATES} nearest CACHED strikes beyond the position at the chosen
                expiry, picked by scraped entry-day |Delta| closest to target;
                off-target by more than {OC.DELTA_TOL:.2f} excludes the row. The zero-filled
                greek sentinel is detected on IV, never on Delta.""")

    sub("core exits — a two-value axis plus one sensitivity, frozen before any outcome")
    for k in (X_SHIP, X_TEF, X_EXP, X_NONE):
        print(f"  {k:<8} {EXIT_DESC[k]}")


def report_cell_table(cells: tuple[Cell, ...]) -> None:
    hdr("CELLS — the registered table, built exactly once each")
    print(f"  {'cell':<15} {'group':<12} {'trigger':<8} {'roll':<5} {'breach':<7} "
          f"{'|Δ|':>5} {'type':<5} {'exit':<8} description")
    for c in cells:
        s = c.spec
        trig = s.trigger if s else "—"
        if c.gap is not None:
            trig += "*"
        print(f"  {c.label:<15} {c.group:<12} {trig:<8} "
              f"{(s.roll if s else '—'):<5} {(s.breach if s else '—'):<7} "
              f"{(f'{s.target:.2f}' if s else '—'):>5} "
              f"{(s.opt_type if s else '—'):<5} {c.exit:<8} {c.desc}")
    print(f"\n  * S-GAP103 runs T-GAP at {1 + SENS_GAP:.2f} instead of the primary "
          f"{1 + OC.TGAP_MIN_GAP:.3f}; it is a\n    SENSITIVITY and cannot become the "
          "headline.\n  N-CORE's strike is the core's own LONG strike at the core's "
          "own expiry — not\n  delta-picked, which is why its |Δ| column is the "
          "spec's default and is unread.")


# ── report: the scrape census ────────────────────────────────────────────────

def report_scrape(census: dict, awaiting: set[str]) -> None:
    hdr("SCRAPE COVERAGE — what the ladder manifest still owes")
    print(f"""  `scripts/collector/fetch_ladder_legs.py` derives every contract a campaign
  owes a core through `lib/ladder_targets.py` — the SAME module this study reads
  — and records the ones not already cached in
  `backtests/sweep_cache/ladder_manifest.csv`. Already-cached targets never enter
  the manifest, so `targets` below is what the SCRAPE owes, not the whole target
  set.

  While a category still has PENDING rows, every cell that needs it carries the
  verdict {AWAITING}: no mean, no CI, no criterion, and NOT a null.""")
    if not census.get("exists"):
        print(f"\n  manifest ABSENT ({census['path']}) — nothing derived yet; every "
              "category is pending.")
        return
    per = census["per"]
    print(f"\n  {'category':<20} {'targets':>9} {'fetched':>9} {'pending':>9} "
          f"{'failed':>8} {'other':>7}")
    tot: Counter = Counter()
    for cat in CATEGORIES:
        c = per.get(cat, Counter())
        other = c["targets"] - c["fetched"] - c["pending"] - c["failed"]
        tot.update(c)
        print(f"  {cat:<20} {c['targets']:>9,} {c['fetched']:>9,} "
              f"{c['pending']:>9,} {c['failed']:>8,} {other:>7,}")
    unknown = {k: v for k, v in per.items() if k not in CATEGORIES}
    for cat, c in sorted(unknown.items()):
        print(f"  {cat + ' (unregistered)':<20} {c['targets']:>9,} "
              f"{c['fetched']:>9,} {c['pending']:>9,} {c['failed']:>8,}")
    other = tot["targets"] - tot["fetched"] - tot["pending"] - tot["failed"]
    print(f"  {'ALL':<20} {tot['targets']:>9,} {tot['fetched']:>9,} "
          f"{tot['pending']:>9,} {tot['failed']:>8,} {other:>7,}")

    if awaiting:
        print(f"\n  cells {AWAITING}: " + "  ".join(sorted(awaiting)))
        print("""
  Every one of those cells is still BUILT below on the cached subset, and every
  gate still runs on it. That is deliberate: the machinery is proved before the
  scrape ends, not after. What is refused is the CONCLUSION, not the run. To
  fetch (resumable, research tier, run by hand — this module never scrapes):

      python3 scripts/collector/fetch_ladder_legs.py --dry-run
      python3 scripts/collector/fetch_ladder_legs.py --limit 200""")
    else:
        print("\n  no category has pending rows — every cell's contracts are cached.")


# ── G0 — POWER, runs and prints FIRST ────────────────────────────────────────

def gate_g0(built: dict, awaiting: set[str]) -> dict[str, bool]:
    hdr("G0 — POWER. Runs and prints FIRST; an underpowered cell is never read.")
    print(f"""  Pre-registered floor, declared before any cell was built: a cell with
  < {MIN_DATES} dates OR < {MIN_ROWS} rows is {UNDERPOWERED} — its n is printed and NO
  criterion is evaluated on it. The floor is re-applied inside every regime cut.
  No cell may be rescued by lowering it.

  {AWAITING} is NOT {UNDERPOWERED}: an underpowered cell has rows and too
  few dates, an awaiting cell's contracts are not in the cache yet.""")
    print(f"\n  {'cell':<15} {'group':<12} {'built':>7} {'dates':>7}  "
          f"{'status':<16} description")
    out: dict[str, bool] = {}
    for cell in built["cells_active"]:
        rows = built["cells"].get(cell.label) or []
        ok = powered(rows)
        out[cell.label] = ok
        status = AWAITING if cell.label in awaiting else \
            ("POWERED" if ok else UNDERPOWERED)
        print(f"  {cell.label:<15} {cell.group:<12} {len(rows):>7} "
              f"{n_dates(rows):>7}  {status:<16} {cell.desc}")

    sub("constructibility census — why a core did not become a cell row")
    for cell in built["cells_active"]:
        c = built["census"].get(cell.label, Counter())
        parts = [f"{k[5:]}={v}" for k, v in sorted(c.items()) if k.startswith("skip_")]
        print(f"  {cell.label:<15} candidates {c['candidates']:>4}  "
              f"built {c['built']:>4}   " + "  ".join(parts))

    sub("tranche census — what the campaign engine did, per cell")
    for cell in built["cells_active"]:
        c = built["tranche_census"].get(cell.label, Counter())
        if not c:
            continue
        parts = [f"{k}={v}" for k, v in sorted(c.items())]
        print(f"  {cell.label:<15} " + "  ".join(parts))
    return out


# ── G1 — reconstruction ──────────────────────────────────────────────────────

def gate_g1(pop_n: int, g1: Counter) -> bool:
    hdr("G1 — RECONSTRUCTION. Can this code rebuild the cores it is about to wrap?")
    print("""  Every number below is a DIFFERENCE against a baseline replay. If the
  baseline cannot be rebuilt from the same cache by the same pricing code, that
  difference is measuring the re-pricer, not the wrapper. Tolerances are the
  pre-registered ones: entry +/-$0.005, per-day mark +/-$0.01, >= 95% of priced
  days agreeing. Failures are excluded from EVERY cell and counted by reason.""")
    ok = g1["ok"]
    print(f"\n  candidate cores            {pop_n:>5}")
    if pop_n:
        print(f"  reconstructed              {ok:>5}  ({ok / pop_n:.1%})")
    for reason, n in sorted(g1.items()):
        if reason != "ok":
            print(f"    failed: {reason:<32} {n:>5}")
    passed = ok > 0
    print(f"\n  G1 {'PASS' if passed else 'FAIL'}"
          + ("" if passed else "  — nothing reconstructs; no cell is interpretable"))
    return passed


# ── G1b — the F4 identity ────────────────────────────────────────────────────

def gate_g1b(built: dict) -> bool:
    hdr("G1b — F4 IDENTITY. Is this rolling engine a SUPERSET of the single tranche?")
    print(f"""  `L-F4` is the T0 / R0 / BHOLD campaign at |Δ| {G1B_TARGET:.2f}. Its per-day MARK
  series must equal `financed_spread` ARM F4 d{int(G1B_TARGET * 100)} `hold`'s series to
  ${G1B_TOL:.2f} PER DAY on the shared rows. That is what makes the rolling engine a
  demonstrated superset of the single-tranche one rather than a second,
  differently-wrong implementation. A mismatch FAILS THE RUN — it is never
  reported as a difference of method.

  R is deliberately NOT compared: this study's denominator is the core debit and
  F4's is the financed net.

  THREE constructions under which the two may legitimately disagree. All three
  are LISTED SEPARATELY and never averaged in, and none of them is a pass:

    settle_intrinsic     a tranche BREACHED with no real mark within {OC.SETTLE_STALE_SESSIONS} sessions of
                         its expiry settles at INTRINSIC here and at the stale
                         mark in F4, which has no breach concept.
    opened_after_entry   F4 requires the picked contract to have a row ON the
                         entry day and skips it otherwise; a campaign opens on
                         the first grid day the contract PRINTS. Where those
                         differ the campaign has done something F4 never does —
                         which IS the superset relation.
    campaign_sold_f4_excluded
                         F4 excluded the row outright and the campaign sold a
                         tranche. Same relation, one step further out.

  The comparison itself runs on grid days ON OR AFTER the common entry day: the
  grid starts at the SIGNAL date, and `f4_net_marks` marks its short leg on the
  pre-fill days (the robustness review's `pre_entry` phantom days, B2) where a
  campaign has no tranche at all. The excluded day count prints below.""")
    recs = built["g1b"]
    by = Counter(r["status"] for r in recs)
    matched = [r for r in recs if r["status"] == "match"]
    intr = [r for r in recs if r["status"] == "settle_intrinsic"]
    late = [r for r in recs if r["status"] == "opened_after_entry"]
    bad = [r for r in recs if r["status"] in ("mismatch", "unpriced_day_mismatch",
                                              "different_contract")]
    print(f"\n  cores reaching G1b         {len(recs):>5}")
    for k, v in sorted(by.items()):
        print(f"    {k:<28} {v:>5}")
    if matched:
        worst = max(matched, key=lambda r: r["max_diff"])
        print(f"\n  matched rows               {len(matched):>5}   "
              f"worst per-day diff ${worst['max_diff']:.4f} "
              f"({worst['ticker']} {worst['date']})   "
              f"tolerance ${G1B_TOL:.2f}")
        print(f"  shared marked days         "
              f"{sum(r['n_days'] for r in matched):>5}")
        print(f"  pre-entry days excluded    "
              f"{sum(r.get('pre_entry_days', 0) for r in matched):>5}   (the fill is the "
              "next trading day;\n                                   `f4_net_marks` "
              "marks a leg it has not sold there)")
    if late:
        sub("rows where the CAMPAIGN opened later than F4 could — the superset, listed")
        for r in sorted(late, key=lambda r: str(r["date"]))[:20]:
            print(f"  {r['ticker']:<8} {r['date']}  tranche opened {r['open_day']} "
                  "— F4 requires the entry-day row and skips the candidate")
        if len(late) > 20:
            print(f"  ... and {len(late) - 20} more")
    if intr:
        sub("rows diverging ONLY by a settle_intrinsic settlement — listed, never averaged")
        for r in sorted(intr, key=lambda r: -(r["max_diff"] or 0))[:20]:
            print(f"  {r['ticker']:<8} {r['date']}  max diff "
                  f"${r['max_diff']:.4f} over {r['n_days']} days")
        if len(intr) > 20:
            print(f"  ... and {len(intr) - 20} more")
    if bad:
        sub("DIVERGENCES THAT ARE NOT settle_intrinsic — these fail the run")
        for r in bad[:20]:
            d = "n/a" if r["max_diff"] is None else f"${r['max_diff']:.4f}"
            print(f"  {r['ticker']:<8} {r['date']}  {r['status']:<24} max diff {d}")
        if len(bad) > 20:
            print(f"  ... and {len(bad) - 20} more")
    ok = not bad
    print(f"\n  G1b {'PASS' if ok else 'FAIL'}"
          + ("" if ok else "  — the rolling engine is NOT a superset of F4; "
                           "nothing above is readable"))
    if not recs or not (matched or intr or late or bad):
        print("  (no core reached a comparable F4 construction on the cached "
              "subset — the\n   identity is UNPROVEN, not disproven; it is "
              "re-checked every run.)")
    return ok


# ── G2 — clamp attribution ───────────────────────────────────────────────────

def gate_g2(built: dict) -> bool:
    hdr("G2 — CLAMP ATTRIBUTION. Does each cell's leg set have the risk it claims?")
    print("""  `_defined_risk_bounds` bounds a SINGLE-EXPIRATION payoff. While a tranche is
  live the position has two expirations and a naked short beyond the core, so
  there IS no such bound and none is applied — the registration's clause is
  "100% UNCLAMPED on days with a live tranche", not a missing clamp. On a day
  with no live tranche the position is a plain single-expiry core again and the
  clamp applies to the CORE VALUE ONLY, with realized cash outside it.

  A ladder cell whose FULL leg set clamps means the tranche shares the core's
  expiry — the leg set is wrong — and FAILS THE RUN. The naked-put cells have no
  core to clamp and are reported, not gated.""")
    ok = True
    print(f"\n  {'cell':<15} {'rows':>6} {'live-day rows':>14} {'full-set clamped':>17} "
          f"{'core clamped':>13}  {'live/grid days':>15}  verdict")
    for cell in built["cells_active"]:
        rows = built["cells"].get(cell.label) or []
        if not rows:
            print(f"  {cell.label:<15} {0:>6}   no rows")
            continue
        with_tr = [r for r in rows if r["n_tranches"]]
        clamped_full = sum(1 for r in with_tr if r["clamped_full"])
        clamped_core = sum(1 for r in rows if r["clamped_core"])
        live = sum(r["n_live_days"] for r in rows)
        grid = sum(r["n_grid_days"] for r in rows)
        if cell.replaces_core or cell.spec is None:
            verdict = "not gated"
        else:
            good = clamped_full == 0
            ok = ok and good
            verdict = "PASS" if good else "FAIL"
        print(f"  {cell.label:<15} {len(rows):>6} {len(with_tr):>14} "
              f"{clamped_full:>17} {clamped_core:>13}  "
              f"{live:>7}/{grid:<7}  {verdict}")
    print(f"\n  G2 {'PASS' if ok else 'FAIL'}")
    return ok


# ── G3 — sizing and the reg-T margin census ──────────────────────────────────

def gate_g3(built: dict) -> None:
    hdr("G3 — SIZING AND MARGIN CENSUS. The only place here that quotes dollars.")
    print("""  Contracts are PINNED to the baseline core's production count in every cell,
  so no cell can win on size and the distribution below is the baseline's by
  construction. What is worth counting is what production sizing WOULD have done
  with each cell's own leg set: `n=1 unbounded` is the 1-contract fallback a
  naked short takes when `_max_loss_per_unit` cannot bound it. It is a CENSUS
  LINE, exactly as the registration words it, and never a cell.""")
    base = built["baseline"]
    print(f"\n  {'cell':<15} {'n':>5} {'contracts: mean':>16} {'med':>5} {'min':>5} "
          f"{'max':>5} {'would=1':>8} {'unbnd':>6}")
    if base:
        bc = [r["contracts"] for r in base]
        print(f"  {'BASELINE':<15} {len(base):>5} {statistics.fmean(bc):>16.2f} "
              f"{statistics.median(bc):>5.0f} {min(bc):>5} {max(bc):>5} "
              f"{sum(1 for c in bc if c == 1):>8} {'—':>6}")
    for cell in built["cells_active"]:
        rows = built["cells"].get(cell.label) or []
        if not rows:
            continue
        cs = [r["contracts"] for r in rows]
        print(f"  {cell.label:<15} {len(rows):>5} {statistics.fmean(cs):>16.2f} "
              f"{statistics.median(cs):>5.0f} {min(cs):>5} {max(cs):>5} "
              f"{sum(1 for r in rows if r['n_would_size'] == 1):>8} "
              f"{sum(1 for r in rows if r['unbounded_size']):>6}")

    sub("reg-T MARGIN PROXY — naked-put cells only, per contract at entry")
    print("""  margin ~= [ max(0.20 x S - max(0, S - K), 0.10 x K) + credit ] x 100

  CAVEAT, REGISTERED: this is a PROXY. Real margin is broker-set, is often
  higher, and EXPANDS while the position is losing — exactly when the account can
  least fund it. No criterion reads this number. It exists so a positive
  naked-put ΔR cannot be read as free.

  This study CANNOT say whether the operator's account could have carried
  N-CORE or N-ROLL at the registered contract count, and it does not try.""")
    print(f"\n  {'cell':<15} {'n':>5} {'margin/contract: mean':>22} {'med':>9} "
          f"{'max':>9}  {'at baseline contracts: mean $':>30}")
    for cell in built["cells_active"]:
        if not cell.replaces_core:
            continue
        rows = [r for r in (built["cells"].get(cell.label) or [])
                if r["margin_proxy"] is not None]
        if not rows:
            print(f"  {cell.label:<15} {0:>5}   no priced rows")
            continue
        m = [r["margin_proxy"] for r in rows]
        tot = [r["margin_proxy"] * r["contracts"] for r in rows]
        print(f"  {cell.label:<15} {len(rows):>5} {statistics.fmean(m):>22,.0f} "
              f"{statistics.median(m):>9,.0f} {max(m):>9,.0f}  "
              f"{statistics.fmean(tot):>30,.0f}")


# ── G4 — the breach census ───────────────────────────────────────────────────

def gate_g4(built: dict) -> None:
    hdr("G4 — BREACH CENSUS. What the short strike being reached actually cost.")
    print(f"""  A BREACH is a STATE, not an exit: the underlying's CLOSE reaches the live
  tranche's short strike (`close >= K` for a call, `close <= K` for a put) on the
  core ticker's own OHLC bars, on any day the tranche is live. Under the PRIMARY
  policy (BHOLD) nothing is done about it — this census is how its cost is read,
  and criterion 8 is read against this census.

  `settle_intrinsic` is the one place settlement is not the last real mark: a
  BREACHED tranche with no mark within {OC.SETTLE_STALE_SESSIONS} sessions of its expiry pays intrinsic
  instead, because a breached short that stops printing is exactly the row whose
  stale mark would forgive assignment.

  `dollar_stop` share matters because that harness stop is an ABSOLUTE cap and it
  truncates exactly the tail this study is measuring.""")
    print(f"\n  {'cell':<15} {'rows':>6} {'tranches':>9} {'breached':>9} "
          f"{'share':>7} {'settle_mk':>10} {'settle_in':>10} {'open_end':>9} "
          f"{'breach R: mean':>15} {'worst':>8} {'$stop':>7}")
    for cell in built["cells_active"]:
        rows = built["cells"].get(cell.label) or []
        if not rows:
            continue
        n_tr = sum(r["n_tranches"] for r in rows)
        n_br = sum(r["n_breached"] for r in rows)
        share = (n_br / n_tr) if n_tr else float("nan")
        means = [r["breach_r_mean"] for r in rows if r["breach_r_mean"] is not None]
        worst = [r["breach_r_worst"] for r in rows if r["breach_r_worst"] is not None]
        stop = sum(1 for r in rows if r["exit_reason"] == "dollar_stop") / len(rows)
        print(f"  {cell.label:<15} {len(rows):>6} {n_tr:>9} {n_br:>9} "
              f"{share:>7.1%} {sum(r['settle_mark'] for r in rows):>10} "
              f"{sum(r['settle_intrinsic'] for r in rows):>10} "
              f"{sum(r['open_at_grid_end'] for r in rows):>9} "
              f"{(_mean(means) if means else float('nan')):>15.3f} "
              f"{(max(worst) if worst else float('nan')):>8.3f} "
              f"{stop:>7.1%}")
    print("\n  `breach R` = the breached tranche's realized cost less its credit, in "
          "R units of\n  the cell's own denominator. Positive = the breach cost "
          "money.")


# ── costs ────────────────────────────────────────────────────────────────────

def report_costs(built: dict, commission: float, slippage: float) -> None:
    hdr("TRANSACTION COSTS — gross and net, plus one labelled sensitivity")
    print(f"""  `config/backtest.yml` carries commission_per_contract = {commission:g} and
  slippage_frac_of_spread = {slippage:g} at run time; both are charged identically in
  every cell, on EVERY tranche open and every tranche close, in addition to the
  core's own entry and exit. """
          + ("Both are 0, so gross == net and the columns agree by construction."
             if not commission and not slippage else
             "A criterion is read on the NET series.")
          + f"""

  The SENSITIVITY columns re-cost the same campaigns at ${SENS_COMMISSION:.2f} per contract per
  side and {SENS_SLIPPAGE:g} of the quoted spread. SENSITIVITY ONLY: it is printed with n,
  it changes no verdict, and it is not a criterion.""")
    print(f"\n  {'cell':<15} {'rows':>6} {'opens+closes':>13} {'gross $':>12} "
          f"{'cost $':>10} {'net $':>12}  {'SENS cost $':>12} {'SENS net $':>12}  "
          "basis")
    for cell in built["cells_active"]:
        rows = built["cells"].get(cell.label) or []
        if not rows:
            continue
        basis = Counter(r["cost_basis"] for r in rows if r["cost_basis"])
        print(f"  {cell.label:<15} {len(rows):>6} "
              f"{sum(r['n_tranches'] for r in rows) * 2:>13} "
              f"{sum(r['cost_gross_dol'] for r in rows):>12,.0f} "
              f"{sum(r['cost_total'] for r in rows):>10,.0f} "
              f"{sum(r['cost_net_dol'] for r in rows):>12,.0f}  "
              f"{sum(r['sens_cost_total'] for r in rows):>12,.0f} "
              f"{sum(r['sens_net_dol'] for r in rows):>12,.0f}  "
              + ("  ".join(f"{k}={v}" for k, v in basis.most_common(2)) or "—"))


# ── the cells ────────────────────────────────────────────────────────────────

def report_cells(built: dict, power: dict, awaiting: set[str]) -> None:
    hdr("PAIRED ΔR — cell minus L-BASE, R only, never dollars on a substitution")
    print("""  Unit is the signal DATE: every CI resamples dates, not rows. The pair is
  within-row on rows BOTH the cell and the baseline price. `gb` = |mean MAE| /
  mean MFE, `cap` = mean R / mean MFE, both recomputed off the synthetic's OWN
  path — a wrapper walks a different path, so the baseline's stored MFE/MAE do
  not describe it.

  Contract counts and structures differ across cells by construction, so `$`
  appears only inside the sizing, margin and cost censuses. Every cell quotes R.""")
    print()
    base = built["baseline"]
    if base:
        print(fmt_row("book baseline (core)", cell_stats(base), width=20))

    for cell in built["cells_active"]:
        rows = built["cells"].get(cell.label) or []
        tag = "  [MODEL]" if cell.is_model else ""
        if cell.label in awaiting:
            sub(f"{cell.label} — {AWAITING}{tag}")
            print(f"  {len(rows)} rows built on the CACHED SUBSET only. The "
                  "contracts this cell needs\n  are still pending in the "
                  "manifest, so no mean, no CI and no criterion are\n  read off "
                  "it — and it is NOT a null.")
            if not rows:
                continue
        elif not rows:
            sub(f"{cell.label} — no rows built{tag}")
            continue
        elif not power[cell.label]:
            sub(f"{cell.label} — {UNDERPOWERED}{tag}")
            print(f"  n={len(rows)} rows / {n_dates(rows)} dates "
                  f"(floor {MIN_ROWS} rows / {MIN_DATES} dates). "
                  "No mean, no CI, no criterion.")
            continue
        else:
            sub(f"{cell.label} — {cell.desc}{tag}")
        if cell.is_model:
            print("  [MODEL] SENSITIVITY TIER — never pooled with cache-priced "
                  "rows, never a criterion.")
        print(fmt_row(cell.label, cell_stats(rows), width=20))
        pr = FS.paired_rows(rows)
        if not pr:
            print("  no paired rows")
            continue
        d_mean = _mean([p["a"] - p["b"] for p in pr])
        lo, hi = P.boot_ci_paired_by_date(pr, "a", "b")
        print(f"  PAIRED       n={len(pr):>4} / {n_dates(pr):>3} dates   "
              f"ΔR {d_mean:+.3f}   CI [{lo:+.3f}, {hi:+.3f}]")
        mean_g, share, min_g, folds = P.loo_by_date(pr, lambda r: r["a"],
                                                    lambda r: r["b"])
        print(f"  LOO-by-date  mean {mean_g:+.3f}  share+ {share:.0%}  "
              f"MIN {min_g:+.3f}  ({folds} folds)")
        for cut, rs in P.window_cuts(pr).items():
            if rs:
                print(f"    {cut:<16} n={len(rs):>4}  "
                      f"ΔR {_mean([r['a'] - r['b'] for r in rs]):+.3f}")
        exb = FS.ex_both_cut(pr)
        if exb:
            print(f"    {'ex_BOTH':<16} n={len(exb):>4}  "
                  f"ΔR {_mean([r['a'] - r['b'] for r in exb]):+.3f}   (by hand)")
        years = {y: _mean([r["a"] - r["b"] for r in rs])
                 for y, rs in P.by_year(pr).items()}
        print("    by year: " + "  ".join(f"{y} {v:+.3f}" for y, v in years.items()))
        stress = [r for r in rows if r.get("R_stress") is not None]
        if stress:
            print(f"    breach-stress  n={len(stress):>4}  "
                  f"ΔR {_mean([r['R_stress'] - r['base_R'] for r in stress]):+.3f}"
                  "   (intrinsic on every breached tranche)")
        mix = Counter(r["exit_reason"] for r in rows)
        print("    exits: " + "  ".join(f"{k}={v}" for k, v in mix.most_common()))


# ── E1 / E2 — exposure ───────────────────────────────────────────────────────

def report_e1_e2(built: dict) -> bool:
    hdr("E1 / E2 — EXPOSURE. What the overlay did to net delta and net vega.")
    print("""  Per-leg greeks read from the same cached history CSVs the pricing reads
  (lib/greeks.py: signed, qty-scaled, ALL-OR-NOTHING per greek — a missing leg
  makes the greek None, never 0).

  E1 IS A GATE, not a finding. The geometry is deterministic: a short CALL above
  the core must make net delta MORE NEGATIVE. A ladder cell whose delta moves the
  other way is a BUILD BUG and fails the run.

  Read at the COMMON ENTRY DAY, as registered. A trigger cell (T-GAP / T-RUN)
  has no tranche at entry, so its entry-day Δ is 0 by construction and the same
  geometry is gated at the FIRST SALE DAY instead — the column beside it. The
  naked-put cells REPLACE the core rather than wrap it (a short put is long
  delta), so their direction is reported and NOT gated; the registration pins
  the ladder geometry only.

  E2 is descriptive: every ladder cell sells an extra option and is structurally
  SHORT vega. This quantifies it; nothing is gated on it.""")
    print(f"\n  {'cell':<15} {'n':>5} {'base delta':>11} {'Δ delta @entry':>15} "
          f"{'Δ delta @sale':>14} {'row-sign':>9}  {'gate':<10} "
          f"{'Δ vega':>10} {'base vega':>10}")
    ok = True
    for cell in built["cells_active"]:
        rows = built["cells"].get(cell.label) or []
        if not rows:
            print(f"  {cell.label:<15} no rows")
            continue
        at_entry = [r for r in rows if r["d_delta"] is not None]
        at_sale = [r for r in rows if r["d_delta_sale"] is not None]
        m_entry = _mean([r["d_delta"] for r in at_entry]) if at_entry else float("nan")
        m_sale = _mean([r["d_delta_sale"] for r in at_sale]) if at_sale else float("nan")
        # Gate on the ENTRY-DAY figure when a tranche is actually live there
        # (T0 cells), else on the FIRST-SALE-DAY figure (T-GAP / T-RUN, whose
        # entry-day Δ is 0 because no tranche exists yet). Same geometry claim,
        # measured where the tranche exists.
        use_sale = not any(r["n_tranches"] and r["d_delta"] not in (None, 0.0)
                           for r in rows) and bool(at_sale)
        vals = at_sale if use_sale else at_entry
        key = "d_delta_sale" if use_sale else "d_delta"
        if cell.spec is None or cell.replaces_core or not vals:
            verdict = "not gated"
            sign = float("nan")
        else:
            m = _mean([r[key] for r in vals])
            good = m < 0
            ok = ok and good
            sign = sum(1 for r in vals if r[key] < 0) / len(vals)
            verdict = "PASS" if good else "FAIL"
        vg = [r["d_vega"] for r in rows if r["d_vega"] is not None]
        print(f"  {cell.label:<15} {len(rows):>5} "
              f"{_mean([r['base_delta'] for r in rows]):>+11.3f} "
              f"{_num(m_entry, 15)} {_num(m_sale, 14)} "
              f"{(f'{sign:.0%}' if sign == sign else '—'):>9}  {verdict:<10} "
              f"{(_mean(vg) if vg else float('nan')):>+10.3f} "
              f"{_mean([r['base_vega'] for r in rows]):>+10.3f}")
    print("\n  `row-sign` = share of gated rows whose Δ delta moved the registered "
          "way\n  (diagnostic; the gate is on the MEAN).")
    print(f"\n  E1 {'PASS' if ok else 'FAIL'}")
    return ok


# ── E3 — correlation with the deployed sleeve ────────────────────────────────

def report_e3(built: dict, power: dict, sleeve: dict[str, float],
              awaiting: set[str]) -> dict:
    hdr("E3 — CORRELATION WITH THE DEPLOYED SLEEVE (the vol_sleeve lesson)")
    print(f"""  The deployed sleeve is `top_k_per_day(ladder_rank, k=3)` over the eligible
  book — {len(sleeve)} dates. These cells are synthesized on the ENGINE'S OWN signal
  dates, so a wrapper can clear every R gate and still be re-wrapping the SAME
  exposure. Registered reading, fixed before the run:

      POSITIVE correlation = RE-WRAP verdict, REGARDLESS of ΔR.

  >= {MIN_SHARED_DATES} shared dates required; fewer means E3 is NOT EVALUABLE and the cell
  cannot be a CANDIDATE. Per year alongside.""")
    out: dict[str, tuple[float | None, int]] = {}
    print(f"\n  {'cell':<15} {'corr':>8} {'dates':>7}   by year")
    for cell in built["cells_active"]:
        rows = built["cells"].get(cell.label) or []
        if not rows:
            print(f"  {cell.label:<15} {'n/a':>8} {0:>7}   "
                  + (AWAITING if cell.label in awaiting else "no rows"))
            continue
        corr, n = FS.cell_corr(rows, sleeve)
        out[cell.label] = (corr, n)
        parts = []
        for y, rs in P.by_year(rows).items():
            c, _ = FS.cell_corr(rs, sleeve)
            if c is not None:
                parts.append(f"{y} {c:+.3f}")
        flag = ""
        if cell.label in awaiting:
            flag = f"  ({AWAITING} — not read)"
        elif not power.get(cell.label):
            flag = f"  ({UNDERPOWERED} — not read)"
        cs = f"{corr:>+8.3f}" if corr is not None else f"{'n/a':>8}"
        print(f"  {cell.label:<15} {cs} {n:>7}   " + "  ".join(parts) + flag)
    return out


# ── the criteria and the verdict grammar ─────────────────────────────────────

def verdict_of(*, awaiting: bool, powered_ok: bool, has_pairs: bool,
               r_gates: list[bool], c7: bool | None, c8: bool | None) -> str:
    """The registered verdict token for one cell. TOTAL: every state maps to
    exactly one token, and there is no state with none.

      AWAITING SCRAPE   the contracts are not cached yet — checked FIRST, because
                        an awaiting cell's rows are a partial cache, not a sample.
      UNDERPOWERED      G0's floor, or no paired rows to read at all.
      CANDIDATE         1-8 all pass. NOT a ship.
      RE-WRAP           1-6 and 8 pass, 7 fails — the ladder holds more of the
                        same exposure.
      BREACH-DOMINATED  1-7 pass and 8 FLIPS the sign — the edge is the tail it
                        did not pay for. Never softened into CANDIDATE.
      NULL              everything else, including an E3 that is NOT EVALUABLE
                        (which can never be a CANDIDATE) and the 1-6-pass /
                        7-fails / 8-fails corner, which is neither a RE-WRAP
                        (clause 8 is part of that token) nor breach-dominated
                        (clauses 1-7 are part of that one).
    """
    if awaiting:
        return AWAITING
    if not powered_ok or not has_pairs:
        return UNDERPOWERED
    if not all(r_gates):
        return "NULL"
    if c7 is True and c8 is True:
        return "CANDIDATE"
    if c7 is False and c8 is True:
        return "RE-WRAP"
    if c7 is True and c8 is False:
        return "BREACH-DOMINATED"
    return "NULL"


def evaluate(cell: Cell, rows: list[dict], powered_ok: bool,
             e3: tuple[float | None, int] | None, awaiting: bool
             ) -> tuple[str, list[tuple[str, bool | None, str]]]:
    """`(verdict, [(criterion, pass|None, detail)])` — the eight-part conjunction.

    `assert_not_model` runs on the row list BEFORE any criterion touches it: a
    `[MODEL]` row reaching a gate is a BUILD ERROR of the same class as pooling
    two prompt versions, and it fails the run rather than being filtered out.
    """
    if awaiting:
        return AWAITING, []
    OC.assert_not_model(rows)
    if not powered_ok or not rows:
        return UNDERPOWERED, []
    pr = FS.paired_rows(rows)
    if not pr:
        return UNDERPOWERED, []

    checks: list[tuple[str, bool | None, str]] = []

    d_mean = _mean([p["a"] - p["b"] for p in pr])
    lo, hi = P.boot_ci_paired_by_date(pr, "a", "b")
    c1 = d_mean > 0 and lo > 0
    checks.append(("1 paired ΔR > 0, CI excludes zero", c1,
                   f"ΔR {d_mean:+.3f}  CI [{lo:+.3f}, {hi:+.3f}]"))

    _, share, min_g, folds = P.loo_by_date(pr, lambda r: r["a"], lambda r: r["b"])
    c2 = min_g == min_g and min_g > 0
    checks.append(("2 every LOO fold positive", c2,
                   f"MIN {min_g:+.3f} over {folds} folds (share+ {share:.0%})"))

    cuts = {k: _mean([r["a"] - r["b"] for r in rs])
            for k, rs in P.window_cuts(pr).items() if rs and k != "ALL"}
    exb = FS.ex_both_cut(pr)
    if exb:
        cuts["ex_BOTH"] = _mean([r["a"] - r["b"] for r in exb])
    c3 = bool(cuts) and all(v > 0 for v in cuts.values())
    checks.append(("3 window cuts + ex-BOTH", c3,
                   "  ".join(f"{k} {v:+.3f}" for k, v in cuts.items())))

    years = {y: _mean([r["a"] - r["b"] for r in rs]) for y, rs in P.by_year(pr).items()}
    c4 = bool(years) and all(v > 0 for v in years.values())
    checks.append(("4 sign-stable every year", c4,
                   "  ".join(f"{y} {v:+.3f}" for y, v in years.items())))

    tiers = {}
    for src in ("real", "tweak"):
        rs = [p for p in pr if p["src"] == src]
        if rs:
            tiers[src] = (_mean([p["a"] - p["b"] for p in rs]), len(rs))
    c5 = bool(tiers) and all(v[0] > 0 for v in tiers.values())
    checks.append(("5 right-signed both pricing tiers", c5,
                   "  ".join(f"{k} n={v[1]} ΔR {v[0]:+.3f}" for k, v in tiers.items())))

    nd = n_dates(pr)
    c6 = nd >= MIN_DATES
    checks.append((f"6 >= {MIN_DATES} affected dates (priced set)", c6, f"{nd} dates"))

    corr, n_shared = e3 if e3 else (None, 0)
    if corr is None:
        c7: bool | None = None
        detail = f"NOT EVALUABLE — {n_shared} shared dates (< {MIN_SHARED_DATES})"
    else:
        c7 = corr <= 0
        detail = f"corr {corr:+.3f} over {n_shared} shared dates"
    checks.append(("7 E3 <= 0 (does not re-wrap the sleeve)", c7, detail))

    st = [r for r in rows if r.get("R_stress") is not None and r.get("base_R") is not None]
    if not st:
        c8: bool | None = None
        s_detail = "NOT EVALUABLE — no re-costable row"
    else:
        s_mean = _mean([r["R_stress"] - r["base_R"] for r in st])
        c8 = s_mean > 0
        s_detail = (f"ΔR {s_mean:+.3f} on {len(st)} rows with intrinsic paid on "
                    "every breached tranche")
    checks.append(("8 right-signed under breach-stress", c8, s_detail))

    verdict = verdict_of(awaiting=False, powered_ok=powered_ok, has_pairs=True,
                         r_gates=[c1, c2, c3, c4, c5, c6], c7=c7, c8=c8)
    return verdict, checks


def report_criteria(built: dict, power: dict, e3: dict,
                    awaiting: set[str]) -> dict[str, str]:
    hdr("CRITERIA — the pre-registered eight-part conjunction, per cell")
    print(f"""  All eight or nothing. Failing any one is failing; there is no partial credit
  and no "promising" cell. Criteria 1-7 are `financed_spread`'s seven verbatim;
  8 is this registration's own.

    CANDIDATE        clears 1-8. NOT a ship — it queues an independent-window
                     confirmation, and nothing ships from a research-tier study.
    RE-WRAP          clears 1-6 and 8, fails 7 — the ladder makes money by
                     holding MORE OF THE SAME exposure. This is the MODAL
                     EXPECTED outcome: `financed_spread` F3 already printed it
                     for a same-direction financed vertical on this book.
    BREACH-DOMINATED clears 1-7, and 8 flips the sign — the edge is the tail it
                     did not pay for. Never softened into CANDIDATE.
    NULL             a window artifact, or an E3 that cannot be evaluated.
    {UNDERPOWERED}     G0 floored the cell — census published, nothing concluded,
                     no re-run on these dates.
    {AWAITING}  the cell's contracts are not cached yet. Not a null.

  Only PRIMARY and naked-put cells may earn a verdict. SENSITIVITY cells print
  their n and are never a criterion.""")
    verdicts: dict[str, str] = {}
    for cell in built["cells_active"]:
        rows = built["cells"].get(cell.label) or []
        if cell.group == SENSITIVITY:
            tag = "  [MODEL]" if cell.is_model else ""
            sub(f"{cell.label}  —  SENSITIVITY, no verdict{tag}")
            print(f"  n={len(rows)} rows / {n_dates(rows)} dates. Printed with its "
                  "n; never a criterion,\n  never pooled with PRIMARY.")
            continue
        verdict, checks = evaluate(cell, rows, power.get(cell.label, False),
                                   e3.get(cell.label),
                                   cell.label in awaiting)
        verdicts[cell.label] = verdict
        sub(f"{cell.label}  —  {verdict}")
        if not checks:
            if verdict == AWAITING:
                print(f"  {len(rows)} rows on the cached subset — the contracts "
                      "this cell needs are not\n  fetched yet. No criterion "
                      "evaluated, and no verdict may be read off this\n  cell in "
                      "either direction.")
            else:
                print(f"  n={len(rows)} rows / {n_dates(rows)} dates — under the "
                      "G0 floor, no criterion evaluated.")
            continue
        if cell.label == BASE_LABEL:
            print("  L-BASE is the baseline paired against ITSELF: ΔR is 0 by "
                  "construction and the\n  conjunction below cannot clear. It is "
                  "printed because the registration says\n  every PRIMARY cell "
                  "prints its n and a verdict token regardless of outcome.")
        for name, ok, detail in checks:
            mark = "PASS" if ok is True else ("FAIL" if ok is False else " ?? ")
            print(f"  [{mark}] {name:<40} {detail}")
    return verdicts


# ── the regime cut — evidence, with G0 re-applied ────────────────────────────

def report_regimes(built: dict, awaiting: set[str]) -> None:
    hdr("REGIME CUT — the PRIMARY cells split by the book's own columns")
    print(f"""  This is EVIDENCE, not a sensitivity: the same cache-priced series, split by a
  column the book already carries. `mech_cell` is the mechanical SPY/VIX cell;
  `mech_vol` and `model_vol` are the L-VOL / H-VOL reads.

  G0 IS RE-APPLIED INSIDE EVERY CUT ({MIN_ROWS} rows / {MIN_DATES} dates), so an underpowered cut
  prints its n and NO statistic. That is the whole discipline of this section.""")
    for key in REGIME_KEYS:
        sub(f"cut on `{key}`")
        print(f"  {'cell':<15} {'level':<12} {'rows':>6} {'dates':>6}  "
              f"{'ΔR':>8}  status")
        for cell in built["cells_active"]:
            if cell.group != PRIMARY or cell.label == BASE_LABEL:
                continue
            rows = built["cells"].get(cell.label) or []
            if not rows:
                continue
            groups: dict[str, list[dict]] = defaultdict(list)
            for r in rows:
                groups[str(r.get(key) or "—")].append(r)
            for level, rs in sorted(groups.items()):
                pr = FS.paired_rows(rs)
                if cell.label in awaiting:
                    status, val = AWAITING, float("nan")
                elif powered(rs) and pr:
                    status = "POWERED"
                    val = _mean([p["a"] - p["b"] for p in pr])
                else:
                    status, val = UNDERPOWERED, float("nan")
                shown = f"{val:>+8.3f}" if val == val else f"{'—':>8}"
                print(f"  {cell.label:<15} {level:<12} {len(rs):>6} "
                      f"{n_dates(rs):>6}  {shown}  {status}")


# ── descriptive, NOT criteria ────────────────────────────────────────────────

def report_descriptive(built: dict, power: dict, sleeve: dict[str, float]) -> None:
    hdr("DESCRIPTIVE — worst-decile behaviour. NOT A CRITERION.")
    print("""  NOT A CRITERION. Printed because the question always gets asked, and refused
  as evidence because this book's date count cannot power a worst-decile read.
  No verdict above depends on anything in this block, and no cell may be promoted
  on it. No criterion in this registration requires one.""")
    if not sleeve:
        print("\n  no deployed sleeve — nothing to cut on")
        return
    vals = sorted(sleeve.values())
    cutoff = vals[max(0, len(vals) // 10 - 1)]
    worst = {d for d, v in sleeve.items() if v <= cutoff}
    print(f"\n  deployed sleeve {len(sleeve)} dates; worst decile = {len(worst)} "
          f"dates (mean R <= {cutoff:+.3f})")
    base_worst = [r for r in built["baseline"] if r["date"] in worst]
    if base_worst:
        print(f"  {'book baseline':<15} n={len(base_worst):>4}  "
              f"meanR {_mean([r['R'] for r in base_worst]):+.3f}")
    for cell in built["cells_active"]:
        rows = [r for r in (built["cells"].get(cell.label) or [])
                if r["date"] in worst]
        if not rows:
            continue
        tag = "" if power.get(cell.label) else "  (cell UNDERPOWERED)"
        print(f"  {cell.label:<15} n={len(rows):>4}  "
              f"meanR {_mean([r['R'] for r in rows]):+.3f}  "
              f"ΔR {_mean([r['R'] - r['base_R'] for r in rows]):+.3f}"
              f"   NOT A CRITERION{tag}")


# ── the per-row CSV ──────────────────────────────────────────────────────────

CSV_COLUMNS = (
    "date", "ticker", "structure", "source", "tier", "ladder_tier", "cell",
    "group", "mech_cell", "mech_vol", "model_vol", "core_dte", "entry_net",
    "core_net", "contracts", "R", "R_dol", "R_stress", "base_R", "base_R_dol",
    "exit_reason", "days_held", "mfe", "mae", "n_tranches", "n_breached",
    "n_live_days", "n_grid_days", "settle_mark", "settle_intrinsic",
    "open_at_grid_end", "breach_r_mean", "breach_r_worst", "credit_total",
    "first_strike", "first_expiry", "first_open", "clamped_full", "clamped_core",
    "cost_total", "cost_basis", "cost_net_dol", "sens_cost_total",
    "sens_net_dol", "n_would_size", "unbounded_size", "margin_proxy",
    "d_delta", "d_delta_sale", "d_vega", "base_delta", "base_vega",
)


def write_rows_csv(built: dict, path: Path = ROWS_CSV) -> tuple[Path, int]:
    """Every (core, cell) result row, one CSV line each.

    The `tier` column is the PRICING tier (`cache` / `model`), which is what
    `assert_not_model` reads; the book's ladder tier (A/B/C/VETO) rides along as
    `ladder_tier` so the two can never be confused by a reader or by a chart
    layer.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(CSV_COLUMNS)
        for cell in built["cells_active"]:
            for r in built["cells"].get(cell.label) or []:
                w.writerow([r.get(c) for c in CSV_COLUMNS])
                n += 1
    return path, n


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--era", default=None,
                    help="book era to run on (default: STUDY_ERA, else current). "
                         "The two eras are NEVER pooled.")
    ap.add_argument("--cells", default="",
                    help="BUILD-ONLY dev flag: comma-separated subset of cell "
                         "labels. A partial run is NOT the study.")
    ap.add_argument("--limit-rows", type=int, default=0,
                    help="BUILD-ONLY dev flag: cap the population at N cores for "
                         "a smoke run. A capped run is NOT the study.")
    a = ap.parse_args(argv)

    cells = CELLS
    if a.cells:
        want = [s.strip() for s in a.cells.split(",") if s.strip()]
        bad = [s for s in want if s not in CELL_BY_LABEL]
        if bad:
            print(f"unknown cell(s): {bad}", file=sys.stderr)
            return EXIT_GATE_FAILED
        cells = tuple(c for c in CELLS if c.label in want)

    # load_book owns the era guard: exit 3 when the exports on disk are not the
    # era asked for, exit 2 when the era is too thin to conclude from. Both are
    # DESIGNED refusals (declared at the top), not failures.
    recs, diag = load_book(include_bs=False, era=a.era)

    pop, why = population(recs)
    if a.limit_rows:
        pop = pop[:a.limit_rows]

    partial = bool(a.limit_rows) or len(cells) != len(CELLS)
    if partial:
        print("=" * 78)
        print("*** PARTIAL RUN — BUILD-ONLY FLAGS IN USE. THIS IS NOT THE STUDY. ***")
        print(f"***   cells={len(cells)}/{len(CELLS)}  "
              f"limit_rows={a.limit_rows or 'none'}")
        print("=" * 78)

    install_target_memo()
    commission, slippage = cost_knobs()
    scrape = manifest_census()
    awaiting = awaiting_cells(scrape) & {c.label for c in cells}

    report_header(recs, diag, pop, why, commission, slippage)
    report_cell_table(cells)
    report_scrape(scrape, awaiting)

    built = build(pop, cells, commission, slippage)

    # G0 RUNS AND PRINTS FIRST — the registration's "runs FIRST", in execution
    # order as well as on the page.
    power = gate_g0(built, awaiting)
    ok_g1 = gate_g1(len(pop), built["g1"])
    ok_g1b = gate_g1b(built)
    ok_g2 = gate_g2(built)
    gate_g3(built)
    gate_g4(built)
    report_costs(built, commission, slippage)

    sleeve = FS.sleeve_daily(recs)
    report_cells(built, power, awaiting)
    ok_e1 = report_e1_e2(built)
    e3 = report_e3(built, power, sleeve, awaiting)

    leak = False
    try:
        verdicts = report_criteria(built, power, e3, awaiting)
    except OC.ModelTierLeak as exc:
        hdr("MODEL TIER LEAK")
        print(f"  {exc}")
        print("  A `[MODEL]` row reached a criterion. That is a BUILD ERROR of the "
              "same class as\n  pooling two prompt versions into one population — "
              "nothing above is evidence.")
        verdicts, leak = {}, True

    report_regimes(built, awaiting)
    report_descriptive(built, power, sleeve)

    if verdicts:
        hdr("VERDICTS")
        for cell in built["cells_active"]:
            if cell.group == SENSITIVITY:
                continue
            print(f"  {cell.label:<15} {verdicts.get(cell.label, UNDERPOWERED)}")
        print("\n  CANDIDATE is not a ship. Nothing ships from a research-tier "
              "study, and a\n  RE-WRAP or BREACH-DOMINATED cell closes its own "
              "thread for these dates.")

    path, n_rows = write_rows_csv(built)
    print(f"\nper-row per-cell results: {n_rows} rows -> "
          f"{path.relative_to(ROOT)}")

    failed = [name for name, ok in
              (("G1 reconstruction", ok_g1), ("G1b F4 identity", ok_g1b),
               ("G2 clamp attribution", ok_g2), ("E1 delta geometry", ok_e1),
               ("MODEL tier leak", not leak)) if not ok]
    if failed:
        hdr("RUN FAILED")
        print("  " + "; ".join(failed))
        print("  A failed gate is a BUILD BUG, not a finding — nothing above is "
              "readable as evidence.")
        return EXIT_GATE_FAILED

    if awaiting:
        hdr(AWAITING)
        print("  " + "  ".join(sorted(awaiting)))
        print(f"""
  The contracts these cells need are still PENDING in
  backtests/sweep_cache/ladder_manifest.csv. Every gate above ran and every cell
  was built on the cached subset, so the machinery is proved — but no criterion
  was evaluated on an awaiting cell and NOTHING about one is a finding.

  The run exits {EXIT_AWAITING_SCRAPE}, as registered: the census above IS the study's
  current, correct, quotable status, and `run.py` promotes this report to
  `-latest.txt` on a clean exit.""")
        return EXIT_AWAITING_SCRAPE
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
