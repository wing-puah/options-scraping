"""Derive chart series from the account_sim positions CSV, and reconcile them.

The positions CSV carries one row per *candidate* the walk considered — taken
and skipped alike — so most of the report's headline numbers can be recomputed
from it. That is the point: `reconcile()` recomputes them and compares against
the parsed report, so a chart drawn from a CSV that does not belong to the
report it is paired with fails the build instead of shipping a quiet lie. (The
common way to hit this: `account_sim-latest.txt` is whichever arm ran last,
which is not necessarily the arm that wrote `account_sim-positions-latest.csv`.)

Two estimators are borrowed rather than reinvented: `max_drawdown` from
`bear_deploy` (it seeds the running peak at zero, so a book that opens underwater
counts that as drawdown) and `boot_ci_by_date` from `protocol` (the date-clustered
bootstrap the study's own A1 line uses). Reimplementing either would produce
numbers that disagree with the report in kind rather than in value.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, median

from scripts.backtest_study import protocol as P
from scripts.backtest_study.bear_deploy import max_drawdown

# The order the report lists them in: taken first, then the exclusion buckets.
CENSUS_ORDER = [
    "taken",
    "taken_downsized",
    "cash",
    "per_pos_delta",
    "net_delta",
    "min1_refusal",
    "day3_cap",
    "unsizable",
]

# Exit reasons, ordered good -> bad, so the stacked bar reads left to right.
# be_stop/underlying_stop are real harness.py outcomes (the shipped `be_after:
# 0.50` bear rule reaches be_stop) — this is the known set, not the whole set;
# `_ordered_keys` below still surfaces anything this list misses.
EXIT_ORDER = [
    "profit_target",
    "time_exit",
    "cap_open",
    "expired",
    "trailing_stop",
    "be_stop",
    "stop_loss",
    "underlying_stop",
    "dollar_stop",
]

# A taken row with no exit_reason at all (should not happen, but a silent
# `if r["exit_reason"]` filter is exactly how it would go unnoticed).
NO_EXIT_REASON = "missing_exit_reason"

# Every column build()/reconcile() reads off a row by name, plus the numeric
# ones load() types below — the set a renamed CSV header would break.
NUMERIC_COLUMNS = ("contracts", "reserved", "dn", "days_held", "R", "dollars",
                   "max_loss_per_contract", "delta", "dte", "score_total", "mfe", "mae")
NAMED_COLUMNS = ("population", "status", "reject_reason", "exit_reason",
                 "exit_sess", "date", "tier", "structure", "credit",
                 # the two regime readings the regime page draws — named here
                 # so a renamed header fails loudly instead of drawing an
                 # empty grid that looks like "the book deployed nowhere"
                 "mech_cell", "mech_direction", "model_dir", "model_vol")
REQUIRED_COLUMNS = NUMERIC_COLUMNS + NAMED_COLUMNS


class ReconcileError(RuntimeError):
    """A CSV-derived number disagrees with the report it was paired with."""


def _f(value: str) -> float | None:
    return float(value) if value not in ("", "nan") else None


def _ordered_keys(present: set[str], order: list[str]) -> list[str]:
    """`order` first (only the members actually present), then anything else
    in a deterministic order — so a bucket the whitelist doesn't know about
    still ships instead of silently vanishing from the chart."""
    return [k for k in order if k in present] + sorted(present - set(order))


def load(path: Path) -> list[dict]:
    """Read the positions CSV, typing the columns the charts need."""
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        header = set(reader.fieldnames or [])
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            raise ReconcileError(f"{path}: missing column(s) {missing} — a renamed "
                                 f"CSV header would otherwise just read as empty")
        rows = list(reader)
    for r in rows:
        for key in NUMERIC_COLUMNS:
            r[key] = _f(r.get(key, ""))
        r["credit"] = r.get("credit") == "True"
    if not rows:
        raise ReconcileError(f"{path}: positions CSV is empty")
    return rows


def _equity(taken: list[dict]) -> list[dict]:
    """Realized cumulative P&L, booked on the session a position exits."""
    by_session: dict[str, float] = defaultdict(float)
    closed: dict[str, int] = defaultdict(int)
    for r in taken:
        if r["exit_sess"]:
            by_session[r["exit_sess"]] += r["dollars"]
            closed[r["exit_sess"]] += 1
    out, cum, peak = [], 0.0, 0.0
    for sess in sorted(by_session):
        cum += by_session[sess]
        peak = max(peak, cum)
        out.append({
            "sess": sess,
            "pnl": round(by_session[sess], 2),
            "cum": round(cum, 2),
            "drawdown": round(cum - peak, 2),
            "closed": closed[sess],
        })
    return out


def _mean_r(rows: list[dict]) -> float | None:
    vals = [r["R"] for r in rows if r["R"] is not None]
    return fmean(vals) if vals else None


def _ci(rows: list[dict]) -> list[float] | None:
    """The study's own date-clustered bootstrap CI of mean R."""
    usable = [r for r in rows if r["R"] is not None]
    if len(usable) < 2:
        return None
    lo, hi = P.boot_ci_by_date(usable, key="R")
    return [round(lo, 4), round(hi, 4)]


def _histogram(values: list[float], edges: list[float]) -> list[dict]:
    """Bin `values` into half-open [lo, hi) bins, last bin closed."""
    bins = [{"lo": edges[i], "hi": edges[i + 1], "n": 0} for i in range(len(edges) - 1)]
    for v in values:
        for i, b in enumerate(bins):
            if b["lo"] <= v < b["hi"] or (i == len(bins) - 1 and v == b["hi"]):
                b["n"] += 1
                break
    return bins


def build(rows: list[dict], population: str, capital: float) -> dict:
    """Every CSV-derived series for one population."""
    pop = [r for r in rows if r["population"] == population]
    taken = [r for r in pop if r["status"] == "taken"]
    equity = _equity(taken)
    dollars = sum(r["dollars"] for r in taken)

    census = Counter(r["reject_reason"] or "taken" for r in pop)
    exits = Counter(r["exit_reason"] or NO_EXIT_REASON for r in taken)
    exit_dollars: dict[str, float] = defaultdict(float)
    for r in taken:
        exit_dollars[r["exit_reason"] or NO_EXIT_REASON] += r["dollars"]

    adverse = [{
        "bucket": "taken",
        "n": len(taken),
        "meanR": _mean_r(taken),
        "ci": _ci(taken),
    }]
    for bucket in ("net_delta", "per_pos_delta"):
        sub = [r for r in pop if r["reject_reason"] == bucket and r["R"] is not None]
        if sub:
            adverse.append({
                "bucket": bucket,
                "n": len(sub),
                "meanR": _mean_r(sub),
                "ci": _ci(sub),
            })

    by_tier: dict[str, dict] = {}
    for r in taken:
        cell = by_tier.setdefault(r["tier"], {"tier": r["tier"], "n": 0, "dollars": 0.0})
        cell["n"] += 1
        cell["dollars"] += r["dollars"]

    by_structure: dict[str, dict] = {}
    for r in taken:
        cell = by_structure.setdefault(r["structure"], {"structure": r["structure"], "n": 0, "dollars": 0.0})
        cell["n"] += 1
        cell["dollars"] += r["dollars"]

    risk_pct = [
        100 * r["contracts"] * r["max_loss_per_contract"] / capital
        for r in taken
        if r["contracts"] and r["max_loss_per_contract"]
    ]

    days_held = [r["days_held"] for r in taken if r["days_held"] is not None]

    return {
        "capital": capital,
        "summary": {
            "n": len(taken),
            "candidates": len(pop),
            "dates": len({r["date"] for r in taken}),
            "dollars": round(dollars, 2),
            "meanR": _mean_r(taken),
            "ci": _ci(taken),
            "win": sum(1 for r in taken if r["dollars"] > 0) / len(taken) if taken else None,
            "sessions": len(equity),
            "maxDD": round(max_drawdown([e["pnl"] for e in equity]), 2),
            "worst": round(min((e["pnl"] for e in equity), default=0.0), 2),
            "best": round(max((e["pnl"] for e in equity), default=0.0), 2),
            "median_days": median(days_held) if days_held else None,
            "credit_n": sum(1 for r in taken if r["credit"]),
        },
        "equity": equity,
        "census": [{"bucket": b, "n": census[b]} for b in _ordered_keys(set(census), CENSUS_ORDER)],
        "adverse": adverse,
        "exits": [
            {"reason": e, "n": exits[e], "dollars": round(exit_dollars[e], 2)}
            for e in _ordered_keys(set(exits), EXIT_ORDER)
        ],
        "contracts": [
            {"contracts": c, "n": n}
            for c, n in sorted(Counter(int(r["contracts"]) for r in taken if r["contracts"]).items())
        ],
        "tiers": sorted(by_tier.values(), key=lambda c: c["tier"]),
        "structures": sorted(by_structure.values(), key=lambda c: -c["n"]),
        "risk_hist": _histogram(risk_pct, [0, 1, 2, 3, 4, 5, 6, 8, 10, 15]),
        "risk_over_budget": sum(1 for v in risk_pct if v > 2.0),
        "risk_n": len(risk_pct),
        "regime": _regime(pop, taken),
    }


# --------------------------------------------------------------------------
# the regime cut (post-hoc — the study prints it, this recomputes and checks it)
# --------------------------------------------------------------------------

NO_LABEL = "NONE"      # matches the study's own sentinel for an absent label
THIN_N = 10            # matches account_sim.THIN_N


def _label(row: dict, field: str) -> str:
    return row.get(field) or NO_LABEL


def _regime_cells(taken: list[dict], key) -> list[dict]:
    """`taken` grouped by (key(row), structure) — the shape the report prints,
    minus its per-cell ALL rollups, which would double-count anything summed."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in taken:
        groups[(key(r), _label(r, "structure"))].append(r)
    return [
        {
            "cell": cell,
            "structure": structure,
            "n": len(rows),
            "dollars": round(sum(r["dollars"] for r in rows), 2),
            "meanR": _mean_r(rows),
            "win": sum(1 for r in rows if r["R"] is not None and r["R"] > 0) / len(rows),
            "thin": len(rows) < THIN_N,
        }
        for (cell, structure), rows in sorted(groups.items())
    ]


def _regime(pop: list[dict], taken: list[dict]) -> dict:
    """Everything the regime page draws, recomputed from the positions export.

    `win` here counts R > 0, matching the study's own per-cell definition —
    NOT the headline summary's dollars > 0. The two agree on every row that
    has both, and reconciliation compares each against its own counterpart.
    """
    mech = _regime_cells(taken, lambda r: _label(r, "mech_cell"))
    model = _regime_cells(
        taken, lambda r: f"{_label(r, 'model_dir')}/{_label(r, 'model_vol')}")

    by_cell: dict[str, list[dict]] = defaultdict(list)
    for r in taken:
        by_cell[_label(r, "mech_cell")].append(r)
    census = [
        {
            "cell": cell,
            "n": len(rows),
            "tierA": sum(1 for r in rows if r["tier"] == "A"),
            "tierB": sum(1 for r in rows if r["tier"] == "B"),
            "reserved": fmean([r["reserved"] for r in rows if r["reserved"] is not None]),
            "dn": fmean([abs(r["dn"]) for r in rows if r["dn"] is not None]),
        }
        for cell, rows in sorted(by_cell.items())
    ]

    skips = Counter(
        (_label(r, "mech_cell"), r["reject_reason"] or "taken") for r in pop)
    agreement = Counter(
        (_label(r, "model_dir"), _label(r, "mech_direction")) for r in taken)
    return {
        "mech": mech,
        "model": model,
        "census": census,
        "skips": [{"cell": c, "bucket": b, "n": n} for (c, b), n in sorted(skips.items())],
        "considered": sum(skips.values()),
        "agreement": [{"model": m, "mech": k, "n": n} for (m, k), n in sorted(agreement.items())],
        "agree": sum(n for (m, k), n in agreement.items() if m == k),
        "agree_total": sum(agreement.values()),
    }


# --------------------------------------------------------------------------
# reconciliation
# --------------------------------------------------------------------------

def _check(problems: list[str], population: str, what: str, got, want, tol=0.0) -> None:
    # `tol` is compared with a hair of float slack (1e-9): a caller passing
    # e.g. tol=0.005 to mean "the report's own rounding may move this by up
    # to half a percentage point" wants a value sitting exactly on that line
    # (0.625 vs a report that prints "62%", i.e. a 0.0050000000000000044
    # float64 delta) to pass, not fail on binary-representation noise the
    # tolerance was never meant to exclude.
    if got is None or want is None:
        problems.append(f"[{population}] {what}: missing (csv={got!r} report={want!r})")
    elif abs(got - want) > tol + 1e-9:
        problems.append(f"[{population}] {what}: csv={got!r} report={want!r}")


def reconcile(derived: dict, parsed: dict, population: str) -> list[str]:
    """Compare CSV-derived headline numbers against the report's own.

    Returns a list of human-readable disagreements; empty means they agree.
    """
    problems: list[str] = []
    s = derived["summary"]
    rep = parsed["populations"][population]
    headline = next(a for a in rep["arms"] if a["headline"])
    equity = rep["equity"]["constrained"]

    _check(problems, population, "positions", s["n"], headline["n"])
    _check(problems, population, "dates", s["dates"], headline["dates"])
    _check(problems, population, "total $", s["dollars"], headline["dollars"], tol=1.0)
    _check(problems, population, "meanR", s["meanR"], headline["meanR"], tol=0.001)
    _check(problems, population, "win rate", s["win"], headline["win"], tol=0.005)
    _check(problems, population, "exit sessions", s["sessions"], equity["sessions"])
    _check(problems, population, "maxDD", s["maxDD"], equity["maxDD"], tol=1.0)
    _check(problems, population, "worst session", s["worst"], equity["worst"], tol=1.0)
    _check(problems, population, "candidates considered", s["candidates"], rep["census"]["total"])
    _check(problems, population, "capital", derived["capital"], rep["equity"]["capital"], tol=0.01)

    # Both directions: a bucket only the CSV has (e.g. an ARM H hedge row the
    # report's own census table doesn't carry) and a bucket only the report
    # has (a bucket that silently stopped showing up in the CSV) must both fail.
    census_map = {bucket["bucket"]: bucket["n"] for bucket in derived["census"]}
    for bucket in derived["census"]:
        _check(problems, population, f"census/{bucket['bucket']}",
               bucket["n"], rep["census"]["buckets"].get(bucket["bucket"]))
    for name, want in rep["census"]["buckets"].items():
        if name not in census_map:
            _check(problems, population, f"census/{name}", 0, want)
    # Every candidate falls into exactly one bucket by construction (the
    # Counter key is `reject_reason or "taken"` for every row) — a mismatch
    # here means a row's bucket got double-counted or dropped upstream.
    _check(problems, population, "census sum", sum(census_map.values()), s["candidates"])

    # The report prints no exit-reason section, so this identity is checked
    # against the CSV's own population instead: every taken row must land in
    # exactly one exit bucket (missing_exit_reason included), and the bucket
    # dollars must add back up to the population's total realized dollars.
    _check(problems, population, "exit reasons n",
           sum(e["n"] for e in derived["exits"]), s["n"])
    _check(problems, population, "exit reasons $",
           sum(e["dollars"] for e in derived["exits"]), s["dollars"], tol=1.0)

    for row in derived["adverse"]:
        want = (rep["adverse"]["taken"] if row["bucket"] == "taken"
                else next((r for r in rep["adverse"]["rejected"] if r["bucket"] == row["bucket"]), None))
        if want is None:
            problems.append(f"[{population}] adverse/{row['bucket']}: absent from the report")
            continue
        _check(problems, population, f"adverse/{row['bucket']} n", row["n"], want["n"])
        _check(problems, population, f"adverse/{row['bucket']} meanR", row["meanR"], want["meanR"], tol=0.001)

    problems += _reconcile_regime(derived["regime"], rep["regime"], population)
    return problems


def _paired(problems: list[str], population: str, what: str,
            got: list[dict], want: list[dict], keys: tuple[str, ...]) -> list[tuple]:
    """Match two row lists on `keys`, reporting rows only one side has.

    Both directions, for the reason the census check states: a cell only the
    CSV has means the report stopped printing it, and a cell only the report
    has means the CSV stopped carrying it. Either is a silently wrong chart.
    """
    got_by = {tuple(r[k] for k in keys): r for r in got}
    want_by = {tuple(r[k] for k in keys): r for r in want}
    for key in sorted(set(got_by) - set(want_by)):
        problems.append(f"[{population}] {what}/{'/'.join(map(str, key))}: absent from the report")
    for key in sorted(set(want_by) - set(got_by)):
        problems.append(f"[{population}] {what}/{'/'.join(map(str, key))}: absent from the positions CSV")
    return [(key, got_by[key], want_by[key]) for key in sorted(set(got_by) & set(want_by))]


def _reconcile_regime(derived: dict, rep: dict, population: str) -> list[str]:
    """The post-hoc regime section, checked exactly as hard as everything else.

    It carries no conclusion, which is precisely why it needs this: a
    descriptive table nobody re-derives is where a quiet disagreement between
    the report and the export would sit forever.
    """
    problems: list[str] = []

    for name in ("mech", "model"):
        for key, got, want in _paired(problems, population, name,
                                      derived[name], rep[name], ("cell", "structure")):
            tag = f"{name}/{key[0]}/{key[1]}"
            _check(problems, population, f"{tag} n", got["n"], want["n"])
            _check(problems, population, f"{tag} $", got["dollars"], want["dollars"], tol=1.0)
            _check(problems, population, f"{tag} meanR", got["meanR"], want["meanR"], tol=0.001)
            _check(problems, population, f"{tag} win", got["win"], want["win"], tol=0.005)

    for key, got, want in _paired(problems, population, "regime census",
                                  derived["census"], rep["census"], ("cell",)):
        tag = f"regime census/{key[0]}"
        for field, tol in (("n", 0.0), ("tierA", 0.0), ("tierB", 0.0),
                           ("reserved", 1.0), ("dn", 1.0)):
            _check(problems, population, f"{tag} {field}", got[field], want[field], tol=tol)

    for key, got, want in _paired(problems, population, "regime skips",
                                  derived["skips"], rep["skips"], ("cell", "bucket")):
        _check(problems, population, f"regime skips/{key[0]}/{key[1]}", got["n"], want["n"])
    _check(problems, population, "regime considered", derived["considered"], rep["considered"])

    for key, got, want in _paired(problems, population, "regime agreement",
                                  derived["agreement"], rep["agreement"], ("model", "mech")):
        _check(problems, population, f"regime agreement/{key[0]}/{key[1]}", got["n"], want["n"])
    _check(problems, population, "regime agreement n", derived["agree"], rep["agree"])
    _check(problems, population, "regime agreement total",
           derived["agree_total"], rep["agree_total"])

    # The section's own TOTAL row is what ties this cut back to the rest of the
    # report: if it does not equal the headline the arms table prints, the
    # regime tables are describing a different book.
    for name in ("mech", "model"):
        total = rep[f"{name}_total"]
        cells = rep[name]
        # Each leaf cell's dollar figure is independently rounded to the
        # nearest dollar in the report text, so summing N already-rounded
        # cells can drift up to ~$0.50 * N from the report's own separately-
        # rounded TOTAL line — a display-rounding artifact of a multi-cell
        # breakdown, not evidence the cut describes a different book (which
        # would show a discrepancy far larger than a few dollars). A flat
        # $1 tolerance was fine for a couple of cells; it is not for a dozen.
        dollar_tol = max(1.0, 0.5 * len(cells))
        _check(problems, population, f"{name} TOTAL n", sum(c["n"] for c in rep[name]), total["n"])
        _check(problems, population, f"{name} TOTAL $",
               sum(c["dollars"] for c in rep[name]), total["dollars"], tol=dollar_tol)
    return problems
