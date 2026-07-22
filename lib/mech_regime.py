"""Mechanical market-regime labels from SPY/VIX daily closes.

FROZEN spec — restated from the study scripts that derived it
(`backtests/mech_regime_recut.py`, `backtests/exit_switch_mech_study.py`).
Direction and volatility are computed causally: every label for date D uses
only closes on or before D, so it is safe to key trade decisions on.

    direction  BEAR  if SPY < 50-day SMA AND 20-day return < 0
               BULL  if SPY > 50-day SMA AND 20-day return > 0
               RANGE otherwise
    vol        E-VOL if VIX >= 30 OR 5-day VIX change >= +25%
               H-VOL if VIX >= 20
               L-VOL otherwise

Labels are used for EXIT conditioning only. Model-produced regime labels
(from the analysis) remain the basis for SELECTION gates — see
`config/backtest-tuning/current.md` §2026-07-22 addendum 4 for the evidence
that the two label sources win on opposite jobs.

Pure module: reads a CSV of `date,spy_close,vix_close`, no network — it is
called per-row inside the backtest, so fetching stays OUT of it. The table is
refreshed nightly into Drive by the Compile Flow workflow
(`scripts/collector/fetch_mech_regime.py`); pull the current copy with
`make mech-regime`, which `make backtest` / `make analyze` depend on.

Rows with no SPY close are dropped, so an in-progress trading day (VIX printed,
SPY not yet closed) is NOT labelled — `cell_for_date` returns NO_DATA rather
than labelling today off a partial bar.
"""

from __future__ import annotations

import bisect
import csv
from pathlib import Path

# Frozen thresholds. Changing any of these invalidates the addendum-4 study
# and every gate decision that rests on it.
SMA_WINDOW = 50
RET_WINDOW = 20
VIX_HVOL = 20.0
VIX_EVOL_LEVEL = 30.0
VIX_EVOL_PCT = 0.25


def _to_float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN guard


def compute_mech_table(csv_path: str | Path) -> list[dict]:
    """Rows of {date, mech_direction, mech_vol, dir_ok}, oldest first.

    Rows with no SPY close are dropped (matches the study's
    `dropna(subset=["spy_close"])`) — a VIX-only trailing row would otherwise
    shift every rolling window by one.
    """
    rows = []
    with open(csv_path, newline="") as fh:
        for r in csv.DictReader(fh):
            spy = _to_float(r.get("spy_close"))
            if spy is None:
                continue
            rows.append({"date": str(r["date"]), "spy": spy,
                         "vix": _to_float(r.get("vix_close"))})
    rows.sort(key=lambda r: r["date"])

    out = []
    for i, r in enumerate(rows):
        sma = None
        if i + 1 >= SMA_WINDOW:
            window = [x["spy"] for x in rows[i + 1 - SMA_WINDOW:i + 1]]
            sma = sum(window) / SMA_WINDOW
        ret_n = None
        if i >= RET_WINDOW:
            prior = rows[i - RET_WINDOW]["spy"]
            if prior:
                ret_n = r["spy"] / prior - 1.0

        if sma is None or ret_n is None:
            direction = None
        elif r["spy"] < sma and ret_n < 0:
            direction = "BEAR"
        elif r["spy"] > sma and ret_n > 0:
            direction = "BULL"
        else:
            direction = "RANGE"

        vix = r["vix"]
        if vix is None:
            vol = None
        else:
            chg5 = None
            if i >= 5:
                prior_vix = rows[i - 5]["vix"]
                if prior_vix:
                    chg5 = vix / prior_vix - 1.0
            if vix >= VIX_EVOL_LEVEL or (chg5 is not None and chg5 >= VIX_EVOL_PCT):
                vol = "E-VOL"
            elif vix >= VIX_HVOL:
                vol = "H-VOL"
            else:
                vol = "L-VOL"

        out.append({"date": r["date"], "mech_direction": direction,
                    "mech_vol": vol, "dir_ok": sma is not None and ret_n is not None})
    return out


class MechLabeler:
    """As-of lookup: for signal date D, use the most recent trading day <= D."""

    def __init__(self, table: list[dict]) -> None:
        self._dates = [r["date"] for r in table]
        self._by_date = {r["date"]: r for r in table}

    @classmethod
    def from_csv(cls, csv_path: str | Path) -> "MechLabeler":
        return cls(compute_mech_table(csv_path))

    @property
    def last_date(self) -> str | None:
        return self._dates[-1] if self._dates else None

    def label(self, d: str) -> tuple[str | None, str | None, bool, str | None]:
        """(direction, vol, ok, mapped_trading_date).

        ok=False means no usable label — either D predates the 50-SMA lookback
        or there is no trading day at/before D in the table. Callers must treat
        ok=False as "no regime override", never as a regime.
        """
        i = bisect.bisect_right(self._dates, str(d)) - 1
        if i < 0:
            return (None, None, False, None)
        row = self._by_date[self._dates[i]]
        if not row["dir_ok"]:
            return (None, None, False, row["date"])
        return (row["mech_direction"], row["mech_vol"], True, row["date"])

    def covers(self, d: str) -> bool:
        """True when the table actually reaches date D.

        `label()` is deliberately as-of (most recent trading day <= D), which is
        correct for a historical backtest date but WRONG for a live one: a table
        that ends before D would label today from a stale close without saying
        so. Callers storing a label for live use must gate on this.
        """
        return bool(self._dates) and str(d) <= self._dates[-1]

    def cell(self, d: str) -> str | None:
        """Regime cell name used to key exit overrides, or None if unlabelled."""
        direction, vol, ok, _ = self.label(d)
        if not ok:
            return None
        if direction == "BEAR" and vol in ("H-VOL", "E-VOL"):
            return "BEAR_HE"
        if vol == "L-VOL":
            return "LVOL"
        if direction in ("RANGE", "BULL") and vol == "E-VOL":
            return "RB_EVOL"
        return None


# Stored-column sentinels. A blank cell is NOT used: blank is indistinguishable
# from "row written before this column existed", so both failure modes get an
# explicit name.
NO_CELL = "NONE"        # labelled fine, but the regime maps to no override cell
NO_DATA = "NO_DATA"     # could not label: table missing, or it ends before D


def cell_for_date(csv_path: str | Path, d: str) -> tuple[str, str | None]:
    """`(value to store, warning or None)` for the mechanical cell of date D.

    Used when the label is written to a durable surface (the analysis tab) that
    a person reads at deploy time, rather than computed inside a backtest run.
    Stricter than `MechLabeler.cell` on purpose — see `covers()`: a date past
    the end of the table returns NO_DATA rather than an as-of answer from a
    stale close, because trading the wrong exit profile is worse than having no
    label at all.

    Refresh the table with `make mech-regime`.
    """
    p = Path(csv_path)
    if not p.exists():
        return NO_DATA, f"mech-regime table not found at {p} — no cell written"
    lab = MechLabeler.from_csv(p)
    if not lab.covers(d):
        return NO_DATA, (f"mech-regime table ends {lab.last_date}, before {d} — "
                         f"refresh with `make mech-regime`")
    return (lab.cell(d) or NO_CELL), None
