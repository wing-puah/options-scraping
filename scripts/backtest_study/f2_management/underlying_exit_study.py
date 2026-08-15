"""RETIRED 2026-08-14 — see scripts/study_map/catalog.py's entry for this study.

Its second input, backtests/v2_BacktestResults_nocreditdiff.csv, is gitignored
scratch (backtests/* is disposable, .gitignore:15-19) that was deleted long
ago and is not recoverable. The genuine rename of that file,
backtests/v2_results_nocreditdiff.csv, does still exist — but this study's
OTHER input (backtests/results.csv, the rolling file every `backtest.py` run
stomps) has 0 credit rows today, so `load_credit_rows` would return `[]` and
the study would emit a degenerate empty report regardless of the rename. Do
not repoint OLD_CSV — see research/next-steps.md §0c(B) for the full diagnosis.

(2026-08-15: the OTHER input was repointed, and only in the sense of ceasing to
be a fixed name at all — `NEW_CSV` now resolves per era through `lib/era.py`
instead of naming `backtests/results.csv`, the rolling file every backtest run
stomps. That closes an era-blindness this study shared with four others; it
does not revive the study, whose blocking input remains OLD_CSV.)

Its recorded verdict (Attempt 9, NULL — nothing shipped) already lives in
research/archive/02-credit-debit-split-attempts-8-12.md and is
quoted in scripts/study_map/catalog.py — it does not need this script to run
again. `run --all` (scripts/backtest_study/run.py) excludes this study from
the bulk run; `run underlying_exit_study` still runs it directly, with a
printed retirement notice, for anyone who wants to see it fail on the missing
file.

---

One-off study: underlying-price-based exits for credit spreads.

Replays the credit trades in backtests/results.csv (new run, credit/debit split)
using the STORED daily marks (daily_price_csv) joined with the underlying price
per day, and evaluates a grid of underlying-breach stop rules against the
actual mark-based exits (old run = v2_BacktestResults_nocreditdiff.csv,
new run = results.csv).

Underlying source: the `Price~` column of the short leg's cached Barchart
price-history CSV (backtests/option_history_cache/) — the exact same scrapes
that produced the stored marks, so dates align 1:1. No yfinance.
Consequence: rules are CLOSE-basis only (no intraday touch variants).

Run from the repo root:  python3 scripts/backtest_study/f2_management/underlying_exit_study.py
"""
import csv
import re
import sys
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
# NEW is the CURRENT book, resolved through `lib/era.py` so `STUDY_ERA` selects
# it. It used to be `backtests/results.csv` — the rolling file every
# `python3 -m scripts.backtest` run stomps, so it named no population at all:
# whatever the last local run left behind, with nothing in the filename or
# schema to say which prompt era that was. Resolving it does NOT un-retire this
# study (see the retirement notice above: OLD is gone and unrecoverable); it
# stops the surviving half of the input pair from being era-blind while the
# retirement stands.
NEW_CSV = era.resolve_paths()["results"]

# OLD is PINNED to v2, deliberately. The whole design is old-run-vs-new-run
# across a production rule change, so this side must NOT track the current era —
# era-resolving it would collapse the comparison into a book against itself.
# The name is also NOT repointed at the surviving `backtests/v2_results_
# nocreditdiff.csv`: per the retirement notice, that rename has 0 credit rows
# today, so a repoint would trade a loud missing-file failure for a silent
# degenerate empty report.
#
# EXEMPT FROM `era.enforce`, for the same reason `load_book(check_era=False)`
# exists: this caller mixes eras BY DESIGN, and the guard's "these exports
# disagree about their era" refusal would be refusing the comparison itself. The
# exemption covers only that cross-era agreement check — NEW is still
# era-RESOLVED above.
OLD_CSV = ROOT / "backtests" / "v2_BacktestResults_nocreditdiff.csv"

PATH_CAP_DAYS = 120          # config/backtest.yml simulation.path_cap_days
MAX_LOSS_ABS = 50000 * 0.02  # portfolio_value × risk_per_trade_pct (dollar_stop)


def _pct(s):
    """Normalize a pct field: old file stores '39.07%', new file plain decimals."""
    s = str(s or "").strip()
    if not s:
        return None
    if s.endswith("%"):
        return float(s.rstrip("%")) / 100
    return float(s)


def _strip_qty(legs_str: str) -> str:
    """Qty-stripped legs key so sizing changes don't break old↔new matching."""
    return re.sub(r"\s+[+-]?\d+\s*$", "", legs_str, flags=re.M)


def load_credit_rows(path: Path) -> list[dict]:
    out = []
    for r in csv.DictReader(open(path)):
        e = _to_float(r.get("entry_option_price"))
        if e is not None and e < 0:
            out.append(r)
    return out


# ─── Per-trade context ─────────────────────────────────────────────────────────

class Trade:
    def __init__(self, row: dict):
        self.row = row
        self.signal_date = date.fromisoformat(row["signal_date"])
        self.ticker = row["ticker"]
        self.structure = row["structure"]
        self.entry_net = float(row["entry_option_price"])   # < 0
        self.credit = abs(self.entry_net)
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

        self.underlying = self._load_underlying()

    def _load_underlying(self) -> dict[date, float]:
        """Underlying Price~ per date from the short leg(s)' cached history CSVs."""
        out: dict[date, float] = {}
        for leg in self.short_legs:
            p = cache_path(HISTORY_CACHE, leg.ticker, leg.expiration, leg.strike, leg.opt_type)
            if not p.exists():
                print(f"  WARN: no cache file {p.name}")
                continue
            details = parse_history_details(p.read_text(), require_mark=False)
            for d, r in details.items():
                v = _to_float(r.get("Price~"))
                if v is not None and d not in out:
                    out[d] = v
        return out

    def pnl_of(self, mark: float) -> float:
        return (mark - self.entry_net) / self.credit

    # ── breach thresholds ──
    def thresholds(self, mode: str) -> list[tuple[str, float]]:
        """[(direction, level)] — 'above' fires when S > level, 'below' when S < level."""
        out = []
        for leg in self.short_legs:
            if mode == "strike":
                lvl = leg.strike
            elif mode.startswith("buffer"):
                b = float(mode.split(":")[1])
                lvl = leg.strike * (1 + b) if leg.opt_type == "Call" else leg.strike * (1 - b)
            elif mode == "breakeven":
                lvl = leg.strike + self.credit if leg.opt_type == "Call" \
                    else leg.strike - self.credit
            else:
                raise ValueError(mode)
            out.append(("above" if leg.opt_type == "Call" else "below", lvl))
        return out

    def first_breach_idx(self, mode: str) -> int | None:
        """1-based grid index of the first CLOSE beyond a threshold, else None."""
        ths = self.thresholds(mode)
        for i, day in enumerate(self.grid, start=1):
            s = self.underlying.get(day)
            if s is None:
                continue
            for direction, lvl in ths:
                if (direction == "above" and s > lvl) or (direction == "below" and s < lvl):
                    return i
        return None


# ─── Replay engines ────────────────────────────────────────────────────────────

def replay_production(t: Trade) -> dict:
    """Exact production credit rule set: pt=0.65 → dollar_stop → stop_loss=1.00.
    Calibration gate: must reproduce results.csv exit_reason/days_held/pnl."""
    for i, mark in enumerate(t.marks, start=1):
        if mark is None:
            continue
        pl = t.pnl_of(mark)
        if pl >= 0.65:
            return {"exit_reason": "profit_target", "days_held": i, "pnl_pct": pl}
        if pl * t.credit * 100 * t.contracts <= -MAX_LOSS_ABS:
            return {"exit_reason": "dollar_stop", "days_held": i, "pnl_pct": pl}
        if pl <= -1.00:
            return {"exit_reason": "stop_loss", "days_held": i, "pnl_pct": pl}
    return _fallback_exit(t)


def _fallback_exit(t: Trade) -> dict:
    priced = [(i, m) for i, m in enumerate(t.marks, start=1) if m is not None]
    i, m = priced[-1]
    return {"exit_reason": "expired" if t.cap_reached_expiry else "cap_open",
            "days_held": i, "pnl_pct": t.pnl_of(m)}


def replay_rule(t: Trade, profit_target: float | None, und_mode: str | None,
                keep_stops: bool = False) -> dict:
    """Candidate rule: profit_target (if any) → underlying close-breach stop (if any)
    → hold to path end. keep_stops=False: NO mark-based stops (the underlying rule
    fully replaces them). keep_stops=True: production stop_loss=1.00 + dollar_stop
    stay as backstops AFTER the underlying rule (Part B's proposed priority)."""
    ths = t.thresholds(und_mode) if und_mode else []
    for i, (day, mark) in enumerate(zip(t.grid, t.marks), start=1):
        if mark is None:
            continue
        pl = t.pnl_of(mark)
        if profit_target is not None and pl >= profit_target:
            return {"exit_reason": "profit_target", "days_held": i, "pnl_pct": pl}
        if ths:
            s = t.underlying.get(day)
            if s is not None and any(
                    (d == "above" and s > lvl) or (d == "below" and s < lvl)
                    for d, lvl in ths):
                return {"exit_reason": "underlying_stop", "days_held": i, "pnl_pct": pl}
        if keep_stops:
            if pl * t.credit * 100 * t.contracts <= -MAX_LOSS_ABS:
                return {"exit_reason": "dollar_stop", "days_held": i, "pnl_pct": pl}
            if pl <= -1.00:
                return {"exit_reason": "stop_loss", "days_held": i, "pnl_pct": pl}
    return _fallback_exit(t)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    new_rows = load_credit_rows(NEW_CSV)
    old_rows = load_credit_rows(OLD_CSV)
    old_by_key = {(r["signal_date"], r["ticker"], r["structure"], _strip_qty(r["legs"])): r
                  for r in old_rows}

    trades = [Trade(r) for r in new_rows]
    trades.sort(key=lambda t: (t.signal_date, t.ticker))

    # ── calibration gate ──
    print("=" * 100)
    print("CALIBRATION: replay of production credit rules vs the new book's actuals")
    print("=" * 100)
    ok = 0
    for t in trades:
        rep = replay_production(t)
        want = (t.row["exit_reason"], int(t.row["days_held"]),
                round(_pct(t.row["realized_pnl_pct"]), 4))
        got = (rep["exit_reason"], rep["days_held"], round(rep["pnl_pct"], 4))
        match = want == got
        ok += match
        flag = "OK " if match else "FAIL"
        print(f"  {flag} {t.signal_date} {t.ticker:5s} want={want} got={got}")
    print(f"  → {ok}/{len(trades)} matched")
    if ok != len(trades):
        print("  CALIBRATION FAILED — rule-variant numbers below are NOT trustworthy.")

    # ── underlying coverage ──
    print()
    print("Underlying (Price~) coverage per trade:")
    for t in trades:
        n_days = sum(1 for d in t.grid if d in t.underlying)
        print(f"  {t.signal_date} {t.ticker:5s} {n_days}/{len(t.grid)} grid days covered")

    # ── per-trade diagnostics ──
    und_modes = [("strike", "strike"), ("buffer:0.01", "strike±1%"),
                 ("buffer:0.02", "strike±2%"), ("breakeven", "breakeven")]

    print()
    print("=" * 100)
    print("PER-TRADE DIAGNOSTICS")
    print("=" * 100)
    for t in trades:
        okey = (t.row["signal_date"], t.ticker, t.structure, _strip_qty(t.row["legs"]))
        old = old_by_key.get(okey)
        mfe_day = int(t.row["mfe_day"]) if t.row["mfe_day"] else None
        mfe_pct = _pct(t.row["mfe_pct"])
        s_mfe = t.underlying.get(t.grid[mfe_day - 1]) if mfe_day else None
        ths = dict((f"{d}", lvl) for d, lvl in t.thresholds("strike"))
        print(f"\n{t.signal_date} {t.ticker} {t.structure}  credit={t.credit:.3f}  "
              f"short={'/'.join(f'{l.strike:g}{l.opt_type[0]}' for l in t.short_legs)}")
        print(f"  MFE {mfe_pct:+.2f}×credit on day {mfe_day}"
              + (f", underlying {s_mfe:.2f} (strike lvl {list(ths.values())[0]:g})" if s_mfe else ""))
        new_pc = _pct(t.row["realized_pnl_pct"]) * t.credit * 100
        print(f"  actual NEW: {t.row['exit_reason']:13s} day {t.row['days_held']:>3}  "
              f"pnl/ct ${new_pc:+8.0f}")
        if old:
            old_pc = _pct(old["realized_pnl_pct"]) * abs(float(old["entry_option_price"])) * 100
            print(f"  actual OLD: {old['exit_reason']:13s} day {old['days_held']:>3}  "
                  f"pnl/ct ${old_pc:+8.0f}")
        else:
            print("  actual OLD: (no matching old row)")
        for mode, label in und_modes:
            idx = t.first_breach_idx(mode)
            if idx is None:
                print(f"  breach[{label:10s}]: never")
            else:
                mark = next((m for m in t.marks[idx - 1:] if m is not None), None)
                pl = t.pnl_of(mark) if mark is not None else None
                s = t.underlying.get(t.grid[idx - 1])
                print(f"  breach[{label:10s}]: day {idx:>3}  S={s:.2f}  "
                      f"pnl@breach {pl:+.2f}×credit (${pl * t.credit * 100:+.0f}/ct)")

    # ── rule-grid summary ──
    print()
    print("=" * 100)
    print("RULE GRID — total per-contract $ P&L across all credit trades")
    print("=" * 100)
    actual_new_total = sum(_pct(t.row["realized_pnl_pct"]) * t.credit * 100 for t in trades)
    tsla_march = [t for t in trades
                  if t.ticker == "TSLA" and t.signal_date.isoformat().startswith("2025-03")]

    print(f"\n  actual NEW run (pt=0.65, stop=1×credit, dollar_stop): "
          f"${actual_new_total:+,.0f}/ct total")
    old_total = 0.0
    for t in trades:
        okey = (t.row["signal_date"], t.ticker, t.structure, _strip_qty(t.row["legs"]))
        old = old_by_key.get(okey)
        if old:
            old_total += _pct(old["realized_pnl_pct"]) * abs(float(old["entry_option_price"])) * 100
    print(f"  actual OLD run (matched rows only):                    ${old_total:+,.0f}/ct total")

    header = (f"  {'profit_target':>13s} | {'underlying rule':22s} | {'total $/ct':>11s} | "
              f"{'Δ vs new':>9s} | {'W-L':>5s} | {'TSLA-Mar pair':>13s}")
    print("\n" + header)
    print("  " + "-" * (len(header) - 2))
    for pt in (0.65, 0.50, None):
        variants = [(None, False, "none (control)")]
        variants += [(m, False, l) for m, l in und_modes]
        variants += [(m, True, l + " +mark stops") for m, l in und_modes]
        if pt is not None:
            variants.append((None, True, "mark stops only"))
        for und_mode, keep_stops, label in variants:
            total, wins, losses, tsla_pc = 0.0, 0, 0, 0.0
            for t in trades:
                rep = replay_rule(t, pt, und_mode, keep_stops=keep_stops)
                pc = rep["pnl_pct"] * t.credit * 100
                total += pc
                wins += rep["pnl_pct"] > 0
                losses += rep["pnl_pct"] < 0
                if t in tsla_march:
                    tsla_pc += pc
            pt_s = f"{pt:.2f}" if pt is not None else "none"
            print(f"  {pt_s:>13s} | {label:22s} | ${total:+9,.0f} | "
                  f"${total - actual_new_total:+7,.0f} | {wins}-{losses} | ${tsla_pc:+9,.0f}")

    print("\nNote: exits price at that day's stored close mark; underlying rules are")
    print("close-basis only (no intraday-touch data). No mark-based stops in the rule")
    print("variants — the underlying rule fully replaces stop_loss/dollar_stop.")


if __name__ == "__main__":
    main()
