"""The rollback-trigger power census — ONE implementation of "affected",
"arming", and the census-first reporting line every trigger evaluation prints.

Four shipped rules each carry a pre-registered forward ROLLBACK TRIGGER
(config/backtest.yml's `regime_exit`/`structure_exit` comments; Attempt 13,
research log 2026-07-13) that has never been evaluated — nothing in the repo
computed "affected dates" before this module. What each function means is
pinned in `research/pre-registrations/f2_management/rollback_triggers.md` (read that file
first); the running commitments themselves are recorded in
`research/deployment-evidence.md` §"Open pre-registered rollback triggers".

This module only classifies and counts. It never ships a rule, never reverts
one, and never reads a verdict off a number below its registered floor — the
callers (`exit_switch_mech_study.py` STEP 3(f), `bear_arm.py`'s be_after
census, `exit_mechanism_study.py --side credit`'s `credit_rollback_census`)
own that.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib.harness import replay  # noqa: E402


def outcome(t, cfg, replay_fn=replay):
    """The comparable outcome triple for `t` replayed under `cfg`: the same
    `(exit_reason, days_held, round(pnl_pct, 4))` shape
    `lib/replay_basis.py::calib` compares a STORED row against — here both
    sides come from a replay, no stored value involved."""
    rp = replay_fn(t, **cfg)
    return (rp["exit_reason"], rp["days_held"], round(rp["pnl_pct"], 4))


def is_affected(t, base_cfg, var_cfg, replay_fn=replay):
    """A row is AFFECTED by a rule iff base and variant configs produce
    different outcome triples under the frozen harness replay (pre-
    registration §Pinned specifications, "Affected")."""
    return outcome(t, base_cfg, replay_fn) != outcome(t, var_cfg, replay_fn)


def affected(trades, base_cfg, var_cfg, replay_fn=replay):
    """(rows, dates) — the AFFECTED subset of `trades` (Trade objects, not
    book records) and the sorted set of their `signal_date`s. An affected
    DATE is a signal date with >=1 affected row."""
    rows = [t for t in trades if is_affected(t, base_cfg, var_cfg, replay_fn)]
    dates = sorted({t.signal_date for t in rows})
    return rows, dates


def peak_pnl(t):
    """Max `round(t.pnl_of(mark), 10)` over the trade's priced marks — the
    same rounding `replay()` applies to its own running peak
    (harness.py: `peak = max(peak, round(t.pnl_of(m), 10))`). `-inf` if the
    trade has no priced mark at all."""
    vals = [round(t.pnl_of(m), 10) for m in t.marks if m is not None]
    return max(vals) if vals else float("-inf")


def arming_rows(trades, threshold):
    """Trades whose `peak_pnl` reaches `threshold` — trigger 3's literal
    wording ("reach peak P&L >= +0.50", pre-registration §"Arming")."""
    return [t for t in trades if peak_pnl(t) >= threshold]


def census_line(label, n_rows, n_dates, floor_dates=None, floor_rows=None):
    """One census line — n affected/arming rows, n affected/arming dates, the
    registered floor, and the verdict, ending in `FLOOR MET` or
    `UNDERPOWERED` (never the retired token "POWER STOP" — research/current.md
    2026-08-22 renamed every live print site to UNDERPOWERED / power floor).

    Pass exactly one of `floor_dates` / `floor_rows`: that names the unit the
    floor for THIS trigger is measured in (trigger 1/2 are dates; trigger 3's
    arming floor and trigger 4's fresh-window floor are rows).
    """
    if floor_dates is None and floor_rows is None:
        raise ValueError("census_line needs floor_dates or floor_rows")
    if floor_dates is not None:
        met = n_dates >= floor_dates
        floor_desc = f"floor={floor_dates} dates"
    else:
        met = n_rows >= floor_rows
        floor_desc = f"floor={floor_rows} rows"
    status = "FLOOR MET" if met else "UNDERPOWERED"
    return (f"  CENSUS [{label}]: n_rows={n_rows}  n_dates={n_dates}  "
            f"{floor_desc}  -> {status}")
