"""bear_fast_exit — does a fast exit make a bear debit pay, net of costs?

Registration: research/pre-registrations/f2_management/bear_fast_exit.md
(ACCEPTED BY DEFAULT 2026-10-09). Every number below is fixed there; this
module only executes it.

Two questions, both graded on net R (the arm's replayed R minus that arm's own
round-trip cost):

  1. LEVEL  — is bear-debit net meanR above zero under a fast exit?
  2. DELTA  — is the fast exit better than the SHIPPED bear-debit exit, paired
              by row?

Arms (frozen at three families, eight arms):

  ARM TP  small profit target   pt in {0.10, 0.20, 0.30}; stop, tef and the
                                BEAR_HE trail unchanged
  ARM TS  time stop in sessions the shipped exit, plus: still open after
                                session N -> exit at the close of session N,
                                N in {1, 2, 3, 5}. Session 1 = entry-day close.
  ARM OP  the operator's rule   pt 0.25 or the close of session 5

Pricing: every arm replays through the FROZEN `lib/harness.py::replay` — never
edited, copied or forked. `ARM TS` is composition around it, as
`staged_exit` ARM E is. The baseline profile is PRODUCTION's own merge,
`scripts/backtest/simulate.py::_effective_sim_cfg` on `config/backtest.yml`,
not a transcription (G2). Cost is PRODUCTION's own
`simulate._apply_costs`, and the quote rule is production's `_leg_spread`
(which carries the 2026-09-24 junk-quote test). Nothing here re-implements
pricing.

Two cost lines, both printed (Resolved at build 2026-10-09):

  HEADLINE   the knobs in `config/backtest.yml` at run time — $0.65 per
             contract per leg per side, slippage 0 — which is `cost_sensitivity`
             ARM X as registered since 2026-09-24 and what the operator pays
             (fills at the combo mid). Grades the verdict.
  SECONDARY  the draft's literal point: the same commission plus 25% of the
             quoted spread per leg per side, missing or degenerate quotes on
             `cost_sensitivity` ARM Q's fallback ladder. Declared; grades its
             own line, never the headline.

Both eras run in ONE process: the requested era (`STUDY_ERA`, default
`current`) is PRIMARY, and v3 is loaded alongside it as the replication era.
They are never pooled. A `--era v3` run grades v3 alone and prints no joint
verdict, so it cannot clobber the primary report with a partial one.

Holdout seal: no outcome is computed on a signal date on or after
`SEAL_START`. `load_book` withholds those rows once the seal lands in
`lib/era.py`; this module drops them again itself and prints the count, so the
rule holds on a checkout that predates that code. C7 (the forward read) is
PENDING until the seal lifts: a registration accepted on or after 2026-10-09
cannot be a sealed reader.

Run:
    python -m scripts.backtest_study run bear_fast_exit
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path, parse_history_details  # noqa: E402
from scripts.backtest import simulate as SIM  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402
from scripts.backtest_study.lib.harness import MAX_LOSS_ABS, Trade, replay  # noqa: E402
from scripts.backtest_study.lib.replay_basis import (  # noqa: E402
    classify as _classify, unreachable_reasons,
)

DESIGNED_REFUSAL_EXIT_CODES = frozenset({2, 3})

CONFIG = ROOT / "config" / "backtest.yml"
BEAR_DEBIT = ("bear_put_spread", "long_put")
REPLICATION_ERA = "v3"

# --- the holdout seal --------------------------------------------------------
# The authoritative seal lives in `lib/era.py` once it lands there; this copy
# only makes the rule hold on a checkout that predates it. Same date, by rule.
SEAL_START = "2026-09-23"

# --- arms, frozen by the registration ------------------------------------------
# (label, family, profit-target override or None, session stop N or None)
ARMS = (
    ("TP 0.10", "TP", 0.10, None),
    ("TP 0.20", "TP", 0.20, None),
    ("TP 0.30", "TP", 0.30, None),
    ("TS 1", "TS", None, 1),
    ("TS 2", "TS", None, 2),
    ("TS 3", "TS", None, 3),
    ("TS 5", "TS", None, 5),
    ("OP 0.25 or session 5", "OP", 0.25, 5),
)

# --- floors and thresholds, frozen by the registration --------------------------
G0_MIN_DATES = 25
G0_MIN_ROWS = 60
G4_MAX_FALLBACK_SHARE = 0.25
C7_MIN_DATES = 15
C7_MIN_ROWS = 30
WIDE_QUOTE_FRAC = 0.50
SECONDARY_SLIPPAGE = 0.25
BOOT_N = P.BOOT_N

# Exit reason the session stop writes. Not a harness reason, on purpose: the
# exit mix then shows how many rows the stop itself closed.
TS_REASON = "session_stop"

# Quote provenance tags (cost_sensitivity ARM Q's ladder).
Q_QUOTE, Q_FB1, Q_FB2, Q_NONE = "quote", "fallback1", "fallback2", "uncostable"


# =============================================================================
# The baseline: production's own merge
# =============================================================================

def load_sim_cfg(path: Path = CONFIG) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)["simulation"]


def harness_profile(eff: dict) -> dict:
    """Production's effective config -> `harness.replay` keyword arguments.

    Refuses (ValueError) a config carrying a rule the frozen harness cannot
    replay: then the baseline would not be production, which is G2's point.
    """
    for key in ("trailing_stop_portfolio_trigger_pct", "trailing_stop_portfolio_trail_pct",
                "loss_days_exit"):
        if eff.get(key) is not None:
            raise ValueError(f"G2: config sets {key}={eff[key]!r}, which the frozen "
                             f"harness cannot replay")
    return dict(pt=eff.get("profit_target"), sl=eff.get("stop_loss"),
                trig=eff.get("trailing_stop_trigger"), trail=eff.get("trailing_stop_pct"),
                tef=eff.get("time_exit_dte_fraction"), be_after=eff.get("be_after"))


def production_profile(rec: dict, sim_cfg: dict) -> dict:
    """The exit profile production runs on this row, built from the config."""
    t = rec["t"]
    eff = SIM._effective_sim_cfg(sim_cfg, t.entry_net, t.signal_date.isoformat(),
                                 t.structure)
    return harness_profile(eff)


def is_bear_debit(rec: dict) -> bool:
    return rec["structure"] in BEAR_DEBIT and not rec["credit"]


# =============================================================================
# The arms: composition around the frozen replay
# =============================================================================

def session_stop(t: Trade, res: dict, n: int) -> dict:
    """`ARM TS`'s composition. If `res` is still open after session `n`, exit at
    the mark of session `n`, or the last priced mark before it. If no mark is
    priced at or before `n`, `res` stands unchanged."""
    if res["days_held"] <= n:
        return res
    for i in range(min(n, len(t.marks)), 0, -1):
        m = t.marks[i - 1]
        if m is not None:
            return dict(exit_reason=TS_REASON, days_held=i, pnl_pct=round(t.pnl_of(m), 10))
    return res


def arm_outcome(rec: dict, base: dict, pt: float | None, n: int | None) -> dict:
    """One row's outcome under an arm. The bear keying lives HERE, so G1 can
    hand this the whole book and check nothing else moved."""
    t = rec["t"]
    if not is_bear_debit(rec):
        return replay(t, **base)
    prof = dict(base)
    if pt is not None:
        prof["pt"] = pt
    res = replay(t, **prof)
    if n is not None:
        res = session_stop(t, res, n)
    return res


def triple(res: dict) -> tuple:
    return (res["exit_reason"], res["days_held"], round(res["pnl_pct"], 10))


# =============================================================================
# Cost: production's `_apply_costs`, on the arm's own exit day
# =============================================================================

def cost_dollars(t: Trade, exit_reason: str, days_held: int, commission: float,
                 slippage: float, entry_units=None, grid_units=None) -> float:
    """Round-trip cost in dollars from `simulate._apply_costs`.

    An expired position pays the entry side only (registration): the exit side
    is never reached, so its slippage is not charged (days_held None hands
    `_apply_costs` no exit spread) and its commission is taken back out.
    """
    cfg = {"commission_per_contract": commission, "slippage_frac_of_spread": slippage}
    expired = exit_reason == "expired"
    result = {"days_held": None if expired else days_held,
              "realized_pnl_abs": 0.0, "realized_pnl_pct": 0.0}
    SIM._apply_costs(result, cfg, t.legs, t.contracts, t.entry_net,
                     entry_units, list(grid_units or []))
    cost = result["cost_total"]
    if expired:
        units = sum(abs(leg.qty) for leg in t.legs) * t.contracts
        cost = round(cost - commission * units, 2)
    return cost


def cost_r(t: Trade, cost: float) -> float:
    return cost / (abs(t.entry_net) * 100 * t.contracts)


# --- quotes, for the SECONDARY line only ------------------------------------

class QuoteBook:
    """Per-contract history rows from the option-history cache, read once."""

    def __init__(self, cache_dir: Path = HISTORY_CACHE):
        self.cache_dir = cache_dir
        self._rows: dict[tuple, dict] = {}

    def rows(self, leg) -> dict:
        key = (leg.ticker, leg.expiration, leg.strike, leg.opt_type)
        if key not in self._rows:
            p = cache_path(self.cache_dir, leg.ticker, leg.expiration, leg.strike, leg.opt_type)
            self._rows[key] = (parse_history_details(p.read_text(), require_mark=False)
                               if p.exists() else {})
        return self._rows[key]


def usable_spread(row) -> float | None:
    """A leg's quoted spread that day, or None when the quote is missing or
    degenerate. Production's `_leg_spread` decides both, junk included: a junk
    quote is not a spread anyone pays, so it takes the fallback ladder."""
    if not row:
        return None
    s = SIM._leg_spread(row)
    return None if (s is None or s == SIM.JUNK_SPREAD) else float(s)


def leg_spreads(t: Trade, quotes: QuoteBook) -> list[list[tuple[float | None, str]]]:
    """`[leg][grid day] -> (spread, tag)` on `cost_sensitivity` ARM Q's ladder:

      quote       the leg's own row that day (never interpolated across dates)
      fallback1   the same contract's median usable spread over the
                  position's priced path
      fallback2   the median usable spread of the position's OTHER legs that day
      uncostable  none of the above
    """
    priced_days = [d for d, m in zip(t.grid, t.marks) if m is not None]
    raw = []
    for leg in t.legs:
        rows = quotes.rows(leg)
        raw.append([usable_spread(rows.get(d)) for d in t.grid])
    med_path = []
    for li, leg in enumerate(t.legs):
        rows = quotes.rows(leg)
        vals = [usable_spread(rows.get(d)) for d in priced_days]
        vals = [v for v in vals if v is not None]
        med_path.append(statistics.median(vals) if vals else None)
    out = []
    for li in range(len(t.legs)):
        per_day = []
        for di in range(len(t.grid)):
            v = raw[li][di]
            if v is not None:
                per_day.append((v, Q_QUOTE))
            elif med_path[li] is not None:
                per_day.append((med_path[li], Q_FB1))
            else:
                others = [raw[lj][di] for lj in range(len(t.legs))
                          if lj != li and raw[lj][di] is not None]
                if others:
                    per_day.append((statistics.median(others), Q_FB2))
                else:
                    per_day.append((None, Q_NONE))
        out.append(per_day)
    return out


def entry_index(t: Trade) -> int:
    """0-based grid index of the entry session: the first priced mark."""
    for i, m in enumerate(t.marks):
        if m is not None:
            return i
    return 0


def side_units(t: Trade, spreads, day_idx: int) -> tuple[float | None, list[str]]:
    """`Σ|qty|·spread` for one side on grid day `day_idx`, and each leg's tag.
    None when any leg is UNCOSTABLE."""
    units, tags = 0.0, []
    for leg, per_day in zip(t.legs, spreads):
        s, tag = per_day[day_idx]
        tags.append(tag)
        if s is None:
            return None, tags
        units += abs(leg.qty) * s
    return units, tags


# =============================================================================
# Evaluation
# =============================================================================

def evaluate_era(era: str, sim_cfg: dict, quotes: QuoteBook, primary: bool) -> dict:
    recs, diag = load_book(include_bs=False, era=era)
    n_loaded = len(recs)
    sealed = [r for r in recs if r["date"] >= SEAL_START]
    recs = [r for r in recs if r["date"] < SEAL_START]
    out = dict(era=diag["era"], requested=era, primary=primary, n_book=n_loaded,
               n_sealed=len(sealed), n_sealed_dates=len({r["date"] for r in sealed}))

    commission, slip = SIM._cost_knobs(sim_cfg)
    out["cost_knobs"] = (commission, slip)

    # profiles (G2 prints them)
    for r in recs:
        r["_base"] = production_profile(r, sim_cfg)

    bear_all = [r for r in recs if is_bear_debit(r)]
    bear = [r for r in bear_all if r["fill_trusted"]]
    out["n_bear_untrusted"] = len(bear_all) - len(bear)
    out["bear"] = bear

    # G3 — export is post-re-price (v4 only; v3 is frozen and never re-priced)
    if out["era"] != "v3":
        blank = [r for r in bear if not str(r["t"].row.get("cost_total") or "").strip()]
        out["g3_blank"] = len(blank)
        if blank:
            print(f"\nG3 FAILED — {len(blank)} of {len(bear)} bear-debit rows on "
                  f"{out['era']} carry no cost_total; the export predates the re-price.")
            sys.exit(1)
    else:
        out["g3_blank"] = None

    # G1 — leak guard over the WHOLE book
    leaks = 0
    for r in recs:
        if is_bear_debit(r):
            continue
        want = triple(replay(r["t"], **r["_base"]))
        for _, _, pt, n in ARMS:
            if triple(arm_outcome(r, r["_base"], pt, n)) != want:
                leaks += 1
    out["n_nonbear"] = sum(1 for r in recs if not is_bear_debit(r))
    out["g1_leaks"] = leaks
    if leaks:
        print(f"\nG1 FAILED — {leaks} non-bear row-arm outcomes changed.")
        sys.exit(1)

    # baseline + G2 reproduction checks
    g2_fail = 0
    for r in bear:
        t, base = r["t"], r["_base"]
        r["_shipped"] = replay(t, **base)
        if triple(arm_outcome(r, base, base["pt"], None)) != triple(r["_shipped"]):
            g2_fail += 1
        if triple(arm_outcome(r, base, None, 10 ** 6)) != triple(r["_shipped"]):
            g2_fail += 1
    out["g2_fail"] = g2_fail
    if g2_fail:
        print(f"\nG2 FAILED — {g2_fail} reproductions of the baseline disagree.")
        sys.exit(1)
    out["profiles"] = Counter(tuple(sorted(r["_base"].items())) for r in bear)
    out["profile_cells"] = Counter((r["mech_cell"] == "BEAR_HE",
                                    tuple(sorted(r["_base"].items()))) for r in bear)

    # stored-reproduction census (diagnostic): does the baseline replay
    # reproduce the row production wrote?
    kinds = Counter()
    for r in bear:
        kind, _, _ = _classify(r["t"], r["_base"], unreachable_reasons(r["_base"]))
        kinds[kind] += 1
    out["calib"] = kinds

    # arm outcomes
    for r in bear:
        r["_arms"] = {lab: arm_outcome(r, r["_base"], pt, n) for lab, _, pt, n in ARMS}

    # quotes (secondary line) and headline costs
    qcensus = Counter()
    for r in bear:
        t = r["t"]
        outcomes = {"BASE": r["_shipped"], **r["_arms"]}
        r["_net"] = {}
        r["_gross"] = {k: v["pnl_pct"] for k, v in outcomes.items()}
        for k, v in outcomes.items():
            c = cost_dollars(t, v["exit_reason"], v["days_held"], commission, slip)
            r["_net"][k] = v["pnl_pct"] - cost_r(t, c)
        spreads = leg_spreads(t, quotes)
        ei = entry_index(t)
        e_units, e_tags = side_units(t, spreads, ei)
        r["_entry_units"] = e_units
        r["_wide"] = (None if e_units is None
                      else e_units > WIDE_QUOTE_FRAC * abs(t.entry_net))
        r["_net2"] = {}
        for k, v in outcomes.items():
            tags = list(e_tags)
            if v["exit_reason"] == "expired":
                x_units, x_tags = 0.0, []
            else:
                x_units, x_tags = side_units(t, spreads, v["days_held"] - 1)
            tags += x_tags
            for tag in tags:
                qcensus[tag] += 1
            if e_units is None or x_units is None:
                r["_net2"][k] = None
                continue
            grid_units = [None] * len(t.grid)
            if v["exit_reason"] != "expired":
                grid_units[v["days_held"] - 1] = x_units
            c = cost_dollars(t, v["exit_reason"], v["days_held"], commission,
                             SECONDARY_SLIPPAGE, e_units, grid_units)
            r["_net2"][k] = v["pnl_pct"] - cost_r(t, c)
    out["qcensus"] = qcensus
    charged = sum(qcensus.values())
    bad = qcensus[Q_FB2] + qcensus[Q_NONE]
    out["g4_share"] = bad / charged if charged else 1.0
    out["g4_uncostable"] = out["g4_share"] > G4_MAX_FALLBACK_SHARE
    return out


def changed_rows(bear: list[dict], lab: str) -> list[dict]:
    return [r for r in bear if triple(r["_arms"][lab]) != triple(r["_shipped"])]


def grade_line(bear: list[dict], key: str) -> dict:
    """Every arm's level and delta, with C5/C6 robustness, on one cost line.
    `key` is `_net` (headline) or `_net2` (secondary)."""
    res = {}
    base_rows = [dict(date=r["date"], v=r[key]["BASE"], g=r["_gross"]["BASE"])
                 for r in bear if r[key]["BASE"] is not None]
    lo, hi = P.boot_ci_by_date(base_rows, "v", n=BOOT_N)
    res["BASE"] = dict(n=len(base_rows), dates=len({p["date"] for p in base_rows}),
                       mean=statistics.fmean(p["v"] for p in base_rows),
                       gross=statistics.fmean(p["g"] for p in base_rows), ci=(lo, hi),
                       pf=P.pf_ci_by_date(base_rows, "v", n=BOOT_N))
    for lab, _, _, _ in ARMS:
        ch = changed_rows(bear, lab)
        a_dates = len({r["date"] for r in ch})
        cell = dict(affected_rows=len(ch), affected_dates=a_dates,
                    powered=a_dates >= G0_MIN_DATES and len(ch) >= G0_MIN_ROWS)
        if not cell["powered"]:
            res[lab] = cell
            continue
        rows = [dict(date=r["date"], a=r[key][lab], b=r[key]["BASE"],
                     g=r["_gross"][lab], source=r["source"])
                for r in bear if r[key][lab] is not None and r[key]["BASE"] is not None]
        cell["n"] = len(rows)
        cell["dates"] = len({p["date"] for p in rows})
        cell["mean"] = statistics.fmean(p["a"] for p in rows)
        cell["gross"] = statistics.fmean(p["g"] for p in rows)
        cell["level_ci"] = P.boot_ci_by_date(rows, "a", n=BOOT_N)
        cell["pf"] = P.pf_ci_by_date(rows, "a", n=BOOT_N)
        cell["delta"] = statistics.fmean(p["a"] - p["b"] for p in rows)
        cell["delta_ci"] = P.boot_ci_paired_by_date(rows, "a", "b", n=BOOT_N)
        _, _, cell["level_loo_min"], _ = P.loo_by_date(rows, lambda p: p["a"], lambda p: 0.0)
        _, _, cell["delta_loo_min"], _ = P.loo_by_date(rows, lambda p: p["a"],
                                                       lambda p: p["b"])
        cell["cuts"] = robustness_cuts(rows)
        res[lab] = cell
    return res


def robustness_cuts(rows: list[dict]) -> dict:
    """C6's cuts: `{cut: (n, level mean, delta mean)}` — the two dominant
    windows, ex-both, every calendar year, both pricing tiers."""
    cuts = dict(P.window_cuts(rows))
    both = set(P.DOMINANT_WINDOWS["ex_2025_mar_apr"]) | set(P.DOMINANT_WINDOWS["ex_2026_feb_apr"])
    cuts["ex_both"] = [p for p in rows if p["date"][:7] not in both]
    for y, rs in P.by_year(rows).items():
        cuts[f"year {y}"] = rs
    for src in ("real", "tweak"):
        cuts[f"tier {src}"] = [p for p in rows if p["source"] == src]
    out = {}
    for name, rs in cuts.items():
        if name == "ALL" or not rs:
            continue
        out[name] = (len(rs), statistics.fmean(p["a"] for p in rs),
                     statistics.fmean(p["a"] - p["b"] for p in rs))
    return out


def robust(cell: dict, question: str) -> tuple[bool, bool]:
    """(C5, C6) for `question` in {"level", "delta"}: every LOO fold and every
    cut keeps the positive sign."""
    if not cell.get("powered"):
        return False, False
    c5 = cell[f"{question}_loo_min"] > 0
    idx = 1 if question == "level" else 2
    c6 = all(v[idx] > 0 for v in cell["cuts"].values())
    return c5, c6


def criteria(prim: dict, repl: dict | None, lab: str) -> dict:
    """C1–C7 for one arm on one cost line. `prim`/`repl` are `grade_line`
    results for the primary and replication eras."""
    p, r = prim.get(lab, {}), (repl or {}).get(lab, {})

    def lo(cell, k):
        return cell[k][0] if cell.get("powered") else float("nan")

    c = dict(
        C1=lo(p, "level_ci") > 0,
        C2=lo(r, "level_ci") > 0,
        C3=lo(p, "delta_ci") > 0,
        C4=lo(r, "delta_ci") > 0,
    )
    lv = [robust(p, "level"), robust(r, "level")]
    dl = [robust(p, "delta"), robust(r, "delta")]
    c["C5_level"] = all(x[0] for x in lv)
    c["C6_level"] = all(x[1] for x in lv)
    c["C5_delta"] = all(x[0] for x in dl)
    c["C6_delta"] = all(x[1] for x in dl)
    c["C7"] = "PENDING"
    c["powered_v4"] = bool(p.get("powered"))
    return c


def verdict(prim: dict, repl: dict | None) -> tuple[str, list[str]]:
    """The registered verdict tokens. C7 is PENDING under the seal, so a PAYS
    or BLEED-CUT prints with that suffix and ships nothing."""
    if not any(prim.get(lab, {}).get("powered") for lab, _, _, _ in ARMS) and \
            not any((repl or {}).get(lab, {}).get("powered") for lab, _, _, _ in ARMS):
        return "UNDERPOWERED", []
    pays, cut, fragile = [], [], []
    for lab, _, _, _ in ARMS:
        c = criteria(prim, repl, lab)
        delta_ok = c["C3"] and c["C4"] and c["C5_delta"] and c["C6_delta"]
        level_ok = c["C1"] and c["C2"] and c["C5_level"] and c["C6_level"]
        if delta_ok and level_ok:
            pays.append(lab)
        elif delta_ok:
            cut.append(lab)
        elif c["C3"] and c["C4"]:
            fragile.append(lab)
    notes = [f"{lab}: clears C3 and C4 but fails C5 or C6" for lab in fragile]
    if pays:
        return "PAYS (C7 PENDING)", pays + notes
    if cut:
        return "BLEED-CUT (C7 PENDING)", cut + notes
    return "NULL", notes


# =============================================================================
# Report
# =============================================================================

def hdr(t: str) -> None:
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t: str) -> None:
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


def _ci(ci) -> str:
    return f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"


def _pf(pf) -> str:
    point, lo, hi = pf
    if point is None:
        return "PF    n/a"
    return f"PF {point:4.2f} [{lo:4.2f}, {hi:4.2f}]"


def fmt_profile(items: tuple) -> str:
    d = dict(items)
    return "  ".join(f"{k}={d[k]}" for k in ("pt", "sl", "tef", "trig", "trail", "be_after"))


def print_census(ev: dict) -> None:
    sub(f"population — {ev['era']} ({'PRIMARY' if ev['primary'] else 'REPLICATION'})")
    bear = ev["bear"]
    print(f"  book rows {ev['n_book']} (real + tweak)   sealed rows withheld "
          f"{ev['n_sealed']} on {ev['n_sealed_dates']} dates >= {SEAL_START}")
    print(f"  bear-debit rows {len(bear)} on {len({r['date'] for r in bear})} dates   "
          f"excluded (fill_trusted False) {ev['n_bear_untrusted']}   "
          f"non-bear rows {ev['n_nonbear']}")
    print("  structure " + "  ".join(f"{k}:{v}" for k, v in
                                     sorted(Counter(r['structure'] for r in bear).items())))
    print("  tier      " + "  ".join(f"{k}:{v}" for k, v in
                                     sorted(Counter(r['source'] for r in bear).items())))
    sub("gates")
    g3 = ("n/a (v3 is frozen; fill_trusted is the guard)" if ev["g3_blank"] is None
          else f"PASS — every bear row carries cost_total")
    print(f"  G1 LEAK GUARD       PASS — {ev['n_nonbear']} non-bear rows x {len(ARMS)} arms, "
          f"0 changed")
    print(f"  G2 BASELINE         PASS — pt-at-baseline and N-beyond-path reproduce "
          f"the baseline on every row")
    print(f"  G3 POST-RE-PRICE    {g3}")
    print("  G2 baseline profile, built from config/backtest.yml at run time:")
    for (bear_he, prof), n in sorted(ev["profile_cells"].items()):
        print(f"    {'BEAR_HE ' if bear_he else 'other   '} n={n:>4}  {fmt_profile(prof)}")
    print("  baseline replay vs the row production wrote (diagnostic, not a gate): "
          + "  ".join(f"{k}:{v}" for k, v in sorted(ev["calib"].items())))
    q = ev["qcensus"]
    tot = sum(q.values())
    print(f"  G4 QUOTE PROVENANCE (secondary line only; the headline reads no quote): "
          f"{tot} leg-sides  " + "  ".join(f"{k}:{q[k]}" for k in (Q_QUOTE, Q_FB1, Q_FB2, Q_NONE))
          + f"   fallback2+uncostable {ev['g4_share']:.1%}"
          + ("  -> UNCOSTABLE" if ev["g4_uncostable"] else "  -> pass"))
    wide = sum(1 for r in bear if r["_wide"])
    unk = sum(1 for r in bear if r["_wide"] is None)
    print(f"  wide entry quote (spread > {WIDE_QUOTE_FRAC:.0%} of debit): {wide} rows   "
          f"entry quote uncostable: {unk}   (kept in every primary figure)")


def print_line(ev: dict, key: str, title: str) -> dict:
    sub(f"{title} — {ev['era']}")
    g = grade_line(ev["bear"], key)
    b = g["BASE"]
    print(f"  {'arm':<22} {'aff rows/dates':>14}  {'gross':>7} {'net meanR':>9} "
          f"{'CI95':>17}  {'ΔR net':>7} {'CI95 paired':>17}  {'LOOmin lvl':>10} "
          f"{'LOOmin Δ':>9}")
    print(f"  {'shipped (baseline)':<22} {'—':>14}  {b['gross']:>+7.3f} {b['mean']:>+9.3f} "
          f"{_ci(b['ci']):>17}  {'—':>7} {'—':>17}")
    for lab, _, _, _ in ARMS:
        c = g[lab]
        aff = f"{c['affected_rows']}/{c['affected_dates']}"
        if not c["powered"]:
            print(f"  {lab:<22} {aff:>14}  UNDERPOWERED (G0 needs {G0_MIN_DATES} dates and "
                  f"{G0_MIN_ROWS} rows)")
            continue
        print(f"  {lab:<22} {aff:>14}  {c['gross']:>+7.3f} {c['mean']:>+9.3f} "
              f"{_ci(c['level_ci']):>17}  {c['delta']:>+7.3f} {_ci(c['delta_ci']):>17}  "
              f"{c['level_loo_min']:>+10.3f} {c['delta_loo_min']:>+9.3f}")
    print(f"\n  rows graded: {b['n']} on {b['dates']} dates. Net R = replayed R minus that "
          f"arm's own round-trip cost; gross grades nothing.")
    print(f"  profit factor on net R (always beside meanR):  shipped {_pf(b['pf'])}")
    for lab, _, _, _ in ARMS:
        if g[lab]["powered"]:
            print(f"    {lab:<22} {_pf(g[lab]['pf'])}   meanR {g[lab]['mean']:+.3f}")
    print("\n  C6 cuts — (n, net meanR, net ΔR) per cut; C6 needs every sign > 0:")
    for lab, _, _, _ in ARMS:
        c = g[lab]
        if not c["powered"]:
            continue
        cells = "  ".join(f"{k} n={n} {lv:+.3f}/{dl:+.3f}" for k, (n, lv, dl) in c["cuts"].items())
        print(f"    {lab:<22} {cells}")
    return g


def print_wide(ev: dict) -> None:
    sub(f"wide-quote positions, printed separately (headline net meanR) — {ev['era']}")
    for flag, name in ((True, "wide"), (False, "quote-sane")):
        rows = [r for r in ev["bear"] if r["_wide"] is flag]
        if not rows:
            print(f"  {name:<11} n=0")
            continue
        cells = "  ".join(f"{k} {statistics.fmean(r['_net'][k] for r in rows):+.3f}"
                          for k in ["BASE"] + [lab for lab, _, _, _ in ARMS])
        print(f"  {name:<11} n={len(rows):>4}  {cells}")


def print_exit_mix(ev: dict) -> None:
    sub(f"exit mix — {ev['era']}")
    print("  shipped  " + "  ".join(f"{k}:{v}" for k, v in sorted(
        Counter(r["_shipped"]["exit_reason"] for r in ev["bear"]).items())))
    for lab, _, _, _ in ARMS:
        print(f"  {lab:<8} " + "  ".join(f"{k}:{v}" for k, v in sorted(
            Counter(r["_arms"][lab]["exit_reason"] for r in ev["bear"]).items())))


def print_criteria(prim: dict, repl: dict | None, title: str) -> None:
    sub(f"criteria — {title}")
    print(f"  {'arm':<22} {'C1':>3} {'C2':>3} {'C3':>3} {'C4':>3} {'C5 lvl':>6} "
          f"{'C6 lvl':>6} {'C5 Δ':>5} {'C6 Δ':>5} {'C7':>8}")
    for lab, _, _, _ in ARMS:
        c = criteria(prim, repl, lab)
        if not c["powered_v4"]:
            print(f"  {lab:<22} UNDERPOWERED on the primary era")
            continue
        yn = lambda v: "yes" if v else "no"  # noqa: E731
        print(f"  {lab:<22} {yn(c['C1']):>3} {yn(c['C2']):>3} {yn(c['C3']):>3} "
              f"{yn(c['C4']):>3} {yn(c['C5_level']):>6} {yn(c['C6_level']):>6} "
              f"{yn(c['C5_delta']):>5} {yn(c['C6_delta']):>5} {c['C7']:>8}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args(argv)

    sim_cfg = load_sim_cfg()
    commission, slip = SIM._cost_knobs(sim_cfg)
    if abs(float(sim_cfg["portfolio_value"]) * float(sim_cfg["risk_per_trade_pct"])
           - MAX_LOSS_ABS) > 1e-9:
        print("G2 FAILED — config dollar stop differs from the frozen harness's.")
        return 1

    hdr("bear_fast_exit — does a fast exit make a bear debit pay, net of costs?")
    print(f"""  Registration: research/pre-registrations/f2_management/bear_fast_exit.md
  HEADLINE cost   config/backtest.yml now: ${commission:.2f} per contract per leg per
                  side, slippage {slip:g} of the quoted spread. Grades the verdict.
  SECONDARY cost  ${commission:.2f} plus {SECONDARY_SLIPPAGE:g} of the quoted spread per leg
                  per side, ARM Q fallback ladder. Declared; never the headline.
  Marks are daily closes. A session-1 exit is the entry-day close; an exit
  inside that session at another price cannot be replayed.
  SEAL: no outcome is computed on a signal date >= {SEAL_START}.""")

    requested = era_mod.requested_era()
    quotes = QuoteBook()
    prim = evaluate_era(requested, sim_cfg, quotes, primary=True)
    repl = None
    if prim["era"] != REPLICATION_ERA:
        repl = evaluate_era(REPLICATION_ERA, sim_cfg, quotes, primary=False)

    lines = {}
    for ev in [prim] + ([repl] if repl else []):
        hdr(f"ERA {ev['era']} — {'PRIMARY' if ev['primary'] else 'REPLICATION'}")
        print_census(ev)
        print_exit_mix(ev)
        lines[(ev["era"], "headline")] = print_line(ev, "_net", "HEADLINE net R")
        if ev["g4_uncostable"]:
            sub(f"SECONDARY net R — {ev['era']}")
            print("  UNCOSTABLE — G4 fired: the quote census above is the result; "
                  "no criterion is graded on this line.")
        else:
            lines[(ev["era"], "secondary")] = print_line(ev, "_net2",
                                                         "SECONDARY net R (declared)")
        print_wide(ev)

    hdr("VERDICT")
    if repl is None:
        print(f"  replication-era run ({prim['era']}) — no joint verdict is printed "
              f"from one era.")
        return 0
    pe, re_ = prim["era"], repl["era"]
    print_criteria(lines[(pe, "headline")], lines[(re_, "headline")], "HEADLINE")
    v, arms = verdict(lines[(pe, "headline")], lines[(re_, "headline")])
    print(f"\n  VERDICT (headline, ${commission:.2f}/contract, slippage {slip:g}): {v}")
    for a in arms:
        print(f"    {a}")
    if prim["g4_uncostable"]:
        print(f"  VERDICT (secondary, + {SECONDARY_SLIPPAGE:g} of spread): UNCOSTABLE")
    elif (re_, "secondary") in lines:
        print_criteria(lines[(pe, "secondary")], lines[(re_, "secondary")], "SECONDARY")
        v2, arms2 = verdict(lines[(pe, "secondary")], lines[(re_, "secondary")])
        print(f"\n  VERDICT (secondary, + {SECONDARY_SLIPPAGE:g} of spread, declared): {v2}")
        for a in arms2:
            print(f"    {a}")
    else:
        print(f"  VERDICT (secondary): replication era {re_} UNCOSTABLE — C2/C4 "
              f"cannot be graded on this line.")
    print(f"""
  C7 FORWARD is PENDING: a registration accepted on or after 2026-10-09 is not a
  sealed reader, so its forward window opens only when the holdout seal lifts
  (floor {C7_MIN_DATES} dates and {C7_MIN_ROWS} rows). A pending C7 ships nothing.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
