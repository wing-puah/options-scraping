"""Day-0 underlying move: is the stock confirming (or not) information, and is cutting on it worth money?

Follow-on to the 2026-08-12 `be_after` run (`bear_giveback` ARM U), which found
two monotone gradients on bear debit at the MFE PEAK — rows whose stock had
fallen >=6% held their gains, rows whose stock was flat/up gave them back — and
showed the gradient survives the moneyness confound. §5 of that entry left the
underlying-conditioned exit as an operator decision requiring pre-registration.

This moves the question from the peak (unknowable in flight) to the ENTRY
SESSION, which is knowable at its close, and widens the population from bear
debit to the whole book.

  ARM D — descriptive. Conform vs non-conform, cut by market regime, structure,
          and the play's own stock regime. This is the operator's ask. It is
          also PARTLY TAUTOLOGICAL — for a directional spread the underlying
          move IS the P&L driver — so it is not read as evidence until ARM C
          says the effect survives the confound.

  ARM C — confound control. ARM U's method moved to day 0: hold the day-0 mark
          P&L roughly constant and ask whether the underlying move still
          separates FINAL R. Two positions both up 10% on day 0 — one because
          the stock moved 2 sigma, one because IV popped on a flat tape — are
          the whole question. If this flattens, ARM D was measuring mechanics.

  ARM R — the rule. A pre-registered day-0 cut, graded against SHIPPED
          PRODUCTION (not against a baseline production does not run — that
          mistake has now changed a decision twice, see the 08-11 close-out and
          the 08-12 be_after run). `harness.py` is FROZEN and is NOT touched:
          the cut is applied by COMPOSITION around `replay`.

NOTHING HERE CAN BE A SELECTION RULE. The day-0 move is unobservable at entry.
D1 (bear selection unfixable, 0 of 496 subsets) is not re-opened; every claim in
this module is exit management.

Every bucket, threshold and pass criterion below was fixed BEFORE the first run
and is pre-registered in research/current.md. Read-only; touches
no config. Run:

    python -m scripts.backtest_study run next_day_move
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import (  # noqa: E402
    BEAR_DEBIT, cell_stats, fmt_row, hdr, prod_profile_for, sub,
)
from scripts.backtest_study.lib.book import CREDIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import replay  # noqa: E402
from scripts.backtest_study.lib.underlying import (  # noqa: E402
    SRC_OHLC, entry_day, load_bars, move_windows, rescaled_tickers, sigma_1d,
)

# --- PRE-DECLARED, fixed before the first run --------------------------------

# Which way the stock has to go for the structure to be right. Vol structures
# have no direction and are excluded from every conformity cut (n=8 of 795 —
# far too thin to carry their own arm, and pretending otherwise would put an
# 8-row cell next to a 327-row one in the same table).
BULLISH = {"bull_call_spread", "bull_put_spread", "long_call", "short_put"}
BEARISH = {"bear_put_spread", "bear_call_spread", "long_put"}
VOL_STRUCTURES = {"straddle", "strangle"}

# Conformity in units of the one-session move the entry IV was pricing. Signed
# so that positive = the stock went the play's way.
SIGMA_BUCKETS = [(-99.0, -1.5, "moved AGAINST > 1.5 sigma"),
                 (-1.5, -0.5, "against 0.5-1.5 sigma"),
                 (-0.5, 0.5, "flat (within +/-0.5 sigma)"),
                 (0.5, 1.5, "confirmed 0.5-1.5 sigma"),
                 (1.5, 99.0, "confirmed > 1.5 sigma")]

# The same cut in raw percent, because sigma hides how big the move actually was
# and the operator reads percent on a screen.
PCT_BUCKETS = [(-99.0, -0.02, "moved AGAINST > 2%"),
               (-0.02, -0.005, "against 0.5-2%"),
               (-0.005, 0.005, "flat (within +/-0.5%)"),
               (0.005, 0.02, "confirmed 0.5-2%"),
               (0.02, 99.0, "confirmed > 2%")]

# ARM C: bands of day-0 mark P&L inside which the conformity cut is repeated.
DAY0_PNL_BANDS = [(-99.0, -0.25, "day-0 P&L <= -25%"),
                  (-0.25, 0.0, "day-0 P&L -25% to 0"),
                  (0.0, 0.25, "day-0 P&L 0 to +25%"),
                  (0.25, 99.0, "day-0 P&L > +25%")]

# A cell thinner than this is printed with its n and NOT read. Fixed in advance
# so it cannot become "well, n=12 is suggestive" after seeing the numbers.
MIN_CELL_N = 20

# ARM R: the cut thresholds, in sigma of conformity at the entry session close.
RULE_THETAS = [("wrong sign", 0.0),
               ("worse than -0.5 sigma", -0.5),
               ("inside the flat band (+0.5 sigma)", 0.5)]

# ARM R pass criteria, all of which must hold. Restated here so the report can
# print them next to the numbers rather than relying on the reader's memory.
CRITERIA = """  1. paired date-clustered CI vs SHIPPED excludes zero
  2. every leave-one-date-out fold positive (read LOOmin, not the mean)
  3. ex-Mar-Apr-2025 still positive
  4. 2026 alone positive, and no single year carrying the result
  5. both pricing tiers (real, tweak) positive
  6. leak guard: 0 rows changed outside the keyed population"""


# --- enrichment ---------------------------------------------------------------

def direction_sign(structure: str) -> int | None:
    """+1 bullish, -1 bearish, None for vol structures / anything unmapped."""
    if structure in BULLISH:
        return 1
    if structure in BEARISH:
        return -1
    return None


def day0_mark_pnl(rec, entry_session) -> tuple[int, float] | None:
    """`(grid_index, mark P&L)` at the entry session close, or None.

    The index is 1-based to match `replay`'s `days_held`, so the two are
    directly comparable when the wrapper decides which exit came first.
    """
    t = rec["t"]
    if entry_session is None:
        return None
    for i, (day, mark) in enumerate(zip(t.grid, t.marks), start=1):
        if day == entry_session and mark is not None:
            return i, round(t.pnl_of(mark), 10)
    return None


def enrich(recs: list[dict]) -> tuple[list[dict], dict]:
    """Attach day-0 geometry to every row. Returns `(enriched, coverage)`.

    Rows are never silently dropped: everything that fails is counted in
    `coverage`, which the report prints before any table, because the
    denominator is what every number here is quoted against.
    """
    cov = Counter()
    rescaled = rescaled_tickers()
    out = []
    for rec in recs:
        cov["rows"] += 1
        if rec["structure"] in VOL_STRUCTURES:
            cov["vol_structure_excluded"] += 1
            continue
        dir_sign = direction_sign(rec["structure"])
        if dir_sign is None:
            cov["unmapped_structure"] += 1
            continue
        bars = load_bars(rec["ticker"])
        if not bars:
            cov["no_bars"] += 1
            continue
        mw = move_windows(rec["t"], bars)
        if mw["entry_day"] is None or mw["source"] is None:
            cov["no_entry_session_bar"] += 1
            continue
        d0 = day0_mark_pnl(rec, mw["entry_day"])
        if d0 is None:
            cov["no_day0_mark"] += 1
            continue
        cov["ohlc" if mw["source"] == SRC_OHLC else "close_only"] += 1
        is_rescaled = rec["ticker"].upper() in rescaled
        if is_rescaled:
            cov["rescaled_basis"] += 1
        sig = sigma_1d(rec["iv_entry"])
        if sig is None:
            cov["no_iv_no_sigma"] += 1

        e = dict(rec)
        e["dir_sign"] = dir_sign
        e["day0_i"], e["day0_pnl"] = d0
        e["sigma_1d"] = sig
        e["rescaled"] = is_rescaled
        for win in ("W0", "W1", "WG", "W1C"):
            w = mw[win]
            # Percent and sigma are ratios off ONE series, so a split-adjusted
            # basis cancels and they stay valid. The absolute dollar move does
            # not: it would be an adjusted-basis dollar sitting in a mean with
            # unadjusted ones. Withheld rather than converted.
            e[f"{win}_abs"] = (w["abs"] * dir_sign) if (w and not is_rescaled) else None
            e[f"{win}_pct"] = (w["pct"] * dir_sign) if w else None
            e[f"{win}_sigma"] = ((w["pct"] * dir_sign) / sig) if (w and sig) else None
        # Unsigned versions of the primary window, for "how big was the move"
        # questions where direction is not the point.
        e["W0_pct_raw"] = mw["W0"]["pct"] if mw["W0"] else None
        e["bar_source"] = mw["source"]
        e["entry_session"] = mw["entry_day"]
        out.append(e)
        if mw["W0"] is not None:
            cov["W0_usable"] += 1
        if mw["W1"] is not None:
            cov["W1_usable"] += 1
        if mw["WG"] is not None:
            cov["WG_usable"] += 1
        if mw["W0"] is not None and sig:
            cov["W0_sigma_usable"] += 1
    return out, cov


# --- shared table helpers -----------------------------------------------------

def bucket_rows(rows: list[dict], key: str, buckets) -> list[tuple[str, list[dict]]]:
    out = []
    for lo, hi, name in buckets:
        out.append((name, [r for r in rows if r.get(key) is not None
                           and lo <= r[key] < hi]))
    return out


def conform_split(rows: list[dict], key: str = "W0_pct") -> dict:
    """`{"confirmed": rows, "did not": rows}` on the sign of the window move."""
    return {"stock CONFIRMED": [r for r in rows if r.get(key) is not None and r[key] > 0],
            "stock did NOT":   [r for r in rows if r.get(key) is not None and r[key] <= 0]}


def move_summary(rows: list[dict], win: str) -> str:
    """Mean absolute $ and % move for a set of rows, both signed to the play."""
    a = [r[f"{win}_abs"] for r in rows if r.get(f"{win}_abs") is not None]
    p = [r[f"{win}_pct"] for r in rows if r.get(f"{win}_pct") is not None]
    s = [r[f"{win}_sigma"] for r in rows if r.get(f"{win}_sigma") is not None]
    if not p:
        return "(no move data)"
    return (f"move ${statistics.fmean(a):>+6.2f}  {statistics.fmean(p):>+6.2%}  "
            f"{statistics.fmean(s):>+5.2f}sig" if a else
            f"move {statistics.fmean(p):>+6.2%}  {statistics.fmean(s):>+5.2f}sig")


def print_cells(pairs, width=34, min_n: int = 0) -> None:
    for label, rows in pairs:
        if not rows:
            print(f"  {label:<{width}}  (no rows)")
            continue
        thin = "  <- n<%d, NOT READ" % min_n if (min_n and len(rows) < min_n) else ""
        print(fmt_row(label, cell_stats(rows), width=width) + thin)


# =============================================================================
# ARM D — descriptive
# =============================================================================

def arm_d(rows: list[dict]) -> None:
    hdr("ARM D — did the stock confirm on the entry session, and did it matter?")
    print("""  W0 (PRIMARY) = entry OPEN -> entry CLOSE, the session the position was
  actually filled in. Signed to the play: positive means the stock went the way
  the structure needed. Absolute $ move is reported but never buckets anything —
  $5 on a $600 stock and on a $20 stock are not the same event.

  THIS TABLE IS PARTLY TAUTOLOGICAL and is not evidence on its own: for a
  directional spread the underlying move is the P&L driver, so "stock went our
  way, position made money" is mechanics. ARM C is the test that decides whether
  anything here is real.""")

    for win, title in (("W0", "W0 — entry open -> entry close (PRIMARY)"),
                       ("W1", "W1 — entry open -> next close"),
                       ("W1C", "W1C — entry close -> next close (close-to-close, the "
                               "only window a fallback row can support)")):
        have = [r for r in rows if r.get(f"{win}_pct") is not None]
        if not have:
            continue
        sub(f"{title}   n={len(have)}")
        for label, rs in conform_split(have, f"{win}_pct").items():
            print(fmt_row(label, cell_stats(rs), width=34))
            print(f"      {move_summary(rs, win)}")

    w0 = [r for r in rows if r.get("W0_pct") is not None]

    sub("W0 by SIGMA bucket (how far it moved, relative to what was priced)")
    print_cells(bucket_rows(w0, "W0_sigma", SIGMA_BUCKETS), min_n=MIN_CELL_N)

    sub("W0 by RAW PERCENT bucket")
    print_cells(bucket_rows(w0, "W0_pct", PCT_BUCKETS), min_n=MIN_CELL_N)

    # --- the three requested dimensions, MARGINALLY first ---
    sub("MARGINAL CUT 1 — market regime (model_dir / model_vol)")
    for field in ("model_dir", "model_vol"):
        for val in sorted({r[field] for r in w0 if r[field]}):
            grp = [r for r in w0 if r[field] == val]
            print(f"\n  [{field} = {val}]  n={len(grp)}")
            print_cells([(k, v) for k, v in conform_split(grp).items()], width=30)

    sub("MARGINAL CUT 2 — structure")
    for st in sorted({r["structure"] for r in w0}):
        grp = [r for r in w0 if r["structure"] == st]
        print(f"\n  [{st}]  n={len(grp)}")
        print_cells([(k, v) for k, v in conform_split(grp).items()], width=30)

    sub("MARGINAL CUT 3 — stock regime (the play's own read, NOT the market's)")
    for field in ("stock_dir", "stock_vol"):
        for val in sorted({r[field] for r in w0 if r[field]}):
            grp = [r for r in w0 if r[field] == val]
            print(f"\n  [{field} = {val}]  n={len(grp)}")
            print_cells([(k, v) for k, v in conform_split(grp).items()], width=30)

    sub("PRE-DECLARED 2-WAY — structure x market direction")
    for st in ("bear_put_spread", "bull_call_spread", "bull_put_spread"):
        for d in ("BULL", "BEAR", "RANGE"):
            grp = [r for r in w0 if r["structure"] == st and r["model_dir"] == d]
            if len(grp) < MIN_CELL_N:
                continue
            print(f"\n  [{st} x market {d}]  n={len(grp)}")
            print_cells([(k, v) for k, v in conform_split(grp).items()], width=30)

    sub("PRE-DECLARED 2-WAY — structure x stock direction")
    for st in ("bear_put_spread", "bull_call_spread", "bull_put_spread"):
        for d in ("BULL", "BEAR", "RANGE"):
            grp = [r for r in w0 if r["structure"] == st and r["stock_dir"] == d]
            if len(grp) < MIN_CELL_N:
                continue
            print(f"\n  [{st} x stock {d}]  n={len(grp)}")
            print_cells([(k, v) for k, v in conform_split(grp).items()], width=30)

    sub("APPENDIX (DESCRIPTIVE ONLY) — market x structure x stock direction")
    print("  Cells are thin by construction. Printed because it was asked for;\n"
          "  nothing in it clears a promotion bar and n<%d is not read." % MIN_CELL_N)
    for md in ("BULL", "BEAR", "RANGE"):
        for st in ("bear_put_spread", "bull_call_spread", "bull_put_spread"):
            for sd in ("BULL", "BEAR", "RANGE"):
                grp = [r for r in w0 if r["model_dir"] == md and r["structure"] == st
                       and r["stock_dir"] == sd]
                if not grp:
                    continue
                stats = cell_stats(grp)
                conf = [r for r in grp if r["W0_pct"] > 0]
                print(f"  mkt {md:<5} {st:<17} stock {sd:<5} n={len(grp):>3} "
                      f"conf {len(conf):>3}  meanR {stats['mean']:>+6.3f}  "
                      f"${stats['dol']:>9,.0f}" +
                      ("  <- NOT READ" if len(grp) < MIN_CELL_N else ""))

    # --- WG: what the entry basis costs ---
    wg = [r for r in rows if r.get("WG_pct") is not None]
    if wg:
        sub("WG — the gap between the signal close and the fill (NOT tradeable)")
        print("""  This move happens BEFORE the position exists: it is already inside the
  entry price under `entry_timing: next_open`. It is measured to price what
  the next-open basis costs, not because anything can be done about it.""")
        favour = [r for r in wg if r["WG_pct"] > 0]
        against = [r for r in wg if r["WG_pct"] <= 0]
        print(f"  gapped the play's WAY     n={len(favour):>4}  "
              f"mean {statistics.fmean(r['WG_pct'] for r in favour):>+6.2%}"
              if favour else "  (none)")
        print(f"  gapped AGAINST the play   n={len(against):>4}  "
              f"mean {statistics.fmean(r['WG_pct'] for r in against):>+6.2%}"
              if against else "  (none)")
        allsig = [r["WG_sigma"] for r in wg if r.get("WG_sigma") is not None]
        if allsig:
            print(f"  overall mean gap          {statistics.fmean(r['WG_pct'] for r in wg):>+6.2%}  "
                  f"({statistics.fmean(allsig):>+.2f} sigma), n={len(wg)}")
        print(fmt_row("  gapped our way -> outcome", cell_stats(favour), width=32))
        print(fmt_row("  gapped against -> outcome", cell_stats(against), width=32))


# =============================================================================
# ARM C — confound control
# =============================================================================

def arm_c(rows: list[dict]) -> None:
    hdr("ARM C — does the day-0 move survive holding day-0 P&L constant?")
    print("""  The ARM D tables cannot separate "the stock moved and that is information"
  from "the stock moved, therefore the mark moved, therefore P&L". This is ARM
  U's control (2026-08-12) moved to day 0: inside a band of day-0 mark P&L, the
  position is roughly equally green either way, so any REMAINING separation in
  FINAL R is the underlying telling us something the mark had not already said.

  Read it as: does the ordering inside a band still run the same way as the
  headline? If it flattens, ARM D was mechanics and the pre-committed answer is
  NO RULE — see the module docstring.""")

    w0 = [r for r in rows if r.get("W0_sigma") is not None and r.get("R") is not None]
    print(f"\n  rows with both a day-0 sigma move and a realized R: {len(w0)}")

    for lo, hi, band in DAY0_PNL_BANDS:
        band_rows = [r for r in w0 if lo <= r["day0_pnl"] < hi]
        print(f"\n  [{band}]  n={len(band_rows)}"
              + ("  — too thin, NOT READ" if len(band_rows) < MIN_CELL_N else ""))
        if not band_rows:
            continue
        print_cells(bucket_rows(band_rows, "W0_sigma", SIGMA_BUCKETS),
                    width=34, min_n=MIN_CELL_N)

    sub("the same control, collapsed to confirmed / not, per band")
    print(f"  {'band':<26} {'n':>4}  {'confirmed meanR':>16}  {'not meanR':>12}  {'gap':>8}")
    for lo, hi, band in DAY0_PNL_BANDS:
        band_rows = [r for r in w0 if lo <= r["day0_pnl"] < hi]
        conf = [r["R"] for r in band_rows if r["W0_pct"] > 0]
        nots = [r["R"] for r in band_rows if r["W0_pct"] <= 0]
        if not conf or not nots:
            print(f"  {band:<26} {len(band_rows):>4}  (one side empty)")
            continue
        a, b = statistics.fmean(conf), statistics.fmean(nots)
        thin = "  <- NOT READ" if min(len(conf), len(nots)) < MIN_CELL_N else ""
        print(f"  {band:<26} {len(band_rows):>4}  {a:>+16.3f}  {b:>+12.3f}  "
              f"{a - b:>+8.3f}{thin}")


# =============================================================================
# ARM R — the pre-registered rule
# =============================================================================

def is_bear_debit(rec: dict) -> bool:
    return rec["structure"] in BEAR_DEBIT and not rec["credit"]


def shipped_profile(rec: dict) -> dict:
    """The exit profile PRODUCTION would actually have run on this row.

    Credits take `CREDIT_PROD` (pt 0.65, no stop) and reach NEITHER overlay:
    config/backtest.yml states the structure_exit and regime_exit merges are
    debit-only ("Credits never reach it"). Routing a credit row through
    `prod_profile_for` would replay it under debit knobs — a wrong baseline, and
    grading against a baseline production does not run is the exact error this
    log has recorded twice.
    """
    if rec["credit"]:
        return dict(CREDIT_PROD)
    return prod_profile_for(rec, 0.50, True)


def apply_day0_cut(rec: dict, profile: dict, theta: float | None,
                   keyed_to=None) -> dict:
    """SHIPPED replay, optionally pre-empted by a day-0 non-confirmation cut.

    `harness.py` is FROZEN, so this is composition, not a new exit mechanism:
    the baseline replay runs untouched and its result is used verbatim whenever
    it already exited at or before the entry session. The cut can only ever
    replace an exit that would have happened LATER.

    `keyed_to` is a predicate on the row — the rule's KEYING, evaluated inside
    this function rather than by pre-filtering the caller's list. That is what
    makes the leak guard a real test: a keyed run is fed the whole book, and any
    row outside the key that moves is a keying bug.
    """
    t = rec["t"]
    base = replay(t, **profile)
    if theta is None:
        return base
    if keyed_to is not None and not keyed_to(rec):
        return base
    sig_move = rec.get("W0_sigma")
    if sig_move is None or sig_move >= theta:
        return base
    day0_i, day0_pnl = rec["day0_i"], rec["day0_pnl"]
    if base["days_held"] < day0_i:
        return base           # production got out first; the cut never fires
    return dict(exit_reason="day0_cut", days_held=day0_i, pnl_pct=day0_pnl)


def arm_r(rows: list[dict], all_recs: list[dict]) -> None:
    hdr("ARM R — the pre-registered day-0 cut, graded against SHIPPED PRODUCTION")
    print("""  Baseline is the SHIPPED merge (base -> structure_exit -> regime_exit), via
  bear_giveback.prod_profile_for(rec, 0.50, True) — the same function whose
  calibration is already published, so there is no second source of truth for
  the production knobs. Grading against a baseline production does not run has
  changed a decision TWICE in this log; it is not repeated here.

  Pass criteria (ALL must hold):
""" + CRITERIA)

    populations = [
        ("whole book", rows),
        ("all debit", [r for r in rows if not r["credit"]]),
        ("bear debit", [r for r in rows if r["structure"] in BEAR_DEBIT and not r["credit"]]),
    ]

    for pop_name, pop in populations:
        pop = [r for r in pop if r.get("W0_sigma") is not None]
        if len(pop) < MIN_CELL_N:
            print(f"\n  [{pop_name}] n={len(pop)} — too thin, skipped")
            continue
        sub(f"{pop_name}  (n={len(pop)} with a day-0 sigma move)")

        base = {id(r): apply_day0_cut(r, shipped_profile(r), None)
                for r in pop}
        base_mean = statistics.fmean(base[id(r)]["pnl_pct"] for r in pop)
        base_dol = sum(r["t"].dollars(base[id(r)]["pnl_pct"]) for r in pop)
        print(f"  SHIPPED baseline: meanR {base_mean:>+7.3f}   ${base_dol:>12,.0f}")
        print(f"  {'variant':<38} {'meanR':>7} {'Dship':>8}  {'CI95 (date-clust)':>22} "
              f"{'LOOmin':>8} {'$':>12} {'chg':>5}")

        for label, theta in RULE_THETAS:
            var = {id(r): apply_day0_cut(r, shipped_profile(r), theta)
                   for r in pop}
            paired = [dict(date=r["date"], a=var[id(r)]["pnl_pct"], b=base[id(r)]["pnl_pct"])
                      for r in pop]
            changed = sum(1 for p in paired if abs(p["a"] - p["b"]) > 1e-9)
            mean_r = statistics.fmean(p["a"] for p in paired)
            dol = sum(r["t"].dollars(var[id(r)]["pnl_pct"]) for r in pop)
            if changed == 0:
                ci_s, loo_s, star = "(identical to shipped)".rjust(22), "       -", ""
            else:
                lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=4000)
                _, _, loo_min, _ = P.loo_by_date(paired, lambda p: p["a"], lambda p: p["b"])
                ci_s = f"[{lo:+.3f}, {hi:+.3f}]".rjust(22)
                loo_s = f"{loo_min:+8.3f}"
                star = "  **" if (lo > 0 and loo_min > 0) else ""
            print(f"  cut when {label:<29} {mean_r:>+7.3f} {mean_r - base_mean:>+8.3f}  "
                  f"{ci_s} {loo_s} {dol:>12,.0f} {changed:>5}{star}")
        print("\n  ** = CI excludes zero AND every LOO-by-date fold positive. Criteria 3-6 below.")

        # --- criteria 3/4/5 on every variant that changed anything ---
        for label, theta in RULE_THETAS:
            var = {id(r): apply_day0_cut(r, shipped_profile(r), theta)
                   for r in pop}
            paired = [dict(date=r["date"], a=var[id(r)]["pnl_pct"], b=base[id(r)]["pnl_pct"],
                           source=r["source"]) for r in pop]
            if not any(abs(p["a"] - p["b"]) > 1e-9 for p in paired):
                continue
            print(f"\n  [{label}]")
            for cut_name, cut_rows in P.window_cuts(paired).items():
                if not cut_rows:
                    continue
                g = statistics.fmean(p["a"] - p["b"] for p in cut_rows)
                print(f"    {cut_name:<18} n={len(cut_rows):>4}  gain {g:>+7.3f}")
            years = P.by_year(paired)
            print("    years: " + "  ".join(
                f"{y} {statistics.fmean(p['a'] - p['b'] for p in rs):+.3f} (n={len(rs)})"
                for y, rs in years.items()))
            for tier in ("real", "tweak"):
                rs = [p for p in paired if p["source"] == tier]
                if rs:
                    print(f"    pricing tier {tier:<6} n={len(rs):>4}  "
                          f"gain {statistics.fmean(p['a'] - p['b'] for p in rs):>+7.3f}")

    sub("LEAK GUARD — rows outside the keyed population must be untouched")
    print("""  A bear-keyed cut is run over the WHOLE book with the keying evaluated
  inside apply_day0_cut, not by pre-filtering the row list. Pre-filtering would
  make this vacuous — the rule could not touch a row it was never handed. Here
  it could, and must not.""")
    for label, theta in RULE_THETAS:
        changed_in, changed_out = 0, 0
        for r in rows:
            prof = shipped_profile(r)
            base = apply_day0_cut(r, prof, None)
            keyed = apply_day0_cut(r, prof, theta, keyed_to=is_bear_debit)
            if abs(keyed["pnl_pct"] - base["pnl_pct"]) > 1e-9:
                if is_bear_debit(r):
                    changed_in += 1
                else:
                    changed_out += 1
        verdict = "OK" if changed_out == 0 else "*** LEAK ***"
        print(f"  cut when {label:<34} bear rows changed {changed_in:>4}   "
              f"non-bear changed {changed_out:>4}   {verdict}")
    print("  0 in the non-bear column is the only acceptable number.")

    # Rows the book has but this study could not use — quoted so the ARM R
    # population is never mistaken for the whole book.
    print(f"\n  ARM R population note: {len(rows)} of {len(all_recs)} book rows carry a "
          f"day-0 move; the rest are counted in the coverage table above.")


# =============================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", default="DCR", help="subset of D/C/R to run")
    a = ap.parse_args(argv)

    recs, diag = load_book(include_bs=False)
    print(f"book: {len(recs)} rows  counts_by_source={diag['counts_by_source']}  "
          f"date_range={diag['date_range']}  (bs excluded)")

    rows, cov = enrich(recs)
    hdr("COVERAGE — the denominator every number below is quoted against")
    print(f"  book rows                        {cov['rows']:>5}")
    print(f"  excluded, vol structure          {cov['vol_structure_excluded']:>5}")
    print(f"  excluded, unmapped structure     {cov['unmapped_structure']:>5}")
    print(f"  excluded, no underlying bars     {cov['no_bars']:>5}")
    print(f"  excluded, no entry-session bar   {cov['no_entry_session_bar']:>5}")
    print(f"  excluded, no day-0 option mark   {cov['no_day0_mark']:>5}")
    print(f"  USABLE                           {len(rows):>5}")
    print(f"    of which real stock OHLC       {cov['ohlc']:>5}")
    print(f"    of which close-only fallback   {cov['close_only']:>5}")
    print(f"    on a split-adjusted basis      {cov['rescaled_basis']:>5}"
          "   ($ move withheld; % and sigma valid)")
    print(f"    with no entry IV (no sigma)    {cov['no_iv_no_sigma']:>5}")
    print(f"  W0 usable (PRIMARY)              {cov['W0_usable']:>5}")
    print(f"  W0 usable in sigma units         {cov['W0_sigma_usable']:>5}")
    print(f"  W1 usable                        {cov['W1_usable']:>5}")
    print(f"  WG usable                        {cov['WG_usable']:>5}")
    print("\n  A close-only row has no OPEN, so it contributes to W1C and to nothing\n"
          "  else. W0/W1/WG counts are therefore <= the OHLC count, never the\n"
          "  USABLE count — do not quote a W0 result against the book total.")

    by_src = Counter(r["bar_source"] for r in rows)
    by_struct = Counter(r["structure"] for r in rows)
    print(f"\n  bar sources: {dict(by_src)}")
    print(f"  structures:  {dict(by_struct)}")

    if "D" in a.arms:
        arm_d(rows)
    if "C" in a.arms:
        arm_c(rows)
    if "R" in a.arms:
        arm_r(rows, recs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
