"""direction_hit — does anything known at entry predict that the underlying moves the play's way?

REGISTERED 2026-10-12, accepted by default the same day, before the first run:
research/pre-registrations/f1_selection/signal/direction_hit.md. Every feature,
floor, seed and verdict word below is that file's. Read it before changing
anything here.

WHY IT EXISTS
-------------
A Tier A/B pick's R is mostly its underlying's own move over the hold (the
2026-10-12 exploratory read: R^2 0.47 on v4). The hit rate (how often the
underlying moves the way the play bets) is what decides R. This study asks
whether any of 17 entry-time features predicts it.

WHAT IT COMPUTES
----------------
Target. `hit` = 1 when direction x (C_exit / C_signal - 1) > 0. C_signal is the
underlying's close on the last bar on or before the SIGNAL date (never a later
bar); C_exit the close on the last bar on or before the exit day (the grid day
at `days_held`). Bars: `lib/underlying.load_bars`.

Method 1, univariate screen. Per feature, a hit-rate lift (binary: 1 minus 0;
number: top tercile minus bottom; category: between-level variance) with a
2,000-draw permutation p. Within-date features are shuffled inside each signal
date; across-dates features have their per-date value shuffled across dates.
Aligned features are re-aligned with each row's own direction after the
shuffle. BH over the 17 features per population and era.

Method 2, the graded model. L2 logistic, C = 1.0, all 17 features, one fold per
calendar month, trained only on rows whose signal date AND exit day precede the
month (`training_mask`). Six-month warm-up; a month with < 100 training rows or
one class is skipped. Graded by pooled out-of-sample AUC with a date-clustered
bootstrap CI:

    PREDICTS  v4 AUC CI lower bound > 0.5 and v3 walk-forward AUC > 0.5
    WEAK      v4 AUC CI lower bound > 0.5 and v3 AUC <= 0.5
    NULL      v4 AUC CI includes or lies below 0.5

Brier skill vs the training fold's base rate is printed beside it. PBO (CSCV,
S = 16) over 16 feature-group subsets is printed; the graded model is fixed,
so PBO does not move the verdict.

Forward: a model fitted on in-sample rows whose exit came before
`era.SEAL_START`, scored on v4 dates from it once the seal lifts. Floors 30
dates and 100 positions. Until then STILL-OPEN.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run direction_hit
"""
from __future__ import annotations

import csv
import math
import sys
from bisect import bisect_right
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import MechLabeler  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import ticker_class as TC  # noqa: E402
from scripts.backtest_study.f1_selection.regime import dip_buy as DB  # noqa: E402
from scripts.backtest_study.f1_selection.regime.regime_map import bh_q  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import pbo as pbo_mod  # noqa: E402
from scripts.backtest_study.lib import sectors  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402
from scripts.backtest_study.lib.book import MECH_TABLE_CSV, load_book  # noqa: E402
from scripts.backtest_study.lib.underlying_features import trailing_bars  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/signal/direction_hit.md"
ACCEPTED = "2026-10-12"

# --- registered constants ------------------------------------------------------
MAX_BAR_LAG_DAYS = 5          # a bar may sit at most this many calendar days before its date
SPLIT_ARTIFACT = U._SPLIT_ARTIFACT_PCT
RET_SESSIONS = 20             # F5 / F15: 20-session return (21 bars)
RET_SPAN_DAYS = 35
SMA_SESSIONS = 50             # F16
SMA_SPAN_DAYS = 80
FIXED_HORIZON = 10            # the descriptive 10-session hit
PERM_N = 2_000
PERM_SEED = 20261012
BOOT_N = 2_000
BOOT_SEED = 20260811
BH_Q = 0.05
C_DEFAULT = 1.0
C_ALT = 0.1
WARMUP_MONTHS = 6
MIN_TRAIN = 100
PBO_S = 16
FWD_MIN_DATES = 30
FWD_MIN_POS = 100
FORWARD_ERA = "v4"
REPLICATION_ERA = "v3"
INDEX_GROUP = "G1_index"

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# (id, name, kind, permuted, group)   kind: num / bin / cat; permuted: date / row
FEATURES = (
    ("F1", "model direction vs play", "cat", "date", "market"),
    ("F2", "model vol", "cat", "date", "market"),
    ("F3", "mech_cell", "cat", "date", "market"),
    ("F4", "SPY trend aligned", "bin", "date", "market"),
    ("F5", "SPY 20-session return, aligned", "num", "date", "market"),
    ("F6", "VIX close", "num", "date", "market"),
    ("F7", "score_total", "num", "row", "flow"),
    ("F8", "oi_confirm_pct", "num", "row", "flow"),
    ("F9", "cpir - 0.5, aligned", "num", "row", "flow"),
    ("F10", "iv_spread, aligned", "num", "row", "flow"),
    ("F11", "iv_skew, aligned against", "num", "row", "flow"),
    ("F12", "iv_pct", "num", "row", "flow"),
    ("F13", "DTE", "num", "row", "structure"),
    ("F14", "index ETF", "bin", "row", "structure"),
    ("F15", "own 20-session return, aligned", "num", "row", "underlying"),
    ("F16", "own close / 50-SMA - 1, aligned", "num", "row", "underlying"),
    ("F17", "sector", "cat", "row", "structure"),
)
FEATURE_IDS = tuple(f[0] for f in FEATURES)
SPEC = {f[0]: f for f in FEATURES}
GROUPS = ("market", "flow", "underlying", "structure")

PREDICTS, WEAK, NULL = "PREDICTS", "WEAK", "NULL"


# ════════════════════════════════════════════════════════════════════════════
# The target
# ════════════════════════════════════════════════════════════════════════════

def bar_on_or_before(bars: dict, d: date, max_lag: int = MAX_BAR_LAG_DAYS):
    """(bar date, Bar) for the last bar on or before `d`, within `max_lag` days."""
    days = [x for x in bars if x <= d]
    if not days:
        return None, None
    b = max(days)
    if (d - b).days > max_lag:
        return None, None
    return b, bars[b]


def hit_of(bars: dict, signal: date, exit_day: date, direction: int):
    """(hit, aligned return, drop reason). The start is the SIGNAL-date close.

    Never a later bar: the hit is measured from the close the analysis saw,
    so the overnight gap into the next-open entry counts toward it.
    """
    sd, sb = bar_on_or_before(bars, signal)
    if sb is None:
        return None, None, "no_signal_bar"
    ed, eb = bar_on_or_before(bars, exit_day)
    if eb is None or ed <= sd:
        return None, None, "no_exit_bar"
    ret = eb.c / sb.c - 1.0
    if (sb.source == U.SRC_TILDE or eb.source == U.SRC_TILDE) and abs(ret) > SPLIT_ARTIFACT:
        return None, None, "split_artifact"
    aligned = direction * ret
    return int(aligned > 0), aligned, None


def hit_fixed(bars: dict, signal: date, direction: int, n: int = FIXED_HORIZON):
    """The hit `n` sessions after the signal bar, or None when the bars run out."""
    sd, sb = bar_on_or_before(bars, signal)
    if sb is None:
        return None
    later = sorted(x for x in bars if x > sd)
    if len(later) < n:
        return None
    eb = bars[later[n - 1]]
    ret = eb.c / sb.c - 1.0
    if (sb.source == U.SRC_TILDE or eb.source == U.SRC_TILDE) and abs(ret) > SPLIT_ARTIFACT:
        return None
    return int(direction * ret > 0)


# ════════════════════════════════════════════════════════════════════════════
# Entry-time features
# ════════════════════════════════════════════════════════════════════════════

def own_return(bars: dict, signal: date, sessions: int = RET_SESSIONS,
               span: int = RET_SPAN_DAYS):
    """Close-to-close return over `sessions` sessions ending at the signal bar."""
    tb = trailing_bars(bars, signal, sessions + 1)
    if len(tb) < sessions + 1:
        return None
    days = sorted(x for x in bars if x <= signal)[-(sessions + 1):]
    if (days[-1] - days[0]).days > span or (signal - days[-1]).days > MAX_BAR_LAG_DAYS:
        return None
    return tb[-1].c / tb[0].c - 1.0


def own_sma_gap(bars: dict, signal: date, sessions: int = SMA_SESSIONS,
                span: int = SMA_SPAN_DAYS):
    """Signal-bar close over its own `sessions`-bar SMA, minus 1."""
    tb = trailing_bars(bars, signal, sessions)
    if len(tb) < sessions:
        return None
    days = sorted(x for x in bars if x <= signal)[-sessions:]
    if (days[-1] - days[0]).days > span or (signal - days[-1]).days > MAX_BAR_LAG_DAYS:
        return None
    return tb[-1].c / (sum(b.c for b in tb) / sessions) - 1.0


class MarketTable:
    """SPY 20-session return and VIX close as of a date, from the mech table CSV."""

    def __init__(self, rows: list[tuple[str, float, float | None]]):
        self.dates = [r[0] for r in rows]
        self.spy = [r[1] for r in rows]
        self.vix = [r[2] for r in rows]

    @classmethod
    def from_csv(cls, path) -> "MarketTable":
        rows = []
        with open(path, newline="") as fh:
            for r in csv.DictReader(fh):
                spy = DB._float(r.get("spy_close"))
                if spy is None:
                    continue
                rows.append((str(r["date"]), spy, DB._float(r.get("vix_close"))))
        rows.sort()
        return cls(rows)

    def asof(self, d: str):
        """(spy 20-session return, vix) on the last row on or before `d`; None past the end."""
        if not self.dates or d > self.dates[-1]:
            return None, None
        i = bisect_right(self.dates, d) - 1
        if i < 0:
            return None, None
        ret = self.spy[i] / self.spy[i - RET_SESSIONS] - 1.0 if i >= RET_SESSIONS else None
        return ret, self.vix[i]


def model_agreement(model_dir, direction: int):
    if model_dir not in ("BULL", "BEAR", "RANGE"):
        return None
    if model_dir == "RANGE":
        return "RANGE"
    return "agrees" if (model_dir == "BULL") == (direction > 0) else "opposes"


def _f(v):
    return DB._float(v)


def base_features(rec, direction: int, bars: dict, signal: date, labeler, market) -> dict:
    """The UNALIGNED base value of every feature (what a permutation shuffles)."""
    d = str(rec["date"])[:10]
    spy_ret, vix = market.asof(d)
    dip = DB.dip_label(labeler, d)
    cell = None
    if labeler.covers(d):
        _dir, _vol, ok, _ = labeler.label(d)
        if ok:
            cell = labeler.cell(d) or "NONE"
    return {
        "F1": rec.get("model_dir") or None,
        "F2": rec.get("model_vol") or None,
        "F3": cell,
        "F4": None if dip is None else (-1.0 if dip == DB.BELOW else 1.0),
        "F5": spy_ret,
        "F6": vix,
        "F7": _f(rec.get("score_total")),
        "F8": _f(rec.get("oi_confirm_pct")),
        "F9": _f(rec.get("cpir")),
        "F10": _f(rec.get("iv_spread")),
        "F11": _f(rec.get("iv_skew")),
        "F12": _f(rec.get("iv_pct")),
        "F13": _f(rec.get("dte")),
        "F14": 1.0 if TC.group_of(rec["ticker"]) == INDEX_GROUP else 0.0,
        "F15": own_return(bars, signal),
        "F16": own_sma_gap(bars, signal),
        "F17": sectors.cluster_for(rec["ticker"]),
    }


def align(fid: str, base, direction):
    """Feature value from its base and the play's direction (+1 / -1).

    Works on a scalar or on numpy arrays (base float array with NaN, direction
    int array); category features take and return object arrays / scalars.
    """
    if fid == "F1":
        if isinstance(base, np.ndarray):
            return np.array([model_agreement(b, int(s)) for b, s in zip(base, direction)],
                            dtype=object)
        return model_agreement(base, direction)
    if fid == "F4":
        if isinstance(base, np.ndarray):
            out = np.where(base * direction > 0, 1.0, 0.0)
            return np.where(np.isnan(base), np.nan, out)
        return None if base is None else (1.0 if base * direction > 0 else 0.0)
    if fid in ("F5", "F10", "F15", "F16"):
        return None if base is None else base * direction
    if fid == "F9":
        return None if base is None else (base - 0.5) * direction
    if fid == "F11":
        return None if base is None else -base * direction
    return base


# ════════════════════════════════════════════════════════════════════════════
# Population
# ════════════════════════════════════════════════════════════════════════════

def prepare(recs, labeler, market, bars_of=U.load_bars) -> tuple[list[dict], Counter]:
    """Directional rows with a hit, their exit day and every feature's base value."""
    out, counts = [], Counter()
    rescaled = U.rescaled_tickers()
    for r in recs:
        if r.get("R") is None:
            counts["R_missing"] += 1
            continue
        if not r.get("fill_trusted", True):
            counts["fill_untrusted"] += 1
            continue
        side = TC.direction(r["structure"])
        if side not in ("bull", "bear"):
            counts["not_directional"] += 1
            continue
        direction = 1 if side == "bull" else -1
        exit_s, _clamped = TC.exit_date_of(r)
        signal = date.fromisoformat(str(r["date"])[:10])
        exit_day = date.fromisoformat(exit_s)
        bars = bars_of(r["ticker"])
        if not bars:
            counts["no_bars"] += 1
            continue
        hit, ret, why = hit_of(bars, signal, exit_day, direction)
        if why:
            counts[why] += 1
            continue
        if r["ticker"].upper() in rescaled:
            counts["rescaled_ticker_kept"] += 1
        out.append(dict(
            date=signal.isoformat(), exit=exit_day.isoformat(), ticker=r["ticker"],
            structure=r["structure"], direction=direction, tier=DB.tier_of(r),
            hit=hit, ret=ret, hit10=hit_fixed(bars, signal, direction),
            base=base_features(r, direction, bars, signal, labeler, market)))
    out.sort(key=lambda x: (x["date"], x["ticker"], x["structure"]))
    return out, counts


def tier_ab(rows):
    return [r for r in rows if r["tier"] in ("A", "B")]


# ════════════════════════════════════════════════════════════════════════════
# Method 1 — univariate screen
# ════════════════════════════════════════════════════════════════════════════

def _num(vals):
    return np.array([np.nan if v is None else float(v) for v in vals], dtype=float)


def base_array(rows, fid: str):
    """Per-row base values; a date-level feature takes its date's first value."""
    kind, level = SPEC[fid][2], SPEC[fid][3]
    vals = [r["base"][fid] for r in rows]
    if level == "date":
        first = {}
        for r, v in zip(rows, vals):
            first.setdefault(r["date"], v)
        vals = [first[r["date"]] for r in rows]
    if kind == "cat" or fid == "F1":
        return np.array(vals, dtype=object)
    return _num(vals)


def stat(fid: str, x, hit, tie) -> float:
    """The registered lift statistic on feature values `x` (aligned)."""
    kind = SPEC[fid][2]
    if kind == "cat":
        ok = np.array([v is not None for v in x])
        if ok.sum() == 0:
            return float("nan")
        xs, hs = x[ok], hit[ok]
        p = hs.mean()
        tot = 0.0
        for lvl in set(xs):
            m = xs == lvl
            tot += m.sum() * (hs[m].mean() - p) ** 2
        return float(tot / ok.sum())
    ok = ~np.isnan(x)
    xs, hs = x[ok], hit[ok]
    if kind == "bin":
        a, b = hs[xs == 1], hs[xs == 0]
        return float(a.mean() - b.mean()) if len(a) and len(b) else float("nan")
    k = len(xs) // 3
    if k == 0:
        return float("nan")
    order = np.lexsort((tie[ok], xs))
    return float(hs[order[-k:]].mean() - hs[order[:k]].mean())


def shuffle_within_date(date_codes, rng) -> np.ndarray:
    """A permutation that moves each row only among rows of its own date.

    `date_codes` must be sorted (rows grouped by date), as `prepare` leaves them.
    """
    return np.lexsort((rng.random(len(date_codes)), date_codes))


def shuffle_across_dates(date_codes, rng) -> np.ndarray:
    """Index map giving each row the value of a randomly re-assigned date."""
    uniq, first = np.unique(date_codes, return_index=True)
    perm = rng.permutation(len(uniq))
    return first[perm][date_codes]


def screen_feature(rows, fid: str, n_perm: int = PERM_N, seed: int = PERM_SEED):
    """(observed lift, permutation p, rows with a value)."""
    hit = np.array([r["hit"] for r in rows], dtype=float)
    dirs = np.array([r["direction"] for r in rows])
    dc = np.unique([r["date"] for r in rows], return_inverse=True)[1]
    base = base_array(rows, fid)
    tie = np.random.default_rng(seed + 1).random(len(rows))
    obs = stat(fid, align(fid, base, dirs), hit, tie)
    if not math.isfinite(obs):
        return obs, float("nan"), 0
    rng = np.random.default_rng(seed)
    level = SPEC[fid][3]
    ge = 0
    for _ in range(n_perm):
        idx = shuffle_within_date(dc, rng) if level == "row" else shuffle_across_dates(dc, rng)
        s = stat(fid, align(fid, base[idx], dirs), hit, tie)
        if math.isfinite(s) and abs(s) >= abs(obs) - 1e-12:
            ge += 1
    vals = align(fid, base, dirs)
    n_val = int(sum(v is not None for v in vals)) if SPEC[fid][2] == "cat" else int((~np.isnan(vals)).sum())
    return obs, (1 + ge) / (1 + n_perm), n_val


def screen(rows, n_perm: int = PERM_N) -> list[dict]:
    out = [dict(fid=f, **dict(zip(("lift", "p", "n"), screen_feature(rows, f, n_perm))))
           for f in FEATURE_IDS]
    for o, q in zip(out, bh_q([o["p"] for o in out])):
        o["q"] = q
    return out


def level_rates(rows, fid: str) -> str:
    """Per-level hit rates for a category (or binary) feature."""
    dirs = np.array([r["direction"] for r in rows])
    vals = align(fid, base_array(rows, fid), dirs)
    hit = np.array([r["hit"] for r in rows], dtype=float)
    c = Counter()
    h = Counter()
    for v, y in zip(vals, hit):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        c[v] += 1
        h[v] += y
    return ", ".join(f"{k} {h[k] / c[k]:.2f} (n={c[k]})" for k in sorted(c, key=str))


# ════════════════════════════════════════════════════════════════════════════
# Method 2 — the walk-forward model
# ════════════════════════════════════════════════════════════════════════════

def month_start(d: str) -> str:
    return d[:7] + "-01"


def add_months(d: str, n: int) -> str:
    y, m = int(d[:4]), int(d[5:7]) + n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}-01"


def training_mask(rows, cutoff: str) -> np.ndarray:
    """Rows a model predicting dates >= `cutoff` may train on: signal AND exit before it."""
    return np.array([r["date"] < cutoff and r["exit"] < cutoff for r in rows])


def design(train, test, fids):
    """(X_train, X_test) from training-fold statistics only."""
    cols_tr, cols_te = [], []
    for fid in fids:
        kind = SPEC[fid][2]
        tr = align(fid, base_array(train, fid), np.array([r["direction"] for r in train]))
        te = align(fid, base_array(test, fid), np.array([r["direction"] for r in test]))
        if kind == "cat":
            levels = sorted({v for v in tr if v is not None}, key=str)
            for lvl in levels:
                cols_tr.append(np.array([v == lvl for v in tr], dtype=float))
                cols_te.append(np.array([v == lvl for v in te], dtype=float))
            continue
        tr, te = np.asarray(tr, dtype=float), np.asarray(te, dtype=float)
        ok = ~np.isnan(tr)
        med = float(np.median(tr[ok])) if ok.any() else 0.0
        trf, tef = np.where(np.isnan(tr), med, tr), np.where(np.isnan(te), med, te)
        mu, sd = trf.mean(), trf.std()
        sd = sd if sd > 0 else 1.0
        cols_tr.append((trf - mu) / sd)
        cols_te.append((tef - mu) / sd)
        if (~ok).any():
            cols_tr.append(np.isnan(tr).astype(float))
            cols_te.append(np.isnan(te).astype(float))
    if not cols_tr:
        return np.zeros((len(train), 0)), np.zeros((len(test), 0))
    return np.column_stack(cols_tr), np.column_stack(cols_te)


def fit_predict(train, test, fids, C: float, target: str = "hit"):
    from sklearn.linear_model import LogisticRegression
    y = np.array([r[target] for r in train], dtype=int)
    Xtr, Xte = design(train, test, fids)
    if Xtr.shape[1] == 0:
        return np.full(len(test), y.mean())
    m = LogisticRegression(C=C, solver="lbfgs", max_iter=1000)
    m.fit(Xtr, y)
    return m.predict_proba(Xte)[:, 1]


def walk_forward(rows, fids, C: float = C_DEFAULT, target: str = "hit") -> dict:
    """Monthly folds; returns the out-of-sample predictions and the skip count."""
    rows = [r for r in rows if r.get(target) is not None]
    if not rows:
        return dict(idx=[], p=np.array([]), base=np.array([]), y=np.array([]), dates=[],
                    skipped=0, months=0, first=None)
    first = add_months(month_start(rows[0]["date"]), WARMUP_MONTHS)
    months = sorted({month_start(r["date"]) for r in rows if r["date"] >= first})
    idx, ps, bs, skipped = [], [], [], 0
    for m0 in months:
        m1 = add_months(m0, 1)
        test_i = [i for i, r in enumerate(rows) if m0 <= r["date"] < m1]
        mask = training_mask(rows, m0)
        train = [r for r, k in zip(rows, mask) if k]
        y = [r[target] for r in train]
        if len(train) < MIN_TRAIN or len(set(y)) < 2:
            skipped += 1
            continue
        test = [rows[i] for i in test_i]
        ps.append(fit_predict(train, test, fids, C, target))
        bs.append(np.full(len(test), float(np.mean(y))))
        idx.extend(test_i)
    y = np.array([rows[i][target] for i in idx], dtype=float)
    return dict(idx=idx, p=np.concatenate(ps) if ps else np.array([]),
                base=np.concatenate(bs) if bs else np.array([]), y=y,
                dates=[rows[i]["date"] for i in idx], skipped=skipped,
                months=len(months), first=first)


def auc(y, p) -> float:
    """Mann-Whitney AUC with tied scores counted half."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    n1, n0 = (y == 1).sum(), (y == 0).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = rankdata(p)
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def grade(wf, n: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    """AUC and Brier skill, each with a date-clustered bootstrap CI."""
    y, p, b = wf["y"], wf["p"], wf["base"]
    nan3 = (float("nan"),) * 3
    if len(y) == 0:
        return dict(n=0, dates=0, auc=nan3, bss=nan3, hit=float("nan"))
    by: dict[str, list[int]] = {}
    for i, d in enumerate(wf["dates"]):
        by.setdefault(d, []).append(i)
    groups = [np.array(v) for v in by.values()]
    rng = np.random.default_rng(seed)
    aucs, bsss = [], []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        ii = np.concatenate([groups[k] for k in pick])
        aucs.append(auc(y[ii], p[ii]))
        bm, bb = np.mean((p[ii] - y[ii]) ** 2), np.mean((b[ii] - y[ii]) ** 2)
        bsss.append(1 - bm / bb if bb > 0 else np.nan)
    aucs, bsss = np.array(aucs), np.array(bsss)
    bm, bb = np.mean((p - y) ** 2), np.mean((b - y) ** 2)
    return dict(n=len(y), dates=len(groups), hit=float(y.mean()),
                auc=(auc(y, p), *np.nanpercentile(aucs, [2.5, 97.5])),
                bss=(1 - bm / bb if bb > 0 else float("nan"), *np.nanpercentile(bsss, [2.5, 97.5])))


def verdict(v4_lo: float, v3_point: float) -> str:
    """The registered grammar on the primary population."""
    if not (math.isfinite(v4_lo) and v4_lo > 0.5):
        return NULL
    return PREDICTS if (math.isfinite(v3_point) and v3_point > 0.5) else WEAK


def forward_token(n_dates: int, n_pos: int, lo: float) -> str:
    if n_dates < FWD_MIN_DATES or n_pos < FWD_MIN_POS or not math.isfinite(lo):
        return "STILL-OPEN"
    return "CONFIRMED" if lo > 0.5 else "NOT-CONFIRMED"


def subset_configs():
    """The 15 non-empty unions of the four groups, plus intercept-only."""
    out = [("intercept", ())]
    for mask in range(1, 2 ** len(GROUPS)):
        gs = tuple(g for i, g in enumerate(GROUPS) if mask >> i & 1)
        out.append(("+".join(gs), tuple(f[0] for f in FEATURES if f[4] in gs)))
    return out


def pbo_read(rows, C: float = C_DEFAULT):
    """CSCV over the subset grid on summed negative Brier per out-of-sample date."""
    cfgs = subset_configs()
    cols, dates = [], None
    for _name, fids in cfgs:
        wf = walk_forward(rows, fids, C)
        per: dict[str, float] = {}
        for d, p, y in zip(wf["dates"], wf["p"], wf["y"]):
            per[d] = per.get(d, 0.0) - (p - y) ** 2
        if dates is None:
            dates = sorted(per)
        cols.append([per.get(d, 0.0) for d in dates])
    M = np.array(cols, dtype=float).T
    trim = M.shape[0] % PBO_S
    M = M[trim:]
    if M.shape[0] < PBO_S:
        return None, cfgs, 0, trim
    return pbo_mod.cscv(M, S=PBO_S), cfgs, M.shape[0], trim


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def _x(v, fmt="+.3f"):
    return "—" if v is None or (isinstance(v, float) and not math.isfinite(v)) else format(v, fmt)


def describe(rows, title: str):
    n = len(rows)
    print(f"\n-- {title}: {n} rows, {len({r['date'] for r in rows})} signal dates")
    if not n:
        return
    for lbl, sub in (("bull plays", [r for r in rows if r["direction"] > 0]),
                     ("bear plays", [r for r in rows if r["direction"] < 0]),
                     ("Tier A/B", tier_ab(rows)), ("Tier C", [r for r in rows if r["tier"] == "C"]),
                     ("VETO", [r for r in rows if r["tier"] == "VETO"]), ("all", rows)):
        if not sub:
            continue
        ret = np.array([r["ret"] for r in sub])
        h10 = [r["hit10"] for r in sub if r["hit10"] is not None]
        print(f"   {lbl:<11} n={len(sub):5d}  hit={np.mean([r['hit'] for r in sub]):.3f}  "
              f"aligned hold return mean={ret.mean():+.4f} median={np.median(ret):+.4f}  "
              f"10-session hit={_x(float(np.mean(h10)) if h10 else None, '.3f')} (n={len(h10)})")


def print_screen(res, res3, rows, rows3, title: str):
    print(f"\n-- {title}: univariate screen, {PERM_N} permutations, BH over {len(res)} features")
    print(f"   {'id':<4}{'feature':<34}{'perm':<6}{'n':>5}{'lift':>8}{'p':>7}{'q':>7}  flag    "
          f"{'v3 lift':>8}{'v3 p':>7}  v3 sign")
    by3 = {o["fid"]: o for o in res3} if res3 else {}
    for o in res:
        fid = o["fid"]
        o3 = by3.get(fid)
        flag = "screen+" if math.isfinite(o["q"]) and o["q"] < BH_Q else "-"
        if o3 is None:
            agree = "—"
        elif SPEC[fid][2] == "cat":
            agree = "n/a (category)"
        elif math.isfinite(o["lift"]) and math.isfinite(o3["lift"]):
            agree = "agrees" if np.sign(o["lift"]) == np.sign(o3["lift"]) else "differs"
        else:
            agree = "—"
        print(f"   {fid:<4}{SPEC[fid][1]:<34}{SPEC[fid][3]:<6}{o['n']:>5}{_x(o['lift']):>8}"
              f"{_x(o['p'], '.3f'):>7}{_x(o['q'], '.3f'):>7}  {flag:<7} "
              f"{_x(o3['lift'] if o3 else None):>8}{_x(o3['p'] if o3 else None, '.3f'):>7}  {agree}")
    for fid in FEATURE_IDS:
        if SPEC[fid][2] in ("cat", "bin"):
            print(f"   {fid} levels, hit rate: {level_rates(rows, fid)}")
            if rows3:
                print(f"   {fid} levels, v3:       {level_rates(rows3, fid)}")


def grade_line(label: str, g: dict, wf: dict) -> str:
    a, b = g["auc"], g["bss"]
    return (f"   {label:<38} n={g['n']:5d} dates={g['dates']:3d} months={wf['months']:2d} "
            f"skipped={wf['skipped']}  AUC={_x(a[0], '.3f')} [{_x(a[1], '.3f')}, {_x(a[2], '.3f')}]  "
            f"Brier skill={_x(b[0])} [{_x(b[1])}, {_x(b[2])}]")


def model_block(rows, title: str):
    """Default model, then the printed alternatives. Returns the default's grade."""
    print(f"\n-- {title}: walk-forward logistic, warm-up {WARMUP_MONTHS} months, "
          f"min {MIN_TRAIN} training rows")
    wf = walk_forward(rows, FEATURE_IDS, C_DEFAULT)
    g = grade(wf)
    print(f"   first graded month {wf['first']}")
    print(grade_line(f"default: all 17, C={C_DEFAULT}, exit-day hit", g, wf))
    wf_c = walk_forward(rows, FEATURE_IDS, C_ALT)
    print(grade_line(f"alt (not graded): C={C_ALT}", grade(wf_c), wf_c))
    wf_h = walk_forward(rows, FEATURE_IDS, C_DEFAULT, target="hit10")
    print(grade_line("alt (not graded): 10-session hit", grade(wf_h), wf_h))
    return g


def pbo_block(rows, title: str):
    res, cfgs, T, trim = pbo_read(rows)
    print(f"\n-- {title}: PBO, CSCV over {len(cfgs)} feature-group subsets, S={PBO_S}, "
          f"metric = summed negative Brier per out-of-sample date")
    if res is None:
        print("   too few out-of-sample dates")
        return None
    share = res.selection_share()
    top = sorted(range(len(cfgs)), key=lambda i: -share[i])[:4]
    print(f"   T={T} dates (earliest {trim} trimmed), combinations {res.n_combinations}")
    # prob_loss is not printed: a negative Brier score is below zero by construction.
    print(f"   PBO={res.pbo:.3f}  degradation slope={_x(res.slope, '+.2f')}"
          + ("  selection fragile" if res.pbo > 0.5 else ""))
    print("   most-often IS-best: " + ", ".join(f"{cfgs[i][0]} {share[i]:.2f}" for i in top))
    return res.pbo


def main() -> int:
    seal_start = era_mod.SEAL_START
    labeler = MechLabeler.from_csv(MECH_TABLE_CSV)
    market = MarketTable.from_csv(MECH_TABLE_CSV)
    print("direction_hit — does anything known at entry predict the underlying moving the play's way?")
    print(f"registration: {REGISTRATION} (accepted by default {ACCEPTED})")
    print(f"target: direction x (C_exit / C_signal - 1) > 0; C_signal = signal-date close; "
          f"bars lib/underlying.load_bars; SPY/VIX table {MECH_TABLE_CSV.name}, ends {market.dates[-1]}")
    print(f"in-sample: signal dates < {seal_start}; forward: >= {seal_start}, seal lifted: "
          f"{era_mod.SEAL_LIFTED or 'no'}")
    print("Nothing ships from this study.")

    recs, diag = load_book()
    rows, counts = prepare(recs, labeler, market)
    ins = [r for r in rows if r["date"] < seal_start]
    fwd = [r for r in rows if r["date"] >= seal_start]
    era = diag["era"]
    print(f"\nera {era}: {len(rows)} directional rows with a hit; dropped {dict(counts)}")

    ins3 = []
    if era != REPLICATION_ERA:
        try:
            recs3, diag3 = load_book(era=REPLICATION_ERA)
        except SystemExit as exc:
            print(f"{REPLICATION_ERA} not loaded: era refusal, exit {exc.code}")
        else:
            rows3, counts3 = prepare(recs3, labeler, market)
            ins3 = [r for r in rows3 if r["date"] < seal_start]
            print(f"era {diag3['era']}: {len(rows3)} directional rows with a hit; "
                  f"dropped {dict(counts3)}")

    print("\n" + "=" * 78)
    print("BASE RATES")
    print("=" * 78)
    describe(ins, f"{era} in-sample")
    if ins3:
        describe(ins3, f"{REPLICATION_ERA} in-sample")

    print("\n" + "=" * 78)
    print("METHOD 1 — UNIVARIATE SCREEN (flags only, no verdict)")
    print("=" * 78)
    for label, sel in (("all directional", lambda x: x), ("Tier A/B", tier_ab)):
        r4, r3 = sel(ins), sel(ins3)
        print_screen(screen(r4), screen(r3) if r3 else None, r4, r3, f"{era} {label}")

    print("\n" + "=" * 78)
    print("METHOD 2 — WALK-FORWARD MODEL")
    print("=" * 78)
    g4 = model_block(ins, f"{era} all directional (GRADED)")
    g3 = model_block(ins3, f"{REPLICATION_ERA} all directional (replication)") if ins3 else None
    ab4 = model_block(tier_ab(ins), f"{era} Tier A/B (secondary)")
    ab3 = model_block(tier_ab(ins3), f"{REPLICATION_ERA} Tier A/B (secondary)") if ins3 else None
    pbo4 = pbo_block(ins, f"{era} all directional")
    if ins3:
        pbo_block(ins3, f"{REPLICATION_ERA} all directional")

    print("\n" + "=" * 78)
    print("FORWARD")
    print("=" * 78)
    held = diag.get("seal", {})
    if not era_mod.SEAL_LIFTED:
        print(f"SEALED: load_book withheld {held.get('rows', 0)} rows on {held.get('dates', 0)} "
              f"signal dates >= {seal_start}. This study is not a named reader.")
    graded_fwd = era == FORWARD_ERA
    f_rows = fwd if graded_fwd else []
    train = [r for r in ins if r["exit"] < seal_start]
    if f_rows and len(train) >= MIN_TRAIN:
        p = fit_predict(train, f_rows, FEATURE_IDS, C_DEFAULT)
        wf = dict(y=np.array([r["hit"] for r in f_rows], dtype=float), p=p,
                  base=np.full(len(f_rows), np.mean([r["hit"] for r in train])),
                  dates=[r["date"] for r in f_rows])
        gf = grade(wf)
        ftok = forward_token(gf["dates"], gf["n"], gf["auc"][1])
        print(f"   forward n={gf['n']} dates={gf['dates']}  AUC={_x(gf['auc'][0], '.3f')} "
              f"[{_x(gf['auc'][1], '.3f')}, {_x(gf['auc'][2], '.3f')}]")
    else:
        ftok = "STILL-OPEN"
        print(f"   forward rows: {len(f_rows)} of {FWD_MIN_POS} positions; "
              f"training rows with exit < {seal_start}: {len(train)}")

    v = verdict(g4["auc"][1], g3["auc"][0] if g3 else float("nan"))
    vab = verdict(ab4["auc"][1], ab3["auc"][0] if ab3 else float("nan"))
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    print(f"  {era} OOS AUC {_x(g4['auc'][0], '.3f')} CI95 [{_x(g4['auc'][1], '.3f')}, "
          f"{_x(g4['auc'][2], '.3f')}]; {REPLICATION_ERA} OOS AUC "
          f"{_x(g3['auc'][0] if g3 else None, '.3f')}; PBO {_x(pbo4, '.3f')}")
    print(f"  >>> direction_hit MODEL (all directional, {era}): {v} <<<")
    print(f"  secondary, Tier A/B: {vab} (AUC {_x(ab4['auc'][0], '.3f')} "
          f"[{_x(ab4['auc'][1], '.3f')}, {_x(ab4['auc'][2], '.3f')}])")
    print(f"  forward: {ftok}")
    print("  Nothing ships from this study. PREDICTS would let the operator consider a "
          "registered filter or tie-break.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
