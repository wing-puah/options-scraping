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
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib.book import CREDIT_PROD, DEBIT_PROD  # noqa: E402
from scripts.backtest_study.lib.harness import (  # noqa: E402
    MAX_LOSS_ABS, PATH_CAP_DAYS, Trade, _pct, _to_float, replay,
)
from scripts.backtest_study.lib.replay_basis import classify, unreachable_reasons  # noqa: E402
from scripts.backtest_study.lib import triggers  # noqa: E402

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

# --- replay engine + production profiles: IMPORTED, no longer defined here ---
# The engine (Trade / replay / _pct and the PATH_CAP_DAYS / MAX_LOSS_ABS
# clamps) lives in lib/harness.py — the FROZEN port of what used to be defined
# in this file — pinned by tests/test_harness_replay.py's fixture, so this
# study and every study that imports the engine THROUGH this module
# (bear_position_study, exit_switch_*, the retired combined/underlying pair)
# now replay under the pinned implementation. The production profiles come
# from lib/book.py, the single source of truth: until 2026-08-24 this file
# carried its own CREDIT_PROD with the PRE-Attempt-13 sl=1.00 — a stop removed
# from production 2026-07-13 — so every credit variant Δ was measured against
# a retired rule, and the variant then named "sl none" WAS production. The
# re-exports are deliberate; downstream import sites stay stable.

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


# ─── Calibration gate ──────────────────────────────────────────────────────────

def calibrate(trades: list[Trade], prod: dict, label: str) -> bool:
    """Classify every row's stored outcome against a replay under `prod`:
    exact / near-rounding-tie / superseded-basis / HARD. One classifier for
    the whole tier — lib/replay_basis.py, the same four buckets as
    exit_switch_mech_study's harness_gate and book.py's debit_calib.

    Superseded rows are EXPECTED on the current book: they are the shipped
    per-row overrides' own output (regime_exit BEAR_HE trail 2026-07-22,
    structure_exit bear-debit be_after 2026-08-11) which the flat profile here
    cannot emit. They are kept — every variant table re-replays all rows under
    each variant, so no stored outcome leaks into a comparison. Only a HARD
    row (reachable reason, wrong outcome) makes the variant numbers
    untrustworthy; the return value is "no HARD rows" and main() stops on it.
    """
    print("=" * 100)
    # "the main book" rather than "results.csv": the input is era-resolved now,
    # and a header naming a file the run did not read is how a report gets
    # attributed to the wrong population.
    print(f"CALIBRATION ({label}): production rules replayed vs the main book's actuals")
    print("=" * 100)
    unreachable = unreachable_reasons(prod)
    tally = Counter()
    sup_rows, hard_rows = [], []
    for t in trades:
        kind, want, got = classify(t, prod, unreachable)
        tally[kind] += 1
        if kind == "superseded":
            sup_rows.append((t, want, got))
        elif kind == "hard":
            hard_rows.append((t, want, got))
    print(f"  → {tally['exact']} exact, {tally['near']} near-rounding-tie, "
          f"{tally['superseded']} superseded-basis, {tally['hard']} HARD "
          f"of {len(trades)}")
    if sup_rows:
        print(f"  superseded-basis rows (stored under a shipped override; "
              f"unreachable under this profile: {sorted(unreachable)}):")
        for t, want, got in sup_rows:
            print(f"    {t.signal_date} {t.ticker:5s} {t.structure:18s} "
                  f"stored={want} replay={got}")
    for t, want, got in hard_rows:
        print(f"  HARD {t.signal_date} {t.ticker:5s} {t.structure:18s} "
              f"want={want} got={got}")
    if hard_rows:
        print("  CALIBRATION FAILED — variant numbers below are NOT trustworthy.")
    return not hard_rows


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
    ("PROD pt.65 sl none", CREDIT_PROD),
    # rollback comparator — the PRE-Attempt-13 stop, removed from production
    # 2026-07-13. Kept as a variant so the Attempt-13 rollback trigger
    # ("sl-none loses to sl-1x on the next >=15-row fresh bull_put window",
    # research/deployment-evidence.md) gets its comparison printed by every
    # run. Until 2026-08-24 this dict WAS the baseline here (stale copy).
    ("sl 1x (pre-Attempt-13)", {**CREDIT_PROD, "sl": 1.00}),
    # profit-target lever (Attempt 8/9: both TSLA peaked at 0.59x)
    ("pt .50", {**CREDIT_PROD, "pt": 0.50}),
    ("pt .55", {**CREDIT_PROD, "pt": 0.55}),
    # "sl none (dollar stop only)" and "pt .50 sl none" — REMOVED 2026-08-24:
    # with the corrected baseline (sl=None) they duplicated PROD and "pt .50"
    # row-for-row.
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


# ─── Credit rollback-trigger census (research/pre-registrations/rollback_triggers.md) ──

ATTEMPT13_SHIP = date(2026, 7, 13)


def credit_rollback_census(trades: list[Trade]) -> None:
    """Attempt-13 rollback trigger (research log 2026-07-13): "sl-none loses
    to sl-1x on the next >=15-row fresh bull_put window." Fresh = bull_put
    rows signal-dated AFTER the Attempt-13 ship date. Census-first
    (pre-registration §Census-first rule): prints n rows, the floor, and
    MET/UNDERPOWERED before anything else. Below the floor there is NO
    tuning read — the standing comparator stays the "sl 1x (pre-Attempt-13)"
    grid line printed below by the variant table (pre-registration §Trigger 4
    scope: CENSUS + COMPARATOR ONLY)."""
    title = ('CREDIT ROLLBACK-TRIGGER CENSUS (Attempt 13 — "sl-none loses to sl-1x '
             'on the next >=15-row fresh bull_put window")')
    print("\n" + "=" * 100 + f"\n{title}\n" + "=" * 100)

    bull_put = [t for t in trades if t.structure == "bull_put_spread"]
    fresh = [t for t in bull_put if t.signal_date > ATTEMPT13_SHIP]
    print(f"  credit rows: {len(trades)}   bull_put rows: {len(bull_put)}   "
          f"fresh bull_put rows (signal_date > {ATTEMPT13_SHIP}): {len(fresh)}")
    fresh_dates = sorted({t.signal_date for t in fresh})
    print(triggers.census_line("credit sl-none vs sl-1x (fresh bull_put)",
                               len(fresh), len(fresh_dates), floor_rows=15))

    variant = {**CREDIT_PROD, "sl": 1.00}
    aff_rows, aff_dates = triggers.affected(trades, CREDIT_PROD, variant)
    by_year = Counter(t.signal_date.year for t in aff_rows)
    print(f"  affected rows (all credit rows, sl-none vs sl-1x): {len(aff_rows)}   "
          f"affected dates: {len(aff_dates)}   by year: "
          + ("  ".join(f"{y}={n}" for y, n in sorted(by_year.items())) if by_year else "(none)"))

    if len(fresh) < 15:
        print("  UNDERPOWERED on the fresh window — NO tuning read. The 'sl 1x "
              "(pre-Attempt-13)' variant line in the grid below is the standing "
              "comparator; census recorded (pre-registration §decisions, trigger 4 "
              "scope: CENSUS + COMPARATOR ONLY). Thread stays parked.")
        return

    prod_reps = {id(t): replay(t, **CREDIT_PROD) for t in fresh}
    var_reps = {id(t): replay(t, **variant) for t in fresh}
    prod_dol = sum(t.dollars(prod_reps[id(t)]["pnl_pct"]) for t in fresh)
    var_dol = sum(t.dollars(var_reps[id(t)]["pnl_pct"]) for t in fresh)
    prod_mean_r = statistics.fmean(prod_reps[id(t)]["pnl_pct"] for t in fresh)
    var_mean_r = statistics.fmean(var_reps[id(t)]["pnl_pct"] for t in fresh)
    print(f"  fresh window (n={len(fresh)}): sl-none(PROD) ${prod_dol:+,.0f} "
          f"meanR={prod_mean_r:+.4f}  vs  sl-1x ${var_dol:+,.0f} meanR={var_mean_r:+.4f}"
          f"   Δ$={var_dol - prod_dol:+,.0f}  ΔmeanR={var_mean_r - prod_mean_r:+.4f}")


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

    if not calibrate(trades, prod, side):
        # A HARD row means the harness and the stored book disagree about a
        # path both sides claim the same rules for — every variant Δ below
        # would be built on that disagreement. Same stop `harness_gate` makes.
        sys.exit(1)

    if side == "credit":
        credit_rollback_census(trades)

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
