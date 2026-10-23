"""ticker_pattern — do the ten most-traded names carry an effect of their own, week, direction and side held fixed?

PRE-REGISTERED 2026-10-23:
research/pre-registrations/f1_selection/benchmark/ticker_pattern.md. This module
implements that file literally; every constant below is the registration's.

What it grades. Ten fixed names (5 ETFs, 5 stocks). P1 is one omnibus
permutation test: inside each (ISO week, direction, side) stratum holding two or
more names, R is turned into a van Elteren rank score, each name's scores are
summed (S_t), and T = sum_t S_t^2 / n_t is compared with 20,000 within-stratum
label permutations. P2 (per-name, Holm m=10, split-half) is graded only when P1
reads TICKER-EFFECT. A CSCV read over "pick the best name" vetoes both.

Population. `load_book(include_pending=True)`, every other argument at its
default (real + strike_expiry_tweak, bs excluded, calibration on). This study is
NOT a named reader of the holdout seal, so signal dates from 2026-09-23 stay
withheld. Pending rows, fill_trusted-false rows and rows with no R are dropped
here, with per-name counts printed.

Nothing ships from this study. Usage:

    python3 -m scripts.backtest_study run ticker_pattern
    python3 -m scripts.backtest_study run ticker_pattern --era v3   # replication
"""
from __future__ import annotations

import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection.benchmark import ticker_class as TC  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import format_pending, load_book, norm_play  # noqa: E402

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# ════════════════════════════════════════════════════════════════════════════
# Constants fixed by the registration
# ════════════════════════════════════════════════════════════════════════════
REGISTERED = "2026-10-23"
ETFS = ("IWM", "SMH", "TLT", "QQQ", "GLD")
STOCKS = ("NVDA", "TSLA", "META", "MU", "AMD")
TEN = ETFS + STOCKS
N_NAMES = len(TEN)
NAME_IDX = {t: i for i, t in enumerate(TEN)}
NEXT_NAMES = {"SPY": 31, "HYG": 30, "AAPL": 27}   # next by the rule, excluded

N_PERM = 20000
SEED = 20261023                 # P1, P2 and every sensitivity
POWER_SEED = 20261024           # GP2
DESIGN_SEED = 20261025          # the design-power table
PERM_CHUNK = 500
ALPHA = 0.05

MIN_ROWS = 30                   # the floor: informative rows ...
MIN_DATES = 20                  # ... on this many distinct signal dates
GP0_MIN_NAMES = 8
GP0_MIN_NAMES_V3 = 4
GP1_MIN_SHARE = 0.60
POWER_SIMS = 200
POWER_PERMS = 500
PLANT_R = 0.50
POWER_BAR = 0.80
HALF_MIN_ROWS = 15

QUAL_WINDOW_P = 0.10            # X-2025 / X-2026 qualifier
QUAL_SENS_P = 0.20              # S-DATE / S-MONTH qualifier

# Declared locally; tests/test_ticker_pattern.py pins them equal to ticker_class's.
CSCV_S = 16
PBO_SUPPORT = 0.25
PBO_VETO = 0.50

DESIGN_NOISE_SD = 0.8
DESIGN_TAPE_SD = 0.5
DESIGN_ONE = (0.20, 0.35, 0.50)
DESIGN_SPREAD = (0.15, 0.20)

LAG_LIVE_MAX = 1
LAG_NEAR_MAX = 7
LAG_CLASSES = ("LIVE", "NEAR", "RETRO", "UNKNOWN")
TRIM = 0.10                     # trimmed meanR, each tail
MECH_MIN = 10                   # mech_cell cells under this are hidden
TOL = 1e-9

# ════════════════════════════════════════════════════════════════════════════
# Row preparation
# ════════════════════════════════════════════════════════════════════════════


def iso_week(d: str) -> str:
    y, w, _ = date.fromisoformat(str(d)[:10]).isocalendar()
    return f"{y:04d}-W{w:02d}"


def lag_class(created, analysis_date: str) -> str:
    """LIVE / NEAR / RETRO / UNKNOWN from the analysis row's created_datetime."""
    if created is None or (isinstance(created, float) and created != created):
        return "UNKNOWN"
    s = str(created).strip()
    if not s or s.lower() == "nan":
        return "UNKNOWN"
    try:
        lag = (date.fromisoformat(s[:10]) - date.fromisoformat(str(analysis_date)[:10])).days
    except ValueError:
        return "UNKNOWN"
    if lag < 0:
        return "UNKNOWN"
    if lag <= LAG_LIVE_MAX:
        return "LIVE"
    if lag <= LAG_NEAR_MAX:
        return "NEAR"
    return "RETRO"


def _float(v):
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def path_class(status) -> str:
    s = str(status or "").strip()
    return {"complete": "complete", "carried": "carried", "open_at_data_end": "cap_open",
            "": "blank"}.get(s, s)


def analysis_created_lookup():
    """join_key -> created_datetime of the first-written AnalysisClaude row.

    The join `lib/book.py::_build_analysis_lookup` makes, re-done here because
    the record does not carry the analysis row: (date, ticker, 60-char play
    prefix), sorted by created_datetime, first kept. The analysis export is read
    with the holdout seal applied, like every other export a study opens.
    """
    import pandas as pd

    path = era_mod.resolve_paths()["analysis"]
    if not path.exists():
        return {}, {"rows": 0, "dates": 0, "reader": None}, str(path)
    ac = pd.read_csv(path, usecols=lambda c: c in ("date", "ticker", "play", "created_datetime"))
    ac, info = era_mod.drop_sealed_frame(ac, "date")
    if not {"date", "ticker", "play"} <= set(ac.columns) or "created_datetime" not in ac.columns:
        return {}, info, str(path)
    ac = ac.copy()
    ac["_cdt"] = pd.to_datetime(ac["created_datetime"], errors="coerce")
    ac["_jk"] = (ac["date"].astype(str) + "|" + ac["ticker"].astype(str)
                 + "|" + ac["play"].apply(norm_play))
    ac = ac.sort_values("_cdt").drop_duplicates(subset="_jk", keep="first")
    return dict(zip(ac["_jk"], ac["created_datetime"])), info, str(path)


def join_key(rec) -> str:
    return f"{rec['date']}|{rec['ticker']}|{norm_play(rec['t'].row.get('play', ''))}"


def prepare(recs, created: dict):
    """(loaded counts, outcome rows, per-name drop counts).

    Outcome rows = the ten names' records minus pending, fill_trusted false and
    R missing, in that order; every direction kept (the descriptive table).
    """
    loaded, drops, out = Counter(), Counter(), []
    lag_loaded = Counter()
    for r in recs:
        t = str(r["ticker"]).upper().strip()
        if t not in NAME_IDX:
            continue
        loaded[t] += 1
        lag = lag_class(created.get(join_key(r)), r["date"])
        lag_loaded[(t, lag)] += 1
        if r.get("pending"):
            drops[(t, "pending")] += 1
            continue
        if not r.get("fill_trusted", True):
            drops[(t, "fill_untrusted")] += 1
            continue
        if r.get("R") is None:
            drops[(t, "R_missing")] += 1
            continue
        row = r["t"].row
        credit = bool(r["credit"])
        out.append(dict(
            date=r["date"], week=iso_week(r["date"]), month=r["date"][:7], ticker=t,
            name=NAME_IDX[t], dir=TC.direction(r["structure"]), credit=credit,
            side="credit" if credit else "debit", R=float(r["R"]),
            ror=_float(row.get("pnl_on_risk_pct")), source=r["source"],
            path=path_class(row.get("path_status")), structure=r["structure"],
            dte=r.get("dte"), days_held=r.get("days_held"), mech_cell=r.get("mech_cell") or "",
            exit_reason=r.get("exit_reason") or "", lag=lag))
    return loaded, out, drops, lag_loaded


# ════════════════════════════════════════════════════════════════════════════
# Strata, scores, permutations
# ════════════════════════════════════════════════════════════════════════════

def stratum_scores(codes, values) -> np.ndarray:
    """a_i = midrank_i / (n_s + 1) - 0.5 inside each stratum (van Elteren).

    Ranks ascend in `values`; tied values share their average rank. Sums to 0
    in every stratum.
    """
    codes = np.asarray(codes)
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n == 0:
        return np.zeros(0)
    order = np.lexsort((values, codes))
    c, v = codes[order], values[order]
    new_s = np.r_[True, c[1:] != c[:-1]]
    s_start = np.maximum.accumulate(np.where(new_s, np.arange(n), 0))
    new_g = new_s | np.r_[True, v[1:] != v[:-1]]
    g_first = np.flatnonzero(new_g)
    g_last = np.r_[g_first[1:] - 1, n - 1]
    g_rank = (g_first + g_last) / 2.0 - s_start[g_first] + 1.0
    ranks = g_rank[np.cumsum(new_g) - 1]
    s_id = np.cumsum(new_s) - 1
    n_s = np.bincount(s_id)[s_id]
    out = np.empty(n)
    out[order] = ranks / (n_s + 1.0) - 0.5
    return out


def stratum_demean(codes, values) -> np.ndarray:
    """R minus its stratum's mean R (the mean-scale score)."""
    codes = np.asarray(codes)
    values = np.asarray(values, dtype=float)
    if not len(values):
        return np.zeros(0)
    sums = np.bincount(codes, weights=values)
    cnt = np.bincount(codes)
    return values - (sums / np.where(cnt > 0, cnt, 1))[codes]


@dataclass
class Design:
    """One stratification of a row set, restricted to informative strata."""
    key: str
    rows: list                 # informative rows, sorted by stratum
    codes: np.ndarray          # stratum code per row, ascending
    labels: np.ndarray         # name index per row
    R: np.ndarray
    a: np.ndarray              # rank scores
    dm: np.ndarray             # mean-scale scores
    n_graded: int
    n_strata: int
    n_inf_strata: int

    @property
    def n_inf(self) -> int:
        return len(self.rows)

    @property
    def share(self) -> float:
        return self.n_inf / self.n_graded if self.n_graded else float("nan")

    @property
    def n_t(self) -> np.ndarray:
        return np.bincount(self.labels, minlength=N_NAMES)

    def dates_t(self) -> np.ndarray:
        d = defaultdict(set)
        for r in self.rows:
            d[r["name"]].add(r["date"])
        return np.array([len(d[i]) for i in range(N_NAMES)])

    def floor_ok(self) -> np.ndarray:
        return (self.n_t >= MIN_ROWS) & (self.dates_t() >= MIN_DATES)


def build_design(rows, key_fn, key: str = "") -> Design:
    by = defaultdict(list)
    for r in rows:
        by[key_fn(r)].append(r)
    inf = sorted((k for k, rs in by.items() if len({x["name"] for x in rs}) >= 2),
                 key=lambda k: tuple(str(x) for x in k))
    out, codes = [], []
    for c, k in enumerate(inf):
        for r in sorted(by[k], key=lambda r: (r["name"], r["date"], r["structure"], r["R"])):
            out.append(r)
            codes.append(c)
    codes = np.array(codes, dtype=int)
    labels = np.array([r["name"] for r in out], dtype=int)
    R = np.array([r["R"] for r in out], dtype=float)
    return Design(key=key, rows=out, codes=codes, labels=labels, R=R,
                  a=stratum_scores(codes, R), dm=stratum_demean(codes, R),
                  n_graded=len(rows), n_strata=len(by), n_inf_strata=len(inf))


def name_sums(labels, weights) -> np.ndarray:
    return np.bincount(np.asarray(labels, dtype=int), weights=np.asarray(weights, dtype=float),
                       minlength=N_NAMES)


def t_stat(S, n_t) -> np.ndarray | float:
    """T = sum_t S_t^2 / n_t over names with n_t > 0 (works on a draws matrix)."""
    S = np.asarray(S, dtype=float)
    m = np.asarray(n_t) > 0
    if not m.any():
        return np.zeros(S.shape[:-1]) if S.ndim > 1 else 0.0
    out = (S[..., m] ** 2 / np.asarray(n_t)[m]).sum(axis=-1)
    return out if S.ndim > 1 else float(out)


def perm_draws(codes, labels, weights, n_perm: int, rng, chunk: int = PERM_CHUNK) -> np.ndarray:
    """(k, n_perm, N_NAMES) per-name sums under within-stratum label permutation.

    `codes` must be sorted ascending. One draw is argsort(code + U(0,1)): every
    stratum's labels are shuffled and none leaves its stratum.
    """
    codes = np.asarray(codes)
    labels = np.asarray(labels, dtype=int)
    W = np.atleast_2d(np.asarray(weights, dtype=float))
    k, n = W.shape
    out = np.zeros((k, n_perm, N_NAMES))
    if n == 0:
        return out
    base = codes.astype(float)
    done = 0
    while done < n_perm:
        m = min(chunk, n_perm - done)
        perm = np.argsort(base[None, :] + rng.random((m, n)), axis=1)
        lp = labels[perm]
        idx = (lp + N_NAMES * np.arange(m)[:, None]).ravel()
        for j in range(k):
            out[j, done:done + m] = np.bincount(
                idx, weights=np.tile(W[j], m), minlength=m * N_NAMES).reshape(m, N_NAMES)
        done += m
    return out


def perm_p(stat: float, draws) -> float:
    draws = np.asarray(draws, dtype=float)
    hit = (draws >= stat - TOL * max(1.0, abs(stat))).sum()
    return float((1 + hit) / (1 + len(draws)))


def omnibus(d: Design, n_perm: int = N_PERM, seed: int = SEED) -> dict:
    n_t = d.n_t
    S, Sm = name_sums(d.labels, d.a), name_sums(d.labels, d.dm)
    T, Tm = t_stat(S, n_t), t_stat(Sm, n_t)
    rng = np.random.default_rng(seed)
    draws = perm_draws(d.codes, d.labels, np.vstack([d.a, d.dm]) if d.n_inf else np.zeros((2, 0)),
                       n_perm, rng)
    Ts, Tms = t_stat(draws[0], n_t), t_stat(draws[1], n_t)
    p_t = (1 + (np.abs(draws[0]) >= np.abs(S) - TOL).sum(axis=0)) / (1 + n_perm)
    return dict(T=T, p=perm_p(T, Ts), Tm=Tm, pm=perm_p(Tm, Tms), S=S, Sm=Sm, n_t=n_t,
                p_t=p_t, null_mean=float(np.mean(Ts)) if len(Ts) else float("nan"))


def median_n_name(n_t) -> int:
    """The lower median (5th of 10) by informative n, ascending, ties alphabetical."""
    order = sorted(range(N_NAMES), key=lambda i: (int(n_t[i]), TEN[i]))
    return order[(N_NAMES - 1) // 2]


def planted_power(d: Design, target: int, plant: float = PLANT_R, sims: int = POWER_SIMS,
                  perms: int = POWER_PERMS, seed: int = POWER_SEED) -> float:
    """GP2: share of sims detecting `plant` on `target` at p <= ALPHA.

    Each sim permutes the real R within strata (removing any real name
    effect), adds `plant` to the target's rows, rescores, and runs `perms`
    within-stratum permutations.
    """
    if not d.n_inf:
        return 0.0
    rng = np.random.default_rng(seed)
    n, n_t = d.n_inf, d.n_t
    bump = plant * (d.labels == target)
    hits = 0
    for _ in range(sims):
        Rs = d.R[np.argsort(d.codes + rng.random(n))] + bump
        a = stratum_scores(d.codes, Rs)
        T = t_stat(name_sums(d.labels, a), n_t)
        Ts = t_stat(perm_draws(d.codes, d.labels, a, perms, rng)[0], n_t)
        hits += perm_p(T, Ts) <= ALPHA
    return hits / sims


def synthetic_power(d: Design, effect_fn, sims: int = POWER_SIMS, perms: int = POWER_PERMS,
                    seed: int = DESIGN_SEED) -> float:
    """DP: power on synthetic outcomes over the real strata; no outcome read.

    R = weekly tape shock N(0, 0.5^2) + t4 noise scaled to SD 0.8 + effect_fn(rng)[name].
    """
    if not d.n_inf:
        return 0.0
    rng = np.random.default_rng(seed)
    n, n_t = d.n_inf, d.n_t
    _, wcode = np.unique([r["week"] for r in d.rows], return_inverse=True)
    n_w = int(wcode.max()) + 1
    scale = DESIGN_NOISE_SD / math.sqrt(2.0)        # Var(t4) = 2
    hits = 0
    for _ in range(sims):
        R = (rng.normal(0.0, DESIGN_TAPE_SD, n_w)[wcode] + rng.standard_t(4, n) * scale
             + np.asarray(effect_fn(rng), dtype=float)[d.labels])
        a = stratum_scores(d.codes, R)
        T = t_stat(name_sums(d.labels, a), n_t)
        Ts = t_stat(perm_draws(d.codes, d.labels, a, perms, rng)[0], n_t)
        hits += perm_p(T, Ts) <= ALPHA
    return hits / sims


def split_halves(weeks) -> tuple[set, set]:
    """H1 = the first floor(W/2) distinct ISO weeks in calendar order, H2 the rest."""
    ws = sorted(set(weeks))
    k = len(ws) // 2
    return set(ws[:k]), set(ws[k:])


def theta_rows(d: Design) -> list[dict]:
    """Per informative row: R minus the mean R of the OTHER names in its stratum."""
    tot = defaultdict(float)
    cnt = defaultdict(int)
    tot_n = defaultdict(float)
    cnt_n = defaultdict(int)
    for c, r in zip(d.codes, d.rows):
        tot[c] += r["R"]
        cnt[c] += 1
        tot_n[(c, r["name"])] += r["R"]
        cnt_n[(c, r["name"])] += 1
    out = []
    for c, r in zip(d.codes, d.rows):
        k = (c, r["name"])
        peers = cnt[c] - cnt_n[k]
        out.append(dict(date=r["date"], name=r["name"],
                        theta=r["R"] - (tot[c] - tot_n[k]) / peers))
    return out


# ════════════════════════════════════════════════════════════════════════════
# Verdict logic
# ════════════════════════════════════════════════════════════════════════════

def p1_verdict(failed_gates, pbo_val, p) -> tuple[str, str]:
    """(token, note). Order: UNDERPOWERED, then the PBO veto, then NULL, then TICKER-EFFECT."""
    if failed_gates:
        return "UNDERPOWERED", "failed " + ", ".join(failed_gates)
    if pbo_val is None or pbo_val != pbo_val or pbo_val > PBO_VETO:
        shown = "not computable" if pbo_val is None or pbo_val != pbo_val else f"{pbo_val:.3f} > {PBO_VETO:.2f}"
        return "NULL", f"PBO veto ({shown}); no name flagged"
    if p > ALPHA:
        return "NULL", f"p = {p:.4f} > {ALPHA}"
    return "TICKER-EFFECT", ("selection fragile" if pbo_val > PBO_SUPPORT else "")


def sign(x) -> int:
    if x is None or x != x or abs(x) <= TOL:
        return 0
    return 1 if x > 0 else -1


def flag_status(graded: bool, floor_ok: bool, adj_p: float, n_h: tuple, s_h: tuple,
                s_full: float, s_real: float) -> str:
    """P2 status for one name: FLAGGED / NOT REPLICABLE / NOT FLAGGED (...) / not graded."""
    if not graded:
        return "not graded"
    if min(n_h) < HALF_MIN_ROWS:
        return "NOT REPLICABLE"
    failed = []
    if not floor_ok:
        failed.append("2 floor")
    if not adj_p < ALPHA:
        failed.append("3 Holm")
    s0 = sign(s_full)
    if s0 == 0 or sign(s_h[0]) != s0 or sign(s_h[1]) != s0:
        failed.append("5 half signs")
    if s0 == 0 or sign(s_real) != s0:
        failed.append("6 real-only sign")
    return "FLAGGED" if not failed else f"NOT FLAGGED ({', '.join(failed)})"


def pbo_matrix(d: Design, months: list[str]) -> np.ndarray:
    """T x 10 x 2: [sum of scores, count] per (month, name); a blank stays [0, 0]."""
    mi = {m: i for i, m in enumerate(months)}
    M = np.zeros((len(months), N_NAMES, 2))
    for r, a in zip(d.rows, d.a):
        i = mi.get(r["month"])
        if i is None:
            continue
        M[i, r["name"], 0] += a
        M[i, r["name"], 1] += 1.0
    return M


def std_matrix(rows, weights: dict, months: list[str]) -> np.ndarray:
    """T x 10 x 2: [direction-standardised meanR, present] per (month, name)."""
    mi = {m: i for i, m in enumerate(months)}
    cells = defaultdict(list)
    for r in rows:
        if r["month"] in mi and r["dir"] in weights:
            cells[(r["month"], r["name"])].append(r)
    M = np.zeros((len(months), N_NAMES, 2))
    for (mo, j), rs in cells.items():
        v = TC.std_point(rs, weights, lambda r: r["dir"])
        if v == v:
            M[mi[mo], j, 0] = v
            M[mi[mo], j, 1] = 1.0
    return M


def run_cscv(M):
    if M.shape[0] < CSCV_S or M.shape[0] % CSCV_S:
        return None
    return PBO.cscv(M, S=CSCV_S, metric=PBO.ratio_metric)


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
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
    return "  n/a" if x is None or x != x else f"{100 * x:3.0f}%"


def fp(p):
    return "  n/a " if p is None or p != p else f"{p:.4f}"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else float("nan")


def median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else float("nan")


def trimmed_mean(xs, frac: float = TRIM):
    xs = sorted(x for x in xs if x is not None)
    k = int(math.floor(frac * len(xs)))
    core = xs[k:len(xs) - k] if len(xs) > 2 * k else []
    return statistics.fmean(core) if core else float("nan")


def print_pbo(res, names, full):
    if res is None:
        print("  PBO not computable (fewer than 16 months after trimming)")
        return
    share = res.selection_share()
    modal = names[int(np.argmax(share))]
    finite = np.where(np.isnan(full), -np.inf, full)
    full_best = names[int(np.argmax(finite))]
    below = float(np.mean(res.logits < 0))
    print(f"  PBO {res.pbo:.3f} (lambda <= 0; {res.n_at_zero} combinations exactly at the median); "
          f"P(lambda < 0 strictly) {below:.3f}; combinations {res.n_combinations}")
    print("  IS-best share per name: " + "  ".join(f"{n} {s:.3f}" for n, s in zip(names, share))
          + f"   (most often {modal})")
    print("  full-window statistic: " + "  ".join(f"{n} {f3(v)}" for n, v in zip(names, full))
          + f"   -> argmax {full_best}")
    pl = "n/a" if res.prob_loss is None else f"{res.prob_loss:.3f}"
    print(f"  degradation slope {res.slope:+.3f}; P(OOS statistic of the IS pick < 0) {pl}")


def pbo_reading(v) -> str:
    if v is None or v != v:
        return "not computable: veto"
    if v > PBO_VETO:
        return "> 0.50: veto"
    if v > PBO_SUPPORT:
        return "0.25-0.50: selection fragile"
    return "<= 0.25: supports a verdict"


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

KEY_PRIMARY = ("strata (ISO week, direction, side)", lambda r: (r["week"], r["dir"], r["side"]))
KEY_DATE = ("strata (date, direction)", lambda r: (r["date"], r["dir"]))
KEY_MONTH = ("strata (month, direction, side)", lambda r: (r["month"], r["dir"], r["side"]))


def main(argv=None) -> int:
    recs, diag = load_book(include_pending=True)
    era = diag.get("era")
    v3 = era == "v3"
    tag = "v3 replication (same ten names)" if v3 else "PRIMARY"
    hdr(f"ticker_pattern — per-name effect among ten fixed names, week/direction/side held fixed   "
        f"[era {era}]   {tag}")
    print(f"  Registration: research/pre-registrations/f1_selection/benchmark/ticker_pattern.md "
          f"(registered {REGISTERED})")
    print(f"  era: load_book() resolved '{era}' ({len(recs)} rows, {diag.get('n_dates')} dates, "
          f"{diag.get('date_range')})")
    print(f"  {era_mod.seal_line(diag['seal'])}  [this study is not a seal reader]")
    print(f"  {format_pending(diag['pending'])}")
    print(f"  ten names (ETFs {', '.join(ETFS)}; stocks {', '.join(STOCKS)}); next by the rule, excluded: "
          + ", ".join(f"{t} ({n})" for t, n in NEXT_NAMES.items()))
    if v3:
        print("  v3 R predates the cost model (gross); v3 path_status is blank, so R-COMPLETE is empty.")

    created, ainfo, apath = analysis_created_lookup()
    print(f"  analysis join for the lag class: {Path(apath).name}, {len(created)} join keys; "
          f"{era_mod.seal_line(ainfo)}")

    loaded, desc, drops, lag_loaded = prepare(recs, created)
    graded = [r for r in desc if r["dir"] in ("bull", "bear")]

    sub("Population per name: loaded -> outcome rows -> graded (bull/bear) -> informative")
    prim = build_design(graded, KEY_PRIMARY[1], KEY_PRIMARY[0])
    n_t, d_t, floor = prim.n_t, prim.dates_t(), prim.floor_ok()
    print(f"  {'name':5} {'loaded':>6} {'pend':>5} {'untr':>5} {'noR':>4} {'outcome':>7} {'neut/oth':>8} "
          f"{'graded':>6} {'inform':>6} {'dates':>5} {'floor':>5}")
    for i, t in enumerate(TEN):
        nd = sum(1 for r in desc if r["ticker"] == t)
        ng = sum(1 for r in graded if r["ticker"] == t)
        print(f"  {t:5} {loaded[t]:>6} {drops[(t, 'pending')]:>5} {drops[(t, 'fill_untrusted')]:>5} "
              f"{drops[(t, 'R_missing')]:>4} {nd:>7} {nd - ng:>8} {ng:>6} {n_t[i]:>6} {d_t[i]:>5} "
              f"{'yes' if floor[i] else 'NO':>5}")
    print(f"  total: loaded {sum(loaded.values())}, outcome {len(desc)}, graded {len(graded)}, "
          f"informative {prim.n_inf} ({fpct(prim.share).strip()}); strata {prim.n_strata}, "
          f"informative strata {prim.n_inf_strata}")

    # ── D0 descriptive ────────────────────────────────────────────────────
    hdr("D0 — DESCRIPTIVE, one row per name (outcome rows, every direction); never graded")
    print(f"  {'name':5} {'n':>4} {'res/twk':>8} {'cmpl/carr/cap/blank':>20} {'pend%':>5} "
          f"{'bull%':>5} {'bear%':>5} {'neut%':>5} {'cred%':>5}  top-2 structures")
    for t in TEN:
        rs = [r for r in desc if r["ticker"] == t]
        n = len(rs)
        if not n:
            print(f"  {t:5} {0:>4}")
            continue
        src = Counter(r["source"] for r in rs)
        pc = Counter(r["path"] for r in rs)
        dc = Counter(r["dir"] for r in rs)
        top = Counter(r["structure"] for r in rs).most_common(2)
        print(f"  {t:5} {n:>4} {src['real']:>3}/{src['tweak']:<4} "
              f"{pc['complete']:>6}/{pc['carried']}/{pc['cap_open']}/{pc['blank']:<5} "
              f"{fpct(drops[(t, 'pending')] / loaded[t] if loaded[t] else None):>5} "
              f"{fpct(dc['bull'] / n):>5} {fpct(dc['bear'] / n):>5} "
              f"{fpct((n - dc['bull'] - dc['bear']) / n):>5} {fpct(sum(r['credit'] for r in rs) / n):>5}  "
              + ", ".join(f"{s} {k}" for s, k in top))
    print()
    print(f"  {'name':5} {'win':>5} {'meanR':>7} {'medR':>7} {'trim10':>7} {'meanRoR':>7} {'medDTE':>6} "
          f"{'medHeld':>7}  {'LIVE/NEAR/RETRO/UNK (outcome)':>30}  {'(loaded)':>18}")
    for t in TEN:
        rs = [r for r in desc if r["ticker"] == t]
        if not rs:
            continue
        Rs = [r["R"] for r in rs]
        lc = Counter(r["lag"] for r in rs)
        ll = "/".join(str(lag_loaded[(t, c)]) for c in LAG_CLASSES)
        print(f"  {t:5} {fpct(sum(1 for x in Rs if x > 0) / len(Rs)):>5} {f3(mean(Rs)):>7} "
              f"{f3(median(Rs)):>7} {f3(trimmed_mean(Rs)):>7} {f3(mean(r['ror'] for r in rs)):>7} "
              f"{median(r['dte'] for r in rs):>6.0f} {median(r['days_held'] for r in rs):>7.0f}  "
              f"{'/'.join(str(lc[c]) for c in LAG_CLASSES):>30}  {ll:>18}")
    print()
    print(f"  meanR by mech_cell (cells under {MECH_MIN} rows hidden) | exit-reason mix")
    for t in TEN:
        rs = [r for r in desc if r["ticker"] == t]
        if not rs:
            continue
        cells = defaultdict(list)
        for r in rs:
            cells[r["mech_cell"]].append(r["R"])
        shown = "  ".join(f"{c} {f3(mean(v))} ({len(v)})" for c, v in sorted(cells.items())
                          if len(v) >= MECH_MIN) or "(none >= 10)"
        ex = Counter(r["exit_reason"] or "?" for r in rs).most_common(4)
        print(f"  {t:5} {shown}")
        print("        exits: " + "  ".join(f"{e} {fpct(k / len(rs)).strip()}" for e, k in ex))
    lag_inf = Counter((r["ticker"], r["lag"]) for r in prim.rows)
    print("  informative rows by lag class (LIVE/NEAR/RETRO/UNK): "
          + "  ".join(f"{t} {'/'.join(str(lag_inf[(t, c)]) for c in LAG_CLASSES)}" for t in TEN))

    # ── Gates ─────────────────────────────────────────────────────────────
    hdr("GATES — GP0 power, GP1 informative share, GP2 planted power")
    gp0_bar = GP0_MIN_NAMES_V3 if v3 else GP0_MIN_NAMES
    n_floor = int(floor.sum())
    gp0 = n_floor >= gp0_bar
    gp1 = prim.n_graded > 0 and prim.share >= GP1_MIN_SHARE
    target = median_n_name(n_t)
    power = planted_power(prim, target)
    gp2 = power >= POWER_BAR
    print(f"  GP0: {n_floor} of 10 names clear the floor ({MIN_ROWS} informative rows on {MIN_DATES} dates); "
          f"bar {gp0_bar}{' (v3)' if v3 else ''} -> {'pass' if gp0 else 'FAIL'}   "
          f"[below: {', '.join(t for i, t in enumerate(TEN) if not floor[i]) or 'none'}]")
    print(f"  GP1: informative share {prim.n_inf}/{prim.n_graded} = {f3(prim.share, False)}; bar "
          f"{GP1_MIN_SHARE:.2f} -> {'pass' if gp1 else 'FAIL'}")
    print(f"  GP2: +{PLANT_R:.2f} R planted on the median-n name {TEN[target]} (n={n_t[target]}); detected "
          f"in {power:.3f} of {POWER_SIMS} sims ({POWER_PERMS} perms each, seed {POWER_SEED}); bar "
          f"{POWER_BAR:.2f} -> {'pass' if gp2 else 'FAIL'}")
    failed = [g for g, ok in (("GP0", gp0), ("GP1", gp1), ("GP2", gp2)) if not ok]

    # ── P1 ────────────────────────────────────────────────────────────────
    hdr("P1 — OMNIBUS over the ten names, strata (ISO week, direction, side); graded")
    res = omnibus(prim)
    print(f"  T = {res['T']:.4f} (permutation-null mean {res['null_mean']:.4f}); p = {fp(res['p'])}   "
          f"[N_PERM {N_PERM}, seed {SEED}, p = (1 + #T* >= T)/(1 + N_PERM)]")
    print(f"  mean-scale T (R minus stratum mean; printed, never graded) = {res['Tm']:.3f}; p = {fp(res['pm'])}")
    print(f"  {'name':5} {'n_t':>4} {'dates':>5} {'S_t':>8} {'S_t/n_t':>8} {'meanscale/n':>11} {'p_t':>7}")
    for i, t in enumerate(TEN):
        nt = n_t[i]
        print(f"  {t:5} {nt:>4} {d_t[i]:>5} {res['S'][i]:>+8.3f} "
              f"{(res['S'][i] / nt if nt else float('nan')):>+8.3f} "
              f"{(res['Sm'][i] / nt if nt else float('nan')):>+11.3f} {fp(res['p_t'][i]):>7}")

    sub("Sensitivities and window cuts — each rebuilds its strata, same draw settings")
    cuts = P.window_cuts(graded)
    sens = [
        ("S-DATE", KEY_DATE, graded, QUAL_SENS_P),
        ("S-MONTH", KEY_MONTH, graded, QUAL_SENS_P),
        ("X-2025", KEY_PRIMARY, cuts["ex_2025_mar_apr"], QUAL_WINDOW_P),
        ("X-2026", KEY_PRIMARY, cuts["ex_2026_feb_apr"], QUAL_WINDOW_P),
        ("R-REAL", KEY_PRIMARY, [r for r in graded if r["source"] == "real"], None),
        ("R-COMPLETE", KEY_PRIMARY, [r for r in graded if r["path"] == "complete"], None),
    ]
    print("  (a qualifier attaches only to a TICKER-EFFECT headline; it never changes the token)")
    print(f"  {'object':10} {'strata':34} {'graded':>6} {'inform':>6} {'share':>5} {'floor':>5} "
          f"{'T':>9} {'p':>7}  qualifier")
    sens_res, quals, real_design = {}, [], None
    for name, (klabel, kfn), rows, qbar in sens:
        dd = build_design(rows, kfn, klabel)
        if name == "R-REAL":
            real_design = dd
        if not dd.n_inf:
            print(f"  {name:10} {klabel:34} {len(rows):>6} {0:>6}   not evaluable (no informative stratum)")
            sens_res[name] = None
            continue
        rr = omnibus(dd)
        sens_res[name] = rr
        trip = qbar is not None and rr["p"] > qbar
        if trip:
            quals.append(f"{name} p {rr['p']:.3f} > {qbar:.2f}")
        qtxt = "printed only" if qbar is None else (f"trips (p > {qbar:.2f})" if trip else f"clear (p <= {qbar:.2f})")
        print(f"  {name:10} {klabel:34} {dd.n_graded:>6} {dd.n_inf:>6} {fpct(dd.share):>5} "
              f"{int(dd.floor_ok().sum()):>5} {rr['T']:>9.3f} {fp(rr['p']):>7}  {qtxt}")

    # ── DP design power ────────────────────────────────────────────────────
    sub("DP — design power on synthetic outcomes over the real informative strata (no outcome read)")
    print(f"  R = weekly tape N(0, {DESIGN_TAPE_SD}^2) + t4 noise SD {DESIGN_NOISE_SD} + effect; "
          f"{POWER_SIMS} sims x {POWER_PERMS} perms, seed {DESIGN_SEED}; power = share with p <= {ALPHA}")
    scen = []
    for x in DESIGN_ONE:
        def one(rng, x=x):
            e = np.zeros(N_NAMES)
            e[target] = x
            return e
        scen.append((f"one name ({TEN[target]}) +{x:.2f} R", one))
    for sd in DESIGN_SPREAD:
        scen.append((f"cross-name spread SD {sd:.2f}", lambda rng, sd=sd: rng.normal(0.0, sd, N_NAMES)))
    for label, fn in scen:
        print(f"  {label:34} power {synthetic_power(prim, fn):.3f}")

    # ── PBO ───────────────────────────────────────────────────────────────
    hdr("PBO / CSCV — the selection 'pick the best name'")
    months = TC.month_span(min(r["month"] for r in prim.rows), max(r["month"] for r in prim.rows)) \
        if prim.n_inf else []
    kept, trimmed = TC.trim_to_multiple(months, CSCV_S)
    M = pbo_matrix(prim, kept)
    pres = run_cscv(M)
    pbo_val = pres.pbo if pres is not None else float("nan")
    blanks = {t: int((M[:, j, 1] == 0).sum()) for j, t in enumerate(TEN)}
    print(f"  T = {len(kept)} months ({kept[0] if kept else '-'} .. {kept[-1] if kept else '-'}); trimmed "
          f"earliest {trimmed or 'none'}; S = {CSCV_S}; cell = [sum of scores, count]")
    print(f"  blank (no informative row) months per name: {blanks}")
    print_pbo(pres, list(TEN), PBO.ratio_metric(M) if len(kept) else np.full(N_NAMES, np.nan))
    print(f"  READING: PBO {f3(pbo_val, False).strip()} {pbo_reading(pbo_val)}")
    sub("PBO-D — diagnostic: direction-standardised monthly meanR per name (graded rows); printed only")
    dirs = Counter(r["dir"] for r in graded)
    tot = sum(dirs.values()) or 1
    w = {k: dirs[k] / tot for k in ("bear", "bull") if dirs[k]}
    gmonths = TC.month_span(min(r["month"] for r in graded), max(r["month"] for r in graded)) if graded else []
    gkept, _ = TC.trim_to_multiple(gmonths, CSCV_S)
    MD = std_matrix(graded, w, gkept)
    dres = run_cscv(MD)
    print(f"  weights {', '.join(f'{k} {v:.3f}' for k, v in w.items())}; T = {len(gkept)} months")
    print_pbo(dres, list(TEN), PBO.ratio_metric(MD) if len(gkept) else np.full(N_NAMES, np.nan))

    # ── P2 ────────────────────────────────────────────────────────────────
    p1_token, p1_note = p1_verdict(failed, pbo_val, res["p"])
    p2_graded = p1_token == "TICKER-EFFECT"
    hdr("P2 — PER NAME (Holm m=10, split-half); " + ("graded" if p2_graded else "printed, not graded (P1 is "
                                                     f"{p1_token})"))
    hinfo = TC.holm({t: float(res["p_t"][i]) for i, t in enumerate(TEN)})
    h1, h2 = split_halves(r["week"] for r in prim.rows)
    S_real = name_sums(real_design.labels, real_design.a) if real_design is not None and real_design.n_inf \
        else np.zeros(N_NAMES)
    th = theta_rows(prim)
    hw = sorted(h1)
    print(f"  halves: H1 = {len(h1)} weeks ({hw[0] if hw else '-'} .. {hw[-1] if hw else '-'}), "
          f"H2 = {len(h2)} weeks; a name needs >= {HALF_MIN_ROWS} informative rows in each")
    print(f"  {'name':5} {'n_t':>4} {'S_t':>8} {'p_t':>7} {'Holm adj':>8} {'theta':>7} {'theta CI95':>17} "
          f"{'H1 n/S':>12} {'H2 n/S':>12} {'S real':>7}  status")
    flagged = []
    for i, t in enumerate(TEN):
        in_h1 = [(r, a) for r, a in zip(prim.rows, prim.a) if r["name"] == i and r["week"] in h1]
        in_h2 = [(r, a) for r, a in zip(prim.rows, prim.a) if r["name"] == i and r["week"] in h2]
        s1, s2 = sum(a for _, a in in_h1), sum(a for _, a in in_h2)
        tr = [x for x in th if x["name"] == i]
        tmean = mean(x["theta"] for x in tr)
        lo, hi = P.boot_ci_by_date(tr, key="theta") if tr else (float("nan"), float("nan"))
        adj = hinfo[t][0]
        st = flag_status(p2_graded, bool(floor[i]), adj, (len(in_h1), len(in_h2)), (s1, s2),
                         float(res["S"][i]), float(S_real[i]))
        if st == "FLAGGED":
            flagged.append(t)
        if not p2_graded:
            would = flag_status(True, bool(floor[i]), adj, (len(in_h1), len(in_h2)), (s1, s2),
                                float(res["S"][i]), float(S_real[i]))
            st = f"not graded (would read: {would})"
        print(f"  {t:5} {n_t[i]:>4} {res['S'][i]:>+8.3f} {fp(res['p_t'][i]):>7} {fp(adj):>8} {f3(tmean):>7} "
              f"[{f3(lo)}, {f3(hi)}] {len(in_h1):>4}/{s1:>+7.3f} {len(in_h2):>4}/{s2:>+7.3f} "
              f"{S_real[i]:>+7.3f}  {st}")
    print("  theta = R minus the mean R of the other names in the stratum; its CI conditions on the peers, so it "
          "is optimistic. The permutation p_t is the graded number.")

    # ── VERDICT ───────────────────────────────────────────────────────────
    hdr("VERDICT" + (" — v3 replication (same ten names); notes agreement only" if v3 else ""))
    head = p1_token
    extra = []
    if p1_token == "TICKER-EFFECT":
        if p1_note:
            extra.append(p1_note)
        if quals:
            extra.append("qualified: " + "; ".join(quals))
    elif p1_note:
        extra.append(p1_note)
    print(f">>> ticker_pattern P1 (omnibus, ten names, {era}): {head} <<<")
    if p2_graded:
        p2_text = ", ".join(f"FLAGGED {t}" for t in flagged) if flagged else "none flagged"
    else:
        p2_text = "none graded"
    print(f">>> ticker_pattern P2 (per-name, Holm m=10, split-half): {p2_text} <<<")
    print(f">>> ticker_pattern PBO (CSCV, pick-the-best-name): {f3(pbo_val, False).strip()} <<<")
    print(f"  P1 p = {fp(res['p'])} (T {res['T']:.3f}); {'; '.join(extra) if extra else 'no qualifier'}")
    print(f"  gates: GP0 {n_floor}/10 names at the floor (bar {gp0_bar}) {'pass' if gp0 else 'FAIL'}; "
          f"GP1 share {f3(prim.share, False)} {'pass' if gp1 else 'FAIL'}; "
          f"GP2 power {power:.3f} {'pass' if gp2 else 'FAIL'}")
    print(f"  PBO reading: {pbo_reading(pbo_val)}")
    if v3:
        print("  v3 replication (same ten names): same market path as v4, so it can note agreement with the "
              "v4 verdict only; never pooled with v4.")
    if p1_token == "TICKER-EFFECT":
        step3 = ("a second registration is written (next ten names, own omnibus and Holm family)"
                 if flagged else "file one 'to be tested' line in research/deployment-evidence.md; step 3 stops")
    elif p1_token == "NULL":
        step3 = "closes on these dates"
    else:
        step3 = "nothing concluded; re-run as the era accrues"
    print(f"  step 3: {step3}" + (" (decided on v4 only; this v3 line is for agreement)" if v3 else ""))
    print("  Nothing ships from this study.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
