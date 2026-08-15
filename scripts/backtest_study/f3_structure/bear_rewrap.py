"""Bear structure substitution: is the vertical the wrong WRAPPER for a bear signal?

Bear selection is closed — B1 searched 496 subsets and found 0, the ML arm
returned 0 of 15 cells, and the log records three independent nulls. This study
does not re-open it. It holds the SIGNAL and the ENTRY fixed and changes only
the structure the signal was expressed in.

THE HYPOTHESIS, MECHANICALLY
----------------------------
A bear_put SPREAD sells the lower put. A down move in a single name arrives
with implied vol EXPANDING, and the short leg gives that expansion away — the
wrapper strips out the one thing that makes a bear position pay when it is
right. Two things in the log are what that would look like from the outside:

  - addendum 14, reproduced 08-08: "bear_put is volatility, not direction"
  - the give-back census: 82% of bear rows go green, 56% of those finish at or
    below zero, |MAE|/MFE ~ 1.25, and 124 rows peaked in +1..50% for -$77.2k

A position whose thesis is right and whose vega is short round-trips exactly
like that. If the wrapper is the problem, dropping the short leg fixes it and
NOTHING about selection changes. If it is not, bear give-back is structural and
the shipped hedge framing (<= 1/2 size, |delta| descending) is the final answer.

WHAT IS SUBSTITUTED
-------------------
  long_put   — drop the short leg. Full convexity, full vega. Costs more premium.
  wider      — short leg pushed to the lowest cached strike below it. Keeps some
               financing, recovers most of the vega.
  long_diag  — long leg rolled to the next cached expiry out, short leg left
               alone. Buys vega and time without paying naked premium.

All three price from `backtests/option_history_cache/` alone — every real-priced
spread row has BOTH legs cached (verified 165/165 bear_put, 128/128 bull_call,
85/85 bull_put), so `long_put` in particular needs no new data at all.

THE FROZEN HARNESS IS NOT EDITED
--------------------------------
`harness.py` prices nothing — it replays a mark series. So a substitution is
expressed as a SYNTHETIC ROW (new legs, new entry price, new daily marks) fed
to the same frozen `Trade`/`replay`. The exit logic, clamps and rounding that
every recorded conclusion rests on are byte-identical to the ones that produced
the baseline. `underlying.py` exists for the same reason: widen by adding code,
never by editing that module.

THE RECONSTRUCTION GATE COMES FIRST
-----------------------------------
Before any substitution is believed, the ORIGINAL structure is rebuilt from the
same cache and re-priced by the same code, and must reproduce the row's stored
`entry_option_price` and `daily_price_csv`. A row that fails is excluded from
every substitution cell and counted. Without this the study would be comparing
a substitution to a baseline priced by different code and calling the
difference an effect — quoting the gate's pass rate is what makes the rest
readable.

Read-only. Touches no config, writes no tab. Run:

    python -m scripts.backtest_study run bear_rewrap
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path, parse_history_details  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _defined_risk_bounds, _price_asof  # noqa: E402
from scripts.backtest.legs import Leg, parse_legs  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import (  # noqa: E402
    BEAR_DEBIT, cell_stats, fmt_row, hdr, prod_profile_for, sub,
)
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.lib.harness import Trade, replay  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402

# Production debit sizing, transcribed from config/backtest.yml (portfolio_value
# 50000, risk_per_trade_pct 0.02, stop_loss 0.75). Contracts matter beyond
# reporting: `harness.replay`'s dollar_stop is an ABSOLUTE $1,000 cap, so a
# substitution priced at a different premium and left at the baseline's contract
# count would be handed a different effective stop and the comparison would be
# measuring sizing, not structure.
PORTFOLIO_VALUE = 50000.0
RISK_PER_TRADE_PCT = 0.02
STOP_LOSS = 0.75

# Tolerance for the reconstruction gate, on a 4-decimal CSV round-trip.
RECON_TOL = 0.005          # entry price, absolute dollars
RECON_MARK_TOL = 0.01      # per-day mark, absolute dollars
RECON_MIN_MATCH = 0.95     # share of priced days that must agree

SUBSTITUTIONS = ("long_put", "wider", "long_diag")


# ── cache access ─────────────────────────────────────────────────────────────

_details_cache: dict[tuple, dict] = {}


def leg_details(leg: Leg) -> dict[date, dict]:
    """`{date: row}` for one contract from the shared option-history cache."""
    key = (leg.ticker, leg.expiration, leg.strike, leg.opt_type)
    if key not in _details_cache:
        path = cache_path(HISTORY_CACHE, leg.ticker, leg.expiration, leg.strike,
                          leg.opt_type)
        if not path.exists():
            _details_cache[key] = {}
        else:
            try:
                _details_cache[key] = parse_history_details(path.read_text(),
                                                            require_mark=False)
            except Exception:
                _details_cache[key] = {}
    return _details_cache[key]


def leg_series(leg: Leg) -> list[tuple[date, float]]:
    """Sorted `[(date, mark)]` for one contract — the shape `_price_asof` wants."""
    return sorted((d, r["_mark"]) for d, r in leg_details(leg).items()
                  if r.get("_mark") is not None)


def cached_puts(ticker: str, expiration: date) -> list[float]:
    """Strikes of every cached PUT on one (ticker, expiry), ascending."""
    prefix = f"{ticker.upper().strip()}_{expiration.strftime('%Y%m%d')}_"
    out = []
    for path in HISTORY_CACHE.glob(f"{prefix}*P.csv"):
        try:
            out.append(float(path.stem.split("_")[-1][:-1]))
        except ValueError:
            continue
    return sorted(out)


def cached_expiries(ticker: str, strike: float, opt_type: str) -> list[date]:
    """Expiries of every cached contract at one (ticker, strike, type), ascending."""
    cp = "C" if opt_type.strip().title() == "Call" else "P"
    out = []
    for path in HISTORY_CACHE.glob(f"{ticker.upper().strip()}_*_{strike:.2f}{cp}.csv"):
        try:
            stamp = path.stem.split("_")[1]
            out.append(date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8])))
        except (ValueError, IndexError):
            continue
    return sorted(out)


# ── pricing (mirrors simulate.py, on the barchart source only) ───────────────

def entry_date_for(legs: list[Leg], grid: list[date]) -> date | None:
    """The first grid day on which EVERY leg has a cached row.

    Production prices all legs on one entry day (the anchor's `_entry_date`,
    the first trading day after the signal under `entry_timing: next_open`).
    Requiring all legs present keeps a substitution from being filled on a
    different day from the baseline it is compared against.
    """
    for day in grid:
        if all(day in leg_details(leg) for leg in legs):
            return day
    return None


def entry_price_of(leg: Leg, day: date) -> float | None:
    """One leg's fill: that day's Open, falling back to its EOD mark.

    Mirrors `_simulate._entry_price_leg` under `entry_timing: next_open` —
    Open when it is positive (the row tags these `barchart_open`), else the
    day's mark for a zero-volume open.
    """
    row = leg_details(leg).get(day)
    if row is None:
        return None
    try:
        op = float(str(row.get("Open", "")).replace(",", "") or 0)
    except ValueError:
        op = 0.0
    if op > 0:
        return op
    mark = row.get("_mark")
    return mark if (mark and mark > 0) else None


def net_entry(legs: list[Leg], day: date) -> float | None:
    """Signed net entry price across legs, or None if any leg cannot be filled."""
    total = 0.0
    for leg in legs:
        p = entry_price_of(leg, day)
        if p is None:
            return None
        total += leg.qty * p
    return total


def net_marks(legs: list[Leg], grid: list[date]) -> list[float | None]:
    """The daily signed net value over `grid`, carry-forward priced and clamped.

    Same two rules as `_simulate` steps 2-4: `_price_asof` carries the most
    recent mark on or before each day, and `_defined_risk_bounds` clamps the net
    to the structure's arbitrage-free range. The clamp returning None for a
    single leg (`long_put`) and for multi-expiration legs (`long_diag`) is the
    correct production behaviour, not an omission.
    """
    series = {id(leg): leg_series(leg) for leg in legs}
    clamp = _defined_risk_bounds(legs)
    out: list[float | None] = []
    for day in grid:
        value = 0.0
        for leg in legs:
            p = _price_asof({"k": series[id(leg)]}, "k", day, leg.expiration)
            if p is None:
                value = None
                break
            value += leg.qty * p
        if value is not None and clamp is not None:
            value = max(clamp[0], min(clamp[1], value))
        out.append(value)
    return out


def size_contracts(entry_net: float) -> int:
    """Production debit sizing: risk budget / (premium x stop). Minimum 1."""
    if entry_net <= 0:
        return 1
    budget = PORTFOLIO_VALUE * RISK_PER_TRADE_PCT
    return max(1, int(budget / (entry_net * STOP_LOSS * 100)))


def synth_trade(rec: dict, legs: list[Leg], structure: str) -> Trade | None:
    """A frozen-harness `Trade` for a substituted structure on the same signal.

    Returns None when the substitution cannot be filled or priced. The grid is
    rebuilt by `Trade` from the legs' nearest expiry, which is why `long_diag`
    only ever rolls the LONG leg — moving the near leg would change the path
    window and the comparison would no longer be like-for-like.
    """
    base: Trade = rec["t"]
    grid = base.grid
    ed = entry_date_for(legs, grid)
    if ed is None:
        return None
    net = net_entry(legs, ed)
    if net is None or abs(net) <= 1e-9:
        return None

    marks = net_marks(legs, grid)
    if all(m is None for m in marks):
        return None

    leg_str = "\n".join(
        f"{l.ticker}:{l.expiration.isoformat()}:{l.strike:g}:"
        f"{'C' if l.opt_type == 'Call' else 'P'} {l.qty:+d}" for l in legs)
    row = {
        "signal_date": base.signal_date.isoformat(),
        "ticker": base.ticker,
        "structure": structure,
        "entry_option_price": f"{net:.4f}",
        "contracts": str(size_contracts(net)),
        "dte_entry": str(base.dte_entry),
        "legs": leg_str,
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
    }
    try:
        return Trade(row)
    except (AssertionError, ValueError, KeyError):
        return None


# ── the reconstruction gate ──────────────────────────────────────────────────

def reconstructs(rec: dict) -> tuple[bool, str]:
    """Does re-pricing the ORIGINAL structure reproduce the stored row?

    `(ok, reason)`. This is the gate the whole study rests on: a substitution is
    only interpretable against a baseline that THIS code can reproduce.
    """
    base: Trade = rec["t"]
    legs = base.legs
    if not legs:
        return False, "no_legs"
    if any(not leg_details(leg) for leg in legs):
        return False, "leg_not_cached"

    ed = entry_date_for(legs, base.grid)
    if ed is None:
        return False, "no_common_entry_day"
    net = net_entry(legs, ed)
    if net is None:
        return False, "entry_unpriced"
    if abs(net - base.entry_net) > RECON_TOL:
        return False, "entry_mismatch"

    marks = net_marks(legs, base.grid)
    both = [(a, b) for a, b in zip(marks, base.marks)
            if a is not None and b is not None]
    if not both:
        return False, "no_overlapping_marks"
    agree = sum(1 for a, b in both if abs(a - b) <= RECON_MARK_TOL)
    if agree / len(both) < RECON_MIN_MATCH:
        return False, "mark_mismatch"
    return True, "ok"


# ── the substitutions ────────────────────────────────────────────────────────

def sub_long_put(rec: dict) -> list[Leg] | None:
    """Drop every short leg. Only meaningful on a two-leg vertical."""
    legs = rec["t"].legs
    longs = [l for l in legs if l.qty > 0]
    if len(legs) < 2 or len(longs) != 1:
        return None
    return longs


def sub_wider(rec: dict) -> list[Leg] | None:
    """Push the short leg to the lowest cached strike strictly below it."""
    legs = rec["t"].legs
    longs = [l for l in legs if l.qty > 0]
    shorts = [l for l in legs if l.qty < 0]
    if len(longs) != 1 or len(shorts) != 1:
        return None
    short = shorts[0]
    if short.opt_type != "Put":
        return None
    lower = [k for k in cached_puts(short.ticker, short.expiration) if k < short.strike]
    if not lower:
        return None
    new_short = Leg(ticker=short.ticker, expiration=short.expiration,
                    strike=min(lower), opt_type=short.opt_type, qty=short.qty)
    if not leg_details(new_short):
        return None
    return [longs[0], new_short]


def sub_long_diag(rec: dict) -> list[Leg] | None:
    """Roll the LONG leg to the next cached expiry out; leave the short alone."""
    legs = rec["t"].legs
    longs = [l for l in legs if l.qty > 0]
    shorts = [l for l in legs if l.qty < 0]
    if len(longs) != 1 or len(shorts) != 1:
        return None
    long_leg = longs[0]
    later = [e for e in cached_expiries(long_leg.ticker, long_leg.strike,
                                        long_leg.opt_type)
             if e > long_leg.expiration]
    if not later:
        return None
    new_long = Leg(ticker=long_leg.ticker, expiration=min(later),
                   strike=long_leg.strike, opt_type=long_leg.opt_type,
                   qty=long_leg.qty)
    if not leg_details(new_long):
        return None
    return [new_long, shorts[0]]


BUILDERS = {"long_put": sub_long_put, "wider": sub_wider, "long_diag": sub_long_diag}


# ── replay ───────────────────────────────────────────────────────────────────

def replay_rec(rec: dict, t: Trade) -> dict:
    """Replay one trade on the SHIPPED production profile for its regime cell.

    `prod_profile_for` is imported from `bear_giveback` rather than rebuilt: its
    base -> structure_exit -> regime_exit merge is the one ARM P validated
    against the real book, and a second transcription of the same YAML is how
    the 08-11 close-out ended up quoting a 3x overstated delta.
    """
    out = replay(t, **prod_profile_for(rec, 0.50, True))
    r = out["pnl_pct"]
    return dict(R=r, R_dol=t.dollars(r), exit_reason=out["exit_reason"],
                days_held=out["days_held"])


def build_arm(bear: list[dict]) -> tuple[dict, dict]:
    """`({label: [row]}, gate_diag)` — the baseline and every substitution.

    Rows carry `date`/`R`/`R_dol` so `protocol.py` can consume them directly,
    plus the stored `mfe`/`mae` for the give-back read. MFE/MAE are the
    BASELINE's on baseline rows only; a substitution's path is different, so its
    MFE/MAE are recomputed off its own marks.
    """
    gate = Counter()
    by_label: dict[str, list[dict]] = defaultdict(list)

    for rec in bear:
        ok, why = reconstructs(rec)
        gate[why] += 1
        if not ok:
            continue

        base_out = replay_rec(rec, rec["t"])
        by_label["baseline"].append(dict(
            date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
            source=rec["source"], tier=rec["tier"], mech_cell=rec["mech_cell"],
            mfe=rec["mfe"], mae=rec["mae"], key=id(rec), **base_out))

        for label in SUBSTITUTIONS:
            legs = BUILDERS[label](rec)
            if legs is None:
                gate[f"skip_{label}"] += 1
                continue
            t = synth_trade(rec, legs, label)
            if t is None:
                gate[f"unpriced_{label}"] += 1
                continue
            out = replay_rec(rec, t)
            pnls = [t.pnl_of(m) for m in t.marks if m is not None]
            by_label[label].append(dict(
                date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
                source=rec["source"], tier=rec["tier"], mech_cell=rec["mech_cell"],
                mfe=max(pnls) if pnls else None, mae=min(pnls) if pnls else None,
                key=id(rec), **out))
    return by_label, gate


# ── reporting ────────────────────────────────────────────────────────────────

def report_gate(bear: list[dict], gate: Counter) -> None:
    hdr("GATE — can this code reproduce the stored rows it is about to modify?")
    print("""  Every substitution below is a DIFFERENCE against the baseline replay.
  If the baseline cannot be rebuilt from the cache by the same pricing code,
  that difference is measuring the re-pricer, not the structure. Rows that
  fail are dropped from every cell and counted here.""")
    total = len(bear)
    ok = gate["ok"]
    print(f"\n  bear debit rows            {total:>5}")
    print(f"  reconstructed              {ok:>5}  ({ok / total:.1%})" if total else "")
    for reason, n in sorted(gate.items()):
        if reason == "ok" or reason.startswith(("skip_", "unpriced_")):
            continue
        print(f"    failed: {reason:<24} {n:>5}")
    sub("substitution availability")
    for label in SUBSTITUTIONS:
        print(f"  {label:<12} not-applicable {gate[f'skip_{label}']:>4}   "
              f"unpriceable {gate[f'unpriced_{label}']:>4}")


def report_cells(by_label: dict) -> None:
    hdr("ARM W — the wrapper, on the SHIPPED production exit")
    print("""  Same signal, same entry day, same exit rules. Only the structure differs.
  `gb` = |mean MAE| / mean MFE (path asymmetry), `cap` = mean R / mean MFE
  (how much of the shown profit the exit banked). A wrapper fix should raise
  cap and drop gb; a selection fix would raise MFE, and nothing here can.""")
    print()
    for label in ("baseline",) + SUBSTITUTIONS:
        rows = by_label.get(label) or []
        if rows:
            print(fmt_row(label, cell_stats(rows), width=12))

    for label in SUBSTITUTIONS:
        rows = by_label.get(label) or []
        if not rows:
            continue
        sub(f"{label} — paired against baseline on the same rows")
        keys = {r["key"] for r in rows}
        base = {r["key"]: r for r in by_label["baseline"] if r["key"] in keys}
        paired = [dict(date=r["date"], a=r["R"], b=base[r["key"]]["R"],
                       a_dol=r["R_dol"], b_dol=base[r["key"]]["R_dol"])
                  for r in rows if r["key"] in base]
        if not paired:
            continue
        d_mean = statistics.fmean(p["a"] - p["b"] for p in paired)
        lo, hi = P.boot_ci_paired_by_date(paired, "a", "b")
        d_dol = sum(p["a_dol"] - p["b_dol"] for p in paired)
        print(f"  n={len(paired)}  dR {d_mean:+.3f}  CI [{lo:+.3f}, {hi:+.3f}]  "
              f"d$ {d_dol:+,.0f}")
        mean_g, share, min_g, folds = P.loo_by_date(
            paired, lambda r: r["a"], lambda r: r["b"])
        print(f"  LOO-by-date: mean {mean_g:+.3f}  share+ {share:.0%}  "
              f"MIN {min_g:+.3f}  ({folds} folds)")
        for cut, rs in P.window_cuts(paired).items():
            if rs:
                print(f"    {cut:<16} n={len(rs):>4}  "
                      f"dR {statistics.fmean(r['a'] - r['b'] for r in rs):+.3f}")
        years = {y: statistics.fmean(r["a"] - r["b"] for r in rs)
                 for y, rs in P.by_year(paired).items()}
        print("    by year: " + "  ".join(f"{y} {v:+.3f}" for y, v in years.items()))
        mix = Counter(r["exit_reason"] for r in rows)
        print("    exits: " + "  ".join(f"{k}={v}" for k, v in mix.most_common()))


def report_criteria(by_label: dict) -> None:
    """The pre-registered ship gates, evaluated one by one per substitution.

    Printed as a checklist rather than prose because the log's failure mode is
    a headline that clears three gates and quietly misses a fourth. Sign
    stability across years is the gate that has killed the most candidates here
    (four recorded recurrences of a single window carrying an effect), and the
    pricing-tier split is the one that has most often turned a dollar headline
    into a composition artifact.
    """
    hdr("CRITERIA — the pre-registered gates, per substitution")
    for label in SUBSTITUTIONS:
        rows = by_label.get(label) or []
        if not rows:
            continue
        keys = {r["key"] for r in rows}
        base = {r["key"]: r for r in by_label["baseline"] if r["key"] in keys}
        paired = [dict(date=r["date"], a=r["R"], b=base[r["key"]]["R"],
                       a_dol=r["R_dol"], b_dol=base[r["key"]]["R_dol"],
                       src=r["source"]) for r in rows if r["key"] in base]
        if not paired:
            continue
        sub(label)
        lo, hi = P.boot_ci_paired_by_date(paired, "a", "b")
        print(f"  [{'PASS' if lo > 0 else 'FAIL'}] CI excludes zero          "
              f"dR {statistics.fmean(p['a'] - p['b'] for p in paired):+.3f} "
              f"CI [{lo:+.3f}, {hi:+.3f}]")

        _, share, min_g, folds = P.loo_by_date(paired, lambda r: r["a"],
                                               lambda r: r["b"])
        print(f"  [{'PASS' if min_g > 0 else 'FAIL'}] every LOO fold positive  "
              f"MIN {min_g:+.3f} over {folds} folds (share+ {share:.0%})")

        cuts = {k: statistics.fmean(r["a"] - r["b"] for r in rs)
                for k, rs in P.window_cuts(paired).items() if rs and k != "ALL"}
        ok_cuts = all(v > 0 for v in cuts.values())
        print(f"  [{'PASS' if ok_cuts else 'FAIL'}] both ex-window cuts       "
              + "  ".join(f"{k} {v:+.3f}" for k, v in cuts.items()))

        years = {y: statistics.fmean(r["a"] - r["b"] for r in rs)
                 for y, rs in P.by_year(paired).items()}
        ok_years = all(v > 0 for v in years.values())
        print(f"  [{'PASS' if ok_years else 'FAIL'}] sign-stable every year    "
              + "  ".join(f"{y} {v:+.3f}" for y, v in years.items()))

        tiers = {}
        for src in ("real", "tweak"):
            rs = [p for p in paired if p["src"] == src]
            if rs:
                tiers[src] = (statistics.fmean(p["a"] - p["b"] for p in rs),
                              sum(p["a_dol"] - p["b_dol"] for p in rs), len(rs))
        ok_tiers = all(v[0] > 0 for v in tiers.values())
        print(f"  [{'PASS' if ok_tiers else 'FAIL'}] right-signed both tiers   "
              + "  ".join(f"{k} n={v[2]} dR {v[0]:+.3f} d$ {v[1]:+,.0f}"
                          for k, v in tiers.items()))
        if ok_tiers and len({v[1] > 0 for v in tiers.values()}) > 1:
            print("        NOTE: the tiers agree on R but DISAGREE on dollars — a "
                  "substitution\n              changes premium, hence contracts, so $ "
                  "carries a sizing effect\n              that R does not. Quote R.")


def report_portfolio(by_label: dict, recs: list[dict]) -> None:
    """P1 and P2: does the sleeve pay on the dates the deployed book hurts?"""
    hdr("ARM P — portfolio contribution (P1 worst-decile, P2 correlation)")
    print("""  The criterion is NOT standalone expectancy — that was answered and
  closed. These are the D2 tests: what the sleeve does on the deployed
  book's worst dates, and whether it moves with the sleeve or against it.
  D2's shipped bear read is +0.252 on worst-decile dates, corr -0.132.""")

    ladder = P.top_k_per_day(recs, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)
    if not ladder:
        print("\n  no deployed rows — ladder replay empty")
        return
    by_date: dict[str, list[float]] = defaultdict(list)
    for r in ladder:
        if r.get("R") is not None:
            by_date[r["date"]].append(float(r["R"]))
    sleeve_daily = {d: statistics.fmean(v) for d, v in by_date.items() if v}
    if not sleeve_daily:
        print("\n  no priced ladder rows")
        return
    cutoff = sorted(sleeve_daily.values())[max(0, len(sleeve_daily) // 10 - 1)]
    worst = {d for d, v in sleeve_daily.items() if v <= cutoff}
    print(f"\n  deployed ladder: {len(ladder)} rows / {len(sleeve_daily)} dates; "
          f"worst decile = {len(worst)} dates (mean R <= {cutoff:+.3f})")

    for label in ("baseline",) + SUBSTITUTIONS:
        rows = by_label.get(label) or []
        if not rows:
            continue
        sub(f"{label}")
        on_worst = [r for r in rows if r["date"] in worst]
        if on_worst:
            lo, hi = P.boot_ci_by_date(on_worst, "R")
            m = statistics.fmean(r["R"] for r in on_worst)
            verdict = "MET" if lo > 0 else "not met"
            print(f"  P1 worst-decile: n={len(on_worst):>3}  meanR {m:+.3f}  "
                  f"CI [{lo:+.3f}, {hi:+.3f}]  ${sum(r['R_dol'] for r in on_worst):+,.0f}"
                  f"   -> {verdict}")
        else:
            print("  P1 worst-decile: no rows on those dates")

        paired = [(sleeve_daily[d], statistics.fmean(
                        [r["R"] for r in rows if r["date"] == d]))
                  for d in sorted({r["date"] for r in rows} & set(sleeve_daily))]
        if len(paired) >= 8:
            corr = statistics.correlation([a for a, _ in paired],
                                          [b for _, b in paired])
            print(f"  P2 correlation with deployed sleeve: {corr:+.3f} "
                  f"over {len(paired)} shared dates   "
                  f"-> {'MET' if corr <= 0 else 'not met'}")
            per_year: dict[str, list] = defaultdict(list)
            for d in sorted({r["date"] for r in rows} & set(sleeve_daily)):
                per_year[d[:4]].append((sleeve_daily[d], statistics.fmean(
                    [r["R"] for r in rows if r["date"] == d])))
            parts = []
            for y, pts in sorted(per_year.items()):
                if len(pts) >= 8:
                    c = statistics.correlation([a for a, _ in pts], [b for _, b in pts])
                    parts.append(f"{y} {c:+.3f}")
            if parts:
                print("     by year: " + "  ".join(parts))
        else:
            print("  P2 correlation: too few shared dates")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", default="GWCP", help="subset of G/W/C/P to run")
    a = ap.parse_args(argv)

    recs, diag = load_book(include_bs=False)
    print(f"book: {len(recs)} rows  counts_by_source={diag['counts_by_source']}  "
          f"(bs excluded)")
    bear = [r for r in recs if r["structure"] in BEAR_DEBIT and not r["credit"]]
    print(f"bear debit rows: {len(bear)}  "
          f"({Counter(r['source'] for r in bear)})")

    by_label, gate = build_arm(bear)

    if "G" in a.arms:
        report_gate(bear, gate)
    if "W" in a.arms:
        report_cells(by_label)
    if "C" in a.arms:
        report_criteria(by_label)
    if "P" in a.arms:
        report_portfolio(by_label, recs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
