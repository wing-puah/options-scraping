"""ML combination search — pre-registered in research/ml-plan.md.

Question: does ANY learned combination of structure x regime x entry geometry x
enrichment beat the shipped score-free ladder out-of-sample? The benchmark is
the ladder's top-3/day A-then-B replay; the ship criteria were written before
this file ran and live in ml-plan.md §Phase 5. Only a human-readable rule (the
depth-3 tree, M3) is allowed to ship; a black-box score can at most tie-break.

Protocol lives in `protocol.py` (purged walk-forward, date-clustered CIs, replay,
window cuts) — read that module's docstring before changing anything here. Data
comes from `book.py` (real + strike_expiry_tweak only; bs_options_hist is
excluded as evidence per the 2026-08-11 decision).

REFUSES (exit 2) on a book too thin for the purged walk-forward to emit a single
test block, and (exit 3) on an export set that is not the era asked for. Both are
the correct answer on a young era, not a failure — see `MIN_BOOK_DATES` and
`lib/era.py`.

DEVIATION from the plan, recorded here and in ml-plan.md: the gradient-boosting
model is sklearn's HistGradientBoosting rather than LightGBM/XGBoost. Same
algorithm family (histogram GBM with the same depth/leaf/L2 controls), no libomp
system dependency. Nothing else in the protocol changed.

Run:
    source .venv/bin/activate
    pip install -r requirements-study.txt
    python -m scripts.backtest_study.f1_selection.ml_combination | tee backtests/study_output/run.txt
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

OUT_DIR = ROOT / "backtests" / "study_output"
SEED = 20260811

# Exit codes this study returns as a DESIGNED refusal to produce a result rather
# than as a failure: 2 = the era is too thin for the purged walk-forward to emit
# a single block (see MIN_BOOK_DATES below), 3 = `load_book`'s era guard refusing
# an export set that is not the era asked for. Both are the study's CORRECT
# current status on a young book, so `run.py` promotes the refusal to
# `-latest.txt` instead of keeping older numbers under a newer date. It reads
# this by AST parse and never imports the module, so it MUST stay a literal
# module-level assignment — `era.DESIGNED_REFUSAL_EXIT_CODES` would be invisible
# to it and every refusal here would be reported as FAILED.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

# Walk-forward geometry. The 120-day embargo is expensive on a book of only
# ~118 dates, so blocks are kept small to buy back test coverage: at block=15 /
# min_train=40 only 43 dates were ever tested, which is too thin to call a null.
BLOCK = 10
MIN_TRAIN_DATES = 30

# The smallest date count at which `P.walk_forward_splits` can emit even ONE
# block, DERIVED from the geometry above rather than stated:
#   - candidate test blocks start at multiples of BLOCK, so the first start that
#     can hold MIN_TRAIN_DATES training dates is ceil(MIN_TRAIN_DATES / BLOCK) *
#     BLOCK — with 30/10 that is index 30, not 30 exactly by coincidence;
#   - a test block must be non-empty, so one further date has to exist AT that
#     index. Hence + 1.
# This is a COUNT floor and nothing more. The 120-day embargo can still purge a
# nominally-sufficient train set (`train` is filtered to dates >= 120 calendar
# days before the test block), so a book can clear this and still yield no
# block; main() diagnoses that case separately rather than folding the two.
#
# COST OF NOT HAVING THIS: on 2026-08-15 the bare exports were refreshed and the
# book went from ~1,900 rows / 142 dates to 74 rows / 10 dates. The split yielded
# nothing, `tested_dates[0]` raised IndexError, and the study's answer to "is the
# era too young to conclude from" was a traceback.
MIN_BOOK_DATES = math.ceil(MIN_TRAIN_DATES / BLOCK) * BLOCK + 1

# ── feature groups (ablation units; see ml-plan.md Phase 4) ──────────────────
CAT_LADDER = ["structure", "model_dir", "model_vol"]
CAT_REGIME = ["mech_cell", "mech_direction", "mech_vol", "stock_dir", "stock_vol",
              "horizon_bucket"]
NUM_GEOMETRY = ["abs_delta", "dte", "iv_entry", "risk_ratio"]
NUM_ENRICH = ["iv_spread", "iv_skew", "iv_pct", "oi_confirm_pct", "cpir",
              "price_vector", "days_to_earnings"]
NUM_SCORES = ["score_total", "score_flow", "score_dealer", "score_price",
              "score_vol", "score_catalyst"]
NUM_CALENDAR = ["dow", "month_num"]
BOOL_FEATS = ["credit", "risk_off", "hedge_pressure", "post13c_flag"]

GROUPS = {
    "ladder": (CAT_LADDER, [], []),
    "regime": (CAT_REGIME, [], ["credit", "risk_off", "hedge_pressure"]),
    "geometry": ([], NUM_GEOMETRY, []),
    "enrichment": ([], NUM_ENRICH, []),
    "scores": ([], NUM_SCORES, ["post13c_flag"]),
    "calendar": ([], NUM_CALENDAR, []),
}


def hdr(t):
    print(f"\n{'=' * 78}\n{t}\n{'=' * 78}")


def sub(t):
    print(f"\n--- {t} " + "-" * max(0, 72 - len(t)))


# ════════════════════════════════════════════════════════════════════════════
# Phase 0 — dataset assembly
# ════════════════════════════════════════════════════════════════════════════

def _horizon_bucket(rec):
    h = str(rec.get("horizon") or "").strip()
    if h:
        return h
    dte = rec.get("dte")
    if dte is None:
        return "unknown"
    return "14" if dte <= 21 else ("60" if dte <= 90 else ("180" if dte <= 240 else "720"))


def build_frame(records) -> pd.DataFrame:
    """One row per priced play, features frozen at decision time (D+1 morning).

    LEAKAGE RULE: nothing computed from the price path after entry (E, R, MFE,
    MAE, exit_reason, days_held) may become a feature. Those are labels and are
    carried alongside, never in the matrix — `feature_columns()` is the only
    thing that selects model inputs.
    """
    rows = []
    for r in records:
        if r.get("E") is None or r.get("R") is None:
            continue
        mr = (r.get("market_regime") or "").upper()
        delta = r.get("delta")
        prem, maxloss = r.get("entry_premium_total"), r.get("max_loss_per_contract")
        rows.append(dict(
            date=r["date"], month=r["month"], ticker=r["ticker"],
            structure=r["structure"], source=r["source"], tier=r["tier"],
            # labels
            E=float(r["E"]), R=float(r["R"]),
            E_dol=r.get("E_dol"), R_dol=r.get("R_dol"),
            mfe=r.get("mfe"), mae=r.get("mae"),
            # categorical features
            model_dir=r.get("model_dir") or "NA",
            model_vol=r.get("model_vol") or "NA",
            mech_cell=r.get("mech_cell") or "NA",
            mech_direction=r.get("mech_direction") or "NA",
            mech_vol=r.get("mech_vol") or "NA",
            stock_dir=r.get("stock_dir") or "NA",
            stock_vol=r.get("stock_vol") or "NA",
            horizon_bucket=_horizon_bucket(r),
            # boolean features
            credit=bool(r.get("credit")),
            risk_off="RISK-OFF" in mr or "RISK OFF" in mr,
            hedge_pressure="HP" in mr.split() or "HEDGE" in mr,
            post13c_flag=bool(r.get("post13c")),
            # numeric features
            abs_delta=abs(delta) if delta is not None else np.nan,
            dte=r.get("dte"),
            iv_entry=r.get("iv_entry"),
            risk_ratio=(prem / maxloss) if (prem and maxloss) else np.nan,
            iv_spread=r.get("iv_spread"), iv_skew=r.get("iv_skew"),
            iv_pct=r.get("iv_pct"), oi_confirm_pct=r.get("oi_confirm_pct"),
            cpir=r.get("cpir"), price_vector=r.get("price_vector"),
            days_to_earnings=r.get("days_to_earnings"),
            dow=pd.Timestamp(r["date"]).dayofweek,
            month_num=int(r["date"][5:7]),
            # ladder inputs kept for the replay benchmark
            score_total=r.get("score_total"), post13c=r.get("post13c"),
            **{k: r.get(k) for k in NUM_SCORES if k != "score_total"},
        ))
    df = pd.DataFrame(rows)
    # Score features are only meaningful post-13c: pre-13c scores anti-select
    # (2026-07-21), so they are masked rather than mixed into one column.
    for c in NUM_SCORES:
        df[c] = pd.to_numeric(df[c], errors="coerce").where(df["post13c_flag"])
    for c in NUM_GEOMETRY + NUM_ENRICH + NUM_CALENDAR:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["y_bin"] = (df["E"] > 0).astype(int)
    return df.sort_values(["date", "ticker"]).reset_index(drop=True)


def feature_columns(groups=None):
    groups = list(GROUPS) if groups is None else groups
    cats, nums, bools = [], [], []
    for g in groups:
        c, n, b = GROUPS[g]
        cats += c
        nums += n
        bools += b
    return cats, nums, bools


def design_matrix(df: pd.DataFrame, groups=None) -> pd.DataFrame:
    """One-hot + numeric matrix. Categories are taken from the WHOLE book on
    purpose: a level absent from a training fold becomes an all-zero column, and
    the encoding uses no label information, so this is not leakage."""
    cats, nums, bools = feature_columns(groups)
    parts = []
    if cats:
        parts.append(pd.get_dummies(df[cats].astype(str), prefix=cats, dtype=float))
    if bools:
        parts.append(df[bools].astype(float))
    if nums:
        parts.append(df[nums].astype(float))
    X = pd.concat(parts, axis=1) if parts else pd.DataFrame(index=df.index)
    return X


def leakage_audit(df: pd.DataFrame) -> None:
    """Fail loudly if a label ever reaches the matrix (Phase-0 gate)."""
    labels = {"E", "R", "E_dol", "R_dol", "mfe", "mae", "y_bin", "exit_reason",
              "days_held", "tier"}
    X = design_matrix(df)
    bad = labels & set(X.columns)
    assert not bad, f"label leaked into the design matrix: {bad}"
    print(f"  leakage audit: OK — {X.shape[1]} feature columns, none label-derived")
    miss = X.isna().mean().sort_values(ascending=False)
    hi = miss[miss > 0.05]
    if len(hi):
        print("  missingness > 5% (imputed with an indicator, never row-dropped):")
        for c, v in hi.items():
            print(f"    {c:24s} {v:6.1%}")


# ════════════════════════════════════════════════════════════════════════════
# Model fitting under the purged walk-forward
# ════════════════════════════════════════════════════════════════════════════

def _fit_predict(make_model, Xtr, ytr, Xte, linear: bool):
    """Fit one fold. Linear models need imputation + scaling; the tree family
    takes NaN natively, so imputing for it would only blur a real 'missing'."""
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    model = make_model()
    if linear:
        model = make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                              StandardScaler(), model)
    model.fit(Xtr, ytr)
    if hasattr(model, "predict_proba"):
        return model.predict_proba(Xte)[:, 1], model
    return model.predict(Xte), model


def oof_predictions(df, X, y, make_model, linear=False, block=BLOCK,
                    min_train_dates=MIN_TRAIN_DATES):
    """Out-of-fold predictions under the purged expanding walk-forward.

    Returns (pred Series indexed like df — NaN where a row was never in a test
    block, fitted_models per fold).
    """
    pred = pd.Series(np.nan, index=df.index, dtype=float)
    models = []
    for train_dates, test_dates in P.walk_forward_splits(df["date"], block=block,
                                                         min_train_dates=min_train_dates):
        tr = df["date"].isin(train_dates).values
        te = df["date"].isin(test_dates).values
        if tr.sum() < 30 or te.sum() == 0:
            continue
        p, m = _fit_predict(make_model, X[tr], y[tr], X[te], linear)
        pred[np.where(te)[0]] = p
        models.append((train_dates, test_dates, m))
    return pred, models


# ════════════════════════════════════════════════════════════════════════════
# Replay comparison: model ranking vs the shipped ladder, same dates
# ════════════════════════════════════════════════════════════════════════════

def _recs(df: pd.DataFrame, pred=None):
    out = df.to_dict("records")
    if pred is not None:
        for r, p in zip(out, pred):
            r["pred"] = p
    return out


def _per_date_mean(picks, key="R"):
    by = {}
    for p in picks:
        by.setdefault(p["date"], []).append(float(p[key]))
    return {d: statistics.fmean(v) for d, v in by.items()}


def _paired_gain(a_picks, b_picks):
    """(gain, CI, n_shared_dates) of a over b, paired on the dates BOTH traded."""
    a_by, b_by = _per_date_mean(a_picks), _per_date_mean(b_picks)
    both = sorted(set(a_by) & set(b_by))
    paired = [dict(date=d, a=a_by[d], b=b_by[d]) for d in both]
    if not paired:
        return float("nan"), (float("nan"), float("nan")), 0
    lo, hi = P.boot_ci_paired_by_date(paired, "a", "b", n=4000)
    return statistics.fmean([r["a"] - r["b"] for r in paired]), (lo, hi), len(both)


def _line(label, s):
    print(f"  {label:26s} n={s['n']:4d} dates={s['dates']:3d} "
          f"${s['dollars']:>10,.0f}  meanR={s['mean_R']:+.3f}  "
          f"meanE={s['mean_E']:+.3f}  win={s['win']:5.1%}")


def compare_replay(df, pred, label, k=3, abstain_at=0.0):
    """Top-k/day by model prediction vs the ladder's A-then-B, on the SAME dates.

    Restricted to rows that actually got an out-of-fold prediction — comparing a
    model on its test blocks against a ladder replayed over the whole book would
    be a difference in which days were traded, not in skill.

    THREE strategies are reported, because "which days you trade" is itself a
    decision and the ladder's is to sit out days with no A/B row:

      - forced   : top-k every tested date (the plan's literal replay)
      - abstain  : top-k, but only rows predicted above `abstain_at` — gives the
                   model the same right to sit out. NOT in the original plan;
                   added 2026-08-11 so the benchmark is not a straw man.
      - tie-break: model ranks WITHIN the ladder's A/B set — the pre-registered
                   ADOPT-AS-TIE-BREAK form, where the ladder still chooses the
                   universe and the model only orders it.
    """
    tested = df[pred.notna()].copy()
    tested["pred"] = pred[pred.notna()].values
    recs = _recs(tested)

    forced = P.top_k_per_day(recs, lambda r: r["pred"], k=k)
    abstain = P.top_k_per_day(recs, lambda r: r["pred"], k=k,
                              eligible_fn=lambda r: r["pred"] > abstain_at)
    tiebreak = P.top_k_per_day(recs, lambda r: r["pred"], k=k,
                               eligible_fn=P.ladder_eligible)
    ladder = P.top_k_per_day(recs, P.ladder_rank, k=k, eligible_fn=P.ladder_eligible)

    _line(f"{label} forced", P.replay_stats(forced))
    _line(f"{label} abstain", P.replay_stats(abstain))
    _line(f"{label} tie-break in A/B", P.replay_stats(tiebreak))
    _line("B0 ladder (same dates)", P.replay_stats(ladder))

    out = dict(label=label, picks=forced, ladder_picks=ladder,
               abstain_picks=abstain, tiebreak_picks=tiebreak)
    for name, picks in (("forced", forced), ("abstain", abstain),
                        ("tiebreak", tiebreak)):
        gain, ci, nd = _paired_gain(picks, ladder)
        flag = "  ** excludes zero **" if (ci[0] > 0 or ci[1] < 0) else ""
        print(f"    paired R gain vs ladder, {name:9s} on {nd:3d} shared dates: "
              f"{gain:+.3f}  CI95 [{ci[0]:+.3f}, {ci[1]:+.3f}]{flag}")
        out[f"gain_{name}"] = gain
        out[f"ci_{name}"] = ci
    out["gain"], out["ci"] = out["gain_forced"], out["ci_forced"]
    return out


def cut_report(picks, label):
    """Mandatory cuts on any headline: ex-window, per-year sign, real-tier-only."""
    for name, rows in P.window_cuts(picks).items():
        s = P.replay_stats(rows)
        print(f"    {label} {name:16s} n={s['n']:4d} ${s['dollars']:>10,.0f} "
              f"meanR={s['mean_R']:+.3f}")
    stable, pos, means = P.sign_stable(picks, key="R")
    per_year = "  ".join(f"{y}:{m:+.3f}" for y, m in means.items())
    print(f"    {label} per-year R  {per_year}   sign-stable={stable} ({pos} positive)")
    real_only = [p for p in picks if p["source"] == "real"]
    s = P.replay_stats(real_only)
    print(f"    {label} real-tier-only  n={s['n']:4d} ${s['dollars']:>10,.0f} "
          f"meanR={s['mean_R']:+.3f}")


# ════════════════════════════════════════════════════════════════════════════
# Phases
# ════════════════════════════════════════════════════════════════════════════

def phase1_baselines(df, y_e, y_bin):
    from sklearn.linear_model import ElasticNetCV, LogisticRegression

    hdr("PHASE 1 — baselines (must run before any model)")

    sub("B0 — the benchmark: shipped ladder, top-3/day A-then-B (whole book)")
    recs = _recs(df)
    picks = P.top_k_per_day(recs, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)
    s = P.replay_stats(picks)
    print(f"  n={s['n']} dates={s['dates']} ${s['dollars']:,.0f} "
          f"meanR={s['mean_R']:+.3f} meanE={s['mean_E']:+.3f} win={s['win']:.1%}")
    cut_report(picks, "B0")

    sub("B1 — logistic on E>0, structure x market-direction x vol only")
    X1 = design_matrix(df, ["ladder"])
    p1, _ = oof_predictions(df, X1.values, y_bin,
                            lambda: LogisticRegression(max_iter=2000, C=0.5),
                            linear=True)
    r1 = compare_replay(df, p1, "B1 logistic", abstain_at=0.5)

    sub("B2 — elastic net on E, full feature set")
    X2 = design_matrix(df)
    p2, models2 = oof_predictions(
        df, X2.values, y_e,
        lambda: ElasticNetCV(l1_ratio=[0.1, 0.5, 0.9], cv=5, random_state=SEED,
                             max_iter=5000),
        linear=True)
    r2 = compare_replay(df, p2, "B2 elastic net")
    nz = []
    for _, _, m in models2:
        en = m[-1]
        nz.append(int((en.coef_ != 0).sum()))
    print(f"  non-zero coefficients per fold: {nz} (of {X2.shape[1]} features)")
    return {"B0": dict(picks=picks, stats=s), "B1": r1, "B2": r2}


def phase2_models(df, y_e, y_bin):
    from sklearn.ensemble import (HistGradientBoostingClassifier,
                                  HistGradientBoostingRegressor)
    from sklearn.tree import DecisionTreeRegressor, export_text

    hdr("PHASE 2/3 — models under the purged walk-forward")
    X = design_matrix(df)
    Xv = X.values

    sub("M1 — histogram GBM on E (depth 3, min_leaf 30, strong L2)")
    p_m1, _ = oof_predictions(df, Xv, y_e, lambda: HistGradientBoostingRegressor(
        max_depth=3, min_samples_leaf=30, l2_regularization=1.0, learning_rate=0.05,
        max_iter=400, early_stopping=True, validation_fraction=0.2,
        random_state=SEED))
    r_m1 = compare_replay(df, p_m1, "M1 GBM (E)")

    sub("M2 — histogram GBM on E>0 (classification is often stabler at this n)")
    p_m2, _ = oof_predictions(df, Xv, y_bin, lambda: HistGradientBoostingClassifier(
        max_depth=3, min_samples_leaf=30, l2_regularization=1.0, learning_rate=0.05,
        max_iter=400, early_stopping=True, validation_fraction=0.2,
        random_state=SEED))
    r_m2 = compare_replay(df, p_m2, "M2 GBM (E>0)", abstain_at=0.5)

    sub("M3 — single depth-3 tree on E (the only shippable form: a checklist)")
    p_m3, models3 = oof_predictions(df, Xv, y_e, lambda: DecisionTreeRegressor(
        max_depth=3, min_samples_leaf=40, random_state=SEED))
    r_m3 = compare_replay(df, p_m3, "M3 depth-3 tree")
    cut_report(r_m3["picks"], "M3")
    if models3:
        full = DecisionTreeRegressor(max_depth=3, min_samples_leaf=40,
                                     random_state=SEED)
        ok = ~np.isnan(y_e)
        full.fit(np.nan_to_num(Xv[ok], nan=0.0), y_e[ok])
        print("\n  Full-sample M3 tree (READ AS A HYPOTHESIS, not a ship candidate —\n"
              "  the ship test is the out-of-fold replay above):")
        txt = export_text(full, feature_names=list(X.columns), max_depth=3)
        print("    " + txt.replace("\n", "\n    "))
    return {"M1": r_m1, "M2": r_m2, "M3": r_m3, "X": X, "pred_m1": p_m1}


def phase4_attribution(df, X, y_e):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.inspection import permutation_importance

    hdr("PHASE 4 — attribution, composition test, ablations")

    sub("Permutation importance (fitted per fold, permuted on its TEST block)")
    imps = {}
    for train_dates, test_dates in P.walk_forward_splits(df["date"], block=BLOCK,
                                                         min_train_dates=MIN_TRAIN_DATES):
        tr = df["date"].isin(train_dates).values
        te = df["date"].isin(test_dates).values
        if tr.sum() < 30 or te.sum() < 10:
            continue
        m = HistGradientBoostingRegressor(max_depth=3, min_samples_leaf=30,
                                          l2_regularization=1.0, learning_rate=0.05,
                                          max_iter=400, early_stopping=True,
                                          validation_fraction=0.2, random_state=SEED)
        m.fit(X.values[tr], y_e[tr])
        pi = permutation_importance(m, X.values[te], y_e[te], n_repeats=8,
                                    random_state=SEED)
        for c, v in zip(X.columns, pi.importances_mean):
            imps.setdefault(c, []).append(v)
    ranked = sorted(((statistics.fmean(v), c) for c, v in imps.items()), reverse=True)
    top5 = [c for _, c in ranked[:5]]
    for v, c in ranked[:10]:
        print(f"    {c:34s} {v:+.4f}")

    sub("Composition-proxy test (rule 6) — top-5 features re-tested WITHIN structure")
    print("    Spearman(feature, E) overall vs inside each structure. A feature "
          "that\n    survives only pooled is a composition proxy (the "
          "oi_confirm/iv_pct trap).")
    for c in top5:
        if c not in df.columns:
            print(f"    {c:24s} (one-hot level — not a continuous feature)")
            continue
        col = pd.to_numeric(df[c], errors="coerce")
        overall = col.corr(df["E"], method="spearman")
        inner = []
        for st, g in df.groupby("structure"):
            if len(g) < 40:
                continue
            v = pd.to_numeric(g[c], errors="coerce").corr(g["E"], method="spearman")
            if v == v:
                inner.append(f"{st.replace('_spread', ''):9s}{v:+.2f}(n={len(g)})")
        print(f"    {c:24s} pooled {overall:+.2f} | " + "  ".join(inner))

    sub("Ablations — how much does anything beyond structure x regime add?")
    from sklearn.ensemble import HistGradientBoostingRegressor as GBM
    combos = [["ladder"], ["ladder", "regime"], ["ladder", "regime", "geometry"],
              ["ladder", "regime", "geometry", "enrichment"],
              ["ladder", "regime", "geometry", "enrichment", "scores"],
              list(GROUPS)]
    for groups in combos:
        Xg = design_matrix(df, groups)
        p, _ = oof_predictions(df, Xg.values, y_e, lambda: GBM(
            max_depth=3, min_samples_leaf=30, l2_regularization=1.0,
            learning_rate=0.05, max_iter=400, early_stopping=True,
            validation_fraction=0.2, random_state=SEED))
        tested = df[p.notna()].copy()
        tested["pred"] = p[p.notna()].values
        picks = P.top_k_per_day(_recs(tested), lambda r: r["pred"], k=3)
        s = P.replay_stats(picks)
        print(f"    {'+'.join(groups):52s} ${s['dollars']:>10,.0f} "
              f"meanR={s['mean_R']:+.3f} meanE={s['mean_E']:+.3f}")


def phase5_decision(res1, res2):
    hdr("PHASE 5 — pre-registered ship decision (ml-plan.md, written before the run)")
    m3 = res2["M3"]
    lo, hi = m3["ci"]
    beats = lo > 0
    picks = m3["picks"]
    _, pos, means = P.sign_stable(picks, key="R")
    years_ok = pos >= 2
    cuts_ok = all(P.replay_stats(rows)["mean_R"] > 0
                  for name, rows in P.window_cuts(picks).items() if name != "ALL")
    print(f"  M3 out-of-fold paired R gain vs B0: {m3['gain']:+.3f} "
          f"CI95 [{lo:+.3f}, {hi:+.3f}]  -> CI excludes zero: {beats}")
    print(f"  positive in >=2 of 3 years: {years_ok}  ({means})")
    print(f"  survives both ex-window cuts: {cuts_ok}")
    verdict = ("SHIP (ladder v2)" if (beats and years_ok and cuts_ok)
               else "NULL RESULT — the ladder is at/near the ceiling of this data")
    for name in ("B1", "B2", "M1", "M2"):
        r = res1.get(name) or res2.get(name)
        if r:
            print(f"  {name:3s} gain {r['gain']:+.3f} CI [{r['ci'][0]:+.3f}, "
                  f"{r['ci'][1]:+.3f}]")
    print(f"\n  VERDICT: {verdict}")
    print("  (ADOPT-AS-TIE-BREAK requires a within-tier ordering gain at the same "
          "CI standard —\n   evaluate only if a model's gain CI excludes zero "
          "while M3's does not.)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-bs", action="store_true",
                    help="include bs_options_hist rows (NOT evidence — curiosity only)")
    args = ap.parse_args()

    hdr("PHASE 0 — dataset assembly + leakage audit")
    records, diag = load_book(include_bs=args.include_bs)
    print(f"  era={diag['era']}  book dates={diag['n_dates']}  "
          f"{diag['date_range'][0]} .. {diag['date_range'][1]}")
    # Refuse HERE, with the numbers, rather than deep inside the split. Nothing
    # below this line is meaningful on a book that cannot carry one test block.
    era.require_dates(diag["n_dates"], diag["era"], minimum=MIN_BOOK_DATES,
                      what=f"{MIN_TRAIN_DATES} purged train dates rounded up to a "
                           f"{BLOCK}-date block boundary, plus one test date")

    df = build_frame(records)
    print(f"  rows={len(df)}  dates={df['date'].nunique()}  "
          f"{df['date'].min()} .. {df['date'].max()}")
    print(f"  sources: {dict(df['source'].value_counts())}")
    print(f"  structures: {dict(df['structure'].value_counts())}")
    print(f"  credit rows (ungated calibration): {diag['n_credit_ungated']}")
    leakage_audit(df)

    # A second, SMALLER quantity than the one checked above: `build_frame` drops
    # every row without a realised E/R, so the frame can hold fewer dates than
    # the book. The split runs on THESE dates, so this is the count that decides
    # whether it can emit a block.
    era.require_dates(int(df["date"].nunique()), diag["era"], minimum=MIN_BOOK_DATES,
                      what="dates with at least one priced, outcome-bearing row")

    blocks = list(P.walk_forward_splits(df["date"], block=BLOCK,
                                        min_train_dates=MIN_TRAIN_DATES))
    if not blocks:
        # Count floor cleared, embargo still bites: the dates are there but they
        # are packed into fewer than PATH_CAP_DAYS of calendar, so every
        # candidate train set is purged. Distinct from the thin-era refusal
        # above and worth saying separately — "add more dates" is the fix for
        # one, "wait for calendar time to pass" is the fix for the other.
        print(f"\nREFUSED — era {diag['era']} has {df['date'].nunique()} priced "
              f"dates ({df['date'].min()} .. {df['date'].max()}), enough to index "
              f"a test block but not enough CALENDAR: the {P.PATH_CAP_DAYS}-day "
              f"embargo purges every candidate train set, so the walk-forward "
              f"yields no block.\n"
              f"  Not a failure, and not a reason to shrink the embargo — the "
              f"embargo is what keeps a train label from being realised after a "
              f"test row's entry. Re-run as the era accrues.")
        return era.EXIT_THIN_ERA

    tested_dates = sorted({d for _, test in blocks for d in test})
    print(f"  purged walk-forward: {len(blocks)} test blocks of {BLOCK} dates, "
          f"embargo {P.PATH_CAP_DAYS}d -> {len(tested_dates)} of "
          f"{df['date'].nunique()} dates ever tested "
          f"({tested_dates[0]} .. {tested_dates[-1]})")

    y_e = df["E"].to_numpy(dtype=float)
    y_bin = df["y_bin"].to_numpy(dtype=int)

    res1 = phase1_baselines(df, y_e, y_bin)
    res2 = phase2_models(df, y_e, y_bin)
    phase4_attribution(df, res2["X"], y_e)
    phase5_decision(res1, res2)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    keep = [c for c in df.columns if c not in ("t",)]
    df[keep].to_csv(OUT_DIR / "dataset.csv", index=False)
    print(f"\nDataset written to {OUT_DIR / 'dataset.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
