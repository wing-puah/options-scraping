"""Cost sensitivity (robustness N1): at what cost per leg does the Tier A/B edge vanish?

Registration: research/pre-registrations/f2_management/cost_sensitivity.md,
accepted by default 2026-10-09. Every arm, gate, bar and verdict below is
transcribed from it; the "Resolved at build" tags there say how each open
point was settled. Read that file before changing anything here.

WHAT IT DOES
------------
The deployed set (top-3/day, Tier A and Tier B, read separately) is loaded once
through `load_book()`. Each position's stored R is net of production's
commission (`cost_total`, the 2026-09-24 commission-only re-price), so the study
first rebuilds GROSS R by adding that cost back, then charges each arm's own
cost onto gross R:

    ARM Z    no cost. Reference only, never a result.
    ARM X    $0.65 per contract, per leg, per side, no slippage. PRIMARY:
             C0-C4 are graded on this arm alone.
    ARM SW   commission x slippage-fraction grid. Sensitivity: the contour.
    ARM Q    quote census + the fixed fallback ladder for the slippage cells.
    ARM GAP  ARM X plus one adverse tick at a threshold exit. Sensitivity.

Cost in R units, per position (contracts cancel):

    commission  = c * sum|qty| * sides / (|entry| * 100)
    slippage    = f * sum_sides sum_legs |qty| * spread / |entry|
    tick (GAP)  = tick * sum|qty| / |entry|               (exit side only)

`sides` is 2, or 1 for an `expired` row (registered: an expired leg carries no
exit cost). Production charges an expired row at both sides; that is the one
place ARM X and the stored R differ, and gate G2 checks it.

Gates: G1 era (lib/era.py), G2 charge-count + stored-cost reconcile (exit 5),
G3 export provenance (exit 4, a designed refusal), G4 quote provenance
(verdict-producing, never a refusal), G5-G7 by construction.

Holdout seal: this study is not a named sealed reader. It reads the book only
through `load_book()` without `sealed_read`, which withholds sealed dates, and
it opens no export itself.

Read-only. Touches no config, no tab. Run:

    python -m scripts.backtest_study run cost_sensitivity
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from lib.barchart.options import cache_path, parse_history_details  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.legs import parse_legs  # noqa: E402
from scripts.backtest.simulate import _leg_spread  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.lib.harness import Trade  # noqa: E402

REGISTRATION = "research/pre-registrations/f2_management/cost_sensitivity.md"
BACKTEST_CONFIG = ROOT / "config" / "backtest.yml"

# --- registered constants (the registration, not defaults) -------------------
ARM_X = (0.65, 0.0)                              # $/contract/leg/side, slippage fraction
SW_COMMISSIONS = (0.00, 0.65, 1.00, 1.50)
SW_FRACTIONS = (0.00, 0.25, 0.50, 1.00)
# ARM GAP tick per leg per share, at exit. Headline + declared secondary
# (Resolved at build 2026-10-09: the draft gave no size).
GAP_TICKS = (("headline", 0.05), ("secondary", 0.01))
# Every threshold-triggered exit the frozen harness can fire (registration, ARM GAP).
THRESHOLD_EXITS = frozenset({"profit_target", "trailing_stop", "underlying_stop",
                             "dollar_stop", "be_stop", "stop_loss"})
EXPIRED = "expired"
G4_MAX_SHARE = 0.25          # fallback-2 + uncostable share of quoted leg-sides
C0_MIN_DATES = 25
C0_MIN_POSITIONS = 40
TOP_K = 3
TIERS = ("A", "B")

# C4 when the second era cannot be read (Resolved at build 2026-10-09).
C4_UNGRADED_MODES = (("headline", "fails"), ("secondary", "drops"))

# --- exit codes ---------------------------------------------------------------
EXIT_G3_PROVENANCE = 4       # designed: the export predates B1/B2
EXIT_G2_MISMATCH = 5         # NOT designed: a charge-count or stored-cost mismatch is a bug
DESIGNED_REFUSAL_EXIT_CODES = frozenset({2, 3, 4})

# Quote tags, in fallback order.
DIRECT, FB1, FB2, UNCOSTABLE = "direct", "fallback1", "fallback2", "uncostable"


class GateRefusal(Exception):
    """A registered gate refused. `code` is the exit code."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


# --- the charging arithmetic --------------------------------------------------

def sides_for(exit_reason) -> int:
    """Sides a position is charged at: 1 for an `expired` row, else 2."""
    return 1 if (exit_reason or "") == EXPIRED else 2


def charge_events(legs, exit_reason) -> list[tuple[int, str]]:
    """`[(leg_index, side)]` — every leg-side the cost model charges."""
    sides = ("entry",) if sides_for(exit_reason) == 1 else ("entry", "exit")
    return [(i, s) for s in sides for i, _ in enumerate(legs)]


def expected_charge_count(n_legs: int, exit_reason) -> int:
    """G2's independent count, read straight off `exit_reason`."""
    return n_legs * (2 - int(str(exit_reason or "").strip() == "expired"))


def leg_units(legs) -> int:
    """sum |qty| over a position's legs."""
    return sum(abs(leg.qty) for leg in legs)


def gross_r(stored_r: float, cost_total, denom: float, contracts: int) -> float:
    """Stored (net) R with production's charge added back."""
    ct = float(cost_total or 0.0)
    return stored_r + ct / (denom * 100 * contracts)


def commission_r(c: float, legs, denom: float, exit_reason) -> float:
    """Commission in R units for one position: |qty| per charged leg-side."""
    units = sum(abs(legs[i].qty) for i, _side in charge_events(legs, exit_reason))
    return c * units / (denom * 100)


def slippage_r(frac: float, legs, denom: float, spreads: dict) -> float | None:
    """Slippage in R units. `spreads` maps (leg_index, side) -> spread in option
    points, or None when that leg-side is uncostable — then the position is
    uncostable and this returns None (never charged zero)."""
    if frac == 0:
        return 0.0
    total = 0.0
    for key, spread in spreads.items():
        if spread is None:
            return None
        total += abs(legs[key[0]].qty) * spread
    return frac * total / denom


def gap_r(tick: float, legs, denom: float, exit_reason) -> float:
    """ARM GAP's extra adverse tick at exit, on a threshold exit only."""
    if (exit_reason or "") not in THRESHOLD_EXITS:
        return 0.0
    return tick * leg_units(legs) / denom


def stored_cost_expected(c: float, legs, contracts: int) -> float:
    """What production's `_apply_costs` charges at slippage 0: both sides, always."""
    return round(c * leg_units(legs) * contracts * 2, 2)


# --- quotes (ARM Q) -----------------------------------------------------------

def usable_spread(row) -> float | None:
    """A leg-day's quoted spread when usable, else None.

    Degenerate = the registration's tests (no Bid/Ask, Ask <= Bid, Bid = 0) plus
    production's junk-quote rule; `simulate._leg_spread` encodes both except
    Ask == Bid, which a zero spread catches here.
    """
    if not row:
        return None
    s = _leg_spread(row)
    if isinstance(s, (int, float)) and s > 0:
        return float(s)
    return None


def resolve_spread(direct, own_path, ticker_peers) -> tuple[float | None, str]:
    """The fixed fallback ladder for one leg-side: `(spread, tag)`.

    `direct` is the leg's usable spread on the day (or None); `own_path` the
    contract's usable spreads over its own priced path; `ticker_peers` the
    usable spreads of the same ticker's other legs on that day. Either list may
    be a zero-argument callable, evaluated only when the ladder reaches it.
    Order fixed by the registration: direct, fallback 1, fallback 2, uncostable.
    """
    if direct is not None:
        return direct, DIRECT
    own = [s for s in (own_path() if callable(own_path) else own_path) if s is not None]
    if own:
        return statistics.median(own), FB1
    peers = [s for s in (ticker_peers() if callable(ticker_peers) else ticker_peers)
             if s is not None]
    if peers:
        return statistics.median(peers), FB2
    return None, UNCOSTABLE


class QuoteBook:
    """Cached per-contract `{date: row}` from the option history cache."""

    def __init__(self, cache_dir: Path = HISTORY_CACHE):
        self.cache_dir = Path(cache_dir)
        self._details: dict[tuple, dict] = {}

    @staticmethod
    def key(leg) -> tuple:
        return (leg.ticker, leg.expiration, round(leg.strike, 4), leg.opt_type)

    def details(self, leg) -> dict:
        k = self.key(leg)
        if k not in self._details:
            p = cache_path(self.cache_dir, leg.ticker, leg.expiration, leg.strike, leg.opt_type)
            self._details[k] = (parse_history_details(p.read_text(), require_mark=False)
                                if p.exists() else {})
        return self._details[k]

    def spread(self, leg, day: date) -> float | None:
        return usable_spread(self.details(leg).get(day))


# --- one position -------------------------------------------------------------

def entry_day(t) -> date:
    """The recorded fill day (registration: `legs[0].expiration - dte_entry`)."""
    return t.legs[0].expiration - timedelta(days=int(t.dte_entry))


def exit_day(t, days_held) -> date | None:
    """The grid day at `days_held` — the day production prices its exit spread."""
    if days_held is None:
        return None
    grid = t.grid if not hasattr(t, "uncut_grid_len") else Trade(t.row).grid
    if 1 <= days_held <= len(grid):
        return grid[days_held - 1]
    return None


def build_position(rec: dict) -> dict:
    """The study's view of one deployed record. Raises nothing: a field it
    cannot read is left None and counted by the caller."""
    t = rec["t"]
    row = t.row
    legs = parse_legs(row.get("legs") or "") or []
    detail_lines = [ln for ln in str(row.get("entry_leg_detail") or "").split("\n") if ln.strip()]
    stored = rec.get("R")
    cost_total = row.get("cost_total")
    gross = (gross_r(float(stored), cost_total or 0.0, t.denom, t.contracts)
             if stored is not None else None)
    return dict(
        date=rec["date"], ticker=rec["ticker"], tier=rec["tier"], source=rec["source"],
        structure=rec["structure"], exit_reason=rec.get("exit_reason") or "",
        days_held=rec.get("days_held"), denom=t.denom, contracts=t.contracts,
        legs=legs, n_detail=len(detail_lines), stored_R=stored, gross_R=gross,
        cost_total=cost_total, cost_basis=(row.get("cost_basis") or "").strip(),
        has_cost_col="cost_basis" in row, E=rec.get("E"), t=t,
    )


# --- gates --------------------------------------------------------------------

def gate_g3(positions: list[dict]) -> dict:
    """Export provenance: every row written by code carrying B1 + B2."""
    no_col = sum(1 for p in positions if not p["has_cost_col"])
    blank = sum(1 for p in positions if p["has_cost_col"] and not p["cost_basis"])
    info = dict(n=len(positions), no_column=no_col, blank=blank,
                bases=Counter(p["cost_basis"] for p in positions))
    if no_col or blank:
        raise GateRefusal(EXIT_G3_PROVENANCE,
                          f"G3 GRID FIX PRESENT — {no_col} rows from an export with no "
                          f"cost_basis column and {blank} rows with it blank, of {len(positions)}. "
                          f"Those rows were written before B1/B2 (2026-09-08).")
    return info


def gate_g2(positions: list[dict], stored_commission: float, stored_slippage: float) -> dict:
    """Charge count, leg count and stored-cost reconcile. Raises on any mismatch."""
    bad_sides, bad_legs, bad_cost, checked_cost = [], [], [], 0
    for p in positions:
        tag = f"{p['date']} {p['ticker']} {p['structure']}"
        if len(charge_events(p["legs"], p["exit_reason"])) != \
                expected_charge_count(len(p["legs"]), p["exit_reason"]):
            bad_sides.append(tag)
        if not p["legs"] or len(p["legs"]) != p["n_detail"]:
            bad_legs.append(tag)
        if p["cost_basis"] == "commission_only" and stored_slippage == 0:
            checked_cost += 1
            want = stored_cost_expected(stored_commission, p["legs"], p["contracts"])
            if abs(float(p["cost_total"] or 0.0) - want) > 0.011:
                bad_cost.append(f"{tag} stored {p['cost_total']} vs {want:.2f}")
    if bad_sides or bad_legs or bad_cost:
        lines = [f"G2 COST IS CHARGED TWICE, NEVER ONCE — {len(bad_sides)} side-count, "
                 f"{len(bad_legs)} leg-count and {len(bad_cost)} stored-cost mismatches."]
        lines += [f"    {x}" for x in (bad_sides + bad_legs + bad_cost)[:10]]
        raise GateRefusal(EXIT_G2_MISMATCH, "\n".join(lines))
    return dict(n=len(positions), cost_checked=checked_cost,
                expired=sum(1 for p in positions if p["exit_reason"] == EXPIRED))


def stored_knobs(path: Path = BACKTEST_CONFIG) -> tuple[float, float]:
    """`(commission_per_contract, slippage_frac_of_spread)` the stored rows were
    charged under — read from config/backtest.yml, never defaulted here."""
    sim = (yaml.safe_load(path.read_text()) or {}).get("simulation") or {}
    return (float(sim["commission_per_contract"]), float(sim["slippage_frac_of_spread"]))


# --- quotes for the whole deployed set ----------------------------------------

def attach_quotes(positions: list[dict], qb: QuoteBook) -> Counter:
    """Set `p["spreads"]` = {(leg_i, side): spread|None} and `p["quote_tags"]`
    on every position, and return the leg-side tag census."""
    days: dict[int, dict] = {}
    by_ticker: dict[str, set] = defaultdict(set)
    for idx, p in enumerate(positions):
        t = p["t"]
        try:
            ed = entry_day(t)
        except (TypeError, ValueError, IndexError):
            ed = None
        xd = exit_day(t, p["days_held"])
        days[idx] = {"entry": ed, "exit": xd}
        for leg in p["legs"]:
            by_ticker[leg.ticker].add(leg)

    census: Counter = Counter()
    for idx, p in enumerate(positions):
        spreads, tags = {}, {}
        ed, xd = days[idx]["entry"], days[idx]["exit"]
        for i, side in charge_events(p["legs"], p["exit_reason"]):
            leg = p["legs"][i]
            day = ed if side == "entry" else xd
            if day is None:
                spreads[(i, side)], tags[(i, side)] = None, UNCOSTABLE
                census[UNCOSTABLE] += 1
                continue

            def own(leg=leg, ed=ed, xd=xd):
                if ed is None or xd is None:
                    return []
                return [usable_spread(r) for d, r in qb.details(leg).items() if ed <= d <= xd]

            def peers(leg=leg, day=day):
                return [qb.spread(o, day) for o in by_ticker[leg.ticker]
                        if QuoteBook.key(o) != QuoteBook.key(leg)]

            s, tag = resolve_spread(qb.spread(leg, day), own, peers)
            spreads[(i, side)], tags[(i, side)] = s, tag
            census[tag] += 1
        p["spreads"], p["quote_tags"] = spreads, tags
    return census


def g4_share(census: Counter) -> float:
    n = sum(census.values())
    return (census[FB2] + census[UNCOSTABLE]) / n if n else 0.0


# --- net R per cell -----------------------------------------------------------

def net_r(p: dict, c: float, frac: float, tick: float = 0.0) -> float | None:
    """Net R for one position at one cost point, or None when uncostable."""
    if p["gross_R"] is None:
        return None
    slip = slippage_r(frac, p["legs"], p["denom"], p.get("spreads", {})) if frac else 0.0
    if slip is None:
        return None
    return (p["gross_R"] - commission_r(c, p["legs"], p["denom"], p["exit_reason"])
            - slip - (gap_r(tick, p["legs"], p["denom"], p["exit_reason"]) if tick else 0.0))


def cell_rows(positions: list[dict], c: float, frac: float, tick: float = 0.0) -> list[dict]:
    out = []
    for p in positions:
        v = net_r(p, c, frac, tick)
        if v is not None:
            out.append({"date": p["date"], "ticker": p["ticker"], "net": v})
    return out


def mean_ci(rows: list[dict], boot_n: int) -> tuple[float, float, float]:
    if not rows:
        return float("nan"), float("nan"), float("nan")
    m = statistics.fmean(r["net"] for r in rows)
    lo, hi = P.boot_ci_by_date(rows, key="net", n=boot_n)
    return m, lo, hi


def loo_min(rows: list[dict], key: str) -> tuple[float, str, int]:
    """(lowest fold mean, the unit dropped there, n folds) — leave one `key` out."""
    units = sorted({r[key] for r in rows})
    worst, who = float("inf"), ""
    for u in units:
        kept = [r["net"] for r in rows if r[key] != u]
        if kept:
            m = statistics.fmean(kept)
            if m < worst:
                worst, who = m, u
    return worst, who, len(units)


def implied_dollars(c: float, frac: float, mean_spread: float | None) -> float | None:
    """Implied dollars per leg per side at a cost point."""
    if frac and mean_spread is None:
        return None
    return c + frac * (mean_spread or 0.0) * 100


# --- verdicts -----------------------------------------------------------------

def tier_verdict(c0: bool, c_main: bool | None, c3: bool | None, c4: bool | None,
                 c4_mode: str) -> str:
    """Per-tier verdict. `c4` None = ungraded; `c4_mode` says what that means."""
    if not c0:
        return "UNDERPOWERED"
    if not c_main:
        return "VANISHES"
    c4_ok = c4 if c4 is not None else (c4_mode == "drops")
    return "SURVIVES" if (c3 and c4_ok) else "FRAGILE"


def c0_passes(n_dates: int, n_positions: int) -> bool:
    return n_dates >= C0_MIN_DATES and n_positions >= C0_MIN_POSITIONS


# --- loading ------------------------------------------------------------------

def load_deployed(era: str | None) -> tuple[list[dict], dict]:
    """The deployed top-3/day set as study positions, plus the loader's diag."""
    records, diag = load_book(era=era)
    picked = P.top_k_per_day(records, P.ladder_rank, k=TOP_K, eligible_fn=P.ladder_eligible)
    return [build_position(r) for r in picked], diag


def arm_x_tier_read(positions: list[dict], boot_n: int) -> dict:
    """ARM X numbers for one tier's positions."""
    rows = cell_rows(positions, *ARM_X)
    m, lo, hi = mean_ci(rows, boot_n)
    return dict(rows=rows, n=len(rows), dates=len({r["date"] for r in rows}),
                mean=m, lo=lo, hi=hi, passes=(lo > 0) if rows else False)


# --- printing helpers ----------------------------------------------------------

def hdr(t: str) -> None:
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def fmt(x, nd=4) -> str:
    if x is None or x != x:
        return "n/a"
    return f"{x:+.{nd}f}"


def fmt_pf(x) -> str:
    """A profit factor: unsigned, 2 dp; n/a when undefined (no losing row)."""
    if x is None or x != x:
        return "n/a"
    return f"{x:.2f}"


def _seal_line(diag: dict) -> str:
    seal = diag.get("seal")
    fn = getattr(era_mod, "seal_line", None)
    if seal is not None and fn is not None:
        return fn(seal)
    return "SEAL: this loader applies no seal; see the population date range"


# --- main ---------------------------------------------------------------------

def run(boot_n: int = P.BOOT_N) -> int:
    era_req = era_mod.requested_era()
    hdr("COST_SENSITIVITY — at what cost per leg does the Tier A/B edge vanish?")
    print(f"registration: {REGISTRATION} (accepted by default 2026-10-09)")

    positions, diag = load_deployed(era_req)
    era = diag["era"]
    dr = diag.get("date_range") or (None, None)
    print(f"G1 ERA IDENTITY: era {era} (asked {era_req}); loaded book {diag.get('n_dates')} "
          f"dates, {dr[0]} -> {dr[1]}")
    print(f"  {_seal_line(diag)}")
    srcs = Counter(p["source"] for p in positions)
    if set(srcs) - {"real", "tweak"}:
        raise GateRefusal(EXIT_G2_MISMATCH, f"G7 PRICING-TIER HONESTY — sources {dict(srcs)}")
    print(f"  deployed top-{TOP_K}/day: {len(positions)} positions on "
          f"{len({p['date'] for p in positions})} dates; sources {dict(srcs)} (G7: no bs)")

    g3 = gate_g3(positions)
    print(f"G3 GRID FIX PRESENT: PASS — {g3['n']} rows, cost_basis {dict(g3['bases'])}")

    c_st, s_st = stored_knobs()
    g2 = gate_g2(positions, c_st, s_st)
    print(f"G2 COST IS CHARGED TWICE, NEVER ONCE: PASS — {g2['n']} positions; "
          f"{g2['expired']} expired (entry side only); stored cost_total reconciled on "
          f"{g2['cost_checked']} commission_only rows at the stored knobs "
          f"(commission {c_st:.2f}, slippage {s_st:.2f})")
    no_r = sum(1 for p in positions if p["gross_R"] is None)
    if no_r:
        print(f"  {no_r} deployed positions carry no stored R and are left out of every arm")

    census = attach_quotes(positions, QuoteBook())
    share = g4_share(census)
    g4_pass = share <= G4_MAX_SHARE
    hdr("ARM Q — quote census (leg-sides the slippage cells need), counts only")
    n_ls = sum(census.values())
    for tag in (DIRECT, FB1, FB2, UNCOSTABLE):
        print(f"  {tag:<11} {census[tag]:>6}  {census[tag] / n_ls if n_ls else 0:6.1%}")
    unc_pos = sum(1 for p in positions if any(v is None for v in p["spreads"].values()))
    print(f"  uncostable positions (excluded from slippage cells): {unc_pos} of {len(positions)}")
    print(f"G4 QUOTE PROVENANCE: {'PASS' if g4_pass else 'FAIL'} — fallback-2 + uncostable "
          f"share {share:.1%} (bar {G4_MAX_SHARE:.0%}); ARM X reads no quote and passes trivially")

    by_tier = {tier: [p for p in positions if p["tier"] == tier and p["gross_R"] is not None]
               for tier in TIERS}

    hdr("C0 POWER FLOOR (ARM X population)")
    c0 = {}
    for tier in TIERS:
        ps = by_tier[tier]
        nd = len({p["date"] for p in ps})
        c0[tier] = c0_passes(nd, len(ps))
        print(f"  Tier {tier}: {len(ps)} positions on {nd} dates — "
              f"{'readable' if c0[tier] else 'UNDERPOWERED (census only)'} "
              f"(floor {C0_MIN_DATES} dates, {C0_MIN_POSITIONS} positions)")

    # --- the second era (C4) ------------------------------------------------
    other = "v3" if era != "v3" else None
    c4_note, other_reads = "", {}
    if other is None:
        c4_note = "no second era to compare"
    else:
        try:
            o_pos, _o_diag = load_deployed(other)
            gate_g3(o_pos)
            gate_g2(o_pos, c_st, s_st)
            for tier in TIERS:
                tp = [p for p in o_pos if p["tier"] == tier and p["gross_R"] is not None]
                if c0_passes(len({p["date"] for p in tp}), len(tp)):
                    other_reads[tier] = arm_x_tier_read(tp, boot_n)
            c4_note = f"{other} read"
        except GateRefusal as exc:
            c4_note = f"{other} REFUSED — {str(exc).splitlines()[0]}"
        except SystemExit as exc:
            c4_note = f"{other} REFUSED by lib/era.py (exit {exc.code})"

    verdicts: dict[str, dict[str, str]] = {mode: {} for _, mode in C4_UNGRADED_MODES}
    for tier in TIERS:
        ps = by_tier[tier]
        hdr(f"TIER {tier}")
        if not c0[tier]:
            print("  UNDERPOWERED — census only, no outcome number printed.")
            for _, mode in C4_UNGRADED_MODES:
                verdicts[mode][tier] = "UNDERPOWERED"
            continue

        z_rows = cell_rows(ps, 0.0, 0.0)
        zm, zlo, zhi = mean_ci(z_rows, boot_n)
        e_vals = [p["E"] for p in ps if p["E"] is not None]
        print(f"ARM Z (zero-cost control, reference only): n={len(z_rows)} gross meanR "
              f"{fmt(zm)} [{fmt(zlo)}, {fmt(zhi)}]; PF {fmt_pf(P.pf(z_rows, 'net'))}; "
              f"E gross mean {fmt(statistics.fmean(e_vals) if e_vals else None)} (never graded)")

        x = arm_x_tier_read(ps, boot_n)
        pf_pt, pf_lo, pf_hi = P.pf_ci_by_date(x["rows"], key="net", n=boot_n)
        stored_m = statistics.fmean(p["stored_R"] for p in ps)
        print(f"ARM X (PRIMARY, $0.65/contract/leg/side, no slippage): n={x['n']} on {x['dates']} dates")
        print(f"  net meanR {fmt(x['mean'])}  95% date-clustered CI [{fmt(x['lo'])}, {fmt(x['hi'])}]")
        print(f"  net PF    {fmt_pf(pf_pt)}  95% CI [{fmt_pf(pf_lo)}, {fmt_pf(pf_hi)}]")
        print(f"  stored meanR (production basis, both sides on expired rows) {fmt(stored_m)}")
        c_main = x["passes"]
        cname = "C1" if tier == "A" else "C2"
        print(f"  {cname} TIER {tier} NET-POSITIVE: {'HOLDS' if c_main else 'FAILS'}")

        d_min, d_who, d_n = loo_min(x["rows"], "date")
        t_min, t_who, t_n = loo_min(x["rows"], "ticker")
        c3 = (d_min > 0 and t_min > 0) if c_main else None
        print(f"  C3 LEAVE-ONE-OUT: worst date fold {fmt(d_min)} (drop {d_who}, {d_n} folds); "
              f"worst ticker fold {fmt(t_min)} (drop {t_who}, {t_n} folds) -> "
              f"{'n/a (C' + ('1' if tier == 'A' else '2') + ' fails)' if c3 is None else ('HOLDS' if c3 else 'FAILS')}")

        c4 = None
        if tier in other_reads:
            o = other_reads[tier]
            c4 = bool(c_main and o["passes"] and (o["mean"] > 0) == (x["mean"] > 0))
            print(f"  C4 ERA STABILITY: {other} net meanR {fmt(o['mean'])} [{fmt(o['lo'])}, "
                  f"{fmt(o['hi'])}] n={o['n']} -> {'HOLDS' if c4 else 'FAILS'}")
        else:
            print(f"  C4 ERA STABILITY: NOT GRADED — {c4_note}")
        for _, mode in C4_UNGRADED_MODES:
            verdicts[mode][tier] = tier_verdict(True, c_main, c3, c4, mode)

        # --- ARM SW --------------------------------------------------------
        direct_spreads = [s for p in ps for k, s in p["spreads"].items()
                          if p["quote_tags"][k] == DIRECT]
        mean_spread = statistics.fmean(direct_spreads) if direct_spreads else None
        print(f"\nARM SW (sensitivity only; never a verdict) — net meanR [95% CI] n; "
              f"tier mean direct quoted spread {fmt(mean_spread, 3) if mean_spread else 'n/a'} pts")
        print(f"  {'commission':>10} {'slip':>5} {'$/leg/side':>10}  {'meanR':>8}  "
              f"{'CI lo':>8} {'CI hi':>8} {'n':>5}  note")
        cells = []
        for c in SW_COMMISSIONS:
            for f in SW_FRACTIONS:
                note = "ARM Z" if (c, f) == (0.0, 0.0) else ("ARM X" if (c, f) == ARM_X else "")
                imp = implied_dollars(c, f, mean_spread)
                if f > 0 and not g4_pass:
                    print(f"  {c:>10.2f} {f:>5.2f} {'':>10}  UNCOSTABLE (G4 failed; census above)")
                    continue
                rows = cell_rows(ps, c, f)
                m, lo, hi = mean_ci(rows, boot_n)
                cells.append(dict(c=c, f=f, imp=imp, mean=m, lo=lo, n=len(rows)))
                print(f"  {c:>10.2f} {f:>5.2f} {('%.2f' % imp) if imp is not None else 'n/a':>10}  "
                      f"{fmt(m):>8}  {fmt(lo):>8} {fmt(hi):>8} {len(rows):>5}  {note}")
        crossing = [cl for cl in cells if cl["imp"] is not None and cl["lo"] <= 0]
        if crossing:
            first = min(crossing, key=lambda cl: (cl["imp"], cl["c"], cl["f"]))
            print(f"  CONTOUR: lowest crossing cell (commission {first['c']:.2f}, slippage "
                  f"{first['f']:.2f}) = ${first['imp']:.2f} per leg per side")
            if (first["c"], first["f"]) == (0.0, 0.0):
                print("  The zero-cost cell already crosses: the gross CI includes zero, "
                      "so there is no gross edge for a cost to remove.")
        else:
            print("  CONTOUR: no crossing on the grid")
        for c in SW_COMMISSIONS:
            row = [cl for cl in cells if cl["c"] == c and cl["lo"] <= 0]
            first_f = min((cl["f"] for cl in row), default=None)
            print(f"    commission {c:.2f}: first crossing slippage "
                  f"{'none' if first_f is None else f'{first_f:.2f}'}")

        # --- ARM GAP -------------------------------------------------------
        print("\nARM GAP (sensitivity only) — ARM X plus one adverse tick at a threshold exit")
        n_thr = sum(1 for p in ps if p["exit_reason"] in THRESHOLD_EXITS)
        for label, tick in GAP_TICKS:
            rows = cell_rows(ps, *ARM_X, tick=tick)
            m, lo, hi = mean_ci(rows, boot_n)
            print(f"  {label:<9} tick ${tick:.2f}/leg: net meanR {fmt(m)} [{fmt(lo)}, {fmt(hi)}] "
                  f"n={len(rows)} ({n_thr} threshold exits)")

    hdr("VERDICTS — one per tier, graded on ARM X")
    for label, mode in C4_UNGRADED_MODES:
        what = ("ungraded C4 counts as not holding" if mode == "fails"
                else "ungraded C4 dropped from the verdict")
        tag = "VERDICT" if label == "headline" else "VERDICT-SECONDARY"
        per_tier = " · ".join(f"Tier {t} {verdicts[mode][t]}" for t in TIERS)
        print(f"{tag} ({label}: {what}): {per_tier}")
    print(f"SWEEP: {'graded (G4 PASS)' if g4_pass else 'UNCOSTABLE (G4 FAIL)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--boot-n", type=int, default=P.BOOT_N,
                    help="bootstrap resamples (default protocol.BOOT_N)")
    args = ap.parse_args(argv)
    try:
        return run(boot_n=args.boot_n)
    except GateRefusal as exc:
        print(f"\nREFUSED — {exc}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
