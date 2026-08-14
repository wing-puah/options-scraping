"""v4 emission-composition bridge — does the v3-derived ladder still apply to v4 rows?

WRITTEN BEFORE THE DATA EXISTS (2026-08-12), deliberately. v4 had 10 rows on one
date when this was written, so nothing here can have been tuned to a result. Do
not "fix" a test after seeing its output — that is the whole point of the file.

WHAT THIS ANSWERS
-----------------
The columns dropped at v4 (`score_flow`, `score_dealer`) are established as
decision-irrelevant, so that is NOT the risk. The risk is **behavioural**:
removing two of five Step-5 factors may change *what plays the model emits*. The
only statistically significant version-over-version difference in the entire
tuning log was exactly that — credit emission 19% -> 34% at v2->v3, also
unpredicted. If the emission profile shifts, every rule in
`config/deployment-rules.md` was derived on a population v4 no longer draws from,
and the ladder's validation does not transfer.

PRE-REGISTERED, from current.md §"v4 emission-composition bridge" (2026-08-11)
and its 2026-08-12 recorded deviation:

  Five tests   structure mix / credit share / plays per day / bear share /
               ladder tier mix
  Matching     on `mech_cell`, NOT on calendar date. The deviation exists
               because the original design needed ~20 fresh headless analysis
               runs on v3-covered dates; v4 accrues ~10 rows/day for free, so
               this waits instead of paying. v3 is reweighted to v4's mech_cell
               mix (direct standardisation) so a difference in regime
               composition cannot masquerade as a difference in behaviour.
  Alpha        0.05 per test, NO multiplicity correction. Deliberately liberal
               and fixed in advance: a false alarm costs nothing (keep deploying
               under v3 rules), a miss costs the ladder's validity.
  Decision     no test fires -> the v3-derived ladder CARRIES FORWARD to v4.
               any test fires -> the ladder is UNVALIDATED on v4: keep deploying
               under v3 rules, flag every v4 row in current.md, and do NOT
               re-derive the ladder on v4 rows until there are enough to mean
               anything.
  Power        Thin by construction. Powered to catch a shift the size of the
               v2->v3 credit jump and nothing subtler; mech_cell matching is
               coarser than date matching. A null means "no large shift
               detected", NEVER "the populations are the same".

GATE: exits non-zero until v4 has >= 20 dates. That is the correct answer, not a
failure — see backtest-tuning/README.md.

    python -m scripts.backtest_study run v4_bridge
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "backtests" / "to_evaluate"

# --- pre-registered constants. Changing these after a run invalidates it. ----
MIN_V4_DATES = 20
ALPHA = 0.05

# Exit codes this script returns as a DESIGNED refusal to produce a result —
# not a bug: 2 = the MIN_V4_DATES gate above not yet met, 3 = the era guard
# below (main()) refusing to compare a book against itself. Both are
# pre-registered, terminal, and quotable — see the module docstring's GATE
# note and backtest-tuning/README.md's "non-zero exit is often correct".
# scripts/backtest_study/run.py reads this constant via `ast` (never imports
# the module) to report a matching exit under `run --all` as REFUSED rather
# than FAILED, and to still promote `v4_bridge-latest.txt` on that exit — see
# run.py's "Designed refusals" docstring note.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
# v3 carried these two; v4 dropped them (ROW_COLUMNS 27 -> 25). Era is detected
# from the schema, never from the filename — the v3 and v4 exports are both
# called "AnalysisClaude" after the in-place vN_ rename, and attributing numbers
# to the wrong book has happened before (current.md, 07-22 vs 08-08).
V3_ONLY_COLS = ("score_flow", "score_dealer")

STRUCTURES = ("bull_call_spread", "bull_put_spread", "bear_put_spread",
              "long_call", "long_put", "other")
CREDIT = {"bull_put_spread", "bear_call_spread", "short_put", "short_call"}
BEARISH = {"bear_put_spread", "long_put", "bear_call_spread", "short_call"}


# --------------------------------------------------------------------------
# parsing — shared vocabulary with scripts/live_loop/stage1_map_fills.py
# --------------------------------------------------------------------------
def play_structure(play_text: str) -> str:
    t = str(play_text).lower()
    for key in ["bull call spread", "bear call spread", "bull put spread",
                "bear put spread"]:
        if key in t:
            return key.replace(" ", "_")
    if "protective put spread" in t or "put spread" in t:
        return "bear_put_spread"
    if "call spread" in t:
        return "bull_call_spread"
    if "long call" in t:
        return "long_call"
    if "long put" in t:
        return "long_put"
    return "other"


def _model_direction(regime: str) -> str | None:
    for d in ("BULL", "BEAR", "RANGE"):
        if d in str(regime):
            return d
    return None


def _model_vol(regime: str) -> str | None:
    for v in ("E-VOL", "H-VOL", "L-VOL", "C-VOL"):
        if v in str(regime):
            return v
    return None


def ladder_tier(structure: str, market_regime: str) -> str:
    """VETO / A / B / C per config/deployment-rules.md, keyed on the MODEL regime.

    Mirrors `book.ladder_tier()` with ONE documented difference: short-leg
    |delta| and DTE are not columns on an analysis row, so the Tier-B bull_put
    geometry clause cannot be evaluated and every bull_put falls to C. That
    biases the tier mix — but IDENTICALLY in both eras, which is all a
    composition comparison needs. It would be wrong to quote these tier shares
    as deployment shares.
    """
    mdir, mvol = _model_direction(market_regime), _model_vol(market_regime)
    if structure == "bear_call_spread":
        return "VETO"
    if mdir == "BEAR" and mvol == "H-VOL":
        return "VETO"
    if structure == "bull_call_spread":
        return "A" if (mdir == "RANGE" or mvol == "E-VOL") else "B"
    return "C"


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------
def detect_era(df: pd.DataFrame) -> str:
    return "v3" if any(c in df.columns for c in V3_ONLY_COLS) else "v4"


def _resolve(preferred: str) -> Path:
    """`preferred` if it exists, else the bare AnalysisClaude export."""
    p = EVAL_DIR / preferred
    return p if p.exists() else EVAL_DIR / "analysis - AnalysisClaude.csv"


def load(path: Path) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"missing export: {path}")
    df = pd.read_csv(path)
    for col in ("date", "ticker", "play", "regime", "mech_cell"):
        if col not in df.columns:
            sys.exit(f"{path.name}: required column {col!r} not present")

    # The MARKET row carries the top-level regime; play rows carry their own
    # per-play regime and must NEVER be read as the market read (see the
    # invariant in scripts/analysis_pipeline/core.py). The ladder keys on the
    # MARKET regime, so join it on per date.
    market = (df[df["ticker"] == "MARKET"]
              .drop_duplicates("date").set_index("date")["regime"])
    plays = df[df["ticker"] != "MARKET"].copy()
    plays["market_regime"] = plays["date"].map(market).fillna("")
    plays["structure"] = plays["play"].map(play_structure)
    plays["tier"] = [ladder_tier(s, m) for s, m
                     in zip(plays["structure"], plays["market_regime"])]
    plays["is_credit"] = plays["structure"].isin(CREDIT)
    plays["is_bear"] = plays["structure"].isin(BEARISH)
    plays["mech_cell"] = plays["mech_cell"].fillna("NONE").astype(str)
    return plays


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------
def standardised_share(df: pd.DataFrame, mask: pd.Series, weights: dict) -> float:
    """Share of `mask`, reweighted to the v4 mech_cell mix (direct standardisation).

    Without this, a v3 book drawn mostly from L-VOL dates and a v4 book drawn
    mostly from BEAR_HE dates would differ on every measure for reasons that
    have nothing to do with the prompt change.
    """
    num = den = 0.0
    for cell, w in weights.items():
        sub = df[df["mech_cell"] == cell]
        if len(sub) == 0:
            continue
        num += w * mask[sub.index].mean()
        den += w
    return num / den if den else np.nan


def two_prop_test(k3, n3, k4, n4) -> tuple[float, float]:
    """Pooled two-proportion z-test -> (z, two-sided p). NaN when degenerate."""
    if min(n3, n4) == 0:
        return np.nan, np.nan
    p = (k3 + k4) / (n3 + n4)
    se = np.sqrt(p * (1 - p) * (1 / n3 + 1 / n4))
    if se == 0:
        return 0.0, 1.0
    z = (k4 / n4 - k3 / n3) / se
    return z, 2 * (1 - stats.norm.cdf(abs(z)))


def report_binary(name, v3, v4, mask3, mask4, weights) -> bool:
    """One binary-share test. Returns True if it FIRES (p < ALPHA)."""
    k3, n3 = int(mask3.sum()), len(v3)
    k4, n4 = int(mask4.sum()), len(v4)
    z, p = two_prop_test(k3, n3, k4, n4)
    s3 = standardised_share(v3, mask3, weights)
    s4 = standardised_share(v4, mask4, weights)
    fires = bool(p == p and p < ALPHA)
    print(f"\n  {name}")
    print(f"    raw           v3 {k3:>5}/{n3:<5} = {k3/n3:6.1%}    "
          f"v4 {k4:>4}/{n4:<4} = {k4/n4 if n4 else float('nan'):6.1%}")
    print(f"    standardised  v3 {s3:6.1%}                v4 {s4:6.1%}"
          f"     (to v4's mech_cell mix)")
    print(f"    two-proportion z = {z:+.2f}, p = {p:.4f}   "
          f"{'*** SHIFT' if fires else 'within noise'}")
    return fires


def report_categorical(name, v3, v4, col, levels) -> bool:
    """Chi-square over a categorical mix. Returns True if it FIRES."""
    tab = np.array([[int((v3[col] == lv).sum()) for lv in levels],
                    [int((v4[col] == lv).sum()) for lv in levels]], dtype=float)
    keep = tab.sum(axis=0) > 0
    tab = tab[:, keep]
    kept = [lv for lv, k in zip(levels, keep) if k]
    print(f"\n  {name}")
    print(f"    {'level':<20} {'v3':>14} {'v4':>14}")
    for j, lv in enumerate(kept):
        print(f"    {lv:<20} {tab[0, j]:>6.0f} ({tab[0, j]/tab[0].sum():5.1%}) "
              f"{tab[1, j]:>6.0f} ({tab[1, j]/tab[1].sum() if tab[1].sum() else float('nan'):5.1%})")
    if tab.shape[1] < 2 or tab[1].sum() == 0:
        print("    chi-square: not computable")
        return False
    chi2, p, _, exp = stats.chi2_contingency(tab)
    thin = (exp < 5).any()
    fires = bool(p < ALPHA)
    print(f"    chi2 = {chi2:.2f}, p = {p:.4f}   "
          f"{'*** SHIFT' if fires else 'within noise'}"
          f"{'   [thin cells: expected count < 5, p is approximate]' if thin else ''}")
    return fires


def report_plays_per_day(v3, v4) -> bool:
    a = v3.groupby("date").size().values
    b = v4.groupby("date").size().values
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    fires = bool(p < ALPHA)
    print("\n  3. plays per day")
    print(f"    v3  n={len(a):>3} dates  median {np.median(a):.1f}  mean {a.mean():.2f}")
    print(f"    v4  n={len(b):>3} dates  median {np.median(b):.1f}  mean {b.mean():.2f}")
    print(f"    Mann-Whitney U = {u:.0f}, p = {p:.4f}   "
          f"{'*** SHIFT' if fires else 'within noise'}")
    return fires


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--v3-csv", type=Path, default=None)
    ap.add_argument("--v4-csv", type=Path, default=None)
    args = ap.parse_args()

    # The vN_ rename is in-place, so BOTH eras export as "AnalysisClaude" unless
    # the operator renames the file. Try the explicit name first, fall back to
    # the bare one, and print what resolved — the era guard below catches the
    # case where both land on the same book.
    v3_csv = args.v3_csv or _resolve("analysis - v3_AnalysisClaude.csv")
    v4_csv = args.v4_csv or _resolve("analysis - v4_AnalysisClaude.csv")

    a, b = load(v3_csv), load(v4_csv)
    era_a, era_b = detect_era(pd.read_csv(v3_csv, nrows=1)), \
        detect_era(pd.read_csv(v4_csv, nrows=1))
    args.v3_csv, args.v4_csv = v3_csv, v4_csv

    print("=" * 74)
    print("v4 EMISSION-COMPOSITION BRIDGE")
    print("=" * 74)
    print(f"  --v3-csv  {args.v3_csv.name}   detected era: {era_a}   "
          f"{len(a)} plays / {a['date'].nunique()} dates")
    print(f"  --v4-csv  {args.v4_csv.name}   detected era: {era_b}   "
          f"{len(b)} plays / {b['date'].nunique()} dates")

    # Era detection is a guard, not a formality: after the in-place vN_ rename
    # both exports are called "AnalysisClaude" and are trivially swapped.
    if era_a != "v3" or era_b != "v4":
        print(f"\nABORT: expected v3 then v4, got {era_a} then {era_b}.")
        print("  v3 exports carry score_flow/score_dealer; v4 exports do not.")
        print("  Re-export, or swap --v3-csv/--v4-csv. Refusing to compare a")
        print("  book against itself and call the null a validation.")
        return 3

    n_dates = b["date"].nunique()
    if n_dates < MIN_V4_DATES:
        print(f"\nGATE NOT MET — v4 has {n_dates} of {MIN_V4_DATES} required dates.")
        print(f"  {MIN_V4_DATES - n_dates} more to go; v4 accrues ~1 date/day from"
              " the normal cadence,")
        print(f"  so roughly {MIN_V4_DATES - n_dates} trading days"
              " (~4 weeks from a standing start).")
        print("\n  This is the pre-registered gate working, not a failure. Do not")
        print("  lower MIN_V4_DATES to make it run — the threshold was fixed")
        print("  before any v4 result existed.")
        print("\n  Interim posture (also pre-registered): deploy under the v3")
        print("  rules in config/deployment-rules.md, unchanged.")
        return 2

    # Restrict both eras to the mech_cells v4 actually visited, and weight v3
    # by v4's mix so regime composition cannot masquerade as behaviour.
    weights = b["mech_cell"].value_counts().to_dict()
    cells = set(weights)
    a = a[a["mech_cell"].isin(cells)]
    print(f"\n  mech_cell match on {sorted(cells)}")
    print(f"  v3 restricted to {len(a)} plays / {a['date'].nunique()} dates")
    missing = sorted({"LVOL", "BEAR_HE", "RB_EVOL"} - cells)
    if missing:
        print(f"  NOT REPRESENTED in v4: {missing} — the escape hatch in the"
              " 08-12 deviation")
        print("  allows <=5 targeted re-runs to fill a missing cell.")

    print("\n" + "-" * 74)
    print(f"FIVE PRE-REGISTERED TESTS   (alpha = {ALPHA}, no multiplicity correction)")
    print("-" * 74)

    fired = {
        "1. structure mix": report_categorical(
            "1. structure mix", a, b, "structure", list(STRUCTURES)),
        "2. credit share": report_binary(
            "2. credit share", a, b, a["is_credit"], b["is_credit"], weights),
        "3. plays per day": report_plays_per_day(a, b),
        "4. bear share": report_binary(
            "4. bear share", a, b, a["is_bear"], b["is_bear"], weights),
        "5. ladder tier mix": report_categorical(
            "5. ladder tier mix", a, b, "tier", ["A", "B", "C", "VETO"]),
    }

    print("\n" + "=" * 74)
    hits = [k for k, v in fired.items() if v]
    if hits:
        print("VERDICT: LADDER UNVALIDATED ON v4")
        print(f"  Shifted: {', '.join(hits)}")
        print("  Per the pre-registration: keep deploying under the v3 rules,")
        print("  flag every v4 row in current.md, and do NOT re-derive the")
        print("  ladder on v4 rows until there are enough of them to mean")
        print("  anything.")
    else:
        print("VERDICT: LADDER CARRIES FORWARD TO v4")
        print("  No large composition shift detected on any of the five tests.")
        print("  Record it and deploy unchanged.")
    print("\n  Reminder, pre-committed: this is powered to catch a shift the")
    print("  size of the v2->v3 credit jump and nothing subtler. A null means")
    print('  "no large shift detected", never "the populations are the same".')
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
