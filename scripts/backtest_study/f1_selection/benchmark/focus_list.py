"""focus_list — does trading only a fixed watchlist beat the card?

Registration: `research/pre-registrations/f1_selection/benchmark/focus_list.md`
(accepted by the operator 2026-11-15). That file is the spec; this module
implements it and adds nothing to its bar. RESEARCH TIER: nothing ships from
this study.

THE ARMS, each up to three Tier A/B picks per signal date:
    ARM F   picks from the frozen 14-ticker watchlist `LW` only   (HEADLINE)
    ARM C   the card: picks from the whole book                   (control)
    ARM N   random eligible picks on ARM F's dates, matched on tier and
            count, 2,000 draws; its 95th percentile is the band   (control)
    P1      ARM F minus ARM C, paired by date                     (PRIMARY)

Every arm is `protocol.top_k_per_day(rows, ladder_rank, k=3, ladder_eligible)`
on rows SORTED BY TICKER first. `top_k_per_day`'s sort is stable, so a tie in
`ladder_rank` goes to the earlier ticker and export row order never decides a
pick (registration, Definitions -> Ties).

WINDOWS, cut by this module itself (registration, Population and basis):
    in-sample   signal dates before 2026-09-23
    neither     2026-09-23 through 2026-11-15, never read
    forward     signal dates from 2026-11-16, read ONCE after the seal lifts

The forward read is one-shot. Its result is written to
`backtests/study_output/focus_list-forward-read.json` and later runs print
that file instead of reading again. `scripts/clean_study_output.py` pins that
file (`CODE_INPUTS`), because deleting it would let the read run twice.

PENDING ROWS. `load_book()` drops a pending open row BEFORE the arms rank a
date, as it does for every study, so on such a date both arms hold the next
row down. The report prints how many picks and dates that touches. The
in-sample read therefore moves as rows close; the forward read does not,
because it uses a complete prefix.

Usage:
  python3 -m scripts.backtest_study run focus_list

  # v3 replication. The runner always writes focus_list-latest.txt, so copy
  # the v4 report aside first and restore it afterwards (registration, v3
  # replication):
  cp backtests/study_output/focus_list-latest.txt /tmp/focus_list-v4.txt
  python3 -m scripts.backtest_study run focus_list --era v3
  mv backtests/study_output/focus_list-latest.txt \
     backtests/study_output/focus_list-v3-<date>.txt
  cp /tmp/focus_list-v4.txt backtests/study_output/focus_list-latest.txt
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import statistics
import sys
from collections import Counter
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection.benchmark import ticker_class as TC  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as MC  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# Era refusals from `load_book` (exit 2 thin era, exit 3 wrong era).
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# ── the watchlist, frozen at acceptance ─────────────────────────────────────
#: (group, tickers) in the registration's order. Editing this is a new
#: registration: GF2 refuses a list whose hash differs from `LW_SHA256`.
GROUPS = (
    ("semis", ("MU", "TSM", "SMH", "NVDA", "AMD")),
    ("AI", ("CRWV", "GOOG", "GOOGL", "PLTR", "META")),
    ("GLD", ("GLD",)),
    ("QQQ", ("QQQ",)),
    ("traditional", ("XLE", "XLF")),
)
LW_SHA256 = "9a44a41796f10479cee7187b86b1feb9b90ca533cd735e34e6324cfe93413395"
#: Two tickers of one company count as one name (criterion 5's largest name).
SAME_COMPANY = {"GOOGL": "GOOG"}

REGISTERED = "2026-11-15"
#: The registration is "v4 only", with v3 as a labelled replication. After a
#: prompt bump `current` resolves to a later era, and this study refuses it.
REGISTERED_ERAS = ("v4", "v3")
IN_SAMPLE_BEFORE = "2026-09-23"   # signal dates strictly before
FORWARD_FROM = "2026-11-16"       # signal dates on or after

K = 3
MIN_DATES = 30          # GF0
MIN_POS = 60            # GF0
YEAR_MIN_POS = 10       # criterion 4
GF5_MIN_DATES = 30
N_DRAWS = 2000
BAND_Q = 0.95
ALPHA = 0.05
SEED_BOOT = 20260811    # protocol's own default seed
SEED_BAND = 20261115

OUT_DIR = ROOT / "backtests" / "study_output"
FORWARD_JSON = OUT_DIR / "focus_list-forward-read.json"
JOURNAL_TRADES = ROOT / "journal" / "trades.csv"
LIVE_OUT = ROOT / "journal" / "reports" / "focus_list-live.txt"

UNDERPOWERED = "UNDERPOWERED"
BEATS = "FOCUS-BEATS-CARD"
TRAILS = "FOCUS-TRAILS-CARD"
NOT_THE_LIST = "NOT-THE-LIST"
NULL = "NULL"
STILL_OPEN = "STILL-OPEN"
FWD_CONFIRMED = "FORWARD-CONFIRMED"
FWD_REFUTED = "FORWARD-REFUTED"
FWD_NULL = "FORWARD-NULL"


def hdr(t):
    print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)


def sub(t):
    print("\n" + f"--- {t} ".ljust(100, "-"))


# ════════════════════════════════════════════════════════════════════════════
# The list
# ════════════════════════════════════════════════════════════════════════════

def list_string(groups=GROUPS) -> str:
    """The exact string the registration hashes."""
    return "|".join(f"{g}:{','.join(ts)}" for g, ts in groups)


def list_hash(groups=GROUPS) -> str:
    return hashlib.sha256(list_string(groups).encode()).hexdigest()


def names_of(groups=GROUPS) -> frozenset:
    return frozenset(t for _g, ts in groups for t in ts)


def group_of(ticker, groups=GROUPS):
    for g, ts in groups:
        if ticker in ts:
            return g
    return None


LW = names_of()
SEMIS = frozenset(dict(GROUPS)["semis"])


# ════════════════════════════════════════════════════════════════════════════
# Rows and windows
# ════════════════════════════════════════════════════════════════════════════

def prepare(recs) -> tuple[list[dict], Counter]:
    """Book records -> the flat rows this study grades. A row with no R cannot
    be graded and is counted, never guessed."""
    out, counts = [], Counter()
    for r in recs:
        if r.get("R") is None:
            counts["R_missing"] += 1
            continue
        ed, clamped = TC.exit_date_of(r)
        counts["exit_clamped"] += int(clamped)
        out.append(dict(
            date=str(r["date"])[:10], ticker=str(r["ticker"]).upper().strip(),
            tier=r.get("tier"), R=float(r["R"]), score_total=r.get("score_total"),
            post13c=r.get("post13c"), exit_date=ed, pending=bool(r.get("pending")),
            _rec=r))
    return out, counts


def windows(rows) -> tuple[list, list, list]:
    """`(in_sample, neither, forward)` by signal date."""
    ins = [r for r in rows if r["date"] < IN_SAMPLE_BEFORE]
    gap = [r for r in rows if IN_SAMPLE_BEFORE <= r["date"] < FORWARD_FROM]
    fwd = [r for r in rows if r["date"] >= FORWARD_FROM]
    return ins, gap, fwd


def by_date(rows) -> dict:
    out: dict = {}
    for r in rows:
        out.setdefault(r["date"], []).append(r)
    return out


# ════════════════════════════════════════════════════════════════════════════
# The arms
# ════════════════════════════════════════════════════════════════════════════

def picks(rows, names=None, exclude=None) -> list:
    """Up to `K` Tier A/B picks per date, ties to the earlier ticker.

    `names` restricts the pool to a list (ARM F); `exclude` removes names from
    it (D1's rebuilt card); neither is ARM C.
    """
    pool = sorted(rows, key=lambda r: r["ticker"])
    if names is not None:
        pool = [r for r in pool if r["ticker"] in names]
    if exclude:
        pool = [r for r in pool if r["ticker"] not in exclude]
    return P.top_k_per_day(pool, P.ladder_rank, k=K, eligible_fn=P.ladder_eligible)


def pending_displaced(rows_with_pending, names=None) -> tuple[int, int]:
    """`(picks, dates)`: how many of an arm's picks would be pending rows had
    the loader kept them. Counts only — no outcome is read. On each such date
    the graded arm holds the next row down instead."""
    hit = [r for r in picks(rows_with_pending, names) if r["pending"]]
    return len(hit), len({r["date"] for r in hit})


def mean_r(rows) -> float:
    return statistics.fmean(r["R"] for r in rows)


def paired_x(a_by: dict, b_by: dict) -> list[tuple[str, float]]:
    """`[(date, mean R of a − mean R of b)]` on the dates both sides hold."""
    return [(d, mean_r(a_by[d]) - mean_r(b_by[d])) for d in sorted(a_by) if d in b_by]


def gain_of(xs) -> float | None:
    return statistics.fmean(x for _d, x in xs) if xs else None


def boot_ci(xs, n: int = P.BOOT_N, seed: int = SEED_BOOT, alpha: float = ALPHA):
    """Percentile CI of the mean of per-date values: dates resampled with
    replacement, every date counting once (registration, The statistic)."""
    vals = [x for _d, x in xs]
    if not vals:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    k = len(vals)
    means = sorted(statistics.fmean(rng.choices(vals, k=k)) for _ in range(n))
    return (means[int(alpha / 2 * n)], means[int((1 - alpha / 2) * n)])


def tier_plan(f_by: dict, elig_by: dict, dates) -> list:
    """Per date, `[(n ARM F took of the tier, that date's eligible R of the tier)]`."""
    plan = []
    for d in dates:
        tiers = []
        for t in ("A", "B"):
            n_t = sum(1 for r in f_by[d] if r["tier"] == t)
            if n_t:
                tiers.append((n_t, [r["R"] for r in elig_by[d] if r["tier"] == t]))
        plan.append(tiers)
    return plan


def spare_dates(plan) -> int:
    """GF5: dates on which some tier ARM F picked from holds more eligible
    rows than ARM F took from it."""
    return sum(1 for tiers in plan if any(len(pool) > n_t for n_t, pool in tiers))


def null_gains(f_by: dict, c_by: dict, elig_by: dict, draws: int = N_DRAWS,
               seed: int = SEED_BAND) -> list[float]:
    """ARM N: sorted gains of `draws` random books, each matched to ARM F on
    dates, tier and count, each scored against ARM C exactly as ARM F is."""
    dates = [d for d in sorted(f_by) if d in c_by]
    if not dates:
        return []
    plan = tier_plan(f_by, elig_by, dates)
    c_means = [mean_r(c_by[d]) for d in dates]
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        tot = 0.0
        for tiers, c_mean in zip(plan, c_means):
            vals = []
            for n_t, pool in tiers:
                vals.extend(rng.sample(pool, n_t))
            tot += statistics.fmean(vals) - c_mean
        out.append(tot / len(dates))
    return sorted(out)


def quantile(sorted_vals, q: float) -> float:
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))]


# ════════════════════════════════════════════════════════════════════════════
# Criteria 4-6
# ════════════════════════════════════════════════════════════════════════════

def sign(x) -> int:
    if x is None or x != x or x == 0:
        return 0
    return 1 if x > 0 else -1


def largest_name(f_rows) -> str | None:
    """The name with the most ARM F positions; ties to the earlier name."""
    c = Counter(SAME_COMPANY.get(r["ticker"], r["ticker"]) for r in f_rows)
    if not c:
        return None
    top = max(c.values())
    return sorted(n for n, v in c.items() if v == top)[0]


def without_name(names, name) -> frozenset:
    return frozenset(t for t in names if SAME_COMPANY.get(t, t) != name)


def curve_stats(rows) -> tuple[float, float]:
    """`(total R, depth of the worst drawdown)` on cumulative R by exit date,
    the running peak seeded at 0."""
    by: dict = {}
    for r in rows:
        by[r["exit_date"]] = by.get(r["exit_date"], 0.0) + r["R"]
    cum = peak = depth = 0.0
    for d in sorted(by):
        cum += by[d]
        peak = max(peak, cum)
        depth = max(depth, peak - cum)
    return cum, depth


def crit6(f_rows, c_rows) -> tuple[bool, str]:
    """Criterion 6 with its registered edge cases. Both row sets must already
    be cut to ARM F's dates."""
    ft, fd = curve_stats(f_rows)
    ct, cd = curve_stats(c_rows)
    f_ratio = f" ratio {ft / fd:+.2f}" if fd else ""
    c_ratio = f" ratio {ct / cd:+.2f}" if cd else ""
    detail = (f"ARM F total {ft:+.2f}R depth {fd:.2f}R{f_ratio}   "
              f"ARM C total {ct:+.2f}R depth {cd:.2f}R{c_ratio}")
    if ft <= 0:
        return False, detail + "   (ARM F total R is 0 or below: fails)"
    if fd == 0:
        return True, detail + "   (ARM F has no drawdown: the better of the two)"
    if cd == 0:
        return False, detail + "   (ARM C has no drawdown: the better of the two)"
    return ft / fd >= ct / cd, detail


# ════════════════════════════════════════════════════════════════════════════
# P1
# ════════════════════════════════════════════════════════════════════════════

def grade(rows, names, boot_n: int = P.BOOT_N, draws: int = N_DRAWS) -> dict:
    """Everything P1's verdict reads, on `rows` (one window, one era)."""
    elig = [r for r in rows if P.ladder_eligible(r)]
    f, c = picks(rows, names), picks(rows)
    f_by, c_by, e_by = by_date(f), by_date(c), by_date(elig)
    elig_ids = {id(r) for r in elig}
    g = dict(f=f, c=c, f_by=f_by, c_by=c_by,
             gf4=all(id(r) in elig_ids for r in f) and all(d in c_by for d in f_by),
             n_dates=len(f_by), n_pos=len(f), n_c_pos=len(c), n_c_dates=len(c_by))
    g["gf0"] = g["n_dates"] >= MIN_DATES and g["n_pos"] >= MIN_POS
    c_ids = {id(r) for r in c}
    g["overlap"] = sum(1 for r in f if id(r) in c_ids)
    g["identical"] = sum(1 for d, rs in f_by.items()
                         if {id(r) for r in rs} == {id(r) for r in c_by.get(d, [])})
    xs = paired_x(f_by, c_by)
    g["xs"] = xs
    g["gain"] = gain_of(xs)
    if not xs:
        return g
    g["ci"] = boot_ci(xs, n=boot_n)
    g["c1"] = g["ci"][0] > 0

    # criterion 2
    plan = tier_plan(f_by, e_by, [d for d, _x in xs])
    g["gf5_dates"] = spare_dates(plan)
    if g["gf5_dates"] >= GF5_MIN_DATES:
        band = null_gains(f_by, c_by, e_by, draws=draws)
        g["band_p95"] = quantile(band, BAND_Q)
        g["band_median"] = quantile(band, 0.5)
        g["band_rank"] = sum(1 for v in band if v < g["gain"]) / len(band)
        g["c2"] = g["gain"] > g["band_p95"]
    else:
        g["c2"] = None            # NOT EVALUABLE

    # criterion 3
    g["f_mean_pos"] = mean_r(f)
    g["f_mean_date"] = statistics.fmean(mean_r(rs) for rs in f_by.values())
    g["f_ci"] = P.boot_ci_by_date(f, key="R", n=boot_n)
    g["c3"] = g["f_ci"][0] > 0
    g["c_mean_pos"] = mean_r(c)

    # criterion 4
    base = sign(g["gain"])
    g["windows"] = {}
    for name, months in P.DOMINANT_WINDOWS.items():
        g["windows"][name] = gain_of([(d, x) for d, x in xs if d[:7] not in months])
    g["years"] = {}
    for y in sorted({d[:4] for d in f_by}):
        n_y = sum(len(rs) for d, rs in f_by.items() if d[:4] == y)
        g["years"][y] = (n_y, gain_of([(d, x) for d, x in xs if d[:4] == y]))
    win_ok = all(sign(v) == base and base != 0 for v in g["windows"].values())
    yr_ok = all(v is not None and v > 0 for n_y, v in g["years"].values() if n_y >= YEAR_MIN_POS)
    g["c4"] = win_ok and yr_ok

    # criterion 5
    g["largest"] = largest_name(f)
    f_ex = by_date(picks(rows, without_name(names, g["largest"])))
    g["gain_ex"] = gain_of(paired_x(f_ex, c_by))
    g["c5"] = base != 0 and sign(g["gain_ex"]) == base

    # criterion 6, both curves on ARM F's dates only
    g["c6"], g["c6_detail"] = crit6(f, [r for r in c if r["date"] in f_by])

    g["trails"] = (g["ci"][1] < 0
                   and all(v is not None and v < 0 for v in g["windows"].values())
                   and g["gain_ex"] is not None and g["gain_ex"] < 0)
    return g


def verdict(g: dict) -> str:
    """The registration's rows, first match from the top."""
    if not g.get("gf0"):
        return UNDERPOWERED
    if all(g.get(k) is True for k in ("c1", "c2", "c3", "c4", "c5", "c6")):
        return BEATS
    if g.get("trails"):
        return TRAILS
    if g.get("c1") and g.get("c2") is False:
        return NOT_THE_LIST
    return NULL


def failed(g: dict) -> str:
    out = []
    for i, k in enumerate(("c1", "c2", "c3", "c4", "c5", "c6"), 1):
        v = g.get(k)
        if v is None and k == "c2":
            out.append("2 (NOT EVALUABLE)")
        elif v is not True:
            out.append(str(i))
    return ", ".join(out) or "none"


def fmt(x, spec="+.3f") -> str:
    return "n/a" if x is None or x != x else format(x, spec)


def yn(v) -> str:
    return "NOT EVALUABLE" if v is None else ("Y" if v else "n")


def print_grade(g: dict, label: str) -> None:
    print(f"  ARM F  dates {g['n_dates']:>4}  positions {g['n_pos']:>4}     "
          f"ARM C  dates {g['n_c_dates']:>4}  positions {g['n_c_pos']:>4}")
    share = f" ({g['overlap'] / g['n_pos']:.0%})" if g["n_pos"] else ""
    print(f"  ARM F positions the card also takes: {g['overlap']} of {g['n_pos']}{share}; "
          f"dates on which both arms hold the same picks: {g['identical']} of {g['n_dates']}")
    print(f"  GF0 power (>= {MIN_DATES} dates, >= {MIN_POS} positions): "
          f"{'pass' if g['gf0'] else 'FAIL'}")
    if g.get("gain") is None:
        print("  no paired date; nothing graded")
        return
    lo, hi = g["ci"]
    print(f"  {label}  gain (ARM F − ARM C, mean of per-date differences) "
          f"{g['gain']:+.3f}  CI95 [{lo:+.3f}, {hi:+.3f}]  dates {len(g['xs'])}")
    pf_d, pf_lo, pf_hi = P.pf_paired_by_date(g["f"], [r for r in g["c"] if r["date"] in g["f_by"]])
    print(f"      PF ARM F {fmt(P.pf(g['f']), '.2f')}  ARM C on ARM F's dates "
          f"{fmt(P.pf([r for r in g['c'] if r['date'] in g['f_by']]), '.2f')}  "
          f"difference {fmt(pf_d, '+.2f')} [{fmt(pf_lo, '+.2f')}, {fmt(pf_hi, '+.2f')}]")
    print(f"  1 gain interval above 0                      {yn(g['c1'])}")
    if g["c2"] is None:
        print(f"  2 beats ARM N's 95th percentile              NOT EVALUABLE  "
              f"(GF5: {g['gf5_dates']} dates with a spare same-tier row, need {GF5_MIN_DATES})")
    else:
        print(f"  2 beats ARM N's 95th percentile              {yn(g['c2'])}  "
              f"band p95 {g['band_p95']:+.3f}  median {g['band_median']:+.3f}  "
              f"(seed {SEED_BAND}, {N_DRAWS} draws; GF5 {g['gf5_dates']} dates; "
              f"context, not a p-value: ARM F above {g['band_rank']:.1%} of draws)")
    flo, fhi = g["f_ci"]
    print(f"  3 ARM F's own mean R interval above 0        {yn(g['c3'])}  "
          f"mean R per position {g['f_mean_pos']:+.3f} [{flo:+.3f}, {fhi:+.3f}]  "
          f"per date {g['f_mean_date']:+.3f}  (ARM C per position {g['c_mean_pos']:+.3f})")
    wins = "  ".join(f"{k} {fmt(v)}" for k, v in g["windows"].items())
    yrs = "  ".join(f"{y} {fmt(v)} (n {n})" for y, (n, v) in g["years"].items())
    print(f"  4 sign kept without each window, every year  {yn(g['c4'])}  {wins}  |  {yrs}")
    print(f"  5 sign kept without the largest name         {yn(g['c5'])}  "
          f"largest {g['largest']}  gain without it {fmt(g['gain_ex'])}")
    print(f"  6 return for drawdown at least the card's    {yn(g['c6'])}  {g['c6_detail']}")


# ════════════════════════════════════════════════════════════════════════════
# Printed context: MTM drawdown, D1-D3, L-LIVE
# ════════════════════════════════════════════════════════════════════════════

def mtm_drawdown(rows) -> tuple[float, int, int] | None:
    """`(MTM max drawdown $, positions reconciled, positions)` at each row's
    own contract count, or None when a row carries no book record (a
    synthetic test row). The reconciled count is `book_curves`' own G-MTM
    check of each marked exit against the row's stored booked dollars."""
    recs = [r.get("_rec") for r in rows]
    if not recs or any(rec is None for rec in recs):
        return None
    from scripts.backtest_study.f5_hedging.hedge_portfolio import book_positions
    bc = MC.book_curves(book_positions(recs), target=MC.TARGET_STORED)
    return MC.max_drawdown(bc.mtm.daily), bc.n_reconciled, bc.n_positions


def print_mtm(g: dict) -> None:
    c_on_f = [r for r in g["c"] if r["date"] in g["f_by"]]
    for label, rows in (("ARM F", g["f"]), ("ARM C on ARM F's dates", c_on_f)):
        try:
            got = mtm_drawdown(rows)
        except Exception as exc:  # context only: say why, never kill the verdict
            print(f"      MTM {label}: NOT AVAILABLE ({type(exc).__name__}: {exc})")
            continue
        if got is None:
            print(f"      MTM {label}: NOT AVAILABLE (rows carry no book record)")
        else:
            print(f"      MTM {label}: max drawdown ${got[0]:,.0f}  "
                  f"(G-MTM reconciled {got[1]} of {got[2]} positions; dollars at each row's "
                  f"own contract count; context, not a criterion)")


def print_cuts(rows, g: dict) -> None:
    sub("D1 — ARM F against the card rebuilt without LW names (printed, never graded)")
    off_by = by_date(picks(rows, exclude=LW))
    xs = paired_x(g["f_by"], off_by)
    if xs:
        lo, hi = boot_ci(xs)
        print(f"  dates with a pick on both sides {len(xs)} of {g['n_dates']} ARM F dates; "
              f"gain {gain_of(xs):+.3f}  CI95 [{lo:+.3f}, {hi:+.3f}]")
    else:
        print("  no date holds a pick on both sides")

    sub("D2 — P1 with the semis group alone as the list (printed, never graded)")
    s_by = by_date(picks(rows, SEMIS))
    xs = paired_x(s_by, g["c_by"])
    if xs:
        lo, hi = boot_ci(xs)
        print(f"  dates {len(xs)}  positions {sum(len(v) for v in s_by.values())}  "
              f"gain {gain_of(xs):+.3f}  CI95 [{lo:+.3f}, {hi:+.3f}]")
    else:
        print("  no semis date")

    sub("D3 — ARM F by group (printed, never graded)")
    for grp, _ts in GROUPS:
        rs = [r for r in g["f"] if group_of(r["ticker"]) == grp]
        print(f"  {grp:<12} positions {len(rs):>4}  mean R {fmt(mean_r(rs) if rs else None)}")


def live_cut(names=LW, trades_csv: Path = JOURNAL_TRADES, out: Path = LIVE_OUT) -> str:
    """L-LIVE: journal closes from `FORWARD_FROM`, on-list and off-list.

    Everything goes to gitignored `journal/` only (the registration's table);
    the returned report line names the file and carries no count and no
    figure, because the report is copied into tracked files. Resolved at
    build (2026-11-15): until the holdout seal lifts the file holds counts
    only — a win rate on live closes is an outcome figure on sealed dates.
    """
    if not trades_csv.exists():
        return "L-LIVE: no journal on this machine; nothing written"
    on = off = on_win = off_win = 0
    with trades_csv.open() as fh:
        for row in csv.DictReader(fh):
            raw = (row.get("realized_pnl") or "").strip()
            if not raw or (row.get("date") or "")[:10] < FORWARD_FROM:
                continue
            try:
                pnl = float(raw)
            except ValueError:
                continue
            if (row.get("ticker") or "").upper().strip() in names:
                on, on_win = on + 1, on_win + int(pnl > 0)
            else:
                off, off_win = off + 1, off_win + int(pnl > 0)
    lines = [f"focus_list L-LIVE — journal closes from {FORWARD_FROM}",
             f"on-list closes {on}", f"off-list closes {off}"]
    if era_mod.SEAL_LIFTED:
        lines.append(f"on-list winners {on_win}; off-list winners {off_win}")
    else:
        lines.append("win rates withheld until the holdout seal lifts")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    try:
        where = out.relative_to(ROOT)
    except ValueError:
        where = out
    return f"L-LIVE: written to {where} (gitignored); nothing from it is printed here"


# ════════════════════════════════════════════════════════════════════════════
# The forward read — once
# ════════════════════════════════════════════════════════════════════════════

def complete_prefix(fwd_rows) -> list:
    """Forward rows on dates before the first date that still holds a pending
    eligible row: every pick on the kept dates has closed."""
    pend = sorted(r["date"] for r in fwd_rows if r["pending"] and P.ladder_eligible(r))
    cut = pend[0] if pend else None
    return [r for r in fwd_rows if not r["pending"] and (cut is None or r["date"] < cut)]


def forward_verdict(g: dict) -> str:
    if g.get("c1") and g.get("c3"):
        return FWD_CONFIRMED
    if g.get("gain") is not None and (g["ci"][1] < 0 or g["f_ci"][1] < 0):
        return FWD_REFUTED
    return FWD_NULL


def forward_read(fwd_rows, seal_lifted, names=LW, store: Path = FORWARD_JSON,
                 today: str | None = None) -> dict:
    """`{verdict, ...}`. Reads outcomes at most once: a stored read is returned
    as it was written, and nothing is computed while the seal holds or the
    counts are short."""
    if store.exists():
        got = json.loads(store.read_text())
        got["stored"] = True
        return got
    if not seal_lifted:
        return dict(verdict=STILL_OPEN, why="the holdout seal has not lifted")
    done = complete_prefix(fwd_rows)
    f_by = by_date(picks(done, names))
    n_dates, n_pos = len(f_by), sum(len(v) for v in f_by.values())
    if n_dates < MIN_DATES or n_pos < MIN_POS:
        return dict(verdict=STILL_OPEN, n_dates=n_dates, n_pos=n_pos,
                    why=f"needs {MIN_DATES} forward dates and {MIN_POS} closed positions")
    g = grade(done, names)
    out = dict(verdict=forward_verdict(g), read_on=today or _date.today().isoformat(),
               n_dates=g["n_dates"], n_pos=g["n_pos"], last_date=max(f_by),
               gain=g["gain"], ci=list(g["ci"]), f_mean_pos=g["f_mean_pos"],
               f_ci=list(g["f_ci"]), c1=g["c1"], c2=g["c2"], c3=g["c3"],
               band_p95=g.get("band_p95"), list_sha256=list_hash())
    try:
        mtm = mtm_drawdown(g["f"])
    except Exception:
        mtm = None
    out["mtm_maxdd_dollars"] = None if mtm is None else mtm[0]
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(out, indent=2) + "\n")
    return out


def print_forward(fr: dict, seal_info: dict | None) -> None:
    hdr("FORWARD READ — one read, signal dates from " + FORWARD_FROM)
    if fr.get("stored"):
        print(f"  read once on {fr['read_on']}; this run does not read again "
              f"({FORWARD_JSON.relative_to(ROOT)})")
    if fr["verdict"] == STILL_OPEN:
        print(f"  {fr['why']}")
        if "n_dates" in fr:
            print(f"  census: ARM F forward dates {fr['n_dates']}  closed positions {fr['n_pos']}")
        elif seal_info:
            print(f"  census: {era_mod.seal_line(seal_info)}")
    else:
        print(f"  ARM F forward dates {fr['n_dates']}  positions {fr['n_pos']}  "
              f"through {fr['last_date']}")
        print(f"  gain {fr['gain']:+.3f}  CI95 [{fr['ci'][0]:+.3f}, {fr['ci'][1]:+.3f}]   "
              f"ARM F mean R {fr['f_mean_pos']:+.3f} [{fr['f_ci'][0]:+.3f}, {fr['f_ci'][1]:+.3f}]")
        print(f"  beside it: criterion 2 {yn(fr['c2'])} (band p95 {fmt(fr.get('band_p95'))}); "
              f"MTM max drawdown ${fmt(fr.get('mtm_maxdd_dollars'), ',.0f')}")
    print(f"\n>>> focus_list FORWARD (one read from {FORWARD_FROM}): {fr['verdict']} <<<")


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    recs, diag = load_book(include_bs=False)
    era = diag.get("era")
    v3 = era == "v3"
    hdr("focus_list — does trading only a fixed watchlist beat the card?   "
        f"[era {era}]" + ("   v3 REPLICATION (same path)" if v3 else ""))
    print("  Registration: research/pre-registrations/f1_selection/benchmark/focus_list.md "
          f"(accepted {REGISTERED}). NOTHING SHIPS.")
    print(f"  GF1 era: load_book() resolved era '{era}'  ({len(recs)} rows, "
          f"{diag.get('n_dates')} dates, {diag.get('date_range')})")
    if era not in REGISTERED_ERAS:
        print(f"  GF1 FAIL: the registration covers {' and '.join(REGISTERED_ERAS)} only; "
              f"era '{era}' needs its own registration. Exit 3.")
        return 3
    print(f"  {era_mod.seal_line(diag['seal'])}" if diag.get("seal") else "  seal: n/a")
    print("  LEDGER (selection ledger): focus_list — 1 list, 1 graded contrast: P1; "
          f"registered {REGISTERED}")

    h = list_hash()
    print("  GF2 list: " + "  ".join(f"{g}: {' '.join(ts)}" for g, ts in GROUPS))
    print(f"  GF2 sha256 {h}")
    if h != LW_SHA256:
        print(f"  GF2 FAIL: the registration records {LW_SHA256}")
        return 1
    print("  GF2 pass (matches the registration)")

    rows, counts = prepare(recs)
    ins, gap, fwd = windows(rows)
    print(f"  dropped: R missing {counts['R_missing']}; exit dates clamped to the bounded grid "
          f"{counts['exit_clamped']}")
    print(f"  windows: in-sample (< {IN_SAMPLE_BEFORE}) {len(ins)} rows / "
          f"{len({r['date'] for r in ins})} dates; neither {len(gap)} rows, never read; "
          f"forward (>= {FORWARD_FROM}) {len(fwd)} rows")
    if not ins:
        print("  no in-sample rows")
        return 1

    # Pending rows, for counts and the forward prefix only (never graded
    # in-sample): the same book with `include_pending=True`.
    recs_p, _diag_p = load_book(include_bs=False, include_pending=True)
    ins_p, _gap_p, fwd_p = windows(prepare(recs_p)[0])
    for label, names in (("ARM C", None), ("ARM F", LW)):
        n_p, n_d = pending_displaced(ins_p, names)
        print(f"  pending rows: {n_p} {label} picks on {n_d} dates are pending and were dropped "
              f"before ranking; the arm holds the next row down there")

    g = grade(ins, LW)
    # GF3 on the rows actually graded, not on the partition that made them.
    late = [r for r in g["f"] + g["c"] if r["date"] >= IN_SAMPLE_BEFORE]
    print(f"  GF3 window: {'pass' if not late else 'FAIL'}  (graded picks dated "
          f"{IN_SAMPLE_BEFORE} or later: {len(late)})")
    print(f"  GF4 subset: {'pass' if g['gf4'] else 'FAIL'}")
    if late or not g["gf4"]:
        return 1

    label = "P1 v3 replication (same path)" if v3 else "P1"
    hdr(f"{label} — ARM F minus ARM C, paired by date, in-sample")
    print_grade(g, "P1")
    if g.get("gain") is not None:
        print_mtm(g)
    word = verdict(g)
    if word == NULL:
        print(f"  criteria not met: {failed(g)}")
    # The closing VERDICT block restates lines printed above, word for word in
    # their figures; `scripts/study_results.py` quotes the last such block.
    closing = []
    if g.get("gain") is not None:
        closing.append(f"  P1  gain {g['gain']:+.3f}  CI95 [{g['ci'][0]:+.3f}, {g['ci'][1]:+.3f}]  "
                       f"dates {len(g['xs'])}  ARM F positions {g['n_pos']}")
        closing.append("  criteria  " + "  ".join(
            f"{i} {yn(g.get(k))}" for i, k in enumerate(("c1", "c2", "c3", "c4", "c5", "c6"), 1)))
    if v3:
        line = (f">>> focus_list P1 v3 replication (same path; notes agreement, confirms "
                f"nothing): {word} <<<")
        print(f"\n{line}")
        hdr("VERDICT — v3 replication (same path)")
        print("\n".join(closing + [line]))
        return 0
    line = f">>> focus_list P1 (ARM F minus ARM C, paired by date, in-sample v4): {word} <<<"
    print(f"\n{line}")
    closing.append(line)

    if g.get("gain") is not None:
        print_cuts(ins, g)

    # The forward read uses the pending-included rows to find its complete
    # prefix. While the seal holds the loader withholds every forward row.
    fr = forward_read(fwd_p, era_mod.SEAL_LIFTED)
    print_forward(fr, diag.get("seal"))

    sub("L-LIVE (printed to journal/ only)")
    print(f"  {live_cut()}")

    hdr("VERDICT")
    closing.append(f">>> focus_list FORWARD (one read from {FORWARD_FROM}): {fr['verdict']} <<<")
    closing.append("  In-sample only. The list was chosen after trading these names, so only the "
                   "forward read can confirm it. Nothing ships.")
    print("\n".join(closing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
