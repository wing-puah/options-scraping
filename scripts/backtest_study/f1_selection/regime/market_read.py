"""market_read — does the model's MARKET regime label forecast SPY, beyond the mechanical label?

REGISTERED 2026-10-23: research/pre-registrations/f1_selection/regime/market_read.md.
Every floor, constant, parse rule and verdict word below is that file's. Read it
before changing anything here.

WHAT IT ASKS
------------
The operator sizes trades on the analysis MARKET row's free-text `regime`. P1 asks
whether SPY's 21-session forward log return is higher after model BULL dates than
after model non-BULL (BEAR or RANGE) dates. P2 asks the same inside mechanical-
direction strata (`lib/mech_regime.py`, unchanged), i.e. whether the model adds
anything once the mechanical label on the same closes is held fixed. P3 (sizing)
asks whether SPY falls further after model E-VOL dates (`dd21 = -mae21`). P4
(recall) asks whether the P2 edge is larger on backfilled (RETRO) labels than on
labels written live (LIVE).

POPULATION
----------
MARKET rows of the era's analysis export, through `era.drop_sealed` with no
reader (this study is not in SEALED_READERS). In-sample (P1-P3) = signal dates
before `era.SEAL_START`, whether or not the seal has lifted. P4 = every readable
RETRO and LIVE date. Forward (P1, P2) = signal dates after FWD_AFTER, read only
once `era.SEAL_LIFTED` is set. Dates from SEAL_START through FWD_AFTER enter
P4's LIVE bin only.

Head-only tokeniser: head = text before the first of an em dash, " - ", ". ",
": ", " ("; dir = first of BULL/BEAR/RANGE as a whole word; vol = first of
E-VOL/H-VOL/L-VOL/C-VOL; risk = RISK-ON/RISK-OFF/none; HP whole token. A head
with more than one direction word is flagged a transition and reads as its
first. No direction -> OTHER (census only; refuse, exit 2, above 2%).

Lag bin = created_datetime[:10] - date: <=1 LIVE, 2-7 NEAR, >7 RETRO, blank or
negative UNKNOWN. A date carried by two rows whose directions differ is
AMBIGUOUS and leaves every statistic.

Calendar: SPY sessions with a non-blank close in the SPY/VIX table; a signal
date must be an exact session (never mapped as-of). Mechanical label:
`MechLabeler.label(d)`, kept only when ok and mapped == d.

STATISTICS
----------
Blocks are `i // 21` on that calendar. Each population resamples its own blocks
with replacement, as many as it holds, 10,000 draws from seed 20260811; every
statistic on one population shares those draws. 95% percentile CI, half-width
printed; two-sided p = 2 * min(share <= 0, share >= 0), capped at 1. P1 and P2
are an intersection (5% each, no correction). P3 and P4 are one Holm family
(m = 2), P4 at p = 1 until gradable.

Build rulings (2026-10-23, implementation choices the registration leaves open,
none of which changes what a gate refuses):
  * A transition is any head carrying two or more distinct direction words.
  * Two rows on one date whose directions AGREE count once, from the first row
    in export order. (None exists today; both v3 duplicates disagree.)
  * The OTHER share is taken over the readable (post-seal-guard) dates.
  * The P3 population is the in-sample dates with both a model vol token and a
    mechanical vol; P3's per-arm floor is counted on that population.
  * P4 resamples the P4 population's own blocks; RETRO and LIVE share them.
  * The vocabulary census lists every distinct string, clipped to fit a line;
    the head, which decides the tuple, is shown first.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run market_read
    python -m scripts.backtest_study run market_read --era v3
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import MechLabeler  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark.ticker_class import holm  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import MECH_TABLE_CSV  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/market_read.md"
REGISTERED = "2026-10-23"

# --- registered constants (the registration, not defaults) -------------------
H = 21                      # graded horizon, sessions
HORIZONS = (5, 10, 21)
BLOCK = 21                  # bootstrap block, sessions (i // 21)
BLOCK_SENS = 42             # printed sensitivity
BOOT_N = 10_000
SEED = 20260811
ALPHA = 0.05
ERA_MIN_DATES = 60          # era.require_dates on the in-sample dates
OTHER_MAX = 0.02            # OTHER share above which the run refuses
ARM_DATES, ARM_BLOCKS = 20, 12        # P1, P3 per arm
STRAT_DATES, STRAT_BLOCKS = 10, 3     # P2 (and P3) per arm per stratum
P4_RETRO_BLOCKS = 24
P4_LIVE_BLOCKS, P4_LIVE_DATES = 8, 60
FWD_DATES, FWD_BLOCKS = 60, 8
FWD_AFTER = "2026-10-23"    # forward: signal date strictly after

DIRS = ("BULL", "BEAR", "RANGE")
VOLS = ("E-VOL", "H-VOL", "L-VOL", "C-VOL")
RISKS = ("RISK-ON", "RISK-OFF")
LAG_BINS = ("LIVE", "NEAR", "RETRO", "UNKNOWN")
MECH_DIRS = ("BULL", "RANGE", "BEAR")
MECH_VOL_STRATA = ("L-VOL", "H/E-VOL")

# OTHER above 2% (exit 2); the era refusals from lib/era.py (2 thin, 3 mismatch).
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

RULE = "=" * 78


# ════════════════════════════════════════════════════════════════════════════
# Label parsing
# ════════════════════════════════════════════════════════════════════════════

_HEAD_SEP = re.compile(r"—| - |\. |: | \(")


def _word_rx(token: str, hyphen_is_part: bool = False) -> re.Pattern:
    edge = r"A-Za-z0-9-" if hyphen_is_part else r"A-Za-z0-9"
    return re.compile(rf"(?<![{edge}]){re.escape(token)}(?![{edge}])")


_DIR_RX = {t: _word_rx(t) for t in DIRS}
_VOL_RX = {t: _word_rx(t) for t in VOLS}
_RISK_RX = {t: _word_rx(t) for t in RISKS}
_HP_RX = _word_rx("HP", hyphen_is_part=True)


@dataclass(frozen=True)
class Label:
    head: str
    dir: str                 # BULL / BEAR / RANGE / OTHER
    vol: str | None
    risk: str | None
    hp: bool
    transition: bool

    def tuple(self) -> str:
        return (f"{self.dir:<5} {self.vol or '-':<5} {self.risk or '-':<8} "
                f"{'HP' if self.hp else '--'}{' T' if self.transition else '  '}")


def label_head(raw) -> str:
    """The text before the first registered separator, stripped."""
    s = raw if isinstance(raw, str) else ""
    if s.strip().lower() == "nan":
        s = ""
    m = _HEAD_SEP.search(s)
    return (s[:m.start()] if m else s).strip()


def _first(text: str, rx: dict[str, re.Pattern]) -> tuple[str | None, int]:
    found = {t: m.start() for t, r in rx.items() if (m := r.search(text))}
    if not found:
        return None, 0
    return min(found, key=found.get), len(found)


def parse_label(raw) -> Label:
    head = label_head(raw)
    d, n_dirs = _first(head, _DIR_RX)
    vol, _ = _first(head, _VOL_RX)
    risk, _ = _first(head, _RISK_RX)
    return Label(head=head, dir=d or "OTHER", vol=vol, risk=risk,
                 hp=bool(_HP_RX.search(head)), transition=n_dirs > 1)


def lag_bin(created, signal_date) -> str:
    c = str(created or "").strip()[:10]
    try:
        days = (date.fromisoformat(c) - date.fromisoformat(str(signal_date)[:10])).days
    except ValueError:
        return "UNKNOWN"
    if days < 0:
        return "UNKNOWN"
    if days <= 1:
        return "LIVE"
    if days <= 7:
        return "NEAR"
    return "RETRO"


# ════════════════════════════════════════════════════════════════════════════
# Calendar and outcomes
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Calendar:
    dates: list[str]
    close: np.ndarray
    pos: dict[str, int]

    @classmethod
    def from_pairs(cls, pairs) -> "Calendar":
        pairs = sorted((str(d)[:10], float(c)) for d, c in pairs)
        dates = [d for d, _ in pairs]
        return cls(dates, np.array([c for _, c in pairs], dtype=float),
                   {d: i for i, d in enumerate(dates)})


def load_calendar(path: Path) -> Calendar:
    pairs = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            v = str(r.get("spy_close") or "").strip()
            try:
                c = float(v)
            except ValueError:
                continue
            if c == c:
                pairs.append((r["date"], c))
    return Calendar.from_pairs(pairs)


def block_of(i: int, size: int = BLOCK) -> int:
    return i // size


def outcomes(cal: Calendar, i: int) -> dict[str, float]:
    """Every outcome whose window closes inside the table. A missing key is a
    window past the table end. Every close read is strictly after date i."""
    c, n, d = cal.close, len(cal.close), cal.dates[i]
    out: dict[str, float] = {}
    for h in HORIZONS:
        if i + h < n:
            assert cal.dates[i + h] > d
            out[f"ret{h}"] = math.log(c[i + h] / c[i])
    if i + H < n:
        assert all(x > d for x in cal.dates[i + 1:i + H + 1])
        lr = np.diff(np.log(c[i:i + H + 1]))
        out["rv21"] = float(np.std(lr, ddof=1) * 100.0)
        out["mae21"] = min(0.0, float(c[i + 1:i + H + 1].min() / c[i] - 1.0))
        out["dd21"] = 0.0 - out["mae21"]
    if i + 1 + H < n:
        assert cal.dates[i + 1] > d
        out["ret21_next"] = math.log(c[i + 1 + H] / c[i + 1])
    return out


# ════════════════════════════════════════════════════════════════════════════
# Population
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Rec:
    date: str
    raw: str
    label: Label
    lag: str
    i: int
    mdir: str
    mvol: str | None
    out: dict = field(default_factory=dict)

    def __getitem__(self, key):      # protocol.window_cuts reads r["date"]
        return getattr(self, key)

    @property
    def scope(self) -> str:
        if self.date < era_mod.SEAL_START:
            return "in"
        return "fwd" if self.date > FWD_AFTER else "gap"


@dataclass
class Built:
    recs: list[Rec]
    seal: dict
    counts: Counter
    census: list[tuple[str, str, Label]]          # (date, raw, label), readable rows
    singles: list[tuple[str, str, Label, str]]    # (date, raw, label, lag), deduped
    duplicates: list[dict]
    off_calendar: list[str]
    no_mech: list[str]
    other_dates: list[str]


def dedupe(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """`(one row per date, duplicate findings)`. Differing directions -> the
    date is AMBIGUOUS and dropped; agreeing rows count once, the first kept."""
    by_date: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_date[str(r.get("date", ""))[:10]].append(r)
    kept, findings = [], []
    for d, rs in by_date.items():
        if len(rs) == 1:
            kept.append(rs[0])
            continue
        labels = [parse_label(r.get("regime")) for r in rs]
        agree = len({lb.dir for lb in labels}) == 1
        findings.append({"date": d, "agree": agree,
                         "rows": [(str(r.get("created_datetime", "")), lb) for r, lb in zip(rs, labels)]})
        if agree:
            kept.append(rs[0])
    return kept, findings


def build(rows: list[dict], cal: Calendar, labeler) -> Built:
    counts: Counter = Counter()
    market = [r for r in rows if str(r.get("ticker", "")).strip() == "MARKET"]
    counts["market_rows"] = len(market)
    readable, seal = era_mod.drop_sealed(market, date_key="date")
    census = [(str(r.get("date", ""))[:10], str(r.get("regime") or ""), parse_label(r.get("regime")))
              for r in readable]
    kept, dups = dedupe(readable)
    counts["readable_dates"] = len({str(r.get("date", ""))[:10] for r in readable})
    counts["ambiguous"] = sum(1 for f in dups if not f["agree"])
    recs: list[Rec] = []
    singles, off_cal, no_mech, other = [], [], [], []
    for r in kept:
        d = str(r.get("date", ""))[:10]
        lab = parse_label(r.get("regime"))
        lag = lag_bin(r.get("created_datetime"), d)
        singles.append((d, str(r.get("regime") or ""), lab, lag))
        counts["transition"] += lab.transition
        if lab.dir == "OTHER":
            other.append(d)
            continue
        if d not in cal.pos:
            off_cal.append(d)
            continue
        mdir, mvol, ok, mapped = labeler.label(d)
        if not ok or mapped != d:
            no_mech.append(d)
            continue
        i = cal.pos[d]
        out = outcomes(cal, i)
        for key in ("ret5", "ret10", "ret21", "ret21_next"):
            if key not in out:
                counts[f"past_end_{key}"] += 1
        recs.append(Rec(d, str(r.get("regime") or ""), lab, lag, i, mdir, mvol, out))
    counts["other"] = len(other)
    counts["off_calendar"] = len(off_cal)
    counts["no_mech"] = len(no_mech)
    recs.sort(key=lambda x: x.date)
    return Built(recs, seal, counts, census, singles, dups, off_cal, no_mech, other)


def other_share(b: Built) -> float:
    n = b.counts["readable_dates"]
    return len(b.other_dates) / n if n else 0.0


# ════════════════════════════════════════════════════════════════════════════
# Bootstrap
# ════════════════════════════════════════════════════════════════════════════

class Draws:
    """Block multiplicities for BOOT_N draws over one population's blocks."""

    def __init__(self, blocks, n: int = BOOT_N, seed: int = SEED):
        self.ids = sorted(set(blocks))
        self.k = len(self.ids)
        self.col = {b: j for j, b in enumerate(self.ids)}
        self.W = np.zeros((n, self.k))
        if self.k:
            idx = np.random.default_rng(seed).integers(0, self.k, (n, self.k))
            rows = np.arange(n)
            for c in range(self.k):
                self.W[rows, idx[:, c]] += 1


class Pop:
    def __init__(self, recs: list[Rec], size: int = BLOCK, name: str = ""):
        self.recs = list(recs)
        self.size = size
        self.name = name
        self.draws = Draws([r.i // size for r in self.recs])

    def vec(self, pred, key: str) -> tuple[np.ndarray, np.ndarray]:
        S, N = np.zeros(self.draws.k), np.zeros(self.draws.k)
        for r in self.recs:
            v = r.out.get(key)
            if v is None or not pred(r):
                continue
            j = self.draws.col[r.i // self.size]
            S[j] += v
            N[j] += 1
        return S, N

    def per_draw_mean(self, S, N) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            return (self.draws.W @ S) / (self.draws.W @ N)


@dataclass
class Result:
    point: float = float("nan")
    lo: float = float("nan")
    hi: float = float("nan")
    p: float = float("nan")
    kept: int = 0
    discarded: int = 0
    arms: dict = field(default_factory=dict)       # arm -> (dates, blocks)
    strata: dict = field(default_factory=dict)
    weights: dict = field(default_factory=dict)
    draws: np.ndarray | None = None

    @property
    def half(self) -> float:
        return (self.hi - self.lo) / 2


def _ratio(s: float, n: float) -> float:
    return s / n if n else float("nan")


def summarize(res: Result, d: np.ndarray) -> Result:
    res.draws = d
    ok = np.isfinite(d)
    res.kept, res.discarded = int(ok.sum()), int((~ok).sum())
    if res.kept:
        v = d[ok]
        res.lo, res.hi = (float(x) for x in np.percentile(v, [2.5, 97.5]))
        res.p = float(min(1.0, 2 * min(np.mean(v <= 0), np.mean(v >= 0))))
    return res


def _arm(N: np.ndarray) -> tuple[int, int]:
    return int(N.sum()), int((N > 0).sum())


def mean_diff(pop: Pop, key: str, in_a, in_b) -> Result:
    SA, NA = pop.vec(in_a, key)
    SB, NB = pop.vec(in_b, key)
    res = Result(point=_ratio(SA.sum(), NA.sum()) - _ratio(SB.sum(), NB.sum()),
                 arms={"A": _arm(NA), "B": _arm(NB)})
    return summarize(res, pop.per_draw_mean(SA, NA) - pop.per_draw_mean(SB, NB))


def strat_diff(pop: Pop, key: str, in_a, in_b, stratum_of, strata,
               fixed: tuple[list, dict] | None = None, where=None) -> Result:
    """Fixed-weight standardised difference of arm means across strata.

    With `fixed=None` a stratum enters when each arm holds STRAT_DATES dates in
    STRAT_BLOCKS blocks; weights are each entering stratum's share of the dates
    in all entering strata. `fixed=(entering, weights)` reuses another
    population's strata and weights (P4). A draw in which an entering stratum
    has an empty arm is discarded.
    """
    keep = where or (lambda r: True)
    parts, info = {}, {}
    for s in strata:
        fa = (lambda r, s=s: keep(r) and stratum_of(r) == s and in_a(r))
        fb = (lambda r, s=s: keep(r) and stratum_of(r) == s and in_b(r))
        SA, NA = pop.vec(fa, key)
        SB, NB = pop.vec(fb, key)
        (na, ba), (nb, bb) = _arm(NA), _arm(NB)
        info[s] = {"A": (na, ba), "B": (nb, bb),
                   "enters": na >= STRAT_DATES and ba >= STRAT_BLOCKS
                   and nb >= STRAT_DATES and bb >= STRAT_BLOCKS,
                   "diff": _ratio(SA.sum(), NA.sum()) - _ratio(SB.sum(), NB.sum())}
        parts[s] = (SA, NA, SB, NB)
    if fixed is None:
        entering = [s for s in strata if info[s]["enters"]]
        tot = sum(info[s]["A"][0] + info[s]["B"][0] for s in entering)
        weights = {s: (info[s]["A"][0] + info[s]["B"][0]) / tot for s in entering}
    else:
        entering, weights = fixed
    res = Result(strata=info, weights=weights)
    if not entering:
        return summarize(res, np.full(len(pop.draws.W), np.nan))
    res.point = float(sum(weights[s] * info[s]["diff"] for s in entering))
    stat = np.zeros(len(pop.draws.W))
    for s in entering:
        SA, NA, SB, NB = parts[s]
        stat = stat + weights[s] * (pop.per_draw_mean(SA, NA) - pop.per_draw_mean(SB, NB))
    return summarize(res, stat)


# ════════════════════════════════════════════════════════════════════════════
# The contrasts
# ════════════════════════════════════════════════════════════════════════════

def is_bull(r: Rec) -> bool:
    return r.label.dir == "BULL"


def is_nonbull(r: Rec) -> bool:
    return r.label.dir in ("BEAR", "RANGE")


def is_mech_bull(r: Rec) -> bool:
    return r.mdir == "BULL"


def is_mech_nonbull(r: Rec) -> bool:
    return r.mdir in ("BEAR", "RANGE")


def mech_vol_group(r: Rec) -> str | None:
    if r.mvol == "L-VOL":
        return "L-VOL"
    if r.mvol in ("H-VOL", "E-VOL"):
        return "H/E-VOL"
    return None


def in_p3(r: Rec) -> bool:
    return r.label.vol is not None and mech_vol_group(r) is not None


def p1(pop: Pop, key: str = "ret21") -> Result:
    return mean_diff(pop, key, is_bull, is_nonbull)


def p1m(pop: Pop, key: str = "ret21") -> Result:
    return mean_diff(pop, key, is_mech_bull, is_mech_nonbull)


def paired(a: Result, b: Result) -> Result:
    return summarize(Result(point=a.point - b.point), a.draws - b.draws)


def p2(pop: Pop, key: str = "ret21", fixed=None, where=None) -> Result:
    return strat_diff(pop, key, is_bull, is_nonbull, lambda r: r.mdir, MECH_DIRS,
                      fixed=fixed, where=where)


def p3_arms(token_of=lambda r: r.label.vol == "E-VOL"):
    return (lambda r: in_p3(r) and token_of(r)), (lambda r: in_p3(r) and not token_of(r))


def p3(pop: Pop, key: str = "dd21", token_of=lambda r: r.label.vol == "E-VOL") -> Result:
    a, b = p3_arms(token_of)
    return strat_diff(pop, key, a, b, mech_vol_group, MECH_VOL_STRATA)


def p3_unstratified(pop: Pop, key: str = "dd21", token_of=lambda r: r.label.vol == "E-VOL") -> Result:
    a, b = p3_arms(token_of)
    return mean_diff(pop, key, a, b)


def arm_floor(res: Result, dates: int = ARM_DATES, blocks: int = ARM_BLOCKS) -> bool:
    return all(n >= dates and b >= blocks for n, b in res.arms.values())


# ════════════════════════════════════════════════════════════════════════════
# Verdict words
# ════════════════════════════════════════════════════════════════════════════

def word(lo: float, hi: float, floors_ok: bool) -> str:
    if not floors_ok or not (math.isfinite(lo) and math.isfinite(hi)):
        return "UNDERPOWERED"
    if lo > 0:
        return "SUPPORTED"
    if hi < 0:
        return "CONTRARY"
    return "NULL"


READ_TABLE = {
    ("SUPPORTED", "SUPPORTED"): "MODEL-ADDS",
    ("SUPPORTED", "NULL"): "MECH-COVERS",
    ("NULL", "SUPPORTED"): "INCREMENTAL-ONLY",
    ("NULL", "NULL"): "NO-FORECAST",
}


def read_word(w1: str, w2: str) -> str:
    """The first matching row of the registration's READ table."""
    pair = (w1, w2)
    if "CONTRARY" in pair:
        return "CONTRARY"
    if "UNDERPOWERED" in pair:
        return "UNDERPOWERED"
    return READ_TABLE[pair]


def forward_read(w1: str, w2: str) -> str:
    """READ on forward words, `STILL-OPEN` in place of `UNDERPOWERED`."""
    back = {"STILL-OPEN": "UNDERPOWERED"}
    out = read_word(back.get(w1, w1), back.get(w2, w2))
    return "STILL-OPEN" if out == "UNDERPOWERED" else out


def holm_word(raw: str, p_adj: float) -> str:
    """A P3 SUPPORTED/CONTRARY stands only below ALPHA after Holm."""
    if raw in ("SUPPORTED", "CONTRARY") and not p_adj < ALPHA:
        return "NULL"
    return raw


def p4_word(floors_ok: bool, res: Result, gauge: Result, p_adj: float) -> str:
    if not floors_ok or not (math.isfinite(res.lo) and math.isfinite(res.hi)):
        return "STILL-OPEN"
    if res.lo > 0 and res.point > gauge.point and p_adj < ALPHA:
        return "RECALL-FLAGGED"
    return "RECALL-NOT-SHOWN"


# ════════════════════════════════════════════════════════════════════════════
# Report helpers
# ════════════════════════════════════════════════════════════════════════════

def _f(x, scale: float = 100.0, fmt: str = "+.2f") -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return format(x * scale, fmt)


def ci(res: Result, scale: float = 100.0) -> str:
    half = "—" if not math.isfinite(res.half) else format(res.half * scale, ".2f")
    return f"{_f(res.point, scale)} [{_f(res.lo, scale)}, {_f(res.hi, scale)}] ±{half}"


def _arms(res: Result, names=("A", "B")) -> str:
    return "  ".join(f"{nm} {res.arms[k][0]}d/{res.arms[k][1]}b"
                     for k, nm in zip(("A", "B"), names) if k in res.arms)


def _p(x) -> str:
    return "—" if x is None or not math.isfinite(x) else f"{x:.4f}"


def section(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def lag_cuts(recs: list[Rec]) -> dict[str, list[Rec]]:
    return {"ALL": recs,
            "RETRO": [r for r in recs if r.lag == "RETRO"],
            "LIVE": [r for r in recs if r.lag == "LIVE"]}


def strata_line(res: Result, scale: float = 100.0) -> str:
    bits = []
    for s, v in res.strata.items():
        mark = f"w={res.weights[s]:.2f}" if s in res.weights else "out"
        bits.append(f"{s} A {v['A'][0]}d/{v['A'][1]}b B {v['B'][0]}d/{v['B'][1]}b "
                    f"{_f(v['diff'], scale)} {mark}")
    return "; ".join(bits)


def print_contrasts(recs: list[Rec], size: int = BLOCK, indent: str = "  ") -> None:
    """P1, P1m, P1 - P1m, P2, P3 on one population, printed with words, cut
    ALL / RETRO / LIVE. Printed only: the graded run is computed separately."""
    for cut, rs in lag_cuts(recs).items():
        pop = Pop(rs, size)
        a, m = p1(pop), p1m(pop)
        s2, s3, u3 = p2(pop), p3(pop), p3_unstratified(pop)
        print(f"{indent}[{cut}] {len(rs)} dates, {pop.draws.k} blocks")
        print(f"{indent}  P1      {ci(a)}  {_arms(a, ('BULL', 'nonBULL'))}  "
              f"{word(a.lo, a.hi, arm_floor(a))}")
        print(f"{indent}  P1m     {ci(m)}  {_arms(m, ('mBULL', 'mnonBULL'))}")
        print(f"{indent}  P1-P1m  {ci(paired(a, m))}")
        print(f"{indent}  P2      {ci(s2)}  discards {s2.discarded}  "
              f"{word(s2.lo, s2.hi, bool(s2.weights))}")
        print(f"{indent}  P3      {ci(s3)}  {_arms(u3, ('E-VOL', 'other'))}  discards {s3.discarded}  "
              f"{word(s3.lo, s3.hi, bool(s3.weights) and arm_floor(u3))}")


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def read_rows(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)

    requested = era_mod.requested_era()
    paths = era_mod.resolve_paths(requested)
    era = era_mod.enforce(requested, paths)

    print("market_read — does the model's MARKET regime label forecast SPY, beyond the "
          "mechanical label?")
    print(f"registration: {REGISTRATION} (registered {REGISTERED})")
    print(f"era: {era} (requested {requested!r}); reads {paths['analysis'].name} only, "
          f"MARKET rows; SPY/VIX table {MECH_TABLE_CSV.relative_to(ROOT)}")
    print(f"blocks i//{BLOCK} on the SPY calendar; {BOOT_N} draws, seed {SEED}; "
          f"floors P1/P3 {ARM_DATES}d+{ARM_BLOCKS}b per arm, P2 stratum "
          f"{STRAT_DATES}d+{STRAT_BLOCKS}b per arm")

    cal = load_calendar(MECH_TABLE_CSV)
    labeler = MechLabeler.from_csv(MECH_TABLE_CSV)
    b = build(read_rows(paths["analysis"]), cal, labeler)
    print(era_mod.seal_line(b.seal))
    print(f"calendar: {len(cal.dates)} sessions {cal.dates[0]} -> {cal.dates[-1]}")

    share = other_share(b)
    if share > OTHER_MAX:
        print(f"\nREFUSED — {len(b.other_dates)} OTHER dates are {share:.1%} of "
              f"{b.counts['readable_dates']} readable dates (limit {OTHER_MAX:.0%}). "
              f"Exit 2.")
        return 2

    ins = [r for r in b.recs if r.scope == "in" and "ret21" in r.out]
    era_mod.require_dates(len(ins), era, minimum=ERA_MIN_DATES,
                          what="in-sample MARKET dates with a closed 21-session window")

    report_population(b, ins)
    report_census(b)
    report_duplicates(b)
    report_lag_by_label(b)
    report_confusion(ins)

    # ── the graded in-sample run ─────────────────────────────────────────────
    pop = Pop(ins, BLOCK, "in-sample")
    r1, r1m = p1(pop), p1m(pop)
    r1p = paired(r1, r1m)
    r2 = p2(pop)
    r3, r3u = p3(pop), p3_unstratified(pop)
    w1 = word(r1.lo, r1.hi, arm_floor(r1))
    w2 = word(r2.lo, r2.hi, bool(r2.weights))
    w3_raw = word(r3.lo, r3.hi, bool(r3.weights) and arm_floor(r3u))

    report_p1(pop, r1, r1m, r1p, w1)
    report_p2(r2, w2)
    report_p3(pop, r3, r3u, w3_raw)
    section("LAG CUTS — P1, P1m, P2, P3 on ALL / RETRO / LIVE, printed only (ALL is the graded run)")
    print_contrasts(ins, BLOCK)

    # ── P4 ───────────────────────────────────────────────────────────────────
    p4_recs = [r for r in b.recs if r.lag in ("RETRO", "LIVE") and "ret21" in r.out]
    pop4 = Pop(p4_recs, BLOCK, "P4")
    p4_res, gauge, p4_floor, p4_counts = run_p4(pop4, r2)
    p3_p = r3.p if w3_raw != "UNDERPOWERED" and math.isfinite(r3.p) else 1.0
    p4_p = p4_res.p if p4_floor and math.isfinite(p4_res.p) else 1.0
    adj = holm({"P3": p3_p, "P4": p4_p})
    w3 = holm_word(w3_raw, adj["P3"][0])
    w4 = p4_word(p4_floor, p4_res, gauge, adj["P4"][0])
    report_p4(p4_res, gauge, p4_floor, p4_counts, adj, w4)

    report_printed_only(ins)
    report_sensitivity(ins, p4_recs, r2)
    fwd = report_forward(b)

    read = read_word(w1, w2)
    verdict(era, ins, r1, r1m, r1p, r2, r3, r3u, w1, w2, w3_raw, w3, read,
            p4_res, gauge, p4_floor, p4_counts, adj, w4, fwd)
    return 0


def report_population(b: Built, ins: list[Rec]) -> None:
    section("POPULATION AND DROPS")
    c = b.counts
    scope = Counter(r.scope for r in b.recs)
    print(f"  MARKET rows read                 {c['market_rows']}")
    print(f"  readable after the seal guard    {c['readable_dates']} dates "
          f"({b.seal['rows']} rows on {b.seal['dates']} dates withheld)")
    print(f"  AMBIGUOUS duplicate dates        {c['ambiguous']}")
    print(f"  OTHER (no direction in head)     {c['other']}  ({other_share(b):.1%}; "
          f"refusal above {OTHER_MAX:.0%})")
    print(f"  transition heads                 {c['transition']}")
    print(f"  off-calendar dates               {c['off_calendar']}  {', '.join(b.off_calendar)}")
    print(f"  no exact mechanical label        {c['no_mech']}  {', '.join(b.no_mech)}")
    for key in ("ret5", "ret10", "ret21", "ret21_next"):
        print(f"  window past table end, {key:<10} {c[f'past_end_{key}']}")
    print(f"  labelled dates by scope          in-sample {scope['in']}, gap {scope['gap']}, "
          f"forward {scope['fwd']}")
    print(f"  in-sample with closed ret21      {len(ins)} dates in "
          f"{len({r.i // BLOCK for r in ins})} blocks")
    novol = sum(1 for r in ins if r.label.vol is None)
    nomvol = sum(1 for r in ins if mech_vol_group(r) is None)
    print(f"  in-sample, no model vol token    {novol} (out of P3 only)")
    print(f"  in-sample, no mechanical vol     {nomvol} (out of P3 only)")
    lag = Counter(r.lag for r in ins)
    print("  in-sample lag bins               " + ", ".join(f"{k} {lag[k]}" for k in LAG_BINS))


def report_census(b: Built) -> None:
    section("VOCABULARY CENSUS (readable rows; head decides the tuple)")
    heads = Counter((lb.head, lb.tuple()) for _, _, lb in b.census)
    print(f"  {len(b.census)} rows, {len({raw for _, raw, _ in b.census})} distinct strings, "
          f"{len({lb.head for _, _, lb in b.census})} distinct heads")
    print("  by head:  dir   vol   risk     HP T   n   head")
    for (head, tup), n in sorted(heads.items(), key=lambda kv: (-kv[1], kv[0][0])):
        print(f"            {tup} {n:3d}   {head[:80]}")
    print("  every distinct string (date of first use, tuple, string clipped):")
    seen = set()
    for d, raw, lb in sorted(b.census, key=lambda x: x[0]):
        if raw in seen:
            continue
        seen.add(raw)
        print(f"    {d} {lb.tuple()} | {raw[:96]}")


def report_duplicates(b: Built) -> None:
    section("TEST-RETEST — dates carried by two MARKET rows")
    if not b.duplicates:
        print("  none on this era")
        return
    agree = sum(1 for f in b.duplicates if f["agree"])
    print(f"  {len(b.duplicates)} duplicate dates; direction agrees on {agree}, "
          f"differs on {len(b.duplicates) - agree} (AMBIGUOUS, out of every statistic)")
    for f in b.duplicates:
        tag = "agree -> counted once" if f["agree"] else "AMBIGUOUS"
        print(f"  {f['date']}  {tag}")
        for created, lb in f["rows"]:
            print(f"    created {created[:19]}  {lb.tuple()} | {lb.head[:70]}")
        vols = {lb.vol for _, lb in f["rows"]}
        risks = {lb.risk for _, lb in f["rows"]}
        print(f"    vol {'agrees' if len(vols) == 1 else 'differs'}, "
              f"risk {'agrees' if len(risks) == 1 else 'differs'}")


def report_lag_by_label(b: Built) -> None:
    section("LAG BIN BY LABEL (readable, deduped dates; partitions, never predicts)")
    tab = Counter((lag, lb.dir) for _, _, lb, lag in b.singles)
    cols = ("BULL", "BEAR", "RANGE", "OTHER")
    print("  lag       " + "".join(f"{c:>7}" for c in cols) + "   total")
    for lag in LAG_BINS:
        n = [tab[(lag, c)] for c in cols]
        print(f"  {lag:<9} " + "".join(f"{x:>7}" for x in n) + f"   {sum(n):>5}")
    vt = Counter((lag, lb.vol or "none") for _, _, lb, lag in b.singles)
    vcols = (*VOLS, "none")
    print("\n  lag       " + "".join(f"{c:>7}" for c in vcols))
    for lag in LAG_BINS:
        print(f"  {lag:<9} " + "".join(f"{vt[(lag, c)]:>7}" for c in vcols))
    scope = Counter((lag, "in" if d < era_mod.SEAL_START else "late") for d, _, _, lag in b.singles)
    print("\n  by scope: " + ", ".join(f"{lag} in-sample {scope[(lag, 'in')]} / later "
                                       f"{scope[(lag, 'late')]}" for lag in LAG_BINS))


def report_confusion(ins: list[Rec]) -> None:
    section("MODEL AGAINST MECHANICAL — confusion matrices (in-sample)")
    for cut, rs in lag_cuts(ins).items():
        print(f"  [{cut}] direction: rows model, columns mech")
        t = Counter((r.label.dir, r.mdir) for r in rs)
        print("            " + "".join(f"{c:>7}" for c in MECH_DIRS))
        for m in DIRS:
            print(f"    {m:<7} " + "".join(f"{t[(m, c)]:>7}" for c in MECH_DIRS))
        print(f"  [{cut}] vol: rows model, columns mech")
        mv = ("E-VOL", "H-VOL", "L-VOL", None)
        t = Counter((r.label.vol, r.mvol) for r in rs)
        print("            " + "".join(f"{c or 'none':>7}" for c in mv))
        for m in (*VOLS, None):
            print(f"    {m or 'none':<7} " + "".join(f"{t[(m, c)]:>7}" for c in mv))


def report_p1(pop: Pop, r1: Result, r1m: Result, r1p: Result, w1: str) -> None:
    section("P1 — 21-session forward SPY log return, model BULL minus non-BULL")
    print("  units: percentage points of log return; CI is the 95% block-bootstrap interval")
    print(f"  P1      {ci(r1)}  {_arms(r1, ('BULL', 'nonBULL'))}  p={_p(r1.p)}  {w1}")
    print(f"  P1m     {ci(r1m)}  {_arms(r1m, ('mBULL', 'mnonBULL'))}  p={_p(r1m.p)}  "
          f"(control, printed)")
    print(f"  P1-P1m  {ci(r1p)}  paired on shared draws  p={_p(r1p.p)}  (printed)")
    print(f"  draws kept {r1.kept} of {BOOT_N}; P1 floor {ARM_DATES} dates and "
          f"{ARM_BLOCKS} blocks per arm: {'met' if arm_floor(r1) else 'NOT met'}")
    print("\n  arm means, cut three ways (ret21, %):")
    for cut, rs in lag_cuts(pop.recs).items():
        bits = []
        for nm, pred in (("BULL", is_bull), ("BEAR", lambda r: r.label.dir == "BEAR"),
                         ("RANGE", lambda r: r.label.dir == "RANGE"),
                         ("mBULL", is_mech_bull), ("mnonBULL", is_mech_nonbull)):
            v = [r.out["ret21"] for r in rs if pred(r)]
            bits.append(f"{nm} {_f(np.mean(v) if v else float('nan'))} (n {len(v)})")
        print(f"    [{cut:<5}] " + "  ".join(bits))


def report_p2(r2: Result, w2: str) -> None:
    section("P2 — P1 within mechanical-direction strata, fixed pooled-share weights")
    print(f"  P2      {ci(r2)}  p={_p(r2.p)}  discarded draws {r2.discarded}  {w2}")
    for s, v in r2.strata.items():
        mark = f"enters, weight {r2.weights[s]:.3f}" if s in r2.weights else "below the stratum floor"
        print(f"    mech {s:<6} BULL {v['A'][0]:3d}d/{v['A'][1]:2d}b  nonBULL {v['B'][0]:3d}d/"
              f"{v['B'][1]:2d}b  diff {_f(v['diff'])}  {mark}")


def report_p3(pop: Pop, r3: Result, r3u: Result, w3_raw: str) -> None:
    section("P3 — 21-session drawdown depth dd21 = -mae21, model E-VOL minus not E-VOL")
    print("  within mechanical vol (L-VOL; H/E-VOL pooled); a positive value means E-VOL "
          "dates fell further")
    print(f"  P3      {ci(r3)}  p={_p(r3.p)}  discarded draws {r3.discarded}  "
          f"word before Holm {w3_raw}")
    print(f"  arms    {_arms(r3u, ('E-VOL', 'other'))}  (per-arm floor {ARM_DATES}d/"
          f"{ARM_BLOCKS}b: {'met' if arm_floor(r3u) else 'NOT met'})")
    for s, v in r3.strata.items():
        mark = f"enters, weight {r3.weights[s]:.3f}" if s in r3.weights else "below the stratum floor"
        print(f"    mech {s:<7} E-VOL {v['A'][0]:3d}d/{v['A'][1]:2d}b  other {v['B'][0]:3d}d/"
              f"{v['B'][1]:2d}b  diff {_f(v['diff'])}  {mark}")
    print("\n  printed twins (no verdict):")
    for cut, rs in lag_cuts(pop.recs).items():
        cp = Pop(rs, BLOCK)
        print(f"  [{cut}] {len(rs)} dates")
        print(f"    RISK-OFF, stratified dd21   {ci(p3(cp, token_of=lambda r: r.label.risk == 'RISK-OFF'))}")
        print(f"    HP, stratified dd21         {ci(p3(cp, token_of=lambda r: r.label.hp))}")
        print(f"    E-VOL, unstratified dd21    {ci(p3_unstratified(cp))}")
        mech = mean_diff(cp, "dd21", lambda r: r.mvol == "E-VOL",
                         lambda r: r.mvol in ("H-VOL", "L-VOL"))
        print(f"    mech E-VOL, unstratified    {ci(mech)}  {_arms(mech, ('mE-VOL', 'mother'))}")
        print(f"    E-VOL, stratified rv21      {ci(p3(cp, key='rv21'), scale=1.0)}  (% per day)")
        a, bb = p3_arms()
        for nm, pred in (("E-VOL", a), ("other", bb)):
            v = [r.out["mae21"] for r in rs if pred(r) and "mae21" in r.out]
            s3 = np.mean([x < -0.03 for x in v]) if v else float("nan")
            s5 = np.mean([x < -0.05 for x in v]) if v else float("nan")
            print(f"    share mae21 < -3% / < -5%, {nm:<6} {_f(s3, 100, '.1f')}% / "
                  f"{_f(s5, 100, '.1f')}%  (n {len(v)})")


def run_p4(pop4: Pop, r2: Result):
    retro = lambda r: r.lag == "RETRO"  # noqa: E731
    live = lambda r: r.lag == "LIVE"  # noqa: E731
    counts = {"RETRO": (sum(1 for r in pop4.recs if retro(r)),
                        len({r.i // BLOCK for r in pop4.recs if retro(r)})),
              "LIVE": (sum(1 for r in pop4.recs if live(r)),
                       len({r.i // BLOCK for r in pop4.recs if live(r)}))}
    floor = (counts["RETRO"][1] >= P4_RETRO_BLOCKS and counts["LIVE"][1] >= P4_LIVE_BLOCKS
             and counts["LIVE"][0] >= P4_LIVE_DATES and bool(r2.weights))
    fixed = (list(r2.weights), dict(r2.weights))
    if r2.weights:
        a = p2(pop4, fixed=fixed, where=retro)
        b = p2(pop4, fixed=fixed, where=live)
        res = summarize(Result(point=a.point - b.point), a.draws - b.draws)
        res.strata = {"RETRO": a.point, "LIVE": b.point}
    else:
        res = Result()
    ga = mean_diff(pop4, "ret21", lambda r: retro(r) and is_mech_bull(r),
                   lambda r: retro(r) and is_mech_nonbull(r))
    gb = mean_diff(pop4, "ret21", lambda r: live(r) and is_mech_bull(r),
                   lambda r: live(r) and is_mech_nonbull(r))
    gauge = summarize(Result(point=ga.point - gb.point), ga.draws - gb.draws)
    gauge.strata = {"RETRO": ga.point, "LIVE": gb.point}
    return res, gauge, floor, counts


def report_p4(res: Result, gauge: Result, floor: bool, counts: dict, adj: dict, w4: str) -> None:
    section("P4 — recall: the P2 statistic on RETRO minus on LIVE (NEAR, UNKNOWN out)")
    print(f"  RETRO {counts['RETRO'][0]} dates in {counts['RETRO'][1]} blocks (floor "
          f"{P4_RETRO_BLOCKS} blocks); LIVE {counts['LIVE'][0]} dates in {counts['LIVE'][1]} "
          f"blocks (floor {P4_LIVE_BLOCKS} blocks, {P4_LIVE_DATES} dates): "
          f"{'met' if floor else 'NOT met'}")
    print(f"  P2 on RETRO {_f(res.strata.get('RETRO'))}  on LIVE {_f(res.strata.get('LIVE'))}")
    print(f"  P4      {ci(res)}  p={_p(res.p)}  discarded draws {res.discarded}")
    print(f"  tape gauge (P1m RETRO {_f(gauge.strata['RETRO'])} minus LIVE "
          f"{_f(gauge.strata['LIVE'])})  {ci(gauge)}")
    print(f"  Holm m=2: P3 adj p {_p(adj['P3'][0])}, P4 adj p {_p(adj['P4'][0])} "
          f"(P4 enters at p = 1 until gradable)")
    print(f"  P4 word: {w4}")


def report_printed_only(ins: list[Rec]) -> None:
    section("PRINTED ONLY — ret5, ret10, and the window starting at the next close")
    for cut, rs in lag_cuts(ins).items():
        pop = Pop(rs, BLOCK)
        print(f"  [{cut}] {len(rs)} dates")
        for key in ("ret5", "ret10"):
            a, m = p1(pop, key), p1m(pop, key)
            print(f"    {key:<10} model {ci(a)}  mech {ci(m)}")
        a, s = p1(pop, "ret21_next"), p2(pop, "ret21_next")
        print(f"    next-close P1 {ci(a)}  {_arms(a, ('BULL', 'nonBULL'))}")
        print(f"    next-close P2 {ci(s)}")
    section("PRINTED ONLY — model vol token against rv21, within mechanical vol (% per day)")
    for cut, rs in lag_cuts(ins).items():
        print(f"  [{cut}]  mech vol -> model vol: mean rv21 (n)")
        for mv in ("L-VOL", "H-VOL", "E-VOL"):
            bits = []
            for v in (*VOLS, None):
                x = [r.out["rv21"] for r in rs if r.mvol == mv and r.label.vol == v and "rv21" in r.out]
                bits.append(f"{v or 'none'} {np.mean(x):.2f} ({len(x)})" if x else f"{v or 'none'} — (0)")
            print(f"    mech {mv:<6} " + "  ".join(bits))


def report_sensitivity(ins: list[Rec], p4_recs: list[Rec], r2: Result) -> None:
    section("SENSITIVITY — mandatory window cuts (protocol.window_cuts), printed only")
    for name, rs in P.window_cuts(ins).items():
        print(f"  {name}")
        print_contrasts(rs, BLOCK, indent="    ")
    section(f"SENSITIVITY — {BLOCK_SENS}-session blocks, printed only")
    print_contrasts(ins, BLOCK_SENS)
    pop4 = Pop(p4_recs, BLOCK_SENS)
    if r2.weights:
        fixed = (list(r2.weights), dict(r2.weights))
        a = p2(pop4, fixed=fixed, where=lambda r: r.lag == "RETRO")
        b = p2(pop4, fixed=fixed, where=lambda r: r.lag == "LIVE")
        print(f"  P4 on {BLOCK_SENS}-session blocks  "
              f"{ci(summarize(Result(point=a.point - b.point), a.draws - b.draws))}")


def report_forward(b: Built) -> dict:
    section(f"FORWARD — P1 and P2 on signal dates after {FWD_AFTER}")
    fwd = [r for r in b.recs if r.scope == "fwd" and "ret21" in r.out]
    blocks = len({r.i // BLOCK for r in fwd})
    print(f"  seal lifted: {era_mod.SEAL_LIFTED or 'no — forward dates are withheld'}")
    print(f"  forward dates with a closed window: {len(fwd)} in {blocks} blocks "
          f"(floor {FWD_DATES} dates in {FWD_BLOCKS} blocks)")
    out = {"n": len(fwd), "blocks": blocks, "p1": "STILL-OPEN", "p2": "STILL-OPEN",
           "read": "STILL-OPEN"}
    if era_mod.SEAL_LIFTED is None or len(fwd) < FWD_DATES or blocks < FWD_BLOCKS:
        print("  forward: STILL-OPEN")
        return out
    pop = Pop(fwd, BLOCK, "forward")
    a, s = p1(pop), p2(pop)
    out["p1"] = "STILL-OPEN" if word(a.lo, a.hi, True) == "UNDERPOWERED" else word(a.lo, a.hi, True)
    w = word(s.lo, s.hi, bool(s.weights))
    out["p2"] = "STILL-OPEN" if w == "UNDERPOWERED" else w
    out["read"] = forward_read(out["p1"], out["p2"])
    print(f"  forward P1 {ci(a)}  {out['p1']}")
    print(f"  forward P2 {ci(s)}  {out['p2']}")
    print(f"  forward READ {out['read']}")
    return out


def _tag(w: str, w4: str) -> str:
    return f"{w} (recall unexcluded)" if w == "SUPPORTED" and w4 != "RECALL-NOT-SHOWN" else w


def verdict(era, ins, r1, r1m, r1p, r2, r3, r3u, w1, w2, w3_raw, w3, read,
            p4_res, gauge, p4_floor, p4_counts, adj, w4, fwd) -> None:
    section("VERDICT")
    print(f"  era {era}, signal dates before {era_mod.SEAL_START}: {len(ins)} dates in "
          f"{len({r.i // BLOCK for r in ins})} blocks; {BOOT_N} block draws, seed {SEED}")
    print("  ret21 / dd21 in percentage points; [95% CI] ±half-width")
    print(f"  P1     {ci(r1)}  {_arms(r1, ('BULL', 'nonBULL'))}  p={_p(r1.p)}")
    print(f"  P1m    {ci(r1m)}  {_arms(r1m, ('mBULL', 'mnonBULL'))}  (control)")
    print(f"  P1-P1m {ci(r1p)}  (paired, printed)")
    ent = ", ".join(f"{s} {w:.2f}" for s, w in r2.weights.items()) or "none"
    print(f"  P2     {ci(r2)}  strata entering: {ent}; discarded draws {r2.discarded}")
    print(f"  P3     {ci(r3)}  {_arms(r3u, ('E-VOL', 'other'))}  p={_p(r3.p)}  "
          f"before Holm {w3_raw}, Holm adj p {_p(adj['P3'][0])}")
    print(f"  P4     {ci(p4_res)}  RETRO {p4_counts['RETRO'][0]}d/{p4_counts['RETRO'][1]}b  "
          f"LIVE {p4_counts['LIVE'][0]}d/{p4_counts['LIVE'][1]}b  floors "
          f"{'met' if p4_floor else 'NOT met'}; tape gauge {_f(gauge.point)}")
    read_tag = read
    if read in ("MODEL-ADDS", "MECH-COVERS", "INCREMENTAL-ONLY") and w4 != "RECALL-NOT-SHOWN":
        read_tag = f"{read} (recall unexcluded)"
    print()
    print(f"  >>> market_read P1 (model BULL - non-BULL, 21d fwd SPY, {era} pre-seal): "
          f"{_tag(w1, w4)} <<<")
    print(f"  >>> market_read P2 (P1 within mech direction): {_tag(w2, w4)} <<<")
    print(f"  >>> market_read READ (P1+P2): {read_tag} <<<")
    print(f"  >>> market_read P3 (sizing, E-VOL, 21d drawdown, Holm m=2): {_tag(w3, w4)} <<<")
    print(f"  >>> market_read P4 (recall, RETRO - LIVE): {w4} <<<")
    print(f"  >>> market_read FORWARD (P1, P2, dates after registration): {fwd['read']} <<<")
    print()
    print("  P1 and P2 are read together at 5% each; P3 and P4 are one Holm family (m = 2).")
    print("  The forward verdict of record is the first forward run printing a token other "
          "than STILL-OPEN.")
    print("  Nothing ships from this study (market_read.md).")


if __name__ == "__main__":
    sys.exit(main())
