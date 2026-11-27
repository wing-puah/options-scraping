"""Forward-only test: do Tier A+B plays earn more R per position than Tier C, on dates after 2026-11-27?

Registration: `research/pre-registrations/f4_deployment/tier_contrast_forward.md`
(accepted by default and second-read 2026-11-28, before the build and before
any outcome). Every constant below is fixed there; none may move.

Population: the v4 book through `load_book` (`include_bs=False`,
`include_pending=True` so pending rows can end the complete prefix). The tier
is `book_tier()`, the adapter over `mapping.ladder_tier()`; this module never
re-derives a tier rule. Vetoed rows are in neither arm. `BacktestProxy`
(`tweak`) rows are counted and contrasted separately, never graded.

Window: signal dates from 2026-11-28, cut to the COMPLETE PREFIX (dates before
the first date still holding a pending A, B or C row). D* is the earliest
prefix date, on or before the 2028-11-27 sunset, at which each arm holds at
least 377 closed positions on at least 120 signal dates. A run date never moves
D*.

Before D* exists the run prints counts only and `STILL-OPEN` (or `LAPSED`),
appends one line to the look log, and exits 0. When D* exists it runs the gates
(G1 era, G2 calibration with permutation fallback, G3 window, G4 cache), grades
the one contrast with a date-clustered bootstrap, stores the read, and every
later run prints the stored token and regrades nothing.

Run: `python3 -m scripts.backtest_study run tier_contrast_forward`.
`--pipeline-stopped REASON` declares that v4 emission has stopped (the
registration's pipeline-stop LAPSED rule); it is recorded in the look log.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date as _date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib.book import book_tier, load_book, norm_play  # noqa: E402

REGISTRATION = "research/pre-registrations/f4_deployment/tier_contrast_forward.md"
ACCEPTED = "2026-11-28"
STUDY_ERA = "v4"

# --- registered constants (fixed 2026-11-28) ------------------------------------
START = "2026-11-28"          # first forward signal date
SUNSET = "2028-11-27"         # floors count signal dates on or before this only
MIN_POS = 377                 # closed positions per arm
MIN_DATES = 120               # signal dates per arm
BOOT_N = 10_000
CALIB_N = 500
PERM_N = 10_000
CALIB_BOUND = 0.075           # 1.5 x nominal
ALPHA = 0.05
SIGMA = 1.0                   # frozen per-row R spread
DE = 1.5                      # design effect
REF_EFFECT = 0.25             # reference effect, R
MDE_MULT = 2.80               # z_0.975 + z_0.8
SEED_BOOT = 20261128
SEED_CALIB = 20261129
SEED_PERM = 20261130

ARM_AB, ARM_C = "AB", "C"
TIERED = ("A", "B", "C")

STILL_OPEN = "STILL-OPEN"
LAPSED = "LAPSED"
REFUSED = "REFUSED (gate)"
SELECTS = "GATE-SELECTS"
INVERTED = "GATE-INVERTED"
UNDERPOWERED = "UNDERPOWERED-BY-DESIGN"
NULL = "NULL"

OUT_DIR = ROOT / "backtests" / "study_output"
FORWARD_JSON = OUT_DIR / "tier_contrast_forward-forward-read.json"
LOOKS_JSONL = OUT_DIR / "tier_contrast_forward-looks.jsonl"
OPTION_CACHE_DIR = ROOT / "backtests" / "option_history_cache"

EXIT_WRONG_ERA = 3
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}


# ════════════════════════════════════════════════════════════════════════════
# Rows and the window (pure)
# ════════════════════════════════════════════════════════════════════════════

def tier_of(rec: dict) -> str:
    """The row's tier, from `book_tier()` -> `mapping.ladder_tier()`. Never re-derived."""
    return book_tier(rec)


def arm_of(tier: str) -> str | None:
    return ARM_AB if tier in ("A", "B") else ARM_C if tier == "C" else None


def row_of(rec: dict) -> dict:
    """A slim row: date, tier, arm, R, pending, source, identity key."""
    t = rec.get("t")
    play = norm_play(t.row.get("play", "")) if t is not None else ""
    tier = tier_of(rec)
    R = rec.get("R")
    return dict(date=str(rec["date"])[:10], tier=tier, arm=arm_of(tier),
                R=float(R) if R is not None else None,
                R_capped=rec.get("R_capped"),
                pending=bool(rec.get("pending", False)),
                source=rec.get("source", "real"),
                key=f"{str(rec['date'])[:10]}|{rec.get('ticker')}|{play or rec.get('structure')}")


def forward_rows(rows: list[dict], start: str = START) -> list[dict]:
    """Rows whose signal date is on or after `start`; 2026-11-27 and earlier are out."""
    return [r for r in rows if r["date"] >= start]


def split_rows(rows: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """(primary A/B/C rows, proxy A/B/C rows, census counts). Vetoed rows join neither arm."""
    primary, proxy, census = [], [], defaultdict(int)
    for r in rows:
        if r["tier"] not in TIERED:
            census[f"tier_{r['tier']}"] += 1
            continue
        if r["source"] == "real":
            primary.append(r)
        elif r["source"] == "tweak":
            proxy.append(r)
        else:
            census[f"source_{r['source']}"] += 1
    return primary, proxy, dict(census)


def complete_prefix(rows: list[dict]) -> tuple[list[str], str | None]:
    """(prefix dates, first date holding a pending A/B/C row or None).

    The prefix is every forward date before the first date that still holds a
    pending tiered row. Only prefix rows count."""
    dates = sorted({r["date"] for r in rows})
    stall = min((r["date"] for r in rows if r["pending"] and r["tier"] in TIERED), default=None)
    if stall is None:
        return dates, None
    return [d for d in dates if d < stall], stall


def floors_met(n_pos: int, n_dates: int) -> bool:
    return n_pos >= MIN_POS and n_dates >= MIN_DATES


def arm_counts(rows: list[dict]) -> dict:
    """{arm: (positions, signal dates)} over closed rows with an R."""
    out = {}
    for arm in (ARM_AB, ARM_C):
        rs = [r for r in rows if r["arm"] == arm]
        out[arm] = (len(rs), len({r["date"] for r in rs}))
    return out


def find_dstar(rows: list[dict], prefix: list[str], sunset: str = SUNSET) -> str | None:
    """The earliest prefix date (<= sunset) at which BOTH arms meet both floors."""
    by_date = defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(r)
    n = {ARM_AB: 0, ARM_C: 0}
    nd = {ARM_AB: 0, ARM_C: 0}
    for d in prefix:
        if d > sunset:
            break
        for arm in (ARM_AB, ARM_C):
            k = sum(1 for r in by_date.get(d, ()) if r["arm"] == arm)
            n[arm] += k
            nd[arm] += 1 if k else 0
        if all(floors_met(n[a], nd[a]) for a in (ARM_AB, ARM_C)):
            return d
    return None


def gradable(rows: list[dict]) -> tuple[list[dict], int]:
    """(closed tiered rows with an R, count dropped for a missing R)."""
    keep = [r for r in rows if r["arm"] is not None and not r["pending"] and r["R"] is not None]
    dropped = sum(1 for r in rows if r["arm"] is not None and not r["pending"] and r["R"] is None)
    return keep, dropped


# ════════════════════════════════════════════════════════════════════════════
# Statistics (pure)
# ════════════════════════════════════════════════════════════════════════════

def contrast(rows: list[dict], a: str = ARM_AB, b: str = ARM_C, field: str = "R") -> float:
    """Mean R of arm `a` minus mean R of arm `b` (AB minus C by default)."""
    ra = [r[field] for r in rows if r["arm"] == a]
    rb = [r[field] for r in rows if r["arm"] == b]
    if not ra or not rb:
        return float("nan")
    return float(np.mean(ra) - np.mean(rb))


def _date_arrays(rows: list[dict], labels: list[str] | None = None, field: str = "R"):
    """Per-date sums and counts of each arm: (sAB, cAB, sC, cC) arrays over dates."""
    dates = sorted({r["date"] for r in rows})
    ix = {d: i for i, d in enumerate(dates)}
    k = len(dates)
    sa, ca, sc, cc = (np.zeros(k) for _ in range(4))
    for j, r in enumerate(rows):
        arm = labels[j] if labels is not None else r["arm"]
        i = ix[r["date"]]
        if arm == ARM_AB:
            sa[i] += r[field]
            ca[i] += 1
        elif arm == ARM_C:
            sc[i] += r[field]
            cc[i] += 1
    return sa, ca, sc, cc


def boot_draws(rows: list[dict], n: int = BOOT_N, seed: int = SEED_BOOT,
               labels: list[str] | None = None, field: str = "R") -> np.ndarray:
    """Contrast draws from resampling SIGNAL DATES with replacement; each drawn
    date brings all its AB and C rows (the `regime_map` cell_stats unit)."""
    sa, ca, sc, cc = _date_arrays(rows, labels, field)
    k = len(sa)
    if k == 0:
        return np.array([])
    idx = np.random.default_rng(seed).integers(0, k, size=(n, k))
    na, nc = ca[idx].sum(1), cc[idx].sum(1)
    ok = (na > 0) & (nc > 0)
    return (sa[idx].sum(1)[ok] / na[ok]) - (sc[idx].sum(1)[ok] / nc[ok])


def two_sided_p(draws: np.ndarray) -> float:
    """Twice the smaller share of draws at or below 0 and at or above 0, capped at 1."""
    if len(draws) == 0:
        return float("nan")
    return float(min(1.0, 2 * min(np.mean(draws <= 0), np.mean(draws >= 0))))


def realized_mde(draws: np.ndarray) -> float:
    """2.80 x the bootstrap standard error of the contrast (never the frozen sigma)."""
    return float(MDE_MULT * np.std(draws, ddof=1)) if len(draws) > 1 else float("nan")


def planning_mde(n_ab: int, n_c: int) -> float:
    """The registration's planning MDE from the frozen sigma and DE."""
    if not n_ab or not n_c:
        return float("nan")
    return float(MDE_MULT * SIGMA * np.sqrt(DE * (1 / n_ab + 1 / n_c)))


def shuffle_within_date(rows: list[dict], rng: np.random.Generator) -> list[str]:
    """Arm labels permuted WITHIN each signal date, among that date's AB and C rows."""
    labels = [r["arm"] for r in rows]
    by_date = defaultdict(list)
    for j, r in enumerate(rows):
        by_date[r["date"]].append(j)
    for d in sorted(by_date):
        js = by_date[d]
        perm = rng.permutation([labels[j] for j in js])
        for j, lab in zip(js, perm):
            labels[j] = lab
    return labels


def _labelled_contrast(rows: list[dict], labels: list[str]) -> float:
    ra = [r["R"] for r, lab in zip(rows, labels) if lab == ARM_AB]
    rc = [r["R"] for r, lab in zip(rows, labels) if lab == ARM_C]
    return float(np.mean(ra) - np.mean(rc)) if ra and rc else float("nan")


def calibration_rate(rows: list[dict], n: int = CALIB_N, boot_n: int = BOOT_N,
                     seed: int = SEED_CALIB) -> float:
    """G2: share of within-date label shuffles whose bootstrap p is below ALPHA."""
    rng = np.random.default_rng(seed)
    hits = 0
    for i in range(n):
        labels = shuffle_within_date(rows, rng)
        p = two_sided_p(boot_draws(rows, boot_n, seed + 1 + i, labels=labels))
        hits += p < ALPHA
    return hits / n


def permutation_p(rows: list[dict], n: int = PERM_N, seed: int = SEED_PERM) -> float:
    """G2 fallback: share of within-date shuffles with |contrast| >= |observed|."""
    obs = abs(contrast(rows))
    rng = np.random.default_rng(seed)
    hits = sum(abs(_labelled_contrast(rows, shuffle_within_date(rows, rng))) >= obs
               for _ in range(n))
    return hits / n


def within_date_contrast(rows: list[dict]) -> list[float]:
    """Per date holding both arms: that date's AB mean minus its C mean."""
    by_date = defaultdict(lambda: {ARM_AB: [], ARM_C: []})
    for r in rows:
        by_date[r["date"]][r["arm"]].append(r["R"])
    return [float(np.mean(v[ARM_AB]) - np.mean(v[ARM_C]))
            for d, v in sorted(by_date.items()) if v[ARM_AB] and v[ARM_C]]


def verdict(c: float, p: float, mde: float) -> str:
    """First match wins (registration, Verdicts worded now)."""
    if c > 0 and p < ALPHA:
        return SELECTS
    if c < 0 and p < ALPHA:
        return INVERTED
    if mde > REF_EFFECT:
        return UNDERPOWERED
    return NULL


def open_token(today: str, pending_to_sunset: bool, pipeline_stopped: bool) -> str:
    """STILL-OPEN or LAPSED when no D* exists yet."""
    if pending_to_sunset:
        return STILL_OPEN
    if today > SUNSET or pipeline_stopped:
        return LAPSED
    return STILL_OPEN


# ════════════════════════════════════════════════════════════════════════════
# Gates, the read, the look log
# ════════════════════════════════════════════════════════════════════════════

def cache_state(cache_dir: Path = OPTION_CACHE_DIR) -> dict | None:
    """G4: the option-cache record (file count), or None when there is none."""
    if not cache_dir.is_dir():
        return None
    n = sum(1 for e in os.scandir(cache_dir) if e.is_file())
    return {"dir": str(cache_dir.relative_to(ROOT)) if cache_dir.is_relative_to(ROOT)
            else str(cache_dir), "n_files": n}


def g3_window(rows: list[dict], dstar: str, recs_by_key: dict | None = None) -> bool:
    """Every graded row closed, dated START..D*, tier as `ladder_tier()` gives it."""
    for r in rows:
        if r["pending"] or not (START <= r["date"] <= dstar):
            return False
        if recs_by_key is not None and tier_of(recs_by_key[r["key"]]) != r["tier"]:
            return False
    return True


def grade(rows: list[dict], dstar: str, era_ok: bool, cache: dict | None,
          boot_n: int = BOOT_N, calib_n: int = CALIB_N, perm_n: int = PERM_N,
          recs_by_key: dict | None = None) -> dict:
    """Gates then the one read. A refusal carries only the failed gate and its figure."""
    if not era_ok:
        return {"token": REFUSED, "gate": "G1", "figure": f"era is not {STUDY_ERA}"}
    if not g3_window(rows, dstar, recs_by_key):
        return {"token": REFUSED, "gate": "G3", "figure": "a graded row is outside the window"}
    if cache is None:
        return {"token": REFUSED, "gate": "G4", "figure": "no option-cache record"}
    calib = calibration_rate(rows, calib_n, boot_n)
    draws = boot_draws(rows, boot_n)
    c = contrast(rows)
    p_boot = two_sided_p(draws)
    fallback = calib > CALIB_BOUND
    p = permutation_p(rows, perm_n) if fallback else p_boot
    mde = realized_mde(draws)
    n = arm_counts(rows)
    wd = within_date_contrast(rows)
    wd_draws = (np.array([np.mean(np.random.default_rng(SEED_BOOT + 7).choice(wd, len(wd)))
                          for _ in range(min(boot_n, 2000))]) if wd else np.array([]))
    figs = {
        "token": verdict(c, p, mde), "dstar": dstar, "contrast": c, "p": p,
        "p_bootstrap": p_boot, "p_source": "permutation (G2 fallback)" if fallback else "bootstrap",
        "calibration_rate": calib, "ci": _ci(draws),
        "realized_mde": mde, "planning_mde": planning_mde(n[ARM_AB][0], n[ARM_C][0]),
        "counts": {a: list(v) for a, v in n.items()},
        "a_minus_c": _sub_contrast(rows, "A", boot_n), "b_minus_c": _sub_contrast(rows, "B", boot_n),
        "tier_means": {t: _tier_mean(rows, t, boot_n) for t in TIERED},
        "within_date": {"mean": float(np.mean(wd)) if wd else None, "ci": _ci(wd_draws),
                        "n_dates": len(wd)},
        "capped_contrast": (contrast(rows, field="R_capped")
                            if all(r.get("R_capped") is not None for r in rows) else None),
        "cache": cache,
        "rows": [{"key": r["key"], "date": r["date"], "tier": r["tier"], "R": r["R"]} for r in rows],
    }
    return figs


def _ci(draws) -> list:
    return [float(np.quantile(draws, ALPHA / 2)), float(np.quantile(draws, 1 - ALPHA / 2))] \
        if len(draws) else [None, None]


def _sub_contrast(rows, tier, boot_n) -> dict:
    sub = [dict(r, arm=ARM_AB if r["tier"] == tier else ARM_C)
           for r in rows if r["tier"] in (tier, "C")]
    return {"contrast": contrast(sub), "ci": _ci(boot_draws(sub, boot_n))}


def _tier_mean(rows, tier, boot_n) -> dict:
    rs = [r for r in rows if r["tier"] == tier]
    if not rs:
        return {"mean": None, "ci": [None, None], "n": 0}
    vals = np.array([r["R"] for r in rs])
    idx = np.random.default_rng(SEED_BOOT + 3).integers(0, len(vals), size=(min(boot_n, 2000), len(vals)))
    return {"mean": float(vals.mean()), "ci": _ci(vals[idx].mean(1)), "n": len(rs)}


def print_read(figs: dict) -> None:
    """Print a read (fresh or stored). A refusal prints its gate and figure only."""
    if figs["token"] == REFUSED:
        print(f">>> tier_contrast_forward {REFUSED}: {figs['gate']} {figs['figure']} <<<")
        return
    print(f"D* {figs['dstar']}  counts {figs['counts']}")
    print(f"contrast AB-C {figs['contrast']:+.3f} CI {figs['ci']}  p {figs['p']:.4f} "
          f"({figs['p_source']}; G2 calibration rate {figs['calibration_rate']:.3f})")
    print(f"realized MDE {figs['realized_mde']:.3f}  planning MDE {figs['planning_mde']:.3f}")
    print(f"printed, never graded: A-C {figs['a_minus_c']}  B-C {figs['b_minus_c']}")
    print(f"  tier means {figs['tier_means']}")
    print(f"  within-date {figs['within_date']}")
    if figs["within_date"]["mean"] is not None and \
            np.sign(figs["within_date"]["mean"]) != np.sign(figs["contrast"]):
        print("  the within-date contrast's sign differs from the graded contrast")
    cap = figs["capped_contrast"]
    print(f"  capped-mark contrast {cap:+.3f}" if cap is not None
          else "  capped-mark contrast: no capped marks on these rows (owed)")
    print(f"  cache {figs['cache']}")
    print(f">>> tier_contrast_forward {figs['token']} <<<")


def append_look(rec: dict, path: Path = LOOKS_JSONL) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def run(rows: list[dict], today: str, forward_path: Path = FORWARD_JSON,
        looks_path: Path = LOOKS_JSONL, era_ok: bool = True,
        pipeline_stopped: str | None = None, cache_fn=cache_state,
        recs_by_key: dict | None = None, **grade_kw) -> str:
    """The whole forward read on prepared rows. Returns the printed token."""
    fwd = forward_rows(rows)
    primary, proxy, census = split_rows(fwd)
    prefix, stall = complete_prefix(primary)
    pset = set(prefix)
    graded_all, r_missing = gradable([r for r in primary if r["date"] in pset])
    counts = arm_counts(graded_all)
    look = {"run_date": today, "prefix_end": prefix[-1] if prefix else None,
            "stall_date": stall, "counts": {a: list(v) for a, v in counts.items()}}

    if forward_path.exists():
        stored = json.loads(forward_path.read_text())
        print(f"stored read ({forward_path.name}), regraded nothing:")
        print_read(stored)
        append_look({**look, "token": stored["token"], "stored": True}, looks_path)
        return stored["token"]

    vetoed = census.get("tier_VETO", 0)
    print(f"forward rows from {START}: {len(fwd)}; vetoed (in neither arm) {vetoed}; "
          f"other census {census}")
    print(f"proxy rows (never graded) per tier: "
          f"{ {t: sum(1 for r in proxy if r['tier'] == t) for t in TIERED} }")
    print(f"complete prefix: {len(prefix)} dates"
          + (f", ends at {prefix[-1]}" if prefix else "")
          + (f"; the pending row that ends it is dated {stall}" if stall else ""))
    print(f"closed rows with no R (dropped): {r_missing}")
    for a in (ARM_AB, ARM_C):
        print(f"arm {a}: {counts[a][0]} closed positions on {counts[a][1]} signal dates "
              f"(floor {MIN_POS} on {MIN_DATES})")

    dstar = find_dstar(graded_all, prefix)
    if dstar is None:
        pending_to_sunset = any(r["pending"] and r["date"] <= SUNSET for r in primary)
        token = open_token(today, pending_to_sunset, bool(pipeline_stopped))
        line = f">>> tier_contrast_forward {token} <<<"
        if token == LAPSED:
            line += f"  reason: {pipeline_stopped or 'sunset ' + SUNSET + ' passed'}"
        print(line)
        append_look({**look, "token": token, "pipeline_stopped": pipeline_stopped}, looks_path)
        return token

    window = [r for r in graded_all if r["date"] <= dstar]
    figs = grade(window, dstar, era_ok, cache_fn(), recs_by_key=recs_by_key, **grade_kw)
    print_read(figs)
    if figs["token"] != REFUSED:
        p_rows = [r for r in proxy if START <= r["date"] <= dstar and not r["pending"]
                  and r["R"] is not None]
        if p_rows:
            print(f"proxy contrast (never graded) {contrast(p_rows):+.3f} on {len(p_rows)} rows")
        forward_path.parent.mkdir(parents=True, exist_ok=True)
        forward_path.write_text(json.dumps(figs, indent=1, sort_keys=True))
    append_look({**look, "token": figs["token"], "dstar": dstar}, looks_path)
    return figs["token"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pipeline-stopped", metavar="REASON", default=None,
                    help="declare that v4 emission has stopped (pipeline-stop LAPSED rule)")
    args = ap.parse_args(argv)

    era = era_mod.requested_era()
    if era not in (era_mod.CURRENT, STUDY_ERA):
        print(f"tier_contrast_forward refuses era {era!r}: it reads {STUDY_ERA} only; "
              f"{era} has no forward dates.", file=sys.stderr)
        return EXIT_WRONG_ERA
    print(f"tier_contrast_forward — registration {REGISTRATION} (accepted {ACCEPTED}); era {STUDY_ERA}")
    recs, _diag = load_book(era=era, include_bs=False, include_pending=True)
    rows = [row_of(r) for r in recs]
    by_key = {}
    for rec, row in zip(recs, rows):
        by_key[row["key"]] = rec
    run(rows, _date.today().isoformat(), pipeline_stopped=args.pipeline_stopped,
        recs_by_key=by_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
