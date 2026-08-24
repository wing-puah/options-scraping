"""DEPLOY arm — pre-registered 2026-08-11.

Registration: research/pre-registrations/f4_deployment/bear_deploy.md, where
`study_review` reads it. It was written as §addendum 2 of research/ml-plan.md,
which covered three studies and was split into per-study files (and deleted) on
2026-08-24; the D-rules are quoted there verbatim, and the original text is in
git.

The 2026-08-11 bear arm (`bear_arm.py`) answered "is bear selection fixable"
(no) and "is the bear exit mis-tuned" (yes, `be_after: 0.50`), then closed with
the caveat that the operator's chop hedge is "a portfolio decision the book
cannot price". This module tests that caveat instead of accepting it: 107 of
the 111 bear dates also carry non-bear rows, so the concurrent book exists.

Four estimands, each with its own pre-registered rule (see the registration):

  D1  joint selection x exit — B1 screened E under the PROD exit and B2 then
      changed the exit; the pair was never evaluated together.
  D2  hedge contribution — what the bear sleeve does on the deployed book's
      LOSING dates. The only test that can justify deploying a structure whose
      standalone expectancy is negative.
  D3  sizing — the largest sleeve fraction that does not worsen drawdown.
  D4  conditional pick — GIVEN a bear position is taken today, does any
      decision-time variable pick a better-than-average one? Within-date and
      paired, so the day is its own control and the level problem that sinks
      every B1 subset does not apply.

Nothing here changes config. Read the caveats at the end of the registration
before quoting any conclusion.

Run:
    source .venv/bin/activate
    python -m scripts.backtest_study.f4_deployment.bear_deploy | tee backtests/study_output/bear_deploy.txt
"""
from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.f1_selection.bear_arm import BEAR_STRUCTURES, clause_vocabulary  # noqa: E402
from scripts.backtest_study.lib.book import CREDIT_PROD, DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import replay  # noqa: E402

# The exit B2 recommended (bear_arm's B2, MET 2026-08-11). Bear-KEYED: it is only
# ever applied to bear debit rows here, never to the rest of the book.
BEAR_DEBIT_EXIT = {**DEBIT_PROD, "be_after": 0.50}

# D1 criteria — identical in shape to B1's, so the two are comparable.
MIN_N = 40
MIN_POSITIVE_YEARS = 2

# D3 sleeve fractions.
SIZE_FRACTIONS = (0.0, 0.25, 0.50, 1.0)

# D4 — decision-time rankers. Each returns a sort key (higher = expected better)
# or None when the row can't be ranked. Deliberately small and pre-declared:
# these are the columns the 07-21 sweep left standing plus the two the operator
# names, not a search over everything in the book.
def _abs_or_none(v):
    return abs(v) if v is not None else None


D4_RANKERS = {
    "|delta| low first": lambda r: -_abs_or_none(r.get("delta")) if r.get("delta") is not None else None,
    "|delta| high first": lambda r: _abs_or_none(r.get("delta")) if r.get("delta") is not None else None,
    "dte short first": lambda r: -r["dte"] if r.get("dte") is not None else None,
    "dte long first": lambda r: r["dte"] if r.get("dte") is not None else None,
    "iv_spread low first": lambda r: -r["iv_spread"] if r.get("iv_spread") is not None else None,
    "iv_spread high first": lambda r: r["iv_spread"] if r.get("iv_spread") is not None else None,
    "iv_pct low first": lambda r: -float(r["iv_pct"]) if r.get("iv_pct") is not None else None,
    "iv_pct high first": lambda r: float(r["iv_pct"]) if r.get("iv_pct") is not None else None,
    "score_total high first": lambda r: float(r["score_total"]) if r.get("score_total") is not None else None,
    "widest max_loss first": lambda r: r["max_loss_per_contract"] if r.get("max_loss_per_contract") is not None else None,
}


def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


def fmean(vals):
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else float("nan")


def cuts_pass(cuts) -> bool:
    """The pre-registered "both ex-window cuts >= 0", FAIL-CLOSED on an empty cut.

    An ex-window cut is EMPTY exactly when the subset lies entirely inside the
    dominant window — which is the case ground rule 4 exists to reject. `fmean`
    returns nan for that, and until 2026-08-24 this gate read
    `all(v >= 0 for v in cuts.values() if v == v)`: the nan was filtered OUT of
    the `all()`, so the window check passed vacuously on precisely the subsets
    it was written to kill. `bear_arm.py`'s B1 — the criterion D1 mirrors, on
    the same clause vocabulary — already fails closed, because its `stat()`
    returns None on no rows and the gate tests `c is not None`. The two
    encodings now agree; `tests/test_studies_bear_deploy.py` pins that.

    No recorded verdict changes: D1 has returned 0 survivors on every run.
    """
    return all(v == v and v >= 0 for v in cuts.values())


# ════════════════════════════════════════════════════════════════════════════
# Book preparation — bear rows re-priced under the recommended bear exit
# ════════════════════════════════════════════════════════════════════════════

def apply_bear_exit(bear_rows):
    """Add `Rb` / `Rb_dol` — realized return under the bear-keyed exit.

    Debit rows are replayed under BEAR_DEBIT_EXIT; credit bear rows (bear_call,
    already structure-vetoed at intake) keep CREDIT_PROD, since B2 found no
    credit-side change and there is nothing to apply one to.
    """
    for r in bear_rows:
        cfg = CREDIT_PROD if r.get("credit") else BEAR_DEBIT_EXIT
        rp = replay(r["t"], **cfg)
        r["Rb"] = rp["pnl_pct"]
        r["Rb_dol"] = r["t"].dollars(rp["pnl_pct"])
        r["Rb_exit"] = rp["exit_reason"]
    return bear_rows


# ════════════════════════════════════════════════════════════════════════════
# D1 — joint selection x exit
# ════════════════════════════════════════════════════════════════════════════

def d1_joint(bear_rows):
    hdr("D1 — selection screened on R under the bear-keyed exit (be_after 0.50)")
    print("  B1 screened mean E under the PROD exit and found 0 survivors in 496")
    print("  subsets. B2 then changed the exit. This re-runs the SAME vocabulary on")
    print("  what a deployed position actually returns.")

    pooled_e, pooled_r, pooled_rb = (fmean([r["E"] for r in bear_rows]),
                                     fmean([r["R"] for r in bear_rows]),
                                     fmean([r["Rb"] for r in bear_rows]))
    print(f"\n  pooled bear: E {pooled_e:+.3f}   R(PROD) {pooled_r:+.3f}   "
          f"R(bear exit) {pooled_rb:+.3f}   n={len(bear_rows)}")

    vocab = clause_vocabulary()
    results, tested = [], 0
    for size in (1, 2):
        for combo in combinations(vocab, size):
            preds = [c[1] for c in combo]
            rows = [r for r in bear_rows if all(p(r) for p in preds)]
            tested += 1
            if len(rows) < MIN_N:
                continue
            mean_rb = fmean([r["Rb"] for r in rows])
            lo, hi = P.boot_ci_by_date(rows, "Rb", n=4000)
            _, pos_years, means = P.sign_stable(rows, key="Rb")
            cuts = {n_: fmean([r["Rb"] for r in rs])
                    for n_, rs in P.window_cuts(rows).items() if n_ != "ALL"}
            cuts_ok = cuts_pass(cuts)
            passes = (mean_rb >= 0 and lo > 0 and pos_years >= MIN_POSITIVE_YEARS
                      and cuts_ok)
            results.append(dict(label=" AND ".join(c[0] for c in combo), n=len(rows),
                                mean=mean_rb, ci=(lo, hi), pos_years=pos_years,
                                years=means, cuts=cuts, cuts_ok=cuts_ok,
                                passes=passes, rows=rows))

    survivors = [v for v in results if v["passes"]]
    print(f"\n  combinations evaluated: {tested}  (with n>={MIN_N}: {len(results)})")
    print(f"  survivors of the pre-registered D1 rule: {len(survivors)}  "
          f"(~{0.05 * len(results):.1f} expected by chance)")
    if survivors:
        print("\n  SURVIVORS (ranked by mean R under the bear exit):")
        for v in sorted(survivors, key=lambda x: -x["mean"]):
            yrs = "  ".join(f"{y}:{m:+.3f}" for y, m in v["years"].items())
            dol = sum(r["Rb_dol"] for r in v["rows"] if r.get("Rb_dol") is not None)
            print(f"    {v['label']:46s} n={v['n']:4d} R={v['mean']:+.3f} "
                  f"CI[{v['ci'][0]:+.3f},{v['ci'][1]:+.3f}] ${dol:>9,.0f}")
            print(f"      years {yrs}   ex-window " +
                  "  ".join(f"{k.replace('ex_', '')}:{v_:+.3f}" for k, v_ in v["cuts"].items()))
    print("\n  Best 8 by mean R regardless of passing (context only):")
    for v in sorted(results, key=lambda x: -x["mean"])[:8]:
        flag = "PASS" if v["passes"] else "fail"
        print(f"    [{flag}] {v['label']:44s} n={v['n']:4d} R={v['mean']:+.3f} "
              f"CI[{v['ci'][0]:+.3f},{v['ci'][1]:+.3f}] years+={v['pos_years']}")
    return survivors, results


# ════════════════════════════════════════════════════════════════════════════
# D2 — hedge contribution
# ════════════════════════════════════════════════════════════════════════════

def daily_series(rows, r_key, dol_key):
    """date -> (mean return, total dollars, n) for a sleeve."""
    by = defaultdict(list)
    for r in rows:
        if r.get(r_key) is not None:
            by[str(r["date"])].append(r)
    return {d: (fmean([x[r_key] for x in rs]),
                sum(x[dol_key] for x in rs if x.get(dol_key) is not None),
                len(rs))
            for d, rs in by.items()}


def d2_hedge(deployed, bear_rows):
    hdr("D2 — hedge contribution: what bear does on the deployed book's LOSING dates")
    print("  This is the plan's caveat, tested rather than accepted. The deployed")
    print("  sleeve is the shipped ladder (top-3/day, tiers A/B); the bear sleeve is")
    print("  every bear candidate that date, priced under the bear-keyed exit.")

    dep = daily_series(deployed, "R", "R_dol")
    bear = daily_series(bear_rows, "Rb", "Rb_dol")
    common = sorted(set(dep) & set(bear))
    print(f"\n  deployed dates {len(dep)}   bear dates {len(bear)}   overlapping {len(common)}")
    if len(common) < 20:
        print("  too few overlapping dates to test the hedge — skipped")
        return None

    dep_r = [dep[d][0] for d in common]
    bear_r = [bear[d][0] for d in common]
    corr = statistics.correlation(dep_r, bear_r) if len(common) > 2 else float("nan")
    print(f"  date-level correlation of the two sleeves: {corr:+.3f}")
    print("  (a hedge needs this NEGATIVE — a positive correlation means the bear")
    print("   sleeve loses on the same days the long book does)")

    sub("Deployed-book dates sorted by outcome — the tail is the whole question")
    order = sorted(common, key=lambda d: dep[d][0])
    n_dec = max(3, len(common) // 10)
    buckets = [("worst decile", order[:n_dec]),
               ("worst quartile", order[:max(3, len(common) // 4)]),
               ("negative dates", [d for d in order if dep[d][0] < 0]),
               ("positive dates", [d for d in order if dep[d][0] >= 0]),
               ("ALL", order)]
    print(f"  {'bucket':18s} {'dates':>6s} {'deployed R':>11s} {'bear R':>9s} "
          f"{'bear $':>10s} {'bear win%':>10s}")
    tail_bear = None
    for name, ds in buckets:
        if not ds:
            continue
        d_r = fmean([dep[d][0] for d in ds])
        b_r = fmean([bear[d][0] for d in ds])
        b_d = sum(bear[d][1] for d in ds)
        b_w = sum(1 for d in ds if bear[d][0] > 0) / len(ds)
        print(f"  {name:18s} {len(ds):6d} {d_r:+11.3f} {b_r:+9.3f} {b_d:>10,.0f} {b_w:>9.1%}")
        if name == "worst decile":
            tail_bear = (ds, b_r)

    sub("Does the tail behaviour reproduce by year?")
    ok_years = 0
    tot_years = 0
    for y in sorted({d[:4] for d in common}):
        ys = [d for d in common if d[:4] == y]
        if len(ys) < 6:
            print(f"  {y}: only {len(ys)} overlapping dates — not evaluated")
            continue
        yorder = sorted(ys, key=lambda d: dep[d][0])
        ytail = yorder[:max(2, len(ys) // 4)]
        b_r = fmean([bear[d][0] for d in ytail])
        tot_years += 1
        ok_years += 1 if b_r > 0 else 0
        print(f"  {y}: worst-quartile dates n={len(ytail):3d}  deployed "
              f"{fmean([dep[d][0] for d in ytail]):+.3f}  bear {b_r:+.3f}  "
              f"${sum(bear[d][1] for d in ytail):>9,.0f}")

    sub("Pre-registered D2 rule")
    tail_r = tail_bear[1] if tail_bear else float("nan")
    tail_rows = [r for r in bear_rows if str(r["date"]) in set(tail_bear[0])] if tail_bear else []
    tail_ci = P.boot_ci_by_date(tail_rows, "Rb", n=4000) if len(tail_rows) >= 10 else (float("nan"),) * 2
    met = (tail_r > 0) and (corr < 0) and (ok_years >= 2)
    print(f"  bear R on deployed worst-decile dates: {tail_r:+.3f} "
          f"(row-level CI [{tail_ci[0]:+.3f}, {tail_ci[1]:+.3f}], n={len(tail_rows)}) — "
          f"needs > 0: {'YES' if tail_r > 0 else 'NO'}")
    print(f"  sleeve correlation {corr:+.3f} — needs < 0: {'YES' if corr < 0 else 'NO'}")
    print(f"  tail positive in {ok_years}/{tot_years} evaluable years — needs >= 2: "
          f"{'YES' if ok_years >= 2 else 'NO'}")
    print(f"  HEDGE IS REAL: {'MET' if met else 'NOT MET'}")
    return dict(corr=corr, tail_r=tail_r, ok_years=ok_years, met=met,
                dep=dep, bear=bear, common=common)


# ════════════════════════════════════════════════════════════════════════════
# D3 — sizing
# ════════════════════════════════════════════════════════════════════════════

def max_drawdown(series):
    """Max peak-to-trough drawdown of a cumulative dollar curve."""
    peak, mdd = 0.0, 0.0
    cum = 0.0
    for v in series:
        cum += v
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    return mdd


def _sleeve_dollars(bear_rows, picker, gate=None):
    """date -> dollars of a 1-per-day bear sleeve chosen by `picker`.

    `gate(date, rows)` may veto the day entirely (the D5 conditional sleeve);
    None means carry the sleeve every day a bear candidate exists.
    """
    by_day = defaultdict(list)
    for r in bear_rows:
        if r.get("Rb_dol") is not None:
            by_day[str(r["date"])].append(r)
    out = {}
    for d, rs in by_day.items():
        if gate is not None and not gate(d, rs):
            continue
        keyed = [(picker(r), r) for r in rs]
        keyed = [(k, r) for k, r in keyed if k is not None]
        if not keyed:
            continue
        out[d] = max(keyed, key=lambda kr: kr[0])[1]["Rb_dol"]
    return out


def _sweep(dep, bear_dol, label):
    """Print the f-sweep for one sleeve definition; return (rows, base)."""
    dates = sorted(set(dep) | set(bear_dol))
    print(f"\n  sleeve: {label} — {len(bear_dol)} positions over {len(dates)} book dates")
    print(f"  {'f':>5s} {'total $':>12s} {'max DD $':>12s} {'worst date $':>13s} "
          f"{'neg dates':>10s} {'downside dev':>13s}")
    base, out = None, []
    for f in SIZE_FRACTIONS:
        daily = [dep.get(d, (0, 0.0, 0))[1] + f * bear_dol.get(d, 0.0) for d in dates]
        tot, mdd, worst = sum(daily), max_drawdown(daily), min(daily)
        neg = sum(1 for v in daily if v < 0)
        dd = (statistics.fmean([v * v for v in daily if v < 0]) ** 0.5) if neg else 0.0
        print(f"  {f:5.2f} {tot:>12,.0f} {mdd:>12,.0f} {worst:>13,.0f} "
              f"{neg:>10d} {dd:>13,.0f}")
        if f == 0.0:
            base = (tot, mdd, worst)
        out.append(dict(f=f, total=tot, mdd=mdd, worst=worst))
    return out, base


def _verdict(out, base, label):
    ok = [o for o in out if o["f"] > 0 and o["mdd"] >= base[1] - 1e-9
          and o["worst"] >= base[2] - 1e-9]
    if ok:
        best = max(ok, key=lambda o: o["f"])
        print(f"  [{label}] DEPLOYABLE at f = {best['f']:.2f} — DD {base[1]:,.0f} -> "
              f"{best['mdd']:,.0f}, total ${base[0]:,.0f} -> ${best['total']:,.0f} "
              f"({best['total'] - base[0]:+,.0f})")
        return best
    print(f"  [{label}] NOT MET at any size — no fraction leaves both drawdown and "
          f"worst-date unharmed.")
    # least harmful = the tested size whose drawdown is closest to (or above) base
    least = max((o for o in out if o["f"] > 0), key=lambda o: o["mdd"])
    print(f"      least-harmful tested size f={least['f']:.2f}: DD {base[1]:,.0f} -> "
          f"{least['mdd']:,.0f} ({least['mdd'] - base[1]:+,.0f}), total "
          f"${base[0]:,.0f} -> ${least['total']:,.0f} ({least['total'] - base[0]:+,.0f})")
    return None


def d3_sizing(deployed, bear_rows, d4_adopted):
    hdr("D3 — sizing: how large a bear sleeve the deployed book can carry")
    dep = daily_series(deployed, "R", "R_dol")
    print("  DEVIATION, recorded: the pre-registration fixed the sizing rule but not")
    print("  WHICH bear is taken each day. The first cut used the day's widest")
    print("  max_loss — which D4 then measured as the single WORST available pick")
    print("  (-0.345 vs day average). Both are reported: the D4-adopted picker is the")
    print("  realistic deployment, widest-max_loss is a lower bound on a bad one.")

    pickers = [("widest max_loss (lower bound)",
                lambda r: r.get("max_loss_per_contract") or 0.0)]
    if d4_adopted:
        name = d4_adopted[0]["name"]
        pickers.insert(0, (f"D4-adopted: {name}", D4_RANKERS[name]))

    results = {}
    for label, picker in pickers:
        out, base = _sweep(dep, _sleeve_dollars(bear_rows, picker), label)
        results[label] = (out, base)

    sub("Pre-registered D3 rule: DD and worst-date no worse than f=0")
    for label, (out, base) in results.items():
        _verdict(out, base, label)
    return results


# ════════════════════════════════════════════════════════════════════════════
# D5 — conditional deployment (POST-HOC, labelled as such)
# ════════════════════════════════════════════════════════════════════════════

def d5_conditional_sleeve(deployed, bear_rows, d4_adopted):
    hdr("D5 — carry the hedge only SOME days (POST-HOC — candidate, not a finding)")
    print("  NOT pre-registered. It is the arm D2+D3 jointly imply: the sleeve pays")
    print("  in the deployed book's tail and bleeds in its body, so an ALWAYS-ON")
    print("  hedge cannot clear D3. Every gate below is knowable at deploy time.")
    print("  Held to the same bar as the rest — CI excluding zero, all-fold LOO,")
    print("  and a sign check by year — but read as a candidate for the next")
    print("  independent window, because the gate was chosen after seeing D2.")

    dep = daily_series(deployed, "R", "R_dol")
    picker = D4_RANKERS[d4_adopted[0]["name"]] if d4_adopted else (
        lambda r: r.get("max_loss_per_contract") or 0.0)

    gates = {
        "mech BEAR_HE cell": lambda d, rs: any(r.get("mech_cell") == "BEAR_HE" for r in rs),
        "mech vol L-VOL": lambda d, rs: any(r.get("mech_vol") == "L-VOL" for r in rs),
        "mech vol H-VOL": lambda d, rs: any(r.get("mech_vol") == "H-VOL" for r in rs),
        "mech dir BEAR": lambda d, rs: any(r.get("mech_direction") == "BEAR" for r in rs),
        "model RANGE regime": lambda d, rs: any(r.get("model_dir") == "RANGE" for r in rs),
        "model C-VOL or L-VOL": lambda d, rs: any(r.get("model_vol") in ("C-VOL", "L-VOL") for r in rs),
        "model RANGE + C/L-VOL": lambda d, rs: any(
            r.get("model_dir") == "RANGE" and r.get("model_vol") in ("C-VOL", "L-VOL") for r in rs),
    }

    print(f"\n  {'gate':26s} {'days':>5s} {'f':>5s} {'total $':>11s} {'ΔDD':>10s} "
          f"{'Δworst':>10s} {'Δtotal':>11s}")
    base_dates = sorted(set(dep))
    keep = []
    for gname, gate in gates.items():
        sleeve = _sleeve_dollars(bear_rows, picker, gate=gate)
        if len(sleeve) < 10:
            print(f"  {gname:26s} {len(sleeve):5d}   (too few gated days)")
            continue
        dates = sorted(set(dep) | set(sleeve))
        base_daily = [dep.get(d, (0, 0.0, 0))[1] for d in dates]
        b_tot, b_mdd, b_worst = sum(base_daily), max_drawdown(base_daily), min(base_daily)
        for f in (0.5, 1.0):
            daily = [dep.get(d, (0, 0.0, 0))[1] + f * sleeve.get(d, 0.0) for d in dates]
            tot, mdd, worst = sum(daily), max_drawdown(daily), min(daily)
            flag = "  **" if (mdd >= b_mdd - 1e-9 and worst >= b_worst - 1e-9) else ""
            print(f"  {gname if f == 0.5 else '':26s} {len(sleeve) if f == 0.5 else '':>5} "
                  f"{f:5.2f} {tot:>11,.0f} {mdd - b_mdd:>+10,.0f} "
                  f"{worst - b_worst:>+10,.0f} {tot - b_tot:>+11,.0f}{flag}")
            if flag:
                keep.append((gname, f, tot - b_tot, mdd - b_mdd))

    sub("Gates that leave BOTH drawdown and worst-date unharmed")
    if not keep:
        print("  none — the hedge cannot be timed by any gate tested, at either size.")
        print("  Read: bear deployment is a discretionary risk decision, not a rule the")
        print("  book can hand you.")
        return []
    for gname, f, dtot, dmdd in sorted(keep, key=lambda x: -x[2]):
        print(f"  {gname:26s} f={f:.2f}  Δtotal {dtot:+,.0f}  ΔDD {dmdd:+,.0f}")
    print("\n  Reproduction check on the leading gate (year signs, dollars):")
    gname, f = max(keep, key=lambda x: x[2])[:2]
    sleeve = _sleeve_dollars(bear_rows, picker, gate=gates[gname])
    for y in sorted({d[:4] for d in sleeve}):
        ys = [v for d, v in sleeve.items() if d[:4] == y]
        print(f"    {y}: n={len(ys):3d}  sleeve ${f * sum(ys):>9,.0f}  "
              f"mean ${f * statistics.fmean(ys):>8,.0f}")
    print("  A gate that only pays in one year is the Mar-Apr-2025 failure again.")
    return keep


# ════════════════════════════════════════════════════════════════════════════
# D4 — conditional pick
# ════════════════════════════════════════════════════════════════════════════

def d4_conditional(bear_rows):
    hdr("D4 — GIVEN a bear position is taken today, can any column pick a better one?")
    print("  Within-date and paired: each ranker's top pick is compared against the")
    print("  SAME DAY's bear average. The day is its own control, so the negative")
    print("  level that sinks every B1/D1 subset cancels out. This is the operator's")
    print("  actual question — not 'is bear good' but 'which bear, when I take one'.")

    by_day = defaultdict(list)
    for r in bear_rows:
        if r.get("Rb") is not None:
            by_day[str(r["date"])].append(r)
    multi = {d: rs for d, rs in by_day.items() if len(rs) >= 2}
    print(f"\n  dates with >=2 bear candidates: {len(multi)} "
          f"({sum(len(v) for v in multi.values())} rows); "
          f"mean candidates/day {fmean([len(v) for v in multi.values()]):.1f}")
    if len(multi) < 20:
        print("  too few multi-candidate dates — skipped")
        return []

    print(f"\n  {'ranker':26s} {'dates':>6s} {'pick R':>8s} {'day avg':>8s} "
          f"{'gain':>8s} {'CI95 (paired, by date)':>26s} {'LOO min':>9s}")
    out = []
    for name, fn in D4_RANKERS.items():
        paired = []
        for d, rs in sorted(multi.items()):
            keyed = [(fn(r), r) for r in rs]
            keyed = [(k, r) for k, r in keyed if k is not None]
            if len(keyed) < 2:
                continue
            top = max(keyed, key=lambda kr: kr[0])[1]
            avg = fmean([r["Rb"] for r in rs])
            paired.append(dict(date=d, a=top["Rb"], b=avg))
        if len(paired) < 20:
            print(f"  {name:26s} {len(paired):6d}   (too few ranked dates)")
            continue
        pick_r = fmean([p["a"] for p in paired])
        day_r = fmean([p["b"] for p in paired])
        lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=4000)
        _, share, loo_min, _ = P.loo_by_date(paired, lambda p: p["a"], lambda p: p["b"])
        flag = "  **" if (lo > 0 and loo_min > 0) else ""
        print(f"  {name:26s} {len(paired):6d} {pick_r:+8.3f} {day_r:+8.3f} "
              f"{pick_r - day_r:+8.3f} [{lo:+.3f}, {hi:+.3f}]".ljust(0)
              + f" {loo_min:+9.3f}{flag}")
        out.append(dict(name=name, gain=pick_r - day_r, ci=(lo, hi), loo_min=loo_min,
                        share=share, n=len(paired), paired=paired))

    sub("Pre-registered D4 rule: CI excludes zero AND every LOO fold positive")
    adopted = [o for o in out if o["ci"][0] > 0 and o["loo_min"] > 0]
    print(f"  rankers tested: {len(out)}  adopted: {len(adopted)}  "
          f"(~{0.05 * len(out):.1f} expected by chance)")
    for o in sorted(adopted, key=lambda x: -x["gain"]):
        print(f"    {o['name']:26s} gain {o['gain']:+.3f} "
              f"CI[{o['ci'][0]:+.3f},{o['ci'][1]:+.3f}] LOO min {o['loo_min']:+.3f}")
        for y in sorted({p["date"][:4] for p in o["paired"]}):
            ys = [p for p in o["paired"] if p["date"][:4] == y]
            print(f"      {y}: n={len(ys):3d} gain "
                  f"{fmean([p['a'] for p in ys]) - fmean([p['b'] for p in ys]):+.3f}")
    if not adopted:
        print("  none — no decision-time column picks a better-than-average bear.")
        return adopted

    sub("Exit-dependence check on every adopted ranker")
    print("  `be_after: 0.50` is RECOMMENDED, not shipped. A pick rule that only")
    print("  works under an exit the operator isn't running is not deployable, so")
    print("  each adopted ranker is re-tested on R under the SHIPPED PROD exit and")
    print("  on E, the pure selection basis.")
    for o in adopted:
        fn = D4_RANKERS[o["name"]]
        for basis_label, key in (("Rb (bear exit, recommended)", "Rb"),
                                 ("R  (PROD exit, SHIPPED)", "R"),
                                 ("E  (selection only)", "E")):
            paired = []
            for d, rs in sorted(multi.items()):
                keyed = [(fn(r), r) for r in rs if fn(r) is not None and r.get(key) is not None]
                if len(keyed) < 2:
                    continue
                top = max(keyed, key=lambda kr: kr[0])[1]
                paired.append(dict(date=d, a=top[key],
                                   b=fmean([x[key] for x in rs if x.get(key) is not None])))
            if len(paired) < 20:
                continue
            lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=4000)
            _, _, loo_min, _ = P.loo_by_date(paired, lambda p: p["a"], lambda p: p["b"])
            gain = fmean([p["a"] for p in paired]) - fmean([p["b"] for p in paired])
            yrs = {y: (fmean([p["a"] for p in paired if p["date"][:4] == y])
                       - fmean([p["b"] for p in paired if p["date"][:4] == y]))
                   for y in sorted({p["date"][:4] for p in paired})}
            holds = "HOLDS" if (lo > 0 and loo_min > 0) else "fails"
            print(f"    {o['name']} on {basis_label:28s} gain {gain:+.3f} "
                  f"CI[{lo:+.3f},{hi:+.3f}] LOO {loo_min:+.3f}  {holds}   "
                  + " ".join(f"{y}:{v:+.3f}" for y, v in yrs.items()))
    return adopted


# ════════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-bs", action="store_true")
    args = ap.parse_args()

    records, _ = load_book(include_bs=args.include_bs)
    rows = [r for r in records if r.get("E") is not None and r.get("R") is not None]
    bear = apply_bear_exit([r for r in rows if r["structure"] in BEAR_STRUCTURES])
    deployed = P.top_k_per_day(rows, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)

    hdr("DEPLOY ARM — pre-registered 2026-08-11 "
        "(pre-registrations/f4_deployment/bear_deploy.md)")
    print(f"  book {len(rows)} priced rows / {len({r['date'] for r in rows})} dates")
    print(f"  bear {len(bear)} rows / {len({r['date'] for r in bear})} dates")
    print(f"  deployed ladder sleeve {len(deployed)} rows / "
          f"{len({r['date'] for r in deployed})} dates (top-3/day, tiers A/B)")
    print("  CAVEAT (must travel with any conclusion): this book prices each play")
    print("  standalone. D2 approximates a hedge as equal-weighted concurrent")
    print("  dollars — a proxy for, not a measurement of, a held hedge. 88% of bear")
    print("  rows are bear_put_spread; only 6 are naked long_put, so nothing here")
    print("  speaks to the naked-put hedge the operator sometimes substitutes.")

    # D4 runs before D3 because D3 needs to know which bear a deployment takes.
    d1_survivors, _ = d1_joint(bear)
    d2 = d2_hedge(deployed, bear)
    d4_adopted = d4_conditional(bear)
    d3 = d3_sizing(deployed, bear, d4_adopted)
    d5 = d5_conditional_sleeve(deployed, bear, d4_adopted)

    hdr("VERDICT (pre-registered rules, pre-registrations/f4_deployment/bear_deploy.md)")
    print(f"  D1 joint selection x exit : "
          f"{'candidate(s) found — ' + str(len(d1_survivors)) if d1_survivors else 'NOT MET'}")
    print(f"  D2 hedge is real          : "
          f"{'MET' if (d2 and d2['met']) else 'NOT MET'}")
    d3_ok = any(o["mdd"] >= base[1] - 1e-9 and o["worst"] >= base[2] - 1e-9
                for out, base in d3.values() for o in out if o["f"] > 0)
    print(f"  D3 always-on sizing       : {'MET' if d3_ok else 'NOT MET at any size'}")
    print(f"  D4 conditional pick       : "
          f"{'adopted — ' + ', '.join(o['name'] for o in d4_adopted) if d4_adopted else 'NOT MET'}")
    print(f"  D5 gated sleeve (POST-HOC): "
          f"{str(len(d5)) + ' candidate gate(s)' if d5 else 'no gate survives'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
