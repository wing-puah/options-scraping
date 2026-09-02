"""Coherence audit for the `exit_basis` column — it REPORTS, it never refuses.

`exit_basis` names which exit profile governed a simulated row
({PROD, CREDIT, BEAR_DEBIT, <regime cell>}; see `backtest/simulate.py::_exit_basis`).
It is a LABEL: `_exit_basis` is a pure function of the same inputs
`_effective_sim_cfg` already used, and it feeds nothing. So an incoherent label
cannot move a simulated number — it can only mislead a study that STRATIFIES on
it. That is why nothing here raises and nothing here drops a row: gating the
book on this column would block exactly the exit-profile-combination work the
column exists to enable, and it would block it hardest on v3, where the label is
known-bad and the ROWS are fine.

Contrast `lib/replay_basis.py`, which gates: a HARD row there means the harness
and the stored row disagree about a path both claim the same rules for, which
does make the variant numbers untrustworthy. Different question, different
consequence. This module answers "can this row's label be believed", not "does
this row replay".

Three checks, each mechanical and each one-directional except the first. The
one-directionality is the whole point: a basis can be ARMED without GOVERNING
(measured 2026-09-02 on the v4 book — 112 rows labelled non-PROD, but only 14
carry an outcome the base profile could not have produced), so "label says
BEAR_HE, row exited on profit_target" is CORRECT, not a conflict.

  sign_conflict      `CREDIT` <=> entry_net < 0. The only bidirectional check:
                     it is the unconditional first branch of `_exit_basis`, so
                     both directions are provable from the row alone, with no
                     config at all. This is what caught the v3 corruption
                     (7 of 13 `CREDIT` tags sat on positive-entry rows).
  cell_conflict      A regime-cell label must agree with `MechLabeler.cell()`
                     for the signal date. Independent: the cell is re-derived
                     from the SPY/VIX table, which never went near the sheet.
                     One-directional — a row whose date IS a cell but predates
                     the 2026-07-22 override ships as PROD, correctly.
  unreachable_reason The stored `exit_reason` must be one the claimed profile
                     can emit, via `replay_basis.unreachable_reasons`. Also
                     one-directional, for the arming-vs-governing reason above.

BASIS_KNOBS is HISTORICAL, not a read of config/backtest.yml, and must stay
that way: `simulation.structure_exit.enabled` is `false` as of 2026-09-02 while
95 rows in the v4 book carry `BEAR_DEBIT` from when it shipped (2026-08-11). A
live config read would call every one of those rows incoherent. Only knob
PRESENCE matters here — `unreachable_reasons` tests `is None`, never a value —
so re-tuning a threshold does not date this table; adding or removing a RULE
does, and then the new basis needs an entry.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib.replay_basis import unreachable_reasons  # noqa: E402

# label -> the knobs that were SET under that profile. Values are indicative
# only; presence is what `unreachable_reasons` reads.
#   PROD        base debit config (Attempt 10: no trail)
#   CREDIT      simulation.credit (Attempt 13: no premium stop, no time exit)
#   BEAR_DEBIT  base + structure_exit.bear_debit.be_after   (shipped 2026-08-11)
#   BEAR_HE     base + regime_exit.cells.BEAR_HE trail, be_after suppressed
#               to null by the regime merge landing last (shipped 2026-07-22)
BASIS_KNOBS: dict[str, dict] = {
    "PROD":       dict(pt=0.90, sl=0.75, tef=0.75, trig=None, trail=None,
                       be_after=None, und_buffer=None),
    "CREDIT":     dict(pt=0.65, sl=None, tef=None, trig=None, trail=None,
                       be_after=None, und_buffer=None),
    "BEAR_DEBIT": dict(pt=0.90, sl=0.75, tef=0.75, trig=None, trail=None,
                       be_after=0.50, und_buffer=None),
    "BEAR_HE":    dict(pt=0.90, sl=0.75, tef=0.75, trig=0.50, trail=0.50,
                       be_after=None, und_buffer=None),
}

# Labels that name a mechanical regime cell (so `cell_conflict` applies).
# Everything else in the vocabulary is a structural label, not a date-keyed one.
_CELL_LABELS = {"BEAR_HE"}

_UNREACHABLE = {b: unreachable_reasons(k) for b, k in BASIS_KNOBS.items()}

# Verdicts that mean "believe this row's label".
TRUSTED = {"ok"}


def column_present(columns) -> bool:
    """Is `exit_basis` a NAMED column of this export? False on v3 and earlier,
    where it reached the sheet in a nameless trailing field (the header gap
    `scripts/align_tab_headers.py` now covers), and on v2/v1, which predate it.
    A False here is why every row then audits as `absent` rather than as a
    conflict: an unreadable label is not a wrong one."""
    return "exit_basis" in set(columns)


def audit_row(basis, exit_reason, entry_net, mech_cell=None) -> str:
    """'ok' | 'absent' | 'unknown_basis' | 'sign_conflict' | 'cell_conflict'
    | 'unreachable_reason'.

    `mech_cell` is the independently re-derived cell for the signal date, or
    None when the SPY/VIX table cannot label it — in which case the cell check
    is SKIPPED rather than failed. Checks run in order of how conclusive they
    are, so a row is reported under its strongest violation.
    """
    # `basis != basis` is the NaN test: pandas types an all-blank exit_basis
    # column as float64, so a blank cell arrives as NaN — which is TRUTHY and
    # would sail past a plain falsiness check straight into `.strip()`.
    # Coerce rather than assume a str: an unreadable cell must come back as a
    # verdict, never as an exception, or the audit becomes the gate it refuses
    # to be.
    if basis is None or basis != basis:
        return "absent"
    label = str(basis).strip()
    if not label:
        return "absent"
    if label not in BASIS_KNOBS:
        return "unknown_basis"

    if entry_net is not None:
        is_credit_row = entry_net < 0
        if is_credit_row != (label == "CREDIT"):
            return "sign_conflict"

    if label in _CELL_LABELS and mech_cell is not None and mech_cell != label:
        return "cell_conflict"

    if exit_reason and exit_reason in _UNREACHABLE[label]:
        return "unreachable_reason"

    return "ok"


def audit(rows, columns=None) -> tuple[Counter, list[dict]]:
    """`(tally, conflicts)` over an iterable of dicts carrying `exit_basis`,
    `exit_reason`, `entry_net` and optionally `mech_cell`.

    `conflicts` holds only the rows a study should segregate before
    stratifying — never the `absent` ones, which are simply unlabelled. Pass
    `columns` to short-circuit an export that does not carry the column at all.
    """
    if columns is not None and not column_present(columns):
        return Counter({"absent": len(list(rows))}), []

    tally: Counter = Counter()
    conflicts: list[dict] = []
    for r in rows:
        v = audit_row(r.get("exit_basis"), r.get("exit_reason"),
                      r.get("entry_net"), r.get("mech_cell"))
        tally[v] += 1
        if v not in TRUSTED and v != "absent":
            conflicts.append({**r, "basis_verdict": v})
    return tally, conflicts


def format_tally(tally: Counter, total: int | None = None) -> str:
    """One line for a study header. Names the conflict buckets even at zero —
    a check that prints nothing when it passes is a check nobody notices has
    stopped running."""
    n = total if total is not None else sum(tally.values())
    parts = [f"{tally.get('ok', 0)} coherent", f"{tally.get('absent', 0)} unlabelled"]
    parts += [f"{tally.get(k, 0)} {k}" for k in
              ("sign_conflict", "cell_conflict", "unreachable_reason", "unknown_basis")]
    return f"exit_basis coherence: {', '.join(parts)} of {n}"
