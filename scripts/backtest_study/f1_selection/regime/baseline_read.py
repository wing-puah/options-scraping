"""baseline_read — do the flow baseline's mechanical hedging metrics forecast SPY?

REGISTERED 2026-10-23: research/pre-registrations/f1_selection/regime/baseline_read.md.
Every metric, floor, constant, seed and verdict word below is that file's. Read it
before changing anything here.

WHAT IT ASKS
------------
The operator remembers that heavy hedging in the flow precedes market falls. P1
asks whether SPY's 21-session forward log return is lower after dates whose index
put share (M1, SPY+QQQ+IWM put premium over all their premium) sits in the top
fifth of its own trailing 60-row window (HEAVY) than after the rest (REST). P2
asks the same of the 21-session drawdown depth `dd21 = -mae21`. S1-S4 repeat both
outcomes on the ETF-section put share (M2) and the stock put-dominance breadth
(M3). It is the mechanical twin of `market_read`, which tested the model's label.

POPULATION
----------
`backtests/to_evaluate/analysis - BaselineDaily.csv`, the UNVERSIONED BaselineDaily
tab: only the default era runs (any STUDY_ERA but `current` exits 2), and the
header must be exactly `lib.baseline.BASELINE_COLUMNS` (else exit 3). Rows pass
`era.drop_sealed` with no reader. In-sample = rows from the 61st on (by date
order), on exact SPY sessions, dated before `era.SEAL_START`, with a closed
21-session window. Forward = signal dates from SEAL_START, read only once
`era.SEAL_LIFTED` is set.

Percentile: the midrank share of the 60 rows strictly before d (row order) whose
value is below today's; >= 50 numeric values needed. HEAVY = pct >= 0.80.

STATISTICS
----------
`market_read`'s calendar, outcomes, block (i // 21), Draws, mean_diff and
summarize, imported unchanged; its own seed is NOT used: this study draws from
20261023 (10,000 draws). P1+P2 are one Holm family (m = 2), S1-S4 another
(m = 4); a CI word stands only when its Holm-adjusted p < 0.05. GP plants a
3-point shift into 200 within-block shuffles (seed 20261024, 2,000 draws each).

Build rulings (2026-10-23, implementation choices the registration leaves open,
none of which changes what a gate refuses):
  * `market_read.holm_word` / `word` are not imported: their tokens are
    SUPPORTED/CONTRARY. The HEDGE-* words and their sign flip live here.
  * The `GRID` populations are rows from the W-th on, one population per window,
    so its (0.80, 60) cell reproduces P1 and P2 on the same draws.
  * `HP-MECH`'s REST is every in-sample date with an M1 percentile and a
    mechanical label that is not HEAVY-and-mech-BULL.
  * `BOUNDARY` reads raw M1 levels on all readable rows, not only in-sample ones.
  * GP and `POWER` also print each shift's mean planted point and mean CI
    half-width. The within-block shuffle keeps each block's HEAVY count, so the
    between-block part of the real contrast survives every simulation; the
    mean point makes that visible beside the detection rates (printed only;
    the gate still reads the two detection rates alone).

Nothing ships from this study. Run:

    python -m scripts.backtest_study run baseline_read
"""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.baseline import BASELINE_COLUMNS  # noqa: E402
from lib.mech_regime import MechLabeler  # noqa: E402
from scripts.backtest_study.f1_selection.regime import market_read as MR  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import MECH_TABLE_CSV  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/baseline_read.md"
REGISTERED = "2026-10-23"
BASELINE_CSV = era_mod.EVAL_DIR / "analysis - BaselineDaily.csv"
TAB = "BaselineDaily"

# --- registered constants (the registration, not defaults) -------------------
# Literals on purpose: tests pin each to its production / market_read source, so
# a change THERE fails a test instead of silently re-registering this study.
W = 60                      # trailing window, rows (lib.baseline.WINDOW_ROWS)
WINDOW_MIN = 50             # numeric values needed in the window
THRESH = 0.80               # HEAVY: pct >= THRESH
H = 21                      # graded horizon, sessions (market_read.H)
BLOCK = 21                  # bootstrap block, sessions (market_read.BLOCK)
BLOCK_SENS = 42             # printed sensitivity
BOOT_N = 10_000
SEED = 20261023
ALPHA = 0.05
GC_MIN_DATES = 300          # per metric's in-sample population
ARM_DATES, ARM_BLOCKS = 20, 12        # GF, per arm
FWD_DATES, FWD_BLOCKS = 20, 6         # FORWARD, per arm
GP_SIMS, GP_SEED, GP_DRAWS = 200, 20261024, 2_000
GP_SHIFT = 0.03             # 3 pp, planted on the warning side
GP_PASS = 0.80
POWER_SHIFTS = (-0.03, -0.02, -0.01, 0.01, 0.02, 0.03)
POWER_SIMS, POWER_SEED = 100, 20261025
GRID_THRESH = (0.70, 0.80, 0.90)
GRID_WINDOWS = (40, 60, 90)
LEVEL_MIN = 60              # expanding-percentile twin: prior numeric values needed

GRADED = ("M1", "M2", "M3")
PRINTED_METRICS = ("M4", "M5")
CONTRASTS = (("P1", "M1", "ret21"), ("P2", "M1", "dd21"),
             ("S1", "M2", "ret21"), ("S2", "M2", "dd21"),
             ("S3", "M3", "ret21"), ("S4", "M3", "dd21"))
PRIMARY = ("P1", "P2")
SECONDARY = ("S1", "S2", "S3", "S4")
METRIC_NAME = {"M1": "idx_put_share", "M2": "etf_put_share", "M3": "breadth",
               "M4": "stock_put_share", "M5": "idx_put_dollars"}

WARNS, CONTRARIAN = "HEDGE-WARNS", "HEDGE-CONTRARIAN"
NULL, UNDERPOWERED, STILL_OPEN = "NULL", "UNDERPOWERED", "STILL-OPEN"

# Exit 2: any era but `current`. Exit 3: input missing, header not exact, or an
# in-sample window past the SPY table's end (GE).
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}


class Refused(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════════════════════════════════════════════════════════════
# Metrics and the trailing percentile
# ════════════════════════════════════════════════════════════════════════════

def num(v) -> float | None:
    """A finite number, or None. Blank, text and NaN cells are None."""
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


_IDX_PUTS = ("spy_put_prem", "qqq_put_prem", "iwm_put_prem")
_IDX_CALLS = ("spy_call_prem", "qqq_call_prem", "iwm_call_prem")


def m1(row: dict) -> float | None:
    """Index put share: SPY+QQQ+IWM put premium over their put + call premium."""
    puts = [num(row.get(c)) for c in _IDX_PUTS]
    calls = [num(row.get(c)) for c in _IDX_CALLS]
    if any(x is None for x in puts + calls):
        return None
    den = sum(puts) + sum(calls)
    return sum(puts) / den if den > 0 else None


def _put_share(cp) -> float | None:
    c = num(cp)
    return None if c is None or c < 0 else 1.0 / (1.0 + c)


def m2(row: dict) -> float | None:
    """ETF-section put share by premium: 1 / (1 + call/put)."""
    return _put_share(row.get("etfs_cp_prem"))


def m3(row: dict) -> float | None:
    """Put-dominance breadth over the top-50 stocks by premium."""
    return num(row.get("stocks_pct_put_dom"))


def m4(row: dict) -> float | None:
    return _put_share(row.get("stocks_cp_prem"))


def m5(row: dict) -> float | None:
    puts = [num(row.get(c)) for c in _IDX_PUTS]
    return None if any(x is None for x in puts) else float(sum(puts))


METRICS = {"M1": m1, "M2": m2, "M3": m3, "M4": m4, "M5": m5}


def midrank_share(window: list[float], x: float) -> float:
    below = sum(1 for v in window if v < x)
    equal = sum(1 for v in window if v == x)
    return (below + 0.5 * equal) / len(window)


def trailing_pct(values: list, j: int, w: int = W, need: int = WINDOW_MIN) -> float | None:
    """Midrank share of the `w` rows strictly before row `j` that sit below
    today's value; None in the first `w` rows, on a blank today, or when the
    window holds fewer than `need` numeric values."""
    if j < w or values[j] is None:
        return None
    win = [v for v in values[j - w:j] if v is not None]
    if len(win) < need:
        return None
    return midrank_share(win, values[j])


def expanding_pct(values: list, j: int, need: int = LEVEL_MIN) -> float | None:
    """The level twin: midrank share over EVERY prior row, `need` numeric minimum."""
    if values[j] is None:
        return None
    win = [v for v in values[:j] if v is not None]
    if len(win) < need:
        return None
    return midrank_share(win, values[j])


def grid_need(w: int) -> int:
    """The GRID window floor: five sixths of the window, rounded up."""
    return math.ceil(w * WINDOW_MIN / W)


def is_heavy(p: float | None, thresh: float = THRESH) -> bool:
    return p is not None and p >= thresh


def is_rest(p: float | None, thresh: float = THRESH) -> bool:
    return p is not None and p < thresh


# ════════════════════════════════════════════════════════════════════════════
# Inputs
# ════════════════════════════════════════════════════════════════════════════

def check_era() -> None:
    requested = era_mod.requested_era()
    if requested != era_mod.CURRENT:
        raise Refused(era_mod.EXIT_THIN_ERA,
                      f"baseline_read reads the unversioned {TAB} tab; era {requested!r} "
                      f"does not apply — run it without --era. Exit 2.")


def load_baseline(path: Path) -> list[dict]:
    """The export's rows; refuses (exit 3) on a missing file or a header that is
    not exactly `lib.baseline.BASELINE_COLUMNS` (GE)."""
    if not Path(path).exists():
        raise Refused(era_mod.EXIT_ERA_MISMATCH,
                      f"GE: {path} is missing — run `python3 scripts/export_tabs.py "
                      f"--tabs {TAB}`. Exit 3.")
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if header != BASELINE_COLUMNS:
        missing = [c for c in BASELINE_COLUMNS if c not in header]
        extra = [c for c in header if c not in BASELINE_COLUMNS]
        raise Refused(era_mod.EXIT_ERA_MISMATCH,
                      f"GE: {Path(path).name} header is not lib.baseline.BASELINE_COLUMNS "
                      f"(missing {missing}, extra {extra}, order "
                      f"{'differs' if not missing and not extra else 'n/a'}). Exit 3.")
    return rows


def _inventory(path: Path) -> str:
    with open(path, newline="") as fh:
        n = max(0, sum(1 for _ in csv.reader(fh)) - 1)
    mtime = datetime.fromtimestamp(Path(path).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    try:
        rel = Path(path).resolve().relative_to(ROOT)
    except ValueError:
        rel = Path(path)
    return f"  {n:>6,} rows  {mtime}  {rel}"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return "?"


# ════════════════════════════════════════════════════════════════════════════
# Population
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Rec:
    date: str
    row: int                 # index in the readable, date-sorted baseline rows
    i: int                   # SPY session index
    lag: str
    mdir: str | None
    lvl: dict
    pct: dict                # "M1" (graded), "M1@40", "M1@level", ...
    out: dict = field(default_factory=dict)   # outcomes, plus the values Pop.vec reads

    def __getitem__(self, key):      # protocol.window_cuts reads r["date"]
        return getattr(self, key)


@dataclass
class Built:
    readable: list[dict]
    seal: dict
    recs: list[Rec]
    off_calendar: list[str]
    levels: dict
    pcts: dict


def extra_outcomes(cal, i: int) -> dict[str, float]:
    """`ret0`, `ret_prev5` (closes at or before i only) and the next-close `dd21_next`."""
    c, n, d = cal.close, len(cal.close), cal.dates[i]
    out: dict[str, float] = {}
    if i >= 1:
        out["ret0"] = math.log(c[i] / c[i - 1])
    if i >= 5:
        out["ret_prev5"] = math.log(c[i] / c[i - 5])
    if i + 1 + H < n:
        assert all(x > d for x in cal.dates[i + 2:i + H + 2])
        out["dd21_next"] = 0.0 - min(0.0, float(c[i + 2:i + H + 2].min() / c[i + 1] - 1.0))
    return out


def _fill_aux(r: Rec) -> None:
    """Values `Pop.vec` reads by key: levels, HEAVY indicators, tail indicators."""
    for m, v in r.lvl.items():
        if v is not None:
            r.out[f"lvl_{m}"] = v
    for m in GRADED:
        if r.pct.get(m) is not None:
            r.out[f"hv_{m}"] = 1.0 if is_heavy(r.pct[m]) else 0.0
    if "mae21" in r.out:
        r.out["tail3"] = 1.0 if r.out["mae21"] < -0.03 else 0.0
        r.out["tail5"] = 1.0 if r.out["mae21"] < -0.05 else 0.0


def build(rows: list[dict], cal, labeler) -> Built:
    readable, seal = era_mod.drop_sealed(rows, date_key="date")
    readable = sorted(readable, key=lambda r: str(r.get("date", ""))[:10])
    levels = {m: [fn(r) for r in readable] for m, fn in METRICS.items()}
    n = len(readable)
    pcts: dict[str, list] = {m: [trailing_pct(levels[m], j) for j in range(n)] for m in METRICS}
    for w in GRID_WINDOWS:
        if w != W:
            pcts[f"M1@{w}"] = [trailing_pct(levels["M1"], j, w, grid_need(w)) for j in range(n)]
    for m in GRADED:
        pcts[f"{m}@level"] = [expanding_pct(levels[m], j) for j in range(n)]
    recs, off = [], []
    for j, r in enumerate(readable):
        d = str(r.get("date", ""))[:10]
        if d not in cal.pos:
            off.append(d)
            continue
        i = cal.pos[d]
        mdir, _mvol, ok, mapped = labeler.label(d)
        out = MR.outcomes(cal, i)
        out.update(extra_outcomes(cal, i))
        rec = Rec(d, j, i, MR.lag_bin(r.get("created_datetime"), d),
                  mdir if ok and mapped == d else None,
                  {m: levels[m][j] for m in METRICS},
                  {k: v[j] for k, v in pcts.items()}, out)
        _fill_aux(rec)
        recs.append(rec)
    return Built(readable, seal, recs, off, levels, pcts)


def in_sample_candidates(b: Built) -> list[Rec]:
    return [r for r in b.recs if r.row >= W and r.date < era_mod.SEAL_START]


def ge_windows(cands: list[Rec], cal) -> None:
    """GE: every in-sample window closes inside the SPY table, else exit 3."""
    open_ = [r.date for r in cands if "ret21" not in r.out or "dd21" not in r.out]
    if open_:
        raise Refused(era_mod.EXIT_ERA_MISMATCH,
                      f"GE: {len(open_)} in-sample 21-session windows run past the SPY "
                      f"table's end ({cal.dates[-1]}; first {open_[0]}). Refresh it with "
                      f"`make mech-regime`. Exit 3.")


# ════════════════════════════════════════════════════════════════════════════
# Bootstrap and contrasts
# ════════════════════════════════════════════════════════════════════════════

class BPop(MR.Pop):
    """`market_read.Pop` with this study's seed and draw count."""

    def __init__(self, recs, size: int = BLOCK, seed: int | None = None,
                 n: int | None = None, name: str = ""):
        self.recs = list(recs)
        self.size = size
        self.name = name
        self.draws = MR.Draws([MR.block_of(r.i, size) for r in self.recs],
                              n=BOOT_N if n is None else n,
                              seed=SEED if seed is None else seed)


def contrast(pop: MR.Pop, pkey: str, key: str, thresh: float = THRESH,
             where=None) -> MR.Result:
    """Mean `key`, HEAVY minus REST on percentile `pkey`, on `pop`'s draws."""
    keep = where or (lambda r: True)
    return MR.mean_diff(pop, key,
                        lambda r: keep(r) and is_heavy(r.pct.get(pkey), thresh),
                        lambda r: keep(r) and is_rest(r.pct.get(pkey), thresh))


def mean_one(pop: MR.Pop, key: str, pred) -> MR.Result:
    S, N = pop.vec(pred, key)
    res = MR.Result(point=MR._ratio(S.sum(), N.sum()), arms={"A": MR._arm(N)})
    return MR.summarize(res, pop.per_draw_mean(S, N))


def floors_met(res: MR.Result, dates: int = ARM_DATES, blocks: int = ARM_BLOCKS) -> bool:
    return MR.arm_floor(res, dates, blocks)


def _ret_type(key: str) -> bool:
    return not key.startswith("dd")


def ci_word(lo: float, hi: float, floors_ok: bool, key: str) -> str:
    """The CI word. On a return, CI below 0 warns; on a drawdown depth, above 0."""
    if not floors_ok or not (math.isfinite(lo) and math.isfinite(hi)):
        return UNDERPOWERED
    below, above = hi < 0, lo > 0
    if _ret_type(key):
        return WARNS if below else CONTRARIAN if above else NULL
    return WARNS if above else CONTRARIAN if below else NULL


def holm_word(raw: str, p_adj: float) -> str:
    """A HEDGE-* word stands only when its Holm-adjusted p is below ALPHA."""
    if raw in (WARNS, CONTRARIAN) and not p_adj < ALPHA:
        return NULL
    return raw


def read_word(w1: str, w2: str) -> str:
    """READ over P1 and P2, the registration's table, first matching row."""
    pair = (w1, w2)
    if UNDERPOWERED in pair:
        return UNDERPOWERED
    warn, con = WARNS in pair, CONTRARIAN in pair
    if warn and con:
        return "MIXED"
    if warn:
        return "WARNS"
    if con:
        return "CONTRARIAN"
    return "NO-FORECAST"


def forward_read(w1: str, w2: str) -> str:
    back = {STILL_OPEN: UNDERPOWERED}
    out = read_word(back.get(w1, w1), back.get(w2, w2))
    return STILL_OPEN if out == UNDERPOWERED else out


def holm_p(raw: str, res: MR.Result) -> float:
    """What enters Holm: the bootstrap p, or 1 for an UNDERPOWERED contrast."""
    return res.p if raw != UNDERPOWERED and math.isfinite(res.p) else 1.0


@dataclass
class Graded:
    label: str
    metric: str
    key: str
    res: MR.Result
    floors: bool
    raw: str
    adj: float = float("nan")
    word: str = UNDERPOWERED


def grade(pop: MR.Pop, gc_ok: dict, gp_pass: bool) -> dict[str, Graded]:
    out: dict[str, Graded] = {}
    for label, metric, key in CONTRASTS:
        res = contrast(pop, metric, key)
        ok = floors_met(res) and gc_ok[metric] and (gp_pass or label not in PRIMARY)
        out[label] = Graded(label, metric, key, res, floors_met(res),
                            ci_word(res.lo, res.hi, ok, key))
    for family in (PRIMARY, SECONDARY):
        adj = MR.holm({g: holm_p(out[g].raw, out[g].res) for g in family})
        for g in family:
            out[g].adj = adj[g][0]
            out[g].word = holm_word(out[g].raw, out[g].adj)
    return out


# ════════════════════════════════════════════════════════════════════════════
# GP — planted power
# ════════════════════════════════════════════════════════════════════════════

class PowerRead(NamedTuple):
    """Detection rates (the gate reads these two), plus the mean planted point
    and mean CI half-width per outcome, printed so the table explains itself."""
    ret: float
    dd: float
    ret_point: float = float("nan")
    dd_point: float = float("nan")
    ret_half: float = float("nan")
    dd_half: float = float("nan")


def planted_power(recs: list[Rec], shift: float, sims: int, seed: int,
                  draws: int | None = None, metric: str = "M1",
                  size: int = BLOCK) -> PowerRead:
    """`(P1 detection rate, P2 detection rate, ...)` for a planted `shift` on
    ret21 (dd21 takes -shift) on within-block shuffles of the HEAVY/REST labels.

    Each block keeps its HEAVY count, so the between-block part of the real
    contrast stays in every simulation; the mean planted point shows it.
    Detection is a CI wholly on the planted side: shift < 0 -> P1 CI below 0
    and P2 CI above 0."""
    draws = GP_DRAWS if draws is None else draws
    elig = [r for r in recs if r.pct.get(metric) is not None
            and "ret21" in r.out and "dd21" in r.out]
    if not elig:
        return PowerRead(0.0, 0.0)
    blocks = [MR.block_of(r.i, size) for r in elig]
    ids = sorted(set(blocks))
    col = np.array([ids.index(b) for b in blocks])
    k = len(ids)
    heavy = np.array([is_heavy(r.pct[metric]) for r in elig])
    rest_ok = np.array([is_rest(r.pct[metric]) for r in elig])
    assert bool(np.all(heavy | rest_ok))
    y_ret = np.array([r.out["ret21"] for r in elig])
    y_dd = np.array([r.out["dd21"] for r in elig])
    members = defaultdict(list)
    for j, c in enumerate(col):
        members[c].append(j)
    rng = np.random.default_rng(seed)
    hits = {"ret": 0, "dd": 0}
    points: dict[str, list] = {"ret": [], "dd": []}
    halves: dict[str, list] = {"ret": [], "dd": []}
    for _ in range(sims):
        h = heavy.copy()
        for idx in members.values():
            h[idx] = rng.permutation(heavy[idx])
        W_ = MR.Draws(blocks, n=draws, seed=int(rng.integers(2**32))).W
        for y, delta, name in ((y_ret, shift, "ret"), (y_dd, -shift, "dd")):
            yy = y + delta * h
            Sh = np.bincount(col[h], weights=yy[h], minlength=k)
            Nh = np.bincount(col[h], minlength=k).astype(float)
            Sr = np.bincount(col[~h], weights=yy[~h], minlength=k)
            Nr = np.bincount(col[~h], minlength=k).astype(float)
            with np.errstate(invalid="ignore", divide="ignore"):
                d = (W_ @ Sh) / (W_ @ Nh) - (W_ @ Sr) / (W_ @ Nr)
            d = d[np.isfinite(d)]
            if not len(d):
                continue
            lo, hi = np.percentile(d, [2.5, 97.5])
            hits[name] += bool(hi < 0 if delta < 0 else lo > 0)
            points[name].append(Sh.sum() / Nh.sum() - Sr.sum() / Nr.sum())
            halves[name].append((hi - lo) / 2)

    def avg(v):
        return float(np.mean(v)) if v else float("nan")
    return PowerRead(hits["ret"] / sims, hits["dd"] / sims, avg(points["ret"]),
                     avg(points["dd"]), avg(halves["ret"]), avg(halves["dd"]))


# ════════════════════════════════════════════════════════════════════════════
# Printed-only statistics
# ════════════════════════════════════════════════════════════════════════════

def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return float("nan")
    rx, ry = rankdata(x), rankdata(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def rho(pop: MR.Pop, pkey: str, key: str) -> MR.Result:
    """Spearman rho between the percentile and `key`, block-bootstrapped on `pop`'s draws."""
    elig = [r for r in pop.recs if r.pct.get(pkey) is not None and key in r.out]
    x = np.array([r.pct[pkey] for r in elig])
    y = np.array([r.out[key] for r in elig])
    colidx = np.array([pop.draws.col[MR.block_of(r.i, pop.size)] for r in elig], dtype=int)
    res = MR.Result(point=spearman(x, y), arms={"A": (len(elig), len(set(colidx.tolist())))})
    d = np.full(len(pop.draws.W), np.nan)
    if len(elig):
        for t, row in enumerate(pop.draws.W):
            idx = np.repeat(np.arange(len(elig)), row[colidx].astype(int))
            d[t] = spearman(x[idx], y[idx])
    return MR.summarize(res, d)


def _arms(res: MR.Result, names=("HEAVY", "REST")) -> str:
    return MR._arms(res, names)


def line(label: str, res: MR.Result, key: str, names=("HEAVY", "REST"),
         word: bool = True, scale: float = 100.0) -> str:
    w = f"  {ci_word(res.lo, res.hi, floors_met(res), key)}" if word else ""
    return f"  {label:<28} {MR.ci(res, scale)}  {_arms(res, names)}{w}"


def six(pop: MR.Pop, indent: str = "  ", suffix: str = "", where=None) -> None:
    """The six graded contrasts on `pop`, printed only."""
    for label, metric, key in CONTRASTS:
        res = contrast(pop, metric + suffix, key, where=where)
        print(indent + line(f"{label} {metric}{suffix} {key}", res, key).lstrip())


def pp(x, fmt: str = "+.2f") -> str:
    return MR._f(x, 100.0, fmt)


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)
    try:
        return run()
    except Refused as exc:
        print(f"REFUSED — {exc.message}")
        return exc.code


def run() -> int:
    check_era()
    rows = load_baseline(BASELINE_CSV)
    if not Path(MECH_TABLE_CSV).exists():
        raise Refused(era_mod.EXIT_ERA_MISMATCH,
                      f"GE: SPY/VIX table {MECH_TABLE_CSV} is missing — run `make mech-regime`. "
                      f"Exit 3.")
    dates = sorted(str(r.get("date", ""))[:10] for r in rows)

    print("baseline_read — do the flow baseline's mechanical hedging metrics forecast SPY?")
    print(f"registration: {REGISTRATION} (registered {REGISTERED})")
    print("era: current (inputs are unversioned)")
    print(f"population: {TAB} (unversioned tab), {len(rows)} rows, "
          f"{dates[0] if dates else '—'} → {dates[-1] if dates else '—'}")
    dirty = "dirty" if _git("status", "--porcelain") else "clean"
    print(f"git: {_git('rev-parse', '--short', 'HEAD')} "
          f"({_git('rev-parse', '--abbrev-ref', 'HEAD')}, working tree {dirty})")
    print("inputs read:")
    print(_inventory(BASELINE_CSV))
    print(_inventory(MECH_TABLE_CSV))
    print(f"window W={W} prior rows (row order), >= {WINDOW_MIN} numeric, midrank; HEAVY pct >= "
          f"{THRESH:.2f}; blocks i//{BLOCK}; {BOOT_N} draws, seed {SEED}; floors "
          f"{ARM_DATES}d+{ARM_BLOCKS}b per arm")

    cal = MR.load_calendar(MECH_TABLE_CSV)
    labeler = MechLabeler.from_csv(MECH_TABLE_CSV)
    b = build(rows, cal, labeler)
    print(era_mod.seal_line(b.seal))
    print(f"calendar: {len(cal.dates)} sessions {cal.dates[0]} -> {cal.dates[-1]}")

    cands = in_sample_candidates(b)
    ge_windows(cands, cal)
    ins = cands
    pop = BPop(ins, name="in-sample")
    gc_ok = {m: sum(1 for r in ins if r.pct.get(m) is not None) >= GC_MIN_DATES for m in GRADED}

    report_population(b, ins, cal)

    gp = planted_power(ins, -GP_SHIFT, GP_SIMS, GP_SEED)
    gp_pass = gp[0] >= GP_PASS and gp[1] >= GP_PASS
    power = {s: planted_power(ins, s, POWER_SIMS, POWER_SEED) for s in POWER_SHIFTS}
    graded = grade(pop, gc_ok, gp_pass)
    report_gates(ins, gc_ok, graded, gp, gp_pass, power)
    report_graded(graded)

    report_dose(pop)
    report_rho(pop)
    report_level(pop)
    report_grid(b)
    report_mech(ins, pop)
    report_cuts(ins)
    report_halves(ins)
    report_mode(b, ins, pop)
    report_horizons(ins, pop)
    report_tail_conc(pop)
    report_year(pop)
    report_printed_metrics(pop)
    fwd = report_forward(b)

    read = read_word(graded["P1"].word, graded["P2"].word)
    verdict(ins, graded, read, gc_ok, gp, gp_pass, fwd)
    return 0


# ════════════════════════════════════════════════════════════════════════════
# Report sections
# ════════════════════════════════════════════════════════════════════════════

def _blocks(recs) -> int:
    return len({MR.block_of(r.i) for r in recs})


def report_population(b: Built, ins: list[Rec], cal) -> None:
    MR.section("POPULATION AND DROPS (COUNTS)")
    n = len(b.readable)
    print(f"  rows read after the seal guard   {n} ({b.seal['rows']} rows on {b.seal['dates']} "
          f"dates withheld)")
    print(f"  off-calendar dates               {len(b.off_calendar)}  {', '.join(b.off_calendar)}")
    print(f"  first {W} rows (no full window)   {min(W, n)}")
    first, last = (b.recs[0], b.recs[-1]) if b.recs else (None, None)
    if first:
        span = last.i - first.i + 1
        print(f"  SPY sessions spanned (readable)  {span}; sessions with no baseline row "
              f"{span - len(b.recs)}")
    late = [r for r in b.recs if r.date >= era_mod.SEAL_START]
    print(f"  readable dates from {era_mod.SEAL_START}     {len(late)} (forward scope)")
    for key in ("ret5", "ret10", "ret21", "dd21", "ret21_next", "dd21_next"):
        past = sum(1 for r in b.recs if key not in r.out)
        print(f"  window past table end, {key:<10} {past} (all readable dates)")
    print(f"  in-sample dates                  {len(ins)} in {_blocks(ins)} blocks, "
          f"{ins[0].date if ins else '—'} -> {ins[-1].date if ins else '—'}")
    lag = Counter(r.lag for r in ins)
    print("  in-sample by mode                " + ", ".join(
        f"{k} {lag[k]} ({_blocks([r for r in ins if r.lag == k])}b)" for k in MR.LAG_BINS))
    print("\n  per metric (COUNTS):  blank level (all readable) | in-sample: blank today, "
          "thin window, with pct, HEAVY, REST")
    for m in METRICS:
        blank_all = sum(1 for v in b.levels[m] if v is None)
        blank = sum(1 for r in ins if r.lvl[m] is None)
        have = [r for r in ins if r.pct.get(m) is not None]
        thin = len(ins) - blank - len(have)
        hv = [r for r in have if is_heavy(r.pct[m])]
        rs = [r for r in have if is_rest(r.pct[m])]
        print(f"    {m} {METRIC_NAME[m]:<16} {blank_all:>4} | {blank:>4} {thin:>4} {len(have):>4} "
              f"{len(hv):>4} ({_blocks(hv)}b) {len(rs):>4} ({_blocks(rs)}b)")
    md = Counter((r.mdir, is_heavy(r.pct.get('M1'))) for r in ins if r.pct.get("M1") is not None)
    print("\n  M1 HEAVY / REST by mechanical direction: " + "; ".join(
        f"{d or 'none'} {md[(d, True)]}/{md[(d, False)]}" for d in ("BULL", "RANGE", "BEAR", None)))


def report_gates(ins, gc_ok, graded, gp, gp_pass, power) -> None:
    MR.section("GATES — GE, GC, GF, GP")
    print("  GE inputs present, header exact, every in-sample window closes: pass")
    for m in GRADED:
        n = sum(1 for r in ins if r.pct.get(m) is not None)
        print(f"  GC {m} in-sample dates with a percentile {n} (floor {GC_MIN_DATES}): "
              f"{'pass' if gc_ok[m] else 'FAIL -> UNDERPOWERED'}")
    for label in (*PRIMARY, *SECONDARY):
        g = graded[label]
        print(f"  GF {label} per-arm floor {ARM_DATES}d/{ARM_BLOCKS}b  {_arms(g.res)}: "
              f"{'met' if g.floors else 'not met'}")
    print(f"  GP planted {-GP_SHIFT * 100:+.0f} pp on ret21 / {GP_SHIFT * 100:+.0f} pp on dd21, "
          f"{GP_SIMS} within-block shuffles, seed {GP_SEED}, {GP_DRAWS} draws each")
    print(f"     detection P1 {gp[0]:.3f}  P2 {gp[1]:.3f}  (pass at {GP_PASS:.2f} each): "
          f"{'pass' if gp_pass else 'FAIL -> P1, P2, READ UNDERPOWERED'}")
    print(f"     mean planted point P1 {pp(gp.ret_point)} ±{pp(gp.ret_half, '.2f')}, "
          f"P2 {pp(gp.dd_point)} ±{pp(gp.dd_half, '.2f')}")
    print(f"\n  POWER — design power, printed only ({POWER_SIMS} sims per shift, seed {POWER_SEED})")
    print("  The shuffle keeps each block's HEAVY count, so the between-block part of the real")
    print("  contrast stays in every simulation; the mean planted point shows where each sits.")
    print("     shift on ret21 (dd21 opposite)  P1 detect  P2 detect   mean planted P1 / P2 "
          "(pp, mean ±half-width)")
    for s, pr in power.items():
        side = "warning side" if s < 0 else "contrarian side"
        print(f"     {s * 100:+.0f} pp ({side:<15})       {pr.ret:>6.2f}     {pr.dd:>6.2f}    "
              f"{pp(pr.ret_point)} ±{pp(pr.ret_half, '.2f')} / {pp(pr.dd_point)} "
              f"±{pp(pr.dd_half, '.2f')}")


def report_graded(graded: dict[str, Graded]) -> None:
    MR.section("P1, P2, S1-S4 — HEAVY minus REST, the graded contrasts")
    print("  units: percentage points; CI is the 95% block-bootstrap interval, ±half-width")
    for fam, name in ((PRIMARY, "Holm m=2"), (SECONDARY, "Holm m=4")):
        for label in fam:
            g = graded[label]
            print(f"  {label} {g.metric} {g.key:<6} {MR.ci(g.res)}  {_arms(g.res)}  "
                  f"p={MR._p(g.res.p)}  word before Holm {g.raw}  {name} adj p "
                  f"{MR._p(g.adj)}  -> {g.word}")
            print(f"     draws kept {g.res.kept} of {len(g.res.draws)}")
        print()


def report_dose(pop: BPop) -> None:
    MR.section("PRINTED ONLY — DOSE: mean ret21 and dd21 by percentile fifth (pp, n)")
    bins = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01))
    for m in GRADED:
        print(f"  {m} {METRIC_NAME[m]}")
        for q, (lo, hi) in enumerate(bins, start=1):
            pred = (lambda r, lo=lo, hi=hi, m=m:
                    r.pct.get(m) is not None and lo <= r.pct[m] < hi)
            a, d = mean_one(pop, "ret21", pred), mean_one(pop, "dd21", pred)
            print(f"    Q{q} [{lo:.1f}, {min(hi, 1.0):.1f}{']' if q == 5 else ')'}  ret21 {MR.ci(a)}  "
                  f"dd21 {MR.ci(d)}  n {a.arms['A'][0]}d/{a.arms['A'][1]}b")


def report_rho(pop: BPop) -> None:
    MR.section("PRINTED ONLY — RHO: Spearman rho, percentile against outcome, block bootstrap")
    for m in GRADED:
        for key in ("ret21", "dd21"):
            res = rho(pop, m, key)
            print(f"  {m} vs {key:<6} rho {MR.ci(res, 1.0)}  n {res.arms['A'][0]}d/"
                  f"{res.arms['A'][1]}b  draws kept {res.kept}")


def report_level(pop: BPop) -> None:
    MR.section(f"PRINTED ONLY — LEVEL: expanding percentile (every prior row, >= {LEVEL_MIN} "
               f"numeric) >= {THRESH:.2f}")
    six(pop, suffix="@level")


def report_grid(b: Built) -> None:
    MR.section("PRINTED ONLY — GRID: P1 and P2 by threshold and window; (0.80, 60) is the graded cell")
    for w in GRID_WINDOWS:
        recs = [r for r in b.recs if r.row >= w and r.date < era_mod.SEAL_START
                and "ret21" in r.out]
        gpop = BPop(recs)
        pkey = "M1" if w == W else f"M1@{w}"
        for t in GRID_THRESH:
            a, d = contrast(gpop, pkey, "ret21", t), contrast(gpop, pkey, "dd21", t)
            mark = "  <- graded cell" if (w, t) == (W, THRESH) else ""
            print(f"  W={w:<3} (floor {grid_need(w)}) t={t:.2f}  P1 {MR.ci(a)} {_arms(a)}  "
                  f"P2 {MR.ci(d)}{mark}")


def report_mech(ins: list[Rec], pop: BPop) -> None:
    MR.section("PRINTED ONLY — MECH and HP-MECH: within mechanical direction")
    for name, pred in (("mech BULL", lambda r: r.mdir == "BULL"),
                       ("mech non-BULL", lambda r: r.mdir in ("RANGE", "BEAR"))):
        sub = BPop([r for r in ins if pred(r)])
        print(f"  [{name}] {len(sub.recs)} dates, {sub.draws.k} blocks")
        for label, key in (("P1", "ret21"), ("P2", "dd21")):
            print("  " + line(f"{label} M1 {key}", contrast(sub, "M1", key), key))
    hp = (lambda r: r.mdir == "BULL" and is_heavy(r.pct.get("M1")))
    rest = (lambda r: r.mdir is not None and r.pct.get("M1") is not None and not hp(r))
    print("  [HP-MECH] HEAVY on M1 and mech BULL, against every other date with M1 and a mech label")
    for key in ("ret21", "dd21"):
        res = MR.mean_diff(pop, key, hp, rest)
        print("  " + line(f"HP-MECH {key}", res, key, ("HP-MECH", "rest")))


def report_cuts(ins: list[Rec]) -> None:
    MR.section("PRINTED ONLY — CUTS: mandatory window cuts (protocol.window_cuts)")
    for name, rs in P.window_cuts(ins).items():
        if name == "ALL":
            continue
        sub = BPop(rs)
        print(f"  [{name}] {len(rs)} dates, {sub.draws.k} blocks")
        six(sub, indent="    ")


def report_halves(ins: list[Rec]) -> None:
    MR.section("PRINTED ONLY — HALVES: first and second half by session order")
    order = sorted(ins, key=lambda r: r.i)
    h1, h2 = order[:len(order) // 2], order[len(order) // 2:]
    pts = {}
    for name, rs in (("H1", h1), ("H2", h2)):
        sub = BPop(rs)
        print(f"  [{name}] {len(rs)} dates {rs[0].date if rs else '—'} -> "
              f"{rs[-1].date if rs else '—'}, {sub.draws.k} blocks")
        for label, key in (("P1", "ret21"), ("P2", "dd21")):
            res = contrast(sub, "M1", key)
            pts[(name, label)] = res.point
            print("  " + line(f"{label} M1 {key}", res, key))
    for label in ("P1", "P2"):
        a, c = pts[("H1", label)], pts[("H2", label)]
        agree = (math.isfinite(a) and math.isfinite(c) and (a > 0) == (c > 0))
        print(f"  {label} sign H1 {pp(a)} H2 {pp(c)}: {'agree' if agree else 'disagree'}")


def report_mode(b: Built, ins: list[Rec], pop: BPop) -> None:
    MR.section("PRINTED ONLY — MODE and BOUNDARY: collection mode (lag bin)")
    for mode in ("RETRO", "LIVE"):
        sub = BPop([r for r in ins if r.lag == mode])
        print(f"  [{mode} only] {len(sub.recs)} dates, {sub.draws.k} blocks")
        for label, key in (("P1", "ret21"), ("P2", "dd21")):
            print("  " + line(f"{label} M1 {key}", contrast(sub, "M1", key), key))
    print("  mean metric level by mode, in-sample (level as %, n):")
    for m in GRADED:
        bits = []
        for mode in MR.LAG_BINS:
            res = mean_one(pop, f"lvl_{m}", lambda r, mode=mode: r.lag == mode)
            if res.arms["A"][0]:
                bits.append(f"{mode} {MR.ci(res)} (n {res.arms['A'][0]})")
        print(f"    {m} " + "  ".join(bits))
    live = [r for r in b.recs if r.lag == "LIVE"]
    if not live:
        print("  BOUNDARY: no LIVE row")
        return
    j0 = live[0].row
    window = [r for r in b.recs if j0 - W <= r.row < j0 + W]
    bpop = BPop(window)
    before = (lambda r: r.row < j0)
    after = (lambda r: r.row >= j0)
    res = MR.mean_diff(bpop, "lvl_M1", after, before)
    nb = sum(1 for r in window if before(r) and r.lvl["M1"] is not None)
    na = sum(1 for r in window if after(r) and r.lvl["M1"] is not None)
    mb = np.mean([r.lvl["M1"] for r in window if before(r) and r.lvl["M1"] is not None] or [np.nan])
    ma = np.mean([r.lvl["M1"] for r in window if after(r) and r.lvl["M1"] is not None] or [np.nan])
    print(f"  BOUNDARY first LIVE row {live[0].date}: mean M1 level {W} rows before "
          f"{pp(mb, '.2f')}% (n {nb}), {W} rows from it {pp(ma, '.2f')}% (n {na})")
    print(f"    after minus before {MR.ci(res)}  (level points, block bootstrap)")


def report_horizons(ins: list[Rec], pop: BPop) -> None:
    MR.section("PRINTED ONLY — H5, H10, NEXT, B42")
    for key in ("ret5", "ret10"):
        print(line(f"H{key[3:]} P1 M1 {key}", contrast(pop, "M1", key), key))
    for label, key in (("P1", "ret21_next"), ("P2", "dd21_next")):
        print(line(f"NEXT {label} M1 {key}", contrast(pop, "M1", key), key))
    sub = BPop(ins, size=BLOCK_SENS)
    print(f"  [B42] {BLOCK_SENS}-session blocks: {sub.draws.k} blocks")
    six(sub, indent="    ")


def report_tail_conc(pop: BPop) -> None:
    MR.section("PRINTED ONLY — TAIL and CONC: drawdown shares and the concurrent tape")
    for m in GRADED:
        print(f"  {m} {METRIC_NAME[m]}")
        for key, nm in (("tail3", "share mae21 < -3%"), ("tail5", "share mae21 < -5%")):
            a = mean_one(pop, key, lambda r, m=m: is_heavy(r.pct.get(m)))
            c = mean_one(pop, key, lambda r, m=m: is_rest(r.pct.get(m)))
            dres = contrast(pop, m, key)
            print(f"    TAIL {nm}: HEAVY {MR.ci(a)} REST {MR.ci(c)}  diff {MR.ci(dres)}  "
                  f"{_arms(dres)}")
        for key in ("ret0", "ret_prev5"):
            a = mean_one(pop, key, lambda r, m=m: is_heavy(r.pct.get(m)))
            c = mean_one(pop, key, lambda r, m=m: is_rest(r.pct.get(m)))
            dres = contrast(pop, m, key)
            print(f"    CONC {key:<9}: HEAVY {MR.ci(a)} REST {MR.ci(c)}  diff {MR.ci(dres)}  "
                  f"{_arms(dres)}")


def report_year(pop: BPop) -> None:
    MR.section("PRINTED ONLY — YEAR: M1 level and HEAVY share by calendar year")
    years = sorted({r.date[:4] for r in pop.recs})
    print("  year  n   mean level (%)              p20 / median / p80 (%)   HEAVY share (%)")
    for y in years:
        vals = sorted(r.lvl["M1"] for r in pop.recs if r.date[:4] == y and r.lvl["M1"] is not None)
        lvl = mean_one(pop, "lvl_M1", lambda r, y=y: r.date[:4] == y)
        hv = mean_one(pop, "hv_M1", lambda r, y=y: r.date[:4] == y)
        q = np.percentile(vals, [20, 50, 80]) if vals else [np.nan] * 3
        print(f"  {y}  {len(vals):>3} {MR.ci(lvl)}   {pp(q[0], '.1f')} / {pp(q[1], '.1f')} / "
              f"{pp(q[2], '.1f')}     {MR.ci(hv)} (n {hv.arms['A'][0]})")


def report_printed_metrics(pop: BPop) -> None:
    MR.section("PRINTED ONLY — M4 and M5: stock put share and index put dollars")
    for m in PRINTED_METRICS:
        for key in ("ret21", "dd21"):
            print(line(f"{m} {METRIC_NAME[m]} {key}", contrast(pop, m, key), key))


def forward_words(fwd: list[Rec]) -> dict:
    """P1 and P2 on forward dates: own blocks, Holm m = 2, STILL-OPEN for UNDERPOWERED."""
    pop = BPop(fwd, name="forward")
    out: dict = {"n": len(fwd), "blocks": pop.draws.k, "res": {}}
    raw = {}
    for label, key in (("P1", "ret21"), ("P2", "dd21")):
        res = contrast(pop, "M1", key)
        out["res"][label] = res
        raw[label] = ci_word(res.lo, res.hi, floors_met(res, FWD_DATES, FWD_BLOCKS), key)
    adj = MR.holm({g: holm_p(raw[g], out["res"][g]) for g in PRIMARY})
    for g in PRIMARY:
        w = holm_word(raw[g], adj[g][0])
        out[g.lower()] = STILL_OPEN if w == UNDERPOWERED else w
    out["read"] = forward_read(out["p1"], out["p2"])
    return out


def report_forward(b: Built) -> dict:
    MR.section(f"FORWARD — P1 and P2 on signal dates from {era_mod.SEAL_START}")
    fwd = [r for r in b.recs if r.date >= era_mod.SEAL_START and "ret21" in r.out
           and "dd21" in r.out]
    print(f"  seal lifted: {era_mod.SEAL_LIFTED or 'no — forward dates are withheld'}")
    print(f"  forward dates with closed windows: {len(fwd)} in {_blocks(fwd)} blocks "
          f"(floor {FWD_DATES} dates and {FWD_BLOCKS} blocks per arm)")
    if era_mod.SEAL_LIFTED is None:
        print("  forward: STILL-OPEN")
        return {"n": len(fwd), "p1": STILL_OPEN, "p2": STILL_OPEN, "read": STILL_OPEN}
    out = forward_words(fwd)
    for g in PRIMARY:
        print(f"  forward {g} {MR.ci(out['res'][g])}  {_arms(out['res'][g])}  {out[g.lower()]}")
    print(f"  forward READ {out['read']}")
    return out


def verdict(ins, graded, read, gc_ok, gp, gp_pass, fwd) -> None:
    MR.section("VERDICT")
    n1 = sum(1 for r in ins if r.pct.get("M1") is not None)
    print(f"  {TAB} (unversioned), signal dates before {era_mod.SEAL_START}: {len(ins)} dates "
          f"in {_blocks(ins)} blocks ({n1} with an M1 percentile); {BOOT_N} block draws, "
          f"seed {SEED}")
    print("  HEAVY minus REST, percentage points; [95% CI] ±half-width")
    for label in (*PRIMARY, *SECONDARY):
        g = graded[label]
        print(f"  {label} {g.metric} {g.key:<5} {MR.ci(g.res)}  {_arms(g.res)}  "
              f"before Holm {g.raw}, adj p {MR._p(g.adj)}")
    gc = " ".join(f"{m} " + ("pass" if gc_ok[m] else "FAIL") for m in GRADED)
    print(f"  gates: GE pass; GC {gc}; "
          f"GF P1 {'met' if graded['P1'].floors else 'not met'}, P2 "
          f"{'met' if graded['P2'].floors else 'not met'}; GP P1 {gp[0]:.2f} P2 {gp[1]:.2f} "
          f"({'pass' if gp_pass else 'FAIL'})")
    s = graded
    print()
    print(f"  >>> baseline_read P1 (index put share, top quintile of 60-session window vs rest, "
          f"21d SPY return): {s['P1'].word} <<<")
    print(f"  >>> baseline_read P2 (same cut, 21d drawdown depth): {s['P2'].word} <<<")
    print(f"  >>> baseline_read READ (P1+P2, Holm m=2): {read} <<<")
    print(f"  >>> baseline_read SECONDARY (ETF put share S1/S2, breadth S3/S4, Holm m=4): "
          f"S1 {s['S1'].word} S2 {s['S2'].word} S3 {s['S3'].word} S4 {s['S4'].word} <<<")
    print(f"  >>> baseline_read FORWARD (signal dates from {era_mod.SEAL_START}, read after the "
          f"seal lifts): {fwd['read']} <<<")
    print()
    print("  P1 and P2 are one Holm family (m = 2); S1-S4 another (m = 4). A HEDGE-* word stands")
    print("  only below 0.05 after Holm. On ret21 HEDGE-WARNS means a CI below 0; on dd21, above 0.")
    print("  The forward verdict of record is the first forward run printing a token other "
          "than STILL-OPEN.")
    print("  Nothing ships from this study (baseline_read.md).")


if __name__ == "__main__":
    sys.exit(main())
