"""tail_rebound — after a SPY tail fall, does SPY's next-h-session total return beat its usual h-session return?

REGISTERED 2026-11-15, accepted by default the same day:
research/pre-registrations/f1_selection/regime/tail_rebound.md. Every constant,
floor, seed and verdict word below is that file's. Read it before changing
anything here. It reads `tail_breach_intraday`'s yfinance cache through that
module's own readers and imports its event A unchanged.

WHAT IT ASKS
------------
Event A on session s: `tail_breach_intraday`'s intraday 2-sigma breach,
ln(L_s / A_{s-1}) < -k x VIX(s-1)/100/sqrt(252), k = 2 (1.5 and 2.5 printed).
Event B on session s: a 5% fall completed, L_s <= 0.95 x max(A_{s-5..s-1}),
the session on which `tail_breach_intraday`'s B is realized. L is the
total-return low, A the adjusted close. Both are known by s's close.

Triggers within 5 sessions of each other chain into one episode; the entry is
the first trigger of each episode, at its close. The outcome is
R_h = ln(A_{s+h} / A_s). The excess is the mean R_h over entries minus the mean
R_h over every eligible session in the same sample (trigger defined, R_h
defined). Its CI resamples clusters (entries fewer than h sessions apart)
with replacement, 10,000 draws; the unconditional mean is held fixed.

A21 and B21 are co-primaries, Holm m = 2; A5, A63, B5, B63 are secondaries,
Holm m = 4. Verdicts REBOUND / CONTINUATION / NO-EDGE / UNDERPOWERED (floor 10
clusters per arm). Sample: every SPY session from 1993-01-29 whose window ends
on or before the registration date. Forward entries print STILL-OPEN until 10
clusters.

The holdout seal does not apply: no flow signal, play or backtest row is read.
This study never fetches; refresh the cache with tail_breach_intraday.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run tail_rebound
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection.benchmark.ticker_class import holm  # noqa: E402
from scripts.backtest_study.f1_selection.regime import tail_breach as T  # noqa: E402
from scripts.backtest_study.f1_selection.regime import tail_breach_intraday as TI  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/tail_rebound.md"
# The registration date. Sample: window s..s+h on or before it. Forward: entry
# after it. None would mean an unaccepted draft (no forward window).
REGISTERED: str | None = "2026-11-15"

# --- constants fixed by the registration -------------------------------------
K = TI.K                    # event A: 2 x the VIX-implied 1-day move
K_PARAMS = TI.K_PARAMS      # 1.5 and 2.5, printed only
MOVE = 0.05                 # event B: a 5% fall
LOOKBACK = 5                # event B: from the highest of the 5 prior closes
EPISODE_GAP = 5             # triggers within 5 sessions chain into one episode
H_PRIMARY = 21
H_SECONDARY = (5, 63)
BOOT_N, SEED = 10_000, 20261115
ALPHA = 0.05
MIN_CLUSTERS = 10           # GN, per arm
MAX_CLUSTER_SHARE = 1 / 3   # GN: the largest cluster holds at most this share of entries
FWD_MIN_CLUSTERS = 10       # FORWARD, per arm
UNCOND_BLOCK = 63           # printed half-width of the unconditional mean
FIRST_SESSION = "1993-01-29"
SUB_START = "2024-01-02"    # the 2024+ subperiod, printed only
DECADES = (("1993-1999", "1993-01-01", "2000-01-01"), ("2000s", "2000-01-01", "2010-01-01"),
           ("2010s", "2010-01-01", "2020-01-01"), ("2020-2026", "2020-01-01", "2027-01-01"))
TRADING_DAYS = 252

REBOUND, CONTINUATION, NO_EDGE = "REBOUND", "CONTINUATION", "NO-EDGE"
UNDERPOWERED, STILL_OPEN = T.UNDERPOWERED, T.STILL_OPEN

EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
Refused = T.Refused

CACHE_DIR = TI.CACHE_DIR
BASE_RATE_CSV = T.BASE_RATE_CSV
BARCHART_SPY = TI.BARCHART_SPY


# ════════════════════════════════════════════════════════════════════════════
# Triggers. Each returns a float array: 1.0, 0.0, or NaN (undefined).
# ════════════════════════════════════════════════════════════════════════════

def intraday_breach(cal: TI.ICal, k: float = K) -> np.ndarray:
    """Event A: `tail_breach_intraday.intraday_down`, unchanged."""
    return TI.intraday_down(cal, k)


def completed_fall(cal: TI.ICal, move: float = MOVE, back: int = LOOKBACK) -> np.ndarray:
    """Event B on session s: L_s <= (1 - move) x max(A_{s-back}..A_{s-1}).
    Reads only session s's low and closes before s."""
    lo = cal.low("adj")
    out = np.full(cal.n, np.nan)
    for s in range(back, cal.n):
        prior = cal.adj[s - back:s]
        if not (math.isfinite(lo[s]) and np.all(np.isfinite(prior))):
            continue
        out[s] = 1.0 if lo[s] <= (1.0 - move) * float(np.max(prior)) else 0.0
    return out


# ════════════════════════════════════════════════════════════════════════════
# Episodes, entries, clusters
# ════════════════════════════════════════════════════════════════════════════

def chain(idx, gap: int) -> list[list[int]]:
    """Runs of sorted indices in which each is within `gap` of the one before."""
    runs: list[list[int]] = []
    for i in sorted(idx):
        if runs and i - runs[-1][-1] <= gap:
            runs[-1].append(i)
        else:
            runs.append([i])
    return runs


def trigger_sessions(trig: np.ndarray) -> list[int]:
    return [i for i in range(len(trig)) if trig[i] == 1.0]


def first_entries(trig: np.ndarray, gap: int = EPISODE_GAP) -> list[int]:
    """The first trigger of each episode, chained over the whole series."""
    return [run[0] for run in chain(trigger_sessions(trig), gap)]


def clusters(entries, h: int) -> list[list[int]]:
    """An entry fewer than h sessions after the one before joins its cluster
    (their outcome windows overlap); otherwise it starts a new one."""
    return chain(entries, h - 1)


# ════════════════════════════════════════════════════════════════════════════
# Outcomes. Each returns a session-indexed float array, NaN where undefined.
# ════════════════════════════════════════════════════════════════════════════

def log_return(cal: TI.ICal, h: int) -> np.ndarray:
    """R_h(s) = ln(A_{s+h} / A_s)."""
    out = np.full(cal.n, np.nan)
    if cal.n > h:
        with np.errstate(invalid="ignore", divide="ignore"):
            out[:cal.n - h] = np.log(cal.adj[h:] / cal.adj[:cal.n - h])
    return out


def open_return(cal: TI.ICal, opens_raw: np.ndarray, h: int) -> np.ndarray:
    """ln(A_{s+h} / O_{s+1}), the total-return open of the next session."""
    o = opens_raw * cal.factor
    out = np.full(cal.n, np.nan)
    if cal.n > h:
        with np.errstate(invalid="ignore", divide="ignore"):
            out[:cal.n - h] = np.log(cal.adj[h:] / o[1:cal.n - h + 1])
    return out


def excursions(cal: TI.ICal, h: int) -> tuple[np.ndarray, np.ndarray]:
    """(MAE, MFE): ln(min L / A_s) and ln(max H / A_s) over sessions s+1..s+h."""
    mae, mfe = np.full(cal.n, np.nan), np.full(cal.n, np.nan)
    if cal.n <= h:
        return mae, mfe
    lo, hi = cal.low("adj"), cal.high("adj")
    wl = np.lib.stride_tricks.sliding_window_view(lo[1:], h)[:cal.n - h]
    wh = np.lib.stride_tricks.sliding_window_view(hi[1:], h)[:cal.n - h]
    with np.errstate(invalid="ignore", divide="ignore"):
        mae[:cal.n - h] = np.log(wl.min(axis=1) / cal.adj[:cal.n - h])
        mfe[:cal.n - h] = np.log(wh.max(axis=1) / cal.adj[:cal.n - h])
    return mae, mfe


def vix_scaled(cal: TI.ICal, r: np.ndarray, h: int) -> np.ndarray:
    """R_h in units of VIX_s's implied h-session move."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return r / (cal.vix / 100.0 * math.sqrt(h / TRADING_DAYS))


# ════════════════════════════════════════════════════════════════════════════
# Windows
# ════════════════════════════════════════════════════════════════════════════

def window_of(cal: TI.ICal, s: int, h: int, registered: str | None) -> str:
    """'sample', 'forward', 'gap' (entry on or before the registration date,
    window ending after it) or 'open' (window past the data)."""
    if registered is not None and cal.dates[s] > registered:
        return "forward" if s + h < cal.n else "open"
    if s + h >= cal.n:
        return "open"
    if registered is not None and cal.dates[s + h] > registered:
        return "gap"
    return "sample"


def pool_mask(cal: TI.ICal, trig: np.ndarray, vals: np.ndarray, h: int,
              registered: str | None, part: str = "sample",
              lo: str | None = None, hi: str | None = None) -> np.ndarray:
    """Eligible sessions of `part`: trigger defined, value defined, optionally
    with lo <= date < hi."""
    m = np.isfinite(trig) & np.isfinite(vals)
    for s in np.flatnonzero(m):
        d = cal.dates[s]
        if window_of(cal, s, h, registered) != part or (lo and d < lo) or (hi and d >= hi):
            m[s] = False
    return m


# ════════════════════════════════════════════════════════════════════════════
# Statistic and bootstrap
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Result:
    n_entries: int
    n_clusters: int
    mean_entry: float
    uncond: float
    excess: float
    lo: float
    hi: float
    p: float
    largest: int = 0            # entries in the largest cluster

    @property
    def largest_share(self) -> float:
        return self.largest / self.n_entries if self.n_entries else float("nan")

    @property
    def powered(self) -> bool:
        """GN: at least 10 clusters, the largest holding at most a third of entries."""
        return self.n_clusters >= MIN_CLUSTERS and self.largest_share <= MAX_CLUSTER_SHARE + 1e-12

    @property
    def finite(self) -> bool:
        return math.isfinite(self.lo) and math.isfinite(self.hi)


def excess_ci(vals: np.ndarray, entries: list[int], pool: np.ndarray, h: int,
              draws: int = BOOT_N, seed: int = SEED) -> Result:
    """Mean over entries minus the pool mean (held fixed); clusters resampled."""
    uncond = float(np.mean(vals[pool])) if pool.any() else float("nan")
    ents = [e for e in entries if math.isfinite(vals[e])]
    cls = clusters(ents, h)
    nan = float("nan")
    if not ents:
        return Result(0, 0, nan, uncond, nan, nan, nan, 1.0)
    mean_e = float(np.mean(vals[ents]))
    sums = np.array([float(np.sum(vals[c])) for c in cls])
    cnts = np.array([len(c) for c in cls], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(cls), size=(draws, len(cls)))
    d = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1) - uncond
    lo, hi = (float(x) for x in np.percentile(d, [2.5, 97.5]))
    p = min(1.0, 2.0 * min(float(np.mean(d <= 0)), float(np.mean(d >= 0))))
    return Result(len(ents), len(cls), mean_e, uncond, mean_e - uncond, lo, hi, p,
                  max(len(c) for c in cls))


def uncond_halfwidth(vals: np.ndarray, pool: np.ndarray, L: int = UNCOND_BLOCK) -> float:
    """95% half-width of the pool mean from a moving-block bootstrap."""
    x = vals[pool]
    if len(x) < 2:
        return float("nan")
    idx = T.block_indices(len(x), min(L, len(x)), BOOT_N, SEED)
    m = x[idx].mean(axis=1)
    lo, hi = np.percentile(m, [2.5, 97.5])
    return float((hi - lo) / 2)


def word(res: Result, powered: bool, p_adj: float | None = None) -> str:
    if not powered or not res.finite:
        return UNDERPOWERED
    ok = p_adj is None or p_adj < ALPHA
    if res.lo > 0 and ok:
        return REBOUND
    if res.hi < 0 and ok:
        return CONTINUATION
    return NO_EDGE


def forward_word(res: Result | None, powered: bool) -> str:
    if res is None or not powered:
        return STILL_OPEN
    w = word(res, True)
    return STILL_OPEN if w == UNDERPOWERED else w


def family_p(res: dict, powered: dict) -> dict:
    """Holm-adjusted p; a gated arm stays in its family with p = 1."""
    adj = holm({k: (r.p if powered[k] else 1.0) for k, r in res.items()})
    return {k: adj[k][0] for k in res}


# ════════════════════════════════════════════════════════════════════════════
# Arms
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Arm:
    key: str
    trig: np.ndarray
    h: int
    entries: list[int]          # every first-of-episode entry, whole series
    r: np.ndarray
    pool: np.ndarray
    sample: list[int]
    census: dict
    res: Result

    @property
    def powered(self) -> bool:
        return self.res.powered


def build_arm(key: str, cal: TI.ICal, trig: np.ndarray, h: int, registered: str | None,
              entries: list[int] | None = None) -> Arm:
    r = log_return(cal, h)
    ents = first_entries(trig) if entries is None else entries
    census = {"sample": 0, "forward": 0, "gap": 0, "open": 0}
    for e in ents:
        census[window_of(cal, e, h, registered)] += 1
    sample = [e for e in ents if window_of(cal, e, h, registered) == "sample"]
    pool = pool_mask(cal, trig, r, h, registered)
    return Arm(key, trig, h, ents, r, pool, sample, census, excess_ci(r, sample, pool, h))


def sub_result(cal: TI.ICal, arm: Arm, vals: np.ndarray, lo: str | None = None,
               hi: str | None = None, entries: list[int] | None = None,
               registered: str | None = None, part: str = "sample") -> Result:
    """Any value array on an arm's own entries and pool, optionally a date slice."""
    ents = arm.sample if entries is None else entries
    ents = [e for e in ents if (not lo or cal.dates[e] >= lo) and (not hi or cal.dates[e] < hi)]
    pool = pool_mask(cal, arm.trig, vals, arm.h, registered, part, lo, hi)
    return excess_ci(vals, ents, pool, arm.h)


# ════════════════════════════════════════════════════════════════════════════
# Gates and inputs
# ════════════════════════════════════════════════════════════════════════════

def check_era() -> None:
    requested = era_mod.requested_era()
    if requested != era_mod.CURRENT:
        raise Refused(era_mod.EXIT_THIN_ERA,
                      f"tail_rebound reads yfinance market data, which carries no era; "
                      f"era {requested!r} does not apply — run it without --era. Exit 2.")


def load_inputs() -> tuple[list, dict]:
    paths = {n: CACHE_DIR / f"{n}.csv" for n in ("SPY", "VIX")}
    for n, p in paths.items():
        if not p.exists():
            raise Refused(EXIT_INPUT, f"GE: {p.relative_to(ROOT)} is missing; run "
                          f"`python -m scripts.backtest_study run tail_breach_intraday -- --refresh`. Exit 3.")
    spy = TI.read_ohlc(paths["SPY"])
    vix = {r[0]: r[4] for r in TI.read_ohlc(paths["VIX"])}
    if not spy or not vix:
        raise Refused(EXIT_INPUT, "GE: an input series is empty. Exit 3.")
    return spy, vix


def opens_for(cal: TI.ICal, spy: list[tuple]) -> np.ndarray:
    o = {r[0]: r[1] for r in spy}
    return np.array([o.get(d) if o.get(d) is not None else np.nan for d in cal.dates], dtype=float)


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

section, pct = T.section, T.pct


def ci_txt(r: Result) -> str:
    if r.n_entries == 0:
        return "no entries"
    return (f"excess {pct(r.excess)} [{pct(r.lo)}, {pct(r.hi)}]  entries {pct(r.mean_entry)} vs "
            f"uncond {pct(r.uncond)}; {r.n_entries} entries, {r.n_clusters} clusters, p {r.p:.4f}")


def run() -> int:
    check_era()
    spy, vix = load_inputs()
    cal = TI.build_icals(spy, vix, {})
    reg = REGISTERED

    print("tail_rebound — after a SPY tail fall, does SPY's total return over the next h sessions "
          "beat its unconditional h-session return?")
    print(f"registration: {REGISTRATION} ({'registered ' + reg if reg else 'DRAFT, not registered'})")
    print("era: current (inputs are unversioned market data)")
    print(f"population: SPY sessions {cal.dates[0]} -> {cal.dates[-1]} ({cal.n}); "
          f"sample windows end on or before {reg or 'the last session'}")
    dirty = "dirty" if T._git("status", "--porcelain") else "clean"
    print(f"git: {T._git('rev-parse', '--short', 'HEAD')} "
          f"({T._git('rev-parse', '--abbrev-ref', 'HEAD')}, working tree {dirty})")
    print("inputs read:")
    for p in (CACHE_DIR / "SPY.csv", CACHE_DIR / "VIX.csv", BASE_RATE_CSV, BARCHART_SPY):
        if p.exists():
            print(T._inventory(p))
    print("SEAL: not applied — no flow signal, play or backtest row is read")
    print(f"A: k={K} intraday breach; B: low <= {1 - MOVE:.2f} x max of the {LOOKBACK} prior closes; "
          f"episodes chain within {EPISODE_GAP}; entry = first trigger, at its close; "
          f"{BOOT_N} cluster draws, seed {SEED}")

    # ── gates ───────────────────────────────────────────────────────────────
    ca = [(r[0], r[4], r[5]) for r in spy]
    probs = T.ratio_problems(ca)
    bprobs, n_common = T.base_rate_problems(ca, vix, BASE_RATE_CSV)
    oprobs = TI.ohlc_problems(spy, start=FIRST_SESSION)
    cprobs, n_cross = TI.cross_feed_problems(spy)
    section("GATES — inputs and basis")
    print(f"  GE: SPY {len(spy)} rows, VIX {len(vix)} — pass")
    print(f"  GB ratio: {len(probs)} close/adj steps outside the dividend pattern")
    print(f"  GB base-rate: {n_common} common SPY dates, {len(bprobs)} disagreements over 0.5%"
          + ("" if BASE_RATE_CSV.exists() else " (file missing: skipped)"))
    print(f"  GO: {len(oprobs)} sessions since {FIRST_SESSION} with a missing or out-of-order high/low")
    print(f"  GC: {n_cross} sessions in the Barchart cache, {len(cprobs)} lows off by over "
          f"{TI.CROSS_TOL:.1%}" + ("" if BARCHART_SPY.exists() else " (file missing: skipped)"))
    bad = probs + bprobs + oprobs + cprobs
    if bad:
        for line in bad[:10]:
            print(f"    {line}")
        raise Refused(EXIT_INPUT, "GB/GO/GC: the price basis check failed. Exit 3.")

    # ── triggers and episodes ───────────────────────────────────────────────
    ta, tb = intraday_breach(cal), completed_fall(cal)
    section("TRIGGERS AND EPISODES (whole series)")
    for lab, t in (("A", ta), ("B", tb)):
        ts = trigger_sessions(t)
        ep = first_entries(t)
        print(f"  {lab}: {int(np.isfinite(t).sum())} sessions defined, {len(ts)} trigger sessions, "
              f"{len(ep)} episodes; first {cal.dates[ep[0]] if ep else '—'}, "
              f"last {cal.dates[ep[-1]] if ep else '—'}")

    # ── graded arms ─────────────────────────────────────────────────────────
    arms = {}
    for ev, t in (("A", ta), ("B", tb)):
        for h in (H_PRIMARY, *H_SECONDARY):
            arms[f"{ev}{h}"] = build_arm(f"{ev}{h}", cal, t, h, reg)
    prim = {k: arms[k] for k in ("A21", "B21")}
    secs = {k: arms[k] for k in ("A5", "A63", "B5", "B63")}
    p_prim = family_p({k: a.res for k, a in prim.items()}, {k: a.powered for k, a in prim.items()})
    p_sec = family_p({k: a.res for k, a in secs.items()}, {k: a.powered for k, a in secs.items()})
    words = {k: word(a.res, a.powered, p_prim[k]) for k, a in prim.items()}
    words.update({k: word(a.res, a.powered, p_sec[k]) for k, a in secs.items()})
    plain = {k: word(a.res, a.powered) for k, a in arms.items()}
    holm_p = {**p_prim, **p_sec}

    section("GRADED — sample, first trigger of each episode, entry at the close")
    print("  excess = mean R_h over entries - mean R_h over every eligible session (log total return)")
    for k, a in arms.items():
        fam = "m=2" if k in prim else "m=4"
        hw = uncond_halfwidth(a.r, a.pool)
        print(f"  {k:<4} h={a.h:<2} {ci_txt(a.res)}")
        print(f"       pool {int(a.pool.sum())} sessions, uncond half-width ±{pct(hw)}; "
              f"census {a.census}; GN {a.res.n_clusters} clusters (floor {MIN_CLUSTERS}), largest "
              f"{a.res.largest} entries ({pct(a.res.largest_share)}, cap 33.33%) "
              f"{'pass' if a.powered else 'FAIL'}; Holm({fam}) {holm_p[k]:.4f} "
              f"-> {words[k]} (unadjusted: {plain[k]})")

    # ── printed only ────────────────────────────────────────────────────────
    opens = opens_for(cal, spy)
    section("PRINTED ONLY — EVERY trigger session as an entry")
    for k, a in arms.items():
        every = [e for e in trigger_sessions(a.trig) if window_of(cal, e, a.h, reg) == "sample"]
        print(f"  {k:<4} {ci_txt(excess_ci(a.r, every, a.pool, a.h))}")

    section("PRINTED ONLY — K-PARAM (event A at k = 1.5 and 2.5)")
    for kk in K_PARAMS:
        t = intraday_breach(cal, kk)
        for h in (H_PRIMARY, *H_SECONDARY):
            print(f"  A k={kk} h={h:<2} {ci_txt(build_arm('A', cal, t, h, reg).res)}")

    section("PRINTED ONLY — OPEN (entry at the next session's open)")
    for k, a in arms.items():
        print(f"  {k:<4} {ci_txt(sub_result(cal, a, open_return(cal, opens, a.h), registered=reg))}")

    section("PRINTED ONLY — HIT (share with R_h > 0)")
    for k, a in arms.items():
        hit = np.where(np.isfinite(a.r), (a.r > 0).astype(float), np.nan)
        r = sub_result(cal, a, hit, registered=reg)
        print(f"  {k:<4} entries {pct(r.mean_entry)} vs uncond {pct(r.uncond)}; "
              f"difference {pct(r.excess)} [{pct(r.lo)}, {pct(r.hi)}]")

    section("PRINTED ONLY — MAE and MFE over sessions s+1..s+h (log, total return)")
    for k, a in arms.items():
        mae, mfe = excursions(cal, a.h)
        for lab, v in (("MAE", mae), ("MFE", mfe)):
            r = sub_result(cal, a, v, registered=reg)
            pool = pool_mask(cal, a.trig, v, a.h, reg)
            med_e = float(np.median(v[a.sample])) if a.sample else float("nan")
            med_u = float(np.median(v[pool])) if pool.any() else float("nan")
            print(f"  {k:<4} {lab} mean {pct(r.mean_entry)} vs {pct(r.uncond)} "
                  f"(diff {pct(r.excess)} [{pct(r.lo)}, {pct(r.hi)}]); median {pct(med_e)} vs {pct(med_u)}")

    section("PRINTED ONLY — VIX-SCALED (R_h / VIX_s-implied h-session move)")
    for k, a in arms.items():
        r = sub_result(cal, a, vix_scaled(cal, a.r, a.h), registered=reg)
        print(f"  {k:<4} entries {r.mean_entry:+.3f} vs uncond {r.uncond:+.3f}; "
              f"excess {r.excess:+.3f} [{r.lo:+.3f}, {r.hi:+.3f}] sigma units")

    section("PRINTED ONLY — DECADE and 2024+ (each against its own unconditional mean)")
    for k, a in arms.items():
        for lab, lo, hi in (*DECADES, ("2024+", SUB_START, None)):
            print(f"  {k:<4} {lab:<10} {ci_txt(sub_result(cal, a, a.r, lo, hi, registered=reg))}")

    # ── forward ─────────────────────────────────────────────────────────────
    section("FORWARD — entries after the registration date")
    fwd = {"A21": STILL_OPEN, "B21": STILL_OPEN}
    if reg is None:
        print("  registration not accepted: no forward window. forward: STILL-OPEN")
    else:
        for k in fwd:
            a = arms[k]
            ents = [e for e in a.entries if window_of(cal, e, a.h, reg) == "forward"]
            pool = pool_mask(cal, a.trig, a.r, a.h, reg, "forward")
            res = excess_ci(a.r, ents, pool, a.h)
            pw = res.n_clusters >= FWD_MIN_CLUSTERS and res.powered
            fwd[k] = forward_word(res if pw else None, pw)
            print(f"  {k}: forward entries {res.n_entries}, clusters {res.n_clusters} "
                  f"(floor {FWD_MIN_CLUSTERS}), largest {res.largest}; open {a.census['open']}, "
                  f"gap {a.census['gap']} -> {fwd[k]}")

    section("VERDICT")
    print(f"  sample {cal.dates[0]} -> {reg or cal.dates[-1]}; {BOOT_N} cluster draws, seed {SEED}")
    print()
    print(f"  >>> tail_rebound A21 (SPY 21-session total return after an intraday 2x-VIX breach, first "
          f"of each episode, vs unconditional, 1993 on): {words['A21']} <<<")
    print(f"  >>> tail_rebound B21 (SPY 21-session total return after a completed 5% fall, first of "
          f"each episode, vs unconditional, 1993 on): {words['B21']} <<<")
    print(f"  >>> tail_rebound SECONDARY (h = 5 and 63, Holm m=4): "
          + " ".join(f"{k} {words[k]}" for k in secs) + " <<<")
    print(f"  >>> tail_rebound FORWARD (entries after the registration date): "
          f"A21 {fwd['A21']} B21 {fwd['B21']} <<<")
    print()
    print("  REBOUND needs the 95% cluster-bootstrap CI on the excess wholly above 0 and a Holm p")
    print("  below 0.05 (A21/B21 m=2; secondaries m=4); CONTINUATION the mirror. It prices no option.")
    print("  Nothing ships from this study (tail_rebound.md).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)
    try:
        return run()
    except Refused as exc:
        print(f"REFUSED — {exc.message}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
