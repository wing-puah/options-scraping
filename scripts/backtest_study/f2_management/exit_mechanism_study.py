"""Exit-mechanism study: replay stored daily marks under alternative exit rules.

Replays the trades in the era's BacktestResults export using the STORED daily
marks (daily_price_csv) — no scraping, no repricing — and evaluates a grid of
exit variants per side (debit / credit) against the production rules. Same
methodology as Attempts 7/9 (see research.md); the replay engine
mirrors scripts/backtest/simulate.py::_summarize_path exit priority exactly,
and a calibration gate (production rules must reproduce every row's
exit_reason/days_held/realized_pnl_pct) runs before any variant table.

CHANGED 2026-08-15: the main book was `backtests/results.csv`, the rolling file
every backtest run stomps. See MAIN_CSV below for what that cost and why the
export replaced it. `--file` still overrides, so the old path is one flag away.

Selection discipline (Attempt 8/9 lesson): variants are tuned and selected on
the MAIN book ONLY, with leave-one-out and per-month deltas to catch a single
correlated event deciding the sign. backtests/v1_20260625_results.csv is
replayed as a for-context COMPARISON column (debit side only) — never a
selection criterion, and deliberately a different prompt era.

Underlying source for the credit-side breach rules: the short leg(s)' cached
Barchart price-history `Price~` column (backtests/option_history_cache/), the
exact scrapes that produced the marks — close-basis only, like Attempt 9.

Run from the repo root:
  python3 scripts/backtest_study/f2_management/exit_mechanism_study.py --side debit
  python3 scripts/backtest_study/f2_management/exit_mechanism_study.py --side credit
"""
import argparse
import csv
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path, parse_history_details  # noqa: E402
from lib.parsing import to_float as _to_float  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _weekday_grid  # noqa: E402
from scripts.backtest.legs import parse_legs  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402

# --- the two books, and why only ONE of them is era-resolved ----------------
# MAIN is the CURRENT book, resolved through `lib/era.py` so `STUDY_ERA` selects
# it. It used to be `backtests/results.csv` — the rolling file every
# `python3 -m scripts.backtest` run stomps, which is era-blind in the worst way:
# it is whatever the last local run happened to leave behind, with no filename,
# schema, or header saying so. On 2026-08-15 that file held 5 debit rows from a
# thin v4 run and the calibration gate below reported FAILED against it, which
# is a diagnosis of the input rather than of the exit grid. The era-resolved
# BacktestResults export is the same population every other management study
# reads, and it says which era it is.
MAIN_CSV = era.resolve_paths()["results"]

# V1 is PINNED, deliberately and permanently. It is the for-context comparison
# column (debit only, never a selection criterion — see the module docstring's
# selection-discipline note), and its whole value is that it is a DIFFERENT
# prompt era from MAIN. Era-resolving it would make it track MAIN and the
# comparison would silently become a book against itself.
#
# EXEMPT FROM `era.enforce`, for the same reason `load_book(check_era=False)`
# exists: this caller mixes eras BY DESIGN, so the guard's "these exports
# disagree about their era" refusal would be refusing the study's entire point.
# The exemption is scoped to the cross-era agreement check only — MAIN is still
# era-RESOLVED above, so a run still reads the era it asked for.
#
# The exemption does NOT extend to the DATE FLOOR, and that distinction is the
# whole of what `main()`'s `era.require_dates` call adds. The two guards answer
# different questions: `enforce` asks "are these exports the population you
# asked for", which a deliberately cross-era comparison must be allowed to say
# no to; `require_dates` asks "is there enough of it to conclude from", which a
# cross-era comparison is no more exempt from than any other study. On
# 2026-08-15 this study ran a full variant grid, with LOO deltas and per-month
# sign tables, off 10 dates of v4 on the MAIN side — correctly era-exempt and
# still far too thin to read.
V1_CSV = ROOT / "backtests" / "v1_20260625_results.csv"

PATH_CAP_DAYS = 120          # config/backtest.yml simulation.path_cap_days
MAX_LOSS_ABS = 50000 * 0.02  # portfolio_value × risk_per_trade_pct (dollar_stop)

# Production exit profiles — source of truth is config/backtest.yml
# (simulation: block for debit, simulation.credit: override for credit).
# Attempt 10 (2026-07-04): debit trailing_stop_trigger/trailing_stop_pct removed
# from production (see research.md); backtests/results.csv was
# regenerated without it, so trig/trail must stay None here to calibrate.
DEBIT_PROD = dict(pt=0.90, sl=0.75, trig=None, trail=None, tef=0.75)
CREDIT_PROD = dict(pt=0.65, sl=1.00, trig=None, trail=None, tef=None)


def _pct(s):
    """Normalize a pct field: v1 file stores '39.07%', current file plain decimals."""
    s = str(s or "").strip()
    if not s:
        return None
    if s.endswith("%"):
        return float(s.rstrip("%")) / 100
    return float(s)


class Trade:
    def __init__(self, row: dict, load_underlying: bool = False):
        self.row = row
        self.signal_date = date.fromisoformat(row["signal_date"])
        self.ticker = row["ticker"]
        self.structure = row["structure"]
        self.entry_net = float(row["entry_option_price"])
        self.denom = abs(self.entry_net)
        self.contracts = int(row["contracts"])
        self.dte_entry = int(row["dte_entry"])
        self.legs = parse_legs(row["legs"])
        self.short_legs = [l for l in self.legs if l.qty < 0]

        nearest_dte = min((l.expiration - self.signal_date).days for l in self.legs)
        end = self.signal_date + timedelta(days=min(nearest_dte, PATH_CAP_DAYS))
        self.grid = _weekday_grid(self.signal_date, end)
        self.cap_reached_expiry = nearest_dte <= PATH_CAP_DAYS

        self.marks = [None if t == "" else float(t)
                      for t in row["daily_price_csv"].split(",")]
        assert len(self.marks) == len(self.grid), \
            f"{self.ticker} {self.signal_date}: {len(self.marks)} marks vs {len(self.grid)} grid days"

        self.underlying = self._load_underlying() if load_underlying else {}

    def _load_underlying(self) -> dict[date, float]:
        """Underlying Price~ per date from the short leg(s)' cached history CSVs."""
        out: dict[date, float] = {}
        for leg in self.short_legs:
            p = cache_path(HISTORY_CACHE, leg.ticker, leg.expiration, leg.strike, leg.opt_type)
            if not p.exists():
                continue
            details = parse_history_details(p.read_text(), require_mark=False)
            for d, r in details.items():
                v = _to_float(r.get("Price~"))
                if v is not None and d not in out:
                    out[d] = v
        return out

    def pnl_of(self, mark: float) -> float:
        return (mark - self.entry_net) / self.denom

    def dollars(self, pl: float) -> float:
        return pl * self.denom * 100 * self.contracts

    # ── underlying breach thresholds (credit variants) ──
    def breach_thresholds(self, buffer: float) -> list[tuple[str, float]]:
        """[(direction, level)]. Verticals: short strike ± buffer. Straddles /
        strangles (short call AND short put): breakeven basis per Attempt 9
        lesson — strike-basis fires day 1 when the short strike is ~ATM."""
        credit = self.denom
        types = {l.opt_type for l in self.short_legs}
        straddle_like = types == {"Call", "Put"}
        out = []
        for leg in self.short_legs:
            if straddle_like:
                lvl = leg.strike + credit if leg.opt_type == "Call" else leg.strike - credit
            else:
                lvl = leg.strike * (1 + buffer) if leg.opt_type == "Call" \
                    else leg.strike * (1 - buffer)
            out.append(("above" if leg.opt_type == "Call" else "below", lvl))
        return out


def load_trades(path: Path, side: str, load_underlying: bool = False) -> list[Trade]:
    out = []
    for r in csv.DictReader(open(path)):
        e = _to_float(r.get("entry_option_price"))
        if e is None or not r.get("daily_price_csv"):
            continue
        if (side == "debit") != (e > 0):
            continue
        out.append(Trade(r, load_underlying=load_underlying))
    out.sort(key=lambda t: (t.signal_date, t.ticker))
    return out


# ─── Replay engine ─────────────────────────────────────────────────────────────

def replay(t: Trade, pt=None, sl=None, trig=None, trail=None, tef=None,
           be_after=None, und_buffer=None) -> dict:
    """Mirror of _summarize_path's exit scan (simulate.py:139-171) plus two
    experimental rules:
      be_after    — breakeven ratchet: once peak pnl >= be_after, the stop level
                    tightens from -sl to 0 (exit reason 'be_stop').
      und_buffer  — credit-side underlying close-breach stop (short strike ±
                    buffer; breakeven basis for straddles), checked AHEAD of the
                    mark stops the way Attempt 9's '+ mark stops kept' variant
                    ran (exit reason 'underlying_stop').
    Priority: profit_target → trailing_stop → underlying_stop → dollar_stop →
    stop_loss/be_stop → time_exit. dollar_stop/expiry always on, like production.
    """
    te_day = int(t.dte_entry * tef) if tef else None
    ths = t.breach_thresholds(und_buffer) if und_buffer is not None else []
    peak = -1e18
    trailing_active = False
    for i, (day, m) in enumerate(zip(t.grid, t.marks), start=1):
        if m is None:
            continue
        d = (day - t.signal_date).days
        # round away 1-ulp float noise from the 4-decimal CSV round-trip: e.g.
        # (0.3500-1.4)/1.4 = -0.7499999999999999, which misses the sl=0.75
        # boundary production hit when computing from the unrounded scrape.
        pl = round(t.pnl_of(m), 10)
        peak = max(peak, pl)
        if trig is not None and peak >= trig:
            trailing_active = True

        if pt is not None and pl >= pt:
            return dict(exit_reason="profit_target", days_held=i, pnl_pct=pl)
        if trailing_active and trail is not None and pl <= peak - trail:
            return dict(exit_reason="trailing_stop", days_held=i, pnl_pct=pl)
        if ths:
            s = t.underlying.get(day)
            if s is not None and any(
                    (dr == "above" and s > lvl) or (dr == "below" and s < lvl)
                    for dr, lvl in ths):
                return dict(exit_reason="underlying_stop", days_held=i, pnl_pct=pl)
        if t.dollars(pl) <= -MAX_LOSS_ABS:
            return dict(exit_reason="dollar_stop", days_held=i, pnl_pct=pl)
        if be_after is not None and peak >= be_after and pl <= 0:
            return dict(exit_reason="be_stop", days_held=i, pnl_pct=pl)
        if sl is not None and pl <= -sl:
            return dict(exit_reason="stop_loss", days_held=i, pnl_pct=pl)
        if te_day is not None and d >= te_day:
            return dict(exit_reason="time_exit", days_held=i, pnl_pct=pl)

    priced = [(i, m) for i, m in enumerate(t.marks, start=1) if m is not None]
    i, m = priced[-1]
    return dict(exit_reason="expired" if t.cap_reached_expiry else "cap_open",
                days_held=i, pnl_pct=t.pnl_of(m))


# ─── Calibration gate ──────────────────────────────────────────────────────────

def calibrate(trades: list[Trade], prod: dict, label: str) -> bool:
    print("=" * 100)
    # "the main book" rather than "results.csv": the input is era-resolved now,
    # and a header naming a file the run did not read is how a report gets
    # attributed to the wrong population.
    print(f"CALIBRATION ({label}): production rules replayed vs the main book's actuals")
    print("=" * 100)
    ok = 0
    for t in trades:
        rep = replay(t, **prod)
        want = (t.row["exit_reason"], int(float(t.row["days_held"])),
                round(_pct(t.row["realized_pnl_pct"]), 4))
        got = (rep["exit_reason"], rep["days_held"], round(rep["pnl_pct"], 4))
        match = want == got
        ok += match
        if not match:
            print(f"  FAIL {t.signal_date} {t.ticker:5s} {t.structure:18s} "
                  f"want={want} got={got}")
    print(f"  → {ok}/{len(trades)} matched")
    if ok != len(trades):
        print("  CALIBRATION FAILED — variant numbers below are NOT trustworthy.")
    return ok == len(trades)


# ─── Evaluation / reporting ────────────────────────────────────────────────────

def run_variant(trades: list[Trade], cfg: dict) -> list[dict]:
    out = []
    for t in trades:
        rep = replay(t, **cfg)
        rep["dollars"] = t.dollars(rep["pnl_pct"])
        rep["dollars_per_ct"] = rep["dollars"] / t.contracts
        rep["trade"] = t
        out.append(rep)
    return out


def summarize(name: str, reps: list[dict], base: list[dict] | None,
              v1_total: float | None = None) -> None:
    n = len(reps)
    tot = sum(r["dollars"] for r in reps)
    tot_ct = sum(r["dollars_per_ct"] for r in reps)
    wins = sum(1 for r in reps if r["pnl_pct"] > 0)
    med = sorted(r["dollars"] for r in reps)[n // 2]
    reasons = Counter(r["exit_reason"] for r in reps)
    line = (f"{name:44s} total=${tot:+9.0f}  $/ct={tot_ct:+8.0f}  "
            f"win={wins:3d}/{n}  med=${med:+6.0f}")
    if base is not None:
        deltas = [r["dollars"] - b["dollars"] for r, b in zip(reps, base)]
        d_tot = sum(deltas)
        # leave-one-out on the IMPROVEMENT: does it survive removing its single
        # biggest contributor? (Attempt 8/9: one event deciding the sign.)
        loo = d_tot - max(deltas) if deltas else 0.0
        line += f"  Δ=${d_tot:+8.0f}  Δ-LOO=${loo:+8.0f}"
    if v1_total is not None:
        line += f"  [v1 cmp: ${v1_total:+9.0f}]"
    print(line)
    print(f"{'':44s} exits: " + "  ".join(f"{k}={v}" for k, v in reasons.most_common()))


def monthly_delta(name: str, reps: list[dict], base: list[dict]) -> None:
    by_month = defaultdict(float)
    for r, b in zip(reps, base):
        by_month[r["trade"].signal_date.strftime("%Y-%m")] += r["dollars"] - b["dollars"]
    parts = "  ".join(f"{m}:{v:+.0f}" for m, v in sorted(by_month.items()) if abs(v) >= 1)
    print(f"    per-month Δ vs prod: {parts or '(no change)'}")


def flips(name: str, reps: list[dict], base: list[dict], top: int = 6) -> None:
    ch = [(r["dollars"] - b["dollars"], r, b) for r, b in zip(reps, base)
          if abs(r["dollars"] - b["dollars"]) >= 1]
    ch.sort(key=lambda x: x[0])
    print(f"    biggest movers ({len(ch)} rows changed):")
    for d, r, b in (ch[:top // 2] + ch[-top // 2:] if len(ch) > top else ch):
        t = r["trade"]
        print(f"      {d:+8.0f}  {t.signal_date} {t.ticker:5s} {t.structure:18s} "
              f"{b['exit_reason']}(${b['dollars']:+.0f} d{b['days_held']}) → "
              f"{r['exit_reason']}(${r['dollars']:+.0f} d{r['days_held']})")


# ─── Variant grids ─────────────────────────────────────────────────────────────

DEBIT_VARIANTS: list[tuple[str, dict]] = [
    ("PROD pt.90 sl.75 no-trail tef.75", DEBIT_PROD),
    # trail lever — production has no trail since Attempt 10, so every trail
    # variant must set BOTH trig and trail explicitly (a single-knob override
    # inherits None for the other and silently no-ops)
    ("trail .25 trig .50", {**DEBIT_PROD, "trig": 0.50, "trail": 0.25}),
    ("trail .40 trig .50", {**DEBIT_PROD, "trig": 0.50, "trail": 0.40}),
    ("trail .50 trig .50", {**DEBIT_PROD, "trig": 0.50, "trail": 0.50}),
    ("trail .25 trig .75", {**DEBIT_PROD, "trig": 0.75, "trail": 0.25}),
    ("trail .40 trig .75", {**DEBIT_PROD, "trig": 0.75, "trail": 0.40}),
    ("trail .50 trig .75", {**DEBIT_PROD, "trig": 0.75, "trail": 0.50}),
    # profit-target sweep on the no-trail base
    ("pt .75 no trail", {**DEBIT_PROD, "pt": 0.75, "trig": None, "trail": None}),
    ("pt 1.10 no trail", {**DEBIT_PROD, "pt": 1.10, "trig": None, "trail": None}),
    ("pt 1.25 no trail", {**DEBIT_PROD, "pt": 1.25, "trig": None, "trail": None}),
    # profit-target sweep with a loose trail kept as reversal protection
    ("pt 1.10 trail .50 trig .75", {**DEBIT_PROD, "pt": 1.10, "trig": 0.75, "trail": 0.50}),
    ("pt 1.25 trail .50 trig .75", {**DEBIT_PROD, "pt": 1.25, "trig": 0.75, "trail": 0.50}),
    # breakeven ratchet (stop tightens to 0 once peak >= threshold)
    ("BE ratchet @.50, no trail", {**DEBIT_PROD, "trig": None, "trail": None, "be_after": 0.50}),
    ("BE ratchet @.75, no trail", {**DEBIT_PROD, "trig": None, "trail": None, "be_after": 0.75}),
    ("BE ratchet @.50 + trail .50 trig .75",
     {**DEBIT_PROD, "trig": 0.75, "trail": 0.50, "be_after": 0.50}),
    # time-exit sanity on the no-trail base
    ("no trail, tef null", {**DEBIT_PROD, "trig": None, "trail": None, "tef": None}),
    ("no trail, tef .85", {**DEBIT_PROD, "trig": None, "trail": None, "tef": 0.85}),
]

CREDIT_VARIANTS: list[tuple[str, dict]] = [
    ("PROD pt.65 sl 1x", CREDIT_PROD),
    # profit-target lever (Attempt 8/9: both TSLA peaked at 0.59x)
    ("pt .50", {**CREDIT_PROD, "pt": 0.50}),
    ("pt .55", {**CREDIT_PROD, "pt": 0.55}),
    # stop lever
    ("sl none (dollar stop only)", {**CREDIT_PROD, "sl": None}),
    ("pt .50 sl none", {**CREDIT_PROD, "pt": 0.50, "sl": None}),
    ("sl 1.5x", {**CREDIT_PROD, "sl": 1.50}),
    # wide trail once >=0.5x credit captured (Attempt 8 'possible knob')
    ("trail .50 trig .50", {**CREDIT_PROD, "trig": 0.50, "trail": 0.50}),
    ("trail .50 trig .50, pt none", {**CREDIT_PROD, "pt": None, "trig": 0.50, "trail": 0.50}),
    # underlying close-breach stop (±1% buffer; breakeven basis for straddles),
    # ADDITIONAL to the mark stops — Attempt 9's best-surviving shape
    ("und ±1% + mark stops", {**CREDIT_PROD, "und_buffer": 0.01}),
    ("und ±1% + pt .50", {**CREDIT_PROD, "pt": 0.50, "und_buffer": 0.01}),
    ("und ±2% + mark stops", {**CREDIT_PROD, "und_buffer": 0.02}),
]


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--side", choices=["debit", "credit"], required=True)
    ap.add_argument("--file", default=str(MAIN_CSV))
    ap.add_argument("--no-v1", action="store_true",
                    help="skip the v1 comparison column (debit side)")
    args = ap.parse_args()

    side = args.side
    prod = DEBIT_PROD if side == "debit" else CREDIT_PROD
    variants = DEBIT_VARIANTS if side == "debit" else CREDIT_VARIANTS
    need_underlying = side == "credit"

    trades = load_trades(Path(args.file), side, load_underlying=need_underlying)
    print(f"{side} trades loaded from {args.file}: {len(trades)}")

    # The shared power floor (exit 2), on the CURRENT side only. Stated on
    # distinct signal dates because that is the unit every selection-relevant
    # table below is cut by: `_delta_by_month` reads per-month signs and the
    # Δ-LOO column drops one trade at a time against a book whose date spread is
    # the only thing separating a rule from a single correlated event.
    #
    # The V1 side is deliberately NOT floored. It is the frozen for-context
    # comparison column, never a selection criterion (see the module docstring),
    # so its size is a property of a pinned file rather than of an era that can
    # accrue — a floor there could only ever refuse permanently.
    #
    # The era named in the refusal is the one REQUESTED, not one detected off
    # the file. Detecting it is the job of `era.enforce`, which this study is
    # exempt from by design (see V1_CSV above), and `--file` can point MAIN at
    # any export at all — so the honest label here is what was asked for.
    era.require_dates(len({t.signal_date for t in trades}), era.requested_era(),
                      what=f"the shared research floor, on the {side} side of "
                           f"the CURRENT book")

    if need_underlying:
        thin = [t for t in trades
                if sum(1 for d in t.grid if d in t.underlying) < len(t.grid) // 2]
        for t in thin:
            print(f"  WARN underlying coverage <50%: {t.signal_date} {t.ticker}")

    calibrate(trades, prod, side)

    v1_trades = []
    if side == "debit" and not args.no_v1 and V1_CSV.exists():
        v1_trades = load_trades(V1_CSV, side)
        print(f"\nv1 comparison set (NOT used for selection): {len(v1_trades)} debit rows")

    base = run_variant(trades, prod)
    print()
    print("=" * 100)
    print(f"VARIANTS ({side}) — selected on results.csv only; Δ-LOO = improvement "
          f"minus its single biggest contributing trade")
    print("=" * 100)
    for name, cfg in variants:
        reps = run_variant(trades, cfg)
        v1_total = (sum(r["dollars"] for r in run_variant(v1_trades, cfg))
                    if v1_trades else None)
        summarize(name, reps, base if cfg is not prod else None, v1_total)
        if cfg is not prod:
            monthly_delta(name, reps, base)
            flips(name, reps, base)
        print()


if __name__ == "__main__":
    main()
