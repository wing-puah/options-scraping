"""refuse_floor_forward — do refusing and narrowing an unaffordable pick hold up on new dates?

Registration: `research/pre-registrations/f4_deployment/refuse_floor_forward.md`
(registered 2026-10-07, first forward date 2026-10-08). That file is the spec;
this module implements it and adds nothing to its bar. RESEARCH TIER: nothing
ships from this study.

TWO GRADED CELLS, each on both cap cells, each with its own verdict line:

    (R, F2, $500)    refuse   account_sim's F2
    (R, F3, $500)    narrow   narrow_to_fit's F3 at $500 (Narrower IMPORTED)

and two printed controls, `(R, F1, $500)` and `(R, F2, $1,000)`.

The book is loaded whole by `load_book` (so `lib/era.py`'s refusals fire),
then FILTERED to signal dates on or after `FIRST_FORWARD_DATE`. A fresh
$25,000 account runs on that forward book alone: no position is carried in.

THE GRADE is a confidence sequence (`lib/confidence_sequence.py`, Waudby-Smith
et al. 2024 Theorem 2.2) over one observation per forward signal date: the
mean R of the positions the cell took that date. The sequence stops before the
first date that still holds an open position (complete prefix). The running
intersection starts at the first count meeting 30 dates and 60 positions;
alpha is 0.0125 per sequence (four graded sequences), t* = 150.

A LOOK is any run. Every look appends one JSON line to `LOOK_LOG` (tracked,
under research/study-results/) with every sequence's dates and values, which
is what FW4 re-checks the next look against.

Before any forward date has a loaded row the module prints the census and
STILL-OPEN for every cell, logs the look, and exits `EXIT_NO_FORWARD` — a
DESIGNED refusal, not a failure.

Cells run IN PROCESS on `account_sim.simulate` with `Settings` copied by
`dataclasses.replace`, so no `account_sim` or `narrow_to_fit` artifact, and
no site page, is written.

Usage:
  python3 -m scripts.backtest_study run refuse_floor_forward
  python3 -m scripts.backtest_study.f4_deployment.refuse_floor_forward
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f4_deployment import account_sim as AS  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NF  # noqa: E402
from scripts.backtest_study.f4_deployment.narrow_to_fit import (  # noqa: E402
    Chain, Narrower, unlisted_evidence,
)
from scripts.backtest_study.lib import confidence_sequence as CS  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as MC  # noqa: E402
from scripts.backtest_study.lib import path_bootstrap as PB  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# Era refusals (2 thin era, 3 wrong era) from `load_book`, plus this study's
# own: no forward date has a loaded row yet.
EXIT_NO_FORWARD = 4
DESIGNED_REFUSAL_EXIT_CODES = {2, 3, 4}

hdr, sub = AS.hdr, AS.sub

# ── registered constants (registration, "The boundary" / "Minimum counts") ──
REGISTERED_ON = "2026-10-07"
FIRST_FORWARD_DATE = "2026-10-08"
#: The registration commit. Every look lists the commits after it that touch
#: pricing, the loader, account_sim or narrow_to_fit (Anti-tuning).
REGISTRATION_COMMIT = "920713a"
ALPHA = 0.0125
T_STAR = 150
MIN_DATES = 30
MIN_POSITIONS = 60
REFUTE_BAR = 0.10
DD_BAR = 0.25
BUDGET = 500.0
HEAD_NET_CAP = NF.HEAD_NET_CAP          # 1.50, the registered cap cell
ROBUST_NET_CAP = NF.ROBUST_NET_CAP      # 2.50, the tracked cap cell
CAPS = (HEAD_NET_CAP, ROBUST_NET_CAP)
PER_POS_CAP = NF.PER_POS_CAP
GN5_MAX_UNPRICED = NF.GN5_MAX_UNPRICED  # narrow_to_fit's coverage bar, imported
FWD_BLOCK = 10
FWT_DEPTH = 0.10

#: `(key, label, budget-kind, floor rule, graded?)`. "low" is the config's 2%
#: budget ($500), "high" narrow_to_fit's $1,000.
CELLS = (
    ("F2", "(R, F2, $500)", "low", "refuse", True),
    ("F3", "(R, F3, $500)", "low", "narrow", True),
    ("F1", "(R, F1, $500)", "low", "take", False),
    ("F2_HI", "(R, F2, $1,000)", "high", "refuse", False),
)
GRADED = tuple(k for k, *_rest, g in CELLS if g)
LABEL = {k: lab for k, lab, *_ in CELLS}

LOOK_LOG = (ROOT / "research" / "study-results" / "f4_deployment"
            / "refuse_floor_forward-looks.jsonl")
#: Paths whose commits a look lists (Anti-tuning, "Code changes").
WATCHED_PATHS = ("scripts/backtest/", "scripts/backtest_study/lib/book.py",
                 "scripts/backtest_study/lib/replay_basis.py",
                 "scripts/backtest_study/lib/harness.py",
                 "scripts/backtest_study/f4_deployment/account_sim.py",
                 "scripts/backtest_study/f4_deployment/narrow_to_fit.py")

#: Verdict tokens, worst first (registration, "Verdicts").
REFUTED_DD = "FORWARD-REFUTED (drawdown)"
REFUTED_EDGE = "FORWARD-REFUTED (edge)"
AWAITING = "AWAITING SCRAPE"
OPEN = "STILL-OPEN"
CONFIRMED = "FORWARD-CONFIRMED"
ORDER = (REFUTED_DD, REFUTED_EDGE, AWAITING, OPEN, CONFIRMED)

log = logging.getLogger("refuse_floor_forward")


# ════════════════════════════════════════════════════════════════════════════
# The statistic
# ════════════════════════════════════════════════════════════════════════════

def is_open(p: AS.Pos) -> bool:
    """A taken position still open at the data end: its replay ended
    `cap_open` on a row production booked `open_at_data_end`. A position that
    exited, expired or reached the path cap is closed."""
    status = (p.rec["t"].row.get("path_status") or "").strip()
    return p.exit_reason == "cap_open" and status == "open_at_data_end"


def date_observations(positions) -> tuple[list[tuple[str, float, int]], str | None, int]:
    """The complete prefix: `[(date, mean R, n positions)]` in signal-date order,
    stopping BEFORE the first date that holds an open position.

    Returns the prefix, the date it stopped at (None when nothing is open) and
    the number of positions open on that date or later.
    """
    by = defaultdict(list)
    for p in positions:
        by[p.rec["date"]].append(p)
    out, stop, n_open = [], None, 0
    for d in sorted(by):
        if stop is None and any(is_open(p) for p in by[d]):
            stop = d
        if stop is not None:
            n_open += sum(1 for p in by[d] if is_open(p))
            continue
        rs = [p.R for p in by[d]]
        out.append((d, sum(rs) / len(rs), len(rs)))
    return out, stop, n_open


def start_index(obs: list[tuple[str, float, int]]) -> int | None:
    """The first `t` (1-indexed) meeting both minimum counts, or None."""
    n_pos = 0
    for t, (_d, _x, n) in enumerate(obs, start=1):
        n_pos += n
        if t >= MIN_DATES and n_pos >= MIN_POSITIONS:
            return t
    return None


def run_sequence(obs) -> dict:
    """The confidence sequence over `obs`, summarised for the report and log."""
    xs = [x for _d, x, _n in obs]
    start = start_index(obs)
    steps = CS.sequence(xs, ALPHA, T_STAR, start=start or (len(xs) + 1)) if xs else []
    last = steps[-1] if steps else None
    return dict(
        t=len(xs), start=start, n_pos=sum(n for *_x, n in obs),
        dates=[d for d, _x, _n in obs], xs=xs, ns=[n for *_x, n in obs],
        mean=last.mean if last else None, lo=last.lo if last else None,
        hi=last.hi if last else None,
        run_lo=last.run_lo if last else None, run_hi=last.run_hi if last else None,
        empty=bool(last and last.empty))


def verdict(seq: dict, dd_breach: bool, awaiting: bool = False) -> str:
    """The first verdict row, from the top, whose condition holds."""
    if awaiting:
        return AWAITING
    if dd_breach:
        return REFUTED_DD
    if seq["start"] is None or seq["run_lo"] is None or seq["empty"]:
        return OPEN
    if seq["run_hi"] < REFUTE_BAR:
        return REFUTED_EDGE
    if seq["run_lo"] > 0:
        return CONFIRMED
    return OPEN


def worse(a: str, b: str) -> str:
    return a if ORDER.index(a) <= ORDER.index(b) else b


def closed_drawdown(sim: AS.Sim) -> float:
    """A3's realized-on-close curve, on the closed positions only (dollars, <= 0)."""
    _, vals = AS.equity_curve([p for p in sim.signal_pos if not is_open(p)])
    return AS.max_drawdown(vals) if vals else 0.0


# ════════════════════════════════════════════════════════════════════════════
# The look log and FW4
# ════════════════════════════════════════════════════════════════════════════

def read_looks(path: Path | None = None) -> list[dict]:
    path = path or LOOK_LOG
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def append_look(rec: dict, path: Path | None = None) -> None:
    path = path or LOOK_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= 1e-9


def fw4_check(key: str, seq: dict, looks: list[dict]) -> tuple[bool, list[str]]:
    """FW4 SEQUENCE CHECK for one sequence against the newest earlier look
    that held it with `t > 0`. Returns (ok, lines)."""
    prev = next((lk["sequences"][key] for lk in reversed(looks)
                 if key in lk.get("sequences", {}) and lk["sequences"][key]["t"] > 0),
                None)
    if prev is None:
        return True, [f"  {key}: no earlier look with t > 0 — nothing to re-check"]
    t0 = prev["t"]
    now = list(zip(seq["dates"], seq["xs"], seq["ns"]))[:t0]
    was = list(zip(prev["dates"], prev["xs"], prev["ns"]))
    changed = [d for (d, x, n), (d0, x0, n0) in zip(now, was)
               if d != d0 or n != n0 or abs(x - x0) > 1e-12]
    if len(now) < t0:
        changed += [d0 for d0, *_ in was[len(now):]]
    obs = [(d, x, n) for d, x, n in now]
    start = start_index(obs)
    step = (CS.interval_at([x for _d, x, _n in obs], t0, ALPHA, T_STAR,
                           start=start or (t0 + 1)) if len(obs) == t0 else None)
    run_lo = step.run_lo if step else None
    run_hi = step.run_hi if step else None
    same = (len(obs) == t0 and _same(run_lo, prev["run_lo"])
            and _same(run_hi, prev["run_hi"]))
    if same:
        return True, [f"  {key}: interval at the previous look's t={t0} reproduced"]
    if changed:
        return True, [f"  {key}: interval at t={t0} moved; explained by changed "
                      f"dates {', '.join(sorted(set(changed)))}"]
    return False, [f"  {key}: interval at t={t0} moved and no X_i changed — FW4 FAILS "
                   f"(logged {prev['run_lo']}..{prev['run_hi']}, now {run_lo}..{run_hi})"]


# ════════════════════════════════════════════════════════════════════════════
# Census and provenance
# ════════════════════════════════════════════════════════════════════════════

def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, check=False).stdout.strip()
    except OSError:
        return ""


def export_census(first: str) -> tuple[list[tuple], dict]:
    """Per export: rows on forward dates, last signal date, file mtime."""
    rows, stamps = [], {}
    for key, path in era.resolve_paths().items():
        col = "date" if key == "analysis" else "signal_date"
        if not path.exists():
            rows.append((key, path.name, None, None, None))
            continue
        n_fwd, last = 0, ""
        with path.open(newline="") as fh:
            for r in csv.DictReader(fh):
                d = (r.get(col) or "").strip()[:10]
                last = max(last, d)
                n_fwd += d >= first
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        stamps[key] = mtime
        rows.append((key, path.name, n_fwd, last or None, mtime))
    return rows, stamps


def print_census(census_rows, fwd_recs, first: str) -> None:
    hdr("FORWARD CENSUS — counts only")
    print(f"  first forward date {first}; registered {REGISTERED_ON}")
    print(f"  {'export':<10}{'rows on forward dates':>24}{'last signal date':>20}"
          f"{'mtime':>20}")
    n_exp = 0
    for key, _name, n, last, mtime in census_rows:
        print(f"  {key:<10}{('missing' if n is None else n):>24}{(last or '—'):>20}"
              f"{(mtime or '—'):>20}")
        if key in ("results", "proxy") and n:
            n_exp += n
    n_dates = len({r["date"] for r in fwd_recs})
    print(f"  loaded into the study book: {len(fwd_recs)} rows on {n_dates} forward dates")
    print(f"  results + proxy rows on forward dates not loaded by load_book "
          f"(bs rows, proxy duplicates of a real row, no path/method, failed "
          f"construction): {max(n_exp - len(fwd_recs), 0)}")


# ════════════════════════════════════════════════════════════════════════════
# Context, never graded
# ════════════════════════════════════════════════════════════════════════════

def ratio_on(sim: AS.Sim, ref: AS.Sim, dates: set) -> float:
    num = sum(p.dollars for p in sim.signal_pos if p.rec["date"] in dates)
    den = sum(p.dollars for p in ref.signal_pos if p.rec["date"] in dates)
    return AS.pct_ratio(num, den)


def fw5(sim: AS.Sim, b2: AS.Sim) -> tuple[float, str | None]:
    """A2-reg with each forward calendar month dropped; the largest move (points)."""
    base = ratio_on(sim, b2, sim.dates)
    worst, which = 0.0, None
    for m in sorted({d[:7] for d in sim.dates}):
        kept = {d for d in sim.dates if d[:7] != m}
        r = ratio_on(sim, b2, kept)
        if r == r and base == base and abs(r - base) > abs(worst):
            worst, which = r - base, m
    return worst, which


def mtm_maxdd(sim: AS.Sim) -> tuple[float | None, int]:
    markable, bad = [], 0
    for p in sim.signal_pos:
        try:
            MC.position_marks(p)
        except (ValueError, KeyError, TypeError, IndexError):
            bad += 1
        else:
            markable.append(p)
    if not markable:
        return None, bad
    bc = MC.book_curves(markable, target=MC.TARGET_POSITION)
    return MC.path_stats(bc.mtm, sim.cfg.capital).max_dd, bad


def fmt(x, spec="+.3f") -> str:
    return "—" if x is None or x != x else format(x, spec)


def print_sequence(label: str, seq: dict) -> None:
    print(f"  {label:<34} t={seq['t']:>4}  positions={seq['n_pos']:>4}  "
          f"start={seq['start'] or '—':>4}  mean {fmt(seq['mean'])}  "
          f"step [{fmt(seq['lo'])},{fmt(seq['hi'])}]  "
          f"running [{fmt(seq['run_lo'])},{fmt(seq['run_hi'])}]"
          f"{'  CS EMPTY' if seq['empty'] else ''}")


def print_context(key: str, cap: float, sims: dict, b2s: dict, b2caps: dict,
                  st: AS.Settings) -> None:
    sim = sims[("PRIMARY", cap, key)]
    b2 = b2s[("PRIMARY", cap)]
    capital = st.capital
    rs = [p.R for p in sim.signal_pos]
    print(f"  positions {len(rs)} on {len(sim.dates)} dates; position-weighted "
          f"meanR {fmt(AS.fmean(rs) if rs else None)}; total ${sim.dollars:,.0f}")
    print(f"  A2-reg {fmt(ratio_on(sim, b2, sim.dates), '.0%')}   "
          f"A2-all {fmt(AS.pct_ratio(sim.dollars, b2.dollars), '.0%')}   "
          f"A2-cap {fmt(ratio_on(sim, b2caps[('PRIMARY', cap, key)], sim.dates), '.0%')}"
          f" (disclosure)")
    move, month = fw5(sim, b2)
    print(f"  FW5 largest leave-one-month-out move {move * 100:+.0f} points"
          f"{f' (drop {month})' if month else ''}")
    deb = [p for p in sim.signal_pos if not p.rec["credit"]]
    obs, _stop, _n = date_observations(deb)
    print_sequence("A6 debit-only sequence", run_sequence(obs))
    _, vals = AS.equity_curve(sim.signal_pos)
    if vals:
        band = PB.bootstrap_drawdown(vals, capital, FWD_BLOCK, AS.BOOTSTRAP_N,
                                     AS.BOOTSTRAP_SEED)
        print(f"  FWD median bootstrap maxDD {band.p50:.1%} (block {FWD_BLOCK}, "
              f"seed {AS.BOOTSTRAP_SEED}, {AS.BOOTSTRAP_N} paths) against "
              f"{DD_BAR:.0%}")
    else:
        print("  FWD no closed P&L yet")
    ref = sims[("PRIMARY", cap, "F1")]
    wins = NF.n3_windows(ref, capital)
    if not wins:
        print(f"  FWT no (R, F1, $500) drawdown reaches {FWT_DEPTH:.0%} of capital")
    for d in wins:
        print(f"  FWT {d.peak_label}..{d.trough_sess}  F1 {d.depth:,.0f}  "
              f"cell {NF.depth_inside(sim, d):,.0f}")
    mdd, bad = mtm_maxdd(sim)
    print(f"  MTM maxDD {('—' if mdd is None else f'{mdd:,.0f}')}"
          f"  (unmarkable positions {bad})")


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def seq_key(cell: str, cap: float, pop: str) -> str:
    return f"{cell}|{cap:.2f}|{pop}"


def look_record(stamps: dict, n_rows: int, n_dates: int, seqs: dict,
                verdicts: dict, gn5: dict | None) -> dict:
    return dict(
        look_at=datetime.now().isoformat(timespec="seconds"),
        git=_git("rev-parse", "--short", "HEAD") or "unknown",
        dirty=bool(_git("status", "--porcelain", "--untracked-files=no")),
        era=era.requested_era(), exports=stamps,
        first_forward_date=FIRST_FORWARD_DATE, forward_rows=n_rows,
        forward_dates=n_dates, alpha=ALPHA, t_star=T_STAR,
        sequences=seqs, verdicts=verdicts, gn5=gn5)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip-gates", action="store_true",
                    help="skip account_sim's G2-G5 (debugging only; the report "
                         "says so)")
    args = ap.parse_args(argv)
    logging.getLogger("backtest").setLevel(logging.ERROR)

    st = AS.load_settings(AS.DEFAULT_CONFIG)
    if abs(st.per_pos_cap - PER_POS_CAP) > 1e-9 or abs(st.budget - BUDGET) > 1e-9:
        print(f"REFUSED — config per-position cap {st.per_pos_cap} / budget "
              f"{st.budget} is not the registered {PER_POS_CAP} / {BUDGET}")
        return 2
    assert abs(st.maxdd_fraction - DD_BAR) < 1e-9, "A3's bar must be the registered 25%"

    rho = CS.rho_for(ALPHA, T_STAR)
    hdr("refuse_floor_forward — do refusing and narrowing an unaffordable pick "
        "hold up on new dates?")
    print(f"""  Registration research/pre-registrations/f4_deployment/refuse_floor_forward.md
  Registered {REGISTERED_ON}; first forward date {FIRST_FORWARD_DATE}.
  Graded: {LABEL['F2']} and {LABEL['F3']}, each on net {HEAD_NET_CAP:.2f}x and
  {ROBUST_NET_CAP:.2f}x (per-position {PER_POS_CAP:.2f}x), each its own verdict line.
  Confidence sequence: alpha {ALPHA} per sequence (two-sided), t* {T_STAR},
  rho {rho:.5f}; intersection from {MIN_DATES} dates and {MIN_POSITIONS} positions.
  NOTHING SHIPS FROM THIS STUDY. FW3: every count below is computed by this
  run; no annualised figure, Sharpe or time-to-recover is printed.""")

    recs, diag = load_book(include_bs=False)
    print(f"  era {diag.get('era')}  book {len(recs)} rows  {diag.get('n_dates')} "
          f"dates  {diag.get('date_range')}")
    fwd = [r for r in recs if r["date"] >= FIRST_FORWARD_DATE]
    seen = [r for r in recs if r["date"] < FIRST_FORWARD_DATE]
    census_rows, stamps = export_census(FIRST_FORWARD_DATE)
    print_census(census_rows, fwd, FIRST_FORWARD_DATE)
    looks = read_looks()
    print(f"  earlier looks in the log: {len(looks)}")

    # ── no forward date yet: designed refusal ────────────────────────────
    if not fwd:
        hdr("VERDICTS")
        print("  No forward signal date has a loaded row. Every sequence holds t=0.")
        for key in GRADED:
            print(f"  >>> {LABEL[key]}: {OPEN} <<<  (both cap cells)")
        empty = {seq_key(k, c, pop): run_sequence([])
                 for k in GRADED for c in CAPS for pop in ("PRIMARY", "SECONDARY")}
        append_look(look_record(stamps, 0, 0, empty,
                                {k: OPEN for k in GRADED}, None))
        print(f"\n  Look logged to {_rel(LOOK_LOG)}.")
        print(f"  REFUSED (designed, exit {EXIT_NO_FORWARD}): nothing to grade until "
              f"the exports hold a signal date on or after {FIRST_FORWARD_DATE}.")
        return EXIT_NO_FORWARD

    # ── gates on the forward book ────────────────────────────────────────
    picked = P.top_k_per_day(fwd, P.ladder_rank, k=st.max_per_day,
                             eligible_fn=P.ladder_eligible)
    if args.skip_gates:
        hdr("GATES G2-G5 — SKIPPED (--skip-gates); this run is not a result")
    else:
        res = AS.run_gates(fwd, picked, st, AS.new_cache())
        if not res["ok"]:
            print("\nGATE FAILURE (G2-G5) — no results printed. Exit 1.")
            return 1

    episodes = AS.dense_episodes(
        (d for d, _ in P.ordered_by_day(fwd, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    ep_dates = {d for ep in episodes for d in ep}
    pops = (("PRIMARY", ep_dates), ("SECONDARY", {r["date"] for r in fwd}))
    if not ep_dates:
        print("\n  PRIMARY is empty: no dense episode among the forward dates yet. "
              "Its sequences hold t=0.")

    cell_st = {k: NF.settings_for(st, kind, None) for k, _l, kind, _f, _g in CELLS}
    chain, evidence = Chain(), unlisted_evidence()
    narrower = Narrower(chain, evidence, NF._sim_cfg())
    cache = AS.new_cache()
    sims, b2s, b2caps = {}, {}, {}
    for pop, dates in pops:
        day_lists = P.ordered_by_day([r for r in fwd if r["date"] in dates],
                                     P.ladder_rank, P.ladder_eligible)
        for cap in CAPS:
            for key, label, _kind, floor, _g in CELLS:
                sims[(pop, cap, key)] = AS.simulate(
                    day_lists, NF.cfg_for(cell_st[key], label, floor, cap), cache=cache,
                    narrower=narrower if floor == "narrow" else None)
            b2s[(pop, cap)] = AS.simulate(
                day_lists, st.cfg("B2", compound=False, **AS.UNCONSTRAINED), cache=cache)
            for key in GRADED:
                floor = dict((k, f) for k, _l, _kd, f, _g in CELLS)[key]
                b2caps[(pop, cap, key)] = AS.simulate(
                    day_lists, cell_st[key].cfg(f"B2 {key}", compound=False, floor=floor,
                                                take_floor=(floor != "refuse"),
                                                **AS.UNCONSTRAINED),
                    cache=cache, narrower=narrower if floor == "narrow" else None)

    # ── sequences ────────────────────────────────────────────────────────
    seqs, stops = {}, {}
    for (pop, cap, key), sim in sims.items():
        if key not in GRADED:
            continue
        obs, stop, n_open = date_observations(sim.signal_pos)
        seqs[seq_key(key, cap, pop)] = run_sequence(obs)
        stops[seq_key(key, cap, pop)] = (stop, n_open)

    # ── FW2 FORWARD IDENTITY ─────────────────────────────────────────────
    hdr("FW2 FORWARD IDENTITY")
    early = sorted({d for s in seqs.values() for d in s["dates"] if d < FIRST_FORWARD_DATE})
    late = sorted({r["date"] for r in seen if r["date"] >= FIRST_FORWARD_DATE})
    fw2 = not early and not late
    print(f"  forward sequence dates before {FIRST_FORWARD_DATE}: {len(early)}; "
          f"seen-book dates on or after it: {len(late)}  -> {'PASS' if fw2 else 'FAIL'}")
    if not fw2:
        print("\nFW2 FAILED — no verdict printed. Exit 1.")
        return 1

    # ── GN5 COVERAGE on the forward F3 cell ──────────────────────────────
    hdr("GN5 COVERAGE — forward (R, F3, $500), narrow_to_fit's rule")
    c = sims[("PRIMARY", HEAD_NET_CAP, "F3")].census
    offered, unpriced = c["narrow_offered"], c["narrow_unpriced"]
    share = unpriced / offered if offered else 0.0
    gn5 = share > GN5_MAX_UNPRICED
    print(f"  over-budget PRIMARY picks offered {offered}  narrowed {c['narrowed']}  "
          f"no_fit {c['narrow_no_fit']}  tier_break {c['narrow_tier_break']}  "
          f"unpriced {unpriced} ({share:.0%}; bar {GN5_MAX_UNPRICED:.0%}) -> "
          f"{'FIRES — F3 prints AWAITING SCRAPE on this look' if gn5 else 'clear'}")
    if gn5:
        print("  The fix is `scripts/collector/fetch_substitute_legs.py --scope between`,"
              " never a lower bar.")

    # ── FW4 SEQUENCE CHECK ───────────────────────────────────────────────
    hdr("FW4 SEQUENCE CHECK — against the previous look in the log")
    fw4 = True
    for k in sorted(seqs):
        ok, lines = fw4_check(k, seqs[k], looks)
        fw4 = fw4 and ok
        print("\n".join(lines))
    print(f"  FW4: {'PASS' if fw4 else 'FAIL'}")

    # ── per cell: sequences, verdicts, context ───────────────────────────
    verdicts = {}
    for key in GRADED:
        hdr(f"{LABEL[key]} — the forward grade")
        line = CONFIRMED
        for cap in CAPS:
            sub(f"net {cap:.2f}x{' (registered)' if cap == HEAD_NET_CAP else ' (tracked)'}")
            dd = {pop: closed_drawdown(sims[(pop, cap, key)]) for pop, _ in pops}
            breach = any(abs(v) > DD_BAR * st.capital for v in dd.values())
            print(f"  realized-on-close maxDD, closed positions: PRIMARY ${dd['PRIMARY']:,.0f}"
                  f"  SECONDARY ${dd['SECONDARY']:,.0f}  (bar "
                  f"${DD_BAR * st.capital:,.0f})")
            for pop, _ in pops:
                k = seq_key(key, cap, pop)
                stop, n_open = stops[k]
                print_sequence(f"{pop} sequence", seqs[k])
                if stop:
                    print(f"    stops before {stop}: {n_open} position(s) still open")
            prim = seqs[seq_key(key, cap, "PRIMARY")]
            v = verdict(prim, breach, awaiting=(key == "F3" and gn5))
            if v == REFUTED_EDGE:
                v += (" — upper bound below zero" if prim["run_hi"] < 0
                      else " — upper bound between 0 and +0.10")
            if prim["empty"]:
                print("  CS EMPTY — the running intersection is empty; the "
                      "assumptions failed. Tell the operator.")
            if prim["start"] is None:
                print(f"  minimum counts not met ({MIN_DATES} dates and "
                      f"{MIN_POSITIONS} positions in PRIMARY)")
            verdicts[seq_key(key, cap, "PRIMARY")] = v
            print(f"  -> net {cap:.2f}x: {v}")
            line = worse(line, v.split(" — ")[0])
            print("  context, never graded:")
            print_context(key, cap, sims, b2s, b2caps, st)
        verdicts[key] = line
        print(f"\n  >>> {LABEL[key]}: {line} <<<")

    # ── controls ─────────────────────────────────────────────────────────
    hdr("CONTROLS — printed, not graded")
    print(NF.COLS)
    for pop, _ in pops:
        for cap in CAPS:
            for key, label, *_rest, graded in CELLS:
                NF.print_row(f"{pop[:3]} {cap:.2f} {label}", sims[(pop, cap, key)])

    # ── the seen book, context only ──────────────────────────────────────
    print_seen_book(seen, st, cell_st, narrower)

    # ── code changes since registration ──────────────────────────────────
    hdr("COMMITS SINCE REGISTRATION touching pricing, the loader, account_sim "
        "or narrow_to_fit")
    out = _git("log", "--oneline", f"{REGISTRATION_COMMIT}..HEAD", "--", *WATCHED_PATHS)
    print("\n".join(f"  {ln}" for ln in out.splitlines()) or "  none")

    append_look(look_record(stamps, len(fwd), len({r['date'] for r in fwd}), seqs,
                            verdicts, dict(offered=offered, unpriced=unpriced,
                                           fires=gn5)))
    hdr("CLOSE")
    for key in GRADED:
        print(f"  {LABEL[key]}: {verdicts[key]}")
    print(f"  gates: G2-G5 {'SKIPPED' if args.skip_gates else 'PASS'}  FW2 PASS  "
          f"FW4 {'PASS' if fw4 else 'FAIL'}  GN5 {'FIRES' if gn5 else 'clear'}")
    print(f"  look logged to {_rel(LOOK_LOG)}")
    print("  Nothing in this report is a shippable rule.")
    return 0 if fw4 else 1


def print_seen_book(seen: list, st: AS.Settings, cell_st: dict, narrower) -> None:
    """F2 and F3 on the dates before the first forward date — SEEN, context only."""
    hdr("SEEN — CONTEXT ONLY: the graded cells on dates before the first forward date")
    print("  account_sim's A1-A6 as registered, PRIMARY. Never enters a forward "
          "statistic,\n  interval or verdict.")
    if not seen:
        print("  no seen dates")
        return
    episodes = AS.dense_episodes(
        (d for d, _ in P.ordered_by_day(seen, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    ep = {d for e in episodes for d in e}
    day_lists = P.ordered_by_day([r for r in seen if r["date"] in ep],
                                 P.ladder_rank, P.ladder_eligible)
    cache = AS.new_cache()
    print(f"\n  {'cell':<30}{'n':>5}{'dates':>7}{'meanR':>9}   A1   A2   A3   A4   A5   A6")
    for cap in CAPS:
        b2 = AS.simulate(day_lists, st.cfg("B2", compound=False, **AS.UNCONSTRAINED),
                         cache=cache)
        for key in GRADED:
            floor = "refuse" if key == "F2" else "narrow"
            sim = AS.simulate(day_lists, NF.cfg_for(cell_st[key], LABEL[key], floor, cap),
                              cache=cache, narrower=narrower if floor == "narrow" else None)
            s = AS.criteria_scores(sim, b2, cell_st[key])
            flags = "".join(f"{'MET' if s[a] else 'no':>5}"
                            for a in ("A1", "A2", "A3", "A4", "A5", "A6"))
            print(f"  {LABEL[key] + f' net {cap:.2f}':<30}{len(sim.signal_pos):>5}"
                  f"{len(sim.dates):>7}{fmt(s['mean_R']):>9}{flags}")


if __name__ == "__main__":
    raise SystemExit(main())
