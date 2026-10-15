"""spy_benchmark — do the deployed picks beat a SPY call spread on the same dates?

Registration: `research/pre-registrations/f1_selection/benchmark/spy_benchmark.md`
(accepted by default 2026-10-14, POST HOC: proposed after cost_sensitivity,
direction_hit and mechanical_benchmark's P1 same-ticker read were seen). That
file is the spec; this module implements it and adds nothing to its bar.
RESEARCH TIER: nothing ships from this study, and it is NOT a programme_gate
input.

THE ARM. For every deployed pick (mechanical_benchmark's deployed set: top-3
per day, Tier A/B, post-P3 tiers, sealed dates withheld), ARM SPY is the
`ARM M1` wrap on SPY: long the listed call nearest SPY's signal-date price
x1.00, short nearest x1.05, the pick's OWN expiry, 1 lot, entered on the
pick's recorded entry day. Every rule is mechanical_benchmark's, IMPORTED:
`select_m1` (strike choice, skip-list walk, AWAITING), `finish` (production's
`_simulate`), `UniverseSpot` (SPY's price off its cached contracts), the
deployed set, the seal, `profile_for`, `replay_R` and `grade`.

RULING B (Resolved at build 2026-10-15, `expiry_not_listed`). A SPY wrap
whose expiry has at least `EXPIRY_NOT_LISTED_MIN_CONTRACTS` cached
contracts, none quoted on or before the signal date, drops as
`expiry_not_listed_at_signal` instead of awaiting a fetch.

TWO UNITS (parameter SB-UNIT, printed both ways):
    pick  (default)  one row per pick, SPY at that pick's expiry; a SPY wrap
                     repeats when picks share an expiry. CI date-clustered.
    date             one row per date: the date's mean pick R against the SPY
                     wrap at the expiry of its top-ranked paired pick.

NO OUTCOME WHILE ANYTHING AWAITS. The census runs first on an UNPRICED build.
While any SPY pair awaits a fetch the run prints NOT BUILT — AWAITING SCRAPE
and the fetch count, and nothing is priced or replayed.

Fetch: `python3 scripts/collector/fetch_mechanical_legs.py --arms SPY --no-v3
--dry-run`. No code here fetches.

Usage:
  python3 -m scripts.backtest_study run spy_benchmark
  python3 -m scripts.backtest_study.f1_selection.benchmark.spy_benchmark [--v3]
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import logging
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f1_selection.benchmark import mechanical_benchmark as MB  # noqa: E402
from scripts.backtest_study.f4_deployment import narrow_to_fit as NTF  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib.book import DEBIT_PROD, load_book  # noqa: E402

# Era refusals from `load_book` (exit 2 thin era, exit 3 wrong era).
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

#: The one ticker this benchmark trades.
SPY = "SPY"
#: SB-UNIT: the default first; both print, only the default is the verdict.
UNITS = ("pick", "date")
#: Census floors (registration §Census floors).
FLOOR1_MIN_DATES = 25
FLOOR2_MAX_TIER_GAP = MB.FLOOR2_MAX_TIER_GAP
FLOOR4_MIN_BAND_PAIRS = MB.FLOOR5_MIN_BAND_PAIRS

AWAITING = "NOT BUILT — AWAITING SCRAPE"
NOT_BUILT = "NOT BUILT"

OUT_DIR = MB.OUT_DIR
PAIRS_CSV = OUT_DIR / "spy_benchmark-pairs.csv"
FETCH_CMD = "python3 scripts/collector/fetch_mechanical_legs.py --arms SPY"

log = logging.getLogger("spy_benchmark")
hdr = MB.hdr


# ════════════════════════════════════════════════════════════════════════════
# The build
# ════════════════════════════════════════════════════════════════════════════

@dataclasses.dataclass
class SpyBuild:
    era: str
    slots: list                  # MB.Slot per deployed pick, in ladder order per date
    wraps: list                  # MB.Wrap per slot; shared when signal/entry/expiry match
    seal: str


#: Ruling B's drop reason (registration, Resolved at build 2026-10-15).
EXPIRY_NOT_LISTED = "expiry_not_listed_at_signal"
#: Ruling B: the fewest cached contracts at an expiry, all first quoted after
#: the signal date, that show the expiry itself was not listed then.
EXPIRY_NOT_LISTED_MIN_CONTRACTS = 5


def expiry_not_listed(chain, ticker: str, expiry, signal) -> bool:
    """Ruling B (Resolved at build 2026-10-15, amended the same day), ARM SPY.

    True when (a) every cached contract at `expiry`, calls and puts, has rows
    and its first row is strictly after `signal`, and (b) at least
    `EXPIRY_NOT_LISTED_MIN_CONTRACTS` contracts are cached there. An expiry
    lists all its strikes at once, so many strikes all first quoted after
    the signal show the expiry did not exist then.

    It reads each file's first row, which can be dated after the signal. That
    only decides that the expiry was not listed; it never chooses a strike.
    The files are read uncut (`_load`), so a cache cut at the signal date
    (`AsOfChain`, gate G2) gets the same answer.
    """
    n = 0
    for k in chain.strikes(ticker, expiry):
        for opt in ("Call", "Put"):
            if not chain.cached(ticker, expiry, k, opt):
                continue
            series, details = chain._load(MB.Leg(1, ticker, expiry, float(k), opt))
            days = [d for d, _ in series] + list(details)
            if not days or min(days) <= signal:
                return False
            n += 1
    return n >= EXPIRY_NOT_LISTED_MIN_CONTRACTS


def spy_wrap(chain, evidence, sim_cfg, spot_u, s: MB.Slot, price: bool) -> MB.Wrap:
    """ARM SPY for one slot: `ARM U`'s M1 wrap with SPY as the ticker and the
    pick's own expiry (`ARM M1`'s expiry rule).

    An expiry SPY had not listed on the signal date drops as
    `expiry_not_listed_at_signal` (ruling B, `expiry_not_listed`). No SPY
    spot on the signal date (no cached contract carries a row that day)
    drops as `no_spot_at_signal`, through `ARM M1`'s own `select_m1`
    (Resolved at build 2026-10-15)."""
    if expiry_not_listed(chain, SPY, s.expiry, s.signal):
        return MB.Wrap("drop", EXPIRY_NOT_LISTED)
    spot = spot_u(SPY, s.signal, s.expiry)
    if spot is None:
        return MB.select_m1(chain, evidence, SPY, s.expiry, None, s.signal)
    return MB.u_wrap(chain, evidence, sim_cfg, spot_u, SPY, s, s.expiry, price)


def build_era(era_name: str | None, chain, evidence: set[str], sim_cfg: dict,
              price: bool = True, records=None) -> SpyBuild:
    if records is None:
        records, _diag = load_book(era=era_name, include_bs=False)
    records, seal = MB.apply_seal(records)
    slots = [MB.slot_of(r) for r in MB.deployed(records)]
    spot_u = MB.UniverseSpot(chain)
    memo: dict = {}
    wraps = []
    for s in slots:
        if s.drop:
            wraps.append(MB.Wrap("drop", s.drop))
            continue
        key = (s.signal, s.entry_day, s.expiry)
        if key not in memo:
            memo[key] = spy_wrap(chain, evidence, sim_cfg, spot_u, s, price)
        wraps.append(memo[key])
    return SpyBuild(era_name or era.CURRENT, slots, wraps, seal)


def priced(b: SpyBuild, chain, sim_cfg) -> SpyBuild:
    """The same build with every built wrap priced (unpriceable -> drop)."""
    memo: dict = {}
    out = []
    for s, w in zip(b.slots, b.wraps):
        if w.status != "built":
            out.append(w)
            continue
        key = (s.signal, s.entry_day, s.expiry)
        if key not in memo:
            memo[key] = MB.finish(w, chain, sim_cfg, SPY, s.signal, s.entry_day, s.expiry)
        out.append(memo[key])
    return dataclasses.replace(b, wraps=out)


def fetch_targets(builds: list[SpyBuild]) -> list[dict]:
    """Unique uncached SPY call contracts the awaiting wraps name, tagged
    `SPY:<era>`. `fetch_mechanical_legs.py --arms SPY` fetches these."""
    seen: dict = {}
    for b in builds:
        for w in b.wraps:
            if w.status != "await":
                continue
            for tk, exp, k in w.fetch:
                seen.setdefault((tk, exp, round(float(k), 4)), f"SPY:{b.era}")
    return [dict(ticker=tk, expiration=exp, strike=k, opt_type="Call", category=cat)
            for (tk, exp, k), cat in sorted(seen.items())]


# ════════════════════════════════════════════════════════════════════════════
# Census and floors — counts only
# ════════════════════════════════════════════════════════════════════════════

def census(b: SpyBuild) -> dict:
    st = Counter(w.status for w in b.wraps)
    by = defaultdict(Counter)
    for s, w in zip(b.slots, b.wraps):
        for cut in (f"tier {s.tier}", s.structure, f"band {MB.band_label(s.band)}"):
            by[cut][w.status] += 1
    built = {s.date for s, w in zip(b.slots, b.wraps) if w.status == "built"}
    open_ = {s.date for s, w in zip(b.slots, b.wraps) if w.status in ("built", "await")}
    return dict(
        n_slots=len(b.slots), n_dates=len({s.date for s in b.slots}), status=st,
        reasons=Counter(w.reason for w in b.wraps if w.status != "built"), by=by,
        f1_now=len(built), f1_bound=len(open_),
        f2=MB.tier_unbuildable(b.slots, b.wraps),
        bands=Counter(MB.band_label(s.band) for s, w in zip(b.slots, b.wraps)
                      if w.status == "built"),
        distinct=len({id(w) for w in b.wraps if w.status in ("built", "await")}),
        spy_picks=sum(1 for s in b.slots if s.ticker == SPY),
    )


def floors(c: dict, n_fetch: int) -> tuple[str, list[str]]:
    """`(state, lines)`, state PASS | AWAITING | FAIL. FAIL is definitive:
    even if every awaiting pair built, floor 1 or 2 could not be met."""
    lines, state = [], "PASS"
    if c["f1_bound"] < FLOOR1_MIN_DATES:
        state, f1 = "FAIL", "FAIL"
    elif c["f1_now"] < FLOOR1_MIN_DATES:
        state, f1 = "AWAITING", "PENDING"
    else:
        f1 = "pass"
    lines.append(f"  1  dates with >= 1 SPY pair   now {c['f1_now']:>4}  if fetched <= "
                 f"{c['f1_bound']:>4}  need {FLOOR1_MIN_DATES}  {f1}")
    gap = MB.tier_gap(c["f2"])
    f2s = "  ".join(f"{t} {dr}/{n}" for t, (dr, n) in sorted(c["f2"].items()))
    if c["status"]["await"] or gap is None:
        f2 = "PENDING (awaiting pairs undecided)"
        state = MB._worse(state, "AWAITING")
    elif gap > FLOOR2_MAX_TIER_GAP:
        f2, state = "FAIL", "FAIL"
    else:
        f2 = "pass"
    lines.append(f"  2  in-scope dropped share by tier  {f2s}  gap "
                 f"{'n/a' if gap is None else f'{gap:.3f}'}  max {FLOOR2_MAX_TIER_GAP}  {f2}")
    if n_fetch or c["status"]["await"]:
        state = MB._worse(state, "AWAITING")
    lines.append(f"  3  SPY contracts to fetch {n_fetch} (one feed request each); "
                 f"pairs awaiting {c['status']['await']}  "
                 f"{'pass' if not (n_fetch or c['status']['await']) else 'NEEDS OPERATOR-APPROVED FETCH'}")
    bands = c["bands"]
    lines.append("  4  SPY pairs by band  " + "  ".join(
        f"{MB.band_label(bd)} {bands.get(MB.band_label(bd), 0)}"
        f"{'' if bands.get(MB.band_label(bd), 0) >= FLOOR4_MIN_BAND_PAIRS else ' (not read)'}"
        for bd in MB.BANDS) + "  (no floor)")
    return state, lines


def study_word(state: str) -> str | None:
    return {"FAIL": NOT_BUILT, "AWAITING": AWAITING}.get(state)


def print_census(b: SpyBuild, c: dict) -> None:
    hdr(f"ARM CEN — census, era {b.era} (counts only)")
    print(f"  {b.seal}")
    print(f"  deployed picks (top-{MB.K_DEPLOY}/day, Tier A/B): {c['n_slots']} on "
          f"{c['n_dates']} dates; picks on SPY itself {c['spy_picks']}")
    st = c["status"]
    print(f"  SPY wraps: built {st['built']}  awaiting fetch {st['await']}  "
          f"dropped {st['drop']}  (distinct SPY spreads {c['distinct']})")
    for why, n in c["reasons"].most_common():
        print(f"      not built: {why:<34} {n:>5}")
    print("      cut                          built  await  drop")
    for cut in sorted(c["by"]):
        s = c["by"][cut]
        print(f"      {cut:<28} {s['built']:>6} {s['await']:>6} {s['drop']:>5}")


# ════════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════════

def g2_blind(b: SpyBuild, chain, evidence) -> list[str]:
    """Every SPY choice re-run on a cache cut at the signal date must agree."""
    bad, seen = [], set()
    for s, w in zip(b.slots, b.wraps):
        if s.drop or w.status == "await" or id(w) in seen:
            continue
        seen.add(id(w))
        cut = MB.AsOfChain(chain, s.signal)
        spot = MB.UniverseSpot(cut)(SPY, s.signal, s.expiry)
        if expiry_not_listed(cut, SPY, s.expiry, s.signal):
            r = MB.Wrap("drop", EXPIRY_NOT_LISTED)
        else:
            r = MB.select_m1(cut, evidence, SPY, s.expiry, spot, s.signal)
        same = (r.k_long, r.k_short) == (w.k_long, w.k_short) or \
            (w.status == "drop" and r.status == "drop")
        if not same:
            bad.append(f"{s.date} {s.ticker} {s.expiry}: full {w.k_long}/{w.k_short} "
                       f"vs cut {r.k_long}/{r.k_short}")
    return bad


def g4_pairing(b: SpyBuild) -> list[str]:
    if len(b.wraps) != len(b.slots):
        return [f"{len(b.wraps)} wraps for {len(b.slots)} slots"]
    return []


# ════════════════════════════════════════════════════════════════════════════
# Outcomes — only once nothing awaits
# ════════════════════════════════════════════════════════════════════════════

def pair_rows(b: SpyBuild, basis: str) -> list[dict]:
    """SB-UNIT = pick: one row per built pair, in slot (ladder) order."""
    memo: dict = {}
    out = []
    for i, (s, w) in enumerate(zip(b.slots, b.wraps)):
        if w.status != "built":
            continue
        rt, et = MB.replay_R(s.rec["t"], MB.profile_for(s.rec, basis))
        key = (id(w), s.rec.get("mech_cell"), basis)
        if key not in memo:
            memo[key] = MB.replay_R(MB.trade_of(w.row), MB.profile_for(
                {"credit": False, "mech_cell": s.rec.get("mech_cell")}, basis))
        rc, ec = memo[key]
        out.append(dict(slot=i, date=s.date, ticker=s.ticker, tier=s.tier,
                        structure=s.structure, band=MB.band_label(s.band),
                        expiry=s.expiry, model_dir=s.rec.get("model_dir"),
                        R_T=rt, R_C=rc, E_T=et, E_C=ec,
                        k_long=w.k_long, k_short=w.k_short))
    return out


def date_rows(rows: list[dict]) -> list[dict]:
    """SB-UNIT = date: per date, the mean R of its paired picks against the
    SPY wrap of its top-ranked paired pick (the first row in slot order)."""
    by: dict = {}
    for r in sorted(rows, key=lambda r: r["slot"]):
        by.setdefault(r["date"], []).append(r)
    out = []
    for d, rs in by.items():
        top = rs[0]
        out.append(dict(date=d, ticker=",".join(r["ticker"] for r in rs), tier=top["tier"],
                        structure=top["structure"], band=top["band"], expiry=top["expiry"],
                        model_dir=top["model_dir"], n_picks=len(rs),
                        R_T=statistics.fmean(r["R_T"] for r in rs), R_C=top["R_C"],
                        E_T=statistics.fmean(r["E_T"] for r in rs), E_C=top["E_C"],
                        k_long=top["k_long"], k_short=top["k_short"]))
    return out


def rows_for(unit: str, rows: list[dict]) -> list[dict]:
    return rows if unit == "pick" else date_rows(rows)


def verdict(g: dict) -> str:
    """The registration's tokens, in its precedence (census handled before)."""
    if not g.get("c0"):
        return "UNDERPOWERED"
    if g.get("contrary"):
        return "CONTRARY"
    if g.get("c1") and g.get("c2"):
        return "BEATS-SPY"
    return "DOES-NOT-BEAT"


def write_pairs(rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["date", "ticker", "tier", "structure", "band", "expiry", "model_dir",
            "R_T", "R_C", "E_T", "E_C", "k_long", "k_short"]
    with PAIRS_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--v3", action="store_true",
                    help="also build v3 (graded only once none of its SPY pairs awaits)")
    args = ap.parse_args(argv)
    logging.getLogger("backtest").setLevel(logging.ERROR)
    logging.getLogger("scripts.backtest").setLevel(logging.ERROR)

    hdr("spy_benchmark — do the deployed picks beat a SPY call spread on the same dates?")
    print("""  Registration research/pre-registrations/f1_selection/benchmark/spy_benchmark.md
  (accepted by default 2026-10-14). POST HOC: proposed after cost_sensitivity,
  direction_hit and mechanical_benchmark's P1 read were seen. NOTHING SHIPS,
  and this is not a programme_gate input. Both books GROSS of costs. No
  annualised figure, Sharpe or time-to-recover is printed (G6); every count is
  computed by this run (G7).""")

    chain = NTF.Chain()
    evidence = NTF.unlisted_evidence()
    sim_cfg = NTF._sim_cfg()

    records, diag = load_book(include_bs=False)
    print(f"\n  G1 era {diag.get('era')}  book {len(records)} rows  "
          f"{diag.get('n_dates')} dates  {diag.get('date_range')}")
    eras = [(None, records)]
    if args.v3:
        try:
            v3, d3 = load_book(era="v3", include_bs=False)
            print(f"  G1 era {d3.get('era')} (optional)  book {len(v3)} rows")
            eras.append(("v3", v3))
        except SystemExit as exc:
            print(f"  v3 era refused (exit {exc.code}); v3 not graded")

    # Census on an UNPRICED build: nothing is priced or replayed while any
    # SPY pair awaits a fetch.
    builds = [build_era(name, chain, evidence, sim_cfg, price=False, records=recs)
              for name, recs in eras]
    targets = fetch_targets(builds)
    states = {}
    for b in builds:
        c = census(b)
        print_census(b, c)
        n_era = sum(1 for t in targets if t["category"] == f"SPY:{b.era}")
        states[b.era] = floors(c, n_era)

    hdr("CENSUS FLOORS (registration §Census floors)")
    for b in builds:
        state, lines = states[b.era]
        print(f"  era {b.era}: {state}")
        for ln in lines:
            print(ln)
    by_cat = Counter(t["category"] for t in targets)
    print(f"\n  fetch plan: {len(targets)} unique uncached SPY call contracts  "
          + "  ".join(f"{k}={v}" for k, v in sorted(by_cat.items())))

    word = study_word(states[builds[0].era][0])
    if word:
        hdr(f"VERDICT: {word}")
        print("  The census is the recorded result. No outcome was computed: no SPY")
        print("  wrap was priced or replayed.")
        if word == AWAITING:
            print("  Operator-run steps, in order (none runs from here):")
            print(f"    1. {FETCH_CMD} --no-v3 --dry-run   (approve the count, then "
                  f"--limit N)")
            print("    2. python3 scripts/backup_research_caches.py push")
            print("    3. re-run this study; a fetch can expose nearer strikes, so "
                  "steps 1-3 repeat until nothing awaits")
        return 0

    # ── price, re-check the floors, gates ───────────────────────────────────
    builds = [priced(b, chain, sim_cfg) if states[b.era][0] == "PASS" else b
              for b in builds]
    hdr("GATES AND FLOORS AFTER PRICING")
    ok = True
    for b in builds:
        if states[b.era][0] != "PASS":
            continue
        state, lines = floors(census(b), 0)
        states[b.era] = (state, lines)
        print(f"  era {b.era} floors after pricing: {state}")
        for ln in lines:
            print(ln)
        bad = g2_blind(b, chain, evidence)
        print(f"  G2 NO LOOK-AHEAD ({b.era}): {'PASS' if not bad else 'FAIL'}"
              f"  {len(bad)} SPY choices differ on a cache cut at the signal date")
        for x in bad[:10]:
            print(f"     {x}")
        ok &= not bad
        bad4 = g4_pairing(b)
        print(f"  G4 PAIRING ({b.era}): {'PASS' if not bad4 else 'FAIL'}")
        ok &= not bad4
    print(f"  G3 EXIT PARITY: one harness call per side, headline profile "
          f"{DEBIT_PROD} on both sides")
    srcs = Counter(s.rec["source"] for b in builds for s in b.slots)
    print(f"  G5 TIERS: picks' sources {dict(srcs)}  {'PASS' if 'bs' not in srcs else 'FAIL'}"
          f"; SPY side refuses any model price (mechanical_benchmark.price_wrap)")
    ok &= "bs" not in srcs
    if not ok:
        print("\nGATE FAILURE — no outcome printed. Exit 1.")
        return 1
    word = study_word(states[builds[0].era][0])
    if word:
        hdr(f"VERDICT: {word}")
        print("  A floor fails after pricing. No outcome printed.")
        return 0

    # ── outcomes ─────────────────────────────────────────────────────────────
    record = None
    for basis in ("headline", "own"):
        title = ("HEADLINE — DEBIT_PROD on both sides" if basis == "headline"
                 else "DECLARED SECONDARY — each side under its own §5 row")
        hdr(f"OUTCOMES, {title}. GROSS of costs.")
        for b in builds:
            if states[b.era][0] != "PASS":
                print(f"\n  era {b.era}: floors {states[b.era][0]}; not graded")
                continue
            rows = pair_rows(b, basis)
            for unit in UNITS:
                ur = rows_for(unit, rows)
                g = MB.grade(ur)
                tag = "default" if unit == UNITS[0] else "printed beside it"
                print(f"\n  era {b.era}  SB-UNIT = {unit} ({tag})")
                MB.print_grade("SPY", g, "GROSS")
                print(f"        {MB.arm_criteria(g)}  -> {verdict(g)}")
                ex = [r for r in ur if SPY not in r["ticker"].split(",")]
                if unit == "pick":
                    print(f"        descriptive: {len(ur) - len(ex)} picks on SPY itself; "
                          f"ex-SPY mean gain "
                          + (f"{statistics.fmean(r['R_T'] - r['R_C'] for r in ex):+.3f}"
                             if ex else "n/a"))
                if basis == "headline" and b is builds[0] and unit == "pick":
                    record = verdict(g)
                    write_pairs(rows)
    hdr(f"VERDICT (headline basis, SB-UNIT = pick): {record}")
    print("  Not a programme_gate input: recorded beside the gate, never changing it.")
    print(f"  pairs written to {PAIRS_CSV.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
