"""regime_map — in which market conditions does each ladder tier make or lose money?

REGISTERED 2026-10-12, accepted by default the same day, before the first run:
research/pre-registrations/f1_selection/regime/regime_map.md. Every floor,
label family and verdict word below is that file's. Read it before changing
anything here.

WHAT IT COMPUTES
----------------
A descriptive map, not a selection rule. Each ladder tier (A, B, C, VETO; A+B
printed beside them) is crossed with each of six market labels, one family at
a time: mech_cell, mech direction, mech vol, SPY vs its 50-day SMA, the model's
regime direction and the model's vol. Every cell prints n, dates, win%, PF,
meanR with a date-clustered CI, MFE/MAE, give-back, capture and dollars.

Verdict per cell (registered): POSITIVE / NEGATIVE when past the floors (30
positions, 10 dates) with BH q < 0.05 across the era's whole map; NULL past the
floors otherwise; THIN below either floor. A cell is REPLICATED when v4 (net)
and v3 (gross; v3 has no cost columns) print the same POSITIVE or NEGATIVE
token. The raw-CI token and the gross-vs-gross replication print beside them.

Population: `load_book()` at its defaults; rows with no R or an untrusted fill
are dropped and counted. Tiers come from `mapping.ladder_tier` via
`dip_buy.tier_of`. Labels come from `lib/mech_regime.py::MechLabeler` and the
loader's parse of `market_regime`.

Forward: cells REPLICATED in-sample are read on v4 signal dates from
`era.SEAL_START`, once the seal lifts. Until then they print STILL-OPEN.

Nothing ships from this study. Run:

    python -m scripts.backtest_study run regime_map
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.mech_regime import MechLabeler  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark.ticker_class import cost_pct_of  # noqa: E402
from scripts.backtest_study.f1_selection.regime import dip_buy as DB  # noqa: E402
from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib.book import MECH_TABLE_CSV, load_book  # noqa: E402

REGISTRATION = "research/pre-registrations/f1_selection/regime/regime_map.md"
ACCEPTED = "2026-10-12"

# --- registered constants ------------------------------------------------------
MIN_POS = 30
MIN_DATES = 10
BH_Q = 0.05
BOOT_N = 10_000
SEED = 20260811
STRESS = (("2025-03-01", "2025-04-30"), ("2026-02-01", "2026-04-30"))
FORWARD_ERA = "v4"
REPLICATION_ERA = "v3"

GRADED_TIERS = ("A", "B", "C", "VETO")
PRINTED_TIERS = GRADED_TIERS + ("A+B",)

FAMILIES = {
    "RM-CELL": ("mech_cell", ("LVOL", "BEAR_HE", "RB_EVOL", "NONE")),
    "RM-MDIR": ("mech direction", ("BULL", "BEAR", "RANGE")),
    "RM-MVOL": ("mech vol", ("L-VOL", "H-VOL", "E-VOL")),
    "RM-SMA": ("SPY vs 50-day SMA", ("below", "above")),
    "RM-RDIR": ("model regime direction", ("BULL", "BEAR", "RANGE")),
    "RM-RVOL": ("model vol", ("L-VOL", "H-VOL", "E-VOL", "C-VOL")),
}

POSITIVE, NEGATIVE, NULL, THIN = "POSITIVE", "NEGATIVE", "NULL", "THIN"

DESIGNED_REFUSAL_EXIT_CODES = {2, 3}


# ════════════════════════════════════════════════════════════════════════════
# Labels and population
# ════════════════════════════════════════════════════════════════════════════

def mech_labels(labeler: MechLabeler, d: str) -> dict:
    """RM-CELL / RM-MDIR / RM-MVOL / RM-SMA for signal date `d`; None = unlabelled.

    A date past the table's end is unlabelled in every mech family: the as-of
    rule would otherwise label it from a stale close.
    """
    out = {"RM-CELL": None, "RM-MDIR": None, "RM-MVOL": None, "RM-SMA": None}
    if not labeler.covers(d):
        return out
    direction, vol, ok, _ = labeler.label(d)
    if ok:
        out["RM-CELL"] = labeler.cell(d) or "NONE"
        out["RM-MDIR"] = direction
        out["RM-MVOL"] = vol
    out["RM-SMA"] = DB.dip_label(labeler, d)
    return out


def prepare(recs, labeler, has_cost: bool = True) -> tuple[list[dict], Counter]:
    """Every tiered row (VETO kept) with a stored R and a trusted fill, plus labels."""
    out, counts = [], Counter()
    for r in recs:
        if r.get("R") is None:
            counts["R_missing"] += 1
            continue
        if not r.get("fill_trusted", True):
            counts["fill_untrusted"] += 1
            continue
        R = float(r["R"])
        cost = cost_pct_of(r) if (has_cost and r.get("t") is not None) else 0.0
        labels = mech_labels(labeler, r["date"])
        labels["RM-RDIR"] = r.get("model_dir") or None
        labels["RM-RVOL"] = r.get("model_vol") or None
        mfe = r.get("mfe")
        out.append(dict(date=str(r["date"])[:10], ticker=r.get("ticker"),
                        structure=r.get("structure"), tier=DB.tier_of(r),
                        R=R, Rg=R + cost, R_dol=r.get("R_dol"),
                        mfe=float(mfe) if mfe is not None else None,
                        mae=float(r["mae"]) if r.get("mae") is not None else None,
                        labels=labels))
    return out, counts


def in_tier(row, tier: str) -> bool:
    return row["tier"] in ("A", "B") if tier == "A+B" else row["tier"] == tier


def in_stress(d: str) -> bool:
    return any(a <= d <= b for a, b in STRESS)


# ════════════════════════════════════════════════════════════════════════════
# Statistics
# ════════════════════════════════════════════════════════════════════════════

def boot_draws(rows, key: str = "R", n: int = BOOT_N, seed: int = SEED):
    """(point meanR, draws): date-clustered bootstrap of the pooled mean."""
    if not rows:
        return float("nan"), np.array([])
    acc: dict[str, list[float]] = {}
    for r in rows:
        a = acc.setdefault(r["date"], [0.0, 0])
        a[0] += r[key]
        a[1] += 1
    v = np.array(list(acc.values()), dtype=float)
    s, c = v[:, 0], v[:, 1]
    point = float(s.sum() / c.sum())
    if len(s) < 2:
        return point, np.array([])
    idx = np.random.default_rng(seed).integers(0, len(s), (n, len(s)))
    return point, s[idx].sum(1) / c[idx].sum(1)


def boot_p(draws: np.ndarray) -> float:
    """Two-sided percentile-bootstrap p for a mean of 0 (registered formula)."""
    if not len(draws):
        return float("nan")
    return float(min(1.0, 2 * min(np.mean(draws <= 0), np.mean(draws >= 0))))


def bh_q(pvals) -> list[float]:
    """Benjamini-Hochberg adjusted q-values, same order as `pvals`. NaN stays NaN."""
    p = np.asarray(pvals, dtype=float)
    q = np.full(len(p), np.nan)
    ok = np.where(np.isfinite(p))[0]
    m = len(ok)
    if not m:
        return q.tolist()
    order = ok[np.argsort(p[ok], kind="stable")]
    ranked = p[order] * m / np.arange(1, m + 1)
    q[order] = np.minimum(1.0, np.minimum.accumulate(ranked[::-1])[::-1])
    return q.tolist()


def n_dates(rows) -> int:
    return len({r["date"] for r in rows})


def past_floors(n: int, dates: int, min_pos: int = MIN_POS, min_dates: int = MIN_DATES) -> bool:
    return n >= min_pos and dates >= min_dates


def verdict(n: int, dates: int, mean: float, q: float,
            min_pos: int = MIN_POS, min_dates: int = MIN_DATES, alpha: float = BH_Q) -> str:
    """The registered grammar: floors first, then BH q, then sign."""
    if not past_floors(n, dates, min_pos, min_dates):
        return THIN
    if not (math.isfinite(q) and math.isfinite(mean)) or q >= alpha:
        return NULL
    return POSITIVE if mean > 0 else NEGATIVE if mean < 0 else NULL


def raw_token(n: int, dates: int, lo: float, hi: float) -> str:
    """The printed alternative: the CI alone, no correction."""
    if not past_floors(n, dates):
        return THIN
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return NULL
    return POSITIVE if lo > 0 else NEGATIVE if hi < 0 else NULL


def replication(v4_token: str, v3_token: str) -> str:
    if v4_token == v3_token and v4_token in (POSITIVE, NEGATIVE):
        return "REPLICATED"
    if {v4_token, v3_token} == {POSITIVE, NEGATIVE}:
        return "CONTRADICTED"
    return "-"


def forward_token(rows, in_sample_token: str, key: str = "R") -> tuple[str, float, float, float]:
    """(token, mean, lo, hi) for one REPLICATED cell on forward dates."""
    mean, draws = boot_draws(rows, key)
    lo, hi = (np.percentile(draws, [2.5, 97.5]) if len(draws) else (float("nan"),) * 2)
    if not past_floors(len(rows), n_dates(rows)) or not len(draws):
        return "STILL-OPEN", mean, float(lo), float(hi)
    ok = lo > 0 if in_sample_token == POSITIVE else hi < 0
    return ("CONFIRMED" if ok else "NOT-CONFIRMED"), mean, float(lo), float(hi)


def cell_stats(rows, key: str = "R") -> dict:
    """Every registered per-cell statistic on `key` ("R" net, "Rg" gross)."""
    n, d = len(rows), n_dates(rows)
    mean, draws = boot_draws(rows, key)
    lo, hi = (np.percentile(draws, [2.5, 97.5]) if len(draws) else (float("nan"),) * 2)
    vals = np.array([r[key] for r in rows], dtype=float)
    gains, losses = vals[vals > 0].sum(), -vals[vals < 0].sum()
    with_mfe = [r for r in rows if r["mfe"] is not None]
    pos_mfe = [r for r in with_mfe if r["mfe"] > 0]
    mae = [r["mae"] for r in rows if r["mae"] is not None]
    dollars = [r["R_dol"] for r in rows if r.get("R_dol") is not None]
    return dict(
        n=n, dates=d, mean=mean, lo=float(lo), hi=float(hi), p=boot_p(draws),
        win=float(np.mean(vals > 0)) if n else float("nan"),
        pf=float(gains / losses) if losses > 0 else (float("inf") if gains > 0 else float("nan")),
        mfe=float(np.mean([r["mfe"] for r in with_mfe])) if with_mfe else float("nan"),
        mae=float(np.mean(mae)) if mae else float("nan"),
        giveback=float(np.mean([r["mfe"] - r[key] for r in with_mfe])) if with_mfe else float("nan"),
        capture=(float(sum(r[key] for r in pos_mfe) / sum(r["mfe"] for r in pos_mfe))
                 if pos_mfe else float("nan")),
        dollars=float(sum(dollars)) if dollars else 0.0,
    )


def build_map(rows, key: str = "R") -> list[dict]:
    """Every tier x family x level cell, with BH q over the graded, non-THIN cells."""
    cells = []
    for fam, (_name, levels) in FAMILIES.items():
        for tier in PRINTED_TIERS:
            for lvl in levels:
                sub = [r for r in rows if in_tier(r, tier) and r["labels"].get(fam) == lvl]
                st = cell_stats(sub, key)
                st.update(family=fam, tier=tier, level=lvl,
                          graded=tier in GRADED_TIERS and past_floors(st["n"], st["dates"]))
                cells.append(st)
    graded = [c for c in cells if c["graded"]]
    for c, q in zip(graded, bh_q([c["p"] for c in graded])):
        c["q"] = q
    for c in cells:
        c.setdefault("q", float("nan"))
        if c["tier"] in GRADED_TIERS:
            c["verdict"] = verdict(c["n"], c["dates"], c["mean"], c["q"])
        else:
            c["verdict"] = "(not graded)"
        c["raw"] = raw_token(c["n"], c["dates"], c["lo"], c["hi"])
    return cells


def cell_key(c) -> tuple:
    return (c["family"], c["tier"], c["level"])


# ════════════════════════════════════════════════════════════════════════════
# Report
# ════════════════════════════════════════════════════════════════════════════

def _f(x, fmt="+.3f"):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    if isinstance(x, float) and math.isinf(x):
        return "inf"
    return format(x, fmt)


def print_map(cells, title: str, graded: bool = True):
    n_graded = sum(1 for c in cells if c["graded"])
    print(f"\n-- {title}")
    print(f"   BH family: {n_graded} graded cells past the floors"
          + ("" if graded else "  (re-cut: tokens printed, not graded)"))
    for fam, (name, _levels) in FAMILIES.items():
        print(f"\n   {fam}  {name}")
        print(f"   {'tier':<5}{'level':<9}{'n':>5}{'dates':>6}{'win':>6}{'PF':>6}{'meanR':>8}"
              f"{'CI95':>18}{'MFE':>7}{'MAE':>7}{'giveb':>7}{'capt':>7}{'$':>10}"
              f"{'p':>7}{'q':>7}  verdict   raw")
        for c in (c for c in cells if c["family"] == fam):
            print(f"   {c['tier']:<5}{c['level']:<9}{c['n']:>5}{c['dates']:>6}"
                  f"{_f(c['win'], '.2f'):>6}{_f(c['pf'], '.2f'):>6}{_f(c['mean']):>8}"
                  f"  [{_f(c['lo'])}, {_f(c['hi'])}]{_f(c['mfe'], '+.2f'):>7}"
                  f"{_f(c['mae'], '+.2f'):>7}{_f(c['giveback'], '+.2f'):>7}"
                  f"{_f(c['capture'], '+.2f'):>7}{_f(c['dollars'], '+.0f'):>10}"
                  f"{_f(c['p'], '.3f'):>7}{_f(c['q'], '.3f'):>7}  {c['verdict']:<9} {c['raw']}")


def tally(cells) -> Counter:
    return Counter(c["verdict"] for c in cells if c["tier"] in GRADED_TIERS)


def replication_block(v4_cells, v3_cells):
    """The registered rule, then the gross-vs-gross alternative; REPLICATED rows listed."""
    by3 = {cell_key(c): c for c in v3_cells}
    out = []
    for c in v4_cells:
        if c["tier"] not in GRADED_TIERS:
            continue
        o = by3.get(cell_key(c))
        if o is None:
            continue
        out.append((c, o, replication(c["verdict"], o["verdict"])))
    return out


def print_replication(rows_net, rows_gross, label_net: str, label_gross: str):
    print(f"\n-- REPLICATION, registered basis: {label_net}")
    tally_ = Counter(r[2] for r in rows_net)
    print(f"   REPLICATED {tally_['REPLICATED']}  CONTRADICTED {tally_['CONTRADICTED']}  "
          f"neither {tally_['-']}  (of {len(rows_net)} graded tier x level cells)")
    print(f"   {'family':<9}{'tier':<6}{'level':<9}{'v4 meanR':>9}{'v4 q':>7} v4 token   "
          f"{'v3 meanR':>9}{'v3 q':>7} v3 token   result")
    for c, o, res in rows_net:
        if res == "-" and c["verdict"] not in (POSITIVE, NEGATIVE) and o["verdict"] not in (POSITIVE, NEGATIVE):
            continue
        print(f"   {c['family']:<9}{c['tier']:<6}{c['level']:<9}{_f(c['mean']):>9}"
              f"{_f(c['q'], '.3f'):>7} {c['verdict']:<10}{_f(o['mean']):>9}"
              f"{_f(o['q'], '.3f'):>7} {o['verdict']:<10} {res}")
    print("   (cells where neither era printed POSITIVE or NEGATIVE are not listed)")
    t2 = Counter(r[2] for r in rows_gross)
    print(f"\n-- REPLICATION, alternative basis (printed, not graded): {label_gross}")
    print(f"   REPLICATED {t2['REPLICATED']}  CONTRADICTED {t2['CONTRADICTED']}  "
          f"neither {t2['-']}")
    for c, o, res in rows_gross:
        if res != "-":
            print(f"   {c['family']:<9}{c['tier']:<6}{c['level']:<9} v4 gross {_f(c['mean'])} "
                  f"{c['verdict']:<9} v3 {_f(o['mean'])} {o['verdict']:<9} {res}")


def raw_replication(v4_cells, v3_cells) -> list[tuple[dict, dict, str]]:
    """The printed alternative correction: replication on the raw-CI tokens."""
    by3 = {cell_key(c): c for c in v3_cells}
    return [(c, by3[cell_key(c)], replication(c["raw"], by3[cell_key(c)]["raw"]))
            for c in v4_cells if c["tier"] in GRADED_TIERS and cell_key(c) in by3]


def print_raw_replication(v4_cells, v3_cells, label: str):
    rows = raw_replication(v4_cells, v3_cells)
    t = Counter(r[2] for r in rows)
    print(f"\n-- REPLICATION, alternative correction (printed, not graded): raw CI tokens, {label}")
    print(f"   REPLICATED {t['REPLICATED']}  CONTRADICTED {t['CONTRADICTED']}  neither {t['-']}")
    for c, o, res in rows:
        if res != "-":
            print(f"   {c['family']:<9}{c['tier']:<6}{c['level']:<9} v4 {_f(c['mean'])} "
                  f"[{_f(c['lo'])}, {_f(c['hi'])}] {c['raw']:<9} v3 {_f(o['mean'])} "
                  f"[{_f(o['lo'])}, {_f(o['hi'])}] {o['raw']:<9} {res}")


def coverage(rows, counts, era: str):
    print(f"\nera {era}: {len(rows)} rows kept (VETO included); dropped {dict(counts)}")
    print(f"   tiers: {dict(Counter(r['tier'] for r in rows))}")
    print("   unlabelled rows per family: " + ", ".join(
        f"{fam} {sum(1 for r in rows if r['labels'].get(fam) is None)}" for fam in FAMILIES))
    dates = {r["date"]: r["labels"] for r in rows}
    for fam, (name, levels) in FAMILIES.items():
        cnt = Counter(lab.get(fam) for lab in dates.values())
        print(f"   {name:<24} signal dates by level: "
              + ", ".join(f"{lvl} {cnt.get(lvl, 0)}" for lvl in levels)
              + f", unlabelled {cnt.get(None, 0)}")


def main() -> int:
    seal_start = era_mod.SEAL_START
    labeler = MechLabeler.from_csv(MECH_TABLE_CSV)
    print("regime_map — each ladder tier against each market label, one label at a time")
    print(f"registration: {REGISTRATION} (accepted by default {ACCEPTED})")
    print(f"mech labels: lib/mech_regime.py MechLabeler, table {MECH_TABLE_CSV.name}, "
          f"ends {labeler.last_date}")
    print(f"floors per cell: {MIN_POS} positions and {MIN_DATES} signal dates; BH q < {BH_Q} "
          f"over each era's graded cells; bootstrap {BOOT_N} draws, seed {SEED}")
    print(f"in-sample: signal dates < {seal_start}; forward: >= {seal_start} (lib/era.py "
          f"SEAL_START), seal lifted: {era_mod.SEAL_LIFTED or 'no'}")
    print("A descriptive map, not a selection rule. Nothing ships from this study.")

    recs, diag = load_book()
    rows, counts = prepare(recs, labeler, has_cost=True)
    ins = [r for r in rows if r["date"] < seal_start]
    fwd = [r for r in rows if r["date"] >= seal_start]
    era = diag["era"]

    print("\n" + "=" * 78)
    print(f"IN-SAMPLE MAP — era {era}, R net of cost_total (graded)")
    print("=" * 78)
    coverage(ins, counts, era)
    net4 = build_map(ins, "R")
    print_map(net4, f"{era} net R")
    gross4 = build_map(ins, "Rg")

    v3_cells = None
    if era != REPLICATION_ERA:
        try:
            recs3, diag3 = load_book(era=REPLICATION_ERA)
        except SystemExit as exc:
            print(f"\n{REPLICATION_ERA} not loaded: era refusal, exit {exc.code}")
        else:
            rows3, counts3 = prepare(recs3, labeler, has_cost=False)
            ins3 = [r for r in rows3 if r["date"] < seal_start]
            print("\n" + "=" * 78)
            print(f"IN-SAMPLE MAP — era {diag3['era']}, R gross (no cost columns), the replication")
            print("=" * 78)
            coverage(ins3, counts3, diag3["era"])
            v3_cells = build_map(ins3, "R")
            print_map(v3_cells, f"{diag3['era']} gross R")

    print("\n" + "=" * 78)
    print("EX-STRESS RE-CUT — not graded (windows chosen from outcomes)")
    print("=" * 78)
    print(f"   dropped signal dates in {STRESS}")
    print_map(build_map([r for r in ins if not in_stress(r["date"])], "R"),
              f"{era} net R, ex-stress", graded=False)
    if v3_cells is not None:
        print_map(build_map([r for r in ins3 if not in_stress(r["date"])], "R"),
                  f"{REPLICATION_ERA} gross R, ex-stress", graded=False)

    replicated = []
    if v3_cells is not None:
        print("\n" + "=" * 78)
        print("REPLICATION ACROSS ERAS")
        print("=" * 78)
        rep_net = replication_block(net4, v3_cells)
        rep_gross = replication_block(gross4, v3_cells)
        print_replication(rep_net, rep_gross, f"{era} net vs {REPLICATION_ERA} gross",
                          f"{era} gross vs {REPLICATION_ERA} gross")
        replicated = [c for c, _o, res in rep_net if res == "REPLICATED"]
        print_raw_replication(net4, v3_cells, f"{era} net vs {REPLICATION_ERA} gross")

    print("\n" + "=" * 78)
    print("FORWARD — REPLICATED cells only")
    print("=" * 78)
    graded_fwd = era == FORWARD_ERA
    held = diag.get("seal", {})
    if not era_mod.SEAL_LIFTED:
        print(f"SEALED: load_book withheld {held.get('rows', 0)} rows on {held.get('dates', 0)} "
              f"signal dates >= {seal_start}. This study is not a named reader.")
    if not graded_fwd:
        print(f"era {era} is not the forward era {FORWARD_ERA}: not graded")
    ftally = Counter()
    for c in replicated:
        sub = [r for r in (fwd if graded_fwd else [])
               if in_tier(r, c["tier"]) and r["labels"].get(c["family"]) == c["level"]]
        tok, m, lo, hi = forward_token(sub, c["verdict"])
        ftally[tok] += 1
        print(f"   {c['family']:<9}{c['tier']:<6}{c['level']:<9} in-sample {c['verdict']:<9} "
              f"forward n={len(sub)} dates={n_dates(sub)} meanR={_f(m)} [{_f(lo)}, {_f(hi)}]  {tok}")
    if not replicated:
        print("   no cell REPLICATED in-sample: nothing to read forward")

    t4 = tally(net4)
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    toks = (POSITIVE, NEGATIVE, NULL, THIN)
    print(f"  {era} net, graded cells: " + ", ".join(f"{k} {t4.get(k, 0)}" for k in toks))
    if v3_cells is not None:
        t3 = tally(v3_cells)
        print(f"  {REPLICATION_ERA} gross, graded cells: " + ", ".join(
            f"{k} {t3.get(k, 0)}" for k in (POSITIVE, NEGATIVE, NULL, THIN)))
    names = ", ".join(f"{c['tier']} x {c['family']}={c['level']} {c['verdict']}" for c in replicated)
    print(f"  >>> regime_map REPLICATED cells ({era} net vs {REPLICATION_ERA} gross): "
          f"{len(replicated)}{': ' + names if names else ''} <<<")
    print(f"  forward: {dict(ftally) if ftally else 'none to read'}")
    print("  A descriptive map, not a selection rule. Nothing ships from this study.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
