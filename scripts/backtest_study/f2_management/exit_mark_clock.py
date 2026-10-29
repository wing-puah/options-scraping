"""exit_mark_clock — does a closing-mid daily mark make better exits?

Registration: research/pre-registrations/f2_management/exit_mark_clock.md
(registered 2026-10-29). IMMUTABLE: every arm, gate, bar and verdict below is
transcribed from it. Read that file before changing anything here.

WHAT IT DOES
------------
Production marks a leg on its closing mid every day, except on a JUNK day
(`simulate._is_junk_quote`), where `simulate.junk_day_mark` marks it at the
day's last trade (`barchart_last`) or carries an older good mark
(`barchart_stale`), capped by the no-bid ceiling. The two arms:

    ARM P   production as it is: `junk_day_mark` unchanged.
    ARM M   on a junk day with a TWO-SIDED quote (`_close_mid` returns a
            value), the leg is marked at that day's closing mid, tagged
            `barchart`. A junk day with no bid falls through to ARM P.

Each arm re-simulates every stored row cache-only on its STORED legs, the way
`scripts.backtest --reprice-stale` does: the candidate comes from the local
AnalysisClaude export, its expiry is pinned to the stored row
(`identity.pin_stored_expiry`), it is rebuilt by the production classifier and
priced by production's engine. Results rows go through `Play.simulate`, proxy
rows through `proxy._evaluate(allow_probe=False)`. A row is compared only when
both arms rebuilt the stored legs (`identity.same_legs`).

ARM M is installed by `arm()`, a scoped context manager that swaps
`simulate.junk_day_mark` and ALWAYS restores the original (try/finally). No
production file is edited; the frozen `lib/harness.py` is not used.

POPULATION
----------
Graded: multi-leg rows (two or more legs) signal-dated strictly AFTER
`REGISTERED_ON`, on BacktestResults (PRIMARY) and BacktestProxy (SECONDARY),
v4 only. Every one of those dates is inside the holdout seal
(`lib/era.py`, from 2026-09-23), and a registration made after 2026-10-09
cannot be a sealed reader, so the graded set is EMPTY until the seal lifts.
The study counts those rows (counts only) and prints UNDERPOWERED.

While the graded set is empty it also prints a DESCRIPTIVE in-sample block on
the unsealed v4 rows on or before the registration date, so the operator can
see the replay works. That block is labelled, prints no verdict token, and is
never read by `verdict()`.

GATES
-----
    G-REPRO  ARM P reproduces >= 98% of the stored graded rows on the outcome
             triple, per tab. Below: refuse (exit 4). Not evaluable on 0 rows.
    G-THIN   >= 25 affected dates on PRIMARY, else UNDERPOWERED.
    G-LOOK   instrumented in both arms (`LookProbe`): every `_snap_asof` snap
             is on or before its day, and every junk-day mark reads its own
             day's row (ARM M's mid) or an earlier one, never a day after the
             grid day being marked. A violation refuses the run (exit 5).

No network call, no tab write: history is read with
`plan_option_histories(cache_only=True)`, the proxy runs with
`allow_probe=False`, and nothing here imports a Sheets or Drive writer.

Run:
    python -m scripts.backtest_study run exit_mark_clock
"""
from __future__ import annotations

import argparse
import copy
import csv
import logging
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import yaml  # noqa: E402

from lib.barchart.options import cache_path, parse_history_details  # noqa: E402
from scripts.backtest import simulate as SIM  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _weekday_grid  # noqa: E402
from scripts.backtest.legs import parse_legs  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402

DESIGNED_REFUSAL_EXIT_CODES = frozenset({2, 3, 4, 5})
EXIT_G_REPRO = 4
EXIT_G_LOOK = 5

REGISTRATION = "research/pre-registrations/f2_management/exit_mark_clock.md"
CONFIG_REL = "config/backtest.yml"
SIMULATE_REL = "scripts/backtest/simulate.py"
OUT_CSV = ROOT / "backtests" / "study_output" / "exit_mark_clock-latest.csv"

# --- registered constants ------------------------------------------------------
REGISTERED_ON = date(2026, 10, 29)   # graded rows are signal-dated strictly after
ERA = "v4"
G_REPRO_MIN = 0.98
G_THIN_MIN_DATES = 25
TABS = (("PRIMARY", "results", "BacktestResults"),
        ("SECONDARY", "proxy", "BacktestProxy"))
OPEN = "open_at_data_end"
# Exits that are the path running out rather than a rule firing.
PATH_ENDS = frozenset({"cap_open", "expired"})
VERDICTS = ("CANDIDATE", "CONTRARY", "NULL", "UNDERPOWERED")

CSV_COLS = ("block", "tab", "signal_date", "ticker", "play", "n_legs",
            "p_exit_reason", "p_days_held", "p_pnl", "m_exit_reason", "m_days_held",
            "m_pnl", "delta", "affected", "reproduced")


# --- the two marks ---------------------------------------------------------------

def mid_mark(original):
    """ARM M's junk-day mark: the closing mid when the quote is two-sided,
    else `original` (ARM P) unchanged, so the no-bid ceiling stays."""
    def junk_day_mark_mid(row, q_day, series, details, expiration=None):
        mid = SIM._close_mid(row)
        if mid is not None:
            return mid, "barchart", q_day
        return original(row, q_day, series, details, expiration)
    junk_day_mark_mid.arm_m = True
    return junk_day_mark_mid


class LookProbe:
    """G-LOOK, recorded while an arm runs.

    `_price_leg` calls `_snap_asof(series, key, day, ...)` with the grid day
    being marked and then, on a junk day, `junk_day_mark(row, q_day, ...)`. The
    probe remembers the last `day` and checks each junk-day mark against it.
    """

    def __init__(self):
        self.day = None
        self.violations: list[str] = []
        self.snaps = 0
        self.junk_marks = 0
        self.mid_marks = 0
        self.mid_earlier_row = 0   # ARM M mid read q_day < grid day (descriptive)

    def snap(self, key, day, snap):
        self.snaps += 1
        self.day = day
        if snap is not None and snap > day:
            self.violations.append(f"_snap_asof {key}: snap {snap} after day {day}")

    def junk(self, arm, row, q_day, details, out, used_mid):
        self.junk_marks += 1
        day = self.day
        if day is not None and q_day > day:
            self.violations.append(f"ARM {arm}: junk row {q_day} after grid day {day}")
        if out is not None and out[2] is not None and out[2] > q_day:
            self.violations.append(f"ARM {arm}: mark snap {out[2]} after its row {q_day}")
        if used_mid:
            self.mid_marks += 1
            own = (details or {}).get(q_day)
            if own is not row and own != row:
                self.violations.append(f"ARM {arm}: mid read a row not dated {q_day}")
            if day is not None and q_day < day:
                self.mid_earlier_row += 1


@contextmanager
def arm(name: str, probe: LookProbe | None = None):
    """Install ARM `name` ("P" or "M") on `simulate` for the block's duration.

    Both arms install the G-LOOK probe; only M changes the mark. The originals
    are restored in `finally`, so an exception inside the block cannot leave
    production's engine patched.
    """
    if name not in ("P", "M"):
        raise ValueError(f"unknown arm {name!r}")
    probe = probe if probe is not None else LookProbe()
    orig_jdm, orig_snap = SIM.junk_day_mark, SIM._snap_asof
    rule = orig_jdm if name == "P" else mid_mark(orig_jdm)

    def snap_probe(series, key, day, expiration=None):
        price, snap = orig_snap(series, key, day, expiration)
        probe.snap(key, day, snap)
        return price, snap

    def jdm_probe(row, q_day, series, details, expiration=None):
        used_mid = name == "M" and SIM._close_mid(row) is not None
        out = rule(row, q_day, series, details, expiration)
        probe.junk(name, row, q_day, details, out, used_mid)
        return out

    try:
        SIM.junk_day_mark = jdm_probe
        SIM._snap_asof = snap_probe
        yield probe
    finally:
        SIM.junk_day_mark = orig_jdm
        SIM._snap_asof = orig_snap


# --- population ------------------------------------------------------------------

def _sig(r) -> date | None:
    try:
        return date.fromisoformat(str(r.get("signal_date") or "").strip()[:10])
    except ValueError:
        return None


def is_forward(r, registered_on: date = REGISTERED_ON) -> bool:
    """Graded population: signal-dated strictly after the registration date."""
    d = _sig(r)
    return d is not None and d > registered_on


def forward_rows(rows, registered_on: date = REGISTERED_ON) -> list:
    return [r for r in rows if is_forward(r, registered_on)]


def n_legs(r) -> int:
    return len(parse_legs(r.get("legs", "") or "") or [])


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def outcome(r) -> tuple | None:
    """The registered outcome triple, or None when the row is not priced."""
    if r is None:
        return None
    pnl, dh = _f(r.get("realized_pnl_abs")), _f(r.get("days_held"))
    if pnl is None or dh is None:
        return None
    return (str(r.get("exit_reason") or ""), int(dh), round(pnl, 2))


# --- grading ---------------------------------------------------------------------

def pair_rows(pairs):
    """`pairs`: [(signal_date, p_row, m_row)]. Returns the gradable pairs: both
    arms priced, neither `open_at_data_end`."""
    out = []
    for d, p, m in pairs:
        if outcome(p) is None or outcome(m) is None:
            continue
        if p.get("path_status") == OPEN or m.get("path_status") == OPEN:
            continue
        out.append((d, p, m))
    return out


def per_date_deltas(pairs) -> dict:
    """{affected date: sum over that date's rows of pnl(M) - pnl(P)}."""
    by_date: dict = defaultdict(float)
    affected: set = set()
    for d, p, m in pair_rows(pairs):
        by_date[d] += outcome(m)[2] - outcome(p)[2]
        if outcome(m) != outcome(p):
            affected.add(d)
    return {d: round(by_date[d], 2) for d in sorted(affected)}


def halves(dates: list) -> tuple[list, list]:
    """Chronological halves of the affected dates; an odd middle date goes to
    the second half."""
    dates = sorted(dates)
    k = len(dates) // 2
    return dates[:k], dates[k:]


def estimators(deltas: dict) -> dict:
    vals = [deltas[d] for d in sorted(deltas)]
    h1, h2 = halves(list(deltas))
    return {
        "n": len(vals),
        "total": round(sum(vals), 2),
        "median": round(statistics.median(vals), 2) if vals else 0.0,
        "h1": round(sum(deltas[d] for d in h1), 2),
        "h2": round(sum(deltas[d] for d in h2), 2),
        "positive": sum(v > 0 for v in vals),
    }


def verdict(deltas: dict, min_dates: int = G_THIN_MIN_DATES) -> tuple[str, dict]:
    """The registered verdict on one tab's per-date deltas."""
    e = estimators(deltas)
    if e["n"] < min_dates:
        return "UNDERPOWERED", e
    if e["total"] > 0 and e["median"] > 0 and e["h1"] > 0 and e["h2"] > 0:
        return "CANDIDATE", e
    if e["total"] < 0 and e["median"] < 0:
        return "CONTRARY", e
    return "NULL", e


def repro_rate(stored: dict, base: dict) -> tuple[int, int]:
    """(reproduced, stored): ARM P matches the stored row's legs and triple."""
    from scripts.backtest.shared.identity import same_legs
    ok = 0
    for k, s in stored.items():
        b = base.get(k)
        if b is not None and same_legs(b, s) and outcome(b) == outcome(s):
            ok += 1
    return ok, len(stored)


# --- the replay (cache only) -----------------------------------------------------

def registration_sha() -> str:
    out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%H", "-1", "--",
                          REGISTRATION], cwd=ROOT, capture_output=True, text=True)
    return out.stdout.strip()


def load_config(sha: str) -> dict:
    """`config/backtest.yml` as committed with the registration."""
    out = subprocess.run(["git", "show", f"{sha}:{CONFIG_REL}"], cwd=ROOT,
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"cannot read {CONFIG_REL} at {sha}: {out.stderr.strip()}")
    return yaml.safe_load(out.stdout)


def _differs(sha: str, rel: str) -> bool:
    out = subprocess.run(["git", "diff", "--quiet", sha, "--", rel], cwd=ROOT)
    return out.returncode != 0


def read_stored(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh)
                if str(r.get("realized_pnl_abs") or "").strip()]


class Replay:
    """Cache-only re-simulation of stored rows, mirroring `--reprice-stale`."""

    def __init__(self, analysis_path: Path, cfg: dict):
        from scripts.backtest import core
        from scripts.backtest.shared.analysis_io import load_analysis_csv
        from scripts.backtest.shared.identity import identity_key
        self.cfg = cfg
        self.sim_cfg = cfg["simulation"]
        self.proxy_cfg = cfg.get("proxy", {}) or {}
        self.spread_pct = self.sim_cfg.get("spread_width_pct", 0.02)
        self.veto = (cfg.get("entry") or {}).get("structure_veto") or ()
        self.tf_s = cfg.get("structure_override")
        cands, self.mregime = load_analysis_csv(analysis_path, None, None)
        core._attach_rollup_metrics(cands)
        self.by_key: dict = {}
        for c in cands:
            self.by_key.setdefault(identity_key(c["signal_date"], c["ticker"],
                                                c.get("play", "")), c)
        self._plan = None

    def _cands(self, rows: dict, regime):
        from scripts.backtest.shared.identity import pin_stored_expiry
        out = {}
        for k, r in rows.items():
            if k not in self.by_key:
                continue
            c = copy.deepcopy(self.by_key[k])
            pin_stored_expiry(c, r)
            c["market_regime"] = regime(self.mregime.get(c["date"], ""))
            out[k] = c
        return out

    def results(self, rows: dict) -> dict:
        from scripts.backtest.plays import build_matched_plays
        from scripts.backtest.shared.history import plan_option_histories
        from scripts.backtest.shared.identity import identity_key
        cs = self._cands(rows, lambda s: s)
        plays, contracts, needed, _ = build_matched_plays(
            list(cs.values()), self.spread_pct, self.tf_s, self.veto)
        if self._plan is None:
            self._plan = plan_option_histories(list(contracts.values()), needed,
                                               cache_only=True)
        out = {}
        for p in plays:
            k = identity_key(p.c["signal_date"], p.c["ticker"], p.c.get("play", ""))
            res = p.simulate(self._plan.series_map, self._plan.details_map,
                             self.sim_cfg, self.spread_pct)
            out[k] = res if res and outcome(res) is not None else None
        return out

    def proxy(self, rows: dict) -> dict:
        from scripts.backtest import proxy
        from scripts.backtest.plays import classify_and_build
        cs = self._cands(rows, proxy._regime_prefix)
        out = {}
        for k, c in cs.items():
            pr = classify_and_build(c, self.spread_pct, None, self.veto)
            r = proxy._evaluate(*pr, c, self.proxy_cfg, self.sim_cfg, self.spread_pct,
                                "exit_mark_clock", False)
            out[k] = r if outcome(r) is not None else None
        return out


_DETAILS: dict = {}


def _details(lg) -> dict:
    k = (lg.ticker, lg.expiration, lg.strike, lg.opt_type)
    if k not in _DETAILS:
        p = cache_path(HISTORY_CACHE, lg.ticker, lg.expiration, lg.strike, lg.opt_type)
        _DETAILS[k] = parse_history_details(p.read_text()) if p.exists() else {}
    return _DETAILS[k]


def exit_on_junk_day(r, signal: date) -> bool:
    """Does the exit's day (grid index `days_held`) have a leg quoted junk?"""
    grid = _weekday_grid(signal, signal + timedelta(days=900))
    dh = int(_f(r["days_held"]))
    if not 1 <= dh <= len(grid):
        return False
    day = grid[dh - 1]
    return any(SIM._is_junk_quote(_details(lg).get(day))
               for lg in (parse_legs(r.get("legs", "") or "") or []))


# --- report ----------------------------------------------------------------------

def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n--- {t}")


def _money(x):
    return f"{x:+,.0f}"


def describe(label, tab, stored, base, pat, keys_sig, csv_rows, block):
    """Every computed line for one tab's population. Returns the deltas
    (multi-leg) for the caller to grade, or not."""
    from scripts.backtest.shared.identity import same_legs
    multi = {k: s for k, s in stored.items() if n_legs(s) >= 2}
    single = {k: s for k, s in stored.items() if n_legs(s) == 1}
    ok, n = repro_rate(multi, base)
    print(f"  stored multi-leg rows {n}; ARM P re-simulated "
          f"{sum(base.get(k) is not None for k in multi)}; reproduced {ok} "
          f"({ok / n:.1%})" if n else "  stored multi-leg rows 0")

    key_of: dict = {}

    def pairs_of(ks):
        out = []
        for k in ks:
            p, m = base.get(k), pat.get(k)
            s = stored[k]
            if p is None or m is None or not same_legs(p, s) or not same_legs(m, s):
                continue
            key_of[id(p)] = k
            out.append((keys_sig[k], p, m))
        return out

    pm = pairs_of(multi)
    graded = pair_rows(pm)
    n_open = len(pm) - len(graded)
    deltas = per_date_deltas(pm)
    all_dates = {d for d, _, _ in graded}
    e = estimators(deltas)
    h1, h2 = halves(list(deltas))
    print(f"  compared rows {len(graded)} on {len(all_dates)} dates "
          f"(excluded {n_open} open_at_data_end in either arm)")
    print(f"  affected dates {e['n']}  total delta {_money(e['total'])}  median per-date "
          f"delta {_money(e['median'])}  positive dates {e['positive']}")
    for name, part, tot in (("first", h1, e["h1"]), ("second", h2, e["h2"])):
        span = f"  ({part[0]} .. {part[-1]})" if part else ""
        print(f"  {name} half of affected dates: {len(part)} dates, delta {_money(tot)}{span}")

    # descriptive lines (registered, never graded)
    sub(f"{label} descriptive lines (not graded)")
    for arm_name, idx in (("ARM P", 1), ("ARM M", 2)):
        fired = [(d, t[idx]) for t in graded for d in [t[0]]
                 if t[idx]["exit_reason"] not in PATH_ENDS]
        nj = sum(exit_on_junk_day(r, d) for d, r in fired)
        neg_pt = sum(1 for t in graded if t[idx]["exit_reason"] == "profit_target"
                     and outcome(t[idx])[2] < 0)
        share = f"{nj / len(fired):.1%}" if fired else "n/a"
        print(f"  {arm_name}: fired exits {len(fired)}, on a junk day {nj} ({share}); "
              f"profit_target exits with net < 0: {neg_pt}")
    by_reason: dict = defaultdict(lambda: [0, 0, 0.0])
    for d, p, m in graded:
        g = by_reason[p["exit_reason"]]
        g[0] += 1
        if outcome(p) != outcome(m):
            g[1] += 1
        g[2] += outcome(m)[2] - outcome(p)[2]
    print(f"  deltas by ARM P exit reason:  {'reason':<14} {'rows':>5} {'affected':>8} "
          f"{'delta':>10}")
    for reason, (nr, na, dl) in sorted(by_reason.items(), key=lambda x: -x[1][0]):
        print(f"  {'':30}{reason:<14} {nr:>5} {na:>8} {_money(dl):>10}")
    ps = pair_rows(pairs_of(single))
    sd = sum(outcome(m)[2] - outcome(p)[2] for _, p, m in ps)
    ns = sum(outcome(m) != outcome(p) for _, p, m in ps)
    print(f"  single-leg rows (never graded): stored {len(single)}, compared {len(ps)}, "
          f"affected {ns}, total delta {_money(sd)}")

    for d, p, m in graded:
        s = stored[key_of[id(p)]]
        csv_rows.append({
            "block": block, "tab": tab, "signal_date": d.isoformat(),
            "ticker": s.get("ticker", ""), "play": (s.get("play", "") or "")[:60],
            "n_legs": n_legs(s),
            "p_exit_reason": p["exit_reason"], "p_days_held": outcome(p)[1],
            "p_pnl": outcome(p)[2], "m_exit_reason": m["exit_reason"],
            "m_days_held": outcome(m)[1], "m_pnl": outcome(m)[2],
            "delta": round(outcome(m)[2] - outcome(p)[2], 2),
            "affected": outcome(m) != outcome(p),
            "reproduced": same_legs(p, s) and outcome(p) == outcome(s),
        })
    return deltas, (ok, n)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    logging.basicConfig(level=logging.ERROR)
    logging.getLogger().setLevel(logging.ERROR)

    hdr("exit_mark_clock — does a closing-mid daily mark make better exits?")
    sha = registration_sha()
    print(f"  Registration: {REGISTRATION} (registered {REGISTERED_ON}, commit "
          f"{sha[:7] or '?'})")
    print("  ARM P  junk-day mark unchanged: last trade, else a carried good mark,")
    print("         with the no-bid ceiling.")
    print("  ARM M  closing mid when the junk quote is two-sided; otherwise ARM P.")
    print(f"  Graded: multi-leg rows signal-dated after {REGISTERED_ON}, era {ERA}.")
    print("  Cache only: no network call, no tab written.")

    requested = era_mod.requested_era()
    paths = era_mod.resolve_paths(requested)
    actual = era_mod.enforce(requested, paths)
    print(f"  ERA: {actual} (requested {requested})")
    if actual != ERA:
        era_mod._refuse(era_mod.EXIT_ERA_MISMATCH,
                        f"the registration fixes era {ERA}; these exports are {actual}.")
    if not sha:
        print("\nFAILED — the registration has no commit; config cannot be pinned.")
        return 1
    cfg = load_config(sha)
    print(f"  config: {CONFIG_REL} at {sha[:7]}"
          f"{'  (working copy DIFFERS; the committed one is used)' if _differs(sha, CONFIG_REL) else ''}")
    if _differs(sha, SIMULATE_REL):
        print(f"  NOTE: {SIMULATE_REL} has changed since the registration commit.")

    from scripts.backtest.shared.identity import identity_key
    replay = Replay(paths["analysis"], cfg)
    probe = LookProbe()

    blocks = {}
    for label, key, tab in TABS:
        raw = read_stored(paths[key])
        fwd = forward_rows(raw)
        fwd_multi = sum(n_legs(r) >= 2 for r in fwd)
        kept, info = era_mod.drop_sealed(raw)
        dates = {_sig(r) for r in kept if _sig(r)}
        if label == "PRIMARY":
            era_mod.require_dates(len(dates), actual)
        graded = {identity_key(r["signal_date"], r["ticker"], r["play"]): r
                  for r in forward_rows(kept)}
        insample = {identity_key(r["signal_date"], r["ticker"], r["play"]): r
                    for r in kept if not is_forward(r)}
        blocks[label] = dict(tab=tab, key=key, n_raw=len(raw), n_fwd=len(fwd),
                             n_fwd_multi=fwd_multi, seal=info, graded=graded,
                             insample=insample)

    hdr("CENSUS")
    for label, b in blocks.items():
        print(f"  {label:<9} {b['tab']}: priced rows {b['n_raw']}; signal-dated after "
              f"{REGISTERED_ON}: {b['n_fwd']} ({b['n_fwd_multi']} multi-leg)")
        print(f"            {era_mod.seal_line(b['seal'])}")
        print(f"            graded rows readable now: {len(b['graded'])} "
              f"({sum(n_legs(r) >= 2 for r in b['graded'].values())} multi-leg)")

    def simulate(b, rows):
        if not rows:
            return {}, {}
        with arm("P", probe):
            base = replay.results(rows) if b["key"] == "results" else replay.proxy(rows)
        with arm("M", probe):
            pat = replay.results(rows) if b["key"] == "results" else replay.proxy(rows)
        return base, pat

    csv_rows: list = []
    graded_out = {}
    for label, b in blocks.items():
        base, pat = simulate(b, b["graded"])
        graded_out[label] = (base, pat)

    any_graded = any(b["graded"] for b in blocks.values())
    insample_out = {}
    if not any_graded:
        for label, b in blocks.items():
            insample_out[label] = simulate(b, b["insample"])

    hdr("G-LOOK — no mark reads a later row")
    print(f"  snaps checked {probe.snaps}; junk-day marks checked {probe.junk_marks}; "
          f"ARM M closing-mid marks {probe.mid_marks}")
    print(f"  ARM M mids read on a carried day's own earlier row (descriptive): "
          f"{probe.mid_earlier_row}")
    if probe.violations:
        print(f"  VIOLATIONS {len(probe.violations)}:")
        for v in probe.violations[:20]:
            print(f"    {v}")
        print("\nREFUSED — G-LOOK: a mark read a row dated after the day it marks.")
        return EXIT_G_LOOK
    print("  PASS — every mark read its own day's row or an earlier one.")

    results = {}
    repro_fail = []
    for label, b in blocks.items():
        hdr(f"GRADED — {label} ({b['tab']}), signal-dated after {REGISTERED_ON}")
        sig = {k: k[0] for k in b["graded"]}
        base, pat = graded_out[label]
        multi = {k: s for k, s in b["graded"].items() if n_legs(s) >= 2}
        if not multi:
            print("  0 graded multi-leg rows.")
            print("  G-REPRO: not evaluable on 0 rows.")
            results[label] = verdict({})
            continue
        deltas, (ok, n) = describe(label, b["tab"], b["graded"], base, pat, sig,
                                   csv_rows, "graded")
        rate = ok / n
        print(f"  G-REPRO: {ok}/{n} = {rate:.1%} (bar {G_REPRO_MIN:.0%}) "
              f"{'PASS' if rate >= G_REPRO_MIN else 'FAIL'}")
        if rate < G_REPRO_MIN:
            repro_fail.append(label)
        results[label] = verdict(deltas)

    if insample_out:
        hdr(f"DESCRIPTIVE — IN-SAMPLE, signal-dated on or before {REGISTERED_ON}")
        print("  Not a gate, not evidence, no verdict. Unsealed v4 rows only (the seal")
        print(f"  withholds every date from {era_mod.SEAL_START}). Shown so the replay")
        print("  can be seen to work.")
        for label, b in blocks.items():
            sub(f"{label} ({b['tab']}) in-sample")
            sig = {k: k[0] for k in b["insample"]}
            base, pat = insample_out[label]
            describe(label, b["tab"], b["insample"], base, pat, sig, csv_rows,
                     "insample_descriptive")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLS)
        w.writeheader()
        w.writerows(csv_rows)

    if repro_fail:
        print(f"\nREFUSED — G-REPRO: ARM P reproduced under {G_REPRO_MIN:.0%} of the "
              f"stored graded rows on {', '.join(repro_fail)}; no grade.")
        return EXIT_G_REPRO

    hdr("VERDICT")
    for label, (tok, e) in results.items():
        thin = (f"G-THIN {'met' if e['n'] >= G_THIN_MIN_DATES else 'not met'}: "
                f"{e['n']} affected dates (need {G_THIN_MIN_DATES})")
        print(f"  {label:<9} {tok}  — {thin}")
        if tok != "UNDERPOWERED":
            print(f"            total {_money(e['total'])}  median {_money(e['median'])}  "
                  f"halves {_money(e['h1'])} / {_money(e['h2'])}")
    print("  The SECONDARY verdict never moves the PRIMARY one. Nothing ships by itself;")
    print("  CANDIDATE lets the operator rule on the junk-day mark.")
    print(f"  positions CSV: {OUT_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
