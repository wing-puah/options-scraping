"""ruin_bound — which cap cell earns the most while ruin stays under a stated bound?

Registration: `research/pre-registrations/f4_deployment/ruin_bound.md`,
accepted by default 2026-10-09 on the drafter's recommended defaults. That file
is the spec; this module implements it and adds nothing to its bar. RESEARCH
TIER: the result is a reading for the operator and changes no tracked cap.

24 CONFIGURATIONS: six cap cells (net cap 1.00 / 1.50 / 2.50 x F1 / F2, the
per-position cap fixed at 0.25) x four guardrails (none, G-M max open risk,
G-K kill switch, G-C circuit breaker), all under `account_sim` ARM R. Each is
walked on 5,000 stationary-block-bootstrap paths of the session series, under
four overlays (O0 none, O1 correlated gap, O2 total loss, O3 live density),
at three block lengths, on PRIMARY and SECONDARY, at two budgets: the
registered $500 (HEADLINE) and the operator's $1,000 (DECLARED SECONDARY).

The walk is `lib/ruin_walk.py`, a vectorised second copy of `simulate()`'s
ARM R loop. Gate R2 holds it equal to `simulate()` on the realized walk of
every cell; `simulate()` itself is not changed. Positions are sized and
replayed by `account_sim.replay_sized` (the frozen harness) and marked by
`mtm_curve.position_marks`; both are imported, never mirrored.

HOLDOUT SEAL. The study reads signal dates before the seal (2026-09-23) only.
It loads through `load_book()` and drops any sealed row itself as well, so a
book exported later cannot bring a sealed date in.

Usage:
  python3 -m scripts.backtest_study run ruin_bound
  python3 -m scripts.backtest_study.f4_deployment.ruin_bound [--workers N]
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f4_deployment import account_sim as AS  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import forward_drawdown as FD  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as MC  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import ruin_walk as RW  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# Era refusals from `load_book` (exit 2 thin era, exit 3 wrong era) are the
# study's correct status, not failures.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

hdr, sub = AS.hdr, AS.sub

# ── registered constants (Resolved at build 2026-10-09) ─────────────────────

SEED = 20261009
N_PATHS = 5000
X_RUIN = 0.50
P_RUIN = 0.01
P_RUIN_STRESS = 0.05
D95 = 0.30
D99 = 0.45
R_MAX = 0.60
G_GAP = 0.10
M_OPEN = 0.50
K_KILL = 0.25
C_SHOCK = 0.05
B_PAUSE = 5
L_FLOOR = 20
L_STEP = 5
MIN_BLOCKS = 8
PER_POS_CAP = 0.25
HIGH_BUDGET = 1000.0
#: The holdout seal's first sealed signal date. `era.SEAL_START` once the seal
#: code is on the branch; the literal is the registered date until then.
SEAL_START = str(getattr(era, "SEAL_START", "2026-09-23"))[:10]

CELLS = (("N100-F1", 1.00, True), ("N150-F1", 1.50, True), ("N250-F1", 2.50, True),
         ("N100-F2", 1.00, False), ("N150-F2", 1.50, False), ("N250-F2", 2.50, False))
GUARDS = ("none", "M", "K", "C")
GUARD_LABEL = {"none": "G-none", "M": "G-M", "K": "G-K", "C": "G-C"}
#: The cell the p75 holding period is read from (registered headline cell).
L_SOURCE = "N150-F1 G-none"
BUDGETS = (("HEADLINE", "$500 budget and stop", None),
           ("DECLARED SECONDARY", "$1,000 budget and stop", HIGH_BUDGET))
POPS = ("PRIMARY", "SECONDARY")
OVERLAYS = ("O0", "O1", "O2", "O3")

V_RISKIER = "RISKIER CELL EARNS ITS DRAWDOWN: "
V_SAFEST = "SAFEST ELIGIBLE CELL: "
V_NONE = "NO CELL MEETS THE BOUNDS"
V_UNDER = "UNDERPOWERED"

log = logging.getLogger("ruin_bound")


def configs() -> list[RW.WalkCfg]:
    """The 24 configurations, cell-major, in the registration's arms order."""
    return [RW.WalkCfg(label=f"{cell} {GUARD_LABEL[g]}", net_cap=net, take_floor=f1,
                       guard=g, m=M_OPEN, k=K_KILL, c=C_SHOCK, b=B_PAUSE,
                       ruin_frac=X_RUIN)
            for cell, net, f1 in CELLS for g in GUARDS]


def seal(recs: list[dict]) -> tuple[list[dict], int]:
    """Drop every row on a sealed signal date. Returns `(kept, n_dropped)`."""
    kept = [r for r in recs if str(r["date"])[:10] < SEAL_START]
    return kept, len(recs) - len(kept)


def settings_for(st: AS.Settings, budget: float | None) -> AS.Settings:
    """The account at one budget; the stop is the budget (no `dollar_stop`)."""
    if budget is None:
        return dataclasses.replace(st, dollar_stop=None)
    return dataclasses.replace(st, risk_pct=budget / st.capital, dollar_stop=None)


def as_cfg(st_b: AS.Settings, wc: RW.WalkCfg) -> AS.Cfg:
    return st_b.cfg(wc.label, net_cap=wc.net_cap, take_floor=wc.take_floor,
                    compound=False)


def block_lengths(p75: float) -> tuple[int, int, int]:
    """(primary, half, one-and-a-half), each rounded UP to a multiple of 5."""
    def up5(x: float) -> int:
        return int(math.ceil(x / L_STEP - 1e-12) * L_STEP)
    primary = max(L_FLOOR, up5(p75))
    return primary, up5(primary / 2), up5(primary * 1.5)


def weekdays(a: date, b: date) -> list[date]:
    out, d = [], a
    while d <= b:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


# ════════════════════════════════════════════════════════════════════════════
# The candidate table
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Built:
    """A `ruin_walk.Table` plus what the report needs to read positions back."""
    table: RW.Table
    recs: list
    contracts: list
    replays: list
    gross: np.ndarray
    cost: np.ndarray
    has_cost: list
    series: list
    day_lists: list


def build(pop_recs: list[dict], st_b: AS.Settings, cache: dict,
          charge_cost: bool = True) -> Built:
    """Size, replay and mark every ladder-eligible candidate of a population.

    The session series is every weekday on which some sizable candidate could
    be open, entry to replayed exit (registration, Horizon H). Marks are
    `position_marks` carried onto that series; with `charge_cost` the exit
    mark and the booked dollars are charged the row's `cost_total` per
    contract times the sized contracts.
    """
    day_lists = P.ordered_by_day(pop_recs, P.ladder_rank, P.ladder_eligible)
    budget, stop = st_b.budget, st_b.stop
    items = []
    for _d, ranked in day_lists:
        for rec in ranked:
            c = AS.risk_contracts(rec["max_loss_per_contract"], budget)
            if c is None:
                items.append(dict(rec=rec, c=None))
                continue
            rp = AS.replay_sized(rec, c, stop, cache=cache)
            grid = rec["t"].grid
            dh = rp["days_held"]
            sess, marks, _ = MC.position_marks(SimpleNamespace(rec=rec, contracts=c,
                                                               days_held=dh))
            items.append(dict(rec=rec, c=c, rp=rp, entry=grid[0],
                              exit=grid[min(dh, len(grid)) - 1],
                              mark_by=dict(zip(sess, marks))))
    days: set = set()
    for it in items:
        if it["c"] is not None:
            days.update(weekdays(it["entry"], it["exit"]))
    series = sorted(days)
    idx = {s: i for i, s in enumerate(series)}
    n = len(series)
    C = len(items)
    K = max((len(r) for _d, r in day_lists), default=1)
    cand = np.full((n, K), -1, dtype=np.int64)
    reserved = np.zeros(C)
    dn = np.zeros(C)
    dollars = np.zeros(C)
    gross = np.zeros(C)
    cost = np.zeros(C)
    kk = np.zeros(C, dtype=np.int64)
    entry = np.zeros(C, dtype=np.int64)
    unsizable = np.zeros(C, dtype=bool)
    over_budget = np.zeros(C, dtype=bool)
    pp_bad = np.zeros(C, dtype=bool)
    has_cost = [False] * C
    rows: list[list[float]] = []
    i_item = 0
    for _d, ranked in day_lists:
        e0 = ranked[0]["t"].grid[0]
        for j, _rec in enumerate(ranked):
            it = items[i_item]
            cid = i_item
            i_item += 1
            if e0 in idx:
                cand[idx[e0], j] = cid
                entry[cid] = idx[e0]
            if it["c"] is None:
                unsizable[cid] = True
                rows.append([0.0])
                continue
            rec, c, rp = it["rec"], it["c"], it["rp"]
            mlpc = rec["max_loss_per_contract"]
            dn[cid] = AS.signed_dn(rec, c)
            over_budget[cid] = mlpc > budget
            pp_bad[cid] = abs(dn[cid]) > st_b.per_pos_cap * st_b.capital + AS.EPS
            row_cost = MC.row_cost(rec)
            row_c = int(float(rec["t"].row.get("contracts") or 0) or 0)
            has_cost[cid] = (row_cost is not None
                             and bool((rec["t"].row.get("cost_basis") or "").strip()))
            if charge_cost and row_cost is not None and row_c > 0:
                cost[cid] = row_cost / row_c * c
            # The reserve is the most the position can cost: its max loss, plus
            # its commission on the net basis (Resolved at build, gate R3).
            reserved[cid] = mlpc * c + cost[cid]
            k = idx[it["exit"]] - idx[it["entry"]]
            kk[cid] = k
            gross[cid] = rp["dollars"]
            dollars[cid] = rp["dollars"] - cost[cid]
            last, mk = 0.0, []
            for o in range(k + 1):
                s = series[idx[it["entry"]] + o]
                last = it["mark_by"].get(s, last)
                mk.append(last)
            mk[-1] -= cost[cid]
            rows.append(mk)
    W = max(len(r) for r in rows) if rows else 1
    marks = np.zeros((C + 1, W))
    for cid, mk in enumerate(rows):
        marks[cid, :len(mk)] = mk
        marks[cid, len(mk):] = mk[-1]
    tab = RW.Table(n=n, cand=cand, reserved=reserved, dn=dn, dollars=dollars, k=kk,
                   entry=entry, unsizable=unsizable, over_budget=over_budget,
                   pp_bad=pp_bad, marks=marks, capital=st_b.capital,
                   max_per_day=st_b.max_per_day)
    return Built(table=tab, recs=[it["rec"] for it in items],
                 contracts=[it["c"] for it in items],
                 replays=[it.get("rp") for it in items], gross=gross, cost=cost,
                 has_cost=has_cost, series=series, day_lists=day_lists)


def identity(b: Built, wc: RW.WalkCfg) -> RW.Result:
    """The realized walk: the series itself, in order."""
    return RW.walk(b.table, np.arange(b.table.n)[None, :], wc, record=True)


def positions(b: Built, res: RW.Result) -> list[AS.Pos]:
    """The realized walk's positions as `account_sim.Pos`, booked GROSS (the
    replay's own dollars), so A1 and R2 read them as `simulate()` would."""
    out = []
    for _p, _t, cid in res.decisions:
        rec, c, rp = b.recs[cid], b.contracts[cid], b.replays[cid]
        grid = rec["t"].grid
        out.append(AS.Pos(rec=rec, contracts=c, reserved=b.table.reserved[cid],
                          dn=b.table.dn[cid], entry_sess=grid[0],
                          exit_sess=grid[min(rp["days_held"], len(grid)) - 1],
                          days_held=rp["days_held"], R=rp["R"], dollars=rp["dollars"],
                          exit_reason=rp["exit_reason"]))
    return out


def sim_of(st_b: AS.Settings, wc: RW.WalkCfg, pos: list[AS.Pos]) -> AS.Sim:
    sim = AS.Sim(cfg=as_cfg(st_b, wc), taken=list(pos))
    sim.ledger = AS.Ledger(st_b.capital)
    return sim


def signature(pos) -> list[tuple]:
    return sorted((id(p.rec), int(p.contracts), round(float(p.dollars), 6), p.exit_reason)
                  for p in pos)


def perturbed(tab: RW.Table, cut: int, pad: int = 3) -> RW.Table:
    """`tab` with every outcome after session `cut` scrambled (R4 truncation).

    Marks on sessions at or after `cut` become garbage; a position exiting at
    or after `cut` exits `pad` sessions later and books a different figure.
    Nothing a decision at or before `cut` may read is touched.
    """
    C = tab.n_cand
    W = tab.marks.shape[1] + pad
    marks = np.zeros((C + 1, W))
    marks[:, :tab.marks.shape[1]] = tab.marks
    k = tab.k.copy()
    dollars = tab.dollars.copy()
    for cid in range(C):
        e = tab.entry[cid]
        for o in range(W):
            if e + o >= cut:
                marks[cid, o] = -0.9 * tab.reserved[cid] - 7.0 - o
        if e + k[cid] >= cut:
            k[cid] += pad
            dollars[cid] = -0.8 * tab.reserved[cid] - 3.0
    return dataclasses.replace(tab, marks=marks, k=k, dollars=dollars)


# ════════════════════════════════════════════════════════════════════════════
# Worker processes
# ════════════════════════════════════════════════════════════════════════════

_TABLES: dict = {}


def _init(tables: dict) -> None:
    _TABLES.update(tables)


def _task(args: tuple) -> tuple:
    key, L, wc, n_paths = args
    names = [name for name, _l, _b in BUDGETS]
    stream = (names.index(key[0]), POPS.index(key[1]), int(L))
    out = RW.run_task(_TABLES[key], wc, L, n_paths, SEED, stream, G_GAP)
    return key, L, wc.label, out


# ════════════════════════════════════════════════════════════════════════════
# Printing helpers
# ════════════════════════════════════════════════════════════════════════════

def pct(x: float) -> str:
    return "  n/a" if x != x else f"{100 * x:5.1f}%"


def money(x: float) -> str:
    return "n/a" if x != x else f"${x:+,.0f}"


def ci_str(ci: tuple) -> str:
    return f"[{100 * ci[0]:.1f}, {100 * ci[1]:.1f}]"


# ════════════════════════════════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:  # noqa: C901 — one linear report, gate by gate
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                    help="worker processes for the resample (default: cores - 1)")
    ap.add_argument("--paths", type=int, default=N_PATHS,
                    help=f"paths per configuration (registered: {N_PATHS}); any "
                         f"other value is a smoke run and prints no verdict")
    args = ap.parse_args(argv)
    logging.getLogger("backtest").setLevel(logging.ERROR)
    smoke = args.paths != N_PATHS
    t0 = time.time()

    st = AS.load_settings(AS.DEFAULT_CONFIG)
    if abs(st.per_pos_cap - PER_POS_CAP) > 1e-9:
        print(f"REFUSED — config per-position cap {st.per_pos_cap} is not the "
              f"registered {PER_POS_CAP}")
        return 2
    assert abs(HIGH_BUDGET - AS.MAX_LOSS_ABS) < 1e-9, "HIGH_BUDGET must be MAX_LOSS_ABS"

    hdr("ruin_bound — which cap cell earns the most while ruin stays under a stated bound?")
    print(f"""  Registration research/pre-registrations/f4_deployment/ruin_bound.md
  (accepted by default 2026-10-09 on the drafter's recommended defaults).
  A READING FOR THE OPERATOR: no tracked cap, config or production rule moves.
  A resample recombines one history. It shows how bad the ORDER of this
  history could have been, not how bad a different market could be; the tail
  beyond the sample comes only from the overlays, which are assumptions.
  No annualised figure, Sharpe or time-to-recover is printed.
  Seed {SEED}. Paths per configuration {args.paths}{'  (SMOKE RUN — no verdict)' if smoke else ''}.""")

    # ── R0 era + the seal ────────────────────────────────────────────────
    recs, diag = load_book(include_bs=False)
    recs, n_sealed = seal(recs)
    print(f"  era {diag.get('era')}  book {len(recs)} rows  {diag.get('n_dates')} dates  "
          f"{diag.get('date_range')}")
    print(f"  SEAL: this study read no signal date on or after {SEAL_START}; "
          f"{n_sealed} rows dropped here (load_book's own withholding is separate).")
    print("  R0 ERA: PASS (load_book resolved and checked the era)")
    AS.print_configuration(st, AS.DEFAULT_CONFIG)

    episodes = AS.dense_episodes(
        (d for d, _ in P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    ep_dates = {d for ep in episodes for d in ep}
    all_dates = {r["date"] for r in recs}
    refusal = AS.primary_refusal(all_dates, ep_dates, st)
    if refusal:
        print(f"\nREFUSED — {refusal}")
        return era.EXIT_THIN_ERA
    pop_dates = {"PRIMARY": ep_dates, "SECONDARY": all_dates}
    cfgs = configs()
    st_b = {name: settings_for(st, b) for name, _l, b in BUDGETS}
    picked = P.top_k_per_day(recs, P.ladder_rank, k=st.max_per_day,
                             eligible_fn=P.ladder_eligible)

    # ── R4 part 1: account_sim's G2-G5 on both budget bases ─────────────
    gates_ok = True
    for name, label, _b in BUDGETS:
        print(f"\n######## account_sim gates on the {label} basis ({name}) ########")
        res = AS.run_gates(recs, picked, st_b[name], AS.new_cache())
        gates_ok = gates_ok and res["ok"]
    if not gates_ok:
        print("\nGATE FAILURE (account_sim G2-G5, part of R4) — no verdict. Exit 1.")
        return 1

    # ── tables ───────────────────────────────────────────────────────────
    cache = AS.new_cache()
    built: dict[tuple, Built] = {}
    gross_built: dict[tuple, Built] = {}
    hdr("POPULATION AND SESSION SERIES (counts only)")
    print(f"  PRIMARY: {len(episodes)} dense episodes, {len(ep_dates)} signal dates.  "
          f"SECONDARY: {len(all_dates)} signal dates.")
    for name, label, _b in BUDGETS:
        for pop in POPS:
            pr = [r for r in recs if r["date"] in pop_dates[pop]]
            built[(name, pop)] = build(pr, st_b[name], cache, charge_cost=True)
            gross_built[(name, pop)] = build(pr, st_b[name], cache, charge_cost=False)
            b = built[(name, pop)]
            n_cand = b.table.n_cand
            print(f"  {name:<18} {pop:<9}  sessions H = {b.table.n:4d} "
                  f"({b.series[0]} -> {b.series[-1]})  signal sessions "
                  f"{len(b.table.signal_sessions()):3d}  candidates {n_cand}  "
                  f"unsizable {int(b.table.unsizable.sum())}")

    # ── realized walks (identity) for every configuration ───────────────
    ident: dict[tuple, RW.Result] = {}
    for key, b in built.items():
        for wc in cfgs:
            ident[(*key, wc.label)] = identity(b, wc)

    # ── R1 cost coverage ─────────────────────────────────────────────────
    hdr("R1 COST COVERAGE — every taken position on every realized walk")
    r1_ok = True
    for key, b in built.items():
        taken_ids = {cid for wc in cfgs for _p, _t, cid in ident[(*key, wc.label)].decisions}
        n_cov = sum(1 for cid in taken_ids if b.has_cost[cid])
        ok = n_cov == len(taken_ids)
        r1_ok &= ok
        print(f"  {key[0]:<18} {key[1]:<9}  distinct taken positions {len(taken_ids):4d}  "
              f"carrying cost_total + cost_basis {n_cov:4d}  -> {'PASS' if ok else 'FAIL'}")
    print(f"  R1: {'PASS' if r1_ok else 'FAIL'}")

    # ── block length (printed before any result) ─────────────────────────
    hdr("BLOCK LENGTH — read before any outcome figure is printed")
    src = ident[("HEADLINE", "PRIMARY", L_SOURCE)]
    held = [b.replays[cid]["days_held"] for b in [built[("HEADLINE", "PRIMARY")]]
            for _p, _t, cid in src.decisions]
    p75 = FD.pctile(held, 75)
    L_primary, L_half, L_more = block_lengths(p75)
    Ls = (L_primary, L_half, L_more)
    print(f"  p75 of held sessions, {L_SOURCE}, PRIMARY, HEADLINE: {p75:.1f} "
          f"({len(held)} positions)")
    print(f"  primary L = max({L_FLOOR}, p75 rounded up to a multiple of {L_STEP}) = "
          f"{L_primary}; sensitivity L = {L_half} and {L_more}")
    readable: dict[tuple, bool] = {}
    for key, b in built.items():
        cells = []
        for L in Ls:
            ok = b.table.n / L >= MIN_BLOCKS
            readable[(*key, L)] = ok
            cells.append(f"L={L}: H/L={b.table.n / L:5.1f} "
                         f"{'read' if ok else 'TOO FEW BLOCKS, not read'}")
        print(f"  {key[0]:<18} {key[1]:<9}  " + "   ".join(cells))

    # ── reserved over equity, the realized walk (G-M's context) ─────────
    hdr("RESERVED CAPITAL OVER MARKED EQUITY — realized walks, no guardrail")
    print("  Sessions with at least one open position. G-M's m = 0.50 binds above it.")
    for key in built:
        for cell, _n, _f in CELLS:
            r = ident[(*key, f"{cell} G-none")]
            ratio = [rv / ev for rv, ev in zip(r.reserved, r.equity) if rv > 0]
            print(f"  {key[0]:<18} {key[1]:<9} {cell}:  median {FD.pctile(ratio, 50):.2f}  "
                  f"p90 {FD.pctile(ratio, 90):.2f}  share above 0.50 "
                  f"{pct(sum(1 for x in ratio if x > M_OPEN) / len(ratio)) if ratio else 'n/a'}")

    # ── R2 identity against simulate() ──────────────────────────────────
    hdr("R2 IDENTITY — the walk at L = series length vs account_sim.simulate()")
    print("  Gross basis (simulate() books gross). Positions are (row, contracts,\n"
          "  dollars, exit reason); marked max drawdown may differ by one cent per\n"
          "  contract, the daily_pnl_csv write resolution.")
    r2_ok = True
    for name, _l, _b in BUDGETS:
        for pop in POPS:
            gb = gross_built[(name, pop)]
            for cell, net, f1 in CELLS:
                wc = RW.WalkCfg(label=f"{cell} G-none", net_cap=net, take_floor=f1,
                                ruin_frac=X_RUIN)
                mine = identity(gb, wc)
                mpos = positions(gb, mine)
                sim = AS.simulate(gb.day_lists, as_cfg(st_b[name], wc), cache=cache)
                same = signature(mpos) == signature(sim.signal_pos)
                _, vals = AS.equity_curve(sim.signal_pos)
                rdd = -AS.max_drawdown(vals) / st.capital
                bc = MC.book_curves(sim.signal_pos, target=MC.TARGET_POSITION)
                mdd = -MC.max_drawdown(bc.mtm.daily) / st.capital
                tol = 0.01 * max(1, sum(p.contracts for p in sim.signal_pos)) / st.capital
                ok = (same and abs(rdd - mine.rmaxdd[0]) < 1e-9
                      and abs(mdd - mine.maxdd[0]) <= tol)
                r2_ok &= ok
                print(f"  {name:<18} {pop:<9} {cell}: positions {len(mpos)} vs "
                      f"{len(sim.signal_pos)} {'same' if same else 'DIFFERENT'}  "
                      f"realized DD diff {abs(rdd - mine.rmaxdd[0]):.2e}  marked DD diff "
                      f"{abs(mdd - mine.maxdd[0]):.2e}  -> {'PASS' if ok else 'FAIL'}")
    print(f"  R2: {'PASS' if r2_ok else 'FAIL'}")

    # ── R4 part 2: truncation blindness of the new code ─────────────────
    hdr("R4 TRUNCATION — outcomes after a cut scrambled; decisions up to it unchanged")
    r4_ok = True
    n_checks = 0
    for key, b in built.items():
        n = b.table.n
        cuts = sorted({int(n * f) for f in (0.1, 0.25, 0.4, 0.55, 0.7, 0.85)})
        bad = []
        for wc in cfgs:
            base = ident[(*key, wc.label)].decisions
            for cut in cuts:
                pert = RW.walk(perturbed(b.table, cut), np.arange(n)[None, :], wc,
                               record=True).decisions
                n_checks += 1
                if [d for d in base if d[1] <= cut] != [d for d in pert if d[1] <= cut]:
                    bad.append((wc.label, cut))
        r4_ok &= not bad
        print(f"  {key[0]:<18} {key[1]:<9}  {len(cfgs)} configurations x {len(cuts)} cuts: "
              f"{'all identical' if not bad else f'{len(bad)} DIFFER, e.g. {bad[:3]}'}")
    print(f"  R4 (G2-G5 above + {n_checks} truncation checks): {'PASS' if r4_ok else 'FAIL'}")

    # ── the realized walk, the anchor ───────────────────────────────────
    b2s = {key: AS.simulate(b.day_lists, st_b[key[0]].cfg("B2", compound=False,
                                                          **AS.UNCONSTRAINED), cache=cache)
           for key, b in gross_built.items()}
    a1: dict[tuple, bool] = {}
    hdr("THE REALIZED WALK — every configuration, net of cost, before any resample")
    print("  Positions, net dollars, marked and realized max drawdown (fraction of\n"
          "  starting capital), ruined (marked equity at or below half), A1 on the\n"
          "  gross replay R as account_sim scores it.")
    for key, b in built.items():
        sub(f"{key[0]} ({dict((n, l) for n, l, _ in BUDGETS)[key[0]]}) — {key[1]}")
        print(f"  {'configuration':<18} {'pos':>4} {'net $':>10} {'MTM DD':>7} "
              f"{'real DD':>7} {'ruined':>6}  A1")
        for wc in cfgs:
            r = ident[(*key, wc.label)]
            s = AS.criteria_scores(sim_of(st_b[key[0]], wc, positions(b, r)),
                                   b2s[key], st_b[key[0]])
            a1[(*key, wc.label)] = bool(s["A1"])
            print(f"  {wc.label:<18} {int(r.taken[0]):4d} {money(float(r.dollars[0])):>10} "
                  f"{pct(float(r.maxdd[0])):>7} {pct(float(r.rmaxdd[0])):>7} "
                  f"{'yes' if r.ruined[0] else 'no':>6}  "
                  f"{'MET' if s['A1'] else 'NOT MET'} (meanR {s['mean_R']:+.3f}, "
                  f"CI [{s['lo']:+.3f}, {s['hi']:+.3f}])")

    gates_pre = r1_ok and r2_ok and r4_ok
    if not gates_pre:
        print("\nGATE FAILURE (R1, R2 or R4) — the resample is not run and no verdict "
              "prints. Exit 1.")
        return 1

    # ── the resample ─────────────────────────────────────────────────────
    hdr("THE RESAMPLE")
    tasks = [(key, L, wc, args.paths) for key in built for L in Ls for wc in cfgs]
    print(f"  {len(tasks)} tasks (configuration x L x population x budget), each O0, O1,\n"
          f"  O2 and O3 on {args.paths} paths; {args.workers} worker processes.")
    tables = {key: b.table for key, b in built.items()}
    out: dict[tuple, dict] = {}
    t1 = time.time()
    if args.workers <= 1:
        _init(tables)
        for tk in tasks:
            k_, L_, lab, o = _task(tk)
            out[(*k_, L_, lab)] = o
    else:
        with ProcessPoolExecutor(max_workers=args.workers, initializer=_init,
                                 initargs=(tables,)) as ex:
            for k_, L_, lab, o in ex.map(_task, tasks, chunksize=1):
                out[(*k_, L_, lab)] = o
    print(f"  done in {time.time() - t1:,.0f}s")

    # ── R3 ledger, R5 overlay order ──────────────────────────────────────
    hdr("R3 LEDGER / R5 OVERLAY ORDER")
    worst = max(o[ov]["ledger_err"] for o in out.values() for ov in OVERLAYS)
    negc = sum(o[ov]["neg_cash"] for o in out.values() for ov in OVERLAYS)
    r3_ok = worst <= 1e-6 and negc == 0
    print(f"  R3: worst |cash + reserved - capital - realized| ${worst:.2e}; sessions "
          f"with negative cash (margin-call proxy) {negc} -> {'PASS' if r3_ok else 'FAIL'}")
    n_paths = sum(o["R5"]["paths"] for o in out.values())
    ruin_bad = sum(o["R5"]["ruin_bad"] for o in out.values())
    eq_bad = sum(o["R5"]["eq_bad"] for o in out.values())
    r5_ok = ruin_bad == 0 and eq_bad == 0
    print(f"  R5 (path by path, up to the shock; Resolved at build 2026-10-09): "
          f"{n_paths:,} shocked paths;\n      equity at the shock out of order "
          f"(O2 <= O1 <= O0) on {eq_bad}; ruin by the shock out of order on "
          f"{ruin_bad} -> {'PASS' if r5_ok else 'FAIL'}")
    full = [k for k, o in out.items()
            if not (o["O2"]["p_ruin"] >= o["O1"]["p_ruin"] >= o["O0"]["p_ruin"])]
    print(f"  Disclosure, not the gate: the full-H share order O2 >= O1 >= O0 holds "
          f"in {len(out) - len(full)} of {len(out)} cells.")
    for k in full[:12]:
        o = out[k]
        print(f"    out of order {k}: O0 {o['O0']['p_ruin']:.4f}  O1 {o['O1']['p_ruin']:.4f}"
              f"  O2 {o['O2']['p_ruin']:.4f}")
    if not (r3_ok and r5_ok):
        print("\nGATE FAILURE (R3 or R5) — no verdict. Exit 1.")
        return 1

    # ── the full table ───────────────────────────────────────────────────
    hdr("THE FULL TABLE — printed, never used to pick a configuration by eye")
    print("  P(ruin) with its Wilson 95% interval; marked max drawdown percentiles;\n"
          "  dollars over H realized on close (p50, p5); O2 p99 loss of equity;\n"
          "  taken positions (median); share of paths where the guardrail acted.")
    for key in built:
        for L in Ls:
            tag = "" if readable[(*key, L)] else "   (TOO FEW BLOCKS — printed, not read)"
            sub(f"{key[0]} — {key[1]} — L = {L}{tag}")
            print(f"  {'configuration':<16} {'O0 ruin':>7} {'95% CI':>13} {'O1':>6} "
                  f"{'O2':>6} {'O3':>6} {'DD p50':>6} {'p95':>6} {'p99':>6} "
                  f"{'$ p50':>9} {'$ p5':>9} {'O2 p99':>6} {'pos':>4} {'fired':>6}")
            for wc in cfgs:
                o = out[(*key, L, wc.label)]
                z = o["O0"]
                print(f"  {wc.label:<16} {pct(z['p_ruin']):>7} {ci_str(z['ci']):>13} "
                      f"{pct(o['O1']['p_ruin']):>6} {pct(o['O2']['p_ruin']):>6} "
                      f"{pct(o['O3']['p_ruin']):>6} {pct(z['dd50']):>6} {pct(z['dd95']):>6} "
                      f"{pct(z['dd99']):>6} {money(z['dol50']):>9} {money(z['dol5']):>9} "
                      f"{pct(o['O2']['o2_99']):>6} {z['taken50']:4.0f} "
                      f"{pct(z['fired']) if wc.guard != 'none' else '    —':>6}")

    # ── eligibility and the decision rule, per budget ────────────────────
    verdicts = {}
    for name, label, _b in BUDGETS:
        hdr(f"BAR FOR A CANDIDATE — {name} ({label})")
        print(f"  B1 O0 ruin <= {P_RUIN}; B2 O1 and O3 ruin <= {P_RUIN_STRESS}; "
              f"B3 O0 p95 DD <= {D95}; B4 O0 p99 DD <= {D99};\n  B5 O2 p99 loss <= "
              f"{R_MAX}; B6 A1 on the realized walk. Every readable L, both populations.")
        eligible = []
        print(f"  {'configuration':<16}  B1  B2  B3  B4  B5  B6   eligible")
        for wc in cfgs:
            flags = {c: True for c in ("B1", "B2", "B3", "B4", "B5", "B6")}
            for pop in POPS:
                flags["B6"] &= a1[(name, pop, wc.label)]
                for L in Ls:
                    if not readable[(name, pop, L)]:
                        continue
                    o = out[(name, pop, L, wc.label)]
                    flags["B1"] &= o["O0"]["p_ruin"] <= P_RUIN
                    flags["B2"] &= (o["O1"]["p_ruin"] <= P_RUIN_STRESS
                                    and o["O3"]["p_ruin"] <= P_RUIN_STRESS)
                    flags["B3"] &= o["O0"]["dd95"] <= D95
                    flags["B4"] &= o["O0"]["dd99"] <= D99
                    o2 = o["O2"]["o2_99"]
                    flags["B5"] &= (o2 != o2) or o2 <= R_MAX
            ok = all(flags.values())
            if ok:
                eligible.append(wc)
            print(f"  {wc.label:<16}  " + "  ".join("ok" if flags[c] else "--"
                                                    for c in sorted(flags))
                  + f"   {'ELIGIBLE' if ok else 'no'}")
        verdicts[name] = decide(name, eligible, built, ident, out, readable, L_primary)

    # ── disclosures ──────────────────────────────────────────────────────
    hdr("DISCLOSURES — scored by nothing")
    sub("Ruin without G-K firing (O0, every L)")
    for key in built:
        for wc in cfgs:
            if wc.guard != "K":
                continue
            line = "  ".join(f"L={L}: {out[(*key, L, wc.label)]['O0']['ruin_unfired']} of "
                             f"{out[(*key, L, wc.label)]['O0']['n_ruin']}" for L in Ls)
            print(f"  {key[0]:<18} {key[1]:<9} {wc.label:<16} {line}")
    sub("Paths where reserved capital exceeded MARKED equity on some session (O0, primary L)")
    print("  Not a ledger fault: open positions marked below their reserve do this.")
    for key in built:
        vals = [out[(*key, L_primary, wc.label)]["O0"]["over_share"] for wc in cfgs]
        print(f"  {key[0]:<18} {key[1]:<9} share of paths, across configurations: "
              f"{pct(min(vals))} to {pct(max(vals))}")

    if any(v.startswith(V_NONE) for v in verdicts.values()):
        hdr("CAPITAL — where a NO CELL answer points (the capital adequacy census)")
        for pop in POPS:
            b = built[("HEADLINE", pop)]
            pop_rows = [r for r in recs if r["date"] in pop_dates[pop]]
            AS.print_capital_adequacy(pop_rows, b.day_lists, pop, st, diag)

    control_v3(st_b, cfgs)

    hdr("VERDICT")
    if smoke:
        print(f"  SMOKE RUN ({args.paths} paths, not {N_PATHS}) — no verdict printed.")
    else:
        print(f"  HEADLINE ($500 budget and stop): >>> {verdicts['HEADLINE']} <<<")
        print(f"  DECLARED SECONDARY ($1,000 budget and stop): "
              f"{verdicts['DECLARED SECONDARY']}")
        print("  A reading for the operator. The tracked cap in config/account-sim.yml\n"
              "  is unchanged whatever these lines say.")
    print(f"\n  run time {time.time() - t0:,.0f}s")
    return 0


def decide(name: str, eligible: list, built: dict, ident: dict, out: dict,
           readable: dict, L_primary: int) -> str:
    """The registered decision rule on one budget. Prints its steps."""
    sub(f"DECISION RULE — {name}")
    if not readable[(name, "PRIMARY", L_primary)]:
        print(f"  H / L < {MIN_BLOCKS} at the primary L on PRIMARY.")
        return V_UNDER
    if not eligible:
        print("  No configuration is eligible.")
        return V_NONE

    def p95(wc):
        return out[(name, "PRIMARY", L_primary, wc.label)]["O0"]["dd95"]
    s = min(eligible, key=p95)          # min() keeps the first of equal keys
    print(f"  Step 1: S = {s.label} (p95 marked DD {pct(p95(s))} under O0, primary L, PRIMARY)")
    b = built[(name, "PRIMARY")]
    dates = sorted({str(rec["date"]) for _d, ranked in b.day_lists for rec in ranked})

    def per_date(wc):
        acc = {d: 0.0 for d in dates}
        for _p, _t, cid in ident[(name, "PRIMARY", wc.label)].decisions:
            acc[str(b.recs[cid]["date"])] += float(b.table.dollars[cid])
        return acc
    base = per_date(s)
    winners = []
    for wc in eligible:
        if wc is s or not p95(wc) > p95(s):
            continue
        mine = per_date(wc)
        rows = [dict(date=d, a=mine[d], b=base[d]) for d in dates]
        lo, hi = P.boot_ci_paired_by_date(rows, "a", "b")
        diff = sum(mine.values()) - sum(base.values())
        passed = lo > 0
        print(f"  Step 2: {wc.label} vs S: per-date advantage CI [{lo:+.1f}, {hi:+.1f}] "
              f"$/date, total {money(diff)} -> {'PASSES' if passed else 'does not pass'}")
        if passed:
            winners.append(wc)
    if not winners:
        return V_SAFEST + s.label

    def med(wc):
        return out[(name, "PRIMARY", L_primary, wc.label)]["O0"]["dol50"]
    best = max(winners, key=med)
    print(f"  Step 3: {best.label} has the highest median dollars over H under O0 "
          f"({money(med(best))}).")
    return V_RISKIER + best.label


def control_v3(st_b: dict, cfgs: list) -> None:
    """The v3 composition control: the realized walk only, never scored."""
    hdr("CONTROL — era v3, realized walk only (printed, never read by the decision)")
    try:
        recs, diag = load_book(include_bs=False, era="v3")
    except SystemExit as exc:
        print(f"  era v3 refused by load_book (exit {exc.code}); no control printed.")
        return
    recs, _ = seal(recs)
    st = st_b["HEADLINE"]
    episodes = AS.dense_episodes(
        (d for d, _ in P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    ep = {d for e in episodes for d in e}
    print(f"  era {diag.get('era')}  book {len(recs)} rows  {diag.get('date_range')}  "
          f"PRIMARY dates {len(ep)}")
    cache = AS.new_cache()
    for name, _l, _b in BUDGETS:
        for pop, dates in (("PRIMARY", ep), ("SECONDARY", {r["date"] for r in recs})):
            if not dates:
                continue
            b = build([r for r in recs if r["date"] in dates], st_b[name], cache)
            n_cost = sum(1 for x in b.has_cost if x)
            sub(f"v3 {name} — {pop} (rows carrying a cost: {n_cost} of {len(b.has_cost)})")
            for wc in cfgs:
                r = identity(b, wc)
                print(f"  {wc.label:<16} pos {int(r.taken[0]):4d}  net "
                      f"{money(float(r.dollars[0])):>9}  MTM DD {pct(float(r.maxdd[0]))}  "
                      f"real DD {pct(float(r.rmaxdd[0]))}  ruined "
                      f"{'yes' if r.ruined[0] else 'no'}")


if __name__ == "__main__":
    sys.exit(main())
