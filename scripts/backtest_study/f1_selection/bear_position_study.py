"""
BEAR-POSITION STUDY (2026-07-22) — pre-registered in
research/current.md §addendum 13 BEFORE this file was run.

Why pre-registered: addenda 11-12 produced three verdicts on bear_put in one
session by post-hoc slicing the same 663-row book. The cut list, the window
control, and the decision rule below were all fixed in the log first. Nothing
here may be added to after seeing the output.

Outcome measures (both reported on every cut):
  E = pnl_at_cap_pct  — P&L at the last priced path day, computed independently
                        of the exit rule (simulate.py:267). SELECTION measure.
  R = pnl under DEBIT_PROD, RE-REPLAYED per row — SELECTION + EXIT.
  E<0 => selection problem (no exit rule rescues it).
  E>0 and R<0 => exit problem.

Book/calibration/dedup are IMPORTED from exit_switch_mech_study.py, so this is
the same pooled debit book as addenda 4 and 12.

--- R basis: CORRECTED 2026-08-14 -------------------------------------------
R was previously the STORED `realized_pnl_pct` column, and this docstring
described it as "under PROD". That was true when written and became false on
2026-07-22, when 31cb935 shipped the `regime_exit.cells.BEAR_HE` trail: 12 real
debit rows now carry a stored outcome produced by a rule DEBIT_PROD does not
contain, and 9 of the 12 are bear_put_spread/long_put — squarely this study's
population, and it feeds docs/deployment-rules.md §"Bear positions — hedge
sleeve". R is now re-replayed per row under DEBIT_PROD (see `build`), which
makes the label true for every row and matches what the exit-switch studies
already do. E is untouched (pnl_at_cap_pct is exit-rule-independent by
construction). Numbers in the ORIGINAL 2026-07-22 run were computed on the old
basis. All 12 affected rows carry created_datetime >= 2026-07-22 23:39, i.e. at
or after the trail's ship commit, so they were almost certainly absent from that
run's export — but treat any R figure this study prints NOW as superseding the
recorded one rather than assuming the two are comparable.

Run:
    source .venv/bin/activate
    python3 scripts/backtest_study/f1_selection/bear_position_study.py | tee backtests/bear_position_study_output.txt
"""

import random
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f2_management.exit_mechanism_study import _to_float, replay  # noqa: E402
from scripts.backtest_study.f2_management.exit_switch_mech_study import (  # noqa: E402
    DEBIT_PROD, MechLabeler, compute_mech_table, ensure_spy_vix,
    load_debit_trades, harness_gate, cell_of, model_direction, model_vol,
    hdr, sub,
)

TARGET = "bear_put_spread"
COMP = "bull_call_spread"
WINDOW = ("2025-03", "2025-04")     # declared in the pre-registration
BOOT_N = 10000
random.seed(20260722)


def in_window(d):
    return d[:7] in WINDOW


# ── ladder (docs/deployment-rules.md) ─────────────────────────────────────

def ladder_tier(r):
    """VETO / A / B / C per docs/deployment-rules.md, from the MODEL regime."""
    st, mr = r["structure"], r["market_regime"] or ""
    mdir, mvol = model_direction(mr), model_vol(mr)
    if st == "bear_call_spread":
        return "VETO"
    if mdir == "BEAR" and mvol == "H-VOL":
        return "VETO"
    if st == COMP:
        return "A" if (mdir == "RANGE" or mvol == "E-VOL") else "B"
    if st == "bull_put_spread":
        d, dte = r["delta"], r["dte"]
        if d is not None and dte is not None and 0.08 <= abs(d) <= 0.20 and dte <= 59:
            return "B"
    return "C"


def build(trades, labeler):
    recs = []
    for t in trades:
        row = t.row
        d = t.signal_date.isoformat()
        mdir, mvol, mok, _ = labeler.label(d)
        e = _to_float(row.get("pnl_at_cap_pct"))
        # R is RE-REPLAYED under DEBIT_PROD, never read off the row.
        # CORRECTED 2026-08-14: this used to be `_to_float(row["realized_pnl_pct"])`,
        # which silently imported a DIFFERENT exit config for the 12 real rows
        # whose stored outcome came from the shipped `regime_exit.BEAR_HE` trail
        # (2026-07-22, 31cb935) — and 9 of those 12 are bear_put_spread/long_put,
        # squarely this study's population, feeding deployment-rules.md
        # §"Bear positions — hedge sleeve". The docstring's "R = realized_pnl_pct
        # under PROD" was false for exactly those rows: the stored column is not
        # under PROD when a regime override governed the row. Re-replaying makes
        # the label true for every row and matches what the two exit-switch
        # studies already do for everything they report.
        r_ = replay(t, **DEBIT_PROD)["pnl_pct"]
        if e is None or r_ is None:
            continue
        rec = dict(
            date=d, month=d[:7], ticker=t.ticker, structure=t.structure,
            tier_price=t.source, E=e, R=r_,
            E_dol=t.dollars(e), R_dol=t.dollars(r_),
            delta=_to_float(row.get("delta")), dte=_to_float(row.get("dte_entry")),
            iv_entry=_to_float(row.get("iv_entry_pct")),
            iv_spread=_to_float(row.get("iv_spread")),
            mfe=_to_float(row.get("mfe_pct")), mae=_to_float(row.get("mae_pct")),
            mfe_day=_to_float(row.get("mfe_day")), mae_day=_to_float(row.get("mae_day")),
            market_regime=row.get("market_regime", ""),
            mech_cell=cell_of(mdir, mvol) if mok else "PROD",
            inW=in_window(d),
        )
        rec["tier"] = ladder_tier(rec)
        recs.append(rec)
    return recs


def stat(rows, key="E"):
    if not rows:
        return None
    v = [r[key] for r in rows]
    dol = sum(r[key + "_dol"] for r in rows)
    return dict(n=len(v), mean=statistics.mean(v), med=statistics.median(v),
                win=sum(1 for x in v if x > 0) / len(v), dol=dol)


def line(label, s, width=30):
    if s is None:
        print(f"    {label:{width}s}      (none)")
        return
    print(f"    {label:{width}s}  n={s['n']:4d}  mean={s['mean']:+7.3f}  "
          f"med={s['med']:+7.3f}  win={s['win']:6.1%}  ${s['dol']:>10,.0f}")


def boot_ci(rows, key="E", n=BOOT_N):
    """Date-clustered bootstrap 95% CI of the mean (resample signal dates)."""
    if not rows:
        return (float("nan"), float("nan"))
    by = {}
    for r in rows:
        by.setdefault(r["date"], []).append(r[key])
    dates = list(by)
    means = []
    for _ in range(n):
        pool = []
        for _ in range(len(dates)):
            pool.extend(by[random.choice(dates)])
        means.append(statistics.mean(pool))
    means.sort()
    return (means[int(0.025 * n)], means[int(0.975 * n)])


def main():
    ensure_spy_vix()
    labeler = MechLabeler(compute_mech_table())
    trades, diag = load_debit_trades()
    hdr("BOOK")
    # Same gate as both exit-switch studies — one shared implementation.
    harness_gate(diag, study="bear position")
    recs = build(trades, labeler)
    print(f"Rows with both E and R: {len(recs)}")
    print("Structures: " + "  ".join(f"{k}={v}" for k, v in
                                     Counter(r["structure"] for r in recs).most_common()))
    print(f"Window W = {WINDOW[0]} + {WINDOW[1]}:  in={sum(1 for r in recs if r['inW'])}  "
          f"out={sum(1 for r in recs if not r['inW'])}")
    bp = [r for r in recs if r["structure"] == TARGET]
    bc = [r for r in recs if r["structure"] == COMP]

    # ── C1 ──
    hdr("C1 — LEVELS by structure × window, on E (exit-free) and R (realized)")
    for key, nm in (("E", "E = hold-to-cap, EXIT-FREE"), ("R", "R = realized under PROD")):
        sub(nm)
        for st, rows in ((TARGET, bp), (COMP, bc)):
            for wl, sel in (("ALL", rows),
                            ("IN-W  (Mar+Apr25)", [r for r in rows if r["inW"]]),
                            ("EX-W", [r for r in rows if not r["inW"]])):
                line(f"{st:17s} {wl}", stat(sel, key), 40)
            print()
    sub("Pricing tier split — bear_put, EX-W, on E")
    for tp in ("real", "tweak", "bs"):
        line(f"tier={tp}", stat([r for r in bp if not r["inW"] and r["tier_price"] == tp], "E"))

    # ── C2 ──
    hdr("C2 — DATE-CLUSTERED BOOTSTRAP 95% CI (10k resamples of signal dates)")
    for st, rows in ((TARGET, bp), (COMP, bc)):
        for wl, sel in (("EX-W", [r for r in rows if not r["inW"]]), ("ALL", rows)):
            for key in ("E", "R"):
                lo, hi = boot_ci(sel, key)
                m = statistics.mean([r[key] for r in sel]) if sel else float("nan")
                excl = "CI excludes 0" if (lo < 0 and hi < 0) or (lo > 0 and hi > 0) else "CI spans 0"
                print(f"    {st:17s} {wl:5s} {key}  n={len(sel):4d}  mean={m:+7.3f}  "
                      f"95% CI [{lo:+.3f}, {hi:+.3f}]   {excl}")
        print()

    # ── C3 ──
    hdr("C3 — TIME HALVES + PER-MONTH SIGN, on E")
    ud = sorted({r["date"] for r in recs})
    med = ud[len(ud) // 2]
    print(f"median signal date (of {len(ud)}): {med}\n")
    for st, rows in ((TARGET, bp), (COMP, bc)):
        sub(st)
        for hl, sel in (("EARLY (all)", [r for r in rows if r["date"] < med]),
                        ("LATE  (all)", [r for r in rows if r["date"] >= med]),
                        ("EARLY EX-W", [r for r in rows if r["date"] < med and not r["inW"]]),
                        ("LATE  EX-W", [r for r in rows if r["date"] >= med and not r["inW"]])):
            line(hl, stat(sel, "E"))
        months = {}
        for r in rows:
            months.setdefault(r["month"], []).append(r["E"])
        pos = sum(1 for v in months.values() if statistics.mean(v) > 0)
        print(f"    months with mean E > 0: {pos}/{len(months)}")
        print("    " + "  ".join(f"{m}:{statistics.mean(v):+.2f}" for m, v in sorted(months.items())))

    # ── C4 ──
    hdr("C4 — MECH CELL × STRUCTURE, on E")
    for wl, sel_all in (("ALL", recs), ("EX-W", [r for r in recs if not r["inW"]])):
        sub(wl)
        for st in (TARGET, COMP):
            for cell in ("BEAR_HE", "LVOL", "RB_EVOL", "PROD"):
                line(f"{st:17s} {cell}",
                     stat([r for r in sel_all if r["structure"] == st and r["mech_cell"] == cell], "E"), 40)
            print()

    # ── C5 ──
    hdr("C5 — ENTRY GEOMETRY on bear_put, on E (EX-W decision-eligible; IN-W context only)")
    cuts = [
        ("|delta| <0.15", lambda r: r["delta"] is not None and abs(r["delta"]) < 0.15),
        ("|delta| 0.15-0.30", lambda r: r["delta"] is not None and 0.15 <= abs(r["delta"]) < 0.30),
        ("|delta| 0.30-0.45", lambda r: r["delta"] is not None and 0.30 <= abs(r["delta"]) < 0.45),
        ("|delta| >=0.45", lambda r: r["delta"] is not None and abs(r["delta"]) >= 0.45),
        ("DTE <=22", lambda r: r["dte"] is not None and r["dte"] <= 22),
        ("DTE 23-44", lambda r: r["dte"] is not None and 23 <= r["dte"] <= 44),
        ("DTE 45-59", lambda r: r["dte"] is not None and 45 <= r["dte"] <= 59),
        ("DTE >=60", lambda r: r["dte"] is not None and r["dte"] >= 60),
        ("iv_entry <30", lambda r: r["iv_entry"] is not None and r["iv_entry"] < 30),
        ("iv_entry 30-50", lambda r: r["iv_entry"] is not None and 30 <= r["iv_entry"] < 50),
        ("iv_entry >=50", lambda r: r["iv_entry"] is not None and r["iv_entry"] >= 50),
        ("iv_spread > 0", lambda r: r["iv_spread"] is not None and r["iv_spread"] > 0),
        ("iv_spread <= 0", lambda r: r["iv_spread"] is not None and r["iv_spread"] <= 0),
    ]
    for wl, sel in (("EX-W  [decision-eligible]", [r for r in bp if not r["inW"]]),
                    ("IN-W  [context only]", [r for r in bp if r["inW"]])):
        sub(wl)
        for nm, fn in cuts:
            line(nm, stat([r for r in sel if fn(r)], "E"))
    sub("EX-W cuts split by time half (the n>=30 + both-halves-positive test)")
    exw = [r for r in bp if not r["inW"]]
    for nm, fn in cuts:
        e_ = [r for r in exw if fn(r) and r["date"] < med]
        l_ = [r for r in exw if fn(r) and r["date"] >= med]
        se, sl = stat(e_, "E"), stat(l_, "E")
        n_tot = len(e_) + len(l_)
        ok = (n_tot >= 30 and se and sl and se["mean"] > 0 and sl["mean"] > 0)
        print(f"    {nm:22s}  n={n_tot:4d}  early={se['mean'] if se else float('nan'):+7.3f}"
              f"(n={len(e_):3d})  late={sl['mean'] if sl else float('nan'):+7.3f}(n={len(l_):3d})"
              f"   {'** QUALIFIES **' if ok else ''}")

    # ── C6 ──
    hdr("C6 — DEPLOYMENT LADDER: does it already screen the bear_put losers?")
    for wl, sel in (("ALL", bp), ("EX-W", [r for r in bp if not r["inW"]])):
        sub(f"bear_put by ladder tier — {wl}")
        for t in ("VETO", "A", "B", "C"):
            line(f"tier {t}", stat([r for r in sel if r["tier"] == t], "E"))
    sub("Whole book by tier (context), on E")
    for t in ("VETO", "A", "B", "C"):
        line(f"tier {t} ALL", stat([r for r in recs if r["tier"] == t], "E"))
        line(f"tier {t} EX-W", stat([r for r in recs if r["tier"] == t and not r["inW"]], "E"))

    # ── C7 ──
    hdr("C7 — PATH SHAPE and the MFE->E give-back")
    print(f"    {'slice':28s}  {'n':>4s}  {'mean MFE':>9s}  {'mean E':>8s}  "
          f"{'give-back':>10s}  {'MFE-first':>10s}  {'mfe_day':>8s}  {'mae_day':>8s}")
    for st, rows in ((TARGET, bp), (COMP, bc)):
        for wl, sel in (("ALL", rows), ("IN-W", [r for r in rows if r["inW"]]),
                        ("EX-W", [r for r in rows if not r["inW"]])):
            g = [r for r in sel if r["mfe"] is not None and r["mfe_day"] is not None
                 and r["mae_day"] is not None]
            if not g:
                continue
            mfe = statistics.mean(r["mfe"] for r in g)
            e = statistics.mean(r["E"] for r in g)
            first = sum(1 for r in g if r["mfe_day"] < r["mae_day"]) / len(g)
            print(f"    {st[:12]:12s} {wl:6s}{'':10s}  {len(g):4d}  {mfe:9.3f}  {e:8.3f}  "
                  f"{mfe - e:10.3f}  {first:10.1%}  "
                  f"{statistics.mean(r['mfe_day'] for r in g):8.1f}  "
                  f"{statistics.mean(r['mae_day'] for r in g):8.1f}")

    # ── Decision rule ──
    hdr("DECISION (pre-registered rule, addendum 13)")
    exw_bp = [r for r in bp if not r["inW"]]
    mE = statistics.mean(r["E"] for r in exw_bp)
    lo, hi = boot_ci(exw_bp, "E")
    eh = [r for r in exw_bp if r["date"] < med]
    lh = [r for r in exw_bp if r["date"] >= med]
    mEe = statistics.mean(r["E"] for r in eh) if eh else float("nan")
    mEl = statistics.mean(r["E"] for r in lh) if lh else float("nan")
    c1, c2, c3 = mE < 0, hi < 0, (mEe < 0 and mEl < 0)
    print(f"    DEMOTE requires all three:")
    print(f"      [{'PASS' if c1 else 'FAIL'}]  ex-window mean E < 0            ({mE:+.3f})")
    print(f"      [{'PASS' if c2 else 'FAIL'}]  bootstrap 95% CI upper < 0      ([{lo:+.3f}, {hi:+.3f}])")
    print(f"      [{'PASS' if c3 else 'FAIL'}]  both time halves negative       "
          f"(early {mEe:+.3f}, late {mEl:+.3f})")
    qualifies = []
    for nm, fn in cuts:
        e_ = [r for r in exw_bp if fn(r) and r["date"] < med]
        l_ = [r for r in exw_bp if fn(r) and r["date"] >= med]
        if len(e_) + len(l_) >= 30 and e_ and l_ and \
           statistics.mean(r["E"] for r in e_) > 0 and statistics.mean(r["E"] for r in l_) > 0:
            qualifies.append(nm)
    print(f"\n    CONSTRAIN candidates (n>=30, both halves positive, EX-W): "
          f"{qualifies if qualifies else 'NONE'}")
    verdict = "DEMOTE TO VETO" if (c1 and c2 and c3) else (
        f"CONSTRAIN on {qualifies}" if qualifies else "NO ACTION")
    print(f"\n    VERDICT: {verdict}")
    print("\n" + "=" * 100 + "\nEND OF REPORT\n" + "=" * 100)


if __name__ == "__main__":
    main()
