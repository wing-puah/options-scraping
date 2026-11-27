"""ticker_regime_move — does a play's own regime label forecast that ticker's stock move?

REGISTERED 2026-11-27: research/pre-registrations/f1_selection/regime/ticker_regime_move.md.
Every floor, constant, parse rule and verdict word below is that file's. Read it
before changing anything here.

WHAT IT ASKS
------------
Each play row carries its own free-text `regime` (the model's read of that
ticker). D asks whether BULL-labelled tickers out-run BEAR-labelled ones over 21
sessions, net of their trailing beta to SPY, inside own-trend strata (close over or under the
ticker's own 50-close mean). S asks whether E-VOL-labelled tickers move more
over 10 sessions than their trailing realised vol implies, against rows with
another vol token. Stock closes only: no option price, position, tier or R.

POPULATION
----------
Non-MARKET rows of the era's analysis export, through `era.drop_sealed` with no
reader, one row per (date, ticker), SPY dropped, OHLC bars only. In-sample =
signal dates whose 21-session window closes by IN_SAMPLE_WINDOW_END (a frozen
set); forward = LIVE-lag signal dates after FWD_AFTER, never pooled. The label
parse and lag bin are `market_read`'s, imported unchanged.

STATISTICS
----------
Blocks are `i // 21` on the SPY calendar; all rows of a block travel together.
10,000 draws, seed 20261127, shared by D and S. 95% percentile CI, two-sided p.
D and S are one Holm family (m = 2) at 0.05.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run ticker_regime_move
    python -m scripts.backtest_study run ticker_regime_move --era v3
"""
from __future__ import annotations

import argparse
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

from scripts.backtest_study.f1_selection.benchmark.ticker_class import holm  # noqa: E402
from scripts.backtest_study.f1_selection.regime import market_read as MR  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402
from scripts.backtest_study.lib import underlying_features as UF  # noqa: E402
from scripts.backtest_study.lib.book import MECH_TABLE_CSV  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/ticker_regime_move.md"
REGISTERED = "2026-11-27"

# --- registered constants (the registration, not defaults) -------------------
H_D = 21                    # D's horizon, sessions
H_S = 10                    # S's horizon, sessions
HORIZONS = (10, 21)
BLOCK = 21
BLOCK_SENS = 42
BOOT_N = 10_000
SEED = 20261127
ALPHA = 0.05
ERA_MIN_DATES = 60
SMA_N = 50
D_ROWS, D_BLOCKS = 50, 6          # D: per arm, per stratum
S_ROWS, S_BLOCKS = 200, 12        # S: per arm
FWD_AFTER = "2026-11-27"          # forward: signal date strictly after
IN_SAMPLE_WINDOW_END = "2026-11-25"   # in-sample: 21-session window closes by here
MAX_DISCARD = 0.05                # D is UNDERPOWERED above this share of discarded draws
SPLIT_RATIOS = (1.5, 2.0, 3.0, 4.0, 5.0, 10.0)
SPLIT_TOL = 0.05
STRATA = ("above", "below")

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

RULE = "=" * 78
_TAG_RX = re.compile(r"\[([A-Za-z]+)\]")


# ════════════════════════════════════════════════════════════════════════════
# Rows
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Rec:
    date: str
    ticker: str
    raw: str
    label: MR.Label
    lag: str
    i: int
    flag: str | None
    out: dict = field(default_factory=dict)
    signal_tag: str = ""

    scope: str = "in"             # in / gap / fwd / fwd_not_live


def is_split_step(r: float) -> bool:
    """A step over the cap whose size sits within 5% of a common split ratio."""
    a = abs(r)
    if a <= UF._MAX_ABS_LOG_RETURN:
        return False
    ratio = math.exp(a)
    return any(abs(ratio / k - 1.0) <= SPLIT_TOL for k in SPLIT_RATIOS)


def scope_of(d: str, i: int, lag: str, end_idx: int | None) -> str:
    if d > FWD_AFTER:
        return "fwd" if lag == "LIVE" else "fwd_not_live"
    return "in" if end_idx is not None and i + H_D <= end_idx else "gap"


def dedupe(rows: list[dict]) -> tuple[list[dict], int]:
    """`(one row per (date, ticker), AMBIGUOUS pairs dropped)`. Rows whose
    direction heads agree count once, the first in export order."""
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_key[(str(r.get("date", ""))[:10], str(r.get("ticker", "")).strip().upper())].append(r)
    kept, ambiguous = [], 0
    for rs in by_key.values():
        if len({MR.parse_label(r.get("regime")).dir for r in rs}) > 1:
            ambiguous += 1
            continue
        kept.append(rs[0])
    return kept, ambiguous


def window_return(bars: dict, sessions: list[date], i: int, h: int) -> tuple[float | None, str]:
    """`(ln(c[i+h] / c[i]), reason)`. None with a reason when the window runs
    past the calendar, lacks a bar on any session, or holds a split step."""
    if i + h >= len(sessions):
        return None, "past_end"
    closes = []
    for s in sessions[i:i + h + 1]:
        b = bars.get(s)
        if b is None or not b.c or b.c <= 0:
            return None, "no_bar"
        closes.append(b.c)
    for prev, cur in zip(closes, closes[1:]):
        if is_split_step(math.log(cur / prev)):
            return None, "split_guard"
    return math.log(closes[-1] / closes[0]), ""


def own_trend(bars: dict, d: date) -> str | None:
    """`above` / `below` the mean of the last SMA_N closes on or before `d`;
    None without a bar on `d` or without SMA_N bars."""
    if d not in bars:
        return None
    tb = UF.trailing_bars(bars, d, SMA_N)
    if len(tb) < SMA_N:
        return None
    return "above" if bars[d].c > sum(b.c for b in tb) / SMA_N else "below"


def outcomes(bars: dict, cal: MR.Calendar, sessions: list[date], i: int,
             counts: Counter, beta=UF.beta_corr_spy, tag: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    b = beta(bars, sessions[i])[0]
    if b is None:
        counts["no_beta"] += 1
    for h in HORIZONS:
        r, why = window_return(bars, sessions, i, h)
        if r is None:
            counts[f"{why}_{h}"] += 1
            if why == "split_guard":
                counts[f"split_guard_{h}_{tag}"] += 1
            continue
        spy = math.log(cal.close[i + h] / cal.close[i])
        out[f"exret{h}"] = r - spy
        if b is not None:
            out[f"bres{h}"] = r - b * spy
        if h == H_S:
            rv = UF.rv20(bars, sessions[i])
            if not rv:
                counts["no_rv20"] += 1
            else:
                out["absz10"] = abs(r) / (rv * math.sqrt(H_S / 252))
    return out


@dataclass
class Built:
    recs: list[Rec]
    seal: dict
    counts: Counter


def build(rows: list[dict], cal: MR.Calendar, load_bars=U.load_bars,
          beta=UF.beta_corr_spy) -> Built:
    counts: Counter = Counter()
    plays = [r for r in rows if str(r.get("ticker", "")).strip().upper() != "MARKET"]
    counts["play_rows"] = len(plays)
    readable, seal = era_mod.drop_sealed(plays, date_key="date")
    counts["readable_rows"] = len(readable)
    kept, counts["ambiguous"] = dedupe(readable)
    counts["date_ticker_rows"] = len(kept) + counts["ambiguous"]
    sessions = [date.fromisoformat(d) for d in cal.dates]
    end_idx = cal.pos.get(IN_SAMPLE_WINDOW_END)
    recs: list[Rec] = []
    for r in kept:
        d = str(r.get("date", ""))[:10]
        tk = str(r.get("ticker", "")).strip().upper()
        if tk == "SPY":
            counts["spy"] += 1
            continue
        lab = MR.parse_label(r.get("regime"))
        if lab.dir == "OTHER":
            counts["other"] += 1
            continue
        if d not in cal.pos:
            counts["off_calendar"] += 1
            continue
        i = cal.pos[d]
        bars = load_bars(tk)
        if not bars:
            counts["no_bars"] += 1
            continue
        if any(x.source == U.SRC_TILDE for x in bars.values()):
            counts["tilde_bars"] += 1
            continue
        lag = MR.lag_bin(r.get("created_datetime"), d)
        counts["transition"] += lab.transition
        m = _TAG_RX.search(str(r.get("signal") or ""))
        recs.append(Rec(d, tk, str(r.get("regime") or ""), lab, lag, i,
                        own_trend(bars, sessions[i]),
                        outcomes(bars, cal, sessions, i, counts, beta, lab.dir),
                        m.group(1).upper() if m else "none",
                        scope_of(d, i, lag, end_idx)))
    recs.sort(key=lambda x: (x.date, x.ticker))
    return Built(recs, seal, counts)


# ════════════════════════════════════════════════════════════════════════════
# Contrasts
# ════════════════════════════════════════════════════════════════════════════

def is_bull(r: Rec) -> bool:
    return r.label.dir == "BULL" and not r.label.transition


def is_bear(r: Rec) -> bool:
    return r.label.dir == "BEAR" and not r.label.transition


def is_evol(r: Rec) -> bool:
    return r.label.vol == "E-VOL"


def is_other_vol(r: Rec) -> bool:
    return r.label.vol is not None and r.label.vol != "E-VOL"


def d_strat(pop: MR.Pop, key: str = "bres21") -> MR.Result:
    """BULL minus BEAR inside each own-trend stratum, weighted by each stratum's
    share of the BULL and BEAR rows holding `key`. Both strata always enter.
    Gradable only when BOTH meet the floor and at most MAX_DISCARD of the draws
    are discarded; `res.weights` is empty otherwise."""
    parts, info = {}, {}
    for s in STRATA:
        SA, NA = pop.vec(lambda r, s=s: r.flag == s and is_bull(r), key)
        SB, NB = pop.vec(lambda r, s=s: r.flag == s and is_bear(r), key)
        (na, ba), (nb, bb) = MR._arm(NA), MR._arm(NB)
        info[s] = {"A": (na, ba), "B": (nb, bb),
                   "enters": min(na, nb) >= D_ROWS and min(ba, bb) >= D_BLOCKS,
                   "diff": MR._ratio(SA.sum(), NA.sum()) - MR._ratio(SB.sum(), NB.sum())}
        parts[s] = (SA, NA, SB, NB)
    res = MR.Result(strata=info)
    tot = sum(info[s]["A"][0] + info[s]["B"][0] for s in STRATA)
    if not tot or any(min(info[s]["A"][0], info[s]["B"][0]) == 0 for s in STRATA):
        return MR.summarize(res, np.full(len(pop.draws.W), np.nan))
    w = {s: (info[s]["A"][0] + info[s]["B"][0]) / tot for s in STRATA}
    res.point = float(sum(w[s] * info[s]["diff"] for s in STRATA))
    stat = np.zeros(len(pop.draws.W))
    for s in STRATA:
        SA, NA, SB, NB = parts[s]
        stat = stat + w[s] * (pop.per_draw_mean(SA, NA) - pop.per_draw_mean(SB, NB))
    MR.summarize(res, stat)
    if (all(info[s]["enters"] for s in STRATA)
            and res.discarded <= MAX_DISCARD * len(pop.draws.W)):
        res.weights = w
    return res


def d_raw(pop: MR.Pop, key: str = "bres21") -> MR.Result:
    return MR.mean_diff(pop, key, is_bull, is_bear)


def d_twin(pop: MR.Pop, key: str = "bres21") -> MR.Result:
    return MR.mean_diff(pop, key, lambda r: r.flag == "above", lambda r: r.flag == "below")


def s_diff(pop: MR.Pop) -> MR.Result:
    return MR.mean_diff(pop, "absz10", is_evol, is_other_vol)


def s_floor(res: MR.Result) -> bool:
    return all(n >= S_ROWS and b >= S_BLOCKS for n, b in res.arms.values())


def raw_word(res: MR.Result, floors_ok: bool) -> str:
    if not floors_ok or not (math.isfinite(res.lo) and math.isfinite(res.hi)):
        return "UNDERPOWERED"
    return "SUPPORTED" if res.lo > 0 else "CONTRARY" if res.hi < 0 else "NULL"


def final_word(raw: str, p_adj: float, forward: bool = False) -> str:
    """SUPPORTED and CONTRARY also need the Holm-adjusted p under ALPHA. An
    in-sample SUPPORTED prints IN-SAMPLE-ONLY; SUPPORTED is a forward word."""
    if raw in ("SUPPORTED", "CONTRARY") and not p_adj < ALPHA:
        return "NULL"
    if raw == "SUPPORTED" and not forward:
        return "IN-SAMPLE-ONLY"
    return raw


READ = {"IN-SAMPLE-ONLY": "IN-SAMPLE-ONLY", "NULL": "NO-FORECAST",
        "CONTRARY": "CONTRARY", "UNDERPOWERED": "UNDERPOWERED"}


def grade(recs: list[Rec], size: int = BLOCK, forward: bool = False) -> dict:
    """D and S on one set of rows, with one shared set of block draws."""
    pop = MR.Pop(recs, size)
    rd, rs = d_strat(pop), s_diff(pop)
    wd_raw = raw_word(rd, bool(rd.weights))
    ws_raw = raw_word(rs, s_floor(rs))
    adj = holm({"D": rd.p if wd_raw != "UNDERPOWERED" and math.isfinite(rd.p) else 1.0,
                "S": rs.p if ws_raw != "UNDERPOWERED" and math.isfinite(rs.p) else 1.0})
    return {"pop": pop, "D": rd, "S": rs, "adj": adj,
            "wD": final_word(wd_raw, adj["D"][0], forward),
            "wS": final_word(ws_raw, adj["S"][0], forward)}


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def section(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def _ci(res: MR.Result, scale: float, fmt: str) -> str:
    if not math.isfinite(res.point):
        return "n/a"
    f = lambda x: format(x * scale, fmt) if math.isfinite(x) else "n/a"  # noqa: E731
    return f"{f(res.point)} [{f(res.lo)}, {f(res.hi)}]"


def _arms(res: MR.Result, names) -> str:
    return "  ".join(f"{nm} {res.arms[k][0]}r/{res.arms[k][1]}b" for nm, k in zip(names, ("A", "B")))


def _p(x: float) -> str:
    return f"{x:.4f}" if math.isfinite(x) else "n/a"


def d_line(name: str, res: MR.Result) -> str:
    st = "; ".join(f"{s} BULL {v['A'][0]}r/{v['A'][1]}b BEAR {v['B'][0]}r/{v['B'][1]}b "
                   f"diff {v['diff'] * 100:+.2f}{'' if v['enters'] else ' (under floor)'}"
                   for s, v in res.strata.items())
    return (f"  {name:<8}{_ci(res, 100, '+.2f')}  p={_p(res.p)}  "
            f"discarded draws {res.discarded}\n          {st}")


def print_contrasts(recs: list[Rec], size: int = BLOCK) -> None:
    g = grade(recs, size)
    pop = g["pop"]
    print(d_line("D", g["D"]))
    r = d_raw(pop)
    print(f"  D-raw  {_ci(r, 100, '+.2f')}  p={_p(r.p)}  {_arms(r, ('BULL', 'BEAR'))}")
    s = g["S"]
    print(f"  S      {_ci(s, 1, '+.3f')}  p={_p(s.p)}  {_arms(s, ('E-VOL', 'other-vol'))}")


def report_population(b: Built, ins: list[Rec], era: str) -> None:
    section("POPULATION")
    c = b.counts
    print(f"  play rows {c['play_rows']}; readable after the seal guard {c['readable_rows']}; "
          f"(date, ticker) pairs {c['date_ticker_rows']}")
    print(f"  dropped: AMBIGUOUS {c['ambiguous']}, SPY {c['spy']}, OTHER head {c['other']} "
          f"({c['other'] / max(1, c['date_ticker_rows']):.1%} of pairs), off-calendar "
          f"{c['off_calendar']}, no bars {c['no_bars']}, close-only bars {c['tilde_bars']}")
    print(f"  kept {len(b.recs)} rows = {c['date_ticker_rows']} - {c['ambiguous']} - {c['spy']} - "
          f"{c['other']} - {c['off_calendar']} - {c['no_bars']} - {c['tilde_bars']}")
    sc = Counter(r.scope for r in b.recs)
    print(f"  scope: in-sample {sc['in']}, gap {sc['gap']}, forward LIVE {sc['fwd']}, "
          f"forward not LIVE {sc['fwd_not_live']}")
    for h in HORIZONS:
        print(f"  {h}-session window drops: past end {c[f'past_end_{h}']}, no bar "
              f"{c[f'no_bar_{h}']}, split guard {c[f'split_guard_{h}']} ("
              + ", ".join(f"{d} {c[f'split_guard_{h}_{d}']}" for d in MR.DIRS) + ")")
    print(f"  no rv20 (leaves S) {c['no_rv20']}; no beta (leaves D) {c['no_beta']}; "
          f"transition head (leaves D) {c['transition']}; no own-trend flag (leaves D) "
          f"{sum(1 for r in b.recs if r.flag is None)}")
    print(f"  in-sample (era {era}, 21-session window closed by {IN_SAMPLE_WINDOW_END}): "
          f"{len(ins)} rows, "
          f"{len({r.date for r in ins})} dates, {len({r.ticker for r in ins})} tickers, "
          f"{len({r.i // BLOCK for r in ins})} blocks")
    print("  label census, in-sample rows: " + ", ".join(
        f"{k} {v}" for k, v in Counter(r.label.dir for r in ins).most_common()))
    print("  vol token: " + ", ".join(
        f"{k} {v}" for k, v in Counter(r.label.vol or "none" for r in ins).most_common()))
    print("  lag bin: " + ", ".join(
        f"{k} {v}" for k, v in Counter(r.lag for r in ins).most_common()))


def report_grid(ins: list[Rec]) -> None:
    section("GRID — mean bres21 (pp) and absz10 per dir x vol cell, printed only")
    print(f"  {'dir':<6}{'vol':<7}{'rows':>6}{'bres21':>10}{'absz10':>9}")
    cells: dict[tuple[str, str], list[Rec]] = defaultdict(list)
    for r in ins:
        cells[(r.label.dir, r.label.vol or "none")].append(r)
    for (d, v), rs in sorted(cells.items()):
        e = [r.out["bres21"] for r in rs if "bres21" in r.out]
        z = [r.out["absz10"] for r in rs if "absz10" in r.out]
        print(f"  {d:<6}{v:<7}{len(rs):>6}"
              f"{(format(np.mean(e) * 100, '+.2f') if e else 'n/a'):>10}"
              f"{(format(np.mean(z), '.3f') if z else 'n/a'):>9}")


def verdict(era: str, ins: list[Rec], g: dict, fwd_recs: list[Rec]) -> None:
    section("VERDICT")
    rd, rs, adj = g["D"], g["S"], g["adj"]
    print(f"  era {era}, 21-session window closed by {IN_SAMPLE_WINDOW_END}: {len(ins)} rows, "
          f"{len({r.date for r in ins})} dates, {g['pop'].draws.k} blocks; "
          f"{BOOT_N} block draws, seed {SEED}")
    print("  bres21 in percentage points; absz10 as a ratio; [95% CI]")
    print(d_line("D", rd))
    print(f"          Holm adj p {_p(adj['D'][0])}")
    print(f"  S      {_ci(rs, 1, '+.3f')}  p={_p(rs.p)}  {_arms(rs, ('E-VOL', 'other-vol'))}  "
          f"Holm adj p {_p(adj['S'][0])}")
    print(f"  >>> ticker_regime_move D (BULL - BEAR, 21d beta-adjusted return, own-trend strata, "
          f"{era} in-sample): {g['wD']} <<<")
    print(f"  >>> ticker_regime_move S (E-VOL - other vol, scaled 10d move, {era} in-sample): "
          f"{g['wS']} <<<")
    print(f"  >>> ticker_regime_move READ (D): {READ[g['wD']]} <<<")
    fd = fs = "STILL-OPEN"
    if fwd_recs:
        gf = grade(fwd_recs, forward=True)
        fd = gf["wD"] if gf["D"].weights else fd
        fs = gf["wS"] if s_floor(gf["S"]) else fs
    print(f"  >>> ticker_regime_move FORWARD (LIVE signal dates after {FWD_AFTER}): "
          f"D {fd}, S {fs} <<<")
    print("  D and S are one Holm family (m = 2) at 0.05.")
    print("  The first run is the in-sample verdict of record. A contrast's forward verdict "
          "of record is its first word other than STILL-OPEN.")
    print("  Nothing ships from this study (ticker_regime_move.md).")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)

    requested = era_mod.requested_era()
    paths = era_mod.resolve_paths(requested)
    era = era_mod.enforce(requested, paths)

    print("ticker_regime_move — does a play's own regime label forecast that ticker's "
          "stock move?")
    print(f"registration: {REGISTRATION} (registered {REGISTERED})")
    print(f"era: {era} (requested {requested!r}); reads {paths['analysis'].name} only, "
          f"non-MARKET rows; SPY calendar {MECH_TABLE_CSV.relative_to(ROOT)}; ticker closes "
          f"from lib/underlying.py::load_bars")
    print(f"blocks i//{BLOCK} on the SPY calendar; {BOOT_N} draws, seed {SEED}; floors D "
          f"{D_ROWS}r+{D_BLOCKS}b per arm per stratum, S {S_ROWS}r+{S_BLOCKS}b per arm")

    cal = MR.load_calendar(MECH_TABLE_CSV)
    b = build(MR.read_rows(paths["analysis"]), cal)
    print(era_mod.seal_line(b.seal))
    print(f"calendar: {len(cal.dates)} sessions {cal.dates[0]} -> {cal.dates[-1]}")

    ins = [r for r in b.recs if r.scope == "in"]
    fwd = [r for r in b.recs if r.scope == "fwd"]
    era_mod.require_dates(len({r.date for r in ins}), era, minimum=ERA_MIN_DATES,
                          what="in-sample dates with a closed window")

    report_population(b, ins, era)
    g = grade(ins)
    pop = g["pop"]

    section("D — direction: BULL minus BEAR mean bres21 (pp), own-trend strata (graded)")
    print(d_line("D", g["D"]))
    r = d_raw(pop)
    print(f"  D-raw  {_ci(r, 100, '+.2f')}  p={_p(r.p)}  {_arms(r, ('BULL', 'BEAR'))}  (printed)")
    t = d_twin(pop)
    print(f"  D-twin {_ci(t, 100, '+.2f')}  p={_p(t.p)}  {_arms(t, ('above', 'below'))}  "
          f"(printed control)")
    print(d_line("D-plain", d_strat(pop, "exret21")) + "  (printed, beta fixed at 1)")
    print(d_line("D10", d_strat(pop, "bres10")) + "  (printed)")
    rng = [x for x in ins if x.label.dir == "RANGE" and "bres21" in x.out]
    if rng:
        print(f"  RANGE rows: {len(rng)}, mean bres21 "
              f"{np.mean([x.out['bres21'] for x in rng]) * 100:+.2f} (printed)")

    section("S — size: E-VOL minus other-vol mean absz10 (graded)")
    s = g["S"]
    print(f"  S      {_ci(s, 1, '+.3f')}  p={_p(s.p)}  {_arms(s, ('E-VOL', 'other-vol'))}")

    section("LAG CUTS — D, D-raw, S on LIVE rows and on RETRO rows, printed only")
    for lag in ("LIVE", "RETRO"):
        cut = [x for x in ins if x.lag == lag]
        print(f"  {lag}: {len(cut)} rows, {len({x.date for x in cut})} dates")
        if cut:
            print_contrasts(cut)

    report_grid(ins)

    section("SIGNAL TAGS — leading tag of the `signal` column, in-sample rows, printed only")
    print("  " + ", ".join(f"{k} {v}" for k, v in Counter(x.signal_tag for x in ins).most_common()))

    section(f"BLOCK {BLOCK_SENS} — D and S with blocks i//{BLOCK_SENS}, printed sensitivity")
    print_contrasts(ins, BLOCK_SENS)

    section("FORWARD")
    print(f"  LIVE signal dates after {FWD_AFTER}: {len(fwd)} rows, "
          f"{len({x.date for x in fwd})} dates")

    verdict(era, ins, g, fwd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
