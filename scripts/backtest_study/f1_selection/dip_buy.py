"""dip_buy — do Tier A/B positions do better when SPY closes below its 50-day SMA?

REGISTERED 2026-10-12, accepted by default the same day:
research/pre-registrations/f1_selection/dip_buy.md. Every floor, constant and
verdict word below is that file's. Read it before changing anything here.

WHY IT EXISTS
-------------
The 2026-10-12 exploratory read (research/current.md) found one rule that
ranked high in both eras' PBO read: Tier A/B picks taken on dates when SPY
closed below its 50-day SMA. It was picked post hoc from 28 candidate rules,
so in-sample data cannot confirm it. This module prints the in-sample eras as
DESCRIPTIVE CONTEXT, labelled post hoc, and grades ONE population: signal
dates on or after the holdout seal's start (`lib/era.py::SEAL_START`).

WHAT IT COMPUTES
----------------
Population. `load_book()` at its defaults (era from STUDY_ERA, real + tweak,
bs excluded). Rows with no stored R or `fill_trusted` False are dropped and
counted. R is the stored `realized_pnl_pct`, net of `cost_total`.

Tier. `scripts/journal/lib/mapping.py::ladder_tier` with the row's delta, the
one encoding of deployment-rules §1-§3. Never the loader's port.

Dip label. `lib/mech_regime.py::MechLabeler.below_sma`: SPY's close on the
last trading day at or before the signal date, strictly below its 50-day SMA.
The same table and SMA the shipped `mech_cell` uses. A date the table does
not cover, or with no 50-day runway, is unlabelled, dropped and counted.

PRIMARY (forward only). Among Tier A/B positions: meanR(below) minus
meanR(above). The CI resamples each arm's signal dates independently, with
replacement (10,000 draws). PF is printed beside it, never graded.

    SUPPORTED   both arms past the floor, CI excludes 0, positive
    CONTRARY    both arms past the floor, CI excludes 0, negative
    NULL        both arms past the floor, CI spans 0
    STILL-OPEN  either arm short of its floor (30 signal dates, 60 positions)

Secondaries, printed both ways and never graded: the score_total tie-break
within tier, ascending vs descending; cpir above vs at-or-below the registered
in-sample median 0.92. Deployment arm: ladder top-3/day against dip-gated
top-3/day (below-SMA dates only), each against a random bull_call_spread null.

Holdout seal. This study is NOT a named sealed reader. It reads the book only
through `load_book()` without `sealed_read`, so every signal date on or after
SEAL_START is withheld until `era.SEAL_LIFTED` is set by the unseal read. Until
then the forward population is empty and the verdict is STILL-OPEN. The only
forward figure printed meanwhile is a census of trading days with SPY below
its SMA, read from the SPY table, which holds no outcome.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run dip_buy
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import MechLabeler, compute_mech_table  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib.book import MECH_TABLE_CSV, load_book  # noqa: E402
from scripts.journal.lib.mapping import ladder_tier as mapping_ladder_tier  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/dip_buy.md"
ACCEPTED = "2026-10-12"

# --- registered constants (the registration, not defaults) -------------------
MIN_DATES = 30            # per arm, forward: signal dates
MIN_POS = 60              # per arm, forward: positions
CPIR_MEDIAN = 0.92        # v4 in-sample Tier A/B median, fixed 2026-10-12
TOP_K = 3
BOOT_N = 10_000
SEED = 20260811           # protocol's seed
NULL_SIMS = 10_000
NULL_SEED = 42
FORWARD_ERA = "v4"        # a prompt-version bump freezes the grade at the last v4 date
REPLICATION_ERA = "v3"
BELOW, ABOVE = "below", "above"
TIERS = ("A", "B")
TIER_RANK = {"A": 2, "B": 1}

# The era refusals raised inside load_book (lib/era.py).
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}


# ════════════════════════════════════════════════════════════════════════════
# Row preparation
# ════════════════════════════════════════════════════════════════════════════

def _float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def tier_of(rec) -> str:
    """VETO / A / B / C from the one production encoding."""
    dte = _float(rec.get("dte"))
    tier, _partial, _why = mapping_ladder_tier(
        rec["structure"], rec.get("market_regime") or "",
        dte_proxy=dte if dte is not None else float("nan"),
        short_leg_delta=_float(rec.get("delta")))
    return tier


def dip_label(labeler: MechLabeler, d: str) -> str | None:
    """`below` / `above` for signal date `d`, or None when it cannot be labelled.

    None when the table does not reach `d` (an as-of answer would label a new
    date from a stale close) or when `d` has no 50-day runway.
    """
    if not labeler.covers(d):
        return None
    flag, _mapped = labeler.below_sma(d)
    if flag is None:
        return None
    return BELOW if flag else ABOVE


def prepare(recs, labeler) -> tuple[list[dict], Counter]:
    """Non-veto rows with a stored R, a trusted fill and a dip label."""
    out, counts = [], Counter()
    for r in recs:
        if r.get("R") is None:
            counts["R_missing"] += 1
            continue
        if not r.get("fill_trusted", True):
            counts["fill_untrusted"] += 1
            continue
        tier = tier_of(r)
        if tier == "VETO":
            counts["veto"] += 1
            continue
        dip = dip_label(labeler, r["date"])
        if dip is None:
            counts["dip_unlabelled"] += 1
            continue
        if tier != r.get("tier"):
            counts["tier_differs_from_loader_port"] += 1
        out.append(dict(date=str(r["date"])[:10], ticker=r["ticker"],
                        structure=r["structure"], tier=tier, R=float(r["R"]),
                        score=_float(r.get("score_total")), cpir=_float(r.get("cpir")),
                        dip=dip))
    return out, counts


def split_window(rows, forward_from: str):
    """(in-sample, forward): forward is every signal date on or after `forward_from`."""
    ins = [r for r in rows if r["date"] < forward_from]
    fwd = [r for r in rows if r["date"] >= forward_from]
    return ins, fwd


def tier_ab(rows):
    return [r for r in rows if r["tier"] in TIERS]


def arm(rows, dip: str):
    return [r for r in rows if r["dip"] == dip]


# ════════════════════════════════════════════════════════════════════════════
# Statistics
# ════════════════════════════════════════════════════════════════════════════

def _by_date(rows):
    """(sum R, count, sum of gains, sum of |losses|) per signal date, as arrays."""
    acc: dict[str, list[float]] = {}
    for r in rows:
        a = acc.setdefault(r["date"], [0.0, 0, 0.0, 0.0])
        a[0] += r["R"]
        a[1] += 1
        if r["R"] > 0:
            a[2] += r["R"]
        elif r["R"] < 0:
            a[3] -= r["R"]
    v = np.array(list(acc.values()), dtype=float).reshape(-1, 4)
    return v[:, 0], v[:, 1], v[:, 2], v[:, 3]


def _boot_idx(rng, n_dates: int, n: int):
    return rng.integers(0, n_dates, (n, n_dates))


def boot_mean(rows, n: int = BOOT_N, seed: int = SEED):
    """(meanR, lo, hi): date-clustered bootstrap of the pooled mean."""
    if not rows:
        return (float("nan"),) * 3
    s, c, _, _ = _by_date(rows)
    point = s.sum() / c.sum()
    if len(s) < 2:
        return (point, float("nan"), float("nan"))
    idx = _boot_idx(np.random.default_rng(seed), len(s), n)
    m = s[idx].sum(1) / c[idx].sum(1)
    lo, hi = np.percentile(m, [2.5, 97.5])
    return (float(point), float(lo), float(hi))


def boot_pf(rows, n: int = BOOT_N, seed: int = SEED):
    """(PF, lo, hi): date-clustered; a draw with no loss is dropped, never infinite."""
    if not rows:
        return (None, float("nan"), float("nan"))
    _, _, g, ls = _by_date(rows)
    point = float(g.sum() / ls.sum()) if ls.sum() > 0 else None
    if len(g) < 2:
        return (point, float("nan"), float("nan"))
    idx = _boot_idx(np.random.default_rng(seed), len(g), n)
    num, den = g[idx].sum(1), ls[idx].sum(1)
    ok = den > 0
    if not ok.any():
        return (point, float("nan"), float("nan"))
    lo, hi = np.percentile(num[ok] / den[ok], [2.5, 97.5])
    return (point, float(lo), float(hi))


def boot_diff(below, above, n: int = BOOT_N, seed: int = SEED):
    """(diff, lo, hi) of meanR(below) - meanR(above).

    The arms hold disjoint dates (the label is per date), so each arm's dates
    are resampled independently, with replacement, in the same draw.
    """
    if not below or not above:
        return (float("nan"),) * 3
    sb, cb, _, _ = _by_date(below)
    sa, ca, _, _ = _by_date(above)
    point = sb.sum() / cb.sum() - sa.sum() / ca.sum()
    if len(sb) < 2 or len(sa) < 2:
        return (float(point), float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    ib, ia = _boot_idx(rng, len(sb), n), _boot_idx(rng, len(sa), n)
    d = sb[ib].sum(1) / cb[ib].sum(1) - sa[ia].sum(1) / ca[ia].sum(1)
    lo, hi = np.percentile(d, [2.5, 97.5])
    return (float(point), float(lo), float(hi))


def n_dates(rows) -> int:
    return len({r["date"] for r in rows})


def verdict(below, above, lo: float, hi: float,
            min_dates: int = MIN_DATES, min_pos: int = MIN_POS) -> str:
    """The registered grammar. Floors first; a CI that is not a number is not a verdict."""
    for side in (below, above):
        if n_dates(side) < min_dates or len(side) < min_pos:
            return "STILL-OPEN"
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "STILL-OPEN"
    if lo > 0:
        return "SUPPORTED"
    if hi < 0:
        return "CONTRARY"
    return "NULL"


# ════════════════════════════════════════════════════════════════════════════
# The deployment-shaped arm
# ════════════════════════════════════════════════════════════════════════════

def rank_key(tiebreak: str):
    """Tier first (A over B), then score_total in the given direction.

    A row with no score sorts after every scored row of its tier, either way.
    Ties after that keep load order (Python's sort is stable).
    """
    if tiebreak not in ("desc", "asc"):
        raise ValueError(tiebreak)
    sign = -1.0 if tiebreak == "desc" else 1.0

    def key(r):
        s = r.get("score")
        return (-TIER_RANK.get(r["tier"], 0), s is None, sign * s if s is not None else 0.0)
    return key


def top_k(rows, tiebreak: str, k: int = TOP_K, gate: str | None = None):
    """The k Tier A/B rows each date deploys; `gate=BELOW` deploys on below-SMA dates only."""
    by: dict[str, list] = {}
    for r in rows:
        if r["tier"] not in TIERS or (gate is not None and r["dip"] != gate):
            continue
        by.setdefault(r["date"], []).append(r)
    key = rank_key(tiebreak)
    out = []
    for d in sorted(by):
        out.extend(sorted(by[d], key=key)[:k])
    return out


def per_date_mean(rows) -> float:
    if not rows:
        return float("nan")
    s, c, _, _ = _by_date(rows)
    return float(np.mean(s / c))


def random_bcs_null(rows, dates, picked_per_date: dict, sims: int = NULL_SIMS,
                    seed: int = NULL_SEED):
    """meanR of `sims` random books: on each date, as many random non-veto
    bull_call_spreads as the ladder picked that date (fewer if the pool is short)."""
    rng = np.random.default_rng(seed)
    pool: dict[str, list[float]] = {}
    for r in rows:
        if r["structure"] == "bull_call_spread" and r["date"] in dates:
            pool.setdefault(r["date"], []).append(r["R"])
    tot, cnt = np.zeros(sims), 0
    for d in sorted(pool):
        vals = np.array(pool[d])
        k = min(picked_per_date.get(d, 0), len(vals))
        if k == 0:
            continue
        if k == len(vals):
            tot += vals.sum()
        else:
            idx = np.argpartition(rng.random((sims, len(vals))), k, axis=1)[:, :k]
            tot += vals[idx].sum(1)
        cnt += k
    return tot / cnt if cnt else np.full(sims, np.nan)


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def _f(x, fmt="+.3f"):
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def arm_line(label: str, rows) -> str:
    m, lo, hi = boot_mean(rows)
    p, plo, phi = boot_pf(rows)
    return (f"  {label:<26} n={len(rows):4d}  dates={n_dates(rows):3d}  meanR={_f(m)} "
            f"[{_f(lo)}, {_f(hi)}]  PF={_f(p, '.2f')} [{_f(plo, '.2f')}, {_f(phi, '.2f')}]")


def diff_line(label: str, below, above) -> str:
    d, lo, hi = boot_diff(below, above)
    return f"  {label:<26} below - above = {_f(d)}  CI95 [{_f(lo)}, {_f(hi)}]"


def contrast_block(rows, title: str):
    ab = tier_ab(rows)
    print(f"\n-- {title}")
    for lbl, sub in (("Tier A+B", ab), ("Tier A", [r for r in ab if r["tier"] == "A"]),
                     ("Tier B", [r for r in ab if r["tier"] == "B"])):
        b, a = arm(sub, BELOW), arm(sub, ABOVE)
        print(arm_line(f"{lbl}, below SMA", b))
        print(arm_line(f"{lbl}, above SMA", a))
        print(diff_line(lbl, b, a))


def secondary_block(rows, title: str):
    ab = tier_ab(rows)
    print(f"\n-- {title}: cpir split at the registered median {CPIR_MEDIAN} (not graded)")
    hi_c = [r for r in ab if r["cpir"] is not None and r["cpir"] > CPIR_MEDIAN]
    lo_c = [r for r in ab if r["cpir"] is not None and r["cpir"] <= CPIR_MEDIAN]
    print(f"  rows with no cpir: {sum(1 for r in ab if r['cpir'] is None)}")
    for lbl, sub in ((f"cpir > {CPIR_MEDIAN}", hi_c), (f"cpir <= {CPIR_MEDIAN}", lo_c)):
        print(arm_line(f"{lbl}, below", arm(sub, BELOW)))
        print(arm_line(f"{lbl}, above", arm(sub, ABOVE)))
        print(diff_line(lbl, arm(sub, BELOW), arm(sub, ABOVE)))


def deployment_block(rows, title: str):
    print(f"\n-- {title}: deployment arm, top-{TOP_K}/day, Tier A/B (not graded)")
    for tb in ("desc", "asc"):
        print(f"  tie-break: score_total {'descending' if tb == 'desc' else 'ascending'} within tier")
        for lbl, gate in (("ladder, every date", None), ("dip-gated, below only", BELOW)):
            picks = top_k(rows, tb, gate=gate)
            m, lo, hi = boot_mean(picks)
            total = sum(r["R"] for r in picks)
            per_d = Counter(r["date"] for r in picks)
            null = random_bcs_null(rows, set(per_d), per_d)
            pct = float(np.mean(null < m)) * 100 if picks and np.isfinite(null).all() else float("nan")
            print(f"    {lbl:<22} n={len(picks):4d} dates={len(per_d):3d}  total R={_f(total, '+.1f')}  "
                  f"meanR={_f(m)} [{_f(lo)}, {_f(hi)}]  per-date meanR={_f(per_date_mean(picks))}")
            print(f"    {'':<22} random bull_call_spread null, same dates and counts: median "
                  f"{_f(float(np.nanmedian(null)))}  [{_f(float(np.nanpercentile(null, 2.5)))}, "
                  f"{_f(float(np.nanpercentile(null, 97.5)))}]  ladder at pct {_f(pct, '.1f')}")
        top_below = [r for r in top_k(rows, tb) if r["dip"] == BELOW]
        top_above = [r for r in top_k(rows, tb) if r["dip"] == ABOVE]
        print("    " + diff_line("contrast on the top-3 picks", top_below, top_above).strip())


def composition(rows, title: str):
    dates = {}
    for r in rows:
        dates[r["date"]] = r["dip"]
    nb = sum(1 for v in dates.values() if v == BELOW)
    share = nb / len(dates) if dates else float("nan")
    print(f"\n-- {title}: signal dates with a labelled non-veto row: {len(dates)}; "
          f"SPY below its 50-day SMA on {nb} ({_f(share * 100, '.1f')}%)")
    return share, len(dates)


def era_context(era_name: str, rows, counts, diag):
    print(f"\nera {diag['era']}: {len(rows)} labelled non-veto rows, "
          f"{len(tier_ab(rows))} Tier A/B; dropped {dict(counts)}")
    share, _ = composition(rows, f"{diag['era']} in-sample")
    contrast_block(rows, f"{diag['era']} in-sample, PRIMARY contrast, POST HOC (descriptive)")
    secondary_block(rows, f"{diag['era']} in-sample")
    deployment_block(rows, f"{diag['era']} in-sample")
    return share


def forward_census(seal_start: str) -> tuple[int, int]:
    """Trading days on or after the seal start with SPY below its SMA. No outcome."""
    table = [r for r in compute_mech_table(MECH_TABLE_CSV) if r["date"] >= seal_start]
    return len(table), sum(1 for r in table if r["spy_below_sma"])


def main() -> int:
    seal_start = era_mod.SEAL_START
    labeler = MechLabeler.from_csv(MECH_TABLE_CSV)
    print("dip_buy — Tier A/B meanR when SPY is below vs above its 50-day SMA")
    print(f"registration: {REGISTRATION} (accepted by default {ACCEPTED})")
    print(f"dip label: lib/mech_regime.py MechLabeler.below_sma, table {MECH_TABLE_CSV.name}, "
          f"ends {labeler.last_date}")
    print(f"forward population: signal dates >= {seal_start} (lib/era.py SEAL_START), era "
          f"{FORWARD_ERA}; seal lifted: {era_mod.SEAL_LIFTED or 'no'}")
    print(f"floors per arm, forward: {MIN_DATES} signal dates and {MIN_POS} positions")

    recs, diag = load_book()
    rows, counts = prepare(recs, labeler)
    ins, fwd = split_window(rows, seal_start)

    print("\n" + "=" * 78)
    print("IN-SAMPLE CONTEXT — POST HOC, DESCRIPTIVE, NOT A VERDICT")
    print("=" * 78)
    print("The rule was picked from 28 candidates after these dates were read "
          "(research/current.md 2026-10-12).")
    share = era_context(diag["era"], ins, counts, diag)

    if diag["era"] != REPLICATION_ERA:
        try:
            recs3, diag3 = load_book(era=REPLICATION_ERA)
        except SystemExit as exc:
            print(f"\n{REPLICATION_ERA} context not loaded: era refusal, exit {exc.code}")
        else:
            rows3, counts3 = prepare(recs3, labeler)
            ins3, _ = split_window(rows3, seal_start)
            era_context(REPLICATION_ERA, ins3, counts3, diag3)

    print("\n" + "=" * 78)
    print("FORWARD — the graded population")
    print("=" * 78)
    days, below_days = forward_census(seal_start)
    print(f"census, SPY table only: {days} trading days since {seal_start}, "
          f"{below_days} with SPY below its 50-day SMA")
    if math.isfinite(share) and share > 0:
        print(f"expected wait: at the in-sample below-SMA share ({_f(share * 100, '.1f')}% of "
              f"signal dates) the below arm needs about {math.ceil(MIN_DATES / share)} "
              f"forward signal dates to reach {MIN_DATES}, before option expiry")
    graded = diag["era"] == FORWARD_ERA
    held = diag.get("seal", {})
    if not era_mod.SEAL_LIFTED:
        print(f"SEALED: load_book withheld {held.get('rows', 0)} rows on {held.get('dates', 0)} "
              f"signal dates >= {seal_start}. This study is not a named reader; its forward read "
              "waits for the unseal (holdout_seal.md).")
    if not graded:
        print(f"era {diag['era']} is not the registered forward era {FORWARD_ERA}: not graded")
    fab = tier_ab(fwd) if graded else []
    fb, fa = arm(fab, BELOW), arm(fab, ABOVE)
    print(arm_line("Tier A+B, below SMA", fb))
    print(arm_line("Tier A+B, above SMA", fa))
    _d, lo, hi = boot_diff(fb, fa)
    print(diff_line("Tier A+B", fb, fa))
    v = verdict(fb, fa, lo, hi)
    if fwd and graded:
        secondary_block(fwd, "forward")
        deployment_block(fwd, "forward")

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    print("  In-sample v4 and v3: post hoc context only. They carry no verdict.")
    print(f"  forward below arm: {n_dates(fb)} of {MIN_DATES} dates, {len(fb)} of {MIN_POS} positions")
    print(f"  forward above arm: {n_dates(fa)} of {MIN_DATES} dates, {len(fa)} of {MIN_POS} positions")
    print(f"  >>> dip_buy PRIMARY (forward, Tier A+B, below - above): {v} <<<")
    if v == "STILL-OPEN" and not era_mod.SEAL_LIFTED:
        print("  STILL-OPEN because the forward dates are sealed and no arm has reached its floor.")
    print("  The verdict of record is the first run printing a token other than STILL-OPEN; "
          "later runs are descriptive (dip_buy.md).")
    print("  Nothing ships from this study. A forward SUPPORTED lets the operator consider "
          "a deployment-rules change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
