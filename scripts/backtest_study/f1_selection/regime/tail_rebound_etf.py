"""tail_rebound_etf — after a QQQ or SMH tail fall, does the ETF's next-h-session total return beat its usual one?

REGISTERED 2026-11-15, accepted by default the same day:
research/pre-registrations/f1_selection/regime/tail_rebound_etf.md.
Every constant, floor, seed and verdict word below is that file's. Read it
before changing anything here. It asks `tail_rebound`'s question on QQQ and
SMH and imports `tail_rebound` (and through it `tail_breach_intraday` and
`tail_breach`) unchanged; nothing is copied.

WHAT IT ASKS
------------
Event A on session s: ln(L_s / A_{s-1}) < -k x sigma_s, k = 2, with
sigma_s = VXN(s-1)/100/sqrt(252) for both ETFs (VIX and the ETF's own
20-session realized vol printed only). Event B on session s:
L_s <= 0.95 x max(A_{s-5..s-1}) (7.5% and 10% printed only). L is the
total-return low, A the adjusted close.

Episodes, entries, the excess, clusters and the bootstrap are tail_rebound's.
QQQ-A21, QQQ-B21, SMH-A21, SMH-B21 are co-primaries, Holm m = 4; the eight
h = 5 and 63 arms are secondaries, Holm m = 8. Verdicts REBOUND /
CONTINUATION / NO-EDGE / UNDERPOWERED (floor 10 clusters per arm, largest
cluster at most a third of entries). Forward entries print STILL-OPEN until
the floor.

Inputs: yfinance OHLC for QQQ, SMH and ^VXN in backtests/tail_rebound_etf/
(fetched by --refresh only), and tail_breach_intraday's SPY and VIX cache.
The holdout seal does not apply: no flow signal, play or backtest row is read.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run tail_rebound_etf
    python -m scripts.backtest_study.f1_selection.regime.tail_rebound_etf --refresh
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection.regime import tail_breach as T  # noqa: E402
from scripts.backtest_study.f1_selection.regime import tail_breach_intraday as TI  # noqa: E402
from scripts.backtest_study.f1_selection.regime import tail_rebound as R  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/tail_rebound_etf.md"
# The registration date. Sample: window s..s+h on or before it. Forward: entry
# after it. None would mean an unaccepted draft (no forward window).
REGISTERED: str | None = "2026-11-15"

# --- constants fixed by the registration -------------------------------------
ETFS = ("QQQ", "SMH")
SERIES = {"QQQ": ("QQQ", "1999-03-10"), "SMH": ("SMH", "1995-01-01"), "VXN": ("^VXN", "2000-01-01")}
K = R.K                      # 2
K_PARAMS = R.K_PARAMS        # 1.5, 2.5 printed only
MOVE = R.MOVE                # 5%
MOVE_PARAMS = (0.075, 0.10)  # printed only
H_PRIMARY = R.H_PRIMARY      # 21
H_SECONDARY = R.H_SECONDARY  # 5, 63
RV_WINDOW = 20               # RV20: 20 daily log total returns ending at s-1
RELAUNCH = "2011-12-20"      # SMH: VanEck takes the ticker from the Merrill HOLDRS
GB_STEP_MAX = 0.03           # GB: largest single step down in close/adj (annual dividends)
GB_UP_TOL = T.RATIO_UP_TOL   # GB: close/adj may only fall
GB_RAW_STEP = 0.25           # GB: a raw close moving more than this in a day is an unadjusted split
SUB_START = R.SUB_START
DECADES = (("1999-2009", "1999-01-01", "2010-01-01"), ("2010s", "2010-01-01", "2020-01-01"),
           ("2020-2026", "2020-01-01", "2027-01-01"))
BOOT_N, SEED = R.BOOT_N, R.SEED
MIN_CLUSTERS, FWD_MIN_CLUSTERS = R.MIN_CLUSTERS, R.FWD_MIN_CLUSTERS
TRADING_DAYS = R.TRADING_DAYS

REBOUND, CONTINUATION, NO_EDGE = R.REBOUND, R.CONTINUATION, R.NO_EDGE
UNDERPOWERED, STILL_OPEN = R.UNDERPOWERED, R.STILL_OPEN
PRIMARY_KEYS = tuple(f"{e}-{ev}{H_PRIMARY}" for e in ETFS for ev in ("A", "B"))
SECONDARY_KEYS = tuple(f"{e}-{ev}{h}" for e in ETFS for ev in ("A", "B") for h in H_SECONDARY)

EXIT_INPUT = era_mod.EXIT_ERA_MISMATCH
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
Refused = T.Refused

CACHE_DIR = ROOT / "backtests" / "tail_rebound_etf"
SPY_CACHE = TI.CACHE_DIR
BARCHART_DIR = ROOT / "backtests" / "underlying_ohlc_cache"


# ════════════════════════════════════════════════════════════════════════════
# Data
# ════════════════════════════════════════════════════════════════════════════

def cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.csv"


def fetch(name: str, end: str | None = None) -> Path:
    """yfinance (auto_adjust=False) -> backtests/tail_rebound_etf/<name>.csv; `end` exclusive."""
    import pandas as pd
    import yfinance as yf
    sym, start = SERIES[name]
    df = yf.download(sym, start=start, end=end or date.today().isoformat(),
                     auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise Refused(EXIT_INPUT, f"GE: yfinance returned no rows for {sym}. Exit 3.")

    def col(c):
        x = df[c]
        return x.iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else x

    cols = [col(c) for c in ("Open", "High", "Low", "Close", "Adj Close")]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(name)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "open", "high", "low", "close", "adj_close"])
        for i, d in enumerate(cols[3].index):
            vals = [float(c.values[i]) for c in cols]
            if vals[3] != vals[3]:
                continue
            w.writerow([pd.Timestamp(d).strftime("%Y-%m-%d"),
                        *[repr(v) if v == v else "" for v in vals]])
    print(f"fetched {sym} -> {path.relative_to(ROOT)} ({len(cols[3])} rows)")
    return path


def load_inputs(refresh: bool = False) -> tuple[dict, dict, dict, list]:
    """(ETF rows by name, VXN closes, VIX closes, SPY rows)."""
    for name in SERIES:
        if refresh or not cache_path(name).exists():
            if not refresh:
                raise Refused(EXIT_INPUT, f"GE: backtests/tail_rebound_etf/{name}.csv is missing; run "
                              f"`python -m scripts.backtest_study.f1_selection.regime.tail_rebound_etf "
                              f"--refresh`. Exit 3.")
            try:
                fetch(name)
            except Refused:
                raise
            except Exception as exc:  # network, yfinance schema
                raise Refused(EXIT_INPUT, f"GE: fetching {SERIES[name][0]} failed ({exc}). Exit 3.")
    rows = {e: TI.read_ohlc(cache_path(e)) for e in ETFS}
    vxn = {r[0]: r[4] for r in TI.read_ohlc(cache_path("VXN"))}
    spy, vix = R.load_inputs()          # GE for the SPY side, refuses with its own message
    if not all(rows.values()) or not vxn:
        raise Refused(EXIT_INPUT, "GE: an input series is empty. Exit 3.")
    return rows, vxn, vix, spy


# ════════════════════════════════════════════════════════════════════════════
# Volatility sources. Each calendar carries its sigma source in the VIX slot,
# in index points, so tail_breach.implied_sigma and intraday_down read it unchanged.
# ════════════════════════════════════════════════════════════════════════════

def etf_cal(rows: list[tuple], vol: dict[str, float]) -> TI.ICal:
    return TI.build_icals(rows, vol, {})


def rv20_points(cal: TI.ICal, w: int = RV_WINDOW) -> np.ndarray:
    """v[i] = 100 x sqrt(252) x the sample sd of the w log total returns ending
    at close i (closes i-w..i). implied_sigma shifts it one session, so
    sigma_s reads returns i = s-w .. s-1: nothing on or after session s."""
    out = np.full(cal.n, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        lr = np.log(cal.adj[1:] / cal.adj[:-1])      # lr[j] is the return ending at close j+1
    for i in range(w, cal.n):
        x = lr[i - w:i]
        if np.all(np.isfinite(x)):
            out[i] = float(np.std(x, ddof=1)) * math.sqrt(TRADING_DAYS) * 100.0
    return out


def with_vol(cal: TI.ICal, vol: np.ndarray) -> TI.ICal:
    """The same calendar with another sigma source in the VIX slot."""
    return dataclasses.replace(cal, vix=np.asarray(vol, dtype=float))


def map_onto(cal: TI.ICal, series: dict[str, float]) -> np.ndarray:
    return np.array([series.get(d, np.nan) for d in cal.dates], dtype=float)


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def check_era() -> None:
    requested = era_mod.requested_era()
    if requested != era_mod.CURRENT:
        raise Refused(era_mod.EXIT_THIN_ERA,
                      f"tail_rebound_etf reads yfinance market data, which carries no era; "
                      f"era {requested!r} does not apply — run it without --era. Exit 2.")


def gb_problems(rows: list[tuple]) -> list[str]:
    """GB: close/adj may only fall, by at most GB_STEP_MAX in one session, and
    no raw close moves more than GB_RAW_STEP in one session."""
    out, prev = [], None
    for i, (d, _o, _h, _l, c, a) in enumerate(rows):
        if a is not None:
            r = c / a
            if prev is not None:
                step = r / prev - 1.0
                if step > GB_UP_TOL or step < -GB_STEP_MAX:
                    out.append(f"{d} close/adj step {step:+.4%}")
            prev = r
        if i and abs(c / rows[i - 1][4] - 1.0) > GB_RAW_STEP:
            out.append(f"{d} raw close step {c / rows[i - 1][4] - 1.0:+.2%}")
    return out


def ratio_steps(rows: list[tuple], limit: float = T.RATIO_STEP_MAX) -> list[str]:
    """Printed only: steps down larger than tail_breach's SPY limit."""
    out, prev = [], None
    for d, _o, _h, _l, c, a in rows:
        if a is None:
            continue
        r = c / a
        if prev is not None and r / prev - 1.0 < -limit:
            out.append(f"{d} {r / prev - 1.0:+.3%}")
        prev = r
    return out


# ════════════════════════════════════════════════════════════════════════════
# Arms
# ════════════════════════════════════════════════════════════════════════════

def spy_relative(cal: TI.ICal, spy_adj: dict[str, float], h: int) -> np.ndarray:
    """D_h(s) = R_h^ETF(s) - ln(SPY_A(date_{s+h}) / SPY_A(date_s)), SPY matched by date."""
    r = R.log_return(cal, h)
    sa = map_onto(cal, spy_adj)
    out = np.full(cal.n, np.nan)
    if cal.n > h:
        with np.errstate(invalid="ignore", divide="ignore"):
            out[:cal.n - h] = r[:cal.n - h] - np.log(sa[h:] / sa[:cal.n - h])
    return out


def build_arms(cals: dict[str, TI.ICal], registered: str | None) -> dict[str, R.Arm]:
    arms = {}
    for e in ETFS:
        cal = cals[e]
        trig = {"A": R.intraday_breach(cal), "B": R.completed_fall(cal)}
        for ev in ("A", "B"):
            for h in (H_PRIMARY, *H_SECONDARY):
                key = f"{e}-{ev}{h}"
                arms[key] = R.build_arm(key, cal, trig[ev], h, registered)
    return arms


def grade(arms: dict[str, R.Arm]) -> tuple[dict, dict, dict]:
    """(graded words, unadjusted words, Holm p). Co-primaries m = 4, secondaries m = 8;
    a gated arm stays in its family with p = 1."""
    holm_p = {}
    for keys in (PRIMARY_KEYS, SECONDARY_KEYS):
        fam = {k: arms[k] for k in keys}
        holm_p.update(R.family_p({k: a.res for k, a in fam.items()},
                                 {k: a.powered for k, a in fam.items()}))
    words = {k: R.word(arms[k].res, arms[k].powered, holm_p[k]) for k in (*PRIMARY_KEYS, *SECONDARY_KEYS)}
    plain = {k: R.word(a.res, a.powered) for k, a in arms.items()}
    return words, plain, holm_p


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

section, pct, ci_txt = T.section, T.pct, R.ci_txt
PHRASE = {"A": "an intraday 2x-VXN breach", "B": "a completed 5% fall"}


def run(refresh: bool = False) -> int:
    check_era()
    rows, vxn, vix, spy = load_inputs(refresh)
    reg = REGISTERED
    cals = {e: etf_cal(rows[e], vxn) for e in ETFS}
    spy_adj = {r[0]: r[5] for r in spy if r[5] is not None}

    print("tail_rebound_etf — after a QQQ or SMH tail fall, does the ETF's total return over the "
          "next h sessions beat its unconditional h-session return?")
    print(f"registration: {REGISTRATION} ({'registered ' + reg if reg else 'DRAFT, not registered'})")
    print("era: current (inputs are unversioned market data)")
    for e in ETFS:
        c = cals[e]
        print(f"population: {e} sessions {c.dates[0]} -> {c.dates[-1]} ({c.n}); "
              f"sample windows end on or before {reg or 'the last session'}")
    dirty = "dirty" if T._git("status", "--porcelain") else "clean"
    print(f"git: {T._git('rev-parse', '--short', 'HEAD')} "
          f"({T._git('rev-parse', '--abbrev-ref', 'HEAD')}, working tree {dirty})")
    print("inputs read:")
    for p in (*(cache_path(n) for n in SERIES), SPY_CACHE / "SPY.csv", SPY_CACHE / "VIX.csv",
              *(BARCHART_DIR / f"{e}.csv" for e in ETFS)):
        if p.exists():
            print(T._inventory(p))
    print("SEAL: not applied — no flow signal, play or backtest row is read")
    print(f"A: k={K} intraday breach, sigma = VXN(s-1)/100/sqrt(252) for both ETFs; "
          f"B: low <= {1 - MOVE:.2f} x max of the {R.LOOKBACK} prior closes; episodes chain within "
          f"{R.EPISODE_GAP}; entry = first trigger, at its close; {BOOT_N} cluster draws, seed {SEED}")

    # ── gates ───────────────────────────────────────────────────────────────
    section("GATES — inputs and basis")
    bad = []
    print(f"  GE: QQQ {len(rows['QQQ'])} rows, SMH {len(rows['SMH'])}, VXN {len(vxn)}, "
          f"SPY {len(spy)}, VIX {len(vix)} — pass")
    for e in ETFS:
        gb = gb_problems(rows[e])
        go = TI.ohlc_problems(rows[e], start=rows[e][0][0])
        bpath = BARCHART_DIR / f"{e}.csv"
        gc, n_cross = TI.cross_feed_problems(rows[e], bpath)
        print(f"  {e} GB: {len(gb)} problems (close/adj steps down up to {GB_STEP_MAX:.0%} allowed); "
              f"steps beyond tail_breach's {T.RATIO_STEP_MAX:.0%}: {ratio_steps(rows[e]) or 'none'}")
        print(f"  {e} GO: {len(go)} sessions since {rows[e][0][0]} with a missing or out-of-order high/low")
        print(f"  {e} GC: {n_cross} sessions in the Barchart cache, {len(gc)} lows off by over "
              f"{TI.CROSS_TOL:.1%}" + ("" if bpath.exists() else " (file missing: skipped)"))
        bad += [f"{e} {x}" for x in gb + go + gc]
    if bad:
        for line in bad[:10]:
            print(f"    {line}")
        raise Refused(EXIT_INPUT, "GB/GO/GC: the price basis check failed. Exit 3.")

    # ── triggers and episodes ───────────────────────────────────────────────
    section("TRIGGERS AND EPISODES (whole series)")
    for e in ETFS:
        cal = cals[e]
        for lab, t in (("A", R.intraday_breach(cal)), ("B", R.completed_fall(cal))):
            ts, ep = R.trigger_sessions(t), R.first_entries(t)
            defined = np.flatnonzero(np.isfinite(t))
            print(f"  {e} {lab}: {len(defined)} sessions defined from "
                  f"{cal.dates[defined[0]] if len(defined) else '—'}, {len(ts)} trigger sessions, "
                  f"{len(ep)} episodes; first {cal.dates[ep[0]] if ep else '—'}, "
                  f"last {cal.dates[ep[-1]] if ep else '—'}")

    # ── graded arms ─────────────────────────────────────────────────────────
    arms = build_arms(cals, reg)
    words, plain, holm_p = grade(arms)
    section("GRADED — sample, first trigger of each episode, entry at the close")
    print("  excess = mean R_h over entries - mean R_h over every eligible session (log total return)")
    for k in (*PRIMARY_KEYS, *SECONDARY_KEYS):
        a = arms[k]
        fam = "m=4" if k in PRIMARY_KEYS else "m=8"
        hw = R.uncond_halfwidth(a.r, a.pool)
        print(f"  {k:<8} h={a.h:<2} {ci_txt(a.res)}")
        print(f"           pool {int(a.pool.sum())} sessions, uncond half-width ±{pct(hw)}; "
              f"census {a.census}; GN {a.res.n_clusters} clusters (floor {MIN_CLUSTERS}), largest "
              f"{a.res.largest} entries ({pct(a.res.largest_share)}, cap 33.33%) "
              f"{'pass' if a.powered else 'FAIL'}; Holm({fam}) {holm_p[k]:.4f} "
              f"-> {words[k]} (unadjusted: {plain[k]})")

    # ── printed only ────────────────────────────────────────────────────────
    hs = (H_PRIMARY, *H_SECONDARY)
    section("PRINTED ONLY — EVERY trigger session as an entry")
    for k, a in arms.items():
        cal = cals[k[:3]]
        every = [s for s in R.trigger_sessions(a.trig) if R.window_of(cal, s, a.h, reg) == "sample"]
        print(f"  {k:<8} {ci_txt(R.excess_ci(a.r, every, a.pool, a.h))}")

    section("PRINTED ONLY — K-PARAM (event A at k = 1.5 and 2.5, VXN)")
    for e in ETFS:
        for kk in K_PARAMS:
            t = R.intraday_breach(cals[e], kk)
            for h in hs:
                print(f"  {e}-A k={kk} h={h:<2} {ci_txt(R.build_arm('A', cals[e], t, h, reg).res)}")

    section("PRINTED ONLY — MOVE-PARAM (event B at 7.5% and 10%)")
    for e in ETFS:
        for mv in MOVE_PARAMS:
            t = R.completed_fall(cals[e], mv)
            for h in hs:
                print(f"  {e}-B {mv:.1%} h={h:<2} {ci_txt(R.build_arm('B', cals[e], t, h, reg).res)}")

    section("PRINTED ONLY — VOL-ALT (event A, k = 2, sigma from VIX and from RV20)")
    for e in ETFS:
        alts = {"VIX": with_vol(cals[e], map_onto(cals[e], vix)),
                "RV20": with_vol(cals[e], rv20_points(cals[e]))}
        for lab, c in alts.items():
            t = R.intraday_breach(c)
            for h in hs:
                print(f"  {e}-A {lab:<4} h={h:<2} {ci_txt(R.build_arm('A', c, t, h, reg).res)}")

    section("PRINTED ONLY — OPEN (entry at the next session's open)")
    for k, a in arms.items():
        cal = cals[k[:3]]
        opens = R.opens_for(cal, rows[k[:3]])
        print(f"  {k:<8} {ci_txt(R.sub_result(cal, a, R.open_return(cal, opens, a.h), registered=reg))}")

    section("PRINTED ONLY — HIT (share with R_h > 0)")
    for k, a in arms.items():
        hit = np.where(np.isfinite(a.r), (a.r > 0).astype(float), np.nan)
        r = R.sub_result(cals[k[:3]], a, hit, registered=reg)
        print(f"  {k:<8} entries {pct(r.mean_entry)} vs uncond {pct(r.uncond)}; "
              f"difference {pct(r.excess)} [{pct(r.lo)}, {pct(r.hi)}]")

    section("PRINTED ONLY — MAE and MFE over sessions s+1..s+h (log, total return)")
    for k, a in arms.items():
        cal = cals[k[:3]]
        mae, mfe = R.excursions(cal, a.h)
        for lab, v in (("MAE", mae), ("MFE", mfe)):
            r = R.sub_result(cal, a, v, registered=reg)
            pool = R.pool_mask(cal, a.trig, v, a.h, reg)
            ents = [s for s in a.sample if math.isfinite(v[s])]
            med_e = float(np.median(v[ents])) if ents else float("nan")
            med_u = float(np.median(v[pool])) if pool.any() else float("nan")
            print(f"  {k:<8} {lab} mean {pct(r.mean_entry)} vs {pct(r.uncond)} "
                  f"(diff {pct(r.excess)} [{pct(r.lo)}, {pct(r.hi)}]); median {pct(med_e)} vs {pct(med_u)}")

    section("PRINTED ONLY — VOL-SCALED (R_h / VXN_s-implied h-session move)")
    for k, a in arms.items():
        r = R.sub_result(cals[k[:3]], a, R.vix_scaled(cals[k[:3]], a.r, a.h), registered=reg)
        print(f"  {k:<8} entries {r.mean_entry:+.3f} vs uncond {r.uncond:+.3f}; "
              f"excess {r.excess:+.3f} [{r.lo:+.3f}, {r.hi:+.3f}] sigma units; {r.n_clusters} clusters")

    section("PRINTED ONLY — DECADE, 2024+ and RELAUNCH (each against its own unconditional mean)")
    for k, a in arms.items():
        cuts = [*DECADES, ("2024+", SUB_START, None)]
        if k.startswith("SMH"):
            cuts.append(("RELAUNCH", RELAUNCH, None))
        for lab, lo, hi in cuts:
            print(f"  {k:<8} {lab:<10} {ci_txt(R.sub_result(cals[k[:3]], a, a.r, lo, hi, registered=reg))}")

    section("PRINTED ONLY — VS-SPY (excess of R_h^ETF - R_h^SPY on the same dates)")
    for k, a in arms.items():
        cal = cals[k[:3]]
        d = spy_relative(cal, spy_adj, a.h)
        print(f"  {k:<8} {ci_txt(R.sub_result(cal, a, d, registered=reg))}")

    # ── forward ─────────────────────────────────────────────────────────────
    section("FORWARD — entries after the registration date")
    fwd = {k: STILL_OPEN for k in PRIMARY_KEYS}
    if reg is None:
        print("  registration not accepted: no forward window. forward: STILL-OPEN")
    else:
        for k in fwd:
            a, cal = arms[k], cals[k[:3]]
            ents = [s for s in a.entries if R.window_of(cal, s, a.h, reg) == "forward"]
            pool = R.pool_mask(cal, a.trig, a.r, a.h, reg, "forward")
            res = R.excess_ci(a.r, ents, pool, a.h)
            pw = res.n_clusters >= FWD_MIN_CLUSTERS and res.powered
            fwd[k] = R.forward_word(res if pw else None, pw)
            print(f"  {k}: forward entries {res.n_entries}, clusters {res.n_clusters} "
                  f"(floor {FWD_MIN_CLUSTERS}), largest {res.largest}; open {a.census['open']}, "
                  f"gap {a.census['gap']} -> {fwd[k]}")

    section("VERDICT")
    print(f"  sample to {reg or 'the last session'}; {BOOT_N} cluster draws, seed {SEED}")
    print()
    start = {"QQQ-A": "2001", "QQQ-B": "1999", "SMH-A": "2001", "SMH-B": "2000"}
    for k in PRIMARY_KEYS:
        e, ev = k[:3], k[4]
        print(f"  >>> tail_rebound_etf {k} ({e} 21-session total return after {PHRASE[ev]}, first of "
              f"each episode, vs unconditional, {start[k[:5]]} on): {words[k]} <<<")
    print("  >>> tail_rebound_etf SECONDARY (h = 5 and 63, Holm m=8): "
          + " ".join(f"{k} {words[k]}" for k in SECONDARY_KEYS) + " <<<")
    print("  >>> tail_rebound_etf FORWARD (entries after the registration date): "
          + " ".join(f"{k} {fwd[k]}" for k in PRIMARY_KEYS) + " <<<")
    print()
    print("  REBOUND needs the 95% cluster-bootstrap CI on the excess wholly above 0 and a Holm p")
    print("  below 0.05 (co-primaries m=4; secondaries m=8); CONTINUATION the mirror. It prices no option.")
    print("  Nothing ships from this study (tail_rebound_etf.md).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="refetch QQQ, SMH and ^VXN from yfinance first")
    args = ap.parse_args(argv)
    try:
        return run(args.refresh)
    except Refused as exc:
        print(f"REFUSED — {exc.message}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
