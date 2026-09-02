"""Portfolio net-delta study: is there a net delta level the deployed book should hold?

PRE-REGISTERED 2026-08-19, BEFORE this file was written, in
`research/pre-registrations/f4_deployment/portfolio_delta.md`. Read that first; nothing here
may drift from it. In brief:

  Question  `account_sim` meters exposure with a MAGNITUDE cap on
            |Σ signed delta-notional|. This study asks the different question:
            is there a net-delta LEVEL — a signed band with a floor and a
            ceiling — that the deployed book should be held at, and does adding
            exposure onto an already-long book pay worse?
  Not this  NOT a selection study (no arm changes which signals are eligible;
            "bear = hedge sleeve only" is respected by every arm including
            ARM H*), NOT an exit study (every position replays under the shipped
            profiles), NOT a cap search (capital, risk %, per-position cap, net
            cap and positions/day come from `config/account-sim.yml` AS
            COMMITTED and are not swept; compounding OFF).
  Arms      Four, frozen. ARM D dose-response (DESCRIPTIVE PRIMARY): label each
            session by open-book net delta-notional / equity at session open
            BEFORE that day's picks, bands [0,0.5)/[0.5,1)/[1,2)/[2,inf), read
            the outcome of the positions OPENED in each band. ARM B ceiling
            band {1.0,1.5,2.0,2.5,inf} x equity through a LOCAL
            `admission_banded` copy behind G-EQUIV. ARM H* the shipped bear
            hedge sleeve re-sized to a delta TARGET {1.0,1.5,2.0} x equity
            instead of the fixed 1/2-risk size — the only arm that can push net
            delta DOWN. ARM N 200 seeded random admissions = the null band.
  Unit      The SESSION. ARM D quotes mean R per band (MIN_CELL_N = 20). ARM B /
            ARM H* are within-date paired differences vs the shipped walk.
  Gates     G-DELTA (delta source) -> G-EQUIV (the fork reproduces
            `account_sim.simulate()` exactly) -> G-INVENTORY (census + the
            >= 25 moved-dates power floor) -> imported G3 (ledger identity) and
            G5 (outcome blindness) on every arm that admits positions -> no
            annualised figure anywhere.
  Firewall  NO band value, ceiling value or delta target may be adopted,
            recommended, or carried into a conclusion ON THE BASIS OF ITS P&L.
            The only admissible readings are ARM D's dose-response SHAPE,
            whether an arm exceeds ARM N's 95th percentile, and the census.

NOTHING SHIPS FROM THIS STUDY UNDER ANY OUTCOME. LONG-ONLY-BY-CONSTRUCTION is
the likely verdict, it is registered in advance as a RESULT rather than a null,
and it is publishable.

REFUSES (exit 2) rather than reporting a verdict when the era is too thin to
conclude from; exit 3 is `load_book`'s era guard. See
`DESIGNED_REFUSAL_EXIT_CODES` and `lib/era.py`. A real gate failure is exit 1.

    python -m scripts.backtest_study run portfolio_delta --era v3
    python -m scripts.backtest_study run portfolio_delta -- --gates-only
"""
from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.f4_deployment import account_sim as A  # noqa: E402
from scripts.backtest_study.lib import era  # noqa: E402
from scripts.backtest_study.lib import greeks  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import (  # noqa: E402
    BEAR_DEBIT, hdr, sub,
)
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# Exit codes this study returns as a DESIGNED refusal to produce a result rather
# than as a failure: 2 is the thin-era guard, 3 is `load_book`'s era mismatch.
# `run.py` finds this by AST parse and never imports the module, so it MUST stay
# a literal module-level set assignment — an alias to
# `era.DESIGNED_REFUSAL_EXIT_CODES` (a frozenset() CALL) would be invisible to
# it and a refusal would be reported as FAILED with its report deleted.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}


# ════════════════════════════════════════════════════════════════════════════
# Frozen constants — every one of these was written before the study first ran
# ════════════════════════════════════════════════════════════════════════════

# ARM D's bands, on net delta-notional / equity at SESSION OPEN. Four, frozen.
BANDS = ((0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, float("inf")))

# A descriptive cell under this many positions prints its n and is NOT read.
MIN_CELL_N = 20

# ARM B's ceilings and ARM H*'s targets, both x equity. Five and three, frozen.
CEILINGS = (1.0, 1.5, 2.0, 2.5, float("inf"))
HEDGE_TARGETS = (1.0, 1.5, 2.0)

# ARM N — the null band. 200 draws, seed fixed and PRINTED whether or not the
# draws are taken, so the claim and the number never come apart.
DRAWS = 200
SEED = 20260819
BAND_ALPHA = 0.05          # band = [p5, p95]; the criterion reads "> p95"

# G-INVENTORY's power floor. Declared before the count was knowable.
MIN_MOVED_DATES = 25

# G-DELTA's pre-declared thresholds.
DELTA_TOL = 0.05           # absolute agreement tolerance, leg-sum vs stored
MIN_DELTA_AGREE = 0.90     # >= 90% of cross-checkable rows within DELTA_TOL
MIN_DELTA_AVAIL = 0.95     # >= 95% per-leg availability at the entry day

# The pricing tiers a result must be right-signed on (book.py's `source`).
PRICING_TIERS = ("real", "tweak")

# ARM D's monotonicity read needs at least this many READABLE bands before the
# word "monotone" means anything. Three of the four, declared here.
MIN_READABLE_BANDS = 3

FIREWALL = """  THE FIREWALL (imported verbatim in spirit from account_sim's anti-tuning rule):
  NO band value, ceiling value or delta target may be adopted, recommended, or
  carried into a conclusion ON THE BASIS OF ITS P&L. The ceiling grid is
  monotone by construction in the same way account_sim's cap grid is, and
  reading a winner off it would be reading the construction.

  The ONLY admissible readings from this study are:
    1. ARM D's dose-response SHAPE — monotone, flat, or non-monotone;
    2. whether an arm exceeds ARM N's 95th percentile — a BINARY, not a ranking;
    3. the inventory census — what the book is, and what it can be moved to.
  Everything else printed below is descriptive and is labelled NOT A CRITERION."""


# ════════════════════════════════════════════════════════════════════════════
# Bands — the labelling, and nothing else
# ════════════════════════════════════════════════════════════════════════════

def band_index(x) -> int | None:
    """The frozen band `x` (net delta-notional / equity) falls in, or None.

    None means "outside the registered bands", which on this book has exactly
    one cause: a NET SHORT session. The registration states the deployed ladder
    is long-only (219 of 220 picks positive delta, per-date net never negative),
    so a None here is a finding, not a rounding case — it is counted and
    printed rather than folded into the first band.
    """
    if x is None or x != x:
        return None
    if x < BANDS[0][0]:
        return None
    for i, (lo, hi) in enumerate(BANDS):
        if lo <= x < hi:
            return i
    return None


def band_label(i: int | None) -> str:
    if i is None:
        return "OUT-OF-BANDS"
    lo, hi = BANDS[i]
    hi_s = "inf" if hi == float("inf") else f"{hi:.1f}"
    return f"[{lo:.1f},{hi_s})"


def _cap_label(v: float) -> str:
    return "inf" if v == float("inf") else f"{v:.2f}"


# ════════════════════════════════════════════════════════════════════════════
# The LOCAL fork — `admission_banded` and the walk that uses it
# ════════════════════════════════════════════════════════════════════════════
#
# A deliberate LOCAL COPY of `account_sim.admission()` / `account_sim.simulate()`,
# kept in this module and NOT promoted to `lib/`. The registration says why: a
# signed band with a floor and a ceiling is different machinery from a magnitude
# cap, `account_sim.py` is the file every recorded deployment conclusion rests
# on, and editing it to grow a parameter this study needs would put that
# conclusion at risk for a question account_sim's own firewall forbids it to
# answer.
#
# The fork is gated. G-EQUIV requires that at the COMMITTED `caps.net` — the
# degenerate band — this walk reproduces `account_sim.simulate()`'s book EXACTLY
# under `book_signature()` equality, with and without the hedge sleeve. A fork
# that has drifted is a finding about the fork, and the run stops.

def admission_banded(reserved: float, dn_signed: float, cash: float,
                     net_open: float, cfg, *, equity: float | None = None,
                     net_band: float | None = None) -> tuple[bool, str | None]:
    """`account_sim.admission()` with the net ceiling as a PARAMETER.

    Identical in every other respect, including the fixed constraint order
    (cash -> per-position delta -> net delta) that makes "exactly ONE binding
    constraint" well defined, and including the `EPS` tolerances.

    `net_band=None` means "use `cfg.net_cap`", i.e. the degenerate band, and is
    what G-EQUIV pins against `account_sim.admission()`.
    """
    eq = cfg.capital if equity is None else equity
    ceiling = cfg.net_cap if net_band is None else net_band
    if cfg.enforce_cash and reserved > cash + A.EPS:
        return False, "cash"
    if abs(dn_signed) > cfg.per_pos_cap * eq + A.EPS:
        return False, "per_pos_delta"
    if abs(net_open + dn_signed) > ceiling * eq + A.EPS:
        return False, "net_delta"
    return True, None


def solve_contracts_banded(max_c: int, unit_reserved: float, unit_dn: float,
                           cash: float, net_open: float, cfg, *,
                           equity: float | None = None,
                           net_band: float | None = None) -> int:
    """`account_sim.solve_contracts()` against `admission_banded`.

    Reached only when `cfg.downsize` is set, which the committed config never
    is — carried anyway so the fork is a faithful copy on every path rather
    than on the paths this study happens to walk.
    """
    for c in range(max_c, 0, -1):
        ok, _ = admission_banded(c * unit_reserved, c * unit_dn, cash, net_open,
                                 cfg, equity=equity, net_band=net_band)
        if ok:
            return c
    return 0


def hedge_contracts_for_target(net_open: float, unit_dn: float,
                               target_dollars: float) -> int:
    """ARM H*'s contract count: enough to pull net delta-notional to the target.

    The ONLY thing ARM H* changes about the shipped sleeve. Selection is
    untouched — the |delta|-descending bear pick, one per date, entered AFTER
    the day's signal picks — and so is admission: the count computed here is
    still offered to `admission_banded` and can still be refused, which is
    counted in the `hedge_rejected` census bucket exactly as the shipped rule's
    count is.

    Floors at 1 for the same reason the shipped rule does: the sleeve position
    the shipped rule already opened stays opened. A book already inside the
    target therefore takes the 1-contract floor rather than nothing — which is
    the registration's "only the SIZE of a sleeve position the shipped rule
    already opened changes", not a new admission.
    """
    if unit_dn >= 0:
        # A non-negative-delta candidate cannot reduce net exposure at any size.
        # Nothing to solve for; keep the floor rather than scaling a position
        # that moves the book the wrong way.
        return 1
    need = (net_open - target_dollars) / (-unit_dn)
    if need <= 0:
        return 1
    return max(1, int(math.ceil(need)))


def simulate_banded(day_lists, cfg, bear_by_day: dict | None = None,
                    cache: dict | None = None, *, net_band: float | None = None,
                    hedge_target: float | None = None):
    """`account_sim.simulate()` with a net-delta BAND and a delta-TARGETED sleeve.

    Line-for-line the same event loop — exits before entries, entries admitted
    in ladder order until `cfg.max_per_day` are held, the same census buckets,
    the same occupancy and release rule, the same `replay_sized` call — with
    exactly two substitutions:

      * `admission()` -> `admission_banded(..., net_band=net_band)`  (ARM B)
      * the sleeve's contract count -> `hedge_contracts_for_target(...)` when
        `hedge_target` is given                                       (ARM H*)

    `net_band=None` and `hedge_target=None` is the DEGENERATE configuration and
    must reproduce `account_sim.simulate()` byte-for-byte; G-EQUIV checks it.

    COMPOUNDING IS REFUSED, not silently ignored. This study is registered on
    the frozen, path-INDEPENDENT book, and a fork that quietly dropped the
    re-mark would produce a book that looks like account_sim's and is not.
    """
    if cfg.compound:
        raise ValueError(
            "portfolio_delta is registered on the FROZEN, path-INDEPENDENT book; "
            "simulate_banded does not implement the compounding re-mark and will "
            "not pretend to. Pass a cfg with compound=False.")
    if cache is None:
        cache = A.new_cache()
    sim = A.Sim(cfg=cfg)
    led = A.Ledger(cfg.capital)
    sim.ledger = led
    open_pos: list = []
    net_open = 0.0

    # Static sizing basis — the frozen book. Named rather than inlined so the
    # copy reads against account_sim's own loop line by line.
    equity = float(cfg.capital)
    budget = cfg.budget
    stop = cfg.stop

    def release_before(sess) -> None:
        nonlocal net_open
        for p in sorted([q for q in open_pos if q.exit_sess < sess],
                        key=lambda q: q.exit_sess):
            led.close(p.reserved, p.dollars, f"{p.rec['ticker']} {p.rec['date']}")
            open_pos.remove(p)
            net_open -= p.dn

    def take(rec, contracts, downsized=False, hedge=False):
        nonlocal net_open
        rp = A.replay_sized(rec, contracts, stop, cache=cache)
        if not rp["stop_exact"]:
            sim.stop_inexact += 1
        t = rec["t"]
        pos = A.Pos(rec=rec, contracts=contracts,
                    reserved=rec["max_loss_per_contract"] * contracts,
                    dn=A.signed_dn(rec, contracts),
                    entry_sess=t.grid[0],
                    exit_sess=t.grid[min(rp["days_held"], len(t.grid)) - 1],
                    days_held=rp["days_held"], R=rp["R"], dollars=rp["dollars"],
                    exit_reason=rp["exit_reason"], downsized=downsized,
                    hedge=hedge)
        led.open(pos.reserved, f"{rec['ticker']} {rec['date']}")
        open_pos.append(pos)
        sim.taken.append(pos)
        net_open += pos.dn
        return pos

    for d, ranked in day_lists:
        entry_sess = ranked[0]["t"].grid[0]
        release_before(entry_sess)

        n_today = 0
        for rec in ranked:
            if n_today >= cfg.max_per_day:
                sim.census["day3_cap"] += 1
                sim.skipped.append((rec, "day3_cap", None))
                continue
            mlpc = rec["max_loss_per_contract"]
            c = A.risk_contracts(mlpc, budget)
            if c is None:
                # Unsizable, but the ladder DID select it — it burns the slot.
                sim.census["unsizable"] += 1
                sim.skipped.append((rec, "unsizable", None))
                n_today += 1
                continue
            if mlpc > budget and not cfg.take_floor:
                sim.census["min1_refusal"] += 1
                sim.skipped.append((rec, "min1_refusal",
                                    A.replay_sized(rec, c, stop, cache=cache)))
                continue
            unit_dn = A.signed_dn(rec, 1)
            ok, why = admission_banded(c * mlpc, c * unit_dn, led.cash, net_open,
                                       cfg, equity=equity, net_band=net_band)
            if not ok and cfg.downsize:
                c2 = solve_contracts_banded(c, mlpc, unit_dn, led.cash, net_open,
                                            cfg, equity=equity, net_band=net_band)
                if c2 > 0:
                    sim.downsize_reason[why] += 1
                    sim.census["taken_downsized"] += 1
                    take(rec, c2, downsized=True)
                    n_today += 1
                    continue
            if not ok:
                sim.census[why] += 1
                sim.skipped.append((rec, why,
                                    A.replay_sized(rec, c, stop, cache=cache)))
                continue
            sim.census["taken"] += 1
            take(rec, c)
            n_today += 1

        # The shipped bear sleeve, AFTER the day's signal picks so it can never
        # displace one, and not counted against cfg.max_positions_per_day.
        if cfg.hedge and bear_by_day and d in bear_by_day:
            cands = sorted(
                bear_by_day[d],
                key=lambda r: abs(r["delta"]) if r.get("delta") is not None else -1,
                reverse=True)
            for rec in cands[:1]:
                if rec.get("delta") is None or not rec["max_loss_per_contract"]:
                    continue
                base = A.risk_contracts(rec["max_loss_per_contract"], budget)
                if base is None:
                    continue
                unit_dn = A.signed_dn(rec, 1)
                if hedge_target is None:
                    c = max(1, int(cfg.hedge_risk_fraction * base))
                else:
                    c = hedge_contracts_for_target(net_open, unit_dn,
                                                   hedge_target * equity)
                ok, _ = admission_banded(c * rec["max_loss_per_contract"],
                                         c * unit_dn, led.cash, net_open, cfg,
                                         equity=equity, net_band=net_band)
                if ok:
                    sim.census["hedge_taken"] += 1
                    take(rec, c, hedge=True)
                else:
                    sim.census["hedge_rejected"] += 1

    for p in sorted(open_pos, key=lambda q: q.exit_sess):
        led.close(p.reserved, p.dollars, "final")
    return sim


# ════════════════════════════════════════════════════════════════════════════
# Session-open exposure — the quantity ARM D bands on
# ════════════════════════════════════════════════════════════════════════════

def entry_sessions(day_lists) -> dict:
    """`{signal_date: entry session}`, read the way `simulate()` reads it.

    Every record on a signal date shares `t.grid[0]`, so the first candidate's
    entry session is the date's entry session whichever candidate happens to
    lead the list. Taken from the CANDIDATE lists rather than from the taken
    positions, so a date exists here even in an arm that admitted nothing on it
    — which is what lets G-INVENTORY compare two arms date for date.
    """
    return {d: ranked[0]["t"].grid[0] for d, ranked in day_lists if ranked}


def open_net_before(sim, sess) -> float:
    """Net signed delta-notional of the book OPEN at `sess`, BEFORE its entries.

    `simulate()` runs `release_before(entry_sess)` and only then admits the
    day's picks, so the book an operator would see at session open holds
    exactly the positions with `entry_sess < sess <= exit_sess`. Capital is
    released at the first session AFTER the exit session, which is why the
    upper bound is inclusive.

    This is the same quantity `account_sim.session_series()` reports, minus the
    positions opening on `sess` itself — the series is a post-hoc occupancy
    view that counts a position on its own entry session, and banding on that
    would band a session on picks that had not been made yet. The two are
    reconciled explicitly in the report rather than asserted.
    """
    return sum(p.dn for p in sim.taken
               if p.entry_sess < sess <= p.exit_sess)


def session_bands(sim, entry_by_date: dict, equity: float) -> dict:
    """`{signal_date: (net_before, net_before/equity, band index or None)}`."""
    out = {}
    for d, sess in entry_by_date.items():
        net = open_net_before(sim, sess)
        x = net / equity if equity else float("nan")
        out[d] = (net, x, band_index(x))
    return out


def reconcile_session_series(sim, entry_by_date: dict) -> tuple[int, int]:
    """`(checked, mismatched)` for `open_net_before` vs `session_series`.

    Identity: the occupancy series' net on an entry session equals the
    session-open net PLUS the delta-notional of everything opened that session.
    Printed rather than asserted, because it is the one place this study
    re-derives a quantity account_sim already computes.
    """
    ser = A.session_series(sim)
    opened: dict = defaultdict(float)
    for p in sim.taken:
        opened[p.entry_sess] += p.dn
    checked = bad = 0
    for sess in set(entry_by_date.values()):
        if sess not in ser:
            continue
        checked += 1
        if abs((open_net_before(sim, sess) + opened.get(sess, 0.0))
               - ser[sess]["net"]) > 1e-6:
            bad += 1
    return checked, bad


# ════════════════════════════════════════════════════════════════════════════
# Paired plumbing — mirrors selection_order's, unit = the SESSION
# ════════════════════════════════════════════════════════════════════════════

def positions_of(sim, include_hedge: bool) -> list:
    return sim.taken if include_hedge else sim.signal_pos


def paired_rows(arm, base, dates, include_hedge: bool,
                source: str | None = None) -> tuple[list[dict], int]:
    """One row per date in `dates` where BOTH books hold a position.

    `source` restricts both sides to one pricing tier (`real` / `tweak`) for
    the right-signed-on-both-tiers criterion; a date where one side then holds
    nothing drops out of that tier's rows the same way it does overall.
    """
    def by_date(sim):
        by: dict = defaultdict(list)
        for p in positions_of(sim, include_hedge):
            if source is not None and p.rec.get("source") != source:
                continue
            by[p.rec["date"]].append(p)
        return by

    a_by, b_by = by_date(arm), by_date(base)
    rows, dropped = [], 0
    for d in sorted(dates):
        if d not in a_by or d not in b_by:
            dropped += 1
            continue
        rows.append(dict(
            date=d,
            a=statistics.fmean([p.R for p in a_by[d]]),
            b=statistics.fmean([p.R for p in b_by[d]]),
            gain=(statistics.fmean([p.R for p in a_by[d]])
                  - statistics.fmean([p.R for p in b_by[d]])),
            a_dol=sum(p.dollars for p in a_by[d]),
            b_dol=sum(p.dollars for p in b_by[d])))
    return rows, dropped


def mean_gain(rows) -> float:
    return statistics.fmean(r["gain"] for r in rows) if rows else float("nan")


def ex_both_windows(rows):
    """The cut `protocol.window_cuts` does NOT provide — both dominant windows
    removed at once. Added by hand because an effect can survive each cut
    singly and live entirely in the gap they leave between them."""
    months = {m for ms in P.DOMINANT_WINDOWS.values() for m in ms}
    return [r for r in rows if str(r["date"])[:7] not in months]


def perm_keys(day_lists, seed: int) -> dict:
    """ARM N draw: a seeded within-day permutation, as `{id(rec): sort key}`.

    The pattern is `selection_order.perm_keys`, deliberately: keyed on the
    ladder ORDER rather than on record content, so the SAME seed over a blinded
    copy of the same book produces the same permutation, which is what lets the
    blindness probe reach ARM N at all.
    """
    rng = random.Random(seed)
    keys: dict[int, float] = {}
    for _, ranked in day_lists:
        order = list(range(len(ranked)))
        rng.shuffle(order)
        for rec, k in zip(ranked, order):
            keys[id(rec)] = float(k)
    return keys


def bear_by_day_of(pop) -> dict:
    """The sleeve's candidate pool, exactly as `account_sim.report_population`
    builds it: bear-DEBIT structures only."""
    out: dict = defaultdict(list)
    for r in pop:
        if r["structure"] in BEAR_DEBIT and not r["credit"]:
            out[r["date"]].append(r)
    return dict(out)


# ════════════════════════════════════════════════════════════════════════════
# G-DELTA — the delta SOURCE gate
# ════════════════════════════════════════════════════════════════════════════

def gate_delta(recs) -> bool:
    hdr("G-DELTA — the delta source, cross-checked against the per-leg cache")
    print(f"""  Every band, ceiling and target in this study is a statement about SIGNED
  DELTA-NOTIONAL, so the delta itself is the study's single point of failure.
  The row's stored signed net `delta` is PRIMARY. It is cross-checked against
  the per-leg `Delta` in the cached option-history CSVs, summed at the record's
  common entry day, via scripts/backtest_study/lib/greeks.py.

  Pre-declared thresholds: >= {MIN_DELTA_AGREE:.0%} of cross-checkable rows agree within
  {DELTA_TOL} absolute, AND >= {MIN_DELTA_AVAIL:.0%} per-leg availability at the entry day.
  A missing leg greek is None, NEVER 0.0 (repo invariant): such a row is
  EXCLUDED from the agreement rate and COUNTED, never silently zeroed.""")
    n = len(recs)
    n_stored = sum(1 for r in recs if r.get("delta") is not None)
    diffs = [greeks.delta_agreement(r) for r in recs]
    avail = [d for d in diffs if d is not None]
    n_avail = len(avail)
    n_agree = sum(1 for d in avail if d <= DELTA_TOL)
    availability = n_avail / n if n else float("nan")
    agreement = n_agree / n_avail if n_avail else float("nan")

    print(f"\n  book rows                                  {n:>6}")
    print(f"  stored signed `delta` present              {n_stored:>6}  "
          f"({(n_stored / n if n else float('nan')):.1%})  [PRIMARY]")
    print(f"  per-leg greeks available at the entry day  {n_avail:>6}  "
          f"({availability:.1%})  (threshold {MIN_DELTA_AVAIL:.0%})")
    print(f"  of those, agreeing within {DELTA_TOL}             {n_agree:>6}  "
          f"({agreement:.1%})  (threshold {MIN_DELTA_AGREE:.0%})")
    print(f"  excluded from the cross-check (a leg greek was None, not 0.0): "
          f"{n - n_avail}")
    if avail:
        srt = sorted(avail)
        print(f"  |leg-sum - stored| : median {statistics.median(srt):.4f}  "
              f"p90 {srt[min(len(srt) - 1, int(0.9 * len(srt)))]:.4f}  "
              f"max {srt[-1]:.4f}")
    ok = (n > 0 and n_avail > 0
          and availability >= MIN_DELTA_AVAIL
          and agreement >= MIN_DELTA_AGREE)
    print(f"\n  G-DELTA: {'PASS' if ok else 'FAIL'}")
    if not ok:
        print("  A delta source that cannot be corroborated makes every band in "
              "this study a\n  statement about a number nobody checked. The run "
              "stops here rather than\n  printing a dose-response over it.")
    return ok


# ════════════════════════════════════════════════════════════════════════════
# G-EQUIV — the fork reproduces account_sim EXACTLY at the committed cap
# ════════════════════════════════════════════════════════════════════════════

def gate_equiv(pops: dict, st, cache: dict) -> bool:
    hdr("G-EQUIV — the LOCAL admission fork reproduces account_sim.simulate()")
    print(f"""  ARM B walks a LOCAL copy of account_sim's admission step
  (`admission_banded`), kept in this module and deliberately NOT promoted to
  lib/. At the COMMITTED caps.net ({st.net_cap:.2f}x equity) the banded walk must reproduce
  account_sim.simulate()'s book EXACTLY under book_signature() equality —
  same positions, same order, same contract counts, same R, same dollars, same
  exit reasons. A fork that has drifted is a finding ABOUT THE FORK, and it
  fails the run rather than quietly reporting a band effect that is really a
  copy bug.

  Checked with the sleeve OFF (ARM B's basis) and with the sleeve ON at the
  shipped 1/2-risk size (ARM H*'s baseline), because ARM H* forks that path too.""")
    ok = True
    for label, book in pops.items():
        day_lists, bear = book["day_lists"], book["bear_by_day"]
        for name, hedge in (("sleeve OFF", False), ("sleeve ON (shipped 1/2-risk)", True)):
            cfg = st.cfg(f"G-EQUIV {label} {name}", compound=False, hedge=hedge)
            ref = A.simulate(day_lists, cfg, bear_by_day=bear, cache=cache)
            got = simulate_banded(day_lists, cfg, bear_by_day=bear, cache=cache)
            ref_sig, got_sig = A.book_signature(ref), A.book_signature(got)
            same = ref_sig == got_sig
            ok = ok and same
            print(f"\n  [{label}] {name}")
            print(f"    account_sim.simulate  {len(ref.taken):>4} positions  "
                  f"${sum(p.dollars for p in ref.taken):>10,.0f}")
            print(f"    simulate_banded       {len(got.taken):>4} positions  "
                  f"${sum(p.dollars for p in got.taken):>10,.0f}")
            n_diff = sum(1 for x, y in zip(ref_sig, got_sig) if x != y)
            print(f"    signatures: {len(ref_sig)} vs {len(got_sig)}, differing "
                  f"{n_diff}  -> {'IDENTICAL' if same else 'DIVERGED'}")
            if not same:
                for x, y in zip(ref_sig, got_sig):
                    if x != y:
                        print(f"      FIRST DIVERGENCE  account_sim {x}")
                        print(f"                        banded      {y}")
                        break
    print(f"\n  G-EQUIV: {'PASS' if ok else 'FAIL'}")
    return ok


# ════════════════════════════════════════════════════════════════════════════
# Imported G3 (ledger identity) and G5 (outcome blindness), per ARM
# ════════════════════════════════════════════════════════════════════════════

def gate_ledger(arm_sims: dict) -> bool:
    """account_sim's G3, re-asserted on EVERY arm that admits positions.

    `Ledger._check` runs after every event, so this reads the violations the
    walk already accumulated rather than re-deriving the identity — one
    implementation, checked per arm.
    """
    hdr("IMPORTED G3 — ledger identity on every arm that admits positions")
    print("""  account_sim's Ledger self-checks `cash + reserved == capital + realized`
  after EVERY open and close, and refuses a negative cash. This gate reports
  that check per arm: a band or a re-sized sleeve that admitted a position the
  account could not pay for would show up here and nowhere else.""")
    ok = True
    print(f"\n  {'population':<26}{'arm':<26}{'events':>8}{'positions':>11}"
          f"{'violations':>12}")
    for (label, arm), sim in arm_sims.items():
        led = sim.ledger
        bad = len(led.violations)
        ok = ok and bad == 0
        print(f"  {label:<26}{arm:<26}{led.checks:>8}{len(sim.taken):>11}"
              f"{bad:>12}")
        for v in led.violations[:3]:
            print(f"      VIOLATION {v}")
    print(f"\n  IMPORTED G3: {'PASS' if ok else 'FAIL'}")
    return ok


def gate_blind(pops: dict, st, cache: dict) -> bool:
    """account_sim's G5, run on every arm configuration this study walks.

    The blinded records and their replay memo are built ONCE and reused across
    every blind probe. That is sound where a shared SIGHTED cache would not be:
    the point of the gate is that no blind result may be served from a sighted
    computation, and this cache never sees one.
    """
    hdr("IMPORTED G5 — outcome blindness on every arm")
    print(f"""  Every record is re-wrapped so that reading an outcome key RAISES, and the
  outcome columns are DELETED from the underlying trade row so a read cannot
  route around the wrapper. Each arm must then produce a byte-identical book.
  A delta band that peeks at how a position turned out is worthless: the whole
  point is a rule an operator could run at SESSION OPEN, before anything is
  known.

  row columns deleted from every Trade: {', '.join(sorted(A.LOOKAHEAD_ROW_COLUMNS))}""")
    ok = True
    blind_cache = A.new_cache()
    for label, book in pops.items():
        pop = book["pop"]
        if not pop:
            print(f"\n  [{label}] NOT EVALUABLE — empty population.")
            continue
        blind = A.blind_records(pop)
        tripwire = False
        try:
            _ = blind[0]["R"]
        except A.LookaheadError:
            tripwire = True
        ok = ok and tripwire
        print(f"\n  [{label}] tripwire live (reading a blinded outcome key "
              f"raises): {tripwire}")
        blind_lists = P.ordered_by_day(blind, P.ladder_rank, P.ladder_eligible)
        blind_bear = bear_by_day_of(blind)
        probes = [("D / shipped walk", dict(hedge=False), dict())]
        for cap in CEILINGS:
            probes.append((f"B ceiling {_cap_label(cap)}", dict(hedge=False),
                           dict(net_band=cap)))
        for tgt in HEDGE_TARGETS:
            probes.append((f"H* target {tgt:.2f}", dict(hedge=True),
                           dict(hedge_target=tgt)))
        probes.append(("H* baseline (1/2-risk sleeve)", dict(hedge=True), dict()))
        # ARM N is probed at draw 0 — a random key built off a sighted ordering
        # would be a silent leak, so the permutation is rebuilt on the blind
        # lists under the same seed.
        s_keys = perm_keys(book["day_lists"], SEED)
        b_keys = perm_keys(blind_lists, SEED)
        for name, cfg_kw, walk_kw in probes:
            cfg = st.cfg(f"G5 {label} {name}", compound=False, **cfg_kw)
            a_sig = A.book_signature(simulate_banded(
                book["day_lists"], cfg, bear_by_day=book["bear_by_day"],
                cache=cache, **walk_kw))
            try:
                b_sig = A.book_signature(simulate_banded(
                    blind_lists, cfg, bear_by_day=blind_bear,
                    cache=blind_cache, **walk_kw))
                leaked = None
            except A.LookaheadError as exc:
                b_sig, leaked = None, str(exc)
            ok = _report_blind(name, a_sig, b_sig, leaked) and ok
        # ARM N draw 0.
        cfg = st.cfg(f"G5 {label} N[draw 0]", compound=False)
        a_sig = A.book_signature(simulate_banded(
            P.ordered_by_day(pop, lambda r: s_keys[id(r)], P.ladder_eligible),
            cfg, cache=cache))
        try:
            b_sig = A.book_signature(simulate_banded(
                P.ordered_by_day(blind, lambda r: b_keys[id(r)], P.ladder_eligible),
                cfg, cache=blind_cache))
            leaked = None
        except A.LookaheadError as exc:
            b_sig, leaked = None, str(exc)
        ok = _report_blind("N[draw 0]", a_sig, b_sig, leaked) and ok
    print(f"\n  IMPORTED G5: {'PASS' if ok else 'FAIL'}")
    return ok


def _report_blind(name: str, a_sig, b_sig, leaked) -> bool:
    if leaked:
        print(f"    {name:<30} LOOKAHEAD DETECTED: {leaked}")
        return False
    n_diff = sum(1 for x, y in zip(a_sig, b_sig) if x != y)
    same = a_sig == b_sig and len(a_sig) > 0
    print(f"    {name:<30} sighted {len(a_sig):>4}  blind {len(b_sig):>4}  "
          f"differing {n_diff:>3}  -> {'identical' if same else 'DIVERGED'}")
    return same


def gate_no_annualised() -> bool:
    hdr("NO ANNUALISED FIGURE, SHARPE, OR TIME-TO-RECOVER")
    print("""  By construction: this study prints mean R, within-date paired
  differences, a seeded null band, ledger dollars inside the census, and
  counts. It computes no return per unit time and no risk-adjusted ratio, so
  there is nothing to annualise. Registered as a gate because the temptation
  to add one arrives with the first equity-shaped table.""")
    print("  PASS")
    return True


# ════════════════════════════════════════════════════════════════════════════
# G-INVENTORY — the census, printed FIRST, and the power floor
# ════════════════════════════════════════════════════════════════════════════

def print_inventory_census(picked, bands_by_pop: dict, primary: str, st) -> dict:
    """What the book IS. Printed BEFORE any arm, because it is what decides
    whether any arm could move it.

    `picked` is the WHOLE deployed set — every date the ladder deployed on, not
    just PRIMARY's dense episodes. That is the population the registration's
    disclosed constraint was measured on ("220 picks over 90 dates ... 219 of
    220 positive delta"), and a census scoped to PRIMARY would silently print a
    different number against the same words. The SESSION-OPEN distribution is
    then given per population, because that quantity is a property of the walk
    and each population is walked separately.
    """
    hdr("G-INVENTORY — the census, printed FIRST (it is the finding most "
        "likely to BE the study)")
    print("""  The registration states the central measured constraint up front: the
  deployed ladder is structurally LONG-ONLY. Net delta can only be moved DOWN
  by not trading or by re-sizing the hedge sleeve; a band with a LOWER bound is
  unreachable from below on this book. The census below is that claim, measured
  on the era this run actually loaded.""")
    dates = sorted({r["date"] for r in picked})
    print(f"\n  deployed picks {len(picked)} over {len(dates)} dates"
          + (f"  ({dates[0]} .. {dates[-1]})" if dates else "")
          + "   [the WHOLE deployed set, both populations]")

    sub("structures of the deployed picks")
    structures = Counter(r["structure"] for r in picked)
    for s, n in structures.most_common():
        print(f"  {s:<28}{n:>5}")

    sub("signed delta of the deployed picks")
    deltas = [r.get("delta") for r in picked]
    have = [float(d) for d in deltas if d is not None]
    n_pos = sum(1 for d in have if d > 0)
    n_neg = sum(1 for d in have if d < 0)
    n_zero = sum(1 for d in have if d == 0)
    print(f"  present {len(have)}/{len(deltas)}   positive {n_pos}   "
          f"NEGATIVE {n_neg}   zero {n_zero}   missing {len(deltas) - len(have)}")
    if have:
        srt = sorted(have)
        print(f"  min {srt[0]:+.3f}   p25 {srt[len(srt) // 4]:+.3f}   "
              f"median {statistics.median(srt):+.3f}   "
              f"p75 {srt[3 * len(srt) // 4]:+.3f}   max {srt[-1]:+.3f}")
    if n_neg:
        sub("the negative-delta picks, named (they are the whole short side)")
        for r in picked:
            d = r.get("delta")
            if d is not None and float(d) < 0:
                print(f"  {r['date']}  {r['ticker']:<6} {r['structure']:<22}"
                      f"delta {float(d):+.3f}")

    sub("per-date net delta-notional / equity at SESSION OPEN (shipped walk)")
    print(f"  equity basis ${st.capital:,.0f} — the committed capital, not swept.")
    per_pop = {}
    for label, bands in bands_by_pop.items():
        xs = sorted(x for _, x, _ in bands.values() if x == x)
        if not xs:
            print(f"  [{label}] no deployed date carries a session-open reading.")
            per_pop[label] = dict(xs=[], long_only=False, hist=Counter())
            continue
        print(f"  [{label}] dates {len(xs)}   min {xs[0]:+.3f}   "
              f"p25 {xs[len(xs) // 4]:+.3f}   median {statistics.median(xs):+.3f}   "
              f"p75 {xs[3 * len(xs) // 4]:+.3f}   max {xs[-1]:+.3f}   "
              f"net-SHORT sessions {sum(1 for x in xs if x < 0)}")
        per_pop[label] = dict(xs=xs, long_only=xs[0] >= 0.0,
                              hist=Counter(b for _, _, b in bands.values()))

    sub("deployed dates by band, shipped walk")
    print(f"  {'band':<16}" + "".join(f"{lab:>28}" for lab in bands_by_pop))
    for i in list(range(len(BANDS))) + [None]:
        print(f"  {band_label(i):<16}"
              + "".join(f"{per_pop[lab]['hist'].get(i, 0):>28}"
                        for lab in bands_by_pop))
    print("  (OUT-OF-BANDS = net SHORT sessions, outside the registered bands)")

    prim = per_pop.get(primary, dict(xs=[], long_only=False, hist=Counter()))
    return dict(structures=structures, n_neg=n_neg, n_pos=n_pos,
                min_x=prim["xs"][0] if prim["xs"] else float("nan"),
                max_x=prim["xs"][-1] if prim["xs"] else float("nan"),
                long_only=prim["long_only"], hist=prim["hist"],
                per_pop=per_pop)


def gate_inventory_power(label: str, shipped_bands: dict,
                         arm_bands: dict) -> dict:
    """The PRE-DECLARED power rule, per arm.

    An arm that cannot move >= MIN_MOVED_DATES deployed DATES into a DIFFERENT
    band than the shipped walk puts them in is UNDERPOWERED: its cells are not
    read and no criterion is evaluated on it. Declared before the counts were
    known, which is the whole point — the long-only constraint makes this the
    likely outcome for ARM B.
    """
    hdr(f"[{label}] G-INVENTORY — the POWER FLOOR (pre-declared, "
        f">= {MIN_MOVED_DATES} moved dates)")
    print(f"""  For each arm: how many deployed DATES the arm puts in a DIFFERENT
  session-open band than the shipped walk does. A date one arm reaches and the
  other does not counts as MOVED (band vs no band is a difference). Under
  {MIN_MOVED_DATES} moved dates the arm is UNDERPOWERED — census published, nothing read,
  no criterion evaluated, and no re-run on these dates.""")
    print(f"\n  {'arm':<30}{'moved dates':>12}{'of':>6}   status")
    out = {}
    all_dates = set(shipped_bands)
    for arm, bands in arm_bands.items():
        all_dates |= set(bands)
    for arm, bands in arm_bands.items():
        moved = {d for d in all_dates
                 if (shipped_bands.get(d, (None, None, None))[2]
                     != bands.get(d, (None, None, None))[2])}
        powered = len(moved) >= MIN_MOVED_DATES
        out[arm] = dict(moved=moved, n_moved=len(moved), powered=powered)
        print(f"  {arm:<30}{len(moved):>12}{len(all_dates):>6}   "
              f"{'ok' if powered else 'UNDERPOWERED'}")
    cleared = [a for a, v in out.items() if v["powered"]]
    print(f"\n  arms cleared for reading: "
          f"{', '.join(cleared) if cleared else 'NONE — every arm underpowered'}")
    return out


# ════════════════════════════════════════════════════════════════════════════
# ARM D — the dose-response. DESCRIPTIVE PRIMARY, zero new ledger code.
# ════════════════════════════════════════════════════════════════════════════

def arm_d(label: str, sim, shipped_bands: dict) -> dict:
    hdr(f"[{label}] ARM D — DOSE-RESPONSE (descriptive primary)")
    print(f"""  A conditional read of the SHIPPED book: no counterfactual, no forked
  admission, nothing re-simulated. Every session is labelled by the open book's
  net delta-notional / equity at SESSION OPEN, BEFORE that day's picks are
  admitted, and the positions OPENED in each band are reported. The operator
  question it asks is exactly: does adding exposure onto an already-long book
  pay worse?

  MIN_CELL_N = {MIN_CELL_N} positions. A band under it prints its n and IS NOT READ.
  Mean R is quoted, never dollars — every band is a different composition.""")
    by_band: dict = defaultdict(list)
    for p in sim.signal_pos:
        b = shipped_bands.get(p.rec["date"], (None, None, None))[2]
        by_band[b].append(p)

    print(f"\n  {'band':<16}{'n':>5}{'dates':>7}{'meanR':>9}{'win':>8}"
          f"{'CI95 (date-clustered)':>28}   read?")
    cells = {}
    for i in list(range(len(BANDS))) + [None]:
        ps = by_band.get(i, [])
        if not ps:
            print(f"  {band_label(i):<16}{0:>5}{0:>7}{'—':>9}{'—':>8}"
                  f"{'—':>28}   no (empty)")
            cells[i] = dict(n=0, mean=float("nan"), readable=False)
            continue
        rows = [dict(date=p.rec["date"], R=p.R) for p in ps]
        m = statistics.fmean([p.R for p in ps])
        win = sum(1 for p in ps if p.R > 0) / len(ps)
        lo, hi = P.boot_ci_by_date(rows, key="R")
        readable = len(ps) >= MIN_CELL_N
        print(f"  {band_label(i):<16}{len(ps):>5}"
              f"{len({p.rec['date'] for p in ps}):>7}{m:>+9.3f}{win:>8.2f}"
              f"{f'[{lo:+.3f}, {hi:+.3f}]':>28}   "
              f"{'yes' if readable else f'NO (n < {MIN_CELL_N})'}")
        cells[i] = dict(n=len(ps), mean=m, readable=readable, rows=rows,
                        ci=(lo, hi))

    sub("per-year cut, each band (protocol.by_year — every year present)")
    print(f"  {'band':<16}" + "  ".join(f"{y:>16}" for y in sorted(
        {p.rec["date"][:4] for p in sim.signal_pos})))
    years = sorted({p.rec["date"][:4] for p in sim.signal_pos})
    for i in list(range(len(BANDS))) + [None]:
        ps = by_band.get(i, [])
        if not ps:
            continue
        row = f"  {band_label(i):<16}"
        for y in years:
            vals = [p.R for p in ps if p.rec["date"][:4] == y]
            row += (f"{statistics.fmean(vals):>+11.3f} (n={len(vals):>2})"
                    if vals else f"{'—':>16}  ")
        print(row)

    sub("window cuts, each READABLE band (ALL / the two dominant windows / "
        "ex-BOTH)")
    for i in list(range(len(BANDS))) + [None]:
        c = cells.get(i)
        if not c or not c.get("readable"):
            continue
        cuts = dict(P.window_cuts(c["rows"]))
        cuts["ex_BOTH_windows"] = ex_both_windows(c["rows"])
        line = f"  {band_label(i):<16}"
        for k, rs in cuts.items():
            # A cut that removes every row of a band prints EMPTY rather than a
            # nan: "no rows survived this cut" and "the mean was undefined" read
            # the same in a fixed-width report, and only the first is true.
            line += (f"  {k} {statistics.fmean([r['R'] for r in rs]):+.3f} "
                     f"(n={len(rs)})" if rs else f"  {k} EMPTY (n=0)")
        print(line)

    readable = [i for i in range(len(BANDS))
                if cells.get(i, {}).get("readable")]
    means = [cells[i]["mean"] for i in readable]
    monotone = (len(readable) >= MIN_READABLE_BANDS
                and (all(a >= b for a, b in zip(means, means[1:]))
                     or all(a <= b for a, b in zip(means, means[1:]))))
    sub("the SHAPE — the only admissible reading of this arm")
    print(f"  readable bands (n >= {MIN_CELL_N}): "
          f"{', '.join(band_label(i) for i in readable) if readable else 'NONE'}"
          f"   (>= {MIN_READABLE_BANDS} needed before 'monotone' means anything)")
    if len(readable) < MIN_READABLE_BANDS:
        print("  SHAPE: NOT READABLE — too few n-sufficient bands to call the "
              "relationship\n  monotone, flat, or non-monotone. Recorded as "
              "such; not a null.")
    else:
        print("  meanR across readable bands: "
              + "  ".join(f"{band_label(i)} {cells[i]['mean']:+.3f}"
                          for i in readable))
        print(f"  SHAPE: {'MONOTONE' if monotone else 'NON-MONOTONE / FLAT'}  "
              f"(descriptive — NOT A CRITERION, and no band value may be "
              f"adopted on it)")
    return dict(cells=cells, readable=readable, monotone=monotone)


# ════════════════════════════════════════════════════════════════════════════
# ARM N — the null band
# ════════════════════════════════════════════════════════════════════════════

def random_band(label: str, pop, base, dates, st, cache: dict,
                include_hedge: bool) -> dict:
    sub(f"[{label}] ARM N — the null band ({DRAWS} seeded random admissions, "
        f"seed {SEED})")
    print("""  ARM N decides the meaning of the others. The registered reading is
  explicit: an arm must beat ARM N's 95th PERCENTILE, not merely beat the
  shipped book. An arm inside the band is noise, whatever its point estimate.
  Each draw is a seeded within-day permutation of the SAME candidate list,
  walked through the SAME ledger — matched on positions per date by
  construction, since the day cap and the sizing are untouched.""")
    ladder_lists = P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible)
    draws = []
    for i in range(DRAWS):
        keys = perm_keys(ladder_lists, SEED + i)
        lists = P.ordered_by_day(pop, lambda r: keys[id(r)], P.ladder_eligible)
        sim = simulate_banded(lists, st.cfg(f"{label} N[{i}]", compound=False),
                              cache=cache)
        rows, _ = paired_rows(sim, base, dates, include_hedge)
        if rows:
            draws.append(mean_gain(rows))
    if not draws:
        print("  no evaluable draws.")
        return dict(draws=[], p95=float("nan"))
    draws.sort()
    p5 = draws[int(BAND_ALPHA * len(draws))]
    p95 = draws[min(len(draws) - 1, int((1 - BAND_ALPHA) * len(draws)))]
    inside = p5 <= 0.0 <= p95
    print(f"\n  draws {len(draws)}   min {draws[0]:+.4f}   p5 {p5:+.4f}   "
          f"median {statistics.median(draws):+.4f}   p95 {p95:+.4f}   "
          f"max {draws[-1]:+.4f}")
    print(f"  the shipped walk (gain 0 by definition) sits "
          f"{'INSIDE' if inside else 'OUTSIDE'} the band [p5, p95].")
    return dict(draws=draws, p95=p95, p5=p5, inside=inside)


# ════════════════════════════════════════════════════════════════════════════
# The adoption bar — the full conjunction from the registration
# ════════════════════════════════════════════════════════════════════════════

def evaluate_arm(name: str, arm_sim, base_sim, dates, moved: set, band: dict,
                 label: str, include_hedge: bool) -> dict:
    sub(f"[{label}] {name} — the adoption bar (failing any one part is failing)")
    rows, dropped = paired_rows(arm_sim, base_sim, dates, include_hedge)
    print(f"  paired dates {len(rows)} (dropped {dropped} where one book held "
          f"nothing)")
    res = dict(arm=name, n_rows=len(rows))
    if not rows:
        print("  no paired dates — NOT EVALUABLE")
        res["pass"] = False
        res["gain"] = float("nan")
        return res

    g = mean_gain(rows)
    ci_lo, ci_hi = P.boot_ci_paired_by_date(rows, "a", "b")
    c1 = g > 0 and ci_lo > 0
    print(f"  (1) paired mean gain {g:+.4f} R   CI95 [{ci_lo:+.4f}, {ci_hi:+.4f}] "
          f"(date-clustered, BOOT_N={P.BOOT_N})  -> {'PASS' if c1 else 'FAIL'}")

    loo_mean, loo_share, loo_min, loo_n = P.loo_by_date(
        rows, lambda r: r["a"], lambda r: r["b"])
    c2 = loo_n > 0 and loo_share == 1.0 and loo_min > 0
    print(f"  (2) LOO by date: folds {loo_n}  mean {loo_mean:+.4f}  share>0 "
          f"{loo_share:.0%}  MIN {loo_min:+.4f}  -> {'PASS' if c2 else 'FAIL'}")

    cuts = dict(P.window_cuts(rows))
    cuts["ex_BOTH_windows"] = ex_both_windows(rows)
    cut_g = {k: mean_gain(v) for k, v in cuts.items() if v}
    c3 = bool(cut_g) and all(v > 0 for v in cut_g.values()) and len(cut_g) == 4
    print("  (3) window cuts: " + "  ".join(
        f"{k} {v:+.4f} (n={len(cuts[k])})" for k, v in cut_g.items())
        + f"  -> {'PASS' if c3 else 'FAIL'}")

    years = P.by_year(rows)
    ymeans = {y: mean_gain(rs) for y, rs in years.items()}
    c4 = bool(ymeans) and all(v > 0 for v in ymeans.values())
    print("  (4) by year: " + "  ".join(f"{y} {v:+.4f} (n={len(years[y])})"
                                        for y, v in ymeans.items())
          + f"  -> {'PASS' if c4 else 'FAIL'}")

    tier_g = {}
    for tier in PRICING_TIERS:
        t_rows, _ = paired_rows(arm_sim, base_sim, dates, include_hedge,
                                source=tier)
        if t_rows:
            tier_g[tier] = mean_gain(t_rows)
    c5 = bool(tier_g) and all(v > 0 for v in tier_g.values())
    print("  (5) pricing tiers right-signed: " + ("  ".join(
        f"{k} {v:+.4f}" for k, v in tier_g.items()) or "no tier carried rows")
        + f"  -> {'PASS' if c5 else 'FAIL'}")

    c6 = len(moved) >= MIN_MOVED_DATES
    print(f"  (6) moved dates {len(moved)} (>= {MIN_MOVED_DATES})  "
          f"-> {'PASS' if c6 else 'FAIL'}")

    p95 = band.get("p95")
    c7 = p95 is not None and p95 == p95 and g > p95
    pct = (sum(1 for x in band.get("draws", []) if x < g)
           / len(band["draws"])) if band.get("draws") else float("nan")
    print(f"  (7) ARM N band p95 {p95:+.4f} (seed {SEED}, {DRAWS} draws); this "
          f"arm {g:+.4f} sits at pct {pct:.0%}  -> {'PASS' if c7 else 'FAIL'}")

    dol = sum(r["a_dol"] - r["b_dol"] for r in rows)
    print(f"  dollars alongside (SANITY CHECK ONLY — composition-dependent, "
          f"quote R): {dol:+,.0f}")

    parts = dict(c1=c1, c2=c2, c3=c3, c4=c4, c5=c5, c6=c6, c7=c7)
    res.update(parts, gain=g, ci=(ci_lo, ci_hi), loo_min=loo_min, dollars=dol,
               band_pct=pct)
    res["pass"] = all(parts.values())
    failed = ", ".join(k for k, v in parts.items() if not v)
    print(f"  => {name}: " + ("CANDIDATE (all seven) — queued for an "
                              "INDEPENDENT window, nothing ships"
                              if res["pass"] else f"FAILS {failed}"))
    return res


# ════════════════════════════════════════════════════════════════════════════
# Books and the per-population report
# ════════════════════════════════════════════════════════════════════════════

def build_books(recs, dates_allowed, label: str, st, cache: dict) -> dict:
    """Every arm's book for one population. Computes NOTHING readable.

    Split out from the reporting so the census and G-INVENTORY's power floor can
    print BEFORE any outcome number, which is what the registration means by
    the census coming first.
    """
    pop = [r for r in recs if r["date"] in dates_allowed]
    day_lists = P.ordered_by_day(pop, P.ladder_rank, P.ladder_eligible)
    bear = bear_by_day_of(pop)
    entry_by_date = entry_sessions(day_lists)

    # ARM D's basis: account_sim.simulate() UNCHANGED at the committed config.
    shipped = A.simulate(day_lists, st.cfg(f"{label} shipped", compound=False),
                         cache=cache)
    # ARM H*'s baseline: the shipped 1/2-risk sleeve.
    sleeve_base = A.simulate(day_lists,
                             st.cfg(f"{label} sleeve", compound=False, hedge=True),
                             bear_by_day=bear, cache=cache)

    arms = {}
    for cap in CEILINGS:
        arms[f"B ceiling {_cap_label(cap)}"] = dict(
            sim=simulate_banded(day_lists,
                                st.cfg(f"{label} B {_cap_label(cap)}",
                                       compound=False),
                                cache=cache, net_band=cap),
            base="shipped", hedge=False)
    for tgt in HEDGE_TARGETS:
        arms[f"H* target {tgt:.2f}"] = dict(
            sim=simulate_banded(day_lists,
                                st.cfg(f"{label} H* {tgt:.2f}", compound=False,
                                       hedge=True),
                                bear_by_day=bear, cache=cache, hedge_target=tgt),
            base="sleeve", hedge=True)

    equity = st.capital
    return dict(pop=pop, day_lists=day_lists, bear_by_day=bear,
                entry_by_date=entry_by_date, shipped=shipped,
                sleeve_base=sleeve_base, arms=arms,
                shipped_bands=session_bands(shipped, entry_by_date, equity),
                sleeve_bands=session_bands(sleeve_base, entry_by_date, equity),
                arm_bands={name: session_bands(a["sim"], entry_by_date, equity)
                           for name, a in arms.items()})


def print_arm_census(label: str, book: dict) -> None:
    """Every arm's book, census columns only. Outcome columns are withheld
    until G-INVENTORY has cleared an arm — an arm's mean R IS its cell."""
    sub(f"[{label}] arm census — positions, dates, sleeve, and where the caps bound")
    print(f"  {'arm':<30}{'sig pos':>9}{'sleeve':>8}{'dates':>7}"
          f"{'net_delta excl':>16}{'sleeve rej':>12}")
    rows = [("shipped walk (ARM D basis)", book["shipped"]),
            ("shipped + 1/2-risk sleeve", book["sleeve_base"])]
    rows += [(name, a["sim"]) for name, a in book["arms"].items()]
    for name, sim in rows:
        print(f"  {name:<30}{len(sim.signal_pos):>9}"
              f"{sum(1 for p in sim.taken if p.hedge):>8}"
              f"{len(sim.dates):>7}{sim.census['net_delta']:>16}"
              f"{sim.census['hedge_rejected']:>12}")


def report_population(label: str, book: dict, st, cache: dict) -> dict:
    hdr(f"{label.upper()} — arms, band, and the adoption bar")
    print_arm_census(label, book)

    checked, bad = reconcile_session_series(book["shipped"],
                                            book["entry_by_date"])
    print(f"\n  session-open reconciliation vs account_sim.session_series(): "
          f"{checked} sessions checked, {bad} mismatched"
          + ("" if bad == 0 else "   *** THE BAND LABELS ARE NOT TRUSTWORTHY ***"))

    d = arm_d(label, book["shipped"], book["shipped_bands"])

    g_inv = gate_inventory_power(label, book["shipped_bands"], book["arm_bands"])

    powered = [a for a, v in g_inv.items() if v["powered"]]
    if not powered:
        sub(f"[{label}] ARM N — NOT RUN  (seed {SEED}, {DRAWS} draws, not taken)")
        print(f"""  The null band exists to serve criterion (7). Every arm is
  UNDERPOWERED at G-INVENTORY, so there is no criterion to serve and the {DRAWS}
  draws are not taken. The seed is stated anyway ({SEED}) so the arm is
  reproducible by anyone re-running it on a book that can be moved.""")
        return dict(arm_d=d, g_inventory=g_inv, band={}, band_hedge={},
                    results={})

    # Two bands, because the two arm families are read against two baselines:
    # ARM B against the shipped walk (sleeve off), ARM H* against the shipped
    # 1/2-risk sleeve (sleeve on, positions include it).
    need_b = any(not book["arms"][a]["hedge"] for a in powered)
    need_h = any(book["arms"][a]["hedge"] for a in powered)
    band = (random_band(label, book["pop"], book["shipped"],
                        set(book["entry_by_date"]), st, cache,
                        include_hedge=False) if need_b else {})
    band_h = (random_band(f"{label} (sleeve basis)", book["pop"],
                          book["sleeve_base"], set(book["entry_by_date"]), st,
                          cache, include_hedge=True) if need_h else {})

    results = {}
    for name, arm in book["arms"].items():
        if not g_inv[name]["powered"]:
            sub(f"[{label}] {name} — UNDERPOWERED at "
                f"{g_inv[name]['n_moved']} moved dates")
            print(f"  Not read. No criterion is evaluated on this arm "
                  f"(threshold {MIN_MOVED_DATES}, declared before the count was "
                  f"knowable).")
            continue
        base = book["sleeve_base"] if arm["hedge"] else book["shipped"]
        results[name] = evaluate_arm(
            name, arm["sim"], base, set(book["entry_by_date"]),
            g_inv[name]["moved"], band_h if arm["hedge"] else band, label,
            include_hedge=arm["hedge"])
    return dict(arm_d=d, g_inventory=g_inv, band=band, band_hedge=band_h,
                results=results)


# ════════════════════════════════════════════════════════════════════════════
# Verdict — the four registered labels, and the mapping made TOTAL
# ════════════════════════════════════════════════════════════════════════════
#
# The registration words four verdicts: LONG-ONLY-BY-CONSTRUCTION,
# DELTA-DOSE-RESPONSE, NOISE, UNDERPOWERED. They are not disjoint by
# construction — a book can be long-only AND show a readable dose response — so
# the PRECEDENCE below is fixed here, before any number was seen, and companion
# findings are printed alongside the headline rather than being dropped:
#
#   1. every arm underpowered AND the census shows a long-only book
#      -> LONG-ONLY-BY-CONSTRUCTION  (the registration's LIKELY verdict, and it
#         is a result rather than a null: "target a portfolio delta" is not an
#         available lever on this book, and the sleeve is the only dial)
#   2. every arm underpowered, book NOT long-only  -> UNDERPOWERED
#   3. any arm passes the FULL §Bar conjunction    -> CANDIDATE-FOR-INDEPENDENT-WINDOW
#   4. ARM D readable and monotone                  -> DELTA-DOSE-RESPONSE
#   5. otherwise                                    -> NOISE
#
# 1 outranks 4 deliberately: if nothing can move the book, the dose-response is
# a description of a book with one available state, and leading with it would
# invite exactly the adoption the firewall forbids. ARM D's shape is still
# printed in full and is carried as a companion finding.
#
# 3 is the registration's 2026-08-27 amendment (grammar completion, no
# criterion moved): the full-pass combination was worded in §Bar from the
# start ("even a full pass is a CANDIDATE queued for an independent window")
# but never mapped to a label, so the 2026-08-27 run's first full-bar pass
# fell through to NOISE — a headline the same report's checklist line
# contradicted. Unreachable under 1/2 (a pass requires a powered arm).
#
# NOISE is doing double duty as the CATCH-ALL, and that is stated on the page
# rather than hidden in the precedence. Its registered wording is "no arm
# exceeds ARM N's 95th percentile AND ARM D's bands are flat within their
# cells"; a run where an arm DID clear criterion (7) and then failed the rest of
# the conjunction matches neither that wording nor any of the other three
# original labels. Rather than invent a label after seeing a number, the
# catch-all fires and a QUALIFICATION naming those arms is printed underneath
# it — the same discipline account_sim's 2026-08-14 verdict-grammar amendment
# used: the checklist above is the whole result, the label only states what it
# means.

def print_verdict(out: dict, census: dict, label: str) -> str:
    hdr(f"VERDICT ({label} — grammar worded in the pre-registration)")
    g_inv = out["g_inventory"]
    powered = [a for a, v in g_inv.items() if v["powered"]]
    winners = [a for a, r in out["results"].items() if r.get("pass")]
    d = out["arm_d"]
    print(f"  arms powered (G-INVENTORY): "
          f"{', '.join(powered) if powered else 'none'}")
    print(f"  arms clearing the whole bar:  "
          f"{', '.join(winners) if winners else 'none'}")
    print(f"  ARM D readable bands: "
          f"{', '.join(band_label(i) for i in d['readable']) or 'none'}   "
          f"shape: {'MONOTONE' if d['monotone'] else 'not monotone / not readable'}")
    print(f"  census: long-only book: {census['long_only']}   "
          f"negative-delta picks {census['n_neg']} of "
          f"{census['n_neg'] + census['n_pos']}   per-date net/equity range "
          f"[{census['min_x']:+.2f}, {census['max_x']:+.2f}]")

    if not powered and census["long_only"]:
        v = ("LONG-ONLY-BY-CONSTRUCTION — the census and G-INVENTORY show the "
             "deployed ladder cannot be moved to a materially different "
             "net-delta level without either not trading or re-sizing the "
             "sleeve. 'Target a portfolio delta' is NOT an available lever on "
             "this book; the sleeve is the only dial.")
    elif not powered:
        v = (f"UNDERPOWERED — every arm moved fewer than {MIN_MOVED_DATES} deployed dates "
             f"into a different band. Census published, nothing read, and NO "
             f"re-run on these dates.")
    elif winners:
        v = (f"CANDIDATE-FOR-INDEPENDENT-WINDOW — "
             f"{', '.join(winners)} clear{'s' if len(winners) == 1 else ''} "
             f"the full adoption-eligibility conjunction. Queued for an "
             f"independent window and NOTHING ELSE — nothing ships from this "
             f"study under any outcome, and no ceiling or target value may be "
             f"adopted on its P&L. (Label per the registration's 2026-08-27 "
             f"grammar-completion amendment.)")
    elif d["monotone"] and len(d["readable"]) >= MIN_READABLE_BANDS:
        v = ("DELTA-DOSE-RESPONSE — ARM D shows a monotone, n-sufficient "
             "relationship between open-book delta at session open and the "
             "outcome of positions opened there. DESCRIPTIVE: it queues an "
             "independent-window confirmation and may THEN be proposed as a "
             "context note, never as an automatic cap.")
    else:
        v = ("NOISE — no arm exceeds ARM N's 95th percentile and ARM D's bands "
             "do not separate within their cells. Recorded; thread closed for "
             "these dates.")

    print(f"\n  >>> {v} <<<")
    beat_null = [a for a, r in out["results"].items() if r.get("c7")]
    if v.startswith("NOISE") and beat_null:
        print(f"""
  QUALIFICATION on the label above (printed because the catch-all fired, not
  because the wording matched): {', '.join(beat_null)} DID clear criterion (7)
  — it sits above ARM N's 95th percentile — and then failed the rest of the
  conjunction. NOISE is carrying it as the catch-all rather than a fifth label
  being invented after the number was seen. Read the per-arm checklist above:
  it is the whole result, and nothing on it is adoption-eligible.""")
    if not powered and census["long_only"] and d["readable"]:
        print("""
  COMPANION FINDING, explicitly NOT a verdict upgrade: ARM D's bands above are
  printed in full and some of them are n-sufficient. They describe a book with
  effectively one reachable exposure state, which is why the headline is the
  constraint and not the shape. Reading a band value off them would be reading
  the construction — see THE FIREWALL.""")
    return v


# ════════════════════════════════════════════════════════════════════════════
# Driver
# ════════════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m scripts.backtest_study.f4_deployment.portfolio_delta",
        description=__doc__.splitlines()[0])
    ap.add_argument("--gates-only", action="store_true",
                    help="run G-DELTA / G-EQUIV / G3 / G5 and the census, then "
                         "stop before any arm grid is read")
    # `argv` (not `argv or []`): None must fall through to sys.argv, or a flag
    # typed on the command line is silently ignored and the run reports
    # something other than what was asked for.
    args = ap.parse_args(argv)

    st = A.load_settings(A.DEFAULT_CONFIG)

    hdr("portfolio_delta — is there a net delta LEVEL the deployed book should hold?")
    print(f"""  config    {A.DEFAULT_CONFIG.relative_to(ROOT)}  (as committed; NO cap,
            capital, risk-%, or positions/day value is swept by this study)
  Basis     load_book(include_bs=False), proxy calibration gate ON, eras never
            pooled, compounding OFF (the frozen, path-independent book).
  Frozen    Tier membership, candidate universe, sizing, caps and exits are
            EXACTLY account_sim's, imported unchanged. This study adds no new
            ledger semantics; the ONLY new machinery is a LOCAL, G-EQUIV-gated
            copy of the admission step.
  Capital   ${st.capital:,.0f}, risk {st.risk_pct:.0%} = ${st.budget:,.0f}/position,
            {st.max_per_day} positions/day, per-position cap {st.per_pos_cap:.2f}x,
            net cap {st.net_cap:.2f}x equity.
  NOTHING SHIPS FROM THIS STUDY UNDER ANY OUTCOME.""")
    print()
    print(FIREWALL)

    A.print_configuration(st, A.DEFAULT_CONFIG.relative_to(ROOT))

    recs, diag = load_book(include_bs=False)
    print(f"\n  era: {diag['era']}  book dates={diag['n_dates']}  "
          f"{diag['date_range'][0]} .. {diag['date_range'][1]}")
    era.require_dates(diag["n_dates"], diag["era"],
                      what="a book whose deployed dates can carry a "
                           "session-open exposure band at all; G-INVENTORY's "
                           "25-moved-date power floor is a tighter test on top")

    picked = P.top_k_per_day(recs, P.ladder_rank, k=st.max_per_day,
                             eligible_fn=P.ladder_eligible)
    print(f"  book: {len(recs)} rows  counts_by_source={diag['counts_by_source']}"
          f"  deployed picks {len(picked)}")

    A.print_book_calibration(diag, picked)

    cache = A.new_cache()

    # ── G-DELTA runs first: every band below is a claim about delta ──────────
    if not gate_delta(recs):
        print("\nGATE FAILURE (G-DELTA) — no results printed. Exit 1.")
        return 1

    episodes = A.dense_episodes(
        (d for d, _ in P.ordered_by_day(recs, P.ladder_rank, P.ladder_eligible)),
        max_gap=st.episode_max_gap, min_dates=st.episode_min_dates)
    ep_dates = {d for ep in episodes for d in ep}
    all_dates = {r["date"] for r in recs}
    print(f"\n  PRIMARY   dense episodes: {len(episodes)} episodes, "
          f"{len(ep_dates)} dates")
    print(f"  SECONDARY full book: {len(all_dates)} dates (reported, carries "
          f"nothing — the same convention account_sim and selection_order run "
          f"under)")

    refusal = A.primary_refusal(all_dates, ep_dates, st)
    if refusal:
        print(f"\nREFUSED — {refusal}")
        return era.EXIT_THIN_ERA

    pops = {"PRIMARY dense episodes": ep_dates, "SECONDARY full book": all_dates}
    books = {label: build_books(recs, dates, label, st, cache)
             for label, dates in pops.items()}

    # ── the census, printed BEFORE any arm outcome ──────────────────────────
    primary = "PRIMARY dense episodes"
    census = print_inventory_census(
        picked, {label: b["shipped_bands"] for label, b in books.items()},
        primary, st)

    gates = {}
    gates["G-EQUIV"] = gate_equiv(books, st, cache)
    arm_sims = {(label, "shipped walk"): b["shipped"] for label, b in books.items()}
    arm_sims.update({(label, "shipped + 1/2-risk sleeve"): b["sleeve_base"]
                     for label, b in books.items()})
    for label, b in books.items():
        for name, arm in b["arms"].items():
            arm_sims[(label, name)] = arm["sim"]
    gates["IMPORTED G3"] = gate_ledger(arm_sims)
    gates["IMPORTED G5"] = gate_blind(books, st, cache)
    gates["NO-ANNUALISED"] = gate_no_annualised()
    if not all(gates.values()):
        print("\nGATE FAILURE — "
              + ", ".join(k for k, v in gates.items() if not v)
              + ". No arm results printed. Exit 1.")
        return 1

    if args.gates_only:
        print("\n--gates-only: gates passed and the census is printed; stopping "
              "before the arm grids.")
        return 0

    out = {label: report_population(label, book, st, cache)
           for label, book in books.items()}

    verdict = print_verdict(out[primary], census, primary)

    hdr("STANDING CAVEAT (required by the pre-registration to appear here)")
    print(f"""  The ladder is itself IN-SAMPLE (fitted on this book), so any exposure rule
  evaluated on the same book is SECOND-ORDER in-sample. The mitigations are that
  these are mechanical, entry-side, SESSION-OPEN rules with no fitted threshold,
  and that adoption requires out-of-fold survival. The caveat does not disappear
  if the numbers look good.

  Anti-tuning: bands frozen at four, ceilings at five, targets at three, ARM N at
  {DRAWS} seeded draws. Capital, risk %, per-position cap, net cap, positions/day,
  take_floor, downsize and the exit profiles are NOT swept — they come from
  {A.DEFAULT_CONFIG.name} at their committed values for every arm. Compounding OFF.
  No new selection column. Every arm and every cell is reported regardless of
  outcome, including the ones that lose and the ones that come up underpowered, and no
  threshold was moved after a number was seen.

  Random-control seed: {SEED} (fixed; draw i uses SEED + i over {DRAWS} draws). Stated
  whether or not ARM N was drawn, so the claim and the number never come apart.""")

    hdr("CLOSE")
    print(f"  verdict: {verdict}")
    print("  G-DELTA: PASS")
    for k, v in gates.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    print("  Nothing in this report is a shippable rule. No band value, ceiling "
          "or delta target\n  may be adopted on P&L — see THE FIREWALL at the "
          "top of this report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
