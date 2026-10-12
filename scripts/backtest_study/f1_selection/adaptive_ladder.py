"""adaptive_ladder — does re-choosing the selection rule from trailing results beat the shipped ladder?

REGISTERED 2026-10-12, accepted by default the same day:
research/pre-registrations/f1_selection/adaptive_ladder.md. Every constant,
menu rule and verdict word below is that file's. Read it before changing
anything here.

WHY IT EXISTS
-------------
The operator wants the deploy rule to adapt to current conditions. With a
short book the honest way to do that is to make the ADAPTATION PROCEDURE the
strategy and grade it walk-forward: a fixed menu of selection rules, and a
fixed procedure that re-picks one of them from trailing realized results.

WHAT IT COMPUTES
----------------
Population. `load_book()` at its defaults, through `dip_buy.prepare`'s rules:
non-veto rows with a stored R, a trusted fill and a dip label. R is the stored
`realized_pnl_pct` (net of `cost_total` on v4; v3 carries no cost columns, so
v3 R is gross). Tiers come from `mapping.ladder_tier`, via `dip_buy.tier_of`.

Known date. A position's outcome is known at the close of its exit session,
`t.grid[days_held - 1]` (the grid `mtm_curve` and `account_sim` use; a
deferred fill is already inside `days_held`). A row still open at the data
end is never known. On a rebalance date `Rb` the adapter may read a position
only when its known date is strictly before `Rb`.

Menu. Six fixed rules, each picking up to 3 positions per signal date:

    M0  Tier A/B, A first, score_total descending   (the shipped card)
    M1  Tier A/B, A first, score_total ascending
    M2  Tier A/B, A first, random order within tier (expected value, exact)
    M3  M1 on dip dates only; nothing on above dates
    M4  M1, but on above dates Tier A only
    M5  non-veto bull_call_spread, tier-blind, score_total ascending

A rule's book is a list of (position, weight) per date; weight is 1 for a
pick and the pick probability under M2.

Adapter. At each rebalance date every rule is scored on its own trailing
known positions: the weighted meanR, a date-clustered standard error, and
n = summed weight. The incumbent (M0 at the start) is replaced by the
challenger with the highest trailing mean among those with n >= MIN_N and a
score above the incumbent's trailing mean (lower bound under the default
margin `lb`, plain mean under `mean`). An incumbent with no trailing position
scores 0, the value of cash.

Graded. Per signal date, R per budget slot: the summed R of the day's picks
divided by 3, so an empty slot or a sat-out date earns 0. The statistic is
the mean over graded dates of adapter minus M0. CI: calendar-month blocks
resampled with replacement, 10,000 draws. First 6 months not graded; dates
on or after `era.SEAL_START` are the forward read.

    ADAPTS  CI excludes 0, positive
    HURTS   CI excludes 0, negative
    NULL    CI spans 0

Forward: STILL-OPEN until 30 forward signal dates and 60 M0 positions.

Nothing ships. Run:

    python -m scripts.backtest_study run adaptive_ladder
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import MechLabeler  # noqa: E402
from scripts.backtest_study.f1_selection import dip_buy as DB  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as pbo_mod  # noqa: E402
from scripts.backtest_study.lib.book import MECH_TABLE_CSV, load_book  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/adaptive_ladder.md"
ACCEPTED = "2026-10-12"

# --- registered constants ------------------------------------------------------
MENU = ("M0", "M1", "M2", "M3", "M4", "M5")
MENU_TEXT = {
    "M0": "Tier A/B, score_total descending (shipped)",
    "M1": "Tier A/B, score_total ascending",
    "M2": "Tier A/B, random within tier (expected value)",
    "M3": "M1 on dip dates only",
    "M4": "M1; above dates Tier A only",
    "M5": "bull_call_spread only, tier-blind, ascending",
}
START_RULE = "M0"
TOP_K = 3
CADENCES = ("monthly", "weekly")
WINDOWS = (120, 60, None)          # calendar days on the known date; None = expanding
MARGINS = ("lb", "mean")
MIN_N = 20
Z = 1.96
DEFAULT = ("monthly", 120, "lb")
WARMUP_MONTHS = 6
BOOT_N = 10_000
SEED = 20260811
PBO_S = 16
STRESS = (("2025-03-01", "2025-04-30"), ("2026-02-01", "2026-04-30"))
MIN_FWD_DATES = 30
MIN_FWD_POS = 60
FORWARD_ERA = "v4"
REPLICATION_ERA = "v3"

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}


# ════════════════════════════════════════════════════════════════════════════
# Population
# ════════════════════════════════════════════════════════════════════════════

def known_date(rec) -> str | None:
    """ISO date the outcome is known (exit session), or None if still open."""
    row = rec["t"].row if rec.get("t") is not None else {}
    if (row.get("path_status") or "").strip() == "open_at_data_end":
        return None
    dh = rec.get("days_held")
    grid = rec["t"].grid
    if dh is None or dh < 1 or dh > len(grid):
        return None
    return grid[dh - 1].isoformat()


def prepare(recs, labeler) -> tuple[list[dict], Counter]:
    """`dip_buy.prepare`'s population, plus each row's known date."""
    rows, counts = DB.prepare(recs, labeler)
    # dip_buy.prepare keeps order and drops whole records, so re-walk to attach.
    keep = []
    for r in recs:
        if r.get("R") is None or not r.get("fill_trusted", True):
            continue
        if DB.tier_of(r) == "VETO" or DB.dip_label(labeler, r["date"]) is None:
            continue
        keep.append(r)
    assert len(keep) == len(rows)
    for row, rec in zip(rows, keep):
        row["known"] = known_date(rec)
        if row["known"] is None:
            counts["open_at_data_end_kept_never_known"] += 1
    return rows, counts


# ════════════════════════════════════════════════════════════════════════════
# Menu
# ════════════════════════════════════════════════════════════════════════════

def _ranked(rows, tiebreak):
    return sorted(rows, key=DB.rank_key(tiebreak))


def _expected_random(rows, k=TOP_K):
    """(row, pick probability) under a uniform random order within tier, A first."""
    out, slots = [], k
    for tier in ("A", "B"):
        pool = [r for r in rows if r["tier"] == tier]
        if not pool or slots == 0:
            continue
        if len(pool) <= slots:
            out += [(r, 1.0) for r in pool]
            slots -= len(pool)
        else:
            out += [(r, slots / len(pool)) for r in pool]
            slots = 0
    return out


def select(day_rows, rule: str, k: int = TOP_K):
    """[(row, weight)] one rule deploys on one signal date."""
    ab = [r for r in day_rows if r["tier"] in ("A", "B")]
    dip = day_rows[0]["dip"] if day_rows else None
    if rule == "M0":
        return [(r, 1.0) for r in _ranked(ab, "desc")[:k]]
    if rule == "M1":
        return [(r, 1.0) for r in _ranked(ab, "asc")[:k]]
    if rule == "M2":
        return _expected_random(ab, k)
    if rule == "M3":
        if dip != DB.BELOW:
            return []
        return [(r, 1.0) for r in _ranked(ab, "asc")[:k]]
    if rule == "M4":
        pool = ab if dip == DB.BELOW else [r for r in ab if r["tier"] == "A"]
        return [(r, 1.0) for r in _ranked(pool, "asc")[:k]]
    if rule == "M5":
        bcs = [r for r in day_rows if r["structure"] == "bull_call_spread"]
        s = sorted(bcs, key=lambda r: (r["score"] is None,
                                       r["score"] if r["score"] is not None else 0.0))
        return [(r, 1.0) for r in s[:k]]
    raise ValueError(rule)


def by_date(rows) -> dict[str, list]:
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(r["date"], []).append(r)
    return dict(sorted(out.items()))


def menu_books(days: dict) -> dict[str, dict[str, list]]:
    return {m: {d: select(rs, m) for d, rs in days.items()} for m in MENU}


# ════════════════════════════════════════════════════════════════════════════
# Adapter
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Score:
    mean: float
    lb: float
    n: float


def _shift_days(d: str, days: int) -> str:
    return date.fromordinal(date.fromisoformat(d).toordinal() - days).isoformat()


def trailing_score(book: dict[str, list], rb: str, window: int | None) -> Score:
    """Weighted meanR of the positions whose outcome was known before `rb`.

    A position enters only when its known date is strictly before `rb` and,
    with a window, on or after `rb - window` days. The standard error is
    clustered on signal date.
    """
    lo = _shift_days(rb, window) if window is not None else ""
    sums: dict[str, list[float]] = {}
    for d, picks in book.items():
        if d >= rb:
            break
        for r, w in picks:
            kd = r["known"]
            if kd is None or kd >= rb or kd < lo:
                continue
            a = sums.setdefault(d, [0.0, 0.0])
            a[0] += w * r["R"]
            a[1] += w
    if not sums:
        return Score(float("nan"), float("nan"), 0.0)
    s = np.array([v[0] for v in sums.values()])
    c = np.array([v[1] for v in sums.values()])
    n = float(c.sum())
    mean = float(s.sum() / n)
    g = len(s)
    if g < 2:
        return Score(mean, float("-inf"), n)
    se = math.sqrt(float(((s - mean * c) ** 2).sum()) * g / (g - 1)) / n
    return Score(mean, mean - Z * se, n)


def choose(incumbent: str, scores: dict[str, Score], margin: str,
           min_n: float = MIN_N) -> str:
    """The rule held after a rebalance. Ties go to menu order."""
    inc = scores[incumbent]
    bar = inc.mean if inc.n > 0 else 0.0
    best, best_mean = incumbent, None
    for m in MENU:
        if m == incumbent:
            continue
        s = scores[m]
        if s.n < min_n:
            continue
        test = s.lb if margin == "lb" else s.mean
        if not (test > bar):
            continue
        if best_mean is None or s.mean > best_mean:
            best, best_mean = m, s.mean
    return best


def rebalance_dates(dates, cadence: str) -> list[str]:
    seen, out = set(), []
    for d in dates:
        dd = date.fromisoformat(d)
        if cadence == "monthly":
            key = (dd.year, dd.month)
        elif cadence == "weekly":
            key = tuple(dd.isocalendar()[:2])
        else:
            raise ValueError(cadence)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def run_adapter(books: dict[str, dict[str, list]], dates: list[str], cadence: str,
                window: int | None, margin: str, min_n: float = MIN_N,
                start: str = START_RULE):
    """(rule per date, [(rebalance date, from, to)]) for one adapter config."""
    rbs = set(rebalance_dates(dates, cadence))
    inc, held, switches = start, {}, []
    for d in dates:
        if d in rbs:
            scores = {m: trailing_score(books[m], d, window) for m in MENU}
            new = choose(inc, scores, margin, min_n)
            if new != inc:
                switches.append((d, inc, new))
                inc = new
        held[d] = inc
    return held, switches


def adapter_book(books, held: dict[str, str]) -> dict[str, list]:
    return {d: books[m][d] for d, m in held.items()}


# ════════════════════════════════════════════════════════════════════════════
# Statistics
# ════════════════════════════════════════════════════════════════════════════

def slot_r(book: dict[str, list], dates) -> np.ndarray:
    """Per date: summed weighted R over the 3 budget slots. Empty slot = 0."""
    return np.array([sum(w * r["R"] for r, w in book.get(d, [])) / TOP_K for d in dates])


def date_total(book, dates) -> np.ndarray:
    return np.array([sum(w * r["R"] for r, w in book.get(d, [])) for d in dates])


def positions(book, dates) -> float:
    return float(sum(w for d in dates for _r, w in book.get(d, [])))


def pooled_mean(book, dates) -> float:
    n = positions(book, dates)
    return float(date_total(book, dates).sum() / n) if n > 0 else float("nan")


def max_dd(series: np.ndarray) -> float:
    cum = np.concatenate([[0.0], np.cumsum(series)])
    return float((np.maximum.accumulate(cum) - cum).max())


def warmup_end(dates) -> str:
    d0 = date.fromisoformat(dates[0])
    m = d0.month - 1 + WARMUP_MONTHS
    return date(d0.year + m // 12, m % 12 + 1, 1).isoformat()


def in_stress(d: str) -> bool:
    return any(a <= d <= b for a, b in STRESS)


def boot_month_mean(diff: np.ndarray, dates, n: int = BOOT_N, seed: int = SEED):
    """(mean, lo, hi) of the per-date values, calendar-month blocks resampled."""
    if len(diff) == 0:
        return (float("nan"),) * 3
    point = float(diff.mean())
    months: dict[str, list[float]] = {}
    for d, v in zip(dates, diff):
        months.setdefault(d[:7], []).append(v)
    s = np.array([sum(v) for v in months.values()])
    c = np.array([len(v) for v in months.values()], dtype=float)
    if len(s) < 2:
        return (point, float("nan"), float("nan"))
    idx = np.random.default_rng(seed).integers(0, len(s), (n, len(s)))
    m = s[idx].sum(1) / c[idx].sum(1)
    lo, hi = np.percentile(m, [2.5, 97.5])
    return (point, float(lo), float(hi))


def verdict(lo: float, hi: float) -> str:
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "NULL"
    if lo > 0:
        return "ADAPTS"
    if hi < 0:
        return "HURTS"
    return "NULL"


def forward_verdict(n_dates: int, n_pos: float, lo: float, hi: float) -> str:
    if n_dates < MIN_FWD_DATES or n_pos < MIN_FWD_POS:
        return "STILL-OPEN"
    return verdict(lo, hi)


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def _f(x, fmt="+.3f"):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def cfg_name(cfg) -> str:
    cad, win, mar = cfg
    return f"{cad}/{'exp' if win is None else win}/{mar}"


def grid_configs():
    return [(c, w, m) for c in CADENCES for w in WINDOWS for m in MARGINS]


def book_line(label, book, dates, base=None):
    sr = slot_r(book, dates)
    tot = date_total(book, dates)
    line = (f"  {label:<26} pos={positions(book, dates):7.1f}  meanR={_f(pooled_mean(book, dates))}  "
            f"slotR/date={_f(float(sr.mean()) if len(sr) else float('nan'), '+.4f')}  "
            f"totalR={_f(float(tot.sum()), '+.1f')}  maxDD={_f(max_dd(tot), '.1f')}")
    if base is not None:
        d, lo, hi = boot_month_mean(sr - slot_r(base, dates), dates)
        line += f"  vs M0 {_f(d, '+.4f')} [{_f(lo, '+.4f')}, {_f(hi, '+.4f')}]"
    return line


def time_in_rule(held, dates) -> str:
    c = Counter(held[d] for d in dates)
    return "  ".join(f"{m} {c[m] / len(dates) * 100:.0f}%" for m in MENU if c[m]) if dates else "—"


def walk(rows, label, graded_until=None, quiet=False):
    """Run the whole procedure on one era. Returns a dict of the pieces."""
    days = by_date(rows)
    dates = list(days)
    books = menu_books(days)
    w_end = warmup_end(dates)
    graded = [d for d in dates if d >= w_end and (graded_until is None or d < graded_until)]
    configs = grid_configs()
    runs = {cfg: run_adapter(books, dates, *cfg) for cfg in configs}
    return dict(days=days, dates=dates, books=books, warmup_end=w_end, graded=graded,
                runs=runs, label=label)


def print_walk(W, title: str, graded_token: bool):
    books, graded, runs = W["books"], W["graded"], W["runs"]
    held, switches = runs[DEFAULT]
    ad = adapter_book(books, held)
    m0 = books["M0"]
    print(f"\n-- {title}")
    print(f"  signal dates {len(W['dates'])} ({W['dates'][0]} .. {W['dates'][-1]}); warm-up ends "
          f"{W['warmup_end']}; graded dates {len(graded)}"
          + (f" ({graded[0]} .. {graded[-1]})" if graded else ""))
    if not graded:
        print("  no graded dates")
        return None
    print(f"  default adapter {cfg_name(DEFAULT)}, min n {MIN_N}, start {START_RULE}")
    print(book_line("ADAPTER (default)", ad, graded, base=m0))
    for m in MENU:
        print(book_line(f"{m} {MENU_TEXT[m][:22]}", books[m], graded,
                        base=m0 if m != "M0" else None))
    means = {m: float(slot_r(books[m], graded).mean()) for m in MENU}
    oracle = max(MENU, key=lambda m: means[m])
    print(f"  ORACLE (hindsight, best static rule on these graded dates): {oracle} "
          f"slotR/date={_f(means[oracle], '+.4f')}")
    g_sw = [s for s in switches if s[0] >= graded[0] and s[0] <= graded[-1]]
    print(f"  switches: {len(switches)} in all, {len(g_sw)} inside the graded dates")
    for s in switches:
        print(f"    {s[0]}  {s[1]} -> {s[2]}")
    print(f"  time in rule, graded dates: {time_in_rule(held, graded)}")
    diff = slot_r(ad, graded) - slot_r(m0, graded)
    d, lo, hi = boot_month_mean(diff, graded)
    v = verdict(lo, hi)
    tag = "graded" if graded_token else "descriptive, not graded"
    print(f"  >>> adapter - M0, slotR per date: {_f(d, '+.4f')}  CI95 [{_f(lo, '+.4f')}, "
          f"{_f(hi, '+.4f')}]  {v} ({tag}) <<<")
    return dict(diff=d, lo=lo, hi=hi, verdict=v, oracle=oracle, switches=len(switches))


def grid_block(W, title):
    books, graded, runs = W["books"], W["graded"], W["runs"]
    if not graded:
        return
    m0 = slot_r(books["M0"], graded)
    print(f"\n-- {title}: adapter parameter grid (printed, only {cfg_name(DEFAULT)} is graded)")
    for cfg in grid_configs():
        held, sw = runs[cfg]
        sr = slot_r(adapter_book(books, held), graded)
        d, lo, hi = boot_month_mean(sr - m0, graded)
        print(f"  {cfg_name(cfg):<20} vs M0 {_f(d, '+.4f')} [{_f(lo, '+.4f')}, {_f(hi, '+.4f')}]  "
              f"switches {len(sw):2d}  {time_in_rule(held, graded)}")


def cut_block(W, title):
    """Ex-stress and per-year rows of the default adapter against M0."""
    books, graded = W["books"], W["graded"]
    if not graded:
        return
    held, _ = W["runs"][DEFAULT]
    ad = adapter_book(books, held)
    print(f"\n-- {title}: default adapter vs M0 by cut (not graded)")
    cuts = [("all graded dates", graded),
            ("ex Mar-Apr 2025, Feb-Apr 2026", [d for d in graded if not in_stress(d)])]
    for y in sorted({d[:4] for d in graded}):
        cuts.append((f"year {y}", [d for d in graded if d[:4] == y]))
    for lbl, ds in cuts:
        if not ds:
            continue
        diff = slot_r(ad, ds) - slot_r(books["M0"], ds)
        d, lo, hi = boot_month_mean(diff, ds)
        print(f"  {lbl:<32} dates={len(ds):3d}  adapter meanR={_f(pooled_mean(ad, ds))}  "
              f"M0 meanR={_f(pooled_mean(books['M0'], ds))}  diff/date={_f(d, '+.4f')} "
              f"[{_f(lo, '+.4f')}, {_f(hi, '+.4f')}]  {verdict(lo, hi)}")


def pbo_block(W, title):
    books, graded, runs = W["books"], W["graded"], W["runs"]
    cols, names = [], []
    for m in MENU:
        cols.append(slot_r(books[m], graded))
        names.append(m)
    for cfg in grid_configs():
        cols.append(slot_r(adapter_book(books, runs[cfg][0]), graded))
        names.append("A:" + cfg_name(cfg))
    M = np.column_stack(cols)
    trim = M.shape[0] % PBO_S
    M = M[trim:]
    print(f"\n-- {title}: PBO, CSCV over {len(names)} configs ({len(MENU)} static rules + "
          f"{len(grid_configs())} adapter configs)")
    if M.shape[0] < PBO_S:
        print("  too few graded dates")
        return None
    res = pbo_mod.cscv(M, S=PBO_S)
    share = res.selection_share()
    top = sorted(range(len(names)), key=lambda i: -share[i])[:4]
    print(f"  T={M.shape[0]} graded dates (earliest {trim} trimmed so S={PBO_S} divides T), "
          f"combinations {res.n_combinations}, metric = summed slotR")
    print(f"  PBO={res.pbo:.3f}  prob_loss={_f(res.prob_loss, '.3f')}  degradation slope="
          f"{_f(res.slope, '+.2f')}")
    print("  most-often IS-best: " + ", ".join(f"{names[i]} {share[i]:.2f}" for i in top))
    return res.pbo


def main() -> int:
    seal_start = era_mod.SEAL_START
    labeler = MechLabeler.from_csv(MECH_TABLE_CSV)
    print("adaptive_ladder — walk-forward choice among six selection rules, against the shipped ladder")
    print(f"registration: {REGISTRATION} (accepted by default {ACCEPTED})")
    print("menu: " + "; ".join(f"{m} {MENU_TEXT[m]}" for m in MENU))
    print(f"default adapter: {cfg_name(DEFAULT)}; switch needs n >= {MIN_N} and a score above "
          f"the incumbent's trailing mean; warm-up {WARMUP_MONTHS} months")
    print("known date: exit session, strictly before the rebalance date; open rows never known")
    print(f"forward: signal dates >= {seal_start} (lib/era.py SEAL_START); seal lifted: "
          f"{era_mod.SEAL_LIFTED or 'no'}")

    recs, diag = load_book()
    rows, counts = prepare(recs, labeler)
    print(f"\nera {diag['era']}: {len(rows)} non-veto labelled rows; dropped/flagged {dict(counts)}")
    graded_era = diag["era"] == FORWARD_ERA
    if diag["era"] == "v3":
        print("v3 carries no cost columns: R is gross of costs")

    print("\n" + "=" * 78)
    print("WALK-FORWARD, IN-SAMPLE DATES — the graded walk-forward")
    print("=" * 78)
    print("Caveat: M1, M3, M4 and M5 were built from the 2026-10-12 exploratory read of these "
          "same dates, so the menu itself is hindsight. The clean read is the forward one.")
    W = walk(rows, diag["era"], graded_until=seal_start)
    res = print_walk(W, f"{diag['era']}, default adapter", graded_era)
    grid_block(W, diag["era"])
    cut_block(W, diag["era"])
    pbo_v = pbo_block(W, diag["era"])

    if diag["era"] != REPLICATION_ERA:
        print("\n" + "=" * 78)
        print(f"REPLICATION, {REPLICATION_ERA} — descriptive, not graded; R gross of costs")
        print("=" * 78)
        try:
            recs3, diag3 = load_book(era=REPLICATION_ERA)
        except SystemExit as exc:
            print(f"{REPLICATION_ERA} not loaded: era refusal, exit {exc.code}")
        else:
            rows3, counts3 = prepare(recs3, labeler)
            print(f"era {diag3['era']}: {len(rows3)} rows; dropped/flagged {dict(counts3)}")
            W3 = walk(rows3, REPLICATION_ERA, graded_until=seal_start)
            print_walk(W3, f"{REPLICATION_ERA}, default adapter", False)
            grid_block(W3, REPLICATION_ERA)
            cut_block(W3, REPLICATION_ERA)
            pbo_block(W3, REPLICATION_ERA)

    print("\n" + "=" * 78)
    print("FORWARD — signal dates on or after the seal start")
    print("=" * 78)
    Wf = walk(rows, diag["era"])
    fwd = [d for d in Wf["dates"] if d >= seal_start] if graded_era else []
    held, _ = Wf["runs"][DEFAULT]
    if fwd:
        ad = adapter_book(Wf["books"], held)
        diff = slot_r(ad, fwd) - slot_r(Wf["books"]["M0"], fwd)
        fd, flo, fhi = boot_month_mean(diff, fwd)
    else:
        fd = flo = fhi = float("nan")
    npos = positions(Wf["books"]["M0"], fwd)
    fv = forward_verdict(len(fwd), npos, flo, fhi)
    seal = diag.get("seal", {})
    if not era_mod.SEAL_LIFTED:
        print(f"SEALED: load_book withheld {seal.get('rows', 0)} rows on {seal.get('dates', 0)} "
              f"signal dates >= {seal_start}. This study is not a named reader.")
    print(f"  forward dates {len(fwd)} of {MIN_FWD_DATES}; M0 positions {npos:.0f} of {MIN_FWD_POS}")
    print(f"  rule held entering the forward window: {held[Wf['dates'][-1]] if Wf['dates'] else '—'}")
    print(f"  adapter - M0, slotR per date: {_f(fd, '+.4f')}  CI95 [{_f(flo, '+.4f')}, {_f(fhi, '+.4f')}]")

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    if res is not None and graded_era:
        print(f"  >>> adaptive_ladder WALK-FORWARD (in-sample dates, {diag['era']}, adapter - M0): "
              f"{res['verdict']} <<<")
        print(f"  oracle (hindsight): {res['oracle']}; switches {res['switches']}; PBO {_f(pbo_v, '.3f')}")
    else:
        print(f"  era {diag['era']} is not the registered era {FORWARD_ERA}: nothing graded")
    print(f"  >>> adaptive_ladder FORWARD (adapter - M0): {fv} <<<")
    print("  The forward verdict of record is the first run printing a token other than STILL-OPEN.")
    print("  Nothing ships from this study. An ADAPTS lets the operator consider a deployment-rules "
          "change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
