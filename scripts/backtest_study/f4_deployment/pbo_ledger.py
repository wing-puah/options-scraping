"""pbo_ledger — how likely is it that the account-sizing configuration chosen as best was luck?

OPERATOR REQUEST 2026-10-06. Not pre-registered and not an arm: it adds no
configuration and changes no verdict. It re-runs the account-sizing
configurations the feasibility plan's trial ledger lists
(`research/account-sim-feasibility-plan.md`, "A trial ledger") plus
`narrow_to_fit`'s cached cells, on ONE calendar, and scores the selection by
the Probability of Backtest Overfitting (`lib/pbo.py`; Bailey, Borwein,
López de Prado, Zhu, J. Comput. Finance 2017, CSCV, S = 16).

Every configuration runs IN PROCESS on `account_sim.simulate` with a `Cfg`
built by `Settings.cfg(...)` overrides. Nothing is read from or written to
`config/account-sim.yml`, and no `account_sim` artifact or site page is
written. The only output is this report.

Per configuration and population (PRIMARY dense episodes, SECONDARY full
book, `account_sim`'s), the series is realized P&L booked on each EXIT
session, divided by that configuration's starting capital, on every weekday
from the population's first entry to its last exit. Zero rows before the
first entry pad the head so that S divides T. Gate GP1 proves that each
series' sum and max drawdown reproduce `account_sim`'s own total and A3
drawdown for that simulation.

Selection metrics, each mirroring how a configuration was preferred:

  total   total return on starting capital (A2's dollars, scale-free)
  maxdd   shallowest max drawdown of the joined rows in time order (A3)
  meanR   mean R per position, by exit session (A1's statistic)
  bar     the 25% drawdown bar first, then total return (FEASIBLE's shape)

Loss and degradation are reported on total return for `maxdd` and `bar`,
which have no natural zero. Usage:

  python3 -m scripts.backtest_study run pbo_ledger
"""
from __future__ import annotations

import contextlib
import logging
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f4_deployment import account_sim as AS  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import mtm_curve as MC  # noqa: E402
from scripts.backtest_study.lib import pbo as PBO  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

hdr, sub = AS.hdr, AS.sub
INF = float("inf")

#: CSCV block count (the paper's §4 recommendation) and the disclosed
#: sensitivity values.
S_HEAD = 16
S_SENS = (8, 12)
#: A3's bar, as a fraction of starting capital.
BAR = 0.25
#: Lexicographic offset for `bar`: any pass outranks any fail. Returns are
#: fractions of capital, so no total comes near it.
BAR_OFFSET = 1e3

#: The tracked cell every ledger entry varies from (the ledger's baseline,
#: `account_sim` (R, F1) as run 2026-09-08 to 2026-09-21). Constants: they
#: DEFINE the ledger, whatever the config file holds today.
BASE = dict(capital=25000.0, per_pos_cap=0.25, net_cap=2.50, risk_pct=0.02,
            max_per_day=3)
SWEEP_BUDGET = BASE["capital"] * BASE["risk_pct"]

#: The configurations whose ranks the report follows: the post-hoc favourite.
FOCUS = ("RF2_250", "RF2_150", "TC_F2HI_150", "TC_F2HI_250")
#: The two configuration sets PBO is computed on. "ticker-cap" adds the
#: `account_sim --ticker-cap` R cells scored 2026-10-06 (operator: they are
#: now among the configurations looked at).
SETS = ("ledger", "ledger + ticker-cap")


# ════════════════════════════════════════════════════════════════════════════
# The ledger
# ════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Trial:
    key: str
    label: str
    source: str
    over: dict = field(default_factory=dict)
    transform: tuple | None = None      # ("burn"|"walk", k) or ("regime", dirs)
    turtle: tuple | None = None         # (basis, scale_contracts, scale_caps)
    ticker_cap: bool = False            # in the "ledger + ticker-cap" set only


def _cap(v: float) -> str:
    return "inf" if v == INF else f"{v:.2f}"


def ledger() -> list[Trial]:
    out = [Trial("HEAD", "(R, F1) $25k 2% 0.25/2.50", "headline; knob base; "
                 "grid cell; $25k rung; arm (R, F1); narrow_to_fit (R, F1, $500)")]
    out += [Trial("RISK150", "risk 1.5%", "knob table", dict(risk_pct=0.015)),
            Trial("RISK125", "risk 1.25%", "knob table", dict(risk_pct=0.0125)),
            Trial("DAY2", "2 positions/day", "knob table", dict(max_per_day=2))]
    for cap in (35000, 50000, 75000, 100000, 150000, 250000):
        out.append(Trial(f"CAP{cap // 1000}K", f"capital ${cap // 1000}k",
                         "capital ladder" + ("" if cap <= 50000 else " (post-hoc)"),
                         dict(capital=float(cap))))
    for pp in (0.15, 0.25, 0.40, INF):
        for nc in (1.00, 1.50, 2.50, INF):
            if (pp, nc) == (0.25, 2.50):
                continue
            src = "cap grid" + ("; knob caps.net 1.50; registered cell"
                                if (pp, nc) == (0.25, 1.50) else "")
            out.append(Trial(f"G{_cap(pp)}_{_cap(nc)}", f"caps {_cap(pp)}/{_cap(nc)}",
                             src, dict(per_pos_cap=pp, net_cap=nc)))
    for net, tag in ((2.50, "250"), (1.50, "150")):
        out += [
            Trial(f"RF2_{tag}", f"(R, F2) $500 net {net:.2f}",
                  "arm cell" + ("; narrow_to_fit (R, F2, $500)"),
                  dict(net_cap=net, take_floor=False)),
            Trial(f"DF1_{tag}", f"(D, F1) net {net:.2f}", "arm cell",
                  dict(net_cap=net, downsize=True)),
            Trial(f"DF2_{tag}", f"(D, F2) net {net:.2f}", "arm cell",
                  dict(net_cap=net, downsize=True, take_floor=False)),
            Trial(f"F1HI_{tag}", f"(R, F1, $1,000) net {net:.2f}",
                  "narrow_to_fit cached", dict(net_cap=net, risk_pct=0.04)),
            Trial(f"F2HI_{tag}", f"(R, F2, $1,000) net {net:.2f}",
                  "narrow_to_fit cached",
                  dict(net_cap=net, risk_pct=0.04, take_floor=False)),
            Trial(f"F4_{tag}", f"F4 $500/$1,000 stop net {net:.2f}",
                  "narrow_to_fit cached", dict(net_cap=net, stop_abs=1000.0)),
        ]
    out += [
        Trial("BURN10", "skip >1.0x budget, burn slot", "investigation sweep",
              transform=("burn", 1.0)),
        Trial("BURN15", "skip >1.5x budget, burn slot", "investigation sweep",
              transform=("burn", 1.5)),
        Trial("WALK15", "skip >1.5x budget, walk down", "investigation sweep",
              transform=("walk", 1.5)),
        Trial("WALK20", "skip >2.0x budget, walk down", "investigation sweep",
              transform=("walk", 2.0)),
        Trial("WALK30", "skip >3.0x budget, walk down", "investigation sweep",
              transform=("walk", 3.0)),
        Trial("REGB", "refuse mech-BEAR dates", "investigation sweep",
              transform=("regime", frozenset({"BEAR"}))),
        Trial("REGBR", "refuse mech-BEAR/RANGE dates", "investigation sweep",
              transform=("regime", frozenset({"BEAR", "RANGE"}))),
    ]
    for name, sc_c, sc_caps in (("ladder", True, False), ("caps", False, True),
                                ("both", True, True)):
        for basis in ("mtm", "realized"):
            out.append(Trial(f"T_{name}_{basis}", f"Turtle {name} {basis}",
                             "Turtle throttle, tracked cell",
                             turtle=(basis, sc_c, sc_caps)))
    out.append(Trial("T_ladder_realized_150", "Turtle ladder realized net 1.50",
                     "Turtle throttle, registered cell", dict(net_cap=1.50),
                     turtle=("realized", True, False)))
    # `account_sim --ticker-cap`: the per-position cap binds on a ticker's
    # signed open total. Its R cells, $500/$1,000 x net 1.50/2.50 x F1/F2.
    for net, tag in ((1.50, "150"), (2.50, "250")):
        for bud, btag, risk in (("$500", "LO", 0.02), ("$1,000", "HI", 0.04)):
            for fl, take in (("F1", True), ("F2", False)):
                out.append(Trial(f"TC_{fl}{btag}_{tag}",
                                 f"ticker-cap (R, {fl}, {bud}) net {net:.2f}",
                                 "account_sim --ticker-cap, scored 2026-10-06",
                                 dict(net_cap=net, risk_pct=risk, take_floor=take,
                                      ticker_cap=True), ticker_cap=True))
    return out


NOT_REPRODUCED = (
    ("Fractional contracts, every variant (a, a+c, frac x max/day, caps, risk)",
     "simulate() sizes whole contracts; there is no fractional path"),
    ("One-contract floor with the dollar stop disabled (e)",
     "the frozen harness stop is $1,000; replay_sized can scale it, not remove it"),
    ("Dropping the three worst positions",
     "chosen on outcome; not a configuration"),
    ("(R, F3, $500) and (R, F3, $1,000)",
     "need the substitute-leg scrape (narrow_to_fit: AWAITING SCRAPE)"),
    ("Step 5, the v3 control", "a different population, not the same calendar"),
    ("Steps 0b-i, 0c, 3 (MTM curve, adequacy, bootstrap)",
     "measurements of one configuration, not configurations"),
    ("--compounding, ARM H, --ticker-cap, --live-select, --structure-universe",
     "not in the plan's ledger enumeration"),
)


# ════════════════════════════════════════════════════════════════════════════
# Running one configuration
# ════════════════════════════════════════════════════════════════════════════

def transform_days(day_lists, transform) -> list:
    """The day lists a sweep sees. `burn` swaps an over-threshold pick for an
    unsizable copy, which `simulate` counts as using the day's slot; `walk`
    and `regime` drop the pick so the walk continues down the list. The copies
    live in the returned list, which keeps them alive for the replay memo."""
    kind, arg = transform
    out = []
    for d, ranked in day_lists:
        new = []
        for r in ranked:
            mlpc = r.get("max_loss_per_contract")
            if kind == "regime":
                if r.get("mech_direction") in arg:
                    continue
            elif mlpc is not None and mlpc > arg * SWEEP_BUDGET:
                if kind == "walk":
                    continue
                r = dict(r, max_loss_per_contract=None)
            new.append(r)
        if new:
            out.append((d, new))
    return out


# -- Turtle: a port of the 2026-09-22 exploratory scratch --------------------
# `backtests/feasibility_plan_20260922/turtle_exploratory/turtle_sim.py`
# (gitignored), Curtis Faith, *Original Turtle Trading Rules*, Ch. 3: size x
# 0.8 per step, step k at a cumulative loss of sum 0.10 x 0.8^(j-1) below the
# year's starting equity, reset at the first session of each calendar year.
# The scratch drove `simulate` through the `ranker` hook and swapped
# `risk_contracts` / `admission` on the module for the call; this does the
# same, restored in `finally`. account_sim.py itself is not edited.

TURTLE_STEPS = 12
TURTLE_CUM = [0.0]
for _k in range(1, TURTLE_STEPS + 1):
    TURTLE_CUM.append(TURTLE_CUM[-1] + 0.10 * 0.8 ** (_k - 1))


class TurtleLadder:
    def __init__(self, capital: float, basis: str):
        self.capital, self.basis = float(capital), basis
        self.ref = None
        self.year = None
        self.k = 0
        self._marks: dict[int, tuple] = {}

    def _unrealized(self, open_pos, entry_sess) -> float:
        tot = 0.0
        for p in open_pos:
            got = self._marks.get(id(p))
            if got is None:
                try:
                    sess, dol, _ = MC.position_marks(p)
                except (ValueError, KeyError, TypeError, IndexError):
                    sess, dol = [], []
                got = self._marks[id(p)] = (sess, dol)
            val = 0.0
            for s, v in zip(*got):
                if s < entry_sess:
                    val = v
                else:
                    break
            tot += val
        return tot

    def step(self, entry_sess, open_pos, led) -> float:
        eq = self.capital + led.realized
        if self.basis == "mtm":
            eq += self._unrealized(open_pos, entry_sess)
        if self.year != entry_sess.year:
            self.year, self.ref, self.k = entry_sess.year, eq, 0
        if eq >= self.ref:
            self.k = 0
        else:
            trig = 0
            for k in range(1, TURTLE_STEPS + 1):
                if eq <= self.ref * (1.0 - TURTLE_CUM[k]):
                    trig = k
                else:
                    break
            self.k = max(self.k, trig)
        return 0.8 ** self.k


@contextlib.contextmanager
def _turtle_patch(state: dict, scale_contracts: bool, scale_caps: bool):
    orig_rc, orig_adm = AS.risk_contracts, AS.admission

    def rc(mlpc, budget):
        return orig_rc(mlpc, budget * state["m"])

    def adm(*a, equity=None, **kw):
        eq = a[4].capital if equity is None else equity
        return orig_adm(*a, equity=eq * state["m"], **kw)

    if scale_contracts:
        AS.risk_contracts = rc
    if scale_caps:
        AS.admission = adm
    try:
        yield
    finally:
        AS.risk_contracts, AS.admission = orig_rc, orig_adm


def run_trial(trial: Trial, day_lists, st: AS.Settings, cache: dict) -> AS.Sim:
    over = {**BASE, "compound": False, "stop_abs": None, "ticker_cap": False,
            "dd_throttle": None, **trial.over}
    cfg = st.cfg(trial.label, **over)
    days = transform_days(day_lists, trial.transform) if trial.transform else day_lists
    if trial.turtle is None:
        return AS.simulate(days, cfg, cache=cache)
    basis, sc_c, sc_caps = trial.turtle
    lad = TurtleLadder(cfg.capital, basis)
    state = {"m": 1.0}

    def ranker(d, ranked, open_pos, led, net_open, marked):
        state["m"] = lad.step(ranked[0]["t"].grid[0], open_pos, led)
        return ranked

    with _turtle_patch(state, sc_c, sc_caps):
        return AS.simulate(days, cfg, cache=cache, ranker=ranker)


# ════════════════════════════════════════════════════════════════════════════
# Series, gate GP1, columns
# ════════════════════════════════════════════════════════════════════════════

def weekdays(a: date, b: date) -> list[date]:
    out, d = [], a
    while d <= b:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def series(sim: AS.Sim, index: dict, T: int) -> np.ndarray:
    """T x 3: P&L / capital, sum of R, positions, each on the exit session."""
    out = np.zeros((T, 3))
    for p in sim.signal_pos:
        i = index[p.exit_sess]
        out[i, 0] += p.dollars / sim.cfg.capital
        out[i, 1] += p.R
        out[i, 2] += 1
    return out


def gp1(sim: AS.Sim, col: np.ndarray) -> str | None:
    """None when the series reproduces account_sim's own total and A3 drawdown."""
    cap = sim.cfg.capital
    _, vals = AS.equity_curve(sim.signal_pos)
    mdd = abs(AS.max_drawdown(vals))
    tot = col[:, 0].sum() * cap
    dd = PBO.max_drawdown(col[:, :1])[0] * cap
    if abs(tot - sim.dollars) > 1e-4 or abs(dd - mdd) > 1e-4 \
            or int(col[:, 2].sum()) != len(sim.signal_pos):
        return (f"total {tot:,.2f} vs {sim.dollars:,.2f}, maxDD {dd:,.2f} vs "
                f"{mdd:,.2f}, n {int(col[:, 2].sum())} vs {len(sim.signal_pos)}")
    return None


def bar_metric(sub_: np.ndarray) -> np.ndarray:
    ok = PBO.max_drawdown(sub_) <= BAR + 1e-12
    return PBO.total_metric(sub_) + np.where(ok, BAR_OFFSET, 0.0)


def mean_r_metric(sub_: np.ndarray) -> np.ndarray:
    return PBO.ratio_metric(sub_[..., 1:])


METRICS = (
    ("total", "total return on starting capital", PBO.total_metric, None),
    ("maxdd", "shallowest max drawdown", PBO.neg_drawdown_metric, PBO.total_metric),
    ("meanR", "mean R per position", mean_r_metric, None),
    ("bar", "25% drawdown bar, then total return", bar_metric, PBO.total_metric),
)


def dedupe(keys: list[str], cols: dict) -> tuple[list[str], dict]:
    """Columns with identical series collapse to the first; returns the kept
    keys and {kept: [aliases]}."""
    seen: dict[bytes, str] = {}
    kept, alias = [], {}
    for k in keys:
        b = cols[k].tobytes()
        if b in seen:
            alias[seen[b]].append(k)
        else:
            seen[b] = k
            kept.append(k)
            alias[k] = []
    return kept, alias


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def full_scores(M: np.ndarray) -> dict:
    return {name: np.asarray(fn(M), dtype=float) for name, _d, fn, _r in METRICS}


def desc_rank(v: np.ndarray, i: int) -> int:
    """1 = best, among the columns; NaN worst."""
    v = np.where(np.isnan(v), -np.inf, v)
    return int((v > v[i]).sum()) + 1


def print_pop(pop: str, trials, sims, M, kept, alias, by_key) -> dict:
    lab = {t.key: t.label for t in trials}
    N = len(kept)
    hdr(f"[{pop}] CONFIGURATIONS ON ONE CALENDAR")
    print(f"  {N + sum(len(alias[k]) for k in kept)} configurations, {N} distinct "
          f"series after merging "
          f"identical ones.")
    sc = full_scores(M)
    print(f"\n  {'#':>3} {'configuration':<38}{'n':>5}{'return':>9}{'maxDD':>8}"
          f"{'meanR':>8}  full-sample rank: total maxdd meanR bar")
    for j, k in enumerate(kept):
        s = sims[k]
        rs = [p.R for p in s.signal_pos]
        ranks = " ".join(f"{desc_rank(sc[m], j):>5}" for m, *_ in METRICS)
        print(f"  {j + 1:>3} {lab[k][:37]:<38}{len(rs):>5}"
              f"{M[:, j, 0].sum():>+9.1%}{PBO.max_drawdown(M[:, j:j + 1, 0])[0]:>8.1%}"
              f"{AS.fmean(rs):>+8.3f}  {ranks}")
        if alias[k]:
            print(f"      same series: {', '.join(lab[a] for a in alias[k])}")
    return sc


def print_cscv(pop: str, M: np.ndarray, kept, lab, padded: int) -> dict:
    results = {}
    hdr(f"[{pop}] PBO BY CSCV — S = {S_HEAD}")
    print(f"  T = {M.shape[0]} weekday rows ({padded} zero rows padded at the head), "
          f"N = {len(kept)} configurations, blocks of {M.shape[0] // S_HEAD} rows.")
    print(f"\n  {'metric':<8}{'combos':>8}{'PBO':>8}{'lambda p05':>12}{'p25':>8}"
          f"{'median':>8}{'p75':>8}{'p95':>8}{'mean':>8}{'slope':>8}{'P(loss)':>9}")
    for name, _desc, fn, rep in METRICS:
        res = PBO.cscv(M, S_HEAD, fn, report_metric=rep, keep_ranks=True)
        results[name] = res
        q = res.logit_quantiles()
        loss = "n/a" if res.prob_loss is None else f"{res.prob_loss:.1%}"
        print(f"  {name:<8}{res.n_combinations:>8}{res.pbo:>8.1%}"
              f"{q[0.05]:>+12.2f}{q[0.25]:>+8.2f}{q[0.5]:>+8.2f}{q[0.75]:>+8.2f}"
              f"{q[0.95]:>+8.2f}{float(np.mean(res.logits)):>+8.2f}"
              f"{res.slope:>+8.2f}{loss:>9}")
    print("""
  PBO is the share of combinations whose IS-best configuration ranks at or
  below the OOS median (lambda <= 0). Slope is the OLS slope of the selected
  configuration's OOS statistic on its IS statistic (degradation, §3.2).
  P(loss) is the share of combinations in which it loses OOS. For maxdd and
  bar both are read on total return. A drawdown ranks persistently because
  size sets it: a low maxdd PBO says the shallow configurations stay shallow,
  not that they earn.""")
    at0 = {n: r.n_at_zero for n, r in results.items() if r.n_at_zero}
    if at0:
        print(f"  combinations with lambda exactly 0 (counted as overfit): {at0}")

    sub("what the IS selection picks most often")
    for name, res in results.items():
        share = res.selection_share()
        top = np.argsort(-share)[:4]
        parts = []
        for j in top:
            if share[j] <= 0:
                continue
            m = res.n_star == j
            parts.append(f"{lab[kept[j]]} {share[j]:.0%} "
                         f"(lambda<=0 {np.mean(res.logits[m] <= 0):.0%})")
        print(f"  {name:<6} " + "; ".join(parts))
    return results


def print_focus(pop: str, results: dict, kept, alias, lab, sc) -> None:
    hdr(f"[{pop}] WHERE (R, F2) RANKS — IS against OOS")
    N = len(kept)
    for fk in FOCUS:
        j = next((i for i, k in enumerate(kept) if k == fk or fk in alias[k]), None)
        if j is None:
            continue
        sub(f"{lab[fk]}" + (f" (series of {lab[kept[j]]})" if kept[j] != fk else ""))
        print(f"  {'metric':<8}{'full rank':>10}{'IS-best':>9}{'IS top-5':>10}"
              f"{'OOS rank then':>15}{'IS-best: OOS omega':>20}{'lambda<=0':>11}")
        for name, res in results.items():
            sel = res.n_star == j
            # IS rank is ascending (N = best), so top-5 is rank > N - 5.
            top5 = res.is_rank[:, j] > N - 5
            oos_top5 = (f"{np.median(res.oos_rank[top5, j]) / (N + 1):.2f}"
                        if top5.any() else "never")
            if sel.any():
                w = f"{np.mean(res.omega[sel]):.2f}"
                lz = f"{np.mean(res.logits[sel] <= 0):.0%}"
            else:
                w = lz = "never"
            print(f"  {name:<8}{desc_rank(sc[name], j):>6} of {N:<3}{sel.mean():>8.0%}"
                  f"{top5.mean():>10.0%}{oos_top5:>15}{w:>20}{lz:>11}")
    print("""
  'full rank' is 1 = best on the whole path. 'IS top-5' is the share of
  combinations in which it ranks in the top five in-sample; 'OOS rank then' is
  its median OOS relative rank in those combinations (rank / (N + 1), 1 =
  best, 0.5 = median). Unconditional IS and OOS rank distributions are equal
  by construction: every training set is another combination's test set.""")


def print_sensitivity(pop: str, M_raw: np.ndarray) -> None:
    sub(f"[{pop}] disclosure — PBO at other S (each padded to fit)")
    for S in (*S_SENS, S_HEAD):
        Mp, k = PBO.pad_head(M_raw, S)
        vals = "  ".join(f"{name} {PBO.cscv(Mp, S, fn, report_metric=rep).pbo:.1%}"
                         for name, _d, fn, rep in METRICS)
        print(f"  S={S:<3} ({Mp.shape[0] // S} rows a block, {k} padded)  {vals}")


# ════════════════════════════════════════════════════════════════════════════
# Driver
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    logging.getLogger("backtest").setLevel(logging.ERROR)
    st = AS.load_settings(AS.DEFAULT_CONFIG)
    trials = ledger()
    lab = {t.key: t.label for t in trials}

    caps = f"{BASE['per_pos_cap']:.2f}/{BASE['net_cap']:.2f}"
    hdr("pbo_ledger — Probability of Backtest Overfitting over the account-sizing ledger")
    recs, diag = load_book(include_bs=False)
    print(f"""  era {diag.get('era')}   book {len(recs)} rows   {diag.get('n_dates')} dates   {diag.get('date_range')}
  Ledger: research/account-sim-feasibility-plan.md "A trial ledger", plus
  narrow_to_fit's cached cells. Rebuilt on the CURRENT book; the ledger's own
  figures came from earlier exports and are not reproduced here.
  Base cell: capital ${BASE['capital']:,.0f}, risk {BASE['risk_pct']:.0%}, caps {caps},
  {BASE['max_per_day']} positions/day, ARM R, F1. A ledger row changes one thing from it;
  the arm, narrow_to_fit and ticker-cap rows are the cells their labels name.
  Method: Bailey, Borwein, Lopez de Prado, Zhu (2017), Algorithm 2.3 (CSCV).
  NOTHING SHIPS. This adds no configuration to the ledger and moves no
  verdict. No annualised figure, Sharpe or time-to-recover is printed.""")

    episodes = AS.dense_episodes(
        (d for d, _ in P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    ep_dates = {d for ep in episodes for d in ep}
    all_dates = {r["date"] for r in recs}
    refusal = AS.primary_refusal(all_dates, ep_dates, st)
    if refusal:
        print(f"\nREFUSED — {refusal}")
        return era.EXIT_THIN_ERA

    hdr("LEDGER RECONSTRUCTED")
    print(f"  {'key':<24}{'configuration':<38}source")
    for t in trials:
        print(f"  {t.key:<24}{t.label:<38}{t.source}")
    sub("ledger entries NOT reproduced")
    for what, why in NOT_REPRODUCED:
        print(f"  - {what}: {why}")

    cache = AS.new_cache()
    failures = []
    summary = {}
    for pop, dates in (("PRIMARY", ep_dates), ("SECONDARY", all_dates)):
        pop_recs = [r for r in recs if r["date"] in dates]
        day_lists = P.ordered_by_day(pop_recs, P.ladder_rank, P.ladder_eligible)
        sims = {t.key: run_trial(t, day_lists, st, cache) for t in trials}
        poss = [p for s in sims.values() for p in s.signal_pos]
        cal = weekdays(min(p.entry_sess for p in poss), max(p.exit_sess for p in poss))
        index = {d: i for i, d in enumerate(cal)}
        cols = {}
        for t in trials:
            off = [p for p in sims[t.key].signal_pos if p.exit_sess not in index]
            if off:
                failures.append(f"{pop} {t.key}: {len(off)} exits off the weekday calendar")
                continue
            cols[t.key] = series(sims[t.key], index, len(cal))
            why = gp1(sims[t.key], cols[t.key])
            if why:
                failures.append(f"{pop} {t.key}: {why}")
        if failures:
            break
        for set_name in SETS:
            keys = [t.key for t in trials
                    if set_name != "ledger" or not t.ticker_cap]
            kept, alias = dedupe(keys, cols)
            M_raw = np.stack([cols[k] for k in kept], axis=1)
            M, padded = PBO.pad_head(M_raw, S_HEAD)
            tag = f"{pop} | {set_name}"
            sc = print_pop(tag, trials, sims, M, kept, alias, cols)
            results = print_cscv(tag, M, kept, lab, padded)
            print_focus(tag, results, kept, alias, lab, sc)
            print_sensitivity(tag, M_raw)
            summary[tag] = (len(kept), results)

    hdr("GATE GP1 — each series reproduces account_sim's total and A3 drawdown")
    if failures:
        for f in failures:
            print(f"  FAIL {f}")
        print("  GP1: FAIL — nothing above is a result. Exit 1.")
        return 1
    print(f"  GP1: PASS on {len(trials)} configurations x 2 populations")

    hdr("CLOSE")
    for pop, (n, results) in summary.items():
        print(f"  {pop:<31} N={n:<3} " + "  ".join(
            f"PBO[{name}] {r.pbo:.1%}" for name, r in results.items()))
    print("""  Caveats: one market path; CSCV assumes the S blocks are exchangeable,
  which serial dependence in open positions strains; many configurations
  differ by one knob, so their series are correlated and the effective N is
  smaller than the count. Nothing in this report is a shippable rule.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
