"""BEAR arm — pre-registered in research/ml-plan.md §Kickoff addendum.

Operator instruction (2026-08-11): bear positions are NOT to be removed
wholesale — they are wanted for choppy tape — and the exit config may simply be
mis-tuned for them. So the pending bear_put decision is reframed from
demote/keep to **when**, and split into two questions:

  B1  selection conditioning — is there a subset of bear rows, defined only by
      variables known at decision time, that is not negative and reproduces?
  B2  exit fit — does any config from the FROZEN grid beat PROD on bear rows?
      (E<0 with R<E means the exit is leaking; E<0 with R>E means the exit is
      already rescuing what selection got wrong. Both are reported.)

Decision rules were fixed BEFORE this ran; see ml-plan.md. Nothing here changes
config.

CAVEAT AMENDED 2026-08-11 (same day): this module's "the book prices each play
standalone and cannot price a hedge" was too strong. 84 bear dates also carry a
deployed ladder sleeve, so a concurrent-dollar proxy for the hedge IS
measurable — see `bear_deploy.py` (D2), which measures it and finds the hedge
real. Quote the amended version: the book cannot price a *held* hedge with
margin and real sizing, but it can and does price the concurrent book.

Run:
    source .venv/bin/activate
    python -m scripts.backtest_study.bear_arm | tee backtests/study_output/bear_arm.txt
"""
from __future__ import annotations

import argparse
import statistics
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study import protocol as P  # noqa: E402
from scripts.backtest_study.book import CREDIT_PROD, DEBIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.harness import replay  # noqa: E402

BEAR_STRUCTURES = ("bear_put_spread", "bear_call_spread", "long_put")

# Pre-registered decision rule (ml-plan.md §Kickoff addendum, B1).
MIN_N = 40
CI_FLOOR = -0.05
MIN_POSITIVE_YEARS = 2

# The FROZEN exit grid — copied from scripts/backtest_study/exit_mechanism_study.py
# DEBIT_VARIANTS/CREDIT_VARIANTS. This is not a new mechanism search: no config
# outside this list may be evaluated, which is what keeps B2 from becoming a
# free parameter hunt over the same 300 rows.
DEBIT_GRID = [
    ("PROD pt.90 sl.75 tef.75", DEBIT_PROD),
    ("trail .25 trig .50", {**DEBIT_PROD, "trig": 0.50, "trail": 0.25}),
    ("trail .40 trig .50", {**DEBIT_PROD, "trig": 0.50, "trail": 0.40}),
    ("trail .50 trig .50", {**DEBIT_PROD, "trig": 0.50, "trail": 0.50}),
    ("trail .25 trig .75", {**DEBIT_PROD, "trig": 0.75, "trail": 0.25}),
    ("trail .40 trig .75", {**DEBIT_PROD, "trig": 0.75, "trail": 0.40}),
    ("trail .50 trig .75", {**DEBIT_PROD, "trig": 0.75, "trail": 0.50}),
    ("pt .75 no trail", {**DEBIT_PROD, "pt": 0.75}),
    ("pt 1.10 no trail", {**DEBIT_PROD, "pt": 1.10}),
    ("pt 1.25 no trail", {**DEBIT_PROD, "pt": 1.25}),
    ("pt 1.10 trail .50 trig .75", {**DEBIT_PROD, "pt": 1.10, "trig": 0.75, "trail": 0.50}),
    ("pt 1.25 trail .50 trig .75", {**DEBIT_PROD, "pt": 1.25, "trig": 0.75, "trail": 0.50}),
    ("BE ratchet @.50", {**DEBIT_PROD, "be_after": 0.50}),
    ("BE ratchet @.75", {**DEBIT_PROD, "be_after": 0.75}),
    ("BE @.50 + trail .50 trig .75",
     {**DEBIT_PROD, "trig": 0.75, "trail": 0.50, "be_after": 0.50}),
    # DEVIATION from the frozen grid, added 2026-08-11 as a single pre-registered
    # CONFIRMATION (not a search): production's shipped BEAR_HE cell adds a
    # 0.50/0.50 trail, so a bear debit on a BEAR_HE date would run BE *and* that
    # trail — a combination the frozen grid never evaluated (it only tested BE +
    # trail at trigger .75). Decision rule fixed before running: gain holds →
    # stack both in production; degrades/flips/ambiguous → suppress be_after
    # inside BEAR_HE so each rule stays inside its measured envelope.
    ("BE @.50 + trail .50 trig .50",
     {**DEBIT_PROD, "trig": 0.50, "trail": 0.50, "be_after": 0.50}),
    # DEVIATION from the frozen grid, added 2026-08-12 as a pre-registered
    # THRESHOLD SWEEP (four named configs, not a search). Motivation is a
    # measured reach gap, not a hunt: 124 bear-debit rows peaked between +1%
    # and +50% and lost -$77.2k, entirely BELOW the shipped @.50 arming point
    # (current.md §"bear MFE give-back"). The census of peaks does not price
    # the cost on winners that dip back through entry after arming, which is
    # exactly what this replay exists to measure. Decision rule fixed before
    # running: a threshold ships only on the standing bear-arm criteria
    # (pooled CI excludes zero, ex-Mar-Apr-2025 positive, 2026 alone positive,
    # every LOO fold positive, right-signed in both pricing tiers) AND a clean
    # leak guard on the non-bear debit book. If none clears, the pre-committed
    # reading is that bear give-back is structural.
    ("BE ratchet @.20", {**DEBIT_PROD, "be_after": 0.20}),
    ("BE ratchet @.25", {**DEBIT_PROD, "be_after": 0.25}),
    ("BE ratchet @.30", {**DEBIT_PROD, "be_after": 0.30}),
    ("BE ratchet @.40", {**DEBIT_PROD, "be_after": 0.40}),
    ("tef null", {**DEBIT_PROD, "tef": None}),
    ("tef .85", {**DEBIT_PROD, "tef": 0.85}),
    ("sl .50 (tighter)", {**DEBIT_PROD, "sl": 0.50}),
]
CREDIT_GRID = [
    ("PROD pt.65 sl none", CREDIT_PROD),
    ("pt .50", {**CREDIT_PROD, "pt": 0.50}),
    ("pt .55", {**CREDIT_PROD, "pt": 0.55}),
    ("sl 1x", {**CREDIT_PROD, "sl": 1.00}),
    ("sl 1.5x", {**CREDIT_PROD, "sl": 1.50}),
    ("trail .50 trig .50", {**CREDIT_PROD, "trig": 0.50, "trail": 0.50}),
]


def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


def stat(rows, key="E"):
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    if not vals:
        return None
    dol_key = key + "_dol"
    dol = sum(float(r[dol_key]) for r in rows if r.get(dol_key) is not None)
    return dict(n=len(vals), mean=statistics.fmean(vals),
                med=statistics.median(vals),
                win=sum(1 for v in vals if v > 0) / len(vals), dol=dol,
                dates=len({r["date"] for r in rows}))


def line(label, rows, width=34):
    s_e, s_r = stat(rows, "E"), stat(rows, "R")
    if s_e is None:
        print(f"  {label:{width}s}   (none)")
        return
    mae = [abs(float(r["mae"])) for r in rows if r.get("mae") is not None]
    mfe = [float(r["mfe"]) for r in rows if r.get("mfe") is not None]
    ratio = (statistics.fmean(mae) / statistics.fmean(mfe)) if mfe and statistics.fmean(mfe) else float("nan")
    print(f"  {label:{width}s} n={s_e['n']:4d} d={s_e['dates']:3d} "
          f"E={s_e['mean']:+.3f} R={s_r['mean']:+.3f} win={s_r['win']:5.1%} "
          f"${s_r['dol']:>9,.0f} |MAE|/MFE={ratio:.2f}")


# ════════════════════════════════════════════════════════════════════════════
# B1 — selection conditioning
# ════════════════════════════════════════════════════════════════════════════

def clause_vocabulary():
    """Pre-declared clauses. Fixed in advance to bound the multiple-comparisons
    problem: only these, only singles and pairs, and the count of combinations
    tested is reported alongside any survivor."""
    def eq(field, value):
        return (f"{field}={value}", lambda r, f=field, v=value: r.get(f) == v)

    v = []
    for cell in ("BEAR_HE", "LVOL", "RB_EVOL", "PROD"):
        v.append(eq("mech_cell", cell))
    for d in ("BEAR", "BULL", "RANGE"):
        v.append(eq("mech_direction", d))
        v.append(eq("model_dir", d))
        v.append(eq("stock_dir", d))
    for vol in ("E-VOL", "H-VOL", "L-VOL"):
        v.append(eq("mech_vol", vol))
        v.append(eq("model_vol", vol))
    v.append(("credit", lambda r: bool(r.get("credit"))))
    v.append(("debit", lambda r: not r.get("credit")))
    v.append(("|delta|<=0.20", lambda r: r.get("delta") is not None and abs(r["delta"]) <= 0.20))
    v.append(("|delta|>0.20", lambda r: r.get("delta") is not None and abs(r["delta"]) > 0.20))
    v.append(("0.08<=|delta|<=0.20",
              lambda r: r.get("delta") is not None and 0.08 <= abs(r["delta"]) <= 0.20))
    v.append(("dte<=30", lambda r: r.get("dte") is not None and r["dte"] <= 30))
    v.append(("dte 31-59", lambda r: r.get("dte") is not None and 31 <= r["dte"] <= 59))
    v.append(("dte>=60", lambda r: r.get("dte") is not None and r["dte"] >= 60))
    v.append(("iv_spread>0", lambda r: r.get("iv_spread") is not None and r["iv_spread"] > 0))
    v.append(("iv_spread<=0", lambda r: r.get("iv_spread") is not None and r["iv_spread"] <= 0))
    v.append(("iv_pct>=0.5", lambda r: r.get("iv_pct") is not None and float(r["iv_pct"]) >= 0.5))
    v.append(("iv_pct<0.5", lambda r: r.get("iv_pct") is not None and float(r["iv_pct"]) < 0.5))
    return v


def evaluate_subset(rows, label, n_clauses):
    """Apply the pre-registered B1 criteria. Returns a verdict dict or None."""
    if len(rows) < MIN_N:
        return None
    s = stat(rows, "E")
    lo, hi = P.boot_ci_by_date(rows, "E", n=4000)
    _, pos_years, means = P.sign_stable(rows, key="E")
    cuts = {name: stat(r, "E") for name, r in P.window_cuts(rows).items()}
    cuts_ok = all(c is not None and c["mean"] >= 0 for name, c in cuts.items()
                  if name != "ALL")
    passes = (s["mean"] >= 0 and lo > CI_FLOOR
              and pos_years >= MIN_POSITIVE_YEARS and cuts_ok
              and n_clauses <= 2)
    return dict(label=label, n=s["n"], mean_E=s["mean"], ci=(lo, hi),
                pos_years=pos_years, year_means=means, cuts_ok=cuts_ok,
                passes=passes, rows=rows)


def b1_selection(bear_rows):
    hdr("B1 — selection conditioning: is there a bear subset that is not negative?")

    sub("Baseline — all bear rows, and the structures inside them")
    line("ALL bear structures", bear_rows)
    for st in sorted({r["structure"] for r in bear_rows}):
        line(f"  {st}", [r for r in bear_rows if r["structure"] == st])
    lo, hi = P.boot_ci_by_date(bear_rows, "E", n=4000)
    _, pos, means = P.sign_stable(bear_rows, key="E")
    print(f"  bear E CI95 [{lo:+.3f}, {hi:+.3f}]  per-year E: "
          + "  ".join(f"{y}:{m:+.3f}" for y, m in means.items()))

    sub("Descriptive — where bear rows do best (NOT a decision, read multiplicity below)")
    for field in ("mech_cell", "mech_vol", "mech_direction", "model_dir", "model_vol"):
        print(f"  by {field}:")
        for val in sorted({str(r.get(field)) for r in bear_rows}):
            grp = [r for r in bear_rows if str(r.get(field)) == val]
            if len(grp) >= 15:
                line(f"    {field}={val}", grp)

    sub("The operator's chop hypothesis, tested directly (descriptive, not a rule)")
    print("  'Bear positions are necessary especially when the market is choppy.'")
    print("  E is the selection measure, R is what the PROD exit actually returned:")
    for label, pred in (("mech L-VOL (quiet tape)", lambda r: r.get("mech_vol") == "L-VOL"),
                        ("mech RANGE direction", lambda r: r.get("mech_direction") == "RANGE"),
                        ("model C-VOL (choppy)", lambda r: r.get("model_vol") == "C-VOL"),
                        ("model RANGE direction", lambda r: r.get("model_dir") == "RANGE"),
                        ("model RANGE + C/L-VOL",
                         lambda r: r.get("model_dir") == "RANGE"
                         and r.get("model_vol") in ("C-VOL", "L-VOL"))):
        grp = [r for r in bear_rows if pred(r)]
        if len(grp) < 15:
            continue
        line(label, grp)
        e_lo, e_hi = P.boot_ci_by_date(grp, "E", n=4000)
        r_lo, r_hi = P.boot_ci_by_date(grp, "R", n=4000)
        _, _, r_years = P.sign_stable(grp, key="R")
        print(f"      E CI[{e_lo:+.3f},{e_hi:+.3f}]  R CI[{r_lo:+.3f},{r_hi:+.3f}]  "
              f"R by year: " + "  ".join(f"{y}:{m:+.3f}" for y, m in r_years.items()))
    print("  Read: a slice with E<0 but R>=0 is NOT a selection edge — it is the exit\n"
          "  rescuing a losing selection, and it stops being true if the exit changes.")

    sub("Pre-registered search — all 1- and 2-clause subsets")
    vocab = clause_vocabulary()
    results, tested = [], 0
    for size in (1, 2):
        for combo in combinations(vocab, size):
            names = " AND ".join(c[0] for c in combo)
            preds = [c[1] for c in combo]
            rows = [r for r in bear_rows if all(p(r) for p in preds)]
            tested += 1
            v = evaluate_subset(rows, names, size)
            if v:
                results.append(v)
    survivors = [v for v in results if v["passes"]]
    print(f"  combinations evaluated: {tested}  (with n>={MIN_N}: {len(results)})")
    print(f"  survivors of the full pre-registered rule: {len(survivors)}")
    exp_false = 0.05 * len(results)
    print(f"  expected false survivors at a nominal 5% rate: ~{exp_false:.1f} — a "
          f"survivor count\n  at or below that is noise, not a rule.")

    if survivors:
        print("\n  SURVIVORS (ranked by mean E):")
        for v in sorted(survivors, key=lambda x: -x["mean_E"]):
            print(f"    {v['label']:44s} n={v['n']:4d} E={v['mean_E']:+.3f} "
                  f"CI[{v['ci'][0]:+.3f},{v['ci'][1]:+.3f}] "
                  f"years+={v['pos_years']} cuts_ok={v['cuts_ok']}")
            line("      -> book", v["rows"], width=32)
    print("\n  Best 8 by mean E regardless of passing (context only):")
    for v in sorted(results, key=lambda x: -x["mean_E"])[:8]:
        flag = "PASS" if v["passes"] else "fail"
        print(f"    [{flag}] {v['label']:42s} n={v['n']:4d} E={v['mean_E']:+.3f} "
              f"CI[{v['ci'][0]:+.3f},{v['ci'][1]:+.3f}] years+={v['pos_years']}")
    return survivors, results


# ════════════════════════════════════════════════════════════════════════════
# B2 — exit fit
# ════════════════════════════════════════════════════════════════════════════

def b2_exit(bear_rows, other_rows, side: str):
    """Frozen-grid exit sweep on bear rows, PROD-vs-variant paired by row."""
    grid = DEBIT_GRID if side == "debit" else CREDIT_GRID
    want_credit = side == "credit"
    rows = [r for r in bear_rows if bool(r.get("credit")) == want_credit]
    others = [r for r in other_rows if bool(r.get("credit")) == want_credit]
    hdr(f"B2 — exit fit on BEAR {side} rows (n={len(rows)}, frozen grid only)")
    if len(rows) < 30:
        print("  too few rows to test an exit change — skipped")
        return []

    prod_cfg = grid[0][1]
    base = {}
    for r in rows + others:
        rp = replay(r["t"], **prod_cfg)
        base[id(r)] = rp["pnl_pct"]

    e = stat(rows, "E")
    r_prod = statistics.fmean([base[id(x)] for x in rows])
    print(f"  selection vs exit: mean E {e['mean']:+.3f} vs mean R(PROD replay) "
          f"{r_prod:+.3f}")
    print("  E<0 and R>E means the exit is already RESCUING a bad selection; a "
          "better exit\n  cannot turn a negative-E population positive — it can "
          "only cut the bleed.")

    out = []
    print(f"\n  {'variant':32s} {'meanR':>8s} {'ΔPROD':>8s} {'CI95 (paired, date-clust)':>28s}"
          f" {'LOO min':>9s} {'$':>10s}")
    for name, cfg in grid:
        rep = {id(x): replay(x["t"], **cfg)["pnl_pct"] for x in rows}
        paired = [dict(date=x["date"], a=rep[id(x)], b=base[id(x)]) for x in rows]
        mean_r = statistics.fmean([p["a"] for p in paired])
        delta = mean_r - r_prod
        lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=4000)
        _, share, min_gain, _ = P.loo_by_date(paired, lambda p: p["a"], lambda p: p["b"])
        dollars = sum(x["t"].dollars(rep[id(x)]) for x in rows)
        flag = "  **" if (lo > 0) else ""
        print(f"  {name:32s} {mean_r:+8.3f} {delta:+8.3f} "
              f"[{lo:+.3f}, {hi:+.3f}]".ljust(0)
              + f"   {min_gain:+9.3f} {dollars:>10,.0f}{flag}")
        out.append(dict(name=name, mean_r=mean_r, delta=delta, ci=(lo, hi),
                        loo_min=min_gain, loo_share=share, dollars=dollars,
                        cfg=cfg))

    # Rule 4 is mandatory on any headline, and addendum 12 is the direct
    # precedent: a structure-keyed bear trail looked good pooled and was negative
    # outside one window. A variant that does not survive these cuts is a window
    # fit, whatever its CI said.
    passing = [o for o in out if o["name"] != grid[0][0] and o["ci"][0] > 0
               and o["loo_min"] > 0]
    if passing:
        sub("Window / year / tier cuts on every variant that passed CI+LOO")
        for o in sorted(passing, key=lambda x: -x["delta"])[:6]:
            print(f"  {o['name']}  (pooled Δ {o['delta']:+.3f})")
            cfg = o["cfg"]

            def dlt(subset, ci=False):
                if len(subset) < 15:
                    return None
                a = statistics.fmean([replay(x["t"], **cfg)["pnl_pct"] for x in subset])
                b = statistics.fmean([base[id(x)] for x in subset])
                if not ci:
                    return a - b, len(subset), None
                paired_s = [dict(date=x["date"], a=replay(x["t"], **cfg)["pnl_pct"],
                                 b=base[id(x)]) for x in subset]
                return a - b, len(subset), P.boot_ci_paired_by_date(paired_s, "a", "b",
                                                                   n=2000)

            # The ex-window cuts carry the whole question (addendum 12: 94% of the
            # old bear-trail gain lived in Mar-Apr 2025), so they get a CI, not
            # just a point estimate.
            for name, sub_rows in P.window_cuts(rows).items():
                d = dlt(sub_rows, ci=True)
                if d:
                    ci = f" CI[{d[2][0]:+.3f}, {d[2][1]:+.3f}]" if d[2] else ""
                    print(f"      {name:18s} Δ={d[0]:+.3f} (n={d[1]}){ci}")
            for y, sub_rows in P.by_year(rows).items():
                # 2026 is the SECOND sustained bear drawdown — the data addendum
                # 12 said would settle this — so it gets a CI too.
                d = dlt(sub_rows, ci=(y == "2026"))
                if d:
                    ci = f" CI[{d[2][0]:+.3f}, {d[2][1]:+.3f}]" if d[2] else ""
                    print(f"      year {y:13s} Δ={d[0]:+.3f} (n={d[1]}){ci}")
            for src in sorted({x["source"] for x in rows}):
                d = dlt([x for x in rows if x["source"] == src])
                if d:
                    print(f"      tier {src:13s} Δ={d[0]:+.3f} (n={d[1]})")
            for st in sorted({x["structure"] for x in rows}):
                d = dlt([x for x in rows if x["structure"] == st])
                if d:
                    print(f"      {st:18s} Δ={d[0]:+.3f} (n={d[1]})")
            # What the change actually does to the exit mix — a gain that is all
            # "sell earlier" reads differently from one that avoids stop-outs.
            from collections import Counter
            before = Counter(replay(x["t"], **prod_cfg)["exit_reason"] for x in rows)
            after = Counter(replay(x["t"], **cfg)["exit_reason"] for x in rows)
            keys = sorted(set(before) | set(after))
            print("      exit mix: " + "  ".join(
                f"{k}:{before.get(k, 0)}->{after.get(k, 0)}" for k in keys))
            if others:
                ob = statistics.fmean([base[id(x)] for x in others])
                ov = statistics.fmean([replay(x["t"], **cfg)["pnl_pct"] for x in others])
                print(f"      NON-bear {side} book under the same config: {ob:+.3f} -> "
                      f"{ov:+.3f} ({ov - ob:+.3f}) — why it must be bear-KEYED")

    best = max((o for o in out if o["name"] != grid[0][0]), key=lambda o: o["delta"],
               default=None)
    if best:
        print(f"\n  best non-PROD variant: {best['name']}  Δ={best['delta']:+.3f} "
              f"CI[{best['ci'][0]:+.3f}, {best['ci'][1]:+.3f}] "
              f"LOO min gain {best['loo_min']:+.3f}")
        ships = best["ci"][0] > 0 and best["loo_min"] > 0
        print(f"  pre-registered EXIT FIX criteria (CI excludes zero AND every LOO "
              f"fold positive): {'MET' if ships else 'NOT met'}")
        if others:
            o_base = statistics.fmean([base[id(x)] for x in others])
            o_var = statistics.fmean([replay(x["t"], **best["cfg"])["pnl_pct"]
                                      for x in others])
            print(f"  same variant on NON-bear {side} rows (n={len(others)}): "
                  f"{o_base:+.3f} -> {o_var:+.3f} ({o_var - o_base:+.3f}) — a "
                  f"bear-keyed rule\n  would not touch these, shown only to say "
                  f"whether the effect is bear-specific.")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-bs", action="store_true")
    args = ap.parse_args()

    records, _ = load_book(include_bs=args.include_bs)
    rows = [r for r in records if r.get("E") is not None and r.get("R") is not None]
    bear = [r for r in rows if r["structure"] in BEAR_STRUCTURES]
    other = [r for r in rows if r["structure"] not in BEAR_STRUCTURES]

    hdr("BEAR ARM — pre-registered 2026-08-11 (ml-plan.md §Kickoff addendum)")
    print(f"  book: {len(rows)} priced rows (real+tweak), {len(bear)} bear, "
          f"{len({r['date'] for r in bear})} bear dates")
    print(f"  bear by source: "
          + "  ".join(f"{s}={sum(1 for r in bear if r['source'] == s)}"
                      for s in sorted({r["source"] for r in bear})))
    print("  CAVEAT (amended 2026-08-11): this book prices each play standalone, "
          "but the\n  hedging value IS partly measurable on the concurrent book — "
          "see bear_deploy.py\n  (D2), which finds it real. What stays unpriceable "
          "is a HELD hedge with margin\n  and the operator's real sizing.")

    from collections import Counter
    tiers = Counter(r["tier"] for r in bear)
    print(f"  bear rows by ladder tier: {dict(tiers)} — anything not A/B is never "
          f"deployed\n  by the shipped ladder, so a bear-keyed EXIT rule only "
          f"bites on positions the\n  operator takes deliberately (the chop hedge).")

    survivors, _ = b1_selection(bear)
    b2_exit(bear, other, "debit")
    b2_exit(bear, other, "credit")

    hdr("VERDICT (pre-registered rules, ml-plan.md §Kickoff addendum)")
    print(f"  B1 KEEP-CONDITIONED: {'candidate(s) found' if survivors else 'NOT met'}"
          f" — {len(survivors)} subset(s) passed all criteria")
    print("  B2 EXIT FIX: see the per-side criteria lines above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
