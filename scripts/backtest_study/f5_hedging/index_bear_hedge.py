"""index_bear_hedge — do the book's index bear plays pay for themselves as crash insurance?

Registration: `research/pre-registrations/f5_hedging/index_bear_hedge.md`
(ACCEPTED BY DEFAULT 2026-10-09 on the drafter's recommended defaults, with OD4
decided as forward-only). That file is the spec; this module implements it and
adds nothing to its bar. RESEARCH TIER: nothing ships from this study, and no
verdict here removes the deployment-rules §4 bear sleeve.

WHAT IS GRADED. Only FUTURE sell-offs (OD4 (b)): every E-DD5 episode whose peak
falls after `ACCEPTED`, once its buffer has closed. Until `FORWARD_FLOOR` such
episodes are evaluable the forward verdict reads STILL-OPEN; at `SUNSET` with
fewer it reads UNDERPOWERED. The declared secondary is the draft's two-episode
confirmation clause, printed beside it as the EARLY READ.

WHAT IS DESCRIBED. The in-sample episodes of the era (five on v4) are printed
in full — M1 protection, M2 carry, M3 net, the permutation p, the robustness
battery and the criterion vector — under a DESCRIPTION banner. No verdict word
is ever printed for them. That is OD4: the analysis was written by a model
whose training data may include those sell-offs, so an in-sample result could
be recall.

THE HOLDOUT SEAL. The book comes from `load_book` with no `sealed_read`, so
every signal date from `era.SEAL_START` on is withheld. This registration was
accepted on 2026-10-09 and is not in `era.SEALED_READERS`: its forward window
reads nothing until `era.SEAL_LIFTED` is set. `_apply_seal` repeats the guard
on the returned rows so the study is sealed even on a checkout whose loader
predates the guard.

Curves: `lib/mtm_curve.book_curves(target=TARGET_STORED)` per weight group —
net of `cost_total`, G-MTM at the shipped tolerance, never widened. The sleeve
carries each index bear at `1 / n_indexbear(signal date)`, so book_curves runs
once per distinct `n` and the scaled levels are summed on one session axis.

Gates: G-ERA (load_book) · G-MTM (exit 4) · G-HASH (exit 5) · G-CENSUS (the
census prints before any outcome column is read) · G-OPEN (per episode; a
failing episode is NOT EVALUABLE, not a refusal).

Run:
    python -m scripts.backtest_study run index_bear_hedge
    STUDY_ERA=v3 python -m scripts.backtest_study run index_bear_hedge   # same-episode replication
    python -m scripts.backtest_study.f5_hedging.index_bear_hedge --fetch-base-rate   # OD5, network
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection import ticker_class as TC  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import hedge_criteria as HC  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as M  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402

# 2 thin era / 3 era mismatch belong to lib/era.py. G-MTM (4) and G-HASH (5)
# are real failures, not designed refusals, so they are not listed here.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
EXIT_GMTM = 4
EXIT_GHASH = 5

# ════════════════════════════════════════════════════════════════════════════
# Registered constants
# ════════════════════════════════════════════════════════════════════════════
REGISTRATION = "research/pre-registrations/f5_hedging/index_bear_hedge.md"
ACCEPTED = "2026-10-09"
#: Sunset: three years from acceptance.
SUNSET = "2029-10-09"

SPY_VIX_CSV = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"
#: OD5: a separate, longer SPY history used for the base rate only.
BASE_RATE_CSV = ROOT / "backtests" / "mech_regime" / "spy_base_rate_daily.csv"
BASE_RATE_START = "1993-01-29"

#: The episode definitions, as data. G-HASH is sha256 over the canonical JSON
#: of this dict; changing any value is a new registration.
EPISODE_DEFS: dict = {
    "E-DD5": {"kind": "drawdown", "lookback": 63, "trigger": -0.05,
              "recover": -0.02, "trough_max": 42},
    "E-DD8": {"kind": "drawdown", "lookback": 63, "trigger": -0.08,
              "recover": -0.02, "trough_max": 42},
    "E-VIX25": {"kind": "vix", "run_level": 25.0, "stretch_level": 20.0,
                "max_back": 21},
    "E-20D5": {"kind": "return20", "horizon": 20, "threshold": -0.05},
    "_common": {"merge_gap": 10, "buffer": 10, "peak_tie": "latest",
                "trough_tie": "earliest", "calendar": "spy_trading_days"},
}
PRIMARY = "E-DD5"
SECONDARY = ("E-DD8", "E-VIX25", "E-20D5")
#: Recorded in the registration at acceptance (G-HASH).
EPISODE_DEFS_SHA256 = "6320a5e3ddc22615189a4c9c4137dc6b0bc0a6b4e3e0e1592e2776087e815e5b"

#: Power floor and evaluability (registration, "Power floor").
FLOOR = 5
MIN_EP_SLEEVE = 3
MIN_EP_SESSIONS = 5
OPEN_MAX = 0.25
#: The declared secondary forward read (the draft's confirmation clause).
EARLY_FLOOR = 2
#: Permutation: every circular shift of at least this many sessions.
MIN_SHIFT = 21
ALPHA = 0.05
TOP_K = 3

ARMS = ("B", "H", "H-raw", "H-stock")


# ════════════════════════════════════════════════════════════════════════════
# The seal
# ════════════════════════════════════════════════════════════════════════════

def seal_lifted() -> bool:
    return bool(getattr(era, "SEAL_LIFTED", None))


def _apply_seal(recs: list[dict]) -> tuple[list[dict], dict]:
    """Withhold sealed signal dates — `era.drop_sealed` with no reader.

    `load_book` already does this; repeating it is a no-op there and keeps the
    study sealed on a checkout whose loader predates the guard.
    """
    drop = getattr(era, "drop_sealed", None)
    if drop is not None:
        return drop(recs, "date")
    start = "2026-09-23"   # era.SEAL_START, for a loader that predates it
    kept = [r for r in recs if str(r["date"])[:10] < start]
    held = [r for r in recs if str(r["date"])[:10] >= start]
    return kept, {"rows": len(held), "dates": len({r["date"] for r in held}),
                  "reader": None}


# ════════════════════════════════════════════════════════════════════════════
# Hashes (G-HASH)
# ════════════════════════════════════════════════════════════════════════════

def episode_defs_hash(defs: dict | None = None) -> str:
    blob = json.dumps(EPISODE_DEFS if defs is None else defs, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def gate_hash() -> list[str]:
    """Failures of G-HASH, empty when both hashes match."""
    bad = []
    if episode_defs_hash() != EPISODE_DEFS_SHA256:
        bad.append(f"episode definitions hash {episode_defs_hash()[:12]} is not "
                   f"the registered {EPISODE_DEFS_SHA256[:12]}")
    if TC.table_hash() != TC.GROUPS_V1_SHA256:
        bad.append(f"GT3 group table hash {TC.table_hash()[:12]} is not "
                   f"{TC.GROUPS_V1_SHA256[:12]}")
    return bad


# ════════════════════════════════════════════════════════════════════════════
# Market series and episodes
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Series:
    """SPY (and VIX) closes on the SPY trading calendar."""
    dates: list[str]
    spy: list[float]
    vix: list[float | None]

    def index(self, d: str) -> int:
        return self.dates.index(d)


def _f(v) -> float | None:
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def load_series(path: Path = SPY_VIX_CSV) -> Series:
    """Rows with a SPY close, in date order. A VIX-only row is not a session."""
    dates, spy, vix = [], [], []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            s = _f(row.get("spy_close"))
            if s is None:
                continue
            dates.append(str(row["date"])[:10])
            spy.append(s)
            vix.append(_f(row.get("vix_close")))
    order = sorted(range(len(dates)), key=lambda i: dates[i])
    return Series([dates[i] for i in order], [spy[i] for i in order],
                  [vix[i] for i in order])


@dataclass
class Episode:
    """One sell-off window [peak, trough] on the SPY calendar.

    `closed` is False when the data ends before the episode's trough is fixed;
    `buffer_end` is None when the data ends inside the buffer.
    """
    definition: str
    peak: str
    trough: str
    peak_i: int
    trough_i: int
    closed: bool
    buffer_end: str | None = None
    spy_move: float = float("nan")
    max_vix: float | None = None

    @property
    def label(self) -> str:
        return f"{self.peak[:7]}/{self.trough[5:7]}"


def drawdowns(spy: list[float], lookback: int) -> list[float | None]:
    """`dd_t = close_t / max(close over the trailing lookback rows, incl. t) - 1`.

    Undefined (None) until a full `lookback` rows exist.
    """
    out: list[float | None] = []
    for i in range(len(spy)):
        if i < lookback - 1:
            out.append(None)
            continue
        hi = max(spy[i - lookback + 1:i + 1])
        out.append(spy[i] / hi - 1.0)
    return out


def dd_episodes(s: Series, p: dict) -> list[Episode]:
    """Drawdown episodes (E-DD5 / E-DD8), before merging."""
    lb, trig, rec, tmax = p["lookback"], p["trigger"], p["recover"], p["trough_max"]
    dd = drawdowns(s.spy, lb)
    n = len(s.spy)
    out: list[Episode] = []
    i = 0
    while i < n:
        if dd[i] is None or dd[i] > trig:
            i += 1
            continue
        i0 = i
        lo = i0 - lb + 1
        hi_val = max(s.spy[lo:i0 + 1])
        peak_i = max(j for j in range(lo, i0 + 1) if s.spy[j] == hi_val)  # ties: latest
        r = next((j for j in range(i0 + 1, n)
                  if dd[j] is not None and dd[j] > rec), None)
        stop = r if r is not None else n
        last_trig = max(j for j in range(i0, stop) if dd[j] is not None and dd[j] <= trig)
        end = min(stop - 1, last_trig + tmax)
        closed = r is not None or last_trig + tmax <= n - 1
        seg = range(i0, end + 1)
        lo_val = min(s.spy[j] for j in seg)
        trough_i = min(j for j in seg if s.spy[j] == lo_val)       # ties: earliest
        out.append(Episode("", s.dates[peak_i], s.dates[trough_i], peak_i,
                           trough_i, closed))
        if r is None:
            break
        i = r
    return out


def vix_episodes(s: Series, p: dict) -> list[Episode]:
    """E-VIX25: a run of VIX closes >= 25, extended back over the VIX >= 20
    stretch that leads into it, by at most `max_back` rows."""
    out: list[Episode] = []
    n = len(s.vix)
    i = 0
    while i < n:
        v = s.vix[i]
        if v is None or v < p["run_level"]:
            i += 1
            continue
        a = i
        while i + 1 < n and s.vix[i + 1] is not None and s.vix[i + 1] >= p["run_level"]:
            i += 1
        b = i
        start = a
        while (start - 1 >= 0 and a - (start - 1) <= p["max_back"]
               and s.vix[start - 1] is not None
               and s.vix[start - 1] >= p["stretch_level"]):
            start -= 1
        out.append(Episode("", s.dates[start], s.dates[b], start, b,
                           closed=b < n - 1))
        i = b + 1
    return out


def ret20_episodes(s: Series, p: dict) -> list[Episode]:
    """E-20D5: the union of every 20-session span whose SPY return <= -5%."""
    h, thr = p["horizon"], p["threshold"]
    spans = [(t - h, t) for t in range(h, len(s.spy))
             if s.spy[t] / s.spy[t - h] - 1.0 <= thr]
    out: list[Episode] = []
    for a, b in spans:
        if out and a <= out[-1].trough_i:
            last = out[-1]
            last.trough_i = max(last.trough_i, b)
            last.trough = s.dates[last.trough_i]
            continue
        out.append(Episode("", s.dates[a], s.dates[b], a, b, closed=True))
    if out:
        out[-1].closed = out[-1].trough_i < len(s.spy) - 1
    return out


def merge(eps: list[Episode], s: Series, gap: int, by_low: bool) -> list[Episode]:
    """Merge episodes fewer than `gap` sessions apart (trough to next peak).

    A merged episode keeps the earliest peak and, for drawdown definitions, the
    lowest close (`by_low`); otherwise the later end.
    """
    out: list[Episode] = []
    for e in eps:
        if out and e.peak_i - out[-1].trough_i < gap:
            prev = out[-1]
            if by_low:
                if s.spy[e.trough_i] < s.spy[prev.trough_i]:
                    prev.trough_i, prev.trough = e.trough_i, e.trough
            else:
                prev.trough_i, prev.trough = e.trough_i, e.trough
            prev.closed = e.closed
            continue
        out.append(e)
    return out


def episodes(s: Series, name: str, defs: dict | None = None) -> list[Episode]:
    """Every episode of definition `name` on `s`, merged, with its descriptors."""
    defs = defs or EPISODE_DEFS
    p, common = defs[name], defs["_common"]
    kind = p["kind"]
    raw = (dd_episodes(s, p) if kind == "drawdown"
           else vix_episodes(s, p) if kind == "vix"
           else ret20_episodes(s, p))
    eps = merge(raw, s, common["merge_gap"], by_low=(kind == "drawdown"))
    for e in eps:
        e.definition = name
        e.spy_move = s.spy[e.trough_i] / s.spy[e.peak_i] - 1.0
        vs = [v for v in s.vix[e.peak_i:e.trough_i + 1] if v is not None]
        e.max_vix = max(vs) if vs else None
        bi = e.trough_i + common["buffer"]
        e.buffer_end = s.dates[bi] if (e.closed and bi < len(s.dates)) else None
    return eps


def dd_defined_sessions(s: Series, lookback: int = 63) -> int:
    return sum(1 for v in drawdowns(s.spy, lookback) if v is not None)


def observed_rate(s: Series, name: str = PRIMARY) -> tuple[int, int, float]:
    """`(closed episodes, sessions with dd defined, episodes per 252 sessions)`."""
    eps = [e for e in episodes(s, name) if e.closed]
    n_sess = dd_defined_sessions(s, EPISODE_DEFS[name]["lookback"])
    return len(eps), n_sess, (len(eps) / n_sess * 252.0) if n_sess else float("nan")


# ════════════════════════════════════════════════════════════════════════════
# The book: deployed sleeve, index-bear sleeve, stock-bear sleeve
# ════════════════════════════════════════════════════════════════════════════

def is_index_bear(rec) -> bool:
    return (TC.group_of(rec["ticker"]) == TC.G1
            and TC.direction(rec["structure"]) == "bear")


def is_stock_bear(rec) -> bool:
    return (TC.group_of(rec["ticker"]) in TC.SINGLE_STOCK
            and TC.direction(rec["structure"]) == "bear")


def deployed(recs: list[dict]) -> list[dict]:
    """`top_k_per_day(ladder_rank, k=3, A|B)` over the whole book, then minus
    any index bear it picked. No back-fill (Resolved at build 2026-10-09)."""
    picks = P.top_k_per_day(recs, P.ladder_rank, k=TOP_K,
                            eligible_fn=P.ladder_eligible)
    return [r for r in picks if not is_index_bear(r)]


def unit_weights(rows: list[dict]) -> dict[int, float]:
    """id(row) -> 1 / (rows on that row's signal date): one risk unit per date."""
    n = Counter(r["date"] for r in rows)
    return {id(r): 1.0 / n[r["date"]] for r in rows}


def scheduled_end(rec) -> date:
    """Last calendar day of the scheduled span [signal, signal + DTE].

    A descriptor only. A row with no DTE falls back to its price grid's end.
    """
    d0 = date.fromisoformat(str(rec["date"])[:10])
    dte = rec.get("dte")
    if dte is not None and dte == dte:
        return d0 + timedelta(days=int(round(dte)))
    return rec["t"].grid[-1]


def open_into(rec, e: Episode) -> bool:
    d0 = date.fromisoformat(str(rec["date"])[:10])
    return d0 <= date.fromisoformat(e.trough) and scheduled_end(rec) >= date.fromisoformat(e.peak)


def entered_in(rec, e: Episode) -> bool:
    return e.peak <= str(rec["date"])[:10] <= e.trough


def open_at_data_end(rec) -> bool:
    return (rec["t"].row.get("path_status") or "").strip() == "open_at_data_end"


# ════════════════════════════════════════════════════════════════════════════
# Curves
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class CurveSet:
    """Scaled level series from one or more `book_curves` calls."""
    parts: list[tuple[list[date], list[float]]] = field(default_factory=list)
    mismatches: list = field(default_factory=list)
    n_positions: int = 0
    n_reconciled: int = 0
    n_degraded: int = 0
    n_cost_netted: int = 0

    def sessions(self) -> set[date]:
        out: set[date] = set()
        for sess, _ in self.parts:
            out.update(sess)
        return out


def build_curves(recs: list[dict], weights: dict[int, float] | None = None) -> CurveSet:
    """Book curves for `recs`, one `book_curves` call per distinct weight."""
    from scripts.backtest_study.f5_hedging.hedge_portfolio import book_positions
    groups: dict[float, list[dict]] = defaultdict(list)
    for r in recs:
        groups[1.0 if weights is None else weights[id(r)]].append(r)
    cs = CurveSet()
    for w, rows in sorted(groups.items()):
        bc = M.book_curves(book_positions(rows), target=M.TARGET_STORED)
        cs.parts.append((bc.mtm.sessions, [w * v for v in bc.mtm.levels]))
        cs.mismatches.extend(bc.mismatches)
        cs.n_positions += bc.n_positions
        cs.n_reconciled += bc.n_reconciled
        cs.n_degraded += bc.n_degraded
        cs.n_cost_netted += bc.n_cost_netted
    return cs


def on_axis(cs: CurveSet, axis: list[date]) -> list[float]:
    """The summed level of `cs` at every axis session (carry-forward; 0 before)."""
    total = [0.0] * len(axis)
    for sess, lv in cs.parts:
        if not sess:
            continue
        for i, d in enumerate(axis):
            k = bisect.bisect_right(sess, d) - 1
            if k >= 0:
                total[i] += lv[k]
    return total


def to_daily(levels: list[float]) -> list[float]:
    out, prev = [], 0.0
    for v in levels:
        out.append(v - prev)
        prev = v
    return out


# ════════════════════════════════════════════════════════════════════════════
# Metrics
# ════════════════════════════════════════════════════════════════════════════

def window_indices(axis: list[date], e: Episode) -> list[int]:
    a, b = date.fromisoformat(e.peak), date.fromisoformat(e.trough)
    return [i for i, d in enumerate(axis) if a <= d <= b]


def window_dd(daily: list[float], idx: list[int]) -> float:
    """`DD_e = min_t (L(t) - max_{s in [first, t]} L(s))` over the window.

    Measured on per-session changes from the window's first session, which is
    the level formula for a contiguous window and stays defined for a window
    the permutation wraps around the end of the span.
    """
    if not idx:
        return float("nan")
    cum = peak = 0.0
    worst = 0.0
    for j, i in enumerate(idx):
        if j > 0:
            cum += daily[i]
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def window_gain(daily: list[float], idx: list[int]) -> float:
    """The sleeve's MTM dollars inside the window: level change across it."""
    return sum(daily[i] for i in idx[1:]) if idx else float("nan")


def classify(axis: list[date], eps: list[Episode], s: Series) -> list[str]:
    """Each axis session as `window`, `buffer`, `outside` or `unclassified`.

    Unclassified: before the drawdown is defined, after the SPY data ends, or
    after the peak of an episode the data has not closed.
    """
    first = date.fromisoformat(s.dates[EPISODE_DEFS[PRIMARY]["lookback"] - 1])
    last = date.fromisoformat(s.dates[-1])
    lab = []
    for d in axis:
        if d < first or d > last:
            lab.append("unclassified")
            continue
        tag = "outside"
        for e in eps:
            pk, tr = date.fromisoformat(e.peak), date.fromisoformat(e.trough)
            if not e.closed and d >= pk:
                tag = "unclassified"
                break
            if pk <= d <= tr:
                tag = "window"
                break
            if d > tr and (e.buffer_end is None or d <= date.fromisoformat(e.buffer_end)):
                tag = "buffer" if e.buffer_end is not None else "unclassified"
                break
        lab.append(tag)
    return lab


@dataclass
class EpisodeRead:
    episode: Episode
    n_sessions: int
    n_sleeve_open: int
    n_sleeve_entered: int
    n_book_open: int
    open_share: float
    evaluable: bool
    why: str
    dd_b: float = float("nan")
    dd_h: float = float("nan")
    delta: float = float("nan")
    gain: float = float("nan")


def episode_census(eps: list[Episode], axis: list[date], sleeve: list[dict],
                   book: list[dict]) -> list[EpisodeRead]:
    """Evaluability from descriptors only — no outcome column is read here."""
    out = []
    for e in eps:
        idx = window_indices(axis, e)
        sl_open = [r for r in sleeve if open_into(r, e)]
        share = (sum(open_at_data_end(r) for r in sl_open) / len(sl_open)
                 if sl_open else 0.0)
        why = []
        if not e.closed:
            why.append("not closed")
        if len(sl_open) < MIN_EP_SLEEVE:
            why.append(f"{len(sl_open)} sleeve open < {MIN_EP_SLEEVE}")
        if share > OPEN_MAX:
            why.append(f"G-OPEN {share:.0%} > {OPEN_MAX:.0%}")
        if len(idx) < MIN_EP_SESSIONS:
            why.append(f"{len(idx)} sessions < {MIN_EP_SESSIONS}")
        out.append(EpisodeRead(
            episode=e, n_sessions=len(idx), n_sleeve_open=len(sl_open),
            n_sleeve_entered=sum(entered_in(r, e) for r in sleeve),
            n_book_open=sum(open_into(r, e) for r in book),
            open_share=share, evaluable=not why, why="; ".join(why) or "evaluable"))
    return out


@dataclass
class Reading:
    """M1-M3 for one arm against B over a set of episodes."""
    episodes: list[EpisodeRead]
    sum_delta: float
    n: int
    n_positive: int
    median_delta: float
    carry: float
    n_outside: int
    buffer: float
    n_buffer: int
    gains_all: float
    unclassified: float
    net: float
    f_star: float | None
    mean_gain: float
    unharmed: bool
    mdd_b: float
    mdd_h: float
    worst_b: float
    worst_h: float


def read_arm(axis, b_daily, s_daily, census: list[EpisodeRead], labels,
             span: tuple[date, date] | None = None) -> Reading:
    """M1, M2 and M3 for sleeve `s_daily` carried on book `b_daily`.

    `span` restricts M2/M3 and the unharmed check to sessions in it (the
    forward read); None is the whole axis.
    """
    keep = [i for i, d in enumerate(axis)
            if span is None or span[0] <= d <= span[1]]
    h_daily = [b + s for b, s in zip(b_daily, s_daily)]
    reads = []
    for c in census:
        idx = window_indices(axis, c.episode)
        r = EpisodeRead(**{k: getattr(c, k) for k in c.__dataclass_fields__})
        if idx:
            r.dd_b = window_dd(b_daily, idx)
            r.dd_h = window_dd(h_daily, idx)
            r.delta = r.dd_h - r.dd_b
            r.gain = window_gain(s_daily, idx)
        reads.append(r)
    ev = [r for r in reads if r.evaluable]
    deltas = [r.delta for r in ev]
    outside = [i for i in keep if labels[i] == "outside"]
    buf = [i for i in keep if labels[i] == "buffer"]
    unc = [i for i in keep if labels[i] == "unclassified"]
    win = [i for i in keep if labels[i] == "window"]
    carry = sum(s_daily[i] for i in outside)
    gains = [r.gain for r in ev]
    mean_gain = statistics.fmean(gains) if gains else float("nan")
    per_sess = carry / len(outside) if outside else float("nan")
    f_star = (-per_sess / mean_gain * 252.0) if (gains and mean_gain > 0) else None
    bd = [b_daily[i] for i in keep]
    hd = [h_daily[i] for i in keep]
    mdd_b, mdd_h = HC.max_drawdown(bd), HC.max_drawdown(hd)
    worst_b, worst_h = (min(bd) if bd else 0.0), (min(hd) if hd else 0.0)
    return Reading(
        episodes=reads, sum_delta=sum(deltas), n=len(ev),
        n_positive=sum(1 for v in deltas if v > 0),
        median_delta=statistics.median(deltas) if deltas else float("nan"),
        carry=carry, n_outside=len(outside),
        buffer=sum(s_daily[i] for i in buf), n_buffer=len(buf),
        gains_all=sum(s_daily[i] for i in win),
        unclassified=sum(s_daily[i] for i in unc),
        net=sum(s_daily[i] for i in keep), f_star=f_star, mean_gain=mean_gain,
        unharmed=HC.unharmed(mdd_h, worst_h, mdd_b, worst_b),
        mdd_b=mdd_b, mdd_h=mdd_h, worst_b=worst_b, worst_h=worst_h)


def permutation_p(axis, b_daily, s_daily, eps: list[Episode],
                  min_shift: int = MIN_SHIFT) -> tuple[float, int, float]:
    """`(p, n_shifts, T)`: the circular-shift test on `T = sum dDD_e`.

    Every shift k in [min_shift, N - min_shift] moves all windows together,
    wrapping at the end of the span. p = (1 + #{T_k >= T}) / (1 + n_shifts).
    """
    h_daily = [b + s for b, s in zip(b_daily, s_daily)]
    n = len(axis)
    wins = [window_indices(axis, e) for e in eps]
    wins = [w for w in wins if w]

    def stat(shift):
        tot = 0.0
        for w in wins:
            idx = [(i + shift) % n for i in w]
            tot += window_dd(h_daily, idx) - window_dd(b_daily, idx)
        return tot

    t0 = stat(0)
    shifts = list(range(min_shift, n - min_shift + 1))
    if not shifts or not wins:
        return float("nan"), 0, t0
    ge = sum(1 for k in shifts if stat(k) >= t0 - 1e-9)
    return (1 + ge) / (1 + len(shifts)), len(shifts), t0


def sign(x: float) -> int:
    return 0 if (x != x or x == 0) else (1 if x > 0 else -1)


# ════════════════════════════════════════════════════════════════════════════
# The verdict grammar (applied to FORWARD episodes only — OD4)
# ════════════════════════════════════════════════════════════════════════════

def verdict(n: int, deltas: list[float], p: float, net: float, unharmed: bool,
            rb_hold: bool, rb5_fires: bool, floor: int = FLOOR,
            before_sunset: bool = True) -> str:
    """The registration's table, first match wins, with OD4's forward wording.

    Below the floor the forward read is STILL-OPEN until the sunset and
    UNDERPOWERED after it. No direction is quoted under either.
    """
    if n < floor:
        return "STILL-OPEN" if before_sunset else "UNDERPOWERED"
    pos = sum(1 for v in deltas if v > 0)
    nonpos = n - pos
    suffix = " — bear protection, not index-specific" if rb5_fires else ""
    if pos == n and p <= ALPHA and net > 0 and unharmed and rb_hold:
        return "EARNS ITS KEEP" + suffix
    if pos >= n - 1 and net <= 0:
        return "PROTECTS, COSTS MORE THAN IT SAVES" + suffix
    if nonpos >= 2 or statistics.median(deltas) <= 0:
        return "DOES NOT PROTECT"
    return "INDETERMINATE"


def early_read(deltas: list[float], carry_per_session: float,
               breakeven_carry: float | None, floor: int = EARLY_FLOOR) -> str:
    """The declared secondary: the draft's confirmation clause, forward only.

    PROTECTING needs >= `floor` evaluable forward episodes, every one with
    dDD > 0, and forward carry per outside session no worse than the carry at
    which the in-sample insurance breaks even at the observed episode rate.
    Any forward episode with dDD <= 0 reads NOT PROTECTING.
    """
    if any(v <= 0 for v in deltas):
        return "NOT PROTECTING"
    if len(deltas) < floor:
        return "STILL-OPEN"
    if breakeven_carry is None or carry_per_session != carry_per_session:
        return "STILL-OPEN"
    return "PROTECTING" if carry_per_session >= breakeven_carry else "PROTECTS, CARRY TOO HIGH"


# ════════════════════════════════════════════════════════════════════════════
# Printing helpers
# ════════════════════════════════════════════════════════════════════════════

def hdr(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def money(v) -> str:
    if v is None or v != v:
        return "n/a"
    return f"{'-' if v < 0 else '+'}${abs(v):,.0f}"


def print_episode_census(s: Series, all_eps: dict[str, list[Episode]]) -> None:
    hdr("EPISODES — SPY/VIX only, no book column read")
    print(f"  file {SPY_VIX_CSV.relative_to(ROOT)}: {s.dates[0]} .. {s.dates[-1]}, "
          f"{len(s.dates)} sessions with a SPY close")
    print(f"  {'#':>2} {'peak':<10} {'trough':<10} {'SPY':>7} {'max VIX':>7} "
          f"{'sess':>4} closed buffer_end")
    for k, e in enumerate(all_eps[PRIMARY], 1):
        print(f"  {k:>2} {e.peak:<10} {e.trough:<10} {e.spy_move:>+7.1%} "
              f"{(e.max_vix or float('nan')):>7.1f} {e.trough_i - e.peak_i + 1:>4} "
              f"{'yes' if e.closed else 'NO ':<6} {e.buffer_end or '-'}")
    for name in SECONDARY:
        print(f"  {name:<8} {len(all_eps[name])} episodes: "
              + ", ".join(f"{e.peak}..{e.trough}" for e in all_eps[name]))
    n_ep, n_sess, rate = observed_rate(s)
    print(f"  observed E-DD5 rate in the file: {n_ep} closed episodes over "
          f"{n_sess} sessions with dd defined = {rate:.2f} per 252 sessions")


def print_base_rate() -> float | None:
    """OD5: the long-history base rate, if the file has been fetched."""
    if not BASE_RATE_CSV.exists():
        print(f"  OD5 base rate: {BASE_RATE_CSV.relative_to(ROOT)} absent — run "
              f"with --fetch-base-rate (network). Only the file rate above is printed.")
        return None
    s = load_series(BASE_RATE_CSV)
    n_ep, n_sess, rate = observed_rate(s)
    print(f"  OD5 base rate (declared secondary, SPY {s.dates[0]}..{s.dates[-1]}): "
          f"{n_ep} closed E-DD5 episodes over {n_sess} sessions = {rate:.2f} per 252")
    return rate


def fetch_base_rate() -> int:
    """Write `BASE_RATE_CSV` from yfinance: SPY and ^VIX daily closes."""
    import yfinance as yf
    end = (date.today() + timedelta(days=1)).isoformat()
    spy = yf.download("SPY", start=BASE_RATE_START, end=end, auto_adjust=False,
                      progress=False)
    vix = yf.download("^VIX", start=BASE_RATE_START, end=end, auto_adjust=False,
                      progress=False)

    def closes(df):
        col = df["Close"]
        if hasattr(col, "columns"):
            col = col.iloc[:, 0]
        return {d.date().isoformat(): float(v) for d, v in col.items() if v == v}

    sc, vc = closes(spy), closes(vix)
    BASE_RATE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with BASE_RATE_CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "spy_close", "vix_close"])
        for d in sorted(sc):
            w.writerow([d, sc[d], vc.get(d, "")])
    print(f"wrote {BASE_RATE_CSV} ({len(sc)} SPY rows)")
    return 0


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fetch-base-rate", action="store_true",
                    help="OD5: fetch the long SPY/VIX history for the base rate, then exit")
    args = ap.parse_args(argv)
    if args.fetch_base_rate:
        return fetch_base_rate()

    from scripts.backtest_study.lib.book import load_book

    hdr("index_bear_hedge — do the book's index bear plays pay for themselves "
        "as crash insurance?")
    print(f"""  Registration {REGISTRATION}
  Accepted by default {ACCEPTED}; OD4 = forward only. The in-sample episodes are
  DESCRIPTION, never a verdict. Sunset {SUNSET}.
  NOTHING SHIPS FROM THIS STUDY, and no verdict removes the §4 bear sleeve.
  No annualised figure, Sharpe or time-to-recover is printed.""")

    # ── G-HASH ────────────────────────────────────────────────────────────
    bad = gate_hash()
    print(f"  G-HASH  episode definitions {episode_defs_hash()[:12]}  "
          f"GT3 {TC.table_hash()[:12]}  -> {'PASS' if not bad else 'FAIL'}")
    if bad:
        print("\nREFUSED — G-HASH: " + "; ".join(bad))
        return EXIT_GHASH

    # ── episodes (market data only) ───────────────────────────────────────
    s = load_series()
    all_eps = {name: episodes(s, name) for name in (PRIMARY, *SECONDARY)}
    print_episode_census(s, all_eps)
    long_rate = print_base_rate()

    # ── the book ──────────────────────────────────────────────────────────
    recs, diag = load_book(include_bs=False)
    recs, seal = _apply_seal(recs)
    era_name = diag.get("era")
    n_nodh = sum(1 for r in recs if r.get("days_held") is None)
    recs = [r for r in recs if r.get("days_held") is not None]
    book = deployed(recs)
    sleeve = [r for r in recs if is_index_bear(r)]
    stock = [r for r in recs if is_stock_bear(r)]
    w_sleeve, w_stock = unit_weights(sleeve), unit_weights(stock)

    hdr(f"POPULATION — era {era_name}"
        + (" (PRIMARY)" if era_name == "v4" else " (same-episode replication)"))
    print(f"  seal: withheld {seal['rows']} rows on {seal['dates']} signal dates "
          f"(load_book, no sealed_read; this study is not a sealed reader)")
    print(f"  book {len(recs)} rows on {len({r['date'] for r in recs})} signal dates, "
          f"{min(r['date'] for r in recs)} .. {max(r['date'] for r in recs)}; "
          f"{n_nodh} rows with no days_held left out")
    print(f"  sources {dict(Counter(r['source'] for r in recs))}; "
          f"fill_trusted False on {sum(1 for r in recs if not r.get('fill_trusted', True))} rows "
          f"(not filtered: the registration names no such filter)")
    print(f"  B  deployed book (top-{TOP_K}/day, A|B, minus index bears): {len(book)} positions "
          f"on {len({r['date'] for r in book})} dates")
    print(f"  S  index bears: {len(sleeve)} positions on {len({r['date'] for r in sleeve})} dates; "
          f"per-date counts {dict(sorted(Counter(Counter(r['date'] for r in sleeve).values()).items()))}")
    print(f"     structures {dict(Counter(r['structure'] for r in sleeve).most_common())}")
    print(f"     tickers {dict(Counter(r['ticker'] for r in sleeve).most_common())}")
    print(f"  H-stock single-stock bears: {len(stock)} positions on "
          f"{len({r['date'] for r in stock})} dates")

    # ── curves (built now; read after the census) ─────────────────────────
    sets = {
        "B": build_curves(book),
        "S": build_curves(sleeve, w_sleeve),
        "S-raw": build_curves(sleeve),
        "S-stock": build_curves(stock, w_stock),
    }
    book_real = [r for r in book if r["source"] == "real"]
    sleeve_real = [r for r in sleeve if r["source"] == "real"]
    sets["B-real"] = build_curves(book_real)
    sets["S-real"] = build_curves(sleeve_real, unit_weights(sleeve_real))
    axis = sorted(set().union(*(c.sessions() for c in sets.values())))
    labels = classify(axis, all_eps[PRIMARY], s)
    first_axis, last_axis = axis[0], axis[-1]
    in_span = [e for e in all_eps[PRIMARY]
               if date.fromisoformat(e.trough) >= first_axis
               and date.fromisoformat(e.peak) <= last_axis]
    insample = [e for e in in_span if e.peak <= ACCEPTED]
    forward = [e for e in all_eps[PRIMARY] if e.peak > ACCEPTED]

    # ── G-CENSUS ──────────────────────────────────────────────────────────
    hdr("G-CENSUS — per episode, descriptors only (no outcome column read yet)")
    census = episode_census(insample, axis, sleeve, book)
    print(f"  session axis {first_axis} .. {last_axis}, {len(axis)} sessions: "
          + ", ".join(f"{k} {v}" for k, v in sorted(Counter(labels).items())))
    print(f"  {'episode':<9} {'peak':<10} {'trough':<10} {'sess':>4} {'S entered':>9} "
          f"{'S open':>6} {'open@end':>8} {'B open':>6}  status")
    for c in census:
        e = c.episode
        print(f"  {e.label:<9} {e.peak:<10} {e.trough:<10} {c.n_sessions:>4} "
              f"{c.n_sleeve_entered:>9} {c.n_sleeve_open:>6} {c.open_share:>8.0%} "
              f"{c.n_book_open:>6}  {c.why}")
    out_entered = sum(1 for r in sleeve
                      if not any(entered_in(r, c.episode) for c in census))
    print(f"  index bears entered outside every window: {out_entered}")
    n_ev = sum(c.evaluable for c in census)
    print(f"  evaluable in-sample E-DD5 episodes: {n_ev} (registered floor {FLOOR})")
    print(f"  forward episodes (peak after {ACCEPTED}) in the SPY file: {len(forward)}")
    print("  G-CENSUS complete. Outcome columns are read from here on.")

    # ── G-MTM ─────────────────────────────────────────────────────────────
    hdr("G-MTM — marked exit vs stored realized_pnl_abs, shipped tolerance")
    failed = False
    for name, c in sets.items():
        ok = not c.mismatches
        failed |= not ok
        print(f"  {name:<8} {c.n_positions:>5} positions  {c.n_reconciled:>5} reconciled  "
              f"cost-netted {c.n_cost_netted:>4}  degraded {c.n_degraded}  "
              f"-> {'PASS' if ok else f'FAIL ({len(c.mismatches)})'}")
    if failed:
        worst = sorted((m for c in sets.values() for m in c.mismatches),
                       key=lambda m: -abs(m.diff or 0))[:10]
        for m in worst:
            print(f"    {m.date} {m.ticker} {m.structure} diff {m.diff}")
        print("\nREFUSED — G-MTM failed; the tolerance is never widened.")
        return EXIT_GMTM

    daily = {k: to_daily(on_axis(c, axis)) for k, c in sets.items()}
    ctx = Context(axis=axis, daily=daily, all_eps=all_eps, s=s, sleeve=sleeve,
                  book=book, sleeve_real=sleeve_real, book_real=book_real)
    ins = full_read(ctx, insample, span=None)
    describe(ctx, ins, era_name, long_rate)
    forward_read(ctx, forward, ins)
    return 0


# ════════════════════════════════════════════════════════════════════════════
# One complete read over a set of episodes (in-sample description or forward)
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Context:
    axis: list[date]
    daily: dict[str, list[float]]
    all_eps: dict[str, list[Episode]]
    s: Series
    sleeve: list[dict]
    book: list[dict]
    sleeve_real: list[dict]
    book_real: list[dict]


@dataclass
class FullRead:
    main: Reading
    p: float
    n_shifts: int
    t0: float
    secondary: dict[str, Reading]
    raw: Reading
    real: Reading
    stock: Reading
    loo: list[tuple[str, float, float, bool]]
    rb1: bool
    rb2: bool
    rb3: bool
    rb4: bool | None
    rb5: bool
    corr_outside: float

    @property
    def rb_hold(self) -> bool:
        """RB1-RB4 hold. RB4 not applicable counts as holding."""
        return self.rb1 and self.rb2 and self.rb3 and self.rb4 is not False


def _eps_in(ctx: Context, name: str, span: tuple[date, date] | None,
            forward: bool) -> list[Episode]:
    lo, hi = span if span else (ctx.axis[0], ctx.axis[-1])
    return [e for e in ctx.all_eps[name]
            if date.fromisoformat(e.trough) >= lo and date.fromisoformat(e.peak) <= hi
            and ((e.peak > ACCEPTED) if forward else (e.peak <= ACCEPTED))]


def full_read(ctx: Context, eps: list[Episode],
              span: tuple[date, date] | None) -> FullRead:
    """M1-M3, the permutation p, the secondary definitions and RB1-RB5."""
    axis, d = ctx.axis, ctx.daily
    forward = span is not None
    labels = classify(axis, ctx.all_eps[PRIMARY], ctx.s)
    census = episode_census(eps, axis, ctx.sleeve, ctx.book)
    main = read_arm(axis, d["B"], d["S"], census, labels, span)

    keep = [i for i, x in enumerate(axis) if span is None or span[0] <= x <= span[1]]
    sub = [axis[i] for i in keep]
    ev_eps = [r.episode for r in main.episodes if r.evaluable]
    p, n_shifts, t0 = permutation_p(sub, [d["B"][i] for i in keep],
                                    [d["S"][i] for i in keep], ev_eps)

    secondary = {}
    for name in SECONDARY:
        eps2 = _eps_in(ctx, name, span, forward)
        lab2 = classify(axis, ctx.all_eps[name], ctx.s)
        c2 = episode_census(eps2, axis, ctx.sleeve, ctx.book)
        secondary[name] = read_arm(axis, d["B"], d["S"], c2, lab2, span)

    sgn = sign(main.sum_delta)
    rb1 = all(sign(secondary[n].sum_delta) == sgn for n in ("E-DD8", "E-20D5"))
    loo, rb2 = [], True
    for r in main.episodes:
        if not r.evaluable:
            continue
        sd, net = main.sum_delta - r.delta, main.net - r.gain
        ok = sign(sd) == sgn and sign(net) == sign(main.net)
        rb2 &= ok
        loo.append((r.episode.label, sd, net, ok))
    raw = read_arm(axis, d["B"], d["S-raw"], census, labels, span)
    c_real = episode_census(eps, axis, ctx.sleeve_real, ctx.book_real)
    real = read_arm(axis, d["B-real"], d["S-real"], c_real, labels, span)
    stock = read_arm(axis, d["B"], d["S-stock"], census, labels, span)
    out_i = [i for i in keep if labels[i] == "outside"]
    corr = (statistics.correlation([d["S"][i] for i in out_i], [d["B"][i] for i in out_i])
            if len(out_i) > 2 else float("nan"))
    return FullRead(
        main=main, p=p, n_shifts=n_shifts, t0=t0, secondary=secondary, raw=raw,
        real=real, stock=stock, loo=loo, rb1=rb1, rb2=rb2,
        rb3=sign(raw.sum_delta) == sgn,
        rb4=None if real.n < 3 else sign(real.sum_delta) == sgn,
        rb5=stock.sum_delta >= main.sum_delta, corr_outside=corr)


def breakeven_carry(ins: FullRead, s: Series) -> float | None:
    """Carry per outside session at which the in-sample insurance breaks even
    at the file's observed episode rate. None when mean G_e is not positive."""
    mg = ins.main.mean_gain
    if not (mg == mg and mg > 0):
        return None
    _, _, rate = observed_rate(s)
    return -(rate / 252.0) * mg


# ════════════════════════════════════════════════════════════════════════════
# Printing the reads
# ════════════════════════════════════════════════════════════════════════════

def describe(ctx: Context, fr: FullRead, era_name, long_rate) -> None:
    """The in-sample DESCRIPTION. Prints figures and flags, never a verdict."""
    hdr(f"IN-SAMPLE DESCRIPTION — era {era_name}. NOT A VERDICT (OD4: forward only)")
    print("  These episodes may sit inside the analysing model's training data.\n"
          "  Every figure below describes them; none is graded.")
    m = fr.main
    print("\n  M1 — protection per episode, arm H (one unit per date) vs B, MTM dollars")
    print(f"  {'episode':<9} {'DD(B)':>10} {'DD(H)':>10} {'dDD':>9} {'G_e':>9}  status")
    for r in m.episodes:
        print(f"  {r.episode.label:<9} {money(r.dd_b):>10} {money(r.dd_h):>10} "
              f"{money(r.delta):>9} {money(r.gain):>9}  {r.why}")
    print(f"  sum dDD over {m.n} evaluable: {money(m.sum_delta)}; positive in "
          f"{m.n_positive} of {m.n}; median {money(m.median_delta)}")
    print(f"  permutation (circular shift, {fr.n_shifts} shifts of >= {MIN_SHIFT} "
          f"sessions): T {money(fr.t0)}, one-sided p {fr.p:.3f}")

    per100 = (m.carry / m.n_outside * 100) if m.n_outside else float("nan")
    print("\n  M2 — carry outside episodes")
    print(f"  C {money(m.carry)} over {m.n_outside} outside sessions = {money(per100)} "
          f"per 100; buffer {money(m.buffer)} over {m.n_buffer} sessions (neither side)")

    print("\n  M3 — net")
    print(f"  NET {money(m.net)} = windows {money(m.gains_all)} + C {money(m.carry)} "
          f"+ buffer {money(m.buffer)} + unclassified {money(m.unclassified)}")
    print(f"  full-span MTM maxDD B {money(m.mdd_b)}  H {money(m.mdd_h)}; worst session "
          f"B {money(m.worst_b)}  H {money(m.worst_h)}; unharmed "
          f"{'yes' if m.unharmed else 'no'}")
    _, _, rate = observed_rate(ctx.s)
    if m.f_star is None:
        print(f"  break-even f*: no break-even (mean G_e {money(m.mean_gain)} is not "
              f"positive)")
    else:
        print(f"  break-even f* {m.f_star:.2f} episodes per 252 sessions (mean G_e "
              f"{money(m.mean_gain)}); observed in the file {rate:.2f}"
              + (f"; OD5 long-history base rate {long_rate:.2f}"
                 if long_rate is not None else ""))

    from scripts.backtest_study.f4_deployment import account_sim as A
    capital = A.load_settings(A.DEFAULT_CONFIG).capital
    b, sl = ctx.daily["B"], ctx.daily["S"]
    lv_b, lv_h = _levels(b), _levels([x + y for x, y in zip(b, sl)])
    print(f"\n  Diagnostics (never graded): Ulcer B {M.ulcer_index(lv_b, capital):.2f}  "
          f"H {M.ulcer_index(lv_h, capital):.2f} (% of ${capital:,.0f}); "
          f"corr(S, B) outside episodes {fr.corr_outside:+.3f}")
    print("\n  Secondary definitions (sensitivity; M1-M3 on the same curves)")
    for name, r2 in fr.secondary.items():
        print(f"  {name:<8} evaluable {r2.n}/{len(r2.episodes)}  sum dDD "
              f"{money(r2.sum_delta)}  positive {r2.n_positive}/{r2.n}  C "
              f"{money(r2.carry)}  NET {money(r2.net)}")

    hdr("ROBUSTNESS BATTERY — veto flags, described only")
    print(f"  RB1 E-DD8 and E-20D5 keep the sign of sum dDD: {_flag(fr.rb1)} "
          f"({money(fr.secondary['E-DD8'].sum_delta)}, "
          f"{money(fr.secondary['E-20D5'].sum_delta)})")
    for label, sd, net, ok in fr.loo:
        print(f"  RB2 leave out {label}: sum dDD {money(sd)}  NET {money(net)}  {_flag(ok)}")
    print(f"  RB3 H-raw (recorded size): sum dDD {money(fr.raw.sum_delta)}  NET "
          f"{money(fr.raw.net)}  {_flag(fr.rb3)}")
    print(f"  RB4 real-priced rows only: evaluable {fr.real.n}, sum dDD "
          f"{money(fr.real.sum_delta)}  "
          + ("not applicable (< 3 evaluable)" if fr.rb4 is None else _flag(fr.rb4)))
    print(f"  RB5 H-stock (single-stock bears, one unit per date): sum dDD "
          f"{money(fr.stock.sum_delta)}  NET {money(fr.stock.net)}  "
          f"{'FIRES (stock bears protect at least as well)' if fr.rb5 else 'quiet'}")

    hdr("CRITERION VECTOR — in-sample, DESCRIPTION ONLY (no verdict under OD4)")
    print(f"  n evaluable {m.n} (floor {FLOOR}) · dDD > 0 in {m.n_positive} · "
          f"permutation p {fr.p:.3f} · NET {money(m.net)} · unharmed "
          f"{'yes' if m.unharmed else 'no'} · RB1 {_flag(fr.rb1)} RB2 {_flag(fr.rb2)} "
          f"RB3 {_flag(fr.rb3)} RB4 {_flag(fr.rb4)} RB5 {'fires' if fr.rb5 else 'quiet'}")


def _flag(v) -> str:
    return "n/a" if v is None else ("holds" if v else "FAILS")


def _levels(daily: list[float]) -> list[float]:
    out, acc = [], 0.0
    for v in daily:
        acc += v
        out.append(acc)
    return out


def forward_read(ctx: Context, forward: list[Episode], ins: FullRead,
                 today: str | None = None) -> tuple[str, str]:
    """The graded read: E-DD5 episodes whose peak is after ACCEPTED.

    Under the holdout seal it reads no outcome at all. Returns the two words
    (headline, early read) it printed.
    """
    today = today or date.today().isoformat()
    before_sunset = today < SUNSET
    closed = [e for e in forward if e.closed and e.buffer_end is not None]
    hdr("VERDICT — forward episodes only (OD4)")
    print(f"  forward E-DD5 episodes with peak after {ACCEPTED}: {len(forward)}; "
          f"buffer closed: {len(closed)}; SPY data to {ctx.s.dates[-1]}")
    if not seal_lifted() or not closed:
        why = ("the holdout seal holds: this registration is not a sealed reader, so "
               "its forward window waits for era.SEAL_LIFTED"
               if not seal_lifted() else "no forward episode has closed its buffer")
        head = "STILL-OPEN" if before_sunset else "UNDERPOWERED"
        print(f"  FORWARD VERDICT (headline, floor {FLOOR} episodes): {head} — "
              f"0 forward episodes graded; {why}")
        print(f"  FORWARD EARLY READ (declared secondary, floor {EARLY_FLOOR} episodes): "
              f"STILL-OPEN — 0 forward episodes graded")
        return head, "STILL-OPEN"

    span = (date.fromisoformat(ACCEPTED), ctx.axis[-1])
    fr = full_read(ctx, closed, span)
    m = fr.main
    deltas = [r.delta for r in m.episodes if r.evaluable]
    head = verdict(m.n, deltas, fr.p, m.net, m.unharmed, fr.rb_hold, fr.rb5,
                   before_sunset=before_sunset)
    per_sess = m.carry / m.n_outside if m.n_outside else float("nan")
    early = early_read(deltas, per_sess, breakeven_carry(ins, ctx.s))
    for r in m.episodes:
        print(f"  {r.episode.label:<9} dDD {money(r.delta):>9}  G_e {money(r.gain):>9}  "
              f"{r.why}")
    print(f"  criterion vector: n {m.n} · dDD > 0 in {m.n_positive} · p {fr.p:.3f} · "
          f"NET {money(m.net)} · unharmed {'yes' if m.unharmed else 'no'} · "
          f"RB1-RB4 {'hold' if fr.rb_hold else 'FAIL'} · RB5 "
          f"{'fires' if fr.rb5 else 'quiet'}")
    print(f"  FORWARD VERDICT (headline, floor {FLOOR} episodes): {head}")
    print(f"  FORWARD EARLY READ (declared secondary, floor {EARLY_FLOOR} episodes): {early}")
    return head, early


if __name__ == "__main__":
    sys.exit(main())
