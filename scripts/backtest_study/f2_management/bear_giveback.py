"""Bear MFE give-back: production-baseline threshold test, underlying-path pattern, deployment stats.

Three arms, run together because they answer one operator question — "bear
positions still show MFE but most of it is given back; can we capture a pattern,
and give me deploy-time numbers to look at".

  ARM P — PRODUCTION baseline for the `be_after` threshold. `bear_arm.py`'s grid
          measures against DEBIT_PROD (no trail). Production is NOT that: it
          ships the BEAR_HE 0.50/0.50 trail plus `be_after: 0.50` suppressed
          inside BEAR_HE. The 08-11 close-out recorded that this gap made the
          study delta 3x the real one. This arm replays the SHIPPED merge
          (base -> structure -> regime) so the number quoted is the one the book
          would actually have earned.

          It also re-opens A3, which was decided for @.50 ONLY. Inside BEAR_HE
          the trail arms at peak >= 0.50 and its floor (peak - 0.50) is then
          >= 0, which is what made @.50 strictly dominated there. A ratchet at
          0.30 arms at peak >= 0.30 — on rows peaking in [0.30, 0.50) the trail
          NEVER arms and the ratchet would. So the suppression decision does not
          automatically carry down, and both variants are measured.

  ARM U — does the underlying price path explain the give-back? Every feature is
          observable IN FLIGHT (at the moment the position is up X%), so this is
          exit MANAGEMENT conditioning, not entry selection — D1 settled that
          bear selection is unfixable from these columns and this arm does not
          re-open it. Buckets are pre-declared below; no search.

  ARM S — deployment reference stats: n / win rate / profit factor / mean R by
          structure x regime and by ladder tier. Descriptive, for the operator
          card. These are IN-SAMPLE book summaries, not predictions.

Read-only. Touches no config. Run:

    python -m scripts.backtest_study run bear_giveback
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib.book import DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import replay  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402

BEAR_DEBIT = ("bear_put_spread", "long_put")

# --- the SHIPPED production profiles, transcribed from config/backtest.yml -----
# base debit
PROD_BASE = dict(DEBIT_PROD)
# regime_exit.cells.BEAR_HE  (trail on, ratchet explicitly nulled)
PROD_BEAR_HE = {**DEBIT_PROD, "trig": 0.50, "trail": 0.50, "be_after": None}
# structure_exit.cells.bear_debit  (applies on every NON-BEAR_HE date)
PROD_BEAR_DEBIT = {**DEBIT_PROD, "be_after": 0.50}

# ARM U pre-declared buckets. Fixed before looking at any output.
DAYS_TO_MFE_BUCKETS = [(0, 3, "peak within 3d"), (3, 8, "peak 4-8d"),
                       (8, 20, "peak 9-20d"), (20, 999, "peak >20d")]
UND_MOVE_BUCKETS = [(-999, -0.06, "stock -6% or worse"), (-0.06, -0.03, "stock -3% to -6%"),
                    (-0.03, -0.01, "stock -1% to -3%"), (-0.01, 999, "stock flat/up")]


def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


def profit_factor(dols: list[float]) -> float | None:
    """Gross wins / |gross losses|. None when there is no losing side to divide by."""
    wins = sum(d for d in dols if d > 0)
    loss = -sum(d for d in dols if d < 0)
    if loss <= 0:
        return None
    return wins / loss


def cell_stats(rows: list[dict], key="R") -> dict:
    """n / win rate / profit factor / mean-median R / $ PLUS the path stats.

    MFE and MAE come off the stored row (`mfe_pct` / `mae_pct`), not the replay,
    so they describe the path the position actually walked regardless of which
    exit rule closed it. Two derived ratios:
      giveback = |mean MAE| / mean MFE — path asymmetry. >1 means the average
                 position spent more time under water than it ever showed green.
      capture  = mean R / mean MFE — how much of the shown profit the exit rule
                 actually banked. Low capture with high MFE is an EXIT problem;
                 low MFE is a SELECTION problem. (see MEMORY: never read these
                 cells on realized P&L alone.)
    """
    vals = [r[key] for r in rows if r.get(key) is not None]
    dols = [r[key + "_dol"] for r in rows if r.get(key + "_dol") is not None]
    if not vals:
        return {}
    mfes = [r["mfe"] for r in rows if r.get("mfe") is not None]
    maes = [r["mae"] for r in rows if r.get("mae") is not None]
    mfe = statistics.fmean(mfes) if mfes else None
    mae = statistics.fmean(maes) if maes else None
    return dict(n=len(vals), win=sum(1 for v in vals if v > 0) / len(vals),
                mean=statistics.fmean(vals), med=statistics.median(vals),
                pf=profit_factor(dols), dol=sum(dols),
                mfe=mfe, mae=mae, n_path=len(mfes),
                giveback=(abs(mae) / mfe) if (mfe and mae is not None and mfe > 0) else None,
                capture=(statistics.fmean(vals) / mfe) if (mfe and mfe > 0) else None)


def fmt_row(label: str, s: dict, width=30) -> str:
    if not s:
        return f"  {label:<{width}}  (no rows)"
    pf = f"{s['pf']:5.2f}" if s["pf"] is not None else "  inf"
    mfe = f"{s['mfe']:>+6.2f}" if s["mfe"] is not None else "     -"
    mae = f"{s['mae']:>+6.2f}" if s["mae"] is not None else "     -"
    gb = f"{s['giveback']:>5.2f}" if s["giveback"] is not None else "    -"
    cap = f"{s['capture']:>+6.2f}" if s["capture"] is not None else "     -"
    return (f"  {label:<{width}} n={s['n']:>4}  win {s['win']:>5.0%}  PF {pf}  "
            f"meanR {s['mean']:>+6.3f}  ${s['dol']:>10,.0f}  "
            f"MFE {mfe}  MAE {mae}  gb {gb}  cap {cap}")


# =============================================================================
# ARM P — production-baseline threshold test
# =============================================================================

def prod_profile_for(rec: dict, be_after: float | None, suppress_in_bear_he: bool) -> dict:
    """Merge base -> structure_exit -> regime_exit exactly as simulate.py does.

    `be_after=None` reproduces the SHIPPED book only if callers also pass the
    shipped 0.50; it is the knob under test, not a disable switch.
    """
    is_bear_debit = rec["structure"] in BEAR_DEBIT and not rec["credit"]
    cfg = dict(PROD_BASE)
    if is_bear_debit and be_after is not None:          # structure_exit
        cfg["be_after"] = be_after
    if rec["mech_cell"] == "BEAR_HE":                    # regime_exit merges LAST
        cfg["trig"], cfg["trail"] = 0.50, 0.50
        if suppress_in_bear_he:
            cfg["be_after"] = None
    return cfg


def arm_p(bear: list[dict], nonbear_debit: list[dict], credits: list[dict]) -> None:
    hdr("ARM P — the be_after threshold measured against SHIPPED PRODUCTION")
    print("""  bear_arm.py grades every variant against DEBIT_PROD (pt .90 / sl .75 /
  tef .75, NO trail). Production is not that. This arm replays the shipped
  merge so the delta quoted is the one the book would actually have earned.

  A3 IS RE-OPENED HERE, deliberately: it was decided for @.50, where the
  BEAR_HE trail strictly dominates the ratchet. At a lower threshold the
  ratchet arms on rows the trail never reaches, so 'suppress' and 'stack'
  are genuinely different books and both are measured.""")

    variants = [("SHIPPED  be .50, suppressed in BEAR_HE", 0.50, True)]
    for thr in (0.40, 0.30, 0.25, 0.20):
        variants.append((f"be {thr:.2f}, suppressed in BEAR_HE", thr, True))
        variants.append((f"be {thr:.2f}, STACKED in BEAR_HE", thr, False))

    base_r = {id(rec): replay(rec["t"], **prod_profile_for(rec, 0.50, True))["pnl_pct"]
              for rec in bear}
    rows_out = []
    for label, thr, suppress in variants:
        per_row = {id(rec): replay(rec["t"], **prod_profile_for(rec, thr, suppress))
                   for rec in bear}
        paired = [dict(date=rec["date"], a=per_row[id(rec)]["pnl_pct"], b=base_r[id(rec)])
                  for rec in bear]
        changed = sum(1 for p in paired if abs(p["a"] - p["b"]) > 1e-9)
        bhc = sum(1 for rec in bear if rec["mech_cell"] == "BEAR_HE"
                  and abs(per_row[id(rec)]["pnl_pct"] - base_r[id(rec)]) > 1e-9)
        mean_r = statistics.fmean(p["a"] for p in paired)
        dmean = mean_r - statistics.fmean(p["b"] for p in paired)
        dol = sum(rec["t"].dollars(per_row[id(rec)]["pnl_pct"]) for rec in bear)
        mix = Counter(r["exit_reason"] for r in per_row.values())
        rows_out.append((label, mean_r, dmean, paired, dol, changed, bhc, mix))

    sub(f"bear debit under production (n={len(bear)}) — delta vs SHIPPED")
    print(f"  {'variant':<40} {'meanR':>7} {'Δship':>8}  {'CI95 (date-clust)':>22} "
          f"{'LOOmin':>8} {'$':>11} {'chg':>5} {'BEAR_HE':>8}")
    for label, mean_r, dmean, paired, dol, changed, bhc, mix in rows_out:
        star = ""
        if changed == 0:
            ci_s, loo_s = "(identical to shipped)".rjust(22), "       —"
        else:
            lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=4000)
            _, _, loo_min, _ = P.loo_by_date(paired, lambda p: p["a"], lambda p: p["b"])
            ci_s = f"[{lo:+.3f}, {hi:+.3f}]".rjust(22)
            loo_s = f"{loo_min:+8.3f}"
            if lo > 0 and loo_min > 0:
                star = "  **"
        print(f"  {label:<40} {mean_r:>+7.3f} {dmean:>+8.3f}  {ci_s} {loo_s} "
              f"{dol:>11,.0f} {changed:>5} {bhc:>8}{star}")
    print("\n  ** = paired date-clustered CI excludes zero AND every LOO-by-date fold positive.")
    print("  'BEAR_HE' = how many of the changed rows sit in the suppressed cell.")

    sub("year cuts on the leading candidates (rule 4 — a pooled win is not enough)")
    for label, _, _, paired, _, changed, _, _ in rows_out:
        if changed == 0 or "SHIPPED" in label:
            continue
        by_year: dict[str, list] = defaultdict(list)
        for p in paired:
            by_year[str(p["date"])[:4]].append(p)
        cells = []
        for y in sorted(by_year):
            g = statistics.fmean(p["a"] - p["b"] for p in by_year[y])
            cells.append(f"{y} {g:+.3f} (n={len(by_year[y])})")
        print(f"  {label:<40} " + "  ".join(cells))

    sub("exit mix, shipped vs the leading candidate")
    for label, _, _, _, _, _, _, mix in rows_out:
        if "SHIPPED" in label or "be 0.30, suppressed" in label or "be 0.30, STACKED" in label:
            print(f"  {label:<40} " + "  ".join(f"{k}:{v}" for k, v in sorted(mix.items())))

    sub("LEAK GUARD — the rule is bear-keyed, so these books must be untouched")
    for name, pop in (("non-bear debit", nonbear_debit), ("credit", credits)):
        if not pop:
            continue
        changed = 0
        for rec in pop:
            a = replay(rec["t"], **prod_profile_for(rec, 0.50, True))
            b = replay(rec["t"], **prod_profile_for(rec, 0.30, True))
            if abs(a["pnl_pct"] - b["pnl_pct"]) > 1e-9:
                changed += 1
        print(f"  {name:<20} n={len(pop):>4}  rows changed by be .50 -> be .30: {changed}")
    print("""  (structure_exit is keyed on bear_put_spread/long_put with entry_net >= 0, so
  a non-bear row can only change if the keying itself is broken. 0 is the only
  acceptable number here; anything else is a bug, not a finding.)""")


# =============================================================================
# ARM U — underlying price path
# =============================================================================

def arm_u(bear: list[dict]) -> None:
    hdr("ARM U — does the UNDERLYING path explain the give-back?")
    print("""  Every feature below is observable IN FLIGHT — at the moment the position
  is up X%, the operator can see how many days it took and what the stock did.
  This is exit-management conditioning, NOT entry selection: D1 (0 of 496
  subsets) settled that bear selection is unfixable and nothing here re-opens
  it. Buckets were fixed in the module header before the first run.""")

    enriched, no_und = [], 0
    for rec in bear:
        t = rec["t"]
        und = t._load_underlying()
        if not und:
            no_und += 1
            continue
        marks = [(d, m) for d, m in zip(t.grid, t.marks) if m is not None]
        if not marks:
            continue
        pls = [(d, round(t.pnl_of(m), 10)) for d, m in marks]
        peak_day, peak = max(pls, key=lambda x: x[1])
        entry_spot = und.get(marks[0][0])
        peak_spot = und.get(peak_day)
        if entry_spot is None or peak_spot is None or entry_spot <= 0:
            continue
        # spot at the row's actual realized exit day
        exit_i = rec["days_held"] or len(pls)
        exit_day = pls[min(exit_i, len(pls)) - 1][0]
        exit_spot = und.get(exit_day)
        enriched.append(dict(
            rec=rec, peak=peak,
            days_to_peak=(peak_day - marks[0][0]).days,
            und_at_peak=(peak_spot - entry_spot) / entry_spot,
            und_at_exit=((exit_spot - entry_spot) / entry_spot) if exit_spot else None,
            retrace=((exit_spot - peak_spot) / peak_spot) if exit_spot and peak_spot else None,
        ))
    print(f"\n  usable rows: {len(enriched)} of {len(bear)}  "
          f"({no_und} lacked cached underlying history)")

    green = [e for e in enriched if e["peak"] > 0.01]
    print(f"  of those, ever green (peak > +1%): {len(green)}")

    def gb_line(label, rows):
        if not rows:
            return f"  {label:<28}  (no rows)"
        gave = [e for e in rows if e["rec"]["R"] is not None and e["rec"]["R"] <= 0]
        Rs = [e["rec"]["R"] for e in rows if e["rec"]["R"] is not None]
        dol = sum(e["rec"]["R_dol"] for e in rows if e["rec"]["R_dol"] is not None)
        return (f"  {label:<28} n={len(rows):>4}  give-back {len(gave) / len(rows):>4.0%}  "
                f"meanR {statistics.fmean(Rs):>+6.3f}  meanPeak {statistics.fmean(e['peak'] for e in rows):>+5.2f}  "
                f"${dol:>9,.0f}")

    sub("give-back rate by DAYS TO PEAK (green rows only)")
    for lo, hi, name in DAYS_TO_MFE_BUCKETS:
        print(gb_line(name, [e for e in green if lo <= e["days_to_peak"] < hi]))

    sub("give-back rate by UNDERLYING MOVE AT PEAK (green rows only)")
    print("  how far the stock had actually fallen when the position was at its best")
    for lo, hi, name in UND_MOVE_BUCKETS:
        print(gb_line(name, [e for e in green if lo <= e["und_at_peak"] < hi]))

    sub("the retrace itself — what the stock did between peak and exit")
    for lab, rows in (("gave it all back (R<=0)", [e for e in green if e["rec"]["R"] <= 0]),
                      ("held a gain (R>0)", [e for e in green if e["rec"]["R"] > 0])):
        rt = [e["retrace"] for e in rows if e["retrace"] is not None]
        up = [e["und_at_peak"] for e in rows]
        if not rt:
            continue
        print(f"  {lab:<26} n={len(rt):>4}  stock move peak->exit  "
              f"mean {statistics.fmean(rt):>+6.2%}  median {statistics.median(rt):>+6.2%}   "
              f"| stock at peak mean {statistics.fmean(up):>+6.2%}")

    sub("CONFOUND CONTROL — is 'stock fell more' just 'position is deeper ITM'?")
    print("""  A bear spread with the stock down 8% is near max value: of course it holds.
  That cut would be tautological. The non-tautological question is whether, among
  positions at the SAME peak P&L, the underlying move still separates them — two
  rows both up 50%, one because the stock fell hard and one because IV popped on
  a flat tape. Only the second is a decision.""")
    for plo, phi, pname in [(0.25, 0.75, "peak +25% to +75%"),
                            (0.75, 1.50, "peak +75% to +150%"),
                            (1.50, 999, "peak > +150%")]:
        band = [e for e in green if plo <= e["peak"] < phi]
        if len(band) < 20:
            print(f"\n  [{pname}]  n={len(band)} — too thin, skipped")
            continue
        print(f"\n  [{pname}]  n={len(band)}  "
              f"(peak level now held roughly constant within the band)")
        for lo, hi, name in UND_MOVE_BUCKETS:
            rows = [e for e in band if lo <= e["und_at_peak"] < hi]
            if rows:
                print(gb_line("    " + name, rows))

    sub("READ")
    print("""  If the gradient SURVIVES inside a peak band, the signal is the underlying,
  not the moneyness, and it is observable in flight: 'I am up X% but the stock
  has barely moved' is a different position from 'I am up X% because the stock
  fell 8%'. If it FLATTENS inside the bands, the headline cut was just measuring
  depth-in-the-money and there is nothing here to act on.""")


# =============================================================================
# ARM S — deployment reference stats
# =============================================================================

def arm_s(recs: list[dict]) -> None:
    hdr("ARM S — deployment reference: win rate, PF, MFE/MAE by regime x structure")
    print("""  DESCRIPTIVE in-sample summaries of the book, for the operator card. These
  are NOT predictions and NOT a selection rule — cells with small n move a lot.
  Population: real+tweak only (bs excluded — attenuating, per 08-11).

  Columns:
    win    share of rows with realized R > 0
    PF     profit factor = gross winning $ / |gross losing $| on realized R
    meanR  mean realized return as a fraction of premium at risk
    $      summed realized dollars (position-size weighted, unlike meanR)
    MFE    mean best unrealized point on the path (fraction of premium)
    MAE    mean worst unrealized point on the path
    gb     give-back = |MAE| / MFE. >1 = the average row was under water deeper
           than it was ever green.
    cap    capture = meanR / MFE. How much of the shown profit the exit banked.
           low cap + high MFE = EXIT problem; low MFE = SELECTION problem.""")

    sub("WHOLE BOOK and the debit/credit split")
    _all = cell_stats(recs)
    if _all["n_path"] != _all["n"]:
        print(f"  NOTE: MFE/MAE present on {_all['n_path']}/{_all['n']} rows; the path "
              f"columns are means over those only.")
    print(fmt_row("all rows", _all))
    print(fmt_row("debit", cell_stats([r for r in recs if not r["credit"]])))
    print(fmt_row("credit", cell_stats([r for r in recs if r["credit"]])))

    sub("by STRUCTURE (all regimes)")
    for s in sorted({r["structure"] for r in recs}):
        print(fmt_row(s, cell_stats([r for r in recs if r["structure"] == s])))

    sub("by LADDER TIER")
    for tier in ("A", "B", "C", "VETO"):
        print(fmt_row(f"tier {tier}", cell_stats([r for r in recs if r["tier"] == tier])))

    sub("by MECH CELL x STRUCTURE  (mech = SPY/VIX truth, the exit-conditioning label)")
    cells = ["LVOL", "BEAR_HE", "RB_EVOL", "NONE", "PROD"]
    structs = ["bull_call_spread", "bull_put_spread", "bear_put_spread", "bear_call_spread"]
    for cell in cells:
        sub_rows = [r for r in recs if r["mech_cell"] == cell]
        if not sub_rows:
            continue
        print(f"\n  [{cell}]  n={len(sub_rows)}")
        for s in structs:
            rows = [r for r in sub_rows if r["structure"] == s]
            if rows:
                print(fmt_row("    " + s, cell_stats(rows), width=30))

    sub("by MODEL REGIME x STRUCTURE  (model label = the SELECTION-relevant one)")
    for dirn in ("BULL", "BEAR", "RANGE"):
        sub_rows = [r for r in recs if r["model_dir"] == dirn]
        if not sub_rows:
            continue
        print(f"\n  [model {dirn}]  n={len(sub_rows)}")
        for s in structs:
            rows = [r for r in sub_rows if r["structure"] == s]
            if rows:
                print(fmt_row("    " + s, cell_stats(rows), width=30))

    sub("the §3 geometry gate: bull_put_spread in-band vs out")
    bp = [r for r in recs if r["structure"] == "bull_put_spread"]
    def in_band(r):
        d, dte = r["delta"], r["dte"]
        return d is not None and dte is not None and 0.08 <= abs(d) <= 0.20 and dte <= 59
    print(fmt_row("in band (|d| .08-.20, DTE<=59)", cell_stats([r for r in bp if in_band(r)]),
                  width=30))
    print(fmt_row("out of band", cell_stats([r for r in bp if not in_band(r)]), width=30))
    print(fmt_row("  of in-band: DTE 45-59",
                  cell_stats([r for r in bp if in_band(r) and r["dte"] >= 45]), width=30))

    sub("by MODEL REGIME x VOL, all structures pooled  (the §1 veto cells live here)")
    for dirn in ("BULL", "BEAR", "RANGE"):
        for vol in ("E-VOL", "H-VOL", "L-VOL", "C-VOL"):
            rows = [r for r in recs if r["model_dir"] == dirn and r["model_vol"] == vol]
            if rows:
                print(fmt_row(f"{dirn} + {vol}", cell_stats(rows)))

    sub("the deploy-time cell: bull_call_spread by model regime x vol")
    for dirn in ("RANGE", "BULL", "BEAR"):
        for vol in ("E-VOL", "H-VOL", "L-VOL", "C-VOL"):
            rows = [r for r in recs if r["structure"] == "bull_call_spread"
                    and r["model_dir"] == dirn and r["model_vol"] == vol]
            if len(rows) >= 8:
                print(fmt_row(f"{dirn} + {vol}", cell_stats(rows)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", default="PUS", help="subset of P/U/S to run")
    a = ap.parse_args(argv)

    recs, diag = load_book(include_bs=False)
    print(f"book: {len(recs)} rows  counts_by_source={diag['counts_by_source']}  "
          f"(bs excluded)")
    bear = [r for r in recs if r["structure"] in BEAR_DEBIT and not r["credit"]]
    nonbear_debit = [r for r in recs if r["structure"] not in BEAR_DEBIT and not r["credit"]]
    credits = [r for r in recs if r["credit"]]
    print(f"bear debit {len(bear)}  non-bear debit {len(nonbear_debit)}  credit {len(credits)}")

    if "P" in a.arms:
        arm_p(bear, nonbear_debit, credits)
    if "U" in a.arms:
        arm_u(bear)
    if "S" in a.arms:
        arm_s(recs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
