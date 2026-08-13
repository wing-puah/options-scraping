"""Underlying-volume signal study: does share volume condition exits, or anything?

PRE-REGISTERED 2026-08-13 in config/backtest-tuning/current.md BEFORE this file
was written. Read that entry first; nothing here may drift from it. In brief:

  H1 (PRIMARY, path/exit)  HIGH unusual-O/S rows give back more. Mechanism test
       is a frozen variant set of exactly ONE: `be_after: 0.50` applied to
       NON-bear debit rows in the HIGH os_ratio tercile, graded against SHIPPED
       production (bear_giveback.prod_profile_for merge), leave-one-date-out.
  H2 (rvolz20)   exploratory descriptive cut only — no adoption path this run.
  H3 (amihud20)  control: an H1 separation that collapses within amihud
       terciles is LIQUIDITY-PROXY, not flow information.
  Selection      SECONDARY, within structure from the first look, and only a
       walk-forward TEST-row read may ever call something a candidate.

Gates: G1 calibration stop, G2 coverage-before-numbers, G3 MIN_CELL_N=20,
G4 no annualised figures, G5 in-sample tables labelled. Verdict grammar
(VOLUME-CONDITIONS-EXITS / LIQUIDITY-PROXY / PATH-VOL-PROXY / NULL) is worded
in the pre-registration; the operationalizations below were coded before the
study first ran and are not knobs. Nothing ships from this study under any
outcome.
"""
from __future__ import annotations

import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study import protocol as P  # noqa: E402
from scripts.backtest_study import volume_features as VF  # noqa: E402
from scripts.backtest_study.bear_giveback import (  # noqa: E402
    BEAR_DEBIT, prod_profile_for,
)
from scripts.backtest_study.book import DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.harness import replay  # noqa: E402
from scripts.backtest_study.underlying import load_bars  # noqa: E402

MIN_CELL_N = 20

# Sub-arming give-back (the §2.4 census definition): peaked at or above +1%,
# never reached the 0.50 arming threshold, finished at or below zero.
GIVEBACK_LO, GIVEBACK_HI = 0.01, 0.50

# Per-row exit capture R/MFE is quoted only when the row actually had something
# to capture; below this peak the ratio is noise around 0/0.
CAPTURE_MIN_MFE = 0.05

TERCILE_ORDER = ("LOW", "MID", "HIGH")


def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


# ── population predicates ────────────────────────────────────────────────────

def is_bear_debit(rec: dict) -> bool:
    return rec["structure"] in BEAR_DEBIT and not rec["credit"]


def is_nonbear_debit(rec: dict) -> bool:
    return not rec["credit"] and rec["structure"] not in BEAR_DEBIT


def giveback(rec: dict) -> bool | None:
    """True when the row is a sub-arming give-back; None when MFE/R missing."""
    if rec.get("mfe") is None or rec.get("R") is None:
        return None
    return GIVEBACK_LO <= rec["mfe"] < GIVEBACK_HI and rec["R"] <= 0


# ── enrichment ───────────────────────────────────────────────────────────────

def enrich(recs: list[dict]) -> None:
    """Attach the three volume features (and coverage fields) to every record."""
    contracts = VF.load_contracts()
    for r in recs:
        bars = load_bars(r["ticker"])
        c = contracts.get((str(r["date"]), r["ticker"].upper().strip()))
        r.update(VF.features(bars, r["t"].signal_date, r["ticker"], c))


# ── G1: calibration stop ─────────────────────────────────────────────────────

def gate_calibration(recs: list[dict], diag: dict) -> list[dict]:
    """Quote the book gate, re-verify replay identity, return the exit-arm pop."""
    hdr("G1 — CALIBRATION (stop condition)")
    dc = diag["debit_calib"]
    print(f"  book debit calibration: {dc}   credit rows ungated: "
          f"{diag['n_credit_ungated']}")
    pop = [r for r in recs if not r["credit"] and r["calibrated"]]
    hard = []
    for r in pop:
        t = r["t"]
        rp = replay(t, **DEBIT_PROD)
        want = (t.row["exit_reason"], int(float(t.row["days_held"])),
                round(float(t.row["realized_pnl_pct"]), 4))
        got = (rp["exit_reason"], rp["days_held"], round(rp["pnl_pct"], 4))
        if want != got:
            hard.append((r, want, got))
    print(f"  replay identity re-check on the exit-arm population: "
          f"{len(pop) - len(hard)}/{len(pop)} exact")
    if hard:
        print("\n  *** G1 FAILED — calibrated rows do not reproduce DEBIT_PROD. ***")
        for r, want, got in hard[:10]:
            print(f"    {r['date']} {r['ticker']} {r['structure']} "
                  f"want={want} got={got}")
        sys.exit(1)
    print("  -> PASS")
    return pop


# ── G2: coverage before numbers ──────────────────────────────────────────────

def gate_coverage(recs: list[dict]) -> None:
    hdr("G2 — COVERAGE (the denominator every number below is quoted against)")
    cov = VF.coverage(recs)
    print(f"  book rows                      {cov['n_rows']:>5}")
    print(f"  O/S join hit (rollup match)    {cov['contracts_join']:>5}")
    print(f"  rescaled basis (window feats   {cov['rescaled_withheld']:>5}"
          "   rvolz20/amihud20 withheld)")
    for key in VF.VOLUME_KEYS:
        c = cov[key]
        print(f"  {key:<12} usable            {c['n']:>5}   ({c['pct']:.0%})")
    src = Counter(r["source"] for r in recs)
    print(f"  pricing tiers: {dict(src)}")
    print("\n  os_ratio needs BOTH a rollup row and an OHLC-cache bar on the exact")
    print("  signal date; window features need >=15 clean sessions of volume.")


# ── descriptive tercile tables (in-sample, G5-labelled) ──────────────────────

def cell_stats(rows: list[dict]) -> dict:
    rs = [r["R"] for r in rows if r.get("R") is not None]
    mfes = [r["mfe"] for r in rows if r.get("mfe") is not None]
    maes = [r["mae"] for r in rows if r.get("mae") is not None]
    gbs = [giveback(r) for r in rows]
    gbs = [g for g in gbs if g is not None]
    caps = [r["R"] / r["mfe"] for r in rows
            if r.get("R") is not None and r.get("mfe") is not None
            and r["mfe"] >= CAPTURE_MIN_MFE]
    return dict(
        n=len(rows),
        mean=statistics.fmean(rs) if rs else None,
        win=(sum(1 for x in rs if x > 0) / len(rs)) if rs else None,
        dol=sum(r["R_dol"] for r in rows if r.get("R_dol") is not None),
        mfe=statistics.fmean(mfes) if mfes else None,
        mae=statistics.fmean(maes) if maes else None,
        gb=(sum(gbs) / len(gbs)) if gbs else None,
        cap=statistics.fmean(caps) if caps else None,
    )


def _fmt(v, spec, dash="     -"):
    return format(v, spec) if v is not None else dash


def tercile_table(rows: list[dict], feature: str, bounds, label: str) -> dict:
    """Print the tercile cut; return {tercile: stats} for the verdict logic."""
    sub(f"{feature} terciles — {label}  [IN-SAMPLE boundaries, G5]")
    if bounds is None:
        print("  (boundaries not computable)")
        return {}
    print(f"  boundaries: LOW < {bounds[0]:.4g} <= MID < {bounds[1]:.4g} <= HIGH")
    print(f"  {'cell':<6} {'n':>5} {'meanR':>8} {'win':>6} {'$':>12} "
          f"{'MFE':>7} {'MAE':>7} {'gb%':>6} {'cap':>7}  CI95(meanR, date-clust)")
    out = {}
    for terc in TERCILE_ORDER:
        cell = [r for r in rows if VF.tercile_of(r.get(feature), bounds) == terc]
        s = cell_stats(cell)
        out[terc] = s
        if s["n"] < MIN_CELL_N:
            print(f"  {terc:<6} {s['n']:>5}   (< MIN_CELL_N={MIN_CELL_N} — printed, not read)")
            continue
        lo, hi = P.boot_ci_by_date(cell, key="R")
        print(f"  {terc:<6} {s['n']:>5} {_fmt(s['mean'], '+8.3f'):>8} "
              f"{_fmt(s['win'], '6.0%'):>6} {s['dol']:>12,.0f} "
              f"{_fmt(s['mfe'], '+7.2f'):>7} {_fmt(s['mae'], '+7.2f'):>7} "
              f"{_fmt(s['gb'], '6.0%'):>6} {_fmt(s['cap'], '+7.2f'):>7}  "
              f"[{lo:+.3f}, {hi:+.3f}]")
    return out


# ── H1(b): the frozen exit-variant arm ───────────────────────────────────────

def keyed_profile(rec: dict, bounds, keyed: bool) -> dict:
    """SHIPPED merge, plus the frozen variant when keyed and in the key.

    The key — non-bear debit AND os_ratio HIGH — is evaluated HERE, inside the
    profile builder, so the leak guard below is a real test (next_day_move
    pattern). On BEAR_HE dates the shipped merge nulls be_after for bear rows;
    for the non-bear rows this variant touches, the ratchet STACKS on the trail
    — disclosed, and the single frozen choice, not a grid.
    """
    cfg = prod_profile_for(rec, 0.50, True)
    if keyed and is_nonbear_debit(rec) and \
            VF.tercile_of(rec.get("os_ratio"), bounds) == "HIGH":
        cfg["be_after"] = 0.50
    return cfg


def arm_exit(pop: list[dict], bounds) -> dict:
    hdr("H1(b) — FROZEN EXIT VARIANT: be_after 0.50 on HIGH-os_ratio non-bear debit")
    print("""  Baseline is SHIPPED production (bear_giveback.prod_profile_for merge) on
  the calibrated debit book — grading against a baseline production does not
  run has changed a decision twice in this log. One variant, no grid.""")
    if bounds is None:
        print("  os_ratio boundaries not computable — arm NOT EVALUABLE.")
        return {}

    paired = []
    for r in pop:
        base = replay(r["t"], **keyed_profile(r, bounds, keyed=False))
        var = replay(r["t"], **keyed_profile(r, bounds, keyed=True))
        paired.append(dict(date=r["date"], source=r["source"], rec=r,
                           a=var["pnl_pct"], b=base["pnl_pct"],
                           a_dol=r["t"].dollars(var["pnl_pct"]),
                           b_dol=r["t"].dollars(base["pnl_pct"])))

    changed = [p for p in paired if abs(p["a"] - p["b"]) > 1e-9]
    in_key = [p for p in changed
              if is_nonbear_debit(p["rec"])
              and VF.tercile_of(p["rec"].get("os_ratio"), bounds) == "HIGH"]
    leak = len(changed) - len(in_key)
    print(f"\n  rows changed by the variant: {len(changed)} "
          f"(in key {len(in_key)}, outside key {leak})")
    print(f"  LEAK GUARD: {'OK' if leak == 0 else '*** LEAK ***'} "
          "(0 outside the key is the only acceptable number)")

    mean_a = statistics.fmean(p["a"] for p in paired)
    mean_b = statistics.fmean(p["b"] for p in paired)
    dol_a = sum(p["a_dol"] for p in paired)
    dol_b = sum(p["b_dol"] for p in paired)
    print(f"\n  SHIPPED baseline: meanR {mean_b:+.4f}   ${dol_b:>12,.0f}")
    print(f"  variant:          meanR {mean_a:+.4f}   ${dol_a:>12,.0f}   "
          f"Delta meanR {mean_a - mean_b:+.4f}   Delta$ {dol_a - dol_b:+,.0f}")

    if not changed:
        print("  (identical to shipped — nothing to test)")
        return dict(evaluable=False)

    ci_lo, ci_hi = P.boot_ci_paired_by_date(paired, "a", "b")
    loo_mean, loo_share, loo_min, loo_n = P.loo_by_date(
        paired, lambda p: p["a"], lambda p: p["b"])
    print(f"\n  paired CI95 (date-clustered): [{ci_lo:+.4f}, {ci_hi:+.4f}]")
    print(f"  LOO by date: mean {loo_mean:+.4f}  share>0 {loo_share:.0%}  "
          f"min {loo_min:+.4f}  folds {loo_n}")

    cuts_ok = True
    sub("window cuts (pre-registered both-window standard)")
    for name, rows in P.window_cuts(paired).items():
        if not rows:
            continue
        g = statistics.fmean(p["a"] - p["b"] for p in rows)
        cuts_ok = cuts_ok and g > 0
        print(f"    {name:<18} n={len(rows):>4}  gain {g:+.4f}")
    sub("years / pricing tiers")
    for y, rows in P.by_year(paired).items():
        print(f"    {y}  n={len(rows):>4}  gain "
              f"{statistics.fmean(p['a'] - p['b'] for p in rows):+.4f}")
    for tier in ("real", "tweak"):
        rows = [p for p in paired if p["source"] == tier]
        if rows:
            print(f"    tier {tier:<5}  n={len(rows):>4}  gain "
                  f"{statistics.fmean(p['a'] - p['b'] for p in rows):+.4f}")

    return dict(evaluable=True, leak=leak, ci_lo=ci_lo, ci_hi=ci_hi,
                loo_min=loo_min, loo_share=loo_share, cuts_ok=cuts_ok,
                delta_mean=mean_a - mean_b, delta_dol=dol_a - dol_b,
                n_changed=len(changed))


# ── H3: the amihud control ───────────────────────────────────────────────────

def arm_control(nonbear: list[dict], os_bounds, am_bounds) -> dict:
    hdr("H3 — AMIHUD CONTROL: does the os_ratio separation survive within "
        "illiquidity terciles?")
    if os_bounds is None or am_bounds is None:
        print("  boundaries not computable — control NOT EVALUABLE.")
        return dict(evaluable=False)
    pooled = {t: [r for r in nonbear
                  if VF.tercile_of(r.get("os_ratio"), os_bounds) == t]
              for t in ("LOW", "HIGH")}
    if any(len(v) < MIN_CELL_N for v in pooled.values()):
        print("  pooled HIGH/LOW cells too thin — control NOT EVALUABLE.")
        return dict(evaluable=False)
    pooled_sep = (statistics.fmean(r["R"] for r in pooled["HIGH"] if r["R"] is not None)
                  - statistics.fmean(r["R"] for r in pooled["LOW"] if r["R"] is not None))
    print(f"  pooled HIGH-minus-LOW meanR (non-bear debit): {pooled_sep:+.4f}")
    print(f"\n  {'amihud cell':<12} {'n(LOW)':>7} {'n(HIGH)':>8} "
          f"{'meanR LOW':>10} {'meanR HIGH':>11} {'sep':>8}")
    kept = evaluable = 0
    for am_t in TERCILE_ORDER:
        cell = [r for r in nonbear
                if VF.tercile_of(r.get("amihud20"), am_bounds) == am_t]
        low = [r for r in cell if VF.tercile_of(r.get("os_ratio"), os_bounds) == "LOW"
               and r.get("R") is not None]
        high = [r for r in cell if VF.tercile_of(r.get("os_ratio"), os_bounds) == "HIGH"
                and r.get("R") is not None]
        if len(low) < MIN_CELL_N or len(high) < MIN_CELL_N:
            print(f"  {am_t:<12} {len(low):>7} {len(high):>8}   "
                  f"(< MIN_CELL_N — printed, not read)")
            continue
        evaluable += 1
        ml, mh = statistics.fmean(r["R"] for r in low), statistics.fmean(r["R"] for r in high)
        sep = mh - ml
        if sep * pooled_sep > 0:
            kept += 1
        print(f"  {am_t:<12} {len(low):>7} {len(high):>8} {ml:>+10.3f} "
              f"{mh:>+11.3f} {sep:>+8.3f}")
    collapse = evaluable >= 2 and kept < 2
    print(f"\n  evaluable cells {evaluable}, keeping the pooled sign {kept} "
          f"-> {'COLLAPSED (liquidity proxy)' if collapse else 'not collapsed'}")
    return dict(evaluable=evaluable >= 2, collapse=collapse, pooled_sep=pooled_sep)


# ── selection (SECONDARY): walk-forward ──────────────────────────────────────

def arm_selection_wf(recs: list[dict], feature: str) -> None:
    sub(f"walk-forward TEST rows — {feature} (boundaries fitted on TRAIN only)")
    rows = [r for r in recs if r.get(feature) is not None and r.get("R") is not None]
    agg: dict[tuple[str, str], list[float]] = {}
    n_folds = 0
    for train_d, test_d in P.walk_forward_splits([r["date"] for r in rows]):
        train = [r for r in rows if r["date"] in set(train_d)]
        bounds = VF.terciles(train, feature)
        if bounds is None:
            continue
        n_folds += 1
        for r in (r for r in rows if r["date"] in set(test_d)):
            terc = VF.tercile_of(r[feature], bounds)
            agg.setdefault((r["structure"], terc), []).append(r["R"])
    if not n_folds:
        print("    (no evaluable folds — book too thin for the embargo)")
        return
    print(f"    folds: {n_folds}   (aggregated TEST rows below; thin cells printed, not read)")
    structs = Counter(s for s, _ in agg)
    for s in sorted({k[0] for k in agg}):
        parts = []
        for terc in TERCILE_ORDER:
            vals = agg.get((s, terc), [])
            if not vals:
                parts.append(f"{terc} -")
            elif len(vals) < MIN_CELL_N:
                parts.append(f"{terc} n={len(vals)}(thin)")
            else:
                parts.append(f"{terc} {statistics.fmean(vals):+.3f} (n={len(vals)})")
        print(f"    {s:<22} " + "  ".join(parts))
    _ = structs


# ── verdict ──────────────────────────────────────────────────────────────────

def verdict(h1a: dict, exit_res: dict, control: dict) -> None:
    hdr("VERDICT (grammar pre-registered; operationalizations coded before first run)")
    hi, lo = h1a.get("HIGH", {}), h1a.get("LOW", {})
    readable = (hi.get("n", 0) >= MIN_CELL_N and lo.get("n", 0) >= MIN_CELL_N
                and hi.get("mean") is not None and lo.get("mean") is not None)
    r_sep = (hi["mean"] - lo["mean"]) if readable else None

    def _sep(key):
        if readable and hi.get(key) is not None and lo.get(key) is not None:
            return hi[key] - lo[key]
        return None

    mfe_sep, mae_sep = _sep("mfe"), _sep("mae")

    exit_ok = (exit_res.get("evaluable") and exit_res.get("leak") == 0
               and exit_res.get("ci_lo", 0) > 0 and exit_res.get("loo_min", 0) > 0
               and exit_res.get("cuts_ok"))
    collapsed = control.get("evaluable") and control.get("collapse")
    # LABELLED AMENDMENT (2026-08-13, after first run; disclosed in current.md):
    # the first-run operationalization compared SIGNED separations, so a cell
    # with higher peaks and SHALLOWER drawdowns read as "mirrored". The
    # registered wording is about path WIDTH moving together: MFE up with MAE
    # DEEPER (mae is negative, so widening is mfe_sep and -mae_sep same sign).
    # No number changes under this fix — only which verdict label fires.
    mirrored = (r_sep is not None and mfe_sep is not None and mae_sep is not None
                and mfe_sep * (-mae_sep) > 0
                and abs(mfe_sep) > abs(r_sep) and abs(mae_sep) > abs(r_sep))

    print(f"  components: H1a readable={readable} r_sep="
          f"{'-' if r_sep is None else f'{r_sep:+.4f}'}  "
          f"exit_ok={bool(exit_ok)}  amihud_collapse={bool(collapsed)}  "
          f"mfe/mae mirrored={bool(mirrored)}")
    if exit_ok and not collapsed:
        v = ("VOLUME-CONDITIONS-EXITS — candidate only; queue an "
             "independent-window confirmation. NOTHING SHIPS from this study.")
    elif collapsed:
        v = "LIQUIDITY-PROXY — the separation is amihud, not flow information."
    elif mirrored:
        v = "PATH-VOL-PROXY — MFE and MAE move together with no R separation."
    else:
        v = "NULL — the volume column is CLOSED; the live pipeline never pays the version bump."
    print(f"\n  VERDICT: {v}")


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    recs, diag = load_book(include_bs=False)
    print(f"book: {len(recs)} rows  counts_by_source={diag['counts_by_source']}  "
          f"date_range={diag['date_range']}  (bs excluded)")

    exit_pop = gate_calibration(recs, diag)
    enrich(recs)
    gate_coverage(recs)

    # frozen boundaries: full population, disclosed in-sample (G5)
    os_bounds = VF.terciles(recs, "os_ratio")
    rv_bounds = VF.terciles(recs, "rvolz20")
    am_bounds = VF.terciles(recs, "amihud20")

    bear = [r for r in recs if is_bear_debit(r)]
    nonbear = [r for r in recs if is_nonbear_debit(r)]
    credits = [r for r in recs if r["credit"]]

    hdr("H1(a) — os_ratio DESCRIPTIVE (in-sample, G5-labelled)")
    h1a = tercile_table(nonbear, "os_ratio", os_bounds, "NON-BEAR DEBIT (primary)")
    tercile_table(bear, "os_ratio", os_bounds, "BEAR DEBIT")
    tercile_table(credits, "os_ratio", os_bounds,
                  "CREDIT (flagged: ungated replay, descriptive only)")

    sub("bear sub-arming give-back census by os_ratio tercile (feeds §2.4)")
    if os_bounds is None:
        print("  (boundaries not computable)")
    else:
        for terc in TERCILE_ORDER:
            cell = [r for r in bear
                    if VF.tercile_of(r.get("os_ratio"), os_bounds) == terc]
            gb = [r for r in cell if giveback(r)]
            dol = sum(r["R_dol"] for r in gb if r.get("R_dol") is not None)
            print(f"  {terc:<6} bear rows {len(cell):>4}  give-backs {len(gb):>4}  "
                  f"${dol:>12,.0f}")

    exit_res = arm_exit(exit_pop, os_bounds)

    hdr("H2 — rvolz20 DESCRIPTIVE (exploratory; no adoption path this run)")
    tercile_table(nonbear, "rvolz20", rv_bounds, "NON-BEAR DEBIT")
    tercile_table(bear, "rvolz20", rv_bounds, "BEAR DEBIT")

    control = arm_control(nonbear, os_bounds, am_bounds)

    hdr("SELECTION (SECONDARY) — within structure from the first look")
    print("  A pooled cross-structure read may not carry a conclusion "
          "(closed-threads rule).")
    for feature in ("os_ratio", "rvolz20"):
        arm_selection_wf([r for r in recs if not r["credit"]], feature)

    verdict(h1a, exit_res, control)

    print("\nG4 note: no annualised return, Sharpe, or time-to-recover is printed "
          "anywhere above, by design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
