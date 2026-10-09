"""ticker_class — is a play on a broad US index ETF more reliable than a single-stock play, direction held fixed?

PRE-REGISTERED 2026-10-07 (IMMUTABLE):
research/pre-registrations/f1_selection/ticker_class.md. This module implements
that file literally. Every gate, bar, threshold and verdict word below is the
registration's; where the registration left a mechanic open, the reading taken
is named in `BUILD READINGS` (printed in the report) rather than chosen quietly.

What it grades. The unit is a fixed GROUP of tickers (the group table is
embedded verbatim below and hashed, GT3). The primary contrast P1 is G1 (index
ETFs) against S = G5 ∪ G6 ∪ G7 (single stocks), DIRECTION-STANDARDISED: each
side's bear and bull meanR are weighted by G1's own bear/bull mix. S1-S3 are
G1 against G5/G6/G7 on bear plays; S4 is G1 against G2 on bull plays. Four
metrics together make "reliable": meanR with a date-clustered CI, hit rate,
share of the book's maxDD episode, and sign stability (window, year,
half-year, top-ticker removal). A PBO/CSCV read over the five graded groups
vetoes any group-level verdict when selection looks like luck.

Population. `load_book()` at its defaults (era from STUDY_ERA, real + tweak,
bs excluded, proxy calibration on). In-sample = signal dates before
2026-08-11; 2026-08-11..2026-10-07 is in neither window; forward = signal
dates after 2026-10-07. `fill_trusted` false rows are dropped. Headline R is
the stored `realized_pnl_pct` (net of `cost_total`); gross is printed beside.

Nothing ships from this study. Usage:

    python3 -m scripts.backtest_study run ticker_class
    python3 -m scripts.backtest_study run ticker_class --era v3   # P1, S1-S3 only
"""
from __future__ import annotations

import hashlib
import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import CREDIT_PROD, DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import replay  # noqa: E402
from scripts.journal.lib.mapping import ladder_tier as mapping_ladder_tier  # noqa: E402

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# ════════════════════════════════════════════════════════════════════════════
# The frozen group table (GT3)
# ════════════════════════════════════════════════════════════════════════════
# VERBATIM content of the scratch file `groups_v1.py` written 2026-10-07 18:35
# +08 before any outcome column was read. The hash is sha256 over this string's
# UTF-8 bytes, which are byte-identical to that file. The table is USED by
# executing this very string, so the hash covers exactly what the study runs.
# Never edit it: a different table is a new registration.
GROUPS_V1_SOURCE = (
    "# FIXED GROUP TABLE — written 2026-10-07 BEFORE any outcome column was read.\n"
    "# Rule order (first match wins): instrument type, then exposure. External sources only:\n"
    "# ETF prospectus mandate; GICS industry 4530 (semis); the \"Magnificent 7\" list.\n"
    "G1_INDEX   = {\"SPY\",\"QQQ\",\"IWM\",\"DIA\"}                       # broad US equity index ETFs\n"
    "G2_COUNTRY = {\"FXI\",\"EWZ\",\"EWY\",\"EWJ\",\"EEM\",\"EFA\",\"KWEB\",\"ASHR\",\"INDA\",\"EWW\",\"EWT\",\"MCHI\"}  # single-country / regional equity ETFs\n"  # noqa: E501
    "G3_SECTOR  = {\"SMH\",\"SOXX\",\"XLE\",\"XLF\",\"XLI\",\"XLU\",\"XLV\",\"XLY\",\"XRT\",\"KRE\",\"XBI\",\"IGV\",\"ITB\",\"OIH\",\"GDX\",\"ARKK\",\"DRAM\"}  # US sector/thematic equity ETFs\n"  # noqa: E501
    "G4_NONEQ   = {\"GLD\",\"SLV\",\"TLT\",\"HYG\",\"LQD\",\"USO\",\"IBIT\",\"ETHA\",\"BITO\"}  # non-equity ETFs/ETPs\n"  # noqa: E501
    "G6_SEMIS   = {\"NVDA\",\"AMD\",\"MU\",\"TSM\",\"INTC\",\"AVGO\",\"MRVL\",\"ARM\",\"LRCX\",\"AMAT\",\"KLAC\",\"QCOM\",\"TXN\",\"CRDO\",\"SKHY\"}  # GICS 4530 single names (semis beats Mag-7: NVDA lands here)\n"  # noqa: E501
    "G5_BIGTECH = {\"AAPL\",\"MSFT\",\"AMZN\",\"GOOGL\",\"GOOG\",\"META\",\"TSLA\"}  # Magnificent 7 minus NVDA\n"
    "# G7_REST = every other single name. Unresolved tickers (SPCX, SNDK, SMCI…) default to G7; operator may move them BEFORE acceptance, never after.\n"  # noqa: E501
    "ORDER = [(\"G1_index\",G1_INDEX),(\"G2_country\",G2_COUNTRY),(\"G3_sector\",G3_SECTOR),(\"G4_noneq\",G4_NONEQ),\n"
    "         (\"G6_semis\",G6_SEMIS),(\"G5_bigtech\",G5_BIGTECH)]\n"
    "def group(t):\n"
    "    t = str(t).upper().strip()\n"
    "    for name, s in ORDER:\n"
    "        if t in s: return name\n"
    "    return \"G7_rest\"\n"
)

#: The registration prints `6ce7373e…`; the full digest of the file it names.
REGISTERED_HASH_PREFIX = "6ce7373e"
GROUPS_V1_SHA256 = "6ce7373e1982d592d45b63065549b6b5c0a592db880b41da1816757005afedcc"

_TABLE_NS: dict = {}
exec(GROUPS_V1_SOURCE, _TABLE_NS)  # noqa: S102 — our own frozen constant
_group_raw = _TABLE_NS["group"]
TABLE_ORDER: list = _TABLE_NS["ORDER"]

G1, G2, G3, G4, G5, G6, G7 = ("G1_index", "G2_country", "G3_sector", "G4_noneq",
                              "G5_bigtech", "G6_semis", "G7_rest")
ALL_GROUPS = (G1, G2, G3, G4, G5, G6, G7)
SINGLE_STOCK = (G5, G6, G7)            # S
GRADED_GROUPS = (G1, G2, G5, G6, G7)   # the PBO N
BEAR_PBO_GROUPS = (G1, G5, G6, G7)     # the bear-stratum diagnostic N
S_NAME = "S"


def table_hash(source: str = None) -> str:
    return hashlib.sha256((GROUPS_V1_SOURCE if source is None else source)
                          .encode("utf-8")).hexdigest()


def group_of(ticker) -> str:
    """The frozen first-match rule (G1, G2, G3, G4, G6, G5, else G7)."""
    return _group_raw(ticker)


def explicit_memberships(ticker) -> list[str]:
    """Every explicit set the ticker is listed in (GT2 wants at most one)."""
    t = str(ticker).upper().strip()
    return [name for name, members in TABLE_ORDER if t in members]


# ════════════════════════════════════════════════════════════════════════════
# Constants fixed by the registration
# ════════════════════════════════════════════════════════════════════════════
IN_SAMPLE_BEFORE = "2026-08-11"     # signal dates strictly before
IN_SAMPLE_LAST_DAY = "2026-08-10"   # the window's last day; its month is T's last row
FORWARD_AFTER = "2026-10-07"        # signal dates strictly after
ACCEPTED = "2026-10-07"
MIN_DATES = 30                      # GT0 per graded side
MIN_POS = 60
MIN_POS_S4_G2 = 30                  # S4's G2 side
STRATUM_MIN_DATES = 30              # a standardisation stratum below this is dropped
YEAR_MIN_POS = 10                   # criteria 4 and 5: each side >= 10 positions
HALF_SHARE = 2.0 / 3.0
PBO_SUPPORT = 0.25
PBO_VETO = 0.50
CSCV_S = 16
ALPHA = 0.05
BOOT_N = P.BOOT_N                   # 10,000
SEED = 20260811                     # protocol's seed
FWD_MIN_DATES = 30
GT4_TOL = 1e-9

NEUTRAL_KEYS = ("straddle", "strangle", "iron_condor", "butterfly", "calendar")

BUILD_READINGS = [
    "Direction: bull_* / long_call / short_put = bull; bear_* / long_put = bear; a structure "
    "containing straddle, strangle, iron_condor, butterfly or calendar = neutral; anything else = "
    "'other' (printed, never graded).",
    "Tier: scripts/journal/lib/mapping.py::ladder_tier(structure, market_regime, dte, "
    "short_leg_delta=row delta), as narrow_to_fit.tier_of does. The loader's own `tier` is a port "
    "(book.ladder_tier) without the credit RANGE+L-VOL veto, so it is NOT that function's output; "
    "agreement is printed.",
    "Gross R = stored R + cost_total / (|entry| x 100 x contracts), split on a non-blank "
    "cost_total, never on cost_basis.",
    "Diff CIs (meanR and hit rate): numpy date-clustered bootstrap over the UNION of both "
    "sides' dates, resampled jointly, BOOT_N draws, seed 20260811; a draw leaving a used stratum "
    "empty on either side is discarded and counted. Per-side meanR CIs use protocol.boot_ci_by_date.",
    "Criterion 1 for S1-S4: two-sided bootstrap p per contrast, Holm step-down across the four "
    "(m = 4 on v4; m = 3 on the v3 replication, which runs S1-S3 only); the CI printed is the "
    "percentile CI at that contrast's Holm level alpha/(m-rank+1). Met when the Holm-adjusted "
    "p < 0.05 and the Holm-level CI excludes 0 on the graded side.",
    "Hit rate on P1/T1 is direction-standardised with the same weights as meanR.",
    "Criterion 3 (and the census): the book = every in-sample trusted row, all groups and "
    "directions; exit date = the grid day at days_held (clamped to the bounded grid); episode = "
    "exits after the running peak (seed 0) through the maxDD trough. G1's share uses all its "
    "rows in the episode, the same for every contrast.",
    "Criteria 4-6 test the sign of the full-sample point difference; a sub-cut recomputes the "
    "contrast with the base weights renormalised over strata present on both sides. Criterion 5 "
    "with no qualifying half-year reads NOT MET. Criterion 6 removes the largest ticker (by "
    "positions in the contrast population) from each side at once.",
    "MIX-ONLY: the pooled, unadjusted G1-vs-comparison contrast (all directions; C0's basis) "
    "has a CI95 clear of 0 while the contrast's own criterion-1 CI is not.",
    "PBO: T = every calendar month from the first in-sample signal month through 2026-08, the "
    "month the in-sample window ends in (2026-08-10), decided by date only, so a month with no "
    "position at all is a blank row, not a dropped one; a cell is that "
    "month's direction-standardised meanR (weights renormalised over the strata present that "
    "month), passed to lib/pbo.cscv as a T x N x 2 array [value, present] with "
    "pbo.ratio_metric, so a block's statistic is the mean over NON-BLANK months and a blank "
    "month is never a zero (cscv refuses NaN). A group blank across a whole half ranks worst. "
    "'P(below median)' counts lambda < 0 strictly; PBO itself counts lambda <= 0.",
    "DEBIT_PROD baseline: every row re-replayed through the frozen harness, debit under "
    "DEBIT_PROD, credit under CREDIT_PROD (gross, point only). Shipped-rule baseline: the "
    "contrast restricted to mapping tiers A/B, plus the shipped top-3/day ladder book's meanR.",
]


# ════════════════════════════════════════════════════════════════════════════
# Row preparation
# ════════════════════════════════════════════════════════════════════════════

def direction(structure) -> str:
    s = str(structure or "").strip().lower()
    if s.startswith("bull_") or s in ("long_call", "short_put"):
        return "bull"
    if s.startswith("bear_") or s == "long_put":
        return "bear"
    if any(k in s for k in NEUTRAL_KEYS):
        return "neutral"
    return "other"


def _float(v):
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def cost_pct_of(rec) -> float:
    """cost_total on the pnl-pct scale; 0 where cost_total is blank."""
    t = rec["t"]
    ct = _float(t.row.get("cost_total"))
    if ct is None:
        return 0.0
    denom = t.denom * 100 * t.contracts
    return ct / denom if denom else 0.0


def exit_date_of(rec) -> tuple[str, bool]:
    """(exit date, clamped?) — the grid day at `days_held` (1-based)."""
    t = rec["t"]
    dh = rec.get("days_held")
    n = len(t.grid)
    if dh is None or dh < 1:
        return t.grid[-1].isoformat(), True
    if dh > n:
        return t.grid[-1].isoformat(), True
    return t.grid[dh - 1].isoformat(), False


def tier_of(rec) -> str:
    dte = rec.get("dte")
    tier, _partial, _why = mapping_ladder_tier(
        rec["structure"], rec.get("market_regime") or "",
        dte_proxy=float(dte) if dte is not None else float("nan"),
        short_leg_delta=rec.get("delta"))
    return tier


def prod_replay_R(rec) -> float | None:
    prof = CREDIT_PROD if rec["credit"] else DEBIT_PROD
    try:
        return float(replay(rec["t"], **prof)["pnl_pct"])
    except Exception:  # a replay failure is counted, never fatal
        return None


def prepare(recs) -> tuple[list[dict], Counter]:
    out, counts = [], Counter()
    for r in recs:
        if r.get("R") is None:
            counts["R_missing"] += 1
            continue
        if not r.get("fill_trusted", True):
            counts["fill_untrusted"] += 1
            continue
        ed, clamped = exit_date_of(r)
        counts["exit_clamped"] += int(clamped)
        cp = cost_pct_of(r)
        has_cost = _float(r["t"].row.get("cost_total")) is not None
        counts["cost_total_nonblank" if has_cost else "cost_total_blank"] += 1
        out.append(dict(
            date=r["date"], ticker=str(r["ticker"]).upper().strip(),
            structure=r["structure"], source=r["source"], credit=r["credit"],
            group=group_of(r["ticker"]), dir=direction(r["structure"]),
            tier=tier_of(r), tier_book=r.get("tier"),
            R=float(r["R"]), Rg=float(r["R"]) + cp, hit=1.0 if r["R"] > 0 else 0.0,
            mfe=r.get("mfe"), mae=r.get("mae"), exit_date=ed,
            market_regime=r.get("market_regime"), score_total=r.get("score_total"),
            post13c=r.get("post13c"), Rprod=None, _rec=r))
    return out, counts


# ════════════════════════════════════════════════════════════════════════════
# Statistics
# ════════════════════════════════════════════════════════════════════════════

def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else float("nan")


def strat_of(standardised: bool):
    return (lambda r: r["dir"]) if standardised else (lambda r: "all")


def std_point(rows, weights: dict, strat, key="R") -> float:
    """Σ_s w_s mean_s(key), weights renormalised over strata present in `rows`."""
    by = defaultdict(list)
    for r in rows:
        s = strat(r)
        if s in weights and r.get(key) is not None:
            by[s].append(r[key])
    present = {s: w for s, w in weights.items() if by.get(s)}
    tot = sum(present.values())
    if not present or tot <= 0:
        return float("nan")
    return sum(w / tot * statistics.fmean(by[s]) for s, w in present.items())


def diff_point(a, b, weights, strat, key="R") -> float:
    """G1 minus comparison, both standardised on the strata present on BOTH sides."""
    sa = {strat(r) for r in a if strat(r) in weights}
    sb = {strat(r) for r in b if strat(r) in weights}
    w = {s: weights[s] for s in sa & sb}
    if not w:
        return float("nan")
    return std_point(a, w, strat, key) - std_point(b, w, strat, key)


def joint_boot(a, b, weights, strat, key="R", n=BOOT_N, seed=SEED, chunk=500):
    """Sorted bootstrap draws of diff_point(a, b) — dates resampled jointly over
    the union of both sides' dates. Returns (sorted draws, discarded draws)."""
    strata = list(weights)
    if not strata:
        return np.array([]), 0
    dates = sorted({r["date"] for r in a} | {r["date"] for r in b})
    di = {d: i for i, d in enumerate(dates)}
    D, K = len(dates), len(strata)
    ki = {s: k for k, s in enumerate(strata)}

    def arrays(rows):
        S = np.zeros((K, D))
        C = np.zeros((K, D))
        for r in rows:
            s = strat(r)
            if s not in ki or r.get(key) is None:
                continue
            S[ki[s], di[r["date"]]] += r[key]
            C[ki[s], di[r["date"]]] += 1
        return S, C

    sa, ca = arrays(a)
    sb, cb = arrays(b)
    w = np.array([weights[s] for s in strata])[:, None]
    rng = np.random.default_rng(seed)
    kept, dropped, done = [], 0, 0
    while done < n:
        m = min(chunk, n - done)
        idx = rng.integers(0, D, size=(m, D))
        SA, CA = sa[:, idx].sum(axis=2), ca[:, idx].sum(axis=2)
        SB, CB = sb[:, idx].sum(axis=2), cb[:, idx].sum(axis=2)
        ok = (CA > 0).all(axis=0) & (CB > 0).all(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            stat = (w * SA / CA).sum(axis=0) - (w * SB / CB).sum(axis=0)
        kept.append(stat[ok])
        dropped += int((~ok).sum())
        done += m
    return np.sort(np.concatenate(kept)), dropped


def pct_ci(draws: np.ndarray, alpha: float = ALPHA) -> tuple[float, float]:
    m = len(draws)
    if not m:
        return float("nan"), float("nan")
    return float(draws[int(alpha / 2 * m)]), float(draws[min(m - 1, int((1 - alpha / 2) * m))])


def boot_p(draws: np.ndarray) -> float:
    """Two-sided percentile-bootstrap p-value for a difference of 0."""
    if not len(draws):
        return 1.0
    return float(min(1.0, 2 * min(np.mean(draws <= 0), np.mean(draws >= 0))))


def holm(pvals: dict) -> dict:
    """{name: (adjusted p, rank, level alpha_k)}, Holm step-down over all names."""
    m = len(pvals)
    order = sorted(pvals, key=lambda k: (pvals[k], k))
    out, running = {}, 0.0
    for i, k in enumerate(order, start=1):
        running = max(running, min(1.0, (m - i + 1) * pvals[k]))
        out[k] = (running, i, ALPHA / (m - i + 1))
    return out


def direction_weights(g1_rows, b_rows) -> tuple[dict, dict, list]:
    """G1's own bear/bull mix, with any stratum below 30 dates on either side
    dropped and the rest renormalised. Returns (weights, raw mix, dropped)."""
    n = Counter(r["dir"] for r in g1_rows if r["dir"] in ("bear", "bull"))
    tot = sum(n.values())
    raw = {s: (n[s] / tot if tot else 0.0) for s in ("bear", "bull")}
    keep, dropped = {}, []
    for s in ("bear", "bull"):
        da = len({r["date"] for r in g1_rows if r["dir"] == s})
        db = len({r["date"] for r in b_rows if r["dir"] == s})
        if da < STRATUM_MIN_DATES or db < STRATUM_MIN_DATES or raw[s] <= 0:
            dropped.append(f"{s} (G1 {da} dates, comparison {db} dates)")
        else:
            keep[s] = raw[s]
    tot_k = sum(keep.values())
    return ({s: v / tot_k for s, v in keep.items()} if tot_k else {}), raw, dropped


def maxdd_episode(rows, key="R"):
    """(depth, peak_date | None, trough_date | None, rows in episode) on the R
    series summed by exit date, running peak seeded at 0."""
    by = defaultdict(float)
    for r in rows:
        by[r["exit_date"]] += r[key]
    days = sorted(by)
    cum, peak, peak_day = 0.0, 0.0, None
    best = (0.0, None, None)
    for d in days:
        cum += by[d]
        if cum > peak:
            peak, peak_day = cum, d
        dd = peak - cum
        if dd > best[0]:
            best = (dd, peak_day, d)
    depth, pk, tr = best
    if tr is None:
        return 0.0, None, None, []
    ep = [r for r in rows if (pk is None or r["exit_date"] > pk) and r["exit_date"] <= tr]
    return depth, pk, tr, ep


def dd_shares(episode, depth, key="R") -> dict:
    """{group: (share of the episode's R, share of its positions)}."""
    n = len(episode)
    tot = sum(r[key] for r in episode)
    out = {}
    for g in ALL_GROUPS:
        gr = [r for r in episode if r["group"] == g]
        out[g] = ((sum(r[key] for r in gr) / tot) if tot else float("nan"),
                  (len(gr) / n) if n else float("nan"))
    return out


def gt4_sums(rows, key="R") -> tuple[float, float]:
    """(summed R over the seven groups, summed R over the book) — GT4."""
    return (sum(sum(r[key] for r in rows if r["group"] == g) for g in ALL_GROUPS),
            sum(r[key] for r in rows))


def half_of(d: str) -> str:
    return f"{d[:4]}H{1 if int(d[5:7]) <= 6 else 2}"


def top_ticker(rows) -> tuple[str | None, float]:
    c = Counter(r["ticker"] for r in rows)
    if not c:
        return None, float("nan")
    t, k = c.most_common(1)[0]
    return t, k / len(rows)


def sign(x) -> int:
    if x is None or x != x or x == 0:
        return 0
    return 1 if x > 0 else -1


def cramers_v(rows, a_key, b_key) -> float:
    av = sorted({r[a_key] for r in rows})
    bv = sorted({r[b_key] for r in rows})
    if len(av) < 2 or len(bv) < 2:
        return float("nan")
    M = np.zeros((len(av), len(bv)))
    for r in rows:
        M[av.index(r[a_key]), bv.index(r[b_key])] += 1
    n = M.sum()
    E = M.sum(1, keepdims=True) * M.sum(0, keepdims=True) / n
    chi2 = ((M - E) ** 2 / np.where(E > 0, E, 1)).sum()
    return float(math.sqrt(chi2 / n / (min(M.shape) - 1)))


# ════════════════════════════════════════════════════════════════════════════
# One contrast
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Contrast:
    key: str
    label: str
    a: list                     # G1 rows
    b: list                     # comparison rows
    b_name: str
    standardised: bool
    min_pos_b: int = MIN_POS
    graded: bool = True
    weights: dict = field(default_factory=dict)
    raw_mix: dict = field(default_factory=dict)
    dropped: list = field(default_factory=list)
    res: dict = field(default_factory=dict)


def power(rows) -> tuple[int, int]:
    return len(rows), len({r["date"] for r in rows})


def evaluate(c: Contrast, quick: bool = False) -> dict:
    """Everything criterion 1-6 needs, except Holm and criterion 3 (book-level)."""
    strat = strat_of(c.standardised)
    if c.standardised:
        c.weights, c.raw_mix, c.dropped = direction_weights(c.a, c.b)
    else:
        c.weights, c.raw_mix, c.dropped = {"all": 1.0}, {"all": 1.0}, []
    na, da = power(c.a)
    nb, db = power(c.b)
    under = []
    if da < MIN_DATES or na < MIN_POS:
        under.append(f"G1 side {na} pos / {da} dates (needs {MIN_POS} / {MIN_DATES})")
    if db < MIN_DATES or nb < c.min_pos_b:
        under.append(f"{c.b_name} side {nb} pos / {db} dates (needs {c.min_pos_b} / {MIN_DATES})")
    if not c.weights:
        under.append("every direction stratum dropped (< 30 dates)")
    res = dict(na=na, da=da, nb=nb, db=db, underpowered=under)
    w = c.weights
    if not w:
        c.res = res
        return res
    res["mean_a"] = std_point(c.a, w, strat)
    res["mean_b"] = std_point(c.b, w, strat)
    res["diff"] = diff_point(c.a, c.b, w, strat)
    res["mean_a_g"] = std_point(c.a, w, strat, "Rg")
    res["mean_b_g"] = std_point(c.b, w, strat, "Rg")
    res["diff_g"] = res["mean_a_g"] - res["mean_b_g"]
    res["hit_a"] = std_point(c.a, w, strat, "hit")
    res["hit_b"] = std_point(c.b, w, strat, "hit")
    res["hit_diff"] = res["hit_a"] - res["hit_b"]
    draws, dropped = joint_boot(c.a, c.b, w, strat, "R")
    res["draws"], res["boot_dropped"] = draws, dropped
    res["ci"] = pct_ci(draws)
    res["p"] = boot_p(draws)
    hd, _ = joint_boot(c.a, c.b, w, strat, "hit")
    res["hit_ci"] = pct_ci(hd)
    if quick:
        c.res = res
        return res
    # per-side raw meanR CIs, protocol's own bootstrap
    in_w = [r for r in c.a if strat(r) in w]
    in_wb = [r for r in c.b if strat(r) in w]
    res["ci_a_raw"] = P.boot_ci_by_date(in_w, key="R")
    res["ci_b_raw"] = P.boot_ci_by_date(in_wb, key="R")
    res["raw_a"] = mean(r["R"] for r in in_w)
    res["raw_b"] = mean(r["R"] for r in in_wb)
    s0 = sign(res["diff"])
    # criterion 4: windows + years
    wins = {}
    ca_, cb_ = P.window_cuts(c.a), P.window_cuts(c.b)
    for name in P.DOMINANT_WINDOWS:
        wins[name] = diff_point(ca_[name], cb_[name], w, strat)
    years = {}
    ya, yb = P.by_year(c.a), P.by_year(c.b)
    for y in sorted(set(ya) | set(yb)):
        ra, rb = ya.get(y, []), yb.get(y, [])
        years[y] = (len(ra), len(rb),
                    diff_point(ra, rb, w, strat) if len(ra) >= YEAR_MIN_POS and len(rb) >= YEAR_MIN_POS
                    else None)
    q_years = {y: v[2] for y, v in years.items() if v[2] is not None}
    c4 = (s0 != 0 and all(sign(v) == s0 for v in wins.values())
          and all(sign(v) == s0 for v in q_years.values()))
    # criterion 5: half-years
    ha, hb = defaultdict(list), defaultdict(list)
    for r in c.a:
        ha[half_of(r["date"])].append(r)
    for r in c.b:
        hb[half_of(r["date"])].append(r)
    halves = {}
    for h in sorted(set(ha) | set(hb)):
        ra, rb = ha.get(h, []), hb.get(h, [])
        halves[h] = (len(ra), len(rb),
                     diff_point(ra, rb, w, strat) if len(ra) >= YEAR_MIN_POS and len(rb) >= YEAR_MIN_POS
                     else None)
    q_h = [v[2] for v in halves.values() if v[2] is not None]
    kept_h = sum(1 for v in q_h if sign(v) == s0)
    c5 = bool(q_h) and s0 != 0 and kept_h / len(q_h) >= HALF_SHARE
    # criterion 6: top ticker of each side removed
    ta, sha = top_ticker(c.a)
    tb, shb = top_ticker(c.b)
    d6 = diff_point([r for r in c.a if r["ticker"] != ta], [r for r in c.b if r["ticker"] != tb], w, strat)
    c6 = s0 != 0 and sign(d6) == s0
    res.update(wins=wins, years=years, c4=c4, halves=halves, half_kept=(kept_h, len(q_h)), c5=c5,
               top=(ta, sha, tb, shb), d6=d6, c6=c6, s0=s0)
    # baselines
    res["diff_prod"] = diff_point(c.a, c.b, w, strat, "Rprod")
    ab_a = [r for r in c.a if r["tier"] in ("A", "B")]
    ab_b = [r for r in c.b if r["tier"] in ("A", "B")]
    res["ab"] = (len(ab_a), len(ab_b), std_point(ab_a, w, strat), std_point(ab_b, w, strat),
                 diff_point(ab_a, ab_b, w, strat))
    c.res = res
    return res


def verdict_for(c: Contrast, c1_pos: bool, c1_neg: bool, c2: bool, c3: bool,
                pbo_val: float, mix_clear: bool, ci_clear: bool) -> str:
    q = "" if c.key == "P1" else f" vs {c.b_name}"
    res = c.res
    if res["underpowered"]:
        return f"UNDERPOWERED{q}"
    if pbo_val is None or pbo_val != pbo_val or pbo_val > PBO_VETO:
        return f"NULL{q} (PBO {pbo_val:.3f} > {PBO_VETO:.2f}: no group-level verdict ships)"
    fragile = " — selection fragile" if pbo_val > PBO_SUPPORT else ""
    c4, c5, c6 = res["c4"], res["c5"], res["c6"]
    if c1_pos and c2 and c3 and c4 and c5 and c6:
        return f"INDEX-MORE-RELIABLE{q}{fragile}"
    if c1_neg and c4 and c5 and c6:
        return f"INDEX-LESS-RELIABLE (CONTRARY){q}{fragile}"
    if c1_pos and c2 and c3:
        failed = [str(k) for k, ok in ((4, c4), (5, c5), (6, c6)) if not ok]
        return f"NULL{q} (criteria 1-3 met; failed criterion {', '.join(failed)})"
    if mix_clear and not ci_clear:
        return f"MIX-ONLY{q}"
    return f"NULL{q}"


# ════════════════════════════════════════════════════════════════════════════
# PBO / CSCV
# ════════════════════════════════════════════════════════════════════════════

def month_span(first: str, last: str) -> list[str]:
    y, m = int(first[:4]), int(first[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def monthly_matrix(rows, groups, weights, months) -> np.ndarray:
    """T x N x 2: [standardised monthly meanR, present?]; a blank stays blank."""
    M = np.zeros((len(months), len(groups), 2))
    mi = {mo: i for i, mo in enumerate(months)}
    gi = {g: j for j, g in enumerate(groups)}
    cells = defaultdict(list)
    for r in rows:
        if r["group"] in gi and r["date"][:7] in mi and r["dir"] in weights:
            cells[(r["date"][:7], r["group"])].append(r)
    for (mo, g), rs in cells.items():
        v = std_point(rs, weights, lambda r: r["dir"])
        if v == v:
            M[mi[mo], gi[g], 0] = v
            M[mi[mo], gi[g], 1] = 1.0
    return M


def trim_to_multiple(months: list[str], S: int) -> tuple[list[str], list[str]]:
    k = len(months) % S
    return months[k:], months[:k]


def run_cscv(rows, groups, weights, months):
    kept, trimmed = trim_to_multiple(months, CSCV_S)
    M = monthly_matrix(rows, groups, weights, kept)
    res = PBO.cscv(M, S=CSCV_S, metric=PBO.ratio_metric)
    full = PBO.ratio_metric(M)
    return res, kept, trimmed, full, M


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def hdr(t):
    print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)


def sub(t):
    print("\n" + f"--- {t} ".ljust(100, "-"))


def f3(x, sgn=True):
    if x is None or x != x:
        return "   n/a"
    return f"{x:+.3f}" if sgn else f"{x:.3f}"


def fpct(x):
    return "  n/a" if x is None or x != x else f"{100 * x:4.0f}%"


def short(g):
    return g.split("_")[0] if g != S_NAME else S_NAME


def print_census(ins):
    sub("Census, in-sample (reprints the registration's plan-time counts for THIS window)")
    print(f"  {'group':12} {'positions':>9} {'dates':>6} {'tickers':>7}  largest ticker      "
          f"{'bear':>5} {'bull':>5} {'neut':>5} {'other':>5}  bear%  debitV%  tierC%  tierA")
    for g in ALL_GROUPS:
        rs = [r for r in ins if r["group"] == g]
        if not rs:
            print(f"  {g:12} {0:>9}")
            continue
        n, d = power(rs)
        tk, sh = top_ticker(rs)
        dc = Counter(r["dir"] for r in rs)
        dv = sum(1 for r in rs if r["structure"] in ("bull_call_spread", "bear_put_spread"))
        tc = Counter(r["tier"] for r in rs)
        print(f"  {g:12} {n:>9} {d:>6} {len({r['ticker'] for r in rs}):>7}  {tk:6} {fpct(sh):>5}       "
              f"{dc['bear']:>5} {dc['bull']:>5} {dc['neutral']:>5} {dc['other']:>5}  {fpct(dc['bear'] / n)} "
              f"   {fpct(dv / n)}   {fpct(tc['C'] / n)}  {tc['A']:>5}")
    graded = [r for r in ins if r["dir"] in ("bear", "bull")]
    print(f"  Cramér's V (in-sample, bear+bull rows): group x direction "
          f"{cramers_v(graded, 'group', 'dir'):.2f}; group x tier {cramers_v(ins, 'group', 'tier'):.2f}")
    sub("Cell power, in-sample: positions (dates); x = below 30 dates")
    print(f"  {'group':12} {'bear':>14} {'bull':>14} {'tier B':>14} {'tier C':>14} {'tier A':>14}")

    def cell(rs):
        n, d = power(rs)
        return f"{n} ({d}){' x' if d < MIN_DATES else '  '}"
    for g in GRADED_GROUPS:
        rs = [r for r in ins if r["group"] == g]
        print(f"  {g:12} {cell([r for r in rs if r['dir'] == 'bear']):>14} "
              f"{cell([r for r in rs if r['dir'] == 'bull']):>14} "
              f"{cell([r for r in rs if r['tier'] == 'B']):>14} "
              f"{cell([r for r in rs if r['tier'] == 'C']):>14} "
              f"{cell([r for r in rs if r['tier'] == 'A']):>14}")
    g1 = [r for r in ins if r["group"] == G1]
    if g1:
        dc = Counter(r["dir"] for r in g1 if r["dir"] in ("bear", "bull"))
        tot = sum(dc.values()) or 1
        print(f"  G1's own bear/bull mix (the P1 weights before any stratum drop): "
              f"bear {dc['bear'] / tot:.3f} / bull {dc['bull'] / tot:.3f} (n={tot})")
    other = Counter(r["structure"] for r in ins if r["dir"] == "other")
    if other:
        print(f"  structures outside the direction rule (never graded): {dict(other)}")


def print_contrast(c: Contrast, holm_info=None):
    res = c.res
    print(f"\n  {c.key}  {c.label}")
    print(f"    power: G1 {res['na']} pos / {res['da']} dates; {c.b_name} {res['nb']} pos / {res['db']} dates"
          + (f"   GT0 UNDERPOWERED: {'; '.join(res['underpowered'])}" if res["underpowered"] else "   GT0 pass"))
    if c.standardised:
        print(f"    weights: G1 raw mix {', '.join(f'{k} {v:.3f}' for k, v in c.raw_mix.items())}; "
              f"used {', '.join(f'{k} {v:.3f}' for k, v in c.weights.items()) or 'NONE'}"
              + (f"; dropped {'; '.join(c.dropped)}" if c.dropped else ""))
    if not c.weights:
        return
    print(f"    meanR NET   G1 {f3(res['mean_a'])}  {c.b_name} {f3(res['mean_b'])}  diff {f3(res['diff'])}  "
          f"CI95 [{f3(res['ci'][0])}, {f3(res['ci'][1])}]  p={res['p']:.4f}"
          + (f"  (bootstrap draws discarded: {res['boot_dropped']})" if res["boot_dropped"] else ""))
    if holm_info:
        padj, rank, lvl, hci = holm_info
        print(f"    Holm: rank {rank}, level {lvl:.4f}, adjusted p={padj:.4f}, "
              f"CI at Holm level [{f3(hci[0])}, {f3(hci[1])}]")
    print(f"    meanR GROSS G1 {f3(res['mean_a_g'])}  {c.b_name} {f3(res['mean_b_g'])}  diff {f3(res['diff_g'])}")
    if "ci_a_raw" in res:
        print(f"    per-side raw meanR (protocol.boot_ci_by_date): G1 {f3(res['raw_a'])} "
              f"[{f3(res['ci_a_raw'][0])}, {f3(res['ci_a_raw'][1])}]  {c.b_name} {f3(res['raw_b'])} "
              f"[{f3(res['ci_b_raw'][0])}, {f3(res['ci_b_raw'][1])}]")
    print(f"    hit rate    G1 {f3(res['hit_a'], False)}  {c.b_name} {f3(res['hit_b'], False)}  "
          f"diff {f3(res['hit_diff'])}  CI95 [{f3(res['hit_ci'][0])}, {f3(res['hit_ci'][1])}]")
    if "wins" not in res:
        return
    print("    windows: " + "  ".join(f"{k} {f3(v)}" for k, v in res["wins"].items()))
    print("    years (G1 n / comp n / diff, graded when both >= 10): "
          + "  ".join(f"{y} {a}/{b}/{f3(d) if d is not None else 'not graded'}"
                      for y, (a, b, d) in res["years"].items()))
    halves = "  ".join(f"{h} {a}/{b}/{f3(d) if d is not None else '-'}"
                       for h, (a, b, d) in res["halves"].items())
    print(f"    half-years: {halves}"
          f"   sign kept {res['half_kept'][0]} of {res['half_kept'][1]}")
    ta, sha, tb, shb = res["top"]
    print(f"    concentration: drop {ta} ({fpct(sha).strip()} of G1) and {tb} ({fpct(shb).strip()} of "
          f"{c.b_name}) -> diff {f3(res['d6'])}")
    print(f"    DEBIT_PROD replay (gross; credit rows CREDIT_PROD): diff {f3(res['diff_prod'])}   "
          f"shipped tiers A/B only: G1 n={res['ab'][0]} {f3(res['ab'][2])}  {c.b_name} n={res['ab'][1]} "
          f"{f3(res['ab'][3])}  diff {f3(res['ab'][4])}")


def criteria_line(c, c1p, c1n, c2, c3):
    r = c.res

    def ok(b):
        return "MET" if b else "not met"
    return (f"    criteria: 1 {ok(c1p)}{' (negative side: MET)' if c1n else ''} | 2 {ok(c2)} | 3 {ok(c3)} | "
            f"4 {ok(r['c4'])} | 5 {ok(r['c5'])} | 6 {ok(r['c6'])}")


def main(argv=None) -> int:
    # A named reader of the holdout seal: forward dates after FORWARD_AFTER;
    # the sealed gap stays withheld, as ruling 5 wants (holdout_seal.md).
    recs, diag = load_book(sealed_read="ticker_class")
    era = diag.get("era")
    v3 = era == "v3"
    hdr(f"ticker_class — index ETFs vs single-stock groups, direction held fixed   [era {era}]"
        + ("   v3 REPLICATION (same path)" if v3 else ""))
    print("  Registration: research/pre-registrations/f1_selection/ticker_class.md (2026-10-07, IMMUTABLE)")
    print(f"  GT1 era: load_book() resolved era '{era}'  ({len(recs)} rows, {diag.get('n_dates')} dates, "
          f"{diag.get('date_range')})")
    print("  LEDGER (selection ledger, outside the 'three new arms' cap; also printed in the feasibility "
          "ledger): ticker_class — 1 configuration (group table groups_v1, sha256 "
          f"{GROUPS_V1_SHA256[:8]}…), 5 graded trials: P1 S1 S2 S3 S4; registered 2026-10-07")

    # GT3
    h = table_hash()
    print(f"  GT3 blind order: group-table sha256 {h}")
    if h != GROUPS_V1_SHA256 or not h.startswith(REGISTERED_HASH_PREFIX):
        print(f"  GT3 FAIL: expected {GROUPS_V1_SHA256} (registration: {REGISTERED_HASH_PREFIX}…)")
        return 1
    print(f"  GT3 pass (matches the registration's {REGISTERED_HASH_PREFIX}…)")

    rows, counts = prepare(recs)
    print(f"  dropped: fill_trusted false {counts['fill_untrusted']}; R missing {counts['R_missing']}. "
          f"cost_total non-blank {counts['cost_total_nonblank']}, blank {counts['cost_total_blank']} "
          f"(gross = net where blank). exit dates clamped to the bounded grid: {counts['exit_clamped']}")
    for r in rows:
        r["Rprod"] = prod_replay_R(r["_rec"])
    n_prod_fail = sum(1 for r in rows if r["Rprod"] is None)
    tier_agree = sum(1 for r in rows if r["tier"] == r["tier_book"])
    print(f"  tier: mapping.ladder_tier agrees with the loader's port on {tier_agree} of {len(rows)} rows; "
          f"DEBIT_PROD/CREDIT_PROD replay failures {n_prod_fail}")

    ins = [r for r in rows if r["date"] < IN_SAMPLE_BEFORE]
    gap = [r for r in rows if IN_SAMPLE_BEFORE <= r["date"] <= FORWARD_AFTER]
    fwd = [r for r in rows if r["date"] > FORWARD_AFTER]
    print(f"  windows: in-sample (< {IN_SAMPLE_BEFORE}) {len(ins)} rows / {len({r['date'] for r in ins})} dates; "
          f"excluded gap {len(gap)} rows / {len({r['date'] for r in gap})} dates; forward (> {FORWARD_AFTER}) "
          f"{len(fwd)} rows / {len({r['date'] for r in fwd})} dates")
    if not ins:
        print("  no in-sample rows")
        return 1

    # GT2
    bad = {t: explicit_memberships(t) for t in {r["ticker"] for r in ins}}
    bad = {t: m for t, m in bad.items() if len(m) > 1}
    first_seen = {}
    for r in rows:
        first_seen[r["ticker"]] = min(first_seen.get(r["ticker"], r["date"]), r["date"])
    new_t = sorted(t for t, d in first_seen.items() if d > ACCEPTED)
    print(f"  GT2 map: {len({r['ticker'] for r in ins})} in-sample tickers; multiply-listed: {bad or 'none'}; "
          f"newly assigned (first seen after {ACCEPTED}): {', '.join(f'{t}->{group_of(t)}' for t in new_t) or 'none'}")
    if bad:
        print("  GT2 FAIL")
        return 1
    g7 = sorted({r["ticker"] for r in ins if r["group"] == G7})
    print(f"  G7 tickers in-sample ({len(g7)}, by default rule): {' '.join(g7)}")

    # GT4
    by_g, book = gt4_sums(ins)
    print(f"  GT4 reconcile: summed R over groups {by_g:.12f} vs book {book:.12f} (|diff| {abs(by_g - book):.2e})")
    if abs(by_g - book) > GT4_TOL:
        print("  GT4 FAIL")
        return 1

    sub("Build readings (where the registration left a mechanic open)")
    for i, line in enumerate(BUILD_READINGS, 1):
        print(f"  R{i:02d}. {line}")

    print_census(ins)

    graded = [r for r in ins if r["dir"] in ("bear", "bull")]

    def grp(g, d=None, pop=graded):
        gs = SINGLE_STOCK if g == S_NAME else (g,)
        return [r for r in pop if r["group"] in gs and (d is None or r["dir"] == d)]

    contrasts = [Contrast("P1", "G1 vs S, direction-standardised (bear + bull)" + (
        " — on v3 in effect the bear stratum" if v3 else ""), grp(G1), grp(S_NAME), S_NAME, True)]
    contrasts += [Contrast(k, f"G1 vs {short(g)}, bear only", grp(G1, "bear"), grp(g, "bear"), short(g), False)
                  for k, g in (("S1", G5), ("S2", G6), ("S3", G7))]
    if not v3:
        contrasts.append(Contrast("S4", "G1 vs G2, bull only", grp(G1, "bull"), grp(G2, "bull"), "G2", False,
                                  min_pos_b=MIN_POS_S4_G2))
    for c in contrasts:
        evaluate(c)

    # book maxDD episode (criterion 3)
    depth, pk, tr, ep = maxdd_episode(ins)
    shares = dd_shares(ep, depth)
    g1_dd, g1_pos = shares[G1]
    c3 = (g1_pos != g1_pos) or (g1_dd != g1_dd) or g1_dd <= g1_pos
    sub("Drawdown share — the in-sample book's maxDD episode on R summed by exit date")
    print(f"  episode: after peak {pk or '(start)'} through trough {tr}; depth {depth:.3f} R; "
          f"{len(ep)} positions exit inside it")
    for g in ALL_GROUPS:
        s, p = shares[g]
        print(f"    {g:12} share of episode R {fpct(s)}   share of episode positions {fpct(p)}")
    print(f"  criterion 3 (G1 share {fpct(g1_dd).strip()} <= its position share {fpct(g1_pos).strip()}): "
          f"{'MET' if c3 else 'not met'}")

    # PBO
    months = month_span(min(r["date"] for r in ins)[:7], IN_SAMPLE_LAST_DAY[:7])
    p1 = contrasts[0]
    pbo_w = p1.weights or {"bear": 1.0}
    hdr("PBO / CSCV — the selection 'pick the best group'")
    pres, kept, trimmed, full, M = run_cscv(graded, GRADED_GROUPS, pbo_w, months)
    blanks = {short(g): int((M[:, j, 1] == 0).sum()) for j, g in enumerate(GRADED_GROUPS)}
    print(f"  T = {len(kept)} months ({kept[0]} .. {kept[-1]}); trimmed earliest {trimmed or 'none'}; "
          f"S = {CSCV_S}; combinations {pres.n_combinations}; weights {pbo_w}")
    print(f"  blank (no position) months per group: {blanks}")
    _print_pbo(pres, GRADED_GROUPS, full)
    pbo_val = pres.pbo
    if pbo_val > PBO_VETO:
        reading = "> 0.50: no group-level verdict ships; every graded contrast reads NULL"
    elif pbo_val > PBO_SUPPORT:
        reading = "0.25-0.50: verdicts print with 'selection fragile'"
    else:
        reading = "<= 0.25: supports a verdict"
    print(f"  READING: PBO {pbo_val:.3f} {reading}")
    sub("Diagnostic: bear stratum alone, N = G1, G5, G6, G7")
    bear_rows = [r for r in graded if r["dir"] == "bear"]
    bres, bkept, btrim, bfull, bM = run_cscv(bear_rows, BEAR_PBO_GROUPS, {"bear": 1.0}, months)
    print(f"  T = {len(bkept)} months; blank months per group: "
          f"{ {short(g): int((bM[:, j, 1] == 0).sum()) for j, g in enumerate(BEAR_PBO_GROUPS)} }")
    _print_pbo(bres, BEAR_PBO_GROUPS, bfull)

    # Holm across the secondaries
    secs = [c for c in contrasts if c.key.startswith("S") and c.weights]
    hinfo = holm({c.key: c.res["p"] for c in secs})
    holm_ci = {}
    for c in secs:
        padj, rank, lvl = hinfo[c.key]
        holm_ci[c.key] = (padj, rank, lvl, pct_ci(c.res["draws"], lvl))

    # pooled unadjusted G1-vs-comparison (MIX-ONLY basis)
    def pooled(bname):
        gs = SINGLE_STOCK if bname == S_NAME else (dict((short(g), g) for g in ALL_GROUPS)[bname],)
        a = [r for r in ins if r["group"] == G1]
        b = [r for r in ins if r["group"] in gs]
        d, _ = joint_boot(a, b, {"all": 1.0}, strat_of(False))
        return diff_point(a, b, {"all": 1.0}, strat_of(False)), pct_ci(d), len(a), len(b)

    hdr("GRADED CONTRASTS — P1 (primary), S1-S4 (secondary, Holm across the four)"
        if not v3 else "GRADED CONTRASTS (v3 replication: P1, S1-S3; Holm across the three)")
    verdicts = {}
    for c in contrasts:
        print_contrast(c, holm_ci.get(c.key))
        if not c.weights:
            verdicts[c.key] = f"UNDERPOWERED{'' if c.key == 'P1' else ' vs ' + c.b_name}"
            print(f"    VERDICT {c.key}: {verdicts[c.key]}")
            continue
        if c.key == "P1":
            lo, hi = c.res["ci"]
            c1p, c1n = lo > 0, hi < 0
        else:
            padj, _rank, _lvl, (lo, hi) = holm_ci[c.key]
            c1p = padj < ALPHA and lo > 0
            c1n = padj < ALPHA and hi < 0
        c2 = c.res["hit_diff"] >= 0 and c.res["hit_ci"][1] > 0
        pdiff, pci, pna, pnb = pooled(c.b_name)
        mix_clear = pci[0] > 0 or pci[1] < 0
        print(f"    pooled unadjusted G1 vs {c.b_name} (all directions, n {pna}/{pnb}): diff {f3(pdiff)} "
              f"CI95 [{f3(pci[0])}, {f3(pci[1])}]")
        print(criteria_line(c, c1p, c1n, c2, c3))
        verdicts[c.key] = verdict_for(c, c1p, c1n, c2, c3, pbo_val, mix_clear, c1p or c1n)
        print(f"    VERDICT {c.key}: {verdicts[c.key]}")

    if not v3:
        hdr("PRINTED, NEVER GRADED — T1, T2, C0, R1")
        t1 = Contrast("T1", "G1 vs S, tier C only, direction-standardised",
                      [r for r in grp(G1) if r["tier"] == "C"], [r for r in grp(S_NAME) if r["tier"] == "C"],
                      S_NAME, True, graded=False)
        t2 = Contrast("T2", "G1 vs S, tier B only",
                      [r for r in grp(G1) if r["tier"] == "B"], [r for r in grp(S_NAME) if r["tier"] == "B"],
                      S_NAME, False, graded=False)
        real = [r for r in graded if r["source"] == "real"]
        r1 = Contrast("R1", "real rows only, P1 repeated",
                      grp(G1, pop=real), grp(S_NAME, pop=real), S_NAME, True, graded=False)
        for c in (t1, t2, r1):
            evaluate(c, quick=(c.key != "R1"))
            print_contrast(c)
        sub("C0 — all seven groups, pooled, unadjusted (every in-sample direction)")
        print(f"  {'group':12} {'n':>5} {'dates':>6} {'meanR':>7}  {'CI95':>17}  {'gross':>7}  {'hit':>6}  "
              f"{'bear meanR':>10} {'bull meanR':>10}")
        for g in ALL_GROUPS:
            rs = [r for r in ins if r["group"] == g]
            if not rs:
                continue
            lo, hi = P.boot_ci_by_date(rs, key="R")
            print(f"  {g:12} {len(rs):>5} {len({r['date'] for r in rs}):>6} {f3(mean(r['R'] for r in rs)):>7}  "
                  f"[{f3(lo)}, {f3(hi)}]  {f3(mean(r['Rg'] for r in rs)):>7}  "
                  f"{f3(mean(r['hit'] for r in rs), False):>6}  "
                  f"{f3(mean(r['R'] for r in rs if r['dir'] == 'bear')):>10} "
                  f"{f3(mean(r['R'] for r in rs if r['dir'] == 'bull')):>10}")
        pdiff, pci, pna, pnb = pooled(S_NAME)
        print(f"  C0 G1 vs S pooled unadjusted: diff {f3(pdiff)} CI95 [{f3(pci[0])}, {f3(pci[1])}] (n {pna}/{pnb})")

    hdr("PATH — median MFE, median MAE, exit capture (R / MFE where MFE > 0), per group; reported, never graded")
    print(f"  {'group':12} {'dir':5} {'n':>5} {'medMFE':>7} {'medMAE':>7} {'n MFE>0':>8} "
          f"{'med capture':>11} {'ΣR/ΣMFE':>8}")
    for g in ALL_GROUPS:
        for d in ("all", "bear", "bull"):
            rs = [r for r in ins if r["group"] == g and (d == "all" or r["dir"] == d)]
            if not rs:
                continue
            mf = [r["mfe"] for r in rs if r["mfe"] is not None]
            ma = [r["mae"] for r in rs if r["mae"] is not None]
            pos = [r for r in rs if r["mfe"] is not None and r["mfe"] > 0]
            cap = [r["R"] / r["mfe"] for r in pos]
            pooled_cap = (sum(r["R"] for r in pos) / sum(r["mfe"] for r in pos)) if pos else float("nan")
            print(f"  {g:12} {d:5} {len(rs):>5} {f3(statistics.median(mf) if mf else None):>7} "
                  f"{f3(statistics.median(ma) if ma else None):>7} {len(pos):>8} "
                  f"{f3(statistics.median(cap) if cap else None):>11} {f3(pooled_cap):>8}")

    sub("Shipped-rule baseline — the shipped top-3/day ladder book (mapping tiers A/B), in-sample")
    pick = P.top_k_per_day(ins, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)
    st = P.replay_stats(pick)
    gc = Counter(r["group"] for r in pick)
    print(f"  {st['n']} picks / {st['dates']} dates, meanR {f3(st['mean_R'])}, win {f3(st['win'], False)}; "
          f"by group {dict(sorted((short(g), n) for g, n in gc.items()))}")

    if not v3:
        hdr("FORWARD READ — P1 on signal dates after 2026-10-07, criteria 1-3")
        fg = [r for r in fwd if r["dir"] in ("bear", "bull")]
        fa, fb = grp(G1, pop=fg), grp(S_NAME, pop=fg)
        da_, db_ = len({r["date"] for r in fa}), len({r["date"] for r in fb})
        print(f"  forward: G1 {len(fa)} positions / {da_} dates; S {len(fb)} positions / {db_} dates")
        if da_ < FWD_MIN_DATES or db_ < FWD_MIN_DATES:
            print(f"  FORWARD P1: STILL-OPEN (each side needs {FWD_MIN_DATES} forward dates)")
        else:
            fc = Contrast("P1-fwd", "forward P1", fa, fb, S_NAME, True)
            evaluate(fc, quick=True)
            fdepth, _, _, fep = maxdd_episode(fwd)
            fs = dd_shares(fep, fdepth)[G1]
            f1 = fc.weights and fc.res["ci"][0] > 0
            f2 = fc.weights and fc.res["hit_diff"] >= 0 and fc.res["hit_ci"][1] > 0
            f3_ = (fs[0] != fs[0]) or (fs[1] != fs[1]) or fs[0] <= fs[1]
            print_contrast(fc)
            print(f"  FORWARD P1: {'FORWARD-CONFIRMED' if (f1 and f2 and f3_) else 'FORWARD-REFUTED'} "
                  f"(criteria 1 {f1}, 2 {f2}, 3 {f3_})")

    hdr("VERDICTS" + (" — v3 replication (same path); notes agreement only, confirms nothing" if v3 else ""))
    for k, v in verdicts.items():
        print(f"  {k:3} {('v3 replication (same path): ' if v3 else '')}{v}")
    print(f"  PBO {pbo_val:.3f} (graded N=5)  |  bear-stratum diagnostic PBO {bres.pbo:.3f}")
    print("  Nothing ships from this study. INDEX-MORE-RELIABLE or CONTRARY files a 'to be tested' entry in "
          "research/deployment-evidence.md.")
    return 0


def _print_pbo(res, groups, full):
    share = res.selection_share()
    names = [short(g) for g in groups]
    modal = names[int(np.argmax(share))]
    full_best = names[int(np.nanargmax(np.where(np.isnan(full), -np.inf, full)))]
    below = float(np.mean(res.logits < 0))
    print(f"  PBO {res.pbo:.3f} (lambda <= 0; {res.n_at_zero} combinations exactly at the median)")
    print(f"  P(IS argmax lands below the OOS median, lambda < 0 strictly) {below:.3f}")
    print(f"  IS argmax: most often {modal}; share of combinations each group is IS-best: "
          + "  ".join(f"{n} {s:.3f}" for n, s in zip(names, share)))
    print("  full-window statistic (mean of non-blank monthly cells): "
          + "  ".join(f"{n} {f3(v)}" for n, v in zip(names, full)) + f"   -> argmax {full_best}")
    pl = "n/a" if res.prob_loss is None else f"{res.prob_loss:.3f}"
    print(f"  degradation slope {res.slope:+.3f}; P(OOS meanR of the IS pick < 0) {pl}")


if __name__ == "__main__":
    sys.exit(main())
