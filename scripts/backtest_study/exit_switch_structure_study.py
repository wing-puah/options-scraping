"""
STRUCTURE-keyed exit-switch study + composition test of the shipped BEAR_HE
override (2026-07-22, addendum 11 follow-up).

Two pre-registered questions, one setup:

Q1 — Does a structure-conditional trailing stop on bear_put_spread pass the
     SAME ship gate the mech-keyed switch passed? Addendum 11 measured
     bear_put's path shape as MFE-first in 77.3% of real-priced paths (peak
     day 17, trough day 41) against bull_call's 38.2% — run-then-bleed, the
     shape a trailing stop exists to harvest. Attempt 10 removed the debit
     trail on the POOLED debit book, dominated by bull_call's opposite shape,
     so this hypothesis was never actually tested.

Q2 — Is the SHIPPED mech BEAR_HE override (config/backtest.yml
     §simulation.regime_exit, addendum 7) a COMPOSITION PROXY for Q1? Both
     apply the identical variant (trail .50 / trig .50). If BEAR_HE rows are
     bear_put-heavy, the regime key may just be finding the structure effect
     through a noisier variable. Rule 7 (the trap that killed oi_confirm_pct
     and iv_pct) says test this before trusting the key.

     Decomposition: run the BEAR_HE override on NON-bear_put rows only, and
     the structure override on NON-BEAR_HE rows only. Whichever survives its
     own complement is the real key. If structure survives and regime does
     not, structure-keying is both simpler AND removes the runtime dependency
     on the SPY/VIX table.

Variant choice is NOT a new search. The primary structure variant is
V_TRAIL = trail .50 / trig .50 — the SAME frozen-grid config the mech switch
already uses for BEAR_HE, chosen so Q1 and Q2 differ only in the KEY, never
in the treatment. The remaining trail/BE entries of the frozen DEBIT_VARIANTS
grid are reported for bear_put as clearly-labelled EXPLORATORY only; they are
not eligible to ship off this run.

Data, calibration, dedup, post-13c join, LOO gate and perturbation logic are
IMPORTED from exit_switch_mech_study.py — same pooled debit book, same
harness validation, same gate thresholds. Nothing is reimplemented, so a
difference in the answer cannot come from a difference in the setup.

Run:
    source .venv/bin/activate
    python3 scripts/backtest_study/exit_switch_structure_study.py \
        | tee backtests/exit_switch_structure_study_output.txt

Read-only: touches no config/, scripts/, lib/, or existing backtests/*.py.
"""

import statistics
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.exit_mechanism_study import replay  # noqa: E402
from scripts.backtest_study.exit_switch_mech_study import (  # noqa: E402
    DEBIT_PROD, V_TRAIL, V_TEFNULL, V_PT110, SWITCH_CELLS, CELL_VARIANT,
    MechLabeler, compute_mech_table, ensure_spy_vix, build_post13c_lookup,
    load_debit_trades, harness_gate, cell_of, model_direction, model_vol,
    norm_play, POST13C_CUTOFF, hdr, sub,
)
import pandas as pd  # noqa: E402

# ── the structure under test ────────────────────────────────────────────────
TARGET_STRUCT = "bear_put_spread"
STRUCT_CELL = "BEARPUT"

# Named configs replayed once per trade. PROD + the three mech variants (so the
# mech comparator is exact) + the exploratory bear_put trail grid.
CONFIGS = {
    "PROD": DEBIT_PROD,
    "V_TRAIL": V_TRAIL,
    "V_TEFNULL": V_TEFNULL,
    "V_PT110": V_PT110,
    # EXPLORATORY (frozen grid, reported for bear_put only, not ship-eligible)
    "trail.25/.50": {**DEBIT_PROD, "trig": 0.50, "trail": 0.25},
    "trail.40/.50": {**DEBIT_PROD, "trig": 0.50, "trail": 0.40},
    "trail.25/.75": {**DEBIT_PROD, "trig": 0.75, "trail": 0.25},
    "trail.40/.75": {**DEBIT_PROD, "trig": 0.75, "trail": 0.40},
    "trail.50/.75": {**DEBIT_PROD, "trig": 0.75, "trail": 0.50},
    "BE@.50": {**DEBIT_PROD, "trig": None, "trail": None, "be_after": 0.50},
    "BE@.50+trail.50/.75": {**DEBIT_PROD, "trig": 0.75, "trail": 0.50, "be_after": 0.50},
}


# ════════════════════════════════════════════════════════════════════════════
# Enrichment — one replay per (trade, config), then everything is arithmetic
# ════════════════════════════════════════════════════════════════════════════

def enrich(trades, labeler, post13c_lu):
    recs = []
    for t in trades:
        d = t.signal_date.isoformat()
        mdir, mvol, mok, mapped = labeler.label(d)
        jk = f"{d}|{t.ticker}|{norm_play(t.row.get('play', ''))}"
        cdt = post13c_lu.get(jk)
        post13c = (cdt >= POST13C_CUTOFF) if pd.notna(cdt) else None

        pct = {name: replay(t, **cfg)["pnl_pct"] for name, cfg in CONFIGS.items()}
        dol = {name: t.dollars(v) for name, v in pct.items()}

        recs.append(dict(
            t=t, date=d, ticker=t.ticker, structure=t.structure, source=t.source,
            mech_ok=mok, mech_mapped=mapped,
            mech_cell=cell_of(mdir, mvol) if mok else "PROD",
            model_cell=cell_of(model_direction(t.row.get("market_regime", "")),
                               model_vol(t.row.get("market_regime", ""))),
            struct_cell=STRUCT_CELL if t.structure == TARGET_STRUCT else "PROD",
            post13c=post13c, pct=pct, dol=dol,
        ))
    return recs


# ── switch definitions: each returns the CONFIG NAME to use for a record ─────

def sw_prod(r):
    return "PROD"


def sw_mech(r):
    c = r["mech_cell"]
    return {"BEAR_HE": "V_TRAIL", "LVOL": "V_TEFNULL", "RB_EVOL": "V_PT110"}.get(c, "PROD")


def sw_struct(r, variant="V_TRAIL"):
    return variant if r["struct_cell"] == STRUCT_CELL else "PROD"


def sw_both(r):
    """Structure wins where the two overlap (pre-registered precedence)."""
    if r["struct_cell"] == STRUCT_CELL:
        return "V_TRAIL"
    return sw_mech(r)


def sw_bearhe(r):
    """The SHIPPED clause in isolation: BEAR_HE cell only, LVOL/RB_EVOL off."""
    return "V_TRAIL" if r["mech_cell"] == "BEAR_HE" else "PROD"


def sw_mech_minus_target(r):
    """BEAR_HE override applied ONLY to non-bear_put rows (Q2 decomposition).

    Deliberately the BEAR_HE clause alone — folding in LVOL/RB_EVOL here would
    credit the complement with gains from cells that are not under test.
    """
    if r["structure"] == TARGET_STRUCT:
        return "PROD"
    return sw_bearhe(r)


def sw_struct_minus_bearhe(r):
    """bear_put trail applied ONLY outside the BEAR_HE cell (Q2 decomposition)."""
    if r["struct_cell"] == STRUCT_CELL and r["mech_cell"] != "BEAR_HE":
        return "V_TRAIL"
    return "PROD"


def tot(recs, swfn, unit="pct"):
    return sum(r[unit][swfn(r)] for r in recs)


def gain(recs, swfn, unit="pct"):
    return tot(recs, swfn, unit) - tot(recs, sw_prod, unit)


# ── LOO: out-of-fold cell-by-cell config selection, same shape as the mech study ──

def loo_by_date(recs, cellkey, variant_of, unit="pct"):
    """For each held-out date, each switch cell picks PROD vs its designated
    variant by the better TRAINING mean pnl_pct on the remaining dates; apply
    to the held-out date; accumulate switch-minus-PROD."""
    dates = sorted({r["date"] for r in recs})
    by_date = {}
    for r in recs:
        by_date.setdefault(r["date"], []).append(r)
    cells = [c for c in variant_of if c != "PROD"]

    fold_gains = {}
    for held in dates:
        train = [r for r in recs if r["date"] != held]
        choose = {}
        for cell in cells:
            crows = [r for r in train if r[cellkey] == cell]
            if not crows:
                choose[cell] = False
                continue
            mp = sum(r["pct"]["PROD"] for r in crows) / len(crows)
            mv = sum(r["pct"][variant_of[cell]] for r in crows) / len(crows)
            choose[cell] = mv > mp
        g = 0.0
        for r in by_date[held]:
            cell = r[cellkey]
            prod = r[unit]["PROD"]
            use = r[unit][variant_of[cell]] if (cell in cells and choose[cell]) else prod
            g += use - prod
        fold_gains[held] = g
    return fold_gains


def summarize_folds(fg, label):
    vals = list(fg.values())
    n = len(vals)
    med = statistics.median(vals)
    total = sum(vals)
    nonneg = sum(1 for v in vals if v >= 0) / n
    pos = sum(1 for v in vals if v > 0) / n
    print(f"    {label:34s}  dates={n:4d}  median={med:+9.4f}  total={total:+11.4f}  "
          f">0={pos:6.2%}  >=0={nonneg:6.2%}")
    return dict(n=n, median=med, total=total, pos=pos, nonneg=nonneg)


MECH_VARIANT_OF = {"BEAR_HE": "V_TRAIL", "LVOL": "V_TEFNULL", "RB_EVOL": "V_PT110"}
STRUCT_VARIANT_OF = {STRUCT_CELL: "V_TRAIL"}


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def main():
    ensure_spy_vix()
    labeler = MechLabeler(compute_mech_table())
    post13c_lu = build_post13c_lookup()

    hdr("STEP 1 — BOOK, CALIBRATION, COMPOSITION")
    trades, diag = load_debit_trades()
    px = diag["proxy"]
    # Same gate as the mech study — literally the same function, so the
    # 2026-08-14 exact-replay correction can never drift between the two.
    rc = harness_gate(diag, study="structure switch")
    print(f"Debit priced book: real={rc['n']} tweak={px['n_tweak']} bs={px['n_bs']} "
          f"-> pooled = {rc['n'] + px['n_tweak'] + px['n_bs']}")

    recs = enrich(trades, labeler, post13c_lu)
    post = [r for r in recs if r["post13c"] is True]
    tgt = [r for r in recs if r["structure"] == TARGET_STRUCT]
    print(f"\nStructure mix (debit): "
          + "  ".join(f"{k}={v}" for k, v in Counter(r["structure"] for r in recs).most_common()))
    print(f"{TARGET_STRUCT}: n={len(tgt)}  post-13c n={sum(1 for r in tgt if r['post13c'] is True)}")

    # ── Q2 composition: is BEAR_HE bear_put-heavy? ──
    sub("Q2 COMPOSITION — structure mix inside each mech cell")
    base = len(tgt) / len(recs)
    print(f"    book-wide {TARGET_STRUCT} share: {base:.2%}\n")
    print(f"    {'mech_cell':12s}  {'n':>4s}  {'n_target':>8s}  {'target_share':>12s}  {'lift_vs_book':>12s}")
    for cell in ("BEAR_HE", "LVOL", "RB_EVOL", "PROD"):
        rows = [r for r in recs if r["mech_cell"] == cell]
        if not rows:
            continue
        nt = sum(1 for r in rows if r["structure"] == TARGET_STRUCT)
        sh = nt / len(rows)
        print(f"    {cell:12s}  {len(rows):4d}  {nt:8d}  {sh:12.2%}  {sh - base:+12.2%}")
    n_overlap = sum(1 for r in recs if r["struct_cell"] == STRUCT_CELL and r["mech_cell"] == "BEAR_HE")
    print(f"\n    overlap (bear_put AND BEAR_HE): {n_overlap} rows "
          f"= {n_overlap/max(len(tgt),1):.1%} of bear_puts")

    # ── Q1: fixed structure switch, all frozen-grid variants ──
    hdr("STEP 2 — Q1: bear_put EXIT VARIANTS (fixed switch, applied to bear_put only)")
    print("PRIMARY = V_TRAIL (trail .50 / trig .50), the same treatment BEAR_HE uses.")
    print("Everything below it is EXPLORATORY grid context, not ship-eligible.\n")
    print(f"    {'variant':22s}  {'Δpnl_pct':>10s}  {'Δ$':>10s}  {'mean_var':>9s}  "
          f"{'mean_prod':>9s}  {'win_var':>8s}  {'win_prod':>8s}")
    n = len(tgt)
    mprod = sum(r["pct"]["PROD"] for r in tgt) / n
    wprod = sum(1 for r in tgt if r["pct"]["PROD"] > 0) / n
    order = ["V_TRAIL"] + [k for k in CONFIGS if k not in ("PROD", "V_TRAIL", "V_TEFNULL", "V_PT110")]
    for name in order:
        dp = sum(r["pct"][name] - r["pct"]["PROD"] for r in tgt)
        dd = sum(r["dol"][name] - r["dol"]["PROD"] for r in tgt)
        mv = sum(r["pct"][name] for r in tgt) / n
        wv = sum(1 for r in tgt if r["pct"][name] > 0) / n
        tag = "  <- PRIMARY" if name == "V_TRAIL" else ""
        print(f"    {name:22s}  {dp:10.4f}  {dd:10.0f}  {mv:9.4f}  {mprod:9.4f}  "
              f"{wv:8.2%}  {wprod:8.2%}{tag}")

    sub("Same, POST-13c bear_put rows only")
    tgt_p = [r for r in tgt if r["post13c"] is True]
    if tgt_p:
        npp = len(tgt_p)
        for name in order:
            dp = sum(r["pct"][name] - r["pct"]["PROD"] for r in tgt_p)
            dd = sum(r["dol"][name] - r["dol"]["PROD"] for r in tgt_p)
            print(f"    {name:22s}  n={npp:3d}  Δpnl_pct={dp:+8.4f}  Δ$={dd:+9.0f}")
    else:
        print("    (no post-13c bear_put rows)")

    # ── Book-level comparison of the four switches ──
    hdr("STEP 3 — BOOK-LEVEL: PROD vs mech-keyed vs structure-keyed vs both")
    for label, scope in [("POOLED", recs), ("POST-13c", post)]:
        sub(f"{label} — n={len(scope)}")
        print(f"    {'switch':22s}  {'Δpnl_pct':>10s}  {'Δ$':>10s}  {'n_rows_changed':>15s}")
        for nm, fn in [("mech (SHIPPED)", sw_mech), ("structure", sw_struct),
                       ("both (struct wins)", sw_both)]:
            changed = sum(1 for r in scope if fn(r) != "PROD")
            print(f"    {nm:22s}  {gain(scope, fn):10.4f}  {gain(scope, fn, 'dol'):10.0f}  "
                  f"{changed:15d}")

    # ── Q2 decomposition: each key on the OTHER's complement ──
    hdr("STEP 4 — Q2 DECOMPOSITION: does each key survive the other's complement?")
    print("If BEAR_HE only works because its rows are bear_puts, removing bear_puts from it")
    print("kills it. If bear_put only works inside BEAR_HE, removing BEAR_HE kills it.")
    print("A key that survives its complement is doing independent work.\n")
    for label, scope in [("POOLED", recs), ("POST-13c", post)]:
        sub(f"{label}")
        rows = [
            ("mech BEAR_HE, all rows", sw_bearhe),
            ("mech BEAR_HE, NON-bear_put only", sw_mech_minus_target),
            ("bear_put trail, all rows", sw_struct),
            ("bear_put trail, OUTSIDE BEAR_HE", sw_struct_minus_bearhe),
            ("overlap only (both true)",
             lambda r: "V_TRAIL" if (r["mech_cell"] == "BEAR_HE" and r["structure"] == TARGET_STRUCT) else "PROD"),
        ]
        print(f"    {'slice':36s}  {'n_changed':>9s}  {'Δpnl_pct':>10s}  {'Δ$':>10s}")
        for nm, fn in rows:
            ch = sum(1 for r in scope if fn(r) != "PROD")
            print(f"    {nm:36s}  {ch:9d}  {gain(scope, fn):10.4f}  {gain(scope, fn, 'dol'):10.0f}")

    # ── LOO gate, structure-keyed, vs the mech comparator ──
    hdr("STEP 5 — LEAVE-ONE-OUT BY SIGNAL DATE (out-of-fold selection)")
    res = {}
    for label, scope in [("POOLED", recs), ("POST-13c", post)]:
        sub(f"LOO — {label}")
        for kn, ck, vo in [("structure-keyed", "struct_cell", STRUCT_VARIANT_OF),
                           ("mech-keyed (comparator)", "mech_cell", MECH_VARIANT_OF)]:
            fgp = loo_by_date(scope, ck, vo, "pct")
            fgd = loo_by_date(scope, ck, vo, "dol")
            res[(label, kn)] = summarize_folds(fgp, f"{kn} [pnl_pct]")
            summarize_folds(fgd, f"{kn} [$]")

    # ── Time halves ──
    hdr("STEP 6 — TIME-SPLIT AT MEDIAN SIGNAL DATE (fixed switches)")
    ud = sorted({r["date"] for r in recs})
    med = ud[len(ud) // 2]
    print(f"median signal date (of {len(ud)} unique): {med}\n")
    print(f"    {'switch':22s}  {'EARLY Δpct':>11s}  {'EARLY Δ$':>10s}  "
          f"{'LATE Δpct':>10s}  {'LATE Δ$':>9s}")
    early = [r for r in recs if r["date"] < med]
    late = [r for r in recs if r["date"] >= med]
    halves = {}
    for nm, fn in [("mech (SHIPPED)", sw_mech), ("structure", sw_struct), ("both", sw_both)]:
        e, l = gain(early, fn), gain(late, fn)
        halves[nm] = (e, l)
        print(f"    {nm:22s}  {e:11.4f}  {gain(early, fn, 'dol'):10.0f}  "
              f"{l:10.4f}  {gain(late, fn, 'dol'):9.0f}")

    # ── Concentration: is the structure gain one correlated cluster? ──
    hdr("STEP 7 — CONCENTRATION OF THE STRUCTURE-SWITCH GAIN")
    print("Attempt 13's credit-stop removal was ~80% one July-2024 cluster. Same check here:")
    print("if a handful of dates or one ticker carry the gain, it is not a rule.\n")
    per_date = {}
    per_tkr = {}
    per_month = {}
    for r in tgt:
        g = r["dol"]["V_TRAIL"] - r["dol"]["PROD"]
        per_date[r["date"]] = per_date.get(r["date"], 0.0) + g
        per_tkr[r["ticker"]] = per_tkr.get(r["ticker"], 0.0) + g
        per_month[r["date"][:7]] = per_month.get(r["date"][:7], 0.0) + g
    total = sum(per_date.values())
    nd = len(per_date)
    top = sorted(per_date.items(), key=lambda kv: -abs(kv[1]))[:5]
    print(f"    bear_put dates with rows: {nd}   dates with gain>0: "
          f"{sum(1 for v in per_date.values() if v > 0)}   <0: "
          f"{sum(1 for v in per_date.values() if v < 0)}   total ${total:,.0f}")
    print(f"    top-5 dates by |Δ$|: " + "  ".join(f"{d}=${v:,.0f}" for d, v in top))
    print(f"    top-5 dates share of total: {sum(v for _, v in top)/total:.1%}")
    tt = sorted(per_tkr.items(), key=lambda kv: -abs(kv[1]))[:5]
    print(f"    top-5 tickers: " + "  ".join(f"{k}=${v:,.0f}" for k, v in tt))
    print(f"    top-5 tickers share of total: {sum(v for _, v in tt)/total:.1%}")
    print(f"\n    {'month':9s}  {'Δ$':>10s}")
    for m in sorted(per_month):
        print(f"    {m:9s}  {per_month[m]:10,.0f}")
    print(f"    months positive: {sum(1 for v in per_month.values() if v > 0)}/{len(per_month)}")

    # ── Ship gate (same six checks as the mech study) ──
    hdr("SHIP-GATE EVALUATION — STRUCTURE-KEYED bear_put TRAIL")
    pooled = res[("POOLED", "structure-keyed")]
    postl = res[("POST-13c", "structure-keyed")]
    e, l = halves["structure"]
    checks = {
        "LOO median > 0 (pooled)": pooled["median"] > 0,
        "LOO >=60% dates non-negative (pooled)": pooled["nonneg"] >= 0.60,
        "LOO total > 0 (pooled)": pooled["total"] > 0,
        "positive in BOTH time halves (fixed switch)": e > 0 and l > 0,
        "positive post-13c (LOO total > 0)": postl["total"] > 0,
        "survives the BEAR_HE complement (Δ>0 outside BEAR_HE)":
            gain(recs, sw_struct_minus_bearhe) > 0,
    }
    for k, v in checks.items():
        print(f"    [{'PASS' if v else 'FAIL'}]  {k}")
    print(f"\n    pooled  LOO: median={pooled['median']:+.4f} total={pooled['total']:+.4f} "
          f"nonneg={pooled['nonneg']:.2%}")
    print(f"    post13c LOO: median={postl['median']:+.4f} total={postl['total']:+.4f} "
          f"nonneg={postl['nonneg']:.2%}")
    print(f"    time halves: early Δ={e:+.4f}  late Δ={l:+.4f}")
    print(f"\n    VERDICT: structure-keyed bear_put trail "
          f"{'COMES OFF THE GATE' if all(checks.values()) else 'STAYS GATED'}.")

    bh = gain(recs, sw_bearhe)
    bh_c = gain(recs, sw_mech_minus_target)
    sg = gain(recs, sw_struct)
    sg_c = gain(recs, sw_struct_minus_bearhe)
    print(f"\n    Q2 READ (pooled, BEAR_HE clause as SHIPPED — LVOL/RB_EVOL excluded):")
    print(f"      shipped BEAR_HE clause  Δ={bh:+.4f}   on its complement (non-bear_put) Δ={bh_c:+.4f}"
          f"   retained {bh_c/bh:.0%}" if bh else "")
    print(f"      structure bear_put trail Δ={sg:+.4f}   on its complement (outside BEAR_HE) Δ={sg_c:+.4f}"
          f"   retained {sg_c/sg:.0%}" if sg else "")
    print("    (a key that keeps little of its gain on its own complement is a proxy for the other.)")

    print("\n" + "=" * 100 + "\nEND OF REPORT\n" + "=" * 100)


if __name__ == "__main__":
    main()
