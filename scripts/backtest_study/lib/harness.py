"""Exit-replay harness — VERBATIM port of `Trade` / `replay` / `_pct` (and their
helpers) from `scripts/backtest_study/f2_management/exit_mechanism_study.py`, ported 2026-08-11 so the
replay engine every prior tuning study (Attempts 7-13, the mech-regime switch
study, the bear_put demotion study) rests on is available outside the
gitignored `backtests/` tree.

DO NOT "improve" the exit scan, the clamps, or the rounding here. Every
existing tuning conclusion recorded in `research/current.md`
was produced by replaying `backtests/results.csv`/the pooled Sheets exports
through exactly this logic; a behavioural change invalidates all of it
silently (the replay would still run, just disagree with history). If the
exit mechanism itself needs to change, that is a new study with its own
calibration gate — copy this module, don't edit it in place.

The only intentional differences from the source file:
  - the variant grids, `calibrate()`/`run_variant()`/reporting, and the CLI
    `main()` are NOT ported — those are per-study reporting code, not shared
    data-layer logic. Callers do their own calibration gate (see
    `scripts/backtest_study/lib/book.py`) against whichever PROD profile applies.
  - `DEBIT_PROD` / `CREDIT_PROD` are NOT redefined here (avoid a second
    source of truth for the production exit knobs); `scripts/backtest_study/lib/book.py`
    owns those constants.
"""
from __future__ import annotations

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

PATH_CAP_DAYS = 120          # config/backtest.yml simulation.path_cap_days
MAX_LOSS_ABS = 50000 * 0.02  # portfolio_value x risk_per_trade_pct (dollar_stop)


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

    # -- underlying breach thresholds (credit variants) --
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


# --- Replay engine ----------------------------------------------------------

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
    Priority: profit_target -> trailing_stop -> underlying_stop -> dollar_stop ->
    stop_loss/be_stop -> time_exit. dollar_stop/expiry always on, like production.
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
